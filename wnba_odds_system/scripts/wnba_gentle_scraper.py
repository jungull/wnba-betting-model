"""
WNBA Gentle Scraper - Start Here!
Conservative scraper that respects rate limits and collects data gradually

This script is designed to start collecting WNBA odds data immediately while being
respectful to servers and avoiding rate limiting issues.

Usage:
    python wnba_gentle_scraper.py --start-collection
"""

import os
import sys
import requests
import pandas as pd
from bs4 import BeautifulSoup
import time
import json
from datetime import datetime
from typing import Dict, List, Optional
import logging
import random

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class WNBAGentleScraper:
    """Conservative WNBA scraper that starts collecting data immediately"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Connection': 'keep-alive',
        })
        self.data_dir = "data/odds"
        os.makedirs(self.data_dir, exist_ok=True)
        self.collected_data = []
    
    def gentle_request(self, url: str, delay: float = 8.0) -> Optional[requests.Response]:
        """Make a gentle request with appropriate delays"""
        try:
            logger.info(f"🌐 Fetching: {url}")
            
            # Random delay between 8-12 seconds to be extra respectful
            actual_delay = random.uniform(delay, delay + 4)
            logger.info(f"⏳ Waiting {actual_delay:.1f}s before request...")
            time.sleep(actual_delay)
            
            response = self.session.get(url, timeout=30)
            
            if response.status_code == 200:
                logger.info(f"✅ Success: {response.status_code}")
                return response
            elif response.status_code == 429:
                logger.warning(f"🚦 Rate limited. Waiting 60 seconds...")
                time.sleep(60)
                return None
            else:
                logger.warning(f"⚠️  HTTP {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Request failed: {e}")
            return None
    
    def collect_current_2025_data(self) -> List[Dict]:
        """Collect current 2025 WNBA season data from accessible sources"""
        logger.info("🎯 Starting gentle collection of 2025 WNBA data...")
        
        # Start with most accessible sources
        sources_to_try = [
            {
                'name': 'ESPN WNBA Standings',
                'url': 'https://www.espn.com/wnba/standings',
                'parser': self._parse_espn_standings
            },
            {
                'name': 'ESPN WNBA Scores', 
                'url': 'https://www.espn.com/wnba/scores',
                'parser': self._parse_espn_scores
            },
            {
                'name': 'WNBA Official Standings',
                'url': 'https://www.wnba.com/standings/',
                'parser': self._parse_wnba_official
            }
        ]
        
        all_data = []
        
        for source in sources_to_try:
            try:
                logger.info(f"📊 Trying {source['name']}...")
                response = self.gentle_request(source['url'])
                
                if response:
                    data = source['parser'](response.content)
                    if data:
                        all_data.extend(data)
                        logger.info(f"✅ Collected {len(data)} records from {source['name']}")
                    else:
                        logger.info(f"ℹ️  No data found in {source['name']}")
                else:
                    logger.warning(f"⚠️  Failed to access {source['name']}")
                    
            except Exception as e:
                logger.error(f"❌ Error with {source['name']}: {e}")
                continue
        
        self.collected_data.extend(all_data)
        return all_data
    
    def _parse_espn_standings(self, html_content: bytes) -> List[Dict]:
        """Parse ESPN WNBA standings for team data"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            data = []
            
            # Look for standings table
            tables = soup.find_all('table')
            for table in tables:
                rows = table.find_all('tr')
                
                for row in rows[1:]:  # Skip header
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 3:
                        try:
                            team_cell = cells[0]
                            team_name = team_cell.get_text(strip=True)
                            
                            # Get wins/losses if available
                            wins = cells[1].get_text(strip=True) if len(cells) > 1 else None
                            losses = cells[2].get_text(strip=True) if len(cells) > 2 else None
                            
                            if team_name and any(wnba_team in team_name.lower() for wnba_team in [
                                'aces', 'dream', 'sky', 'sun', 'fever', 'sparks', 
                                'lynx', 'liberty', 'mercury', 'storm', 'wings', 'mystics'
                            ]):
                                data.append({
                                    'date': datetime.now().strftime('%Y-%m-%d'),
                                    'team': self._standardize_team_name(team_name),
                                    'wins': wins,
                                    'losses': losses,
                                    'source': 'ESPN_Standings',
                                    'data_type': 'standings'
                                })
                        except Exception as e:
                            logger.debug(f"Error parsing standings row: {e}")
                            continue
            
            return data
            
        except Exception as e:
            logger.error(f"Error parsing ESPN standings: {e}")
            return []
    
    def _parse_espn_scores(self, html_content: bytes) -> List[Dict]:
        """Parse ESPN WNBA scores for recent games"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            data = []
            
            # Look for game containers
            game_containers = soup.find_all('div', class_='game-strip') + soup.find_all('article')
            
            for container in game_containers[:10]:  # Limit to recent games
                try:
                    # Try to extract team names and scores
                    team_elements = container.find_all(['span', 'div'], text=True)
                    
                    teams_found = []
                    scores_found = []
                    
                    for elem in team_elements:
                        text = elem.get_text(strip=True)
                        
                        # Check if it's a team name
                        if any(wnba_team in text.lower() for wnba_team in [
                            'aces', 'dream', 'sky', 'sun', 'fever', 'sparks', 
                            'lynx', 'liberty', 'mercury', 'storm', 'wings', 'mystics',
                            'las vegas', 'atlanta', 'chicago', 'connecticut', 'indiana',
                            'los angeles', 'minnesota', 'new york', 'phoenix', 'seattle',
                            'dallas', 'washington'
                        ]):
                            teams_found.append(text)
                        
                        # Check if it's a score
                        if text.isdigit() and 50 <= int(text) <= 150:  # Reasonable WNBA score range
                            scores_found.append(int(text))
                    
                    if len(teams_found) >= 2:
                        data.append({
                            'date': datetime.now().strftime('%Y-%m-%d'),
                            'away_team': self._standardize_team_name(teams_found[0]),
                            'home_team': self._standardize_team_name(teams_found[1]),
                            'away_score': scores_found[0] if len(scores_found) > 0 else None,
                            'home_score': scores_found[1] if len(scores_found) > 1 else None,
                            'source': 'ESPN_Scores',
                            'data_type': 'game_result'
                        })
                        
                except Exception as e:
                    logger.debug(f"Error parsing game container: {e}")
                    continue
            
            return data
            
        except Exception as e:
            logger.error(f"Error parsing ESPN scores: {e}")
            return []
    
    def _parse_wnba_official(self, html_content: bytes) -> List[Dict]:
        """Parse official WNBA site for additional data"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            data = []
            
            # Look for any team or game data
            elements = soup.find_all(['div', 'span', 'td'], text=True)
            
            team_mentions = {}
            
            for elem in elements[:50]:  # Limit processing
                text = elem.get_text(strip=True)
                
                # Count team mentions for popularity/activity
                for team_key in ['aces', 'dream', 'sky', 'sun', 'fever', 'sparks', 
                               'lynx', 'liberty', 'mercury', 'storm', 'wings', 'mystics']:
                    if team_key in text.lower():
                        team_mentions[team_key] = team_mentions.get(team_key, 0) + 1
            
            # Convert mentions to data points
            for team_key, mentions in team_mentions.items():
                if mentions > 0:
                    data.append({
                        'date': datetime.now().strftime('%Y-%m-%d'),
                        'team': self._standardize_team_name(team_key),
                        'mentions': mentions,
                        'source': 'WNBA_Official',
                        'data_type': 'team_activity'
                    })
            
            return data
            
        except Exception as e:
            logger.error(f"Error parsing WNBA official: {e}")
            return []
    
    def _standardize_team_name(self, team_name: str) -> str:
        """Standardize team names across sources"""
        if not isinstance(team_name, str):
            return ""
        
        team_lower = team_name.lower().strip()
        
        # WNBA team mappings
        mappings = {
            'aces': 'Las Vegas Aces',
            'las vegas': 'Las Vegas Aces',
            'dream': 'Atlanta Dream',
            'atlanta': 'Atlanta Dream',
            'sky': 'Chicago Sky',
            'chicago': 'Chicago Sky',
            'sun': 'Connecticut Sun',
            'connecticut': 'Connecticut Sun',
            'fever': 'Indiana Fever',
            'indiana': 'Indiana Fever',
            'sparks': 'Los Angeles Sparks',
            'los angeles': 'Los Angeles Sparks',
            'lynx': 'Minnesota Lynx',
            'minnesota': 'Minnesota Lynx',
            'liberty': 'New York Liberty',
            'new york': 'New York Liberty',
            'mercury': 'Phoenix Mercury',
            'phoenix': 'Phoenix Mercury',
            'storm': 'Seattle Storm',
            'seattle': 'Seattle Storm',
            'wings': 'Dallas Wings',
            'dallas': 'Dallas Wings',
            'mystics': 'Washington Mystics',
            'washington': 'Washington Mystics',
            'valkyries': 'Golden State Valkyries',
            'golden state': 'Golden State Valkyries'
        }
        
        for key, standard_name in mappings.items():
            if key in team_lower:
                return standard_name
        
        return team_name.title()
    
    def save_progress(self, data: List[Dict] = None) -> str:
        """Save current progress to file"""
        if data is None:
            data = self.collected_data
        
        if not data:
            logger.warning("No data to save")
            return ""
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"wnba_gentle_collection_{timestamp}"
        
        # Convert to DataFrame
        df = pd.DataFrame(data)
        
        # Save as CSV
        csv_path = os.path.join(self.data_dir, f"{filename}.csv")
        df.to_csv(csv_path, index=False)
        
        # Save progress report
        report_path = os.path.join(self.data_dir, f"{filename}_report.json")
        report = {
            'collection_date': timestamp,
            'total_records': len(df),
            'sources': list(df['source'].unique()) if 'source' in df.columns else [],
            'data_types': list(df['data_type'].unique()) if 'data_type' in df.columns else [],
            'teams_found': list(df['team'].unique()) if 'team' in df.columns else []
        }
        
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"💾 Saved {len(df)} records to {csv_path}")
        self._print_progress_summary(df)
        
        return csv_path
    
    def _print_progress_summary(self, df: pd.DataFrame):
        """Print collection summary"""
        print(f"\n📊 WNBA DATA COLLECTION PROGRESS")
        print(f"{'='*50}")
        print(f"📅 Collection Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📦 Total Records: {len(df)}")
        
        if 'source' in df.columns:
            print(f"🔍 Sources: {', '.join(df['source'].unique())}")
        
        if 'data_type' in df.columns:
            print(f"📋 Data Types: {', '.join(df['data_type'].unique())}")
        
        if 'team' in df.columns:
            teams = df['team'].dropna().unique()
            print(f"🏀 Teams Found: {len(teams)} ({', '.join(teams[:5])}{'...' if len(teams) > 5 else ''})")
        
        print(f"\n✅ Data saved and ready for analysis!")
        print(f"🚀 Next: Run systematic historical collection")

