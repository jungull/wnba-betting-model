#!/usr/bin/env python
"""test_cbs_builders.py — invariance tests for the v3 baseline-suite builders.

**Synthetic and toy data only.** Nothing here reads a contract parquet, fits a
real model, or produces a forecast, accuracy figure or coverage number. The
point is to demonstrate that the `contract_baseline_suite_v3` specification is
executable and that the properties it claims actually hold.

The properties under test are the ones whose violation would silently
manufacture a favourable result:

  A. selection and calibration outcomes are DISJOINT (v2's real defect);
  B. play history counts candidate OBLIGATIONS, so 0-of-4 is distinguished from
     no-evidence, and only no-evidence takes the base-rate default;
  C. estimators are strictly shifted -- no row sees its own outcome;
  D. alpha selection is ordered, masked, tie-broken to the smallest alpha, and
     reports boundary solutions instead of hiding them;
  E. dispersion comes from calibration residuals with the frozen estimator, and
     emitted quantiles are truncated THEN monotone.

Usage:  python tests/test_cbs_builders.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cbs_builders as cb  # noqa: E402

PASSED = 0
FAILED: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASSED
    if cond:
        PASSED += 1
    else:
        FAILED.append(f"{name}: {detail}")


def toy_frame(n_players: int = 6, n_dates: int = 40, seed: int = 7) -> pd.DataFrame:
    """A small deterministic candidate frame. Not real data, and not fitted."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2099-05-01", periods=n_dates, freq="D")
    rows = []
    for pid in range(n_players):
        for d in dates:
            appeared = int(rng.random() < (0.5 + 0.08 * pid))
            minutes = float(rng.uniform(8, 34)) if appeared else 0.0
            rows.append({
                "player_id": f"P{pid}", "season": 2099, "game_date": d,
                "appeared": appeared, "minutes": minutes,
                "fga": float(rng.poisson(max(minutes, 0.1) * 0.35)),
                "points": float(rng.poisson(max(minutes, 0.1) * 0.45)),
            })
    return pd.DataFrame(rows).reset_index(drop=True)


df = toy_frame()

# ---------------------------------------------------------------------------
# A. disjoint selection / calibration
# ---------------------------------------------------------------------------
sp = cb.split_tuning_calibration(df)
check("split is not degenerate on a healthy window", not sp.degenerate, sp.reason)
check("tuning and calibration rows are disjoint",
      len(np.intersect1d(sp.tuning_idx, sp.calibration_idx)) == 0)
check("tuning and calibration dates are disjoint",
      not (set(sp.tuning_dates) & set(sp.calibration_dates)))
check("split covers every training row",
      len(sp.tuning_idx) + len(sp.calibration_idx) == len(df))
check("calibration tail is strictly LATER than every tuning date",
      min(sp.calibration_dates) > max(sp.tuning_dates),
      f"{min(sp.calibration_dates)} vs {max(sp.tuning_dates)}")

# no date may straddle the boundary -- a heavy slate must land entirely on one side
tune_dates = set(df.loc[sp.tuning_idx, "game_date"])
cal_dates = set(df.loc[sp.calibration_idx, "game_date"])
check("no date straddles the split", not (tune_dates & cal_dates),
      str(sorted(tune_dates & cal_dates))[:200])

check("assert_disjoint accepts a valid split", sp.assert_disjoint() is None)

# a deliberately corrupted split must be caught, not tolerated
bad = cb.TrainSplit(tuning_idx=np.array([0, 1, 2]), calibration_idx=np.array([2, 3]),
                    tuning_dates=[1], calibration_dates=[2], boundary_date=2)
try:
    bad.assert_disjoint()
    check("overlapping split raises SelectionLeakage", False, "no exception")
except cb.SelectionLeakage:
    check("overlapping split raises SelectionLeakage", True)

# degenerate windows are reported, never silently split
tiny = cb.split_tuning_calibration(toy_frame(n_players=2, n_dates=5))
check("short window is flagged degenerate", tiny.degenerate, tiny.reason)
check("degenerate window yields NO calibration rows", len(tiny.calibration_idx) == 0,
      "a degenerate window must fall back to declared constants, not reuse tuning")
check("empty window is degenerate",
      cb.split_tuning_calibration(df.iloc[0:0]).degenerate)

