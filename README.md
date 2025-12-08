# AirWatch ASEAN - Hệ Thống Giám Sát Chất Lượng Không Khí

🌬️ Hệ thống giám sát và dự báo chất lượng không khí thời gian thực khu vực ASEAN.

## 🚀 Tính Năng

- 📊 **Real-time AQI** - Dữ liệu từ 400+ trạm WAQI
- 🤖 **AI Prediction** - Dự báo 1h/6h/12h/24h với Gradient Boosting
- 🗺️ **IDW Map** - Bản đồ phủ màu chất lượng không khí
- ⚠️ **Alert System** - Cảnh báo đột biến AQI
- 🌓 **Dark/Light Theme** - Giao diện hiện đại
- 📱 **PWA** - Hỗ trợ cài đặt như app

## 🛠️ Cài Đặt Local

```bash
# Clone project
git clone https://github.com/YOUR_USERNAME/AirQuality_Thesis.git
cd AirQuality_Thesis

# Tạo virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# hoặc: venv\Scripts\activate  # Windows

# Cài đặt dependencies
pip install -r requirements.txt

# Chạy server
python main.py
```

Mở trình duyệt: http://localhost:8000

## 📦 Deploy lên Railway

1. Push code lên GitHub
2. Vào [railway.app](https://railway.app)
3. New Project → Deploy from GitHub
4. Chọn repo → Done!

## 📁 Cấu Trúc

```
├── main.py           # Backend FastAPI + AI
├── index.html        # Frontend Dashboard
├── stations.json     # Danh sách 400+ trạm
├── requirements.txt  # Python dependencies
├── Procfile          # Deploy config
└── manifest.json     # PWA config
```

## 🔌 API Endpoints

| Endpoint | Mô tả |
|----------|-------|
| `GET /api/stations` | Danh sách trạm + AQI |
| `GET /api/stats` | Thống kê tổng quan |
| `GET /api/history/{uid}` | Lịch sử 24h |
| `GET /api/predictions/{uid}` | Dự báo AI |

## 📝 License

MIT License - Đồ án tốt nghiệp 2024
