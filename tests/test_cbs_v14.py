#!/usr/bin/env python
"""test_cbs_v14.py — the prior-obligation count, and the two accounting claims made true.

The supervisor's ruling (`20260803T002715462Z`) named seven properties the corrected count must
have, and two v13 claims that had to be repaired or withdrawn. All nine are here.

  §2  both members of every equal-cutoff pair receive the SAME prior count, neither counting
      the other — and the 55 positional overcounts disappear, including the 28 collision rows
  §3  the two identified 2022 `p_active` fallback-band decisions are corrected, and no others
  §4  the seam is confined: only the count and its derived flag moved
  §5  relabelling the two team ids cannot change a component or fallback decision, and any
      floating movement is bounded and reported at machine precision
  §6  history still crosses a team change within a season and never crosses a season
  §7  all four targets still emit both canonical obligations and pass strict validation, and a
      full-key duplicate still fails before any estimator call
  §8  the fork is parity-checked at THREE lines against the live inherited source
  §9  the two v13 accounting claims: the order assertion now checks the ordered frame, and
      `row_set_unchanged` now compares row SETS

Everything fitted here is fitted on synthetic fixtures. Nothing is scored.

Run as a script (this repository has no pytest installed)::

    python tests/test_cbs_v14.py
"""

from __future__ import annotations

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
import cbs_obligation_order_v3 as order3        # noqa: E402
import cbs_player_history_v14 as hist14         # noqa: E402
import cbs_player_runner_v13 as fork13          # noqa: E402
import cbs_player_runner_v14 as fork14          # noqa: E402
import cbs_provenance_v4 as prov4               # noqa: E402
import cbs_v7                                   # noqa: E402
import cbs_v8                                   # noqa: E402
import cbs_v12                                  # noqa: E402
import cbs_v13                                  # noqa: E402
import cbs_v14 as v14                           # noqa: E402
from cbs_identity_v3 import (FRAME_IDENTITY_SCHEMA, REAL_PATH_MODE,  # noqa: E402
                             frames_digest)
from cbs_v5 import PLAYER_SORT_KEYS             # noqa: E402
from cbs_v7 import PLAYER_SHORT_HISTORY_MAX, SIDECAR_COLS   # noqa: E402

REGISTRY = REPO / "experiments" / "registry.jsonl"
IK, OK_ = list(order2.INHERITED_KEY), list(order2.ORDER_KEY)
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


def band(n):
    return "none" if n <= 0 else ("short" if n <= PLAYER_SHORT_HISTORY_MAX else "long")


# =========================================================================== #
print("\n1. registration, the erratum, and what each component declares")
# =========================================================================== #
recs = [json.loads(ln) for ln in REGISTRY.read_text(encoding="utf-8").splitlines() if ln.strip()]
ids = [r.get("experiment_id") for r in recs]
V14_INDEX, ERRATUM_INDEX = 95, 94

ok(len(recs) >= 96, f"registry holds at least the 96 records v14 registered (got {len(recs)})")
ok(ids[V14_INDEX] == "contract_baseline_suite_v14", "v14's record sits at its registered index")
ok(ids[ERRATUM_INDEX] == "contract_baseline_suite_v13__erratum_20260803",
   "the v13 erratum immediately precedes it")
ok(ids.count("contract_baseline_suite_v14") == 1, "v14's own record appears exactly once")
ok(ids.count("contract_baseline_suite_v13") == 1, "v13's record is untouched and appears once")
ERR = recs[ERRATUM_INDEX]
ok(ERR["kind"] == "erratum" and ERR["errata_for"] == "contract_baseline_suite_v13"
   and ERR["prior_records_mutated"] is False, "the erratum is kind=erratum and mutates nothing")
ok(len(ERR["corrections"]) == 6,
   f"the erratum records all six items (got {len(ERR['corrections'])})")

