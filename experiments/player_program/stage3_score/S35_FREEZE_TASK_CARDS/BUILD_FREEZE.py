r"""S35_FREEZE_TASK_CARDS - emit the frozen card set, the registry append payload, and the
pre-append registry baseline verification.

ROOT: C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program

Writes exactly three files, all inside this node's directory:
  SPEC.json                          the frozen card set (the thing that becomes immutable)
  REGISTRY_APPEND_PAYLOAD.jsonl      the append the COORDINATOR (single writer) performs
  REGISTRY_BASELINE_VERIFICATION.json proof the pre-append registry was read record by record

This node NEVER touches arm_registry.jsonl. It reads it and hashes it; nothing more.
Run VERIFY_REPAIR.py first - this script refuses to build if VERIFICATION.json is missing
or does not report all_pass.
"""
import hashlib
import json
import os
import sys

WORKTREE = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
PP = os.path.join(WORKTREE, "experiments", "player_program")
S3 = os.path.join(PP, "stage3_score")
S33R = os.path.join(S3, "S33R_PREREGISTRATION_REPAIR")
HERE = os.path.dirname(os.path.abspath(__file__))
REGISTRY = os.path.join(PP, "arm_registry.jsonl")

REL = "experiments/player_program/stage3_score/S35_FREEZE_TASK_CARDS"
PROPOSED_TS = "2026-08-07T00:00:00Z"


def sha256_file(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(chunk), b""):
            h.update(b)
    return h.hexdigest()


def canon_sha(obj):
    """The cycle-1 P35 card-hash rule, carried unchanged:
    sha256 over json.dumps(obj, sort_keys=True, separators=(',', ':')).encode('utf-8')."""
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


# ------------------------------------------------------------------ gate on the verification
VER_PATH = os.path.join(HERE, "VERIFICATION.json")
if not os.path.exists(VER_PATH):
    sys.exit("REFUSING TO FREEZE: VERIFICATION.json absent. Run VERIFY_REPAIR.py first.")
ver = json.load(open(VER_PATH, encoding="utf-8"))
if not ver.get("all_pass"):
    sys.exit("REFUSING TO FREEZE: VERIFICATION.json does not report all_pass. "
             "A freeze over an unverified repair is worse than a delay.\n"
             + json.dumps(ver.get("summary"), indent=1))

spec2_path = os.path.join(S33R, "SPEC_V2.json")
spec2 = json.load(open(spec2_path, encoding="utf-8"))
SPEC_V2_SHA = sha256_file(spec2_path)

DISP_SHA = sha256_file(os.path.join(S33R, "S34_DISPOSITION.md"))
CNOTES_SHA = sha256_file(os.path.join(S33R, "S34_SEVERITY_C_RECOVERED.md"))
K0SCHEMA_SHA = sha256_file(os.path.join(S3, "S32B_K0_CONTRACT", "K0_MATCHED_SCHEMA_SCORE.json"))
TC_MD_SHA = sha256_file(os.path.join(S3, "S30_TARGET_CONTRACT", "CYCLE2_TARGET_CONTRACT.md"))
TC_JSON_SHA = sha256_file(os.path.join(S3, "S30_TARGET_CONTRACT", "TARGET_CONTRACT.json"))
P35_C1_SHA = sha256_file(os.path.join(PP, "stage2b", "P35_FREEZE_TASK_CARDS", "SPEC.json"))
VERIFY_PY_SHA = sha256_file(os.path.join(HERE, "VERIFY_REPAIR.py"))
VERIFICATION_SHA = sha256_file(VER_PATH)
MASTER_TEAM_SHA = spec2["inputs_verified_sha256"]["data/masters/master_team.parquet"]

registry_raw = open(REGISTRY, "rb").read()
REG_SHA = hashlib.sha256(registry_raw).hexdigest()
reg_baseline = ver["checks"]["V11_registry_pre_append_baseline"]

# ---------------------------------------------------------------- the frozen element cards
ARM_ORDER = [a["arm_id"] for a in spec2["arms"]]
fam_of = {a["arm_id"]: a["family_primary"] for a in spec2["arms"]}

frozen_cards = []
for eid, rec in spec2["k0_matched"].items():
    frozen_cards.append({
        "element_id": eid,
        "arm_id": rec["arm_id"],
        "estimand": rec["estimand"],
        "primary_metric": rec["primary_metric"],
        "arm_kind": rec["arm_kind"],
        "family_primary": fam_of[rec["arm_id"]],
        "status": "FROZEN_IMPLEMENTATION_READY",
        "card_source": {
            "artifact": "experiments/player_program/stage3_score/S33R_PREREGISTRATION_REPAIR/"
                        "SPEC_V2.json",
            "artifact_sha256": SPEC_V2_SHA,
            "json_pointer": f"/k0_matched/{eid}",
        },
        "card_sha256": canon_sha(rec),
        "carried_verbatim": True,
    })

frozen_arm_blocks = []
for a in spec2["arms"]:
    frozen_arm_blocks.append({
        "arm_id": a["arm_id"],
        "family_primary": a["family_primary"],
        "elements": a["elements"],
        "n_elements": len(a["elements"]),
        "status": "FROZEN_IMPLEMENTATION_READY",
        "block_source": {
            "artifact": "experiments/player_program/stage3_score/S33R_PREREGISTRATION_REPAIR/"
                        "SPEC_V2.json",
            "artifact_sha256": SPEC_V2_SHA,
            "json_pointer": f"/arms/{ARM_ORDER.index(a['arm_id'])}",
        },
        "arm_block_sha256": canon_sha(a),
        "carried_verbatim": True,
    })

TASK_CARDS_SHA = canon_sha(frozen_cards)
ARM_BLOCKS_SHA = canon_sha(frozen_arm_blocks)

