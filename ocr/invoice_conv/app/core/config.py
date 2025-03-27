from pydantic_settings import BaseSettings
from typing import Optional, Dict, Any, List
from pydantic import field_validator
import secrets
import os
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env')
load_dotenv(env_path)


class Settings(BaseSettings):
    PROJECT_NAME: str = "InvoiceScan"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = secrets.token_urlsafe(32)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days
    
    # Database
    DATABASE_URL: str = "sqlite:///./sql_app.db"
    
    # OpenAI
    OPENAI_API_KEY: str
    
    # Debug and testing flags
    INVOICE_TEST_MODE: bool = os.getenv("INVOICE_TEST_MODE", "false").lower() == "true"
    DEBUG_MODE: bool = os.getenv("DEBUG_MODE", "false").lower() == "true"
    
    # Google OAuth
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    
    # Stripe keys
    STRIPE_SECRET_KEY: Optional[str] = None
    STRIPE_PUBLISHABLE_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None
    
    # Pricing tiers
    FREE_TIER_SCANS: int = 5
    BASIC_TIER_SCANS: int = 50
    PRO_TIER_SCANS: int = 200
    ENTERPRISE_TIER_SCANS: int = 1000
    
    # Allowed CORS origins
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:8000", "http://localhost", "http://localhost:3000"]
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
