from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.subscription import Subscription
from app.schemas.subscription import SubscriptionCreate, SubscriptionUpdate


def get_subscription(db: Session, subscription_id: str) -> Optional[Subscription]:
    return db.query(Subscription).filter(Subscription.id == subscription_id).first()


def get_user_subscription(db: Session, user_id: str) -> Optional[Subscription]:
    return db.query(Subscription).filter(Subscription.user_id == user_id).first()


def create_subscription(db: Session, subscription_in: SubscriptionCreate) -> Subscription:
    # Set monthly scans based on tier
    monthly_scans = subscription_in.monthly_scans
    if subscription_in.tier == "basic":
        monthly_scans = 50
    elif subscription_in.tier == "pro":
        monthly_scans = 200
    elif subscription_in.tier == "enterprise":
        monthly_scans = 1000
    
    # Create subscription
    db_subscription = Subscription(
        user_id=subscription_in.user_id,
        tier=subscription_in.tier,
        status=subscription_in.status,
        monthly_scans=monthly_scans,
        expires_at=subscription_in.expires_at,
        stripe_customer_id=subscription_in.stripe_customer_id,
        stripe_subscription_id=subscription_in.stripe_subscription_id,
    )
    db.add(db_subscription)
    db.commit()
    db.refresh(db_subscription)
    return db_subscription


def update_subscription(db: Session, subscription: Subscription, subscription_in: SubscriptionUpdate) -> Subscription:
    update_data = subscription_in.model_dump(exclude_unset=True)
    
    # Update monthly scans if tier is changing
    if "tier" in update_data:
        if update_data["tier"] == "free":
            update_data["monthly_scans"] = 5
        elif update_data["tier"] == "basic":
            update_data["monthly_scans"] = 50
        elif update_data["tier"] == "pro":
            update_data["monthly_scans"] = 200
        elif update_data["tier"] == "enterprise":
            update_data["monthly_scans"] = 1000
    
    for field, value in update_data.items():
        setattr(subscription, field, value)
    
    db.add(subscription)
    db.commit()
    db.refresh(subscription)
    return subscription


def increment_scan_usage(db: Session, user_id: str) -> bool:
    """Increment scan usage for a user. Returns True if successful, False if quota exceeded."""
    subscription = get_user_subscription(db, user_id)
    if not subscription:
        return False
    
    if subscription.scans_used >= subscription.monthly_scans:
        return False  # Quota exceeded
    
    subscription.scans_used += 1
    db.add(subscription)
    db.commit()
    return True


def reset_monthly_usage(db: Session) -> int:
    """Reset monthly usage for all active subscriptions. Returns number of reset subscriptions."""
    reset_count = 0
    subscriptions = db.query(Subscription).filter(Subscription.status == "active").all()
    
    for subscription in subscriptions:
        subscription.scans_used = 0
        db.add(subscription)
        reset_count += 1
    
    db.commit()
    return reset_count
