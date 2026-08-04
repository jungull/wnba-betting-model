#!/usr/bin/env python3
"""TESTS.py -- P23_DIMENSION_CARDINALITY_GUARD.

Standalone runnable test script (pytest is NOT available in this environment).
`main()` returns 0 on success and 1 on any failure.

Two families of test:

  SYNTHETIC  -- exercise every branch of merge_guard.py on constructed frames.
  REAL       -- re-derive the V2_STOP_CONDITION S2 measurements against the actual bytes of
                data/reference/team_cities.csv and the frozen 2,982-row universe in
                projected_exposure_v1/team_possession_prior_v1.parquet, and demonstrate that the
                guard both REJECTS the naive join and ACCEPTS the season-effective resolution.

The REAL family reads two files outside `experiments/player_program/`. That read is unavoidable:
acceptance criterion 5 is stated about `team_id` 1611661317, which exists only in
`data/reference/team_cities.csv`. Both files are read strictly read-only.

Every number this script prints is computed here. Nothing is quoted from the packet.
"""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from merge_guard import (  # noqa: E402
    AmbiguousDimensionError,
    DimensionSpec,
    MergeCardinalityFailure,
    RowUniverse,
    UndeclaredNullIntervalError,
    assert_no_order_dependent_dedup,
    check_dimension_primary_key,
    guarded_merge,
    resolve_effective_dimension,
)

# repo root = .../<worktree>/experiments/player_program/stage2b/<node>/ -> up 4
REPO = HERE.parents[3]
TEAM_CITIES = REPO / "data" / "reference" / "team_cities.csv"
PRIOR = (REPO / "experiments" / "player_program" / "projected_exposure_v1"
         / "team_possession_prior_v1.parquet")

RESULTS: list[dict] = []
MEASURED: dict = {}


def _fail(msg):
    raise AssertionError(msg)


def check(cond, msg):
    if not cond:
        _fail(msg)


# --------------------------------------------------------------------------------------------
# fixtures
# --------------------------------------------------------------------------------------------

def synthetic_fact(n_games=4):
    rows = []
    for g in range(n_games):
        for t in (10, 20):
            rows.append({"game_id": f"G{g:03d}", "team_id": t, "season": 2021 + (g % 3),
                         "y": float(g * 10 + t)})
    return pd.DataFrame(rows)


def synthetic_dim_unique():
    return pd.DataFrame({"team_id": [10, 20], "elevation_ft": [100, 2000],
                         "timezone": ["A", "B"]})


def synthetic_dim_duplicated():
    """team_id 20 appears twice -- the synthetic analogue of the PHO/PHX rebrand."""
    return pd.DataFrame({"team_id": [10, 20, 20],
                         "first_season": [2021, 2021, 2023],
                         "last_season": [np.nan, 2022.0, np.nan],
                         "elevation_ft": [100, 2000, 2000],
                         "timezone": ["A", "B", "B"]})


def load_real():
    if not TEAM_CITIES.exists():
        _fail(f"required dimension file absent: {TEAM_CITIES}")
    if not PRIOR.exists():
        _fail(f"required universe artifact absent: {PRIOR}")
    tc = pd.read_csv(TEAM_CITIES)
    prior = pd.read_parquet(PRIOR)
    universe = prior[prior["pace_resolved"].astype(bool)].copy().reset_index(drop=True)
    return tc, prior, universe


# --------------------------------------------------------------------------------------------
# SYNTHETIC tests
# --------------------------------------------------------------------------------------------

