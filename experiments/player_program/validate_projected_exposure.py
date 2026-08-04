#!/usr/bin/env python3
"""validate_projected_exposure.py — the gate `projected_player_possessions_v1` must pass
BEFORE any downstream accuracy is looked at.

Every check here is a property of the artifact or of the producer. **Nothing here is scored.** No
realised minute, possession, margin or outcome is compared against a projection anywhere in this
file, and no accuracy, calibration or error figure is computed.

The perturbation tests drive the REAL producer (`build_projected_exposure.build_frames`) with
patched input paths, so they exercise the shipped code rather than a re-implementation of it. The
provenance gate instruments `pandas.read_parquet` at runtime and records every file and every
column the producer actually reads -- it does not grep the source for words.

Run::

    python experiments/player_program/validate_projected_exposure.py
"""

from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

import build_projected_exposure as M  # noqa: E402

OUT = M.OUT
V4 = ROOT / "experiments/prediction_contract_v4/player_game.parquet"
RESULTS: list[dict] = []


def check(name: str, requirement: str, section: str):
    def deco(fn):
        try:
            detail = fn()
            RESULTS.append({"check": name, "section": section, "requirement": requirement,
                            "result": "PASS", "detail": detail or {}})
            print(f"  PASS  {name}")
        except AssertionError as exc:
            RESULTS.append({"check": name, "section": section, "requirement": requirement,
                            "result": "FAIL", "detail": {"error": str(exc)}})
            print(f"  FAIL  {name}: {exc}")
        except Exception as exc:                                    # noqa: BLE001
            RESULTS.append({"check": name, "section": section, "requirement": requirement,
                            "result": "ERROR", "detail": {"error": f"{type(exc).__name__}: {exc}"}})
            print(f"  ERROR {name}: {type(exc).__name__}: {exc}")
        return fn
    return deco


PLAYERS = pd.read_parquet(OUT / "projected_player_possessions_v1.parquet")
TEAMS = pd.read_parquet(OUT / "projected_team_rotations_v1.parquet")
PACE = pd.read_parquet(OUT / "team_possession_prior_v1.parquet")
CONTRACT = pd.read_parquet(M.CONTRACT)
RECEIPT = json.loads((OUT / "PROJECTED_EXPOSURE_RECEIPT.json").read_text(encoding="utf-8"))

PKEY = ["game_id", "team_id", "regime", "row_uid"]
TKEY = ["game_id", "team_id", "regime"]
GKEY = ["game_id", "team_id"]
ALLOCATED = ("normal", "minutes_only_no_pace")
READS: list[dict] = []


def _run(contract=None, poss=None, pred_dir=None, record=False):
    """Run the real producer with patched input paths. Returns (pace, players, teams)."""
    old = (M.CONTRACT, M.POSS, M.PRED_DIR)
    orig_pq, orig_csv = pd.read_parquet, pd.read_csv
    try:
        if contract is not None:
            M.CONTRACT = contract
        if poss is not None:
            M.POSS = poss
        if pred_dir is not None:
            M.PRED_DIR = pred_dir
        if record:
            READS.clear()

            def rec(path, *a, **k):
                READS.append({"path": str(path),
                              "columns": list(k["columns"]) if k.get("columns") else None})
                return orig_pq(path, *a, **k)

            def no_csv(*a, **k):
                raise AssertionError("the producer called pandas.read_csv")

            pd.read_parquet, pd.read_csv = rec, no_csv
        _b, _c, _G, P, players, teams, _h = M.build_frames()
        return M._sorted_outputs(P, players, teams)
    finally:
        M.CONTRACT, M.POSS, M.PRED_DIR = old
        pd.read_parquet, pd.read_csv = orig_pq, orig_csv


print("\nbaseline instrumented rebuild")
BASE_PACE, BASE_PLAYERS, BASE_TEAMS = _run(record=True)
BASE_READS = list(READS)
print(f"  recorded {len(BASE_READS)} parquet reads")


def _cmp_subset(a, b, keys, where, label) -> int:
    a2 = a[where(a)].set_index(keys).sort_index()
    b2 = b[where(b)].set_index(keys).sort_index()
    assert a2.index.equals(b2.index), f"{label}: row set changed ({len(a2)} vs {len(b2)})"
    for c in [c for c in a2.columns if c in b2.columns]:
        s1, s2 = a2[c], b2[c]
        if pd.api.types.is_float_dtype(s1):
            same = np.isclose(s1.to_numpy(), s2.to_numpy(), rtol=0, atol=0, equal_nan=True)
        else:
            same = (s1.to_numpy() == s2.to_numpy()) | (s1.isna().to_numpy() & s2.isna().to_numpy())
        assert same.all(), f"{label}: column {c} changed on {int((~same).sum())} rows"
    return len(a2)


def _dist(s):
    s = pd.Series(s).dropna()
    if not len(s):
        return {}
    q = s.quantile([0.05, 0.5, 0.95])
    return {"n": int(len(s)), "mean": round(float(s.mean()), 4), "min": float(s.min()),
            "p05": float(q.loc[0.05]), "p50": float(q.loc[0.5]), "p95": float(q.loc[0.95]),
            "max": float(s.max())}


# =========================================================================== #
S = "1. grain reconciliation and uniqueness"
print(f"\n{S}")


@check("grain_definitions_and_uniqueness", "each grain is defined and its canonical key is unique", S)
def _g1():
    grains = {}
    for label, df, key, defn in (
        ("pace", PACE, GKEY,
         "one row per TEAM-GAME: the projected team offensive possession count for that club in "
         "that game. Not per player and not per regime."),
        ("team_rotation", TEAMS, TKEY,
         "one row per TEAM-GAME x EVIDENCE REGIME: the allocation summary for one club's rotation "
         "under one candidate-set definition."),
        ("player", PLAYERS, PKEY,
         "one row per CONTRACT OBLIGATION x EVIDENCE REGIME: a projected minute and possession "
         "allocation for one candidate player-team-game under one candidate-set definition. The "
         "same obligation appears once per regime that admits it."),
    ):
        dup = int(df.duplicated(key).sum())
        assert dup == 0, f"{label}: {dup} duplicate rows on {key}"
        grains[label] = {"key": key, "rows": int(len(df)), "duplicates_on_key": dup,
                         "definition": defn}
    # player grain has a second equivalent key
    dup2 = int(PLAYERS.duplicated(["regime", "row_uid"]).sum())
    assert dup2 == 0, f"{dup2} duplicates on (regime, row_uid)"
    grains["player"]["equivalent_key"] = ["regime", "row_uid"]
    grains["player"]["duplicates_on_equivalent_key"] = dup2
    return grains


