"""
WNBA Historical Odds Scraper
Scrapes historical WNBA odds from free sources like SportsOddsHistory.com
and other publicly available archives

Usage:
    python wnba_historical_odds_scraper.py --year 2024
    python wnba_historical_odds_scraper.py --start-year 2021 --end-year 2024
"""

import os
import sys
import requests
import pandas as pd
from bs4 import BeautifulSoup
import time
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging
import re

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class WNBAHistoricalOddsScraper:
    """Scrapes historical WNBA odds from free sources"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.base_url = "https://www.sportsoddshistory.com"
        
    def get_wnba_seasons_available(self) -> List[int]:
        """Check what WNBA seasons are available on SportsOddsHistory"""
        try:
            # Try to access the WNBA section
            wnba_url = f"{self.base_url}/wnba/"
            response = self.session.get(wnba_url)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Look for season links or data
                season_links = soup.find_all('a', href=re.compile(r'wnba.*\d{4}'))
                seasons = []
                
                for link in season_links:
                    match = re.search(r'(\d{4})', link.get('href', ''))
                    if match:
                        year = int(match.group(1))
                        if year not in seasons and 2020 <= year <= 2025:
                            seasons.append(year)
                
                return sorted(seasons, reverse=True)
            else:
                logger.warning(f"Could not access WNBA section: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Error checking available seasons: {e}")
            return []
    
    def scrape_wnba_season_odds(self, year: int) -> List[Dict]:
        """
        Scrape WNBA odds for a specific season
        
        Args:
            year: Season year to scrape
            
        Returns:
            List of odds records
        """
        logger.info(f"Scraping WNBA odds for {year} season...")
        
        odds_data = []
        
        try:
            # Try different URL patterns for WNBA data
            possible_urls = [
                f"{self.base_url}/wnba/{year}/",
                f"{self.base_url}/wnba-{year}/",
                f"{self.base_url}/basketball/wnba/{year}/",
                f"{self.base_url}/wnba/{year}-odds/"
            ]
            
            for url in possible_urls:
                try:
                    response = self.session.get(url)
                    if response.status_code == 200:
                        logger.info(f"Found WNBA data at: {url}")
                        odds_data.extend(self._parse_season_page(response.content, year))
                        break
                        
                except Exception as e:
                    continue
                    
            if not odds_data:
                logger.warning(f"No WNBA odds data found for {year}")
                
        except Exception as e:
            logger.error(f"Error scraping {year} season: {e}")
            
        return odds_data
    
    def _parse_season_page(self, html_content: bytes, year: int) -> List[Dict]:
        """Parse WNBA season page for odds data"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            odds_records = []
            
            # Look for tables with odds data
            tables = soup.find_all('table')
            
            for table in tables:
                rows = table.find_all('tr')
                
                for row in rows[1:]:  # Skip header row
                    cells = row.find_all(['td', 'th'])
                    
                    if len(cells) >= 4:  # Need at least date, teams, odds
                        try:
                            # Extract game information
                            record = self._extract_game_odds(cells, year)
                            if record:
                                odds_records.append(record)
                                
                        except Exception as e:
                            continue
            
            return odds_records
            
        except Exception as e:
            logger.error(f"Error parsing season page: {e}")
            return []
    
    def _extract_game_odds(self, cells: List, year: int) -> Optional[Dict]:
        """Extract odds information from table cells"""
        try:
            # Basic structure - adjust based on actual site format
            # This is a template that would need to be adjusted based on
            # the actual structure of SportsOddsHistory.com
            
            record = {
                'year': year,
                'date': None,
                'home_team': None,
                'away_team': None,
                'home_odds': None,
                'away_odds': None,
                'spread': None,
                'total': None,
                'source': 'SportsOddsHistory'
            }
            
            # Extract date (adjust index based on actual table structure)
            if len(cells) > 0:
                date_text = cells[0].get_text(strip=True)
                record['date'] = self._parse_date(date_text, year)
            
            # Extract teams (adjust based on actual format)
            if len(cells) > 1:
                team_text = cells[1].get_text(strip=True)
                teams = self._parse_teams(team_text)
                if teams:
                    record['away_team'] = teams.get('away')
                    record['home_team'] = teams.get('home')
            
            # Extract odds (adjust based on actual format)
            if len(cells) > 2:
                odds_text = cells[2].get_text(strip=True)
                odds = self._parse_odds(odds_text)
                record.update(odds)
            
            return record if record['date'] and record['home_team'] else None
            
        except Exception as e:
            return None
    
    def _parse_date(self, date_text: str, year: int) -> Optional[str]:
        """Parse date string into standardized format"""
        try:
            # Common date formats to handle
            date_patterns = [
                r'(\d{1,2})/(\d{1,2})/(\d{4})',  # MM/DD/YYYY
                r'(\d{1,2})-(\d{1,2})-(\d{4})',  # MM-DD-YYYY
                r'(\w+)\s+(\d{1,2}),?\s+(\d{4})',  # Month DD, YYYY
                r'(\d{1,2})/(\d{1,2})',  # MM/DD (assume current year)
            ]
            
            for pattern in date_patterns:
                match = re.search(pattern, date_text)
                if match:
                    if len(match.groups()) == 3:
                        if pattern.endswith('(\\d{4})'):
                            # Full year provided
                            month, day, year_found = match.groups()
                            if pattern.startswith(r'(\w+)'):
                                # Handle month name
                                month_names = {
                                    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4,
                                    'may': 5, 'jun': 6, 'jul': 7, 'aug': 8,
                                    'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
                                }
                                month = month_names.get(month.lower()[:3], 1)
                            
                            return f"{year_found}-{int(month):02d}-{int(day):02d}"
                        else:
                            month, day = match.groups()[:2]
                            return f"{year}-{int(month):02d}-{int(day):02d}"
            
            return None
            
        except Exception:
            return None
    
    def _parse_teams(self, team_text: str) -> Optional[Dict]:
        """Parse team information from text"""
        try:
            # Common patterns for team matchups
            patterns = [
                r'(.+?)\s+@\s+(.+)',  # Away @ Home
                r'(.+?)\s+at\s+(.+)',  # Away at Home
                r'(.+?)\s+vs\.?\s+(.+)',  # Team1 vs Team2
                r'(.+?)\s+-\s+(.+)',  # Team1 - Team2
            ]
            
            for pattern in patterns:
                match = re.search(pattern, team_text, re.IGNORECASE)
                if match:
                    away, home = match.groups()
                    return {
                        'away': away.strip(),
                        'home': home.strip()
                    }
            
            return None
            
        except Exception:
            return None
    
    def _parse_odds(self, odds_text: str) -> Dict:
        """Parse odds information from text"""
        try:
            odds_data = {
                'home_odds': None,
                'away_odds': None,
                'spread': None,
                'total': None
            }
            
            # Look for moneyline odds
            ml_pattern = r'([+-]?\d+)'
            ml_matches = re.findall(ml_pattern, odds_text)
            
            if len(ml_matches) >= 2:
                odds_data['away_odds'] = int(ml_matches[0])
                odds_data['home_odds'] = int(ml_matches[1])
            
            # Look for spread
            spread_pattern = r'([+-]?\d+\.?\d*)\s*spread'
            spread_match = re.search(spread_pattern, odds_text, re.IGNORECASE)
            if spread_match:
                odds_data['spread'] = float(spread_match.group(1))
            
            # Look for total
            total_pattern = r'(\d+\.?\d*)\s*total'
            total_match = re.search(total_pattern, odds_text, re.IGNORECASE)
            if total_match:
                odds_data['total'] = float(total_match.group(1))
            
            return odds_data
            
        except Exception:
            return {}
    
    def scrape_alternative_sources(self, year: int) -> List[Dict]:
        """Try alternative sources for WNBA odds data"""
        logger.info(f"Checking alternative sources for {year} WNBA odds...")
        
        odds_data = []
        
        # Alternative source: OddsPortal archive (if available)
        try:
            oddsportal_url = f"https://www.oddsportal.com/basketball/usa/wnba-{year}/results/"
            response = self.session.get(oddsportal_url)
            
            if response.status_code == 200:
                logger.info(f"Found OddsPortal data for {year}")
                # Parse OddsPortal format (would need specific parsing logic)
                
        except Exception as e:
            logger.debug(f"OddsPortal not available for {year}: {e}")
        
        return odds_data
    
    def save_odds_data(self, odds_data: List[Dict], filename: str = None) -> str:
        """Save scraped odds data to files"""
        if not odds_data:
            logger.warning("No odds data to save")
            return ""
        
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"wnba_historical_odds_{timestamp}"
        
        # Create data directory
        data_dir = "data/odds"
        os.makedirs(data_dir, exist_ok=True)
        
        # Convert to DataFrame
        df = pd.DataFrame(odds_data)
        
        # Save as both CSV and parquet
        csv_path = os.path.join(data_dir, f"{filename}.csv")
        parquet_path = os.path.join(data_dir, f"{filename}.parquet")
        
        df.to_csv(csv_path, index=False)
        df.to_parquet(parquet_path, index=False)
        
        logger.info(f"Saved {len(df)} records to {csv_path} and {parquet_path}")
        return parquet_path

