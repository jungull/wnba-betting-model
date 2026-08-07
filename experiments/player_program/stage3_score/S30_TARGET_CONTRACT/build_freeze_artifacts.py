#!/usr/bin/env python3
"""S30 freeze builder — deterministic, receipt-emitting.

From CYCLE2_TARGET_CONTRACT_DRAFT.md (v5, both reviewers FREEZE-READY) emits:
  1. CYCLE2_TARGET_CONTRACT.md              — FULL frozen edition (status header updated)
  2. CYCLE2_TARGET_CONTRACT_IDEATION_EDITION.md — the three §7 bullets replaced per the
     contract's own §7 specification (redaction notice / generic identifiability form /
     conditional cycle-1-nulls form)
  3. EDITION_DIFF_RECEIPT.json              — machine proof the editions differ ONLY in the
     named regions (line-region diff + sha256 of both editions)
  4. TARGET_CONTRACT.json                   — machine-readable contract summary with
     artifact hash pins

Deterministic: same input bytes -> same output bytes (no timestamps inside the editions;
the receipt carries the pins the freeze event will quote).
"""
import difflib
import hashlib
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
DRAFT = os.path.join(HERE, "CYCLE2_TARGET_CONTRACT_DRAFT.md")
FULL = os.path.join(HERE, "CYCLE2_TARGET_CONTRACT.md")
IDEATION = os.path.join(HERE, "CYCLE2_TARGET_CONTRACT_IDEATION_EDITION.md")
RECEIPT = os.path.join(HERE, "EDITION_DIFF_RECEIPT.json")
TC_JSON = os.path.join(HERE, "TARGET_CONTRACT.json")

FLOORS_ARTIFACTS = [
    "experiments/market_program/SCORE_BASELINES/score_baselines.json",
    "experiments/market_program/SCORE_BASELINES/score_baseline_rows.parquet",
]

DRAFT_STATUS = ("**Status: DRAFT v5 — post red-team rounds 1–3, under final confirmation. "
                 "Nothing herein\nauthorizes fitting until this contract is FROZEN, arms are "
                 "preregistered with frozen cards,\nand implementation audits pass.**")
FROZEN_STATUS = ("**Status: FROZEN (v5 bytes; both red-team reviewers FREEZE-READY, "
                  "2026-08-07). This contract\nbinds every downstream S-lane node. It does not "
                  "itself authorize fitting: that additionally\nrequires the S32B K0 schema "
                  "frozen, cards frozen through S33–S35, and the S37 audit pass.**")

# The three §7 replacement regions, keyed by their exact first line in the FULL edition.
DIRECTED_BULLET_START = "* **The user-directed families enter as DIRECTED CANDIDATES at synthesis (S32), not through"
IDENT_BULLET_START = "* **Identifiability acknowledgment (consistency finding C4):**"
NULLS_BULLET_START = "* Cycle-1 nulls bind: rest/schedule/home arms may not target *pace* mechanisms in the same"

DIRECTED_REPLACEMENT = [
    "* **[REDACTED IN THE IDEATION EDITION.]** A directed-candidate set exists and enters at",
    "  S32 with provenance labels; it is enumerated only in the FULL edition. This notice",
    "  names no mechanism, no family, no area.",
]
IDENT_REPLACEMENT = [
    "* **Identification constraint (generic form):** any candidate whose structure has a scale",
    "  or identification indeterminacy must register its identification constraint explicitly.",
]
NULLS_REPLACEMENT = [
    "* Cycle-1 nulls bind (conditional form): any candidate acting on rest, schedule or",
    "  home-court context may not target pace mechanisms in the cycle-1 forms (P42 §4.4 retry",
    "  bound); such context, if proposed, acts on scoring.",
]


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha256_file(path):
    with open(path, "rb") as f:
        return sha256_bytes(f.read())


def bullet_region(lines, start_marker):
    """Return (start, end) line indexes of the bullet beginning with start_marker,
    ending before the next line that starts with '* ' or '## '."""
    for i, ln in enumerate(lines):
        if ln.startswith(start_marker):
            j = i + 1
            while j < len(lines) and not (lines[j].startswith("* ") or lines[j].startswith("## ")):
                j += 1
            return i, j
    raise SystemExit(f"marker not found: {start_marker[:60]}")


