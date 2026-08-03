#!/usr/bin/env python
"""test_cbs_v13.py — the ordering correction, and the eight properties it must have.

The supervisor's ruling (`20260802T232025204Z`) named eight things v13 has to prove. Seven of
them are here and the eighth — a real 2021 player cold-start fold traversing the complete
boundary with zero estimator fits — is in `tests/test_cbs_real_integration_v13.py`, because it
reads real artifacts and this file does not except for the contract table and the registry.

  §2  all 28 real collisions are resolved and NO other obligation count changes
  §3  input shuffling leaves outputs and provenance invariant
  §4  both rows in a dual-team group are emitted and validate against their canonical keys
  §5  equal-cutoff dual-team rows and the lagged history — what holds, and what does NOT
  §6  player history crosses a team change but never a season boundary
  §7  a duplicate even after the full v13 key fails closed BEFORE any fit
  §8  the fork is parity-checked against the LIVE inherited source

Everything fitted here is fitted on synthetic fixtures. Nothing is scored.

Run as a script (this repository has no pytest installed)::

    python tests/test_cbs_v13.py
"""

from __future__ import annotations

import ast
import inspect
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import cbs_generator as gen                     # noqa: E402
import cbs_obligation_key as obk                # noqa: E402
import cbs_obligation_order as order2           # noqa: E402
import cbs_player_runner_v13 as fork            # noqa: E402
import cbs_provenance_v4 as prov4               # noqa: E402
import cbs_v7                                   # noqa: E402
import cbs_v8                                   # noqa: E402
import cbs_v12                                  # noqa: E402
import cbs_v13 as v13                           # noqa: E402
from cbs_identity_v3 import (FRAME_IDENTITY_SCHEMA, REAL_PATH_MODE,  # noqa: E402
                             frames_digest)
from cbs_v7 import SIDECAR_COLS                 # noqa: E402

REGISTRY = REPO / "experiments" / "registry.jsonl"
_n = 0


def ok(cond, label):
    global _n
    _n += 1
    if not cond:
        print(f"  FAIL {label}")
        raise SystemExit(1)
    print(f"  ok   {label}")


def raises(fn, label, contains=None, exc=Exception):
    global _n
    _n += 1
    try:
        fn()
    except exc as e:                                             # noqa: BLE001
        if contains and contains.lower() not in str(e).lower():
            print(f"  FAIL {label} -- raised but message lacked {contains!r}: {e}")
            raise SystemExit(1)
        print(f"  ok   {label}")
        return
    print(f"  FAIL {label} -- did not raise")
    raise SystemExit(1)


# =========================================================================== #
print("\n1. registration, append-only, and the ordering component it names")
# =========================================================================== #
recs = [json.loads(ln) for ln in REGISTRY.read_text(encoding="utf-8").splitlines() if ln.strip()]
ids = [r.get("experiment_id") for r in recs]
V13_INDEX = 93

ok(len(recs) >= 94, f"registry holds at least the 94 records v13 registered (got {len(recs)})")
ok(ids[V13_INDEX] == "contract_baseline_suite_v13", "v13's record sits at its registered index")
ok(ids.count("contract_baseline_suite_v13") == 1, "v13's own record appears exactly once")
ok(ids.count("contract_baseline_suite_v12") == 1, "v12's record is untouched and appears once")
ok(all(ln.strip() for ln in REGISTRY.read_text(encoding="utf-8").splitlines()[:93]),
   "the 93 prior registry lines are still present and non-empty")

REC = recs[V13_INDEX]
FC = REC["extra"]["frozen_config"]
ok(v13.recompute_registered_config_hash() == v13.REGISTERED_CONFIG_HASH,
   "v13's registered config hash recomputes from the registry")
for mod in (cbs_v12, cbs_v8):
    got = mod.recompute_registered_config_hash(experiment_id=mod.ARM_ID)
    ok(got == mod.REGISTERED_CONFIG_HASH,
       f"{mod.ARM_ID}'s config hash still recomputes despite the appended record")
ok(v13.REGISTERED_CONFIG_HASH != cbs_v12.REGISTERED_CONFIG_HASH,
   "v12 and v13 are different registered configurations")
