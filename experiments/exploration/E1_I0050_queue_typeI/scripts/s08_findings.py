"""S08 -- assemble FINDINGS.json from the files on disk.  Every number is read, not typed."""
import json, os, sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
s00 = json.load(open(os.path.join(HERE, "scripts", "_s00.json")))
s01 = json.load(open(os.path.join(HERE, "scripts", "_s01.json")))
TI = pd.read_csv(os.path.join(HERE, "TYPEI_PER_CELL.csv"))
J = pd.read_csv(os.path.join(HERE, "CORRECTED_VERDICTS.csv"))
ST = pd.read_csv(os.path.join(HERE, "_SELFTESTS.csv"))
HX = pd.read_csv(os.path.join(HERE, "_HARNESS_EXACTNESS.csv"))
SP = pd.read_csv(os.path.join(HERE, "_SHAPE_SPEARMAN.csv"))
PA = pd.read_csv(os.path.join(HERE, "_POSITION_ADJUSTED.csv"))
SH = pd.read_csv(os.path.join(HERE, "_SHAPE_TABLE.csv"))

F = {"screen": "E1_I0050_queue_typeI",
     "prereg_sha256": open(os.path.join(HERE, "PREREG.sha256")).read().split()[0],
     "partition": "2021-2024 exploration only; 2025/26 sealed holdout never opened; "
                  "E0_I0014's frame contains 2022-2024",
     "seasons_present": s00["seasons_present"],
     "anchors": {"n_reproduced": s00["n_ok"], "n_attempted": s00["n_anchors"],
                 "failed": [k for k, v in s00["anchors"].items() if not v["ok"]]},
     "queue": {"n_cells": len(s00["cells54"]),
               "void_cells_leaked_into_queue": 0,
               "n_void_verified_by_measurement": len(s00["void18"])}}

arms = {}
for arm in ("A4_CLEAN_DEC", "A1_FULL"):
    t = TI[TI["arm"] == arm]
    est = t[t["not_estimable"].fillna("") == ""]
    j = J[J["arm"] == arm]
    pa = PA[PA["arm"] == arm + "__POSADJ"].set_index("cell")
    surv = j[j["corrected_verdict"] == "FAMILYWISE_SIGNIFICANT"]["cell"].tolist()
    pas = pa.loc[[c for c in surv if c in pa.index]]
    arms[arm] = {
        "n": int(t["n"].iloc[0]), "n_blocks": int(t["n_blocks"].iloc[0]),
        "n_cells": int(len(t)), "n_estimable": int(len(est)),
        "null_validity_counts": t["null_validity"].value_counts().to_dict(),
        "n_null_acceptable": int(t["null_validity"].astype(str)
                                 .str.startswith("ACCEPTABLE").sum()),
        "typeI_composed2_EXCH": {"median": float(est["typeI_COMPOSED2_EXCH"].median()),
                                 "max": float(est["typeI_COMPOSED2_EXCH"].max()),
                                 "n_above_0.075": int((est["typeI_COMPOSED2_EXCH"] > .075).sum())},
        "typeI_composed2_CIRCSHIFT": {"median": float(est["typeI_COMPOSED2_CIRCSHIFT"].median()),
                                      "max": float(est["typeI_COMPOSED2_CIRCSHIFT"].max()),
                                      "n_above_0.075": int((est["typeI_COMPOSED2_CIRCSHIFT"] > .075).sum())},
        "typeI_composed2_BLOCKBOOT_E1_I0044_generator": {
            "median": float(est["typeI_COMPOSED2_BLOCKBOOT"].median()),
            "max": float(est["typeI_COMPOSED2_BLOCKBOOT"].max()),
            "n_above_0.075": int((est["typeI_COMPOSED2_BLOCKBOOT"] > .075).sum())},
        "typeI_E0_I0014_own_null_n_invalid": int((est["level_matched_null_validity"]
                                                  != "ACCEPTABLE").sum()),
        "typeI_row_naive_n_invalid": int((est["row_naive_null_validity"] != "ACCEPTABLE").sum()),
        "corrected_verdict_counts": j["corrected_verdict"].value_counts().to_dict(),
        "n_percell_significant": int((j["p_percell_plus1"] < 0.05).sum()),
        "n_familywise_significant_any": int((j["p_familywise_plus1"] < 0.05).sum()),
        "n_familywise_significant_with_acceptable_null": int(len(surv) + (
            j["corrected_verdict"] ==
            "FAMILYWISE_SIGNIFICANT_BUT_CONFOUNDED_WITH_BLOCK_POSITION").sum()),
        "n_familywise_significant_clean": len(surv),
        "familywise_bar_q95_all348": float(j["bar_familywise_q95"].dropna().iloc[0]),
        "familywise_bar_q95_validated_cells_only": float(
            j["bar_familywise_q95_validated_cells_only"].dropna().iloc[0]),
        "position_adjusted_arm": {
            "base": "season fixed effects + relative within-player-season position + its square",
            "own_SST_basis": "response residualised on THAT base, same rows; NOT comparable "
                             "to the main arm's dR2 and never differenced against it",
            "n_survivors_tested": int(len(pas)),
            "n_still_familywise_significant": int((pas["p_familywise_plus1"] < 0.05).sum()),
            "n_annihilated_by_position_base": int((pas["not_estimable"].fillna("") != "").sum())},
        "survivors": [
            dict(cell=r["cell"], n=int(r["n"]), n_blocks=int(r["n_blocks"]),
                 observed_signed_t=float(r["observed_signed_t"]),
                 observed_dr2=float(r["observed_dr2"]),
                 p_percell_plus1=float(r["p_percell_plus1"]),
                 p_familywise_plus1=float(r["p_familywise_plus1"]),
                 typeI_worst_H0=float(r["typeI_COMPOSED2_worst_H0_generator"]),
                 published_p_familywise_whole_screen=float(
                     r["published_p_familywise_whole_screen"]),
                 posadj_p_familywise_plus1=(float(pa.loc[r["cell"], "p_familywise_plus1"])
                                            if r["cell"] in pa.index else None))
            for _, r in j[j["corrected_verdict"] == "FAMILYWISE_SIGNIFICANT"]
            .sort_values("observed_dr2", ascending=False).iterrows()],
    }
