#!/usr/bin/env python
"""test_cbs_generator.py — synthetic integration + invariance suite for v4.

**Synthetic data only.** No contract parquet is read, no historical OOF is
produced, no accuracy or coverage figure is computed or inspected. The frames
below are fabricated in-process; the generator has no file I/O at all, so it
cannot reach real data even by mistake.

Integration coverage (every stage of the registered v4 pipeline):
  Stage-A contract-row features; standardisation, IRLS logistic fitting and λ
  tuning; target-specific masks and fallback means; ordered minutes/attempts/
  points tuning with the minutes leg fixed; team-channel tuning, T2 calibration-
  map fitting and T3 dispersion; season-2021 emission; full obligation-row
  output; provenance; exclusion cross-tabs; and the REAL
  `prediction_contract_v2.validate_predictions()`.

Required negative / invariance tests:
  N1 perturbing calibration or outer-test outcomes cannot change any selected
     parameter, base rate, fallback mean, or fitted-prefix feature
  N2 an intentionally contaminated selection call is rejected
  N3 inactive rows affect p_active but cannot affect conditional-target
     tuning/fallbacks
  N4 both team rows and whole dates stay in exactly one T1/T2/T3 segment
  N5 zero-candidate and excluded obligations stay visible; every required row
     is emitted
  N6 constant and degenerate residual pools fail closed to the fallback
  N7 duplicate / tied candidate obligations fail closed
  N8 validation, provenance, coverage obligations and exclusion accounting pass
     before any scoring path can run
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import cbs_generator as gen  # noqa: E402
import cbs_pipeline as pipe  # noqa: E402
from cbs_builders import SelectionLeakage  # noqa: E402
from prediction_contract_v2 import validate_predictions  # noqa: E402

PASSED = 0
FAILED: list[str] = []
CFG = "synthetic-config-hash"


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASSED
    if cond:
        PASSED += 1
    else:
        FAILED.append(f"{name}: {detail}")


# --------------------------------------------------------------------------
# synthetic contract-shaped frames
# --------------------------------------------------------------------------

def player_frame(n_players=8, n_dates=48, seed=3, start="2099-05-01"):
    rng = np.random.default_rng(seed)
    dates = pd.date_range(start, periods=n_dates, freq="D")
    rows = []
    for gi, d in enumerate(dates):
        for pid in range(n_players):
            appeared = int(rng.random() < 0.55 + 0.04 * pid)
            minutes = float(rng.uniform(9, 33)) if appeared else 0.0
            rows.append({
                "row_uid": f"pg_{gi:04d}_{pid}",
                "player_id": f"P{pid}", "season": 2099,
                "game_id": f"G{gi:04d}", "game_date": d,
                "forecast_cutoff": (d - pd.Timedelta(hours=6)).tz_localize("UTC").isoformat(),
                "feature_asof": (d - pd.Timedelta(hours=12)).tz_localize("UTC").isoformat(),
                "appeared": appeared, "in_target_box": bool(appeared),
                "minutes": minutes,
                "fga": float(rng.poisson(max(minutes, .1) * .35)) if appeared else 0.0,
                "points": float(rng.poisson(max(minutes, .1) * .45)) if appeared else 0.0,
                "team_gp_season": float(gi),
            })
    return pd.DataFrame(rows).reset_index(drop=True)


def team_frame(n_teams=6, n_dates=48, seed=5, start="2099-05-01"):
    rng = np.random.default_rng(seed)
    dates = pd.date_range(start, periods=n_dates, freq="D")
    rows = []
    for gi, d in enumerate(dates):
        for pair in range(n_teams // 2):                 # two rows per game
            gid = f"TG{gi:04d}_{pair}"
            for side in (0, 1):
                tid = f"T{pair * 2 + side}"
                rows.append({
                    "row_uid": f"tg_{gi:04d}_{pair}_{side}",
                    "team_id": tid, "game_id": gid, "season": 2099, "game_date": d,
                    "forecast_cutoff": (d - pd.Timedelta(hours=6)).tz_localize("UTC").isoformat(),
                    "feature_asof": (d - pd.Timedelta(hours=12)).tz_localize("UTC").isoformat(),
                    "ch_ft": float(rng.uniform(10, 20)), "ch_fg3": float(rng.uniform(15, 30)),
                    "ch_paint": float(rng.uniform(25, 40)), "ch_np2": float(rng.uniform(8, 18)),
                    "team_points": float(rng.uniform(68, 96)),
                    "n_candidates": 12,
                })
    return pd.DataFrame(rows).reset_index(drop=True)


def universe_for(df, target, required=True):
    u = df[["row_uid"]].copy()
    u[f"prediction_required__{target}"] = required
    sc = df["appeared"].astype(bool) if "appeared" in df.columns else True
    u[f"outcome_scoreable__{target}"] = sc if target != "p_active" else True
    for c in ("in_target_box", "appeared"):
        if c in df.columns:
            u[c] = df[c].to_numpy()
    return u


TRAIN = player_frame(seed=3, start="2099-05-01")
TEST = player_frame(seed=9, start="2099-08-01", n_dates=12)
T_TRAIN = team_frame(seed=5, start="2099-05-01")
T_TEST = team_frame(seed=11, start="2099-08-01", n_dates=8)

res = pipe.run_player_fold(TRAIN, TEST, "season:2099", config_hash=CFG)
P, D = res["predictions"], res["diagnostics"]

# --------------------------------------------------------------------------
# integration
# --------------------------------------------------------------------------
check("fold is not degenerate on a healthy window", not D["degenerate"], D.get("reason", ""))
check("all four player targets emitted", set(P) == {
    "p_active", "e_minutes_given_active", "attempts_usage",
    "player_scoring_distribution"}, str(set(P)))

for tgt, pred in P.items():
    check(f"{tgt}: every obligation row emitted", len(pred) == len(TEST),
          f"{len(pred)} vs {len(TEST)}")
    check(f"{tgt}: row_uids unique", not pred.row_uid.duplicated().any())
    for h in ("model_hash", "config_hash", "data_snapshot_hash"):
        check(f"{tgt}: {h} present on every predicted row",
              pred[pred.exclusion_reason.isna()][h].notna().all())
    v = validate_predictions(pred, universe_for(TEST, tgt), tgt)
    check(f"{tgt}: REAL validate_predictions accepts the output", v["ok"], str(v["problems"]))
    check(f"{tgt}: prediction_coverage is 1.0", v["prediction_coverage"] == 1.0,
          str(v["prediction_coverage"]))
    check(f"{tgt}: coverage reported separately from scoreable",
          "scoreable_coverage" in v and "prediction_coverage" in v)

check("Stage-A produced 14 features in canonical order",
      list(gen.stage_a_features(TRAIN, __import__("cbs_builders")
                                .prior_candidate_history(TRAIN), 0.5).columns)
      == gen.P_ACTIVE_FEATURES)
check("lambda was selected from the frozen grid",
      D["selected"]["lambda"] in gen.LAMBDA_GRID, str(D["selected"]["lambda"]))
check("p_active stays inside [0,1]",
      bool(P["p_active"].pred_point.between(0, 1).all()))
check("p_active emits null sd by contract", bool(P["p_active"].pred_sd.isna().all()))
for tgt in ("e_minutes_given_active", "attempts_usage", "player_scoring_distribution"):
    check(f"{tgt}: pred_sd strictly positive", bool((P[tgt].pred_sd > 0).all()))
    q = P[tgt][["pred_q05", "pred_q25", "pred_q50", "pred_q75", "pred_q95"]].to_numpy()
    check(f"{tgt}: quantiles monotone", bool(np.all(np.diff(q, axis=1) >= -1e-12)))
check("minutes are truncated to [0,48]",
      bool(P["e_minutes_given_active"].pred_point.between(0, 48).all()))
check("attempts are non-negative", bool((P["attempts_usage"].pred_point >= 0).all()))

check("minutes alpha selected from the frozen grid",
      D["selected"]["minutes_alpha"] in gen.ALPHA_GRID)
check("the minutes leg is recorded as held fixed",
      D["selected"]["minutes_alpha_held_fixed_at"] == D["selected"]["minutes_alpha"])
check("attempts and points alphas selected", "attempts_alpha" in D["selected"]
      and "points_alpha" in D["selected"])
check("dispersion recorded per conditional target",
      set(D["dispersion"]) == {"e_minutes_given_active", "attempts_usage",
                               "player_scoring_distribution"}, str(set(D["dispersion"])))
check("fallback means recorded per conditional target", len(D["fallback_mean"]) == 3)

# season:2021 -- empty training window
empty = TRAIN.iloc[0:0]
r21 = pipe.run_player_fold(empty, TEST, "season:2021", config_hash=CFG)
check("season:2021 is degenerate", r21["diagnostics"]["degenerate"])
check("season:2021 uses declared constants",
      r21["diagnostics"]["fallback"] == "declared_constants")
for tgt, pr in r21["predictions"].items():
    check(f"season:2021 {tgt}: every obligation still emitted", len(pr) == len(TEST))
    check(f"season:2021 {tgt}: flagged fallback AND cold start",
          bool(pr.is_fallback.all() and pr.is_cold_start.all()))
    v = validate_predictions(pr, universe_for(TEST, tgt), tgt)
    check(f"season:2021 {tgt}: validator accepts", v["ok"], str(v["problems"]))
check("season:2021 p_active uses the declared 0.800",
      bool((r21["predictions"]["p_active"].pred_point == 0.800).all()))

# team fold
tres = pipe.run_team_fold(T_TRAIN, T_TEST, "season:2099", config_hash=CFG)
TP, TD = tres["predictions"]["team_game_distribution"], tres["diagnostics"]
check("team fold not degenerate", not TD["degenerate"], TD.get("reason", ""))
check("team channel alphas selected for all four channels",
      set(TD["channel_alphas"]) == {"ft", "fg3", "paint", "np2"}, str(TD["channel_alphas"]))
check("T2 fitted the calibration map", TD["calibration_map_n"] > 0)
check("T3 supplied dispersion", TD["dispersion"]["n_resid"] > 0)
check("team every obligation emitted", len(TP) == len(T_TEST))
check("team pred_sd strictly positive", bool((TP.pred_sd > 0).all()))
check("team points respect the 1e-6 floor",
      bool((TP.pred_point >= gen.TEAM_POINTS_FLOOR).all()))
tv = validate_predictions(TP, universe_for(T_TEST, "team_game_distribution"),
                          "team_game_distribution")
check("team: REAL validate_predictions accepts", tv["ok"], str(tv["problems"]))

# --------------------------------------------------------------------------
# N1 -- calibration / outer-test outcomes cannot move anything selected
# --------------------------------------------------------------------------
ctx = gen.player_split(gen.order_obligations(TRAIN))
tr_sorted = gen.order_obligations(TRAIN)
poisoned = tr_sorted.copy()
for col in ("minutes", "fga", "points", "appeared"):
    poisoned.loc[ctx.calibration_idx, col] = 999.0
r_poison = pipe.run_player_fold(poisoned, TEST, "season:2099", config_hash=CFG)
DP = r_poison["diagnostics"]
check("N1 calibration outcomes cannot change the selected lambda",
      DP["selected"]["lambda"] == D["selected"]["lambda"])
check("N1 calibration outcomes cannot change the minutes alpha",
      DP["selected"]["minutes_alpha"] == D["selected"]["minutes_alpha"])
check("N1 calibration outcomes cannot change the attempts alpha",
      DP["selected"]["attempts_alpha"] == D["selected"]["attempts_alpha"])
check("N1 calibration outcomes cannot change the points alpha",
      DP["selected"]["points_alpha"] == D["selected"]["points_alpha"])
check("N1 calibration outcomes cannot change the base rate",
      DP["base_rate"] == D["base_rate"], f"{DP['base_rate']} vs {D['base_rate']}")
for tgt in D["fallback_mean"]:
    check(f"N1 calibration outcomes cannot change the {tgt} fallback mean",
          DP["fallback_mean"][tgt] == D["fallback_mean"][tgt])

test_poison = TEST.copy()
for col in ("minutes", "fga", "points", "appeared"):
    test_poison[col] = 999.0
D2 = pipe.run_player_fold(TRAIN, test_poison, "season:2099", config_hash=CFG)["diagnostics"]
check("N1 outer-test outcomes cannot change any selected parameter",
      D2["selected"] == D["selected"], f"{D2['selected']} vs {D['selected']}")
check("N1 outer-test outcomes cannot change the base rate", D2["base_rate"] == D["base_rate"])
check("N1 outer-test outcomes cannot change fallback means",
      D2["fallback_mean"] == D["fallback_mean"])

# --------------------------------------------------------------------------
# N2 -- a contaminated selection call is REJECTED, not silently served
# --------------------------------------------------------------------------
bad_mask = pd.Series(True, index=tr_sorted.index)          # includes calibration rows
try:
    gen.select_alpha_bound(lambda a: tr_sorted["minutes"], tr_sorted["minutes"],
                           ctx, bad_mask)
    check("N2 contaminated alpha selection is rejected", False, "no exception raised")
except SelectionLeakage:
    check("N2 contaminated alpha selection is rejected", True)

try:
    gen.prefix_mean(tr_sorted["minutes"], ctx, bad_mask)
    check("N2 contaminated prefix_mean is rejected", False, "no exception raised")
except SelectionLeakage:
    check("N2 contaminated prefix_mean is rejected", True)

try:
    ctx.require_tuning(ctx.calibration_idx[:1])
    check("N2 require_tuning rejects a calibration index", False, "no exception")
except SelectionLeakage:
    check("N2 require_tuning rejects a calibration index", True)

try:
    gen.SplitContext(np.array([1, 2, 3]), np.array([3, 4]))
    check("N2 overlapping SplitContext is rejected at construction", False, "no exception")
except SelectionLeakage:
    check("N2 overlapping SplitContext is rejected at construction", True)

# --------------------------------------------------------------------------
# N3 -- inactive rows drive p_active but never the conditional targets
# --------------------------------------------------------------------------
flip = tr_sorted.copy()
inactive = ~flip["appeared"].astype(bool)
flip.loc[inactive & flip.index.isin(ctx.tuning_idx), ["minutes", "fga", "points"]] = 777.0
D3 = pipe.run_player_fold(flip, TEST, "season:2099", config_hash=CFG)["diagnostics"]
check("N3 inactive-row outcomes cannot change the minutes alpha",
      D3["selected"]["minutes_alpha"] == D["selected"]["minutes_alpha"])
check("N3 inactive-row outcomes cannot change the attempts alpha",
      D3["selected"]["attempts_alpha"] == D["selected"]["attempts_alpha"])
check("N3 inactive-row outcomes cannot change conditional fallback means",
      D3["fallback_mean"] == D["fallback_mean"],
      f"{D3['fallback_mean']} vs {D['fallback_mean']}")

flip2 = tr_sorted.copy()
flip2.loc[flip2.index.isin(ctx.tuning_idx), "appeared"] = 1
D4 = pipe.run_player_fold(flip2, TEST, "season:2099", config_hash=CFG)["diagnostics"]
check("N3 inactive rows DO affect the p_active base rate",
      D4["base_rate"] != D["base_rate"], f"{D4['base_rate']} vs {D['base_rate']}")

# --------------------------------------------------------------------------
# N4 -- team segments respect games and dates
# --------------------------------------------------------------------------
ts = gen.team_split(T_TRAIN)
seg = {}
for name, idx in (("T1", ts.t1), ("T2", ts.t2), ("T3", ts.t3)):
    for i in idx:
        seg[i] = name
check("N4 every team row lands in exactly one segment", len(seg) == len(T_TRAIN),
      f"{len(seg)} vs {len(T_TRAIN)}")
by_game = T_TRAIN.assign(_s=[seg[i] for i in T_TRAIN.index]).groupby("game_id")["_s"].nunique()
check("N4 both rows of a game share one segment", bool((by_game == 1).all()),
      str(by_game[by_game > 1].head().to_dict()))
by_date = T_TRAIN.assign(_s=[seg[i] for i in T_TRAIN.index]).groupby("game_date")["_s"].nunique()
check("N4 every game on a date shares one segment", bool((by_date == 1).all()),
      str(by_date[by_date > 1].head().to_dict()))
check("N4 segments are chronologically ordered",
      max(ts.t1_dates) < min(ts.t2_dates) and max(ts.t2_dates) < min(ts.t3_dates))
check("N4 segments are pairwise disjoint",
      not (set(ts.t1) & set(ts.t2)) and not (set(ts.t2) & set(ts.t3))
      and not (set(ts.t1) & set(ts.t3)))
check("N4 rounding is the frozen floor rule",
      len(ts.t3_dates) == int(np.floor(48 * .25)) and len(ts.t2_dates) == int(np.floor(48 * .25))
      and len(ts.t1_dates) == 48 - 2 * int(np.floor(48 * .25)),
      f"{len(ts.t1_dates)}/{len(ts.t2_dates)}/{len(ts.t3_dates)}")
short = gen.team_split(team_frame(n_dates=10, seed=2))
check("N4 a short team window is degenerate, not silently split", short.degenerate)
check("N4 a degenerate team split yields empty T2 and T3",
      len(short.t2) == 0 and len(short.t3) == 0)

# --------------------------------------------------------------------------
# N5 -- zero-candidate and excluded obligations stay visible
# --------------------------------------------------------------------------
tz = T_TEST.copy()
tz.loc[tz.index[:4], "n_candidates"] = 0
rz = pipe.run_team_fold(T_TRAIN, tz, "season:2099", config_hash=CFG)
check("N5 zero-candidate team-games are counted, not dropped",
      rz["diagnostics"]["zero_candidate_team_games"] == 4,
      str(rz["diagnostics"]["zero_candidate_team_games"]))
check("N5 zero-candidate team-games still emit a row",
      len(rz["predictions"]["team_game_distribution"]) == len(tz))

excl = P["e_minutes_given_active"].copy()
excl.loc[excl.index[:5], "exclusion_reason"] = "synthetic_exclusion"
excl.loc[excl.index[:5], ["pred_point", "pred_sd"]] = np.nan
ct = gen.exclusion_crosstab(excl, universe_for(TEST, "e_minutes_given_active"))
check("N5 exclusion cross-tab counts exclusions", ct["n_excluded"] == 5, str(ct))
check("N5 exclusion cross-tab reports the appeared rate",
      "excluded_appeared_rate" in ct, str(ct))
v_excl = validate_predictions(excl, universe_for(TEST, "e_minutes_given_active"),
                              "e_minutes_given_active")
check("N5 excluded rows still satisfy the obligation (no missing row_uid)",
      not any("REQUIRED rows" in p for p in v_excl["problems"]), str(v_excl["problems"]))

alarm = P["e_minutes_given_active"].copy()
# Select by row_uid, NOT by index label: emit_rows returns a fresh RangeIndex in
# obligation order, so TEST's labels do not address the same rows.
never_uids = TEST.loc[~TEST["appeared"].astype(bool), "row_uid"].tolist()[:6]
alarm.loc[alarm.row_uid.isin(never_uids), "exclusion_reason"] = "outcome_selected"
ct2 = gen.exclusion_crosstab(alarm, universe_for(TEST, "e_minutes_given_active"))
check("N5 exclusion that perfectly predicts non-appearance raises the alarm",
      ct2["outcome_selection_alarm"] is True, str(ct2))

# --------------------------------------------------------------------------
# N6 -- degenerate residual pools fail closed
# --------------------------------------------------------------------------
sd, off, m = gen.dispersion(np.full(400, 5.0), min_resid=10)
check("N6 a CONSTANT residual pool is insufficient, not sd=0", m == "insufficient",
      f"method={m} sd={sd}")
check("N6 an empty pool is insufficient",
      gen.dispersion(np.array([]), min_resid=10)[2] == "insufficient")
check("N6 a single residual is insufficient",
      gen.dispersion(np.array([1.0]), min_resid=10)[2] == "insufficient")
check("N6 an all-NaN pool is insufficient",
      gen.dispersion(np.full(50, np.nan), min_resid=10)[2] == "insufficient")
check("N6 a healthy pool is usable",
      gen.dispersion(np.random.default_rng(1).normal(0, 2, 400), min_resid=10)[2]
      == "empirical")

const_train = tr_sorted.copy()
const_train["minutes"] = 20.0
rc = pipe.run_player_fold(const_train, TEST, "season:2099", config_hash=CFG)
check("N6 a constant-outcome fold still emits strictly positive sd",
      bool((rc["predictions"]["e_minutes_given_active"].pred_sd > 0).all()))
vc = validate_predictions(rc["predictions"]["e_minutes_given_active"],
                          universe_for(TEST, "e_minutes_given_active"),
                          "e_minutes_given_active")
check("N6 the constant-pool fold still validates", vc["ok"], str(vc["problems"]))

# --------------------------------------------------------------------------
# N7 -- duplicate / tied obligations fail closed
# --------------------------------------------------------------------------
dup = pd.concat([TRAIN, TRAIN.iloc[[0]]], ignore_index=True)
try:
    gen.order_obligations(dup)
    check("N7 duplicate obligations fail closed", False, "no exception raised")
except gen.ObligationOrderError:
    check("N7 duplicate obligations fail closed", True)

try:
    pipe.run_player_fold(dup, TEST, "season:2099", config_hash=CFG)
    check("N7 the pipeline refuses duplicated obligations", False, "no exception")
except gen.ObligationOrderError:
    check("N7 the pipeline refuses duplicated obligations", True)

try:
    gen.order_obligations(TRAIN.drop(columns=["game_id"]))
    check("N7 a missing ordering key fails closed", False, "no exception")
except gen.ObligationOrderError:
    check("N7 a missing ordering key fails closed", True)

check("N7 ordering is deterministic under row shuffling",
      gen.order_obligations(TRAIN.sample(frac=1, random_state=4))
      .row_uid.tolist() == gen.order_obligations(TRAIN).row_uid.tolist())

# --------------------------------------------------------------------------
# N8 -- validation / provenance / coverage gate any scoring path
# --------------------------------------------------------------------------
broken = P["e_minutes_given_active"].copy()
broken = broken.iloc[5:]
vb = validate_predictions(broken, universe_for(TEST, "e_minutes_given_active"),
                          "e_minutes_given_active")
check("N8 missing obligation rows are rejected", not vb["ok"]
      and any("REQUIRED rows" in p for p in vb["problems"]), str(vb["problems"]))

leaky = P["e_minutes_given_active"].copy()
leaky["feature_asof"] = leaky["forecast_cutoff"]
vl = validate_predictions(leaky, universe_for(TEST, "e_minutes_given_active"),
                          "e_minutes_given_active")
check("N8 feature_asof == forecast_cutoff is rejected as leakage", not vl["ok"]
      and any("leakage" in p for p in vl["problems"]), str(vl["problems"]))

nosd = P["attempts_usage"].copy()
nosd["pred_sd"] = 0.0
vs = validate_predictions(nosd, universe_for(TEST, "attempts_usage"), "attempts_usage")
check("N8 pred_sd == 0 is rejected", not vs["ok"], str(vs["problems"]))

noprov = P["attempts_usage"].copy()
noprov["model_hash"] = np.nan
vp = validate_predictions(noprov, universe_for(TEST, "attempts_usage"), "attempts_usage")
check("N8 missing provenance is rejected", not vp["ok"], str(vp["problems"]))

nonmono = P["player_scoring_distribution"].copy()
nonmono["pred_q05"] = nonmono["pred_q95"] + 1.0
vm = validate_predictions(nonmono, universe_for(TEST, "player_scoring_distribution"),
                          "player_scoring_distribution")
check("N8 non-monotone quantiles are rejected", not vm["ok"], str(vm["problems"]))

print(f"{PASSED}/{PASSED + len(FAILED)} tests passed")
for f in FAILED:
    print(f"  FAIL  {f}")
sys.exit(1 if FAILED else 0)
