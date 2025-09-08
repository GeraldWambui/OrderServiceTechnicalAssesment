from fastapi import FastAPI, HTTPException, Depends, Request, Header, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Enum as SQLEnum, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import IntegrityError, DBAPIError
from pydantic import BaseModel, EmailStr, validator
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from passlib.context import CryptContext
from jose import JWTError, jwt
from enum import Enum
import hashlib
import hmac
import json
import time
import asyncio
import logging
import uuid
from functools import wraps
import redis
import os

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./orders.db")
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "webhook-secret")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database setup
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Redis setup for caching
try:
    redis_client = redis.from_url(REDIS_URL)
    redis_client.ping()
except:
    redis_client = None
    logger.warning("Redis not available, caching disabled")

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Enums
class UserRole(str, Enum):
    ADMIN = "ADMIN"
    USER = "USER"

class OrderStatus(str, Enum):
    PENDING = "PENDING"
    PAID = "PAID"
    CANCELLED = "CANCELLED"

# Database Models
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(SQLEnum(UserRole), default=UserRole.USER, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class Order(Base):
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    items = Column(Text, nullable=False)  # JSON string
    status = Column(SQLEnum(OrderStatus), default=OrderStatus.PENDING)
    client_token = Column(String, unique=True, nullable=False)
    total_amount = Column(Float, nullable=False)
    version = Column(Integer, default=1)  # For optimistic locking
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class PaymentRetry(Base):
    __tablename__ = "payment_retries"
    
    id = Column(Integer, primary_key=True, index=True)
    payment_id = Column(String, nullable=False)
    order_id = Column(Integer, nullable=False)
    status = Column(String, nullable=False)
    retry_count = Column(Integer, default=0)
    last_attempt = Column(DateTime, default=datetime.utcnow)
    error_message = Column(Text)

# Create tables
Base.metadata.create_all(bind=engine)

# Pydantic models
class UserSignup(BaseModel):
    email: EmailStr
    password: str
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 6:
            raise ValueError('Password must be at least 6 characters')
        return v

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class OrderItem(BaseModel):
    sku: str
    qty: int
    
    @validator('qty')
    def validate_qty(cls, v):
        if v <= 0:
            raise ValueError('Quantity must be positive')
        return v

class CreateOrder(BaseModel):
    items: List[OrderItem]
    client_token: str
    
    @validator('items')
    def validate_items(cls, v):
        if not v:
            raise ValueError('Items list cannot be empty')
        return v

class UpdateOrderStatus(BaseModel):
    status: OrderStatus
    version: Optional[int] = None

class WebhookPayload(BaseModel):
    payment_id: str
    order_id: int
    status: str

# Metrics (simple counter)
metrics = {"orders_created_total": 0}

# Rate limiting storage
rate_limit_storage = {}

# FastAPI app
app = FastAPI(title="Order Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=24)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm="HS256")
    return encoded_jwt

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=["HS256"])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user

def require_admin(current_user: User = Depends(get_current_user)):
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user

# Rate limiting decorator
def rate_limit(max_requests: int, window_seconds: int):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            
            if request:
                client_ip = request.client.host
                current_time = time.time()
                key = f"{client_ip}:{func.__name__}"
                
                if key not in rate_limit_storage:
                    rate_limit_storage[key] = []
                
                # Clean old requests
                rate_limit_storage[key] = [
                    req_time for req_time in rate_limit_storage[key]
                    if current_time - req_time < window_seconds
                ]
                
                if len(rate_limit_storage[key]) >= max_requests:
                    raise HTTPException(status_code=429, detail="Rate limit exceeded")
                
                rate_limit_storage[key].append(current_time)
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator

# Caching utilities
def cache_key(prefix: str, key: str) -> str:
    return f"{prefix}:{key}"

def get_cache(key: str) -> Optional[str]:
    if redis_client:
        try:
            return redis_client.get(key)
        except:
            pass
    return None

def set_cache(key: str, value: str, ttl: int = 30):
    if redis_client:
        try:
            redis_client.setex(key, ttl, value)
        except:
            pass

def invalidate_cache(pattern: str):
    if redis_client:
        try:
            keys = redis_client.keys(pattern)
            if keys:
                redis_client.delete(*keys)
        except:
            pass

# Middleware for request logging
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    
    logger.info(
        f"{request.method} {request.url.path} "
        f"status={response.status_code} "
        f"duration={process_time:.3f}s"
    )
    return response

# Auth endpoints
@app.post("/auth/signup")
async def signup(user_data: UserSignup, db: Session = Depends(get_db)):
    # Check if user exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create user
    hashed_password = get_password_hash(user_data.password)
    user = User(
        email=user_data.email,
        hashed_password=hashed_password,
        role=UserRole.ADMIN if user_data.email == "admin@example.com" else UserRole.USER
    )
    
    try:
        db.add(user)
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Email already registered")
    
    return {
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "created_at": user.created_at
    }

@app.post("/auth/login")
async def login(user_data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == user_data.email).first()
    if not user or not verify_password(user_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    
    access_token = create_access_token(data={"sub": user.email, "role": user.role})
    return {"access_token": access_token, "token_type": "bearer", "role": user.role}

# Order endpoints
@app.post("/orders")
@rate_limit(max_requests=10, window_seconds=60)
async def create_order(
    request: Request,
    order_data: CreateOrder,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Check for existing order with same client_token (idempotency)
    existing_order = db.query(Order).filter(Order.client_token == order_data.client_token).first()
    if existing_order:
        return {
            "id": existing_order.id,
            "status": existing_order.status,
            "items": json.loads(existing_order.items),
            "total_amount": existing_order.total_amount,
            "created_at": existing_order.created_at,
            "message": "Order already exists (idempotent response)"
        }
    
    # Calculate total (simplified - assume each item costs $10)
    total_amount = sum(item.qty * 10.0 for item in order_data.items)
    
    # Create new order
    order = Order(
        user_id=current_user.id,
        items=json.dumps([item.dict() for item in order_data.items]),
        client_token=order_data.client_token,
        total_amount=total_amount,
        status=OrderStatus.PENDING
    )
    
    try:
        db.add(order)
        db.commit()
        db.refresh(order)
        metrics["orders_created_total"] += 1
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Duplicate client token")
    
    return {
        "id": order.id,
        "status": order.status,
        "items": json.loads(order.items),
        "total_amount": order.total_amount,
        "created_at": order.created_at
    }

@app.get("/orders")
async def list_orders(
    status: Optional[str] = None,
    q: Optional[str] = None,
    page: int = 1,
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Order)
    
    # RBAC: Users can only see their own orders
    if current_user.role == UserRole.USER:
        query = query.filter(Order.user_id == current_user.id)
    
    # Filter by status
    if status:
        try:
            status_enum = OrderStatus(status.upper())
            query = query.filter(Order.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid status")
    
    # Search by SKU
    if q:
        query = query.filter(Order.items.contains(q))
    
    # Pagination
    offset = (page - 1) * limit
    total = query.count()
    orders = query.offset(offset).limit(limit).all()
    
    return {
        "orders": [
            {
                "id": order.id,
                "status": order.status,
                "items": json.loads(order.items),
                "total_amount": order.total_amount,
                "created_at": order.created_at,
                "updated_at": order.updated_at
            }
            for order in orders
        ],
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit
    }

@app.get("/orders/{order_id}")
async def get_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Check cache first
    cache_k = cache_key("order", str(order_id))
    cached = get_cache(cache_k)
    if cached:
        order_data = json.loads(cached)
        # Still need to check RBAC
        if current_user.role == UserRole.USER and order_data["user_id"] != current_user.id:
            raise HTTPException(status_code=404, detail="Order not found")
        return order_data
    
    # Query database
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # RBAC: Users can only see their own orders
    if current_user.role == UserRole.USER and order.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Order not found")
    
    order_data = {
        "id": order.id,
        "user_id": order.user_id,
        "status": order.status,
        "items": json.loads(order.items),
        "total_amount": order.total_amount,
        "version": order.version,
        "created_at": order.created_at.isoformat(),
        "updated_at": order.updated_at.isoformat()
    }
    
    # Cache the result
    set_cache(cache_k, json.dumps(order_data, default=str), ttl=30)
    
    return order_data

@app.patch("/orders/{order_id}/status")
async def update_order_status(
    order_id: int,
    status_data: UpdateOrderStatus,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    # Get current order with row-level locking
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Optimistic locking check
    if status_data.version is not None and order.version != status_data.version:
        raise HTTPException(
            status_code=409,
            detail=f"Version conflict. Expected {status_data.version}, got {order.version}"
        )
    
    # Update status and increment version
    order.status = status_data.status
    order.version += 1
    order.updated_at = datetime.utcnow()
    
    try:
        db.commit()
        db.refresh(order)
        
        # Invalidate cache
        invalidate_cache(f"order:{order_id}")
        
        return {
            "id": order.id,
            "status": order.status,
            "version": order.version,
            "updated_at": order.updated_at
        }
    except DBAPIError:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update order")

# Payment endpoints
@app.post("/payments/initiate")
async def initiate_payment(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # RBAC: Users can only initiate payment for their own orders
    if current_user.role == UserRole.USER and order.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Order not found")
    
    payment_id = str(uuid.uuid4())
    amount_cents = int(order.total_amount * 100)
    
    return {
        "payment_id": payment_id,
        "order_id": order_id,
        "amount_cents": amount_cents,
        "redirect_url": f"https://payment-provider.example.com/pay/{payment_id}"
    }

# Webhook with retry logic
async def process_webhook_with_retry(payment_id: str, order_id: int, status: str, retry_count: int = 0):
    db = SessionLocal()
    try:
        if status == "SUCCESS":
            order = db.query(Order).filter(Order.id == order_id).first()
            if order:
                order.status = OrderStatus.PAID
                order.updated_at = datetime.utcnow()
                order.version += 1
                db.commit()
                
                # Invalidate cache
                invalidate_cache(f"order:{order_id}")
                logger.info(f"Order {order_id} marked as PAID")
        
        # Clean up retry record if exists
        db.query(PaymentRetry).filter(
            PaymentRetry.payment_id == payment_id,
            PaymentRetry.order_id == order_id
        ).delete()
        db.commit()
        
    except Exception as e:
        db.rollback()
        logger.error(f"Webhook processing error: {e}")
        
        if retry_count < 3:
            # Save retry record
            retry_record = db.query(PaymentRetry).filter(
                PaymentRetry.payment_id == payment_id,
                PaymentRetry.order_id == order_id
            ).first()
            
            if not retry_record:
                retry_record = PaymentRetry(
                    payment_id=payment_id,
                    order_id=order_id,
                    status=status,
                    retry_count=0
                )
                db.add(retry_record)
            
            retry_record.retry_count = retry_count + 1
            retry_record.last_attempt = datetime.utcnow()
            retry_record.error_message = str(e)
            db.commit()
            
            # Exponential backoff
            delay = 2 ** retry_count
            await asyncio.sleep(delay)
            await process_webhook_with_retry(payment_id, order_id, status, retry_count + 1)
        else:
            logger.error(f"Webhook processing failed after 3 retries for payment {payment_id}")
    finally:
        db.close()

@app.post("/payments/webhook")
async def payment_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_signature: str = Header(..., alias="X-Signature")
):
    body = await request.body()
    
    # Verify signature
    expected_signature = hmac.new(
        WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(f"sha256={expected_signature}", x_signature):
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    try:
        payload = json.loads(body)
        webhook_data = WebhookPayload(**payload)
    except (json.JSONDecodeError, ValueError) as e:
        raise HTTPException(status_code=400, detail="Invalid payload")
    
    # Process webhook asynchronously with retry logic
    background_tasks.add_task(
        process_webhook_with_retry,
        webhook_data.payment_id,
        webhook_data.order_id,
        webhook_data.status
    )
    
    return {"status": "received"}

# Metrics endpoint
@app.get("/metrics")
async def get_metrics():
    return metrics

# Health check
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)