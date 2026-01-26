"""
Scan OpenWeatherMap Air Pollution API for ASEAN virtual stations
OWM uses satellite/model data - works anywhere by coordinates
Free tier: 1000 calls/day, 60 calls/min

API: http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={key}
"""
import requests
import json
import time
import os
from dotenv import load_dotenv

load_dotenv()

# Get OpenWeatherMap API key
OWM_API_KEY = os.getenv("OPENWEATHER_API_KEY", "eda5937f0d0d0c56547e6a213b079db1")

# Grid points for ASEAN regions with sparse ground station coverage
# Focus on Indonesia, Philippines, Myanmar, Cambodia, Laos
VIRTUAL_STATIONS_GRID = [
    # Indonesia - Major cities
    {"name": "Jakarta", "lat": -6.2088, "lng": 106.8456, "country": "Indonesia"},
    {"name": "Surabaya", "lat": -7.2575, "lng": 112.7521, "country": "Indonesia"},
    {"name": "Bandung", "lat": -6.9175, "lng": 107.6191, "country": "Indonesia"},
    {"name": "Medan", "lat": 3.5952, "lng": 98.6722, "country": "Indonesia"},
    {"name": "Semarang", "lat": -6.9666, "lng": 110.4196, "country": "Indonesia"},
    {"name": "Makassar", "lat": -5.1477, "lng": 119.4327, "country": "Indonesia"},
    {"name": "Palembang", "lat": -2.9761, "lng": 104.7754, "country": "Indonesia"},
    {"name": "Denpasar", "lat": -8.6705, "lng": 115.2126, "country": "Indonesia"},
    {"name": "Yogyakarta", "lat": -7.7956, "lng": 110.3695, "country": "Indonesia"},
    {"name": "Balikpapan", "lat": -1.2654, "lng": 116.8311, "country": "Indonesia"},
    {"name": "Pontianak", "lat": -0.0263, "lng": 109.3425, "country": "Indonesia"},
    {"name": "Manado", "lat": 1.4748, "lng": 124.8421, "country": "Indonesia"},
    
    # Philippines
    {"name": "Quezon City", "lat": 14.6760, "lng": 121.0437, "country": "Philippines"},
    {"name": "Davao", "lat": 7.1907, "lng": 125.4553, "country": "Philippines"},
    {"name": "Cebu City", "lat": 10.3157, "lng": 123.8854, "country": "Philippines"},
    {"name": "Zamboanga", "lat": 6.9214, "lng": 122.0790, "country": "Philippines"},
    {"name": "Cagayan de Oro", "lat": 8.4542, "lng": 124.6319, "country": "Philippines"},
    {"name": "Iloilo City", "lat": 10.7202, "lng": 122.5621, "country": "Philippines"},
    
    # Myanmar
    {"name": "Yangon", "lat": 16.8661, "lng": 96.1951, "country": "Myanmar"},
    {"name": "Mandalay", "lat": 21.9588, "lng": 96.0891, "country": "Myanmar"},
    {"name": "Naypyidaw", "lat": 19.7633, "lng": 96.0785, "country": "Myanmar"},
    {"name": "Mawlamyine", "lat": 16.4905, "lng": 97.6256, "country": "Myanmar"},
    
    # Cambodia
    {"name": "Phnom Penh", "lat": 11.5564, "lng": 104.9282, "country": "Cambodia"},
    {"name": "Siem Reap", "lat": 13.3671, "lng": 103.8448, "country": "Cambodia"},
    {"name": "Battambang", "lat": 13.0957, "lng": 103.2022, "country": "Cambodia"},
    {"name": "Sihanoukville", "lat": 10.6093, "lng": 103.5296, "country": "Cambodia"},
    
    # Laos
    {"name": "Vientiane", "lat": 17.9757, "lng": 102.6331, "country": "Laos"},
    {"name": "Luang Prabang", "lat": 19.8833, "lng": 102.1333, "country": "Laos"},
    {"name": "Savannakhet", "lat": 16.5573, "lng": 104.7519, "country": "Laos"},
    {"name": "Pakse", "lat": 15.1200, "lng": 105.7833, "country": "Laos"},
    
    # Vietnam - Additional cities
    {"name": "Vinh", "lat": 18.6796, "lng": 105.6813, "country": "Vietnam"},
    {"name": "Quy Nhon", "lat": 13.7830, "lng": 109.2197, "country": "Vietnam"},
    {"name": "Buon Ma Thuot", "lat": 12.6676, "lng": 108.0383, "country": "Vietnam"},
    {"name": "Rach Gia", "lat": 10.0125, "lng": 105.0809, "country": "Vietnam"},
    
    # Thailand - Additional
    {"name": "Khon Kaen", "lat": 16.4322, "lng": 102.8236, "country": "Thailand"},
    {"name": "Udon Thani", "lat": 17.4156, "lng": 102.7872, "country": "Thailand"},
    {"name": "Hat Yai", "lat": 7.0086, "lng": 100.4747, "country": "Thailand"},
]


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