# ---------------------------------------------------------------------------
# B. candidate-obligation history
# ---------------------------------------------------------------------------
hist = cb.prior_candidate_history(df)
check("history aligns to the input index", list(hist.index) == list(df.index))

first_rows = hist[hist["n_prior_candidate_games"] == 0]
check("first obligation has no prior appearances",
      (first_rows["n_prior_appearances"] == 0).all())
check("first obligation has NaN p_plays_prior (no evidence)",
      first_rows["p_plays_prior"].isna().all())
check("first obligation is flagged as having no prior obligation",
      (~first_rows["has_prior_obligation"]).all())
check("prior appearances never exceed prior obligations",
      (hist["n_prior_appearances"] <= hist["n_prior_candidate_games"]).all())

# the exact case Codex named: 0 appearances across k>0 obligations is EVIDENCE
never = pd.DataFrame({
    "player_id": ["X"] * 5, "season": [2099] * 5,
    "game_date": pd.date_range("2099-05-01", periods=5, freq="D"),
    "appeared": [0, 0, 0, 0, 0],
})
nh = cb.prior_candidate_history(never)
check("0-of-k history is 0.0, not NaN",
      list(nh["p_plays_prior"])[1:] == [0.0, 0.0, 0.0, 0.0],
      str(list(nh["p_plays_prior"])))
check("0-of-k rows count their obligations",
      list(nh["n_prior_candidate_games"]) == [0, 1, 2, 3, 4],
      str(list(nh["n_prior_candidate_games"])))

filled = cb.apply_base_rate_default(nh, base_rate=0.77)
check("base rate fills ONLY the no-obligation row", filled.iloc[0] == 0.77)
check("base rate does NOT overwrite real 0-of-k evidence",
      list(filled)[1:] == [0.0, 0.0, 0.0, 0.0], str(list(filled)))

always = never.copy()
always["appeared"] = 1
ah = cb.prior_candidate_history(always)
check("all-appeared history is 1.0", list(ah["p_plays_prior"])[1:] == [1.0] * 4)

# ---------------------------------------------------------------------------
# C. estimators are strictly shifted
# ---------------------------------------------------------------------------
e = cb.shifted_ewma(df, df["minutes"], 0.30)
check("shifted EWMA aligns to the input index", list(e.index) == list(df.index))
first_per_player = df.groupby(["player_id", "season"])["game_date"].idxmin()
check("first row per player has no EWMA (nothing prior)",
      e.loc[first_per_player].isna().all())

# the decisive leakage test: perturb ONLY the last row's outcome; no earlier
# feature may move, and the last row's own feature must not move either
df2 = df.copy()
last = df2.sort_values(["player_id", "season", "game_date"]).index[-1]
df2.loc[last, "minutes"] = df2.loc[last, "minutes"] + 1000.0
e2 = cb.shifted_ewma(df2, df2["minutes"], 0.30)
check("changing a row's outcome cannot change its own feature",
      (pd.isna(e.loc[last]) and pd.isna(e2.loc[last])) or e.loc[last] == e2.loc[last],
      f"{e.loc[last]} -> {e2.loc[last]}")
check("changing the last outcome changes no other row's feature",
      e.drop(index=last).equals(e2.drop(index=last)))

r = cb.shifted_ratio_ewma(df, df["fga"], df["minutes"], 0.05)
check("ratio EWMA aligns to the input index", list(r.index) == list(df.index))
zero = pd.DataFrame({
    "player_id": ["Z"] * 4, "season": [2099] * 4,
    "game_date": pd.date_range("2099-05-01", periods=4, freq="D"),
    "fga": [0.0, 0.0, 3.0, 4.0], "minutes": [0.0, 0.0, 10.0, 12.0],
})
rz = cb.shifted_ratio_ewma(zero, zero["fga"], zero["minutes"], 0.05)
check("zero EWMA denominator yields NaN, never a silent zero",
      bool(pd.isna(rz.iloc[1])), f"got {rz.iloc[1]}")

# ---------------------------------------------------------------------------
# D. ordered, masked, tie-broken alpha selection
# ---------------------------------------------------------------------------
y = pd.Series(np.arange(len(df), dtype=float), index=df.index)
flat = cb.select_alpha(lambda a: y + 1.0, y, pd.Series(True, index=df.index))
check("an exactly flat curve ties to the SMALLEST alpha",
      flat.alpha == cb.ALPHA_GRID[0], str(flat.alpha))
