"""
Authentication routes for AirWatch ASEAN
/api/auth/*
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db, User
from auth import (
    hash_password, verify_password, create_access_token, require_auth,
    UserRegister, UserLogin, UserResponse, TokenResponse
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
def register(data: UserRegister, db: Session = Depends(get_db)):
    """Đăng ký tài khoản mới"""
    # Check if email exists
    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email đã được sử dụng"
        )
    
    # Create user
    user = User(
        email=data.email,
        password_hash=hash_password(data.password),
        name=data.name
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Create token
    token = create_access_token({"sub": str(user.id)})
    
    logging.info(f"New user registered: {user.email}")
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user)
    )


@router.post("/login", response_model=TokenResponse)
def login(data: UserLogin, db: Session = Depends(get_db)):
    """Đăng nhập"""
    user = db.query(User).filter(User.email == data.email).first()
    
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoặc mật khẩu không đúng"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản đã bị khóa"
        )
    
    token = create_access_token({"sub": str(user.id)})
    
    logging.info(f"User logged in: {user.email}")
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user)
    )


@router.get("/me", response_model=UserResponse)
def get_me(user: User = Depends(require_auth)):
    """Lấy thông tin user hiện tại"""
    return UserResponse.model_validate(user)


@router.post("/logout")
def logout():
    """Đăng xuất (client xóa token)"""
    return {"message": "Đăng xuất thành công"}
