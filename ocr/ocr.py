from mistralai import Mistral
import os  
import glob 
from dotenv import load_dotenv
from rich import print as rprint
from pathlib import Path
from mistralai import DocumentURLChunk, TextChunk
from pydantic import BaseModel, Field
import pandas as pd
import asyncio
import logfire  # Adding logfire for better logging
import tkinter as tk
from tkinter import filedialog, ttk
from threading import Thread


load_dotenv()

# Initialize logfire
logfire.configure()

api_key = 'G0HjyXqRHp20hE46JGSAAKegcTrNfgDf'

mistral = Mistral(api_key=api_key)



def load_pdf_files_from_folder(folder_path: str):
    """Load all PDF files from the specified folder."""
    pdf_files = glob.glob(os.path.join(folder_path, '*.pdf'))
    logfire.info(f"Found {len(pdf_files)} PDF files in {folder_path}")
    return pdf_files

# Will be set by GUI
folder_path = ''
pdf_files = []


class OCRResponse(BaseModel):
    invoice_number: str = Field(description="The number of the invoice")
    invoice_date: str = Field(description="The date of the invoice, shoud be in format DD/MM/YYYY")
    vendor: str = Field(description="The vendor of the invoice")
    campaigns: str = Field(description="The campaigns of the invoice")
    campaigns_duration: list[str] = Field(description="The duration of the campaigns of the invoice")
    invoice_total: float = Field(description="The total of the invoice")
    invoice_currency: str = Field(description="The currency of the invoice")
    invoice_status: str = Field(description="The status of the invoice")

async def process_pdf_file(pdf_file, semaphore):
    """Process a single PDF file with OCR and parsing."""
    async with semaphore:
        try:
            logfire.info(f"Processing file: {pdf_file}")
            
            # Upload the file
            uploaded_pdf = mistral.files.upload(
                file={
                    "file_name": Path(pdf_file).stem,
                    "content": Path(pdf_file).read_bytes(),
                },
                purpose="ocr")
            logfire.debug(f"Uploaded {pdf_file} with ID: {uploaded_pdf.id}")

            # Get signed URL
            signed_url = mistral.files.get_signed_url(file_id=uploaded_pdf.id)
            logfire.debug(f"Got signed URL for {pdf_file}")

            # Process with OCR
            pdf_response = mistral.ocr.process(
                document=DocumentURLChunk(document_url=signed_url.url), 
                model="mistral-ocr-latest", 
                include_image_base64=True)
            logfire.debug(f"OCR processing complete for {pdf_file}")

            # Parse the content
            end_result = mistral.chat.parse(
                model="pixtral-12b-latest",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            TextChunk(text=(
                                "This is the image's OCR in markdown:\n"
                                f"\n{pdf_response.pages[0].markdown}\n.\n"
                                "Convert this into a structured JSON response with the OCR contents in a sensible dictionnary."
                            ))
                        ],
                    },
                ],
                response_format=OCRResponse,
                temperature=0
            )
            logfire.info(f"Successfully processed {pdf_file}")
            return end_result.choices[0].message.parsed
        except Exception as e:
            logfire.error(f"Error processing {pdf_file}: {str(e)}")
            return None

async def main():
    # Create a semaphore to limit concurrency to 5
    semaphore = asyncio.Semaphore(5)
    
    # Create tasks for all PDF files
    tasks = [process_pdf_file(pdf_file, semaphore) for pdf_file in pdf_files]
    
    # Run tasks concurrently and collect results
    logfire.info(f"Starting concurrent processing of {len(tasks)} files")
    results = await asyncio.gather(*tasks)
    
    # Filter out any None results (failed processing)
    parsed_data = [result for result in results if result is not None]
    logfire.info(f"Successfully processed {len(parsed_data)} out of {len(pdf_files)} files")

    # Convert parsed_data to a list of dictionaries
    data_dicts = [data.dict() for data in parsed_data]

    # Create a DataFrame from the list of dictionaries
    df = pd.DataFrame(data_dicts)

    # Define the output Excel file path
    output_excel_file = "parsed_data.xlsx"

    # Write the DataFrame to an Excel file
    df.to_excel(output_excel_file, index=False)

    logfire.info(f"Data has been written to {output_excel_file}")
    print(f"Data has been written to {output_excel_file}")

