#!/bin/bash

set -e

echo "🚀 Setting up Order Service..."

mkdir -p data
mkdir -p logs

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip install -r requirements.txt --default-timeout=500 --retries=10

# Generate OpenAPI documentation
echo "📚 Generating API documentation..."
python generate_openapi.py

# Start the services
echo "🔧 Starting services..."
if command -v docker-compose &> /dev/null; then
    docker-compose up -d
elif command -v docker &> /dev/null && docker compose version &> /dev/null; then
    docker compose up -d
else
    echo "⚠️  Docker not found. Starting API server directly..."
    echo "⚠️  Note: You'll need to run Redis and PostgreSQL manually for full functionality"
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
    SERVER_PID=$!
fi

echo " Waiting for services to start..."
sleep 5

echo " Creating demo admin user..."
curl -s -X POST "http://localhost:8000/auth/signup" \
     -H "Content-Type: application/json" \
     -d '{
       "email": "admin@example.com",
       "password": "password123"
     }' > /dev/null && echo " Admin user created" || echo "⚠️  Admin user may already exist"

echo " Creating demo regular user..."
curl -s -X POST "http://localhost:8000/auth/signup" \
     -H "Content-Type: application/json" \
     -d '{
       "email": "user@example.com",
       "password": "password123"
     }' > /dev/null && echo " Regular user created" || echo "⚠️  Regular user may already exist"


# Display setup information
echo ""
echo " Setup complete!"
echo ""
echo " Service Information:"
echo "  • API Server: http://localhost:8000"
echo "  • Admin UI: http://localhost/admin"
echo "  • API Docs: http://localhost:8000/docs"
echo "  • Health Check: http://localhost:8000/health"
echo "  • Metrics: http://localhost:8000/metrics"
echo ""
echo " Demo Accounts:"
echo "  • Admin: admin@example.com / password123"
echo "  • User: user@example.com / password123"
echo ""
echo "  Useful Commands:"
echo "  • Run tests: pytest -v"
echo "  • Simulate payment: python payment_simulator.py success 1"
echo "  • View logs: docker-compose logs -f api"
echo "  • Stop services: docker-compose down"
echo ""
echo " API Endpoints:"
echo "  POST /auth/signup       - Create user account"
echo "  POST /auth/login        - User login"
echo "  POST /orders            - Create order (rate limited)"
echo "  GET  /orders            - List orders (with pagination/search)"
echo "  GET  /orders/{id}       - Get order details (cached)"
echo "  PATCH /orders/{id}/status - Update order status (admin only)"
echo "  POST /payments/initiate - Initiate payment"
echo "  POST /payments/webhook  - Payment webhook (with retries)"
echo ""

# Make scripts executable
chmod +x payment_simulator.py
chmod +x generate_openapi.py

echo "Ready to use!"