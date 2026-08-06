#!/usr/bin/env python3
"""market_view.py -- model-agnostic, book-agnostic market screen shell, rendered from a
view payload.

PRODUCT SCAFFOLD built against fixtures. Carries no market claim and must not imply that
any edge, signal or tradable opportunity exists: fixtures render as fixtures.

This is the market_intelligence lane's extension of the U11/U13 pattern established in
`experiments/player_program/product_lane/U11_UI_SHELL/ui_shell.py` and
`.../U13_MONITORING_INTERFACE/monitor_state.py` -- it does not fork that pattern, it reuses
its shape:

  * a pure `render_payload(payload: dict) -> str` function with no I/O, no model, no
    estimator, no book, no venue identifier baked in (U11's invariant 1);
  * a single decision point, `resolve_cell`, between showing a number and showing a
    warning, so absence, staleness, non-numeric and non-finite values all fail to a
    warning and never to a substituted value (U11's invariant 2);
  * a fail-closed status vocabulary with an explicit UNKNOWN member that suppresses rather
    than defaults to healthy (U13's FAIL-CLOSED property).

Three things are new here because a market screen is not a projection screen:

  1. **Evidence-ladder gating.** Every opportunity carries the SET of §3 labels it
     currently holds (`contract_constants.LADDER_LABELS`, loaded from the frozen
     TAXONOMY.json, never retyped). The screen renders that set verbatim and computes a
     structural `actionable` flag: true only when the held set is COMPLETE (every rung
     1..7, not just a claimed PRODUCTION_ELIGIBLE with gaps beneath it -- "reporting a
     higher label without the per-label records beneath it is a Severity A methodology
     breach", section 3) AND every hard-risk-control check passes. Nothing below
     PRODUCTION_ELIGIBLE ever renders as actionable, and a PRODUCTION_ELIGIBLE claim with
     a broken ladder beneath it is downgraded and flagged, not trusted.
  2. **The D024 mode badge.** OFF/SHADOW/CONFIRM/AUTO, taken from TAXONOMY.json. A payload
     that declares no mode, or an invalid one, renders the SHADOW badge with an explicit
     note that this is the D024 default being applied for display, not a live deployment
     fact. This shell places no order in any mode -- it has no order-placement code path at
     all, in any mode.
  3. **The M00 archive-use gate.** Any data point tagged tier T2 must carry
     `m00_use_class` and `caveat_sha256`, and only M00-U4 is accepted for on-screen
     display (contract_constants.M00_USE_CLASS_ACCEPTED_ON_SCREEN); every other T2 use, or
     a T2 point with no use class, or a mismatched caveat hash, renders as a
     CONTRACT_VIOLATION warning and the underlying value is suppressed -- never displayed,
     even alongside the warning. This is a structural safeguard exercised only against
     fixtures; it has never touched the real archive.

Everything this module displays is a value carried in the payload it was handed. The
renderer never fits, loads, polls, or estimates.
"""
from __future__ import annotations

import datetime as _dt
import html
import math
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import contract_constants as CC  # noqa: E402

FIXTURES = HERE / "fixtures"
RENDERED = HERE / "rendered"

VIEW_SCHEMA = "m25_market_view_payload/1"

EPISTEMIC_BANNER = (
    "PRODUCT SCAFFOLD built against fixtures. Carries no market claim and must not imply "
    "that any edge, signal or tradable opportunity exists: fixtures render as fixtures."
)

REASONS = {
    "VALUE_ABSENT": "no value was supplied for this cell",
    "VALUE_NOT_FINITE": "the supplied value is not a finite number",
    "VALUE_NOT_NUMERIC": "the supplied value is not numeric",
    "INPUT_STALE": "a required input is older than its declared maximum age",
    "INPUT_MISSING": "a required input was never delivered",
    "INPUT_FAILED": "a required input's producing job failed",
    "INPUT_UNDECLARED": "a required input is named but not present in the input ledger",
    "OUTPUT_UNBOUND": "outputs are not bound to a model version and artifact digests",
    "ROW_BLOCKED": "this row carries an explicit blocker",
    "PAYLOAD_UNREADABLE": "the payload could not be interpreted",
    "NO_TIMESTAMP": "amendment 4: a displayed number without a timestamp is never rendered",
    "LADDER_UNKNOWN_LABEL": "a claimed evidence-ladder label is not one of the seven frozen labels",
    "LADDER_INCOMPLETE": "a higher label is claimed without every lower label also held (section 3 breach)",
    "CONTRACT_VIOLATION": "a tier-T2 value was used outside its bounded, accepted use -- suppressed, not displayed",
    "M00_USE_CLASS_MISSING": "a tier-T2 value carries no m00_use_class",
    "M00_USE_CLASS_UNACCEPTED": "this screen accepts only M00-U4 for on-screen T2 display; another use class is not a display use",
    "M00_CAVEAT_HASH_MISMATCH": "the payload's caveat text does not hash to the frozen caveat_sha256 for its use class",
}

# --------------------------------------------------------------------- generic helpers
def _e(x: Any) -> str:
    return html.escape("" if x is None else str(x), quote=True)


