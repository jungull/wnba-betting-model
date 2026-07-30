#!/usr/bin/env python3
"""
Per-game misc/advanced V3 backfill — closes the granular gaps collect_refresh.py doesn't cover:

  misc:     2021 Regular Season, 2022 (R+P), 2024 (R+P)
  advanced: 2021 Regular Season, 2022 (R+P), 2023 (R+P), 2024 (R+P)

(collect_refresh.py covers: 2021 postseason misc+adv+pbp, 2023 misc, 2025 all, 2026 all.
The repo itself has NO per-game misc/advanced files — the *_with_misc_stats.parquet
gamelogs are mislabeled and contain no misc columns.)

After this run the repo holds uniform V3 per-game granular stats for 2021-2026 and no
longer depends on the Drive master_player.csv export for paint/PFD/fastbreak channels.

Run from repo root AFTER collect_refresh.py finishes:   python collect_misc_backfill.py
Resumable (same per-game checkpointing). Outputs to data/refresh_2026/{misc,advanced}/,
report to data/refresh_2026/backfill_report.json. Runtime roughly 75-90 min.
"""
import json

from collect_refresh import season_games, per_game, OUT, FAILURES

PLANS = [
    ("2021", ("Regular Season",), ("misc", "advanced")),   # playoffs done in Phase A
    ("2022", ("Regular Season", "Playoffs"), ("misc", "advanced")),
    ("2023", ("Regular Season", "Playoffs"), ("advanced",)),  # misc done in Phase B
    ("2024", ("Regular Season", "Playoffs"), ("misc", "advanced")),
]

def main():
    report = {}
    for season, types, kinds in PLANS:
        print(f"\n== backfill {season}: {', '.join(kinds)} ==")
        _, ids = season_games(season, types=types)
        for kind in kinds:
            per_game(ids, kind)
        report[f"{season}_games"] = len(ids)
    report["permanent_failures"] = FAILURES
    print(json.dumps(report, indent=2))
    (OUT / "backfill_report.json").write_text(json.dumps(report, indent=2))
    print("\nDone. Repo now has per-game V3 misc/advanced for every season 2021-2026.")

if __name__ == "__main__":
    main()
