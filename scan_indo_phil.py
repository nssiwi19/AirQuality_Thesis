"""
Add more virtual stations for Indonesia and Philippines from OpenWeatherMap
These countries have sparse ground station coverage
"""
import requests
import json
import time

OWM_API_KEY = "eda5937f0d0d0c56547e6a213b079db1"

# Extended grid for Indonesia - covering all major islands
INDONESIA_CITIES = [
    # Java (most populated)
    {"name": "Jakarta Utara", "lat": -6.1384, "lng": 106.8633},
    {"name": "Jakarta Selatan", "lat": -6.2615, "lng": 106.8106},
    {"name": "Tangerang", "lat": -6.1783, "lng": 106.6319},
    {"name": "Bekasi", "lat": -6.2349, "lng": 107.0036},
    {"name": "Depok", "lat": -6.4025, "lng": 106.7942},
    {"name": "Bogor", "lat": -6.5971, "lng": 106.8060},
    {"name": "Cirebon", "lat": -6.7320, "lng": 108.5523},
    {"name": "Tasikmalaya", "lat": -7.3274, "lng": 108.2207},
    {"name": "Surakarta", "lat": -7.5755, "lng": 110.8243},
    {"name": "Malang", "lat": -7.9786, "lng": 112.6304},
    {"name": "Kediri", "lat": -7.8161, "lng": 112.0185},
    {"name": "Madiun", "lat": -7.6298, "lng": 111.5230},
    
    # Sumatra
    {"name": "Pekanbaru", "lat": 0.5071, "lng": 101.4478},
    {"name": "Padang", "lat": -0.9471, "lng": 100.4172},
    {"name": "Jambi", "lat": -1.5896, "lng": 103.6134},
    {"name": "Bandar Lampung", "lat": -5.4295, "lng": 105.2610},
    {"name": "Bengkulu", "lat": -3.7928, "lng": 102.2608},
    {"name": "Batam", "lat": 1.0456, "lng": 104.0305},
    
    # Kalimantan
    {"name": "Samarinda", "lat": -0.4948, "lng": 117.1436},
    {"name": "Banjarmasin", "lat": -3.3194, "lng": 114.5908},
    {"name": "Tarakan", "lat": 3.3005, "lng": 117.5893},
    {"name": "Palangkaraya", "lat": -2.2136, "lng": 113.9108},
    
    # Sulawesi
    {"name": "Palu", "lat": -0.9002, "lng": 119.8779},
    {"name": "Kendari", "lat": -3.9985, "lng": 122.5129},
    {"name": "Gorontalo", "lat": 0.5435, "lng": 123.0568},
    
    # Other islands
    {"name": "Ambon", "lat": -3.6954, "lng": 128.1814},
    {"name": "Jayapura", "lat": -2.5337, "lng": 140.7181},
    {"name": "Sorong", "lat": -0.8762, "lng": 131.2870},
    {"name": "Kupang", "lat": -10.1772, "lng": 123.6070},
    {"name": "Mataram", "lat": -8.5833, "lng": 116.1167},
]

# Extended grid for Philippines - covering all major regions
PHILIPPINES_CITIES = [
    # NCR and nearby
    {"name": "Makati", "lat": 14.5547, "lng": 121.0244},
    {"name": "Pasig", "lat": 14.5764, "lng": 121.0851},
    {"name": "Taguig", "lat": 14.5176, "lng": 121.0509},
    {"name": "Caloocan", "lat": 14.6488, "lng": 120.9672},
    {"name": "Pasay", "lat": 14.5378, "lng": 121.0014},
    
    # Luzon
    {"name": "Baguio", "lat": 16.4023, "lng": 120.5960},
    {"name": "Angeles", "lat": 15.1450, "lng": 120.5887},
    {"name": "Olongapo", "lat": 14.8292, "lng": 120.2830},
    {"name": "Batangas", "lat": 13.7565, "lng": 121.0583},
    {"name": "Lipa", "lat": 13.9411, "lng": 121.1622},
    {"name": "Lucena", "lat": 13.9373, "lng": 121.6170},
    {"name": "Naga", "lat": 13.6192, "lng": 123.1814},
    {"name": "Legazpi", "lat": 13.1391, "lng": 123.7438},
    
    # Visayas
    {"name": "Bacolod", "lat": 10.6840, "lng": 122.9563},
    {"name": "Iloilo City", "lat": 10.7202, "lng": 122.5621},
    {"name": "Tacloban", "lat": 11.2543, "lng": 124.9613},
    {"name": "Dumaguete", "lat": 9.3068, "lng": 123.3054},
    {"name": "Tagbilaran", "lat": 9.6500, "lng": 123.8500},
    
    # Mindanao
    {"name": "General Santos", "lat": 6.1164, "lng": 125.1716},
    {"name": "Butuan", "lat": 8.9475, "lng": 125.5406},
    {"name": "Cotabato", "lat": 7.2236, "lng": 124.2464},
    {"name": "Iligan", "lat": 8.2280, "lng": 124.2452},
    {"name": "Dipolog", "lat": 8.5872, "lng": 123.3408},
    {"name": "Surigao", "lat": 9.7572, "lng": 125.4989},
]