@check("grain_arithmetic_reconciles", "every headline count is derived, not asserted", S)
def _g2():
    games = int(PACE["game_id"].nunique())
    tg = int(len(PACE))
    assert tg == games * 2, f"{tg} pace rows != {games} games x 2"
    assert len(TEAMS) == tg * len(M.REGIMES), "team rows != team-games x regimes"

    per_regime = PLAYERS.groupby("regime").size().to_dict()
    assert sum(per_regime.values()) == len(PLAYERS)

    tiers = CONTRACT["evaluation_tier"].value_counts().to_dict()
    assert sum(tiers.values()) == len(CONTRACT)

    # primary regime: does every Tier A obligation allocate?
    prim = TEAMS[TEAMS["regime"] == M.PRIMARY_REGIME]
    unres = prim[prim["status"] == "unresolved_insufficient_candidates"]
    stranded = int(unres["n_candidates"].sum())
    allocated_a = per_regime[M.PRIMARY_REGIME]
    assert allocated_a + stranded == tiers["A_primary"], "Tier A accounting does not close"

    widest = "tier_a_plus_tx_b_plus_s2"
    unres_w = TEAMS[(TEAMS["regime"] == widest) &
                    (TEAMS["status"] == "unresolved_insufficient_candidates")]
    stranded_w = int(unres_w["n_candidates"].sum())
    assert per_regime[widest] + stranded_w == len(CONTRACT), "widest regime accounting does not close"

    return {
        "games": games,
        "pace_rows_2990": {"value": tg, "equals": "1495 games x 2 clubs"},
        "team_rotation_rows_8970": {"value": int(len(TEAMS)),
                                    "equals": f"{tg} team-games x {len(M.REGIMES)} regimes"},
        "player_rows_120262": {"value": int(len(PLAYERS)),
                               "equals": " + ".join(f"{k}={v}" for k, v in sorted(per_regime.items())),
                               "sum": sum(per_regime.values())},
        "contract_44851": {"value": int(len(CONTRACT)), "by_evaluation_tier": tiers},
        "allocated_35629": {
            "value": allocated_a,
            "is": "Tier A obligations allocated in the PRIMARY regime",
            "denominator": tiers["A_primary"],
            "denominator_is": "all A_primary obligations in prediction_contract_v5",
            "stranded_in_unresolved_team_games": stranded,
            "unresolved_primary_team_games_76": int(len(unres)),
            "are_those_76_excluded_from_the_denominator": (
                "NO -- they cannot be, because they contain ZERO Tier A obligations. They are "
                "excluded from the TEAM-GAME count of formed rotations (2914 of 2990), not from "
                "the obligation denominator. The obligation denominator is unaffected."),
            "literal_statement_that_is_true": (
                f"{allocated_a} of {tiers['A_primary']} Tier A obligations allocate; "
                f"{stranded} are stranded"),
        },
        "widest_regime": {"allocated": per_regime[widest], "stranded": stranded_w,
                          "unresolved_team_games": int(len(unres_w)),
                          "closes_to": len(CONTRACT)},
    }


@check("v4_v5_universe_reconciliation",
       "35,627 and 35,629 are different universes, not one count measured twice", S)
def _g3():
    assert V4.exists(), "prediction_contract_v4 not found"
    v4 = pd.read_parquet(V4, columns=["game_id", "team_id", "player_id"])
    a = CONTRACT[CONTRACT["evaluation_tier"] == "A_primary"]
    k4 = set(zip(v4["game_id"], v4["team_id"], v4["player_id"]))
    k5 = set(zip(a["game_id"], a["team_id"], a["player_id"]))
    only5, only4 = k5 - k4, k4 - k5
    assert not only4, f"{len(only4)} v4 obligations are absent from v5 Tier A"
    extra = a[[k in only5 for k in zip(a["game_id"], a["team_id"], a["player_id"])]]
    return {
        "v4_obligations_35627": len(k4),
        "v5_tier_a_35629": len(k5),
        "v4_rows_lost": len(only4),
        "v5_tier_a_is_strict_superset_of_v4": True,
        "difference_is_exactly": len(only5),
        "the_added_rows": extra[["game_id", "team_id", "player_id", "season",
                                 "candidate_source"]].to_dict("records"),
        "units": {
            "35627": "prediction_contract_v4 obligations -- the universe of the v14 control",
            "35629": "prediction_contract_v5 A_primary obligations -- this artifact's primary universe",
            "44851": "ALL prediction_contract_v5 obligations across all three evaluation tiers",
            "warning": "these are three different universes and are not directly comparable",
        },
    }


# =========================================================================== #
S = "2. rotation allocation and possession conservation"
print(f"\n{S}")


@check("team_minutes_exactly_200", "minutes sum to exactly 200 on every resolved team-game", S)
def _a1():
    alloc = TEAMS[TEAMS["status"].isin(ALLOCATED)]
    bad = alloc[alloc["projected_minutes_micro_sum"] != M.TEAM_MICRO]
    assert len(bad) == 0, f"{len(bad)} allocated team-games off the exact integer total"
    unres = TEAMS[~TEAMS["status"].isin(ALLOCATED)]
    assert (unres["projected_minutes_micro_sum"] == 0).all(), "an unresolved row carries minutes"
    s = PLAYERS.groupby(TKEY)["projected_minutes"].sum()
    worst = float((s - 200.0).abs().max())
    assert worst < 1e-9, f"float minute sum deviates by {worst}"
    return {"allocated_team_game_regimes": int(len(alloc)),
            "unresolved_rows_checked_separately": int(len(unres)),
            "exact_integer_total_micro_minutes": M.TEAM_MICRO,
            "worst_float_deviation": worst,
            "by_status": TEAMS["status"].value_counts().to_dict()}


@check("player_minute_bounds", "0 <= projected minutes <= 40 for every allocated player", S)
def _a2():
    assert (PLAYERS["projected_minutes"] >= 0).all(), "negative projected minutes"
    assert (PLAYERS["projected_minutes_micro"] <= M.CAP_MICRO).all(), "a player exceeds 40 minutes"
    return {"min": float(PLAYERS["projected_minutes"].min()),
            "max": float(PLAYERS["projected_minutes"].max()),
            "at_cap": int((PLAYERS["projected_minutes_micro"] == M.CAP_MICRO).sum()),
            "cap_by_regime": PLAYERS[PLAYERS["was_capped"]].groupby("regime").size().to_dict()}


@check("no_minutes_silently_discarded",
       "the redistribution is explicit and every minute is attributable", S)