def fetch_owm_pollution(lat, lng):
    """Fetch air pollution data from OpenWeatherMap"""
    if not OWM_API_KEY:
        return None
    
    try:
        url = "http://api.openweathermap.org/data/2.5/air_pollution"
        resp = requests.get(url, params={
            'lat': lat,
            'lon': lng,
            'appid': OWM_API_KEY
        }, timeout=15)
        
        if resp.status_code == 200:
            data = resp.json()
            if data.get('list') and len(data['list']) > 0:
                pollution = data['list'][0]
                components = pollution.get('components', {})
                pm25 = components.get('pm2_5', 0)
                pm10 = components.get('pm10', 0)
                
                # Convert to US EPA AQI
                aqi = pm25_to_aqi(pm25) if pm25 > 0 else 0
                
                return {
                    'aqi': aqi,
                    'pm25': round(pm25, 1),
                    'pm10': round(pm10, 1),
                    'owm_aqi': pollution.get('main', {}).get('aqi', 0)
                }
        else:
            print(f"   ❌ HTTP {resp.status_code}")
    except Exception as e:
        print(f"   ❌ Exception: {e}")
    return None


def scan_owm_virtual_stations():
    """Scan all virtual stations from OpenWeatherMap"""
    if not OWM_API_KEY:
        print("❌ OPENWEATHER_API_KEY not set in .env file!")
        print("   Get your free API key at: https://openweathermap.org/api")
        return []
    
    print(">>> Scanning OpenWeatherMap for virtual stations...")
    all_stations = []
    
    for point in VIRTUAL_STATIONS_GRID:
        name = point['name']
        lat = point['lat']
        lng = point['lng']
        country = point['country']
        
        print(f"🔍 {name}, {country}...", end=" ")
        
        pollution = fetch_owm_pollution(lat, lng)
        time.sleep(0.1)  # Rate limiting (60 calls/min allowed)
        
        if pollution:
            station = {
                "uid": f"owm_{name.lower().replace(' ', '_')}",
                "name": f"{name}, {country} (OWM Satellite)",
                "lat": lat,
                "lng": lng,
                "country": country,
                "source": "openweathermap"
            }
            all_stations.append(station)
            print(f"✅ AQI={pollution['aqi']} (PM2.5={pollution['pm25']})")
        else:
            print("❌ No data")
    
    print(f"\n📊 Found {len(all_stations)} virtual stations")
    
    # Save to file
    if all_stations:
        with open("owm_stations.json", "w", encoding="utf-8") as f:
            json.dump(all_stations, f, indent=4, ensure_ascii=False)
        print(f"✅ Saved to owm_stations.json")
    
    return all_stations


def merge_with_main_stations(owm_stations):
    """Merge OWM stations with main stations.json"""
    if not owm_stations:
        print("⚠️ No OWM stations to merge")
        return
    
    # Load current stations
    try:
        with open("stations.json", "r", encoding="utf-8") as f:
            stations = json.load(f)
    except:
        stations = []
    
    # Get existing station info
    existing_uids = {st['uid'] for st in stations}
    existing_names = {st['name'].split(',')[0].lower() for st in stations}
    
    # Add new OWM stations (avoid duplicates)
    added = 0
    skipped = 0
    for st in owm_stations:
        city_name = st['name'].split(',')[0].lower()
        
        # Check if similar station already exists
        if st['uid'] in existing_uids:
            print(f"   ~ {st['name']} (UID exists)")
            skipped += 1
        elif city_name in existing_names:
            print(f"   ~ {st['name']} (city exists)")
            skipped += 1
        else:
            stations.append(st)
            added += 1
            print(f"   + {st['name']}")
    
    # Save updated stations
    with open("stations.json", "w", encoding="utf-8") as f:
        json.dump(stations, f, indent=4, ensure_ascii=False)
    
    print(f"\n✅ Added {added} new OWM stations (skipped {skipped} duplicates)")
    print(f"📊 Total stations now: {len(stations)}")


if __name__ == "__main__":
    stations = scan_owm_virtual_stations()
    if stations:
        print("\n>>> Merging with stations.json...")
        merge_with_main_stations(stations)
