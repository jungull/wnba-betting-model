# API Reference

## OddsAPIClient
- `get_odds(sport)`
- `parse_api_response(response)`

## OddsSharkScraper
- `scrape_with_retry(url, max_retries)`
- `extract_odds_data(html)`

## DataProcessor
- `clean_and_validate(record)`

## QualityMonitor
- `check_completeness(records, required_fields)`
- `check_outliers(records, field, min_val, max_val)`
- `report()` 