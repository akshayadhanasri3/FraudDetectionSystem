from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel, EmailStr
import os

from database.connection import get_db
from database.models import User, OTPStore
from core import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, decode_token,
    generate_otp, send_email,
)

router = APIRouter()
templates = Jinja2Templates(directory="templates")

OTP_EXPIRE_MINUTES = 10


# ─── Pydantic Schemas ─────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class OTPVerifyRequest(BaseModel):
    email: EmailStr
    otp: str
    purpose: str  # 'verify' | 'reset'

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    otp: str
    new_password: str

class RefreshRequest(BaseModel):
    refresh_token: str


# ─── Page Routes ──────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return RedirectResponse(url="/login")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@router.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request})


@router.get("/verify-otp", response_class=HTMLResponse)
async def otp_page(request: Request):
    return templates.TemplateResponse("otp.html", {"request": request})


@router.get("/forgot-password", response_class=HTMLResponse)
async def forgot_page(request: Request):
    return templates.TemplateResponse("forgot_password.html", {"request": request})


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})


# ─── API Routes ───────────────────────────────────────────────────────────────

@router.post("/api/auth/register")
async def register(data: RegisterRequest, db: Session = Depends(get_db)):
    # Check duplicates
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    if db.query(User).filter(User.username == data.username).first():
        raise HTTPException(status_code=400, detail="Username already taken")

    # Validate password
    if len(data.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    user = User(
        username=data.username,
        email=data.email,
        hashed_password=hash_password(data.password),
        is_verified=False,
    )
    db.add(user)
    db.commit()

    # Send OTP
    otp = generate_otp()
    expires = datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRE_MINUTES)
    db.add(OTPStore(email=data.email, otp_code=otp, purpose="verify", expires_at=expires))
    db.commit()

    await send_email(
        data.email,
        "FraudShield - Verify Your Email",
        f"""
        <h2>Welcome to FraudShield!</h2>
        <p>Your verification OTP is:</p>
        <h1 style="color:#6366f1;letter-spacing:8px">{otp}</h1>
        <p>Valid for {OTP_EXPIRE_MINUTES} minutes.</p>
        """
    )

    return {"message": "Registered! Check your email for OTP.", "email": data.email}


@router.post("/api/auth/verify-otp")
async def verify_otp(data: OTPVerifyRequest, db: Session = Depends(get_db)):
    record = (
        db.query(OTPStore)
        .filter(
            OTPStore.email == data.email,
            OTPStore.otp_code == data.otp,
            OTPStore.purpose == data.purpose,
            OTPStore.is_used == False,
        )
        .order_by(OTPStore.created_at.desc())
        .first()
    )

    if not record:
        raise HTTPException(status_code=400, detail="Invalid OTP")

    if datetime.now(timezone.utc) > record.expires_at.replace(tzinfo=timezone.utc):
        raise HTTPException(status_code=400, detail="OTP expired")

    record.is_used = True

    if data.purpose == "verify":
        user = db.query(User).filter(User.email == data.email).first()
        if user:
            user.is_verified = True

    db.commit()
    return {"message": "OTP verified successfully"}


@router.post("/api/auth/login")
async def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user.is_verified:
        raise HTTPException(status_code=403, detail="Email not verified. Please verify first.")

    access_token = create_access_token({"sub": str(user.id), "email": user.email})
    refresh_token = create_refresh_token({"sub": str(user.id), "email": user.email})

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "is_admin": user.is_admin,
        },
    }


@router.post("/api/auth/refresh")
async def refresh_token(data: RefreshRequest):
    payload = decode_token(data.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    new_access = create_access_token({"sub": payload["sub"], "email": payload["email"]})
    return {"access_token": new_access, "token_type": "bearer"}


@router.post("/api/auth/forgot-password")
async def forgot_password(data: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        # Don't reveal if email exists
        return {"message": "If that email exists, an OTP has been sent."}

    otp = generate_otp()
    expires = datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRE_MINUTES)
    db.add(OTPStore(email=data.email, otp_code=otp, purpose="reset", expires_at=expires))
    db.commit()

    await send_email(
        data.email,
        "FraudShield - Password Reset OTP",
        f"""
        <h2>Password Reset Request</h2>
        <p>Your reset OTP is:</p>
        <h1 style="color:#ef4444;letter-spacing:8px">{otp}</h1>
        <p>Valid for {OTP_EXPIRE_MINUTES} minutes. If you didn't request this, ignore this email.</p>
        """
    )
    return {"message": "If that email exists, an OTP has been sent."}


@router.post("/api/auth/reset-password")
async def reset_password(data: ResetPasswordRequest, db: Session = Depends(get_db)):
    record = (
        db.query(OTPStore)
        .filter(
            OTPStore.email == data.email,
            OTPStore.otp_code == data.otp,
            OTPStore.purpose == "reset",
            OTPStore.is_used == False,
        )
        .order_by(OTPStore.created_at.desc())
        .first()
    )

    if not record:
        raise HTTPException(status_code=400, detail="Invalid OTP")
    if datetime.now(timezone.utc) > record.expires_at.replace(tzinfo=timezone.utc):
        raise HTTPException(status_code=400, detail="OTP expired")

    if len(data.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.hashed_password = hash_password(data.new_password)
    record.is_used = True
    db.commit()

    return {"message": "Password reset successfully! Please login."}


@router.post("/api/auth/resend-otp")
async def resend_otp(data: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    otp = generate_otp()
    expires = datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRE_MINUTES)
    db.add(OTPStore(email=data.email, otp_code=otp, purpose="verify", expires_at=expires))
    db.commit()

    await send_email(
        data.email,
        "FraudShield - New OTP",
        f"""
        <h2>New Verification OTP</h2>
        <p>Your new OTP is:</p>
        <h1 style="color:#6366f1;letter-spacing:8px">{otp}</h1>
        <p>Valid for {OTP_EXPIRE_MINUTES} minutes.</p>
        """
    )
    return {"message": "New OTP sent to your email."}
