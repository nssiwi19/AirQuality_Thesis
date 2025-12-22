"""
Utility functions for AirWatch ASEAN
IDW interpolation, geo calculations, satellite data
"""
import math
import logging
import requests

from app.config import STATIONS_CONFIG, OPENWEATHER_API_KEY, OPENAQ_API_KEY
from app.db import get_db_connection


def haversine_km(lat1, lng1, lat2, lng2):
    """Calculate distance in km between two points using Haversine formula"""
    R = 6371  # Earth radius in km
    lat1, lng1, lat2, lng2 = map(math.radians, [lat1, lng1, lat2, lng2])
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng/2)**2
    return R * 2 * math.asin(math.sqrt(a))


def get_confidence_level(distance_km):
    """Get confidence level based on distance to nearest station"""
    if distance_km <= 30:
        return {"level": "high", "percent": 95, "message": "Dữ liệu chính xác", "color": "#22c55e"}
    elif distance_km <= 100:
        return {"level": "medium", "percent": 70, "message": "Ước tính gần đúng", "color": "#eab308"}
    elif distance_km <= 200:
        return {"level": "low", "percent": 40, "message": "Ước tính sơ bộ", "color": "#f97316"}
    else:
        return {"level": "very_low", "percent": 20, "message": "Không có trạm gần", "color": "#ef4444"}


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


def fetch_satellite_aqi(lat, lng):
    """
    Fetch AQI from OpenWeatherMap Air Pollution API
    Uses satellite/model data with global coverage
    Free tier: 1000 calls/day
    
    API returns AQI scale 1-5 and component concentrations (PM2.5, PM10, etc.)
    """
    # Try OpenWeatherMap first (better coverage)
    if OPENWEATHER_API_KEY:
        try:
            response = requests.get(
                "http://api.openweathermap.org/data/2.5/air_pollution",
                params={
                    'lat': lat,
                    'lon': lng,
                    'appid': OPENWEATHER_API_KEY
                },
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('list') and len(data['list']) > 0:
                    pollution = data['list'][0]
                    
                    # Get component concentrations
                    components = pollution.get('components', {})
                    pm25 = components.get('pm2_5', 0)
                    pm10 = components.get('pm10', 0)
                    no2 = components.get('no2', 0)
                    o3 = components.get('o3', 0)
                    
                    # Convert PM2.5 to US EPA AQI
                    aqi = pm25_to_aqi(pm25) if pm25 > 0 else 0
                    
                    # OpenWeatherMap's own AQI (1-5 scale)
                    owm_aqi = pollution.get('main', {}).get('aqi', 0)
                    aqi_labels = {1: 'Tốt', 2: 'Khá', 3: 'Trung bình', 4: 'Kém', 5: 'Rất xấu'}
                    
                    return {
                        'aqi': aqi,
                        'source': 'openweathermap_satellite',
                        'pm25': round(pm25, 1),
                        'pm10': round(pm10, 1),
                        'no2': round(no2, 1),
                        'o3': round(o3, 1),
                        'owm_aqi_index': owm_aqi,
                        'owm_aqi_label': aqi_labels.get(owm_aqi, 'N/A'),
                        'data_type': 'satellite_model'
                    }
                    
        except Exception as e:
            logging.error(f"OpenWeatherMap API error: {e}")
    
    # Fallback to OpenAQ if configured
    if OPENAQ_API_KEY:
        try:
            response = requests.get(
                "https://api.openaq.org/v3/locations",
                params={
                    'coordinates': f'{lat},{lng}',
                    'radius': 300000,
                    'limit': 5
                },
                headers={'X-API-Key': OPENAQ_API_KEY},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('results'):
                    for loc in data['results']:
                        sensors = loc.get('sensors', [])
                        for sensor in sensors:
                            if sensor.get('parameter', {}).get('name') == 'pm25':
                                pm25 = sensor.get('latest', {}).get('value')
                                if pm25:
                                    return {
                                        'aqi': pm25_to_aqi(pm25),
                                        'source': 'openaq_satellite',
                                        'pm25': pm25,
                                        'location_name': loc.get('name')
                                    }
        except Exception as e:
            logging.error(f"OpenAQ API error: {e}")
    
    return None


def idw_interpolate(lat, lng, stations_data=None, power=2.0, max_dist_km=500):
    """
    IDW interpolation with confidence indicator
    Returns: {aqi, nearest_station, distance_km, confidence, source}
    """
    # Get current AQI from database
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
    db_aqi = {row[0]: row[1] for row in cursor.fetchall()}
    conn.close()
    
    # Build station data with current AQI
    stations = []
    for st in STATIONS_CONFIG:
        aqi = db_aqi.get(st['uid'])
        if aqi is not None:
            stations.append({
                'uid': st['uid'],
                'name': st.get('name', 'Unknown'),
                'lat': st['lat'],
                'lng': st['lng'],
                'aqi': aqi
            })
    
    if not stations:
        return None
    
    # Find nearest station and calculate IDW
    nearest_station = None
    nearest_dist = float('inf')
    
    num = 0
    den = 0
    has_nearby = False
    
    for st in stations:
        dist = haversine_km(lat, lng, st['lat'], st['lng'])
        
        # Track nearest
        if dist < nearest_dist:
            nearest_dist = dist
            nearest_station = st
        
        # IDW calculation
        if dist > max_dist_km:
            continue
        has_nearby = True
        
        if dist < 1:
            # Very close to station - use exact value
            return {
                'aqi': st['aqi'],
                'nearest_station': st,
                'distance_km': round(dist, 1),
                'confidence': get_confidence_level(dist),
                'source': 'ground_station',
                'interpolated': False
            }
        
        weight = 1 / (dist ** power)
        num += st['aqi'] * weight
        den += weight
    
    if not has_nearby or den == 0:
        # No stations within max_dist - fallback to nearest (with low confidence)
        if nearest_station:
            return {
                'aqi': nearest_station['aqi'],
                'nearest_station': nearest_station,
                'distance_km': round(nearest_dist, 1),
                'confidence': get_confidence_level(nearest_dist),
                'source': 'nearest_station_fallback',
                'interpolated': False,
                'warning': f'Không có trạm trong {max_dist_km}km. Dữ liệu từ trạm gần nhất ({round(nearest_dist)}km).'
            }
        return None
    
    interpolated_aqi = round(num / den)
    
    return {
        'aqi': interpolated_aqi,
        'nearest_station': nearest_station,
        'distance_km': round(nearest_dist, 1),
        'confidence': get_confidence_level(nearest_dist),
        'source': 'idw_interpolation',
        'interpolated': True
    }
