#!/usr/bin/env python3
"""
Payment Provider Simulator

This script simulates webhook calls from a payment provider.
Usage:
  python payment_simulator.py success <order_id>
  python payment_simulator.py failed <order_id>
"""

import sys
import json
import hmac
import hashlib
import requests
import uuid

WEBHOOK_URL = "http://localhost:8000/payments/webhook"
WEBHOOK_SECRET = "webhook-secret-change-in-production"

def create_webhook_signature(payload_str: str) -> str:
    """Create HMAC signature for webhook payload"""
    signature = hmac.new(
        WEBHOOK_SECRET.encode(),
        payload_str.encode(),
        hashlib.sha256
    ).hexdigest()
    return f"sha256={signature}"

def send_webhook(payment_id: str, order_id: int, status: str):
    """Send webhook notification to the order service"""
    payload = {
        "payment_id": payment_id,
        "order_id": order_id,
        "status": status.upper()
    }
    
    payload_str = json.dumps(payload)
    signature = create_webhook_signature(payload_str)
    
    headers = {
        "Content-Type": "application/json",
        "X-Signature": signature
    }
    
    print(f"Sending webhook for order {order_id} with status {status.upper()}")
    print(f"Payload: {payload_str}")
    print(f"Signature: {signature}")
    
    try:
        response = requests.post(
            WEBHOOK_URL,
            data=payload_str,
            headers=headers,
            timeout=30
        )
        
        print(f"Response Status: {response.status_code}")
        print(f"Response Body: {response.text}")
        
        if response.status_code == 200:
            print("Webhook sent successfully!")
        else:
            print("Webhook failed!")
            
    except requests.exceptions.RequestException as e:
        print(f"Error sending webhook: {e}")

def main():
    if len(sys.argv) != 3:
        print("Usage: python payment_simulator.py <success|failed> <order_id>")
        print("Example: python payment_simulator.py success 1")
        sys.exit(1)
    
    status = sys.argv[1].lower()
    if status not in ["success", "failed"]:
        print("Status must be either 'success' or 'failed'")
        sys.exit(1)
    
    try:
        order_id = int(sys.argv[2])
    except ValueError:
        print("Order ID must be a valid integer")
        sys.exit(1)
    
    payment_id = f"pay_{uuid.uuid4().hex[:8]}"
    
    send_webhook(payment_id, order_id, status)

if __name__ == "__main__":
    main()