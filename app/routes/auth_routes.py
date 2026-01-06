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
from email_service import generate_otp, send_verification_email, get_otp_expiry_time, OTP_EXPIRY_MINUTES

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ===== ADDITIONAL SCHEMAS =====
class VerifyOTPRequest(BaseModel):
    email: EmailStr
    otp: str


class ResendOTPRequest(BaseModel):
    email: EmailStr


class RegisterResponse(BaseModel):
    message: str
    email: str
    requires_verification: bool = True


# ===== ENDPOINTS =====

@router.post("/register", response_model=RegisterResponse)
def register(data: UserRegister, db: Session = Depends(get_db)):
    """Đăng ký tài khoản mới - yêu cầu xác thực email"""
    # Check if email exists
    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        if existing.is_verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email đã được sử dụng"
            )
        else:
            # User exists but not verified - update and resend OTP
            otp = generate_otp()
            existing.password_hash = hash_password(data.password)
            existing.name = data.name
            existing.verification_token = otp
            existing.otp_expires = get_otp_expiry_time()
            db.commit()
            
            # Send verification email
            send_verification_email(data.email, otp, data.name)
            
            logging.info(f"Resent OTP to existing unverified user: {data.email}")
            return RegisterResponse(
                message=f"Mã xác thực đã được gửi đến {data.email}. Vui lòng kiểm tra email.",
                email=data.email
            )
    
    # Generate OTP
    otp = generate_otp()
    
    # Create user (unverified)
    user = User(
        email=data.email,
        password_hash=hash_password(data.password),
        name=data.name,
        is_verified=False,
        verification_token=otp,
        otp_expires=get_otp_expiry_time()
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Send verification email
    send_verification_email(data.email, otp, data.name)
    
    logging.info(f"New user registered (pending verification): {user.email}")
    return RegisterResponse(
        message=f"Mã xác thực đã được gửi đến {data.email}. Vui lòng kiểm tra email.",
        email=data.email
    )


@router.post("/verify", response_model=TokenResponse)
def verify_otp(data: VerifyOTPRequest, db: Session = Depends(get_db)):
    """Xác thực mã OTP và hoàn tất đăng ký"""
    user = db.query(User).filter(User.email == data.email).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email không tồn tại"
        )
    
    if user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tài khoản đã được xác thực"
        )
    
    # Check OTP expiry
    if user.otp_expires and datetime.utcnow() > user.otp_expires:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mã xác thực đã hết hạn. Vui lòng yêu cầu mã mới."
        )
    
    # Verify OTP
    if user.verification_token != data.otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mã xác thực không đúng"
        )
    
    # Mark as verified
    user.is_verified = True
    user.verification_token = None
    user.otp_expires = None
    db.commit()
    
    # Create token and login
    token = create_access_token({"sub": str(user.id)})
    
    logging.info(f"User verified and logged in: {user.email}")
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user)
    )


@router.post("/resend-otp")
def resend_otp(data: ResendOTPRequest, db: Session = Depends(get_db)):
    """Gửi lại mã OTP"""
    user = db.query(User).filter(User.email == data.email).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email không tồn tại"
        )
    
    if user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tài khoản đã được xác thực"
        )
    
    # Generate new OTP
    otp = generate_otp()
    user.verification_token = otp
    user.otp_expires = get_otp_expiry_time()
    db.commit()
    
    # Send email
    send_verification_email(data.email, otp, user.name)
    
    logging.info(f"Resent OTP to: {data.email}")
    return {
        "message": f"Mã xác thực mới đã được gửi đến {data.email}",
        "expires_in_minutes": OTP_EXPIRY_MINUTES
    }


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
        
        # Check if email is verified (with graceful fallback for missing column)
        is_verified = getattr(user, 'is_verified', True)  # Default to True if column doesn't exist
        if not is_verified:
            # Resend OTP automatically
            otp = generate_otp()
            if hasattr(user, 'verification_token'):
                user.verification_token = otp
            if hasattr(user, 'otp_expires'):
                user.otp_expires = get_otp_expiry_time()
            db.commit()
            send_verification_email(data.email, otp, user.name)
            
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="EMAIL_NOT_VERIFIED"  # Special code for frontend to show OTP modal
            )
        
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
