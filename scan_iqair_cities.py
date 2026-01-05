"""
Quick scan IQAir for major ASEAN cities only
Saves API calls by targeting specific cities
"""
import requests
import json
import time

IQAIR_API_KEY = "b40d772a-7243-457f-ad6f-62e220841057"
BASE_URL = "http://api.airvisual.com/v2"

# Major cities to scan (city, state, country)
MAJOR_CITIES = [
    # Vietnam
    ("Hanoi", "Hanoi", "Vietnam"),
    ("Ho Chi Minh City", "Ho Chi Minh", "Vietnam"),
    ("Da Nang", "Da Nang", "Vietnam"),
    ("Hai Phong", "Hai Phong", "Vietnam"),
    ("Can Tho", "Can Tho", "Vietnam"),
    ("Nha Trang", "Khanh Hoa", "Vietnam"),
    ("Hue", "Thua Thien-Hue", "Vietnam"),
    
    # Thailand
    ("Bangkok", "Bangkok", "Thailand"),
    ("Chiang Mai", "Chiang Mai", "Thailand"),
    ("Phuket", "Phuket", "Thailand"),
    ("Pattaya", "Chonburi", "Thailand"),
    
    # Indonesia
    ("Jakarta", "Jakarta", "Indonesia"),
    ("Surabaya", "East Java", "Indonesia"),
    ("Bandung", "West Java", "Indonesia"),
    ("Medan", "North Sumatra", "Indonesia"),
    ("Bali", "Bali", "Indonesia"),
    
    # Philippines
    ("Manila", "Metro Manila", "Philippines"),
    ("Cebu City", "Cebu", "Philippines"),
    ("Davao", "Davao del Sur", "Philippines"),
    
    # Malaysia
    ("Kuala Lumpur", "Kuala Lumpur", "Malaysia"),
    ("Penang", "Penang", "Malaysia"),
    ("Johor Bahru", "Johor", "Malaysia"),
    
    # Singapore
    ("Singapore", "Singapore", "Singapore"),
    
    # Myanmar
    ("Yangon", "Yangon", "Myanmar"),
    ("Mandalay", "Mandalay", "Myanmar"),
    
    # Cambodia
    ("Phnom Penh", "Phnom Penh", "Cambodia"),
    ("Siem Reap", "Siem Reap", "Cambodia"),
]


def get_city_data(city, state, country):
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
            else:
                print(f"   ⚠️ {data.get('data', {}).get('message', 'Unknown error')}")
        else:
            print(f"   ❌ HTTP {resp.status_code}")
    except Exception as e:
        print(f"   ❌ Exception: {e}")
    return None


def scan_major_cities():
    """Scan major ASEAN cities"""
    print(">>> Scanning major ASEAN cities from IQAir...")
    all_stations = []
    
    for city, state, country in MAJOR_CITIES:
        print(f"🔍 {city}, {country}...", end=" ")
        
        city_data = get_city_data(city, state, country)
        time.sleep(0.5)  # Rate limiting
        
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
                "uid": f"iqair_{city.lower().replace(' ', '_')}",
                "name": f"{city}, {country} (IQAir)",
                "lat": lat,
                "lng": lng,
                "country": country,
                "source": "iqair"
            }
            all_stations.append(station)
            print(f"✅ AQI={aqi} ({lat:.2f}, {lng:.2f})")
        else:
            print("")
    
    print(f"\n📊 Found {len(all_stations)} cities with data")
    
    # Save to file
    if all_stations:
        with open("iqair_stations.json", "w", encoding="utf-8") as f:
            json.dump(all_stations, f, indent=4, ensure_ascii=False)
        print(f"✅ Saved to iqair_stations.json")
    
    return all_stations


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
    
    # Get existing station names (to avoid duplicates by name)
    existing_names = {st['name'].lower() for st in stations}
    existing_uids = {st['uid'] for st in stations}
    
    # Add new IQAir stations
    added = 0
    for st in iqair_stations:
        # Check if similar station already exists
        city_name = st['name'].split(',')[0].lower()
        already_exists = any(city_name in name for name in existing_names)
        
        if st['uid'] not in existing_uids and not already_exists:
            stations.append(st)
            added += 1
            print(f"   + {st['name']}")
        else:
            print(f"   ~ {st['name']} (already exists)")
    
    # Save updated stations
    with open("stations.json", "w", encoding="utf-8") as f:
        json.dump(stations, f, indent=4, ensure_ascii=False)
    
    print(f"\n✅ Added {added} new IQAir stations")
    print(f"📊 Total stations now: {len(stations)}")


if __name__ == "__main__":
    stations = scan_major_cities()
    if stations:
        print("\n>>> Merging with stations.json...")
        merge_with_main_stations(stations)