REC = recs[V14_INDEX]
FC = REC["extra"]["frozen_config"]
ok(v14.recompute_registered_config_hash() == v14.REGISTERED_CONFIG_HASH,
   "v14's registered config hash recomputes from the registry")
for mod in (cbs_v13, cbs_v12):
    ok(mod.recompute_registered_config_hash(experiment_id=mod.ARM_ID)
       == mod.REGISTERED_CONFIG_HASH,
       f"{mod.ARM_ID}'s config hash still recomputes despite the appended records")
ok(FC["row_universe_unchanged"] and FC["prediction_contract_v4_left_immutable"]
   and FC["v13_left_immutable"] and FC["cbs_generator_left_immutable"]
   and FC["cbs_v8_left_immutable"] and FC["no_globals_were_monkey_patched"],
   "the registration declares the contract and the inherited modules untouched")

ok(hist14.HISTORY_ID == "cbs_player_history/14" == FC["prior_obligation_count"]["id"],
   "the prior-count component is cbs_player_history/14")
ok("STRICTLY EARLIER" in hist14.COUNT_DEFINITION.upper()
   and "OBLIGATIONS" in hist14.COUNT_DEFINITION.upper(),
   "and defines the count over OBLIGATIONS with a STRICTLY EARLIER cutoff")
ok("not a count of distinct game ids" in hist14.COUNT_DEFINITION.lower(),
   "and says explicitly that it is not a count of distinct game ids")
ok(tuple(hist14.GROUP_COLS) == ("player_id", "season")
   and "team_id" not in hist14.GROUP_COLS,
   "the count is taken within (player_id, season) and is team-blind")
ok(order3.ORDER_ID == "cbs_obligation_order/3" and order3.SUPERSEDES == order2.ORDER_ID,
   "the ordering component is /3 and names /2 as its predecessor")
ok(list(order3.ORDER_KEY) == list(order2.ORDER_KEY),
   "/3 keeps /2's order key exactly -- only the self-checks changed")


# =========================================================================== #
print("\n2. equal-cutoff pairs agree, and the positional overcounts disappear")
# =========================================================================== #
PG = pd.read_parquet(REPO / prov4.PLAYER_GAME)
ok(len(PG) == 35627 and PG["row_uid"].is_unique, "the contract is the registered universe")

# the whole contract, treated as one grouped population: positional vs strict-cutoff
d = PG.sort_values(OK_, kind="mergesort").reset_index(drop=True)
d["_cut"] = pd.to_datetime(d["forecast_cutoff"], utc=True)
positional = d.groupby(["player_id", "season"]).cumcount().to_numpy()
causal = np.empty(len(d), dtype=int)
for _, g in d.groupby(["player_id", "season"], sort=False):
    c = g["_cut"].to_numpy()
    causal[g.index.to_numpy()] = np.searchsorted(np.sort(c), c, side="left")
d["pos"], d["new"] = positional, causal

n_over = int((d["pos"] != d["new"]).sum())
ok(n_over == 55, f"the positional prefix overcounts exactly 55 contract rows (got {n_over})")
ok(bool((d["new"] <= d["pos"]).all()),
   "and never undercounts: a strictly-earlier cutoff is a subset of an earlier position")
COLL = set(PG.loc[PG.duplicated(subset=IK, keep=False), "row_uid"])
ok(len(COLL) == 28, "the 28 collision rows are the ones the inherited ordering could not name")

# The 55 decompose into TWO phenomena, and only one of them was ever visible. Stating this
# precisely matters: the ruling described the 55 as "including the 28 collision rows", and the
# truth is narrower in one direction and much wider in the other.
_g = d.groupby(["player_id", "season", "forecast_cutoff"])
d["_gsize"] = _g["row_uid"].transform("size")
d["_ngames"] = _g["game_id"].transform("nunique")
over = d[d["pos"] != d["new"]]

ok(int((d["_gsize"] > 2).sum()) == 0, "every equal-cutoff group has exactly two members")
ok(len(over) == 55 and bool((over["_gsize"] == 2).all()),
   "so the 55 overcounts are exactly one per equal-cutoff group -- the SECOND member")
