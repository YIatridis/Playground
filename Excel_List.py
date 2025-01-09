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

api_key = os.getenv('OPENAI_API_KEY')
jina_api_key = os.getenv('JINA_API_KEY')

client = OpenAI(api_key=api_key)

# def get_raw_data(url):
#     headers = {
#         'Accept': 'text/event-stream',
#         'Authorization': f'Bearer {jina_api_key}',
#         'X-Retain-Images': 'none',
#         'X-With-Iframe': 'true'
#     }
#     response = requests.get(f"https://r.jina.ai/{url}", headers=headers)
#     return response.text

class get_raw_data:
    def __init__(self, url):
        self.url = url
        self.title = "No title found"
        self.text = ""
        self.links = []
        self._fetch_with_selenium()

    def _fetch_with_selenium(self):
        options = Options()
        options.add_argument("--headless")  # Keep commented if you want to watch the browser
        options.add_argument("--disable-gpu")
        driver = webdriver.Chrome(options=options)

        try:
            driver.get(self.url)
            time.sleep(2)  # Initial wait for JS to load

            scroll_pause_time = 2.0
            scroll_up_amount = 500  # Number of pixels to scroll up
            last_height = driver.execute_script("return document.body.scrollHeight")

            while True:
                # 1. Scroll to bottom
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(scroll_pause_time)

                new_height = driver.execute_script("return document.body.scrollHeight")

                if new_height == last_height:
                    # 2. Scroll up slightly by 500 pixels
                    driver.execute_script(f"window.scrollBy(0, -{scroll_up_amount});")
                    time.sleep(scroll_pause_time)

                    # Check if content changed after scrolling up
                    newest_height = driver.execute_script("return document.body.scrollHeight")
                    if newest_height == new_height:
                        # No change even after scrolling up → no more content
                        break
                    else:
                        # Something changed, keep going
                        last_height = newest_height
                else:
                    # Content loaded, update last_height and continue
                    last_height = new_height

            # Now we parse the main page’s final content
            main_soup = BeautifulSoup(driver.page_source, "html.parser")
            self.title = main_soup.title.string if main_soup.title else "No title found"

            body_tag = main_soup.body
            if body_tag:
                for irrelevant in body_tag(["script", "style", "img", "input"]):
                    irrelevant.decompose()
                self.text = body_tag.get_text(separator="\n", strip=True)

            # Process iframes
            iframes = main_soup.find_all("iframe")
            for iframe in iframes:
                src = iframe.get("src")
                if src:
                    iframe_url = urljoin(self.url, src)
                    driver.execute_script(f"window.open('{iframe_url}', '_blank');")
                    driver.switch_to.window(driver.window_handles[-1])
                    time.sleep(2)

                    # Repeat the same scroll-then-scroll-up logic in the iframe
                    last_height_iframe = driver.execute_script("return document.body.scrollHeight")
                    while True:
                        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                        time.sleep(scroll_pause_time)
                        new_height_iframe = driver.execute_script("return document.body.scrollHeight")

                        if new_height_iframe == last_height_iframe:
                            driver.execute_script(f"window.scrollBy(0, -{scroll_up_amount});")
                            time.sleep(scroll_pause_time)

                            newest_height_iframe = driver.execute_script("return document.body.scrollHeight")
                            if newest_height_iframe == new_height_iframe:
                                # No more content to load
                                break
                            else:
                                last_height_iframe = newest_height_iframe
                        else:
                            last_height_iframe = new_height_iframe

                    # Parse the fully loaded iframe
                    iframe_soup = BeautifulSoup(driver.page_source, "html.parser")
                    if iframe_soup.body:
                        for irrelevant in iframe_soup.body(["script", "style", "img", "input"]):
                            irrelevant.decompose()
                        self.text += "\n" + iframe_soup.body.get_text(separator="\n", strip=True)

                    driver.close()
                    driver.switch_to.window(driver.window_handles[0])

            # Extract links from the main page
            all_links = [a.get("href") for a in main_soup.find_all("a")]
            self.links = [l for l in all_links if l]

        finally:
            driver.quit()

    def get_contents(self):
        return f"Webpage Title:\n{self.title}\nWebpage Contents:\n{self.text}\n\n"


def create_excel_list(url, user_prompt):
    raw_data = get_raw_data(url)
    system_prompt = """You are an assistant that extracts information from a webpage and creates a CSV formatted list of the information. 
    The exact instructions regarding the data needed to be extracted along with the raw datawill be provided by the user prompt. For each kind of information, you will create an column. For example, if the users requests
    a list of all the products and services, you will create a column for "Product/Service". If the user requests a list of all the customers, you will create a column for "Customer".
    You will only return well-formed CSV with columns separated by commas and each row on a new line. No Markdown tables, no additional text, no code fences. """

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"The user prompt is: {user_prompt}. The raw data is: {raw_data}, {raw_data.links}"}
    ]

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages
    )

    csv_content = response.choices[0].message.content
    
    try:
        # Read CSV content into pandas DataFrame
        df = pd.read_csv(io.StringIO(csv_content), sep=",", engine="python")
        
        # Generate filename based on URL
        domain = urlparse(url).netloc
        filename = f"{domain}_list.xlsx"
        
        # Check if file exists and append data
        if os.path.exists(filename):
            existing_df = pd.read_excel(filename)
            combined_df = pd.concat([existing_df, df], ignore_index=True)
            combined_df.drop_duplicates(inplace=True)
            combined_df.to_excel(filename, index=False)
        else:
            # Create new Excel file
            df.to_excel(filename, index=False)
        
        # Return both the CSV content and filename
        return f"Excel file saved as: {filename}\n\n{csv_content}"
        
    except pd.errors.EmptyDataError:
        return "Error: No data could be parsed from the response"
    except Exception as e:
        return f"Error creating Excel file: {str(e)}\n\nRaw CSV content:\n{csv_content}"


with gr.Blocks() as ui:
    gr.Markdown("# Excel List Generator")
    company_url_input = gr.Textbox(label="Website URL", placeholder="Enter the company website URL")
    user_prompt_input = gr.Textbox(label="User Prompt", placeholder="Enter what information you want extracted from the website")
    output_markdown = gr.Markdown(label="Generated Excel List", value="Results will appear here...")
    generate_button = gr.Button("Generate Excel List")
    
    generate_button.click(
        create_excel_list,
        inputs=[company_url_input, user_prompt_input], 
        outputs=output_markdown
    )

ui.launch()