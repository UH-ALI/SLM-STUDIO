from fastapi import APIRouter, Depends
from app import models, schemas

# Kept intact: This dependency handles the heavy lifting of parsing the JWT 
from app.core.deps import get_current_user

router = APIRouter()

@router.get("/me", response_model=schemas.UserResponse)
def read_users_me(current_user: models.User = Depends(get_current_user)):
    """
    Fetches the profile details of the currently logged-in user.
    The frontend calls this using the JWT token to populate the dashboard UI.
    """
    # The bouncer already verified the token and fetched the user from the database.
    # We just hand the user object straight back to Pydantic to format as JSON!
    return current_user