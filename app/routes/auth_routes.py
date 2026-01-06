"""
Authentication routes for AirWatch ASEAN
/api/auth/*
"""
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional

from database import get_db, User
from auth import (
    hash_password, verify_password, create_access_token, require_auth,
    UserRegister, UserLogin, UserResponse, TokenResponse
)


router = APIRouter(prefix="/api/auth", tags=["auth"])


# ===== ADDITIONAL SCHEMAS =====



class RegisterResponse(BaseModel):
    message: str
    email: str
    requires_verification: bool = True


# ===== ENDPOINTS =====

@router.post("/register", response_model=RegisterResponse)
def register(data: UserRegister, db: Session = Depends(get_db)):
    """Đăng ký tài khoản mới - không yêu cầu xác thực email"""
    # Check if email exists
    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email đã được sử dụng"
        )
    
    # Create user (verified immediately - no OTP required)
    user = User(
        email=data.email,
        password_hash=hash_password(data.password),
        name=data.name,
        is_verified=True,  # Auto-verified
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    logging.info(f"New user registered: {user.email}")
    return RegisterResponse(
        message=f"Đăng ký thành công! Bạn có thể đăng nhập ngay.",
        email=data.email,
        requires_verification=False
    )








@router.post("/login", response_model=TokenResponse)
def login(data: UserLogin, db: Session = Depends(get_db)):
    """Đăng nhập"""
    try:
        user = db.query(User).filter(User.email == data.email).first()
        
        if not user or not verify_password(data.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email hoặc mật khẩu không đúng"
            )
        
        # Skip email verification check - all users are auto-verified
        
        is_active = getattr(user, 'is_active', True)  # Default to True if column doesn't exist
        if not is_active:
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
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi hệ thống: {str(e)}"
        )


@router.get("/me", response_model=UserResponse)
def get_me(user: User = Depends(require_auth)):
    """Lấy thông tin user hiện tại"""
    return UserResponse.model_validate(user)


@router.post("/logout")
def logout():
    """Đăng xuất (client xóa token)"""
    return {"message": "Đăng xuất thành công"}
