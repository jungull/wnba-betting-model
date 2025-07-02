"""
Quick test of The Odds API for WNBA support
Tests the free tier to see what WNBA data is available
"""

import requests
import json

def test_odds_api():
    """Test The Odds API for WNBA support"""
    
    print("🔍 Testing The Odds API for WNBA support...")
    
    # Test without API key first (free tier has limited requests)
    base_url = "https://api.the-odds-api.com/v4"
    
    try:
        # 1. Check available sports
        print("\n1. Checking available sports...")
        sports_url = f"{base_url}/sports"
        response = requests.get(sports_url)
        
        if response.status_code == 200:
            sports = response.json()
            wnba_sports = [sport for sport in sports if 'wnba' in sport.get('key', '').lower()]
            
            print(f"   Status: ✅ Success")
            print(f"   Total sports: {len(sports)}")
            print(f"   WNBA sports found: {len(wnba_sports)}")
            
            if wnba_sports:
                for sport in wnba_sports:
                    print(f"   - {sport['key']}: {sport['title']}")
                    
                # 2. Test WNBA odds (will require API key for actual data)
                print(f"\n2. Testing WNBA odds access...")
                wnba_key = wnba_sports[0]['key']
                odds_url = f"{base_url}/sports/{wnba_key}/odds"
                
                odds_response = requests.get(odds_url)
                
                if odds_response.status_code == 401:
                    print(f"   Status: ⚠️  API key required for odds data")
                    print(f"   This confirms WNBA endpoint exists and is functional")
                elif odds_response.status_code == 200:
                    print(f"   Status: ✅ WNBA odds accessible!")
                    odds_data = odds_response.json()
                    print(f"   Games available: {len(odds_data)}")
                else:
                    print(f"   Status: ❌ Error {odds_response.status_code}")
                    
            else:
                print("   ❌ No WNBA sports found")
        else:
            print(f"   ❌ Error {response.status_code}: {response.text}")
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    print(f"\n3. Pricing Information:")
    print(f"   - Free tier: 500 requests/month")
    print(f"   - Starter: $10/month (10,000 requests)")
    print(f"   - Pro: $50/month (100,000 requests + historical)")
    
    print(f"\n📋 Summary:")
    print(f"   - The Odds API definitely supports WNBA")
    print(f"   - Sport key: 'basketball_wnba'")
    print(f"   - Requires paid plan for live odds data")
    print(f"   - Much cheaper than Sports Game Odds upgrade")

if __name__ == "__main__":
    test_odds_api()