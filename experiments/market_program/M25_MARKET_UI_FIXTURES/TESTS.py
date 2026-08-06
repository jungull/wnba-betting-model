"""
TESTS.py -- validation for M25_MARKET_UI_FIXTURES.

Run: python experiments/market_program/M25_MARKET_UI_FIXTURES/TESTS.py

These are unit/synthetic/identity/schema tests only, per the node's standing rule 8
(no performance peeking). Nothing here reads SEALED_RESULTS or any comparative
historical performance data.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
sys.path.insert(0, str(HERE))

import render as R  # noqa: E402
import build_shell as B  # noqa: E402

FAILURES: list[str] = []
PASS_COUNT = 0


def check(name: str, condition: bool, detail: str = ""):
    global PASS_COUNT
    if condition:
        PASS_COUNT += 1
        print(f"PASS: {name}")
    else:
        msg = f"FAIL: {name}" + (f" -- {detail}" if detail else "")
        print(msg)
        FAILURES.append(msg)


def load(name: str):
    with open(FIXTURES / name, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    now = B.now_reference()

    # ---- 1. fixtures-only / no live wiring -----------------------------------------
    shell_source = (HERE / "build_shell.py").read_text(encoding="utf-8")
    forbidden_live_markers = ["requests.get", "requests.post", "urllib.request", "socket.socket",
                               "http.client", "aiohttp"]
    hits = [m for m in forbidden_live_markers if m in shell_source]
    check("build_shell.py contains no live network I/O calls", len(hits) == 0, str(hits))

    render_source = (HERE / "render.py").read_text(encoding="utf-8")
    hits2 = [m for m in forbidden_live_markers if m in render_source]
    check("render.py contains no live network I/O calls", len(hits2) == 0, str(hits2))

    shell_html = B.build()
    forbidden_client_js = ["fetch(", "XMLHttpRequest", "WebSocket(", "<script"]
    hits3 = [m for m in forbidden_client_js if m in shell_html]
    check(
        "shell.html contains no client-side network calls or scripts (fully static, baked at build time)",
        len(hits3) == 0,
        str(hits3),
    )
    check(
        "shell.html declares itself a PRODUCT SCAFFOLD with the verbatim epistemic-status banner",
        "PRODUCT SCAFFOLD built against fixtures." in shell_html
        and "fixtures render as fixtures" in shell_html,
    )

    # ---- 2. stale/absent input renders as a warning, never a number ----------------
    quotes = load("cross_book_quotes.json")["quotes"]
    stale_row = next(q for q in quotes if q["quote_id"] == "Q_FIXTURE_0001_C_STALE")
    absent_row = next(q for q in quotes if q["quote_id"] == "Q_FIXTURE_0001_D_ABSENT")
    fresh_row = next(q for q in quotes if q["quote_id"] == "Q_FIXTURE_0001_A")

    rendered_stale = R.render_numeric_signal(
        "x", stale_row["price_over_american"], stale_row["retrieval_ts"],
        stale_row["max_staleness_bound_seconds"], now,
    )
    rendered_absent = R.render_numeric_signal(
        "x", absent_row["price_over_american"], absent_row["retrieval_ts"],
        absent_row["max_staleness_bound_seconds"], now,
    )
    rendered_fresh = R.render_numeric_signal(
        "x", fresh_row["price_over_american"], fresh_row["retrieval_ts"],
        fresh_row["max_staleness_bound_seconds"], now,
    )

    check("stale quote renders as warning", rendered_stale["display"] == "warning" and rendered_stale["reason"] == "STALE_INPUT")
    check("stale quote render payload never carries the numeric value", "value" not in rendered_stale)
    check("absent quote renders as warning", rendered_absent["display"] == "warning" and rendered_absent["reason"] == "ABSENT_INPUT")
    check("absent quote render payload never carries the numeric value", "value" not in rendered_absent)
    check("fresh quote renders as a value", rendered_fresh["display"] == "value" and rendered_fresh["value"] == -108)
    check("fresh quote carries a freshness stamp", rendered_fresh["freshness"]["status"] == "FRESH")

    # every value-rendered signal in the shell HTML must be paired with a freshness stamp;
    # scan for numeric "value" divs and confirm each has an accompanying "freshness" span in
    # the same section by construction of the renderer (structural check via render.py directly)
    for q in quotes:
        r = R.render_numeric_signal(
            "x", q.get("price_over_american"), q.get("retrieval_ts"),
            q.get("max_staleness_bound_seconds"), now,
        )
        check(f"{q['quote_id']} render carries freshness field", "freshness" in r)

    # ---- 3. evidence-ladder gating: nothing below PRODUCTION_ELIGIBLE is actionable ----
    consensus = load("consensus.json")
    rendered_consensus = R.render_numeric_signal(
        "consensus", consensus["consensus_no_vig_prob_over"], consensus["retrieval_ts"],
        consensus["max_staleness_bound_seconds"], now, consensus["evidence_labels_held"],
    )
    check(
        "consensus signal (evidence_labels_held=[]) is never actionable",
        rendered_consensus["display"] == "value" and rendered_consensus["actionable"] is False,
    )

    edge_data = load("edge_estimate.json")
    for opp in edge_data["opportunities"]:
        rendered = R.render_usable_edge(opp, now)
        if rendered["display"] == "value":
            check(
                f"{opp['opportunity_id']} usable_edge is not actionable (no PRODUCTION_ELIGIBLE label)",
                rendered["actionable"] is False,
            )
    check(
        "the stale edge_estimate fixture renders as a warning, not a computed usable_edge",
        R.render_usable_edge(
            next(o for o in edge_data["opportunities"] if o["opportunity_id"] == "OPP_FIXTURE_0002_STALE"), now
        )["display"] == "warning",
    )

    # evidence label strings used anywhere in fixtures must be members of the frozen TAXONOMY set
    all_labels_used = set()
    for fname in ["consensus.json", "edge_estimate.json"]:
        data = load(fname)
        if "evidence_labels_held" in data:
            all_labels_used.update(data["evidence_labels_held"])
        if "opportunities" in data:
            for o in data["opportunities"]:
                all_labels_used.update(o.get("evidence_labels_held", []))
    check(
        "every evidence label referenced in fixtures is a member of the frozen 7-label ladder",
        all_labels_used.issubset(set(R.EVIDENCE_LADDER_LABELS)),
        str(all_labels_used - set(R.EVIDENCE_LADDER_LABELS)),
    )
    check(
        "no fixture currently claims PRODUCTION_ELIGIBLE (nothing has been promoted lane-wide)",
        R.PRODUCTION_ELIGIBLE not in all_labels_used,
    )

    # ---- 4. amendment-4 reaction-time claim discipline ------------------------------
    residuals = load("stale_book_residuals.json")["candidates"]
    complete = next(c for c in residuals if c["candidate_id"] == "STALE_CANDIDATE_FIXTURE_COMPLETE")
    incomplete = next(c for c in residuals if c["candidate_id"] == "STALE_CANDIDATE_FIXTURE_INCOMPLETE")

    r_complete = R.render_reaction_time_claim(complete)
    r_incomplete = R.render_reaction_time_claim(incomplete)
    check("complete reaction-time claim renders as a reaction_time_claim (all mandatory fields present)", r_complete["display"] == "reaction_time_claim")
    check("complete reaction-time claim is never actionable at fixture stage", r_complete.get("actionable") is False)
    check("incomplete reaction-time claim renders UNSUPPORTABLE", r_incomplete["display"] == "UNSUPPORTABLE")
    check(
        "UNSUPPORTABLE claim reports which mandatory fields are missing",
        set(r_incomplete["missing_fields"]) == {
            "t_upper", "poll_interval_quote_seconds", "vendor_latency_bound", "clock_skew_bound",
        },
        str(r_incomplete["missing_fields"]),
    )
    check(
        "every mandatory amendment-4 field name is checked",
        set(R.REACTION_TIME_MANDATORY_FIELDS) == {
            "t_lower", "t_upper", "poll_interval_event_seconds", "poll_interval_quote_seconds",
            "vendor_latency_bound", "clock_skew_bound", "censor_type", "tier", "n_trusted", "n_excluded",
        },
    )

    # sharpness prohibition: opportunity age is never a bare scalar, always an interval
    age_data = load("opportunity_age.json")["opportunities"]
    fresh_age = next(o for o in age_data if o["opportunity_id"] == "OPP_FIXTURE_0001")
    stale_age = next(o for o in age_data if o["opportunity_id"] == "OPP_FIXTURE_0002_STALE")
    r_age_fresh = R.render_opportunity_age(fresh_age, now)
    r_age_stale = R.render_opportunity_age(stale_age, now)
    check("fresh opportunity age renders as an interval, not a bare scalar", r_age_fresh["display"] == "interval")
    check("interval has lower <= upper", r_age_fresh["age_lower_seconds"] <= r_age_fresh["age_upper_seconds"])
    check("stale opportunity age renders as a warning, not an interval", r_age_stale["display"] == "warning")

    # ---- 5. mode badge defaults to SHADOW; ungated transitions are refused ---------
    mode_scenarios = load("mode_state.json")["scenarios"]
    default_scn = next(s for s in mode_scenarios if s["scenario_id"] == "MODE_FIXTURE_DEFAULT")
    ungated_scn = next(s for s in mode_scenarios if s["scenario_id"] == "MODE_FIXTURE_UNGATED_CONFIRM_REQUEST")
    gated_scn = next(s for s in mode_scenarios if s["scenario_id"] == "MODE_FIXTURE_GATED_CONFIRM_REQUEST")

    b_default = R.render_mode_badge(default_scn)
    b_ungated = R.render_mode_badge(ungated_scn)
    b_gated = R.render_mode_badge(gated_scn)

    check("default mode scenario badge is SHADOW", b_default["badge_mode"] == "SHADOW")
    check("default mode scenario carries no warning", b_default["warning"] is None)
    check("ungated CONFIRM request is refused and forced back to SHADOW", b_ungated["badge_mode"] == "SHADOW" and b_ungated["warning"] == "MODE_TRANSITION_UNGATED_FORCED_TO_SHADOW")
    check(
        "gated CONFIRM request still displays SHADOW as the badge (never self-verifies a grant)",
        b_gated["badge_mode"] == "SHADOW",
    )
    check("SHADOW is the frozen default mode constant", R.DEFAULT_MODE == "SHADOW")
    check("mode ladder matches D024's four modes exactly", set(R.MODES) == {"OFF", "SHADOW", "CONFIRM", "AUTO"})

    # shell.html actually shows a mode badge for every scenario, and never shows CONFIRM/AUTO
    # as the badge_mode anywhere (since none is validly gated in this scaffold)
    check(
        'shell.html renders "MODE: SHADOW" at least once (default badge visible)',
        "MODE: SHADOW" in shell_html,
    )
    check(
        "shell.html never renders MODE: CONFIRM or MODE: AUTO as an active badge",
        "MODE: CONFIRM" not in shell_html and "MODE: AUTO" not in shell_html,
    )

    # ---- 6. hard risk control checklist: every one of the 11 controls is visible ---
    exec_data = load("execution_warnings.json")
    checklist = R.render_hard_risk_control_checklist(exec_data)
    controls_seen = {r["control"] for r in checklist["rows"]}
    check(
        "all 11 frozen hard risk controls (section 7) appear in the checklist",
        set(R.HARD_RISK_CONTROLS).issubset(controls_seen),
        str(set(R.HARD_RISK_CONTROLS) - controls_seen),
    )
    check("no hard risk control is silently satisfied in this scaffold", checklist["any_satisfied"] is False)
    check("hard risk control list length matches the frozen 11-item contract checklist", len(R.HARD_RISK_CONTROLS) == 11)

    # ---- 7. reserved-term "arbitrage" discipline ------------------------------------
    check(
        "'arbitrage' attached to TRUE_CROSS_BOOK_ARBITRAGE is compliant",
        R.check_reserved_arbitrage_term("TRUE_CROSS_BOOK_ARBITRAGE", "possible arbitrage window"),
    )
    check(
        "'arbitrage' attached to any other class is flagged non-compliant",
        R.check_reserved_arbitrage_term("MIDDLES_AND_DISLOCATIONS", "this looks like arbitrage") is False,
    )
    check(
        "text without the word 'arbitrage' is always compliant regardless of class",
        R.check_reserved_arbitrage_term("MIDDLES_AND_DISLOCATIONS", "a middle"),
    )
    check(
        "opportunity classes fixture uses only match the frozen 6-class taxonomy",
        {c.get("opportunity_class") for c in load("edge_estimate.json")["opportunities"]}.issubset(set(R.OPPORTUNITY_CLASSES)),
    )
    check(
        "shell.html itself never uses the word 'arbitrage' (no arbitrage-class fixture is rendered)",
        "arbitrage" not in shell_html.lower(),
    )

    # ---- 8. M00-U5 fixture-caveat header integrity ----------------------------------
    manifest = load("manifest.json")
    computed_hash = hashlib.sha256(manifest["caveat_text"].encode("utf-8")).hexdigest()
    check(
        "manifest.json m00_use_class is M00-U5 (schema fixtures and test corpora)",
        manifest["m00_use_class"] == "M00-U5",
    )
    check(
        "manifest.json caveat_sha256 matches sha256 of its own caveat_text (internal consistency)",
        computed_hash == manifest["caveat_sha256"],
        f"computed={computed_hash} recorded={manifest['caveat_sha256']}",
    )
    # cross-check against the frozen value cited in TAXONOMY.json for M00-U5 (transcribed
    # constant below, sourced from TAXONOMY.json final_state_archive_ruling.permitted_uses)
    taxonomy_path = HERE.parent / "M00_MARKET_PROGRAM_CONTRACT" / "TAXONOMY.json"
    if taxonomy_path.exists():
        taxonomy = json.loads(taxonomy_path.read_text(encoding="utf-8"))
        u5 = next(
            u for u in taxonomy["final_state_archive_ruling"]["permitted_uses"] if u["use_class"] == "M00-U5"
        )
        check(
            "manifest.json caveat_text matches TAXONOMY.json M00-U5 caveat_text verbatim",
            manifest["caveat_text"] == u5["caveat_text"],
        )
        check(
            "manifest.json caveat_sha256 matches TAXONOMY.json M00-U5 caveat_sha256",
            manifest["caveat_sha256"] == u5["caveat_sha256"],
        )
    else:
        check("TAXONOMY.json reachable for M00-U5 cross-check", False, str(taxonomy_path))

    # ---- 9. every fixture timestamp is clearly synthetic / no accidental T2 bytes --
    # No fixture file may reference the real archive path or claim tier T0/T1/T2 outside the
    # explicit "_FIXTURE_SYNTHETIC" / "_FIXTURE" markers this node invented.
    for fname in [
        "consensus.json", "cross_book_quotes.json", "stale_book_residuals.json",
        "line_price_history.json", "information_events.json", "our_projection.json",
        "edge_estimate.json", "opportunity_age.json",
    ]:
        text = (FIXTURES / fname).read_text(encoding="utf-8")
        check(f"{fname} does not reference the real master_odds.csv archive path", "drive_masters" not in text)
        tier_mentions = re.findall(r'"tier":\s*"([^"]+)"', text)
        bad = [t for t in tier_mentions if "FIXTURE" not in t]
        check(f"{fname} tier fields are all fixture-marked (no bare T0/T1/T2 claims)", len(bad) == 0, str(bad))

    # ---- 10. required output files exist for the scope contract ---------------------
    check("REPORT.md exists in the node's write scope", (HERE / "REPORT.md").exists())
    check("shell.html builds successfully and exists", (HERE / "shell.html").exists())

    print()
    print(f"{PASS_COUNT} passed, {len(FAILURES)} failed")
    if FAILURES:
        for f in FAILURES:
            print(f)
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
