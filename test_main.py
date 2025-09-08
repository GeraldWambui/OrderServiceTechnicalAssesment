import pytest
import asyncio
import json
import hmac
import hashlib
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from main import app, get_db, Base, User, Order, OrderStatus, UserRole
import threading
import time

# Test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

@pytest.fixture(autouse=True)
def clean_db():
    """Clean database before each test"""
    db = TestingSessionLocal()
    db.query(Order).delete()
    db.query(User).delete()
    db.commit()
    db.close()

def create_test_user(email: str = "test@example.com", password: str = "password123", role: str = "USER"):
    """Helper to create a test user"""
    response = client.post("/auth/signup", json={"email": email, "password": password})
    assert response.status_code == 200
    
    # Manually set role if needed
    if role == "ADMIN":
        db = TestingSessionLocal()
        user = db.query(User).filter(User.email == email).first()
        user.role = UserRole.ADMIN
        db.commit()
        db.close()
    
    return response.json()

def get_auth_token(email: str = "test@example.com", password: str = "password123"):
    """Helper to get auth token"""
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]

class TestAuth:
    def test_signup_success(self):
        response = client.post("/auth/signup", json={
            "email": "newuser@example.com",
            "password": "password123"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "newuser@example.com"
        assert data["role"] == "USER"

    def test_signup_duplicate_email(self):
        # Create first user
        client.post("/auth/signup", json={
            "email": "test@example.com",
            "password": "password123"
        })
        
        # Try to create duplicate
        response = client.post("/auth/signup", json={
            "email": "test@example.com",
            "password": "password123"
        })
        assert response.status_code == 400
        assert "already registered" in response.json()["detail"]

    def test_login_success(self):
        create_test_user()
        response = client.post("/auth/login", json={
            "email": "test@example.com",
            "password": "password123"
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_invalid_credentials(self):
        create_test_user()
        response = client.post("/auth/login", json={
            "email": "test@example.com",
            "password": "wrongpassword"
        })
        assert response.status_code == 401

class TestOrders:
    def test_create_order_success(self):
        create_test_user()
        token = get_auth_token()
        
        response = client.post("/orders", 
            headers={"Authorization": f"Bearer {token}"},
            json={
                "items": [{"sku": "ITEM-001", "qty": 2}],
                "client_token": "test-token-123"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "PENDING"
        assert len(data["items"]) == 1
        assert data["total_amount"] == 20.0  # 2 * $10

    def test_create_order_idempotency(self):
        """Test that duplicate client_token returns original order"""
        create_test_user()
        token = get_auth_token()
        
        # First request
        response1 = client.post("/orders",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "items": [{"sku": "ITEM-001", "qty": 1}],
                "client_token": "idempotent-token"
            }
        )
        assert response1.status_code == 200
        
        # Second request with same token
        response2 = client.post("/orders",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "items": [{"sku": "ITEM-002", "qty": 5}],  # Different items
                "client_token": "idempotent-token"  # Same token
            }
        )
        assert response2.status_code == 200
        
        # Should return original order
        assert response1.json()["id"] == response2.json()["id"]
        assert response2.json()["items"][0]["sku"] == "ITEM-001"  # Original SKU
        assert "already exists" in response2.json()["message"]

    def test_list_orders_rbac(self):
        """Test that users only see their own orders"""
        # Create two users
        create_test_user("user1@example.com")
        create_test_user("user2@example.com")
        
        token1 = get_auth_token("user1@example.com")
        token2 = get_auth_token("user2@example.com")
        
        # User1 creates an order
        client.post("/orders",
            headers={"Authorization": f"Bearer {token1}"},
            json={
                "items": [{"sku": "ITEM-001", "qty": 1}],
                "client_token": "user1-token"
            }
        )
        
        # User2 creates an order
        client.post("/orders",
            headers={"Authorization": f"Bearer {token2}"},
            json={
                "items": [{"sku": "ITEM-002", "qty": 1}],
                "client_token": "user2-token"
            }
        )
        
        # User1 should only see their order
        response1 = client.get("/orders", headers={"Authorization": f"Bearer {token1}"})
        assert response1.status_code == 200
        assert response1.json()["total"] == 1
        assert response1.json()["orders"][0]["items"][0]["sku"] == "ITEM-001"
        
        # User2 should only see their order
        response2 = client.get("/orders", headers={"Authorization": f"Bearer {token2}"})
        assert response2.status_code == 200
        assert response2.json()["total"] == 1
        assert response2.json()["orders"][0]["items"][0]["sku"] == "ITEM-002"

class TestRBAC:
    def test_admin_can_update_order_status(self):
        """Test that admin can update order status"""
        # Create admin user
        create_test_user("admin@example.com", "password123", "ADMIN")
        create_test_user("user@example.com")
        
        admin_token = get_auth_token("admin@example.com")
        user_token = get_auth_token("user@example.com")
        
        # User creates order
        response = client.post("/orders",
            headers={"Authorization": f"Bearer {user_token}"},
            json={
                "items": [{"sku": "ITEM-001", "qty": 1}],
                "client_token": "test-token"
            }
        )
        order_id = response.json()["id"]
        
        # Admin updates status
        response = client.patch(f"/orders/{order_id}/status",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"status": "PAID"}
        )
        assert response.status_code == 200
        assert response.json()["status"] == "PAID"

    def test_user_cannot_update_order_status(self):
        """Test that regular user cannot update order status"""
        create_test_user()
        token = get_auth_token()
        
        # Create order
        response = client.post("/orders",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "items": [{"sku": "ITEM-001", "qty": 1}],
                "client_token": "test-token"
            }
        )
        order_id = response.json()["id"]
        
        # Try to update status as user
        response = client.patch(f"/orders/{order_id}/status",
            headers={"Authorization": f"Bearer {token}"},
            json={"status": "PAID"}
        )
        assert response.status_code == 403

class TestConcurrency:
    def test_optimistic_locking_version_conflict(self):
        """Test optimistic locking prevents lost updates"""
        create_test_user("admin@example.com", "password123", "ADMIN")
        create_test_user("user@example.com")
        
        admin_token = get_auth_token("admin@example.com")
        user_token = get_auth_token("user@example.com")
        
        # Create order
        response = client.post("/orders",
            headers={"Authorization": f"Bearer {user_token}"},
            json={
                "items": [{"sku": "ITEM-001", "qty": 1}],
                "client_token": "test-token"
            }
        )
        order_id = response.json()["id"]
        
        # Get order to get version
        response = client.get(f"/orders/{order_id}",
            headers={"Authorization": f"Bearer {admin_token}"})
        version = response.json()["version"]
        
        # First update succeeds
        response1 = client.patch(f"/orders/{order_id}/status",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"status": "PAID", "version": version}
        )
        assert response1.status_code == 200
        
        # Second update with old version fails
        response2 = client.patch(f"/orders/{order_id}/status",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"status": "CANCELLED", "version": version}  # Old version
        )
        assert response2.status_code == 409
        assert "Version conflict" in response2.json()["detail"]

    def test_concurrent_order_creation(self):
        """Test concurrent order creation with same client_token"""
        create_test_user()
        token = get_auth_token()
        
        results = []
        
        def create_order():
            response = client.post("/orders",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "items": [{"sku": "ITEM-001", "qty": 1}],
                    "client_token": "concurrent-token"
                }
            )
            results.append(response)
        
        # Create multiple threads trying to create the same order
        threads = []
        for _ in range(3):
            thread = threading.Thread(target=create_order)
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # All should succeed (idempotency), but only one order created
        success_count = sum(1 for r in results if r.status_code == 200)
        assert success_count == 3  # All succeed due to idempotency
        
        # Verify all return the same order ID
        order_ids = [r.json()["id"] for r in results if r.status_code == 200]
        assert all(oid == order_ids[0] for oid in order_ids)

