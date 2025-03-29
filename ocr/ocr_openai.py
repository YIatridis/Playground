from enum import Enum
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.output import text_from_rendered
from datetime import datetime
import os  
import glob 
from dotenv import load_dotenv
from openai import AsyncOpenAI
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict, field_validator, ValidationError
import pandas as pd
import asyncio
import logfire 
import argparse
import time
from typing import Optional, List, Dict, Union, Literal
import re
import concurrent.futures
import multiprocessing
from functools import partial

# Set the multiprocessing start method to 'spawn' for macOS compatibility
# This prevents issues with forking processes on macOS
if multiprocessing.get_start_method(allow_none=True) != 'spawn':
    multiprocessing.set_start_method('spawn', force=True)

load_dotenv()

# Initialize logfire
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
logfire.configure()
logfire.instrument_openai(client)

# Fixed concurrency limit
MAX_CONCURRENCY = 4
# Thread pool for CPU-bound operations - will be initialized in main function
thread_pool = None

def get_gl_date(invoice_date: str) -> str:
    try:
        invoice_date_obj = datetime.strptime(invoice_date, "%d/%m/%Y")
        current_date = datetime.now()
        if invoice_date_obj.month == current_date.month and invoice_date_obj.year == current_date.year:
            return invoice_date
        else:
            return current_date.replace(day=1).strftime("%d/%m/%Y")
    except Exception as e:
        logfire.error(f"Error parsing invoice date: {e}")
        return datetime.now().replace(day=1).strftime("%d/%m/%Y")


def load_pdf_files_from_folder(folder_path: str) -> List[str]:
    """Load all PDF files from the specified folder."""
    pdf_files = glob.glob(os.path.join(folder_path, '*.pdf'))
    logfire.info(f"Found {len(pdf_files)} PDF files in {folder_path}")
    return pdf_files


class PaymentTerms(str, Enum):
    paid = "Paid"
    thirty_days = "30 Days after Invoice Date"
    sixty_days = "60 Days after Invoice Date"
    ninety_days = "90 Days after Invoice Date"

class Solutions(str, Enum):
    ticket_restaurant = "Ticket Restaurant"
    ticket_compliments = "Ticket Compliments"
    ticket_restaurant_paper = "Ticket Restaurant Paper"
    mybenefits = "MyBenefits"
    spendeo = "Spendeo"
    spendeo_plus = "Spendeo Plus"
    


