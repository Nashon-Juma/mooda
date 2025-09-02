#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""db_config module."""

from src.utils.db_connection.db_connection import DBConnection


def db_config():
    """db_config function."""
    conn = DBConnection()
    cursor = conn.connection.cursor()  # Use conn.connection instead of conn.cnx

    try:
        # -------------------- USER TABLE --------------------
        cursor.execute("SHOW TABLES LIKE 'User';")
        user_exists = cursor.fetchone() is not None

        if user_exists:
            print("User table exists!")
        else:
            cursor.execute(
                """
                CREATE TABLE User (
                    user_id INT NOT NULL AUTO_INCREMENT,
                    first_name VARCHAR(255) NOT NULL,
                    last_name VARCHAR(255) NOT NULL,
                    email VARCHAR(255) NOT NULL,
                    password VARCHAR(255) NOT NULL,
                    birth DATE NOT NULL,
                    gender ENUM('male','female') NOT NULL,
                    doctor_key VARCHAR(255) DEFAULT NULL,
                    PRIMARY KEY (user_id),
                    UNIQUE KEY email (email),
                    UNIQUE KEY doctor_key (doctor_key)
                )
                """
            )
            print("✅ User table created successfully!")

        # -------------------- JOURNAL TABLE --------------------
        cursor.execute("SHOW TABLES LIKE 'Journal';")
        journal_exists = cursor.fetchone() is not None

        if journal_exists:
            print("Journal table exists!")
        else:
            cursor.execute(
                """
                CREATE TABLE Journal (
                    journal_id INT NOT NULL AUTO_INCREMENT,
                    user_id INT NOT NULL,
                    journal_title VARCHAR(255) NOT NULL,
                    journal_content TEXT NOT NULL,
                    journal_date DATE NOT NULL,
                    PRIMARY KEY (journal_id),
                    KEY fk_user_id (user_id),
                    CONSTRAINT fk_user_id FOREIGN KEY (user_id)
                        REFERENCES User (user_id) ON DELETE CASCADE
                )
                """
            )
            print("✅ Journal table created successfully!")

        # -------------------- CHECKUP TABLE --------------------
        cursor.execute("SHOW TABLES LIKE 'Checkup';")
        checkup_exists = cursor.fetchone() is not None

        if checkup_exists:
            print("Checkup table exists!")
        else:
            cursor.execute(
                """
                CREATE TABLE Checkup (
                    checkup_id INT NOT NULL AUTO_INCREMENT,
                    checkup_content VARCHAR(255) NOT NULL,
                    PRIMARY KEY (checkup_id)
                )
                """
            )
            print("✅ Checkup table created successfully!")

        # -------------------- CHECKUP_ANSWER TABLE --------------------
        cursor.execute("SHOW TABLES LIKE 'Checkup_answer';")
        checkup_answer_exists = cursor.fetchone() is not None

        if checkup_answer_exists:
            print("Checkup_answer table exists!")
        else:
            cursor.execute(
                """
                CREATE TABLE Checkup_answer (
                    answer_id INT NOT NULL AUTO_INCREMENT,
                    checkup_id INT NOT NULL,
                    user_id INT NOT NULL,
                    answer TINYINT(1) DEFAULT NULL,
                    answer_date DATE DEFAULT NULL,
                    PRIMARY KEY (answer_id),
                    KEY fk_checkup_id (checkup_id),
                    KEY fk_user_id_checkup_answer (user_id),
                    CONSTRAINT fk_checkup_id FOREIGN KEY (checkup_id)
                        REFERENCES Checkup (checkup_id) ON DELETE CASCADE,
                    CONSTRAINT fk_user_id_checkup_answer FOREIGN KEY (user_id)
                        REFERENCES User (user_id) ON DELETE CASCADE
                )
                """
            )
            print("✅ Checkup_answer table created successfully!")
            
        # -------------------- EMOTIONS TABLE --------------------
        cursor.execute("SHOW TABLES LIKE 'emotions';")
        emotions_exists = cursor.fetchone() is not None

        if emotions_exists:
            print("emotions table exists!")
        else:
            cursor.execute(
                """
                CREATE TABLE emotions (
                    id INT NOT NULL AUTO_INCREMENT,
                    user_id INT NOT NULL,
                    input_text TEXT NOT NULL,
                    emotion_data TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (id),
                    KEY fk_user_id_emotions (user_id),
                    CONSTRAINT fk_user_id_emotions FOREIGN KEY (user_id)
                        REFERENCES User (user_id) ON DELETE CASCADE
                )
                """
            )
            print("✅ emotions table created successfully!")
            
        # -------------------- SUBSCRIPTIONS TABLE --------------------
        cursor.execute("SHOW TABLES LIKE 'subscriptions';")
        subscriptions_exists = cursor.fetchone() is not None

        if subscriptions_exists:
            print("subscriptions table exists!")
        else:
            cursor.execute(
                """
                CREATE TABLE subscriptions (
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
                    FOREIGN KEY (user_id) REFERENCES User (user_id)
                )
                """
            )
            print("✅ subscriptions table created successfully!")

        # Commit changes
        conn.connection.commit()
        print("✅ All database tables configured successfully!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        if conn.connection:
            conn.connection.rollback()
        
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


if __name__ == "__main__":
    db_config()