#!/usr/bin/env python3
"""
W2 shot-location pull — league-wide shotchartdetail (LeagueID 10), all seasons.

The player_id=0/team_id=0 league-wide form works for WNBA (verified 2026-07-30:
32,759 rows for 2024 regular season in one call), so the whole pull is ~14 calls.
Saves per season+type:
  data/shotcharts/shots_<season>_<type>.parquet         (every FGA with x/y, zones, make/miss)
  data/shotcharts/league_avg_<season>_<type>.parquet    (league zone averages, second dataset)
Resumable: skips files that already exist.
"""
import sys
import time
from pathlib import Path

try:
    from nba_api.stats.endpoints import shotchartdetail
except ImportError:
    sys.exit("Run first:  pip install nba_api pandas pyarrow")

OUT = Path("data/shotcharts")
OUT.mkdir(parents=True, exist_ok=True)
SEASONS = ["2021", "2022", "2023", "2024", "2025", "2026"]
TYPES = [("Regular Season", "regular"), ("Playoffs", "playoffs")]


def main():
    for season in SEASONS:
        for st, tag in TYPES:
            f_shots = OUT / f"shots_{season}_{tag}.parquet"
            if f_shots.exists():
                print(f"{season} {tag}: exists, skip")
                continue
            try:
                r = shotchartdetail.ShotChartDetail(
                    team_id=0, player_id=0, season_nullable=season,
                    season_type_all_star=st, context_measure_simple="FGA",
                    league_id="10", timeout=60)
                shots, avg = r.get_data_frames()[0], r.get_data_frames()[1]
            except Exception as e:
                print(f"{season} {tag}: FAILED {str(e)[:80]}")
                continue
            if len(shots):
                shots.to_parquet(f_shots, index=False)
                avg.to_parquet(OUT / f"league_avg_{season}_{tag}.parquet", index=False)
            print(f"{season} {tag}: {len(shots)} shots")
            time.sleep(2)
    total = sum(len(__import__('pandas').read_parquet(p)) for p in OUT.glob("shots_*.parquet"))
    print(f"done; total shots on disk: {total}")


if __name__ == "__main__":
    main()