ok(bool((over["pos"] - over["new"] == 1).all()), "each overcounted by exactly one")

same_game = over[over["_ngames"] == 1]
two_games = over[over["_ngames"] == 2]
ok(len(same_game) == 14,
   f"14 of them are the dual-team collision: one game, two clubs (got {len(same_game)})")
ok(set(same_game["row_uid"]) <= COLL,
   "and every one of those 14 is the second member of one of the 14 refused pairs")
ok(len(two_games) == 41,
   f"the other 41 are a DIFFERENT phenomenon: same player, same cutoff, TWO DIFFERENT GAMES "
   f"(got {len(two_games)})")
ok(not set(two_games["row_uid"]) & COLL,
   "none of those 41 is a collision row")
_pairs = d[(d["_gsize"] == 2) & (d["_ngames"] == 2)]
ok(int(_pairs.duplicated(subset=IK, keep=False).sum()) == 0,
   "the inherited ORDER never refused them -- differing game_id distinguishes them -- so they "
   "were silently miscounted in every earlier arm and nothing blocked them")
ok(sorted(set(two_games["season"])) == [2021, 2022, 2023, 2024, 2025],
   f"they occur in five seasons (got {sorted(set(two_games['season']))})")

# under the correction every equal-cutoff group agrees with itself; under the prefix none did
grp = _g["new"].agg(["size", "nunique"])
ties = grp[grp["size"] > 1]
ok(len(ties) == 55, f"the contract has 55 equal-cutoff groups (got {len(ties)})")
ok(int((ties["nunique"] > 1).sum()) == 0,
   "and EVERY one of them now receives a single shared prior count")
old_grp = _g["pos"].nunique()
ok(int((old_grp > 1).sum()) == 55,
   "whereas under the positional prefix all 55 disagreed with themselves")


# =========================================================================== #
print("\n3. the two identified 2022 fallback-band decisions are corrected, and no others")
# =========================================================================== #
NAMED = {"ob_f2e6b1c4373894ac", "ob_a8c6201e99f29bba"}
d["band_old"], d["band_new"] = d["pos"].map(band), d["new"].map(band)
flip = d[d["band_old"] != d["band_new"]]
ok(len(flip) == 2, f"exactly two obligations change p_active fallback band (got {len(flip)})")
ok(set(flip["row_uid"]) == NAMED,
   f"and they are exactly the two the supervisor named (got {sorted(flip['row_uid'])})")
ok(set(flip["season"]) == {2022}, "both in 2022")
ok(list(flip["band_old"]) == ["long", "long"] and list(flip["band_new"]) == ["short", "short"],
   "each moves from the long band to the short band, because 3 prior became 2")
ok(int(flip["pos"].iloc[0]) == 3 and int(flip["new"].iloc[0]) == 2,
   "3 -> 2, straddling PLAYER_SHORT_HISTORY_MAX")
ok(PLAYER_SHORT_HISTORY_MAX == 2, "which is the registered short-history bound")
# one from each phenomenon -- so the previously invisible kind is not merely cosmetic
ok(sorted(flip["_ngames"]) == [1, 2],
   f"ONE of the two corrected decisions comes from the dual-team collision and the other from "
   f"the two-games-one-cutoff kind nobody had identified (got {sorted(flip['_ngames'])})")
_M = FC["what_v14_closes"]["1_the_prior_count_is_defined_by_cutoff"]
ok(_M["measured_over_the_contract"]
   == {"equal_cutoff_groups": 55, "every_group_has_exactly_two_members": True,
       "rows_corrected": 55, "corrected_by_exactly_one_each": True,
       "p_active_fallback_band_decisions_corrected": 2,
       "corrected_row_uids": sorted(NAMED), "season": 2022,
       "rows_where_the_corrected_count_exceeds_the_positional_one": 0},
   "and the registration records exactly those numbers")