ok(REC["primary_metric"].endswith("NOT_YET_COMPUTED"),
   "v13's primary_metric is explicitly NOT_YET_COMPUTED")
ok(FC["row_universe"] == "prediction_contract_v4" and FC["row_universe_unchanged"] is True,
   "v13 consumes prediction_contract_v4 unchanged -- it corrects an ordering, not a contract")
ok(FC["cbs_generator_left_immutable"] and FC["cbs_v8_left_immutable"]
   and FC["v12_left_immutable"] and FC["no_globals_were_monkey_patched"],
   "the registration declares the inherited modules immutable and unpatched")
ok(order2.ORDER_ID == "cbs_obligation_order/2" == FC["obligation_order"]["id"],
   "the registered ordering component is cbs_obligation_order/2")
ok(list(order2.ORDER_KEY) == FC["obligation_order"]["order_key"]
   == ["player_id", "season", "forecast_cutoff", "game_id", "team_id", "row_uid"],
   "the registered order key is the inherited key plus team_id plus row_uid")
ok(order2.TIE_BREAKER == "row_uid" and order2.ORDER_KEY[-1] == "row_uid",
   "the canonical obligation key is the TERMINAL tie-breaker, so the order is total")
ok(tuple(order2.INHERITED_KEY) == tuple(order2.ORDER_KEY[:4])
   == tuple(cbs_v7.PLAYER_SORT_KEYS if hasattr(cbs_v7, "PLAYER_SORT_KEYS")
            else order2.INHERITED_KEY),
   "and it is an EXTENSION of the inherited key, not a different key")


# =========================================================================== #
print("\n2. all 28 real collisions resolved, and no other obligation count changes")
# =========================================================================== #
PG = pd.read_parquet(REPO / prov4.PLAYER_GAME)
IK, OK_ = list(order2.INHERITED_KEY), list(order2.ORDER_KEY)

ok(len(PG) == 35627 and PG["row_uid"].is_unique,
   f"the contract is the registered 35,627-obligation universe (got {len(PG)})")
n_inherited = int(PG.duplicated(subset=IK, keep=False).sum())
n_groups = int(PG.loc[PG.duplicated(subset=IK, keep=False)].groupby(IK).ngroups)
n_full = int(PG.duplicated(subset=OK_, keep=False).sum())
ok(n_inherited == 28, f"the inherited key cannot name 28 obligations (got {n_inherited})")
ok(n_groups == 14, f"in 14 groups (got {n_groups})")
ok(n_full == 0, f"the full v13 key names every one of them (got {n_full} still colliding)")

ordered = order2.order_obligations_v2(PG, where="contract")
ok(len(ordered) == len(PG), "ordering adds and removes no obligation")
ok(set(ordered["row_uid"]) == set(PG["row_uid"]),
   "the row SET is identical -- only the order changed, exactly as with the key in v11")
ok(ordered["row_uid"].is_unique, "and the canonical key is still unique afterwards")

# the relative order of everything /1 could already distinguish is unchanged: /2's key is an
# extension and the sort is stable, so /2's refusal is strictly narrower and never wider
nocol = PG.loc[~PG.duplicated(subset=IK, keep=False)]
a = order2.order_obligations_v2(nocol, where="probe")["row_uid"].tolist()
b = gen.order_obligations(nocol)["row_uid"].tolist()
ok(a == b, "on every frame the inherited order accepted, /2 produces the IDENTICAL order")
refused, why = order2.inherited_would_refuse(PG)
ok(refused and "indistinguishable" in why,
   "and the inherited order really does refuse the full contract, measured not assumed")

BY_SEASON = {int(s): int(v) for s, v in
             PG.loc[PG.duplicated(subset=IK, keep=False)].groupby("season").size().items()}
ok(sorted(BY_SEASON) == [2021, 2022, 2023, 2024, 2025, 2026],
   f"every season was affected, so no player fold could run at all (got {BY_SEASON})")
ok(set(PG.loc[PG.duplicated(subset=IK, keep=False), "row_uid"])
   == set(PG.loc[PG["player_game_uid"].duplicated(keep=False), "row_uid"]),
   "they are exactly the rows sharing a legacy player_game_uid")
