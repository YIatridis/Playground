import os
import glob
import base64
import asyncio
import requests
from pathlib import Path
from dotenv import load_dotenv
from typing import List, Optional
from pdf2image import convert_from_path
from rich import print as rprint
from pydantic import BaseModel, Field
import pandas as pd
import logfire
from io import BytesIO
from openai import AsyncOpenAI
import tempfile
# Initialize logfire
logfire.configure()


# Load environment variables
load_dotenv()

# Ollama API endpoint
OLLAMA_API_URL = "http://100.99.81.63:11434/v1"
# Model to use - should be a multimodal model like llava or bakllava
OLLAMA_MODEL = "gemma3:latest"
client = AsyncOpenAI(base_url="http://100.99.81.63:11434/v1/", api_key='ollama')
logfire.instrument_openai(client)

class OCRResponse(BaseModel):
    invoice_number: str = Field(description="The number of the invoice")
    invoice_date: str = Field(description="The date of the invoice")
    vendor: str = Field(description="The vendor issuing the invoice. This can never be Edenred or Voucher Services or Υπηρεσιες Διατακτικων")
    date: str = Field(description="The date of the invoice. This should always be in the format DD/MM/YYYY")
    campaigns: list[str] = Field(description="The campaigns of the invoice")
    campaigns_duration: list[str] = Field(description="The duration of the campaigns of the invoice")
    invoice_total: float = Field(description="The total of the invoice")
    invoice_currency: str = Field(description="The currency of the invoice")
    invoice_status: str = Field(description="The status of the invoice")


def load_pdf_files_from_folder(folder_path: str) -> List[str]:
    """Load all PDF files from the specified folder."""
    pdf_files = glob.glob(os.path.join(folder_path, '*.pdf'))
    logfire.info(f"Found {len(pdf_files)} PDF files in {folder_path}")
    return pdf_files


def convert_pdf_to_images(pdf_path: str) -> List[BytesIO]:
    """Convert a PDF file to a list of images."""
    try:
        logfire.info(f"Converting PDF to images: {pdf_path}")
        images = convert_from_path(pdf_path)
        logfire.info(f"Converted {len(images)} pages from {pdf_path}")
        
        # Convert PIL images to BytesIO objects
        image_bytes_list = []
        for i, image in enumerate(images):
            img_byte_arr = BytesIO()
            image.save(img_byte_arr, format='PNG')
            img_byte_arr.seek(0)
            image_bytes_list.append(img_byte_arr)
        
        return image_bytes_list
    except Exception as e:
        logfire.error(f"Error converting PDF to images: {str(e)}")
        return []


def encode_image_to_base64(image_bytes: BytesIO) -> str:
    """Encode image bytes to base64 string."""
    return base64.b64encode(image_bytes.getvalue()).decode('utf-8')


async def process_image_with_ollama(image_bytes: BytesIO, semaphore) -> Optional[OCRResponse]:
    """Process an image with Ollama's multimodal model."""
    async with semaphore:
        try:
            image_base64 = encode_image_to_base64(image_bytes)
            
            # Create the prompt for the model
            system_prompt = """You are a helpful assistant that parses OCR data from images into a structured JSON response.
            Vendor can never be Edenred or Voucher Services or Υπηρεσιες Διατακτικων.
            Date should always be in the format DD/MM/YYYY.
            """
            
            user_prompt = "Extract all the invoice information from this image and return it in JSON format."
            
            # Prepare the API request payload
            payload = {
                "model": OLLAMA_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user", 
                        "content": [
                            {"type": "text", "text": user_prompt},
                            {"type": "image", "image": f"data:image/png;base64,{image_base64}"}
                        ]
                    }
                ],
                
                "format": OCRResponse  # Request JSON formatted response
            }
            
            logfire.debug("Sending request to Ollama API")
            response = await client.chat.completions.create(
                payload
            )
            
            if response.status_code != 200:
                logfire.error(f"Error from Ollama API: {response.status_code} - {response.text}")
                return None
                
            result = response.json()
            content = result.get("message", {}).get("content", "")
            
            logfire.debug(f"Received response from Ollama: {content[:100]}...")
            
            # Parse the JSON response into the OCRResponse model
            try:
                # The model may return JSON as a string inside the response text,
                # or might not properly format it. We'll need to handle both cases.
                import json
                import re
                
                # Try to extract JSON from the text if it's not already valid JSON
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                    data = json.loads(json_str)
                else:
                    # If we can't find JSON pattern, try parsing the whole content
                    data = json.loads(content)
                
                # Ensure all required fields are present
                parsed_data = {
                    "invoice_number": data.get("invoice_number", ""),
                    "invoice_date": data.get("invoice_date", ""),
                    "vendor": data.get("vendor", ""),
                    "date": data.get("date", ""),
                    "campaigns": data.get("campaigns", []),
                    "campaigns_duration": data.get("campaigns_duration", []),
                    "invoice_total": float(data.get("invoice_total", 0)),
                    "invoice_currency": data.get("invoice_currency", ""),
                    "invoice_status": data.get("invoice_status", "")
                }
                
                return OCRResponse(**parsed_data)
            except Exception as e:
                logfire.error(f"Error parsing response to OCRResponse: {str(e)}")
                logfire.error(f"Response content: {content}")
                return None
                
        except Exception as e:
            logfire.error(f"Error processing image with Ollama: {str(e)}")
            return None


