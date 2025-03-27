import os
import sys
import sqlite3
from datetime import datetime
import uuid
import hashlib

# Set up the database path
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sql_app.db')

def hash_password(password):
    """Create a simple hash of the password (not secure, just for testing)"""
    # In production, you should use a proper password hashing library like bcrypt
    # This is just for testing purposes
    return "$2b$12$" + hashlib.sha256(password.encode()).hexdigest()

def create_tables():
    """Create necessary tables if they don't exist"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create users table if not exists
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        email TEXT UNIQUE NOT NULL,
        hashed_password TEXT,
        first_name TEXT,
        last_name TEXT,
        is_active BOOLEAN DEFAULT 1,
        is_superuser BOOLEAN DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_login TIMESTAMP,
        google_id TEXT UNIQUE,
        avatar_url TEXT
    )
    ''')
    
    # Create subscription table if not exists
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS subscriptions (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        tier TEXT NOT NULL,
        status TEXT NOT NULL,
        monthly_scans INTEGER NOT NULL,
        scans_used INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expires_at TIMESTAMP,
        stripe_customer_id TEXT,
        stripe_subscription_id TEXT,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')
    
    # Create scans table if not exists
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS scans (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        original_filename TEXT NOT NULL,
        uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        processed_at TIMESTAMP,
        status TEXT DEFAULT "pending",
        result_data JSON,  -- Change to JSON type for SQLAlchemy compatibility
        file_path TEXT,
        page_count INTEGER,
        error TEXT,
        processing_time REAL,
        extracted_text TEXT,
        invoice_number TEXT,
        invoice_date TEXT,
        vendor TEXT,
        invoice_total REAL,
        invoice_currency TEXT,
        invoice_status TEXT,
        campaigns TEXT,
        campaigns_duration JSON,  -- Change to JSON type for SQLAlchemy compatibility
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')
    
    # Create uploads directory if it doesn't exist
    uploads_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
    if not os.path.exists(uploads_dir):
        os.makedirs(uploads_dir)
    
    conn.commit()
    conn.close()
    print("Tables created successfully")

def create_demo_user():
    """Create a demo user for testing"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if demo user exists
    cursor.execute("SELECT id FROM users WHERE email = ?", ("demo@example.com",))
    existing_user = cursor.fetchone()
    
    if existing_user:
        user_id = existing_user[0]
        print(f"Demo user already exists with ID: {user_id}")
    else:
        # Create new user
        user_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        
        cursor.execute('''
        INSERT INTO users (id, email, hashed_password, first_name, last_name, is_active, is_superuser, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, "demo@example.com", hash_password("password"), "Demo", "User", True, False, now))
        
        print(f"Created demo user with ID: {user_id}")
    
    # Check if user has a subscription
    cursor.execute("SELECT id FROM subscriptions WHERE user_id = ?", (user_id,))
    existing_sub = cursor.fetchone()
    
    if not existing_sub:
        # Create subscription
        sub_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        
        cursor.execute('''
        INSERT INTO subscriptions (id, user_id, tier, status, monthly_scans, scans_used, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (sub_id, user_id, "pro", "active", 50, 0, now))
        
        print(f"Created subscription for demo user")
    
    # Make sure user directory exists
    user_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads', user_id)
    if not os.path.exists(user_dir):
        os.makedirs(user_dir)
        print(f"Created user directory: {user_dir}")
    
    conn.commit()
    
    # Show user credentials
    print("\nDemo User Credentials:")
    print("Email: demo@example.com")
    print("Password: password")
    
    conn.close()

if __name__ == "__main__":
    try:
        create_tables()
        create_demo_user()
        print("\nSetup completed successfully")
    except Exception as e:
        print(f"Error: {str(e)}")