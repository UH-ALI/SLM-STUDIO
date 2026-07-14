from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
from jose import jwt
# Notice: os and dotenv are no longer needed here!
from app.core.config import settings 
# Initialize the password hashing context using Bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
# ---------------------------------------------------------
# PASSWORD CRYPTOGRAPHY
# ---------------------------------------------------------
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Takes a plain text password, hashes it, and compares it to the hash in the database.
    """
    return pwd_context.verify(plain_password, hashed_password)
def get_password_hash(password: str) -> str:
    """
    Takes a plain text password and securely hashes it using Bcrypt.
    """
    return pwd_context.hash(password)
# ---------------------------------------------------------
# JSON WEB TOKEN (JWT) GENERATION
# ---------------------------------------------------------
def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """
    Creates a stateless JWT containing the user's identity (email) and an expiration time.
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        # Using the Pydantic settings attribute (already an int!)
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})

    # Securely sign the token using Pydantic settings attributes
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    return encoded_jwt