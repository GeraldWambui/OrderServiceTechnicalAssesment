# Order Service

A comprehensive order management system built with FastAPI and React, featuring authentication, role-based access control, payment processing, and webhook integration.

## 🚀 Quick Start

### One-Command Setup (Docker)

```bash
# Clone the repository
git clone <repository-url>
cd order-service

# Start everything with Docker
docker-compose up -d

# Access the admin UI
open http://localhost/admin
```

### Manual Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Run setup script
chmod +x setup.sh
./setup.sh

# Or start manually
uvicorn main:app --reload
```

## 🏗️ Architecture

### Core Components

- **FastAPI Backend**: RESTful API with automatic OpenAPI documentation
- **React Admin UI**: Modern single-page application for order management
- **PostgreSQL**: Primary database with optimistic locking
- **Redis**: Caching layer for improved performance
- **Nginx**: Reverse proxy and static file serving

### Key Features

#### Part A - Secure Backend Service
- ✅ **JWT Authentication** with HS256 signing
- ✅ **Role-Based Access Control** (ADMIN, USER)
- ✅ **Idempotent Order Creation** with client tokens
- ✅ **Optimistic Locking** for concurrent updates
- ✅ **Input Validation** with detailed error messages
- ✅ **Database Migrations** with SQLAlchemy
- ✅ **Comprehensive Tests** (16 test cases)
- ✅ **Request Logging & Metrics** with Prometheus-style counters
- ✅ **Rate Limiting** (10 requests/minute for order creation)

#### Part B - External Integration
- ✅ **Payment Webhook Integration** with HMAC signature verification
- ✅ **Idempotent Webhook Handling** safe for replays
- ✅ **Exponential Backoff Retry** (3 attempts with exponential delay)
- ✅ **Response Caching** (30s TTL with cache invalidation)
- ✅ **Dead Letter Queue** logging for failed retries

#### Part C - Admin UI
- ✅ **JWT Authentication** with role verification
- ✅ **Paginated Orders Table** with search functionality
- ✅ **Real-time Status Updates** via PATCH requests
- ✅ **Error Handling** with toast notifications
- ✅ **Responsive Design** with Tailwind CSS

## 🛡️ Security Features

### Authentication & Authorization
- JWT tokens with expiration
- Password hashing with bcrypt
- Role-based endpoint protection
- Request signature verification for webhooks

### Data Protection
- SQL injection prevention via SQLAlchemy ORM
- Input validation with Pydantic models
- CORS configuration for cross-origin requests
- Rate limiting to prevent abuse

### Concurrency Safety
- Optimistic locking with version columns
- Atomic database transactions
- Idempotent operations to prevent duplicates

## 📊 API Documentation

### Authentication Endpoints

```http
POST /auth/signup
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "password123"
}
```

```http
POST /auth/login
Content-Type: application/json

{
  "email": "user@example.com", 
  "password": "password123"
}

Response: {
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer",
  "role": "USER"
}
```

### Order Management

```http
POST /orders
Authorization: Bearer <token>
Content-Type: application/json

{
  "items": [
    {"sku": "WIDGET-001", "qty": 2},
    {"sku": "GADGET-002", "qty": 1}
  ],
  "client_token": "unique-client-token-123"
}
```

```http
GET /orders?status=PENDING&q=WIDGET&page=1&limit=10
Authorization: Bearer <token>

Response: {
  "orders": [...],
  "total": 25,
  "page": 1,
  "limit": 10,
  "pages": 3
}
```

```http
PATCH /orders/123/status
Authorization: Bearer <admin-token>
Content-Type: application/json

{
  "status": "PAID",
  "version": 1
}
```

### Payment Integration

```http
POST /payments/initiate
Authorization: Bearer <token>
Content-Type: application/json

{
  "order_id": 123
}

Response: {
  "payment_id": "pay_abc123",
  "order_id": 123,
  "amount_cents": 3000,
  "redirect_url": "https://payment-provider.example.com/pay/pay_abc123"
}
```

```http
POST /payments/webhook
X-Signature: sha256=<hmac-signature>
Content-Type: application/json

{
  "payment_id": "pay_abc123",
  "order_id": 123,
  "status": "SUCCESS"
}
```

## 🧪 Testing

### Running Tests

```bash
# Run all tests
pytest -v

