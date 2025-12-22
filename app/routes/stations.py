"""
Station routes for AirWatch ASEAN
/api/stations, /api/stats, /api/history, /api/heatmap
"""
import sqlite3
from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.config import DB_NAME, STATIONS_CONFIG
from app.db import get_db_connection
from app.predictor import predictor

router = APIRouter()


@router.get("/")
def serve_index():
    return FileResponse("index.html")


@router.get("/api/stations")
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


@router.get("/api/stats")
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


@router.get("/api/history/{uid}")
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


@router.get("/api/heatmap")
def api_heatmap():
    """Dữ liệu cho heatmap layer"""
    conn = get_db_connection()
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