# ------------------------------------------------------------------- downstream obligations
v9 = ver["checks"]["V9_C2_era_kill_power"]
POWER_STATEMENT = (
    "POWER STATEMENT (MANDATORY, prints adjacent to any verdict this kill produces): SC06's "
    "era-instability kill is essentially UNPOWERED. Its pre-2024 support is "
    f"{v9['pre_2024_TEST_clusters']} pooled-TEST clusters "
    f"({v9['per_test_season_2022_to_2026'][0]} in 2022 + "
    f"{v9['per_test_season_2022_to_2026'][1]} in 2023) of the "
    f"{v9['pooled_test_total']} test-fold clusters at |F_H - F_A| >= 1 "
    f"({v9['pooled_clusters_at_abs_F_diff_ge_1']} pooled including the 2021 training season; "
    "rest components only, tz component added at sealed-run receipt time). CONSEQUENCE: a kill "
    "that does NOT fire is NOT evidence that the fatigue-by-era interaction is stable; it is "
    "evidence that this slate cannot tell. Any report of the era-split table that omits this "
    "statement is a reporting defect.")

downstream_obligations = {
    "O1_S36_MASTER_TEAM_PIN": {
        "source": "S34 root-path finding, carried into the freeze so it cannot be lost",
        "binds": "S36_IMPLEMENTATION (and every node that builds a feature matrix this cycle)",
        "obligation": "S36 MUST read data/masters/master_team.parquet from the PROGRAM "
                      "WORKTREE and verify its sha256 equals the pin below BEFORE building "
                      "anything. It must NEVER read the live data-worktree / main-working-tree "
                      "copy, which legitimately keeps growing as the season is captured.",
        "pinned_path_in_the_program_worktree":
            r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
            r"\data\masters\master_team.parquet",
        "pinned_sha256": MASTER_TEAM_SHA,
        "known_drifted_copy_sha256":
            "e8e35b539df2d13f2325e207b9fb2ba8b2e96da476eaa0ec877fcf5588a71c19",
        "why_it_matters": "the drifted copy yields a 1,508-cluster universe with 232 clusters "
                          "in 2026 instead of the frozen 1,491 / 215. Every count in this "
                          "freeze is false against it.",
        "on_mismatch": "HALT. Do not build. Report to the coordinator. A silent rebuild on "
                       "drifted bytes voids the preregistration.",
        "verified_at_this_node": True,
    },
    "O2_S36_GAME_ID_PREBUILD_DIGEST": {
        "source": "S34 Severity C note C4 (J11's own invitation), coordinator disposition "
                  "ADOPT THE REVIEWER'S SUGGESTION",
        "binds": "S36_IMPLEMENTATION",
        "obligation": "before any design matrix is constructed, S36 MUST emit a pre-build "
                      "digest of the game_id set of the 1,491-cluster universe and pin it into "
                      "its own receipt, converting invariants.rows - deferred to S36 on all 17 "
                      "records - from a deferred invariant into a receipted one BEFORE any fit "
                      "runs.",
        "digest_rule": "sha256 over the U+001F-joined canonicalised game_id values, sorted "
                       "lexicographically on str(game_id) ascending, UTF-8 (the S32B "
                       "column-digest canonicalisation, so the number is comparable to every "
                       "other pin in this program)",
        "must_also_report": ["n_clusters (expect 1491)",
                             "per-season census (expect 205/239/260/262/310/215)",
                             "the measured identity with the frozen store's league_average_v1 "
                             "game_id set (the interim pin S34 confirmed holds)"],
        "on_mismatch": "HALT before fitting.",
        "status_at_this_freeze": "OPEN - discharged by S36, not by this node",
    },
    "O3_SC06_ERA_KILL_POWER_STATEMENT": {
        "source": "S34 Severity C note C2, coordinator disposition ACCEPT WITH THE POWER "
                  "STATEMENT CARRIED FORWARD",
        "binds": "S40_ADJUDICATION and every downstream report, plus the S36/S38 receipt writer",
        "applies_to_kill": "SC06_SCHED_FATIGUE_DIFF kill_conditions[2] - 'era instability: "
                           "subset-Delta sign differs between pre-2024 and 2024+ AND the pooled "
                           "Delta depends on the pre-2024 split alone'",
        "applies_to_elements": ["SC06_SCHED_FATIGUE_DIFF::E2_FINAL_MARGIN_HOME",
                                "SC06_SCHED_FATIGUE_DIFF::E3_HOME_WIN_PROB"],
        "mandatory_text": POWER_STATEMENT,
        "re_derived_at_this_node": {
            "pooled_clusters_at_abs_F_diff_ge_1": v9["pooled_clusters_at_abs_F_diff_ge_1"],
            "per_test_season_2022_to_2026": v9["per_test_season_2022_to_2026"],
            "pooled_test_total": v9["pooled_test_total"],
            "pre_2024_test_clusters": v9["pre_2024_TEST_clusters"],
            "arithmetic_closes": v9["arithmetic_closes_pooled"],
            "note": "re-derived from SC06's own carded habitat numbers in SPEC_V2, which is "
                    "where the C2 reviewer got them; the underlying census is the arm's, not "
                    "this node's",
        },
        "the_kill_is_not_weakened": "the kill stays exactly as carded and stays arm-killing. "
                                    "Only the reading of a NON-firing kill is constrained.",
        "status_at_this_freeze": "REGISTERED HERE; discharged at report time",
    },
    "O4_SC11_E2_RECEIPT_NON_CITABLE": {
        "source": "S34 Severity C note C3, coordinator disposition BIND THE NON-CITABILITY "
                  "EXPLICITLY",
        "binds": "S36/S38 (label at emission), S39/S40 (label at open), every citation forever",
        "applies_to": "SC11_LEAGUE_TOTAL_DRIFT::E1_GAME_TOTAL - the cross-estimand sanity "
                      "receipt that fits the identical feature on the E2 head and receipts "
                      "|Delta-MAE(E2)|",
        "label": "NON_CITABLE_INTEGRITY_DIAGNOSTIC",
        "binding_rule": "the |Delta-MAE(E2)| number produced by this receipt is computed on an "
                        "estimand SC11 is NOT registered for and that sits in NO family. It "
                        "MUST be emitted carrying the literal label "
                        "'NON_CITABLE_INTEGRITY_DIAGNOSTIC', it may NEVER be quoted as a "
                        "performance result, it enters no Holm family, no pass tally and no "
                        "multi-survivor comparison, and it may be used for exactly one thing: "
                        "firing or not firing SC11's card-pinned implementation-integrity kill "
                        "at |Delta-MAE(E2)| > 0.10 MAE points.",
        "why": "a number that exists in the sealed outputs but belongs to no family and no "
               "registration is precisely the kind of quantity that gets quoted later as if it "
               "were a result. The label travels with the number.",
        "status_at_this_freeze": "REGISTERED HERE; enforced at emission and at every citation",
    },
    "O5_R_SC08_FLOOR": {
        "source": "S34 Severity A4, closed at S33R by the receipt route",
        "binds": "S36 (must emit), S40 (must apply the label rule)",
        "receipt_id": "R_SC08_FLOOR",
        "mandatory": True,
        "gating_on": "SC08_SIGMA_MARGIN_MAP::E3_HOME_WIN_PROB",
        "non_gating_agreement_receipt_on": ["SC01_OPP_ADJ_INTERACTING::E3_HOME_WIN_PROB",
                                            "SC06_SCHED_FATIGUE_DIFF::E3_HOME_WIN_PROB"],
        "rule": "see SPEC_V2.a4_sc08_null_strength_receipt, carried by hash. Absence of the "
                "receipt is a CARD DEFECT, not a missing nice-to-have.",
        "verified_present_in_binding_records_at_this_node":
            ver["checks"]["V6_A4_R_SC08_FLOOR_binding"]["elements_carrying_the_receipt_id"],
    },
    "O6_R_A1_EXCEPTIONS": {
        "source": "S34 Severity A1, closed at S33R by measurement",
        "binds": "S36 (must emit on EVERY element), S37 (must re-run "
                 "M_A1_GAME_DATE_CUTOFF_V2 byte-for-byte)",
        "receipt_id": "R-A1-EXCEPTIONS",
        "rule": "the enumerated exception set (10 release-order displaced + 6 clusters without "
                "a second-endpoint witness) is a mandatory non-gating sensitivity receipt on "
                "every element, and on SC06 it additionally carries an arm-killing "
                "A1-SENSITIVITY kill. master_team.game_date is frozen at "
                "CUTOFF_VALID_WITH_ENUMERATED_EXCEPTIONS - never at unconditional CUTOFF_VALID.",
        "exception_set_location":
            "SPEC_V2.a1_game_date_cutoff_promotion.replacement_measurement_registered."
            "enumerated_exception_set",
    },
    "O7_IDENTITY_SET_EXTENSION_IS_REVIEWABLE": {
        "source": "S34 Severity A2, closed at S33R by registration",
        "binds": "S36 (receipt runs at COLUMN grain), S37 (audits the classification per column)",
        "rule": "the current-game-deletion invariance receipt runs at COLUMN grain, retaining "
                "the S30 section-1 base closed set PLUS the six adjudicated extension columns "
                "and nulling every other column of every consumed source on the current game's "
                "rows. If a later reviewer rejects any extension member, the affected element "
                "set is mechanically readable from the current_game_row_consumed flags.",
        "six_extension_columns_verified_at_this_node":
            ver["checks"]["V5_A2_identity_set_extension"]["member_columns"],
        "every_column_digest_recomputed_and_matched": True,
    },
}