_D = _M["the_55_decompose_into_two_phenomena"]
ok(_D["dual_team_one_game"]["groups"] == 14
   and _D["two_games_one_cutoff"]["groups"] == 41
   and _D["two_games_one_cutoff"]["visible_before"] is False,
   "and registers the decomposition, including that 41 of them were never visible")


# =========================================================================== #
print("\n4. fixtures, and the seam is confined to two columns")
# =========================================================================== #
DERIVED = {"p_plays_prior", "player_gp_season"}
SUPPLIED = [c for c in gen.P_ACTIVE_FEATURES if c not in DERIVED]
TEAM_A, TEAM_B = 1611661320, 1611661321


def pframe(season, n_players=8, n_dates=40, seed=3, team=TEAM_A, dual_last=False):
    rng = np.random.default_rng(seed)
    dates = pd.date_range(f"{season}-05-01", periods=n_dates, freq="D")
    rows = []

    def mk(pid, gi, d_, tm):
        ap = int(rng.random() < 0.6)
        mn = float(rng.uniform(9, 33)) if ap else 0.0
        cut = (d_ - pd.Timedelta(hours=6)).tz_localize("UTC")
        game = f"G{season}{gi:04d}"
        r = {"row_uid": obk.row_uid(1000 + pid, game, tm),
             "obligation_key_id": obk.OBLIGATION_KEY_ID,
             "player_id": 1000 + pid, "team_id": tm, "game_id": game,
             "season": season, "game_date": d_, "forecast_cutoff": cut.isoformat(),
             "feature_asof": (cut - pd.Timedelta(hours=6)).isoformat(),
             "appeared": ap, "minutes": mn,
             "fga": float(rng.poisson(max(mn, .1) * .35)) if ap else 0.0,
             "points": float(rng.poisson(max(mn, .1) * .45)) if ap else 0.0}
        for k, lag in zip(v14.REQUIRED_PLAYER_FEATURE_SOURCES, (9, 8, 30)):
            r[k] = (cut - pd.Timedelta(hours=lag)).isoformat()
        for c in SUPPLIED:
            r[c] = float(rng.uniform(0, 1))
        r["days_since_last_appearance"] = float(rng.integers(1, 12))
        r["team_gp_season"] = float(gi)
        return r

    for gi, d_ in enumerate(dates):
        for pid in range(n_players):
            rows.append(mk(pid, gi, d_, team))
        if dual_last and gi == n_dates - 1:
            rows.append(mk(0, gi, d_, TEAM_B))
    return pd.DataFrame(rows).reset_index(drop=True)


FOLD = "season:2100"
TRAIN = pframe(2099)
TEST = pframe(2100, seed=9, n_dates=14, dual_last=True)
CFG = v14.SYNTHETIC_CONFIG_HASH
DUAL = TEST[TEST.duplicated(subset=IK, keep=False)]
DUAL_UIDS = set(DUAL["row_uid"])
ok(len(DUAL) == 2 and DUAL["team_id"].nunique() == 2,
   "the fixture carries one dual-team pair at one cutoff")

_comb = cbs_v7.combine_history_frames(TRAIN, TEST)
_plan = cbs_v7.build_walk_forward_plan(_comb, group_cols=list(hist14.GROUP_COLS),
                                       sort_cols=list(PLAYER_SORT_KEYS))
SEAM = hist14.assert_only_the_count_moved(_comb, _plan)
ok(SEAM["ok"] and SEAM["replaced_columns"] == list(hist14.REPLACED_COLUMNS),
   "only n_prior_candidate_games and its derived flag are replaced")
for col in ("n_prior_available_obligations", "n_prior_appearances", "p_plays_prior",
            "has_prior_appearance", "has_prior_available_obligation"):
    ok(col in SEAM["columns_unchanged"],
       f"the availability-gated {col} is the inherited value, untouched")
ok(SEAM["n_rows_corrected"] >= 1 and SEAM["max_overcount"] == 1,
   f"the fixture's sibling was overcounted by exactly one ({SEAM['n_rows_corrected']} rows)")