def _parse_ts(ts: Any) -> _dt.datetime | None:
    if not isinstance(ts, str) or not ts.strip():
        return None
    try:
        dt = _dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_dt.timezone.utc)
    return dt


def _is_finite_number(v: Any) -> bool:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return False
    return math.isfinite(float(v))


def _age_seconds(captured: _dt.datetime | None, as_of: _dt.datetime | None) -> float | None:
    if captured is None or as_of is None:
        return None
    return (as_of - captured).total_seconds()


# ------------------------------------------------------------- freshness model (U11-style)
def evaluate_inputs(payload: dict) -> dict[str, dict]:
    """Classify every declared input as OK / STALE / MISSING / FAILED. Fail-closed:
    an input whose freshness cannot be evaluated is MISSING, never OK."""
    as_of = _parse_ts(payload.get("as_of"))
    out: dict[str, dict] = {}
    for item in payload.get("inputs") or []:
        iid = str(item.get("input_id"))
        rec = {
            "input_id": iid,
            "label": item.get("label") or iid,
            "captured_at": item.get("captured_at"),
            "max_age_seconds": item.get("max_age_seconds"),
            "age_seconds": None,
            "tier": item.get("tier"),
            "detail": item.get("detail") or "",
        }
        declared = str(item.get("status") or "").lower()
        if declared == "failed":
            rec["state"], rec["reason"] = "FAILED", "INPUT_FAILED"
            out[iid] = rec
            continue
        if declared == "missing" or item.get("captured_at") in (None, ""):
            rec["state"], rec["reason"] = "MISSING", "INPUT_MISSING"
            out[iid] = rec
            continue

        captured = _parse_ts(item.get("captured_at"))
        max_age = item.get("max_age_seconds")
        if captured is None or as_of is None or not _is_finite_number(max_age):
            rec["state"], rec["reason"] = "MISSING", "INPUT_MISSING"
            rec["detail"] = (rec["detail"] + " freshness not evaluable").strip()
            out[iid] = rec
            continue

        age = (as_of - captured).total_seconds()
        rec["age_seconds"] = age
        if age > float(max_age) or age < 0:
            rec["state"], rec["reason"] = "STALE", "INPUT_STALE"
        else:
            rec["state"], rec["reason"] = "OK", None
        out[iid] = rec
    return out


def model_binding(payload: dict) -> dict:
    model = payload.get("model") or {}
    version = model.get("version")
    hashes = model.get("artifact_sha256") or {}
    bound = bool(isinstance(version, str) and version.strip()) and bool(
        isinstance(hashes, dict) and hashes
    )
    return {
        "version": version,
        "artifact_sha256": hashes if isinstance(hashes, dict) else {},
        "promotion_status": model.get("promotion_status"),
        "bound": bound,
    }


def dependency_blockers(required: list | None, inputs: dict[str, dict]) -> list[dict]:
    blockers: list[dict] = []
    for iid in required or []:
        rec = inputs.get(str(iid))
        if rec is None:
            blockers.append({"reason": "INPUT_UNDECLARED", "subject": str(iid)})
        elif rec["state"] != "OK":
            blockers.append({"reason": rec["reason"], "subject": rec["label"]})
    return blockers


def resolve_cell(value: Any, blockers: list[dict], row_blockers: list[str] | None = None) -> dict:
    """The single decision point between a number and a warning. Never both."""
    reasons: list[dict] = list(blockers)
    for rb in row_blockers or []:
        reasons.append({"reason": "ROW_BLOCKED", "subject": str(rb)})
    if reasons:
        return {"kind": "warning", "reasons": reasons}
    if value is None:
        return {"kind": "warning", "reasons": [{"reason": "VALUE_ABSENT", "subject": ""}]}
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return {"kind": "warning", "reasons": [{"reason": "VALUE_NOT_NUMERIC", "subject": type(value).__name__}]}
    if not math.isfinite(float(value)):
        return {"kind": "warning", "reasons": [{"reason": "VALUE_NOT_FINITE", "subject": "non-finite float"}]}
    return {"kind": "value", "value": float(value)}


def resolve_timestamped_cell(
    value: Any,
    as_of: Any,
    captured_at: Any,
    max_age_seconds: Any,
    blockers: list[dict] | None = None,
    row_blockers: list[str] | None = None,
) -> dict:
    """resolve_cell, plus amendment-4: no displayed number without a timestamp and a
    freshness verdict against it. A value with no captured_at, or a captured_at that
    cannot be aged against payload.as_of, is suppressed -- NO_TIMESTAMP -- regardless of
    whether the bare value itself would have resolved.
    """
    blockers = list(blockers or [])
    as_of_dt = _parse_ts(as_of)
    captured_dt = _parse_ts(captured_at)
    if captured_dt is None:
        blockers.append({"reason": "NO_TIMESTAMP", "subject": "captured_at is absent or unparseable"})
    elif as_of_dt is None:
        blockers.append({"reason": "NO_TIMESTAMP", "subject": "payload as_of is absent or unparseable"})
    else:
        age = (as_of_dt - captured_dt).total_seconds()
        if not _is_finite_number(max_age_seconds):
            blockers.append({"reason": "INPUT_MISSING", "subject": "no max_age_seconds declared for this cell"})
        elif age > float(max_age_seconds) or age < 0:
            blockers.append({"reason": "INPUT_STALE", "subject": f"{age:.0f}s old, limit {max_age_seconds}s"})
    return resolve_cell(value, blockers, row_blockers)


