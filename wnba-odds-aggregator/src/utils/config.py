import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    ODDS_API_KEY = os.getenv('ODDS_API_KEY')
    ODDS_API_BASE_URL = os.getenv('ODDS_API_BASE_URL', 'https://api.the-odds-api.com/v4')
    API_RATE_LIMIT_REQUESTS = int(os.getenv('API_RATE_LIMIT_REQUESTS', 500))
    API_RATE_LIMIT_PERIOD = int(os.getenv('API_RATE_LIMIT_PERIOD', 2592000))
    DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///wnba_odds.db')
    DATABASE_BACKUP_ENABLED = os.getenv('DATABASE_BACKUP_ENABLED', 'true').lower() == 'true'
    DATABASE_BACKUP_INTERVAL = int(os.getenv('DATABASE_BACKUP_INTERVAL', 86400))
    SCRAPER_DELAY = int(os.getenv('SCRAPER_DELAY', 2))
    SCRAPER_USER_AGENT = os.getenv('SCRAPER_USER_AGENT', 'WNBAOddsAggregator/1.0')
    SCRAPER_TIMEOUT = int(os.getenv('SCRAPER_TIMEOUT', 30))
    SCRAPER_MAX_RETRIES = int(os.getenv('SCRAPER_MAX_RETRIES', 3))
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('LOG_FILE', 'wnba_odds.log')
    LOG_MAX_SIZE = int(os.getenv('LOG_MAX_SIZE', 10485760))
    LOG_BACKUP_COUNT = int(os.getenv('LOG_BACKUP_COUNT', 5))
    ENABLE_HEALTH_CHECKS = os.getenv('ENABLE_HEALTH_CHECKS', 'true').lower() == 'true'
    HEALTH_CHECK_INTERVAL = int(os.getenv('HEALTH_CHECK_INTERVAL', 3600))
    ALERT_EMAIL = os.getenv('ALERT_EMAIL', '') 