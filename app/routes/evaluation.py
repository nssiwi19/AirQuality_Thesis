"""
Model evaluation routes for AirWatch ASEAN (Thesis Chapter 4)
/api/model-evaluation, /api/model-evaluation-all
"""
import sqlite3
import pandas as pd
import numpy as np
from fastapi import APIRouter
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split

from app.config import DB_NAME

router = APIRouter()


@router.get("/api/model-evaluation/{uid}")
def api_model_evaluation(uid: int):
    """
    Compare ML models for thesis Chapter 4.
    Returns RMSE, MAE, R² for:
    - Linear Regression (Baseline)
    - Random Forest
    - Gradient Boosting
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT aqi, timestamp FROM measurements 
        WHERE station_uid = ? AND aqi IS NOT NULL
        ORDER BY timestamp DESC LIMIT 200
    """, (uid,))
    
    rows = cursor.fetchall()
    conn.close()
    
    if len(rows) < 30:
        return {"error": "Không đủ dữ liệu (cần ít nhất 30 records)"}
    
    # Prepare dataframe
    df = pd.DataFrame(rows, columns=['aqi', 'timestamp'])
    df['ts'] = pd.to_datetime(df['timestamp'])
    df['hour'] = df['ts'].dt.hour
    df['day_of_week'] = df['ts'].dt.dayofweek
    df['is_weekend'] = (df['day_of_week'] >= 5).astype(int)
    df['lag_1'] = df['aqi'].shift(-1).fillna(df['aqi'])
    df['lag_3'] = df['aqi'].shift(-3).fillna(df['aqi'])
    df = df.dropna()
    
    if len(df) < 20:
        return {"error": "Không đủ dữ liệu sau xử lý"}
    
    # Features and target
    X = df[['hour', 'day_of_week', 'is_weekend', 'lag_1', 'lag_3']].values
    y = df['aqi'].values
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # Models to compare
    models = {
        "Linear Regression": LinearRegression(),
        "Random Forest": RandomForestRegressor(n_estimators=50, max_depth=5, random_state=42),
        "Gradient Boosting": GradientBoostingRegressor(n_estimators=50, max_depth=3, random_state=42)
    }
    
    results = []
    for name, model in models.items():
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)
        
        rmse = np.sqrt(mean_squared_error(y_test, y_pred))
        mae = mean_absolute_error(y_test, y_pred)
        r2 = r2_score(y_test, y_pred)
        
        results.append({
            "model": name,
            "rmse": round(rmse, 2),
            "mae": round(mae, 2),
            "r2_score": round(r2, 4),
            "train_samples": len(X_train),
            "test_samples": len(X_test)
        })
    
    # Sort by RMSE (best first)
    results.sort(key=lambda x: x['rmse'])
    
    return {
        "station_uid": uid,
        "total_samples": len(df),
        "features_used": ["hour", "day_of_week", "is_weekend", "lag_1", "lag_3"],
        "comparison": results,
        "best_model": results[0]["model"],
        "note": "RMSE thấp hơn = tốt hơn, R² cao hơn = tốt hơn"
    }


@router.get("/api/model-evaluation-all")
def api_model_evaluation_all():
    """
    Run model evaluation across multiple stations for thesis Chapter 4
    Returns aggregated statistics
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Get stations with enough data
    cursor.execute("""
        SELECT station_uid, COUNT(*) as cnt 
        FROM measurements 
        WHERE aqi IS NOT NULL 
        GROUP BY station_uid 
        HAVING cnt >= 50
        LIMIT 20
    """)
    
    stations = cursor.fetchall()
    conn.close()
    
    if not stations:
        return {"error": "Không có đủ dữ liệu để đánh giá"}
    
    all_results = {
        "Linear Regression": {"rmse": [], "mae": [], "r2": []},
        "Random Forest": {"rmse": [], "mae": [], "r2": []},
        "Gradient Boosting": {"rmse": [], "mae": [], "r2": []}
    }
    
    evaluated_stations = 0
    for uid, count in stations:
        try:
            result = api_model_evaluation(uid)
            if "comparison" in result:
                evaluated_stations += 1
                for model_result in result["comparison"]:
                    model_name = model_result["model"]
                    all_results[model_name]["rmse"].append(model_result["rmse"])
                    all_results[model_name]["mae"].append(model_result["mae"])
                    all_results[model_name]["r2"].append(model_result["r2_score"])
        except:
            continue
    
    # Calculate averages
    summary = []
    for model_name, metrics in all_results.items():
        if metrics["rmse"]:
            summary.append({
                "model": model_name,
                "avg_rmse": round(np.mean(metrics["rmse"]), 2),
                "avg_mae": round(np.mean(metrics["mae"]), 2),
                "avg_r2": round(np.mean(metrics["r2"]), 4),
                "std_rmse": round(np.std(metrics["rmse"]), 2)
            })
    
    summary.sort(key=lambda x: x['avg_rmse'])
    
    return {
        "evaluated_stations": evaluated_stations,
        "summary": summary,
        "best_model": summary[0]["model"] if summary else "N/A",
        "conclusion": f"Với {evaluated_stations} trạm đánh giá, {summary[0]['model'] if summary else 'N/A'} cho kết quả tốt nhất với RMSE trung bình {summary[0]['avg_rmse'] if summary else 'N/A'}"
    }