ok(FC["what_v13_closes"]["1_the_player_path_opens"]["measured"]
   == {"collisions_under_the_inherited_key": 28, "groups": 14,
       "collisions_under_the_full_v13_key": 0, "obligations_added_or_removed": 0,
       "row_set_unchanged": True},
   "and the registration records exactly those numbers")


# =========================================================================== #
print("\n3. fixtures: a nondegenerate synthetic fold that carries a real-shaped collision")
# =========================================================================== #
DERIVED = {"p_plays_prior", "player_gp_season"}
SUPPLIED = [c for c in gen.P_ACTIVE_FEATURES if c not in DERIVED]
TEAM_A, TEAM_B = 1611661320, 1611661321


def pframe(season, n_players=8, n_dates=40, seed=3, team=TEAM_A, dual_last=False):
    """A synthetic player fold supplying every non-derived Stage-A input.

    `dual_last` appends a SECOND obligation for player 1000 in the final game, registered to the
    other club: the exact shape of the real dual-team collision, at the same cutoff and game.
    """
    rng = np.random.default_rng(seed)
    dates = pd.date_range(f"{season}-05-01", periods=n_dates, freq="D")
    rows = []

    def make(pid, gi, d, tm):
        ap = int(rng.random() < 0.6)
        mn = float(rng.uniform(9, 33)) if ap else 0.0
        cut = (d - pd.Timedelta(hours=6)).tz_localize("UTC")
        game = f"G{season}{gi:04d}"
        r = {"row_uid": obk.row_uid(1000 + pid, game, tm),
             "obligation_key_id": obk.OBLIGATION_KEY_ID,
             "player_id": 1000 + pid, "team_id": tm, "game_id": game,
             "season": season, "game_date": d, "forecast_cutoff": cut.isoformat(),
             "feature_asof": (cut - pd.Timedelta(hours=6)).isoformat(),
             "appeared": ap, "minutes": mn,
             "fga": float(rng.poisson(max(mn, .1) * .35)) if ap else 0.0,
             "points": float(rng.poisson(max(mn, .1) * .45)) if ap else 0.0}
        for k, lag in zip(v13.REQUIRED_PLAYER_FEATURE_SOURCES, (9, 8, 30)):
            r[k] = (cut - pd.Timedelta(hours=lag)).isoformat()
        for c in SUPPLIED:
            r[c] = float(rng.uniform(0, 1))
        r["days_since_last_appearance"] = float(rng.integers(1, 12))
        r["team_gp_season"] = float(gi)
        return r

    for gi, d in enumerate(dates):
        for pid in range(n_players):
            rows.append(make(pid, gi, d, team))
        if dual_last and gi == n_dates - 1:
            rows.append(make(0, gi, d, TEAM_B))
    return pd.DataFrame(rows).reset_index(drop=True)


FOLD = "season:2100"
TRAIN = pframe(2099)
TEST = pframe(2100, seed=9, n_dates=14, dual_last=True)
CFG = v13.SYNTHETIC_CONFIG_HASH

DUAL = TEST[TEST.duplicated(subset=IK, keep=False)]
ok(len(DUAL) == 2 and DUAL["team_id"].nunique() == 2 and DUAL["game_id"].nunique() == 1
   and DUAL["forecast_cutoff"].nunique() == 1,
   "the fixture carries one dual-team pair: same player, game and cutoff, two clubs")
ok(DUAL["row_uid"].is_unique, "with distinct canonical keys")
raises(lambda: gen.order_obligations(TEST),
       "the INHERITED order refuses the fixture, exactly as it refuses the real contract",
       exc=gen.ObligationOrderError, contains="indistinguishable")


def universe_of(test):
    u = pd.DataFrame({"row_uid": test.row_uid, "obligation_key_id": obk.OBLIGATION_KEY_ID,
                      "player_id": test.player_id, "game_id": test.game_id,
                      "team_id": test.team_id, "fold_id": FOLD,
                      "forecast_cutoff": test.forecast_cutoff,
                      "appeared": test.appeared.astype(bool)})
    for t in v13.PLAYER_TARGETS:
        u[f"prediction_required__{t}"] = True
        u[f"outcome_scoreable__{t}"] = (u["appeared"] if t != "p_active" else True)
    return u