def t01_spec_requires_explicit_declarations():
    """Criterion 1: keys and expected cardinality cannot be omitted or inferred."""
    for kwargs, why in [
        (dict(cardinality="many_to_one"), "an undeclared/invalid cardinality string"),
        (dict(left_keys=("team_id", "season"), right_keys=("team_id",)), "key arity mismatch"),
        (dict(left_keys=(), right_keys=()), "empty key list"),
        (dict(value_columns=()), "empty value_columns"),
        (dict(effective_from="first_season"), "a partial interval declaration"),
    ]:
        base = dict(name="s", left_keys=("team_id",), right_keys=("team_id",),
                    cardinality="m:1", value_columns=("elevation_ft",))
        base.update(kwargs)
        try:
            DimensionSpec(**base)
        except MergeCardinalityFailure:
            continue
        _fail(f"DimensionSpec accepted {why}")
    ok = DimensionSpec(name="s", left_keys=("team_id",), right_keys=("team_id",),
                       cardinality="m:1", value_columns=("elevation_ft",))
    check(ok.cardinality == "m:1", "valid spec rejected")
    return {"n_invalid_specs_rejected": 5}


def t02_duplicate_primary_key_is_rejected():
    """Criterion 3, first half: a non-unique dimension PK is rejected BEFORE the merge."""
    spec = DimensionSpec(name="dup", left_keys=("team_id",), right_keys=("team_id",),
                         cardinality="m:1", value_columns=("elevation_ft",))
    try:
        check_dimension_primary_key(synthetic_dim_duplicated(), spec)
    except MergeCardinalityFailure as e:
        check("20" in str(e), "rejection did not name the duplicated key")
    else:
        _fail("duplicate primary key was NOT rejected")
    pk = check_dimension_primary_key(synthetic_dim_unique(), spec)
    check(pk["unique"] and pk["n_duplicated_keys"] == 0, "unique dimension wrongly flagged")
    return {"duplicate_pk_rejected": True, "unique_pk_accepted": True}


def t03_fan_out_fails_the_merge():
    """Criterion 3, second half: fan-out fails, and it fails even if the PK check is bypassed."""
    fact, dim = synthetic_fact(), synthetic_dim_duplicated()
    spec = DimensionSpec(name="fanout", left_keys=("team_id",), right_keys=("team_id",),
                         cardinality="m:1", value_columns=("elevation_ft",))
    try:
        guarded_merge(fact, dim, spec)
    except MergeCardinalityFailure:
        pass
    else:
        _fail("guarded_merge allowed a fan-out merge")

    # what an UNGUARDED merge would have done, measured
    naive = fact.merge(dim[["team_id", "elevation_ft"]], on="team_id", how="left")
    check(len(naive) > len(fact), "synthetic fixture does not actually fan out")

    # and the universe assertion catches it on its own, independent of the PK check
    uni = RowUniverse.capture(fact)
    try:
        uni.assert_unchanged(naive, context="naive")
    except MergeCardinalityFailure as e:
        check("row_count_changed" in str(e), "universe failure did not report row_count_changed")
        check("team_game_key_fan_out" in str(e), "universe failure did not report fan-out")
    else:
        _fail("RowUniverse.assert_unchanged accepted a fanned-out frame")
    return {"guarded_rows": len(fact), "unguarded_rows": len(naive),
            "unguarded_excess_rows": len(naive) - len(fact)}


def t04_row_universe_detects_every_mutation():
    """Criterion 2: row count, game key set and team-game key set are each asserted."""
    fact = synthetic_fact()
    uni = RowUniverse.capture(fact)
    check(uni.assert_unchanged(fact.copy(), "identity")["preserved"], "identity merge flagged")

    kinds = set()
    for mutant, label in [
        (fact.iloc[:-1].copy(), "dropped_row"),
        (pd.concat([fact, fact.iloc[[0]]], ignore_index=True), "duplicated_row"),
    ]:
        try:
            uni.assert_unchanged(mutant, label)
        except MergeCardinalityFailure as e:
            kinds.update(k for k in ("row_count_changed", "game_key_set_changed",
                                     "team_game_key_set_changed", "team_game_key_fan_out")
                         if k in str(e))
        else:
            _fail(f"universe mutation {label} not detected")

    # a fact frame that is already non-unique cannot even be used as a baseline
    try:
        RowUniverse.capture(pd.concat([fact, fact], ignore_index=True))
    except MergeCardinalityFailure:
        pass
    else:
        _fail("RowUniverse.capture accepted an already-fanned-out frame")
    return {"detected_problem_kinds": sorted(kinds)}


