from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import time

class Website:
    def __init__(self, url):
        self.url = url
        self.title = "No title found"
        self.text = ""
        self.links = []
        self._fetch_with_selenium()

    def _scroll_down_up(self, driver, scroll_pause_time=2.0, scroll_up_amount=500):
        """
        Scrolls to the bottom, waits, then scrolls up by scroll_up_amount if
        no new content is loaded, repeating until no further content appears.
        """
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

                newest_height = driver.execute_script("return document.body.scrollHeight")
                if newest_height == new_height:
                    # No more content, break out
                    break
                else:
                    last_height = newest_height
            else:
                last_height = new_height

    def _fetch_with_selenium(self):
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        driver = webdriver.Chrome(options=options)

        try:
            # 1. Load the main page
            driver.get(self.url)
            time.sleep(2)  # Initial wait for JS to load

            # 2. Scroll on the main page
            self._scroll_down_up(driver, scroll_pause_time=2.0, scroll_up_amount=500)

            # 3. Parse the fully loaded main page
            main_soup = BeautifulSoup(driver.page_source, "html.parser")
            self.title = main_soup.title.string if main_soup.title else "No title found"

            body_tag = main_soup.body
            if body_tag:
                # Remove only script, style, img, input. We keep anchor tags (a) to preserve links.
                for irrelevant in body_tag(["script", "style", "img", "input"]):
                    irrelevant.decompose()
                self.text = body_tag.get_text(separator="\n", strip=True)

            # Collect links from the main page
            page_links = [link.get("href") for link in main_soup.find_all("a") if link.get("href")]
            self.links.extend(page_links)

            # 4. Process iframes
            iframes = main_soup.find_all("iframe")
            for iframe in iframes:
                src = iframe.get("src")
                if src:
                    iframe_url = urljoin(self.url, src)
                    # Open the iframe in a new browser tab
                    driver.execute_script(f"window.open('{iframe_url}', '_blank');")
                    driver.switch_to.window(driver.window_handles[-1])
                    time.sleep(2)

                    # Scroll inside the iframe
                    self._scroll_down_up(driver, scroll_pause_time=2.0, scroll_up_amount=500)

                    # Parse the fully loaded iframe content
                    iframe_soup = BeautifulSoup(driver.page_source, "html.parser")
                    if iframe_soup.body:
                        # Again, remove script, style, img, input
                        for irrelevant in iframe_soup.body(["script", "style", "img", "input"]):
                            irrelevant.decompose()

                        # Collect text
                        iframe_text = iframe_soup.body.get_text(separator="\n", strip=True)
                        self.text += "\n" + iframe_text

                        # Collect links from the iframe
                        iframe_links = [a.get("href") for a in iframe_soup.find_all("a") if a.get("href")]
                        self.links.extend(iframe_links)

                    # Close the new tab and switch back to the main page
                    driver.close()
                    driver.switch_to.window(driver.window_handles[0])

        finally:
            driver.quit()

    def get_contents(self):
        # Return the raw text plus any discovered links
        return (
            f"Webpage Title:\n{self.title}\n"
            f"Webpage Contents:\n{self.text}\n\n"
        )

if __name__ == "__main__":
    site = Website("https://hrpro.gr/recruiters-50-powerlist-2024/")
    print(site.get_contents())
    print(site.links)
