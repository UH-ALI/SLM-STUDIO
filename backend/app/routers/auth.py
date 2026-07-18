import random
import string
import uuid
from datetime import timedelta, datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app import models, schemas
from app.database import get_db
from app.core import security
# Import the instantiated settings singleton directly
from app.core.config import settings
from app.services import email_service
from app.services.email_verification_service import check_email_deliverability
from app.core.rate_limit import check_rate_limit, reset_rate_limit, _redis

router = APIRouter()

# How long a password-reset code stays valid after being emailed.
RESET_CODE_TTL_MINUTES = 15

# [NEXT_STEPS.md #2] Shared brute-force caps for the two endpoints that were
# previously unthrottled: 5 guesses per account per window, then locked out
# until the window expires (login) or a fresh code is requested (reset).
LOGIN_ATTEMPT_LIMIT = 5
LOGIN_ATTEMPT_WINDOW_SECONDS = 15 * 60
RESET_ATTEMPT_LIMIT = 5

# [MERGED from fyp_SLM--AI-Improved-Updated] Email-verification link TTL and
# resend cooldown. Tokens live in Redis (same instance as rate limiting) —
# no new DB table needed, since a verify token is short-lived and single-use.
_VERIFY_TTL_SECONDS = 24 * 60 * 60
_RESEND_RATE_SECONDS = 60

# ---------------------------------------------------------
# CHECK EMAIL — used by the signup form (on blur) to tell the user, before
# they submit, whether this email is already registered and/or looks
# undeliverable, instead of only finding out after a full form submission.
# ---------------------------------------------------------
@router.post("/check-email", response_model=schemas.CheckEmailResponse)
def check_email(payload: schemas.CheckEmailRequest, db: Session = Depends(get_db)):
    exists = db.query(models.User).filter(models.User.email == payload.email).first() is not None

    # Skip the Verifalia round trip entirely if the account already exists —
    # the frontend only needs one reason to show, and "already registered"
    # takes priority over a deliverability check.
    if exists:
        return schemas.CheckEmailResponse(
            exists=True,
            deliverable=True,
            classification=None,
            reason="An account with this email already exists.",
        )

    result = check_email_deliverability(payload.email)
    return schemas.CheckEmailResponse(
        exists=False,
        deliverable=result["deliverable"],
        classification=result["classification"],
        reason=None if result["deliverable"] else "This email address doesn't look reachable.",
    )


# ---------------------------------------------------------
# VERIFY EMAIL — [MERGED from fyp_SLM--AI-Improved-Updated]
# Validates the one-time token from the verification email, marks the user
# as verified, and deletes the token. Token lives in Redis only (see
# _VERIFY_TTL_SECONDS above), same instance the rate limiter already uses.
# ---------------------------------------------------------
@router.get("/verify-email", response_model=schemas.EmailActionResponse)
def verify_email(token: str = Query(...), db: Session = Depends(get_db)):
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

    return {"message": "Email verified successfully! You can now log in."}


# ---------------------------------------------------------
# RESEND VERIFICATION — [MERGED from fyp_SLM--AI-Improved-Updated]
# Generates a fresh verification token and re-sends the verification email.
# Rate-limited to one resend per 60 seconds per email. Always returns 200
# (anti-enumeration — never reveal whether the email exists or is already
# verified), matching the same trade-off /auth/forgot-password already makes.
# ---------------------------------------------------------
@router.post("/resend-verification", response_model=schemas.EmailActionResponse)
def resend_verification(payload: schemas.ResendVerificationRequest, db: Session = Depends(get_db)):
    rate_key = f"resend_rate:{payload.email.strip().lower()}"
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
            email_service.send_verification_email(user.email, token)
        except Exception:
            pass

    return {"message": "If an unverified account exists with this email, a verification link has been sent."}


