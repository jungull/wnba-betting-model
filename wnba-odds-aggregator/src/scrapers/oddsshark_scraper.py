import requests
import time
from utils.config import Config

class RateLimiter:
    def __init__(self, calls=1, period=2):
        self.calls = calls
        self.period = period
        self.last_call = 0

    def wait(self):
        now = time.time()
        elapsed = now - self.last_call
        if elapsed < self.period:
            time.sleep(self.period - elapsed)
        self.last_call = time.time()

class OddsSharkScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': Config.SCRAPER_USER_AGENT})
        self.rate_limiter = RateLimiter(calls=1, period=Config.SCRAPER_DELAY)

    def scrape_with_retry(self, url, max_retries=3):
        for attempt in range(max_retries):
            try:
                self.rate_limiter.wait()
                response = self.session.get(url, timeout=Config.SCRAPER_TIMEOUT)
                response.raise_for_status()
                return response.text
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise e

    def extract_odds_data(self, html):
        # TODO: Implement HTML parsing and data extraction
        pass 