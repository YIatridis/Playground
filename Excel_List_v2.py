"""
Excel List Generator

This module provides functionality to scrape web content and generate Excel files with structured data.
It uses Selenium for web scraping and OpenAI's GPT model to extract and structure the data.

Main components:
- WebScraper (get_raw_data class): Handles web page content extraction
- ExcelGenerator: Processes scraped data into Excel files
- Gradio UI: Provides a web interface for the tool
"""

from openai import OpenAI
import gradio as gr
import os
import requests
import pandas as pd
import io
from urllib.parse import urlparse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import time

# Initialize API clients
api_key = os.getenv('OPENAI_API_KEY')
jina_api_key = os.getenv('JINA_API_KEY')
client = OpenAI(api_key=api_key)

class WebScraper:
    """Handles web page content extraction using Selenium and BeautifulSoup."""
    
    def __init__(self, url):
        """Initialize scraper with target URL."""
        self.url = url
        self.title = "No title found"
        self.text = ""
        self.links = []
        self._fetch_with_selenium()

    def _scroll_down_up(self, driver, scroll_pause_time=2.0, scroll_up_amount=1000):
        """
        Implements infinite scroll handling by scrolling down and up to trigger content loading.
        
        Args:
            driver: Selenium WebDriver instance
            scroll_pause_time: Time to wait between scrolls
            scroll_up_amount: Pixels to scroll up when checking for new content
        """
        last_height = driver.execute_script("return document.body.scrollHeight")
        while True:
            # Scroll to bottom
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(scroll_pause_time)

            new_height = driver.execute_script("return document.body.scrollHeight")

            if new_height == last_height:
                # Try scrolling up multiple times to trigger lazy loading
                for _ in range(3):
                    driver.execute_script(f"window.scrollBy(0, -{scroll_up_amount});")
                    time.sleep(scroll_pause_time)

                newest_height = driver.execute_script("return document.body.scrollHeight")
                if newest_height == new_height:
                    break
                else:
                    last_height = newest_height
            else:
                last_height = new_height

    def _fetch_with_selenium(self):
        """Main method to fetch and process web content using Selenium."""
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        driver = webdriver.Chrome(options=options)

        try:
            # Process main page
            driver.get(self.url)
            time.sleep(2)  # Allow initial JS load
            self._scroll_down_up(driver)
            self._process_main_page(driver)
            
            # Process iframes
            self._process_iframes(driver)

        finally:
            driver.quit()

    def _process_main_page(self, driver):
        """Extract content from the main page."""
        main_soup = BeautifulSoup(driver.page_source, "html.parser")
        self.title = main_soup.title.string if main_soup.title else "No title found"

        if main_soup.body:
            self._clean_and_extract_content(main_soup.body)
            self.links.extend([link.get("href") for link in main_soup.find_all("a") if link.get("href")])

    def _process_iframes(self, driver):
        """Process iframe content on the page."""
        main_soup = BeautifulSoup(driver.page_source, "html.parser")
        for iframe in main_soup.find_all("iframe"):
            src = iframe.get("src")
            if src:
                self._process_single_iframe(driver, src)

    def _process_single_iframe(self, driver, src):
        """Process a single iframe's content."""
        iframe_url = urljoin(self.url, src)
        driver.execute_script(f"window.open('{iframe_url}', '_blank');")
        driver.switch_to.window(driver.window_handles[-1])
        time.sleep(2)

        self._scroll_down_up(driver)
        iframe_soup = BeautifulSoup(driver.page_source, "html.parser")
        
        if iframe_soup.body:
            self._clean_and_extract_content(iframe_soup.body)
            self.links.extend([a.get("href") for a in iframe_soup.find_all("a") if a.get("href")])

        driver.close()
        driver.switch_to.window(driver.window_handles[0])

    def _clean_and_extract_content(self, element):
        """Clean and extract text content from a BeautifulSoup element."""
        for irrelevant in element(["script", "style", "img", "input"]):
            irrelevant.decompose()
        self.text += "\n" + element.get_text(separator="\n", strip=True)

    def get_contents(self):
        """Return formatted page contents."""
        return (
            f"Webpage Title:\n{self.title}\n"
            f"Webpage Contents:\n{self.text}\n\n"
        )

