"""
WNBA Odds Data Fetcher
Fetches current and historical WNBA odds from Sports Game Odds API

Usage:
    python wnba_odds_fetcher.py --api-key YOUR_API_KEY
    python wnba_odds_fetcher.py --api-key YOUR_API_KEY --historical --start-date 2024-05-01
"""

import os
import sys
import requests
import json
from datetime import datetime, timedelta
import time
import argparse
from typing import Dict, List, Optional
import logging

try:
    import pandas as pd
except ImportError:
    print("pandas is required but not installed. Please install it with: pip install pandas")
    sys.exit(1)

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class WNBAOddsFetcher:
    """Fetches WNBA odds data from Sports Game Odds API"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.sportsgameodds.com/v2"
        self.headers = {
            "X-API-Key": api_key,
            "Content-Type": "application/json"
        }
        self.wnba_league_id = "WNBA"  # Adjust based on API documentation
        
    def get_wnba_events(self, date: Optional[str] = None) -> List[Dict]:
        """
        Fetch WNBA events for a specific date or upcoming games
        
        Args:
            date: Date in YYYY-MM-DD format, defaults to today
            
        Returns:
            List of WNBA events with odds
        """
        try:
            endpoint = f"{self.base_url}/events"
            params = {
                "leagueID": self.wnba_league_id,
                "oddsAvailable": "true"
            }
            
            if date:
                params["date"] = date
                
            response = requests.get(endpoint, headers=self.headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"Fetched {len(data)} WNBA events")
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching WNBA events: {e}")
            return []
    
    def get_detailed_odds(self, event_id: str) -> Dict:
        """
        Get detailed odds for a specific WNBA event
        
        Args:
            event_id: Unique event identifier
            
        Returns:
            Detailed odds data for the event
        """
        try:
            endpoint = f"{self.base_url}/events/{event_id}/odds"
            response = requests.get(endpoint, headers=self.headers)
            response.raise_for_status()
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching odds for event {event_id}: {e}")
            return {}
    
    def get_historical_odds(self, start_date: str, end_date: str) -> List[Dict]:
        """
        Fetch historical WNBA odds for a date range
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            
        Returns:
            List of historical odds data
        """
        historical_data = []
        current_date = datetime.strptime(start_date, "%Y-%m-%d")
        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
        
        while current_date <= end_date_obj:
            date_str = current_date.strftime("%Y-%m-%d")
            logger.info(f"Fetching odds for {date_str}")
            
            events = self.get_wnba_events(date_str)
            
            for event in events:
                detailed_odds = self.get_detailed_odds(event.get("eventID", ""))
                if detailed_odds:
                    historical_data.append({
                        "date": date_str,
                        "event": event,
                        "odds": detailed_odds
                    })
                
                # Rate limiting - be respectful to the API
                time.sleep(0.5)
            
            current_date += timedelta(days=1)
            
        return historical_data
    
    def parse_odds_data(self, raw_data: List[Dict]) -> pd.DataFrame:
        """
        Parse raw odds data into a structured DataFrame
        
        Args:
            raw_data: List of raw odds data from API
            
        Returns:
            Structured DataFrame with odds information
        """
        parsed_records = []
        
        for record in raw_data:
            event = record.get("event", {})
            odds_data = record.get("odds", {})
            
            base_record = {
                "date": record.get("date"),
                "event_id": event.get("eventID"),
                "home_team": event.get("homeTeam"),
                "away_team": event.get("awayTeam"),
                "game_time": event.get("gameTime"),
                "status": event.get("status")
            }
            
            # Parse different types of odds
            if "odds" in odds_data:
                for odds_entry in odds_data["odds"]:
                    record_copy = base_record.copy()
                    record_copy.update({
                        "sportsbook": odds_entry.get("sportsbook"),
                        "home_ml": odds_entry.get("homeML"),
                        "away_ml": odds_entry.get("awayML"),
                        "home_spread": odds_entry.get("homeSpread"),
                        "away_spread": odds_entry.get("awaySpread"),
                        "total_over_under": odds_entry.get("totalOverUnder"),
                        "over_odds": odds_entry.get("overOdds"),
                        "under_odds": odds_entry.get("underOdds"),
                        "timestamp": odds_entry.get("timestamp")
                    })
                    parsed_records.append(record_copy)
        
        return pd.DataFrame(parsed_records)
    
    def save_odds_data(self, df: pd.DataFrame, filename: Optional[str] = None) -> str:
        """
        Save odds data to CSV and parquet files
        
        Args:
            df: DataFrame containing odds data
            filename: Optional custom filename
            
        Returns:
            Path to saved file
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"wnba_odds_{timestamp}"
        
        # Create data directory if it doesn't exist
        data_dir = "data/odds"
        os.makedirs(data_dir, exist_ok=True)
        
        # Save as both CSV and parquet
        csv_path = os.path.join(data_dir, f"{filename}.csv")
        parquet_path = os.path.join(data_dir, f"{filename}.parquet")
        
        df.to_csv(csv_path, index=False)
        df.to_parquet(parquet_path, index=False)
        
        logger.info(f"Saved {len(df)} records to {csv_path} and {parquet_path}")
        return parquet_path
    
    def get_live_odds(self) -> pd.DataFrame:
        """
        Fetch current live WNBA odds
        
        Returns:
            DataFrame with current odds
        """
        logger.info("Fetching live WNBA odds...")
        events = self.get_wnba_events()
        
        all_odds = []
        for event in events:
            detailed_odds = self.get_detailed_odds(event.get("eventID", ""))
            if detailed_odds:
                all_odds.append({
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "event": event,
                    "odds": detailed_odds
                })
        
        return self.parse_odds_data(all_odds)

def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(description="Fetch WNBA odds data")
    parser.add_argument("--api-key", required=True, help="Sports Game Odds API key")
    parser.add_argument("--historical", action="store_true", help="Fetch historical data")
    parser.add_argument("--start-date", help="Start date for historical data (YYYY-MM-DD)")
    parser.add_argument("--end-date", help="End date for historical data (YYYY-MM-DD)")
    parser.add_argument("--output", help="Output filename (without extension)")
    
    args = parser.parse_args()
    
    # Initialize fetcher
    fetcher = WNBAOddsFetcher(args.api_key)
    
    try:
        if args.historical:
            if not args.start_date:
                logger.error("--start-date required for historical data")
                sys.exit(1)
            
            end_date = args.end_date or datetime.now().strftime("%Y-%m-%d")
            
            logger.info(f"Fetching historical odds from {args.start_date} to {end_date}")
            historical_data = fetcher.get_historical_odds(args.start_date, end_date)
            
            if historical_data:
                df = fetcher.parse_odds_data(historical_data)
                file_path = fetcher.save_odds_data(df, args.output)
                logger.info(f"Historical data saved to {file_path}")
            else:
                logger.warning("No historical data found")
        
        else:
            # Fetch live odds
            logger.info("Fetching live WNBA odds...")
            df = fetcher.get_live_odds()
            
            if not df.empty:
                file_path = fetcher.save_odds_data(df, args.output)
                logger.info(f"Live odds saved to {file_path}")
                
                # Print summary
                print(f"\n=== WNBA ODDS SUMMARY ===")
                print(f"Total records: {len(df)}")
                print(f"Unique games: {df['event_id'].nunique()}")
                print(f"Sportsbooks: {', '.join(df['sportsbook'].dropna().unique())}")
                print(f"Date range: {df['date'].min()} to {df['date'].max()}")
            else:
                logger.warning("No live odds data found")
                
    except Exception as e:
        logger.error(f"Error in main execution: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()