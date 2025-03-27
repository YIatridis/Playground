from typing import Optional, List, Dict, Any

from sqlalchemy.orm import Session

from app.models.user import User
from app.models.subscription import Subscription
from app.schemas.user import UserCreate, UserCreateOAuth, UserUpdate
from app.core.security import get_password_hash, verify_password


def get_user(db: Session, user_id: str) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email).first()


def get_user_by_google_id(db: Session, google_id: str) -> Optional[User]:
    return db.query(User).filter(User.google_id == google_id).first()


def get_users(db: Session, skip: int = 0, limit: int = 100) -> List[User]:
    return db.query(User).offset(skip).limit(limit).all()


def create_user(db: Session, user_in: UserCreate) -> User:
    db_user = User(
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        first_name=user_in.first_name,
        last_name=user_in.last_name,
        is_superuser=False,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    # Create default subscription for new user
    default_subscription = Subscription(
        user_id=db_user.id,
        tier="free",
        status="active",
        monthly_scans=5,  # Default free tier
    )
    db.add(default_subscription)
    db.commit()
    
    return db_user


def create_user_oauth(db: Session, user_in: UserCreateOAuth) -> User:
    db_user = User(
        email=user_in.email,
        first_name=user_in.first_name,
        last_name=user_in.last_name,
        is_superuser=False,
        google_id=user_in.google_id,
        avatar_url=user_in.avatar_url,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    # Create default subscription for new user
    default_subscription = Subscription(
        user_id=db_user.id,
        tier="free",
        status="active",
        monthly_scans=5,  # Default free tier
    )
    db.add(default_subscription)
    db.commit()
    
    return db_user


def update_user(db: Session, user: User, user_in: UserUpdate) -> User:
    update_data = user_in.model_dump(exclude_unset=True)
    
    if "password" in update_data and update_data["password"]:
        update_data["hashed_password"] = get_password_hash(update_data["password"])
        del update_data["password"]
    
    for field, value in update_data.items():
        setattr(user, field, value)
    
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    user = get_user_by_email(db, email=email)
    if not user or user.hashed_password is None:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def is_active(user: User) -> bool:
    return user.is_active


def is_superuser(user: User) -> bool:
    return user.is_superuser