def t05_null_expansion_is_reported():
    """Criterion 4: nulls introduced by the merge are measured and attributed."""
    fact = synthetic_fact()
    dim = pd.DataFrame({"team_id": [10, 20], "elevation_ft": [100, np.nan],
                        "timezone": ["A", "B"]})
    spec = DimensionSpec(name="nulls", left_keys=("team_id",), right_keys=("team_id",),
                         cardinality="m:1", value_columns=("elevation_ft", "timezone"))
    _, rep = guarded_merge(fact, dim, spec)
    ne = rep["null_expansion"]
    col = {c["column"]: c for c in ne["columns"]}
    check(ne["any_null_expansion"] is True, "null expansion not flagged")
    check(col["elevation_ft"]["n_null_after_merge"] == 4,
          f"wrong null count: {col['elevation_ft']}")
    check(col["elevation_ft"]["n_null_from_unmatched_fact_rows"] == 0,
          "nulls wrongly attributed to unmatched rows")
    check(col["elevation_ft"]["n_null_from_dimension_values"] == 4,
          "nulls not attributed to the dimension source")
    check(col["timezone"]["n_null_after_merge"] == 0, "timezone should be complete")

    # an uncovered key: coverage failure, with the nulls attributed to unmatched rows
    dim2 = pd.DataFrame({"team_id": [10], "elevation_ft": [100], "timezone": ["A"]})
    spec2 = DimensionSpec(name="partial", left_keys=("team_id",), right_keys=("team_id",),
                          cardinality="m:1", value_columns=("elevation_ft", "timezone"),
                          require_total_coverage=True)
    try:
        guarded_merge(fact, dim2, spec2)
    except MergeCardinalityFailure as e:
        check("matched no dimension row" in str(e), f"wrong coverage error: {e}")
    else:
        _fail("incomplete dimension coverage was not rejected")

    spec3 = DimensionSpec(name="partial_ok", left_keys=("team_id",), right_keys=("team_id",),
                          cardinality="m:1", value_columns=("elevation_ft", "timezone"),
                          require_total_coverage=False)
    _, rep3 = guarded_merge(fact, dim2, spec3)
    ne3 = rep3["null_expansion"]
    check(ne3["n_unmatched_fact_rows"] == 4, f"wrong unmatched count: {ne3}")
    c3 = {c["column"]: c for c in ne3["columns"]}
    check(c3["timezone"]["n_null_from_unmatched_fact_rows"] == 4,
          "unmatched nulls not attributed correctly")
    return {"null_from_dimension_values": 4, "null_from_unmatched_rows": 4}


def t06_undeclared_null_interval_is_a_hard_failure():
    """Criterion 5 support: a null interval endpoint must be declared, never silently filtered."""
    dim = synthetic_dim_duplicated()
    spec = DimensionSpec(name="undecl", left_keys=("team_id", "season"),
                         right_keys=("team_id", "season"), cardinality="m:1",
                         value_columns=("elevation_ft",),
                         effective_from="first_season", effective_to="last_season",
                         effective_on="season")
    try:
        resolve_effective_dimension(dim, spec, {(10, 2021)})
    except UndeclaredNullIntervalError as e:
        check("open_ended_upper_bound" in str(e), f"wrong message: {e}")
    else:
        _fail("undeclared null upper bound was accepted")

    # the null-UNSAFE filter that S2 warns about, measured on the synthetic fixture
    surviving = dim[dim["last_season"].notna()]
    check(len(surviving) < len(dim), "fixture has no null upper bounds")
    return {"rows_before_null_unsafe_filter": int(len(dim)),
            "rows_after_null_unsafe_filter": int(len(surviving))}


