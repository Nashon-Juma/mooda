#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""DBConnection module for remote MySQL connections."""

import os
import mysql.connector
from mysql.connector import Error, pooling
from dotenv import load_dotenv
import time
import logging
from functools import wraps

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def retry_operation(max_retries=3, delay=2, backoff=2):
    """Decorator to retry database operations with exponential backoff."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except (Error, mysql.connector.errors.InterfaceError) as e:
                    retries += 1
                    if retries == max_retries:
                        logger.error(f"Operation failed after {max_retries} attempts: {e}")
                        raise e
                    
                    wait_time = delay * (backoff ** (retries - 1))
                    logger.warning(f"Attempt {retries} failed. Retrying in {wait_time} seconds: {e}")
                    time.sleep(wait_time)
                    
                    # Try to reconnect if connection is lost
                    if "connection" in str(e).lower() or "interface" in str(e).lower():
                        args[0]._reconnect_pool()
            return None
        return wrapper
    return decorator

class DBConnection:
    """DBConnection Class with connection pooling for remote MySQL connections."""

    _connection_pool = None

    @classmethod
    def initialize_pool(cls):
        """Initialize the connection pool."""
        if cls._connection_pool is None:
            try:
                load_dotenv()
                
                # Get database configuration from environment variables
                db_config = {
                    'database': os.getenv("DATABASE_NAME"),
                    'host': os.getenv("DATABASE_HOSTNAME"),
                    'user': os.getenv("DATABASE_USER"),
                    'password': os.getenv("DATABASE_PASSWORD"),
                    'port': os.getenv("DATABASE_PORT", 3306),
                    'auth_plugin': 'mysql_native_password',
                    'pool_name': 'mooda_pool',
                    'pool_size': 5,  # Adjust based on your free tier limits
                    'pool_reset_session': True,
                    'connect_timeout': 30,  # Increased timeout for remote connections
                    'buffered': True,
                }

                # Remove None values
                db_config = {k: v for k, v in db_config.items() if v is not None}

                cls._connection_pool = pooling.MySQLConnectionPool(**db_config)
                logger.info("✅ MySQL connection pool initialized successfully")
                
            except Error as e:
                logger.error(f"❌ Error initializing connection pool: {e}")
                cls._connection_pool = None

    def __init__(self):
        """Init constructor for DBConnection class."""
        if DBConnection._connection_pool is None:
            DBConnection.initialize_pool()
        
        self.connection = None
        self.cursor = None
        self._get_connection()

    def _get_connection(self):
        """Get a connection from the pool."""
        try:
            if DBConnection._connection_pool:
                self.connection = DBConnection._connection_pool.get_connection()
                if self.connection.is_connected():
                    logger.info("✅ Successfully connected to remote MySQL database")
                return True
        except Error as e:
            logger.error(f"❌ Error getting connection from pool: {e}")
            self.connection = None
        return False

    def _reconnect_pool(self):
        """Reinitialize the connection pool."""
        try:
            if self.connection:
                self.connection.close()
            DBConnection._connection_pool = None
            DBConnection.initialize_pool()
            return self._get_connection()
        except Error as e:
            logger.error(f"❌ Error reconnecting pool: {e}")
            return False

    @retry_operation(max_retries=3, delay=2)
    def execute_query(self, query, params=None):
        """Execute a query that doesn't return results (INSERT, UPDATE, DELETE)."""
        try:
            if not self.connection or not self.connection.is_connected():
                if not self._get_connection():
                    raise Error("Failed to establish database connection")

            cursor = self.connection.cursor()
            cursor.execute(query, params or ())
            self.connection.commit()
            lastrowid = cursor.lastrowid
            cursor.close()
            return lastrowid
            
        except Error as e:
            logger.error(f"❌ Error executing query: {e}")
            logger.error(f"Query: {query}")
            logger.error(f"Params: {params}")
            if self.connection:
                self.connection.rollback()
            raise e

    @retry_operation(max_retries=3, delay=2)
    def fetch_one(self, query, params=None):
        """Fetch a single row from the database."""
        try:
            if not self.connection or not self.connection.is_connected():
                if not self._get_connection():
                    raise Error("Failed to establish database connection")

            cursor = self.connection.cursor(dictionary=True)
            cursor.execute(query, params or ())
            result = cursor.fetchone()
            cursor.close()
            return result
            
        except Error as e:
            logger.error(f"❌ Error fetching data: {e}")
            logger.error(f"Query: {query}")
            logger.error(f"Params: {params}")
            raise e

    @retry_operation(max_retries=3, delay=2)
    def fetch_all(self, query, params=None):
        """Fetch all rows from the database."""
        try:
            if not self.connection or not self.connection.is_connected():
                if not self._get_connection():
                    raise Error("Failed to establish database connection")

            cursor = self.connection.cursor(dictionary=True)
            cursor.execute(query, params or ())
            result = cursor.fetchall()
            cursor.close()
            return result
            
        except Error as e:
            logger.error(f"❌ Error fetching data: {e}")
            logger.error(f"Query: {query}")
            logger.error(f"Params: {params}")
            raise e

    def close(self):
        """Close the database connection and return it to the pool."""
        try:
            if self.cursor:
                self.cursor.close()
            if self.connection:
                self.connection.close()
                logger.info("✅ MySQL connection returned to pool")
        except Error as e:
            logger.error(f"❌ Error closing connection: {e}")

    def is_connected(self):
        """Check if the connection is still active."""
        try:
            if self.connection and self.connection.is_connected():
                # Test the connection with a simple query
                cursor = self.connection.cursor()
                cursor.execute("SELECT 1")
                cursor.close()
                return True
            return False
        except Error:
            return False

    # Context manager support for with statements
    def __enter__(self):
        """Enter the runtime context related to this object."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the runtime context and close the connection."""
        self.close()

    # Backward compatibility methods
    def reconnect(self):
        """Reconnect to the database if connection is lost."""
        if not self.is_connected():
            logger.info("🔁 Reconnecting to database...")
            self.close()
            return self._get_connection()
        return True

    # Static method for quick queries
    @staticmethod
    @retry_operation(max_retries=3, delay=2)
    def execute_quick_query(query, params=None):
        """Execute a quick query without maintaining connection state."""
        try:
            load_dotenv()
            
            connection = mysql.connector.connect(
                database=os.getenv("DATABASE_NAME"),
                host=os.getenv("DATABASE_HOSTNAME"),
                user=os.getenv("DATABASE_USER"),
                password=os.getenv("DATABASE_PASSWORD"),
                port=os.getenv("DATABASE_PORT", 3306),
                auth_plugin="mysql_native_password",
                connect_timeout=30,
            )
            
            with connection.cursor(dictionary=True) as cursor:
                cursor.execute(query, params or ())
                
                if query.strip().upper().startswith('SELECT'):
                    result = cursor.fetchall()
                else:
                    connection.commit()
                    result = cursor.lastrowid
                
            connection.close()
            return result
            
        except Error as e:
            logger.error(f"❌ Error in quick query: {e}")
            raise e

# Global connection pool initialization
DBConnection.initialize_pool()