# ------------------------------------------------------------------- evidence ladder
def evaluate_ladder(held_labels: Any) -> dict:
    """Validate a claimed set of held evidence-ladder labels against the frozen seven.

    Returns:
      held: the labels recognised as valid (subset of CC.LADDER_IDS actually supplied)
      unknown: labels supplied that are not in CC.LADDER_IDS
      complete_through: highest rank R such that ranks 1..R are ALL held (0 if rank 1 absent)
      production_claimed: True iff PRODUCTION_ELIGIBLE is in `held`
      production_eligible_valid: True iff production_claimed AND complete_through == top rank
      violation: True iff production_claimed but the ladder beneath it has a gap
    """
    raw = held_labels if isinstance(held_labels, list) else []
    held = sorted({str(x) for x in raw if str(x) in CC.LADDER_IDS}, key=lambda i: CC.LADDER_RANK_BY_ID[i])
    unknown = sorted({str(x) for x in raw if str(x) not in CC.LADDER_IDS})
    ranks_held = {CC.LADDER_RANK_BY_ID[i] for i in held}
    complete_through = 0
    for r in range(1, CC.LADDER_TOP_RANK + 1):
        if r in ranks_held:
            complete_through = r
        else:
            break
    production_claimed = CC.PRODUCTION_ELIGIBLE in held
    production_eligible_valid = production_claimed and complete_through == CC.LADDER_TOP_RANK
    violation = production_claimed and not production_eligible_valid
    return {
        "held": held,
        "unknown": unknown,
        "complete_through": complete_through,
        "production_claimed": production_claimed,
        "production_eligible_valid": production_eligible_valid,
        "violation": violation,
    }


# ------------------------------------------------------------------- hard risk controls
def evaluate_execution_warnings(rows: Any) -> dict:
    """Fail-closed evaluation of the D024 hard-risk-control checklist for one opportunity.
    A control this shell does not recognise, or that the payload marks UNKNOWN, or that
    the payload never mentions at all, blocks execution readiness -- an absent control
    check is not assumed to pass.
    """
    rows = rows if isinstance(rows, list) else []
    by_code = {}
    for r in rows:
        if not isinstance(r, dict):
            continue
        code = r.get("code")
        if code in CC.HARD_RISK_CONTROLS:
            by_code[code] = r
    results = []
    all_pass = True
    for code in CC.HARD_RISK_CONTROLS:
        row = by_code.get(code)
        status = str((row or {}).get("status") or "UNKNOWN").upper()
        if status not in ("PASS", "FAIL"):
            status = "UNKNOWN"
        if status != "PASS":
            all_pass = False
        results.append({
            "code": code,
            "status": status,
            "detail": (row or {}).get("detail") or ("no check reported for this control" if row is None else ""),
        })
    return {"rows": results, "execution_ready": all_pass and bool(rows)}


# --------------------------------------------------------------------- M00 archive gate
def evaluate_m00_use(tier: Any, use_class: Any, caveat_text: Any) -> dict:
    """T0/T1/None values pass through untouched. A T2 value is display-eligible only if
    it declares M00-U4 (this screen's only accepted on-screen use class) and its own
    caveat_text hashes to the frozen caveat_sha256 for that class. Anything else is a
    CONTRACT_VIOLATION: the underlying value must not be displayed, with or without a
    warning alongside it.
    """
    if tier != "T2":
        return {"ok": True, "codes": [], "caveat_text": None}
    codes: list[str] = []
    if not use_class:
        codes.append("M00_USE_CLASS_MISSING")
    elif use_class != CC.M00_USE_CLASS_ACCEPTED_ON_SCREEN:
        codes.append("M00_USE_CLASS_UNACCEPTED")
    elif use_class in CC.M00_PERMITTED_USES:
        expected = CC.M00_PERMITTED_USES[use_class]
        if not isinstance(caveat_text, str) or caveat_text != expected["caveat_text"]:
            codes.append("M00_CAVEAT_HASH_MISMATCH")
    if codes:
        codes.append("CONTRACT_VIOLATION")
        return {"ok": False, "codes": codes, "caveat_text": None}
    return {"ok": True, "codes": [], "caveat_text": CC.M00_PERMITTED_USES[use_class]["caveat_text"]}


# ------------------------------------------------------------------ HTML cell rendering
NUMBER_MARKER = 'class="v"'


def _fmt_number(v: float, signed: bool = False) -> str:
    return f'<span {NUMBER_MARKER}>{v:+.3f}</span>' if signed else f'<span {NUMBER_MARKER}>{v:.3f}</span>'


def _number_cell(v: float, units: str | None = None, stamp: str | None = None) -> str:
    suffix = f" <span class='u'>{_e(units)}</span>" if units else ""
    stampout = f"<div class='stamp'>as of {_e(stamp)}</div>" if stamp else "<div class='stamp warn-stamp'>NO TIMESTAMP</div>"
    return f"<td class='num'>{_fmt_number(v)}{suffix}{stampout}</td>"


