"""
Crawler module for AirWatch ASEAN
Fetches AQI data from WAQI API
"""
import sqlite3
import time
import logging
import requests
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from app.config import WAQI_TOKEN, STATIONS_CONFIG
from app.db import get_db_connection


def fetch_single_station(station):
    """Fetch AQI data for a single station from WAQI API"""
    try:
        url = f"https://api.waqi.info/feed/@{station['uid']}/?token={WAQI_TOKEN}"
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            raw = resp.json()
            if raw.get('status') == 'ok':
                data = raw.get('data', {})
                aqi = data.get('aqi')
                pm25 = data.get('iaqi', {}).get('pm25', {}).get('v', 0)
                
                if str(aqi).isdigit() and 0 <= int(aqi) <= 999:
                    try:
                        t_str = data.get('time', {}).get('iso')
                        ts = datetime.fromisoformat(t_str).replace(tzinfo=None)
                    except:
                        ts = datetime.now()
                    
                    return {
                        "uid": station['uid'], "name": station['name'],
                        "aqi": int(aqi), "pm25": float(pm25) if float(pm25) >= 0 else 0.0,
                        "timestamp": ts
                    }
    except Exception:
        pass
    return None


def check_spike_alert(uid, current_aqi):
    """Kiểm tra đột biến AQI để tạo cảnh báo"""
    conn = None
    max_retries = 3
    for attempt in range(max_retries):
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT aqi FROM measurements 
                WHERE station_uid=? 
                ORDER BY timestamp DESC LIMIT 3
            """, (uid,))
            rows = cursor.fetchall()
            
            if len(rows) >= 2:
                prev_avg = sum(r[0] for r in rows[1:]) / len(rows[1:])
                # Nếu tăng hơn 30% -> cảnh báo
                if current_aqi > prev_avg * 1.3 and current_aqi > 100:
                    cursor.execute("""
                        INSERT INTO alerts (station_uid, alert_type, message, aqi_value)
                        VALUES (?, 'SPIKE', ?, ?)
                    """, (uid, f"AQI tăng đột biến từ {int(prev_avg)} lên {current_aqi}", current_aqi))
                    conn.commit()
                    logging.warning(f"⚠️ SPIKE ALERT: Station {uid} - AQI {current_aqi}")
            break  # Success, exit retry loop
        except sqlite3.OperationalError as e:
            if "locked" in str(e) and attempt < max_retries - 1:
                time.sleep(0.5 * (attempt + 1))  # Exponential backoff
                continue
            logging.error(f"Spike check error: {e}")
        except Exception as e:
            logging.error(f"Spike check error: {e}")
            break
        finally:
            if conn:
                conn.close()


def crawler_task():
    """Background task to periodically fetch AQI data from all stations"""
    logging.info(">>> Crawler started...")
    while True:
        logging.info(f"Scanning {len(STATIONS_CONFIG)} stations...")
        valid_data_batch = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            results = executor.map(fetch_single_station, STATIONS_CONFIG)
            for res in results:
                if res: valid_data_batch.append(res)

        if valid_data_batch:
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                count = 0
                for item in valid_data_batch:
                    cursor.execute('''
                        INSERT OR IGNORE INTO measurements (station_uid, aqi, pm25, timestamp) 
                        VALUES (?, ?, ?, ?)
                    ''', (item['uid'], item['aqi'], item['pm25'], item['timestamp']))
                    if cursor.rowcount > 0: 
                        count += 1
                        # Kiểm tra spike alert
                        check_spike_alert(item['uid'], item['aqi'])
                conn.commit()
                conn.close()
                logging.info(f"Saved {count} new records.")
            except Exception as e:
                logging.error(f"DB Write Error: {e}")
        
        time.sleep(300)
