#!/usr/bin/env python3
"""TESTS.py -- MODEL_VS_MARKET fixtures with KNOWN ANSWERS.

Synthetic fixtures only (M00-U5 discipline: timing fields synthetic; no
fixture leans on vendor-asserted stamps). Every expected value below is
derived by hand in the comment beside it. Run: python TESTS.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[0] / "M11_CONSENSUS_MODEL"))

import consensus  # noqa: E402
from compute_model_vs_market import (  # noqa: E402
    _norm_name, cluster_bootstrap_ci, compare_cell, select_consensus_line)

FAILURES = []


def check(name, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {name}" + (f" -- {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(name)


# ---------------------------------------------------------------------------
# 1. de-vig via consensus.py (DELEGATED math): known closed-form answers
# ---------------------------------------------------------------------------
# over -110 / under -110: raw = 110/210 each = 0.523809...; multiplicative
# devig -> exactly 0.5.
probs, *_ = consensus.no_vig([-110, -110])
check("devig_symmetric_-110_-110_gives_0.5", abs(probs[0] - 0.5) < 1e-12)

# over -200 / under +150: raw_over = 200/300 = 2/3; raw_under = 100/250 = 0.4;
# sum = 16/15; p_over = (2/3)/(16/15) = 0.625 exactly.
probs, *_ = consensus.no_vig([-200, 150])
check("devig_-200_+150_gives_0.625", abs(probs[0] - 0.625) < 1e-12)

# ---------------------------------------------------------------------------
# 2. consensus_fair_value: two books, uniform weights -> mean of devigged
# ---------------------------------------------------------------------------
# book A: -200/+150 -> p_over 0.625 ; book B: -110/-110 -> 0.5
# uniform consensus = 0.5625 exactly. Synthetic timestamps.


def q(book, over, under):
    quote = consensus.make_quote(bookmaker=book, price=over,
                                 capture_ts=1_700_000_000, tier="T1",
                                 vendor_ts_semantics="unknown_unverified",
                                 market="player_points", outcome="over",
                                 point=15.5)
    quote["opposite_price"] = under
    return quote


obj = consensus.consensus_fair_value([q("A", -200, 150), q("B", -110, -110)],
                                     allow_t1=True, game_id="FIXTURE")
check("consensus_two_books_uniform_mean_0.5625",
      abs(obj["consensus_fair_prob"] - 0.5625) < 1e-12)
check("consensus_carries_preregistration_hash",
      obj["vig_method_preregistration_hash"] == consensus.PREREGISTRATION_HASH)
check("consensus_claims_no_ladder_label", obj["evidence_ladder_labels_held"] == [])
check("consensus_tier_is_T1_vendor_asserted_channel",
      obj["tier"] == "T1" and obj["channel"] == "VENDOR_ASSERTED")

# T2 quotes must be excluded by the machinery (tier discipline)
t2 = q("C", -110, -110)
t2["tier"] = "T2"
obj2 = consensus.consensus_fair_value([q("A", -110, -110), t2],
                                      allow_t1=True, game_id="FIXTURE")
check("consensus_excludes_T2_quotes", obj2["n_books_admitted"] == 1
      and obj2["n_excluded"] == 1)

# ---------------------------------------------------------------------------
# 3. consensus-line selection rule (frozen): modal -> median-closest -> lower
# ---------------------------------------------------------------------------
df = pd.DataFrame({"bookmaker_key": ["a", "b", "c", "a", "b"],
                   "line": [15.5, 15.5, 15.5, 16.5, 16.5]})
check("line_modal_wins", select_consensus_line(df) == 15.5)   # 3 books vs 2
# tie 2-2: lines 14.5 (books a,b) and 16.5 (books c,d); all-line median of
# [14.5,14.5,16.5,16.5] = 15.5, equidistant -> LOWER line wins.
df = pd.DataFrame({"bookmaker_key": ["a", "b", "c", "d"],
                   "line": [14.5, 14.5, 16.5, 16.5]})
check("line_tie_equidistant_takes_lower", select_consensus_line(df) == 14.5)
# tie 2-2 asymmetric: lines 13.5,13.5,16.5,16.5,17.5 -> counts {13.5:2,16.5:2,
# 17.5:1}; median 16.5 -> 16.5 closest among the tied -> 16.5 wins.
df = pd.DataFrame({"bookmaker_key": ["a", "b", "c", "d", "e"],
                   "line": [13.5, 13.5, 16.5, 16.5, 17.5]})
check("line_tie_median_closest_wins", select_consensus_line(df) == 16.5)

# ---------------------------------------------------------------------------
# 4. OU calls, paired accuracy, Brier, threshold distance: hand-computed cell
# ---------------------------------------------------------------------------
# 4 rows, all on one game date (1 cluster -> degenerate CI equals the point):
# row line  pred  p_over pts | outcome model_call model_ok market_call market_ok
# 1   15.5  18.0  0.60   20  | over    over  1          over   1
# 2   15.5  12.0  0.60   20  | over    under 0          over   1
# 3   10.5   9.0  0.40    8  | under   under 1          under  1
# 4   20.5  22.0  0.40   19  | under   over  0          under  1
# model acc = 2/4 = 0.5 ; market acc = 4/4 = 1.0 ; paired diff = -0.5
# Brier = mean((0.6-1)^2,(0.6-1)^2,(0.4-0)^2,(0.4-0)^2) = 0.16 exactly
# dist_model = |18-20|,|12-20|,|9-8|,|22-19| = 2,8,1,3 -> mean 3.5
# dist_line  = |15.5-20|,|15.5-20|,|10.5-8|,|20.5-19| = 4.5,4.5,2.5,1.5 -> 3.25
# paired dist diff = +0.25
fix = pd.DataFrame({
    "consensus_line": [15.5, 15.5, 10.5, 20.5],
    "pred_point": [18.0, 12.0, 9.0, 22.0],
    "p_over_devig": [0.60, 0.60, 0.40, 0.40],
    "pts": [20.0, 20.0, 8.0, 19.0],
    "game_date": ["2026-01-01"] * 4,
    "game_id": ["g1", "g1", "g2", "g2"],
})
cell = compare_cell(fix, "fixture", "fixture_tier")
check("cell_model_acc_0.5", abs(cell["model_ou_accuracy"] - 0.5) < 1e-12)
check("cell_market_acc_1.0", abs(cell["market_ou_accuracy"] - 1.0) < 1e-12)
check("cell_paired_diff_-0.5",
      abs(cell["paired_accuracy_diff_model_minus_market"] + 0.5) < 1e-12)
check("cell_brier_0.16", abs(cell["market_brier_devig_p_over"] - 0.16) < 1e-12)
b = cell["threshold_distance_block"]
check("cell_dist_model_3.5", abs(b["model_mean_abs_pred_minus_outcome"] - 3.5) < 1e-12)
check("cell_dist_line_3.25", abs(b["line_mean_abs_line_minus_outcome"] - 3.25) < 1e-12)
check("cell_dist_paired_diff_+0.25",
      abs(b["paired_diff_model_minus_line"] - 0.25) < 1e-12)
ci = cell["paired_accuracy_diff_ci95"]
check("cell_single_cluster_degenerate_ci_equals_point",
      abs(ci["lo"] + 0.5) < 1e-12 and abs(ci["hi"] + 0.5) < 1e-12)

# ---------------------------------------------------------------------------
# 5. clustered bootstrap: two clusters with opposite values -> CI spans them
# ---------------------------------------------------------------------------
vals = np.array([1.0, 1.0, -1.0, -1.0])
cl = np.array(["d1", "d1", "d2", "d2"])
ci = cluster_bootstrap_ci(vals, cl)
check("bootstrap_two_cluster_ci_spans_-1_to_1",
      ci["lo"] >= -1.0 - 1e-12 and ci["hi"] <= 1.0 + 1e-12
      and ci["lo"] < 0 < ci["hi"])
check("bootstrap_records_method_seed",
      ci["method"] == "cluster_bootstrap_over_game_dates_percentile"
      and ci["seed"] == 20260806 and ci["n_clusters"] == 2)

# ---------------------------------------------------------------------------
# 6. O14 name normalization (normalized-exact, no fuzz)
# ---------------------------------------------------------------------------
check("norm_diacritics_and_punct",
      _norm_name("A'ja  WILSON") == "ajawilson"
      and _norm_name("Iliana Rupert") == _norm_name("Iliana Rupért"))
check("norm_does_NOT_bridge_real_variants",
      _norm_name("Cheyenne Parker") != _norm_name("Cheyenne Parker-Tyus"))

print()
if FAILURES:
    print(f"{len(FAILURES)} FAILURE(S): {FAILURES}")
    sys.exit(1)
print("ALL TESTS PASS")