AGREE = hist14.equal_cutoff_agreement(_comb, _plan)
ok(AGREE["ok"] and AGREE["n_groups_whose_members_disagree"] == 0,
   "and every equal-cutoff group in the fixture now agrees with itself")


def universe_of(test):
    u = pd.DataFrame({"row_uid": test.row_uid, "obligation_key_id": obk.OBLIGATION_KEY_ID,
                      "player_id": test.player_id, "game_id": test.game_id,
                      "team_id": test.team_id, "fold_id": FOLD,
                      "forecast_cutoff": test.forecast_cutoff,
                      "appeared": test.appeared.astype(bool)})
    for t in v14.PLAYER_TARGETS:
        u[f"prediction_required__{t}"] = True
        u[f"outcome_scoreable__{t}"] = (u["appeared"] if t != "p_active" else True)
    return u


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


UNI = universe_of(TEST)
MAN = manifest({"train": TRAIN, "test": TEST, "universe": UNI})
SNAP = v14.snapshot_identity(MAN)
RES = v14.run_player_fold(TRAIN, TEST, FOLD, config_hash=CFG, snapshot_hash=SNAP,
                          snapshot_manifest=MAN, universe=UNI)
ok(RES["scoring_permitted"] is True,
   f"the fold passes every v14 receipt (failed={RES['failed_receipts']}, "
   f"inherited={RES['inherited_receipts']})")
ok(RES["diagnostics"]["degenerate"] is False, "the run is NONDEGENERATE")
ok("p_active/ridge_logistic_stage_a" in
   {c for p in RES["predictions"].values() for c in p.component_id.unique()},
   "a Stage-A ridge logistic was fitted and used")
ok(RES["player_history_id"] == "cbs_player_history/14"
   and RES["obligation_order_id"] == "cbs_obligation_order/3"
   and RES["player_runner_id"] == "cbs_player_runner/14",
   "the run names all three corrected components")

SC = RES["provenance_sidecar"]
PAIR = SC[(SC.row_uid.isin(DUAL_UIDS)) & (SC.target_key == "p_active")]
ok(len(PAIR) == 2 and PAIR["n_prior_candidate_games"].nunique() == 1,
   f"both siblings received the SAME prior count "
   f"({sorted(PAIR['n_prior_candidate_games'].tolist())})")
ok(PAIR["n_prior_appearances"].nunique() == 1
   and PAIR["n_prior_available_obligations"].nunique() == 1,
   "and still agree on every availability-gated quantity, as they did under v13")


# =========================================================================== #
print("\n5. relabelling the two team ids changes no decision")
# =========================================================================== #
SWAP = {TEAM_A: TEAM_B, TEAM_B: TEAM_A}


def relabel(df):
    out = df.copy()
    out["team_id"] = out["team_id"].map(SWAP)
    out["row_uid"] = [obk.row_uid(p, g, t) for p, g, t
                      in zip(out["player_id"], out["game_id"], out["team_id"])]
    return out.reset_index(drop=True)


R_TR, R_TE = relabel(TRAIN), relabel(TEST)
R_UNI = universe_of(R_TE)
R_MAN = manifest({"train": R_TR, "test": R_TE, "universe": R_UNI})
R_RES = v14.run_player_fold(R_TR, R_TE, FOLD, config_hash=CFG,
                            snapshot_hash=v14.snapshot_identity(R_MAN),
                            snapshot_manifest=R_MAN, universe=R_UNI)
ok(R_RES["scoring_permitted"] is True, "the relabelled fold also passes every receipt")

# map emitted rows back to the ORIGINAL obligation via (player_id, game_id, original team)
BACK = {obk.row_uid(p, g, SWAP[t]): obk.row_uid(p, g, t)
        for p, g, t in zip(TEST["player_id"], TEST["game_id"], TEST["team_id"])}
