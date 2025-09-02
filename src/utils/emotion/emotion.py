# src/utils/emotion/emotion.py
from datetime import datetime
import json

class Emotion:
    def __init__(self, db_conn):
        self.db_conn = db_conn
    
    def create_emotion_table(self):
        """Create emotion analysis table if it doesn't exist"""
        query = """
        CREATE TABLE IF NOT EXISTS emotions (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            user_id INTEGER NOT NULL,
            input_text TEXT NOT NULL,
            emotion_data TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        """
        self.db_conn.execute_query(query)
    
    def save_emotion_analysis(self, user_id, input_text, emotion_data):
        """Save emotion analysis to database"""
        query = """
        INSERT INTO emotions (user_id, input_text, emotion_data)
        VALUES (%s, %s, %s)
        """
        params = (user_id, input_text, json.dumps(emotion_data))
        return self.db_conn.execute_query(query, params)
    
    def get_user_emotions(self, user_id, limit=30):
        """Get emotion history for a user"""
        query = """
        SELECT input_text, emotion_data, created_at 
        FROM emotions 
        WHERE user_id = %s 
        ORDER BY created_at DESC 
        LIMIT %s
        """
        params = (user_id, limit)
        return self.db_conn.fetch_all(query, params)