# Run specific test categories
pytest -k "test_auth" -v
pytest -k "test_rbac" -v  
pytest -k "test_concurrency" -v
pytest -k "test_webhook" -v
```

### Test Coverage

- **Authentication Tests**: Signup, login, validation
- **RBAC Tests**: Role-based access control
- **Idempotency Tests**: Duplicate request handling
- **Concurrency Tests**: Optimistic locking, race conditions
- **Webhook Tests**: Payment processing, signature verification
- **Rate Limiting Tests**: Request throttling
- **Validation Tests**: Input sanitization

### Manual Testing

```bash
# Create demo data
./setup.sh

# Test payment webhook
python payment_simulator.py success 1
python payment_simulator.py failed 2

# Load testing (requires artillery)
artillery quick --count 10 --num 50 http://localhost:8000/health
```

## 🔧 Configuration

### Environment Variables

```bash
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/orderdb
# or for SQLite: sqlite:///./orders.db

# Security
SECRET_KEY=your-jwt-secret-key-here
WEBHOOK_SECRET=your-webhook-secret-here

# Caching
REDIS_URL=redis://localhost:6379

# Optional
DEBUG=true
LOG_LEVEL=INFO
```

### Docker Configuration

```yaml
# docker-compose.yml
version: '3.8'
services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://orderuser:orderpass@db:5432/orderdb
      - SECRET_KEY=production-secret-key
      - REDIS_URL=redis://redis:6379