UNI = universe_of(TEST)


def manifest(frames):
    return {"schema": prov4.SNAPSHOT_MANIFEST_SCHEMA,
            "frame_identity_schema": FRAME_IDENTITY_SCHEMA,
            "frame_identity_mode": REAL_PATH_MODE,
            "obligation_key_id": obk.OBLIGATION_KEY_ID,
            "membership_rule_id": prov4.MEMBERSHIP_RULE_ID,
            "roster_binding_id": prov4.ROSTER_BINDING_ID,
            "captured_at": "2100-09-01T00:00:00+00:00",
            "artifacts": {rel: {"sha256": "a" * 64, "bytes": 1}
                          for rel in prov4.CBS_REQUIRED_ARTIFACTS},
            "frames": frames_digest(frames, mode=REAL_PATH_MODE)}


FRAMES = {"train": TRAIN, "test": TEST, "universe": UNI}
MAN = manifest(FRAMES)
SNAP = v13.snapshot_identity(MAN)

RES = v13.run_player_fold(TRAIN, TEST, FOLD, config_hash=CFG, snapshot_hash=SNAP,
                          snapshot_manifest=MAN, universe=UNI)
ok(RES["scoring_permitted"] is True,
   f"the fold passes every v13 receipt (failed={RES['failed_receipts']}, "
   f"inherited={RES['inherited_receipts']})")
ok(RES["diagnostics"]["degenerate"] is False, "the run is NONDEGENERATE")
COMPONENTS = {c for p in RES["predictions"].values() for c in p.component_id.unique()}
ok("p_active/ridge_logistic_stage_a" in COMPONENTS,
   "a Stage-A ridge logistic was fitted and used, so the run reached a model")
ok(RES["obligation_order_id"] == "cbs_obligation_order/2"
   and RES["player_runner_id"] == "cbs_player_runner/13",
   "the run names the ordering component and the forked runner it used")


# ---- BOTH rows of the dual-team group are emitted and validate ------------
DUAL_UIDS = set(DUAL["row_uid"])
for tgt, p in RES["predictions"].items():
    ok(DUAL_UIDS <= set(p["row_uid"]) and int(p["row_uid"].isin(DUAL_UIDS).sum()) == 2,
       f"{tgt}: BOTH obligations of the dual-team group received a forecast")
    ok(p["row_uid"].is_unique, f"{tgt}: no forecast covers two obligations")
ok(RES["receipts"]["prediction_validation"]["ok"],
   "and contract_v4_strict validates them against their canonical keys")
ok(RES["receipts"]["coverage"]["per_target"]["p_active"]["n_covered"] == len(UNI),
   "obligation completeness is exact over the fixture universe")


# =========================================================================== #
print("\n4. input shuffling leaves outputs and provenance invariant")
# =========================================================================== #
SH_TR = TRAIN.sample(frac=1.0, random_state=7).reset_index(drop=True)
SH_TE = TEST.sample(frac=1.0, random_state=11).reset_index(drop=True)
SH_UNI = universe_of(SH_TE)
SH_MAN = manifest({"train": SH_TR, "test": SH_TE, "universe": SH_UNI})
SH = v13.run_player_fold(SH_TR, SH_TE, FOLD, config_hash=CFG,
                         snapshot_hash=v13.snapshot_identity(SH_MAN),
                         snapshot_manifest=SH_MAN, universe=SH_UNI)
ok(SH["scoring_permitted"] is True, "the shuffled fold also passes every receipt")

# The DISCRETE fields and the point forecasts must be BIT-identical: those are the run's
# decisions, and a decision that moves with input order is the pathology the ordering guard
# exists to prevent.
EXACT = ["row_uid", "pred_point", "component_id", "fallback_level", "is_cold_start",
         "n_prior_games", "feature_asof", "model_hash", "exclusion_reason", "target_key"]
for tgt in RES["predictions"]:
    a = RES["predictions"][tgt][EXACT].sort_values("row_uid").reset_index(drop=True)
    b = SH["predictions"][tgt][EXACT].sort_values("row_uid").reset_index(drop=True)
    ok(a.equals(b),
       f"{tgt}: shuffling the input leaves every decision and point forecast BIT-identical")