# ---------------------------------------------------------
# REGISTRATION ENDPOINT
# ---------------------------------------------------------
@router.post("/register", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    """
    Registers a new user in the system.
    Hashes their password securely before saving to PostgreSQL.
    """
    # 1. Check if a user with this email already exists
    if db.query(models.User).filter(models.User.email == user.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="A user with this email is already registered."
        )

    # 2. Check if the username is already taken
    if db.query(models.User).filter(models.User.username == user.username).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="This username is already taken. Please choose another."
        )

    # 2b. [FEATURE] Reject addresses Verifalia positively confirms as
    # undeliverable (typo'd domains, non-existent mailboxes, etc). This
    # fails open — see email_verification_service.py — so a Verifalia
    # outage or missing API credentials never blocks signup.
    deliverability = check_email_deliverability(user.email)
    if deliverability["checked"] and not deliverability["deliverable"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This email address doesn't look reachable. Please double-check it or use a different one.",
        )

    # 3. Hash the plain text password
    hashed_password = security.get_password_hash(user.password)

    # [PROJECT REFACTOR] Combine firstName + lastName into full_name
    full_name = f"{user.first_name} {user.last_name or ''}".strip()

    # 4. Create the new user record with all fields
    new_user = models.User(
        email=user.email,
        username=user.username,
        full_name=full_name,
        hashed_password=hashed_password
    )

    # 5. Save to database
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # 6. [FEATURE] Best-effort welcome email — failure here must never fail
    # the registration itself (email_service already fails soft internally,
    # but the call is wrapped here too as defense in depth).
    try:
        email_service.send_welcome_email(new_user.email, new_user.full_name)
    except Exception:
        pass

    # 6b. [MERGED from fyp_SLM--AI-Improved-Updated] Kick off email
    # verification too. Best-effort, same reasoning as the welcome email —
    # the account exists either way; the user can always hit
    # /auth/resend-verification if this particular send fails.
    try:
        token = str(uuid.uuid4())
        _redis.setex(f"verify_token:{token}", _VERIFY_TTL_SECONDS, str(new_user.id))
        email_service.send_verification_email(new_user.email, token)
    except Exception:
        pass

    return new_user


# ---------------------------------------------------------
# LOGIN ENDPOINT (JWT GENERATION)
# [PROJECT REFACTOR] Returns user object alongside token (Mismatch 2 fix)
# ---------------------------------------------------------
@router.post("/login", response_model=schemas.TokenWithUser)
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(), 
    db: Session = Depends(get_db)
):
    """
    Authenticates a user and returns a JSON Web Token (JWT) + user profile.
    Allows the user to log in using EITHER their email OR their username.
    """
    # 0. [NEXT_STEPS.md #2] Rate-limit before touching the DB or verifying a
    # password: nothing previously stopped repeated password guesses against
    # one account. Counts every attempt (success or failure) toward the cap;
    # a successful login clears the counter below so normal users who
    # mistyped once or twice aren't left partway to a lockout.
    check_rate_limit(f"login:{form_data.username.strip().lower()}", LOGIN_ATTEMPT_LIMIT, LOGIN_ATTEMPT_WINDOW_SECONDS)

    # 1. Check if the form input matches EITHER the email OR the username column
    user = db.query(models.User).filter(
        or_(
            models.User.email == form_data.username,
            models.User.username == form_data.username
        )
    ).first()

    # 2. [FIX] Distinct messages for "no such account" vs "wrong password",
    # per explicit request, instead of one generic "incorrect email/username
    # or password" for both.
    #
    # Trade-off worth knowing about: returning different messages for these
    # two cases lets an attacker enumerate which emails/usernames have
    # accounts on this system (submit a password, see whether the error says
    # "no account" or "wrong password"). That's a real, standard security
    # concern for production auth systems — the previous single generic
    # message avoided it. For a small-scale app where UX clarity matters
    # more than resisting enumeration, distinct messages are usually fine;
    # if this becomes a public product handling sensitive data, switch back
    # to one generic message for both branches below.
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No account found with that email or username.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not security.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. Check if the account is active
    if not user.is_active:
         raise HTTPException(status_code=400, detail="Inactive user account.")

    # 3b. [NEXT_STEPS.md #2] Credentials verified — clear the attempt
    # counter so it doesn't carry over into the next login window.
    reset_rate_limit(f"login:{form_data.username.strip().lower()}")

    # 4. Generate the JWT token using the dynamic config value
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES) 
    access_token = security.create_access_token(
        data={"sub": user.email}, 
        expires_delta=access_token_expires
    )

    # 4b. [FEATURE] Issue a long-lived refresh token alongside the access
    # token, so the frontend can silently get a new access token instead of
    # logging the user out when ACCESS_TOKEN_EXPIRE_MINUTES elapses.
    refresh_token = security.generate_refresh_token()
    db.add(models.RefreshToken(
        user_id=user.id,
        token_hash=security.hash_refresh_token(refresh_token),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    ))
    db.commit()

    # 4c. [FEATURE] Best-effort login notification email.
    try:
        email_service.send_login_notification_email(user.email, user.full_name)
    except Exception:
        pass

    # 5. Return token + user profile (frontend expects user object in login response)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": schemas.UserResponse.model_validate(user)
    }


