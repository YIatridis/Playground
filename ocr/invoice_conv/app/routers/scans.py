import os
import uuid
import shutil
from typing import Any, List, Optional
from datetime import datetime
import asyncio
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, BackgroundTasks, Response
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
import pandas as pd
import io

from app.core.deps import get_db, get_current_user
from app.services import scan as scan_service
from app.services import subscription as subscription_service
from app.models.user import User
from app.schemas.scan import ScanOut, ScanCreate, ScanUpdate
from app.schemas.invoice import ExportFormat
from app.core.config import settings


router = APIRouter()


@router.post("/", response_model=ScanOut, status_code=status.HTTP_201_CREATED)
async def create_scan(
    *,
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
) -> Any:
    """Upload a PDF file for scanning."""
    # Check if file is a PDF
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are supported",
        )
    
    # Check available scans in subscription
    subscription = subscription_service.get_user_subscription(db, current_user.id)
    if not subscription or subscription.scans_remaining <= 0:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Scan quota exceeded. Please upgrade your subscription.",
        )
    
    # Create uploads directory if it doesn't exist
    uploads_dir = Path("uploads")
    user_dir = uploads_dir / current_user.id
    user_dir.mkdir(parents=True, exist_ok=True)
    
    # Save file with unique name
    file_uuid = str(uuid.uuid4())
    file_extension = os.path.splitext(file.filename)[1]
    safe_filename = f"{file_uuid}{file_extension}"
    file_path = user_dir / safe_filename
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Create scan record
    scan_in = ScanCreate(
        user_id=current_user.id,
        original_filename=file.filename,
        file_path=str(file_path),
    )
    
    db_scan = scan_service.create_scan(db, scan_in)
    if not db_scan:
        # This shouldn't happen since we checked quota, but just in case
        os.remove(file_path)
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Failed to create scan. Quota may have been exceeded.",
        )
    
    # Process scan in background
    background_tasks.add_task(scan_service.process_scan, db, db_scan.id)
    
    return db_scan


@router.get("/", response_model=List[ScanOut])
def get_user_scans(
    *,
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
) -> Any:
    """Get user's scans."""
    scans = scan_service.get_user_scans(db, current_user.id, skip=skip, limit=limit)
    return scans


@router.get("/{scan_id}", response_model=ScanOut)
def get_scan(
    *,
    db: Session = Depends(get_db),
    scan_id: str,
    current_user: User = Depends(get_current_user),
) -> Any:
    """Get a specific scan."""
    scan = scan_service.get_scan(db, scan_id)
    if not scan or scan.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Scan not found")
    return scan


@router.delete("/{scan_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scan(
    *,
    db: Session = Depends(get_db),
    scan_id: str,
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete a scan."""
    scan = scan_service.get_scan(db, scan_id)
    if not scan or scan.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Scan not found")
    
    success = scan_service.delete_scan(db, scan_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete scan")
    
    # For 204 responses, don't return anything


@router.post("/export")
def export_scans(
    *,
    db: Session = Depends(get_db),
    export_format: ExportFormat = Depends(),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Export scans to various formats."""
    export_data = scan_service.export_scans(db, current_user.id, export_format.format_type)
    
    if export_format.format_type == "excel":
        # Convert to Excel
        output = io.BytesIO()
        df = pd.DataFrame(export_data["data"])
        df.to_excel(output, index=False, engine="openpyxl")
        output.seek(0)
        
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=invoice_scans_{datetime.now().strftime('%Y%m%d')}.xlsx"},
        )
    
    elif export_format.format_type == "csv":
        # Convert to CSV
        output = io.StringIO()
        df = pd.DataFrame(export_data["data"])
        df.to_csv(output, index=False)
        output.seek(0)
        
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode()),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=invoice_scans_{datetime.now().strftime('%Y%m%d')}.csv"},
        )
    
    else:  # JSON
        return export_data
