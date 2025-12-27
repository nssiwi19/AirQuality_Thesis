"""
Database utilities for AirWatch ASEAN
SQLite database connection and initialization
"""
import sqlite3
import logging
import os
from datetime import datetime

from app.config import DB_NAME


def adapt_datetime(ts): 
    return ts.isoformat()


def convert_datetime(ts): 
    return datetime.fromisoformat(ts.decode())


# Register adapters
sqlite3.register_adapter(datetime, adapt_datetime)
sqlite3.register_converter("DATETIME", convert_datetime)


def get_db_connection(timeout=30):
    """
    Get database connection with timeout and WAL mode to prevent locking.
    WAL mode allows concurrent reads while writing.
    """
    print(f"📁 [DB] Connecting to database: {DB_NAME}")
    print(f"📁 [DB] Current working directory: {os.getcwd()}")
    conn = sqlite3.connect(DB_NAME, timeout=timeout)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")  # 30 seconds
    return conn


def init_db():
    """Initialize AQI database tables"""
    print("🗄️ [DB] Starting database initialization...")
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        print("🗄️ [DB] Creating measurements table...")
        cursor.execute('''CREATE TABLE IF NOT EXISTS measurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            station_uid INTEGER, 
            station_name TEXT,
            aqi INTEGER, 
            pm25 REAL,
            timestamp DATETIME,
            UNIQUE(station_uid, timestamp)
        )''')
        
        # Add station_name column if it doesn't exist (migration for existing DB)
        try:
            cursor.execute("ALTER TABLE measurements ADD COLUMN station_name TEXT")
            print("🗄️ [DB] Added station_name column to existing table")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        print("🗄️ [DB] Creating alerts table...")
        cursor.execute('''CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            station_uid INTEGER,
            alert_type TEXT,
            message TEXT,
            aqi_value INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )''')
        
        conn.commit()
        conn.close()
        print("✅ [DB] Database initialized successfully!")
        logging.info("Database initialized.")
    except Exception as e:
        print(f"❌ [DB] Database initialization FAILED: {e}")
        logging.error(f"DB Init Failed: {e}")
        raise  # Re-raise to make error visible
