from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime

from app.schemas.subscription import SubscriptionOut
from app.schemas.scan import ScanBasic


class UserBase(BaseModel):
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_active: bool = True


class UserCreate(UserBase):
    password: str


class UserCreateOAuth(UserBase):
    google_id: str
    avatar_url: Optional[str] = None


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    password: Optional[str] = None


class UserInDBBase(UserBase):
    id: str
    is_superuser: bool = False
    created_at: datetime
    last_login: Optional[datetime] = None
    google_id: Optional[str] = None
    avatar_url: Optional[str] = None

    class Config:
        from_attributes = True


class User(UserInDBBase):
    pass


class UserWithSubscription(UserInDBBase):
    subscription: Optional[SubscriptionOut] = None


class UserWithScans(UserInDBBase):
    scans: List[ScanBasic] = []


class UserFull(UserInDBBase):
    subscription: Optional[SubscriptionOut] = None
    scans: List[ScanBasic] = []


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: Optional[str] = None
