import os
import sys

# Add the current directory to path to allow importing app modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.user import User
from app.models.subscription import Subscription
from app.core.security import get_password_hash
import uuid

def create_demo_user(db: Session):
    # Check if demo user already exists
    demo_user = db.query(User).filter(User.email == "demo@example.com").first()
    
    if demo_user:
        print("Demo user already exists")
        return demo_user
    
    # Create demo user
    demo_user = User(
        id=str(uuid.uuid4()),
        email="demo@example.com",
        hashed_password=get_password_hash("password"),
        first_name="Demo",
        last_name="User",
        is_superuser=False,
        is_active=True
    )
    
    db.add(demo_user)
    db.commit()
    db.refresh(demo_user)
    
    # Create default subscription for demo user
    demo_subscription = Subscription(
        user_id=demo_user.id,
        tier="pro",  # Give them a higher tier for testing
        status="active",
        monthly_scans=50,
        scans_used=0
    )
    
    db.add(demo_subscription)
    db.commit()
    
    print(f"Created demo user with ID: {demo_user.id}")
    print("Email: demo@example.com")
    print("Password: password")
    return demo_user

if __name__ == "__main__":
    db = SessionLocal()
    try:
        create_demo_user(db)
    finally:
        db.close()