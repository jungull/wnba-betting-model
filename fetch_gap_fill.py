#!/usr/bin/env python3
"""
Gap-fill after the master rebuild's coverage findings (2026-07-30):

1. 2025 regular-season advanced stats: collect_refresh Phase C fetched advanced
   only for post-July-3 games; the ~108 earlier 2025 games have misc but no
   advanced. Fetch the missing ones.
2. Real team-gamelog season files for 2021/2022/2023 regular seasons (master
   rebuild had to derive 1,296 team rows from player sums; real team rows carry
   team turnovers etc. that player sums cannot).
3. Refetch 2022/2023 player gamelogs (two games contradict their own PBP -
   stl/tov off by one; stat corrections may have landed at the source since
   the 2025 pull; saved to refresh_2026, never overwriting the originals).

Run AFTER other stats-API crawls finish. Resumable/idempotent.
"""
from pathlib import Path

import pandas as pd

from collect_refresh import get_gamelog, per_game, save, OUT, FAILURES, phase_team_backfill

def main():
    # 1 - missing 2025 advanced
    t25 = pd.concat([pd.read_parquet(p) for p in OUT.glob("gamelog_team_2025_*.parquet")])
    ids25 = sorted(set(t25.GAME_ID.astype(str)))
    have = {p.stem.split("_")[1] for p in (OUT / "advanced").glob("advanced_*.parquet")}
    missing = [g for g in ids25 if g not in have]
    print(f"2025 advanced: {len(missing)} games missing")
    per_game(missing, "advanced")

    # 2 - real team gamelogs 2021-2023 regular seasons (now a collect_refresh
    # phase -- single implementation, same output paths; skips existing files)
    phase_team_backfill()

    # 3 - refreshed player gamelogs for the two pbp-contradicted seasons.
    # NOTE: written to a refetch/ SUBFOLDER on purpose -- build_masters.py loads
    # every refresh_2026/gamelog_player_*.parquet, so a refetch file at the top
    # level would collide with the old-era season files as ~9k duplicate
    # (game_id, player_id) rows. These are reference pulls, not master inputs
    # (the master repair is repair_gamelog_two_games.py).
    for season in ("2022", "2023"):
        f = OUT / "refetch" / f"gamelog_player_{season}_regular_season_refetch.parquet"
        if f.exists():
            print(f"{season} player refetch: exists, skip")
            continue
        df = get_gamelog(season, "Regular Season", "P")
        if len(df):
            df["season_type"] = "Regular Season"
            save(df, f)
        print(f"{season} regular player gamelog refetch: {len(df)} rows")

    print(f"done; permanent failures: {FAILURES}")

if __name__ == "__main__":
    main()