# One quantity is NOT bit-identical, and saying so is worth more than a tolerance nobody reads.
# `pred_sd` for `e_minutes_given_active` moved by 8.9e-16 — one ULP — because the dispersion is a
# standard deviation over a residual pool that numpy sums in INPUT order. Nothing decided by the
# run depends on it at that magnitude: the fallback ladder, the component and every point
# forecast above are bit-identical. Measured and bounded rather than waved through.
DELTAS = {}
for tgt in RES["predictions"]:
    a = RES["predictions"][tgt].sort_values("row_uid")["pred_sd"].to_numpy(float)
    b = SH["predictions"][tgt].sort_values("row_uid")["pred_sd"].to_numpy(float)
    d = np.abs(a - b)
    DELTAS[tgt] = 0.0 if np.all(np.isnan(d)) else float(np.nanmax(d))
WORST = max(DELTAS.values())
ok(WORST < 1e-12,
   f"pred_sd agrees to floating-point across the shuffle (worst |delta| = {WORST:.3e})")
ok(sum(v > 0 for v in DELTAS.values()) <= 1,
   f"and at most ONE target's dispersion is affected at all: {DELTAS}")
ok(all(np.isclose(RES["predictions"][t].sort_values("row_uid")["pred_sd"].to_numpy(float),
                  SH["predictions"][t].sort_values("row_uid")["pred_sd"].to_numpy(float),
                  rtol=0, atol=1e-12, equal_nan=True).all() for t in RES["predictions"]),
   "every row of every target agrees within one part in 1e12, not merely on average")
sa = RES["provenance_sidecar"][SIDECAR_COLS].sort_values(
    ["target_key", "row_uid"]).reset_index(drop=True)
sb = SH["provenance_sidecar"][SIDECAR_COLS].sort_values(
    ["target_key", "row_uid"]).reset_index(drop=True)
ok(sa.equals(sb), "and the provenance sidecar is identical row for row")
ok(RES["provenance_sidecar_digest"] == SH["provenance_sidecar_digest"],
   "so the sidecar identity is the same string, not merely equal content")
ok(v13.sidecar_identity(RES["provenance_sidecar"])
   == v13.sidecar_identity(SH["provenance_sidecar"]),
   "which is what makes the order-independence claim checkable rather than eyeballed")


# =========================================================================== #
print("\n5. equal-cutoff dual-team rows and the lagged history")
# =========================================================================== #
# What HOLDS, structurally: every availability-gated quantity excludes the sibling, because
# admission is `availability < cutoff` and a row's own outcome may not be available at its own
# cutoff. Asserted on the emitted provenance, not deduced.
SC = RES["provenance_sidecar"]
pair = SC[(SC.row_uid.isin(DUAL_UIDS)) & (SC.target_key == "p_active")]
ok(len(pair) == 2, "both siblings appear in the provenance sidecar")
ok(pair["n_prior_appearances"].nunique() == 1,
   "the siblings agree on n_prior_appearances -- neither counted the other as an appearance")
ok(pair["n_prior_available_obligations"].nunique() == 1,
   "and on n_prior_available_obligations -- neither entered the other's ADMITTED history")

_plan_src = inspect.getsource(cbs_v7.build_walk_forward_plan)
ok("av[prior] < cut[i]" in _plan_src,
   "admission is an explicit availability < cutoff comparison, not a positional prefix")
ok("require_own_outcome_unavailable" in _plan_src,
   "and a row's own outcome is forbidden from being available at its own cutoff, which is why "
   "a same-cutoff sibling can never be admitted")

# What does NOT hold, measured and reported rather than claimed away.
M = RES["receipts"]["obligation_order"]["equal_cutoff_candidate_count"]
ok(M["outcome_leak"] is False,
   "n_prior_candidate_games carries no outcome, so this is not an outcome leak")
ok(M["n_rows_where_positional_exceeds_causal"] >= 1,
   "but the inherited POSITIONAL count does over-count the sibling, and v13 measures it")
ok(pair["n_prior_candidate_games"].nunique() == 2,
   "the two siblings therefore disagree on n_prior_candidate_games by exactly the sort order")
