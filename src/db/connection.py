import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import os

load_dotenv()


class DatabaseConnection:
    def __init__(self):
        self.connection = None

    def connect(self):
        try:
            self.connection = psycopg2.connect(
                host=os.getenv("DB_HOST"),
                port=os.getenv("DB_PORT"),
                database=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                cursor_factory=RealDictCursor
            )

            print("✅ Connected to PostgreSQL successfully.")
            return self.connection

        except Exception as e:
            print(f"❌ Connection failed: {e}")

    def get_connection(self):
        return self.connection

    def close(self):
        if self.connection:
            self.connection.close()
            print("Database connection closed.")