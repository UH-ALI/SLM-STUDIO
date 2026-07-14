from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.core.config import settings

# ---------------------------------------------------------
# OAUTH2 SCHEME SETUP
# ---------------------------------------------------------
# This points FastAPI to the exact URL where it can get the token.
# Crucially, this is what makes the "Authorize" padlock button 
# in the Swagger UI work automatically!
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


# ---------------------------------------------------------
# DEPENDENCY INJECTION FUNCTION
# ---------------------------------------------------------
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """
    Decodes the JWT token, verifies the user exists, and returns the User model.
    Inject this into any router endpoint that needs to be secured.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # 1. Decode the token using our secret key
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

        
        # 2. Extract the 'sub' (subject) which we set as the user's email
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
            
        # 3. Validate the payload using our Pydantic schema
        token_data = schemas.TokenData(email=email)
        
    except JWTError:
        # If the token is expired, tampered with, or invalid
        raise credentials_exception
        
    # 4. Fetch the actual user record from PostgreSQL
    user = db.query(models.User).filter(models.User.email == token_data.email).first()
    if user is None:
        raise credentials_exception
        
    # 5. Security check: Ensure the account hasn't been suspended
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user account")
        
    return user