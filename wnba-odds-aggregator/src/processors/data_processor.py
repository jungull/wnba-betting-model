from utils.team_mapper import TeamMapper
from utils.validators import validate_team_name, validate_odds_value, validate_datetime

class DataProcessor:
    def __init__(self):
        self.team_mapper = TeamMapper()

    def clean_and_validate(self, record):
        # Standardize team names
        record['home_team'] = self.team_mapper.standardize(record.get('home_team', ''))
        record['away_team'] = self.team_mapper.standardize(record.get('away_team', ''))
        # Validate fields
        record['valid'] = (
            validate_team_name(record['home_team']) and
            validate_team_name(record['away_team']) and
            validate_odds_value(record.get('price_home')) and
            validate_odds_value(record.get('price_away')) and
            validate_datetime(record.get('commence_time'))
        )
        return record 