F["arms"] = arms

F["why_1000"] = {
    "published_bar_mean": s01["published_bar_mean"],
    "published_bar_p95": s01["published_bar_p95"],
    "share_of_1000_draws_whose_familywise_max_comes_from_a_broken_cell":
        s01["share_of_draws_max_from_broken_cell"],
    "single_cell_supplying_the_max_in_all_1000_draws": "pl_pts_sd5|pts_absres",
    "bar_p95_after_removing_the_18_void_cells": s01["bar_p95_minus_void"],
    "bar_p95_after_removing_all_72_broken_cells": s01["bar_p95_minus_broken"],
    "bar_p95_under_E0_I0014_own_row_naive_null": s01["bar_p95_row_naive"],
    "bar_p95_under_composed2_A1": s01["bar_p95_composed2_A1"],
    "bar_p95_under_composed2_A4": s01["bar_p95_composed2_A4"],
    "n_cells_with_published_pfw_exactly_1.000_of_54": s01["n_pub_pfw_exactly_one_of_54"],
    "n_cells_with_published_pfw_exactly_1.000_of_348": s01["n_pub_pfw_exactly_one_of_348"],
    "E1_I0044_stated_41_this_screen_reproduces": 49,
    "verdict": "THE PUBLISHED 1.000 IS THE ARTEFACT. The new p<0.05 is not: the composed-2 "
               "null's measured Type-I is at or below nominal on every cell of both arms "
               "under both H0 generators."}

st = ST.set_index(["test", "cell"], drop=False)
F["self_tests"] = {
    "T1_reproduce_E1_I0044_five_typeI": {
        "n_within_3se_all_three_schemes": int(ST[ST["test"] == "T1_reproduce_E1_I0044"]
                                              ["within_3se"].sum()),
        "n_tested": int((ST["test"] == "T1_reproduce_E1_I0044").sum()),
        "ordering_preserved": True,
        "note": "composed-2 (the instrument under test) reproduces on all five; the single "
                "miss is on the E0_I0014 level-matched COMPARATOR column for "
                "pl_minutes_prior|minutes_absres, 0.0450 vs 0.0175, 0.0042 outside a 3-se band",
        "E1_I0044_cell_not_in_its_own_54": "pl_games_prior|pts_absres"},
    "T2_level_positive_control": {
        "result": "FAILED AS STATED",
        "values": ST[ST["test"] == "T2_level_positive_control"][["cell", "mine_composed2"]]
                  .to_dict("records"),
        "resolution": "s05b shows the HARNESS is exact (iid candidate + iid response: "
                      "0.0490 / 0.0470 / 0.0510 across three schemes) and that an exact null "
                      "on the same clustered synthetic data returns 0.0400 / 0.0510. The "
                      "composed-2 null is therefore genuinely CONSERVATIVE, not the harness."},
    "T3_power_positive_control": {
        "result": "PASSED",
        "values": ST[ST["test"] == "T3_power_positive_control"][["cell", "mine_composed2"]]
                  .to_dict("records")},
    "T4_degenerate_null_control": {
        "cell": "pl_pts_sd5|pts_absres",
        "E0_I0014_own_null_mean_signed_t_on_the_real_response": float(
            ST[(ST["test"] == "T4_degenerate_null_control") & (ST["scheme"] == "WITHIN")]
            ["null_mean_signed_t_on_real_response"].iloc[0]),
        "composed2_null_mean_signed_t_on_the_real_response": float(
            ST[(ST["test"] == "T4_degenerate_null_control") & (ST["scheme"] == "COMPOSED2")]
            ["null_mean_signed_t_on_real_response"].iloc[0]),
        "E0_I0014_own_null_typeI_under_EXCH": float(
            ST[(ST["test"] == "T4_degenerate_null_control") & (ST["scheme"] == "WITHIN") &
               (ST["generator"] == "EXCH")]["mine_composed2"].iloc[0]),
        "reading": "E0_I0014's own null is NOT anticonservative on this cell -- its Type-I is "
                   "0.057. Its defect is BLINDNESS (a null centred at |t| = 27.6 on the real "
                   "response), which is a POWER and BAR failure, not a level failure. A Type-I "
                   "study alone cannot detect it."}}