def create_excel_list(url, user_prompt):
    """
    Create an Excel file from web content based on user prompt.
    
    Args:
        url: Target website URL
        user_prompt: Instructions for data extraction
        
    Returns:
        tuple: (markdown_content, status_message)
    """
    # Scrape web content
    raw_obj = WebScraper(url)
    raw_text = raw_obj.get_contents()
    collected_links = raw_obj.links

    # Prepare GPT prompt
    system_prompt = """You are an assistant that extracts information from a webpage and creates a CSV formatted list of the information. 
    The exact instructions regarding the data needed to be extracted along with the raw data will be provided by the user prompt. For each kind of information, you will create a column. 
    You will only return well-formed CSV with columns separated by commas and each row on a new line. No Markdown tables, no additional text, no code fences."""

    # Get structured data from GPT
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"The user prompt is: {user_prompt}. The raw data is: {raw_text}, and the links are {collected_links}"}
        ],
        temperature=0.0
    )

    csv_content = response.choices[0].message.content
    return save_to_excel(csv_content, url, raw_obj.title)

def save_to_excel(csv_content, url, page_title):
    """
    Save CSV content to Excel file with proper error handling.
    
    Returns:
        tuple: (markdown_content, status_message)
    """
    file_saved = False
    filename = f"{urlparse(url).netloc}_list.xlsx"
    sheet_name = sanitize_sheet_name(page_title)
    error_msg = ""
    
    try:
        df = pd.read_csv(io.StringIO(csv_content), sep=",", engine="python")
        sheet_name = handle_existing_file(filename, sheet_name, df)
        file_saved = True
        
    except pd.errors.EmptyDataError:
        error_msg = "Error: No data could be parsed from the response"
    except Exception as e:
        error_msg = f"Error: {str(e)}"

    status = generate_status_message(file_saved, filename, sheet_name, error_msg)
    return f"{status}\n\nExtracted Data:\n{csv_content}", status

def sanitize_sheet_name(title):
    """Create valid Excel sheet name from title."""
    sheet_name = title.strip()
    invalid_chars = [':', '\\', '/', '?', '*', '[', ']']
    for char in invalid_chars:
        sheet_name = sheet_name.replace(char, '')
    return sheet_name[:27] or "Sheet1"

def handle_existing_file(filename, sheet_name, df):
    """Handle writing to existing Excel file with sheet name conflicts."""
    if os.path.exists(filename):
        try:
            existing_wb = pd.read_excel(filename, sheet_name=None)
            sheet_name = get_unique_sheet_name(sheet_name, existing_wb.keys())
            with pd.ExcelWriter(filename, engine='openpyxl', mode='a') as writer:
                df.to_excel(writer, sheet_name=sheet_name, index=False)
        except Exception:
            with pd.ExcelWriter(filename, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name=sheet_name, index=False)
    else:
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    return sheet_name

def get_unique_sheet_name(base_name, existing_names):
    """Generate unique sheet name avoiding conflicts."""
    test_name = base_name
    counter = 1
    while test_name in existing_names:
        test_name = f"{base_name}_{counter}"
        counter += 1
    return test_name

def generate_status_message(file_saved, filename, sheet_name, error_msg):
    """Generate appropriate status message based on operation result."""
    if file_saved:
        status = f"Success! Excel file saved as: {filename} (Sheet: {sheet_name})"
        if error_msg:
            status += f"\nNote: {error_msg}"
    else:
        status = f"Failed to save Excel file. {error_msg}"
    return status

# Initialize Gradio UI
with gr.Blocks() as ui:
    gr.Markdown("# Excel List Generator")
    company_url_input = gr.Textbox(
        label="Website URL", 
        placeholder="Enter the company website URL",
        value="https://hrpro.gr/recruiters-50-powerlist-2024/"
    )
    user_prompt_input = gr.Textbox(
        label="User Prompt", 
        placeholder="Enter what information you want extracted from the website",
        value="Grab a list with the names, companies and Linkedin profile links of all the people on the page. "
    )
    output_markdown = gr.Markdown(label="Generated Excel List", value="Results will appear here...")
    generate_button = gr.Button("Generate Excel List")
    status_text = gr.Textbox(label="Status", value="Ready", interactive=False)
    
    def process_with_status(url, prompt):
        """Handle button click with status updates."""
        status_text.value = "Processing... Please wait"
        return create_excel_list(url, prompt)
    
    generate_button.click(
        process_with_status,
        inputs=[company_url_input, user_prompt_input],
        outputs=[output_markdown, status_text]
    )

ui.launch()