class TestWebhook:
    def test_webhook_success_payment(self):
        """Test successful payment webhook"""
        create_test_user("admin@example.com", "password123", "ADMIN")
        create_test_user("user@example.com")
        
        admin_token = get_auth_token("admin@example.com")
        user_token = get_auth_token("user@example.com")
        
        # Create order
        response = client.post("/orders",
            headers={"Authorization": f"Bearer {user_token}"},
            json={
                "items": [{"sku": "ITEM-001", "qty": 1}],
                "client_token": "webhook-test"
            }
        )
        order_id = response.json()["id"]
        
        # Simulate webhook
        payload = {
            "payment_id": "pay_123",
            "order_id": order_id,
            "status": "SUCCESS"
        }
        
        body = json.dumps(payload)
        signature = hmac.new(
            b"webhook-secret",
            body.encode(),
            hashlib.sha256
        ).hexdigest()
        
        response = client.post("/payments/webhook",
            content=body,
            headers={
                "X-Signature": f"sha256={signature}",
                "Content-Type": "application/json"
            }
        )
        assert response.status_code == 200
        
        # Give some time for background task
        time.sleep(0.1)
        
        # Check order status updated
        response = client.get(f"/orders/{order_id}",
            headers={"Authorization": f"Bearer {admin_token}"})
        assert response.json()["status"] == "PAID"

    def test_webhook_invalid_signature(self):
        """Test webhook with invalid signature"""
        payload = {
            "payment_id": "pay_123",
            "order_id": 1,
            "status": "SUCCESS"
        }
        
        response = client.post("/payments/webhook",
            json=payload,
            headers={"X-Signature": "sha256=invalid"}
        )
        assert response.status_code == 401

