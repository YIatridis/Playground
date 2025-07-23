from enum import Enum
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
import pymupdf4llm

load_dotenv()

# Initialize logfire and OpenAI client
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
logfire.configure()
logfire.instrument_openai(client)

# Configure concurrency
MAX_CONCURRENT_TASKS = 20

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


async def process_pdf_file(pdf_file: str, semaphore: asyncio.Semaphore) -> Optional[SaxoData]:
    """
    Process a single PDF file with OCR and parsing.
    Uses a semaphore to limit concurrent processing.
    
    Args:
        pdf_file: Path to the PDF file to process
        semaphore: Asyncio semaphore for concurrency control
        
    Returns:
        SaxoData object or None if processing failed
    """
    async with semaphore:
        start_time = time.time()
        
        try:
            file_name = Path(pdf_file).name
            logfire.info(f"Starting processing: {file_name}")
            
            # Convert PDF to markdown using pymupdf4llm
            logfire.debug(f"Converting PDF to markdown: {file_name}")
            full_markdown = pymupdf4llm.to_markdown(pdf_file)
            
            # Parse content with OpenAI with retry logic for validation errors
            logfire.debug(f"Sending to OpenAI for parsing: {file_name}")
            
            system_prompt = """You are a helpful assistant that parses OCR data from images into a structured JSON response.
            vendor_name can never be Edenred or Voucher Services or Υπηρεσιες Διατακτικων. Be extra careful with this.
            Date should always be in the format DD/MM/YYYY.
            """

            max_retries = 3
            for attempt in range(max_retries):
                try:
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
                    break  # Success, exit the retry loop
                    
                except ValidationError as ve:
                    error_str = str(ve)
                    if "Vendor name" in error_str and "is disallowed" in error_str and attempt < max_retries - 1:
                        # This is a vendor name validation error, retry with clearer instructions
                        logfire.warning(f"Validation error on attempt {attempt+1}: {error_str}. Retrying...")
                        # Add more specific instructions for the next attempt
                        system_prompt_retry = system_prompt + "\nIMPORTANT: The previous attempt returned a disallowed vendor name. The vendor name CANNOT be any of: Edenred Greece, Voucher Services, Υπηρεσιες Διατακτικων. Look for the actual third-party vendor name in the invoice."
                        # Use the enhanced prompt in the next attempt
                        system_prompt = system_prompt_retry
                        continue
                    else:
                        # Other validation error or reached max retries
                        logfire.error(f"Validation error after {attempt+1} attempts: {error_str}")
                        raise  # Re-raise the exception
            
            processing_time = time.time() - start_time
            logfire.info(f"Successfully processed {file_name} in {processing_time:.2f}s")
            return saxo_data
            
        except Exception as e:
            processing_time = time.time() - start_time
            file_name = Path(pdf_file).name
            logfire.error(f"Error processing {file_name} after {processing_time:.2f}s: {str(e)}")
            return None


async def process_folder(folder_path: str, output_excel_file: str) -> None:
    """
    Process all PDF files in the given folder using asyncio with semaphore for concurrency control.
    
    Args:
        folder_path: Path to folder containing PDF files
        output_excel_file: Path to save the Excel output
    """
    start_time = time.time()
    
    # Load all PDF files from the folder
    logfire.info(f"Starting PDF processing from folder: {folder_path}")
    pdf_files = load_pdf_files_from_folder(folder_path)
    
    if not pdf_files:
        logfire.warning(f"No PDF files found in {folder_path}")
        return
    
    # Create a semaphore to limit concurrency
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
    logfire.info(f"Using asyncio with semaphore limiting to {MAX_CONCURRENT_TASKS} concurrent tasks")
    
    # Process files concurrently with semaphore control
    tasks = [process_pdf_file(pdf_file, semaphore) for pdf_file in pdf_files]
    
    # Track active tasks for monitoring
    active_tasks = set()
    active_tasks_lock = asyncio.Lock()
    
    async def wrapped_task(task, pdf_file):
        file_name = Path(pdf_file).name
        async with active_tasks_lock:
            active_tasks.add(file_name)
            logfire.debug(f"Starting task for {file_name}. Active tasks: {len(active_tasks)}")
        
        try:
            return await task
        finally:
            async with active_tasks_lock:
                active_tasks.remove(file_name)
                logfire.debug(f"Completed task for {file_name}. Remaining active tasks: {len(active_tasks)}")
    
    # Create a monitoring task
    async def monitor_progress():
        while True:
            async with active_tasks_lock:
                if not active_tasks:
                    break
                logfire.info(f"Currently processing {len(active_tasks)} files concurrently")
            await asyncio.sleep(5)
    
    # Start monitoring
    monitor = asyncio.create_task(monitor_progress())
    
    # Gather all results
    wrapped_tasks = [wrapped_task(task, pdf_file) for task, pdf_file in zip(tasks, pdf_files)]
    results = await asyncio.gather(*wrapped_tasks)
    
    # Cancel monitoring
    monitor.cancel()
    try:
        await monitor
    except asyncio.CancelledError:
        pass
    
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
    parser.add_argument("--concurrency", type=int, default=MAX_CONCURRENT_TASKS, 
                      help=f"Maximum number of concurrent tasks (default: {MAX_CONCURRENT_TASKS})")
    return parser.parse_args()


async def main_async():
    """Async main entry point."""
    # Parse command-line arguments
    args = parse_arguments()
    
    # Update concurrency limit if specified
    global MAX_CONCURRENT_TASKS
    if args.concurrency:
        MAX_CONCURRENT_TASKS = args.concurrency
        logfire.info(f"Setting concurrency limit to {MAX_CONCURRENT_TASKS}")
    
    # Process the folder
    await process_folder(args.folder, args.output)


def main():
    """Main entry point for the script."""
    try:
        # Run the asyncio event loop
        asyncio.run(main_async())
    except KeyboardInterrupt:
        logfire.warning("Process interrupted by user")
    except Exception as e:
        logfire.error(f"Unhandled error: {str(e)}")
        raise


if __name__ == "__main__":
    main() 