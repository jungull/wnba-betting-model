"""
Comprehensive WNBA Odds Scraper
Multi-source scraper for historical WNBA odds data (2021-2025)

Primary Sources:
- OddsPortal (2009+ historical data with odds)
- VegasInsider (current odds, multiple sportsbooks)  
- Doc's Sports (live odds comparison)
- BetInf.com (historical results by season)

Usage:
    python wnba_comprehensive_scraper.py --all-sources
    python wnba_comprehensive_scraper.py --source oddsportal --years 2021-2024
    python wnba_comprehensive_scraper.py --source vegasinsider --current-only
"""

import os
import sys
import requests
import pandas as pd
from bs4 import BeautifulSoup
import time
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union
import logging
import re
import json
from urllib.parse import urljoin, urlparse
import random

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class WNBAOddsScraper:
    """Comprehensive WNBA odds scraper targeting multiple sources"""
    
    def __init__(self, delay_range=(1, 3), max_retries=3):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        self.delay_range = delay_range
        self.max_retries = max_retries
        self.data_dir = "data/odds"
        os.makedirs(self.data_dir, exist_ok=True)
    
    def _make_request(self, url: str, **kwargs) -> Optional[requests.Response]:
        """Make HTTP request with retries and delays"""
        for attempt in range(self.max_retries):
            try:
                logger.debug(f"Requesting: {url} (attempt {attempt + 1})")
                response = self.session.get(url, timeout=30, **kwargs)
                
                if response.status_code == 200:
                    # Random delay to be respectful
                    delay = random.uniform(*self.delay_range)
                    time.sleep(delay)
                    return response
                elif response.status_code == 429:  # Rate limited
                    wait_time = 10 * (attempt + 1)
                    logger.warning(f"Rate limited, waiting {wait_time}s")
                    time.sleep(wait_time)
                else:
                    logger.warning(f"HTTP {response.status_code} for {url}")
                    
            except Exception as e:
                logger.warning(f"Request failed (attempt {attempt + 1}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
        
        return None
    
    def scrape_oddsportal_historical(self, years: List[int]) -> List[Dict]:
        """
        Scrape historical WNBA data from OddsPortal
        This is the primary source for historical odds data
        """
        logger.info("🎯 Scraping OddsPortal historical WNBA data...")
        all_odds = []
        
        for year in years:
            logger.info(f"📅 Processing {year} season...")
            
            # OddsPortal WNBA URLs - try different formats
            url_patterns = [
                f"https://www.oddsportal.com/basketball/usa/wnba-{year}/results/",
                f"https://www.oddsportal.com/basketball/usa/wnba/results/#{year}",
                f"https://www.oddsportal.com/basketball/usa/wnba/{year}/results/"
            ]
            
            for url in url_patterns:
                response = self._make_request(url)
                if response:
                    logger.info(f"✅ Found data at: {url}")
                    season_odds = self._parse_oddsportal_season(response.content, year)
                    all_odds.extend(season_odds)
                    break
            else:
                logger.warning(f"❌ No data found for {year} on OddsPortal")
        
        logger.info(f"📊 OddsPortal collected {len(all_odds)} records")
        return all_odds
    
    def _parse_oddsportal_season(self, html_content: bytes, year: int) -> List[Dict]:
        """Parse OddsPortal season page for WNBA odds"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            odds_records = []
            
            # Look for results table - OddsPortal uses specific table structure
            results_table = soup.find('table', {'class': 'table-main'}) or soup.find('div', {'id': 'tournamentTable'})
            
            if not results_table:
                # Try alternative selectors
                results_table = soup.find('table') or soup.find('div', class_='table')
            
            if results_table:
                rows = results_table.find_all('tr')[1:]  # Skip header
                
                for row in rows:
                    try:
                        record = self._extract_oddsportal_game(row, year)
                        if record:
                            odds_records.append(record)
                    except Exception as e:
                        logger.debug(f"Error parsing row: {e}")
                        continue
            
            # Also look for individual game links to get detailed odds
            game_links = soup.find_all('a', href=re.compile(r'/basketball/usa/wnba.*'))
            for link in game_links[:10]:  # Limit to avoid too many requests
                try:
                    game_url = urljoin("https://www.oddsportal.com", link.get('href'))
                    detailed_odds = self._scrape_oddsportal_game_details(game_url, year)
                    if detailed_odds:
                        odds_records.extend(detailed_odds)
                except Exception as e:
                    logger.debug(f"Error scraping game details: {e}")
                    continue
            
            return odds_records
            
        except Exception as e:
            logger.error(f"Error parsing OddsPortal season: {e}")
            return []
    
    def _extract_oddsportal_game(self, row, year: int) -> Optional[Dict]:
        """Extract game data from OddsPortal table row"""
        try:
            cells = row.find_all(['td', 'th'])
            if len(cells) < 3:
                return None
            
            # OddsPortal typical structure: Date, Teams, Score, Odds
            date_text = cells[0].get_text(strip=True)
            teams_text = cells[1].get_text(strip=True)
            
            # Parse teams
            teams = self._parse_teams_oddsportal(teams_text)
            if not teams:
                return None
            
            # Look for odds in green spans (OddsPortal highlights closing odds)
            odds_spans = row.find_all('span', class_='odds')
            odds_data = {}
            
            if odds_spans and len(odds_spans) >= 2:
                try:
                    odds_data['home_odds'] = float(odds_spans[0].get_text(strip=True))
                    odds_data['away_odds'] = float(odds_spans[1].get_text(strip=True))
                except:
                    pass
            
            return {
                'date': self._parse_date_oddsportal(date_text, year),
                'year': year,
                'home_team': teams['home'],
                'away_team': teams['away'],
                'source': 'OddsPortal',
                'data_type': 'closing_odds',
                **odds_data
            }
            
        except Exception as e:
            logger.debug(f"Error extracting OddsPortal game: {e}")
            return None
    
    def _scrape_oddsportal_game_details(self, game_url: str, year: int) -> List[Dict]:
        """Scrape detailed odds from individual game page"""
        try:
            response = self._make_request(game_url)
            if not response:
                return []
            
            soup = BeautifulSoup(response.content, 'html.parser')
            odds_records = []
            
            # Look for odds comparison table
            odds_table = soup.find('table', {'id': 'odds-data-table'})
            if odds_table:
                rows = odds_table.find_all('tr')[1:]  # Skip header
                
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) >= 3:
                        sportsbook = cells[0].get_text(strip=True)
                        home_odds = cells[1].get_text(strip=True)
                        away_odds = cells[2].get_text(strip=True)
                        
                        # Convert odds if needed
                        home_decimal = self._convert_odds_to_decimal(home_odds)
                        away_decimal = self._convert_odds_to_decimal(away_odds)
                        
                        if home_decimal and away_decimal:
                            odds_records.append({
                                'year': year,
                                'sportsbook': sportsbook,
                                'home_odds': home_decimal,
                                'away_odds': away_decimal,
                                'source': 'OddsPortal_Detail',
                                'url': game_url
                            })
            
            return odds_records
            
        except Exception as e:
            logger.debug(f"Error scraping game details: {e}")
            return []
    
    def scrape_vegasinsider_current(self) -> List[Dict]:
        """Scrape current WNBA odds from VegasInsider"""
        logger.info("🎯 Scraping VegasInsider current WNBA odds...")
        
        urls = [
            "https://www.vegasinsider.com/wnba/odds/",
            "https://www.vegasinsider.com/wnba/odds/futures/",
            "https://www.vegasinsider.com/wnba/odds/money-line/"
        ]
        
        all_odds = []
        
        for url in urls:
            response = self._make_request(url)
            if response:
                odds = self._parse_vegasinsider_odds(response.content)
                all_odds.extend(odds)
        
        logger.info(f"📊 VegasInsider collected {len(all_odds)} records")
        return all_odds
    
    def _parse_vegasinsider_odds(self, html_content: bytes) -> List[Dict]:
        """Parse VegasInsider odds table"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            odds_records = []
            
            # VegasInsider uses tables with sportsbook columns
            odds_tables = soup.find_all('table')
            
            for table in odds_tables:
                rows = table.find_all('tr')
                if len(rows) < 2:
                    continue
                
                # Header row usually contains sportsbook names
                header = rows[0]
                sportsbooks = [th.get_text(strip=True) for th in header.find_all(['th', 'td'])]
                
                for row in rows[1:]:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) < 2:
                        continue
                    
                    # First cell usually contains team/game info
                    game_info = cells[0].get_text(strip=True)
                    
                    # Extract team names
                    teams = self._parse_teams_vegasinsider(game_info)
                    if not teams:
                        continue
                    
                    # Parse odds from each sportsbook column
                    for i, cell in enumerate(cells[1:], 1):
                        if i < len(sportsbooks):
                            sportsbook = sportsbooks[i]
                            odds_text = cell.get_text(strip=True)
                            
                            if odds_text and odds_text != '-':
                                parsed_odds = self._parse_vegasinsider_odds_cell(odds_text)
                                if parsed_odds:
                                    odds_records.append({
                                        'date': datetime.now().strftime('%Y-%m-%d'),
                                        'year': 2025,
                                        'home_team': teams.get('home'),
                                        'away_team': teams.get('away'),
                                        'sportsbook': sportsbook,
                                        'source': 'VegasInsider',
                                        'data_type': 'live_odds',
                                        **parsed_odds
                                    })
            
            return odds_records
            
        except Exception as e:
            logger.error(f"Error parsing VegasInsider: {e}")
            return []
    
    def scrape_betinf_historical(self, years: List[int]) -> List[Dict]:
        """Scrape historical results from BetInf.com"""
        logger.info("🎯 Scraping BetInf historical WNBA data...")
        all_results = []
        
        for year in years:
            url = f"https://www.betinf.com/wnba_{year}.htm"
            response = self._make_request(url)
            
            if response:
                season_results = self._parse_betinf_season(response.content, year)
                all_results.extend(season_results)
            else:
                # Try alternative URL format
                alt_url = f"https://www.betinf.com/wnba.htm?season={year}"
                response = self._make_request(alt_url)
                if response:
                    season_results = self._parse_betinf_season(response.content, year)
                    all_results.extend(season_results)
        
        logger.info(f"📊 BetInf collected {len(all_results)} records")
        return all_results
    
    def _parse_betinf_season(self, html_content: bytes, year: int) -> List[Dict]:
        """Parse BetInf season results"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            results = []
            
            # Look for results table
            results_table = soup.find('table') or soup.find('div', class_='results')
            
            if results_table:
                rows = results_table.find_all('tr')[1:]  # Skip header
                
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 3:
                        try:
                            date_text = cells[0].get_text(strip=True)
                            teams_text = cells[1].get_text(strip=True)
                            score_text = cells[2].get_text(strip=True)
                            
                            teams = self._parse_teams_generic(teams_text)
                            scores = self._parse_score(score_text)
                            
                            if teams and scores:
                                results.append({
                                    'date': self._parse_date_generic(date_text, year),
                                    'year': year,
                                    'home_team': teams['home'],
                                    'away_team': teams['away'],
                                    'home_score': scores['home'],
                                    'away_score': scores['away'],
                                    'source': 'BetInf',
                                    'data_type': 'results'
                                })
                        except Exception as e:
                            logger.debug(f"Error parsing BetInf row: {e}")
                            continue
            
            return results
            
        except Exception as e:
            logger.error(f"Error parsing BetInf season: {e}")
            return []
    
    # Utility parsing methods
    def _parse_teams_oddsportal(self, teams_text: str) -> Optional[Dict]:
        """Parse team names from OddsPortal format"""
        patterns = [
            r'(.+?)\s*-\s*(.+)',  # Team1 - Team2
            r'(.+?)\s*@\s*(.+)',  # Away @ Home
            r'(.+?)\s*vs\.?\s*(.+)'  # Team1 vs Team2
        ]
        
        for pattern in patterns:
            match = re.search(pattern, teams_text, re.IGNORECASE)
            if match:
                away, home = match.groups()
                return {
                    'away': away.strip(),
                    'home': home.strip()
                }
        return None
    
    def _parse_teams_vegasinsider(self, game_info: str) -> Optional[Dict]:
        """Parse team names from VegasInsider format"""
        return self._parse_teams_oddsportal(game_info)
    
    def _parse_teams_generic(self, teams_text: str) -> Optional[Dict]:
        """Generic team name parser"""
        return self._parse_teams_oddsportal(teams_text)
    
    def _parse_date_oddsportal(self, date_text: str, year: int) -> Optional[str]:
        """Parse date from OddsPortal format"""
        try:
            # Common formats: "14 Jan", "14.01", "01/14"
            patterns = [
                r'(\d{1,2})\s+(\w{3})',  # 14 Jan
                r'(\d{1,2})\.(\d{1,2})',  # 14.01
                r'(\d{1,2})/(\d{1,2})',   # 01/14
                r'(\d{4})-(\d{1,2})-(\d{1,2})'  # 2024-01-14
            ]
            
            for pattern in patterns:
                match = re.search(pattern, date_text)
                if match:
                    if len(match.groups()) == 3:  # Full date
                        year_str, month_str, day_str = match.groups()
                        return f"{year_str}-{int(month_str):02d}-{int(day_str):02d}"
                    else:  # Day/month only
                        day_month = match.groups()
                        if day_month[1].isalpha():  # Month name
                            months = {
                                'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
                                'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
                            }
                            month = months.get(day_month[1].lower()[:3], 1)
                            return f"{year}-{month:02d}-{int(day_month[0]):02d}"
                        else:  # Numeric month
                            return f"{year}-{int(day_month[1]):02d}-{int(day_month[0]):02d}"
            
            return None
        except:
            return None
    
    def _parse_date_generic(self, date_text: str, year: int) -> Optional[str]:
        """Generic date parser"""
        return self._parse_date_oddsportal(date_text, year)
    
    def _parse_score(self, score_text: str) -> Optional[Dict]:
        """Parse game score"""
        try:
            # Formats: "85:92", "85-92", "85 92"
            pattern = r'(\d+)[\s:\-]+(\d+)'
            match = re.search(pattern, score_text)
            if match:
                score1, score2 = match.groups()
                return {
                    'home': int(score2),  # Assuming second score is home
                    'away': int(score1)
                }
            return None
        except:
            return None
    
    def _parse_vegasinsider_odds_cell(self, odds_text: str) -> Optional[Dict]:
        """Parse odds from VegasInsider cell"""
        try:
            # Look for different formats: +150, -110, etc.
            pattern = r'([+-]?\d+(?:\.\d+)?)'
            matches = re.findall(pattern, odds_text)
            
            if matches:
                if len(matches) >= 2:
                    return {
                        'away_odds': self._american_to_decimal(int(matches[0])),
                        'home_odds': self._american_to_decimal(int(matches[1]))
                    }
                elif len(matches) == 1:
                    return {
                        'odds': self._american_to_decimal(int(matches[0]))
                    }
            
            return None
        except:
            return None
    
    def _convert_odds_to_decimal(self, odds_str: str) -> Optional[float]:
        """Convert various odds formats to decimal"""
        try:
            odds_str = odds_str.strip()
            
            if odds_str.startswith(('+', '-')):  # American odds
                return self._american_to_decimal(int(odds_str))
            elif '/' in odds_str:  # Fractional odds
                return self._fractional_to_decimal(odds_str)
            else:  # Assume decimal
                return float(odds_str)
        except:
            return None
    
    def _american_to_decimal(self, american_odds: int) -> float:
        """Convert American odds to decimal"""
        if american_odds > 0:
            return (american_odds / 100) + 1
        else:
            return (100 / abs(american_odds)) + 1
    
    def _fractional_to_decimal(self, fractional_odds: str) -> float:
        """Convert fractional odds to decimal"""
        try:
            num, den = fractional_odds.split('/')
            return (float(num) / float(den)) + 1
        except:
            return 1.0
    
    def save_data(self, data: List[Dict], filename: str = None) -> str:
        """Save scraped data to files"""
        if not data:
            logger.warning("No data to save")
            return ""
        
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"wnba_odds_scraped_{timestamp}"
        
        # Convert to DataFrame
        df = pd.DataFrame(data)
        
        # Clean and standardize data
        df = self._clean_dataframe(df)
        
        # Save as both CSV and parquet
        csv_path = os.path.join(self.data_dir, f"{filename}.csv")
        parquet_path = os.path.join(self.data_dir, f"{filename}.parquet")
        
        df.to_csv(csv_path, index=False)
        df.to_parquet(parquet_path, index=False)
        
        logger.info(f"💾 Saved {len(df)} records to {csv_path}")
        
        # Print summary
        self._print_summary(df)
        
        return parquet_path
    
    def _clean_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean and standardize scraped data"""
        try:
            # Standardize team names
            df['home_team'] = df['home_team'].apply(self._standardize_team_name)
            df['away_team'] = df['away_team'].apply(self._standardize_team_name)
            
            # Ensure date format
            df['date'] = pd.to_datetime(df['date'], errors='coerce')
            
            # Remove duplicates
            df = df.drop_duplicates(subset=['date', 'home_team', 'away_team', 'source'], keep='first')
            
            # Sort by date
            df = df.sort_values('date')
            
            return df
        except Exception as e:
            logger.warning(f"Error cleaning dataframe: {e}")
            return df
    
    def _standardize_team_name(self, team_name: str) -> str:
        """Standardize team names across sources"""
        if not isinstance(team_name, str):
            return ""
        
        # WNBA team name mappings
        name_mappings = {
            'atlanta': 'Atlanta Dream',
            'chicago': 'Chicago Sky',
            'connecticut': 'Connecticut Sun',
            'dallas': 'Dallas Wings',
            'indiana': 'Indiana Fever',
            'las vegas': 'Las Vegas Aces',
            'los angeles': 'Los Angeles Sparks',
            'minnesota': 'Minnesota Lynx',
            'new york': 'New York Liberty',
            'phoenix': 'Phoenix Mercury',
            'seattle': 'Seattle Storm',
            'washington': 'Washington Mystics',
            'golden state': 'Golden State Valkyries'
        }
        
        team_lower = team_name.lower().strip()
        for key, standard_name in name_mappings.items():
            if key in team_lower:
                return standard_name
        
        return team_name.title()
    
    def _print_summary(self, df: pd.DataFrame):
        """Print summary of scraped data"""
        print(f"\n📊 WNBA ODDS SCRAPING SUMMARY")
        print(f"{'='*50}")
        print(f"Total records: {len(df)}")
        print(f"Date range: {df['date'].min()} to {df['date'].max()}")
        print(f"Years covered: {sorted(df['year'].unique()) if 'year' in df.columns else 'N/A'}")
        print(f"Sources: {', '.join(df['source'].unique()) if 'source' in df.columns else 'N/A'}")
        
        if 'sportsbook' in df.columns:
            sportsbooks = df['sportsbook'].dropna().unique()
            if len(sportsbooks) > 0:
                print(f"Sportsbooks: {', '.join(sportsbooks[:5])}{' (+more)' if len(sportsbooks) > 5 else ''}")
        
        print(f"Data types: {', '.join(df['data_type'].unique()) if 'data_type' in df.columns else 'N/A'}")

