#!/usr/bin/env python3
"""TESTS.py -- M14_MODEL_MARKET_RESIDUAL validation suite.

Run: python experiments/market_program/M14_MODEL_MARKET_RESIDUAL/TESTS.py
(rebuilds FINDINGS.json first, then checks structural invariants against it -- this suite does
NOT re-implement the statistics; it checks that build_residual.py's own output is internally
consistent, matches the frozen contract/taxonomy hashes, and honors this node's acceptance
criteria and stop conditions.)
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_residual as br  # noqa: E402

FINDINGS_PATH = HERE / "FINDINGS.json"

RESULTS = []


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append({"name": name, "pass": bool(cond), "detail": detail})
    print(("PASS " if cond else "FAIL "), name, ("" if cond else f" -- {detail}"))


def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def main() -> int:
    findings = br.main()   # rebuild deterministically, get the in-memory dict back

    # T01 -- FINDINGS.json parses via plain json.load (the harness's own validation command)
    parsed = json.loads(FINDINGS_PATH.read_text(encoding="utf-8"))
    check("T01_findings_json_parses", isinstance(parsed, dict) and len(parsed) > 0)

    # T02 -- contract hash pinned and verified
    check("T02_contract_sha256_matches_pinned_constant",
          parsed["contract_sha256_verified"] == br.CONTRACT_SHA256_EXPECTED)

    # T03 -- M00-U2 caveat hash reproduces from TAXONOMY.json bytes
    taxonomy = json.loads(br.TAXONOMY.read_text(encoding="utf-8"))
    u2 = next(u for u in taxonomy["final_state_archive_ruling"]["permitted_uses"]
              if u["use_class"] == "M00-U2")
    got_hash = sha256_hex(u2["caveat_text"])
    check("T03_m00_u2_caveat_hash_reproduces",
          got_hash == u2["caveat_sha256"] == parsed["m00_bounded_use"]["caveat_hash"])

    # T04 -- epistemic status line is written verbatim and matches the node's contract text
    expected_epistemic = (
        "DIAGNOSTIC MEASUREMENT. Residuals between the translated fundamental fair line and the "
        "market consensus, both pinned to point-in-time snapshots. A residual is a discrepancy, "
        "not an edge; promotion beyond diagnostic status runs through the M00 ladder and the "
        "shadow-trading chain, never through this node."
    )
    check("T04_epistemic_status_verbatim", parsed["epistemic_status"] == expected_epistemic)

    # T05 -- evidence class is DIAGNOSTIC, no ladder label, no tradability/production claim
    # (acceptance criterion 2)
    check("T05_evidence_class_diagnostic_no_ladder_label",
          parsed["evidence_class"] == "DIAGNOSTIC"
          and parsed["evidence_ladder_labels_held"] == []
          and parsed["not_a_production_eligible_or_tradability_claim"] is True)
    report_text = ""
    report_path = HERE / "M14_REPORT_BODY.md"
    if report_path.exists():
        report_text = report_path.read_text(encoding="utf-8")
    # heuristic: every sentence-ish chunk mentioning PRODUCTION_ELIGIBLE must also contain a
    # negation cue nearby (no / never / not / none) -- catches an affirmative claim like "holds
    # PRODUCTION_ELIGIBLE" while tolerating "no PRODUCTION_ELIGIBLE claim is made" /
    # "or PRODUCTION_ELIGIBLE claim is made" (both negated by the sentence's leading "No").
    negation_cues = ("no ", "never", "not ", "none")
    bad_chunks = []
    if report_text:
        for chunk in report_text.replace("\n", " ").split(". "):
            if "PRODUCTION_ELIGIBLE" in chunk and not any(c in chunk.lower() for c in negation_cues):
                bad_chunks.append(chunk.strip())
    check("T05b_report_never_affirmatively_claims_production_eligible",
          len(bad_chunks) == 0, f"unnegated mentions: {bad_chunks}")

    # T06 -- acceptance criterion 1: every residual pair carries explicit timestamps and a
    # recorded mismatch window, wrapped with the full amendment-4 sentinel field set
    tp = parsed["timestamp_pairing_and_mismatch_window"]
    a4_fields = ["t_lower", "t_upper", "poll_interval_event", "poll_interval_quote",
                 "vendor_latency_bound", "clock_skew_bound", "censor_type", "tier"]
    check("T06_amendment4_field_set_present", all(f in tp for f in a4_fields))
    check("T06b_is_reaction_time_claim_false", tp["is_reaction_time_claim"] is False)
    mw = tp["mismatch_window_hours"]
    check("T06c_mismatch_window_recorded_game_and_book_level",
          "game_level_snap_ret_minus_forecast_cutoff" in mw
          and "book_level_last_update_minus_forecast_cutoff" in mw
          and mw["game_level_snap_ret_minus_forecast_cutoff"]["n"] > 0
          and mw["book_level_last_update_minus_forecast_cutoff"]["n"] > 0)

    # T07 -- acceptance criterion 3: reported by market, by book, by season -- never a single
    # silently-pooled cell standing in for all three
    check("T07a_by_market_reports_exactly_one_matched_market_and_states_the_rest_as_null",
          parsed["residual_by_market"][br.MARKET_KEY]["n_matched_player_games"] > 0
          and len(parsed["residual_by_market"]["other_stat_families_checked"]) > 0)
    check("T07b_by_season_has_multiple_seasons_plus_pooled_never_only_pooled",
          set(parsed["residual_by_season"][br.HEADLINE_TIER].keys()) >= {"2024", "2025", "2026", "pooled"})
    check("T07c_by_book_has_multiple_books_never_only_consensus",
          len(parsed["residual_by_book"]) >= 5)
    check("T07d_by_book_and_season_grid_present",
          len(parsed["residual_by_book_and_season"]) == len(parsed["residual_by_book"]))

    # T08 -- acceptance criterion 4: falsification block states both directions and reports an
    # actually-measured verdict (not merely asserted)
    fz = parsed["falsification"]
    check("T08a_falsification_states_support_and_falsify_conditions",
          len(fz["would_be_supported_by"]) > 20 and len(fz["would_be_falsified_by"]) > 20)
    pooled = fz["pooled_headline"]
    expect_verdict = ("NOT_FALSIFIED_AT_THIS_N_SEE_CAVEATS"
                       if (pooled["slope_distinguishable_from_zero"] and pooled["slope"] > 0)
                       else "FALSIFIED_NO_PREDICTIVE_CONTENT_DETECTED_AT_THIS_N")
    check("T08b_verdict_consistent_with_measured_pooled_slope", fz["verdict"] == expect_verdict,
          f"got {fz['verdict']!r}, pooled slope={pooled['slope']!r}, "
          f"distinguishable={pooled['slope_distinguishable_from_zero']!r}")
    check("T08c_falsification_reports_season_variant_and_influence_robustness",
          len(fz["by_season_headline"]) == 3 and len(fz["by_translation_variant_headline"]) == 4
          and len(fz["influence_leave_out_top_n"]) == 3)

    # T09 -- integrity: M14's rebuilt translation_rows hash and reconstructed consensus
    # probability actually match the upstream M13 artifact (re-derived, not merely trusted)
    inp = parsed["inputs"]
    check("T09a_translation_rows_hash_matches_m13_findings",
          inp["m13_translation_rows"]["sha256_matches_m13_findings"] is True)
    rc = inp["reconstruction_integrity_check"]
    check("T09b_book_level_reconstruction_reproduces_m13_consensus_within_tolerance",
          rc["reconstruction_matches_within_tolerance"] is True and rc["n_player_games_reconstructed"] > 5000)

    # T10 -- stop conditions: this node's own source never opens/imports anything under
    # stage2b/SEALED_RESULTS. Every mention of "stage2b" in the source is prose (inside a quoted
    # string), never part of a Path(...)/open(...) construction or an import statement.
    src = (HERE / "build_residual.py").read_text(encoding="utf-8")
    suspicious_lines = [
        ln for ln in src.splitlines()
        if "stage2b" in ln and ("Path(" in ln or ln.strip().startswith(("import ", "from ", "open(")))
    ]
    check("T10_sealed_results_path_never_opened_or_imported_in_source",
          len(suspicious_lines) == 0, f"suspicious lines: {suspicious_lines}")
    check("T10b_stop_conditions_block_present_and_all_none_tripped",
          all("none tripped" in v or "none made" in v or "not a new or stretched use" in v.lower()
              for v in parsed["stop_conditions_checked"].values()))

    # T11 -- could_not_establish and contradictions are preserved, not omitted
    check("T11_could_not_establish_nonempty_null_preservation", len(parsed["could_not_establish"]) >= 3)

    # T12 -- result_hash is reproducible from the findings body (excluding generated_utc)
    body = {k: v for k, v in parsed.items() if k not in ("generated_utc", "result_hash")}
    recomputed = sha256_hex(json.dumps(body, sort_keys=True, separators=(",", ":"), default=str))
    check("T12_result_hash_reproduces", recomputed == parsed["result_hash"])

    n_pass = sum(1 for r in RESULTS if r["pass"])
    n_fail = sum(1 for r in RESULTS if not r["pass"])
    print(json.dumps({"suite": "M14_MODEL_MARKET_RESIDUAL/TESTS.py", "n_pass": n_pass, "n_fail": n_fail}))
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
