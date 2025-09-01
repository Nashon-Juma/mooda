# src/utils/subscription/subscription.py
from datetime import datetime, timedelta
from src.utils.db_connection.db_connection import DBConnection

class Subscription:
    def __init__(self, db_conn: DBConnection):
        """Initialize Subscription with a database connection."""
        self.db_conn = db_conn
    
    def create_subscription_table(self):
        """Create subscription table if it doesn't exist"""
        query = """
        CREATE TABLE IF NOT EXISTS subscriptions (
            id INT PRIMARY KEY AUTO_INCREMENT,
            user_id INT NOT NULL,
            plan_name VARCHAR(255) NOT NULL,
            amount DECIMAL(10,2) NOT NULL,
            status VARCHAR(50) DEFAULT 'active',
            start_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            end_date TIMESTAMP NULL,
            paystack_reference VARCHAR(255) UNIQUE,
            paystack_customer_code VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
        """
        try:
            result = self.db_conn.execute_query(query)
            print("✅ Subscription table created or already exists")
            return result
        except Exception as e:
            print(f"❌ Error creating subscription table: {e}")
            return None
    
    def update_subscription_status(self, reference, status):
        """Update subscription status"""
        query = "UPDATE subscriptions SET status = %s WHERE paystack_reference = %s"
        params = (status, reference)
        return self.db_conn.execute_query(query, params)
    
    def get_user_subscription(self, user_id):
        """Get user's current subscription"""
        # Ensure database connection is active
        if not self.db_conn.is_connected():
            self.db_conn.reconnect()
        
        query = """
        SELECT * FROM subscriptions 
        WHERE user_id = %s AND status = 'active' AND end_date > NOW()
        ORDER BY created_at DESC LIMIT 1
        """
        params = (user_id,)
        try:
            return self.db_conn.fetch_one(query, params)
        except Exception as e:
            print(f"❌ Error fetching subscription: {e}")
            return None
    
    def is_premium_user(self, user_id):
        """Check if user has an active premium subscription"""
        try:
            # Ensure database connection is active
            if not self.db_conn.is_connected():
                self.db_conn.reconnect()
                
            subscription = self.get_user_subscription(user_id)
            return subscription is not None
        except Exception as e:
            print(f"❌ Error checking premium status: {e}")
            return False
    
