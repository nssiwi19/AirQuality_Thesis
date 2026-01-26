"""
Script đánh giá độ chính xác IDW và Gradient Boosting
Chạy: python validate_models.py
Output: Bảng so sánh kết quả nội suy/dự báo vs thực tế
"""
import sqlite3
import math
import pandas as pd
import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from tabulate import tabulate

# Database path
DB_NAME = "air_quality_asean.db"

# Load stations config
import json
with open("stations.json", "r", encoding="utf-8") as f:
    STATIONS_CONFIG = json.load(f)


def haversine_km(lat1, lng1, lat2, lng2):
    """Calculate distance in km between two points"""
    R = 6371
    lat1, lng1, lat2, lng2 = map(math.radians, [lat1, lng1, lat2, lng2])
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng/2)**2
    return R * 2 * math.asin(math.sqrt(a))


def idw_predict(target_lat, target_lng, stations, exclude_uid=None, power=2.0, max_dist_km=200):
    """IDW interpolation excluding one station"""
    num = 0
    den = 0
    nearest_dist = float('inf')
    
    for st in stations:
        if st['uid'] == exclude_uid:
            continue
        
        dist = haversine_km(target_lat, target_lng, st['lat'], st['lng'])
        
        if dist < nearest_dist:
            nearest_dist = dist
        
        if dist > max_dist_km:
            continue
        
        if dist < 1:
            return st['aqi'], dist
        
        weight = 1 / (dist ** power)
        num += st['aqi'] * weight
        den += weight
    
    if den == 0:
        return None, nearest_dist
    
    return round(num / den), nearest_dist


def validate_idw():
    """Leave-One-Out Cross-Validation for IDW"""
    print("\n" + "="*70)
    print("BẢNG 1: ĐÁNH GIÁ IDW INTERPOLATION (Leave-One-Out Cross-Validation)")
    print("="*70)
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Get latest AQI for each station
    cursor.execute("""
        SELECT m.station_uid, m.aqi, m.station_name
        FROM measurements m
        INNER JOIN (
            SELECT station_uid, MAX(timestamp) as max_ts 
            FROM measurements GROUP BY station_uid
        ) latest ON m.station_uid = latest.station_uid AND m.timestamp = latest.max_ts
        WHERE m.aqi IS NOT NULL
    """)
    
    db_aqi = {row[0]: {'aqi': row[1], 'name': row[2]} for row in cursor.fetchall()}
    conn.close()
    
    # Build station list with current AQI
    stations = []
    for st in STATIONS_CONFIG:
        uid = st.get('uid')
        if uid in db_aqi:
            stations.append({
                'uid': uid,
                'name': db_aqi[uid]['name'] or st.get('name', 'Unknown'),
                'lat': st['lat'],
                'lng': st['lng'],
                'aqi': db_aqi[uid]['aqi']
            })
    
    print(f"\nSố trạm có dữ liệu: {len(stations)}")
    
    # Leave-One-Out Cross-Validation
    results = []
    errors = []
    
    for target_st in stations:
        predicted_aqi, distance = idw_predict(
            target_st['lat'], 
            target_st['lng'], 
            stations, 
            exclude_uid=target_st['uid']
        )
        
        if predicted_aqi is not None:
            actual = target_st['aqi']
            error = predicted_aqi - actual
            errors.append(error)
            
            results.append({
                "Tên trạm": target_st['name'][:30],
                "AQI thực": actual,
                "IDW dự đoán": predicted_aqi,
                "Sai số": error,
                "|Sai số|": abs(error),
                "Khoảng cách (km)": round(distance, 1)
            })
    
    # Sort by absolute error
    results.sort(key=lambda x: x['|Sai số|'], reverse=True)
    
    # Print table
    print("\nKết quả Cross-Validation (20 trạm có sai số lớn nhất):")
    print(tabulate(results[:20], headers="keys", tablefmt="grid"))
    
    # Calculate metrics
    errors_np = np.array(errors)
    actuals = np.array([r['AQI thực'] for r in results])
    
    rmse = np.sqrt(np.mean(errors_np ** 2))
    mae = np.mean(np.abs(errors_np))
    r2 = 1 - (np.sum(errors_np ** 2) / np.sum((actuals - np.mean(actuals)) ** 2))
    mape = np.mean(np.abs(errors_np / np.maximum(actuals, 1))) * 100
    
    print(f"\n--- METRICS IDW ---")
    print(f"RMSE: {rmse:.2f}")
    print(f"MAE: {mae:.2f}")
    print(f"R²: {r2:.4f}")
    print(f"MAPE: {mape:.2f}%")
    
    return {"rmse": rmse, "mae": mae, "r2": r2, "mape": mape, "n": len(results)}