def t07_interval_resolution_is_exact_or_it_raises():
    """Criterion 5: resolution is by declared interval only; 0 or >1 matches raises."""
    dim = synthetic_dim_duplicated()
    spec = DimensionSpec(name="eff", left_keys=("team_id", "season"),
                         right_keys=("team_id", "season"),
                         cardinality="m:1", value_columns=("elevation_ft",),
                         effective_from="first_season", effective_to="last_season",
                         effective_on="season", open_ended_upper_bound=True)
    pairs = {(10, 2021), (10, 2022), (20, 2021), (20, 2022), (20, 2023)}
    res, rep = resolve_effective_dimension(dim, spec, pairs)
    check(rep["resolved"] and len(res) == len(pairs), f"resolution failed: {rep}")
    check(rep["n_multi_row_keys"] == 1, "multi-row key not reported")
    got = {(int(r.team_id), int(r.season)): float(r.first_season) for r in res.itertuples()}
    check(got[(20, 2022)] == 2021 and got[(20, 2023)] == 2023,
          f"interval resolution picked the wrong row: {got}")

    # uncovered pair
    try:
        resolve_effective_dimension(dim, spec, {(20, 2019)})
    except AmbiguousDimensionError as e:
        check("no interval covers it" in str(e) or "match NO declared interval" in str(e),
              f"wrong uncovered message: {e}")
    else:
        _fail("uncovered (key, season) pair was not rejected")

    # genuinely overlapping intervals -> ambiguous -> caller must EXCLUDE
    bad = pd.DataFrame({"team_id": [20, 20], "first_season": [2021, 2022],
                        "last_season": [2023.0, 2024.0], "elevation_ft": [1, 2]})
    try:
        resolve_effective_dimension(bad, spec, {(20, 2022)})
    except AmbiguousDimensionError as e:
        check("EXCLUDE" in str(e), f"ambiguity message must instruct exclusion: {e}")
    else:
        _fail("overlapping intervals were not rejected")
    return {"pairs_resolved": len(res), "uncovered_rejected": True, "overlap_rejected": True}


def t08_no_order_dependent_dedup_in_this_node():
    """Criterion 6: deduplication by arbitrary first/last row order is used nowhere."""
    scan = assert_no_order_dependent_dedup([HERE / "merge_guard.py"])
    check(scan["clean"], f"order-dependent dedup found in merge_guard.py: {scan['hits']}")

    # the scanner must actually be able to see such a construct
    probe = HERE / "_scanner_probe.tmp.py"
    probe.write_text("x = df.sort_values('a').drop_duplicates('k', keep='first')\n",
                     encoding="utf-8")
    try:
        s2 = assert_no_order_dependent_dedup([probe])
        pats = {h["pattern"] for h in s2["hits"]}
        check({"drop_duplicates", "keep_first_or_last", "sort_then_take"} <= pats,
              f"scanner missed a forbidden construct: {pats}")
    finally:
        probe.unlink(missing_ok=True)
    return {"merge_guard_clean": True,
            "scanner_patterns": sorted(scan["files_scanned"] and
                                       __import__("merge_guard").ORDER_DEPENDENT_PATTERNS)}


# --------------------------------------------------------------------------------------------
# REAL tests -- re-derivation of V2_STOP_CONDITION S2
# --------------------------------------------------------------------------------------------

def t09_rederive_S2_dimension_measurements():
    """Re-derive every figure S2 states about team_cities.csv. AGREE or CORRECT, explicitly."""
    tc, _, _ = load_real()
    counts = tc["team_id"].value_counts()
    dup = {str(k): int(v) for k, v in counts[counts > 1].items()}
    m = {
        "rows": int(len(tc)),
        "distinct_team_id": int(tc["team_id"].nunique()),
        "duplicated_team_id": dup,
        "last_season_dtype": str(tc["last_season"].dtype),
        "last_season_nulls": int(tc["last_season"].isna().sum()),
        "elevation_ft_min": int(tc["elevation_ft"].min()),
        "elevation_ft_max": int(tc["elevation_ft"].max()),
        "rows_above_1000ft": int((tc["elevation_ft"] > 1000).sum()),
        "distinct_arenas_above_1000ft": int(tc.loc[tc["elevation_ft"] > 1000, "arena"].nunique()),
        "distinct_franchises_above_1000ft":
            int(tc.loc[tc["elevation_ft"] > 1000, "franchise"].nunique()),
        "n_columns": int(tc.shape[1]),
        "columns": list(tc.columns),
    }
    MEASURED["S2_dimension"] = m
    check(m["rows"] == 16, f"packet says 16 rows, measured {m['rows']}")
    check(m["distinct_team_id"] == 15, f"packet says 15 distinct, measured {m['distinct_team_id']}")
    check(dup == {"1611661317": 2}, f"packet says 1611661317 x2, measured {dup}")
    check(m["last_season_dtype"] == "float64", f"measured dtype {m['last_season_dtype']}")
    check(m["last_season_nulls"] == 15, f"packet says 15 nulls, measured {m['last_season_nulls']}")
    check([m["elevation_ft_min"], m["elevation_ft_max"]] == [20, 2030],
          f"packet says [20,2030], measured [{m['elevation_ft_min']},{m['elevation_ft_max']}]")
    # the packet's "4 venues above 1000ft" is a ROW count, not a VENUE count
    check(m["rows_above_1000ft"] == 4, "row count above 1000ft is not 4")
    check(m["distinct_arenas_above_1000ft"] == 3, "distinct arena count above 1000ft is not 3")
    return m