# ----------------------------------------------------------------------------- the SPEC
spec = {
    "schema": "stage3_score_s35_freeze_task_cards/1",
    "node": "S35_FREEZE_TASK_CARDS",
    "lane": "score",
    "cycle": 2,
    "epistemic_status":
        "FROZEN PREREGISTRATION. These bytes are immutable from this point. The freeze was "
        "authorised by a PASSED preregistration gate: S33R repaired every S34 Severity A and B "
        "finding, S34's four Severity C notes were recovered and dispositioned, and THIS node "
        "independently re-ran the repair's own measurements before freezing (VERIFICATION.json, "
        "11/11 checks PASS). Freezing authorises IMPLEMENTATION only - see "
        "what_this_freeze_authorises.",
    "root_stated_explicitly":
        r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program",

    "carry_convention":
        "Each frozen card below carries the COMPLETE S33R record BY HASH REFERENCE: the card "
        "IS SPEC_V2.json's k0_matched[element_id] object, and card_sha256 is the sha256 of that "
        "object under the cycle-1 P35 canonicalisation "
        "(json.dumps(obj, sort_keys=True, separators=(',',':')).encode('utf-8')). No field is "
        "transcribed, so no field can drift. Every field of the S33R record is binding. The "
        "same convention carries the 11 arm blocks. Shared blocks (universe, folds, inference, "
        "seed manifest, multiplicity, leakage obligations, the A1/A2/A3/A4 repair blocks) are "
        "carried the same way and restated here only where this node ADDS a binding obligation.",

    "inputs_verified_sha256": {
        "stage3_score/S30_TARGET_CONTRACT/CYCLE2_TARGET_CONTRACT.md (FROZEN law)": TC_MD_SHA,
        "stage3_score/S30_TARGET_CONTRACT/TARGET_CONTRACT.json": TC_JSON_SHA,
        "stage3_score/S33R_PREREGISTRATION_REPAIR/SPEC_V2.json (THE card set that freezes)":
            SPEC_V2_SHA,
        "stage3_score/S33R_PREREGISTRATION_REPAIR/S34_DISPOSITION.md": DISP_SHA,
        "stage3_score/S33R_PREREGISTRATION_REPAIR/S34_SEVERITY_C_RECOVERED.md": CNOTES_SHA,
        "stage3_score/S32B_K0_CONTRACT/K0_MATCHED_SCHEMA_SCORE.json": K0SCHEMA_SHA,
        "stage2b/P35_FREEZE_TASK_CARDS/SPEC.json (cycle-1 precedent)": P35_C1_SHA,
        "stage3_score/S33_PREREGISTRATION_DRAFT/SPEC.json (superseded, kept byte-frozen)":
            ver["checks"]["V3_validator_over_frozen_S33"]["s33_spec_sha256"],
        "arm_registry.jsonl PRE-APPEND BASELINE (51 records, byte-identity reference)": REG_SHA,
    },

    "verification_of_the_repair_before_freezing": {
        "principle": "Measure, do not assert. A freeze over an unverified repair is worse than "
                     "a delay, so every claim this freeze rests on was re-run at this node "
                     "against the program worktree.",
        "script": f"{REL}/VERIFY_REPAIR.py",
        "script_sha256": VERIFY_PY_SHA,
        "receipt": f"{REL}/VERIFICATION.json",
        "receipt_sha256": VERIFICATION_SHA,
        "summary": ver["summary"],
        "all_pass": ver["all_pass"],
        "headline_reproductions": {
            "17_of_17_records_schema_valid_and_cross_field_clean":
                "re-run with S33R's own VALIDATE.py (imported, not re-implemented) against the "
                "S32B schema; 0 failures; identical to the declared self_validation.results",
            "A3_stratum_pin": "max(n_H,n_A) <= 12 re-derived from the pinned master_team.parquet "
                              "on the 1,491-cluster row base: 472 pooled, 75/76/74/81/92 per "
                              "test season, 74 in 2021 - exactly the carded pin. The rejected "
                              "min<=12 reading re-derives to 516. SC02 249 and SC03 399 also "
                              "re-derive unchanged.",
            "A2_identity_set_extension": "six members present; all six column digests recomputed "
                                         "from the pinned parquets and matched byte for byte",
            "A4_R_SC08_FLOOR": "present in the BINDING per-element records (verdict_label_policy "
                               "and notes on SC08::E3, plus the non-gating agreement receipt on "
                               "SC01::E3 and SC06::E3), not only in prose",
            "B1_R5_fix": "'ERA2024' is the literal key in both sides' structural_terms and "
                         "declaration_routing and in invariants.lower_order_structural_terms on "
                         "BOTH SC06 records; the same validator run against the frozen S33 bytes "
                         "fails EXACTLY those two records on literal R5 and nothing else",
            "C2_power_figure": "17 pre-2024 pooled-test clusters (8 in 2022 + 9 in 2023 of 77) "
                               "re-derived from the card's own habitat numbers; the arithmetic "
                               "closes against the 78 pooled / 18 pre-2024 / 60 post-2024 split",
        },
        "one_documented_gap_carried_not_hidden": {
            "item": "the projected_team_off_possessions byte pin also carries a "
                    "join_key_sha256; the pin states join_key_columns [game_id, team_id] but "
                    "not the inter-column separator convention, so the join-key digest did NOT "
                    "reproduce under this node's reading.",
            "what_DID_reproduce": "the COLUMN digest itself "
                                  "(9078790427e0c3357dd8fe6a337fcc96852bfbfedaac48d963f5686894ac71bd, "
                                  "2,990 values, 8 NaN) matched exactly, as did all five "
                                  "composite column digests.",
            "assessment": "a documentation gap in the pin's own stated rule, not evidence any "
                          "digest is wrong. NOT a freeze blocker: nothing in the slate reads "
                          "the join-key digest; it is provenance metadata beside a column "
                          "digest that does reproduce.",
            "obligation": "S36 must state the join-key separator convention explicitly when it "
                          "recomputes byte pins under R10, so the pin becomes reproducible by a "
                          "third party.",
        },
        "what_this_node_did_NOT_re_verify": [
            "N6 (no D043 market-bar numeral appears anywhere in the card set): not re-derivable "
            "here without reading the bar values, which S30 section 4 forbids this author from "
            "quoting. Carried as S33R's own check; re-checkable only by a node already holding "
            "the values.",
            "R6/R7/R8/R9 and the full R10 pin recomputation remain audit-time rules assigned to "
            "S36/S37, exactly as S33R recorded. R10 was discharged at this node for all six "
            "identity-extension column pins.",
            "pipeline_id remains asserted-not-demonstrated (the frozen comparison_gate's own "
            "documented open gap, inherited, not introduced here).",
            "The S34 Severity C notes are the coordinator's transcription of the reviewer's "
            "returned text (S34 wrote no artifact). This node dispositions them as recovered; "
            "it cannot re-verify the transcription against a session transcript it cannot read.",
        ],
    },

    "counts": {
        "arms_in_candidate_universe": spec2["counts"]["arms_in_candidate_universe"],
        "arms_retained_and_frozen": spec2["counts"]["arms_retained"],
        "arms_withdrawn": spec2["counts"]["arms_withdrawn"],
        "element_cards_frozen": len(frozen_cards),
        "arm_blocks_frozen": len(frozen_arm_blocks),
        "families_primary_partition": spec2["counts"]["families_primary_partition"],
        "families_maximal_disputed_partition":
            spec2["counts"]["families_maximal_disputed_partition"],
        "registered_partitions": spec2["counts"]["families_registered_partitions"],
        "check": "17 element cards over 11 arms; 12 candidate arms minus SC07 withdrawn",
    },

    "shared_universe": spec2["shared_universe"],
    "shared_universe_re_derived_at_this_node": {
        "game_clusters": ver["checks"]["V4_A3_stratum_pin"]["universe_clusters_measured"],
        "team_game_rows": ver["checks"]["V4_A3_stratum_pin"]["team_game_rows_measured"],
        "source": "data/masters/master_team.parquet in the PROGRAM WORKTREE, sha256 "
                  + MASTER_TEAM_SHA,
        "agrees_with_the_frozen_block": True,
    },

    "frozen_inference_configuration": {
        "note": "frozen exactly as S33R carded it; restated here because implementation reads "
                "this block directly",
        "inference": spec2["inference"],
        "folds": spec2["shared_universe"]["folds"],
        "games_never_split": spec2["shared_universe"]["games_never_split"],
        "seed_manifest_plan": spec2["seed_manifest_plan"],
        "primary_gate_per_element": spec2["primary_gate_per_element"],
        "multiplicity_correction": spec2["multiplicity"]["correction"],
        "disputed_partitions_rule": spec2["multiplicity"]["disputed_partitions_rule"],
        "kills": spec2["multiplicity"]["kills"],
        "multi_survivor_rule": spec2["multiplicity"]["multi_survivor_rule"],
        "cross_estimand_claims": spec2["multiplicity"]["cross_estimand_claims"],
        "denominators_both_reported": spec2["shared_universe"]["denominators_both_reported"],
    },

    "program_alpha_declaration": {
        "no_program_wide_FWER_claim": True,
        "per_family_control": "family-Holm at alpha = 0.05 over each family's fitted elements, "
                              "applied to primary-gate p-values",
        "GOVERNING_BOUND": 0.40,
        "governing_basis": "8 families under the primary partition x 0.05. Under the frozen "
                           "rule that a disputed element must survive Holm under BOTH/EVERY "
                           "registered partition, the realized decision rule is the "
                           "INTERSECTION, so the governing additive bound is "
                           "min(0.40, 0.50) = 0.40.",
        "DISCLOSED_BOUND": 0.50,
        "disclosed_basis": "10 families under the maximal disputed partition B x 0.05. Carried "
                           "in disclosure because it is the looser number and disclosing the "
                           "looser number while the stricter one governs is the safe direction "
                           "of error.",
        "s34_C1_disposition": "ACCEPT AS-IS. S34 C1 checked this arithmetic and found the "
                              "0.50 carry to be conservative disclosure, not an error. S35 "
                              "states both and names 0.40 as GOVERNING so no future reader "
                              "mistakes 0.50 for the operative bound.",
        "partition_D_does_not_move_it": "partition D (FAM_S2_LAGGED_OWN_FORM = {SC10, SC12}) is "
                                        "a MERGE; the additive bound uses the MAXIMUM family "
                                        "count over registered partitions, and a merge never "
                                        "raises that count. The maximum is still 10 "
                                        "(partition B). D makes Holm strictly HARDER for those "
                                        "three elements.",
        "what_the_bound_is_not": "this is an additive expectation bound on program-wide false "
                                 "positives, not an FWER guarantee. No claim of program-wide "
                                 "family-wise error control is made anywhere in this cycle.",
    },

    "family_table": spec2["multiplicity"]["families"],
    "registered_partitions": spec2["multiplicity"]["registered_partitions"],
    "withdrawals": spec2["withdrawals"],

    "frozen_cards": frozen_cards,
    "frozen_arm_blocks": frozen_arm_blocks,
    "task_cards_sha256": TASK_CARDS_SHA,
    "arm_blocks_sha256": ARM_BLOCKS_SHA,

    "downstream_obligations": downstream_obligations,

    "leakage_receipt_obligations": spec2["leakage_receipt_obligations"],
    "floor_bar_discipline": spec2["floor_bar_discipline"],

    "what_this_freeze_authorises": {
        "AUTHORISED": [
            "IMPLEMENTATION at S36 against THESE EXACT BYTES: the 17 element cards and 11 arm "
            "blocks identified by the sha256 pins above, read out of SPEC_V2.json at "
            f"sha256 {SPEC_V2_SHA}. An implementation that does not reproduce those hashes is "
            "not implementing this preregistration.",
            "construction of feature matrices, K0_MATCHED constructions and the receipted "
            "diagnostics each card names, on the pinned universe and the pinned row base",
            "emission of the mandatory receipts (R_SC08_FLOOR, R-A1-EXCEPTIONS, the "
            "deletion-invariance receipt at column grain, the pre-build game_id digest)",
        ],
        "NOT_AUTHORISED_FITTING": "This freeze does NOT authorise fitting. Fitting requires a "
                                  "PASSED S37 implementation audit. Until S37 passes, no arm "
                                  "and no K0 may be fitted and no performance number may be "
                                  "computed.",
        "NOT_AUTHORISED_ADOPTION": "This freeze NEVER authorises adoption. Adoption of any "
                                   "fitted score model for operational or wager-shaped use is "
                                   "the S42_ADOPTION_DECISION USER gate (S30 user_gates). No "
                                   "node in this lane can grant it, and nothing downstream of "
                                   "S36 changes that.",
        "NOT_AUTHORISED_EDITS": "The cards are immutable from this point. Any defect discovered "
                                "downstream is handled by a NEW registry-appended erratum or "
                                "amendment record naming the defective field, never by editing "
                                "these bytes - exactly as cycle 1 handled the A24 card defect.",
        "SEALING": "results are sealed under stage3_score/SEALED_RESULTS; S39 verifies without "
                   "opening; only S40 opens (S30 blinding).",
    },

    "registry_append": {
        "protocol":
            "THIS NODE IS NOT A WRITER OF arm_registry.jsonl. That path is FROZEN under "
            "GRAPH_POLICY section 3: existing records may never be edited, reordered or "
            "rewritten. Appending is permitted only after a passed preregistration gate, which "
            "S33R + S34 + this node's verification now satisfy. The SINGLE WRITER of the append "
            "is the COORDINATOR at integration, after validating this node's output. The "
            "payload file below is appended VERBATIM, one JSON line per record, in file order, "
            "to the END of experiments/player_program/arm_registry.jsonl.",
        "payload_file": f"{REL}/REGISTRY_APPEND_PAYLOAD.jsonl",
        "baseline_file": f"{REL}/REGISTRY_BASELINE_VERIFICATION.json",
        "pre_append_baseline": {
            "n_records": reg_baseline["n_records"],
            "file_sha256": REG_SHA,
            "file_bytes": reg_baseline["file_bytes_pre_append"],
            "file_ends_with_newline": reg_baseline["file_ends_with_newline"],
        },
        "byte_identity_proof_the_coordinator_must_run":
            "REGISTRY_BASELINE_VERIFICATION.json carries the sha256 of EVERY existing record "
            f"line (all {reg_baseline['n_records']}) computed BEFORE any append. After the "
            f"append, re-hash the first {reg_baseline['n_records']} lines individually and "
            "confirm each matches; then confirm the first "
            f"{reg_baseline['file_bytes_pre_append']} bytes of the file are byte-identical to "
            f"the pre-append content whose sha256 is {REG_SHA}. Any divergence means the "
            "frozen registry was mutated and the append must be reverted.",
        "line_ending_note":
            "the existing file has MIXED line endings (28 LF, 23 CRLF) for historical reasons "
            "and ends with a newline. New records are emitted LF-terminated, matching the most "
            "recent 16 records including cycle-1's own P35 append block. The coordinator must "
            "not normalise the existing lines - normalising CRLF to LF would rewrite frozen "
            "records.",
        "records_to_append": None,  # filled below
    },

    "stop_condition": {
        "tripped": False,
        "detail":
            "Per S30 section 11. This node changes NOTHING: it freezes S33R's bytes by hash and "
            "adds only downstream reporting/receipt obligations that the S34 Severity C "
            "dispositions already mandated. The estimands (E1/E2/E3), the K0 structure, the "
            "inference scaffold, the universe (1,491 clusters / 2,982 rows), the family table, "
            "the program-alpha arithmetic and the leakage status all stand exactly as S33R left "
            "them. The two boundary items S33R recorded - the game_date promotion to "
            "CUTOFF_VALID_WITH_ENUMERATED_EXCEPTIONS and the S34-adjudicated schedule-identity "
            "extension - are carried forward unchanged and unenlarged. This node does not mark "
            "its own work accepted.",
    },

    "prohibitions_honoured":
        "No fit performed. No performance number computed or read. Nothing under "
        "stage2b/SEALED_RESULTS or stage3_score/SEALED_RESULTS was read, listed or globbed. No "
        "frozen artifact modified: SPEC_V2.json, the S33 draft, the S30 contract and "
        "arm_registry.jsonl were all opened READ-ONLY. arm_registry.jsonl was NOT appended to by "
        "this node. git was not run. All writes are inside "
        f"{REL}/. Every measurement ran against the PROGRAM WORKTREE, whose "
        f"data/masters/master_team.parquet matches the pin {MASTER_TEAM_SHA[:8]}...; the main "
        "working tree's drifted copy was never read.",

    "validation": {
        "command": "python -c \"import json;json.load(open('" + REL + "/SPEC.json'))\"",
        "task_cards_hash_rule":
            "sha256 over json.dumps(spec['frozen_cards'], sort_keys=True, "
            "separators=(',',':')).encode('utf-8') - the cycle-1 P35 rule, unchanged",
        "card_hash_rule":
            "each frozen_cards[i].card_sha256 = sha256 over json.dumps(<the SPEC_V2 "
            "k0_matched[element_id] object>, sort_keys=True, separators=(',',':'))"
            ".encode('utf-8'); recomputable by any third party from SPEC_V2.json alone",
        "reproduce": f"python {REL}/VERIFY_REPAIR.py  then  python {REL}/BUILD_FREEZE.py",
    },
}