async def process_pdf_file(pdf_file: str, semaphore) -> List[Optional[OCRResponse]]:
    """Process a single PDF file by converting to images and processing with Ollama."""
    try:
        logfire.info(f"Processing file: {pdf_file}")
        
        # Convert PDF to images
        images = convert_pdf_to_images(pdf_file)
        
        if not images:
            logfire.warning(f"No images could be extracted from {pdf_file}")
            return []
            
        # Process each image with Ollama
        tasks = [process_image_with_ollama(image, semaphore) for image in images]
        results = await asyncio.gather(*tasks)
        
        # Filter out None results
        valid_results = [result for result in results if result is not None]
        
        logfire.info(f"Successfully processed {len(valid_results)} out of {len(images)} pages from {pdf_file}")
        return valid_results
        
    except Exception as e:
        logfire.error(f"Error processing {pdf_file}: {str(e)}")
        return []


async def main():
    # Get folder path
    folder_path = 'meta_invoices'
    pdf_files = load_pdf_files_from_folder(folder_path)
    rprint(f"Loaded PDF files: {pdf_files}")
    
    # Create a semaphore to limit concurrency to 3 (Ollama may have resource constraints)
    semaphore = asyncio.Semaphore(3)
    
    # Process all PDF files
    all_tasks = [process_pdf_file(pdf_file, semaphore) for pdf_file in pdf_files]
    all_results = await asyncio.gather(*all_tasks)
    
    # Flatten the list of lists
    parsed_data = [item for sublist in all_results for item in sublist]
    
    logfire.info(f"Total successfully processed items: {len(parsed_data)}")
    
    if not parsed_data:
        logfire.warning("No data was successfully processed")
        return
    
    # Convert parsed_data to a list of dictionaries
    data_dicts = [data.dict() for data in parsed_data]
    
    # Create a DataFrame from the list of dictionaries
    df = pd.DataFrame(data_dicts)
    
    # Define the output Excel file path
    output_excel_file = "parsed_data_ollama.xlsx"
    
    # Write the DataFrame to an Excel file
    df.to_excel(output_excel_file, index=False)
    
    logfire.info(f"Data has been written to {output_excel_file}")
    rprint(f"Data has been written to {output_excel_file}")


if __name__ == "__main__":
    # Check if Ollama is running
    try:
        response = requests.get(f"{OLLAMA_API_URL}/tags")
        if response.status_code != 200:
            logfire.error(f"Error connecting to Ollama API: {response.status_code} - {response.text}")
            print("Error: Could not connect to Ollama API. Make sure Ollama is running.")
            exit(1)
            
        # Check if the selected model is available
        models = response.json().get("models", [])
        available_models = [model["name"] for model in models]
        
        if OLLAMA_MODEL not in available_models:
            logfire.warning(f"Selected model {OLLAMA_MODEL} not found in available models: {available_models}")
            print(f"Warning: Model {OLLAMA_MODEL} not found. Available models: {available_models}")
            print(f"You can pull the model with: ollama pull {OLLAMA_MODEL}")
            response = input("Would you like to continue anyway? (y/n): ")
            if response.lower() != 'y':
                exit(1)
    except Exception as e:
        logfire.error(f"Error checking Ollama status: {str(e)}")
        print(f"Error: Could not check Ollama status. Make sure Ollama is running. Error: {str(e)}")
        exit(1)
    
    asyncio.run(main())