def _warning_cell(reasons: list[dict], colspan: int = 1) -> str:
    parts = []
    for r in reasons:
        code = r.get("reason", "PAYLOAD_UNREADABLE")
        text = REASONS.get(code, "unclassified")
        subj = r.get("subject") or ""
        parts.append(f"{_e(code)}: {_e(text)}" + (f" ({_e(subj)})" if subj else ""))
    span = f" colspan='{colspan}'" if colspan > 1 else ""
    return (
        f"<td class='warn'{span}><span class='badge'>WARNING</span> "
        + "; ".join(parts)
        + "</td>"
    )


def _cell(resolved: dict, units: str | None = None, stamp: str | None = None) -> str:
    if resolved["kind"] == "value":
        return _number_cell(resolved["value"], units, stamp)
    return _warning_cell(resolved["reasons"])


# ------------------------------------------------------------------------- CSS
_CSS = """
body{font:14px/1.45 -apple-system,Segoe UI,Roboto,sans-serif;margin:0;padding:24px;
 background:#fbfbfc;color:#16181d}
h1{font-size:19px;margin:0 0 4px} h2{font-size:15px;margin:26px 0 8px} h3{font-size:13px;margin:16px 0 6px;color:#3c4351}
.banner{background:#1d2330;color:#fff;padding:10px 14px;border-radius:6px;margin-bottom:16px;font-weight:600}
.meta{color:#5b6472;font-size:12px;margin-bottom:14px}
table{border-collapse:collapse;width:100%;background:#fff;margin-bottom:10px}
th,td{border:1px solid #e3e6ea;padding:6px 9px;text-align:left;vertical-align:top}
th{background:#f2f4f7;font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.04em}
td.num,td.age{text-align:right;font-variant-numeric:tabular-nums}
td.age{color:#5b6472}
td.num .u{color:#77808f;font-size:11px}
.stamp{color:#77808f;font-size:10px;margin-top:2px}
.warn-stamp{color:#8a1c1c;font-weight:700}
td.warn{background:#fff5f5;color:#8a1c1c}
.badge{display:inline-block;background:#c0392b;color:#fff;font-size:10px;font-weight:700;
 padding:1px 6px;border-radius:3px;margin-right:6px;letter-spacing:.06em}
.ok{color:#1c7a3c;font-weight:600}.bad{color:#8a1c1c;font-weight:600}
code{font:12px/1.4 ui-monospace,Consolas,monospace;color:#3c4351;word-break:break-all}
.footer{color:#77808f;font-size:11px;margin-top:26px;border-top:1px solid #e3e6ea;padding-top:10px}
.mode-badge{display:inline-block;padding:4px 12px;border-radius:14px;font-weight:700;font-size:12px;
 letter-spacing:.05em;margin-right:8px}
.mode-OFF{background:#e3e6ea;color:#3c4351}
.mode-SHADOW{background:#e6ecff;color:#28408a}
.mode-CONFIRM{background:#fff2d6;color:#8a5c00}
.mode-AUTO{background:#ffdede;color:#8a1c1c}
.actionable{display:inline-block;padding:2px 9px;border-radius:4px;font-size:11px;font-weight:700;
 background:#1c7a3c;color:#fff}
.informational{display:inline-block;padding:2px 9px;border-radius:4px;font-size:11px;font-weight:700;
 background:#e3e6ea;color:#3c4351}
.ladder{display:flex;gap:4px;flex-wrap:wrap;margin:4px 0}
.rung{padding:2px 7px;border-radius:3px;font-size:10px;font-weight:600;border:1px solid #d3d8de}
.rung.held{background:#1c7a3c;color:#fff;border-color:#1c7a3c}
.rung.gap{background:#fff;color:#9aa2ad}
"""


# ------------------------------------------------------------------ mode badge
def _render_mode_badge(payload: dict) -> str:
    mode = payload.get("mode")
    defaulted = False
    if mode not in CC.EXECUTION_MODE_IDS:
        defaulted = True
        mode = CC.DEFAULT_EXECUTION_MODE
    meaning = CC.EXECUTION_MODE_MEANING.get(mode, "")
    gate = CC.EXECUTION_MODE_GATE.get(mode)
    out = [f"<div><span class='mode-badge mode-{_e(mode)}'>MODE: {_e(mode)}</span>"
           f"<span class='meta'>{_e(meaning)}</span></div>"]
    if defaulted:
        out.append(
            "<p class='meta'>note: the payload declared no valid mode. This screen is "
            "rendering <code>SHADOW</code>, the D024 default and starting mode for every "
            "strategy, as a DISPLAY default only -- it is not evidence that any live "
            "deployment exists.</p>"
        )
    if gate:
        out.append(f"<p class='meta'>gate to enter this mode: {_e(gate)}</p>")
    out.append(
        "<p class='meta'>this shell places no order in any mode -- it has no order-"
        "placement code path, in SHADOW, CONFIRM, or AUTO alike. Every mode transition on "
        "the D024 ladder is a USER_REQUIRED gate (section 9.6) and is never performed by "
        "this screen or any node.</p>"
    )
    return "".join(out)


