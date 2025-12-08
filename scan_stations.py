import requests
import json  # <--- Thêm thư viện này để ghi file

# --- CẤU HÌNH ---
TOKEN = "6004e823ec662d0cc54399fc75bcec0c146a69cb"

# Tọa độ ĐÔNG NAM Á
LAT_MIN = -11.0
LAT_MAX = 28.5
LNG_MIN = 92.0
LNG_MAX = 141.0

def scan_and_save():
    print(f">>> Đang quét trạm và lưu vào file JSON...")
    url = f"https://api.waqi.info/map/bounds/?latlng={LAT_MIN},{LNG_MIN},{LAT_MAX},{LNG_MAX}&token={TOKEN}"
    
    try:
        resp = requests.get(url).json()
        if resp['status'] != 'ok':
            print("Lỗi API:", resp.get('data'))
            return

        stations = []
        for st in resp['data']:
            uid = st['uid']
            aqi = st['aqi']
            name = st['station']['name']
            lat = st['lat']
            lng = st['lon']

            if str(aqi).isdigit():
                clean_name = name.replace('"', '').replace("'", "").replace("\n", "").strip()
                stations.append({
                    "uid": uid,
                    "name": clean_name,
                    "lat": lat,
                    "lng": lng
                })

        # --- LƯU RA FILE JSON ---
        with open("stations.json", "w", encoding="utf-8") as f:
            json.dump(stations, f, indent=4, ensure_ascii=False)
            
        print(f"✅ Đã lưu {len(stations)} trạm vào file 'stations.json' thành công!")

    except Exception as e:
        print("Lỗi:", e)

if __name__ == "__main__":
    scan_and_save()