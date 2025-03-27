from typing import Any, List
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user
from app.core.security import create_access_token
from app.services import user as user_service
from app.schemas.user import User, UserCreate, Token, UserCreateOAuth


router = APIRouter()


@router.post("/login", response_model=Token)
def login_access_token(
    db: Session = Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends()
) -> Any:
    """OAuth2 compatible token login, get an access token for future requests."""
    user = user_service.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    elif not user_service.is_active(user):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user"
        )
    
    # Update last login time
    user.last_login = datetime.utcnow()
    db.add(user)
    db.commit()
    
    return {
        "access_token": create_access_token(user.id),
        "token_type": "bearer",
    }


@router.post("/register", response_model=User, status_code=status.HTTP_201_CREATED)
def register_user(*, db: Session = Depends(get_db), user_in: UserCreate) -> Any:
    """Register a new user."""
    # Check if user already exists
    user = user_service.get_user_by_email(db, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    
    # Create new user
    user = user_service.create_user(db, user_in)
    
    return user


@router.post("/google-login", response_model=Token)
def google_login(
    *, db: Session = Depends(get_db), token_info: dict
) -> Any:
    """Login with Google OAuth token."""
    # In a real implementation, verify the token with Google
    # For this PoC, we'll just assume it's valid and contains user info
    
    # Check if user exists by Google ID
    google_id = token_info.get("sub")
    if not google_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid token",
        )
    
    user = user_service.get_user_by_google_id(db, google_id=google_id)
    
    # If user doesn't exist, create a new one
    if not user:
        email = token_info.get("email")
        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email not provided in token",
            )
        
        # Check if user exists by email
        existing_user = user_service.get_user_by_email(db, email=email)
        if existing_user:
            # Link existing account to Google ID
            existing_user.google_id = google_id
            existing_user.avatar_url = token_info.get("picture")
            db.add(existing_user)
            db.commit()
            db.refresh(existing_user)
            user = existing_user
        else:
            # Create new user
            user_data = UserCreateOAuth(
                email=email,
                first_name=token_info.get("given_name", ""),
                last_name=token_info.get("family_name", ""),
                google_id=google_id,
                avatar_url=token_info.get("picture"),
            )
            user = user_service.create_user_oauth(db, user_data)
    
    # Update last login time
    user.last_login = datetime.utcnow()
    db.add(user)
    db.commit()
    
    return {
        "access_token": create_access_token(user.id),
        "token_type": "bearer",
    }


@router.post("/logout")
def logout(
    response: Response, current_user: User = Depends(get_current_user)
) -> Any:
    """Logout current user."""
    # In a stateless JWT auth system, we can't invalidate tokens server-side
    # In a real app, you might want to use a token blacklist or shorter token expiry
    
    # Clear cookies if they're being used
    response.delete_cookie("access_token")
    
    return {"success": True}