# ------------------------------------------------------------------ evidence-ladder block
def _render_ladder(ladder_eval: dict) -> str:
    rungs = []
    for row in CC.LADDER_LABELS:
        cls = "held" if row["id"] in ladder_eval["held"] else "gap"
        definition = _e(row["definition"])
        rungs.append(f"<span class='rung {cls}' title='{definition}'>"
                     f"{row['rank']}. {_e(row['id'])}</span>")
    out = [f"<div class='ladder'>{''.join(rungs)}</div>"]
    if ladder_eval["unknown"]:
        out.append(_warn_p(f"LADDER_UNKNOWN_LABEL: {', '.join(ladder_eval['unknown'])} is not "
                            "one of the seven frozen evidence-ladder labels"))
    if ladder_eval["violation"]:
        out.append(_warn_p(
            "LADDER_INCOMPLETE: PRODUCTION_ELIGIBLE is claimed but the ladder beneath it "
            f"is not complete (held through rank {ladder_eval['complete_through']} of "
            f"{CC.LADDER_TOP_RANK}). Section 3: 'reporting a higher label without the "
            "per-label records beneath it is a Severity A methodology breach.' This "
            "opportunity is forced non-actionable regardless of the claim."
        ))
    return "".join(out)


def _warn_p(text: str) -> str:
    return f"<p class='meta'><span class='badge'>WARNING</span> {_e(text)}</p>"


# ------------------------------------------------------------------ execution warnings
def _render_execution_warnings(ew: dict) -> str:
    head = "<tr><th>hard risk control (section 7)</th><th>status</th><th>detail</th></tr>"
    body = []
    for r in ew["rows"]:
        cls = "ok" if r["status"] == "PASS" else "bad"
        body.append(f"<tr><td>{_e(r['code'])}</td><td class='{cls}'>{_e(r['status'])}</td>"
                    f"<td>{_e(r['detail'])}</td></tr>")
    ready = "<span class='ok'>READY</span>" if ew["execution_ready"] else "<span class='bad'>NOT READY</span>"
    return (f"<h3>Execution warnings</h3><p class='meta'>overall: {ready}</p>"
            f"<table>{head}{''.join(body)}</table>")


# ------------------------------------------------------------------ opportunity age
def _render_opportunity_age(first_detected_at: Any, as_of: Any) -> str:
    as_of_dt = _parse_ts(as_of)
    fd_dt = _parse_ts(first_detected_at)
    note = (
        "<p class='meta'>opportunity age is elapsed wall-clock time between our own "
        "capture timestamps, not a market reaction-time claim; it carries none of the "
        "section 6 timestamp-uncertainty calculus and must never be read as one.</p>"
    )
    if as_of_dt is None or fd_dt is None:
        return _warn_p("VALUE_ABSENT: opportunity_first_detected_at or as_of is absent/unparseable; age cannot be shown") + note
    age = (as_of_dt - fd_dt).total_seconds()
    if age < 0:
        return _warn_p("VALUE_NOT_FINITE: first_detected_at is after as_of") + note
    return f"<p>opportunity age: {_fmt_number(age)} <span class='u'>seconds</span> (since {_e(first_detected_at)})</p>" + note


