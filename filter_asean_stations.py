"""
Filter stations.json to keep only ASEAN countries
ASEAN = Vietnam, Thailand, Indonesia, Philippines, Malaysia, Singapore, 
        Myanmar, Cambodia, Laos, Brunei
"""
import json

# ASEAN country keywords to detect from station name
ASEAN_COUNTRIES = {
    "Vietnam": ["Vietnam", "Việt Nam", "Viet Nam", "Hanoi", "Ho Chi Minh", "Da Nang"],
    "Thailand": ["Thailand", "Bangkok", "Chiang Mai", "Phuket", "Pattaya", "ไทย"],
    "Indonesia": ["Indonesia", "Jakarta", "Surabaya", "Bandung", "Medan", "Bali"],
    "Philippines": ["Philippines", "Manila", "Cebu", "Davao"],
    "Malaysia": ["Malaysia", "Kuala Lumpur", "Penang", "Johor", "Sabah", "Sarawak", 
                 "Selangor", "Perak", "Pahang", "Terengganu", "Kelantan", "Kedah",
                 "Melaka", "Negeri Sembilan", "Perlis", "Labuan"],
    "Singapore": ["Singapore"],
    "Myanmar": ["Myanmar", "Burma", "Yangon", "Mandalay", "မြန်မာ"],
    "Cambodia": ["Cambodia", "Phnom Penh", "Siem Reap", "កម្ពុជា"],
    "Laos": ["Laos", "Vientiane", "Luang Prabang", "ລາວ"],
    "Brunei": ["Brunei"],
}

# Non-ASEAN keywords (to exclude)
NON_ASEAN_KEYWORDS = [
    # Countries
    "China", "Taiwan", "Japan", "Okinawa", "India", "Hong Kong", "Macau", "Korea",
    # Chinese provinces/cities
    "Guangdong", "Guangxi", "Yunnan", "Fujian", "Hainan", "Hunan", "Jiangxi",
    "Shenzhen", "Guangzhou", "Shantou", "Zhuhai", "Dongguan", "Foshan", "Zhongshan",
    "Huizhou", "Jiangmen", "Zhanjiang", "Maoming", "Shaoguan", "Meizhou", "Heyuan",
    "Qingyuan", "Zhaoqing", "Jieyang", "Chaozhou", "Shanwei", "Yangjiang", "Yunfu",
    "Nanning", "Guilin", "Liuzhou", "Wuzhou", "Beihai", "Qinzhou", "Guigang",
    "Yulin", "Baise", "Hechi", "Laibin", "Chongzuo", "Kunming", "Dali", "Lijiang",
    "Xishuangbanna", "Puer", "Wenshan", "Honghe", "Chuxiong", "Qujing", "Zhaotong",
    "Lincang", "Dehong", "Nujiang", "Diqing", "Baoshan", "Xiamen", "Fuzhou", "Quanzhou",
    "Zhangzhou", "Longyan", "Ningde", "Sanming", "Nanping", "Putian", "Haikou", "Sanya",
    "Changsha", "Zhuzhou", "Xiangtan", "Hengyang", "Shaoyang", "Yueyang", "Changde",
    "Zhangjiajie", "Yiyang", "Chenzhou", "Yongzhou", "Huaihua", "Loudi", "Xiangxi",
    "Nanchang", "Jiujiang", "Jingdezhen", "Pingxiang", "Xinyu", "Yingtan", "Ganzhou",
    "Jian", "Yichun", "Shangrao", "Wenzhou", "Lishui", "Guiyang", "Zunyi", "Panzhihua",
    # Chinese characters
    "市", "省", "区", "县", "镇", "站", "州",
]

def detect_country_from_name(name):
    """Detect ASEAN country from station name"""
    name_lower = name.lower()
    for country, keywords in ASEAN_COUNTRIES.items():
        for kw in keywords:
            if kw.lower() in name_lower or kw in name:
                return country
    return None

def contains_non_asean_keyword(name):
    """Check if station name contains non-ASEAN keywords"""
    name_lower = name.lower()
    for keyword in NON_ASEAN_KEYWORDS:
        if keyword.lower() in name_lower or keyword in name:
            return True
    return False

