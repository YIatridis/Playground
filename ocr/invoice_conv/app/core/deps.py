import os
from typing import Generator, Optional

from fastapi import Depends, HTTPException, status, Header, Request
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session
import uuid

from app.core.config import settings
from app.core.security import DEFAULT_JWT_ALGORITHM
from app.db.session import SessionLocal
from app.models.user import User


oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login", auto_error=False)

# Debug mode is controlled via settings.DEBUG_MODE from app.core.config


def get_db() -> Generator[Session, None, None]:
    try:
        db = SessionLocal()
        yield db
    finally:
        db.close()


def get_demo_user(db: Session) -> User:
    """Get or create a demo user for debugging."""
    demo_user = db.query(User).filter(User.email == "demo@example.com").first()
    
    if not demo_user:
        # Create a new demo user if one doesn't exist
        from app.core.security import get_password_hash
        import datetime
        
        user_id = str(uuid.uuid4())
        demo_user = User(
            id=user_id,
            email="demo@example.com",
            hashed_password=get_password_hash("password"),
            first_name="Demo",
            last_name="User",
            is_superuser=False,
            is_active=True
        )
        db.add(demo_user)
        
        try:
            db.commit()
            db.refresh(demo_user)
            
            # Also create a subscription for this user
            from app.models.subscription import Subscription
            
            # Check if subscription already exists
            sub = db.query(Subscription).filter(Subscription.user_id == user_id).first()
            if not sub:
                sub = Subscription(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    tier="pro",
                    status="active",
                    monthly_scans=50,
                    scans_used=0,
                    created_at=datetime.datetime.utcnow(),
                    stripe_customer_id="demo_customer",
                    stripe_subscription_id="demo_subscription"
                )
                db.add(sub)
                db.commit()
                print(f"Created subscription for demo user: {user_id}")
                
        except Exception as e:
            db.rollback()
            print(f"Error creating demo user: {str(e)}")
            
            # If we can't create a user, try to find an existing one
            all_users = db.query(User).all()
            if all_users:
                return all_users[0]
            
    # Make sure user has a subscription
    from app.models.subscription import Subscription
    
    sub = db.query(Subscription).filter(Subscription.user_id == demo_user.id).first()
    if not sub:
        try:
            import datetime
            sub = Subscription(
                id=str(uuid.uuid4()),
                user_id=demo_user.id,
                tier="pro",
                status="active",
                monthly_scans=50,
                scans_used=0,
                created_at=datetime.datetime.utcnow(),
                stripe_customer_id="demo_customer",
                stripe_subscription_id="demo_subscription"
            )
            db.add(sub)
            db.commit()
            print(f"Added missing subscription for existing demo user: {demo_user.id}")
        except Exception as e:
            db.rollback()
            print(f"Error creating subscription: {str(e)}")
            
    return demo_user


async def get_current_user(
    db: Session = Depends(get_db), 
    token: Optional[str] = Depends(oauth2_scheme),
    x_debug: Optional[str] = Header(None)
) -> User:
    """Get the current user from the token or use a demo user in debug mode."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # For debugging - if settings.DEBUG_MODE is True or X-Debug header is present, use demo user
    from app.core.config import settings
    if settings.DEBUG_MODE or x_debug == "true":
        return get_demo_user(db)
        
    if not token:
        raise credentials_exception
        
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[DEFAULT_JWT_ALGORITHM]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
        
    return user


def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


def get_current_active_superuser(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )
    return current_user