# ------------------------------------------------------------------ opportunity render
def _render_opportunity(opp: dict, inputs: dict[str, dict], bound: bool, as_of: Any) -> str:
    oid = opp.get("opportunity_id")
    title = (f"<h2>Opportunity <code>{_e(oid)}</code> &mdash; {_e(opp.get('label') or '')}</h2>"
             if oid else "<h2>Opportunity " + _warning_cell([{"reason": "VALUE_ABSENT", "subject": "opportunity_id"}]) + "</h2>")
    out = [title]

    row_blockers = list(opp.get("row_blockers") or [])
    dep_blockers = dependency_blockers(opp.get("required_inputs"), inputs)
    base_blockers: list[dict] = []
    if not bound:
        base_blockers.append({"reason": "OUTPUT_UNBOUND", "subject": "model binding"})
    base_blockers.extend(dep_blockers)
    if base_blockers:
        out.append("<table><tr>" + _warning_cell(base_blockers) + "</tr></table>")

    ladder_eval = evaluate_ladder((opp.get("evidence_ladder") or {}).get("held_labels"))
    out.append("<h3>Evidence ladder (M00 section 3, verbatim label set)</h3>")
    out.append(_render_ladder(ladder_eval))

    ew = evaluate_execution_warnings(opp.get("execution_warnings"))
    out.append(_render_execution_warnings(ew))

    actionable = (
        not base_blockers
        and ladder_eval["production_eligible_valid"]
        and not ladder_eval["unknown"]
        and ew["execution_ready"]
    )
    badge = "<span class='actionable'>ACTIONABLE</span>" if actionable else "<span class='informational'>NOT ACTIONABLE / INFORMATIONAL ONLY</span>"
    out.append(f"<p>{badge}</p>")

    # -- consensus -----------------------------------------------------------------
    out.append("<h3>Consensus</h3>")
    out.append(_render_consensus(opp.get("consensus") or {}, as_of, row_blockers + base_blockers))

    # -- cross-book quotes -----------------------------------------------------------
    out.append("<h3>Cross-book quotes</h3>")
    out.append(_render_quotes(opp.get("cross_book_quotes") or [], as_of, row_blockers + base_blockers))

    # -- stale-book residuals ---------------------------------------------------------
    out.append("<h3>Stale-book residuals (book quote &minus; consensus)</h3>")
    out.append(_render_residuals(opp.get("cross_book_quotes") or [], opp.get("consensus") or {}, as_of, row_blockers + base_blockers))

    # -- line / price history -----------------------------------------------------
    out.append("<h3>Line / price history</h3>")
    out.append(_render_line_history(opp.get("line_history") or []))

    # -- information events --------------------------------------------------------
    out.append("<h3>Information events</h3>")
    out.append(_render_information_events(opp.get("information_events") or []))

    # -- our projection --------------------------------------------------------------
    out.append("<h3>Our projection</h3>")
    proj = opp.get("our_projection") or {}
    pres = resolve_timestamped_cell(
        proj.get("value"), as_of, proj.get("as_of"), proj.get("max_age_seconds"),
        base_blockers, row_blockers,
    )
    out.append(f"<table><tr>{_cell(pres, proj.get('units'), proj.get('as_of'))}</tr></table>")

    # -- edge estimate + uncertainty --------------------------------------------------
    out.append("<h3>Edge estimate</h3>")
    edge = opp.get("edge_estimate") or {}
    eres = resolve_timestamped_cell(
        edge.get("value"), as_of, edge.get("as_of"), edge.get("max_age_seconds"),
        base_blockers, row_blockers,
    )
    unc = edge.get("uncertainty") or {}
    lo = resolve_timestamped_cell(unc.get("lo"), as_of, edge.get("as_of"), edge.get("max_age_seconds"), base_blockers, row_blockers)
    hi = resolve_timestamped_cell(unc.get("hi"), as_of, edge.get("as_of"), edge.get("max_age_seconds"), base_blockers, row_blockers)
    edge_row = [f"<td>edge</td>{_cell(eres, edge.get('units'), edge.get('as_of'))}"]
    if lo["kind"] == "value" and hi["kind"] == "value":
        level = unc.get("level")
        lvl = f" <span class='u'>{_e(level)}</span>" if level else ""
        edge_row.append("<td class='num'>" + _fmt_number(lo["value"]) + " &ndash; " + _fmt_number(hi["value"]) + lvl + "</td>")
    else:
        edge_row.append(_warning_cell((lo["reasons"] if lo["kind"] == "warning" else hi["reasons"])))
    out.append("<table><tr><th>metric</th><th>value</th><th>uncertainty interval</th></tr>"
               f"<tr>{''.join(edge_row)}</tr></table>")

    # -- opportunity age -----------------------------------------------------------
    out.append("<h3>Opportunity age</h3>")
    out.append(_render_opportunity_age(opp.get("opportunity_first_detected_at"), as_of))

    for note in opp.get("notes") or []:
        out.append(f"<p class='meta'>note: {_e(note)}</p>")
    return "".join(out)


def _render_consensus(consensus: dict, as_of: Any, base_blockers: list[dict]) -> str:
    tier = consensus.get("tier")
    m00 = evaluate_m00_use(tier, consensus.get("m00_use_class"), consensus.get("m00_caveat_text"))
    if not m00["ok"]:
        reasons = [{"reason": c, "subject": f"consensus tier={tier}"} for c in m00["codes"]]
        return f"<table><tr>{_warning_cell(reasons)}</tr></table>"
    blockers = list(base_blockers)
    res = resolve_timestamped_cell(
        consensus.get("value"), as_of, consensus.get("as_of"), consensus.get("max_age_seconds"), blockers,
    )
    cell = _cell(res, consensus.get("units"), consensus.get("as_of"))
    caveat = f"<p class='meta'>{_e(m00['caveat_text'])}</p>" if m00["caveat_text"] else ""
    method = consensus.get("method")
    n = consensus.get("n_books")
    meta = f"<p class='meta'>method: {_e(method or 'unstated')}; n_books: {_e(n if n is not None else 'unstated')}; tier: {_e(tier or 'unstated')}</p>"
    return f"<table><tr>{cell}</tr></table>{meta}{caveat}"


def _render_quotes(quotes: list, as_of: Any, base_blockers: list[dict]) -> str:
    if not quotes:
        return "<table><tr>" + _warning_cell([{"reason": "VALUE_ABSENT", "subject": "no cross-book quotes supplied"}]) + "</tr></table>"
    head = "<tr><th>book</th><th>price</th><th>line</th><th>freshness</th></tr>"
    body = []
    for q in quotes:
        tier = q.get("tier")
        m00 = evaluate_m00_use(tier, q.get("m00_use_class"), q.get("m00_caveat_text"))
        book = _e(q.get("book") or "<unnamed book>")
        if not m00["ok"]:
            reasons = [{"reason": c, "subject": f"{book} tier={tier}"} for c in m00["codes"]]
            body.append(f"<tr><td>{book}</td>{_warning_cell(reasons, colspan=3)}</tr>")
            continue
        pres = resolve_timestamped_cell(q.get("price"), as_of, q.get("captured_at"), q.get("max_age_seconds"), list(base_blockers))
        lres = resolve_timestamped_cell(q.get("line"), as_of, q.get("captured_at"), q.get("max_age_seconds"), list(base_blockers))
        body.append(
            f"<tr><td>{book}</td>{_cell(pres, None, q.get('captured_at'))}{_cell(lres, None, q.get('captured_at'))}"
            f"<td class='age'>captured {_e(q.get('captured_at') or 'unstated')}, limit {_e(q.get('max_age_seconds'))}s</td></tr>"
        )
    return f"<table>{head}{''.join(body)}</table>"