def t10_rederive_the_2982_1491_universe():
    """The universe this node must preserve, measured from the frozen artifact."""
    _, prior, u = load_real()
    tg = list(zip(u["game_id"].tolist(), u["team_id"].tolist()))
    m = {
        "prior_artifact_rows": int(len(prior)),
        "prior_artifact_games": int(prior["game_id"].nunique()),
        "restriction": "pace_resolved == True",
        "universe_rows": int(len(u)),
        "universe_game_clusters": int(u["game_id"].nunique()),
        "universe_team_game_keys": len(set(tg)),
        "duplicate_team_game_keys": int(len(tg) - len(set(tg))),
        "distinct_team_id": int(u["team_id"].nunique()),
        "seasons": sorted(int(s) for s in u["season"].unique()),
        "distinct_team_season_pairs": len(set(zip(u["team_id"].tolist(), u["season"].tolist()))),
        "rows_for_team_1611661317": int((u["team_id"] == 1611661317).sum()),
    }
    MEASURED["universe"] = m
    check(m["universe_rows"] == 2982, f"expected 2982 rows, measured {m['universe_rows']}")
    check(m["universe_game_clusters"] == 1491,
          f"expected 1491 clusters, measured {m['universe_game_clusters']}")
    check(m["duplicate_team_game_keys"] == 0, "the universe is not unique on (game_id, team_id)")
    check(m["prior_artifact_rows"] == 2990 and m["prior_artifact_games"] == 1495,
          f"unexpected parent artifact shape: {m}")
    return m


def t11_naive_join_corrupts_the_real_universe_and_the_guard_rejects_it():
    """The S2 hazard, measured on the real bytes, then blocked."""
    tc, _, u = load_real()
    naive = u.merge(tc, on="team_id", how="left")
    tg = list(zip(naive["game_id"].tolist(), naive["team_id"].tolist()))
    m = {
        "universe_rows": int(len(u)),
        "naive_left_merge_rows": int(len(naive)),
        "excess_rows": int(len(naive) - len(u)),
        "naive_game_clusters": int(naive["game_id"].nunique()),
        "duplicated_team_game_keys_after_naive_merge": int(len(tg) - len(set(tg))),
    }
    MEASURED["naive_join"] = m
    check(m["naive_left_merge_rows"] == 3228, f"measured {m['naive_left_merge_rows']}, expected 3228")
    check(m["excess_rows"] == 246, f"measured excess {m['excess_rows']}")
    check(m["naive_game_clusters"] == 1491,
          "game cluster count changed -- the fan-out signature should leave it identical")

    spec = DimensionSpec(name="team_cities__naive", left_keys=("team_id",),
                         right_keys=("team_id",), cardinality="m:1",
                         value_columns=("elevation_ft", "timezone", "lat", "lon"))
    try:
        guarded_merge(u, tc, spec)
    except MergeCardinalityFailure as e:
        check("1611661317" in str(e), f"rejection did not name the offending key: {e}")
        m["guard_rejected"] = True
    else:
        _fail("guarded_merge accepted the naive team_cities join")

    # and the universe assertion catches it independently
    uni = RowUniverse.capture(u)
    try:
        uni.assert_unchanged(naive, "naive_team_cities")
    except MergeCardinalityFailure:
        m["row_universe_assertion_rejected"] = True
    else:
        _fail("RowUniverse accepted the fanned-out real merge")
    return m


