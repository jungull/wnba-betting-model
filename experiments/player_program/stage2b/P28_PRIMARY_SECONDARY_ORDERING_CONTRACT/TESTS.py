#!/usr/bin/env python3
"""TESTS.py -- standalone assertions for the P28 ordering contract. pytest is NOT available.

Run:  python experiments/player_program/stage2b/P28_PRIMARY_SECONDARY_ORDERING_CONTRACT/TESTS.py
main() returns 1 on any failure, 0 otherwise.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PP = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(PP))

import ordering_contract as oc                                          # noqa: E402

FAILS: list[str] = []
NCHECK = 0


def check(cond: bool, label: str) -> None:
    global NCHECK
    NCHECK += 1
    if not cond:
        FAILS.append(label)


def raises(fn, label: str) -> None:
    global NCHECK
    NCHECK += 1
    try:
        fn()
    except oc.OrderingContractFailure:
        return
    except Exception as exc:                                           # wrong exception type
        FAILS.append(f"{label} (raised {type(exc).__name__}: {exc})")
        return
    FAILS.append(f"{label} (did not raise)")


def primary(**over):
    rec = {
        "schema": "player_program_primary_verdict/1",
        "contract_id": oc.CONTRACT_ID,
        "candidate_id": "EXAMPLE_candidate_1",
        "arm_id": "EXAMPLE_arm_1",
        "target": oc.PRIMARY_TARGET,
        "metric_name": "mae",
        "lower_is_better": True,
        "k0_matched_arm_id": "K0_MATCHED[EXAMPLE_arm_1]",
        "row_universe_digest": "0" * 64,
        "n_rows": 2982,
        "n_game_clusters": 1491,
        "primary_mae_challenger": 2.85,
        "primary_mae_k0_matched": 2.95,
        "primary_delta_vs_k0": -0.10,
        "registered_med": 0.05,
        "med_registered_before_fitting": True,
        "per_fold": [{"fold": s, "delta": -0.1} for s in
                     ("2021", "2022", "2023", "2024", "2025", "2026")],
        "feature_channel_declarations": [
            {"feature": "pace_gap", "declared_benefit_channels": ["pace_level_estimation"],
             "primary_target_contribution_demonstrated": True, "adjudication": None}],
        "verdict": "PASS",
        "sealed_by": "TESTS.py",
        "downstream_computed": False,
    }
    rec.update(over)
    return rec


def downstream(sealed, **over):
    rec = {
        "schema": "player_program_downstream_receipt/1",
        "contract_id": oc.CONTRACT_ID,
        "candidate_id": sealed["candidate_id"],
        "primary_verdict_digest": sealed["primary_verdict_digest"],
        "epistemic_role": "secondary_diagnostic",
        "scorer": {"file": oc.FROZEN_SCORER, "line": 149,
                   "sha256": oc.FROZEN_SCORER_SHA256, "modified": False},
        "documented_mismatch_restated": dict(oc.DOCUMENTED_MISMATCH),
        "strata": {"overtime": {"n_rows": 132, "n_game_clusters": 66, "mae": 2.17},
                   "regulation": {"n_rows": 2850, "n_game_clusters": 1425, "mae": 0.52}},
        "may_overturn_primary": False,
    }
    rec.update(over)
    return rec


# --------------------------------------------------------------------------- #
def T01_contract_constants():
    s = oc.contract_summary()
    check(s["primary_target"] == "REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS",
          "T01 primary target string is the settled one")
    check(s["primary_lower_is_better"] is True, "T01 sign convention pinned")
    check(s["downstream_role"] == "secondary_diagnostic", "T01 downstream role pinned")
    check(set(s["rules"]) == {f"R{i}" for i in range(1, 9)}, "T01 all eight rules present")
    check(s["documented_mismatch"]["disposition"].startswith("RESTATED, NOT REPAIRED"),
          "T01 mismatch is restated not repaired")


def T02_clean_seal():
    s = oc.seal_primary_verdict(primary())
    check(s["sealed"] is True, "T02 a clean primary verdict seals")
    check(len(s["primary_verdict_digest"]) == 64, "T02 digest is a sha256 hex")
    check(s["ordering_findings"] == [], "T02 no findings on a clean record")


def T03_downstream_before_seal_blocked():
    raises(lambda: oc.seal_primary_verdict(primary(downstream_computed=True)),
           "T03 R2: sealing refuses a record that admits downstream was already computed")


def T04_target_substitution_blocked():
    raises(lambda: oc.seal_primary_verdict(primary(target="RAW_TEAM_OFFENSIVE_POSSESSIONS")),
           "T04 the primary target may not be swapped")
    raises(lambda: oc.seal_primary_verdict(primary(metric_name="turnover_mae")),
           "T04 the primary metric may not be swapped")


def T05_sign_convention():
    raises(lambda: oc.seal_primary_verdict(primary(primary_delta_vs_k0=0.10)),
           "T05 delta must equal challenger - K0")
    raises(lambda: oc.seal_primary_verdict(primary(lower_is_better=False)),
           "T05 lower_is_better must be True for MAE")


def T06_worsening_primary_cannot_be_PASS():
    bad = primary(primary_mae_challenger=3.05, primary_delta_vs_k0=0.10, verdict="PASS")
    raises(lambda: oc.seal_primary_verdict(bad),
           "T06 R4: a worsening primary target may not be recorded PASS")
    rep = oc.seal_primary_verdict(bad, raise_on_block=False)
    kinds = {f["kind"] for f in rep["ordering_findings"]}
    check("worsening_primary_not_marked_FAIL" in kinds,
          "T06 the worsening finding is named explicitly")


def T07_worsening_primary_as_FAIL_seals_and_fails():
    rec = primary(primary_mae_challenger=3.05, primary_delta_vs_k0=0.10, verdict="FAIL")
    s = oc.seal_primary_verdict(rec)
    check(s["sealed"] is True, "T07 a correctly-marked FAIL still seals")
    v = oc.adjudicate(s, downstream(s, strata={
        "overtime": {"n_rows": 132, "n_game_clusters": 66, "mae": 0.01},
        "regulation": {"n_rows": 2850, "n_game_clusters": 1425, "mae": 0.01}}))
    check(v["final_verdict"] == "FAIL",
          "T07 R3/R4: a spectacular downstream figure does not rescue a primary FAIL")
    check(v["downstream_consulted"] is False,
          "T07 the downstream figure was not consulted at all")
    check(v["decided_by"] == "PRIMARY_TARGET_ONLY", "T07 decided by the primary target only")


def T08_authorize_requires_seal():
    unsealed = dict(primary())
    unsealed["sealed"] = False
    unsealed["primary_verdict_digest"] = "x" * 64
    raises(lambda: oc.authorize_downstream(unsealed),
           "T08 R1: an unsealed primary verdict cannot authorise the frozen scorer")


def T09_authorize_refuses_primary_fail():
    s = oc.seal_primary_verdict(primary(primary_mae_challenger=3.05,
                                        primary_delta_vs_k0=0.10, verdict="FAIL"))
    raises(lambda: oc.authorize_downstream(s),
           "T09 R1/R3: a primary FAIL may not enter the frozen turnover scorer at all")
    rep = oc.authorize_downstream(s, raise_on_block=False)
    check(rep["authorized"] is False, "T09 authorization is refused")
    check("primary_verdict_is_FAIL" in {f["kind"] for f in rep["findings"]},
          "T09 the refusal names the primary FAIL")


def T10_authorize_allows_a_pass():
    s = oc.seal_primary_verdict(primary())
    rep = oc.authorize_downstream(s)
    check(rep["authorized"] is True, "T10 a sealed primary PASS authorises the scorer")
    check(rep["primary_verdict_digest"] == s["primary_verdict_digest"],
          "T10 the authorisation carries the digest the downstream receipt must bind")


def T11_binding_broken():
    s = oc.seal_primary_verdict(primary())
    raises(lambda: oc.validate_downstream_receipt(
        downstream(s, primary_verdict_digest="f" * 64), s),
        "T11 R2: a downstream receipt bound to the wrong primary digest is refused")


def T12_primary_mutated_after_sealing():
    s = oc.seal_primary_verdict(primary())
    d = downstream(s)
    tampered = dict(s)
    tampered["primary_mae_challenger"] = 2.10          # rewrite history, keep the old digest
    raises(lambda: oc.validate_downstream_receipt(d, tampered),
           "T12 R2: mutating the primary verdict after sealing is detected by recomputation")


def T13_scorer_is_frozen():
    s = oc.seal_primary_verdict(primary())
    for over, label in (
            ({"file": "experiments/player_program/my_fixed_scorer.py", "line": 149,
              "sha256": oc.FROZEN_SCORER_SHA256, "modified": False}, "substituted file"),
            ({"file": oc.FROZEN_SCORER, "line": 149, "sha256": "9" * 64, "modified": False},
             "changed bytes"),
            ({"file": oc.FROZEN_SCORER, "line": 149, "sha256": oc.FROZEN_SCORER_SHA256,
              "modified": True}, "declared modified")):
        raises(lambda o=over: oc.validate_downstream_receipt(downstream(s, scorer=o), s),
               f"T13 R6: the frozen scorer is refused when {label}")


def T14_mismatch_must_be_restated_verbatim():
    s = oc.seal_primary_verdict(primary())
    repaired = dict(oc.DOCUMENTED_MISMATCH)
    repaired["disposition"] = "REPAIRED: turnovers rescaled to regulation-equivalent"
    raises(lambda: oc.validate_downstream_receipt(
        downstream(s, documented_mismatch_restated=repaired), s),
        "T14 R6: the mismatch must be restated verbatim; a 'repair' is refused")
    dropped = {k: v for k, v in oc.DOCUMENTED_MISMATCH.items() if k != "n_OT_rows"}
    raises(lambda: oc.validate_downstream_receipt(
        downstream(s, documented_mismatch_restated=dropped), s),
        "T14 dropping a restated field is refused")


def T15_strata_required():
    s = oc.seal_primary_verdict(primary())
    raises(lambda: oc.validate_downstream_receipt(
        downstream(s, strata={"regulation": {"n_rows": 2850, "n_game_clusters": 1425,
                                             "mae": 0.52}}), s),
        "T15 R7: the OT stratum must be reported separately")
    raises(lambda: oc.validate_downstream_receipt(
        downstream(s, strata={"overtime": {"mae": 2.17},
                              "regulation": {"n_rows": 2850, "n_game_clusters": 1425,
                                             "mae": 0.52}}), s),
        "T15 R7: an OT figure without its row count is refused")


def T16_downstream_cannot_claim_authority():
    s = oc.seal_primary_verdict(primary())
    raises(lambda: oc.validate_downstream_receipt(downstream(s, may_overturn_primary=True), s),
           "T16 R3: a receipt claiming authority over the primary verdict is refused")
    raises(lambda: oc.validate_downstream_receipt(
        downstream(s, epistemic_role="primary_decision"), s),
        "T16 R7: relabelling the downstream role is refused")


def T17_R5_only_channel_is_the_mismatch():
    c = oc.classify_feature_channel({
        "feature": "trailing_ot_rate",
        "declared_benefit_channels": ["ot_mismatch_arbitrage"],
        "primary_target_contribution_demonstrated": False, "adjudication": None})
    check(c["creditable"] is False, "T17 R5: trailing_ot_rate is not creditable")
    kinds = {f["kind"] for f in c["findings"]}
    check("benefit_channel_is_only_the_mismatch" in kinds, "T17 the sole-channel finding fires")
    check("mismatch_carrier_without_primary_contribution" in kinds,
          "T17 the carrier-name finding fires")


def T18_R5_carrier_name_patterns():
    for name in ("trailing_ot_rate", "trailing_overtime_rate", "team_ot_propensity",
                 "ot_corrected_pace_window", "overtime_rate_l10", "game_minutes_lagged",
                 "max_period_trailing_mean", "ot_adjusted_exposure", "raw_off_poss_gap",
                 "exposure_mismatch_indicator"):
        c = oc.classify_feature_channel({
            "feature": name, "declared_benefit_channels": ["pace_level_estimation"],
            "primary_target_contribution_demonstrated": False, "adjudication": None})
        check(c["name_matches_mismatch_carrier"] is True,
              f"T18 R5: '{name}' is recognised as a presumptive mismatch carrier")
        check(c["creditable"] is False, f"T18 R5: '{name}' is not creditable undemonstrated")


def T19_R5_ordinary_feature_is_creditable():
    c = oc.classify_feature_channel({
        "feature": "opponent_pace_estimate", "declared_benefit_channels": ["pace_level_estimation"],
        "primary_target_contribution_demonstrated": True, "adjudication": None})
    check(c["creditable"] is True, "T19 an ordinary declared feature is creditable")
    c2 = oc.classify_feature_channel({"feature": "opponent_pace_estimate",
                                      "declared_benefit_channels": [],
                                      "primary_target_contribution_demonstrated": True})
    check(c2["creditable"] is False, "T19 an undeclared benefit channel is not creditable")


def T20_R5_blocks_a_passing_candidate_carrying_a_carrier():
    bad = primary(feature_channel_declarations=[
        {"feature": "trailing_ot_rate", "declared_benefit_channels": ["ot_mismatch_arbitrage"],
         "primary_target_contribution_demonstrated": False, "adjudication": None}])
    raises(lambda: oc.seal_primary_verdict(bad),
           "T20 R5: a PASS carrying an uncreditable mismatch carrier is refused")
    rep = oc.seal_primary_verdict(bad, raise_on_block=False)
    check("uncreditable_feature_in_a_PASSING_candidate" in
          {f["kind"] for f in rep["ordering_findings"]},
          "T20 the refusal names the uncreditable feature")


def T21_med_and_per_fold():
    raises(lambda: oc.seal_primary_verdict(primary(primary_mae_challenger=2.94,
                                                   primary_delta_vs_k0=-0.01)),
           "T21 an improvement below the registered MED is not a PASS")
    raises(lambda: oc.seal_primary_verdict(primary(med_registered_before_fitting=False)),
           "T21 the MED must be registered before fitting")
    raises(lambda: oc.seal_primary_verdict(primary(per_fold=[])),
           "T21 a pooled-only primary verdict is refused")
    raises(lambda: oc.seal_primary_verdict(primary(k0_matched_arm_id="")),
           "T21 the per-arm K0_MATCHED must be named")


def T22_unknown_and_missing_fields():
    raises(lambda: oc.seal_primary_verdict(primary(downstrem_computed=False)),
           "T22 a typo'd field is refused rather than silently disabling a rule")
    rec = primary()
    del rec["registered_med"]
    raises(lambda: oc.seal_primary_verdict(rec), "T22 a missing required field is refused")


def T23_adjudicate_pass_path():
    s = oc.seal_primary_verdict(primary())
    d = downstream(s)
    oc.validate_downstream_receipt(d, s)
    v = oc.adjudicate(s, d)
    check(v["final_verdict"] == "PASS", "T23 a clean candidate passes")
    check(v["decided_by"] == "PRIMARY_TARGET_ONLY",
          "T23 the verdict is decided by the primary target only")
    check(v["downstream_report"]["may_overturn_primary"] is False,
          "T23 the downstream report is marked non-decisive")
    check(set(v["downstream_report"]["strata"]) == {"overtime", "regulation"},
          "T23 both strata are carried into the report")


def T24_adjudicate_has_no_downstream_branch():
    """The FAIL path must be byte-identical regardless of the downstream figure supplied."""
    s = oc.seal_primary_verdict(primary(primary_mae_challenger=3.05,
                                        primary_delta_vs_k0=0.10, verdict="FAIL"))
    outs = set()
    for mae in (0.0, 0.1, 0.5, 5.0):
        d = downstream(s, strata={"overtime": {"n_rows": 132, "n_game_clusters": 66, "mae": mae},
                                  "regulation": {"n_rows": 2850, "n_game_clusters": 1425,
                                                 "mae": mae}})
        outs.add(json.dumps(oc.adjudicate(s, d), sort_keys=True))
    check(len(outs) == 1,
          "T24 R3: the FAIL adjudication is invariant to every downstream figure supplied")


def T25_digest_is_order_independent():
    a = primary()
    b = {k: a[k] for k in reversed(list(a))}
    check(oc.canonical_digest(a) == oc.canonical_digest(b),
          "T25 the seal digest does not depend on key order")
    c = primary(primary_mae_challenger=2.851)
    check(oc.canonical_digest(a) != oc.canonical_digest(c),
          "T25 the seal digest changes when a metric changes")


def T26_frozen_scorer_sha_matches_disk():
    p = PP / "run_turnover_p1_universe_fix.py"
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    check(h == oc.FROZEN_SCORER_SHA256,
          f"T26 the pinned scorer sha256 matches the file on disk (disk={h})")
    line = p.read_text(encoding="utf-8").splitlines()[oc.FROZEN_SCORER_LINE - 1]
    check("projected_team_off_possessions" in line,
          "T26 line 149 is still the operational exposure selection")


def T27_target_string_matches_the_frozen_packet():
    packet = json.loads((PP / "stage2a" / "EVIDENCE_PACKET_V2.json").read_text(encoding="utf-8"))
    check(packet["possession_unit_ruling"]["authoritative_target"] == oc.PRIMARY_TARGET,
          "T27 the contract's primary target is the packet's authoritative target")
    rec = packet["downstream_operational_boundary"]["recorded_pairing"]
    check(rec["consumer"] == oc.DOCUMENTED_MISMATCH["consumer"],
          "T27 the restated consumer matches the packet verbatim")
    check(rec["exposure"] == oc.DOCUMENTED_MISMATCH["exposure"]
          and rec["outcome"] == oc.DOCUMENTED_MISMATCH["outcome"],
          "T27 the restated pairing matches the packet verbatim")


def T28_measured_arbitrage_is_caught():
    """The measured ORACLE arbitrage from MEASUREMENTS.json must adjudicate to FAIL."""
    m = json.loads((HERE / "MEASUREMENTS.json").read_text(encoding="utf-8"))
    fam = m["M6_arbitrage_demonstration"]["families"]["ORACLE_target_game_is_overtime"]
    opt = fam["OPTIMUM"]
    check(opt is not None, "T28 the measured arbitrage optimum exists")
    if opt is None:
        return
    base = m["M6_arbitrage_demonstration"]["baseline_lambda0"]["primary_possession_mae"]
    rec = primary(
        candidate_id="MEASURED_oracle_ot_inflation",
        primary_mae_challenger=opt["primary_possession_mae_reg_equiv"],
        primary_mae_k0_matched=base,
        primary_delta_vs_k0=round(opt["primary_possession_mae_reg_equiv"] - base, 6),
        verdict="FAIL",
        feature_channel_declarations=[
            {"feature": "ot_adjusted_exposure_inflation",
             "declared_benefit_channels": ["ot_mismatch_arbitrage"],
             "primary_target_contribution_demonstrated": False, "adjudication": None}])
    s = oc.seal_primary_verdict(rec)
    check(s["sealed"] is True, "T28 the arbitraging candidate seals as a FAIL")
    raises(lambda: oc.authorize_downstream(s),
           "T28 the arbitraging candidate never reaches the frozen scorer")
    v = oc.adjudicate(s)
    check(v["final_verdict"] == "FAIL" and v["downstream_consulted"] is False,
          "T28 the measured arbitrage adjudicates FAIL without reading its downstream gain")
    # and the same candidate declared PASS is refused outright
    raises(lambda: oc.seal_primary_verdict({**rec, "verdict": "PASS"}),
           "T28 declaring the arbitraging candidate PASS is refused at seal time")


TESTS = [v for k, v in sorted(globals().items()) if k.startswith("T") and callable(v)]


def main() -> int:
    for t in TESTS:
        try:
            t()
        except Exception as exc:                                       # noqa: BLE001
            FAILS.append(f"{t.__name__} raised {type(exc).__name__}: {exc}")
    print(f"P28 ordering contract: {NCHECK} assertions across {len(TESTS)} tests")
    if FAILS:
        print(f"FAILED ({len(FAILS)}):")
        for f in FAILS:
            print("  -", f)
        return 1
    print("all assertions passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