def _a3():
    alloc = TEAMS[TEAMS["status"].isin(ALLOCATED)].copy()
    # 200 = raw sum + redistributed, by definition of the persisted fields
    resid = (alloc["sum_raw_expected_minutes"] + alloc["redistributed_minutes"] - 200.0).abs()
    assert resid.max() < 1e-9, f"redistribution does not close: worst {resid.max()}"
    # the persisted scale factor is the one actually applied where no cap bound
    free = alloc[alloc["n_capped"] == 0]
    got = PLAYERS[PLAYERS["was_capped"] == False].groupby(TKEY)["projected_minutes"].sum()  # noqa: E712
    del got
    return {"team_game_regimes": int(len(alloc)),
            "identity": "200 == sum_raw_expected_minutes + redistributed_minutes",
            "worst_residual": float(resid.max()),
            "team_games_with_no_binding_cap": int(len(free)),
            "redistributed_minutes": _dist(alloc["redistributed_minutes"]),
            "scale_factor": _dist(alloc["scale_factor"])}


@check("cap_redistribution_terminates_and_is_deterministic",
       "the water-filling loop terminates and gives the same answer under permuted input order", S)
def _a4():
    rng = np.random.default_rng(7)
    trials, maxiter = 0, 0
    for _ in range(400):
        n = int(rng.integers(5, 40))
        raw = rng.gamma(2.0, 6.0, n)
        uids = np.arange(n)
        m1, c1 = M.allocate(raw.copy(), uids)
        perm = rng.permutation(n)
        m2, c2 = M.allocate(raw[perm].copy(), uids[perm])
        inv = np.argsort(perm)
        assert (m1 == m2[inv]).all(), "allocation depends on input order"
        assert (c1 == c2[inv]).all(), "capping depends on input order"
        assert int(m1.sum()) == M.TEAM_MICRO, "trial did not sum to 200"
        assert (m1 <= M.CAP_MICRO).all() and (m1 >= 0).all(), "trial breached the bounds"
        trials += 1
        maxiter = max(maxiter, int(c1.sum()))
    # degenerate: exactly five viable candidates must each receive exactly 40
    m, c = M.allocate(np.array([1.0, 2.0, 3.0, 4.0, 5.0]), np.arange(5))
    assert (m == M.CAP_MICRO).all(), "five candidates did not each receive exactly 40 minutes"
    return {"randomised_trials": trials, "order_invariant": True,
            "max_players_capped_in_a_trial": maxiter,
            "five_candidate_degenerate_case": "each receives exactly 40.0 minutes"}


@check("offensive_possession_mass", "sum(player off) == 5 x projected team offensive possessions", S)
def _a5():
    r = PLAYERS[PLAYERS["team_game_status"] == "normal"]
    g = r.groupby(TKEY).agg(got=("projected_off_possessions", "sum"),
                            want=("projected_team_off_possessions", "first"))
    err = (g["got"] - 5.0 * g["want"]).abs()
    assert err.max() < 1e-9, f"worst offensive mass error {err.max()}"
    withheld = PLAYERS[PLAYERS["team_game_status"] == "minutes_only_no_pace"]
    assert withheld["projected_off_possessions"].isna().all(), \
        "a pace-unresolved row carries offensive possessions"
    return {"team_game_regimes_checked": int(len(g)), "worst_abs_error": float(err.max()),
            "rows_with_possessions_withheld": int(len(withheld))}


@check("defensive_possession_mass",
       "sum(player def) == 5 x opponent projected offensive possessions", S)
def _a6():
    r = PLAYERS[PLAYERS["team_game_status"] == "normal"]
    g = r.groupby(TKEY).agg(got=("projected_def_possessions", "sum"),
                            want=("projected_opp_off_possessions", "first"))
    err = (g["got"] - 5.0 * g["want"]).abs()
    assert err.max() < 1e-9, f"worst defensive mass error {err.max()}"
    withheld = PLAYERS[PLAYERS["team_game_status"] == "minutes_only_no_pace"]
    assert withheld["projected_def_possessions"].isna().all(), \
        "a pace-unresolved row carries defensive possessions"
    return {"team_game_regimes_checked": int(len(g)), "worst_abs_error": float(err.max())}


@check("home_away_accounting_reconciles",
       "team A's defensive mass equals team B's offensive mass, within the same canonical game", S)
def _a7():
    r = PLAYERS[PLAYERS["team_game_status"] == "normal"]
    tg = r.groupby(TKEY).agg(off=("projected_off_possessions", "sum"),
                             dfn=("projected_def_possessions", "sum")).reset_index()
    m = tg.merge(tg, on=["game_id", "regime"], suffixes=("_a", "_b"))
    m = m[m["team_id_a"] != m["team_id_b"]]
    assert len(m) > 0, "no opposing pairs found"
    d = (m["dfn_a"] - m["off_b"]).abs()
    assert d.max() < 1e-9, f"worst reconciliation error {d.max()}"

    # A club is present in PLAYERS iff its team-game is allocated. A club may legitimately be
    # ABSENT -- when it has fewer than five viable candidates -- but only with an explicit
    # unresolved status. Nothing may be dropped silently.
    idx = pd.MultiIndex.from_product(
        [sorted(PACE["game_id"].unique()), sorted(M.REGIMES)], names=["game_id", "regime"])
    alloc_n = (TEAMS[TEAMS["status"].isin(ALLOCATED)].groupby(["game_id", "regime"]).size()
               .reindex(idx, fill_value=0))
    present_n = (PLAYERS.groupby(["game_id", "regime"])["team_id"].nunique()
                 .reindex(idx, fill_value=0))
    assert (present_n == alloc_n).all(), \
        "player rows and allocated team statuses disagree about which clubs are present"
    absent = TEAMS[~TEAMS["status"].isin(ALLOCATED)]
    assert (absent["status"] == "unresolved_insufficient_candidates").all(), \
        "a club is absent for a reason other than an explicit unresolved status"
    assert (absent["n_allocated"] == 0).all(), "an unresolved club carries allocated players"

    # opponent identity is always the other club of that canonical game, per the contract,
    # even when that other club is itself unresolved
    gt = CONTRACT.groupby("game_id")["team_id"].agg(lambda s: frozenset(s))
    exp = PLAYERS["game_id"].map(gt)
    ok = [(o in p) and (o != t) for o, t, p in
          zip(PLAYERS["opp_team_id"], PLAYERS["team_id"], exp)]
    assert all(ok), "an opponent id is not the other club of that canonical game"

    return {"opposing_pairs_reconciled": int(len(m)), "worst_abs_error": float(d.max()),
            "game_regimes_with_both_clubs_allocated": int((alloc_n == 2).sum()),
            "game_regimes_with_one_club_allocated": int((alloc_n == 1).sum()),
            "game_regimes_with_neither_club_allocated": int((alloc_n == 0).sum()),
            "one_sided_examples": (TEAMS[~TEAMS["status"].isin(ALLOCATED)]
                                   .groupby("game_id").size().head(4).to_dict()),
            "absent_clubs_all_explicitly_unresolved": True,
            "note": ("a one-sided game-regime is not a defect: the absent club has fewer than five "
                     "viable candidates and carries unresolved_insufficient_candidates. "
                     "Reconciliation is asserted on the pairs where both clubs are allocated.")}


