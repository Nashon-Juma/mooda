#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""login module."""

import bcrypt
import logging
import time
import mysql.connector
from src.utils.db_connection.db_connection import DBConnection

# Set up logging
logger = logging.getLogger(__name__)

class Login:
    """Login."""
    
    def __init__(self):
        """Login constructor."""
        # Don't create connection in init, create per operation
        pass

    def login(self, email, password):
        """Login function."""
        logger.info(f"Starting login for email: {email}")
        start_time = time.time()
        try:
            with DBConnection() as db:
                logger.info("Fetched DB connection")
                query_time = time.time()
                query = "SELECT email FROM User WHERE email=%s"
                result = db.fetch_one(query, (email,))
                logger.info(f"Email query took {time.time() - query_time:.2f} seconds")
                
                if result is not None:
                    logger.info("Email found, validating password")
                    password_start = time.time()
                    if isinstance(password, str):
                        password_bytes = password.encode('utf-8')
                    else:
                        password_bytes = password
                    
                    result = self.validate_password(email, password_bytes)
                    logger.info(f"Password validation took {time.time() - password_start:.2f} seconds")
                    
                    if result.get("matches") is True:
                        logger.info("Login succeeded")
                        return {"login_succeeded": True}
                    else:
                        logger.info("Invalid password")
                        return {"login_succeeded": False, "reason": "Invalid password"}
                else:
                    logger.info("Email not found")
                    return {"login_succeeded": False, "reason": "Email not found"}
                    
        except mysql.connector.Error as e:
            logger.error(f"Database error in login: {e}")
            return {"login_succeeded": False, "reason": f"Database error: {str(e)}"}
        except Exception as e:
            logger.error(f"Unexpected error in login: {e}")
            return {"login_succeeded": False, "reason": f"Unexpected error: {str(e)}"}
        finally:
            logger.info(f"Total login time: {time.time() - start_time:.2f} seconds")

    def validate_password(self, email, password):
        """Validate password function."""
        logger.info(f"Validating password for email: {email}")
        start_time = time.time()
        try:
            with DBConnection() as db:
                query_time = time.time()
                query = "SELECT password FROM User WHERE email=%s LIMIT 1"
                result = db.fetch_one(query, (email,))
                logger.info(f"Password query took {time.time() - query_time:.2f} seconds")
                
                if result is None:
                    logger.info("No user found")
                    return {"hashed_password_found": False, "matches": False}

                hashed_password = result.get("password")
                
                if not hashed_password:
                    logger.info("No hashed password found")
                    return {"hashed_password_found": False, "matches": False}

                # Ensure password is bytes for bcrypt
                if isinstance(password, str):
                    password = password.encode('utf-8')
                
                # Ensure hashed_password is bytes for bcrypt
                if isinstance(hashed_password, str):
                    hashed_password = hashed_password.encode('utf-8')
                
                check_start = time.time()
                matches = bcrypt.checkpw(password, hashed_password)
                logger.info(f"bcrypt.checkpw took {time.time() - check_start:.2f} seconds")
                
                return {"hashed_password_found": True, "matches": matches}
                        
        except mysql.connector.Error as e:
            logger.error(f"Database error in validate_password: {e}")
            return {"hashed_password_found": False, "matches": False}
        except Exception as e:
            logger.error(f"Unexpected error in validate_password: {e}")
            return {"hashed_password_found": False, "matches": False}
        finally:
            logger.info(f"Total validate_password time: {time.time() - start_time:.2f} seconds")