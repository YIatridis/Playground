import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Float, JSON, Boolean, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from datetime import datetime

from app.db.session import Base


class Scan(Base):
    __tablename__ = "scans"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    original_filename = Column(String, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
    status = Column(String, default="pending")  # pending, processing, completed, failed
    result_data = Column(String, nullable=True)  # Store as string in SQLite
    file_path = Column(String, nullable=True)  # Path to the stored file
    page_count = Column(Integer, nullable=True)  # Number of pages in the document
    error = Column(String, nullable=True)  # Error message if processing failed
    processing_time = Column(Float, nullable=True)  # Time taken to process in seconds
    extracted_text = Column(String, nullable=True)  # Raw text extracted from PDF
    
    # Invoice specific fields
    invoice_number = Column(String, nullable=True)
    invoice_date = Column(String, nullable=True)
    vendor = Column(String, nullable=True)
    invoice_total = Column(Float, nullable=True)
    invoice_currency = Column(String, nullable=True)
    invoice_status = Column(String, nullable=True)
    campaigns = Column(String, nullable=True)
    campaigns_duration = Column(String, nullable=True)  # Stored as a JSON string in SQLite
    
    # Relationships
    user = relationship("User", back_populates="scans")
