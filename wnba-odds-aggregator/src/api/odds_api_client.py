import requests
import time
from utils.config import Config

class RateLimiter:
    def __init__(self, calls=500, period=2592000):
        self.calls = calls
        self.period = period
        self.calls_made = 0
        self.start_time = time.time()

    def wait(self):
        if self.calls_made >= self.calls:
            elapsed = time.time() - self.start_time
            if elapsed < self.period:
                time.sleep(self.period - elapsed)
            self.calls_made = 0
            self.start_time = time.time()
        self.calls_made += 1

class OddsAPIClient:
    def __init__(self):
        self.base_url = Config.ODDS_API_BASE_URL
        self.api_key = Config.ODDS_API_KEY
        self.rate_limiter = RateLimiter(calls=Config.API_RATE_LIMIT_REQUESTS, period=Config.API_RATE_LIMIT_PERIOD)

    def get_odds(self, sport='basketball_wnba'):
        self.rate_limiter.wait()
        url = f"{self.base_url}/sports/{sport}/odds"
        params = {
            'apiKey': self.api_key,
            'regions': 'us',
            'markets': 'h2h,spreads,totals'
        }
        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"API error: {e}")
            return None

    def parse_api_response(self, response):
        # Flatten the API response to match the odds table schema
        if not response:
            return []
        records = []
        for game in response:
            game_id = game.get('id')
            commence_time = game.get('commence_time')
            home_team = game.get('home_team')
            away_team = game.get('away_team')
            sport = game.get('sport_key', 'basketball_wnba')
            for bookmaker in game.get('bookmakers', []):
                bookmaker_name = bookmaker.get('title')
                for market in bookmaker.get('markets', []):
                    market_key = market.get('key')
                    last_update = market.get('last_update')
                    outcomes = {o['name']: o for o in market.get('outcomes', [])}
                    record = {
                        'game_id': game_id,
                        'sport': sport,
                        'commence_time': commence_time,
                        'home_team': home_team,
                        'away_team': away_team,
                        'bookmaker': bookmaker_name,
                        'market_key': market_key,
                        'price_home': outcomes.get(home_team, {}).get('price'),
                        'point_home': outcomes.get(home_team, {}).get('point'),
                        'price_away': outcomes.get(away_team, {}).get('price'),
                        'point_away': outcomes.get(away_team, {}).get('point'),
                        'last_update': last_update,
                        'source': 'api',
                        'data_quality_score': 1.0
                    }
                    records.append(record)
        return records 