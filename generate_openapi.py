#!/usr/bin/env python3
"""
Generate OpenAPI documentation for the Order Service
"""

import json
from main import app

def generate_openapi_spec():
    """Generate and save OpenAPI specification"""
    openapi_schema = app.openapi()
    
    # Add additional metadata
    openapi_schema["info"].update({
        "title": "Order Service API",
        "description": """
        A comprehensive order management service with:
        - User authentication with JWT
        - Role-based access control (RBAC)
        - Idempotent order creation
        - Optimistic locking for concurrency safety
        - Payment webhook integration
        - Caching and rate limiting
        """,
        "version": "1.0.0",
        "contact": {
            "name": "Order Service Team",
            "email": "api@orderservice.com"
        }
    })
    
    # Add server information
    openapi_schema["servers"] = [
        {
            "url": "http://localhost:8000",
            "description": "Development server"
        },
        {
            "url": "http://api.orderservice.com",
            "description": "Production server"
        }
    ]
    
    # Add security schemes
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT"
        }
    }
    
    # Add tags for organization
    openapi_schema["tags"] = [
        {
            "name": "Authentication",
            "description": "User signup and login operations"
        },
        {
            "name": "Orders",
            "description": "Order management operations"
        },
        {
            "name": "Payments",
            "description": "Payment processing operations"
        },
        {
            "name": "System",
            "description": "Health checks and metrics"
        }
    ]
    
    # Save to file
    with open("openapi.json", "w") as f:
        json.dump(openapi_schema, f, indent=2)
    
    print("OpenAPI specification generated: openapi.json")
    print("View documentation at: http://localhost:8000/docs")

if __name__ == "__main__":
    generate_openapi_spec()