class OCRResponse(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    invoice_number: str = Field(description="The number of the invoice (not reference but the actual invoice number)")
    invoice_date: str = Field(description="The date of the invoice, shoud be in format DD/MM/YYYY")
    vendor_name: str = Field(description="The vendor of the invoice. This can be a company or a person. It can NEVER be 'Edenred Greece' or 'Voucher Services' or 'Υπηρεσιες Διατακτικων' as this will cause a validation error. ")
    vendor_VAT: str = Field(description="The VAT of the vendor")
    description: str = Field(description="A one line description of the invoice based on the expenses it describes")
    solutions: list[Solutions] = Field(description="The different solutions for which the invoice was alloccated to")
    amount_per_solution: Optional[Dict[str, float]] = Field(description="The amount of the invoice for each solution where the key is the solution name and the value is the amount")
    campaigns_duration: Optional[list[str]] = Field(description="The duration of the campaigns (if any) of the invoice")
    payment_method: Literal['Wired', 'Electronic Transfer'] = Field(description="The payment method of the invoice, should be either 'Wired' or 'Electronic Transfer'")
    payment_terms: PaymentTerms = Field(description="The payment terms of the invoice, should be either 'Paid', '30 Days after Invoice Date', '60 Days after Invoice Date' or '90 Days after Invoice Date'")
    invoice_total: float = Field(description="The total amount of the invoice, usually expressed in EUR or (rarely) USD. Should always be a currency format with two decimals")
    invoice_currency: str = Field(description="The currency of the invoice, should be a three letter currency code.")

    @field_validator("vendor_name")
    @classmethod
    def validate_vendor_name(cls, v):
        DISALLOWED_VENDOR_NAMES = {"Edenred Greece", "Voucher Services", "Υπηρεσιες Διατακτικων"}
        if v in DISALLOWED_VENDOR_NAMES:
            raise ValueError(f"Vendor name '{v}' is disallowed.")
        return v


class SaxoData(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    vendor_name: str
    identifier: str = Field(default="00709")
    vendor_number: Optional[str] = None
    vendor_site_code: str
    invoice_number: str
    invoice_date: str
    invoice_currency: str
    rate: float = Field(default=1.0)
    gl_date: str
    gross_amount: float
    payment_currency: str
    description: str
    payment_method: str
    payment_terms: str
    tax_code: str
    amount_without_tax: float
    tax_amount: float
    leg_acount: Optional[str] = None
    cost_center: Optional[str] = None
    flow: str = Field(default="000")
    solutions: List[Solutions] = Field(default=[Solutions.ticket_restaurant])
    project: Optional[str] = None
    partner: str = Field(default="00000")
    millesim: str = Field(default="0000")
    line_description: str
    prepaid_expenses: Optional[str] = None
    amount_per_solution: Dict[str, float]
    campaigns_duration: List[str]
    

def create_saxo_data_from_ocr(ocr_data: OCRResponse) -> SaxoData:
    """Convert OCRResponse to SaxoData."""
    
    is_greek_vat = ocr_data.vendor_VAT.startswith("EL") or ocr_data.vendor_VAT[:2].isdigit()
    amount_without_tax = round(ocr_data.invoice_total / 1.24, 2) if is_greek_vat else ocr_data.invoice_total
    tax_amount = round(ocr_data.invoice_total - amount_without_tax, 2) if is_greek_vat else 0
    
    # Default empty list for campaigns if not available

    solutions = ocr_data.solutions if hasattr(ocr_data, 'solutions') else []
    amount_per_solution = ocr_data.amount_per_solution if ocr_data.amount_per_solution else {}
    
    return SaxoData(
        vendor_name=ocr_data.vendor_name,
        vendor_site_code=re.sub(r'\s+', '', ocr_data.vendor_VAT),
        invoice_number=ocr_data.invoice_number,
        invoice_date=ocr_data.invoice_date,
        invoice_currency=ocr_data.invoice_currency,
        gl_date=get_gl_date(ocr_data.invoice_date),
        gross_amount=ocr_data.invoice_total,
        payment_currency=ocr_data.invoice_currency,
        description=ocr_data.description,
        payment_method=ocr_data.payment_method,
        payment_terms=ocr_data.payment_terms,
        tax_code=re.sub(r'\s+', '', ocr_data.vendor_VAT),
        amount_without_tax=amount_without_tax,
        tax_amount=tax_amount,
        solutions=solutions,
        line_description=ocr_data.description,
        amount_per_solution=amount_per_solution,
        campaigns_duration=ocr_data.campaigns_duration
    )

system_prompt = """You are a helpful assistant that parses OCR data from images into a structured JSON response.
vendor_name can never be Edenred or Voucher Services or Υπηρεσιες Διατακτικων. Be extra careful with this.
Date should always be in the format DD/MM/YYYY.
"""

async def convert_pdf_in_thread(pdf_file: str) -> tuple:
    """
    Run the PdfConverter in a thread pool to avoid blocking the event loop.
    
    Args:
        pdf_file (str): Path to the PDF file
        
    Returns:
        tuple: (full_markdown, metadata, images)
    """
    loop = asyncio.get_event_loop()
    
    def _convert_pdf():
        converter = PdfConverter(artifact_dict=create_model_dict())
        rendered = converter(pdf_file)
        return text_from_rendered(rendered)
    
    # Use the global thread_pool 
    return await loop.run_in_executor(thread_pool, _convert_pdf)

async def process_pdf_file(pdf_file: str) -> Optional[SaxoData]:
    """
    Process a single PDF file with OCR and parsing.
    
    This function:
    1. Converts the PDF to markdown text using the PdfConverter (in a thread pool)
    2. Sends the markdown to OpenAI for parsing into structured data
    3. Converts the OpenAI response to a SaxoData object
    
    Args:
        pdf_file: Path to the PDF file to process
        
    Returns:
        SaxoData object or None if processing failed
    """
    
    start_time = time.time()
    
    try:
        file_name = Path(pdf_file).name
        logfire.info(f"Starting processing: {file_name}")
        
        # Run the PDF conversion in a thread pool to avoid blocking the event loop
        logfire.debug(f"Converting PDF to markdown: {file_name}")
        full_markdown, metadata, images = await convert_pdf_in_thread(pdf_file)
        logfire.debug(f"Metadata: {metadata}")
        
        # Parse content with OpenAI
        logfire.debug(f"Sending to OpenAI for parsing: {file_name}")
        
        end_result = await client.responses.parse(
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
        saxo_data = create_saxo_data_from_ocr(ocr_data)
        
        processing_time = time.time() - start_time
        logfire.info(f"Successfully processed {file_name} in {processing_time:.2f}s")
        return saxo_data
        
    except Exception as e:
        processing_time = time.time() - start_time
        file_name = Path(pdf_file).name
        logfire.error(f"Error processing {file_name} after {processing_time:.2f}s: {str(e)}")
        return None


async def process_batch(pdf_files: List[str]) -> List[Optional[SaxoData]]:
    """
    Process a batch of PDF files concurrently using asyncio.gather.
    
    This function takes a list of PDF files and processes them all at once,
    returning results in the same order as the input files.
    
    Args:
        pdf_files (List[str]): List of PDF file paths to process
        
    Returns:
        List[Optional[SaxoData]]: List of SaxoData objects (or None for failed processing)
    """
    # Create a set to track active tasks
    active_files = set()
    
    async def wrapped_process_pdf(pdf_file: str) -> Optional[SaxoData]:
        """Helper function to track active files for debugging concurrency"""
        file_name = Path(pdf_file).name
        active_files.add(file_name)
        logfire.debug(f"Added {file_name} to active files. Currently processing: {len(active_files)} files")
        
        try:
            result = await process_pdf_file(pdf_file)
            return result
        finally:
            active_files.remove(file_name)
            logfire.debug(f"Removed {file_name} from active files. Still processing: {len(active_files)} files")
    
    tasks = [wrapped_process_pdf(pdf_file) for pdf_file in pdf_files]
    logfire.info(f"Starting concurrent processing of {len(tasks)} files")
    
    # Create a periodic task to report on concurrency
    async def report_concurrency():
        while active_files:
            logfire.info(f"Currently processing {len(active_files)} files concurrently: {', '.join(sorted(active_files))}")
            await asyncio.sleep(5)
    
    # Start the reporting task
    report_task = asyncio.create_task(report_concurrency())
    
    # Wait for all tasks to complete
    results = await asyncio.gather(*tasks)
    
    # Cancel the reporting task
    report_task.cancel()
    try:
        await report_task
    except asyncio.CancelledError:
        pass
    
    return results


async def process_folder(folder_path: str, output_excel_file: str) -> None:
    """
    Process all PDF files in the given folder using a batched approach.
    
    Instead of using a semaphore for concurrency control, this function:
    1. Loads all PDF files from the folder
    2. Divides them into batches of MAX_CONCURRENCY
    3. Processes each batch fully before moving to the next batch
    
    This approach is simpler than using semaphores while still maintaining
    a fixed concurrency limit of MAX_CONCURRENCY.
    
    Args:
        folder_path (str): Path to folder containing PDF files
        output_excel_file (str): Path to save the Excel output
    
    Returns:
        None
    """
    start_time = time.time()
    
    # Load all PDF files from the folder
    logfire.info(f"Starting PDF processing from folder: {folder_path}")
    pdf_files = load_pdf_files_from_folder(folder_path)
    
    if not pdf_files:
        logfire.warning(f"No PDF files found in {folder_path}")
        return
    
    # Process files in batches of MAX_CONCURRENCY
    results = []
    total_batches = (len(pdf_files) + MAX_CONCURRENCY - 1) // MAX_CONCURRENCY  # Ceiling division
    
    for i in range(0, len(pdf_files), MAX_CONCURRENCY):
        batch = pdf_files[i:i + MAX_CONCURRENCY]
        batch_num = i // MAX_CONCURRENCY + 1
        logfire.info(f"Processing batch {batch_num}/{total_batches}: {len(batch)} files")
        batch_results = await process_batch(batch)
        results.extend(batch_results)
        logfire.info(f"Completed batch {batch_num}/{total_batches}")
    
    # Filter out any None results (failed processing)
    saxo_data_list = [result for result in results if result is not None]
    success_rate = len(saxo_data_list) / len(pdf_files) * 100 if pdf_files else 0
    logfire.info(f"Successfully processed {len(saxo_data_list)} out of {len(pdf_files)} files ({success_rate:.1f}%)")

    if not saxo_data_list:
        logfire.warning("No data was successfully processed")
        return

    # Convert parsed_data to a list of dictionaries
    data_dicts = [data.model_dump() for data in saxo_data_list]

    # Create a DataFrame from the list of dictionaries
    df = pd.DataFrame(data_dicts)

    # Write the DataFrame to an Excel file
    df.to_excel(output_excel_file, index=False)

    total_time = time.time() - start_time
    logfire.info(f"Data has been written to {output_excel_file}")
    logfire.info(f"Total processing time: {total_time:.2f} seconds")
    print(f"✅ Processing complete! Data has been written to {output_excel_file}")


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Process PDF files with OCR and export results to Excel.")
    parser.add_argument("--folder", required=True, help="Folder containing PDF files to process")
    parser.add_argument("--output", default="parsed_data.xlsx", help="Output Excel file (default: parsed_data.xlsx)")
    return parser.parse_args()


def main():
    """Main entry point with proper resource handling."""
    global thread_pool
    
    # Parse command-line arguments
    args = parse_arguments()
    
    try:
        # Initialize thread pool here to ensure proper lifecycle management
        thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=MAX_CONCURRENCY)
        
        # Run the asyncio event loop
        asyncio.run(process_folder(args.folder, args.output))
    finally:
        # Ensure the thread pool is properly shutdown
        if thread_pool:
            logfire.info("Shutting down thread pool...")
            thread_pool.shutdown(wait=True)
            thread_pool = None
            logfire.info("Thread pool shutdown complete")


if __name__ == "__main__":
    main()



