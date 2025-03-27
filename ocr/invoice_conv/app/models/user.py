import uuid
from sqlalchemy import Boolean, Column, String, DateTime, ForeignKey, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import datetime

from app.db.session import Base


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=True)  # Nullable for social auth
    first_name = Column(String, index=True)
    last_name = Column(String, index=True)
    is_active = Column(Boolean(), default=True)
    is_superuser = Column(Boolean(), default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    
    # Google OAuth info
    google_id = Column(String, nullable=True, unique=True)
    avatar_url = Column(String, nullable=True)
    
    # Relationships
    subscription = relationship("Subscription", back_populates="user", uselist=False)
    scans = relationship("Scan", back_populates="user")
