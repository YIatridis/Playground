from typing import Optional
from pydantic import BaseModel
from datetime import datetime


class SubscriptionBase(BaseModel):
    tier: str = "free"  # free, basic, pro, enterprise
    status: str = "active"  # active, cancelled, pastdue


class SubscriptionCreate(SubscriptionBase):
    user_id: str
    monthly_scans: int = 5
    expires_at: Optional[datetime] = None
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None


class SubscriptionUpdate(BaseModel):
    tier: Optional[str] = None
    status: Optional[str] = None
    monthly_scans: Optional[int] = None
    scans_used: Optional[int] = None
    expires_at: Optional[datetime] = None
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None


class SubscriptionOut(SubscriptionBase):
    id: str
    user_id: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    monthly_scans: int
    scans_used: int
    is_active: bool
    scans_remaining: int

    class Config:
        from_attributes = True
