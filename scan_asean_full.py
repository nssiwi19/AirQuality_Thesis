"""
Comprehensive ASEAN stations scanner
Target: ~400 stations across all 10 ASEAN countries
Using OpenWeatherMap API (1000 calls/day limit)
"""
import requests
import json
import time

OWM_API_KEY = "eda5937f0d0d0c56547e6a213b079db1"

# Comprehensive grid for ALL ASEAN countries
ASEAN_GRID = {
    "Vietnam": [
        # Northern
        {"name": "Lao Cai", "lat": 22.4809, "lng": 103.9755},
        {"name": "Dien Bien Phu", "lat": 21.3860, "lng": 103.0230},
        {"name": "Son La", "lat": 21.3268, "lng": 103.9144},
        {"name": "Yen Bai", "lat": 21.7051, "lng": 104.8702},
        {"name": "Thai Nguyen", "lat": 21.5942, "lng": 105.8482},
        {"name": "Lang Son", "lat": 21.8537, "lng": 106.7615},
        {"name": "Quang Ninh", "lat": 21.0064, "lng": 107.2925},
        {"name": "Bac Ninh", "lat": 21.1861, "lng": 106.0763},
        {"name": "Hai Duong", "lat": 20.9373, "lng": 106.3146},
        {"name": "Nam Dinh", "lat": 20.4388, "lng": 106.1621},
        {"name": "Ninh Binh", "lat": 20.2506, "lng": 105.9745},
        {"name": "Thanh Hoa", "lat": 19.8067, "lng": 105.7852},
        # Central
        {"name": "Nghe An", "lat": 18.6700, "lng": 105.6813},
        {"name": "Ha Tinh", "lat": 18.3559, "lng": 105.8877},
        {"name": "Quang Binh", "lat": 17.4690, "lng": 106.5990},
        {"name": "Quang Tri", "lat": 16.7520, "lng": 107.1856},
        {"name": "Thua Thien Hue", "lat": 16.4637, "lng": 107.5909},
        {"name": "Quang Nam", "lat": 15.5394, "lng": 108.0191},
        {"name": "Quang Ngai", "lat": 15.1214, "lng": 108.8044},
        {"name": "Binh Dinh", "lat": 13.7765, "lng": 109.2237},
        {"name": "Phu Yen", "lat": 13.0882, "lng": 109.0929},
        {"name": "Khanh Hoa", "lat": 12.2388, "lng": 109.1968},
        {"name": "Ninh Thuan", "lat": 11.5752, "lng": 108.9829},
        {"name": "Binh Thuan", "lat": 10.9280, "lng": 108.1021},
        # Central Highlands
        {"name": "Kon Tum", "lat": 14.3545, "lng": 108.0007},
        {"name": "Gia Lai", "lat": 13.9833, "lng": 108.0000},
        {"name": "Dak Lak", "lat": 12.6667, "lng": 108.0500},
        {"name": "Dak Nong", "lat": 12.0000, "lng": 107.7000},
        {"name": "Lam Dong", "lat": 11.9404, "lng": 108.4583},
        # Southern
        {"name": "Binh Phuoc", "lat": 11.7512, "lng": 106.7235},
        {"name": "Tay Ninh", "lat": 11.3103, "lng": 106.0983},
        {"name": "Binh Duong", "lat": 11.1671, "lng": 106.6414},
        {"name": "Dong Nai", "lat": 10.9453, "lng": 106.8243},
        {"name": "Ba Ria Vung Tau", "lat": 10.5417, "lng": 107.2428},
        {"name": "Long An", "lat": 10.5361, "lng": 106.4133},
        {"name": "Tien Giang", "lat": 10.3600, "lng": 106.3600},
        {"name": "Ben Tre", "lat": 10.2415, "lng": 106.3759},
        {"name": "Vinh Long", "lat": 10.2537, "lng": 105.9722},
        {"name": "Tra Vinh", "lat": 9.9347, "lng": 106.3455},
        {"name": "Dong Thap", "lat": 10.4933, "lng": 105.6882},
        {"name": "An Giang", "lat": 10.5216, "lng": 105.1259},
        {"name": "Kien Giang", "lat": 10.0125, "lng": 105.0809},
        {"name": "Hau Giang", "lat": 9.7579, "lng": 105.6413},
        {"name": "Soc Trang", "lat": 9.6003, "lng": 105.9800},
        {"name": "Bac Lieu", "lat": 9.2850, "lng": 105.7278},
        {"name": "Ca Mau", "lat": 9.1769, "lng": 105.1500},
    ],
    
    "Thailand": [
        # Northern
        {"name": "Chiang Rai", "lat": 19.9105, "lng": 99.8406},
        {"name": "Mae Hong Son", "lat": 19.2990, "lng": 97.9654},
        {"name": "Nan", "lat": 18.7756, "lng": 100.7730},
        {"name": "Phrae", "lat": 18.1445, "lng": 100.1403},
        {"name": "Lampang", "lat": 18.2888, "lng": 99.4987},
        {"name": "Phitsanulok", "lat": 16.8211, "lng": 100.2659},
        {"name": "Sukhothai", "lat": 17.0072, "lng": 99.8231},
        {"name": "Tak", "lat": 16.8840, "lng": 99.1258},
        {"name": "Uttaradit", "lat": 17.6200, "lng": 100.0993},
        # Northeastern (Isan)
        {"name": "Nakhon Ratchasima", "lat": 14.9799, "lng": 102.0978},
        {"name": "Ubon Ratchathani", "lat": 15.2287, "lng": 104.8564},
        {"name": "Roi Et", "lat": 16.0567, "lng": 103.6528},
        {"name": "Kalasin", "lat": 16.4322, "lng": 103.5061},
        {"name": "Maha Sarakham", "lat": 16.1847, "lng": 103.3009},
        {"name": "Nakhon Phanom", "lat": 17.4107, "lng": 104.7858},
        {"name": "Mukdahan", "lat": 16.5436, "lng": 104.7235},
        {"name": "Amnat Charoen", "lat": 15.8656, "lng": 104.6297},
        {"name": "Yasothon", "lat": 15.7944, "lng": 104.1451},
        {"name": "Sisaket", "lat": 15.1186, "lng": 104.3220},
        {"name": "Buriram", "lat": 14.9931, "lng": 103.1029},
        {"name": "Surin", "lat": 14.8818, "lng": 103.4936},
        {"name": "Chaiyaphum", "lat": 15.8068, "lng": 102.0316},
        {"name": "Loei", "lat": 17.4860, "lng": 101.7223},
        {"name": "Nong Bua Lamphu", "lat": 17.2042, "lng": 102.4260},
        # Central
        {"name": "Nakhon Sawan", "lat": 15.7030, "lng": 100.1371},
        {"name": "Lop Buri", "lat": 14.7995, "lng": 100.6534},
        {"name": "Saraburi", "lat": 14.5289, "lng": 100.9102},
        {"name": "Ang Thong", "lat": 14.5896, "lng": 100.4549},
        {"name": "Sing Buri", "lat": 14.8936, "lng": 100.4014},
        {"name": "Chainat", "lat": 15.1851, "lng": 100.1252},
        {"name": "Uthai Thani", "lat": 15.3835, "lng": 100.0245},
        {"name": "Kamphaeng Phet", "lat": 16.4827, "lng": 99.5220},
        {"name": "Nakhon Pathom", "lat": 13.8196, "lng": 100.0445},
        {"name": "Ratchaburi", "lat": 13.5283, "lng": 99.8134},
        {"name": "Kanchanaburi", "lat": 14.0227, "lng": 99.5328},
        {"name": "Suphan Buri", "lat": 14.4744, "lng": 100.1177},
        {"name": "Prachin Buri", "lat": 14.0509, "lng": 101.3687},
        {"name": "Sa Kaeo", "lat": 13.8130, "lng": 102.0645},
        {"name": "Chachoengsao", "lat": 13.6904, "lng": 101.0779},
        # Southern
        {"name": "Chumphon", "lat": 10.4930, "lng": 99.1800},
        {"name": "Ranong", "lat": 9.9529, "lng": 98.6085},
        {"name": "Surat Thani", "lat": 9.1382, "lng": 99.3211},
        {"name": "Phang Nga", "lat": 8.4509, "lng": 98.5253},
        {"name": "Krabi", "lat": 8.0863, "lng": 98.9063},
        {"name": "Nakhon Si Thammarat", "lat": 8.4324, "lng": 99.9631},
        {"name": "Trang", "lat": 7.5645, "lng": 99.6113},
        {"name": "Phatthalung", "lat": 7.6167, "lng": 100.0833},
        {"name": "Songkhla", "lat": 7.1756, "lng": 100.6142},
        {"name": "Satun", "lat": 6.6238, "lng": 100.0673},
        {"name": "Pattani", "lat": 6.8686, "lng": 101.2501},
        {"name": "Yala", "lat": 6.5400, "lng": 101.2800},
        {"name": "Narathiwat", "lat": 6.4318, "lng": 101.8231},
    ],
    
    "Malaysia": [
        # Peninsular - West Coast
        {"name": "Langkawi", "lat": 6.3500, "lng": 99.8000},
        {"name": "Butterworth", "lat": 5.3991, "lng": 100.3639},
        {"name": "Sungai Petani", "lat": 5.6470, "lng": 100.4882},
        {"name": "Taiping", "lat": 4.8500, "lng": 100.7333},
        {"name": "Teluk Intan", "lat": 4.0259, "lng": 101.0213},
        {"name": "Klang", "lat": 3.0449, "lng": 101.4455},
        {"name": "Shah Alam", "lat": 3.0733, "lng": 101.5185},
        {"name": "Petaling Jaya", "lat": 3.1073, "lng": 101.6067},
        {"name": "Subang Jaya", "lat": 3.0565, "lng": 101.5851},
        {"name": "Kajang", "lat": 2.9927, "lng": 101.7909},
        {"name": "Seremban", "lat": 2.7297, "lng": 101.9381},
        {"name": "Muar", "lat": 2.0442, "lng": 102.5689},
        # Peninsular - East Coast
        {"name": "Kota Bharu", "lat": 6.1254, "lng": 102.2381},
        {"name": "Kuala Terengganu", "lat": 5.3117, "lng": 103.1324},
        {"name": "Kemaman", "lat": 4.2333, "lng": 103.4167},
        {"name": "Kuantan", "lat": 3.8077, "lng": 103.3260},
        {"name": "Pekan", "lat": 3.4833, "lng": 103.4000},
        {"name": "Mersing", "lat": 2.4311, "lng": 103.8406},
        # Sabah
        {"name": "Kota Kinabalu", "lat": 5.9804, "lng": 116.0735},
        {"name": "Sandakan", "lat": 5.8402, "lng": 118.1179},
        {"name": "Tawau", "lat": 4.2498, "lng": 117.8871},
        {"name": "Lahad Datu", "lat": 5.0267, "lng": 118.3400},
        {"name": "Keningau", "lat": 5.3378, "lng": 116.1597},
        {"name": "Beaufort", "lat": 5.3472, "lng": 115.7472},
        # Sarawak
        {"name": "Kuching", "lat": 1.5535, "lng": 110.3593},
        {"name": "Miri", "lat": 4.3995, "lng": 113.9914},
        {"name": "Sibu", "lat": 2.2870, "lng": 111.8308},
        {"name": "Bintulu", "lat": 3.1667, "lng": 113.0333},
        {"name": "Limbang", "lat": 4.7500, "lng": 115.0000},
        {"name": "Sarikei", "lat": 2.1333, "lng": 111.5167},
    ],
    
    "Myanmar": [
        {"name": "Naypyidaw", "lat": 19.7633, "lng": 96.0785},
        {"name": "Yangon", "lat": 16.8661, "lng": 96.1951},
        {"name": "Mandalay", "lat": 21.9588, "lng": 96.0891},
        {"name": "Mawlamyine", "lat": 16.4905, "lng": 97.6256},
        {"name": "Bago", "lat": 17.3352, "lng": 96.4814},
        {"name": "Pathein", "lat": 16.7792, "lng": 94.7319},
        {"name": "Monywa", "lat": 22.1086, "lng": 95.1361},
        {"name": "Meiktila", "lat": 20.8667, "lng": 95.8500},
        {"name": "Myitkyina", "lat": 25.3867, "lng": 97.3958},
        {"name": "Taunggyi", "lat": 20.7833, "lng": 97.0333},
        {"name": "Lashio", "lat": 22.9333, "lng": 97.7500},
        {"name": "Sittwe", "lat": 20.1500, "lng": 92.8833},
        {"name": "Magway", "lat": 20.1500, "lng": 94.9333},
        {"name": "Pyay", "lat": 18.8167, "lng": 95.2167},
        {"name": "Hpa-An", "lat": 16.8900, "lng": 97.6350},
        {"name": "Dawei", "lat": 14.0833, "lng": 98.2000},
        {"name": "Myeik", "lat": 12.4333, "lng": 98.6000},
        {"name": "Kawthoung", "lat": 9.9833, "lng": 98.5500},
    ],
    
    "Cambodia": [
        {"name": "Phnom Penh", "lat": 11.5564, "lng": 104.9282},
        {"name": "Siem Reap", "lat": 13.3671, "lng": 103.8448},
        {"name": "Battambang", "lat": 13.0957, "lng": 103.2022},
        {"name": "Sihanoukville", "lat": 10.6093, "lng": 103.5296},
        {"name": "Kampong Cham", "lat": 11.9925, "lng": 105.4623},
        {"name": "Kampong Thom", "lat": 12.7111, "lng": 104.8883},
        {"name": "Kampong Speu", "lat": 11.4519, "lng": 104.5186},
        {"name": "Takeo", "lat": 10.9908, "lng": 104.7850},
        {"name": "Prey Veng", "lat": 11.4872, "lng": 105.3244},
        {"name": "Svay Rieng", "lat": 11.0883, "lng": 105.7989},
        {"name": "Pursat", "lat": 12.5338, "lng": 103.9192},
        {"name": "Kratie", "lat": 12.4881, "lng": 106.0189},
        {"name": "Stung Treng", "lat": 13.5236, "lng": 105.9683},
        {"name": "Banlung", "lat": 13.7394, "lng": 106.9872},
        {"name": "Mondulkiri", "lat": 12.4500, "lng": 107.1833},
        {"name": "Koh Kong", "lat": 11.6150, "lng": 102.9839},
        {"name": "Kampot", "lat": 10.6104, "lng": 104.1791},
        {"name": "Kep", "lat": 10.4833, "lng": 104.3167},
    ],
    
    "Laos": [
        {"name": "Vientiane", "lat": 17.9757, "lng": 102.6331},
        {"name": "Luang Prabang", "lat": 19.8833, "lng": 102.1333},
        {"name": "Savannakhet", "lat": 16.5573, "lng": 104.7519},
        {"name": "Pakse", "lat": 15.1200, "lng": 105.7833},
        {"name": "Thakhek", "lat": 17.4000, "lng": 104.8000},
        {"name": "Luang Namtha", "lat": 20.9500, "lng": 101.4000},
        {"name": "Phongsali", "lat": 21.6833, "lng": 102.1000},
        {"name": "Sam Neua", "lat": 20.4167, "lng": 104.0500},
        {"name": "Xam Nua", "lat": 20.4167, "lng": 104.0500},
        {"name": "Oudomxay", "lat": 20.6833, "lng": 101.9833},
        {"name": "Sayaboury", "lat": 19.2500, "lng": 101.7167},
        {"name": "Xieng Khouang", "lat": 19.3333, "lng": 103.3667},
        {"name": "Bolikhamxai", "lat": 18.3833, "lng": 103.6500},
        {"name": "Khammouane", "lat": 17.8167, "lng": 105.2333},
        {"name": "Salavan", "lat": 15.7167, "lng": 106.4167},
        {"name": "Sekong", "lat": 15.3500, "lng": 106.7333},
        {"name": "Attapeu", "lat": 14.8000, "lng": 106.8333},
        {"name": "Champasak", "lat": 14.8833, "lng": 105.8833},
    ],
    
    "Brunei": [
        {"name": "Bandar Seri Begawan", "lat": 4.9031, "lng": 114.9398},
        {"name": "Kuala Belait", "lat": 4.5833, "lng": 114.2333},
        {"name": "Seria", "lat": 4.6167, "lng": 114.3167},
        {"name": "Tutong", "lat": 4.8000, "lng": 114.6500},
        {"name": "Bangar", "lat": 4.7167, "lng": 115.0667},
    ],
    
    "Singapore": [
        {"name": "Jurong West", "lat": 1.3404, "lng": 103.7090},
        {"name": "Tampines", "lat": 1.3496, "lng": 103.9568},
        {"name": "Woodlands", "lat": 1.4382, "lng": 103.7891},
        {"name": "Bedok", "lat": 1.3236, "lng": 103.9273},
        {"name": "Changi", "lat": 1.3644, "lng": 103.9915},
        {"name": "Toa Payoh", "lat": 1.3343, "lng": 103.8563},
        {"name": "Ang Mo Kio", "lat": 1.3691, "lng": 103.8454},
        {"name": "Bukit Timah", "lat": 1.3294, "lng": 103.8021},
        {"name": "Sentosa", "lat": 1.2494, "lng": 103.8303},
    ],
}