check("a lower-corner solution is REPORTED as a boundary", flat.boundary == "lower",
      "a boundary solution must be reported, not fixed by widening the grid")

upper = cb.select_alpha(lambda a: y + (1.0 / a), y, pd.Series(True, index=df.index))
check("an upper-corner solution is reported", upper.boundary == "upper", str(upper.alpha))

interior = cb.select_alpha(lambda a: y + abs(a - 0.15) * 10, y,
                           pd.Series(True, index=df.index))
check("an interior optimum is found and not called a boundary",
      interior.alpha == 0.15 and interior.boundary == "", str(interior.alpha))

empty_mask = cb.select_alpha(lambda a: y, y, pd.Series(False, index=df.index))
check("empty mask falls back to the declared default alpha",
      empty_mask.used_default and empty_mask.alpha == cb.DEFAULT_ALPHA)

# the mask must actually bind: rows outside it may not influence the choice
mask = df["appeared"].astype(bool)
poison = y.copy()
poison[~mask] = 1e9
sel_a = cb.select_alpha(lambda a: y + abs(a - 0.20) * 5, y, mask)
sel_b = cb.select_alpha(lambda a: poison + abs(a - 0.20) * 5, y, mask)
check("rows outside the mask cannot change the selected alpha",
      sel_a.alpha == sel_b.alpha, f"{sel_a.alpha} vs {sel_b.alpha}")

# ordering: attempts/points must be built against the FIXED minutes alpha
seen: list[float] = []
sel = cb.select_alpha_ordered(
    builders={
        "minutes": lambda a: y + abs(a - 0.30) * 3,
        "attempts": lambda a, m: seen.append(m) or (y + abs(a - 0.05) * 3),
        "points": lambda a, m: y + abs(a - 0.40) * 3,
    },
    y={"minutes": y, "attempts": y, "points": y},
    masks={k: pd.Series(True, index=df.index) for k in ("minutes", "attempts", "points")},
)
check("minutes alpha is selected first", sel["minutes"].alpha == 0.30, str(sel["minutes"].alpha))
check("attempts sees the FIXED minutes alpha every time",
      set(seen) == {0.30}, str(set(seen)))
check("the held-fixed minutes alpha is recorded as provenance",
      sel["_minutes_alpha_held_fixed_at"] == 0.30)
check("attempts alpha is selected on its own curve", sel["attempts"].alpha == 0.05)
check("points alpha is selected on its own curve", sel["points"].alpha == 0.40)

# ---------------------------------------------------------------------------
# E. dispersion and quantile emission
# ---------------------------------------------------------------------------
rng = np.random.default_rng(11)
resid = rng.normal(0, 3.0, 500)
sd, off, method = cb.dispersion_from_residuals(resid, min_resid=cb.MIN_RESID_PLAYER)
check("large residual pool uses empirical quantiles", method == "empirical", method)
check("sd uses ddof=1", abs(sd - np.std(resid, ddof=1)) < 1e-12)
check("empirical offsets are ascending", bool(np.all(np.diff(off) >= 0)))

sd2, off2, method2 = cb.dispersion_from_residuals(resid[:20], min_resid=cb.MIN_RESID_PLAYER)
check("small residual pool falls back to Gaussian", method2 == "gaussian", method2)
check("Gaussian offsets are z*sd", np.allclose(off2, np.asarray(cb.QUANTILE_Z) * sd2))
check("degenerate residual pool is reported, not guessed",
      cb.dispersion_from_residuals(np.array([1.0]), min_resid=5)[2] == "insufficient")

point = np.array([20.0, 1.0, 47.0])
q = cb.emit_quantiles(point, off2, low=0.0, high=48.0)
check("quantiles are monotone per row", bool(np.all(np.diff(q, axis=1) >= 0)))
check("quantiles respect the lower bound", bool(np.all(q >= 0.0)))
check("quantiles respect the upper bound", bool(np.all(q <= 48.0)))
check("truncation happens BEFORE the sort (no non-monotone survivor)",
      bool(np.all(np.diff(cb.emit_quantiles(np.array([0.5]), off2, low=0.0),
                          axis=1) >= 0)))
