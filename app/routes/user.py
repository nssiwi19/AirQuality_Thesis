"""
User routes for AirWatch ASEAN
/api/user/favorites, /api/user/alerts
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db, User, FavoriteLocation, AlertSetting
from auth import require_auth, FavoriteCreate, FavoriteResponse, AlertCreate, AlertResponse

router = APIRouter(prefix="/api/user", tags=["user"])


@router.get("/favorites", response_model=List[FavoriteResponse])
def get_favorites(user: User = Depends(require_auth), db: Session = Depends(get_db)):
    """Lấy danh sách vị trí yêu thích"""
    favorites = db.query(FavoriteLocation).filter(
        FavoriteLocation.user_id == user.id
    ).order_by(FavoriteLocation.created_at.desc()).all()
    return [FavoriteResponse.model_validate(f) for f in favorites]


@router.post("/favorites", response_model=FavoriteResponse)
def add_favorite(
    data: FavoriteCreate, 
    user: User = Depends(require_auth), 
    db: Session = Depends(get_db)
):
    """Thêm vị trí yêu thích"""
    # Check duplicate
    existing = db.query(FavoriteLocation).filter(
        FavoriteLocation.user_id == user.id,
        FavoriteLocation.lat == data.lat,
        FavoriteLocation.lng == data.lng
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vị trí này đã được lưu"
        )
    
    favorite = FavoriteLocation(
        user_id=user.id,
        name=data.name,
        lat=data.lat,
        lng=data.lng
    )
    db.add(favorite)
    db.commit()
    db.refresh(favorite)
    
    return FavoriteResponse.model_validate(favorite)


@router.delete("/favorites/{favorite_id}")
def delete_favorite(
    favorite_id: int,
    user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """Xóa vị trí yêu thích"""
    favorite = db.query(FavoriteLocation).filter(
        FavoriteLocation.id == favorite_id,
        FavoriteLocation.user_id == user.id
    ).first()
    
    if not favorite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy vị trí"
        )
    
    db.delete(favorite)
    db.commit()
    
    return {"message": "Đã xóa vị trí yêu thích"}


@router.get("/alerts", response_model=List[AlertResponse])
def get_user_alerts(user: User = Depends(require_auth), db: Session = Depends(get_db)):
    """Lấy danh sách cảnh báo"""
    alerts = db.query(AlertSetting).filter(
        AlertSetting.user_id == user.id
    ).order_by(AlertSetting.created_at.desc()).all()
    return [AlertResponse.model_validate(a) for a in alerts]


@router.post("/alerts", response_model=AlertResponse)
def add_alert(
    data: AlertCreate,
    user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """Tạo cảnh báo AQI cho vị trí"""
    alert = AlertSetting(
        user_id=user.id,
        name=data.name,
        lat=data.lat,
        lng=data.lng,
        threshold=data.threshold
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    
    return AlertResponse.model_validate(alert)


@router.delete("/alerts/{alert_id}")
def delete_alert(
    alert_id: int,
    user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """Xóa cảnh báo"""
    alert = db.query(AlertSetting).filter(
        AlertSetting.id == alert_id,
        AlertSetting.user_id == user.id
    ).first()
    
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy cảnh báo"
        )
    
    db.delete(alert)
    db.commit()
    
    return {"message": "Đã xóa cảnh báo"}
