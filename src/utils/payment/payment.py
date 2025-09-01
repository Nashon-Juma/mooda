import os
import requests
from datetime import datetime, timedelta

class Payment:
    def __init__(self):
        self.secret_key = os.getenv("PAYSTACK_SECRET_KEY")
        self.public_key = os.getenv("PAYSTACK_PUBLIC_KEY")
        self.base_url = "https://api.paystack.co"
        self.headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json"
        }
    
    def initialize_transaction(self, email, amount, plan_code=None, metadata=None):
        """Initialize a transaction with Paystack"""
        payload = {
            "email": email,
            "amount": int(amount * 100),  # Convert to kobo
            "callback_url": f"{os.getenv('APP_URL', 'http://localhost:5000')}/payment/verify",
            "metadata": metadata or {}
        }
        
        if plan_code:
            payload["plan"] = plan_code
        
        try:
            response = requests.post(
                f"{self.base_url}/transaction/initialize",
                headers=self.headers,
                json=payload
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Paystack API Error: {e}")
            return None
    
    def verify_transaction(self, reference):
        """Verify a transaction with Paystack"""
        try:
            response = requests.get(
                f"{self.base_url}/transaction/verify/{reference}",
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Paystack API Error: {e}")
            return None
    
    def create_plan(self, name, amount, interval="monthly"):
        """Create a subscription plan"""
        payload = {
            "name": name,
            "amount": int(amount * 100),
            "interval": interval,
            "currency": "KSH"  # or "USD", "GHS" depending on your market
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/plan",
                headers=self.headers,
                json=payload
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Paystack API Error: {e}")
            return None
    
    def verify_webhook_signature(self, payload, signature):
        """Verify webhook signature for security"""
        import hashlib
        import hmac
        
        computed_signature = hmac.new(
            self.webhook_secret.encode('utf-8'),
            payload,
            hashlib.sha512
        ).hexdigest()
        
        return hmac.compare_digest(computed_signature, signature)