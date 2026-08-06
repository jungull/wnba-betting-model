#!/usr/bin/env python3
"""TESTS.py -- fixture (synthetic known-answer) tests for every metric
computation in compute_player_granular.py. These are IMPLEMENTATION tests
(D036 point 1): they are never predictive evidence.

Run:  python TESTS.py
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import compute_player_granular as G  # noqa: E402
import consensus  # noqa: E402  (path added by the import above)

PASS = []
FAIL = []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  [{detail}]" if detail and not cond else ""))


def approx(a, b, tol=1e-9) -> bool:
    return abs(a - b) <= tol


# ---------------------------------------------------------------------------
# 1. MIN parsing
# ---------------------------------------------------------------------------
print("MIN parsing")
check("parse_min mm:ss", approx(G.parse_min("33:02"), 33 + 2 / 60))
check("parse_min noisy decimals", approx(G.parse_min("30.000000:46"), 30 + 46 / 60))
check("parse_min bare int", approx(G.parse_min(28), 28.0))
check("parse_min bare float str", approx(G.parse_min("12.5"), 12.5))
check("parse_min None -> 0", approx(G.parse_min(None), 0.0))
check("parse_min NaN -> 0", approx(G.parse_min(float("nan")), 0.0))
try:
    G.parse_min("garbage")
    check("parse_min garbage raises", False)
except ValueError:
    check("parse_min garbage raises", True)

# ---------------------------------------------------------------------------
# 2. name normalization
# ---------------------------------------------------------------------------
print("name normalization")
check("accent fold", G.normalize_name("Gabby Williamsé") == "gabby williamse")
check("punct/hyphen", G.normalize_name("Skylar Diggins-Smith") == "skylar diggins smith")
check("apostrophe", G.normalize_name("A'ja Wilson") == "a ja wilson")
check("case/space", G.normalize_name("  BREANNA   Stewart ") == "breanna stewart")

# ---------------------------------------------------------------------------
# 3. MAE / RMSE / bias known answers
# ---------------------------------------------------------------------------
print("mae/rmse/bias")
m = G.mae_rmse_bias(np.array([1.0, 2.0, 5.0]), np.array([2.0, 2.0, 1.0]))
# errors pred-actual: -1, 0, 4  -> mae 5/3, rmse sqrt(17/3), bias 1.0
check("mae", approx(m["mae"], 5 / 3))
check("rmse", approx(m["rmse"], math.sqrt(17 / 3)))
check("bias sign is pred-minus-actual", approx(m["bias"], 1.0))

# ---------------------------------------------------------------------------
# 4. cluster bootstrap
# ---------------------------------------------------------------------------
print("cluster bootstrap CI")
v = np.array([2.0, 2.0, 2.0, 2.0])
ci = G.cluster_bootstrap_ci(v, np.array(["d1", "d1", "d2", "d2"]), n_boot=200, seed=1)
check("degenerate values -> point CI", approx(ci["lo"], 2.0) and approx(ci["hi"], 2.0))
v2 = np.array([0.0, 0.0, 10.0, 10.0])
ci_a = G.cluster_bootstrap_ci(v2, np.array(["d1", "d1", "d2", "d2"]), n_boot=300, seed=7)
ci_b = G.cluster_bootstrap_ci(v2, np.array(["d1", "d1", "d2", "d2"]), n_boot=300, seed=7)
check("seeded reproducibility", ci_a == ci_b)
check("two-cluster CI spans cluster means", ci_a["lo"] >= 0.0 and ci_a["hi"] <= 10.0
      and ci_a["hi"] > ci_a["lo"])
check("cluster count recorded", ci_a["n_clusters"] == 2 and ci_a["seed"] == 7)

# ---------------------------------------------------------------------------
# 5. baseline predictions on a synthetic frame (hand-computed)
# ---------------------------------------------------------------------------
print("baseline construction (strictly-prior)")
# Player 1: games on d1..d7 pts 10,20,30,40,50,60,70; player 2: d1,d2 pts 0,8.
# Season 2030 only. Dates sortable strings.
rows = []
for i, p in enumerate([10, 20, 30, 40, 50, 60, 70]):
    rows.append(dict(game_id=f"g{i+1}", player_id=1, player_name="A One",
                     season=2030, game_date=f"2030-06-0{i+1}", pts=float(p)))
rows.append(dict(game_id="g1", player_id=2, player_name="B Two",
                 season=2030, game_date="2030-06-01", pts=0.0))
rows.append(dict(game_id="g2", player_id=2, player_name="B Two",
                 season=2030, game_date="2030-06-02", pts=8.0))
syn = pd.DataFrame(rows)
for c in G.STAT_COL.values():
    if c not in syn:
        syn[c] = syn["pts"]  # duplicate pts into every stat column
syn = syn.sort_values(["season", "player_id", "game_date", "game_id"],
                      kind="mergesort").reset_index(drop=True)
out = G.add_baseline_predictions(syn)
p1 = out[out.player_id == 1].reset_index(drop=True)
p2 = out[out.player_id == 2].reset_index(drop=True)

check("t5 cold start first game NaN", np.isnan(p1.loc[0, "pred_t5__pts"]))
check("t5 game2 = prior game", approx(p1.loc[1, "pred_t5__pts"], 10.0))
check("t5 game4 = mean(10,20,30)", approx(p1.loc[3, "pred_t5__pts"], 20.0))
# game 7 window = last 5 priors: 20,30,40,50,60 -> 40
check("t5 game7 = mean(last 5 priors)", approx(p1.loc[6, "pred_t5__pts"], 40.0))
check("std game7 = mean(all 6 priors)", approx(p1.loc[6, "pred_std__pts"], 35.0))
check("std cold start NaN", np.isnan(p2.loc[0, "pred_std__pts"]))
# league mean: date d2 -> mean of ALL rows on d1 = (10 + 0)/2 = 5
check("league mean d2 = mean of all d1 rows", approx(p1.loc[1, "pred_lg__pts"], 5.0)
      and approx(p2.loc[1, "pred_lg__pts"], 5.0))
# d3 -> mean of d1+d2 rows = (10+0+20+8)/4 = 9.5
check("league mean d3 strictly prior dates", approx(p1.loc[2, "pred_lg__pts"], 9.5))
check("league mean season first date NaN", np.isnan(p1.loc[0, "pred_lg__pts"])
      and np.isnan(p2.loc[0, "pred_lg__pts"]))

# metric cell on the fixture: player 1 t5 errors known
cell, cov = G.baseline_metric_cell(out, "points", "trailing_5_mean", 2030)
# evaluated rows: p1 g2..g7 (preds 10,15,20,25,30... wait) recompute:
# p1 preds: g2=10,g3=15,g4=20,g5=25,g6=30,g7=40 vs actual 20,30,40,50,60,70
# abs err: 10,15,20,25,30,30 ; p2 g2 pred 0 vs 8 -> 8
expected_mae = (10 + 15 + 20 + 25 + 30 + 30 + 8) / 7
check("fixture cell MAE hand-computed", approx(cell["mae"], expected_mae))
check("fixture cold-start count", cell["n_cold_start_excluded"] == 2
      and cov["n_evaluated"] == 7)
check("evidence class label", cell["evidence_class"] == "NAIVE_BASELINE")

# ---------------------------------------------------------------------------
# 6. de-vig (delegated to M11 consensus.py)
# ---------------------------------------------------------------------------
print("de-vig")
check("symmetric -110/-110 -> 0.5", approx(G.devig_p_over(-110, -110), 0.5))
# hand-computed multiplicative devig for -124/-107:
r_over = 124 / 224
r_under = 107 / 207
check("known-answer -124/-107",
      approx(G.devig_p_over(-124, -107), r_over / (r_over + r_under)))
check("preregistered method is multiplicative",
      consensus.PREREGISTERED_VIG_METHOD == "multiplicative_proportional")
check("probs sum to 1",
      approx(G.devig_p_over(150, -180) + G.devig_p_over(-180, 150), 1.0))

# ---------------------------------------------------------------------------
# 7. market join + threshold metrics on a synthetic fixture
# ---------------------------------------------------------------------------
print("market join and threshold metrics")
outcomes = out[["game_id", "player_name", "season", "game_date"]
               + list(G.STAT_COL.values())].copy()
props = pd.DataFrame([
    # p1 g2: line 15.5, actual 20 -> over. Book leans over (p_over>0.5): correct.
    dict(game_id="g2", market_key="player_points", player_name="A. One",
         bookmaker_key="bookx", line=15.5, over_price=-130, under_price=+110),
    # p1 g3: line 35.5, actual 30 -> under. Book leans over: incorrect.
    dict(game_id="g3", market_key="player_points", player_name="A One",
         bookmaker_key="bookx", line=35.5, over_price=-130, under_price=+110),
    # p2 g2: push line 8.0, actual 8 -> excluded from OU/Brier, kept in tMAE.
    dict(game_id="g2", market_key="player_points", player_name="B Two",
         bookmaker_key="booky", line=8.0, over_price=-110, under_price=-110),
    # unmatched player (never played)
    dict(game_id="g2", market_key="player_points", player_name="C Three",
         bookmaker_key="bookx", line=9.5, over_price=-110, under_price=-110),
    # one-sided quote -> excluded and counted
    dict(game_id="g3", market_key="player_points", player_name="A One",
         bookmaker_key="booky", line=30.5, over_price=-110, under_price=None),
    # unsupported market family -> excluded and counted
    dict(game_id="g3", market_key="player_rebounds", player_name="A One",
         bookmaker_key="bookx", line=5.5, over_price=-110, under_price=-110),
])
j, audit = G.market_rows(props, outcomes)
check("unsupported family filtered+counted",
      audit["n_raw_rows"] == 6 and audit["n_rows_supported_market_families"] == 5)
check("one-sided excluded+counted", audit["n_rows_missing_a_side_excluded"] == 1)
check("matched rows", audit["n_quote_rows_matched"] == 3)
check("unmatched listed no silent drop",
      audit["n_quote_rows_unmatched"] == 1 and
      audit["unmatched_player_games"][0]["player_name"] == "C Three")
check("punctuated name matches", (j["norm_name"] == "a one").sum() == 2)
check("push flagged", audit["n_push_rows_excluded_from_ou_and_brier"] == 1)

cell = G.market_metric_cell(j, "points", "pooled")
# threshold MAE over all 3 matched rows: |15.5-20|+|35.5-30|+|8-8| = 4.5+5.5+0
check("threshold_mae hand-computed", approx(cell["threshold_mae"], 10.0 / 3))
check("threshold_mae labeled not projection MAE",
      "NOT a projection MAE" in cell["threshold_mae_note"])
# OU: two non-push rows, book leaned over both times; g2 over hit, g3 did not.
check("ou accuracy hand-computed", approx(cell["devig_ou_accuracy"], 0.5))
p_over_130 = G.devig_p_over(-130, 110)
expected_brier = ((p_over_130 - 1.0) ** 2 + (p_over_130 - 0.0) ** 2) / 2
check("brier hand-computed", approx(cell["devig_brier"], expected_brier))
check("push excluded count on cell", cell["n_push_excluded"] == 1)
check("evidence class market", cell["evidence_class"] == "MARKET_THRESHOLD")
per_book = G.market_metric_cell(j, "points", "pooled", book="booky")
check("per-book universe restriction", per_book["n_quote_rows"] == 1
      and per_book["bookmaker"] == "booky")

# ---------------------------------------------------------------------------
print()
print(f"{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILURES:", FAIL)
    sys.exit(1)