# ------------------------------------------------------------------ the append payload
def rec_freeze():
    return {
        "schema": "player_program_arm_registry/1",
        "kind": "preregistration_freeze",
        "experiment_id": "stage3_score_s35_task_card_freeze/1",
        "registered_at": PROPOSED_TS,
        "registered_before_execution": True,
        "authorises_execution": True,
        "node": "S35_FREEZE_TASK_CARDS",
        "decision": "S34_ADJUDICATION_VIA_S33R_REPAIR (4 Severity A + 8 Severity B closed; "
                    "4 Severity C recovered and dispositioned)",
        "spec_path": f"{REL}/SPEC.json",
        "task_cards_sha256": TASK_CARDS_SHA,
        "arm_blocks_sha256": ARM_BLOCKS_SHA,
        "cards_frozen": len(frozen_cards),
        "arms_frozen": len(frozen_arm_blocks),
        "fitted_elements": len(frozen_cards),
        "families": spec2["counts"]["families_primary_partition"],
        "families_maximal_disputed": spec2["counts"]["families_maximal_disputed_partition"],
        "program_alpha_governing": 0.40,
        "program_alpha_disclosed": 0.50,
        "s33r_spec_v2_sha256": SPEC_V2_SHA,
        "s33_draft_spec_sha256":
            ver["checks"]["V3_validator_over_frozen_S33"]["s33_spec_sha256"],
        "s30_target_contract_sha256": TC_MD_SHA,
        "note": "IMPLEMENTATION ONLY. authorises_execution=true means S36 may implement against "
                "these exact bytes. It does NOT authorise fitting (requires a passed S37 "
                "implementation audit) and it NEVER authorises adoption (S42 USER gate). "
                "Verified before freezing by S35's own re-run of every repair measurement: "
                f"{REL}/VERIFICATION.json sha256 {VERIFICATION_SHA}, 11/11 checks PASS.",
        "provenance": {
            "proposed_by": "S35_FREEZE_TASK_CARDS (coordinator-role node, score lane, cycle 2)",
            "registered_at_is_proposed": "the coordinator may replace registered_at with the "
                                         "actual append time; every other field is final as "
                                         "proposed",
            "registry_pre_append_baseline_sha256": REG_SHA,
            "registry_pre_append_records": reg_baseline["n_records"],
        },
    }


