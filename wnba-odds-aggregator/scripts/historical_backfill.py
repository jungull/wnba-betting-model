import sys
import os
from datetime import datetime
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
from scrapers.oddsshark_scraper import OddsSharkScraper
from processors.data_processor import DataProcessor
from utils.database import get_engine, Odds
from utils.progress_tracker import ProgressTracker
from sqlalchemy.orm import sessionmaker

START_YEAR = 2020
CURRENT_YEAR = datetime.now().year

if __name__ == '__main__':
    scraper = OddsSharkScraper()
    processor = DataProcessor()
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    session = Session()
    tracker = ProgressTracker('historical_progress.json')

    for year in range(START_YEAR, CURRENT_YEAR + 1):
        if tracker.get(str(year)) == 'done':
            continue
        print(f"Fetching odds for {year}...")
        # TODO: Implement actual scraping logic for the year
        # Example: url = f"https://www.oddsshark.com/wnba/odds/archive/{year}"
        html = scraper.scrape_with_retry(f"https://www.oddsshark.com/wnba/odds/archive/{year}")
        records = scraper.extract_odds_data(html)
        for record in records:
            processed = processor.clean_and_validate(record)
            if not processed['valid']:
                continue
            if 'valid' in processed:
                del processed['valid']
            for dt_field in ['commence_time', 'last_update']:
                if dt_field in processed and isinstance(processed[dt_field], str):
                    try:
                        processed[dt_field] = datetime.fromisoformat(processed[dt_field])
                    except Exception:
                        processed[dt_field] = None
            existing = session.query(Odds).filter_by(
                game_id=processed['game_id'],
                bookmaker=processed['bookmaker'],
                market_key=processed['market_key']
            ).first()
            if existing:
                for k, v in processed.items():
                    setattr(existing, k, v)
            else:
                session.add(Odds(**processed))
        session.commit()
        tracker.update(str(year), 'done')
        print(f"Backfill for {year} complete.")
    print("Historical backfill complete.") 