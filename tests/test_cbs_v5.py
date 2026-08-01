#!/usr/bin/env python
"""test_cbs_v5.py — corrected-implementation and strict-validator suite for v5.

**Synthetic data only.** No contract parquet is read, no historical OOF is
produced, no accuracy or coverage figure is computed or inspected.

Every test below corresponds to a defect that was found in the v4
implementation and confirmed by direct reproduction, or to a check the
historical v2 validator does not perform.

  V1  λ inner split is date-disjoint (v4 split by PLAYER: fit P0-P5, val P6-P7,
      all 36 dates on both sides)
  V2  team train/test row-shuffle invariance (v4 moved predictions by ~6 pts)
  V3  no future team row can affect an earlier feature
  V4  season boundary / carry behaviour is frozen and tested
  V5  separate home/away T2 maps; missing channel or side fails closed
  V6  asymmetric quantile DIRECTION (v4 inverted the residual sign)
  V7  target-specific cold starts
  V8  the model hash responds to every fitted parameter
  V9  missing Stage-A features fail closed; feature_asof is derived, not trusted
  V10 the strict validator rejects wrong fold, cutoff, target, support, hashes —
      cases the historical validator accepts
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import cbs_v5 as v5  # noqa: E402
from cbs_generator import SplitContext, player_split  # noqa: E402
from contract_validator_v2_strict import validate_strict  # noqa: E402
from prediction_contract_v2 import validate_predictions  # noqa: E402

PASSED = 0
FAILED: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASSED
    if cond:
        PASSED += 1
    else:
        FAILED.append(f"{name}: {detail}")


def player_frame(n_players=8, n_dates=48, seed=3, start="2099-05-01", season=2099):
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
                "src_ts": (d - pd.Timedelta(hours=12)).tz_localize("UTC").isoformat(),
                "appeared": ap, "minutes": mn,
                "fga": float(rng.poisson(max(mn, .1) * .35)) if ap else 0.0,
                "points": float(rng.poisson(max(mn, .1) * .45)) if ap else 0.0,
            })
    return pd.DataFrame(rows).reset_index(drop=True)


def team_frame(n_pairs=3, n_dates=48, seed=5, start="2099-05-01", season=2099):
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
                    "team_points": float(rng.uniform(68, 96)) + (4.0 if side == "home" else 0.0),
                })
    return pd.DataFrame(rows).reset_index(drop=True)


TRAIN = player_frame()
T_TRAIN = team_frame()

# --------------------------------------------------------------------------
# V1 -- lambda inner split is DATE-disjoint
# --------------------------------------------------------------------------
tr = TRAIN.sort_values(list(v5.PLAYER_SORT_KEYS), kind="mergesort")
ctx = player_split(tr)
inner = v5.chronological_inner_split(tr, ctx)
check("V1 inner split is not degenerate", not inner.degenerate, inner.reason)
fd, vd = set(inner.fit_dates), set(inner.val_dates)
check("V1 fit and validation dates are DISJOINT", not (fd & vd),
      f"{len(fd & vd)} shared dates")
check("V1 validation is strictly LATER than fit", min(vd) > max(fd))
check("V1 every tuning row lands on exactly one side",
      len(inner.fit_idx) + len(inner.val_idx) == len(ctx.tuning_idx))
check("V1 no row appears on both sides",
      len(np.intersect1d(inner.fit_idx, inner.val_idx)) == 0)
check("V1 both sides contain ALL players (the v4 bug split by player)",
      set(tr.loc[inner.fit_idx, "player_id"]) == set(tr.loc[inner.val_idx, "player_id"]),
      f"fit={sorted(set(tr.loc[inner.fit_idx,'player_id']))} "
      f"val={sorted(set(tr.loc[inner.val_idx,'player_id']))}")
check("V1 rounding is the frozen floor rule",
      len(vd) == int(np.floor(len(fd | vd) * v5.LAMBDA_INNER_TAIL_FRACTION)),
      f"{len(vd)} of {len(fd | vd)}")
# A genuinely short segment means few DISTINCT DATES, not few rows: the frame is
# ordered by player, so the first 20 rows span 20 dates of one player.
few_dates = sorted(pd.unique(tr["game_date"]))[:4]
short_rows = np.asarray(tr.index[tr["game_date"].isin(few_dates)])
rest = np.asarray(tr.index[~tr["game_date"].isin(few_dates)])
short_ctx = SplitContext(short_rows, rest)
short_inner = v5.chronological_inner_split(tr, short_ctx)
check("V1 a short tuning segment is degenerate, not silently split",
      short_inner.degenerate, short_inner.reason)
check("V1 a degenerate inner split yields NO validation rows",
      len(short_inner.val_idx) == 0)

hist = v5.player_history_accounting(tr)
X = v5.stage_a_features_strict(tr, hist, 0.5, allow_declared_defaults=True)
lam, used_default, inner2 = v5.select_lambda_chronological(
    X, tr["appeared"].astype(float), ctx, tr)
check("V1 lambda comes from the frozen grid", lam in v5.LAMBDA_GRID, str(lam))
check("V1 lambda selection used a date-disjoint inner split",
      not set(inner2.fit_dates) & set(inner2.val_dates))

# --------------------------------------------------------------------------
# V2/V3/V4 -- team ordering, shuffle invariance, no future leakage
# --------------------------------------------------------------------------
alphas = {c: 0.10 for c in v5.REQUIRED_CHANNELS}
base = v5.team_structural(T_TRAIN, alphas)
shuf = T_TRAIN.sample(frac=1, random_state=17)
shuf_struct = v5.team_structural(shuf, alphas)
check("V2 team structural trend is row-shuffle invariant",
      np.allclose(base.to_numpy(dtype=float),
                  shuf_struct.reindex(T_TRAIN.index).to_numpy(dtype=float),
                  equal_nan=True),
      "shuffling the input changed the team features")

pg = v5.team_prior_games(T_TRAIN)
pg_shuf = v5.team_prior_games(shuf).reindex(T_TRAIN.index)
check("V2 team prior-game counts are shuffle invariant", bool((pg == pg_shuf).all()))

ordered = v5.order_team_rows(T_TRAIN)
last = ordered.index[-1]
bumped = T_TRAIN.copy()
bumped.loc[last, "ch_ft"] = bumped.loc[last, "ch_ft"] + 5000.0
after = v5.team_structural(bumped, alphas)
check("V3 changing the LAST team row cannot change any earlier feature",
      np.allclose(base.drop(index=last).to_numpy(dtype=float),
                  after.drop(index=last).to_numpy(dtype=float), equal_nan=True))
check("V3 a team row cannot change its own feature",
      (pd.isna(base.loc[last]) and pd.isna(after.loc[last]))
      or base.loc[last] == after.loc[last])

first_per_team = ordered.groupby(list(v5.TEAM_HISTORY_GROUP), sort=False).head(1).index
check("V4 the first game of a team-season has no history",
      bool(base.reindex(first_per_team).isna().all()))
check("V4 prior_games restarts at 0 each team-season",
      bool((pg.reindex(first_per_team) == 0).all()))

two_seasons = pd.concat([team_frame(season=2099, start="2099-05-01", n_dates=20),
                         team_frame(season=2100, start="2100-05-01", n_dates=20, seed=8)],
                        ignore_index=True)
s2 = v5.team_structural(two_seasons, alphas)
o2 = v5.order_team_rows(two_seasons)
opener_2100 = o2[(o2.season == 2100)].groupby("team_id", sort=False).head(1).index
check("V4 history does NOT carry across the season boundary",
      bool(s2.reindex(opener_2100).isna().all()),
      "a 2100 opener inherited 2099 history")

# --------------------------------------------------------------------------
# V5 -- separate side maps; missing channel/side fails closed
# --------------------------------------------------------------------------
v5.require_team_inputs(T_TRAIN)
check("V5 a complete team frame is accepted", True)
for drop, label in ((["ch_3pt"], "channel"), (["side"], "side indicator")):
    try:
        v5.require_team_inputs(T_TRAIN.drop(columns=drop))
        check(f"V5 a missing {label} fails closed", False, "no exception raised")
    except v5.MissingRequiredInput:
        check(f"V5 a missing {label} fails closed", True)
try:
    bad_side = T_TRAIN.copy()
    bad_side.loc[bad_side.index[0], "side"] = "neutral"
    v5.require_team_inputs(bad_side)
    check("V5 an unexpected side value fails closed", False, "no exception")
except v5.MissingRequiredInput:
    check("V5 an unexpected side value fails closed", True)

ts = v5.team_split(T_TRAIN)
maps = v5.fit_side_maps(T_TRAIN, base, ts.t2)
check("V5 one map is fitted per side", set(maps) == set(v5.REQUIRED_SIDES), str(maps))
check("V5 the home and away maps DIFFER", maps["home"] != maps["away"], str(maps))
applied = v5.apply_side_maps(T_TRAIN, base, maps)
hm = T_TRAIN["side"] == "home"
check("V5 the home map is applied only to home rows",
      np.allclose(applied[hm & base.notna()].to_numpy(dtype=float),
                  (maps["home"][0] + maps["home"][1]
                   * base[hm & base.notna()]).to_numpy(dtype=float)))
check("V5 the away map is applied only to away rows",
      np.allclose(applied[~hm & base.notna()].to_numpy(dtype=float),
                  (maps["away"][0] + maps["away"][1]
                   * base[~hm & base.notna()]).to_numpy(dtype=float)))

# --------------------------------------------------------------------------
# V6 -- residual DIRECTION (the v4 sign inversion)
# --------------------------------------------------------------------------
pred_s = pd.Series(np.full(400, 20.0))
out_s = pd.Series(np.concatenate([np.full(360, 18.0), np.full(40, 60.0)]))  # long UPPER tail
r = v5.residuals(out_s, pred_s)
check("V6 residual is outcome - prediction", float(r[0]) == -2.0, str(r[0]))
sd, off, method = v5.dispersion(r, min_resid=10)
check("V6 an asymmetric pool uses empirical quantiles", method == "empirical", method)
q = v5.emit_quantiles(np.array([20.0]), off, low=0.0)[0]
upper_gap, lower_gap = q[4] - q[2], q[2] - q[0]
check("V6 a long UPPER outcome tail emits a long UPPER quantile tail",
      upper_gap > lower_gap,
      f"upper={upper_gap:.3f} lower={lower_gap:.3f} -- v4's sign would invert this")
r_inv = (pred_s - out_s).to_numpy(float)          # the v4 convention
_, off_inv, _ = v5.dispersion(r_inv, min_resid=10)
q_inv = v5.emit_quantiles(np.array([20.0]), off_inv, low=0.0)[0]
check("V6 the v4 convention would have inverted the tail",
      (q_inv[4] - q_inv[2]) < (q_inv[2] - q_inv[0]),
      "reproduction of the defect")

# --------------------------------------------------------------------------
# V7 -- target-specific cold starts
# --------------------------------------------------------------------------
never = pd.DataFrame({
    "player_id": ["X"] * 5, "season": [2099] * 5,
    "game_id": [f"G{i}" for i in range(5)],
    "forecast_cutoff": pd.date_range("2099-05-01", periods=5, freq="D").tz_localize("UTC"),
    "game_date": pd.date_range("2099-05-01", periods=5, freq="D"),
    "appeared": [0, 0, 0, 0, 0],
})
h = v5.player_history_accounting(never)
check("V7 0-of-k gives p_plays_prior 0.0, not NaN",
      list(h["p_plays_prior"])[1:] == [0.0] * 4, str(list(h["p_plays_prior"])))
ca = v5.cold_start_flag(h, "p_active")
cc = v5.cold_start_flag(h, "e_minutes_given_active")
check("V7 p_active is cold ONLY on the first obligation",
      list(ca) == [True, False, False, False, False], str(list(ca)))
check("V7 conditional targets are cold on EVERY row with no prior appearance",
      list(cc) == [True] * 5, str(list(cc)))
check("V7 the two cold-start flags genuinely differ", list(ca) != list(cc))
check("V7 n_prior_games counts APPEARANCES", list(v5.n_prior_for(h, "p_active")) == [0] * 5)

mixed = never.copy()
mixed["appeared"] = [0, 1, 0, 1, 0]
hm2 = v5.player_history_accounting(mixed)
check("V7 a player with appearances stops being conditionally cold",
      list(v5.cold_start_flag(hm2, "attempts_usage")) == [True, True, False, False, False],
      str(list(v5.cold_start_flag(hm2, "attempts_usage"))))
check("V7 obligations and appearances are tracked separately",
      list(hm2["n_prior_candidate_games"]) == [0, 1, 2, 3, 4]
      and list(hm2["n_prior_appearances"]) == [0, 0, 1, 1, 2],
      f"{list(hm2['n_prior_candidate_games'])} / {list(hm2['n_prior_appearances'])}")
tpg = v5.team_prior_games(T_TRAIN)
check("V7 team rows report real prior-game counts, not always zero",
      int(tpg.max()) > 0 and int(tpg.min()) == 0, f"min={tpg.min()} max={tpg.max()}")

# --------------------------------------------------------------------------
# V8 -- the model hash responds to EVERY fitted parameter
# --------------------------------------------------------------------------
state = {"feature_order": list(v5.P_ACTIVE_FEATURES), "lambda": 1.0,
         "beta": [0.1, 0.2, 0.3], "scaler_mean": [1.0, 2.0], "scaler_std": [1.0, 1.0],
         "dropped": [], "fallback_mean": 20.0,
         "dispersion": {"sd": 3.0, "method": "empirical", "offsets": [-1, 0, 1]}}
h0 = v5.fitted_state_hash(state)
check("V8 the hash is a 64-hex digest", len(h0) == 64)
check("V8 hashing is deterministic", v5.fitted_state_hash(dict(state)) == h0)
for field, newval in (("lambda", 2.0), ("beta", [0.1, 0.2, 0.4]),
                      ("scaler_mean", [1.0, 2.5]), ("scaler_std", [1.0, 2.0]),
                      ("dropped", ["min_ewma"]), ("fallback_mean", 21.0),
                      ("feature_order", list(reversed(v5.P_ACTIVE_FEATURES)))):
    s2 = dict(state)
    s2[field] = newval
    check(f"V8 the hash changes when {field} changes",
          v5.fitted_state_hash(s2) != h0, f"{field} did not move the hash")
s3 = dict(state)
s3["dispersion"] = {"sd": 3.5, "method": "empirical", "offsets": [-1, 0, 1]}
check("V8 the hash changes when dispersion state changes",
      v5.fitted_state_hash(s3) != h0)

good = "a" * 64
try:
    v5.require_identity(good, good, synthetic=False)
    check("V8 a real run accepts explicit 64-hex identities", True)
except v5.AdapterBoundaryError as e:
    check("V8 a real run accepts explicit 64-hex identities", False, str(e))
for cfg, snap, label in ((good, "synthetic", "placeholder snapshot"),
                         ("not-a-hash", good, "non-hex config"),
                         (good, "0" * 64, "all-zero snapshot")):
    try:
        v5.require_identity(cfg, snap, synthetic=False)
        check(f"V8 a real run rejects a {label}", False, "no exception raised")
    except v5.AdapterBoundaryError:
        check(f"V8 a real run rejects a {label}", True)
try:
    v5.require_identity("anything", "synthetic", synthetic=True)
    check("V8 synthetic runs may use placeholders explicitly", True)
except v5.AdapterBoundaryError as e:
    check("V8 synthetic runs may use placeholders explicitly", False, str(e))

# --------------------------------------------------------------------------
# V9 -- Stage-A features and feature_asof fail closed
# --------------------------------------------------------------------------
full = TRAIN.copy()
for c in v5.P_ACTIVE_FEATURES:
    if c not in full.columns:
        full[c] = 0.0
hf = v5.player_history_accounting(full)
Xs = v5.stage_a_features_strict(full, hf, 0.5)
check("V9 a complete frame builds all 14 features in canonical order",
      list(Xs.columns) == list(v5.P_ACTIVE_FEATURES))
try:
    v5.stage_a_features_strict(TRAIN, hist, 0.5)
    check("V9 missing Stage-A features fail closed", False, "no exception raised")
except v5.MissingRequiredInput:
    check("V9 missing Stage-A features fail closed", True)
check("V9 declared defaults must be opted into explicitly",
      v5.stage_a_features_strict(TRAIN, hist, 0.5, allow_declared_defaults=True)
      .shape == (len(TRAIN), 14))

asof = v5.resolve_feature_asof(TRAIN, ["src_ts"])
check("V9 feature_asof is derived from real source timestamps", len(asof) == len(TRAIN))
try:
    v5.resolve_feature_asof(TRAIN, ["nonexistent_ts"])
    check("V9 absent source timestamps fail closed", False, "no exception")
except v5.MissingRequiredInput:
    check("V9 absent source timestamps fail closed", True)
late = TRAIN.copy()
late["src_ts"] = late["forecast_cutoff"]
try:
    v5.resolve_feature_asof(late, ["src_ts"])
    check("V9 a source at/after the cutoff fails closed", False, "no exception")
except v5.MissingRequiredInput:
    check("V9 a source at/after the cutoff fails closed", True)

# --------------------------------------------------------------------------
# V10 -- the strict validator catches what the historical one does not
# --------------------------------------------------------------------------
n = 40
uni = pd.DataFrame({
    "row_uid": [f"pg_{i}" for i in range(n)],
    "prediction_required__attempts_usage": True,
    "outcome_scoreable__attempts_usage": True,
    "fold_id": "season:2099",
    "forecast_cutoff": pd.date_range("2099-05-01", periods=n, freq="h",
                                     tz="UTC").astype(str),
})
H = "b" * 64
ok_pred = pd.DataFrame({
    "row_uid": uni.row_uid, "target_key": "attempts_usage", "arm_id": v5.ARM_ID,
    "fold_id": "season:2099", "forecast_cutoff": uni.forecast_cutoff,
    "pred_point": 7.0, "pred_sd": 2.0,
    "pred_q05": 3.0, "pred_q25": 5.0, "pred_q50": 7.0, "pred_q75": 9.0, "pred_q95": 11.0,
    "is_fallback": False, "is_cold_start": False, "n_prior_games": 3,
    "feature_asof": (pd.to_datetime(uni.forecast_cutoff)
                     - pd.Timedelta(hours=1)).astype(str),
    "model_hash": H, "config_hash": H, "data_snapshot_hash": H,
    "exclusion_reason": pd.NA,
})
base_v = validate_strict(ok_pred.assign(arm_id=v5.ARM_ID), uni, "attempts_usage",
                         expected_fold_id="season:2099",
                         expected_arm_id=v5.ARM_ID, expected_config_hash=H,
                         expected_snapshot_hash=H)
check("V10 a clean frame passes the strict validator", base_v["ok"], str(base_v["problems"]))
check("V10 the historical validator also passes it",
      validate_predictions(ok_pred, uni, "attempts_usage")["ok"])

cases = [
    ("wrong fold_id", lambda d: d.assign(fold_id="season:2098")),
    ("wrong target_key", lambda d: d.assign(target_key="p_active")),
    ("cutoff disagreeing with the universe",
     lambda d: d.assign(forecast_cutoff=(pd.to_datetime(d.forecast_cutoff)
                                         + pd.Timedelta(days=1)).astype(str))),
    ("pred_point below support", lambda d: d.assign(pred_point=-1.0)),
    ("a quantile below support", lambda d: d.assign(pred_q05=-5.0)),
    ("a non-hex model_hash", lambda d: d.assign(model_hash="deadbeef")),
    ("a config_hash that is not the expected one", lambda d: d.assign(config_hash="c" * 64)),
    ("a non-boolean is_fallback", lambda d: d.assign(is_fallback="yes")),
    ("a negative n_prior_games", lambda d: d.assign(n_prior_games=-2)),
]
for label, mutate in cases:
    bad = mutate(ok_pred.assign(arm_id=v5.ARM_ID).copy())
    sv = validate_strict(bad, uni, "attempts_usage", expected_fold_id="season:2099",
                         expected_arm_id=v5.ARM_ID, expected_config_hash=H,
                         expected_snapshot_hash=H)
    check(f"V10 strict validator rejects {label}", not sv["ok"], str(sv["problems"]))

missed = 0
for label, mutate in cases:
    bad = mutate(ok_pred.assign(arm_id=v5.ARM_ID).copy())
    if validate_predictions(bad, uni, "attempts_usage")["ok"]:
        missed += 1
check("V10 the historical validator misses most of these (hence a second one)",
      missed >= 6, f"historical validator caught all but {missed}")

# Identity is now MANDATORY, so these must supply it -- otherwise they would
# "pass" by failing on missing identity rather than on the defect they name.
IDK = dict(expected_arm_id=v5.ARM_ID, expected_fold_id="season:2099",
           expected_config_hash=H, expected_snapshot_hash=H)
ok_pred_v5 = ok_pred.assign(arm_id=v5.ARM_ID)
sv_sd = validate_strict(ok_pred_v5.assign(pred_sd=0.0), uni, "attempts_usage", **IDK)
check("V10 strict validator rejects pred_sd == 0", not sv_sd["ok"],
      str(sv_sd["problems"]))
check("V10 ... and it is the SD that is rejected",
      any("pred_sd" in p for p in sv_sd["problems"]), str(sv_sd["problems"]))
sv_q = validate_strict(ok_pred_v5.assign(pred_q05=99.0), uni, "attempts_usage", **IDK)
check("V10 strict validator rejects non-monotone quantiles", not sv_q["ok"])
check("V10 ... and it is the quantiles that are rejected",
      any("quantile" in p for p in sv_q["problems"]), str(sv_q["problems"]))
sv_missing = validate_strict(ok_pred_v5.iloc[3:], uni, "attempts_usage", **IDK)
check("V10 strict validator rejects missing obligation rows", not sv_missing["ok"])
check("V10 ... and it is the coverage that is rejected",
      any("REQUIRED" in p for p in sv_missing["problems"]), str(sv_missing["problems"]))
sv_pa = validate_strict(ok_pred_v5.assign(target_key="p_active", pred_point=0.5,
                                          pred_sd=np.nan), uni, "p_active", **IDK)
check("V10 strict validator requires null quantiles for p_active", not sv_pa["ok"],
      str(sv_pa["problems"]))
check("V10 identity is MANDATORY -- omitting it is itself a rejection",
      not validate_strict(ok_pred_v5, uni, "attempts_usage")["ok"])

print(f"{PASSED}/{PASSED + len(FAILED)} tests passed")
for f in FAILED:
    print(f"  FAIL  {f}")
sys.exit(1 if FAILED else 0)