def _render_residuals(quotes: list, consensus: dict, as_of: Any, base_blockers: list[dict]) -> str:
    cons_tier = consensus.get("tier")
    cons_m00 = evaluate_m00_use(cons_tier, consensus.get("m00_use_class"), consensus.get("m00_caveat_text"))
    cons_res = None
    if cons_m00["ok"]:
        cons_res = resolve_timestamped_cell(
            consensus.get("value"), as_of, consensus.get("as_of"), consensus.get("max_age_seconds"), list(base_blockers),
        )
    if not quotes:
        return "<table><tr>" + _warning_cell([{"reason": "VALUE_ABSENT", "subject": "no cross-book quotes supplied"}]) + "</tr></table>"
    head = "<tr><th>book</th><th>book status</th><th>residual</th></tr>"
    body = []
    for q in quotes:
        book = _e(q.get("book") or "<unnamed book>")
        tier = q.get("tier")
        m00 = evaluate_m00_use(tier, q.get("m00_use_class"), q.get("m00_caveat_text"))
        if not m00["ok"]:
            body.append(f"<tr><td>{book}</td><td class='bad'>CONTRACT_VIOLATION</td>"
                        + _warning_cell([{"reason": c, "subject": "T2 book quote"} for c in m00["codes"]]) + "</tr>")
            continue
        pres = resolve_timestamped_cell(q.get("price"), as_of, q.get("captured_at"), q.get("max_age_seconds"), list(base_blockers))
        status = "OK" if pres["kind"] == "value" else "STALE/MISSING"
        cls = "ok" if pres["kind"] == "value" else "bad"
        if pres["kind"] == "value" and cons_res is not None and cons_res["kind"] == "value":
            residual = _number_cell(pres["value"] - cons_res["value"])
        else:
            reasons = (pres["reasons"] if pres["kind"] == "warning" else
                       (cons_res["reasons"] if cons_res is not None and cons_res["kind"] == "warning" else
                        [{"reason": "VALUE_ABSENT", "subject": "consensus unavailable"}]))
            residual = _warning_cell(reasons)
        body.append(f"<tr><td>{book}</td><td class='{cls}'>{status}</td>{residual}</tr>")
    return f"<table>{head}{''.join(body)}</table>"


def _render_line_history(points: list) -> str:
    if not points:
        return "<table><tr>" + _warning_cell([{"reason": "VALUE_ABSENT", "subject": "no line history supplied"}]) + "</tr></table>"
    head = "<tr><th>captured at</th><th>value</th><th>tier</th></tr>"
    body = []
    for p in points:
        tier = p.get("tier")
        m00 = evaluate_m00_use(tier, p.get("m00_use_class"), p.get("m00_caveat_text"))
        ts = _e(p.get("captured_at") or "unstated")
        if tier == "T2":
            # A point-in-time series is inherently a timing use; C.2 prohibits ANY
            # open/close or line-movement use of the T2 archive without exception,
            # regardless of use-class or caveat correctness. A T2 point never appears in
            # this series as a number.
            body.append(f"<tr><td>{ts}</td>{_warning_cell([{'reason': 'CONTRACT_VIOLATION', 'subject': 'section C.2 prohibits any line-movement/timing use of the T2 archive without exception'}], colspan=2)}</tr>")
            continue
        val = p.get("value")
        vres = resolve_cell(val, [])
        cell = _cell(vres, None, p.get("captured_at"))
        body.append(f"<tr><td>{ts}</td>{cell}<td>{_e(tier or 'unstated')}</td></tr>")
    return f"<table>{head}{''.join(body)}</table>"


def _render_information_events(events: list) -> str:
    if not events:
        return "<table><tr>" + _warning_cell([{"reason": "VALUE_ABSENT", "subject": "no information events supplied"}]) + "</tr></table>"
    head = "<tr><th>observed at</th><th>type</th><th>source</th><th>tier</th><th>detail</th></tr>"
    body = []
    for ev in events:
        observed = ev.get("observed_at")
        tier = ev.get("tier")
        row = (f"<tr><td>{_e(observed or 'unstated')}</td><td>{_e(ev.get('type') or 'unstated')}</td>"
               f"<td>{_e(ev.get('source') or 'unstated')}</td><td>{_e(tier or 'unstated')}</td>"
               f"<td>{_e(ev.get('detail') or '')}</td></tr>")
        if not observed:
            row = f"<tr>{_warning_cell([{'reason': 'VALUE_ABSENT', 'subject': 'observed_at'}], colspan=5)}</tr>"
        body.append(row)
    return f"<table>{head}{''.join(body)}</table>"


