"""
Crawler module for AirWatch ASEAN
Fetches AQI data from WAQI, IQAir, and OpenWeatherMap APIs
"""
import sqlite3
import time
import logging
import requests
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from app.config import WAQI_TOKEN, STATIONS_CONFIG, OPENWEATHER_API_KEY, IQAIR_API_KEY
from app.db import get_db_connection


def pm25_to_aqi(pm25):
    """Convert PM2.5 concentration (μg/m³) to US EPA AQI"""
    breakpoints = [
        (0, 12.0, 0, 50),
        (12.1, 35.4, 51, 100),
        (35.5, 55.4, 101, 150),
        (55.5, 150.4, 151, 200),
        (150.5, 250.4, 201, 300),
        (250.5, 350.4, 301, 400),
        (350.5, 500.4, 401, 500)
    ]
    for bp_lo, bp_hi, i_lo, i_hi in breakpoints:
        if bp_lo <= pm25 <= bp_hi:
            return round(((i_hi - i_lo) / (bp_hi - bp_lo)) * (pm25 - bp_lo) + i_lo)
    return 500 if pm25 > 500.4 else 0


def fetch_waqi_station(station):
    """Fetch AQI data for a WAQI station"""
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


def fetch_owm_station(station):
    """Fetch AQI data for an OpenWeatherMap virtual station"""
    if not OPENWEATHER_API_KEY:
        return None
    try:
        url = "http://api.openweathermap.org/data/2.5/air_pollution"
        resp = requests.get(url, params={
            'lat': station['lat'],
            'lon': station['lng'],
            'appid': OPENWEATHER_API_KEY
        }, timeout=15)
        
        if resp.status_code == 200:
            data = resp.json()
            if data.get('list') and len(data['list']) > 0:
                pollution = data['list'][0]
                components = pollution.get('components', {})
                pm25 = components.get('pm2_5', 0)
                
                aqi = pm25_to_aqi(pm25) if pm25 > 0 else 0
                
                return {
                    "uid": station['uid'], 
                    "name": station['name'],
                    "aqi": aqi, 
                    "pm25": round(pm25, 1),
                    "timestamp": datetime.now()
                }
    except Exception as e:
        logging.debug(f"OWM fetch error for {station['name']}: {e}")
    return None


def fetch_iqair_station(station):
    """Fetch AQI data for an IQAir station"""
    if not IQAIR_API_KEY:
        return None
    try:
        # Parse city/state/country from station name
        # Format: "City, Country (IQAir)" or "City, State, Country"
        parts = station['name'].replace(' (IQAir)', '').split(', ')
        city = parts[0] if len(parts) > 0 else None
        country = parts[-1] if len(parts) > 0 else None
        state = parts[1] if len(parts) > 2 else parts[0]  # Use city as state for simple format
        
        if not city or not country:
            return None
        
        url = "http://api.airvisual.com/v2/city"
        resp = requests.get(url, params={
            'city': city,
            'state': state,
            'country': country,
            'key': IQAIR_API_KEY
        }, timeout=15)
        
        if resp.status_code == 200:
            data = resp.json()
            if data.get('status') == 'success':
                current = data.get('data', {}).get('current', {})
                pollution = current.get('pollution', {})
                aqi = pollution.get('aqius', 0)
                
                return {
                    "uid": station['uid'],
                    "name": station['name'],
                    "aqi": aqi,
                    "pm25": 0,  # IQAir API structure is different
                    "timestamp": datetime.now()
                }
    except Exception as e:
        logging.debug(f"IQAir fetch error for {station['name']}: {e}")
    return None


def fetch_single_station(station):
    """Fetch AQI data for a station based on its source"""
    source = station.get('source', 'waqi')
    
    if source == 'openweathermap':
        return fetch_owm_station(station)
    elif source == 'iqair':
        return fetch_iqair_station(station)
    else:
        # Default: WAQI
        return fetch_waqi_station(station)


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
    
    # Wait 30 seconds before first fetch (allow health check to pass)
    logging.info("⏳ Waiting 30s for app to fully start...")
    time.sleep(30)
    
    # Count stations by source
    waqi_count = len([s for s in STATIONS_CONFIG if s.get('source') not in ['iqair', 'openweathermap']])
    iqair_count = len([s for s in STATIONS_CONFIG if s.get('source') == 'iqair'])
    owm_count = len([s for s in STATIONS_CONFIG if s.get('source') == 'openweathermap'])
    logging.info(f"📊 Stations: WAQI={waqi_count}, IQAir={iqair_count}, OWM={owm_count}")
    
    while True:
        logging.info(f"Scanning {len(STATIONS_CONFIG)} stations...")
        valid_data_batch = []
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            results = executor.map(fetch_single_station, STATIONS_CONFIG)
            for res in results:
                if res: 
                    valid_data_batch.append(res)

        if valid_data_batch:
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                count = 0
                for item in valid_data_batch:
                    cursor.execute('''
                        INSERT OR IGNORE INTO measurements (station_uid, station_name, aqi, pm25, timestamp) 
                        VALUES (?, ?, ?, ?, ?)
                    ''', (item['uid'], item['name'], item['aqi'], item['pm25'], item['timestamp']))
                    if cursor.rowcount > 0: 
                        count += 1
                        # Kiểm tra spike alert
                        check_spike_alert(item['uid'], item['aqi'])
                conn.commit()
                conn.close()
                logging.info(f"Saved {count} new records (from {len(valid_data_batch)} fetched).")
            except Exception as e:
                logging.error(f"DB Write Error: {e}")
        
        time.sleep(300)  # 5 minutes

