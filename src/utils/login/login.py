#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""login module."""

import bcrypt
import logging
from src.utils.db_connection.db_connection import DBConnection

# Set up logging
logger = logging.getLogger(__name__)

class Login:
    """Login."""
    
    def __init__(self):
        """Login constructor."""
        # Don't create connection in init, create per operation
        pass

    def validate_password(self, email, password):
        """Validate password function."""
        try:
            with DBConnection() as db:
                query = "SELECT password FROM User WHERE email=%s LIMIT 1"
                result = db.fetch_one(query, (email,))
                
                if result is None:
                    return {"hashed_password_found": False, "matches": False}

                hashed_password = result.get("password")
                
                if not hashed_password:
                    return {"hashed_password_found": False, "matches": False}

                # Ensure password is bytes for bcrypt
                if isinstance(password, str):
                    password = password.encode('utf-8')
                
                # Ensure hashed_password is bytes for bcrypt
                if isinstance(hashed_password, str):
                    hashed_password = hashed_password.encode('utf-8')
                
                if bcrypt.checkpw(password, hashed_password):
                    return {"hashed_password_found": True, "matches": True}
                else:
                    return {"hashed_password_found": True, "matches": False}
                    
        except Exception as e:
            logger.error(f"Error in validate_password: {e}")
            return {"hashed_password_found": False, "matches": False}

    def login(self, email, password):
        """Login function."""
        try:
            with DBConnection() as db:
                query = "SELECT email FROM User WHERE email=%s"
                result = db.fetch_one(query, (email,))
                
                if result is not None:
                    # Ensure password is encoded if it's a string
                    if isinstance(password, str):
                        password_bytes = password.encode('utf-8')
                    else:
                        password_bytes = password
                    
                    result = self.validate_password(email, password_bytes)
                    
                    if result.get("matches") is True:
                        return {"login_succeeded": True}
                    else:
                        return {"login_succeeded": False, "reason": "Invalid password"}
                else:
                    return {"login_succeeded": False, "reason": "Email not found"}
                    
        except Exception as e:
            logger.error(f"Error in login: {e}")
            return {"login_succeeded": False, "reason": f"Error: {str(e)}"}