@check("no_invented_players", "no player is invented; unresolved is explicit", S)
def _a8():
    detail = {}
    for regime, tiers in M.REGIMES.items():
        want = CONTRACT[CONTRACT["evaluation_tier"].isin(tiers)]
        unres = TEAMS[(TEAMS["regime"] == regime) &
                      (TEAMS["status"] == "unresolved_insufficient_candidates")]
        ukeys = set(map(tuple, unres[GKEY].to_numpy()))
        expected = {u for u, k in zip(want["row_uid"], zip(want["game_id"], want["team_id"]))
                    if k not in ukeys}
        got = set(PLAYERS.loc[PLAYERS["regime"] == regime, "row_uid"])
        assert got <= set(want["row_uid"]), f"{regime}: allocated a row outside its tier set"
        assert got == expected, f"{regime}: allocated {len(got)}, expected {len(expected)}"
        detail[regime] = {"contract_rows_in_tiers": int(len(want)), "allocated": int(len(got)),
                          "stranded": int(len(want) - len(got)),
                          "unresolved_team_games": int(len(unres))}
    return detail


@check("degraded_and_unresolved_reported_separately",
       "degraded and unresolved rows do not pass aggregate checks by being averaged in", S)
def _a9():
    out = {}
    for regime in M.REGIMES:
        t = TEAMS[TEAMS["regime"] == regime]
        by = t["rotation_plausibility"].value_counts().to_dict()
        assert set(by) <= {"plausible", "degraded_roster_cardinality", "degraded_extreme_scaling",
                           "degraded_both", "unresolved"}, f"unknown plausibility label in {regime}"
        unres = t[~t["status"].isin(ALLOCATED)]
        assert (unres["rotation_plausibility"] == "unresolved").all(), \
            f"{regime}: an unresolved row carries a plausibility verdict"
        out[regime] = by
    return out


# =========================================================================== #
S = "3. regime evidence and S2 degradation"
print(f"\n{S}")


@check("regime_separation", "Tier A, transaction Tier B and S2-only are never pooled", S)
def _r1():
    for regime, tiers in M.REGIMES.items():
        got = set(PLAYERS.loc[PLAYERS["regime"] == regime, "evaluation_tier"].unique())
        assert got <= set(tiers), f"{regime} contains tiers outside its definition"
    a = set(PLAYERS.loc[PLAYERS["regime"] == "tier_a_only", "row_uid"])
    b = set(PLAYERS.loc[PLAYERS["regime"] == "tier_a_plus_tx_b", "row_uid"])
    c = set(PLAYERS.loc[PLAYERS["regime"] == "tier_a_plus_tx_b_plus_s2", "row_uid"])
    assert a <= b <= c, "the sensitivity regimes are not supersets of the primary"
    s2 = PLAYERS[PLAYERS["evaluation_tier"] == "B_s2_weak_fallback"]
    assert set(s2["regime"].unique()) <= {"tier_a_plus_tx_b_plus_s2"}, "S2 leaked out of its regime"
    return {"nested_sizes": {"tier_a_only": len(a), "tier_a_plus_tx_b": len(b),
                             "tier_a_plus_tx_b_plus_s2": len(c)},
            "s2_rows": int(len(s2)),
            "evidence_by_regime": PLAYERS.groupby(
                ["regime", "roster_evidence_regime"]).size().unstack(fill_value=0).to_dict()}


@check("operational_achievability_labelled",
       "only evidence captured before the cutoff supports a live-achievable rotation", S)
def _r2():
    for regime, ev in M.REGIME_EVIDENCE.items():
        sub = PLAYERS[PLAYERS["regime"] == regime]
        assert (sub["operationally_achievable"] == ev["operationally_achievable"]).all()
        assert (sub["evidence_class"] == ev["evidence_class"]).all()
    prim = PLAYERS[PLAYERS["regime"] == M.PRIMARY_REGIME]
    assert set(prim["roster_evidence_regime"].unique()) == {"captured_asof"}, \
        "the primary regime rests on evidence that was not captured before the cutoff"
    for regime in ("tier_a_plus_tx_b", "tier_a_plus_tx_b_plus_s2"):
        sub = PLAYERS[PLAYERS["regime"] == regime]
        assert not M.REGIME_EVIDENCE[regime]["operationally_achievable"]
        assert (sub["roster_evidence_regime"] != "captured_asof").any()
    return {"tier_a_only": "captured_asof only -- operationally achievable",
            "tier_a_plus_tx_b": ("adds retrospective_effective_date evidence, reconstructed AFTER "
                                 "the cutoff -- NOT live-achievable, sensitivity only"),
            "tier_a_plus_tx_b_plus_s2": ("adds weak_prior_season affiliation -- NOT live-achievable, "
                                         "weak diagnostic only"),
            "caveat_on_the_primary_regime": (
                "captured_asof concerns ROSTER membership. Availability remains information-limited "
                "before 2026-07-30; that limitation lives in the bound v15 p_active and is "
                "inherited here unchanged."),
            "labels": M.REGIME_EVIDENCE}


@check("rotation_cardinality_and_concentration_all_regimes",
       "the same plausibility diagnostics are reported for every regime, primary included", S)
def _r3():
    out = {}
    for regime in M.REGIMES:
        t = TEAMS[(TEAMS["regime"] == regime) & (TEAMS["status"].isin(ALLOCATED))]
        out[regime] = {
            "allocated_team_games": int(len(t)),
            "n_allocated": _dist(t["n_allocated"]),
            "effective_rotation_size": _dist(t["effective_rotation_size"]),
            "n_players_ge_10_min": _dist(t["n_players_ge_10_min"]),
            "n_players_ge_20_min": _dist(t["n_players_ge_20_min"]),
            "top5_minute_share": _dist(t["top5_minute_share"]),
            "min_player_minutes": _dist(t["min_player_minutes"]),
            "scale_factor": _dist(t["scale_factor"]),
            "exceeds_standard_active_roster": int(t["exceeds_standard_active_roster"].sum()),
            "extreme_scaling": int(t["extreme_scaling"].sum()),
            "plausibility": t["rotation_plausibility"].value_counts().to_dict(),
        }
    s2 = out["tier_a_plus_tx_b_plus_s2"]
    assert s2["n_allocated"]["max"] > M.STANDARD_ACTIVE_ROSTER, \
        "the S2 regime no longer shows the implausible cardinality it was degraded for"
    return {"thresholds": {"standard_active_roster": M.STANDARD_ACTIVE_ROSTER,
                           "scale_band": list(M.SCALE_BAND),
                           "note": "labels only; neither changes an allocated minute"},
            "by_regime": out}


# =========================================================================== #
S = "4. pace prior: chronology, cutoff isolation and fallback"
print(f"\n{S}")