def validate_gradient_boosting():
    """Temporal validation for Gradient Boosting vs Baseline"""
    print("\n" + "="*70)
    print("BẢNG 2: ĐÁNH GIÁ GRADIENT BOOSTING vs BASELINE (T+1h, T+6h)")
    print("="*70)
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Get stations with enough historical data
    cursor.execute("""
        SELECT station_uid, station_name, COUNT(*) as cnt 
        FROM measurements 
        WHERE aqi IS NOT NULL 
        GROUP BY station_uid 
        HAVING cnt >= 100
        LIMIT 30
    """)
    
    stations = cursor.fetchall()
    
    print(f"\nSố trạm có đủ dữ liệu lịch sử (>100 records): {len(stations)}")
    
    horizons = [1, 6]
    metrics_summary = []
    
    for h in horizons:
        print(f"\n--- Đánh giá Dự báo T+{h} giờ ---")
        all_errors_gb = []
        all_errors_base = []
        all_actuals = []
        
        for uid, name, count in stations:
            # Get historical data (increased limit for T+6)
            df = pd.read_sql_query(
                "SELECT timestamp, aqi FROM measurements WHERE station_uid=? ORDER BY timestamp DESC LIMIT 500",
                conn,
                params=(str(uid),)
            )
            
            if len(df) < 50:
                continue
            
            df['ts'] = pd.to_datetime(df['timestamp'])
            df['hour'] = df['ts'].dt.hour
            df['day_of_week'] = df['ts'].dt.dayofweek
            
            # Target: AQI at time T. Feature: AQI at time T-h
            # Since data is DESC (Index 0 is T, Index 1 is T-1)
            # We want to predict df['aqi'] (T) using df['aqi'].shift(-h) (T-h)
            
            # Create Lag features
            df[f'lag_{h}'] = df['aqi'].shift(-h)
            
            # Drop NaN created by shifting (the oldest records wont have previous history)
            df = df.dropna()
            
            if len(df) < 50:
                continue
            
            # Features and Target
            X = df[['hour', 'day_of_week', f'lag_{h}']].values
            y = df['aqi'].values # Actual AQI at time T
            
            # Baseline Prediction (Persistence): Predict T using value at T-h
            # So Pred_Baseline = Lag_h
            y_pred_base = df[f'lag_{h}'].values
            
            # Train/test split (80/20)
            split_idx = int(len(X) * 0.8)
            X_train, X_test = X[:split_idx], X[split_idx:]
            y_train, y_test = y[:split_idx], y[split_idx:]
            y_pred_base_test = y_pred_base[split_idx:]
            
            if len(X_train) < 10 or len(X_test) < 3:
                continue
            
            # Train GB Model
            model = GradientBoostingRegressor(n_estimators=50, max_depth=3, random_state=42)
            model.fit(X_train, y_train)
            
            # Predict GB
            y_pred_gb = model.predict(X_test)
            
            # Collect errors
            all_errors_gb.extend((y_pred_gb - y_test).tolist())
            all_errors_base.extend((y_pred_base_test - y_test).tolist())
            all_actuals.extend(y_test.tolist())

        # Calculate metrics for Horizon h
        if not all_actuals:
            print("Không đủ dữ liệu để đánh giá.")
            continue
            
        errors_gb = np.array(all_errors_gb)
        errors_base = np.array(all_errors_base)
        actuals = np.array(all_actuals)
        
        # Baseline Metrics
        rmse_base = np.sqrt(np.mean(errors_base ** 2))
        mae_base = np.mean(np.abs(errors_base))
        r2_base = 1 - (np.sum(errors_base ** 2) / np.sum((actuals - np.mean(actuals)) ** 2))
        
        # GB Metrics
        rmse_gb = np.sqrt(np.mean(errors_gb ** 2))
        mae_gb = np.mean(np.abs(errors_gb))
        r2_gb = 1 - (np.sum(errors_gb ** 2) / np.sum((actuals - np.mean(actuals)) ** 2))
        
        # Improvement
        imp_rmse = ((rmse_base - rmse_gb) / rmse_base) * 100
        
        metrics_summary.append({
            "Mô hình": "Baseline (Persistence)",
            "Mục tiêu": f"T+{h} giờ",
            "RMSE": rmse_base,
            "MAE": mae_base,
            "R2": r2_base,
            "Cải thiện": "-"
        })
        
        metrics_summary.append({
            "Mô hình": "Gradient Boosting",
            "Mục tiêu": f"T+{h} giờ",
            "RMSE": rmse_gb,
            "MAE": mae_gb,
            "R2": r2_gb,
            "Cải thiện": f"~{imp_rmse:.1f}% (RMSE)"
        })

    conn.close()
    
    # Print Table
    print("\nKẾT QUẢ SO SÁNH CHI TIẾT:")
    headers = ["Mô hình", "Mục tiêu dự báo", "RMSE", "MAE", "R² Score", "Cải thiện so với Baseline"]
    table_data = [[m["Mô hình"], m["Mục tiêu"], f"{m['RMSE']:.1f}", f"{m['MAE']:.1f}", f"{m['R2']:.2f}", m["Cải thiện"]] for m in metrics_summary]
    print(tabulate(table_data, headers=headers, tablefmt="grid"))
    
    return metrics_summary


