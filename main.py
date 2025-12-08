import sqlite3
import uvicorn
import requests
import time
import logging
import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from threading import Thread
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

# --- IMPORT THUẬT TOÁN ---
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor

# --- CẤU HÌNH ---
DB_NAME = "air_quality_asean.db"
WAQI_TOKEN = "6004e823ec662d0cc54399fc75bcec0c146a69cb"

# --- LOAD DANH SÁCH TRẠM ---
def load_config():
    try:
        with open("stations.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print("❌ Lỗi: Không tìm thấy file stations.json! Hãy chạy scan_map.py trước.")
        return []

STATIONS_CONFIG = load_config()

# Cấu hình logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

app = FastAPI(title="AirWatch ASEAN API", version="2.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# --- DATABASE CONFIG ---
def adapt_datetime(ts): return ts.isoformat()
def convert_datetime(ts): return datetime.fromisoformat(ts.decode())
sqlite3.register_adapter(datetime, adapt_datetime)
sqlite3.register_converter("DATETIME", convert_datetime)

def init_db():
    try:
        conn = sqlite3.connect(DB_NAME)
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

# --- CRAWLER WORKER ---
def fetch_single_station(station):
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
    try:
        conn = sqlite3.connect(DB_NAME)
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
        
        conn.close()
    except Exception as e:
        logging.error(f"Spike check error: {e}")

def crawler_task():
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
                conn = sqlite3.connect(DB_NAME)
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

# --- AI PREDICTION (ENHANCED) ---
class AQIPredictor:
    def __init__(self):
        self.models = {}
    
    def get_trend(self, data):
        """Phân tích xu hướng: rising, falling, stable"""
        if len(data) < 3:
            return "stable"
        recent = data[:3]
        older = data[3:6] if len(data) >= 6 else data[3:]
        
        if not older:
            return "stable"
            
        recent_avg = sum(recent) / len(recent)
        older_avg = sum(older) / len(older)
        
        diff_pct = (recent_avg - older_avg) / older_avg * 100 if older_avg > 0 else 0
        
        if diff_pct > 10:
            return "rising"
        elif diff_pct < -10:
            return "falling"
        return "stable"
    
    def predict_multi(self, uid, hours=[1, 6, 12, 24]):
        """Dự báo đa bước: 1h, 6h, 12h, 24h"""
        try:
            conn = sqlite3.connect(DB_NAME)
            df = pd.read_sql_query(
                f"SELECT timestamp, aqi FROM measurements WHERE station_uid={uid} ORDER BY timestamp DESC LIMIT 168", 
                conn
            )
            conn.close()
            
            if len(df) < 10:
                return {h: "Đang học..." for h in hours}, "stable", 0
            
            # Feature Engineering
            df['ts'] = pd.to_datetime(df['timestamp'])
            df['hour'] = df['ts'].dt.hour
            df['day_of_week'] = df['ts'].dt.dayofweek
            df['is_weekend'] = (df['day_of_week'] >= 5).astype(int)
            
            # Thêm lag features
            df['lag_1'] = df['aqi'].shift(-1)
            df['lag_3'] = df['aqi'].shift(-3)
            df = df.dropna()
            
            if len(df) < 5:
                return {h: "Đang học..." for h in hours}, "stable", 0
            
            X = df[['hour', 'day_of_week', 'is_weekend', 'lag_1', 'lag_3']].values
            y = df['aqi'].values
            
            # Model với Gradient Boosting (tốt hơn Random Forest)
            model = GradientBoostingRegressor(n_estimators=100, max_depth=5, random_state=42)
            model.fit(X, y)
            
            # Tính confidence score
            train_score = model.score(X, y)
            confidence = min(int(train_score * 100), 95)
            
            # Trend analysis
            trend = self.get_trend(y.tolist())
            
            # Dự báo đa bước
            predictions = {}
            current_aqi = y[0]
            for h in hours:
                next_time = datetime.now() + timedelta(hours=h)
                # Estimate future lags based on trend
                trend_factor = 1.05 if trend == "rising" else (0.95 if trend == "falling" else 1.0)
                est_lag1 = current_aqi * (trend_factor ** (h/6))
                est_lag3 = current_aqi * (trend_factor ** (h/3))
                
                next_input = [[
                    next_time.hour, 
                    next_time.weekday(),
                    1 if next_time.weekday() >= 5 else 0,
                    est_lag1,
                    est_lag3
                ]]
                pred = model.predict(next_input)
                predictions[h] = max(0, min(500, int(pred[0])))
            
            return predictions, trend, confidence
            
        except Exception as e:
            logging.error(f"Prediction error: {e}")
            return {h: "N/A" for h in hours}, "stable", 0
    
    def predict(self, uid):
        """Backward compatible: trả về dự báo 1h"""
        preds, _, _ = self.predict_multi(uid, [1])
        return preds.get(1, "N/A")

predictor = AQIPredictor()

# --- API ENDPOINTS ---

@app.get("/")
def serve_index():
    return FileResponse("index.html")

@app.get("/api/stations")
def api_stations():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT m.station_uid, m.aqi, m.pm25, m.timestamp 
        FROM measurements m
        INNER JOIN (
            SELECT station_uid, MAX(timestamp) as max_ts 
            FROM measurements GROUP BY station_uid
        ) latest ON m.station_uid = latest.station_uid AND m.timestamp = latest.max_ts
    """)
    db_data = {row['station_uid']: row for row in cursor.fetchall()}
    conn.close()
    
    res = []
    for st in STATIONS_CONFIG:
        uid = st['uid']
        data = db_data.get(uid)
        
        if data:
            preds, trend, confidence = predictor.predict_multi(uid, [1, 6, 12, 24])
            res.append({
                "uid": uid, "name": st['name'], "lat": st['lat'], "lng": st['lng'],
                "aqi": data['aqi'], "pm25": data['pm25'],
                "last_update": data['timestamp'],
                "prediction": preds.get(1, "N/A"),
                "predictions": preds,
                "trend": trend,
                "confidence": confidence
            })
        else:
            res.append({
                "uid": uid, "name": st['name'], "lat": st['lat'], "lng": st['lng'],
                "aqi": "N/A", "pm25": 0, "last_update": "Đang cập nhật...",
                "prediction": "Chưa có",
                "predictions": {},
                "trend": "stable",
                "confidence": 0
            })
    return res

@app.get("/api/stats")
def api_stats():
    """Thống kê tổng quan"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Lấy AQI mới nhất của mỗi trạm
    cursor.execute("""
        SELECT m.aqi FROM measurements m
        INNER JOIN (
            SELECT station_uid, MAX(timestamp) as max_ts 
            FROM measurements GROUP BY station_uid
        ) latest ON m.station_uid = latest.station_uid AND m.timestamp = latest.max_ts
        WHERE m.aqi IS NOT NULL
    """)
    
    aqis = [row[0] for row in cursor.fetchall() if row[0] is not None]
    
    # Đếm alerts trong 24h qua
    cursor.execute("""
        SELECT COUNT(*) FROM alerts 
        WHERE created_at > datetime('now', '-24 hours')
    """)
    alert_count = cursor.fetchone()[0]
    
    conn.close()
    
    if not aqis:
        return {"total_stations": 0, "avg_aqi": 0, "good": 0, "moderate": 0, "unhealthy": 0, "alerts_24h": 0}
    
    return {
        "total_stations": len(aqis),
        "avg_aqi": round(sum(aqis) / len(aqis), 1),
        "max_aqi": max(aqis),
        "min_aqi": min(aqis),
        "good": len([a for a in aqis if a <= 50]),
        "moderate": len([a for a in aqis if 50 < a <= 100]),
        "unhealthy_sensitive": len([a for a in aqis if 100 < a <= 150]),
        "unhealthy": len([a for a in aqis if 150 < a <= 200]),
        "very_unhealthy": len([a for a in aqis if 200 < a <= 300]),
        "hazardous": len([a for a in aqis if a > 300]),
        "alerts_24h": alert_count
    }

@app.get("/api/history/{uid}")
def api_history(uid: int, limit: int = 24):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        "SELECT aqi, pm25, timestamp FROM measurements WHERE station_uid=? ORDER BY timestamp DESC LIMIT ?", 
        (uid, limit)
    )
    data = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return data[::-1]

@app.get("/api/predictions/{uid}")
def api_predictions(uid: int):
    """Dự báo đa bước cho 1 trạm"""
    preds, trend, confidence = predictor.predict_multi(uid, [1, 6, 12, 24])
    return {
        "uid": uid,
        "predictions": preds,
        "trend": trend,
        "confidence": confidence,
        "generated_at": datetime.now().isoformat()
    }

@app.get("/api/alerts")
def api_alerts(limit: int = 20):
    """Lấy danh sách cảnh báo gần đây"""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT a.*, s.name as station_name
        FROM alerts a
        LEFT JOIN (SELECT uid, name FROM stations) s ON a.station_uid = s.uid
        ORDER BY a.created_at DESC
        LIMIT ?
    """, (limit,))
    
    # Fallback nếu không có bảng stations
    try:
        data = [dict(r) for r in cursor.fetchall()]
    except:
        cursor.execute("""
            SELECT * FROM alerts ORDER BY created_at DESC LIMIT ?
        """, (limit,))
        data = [dict(r) for r in cursor.fetchall()]
        # Add station name from config
        for d in data:
            station = next((s for s in STATIONS_CONFIG if s['uid'] == d['station_uid']), None)
            d['station_name'] = station['name'] if station else f"Station {d['station_uid']}"
    
    conn.close()
    return data

@app.get("/api/trends")
def api_trends():
    """Xu hướng AQI theo giờ (trung bình toàn mạng)"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT strftime('%H', timestamp) as hour, AVG(aqi) as avg_aqi, COUNT(*) as count
        FROM measurements
        WHERE timestamp > datetime('now', '-7 days')
        GROUP BY strftime('%H', timestamp)
        ORDER BY hour
    """)
    
    data = [{"hour": int(row[0]), "avg_aqi": round(row[1], 1), "samples": row[2]} for row in cursor.fetchall()]
    conn.close()
    return data

@app.get("/api/heatmap")
def api_heatmap():
    """Dữ liệu cho heatmap layer"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT m.station_uid, m.aqi
        FROM measurements m
        INNER JOIN (
            SELECT station_uid, MAX(timestamp) as max_ts 
            FROM measurements GROUP BY station_uid
        ) latest ON m.station_uid = latest.station_uid AND m.timestamp = latest.max_ts
        WHERE m.aqi IS NOT NULL
    """)
    
    db_data = {row[0]: row[1] for row in cursor.fetchall()}
    conn.close()
    
    points = []
    for st in STATIONS_CONFIG:
        aqi = db_data.get(st['uid'])
        if aqi is not None:
            # Intensity based on AQI (normalized 0-1)
            intensity = min(aqi / 300, 1.0)
            points.append([st['lat'], st['lng'], intensity])
    
    return points

if __name__ == "__main__":
    init_db()
    Thread(target=crawler_task, daemon=True).start()
    uvicorn.run(app, host="0.0.0.0", port=8000)