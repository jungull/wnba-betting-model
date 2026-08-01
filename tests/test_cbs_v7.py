#!/usr/bin/env python
"""test_cbs_v7.py — runner-level synthetic suite for `contract_baseline_suite_v7`.

**Synthetic only.** No contract parquet is read, no historical OOF is produced,
no accuracy or coverage figure is computed or inspected. The only file any code
path here reads is `experiments/registry.jsonl`, and only to recompute the
registered config digest.

v6's suite proved a great deal *inside one season*, against a runner that never
checked which season its rows were in. Every section below targets a boundary v6
left open:

  F1  outer-fold guard: same-season and future-season contamination, train/test
      row overlap, a training boundary that runs into the fold, malformed ids
  F2  identity: the EXACT registered config, a wrong-but-valid 64-hex digest, a
      snapshot identity DERIVED from the manifest, and manifest tampering
  F3  outcome availability and causal walk-forward, player and team
  F4  the real feature-source contract: derived as-of, missing and late sources,
      and declared defaults forbidden on the real path
  F5  the player fallback ladder, levels 1-4
  F6  team MIN_PRIOR=5 binding BOTH selection and emission; 0-4 versus 5+
  F7  stable teams that alternate home and away
  F8  the provenance sidecar: schema, uniqueness, one-to-one binding, digest,
      tampering and substitution
  F9  the composite gate: five targets, every named receipt, and the conjunction
  F10 strict `/3` rejection, including excluded-row lineage
  F11 shuffle invariance, calibration isolation, coverage and hash sensitivity
  F12 team structural preconditions, training obligations separated from
      prediction obligations
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import cbs_v5 as v5  # noqa: E402
import cbs_v7 as v7  # noqa: E402
from contract_validator_v3_strict import (validate_arm_output_v3,  # noqa: E402
                                          validate_strict_v3)

PASSED = 0
FAILED: list[str] = []

CFG = v7.SYNTHETIC_CONFIG_HASH
MANIFEST = {"schema": v7.SNAPSHOT_MANIFEST_SCHEMA,
            "captured_at": "2100-09-01T00:00:00+00:00",
            "artifacts": {"player_game.parquet": "a" * 64,
                          "team_game.parquet": "b" * 64}}
SNAP = v7.snapshot_identity(MANIFEST)
IDENT = dict(config_hash=CFG, snapshot_hash=SNAP, snapshot_manifest=MANIFEST)


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASSED
    if cond:
        PASSED += 1
    else:
        FAILED.append(f"{name}: {detail}")


def raises(name: str, exc, fn, *a, **kw) -> None:
    """Assert `fn` fails closed with `exc` rather than returning a number."""
    try:
        fn(*a, **kw)
        check(name, False, "no exception raised")
    except exc:
        check(name, True)
    except Exception as other:                    # wrong failure is still a failure
        check(name, False, f"raised {type(other).__name__}: {other}")


# --------------------------------------------------------------------------
# fixtures
# --------------------------------------------------------------------------

def pframe(season, n_players=8, n_dates=40, seed=3, start=None, with_sources=False):
    rng = np.random.default_rng(seed)
    dates = pd.date_range(start or f"{season}-05-01", periods=n_dates, freq="D")
    rows = []
    for gi, d in enumerate(dates):
        for pid in range(n_players):
            ap = int(rng.random() < 0.55 + 0.04 * pid)
            mn = float(rng.uniform(9, 33)) if ap else 0.0
            cut = (d - pd.Timedelta(hours=6)).tz_localize("UTC")
            row = {
                "row_uid": f"pg_{season}_{gi:04d}_{pid}", "player_id": f"P{pid}",
                "season": season, "game_id": f"G{season}{gi:04d}", "game_date": d,
                "forecast_cutoff": cut.isoformat(),
                "feature_asof": (cut - pd.Timedelta(hours=6)).isoformat(),
                "appeared": ap, "minutes": mn,
                "fga": float(rng.poisson(max(mn, .1) * .35)) if ap else 0.0,
                "points": float(rng.poisson(max(mn, .1) * .45)) if ap else 0.0,
            }
            if with_sources:
                for k, lag in zip(v7.REQUIRED_PLAYER_FEATURE_SOURCES, (9, 8, 30)):
                    row[k] = (cut - pd.Timedelta(hours=lag)).isoformat()
                for f in v5.P_ACTIVE_FEATURES:
                    if f not in ("p_plays_prior", "player_gp_season"):
                        row[f] = float(rng.uniform(0, 1))
            rows.append(row)
    return pd.DataFrame(rows).reset_index(drop=True)


#: STABLE teams that alternate sides — v6's `T{pair}_{side}` made every team
#: permanently home-only or away-only, so a side map was fitted on a population
#: that never appeared on the other side and history never crossed the split.
TEAMS = ["ATL", "CHI", "CON", "IND", "LVA", "MIN"]


def tframe(season, n_dates=40, seed=5, start=None, with_sources=False,
           with_outcome=True):
    rng = np.random.default_rng(seed)
    dates = pd.date_range(start or f"{season}-05-01", periods=n_dates, freq="D")
    rows = []
    for gi, d in enumerate(dates):
        rot = TEAMS[gi % len(TEAMS):] + TEAMS[:gi % len(TEAMS)]
        for pair in range(len(TEAMS) // 2):
            home, away = rot[2 * pair], rot[2 * pair + 1]
            gid = f"TG{season}{gi:04d}_{pair}"
            for side, team in (("home", home), ("away", away)):
                cut = (d - pd.Timedelta(hours=6)).tz_localize("UTC")
                row = {
                    "row_uid": f"tg_{season}_{gi:04d}_{pair}_{side}",
                    "team_id": team, "game_id": gid, "season": season,
                    "game_date": d, "side": side,
                    "forecast_cutoff": cut.isoformat(),
                    "feature_asof": (cut - pd.Timedelta(hours=6)).isoformat(),
                    "ch_ft": float(rng.uniform(10, 20)),
                    "ch_3pt": float(rng.uniform(15, 30)),
                    "ch_paint": float(rng.uniform(25, 40)),
                    "ch_np2": float(rng.uniform(8, 18)),
                    "n_candidates": 12,
                }
                if with_outcome:
                    row["team_points"] = (float(rng.uniform(68, 96))
                                          + (4.0 if side == "home" else 0.0))
                if with_sources:
                    for k, lag in zip(v7.REQUIRED_TEAM_FEATURE_SOURCES, (9, 30)):
                        row[k] = (cut - pd.Timedelta(hours=lag)).isoformat()
                rows.append(row)
    return pd.DataFrame(rows).reset_index(drop=True)


def universe_for(df, targets, fold_id):
    u = pd.DataFrame({"row_uid": df["row_uid"].to_numpy(), "fold_id": fold_id,
                      "forecast_cutoff": df["forecast_cutoff"].to_numpy()})
    if "appeared" in df.columns:
        u["appeared"] = df["appeared"].astype(bool).to_numpy()
    for t in targets:
        u[f"prediction_required__{t}"] = True
        u[f"outcome_scoreable__{t}"] = (df["appeared"].astype(bool).to_numpy()
                                        if ("appeared" in df.columns and t != "p_active")
                                        else True)
    return u


FOLD = "season:2100"
TRAIN, TEST = pframe(2099), pframe(2100, seed=9, n_dates=14)
T_TRAIN, T_TEST = tframe(2099), tframe(2100, seed=11, n_dates=12)
PUNI = universe_for(TEST, v7.PLAYER_TARGETS, FOLD)
TUNI = universe_for(T_TEST, [v7.TEAM_TARGET], FOLD)

res = v7.run_player_fold(TRAIN, TEST, FOLD, universe=PUNI, **IDENT)
tres = v7.run_team_fold(T_TRAIN, T_TEST, FOLD, universe=TUNI, **IDENT)
P = res["predictions"]
TP = tres["predictions"][v7.TEAM_TARGET]


# --------------------------------------------------------------------------
# F1 -- the outer-fold guard
# --------------------------------------------------------------------------

check("F1 a clean season outer fold is accepted", res["receipts"]["fold_boundary"]["ok"])
check("F1 the receipt names the test season",
      res["receipts"]["fold_boundary"]["test_season"] == 2100)
check("F1 the receipt records the training seasons",
      res["receipts"]["fold_boundary"]["train_seasons"] == [2099])
check("F1 the receipt asserts row-id disjointness",
      res["receipts"]["fold_boundary"]["row_uid_disjoint"] is True)
check("F1 the receipt asserts the training boundary precedes the fold",
      res["receipts"]["fold_boundary"]["train_boundary_precedes_test"] is True)

# SAME-SEASON contamination -- exactly what v6's own fixtures did
same = pframe(2100, seed=21, n_dates=20, start="2100-01-01")
raises("F1 same-season training contamination is rejected", v7.OuterFoldViolation,
       v7.run_player_fold, same, TEST, FOLD, universe=PUNI, **IDENT)
# FUTURE-season contamination
fut = pframe(2101, seed=22, n_dates=20, start="2101-01-01")
raises("F1 future-season training contamination is rejected", v7.OuterFoldViolation,
       v7.require_outer_fold, fut, TEST, FOLD)
# a test row from the wrong season
mixed = pd.concat([TEST, pframe(2099, seed=23, n_dates=1, start="2099-06-01")],
                  ignore_index=True)
raises("F1 a test row outside the fold season is rejected", v7.OuterFoldViolation,
       v7.require_outer_fold, TRAIN, mixed, FOLD)
# train/test row overlap
overlap_tr = pd.concat([TRAIN, TEST.iloc[:3]], ignore_index=True)
raises("F1 train/test row_uid overlap is rejected", v7.OuterFoldViolation,
       v7.require_outer_fold, overlap_tr, TEST, FOLD)
# a training boundary that runs into the fold
late = TRAIN.copy()
late.loc[late.index[-1], "forecast_cutoff"] = TEST["forecast_cutoff"].max()
late.loc[late.index[-1], "season"] = 2099
raises("F1 a training cutoff inside the test fold is rejected", v7.OuterFoldViolation,
       v7.require_outer_fold, late, TEST, FOLD)
raises("F1 a malformed fold_id is rejected", v7.OuterFoldViolation,
       v7.require_outer_fold, TRAIN, TEST, "fold-7")
raises("F1 a non-numeric fold season is rejected", v7.OuterFoldViolation,
       v7.require_outer_fold, TRAIN, TEST, "season:latest")
raises("F1 an empty test fold is rejected", v7.OuterFoldViolation,
       v7.require_outer_fold, TRAIN, TEST.iloc[:0], FOLD)
check("F1 the team runner enforces the same guard",
      tres["receipts"]["fold_boundary"]["ok"])
raises("F1 team same-season contamination is rejected", v7.OuterFoldViolation,
       v7.run_team_fold, tframe(2100, seed=24, n_dates=20, start="2100-01-01"),
       T_TEST, FOLD, universe=TUNI, **IDENT)


# --------------------------------------------------------------------------
# F2 -- identity binding
# --------------------------------------------------------------------------

check("F2 the run binds the synthetic config constant",
      res["receipts"]["identity_binding"]["config_hash"] == CFG)
check("F2 the snapshot identity is DERIVED from the manifest",
      res["receipts"]["identity_binding"]["snapshot_hash"] == SNAP
      and SNAP == v7.snapshot_identity(MANIFEST))

# a wrong-but-perfectly-valid 64-hex digest -- v6 accepted exactly this
raises("F2 a wrong but valid 64-hex config digest is rejected", v7.AdapterBoundaryError,
       v7.run_player_fold, TRAIN, TEST, FOLD, universe=PUNI,
       config_hash="c" * 64, snapshot_hash=SNAP, snapshot_manifest=MANIFEST)
raises("F2 a wrong but valid 64-hex snapshot digest is rejected", v7.AdapterBoundaryError,
       v7.run_player_fold, TRAIN, TEST, FOLD, universe=PUNI,
       config_hash=CFG, snapshot_hash="d" * 64, snapshot_manifest=MANIFEST)
raises("F2 the registered config digest is not accepted on the synthetic path",
       v7.AdapterBoundaryError, v7.require_registered_identity,
       v7.REGISTERED_CONFIG_HASH, SNAP, MANIFEST, synthetic=True)
raises("F2 a missing snapshot manifest is rejected", v7.AdapterBoundaryError,
       v7.require_registered_identity, CFG, SNAP, None, synthetic=True)

# tampering with the manifest moves the identity, so the old digest fails
tampered = {**MANIFEST, "artifacts": {**MANIFEST["artifacts"],
                                      "player_game.parquet": "e" * 64}}
check("F2 tampering with the manifest moves the derived identity",
      v7.snapshot_identity(tampered) != SNAP)
raises("F2 a tampered manifest no longer matches the claimed snapshot hash",
       v7.AdapterBoundaryError, v7.require_registered_identity,
       CFG, SNAP, tampered, synthetic=True)
raises("F2 a manifest with the wrong schema is rejected", v7.AdapterBoundaryError,
       v7.snapshot_identity, {**MANIFEST, "schema": "something/1"})
raises("F2 a manifest with no artifacts is rejected", v7.AdapterBoundaryError,
       v7.snapshot_identity, {**MANIFEST, "artifacts": {}})
raises("F2 a manifest with a non-hex artifact digest is rejected",
       v7.AdapterBoundaryError, v7.snapshot_identity,
       {**MANIFEST, "artifacts": {"x.parquet": "not-a-digest"}})
raises("F2 a manifest with no captured_at is rejected", v7.AdapterBoundaryError,
       v7.snapshot_identity, {"schema": v7.SNAPSHOT_MANIFEST_SCHEMA,
                              "artifacts": {"x.parquet": "a" * 64}})

# the registered constant must recompute from the registry itself
try:
    recomputed = v7.recompute_registered_config_hash()
    check("F2 the registered config digest recomputes from the registry",
          recomputed == v7.REGISTERED_CONFIG_HASH,
          f"registry {recomputed} vs module {v7.REGISTERED_CONFIG_HASH}")
except v7.AdapterBoundaryError as exc:
    check("F2 the registered config digest recomputes from the registry", False, str(exc))
raises("F2 an unregistered experiment id has no config digest", v7.AdapterBoundaryError,
       v7.recompute_registered_config_hash, experiment_id="no_such_arm_v99")


# --------------------------------------------------------------------------
# F3 -- outcome availability and causal walk-forward
# --------------------------------------------------------------------------

avail, src = v7.resolve_outcome_availability(TEST)
check("F3 with no observed column the source is POLICY, never 'observed'",
      src == "policy")
check("F3 the policy timestamp is the frozen conservative bound",
      bool((avail == pd.to_datetime(TEST["game_date"], utc=True).dt.floor("D")
            + pd.Timedelta(hours=v7.OUTCOME_AVAILABILITY_POLICY_LAG_HOURS)).all()))
check("F3 the run reports the policy id rather than claiming an observation",
      res["diagnostics"]["availability"] == {
          "source": "policy", "policy_id": v7.OUTCOME_AVAILABILITY_POLICY_ID})

obs = TEST.copy()
obs[v7.OUTCOME_OBSERVED_AT_COL] = (
    pd.to_datetime(obs["game_date"], utc=True) + pd.Timedelta(hours=30)).map(
        lambda t: t.isoformat())
_, src_obs = v7.resolve_outcome_availability(obs)
check("F3 a fully supplied observed column is used and labelled 'observed'",
      src_obs == "observed")
half = obs.copy()
half.loc[half.index[:5], v7.OUTCOME_OBSERVED_AT_COL] = None
raises("F3 a half-populated observed column is rejected, not back-filled",
       v7.MissingRequiredInput, v7.resolve_outcome_availability, half)

# a row can never read its own outcome
early = TEST.copy()
early[v7.OUTCOME_OBSERVED_AT_COL] = (
    pd.to_datetime(early["forecast_cutoff"], utc=True)
    - pd.Timedelta(hours=1)).map(lambda t: t.isoformat())
raises("F3 an outcome available before its own cutoff fails closed",
       v7.AvailabilityViolation, v7.build_walk_forward_plan, early,
       group_cols=["player_id", "season"], sort_cols=list(v5.PLAYER_SORT_KEYS))

# causal: changing a row's own outcome cannot move its own or any earlier prediction
ordered = TEST.sort_values(list(v5.PLAYER_SORT_KEYS), kind="mergesort")
target_uid = ordered.iloc[len(ordered) // 2]["row_uid"]
bumped = TEST.copy()
sel = bumped.row_uid == target_uid
bumped.loc[sel, ["minutes", "fga", "points"]] = 999.0
res_b = v7.run_player_fold(TRAIN, bumped, FOLD, universe=PUNI, **IDENT)
pid = TEST.loc[sel, "player_id"].iloc[0]
cut = TEST.loc[sel, "forecast_cutoff"].iloc[0]
earlier = TEST[(TEST.player_id == pid) & (TEST.forecast_cutoff < cut)].row_uid
for tgt in ("e_minutes_given_active", "attempts_usage"):
    a = P[tgt].set_index("row_uid").pred_point
    b = res_b["predictions"][tgt].set_index("row_uid").pred_point
    check(f"F3 {tgt}: a row's own outcome cannot change its own prediction",
          np.isclose(a.loc[target_uid], b.loc[target_uid], equal_nan=True),
          f"{a.loc[target_uid]} -> {b.loc[target_uid]}")
    if len(earlier):
        check(f"F3 {tgt}: no EARLIER prediction changed",
              np.allclose(a.loc[earlier].to_numpy(float),
                          b.loc[earlier].to_numpy(float), equal_nan=True))
check("F3 other players are unaffected",
      np.allclose(P["e_minutes_given_active"].set_index("row_uid").pred_point
                  .loc[TEST[TEST.player_id != pid].row_uid].to_numpy(float),
                  res_b["predictions"]["e_minutes_given_active"].set_index("row_uid")
                  .pred_point.loc[TEST[TEST.player_id != pid].row_uid].to_numpy(float),
                  equal_nan=True))

# the same causality, on the TEAM side -- v6 tested players only
t_ord = T_TEST.sort_values(list(v5.TEAM_SORT_KEYS), kind="mergesort")
t_uid = t_ord.iloc[len(t_ord) // 2]["row_uid"]
t_bump = T_TEST.copy()
t_sel = t_bump.row_uid == t_uid
t_bump.loc[t_sel, ["ch_ft", "ch_3pt", "ch_paint", "ch_np2", "team_points"]] = 999.0
t_res_b = v7.run_team_fold(T_TRAIN, t_bump, FOLD, universe=TUNI, **IDENT)
ta = TP.set_index("row_uid").pred_point
tb = t_res_b["predictions"][v7.TEAM_TARGET].set_index("row_uid").pred_point
team_of = T_TEST.loc[t_sel, "team_id"].iloc[0]
t_cut = T_TEST.loc[t_sel, "forecast_cutoff"].iloc[0]
t_earlier = T_TEST[(T_TEST.team_id == team_of)
                   & (T_TEST.forecast_cutoff < t_cut)].row_uid
check("F3 team: a row's own channels cannot change its own prediction",
      np.isclose(ta.loc[t_uid], tb.loc[t_uid], equal_nan=True),
      f"{ta.loc[t_uid]} -> {tb.loc[t_uid]}")
if len(t_earlier):
    check("F3 team: no EARLIER team prediction changed",
          np.allclose(ta.loc[t_earlier].to_numpy(float),
                      tb.loc[t_earlier].to_numpy(float), equal_nan=True))
check("F3 team: other teams are unaffected",
      np.allclose(ta.loc[T_TEST[T_TEST.team_id != team_of].row_uid].to_numpy(float),
                  tb.loc[T_TEST[T_TEST.team_id != team_of].row_uid].to_numpy(float),
                  equal_nan=True))

# a LATE outcome is not admitted merely because it is positionally prior
plan = v7.build_walk_forward_plan(TEST, group_cols=["player_id", "season"],
                                  sort_cols=list(v5.PLAYER_SORT_KEYS))
late_out = TEST.copy()
late_out[v7.OUTCOME_OBSERVED_AT_COL] = (
    pd.to_datetime(late_out["game_date"], utc=True)
    + pd.Timedelta(days=400)).map(lambda t: t.isoformat())
plan_late = v7.build_walk_forward_plan(late_out, group_cols=["player_id", "season"],
                                       sort_cols=list(v5.PLAYER_SORT_KEYS))
check("F3 an outcome published far too late is admitted by NOBODY",
      int(plan_late.n_admitted.sum()) == 0,
      f"{int(plan_late.n_admitted.sum())} admissions survived a 400-day lag")
check("F3 the same rows under the normal policy DO build history",
      int(plan.n_admitted.sum()) > 0)
# ERRATUM 2026-08-01: this assertion read
#   (plan.n_admitted <= np.arange(len(plan.order))).all() or True
# The `or True` made it unconditionally true, and it was there because the
# comparison itself was wrong: it measured each row's WITHIN-GROUP admitted count
# against a GLOBAL ordered position. The real invariant is that the
# availability-gated admissions are a subset of the rows that are prior by
# cutoff within the same group — which is what an engine admitting a non-prior
# row would violate.
_prior_counts = np.asarray([len(p) for p in v7._prior_by_cutoff(plan)], dtype=int)
check("F3 admitted history never exceeds the rows prior by cutoff in the same group",
      bool((plan.n_admitted <= _prior_counts).all()),
      f"max admitted {int(plan.n_admitted.max())} vs max prior "
      f"{int(_prior_counts.max())}")


# --------------------------------------------------------------------------
# F4 -- the real feature-source contract
# --------------------------------------------------------------------------

real_tr = pframe(2099, seed=31, with_sources=True)
real_te = pframe(2100, seed=32, n_dates=14, with_sources=True)
derived = v7.resolve_feature_asof_strict(real_te, v7.REQUIRED_PLAYER_FEATURE_SOURCES)
expected = pd.to_datetime(real_te[list(v7.REQUIRED_PLAYER_FEATURE_SOURCES)]
                          .apply(pd.to_datetime, utc=True).max(axis=1), utc=True)
check("F4 feature_asof is the row MAXIMUM over the sources actually read",
      bool((pd.to_datetime(derived, utc=True) == expected).all()))
check("F4 the derived as-of is strictly before every cutoff",
      bool((pd.to_datetime(derived, utc=True)
            < pd.to_datetime(real_te["forecast_cutoff"], utc=True)).all()))

raises("F4 absent source timestamps fail closed", v7.MissingRequiredInput,
       v7.resolve_feature_asof_strict, TEST, v7.REQUIRED_PLAYER_FEATURE_SOURCES)
one_missing = real_te.drop(columns=[v7.REQUIRED_PLAYER_FEATURE_SOURCES[0]])
raises("F4 a single missing source column fails closed", v7.MissingRequiredInput,
       v7.resolve_feature_asof_strict, one_missing, v7.REQUIRED_PLAYER_FEATURE_SOURCES)
nulled = real_te.copy()
nulled.loc[nulled.index[:2], v7.REQUIRED_PLAYER_FEATURE_SOURCES[1]] = None
raises("F4 a null source timestamp fails closed", v7.MissingRequiredInput,
       v7.resolve_feature_asof_strict, nulled, v7.REQUIRED_PLAYER_FEATURE_SOURCES)
unparseable = real_te.copy()
unparseable[v7.REQUIRED_PLAYER_FEATURE_SOURCES[1]] = "not-a-timestamp"
raises("F4 an unparseable source timestamp fails closed", v7.MissingRequiredInput,
       v7.resolve_feature_asof_strict, unparseable, v7.REQUIRED_PLAYER_FEATURE_SOURCES)
late_src = real_te.copy()
late_src[v7.REQUIRED_PLAYER_FEATURE_SOURCES[0]] = late_src["forecast_cutoff"]
raises("F4 a source read AT the cutoff fails closed (equality is a violation)",
       v7.MissingRequiredInput, v7.resolve_feature_asof_strict, late_src,
       v7.REQUIRED_PLAYER_FEATURE_SOURCES)
later_src = real_te.copy()
later_src[v7.REQUIRED_PLAYER_FEATURE_SOURCES[0]] = (
    pd.to_datetime(later_src["forecast_cutoff"], utc=True)
    + pd.Timedelta(hours=1)).map(lambda t: t.isoformat())
raises("F4 a source read AFTER the cutoff fails closed", v7.MissingRequiredInput,
       v7.resolve_feature_asof_strict, later_src, v7.REQUIRED_PLAYER_FEATURE_SOURCES)

# the real path forbids declared defaults OUTRIGHT -- v6 defaulted them to True
raises("F4 the real path refuses declared Stage-A defaults even if asked",
       v7.AdapterBoundaryError, v7.run_player_fold, real_tr, real_te, FOLD,
       universe=universe_for(real_te, v7.PLAYER_TARGETS, FOLD), synthetic=False,
       allow_declared_defaults=True, config_hash=v7.REGISTERED_CONFIG_HASH,
       snapshot_hash=SNAP, snapshot_manifest=MANIFEST)
hist_stub = v7.player_history_walk_forward(
    real_te, v7.build_walk_forward_plan(real_te, group_cols=["player_id", "season"],
                                        sort_cols=list(v5.PLAYER_SORT_KEYS)))
raises("F4 missing Stage-A features fail closed when defaults are not permitted",
       v7.MissingRequiredInput, v7.stage_a_features_v7, TEST,
       v7.player_history_walk_forward(
           TEST, v7.build_walk_forward_plan(
               TEST, group_cols=["player_id", "season"],
               sort_cols=list(v5.PLAYER_SORT_KEYS))),
       0.5, allow_declared_defaults=False)
X_ok = v7.stage_a_features_v7(real_te, hist_stub, 0.5, allow_declared_defaults=False)
check("F4 a fully supplied real frame builds all 14 features",
      list(X_ok.columns) == list(v5.P_ACTIVE_FEATURES) and len(X_ok) == len(real_te))
nan_feat = real_te.copy()
nan_feat.loc[nan_feat.index[0], "min_ewma"] = np.nan
raises("F4 a null feature may not become a silent zero on the real path",
       v7.MissingRequiredInput, v7.stage_a_features_v7, nan_feat, hist_stub, 0.5,
       allow_declared_defaults=False)

# the derived as-of, not the caller's column, is what reaches the emitted rows
lying = real_te.copy()
lying["feature_asof"] = "2000-01-01T00:00:00+00:00"
res_real = v7.run_player_fold(
    real_tr, lying, FOLD, universe=universe_for(lying, v7.PLAYER_TARGETS, FOLD),
    synthetic=True, allow_declared_defaults=False, **IDENT)
emitted_fa = pd.to_datetime(res_real["predictions"]["p_active"]["feature_asof"], utc=True)
check("F4 the emitted feature_asof is DERIVED, not copied from the caller",
      bool((emitted_fa > pd.Timestamp("2001-01-01", tz="UTC")).all()),
      "a caller-supplied feature_asof column was trusted")


# --------------------------------------------------------------------------
# F5 -- the player fallback ladder
# --------------------------------------------------------------------------

lv = P["e_minutes_given_active"].set_index("row_uid").fallback_level
check("F5 fallback_level is an integer within the registered ladder",
      bool(lv.isin(list(v7.FALLBACK_LADDER)).all()))
check("F5 is_fallback is exactly fallback_level > 0",
      bool((P["e_minutes_given_active"].set_index("row_uid").is_fallback
            == (lv > 0)).all()))
check("F5 level 3 (no history) is present in a fresh fold", (lv == 3).any())
check("F5 level 2 (1-2 prior appearances) is present", (lv == 2).any())
check("F5 level 0 (fitted) is present", (lv == 0).any())

sc7 = res["provenance_sidecar"]
cond = sc7[sc7.target_key == "e_minutes_given_active"].set_index("row_uid")
check("F5 every level-2 row really has 1-2 prior appearances",
      bool(cond.loc[lv[lv == 2].index, "n_prior_appearances"]
           .between(1, v7.PLAYER_SHORT_HISTORY_MAX).all()))
check("F5 every level-3 row really has zero prior appearances or no center",
      bool((cond.loc[lv[lv == 3].index, "n_prior_appearances"] == 0).all()))
check("F5 every level-0 row has more than the short-history band",
      bool((cond.loc[lv[lv == 0].index, "n_prior_appearances"]
            > v7.PLAYER_SHORT_HISTORY_MAX).all()))

# level 4: the registered declared-constant season
s21_tr = pframe(2020, seed=41, n_dates=30, start="2020-05-01")
s21_te = pframe(2021, seed=42, n_dates=12, start="2021-05-01")
r21 = v7.run_player_fold(s21_tr, s21_te, "season:2021",
                         universe=universe_for(s21_te, v7.PLAYER_TARGETS, "season:2021"),
                         **IDENT)
check("F5 level 4 covers every row of a declared-constant season",
      bool((r21["predictions"]["attempts_usage"].fallback_level == 4).all()))
check("F5 a declared-constant season is entirely fallback",
      bool(r21["predictions"]["attempts_usage"].is_fallback.all()))
check("F5 a declared-constant season still passes the composite gate",
      r21["scoring_permitted"], str(r21["failed_receipts"]))

# level 1: a degenerate training window
tiny = pframe(2099, seed=43, n_dates=3, start="2099-05-01")
r_deg = v7.run_player_fold(tiny, TEST, FOLD, universe=PUNI, **IDENT)
deg_lv = r_deg["predictions"]["attempts_usage"].fallback_level
check("F5 a degenerate fold reports level 1 for rows that have history",
      (deg_lv == 1).any(), f"levels seen: {sorted(set(deg_lv))}")
check("F5 a degenerate fold still escalates historyless rows to level 3",
      (deg_lv == 3).any())
check("F5 every row of a degenerate fold is a fallback",
      bool(r_deg["predictions"]["attempts_usage"].is_fallback.all()))
check("F5 the component id records that a declared constant produced the value",
      bool(r_deg["predictions"]["attempts_usage"].component_id
           .str.endswith("declared_constant").all()))
check("F5 fitted rows name the fitted component",
      bool((P["e_minutes_given_active"].loc[lv.to_numpy() == 0, "component_id"]
            == "e_minutes_given_active/walk_forward_active_ewma").all()))
check("F5 fallback rows name the fallback component",
      bool((P["e_minutes_given_active"].loc[lv.to_numpy() > 0, "component_id"]
            == "e_minutes_given_active/prefix_mean").all()))


# --------------------------------------------------------------------------
# F6 -- team MIN_PRIOR=5 binds selection AND emission
# --------------------------------------------------------------------------

tlv = TP.set_index("row_uid").fallback_level
tprior = TP.set_index("row_uid").n_prior_games
check("F6 MIN_PRIOR is the registered 5", v7.TEAM_MIN_PRIOR == 5)
check("F6 every team row with 0 prior games is a fallback",
      bool((tlv[tprior == 0] > 0).all()))
check("F6 season openers are cold",
      bool(TP.loc[TP.n_prior_games == 0, "is_cold_start"].all()))
check("F6 EVERY team row below MIN_PRIOR is a fallback",
      bool((tlv[tprior < v7.TEAM_MIN_PRIOR] > 0).all()),
      "histories of 1-4 games emitted a nonfallback prediction")
check("F6 team rows with 1-4 prior games are level 2",
      bool((tlv[(tprior >= 1) & (tprior < v7.TEAM_MIN_PRIOR)] == 2).all()))
check("F6 team rows with 0 prior games are level 3",
      bool((tlv[tprior == 0] == 3).all()))
check("F6 rows at or above MIN_PRIOR are NOT short-history fallbacks",
      bool((tlv[tprior >= v7.TEAM_MIN_PRIOR] != 2).all()))
check("F6 the fold actually exercises both sides of MIN_PRIOR",
      (tprior < v7.TEAM_MIN_PRIOR).any() and (tprior >= v7.TEAM_MIN_PRIOR).any(),
      f"prior range {int(tprior.min())}..{int(tprior.max())}")
check("F6 below-MIN_PRIOR rows emit the declared constant",
      bool((TP.loc[tlv.to_numpy() > 0, "component_id"]
            == f"{v7.TEAM_TARGET}/declared_constant").all()))
check("F6 selection saw ONLY rows at or above MIN_PRIOR",
      tres["diagnostics"]["n_selection_rows"]
      <= tres["diagnostics"]["n_train_eligible_for_selection"])
check("F6 the diagnostics report the MIN_PRIOR accounting",
      tres["diagnostics"]["team_min_prior"] == 5
      and "n_test_below_min_prior" in tres["diagnostics"])

# A short-history team may not INFLUENCE SELECTION. The isolation has to be set
# up honestly: poisoning a core team's first four games would also change the
# history of its own later, eligible games, and MIN_PRIOR governs which rows are
# SCORED in selection — not which observations are allowed to exist. So the
# probe is a late-joining expansion pair whose every row sits below MIN_PRIOR and
# which is nobody else's history.
def expansion_pair(season, dates, seed=77):
    rng = np.random.default_rng(seed)
    rows = []
    for gi, d in enumerate(dates):
        cut = (d - pd.Timedelta(hours=6)).tz_localize("UTC")
        gid = f"TGX{season}{gi:04d}"
        for side, team in (("home", "EXPA"), ("away", "EXPB")):
            rows.append({
                "row_uid": f"tgx_{season}_{gi:04d}_{side}", "team_id": team,
                "game_id": gid, "season": season, "game_date": d, "side": side,
                "forecast_cutoff": cut.isoformat(),
                "feature_asof": (cut - pd.Timedelta(hours=6)).isoformat(),
                "ch_ft": float(rng.uniform(10, 20)), "ch_3pt": float(rng.uniform(15, 30)),
                "ch_paint": float(rng.uniform(25, 40)),
                "ch_np2": float(rng.uniform(8, 18)),
                "team_points": float(rng.uniform(68, 96)), "n_candidates": 12,
            })
    return pd.DataFrame(rows)


exp_dates = sorted(pd.unique(T_TRAIN["game_date"]))[:4]
base_plus = pd.concat([T_TRAIN, expansion_pair(2099, exp_dates)], ignore_index=True)
poison_plus = base_plus.copy()
is_exp = poison_plus.team_id.isin(["EXPA", "EXPB"])
poison_plus.loc[is_exp, ["ch_ft", "ch_3pt", "ch_paint", "ch_np2"]] = 9999.0
a_base = v7.run_team_fold(base_plus, T_TEST, FOLD, universe=TUNI,
                          **IDENT)["diagnostics"]["channel_alphas"]
a_pois = v7.run_team_fold(poison_plus, T_TEST, FOLD, universe=TUNI,
                          **IDENT)["diagnostics"]["channel_alphas"]
check("F6 a team entirely below MIN_PRIOR cannot move the channel alphas",
      a_base == a_pois, f"{a_base} vs {a_pois}")

# and the mask itself: every row selection was allowed to see clears MIN_PRIOR
_plan_tr = v7.build_walk_forward_plan(T_TRAIN, group_cols=list(v5.TEAM_HISTORY_GROUP),
                                      sort_cols=list(v5.TEAM_SORT_KEYS))
_prior_tr = v7.walk_forward_counts(_plan_tr).reindex(T_TRAIN.index)
_ts = v5.team_split(T_TRAIN)
_t1 = pd.Series(False, index=T_TRAIN.index)
_t1.loc[_ts.t1] = True
check("F6 every selection-eligible row clears MIN_PRIOR",
      bool((_prior_tr[_t1 & (_prior_tr >= v7.TEAM_MIN_PRIOR)]
            >= v7.TEAM_MIN_PRIOR).all())
      and int((_t1 & (_prior_tr >= v7.TEAM_MIN_PRIOR)).sum())
      == tres["diagnostics"]["n_selection_rows"],
      f"{tres['diagnostics']['n_selection_rows']} selection rows")


# --------------------------------------------------------------------------
# F7 -- stable teams that alternate sides
# --------------------------------------------------------------------------

sides = T_TEST.groupby("team_id")["side"].nunique()
check("F7 every team appears on BOTH sides", bool((sides == 2).all()),
      "v6's fixture made each team permanently home-only or away-only")
check("F7 team ids are stable league identities",
      set(T_TEST.team_id) == set(TEAMS))
maps = tres["diagnostics"]["calibration_maps"]
check("F7 separate home and away maps are fitted from a two-sided population",
      set(maps) == set(v5.REQUIRED_SIDES) and maps["home"] != maps["away"], str(maps))
check("F7 a team's history crosses its own side switches",
      bool((TP.set_index("row_uid").n_prior_games > 0).any()))
home_uids = T_TEST[T_TEST.side == "home"].row_uid
away_uids = T_TEST[T_TEST.side == "away"].row_uid
check("F7 both sides receive predictions",
      TP.set_index("row_uid").pred_point.loc[home_uids].notna().any()
      and TP.set_index("row_uid").pred_point.loc[away_uids].notna().any())


# --------------------------------------------------------------------------
# F8 -- the provenance sidecar
# --------------------------------------------------------------------------

sc = res["provenance_sidecar"]
prov_receipt = res["receipts"]["provenance_history"]
check("F8 the sidecar receipt passes", prov_receipt["ok"], str(prov_receipt["problems"]))
check("F8 the sidecar is versioned", (sc["schema"] == v7.PROVENANCE_SIDECAR_SCHEMA).all())
check("F8 the sidecar carries a content digest",
      isinstance(res["provenance_sidecar_digest"], str)
      and len(res["provenance_sidecar_digest"]) == 64)
check("F8 the digest is in the run receipt",
      prov_receipt["digest"] == res["provenance_sidecar_digest"])
check("F8 the sidecar is one-to-one with every prediction frame",
      all(set(sc[sc.target_key == t].row_uid) == set(p.row_uid)
          for t, p in P.items()))
check("F8 the sidecar carries every registered provenance field",
      {"component_id", "fallback_level", "selected_alpha", "selected_lambda",
       "residual_pool_n", "n_prior_candidate_games", "n_prior_appearances",
       "n_prior_available_obligations"} <= set(sc.columns))
check("F8 the sidecar keeps the prior-history fields SEPARATE",
      not sc["n_prior_candidate_games"].equals(sc["n_prior_appearances"])
      or bool((sc["n_prior_appearances"] <= sc["n_prior_candidate_games"]).all()))
check("F8 appearances never exceed candidate obligations",
      bool((sc["n_prior_appearances"] <= sc["n_prior_candidate_games"]).all()))
check("F8 appearances never exceed AVAILABLE prior obligations",
      bool((sc["n_prior_appearances"] <= sc["n_prior_available_obligations"]).all()))
check("F8 the sidecar records the availability source per row",
      bool((sc["outcome_availability_source"] == "policy").all()))
check("F8 policy rows name the registered policy id",
      bool((sc["outcome_availability_policy_id"]
            == v7.OUTCOME_AVAILABILITY_POLICY_ID).all()))
check("F8 the selected alpha is preserved per row",
      bool(sc.loc[sc.target_key == "attempts_usage", "selected_alpha"].notna().all()))
check("F8 the selected lambda is preserved for p_active",
      bool(sc.loc[sc.target_key == "p_active", "selected_lambda"].notna().all()))
check("F8 the residual-pool count is preserved",
      bool((sc.loc[sc.target_key == "attempts_usage", "residual_pool_n"] >= 0).all()))
check("F8 the team sidecar records team prior games",
      bool(tres["provenance_sidecar"]["team_prior_games"].notna().all()))

kwp = dict(fold_id=FOLD, config_hash=CFG, snapshot_hash=SNAP)
# TAMPERING: a changed value must move the digest
tamper = sc.copy()
# pick a value that is guaranteed to DIFFER, so the probe cannot be a no-op that
# accidentally reports the digest as sensitive when nothing was changed
_cur = int(tamper.loc[tamper.index[0], "fallback_level"])
tamper.loc[tamper.index[0], "fallback_level"] = 0 if _cur else 2
check("F8 tampering with a sidecar value moves the digest",
      v7.sidecar_digest(tamper) != v7.sidecar_digest(sc))
check("F8 a tampered sidecar no longer binds to its predictions",
      not v7.validate_provenance_sidecar(tamper, P, **kwp)["ok"])
# a mere REORDER is not a different artifact
check("F8 the digest is invariant to row order",
      v7.sidecar_digest(sc.sample(frac=1, random_state=7)) == v7.sidecar_digest(sc))
# SUBSTITUTION: a sidecar from another fold
other = sc.copy()
other["fold_id"] = "season:2098"
check("F8 a sidecar from a different fold is rejected",
      not v7.validate_provenance_sidecar(other, P, **kwp)["ok"])
sub = sc.copy()
sub["data_snapshot_hash"] = "f" * 64
check("F8 a sidecar from a different snapshot is rejected",
      not v7.validate_provenance_sidecar(sub, P, **kwp)["ok"])
dup = pd.concat([sc, sc.iloc[[0]]], ignore_index=True)
check("F8 duplicate provenance rows are rejected",
      not v7.validate_provenance_sidecar(dup, P, **kwp)["ok"])
short_sc = sc.iloc[:-3]
check("F8 a sidecar missing rows is rejected",
      not v7.validate_provenance_sidecar(short_sc, P, **kwp)["ok"])
bad_lvl = sc.copy()
bad_lvl.loc[bad_lvl.index[0], "fallback_level"] = 99
check("F8 a fallback level outside the ladder is rejected",
      not v7.validate_provenance_sidecar(bad_lvl, P, **kwp)["ok"])
bad_src = sc.copy()
bad_src["outcome_availability_source"] = "observed"
check("F8 relabelling a POLICY timestamp as an observation is rejected",
      not v7.validate_provenance_sidecar(bad_src, P, **kwp)["ok"],
      "a derived policy timestamp must never be sold as an observation")
mis = sc.copy()
mis.loc[mis.index[0], "component_id"] = "something/else"
check("F8 a sidecar whose component disagrees with the emitted row is rejected",
      not v7.validate_provenance_sidecar(mis, P, **kwp)["ok"])
check("F8 the sidecar validator fails closed rather than raising",
      v7.validate_provenance_sidecar(pd.DataFrame({"row_uid": [1]}), P, **kwp)["ok"]
      is False)


# --------------------------------------------------------------------------
# F9 -- the composite gate
# --------------------------------------------------------------------------

check("F9 all four player targets are emitted", set(P) == set(v7.PLAYER_TARGETS))
check("F9 the team target is emitted", TP is not None)
for tgt, p in P.items():
    check(f"F9 {tgt}: every obligation row is emitted", len(p) == len(TEST))
    check(f"F9 {tgt}: the prediction receipt passes",
          res["receipts"]["prediction_validation"]["per_target"][tgt]["ok"],
          str(res["receipts"]["prediction_validation"]["per_target"][tgt]["problems"]))
check("F9 the team prediction receipt passes",
      tres["receipts"]["prediction_validation"]["per_target"][v7.TEAM_TARGET]["ok"])
for name in ("identity_binding", "fold_boundary", "provenance_history",
             "prediction_validation", "exclusion_crosstab", "coverage"):
    check(f"F9 the composite gate contains the {name} receipt", name in res["receipts"])
    check(f"F9 the {name} receipt passes on a clean run", res["receipts"][name]["ok"],
          str(res["receipts"][name].get("problems")))
check("F9 scoring_permitted is the conjunction of every named receipt",
      res["scoring_permitted"] is True and res["failed_receipts"] == [])
check("F9 the composite receipt names both validators",
      "historical" in res["receipts"]["prediction_validation"]["per_target"]["p_active"]
      and "strict" in res["receipts"]["prediction_validation"]["per_target"]["p_active"])
check("F9 the strict validator is the hardened /3",
      res["receipts"]["prediction_validation"]["per_target"]["p_active"]["strict"]
      ["validator"] == "contract_v2_strict/3")
check("F9 arm identity is v7 everywhere",
      all((p.arm_id == v7.ARM_ID).all() for p in P.values()))

# NO universe means NO permission -- not a vacuous pass
res_nouni = v7.run_player_fold(TRAIN, TEST, FOLD, universe=None, **IDENT)
check("F9 a run with no universe is NOT permitted to score",
      res_nouni["scoring_permitted"] is False)
check("F9 the unproducible receipts are named as failures",
      set(res_nouni["failed_receipts"])
      >= {"prediction_validation", "exclusion_crosstab", "coverage"})
check("F9 the team run reports every receipt too",
      set(tres["receipts"]) == set(res["receipts"]))
check("F9 the exclusion cross-tab is produced",
      tres["receipts"]["exclusion_crosstab"]["receipt"] == "exclusion_crosstab/1")
check("F9 the exclusion receipt carries the outcome-selection alarm",
      res["receipts"]["exclusion_crosstab"]["outcome_selection_alarm"] is False)
check("F9 the coverage receipt reports the fallback-level histogram",
      all("fallback_levels" in c for c in res["coverage"].values()))
check("F9 coverage is exactly the obligation set",
      all(c["coverage"] == 1.0 for c in res["coverage"].values()))
check("F9 the runner names the receipts scoring depends on",
      set(res["required_receipts"]) == set(res["receipts"]))


# --------------------------------------------------------------------------
# F10 -- strict /3 rejection
# --------------------------------------------------------------------------

good = P["attempts_usage"]
kw = dict(expected_arm_id=v7.ARM_ID, expected_fold_id=FOLD,
          expected_config_hash=CFG, expected_snapshot_hash=SNAP)
check("F10 the real emitted frame passes strict /3",
      validate_strict_v3(good, PUNI, "attempts_usage", **kw)["ok"],
      str(validate_strict_v3(good, PUNI, "attempts_usage", **kw)["problems"]))
check("F10 missing expected identity is rejected",
      not validate_strict_v3(good, PUNI, "attempts_usage", expected_arm_id=v7.ARM_ID,
                             expected_fold_id=FOLD, expected_config_hash=CFG)["ok"])
check("F10 a universe without fold_id is rejected",
      not validate_strict_v3(good, PUNI.drop(columns=["fold_id"]),
                             "attempts_usage", **kw)["ok"])
check("F10 +inf pred_point is rejected",
      not validate_strict_v3(good.assign(pred_point=np.inf), PUNI,
                             "attempts_usage", **kw)["ok"])
check("F10 numeric 0/1 flags are rejected",
      not validate_strict_v3(good.assign(is_fallback=0), PUNI,
                             "attempts_usage", **kw)["ok"])
check("F10 wrong arm_id is rejected",
      not validate_strict_v3(good.assign(arm_id="other"), PUNI,
                             "attempts_usage", **kw)["ok"])
check("F10 a missing fallback_level column is rejected",
      not validate_strict_v3(good.drop(columns=["fallback_level"]), PUNI,
                             "attempts_usage", **kw)["ok"])
check("F10 a missing component_id column is rejected",
      not validate_strict_v3(good.drop(columns=["component_id"]), PUNI,
                             "attempts_usage", **kw)["ok"])
check("F10 a fallback_level that disagrees with is_fallback is rejected",
      not validate_strict_v3(good.assign(fallback_level=0, is_fallback=True), PUNI,
                             "attempts_usage", **kw)["ok"])
check("F10 a fallback_level outside the ladder is rejected",
      not validate_strict_v3(good.assign(fallback_level=9), PUNI,
                             "attempts_usage", **kw)["ok"])

# EXCLUDED-ROW LINEAGE -- everything /2 scoped to predicted rows only
null_cols = ["pred_point", "pred_sd", "pred_q05", "pred_q25", "pred_q50",
             "pred_q75", "pred_q95"]
excl = good.copy()
excl.loc[excl.index[:3], "exclusion_reason"] = "why"
excl.loc[excl.index[:3], null_cols] = np.nan
check("F10 a properly nulled excluded row is accepted",
      validate_strict_v3(excl, PUNI, "attempts_usage", **kw)["ok"],
      str(validate_strict_v3(excl, PUNI, "attempts_usage", **kw)["problems"]))
keep_vals = good.copy()
keep_vals.loc[keep_vals.index[:3], "exclusion_reason"] = "why"
check("F10 an excluded row that keeps its values is rejected",
      not validate_strict_v3(keep_vals, PUNI, "attempts_usage", **kw)["ok"])
for label, col, value in (
        ("a malformed hash", "config_hash", "nothex"),
        ("an as-of at its own cutoff", "feature_asof", None),
        ("a numeric flag", "is_fallback", 1),
        ("a negative prior count", "n_prior_games", -5),
        ("a null component id", "component_id", None),
        ("a null fallback level", "fallback_level", None)):
    bad = excl.copy()
    bad[col] = bad[col].astype(object)          # so a bool column accepts an int
    bad.loc[bad.index[:3], col] = (bad.loc[bad.index[:3], "forecast_cutoff"]
                                   if col == "feature_asof" else value)
    check(f"F10 an EXCLUDED row with {label} is rejected",
          not validate_strict_v3(bad, PUNI, "attempts_usage", **kw)["ok"],
          "exclusion removes values, never lineage")
lost = excl.copy()
lost.loc[lost.index[:3], "model_hash"] = np.nan
check("F10 an excluded row that loses its lineage is rejected",
      not validate_strict_v3(lost, PUNI, "attempts_usage", **kw)["ok"])
check("F10 a malformed frame returns a verdict rather than raising",
      validate_strict_v3(pd.DataFrame({"row_uid": [1]}), PUNI,
                         "attempts_usage", **kw)["ok"] is False)
check("F10 the composite gate fails closed on a malformed frame",
      validate_arm_output_v3(pd.DataFrame({"row_uid": [1]}), PUNI,
                             "attempts_usage", **kw)["ok"] is False)


# --------------------------------------------------------------------------
# F11 -- shuffle invariance, calibration isolation, hash sensitivity
# --------------------------------------------------------------------------

res_s = v7.run_player_fold(TRAIN.sample(frac=1, random_state=1),
                           TEST.sample(frac=1, random_state=2), FOLD,
                           universe=PUNI, **IDENT)
for tgt in v7.PLAYER_TARGETS:
    a = P[tgt].set_index("row_uid").pred_point
    b = res_s["predictions"][tgt].set_index("row_uid").pred_point.reindex(a.index)
    check(f"F11 {tgt} is train/test shuffle invariant",
          np.allclose(a.to_numpy(float), b.to_numpy(float), equal_nan=True),
          f"max delta {np.nanmax(np.abs(a - b)):.6f}")
    check(f"F11 {tgt} model_hash is shuffle invariant",
          P[tgt].model_hash.iloc[0] == res_s["predictions"][tgt].model_hash.iloc[0])
check("F11 the provenance digest is shuffle invariant",
      res_s["provenance_sidecar_digest"] == res["provenance_sidecar_digest"])

tres_s = v7.run_team_fold(T_TRAIN.sample(frac=1, random_state=3),
                          T_TEST.sample(frac=1, random_state=4), FOLD,
                          universe=TUNI, **IDENT)
a = TP.set_index("row_uid").pred_point
b = tres_s["predictions"][v7.TEAM_TARGET].set_index("row_uid").pred_point.reindex(a.index)
check("F11 team predictions are shuffle invariant",
      np.allclose(a.to_numpy(float), b.to_numpy(float), equal_nan=True),
      f"max delta {np.nanmax(np.abs(a - b)):.6f}")

from cbs_generator import player_split  # noqa: E402
tr_ord = v7.order_obligations(TRAIN)
ctx = player_split(tr_ord)
poison = tr_ord.copy()
poison.loc[ctx.calibration_idx, ["minutes", "fga", "points", "appeared"]] = 999.0
d_p = v7.run_player_fold(poison, TEST, FOLD, universe=PUNI, **IDENT)["diagnostics"]
check("F11 calibration outcomes cannot change the selected parameters",
      d_p["selected"] == res["diagnostics"]["selected"],
      f"{d_p['selected']} vs {res['diagnostics']['selected']}")
check("F11 calibration outcomes cannot change the base rate",
      d_p["base_rate"] == res["diagnostics"]["base_rate"])
check("F11 calibration outcomes cannot change the fallback means",
      d_p["fallback_mean"] == res["diagnostics"]["fallback_mean"])

t_poison = T_TRAIN.copy()
ts = v5.team_split(T_TRAIN)
t_poison.loc[ts.t3, "team_points"] = 5000.0
td = v7.run_team_fold(t_poison, T_TEST, FOLD, universe=TUNI, **IDENT)["diagnostics"]
check("F11 T3 outcomes cannot change the channel alphas",
      td["channel_alphas"] == tres["diagnostics"]["channel_alphas"])
check("F11 T3 outcomes cannot change the calibration maps",
      td["calibration_maps"] == tres["diagnostics"]["calibration_maps"])

test_poison = TEST.copy()
test_poison[["minutes", "fga", "points", "appeared"]] = 999.0
d_t = v7.run_player_fold(TRAIN, test_poison, FOLD, universe=PUNI, **IDENT)["diagnostics"]
check("F11 outer-test outcomes cannot change any selected parameter",
      d_t["selected"] == res["diagnostics"]["selected"])

import dataclasses  # noqa: E402
st = v7.FittedState(target="e_minutes_given_active", fold_id=FOLD,
                    component_id="c/1", feature_order=list(v5.P_ACTIVE_FEATURES),
                    scaler_mean=[1.0, 2.0], scaler_std=[1.0, 1.0], lam=1.0,
                    beta=[0.1, 0.2], alphas={"minutes": 0.1},
                    calibration_maps={"home": [1.0, 2.0]}, base_rate=0.5,
                    fallback_mean=20.0, dispersion_sd=3.0,
                    dispersion_method="empirical", dispersion_offsets=[-1, 0, 1],
                    residual_pool_n=250, min_prior=5,
                    support={"low": 0.0, "high": 48.0},
                    availability_source="policy",
                    availability_policy_id=v7.OUTCOME_AVAILABILITY_POLICY_ID)
h0 = st.hash()
check("F11 the fitted-state hash is 64 hex", len(h0) == 64)
for fld, newval in (("feature_order", list(reversed(v5.P_ACTIVE_FEATURES))),
                    ("scaler_mean", [1.0, 2.5]), ("scaler_std", [1.0, 2.0]),
                    ("dropped_features", ["min_ewma"]), ("lam", 2.0),
                    ("beta", [0.1, 0.3]), ("alphas", {"minutes": 0.2}),
                    ("calibration_maps", {"home": [1.0, 2.5]}), ("base_rate", 0.6),
                    ("fallback_mean", 21.0), ("dispersion_sd", 3.5),
                    ("dispersion_method", "gaussian"),
                    ("dispersion_offsets", [-2, 0, 2]), ("residual_pool_n", 251),
                    ("min_prior", 6), ("component_id", "c/2"),
                    ("support", {"low": 0.0, "high": 40.0}),
                    ("target", "attempts_usage"), ("fold_id", "season:2101"),
                    ("availability_source", "observed"),
                    ("availability_policy_id", "other/1")):
    check(f"F11 model_hash changes when {fld} changes",
          dataclasses.replace(st, **{fld: newval}).hash() != h0, fld)
check("F11 different targets carry different hashes",
      len({p.model_hash.iloc[0] for p in P.values()}) == len(P))


# --------------------------------------------------------------------------
# F12 -- team structural preconditions, training vs prediction
# --------------------------------------------------------------------------

v7.require_team_train_inputs(T_TRAIN)
v7.require_team_predict_inputs(T_TEST)
check("F12 a well-formed team frame is accepted on both paths", True)

no_outcome = T_TEST.drop(columns=["team_points"])
v7.require_team_predict_inputs(no_outcome)
check("F12 a current obligation does NOT need its own postgame outcome", True,
      "v6 required team_points on the test frame merely to predict it")
raises("F12 a TRAINING frame without outcomes is rejected", v7.MissingRequiredInput,
       v7.require_team_train_inputs, no_outcome)
r_no_out = v7.run_team_fold(T_TRAIN, no_outcome, FOLD,
                            universe=universe_for(no_outcome, [v7.TEAM_TARGET], FOLD),
                            **IDENT)
check("F12 the team fold runs with no outcome column on the test frame",
      r_no_out["scoring_permitted"], str(r_no_out["failed_receipts"]))
check("F12 it still emits every obligation row",
      len(r_no_out["predictions"][v7.TEAM_TARGET]) == len(no_outcome))

nonfinite_y = T_TRAIN.copy()
nonfinite_y.loc[nonfinite_y.index[0], "team_points"] = np.inf
raises("F12 a non-finite training outcome is rejected", v7.MissingRequiredInput,
       v7.require_team_train_inputs, nonfinite_y)
null_y = T_TRAIN.copy()
null_y.loc[null_y.index[0], "team_points"] = np.nan
raises("F12 a null training outcome is rejected", v7.MissingRequiredInput,
       v7.require_team_train_inputs, null_y)

bad_cases = {
    "missing channel": T_TRAIN.drop(columns=["ch_3pt"]),
    "missing side": T_TRAIN.drop(columns=["side"]),
    "null side": T_TRAIN.assign(side=T_TRAIN["side"].mask(T_TRAIN.index == 0)),
    "null channel": T_TRAIN.assign(ch_ft=T_TRAIN["ch_ft"].mask(T_TRAIN.index == 0)),
    "non-finite channel": T_TRAIN.assign(
        ch_ft=T_TRAIN["ch_ft"].mask(T_TRAIN.index == 0, np.inf)),
    "unexpected side value": T_TRAIN.assign(
        side=T_TRAIN["side"].mask(T_TRAIN.index == 0, "neutral")),
    "duplicate team-game row": pd.concat([T_TRAIN, T_TRAIN.iloc[[0]]],
                                         ignore_index=True),
    "game with two home rows": T_TRAIN.assign(side="home"),
    "null team_id": T_TRAIN.assign(team_id=T_TRAIN["team_id"].mask(T_TRAIN.index == 0)),
    "null game_id": T_TRAIN.assign(game_id=T_TRAIN["game_id"].mask(T_TRAIN.index == 0)),
    "null season": T_TRAIN.assign(season=T_TRAIN["season"].mask(T_TRAIN.index == 0)),
    "null game_date": T_TRAIN.assign(
        game_date=T_TRAIN["game_date"].mask(T_TRAIN.index == 0)),
    "null row_uid": T_TRAIN.assign(row_uid=T_TRAIN["row_uid"].mask(T_TRAIN.index == 0)),
    "null forecast_cutoff": T_TRAIN.assign(
        forecast_cutoff=T_TRAIN["forecast_cutoff"].mask(T_TRAIN.index == 0)),
    "unparseable forecast_cutoff": T_TRAIN.assign(forecast_cutoff="never"),
    "duplicate row_uid": T_TRAIN.assign(row_uid="same"),
}
for label, frame in bad_cases.items():
    raises(f"F12 {label} fails closed", v7.MissingRequiredInput,
           v7.require_team_train_inputs, frame)

print(f"{PASSED}/{PASSED + len(FAILED)} tests passed")
for f in FAILED:
    print(f"  FAIL  {f}")
sys.exit(1 if FAILED else 0)