def print_comparison(idw_metrics, gb_metrics):
    """Print final comparison table"""
    print("\n" + "="*70)
    print("BẢNG 3: SO SÁNH TỔNG HỢP IDW vs GRADIENT BOOSTING")
    print("="*70)
    
    comparison = [
        {
            "Phương pháp": "IDW Interpolation",
            "Loại": "Nội suy không gian",
            "RMSE": f"{idw_metrics['rmse']:.2f}",
            "MAE": f"{idw_metrics['mae']:.2f}",
            "R²": f"{idw_metrics['r2']:.4f}",
            "MAPE": f"{idw_metrics['mape']:.2f}%",
            "Samples": idw_metrics['n']
        },
        {
            "Phương pháp": "Gradient Boosting",
            "Loại": "Dự báo thời gian",
            "RMSE": f"{gb_metrics['rmse']:.2f}",
            "MAE": f"{gb_metrics['mae']:.2f}",
            "R²": "N/A",
            "MAPE": "N/A",
            "Samples": gb_metrics['n']
        }
    ]
    
    print(tabulate(comparison, headers="keys", tablefmt="grid"))
    
    # Conclusion
    print("\n" + "="*70)
    print("KẾT LUẬN")
    print("="*70)
    
    if idw_metrics['rmse'] < gb_metrics['rmse']:
        print(f"✓ IDW Interpolation có RMSE thấp hơn ({idw_metrics['rmse']:.2f} < {gb_metrics['rmse']:.2f})")
        print("✓ IDW phù hợp hơn cho việc ước tính AQI tại các vị trí không có trạm đo")
    else:
        print(f"✓ Gradient Boosting có RMSE thấp hơn ({gb_metrics['rmse']:.2f} < {idw_metrics['rmse']:.2f})")
        print("✓ GB phù hợp hơn cho dự báo AQI")
    
    print("\n📊 Khuyến nghị sử dụng:")
    print("   - IDW: Ước tính AQI cho vị trí bất kỳ dựa trên các trạm lân cận")
    print("   - Gradient Boosting: Dự báo AQI theo thời gian (1h, 6h, 12h, 24h)")


if __name__ == "__main__":
    print("\n" + "🔬"*35)
    print("   ĐÁNH GIÁ ĐỘ CHÍNH XÁC: IDW vs GRADIENT BOOSTING")
    print("   AirWatch ASEAN - Thesis Chapter 4")
    print("🔬"*35)
    
    try:
        # Validate IDW
        idw_metrics = validate_idw()
        
        # Validate Gradient Boosting
        gb_metrics_list = validate_gradient_boosting()
        
        # Extract GB T+1 metrics for comparison table (2nd item in list is GB T+1)
        # List order: Base T+1, GB T+1, Base T+6, GB T+6
        gb_t1_metrics = next((m for m in gb_metrics_list if m['Mô hình'] == 'Gradient Boosting' and m['Mục tiêu'] == 'T+1 giờ'), None)
        
        if gb_t1_metrics:
             # Convert format to match print_comparison expectation
             gb_metrics_fmt = {
                 'rmse': gb_t1_metrics['RMSE'],
                 'mae': gb_t1_metrics['MAE'],
                 'n': 0 # not available in summary list but implied
             }
             print_comparison(idw_metrics, gb_metrics_fmt)
        
        print("\n✅ Hoàn thành đánh giá!")
        
    except Exception as e:
        print(f"\n❌ Lỗi: {e}")
        import traceback
        traceback.print_exc()
