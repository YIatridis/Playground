from pathlib import Path
import os
import logfire
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.output import text_from_rendered
from rich import print as rprint
from pydantic import BaseModel, Field 
from typing import Optional, Dict
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

logfire.configure()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
                
system_prompt = """You are a helpful assistant that parses OCR data from images into a structured JSON response.
Vendor can never be Edenred or Voucher Services or Υπηρεσιες Διατακτικων.
Date should always be in the format DD/MM/YYYY.
"""



class OCRResponse(BaseModel):
    invoice_number: str = Field(description="The number of the invoice (not reference but the actual invoice number)")
    invoice_date: str = Field(description="The date of the invoice, shoud be in format DD/MM/YYYY")
    vendor_name: str = Field(description="The vendor of the invoice")
    vendor_VAT: str = Field(description="The VAT of the vendor")
    description: str = Field(description="A one line description of the invoice based on the expenses it describes")
    solution: list[str] = Field(description="The different products or services of the invoice")
    amount_per_product: Optional[list[Dict[str, float]]] = Field(description="The amount of the invoice for each product")
    campaigns_duration: Optional[list[str]] = Field(description="The duration of the campaigns (if any) of the invoice")
    payment_method: str = Field(description="The payment method of the invoice, should be either 'Wired' or 'Electronic Transfer'")
    payment_terms: str = Field(description="The payment terms of the invoice, should be either 'Due on receipt' or 'Due on invoice date'")
    invoice_total: float = Field(description="The total amount of the invoice, usually expressed in EUR or (rarely) USD. Should always be a currency format with two decimals")
    invoice_currency: str = Field(description="The currency of the invoice, should be a three letter currency code.")



converter = PdfConverter(
    artifact_dict=create_model_dict(),
)

FILEPATH = "/Users/ioannisiatridis/Code/Projects/Playground/ocr/small_set/2025-01-31T06-25 Transaction #8970124496433449-9011723812273522.pdf"

logfire.info(f"Starting processing: {Path(FILEPATH).name}")

rendered = converter(FILEPATH)
full_markdown, _, images = text_from_rendered(rendered)


end_result = client.responses.parse(
                model="gpt-4o-mini",
                instructions=system_prompt,
                input="This is the Invoice in markdown:\n"
                      f"\n{full_markdown}\n.\n"
                      "Convert this into a structured JSON response",
                text_format=OCRResponse,
                temperature=0
            )

            # Get OCR results and convert to SaxoData
ocr_data = end_result.output[0].content[0].parsed

rprint(full_markdown)
rprint(ocr_data)