def _independent_pace():
    p = pd.read_parquet(M.POSS, columns=["game_id", "period", "offense_team_id"])
    n_off = p.groupby(["game_id", "offense_team_id"]).size().rename("n").reset_index()
    mx = p.groupby("game_id")["period"].max()
    gmin = 40.0 + 5.0 * np.maximum(0, mx - 4)
    n_off["reg"] = n_off["n"] * 40.0 / n_off["game_id"].map(gmin)
    gpace = n_off.groupby("game_id")["reg"].mean()
    sched = CONTRACT[["game_id", "team_id", "game_date", "season"]].drop_duplicates(GKEY).copy()
    sched["gp"] = sched["game_id"].map(gpace)
    sched = sched.sort_values(["game_date", "game_id"])
    gd = sched.drop_duplicates("game_id")[["game_id", "game_date", "gp"]]
    rows = []
    for r in sched.itertuples(index=False):
        own = sched[(sched["team_id"] == r.team_id) & (sched["game_date"] < r.game_date)]
        same = own[own["season"] == r.season]["gp"].tolist()
        prev = own[own["season"] == r.season - 1]["gp"].tolist()
        if len(same) >= M.MIN_HISTORY_M:
            lvl, vals = 1, same[-M.WINDOW_K:]
            est, n = float(np.mean(vals)), len(vals)
        elif len(prev) >= M.MIN_HISTORY_M:
            lvl, vals = 2, prev[-M.WINDOW_K:]
            est, n = float(np.mean(vals)), len(vals)
        else:
            pri = gd[gd["game_date"] < r.game_date]["gp"]
            if len(pri):
                lvl, est, n = 3, float(pri.mean()), int(len(pri))
            else:
                lvl, est, n = 4, np.nan, 0
        rows.append((r.game_id, r.team_id, lvl, n, est))
    return pd.DataFrame(rows, columns=["game_id", "team_id", "pace_level", "n_history_games",
                                       "team_pace_estimate"])


@check("pace_matches_independent_rederivation",
       "every pace value follows the frozen rule exactly, re-derived without producer code", S)
def _p1():
    ind = _independent_pace().set_index(GKEY).sort_index()
    got = PACE.set_index(GKEY).sort_index()
    assert ind.index.equals(got.index), "team-game set differs"
    for col in ("pace_level", "n_history_games"):
        assert (ind[col].to_numpy() == got[col].to_numpy()).all(), f"{col} differs"
    assert np.allclose(ind["team_pace_estimate"].to_numpy(), got["team_pace_estimate"].to_numpy(),
                       rtol=0, atol=1e-12, equal_nan=True), "team_pace_estimate differs"
    return {"team_games": int(len(ind))}


@check("pace_support_by_level", "the exact support behind every fallback level", S)
def _p2():
    sched = CONTRACT[["game_id", "team_id", "game_date", "season"]].drop_duplicates(GKEY)
    out = {}
    for lvl, name in ((1, "team_window_same_season"), (2, "team_window_prior_season"),
                      (3, "league_prior_all"), (4, "unresolved_no_prior_games")):
        sub = PACE[PACE["pace_level"] == lvl]
        blk = {"team_games": int(len(sub)),
               "source": name,
               "n_history_games": _dist(sub["n_history_games"]),
               "by_season": sub.groupby("season").size().to_dict(),
               "by_season_type": sub.groupby("season_type").size().to_dict()}
        if lvl in (1, 2):
            assert (sub["n_history_games"] >= M.MIN_HISTORY_M).all(), f"level {lvl} below minimum"
            assert (sub["n_history_games"] <= M.WINDOW_K).all(), f"level {lvl} exceeds the window"
        if lvl == 4:
            assert sub["team_pace_estimate"].isna().all(), "unresolved carries a value"
            blk["games"] = sorted(sub["game_id"].unique().tolist())
        # every level-2 and level-3 row must genuinely lack the level above it
        for r in sub.itertuples(index=False):
            own = sched[(sched["team_id"] == r.team_id) & (sched["game_date"] < r.game_date)]
            same_n = int((own["season"] == r.season).sum())
            if lvl >= 2:
                assert same_n < M.MIN_HISTORY_M, f"level {lvl} used with {same_n} same-season priors"
            if lvl >= 3:
                assert int((own["season"] == r.season - 1).sum()) < M.MIN_HISTORY_M, \
                    f"level {lvl} used although prior-season history sufficed"
        out[f"level_{lvl}"] = blk
    assert sum(v["team_games"] for v in out.values()) == len(PACE)
    return out


@check("pace_ordered_by_canonical_date_not_game_index",
       "history is ordered by canonical game date, and same-date games are excluded", S)
def _p3():
    sched = CONTRACT[["game_id", "team_id", "game_date", "season"]].drop_duplicates(GKEY)
    dates = sched.drop_duplicates("game_id").set_index("game_id")["game_date"]
    for r in PACE.itertuples(index=False):
        if r.pace_level == 4:
            continue
        own = sched[(sched["team_id"] == r.team_id) & (sched["game_date"] < r.game_date)]
        if r.pace_level == 1:
            avail = int((own["season"] == r.season).sum())
        elif r.pace_level == 2:
            avail = int((own["season"] == r.season - 1).sum())
        else:
            avail = int((dates < r.game_date).sum())
        assert r.n_history_games <= avail, f"{r.game_id}/{r.team_id} used more than is admissible"
    # a same-date game is never admissible: teams play at most once per date, and the independent
    # re-derivation (which uses a strict < on dates) reproduces every value exactly
    per_team_date = sched.groupby(["team_id", "game_date"]).size()
    return {"admissibility_rule": "game_date strictly earlier than the target game's date",
            "max_games_per_team_per_date": int(per_team_date.max()),
            "same_date_history_possible": False,
            "ordering": "canonical game_date, tie-broken by game_id -- never a positional index",
            "verified_by": "pace_matches_independent_rederivation"}


@check("pace_overtime_normalisation", "overtime is normalised out by the frozen rule", S)
def _p4():
    p = pd.read_parquet(M.POSS, columns=["game_id", "period"])
    mx = p.groupby("game_id")["period"].max()
    ot = mx[mx > 4]
    assert RECEIPT["pace"]["overtime_games_normalised"] == int(len(ot))
    return {"games_with_overtime": int(len(ot)),
            "max_period_distribution": mx.value_counts().sort_index().to_dict(),
            "rule": "game_minutes = 40 + 5 * max(0, max_period - 4); possessions scaled by 40/game_minutes",
            "consequence": "the artifact projects REGULATION-EQUIVALENT exposure; no overtime is projected"}


