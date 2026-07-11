from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app import models, schemas
from app.database import get_db
from app.core import security
# Import the instantiated settings singleton directly
from app.core.config import settings 

router = APIRouter()

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
    # 1. Check if the form input matches EITHER the email OR the username column
    user = db.query(models.User).filter(
        or_(
            models.User.email == form_data.username,
            models.User.username == form_data.username
        )
    ).first()

    # 2. Verify existence and check if password matches the hash
    if not user or not security.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email/username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. Check if the account is active
    if not user.is_active:
         raise HTTPException(status_code=400, detail="Inactive user account.")

    # 4. Generate the JWT token using the dynamic config value
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES) 
    access_token = security.create_access_token(
        data={"sub": user.email}, 
        expires_delta=access_token_expires
    )

    # 5. Return token + user profile (frontend expects user object in login response)
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": schemas.UserResponse.model_validate(user)
    }