DECISIONS = ["component_id", "fallback_level", "is_cold_start", "n_prior_games"]
for tgt in RES["predictions"]:
    a = RES["predictions"][tgt].set_index("row_uid").sort_index()
    b = R_RES["predictions"][tgt].copy()
    b["row_uid"] = b["row_uid"].map(BACK)
    b = b.set_index("row_uid").sort_index()
    ok(list(a.index) == list(b.index),
       f"{tgt}: relabelling maps back onto exactly the same obligations")
    ok(a[DECISIONS].equals(b[DECISIONS]),
       f"{tgt}: every component and fallback decision is IDENTICAL under relabelling")

FLOAT_COLS = ["pred_point", "pred_sd", "pred_q05", "pred_q50", "pred_q95"]
WORST = 0.0
for tgt in RES["predictions"]:
    a = RES["predictions"][tgt].set_index("row_uid").sort_index()
    b = R_RES["predictions"][tgt].copy()
    b["row_uid"] = b["row_uid"].map(BACK)
    b = b.set_index("row_uid").sort_index()
    for c in FLOAT_COLS:
        if c in a.columns:
            delta = np.abs(a[c].to_numpy(float) - b[c].to_numpy(float))
            if not np.all(np.isnan(delta)):
                WORST = max(WORST, float(np.nanmax(delta)))
ok(WORST < 1e-9,
   f"and every floating output moves by at most {WORST:.3e} -- bounded and reported, "
   f"not asserted equal")
print(f"       (worst floating movement under team relabelling: {WORST:.3e})")


# =========================================================================== #
print("\n6. history crosses a team change within a season, never a season")
# =========================================================================== #
TRADE = pd.concat([pframe(2099, n_players=1, n_dates=6, seed=41, team=TEAM_A),
                   pframe(2099, n_players=1, n_dates=6, seed=42, team=TEAM_B)],
                  ignore_index=True).drop_duplicates(subset=["row_uid"]).reset_index(drop=True)
plan_t = cbs_v7.build_walk_forward_plan(TRADE, group_cols=list(hist14.GROUP_COLS),
                                        sort_cols=list(PLAYER_SORT_KEYS))
h_t = hist14.player_history_v14(TRADE, plan_t)
merged = TRADE.assign(n=h_t["n_prior_candidate_games"].to_numpy()).sort_values(OK_)
after_trade = merged[merged["team_id"] == TEAM_B]
ok(len(after_trade) and int(after_trade["n"].max()) >= 5,
   f"history CONTINUES across the team change (max prior after the trade: "
   f"{int(after_trade['n'].max())})")

TWO = pd.concat([pframe(2099, n_players=1, n_dates=5, seed=51),
                 pframe(2100, n_players=1, n_dates=5, seed=52)], ignore_index=True)
plan_2 = cbs_v7.build_walk_forward_plan(TWO, group_cols=list(hist14.GROUP_COLS),
                                        sort_cols=list(PLAYER_SORT_KEYS))
h_2 = hist14.player_history_v14(TWO, plan_2)
first_new = TWO.assign(n=h_2["n_prior_candidate_games"].to_numpy())
first_new = first_new[first_new.season == 2100].sort_values(OK_)
ok(int(first_new["n"].iloc[0]) == 0,
   "and RESETS at the season boundary -- the first 2100 obligation has no prior")
ok("team_id" not in hist14.GROUP_COLS and "team_id" not in order2.HISTORY_GROUP_COLS,
   "team_id is nowhere in the grouping used by either component")
ok(v14.player_history_grouping_in_use() == ("player_id", "season"),
   "and the grouping the v14 FORK uses is read out of its own source AST")


# =========================================================================== #
print("\n7. both obligations still emitted and validated; a true duplicate still fails")
# =========================================================================== #
for tgt, p in RES["predictions"].items():
    ok(DUAL_UIDS <= set(p["row_uid"]) and int(p["row_uid"].isin(DUAL_UIDS).sum()) == 2,
       f"{tgt}: BOTH canonical obligations of the pair received a forecast")
    ok(p["row_uid"].is_unique, f"{tgt}: one forecast does not cover two obligations")
