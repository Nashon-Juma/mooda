# test_db.py
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.utils.db_connection.db_connection import DBConnection

def test_db_connection():
    """Test the DBConnection class."""
    print("Testing DBConnection class...")
    
    # Test connection
    db = DBConnection()
    if db.is_connected():
        print("✅ Database connection successful!")
    else:
        print("❌ Database connection failed!")
        return False
    
    # Test fetch_one
    result = db.fetch_one("SELECT 1 as test_value")
    print(f"✅ fetch_one test: {result}")
    
    # Test fetch_all
    result = db.fetch_all("SELECT 1 as test_value")
    print(f"✅ fetch_all test: {result}")
    
    # Test execute_query
    result = db.execute_query("SELECT 1")
    print(f"✅ execute_query test: {result}")
    
    # Close connection
    db.close()
    
    print("All DBConnection tests passed! 🎉")
    return True

if __name__ == "__main__":
    test_db_connection()