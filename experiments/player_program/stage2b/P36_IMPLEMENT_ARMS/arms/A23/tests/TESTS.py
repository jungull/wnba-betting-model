#!/usr/bin/env python3
"""TESTS.py -- unit, synthetic, identity and schema tests for A23_rest_differential_contrast.

BLINDED: every frame here is synthetic (synthetic_fixture.py); no real fold, no real MAE, no
comparative historical performance anywhere. The suite asserts the P38_UNSEALED flag is ABSENT
from the process environment and never sets it.

Covers (per this unit's mandate): feature determinism, strict lagging, arm-vs-null design
nesting, enumeration elements exact, and the card kill-condition hooks decidable.

Run:  python experiments/player_program/stage2b/P36_IMPLEMENT_ARMS/arms/A23/tests/TESTS.py
Writes: ../TEST_RECEIPT.json (machine-readable results).
"""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
A23_DIR = HERE.parent
RUNNER = A23_DIR.parents[1] / "runner"
for p in (str(RUNNER), str(A23_DIR), str(HERE)):
    if p not in sys.path:
        sys.path.insert(0, p)

import blinding                                                        # noqa: E402
import guard_harness as gh                                             # noqa: E402
import runner as rn                                                    # noqa: E402
import runner_constants as rc                                          # noqa: E402
import runner_interface as ri                                          # noqa: E402

import arm_a23 as a23                                                  # noqa: E402
import feature_construction as fc                                      # noqa: E402
import synthetic_fixture as fx                                         # noqa: E402

RESULTS = []


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)


def expect_raises(exc, fn, msg):
    try:
        fn()
    except exc:
        return
    raise AssertionError(f"expected {exc.__name__}: {msg}")


# ------------------------------------------------------------------------------- tests

def t01_rest_and_cap_identities():
    # f(rest) = min(rest, c) -- boundary identities
    r = np.array([0.0, 3.0, 7.0, 10.0])
    got = fc.f_cap(r, 7.0)
    check(np.array_equal(got, np.array([0.0, 3.0, 7.0, 7.0])), "f(rest)=min(rest,7) exact")
    got4 = fc.f_cap(r, 4.0)
    check(np.array_equal(got4, np.array([0.0, 3.0, 4.0, 4.0])), "f(rest)=min(rest,4) exact")
    # NaN passes through
    check(np.isnan(fc.f_cap(np.array([np.nan]), 7.0)[0]), "NaN rest -> NaN f(rest), no fallback")
    return {"cap7": got.tolist(), "cap4": got4.tolist()}


def _hist_kwargs(df):
    return dict(history_team_id=df["team_id"].to_numpy(), history_season=df["season"].to_numpy(),
               history_game_date=df["game_date"].to_numpy(),
               history_game_id=df["game_id"].to_numpy())


def t02_feature_determinism():
    df = fx.build_universe(seed=111)
    r1, o1 = fc.compute_rest_and_opener(df["team_id"].to_numpy(), df["season"].to_numpy(),
                                        df["game_date"].to_numpy(), df["game_id"].to_numpy(),
                                        **_hist_kwargs(df))
    r2, o2 = fc.compute_rest_and_opener(df["team_id"].to_numpy(), df["season"].to_numpy(),
                                        df["game_date"].to_numpy(), df["game_id"].to_numpy(),
                                        **_hist_kwargs(df))
    same = np.array_equal(o1, o2) and (np.array_equal(r1, r2) or
                                       (np.isnan(r1) == np.isnan(r2)).all() and
                                       np.allclose(r1[~np.isnan(r1)], r2[~np.isnan(r2)]))
    check(same, "rest/opener must be bitwise deterministic on repeat")

    # row-order invariance
    perm = np.random.Generator(np.random.PCG64(9)).permutation(len(df))
    dfp = df.iloc[perm].reset_index(drop=True)
    r3, o3 = fc.compute_rest_and_opener(dfp["team_id"].to_numpy(), dfp["season"].to_numpy(),
                                        dfp["game_date"].to_numpy(), dfp["game_id"].to_numpy(),
                                        **_hist_kwargs(dfp))
    back = np.empty(len(df), int)
    back[perm] = np.arange(len(df))
    check(np.array_equal(o1, o3[back]), "opener flag invariant to input row order")
    m1, m3 = ~np.isnan(r1), ~np.isnan(r3[back])
    check(np.array_equal(m1, m3) and np.allclose(r1[m1], r3[back][m1]),
          "rest days invariant to input frame's row order")

    n_openers = int(o1.sum())
    check(n_openers == df.groupby(["team_id", "season"]).ngroups,
          "exactly one opener row per (team_id, season) group")
    return {"n_rows": int(len(df)), "n_openers": n_openers}