def main():
    draft = open(DRAFT, encoding="utf-8").read()
    if DRAFT_STATUS not in draft:
        raise SystemExit("draft status header not found verbatim; refusing to freeze")
    full = draft.replace(DRAFT_STATUS, FROZEN_STATUS, 1)
    open(FULL, "w", encoding="utf-8", newline="\n").write(full)

    lines = full.split("\n")
    regions = {}
    for name, marker, repl in [
        ("directed_enumeration", DIRECTED_BULLET_START, DIRECTED_REPLACEMENT),
        ("identifiability", IDENT_BULLET_START, IDENT_REPLACEMENT),
        ("cycle1_nulls", NULLS_BULLET_START, NULLS_REPLACEMENT),
    ]:
        i, j = bullet_region(lines, marker)
        regions[name] = {"full_lines": [i, j], "replaced_line_count": j - i,
                          "replacement_line_count": len(repl)}
    # apply bottom-up so indexes stay valid
    ordered = sorted(regions.items(), key=lambda kv: kv[1]["full_lines"][0], reverse=True)
    ide_lines = list(lines)
    for name, meta in ordered:
        i, j = meta["full_lines"]
        repl = {"directed_enumeration": DIRECTED_REPLACEMENT,
                "identifiability": IDENT_REPLACEMENT,
                "cycle1_nulls": NULLS_REPLACEMENT}[name]
        ide_lines[i:j] = repl
    ideation = "\n".join(ide_lines)
    open(IDEATION, "w", encoding="utf-8", newline="\n").write(ideation)

    # machine diff receipt: prove the ONLY differing regions are the named ones + status ok
    diff_blocks = []
    sm = difflib.SequenceMatcher(a=lines, b=ide_lines, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag != "equal":
            diff_blocks.append({"op": tag, "full_lines": [i1, i2], "ideation_lines": [j1, j2]})
    # Adjacent named bullets can merge into one diff block; the proof obligation is
    # that every changed full-side line falls INSIDE the union of named regions.
    named_lines = set()
    for meta in regions.values():
        named_lines.update(range(meta["full_lines"][0], meta["full_lines"][1]))
    changed_lines = set()
    for b in diff_blocks:
        changed_lines.update(range(b["full_lines"][0], b["full_lines"][1]))
    only_named = changed_lines.issubset(named_lines) and len(diff_blocks) >= 1
    receipt = {
        "schema": "stage3_score/S30/edition_diff_receipt/1",
        "full_edition": {"path": os.path.relpath(FULL, ROOT).replace("\\", "/"),
                          "sha256": sha256_bytes(full.encode("utf-8"))},
        "ideation_edition": {"path": os.path.relpath(IDEATION, ROOT).replace("\\", "/"),
                              "sha256": sha256_bytes(ideation.encode("utf-8"))},
        "named_regions": regions,
        "observed_diff_blocks": diff_blocks,
        "editions_differ_only_in_named_regions": only_named,
        "no_floor_values_in_ideation_edition_probes": {
            # floor/bar numerals + directed-mechanism content words. "A07" alone is NOT
            # probed: it survives only as the opaque citation "cycle-1 K5/A07 pattern" for
            # the null-construction mechanism, carrying no mechanism content (verified: the
            # mechanism words below all probe 0).
            probe: (probe in ideation) for probe in
            ["13.8", "10.3", "0.218", "13.74", "9.70", "9.68", "0.202", "off_A", "interacting",
             "referee", "charter", "early-season", "early season", "transient"]
        },
    }
    if not only_named:
        raise SystemExit("edition diff has unexpected blocks; refusing to freeze")
    leaked = [k for k, v in receipt["no_floor_values_in_ideation_edition_probes"].items() if v]
    if leaked:
        raise SystemExit(f"ideation edition contains probe strings {leaked}; refusing to freeze")
    with open(RECEIPT, "w", encoding="utf-8") as f:
        json.dump(receipt, f, indent=2)
        f.write("\n")

    floors = [{"path": p, "sha256": sha256_file(os.path.join(ROOT, p))} for p in FLOORS_ARTIFACTS]
    tc = {
        "schema": "stage3_score/S30/target_contract/1",
        "status": "FROZEN",
        "authorities": ["D042", "D043", "D045", "D046", "D047", "D049"],
        "estimands": {
            "E1_GAME_TOTAL": {"statistic": "sum of both teams' final points, officially settled (OT included)", "unit": "points", "denominator": "per game", "primary_metric": "mae"},
            "E2_FINAL_MARGIN_HOME": {"statistic": "home final points minus away final points, settled (OT included)", "unit": "points", "denominator": "per game", "primary_metric": "mae"},
            "E3_HOME_WIN_PROB": {"statistic": "probability home team is the settled winner; model emits p in (0,1)", "unit": "probability", "denominator": "per game", "primary_metric": "brier_raw_model_probability"},
        },
        "universe": {"game_clusters": 1491, "team_game_rows": 2982, "seasons": "2021-2026",
                      "independent_unit": "game cluster; games never split across folds or bootstrap draws",
                      "coverage_floors": {"pooled_min_fraction": 0.90, "per_fold_test_min_fraction": 0.80},
                      "coverage_predicates": "information-based, cutoff-valid only; all-covered-games sensitivity row mandatory (non-gating)"},
        "folds": ["train_lt_2022", "train_lt_2023", "train_lt_2024", "train_lt_2025", "train_lt_2026"],
        "inference": {"unit": "game-clustered bootstrap", "B_test": 10000, "B_train_refit": 2000},
        "multiplicity": {"element": "(arm, estimand) pair", "estimand_dimension": "inside the arm's single mechanism family",
                          "correction": "family-Holm alpha 0.05", "disputed_partitions": "both run; stricter governs (frozen strengthening)",
                          "kills": "evaluated uncorrected", "multi_survivor": "within-estimand only",
                          "cross_estimand_claims": "corrected pass required on each estimand claimed"},
        "k0_discipline": {"definition": "arm's own pipeline, zero substantive features, 17 machine dimensions of comparison_gate.py",
                            "null_strength_floor": "composite frozen ingredients as structural/null-granted terms, byte-pinned (column digests of score_baseline_rows.parquet or builder source hash + resolved parameters)",
                            "cannot_host": "mechanical demonstration reproduced by S34; BELOW-FLOOR-NULL label inseparable; never in unqualified pass tallies; S40 routes would-be promotion to S42 USER gate",
                            "estimation_objective": "explicitly matched dimension; per-arm deviation at S36 voids the arm",
                            "schema": "S32B_K0_CONTRACT must freeze before S33 completes (P26 schema cannot represent E1/E2/E3)"},
        "public_floors": {"artifacts": floors, "values_not_printed_in_contract": True,
                            "contamination": "all S33+ authors assumed to know floors and market bars; floor/bar values banned from kills, stopping rules, coverage predicates, grids; permanent honest-labeling note in adjudication"},
        "market": {"comparison": "paired matched-universe vs LATE cross-book de-vigged consensus, context only, never a gate",
                    "features": "market-odds fields inadmissible as features and coverage inputs this cycle (P2B); USER-level escalation is this contract's own stricter rule",
                    "live_stream": "snapshot < commence filtered at call site (P2B F9)"},
        "leakage": {"ot": "settled estimands include OT; same-game realized info prohibited on the prediction path",
                     "receipts": ["P22 invocation per feature column (S37 verifies fit-for-purpose on score surrogates)",
                                   "frozen per-arm feature-lineage table",
                                   "current-game-deletion invariance at COLUMN grain: closed schedule-identity column set (scheduled date, matchup, home/away, season; S34-extendable), as-of-cutoff values, all other columns nulled, byte-identity"],
                     "injury": "availability features barred this cycle absent point-in-time T0 provenance covering the window",
                     "ideation_isolation": "packets carry the IDEATION EDITION only; per-source packet hash + forbidden-file list receipts"},
        "blinding": "sealed results under stage3_score/SEALED_RESULTS; S39 verifies without opening; only S40 opens; D036 pipeline to the board",
        "user_gates": ["S42_ADOPTION_DECISION: adoption of any fitted score model for operational or wager-shaped use"],
        "editions": {"full": {"path": os.path.relpath(FULL, ROOT).replace("\\", "/"), "sha256": sha256_bytes(full.encode("utf-8"))},
                      "ideation": {"path": os.path.relpath(IDEATION, ROOT).replace("\\", "/"), "sha256": sha256_bytes(ideation.encode("utf-8"))},
                      "diff_receipt": os.path.relpath(RECEIPT, ROOT).replace("\\", "/")},
    }
    with open(TC_JSON, "w", encoding="utf-8") as f:
        json.dump(tc, f, indent=2)
        f.write("\n")
    print("FULL sha256:", tc["editions"]["full"]["sha256"])
    print("IDEATION sha256:", tc["editions"]["ideation"]["sha256"])
    print("diff receipt: only_named =", only_named)
    print("floors pinned:", [f_["sha256"][:12] for f_ in floors])


if __name__ == "__main__":
    main()
