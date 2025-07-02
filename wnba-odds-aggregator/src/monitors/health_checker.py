import os
import requests
from utils.config import Config
from utils.database import get_engine

class HealthChecker:
    def check_db(self):
        try:
            engine = get_engine()
            with engine.connect() as conn:
                conn.execute('SELECT 1')
            return True
        except Exception as e:
            return f'Database error: {e}'

    def check_api(self):
        try:
            response = requests.get(Config.ODDS_API_BASE_URL, timeout=10)
            return response.status_code == 200
        except Exception as e:
            return f'API error: {e}'

    def check_disk(self, path='.'):
        stat = os.statvfs(path)
        free = stat.f_bavail * stat.f_frsize
        if free < 100 * 1024 * 1024:  # less than 100MB
            return 'Low disk space'
        return True 