def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(description="Scrape WNBA odds from multiple sources")
    parser.add_argument("--source", choices=['oddsportal', 'vegasinsider', 'betinf', 'all'], 
                       default='all', help="Source to scrape")
    parser.add_argument("--years", default="2021-2024", help="Years to scrape (format: 2021-2024)")
    parser.add_argument("--current-only", action="store_true", help="Only scrape current odds")
    parser.add_argument("--output", help="Output filename (without extension)")
    parser.add_argument("--delay", type=float, default=2.0, help="Delay between requests (seconds)")
    
    args = parser.parse_args()
    
    # Parse years
    if args.current_only:
        years = [2025]
    else:
        try:
            start_year, end_year = map(int, args.years.split('-'))
            years = list(range(start_year, end_year + 1))
        except:
            years = [2024]  # Default
    
    # Initialize scraper
    scraper = WNBAOddsScraper(delay_range=(args.delay, args.delay + 1))
    
    logger.info(f"🚀 Starting WNBA odds scraping...")
    logger.info(f"📅 Years: {years}")
    logger.info(f"🔍 Source: {args.source}")
    
    all_data = []
    
    try:
        if args.source in ['oddsportal', 'all'] and not args.current_only:
            odds_data = scraper.scrape_oddsportal_historical(years)
            all_data.extend(odds_data)
        
        if args.source in ['vegasinsider', 'all']:
            current_odds = scraper.scrape_vegasinsider_current()
            all_data.extend(current_odds)
        
        if args.source in ['betinf', 'all'] and not args.current_only:
            results_data = scraper.scrape_betinf_historical(years)
            all_data.extend(results_data)
        
        if all_data:
            output_file = scraper.save_data(all_data, args.output)
            print(f"\n✅ Success! Data saved to: {output_file}")
            print(f"🎯 Ready for your WNBA prediction models!")
        else:
            logger.warning("❌ No data collected")
            
    except KeyboardInterrupt:
        logger.info("⏹️  Scraping interrupted by user")
        if all_data:
            output_file = scraper.save_data(all_data, f"wnba_partial_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            print(f"💾 Partial data saved to: {output_file}")
    except Exception as e:
        logger.error(f"❌ Error during scraping: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()