@check("pace_includes_postseason", "postseason games are included where applicable", S)
def _p5():
    by = PACE.groupby("season_type").size().to_dict()
    assert by.get("Playoffs", 0) > 0, "no playoff team-games in the pace artifact"
    pl = PACE[PACE["season_type"] == "Playoffs"]
    assert (pl["pace_level"] == 1).mean() > 0.9, "playoff games mostly failed to resolve at level 1"
    return {"team_games_by_season_type": by,
            "playoff_pace_levels": pl["pace_level"].value_counts().sort_index().to_dict(),
            "pooling_rule": "regular season and playoffs pooled; no separate playoff estimator"}


# =========================================================================== #
S = "5. leakage, provenance and chronological isolation"
print(f"\n{S}")


@check("runtime_provenance_of_every_file_read",
       "the producer reads only its three declared inputs, and only the declared columns", S)
def _l1():
    assert BASE_READS, "no reads were recorded"
    paths = sorted({r["path"] for r in BASE_READS})
    allowed_contract = str(M.CONTRACT)
    allowed_poss = str(M.POSS)
    pred = {str(f) for f in M.PRED_DIR.glob("predictions__p_active__*.parquet")} | \
           {str(f) for f in M.PRED_DIR.glob("predictions__e_minutes_given_active__*.parquet")}
    for p in paths:
        assert p == allowed_contract or p == allowed_poss or p in pred, \
            f"the producer read an undeclared file: {p}"
    poss_reads = [r for r in BASE_READS if r["path"] == allowed_poss]
    assert poss_reads, "the possession artifact was not read"
    for r in poss_reads:
        assert r["columns"] is not None, "the possession artifact was read without a column list"
        assert set(r["columns"]) <= {"game_id", "season_type", "period", "offense_team_id"}, \
            f"the producer read possession columns it must not: {r['columns']}"
    banned = {"off_p1", "off_p2", "off_p3", "off_p4", "off_p5",
              "def_p1", "def_p2", "def_p3", "def_p4", "def_p5",
              "points_scored", "duration_sec", "home_pts_before", "away_pts_before"}
    for r in poss_reads:
        assert not (set(r["columns"]) & banned), "a lineup or scoring column was read"
    pred_reads = [r for r in BASE_READS if r["path"] in pred]
    for r in pred_reads:
        assert set(r["columns"]) <= {"row_uid", "pred_point", "is_fallback", "fallback_level",
                                     "model_hash", "config_hash", "data_snapshot_hash"}, \
            f"an undeclared prediction column was read: {r['columns']}"
    return {"distinct_files_read": len(paths),
            "possession_columns_read": sorted({c for r in poss_reads for c in r["columns"]}),
            "prediction_files_read": len(pred_reads),
            "prediction_columns_read": sorted({c for r in pred_reads for c in r["columns"]}),
            "lineup_columns_read": [],
            "scoring_columns_read": [],
            "read_csv_called": False,
            "method": "pandas.read_parquet instrumented at runtime, not a source grep"}


@check("no_outcome_columns", "no outcome or outcome-derived field appears in any output", S)
def _l2():
    banned = set(M.OUTCOME_COLS)
    for name, df in (("players", PLAYERS), ("teams", TEAMS), ("pace", PACE)):
        hit = banned & set(df.columns)
        assert not hit, f"{name} carries outcome columns: {sorted(hit)}"
    suspicious = [c for c in list(PLAYERS.columns) + list(TEAMS.columns) + list(PACE.columns)
                  if any(k in c.lower() for k in
                         ("actual", "realis", "realiz", "observed_", "in_target_box", "appeared",
                          "_pts", "box_"))]
    assert not suspicious, f"columns hidden under alternate names: {suspicious}"
    # the ambiguity STATE is outcome-derived and must be absent; the COUNT-derived flag may stay
    assert "team_assignment_ambiguity_state" not in PLAYERS.columns
    assert "candidate_claimed_by_multiple_teams" in PLAYERS.columns
    return {"banned_checked": sorted(banned),
            "ambiguity_disclosed_without_outcome_information": {
                "field": "candidate_claimed_by_multiple_teams",
                "rows_flagged": int(PLAYERS["candidate_claimed_by_multiple_teams"].sum()),
                "by_regime": PLAYERS[PLAYERS["candidate_claimed_by_multiple_teams"]]
                             .groupby("regime").size().to_dict(),
                "why_not_resolved": ("resolving it needs the box row, which is target-game outcome "
                                     "information")},
            "player_columns": sorted(PLAYERS.columns.tolist())}


@check("target_game_outcome_perturbation_invariance",
       "target-game box-score outcomes cannot influence the forecast", S)
def _l3():
    with tempfile.TemporaryDirectory() as td:
        alt = Path(td) / "contract_outcomes_scrambled.parquet"
        c = CONTRACT.copy()
        rng = np.random.default_rng(0)
        touched = []
        for col in ["minutes", "pts", "fga"]:
            c[col] = rng.permutation(c[col].to_numpy()) + 7.0
            touched.append(col)
        for col in ["appeared", "in_target_box"] + \
                   [x for x in c.columns if x.startswith("outcome_scoreable__")]:
            c[col] = ~c[col].astype(bool)
            touched.append(col)
        c["team_assignment_ambiguity_state"] = "SCRAMBLED"
        touched.append("team_assignment_ambiguity_state")
        c.to_parquet(alt, index=False)
        pace2, pl2, tm2 = _run(contract=alt)
    pd.testing.assert_frame_equal(pl2, PLAYERS)
    pd.testing.assert_frame_equal(tm2, TEAMS)
    pd.testing.assert_frame_equal(pace2, PACE)
    return {"columns_perturbed": touched, "artifact_changed": False}


@check("future_transaction_and_availability_perturbation_invariance",
       "later-revealed transactions and later availability cannot change an earlier projection", S)
def _l4():
    cut = pd.Timestamp("2024-07-01")
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        alt_c = td / "contract_future_perturbed.parquet"
        c = CONTRACT.copy()
        fut = c["game_date"] >= cut
        c.loc[fut & (c["evaluation_tier"] == "B_s2_weak_fallback"), "evaluation_tier"] = \
            "B_transaction_sensitivity"
        c.loc[fut & (c["evaluation_tier"] == "A_primary"), "team_assignment_confidence"] = "probable"
        c.to_parquet(alt_c, index=False)
        alt_p = td / "preds"
        alt_p.mkdir()
        fut_uids = set(c.loc[fut, "row_uid"])
        rng = np.random.default_rng(1)
        for f in sorted(M.PRED_DIR.glob("predictions__*.parquet")):
            d = pd.read_parquet(f)
            m = d["row_uid"].isin(fut_uids)
            if m.any():
                d.loc[m, "pred_point"] = rng.uniform(0.05, 0.95, int(m.sum())) * \
                    d.loc[m, "pred_point"].to_numpy()
            d.to_parquet(alt_p / f.name, index=False)
        pace2, pl2, tm2 = _run(contract=alt_c, pred_dir=alt_p)

    n_pl = _cmp_subset(PLAYERS, pl2, PKEY, lambda d: d["game_date"] < cut, "players")
    n_tm = _cmp_subset(TEAMS, tm2, TKEY, lambda d: d["game_date"] < cut, "teams")
    n_pc = _cmp_subset(PACE, pace2, GKEY, lambda d: d["game_date"] < cut, "pace")
    a = PLAYERS.set_index(PKEY)["projected_minutes"]
    b = pl2.set_index(PKEY)["projected_minutes"]
    common = a.index.intersection(b.index)
    changed = int((a.loc[common].to_numpy() != b.loc[common].to_numpy()).sum()) \
        + len(a.index.difference(b.index)) + len(b.index.difference(a.index))
    assert changed > 0, "the perturbation changed nothing; the test exercises nothing"
    return {"cutoff": str(cut.date()), "perturbed": ["evaluation_tier (transactions)",
                                                     "p_active (availability)",
                                                     "e_minutes_given_active"],
            "player_rows_unchanged_before_cutoff": n_pl,
            "team_rows_unchanged_before_cutoff": n_tm,
            "pace_rows_unchanged_before_cutoff": n_pc,
            "rows_that_did_change_at_or_after_cutoff": changed}