ok(RES["receipts"]["prediction_validation"]["ok"],
   "contract_v4_strict validates all four targets against their canonical keys")
ok(RES["receipts"]["coverage"]["per_target"]["p_active"]["n_covered"] == len(UNI),
   "obligation completeness is exact")


def with_no_fits(label, fn):
    global _n
    _n += 1
    calls = {"n": 0}
    saved = {m: (m.logistic_fit, m.logistic_predict) for m in (cbs_v8, fork13, fork14)}

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
   "a genuine duplicate ties even under the full key")
raises(lambda: order3.order_obligations_v3(TRUE_DUP, where="probe"),
       "/3 refuses it as not totally orderable", exc=order2.OrderNotTotal,
       contains="genuine duplicate")
with_no_fits("and the v14 runner rejects it before any estimator call",
             lambda: v14.run_player_fold(TRAIN, TRUE_DUP, FOLD, config_hash=CFG,
                                         snapshot_hash=SNAP, snapshot_manifest=MAN,
                                         universe=UNI))
with_no_fits("a caller still cannot re-enable declared Stage-A defaults",
             lambda: v14.run_player_fold(TRAIN, TEST, FOLD, config_hash=CFG,
                                         snapshot_hash=SNAP, snapshot_manifest=MAN,
                                         universe=UNI, allow_declared_defaults=True))
with_no_fits("a mutated frame against a reused manifest still rejects before any fit",
             lambda: v14.run_player_fold(TRAIN, TEST.assign(min_ewma=TEST.min_ewma + 1.0),
                                         FOLD, config_hash=CFG, snapshot_hash=SNAP,
                                         snapshot_manifest=MAN, universe=UNI))
raises(lambda: v14.require_registered_identity(
    v14.REGISTERED_CONFIG_HASH, SNAP, MAN,
    frames={"train": TRAIN, "test": TEST, "universe": UNI}, synthetic=False),
    "a real run without artifact_root is refused", contains="artifact_root")


# =========================================================================== #
print("\n8. the fork is parity-checked at THREE lines against the live source")
# =========================================================================== #
A = inspect.getsource(cbs_v8.run_player_fold).splitlines()
B = inspect.getsource(fork14.run_player_fold).splitlines()
ok(len(A) == len(B), f"the fork has the same line count as the inherited runner ({len(A)})")
DIFF = [i for i, (x, y) in enumerate(zip(A, B)) if x != y]
ok(DIFF == list(fork14.PERMITTED_DIFF_LINES),
   f"and differs on EXACTLY the permitted lines {list(fork14.PERMITTED_DIFF_LINES)}, got {DIFF}")
ok(set(fork14.PERMITTED_DIFF_REASONS) == set(DIFF),
   "every permitted line has a recorded reason")
ok(all("order_obligations" in A[i] for i in (25, 26))
   and "player_history_walk_forward" in A[39],
   "the three inherited lines are the two ordering calls and the history call")
ok("order_obligations_v3" in B[25] and "order_obligations_v3" in B[26]
   and "player_history_v14" in B[39],
   "and the three replacements are /3 ordering and the /14 history")
ok(fork14.SUPERSEDES == "cbs_player_runner/13"
   and len(fork13.PERMITTED_DIFF_LINES) == 2,
   "v14 widened v13's fork from two seams to three, and says so")

for name in ("stage_a_features_v8", "_emit", "_finish", "_provenance_rows",
             "require_registered_identity", "resolve_fold_sources",
             "source_provenance_receipt", "player_history_walk_forward"):
    ok(getattr(fork14, name) is getattr(cbs_v8, name),
       f"the fork uses cbs_v8's own {name}, not a copy")