def rec_arm(block):
    aid = block["arm_id"]
    a = [x for x in spec2["arms"] if x["arm_id"] == aid][0]
    return {
        "schema": "player_program_arm_registry/1",
        "kind": "arm",
        "experiment_id": f"stage3_score_cycle2__{aid}",
        "arm_id": aid,
        "applies_to": aid,
        "registered_at": PROPOSED_TS,
        "registered_before_execution": True,
        "authorises_execution": True,
        "status": "FROZEN_IMPLEMENTATION_READY",
        "node": "S35_FREEZE_TASK_CARDS",
        "spec_path": f"{REL}/SPEC.json",
        "extra": {
            "family_primary": block["family_primary"],
            "elements": block["elements"],
            "n_elements": block["n_elements"],
            "arm_block_sha256": block["arm_block_sha256"],
            "element_card_sha256": {c["element_id"]: c["card_sha256"]
                                    for c in frozen_cards if c["arm_id"] == aid},
            "card_source": {
                "artifact": "experiments/player_program/stage3_score/"
                            "S33R_PREREGISTRATION_REPAIR/SPEC_V2.json",
                "artifact_sha256": SPEC_V2_SHA,
                "arm_pointer": block["block_source"]["json_pointer"],
                "element_pointers": [f"/k0_matched/{e}" for e in block["elements"]],
            },
            "formula": a["formula"],
            "kill_conditions_frozen": [k.get("kill") for k in a.get("kill_conditions", [])],
            "measured_coverage": a.get("measured_coverage"),
            "downstream_obligations_touching_this_arm": sorted(
                k for k, v in downstream_obligations.items()
                if aid in json.dumps(v)),
        },
        "authorisation_scope": "IMPLEMENTATION at S36 against these exact card hashes. NOT "
                               "fitting (needs a passed S37 audit). NEVER adoption (S42 USER "
                               "gate).",
        "provenance": {
            "proposed_by": "S35_FREEZE_TASK_CARDS",
            "registered_at_is_proposed": "the coordinator may replace registered_at with the "
                                         "actual append time; every other field is final as "
                                         "proposed",
        },
    }


