"""
Configuration module for AirWatch ASEAN
"""
import os
import json
import logging
from dotenv import load_dotenv

load_dotenv()

# --- CẤU HÌNH ---
DB_NAME = "air_quality_asean.db"

# WAQI API Token (from environment variable for security)
WAQI_TOKEN = os.getenv("WAQI_TOKEN", "")
if not WAQI_TOKEN:
    logging.warning("⚠️ WAQI_TOKEN not set in environment! AQI data will not load.")

# OpenWeatherMap API config
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")

# OpenAQ API config (satellite fallback)
OPENAQ_API_KEY = os.getenv("OPENAQ_API_KEY", "")
SATELLITE_ENABLED = bool(OPENWEATHER_API_KEY) or bool(OPENAQ_API_KEY)


def load_stations_config():
    """Load danh sách trạm từ stations.json"""
    try:
        with open("stations.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print("❌ Lỗi: Không tìm thấy file stations.json! Hãy chạy scan_map.py trước.")
        return []


# Load stations config once at import
STATIONS_CONFIG = load_stations_config()


def setup_logging():
    """Cấu hình logging"""
    logging.basicConfig(
        level=logging.INFO, 
        format="%(asctime)s [%(levelname)s] %(message)s"
    )