ok(int(pair["n_prior_candidate_games"].max() - pair["n_prior_candidate_games"].min()) == 1,
   "by exactly one")
_pbc = inspect.getsource(cbs_v8._prior_by_cutoff)
ok("by CUTOFF" in _pbc and "av[" not in _pbc,
   "cbs_v8._prior_by_cutoff is documented as by-cutoff and implemented positionally")
ok("11" in json.dumps(FC.get("blockers", {})) or "blocker 11" in json.dumps(FC),
   "and the registration escalates it as blocker 11 rather than asserting the property")


# =========================================================================== #
print("\n6. history crosses a team change but never a season boundary")
# =========================================================================== #
TR_TRADE = pd.concat([pframe(2099, n_players=2, n_dates=6, seed=21, team=TEAM_A),
                      pframe(2099, n_players=2, n_dates=6, seed=22, team=TEAM_B)],
                     ignore_index=True)
TR_TRADE = TR_TRADE.drop_duplicates(subset=["row_uid"]).reset_index(drop=True)
ok(TR_TRADE["team_id"].nunique() == 2,
   "the trade fixture has one player-season spanning two clubs")
ok(order2.require_history_grouping_unchanged(("player_id", "season"))["ok"],
   "history is grouped by (player_id, season)")
raises(lambda: order2.require_history_grouping_unchanged(("player_id", "season", "team_id")),
       "grouping history by team is REFUSED -- it would reset a traded player's history",
       contains="follows a player across a team change")
ok(v13.player_history_grouping_in_use() == ("player_id", "season"),
   "and the grouping the FORK actually uses is read out of its own source AST, not restated")

plan = cbs_v7.build_walk_forward_plan(TR_TRADE, group_cols=["player_id", "season"],
                                      sort_cols=list(order2.ORDER_KEY))
hist = cbs_v8.player_history_walk_forward(TR_TRADE, plan)
merged = TR_TRADE.assign(n_prior=hist["n_prior_candidate_games"].to_numpy())
for pid, g in merged.groupby("player_id"):
    g = g.sort_values(list(order2.ORDER_KEY))
    crossed = g[g["team_id"] == TEAM_B]
    ok(len(crossed) and int(crossed["n_prior"].max()) >= len(g[g["team_id"] == TEAM_A]) - 1,
       f"player {pid}: history CONTINUES across the team change rather than resetting")
    break

TWO_SEASONS = pd.concat([pframe(2099, n_players=1, n_dates=5, seed=31),
                         pframe(2100, n_players=1, n_dates=5, seed=32)], ignore_index=True)
plan2 = cbs_v7.build_walk_forward_plan(TWO_SEASONS, group_cols=["player_id", "season"],
                                       sort_cols=list(order2.ORDER_KEY))
hist2 = cbs_v8.player_history_walk_forward(TWO_SEASONS, plan2)
first_2100 = TWO_SEASONS.assign(n=hist2["n_prior_candidate_games"].to_numpy())
first_2100 = first_2100[first_2100.season == 2100].sort_values(list(order2.ORDER_KEY))
ok(int(first_2100["n"].iloc[0]) == 0,
   "and it RESETS at the season boundary -- the first 2100 obligation has no prior")
ok("team_id" not in order2.HISTORY_GROUP_COLS,
   "team_id is nowhere in the history grouping")


# =========================================================================== #
print("\n7. a duplicate even after the full v13 key fails closed BEFORE any fit")
# =========================================================================== #
def with_no_fits(label, fn):
    global _n
    _n += 1
    calls = {"n": 0}
    saved = {m: (getattr(m, "logistic_fit"), getattr(m, "logistic_predict"))
             for m in (cbs_v8, fork)}

    def counted(inner):
        def f(*a, **k):
            calls["n"] += 1
            return inner(*a, **k)
        return f

    for m, (lf, lp) in saved.items():
        m.logistic_fit, m.logistic_predict = counted(lf), counted(lp)
    try:
        try:
            fn()
        except Exception:                                        # noqa: BLE001
            if calls["n"]:
                print(f"  FAIL {label} -- rejected, but {calls['n']} estimator calls ran first")
                raise SystemExit(1)
            print(f"  ok   {label}")
            return
        print(f"  FAIL {label} -- did not reject")
        raise SystemExit(1)
    finally:
        for m, (lf, lp) in saved.items():
            m.logistic_fit, m.logistic_predict = lf, lp