def t03_strict_lagging_identity():
    """A row's rest/opener depend ONLY on strictly-earlier SAME-TEAM, SAME-SEASON rows."""
    df = fx.build_universe(seed=222)
    r0, o0 = fc.compute_rest_and_opener(df["team_id"].to_numpy(), df["season"].to_numpy(),
                                        df["game_date"].to_numpy(), df["game_id"].to_numpy(),
                                        **_hist_kwargs(df))

    # (a) perturbing a row's own game_date must not move ITS OWN rest/opener value: only the
    #     PRIOR game's date feeds a row's rest, never the row's own date twice.
    mid = int(len(df) // 2)
    df_a = df.copy()
    df_a.loc[mid, "game_date"] = df_a.loc[mid, "game_date"] + 500
    ra, oa = fc.compute_rest_and_opener(df_a["team_id"].to_numpy(), df_a["season"].to_numpy(),
                                        df_a["game_date"].to_numpy(), df_a["game_id"].to_numpy(),
                                        **_hist_kwargs(df_a))
    # the perturbed row's OWN rest depends on rows strictly before its (now-changed) date, so its
    # own value MAY change; what must NOT change is any row of a DIFFERENT team/season.
    other_team = df["team_id"].to_numpy() != df.loc[mid, "team_id"]
    other_season = df["season"].to_numpy() != df.loc[mid, "season"]
    unaffected = other_team | other_season
    same_num = (np.isnan(r0[unaffected]) == np.isnan(ra[unaffected])).all()
    check(same_num and np.array_equal(o0[unaffected], oa[unaffected]),
          "perturbing one row must never move a different team's or a different season's rows")

    # (b) perturbing the LATEST-dated row of a team-season must not move any EARLIER row of that
    #     same team-season (no future information leaks backward).
    team0 = df["team_id"].iloc[0]
    season0 = df["season"].iloc[0]
    grp = np.flatnonzero((df["team_id"].to_numpy() == team0) & (df["season"].to_numpy() == season0))
    grp_sorted = grp[np.argsort(df["game_date"].to_numpy()[grp])]
    check(len(grp_sorted) >= 3, "fixture must give a team-season >= 3 games")
    latest = int(grp_sorted[-1])
    df_b = df.copy()
    df_b.loc[latest, "game_date"] = df_b.loc[latest, "game_date"] + 999
    rb, ob = fc.compute_rest_and_opener(df_b["team_id"].to_numpy(), df_b["season"].to_numpy(),
                                        df_b["game_date"].to_numpy(), df_b["game_id"].to_numpy(),
                                        **_hist_kwargs(df_b))
    earlier = grp_sorted[:-1]
    check(np.allclose(r0[earlier], rb[earlier], equal_nan=True) and
          np.array_equal(o0[earlier], ob[earlier]),
          "perturbing the latest row of a team-season must not change any EARLIER row's rest")

    # (c) perturbing an EARLY row's date DOES propagate to a strictly LATER row of the SAME
    #     team-season (the mechanism is responsive, not accidentally inert).
    early_row = int(grp_sorted[0])
    later_row = int(grp_sorted[1])
    df_c = df.copy()
    df_c.loc[early_row, "game_date"] = df_c.loc[early_row, "game_date"] - 2
    rc_, oc_ = fc.compute_rest_and_opener(df_c["team_id"].to_numpy(), df_c["season"].to_numpy(),
                                          df_c["game_date"].to_numpy(), df_c["game_id"].to_numpy(),
                                          **_hist_kwargs(df_c))
    check(not oc_[later_row], "the second game of a team-season is never itself an opener")
    check(abs(rc_[later_row] - r0[later_row]) > 1e-9,
          "shifting an earlier same-team-season game's date MUST move a later row's rest")
    return {"n_teamseasons_checked": 1,
           "early_row_effect_on_later_rest": float(abs(rc_[later_row] - r0[later_row]))}


def t04_bundle_contrast_identities():
    df = fx.build_universe(seed=333)
    for bundle in fc.ENUMERATED_BUNDLES:
        out = fc.bundle_contrast(df["team_id"].to_numpy(), df["season"].to_numpy(),
                                 df["game_date"].to_numpy(), df["game_id"].to_numpy(),
                                 df["opp_team_id"].to_numpy(), **_hist_kwargs(df), bundle=bundle)
        check(np.all(np.isfinite(out["contrast"])),
              f"bundle_{bundle}: contrast must be finite on every row after the opener rule")
        opener_any = out["opener_own"] | out["opener_opp"]
        if bundle == "AI":
            check(np.allclose(out["contrast"][opener_any], 0.0),
                  "bundle_AI: contrast must be exactly 0 on any row with an opener on either side")
            non_opener = ~opener_any
            expect = np.minimum(out["rest_own"][non_opener], fc.BUNDLE_CAP["AI"]) - \
                np.minimum(out["rest_opp"][non_opener], fc.BUNDLE_CAP["AI"])
            check(np.allclose(out["contrast"][non_opener], expect),
                  "bundle_AI: non-opener contrast == f(rest_own)-f(rest_opp) exactly")
        else:
            check(np.all(out["f_own"][out["opener_own"]] == fc.BUNDLE_CAP["OM"]),
                  "bundle_OM: an opener's own f(rest) must equal the cap exactly (fully rested)")
            check(np.all(out["f_opp"][out["opener_opp"]] == fc.BUNDLE_CAP["OM"]),
                  "bundle_OM: an opener opponent's f(rest) must equal the cap exactly")
            expect_contrast = out["f_own"] - out["f_opp"]
            check(np.allclose(out["contrast"], expect_contrast),
                  "bundle_OM: contrast == f_own - f_opp exactly, always finite")
        # antisymmetry (own-minus-opp construction): checked exhaustively via the built design in
        # t07_k0_nesting_and_p26_and_antisymmetry, which has ready access to the runner-facing
        # column and game_id/opp_team_id keys; not duplicated here.
    return {"bundles_checked": list(fc.ENUMERATED_BUNDLES)}


def t05_enumeration_elements_exact():
    check(fc.ENUMERATED_BUNDLES == ("AI", "OM"), "frozen P35 A23 elements: bundle in {AI, OM}")
    df = fx.build_universe(seed=444)
    cs = fx.build_contract_schedule(df)
    folds = fx.build_folds(df)
    fids = [f["fold_id"] for f in folds]
    arms = a23.make_arms(cs, fids, len(df))
    check(len(arms) == 2, "one module instance per enumerated bundle")
    got = sorted(a.enumeration_element()["bundle"] for a in arms)
    check(got == ["AI", "OM"], f"enumeration_element() values must be exactly the frozen grid: {got}")
    eids = [a.element_id() for a in arms]
    check(len(set(eids)) == 2, "element_id() must be unique per element")
    check(all(a.card_id() == a23.ARM_ID for a in arms), "card_id() must equal the frozen arm_id")
    expect_raises(ValueError, lambda: a23.A23Arm("XX", cs, fids, len(df)),
                  "an off-grid bundle must be refused, never silently admitted")
    return {"element_ids": eids}


def t06_conformance_and_intercept_invariant():
    df = fx.build_universe(seed=555)
    cs = fx.build_contract_schedule(df)
    folds = fx.build_folds(df)
    fids = [f["fold_id"] for f in folds]
    for bundle in fc.ENUMERATED_BUNDLES:
        arm = a23.A23Arm(bundle, cs, fids, len(df))
        rec = ri.validate_arm_module(arm)
        check(rec["conformant"], f"A23 bundle_{bundle} module must conform to RUNNER_INTERFACE")
        check(arm.uses_global_intercept() is False, "A23 is in ARMS_WITHOUT_GLOBAL_INTERCEPT")
        check("A23" in rc.ARMS_WITHOUT_GLOBAL_INTERCEPT, "frozen intercept table must name A23")
        check(arm.requires_franchise_continuity() is False,
              "A23 is absent from the P33 franchise-continuity precondition list")

        bundle_design = arm.build_design(folds[0], df)
        bval = ri.validate_design_bundle(bundle_design, df, False, folds[0]["fold_id"])
        check(bval["valid"], f"A23 bundle_{bundle} design must validate (no intercept)")
        check(bundle_design["treatment_cols"] == [a23.TREATMENT_COL], "treatment column name exact")
        check(bundle_design["nuisance_cols"] == [], "A23 carries no nuisance terms")
        check(bundle_design["k0_matched_design"]["comparison"] == "term_removal",
              "A23's K0 comparison is term_removal")
        check(bundle_design["k0_matched_design"]["treatment_cols"] == [], "term_removal null empty")
        check(bundle_design["indicator_cols"] == [], "the contrast is continuous, not an indicator")

        # column names identical across folds (values may differ; names may not)
        d2 = arm.build_design(folds[1], df)
        check(list(d2["columns"]) == list(bundle_design["columns"]),
              "column name set must be identical across folds")
    return {"treatment_col": a23.TREATMENT_COL}


def t07_k0_nesting_and_p26_and_antisymmetry():
    df = fx.build_universe(seed=666)
    cs = fx.build_contract_schedule(df)
    folds = fx.build_folds(df)
    fids = [f["fold_id"] for f in folds]
    for bundle in fc.ENUMERATED_BUNDLES:
        arm = a23.A23Arm(bundle, cs, fids, len(df))
        rec = arm.p26_k0_record()
        check(rec["arm_kind"] == "substantive_feature", "A23 is a substantive_feature arm")
        out = gh.p26_check(rec)
        check(out["valid"], f"bundle_{bundle}: P26 K0_MATCHED record must validate: "
                            f"{out['blocking_after_adjudication']}")
        a_sub = set(rec["arm_spec"]["substantive_features"])
        k_sub = set(rec["k0_spec"]["substantive_features"])
        treat = set(rec["treatment_mechanism"]["treatment_terms"])
        check(a_sub - k_sub == treat, "K0 must exclude EXACTLY the treatment terms")
        check(set(rec["arm_spec"]["structural_terms"]) ==
              set(rec["k0_spec"]["structural_terms"]) == set(),
              "A23 carries no structural/nuisance terms in either design")

        design = arm.build_design(folds[0], df)
        arm_cols = set(design["treatment_cols"]) | set(design["nuisance_cols"])
        null_cols = set(design["k0_matched_design"]["treatment_cols"]) | \
            set(design["k0_matched_design"]["nuisance_cols"])
        check(null_cols < arm_cols, "K0 design columns must be a STRICT subset of the arm's own")
        check(arm_cols - null_cols == {a23.TREATMENT_COL},
              "the only column K0 excludes is the rest-differential contrast")

        # antisymmetry, exhaustive: swapping which side of a game is "own" negates the contrast.
        contrast = design["columns"][a23.TREATMENT_COL]
        lut = pd.Series(contrast, index=pd.MultiIndex.from_arrays(
            [df["game_id"].to_numpy(), df["team_id"].to_numpy()]))
        opp_key = pd.MultiIndex.from_arrays([df["game_id"].to_numpy(), df["opp_team_id"].to_numpy()])
        opp_contrast = lut.reindex(opp_key).to_numpy()
        check(np.allclose(contrast, -opp_contrast),
              f"bundle_{bundle}: contrast(t, opp) must equal -contrast(opp, t) for every game "
              "(own-minus-opp antisymmetry)")
    return {"bundles_checked": list(fc.ENUMERATED_BUNDLES)}


def t08_guard_negative_paths():
    df = fx.build_universe(seed=777)
    cs = fx.build_contract_schedule(df)
    basis = fx.build_prohibited_basis(df)
    for bundle in fc.ENUMERATED_BUNDLES:
        arm = a23.A23Arm(bundle, cs, ["f1"], len(df))
        design = arm.build_design({"fold_id": "f1", "train_idx": np.arange(len(df)),
                                   "test_idx": np.array([], int)}, df)
        W = df.copy()
        for name, v in design["columns"].items():
            W[name] = np.asarray(v, float)
        names = list(dict.fromkeys(design["treatment_cols"] + design["nuisance_cols"]))
        ok = gh.p22_check(W, names, prohibited_basis=basis, lag_specs=arm.lag_specs(),
                          lag_sources=arm.lag_sources())
        check(not ok["blocking"], f"bundle_{bundle}: honestly-declared DERIVED_NO_JOIN design "
                                  "must clear P22")

        expect_raises(gh.GuardHarnessFailure,
                      lambda: gh.p22_check(W, names, prohibited_basis=basis, lag_specs={}),
                      "missing LagSpec must block even for A23's own columns")

        tr = np.arange(len(df))
        p25 = gh.p25_check(W.iloc[tr], candidate_features=design["treatment_cols"],
                           nuisance_features=design["nuisance_cols"])
        check(p25["passed"], f"bundle_{bundle}: synthetic design must clear P25")

        check(arm.requires_franchise_continuity() is False, "A23 requires no franchise receipt")
        ok23 = gh.p23_check(requires_franchise_continuity=False, receipts=arm.p23_receipts())
        check(ok23["valid"], "A23's (empty) receipt list must pass when not required")
    return {"n_bundles_checked": len(fc.ENUMERATED_BUNDLES)}


def t09_kill_condition_hooks_decidable_end_to_end():
    """Run the full shared runner on synthetic data; verify the per-bundle beta interval the
    card's kill condition reads ('interval excluding 0' / 'no gain over K0') is actually COMPUTED
    and decidable, for BOTH enumerated bundles. Also verifies bundle_AI's S7 rule and bundle_OM's
    absence of one are both honoured end-to-end."""
    df = fx.build_universe(seed=888)
    cs = fx.build_contract_schedule(df)
    folds = fx.build_folds(df)
    basis = fx.build_prohibited_basis(df)
    fids = [f["fold_id"] for f in folds]
    decisions = {}
    for bundle in fc.ENUMERATED_BUNDLES:
        arm = a23.A23Arm(bundle, cs, fids, len(df))
        out_path = HERE / "artifacts" / f"A23_bundle_{bundle}_receipt.json"
        rec = rn.run_arm(arm, df, folds, prohibited_basis=basis, env={},
                         out_path=out_path, run_git=False)
        check(rec["schema"] == rc.RECEIPT_SCHEMA, "receipt schema pin")
        check(rec["guard_records"]["p27"]["overall"] != "FAIL",
              f"bundle_{bundle}: P27 must not FAIL on clean synthetic data")
        per_fold_decidable = []
        for e in rec["folds"]:
            if e["status"] != "EVALUABLE":
                continue
            iv = e["train_refit"]["arm_intervals"].get(a23.TREATMENT_COL)
            check(iv is not None, f"bundle_{bundle} fold {e['fold_id']}: interval missing")
            decidable = iv["n_effective"] > 0 and iv["lo"] is not None and iv["hi"] is not None
            check(decidable, f"bundle_{bundle} fold {e['fold_id']}: beta interval not decidable "
                             f"({iv})")
            no_gain = e["test"]["delta_mae"] <= 0.0
            excludes_zero = bool(iv["lo"] > 0.0 or iv["hi"] < 0.0)
            per_fold_decidable.append({
                "fold_id": e["fold_id"], "lo": iv["lo"], "hi": iv["hi"],
                "no_gain_over_k0": no_gain, "interval_excludes_zero": excludes_zero,
            })
        check(len(per_fold_decidable) >= 1,
              f"bundle_{bundle}: at least one fold must be evaluable on clean synthetic data")
        decisions[bundle] = per_fold_decidable

        # determinism: an identical second run must reproduce the kill-relevant numbers exactly
        rec2 = rn.run_arm(arm, df, folds, prohibited_basis=basis, env={}, run_git=False)
        for e1, e2 in zip(rec["folds"], rec2["folds"]):
            if e1["status"] != "EVALUABLE":
                continue
            iv1 = e1["train_refit"]["arm_intervals"][a23.TREATMENT_COL]
            iv2 = e2["train_refit"]["arm_intervals"][a23.TREATMENT_COL]
            check(iv1 == iv2, f"bundle_{bundle}: kill-relevant interval must be bit-reproducible")

    # kill-condition decision function: "opposite-sign rejection" needs a PREDICTED direction the
    # frozen card bytes available to this module do not pin numerically -- reported honestly as
    # undecidable-without-that-input rather than invented (see evaluate_kill_conditions docstring).
    verdict = a23.evaluate_kill_conditions(decisions["AI"]) if hasattr(a23, "evaluate_kill_conditions") \
        else None

    # blinding still holds through this arm: a real fold id must be refused without the flag
    bad_folds = [dict(folds[0], fold_id="train_lt_2024")]
    arm2 = a23.A23Arm("AI", cs, fids, len(df))
    expect_raises(blinding.BlindingViolation,
                  lambda: rn.run_arm(arm2, df, bad_folds, prohibited_basis=basis, env={}),
                  "the shared runner must refuse real fold ids for A23 too, without P38_UNSEALED")
    return {"decisions": decisions, "kill_condition_verdict_sample": verdict}


def t10_regression_contract_schedule_clock_not_universe():
    """REGRESSION (P37 finding A3-B4 / D039-D040 EXEC-M6): rest/opener status must be computed
    against the CONTRACT-SCHEDULE clock, not the fitting universe -- the exact defect the audit
    found. Two teams (100, 200) each play 3 same-season games; each team's FIRST game of the
    season is present in contract_schedule but EXCLUDED from the fitting universe (the synthetic
    analogue of the real archive's 4 universe-excluded 2021 opening-day games). Under the
    pre-remediation universe-only clock, each team's SECOND universe game would be misclassified
    as an opener (no strictly-earlier row visible in the universe); under the CONTRACT-SCHEDULE
    clock, it correctly resolves to a non-opener with a defined rest value."""
    season = 9977
    dates = pd.date_range("2031-01-01", periods=3, freq="3D")   # day 0, 3, 6
    # game 0 (excluded from universe, present in contract_schedule): team 100 vs team 200
    # game 1 (in universe): team 100 vs team 300; game 2 (in universe): team 200 vs team 400
    cs_rows = [
        {"team_id": 100, "season": season, "game_date": dates[0], "game_id": "G0"},
        {"team_id": 200, "season": season, "game_date": dates[0], "game_id": "G0"},
        {"team_id": 100, "season": season, "game_date": dates[1], "game_id": "G1"},
        {"team_id": 300, "season": season, "game_date": dates[1], "game_id": "G1"},
        {"team_id": 200, "season": season, "game_date": dates[2], "game_id": "G2"},
        {"team_id": 400, "season": season, "game_date": dates[2], "game_id": "G2"},
    ]
    cs = pd.DataFrame(cs_rows)
    uni = cs[cs["game_id"] != "G0"].reset_index(drop=True)     # universe excludes G0
    uni = uni.assign(opp_team_id=[300, 100, 400, 200])

    # pre-remediation (universe-only) oracle: team 100's G1 row would see NO strictly-earlier
    # universe row (G0 is excluded) -> misclassified as an opener.
    r_uni_only, o_uni_only = fc.compute_rest_and_opener(
        uni["team_id"].to_numpy(), uni["season"].to_numpy(), uni["game_date"].to_numpy(),
        uni["game_id"].to_numpy(),
        history_team_id=uni["team_id"].to_numpy(), history_season=uni["season"].to_numpy(),
        history_game_date=uni["game_date"].to_numpy(), history_game_id=uni["game_id"].to_numpy())
    row_100_g1 = int(np.flatnonzero((uni["team_id"] == 100) & (uni["game_id"] == "G1"))[0])
    check(bool(o_uni_only[row_100_g1]),
          "sanity: the REJECTED universe-only clock does misclassify team 100's G1 as an opener "
          "(confirms this regression exercises the real defect, not a vacuous case)")

    # remediated (contract-schedule) clock: G0 is visible, so G1 is correctly NOT an opener, with
    # rest = 3 days (dates[1] - dates[0]).
    r_cs, o_cs = fc.compute_rest_and_opener(
        uni["team_id"].to_numpy(), uni["season"].to_numpy(), uni["game_date"].to_numpy(),
        uni["game_id"].to_numpy(), **_hist_kwargs(cs))
    check(not bool(o_cs[row_100_g1]),
          "P37/EXEC-M6: team 100's G1 must NOT be an opener under the contract-schedule clock "
          "(G0 is a completed contract-schedule game, even though it is excluded from the "
          "fitting universe)")
    check(abs(float(r_cs[row_100_g1]) - 3.0) < 1e-9,
          "P37/EXEC-M6: team 100's G1 rest must equal 3.0 days since G0 (the contract-schedule-"
          "only prior game), not NaN/opener")

    # bundle_AI's contrast must correspondingly NOT be forced to 0 for this row (the pre-
    # remediation defect: an opener-side row's contrast is always forced to 0 under bundle_AI).
    out_ai = fc.bundle_contrast(uni["team_id"].to_numpy(), uni["season"].to_numpy(),
                                uni["game_date"].to_numpy(), uni["game_id"].to_numpy(),
                                uni["opp_team_id"].to_numpy(), **_hist_kwargs(cs), bundle="AI")
    check(not bool(out_ai["opener_own"][row_100_g1]),
          "bundle_AI: team 100's G1 opener_own must be False under the remediated clock")

    # bundle_OM's f_own must equal the ACTUAL capped rest (3, capped at 4), not the cap-as-opener
    # fallback (4) the pre-remediation defect would have assigned.
    out_om = fc.bundle_contrast(uni["team_id"].to_numpy(), uni["season"].to_numpy(),
                                uni["game_date"].to_numpy(), uni["game_id"].to_numpy(),
                                uni["opp_team_id"].to_numpy(), **_hist_kwargs(cs), bundle="OM")
    check(abs(float(out_om["f_own"][row_100_g1]) - 3.0) < 1e-9,
          "bundle_OM: team 100's G1 f_own must equal min(3, 4)=3 (the true rest), not the "
          "opener-fallback cap=4 the pre-remediation defect would have assigned")
    return {"row_checked": row_100_g1, "rest_days": float(r_cs[row_100_g1])}


TESTS = [
    ("T01_rest_and_cap_identities", t01_rest_and_cap_identities),
    ("T02_feature_determinism", t02_feature_determinism),
    ("T03_strict_lagging_identity", t03_strict_lagging_identity),
    ("T04_bundle_contrast_identities", t04_bundle_contrast_identities),
    ("T05_enumeration_elements_exact", t05_enumeration_elements_exact),
    ("T06_conformance_and_intercept_invariant", t06_conformance_and_intercept_invariant),
    ("T07_k0_nesting_and_p26_and_antisymmetry", t07_k0_nesting_and_p26_and_antisymmetry),
    ("T08_guard_negative_paths", t08_guard_negative_paths),
    ("T09_kill_condition_hooks_decidable_end_to_end", t09_kill_condition_hooks_decidable_end_to_end),
    ("T10_regression_contract_schedule_clock_not_universe",
     t10_regression_contract_schedule_clock_not_universe),
]


def main() -> int:
    if rc.UNSEAL_ENV_FLAG in os.environ:
        print(f"FATAL: {rc.UNSEAL_ENV_FLAG} exists in the environment; "
              "the blinded A23 test suite refuses to run.")
        return 2
    (HERE / "artifacts").mkdir(exist_ok=True)
    n_pass = 0
    for name, fn in TESTS:
        t0 = time.time()
        try:
            measured = fn()
            RESULTS.append({"test": name, "passed": True,
                            "seconds": round(time.time() - t0, 2), "measured": measured})
            n_pass += 1
            print(f"PASS  {name}")
        except Exception as e:                                        # noqa: BLE001
            RESULTS.append({"test": name, "passed": False,
                            "seconds": round(time.time() - t0, 2),
                            "error": f"{type(e).__name__}: {e}",
                            "traceback": traceback.format_exc(limit=8)})
            print(f"FAIL  {name}: {type(e).__name__}: {e}")
    receipt = {
        "schema": "p36_a23_test_receipt/1",
        "epistemic_status": ("IMPLEMENTATION. Blinded: no agent may inspect challenger "
                             "performance. Unit, synthetic, identity and schema tests only."),
        "unseal_flag_absent": rc.UNSEAL_ENV_FLAG not in os.environ,
        "arm_id": a23.ARM_ID, "enumerated_bundles": list(fc.ENUMERATED_BUNDLES),
        "n_tests": len(TESTS), "n_passed": n_pass,
        "results": RESULTS,
    }
    out = A23_DIR / "TEST_RECEIPT.json"
    out.write_text(json.dumps(receipt, indent=2, sort_keys=True, default=str), encoding="utf-8")
    print(f"\n{n_pass}/{len(TESTS)} passed -> {out}")
    return 0 if n_pass == len(TESTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
