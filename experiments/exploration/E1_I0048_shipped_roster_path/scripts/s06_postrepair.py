#!/usr/bin/env python3
"""s06 — does the REPAIRED code reproduce the post-repair shipped records?

Imports the production module read-only and re-executes it. Nothing is
modified. This converts "the defect looks repaired" into "the repaired code
reproduces the shipped bytes".
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

HERE = Path(__file__).resolve().parent.parent
LIVE = Path(r"C:\Users\jgallagher\wnba-betting-model")
sys.path.insert(0, str(LIVE))

from entity_resolution import Gaps, player_layer_resolved   # noqa: E402

ET = ZoneInfo("America/New_York")
REPAIR_COMMITS = {"55d84f1edd11e9412cc993f0a64e7d9a260cb32b",
                  "9cfe22e61d77b1478f45e68676b8a73afc294933",
                  "5943846f4d01acf3341ef26f798f045a92655c44"}
TEAMS = {"Atlanta Dream": "ATL", "Chicago Sky": "CHI", "Connecticut Sun": "CON",
         "Dallas Wings": "DAL", "Golden State Valkyries": "GSV",
         "Indiana Fever": "IND", "Las Vegas Aces": "LVA",
         "Los Angeles Sparks": "LAS", "Minnesota Lynx": "MIN",
         "New York Liberty": "NYL", "Phoenix Mercury": "PHX",
         "Portland Fire": "PDX", "Seattle Storm": "SEA",
         "Toronto Tempo": "TOR", "Washington Mystics": "WAS"}
abbr_to_name = {v: k for k, v in TEAMS.items()}

print("=" * 78)
print("s06 — REPAIRED code vs post-repair shipped records")
print("=" * 78)

p_all = pd.read_parquet(LIVE / "data" / "masters" / "master_player.parquet")
inj_all = pd.read_csv(LIVE / "data" / "injury_capture" / "injury_log.csv")
inj_all["cap_dt"] = pd.to_datetime(inj_all.capture_utc,
                                   format="%Y%m%dT%H%M%SZ", utc=True)
recs = [json.loads(l) for l in
        (LIVE / "forecasts" / "forecast_log.jsonl").read_text(encoding="utf-8")
        .splitlines() if l.strip()]

rows = []
for r in recs:
    core = r["core_only_prediction"]
    sha = core["provenance"]["source_version"].replace("git:", "")
    if sha not in REPAIR_COMMITS or "player_layer_informational" not in core:
        continue
    pl = core["player_layer_informational"]
    cutoff = datetime.fromisoformat(r["forecast_cutoff"])
    if cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=timezone.utc)
    slate_date = cutoff.astimezone(ET).date()
    season = slate_date.year

    inj = inj_all[inj_all.cap_dt <= cutoff]
    if len(inj):
        inj = (inj.sort_values("cap_dt")
                  .drop_duplicates(subset=["team", "player"], keep="last"))
    pp = p_all[(p_all.season == season)
               & (pd.to_datetime(p_all.game_date).dt.date < slate_date)].copy()
    pp["game_date"] = pd.to_datetime(pp.game_date)
    teams = sorted({core["home_team"], core["away_team"]})
    try:
        got = player_layer_resolved(teams, pp, inj, abbr_to_name, Gaps(),
                                    p_all=p_all, season=season)
    except Exception as e:
        for side in ("home", "away"):
            rows.append({"record_idx": r["record_idx"], "side": side,
                         "team": core[f"{side}_team"], "reproduced": False,
                         "why": f"{type(e).__name__}: {e}"})
        continue
    for side in ("home", "away"):
        ab = core[f"{side}_team"]
        g = got.get(ab, {})
        s = pl[side]
        ok_r = g.get("n_roster") == s["n_roster"]
        ok_o = g.get("n_out") == s["n_out"]
        ok_n = sorted(o["player"] for o in g.get("out", [])) == sorted(pl[f"out_{side}"])
        se, ss = g.get("sum_min_ewma_available"), s["sum_min_ewma_available"]
        ok_e = (se is None and ss is None) or (
            se is not None and ss is not None and abs(se - ss) <= 1e-9)
        rows.append({"record_idx": r["record_idx"], "side": side, "team": ab,
                     "reproduced": bool(ok_r and ok_o and ok_n and ok_e),
                     "shipped_n_roster": s["n_roster"], "mine_n_roster": g.get("n_roster"),
                     "shipped_n_out": s["n_out"], "mine_n_out": g.get("n_out"),
                     "ok_out_names": ok_n, "ok_sum_ewma": ok_e, "why": ""})

R = pd.DataFrame(rows)
R.to_csv(HERE / "POSTREPAIR_FIDELITY.csv", index=False)
print(f"\npost-repair team-slots: {len(R)}")
print(f"reproduced by the REPAIRED production code: {int(R.reproduced.sum())} / {len(R)}")
bad = R[~R.reproduced]
if len(bad):
    print("\nnot reproduced:")
    print(bad.to_string(index=False))
json.dump({"post_repair_slots": int(len(R)),
           "reproduced": int(R.reproduced.sum())},
          open(HERE / "_s06.json", "w"), indent=2)
print("\nwrote POSTREPAIR_FIDELITY.csv")
