from typing import List, Optional
from pydantic import BaseModel, Field


class OCRResponse(BaseModel):
    invoice_number: str = Field(description="The number of the invoice (not reference but the actual invoice number)")
    invoice_date: str = Field(description="The date of the invoice, should be in format DD/MM/YYYY")
    vendor: str = Field(description="The vendor of the invoice")
    campaigns: str = Field(description="The campaigns of the invoice")
    campaigns_duration: List[str] = Field(description="The duration of the campaigns of the invoice")
    invoice_total: float = Field(description="The total of the invoice. Should always be a currency format with two decimals")
    invoice_currency: str = Field(description="The currency of the invoice, should be a three letter currency code.")
    invoice_status: str = Field(description="The status of the invoice")


class ExportFormat(BaseModel):
    format_type: str = "excel"  # excel, csv, json
    filters: Optional[dict] = None