def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(description="Scrape historical WNBA odds data")
    parser.add_argument("--year", type=int, help="Single year to scrape")
    parser.add_argument("--start-year", type=int, default=2021, help="Start year for range")
    parser.add_argument("--end-year", type=int, default=2024, help="End year for range")
    parser.add_argument("--output", help="Output filename (without extension)")
    
    args = parser.parse_args()
    
    scraper = WNBAHistoricalOddsScraper()
    
    try:
        # Check available seasons
        available_seasons = scraper.get_wnba_seasons_available()
        logger.info(f"Available WNBA seasons: {available_seasons}")
        
        all_odds_data = []
        
        if args.year:
            # Scrape single year
            years_to_scrape = [args.year]
        else:
            # Scrape range
            years_to_scrape = list(range(args.start_year, args.end_year + 1))
        
        for year in years_to_scrape:
            logger.info(f"Processing {year} season...")
            
            # Try main source
            season_odds = scraper.scrape_wnba_season_odds(year)
            
            # Try alternative sources if main source has no data
            if not season_odds:
                season_odds = scraper.scrape_alternative_sources(year)
            
            all_odds_data.extend(season_odds)
            
            # Be respectful - add delay between requests
            time.sleep(2)
        
        if all_odds_data:
            file_path = scraper.save_odds_data(all_odds_data, args.output)
            
            # Print summary
            df = pd.DataFrame(all_odds_data)
            print(f"\n=== WNBA HISTORICAL ODDS SUMMARY ===")
            print(f"Total records: {len(df)}")
            print(f"Years covered: {sorted(df['year'].unique())}")
            print(f"Date range: {df['date'].min()} to {df['date'].max()}")
            if 'source' in df.columns:
                print(f"Sources: {', '.join(df['source'].unique())}")
            print(f"Data saved to: {file_path}")
        else:
            logger.warning("No WNBA odds data found for the specified years")
            
    except Exception as e:
        logger.error(f"Error in main execution: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()