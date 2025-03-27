from typing import Optional, List, Any, Dict, Union
from pydantic import BaseModel, Field
from datetime import datetime


class ScanBase(BaseModel):
    original_filename: str


class ScanCreate(ScanBase):
    user_id: str
    file_path: str


class ScanBasic(ScanBase):
    id: str
    status: str
    uploaded_at: datetime
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    vendor: Optional[str] = None
    invoice_total: Optional[float] = None
    invoice_currency: Optional[str] = None

    class Config:
        from_attributes = True


class ScanOut(ScanBasic):
    processed_at: Optional[datetime] = None
    page_count: Optional[int] = None
    processing_time: Optional[float] = None
    invoice_status: Optional[str] = None
    campaigns: Optional[str] = None
    campaigns_duration: Optional[Union[List[str], str]] = None  # Can be either a list or a JSON string
    error: Optional[str] = None
    
    class Config:
        from_attributes = True
    
    # Add model validator to parse JSON strings
    def model_post_init(self, __context):
        # If campaigns_duration is a JSON string, parse it
        if isinstance(self.campaigns_duration, str):
            try:
                import json
                self.campaigns_duration = json.loads(self.campaigns_duration)
            except (json.JSONDecodeError, ValueError):
                # If it can't be parsed, keep as is
                pass


class ScanUpdate(BaseModel):
    status: Optional[str] = None
    processed_at: Optional[datetime] = None
    result_data: Optional[str] = None  # Stored as a JSON string
    page_count: Optional[int] = None
    error: Optional[str] = None
    processing_time: Optional[float] = None
    extracted_text: Optional[str] = None
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    vendor: Optional[str] = None
    invoice_total: Optional[float] = None
    invoice_currency: Optional[str] = None
    invoice_status: Optional[str] = None
    campaigns: Optional[str] = None
    campaigns_duration: Optional[Union[List[str], str]] = None  # Can be either a list or a JSON string
    
    # Add model validator
    def model_post_init(self, __context):
        # If campaigns_duration is a list, convert to JSON string
        if isinstance(self.campaigns_duration, list):
            import json
            self.campaigns_duration = json.dumps(self.campaigns_duration)
