import os
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid
import asyncio
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.scan import Scan
from app.schemas.scan import ScanCreate, ScanUpdate
from app.utils.vision_parse import VisionParser
from app.core.config import settings
from app.services.subscription import increment_scan_usage


def get_scan(db: Session, scan_id: str) -> Optional[Scan]:
    return db.query(Scan).filter(Scan.id == scan_id).first()


def get_user_scans(db: Session, user_id: str, skip: int = 0, limit: int = 100) -> List[Scan]:
    return db.query(Scan).filter(Scan.user_id == user_id).order_by(Scan.uploaded_at.desc()).offset(skip).limit(limit).all()


def create_scan(db: Session, scan_in: ScanCreate) -> Optional[Scan]:
    # First check if user has available scans
    if not increment_scan_usage(db, scan_in.user_id):
        return None  # User has exceeded their quota
    
    # Create scan record
    db_scan = Scan(
        user_id=scan_in.user_id,
        original_filename=scan_in.original_filename,
        file_path=scan_in.file_path,
        status="pending",
    )
    db.add(db_scan)
    db.commit()
    db.refresh(db_scan)
    return db_scan


def update_scan(db: Session, scan: Scan, scan_in: ScanUpdate) -> Scan:
    update_data = scan_in.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(scan, field, value)
    
    db.add(scan)
    db.commit()
    db.refresh(scan)
    return scan


async def process_scan(db: Session, scan_id: str) -> Optional[Scan]:
    """Process a scan using VisionParser and update the scan record."""
    # Get scan record
    scan = get_scan(db, scan_id)
    if not scan or not os.path.exists(scan.file_path):
        return None
    
    # Update status to processing
    scan.status = "processing"
    db.add(scan)
    db.commit()
    
    try:
        # Create VisionParser instance
        parser = VisionParser(
            model_name="gpt-4o-mini",
            api_key=settings.OPENAI_API_KEY,
            temperature=0.1,
            top_p=0.1,
            image_mode="none",
            detailed_extraction=True,
            enable_concurrency=True,
        )
        
        # Process PDF
        result = await parser.process_pdf(scan.file_path)
        
        # Create update data with proper handling for JSON serialization
        try:
            import json
            # Convert any complex objects to JSON strings
            result_data = {}
            for key, value in result.items():
                # Handle special cases for complex objects
                if key == "campaigns_duration" and isinstance(value, list):
                    # Store as JSON string
                    result_data[key] = json.dumps(value)
                else:
                    result_data[key] = value
            
            # Create the update - serialize result_data to JSON string for SQLite
            scan_update = ScanUpdate(
                status=result["status"],
                processed_at=datetime.utcnow(),
                result_data=json.dumps(result_data),  # Store as JSON string
                page_count=result.get("page_count"),
                error=result.get("error"),
                processing_time=result.get("processing_time"),
                extracted_text=result.get("extracted_text"),
            )
            
            # Add invoice fields if processing was successful
            if result["status"] == "completed":
                scan_update.invoice_number = result.get("invoice_number")
                scan_update.invoice_date = result.get("invoice_date")
                scan_update.vendor = result.get("vendor")
                
                # Handle invoice_total - ensure it's a float
                invoice_total = result.get("invoice_total")
                if isinstance(invoice_total, str):
                    try:
                        invoice_total = float(invoice_total.replace(',', ''))
                    except (ValueError, TypeError):
                        invoice_total = 0.0
                scan_update.invoice_total = invoice_total
                
                scan_update.invoice_currency = result.get("invoice_currency")
                scan_update.invoice_status = result.get("invoice_status")
                scan_update.campaigns = result.get("campaigns")
                
                # Handle campaigns_duration - ensure it's stored as a JSON string for SQLite
                campaigns_duration = result.get("campaigns_duration")
                if isinstance(campaigns_duration, str):
                    try:
                        # If it's already a JSON string, validate it by parsing and re-serializing
                        json_obj = json.loads(campaigns_duration)
                        if not isinstance(json_obj, list):
                            json_obj = [json_obj]
                        campaigns_duration = json.dumps(json_obj)
                    except json.JSONDecodeError:
                        # If it's not a valid JSON string, convert it to a single-item list
                        campaigns_duration = json.dumps([campaigns_duration])
                elif isinstance(campaigns_duration, list):
                    # It's already a list, just serialize it
                    campaigns_duration = json.dumps(campaigns_duration)
                elif campaigns_duration is not None:
                    # It's some other type, convert to string and make it a list
                    campaigns_duration = json.dumps([str(campaigns_duration)])
                else:
                    # It's None, use empty list
                    campaigns_duration = json.dumps([])
                
                scan_update.campaigns_duration = campaigns_duration
                
                # Log the data for debugging
                logfire.debug(f"Processing scan data: {scan_update.model_dump()}")
        except Exception as e:
            logfire.error(f"Error preparing scan update: {str(e)}")
            raise Exception(f"Failed to process scan results: {str(e)}")
        
        # Update scan
        updated_scan = update_scan(db, scan, scan_update)
        return updated_scan
        
    except Exception as e:
        # Update scan with error
        scan.status = "failed"
        scan.error = str(e)
        scan.processed_at = datetime.utcnow()
        db.add(scan)
        db.commit()
        db.refresh(scan)
        return scan


async def delete_scan_file(file_path: str) -> bool:
    """Delete scan file from disk."""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
        return True
    except Exception:
        return False


def delete_scan(db: Session, scan_id: str) -> bool:
    """Delete scan record and associated file."""
    scan = get_scan(db, scan_id)
    if not scan:
        return False
    
    # Delete file if it exists
    if scan.file_path and os.path.exists(scan.file_path):
        try:
            os.remove(scan.file_path)
        except Exception:
            pass  # Continue even if file deletion fails
    
    # Delete database record
    db.delete(scan)
    db.commit()
    return True


def export_scans(db: Session, user_id: str, format_type: str = "excel") -> Dict[str, Any]:
    """Export user scans to specified format."""
    # Get all user scans
    scans = get_user_scans(db, user_id, skip=0, limit=1000)
    
    # Prepare data for export
    data = [{
        "invoice_number": scan.invoice_number,
        "invoice_date": scan.invoice_date,
        "vendor": scan.vendor,
        "campaigns": scan.campaigns,
        "campaigns_duration": scan.campaigns_duration,
        "invoice_total": scan.invoice_total,
        "invoice_currency": scan.invoice_currency,
        "invoice_status": scan.invoice_status,
        "uploaded_at": scan.uploaded_at.isoformat() if scan.uploaded_at else None,
        "processed_at": scan.processed_at.isoformat() if scan.processed_at else None,
        "status": scan.status,
    } for scan in scans if scan.status == "completed"]
    
    # Return data
    return {
        "format": format_type,
        "count": len(data),
        "data": data,
    }
