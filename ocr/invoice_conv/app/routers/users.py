from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user, get_current_active_superuser
from app.services import user as user_service
from app.schemas.user import User, UserUpdate, UserWithSubscription, UserWithScans, UserFull


router = APIRouter()


@router.get("/me", response_model=User)
def get_current_user_info(
    current_user: User = Depends(get_current_user),
) -> Any:
    """Get current user info."""
    return current_user


@router.get("/me/full", response_model=UserFull)
def get_current_user_full(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Get current user with subscription and recent scans."""
    user = db.query(User).filter(User.id == current_user.id)\
        .options(
            orm.joinedload(User.subscription),
            orm.joinedload(User.scans).order_by(Scan.uploaded_at.desc()).limit(5)
        ).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return user


@router.get("/me/subscription", response_model=UserWithSubscription)
def get_current_user_subscription(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Get current user with subscription info."""
    user = db.query(User).filter(User.id == current_user.id)\
        .options(orm.joinedload(User.subscription)).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return user


@router.put("/me", response_model=User)
def update_current_user(
    *,
    db: Session = Depends(get_db),
    user_in: UserUpdate,
    current_user: User = Depends(get_current_user),
) -> Any:
    """Update current user."""
    user = user_service.update_user(db, current_user, user_in)
    return user


@router.get("/", response_model=List[User])
def get_users(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_superuser),
) -> Any:
    """Get all users. Only accessible by superusers."""
    users = user_service.get_users(db, skip=skip, limit=limit)
    return users


@router.get("/{user_id}", response_model=User)
def get_user_by_id(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
) -> Any:
    """Get a specific user by id. Only accessible by superusers."""
    user = user_service.get_user(db, user_id=user_id)
    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )
    return user