# ASEAN country bounding boxes (for fallback)
ASEAN_BOUNDS = {
    "Vietnam": (8.5, 23.5, 102.0, 110.0),
    "Thailand": (5.5, 20.5, 97.3, 105.7),
    "Indonesia": (-11.0, 6.0, 95.0, 141.0),
    "Philippines": (4.5, 21.5, 116.0, 127.0),
    "Malaysia_Peninsula": (1.2, 7.5, 99.5, 104.5),
    "Malaysia_Borneo": (0.8, 7.5, 109.5, 119.5),
    "Singapore": (1.15, 1.48, 103.6, 104.1),
    "Myanmar": (9.5, 28.5, 92.0, 101.2),
    "Cambodia": (10.0, 14.7, 102.3, 107.7),
    "Laos": (13.9, 22.5, 100.0, 107.7),
    "Brunei": (4.0, 5.1, 114.0, 115.5),
}

def detect_country_from_coords(lat, lng):
    """Detect ASEAN country from coordinates (fallback)"""
    # Check more specific regions first
    if 1.15 <= lat <= 1.48 and 103.6 <= lng <= 104.1:
        return "Singapore"
    if 4.0 <= lat <= 5.1 and 114.0 <= lng <= 115.5:
        return "Brunei"
    if 1.2 <= lat <= 7.5 and 99.5 <= lng <= 104.5:
        return "Malaysia"
    if 0.8 <= lat <= 7.5 and 109.5 <= lng <= 119.5:
        return "Malaysia"  # Sabah/Sarawak
    if 10.0 <= lat <= 14.7 and 102.3 <= lng <= 107.7:
        return "Cambodia"
    if 13.9 <= lat <= 22.5 and 100.0 <= lng <= 107.7:
        return "Laos"
    if 8.5 <= lat <= 23.5 and 102.0 <= lng <= 110.0:
        return "Vietnam"
    if 5.5 <= lat <= 20.5 and 97.3 <= lng <= 105.7:
        return "Thailand"
    if 9.5 <= lat <= 28.5 and 92.0 <= lng <= 101.2:
        return "Myanmar"
    if 4.5 <= lat <= 21.5 and 116.0 <= lng <= 127.0:
        return "Philippines"
    if -11.0 <= lat <= 6.0 and 95.0 <= lng <= 141.0:
        return "Indonesia"
    return None

def filter_asean_stations():
    # Load current stations from backup or original
    try:
        with open("stations_backup.json", "r", encoding="utf-8") as f:
            stations = json.load(f)
    except:
        with open("stations.json", "r", encoding="utf-8") as f:
            stations = json.load(f)
        # Create backup
        with open("stations_backup.json", "w", encoding="utf-8") as f:
            json.dump(stations, f, indent=4, ensure_ascii=False)
    
    print(f"📊 Total stations before filtering: {len(stations)}")
    
    asean_stations = []
    excluded = []
    
    for st in stations:
        lat, lng, name = st['lat'], st['lng'], st['name']
        
        # First check: Non-ASEAN keywords (exclude immediately)
        if contains_non_asean_keyword(name):
            excluded.append({'name': name, 'reason': 'non-ASEAN keyword'})
            continue
        
        # Second check: Detect country from station name
        country = detect_country_from_name(name)
        
        # Third check: Detect country from coordinates (fallback)
        if not country:
            country = detect_country_from_coords(lat, lng)
        
        if country:
            st['country'] = country
            asean_stations.append(st)
        else:
            excluded.append({'name': name, 'reason': 'out of ASEAN bounds'})
    
    # Save filtered stations
    with open("stations.json", "w", encoding="utf-8") as f:
        json.dump(asean_stations, f, indent=4, ensure_ascii=False)
    
    # Save excluded list for review
    with open("stations_excluded.json", "w", encoding="utf-8") as f:
        json.dump(excluded, f, indent=4, ensure_ascii=False)
    
    print(f"✅ Filtered to {len(asean_stations)} ASEAN stations")
    print(f"❌ Excluded {len(excluded)} non-ASEAN stations")
    
    # Show breakdown by country
    country_counts = {}
    for st in asean_stations:
        c = st.get('country', 'Unknown')
        country_counts[c] = country_counts.get(c, 0) + 1
    
    print("\n🌏 ASEAN stations breakdown:")
    for country, count in sorted(country_counts.items(), key=lambda x: -x[1]):
        print(f"   {country}: {count}")

if __name__ == "__main__":
    filter_asean_stations()

