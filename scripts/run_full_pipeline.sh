#!/bin/bash
set -e

# 1. Data Acquisition
python scripts/01_acquisition/fetch_wnba_boxscores.py
python scripts/01_acquisition/fetch_wnba_playbyplay.py
python scripts/01_acquisition/fetch_wnba_team_gamelog.py
python scripts/01_acquisition/check_pbp_coverage.py        # optional
python scripts/01_acquisition/validate_data_completeness.py # optional

# 2. Data Enrichment
python scripts/02_processing/add_misc_stats.py

# 3. Possession-Based Feature Engineering
python scripts/02_processing/build_possession_based_features.py

# 4. Advanced Opponent Normalization
python scripts/02_processing/run_advanced_normalization.py

# 5. PhD-Level Player Value Calculation
python scripts/02_processing/build_phd_refined_player_value.py

# 6. (Optional) Validation & QA
python scripts/02_processing/validate_on_court_counts.py    # optional

echo "\n✅ Full WNBA data pipeline completed!" 