TRUE_DUP = pd.concat([TEST, TEST.iloc[[0]]], ignore_index=True)
ok(int(TRUE_DUP.duplicated(subset=OK_, keep=False).sum()) == 2,
   "a genuine duplicate ties even under the FULL v13 key")
raises(lambda: order2.assert_total_order(TRUE_DUP, where="probe"),
       "the ordering component refuses it as not totally orderable",
       exc=order2.OrderNotTotal, contains="genuine duplicate")
with_no_fits("and the runner rejects it before any estimator call",
             lambda: v13.run_player_fold(
                 TRAIN, TRUE_DUP, FOLD, config_hash=CFG, snapshot_hash=SNAP,
                 snapshot_manifest=MAN, universe=UNI))

NULL_KEY = TEST.copy()
NULL_KEY["row_uid"] = NULL_KEY["row_uid"].astype(object)
NULL_KEY.loc[NULL_KEY.index[0], "row_uid"] = None
raises(lambda: order2.assert_total_order(NULL_KEY, where="probe"),
       "a null terminal tie-breaker is refused: the order would not be total",
       exc=order2.OrderNotTotal)
raises(lambda: order2.assert_total_order(TEST.drop(columns=["team_id"]), where="probe"),
       "a frame without the discriminator cannot be ordered at all", contains="missing")

# uniqueness is re-checked AFTER sorting, which /1 never did
_src = inspect.getsource(order2.order_obligations_v2)
ok("assert_total_order" in _src, "order_obligations_v2 asserts totality as part of ordering")
ok("after" in inspect.getsource(order2.assert_total_order).lower(),
   "and the check is documented as running on the RESULT, not only the input")


# =========================================================================== #
print("\n8. the fork is parity-checked against the LIVE inherited source")
# =========================================================================== #
A = inspect.getsource(cbs_v8.run_player_fold).splitlines()
B = inspect.getsource(fork.run_player_fold).splitlines()
ok(len(A) == len(B),
   f"the fork has the same number of lines as the inherited runner ({len(A)} vs {len(B)})")
DIFF = [i for i, (x, y) in enumerate(zip(A, B)) if x != y]
ok(DIFF == list(fork.PERMITTED_DIFF_LINES),
   f"and differs on EXACTLY the permitted lines {list(fork.PERMITTED_DIFF_LINES)}, got {DIFF}")
for i in DIFF:
    ok("order_obligations" in A[i] and "order_obligations_v2" in B[i],
       f"line {i}: the difference is the ordering call and nothing else")
ok(all("order_obligations_v2" not in A[i] for i in DIFF),
   "the inherited runner still calls the inherited orderer")
ok("order_obligations_v2" not in "\n".join(A),
   "and knows nothing about the new component")

# nothing else was reimplemented: every modelling name is the same object
for name in ("stage_a_features_v8", "_emit", "_finish", "_provenance_rows",
             "require_registered_identity", "resolve_fold_sources",
             "source_provenance_receipt", "player_history_walk_forward"):
    ok(getattr(fork, name) is getattr(cbs_v8, name),
       f"the fork uses cbs_v8's own {name}, not a copy")
for name in ("logistic_fit", "logistic_predict", "select_alpha_bound", "prefix_mean",
             "player_split", "Standardizer", "DECLARED"):
    ok(getattr(fork, name) is getattr(gen, name),
       f"the fork uses cbs_generator's own {name}, not a copy")

# and no global was rebound to achieve any of it
ok(gen.order_obligations.__module__ == "cbs_generator",
   "cbs_generator.order_obligations is still cbs_generator's own function")
ok("order_obligations" in inspect.getsource(cbs_v8.run_player_fold),
   "cbs_v8.run_player_fold is byte-untouched and still calls it")
_v13src = (REPO / "cbs_v13.py").read_text(encoding="utf-8")
for patch in ("cbs_v8.order_obligations =", "gen.order_obligations =",
              "setattr(cbs_v8", "setattr(cbs_generator"):
    ok(patch not in _v13src, f"v13 does not monkey-patch: no {patch!r}")


