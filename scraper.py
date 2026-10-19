import time
import socket
import ipaddress
from urllib.parse import urlparse
import requests
import streamlit as st
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, Page

def is_safe_url(url: str, allow_unresolved: bool = True) -> bool:
    """
    Validates that a URL is a safe public HTTP or HTTPS URL.
    Blocks SSRF targets including loopback, local network, link-local (cloud metadata),
    and non-HTTP schemes (file://, javascript:, data:, etc.).
    """
    if not url or not isinstance(url, str):
        return False
        
    try:
        parsed = urlparse(url.strip())
        if parsed.scheme.lower() not in ("http", "https"):
            return False
            
        hostname = parsed.hostname
        if not hostname:
            return False
            
        hostname_lower = hostname.lower()
        
        # Block localhost and local development aliases
        blocked_names = {
            "localhost", "localhost.localdomain", "broadcasthost",
            "metadata.google.internal", "instance-data"
        }
        if hostname_lower in blocked_names:
            return False
            
        if hostname_lower.endswith((".localhost", ".local", ".internal")):
            return False
            
        # Check if the hostname is a direct IP address
        try:
            ip = ipaddress.ip_address(hostname_lower)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                return False
            return True
        except ValueError:
            pass
            
        # For domain names, resolve to IP addresses and ensure none point to internal/metadata IPs
        try:
            addr_info = socket.getaddrinfo(hostname, None)
            for item in addr_info:
                ip = ipaddress.ip_address(item[4][0])
                if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                    return False
        except (socket.gaierror, socket.herror, OSError):
            # If DNS lookup is unavailable (e.g. offline sandbox), permit domains with a valid structure
            if allow_unresolved and "." in hostname_lower:
                return True
            return False
            
        return True
    except Exception:
        return False

def scrape_job_text(url: str, page: Page = None) -> str:
    """Robust scraper using requests with a Playwright fallback. Enforces SSRF and scheme validation."""
    if not is_safe_url(url):
        return f"Error: Disallowed or unsafe URL ({url}). Only public HTTP/HTTPS URLs are allowed."

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    
    # 1. OPTIMIZED BATCH MODE: If an active Playwright page is passed, use it directly
    if page:
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=15000)
            current_url = getattr(page, "url", None)
            if isinstance(current_url, str) and current_url and not is_safe_url(current_url):
                return f"Error: URL redirected to a disallowed address: {current_url}"
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
        response = requests.get(url, headers=headers, timeout=8, allow_redirects=True)
        # Ensure redirect target didn't pivot to a disallowed internal URL
        if not is_safe_url(response.url):
            return f"Error: URL redirected to a disallowed address: {response.url}"
            
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
            temp_page.goto(url, wait_until="domcontentloaded", timeout=15000)
            current_url = getattr(temp_page, "url", None)
            if isinstance(current_url, str) and current_url and not is_safe_url(current_url):
                browser.close()
                return f"Error: URL redirected to a disallowed address: {current_url}"
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
    """Attempts to auto-discover job links from ANY job board search page with URL validation."""
    if not is_safe_url(search_url):
        try:
            from streamlit.runtime.scriptrunner import get_script_run_ctx
            if get_script_run_ctx(suppress_warning=True) is not None:
                st.error("Error: Disallowed or unsafe search URL. Only public HTTP/HTTPS URLs are allowed.")
            else:
                print(f"[Scraper Error] Disallowed or unsafe search URL: {search_url}")
        except Exception:
            print(f"[Scraper Error] Disallowed or unsafe search URL: {search_url}")
        return []

    job_urls = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            
            # Tell Playwright not to wait for background analytics/ads
            page.goto(search_url, wait_until="domcontentloaded", timeout=20000)
            
            # Wait specifically for links to appear
            page.wait_for_selector("a", timeout=10000)
            
            all_links = page.eval_on_selector_all("a", "elements => elements.map(e => e.href)")
            valid_keywords = [
                '/job/', '/jobs/', '/careers/', '/posting/', '/position/',
                'reqid=', '/role/', '/opening/', '/openings/', '/opportunity/',
                '/opportunities/', '/remote-jobs/', '/remote-job/'
            ]
            
            for link in all_links:
                if any(keyword in link.lower() for keyword in valid_keywords):
                    if is_safe_url(link):
                        job_urls.append(link)
                    
            job_urls = list(dict.fromkeys(job_urls))
            browser.close()
    except Exception as e:
        try:
            from streamlit.runtime.scriptrunner import get_script_run_ctx
            if get_script_run_ctx(suppress_warning=True) is not None:
                st.error(f"Error scraping search page: {str(e)}")
            else:
                print(f"[Scraper Error] Error scraping search page: {str(e)}")
        except Exception:
            print(f"[Scraper Error] Error scraping search page: {str(e)}")
        
    return job_urls