def pm25_to_aqi(pm25):
    """Convert PM2.5 to US EPA AQI"""
    breakpoints = [
        (0, 12.0, 0, 50), (12.1, 35.4, 51, 100), (35.5, 55.4, 101, 150),
        (55.5, 150.4, 151, 200), (150.5, 250.4, 201, 300),
        (250.5, 350.4, 301, 400), (350.5, 500.4, 401, 500)
    ]
    for bp_lo, bp_hi, i_lo, i_hi in breakpoints:
        if bp_lo <= pm25 <= bp_hi:
            return round(((i_hi - i_lo) / (bp_hi - bp_lo)) * (pm25 - bp_lo) + i_lo)
    return 500 if pm25 > 500.4 else 0


def fetch_owm(lat, lng):
    """Fetch AQI from OpenWeatherMap"""
    try:
        resp = requests.get("http://api.openweathermap.org/data/2.5/air_pollution", 
                          params={'lat': lat, 'lon': lng, 'appid': OWM_API_KEY}, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('list'):
                pm25 = data['list'][0].get('components', {}).get('pm2_5', 0)
                return pm25_to_aqi(pm25), pm25
    except:
        pass
    return None, None


def scan_extra_stations():
    """Scan additional stations for Indonesia and Philippines"""
    print(">>> Scanning extra stations for Indonesia and Philippines...")
    
    all_stations = []
    
    # Indonesia
    print("\n🇮🇩 Indonesia:")
    for city in INDONESIA_CITIES:
        print(f"  🔍 {city['name']}...", end=" ")
        aqi, pm25 = fetch_owm(city['lat'], city['lng'])
        time.sleep(0.1)
        
        if aqi is not None:
            all_stations.append({
                "uid": f"owm_{city['name'].lower().replace(' ', '_')}",
                "name": f"{city['name']}, Indonesia (OWM Satellite)",
                "lat": city['lat'],
                "lng": city['lng'],
                "country": "Indonesia",
                "source": "openweathermap"
            })
            print(f"✅ AQI={aqi}")
        else:
            print("❌")
    
    # Philippines
    print("\n🇵🇭 Philippines:")
    for city in PHILIPPINES_CITIES:
        print(f"  🔍 {city['name']}...", end=" ")
        aqi, pm25 = fetch_owm(city['lat'], city['lng'])
        time.sleep(0.1)
        
        if aqi is not None:
            all_stations.append({
                "uid": f"owm_{city['name'].lower().replace(' ', '_')}",
                "name": f"{city['name']}, Philippines (OWM Satellite)",
                "lat": city['lat'],
                "lng": city['lng'],
                "country": "Philippines",
                "source": "openweathermap"
            })
            print(f"✅ AQI={aqi}")
        else:
            print("❌")
    
    print(f"\n📊 Found {len(all_stations)} extra stations")
    
    # Merge with main stations
    if all_stations:
        try:
            with open("stations.json", "r", encoding="utf-8") as f:
                stations = json.load(f)
        except:
            stations = []
        
        existing_uids = {s['uid'] for s in stations}
        added = 0
        for st in all_stations:
            if st['uid'] not in existing_uids:
                stations.append(st)
                added += 1
        
        with open("stations.json", "w", encoding="utf-8") as f:
            json.dump(stations, f, indent=4, ensure_ascii=False)
        
        print(f"✅ Added {added} new stations")
        print(f"📊 Total stations now: {len(stations)}")


if __name__ == "__main__":
    scan_extra_stations()
