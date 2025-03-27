import uuid
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime, timedelta

from app.db.session import Base


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, unique=True)
    tier = Column(String, nullable=False, default="free")  # free, basic, pro, enterprise
    status = Column(String, nullable=False, default="active")  # active, cancelled, pastdue
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    monthly_scans = Column(Integer, default=5)  # Default to free tier scans
    scans_used = Column(Integer, default=0)
    
    # Stripe related fields
    stripe_customer_id = Column(String, nullable=True)
    stripe_subscription_id = Column(String, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="subscription")
    
    @property
    def is_active(self):
        if self.expires_at is None:
            return True
        return datetime.utcnow() < self.expires_at
    
    @property
    def scans_remaining(self):
        return max(0, self.monthly_scans - self.scans_used)
