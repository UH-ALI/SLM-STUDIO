"""
backend/app/routers/auth.py

Handles:
  POST /auth/register          — create account, send verification email
  POST /auth/login             — authenticate, return JWT  (hard-gates unverified users)
  GET  /auth/verify-email      — token → mark is_email_verified=True
  POST /auth/resend-verification — rate-limited resend
  POST /auth/forgot-password   — generate reset token (always 200, anti-enumeration)
  POST /auth/reset-password    — consume reset token, update password
"""

import uuid
import logging
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import or_
import redis

from app import models, schemas
from app.database import get_db
from app.core import security
from app.core.config import settings
from app.core.email import send_verification_email, send_password_reset_email

router = APIRouter()
logger = logging.getLogger(__name__)

# Redis client — re-use the same connection string Celery uses
_redis = redis.Redis.from_url(settings.CELERY_BROKER_URL, decode_responses=True)

# Token TTLs
_VERIFY_TTL_SECONDS = 24 * 60 * 60   # 24 hours
_RESET_TTL_SECONDS  = 15 * 60        # 15 minutes
_RESEND_RATE_SECONDS = 60             # 1 resend per 60 s per email
_RESET_RATE_LIMIT    = 3              # max 3 forgot-password requests per hour per email
_RESET_RATE_WINDOW   = 60 * 60       # 1 hour


# ─── REGISTRATION ─────────────────────────────────────────────────────────────

@router.post("/register", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    """
    Creates a new user account with is_email_verified=False,
    stores a verification token in Redis, and sends a verification email.
    """
    # 1. Duplicate email check — return structured error for frontend field routing
    if db.query(models.User).filter(models.User.email == user.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"field": "email", "message": "A user with this email is already registered."},
        )

    # 2. Duplicate username check
    if db.query(models.User).filter(models.User.username == user.username).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"field": "username", "message": "This username is already taken. Please choose another."},
        )

    # 3. Hash password and create user
    hashed_password = security.get_password_hash(user.password)
    full_name = f"{user.first_name} {user.last_name or ''}".strip()

    new_user = models.User(
        email=user.email,
        username=user.username,
        full_name=full_name,
        hashed_password=hashed_password,
        is_email_verified=False,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # 4. Generate verification token, store in Redis, send email
    token = str(uuid.uuid4())
    _redis.setex(f"verify_token:{token}", _VERIFY_TTL_SECONDS, str(new_user.id))

    try:
        send_verification_email(new_user.email, token)
    except Exception as exc:
        logger.error("[Auth] Failed to send verification email: %s", exc)
        # Do NOT block registration — the user can resend later

    return new_user


# ─── LOGIN ────────────────────────────────────────────────────────────────────

@router.post("/login", response_model=schemas.TokenWithUser)
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """
    Authenticates a user and returns a JWT + user profile.
    Allows login with EITHER email OR username.
    Hard-gates unverified users with a structured 403 so the frontend
    can show a resend-verification button inline.
    """
    user = db.query(models.User).filter(
        or_(
            models.User.email == form_data.username,
            models.User.username == form_data.username,
        )
    ).first()

    # OWASP: keep the credential-failure message generic to prevent user enumeration
    if not user or not security.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email/username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user account.")

    # Hard gate: unverified users cannot log in
    if not user.is_email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "field": "email",
                "message": "Please verify your email before logging in. Check your inbox for the verification link.",
                "action": "resend_verification",
            },
        )

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        data={"sub": user.email},
        expires_delta=access_token_expires,
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": schemas.UserResponse.model_validate(user),
    }


# ─── EMAIL VERIFICATION ───────────────────────────────────────────────────────

@router.get("/verify-email", response_model=schemas.EmailActionResponse)
def verify_email(token: str = Query(...), db: Session = Depends(get_db)):
    """
    Validates the one-time token from the verification email,
    marks the user as verified, and deletes the token.
    """
    redis_key = f"verify_token:{token}"
    user_id = _redis.get(redis_key)

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This verification link has expired or is invalid. Please request a new one.",
        )

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    if user.is_email_verified:
        _redis.delete(redis_key)
        return {"message": "Your email is already verified. You can log in."}

    user.is_email_verified = True
    db.commit()
    _redis.delete(redis_key)

    logger.info("[Auth] Email verified for user %s", user_id)
    return {"message": "Email verified successfully! You can now log in."}


# ─── RESEND VERIFICATION ──────────────────────────────────────────────────────

@router.post("/resend-verification", response_model=schemas.EmailActionResponse)
def resend_verification(payload: schemas.ResendVerificationRequest, db: Session = Depends(get_db)):
    """
    Generates a fresh verification token and re-sends the verification email.
    Rate-limited: one resend per 60 seconds per email address.
    Always returns 200 (anti-enumeration — never reveal whether the email exists).
    """
    rate_key = f"resend_rate:{payload.email}"
    if _redis.exists(rate_key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Please wait before requesting another verification email.",
        )

    user = db.query(models.User).filter(models.User.email == payload.email).first()

    if user and not user.is_email_verified:
        token = str(uuid.uuid4())
        _redis.setex(f"verify_token:{token}", _VERIFY_TTL_SECONDS, str(user.id))
        _redis.setex(rate_key, _RESEND_RATE_SECONDS, "1")
        try:
            send_verification_email(user.email, token)
        except Exception as exc:
            logger.error("[Auth] Failed to resend verification email: %s", exc)

    return {"message": "If an unverified account exists with this email, a verification link has been sent."}


# ─── FORGOT PASSWORD ──────────────────────────────────────────────────────────

@router.post("/forgot-password", response_model=schemas.EmailActionResponse)
def forgot_password(payload: schemas.ForgotPasswordRequest, db: Session = Depends(get_db)):
    """
    Generates a password-reset token and sends a reset email.
    Rate-limited: max 3 requests per email per hour.
    ALWAYS returns 200 with a generic message (anti-enumeration).
    """
    _STANDARD_RESPONSE = {"message": "If an account exists with this email, a reset link has been sent."}

    rate_key = f"reset_rate:{payload.email}"
    current_count = _redis.get(rate_key)
    if current_count and int(current_count) >= _RESET_RATE_LIMIT:
        # Return the standard message — don't reveal rate limiting to potential attacker
        return _STANDARD_RESPONSE

    user = db.query(models.User).filter(models.User.email == payload.email).first()
    if user:
        token = str(uuid.uuid4())
        _redis.setex(f"reset_token:{token}", _RESET_TTL_SECONDS, str(user.id))

        # Increment rate limit counter
        pipe = _redis.pipeline()
        pipe.incr(rate_key)
        pipe.expire(rate_key, _RESET_RATE_WINDOW)
        pipe.execute()

        try:
            send_password_reset_email(user.email, token)
        except Exception as exc:
            logger.error("[Auth] Failed to send password reset email: %s", exc)

    return _STANDARD_RESPONSE


# ─── RESET PASSWORD ───────────────────────────────────────────────────────────

@router.post("/reset-password", response_model=schemas.EmailActionResponse)
def reset_password(payload: schemas.ResetPasswordRequest, db: Session = Depends(get_db)):
    """
    Validates the reset token from the email, updates the password,
    and deletes the token (single-use).
    """
    redis_key = f"reset_token:{payload.token}"
    user_id = _redis.get(redis_key)

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This password reset link has expired or has already been used. Please request a new one.",
        )

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    user.hashed_password = security.get_password_hash(payload.new_password)
    db.commit()
    _redis.delete(redis_key)   # single-use: invalidate immediately

    logger.info("[Auth] Password reset for user %s", user_id)
    return {"message": "Password reset successfully. You can now log in with your new password."}
