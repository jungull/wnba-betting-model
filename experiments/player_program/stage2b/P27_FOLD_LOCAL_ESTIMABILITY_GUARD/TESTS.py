#!/usr/bin/env python3
"""TESTS.py -- P27_FOLD_LOCAL_ESTIMABILITY_GUARD.

Standalone. No pytest. `main()` returns 1 on any failure.

    python experiments/player_program/stage2b/P27_FOLD_LOCAL_ESTIMABILITY_GUARD/TESTS.py

Two kinds of test, kept visibly apart:
  SYNTHETIC -- the guard's behaviour on constructed data where the right answer is known by
               construction. These prove the mechanism.
  ARTIFACT  -- assertions against the frozen artifacts. These prove the S7 and S5 measurements
               reproduce, and that the frozen gate really does pass what the guard blocks.

No test reads anything under stage2b/SEALED_RESULTS, and no test consults any comparative
historical performance of any arm.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PROGRAM = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(PROGRAM))

import fold_estimability_guard as G          # noqa: E402
import feature_gate as fg                    # noqa: E402  (frozen; imported READ ONLY)

FAILS: list[str] = []
NCHECK = 0


def check(cond, label, detail=""):
    global NCHECK
    NCHECK += 1
    if cond:
        print(f"  ok   {label}")
    else:
        print(f"  FAIL {label}  {detail}")
        FAILS.append(f"{label} :: {detail}")


# ---------------------------------------------------------------------------
def t01_frozen_gate_untouched():
    print("\n[T01] the frozen gate is imported, mirrored and NOT modified")
    check(fg.RANK_TOL == G.RANK_TOL, "RANK_TOL mirrors feature_gate",
          f"{fg.RANK_TOL} vs {G.RANK_TOL}")
    check(fg.COND_MAX == G.COND_MAX, "COND_MAX mirrors feature_gate",
          f"{fg.COND_MAX} vs {G.COND_MAX}")
    check(fg.audit.__module__ == "feature_gate", "feature_gate.audit is not rebound")
    check(fg.design_rank_report.__module__ == "feature_gate",
          "feature_gate.design_rank_report is not rebound")
    expected = {"exact_duplicate", "near_collinear", "deterministic_transform_of_offset",
                "zero_variance", "non_finite", "impossible_scaling", "schema_mismatch",
                "target_derived", "rank_deficient", "ill_conditioned",
                "missingness_encodes_outcome", "missingness_informative"}
    check(fg.BLOCKING == expected, "feature_gate.BLOCKING is the documented set",
          str(sorted(fg.BLOCKING ^ expected)))
    src = (PROGRAM / "feature_gate.py").read_text(encoding="utf-8")
    check("stage2b" not in src and "fold_estimability_guard" not in src,
          "feature_gate.py contains no reference to this node")


# ---------------------------------------------------------------------------
def _synth(n_seasons=4, teams=8, seed=0):
    """Synthetic team-game panel: two rows per game cluster, one season per block."""
    rng = np.random.default_rng(seed)
    rows = []
    gid = 0
    for si, s in enumerate(range(2020, 2020 + n_seasons)):
        for g in range(40):
            gid += 1
            base = rng.normal(80, 4)
            for side in (0, 1):
                rows.append({"game_id": gid, "season": s, "side": side,
                             "offset_projected": base,
                             "x1": rng.normal(), "x2": rng.normal()})
    df = pd.DataFrame(rows)
    return df


def t02_fold_construction():
    print("\n[T02] fold construction: policies, counts, and games never split")
    df = _synth()
    fb = G.make_outer_training_folds(df["season"], "SEASON_BLOCK")
    fe = G.make_outer_training_folds(df["season"], "EXPANDING_PRIOR_SEASONS")
    check(len(fb) == 4, "SEASON_BLOCK yields one fold per season", str(len(fb)))
    check(len(fe) == 3, "EXPANDING_PRIOR_SEASONS yields one fewer", str(len(fe)))
    check(G.assert_games_not_split(fb, df["game_id"])["ok"], "SEASON_BLOCK never splits a game")
    check(G.assert_games_not_split(fe, df["game_id"])["ok"], "EXPANDING never splits a game")
    try:
        G.make_outer_training_folds(df["season"], "NOT_A_POLICY")
        check(False, "unknown fold policy is rejected")
    except ValueError:
        check(True, "unknown fold policy is rejected")
    # a deliberately split game must be detected
    bad = df.copy()
    bad.loc[bad.index[0], "season"] = 2099
    fbad = G.make_outer_training_folds(bad["season"], "SEASON_BLOCK")
    check(not G.assert_games_not_split(fbad, bad["game_id"])["ok"],
          "a game split across folds is detected")


def t03_fold_local_zero_variance_that_pooled_hides():
    print("\n[T03] SYNTHETIC: a term with variance pooled and none in one fold")
    df = _synth()
    df["tier"] = 0.0
    df.loc[df["season"] != 2021, "tier"] = (
        np.arange((df["season"] != 2021).sum()) % 3 == 0).astype(float)
    # the frozen gate, on the POOLED matrix, sees ample variance
    pooled = fg.audit(df, ["tier", "x1"], offset=df["offset_projected"].to_numpy(float))
    check(pooled["passed"], "frozen gate PASSES the pooled matrix")
    # the frozen gate, on the 2021 fold alone, blocks
    blocked = False
    try:
        fg.audit(df[df["season"] == 2021], ["tier", "x1"],
                 offset=df.loc[df["season"] == 2021, "offset_projected"].to_numpy(float))
    except fg.FeatureGateFailure as e:
        blocked = any(b["kind"] == "zero_variance" for b in json.loads(str(e)))
    check(blocked, "frozen gate BLOCKS the same columns on the 2021 fold (zero_variance)")
    # the guard reaches the fold verdict without the caller having to remember to loop
    r = G.guard(df, ["x1"], ["tier"], "offset_projected", "game_id",
                null_features=[], null_nuisance=["tier"], arm_id="synthetic_fold_degenerate")
    v = {f["fold_id"]: f["verdict"] for f in r["folds"]}
    check(v["train_2021"] == G.VERDICT_UNEVALUABLE,
          "the degenerate fold is UNEVALUABLE_PROSPECTIVELY", str(v))
    check(all(v[k] == G.VERDICT_ESTIMABLE for k in v if k != "train_2021"),
          "the healthy folds are ESTIMABLE", str(v))
    check(r["final_design"]["verdict"] == G.VERDICT_ESTIMABLE,
          "the FINAL assembled design is estimable -- which is exactly the trap")
    pv = r["pooled_vs_fold_reconciliation"]
    check(pv["pooled_pass_would_be_misleading"], "the pooled/final pass is flagged as misleading")
    check(pv["affected_folds_without_an_explicit_verdict"] == [],
          "no affected fold is left carrying a bare ESTIMABLE",
          str(pv["affected_folds_without_an_explicit_verdict"]))
    check(not pv["pooled_pass_masks_fold_degeneracy"],
          "and therefore nothing is MASKED -- the degeneracy is on the face of the receipt")
    check(r["overall"] == "FAIL",
          "overall is FAIL even though the pooled and final designs pass", r["overall"])


def t04_offset_and_nuisance_enter_the_rank_audit():
    print("\n[T04] SYNTHETIC: criterion 2 -- offset and nuisance terms enter the rank audit")
    df = _synth()
    # (a) OFFSET: two features that reproduce the offset exactly, pairwise-innocent
    df["a"] = df["offset_projected"] + np.random.default_rng(1).normal(0, 6, len(df))
    df["b"] = 2 * df["offset_projected"] - df["a"]        # a + b == 2 * offset, exactly
    r_pair = abs(np.corrcoef(df["a"], df["offset_projected"])[0, 1])
    check(r_pair < 0.999, "each feature's pairwise corr with the offset is under 0.999",
          f"{r_pair:.4f}")
    gate = fg.audit(df, ["a", "b"], offset=df["offset_projected"].to_numpy(float))
    check(gate["passed"], "frozen gate PASSES the pair")
    check(gate["design_rank"]["full_rank"], "frozen gate reports the features-only design FULL RANK")
    absorb = G.offset_absorption_report(df, ["a", "b"], [],
                                        df["offset_projected"].to_numpy(float))
    check(absorb["offset_in_design_span"],
          "guard detects the offset inside the design span",
          str(absorb["relative_residual_norm"]))
    aug = G.augmented_rank_report(df, ["a", "b"], [],
                                  df["offset_projected"].to_numpy(float))
    check(not aug["full_rank"], "guard's [X | intercept | offset] rank audit is deficient",
          str(aug["numerical_rank"]) + "/" + str(aug["n_columns"]))
    r = G.guard(df, ["a", "b"], [], "offset_projected", "game_id", arm_id="synthetic_offset")
    check(all(f["verdict"] == G.VERDICT_UNEVALUABLE for f in r["folds"]),
          "every fold is UNEVALUABLE on offset absorption")

    # (b) NUISANCE: a declared feature exactly equal to a NUISANCE term the gate never sees
    df2 = _synth(seed=3)
    df2["tierA"] = (df2["game_id"] % 3 == 0).astype(float)
    df2["feat"] = df2["tierA"]                            # exact duplicate of a nuisance term
    g2 = fg.audit(df2, ["feat"], offset=df2["offset_projected"].to_numpy(float))
    check(g2["passed"], "frozen gate PASSES: the nuisance term was never declared to it")
    aug2 = G.augmented_rank_report(df2, ["feat"], ["tierA"],
                                   df2["offset_projected"].to_numpy(float))
    check(not aug2["full_rank"],
          "guard's augmented audit sees feature == nuisance term and is rank deficient",
          str(aug2["numerical_rank"]) + "/" + str(aug2["n_columns"]))

    # (c) the intercept must not manufacture a false positive on a healthy design
    aug3 = G.augmented_rank_report(df2, ["x1", "x2"], [],
                                   df2["offset_projected"].to_numpy(float))
    check(aug3["full_rank"], "a healthy design with an intercept column is NOT flagged",
          str(aug3))
    check(aug3["condition_ok"], "and is not spuriously ill-conditioned",
          str(aug3["condition_number"]))


def t05_cluster_support_not_row_support():
    print("\n[T05] SYNTHETIC: treatment support is counted in GAME CLUSTERS, not rows")
    df = _synth()
    df["t"] = 0.0
    hit = df["game_id"].isin(sorted(df["game_id"].unique())[:5])   # 5 clusters, 10 rows
    df.loc[hit, "t"] = 1.0
    diag = G.column_diagnostics(df, ["t"], df["game_id"])["t"]
    check(diag["n_nonzero_rows"] == 10, "10 rows carry the term", str(diag["n_nonzero_rows"]))
    check(diag["n_clusters_with_support"] == 5, "but only 5 game clusters do",
          str(diag["n_clusters_with_support"]))
    check(diag["unique_levels"] == 2, "unique-level count is reported", str(diag))
    r = G.guard(df, ["t"], [], "offset_projected", "game_id", arm_id="synthetic_support")
    f0 = r["folds"][0]
    kinds = {x["kind"] for x in f0["findings"]}
    check("thin_cluster_support" in kinds or "no_cluster_support" in kinds,
          "thin/no cluster support is reported per fold", str(sorted(kinds)))
    for f in r["folds"] + [r["final_design"]]:
        for t in f["terms_audited"]:
            d = f["column_diagnostics"][t]
            for k in ("std", "zero_variance", "unique_levels", "n_clusters_with_support"):
                if k not in d:
                    check(False, f"{f['fold_id']}/{t} reports {k}")
    check(all("condition_number" in f["rank_augmented_with_offset_and_nuisance"]
              for f in r["folds"] + [r["final_design"]]),
          "a condition number is reported for every fold AND the final design")


def t06_parameter_count_reconciliation():
    print("\n[T06] SYNTHETIC: candidate and null parameter counts are reconciled")
    ok = G.reconcile_parameter_counts(["a", "b"], ["tier"], [], ["tier"])
    check(ok["reconciled"], "matched control reconciles", str(ok["problems"]))
    check(ok["n_params_candidate"] == 4 and ok["n_params_null"] == 2 and ok["delta_params"] == 2,
          "counts include the intercept and the nuisance terms", str(ok))
    straw = G.reconcile_parameter_counts(["a", "b"], ["tier"], [], [])
    check(not straw["reconciled"], "a control missing the candidate's tier term is refused")
    check(any(p["kind"] == "nuisance_terms_differ" for p in straw["problems"]),
          "and the reason code names the asymmetry", str(straw["problems"]))
    contaminated = G.reconcile_parameter_counts(["a"], ["tier"], ["a"], ["tier"])
    check(not contaminated["reconciled"], "a null carrying a substantive feature is refused")


def t07_active_set_rule_discipline():
    print("\n[T07] SYNTHETIC: the fold-local active-set rule, and its five required properties")
    rule = G.ActiveSetRule("T07_rule", min_nonzero_clusters=10, min_std=1e-8, rationale="test")
    good = G.Preregistration("2026-01-01T00:00:00Z", "tester", rule.spec_sha256, False, "x.json")
    audit = G.validate_preregistration(rule, good)
    check(audit["valid"], "a conforming preregistration validates")
    for k in ("preregistered", "training_fold_support_only", "applied_symmetrically",
              "incapable_of_selecting_on_test_performance", "recorded_in_receipt"):
        check(audit["properties"][k] is True, f"property recorded: {k}")

    late = G.Preregistration("2026-01-01T00:00:00Z", "tester", rule.spec_sha256, True, "x.json")
    try:
        G.validate_preregistration(rule, late)
        check(False, "a rule registered after results is REFUSED")
    except G.PreregistrationFailure as e:
        check(any(p["kind"] == "registered_after_results" for p in json.loads(str(e))),
              "a rule registered after results is REFUSED")
    wrong = G.Preregistration("2026-01-01T00:00:00Z", "tester", "deadbeef" * 8, False, "x.json")
    try:
        G.validate_preregistration(rule, wrong)
        check(False, "a rule whose digest does not match its registration is REFUSED")
    except G.PreregistrationFailure as e:
        check(any(p["kind"] == "digest_mismatch" for p in json.loads(str(e))),
              "a rule whose digest does not match its registration is REFUSED")

    # structural: the type the rule conditions on carries no performance information
    fields = set(G.SupportSummary.__dataclass_fields__)
    forbidden = {"target", "y", "residual", "prediction", "metric", "mae", "rmse", "score",
                 "test", "loss"}
    check(not (fields & forbidden), "SupportSummary carries no target/metric field", str(fields))
    check(all(not any(w in f for w in ("target", "resid", "metric", "mae", "rmse", "test"))
              for f in fields),
          "no SupportSummary field name even alludes to performance", str(fields))

    # behaviour: rule fires on every fold, drops symmetrically, and downgrades the verdict
    df = _synth()
    df["tier"] = 0.0
    df.loc[df["season"] != 2021, "tier"] = (
        np.arange((df["season"] != 2021).sum()) % 3 == 0).astype(float)
    r_no = G.guard(df, ["x1"], ["tier"], "offset_projected", "game_id",
                   null_nuisance=["tier"], arm_id="no_rule")
    r_yes = G.guard(df, ["x1"], ["tier"], "offset_projected", "game_id",
                    null_nuisance=["tier"], rule=rule, prereg=good, arm_id="with_rule")
    r_bad = G.guard(df, ["x1"], ["tier"], "offset_projected", "game_id",
                    null_nuisance=["tier"], rule=rule, prereg=late, arm_id="post_hoc_rule")
    v_no = {f["fold_id"]: f["verdict"] for f in r_no["folds"]}
    v_yes = {f["fold_id"]: f["verdict"] for f in r_yes["folds"]}
    v_bad = {f["fold_id"]: f["verdict"] for f in r_bad["folds"]}
    check(v_no["train_2021"] == G.VERDICT_UNEVALUABLE,
          "without a rule the degenerate fold is UNEVALUABLE")
    check(v_yes["train_2021"] == G.VERDICT_ESTIMABLE_UNDER_RULE,
          "with a conforming rule it is ESTIMABLE_UNDER_PREREGISTERED_ACTIVE_SET", str(v_yes))
    check(v_bad == v_no, "a post-hoc rule changes NOTHING", str(v_bad))
    check(r_bad["preregistration_problems"] is not None,
          "and the refusal is recorded in the receipt")
    rec = [f for f in r_yes["folds"] if f["fold_id"] == "train_2021"][0]["active_set_rule"]
    for k in ("rule_id", "rule_spec_sha256", "preregistration", "summary_the_rule_saw",
              "dropped", "kept", "why"):
        check(k in rec, f"receipt records {k}")
    check("tier" in rec["dropped"], "the rule dropped the unsupported term", str(rec["dropped"]))
    # symmetry: the null's active nuisance equals the candidate's
    f21 = [f for f in r_yes["folds"] if f["fold_id"] == "train_2021"][0]
    pc = r_yes["parameter_count_reconciliation"]["train_2021"]
    check(pc["candidate_nuisance"] == pc["null_nuisance"],
          "the active set is applied symmetrically to candidate and null", str(pc))
    check(pc["reconciled"], "and the parameter counts still reconcile after the drop")
    check(f21["active_nuisance"] == [], "the dropped term is out of the fold's active set")
    # every fold was evaluated by the rule, not only the ones that blocked
    check(all(f["active_set_rule"] is not None and f["active_set_rule"].get("applied")
              for f in r_yes["folds"]),
          "the rule is evaluated on EVERY fold, not only on folds that blocked")


def t08_no_silent_pooled_pass():
    print("\n[T08] SYNTHETIC: a pooled pass is never silently reported as a pass")
    df = _synth()
    df["tier"] = 0.0
    df.loc[df["season"] != 2021, "tier"] = (
        np.arange((df["season"] != 2021).sum()) % 3 == 0).astype(float)
    r = G.guard(df, ["x1"], ["tier"], "offset_projected", "game_id",
                null_nuisance=["tier"], arm_id="pooled_trap")
    pv = r["pooled_vs_fold_reconciliation"]
    check(r["final_design"]["blocking"] == [], "the final assembled design has no blocking finding")
    check("tier" in pv["terms_absent_or_zero_variance_in_at_least_one_fold"],
          "the absent-in-a-fold term is named")
    check(pv["pooled_pass_would_be_misleading"], "the pooled pass is flagged as misleading")
    check(r["overall"] != "PASS", "and overall is NOT PASS", r["overall"])
    # a genuinely healthy design must still be able to reach PASS, or the guard is useless
    clean = G.guard(df, ["x1", "x2"], [], "offset_projected", "game_id", arm_id="clean")
    check(clean["overall"] == "PASS", "a healthy design still reaches PASS", clean["overall"])


# ---------------------------------------------------------------------------
def _universe():
    from run_s7_measurements import build_universe, realised_target
    return build_universe().merge(realised_target(), on=["game_id", "team_id"], how="left")


def t09_artifact_universe():
    print("\n[T09] ARTIFACT: the universe is the packet's 2,982 rows over 1,491 clusters")
    U = _universe()
    check(len(U) == 2982, "2,982 team-game rows", str(len(U)))
    check(U["game_id"].nunique() == 1491, "1,491 game clusters", str(U["game_id"].nunique()))
    check(set(U.groupby("game_id").size().unique()) == {2}, "exactly two team-rows per cluster")
    check(sorted(U["season"].unique()) == [2021, 2022, 2023, 2024, 2025, 2026],
          "six seasons", str(sorted(U["season"].unique())))


def t10_artifact_S7_reproduces():
    print("\n[T10] ARTIFACT: the S7 measurement -- a tier identically zero in four of six folds")
    U = _universe()
    ct = pd.crosstab(U["pace_source"], U["season"])
    packet = {"league_prior_all": {2021: 28, 2022: 0, 2023: 0, 2024: 0, 2025: 3, 2026: 6},
              "team_window_prior_season": {2021: 0, 2022: 36, 2023: 36, 2024: 36, 2025: 36,
                                           2026: 39},
              "team_window_same_season": {2021: 382, 2022: 442, 2023: 484, 2024: 488, 2025: 581,
                                          2026: 385}}
    for tier, per in packet.items():
        for season, n in per.items():
            got = int(ct.loc[tier, season]) if tier in ct.index and season in ct.columns else 0
            check(got == n, f"pace_source[{tier}][{season}] == {n}", f"measured {got}")
    zero_seasons = sorted({int(c) for i in ct.index for c in ct.columns if int(ct.loc[i, c]) == 0})
    check(ct.shape[1] == 6, "six chronological season folds", str(ct.shape[1]))
    check(zero_seasons == [2021, 2022, 2023, 2024],
          "four of six folds carry an identically-zero tier indicator", str(zero_seasons))

    # and the guard reaches that conclusion by itself, on the tier partition K0_MATCHED carries
    tiers = ["tier_league_prior_all", "tier_team_window_prior_season"]
    r = G.guard(U, [], tiers, "offset_projected", "game_id",
                null_nuisance=tiers, arm_id="K0_MATCHED_tier_refcoded")
    une = [f["fold_id"] for f in r["folds"] if f["verdict"] == G.VERDICT_UNEVALUABLE]
    check(une == ["train_2021", "train_2022", "train_2023", "train_2024"],
          "the guard marks exactly those four folds UNEVALUABLE_PROSPECTIVELY", str(une))
    check(r["final_design"]["verdict"] == G.VERDICT_ESTIMABLE,
          "while the FINAL assembled design is estimable")
    check(r["overall"] == "FAIL", "overall FAIL", r["overall"])


def t11_artifact_frozen_gate_pooled_passes_what_folds_block():
    print("\n[T11] ARTIFACT: the frozen gate itself passes pooled and blocks per fold")
    U = _universe()
    tiers = ["tier_league_prior_all", "tier_team_window_prior_season"]
    off = U["offset_projected"].to_numpy(float)
    pooled = fg.audit(U, tiers, offset=off, test_df=U)
    check(pooled["passed"], "frozen gate PASSES the pooled 2,982-row tier design")
    blocked = []
    for s in sorted(U["season"].unique()):
        sub = U[U["season"] == s]
        try:
            fg.audit(sub, tiers, offset=sub["offset_projected"].to_numpy(float), test_df=sub)
        except fg.FeatureGateFailure:
            blocked.append(int(s))
    check(blocked == [2021, 2022, 2023, 2024],
          "and BLOCKS on 2021-2024 when invoked per fold", str(blocked))


def t12_artifact_S5_offset_absorption():
    print("\n[T12] ARTIFACT: S5 -- own + opp reproduce the offset; the frozen gate passes it")
    U = _universe()
    dev = float((U["own_pace_est"] + U["opp_pace_est"]
                 - 2.0 * U["offset_projected"]).abs().max())
    check(dev == 0.0, "own_est + opp_est == 2 * projected, max abs deviation 0.0", str(dev))
    c1 = round(float(np.corrcoef(U["own_pace_est"], U["offset_projected"])[0, 1]), 4)
    c2 = round(float(np.corrcoef(U["own_pace_est"], U["opp_pace_est"])[0, 1]), 4)
    check(c1 == 0.7738, "corr(own, projected) == 0.7738", str(c1))
    check(c2 == 0.1977, "corr(own, opp) == 0.1977", str(c2))
    check(c1 < 0.999 and c2 < 0.999, "both are far below the gate's 0.999 threshold")
    gate = fg.audit(U, ["own_pace_est", "opp_pace_est"],
                    offset=U["offset_projected"].to_numpy(float),
                    target=U["realised_off_poss"].to_numpy(float), test_df=U)
    check(gate["passed"], "frozen gate PASSES the opponent design")
    check(gate["design_rank"]["full_rank"], "and reports it FULL RANK")
    r = G.guard(U, ["own_pace_est", "opp_pace_est"],
                ["tier_league_prior_all", "tier_team_window_prior_season"],
                "offset_projected", "game_id",
                null_nuisance=["tier_league_prior_all", "tier_team_window_prior_season"],
                arm_id="opponent_adjustment_challenger")
    kinds = {b["kind"] for b in r["final_design"]["blocking"]}
    check("offset_in_design_span" in kinds,
          "the guard blocks the final design on offset_in_design_span", str(sorted(kinds)))
    check(all(f["verdict"] == G.VERDICT_UNEVALUABLE for f in r["folds"]),
          "and marks every fold UNEVALUABLE_PROSPECTIVELY")
    check(r["final_design"]["offset_absorption"]["relative_residual_norm"] < 1e-12,
          "relative residual of the offset on the design is machine zero",
          str(r["final_design"]["offset_absorption"]["relative_residual_norm"]))


def t13_measurements_file_is_present_and_consistent():
    print("\n[T13] the node's MEASUREMENTS.json exists and agrees with a live recomputation")
    p = HERE / "MEASUREMENTS.json"
    check(p.exists(), "MEASUREMENTS.json exists")
    if not p.exists():
        return
    m = json.loads(p.read_text(encoding="utf-8"))
    check(m["M1_universe"]["matches_packet"], "recorded universe matches the packet")
    check(m["M2_S7_reproduction"]["claim_four_of_six"], "recorded S7 claim is four of six")
    check(m["M3_S5_reproduction"]["max_abs_deviation"] == 0.0, "recorded S5 deviation is 0.0")
    check(m["frozen_gate_constants_mirrored"]["agree"], "recorded gate constants agree")
    check(m["M6_frozen_gate_pooled_vs_per_fold"]["pooled"]["passed"],
          "recorded: frozen gate passed pooled")
    check(m["M6_frozen_gate_pooled_vs_per_fold"]["pooled_passed_but_folds_blocked"]
          == ["train_2021", "train_2022", "train_2023", "train_2024"],
          "recorded: four folds blocked")
    check(m["headlines"]["D_K0_MATCHED_refcoded_with_valid_rule"]["overall"]
          == "PASS_UNDER_PREREGISTERED_ACTIVE_SET",
          "recorded: the conforming-rule scenario passes under the rule")
    check(m["headlines"]["E_rule_registered_after_results_is_refused"]["overall"] == "FAIL",
          "recorded: the post-hoc-rule scenario fails")
    check(m["headlines"]["C_opponent_arm_vs_K0_refcoded"]["overall"] == "FAIL",
          "recorded: the opponent arm fails")


def main() -> int:
    print("P27_FOLD_LOCAL_ESTIMABILITY_GUARD -- TESTS")
    print("epistemic status: INFRASTRUCTURE + task-specific INVARIANT. Proves an arm/fold is "
          "estimable\nbefore it is fitted. Does not establish that an estimable arm is a real "
          "effect.")
    for t in (t01_frozen_gate_untouched, t02_fold_construction,
              t03_fold_local_zero_variance_that_pooled_hides,
              t04_offset_and_nuisance_enter_the_rank_audit,
              t05_cluster_support_not_row_support,
              t06_parameter_count_reconciliation,
              t07_active_set_rule_discipline,
              t08_no_silent_pooled_pass,
              t09_artifact_universe, t10_artifact_S7_reproduces,
              t11_artifact_frozen_gate_pooled_passes_what_folds_block,
              t12_artifact_S5_offset_absorption,
              t13_measurements_file_is_present_and_consistent):
        try:
            t()
        except Exception as e:                                  # noqa: BLE001
            FAILS.append(f"{t.__name__} raised {type(e).__name__}: {e}")
            print(f"  FAIL {t.__name__} raised {type(e).__name__}: {e}")
    print(f"\n{NCHECK - len(FAILS)}/{NCHECK} checks passed")
    if FAILS:
        print("\nFAILURES:")
        for f in FAILS:
            print("  -", f)
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