def t12_null_unsafe_filter_destroys_the_real_universe():
    """The second S2 hazard: `last_season` is float with 15/16 nulls."""
    tc, _, u = load_real()
    surviving = tc[tc["last_season"].notna()]
    inner = u.merge(surviving[["team_id", "elevation_ft"]], on="team_id", how="inner")
    m = {
        "dimension_rows": int(len(tc)),
        "rows_surviving_last_season_notna": int(len(surviving)),
        "franchises_lost": int(tc["team_id"].nunique() - surviving["team_id"].nunique()),
        "universe_rows_before": int(len(u)),
        "universe_rows_after_null_unsafe_inner_join": int(len(inner)),
        "rows_lost": int(len(u) - len(inner)),
    }
    MEASURED["null_unsafe_filter"] = m
    check(m["rows_surviving_last_season_notna"] == 1, f"measured {m}")
    check(m["franchises_lost"] == 14, f"measured {m}")
    check(m["universe_rows_after_null_unsafe_inner_join"] == 246, f"measured {m}")
    return m


def t13_season_effective_resolution_preserves_the_real_universe():
    """Criterion 5 on the real data: 1611661317 resolved from first_season/last_season only."""
    tc, _, u = load_real()
    spec = DimensionSpec(
        name="team_cities__season_effective",
        left_keys=("team_id", "season"), right_keys=("team_id", "season"),
        cardinality="m:1",
        value_columns=("abbreviation", "franchise", "city", "arena", "lat", "lon",
                       "elevation_ft", "timezone"),
        require_total_coverage=True,
        effective_from="first_season", effective_to="last_season", effective_on="season",
        open_ended_upper_bound=True,
        notes=("null last_season is DOCUMENTED as 'franchise still current at this venue', so the "
               "upper bound is open. Resolution consults first_season/last_season only; row order "
               "is never used."))
    pairs = set(zip(u["team_id"].tolist(), u["season"].tolist()))
    resolved, rres = resolve_effective_dimension(tc, spec, pairs)
    check(rres["resolved"], f"real interval resolution failed: {rres}")

    uni = RowUniverse.capture(u)
    merged, mrep = guarded_merge(u, resolved, spec, universe=uni)

    tg = list(zip(merged["game_id"].tolist(), merged["team_id"].tolist()))
    m = {
        "required_key_season_pairs": len(pairs),
        "resolved_dimension_rows": int(len(resolved)),
        "n_uncovered": rres["n_uncovered"], "n_ambiguous": rres["n_ambiguous"],
        "multi_row_keys": rres["multi_row_keys"],
        "merged_rows": int(len(merged)),
        "merged_game_clusters": int(merged["game_id"].nunique()),
        "merged_team_game_keys": len(set(tg)),
        "fan_out_rows": mrep["fan_out_rows"],
        "row_universe_preserved": mrep["row_universe"]["preserved"],
        "any_null_expansion": mrep["null_expansion"]["any_null_expansion"],
        "n_unmatched_fact_rows": mrep["null_expansion"]["n_unmatched_fact_rows"],
    }
    MEASURED["season_effective_resolution"] = m
    check(m["merged_rows"] == 2982, f"row count changed: {m}")
    check(m["merged_game_clusters"] == 1491, f"cluster count changed: {m}")
    check(m["merged_team_game_keys"] == 2982, f"team-game key set changed: {m}")
    check(m["fan_out_rows"] == 0, "fan-out occurred")
    check(m["any_null_expansion"] is False, f"unexpected null expansion: {mrep['null_expansion']}")
    check(m["n_unmatched_fact_rows"] == 0, "unmatched fact rows present")

    # the PHO/PHX split lands where the DECLARED intervals put it, not where row order would
    phx = merged[merged["team_id"] == 1611661317]
    by_season = {int(s): sorted(set(g["abbreviation"])) for s, g in phx.groupby("season")}
    m["phoenix_abbreviation_by_season"] = {str(k): v for k, v in sorted(by_season.items())}
    m["phoenix_rows"] = int(len(phx))
    check(all(v == ["PHO"] for k, v in by_season.items() if k <= 2024),
          f"pre-2025 Phoenix rows not resolved to PHO: {by_season}")
    check(all(v == ["PHX"] for k, v in by_season.items() if k >= 2025),
          f"2025+ Phoenix rows not resolved to PHX: {by_season}")
    return m