w = spec2["withdrawals"][0]
rec_withdrawal = {
    "schema": "player_program_arm_registry/1",
    "kind": "withdrawal",
    "experiment_id": "stage3_score_cycle2__SC07_REF_CREW_TOTALS__withdrawn",
    "applies_to": w["arm_id"],
    "arm_id": w["arm_id"],
    "registered_at": PROPOSED_TS,
    "registered_before_execution": True,
    "authorises_execution": False,
    "ruling": "WITHDRAWN at S33 and frozen withdrawn at S35. Not registrable this cycle.",
    "basis": "the S32 registration was conditional on two data-admissibility preconditions. "
             "Precondition A (historical crew identity) PASSES on data/officials_master.csv. "
             "Precondition B (pregame assignment provenance) FAILS decisively: the only "
             "witnessed capture stream, data/ref_assignments/assignments_log.csv, holds 69 rows "
             "covering 8 games captured 2026-07-30..2026-08-01 and cannot cover 2021-2026; the "
             "as-worked officials records are published postgame and are exactly the P2B "
             "failure shape for a prediction-side join.",
    "resurrection_bar": "a future-cycle registration requires the witnessed pregame assignment "
                        "stream that began 2026-07-30 to have accumulated real T0 provenance "
                        "across the evaluation window, AND (because the upcoming game's crew is "
                        "not in the closed schedule-identity column set) a fresh adjudicated "
                        "identity-set extension. New registry append required either way.",
    "denominator_consequence": "FAM_S2_REFEREE is removed from the family table with the arm, "
                               "shrinking the program-alpha bound rather than inflating it.",
    "node": "S35_FREEZE_TASK_CARDS",
    "spec_path": f"{REL}/SPEC.json",
    "provenance": {
        "proposed_by": "S35_FREEZE_TASK_CARDS",
        "registered_at_is_proposed": "the coordinator may replace registered_at with the actual "
                                     "append time; every other field is final as proposed",
    },
}

