"""
Scan IQAir API for ASEAN stations
IQAir provides real ground station data with good coverage in ASEAN
Free tier: ~10,000 calls/month

API Endpoints used:
- GET /v2/countries - List all countries
- GET /v2/states?country={country} - List states/provinces
- GET /v2/cities?state={state}&country={country} - List cities
- GET /v2/city?city={city}&state={state}&country={country} - Get city AQI data
"""
import requests
import json
import os
import time
from dotenv import load_dotenv

load_dotenv()

# Get IQAir API key from environment or use directly
IQAIR_API_KEY = os.getenv("IQAIR_API_KEY", "b40d772a-7243-457f-ad6f-62e220841057")
BASE_URL = "http://api.airvisual.com/v2"

# ASEAN countries supported by IQAir
ASEAN_COUNTRIES = [
    "Vietnam",
    "Thailand", 
    "Indonesia",
    "Philippines",
    "Malaysia",
    "Singapore",
    "Myanmar",
    "Cambodia",
    # "Laos",  # May not be available
    # "Brunei",  # May not be available
]


def get_states(country):
    """Get all states/provinces for a country"""
    try:
        url = f"{BASE_URL}/states"
        resp = requests.get(url, params={
            'country': country,
            'key': IQAIR_API_KEY
        }, timeout=15)
        
        if resp.status_code == 200:
            data = resp.json()
            if data.get('status') == 'success':
                states = [s['state'] for s in data.get('data', [])]
                return states
        else:
            print(f"  ⚠️ Error getting states for {country}: {resp.status_code}")
    except Exception as e:
        print(f"  ❌ Exception: {e}")
    return []


def get_cities(country, state):
    """Get all cities for a state"""
    try:
        url = f"{BASE_URL}/cities"
        resp = requests.get(url, params={
            'state': state,
            'country': country,
            'key': IQAIR_API_KEY
        }, timeout=15)
        
        if resp.status_code == 200:
            data = resp.json()
            if data.get('status') == 'success':
                cities = [c['city'] for c in data.get('data', [])]
                return cities
    except Exception as e:
        print(f"  ❌ Exception getting cities: {e}")
    return []


def get_city_data(country, state, city):
    """Get AQI data for a specific city"""
    try:
        url = f"{BASE_URL}/city"
        resp = requests.get(url, params={
            'city': city,
            'state': state,
            'country': country,
            'key': IQAIR_API_KEY
        }, timeout=15)
        
        if resp.status_code == 200:
            data = resp.json()
            if data.get('status') == 'success':
                return data.get('data')
    except Exception as e:
        print(f"  ❌ Exception getting city data: {e}")
    return None


def scan_iqair_asean():
    """Scan all ASEAN countries for available stations"""
    if not IQAIR_API_KEY:
        print("❌ IQAIR_API_KEY not set in .env file!")
        print("   Get your free API key at: https://www.iqair.com/dashboard/api")
        return []
    
    print(">>> Scanning IQAir API for ASEAN stations...")
    all_stations = []
    api_calls = 0
    
    for country in ASEAN_COUNTRIES:
        print(f"\n🌏 {country}:")
        states = get_states(country)
        api_calls += 1
        
        if not states:
            print(f"   No states found")
            continue
        
        print(f"   Found {len(states)} states/provinces")
        
        for state in states:
            cities = get_cities(country, state)
            api_calls += 1
            time.sleep(0.2)  # Rate limiting
            
            for city in cities:
                city_data = get_city_data(country, state, city)
                api_calls += 1
                time.sleep(0.2)  # Rate limiting
                
                if city_data:
                    location = city_data.get('location', {})
                    coords = location.get('coordinates', [0, 0])
                    
                    # IQAir returns [lng, lat] format
                    lng = coords[0] if len(coords) > 0 else 0
                    lat = coords[1] if len(coords) > 1 else 0
                    
                    current = city_data.get('current', {})
                    pollution = current.get('pollution', {})
                    aqi = pollution.get('aqius', 0)
                    
                    station = {
                        "uid": f"iqair_{city.lower().replace(' ', '_')}_{state.lower().replace(' ', '_')}",
                        "name": f"{city}, {state}, {country}",
                        "lat": lat,
                        "lng": lng,
                        "country": country,
                        "source": "iqair",
                        "current_aqi": aqi
                    }
                    all_stations.append(station)
                    print(f"   ✅ {city}: AQI {aqi} ({lat:.2f}, {lng:.2f})")
                
                # Stop if too many API calls
                if api_calls > 200:
                    print(f"\n⚠️ Reached {api_calls} API calls, stopping to save quota...")
                    break
            
            if api_calls > 200:
                break
        
        if api_calls > 200:
            break
    
    print(f"\n📊 Summary:")
    print(f"   Total API calls: {api_calls}")
    print(f"   Total stations found: {len(all_stations)}")
    
    # Save to file
    if all_stations:
        with open("iqair_stations.json", "w", encoding="utf-8") as f:
            json.dump(all_stations, f, indent=4, ensure_ascii=False)
        print(f"   Saved to iqair_stations.json")
    
    return all_stations


