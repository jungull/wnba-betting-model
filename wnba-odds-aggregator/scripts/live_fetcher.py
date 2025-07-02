import sys
import os
from dateutil import parser
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
from api.odds_api_client import OddsAPIClient
from processors.data_processor import DataProcessor
from utils.database import get_engine, Odds
from sqlalchemy.orm import sessionmaker

if __name__ == '__main__':
    client = OddsAPIClient()
    processor = DataProcessor()
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    session = Session()
    data = client.get_odds()
    records = client.parse_api_response(data)
    for record in records:
        processed = processor.clean_and_validate(record)
        if not processed['valid']:
            continue
        # Remove 'valid' key before DB operations
        if 'valid' in processed:
            del processed['valid']
        # Parse datetime fields
        for dt_field in ['commence_time', 'last_update']:
            if dt_field in processed and isinstance(processed[dt_field], str):
                try:
                    processed[dt_field] = parser.isoparse(processed[dt_field])
                except Exception:
                    processed[dt_field] = None
        # Upsert logic
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
    print(f"Inserted/updated {len(records)} odds records.") 