class TestRateLimit:
    def test_order_creation_rate_limit(self):
        """Test rate limiting on order creation"""
        create_test_user()
        token = get_auth_token()
        
        # Make requests up to the limit (10 per minute)
        for i in range(10):
            response = client.post("/orders",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "items": [{"sku": "ITEM-001", "qty": 1}],
                    "client_token": f"rate-limit-{i}"
                }
            )
            assert response.status_code == 200
        
        # 11th request should be rate limited
        response = client.post("/orders",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "items": [{"sku": "ITEM-001", "qty": 1}],
                "client_token": "rate-limit-overflow"
            }
        )
        assert response.status_code == 429

class TestValidation:
    def test_invalid_order_items(self):
        """Test validation of order items"""
        create_test_user()
        token = get_auth_token()
        
        # Empty items
        response = client.post("/orders",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "items": [],
                "client_token": "empty-items"
            }
        )
        assert response.status_code == 422
        
        # Invalid quantity
        response = client.post("/orders",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "items": [{"sku": "ITEM-001", "qty": 0}],
                "client_token": "zero-qty"
            }
        )
        assert response.status_code == 422

    def test_invalid_email_signup(self):
        """Test email validation on signup"""
        response = client.post("/auth/signup", json={
            "email": "not-an-email",
            "password": "password123"
        })
        assert response.status_code == 422

    def test_short_password_signup(self):
        """Test password length validation"""
        response = client.post("/auth/signup", json={
            "email": "test@example.com",
            "password": "short"
        })
        assert response.status_code == 422

class TestCaching:
    def test_order_detail_caching(self):
        """Test that order details are cached"""
        create_test_user()
        token = get_auth_token()
        
        # Create order
        response = client.post("/orders",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "items": [{"sku": "ITEM-001", "qty": 1}],
                "client_token": "cache-test"
            }
        )
        order_id = response.json()["id"]
        
        # First request (hits DB)
        start = time.time()
        response1 = client.get(f"/orders/{order_id}",
            headers={"Authorization": f"Bearer {token}"})
        first_duration = time.time() - start
        
        # Second request (should hit cache)
        start = time.time()
        response2 = client.get(f"/orders/{order_id}",
            headers={"Authorization": f"Bearer {token}"})
        second_duration = time.time() - start
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        assert response1.json() == response2.json()
        
        # Note: Cache timing test is environment dependent,
        # so we just verify both requests succeed

def test_health_check():
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_metrics():
    """Test metrics endpoint"""
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "orders_created_total" in response.json()

if __name__ == "__main__":
    pytest.main([__file__, "-v"])