# ---------------------------------------------------------
# REFRESH — exchanges a valid, unexpired, unrevoked refresh token for a new
# access token. Rotates the refresh token on every use (old row deleted, new
# one issued) so a stolen-but-unused token has only a single-use window.
# Does not touch how the access token itself is issued/verified elsewhere.
# ---------------------------------------------------------
@router.post("/refresh", response_model=schemas.RefreshTokenResponse)
def refresh_access_token(payload: schemas.RefreshTokenRequest, db: Session = Depends(get_db)):
    token_hash = security.hash_refresh_token(payload.refresh_token)

    stored = (
        db.query(models.RefreshToken)
        .filter(
            models.RefreshToken.token_hash == token_hash,
            models.RefreshToken.revoked == False,  # noqa: E712
        )
        .first()
    )

    invalid_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token.",
    )

    if not stored:
        raise invalid_exception

    expires_at = stored.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise invalid_exception

    user = db.query(models.User).filter(models.User.id == stored.user_id).first()
    if not user or not user.is_active:
        raise invalid_exception

    # Rotate: revoke the used token, issue a fresh one
    stored.revoked = True
    new_refresh_token = security.generate_refresh_token()
    db.add(models.RefreshToken(
        user_id=user.id,
        token_hash=security.hash_refresh_token(new_refresh_token),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    ))
    db.commit()

    new_access_token = security.create_access_token(
        data={"sub": user.email},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
    }


# ---------------------------------------------------------
# LOGOUT — revokes the refresh token so it can't be used again. Best-effort:
# the frontend clears its local tokens regardless of whether this succeeds.
# ---------------------------------------------------------
@router.post("/logout")
def logout(payload: schemas.RefreshTokenRequest, db: Session = Depends(get_db)):
    token_hash = security.hash_refresh_token(payload.refresh_token)
    db.query(models.RefreshToken).filter(
        models.RefreshToken.token_hash == token_hash
    ).update({"revoked": True})
    db.commit()
    return {"message": "Logged out."}


# ---------------------------------------------------------
# FORGOT PASSWORD — generates a 6-digit code, emails it, stores it (hashed
# not required here since it's short-lived and single-use — see reset step).
# Always returns the same generic response regardless of whether the email
# exists, specifically to avoid leaking registered emails through this
# particular endpoint (unlike the login/signup trade-off above, there's no
# UX upside to being specific here — the user just wants "check your inbox").
# ---------------------------------------------------------
@router.post("/forgot-password")
def forgot_password(payload: schemas.ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == payload.email).first()

    if user:
        code = "".join(random.choices(string.digits, k=6))
        reset_code = models.PasswordResetCode(
            user_id=user.id,
            code=code,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=RESET_CODE_TTL_MINUTES),
        )
        db.add(reset_code)
        db.commit()

        # [NEXT_STEPS.md #2] A fresh code means a fresh set of attempts —
        # otherwise a user who got rate-limited on an old/expired code would
        # stay locked out even after correctly requesting a new one.
        reset_rate_limit(f"password_reset:{payload.email.strip().lower()}")

        try:
            email_service.send_password_reset_code_email(user.email, code)
        except Exception:
            pass

    return {"message": "If an account with that email exists, a reset code has been sent."}


# ---------------------------------------------------------
# RESET PASSWORD — exchanges a valid, unused, unexpired code for a new
# password. The code is marked used immediately on success so it can't be
# replayed.
# ---------------------------------------------------------
@router.post("/reset-password")
def reset_password(payload: schemas.ResetPasswordRequest, db: Session = Depends(get_db)):
    # [NEXT_STEPS.md #2] The 6-digit code is a 1-in-a-million guess per try,
    # brute-forceable well within its 15-minute window with no cap. 5
    # attempts per email per window, window length matching the code's own
    # TTL so a lockout and a code expiry line up.
    check_rate_limit(
        f"password_reset:{payload.email.strip().lower()}",
        RESET_ATTEMPT_LIMIT,
        RESET_CODE_TTL_MINUTES * 60,
    )

    user = db.query(models.User).filter(models.User.email == payload.email).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired code.")

    reset_code = (
        db.query(models.PasswordResetCode)
        .filter(
            models.PasswordResetCode.user_id == user.id,
            models.PasswordResetCode.code == payload.code,
            models.PasswordResetCode.used == False,  # noqa: E712
        )
        .order_by(models.PasswordResetCode.created_at.desc())
        .first()
    )

    if not reset_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired code.")

    expires_at = reset_code.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired code.")

    user.hashed_password = security.get_password_hash(payload.new_password)
    reset_code.used = True
    db.commit()

    # [NEXT_STEPS.md #2] Successful reset — clear the attempt counter.
    reset_rate_limit(f"password_reset:{payload.email.strip().lower()}")

    return {"message": "Password has been reset successfully."}