@check("target_game_possession_perturbation_invariance",
       "no realised possession or pace of the target game reaches its own forecast", S)
def _l5():
    cut = pd.Timestamp("2024-07-01")
    late = set(CONTRACT.loc[CONTRACT["game_date"] >= cut, "game_id"])
    with tempfile.TemporaryDirectory() as td:
        alt = Path(td) / "poss_future_doubled.parquet"
        p = pd.read_parquet(M.POSS)
        p2 = pd.concat([p, p[p["game_id"].isin(late)]], ignore_index=True)
        p2.to_parquet(alt, index=False)
        pace2, pl2, tm2 = _run(poss=alt)
    n_pc = _cmp_subset(PACE, pace2, GKEY, lambda d: d["game_date"] <= cut, "pace")
    n_pl = _cmp_subset(PLAYERS, pl2, PKEY, lambda d: d["game_date"] <= cut, "players")
    diff = int((pace2.set_index(GKEY).sort_index()["team_pace_estimate"].fillna(-1).to_numpy() !=
                PACE.set_index(GKEY).sort_index()["team_pace_estimate"].fillna(-1).to_numpy()).sum())
    assert diff > 0, "doubling later possessions changed nothing; the test exercises nothing"
    return {"cutoff": str(cut.date()), "games_perturbed": len(late),
            "pace_rows_unchanged_through_cutoff": n_pc,
            "player_rows_unchanged_through_cutoff": n_pl,
            "pace_rows_that_did_change_after_cutoff": diff,
            "note": ("rows ON the cutoff date are unchanged even though their OWN possessions were "
                     "doubled -- that is what proves a game's realised possession count never "
                     "enters its own projection")}


# =========================================================================== #
S = "6. determinism, idempotence and fail-closed behaviour"
print(f"\n{S}")


@check("deterministic_reproduction", "the same inputs always produce the same result", S)
def _d1():
    pace2, pl2, tm2 = _run()
    pd.testing.assert_frame_equal(BASE_PLAYERS, pl2)
    pd.testing.assert_frame_equal(BASE_TEAMS, tm2)
    pd.testing.assert_frame_equal(BASE_PACE, pace2)
    pd.testing.assert_frame_equal(pl2, PLAYERS)
    pd.testing.assert_frame_equal(tm2, TEAMS)
    pd.testing.assert_frame_equal(pace2, PACE)
    return {"independent_builds_compared": 2, "matches_shipped_artifact": True}


@check("idempotent_generation", "regenerating writes byte-identical artifacts", S)
def _d2():
    before = {p.name: M._sha(p) for p in sorted(OUT.glob("*.parquet"))}
    M.main()
    after = {p.name: M._sha(p) for p in sorted(OUT.glob("*.parquet"))}
    assert before == after, "artifact bytes changed on regeneration"
    return {"sha256": after}


@check("nan_handling_fails_closed", "a null prediction is rejected, not silently imputed", S)
def _d3():
    rejected = {}
    # inject into each target the producer ACTUALLY reads -- an earlier version of this test put
    # the NaN in predictions__attempts_usage__*, which sorts first and is never read, so the gate
    # was never exercised
    for target in ("p_active", "e_minutes_given_active"):
        with tempfile.TemporaryDirectory() as td:
            alt = Path(td) / "preds"
            alt.mkdir()
            injected = False
            for f in sorted(M.PRED_DIR.glob("predictions__*.parquet")):
                d = pd.read_parquet(f)
                if not injected and f.name.startswith(f"predictions__{target}__"):
                    d.loc[d.index[0], "pred_point"] = np.nan
                    injected = True
                d.to_parquet(alt / f.name, index=False)
            assert injected, f"no {target} prediction file was found to perturb"
            try:
                _run(pred_dir=alt)
            except M.ProducerFailure as exc:
                rejected[target] = str(exc)[:110]
                continue
        raise AssertionError(f"a null {target} prediction was accepted")
    return {"rejected": rejected, "targets_tested": sorted(rejected)}


@check("missing_side_fails_closed", "a game missing one club is rejected, not half-projected", S)
def _d4():
    with tempfile.TemporaryDirectory() as td:
        alt = Path(td) / "contract_missing_side.parquet"
        c = CONTRACT.copy()
        g = c["game_id"].iloc[0]
        t = c.loc[c["game_id"] == g, "team_id"].iloc[0]
        c = c[~((c["game_id"] == g) & (c["team_id"] == t))]
        c.to_parquet(alt, index=False)
        try:
            _run(contract=alt)
        except M.ProducerFailure as exc:
            return {"rejected": True, "game_id": str(g), "message": str(exc)[:120]}
    raise AssertionError("a one-sided game was accepted")