# ------------------------------------------------------------------------- top level
def render_payload(payload: Any) -> str:
    """Pure function: view payload dict -> HTML string. No I/O, no model, no defaults."""
    parts = [f"<style>{_CSS}</style>", f"<div class='banner'>{_e(EPISTEMIC_BANNER)}</div>"]

    if not isinstance(payload, dict):
        parts.append("<table><tr>" + _warning_cell(
            [{"reason": "PAYLOAD_UNREADABLE", "subject": "payload is not an object"}]) + "</tr></table>")
        return "".join(parts)

    parts.append(f"<h1>{_e(payload.get('title') or 'Market screen')}</h1>")
    schema = payload.get("schema")
    if schema != VIEW_SCHEMA:
        parts.append("<table><tr>" + _warning_cell(
            [{"reason": "PAYLOAD_UNREADABLE", "subject": f"schema {schema!r} is not {VIEW_SCHEMA}"}]) + "</tr></table>")

    as_of = payload.get("as_of")
    src = (payload.get("audit") or {}).get("source")
    parts.append(
        "<p class='meta'>payload <code>{}</code> &middot; as of <code>{}</code> &middot; source <code>{}</code></p>".format(
            _e((payload.get("audit") or {}).get("payload_id") or "unidentified"),
            _e(as_of or "unstated"),
            _e(src or "unstated"),
        )
    )

    parts.append("<h2>Mode</h2>")
    parts.append(_render_mode_badge(payload))

    binding = model_binding(payload)
    inputs = evaluate_inputs(payload)

    parts.append("<h2>Output binding</h2><table>")
    version = binding["version"]
    if isinstance(version, str) and version.strip():
        parts.append(f"<tr><th>model version</th><td><code>{_e(version)}</code></td></tr>")
    else:
        parts.append("<tr><th>model version</th>" + _warning_cell(
            [{"reason": "OUTPUT_UNBOUND", "subject": "no model version in payload"}]) + "</tr>")
    if binding["artifact_sha256"]:
        digests = "<br>".join(f"<code>{_e(k)}</code> &nbsp; <code>{_e(v)}</code>" for k, v in sorted(binding["artifact_sha256"].items()))
        parts.append(f"<tr><th>artifact digests</th><td>{digests}</td></tr>")
    else:
        parts.append("<tr><th>artifact digests</th>" + _warning_cell(
            [{"reason": "OUTPUT_UNBOUND", "subject": "no artifact digests in payload"}]) + "</tr>")
    parts.append("</table>")

    parts.append("<h2>Input freshness</h2>")
    if not inputs:
        parts.append("<table><tr>" + _warning_cell([{"reason": "INPUT_MISSING", "subject": "the payload declares no inputs"}]) + "</tr></table>")
    else:
        head = "<tr><th>input</th><th>state</th><th>captured at</th><th>age (s)</th><th>max age (s)</th><th>tier</th><th>detail</th></tr>"
        body = []
        for iid in sorted(inputs):
            r = inputs[iid]
            cls = "ok" if r["state"] == "OK" else "bad"
            age = f"{r['age_seconds']:.0f}" if _is_finite_number(r["age_seconds"]) else "&mdash;"
            maxage = f"{r['max_age_seconds']:.0f}" if _is_finite_number(r["max_age_seconds"]) else "&mdash;"
            detail = r["detail"] or (REASONS.get(r["reason"], "") if r["reason"] else "")
            body.append(f"<tr><td>{_e(r['label'])} <code>{_e(iid)}</code></td><td class='{cls}'>{_e(r['state'])}</td>"
                        f"<td>{_e(r['captured_at']) or '&mdash;'}</td><td class='age'>{age}</td><td class='age'>{maxage}</td>"
                        f"<td>{_e(r.get('tier') or 'unstated')}</td><td>{_e(detail)}</td></tr>")
        parts.append(f"<table>{head}{''.join(body)}</table>")

    opps = payload.get("opportunities") or []
    if not opps:
        parts.append("<h2>Opportunities</h2><table><tr>" + _warning_cell(
            [{"reason": "VALUE_ABSENT", "subject": "the payload carries no opportunities"}]) + "</tr></table>")
    for opp in opps:
        parts.append(_render_opportunity(opp, inputs, binding["bound"], as_of))

    parts.append(
        "<p class='footer'>Rendered by market_view.py from a payload. Every number on this "
        "page is a value carried in that payload, matched to its own timestamp per "
        "amendment 4; nothing here was computed, polled, or estimated live. A cell that "
        "cannot show a timestamp shows NO_TIMESTAMP instead of a number. No order is "
        "placed by this shell in any mode.</p>"
    )
    return "".join(parts)


# ------------------------------------------------------------------------ main
def main() -> int:
    RENDERED.mkdir(exist_ok=True)
    if not FIXTURES.is_dir():
        print(f"FAIL: no fixtures directory at {FIXTURES}")
        return 1
    import json
    paths = sorted(FIXTURES.glob("*.json"))
    if not paths:
        print("FAIL: no fixtures found")
        return 1
    for p in paths:
        payload = json.loads(p.read_text(encoding="utf-8"))
        out = RENDERED / (p.stem + ".html")
        out.write_text(render_payload(payload), encoding="utf-8")
        print(f"  rendered  {p.name} -> rendered/{out.name}")
    print(f"{len(paths)} fixture(s) rendered")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
