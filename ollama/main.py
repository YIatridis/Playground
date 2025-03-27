from typing import Optional
from pydantic import BaseModel, Field   
from dotenv import load_dotenv
import logfire
from openai import OpenAI
import glob
import os
from pathlib import Path
from rich import print as rprint
from vision_parse import VisionParser
load_dotenv()

# Initialize logfire
ollama_client = OpenAI(base_url='http://100.99.81.63:11434/v1/')
openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
logfire.configure()
logfire.instrument_openai(ollama_client)
logfire.instrument_openai(openai_client)
folder_path = './'

pdf_files = glob.glob(os.path.join(folder_path, '*.pdf'))
pdf_file = Path(pdf_files[0])
logfire.info(f"Found {len(pdf_files)} PDF files in {folder_path}")

# parser = VisionParser(
#     model_name="llama3.2-vision:11b",
#     ollama_config={'OLLAMA_HOST': 'http://100.99.81.63:11434'},
#     api_key='ollama',
#     temperature=0.1,
#     top_p=0.1,
#     image_mode="none",
#     detailed_extraction=True,
#     enable_concurrency=True,
# )
# logfire.debug(f"VisionParser initialized for {Path(pdf_file).name}")

# # Convert PDF to markdown
# logfire.debug(f"Converting PDF to markdown: {Path(pdf_file).name}")
# markdown_pages = parser.convert_pdf(pdf_file)
# full_markdown = "\n\n".join(markdown_pages)
# logfire.debug(f"PDF converted to {len(markdown_pages)} markdown pages")
# rprint(full_markdown)

class Smartphones_Metadata(BaseModel):
    model: str = Field(description="Model name/number of the product")
    color: str = Field(description="Color of the product. Color is usually written in the product description")
    storage: str = Field(description="Storage capacity of the product. Usually it is 32/64/128/256/512GB or 1TB")

class RobotVacuums_Metadata(BaseModel):
    model: str = Field(description="Model name/number of the robot vacuum")
    color: Optional[str] = Field(None, description="Color of the robot vacuum (optional)")

class TVs_Metadata(BaseModel):
    model: str = Field(description="Model name/number of the TV")
    size: str = Field(description="Size of the TV screen, usually in inches (e.g., 55\", 65\")")

class Tablets_Metadata(BaseModel):
    model: str = Field(description="Model name/number of the tablet")
    color: str = Field(description="Color of the tablet")
    storage: str = Field(description="Storage capacity of the tablet. Usually it is 32/64/128/256/512GB or 1TB")

class Laptops_Metadata(BaseModel):
    model: str = Field(description="Model name/number of the laptop")
    size: str = Field(description="Screen size of the laptop, always in inches (word included) (e.g., 13.3\", 15.6\")")
    cpu: str = Field(description="CPU/processor model of the laptop (e.g., Intel i7-1165G7, AMD Ryzen 7 5800H)")
    memory: str = Field(description="RAM/memory capacity of the laptop, usually in GB (e.g., 8GB, 16GB)")
    storage: str = Field(description="Storage capacity of the laptop, usually in GB or TB (e.g., 512GB SSD, 1TB)")
    graphics_card: Optional[str] = Field(None, description="Graphics card model of the laptop (optional)")

CATEGORY_PROMPTS = {
    "Smartphones": '''
        You are a helpful assistant that can extract metadata from a smartphone product description.
        Be careful on the distinction between memory and storage. They are usually referenced together and we only need the storage capacity.
        For example 12GB/512GB means 512GB of storage. We only need the storage capacity and do not need the memory.
        Storage is usually written as 32/64/128/256/512GB or 1TB
    ''',
    
    "Robot_vacuums": '''
        You are a helpful assistant that can extract metadata from a robot vacuum product description.
        Extract the model name/number and color (if available) from the product description.
        Color is optional and might not be present in all descriptions.
    ''',
    
    "TVs": '''
        You are a helpful assistant that can extract metadata from a TV product description.
        Extract the model name/number and screen size from the product description.
        If there are nny spaces in between the model name and the number, remove the spaces.
        Size is typically given in inches (e.g., 55", 65").
    ''',
    
    "Tablets": '''
        You are a helpful assistant that can extract metadata from a tablet product description.
        Extract the model name/number, color, and storage capacity from the product description.
        Be careful on the distinction between memory and storage. They are usually referenced together and we only need the storage capacity.
        For example 4GB/64GB means 64GB of storage. We only need the storage capacity and do not need the memory.
        Storage is usually written as 32/64/128/256/512GB or 1TB
    ''',
    
    "Laptops": '''
        You are a helpful assistant that can extract metadata from a laptop product description.
        Extract the model name/number, screen size, CPU/processor, memory (RAM), storage capacity, and graphics card (if available) from the product description.
        Be careful to distinguish between:
        - Memory (RAM): Usually specified in GB (e.g., 8GB, 16GB)
        - Storage: Usually specified in GB or TB (e.g., 512GB SSD, 1TB HDD)
        - Screen size: Usually specified in inches (e.g., 13.3", 15.6"). Should always be with one decimal, even if it is a whole number. No inches symbol but the word inches should be present.
        Graphics card information is optional and might not be present in all descriptions.
    '''}

description = "Lenovo LOQ 16IRH8 i5-13500H/16GB/512GB RTX 4050 6GB Laptop"

ollama_metadata = ollama_client.beta.chat.completions.parse(
    model="gemma3:1b",
    messages=[
        {"role": "system", "content": CATEGORY_PROMPTS["Laptops"]},
        {"role": "user", "content": description}
    ],
    temperature=0,
    response_format=Laptops_Metadata
)

openai_metadata = openai_client.beta.chat.completions.parse(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": CATEGORY_PROMPTS["Laptops"]},
        {"role": "user", "content": description}
    ],
    response_format=Laptops_Metadata
)



print('Ollama: ', ollama_metadata.choices[0].message.parsed)
print('OpenAI: ', openai_metadata.choices[0].message.parsed)