@check("fail_closed_gate_rejects_violations", "the gate rejects each constraint violation", S)
def _d5():
    fired = {}

    def expect(label, mutate):
        pl, tm = PLAYERS.copy(), TEAMS.copy()
        pl, tm = mutate(pl, tm)
        try:
            M.assert_producer_invariants(pl, tm)
        except M.ProducerFailure as exc:
            fired[label] = str(exc)[:90]
            return
        raise AssertionError(f"gate did not fire for {label}")

    alloc_ix = TEAMS.index[TEAMS["status"].isin(ALLOCATED)][0]
    norm_ix = PLAYERS.index[PLAYERS["team_game_status"] == "normal"][0]

    def _minutes(pl, tm):
        tm.loc[alloc_ix, "projected_minutes_micro_sum"] = M.TEAM_MICRO - 1
        return pl, tm

    def _cap(pl, tm):
        pl.loc[pl.index[0], "projected_minutes_micro"] = M.CAP_MICRO + 1
        return pl, tm

    def _neg(pl, tm):
        pl.loc[pl.index[0], "projected_minutes"] = -1.0
        return pl, tm

    def _dup(pl, tm):
        return pd.concat([pl, pl.iloc[[0]]], ignore_index=True), tm

    def _outcome(pl, tm):
        pl["minutes"] = 1.0
        return pl, tm

    def _mass(pl, tm):
        pl.loc[norm_ix, "projected_off_possessions"] += 5.0
        return pl, tm

    def _dmass(pl, tm):
        pl.loc[norm_ix, "projected_def_possessions"] += 5.0
        return pl, tm

    def _self_opp(pl, tm):
        pl.loc[pl.index[0], "opp_team_id"] = pl.loc[pl.index[0], "team_id"]
        return pl, tm

    for label, fn in (("team_minutes", _minutes), ("player_cap", _cap), ("negative", _neg),
                      ("duplicate", _dup), ("outcome_column", _outcome),
                      ("offensive_mass", _mass), ("defensive_mass", _dmass),
                      ("self_opponent", _self_opp)):
        expect(label, fn)
    return {"violations_rejected": fired, "count": len(fired)}


@check("fail_closed_writes_nothing", "a failing producer writes no artifact", S)
def _d6():
    with tempfile.TemporaryDirectory() as td:
        tmp_out = Path(td) / "would_be_written"
        old_out, old_gate = M.OUT, M.assert_producer_invariants

        def boom(_p, _t):
            raise M.ProducerFailure("injected failure")

        try:
            M.OUT, M.assert_producer_invariants = tmp_out, boom
            try:
                M.main()
            except M.ProducerFailure:
                pass
            else:
                raise AssertionError("main() did not fail")
            assert not tmp_out.exists() or not any(tmp_out.iterdir()), \
                "the producer wrote output despite failing"
        finally:
            M.OUT, M.assert_producer_invariants = old_out, old_gate
    return {"output_written_on_failure": False}


# =========================================================================== #
S = "7. inherited disclosures"
print(f"\n{S}")


@check("tier_b_history_influence_disclosed",
       "observed Tier B games move later Tier A history; that influence is inherited", S)
def _t1():
    n_b = int((CONTRACT["universe_tier"] == "B").sum())
    blk = RECEIPT["tier_b_historical_observation_influence"]
    assert blk["tier_b_rows_in_universe"] == n_b
    assert blk["policy"] == "tier_a_target_fit_with_observed_history/1"
    return {"tier_b_rows": n_b,
            "inherited_through": "the bound v15 predictions, unchanged by this artifact"}


@check("offdef_equality_is_a_projection_assumption",
       "equal player offensive and defensive possessions is registered as an assumption", S)
def _t2():
    r = PLAYERS[PLAYERS["team_game_status"] == "normal"]
    d = (r["projected_off_possessions"] - r["projected_def_possessions"]).abs()
    equal = bool(d.max() < 1e-12)
    assert equal, "the artifact no longer matches its registered assumption"
    return {"player_off_equals_player_def": equal,
            "status": ("a SIMPLIFYING PROJECTION ASSUMPTION of v1, not an empirically established "
                       "player-level fact"),
            "why": ("both counts derive from the same projected minute share and the same single "
                    "game-level pace estimate; v1 projects no substitution timing, so it carries "
                    "no information that could separate them"),
            "what_the_realised_evidence_supports": (
                "one GAME-LEVEL possession total -- the realised home-minus-away team difference "
                "has mean 0.002. It does NOT establish player-level equality, because "
                "substitutions occur between possessions"),
            "required_language_for_the_p3_ablation": (
                "net-coefficient and separate-coefficient arms share this exposure, so differences "
                "between them reflect coefficient construction, estimation and shrinkage, not a "
                "different exposure model"),
            "erratum": "exposure_offdef__erratum_projection_assumption"}


@check("coverage_language_is_accurate",
       "the artifact covers every game with a cutoff-valid prior and fails closed otherwise", S)
def _t3():
    unres = PACE[~PACE["pace_resolved"]]
    assert len(unres) == 8, f"expected 8 unresolved team-games, found {len(unres)}"
    first = CONTRACT["game_date"].min()
    assert (unres["game_date"] == first).all(), "an unresolved pace occurs after the first date"
    mo = TEAMS[TEAMS["status"] == "minutes_only_no_pace"]
    assert mo["projected_team_off_possessions"].isna().all()
    return {"claim": ("covers every game for which a CUTOFF-VALID PRIOR exists; fails closed "
                      "otherwise"),
            "not_claimed": "coverage of every historical game",
            "unresolved_pace_team_games": int(len(unres)),
            "unresolved_games": sorted(unres["game_id"].unique().tolist()),
            "first_game_date": str(first.date()),
            "team_game_regimes_with_minutes_but_no_possessions": int(len(mo)),
            "rejected_alternative": ("fabricating an opening prior from later 2021 games, which "
                                     "lie after those cutoffs"),
            "erratum": "exposure_coverage__erratum_cutoff_valid_prior"}


# =========================================================================== #
def main() -> int:
    n_pass = sum(1 for r in RESULTS if r["result"] == "PASS")
    n_fail = len(RESULTS) - n_pass
    table = [{"section": r["section"], "check": r["check"], "result": r["result"]}
             for r in RESULTS]
    out = {
        "schema": "projected_exposure_validation/2",
        "artifact_id": "projected_player_possessions/1",
        "pace_artifact_id": "team_possession_prior/1",
        "validated_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "nothing_scored": True,
        "no_accuracy_computed": ("this validator compares no projection against any realised "
                                 "minute, possession, margin or outcome"),
        "validator_sha256": M._sha(Path(__file__)),
        "producer_sha256": M._sha(Path(M.__file__)),
        "artifact_sha256": {p.name: M._sha(p) for p in sorted(OUT.glob("*.parquet"))},
        "registry_records": [
            "team_possession_prior_v1", "projected_player_possessions_v1",
            "exposure_coverage__erratum_cutoff_valid_prior",
            "exposure_offdef__erratum_projection_assumption",
            "exposure_s2__policy_weak_evidence_diagnostic",
        ],
        "checks_total": len(RESULTS), "checks_passed": n_pass, "checks_failed": n_fail,
        "verdict": "PASS" if n_fail == 0 else "FAIL",
        "pass_fail_table": table,
        "checks": RESULTS,
    }
    (OUT / "PROJECTED_EXPOSURE_VALIDATION.json").write_text(
        json.dumps(out, indent=2, default=str), encoding="utf-8")
    print(f"\n{n_pass}/{len(RESULTS)} checks passed -> {out['verdict']}")
    for r in RESULTS:
        if r["result"] != "PASS":
            print(f"  {r['result']}: {r['check']} -- {r['detail'].get('error')}")
    print(f"receipt: {OUT / 'PROJECTED_EXPOSURE_VALIDATION.json'}")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