def scan_iqair_quick():
    """Quick scan - only get cities (no AQI data) to save API calls"""
    if not IQAIR_API_KEY:
        print("❌ IQAIR_API_KEY not set!")
        return []
    
    print(">>> Quick scan IQAir (cities only, no AQI data)...")
    all_cities = []
    
    for country in ASEAN_COUNTRIES:
        print(f"\n🌏 {country}:")
        states = get_states(country)
        time.sleep(0.2)
        
        if not states:
            continue
        
        country_cities = []
        for state in states[:5]:  # Limit to first 5 states per country
            cities = get_cities(country, state)
            time.sleep(0.2)
            
            for city in cities:
                country_cities.append({
                    "city": city,
                    "state": state,
                    "country": country
                })
        
        all_cities.extend(country_cities)
        print(f"   Found {len(country_cities)} cities")
    
    # Save city list
    with open("iqair_cities.json", "w", encoding="utf-8") as f:
        json.dump(all_cities, f, indent=4, ensure_ascii=False)
    
    print(f"\n✅ Total {len(all_cities)} cities saved to iqair_cities.json")
    return all_cities


def merge_with_main_stations(iqair_stations):
    """Merge IQAir stations with main stations.json"""
    if not iqair_stations:
        print("⚠️ No IQAir stations to merge")
        return
    
    # Load current stations
    try:
        with open("stations.json", "r", encoding="utf-8") as f:
            stations = json.load(f)
    except:
        stations = []
    
    # Get existing UIDs
    existing_uids = {st['uid'] for st in stations}
    
    # Add new IQAir stations (without current_aqi field)
    added = 0
    for st in iqair_stations:
        if st['uid'] not in existing_uids:
            # Remove current_aqi as it's temporary
            station_to_add = {
                "uid": st['uid'],
                "name": st['name'],
                "lat": st['lat'],
                "lng": st['lng'],
                "country": st['country'],
                "source": "iqair"
            }
            stations.append(station_to_add)
            added += 1
    
    # Save updated stations
    with open("stations.json", "w", encoding="utf-8") as f:
        json.dump(stations, f, indent=4, ensure_ascii=False)
    
    print(f"✅ Added {added} IQAir stations to stations.json")
    print(f"📊 Total stations now: {len(stations)}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--quick":
        # Quick scan - only list cities, no AQI data
        scan_iqair_quick()
    elif len(sys.argv) > 1 and sys.argv[1] == "--merge":
        # Full scan and auto merge
        stations = scan_iqair_asean()
        if stations:
            merge_with_main_stations(stations)
    else:
        # Full scan with AQI data, auto merge
        stations = scan_iqair_asean()
        if stations:
            merge_with_main_stations(stations)

