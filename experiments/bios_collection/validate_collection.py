#!/usr/bin/env python3
"""
Validation evidence for the COLLECT-S reference collection (bios / cities / tips).
Reads data/reference/*.csv + masters; writes evidence CSVs next to this script.
Offline only - no network.
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
REF = ROOT / "data" / "reference"
OUT = Path(__file__).resolve().parent

bios = pd.read_csv(REF / "player_bios.csv")
cities = pd.read_csv(REF / "team_cities.csv")
tips = pd.read_csv(REF / "tip_times.csv", dtype={"game_id": str})
mp = pd.read_parquet(ROOT / "data" / "masters" / "master_player.parquet",
                     columns=["player_id", "season", "player_name", "position",
                              "minutes", "game_id", "team_abbreviation"])
mt = pd.read_parquet(ROOT / "data" / "masters" / "master_team.parquet",
                     columns=["game_id", "season", "team_id", "team_abbreviation", "is_home"])

# ---------------------------------------------------------------- 1. bios coverage
uni = mp.drop_duplicates(["player_id", "season"])[["player_id", "season"]]
b = bios[["player_id", "season", "height_inches", "weight_lbs", "age", "birthdate",
          "draft_year", "position_raw", "source"]]
cov = uni.merge(b, on=["player_id", "season"], how="left", indicator=True)
rows = []
for s, g in cov.groupby("season"):
    rows.append({
        "season": s,
        "master_player_ids": g["player_id"].nunique(),
        "with_bios_row": int((g["_merge"] == "both").sum()),
        "with_height": int(g["height_inches"].notna().sum()),
        "pct_with_height": round(100 * g["height_inches"].notna().mean(), 2),
        "with_weight": int(g["weight_lbs"].notna().sum()),
        "with_age_or_birthdate": int((g["age"].notna() | g["birthdate"].notna()).sum()),
        "with_draft_year": int(g["draft_year"].notna().sum()),
        "with_position_raw": int(g["position_raw"].notna().sum()),
        "from_fallback": int((g["source"] == "commonplayerinfo").sum()),
    })
tot = {
    "season": "ALL",
    "master_player_ids": uni["player_id"].nunique(),
    "with_bios_row": int((cov["_merge"] == "both").sum()),
    "with_height": int(cov["height_inches"].notna().sum()),
    "pct_with_height": round(100 * cov["height_inches"].notna().mean(), 2),
    "with_weight": int(cov["weight_lbs"].notna().sum()),
    "with_age_or_birthdate": int((cov["age"].notna() | cov["birthdate"].notna()).sum()),
    "with_draft_year": int(cov["draft_year"].notna().sum()),
    "with_position_raw": int(cov["position_raw"].notna().sum()),
    "from_fallback": int((cov["source"] == "commonplayerinfo").sum()),
}
pd.DataFrame(rows + [tot]).to_csv(OUT / "coverage_by_season.csv", index=False)

# unresolved: master player-seasons with NO height (we never guess)
unres = cov[cov["height_inches"].isna()].copy()
meta = (mp.groupby("player_id")
        .agg(player_name=("player_name", "last"), games=("game_id", "nunique"),
             total_minutes=("minutes", "sum"),
             teams=("team_abbreviation", lambda x: "|".join(sorted(set(x)))))
        .reset_index())
unres = unres[["player_id", "season", "source"]].merge(meta, on="player_id", how="left")
unres["total_minutes"] = unres["total_minutes"].round(1)
unres.to_csv(OUT / "unresolved_ids.csv", index=False)

# ---------------------------------------------------------------- 2. sanity ranges
viol = bios[
    (bios["height_inches"].notna() & (~bios["height_inches"].between(65, 84)))
    | (bios["weight_lbs"].notna() & (~bios["weight_lbs"].between(120, 280)))
].copy()
viol.to_csv(OUT / "sanity_violations.csv", index=False)

stats = []
for s, g in bios.groupby("season"):
    stats.append({
        "season": s, "n": len(g),
        "height_min": g["height_inches"].min(), "height_max": g["height_inches"].max(),
        "height_mean": round(g["height_inches"].mean(), 2),
        "weight_min": g["weight_lbs"].min(), "weight_max": g["weight_lbs"].max(),
        "weight_mean": round(g["weight_lbs"].mean(), 1),
        "age_min": g["age"].min(), "age_max": g["age"].max(),
        "age_mean": round(g["age"].mean(), 2),
        "n_range_violations": int(len(viol[viol["season"] == s])),
    })
pd.DataFrame(stats).to_csv(OUT / "sanity_distribution_by_season.csv", index=False)

# height by position: position_raw (API) where present, else master modal starter position
mpos = mp[mp["position"].isin(["G", "F", "C"])]
modal = (mpos.groupby("player_id")["position"]
         .agg(lambda x: x.mode().iloc[0]).rename("position_master_modal").reset_index())
hb = bios.drop_duplicates("player_id")[["player_id", "player_name", "height_inches", "weight_lbs", "position_raw"]]
hb = hb.merge(modal, on="player_id", how="left")
hb["position_final"] = hb["position_raw"].fillna(hb["position_master_modal"])
hb["position_source"] = np.where(hb["position_raw"].notna(), "api_commonplayerinfo",
                        np.where(hb["position_master_modal"].notna(), "master_starter_modal", "none"))
dist = (hb.groupby(["position_final", "position_source"], dropna=False)
        .agg(players=("player_id", "nunique"),
             height_mean=("height_inches", "mean"), height_min=("height_inches", "min"),
             height_max=("height_inches", "max"), weight_mean=("weight_lbs", "mean"))
        .round(2).reset_index())
dist.to_csv(OUT / "height_by_position.csv", index=False)

# ---------------------------------------------------------------- 3. cities checks
mk = mt.groupby(["team_id", "team_abbreviation"])["season"].agg(["min", "max"]).reset_index()
mk.columns = ["team_id", "abbreviation", "master_first_season", "master_last_season"]
cj = mk.merge(cities, on=["team_id", "abbreviation"], how="outer", indicator=True)
cj["status"] = cj["_merge"].map({"both": "OK", "left_only": "MISSING_FROM_CITIES",
                                 "right_only": "NOT_IN_MASTER"})
cj.drop(columns="_merge").to_csv(OUT / "cities_join_check.csv", index=False)

spot = cities[["abbreviation", "franchise", "city", "arena", "lat", "lon",
               "elevation_ft", "timezone"]].drop_duplicates("franchise").head(15)
spot.to_csv(OUT / "cities_spot_check.csv", index=False)

# ---------------------------------------------------------------- 4. tip times
home_games = mt[mt["is_home"] == 1][["game_id", "season"]]
tcov = home_games.merge(tips[["game_id", "tip_hour_local"]], on="game_id", how="left")
trows = []
for s, g in tcov.groupby("season"):
    have = g["tip_hour_local"].notna()
    hours = g.loc[have, "tip_hour_local"]
    trows.append({
        "season": s, "master_games": len(g), "with_tip_time": int(have.sum()),
        "without_tip_time": int((~have).sum()),
        "pct_covered": round(100 * have.mean(), 1),
        "matinee_share_pct": round(100 * (hours < 17).mean(), 1) if len(hours) else None,
        "median_tip_hour": hours.median() if len(hours) else None,
    })
pd.DataFrame(trows).to_csv(OUT / "tip_coverage_by_season.csv", index=False)

hour_dist = (tips.groupby(["season", "tip_hour_local"]).size()
             .rename("games").reset_index()
             .pivot(index="tip_hour_local", columns="season", values="games")
             .fillna(0).astype(int))
hour_dist.to_csv(OUT / "tip_hour_distribution.csv")

print("evidence written to", OUT)
print("\ncoverage_by_season:")
print(pd.DataFrame(rows + [tot]).to_string(index=False))
print("\nunresolved:", len(unres), "player-seasons")
print(unres.to_string(index=False) if len(unres) else "  (none)")
print("\nrange violations:", len(viol))
if len(viol):
    print(viol[["player_id", "player_name", "season", "height_inches", "weight_lbs", "source"]].to_string(index=False))
print("\nheight by position:")
print(dist.to_string(index=False))
print("\ntip coverage:")
print(pd.DataFrame(trows).to_string(index=False))
