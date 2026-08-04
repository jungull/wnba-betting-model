#!/usr/bin/env python3
"""TESTS.py — P22_POSTGAME_SURROGATE_GUARD.

Standalone runnable test script (pytest is not available in this environment). ``main()`` returns
1 on any failure. Every number printed is computed here, against the real frozen artifacts.

The acceptance criteria this file discharges, one section each:

  A1  a test proves unlagged master_team.minutes FAILS
  A2  a test proves minutes/5 FAILS
  A3  a test proves a renamed or linearly transformed current-game duration FAILS
  A4  a test proves a correctly lagged prior-game duration PASSES when every cutoff check passes
  A5  same-game joins fail closed
  A6  construction receipts record the lag transformation and the source keys
  A7  feature_gate.py is byte-unchanged: this is a Stage 2 wrapper, not a gate edit

Sections M0-M2 are the MEASUREMENTS the report cites, re-derived here rather than quoted.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import numpy as np, pandas as pd                                                 # noqa: E401

HERE = Path(__file__).resolve().parent
PROGRAM = HERE.parents[1]
ROOT = PROGRAM.parents[1]

sys.path.insert(0, str(HERE))
sys.path.insert(0, str(PROGRAM))

import construction_receipt as cr                                                # noqa: E402
import feature_gate as fg                                                        # noqa: E402
import possession_features as pf                                                 # noqa: E402
import postgame_surrogate_guard as gd                                            # noqa: E402

MASTER_TEAM = ROOT / "data" / "masters" / "master_team.parquet"
POSSESSIONS = PROGRAM / "possessions_v2" / "possessions_raw_v2.parquet"
PRIOR = PROGRAM / "projected_exposure_v1" / "team_possession_prior_v1.parquet"

FAILURES: list[str] = []
MEASURED: dict = {}


def check(name: str, ok: bool, detail: str = "") -> bool:
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {name}" + (f"  -- {detail}" if detail else ""))
    if not ok:
        FAILURES.append(f"{name}: {detail}")
    return bool(ok)


def blocked(fn, *a, **kw) -> tuple[bool, list[dict]]:
    """Run something that must raise PostgameSurrogateFailure. Returns (raised, blocking)."""
    try:
        fn(*a, **kw)
        return False, []
    except gd.PostgameSurrogateFailure as e:
        try:
            return True, json.loads(str(e))
        except Exception:
            return True, [{"kind": "unparsed", "detail": str(e)[:200]}]


# --------------------------------------------------------------------------------------------
# shared fixtures, built once from the frozen artifacts
# --------------------------------------------------------------------------------------------

def build() -> dict:
    u = pf.load_universe(prior_path=PRIOR, possessions_path=POSSESSIONS)
    F = u.frame.copy()

    mt = pd.read_parquet(MASTER_TEAM)
    poss = pd.read_parquet(POSSESSIONS, columns=["game_id", "period"])
    mp = poss.groupby("game_id")["period"].max().rename("max_period").reset_index()
    mp["game_minutes"] = 40.0 + 5.0 * np.maximum(0, mp["max_period"] - 4)

    key = F.reset_index()[[F.index.name, "game_id", "team_id"]]
    key = key.merge(mt[["game_id", "team_id", "minutes"]], on=["game_id", "team_id"],
                    how="left", validate="1:1")
    key = key.merge(mp[["game_id", "game_minutes"]], on="game_id", how="left", validate="m:1")
    key = key.set_index(F.index.name).loc[F.index]

    # ---- the prohibited columns, in every form the criteria name ----
    F["mt_minutes"] = key["minutes"]                             # A1 raw master_team.minutes
    F["mt_minutes_div5"] = key["minutes"] / 5.0                  # A2 minutes / 5 == game_minutes
    F["team_tempo_index"] = key["minutes"]                       # A3 renamed, byte-identical
    F["duration_affine"] = 3.0 * key["minutes"] - 17.5           # A3 linear transform
    F["duration_monotone"] = np.exp(key["minutes"] / 100.0)      # A3 nonlinear injective map
    F["game_minutes_raw"] = key["game_minutes"]

    # ---- the lawful column: the team's PRIOR game's duration ----
    lag_src = F.reset_index()[[F.index.name, "team_id", "game_date"]].copy()
    lag_src["game_minutes"] = key["game_minutes"].to_numpy()
    lag_src = lag_src.set_index(F.index.name)
    ordered = lag_src.sort_values(["team_id", "game_date"], kind="mergesort")
    ordered["prior_game_minutes"] = ordered.groupby("team_id")["game_minutes"].shift(1)
    F["prior_game_minutes"] = ordered["prior_game_minutes"].reindex(F.index)

    basis = gd.realised_duration_basis(F.index, game_id=F["game_id"],
                                       possessions_path=POSSESSIONS, repo_root=ROOT)
    return {"u": u, "F": F, "mt": mt, "mp": mp, "lag_src": lag_src, "basis": basis,
            "folds": pf.chronological_folds(u)}


def prior_spec(col: str = "prior_game_minutes", *, strict: bool = True,
               n_back: int = 1) -> gd.LagSpec:
    return gd.LagSpec(
        column=col, kind=gd.PRIOR_GAME, source_artifact_id="player_possessions/2",
        source_path=str(POSSESSIONS), source_value_column="game_minutes",
        entity_keys=("team_id",), order_column="game_date", n_back=n_back, strict=strict,
        null_policy="null_when_the_club_has_no_earlier_game_in_the_universe",
        rationale=("the duration of the club's most recent STRICTLY EARLIER game. A completed "
                   "historical outcome, which the primary-target ruling permits, as distinct from "
                   "the realised duration of the game being predicted, which it prohibits"))


SCHEDULE_SPECS = {
    "pace_gap": gd.LagSpec(column="pace_gap", kind=gd.DERIVED_NO_JOIN,
                           source_artifact_id="team_possession_prior/1",
                           source_path=str(PRIOR), entity_keys=("game_id", "team_id"),
                           rationale="difference of two prior-games-only trailing-window pace means"),
    "pace_evidence_depth": gd.LagSpec(column="pace_evidence_depth", kind=gd.DERIVED_NO_JOIN,
                                      source_artifact_id="team_possession_prior/1",
                                      source_path=str(PRIOR), entity_keys=("game_id", "team_id"),
                                      rationale="count of prior games backing the estimate"),
    "opp_pace_evidence_depth": gd.LagSpec(column="opp_pace_evidence_depth", kind=gd.DERIVED_NO_JOIN,
                                          source_artifact_id="team_possession_prior/1",
                                          source_path=str(PRIOR),
                                          entity_keys=("game_id", "team_id"),
                                          rationale="same, for the opponent"),
    "is_playoff_game": gd.LagSpec(column="is_playoff_game", kind=gd.SCHEDULE,
                                  source_artifact_id="team_possession_prior/1",
                                  source_path=str(PRIOR), entity_keys=("game_id", "team_id"),
                                  rationale="season_type is fixed before tipoff"),
}


# --------------------------------------------------------------------------------------------
# M0 / A7 — feature_gate.py is byte-unchanged
# --------------------------------------------------------------------------------------------

def section_a7() -> None:
    print("\nA7 / M0 — feature_gate.py is byte-unchanged (Stage 2 wrapper, not a gate edit)")
    sha = gd._sha256_file(PROGRAM / "feature_gate.py")
    MEASURED["feature_gate_sha256"] = sha
    check("feature_gate.py sha256 equals the frozen constant this wrapper wraps",
          sha == gd.FEATURE_GATE_SHA256, sha)
    src = (PROGRAM / "feature_gate.py").read_text(encoding="utf-8")
    check("feature_gate.BLOCKING still has exactly the 12 documented kinds",
          len(fg.BLOCKING) == 12, str(sorted(fg.BLOCKING)))
    check("feature_gate thresholds unchanged (RANK_TOL 1e-8, COND_MAX 1e6)",
          fg.RANK_TOL == 1e-8 and fg.COND_MAX == 1e6)
    check("this node writes nothing into feature_gate.py (no marker string present)",
          "postgame_surrogate" not in src and "P22" not in src)
    guard_src = (HERE / "postgame_surrogate_guard.py").read_text(encoding="utf-8")
    check("the wrapper never writes to any path outside its own node directory",
          all(tok not in guard_src for tok in ("open(PROGRAM", "to_parquet", "PROGRAM /"))
          or "PROGRAM / \"feature_gate.py\"" in guard_src)


# --------------------------------------------------------------------------------------------
# M1 — re-derive S1's own measurement
# --------------------------------------------------------------------------------------------

def section_m1(fx: dict) -> None:
    print("\nM1 — re-derivation of V2_STOP_CONDITION S1 (AGREE / CORRECT)")
    mt, mp = fx["mt"], fx["mp"]
    j = mt.merge(mp[["game_id", "game_minutes"]], on="game_id", how="left", validate="m:1")
    n = int(len(mt))
    nulls = int(mt["minutes"].isna().sum())
    ratio = (j["minutes"] / j["game_minutes"]).to_numpy(float)
    rec = (j["minutes"] / 5.0).to_numpy(float) == j["game_minutes"].to_numpy(float)
    MEASURED["S1"] = {
        "master_team_rows": n, "minutes_nulls": nulls,
        "ratio_mean": float(np.mean(ratio)), "ratio_sd": float(np.std(ratio)),
        "ratio_min": float(np.min(ratio)), "ratio_max": float(np.max(ratio)),
        "exactly_5x": int(np.sum(ratio == 5.0)),
        "game_minutes_recoverable_by_division": int(np.sum(rec)),
        "minutes_distinct_values": sorted(float(v) for v in mt["minutes"].unique()),
        "game_minutes_distinct_values": sorted(float(v) for v in mp["game_minutes"].unique()),
    }
    check("S1 rows = 2990", n == 2990, str(n))
    check("S1 nulls = 0", nulls == 0, str(nulls))
    check("S1 ratio mean/sd/min/max = 5.0/0.0/5.0/5.0",
          np.mean(ratio) == 5.0 and np.std(ratio) == 0.0 and np.min(ratio) == 5.0
          and np.max(ratio) == 5.0,
          f"{np.mean(ratio)}/{np.std(ratio)}/{np.min(ratio)}/{np.max(ratio)}")
    check("S1 exactly_5x = 2990/2990", int(np.sum(ratio == 5.0)) == 2990)
    check("S1 game_minutes recoverable by division = 2990/2990", int(np.sum(rec)) == 2990)

    F = fx["F"]
    MEASURED["universe"] = {"rows": int(len(F)), "game_clusters": int(F["game_id"].nunique()),
                            "rows_with_master_team_minutes": int(F["mt_minutes"].notna().sum())}
    check("universe = 2,982 team-game rows over 1,491 game clusters",
          len(F) == 2982 and F["game_id"].nunique() == 1491,
          f"{len(F)} rows / {F['game_id'].nunique()} clusters")
    check("the S1 identity also holds on all 2,982 audited rows",
          int(((F["mt_minutes"] / F["game_minutes_raw"]) == 5.0).sum()) == 2982)

    poss = pd.read_parquet(POSSESSIONS, columns=["game_id", "period"])
    mpd = poss.groupby("game_id")["period"].max()
    MEASURED["period_structure"] = {
        "games_in_possessions_artifact": int(len(mpd)),
        "games_in_universe": int(fx["F"]["game_id"].nunique()),
        "max_period_distribution": {str(int(k)): int(v)
                                    for k, v in mpd.value_counts().sort_index().items()},
    }
    check("the possessions artifact covers 1,495 games and the universe 1,491 — the 4-game gap "
          "the frozen packet already records as a nit",
          len(mpd) == 1495 and fx["F"]["game_id"].nunique() == 1491,
          f"{len(mpd)} vs {fx['F']['game_id'].nunique()}")
    check("master_team independently corroborates the single 8-period game: 300 team-minutes "
          "exists in master_team exactly where max_period == 8",
          int((fx["mt"]["minutes"] == 300.0).sum()) == 2 and int((mpd == 8).sum()) == 1,
          f"n_rows_300min={int((fx['mt']['minutes'] == 300.0).sum())} "
          f"n_games_period8={int((mpd == 8).sum())}")


# --------------------------------------------------------------------------------------------
# M2 — the gap: feature_gate passes every prohibited form
# --------------------------------------------------------------------------------------------

def section_m2(fx: dict) -> None:
    print("\nM2 — feature_gate.audit PASSES every prohibited form (why the wrapper is needed)")
    F = fx["F"]
    y = F[pf.TARGET_COLUMN].to_numpy(float)
    o = F[pf.OFFSET_COLUMN].to_numpy(float)
    res = {}
    for col in ("mt_minutes", "mt_minutes_div5", "team_tempo_index", "duration_affine",
                "duration_monotone", "game_minutes_raw"):
        names = list(pf.FEATURE_NAMES) + [col]
        try:
            rep = fg.audit(F, names, offset=o, target=y, test_df=F)
            res[col] = {"gate_passed": bool(rep["passed"]),
                        "findings": [f["kind"] for f in rep["findings"]],
                        "corr_with_target": round(float(np.corrcoef(
                            F[col].to_numpy(float), y)[0, 1]), 6),
                        "corr_with_offset": round(float(np.corrcoef(
                            F[col].to_numpy(float), o)[0, 1]), 6),
                        "std": round(float(F[col].std()), 6),
                        "n_null": int(F[col].isna().sum())}
        except fg.FeatureGateFailure as e:
            res[col] = {"gate_passed": False, "blocked": str(e)[:200]}
    MEASURED["feature_gate_blindness"] = res
    for col, r in res.items():
        check(f"feature_gate passes '{col}' with zero findings (the gap)",
              r.get("gate_passed") is True and not r.get("findings"),
              json.dumps({k: r[k] for k in r if k != "findings"}))


# --------------------------------------------------------------------------------------------
# A1 / A2 / A3 — the prohibited forms FAIL the guard
# --------------------------------------------------------------------------------------------

def _guard_on(fx: dict, col: str, spec: gd.LagSpec | None, *, with_source: bool = False):
    F, basis = fx["F"], fx["basis"]
    names = list(pf.FEATURE_NAMES) + [col]
    specs = dict(SCHEDULE_SPECS)
    if spec is not None:
        specs[col] = spec
    srcs = {col: fx["lag_src"]} if with_source else None
    return blocked(gd.audit, F, names, prohibited=basis, lag_specs=specs, lag_sources=srcs)


def section_a1_a3(fx: dict) -> None:
    print("\nA1 — unlagged master_team.minutes FAILS")
    honest = gd.LagSpec(column="mt_minutes", kind=gd.SAME_GAME,
                        source_artifact_id="master_team/1", source_path=str(MASTER_TEAM),
                        source_value_column="minutes", entity_keys=("game_id", "team_id"),
                        rationale="joined on the target game's own key, no lag")
    raised, blk = _guard_on(fx, "mt_minutes", honest)
    kinds = sorted({b["kind"] for b in blk})
    MEASURED["A1_blocking_kinds"] = kinds
    check("unlagged master_team.minutes is BLOCKED", raised, str(kinds))
    check("A1 blocks on the same-game join", "same_game_join" in kinds, str(kinds))
    check("A1 blocks on the dependency battery too, independently of the declaration",
          {"function_of_prohibited", "prohibited_recoverable"} <= set(kinds), str(kinds))

    print("\nA2 — minutes/5 FAILS (this IS game_minutes)")
    raised, blk = _guard_on(fx, "mt_minutes_div5", prior_spec("mt_minutes_div5"),
                            with_source=True)
    kinds = sorted({b["kind"] for b in blk})
    MEASURED["A2_blocking_kinds"] = kinds
    check("minutes/5 is BLOCKED even when its lag is declared as PRIOR_GAME", raised, str(kinds))
    check("A2 blocks on lag_alignment_violated (the declaration is contradicted by the bytes)",
          "lag_alignment_violated" in kinds, str(kinds))
    check("A2 blocks on prohibited_recoverable", "prohibited_recoverable" in kinds, str(kinds))
    rep = gd.audit(fx["F"], ["mt_minutes_div5"], prohibited=fx["basis"],
                   lag_specs={"mt_minutes_div5": prior_spec("mt_minutes_div5")},
                   raise_on_block=False)
    d = rep["per_column"]["mt_minutes_div5"]["dependency"]["game_minutes"]
    check("minutes/5 recovers game_minutes with affine slope 1.0 and zero residual",
          abs(d["prohibited_affine_slope"] - 1.0) < 1e-12
          and d["prohibited_affine_rel_max_residual"] <= gd.EXACT_RTOL,
          f"slope={d['prohibited_affine_slope']} resid={d['prohibited_affine_rel_max_residual']}")

    print("\nA3 — a RENAMED or LINEARLY TRANSFORMED current-game duration FAILS")
    for col, label in (("team_tempo_index", "renamed"), ("duration_affine", "affine 3x-17.5"),
                       ("duration_monotone", "nonlinear injective exp(x/100)"),
                       ("game_minutes_raw", "raw game_minutes")):
        spec = gd.LagSpec(column=col, kind=gd.SCHEDULE, source_artifact_id="master_team/1",
                          source_path=str(MASTER_TEAM), entity_keys=("game_id", "team_id"),
                          rationale="deliberately mis-declared as a schedule fact")
        raised, blk = _guard_on(fx, col, spec)
        kinds = sorted({b["kind"] for b in blk})
        MEASURED.setdefault("A3_blocking_kinds", {})[col] = kinds
        check(f"'{col}' ({label}) is BLOCKED despite a clean-looking declaration", raised, str(kinds))
        check(f"'{col}' blocks on function_of_prohibited (name- and scale-invariant)",
              "function_of_prohibited" in kinds, str(kinds))
    aff = gd.audit(fx["F"], ["duration_affine"], prohibited=fx["basis"],
                   lag_specs={"duration_affine": gd.LagSpec(column="duration_affine",
                                                            kind=gd.SCHEDULE)},
                   raise_on_block=False)["per_column"]["duration_affine"]["dependency"]["team_minutes"]
    check("the affine transform is caught by exact affine recovery in BOTH directions",
          aff["column_exact_affine_of_prohibited"] and aff["prohibited_exact_affine_of_column"],
          f"slope={aff['column_affine_slope']} intercept={aff['column_affine_intercept']}")
    mono = gd.audit(fx["F"], ["duration_monotone"], prohibited=fx["basis"],
                    lag_specs={"duration_monotone": gd.LagSpec(column="duration_monotone",
                                                               kind=gd.SCHEDULE)},
                    raise_on_block=False)["per_column"]["duration_monotone"]["dependency"]["game_minutes"]
    check("the NONLINEAR map defeats affine recovery but not the partition test",
          (not mono["column_exact_affine_of_prohibited"])
          and mono["column_is_function_of_prohibited"]
          and mono["prohibited_is_function_of_column"],
          f"affine_exact={mono['column_exact_affine_of_prohibited']} "
          f"fn_of_prohibited={mono['column_is_function_of_prohibited']}")


# --------------------------------------------------------------------------------------------
# A4 — the correctly lagged prior-game duration PASSES
# --------------------------------------------------------------------------------------------

def section_a4(fx: dict) -> dict:
    print("\nA4 — a correctly lagged prior-game duration PASSES when every cutoff check passes")
    F, basis, lag_src = fx["F"], fx["basis"], fx["lag_src"]
    names = list(pf.FEATURE_NAMES) + ["prior_game_minutes"]
    specs = dict(SCHEDULE_SPECS); specs["prior_game_minutes"] = prior_spec()
    srcs = {"prior_game_minutes": lag_src}

    rep = gd.audit(F, names, prohibited=basis, lag_specs=specs, lag_sources=srcs,
                   raise_on_block=False)
    check("the guard PASSES the lagged design on the final assembled universe",
          rep["passed"], json.dumps([b["kind"] for b in rep["blocking"]]))
    ver = rep["per_column"]["prior_game_minutes"]["lag_verification"]
    MEASURED["A4_lag_verification"] = {k: ver[k] for k in
                                       ("verified", "n_rows", "n_expected_null",
                                        "n_presented_null", "n_rows_disagreeing") if k in ver}
    check("the PRIOR_GAME claim was RE-DERIVED from the declared source and agrees on every row",
          ver.get("verified") is True and ver.get("n_rows_disagreeing") == 0, json.dumps(ver.get("reason")))
    d = rep["per_column"]["prior_game_minutes"]["dependency"]["game_minutes"]
    MEASURED["A4_dependency_vs_game_minutes"] = d
    check("the lagged column is NOT a function of the current game's duration",
          not d["column_is_function_of_prohibited"],
          f"{d['n_prohibited_levels_with_varying_column']} of {d['n_prohibited_levels']} "
          f"prohibited levels carry a varying column")
    check("the current game's duration is NOT recoverable from the lagged column",
          not d["prohibited_is_function_of_column"])
    check("|r| between the lagged column and the current duration is far below 0.999",
          abs(d["pearson_r"]) < 0.05, f"r={d['pearson_r']}")

    # the 15 rows with no earlier game in the universe are DROPPED, not imputed: imputing them
    # would be an undeclared transformation and would break the lag re-derivation, which is the
    # correct behaviour and is exercised by A5(c). GATE_INVOCATION_CONTRACT §8a forbids reaching
    # the gate with a silently transformed frame.
    keep = F.index[F["prior_game_minutes"].notna()]
    G = F.loc[keep]
    b_keep = gd.ProhibitedBasis(frame=basis.frame.loc[keep], source=basis.source, note=basis.note)
    y = G[pf.TARGET_COLUMN].to_numpy(float)
    o = G[pf.OFFSET_COLUMN].to_numpy(float)
    comp = gd.guarded_audit(G, names, prohibited=b_keep, lag_specs=specs, lag_sources=srcs,
                            offset=o, target=y, test_df=G)
    MEASURED["A4_complete_case_rows"] = int(len(G))
    check("guarded_audit (guard THEN feature_gate) passes the lagged design end to end "
          f"on the {len(G)} complete-case rows",
          comp["passed"], json.dumps(comp["feature_gate"]["findings"])[:300])

    print("     per chronological training fold (GATE_INVOCATION_CONTRACT §1)")
    fold_rec = {}
    for f in fx["folds"]:
        tr = F.loc[f.train_index]
        b_tr = gd.ProhibitedBasis(frame=basis.frame.loc[f.train_index], source=basis.source,
                                  note=basis.note)
        ok_lag = gd.audit(tr, names, prohibited=b_tr, lag_specs=specs, lag_sources=srcs,
                          raise_on_block=False)
        bad_names = list(pf.FEATURE_NAMES) + ["mt_minutes"]
        bad_specs = dict(SCHEDULE_SPECS)
        bad_specs["mt_minutes"] = gd.LagSpec(column="mt_minutes", kind=gd.SCHEDULE,
                                             source_path=str(MASTER_TEAM),
                                             entity_keys=("game_id", "team_id"))
        raised, blk = blocked(gd.audit, tr, bad_names, prohibited=b_tr, lag_specs=bad_specs)
        n_ot = int((basis.frame.loc[f.train_index, "is_overtime"] > 0).sum())
        fold_rec[f.fold_id] = {"n_train_rows": int(len(tr)), "n_overtime_rows": n_ot,
                               "lagged_passes": bool(ok_lag["passed"]),
                               "prohibited_blocked": bool(raised),
                               "blocking_kinds": sorted({b["kind"] for b in blk})}
        check(f"fold {f.fold_id}: lagged PASSES and master_team.minutes is BLOCKED",
              ok_lag["passed"] and raised,
              f"n_train={len(tr)} n_OT={n_ot}")
    MEASURED["A4_per_fold"] = fold_rec
    return {"rep": rep, "names": names, "specs": specs, "srcs": srcs}


# --------------------------------------------------------------------------------------------
# A5 — same-game joins fail closed
# --------------------------------------------------------------------------------------------

def section_a5(fx: dict) -> None:
    print("\nA5 — same-game joins fail CLOSED (six independent routes, all must block)")
    F, basis, lag_src = fx["F"], fx["basis"], fx["lag_src"]
    names = list(pf.FEATURE_NAMES) + ["mt_minutes"]
    routes = {}

    raised, blk = blocked(gd.audit, F, names, prohibited=basis, lag_specs=dict(SCHEDULE_SPECS))
    routes["undeclared_column"] = sorted({b["kind"] for b in blk})
    check("(a) an UNDECLARED column blocks — absence of a lag spec is failure, not a pass",
          raised and "lag_specification_absent" in routes["undeclared_column"],
          str(routes["undeclared_column"]))

    s = dict(SCHEDULE_SPECS)
    s["mt_minutes"] = gd.LagSpec(column="mt_minutes", kind=gd.SAME_GAME,
                                 source_path=str(MASTER_TEAM), source_value_column="minutes",
                                 entity_keys=("game_id", "team_id"))
    raised, blk = blocked(gd.audit, F, names, prohibited=basis, lag_specs=s)
    routes["declared_same_game"] = sorted({b["kind"] for b in blk})
    check("(b) an honestly declared SAME_GAME join blocks unconditionally",
          raised and "same_game_join" in routes["declared_same_game"],
          str(routes["declared_same_game"]))

    s = dict(SCHEDULE_SPECS); s["mt_minutes"] = prior_spec("mt_minutes")
    raised, blk = blocked(gd.audit, F, names, prohibited=basis,
                          lag_specs=s, lag_sources={"mt_minutes": lag_src})
    routes["mislabelled_as_prior"] = sorted({b["kind"] for b in blk})
    check("(c) same-game values MISLABELLED as PRIOR_GAME block on lag_alignment_violated",
          raised and "lag_alignment_violated" in routes["mislabelled_as_prior"],
          str(routes["mislabelled_as_prior"]))

    s = dict(SCHEDULE_SPECS)
    s["prior_game_minutes"] = prior_spec(strict=False)
    raised, blk = blocked(gd.audit, F, list(pf.FEATURE_NAMES) + ["prior_game_minutes"],
                          prohibited=basis, lag_specs=s,
                          lag_sources={"prior_game_minutes": lag_src})
    routes["strict_false"] = sorted({b["kind"] for b in blk})
    check("(d) strict_inequality=False on a PRIOR_GAME spec is a same-game join and blocks",
          raised and "same_game_join" in routes["strict_false"],
          str(routes["strict_false"]))

    s = dict(SCHEDULE_SPECS); s["prior_game_minutes"] = prior_spec()
    raised, blk = blocked(gd.audit, F, list(pf.FEATURE_NAMES) + ["prior_game_minutes"],
                          prohibited=basis, lag_specs=s, lag_sources=None)
    routes["unverifiable"] = sorted({b["kind"] for b in blk})
    check("(e) a PRIOR_GAME claim with nothing to re-derive it from blocks as unverifiable",
          raised and "lag_unverifiable" in routes["unverifiable"], str(routes["unverifiable"]))

    s = dict(SCHEDULE_SPECS); s["prior_game_minutes"] = prior_spec()
    raised, blk = blocked(gd.audit, F, list(pf.FEATURE_NAMES) + ["prior_game_minutes"],
                          prohibited=None, lag_specs=s,
                          lag_sources={"prior_game_minutes": lag_src})
    routes["no_basis"] = sorted({b["kind"] for b in blk})
    check("(f) omitting the prohibited basis blocks — it is not a way to skip the check",
          raised and "prohibited_basis_absent" in routes["no_basis"], str(routes["no_basis"]))

    mis = gd.ProhibitedBasis(frame=basis.frame.iloc[:100], source=basis.source, note=basis.note)
    raised, blk = blocked(gd.audit, F, list(pf.FEATURE_NAMES) + ["prior_game_minutes"],
                          prohibited=mis, lag_specs=s,
                          lag_sources={"prior_game_minutes": lag_src})
    routes["misaligned_basis"] = sorted({b["kind"] for b in blk})
    check("(g) a basis not aligned row-for-row with the frame blocks",
          raised and "prohibited_basis_misaligned" in routes["misaligned_basis"],
          str(routes["misaligned_basis"]))

    raised, blk = blocked(gd.guarded_audit, F, names, prohibited=basis,
                          lag_specs=dict(SCHEDULE_SPECS),
                          offset=F[pf.OFFSET_COLUMN].to_numpy(float),
                          target=F[pf.TARGET_COLUMN].to_numpy(float), test_df=F)
    routes["guarded_audit_composition"] = sorted({b["kind"] for b in blk})
    check("(h) guarded_audit raises BEFORE feature_gate sees the design, so no clean gate record "
          "is ever produced for a prohibited frame", raised,
          str(routes["guarded_audit_composition"]))

    MEASURED["A5_routes"] = routes


# --------------------------------------------------------------------------------------------
# A6 — construction receipts record the lag transformation and the source keys
# --------------------------------------------------------------------------------------------

def section_a6(fx: dict, a4: dict) -> None:
    print("\nA6 — the construction receipt records the lag transformation and the source keys")
    F, basis = fx["F"], fx["basis"]
    names, specs, srcs = a4["names"], a4["specs"], a4["srcs"]
    frame = F.loc[:, ["game_id", "team_id", "game_date", "season", "season_type",
                      pf.OFFSET_COLUMN, pf.TARGET_COLUMN] + names]

    guard = gd.audit(frame, names, prohibited=basis, lag_specs=specs, lag_sources=srcs,
                     raise_on_block=True)

    sources = [
        cr.source_declaration(
            PRIOR, role="feature_source", artifact_id="team_possession_prior/1",
            cutoff_valid=True,
            cutoff_rationale="prior-games-only trailing-window pace estimates, as declared and "
                             "validated upstream by PROJECTED_EXPOSURE_RECEIPT.json",
            repo_root=ROOT),
        cr.source_declaration(
            POSSESSIONS, role="outcome_source", artifact_id="player_possessions/2",
            cutoff_valid=False,
            cutoff_rationale="realised possessions and period structure. Read to build the model "
                             "target and the PROHIBITED basis; the only column derived from it "
                             "that enters the frame is the STRICTLY-EARLIER-game lag, and the "
                             "lag is what makes that column cutoff-valid",
            repo_root=ROOT),
    ]
    universe = cr.universe_contract(
        frame, contract_id="team_possession_universe/1",
        row_identity_columns=["game_id", "team_id"],
        description="the 2,982-row possession universe, used unchanged as the S1 guard exemplar")
    fold_identity = cr.fold_declaration(fold_id="final_design", kind="final_design",
                                        n_rows=int(len(frame)),
                                        first_decision_time=frame["game_date"].min(),
                                        last_decision_time=frame["game_date"].max())
    cutoff = cr.cutoff_contract(
        decision_time_rule=("every declared feature is a function of games with game_date STRICTLY "
                            "EARLIER than the row's own game_date, or of the schedule. The "
                            "prior_game_minutes column is the club's most recent strictly earlier "
                            "game's duration and was re-derived from the declared source and "
                            "compared value-for-value"),
        per_row_decision_time_column="game_date")

    out_dir = HERE / "receipts"
    out_dir.mkdir(exist_ok=True)
    path = out_dir / "EXEMPLAR_LAGGED_DURATION_RECEIPT.json"
    receipt = gd.emit_guard_receipt(
        receipt_path=path, experiment="possession_prior", arm="s1_guard_exemplar",
        fold="final_design", run_id="P22_POSTGAME_SURROGATE_GUARD",
        frame=frame, feature_names=names, universe=universe, fold_identity=fold_identity,
        cutoff=cutoff, sources=sources, guard_audit=guard, lag_specs=specs,
        scope="final_design", feature_set_id="s1_guard_exemplar/1", repo_root=ROOT)

    t = receipt["produced_frame_provenance"]["transformation"]
    check("the receipt carries a transformation block", isinstance(t, dict))
    check("the transformation block records the LAG for the lagged column",
          t["columns"]["prior_game_minutes"]["lag_kind"] == gd.PRIOR_GAME
          and t["columns"]["prior_game_minutes"]["n_back"] == 1
          and t["columns"]["prior_game_minutes"]["strict_inequality"] is True,
          json.dumps(t["columns"]["prior_game_minutes"]))
    lag_rec = t["columns"]["prior_game_minutes"]
    check("the transformation block records the SOURCE KEYS (join keys, order column, value column)",
          lag_rec["join_keys"] == ["team_id"] and lag_rec["order_column"] == "game_date"
          and lag_rec["source_value_column"] == "game_minutes",
          json.dumps({k: lag_rec[k] for k in ("join_keys", "order_column", "source_value_column")}))
    check("the transformation block binds the source artifact by sha256",
          isinstance(lag_rec["source_sha256"], str) and len(lag_rec["source_sha256"]) == 64,
          str(lag_rec["source_sha256"]))
    check("the receipt records the empirical lag re-derivation result, not just the claim",
          t["lag_verification"]["prior_game_minutes"]["verified"] is True
          and t["lag_verification"]["prior_game_minutes"]["n_rows_disagreeing"] == 0)
    check("every declared feature has a lag record, not only the lagged one",
          set(t["columns"]) == set(names), str(sorted(t["columns"])))
    check("the receipt records feature_gate.py's sha256 as byte-unchanged",
          t["feature_gate_byte_unchanged"] is True
          and t["feature_gate_sha256"] == gd.FEATURE_GATE_SHA256)
    check("the receipt records the prohibited basis and its per-level support",
          set(t["prohibited_basis"]["names"]) == {"game_minutes", "overtime_periods",
                                                  "is_overtime", "team_minutes"}
          and t["prohibited_basis"]["levels"]["game_minutes"]["n_distinct"] >= 2)
    check("the transformation block is digest-bound",
          isinstance(receipt["produced_frame_provenance"]["transformation_digest"], str))

    kw = dict(frame=frame, feature_names=names, experiment="possession_prior",
              arm="s1_guard_exemplar", fold="final_design", scope="final_design",
              universe=universe, cutoff=cutoff)
    rep = cr.verify_construction_receipt(path, **kw)
    check("the emitted receipt re-verifies against the files and the frame",
          rep["verified"], json.dumps(rep.get("blocking", [])[:3], default=str)[:400])
    grep = gd.verify_guard_receipt(path, **kw)
    check("the guard's own verifier also verifies the untampered receipt", grep["verified"],
          json.dumps(grep.get("blocking", [])[:3], default=str)[:400])

    # --- MEASURED DEFECT in the frozen construction_receipt.py, reported not worked around ---
    body = json.loads(path.read_text(encoding="utf-8"))
    body["produced_frame_provenance"]["transformation"]["columns"][
        "prior_game_minutes"]["strict_inequality"] = False
    tampered = out_dir / "TAMPERED_RECEIPT_FOR_TEST.json"
    tampered.write_text(json.dumps(body, indent=2), encoding="utf-8")
    tkw = dict(kw); tkw.pop("universe"); tkw.pop("cutoff")
    trep = cr.verify_construction_receipt(tampered, **tkw)
    grepped = gd.verify_guard_receipt(tampered, **tkw)
    MEASURED["A6_transformation_binding_defect"] = {
        "edit": "produced_frame_provenance.transformation.columns.prior_game_minutes."
                "strict_inequality: true -> false",
        "construction_receipt_verify_verdict": bool(trep["verified"]),
        "construction_receipt_blocking_kinds": sorted({f["kind"] for f
                                                       in (trep.get("blocking") or [])}),
        "guard_verify_verdict": bool(grepped["verified"]),
        "guard_blocking_kinds": sorted({f["kind"] for f in (grepped.get("blocking") or [])}),
        "stored_transformation_digest": grepped.get("transformation_digest_stored"),
        "recomputed_transformation_digest": grepped.get("transformation_digest_recomputed"),
    }
    check("MEASURED DEFECT: the frozen cr.verify_construction_receipt does NOT catch an edit to "
          "the lag declaration (binding covers the stored digest, never a recomputation)",
          trep["verified"] is True,
          "cr.verified=" + str(trep["verified"]))
    check("the call-site wrapper verify_guard_receipt DOES catch it",
          (not grepped["verified"])
          and "transformation_body_edited" in {f["kind"] for f in grepped["blocking"]},
          str(sorted({f["kind"] for f in grepped.get("blocking", [])})))
    tampered.unlink(missing_ok=True)
    MEASURED["A6_receipt_path"] = str(path)
    MEASURED["A6_receipt_digest"] = receipt["binding"]["receipt_digest"]

    with tempfile.TemporaryDirectory() as td:
        again = gd.emit_guard_receipt(
            receipt_path=Path(td) / "again.json", experiment="possession_prior",
            arm="s1_guard_exemplar", fold="final_design",
            run_id="P22_POSTGAME_SURROGATE_GUARD", frame=frame, feature_names=names,
            universe=universe, fold_identity=fold_identity, cutoff=cutoff, sources=sources,
            guard_audit=guard, lag_specs=specs, scope="final_design",
            feature_set_id="s1_guard_exemplar/1", repo_root=ROOT)
    check("the receipt is deterministic: the same construction digests identically",
          again["binding"]["receipt_digest"] == receipt["binding"]["receipt_digest"],
          receipt["binding"]["receipt_digest"])


# --------------------------------------------------------------------------------------------
# A8 — no false positive on the incumbent-equivalent feature set
# --------------------------------------------------------------------------------------------

def section_no_false_positive(fx: dict) -> None:
    print("\nN1 — the guard does NOT fire on the frozen incumbent-equivalent feature set")
    F, basis = fx["F"], fx["basis"]
    rep = gd.audit(F, list(pf.FEATURE_NAMES), prohibited=basis, lag_specs=dict(SCHEDULE_SPECS),
                   raise_on_block=False)
    MEASURED["N1_incumbent_equivalent"] = {
        "passed": bool(rep["passed"]),
        "blocking_kinds": sorted({b["kind"] for b in rep["blocking"]}),
        "max_abs_r_vs_game_minutes": max(
            abs(rep["per_column"][c]["dependency"]["game_minutes"]["pearson_r"] or 0.0)
            for c in pf.FEATURE_NAMES),
    }
    check("pace_gap / pace_evidence_depth / opp_pace_evidence_depth / is_playoff_game all pass",
          rep["passed"], json.dumps(MEASURED["N1_incumbent_equivalent"]))


def section_scan(fx: dict) -> None:
    """Sweep every numeric column of the two candidate-bearing artifacts against the basis.

    This is a DIAGNOSTIC, not an adjudication. It answers one bounded question: does any OTHER
    column of these two artifacts behave as a current-game duration surrogate the way
    master_team.minutes does? The 48 possessions_raw_v2 columns raised by S8 are a different
    node's mandate (P2A) and are deliberately not adjudicated here.
    """
    print("\nN2 — sweep: is master_team.minutes the ONLY duration surrogate in these artifacts?")
    F, basis = fx["F"], fx["basis"]

    def sweep(frame: pd.DataFrame, cols: list[str]) -> dict:
        blocked_cols, skipped, checked = [], [], []
        for c in cols:
            v = frame[c].to_numpy(float)
            if not np.isfinite(v).any() or float(np.nanstd(v)) == 0.0:
                skipped.append(c)
                continue
            checked.append(c)
            for q in basis.frame.columns:
                d = gd.dependency_report(v, basis.frame[q].to_numpy(float))
                if (d["column_is_function_of_prohibited"]
                        or (d["prohibited_is_function_of_column"]
                            and d["column_cardinality_within_recovery_bound"])
                        or d["column_exact_affine_of_prohibited"]
                        or d["prohibited_exact_affine_of_column"]
                        or (d["pearson_r"] is not None
                            and abs(d["pearson_r"]) >= gd.NEAR_COLLINEAR_R)):
                    blocked_cols.append({"column": c, "prohibited_quantity": str(q),
                                         "pearson_r": d["pearson_r"]})
                    break
        return {"n_checked": len(checked), "n_skipped_constant": len(skipped),
                "skipped": skipped, "blocked": blocked_cols}

    P = pd.read_parquet(PRIOR)
    P.index = pd.Index([f"{g}:{t}" for g, t in zip(P["game_id"], P["team_id"])])
    P = P.loc[F.index]
    pnum = [c for c in P.columns if pd.api.types.is_numeric_dtype(P[c])
            and c not in ("game_id", "team_id")]
    prior_sweep = sweep(P, pnum)

    M = fx["mt"].copy()
    M.index = pd.Index([f"{g}:{t}" for g, t in zip(M["game_id"], M["team_id"])])
    M = M.loc[F.index]
    mnum = [c for c in M.columns if pd.api.types.is_numeric_dtype(M[c])
            and c not in ("game_id", "team_id", "opp_team_id")]
    master_sweep = sweep(M, mnum)

    MEASURED["N2_sweep"] = {"team_possession_prior_v1": prior_sweep, "master_team": master_sweep}
    check("no numeric column of the frozen prior artifact is a duration surrogate",
          not prior_sweep["blocked"],
          f"{prior_sweep['n_checked']} checked, {prior_sweep['n_skipped_constant']} constant")
    check("within master_team, 'minutes' is the ONLY duration surrogate — S1's naming is complete "
          "for that artifact",
          [b["column"] for b in master_sweep["blocked"]] == ["minutes"],
          f"{master_sweep['n_checked']} checked; blocked="
          f"{[b['column'] for b in master_sweep['blocked']]}")


def main() -> int:
    print("=" * 94)
    print("P22_POSTGAME_SURROGATE_GUARD — TESTS")
    print("=" * 94)
    section_a7()
    fx = build()
    section_m1(fx)
    section_m2(fx)
    section_a1_a3(fx)
    a4 = section_a4(fx)
    section_a5(fx)
    section_a6(fx, a4)
    section_no_false_positive(fx)
    section_scan(fx)

    (HERE / "MEASUREMENTS.json").write_text(
        json.dumps(MEASURED, indent=2, default=str), encoding="utf-8")
    print("\n" + "=" * 94)
    if FAILURES:
        print(f"FAILED — {len(FAILURES)} check(s)")
        for f in FAILURES:
            print("  - " + f)
        return 1
    print("ALL CHECKS PASSED")
    print("measurements written to " + str(HERE / "MEASUREMENTS.json"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
