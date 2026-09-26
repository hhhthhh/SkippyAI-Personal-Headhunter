import time
import requests
import streamlit as st
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, Page

def scrape_job_text(url: str, page: Page = None) -> str:
    """Robust scraper using requests with a Playwright fallback. Accepts an existing Page to improve batch performance."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    
    # 1. OPTIMIZED BATCH MODE: If an active Playwright page is passed, use it directly
    if page:
        try:
            page.goto(url, timeout=15000)
            page.wait_for_load_state("domcontentloaded")
            html_content = page.content()
            soup = BeautifulSoup(html_content, "html.parser")
            for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
                element.extract()
            text = soup.get_text(separator="\n")
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            return "\n".join(lines)
        except Exception as e:
            return f"Error scraping URL via persistent browser context: {str(e)}"

    # 2. STANDARD / MANUAL MODE: Attempt fast static fetch first
    try:
        response = requests.get(url, headers=headers, timeout=8)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
                element.extract()
            text = soup.get_text(separator="\n")
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            cleaned_text = "\n".join(lines)
            if len(cleaned_text) > 300:
                return cleaned_text
    except Exception:
        pass  

    # 3. MANUAL MODE FALLBACK: Spin up a temporary headless browser
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            temp_page = browser.new_page(user_agent=headers["User-Agent"])
            temp_page.goto(url, timeout=15000)
            temp_page.wait_for_load_state("domcontentloaded")
            html_content = temp_page.content()
            browser.close()
            
            soup = BeautifulSoup(html_content, "html.parser")
            for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
                element.extract()
            text = soup.get_text(separator="\n")
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            return "\n".join(lines)
    except Exception as e:
        return f"Error scraping URL via temporary browser: {str(e)}"

def scrape_universal_search_results(search_url: str) -> list[str]:
    """Attempts to auto-discover job links from ANY job board search page."""
    job_urls = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            page.goto(search_url, timeout=20000)
            page.wait_for_load_state("domcontentloaded")
            time.sleep(3)
            
            all_links = page.eval_on_selector_all("a", "elements => elements.map(e => e.href)")
            valid_keywords = ['/job/', '/jobs/', '/careers/', '/posting/', '/position/', 'reqid=', '/role/']
            
            for link in all_links:
                if any(keyword in link.lower() for keyword in valid_keywords):
                    job_urls.append(link)
                    
            job_urls = list(dict.fromkeys(job_urls))
            browser.close()
    except Exception as e:
        st.error(f"Error scraping search page: {str(e)}")
        
    return job_urls