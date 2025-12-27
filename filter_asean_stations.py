"""
Filter stations.json to keep only ASEAN countries
ASEAN = Vietnam, Thailand, Indonesia, Philippines, Malaysia, Singapore, 
        Myanmar, Cambodia, Laos, Brunei
"""
import json

# ASEAN country bounding boxes (approximate)
# Format: (lat_min, lat_max, lng_min, lng_max)
ASEAN_BOUNDS = {
    "Vietnam": (8.5, 23.5, 102.0, 110.0),
    "Thailand": (5.5, 20.5, 97.3, 105.7),
    "Indonesia": (-11.0, 6.0, 95.0, 141.0),
    "Philippines": (4.5, 21.5, 116.0, 127.0),
    "Malaysia": (0.8, 7.5, 99.5, 119.5),
    "Singapore": (1.15, 1.48, 103.6, 104.1),
    "Myanmar": (9.5, 28.5, 92.0, 101.2),
    "Cambodia": (10.0, 14.7, 102.3, 107.7),
    "Laos": (13.9, 22.5, 100.0, 107.7),
    "Brunei": (4.0, 5.1, 114.0, 115.5),
}

# Keywords that indicate non-ASEAN countries (to exclude)
NON_ASEAN_KEYWORDS = [
    "China", "Taiwan", "Japan", "Okinawa", "India",
    "Hong Kong", "Macau", "Korea",
    # Chinese provinces/cities
    "Guangdong", "Guangxi", "Yunnan", "Fujian", "Hainan",
    "Shenzhen", "Guangzhou", "Shantou", "Zhuhai", "Dongguan",
    "Foshan", "Zhongshan", "Huizhou", "Jiangmen", "Zhanjiang",
    "Maoming", "Shaoguan", "Meizhou", "Heyuan", "Qingyuan",
    "Zhaoqing", "Jieyang", "Chaozhou", "Shanwei", "Yangjiang",
    "Yunfu", "Nanning", "Guilin", "Liuzhou", "Wuzhou",
    "Beihai", "Qinzhou", "Guigang", "Yulin", "Baise",
    "Hechi", "Laibin", "Chongzuo", "Kunming", "Dali",
    "Lijiang", "Xishuangbanna", "Puer", "Wenshan", "Honghe",
    "Chuxiong", "Qujing", "Zhaotong", "Lincang", "Dehong",
    "Nujiang", "Diqing", "Xiamen", "Fuzhou", "Quanzhou",
    "Zhangzhou", "Longyan", "Ningde", "Sanming", "Nanping",
    "Haikou", "Sanya", "Changsha", "Zhuzhou", "Xiangtan",
    "Hengyang", "Shaoyang", "Yueyang", "Changde", "Zhangjiajie",
    "Yiyang", "Chenzhou", "Yongzhou", "Huaihua", "Loudi",
    "Xiangxi", "Nanchang", "Jiujiang", "Jingdezhen", "Pingxiang",
    "Xinyu", "Yingtan", "Ganzhou", "Ji'an", "Yichun",
    "Fuzhou", "Shangrao", "Wenzhou",
    # Chinese characters patterns
    "市", "省", "区", "县", "镇", "站",
]

def is_in_asean_bounds(lat, lng):
    """Check if coordinates are within any ASEAN country bounds"""
    for country, (lat_min, lat_max, lng_min, lng_max) in ASEAN_BOUNDS.items():
        if lat_min <= lat <= lat_max and lng_min <= lng <= lng_max:
            return True, country
    return False, None

def contains_non_asean_keyword(name):
    """Check if station name contains non-ASEAN keywords"""
    name_lower = name.lower()
    for keyword in NON_ASEAN_KEYWORDS:
        if keyword.lower() in name_lower or keyword in name:
            return True
    return False

def filter_asean_stations():
    # Load current stations
    with open("stations.json", "r", encoding="utf-8") as f:
        stations = json.load(f)
    
    print(f"📊 Total stations before filtering: {len(stations)}")
    
    asean_stations = []
    excluded = []
    
    for st in stations:
        lat, lng, name = st['lat'], st['lng'], st['name']
        
        # Check if in ASEAN bounds
        in_bounds, country = is_in_asean_bounds(lat, lng)
        
        # Check for non-ASEAN keywords
        has_non_asean_keyword = contains_non_asean_keyword(name)
        
        # Include if in bounds AND doesn't have non-ASEAN keywords
        if in_bounds and not has_non_asean_keyword:
            st['country'] = country  # Add country tag
            asean_stations.append(st)
        else:
            excluded.append({
                'name': name,
                'reason': 'non-ASEAN keyword' if has_non_asean_keyword else 'out of bounds'
            })
    
    # Save filtered stations
    with open("stations.json", "w", encoding="utf-8") as f:
        json.dump(asean_stations, f, indent=4, ensure_ascii=False)
    
    # Save excluded list for review
    with open("stations_excluded.json", "w", encoding="utf-8") as f:
        json.dump(excluded, f, indent=4, ensure_ascii=False)
    
    print(f"✅ Filtered to {len(asean_stations)} ASEAN stations")
    print(f"❌ Excluded {len(excluded)} non-ASEAN stations")
    print(f"📁 Excluded list saved to 'stations_excluded.json' for review")
    
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