```

## 📈 Monitoring & Observability

### Health Checks

```http
GET /health
Response: {
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Metrics

```http
GET /metrics
Response: {
  "orders_created_total": 1250
}
```

### Logging

All requests are logged with:
- HTTP method and path
- Response status code
- Request duration
- Client IP (when behind proxy)

```
INFO:     POST /orders status=200 duration=0.125s
INFO:     GET /orders?page=1 status=200 duration=0.045s
INFO:     PATCH /orders/123/status status=200 duration=0.089s
```

## 🔄 Deployment

### Production Checklist

- [ ] Change default secrets in environment variables
- [ ] Configure HTTPS termination
- [ ] Set up database backups
- [ ] Configure log aggregation
- [ ] Set up monitoring and alerting
- [ ] Review rate limiting configuration
- [ ] Test disaster recovery procedures

### Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: order-service
spec:
  replicas: 3
  selector:
    matchLabels:
      app: order-service
  template:
    metadata:
      labels:
        app: order-service
    spec:
      containers:
      - name: api
        image: order-service:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: order-service-secrets
              key: database-url
        - name: SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: order-service-secrets  
              key: jwt-secret
```

## 🛠️ Development

### Project Structure

```
order-service/
├── main.py                 # FastAPI application
├── requirements.txt        # Python dependencies
├── test_main.py           # Test suite
├── admin.html             # React admin UI
├── payment_simulator.py   # Payment webhook simulator
├── generate_openapi.py    # API documentation generator
├── setup.sh              # Development setup script
├── Dockerfile            # Container configuration
├── docker-compose.yml    # Multi-service orchestration
├── nginx.conf           # Reverse proxy configuration
└── README.md            # This file
```

### Adding New Features

1. **New Endpoint**:
   - Add route in `main.py`
   - Add Pydantic models for request/response
   - Add tests in `test_main.py`
   - Update OpenAPI documentation

2. **Database Changes**:
   - Modify SQLAlchemy models in `main.py`
   - Create migration script (or recreate dev DB)
   - Update tests and documentation

3. **Frontend Updates**:
   - Modify React components in `admin.html`
   - Test in browser with demo data
   - Update user documentation

### Code Quality

```bash
# Format code
black main.py test_main.py

# Check types  
mypy main.py

# Security scan
bandit -r .

# Lint
flake8 main.py test_main.py
```

## 🚨 Troubleshooting

### Common Issues

**Database Connection Errors**
```bash
# Check database status
docker-compose logs db

# Reset database
docker-compose down -v
docker-compose up -d db
```

**Redis Connection Issues**
```bash
# Check Redis status
docker-compose logs redis

# Test Redis connection
redis-cli -h localhost ping
```

**Authentication Problems**
```bash
# Verify JWT token
python -c "
import jwt
token = 'your-token-here'
print(jwt.decode(token, options={'verify_signature': False}))
"
```

**Rate Limiting Issues**
```bash
# Clear rate limit storage (development only)
curl -X DELETE http://localhost:8000/admin/rate-limits
```

### Debug Mode

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
uvicorn main:app --reload --log-level debug

# Watch logs in real-time
docker-compose logs -f api
```

## 📚 API Reference

Full API documentation is available at:
- **Interactive Docs**: http://localhost:8000/docs (Swagger UI)
- **Alternative Docs**: http://localhost:8000/redoc (ReDoc)
- **OpenAPI Spec**: http://localhost:8000/openapi.json

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make changes and add tests
4. Run the test suite: `pytest -v`
5. Submit a pull request

### Development Guidelines

- Follow PEP 8 for Python code style
- Write tests for new features
- Update documentation for API changes
- Use semantic commit messages
- Keep functions small and focused

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- FastAPI for the excellent web framework
- SQLAlchemy for robust database ORM
- React for the frontend framework
- Tailwind CSS for utility-first styling
- Docker for containerization
- PostgreSQL and Redis for data storage

---

**Built with ❤️ for modern web applications**

---

## 🏗️ System Design for Scale (10k req/s)

### Architecture Diagram

```
                    ┌─────────────────┐
                    │   Load Balancer │
                    │   (nginx/ALB)   │
                    └─────────┬───────┘
                              │
                    ┌─────────▼───────┐
                    │   API Gateway   │
                    │ (rate limiting) │
                    └─────────┬───────┘
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
    ┌─────▼─────┐       ┌─────▼─────┐       ┌─────▼─────┐
    │   API     │       │   API     │       │   API     │
    │ Server 1  │       │ Server 2  │       │ Server N  │
    └─────┬─────┘       └─────┬─────┘       └─────┬─────┘
          │                   │                   │
          └───────────────────┼───────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
   ┌────▼────┐         ┌──────▼──────┐        ┌─────▼─────┐
   │ Redis   │         │  Message    │        │  Master   │
   │Cluster  │         │   Queue     │        │    DB     │
   │(Cache)  │         │(RabbitMQ/   │        │(Write)    │
   └─────────┘         │ AWS SQS)    │        └─────┬─────┘
                       └─────────────┘              │
                                                    │
                                        ┌───────────┼───────────┐
                                   ┌────▼────┐ ┌────▼────┐ ┌────▼────┐
                                   │ Read    │ │ Read    │ │ Read    │
                                   │Replica 1│ │Replica 2│ │Replica N│
                                   └─────────┘ └─────────┘ └─────────┘
```

### Scaling Strategy to 10k req/s

#### **Horizontal Scaling**
- **API Servers**: 15-20 instances behind load balancer
- **Database**: Master-slave replication with 3-5 read replicas
- **Cache**: Redis cluster with 3-6 nodes for high availability
- **Message Queue**: Clustered RabbitMQ or AWS SQS for webhook processing

#### **Performance Optimizations**
```
Component           Current Capacity    Scaled Capacity    Strategy
──────────────────────────────────────────────────────────────────
API Servers         100 req/s          10k req/s          20x instances
Database Reads      500 req/s          8k req/s           5x read replicas  
Database Writes     200 req/s          2k req/s           Connection pooling
Cache Hit Rate      80%                95%                Cluster + warming
Webhook Processing  50/s               1k/s               Async queues
```

### Queue, Cache, and Replica Placement

#### **Caching Strategy**
```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Application   │◄──►│   Redis Cache    │◄──►│   Database      │
│     Cache       │    │    Cluster       │    │   Read Pool     │
├─────────────────┤    ├──────────────────┤    ├─────────────────┤
│• JWT tokens     │    │• Order details   │    │• User queries   │
│• User sessions  │    │• User profiles   │    │• Order history  │
│• Rate limits    │    │• Product info    │    │• Analytics      │
│• 30s TTL        │    │• 5min TTL        │    │• Reports        │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

#### **Message Queue Architecture**
```
┌──────────────┐    ┌─────────────────┐    ┌──────────────────┐
│   Webhook    │───►│  Dead Letter    │    │   Retry Queue    │
│   Primary    │    │     Queue       │◄───│  (Exponential    │
│   Queue      │    │  (Failed after  │    │   Backoff)       │
│              │    │   3 retries)    │    │                  │
└──────────────┘    └─────────────────┘    └──────────────────┘
       │
       ▼
┌──────────────┐    ┌─────────────────┐    ┌──────────────────┐
│  Payment     │───►│  Order Status   │───►│   Notification   │
│ Processing   │    │    Update       │    │     Queue        │
│  Workers     │    │    Workers      │    │   (Email/SMS)    │
│  (5 pods)    │    │   (10 pods)     │    │    (3 pods)      │
└──────────────┘    └─────────────────┘    └──────────────────┘
```

#### **Database Scaling**
```
Write Operations (2k/s)          Read Operations (8k/s)
┌─────────────────┐             ┌─────────────────┐
│   Master DB     │             │  Read Replica 1 │
│  PostgreSQL     │───repl────► │   (Orders)      │
│                 │             └─────────────────┘
│• Order creation │             ┌─────────────────┐
│• Status updates │───repl────► │  Read Replica 2 │  
│• User management│             │  (Analytics)    │
└─────────────────┘             └─────────────────┘
                                ┌─────────────────┐
                          ────► │  Read Replica 3 │
                                │   (Reports)     │
                                └─────────────────┘
```

### Critical Metrics to Monitor

#### **1. Request Latency (P95/P99)**
```
Why: User experience indicator
Alert: P95 > 500ms, P99 > 2s
Action: Scale API servers, check DB performance
```

#### **2. Database Connection Pool Usage**
```
Why: Prevents connection exhaustion
Alert: >80% pool utilization
Action: Scale connection pools, optimize queries
```

#### **3. Cache Hit Rate**
```
Why: Reduces DB load and improves response time
Alert: <90% hit rate
Action: Optimize cache keys, increase TTL, cache warming
```

#### **4. Webhook Processing Queue Depth**
```
Why: Payment processing delays affect user experience
Alert: >1000 messages queued
Action: Scale workers, check payment provider health
```

#### **5. Order Creation Error Rate**
```
Why: Direct revenue impact
Alert: >0.5% error rate
Action: Check DB health, validate payment integrations
```

### Failure Scenario: Database Master Outage

#### **Scenario**
Primary PostgreSQL master crashes during peak traffic (5k req/s)

#### **Impact Without Mitigation**
- All write operations fail (order creation, status updates)
- Read operations continue via replicas
- Payment webhooks queue up, causing delays
- Estimated revenue loss: $50k/hour

#### **Mitigation Strategy**

**Immediate Response (0-5 minutes)**
```bash
# 1. Automatic failover to standby master
kubectl patch postgresql-cluster main --type='json' \
  -p='[{"op": "replace", "path": "/spec/instances", "value": 2}]'

# 2. Circuit breaker activates - API returns cached data
# 3. Queue webhook processing to prevent data loss
# 4. Alert on-call engineer
```

**Short-term Recovery (5-30 minutes)**
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Standby       │───►│   New Master    │◄───│  Read Replicas  │
│   Promoted      │    │   (Replica 1)   │    │  (2-3 remain)   │
│                 │    │                 │    │                 │
│• Write traffic  │    │• Full capacity  │    │• Read traffic   │
│• 95% capacity   │    │• Sync replicas  │    │• Load balanced  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

**Long-term Resilience**
1. **Automated Backup Recovery**: Restore failed master as new replica
2. **Data Consistency Check**: Verify no transactions were lost
3. **Post-mortem Analysis**: Root cause analysis and prevention
4. **Capacity Planning**: Ensure standby can handle 100% load

#### **Prevention Measures**
- **High Availability**: Multi-AZ deployment with automatic failover
- **Health Checks**: Continuous monitoring with 10s intervals  
- **Backup Strategy**: Point-in-time recovery with 5-minute RPO
- **Circuit Breakers**: Graceful degradation when dependencies fail
- **Chaos Engineering**: Monthly disaster recovery drills

#### **Monitoring Dashboard**
```
Database Health Status
┌─────────────────────────────────────────────────────────────┐
│ Master: ●HEALTHY  Replica-1: ●HEALTHY  Replica-2: ●HEALTHY │
│ Connections: 145/200        Replication Lag: 0.2s          │  
│ Disk Usage: 65%             Backup Status: ✓ CURRENT       │
│ Query P95: 45ms             Failover Test: ✓ PASSED        │
└─────────────────────────────────────────────────────────────┘
```

This architecture ensures 99.9% availability and can handle traffic spikes up to 15k req/s with graceful degradation beyond that point.