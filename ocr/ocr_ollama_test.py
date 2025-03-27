import os  
import glob 
from dotenv import load_dotenv
from pprint import pprint
import logfire
from rich import print as rprint
from pathlib import Path
from pydantic import BaseModel, Field
from vision_parse import VisionParser
from openai import OpenAI


load_dotenv()
logfire.configure()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
logfire.instrument_openai(client)

class OCRResponse(BaseModel):
    invoice_number: str = Field(description="The number of the invoice")
    invoice_date: str = Field(description="The date of the invoice, shoud be in format DD/MM/YYYY")
    vendor: str = Field(description="The vendor of the invoice")
    campaigns: str = Field(description="The campaigns of the invoice")
    campaigns_duration: list[str] = Field(description="The duration of the campaigns of the invoice")
    invoice_total: float = Field(description="The total of the invoice")
    invoice_currency: str = Field(description="The currency of the invoice")
    invoice_status: str = Field(description="The status of the invoice")

system_prompt = """You are a helpful assistant that parses OCR data from images into a structured JSON response.
Vendor can never be Edenred or Voucher Services or Υπηρεσιες Διατακτικων.
Date should always be in the format DD/MM/YYYY.
"""

def load_pdf_files_from_folder(folder_path: str):
    """Load all PDF files from the specified folder."""
    pdf_files = glob.glob(os.path.join(folder_path, '*.pdf'))
    return pdf_files

folder_path = 'meta_invoices'
pdf_files = load_pdf_files_from_folder(folder_path)
rprint(f"Loaded PDF files: {pdf_files}")

pdf_file = Path(pdf_files[0])
assert pdf_file.is_file()


# Initialize the VisionParser with the desired model
parser = VisionParser(
    model_name="gpt-4o-mini",
    api_key=os.getenv("OPENAI_API_KEY"), # Get the OpenAI API key from https://platform.openai.com/api-keys
    temperature=0.1,
    top_p=0.1,
    image_mode="none",
    detailed_extraction=True, # Set to True for more detailed extraction
    enable_concurrency=True,
)

# Path to your local PDF file
#pdf_path = "path/to/your/file.pdf"

# Convert the PDF to markdown
markdown_pages = parser.convert_pdf(pdf_file)
full_markdown = "\n\n".join(markdown_pages)


end_result = client.responses.parse(
                model="gpt-4o-mini",
                instructions=system_prompt,
                input=
                    
                            "This is the Invoice in markdown:\n"
                            f"\n{full_markdown}\n.\n"
                            "Convert this into a structured JSON response",
                text_format=OCRResponse,
                temperature=0
            )


logfire.info(f"Successfully processed {pdf_file}")
rprint(end_result.output[0].content[0].parsed)



# Save the markdown content to a file