for name in ("logistic_fit", "logistic_predict", "select_alpha_bound", "prefix_mean",
             "player_split", "Standardizer", "DECLARED"):
    ok(getattr(fork14, name) is getattr(gen, name),
       f"the fork uses cbs_generator's own {name}, not a copy")
ok(fork14.build_walk_forward_plan is cbs_v7.build_walk_forward_plan,
   "the walk-forward PLAN is still the inherited one -- the seam is the history frame")
_v14src = (REPO / "cbs_v14.py").read_text(encoding="utf-8")
for patch in ("cbs_v8.player_history_walk_forward =", "cbs_v8.order_obligations =",
              "setattr(cbs_v8", "setattr(cbs_generator", "gen.order_obligations ="):
    ok(patch not in _v14src, f"v14 does not monkey-patch: no {patch!r}")


# =========================================================================== #
print("\n9. the two v13 accounting claims, now true")
# =========================================================================== #
# (a) the order assertion checks the ORDERED frame, and the check is behavioural not textual
_v2src = inspect.getsource(order2.order_obligations_v2)
_v3src = inspect.getsource(order3.order_obligations_v3)
ok(_v2src.index("assert_total_order") < _v2src.index("sort_values"),
   "v13's /2 really did assert BEFORE sorting -- the defect is real, not misread")
ok(_v3src.index("sort_values") < _v3src.index("assert_total_order"),
   "/3 sorts first and then asserts")

_seen = {"n": 0, "frames": []}
_real_assert = order3.assert_total_order


def _spy(df, *, where="frame"):
    _seen["n"] += 1
    _seen["frames"].append(df.reset_index(drop=True).copy())
    return _real_assert(df, where=where)


order3.assert_total_order = _spy
try:
    _shuffled = TEST.sample(frac=1.0, random_state=3).reset_index(drop=True)
    _out = order3.order_obligations_v3(_shuffled, where="probe")
finally:
    order3.assert_total_order = _real_assert
ok(_seen["n"] == 1, "ordering asserts exactly once")
ok(_seen["frames"][0]["row_uid"].tolist() == _out["row_uid"].tolist(),
   "and the frame it asserted on IS the frame it returned -- checked by observing the call, "
   "not by reading a docstring")
ok(_seen["frames"][0]["row_uid"].tolist() != _shuffled["row_uid"].tolist(),
   "which is a different frame from the input, so the test can actually distinguish them")

# (b) row_set_unchanged compares SETS
_before = TEST
_after_ok = order3.order_obligations_v3(TEST, where="probe")
_rec_ok = order3.order_receipt_v3(_before, _after_ok, role="test")
ok(_rec_ok["row_set_unchanged"] is True
   and _rec_ok["row_set_comparison"]["compared_on"] == "row_uid",
   "a genuine reordering reports row_set_unchanged=True, compared on the canonical key")

_swapped = _after_ok.copy().reset_index(drop=True)
_swapped.loc[0, "row_uid"] = "ob_not_in_the_original_frame"
_rec_bad = order3.order_receipt_v3(_before, _swapped, role="test")
ok(len(_before) == len(_swapped), "the tampered frame has the SAME length as the original")
ok(order2.order_receipt(_before, _swapped, role="test")["row_set_unchanged"] is True,
   "so /2's length check calls it unchanged -- the defect, reproduced")
ok(_rec_bad["row_set_unchanged"] is False,
   "while /3 catches it, because it compares row SETS")
ok(_rec_bad["row_set_comparison"]["n_only_before"] == 1
   and _rec_bad["row_set_comparison"]["n_only_after"] == 1,
   "and reports the symmetric difference in both directions")
ok(_rec_bad["row_count_unchanged"] is True,
   "the count equality is still reported, separately, under its own name")
ok(ERR["corrections"][0]["field"].startswith("cbs_obligation_order.order_obligations_v2")
   and ERR["corrections"][1]["field"].startswith("cbs_obligation_order.order_receipt"),
   "and the erratum records both as corrections against v13")


print(f"\n{_n}/{_n} tests passed")