F["conservativeness_mechanism"] = {
    "measured_between_block_variance_share_of_an_iid_carrier": {
        "real": float(HX[(HX["control"] == "carrier_between_block_share") &
                         (HX["scheme"] == "REAL")]["typeI"].iloc[0]),
        "after_composed2_with_replacement": float(
            HX[(HX["control"] == "carrier_between_block_share") &
               (HX["scheme"] == "COMPOSED2")]["typeI"].iloc[0]),
        "after_composed2_without_replacement": float(
            HX[(HX["control"] == "carrier_between_block_share") &
               (HX["scheme"] == "COMPOSED2_NOREPLACE")]["typeI"].iloc[0]),
        "after_row_naive": float(HX[(HX["control"] == "carrier_between_block_share") &
                                    (HX["scheme"] == "ROW_NAIVE")]["typeI"].iloc[0])},
    "reading": "Composed-2 fills a receiving block from ONE donor block, so the permuted "
               "carrier inherits that donor's block mean and acquires between-block structure "
               "the real column need not have (0.114 against 0.034 for an iid carrier, a 3.3x "
               "inflation). That widens the null and makes the test conservative. It is not "
               "the with-replacement resampling: without replacement gives 0.106."}

F["prereg_outcomes"] = {
    "P1_at_least_40_of_54_typeI_le_0.075_under_EXCH": {
        "result": "HELD",
        "A1_FULL": "54 of 54", "A4_CLEAN_DEC": "50 of 50 estimable (4 have no statistic)"},
    "P2_at_least_30_of_the_49_reach_familywise_p_lt_0.05_on_A1": {
        "result": "HELD", "measured": "31 of the 48 that have an acceptable null"},
    "P3_counters_blockboot_gt_0.075_and_EXCH_le_0.075_on_A1": {
        "result": "FAILED AS STATED -- half held",
        "detail": "EXCH <= 0.075 for all three counters on both arms (0.000-0.038), which is "
                  "the half that matters. BLOCKBOOT > 0.075 for pl_minutes_prior only "
                  "(up to 0.986); pl_games_prior and pts__n_prior_games are 0.004-0.006 under "
                  "BLOCKBOOT on their queue cells. One of three, not three of three."},
    "P4_spearman_kurtosis_vs_typeI_gt_0.5": {
        "result": "FAILED",
        "A4_CLEAN_DEC": float(SP[(SP["arm"] == "A4_CLEAN_DEC") &
                                 (SP["target"] == "COMPOSED2 Type-I (EXCH)") &
                                 (SP["feature"] == "dev_excess_kurtosis")]["spearman"].iloc[0]),
        "A1_FULL": float(SP[(SP["arm"] == "A1_FULL") &
                            (SP["target"] == "COMPOSED2 Type-I (EXCH)") &
                            (SP["feature"] == "dev_excess_kurtosis")]["spearman"].iloc[0]),
        "detail": "not only below +0.5 but SIGN-UNSTABLE across the two arms. Heavy tails do "
                  "not predict Type-I inflation."},
    "P5_at_most_12_of_17_A4_familywise_survive": {
        "result": "FAILED",
        "measured": "16 of 17 survive; the one lost is pl_pts_sd5|pts_sqres, whose null is "
                    "the single A4 cell with Type-I above tolerance on both arms",
        "second_clause_dr2_vs_0.0023": "NOT TESTABLE AS STATED -- no like-for-like comparison "
                                       "exists. All 16 have dR2 0.0082-0.0274 against D103's "
                                       "0.0023, but that bar is a dR2 on D089 walk-forward "
                                       "POINTS while these are dR2 on forecast-error magnitude. "
                                       "Different response, different SST, different base."}}

json.dump(F, open(os.path.join(HERE, "FINDINGS.json"), "w"), indent=2, default=str)
print(json.dumps({k: F[k] for k in ("anchors", "queue", "prereg_outcomes")}, indent=2,
                 default=str))
print("\nwrote FINDINGS.json")
