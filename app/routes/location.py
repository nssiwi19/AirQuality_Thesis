"""
Location routes for AirWatch ASEAN
/api/location-aqi, /api/weather
"""
import logging
import requests
from datetime import datetime
from fastapi import APIRouter, HTTPException

from app.config import OPENWEATHER_API_KEY, SATELLITE_ENABLED, STATIONS_CONFIG
from app.utils import idw_interpolate, fetch_satellite_aqi

router = APIRouter()


@router.get("/api/weather")
def api_weather(lat: float, lng: float):
    """
    Lấy thông tin thời tiết từ OpenWeatherMap
    Returns: temperature (°C), humidity (%), description
    """
    if not OPENWEATHER_API_KEY:
        return {"error": "OpenWeather API key not configured", "temp": None, "humidity": None}
    
    try:
        response = requests.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={
                'lat': lat,
                'lon': lng,
                'appid': OPENWEATHER_API_KEY,
                'units': 'metric',  # Celsius
                'lang': 'vi'  # Vietnamese
            },
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            return {
                "temp": round(data['main']['temp'], 1),
                "humidity": data['main']['humidity'],
                "feels_like": round(data['main']['feels_like'], 1),
                "description": data['weather'][0]['description'] if data.get('weather') else "",
                "icon": data['weather'][0]['icon'] if data.get('weather') else "",
                "wind_speed": data.get('wind', {}).get('speed', 0),
                "location": data.get('name', ''),
                "timestamp": datetime.now().isoformat()
            }
        else:
            logging.warning(f"Weather API error: {response.status_code}")
            return {"error": f"API error: {response.status_code}", "temp": None, "humidity": None}
            
    except Exception as e:
        logging.error(f"Weather fetch error: {e}")
        return {"error": str(e), "temp": None, "humidity": None}


@router.get("/api/location-aqi")
def api_location_aqi(lat: float, lng: float):
    """
    Get AQI for any location using:
    1. IDW interpolation from ground stations (if nearby)
    2. Satellite data fallback (if no ground stations nearby and API key configured)
    
    Returns AQI with confidence indicator based on data source and distance
    """
    # Try IDW interpolation first
    result = idw_interpolate(lat, lng, STATIONS_CONFIG)
    
    if result:
        # If confidence is very low and satellite is enabled, try satellite data
        if result['confidence']['level'] == 'very_low' and SATELLITE_ENABLED:
            satellite_data = fetch_satellite_aqi(lat, lng)
            if satellite_data:
                result['satellite_data'] = satellite_data
                result['hybrid_source'] = True
        return result
    
    # No ground stations at all - try satellite only
    if SATELLITE_ENABLED:
        satellite_data = fetch_satellite_aqi(lat, lng)
        if satellite_data:
            return {
                'aqi': satellite_data['aqi'],
                'source': 'satellite',
                'confidence': {
                    'level': 'satellite',
                    'percent': 60,
                    'message': 'Dữ liệu vệ tinh',
                    'color': '#8b5cf6'
                },
                'satellite_data': satellite_data
            }
    
    raise HTTPException(
        status_code=404,
        detail="Không có dữ liệu AQI cho vị trí này"
    )