def main():
    """Main execution function"""
    logger.info("🎯 WNBA Gentle Scraper - Starting Collection...")
    
    # Initialize scraper
    scraper = WNBAGentleScraper()
    
    try:
        # Collect current data
        current_data = scraper.collect_current_2025_data()
        
        if current_data:
            # Save progress
            output_file = scraper.save_progress(current_data)
            
            print(f"\n🎉 SUCCESS! Initial WNBA data collection complete!")
            print(f"📁 Data saved to: {output_file}")
            print(f"\n📋 NEXT STEPS:")
            print(f"1. Review the collected data")
            print(f"2. Run historical collection: python wnba_comprehensive_scraper.py --source oddsportal --years 2024-2024 --delay 10.0")
            print(f"3. Set up automated daily collection")
            
        else:
            logger.warning("⚠️  No data collected. Sites may be temporarily unavailable.")
            print("\n💡 ALTERNATIVE ACTIONS:")
            print("1. Try again in a few hours")
            print("2. Consider upgrading to The Odds API ($10/month)")
            print("3. Focus on manual data sources")
            
    except KeyboardInterrupt:
        logger.info("⏹️  Collection interrupted by user")
        if scraper.collected_data:
            scraper.save_progress()
            print("💾 Partial data saved")
    except Exception as e:
        logger.error(f"❌ Error during collection: {e}")
        print(f"\n🔧 TROUBLESHOOTING:")
        print(f"1. Check internet connection")
        print(f"2. Verify sites are accessible")
        print(f"3. Try running with longer delays")

if __name__ == "__main__":
    main()