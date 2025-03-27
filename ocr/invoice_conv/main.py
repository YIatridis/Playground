import os  
import glob 
from dotenv import load_dotenv
from openai import AsyncOpenAI
from rich import print as rprint
from pathlib import Path
from pydantic import BaseModel, Field
import pandas as pd
import asyncio
import logfire 
import argparse
import time
from typing import Optional, List

from vision_parse import VisionParser


load_dotenv()

# Initialize logfire
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
logfire.configure()
logfire.instrument_openai(client)

# Fixed concurrency limit
MAX_CONCURRENCY = 30


def load_pdf_files_from_folder(folder_path: str) -> List[str]:
    """Load all PDF files from the specified folder."""
    pdf_files = glob.glob(os.path.join(folder_path, '*.pdf'))
    logfire.info(f"Found {len(pdf_files)} PDF files in {folder_path}")
    return pdf_files


class OCRResponse(BaseModel):
    invoice_number: str = Field(description="The number of the invoice (not reference but the actual invoice number)")
    invoice_date: str = Field(description="The date of the invoice, shoud be in format DD/MM/YYYY")
    vendor: str = Field(description="The vendor of the invoice")
    campaigns: str = Field(description="The campaigns of the invoice")
    campaigns_duration: list[str] = Field(description="The duration of the campaigns of the invoice")
    invoice_total: float = Field(description="The total of the invoice. Should always be a currency format with two decimals")
    invoice_currency: str = Field(description="The currency of the invoice, should be a three letter currency code.")
    invoice_status: str = Field(description="The status of the invoice")

system_prompt = """You are a helpful assistant that parses OCR data from images into a structured JSON response.
Vendor can never be Edenred or Voucher Services or Υπηρεσιες Διατακτικων.
Date should always be in the format DD/MM/YYYY.
"""


async def process_pdf_file(pdf_file: str, semaphore: asyncio.Semaphore, task_id: int) -> Optional[OCRResponse]:
    """Process a single PDF file with OCR and parsing."""
    
    start_time = time.time()
    
    async with semaphore:
        try:
            logfire.info(f"Starting processing: {Path(pdf_file).name}")
            
            # Create VisionParser instance
            parser = VisionParser(
                model_name="gpt-4o-mini",
                api_key=os.getenv("OPENAI_API_KEY"),
                temperature=0.1,
                top_p=0.1,
                image_mode="none",
                detailed_extraction=True,
                enable_concurrency=True,
            )
            logfire.debug(f"VisionParser initialized for {Path(pdf_file).name}")

            # Convert PDF to markdown
            logfire.debug(f"Converting PDF to markdown: {Path(pdf_file).name}")
            markdown_pages = parser.convert_pdf(pdf_file)
            full_markdown = "\n\n".join(markdown_pages)
            logfire.debug(f"PDF converted to {len(markdown_pages)} markdown pages")

            # Parse content with OpenAI
            logfire.debug(f"Sending to OpenAI for parsing: {Path(pdf_file).name}")
            end_result = await client.responses.parse(
                model="gpt-4o-mini",
                instructions=system_prompt,
                input="This is the Invoice in markdown:\n"
                      f"\n{full_markdown}\n.\n"
                      "Convert this into a structured JSON response",
                text_format=OCRResponse,
                temperature=0
            )

            # Validate and return result
            parsed_result = end_result.output[0].content[0].parsed
            processing_time = time.time() - start_time
            logfire.info(f"Successfully processed {Path(pdf_file).name} in {processing_time:.2f}s")
            return parsed_result
            
        except Exception as e:
            processing_time = time.time() - start_time
            logfire.error(f"Error processing {Path(pdf_file).name} after {processing_time:.2f}s: {str(e)}")
            return None


async def process_folder(folder_path: str, output_excel_file: str) -> None:
    """Process all PDF files in the given folder with fixed concurrency limit."""
    start_time = time.time()
    
    # Load all PDF files from the folder
    logfire.info(f"Starting PDF processing from folder: {folder_path}")
    pdf_files = load_pdf_files_from_folder(folder_path)
    
    if not pdf_files:
        logfire.warning(f"No PDF files found in {folder_path}")
        return
    
    # Create a semaphore to limit concurrency
    semaphore = asyncio.Semaphore(MAX_CONCURRENCY)
    
    # Create tasks for all PDF files with task IDs
    tasks = [
        process_pdf_file(pdf_file, semaphore, i) 
        for i, pdf_file in enumerate(pdf_files)
    ]
    
    # Run tasks concurrently and collect results
    logfire.info(f"Starting concurrent processing of {len(tasks)} files with concurrency limit of {MAX_CONCURRENCY}")
    results = await asyncio.gather(*tasks)
    
    # Filter out any None results (failed processing)
    parsed_data = [result for result in results if result is not None]
    success_rate = len(parsed_data) / len(pdf_files) * 100 if pdf_files else 0
    logfire.info(f"Successfully processed {len(parsed_data)} out of {len(pdf_files)} files ({success_rate:.1f}%)")

    if not parsed_data:
        logfire.warning("No data was successfully processed")
        return

    # Convert parsed_data to a list of dictionaries
    data_dicts = [data.model_dump() for data in parsed_data]

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


if __name__ == "__main__":
    # Parse command-line arguments
    args = parse_arguments()
    
    # Run the asyncio event loop
    asyncio.run(process_folder(args.folder, args.output))



