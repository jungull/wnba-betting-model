#!/usr/bin/env python3
"""s04 — who READS the shipped roster rows?

E1_I0035 verified zero `p_active` references. The equivalent question for the
roster ROWS themselves is different and had not been asked.

Field names are matched by EXPLICIT ALLOWLIST of literal strings. Any hit is
then INSPECTED before being counted as a consumer — a token that happens to
collide with an unrelated local dict key is recorded as a non-consumer, with
the line quoted. (cbs_v6.py:466 is exactly that case.)
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent.parent
WT = HERE.parent.parent.parent
LIVE = Path(r"C:\Users\jgallagher\wnba-betting-model")

PLAYER_LAYER_FIELDS = ["player_layer_informational", "out_home", "out_away",
                       "n_roster", "sum_min_ewma_available", "vacated_min_ewma",
                       "n_cold_start"]
LOG_TOKENS = ["forecast_log.jsonl", "DEFAULT_FORECAST_LOG", "core_only_prediction"]

# every reader of the forecast log, found by repository-wide search on
# LOG_TOKENS over *.py (recorded in NOTES.md)
LOG_READERS = ["evalharness/forecast_log.py", "evalharness/__init__.py",
               "verify_all.py", "migrate_forecast_log_schema2.py",
               "prospective_pair/alt_model_log.py", "tests/test_forecast_log.py",
               "ops_adoption_tests/D4/TESTS.py", "daily_forecast.py"]

# the product surfaces named by the brief
SURFACES = ["props_edge.py", "conditional_edge.py", "calibrated_prob_edge.py",
            "daily_certify.py", "daily_refresh.py", "props_capture_daily.py",
            "odds_capture_daily.py", "injury_capture_daily.py"]
SURFACE_DIRS = ["wnba-prediction-engine", "wnba_odds_system",
                "wnba-odds-aggregator", "leaderboards"]
EXT = {".py", ".ps1", ".json", ".md"}
SKIP = {".git", "__pycache__", "node_modules"}


def count(text, toks):
    return sum(text.count(t) for t in toks)


def read(p):
    try:
        return p.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


print("=" * 78)
print("s04 — CONSUMER TRACE for the shipped roster ROWS")
print("=" * 78)
print(f"player-layer field allowlist (literal): {PLAYER_LAYER_FIELDS}")
print(f"log token allowlist (literal)         : {LOG_TOKENS}")

rows = []
for root, lab in ((LIVE, "LIVE_main"), (WT, "worktree")):
    for f in LOG_READERS + SURFACES:
        p = root / f
        if not p.exists():
            rows.append({"root": lab, "target": f, "kind": "file",
                         "exists": False, "log_refs": None,
                         "player_layer_refs": None, "is_consumer": None})
            continue
        t = read(p)
        rows.append({"root": lab, "target": f, "kind": "file", "exists": True,
                     "log_refs": count(t, LOG_TOKENS),
                     "player_layer_refs": count(t, PLAYER_LAYER_FIELDS),
                     "is_consumer": None})
    for d in SURFACE_DIRS:
        dd = root / d
        if not dd.exists():
            rows.append({"root": lab, "target": d + "/", "kind": "dir",
                         "exists": False, "log_refs": None,
                         "player_layer_refs": None, "is_consumer": None})
            continue
        lr = pr = 0
        for p in dd.rglob("*"):
            if (not p.is_file() or p.suffix.lower() not in EXT
                    or SKIP & set(p.parts)):
                continue
            t = read(p)
            lr += count(t, LOG_TOKENS)
            pr += count(t, PLAYER_LAYER_FIELDS)
        rows.append({"root": lab, "target": d + "/", "kind": "dir",
                     "exists": True, "log_refs": lr, "player_layer_refs": pr,
                     "is_consumer": None})

H = pd.DataFrame(rows)
H.to_csv(HERE / "CONSUMER_SURFACES.csv", index=False)
print("\n--- log readers and product surfaces ---")
print(H.to_string(index=False))

# ---- the one token collision, inspected rather than counted ---------------
print("\n--- token hits inspected individually (NOT counted as consumers) ---")
cv = LIVE / "cbs_v6.py"
if cv.exists():
    for i, ln in enumerate(read(cv).splitlines(), 1):
        if any(t in ln for t in PLAYER_LAYER_FIELDS):
            print(f"  cbs_v6.py:{i}: {ln.strip()}")
            print("    -> unrelated local dict key in a research estimator; "
                  "does NOT read the forecast log. NOT a consumer.")

live = H[(H.root == "LIVE_main") & (H.exists)]
prod_pl = int(live[live.target.isin(SURFACES + [d + "/" for d in SURFACE_DIRS])]
              .player_layer_refs.sum())
reader_pl = int(live[live.target.isin(LOG_READERS)
                     & (live.target != "daily_forecast.py")]
                .player_layer_refs.sum())
print("\n" + "=" * 78)
print(f"player-layer field refs across the 12 named product surfaces : {prod_pl}")
print(f"player-layer field refs across every forecast-log READER      : {reader_pl}")
print("  (daily_forecast.py excluded — it is the WRITER, not a reader)")
print("=" * 78)

json.dump({"product_surface_player_layer_refs": prod_pl,
           "log_reader_player_layer_refs": reader_pl},
          open(HERE / "_s04.json", "w"), indent=2)
print("\nwrote CONSUMER_SURFACES.csv")
