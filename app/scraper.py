import requests
from bs4 import BeautifulSoup
import time
import random
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_URL = "https://www.dotabuff.com/heroes/"

# List of realistic User-Agents to rotate through
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
]

def scrape_hero(hero_name: str, max_retries: int = 3) -> dict:
    """
    Fetch and scrape Dotabuff hero page with retry logic and anti-detection measures.
    hero_name must be lowercase, dash-separated (e.g. 'ogre-magi').
    Returns: { "best_against": [...], "worst_against": [...] }
    """
    url = f"{BASE_URL}{hero_name}"
    
    # Create a session with retry strategy
    session = requests.Session()
    retry_strategy = Retry(
        total=max_retries,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    for attempt in range(max_retries):
        try:
            # Random delay between requests to avoid rate limiting
            if attempt > 0:
                delay = random.uniform(1, 3)  # 1-3 seconds delay (reduced for performance)
                time.sleep(delay)
            
            # Use simpler, more conservative headers
            headers = {
                "User-Agent": random.choice(USER_AGENTS),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
            
            resp = session.get(url, headers=headers, timeout=15)
            
            if resp.status_code == 200:
                return parse_hero_data(resp.text)
            elif resp.status_code == 403:
                print(f"403 error on attempt {attempt + 1} for {hero_name}")
                if attempt == max_retries - 1:
                    print(f"Max retries reached for {hero_name}, returning empty data")
                    return {"best_against": [], "worst_against": []}
            else:
                print(f"Unexpected status code {resp.status_code} for {hero_name}")
                if attempt == max_retries - 1:
                    return {"best_against": [], "worst_against": []}
                
        except requests.exceptions.RequestException as e:
            print(f"Request error on attempt {attempt + 1} for {hero_name}: {e}")
            if attempt == max_retries - 1:
                return {"best_against": [], "worst_against": []}
    
    return {"best_against": [], "worst_against": []}

def parse_hero_data(html_content: str) -> dict:
    """Parse HTML content and extract hero data"""
    soup = BeautifulSoup(html_content, "html.parser")
    data = {"best_against": [], "worst_against": []}

    # Find "Best Versus" section
    headers = soup.find_all("header")
    for header in headers:
        if "Best Versus" in header.get_text():
            best_table = header.find_next("table")
            if best_table:
                # Use a set to avoid duplicates
                best_heroes = set()
                for link in best_table.select("a.link-type-hero"):
                    hero_name_from_url = link["href"].split("/")[-1]
                    best_heroes.add(hero_name_from_url)
                data["best_against"] = list(best_heroes)
            break

    # Find "Worst Versus" section
    for header in headers:
        if "Worst Versus" in header.get_text():
            worst_table = header.find_next("table")
            if worst_table:
                # Use a set to avoid duplicates
                worst_heroes = set()
                for link in worst_table.select("a.link-type-hero"):
                    hero_name_from_url = link["href"].split("/")[-1]
                    worst_heroes.add(hero_name_from_url)
                data["worst_against"] = list(worst_heroes)
            break

    return data