rec_policy = {
    "schema": "player_program_arm_registry/1",
    "kind": "policy",
    "experiment_id": "stage3_score_cycle2__s34_severity_c_downstream_obligations/1",
    "policy_id": "s34_severity_c_downstream_obligations/1",
    "applies_to": "every downstream node of the cycle-2 score lane (S36 implementation, S37 "
                  "audit, S38 sealed run, S39 verification, S40 adjudication) and every "
                  "citation of a cycle-2 score result",
    "registered_at": PROPOSED_TS,
    "registered_before_execution": True,
    "authorises_execution": False,
    "finding_that_motivates_it": "S34's four Severity C notes existed nowhere in the repository "
                                 "at S33R time (S34 wrote no artifact; the coordinator ledger "
                                 "compressed them to a bare count). They were recovered in "
                                 f"S34_SEVERITY_C_RECOVERED.md (sha256 {CNOTES_SHA}). Three of "
                                 "the four impose obligations on downstream nodes rather than "
                                 "card edits, and an obligation that lives only in a report is "
                                 "an obligation that gets lost.",
    "policy": {
        "C1_program_alpha_disclosure": "0.40 GOVERNING (8 primary families x 0.05, the "
                                       "intersection rule), 0.50 DISCLOSED (10 maximal-partition "
                                       "families x 0.05). Both are stated; 0.40 governs. No "
                                       "program-wide FWER claim is made.",
        "C2_sc06_era_kill_power_statement": POWER_STATEMENT,
        "C3_sc11_e2_receipt_label": "SC11_LEAGUE_TOTAL_DRIFT::E1_GAME_TOTAL's cross-estimand "
                                    "|Delta-MAE(E2)| receipt is labelled "
                                    "NON_CITABLE_INTEGRITY_DIAGNOSTIC. It sits in no family, "
                                    "belongs to no registration, may never be quoted as a "
                                    "result, and may be used only to fire or not fire SC11's "
                                    "card-pinned integrity kill at 0.10 MAE points.",
        "C4_s36_prebuild_game_id_digest": "S36 must emit and pin a pre-build digest of the "
                                          "1,491-cluster game_id set before any design matrix "
                                          "is constructed, converting the invariants.rows "
                                          "deferral on all 17 records into a receipted "
                                          "invariant before any fit runs.",
        "ROOT_PATH_RULE": "every cycle-2 score node reads data/masters/master_team.parquet from "
                          "the PROGRAM WORKTREE and verifies sha256 " + MASTER_TEAM_SHA
                          + " before building anything. The live data-worktree copy "
                            "legitimately grows with the season and is INADMISSIBLE; measuring "
                            "it is a defect of the same class that previously produced a "
                            "1,508-cluster universe and a false 'artifacts missing' conclusion.",
    },
    "reporting_rule": "the C2 power statement prints adjacent to any verdict SC06's era kill "
                      "produces, and the C3 label travels with the number wherever it is "
                      "emitted, copied or cited.",
    "node": "S35_FREEZE_TASK_CARDS",
    "spec_path": f"{REL}/SPEC.json",
    "provenance": {
        "proposed_by": "S35_FREEZE_TASK_CARDS",
        "registered_at_is_proposed": "the coordinator may replace registered_at with the actual "
                                     "append time; every other field is final as proposed",
        "recovered_c_notes_artifact":
            "experiments/player_program/stage3_score/S33R_PREREGISTRATION_REPAIR/"
            "S34_SEVERITY_C_RECOVERED.md",
        "recovered_c_notes_sha256": CNOTES_SHA,
    },
}

payload = [rec_freeze()] + [rec_arm(b) for b in frozen_arm_blocks] + \
    [rec_withdrawal, rec_policy]

