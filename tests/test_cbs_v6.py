#!/usr/bin/env python
"""test_cbs_v6.py — runner-level synthetic suite for `contract_baseline_suite_v6`.

**Synthetic only.** No contract parquet is read, no historical OOF is produced,
no accuracy or coverage figure is computed or inspected.

v5's corrections never reached a generated contract row: there was no v5 runner.
These tests drive the v6 runners end to end and prove the corrections survive
into emitted output.

  R1  all five targets emit every required obligation, and the composite gate
      (historical AND strict) accepts them
  R2  full train/test shuffle invariance, player and team
  R3  causal as-of: changing a row cannot change itself or any earlier
      prediction (it may change later history)
  R4  calibration / T3 and outer-test isolation
  R5  separate side maps; missing / null / non-finite channel or side, duplicate
      rows and malformed game structure all fail closed
  R6  conditional fallback emission and target-specific cold starts
  R7  zero-candidate visibility and exact row coverage
  R8  history-sidecar completeness
  R9  every fitted-state component changes the emitted model_hash
  R10 strict rejection of wrong/missing identity, absent universe columns,
      infinities, fake-null SD, numeric flags and malformed excluded rows
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import cbs_v5 as v5  # noqa: E402
import cbs_v6 as v6  # noqa: E402
from contract_validator_v2_strict import validate_arm_output, validate_strict  # noqa: E402

PASSED = 0
FAILED: list[str] = []
CFG, SNAP = "a" * 64, "b" * 64


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASSED
    if cond:
        PASSED += 1
    else:
        FAILED.append(f"{name}: {detail}")


def pframe(n_players=8, n_dates=48, seed=3, start="2099-05-01", season=2099):
    rng = np.random.default_rng(seed)
    dates = pd.date_range(start, periods=n_dates, freq="D")
    rows = []
    for gi, d in enumerate(dates):
        for pid in range(n_players):
            ap = int(rng.random() < 0.55 + 0.04 * pid)
            mn = float(rng.uniform(9, 33)) if ap else 0.0
            rows.append({
                "row_uid": f"pg_{season}_{gi:04d}_{pid}", "player_id": f"P{pid}",
                "season": season, "game_id": f"G{season}{gi:04d}", "game_date": d,
                "forecast_cutoff": (d - pd.Timedelta(hours=6)).tz_localize("UTC").isoformat(),
                "feature_asof": (d - pd.Timedelta(hours=12)).tz_localize("UTC").isoformat(),
                "appeared": ap, "minutes": mn,
                "fga": float(rng.poisson(max(mn, .1) * .35)) if ap else 0.0,
                "points": float(rng.poisson(max(mn, .1) * .45)) if ap else 0.0,
            })
    return pd.DataFrame(rows).reset_index(drop=True)


def tframe(n_pairs=3, n_dates=48, seed=5, start="2099-05-01", season=2099):
    rng = np.random.default_rng(seed)
    dates = pd.date_range(start, periods=n_dates, freq="D")
    rows = []
    for gi, d in enumerate(dates):
        for pair in range(n_pairs):
            gid = f"TG{season}{gi:04d}_{pair}"
            for side in v5.REQUIRED_SIDES:
                rows.append({
                    "row_uid": f"tg_{season}_{gi:04d}_{pair}_{side}",
                    "team_id": f"T{pair}_{side}", "game_id": gid, "season": season,
                    "game_date": d, "side": side,
                    "forecast_cutoff": (d - pd.Timedelta(hours=6)).tz_localize("UTC").isoformat(),
                    "feature_asof": (d - pd.Timedelta(hours=12)).tz_localize("UTC").isoformat(),
                    "ch_ft": float(rng.uniform(10, 20)), "ch_3pt": float(rng.uniform(15, 30)),
                    "ch_paint": float(rng.uniform(25, 40)), "ch_np2": float(rng.uniform(8, 18)),
                    "team_points": float(rng.uniform(68, 96)) + (4.0 if side == "home" else 0),
                    "n_candidates": 12,
                })
    return pd.DataFrame(rows).reset_index(drop=True)


def universe_for(df, targets, fold_id):
    u = pd.DataFrame({"row_uid": df["row_uid"].to_numpy(),
                      "fold_id": fold_id,
                      "forecast_cutoff": df["forecast_cutoff"].to_numpy()})
    for t in targets:
        u[f"prediction_required__{t}"] = True
        u[f"outcome_scoreable__{t}"] = (df["appeared"].astype(bool).to_numpy()
                                        if ("appeared" in df.columns and t != "p_active")
                                        else True)
    return u


FOLD = "season:2099"
TRAIN, TEST = pframe(), pframe(seed=9, start="2099-08-01", n_dates=14)
T_TRAIN, T_TEST = tframe(), tframe(seed=11, start="2099-08-01", n_dates=10)
PUNI = universe_for(TEST, v6.PLAYER_TARGETS, FOLD)
TUNI = universe_for(T_TEST, ["team_game_distribution"], FOLD)

res = v6.run_player_fold(TRAIN, TEST, FOLD, config_hash=CFG, snapshot_hash=SNAP,
                         universe=PUNI)
tres = v6.run_team_fold(T_TRAIN, T_TEST, FOLD, config_hash=CFG, snapshot_hash=SNAP,
                        universe=TUNI)
P, TP = res["predictions"], tres["predictions"]["team_game_distribution"]

# --------------------------------------------------------------------------
# R1 -- five targets, full coverage, composite gate
# --------------------------------------------------------------------------
check("R1 all four player targets emitted", set(P) == set(v6.PLAYER_TARGETS), str(set(P)))
check("R1 team target emitted", TP is not None)
for tgt, p in P.items():
    check(f"R1 {tgt}: every obligation row emitted", len(p) == len(TEST))
    check(f"R1 {tgt}: composite gate accepts", res["validation_receipts"][tgt]["ok"],
          str(res["validation_receipts"][tgt]["problems"]))
check("R1 team: composite gate accepts",
      tres["validation_receipts"]["team_game_distribution"]["ok"],
      str(tres["validation_receipts"]["team_game_distribution"]["problems"]))
check("R1 player run reports validated", res["validated"])
check("R1 team run reports validated", tres["validated"])
check("R1 scoring is gated on validation", res["scoring_permitted"] is True)
check("R1 the composite receipt names both validators",
      "historical" in res["validation_receipts"]["p_active"]
      and "strict" in res["validation_receipts"]["p_active"])
check("R1 arm identity is v6 everywhere",
      all((p.arm_id == v6.ARM_ID).all() for p in P.values()))

# --------------------------------------------------------------------------
# R2 -- shuffle invariance, player and team
# --------------------------------------------------------------------------
res_s = v6.run_player_fold(TRAIN.sample(frac=1, random_state=1),
                           TEST.sample(frac=1, random_state=2), FOLD,
                           config_hash=CFG, snapshot_hash=SNAP, universe=PUNI)
for tgt in v6.PLAYER_TARGETS:
    a = P[tgt].set_index("row_uid").pred_point
    b = res_s["predictions"][tgt].set_index("row_uid").pred_point.reindex(a.index)
    check(f"R2 {tgt} is train/test shuffle invariant",
          np.allclose(a.to_numpy(float), b.to_numpy(float), equal_nan=True),
          f"max delta {np.nanmax(np.abs(a - b)):.6f}")
    check(f"R2 {tgt} model_hash is shuffle invariant",
          P[tgt].model_hash.iloc[0] == res_s["predictions"][tgt].model_hash.iloc[0])
tres_s = v6.run_team_fold(T_TRAIN.sample(frac=1, random_state=3),
                          T_TEST.sample(frac=1, random_state=4), FOLD,
                          config_hash=CFG, snapshot_hash=SNAP, universe=TUNI)
a = TP.set_index("row_uid").pred_point
b = tres_s["predictions"]["team_game_distribution"].set_index("row_uid").pred_point.reindex(a.index)
check("R2 team predictions are shuffle invariant",
      np.allclose(a.to_numpy(float), b.to_numpy(float), equal_nan=True),
      f"max delta {np.nanmax(np.abs(a - b)):.6f}")
check("R2 team model_hash is shuffle invariant",
      TP.model_hash.iloc[0] == tres_s["predictions"]["team_game_distribution"].model_hash.iloc[0])

# --------------------------------------------------------------------------
# R3 -- causal as-of on the test frame
# --------------------------------------------------------------------------
ordered = TEST.sort_values(list(v5.PLAYER_SORT_KEYS), kind="mergesort")
target_uid = ordered.iloc[len(ordered) // 2]["row_uid"]
bumped = TEST.copy()
sel = bumped.row_uid == target_uid
bumped.loc[sel, ["minutes", "fga", "points"]] = 999.0
res_b = v6.run_player_fold(TRAIN, bumped, FOLD, config_hash=CFG, snapshot_hash=SNAP,
                           universe=PUNI)
pid = TEST.loc[sel, "player_id"].iloc[0]
cut = TEST.loc[sel, "forecast_cutoff"].iloc[0]
earlier = TEST[(TEST.player_id == pid) & (TEST.forecast_cutoff < cut)].row_uid
for tgt in ("e_minutes_given_active", "attempts_usage"):
    a = P[tgt].set_index("row_uid").pred_point
    b = res_b["predictions"][tgt].set_index("row_uid").pred_point
    check(f"R3 {tgt}: a row's own outcome cannot change its own prediction",
          np.isclose(a.loc[target_uid], b.loc[target_uid], equal_nan=True),
          f"{a.loc[target_uid]} -> {b.loc[target_uid]}")
    if len(earlier):
        check(f"R3 {tgt}: no EARLIER prediction changed",
              np.allclose(a.loc[earlier].to_numpy(float),
                          b.loc[earlier].to_numpy(float), equal_nan=True))
check("R3 other players are unaffected",
      np.allclose(
          P["e_minutes_given_active"].set_index("row_uid").pred_point
          .loc[TEST[TEST.player_id != pid].row_uid].to_numpy(float),
          res_b["predictions"]["e_minutes_given_active"].set_index("row_uid").pred_point
          .loc[TEST[TEST.player_id != pid].row_uid].to_numpy(float), equal_nan=True))

# --------------------------------------------------------------------------
# R4 -- calibration/T3 and outer-test isolation
# --------------------------------------------------------------------------
from cbs_generator import player_split  # noqa: E402
tr_ord = v6.order_obligations(TRAIN)
ctx = player_split(tr_ord)
poison = tr_ord.copy()
poison.loc[ctx.calibration_idx, ["minutes", "fga", "points", "appeared"]] = 999.0
d_p = v6.run_player_fold(poison, TEST, FOLD, config_hash=CFG, snapshot_hash=SNAP,
                         universe=PUNI)["diagnostics"]
check("R4 calibration outcomes cannot change selected params",
      d_p["selected"] == res["diagnostics"]["selected"],
      f"{d_p['selected']} vs {res['diagnostics']['selected']}")
check("R4 calibration outcomes cannot change the base rate",
      d_p["base_rate"] == res["diagnostics"]["base_rate"])
check("R4 calibration outcomes cannot change fallback means",
      d_p["fallback_mean"] == res["diagnostics"]["fallback_mean"])

t_poison = T_TRAIN.copy()
ts = v5.team_split(T_TRAIN)
t_poison.loc[ts.t3, "team_points"] = 5000.0
td = v6.run_team_fold(t_poison, T_TEST, FOLD, config_hash=CFG, snapshot_hash=SNAP,
                      universe=TUNI)["diagnostics"]
check("R4 T3 outcomes cannot change the channel alphas",
      td["channel_alphas"] == tres["diagnostics"]["channel_alphas"])
check("R4 T3 outcomes cannot change the calibration maps",
      td["calibration_maps"] == tres["diagnostics"]["calibration_maps"])

test_poison = TEST.copy()
test_poison[["minutes", "fga", "points", "appeared"]] = 999.0
d_t = v6.run_player_fold(TRAIN, test_poison, FOLD, config_hash=CFG, snapshot_hash=SNAP,
                         universe=PUNI)["diagnostics"]
check("R4 outer-test outcomes cannot change any selected parameter",
      d_t["selected"] == res["diagnostics"]["selected"])

# --------------------------------------------------------------------------
# R5 -- structural preconditions fail closed
# --------------------------------------------------------------------------
v6.require_team_inputs_strict(T_TRAIN)
check("R5 a well-formed team frame is accepted", True)
bad_cases = {
    "missing channel": T_TRAIN.drop(columns=["ch_3pt"]),
    "missing side": T_TRAIN.drop(columns=["side"]),
    "null side": T_TRAIN.assign(side=T_TRAIN["side"].mask(T_TRAIN.index == 0)),
    "null channel": T_TRAIN.assign(ch_ft=T_TRAIN["ch_ft"].mask(T_TRAIN.index == 0)),
    "non-finite channel": T_TRAIN.assign(
        ch_ft=T_TRAIN["ch_ft"].mask(T_TRAIN.index == 0, np.inf)),
    "unexpected side value": T_TRAIN.assign(
        side=T_TRAIN["side"].mask(T_TRAIN.index == 0, "neutral")),
    "duplicate team-game row": pd.concat([T_TRAIN, T_TRAIN.iloc[[0]]], ignore_index=True),
    "game with two home rows": T_TRAIN.assign(side="home"),
}
for label, frame in bad_cases.items():
    try:
        v6.require_team_inputs_strict(frame)
        check(f"R5 {label} fails closed", False, "no exception raised")
    except v5.MissingRequiredInput:
        check(f"R5 {label} fails closed", True)

maps = tres["diagnostics"]["calibration_maps"]
check("R5 separate home and away maps are fitted",
      set(maps) == set(v5.REQUIRED_SIDES) and maps["home"] != maps["away"], str(maps))

# --------------------------------------------------------------------------
# R6 -- conditional fallback and target-specific cold starts
# --------------------------------------------------------------------------
never_test = TEST.copy()
never_test["appeared"] = 0
r_nev = v6.run_player_fold(TRAIN, never_test, FOLD, config_hash=CFG, snapshot_hash=SNAP,
                           universe=universe_for(never_test, v6.PLAYER_TARGETS, FOLD))
pa = r_nev["predictions"]["p_active"]
em = r_nev["predictions"]["e_minutes_given_active"]
check("R6 zero-appearance rows are conditionally COLD",
      bool(em.is_cold_start.all()), "conditional history is the active subsequence")
check("R6 zero-appearance rows are conditionally FALLBACK", bool(em.is_fallback.all()))
check("R6 the same rows are NOT all cold for p_active",
      not bool(pa.is_cold_start.all()),
      "0-of-k is evidence for p_active, absence for the conditional targets")
check("R6 conditional fallback rows still carry finite predictions",
      bool(np.isfinite(em.pred_point).all()))
check("R6 conditional fallback rows still carry positive sd", bool((em.pred_sd > 0).all()))
check("R6 team season openers carry prior_games zero",
      int(TP.n_prior_games.min()) == 0)
check("R6 team openers are flagged cold",
      bool(TP.loc[TP.n_prior_games == 0, "is_cold_start"].all()))

# --------------------------------------------------------------------------
# R7 -- zero-candidate visibility and exact coverage
# --------------------------------------------------------------------------
tz = T_TEST.copy()
tz.loc[tz.index[:4], "n_candidates"] = 0
rz = v6.run_team_fold(T_TRAIN, tz, FOLD, config_hash=CFG, snapshot_hash=SNAP,
                      universe=universe_for(tz, ["team_game_distribution"], FOLD))
check("R7 zero-candidate team-games are counted",
      rz["diagnostics"]["zero_candidate_team_games"] == 4)
check("R7 zero-candidate team-games still emit rows",
      len(rz["predictions"]["team_game_distribution"]) == len(tz))
for tgt, p in P.items():
    check(f"R7 {tgt} coverage is exactly the obligation set",
          set(p.row_uid) == set(TEST.row_uid))
    check(f"R7 {tgt} coverage receipt is 1.0",
          res["validation_receipts"][tgt]["prediction_coverage"] == 1.0)
check("R7 coverage counts are reported per target", set(res["coverage"]) == set(P))

# --------------------------------------------------------------------------
# R8 -- history sidecar
# --------------------------------------------------------------------------
sc = res["history_sidecar"]
check("R8 sidecar is versioned", (sc["schema"] == v6.HISTORY_SIDECAR_SCHEMA).all())
check("R8 sidecar covers every row", set(sc.row_uid) == set(TEST.row_uid))
check("R8 sidecar records candidate obligations AND appearances separately",
      {"n_prior_candidate_games", "n_prior_appearances"} <= set(sc.columns))
check("R8 appearances never exceed obligations",
      bool((sc.n_prior_appearances <= sc.n_prior_candidate_games).all()))
check("R8 contract n_prior_games equals prior APPEARANCES",
      list(P["p_active"].set_index("row_uid").n_prior_games.loc[sc.row_uid])
      == list(sc.n_prior_appearances))
tsc = tres["history_sidecar"]
check("R8 team sidecar records prior games", "team_prior_games" in tsc.columns)
check("R8 team sidecar covers every row", set(tsc.row_uid) == set(T_TEST.row_uid))

# --------------------------------------------------------------------------
# R9 -- every fitted-state component moves the model hash
# --------------------------------------------------------------------------
st = v6.FittedState(target="e_minutes_given_active", fold_id=FOLD,
                    feature_order=list(v5.P_ACTIVE_FEATURES),
                    scaler_mean=[1.0, 2.0], scaler_std=[1.0, 1.0],
                    dropped_features=[], lam=1.0, beta=[0.1, 0.2],
                    alphas={"minutes": 0.1}, calibration_maps={"home": [1.0, 2.0]},
                    base_rate=0.5, fallback_mean=20.0, dispersion_sd=3.0,
                    dispersion_method="empirical", dispersion_offsets=[-1, 0, 1],
                    support={"low": 0.0, "high": 48.0})
h0 = st.hash()
check("R9 the fitted-state hash is 64 hex", len(h0) == 64)
import dataclasses  # noqa: E402
for fld, newval in (("feature_order", list(reversed(v5.P_ACTIVE_FEATURES))),
                    ("scaler_mean", [1.0, 2.5]), ("scaler_std", [1.0, 2.0]),
                    ("dropped_features", ["min_ewma"]), ("lam", 2.0),
                    ("beta", [0.1, 0.3]), ("alphas", {"minutes": 0.2}),
                    ("calibration_maps", {"home": [1.0, 2.5]}), ("base_rate", 0.6),
                    ("fallback_mean", 21.0), ("dispersion_sd", 3.5),
                    ("dispersion_method", "gaussian"),
                    ("dispersion_offsets", [-2, 0, 2]),
                    ("support", {"low": 0.0, "high": 40.0}),
                    ("target", "attempts_usage"), ("fold_id", "season:2100")):
    check(f"R9 model_hash changes when {fld} changes",
          dataclasses.replace(st, **{fld: newval}).hash() != h0, fld)
check("R9 different targets in the real run carry different hashes",
      len({p.model_hash.iloc[0] for p in P.values()}) == len(P))

# --------------------------------------------------------------------------
# R10 -- strict rejection
# --------------------------------------------------------------------------
good = P["attempts_usage"]
kw = dict(expected_arm_id=v6.ARM_ID, expected_fold_id=FOLD,
          expected_config_hash=CFG, expected_snapshot_hash=SNAP)
check("R10 the real emitted frame passes strict",
      validate_strict(good, PUNI, "attempts_usage", **kw)["ok"],
      str(validate_strict(good, PUNI, "attempts_usage", **kw)["problems"]))
check("R10 missing expected identity is rejected",
      not validate_strict(good, PUNI, "attempts_usage",
                          expected_arm_id=v6.ARM_ID, expected_fold_id=FOLD,
                          expected_config_hash=CFG)["ok"],
      "identity binding must be mandatory")
check("R10 a universe without fold_id is rejected",
      not validate_strict(good, PUNI.drop(columns=["fold_id"]),
                          "attempts_usage", **kw)["ok"])
check("R10 +inf pred_point is rejected",
      not validate_strict(good.assign(pred_point=np.inf), PUNI, "attempts_usage", **kw)["ok"])
check("R10 +inf quantile is rejected",
      not validate_strict(good.assign(pred_q95=np.inf), PUNI, "attempts_usage", **kw)["ok"])
check("R10 numeric 0/1 flags are rejected",
      not validate_strict(good.assign(is_fallback=0), PUNI, "attempts_usage", **kw)["ok"])
check("R10 float flags are rejected",
      not validate_strict(good.assign(is_cold_start=0.0), PUNI, "attempts_usage", **kw)["ok"])
check("R10 wrong arm_id is rejected",
      not validate_strict(good.assign(arm_id="other"), PUNI, "attempts_usage", **kw)["ok"])
check("R10 wrong snapshot hash is rejected",
      not validate_strict(good, PUNI, "attempts_usage",
                          expected_arm_id=v6.ARM_ID, expected_fold_id=FOLD,
                          expected_config_hash=CFG,
                          expected_snapshot_hash="c" * 64)["ok"])
pa_fake = P["p_active"].copy()
pa_fake["pred_sd"] = "not-a-number"
check("R10 non-numeric p_active pred_sd is rejected (not coerced to null)",
      not validate_strict(pa_fake, PUNI, "p_active",
                          expected_arm_id=v6.ARM_ID, expected_fold_id=FOLD,
                          expected_config_hash=CFG, expected_snapshot_hash=SNAP)["ok"])
mal = good.copy()
mal.loc[mal.index[:3], "exclusion_reason"] = "why"      # values left in place
check("R10 an excluded row that keeps its values is rejected",
      not validate_strict(mal, PUNI, "attempts_usage", **kw)["ok"])
mal2 = good.copy()
mal2.loc[mal2.index[:3], "exclusion_reason"] = "why"
mal2.loc[mal2.index[:3], ["pred_point", "pred_sd", "pred_q05", "pred_q25",
                          "pred_q50", "pred_q75", "pred_q95"]] = np.nan
check("R10 a properly nulled excluded row is accepted",
      validate_strict(mal2, PUNI, "attempts_usage", **kw)["ok"],
      str(validate_strict(mal2, PUNI, "attempts_usage", **kw)["problems"]))
mal3 = mal2.copy()
mal3.loc[mal3.index[:3], "model_hash"] = np.nan
check("R10 an excluded row that loses its lineage is rejected",
      not validate_strict(mal3, PUNI, "attempts_usage", **kw)["ok"])
check("R10 a malformed frame returns a verdict rather than raising",
      validate_strict(pd.DataFrame({"row_uid": [1]}), PUNI, "attempts_usage", **kw)["ok"]
      is False)
check("R10 the composite gate fails closed on a malformed frame",
      validate_arm_output(pd.DataFrame({"row_uid": [1]}), PUNI, "attempts_usage",
                          expected_arm_id=v6.ARM_ID, expected_fold_id=FOLD,
                          expected_config_hash=CFG,
                          expected_snapshot_hash=SNAP)["ok"] is False)

# real-boundary identity
try:
    v6.run_player_fold(TRAIN, TEST, FOLD, config_hash="nope", snapshot_hash=SNAP,
                       universe=PUNI, synthetic=False)
    check("R10 a real run rejects a placeholder config hash", False, "no exception")
except v5.AdapterBoundaryError:
    check("R10 a real run rejects a placeholder config hash", True)

print(f"{PASSED}/{PASSED + len(FAILED)} tests passed")
for f in FAILED:
    print(f"  FAIL  {f}")
sys.exit(1 if FAILED else 0)