class OCRApp:
    def __init__(self, root):
        self.root = root
        self.root.title("OCR Invoice Processor")
        self.root.geometry("600x400")
        self.folder_path = ""
        
        # Create main frame
        main_frame = ttk.Frame(root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="OCR Invoice Processor", font=("Arial", 16))
        title_label.pack(pady=10)
        
        # Select folder button
        folder_frame = ttk.Frame(main_frame)
        folder_frame.pack(fill=tk.X, pady=10)
        
        self.folder_label = ttk.Label(folder_frame, text="No folder selected", width=50)
        self.folder_label.pack(side=tk.LEFT, padx=5)
        
        folder_button = ttk.Button(folder_frame, text="Select Folder", command=self.select_folder)
        folder_button.pack(side=tk.RIGHT, padx=5)
        
        # Status section
        self.status_label = ttk.Label(main_frame, text="Ready to process", font=("Arial", 10))
        self.status_label.pack(pady=10)
        
        # Progress bar
        self.progress = ttk.Progressbar(main_frame, orient=tk.HORIZONTAL, length=500, mode='determinate')
        self.progress.pack(pady=10)
        
        # Process button
        self.process_button = ttk.Button(main_frame, text="Process Invoices", command=self.start_processing, state=tk.DISABLED)
        self.process_button.pack(pady=10)
        
        # Results label
        self.results_label = ttk.Label(main_frame, text="")
        self.results_label.pack(pady=10)
    
    def select_folder(self):
        global folder_path, pdf_files
        
        selected_folder = filedialog.askdirectory(title="Select Folder with PDF Invoices")
        if selected_folder:
            self.folder_path = selected_folder
            folder_path = selected_folder  # Set the global variable
            self.folder_label.config(text=f"Selected: {selected_folder}")
            
            # Load PDF files
            pdf_files = load_pdf_files_from_folder(selected_folder)
            if pdf_files:
                self.status_label.config(text=f"Found {len(pdf_files)} PDF files")
                self.process_button.config(state=tk.NORMAL)
            else:
                self.status_label.config(text="No PDF files found in the selected folder")
                self.process_button.config(state=tk.DISABLED)
    
    def update_status(self, message):
        self.status_label.config(text=message)
        self.root.update_idletasks()
    
    def start_processing(self):
        self.process_button.config(state=tk.DISABLED)
        self.update_status("Processing started...")
        self.progress.config(maximum=len(pdf_files))
        self.progress['value'] = 0
        
        # Start processing in a separate thread
        processing_thread = Thread(target=self.run_processing)
        processing_thread.daemon = True
        processing_thread.start()
    
    def run_processing(self):
        try:
            # Run the processing
            output_file = os.path.join(self.folder_path, "parsed_data.xlsx")
            
            asyncio.run(self.processing_with_updates(output_file))
            
            # Update UI after processing
            self.root.after(0, lambda: self.update_status(f"Processing complete! Results saved to {output_file}"))
            self.root.after(0, lambda: self.results_label.config(text=f"Results saved to: {os.path.basename(output_file)}"))
            self.root.after(0, lambda: self.process_button.config(state=tk.NORMAL))
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            logfire.error(error_msg)
            self.root.after(0, lambda: self.update_status(error_msg))
            self.root.after(0, lambda: self.process_button.config(state=tk.NORMAL))
    
    async def processing_with_updates(self, output_excel_file):
        # Create a semaphore to limit concurrency to 5
        semaphore = asyncio.Semaphore(5)
        
        # Create tasks for all PDF files
        tasks = []
        for i, pdf_file in enumerate(pdf_files):
            task = asyncio.create_task(self.process_pdf_with_progress(pdf_file, semaphore, i))
            tasks.append(task)
        
        # Run tasks concurrently and collect results
        logfire.info(f"Starting concurrent processing of {len(tasks)} files")
        results = await asyncio.gather(*tasks)
        
        # Filter out any None results (failed processing)
        parsed_data = [result for result in results if result is not None]
        logfire.info(f"Successfully processed {len(parsed_data)} out of {len(pdf_files)} files")
        
        # Update final status
        self.root.after(0, lambda: self.update_status(f"Successfully processed {len(parsed_data)} out of {len(pdf_files)} files"))
        
        # Convert parsed_data to a list of dictionaries
        data_dicts = [data.dict() for data in parsed_data]
        
        # Create a DataFrame from the list of dictionaries
        df = pd.DataFrame(data_dicts)
        
        # Write the DataFrame to an Excel file
        df.to_excel(output_excel_file, index=False)
        
        logfire.info(f"Data has been written to {output_excel_file}")
    
    async def process_pdf_with_progress(self, pdf_file, semaphore, index):
        """Process a PDF file and update progress"""
        result = await process_pdf_file(pdf_file, semaphore)
        
        # Update progress bar (must be done in the main thread)
        self.root.after(0, lambda: self.progress.step(1))
        self.root.after(0, lambda: self.update_status(f"Processed {index+1}/{len(pdf_files)}: {os.path.basename(pdf_file)}"))
        
        return result


# Run the GUI application
if __name__ == "__main__":
    root = tk.Tk()
    app = OCRApp(root)
    root.mainloop()

