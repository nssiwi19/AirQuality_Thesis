"""
Prediction routes for AirWatch ASEAN
/api/predictions, /api/alerts, /api/trends
"""
import sqlite3
from datetime import datetime
from fastapi import APIRouter

from app.config import DB_NAME, STATIONS_CONFIG
from app.predictor import predictor

router = APIRouter()


@router.get("/api/predictions/{uid}")
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


@router.get("/api/alerts")
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


@router.get("/api/trends")
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
