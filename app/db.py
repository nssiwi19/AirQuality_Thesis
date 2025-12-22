"""
Database utilities for AirWatch ASEAN
SQLite database connection and initialization
"""
import sqlite3
import logging
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
    conn = sqlite3.connect(DB_NAME, timeout=timeout)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")  # 30 seconds
    return conn


def init_db():
    """Initialize AQI database tables"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS measurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            station_uid INTEGER, aqi INTEGER, pm25 REAL,
            timestamp DATETIME,
            UNIQUE(station_uid, timestamp)
        )''')
        # Bảng alerts cho thông báo
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
        logging.info("Database initialized.")
    except Exception as e:
        logging.error(f"DB Init Failed: {e}")
