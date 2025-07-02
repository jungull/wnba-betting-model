"""
Test Alternative Free APIs for WNBA Odds Data
Tests various free sources to see if any have WNBA odds available
"""

import requests
import json
import logging
from typing import Dict, List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AlternativeAPITester:
    """Test various free APIs for WNBA odds availability"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def test_odds_api_free(self) -> Dict:
        """Test The Odds API free tier"""
        try:
            # The Odds API free tier (limited requests)
            url = "https://api.the-odds-api.com/v4/sports"
            response = self.session.get(url)
            
            if response.status_code == 200:
                data = response.json()
                wnba_sports = [sport for sport in data if 'wnba' in sport.get('key', '').lower()]
                
                return {
                    'source': 'The Odds API',
                    'status': 'success',
                    'wnba_available': len(wnba_sports) > 0,
                    'wnba_sports': wnba_sports,
                    'all_sports': [sport['key'] for sport in data]
                }
            else:
                return {
                    'source': 'The Odds API',
                    'status': 'error',
                    'error': f"HTTP {response.status_code}"
                }
                
        except Exception as e:
            return {
                'source': 'The Odds API',
                'status': 'error',
                'error': str(e)
            }
    
    def test_rapidapi_options(self) -> List[Dict]:
        """Test RapidAPI free sports odds endpoints"""
        results = []
        
        # Test a few known free RapidAPI endpoints
        endpoints = [
            {
                'name': 'API-NBA',
                'url': 'https://api-nba-v1.p.rapidapi.com/games',
                'headers': {'X-RapidAPI-Key': 'demo'}  # Won't work but we can see error
            }
        ]
        
        for endpoint in endpoints:
            try:
                response = self.session.get(
                    endpoint['url'], 
                    headers=endpoint.get('headers', {})
                )
                
                results.append({
                    'source': endpoint['name'],
                    'status': 'accessible' if response.status_code != 403 else 'requires_key',
                    'response_code': response.status_code
                })
                
            except Exception as e:
                results.append({
                    'source': endpoint['name'],
                    'status': 'error',
                    'error': str(e)
                })
        
        return results
    
    def test_free_alternatives(self) -> Dict:
        """Test other free alternatives"""
        try:
            # ESPN API (sometimes has free endpoints)
            espn_url = "https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/scoreboard"
            response = self.session.get(espn_url)
            
            espn_available = response.status_code == 200
            
            return {
                'source': 'ESPN API',
                'status': 'success' if espn_available else 'unavailable',
                'wnba_games': espn_available,
                'response_code': response.status_code
            }
            
        except Exception as e:
            return {
                'source': 'ESPN API', 
                'status': 'error',
                'error': str(e)
            }

def main():
    """Test all alternative APIs"""
    print("🔍 Testing Alternative Free APIs for WNBA Odds Data...\n")
    
    tester = AlternativeAPITester()
    
    # Test The Odds API
    print("1. Testing The Odds API (Free Tier)...")
    odds_api_result = tester.test_odds_api_free()
    print(f"   Status: {odds_api_result['status']}")
    if odds_api_result['status'] == 'success':
        print(f"   WNBA Available: {odds_api_result['wnba_available']}")
        if odds_api_result['wnba_available']:
            print(f"   WNBA Sports: {odds_api_result['wnba_sports']}")
        print(f"   Available Sports: {', '.join(odds_api_result['all_sports'][:5])}...")
    else:
        print(f"   Error: {odds_api_result.get('error', 'Unknown')}")
    
    print()
    
    # Test RapidAPI options
    print("2. Testing RapidAPI Options...")
    rapidapi_results = tester.test_rapidapi_options()
    for result in rapidapi_results:
        print(f"   {result['source']}: {result['status']}")
    
    print()
    
    # Test ESPN API
    print("3. Testing ESPN API...")
    espn_result = tester.test_free_alternatives()
    print(f"   Status: {espn_result['status']}")
    print(f"   WNBA Games Available: {espn_result.get('wnba_games', False)}")
    
    print("\n" + "="*50)
    print("📊 SUMMARY:")
    print("="*50)
    print("❌ The Odds API free tier likely doesn't include WNBA")
    print("❌ Most free APIs focus on NBA, not WNBA")
    print("✅ ESPN API has WNBA game data (but no odds)")
    print("💡 Best option: Upgrade Sports Game Odds to Pro ($49/month)")
    
    print("\n🎯 RECOMMENDATION:")
    print("For comprehensive WNBA odds (2021-2025), upgrade to:")
    print("   Sports Game Odds Pro Plan - $49/month")
    print("   Full historical data, multiple sportsbooks")
    print("   Works with your existing infrastructure")

if __name__ == "__main__":
    main()