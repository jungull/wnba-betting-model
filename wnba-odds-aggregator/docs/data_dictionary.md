# Data Dictionary

## odds
- `id`: Primary key
- `game_id`: Unique game identifier
- `sport`: Sport type (default: basketball_wnba)
- `commence_time`: Game start time
- `home_team`: Home team name
- `away_team`: Away team name
- `bookmaker`: Bookmaker name
- `market_key`: Market type
- `price_home`: Home team odds
- `point_home`: Home team point spread
- `price_away`: Away team odds
- `point_away`: Away team point spread
- `last_update`: Last update timestamp
- `source`: Data source (api/scrape)
- `data_quality_score`: Data quality score
- `created_at`: Record creation timestamp

## team_mappings
- `id`: Primary key
- `raw_name`: Raw team name
- `standard_name`: Standardized team name
- `created_at`: Timestamp 