def t14_resolution_is_not_order_dependent():
    """Criterion 6 on the real data: shuffling the dimension changes nothing."""
    tc, _, u = load_real()
    spec = DimensionSpec(
        name="team_cities__shuffled", left_keys=("team_id", "season"),
        right_keys=("team_id", "season"), cardinality="m:1",
        value_columns=("abbreviation", "elevation_ft", "timezone"),
        effective_from="first_season", effective_to="last_season", effective_on="season",
        open_ended_upper_bound=True)
    pairs = set(zip(u["team_id"].tolist(), u["season"].tolist()))

    base, _ = resolve_effective_dimension(tc, spec, pairs)
    key = ["team_id", "season", "abbreviation", "elevation_ft", "timezone"]
    baseline = {(int(r[0]), int(r[1])): (r[2], int(r[3]), r[4])
                for r in base[key].itertuples(index=False, name=None)}

    n_perm = 0
    for seed in (0, 1, 2, 3, 7, 11, 13, 17):
        shuffled = tc.sample(frac=1.0, random_state=seed).reset_index(drop=True)
        res, _ = resolve_effective_dimension(shuffled, spec, pairs)
        got = {(int(r[0]), int(r[1])): (r[2], int(r[3]), r[4])
               for r in res[key].itertuples(index=False, name=None)}
        check(got == baseline, f"resolution changed under permutation seed={seed}")
        n_perm += 1

    # the contrast: what an order-dependent dedup would have produced
    naive_first = tc.drop_duplicates("team_id", keep="first")
    naive_last = tc.drop_duplicates("team_id", keep="last")
    differs = int((naive_first.set_index("team_id")["abbreviation"]
                   != naive_last.set_index("team_id")["abbreviation"]).sum())
    m = {"permutations_tested": n_perm, "resolution_invariant": True,
         "keys_where_keep_first_differs_from_keep_last": differs}
    MEASURED["order_independence"] = m
    check(differs == 1, f"expected exactly 1 order-sensitive key, measured {differs}")
    return m


def t15_packet_schema_listing_is_incomplete():
    """Contradiction check: the packet's own column listing for team_cities.csv."""
    tc, _, _ = load_real()
    pkt = (REPO / "experiments" / "player_program" / "stage2a" / "EVIDENCE_PACKET_V2.json")
    if not pkt.exists():
        _fail(f"evidence packet absent: {pkt}")
    entry = json.loads(pkt.read_text(encoding="utf-8"))[
        "cutoff_valid_availability_table_CORRECTED"]["CORRECTED_now_available"][0]
    src = entry["source"]
    listed = [c for c in tc.columns if c in src]
    m = {"packet_source_string": src,
         "actual_columns": list(tc.columns),
         "n_actual_columns": int(tc.shape[1]),
         "columns_named_in_packet": listed,
         "columns_omitted_from_packet": [c for c in tc.columns if c not in src]}
    MEASURED["packet_schema_listing"] = m
    check(m["n_actual_columns"] == 11, f"expected 11 columns, measured {m['n_actual_columns']}")
    check(set(m["columns_omitted_from_packet"]) == {"abbreviation", "timezone"},
          f"unexpected omission set: {m['columns_omitted_from_packet']}")
    return m