spec["registry_append"]["records_to_append"] = [
    {"index": i, "kind": r["kind"], "experiment_id": r["experiment_id"],
     "authorises_execution": r["authorises_execution"]}
    for i, r in enumerate(payload)]
spec["registry_append"]["n_records"] = len(payload)

payload_bytes = b"".join(
    (json.dumps(r, ensure_ascii=False) + "\n").encode("utf-8") for r in payload)
with open(os.path.join(HERE, "REGISTRY_APPEND_PAYLOAD.jsonl"), "wb") as f:
    f.write(payload_bytes)

spec["registry_append"]["payload_sha256"] = hashlib.sha256(payload_bytes).hexdigest()
spec["registry_append"]["payload_bytes"] = len(payload_bytes)
spec["registry_append"]["post_append_expected"] = {
    "n_records": reg_baseline["n_records"] + len(payload),
    "file_bytes": reg_baseline["file_bytes_pre_append"] + len(payload_bytes),
    "file_sha256": hashlib.sha256(registry_raw + payload_bytes).hexdigest(),
    "note": "the coordinator can check this exact hash after appending; a match proves both "
            "that the payload went in verbatim AND that not one byte of the 51 existing "
            "records changed.",
}

with open(os.path.join(HERE, "SPEC.json"), "w", encoding="utf-8") as f:
    json.dump(spec, f, indent=1, ensure_ascii=False)

# --------------------------------------------------- the pre-append baseline verification
baseline = {
    "schema": "stage3_score_s35_registry_baseline_verification/1",
    "node": "S35_FREEZE_TASK_CARDS",
    "purpose": "Prove that every existing record of the frozen, append-only registry was READ "
               "and hashed BEFORE any append, so the coordinator can prove byte-identity "
               "afterwards. This node performed NO append.",
    "policy": "experiments/player_program/arm_registry.jsonl is a FROZEN path under "
              "GRAPH_POLICY section 3. Existing records may NEVER be edited, reordered or "
              "rewritten. Appending is permitted ONLY after a passed preregistration gate. The "
              "coordinator is the single writer.",
    "path": "experiments/player_program/arm_registry.jsonl",
    "absolute_path": REGISTRY,
    "read_at_node": "S35_FREEZE_TASK_CARDS",
    "pre_append": {
        "file_sha256": REG_SHA,
        "file_bytes": reg_baseline["file_bytes_pre_append"],
        "n_records": reg_baseline["n_records"],
        "all_records_parse_as_json": reg_baseline["all_parse"],
        "file_ends_with_newline": reg_baseline["file_ends_with_newline"],
        "eol_mix": reg_baseline["eol_mix"],
    },
    "per_record": reg_baseline["records"],
    "observed_anomaly_reported_not_touched": {
        "record_index": 50,
        "what": "the last existing record carries no 'schema', 'kind' or 'experiment_id' key. "
                "It is the P37_IMPLEMENTATION_AUDIT A24 amendment DRAFTER REGISTER file "
                "(A24_AMENDMENT_PAYLOAD.json) appended whole, rather than the single amendment "
                "payload nested inside its own registry_append.payloads block.",
        "why_it_matters": "it is self-describing as 'DRAFT ONLY... must never be appended', so "
                          "the appended line contradicts its own text, and it breaks the "
                          "(schema, kind, experiment_id) shape every other record holds. Any "
                          "tool that groups the registry by kind will silently miss it.",
        "what_this_node_did": "NOTHING. The record is frozen. It is reported here so the "
                              "coordinator can decide whether to append a correcting erratum "
                              "record. It is NOT edited, NOT reordered and NOT rewritten, and "
                              "the S35 append is placed strictly after it.",
    },
    "append_to_be_performed_by_the_coordinator": {
        "payload_file": f"{REL}/REGISTRY_APPEND_PAYLOAD.jsonl",
        "payload_sha256": spec["registry_append"]["payload_sha256"],
        "payload_bytes": spec["registry_append"]["payload_bytes"],
        "n_records": len(payload),
        "method": "byte-concatenate the payload file to the END of arm_registry.jsonl. Do not "
                  "re-serialise, re-indent, re-order or re-encode either side. Do not normalise "
                  "line endings of the existing 51 records.",
        "post_append_expected": spec["registry_append"]["post_append_expected"],
    },
    "byte_identity_proof_procedure": [
        "1. BEFORE: this file already carries sha256 of each of the 51 existing record lines "
        "(per_record[].sha256_of_line_without_eol) plus the whole-file sha256 " + REG_SHA + ".",
        "2. APPEND: concatenate REGISTRY_APPEND_PAYLOAD.jsonl verbatim to the end.",
        "3. AFTER: re-split the file on newline; re-hash lines 0..50 individually; every digest "
        "must equal the corresponding per_record entry, and every eol must be unchanged.",
        "4. AFTER: confirm the whole file's sha256 equals post_append_expected.file_sha256. A "
        "match proves the payload went in verbatim AND no existing byte moved.",
        "5. ON ANY DIVERGENCE: revert the append and report. Do not repair in place.",
    ],
    "this_node_performed_no_append": True,
}
with open(os.path.join(HERE, "REGISTRY_BASELINE_VERIFICATION.json"), "w", encoding="utf-8") as f:
    json.dump(baseline, f, indent=1, ensure_ascii=False)

# re-hash the emitted SPEC for the console
print(json.dumps({
    "cards_frozen": len(frozen_cards),
    "arm_blocks_frozen": len(frozen_arm_blocks),
    "task_cards_sha256": TASK_CARDS_SHA,
    "arm_blocks_sha256": ARM_BLOCKS_SHA,
    "spec_v2_sha256": SPEC_V2_SHA,
    "registry_pre_append_sha256": REG_SHA,
    "registry_pre_append_records": reg_baseline["n_records"],
    "payload_records": len(payload),
    "payload_bytes": len(payload_bytes),
    "payload_sha256": spec["registry_append"]["payload_sha256"],
    "post_append_expected_sha256": spec["registry_append"]["post_append_expected"]["file_sha256"],
    "SPEC_json_sha256": sha256_file(os.path.join(HERE, "SPEC.json")),
}, indent=1))