# =========================================================================== #
print("\n9. the fit boundary is v12's, called rather than copied, and still fail-closed")
# =========================================================================== #
for name in ("snapshot_identity", "require_canonical_keys", "require_fold_frame_map",
             "require_real_sources", "require_team_universe_key",
             "build_legacy_identity_shim", "sidecar_identity"):
    ok(getattr(v13, name) is getattr(cbs_v12, name),
       f"v13 calls v12's accepted {name} rather than copying it")
R = RES["receipts"]
for name in v13.V13_REQUIRED_RECEIPTS:
    ok(R[name].get("recomputed_by") == v13.ARM_ID,
       f"the {name} receipt was recomputed by v13, not inherited")
ok(R["source_provenance"]["computed_by_clause_set"] == "cbs_v12.require_real_sources",
   "and the source receipt records BOTH that v13 owns it and that v12's clauses computed it")
ok(R["identity_binding"]["receipt"] == "identity_binding/6"
   and R["provenance_history"]["receipt"] == "provenance_history/3"
   and R["prediction_validation"]["receipt"] == "prediction_validation/4",
   "the v13 receipt ids are v13's own")
ok(R["receipt_authorship"]["ok"] and not R["receipt_authorship"]["inherited_required_receipts"],
   "the authorship receipt confirms no required receipt was inherited")
ok(RES["inner_receipts"]["identity_binding"]["config_hash"] == cbs_v8.SYNTHETIC_CONFIG_HASH,
   "the inner receipt still describes the legacy synthetic identity, retained for audit")

with_no_fits("a mutated frame against a reused manifest still rejects before any fit",
             lambda: v13.run_player_fold(
                 TRAIN, TEST.assign(min_ewma=TEST.min_ewma + 1.0), FOLD, config_hash=CFG,
                 snapshot_hash=SNAP, snapshot_manifest=MAN, universe=UNI))
with_no_fits("a caller cannot re-enable declared Stage-A defaults",
             lambda: v13.run_player_fold(
                 TRAIN, TEST, FOLD, config_hash=CFG, snapshot_hash=SNAP,
                 snapshot_manifest=MAN, universe=UNI, allow_declared_defaults=True))
with_no_fits("a wrong config digest still rejects before any fit",
             lambda: v13.run_player_fold(
                 TRAIN, TEST, FOLD, config_hash="c" * 64, snapshot_hash=SNAP,
                 snapshot_manifest=MAN, universe=UNI))
raises(lambda: v13.require_registered_identity(
    v13.REGISTERED_CONFIG_HASH, SNAP, MAN, frames=FRAMES, synthetic=False),
    "a real run without artifact_root is refused", contains="artifact_root")


# =========================================================================== #
print("\n10. the arm scores nothing")
# =========================================================================== #
BANNED_CALLS = {"fit_transform", "predict_proba", "score", "roc_auc_score", "log_loss",
                "brier_score_loss", "accuracy_score", "mean_squared_error"}
BANNED_IMPORTS = {"sklearn", "catboost", "lightgbm", "xgboost", "tabpfn", "statsmodels"}
for mod_path in ("cbs_v13.py", "cbs_obligation_order.py"):
    tree = ast.parse((REPO / mod_path).read_text(encoding="utf-8"))
    called, imported = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            called.add(f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", ""))
        elif isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    ok(not (called & BANNED_CALLS), f"{mod_path} calls no scoring method")
    ok(not (imported & BANNED_IMPORTS), f"{mod_path} imports no estimator library")
ok("No real MODEL" in FC["evidence_label"] or "NO REAL FITTED PLAYER OUTPUT" in
   FC["evidence_label"], "the registered label states no real fitted player output exists")
ok("OBLIGATION COMPLETENESS" in FC["evidence_label"],
   "and defines coverage as obligation completeness, not accuracy")
ok(FC["no_real_fitted_player_output"] is True, "declared in the frozen config too")
_missing = [f for f in FC["implementation"] if not (REPO / f).exists()]
ok(not _missing, f"every registered implementation file exists (missing: {_missing})")


print(f"\n{_n}/{_n} tests passed")