def t16_dimension_is_team_keyed_not_venue_of_play_keyed():
    """A cardinality-adjacent semantic fact, measured rather than assumed.

    team_cities.csv has no game-level key, so a `team_id`-keyed merge attaches each team its OWN
    arena on EVERY row, including its away rows. Turning that into a venue-of-play or travel
    feature needs a home-team (or is_home) key, which the 2,982-row universe artifact does not
    carry. This node reports the fact; it does not resolve it.
    """
    tc, _, u = load_real()
    m = {
        "team_cities_columns": list(tc.columns),
        "team_cities_has_game_key": any(c in tc.columns for c in
                                        ("game_id", "is_home", "home_team_id")),
        "universe_columns": list(u.columns),
        "universe_has_is_home": "is_home" in u.columns,
        "universe_has_opp_team_id": "opp_team_id" in u.columns,
        "universe_rows_per_game": sorted(set(u.groupby("game_id").size().tolist())),
    }
    MEASURED["venue_semantics"] = m
    check(m["team_cities_has_game_key"] is False,
          "team_cities unexpectedly carries a game-level key")
    check(m["universe_has_is_home"] is False and m["universe_has_opp_team_id"] is False,
          "the universe artifact unexpectedly carries a home/opponent key")
    check(m["universe_rows_per_game"] == [2],
          f"every game should contribute exactly 2 team rows, measured {m['universe_rows_per_game']}")
    return m


# --------------------------------------------------------------------------------------------

TESTS = [
    ("t01_spec_requires_explicit_declarations", t01_spec_requires_explicit_declarations),
    ("t02_duplicate_primary_key_is_rejected", t02_duplicate_primary_key_is_rejected),
    ("t03_fan_out_fails_the_merge", t03_fan_out_fails_the_merge),
    ("t04_row_universe_detects_every_mutation", t04_row_universe_detects_every_mutation),
    ("t05_null_expansion_is_reported", t05_null_expansion_is_reported),
    ("t06_undeclared_null_interval_is_a_hard_failure", t06_undeclared_null_interval_is_a_hard_failure),
    ("t07_interval_resolution_is_exact_or_it_raises", t07_interval_resolution_is_exact_or_it_raises),
    ("t08_no_order_dependent_dedup_in_this_node", t08_no_order_dependent_dedup_in_this_node),
    ("t09_rederive_S2_dimension_measurements", t09_rederive_S2_dimension_measurements),
    ("t10_rederive_the_2982_1491_universe", t10_rederive_the_2982_1491_universe),
    ("t11_naive_join_corrupts_the_real_universe_and_the_guard_rejects_it",
     t11_naive_join_corrupts_the_real_universe_and_the_guard_rejects_it),
    ("t12_null_unsafe_filter_destroys_the_real_universe", t12_null_unsafe_filter_destroys_the_real_universe),
    ("t13_season_effective_resolution_preserves_the_real_universe",
     t13_season_effective_resolution_preserves_the_real_universe),
    ("t14_resolution_is_not_order_dependent", t14_resolution_is_not_order_dependent),
    ("t15_packet_schema_listing_is_incomplete", t15_packet_schema_listing_is_incomplete),
    ("t16_dimension_is_team_keyed_not_venue_of_play_keyed",
     t16_dimension_is_team_keyed_not_venue_of_play_keyed),
]


def main() -> int:
    n_fail = 0
    for name, fn in TESTS:
        try:
            detail = fn()
            RESULTS.append({"test": name, "status": "PASS", "detail": detail})
            print(f"PASS  {name}")
        except Exception as e:  # noqa: BLE001
            n_fail += 1
            RESULTS.append({"test": name, "status": "FAIL", "error": f"{type(e).__name__}: {e}",
                            "traceback": traceback.format_exc()})
            print(f"FAIL  {name}\n      {type(e).__name__}: {e}")
    out = HERE / "TEST_RESULTS.json"
    out.write_text(json.dumps({"n_tests": len(TESTS), "n_failed": n_fail,
                               "results": RESULTS, "measurements": MEASURED},
                              indent=2, default=str), encoding="utf-8")
    print(f"\n{len(TESTS) - n_fail}/{len(TESTS)} passed; results -> {out}")
    return 1 if n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