check("team points floor is frozen at 1e-6", cb.TEAM_POINTS_FLOOR == 1e-6)
tq = cb.emit_quantiles(np.array([1.0]), np.array([-5.0, -1.0, 0.0, 1.0, 5.0]),
                       low=cb.TEAM_POINTS_FLOOR)
check("team points quantiles stay strictly positive", bool(np.all(tq > 0)))

# frozen grids must match the registered specification exactly
check("alpha grid is the registered 11-point grid",
      cb.ALPHA_GRID == (0.01, 0.02, 0.03, 0.05, 0.075, 0.10, 0.15, 0.20, 0.30, 0.40, 0.50))
check("alpha grid is strictly ascending (tie-break depends on it)",
      all(a < b for a, b in zip(cb.ALPHA_GRID, cb.ALPHA_GRID[1:])))
check("lambda grid matches round(logspace(-2,4,13), 6)",
      cb.LAMBDA_GRID == tuple(round(float(x), 6) for x in np.logspace(-2, 4, 13)))
check("quantile levels are the contract's five",
      cb.QUANTILE_LEVELS == (0.05, 0.25, 0.50, 0.75, 0.95))

# ---------------------------------------------------------------------------
# F. the v3 document's feature order must EQUAL the hashed registry order
#    (coefficient and model hashes are positional; a doc that disagrees with
#    the registry makes them uncheckable)
# ---------------------------------------------------------------------------
import json  # noqa: E402
import re  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
reg_path = ROOT / "experiments" / "registry.jsonl"
doc_path = ROOT / "project_docs" / "CONTRACT_BASELINE_SUITE_V3.md"

if reg_path.exists() and doc_path.exists():
    rec = None
    for line in reg_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("experiment_id") == "contract_baseline_suite_v3":
            rec = r
    check("v3 record is present in the registry", rec is not None)

    if rec is not None:
        canonical = rec["extra"]["frozen_config"]["components"]["p_active"][
            "features_canonical_order"]
        check("registry canonical order has 14 features", len(canonical) == 14,
              str(len(canonical)))

        doc = doc_path.read_text(encoding="utf-8")
        block = doc.split("```", 2)[1] if "```" in doc else ""
        pairs = sorted((int(i), name) for i, name in
                       re.findall(r"(\d+)\s+([a-z_][a-z0-9_]*)", block))
        doc_order = [name for _, name in pairs]
        check("document lists 14 features", len(doc_order) == 14, str(doc_order))
        check("document feature order EQUALS the hashed registry order",
              doc_order == canonical,
              f"doc={doc_order}\nreg={canonical}")
        check("indices in the document are 1..14 with no gaps",
              [i for i, _ in pairs] == list(range(1, 15)), str([i for i, _ in pairs]))

        # the regime-B features must not have crept back in
        fc = rec["extra"]["frozen_config"]
        excluded = set(fc["components"]["p_active"]["features_excluded_regime_b"])
        check("no regime-B archive feature is in the canonical order",
              not (excluded & set(canonical)), str(excluded & set(canonical)))

        # frozen numerics must agree with the executable core
        check("registry team-points floor matches cbs_builders",
              fc["support_and_floors"]["team_game_distribution"]["low"]
              == cb.TEAM_POINTS_FLOOR)
        check("registry alpha grid matches cbs_builders",
              tuple(fc["components"]["attempts_usage"]["alpha_grid"]) == cb.ALPHA_GRID)
        check("registry lambda grid matches cbs_builders",
              tuple(fc["components"]["p_active"]["lambda_grid"]) == cb.LAMBDA_GRID)
        check("registry calibration tail fraction matches cbs_builders",
              fc["disjoint_selection_and_calibration"]["player_targets"]["tail_fraction"]
              == cb.CALIBRATION_TAIL_FRACTION)
        check("registry min residual counts match cbs_builders",
              fc["uncertainty_rule"]["min_residuals"]["player"] == cb.MIN_RESID_PLAYER
              and fc["uncertainty_rule"]["min_residuals"]["team"] == cb.MIN_RESID_TEAM)
        check("v3 record declares computed_nothing",
              rec["extra"]["computed_nothing"] is True)

print(f"{PASSED}/{PASSED + len(FAILED)} tests passed")
for f in FAILED:
    print(f"  FAIL  {f}")
sys.exit(1 if FAILED else 0)
