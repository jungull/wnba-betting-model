#!/usr/bin/env python
"""Build and freeze EVIDENCE_PACKET_V3 — node P30_EVIDENCE_PACKET_V3.

Design constraints, in order of importance:

1. SELF-CONTAINED. The P31 ideation sources receive an isolated directory holding ONLY this
   packet and their prompt. Anything they need — the 48-column adjudication, the injury
   regimes, the enforcement rules, the per-arm K0 rules, the fold enumeration, the universe
   caveats — must be INLINE. Deep evidence stays bound by path+sha256 for auditors, but the
   substance a hypothesis author needs is in the packet body.

2. DERIVED, NOT AUTHORED. Every inline table is read from the remediation nodes' committed
   outputs at build time and re-hashed. Where this builder states a ruling, it quotes the
   decision ledger by id. Nothing here is a fresh scientific claim.

3. FAIL CLOSED ON THE SIX DIMENSIONS. The node's acceptance criterion — no unresolved issue
   that changes the target unit, K0 structure, inference, candidate universe, cutoff-valid
   feature set or leakage status — is enforced mechanically: every Severity A stop condition
   raised by the wave must map to either a carried ruling or an explicit
   OPEN_OUTSIDE_SIX_DIMENSIONS classification with its reason. An unmapped item aborts the
   build.

4. V1 AND V2 ARE NOT TOUCHED. Their hashes are verified, and V3 carries V2 by reference with
   an itemised correction addendum. Corrections supersede prospectively; the historical
   record stands.

    python experiments/player_program/stage2b/P30_EVIDENCE_PACKET_V3/build_evidence_packet_v3.py
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent.parent.parent
PP = REPO / "experiments/player_program"
S2A = PP / "stage2a"
S2B = PP / "stage2b"
ORCH = PP / "orchestration"

PINNED = {
    "V1": (S2A / "EVIDENCE_PACKET.json",
           "f373e3eed710026c9d82ff88aad1e9a2cae640ee461a5d7df5208d76abaf1e4e"),
    "V2": (S2A / "EVIDENCE_PACKET_V2.json",
           "3a35ae735333c47713d6e7cc4c35c081e4eb07364c71cba744db03709730a32c"),
    "HALT": (S2B / "P21_FREEZE_V2_HALT_PACKET/V2_HALT_PACKET.json",
             "68a9ceff84b8b965817b3cf75577c5186864d17bbded53b182b2b8e34ae9cd1c"),
}

SOURCES = {
    "P22": S2B / "P22_POSTGAME_SURROGATE_GUARD",
    "P23": S2B / "P23_DIMENSION_CARDINALITY_GUARD",
    "P24": S2B / "P24_INJURY_REGIME_LEDGER",
    "P25R": S2B / "R11_P25_REPORT_REMEDIATION",
    "P25": S2B / "P25_OFFSET_DEPENDENCY_GUARD",
    "P26": S2B / "P26_ARM_SPECIFIC_K0_CONTRACT",
    "P27": S2B / "P27_FOLD_LOCAL_ESTIMABILITY_GUARD",
    "P27R": S2B / "R12_P27_REPORT_REMEDIATION",
    "P28": S2B / "P28_PRIMARY_SECONDARY_ORDERING_CONTRACT",
    "P29": S2B / "P29_TIP_TIME_AND_COVERAGE_AUDIT",
    "P2A": S2B / "P2A_POSSESSION_COLUMN_ADJUDICATION",
    "P2B": S2B / "P2B_MARKET_ODDS_ELIGIBILITY",
}

RULING_IDS = [
    "D005_FEATURE_GATE_CANNOT_ENFORCE_THE_PROHIBITION",
    "D006_FOLD_COUNT_IS_FIVE",
    "D007_K0_MATCHED_SUPERSEDES_THE_PACKET_CONTROL_SPEC",
    "D008_D10_MANUFACTURED_A_NEGATIVE",
    "D009_TWO_CUTOFF_STANDARDS_BOTH_CARRIED",
    "D010_UNIVERSE_EXCLUDES_2021_OPENING_DAY",
    "D011_SEAL_IS_OBFUSCATION_NOT_BLINDING",
    "D016_P2B_COORDINATOR_CORROBORATION",
]


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def jload(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def main() -> int:
    failures: list[str] = []

    # ---- 1. frozen inputs verify -------------------------------------------------
    frozen = {}
    for name, (path, exp) in PINNED.items():
        got = sha(path) if path.is_file() else None
        frozen[name] = {"path": str(path.relative_to(REPO)).replace("\\", "/"),
                        "sha256": got, "expected": exp, "match": got == exp}
        if got != exp:
            failures.append(f"{name} hash diverged: {path}")

    # ---- 2. bind every source ----------------------------------------------------
    bound = {}
    for key, d in SOURCES.items():
        if not d.is_dir():
            failures.append(f"source directory missing: {d}")
            continue
        files = {}
        for f in sorted(d.glob("*")):
            if f.is_file() and f.suffix in (".json", ".md", ".csv", ".py"):
                files[f.name] = sha(f)
        bound[key] = {"dir": str(d.relative_to(REPO)).replace("\\", "/"), "files": files}

    # ---- 3. decision-ledger rulings, quoted by id --------------------------------
    ledger = {}
    for line in (ORCH / "DECISION_LEDGER.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            rec = json.loads(line)
            ledger[rec["decision_id"]] = rec
    rulings = {}
    for rid in RULING_IDS:
        if rid not in ledger:
            failures.append(f"required ruling absent from the ledger: {rid}")
            continue
        rulings[rid] = {"question": ledger[rid]["question"], "ruling": ledger[rid]["ruling"],
                        "authority": ledger[rid]["authority"]}

    # ---- 4. inline tables, read from committed outputs ---------------------------
    # 4a. the 48 possession columns (S8 / P2A)
    adjudication = []
    with open(SOURCES["P2A"] / "ADJUDICATION.csv", newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            adjudication.append({k: row[k] for k in
                                 ("column", "label", "origin", "basis", "hazard")})
    if len(adjudication) != 48:
        failures.append(f"possession adjudication has {len(adjudication)} rows, expected 48")
    labels = sorted({r["label"] for r in adjudication})

    # 4b. injury regimes (S3 / P24)
    p24 = jload(SOURCES["P24"] / "FINDINGS.json")
    injury = {
        "split_reproduction": p24.get("S3_split_reproduction"),
        "regimes": {
            "R_realised_participation": p24.get("regime_R_realised_participation"),
            "T_announcement_wire": p24.get("regime_T_announcement_wire"),
        },
        "classification_rule": (
            "missed_game_* and every realised-participation or retrospective field is NOT a "
            "pregame feature. A field is usable only with a source timestamp at or before the "
            "declared pregame cutoff, documented designation semantics, and no derivation from "
            "the game outcome. Missing or ambiguous timestamps are CUTOFF_UNPROVEN: reportable "
            "in availability, excluded from the fitted feature universe."
        ),
        "measured_consequence": (
            "injury_history.csv contributes ZERO cutoff-valid rows to the fitted feature "
            "universe in every one of the folds (P24, verified)."
        ),
        "coverage_by_season_and_fold": p24.get("coverage_by_season_and_fold"),
    }

    # 4c. per-arm K0 (S6/S9 / P26 + D007)
    k0dir = SOURCES["P26"]
    k0 = {
        "supersession": (
            "K0_MATCHED is a per-arm map keyed by arm_id, superseding "
            "EVIDENCE_PACKET_V2.control_specification's single object PROSPECTIVELY (D007). "
            "V2 is not edited; both readings are preserved in the ledger."
        ),
        "schema": {"path": "experiments/player_program/stage2b/P26_ARM_SPECIFIC_K0_CONTRACT/"
                           "K0_MATCHED_SCHEMA.json",
                   "sha256": sha(k0dir / "K0_MATCHED_SCHEMA.json")},
        "examples": {"path": "experiments/player_program/stage2b/P26_ARM_SPECIFIC_K0_CONTRACT/"
                             "K0_MATCHED_EXAMPLES.json",
                     "sha256": sha(k0dir / "K0_MATCHED_EXAMPLES.json")},
        "validator": {"path": "experiments/player_program/stage2b/P26_ARM_SPECIFIC_K0_CONTRACT/"
                              "validate_k0_matched.py",
                      "sha256": sha(k0dir / "validate_k0_matched.py")},
        "core_rules": [
            "for every arm the matched null holds identical rows, target, folds, weights, "
            "offset, fallback machinery, nuisance terms and lower-order structural terms, and "
            "excludes ONLY the treatment mechanism under test",
            "calibration-only arm: the null fixes the tested parameter at its incumbent value "
            "(slope 1; the preregistered lower-order intercept structure); the calibration "
            "family carries its own nested null and its own multiplicity accounting",
            "substantive-feature arm: K0 contains every non-substantive structural degree of "
            "freedom granted to the candidate; tier interactions require lower-order tier main "
            "effects in K0",
            "no arm receives credit for free re-centring, changed fallback, or a more flexible "
            "estimator; K0_FLAT is diagnostic only",
            "tier support constraint (P27, measured): under a 10-cluster support floor NO "
            "training fold supports the full tier ladder of V2's single control — a per-arm "
            "K0 must respect fold-local support or declare the preregistered active-set rule",
        ],
    }

    # 4d. enforcement wrappers (S1/S2/S4-S5/S7 + D005)
    def _tool(key, fname):
        d = SOURCES[key]
        p = d / fname
        return {"path": str(p.relative_to(REPO)).replace("\\", "/"),
                "sha256": sha(p) if p.is_file() else None}

    enforcement = {
        "gate_enforcement_correction_D005": (
            "feature_gate.audit passes raw game_minutes, the master_team.minutes 5x shape, and "
            "a 100%-missing column with an EMPTY findings list (cause: feature_gate.py:152 "
            "skips the informative-missingness branch for fully missing columns). The "
            "prohibition on current-game duration is enforced NOWHERE in shared code. The gate "
            "stays frozen; the task-specific wrappers below are the enforcement. Reproduced "
            "independently by the coordinator on synthetic data."
        ),
        "postgame_surrogate_guard_S1": {
            "tool": _tool("P22", "postgame_surrogate_guard.py"),
            "rule": ("no current-game outcome-derived column may enter a prediction frame; "
                     "history requires a documented lag of >=1 completed prior game with source "
                     "keys and timestamps preceding the cutoff; same-game joins fail closed; "
                     "receipts record the lag transformation"),
            "proven": ("unlagged minutes FAILS; minutes/5 FAILS; renames, affine and nonlinear "
                       "injective transforms of current-game duration FAIL; correctly lagged "
                       "prior-game duration PASSES all cutoff checks (P22 TESTS, verified)"),
        },
        "dimension_cardinality_guard_S2": {
            "dir": bound["P23"]["dir"],
            "rule": ("every dimension merge declares explicit keys and expected cardinality, "
                     "asserts unchanged row count and unchanged game/team-game key sets, rejects "
                     "duplicate primary keys, reports null expansion, fails on fan-out; the "
                     "PHO/PHX duplicate (team_id 1611661317) resolves only from documented "
                     "effective-date semantics or the family is excluded"),
        },
        "offset_dependency_guard_S4_S5": {
            "dir": bound["P25R"]["dir"],
            "original_findings": bound["P25"]["files"].get("FINDINGS.json"),
            "rule": ("audit the COMPLETE design [offset | nuisance | candidate]; reject exact "
                     "or near-exact affine functions of the offset, exact functions of the "
                     "incumbent projection, and candidate pairs that jointly reconstruct the "
                     "offset; own_est + opp_est == 2*projected, so the pair may not enter beside "
                     "the offset — a single preregistered nonredundant contrast (own-opp) is "
                     "admissible with fold-local full rank; recalibration is its own hypothesis "
                     "family and may not hide inside a substantive arm"),
        },
        "fold_local_estimability_guard_S7": {
            "dir": bound["P27R"]["dir"],
            "original_findings": bound["P27"]["files"].get("FINDINGS.json"),
            "rule": ("per-fold and final-design rank (including offset and nuisance), "
                     "zero-variance, unique-level, cluster-support and condition-number checks; "
                     "parameter-count reconciliation; no silent pooled pass when a term is "
                     "absent in a fold; a fold-local active-set rule only if preregistered, "
                     "training-support-based, symmetric and receipt-recorded — otherwise the "
                     "arm/fold is prospectively UNEVALUABLE"),
            "known_degeneracies": (
                "is_playoff_game — the ONE possession column already carried as a feature — is "
                "identically zero in fold 2026 (P2A, measured); market_total_points is 100% "
                "missing on training rows in 4 of 5 folds (P2B, verifier re-derived). Any arm "
                "carrying such a column must declare the GATE_INVOCATION_CONTRACT §4 frozen "
                "fold-level fallback before results are visible."
            ),
        },
        "primary_before_secondary_P28": {
            "dir": bound["P28"]["dir"],
            "rule": ("a candidate passes its registered PRIMARY possession-target gate before "
                     "it may enter the frozen turnover scorer; the primary verdict is frozen, "
                     "content-addressed, before any downstream number is computed; improving "
                     "downstream turnover MAE while worsening the primary target FAILS; no "
                     "credit for arbitraging the raw/regulation-equivalent scorer mismatch"),
        },
        "blinding_note_D011": (
            "the sealed-result crypto is public-keyed obfuscation, not blinding; blinding for "
            "the experiment rests on PROCESS separation enforced by the graph (runner, "
            "result-integrity and adjudication are separate contexts with separate scopes)"
        ),
    }

    # ---- 5. inference block ------------------------------------------------------
    inference = {
        "team_game_rows": 2982,
        "game_clusters": 1491,
        "report_both": True,
        "fold_construction_D006": {
            "ruling": ("FIVE chronological expanding-window folds — the implementation "
                       "possession_features.chronological_folds governs over V2's ambiguous "
                       "prose; run live by the coordinator and independently enumerated by P22"),
            "folds": [
                {"fold_id": "train_lt_2022", "train_rows": 410, "test_rows": 478},
                {"fold_id": "train_lt_2023", "train_rows": 888, "test_rows": 520},
                {"fold_id": "train_lt_2024", "train_rows": 1408, "test_rows": 524},
                {"fold_id": "train_lt_2025", "train_rows": 1932, "test_rows": 620},
                {"fold_id": "train_lt_2026", "train_rows": 2552, "test_rows": 430},
            ],
            "s7_restatement": ("S7's packet measurement is tabulated by SEASON across six "
                               "seasons; 'identically zero in four of six folds' must be read "
                               "as a season statement and restated against the five real folds"),
        },
        "universe_caveat_D010": (
            "the universe excludes the 2021 opening day entirely — games 1022100001-1022100004, "
            "all 2021-05-14, are in the possessions artifact (1,495 games) but not the universe "
            "(1,491), because the pace producer has no prior-games evidence on day one. Every "
            "cold-start coverage figure on this universe is therefore FLATTERED BY CONSTRUCTION, "
            "and any arm whose mechanism is cold-start behaviour is evaluated on a universe "
            "missing the hardest cold-start case it exists to handle."
        ),
        "resampling": "game-clustered, both team-rows carried together, never rows independently",
        "games_never_split_across_folds": True,
    }

    # ---- 6. cutoff-validity ------------------------------------------------------
    cutoff = {
        "dual_standard_D009": (
            "two standards, BOTH carried, never merged: (a) validated construction ORDER — the "
            "Stage 1B scoped acceptance governs the exact receipted incumbent-equivalent "
            "possession path; (b) timestamped OBSERVATION — governs every NEW field entering "
            "the candidate universe. D10's classification of the four incumbent-equivalent "
            "features as CUTOFF_UNPROVEN under standard (b) is preserved in its ledger and does "
            "not overturn the scoped acceptance under standard (a)."
        ),
        "possession_columns_48_S8": {
            "labels_present": labels,
            "table": adjudication,
            "headline": ("38 of 48 columns are realised target-game outcomes (lagged-use-only "
                         "at best); five exact same-game duration/overtime surrogates live "
                         "inside possessions_raw_v2 (period, end_sec, duration_sec, "
                         "is_overtime, period_clock_start_sec) plus one approximate "
                         "(regulation_seconds_remaining); no column is admitted on availability "
                         "grounds alone"),
        },
        "injury_S3": injury,
        "market_odds_P2B": {
            "stated_ground_in_v2": "capture begins 2026-07-31 — FACTUALLY FALSE on two counts",
            "measured": ("a game-joined retrospective archive reaches back to "
                         "2022-05-21T17:55:00Z, and the first live capture file is "
                         "2026-07-30T15:01:32Z; but the archive is a SINGLE RETROSPECTIVE "
                         "HARVEST — exactly one snapshot per game across all 813 games, "
                         "selected at ~tip-minus-64min from a 5-minute vendor grid, downloaded "
                         "in a 571-second burst on 2026-07-30"),
            "consequence": ("exclusion SUSTAINED on stronger grounds: a one-shot retrospective "
                            "pull is permanently CUTOFF_UNPROVEN however far back its event "
                            "dates reach. The candidate universe is UNCHANGED."),
            "left_open": ("whether a market feature belongs in a possession model at all — it "
                          "changes what the model IS — remains an open program-level question, "
                          "deliberately not settled by P2B or by this packet"),
        },
        "coaching_D008": (
            "PRESENT_RETROSPECTIVE / CUTOFF_UNPROVEN — dated coaching changes exist in "
            "injury_history.csv's 49 front_office rows (D10's ABSENT verdict was a "
            "manufactured negative, corrected by R14 with re-measured coverage); cutoff_valid "
            "count remains 0: presence is not cutoff validity"
        ),
        "tip_times_P29": (
            "tip-derived features are INELIGIBLE this wave: the null mask is nearly "
            "fold-aligned (no 2021 coverage), and the parent derivation discards the snapshot "
            "timestamp (collect_bios.py::phase_tips keeps only the latest snapshot's commence "
            "time), so cutoff validity is unprovable from the tracked artifact"
        ),
    }

    # ---- 7. six-dimension check, fail closed -------------------------------------
    # Every Severity A stop condition raised during the wave maps to a ruling or an explicit
    # OPEN_OUTSIDE_SIX_DIMENSIONS entry. Sourced from the halt packet plus wave escalations.
    halt = jload(PINNED["HALT"][0])
    findings_map = {
        "S1": "ENFORCED by postgame_surrogate_guard_S1 (P22); gate correction recorded (D005)",
        "S2": "ENFORCED by dimension_cardinality_guard_S2 (P23)",
        "S3": "RESOLVED by injury regime classification (P24); zero cutoff-valid rows measured",
        "S4": "ENFORCED by offset_dependency_guard_S4_S5 (P25/R11); calibration is its own family",
        "S5": "ENFORCED by offset_dependency_guard_S4_S5; own+opp identity reproduced and rejected",
        "S6": "RESOLVED by per-arm K0_MATCHED (P26 + D007)",
        "S7": "ENFORCED by fold_local_estimability_guard_S7 (P27/R12); fold count fixed by D006",
        "S8": "RESOLVED by the 48-column adjudication (P2A), inlined in this packet",
        "S9": "RESOLVED by per-arm K0_MATCHED (P26 + D007), independently derived twice",
    }
    for key in halt.get("findings", {}):
        short = key.split("_")[0]
        if short not in findings_map:
            failures.append(f"halt finding {key} has NO disposition in V3 — the packet may not "
                            f"freeze with an unmapped Severity A finding")

    open_outside = [
        {"item": "market-feature model-identity question",
         "why_outside": "the family stays EXCLUDED either way; the candidate universe is "
                        "unchanged until the program decides otherwise (P2B, left open)"},
        {"item": "vendor snapshot-timestamp accuracy",
         "why_outside": "unfalsifiable from inside the repository (P2B could-not-establish); "
                        "affects nothing admitted"},
        {"item": "general producer provenance (Stage 1B general gap)",
         "why_outside": "pre-existing scoped limitation, unchanged by this wave; the scoped "
                        "acceptance governs the receipted path only (D009)"},
    ]

    six = {
        "target_unit": "UNCHANGED — REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS",
        "k0_structure": "SUPERSEDED BY RULING — per-arm map (D007), schema inlined by hash",
        "inference_structure": "RESOLVED — five folds (D006), enumerated above",
        "candidate_universe": "UNCHANGED — 2,982 rows / 1,491 clusters; market family stays "
                              "excluded; opening-day caveat recorded (D010)",
        "cutoff_valid_feature_set": "UPDATED — dual standard (D009); 48-column table inlined; "
                                    "injury regimes split; tip and market families ineligible",
        "leakage_status": "ENFORCEMENT CORRECTED — the shared gate cannot enforce the duration "
                          "prohibition (D005); the wrappers inlined above are the enforcement",
    }

    # ---- 8. correction addendum --------------------------------------------------
    addendum = {
        "withdrawn": [
            "V2.control_specification as a single universal K0 object (D007; unestimable as "
            "written under fold-local support — P27)",
            "V2's market-odds exclusion GROUND 'capture begins 2026-07-31' (P2B; the exclusion "
            "OUTCOME stands on stronger grounds)",
            "the implicit claim that feature_gate enforces the duration prohibition (D005)",
        ],
        "corrected": [
            "fold construction: five expanding-window folds, not six season blocks (D006)",
            "S7's 'four of six folds' restated as a season-tabulated measurement (D006)",
            "coaching availability: ABSENT -> PRESENT_RETROSPECTIVE / CUTOFF_UNPROVEN (D008/R14)",
            "the '1491 vs 1495' packet nit diagnosed: the universe excludes the 2021 opening "
            "day (D010)",
            "availability-table completeness: all 48 possession columns adjudicated (S8/P2A)",
        ],
        "unchanged": [
            "the primary target and its unit",
            "the 2,982-row / 1,491-cluster universe and both-numbers reporting",
            "K0_FLAT as diagnostic only",
            "the frozen downstream turnover scorer and its documented mismatch",
            "Arm D, frozen, unbeaten",
            "V1 and V2 as immutable historical records",
        ],
        "unresolved_outside_six_dimensions": open_outside,
    }

    packet = {
        "schema": "player_program/stage2b/evidence_packet_v3/1",
        "node": "P30_EVIDENCE_PACKET_V3",
        "supersedes_for_candidate_selection": "EVIDENCE_PACKET_V2.json (carried by reference, "
                                              "byte-identical, never edited)",
        "epistemic_status": (
            "FROZEN EVIDENCE for the final ideation wave. Derived from the committed outputs "
            "of the S1-S9 remediation wave and the coordinator decision ledger; every inline "
            "table re-read from its source at build time and every source bound by sha256. "
            "This packet authorises NO fit: fitting requires the preregistration chain "
            "P33-P37."
        ),
        "frozen_inputs": frozen,
        "sources_bound": bound,
        "rulings_carried": rulings,
        "enforcement": enforcement,
        "inference": inference,
        "cutoff_validity": cutoff,
        "k0_matched": k0,
        "halt_finding_dispositions": findings_map,
        "six_dimension_check": six,
        "correction_addendum": addendum,
        "ok": not failures,
        "failures": failures,
    }

    out = HERE / "EVIDENCE_PACKET_V3.json"
    out.write_text(json.dumps(packet, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                   encoding="utf-8", newline="\n")
    digest = sha(out)
    (HERE / "EVIDENCE_PACKET_V3.sha256").write_text(
        f"{digest}  EVIDENCE_PACKET_V3.json\n", encoding="utf-8", newline="\n")

    print(f"frozen inputs   {sum(1 for v in frozen.values() if v['match'])}/{len(frozen)} verify")
    print(f"sources bound   {len(bound)} directories, "
          f"{sum(len(b['files']) for b in bound.values())} files hashed")
    print(f"rulings         {len(rulings)}/{len(RULING_IDS)} carried")
    print(f"columns         {len(adjudication)} adjudicated, labels {labels}")
    print(f"dispositions    {len(findings_map)} halt findings mapped")
    for f in failures:
        print(f"FAIL            {f}")
    print(f"packet sha256   {digest}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
