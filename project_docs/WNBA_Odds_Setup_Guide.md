# WNBA Odds Integration Setup Guide

## Quick Start (5 minutes)

### 1. Get API Access
**Sports Game Odds (Recommended)**
- Visit: https://sportsgameodds.com/
- Sign up for 14-day free trial
- Note your API key from the dashboard

### 2. Install Dependencies
```bash
pip install -r setup_scripts/requirements.txt
```

### 3. Test the Integration
```bash
# Fetch current live WNBA odds
python scripts/04_analysis/wnba_odds_fetcher.py --api-key YOUR_API_KEY

# Fetch historical odds (when WNBA season is active)
python scripts/04_analysis/wnba_odds_fetcher.py --api-key YOUR_API_KEY --historical --start-date 2024-05-15 --end-date 2024-10-20
```

## Data Output Structure

The fetcher creates structured data in `data/odds/` with the following schema:

| Field | Description | Example |
|-------|-------------|---------|
| date | Game date | 2024-05-15 |
| event_id | Unique game identifier | SGO_12345 |
| home_team | Home team abbreviation | LAS |
| away_team | Away team abbreviation | NY |
| sportsbook | Sportsbook name | DraftKings |
| home_ml | Home team moneyline | -150 |
| away_ml | Away team moneyline | +130 |
| home_spread | Home team spread | -3.5 |
| total_over_under | Total points line | 165.5 |
| timestamp | When odds were recorded | 2024-05-15T18:30:00Z |

## Integration with Existing Pipeline

### 1. Add to Data Processing Pipeline
```python
# In your main prediction script
from scripts.analysis.wnba_odds_fetcher import WNBAOddsFetcher

# Initialize odds fetcher
odds_fetcher = WNBAOddsFetcher(api_key="YOUR_API_KEY")

# Get current odds for modeling
current_odds = odds_fetcher.get_live_odds()

# Integrate with your existing game data
merged_data = your_game_data.merge(current_odds, on=['home_team', 'away_team', 'date'])
```

### 2. Create Betting Models
```python
# Example: Simple value betting model
def find_value_bets(predictions_df, odds_df, threshold=0.05):
    """Find bets where model probability > implied probability + threshold"""
    
    # Convert odds to implied probability
    odds_df['implied_prob_home'] = 1 / (1 + (odds_df['home_ml'] / 100))
    odds_df['implied_prob_away'] = 1 / (1 + (odds_df['away_ml'] / 100))
    
    # Compare with model predictions
    merged = predictions_df.merge(odds_df, on=['game_id'])
    
    # Find value bets
    value_bets = merged[
        (merged['predicted_home_prob'] - merged['implied_prob_home'] > threshold) |
        (merged['predicted_away_prob'] - merged['implied_prob_away'] > threshold)
    ]
    
    return value_bets
```

## Recommended Next Steps

### Phase 1: Basic Integration (This Week)
1. ✅ Set up Sports Game Odds API account
2. ✅ Test the fetcher script with live data
3. ⏳ Integrate odds data with existing game predictions
4. ⏳ Build simple value betting alerts

### Phase 2: Historical Analysis (Next 2 weeks)
1. ⏳ Backfill historical odds data for 2024 season
2. ⏳ Analyze closing line value of your predictions
3. ⏳ Build line movement tracking
4. ⏳ Create betting performance dashboard

### Phase 3: Advanced Features (Next month)
1. ⏳ Player prop odds integration
2. ⏳ Live betting models
3. ⏳ Multi-sportsbook arbitrage detection
4. ⏳ Automated betting alerts

## Monitoring & Maintenance

### Daily Tasks
- [ ] Check API rate limits and usage
- [ ] Validate odds data quality
- [ ] Monitor for new sportsbooks

### Weekly Tasks
- [ ] Review betting model performance
- [ ] Update closing line value analysis
- [ ] Check for API changes or updates

### Monthly Tasks
- [ ] Evaluate additional data sources
- [ ] Optimize data storage and retrieval
- [ ] Review and update betting strategies

## WNBA Season Schedule

### Key Dates for 2025
- **Regular Season**: May 16 - September 19, 2025
- **Playoffs**: September 22 - October 20, 2025
- **Peak Betting Period**: June - August (playoff races heat up)

### Data Collection Priority
1. **May-June**: Focus on season opening lines and early season trends
2. **July-August**: Peak betting volume, monitor line movements closely
3. **September-October**: Playoff odds and futures markets

## Troubleshooting

### Common Issues
1. **API Rate Limits**: Add delays between requests (current: 0.5s)
2. **Missing Data**: Some games may not have odds available immediately
3. **Data Quality**: Always validate odds against multiple sources

### Error Handling
```python
# The fetcher includes comprehensive error handling
try:
    odds_data = fetcher.get_live_odds()
except Exception as e:
    logger.error(f"Failed to fetch odds: {e}")
    # Fallback to cached data or alternative source
```

## Success Metrics

### Track These KPIs
- **Data Coverage**: % of games with odds data
- **Prediction Accuracy**: Compare vs closing lines
- **ROI**: Return on investment for betting recommendations
- **Volume**: Number of value bets identified per week

### Recommended Tools
- **Dashboard**: Plotly/Streamlit for visualization
- **Alerts**: Email/Slack notifications for high-value bets
- **Tracking**: Spreadsheet or database for bet tracking

---

## Support & Resources

- **API Documentation**: https://sportsgameodds.com/docs
- **WNBA Schedule**: Check official WNBA website
- **Issues**: Create issues in your project repository

*Last updated: January 2025*