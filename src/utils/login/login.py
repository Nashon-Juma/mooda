#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""login module."""

import bcrypt
from src.utils.db_connection.db_connection import DBConnection


class Login:
    """Login."""

    def __init__(self):
        """Login constructor."""
        self.conn = DBConnection()

    def close_cursor(self, cursor):
        """Close cursor function."""
        if cursor:
            cursor.close()

    def validate_password(self, email, password):
        """Validate password function."""
        query = "SELECT * FROM User WHERE email=%s LIMIT 1"
        cursor = self.conn.cnx.cursor()
        cursor.execute(query, (email,))
        row = cursor.fetchone()

        self.close_cursor(cursor)

        if row is None:
            return {"hashed_password_found": False, "matches": False}

        # Make sure we're accessing the correct column index for password
        # Adjust the index (4) based on your actual database schema
        hashed_password = row[4]  # Assuming password is at index 4

        # Handle case where hashed_password might be None
        if not hashed_password:
            return {"hashed_password_found": False, "matches": False}

        # Ensure password is bytes for bcrypt
        if isinstance(password, str):
            password = password.encode('utf-8')
        
        if bcrypt.checkpw(password, hashed_password.encode("utf-8")):
            return {"hashed_password_found": True, "matches": True}
        else:
            return {"hashed_password_found": True, "matches": False}

    def login(self, email, password):
        """Login function."""
        try:
            query = "SELECT email FROM User WHERE email=%s"
            cursor = self.conn.cnx.cursor()
            cursor.execute(query, (email,))
            row = cursor.fetchone()
            self.close_cursor(cursor)

            if row is not None:
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
            return {"login_succeeded": False, "reason": f"Error: {str(e)}"}
        finally:
            # Ensure connection is always closed
            if self.conn and self.conn.cnx:
                self.conn.cnx.close()