#!/usr/bin/env python3
"""s05 — is a stable id available at the roster site, and how many rows differ
under the two keys?

Simulates the recency-roster construction (daily_forecast.py:662-665) at EVERY
team-game index in every season, and compares the name key the shipped code
used against the player_id key that was available in the same frame.

Partition discipline: 2021-2024 is the exploration partition. 2025/2026 is the
SEALED confirmation holdout — it is reported here as a DESCRIPTIVE COUNT of
identity ambiguity in a production input, never as a measurement of a forecast.
No outcome column is read; no skill statistic is computed.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent.parent
LIVE = Path(r"C:\Users\jgallagher\wnba-betting-model")
RECENCY_GAMES = 3

ALLOW = ["game_id", "season", "game_date", "team_id", "team_abbreviation",
         "player_id", "player_name", "minutes"]
BANNED = ["pts", "fgm", "fga", "reb", "ast", "plus_minus", "appeared"]

print("=" * 78)
print("s05 — NAME KEY vs player_id KEY at the roster site")
print("=" * 78)

p = pd.read_parquet(LIVE / "data" / "masters" / "master_player.parquet")
assert not [c for c in ALLOW if c not in p.columns], "allowlist unresolved"
p = p[ALLOW].copy()
assert not [c for c in p.columns if c in BANNED], "OUTCOME COLUMN LEAKED"
p["game_date"] = pd.to_datetime(p.game_date)
print(f"resolved by explicit allowlist: {ALLOW}")

# ---- H3: is a stable id present in the very frame line 647 reads? ----------
print("\n--- H3: stable id availability in master_player.parquet ---")
print(f"  'player_id' column present : {'player_id' in p.columns}")
print(f"  null player_id rows        : {int(p.player_id.isna().sum())} of {len(p)}")
print(f"  dtype                      : {p.player_id.dtype}")

# ---- identity ambiguity per season (exact equality only, no fuzzy) --------
amb = []
for s, g in p.groupby("season"):
    n2i = g.groupby("player_name").player_id.nunique()
    i2n = g.groupby("player_id").player_name.nunique()
    amb.append({"season": int(s), "rows": len(g),
                "distinct_player_id": int(g.player_id.nunique()),
                "distinct_player_name": int(g.player_name.nunique()),
                "names_mapping_to_multiple_ids": int((n2i > 1).sum()),
                "ids_mapping_to_multiple_names": int((i2n > 1).sum()),
                "partition": ("exploration_2021_2024" if s <= 2024
                              else "SEALED_holdout")})
AMB = pd.DataFrame(amb)
print("\n--- identity ambiguity in the production input, by season ---")
print(AMB.to_string(index=False))
AMB.to_csv(HERE / "NAME_KEY_ambiguity_by_season.csv", index=False)

# name the offending identities (exact grouping, never substring selection)
offenders = []
for s, g in p.groupby("season"):
    i2n = g.groupby("player_id").player_name.nunique()
    for pid in i2n[i2n > 1].index:
        offenders.append({"season": int(s), "kind": "ID_WITH_MULTIPLE_NAMES",
                          "player_id": int(pid),
                          "values": " | ".join(sorted(
                              g[g.player_id == pid].player_name.unique())),
                          "teams": " | ".join(sorted(
                              g[g.player_id == pid].team_abbreviation.unique()))})
    n2i = g.groupby("player_name").player_id.nunique()
    for nm in n2i[n2i > 1].index:
        offenders.append({"season": int(s), "kind": "NAME_WITH_MULTIPLE_IDS",
                          "player_id": " | ".join(map(str, sorted(
                              g[g.player_name == nm].player_id.unique()))),
                          "values": nm,
                          "teams": " | ".join(sorted(
                              g[g.player_name == nm].team_abbreviation.unique()))})
OFF = pd.DataFrame(offenders)
OFF.to_csv(HERE / "NAME_KEY_offenders.csv", index=False)
print(f"\n--- named identities where the two keys disagree ({len(OFF)}) ---")
print(OFF.to_string(index=False) if len(OFF) else "  NONE")

# ---- simulate the roster at EVERY team-game index -------------------------
rows = []
for (s, tid), g in p.groupby(["season", "team_id"]):
    order = (g[["game_id", "game_date"]].drop_duplicates()
             .sort_values(["game_date", "game_id"]))
    gids = list(order.game_id)
    ab = g.team_abbreviation.iloc[0]
    for i in range(1, len(gids) + 1):          # slate before game i (1..n)
        recent = set(gids[max(0, i - RECENCY_GAMES):i])
        rr = g[g.game_id.isin(recent)]
        n_name = rr.player_name.nunique()
        n_id = rr.player_id.nunique()
        if n_name != n_id:
            rows.append({"season": int(s), "team": ab, "slate_index": i,
                         "n_roster_name_key": int(n_name),
                         "n_roster_id_key": int(n_id),
                         "delta": int(n_name - n_id)})
DIFF = pd.DataFrame(rows)
DIFF.to_csv(HERE / "NAME_KEY_window_diffs.csv", index=False)

tot_windows = sum(
    len(g[["game_id"]].drop_duplicates())
    for _, g in p.groupby(["season", "team_id"]))
print(f"\n--- roster windows simulated at every team-game index: {tot_windows} ---")
print(f"  windows where the two keys give a DIFFERENT roster size: {len(DIFF)}")
if len(DIFF):
    print(DIFF.groupby("season").agg(
        windows_differing=("slate_index", "size"),
        teams=("team", "nunique")).to_string())
    print("\n  detail:")
    print(DIFF.to_string(index=False))

json.dump({"player_id_available": True,
           "null_player_id": int(p.player_id.isna().sum()),
           "ambiguity_by_season": amb,
           "n_offender_identities": int(len(OFF)),
           "total_windows": int(tot_windows),
           "windows_keys_differ": int(len(DIFF))},
          open(HERE / "_s05.json", "w"), indent=2)
print("\nwrote NAME_KEY_*.csv")