def pm25_to_aqi(pm25):
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
    try:
        resp = requests.get("http://api.openweathermap.org/data/2.5/air_pollution",
                          params={'lat': lat, 'lon': lng, 'appid': OWM_API_KEY}, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('list'):
                pm25 = data['list'][0].get('components', {}).get('pm2_5', 0)
                return pm25_to_aqi(pm25), pm25
    except:
        pass
    return None, None


def scan_all_asean():
    """Scan comprehensive ASEAN grid"""
    print(">>> Scanning comprehensive ASEAN grid for ~400 stations...")
    print(f"    Total cities to scan: {sum(len(cities) for cities in ASEAN_GRID.values())}")
    
    all_stations = []
    
    for country, cities in ASEAN_GRID.items():
        print(f"\n🌏 {country} ({len(cities)} cities):")
        success = 0
        
        for city in cities:
            aqi, pm25 = fetch_owm(city['lat'], city['lng'])
            time.sleep(0.05)  # Rate limiting
            
            if aqi is not None:
                all_stations.append({
                    "uid": f"owm_{city['name'].lower().replace(' ', '_').replace('-', '_')}",
                    "name": f"{city['name']}, {country} (OWM)",
                    "lat": city['lat'],
                    "lng": city['lng'],
                    "country": country,
                    "source": "openweathermap"
                })
                success += 1
        
        print(f"   ✅ {success}/{len(cities)} cities OK")
    
    print(f"\n📊 Total new stations: {len(all_stations)}")
    
    # Merge with existing stations
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
    
    # Show breakdown
    from collections import Counter
    countries = Counter(s.get('country', '?') for s in stations)
    print("\n🌏 Breakdown by country:")
    for c, n in countries.most_common():
        print(f"   {c}: {n}")


if __name__ == "__main__":
    scan_all_asean()
