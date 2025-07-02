# Advanced Opponent Strength Normalization

## Overview

This system implements sophisticated opponent strength normalization for WNBA player statistics, moving beyond simple single-game adjustments to use comprehensive defensive metrics with weighted historical performance.

## Key Features

### 1. Multiple Defensive Metrics
Instead of using just offensive efficiency as a proxy for defensive strength, we calculate:

- **Defensive Efficiency**: Points allowed per 100 possessions
- **Field Goal Defense**: Opponent FG% and 3P% allowed
- **Steal Rate**: Steals per opponent possession
- **Block Rate**: Blocks per opponent field goal attempt
- **Free Throw Rate Allowed**: FTA per opponent FGA

### 2. Weighted Historical Performance
- **10-Game Lookback**: Uses opponent's last 10 games
- **Recent Weighting**: Past 5 games weighted 1.5x more heavily than older games
- **Formula**: `(recent_avg * 5 * 1.5 + older_avg * 5) / (5 * 1.5 + 5)`

### 3. Comprehensive Normalization
Player statistics are normalized against the opponent's weighted defensive metrics, providing context-aware performance evaluation.

## Implementation Details

### Data Flow

1. **Load Game Data**: All box score files are loaded and combined
2. **Calculate Defensive Metrics**: For each team-game, compute defensive statistics
3. **Build Historical Ratings**: Create weighted defensive ratings for each team
4. **Apply Normalization**: Normalize player stats against opponent strength
5. **Save Results**: Store enhanced player features with normalization metadata

### Key Functions

#### `calculate_defensive_metrics(game_df)`
Calculates comprehensive defensive metrics for a single game:
- Defensive efficiency (points per 100 possessions)
- Shooting defense percentages
- Steal and block rates
- Free throw rate allowed

#### `build_opponent_defensive_history(boxscores)`
Builds historical defensive performance for all teams across all games.

#### `calculate_weighted_defensive_rating(team_id, game_id, defensive_history)`
Computes weighted defensive rating using:
- 10-game lookback window
- 1.5x weight for recent 5 games
- Multiple defensive metrics

#### `normalize_player_stats_with_opponent_strength(player_stats_df, defensive_history)`
Applies advanced normalization to player statistics using opponent defensive strength.

## Usage

### Running the System

```bash
# From the project root
python scripts/02_processing/run_advanced_normalization.py
```

### Prerequisites

1. **Box Score Data**: Must have `wnba_gamelog_*.parquet` files in the `data/` directory
2. **Player Stats**: Must have run `build_possession_based_features.py` first to generate `player_possession_features.parquet`

### Output Files

1. **`team_defensive_history.parquet`**: Historical defensive metrics for all teams
2. **`player_stats_advanced_normalized.parquet`**: Player stats with advanced normalization

## Normalization Methodology

### Defensive Efficiency Calculation
```
Defensive Efficiency = (Opponent Points / Opponent Possessions) * 100
Opponent Possessions = FGA + 0.44*FTA + TOV
```

### Weighted Rating Formula
```
Recent Games (last 5): Weight = 1.5
Older Games (previous 5): Weight = 1.0

Weighted Average = (Recent_Avg * 5 * 1.5 + Older_Avg * 5) / (5 * 1.5 + 5)
```

### Player Stat Normalization
```
Normalized PPP = Raw PPP / (Opponent Defensive Efficiency / 100)
```

## Advantages Over Previous System

### 1. Historical Context
- **Before**: Single-game opponent performance
- **After**: 10-game weighted historical defensive strength

### 2. Multiple Metrics
- **Before**: Only offensive efficiency as defensive proxy
- **After**: 6 different defensive metrics

### 3. Recent Performance Weighting
- **Before**: Equal weight to all games
- **After**: Recent games weighted 1.5x more heavily

### 4. Better Context
- **Before**: Game-specific opponent strength
- **After**: Season-long defensive capability with recent form emphasis

## Example Output

### Player Stats with Advanced Normalization

| Player_ID | Game_ID | Team_ID | Raw_PPP | Normalized_PPP | Opponent_Def_Eff | Normalization_Method |
|-----------|---------|---------|---------|----------------|------------------|---------------------|
| 12345     | 123456  | 161166  | 1.25    | 1.15           | 108.5            | advanced_opponent   |
| 67890     | 123456  | 161166  | 0.95    | 0.87           | 108.5            | advanced_opponent   |

### Defensive History Sample

| Team_ID | Game_ID | Defensive_Efficiency | Opp_FG_PCT | Steal_Rate | Block_Rate |
|---------|---------|---------------------|------------|------------|------------|
| 161166  | 123456  | 108.5               | 0.425      | 0.085      | 0.045      |

## Performance Considerations

### Computational Complexity
- **Time**: O(n * m) where n = games, m = teams
- **Memory**: Stores defensive history for all teams
- **Storage**: Additional ~2-3MB for defensive history

### Optimization Opportunities
1. **Caching**: Defensive ratings can be cached and reused
2. **Incremental Updates**: Only recalculate for new games
3. **Parallel Processing**: Team calculations can be parallelized

## Future Enhancements

### 1. Situational Weighting
- Home/Away performance differences
- Back-to-back game effects
- Rest day impact

### 2. Advanced Metrics
- Defensive rating (DRtg)
- Net rating impact
- Player-specific defensive matchups

### 3. Dynamic Weighting
- Adaptive weights based on performance variance
- Season progression weighting
- Playoff vs. regular season adjustments

## Validation and Quality Assurance

### Data Quality Checks
- Verify defensive metrics are within reasonable ranges
- Check for missing or invalid data
- Validate possession calculations

### Performance Validation
- Compare normalized vs. raw statistics
- Analyze normalization impact on prediction accuracy
- Test different weighting schemes

## Integration with Model Development

This advanced normalization system provides:
1. **Better Feature Engineering**: More sophisticated opponent context
2. **Improved Model Accuracy**: Context-aware player performance
3. **Enhanced Interpretability**: Clear normalization methodology
4. **Scalable Framework**: Easy to extend with additional metrics

The normalized player statistics can be used directly in machine learning models for:
- Player performance prediction
- Team strength assessment
- Betting edge identification
- Risk-adjusted performance evaluation 