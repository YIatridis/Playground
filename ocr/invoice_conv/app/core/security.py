from datetime import datetime, timedelta
from typing import Any, Union, Optional
import hashlib

from jose import jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


DEFAULT_JWT_ALGORITHM = "HS256"


def create_access_token(
    subject: Union[str, Any], expires_delta: Optional[timedelta] = None
) -> str:
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=DEFAULT_JWT_ALGORITHM)
    return encoded_jwt


def verify_password(plain_password: str, hashed_password: str) -> bool:
    # If we're using our debug hashed passwords with the "$2b$12$" prefix and sha256
    if hashed_password.startswith("$2b$12$"):
        # Split off the prefix
        actual_hash = hashed_password[7:]
        # Compute the hash of the plain password
        computed_hash = hashlib.sha256(plain_password.encode()).hexdigest()
        # Compare the hashes
        return actual_hash == computed_hash
    else:
        # Fall back to bcrypt for normally hashed passwords
        return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)
