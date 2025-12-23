"""
AQI Predictor module for AirWatch ASEAN
Machine Learning predictions for AQI with Model Caching
"""
import os
import sqlite3
import logging
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

try:
    import joblib
    JOBLIB_AVAILABLE = True
except ImportError:
    JOBLIB_AVAILABLE = False
    logging.warning("joblib not available, model caching disabled")

from sklearn.ensemble import GradientBoostingRegressor
from app.config import DB_NAME

# Model cache directory
MODELS_DIR = Path("models")
MODELS_DIR.mkdir(exist_ok=True)

# Model cache expiration (24 hours)
MODEL_CACHE_HOURS = 24


class AQIPredictor:
    def __init__(self):
        self.models = {}  # In-memory cache: {uid: (model, timestamp)}
        self.model_metadata = {}  # Track when models were trained
    
    def _get_model_path(self, uid):
        """Get file path for cached model"""
        return MODELS_DIR / f"station_{uid}_model.joblib"
    
    def _get_metadata_path(self, uid):
        """Get file path for model metadata"""
        return MODELS_DIR / f"station_{uid}_meta.joblib"
    
    def _is_model_valid(self, uid):
        """Check if cached model is still valid (< 24 hours old)"""
        if uid in self.model_metadata:
            trained_at = self.model_metadata[uid].get('trained_at')
            if trained_at:
                age_hours = (datetime.now() - trained_at).total_seconds() / 3600
                return age_hours < MODEL_CACHE_HOURS
        return False
    
    def _load_cached_model(self, uid):
        """Load model from disk cache"""
        if not JOBLIB_AVAILABLE:
            return None
            
        model_path = self._get_model_path(uid)
        meta_path = self._get_metadata_path(uid)
        
        if model_path.exists() and meta_path.exists():
            try:
                model = joblib.load(model_path)
                metadata = joblib.load(meta_path)
                
                # Check if model is still valid
                trained_at = metadata.get('trained_at')
                if trained_at:
                    age_hours = (datetime.now() - trained_at).total_seconds() / 3600
                    if age_hours < MODEL_CACHE_HOURS:
                        self.models[uid] = model
                        self.model_metadata[uid] = metadata
                        logging.debug(f"Loaded cached model for station {uid}")
                        return model
            except Exception as e:
                logging.warning(f"Failed to load cached model for {uid}: {e}")
        
        return None
    
    def _save_model(self, uid, model):
        """Save model to disk cache"""
        if not JOBLIB_AVAILABLE:
            return
            
        try:
            model_path = self._get_model_path(uid)
            meta_path = self._get_metadata_path(uid)
            
            metadata = {
                'trained_at': datetime.now(),
                'uid': uid
            }
            
            joblib.dump(model, model_path)
            joblib.dump(metadata, meta_path)
            
            self.models[uid] = model
            self.model_metadata[uid] = metadata
            logging.debug(f"Saved model for station {uid}")
        except Exception as e:
            logging.warning(f"Failed to save model for {uid}: {e}")
    
    def get_trend(self, data):
        """Phân tích xu hướng: rising, falling, stable"""
        if len(data) < 3:
            return "stable"
        recent = data[:3]
        older = data[3:6] if len(data) >= 6 else data[3:]
        
        if not older:
            return "stable"
            
        recent_avg = sum(recent) / len(recent)
        older_avg = sum(older) / len(older)
        
        diff_pct = (recent_avg - older_avg) / older_avg * 100 if older_avg > 0 else 0
        
        if diff_pct > 10:
            return "rising"
        elif diff_pct < -10:
            return "falling"
        return "stable"
    
    def predict_multi(self, uid, hours=[1, 6, 12, 24]):
        """
        Dự báo đa bước: 1h, 6h, 12h, 24h với model caching
        Sử dụng rolling prediction + historical hourly patterns
        """
        try:
            conn = sqlite3.connect(DB_NAME)
            df = pd.read_sql_query(
                f"SELECT timestamp, aqi FROM measurements WHERE station_uid={uid} ORDER BY timestamp DESC LIMIT 168", 
                conn
            )
            conn.close()
            
            # Cần ít nhất 1 bản ghi để dự báo
            if len(df) < 1 or df['aqi'].isna().all():
                return {h: "Đang học..." for h in hours}, "stable", 0
            
            aqi_values = df['aqi'].dropna().tolist()
            current_aqi = aqi_values[0] if aqi_values else 0
            
            # Phân tích xu hướng
            trend = self.get_trend(aqi_values)
            
            # === FALLBACK: Dự báo đơn giản khi ít dữ liệu (< 15 records) ===
            if len(aqi_values) < 15:
                predictions = {}
                avg_aqi = sum(aqi_values) / len(aqi_values)
                
                # Sử dụng weighted average: 70% current + 30% average
                base_pred = current_aqi * 0.7 + avg_aqi * 0.3
                
                # Điều chỉnh theo trend với variance tăng dần theo thời gian
                trend_factor = 1.05 if trend == "rising" else (0.95 if trend == "falling" else 1.0)
                
                for h in hours:
                    # Thêm variance dựa trên historical volatility
                    volatility = abs(max(aqi_values) - min(aqi_values)) / max(avg_aqi, 1) if len(aqi_values) > 1 else 0.1
                    time_decay = 1 + (volatility * h / 24)  # Uncertainty tăng theo thời gian
                    pred = base_pred * (trend_factor ** (h / 4)) * time_decay
                    predictions[h] = max(0, min(500, int(pred)))
                
                # Confidence thấp vì chưa đủ dữ liệu
                confidence = min(len(aqi_values) * 5, 40)
                return predictions, trend, confidence
            
            # === FULL ML MODEL: Khi có đủ dữ liệu (>= 15 records) ===
            df['ts'] = pd.to_datetime(df['timestamp'])
            df['hour'] = df['ts'].dt.hour
            df['day_of_week'] = df['ts'].dt.dayofweek
            df['is_weekend'] = (df['day_of_week'] >= 5).astype(int)
            
            # Thêm lag features với fillna
            df['lag_1'] = df['aqi'].shift(-1).fillna(df['aqi'])
            df['lag_3'] = df['aqi'].shift(-3).fillna(df['aqi'])
            df = df.dropna()
            
            if len(df) < 5:
                # Fallback nếu sau xử lý còn ít dữ liệu
                predictions = {h: max(0, min(500, int(current_aqi))) for h in hours}
                return predictions, trend, 30
            
            X = df[['hour', 'day_of_week', 'is_weekend', 'lag_1', 'lag_3']].values
            y = df['aqi'].values
            
            # Tính hourly patterns từ dữ liệu lịch sử
            hourly_avg = df.groupby('hour')['aqi'].mean().to_dict()
            overall_avg = df['aqi'].mean()
            
            # Try to use cached model first
            model = None
            if self._is_model_valid(uid):
                model = self.models.get(uid)
            
            if model is None:
                model = self._load_cached_model(uid)
            
            # Train new model if no valid cache
            if model is None:
                model = GradientBoostingRegressor(n_estimators=50, max_depth=3, random_state=42)
                model.fit(X, y)
                self._save_model(uid, model)
                logging.info(f"Trained new model for station {uid}")
            
            # Tính confidence score
            train_score = model.score(X, y)
            confidence = min(int(train_score * 100), 95)
            
            # === ROLLING PREDICTION: Dự báo từng bước, dùng kết quả trước cho bước sau ===
            predictions = {}
            sorted_hours = sorted(hours)
            
            # Tính volatility từ dữ liệu lịch sử
            volatility = df['aqi'].std() / max(overall_avg, 1) if len(df) > 1 else 0.1
            
            # Khởi tạo lag values từ dữ liệu thực
            prev_lag1 = current_aqi
            prev_lag3 = aqi_values[2] if len(aqi_values) > 2 else current_aqi
            prev_pred = current_aqi
            prev_hour_offset = 0
            
            for h in sorted_hours:
                next_time = datetime.now() + timedelta(hours=h)
                target_hour = next_time.hour
                target_weekday = next_time.weekday()
                is_weekend = 1 if target_weekday >= 5 else 0
                
                # Tính hourly pattern adjustment
                hour_pattern = hourly_avg.get(target_hour, overall_avg)
                hour_adjustment = (hour_pattern - overall_avg) / max(overall_avg, 1)
                
                # Rolling: sử dụng dự báo trước đó làm lag
                hours_since_last = h - prev_hour_offset
                
                if hours_since_last <= 1:
                    est_lag1 = prev_pred
                else:
                    # Nội suy giữa current và prev_pred
                    est_lag1 = prev_pred * 0.8 + current_aqi * 0.2
                
                if hours_since_last <= 3:
                    est_lag3 = prev_lag3 * 0.7 + prev_pred * 0.3
                else:
                    est_lag3 = prev_pred
                
                # Trend adjustment tăng dần theo thời gian
                trend_strength = 1 + (h / 24) * 0.15  # Max 15% stronger at 24h
                if trend == "rising":
                    trend_adj = 1 + (0.02 * h * trend_strength)
                elif trend == "falling":
                    trend_adj = 1 - (0.02 * h * trend_strength)
                else:
                    trend_adj = 1.0
                
                # Predict với model
                next_input = [[target_hour, target_weekday, is_weekend, est_lag1, est_lag3]]
                raw_pred = model.predict(next_input)[0]
                
                # Apply adjustments
                adjusted_pred = raw_pred * trend_adj * (1 + hour_adjustment * 0.3)
                
                # Thêm uncertainty margin tăng theo thời gian
                uncertainty = volatility * (h / 6) * 0.1
                if trend == "rising":
                    adjusted_pred *= (1 + uncertainty)
                elif trend == "falling":
                    adjusted_pred *= (1 - uncertainty * 0.5)
                
                final_pred = max(0, min(500, int(adjusted_pred)))
                predictions[h] = final_pred
                
                # Update rolling values cho bước tiếp theo
                prev_lag3 = prev_lag1
                prev_lag1 = prev_pred
                prev_pred = final_pred
                prev_hour_offset = h
            
            return predictions, trend, confidence
            
        except Exception as e:
            logging.error(f"Prediction error: {e}")
            return {h: "N/A" for h in hours}, "stable", 0
    
    def predict(self, uid):
        """Backward compatible: trả về dự báo 1h"""
        preds, _, _ = self.predict_multi(uid, [1])
        return preds.get(1, "N/A")
    
    def clear_cache(self, uid=None):
        """Clear model cache for a station or all stations"""
        if uid:
            # Clear specific station
            self.models.pop(uid, None)
            self.model_metadata.pop(uid, None)
            model_path = self._get_model_path(uid)
            meta_path = self._get_metadata_path(uid)
            if model_path.exists():
                model_path.unlink()
            if meta_path.exists():
                meta_path.unlink()
        else:
            # Clear all
            self.models.clear()
            self.model_metadata.clear()
            for f in MODELS_DIR.glob("*.joblib"):
                f.unlink()


# Singleton predictor instance
predictor = AQIPredictor()
