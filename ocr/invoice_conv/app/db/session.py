import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import sqlite3

from app.core.config import settings

# Make sure SQLite connection allows writes
connect_args = {
    "check_same_thread": False,
    "uri": True  # Use URI mode to specify additional parameters
}

# Add this for compatibility with SQLite
# Make sure we're not using a read-only connection
database_url = settings.DATABASE_URL
if database_url.startswith('sqlite'):
    # Convert to URI format if not already
    if not database_url.startswith('sqlite:///'):
        database_url = f"sqlite:///{database_url}"
    
    # Add mode=rwc to create database if it doesn't exist and allow writes
    if '?' not in database_url:
        database_url += "?mode=rwc"
    else:
        database_url += "&mode=rwc"

engine = create_engine(database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
