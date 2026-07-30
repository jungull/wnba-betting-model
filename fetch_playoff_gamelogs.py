#!/usr/bin/env python3
"""
One-off: save the playoff season-gamelog files (player + team) that were never
collected as season files: 2022, 2023, 2024. (2021 playoffs saved by Phase A;
2025/2026 saved by Phases C/D. Discovered by the minutes-spec audit: the repo's
wnba_gamelog_*.parquet files are regular-season only.)
Outputs to data/refresh_2026/ alongside the other season files. ~12 API calls.
"""
from collect_refresh import get_gamelog, save, OUT

for season in ("2022", "2023", "2024"):
    for who, tag in (("P", "player"), ("T", "team")):
        df = get_gamelog(season, "Playoffs", who)
        if len(df):
            df["season_type"] = "Playoffs"
            save(df, OUT / f"gamelog_{tag}_{season}_playoffs.parquet")
        print(f"{season} playoffs {tag}: {len(df)} rows")
print("done")
