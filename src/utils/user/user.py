"""User integrated Class."""

import time
import secrets
import logging

import mysql.connector

from src.utils.db_connection.db_connection import DBConnection

# Set up logging
logger = logging.getLogger(__name__)

class User:
    """User Class."""

    def __init__(self):
        """Create a User object using the provided data."""

    def get_user_id(self, email=None, doctor_key=None):
        """Fetch user_id from table in the DB."""
        database = DBConnection()

        try:
            if doctor_key is None:
                query = "SELECT user_id FROM User WHERE email = %s"
                result = database.fetch_one(query, (email,))
            elif email is None:
                query = "SELECT user_id FROM User WHERE doctor_key = %s"
                result = database.fetch_one(query, (doctor_key,))
            
            return {"user_id": result["user_id"]} if result else None
        except Exception as e:
            logger.error(f"Error in get_user_id: {e}")
            return None
        finally:
            database.close()

    def get_first_name(self, email):
        """Fetch first_name from table in the DB."""
        database = DBConnection()
        
        try:
            query = "SELECT first_name FROM User WHERE email = %s"
            result = database.fetch_one(query, (email,))
            return {"first_name": result["first_name"]} if result else None
        except Exception as e:
            logger.error(f"Error in get_first_name: {e}")
            return None
        finally:
            database.close()

    def get_last_name(self, email):
        """Fetch last_name from table in the DB."""
        database = DBConnection()
        
        try:
            query = "SELECT last_name FROM User WHERE email = %s"
            result = database.fetch_one(query, (email,))
            return {"last_name": result["last_name"]} if result else None
        except Exception as e:
            logger.error(f"Error in get_last_name: {e}")
            return None
        finally:
            database.close()

    def get_birth(self, email):
        """Fetch age/birth from table in the DB."""
        database = DBConnection()
        
        try:
            query = "SELECT birth FROM User WHERE email = %s"
            result = database.fetch_one(query, (email,))
            return {"birth": result["birth"]} if result else None
        except Exception as e:
            logger.error(f"Error in get_birth: {e}")
            return None
        finally:
            database.close()

    def get_email(self, user_id):
        """Fetch email from table in the DB."""
        database = DBConnection()
        
        try:
            query = "SELECT email FROM User WHERE user_id = %s"
            result = database.fetch_one(query, (user_id,))
            return {"email": result["email"]} if result else None
        except Exception as e:
            logger.error(f"Error in get_email: {e}")
            return None
        finally:
            database.close()

    def get_password(self, email):
        """Fetch password from table in the DB."""
        database = DBConnection()
        
        try:
            query = "SELECT password FROM User WHERE email = %s"
            result = database.fetch_one(query, (email,))
            return {"password": result["password"]} if result else None
        except Exception as e:
            logger.error(f"Error in get_password: {e}")
            return None
        finally:
            database.close()

    def get_gender(self, email):
        """Fetch gender of a user from table in the DB."""
        database = DBConnection()
        
        try:
            query = "SELECT gender FROM User WHERE email = %s"
            result = database.fetch_one(query, (email,))
            return {"gender": result["gender"]} if result else None
        except Exception as e:
            logger.error(f"Error in get_gender: {e}")
            return None
        finally:
            database.close()

    def get_doctor_key(self, user_id):
        """Fetch doctor_key of a user from table in the DB."""
        database = DBConnection()
        
        try:
            query = "SELECT doctor_key FROM User WHERE user_id = %s"
            result = database.fetch_one(query, (user_id,))
            return {"doctor_key": result["doctor_key"]} if result else None
        except Exception as e:
            logger.error(f"Error in get_doctor_key: {e}")
            return None
        finally:
            database.close()

    def update_first_name(self, new_first_name, email):
        """Update the first_name of a user in the DB."""
        database = DBConnection()
        
        try:
            query = "UPDATE User SET first_name = %s WHERE email = %s"
            success = database.execute_query(query, (new_first_name, email)) is not None
            return {"first_name_changed": success}
        except Exception as e:
            logger.error(f"Error in update_first_name: {e}")
            return {"first_name_changed": False}
        finally:
            database.close()

    def update_last_name(self, new_last_name, email):
        """Update the last_name of a user in the DB."""
        database = DBConnection()
        
        try:
            query = "UPDATE User SET last_name = %s WHERE email = %s"
            success = database.execute_query(query, (new_last_name, email)) is not None
            return {"last_name_changed": success}
        except Exception as e:
            logger.error(f"Error in update_last_name: {e}")
            return {"last_name_changed": False}
        finally:
            database.close()

    def update_email(self, new_email, email):
        """Update the email of a user in the DB."""
        database = DBConnection()
        
        try:
            query = "UPDATE User SET email = %s WHERE email = %s"
            success = database.execute_query(query, (new_email, email)) is not None
            return {"email_changed": success}
        except Exception as e:
            logger.error(f"Error in update_email: {e}")
            return {"email_changed": False}
        finally:
            database.close()

    def update_password(self, new_password, email):
        """Update the password of a user in the DB."""
        database = DBConnection()
        
        try:
            query = "UPDATE User SET password = %s WHERE email = %s"
            success = database.execute_query(query, (new_password, email)) is not None
            return {"password_changed": success}
        except Exception as e:
            logger.error(f"Error in update_password: {e}")
            return {"password_changed": False}
        finally:
            database.close()

    def update_doctor_key(self, doctor_key):
        """Update the doctor_key of a user in the DB."""
        database = DBConnection()
        
        try:
            key_length = secrets.choice(range(15, 21))
            key = secrets.token_urlsafe(key_length)
            timestamp = str(int(time.time() * 1000))
            key = f"{key}{timestamp}"

            query = "UPDATE User SET doctor_key = %s WHERE doctor_key = %s"
            success = database.execute_query(query, (key, doctor_key)) is not None
            return {"doctor_key_updated": success}
        except Exception as e:
            logger.error(f"Error in update_doctor_key: {e}")
            return {"doctor_key_updated": False}
        finally:
            database.close()

    def delete_user(self, email):
        """Delete a user from the DB."""
        database = DBConnection()
        
        try:
            query = "DELETE FROM User WHERE email = %s"
            success = database.execute_query(query, (email,)) is not None
            return {"user_deleted": success}
        except Exception as e:
            logger.error(f"Error in delete_user: {e}")
            return {"user_deleted": False}
        finally:
            database.close()