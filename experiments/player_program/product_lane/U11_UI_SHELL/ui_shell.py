#!/usr/bin/env python3
"""ui_shell.py — model-agnostic UI shell, rendered from a view payload.

This module is a PRODUCT SCAFFOLD. It renders static HTML from a JSON payload and does
nothing else. It fits nothing, loads no model, reads no artifact, opens no socket and
imports nothing from the scientific lanes. Everything it displays is a value carried in
the payload it was handed.

Three invariants are the whole point of the file, and TESTS.py asserts each of them:

1. **Model-agnostic.** No model or estimator identifier appears anywhere in this source.
   Model version, artifact hashes and promotion status are payload *data*, rendered as
   opaque strings. Swapping the producing model changes the payload, never this file.

2. **Absence renders as a warning, never as a number.** Every projection, interval,
   market line, delta and component number reaches the page through :func:`_fmt_number`
   and only after :func:`resolve_cell` has returned a ``value`` verdict. Every path that
   is missing, null, non-finite, non-numeric, stale, unbound, blocked by a failed job or
   blocked by a missing input returns a WARNING cell instead. There is no default, no
   fallback, no last-known-good and no zero. (The input-freshness table also prints ages
   in seconds; those are diagnostics computed from timestamps that are present, are
   carried in ``td.age`` rather than ``td.num``, and are not model output.)

3. **Fixtures or frozen outputs only.** The renderer is a pure function of the payload
   dict. The only filesystem access in the module is in ``main()``, which reads fixture
   JSON from this node's own ``fixtures/`` directory and writes HTML to its own
   ``rendered/`` directory.

Run::

    python experiments/player_program/product_lane/U11_UI_SHELL/ui_shell.py
"""
from __future__ import annotations

import datetime as _dt
import html
import json
import math
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
RENDERED = HERE / "rendered"

VIEW_SCHEMA = "u11_view_payload/1"

# The epistemic banner is rendered on every page, unconditionally, regardless of payload
# content. It is not payload-driven, so no payload can suppress it.
EPISTEMIC_BANNER = (
    "PRODUCT SCAFFOLD built against fixtures. Carries no scientific claim and must not "
    "imply a model has been promoted."
)

# Reason codes. The UI shows the code and its human text; it never invents a value to
# stand in for a suppressed one.
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
}


# --------------------------------------------------------------------- helpers
def _e(x: Any) -> str:
    return html.escape("" if x is None else str(x), quote=True)


def _parse_ts(ts: Any) -> _dt.datetime | None:
    if not isinstance(ts, str):
        return None
    try:
        return _dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def _is_finite_number(v: Any) -> bool:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return False
    return math.isfinite(float(v))


# ------------------------------------------------------------- freshness model
def evaluate_inputs(payload: dict) -> dict[str, dict]:
    """Classify every declared input as ok / stale / missing / failed.

    Staleness is measured against ``payload['as_of']``. An input whose timestamp or
    max-age cannot be interpreted is classified MISSING, never OK — an unreadable
    freshness claim is treated as no freshness claim.
    """
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
            "detail": item.get("detail") or "",
        }
        declared = str(item.get("status") or "").lower()
        if declared == "failed":
            rec["state"] = "FAILED"
            rec["reason"] = "INPUT_FAILED"
            out[iid] = rec
            continue
        if declared == "missing" or item.get("captured_at") in (None, ""):
            rec["state"] = "MISSING"
            rec["reason"] = "INPUT_MISSING"
            out[iid] = rec
            continue

        captured = _parse_ts(item.get("captured_at"))
        max_age = item.get("max_age_seconds")
        if captured is None or as_of is None or not _is_finite_number(max_age):
            # Cannot evaluate freshness -> not OK. Fail closed.
            rec["state"] = "MISSING"
            rec["reason"] = "INPUT_MISSING"
            rec["detail"] = (rec["detail"] + " freshness not evaluable").strip()
            out[iid] = rec
            continue

        age = (as_of - captured).total_seconds()
        rec["age_seconds"] = age
        if age > float(max_age) or age < 0:
            rec["state"] = "STALE"
            rec["reason"] = "INPUT_STALE"
        else:
            rec["state"] = "OK"
            rec["reason"] = None
        out[iid] = rec
    return out


def model_binding(payload: dict) -> dict:
    """Model identity as carried by the payload. No identifier is supplied by this code.

    Outputs may be shown only when they are bound to BOTH a model version and at least
    one artifact digest. An unbound payload suppresses every number on the page.
    """
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
    """Reasons drawn from a declared dependency list."""
    blockers: list[dict] = []
    for iid in required or []:
        rec = inputs.get(str(iid))
        if rec is None:
            blockers.append({"reason": "INPUT_UNDECLARED", "subject": str(iid)})
        elif rec["state"] != "OK":
            blockers.append({"reason": rec["reason"], "subject": rec["label"]})
    return blockers


def game_blockers(game: dict, inputs: dict[str, dict], bound: bool) -> list[dict]:
    """Every reason this game's numbers must be suppressed."""
    blockers: list[dict] = []
    if not bound:
        blockers.append({"reason": "OUTPUT_UNBOUND", "subject": "model binding"})
    blockers.extend(dependency_blockers(game.get("required_inputs"), inputs))
    return blockers


def resolve_cell(value: Any, blockers: list[dict], row_blockers: list[str] | None = None) -> dict:
    """The single decision point between showing a number and showing a warning.

    Returns ``{"kind": "value", "value": float}`` or ``{"kind": "warning", "reasons": [...]}``.
    Never both, never a substituted number.
    """
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
        # Deliberately does NOT echo the rejected value: a rejected number must not appear
        # on the page in any form, not even inside its own warning.
        return {"kind": "warning", "reasons": [{"reason": "VALUE_NOT_FINITE", "subject": "non-finite float"}]}
    return {"kind": "value", "value": float(value)}


# ------------------------------------------------------------------ HTML cells
NUMBER_MARKER = 'class="v"'


def _fmt_number(v: float, signed: bool = False) -> str:
    """The ONLY function in this module that formats a number into page text.

    Every emitted number is wrapped in ``NUMBER_MARKER`` so that a test can count the
    numbers on a page exactly, wherever they appear.
    """
    return f'<span {NUMBER_MARKER}>{v:+.3f}</span>' if signed else f'<span {NUMBER_MARKER}>{v:.3f}</span>'


def _number_cell(v: float, units: str | None = None) -> str:
    suffix = f" <span class='u'>{_e(units)}</span>" if units else ""
    return f"<td class='num'>{_fmt_number(v)}{suffix}</td>"


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


def _cell(resolved: dict, units: str | None = None) -> str:
    if resolved["kind"] == "value":
        return _number_cell(resolved["value"], units)
    return _warning_cell(resolved["reasons"])


# ------------------------------------------------------------------- rendering
_CSS = """
body{font:14px/1.45 -apple-system,Segoe UI,Roboto,sans-serif;margin:0;padding:24px;
 background:#fbfbfc;color:#16181d}
h1{font-size:19px;margin:0 0 4px} h2{font-size:15px;margin:26px 0 8px}
.banner{background:#1d2330;color:#fff;padding:10px 14px;border-radius:6px;margin-bottom:16px;
 font-weight:600;letter-spacing:.01em}
.meta{color:#5b6472;font-size:12px;margin-bottom:14px}
table{border-collapse:collapse;width:100%;background:#fff;margin-bottom:10px}
th,td{border:1px solid #e3e6ea;padding:6px 9px;text-align:left;vertical-align:top}
th{background:#f2f4f7;font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.04em}
td.num,td.age{text-align:right;font-variant-numeric:tabular-nums}
td.age{color:#5b6472}
td.num .u{color:#77808f;font-size:11px}
td.warn{background:#fff5f5;color:#8a1c1c}
.badge{display:inline-block;background:#c0392b;color:#fff;font-size:10px;font-weight:700;
 padding:1px 6px;border-radius:3px;margin-right:6px;letter-spacing:.06em}
.ok{color:#1c7a3c;font-weight:600}.bad{color:#8a1c1c;font-weight:600}
code{font:12px/1.4 ui-monospace,Consolas,monospace;color:#3c4351;word-break:break-all}
.footer{color:#77808f;font-size:11px;margin-top:26px;border-top:1px solid #e3e6ea;padding-top:10px}
"""


def _render_model_block(binding: dict) -> str:
    rows = []
    version = binding["version"]
    if isinstance(version, str) and version.strip():
        rows.append(f"<tr><th>model version</th><td><code>{_e(version)}</code></td></tr>")
    else:
        rows.append("<tr><th>model version</th>" + _warning_cell(
            [{"reason": "OUTPUT_UNBOUND", "subject": "no model version in payload"}]) + "</tr>")

    if binding["artifact_sha256"]:
        digests = "<br>".join(
            f"<code>{_e(k)}</code> &nbsp; <code>{_e(v)}</code>"
            for k, v in sorted(binding["artifact_sha256"].items())
        )
        rows.append(f"<tr><th>artifact digests</th><td>{digests}</td></tr>")
    else:
        rows.append("<tr><th>artifact digests</th>" + _warning_cell(
            [{"reason": "OUTPUT_UNBOUND", "subject": "no artifact digests in payload"}]) + "</tr>")

    status = binding["promotion_status"]
    if isinstance(status, str) and status.strip():
        rows.append(f"<tr><th>promotion status (as stated by payload)</th><td>{_e(status)}</td></tr>")
    else:
        rows.append("<tr><th>promotion status (as stated by payload)</th>" + _warning_cell(
            [{"reason": "VALUE_ABSENT", "subject": "promotion status"}]) + "</tr>")
    return "<h2>Output binding</h2><table>" + "".join(rows) + "</table>"


def _render_inputs(inputs: dict[str, dict]) -> str:
    if not inputs:
        return "<h2>Input freshness</h2><table><tr>" + _warning_cell(
            [{"reason": "INPUT_MISSING", "subject": "the payload declares no inputs"}]) + "</tr></table>"
    head = ("<tr><th>input</th><th>state</th><th>captured at</th><th>age (s)</th>"
            "<th>max age (s)</th><th>detail</th></tr>")
    body = []
    for iid in sorted(inputs):
        r = inputs[iid]
        state = r["state"]
        cls = "ok" if state == "OK" else "bad"
        age = f"{r['age_seconds']:.0f}" if _is_finite_number(r["age_seconds"]) else "&mdash;"
        maxage = f"{r['max_age_seconds']:.0f}" if _is_finite_number(r["max_age_seconds"]) else "&mdash;"
        detail = r["detail"] or (REASONS.get(r["reason"], "") if r["reason"] else "")
        body.append(
            f"<tr><td>{_e(r['label'])} <code>{_e(iid)}</code></td>"
            f"<td class='{cls}'>{_e(state)}</td>"
            f"<td>{_e(r['captured_at']) or '&mdash;'}</td>"
            f"<td class='age'>{age}</td><td class='age'>{maxage}</td>"
            f"<td>{_e(detail)}</td></tr>"
        )
    return "<h2>Input freshness</h2><table>" + head + "".join(body) + "</table>"


def _render_game(game: dict, inputs: dict[str, dict], bound: bool) -> str:
    blockers = game_blockers(game, inputs, bound)
    gid = game.get("game_id")
    title = (f"<h2>Game <code>{_e(gid)}</code> &mdash; {_e(game.get('label') or '')}</h2>"
             if gid else "<h2>Game " + _warning_cell(
                 [{"reason": "VALUE_ABSENT", "subject": "game_id"}]) + "</h2>")

    out = [title]
    if blockers:
        out.append("<table><tr>" + _warning_cell(blockers) + "</tr></table>")

    head = ("<tr><th>entity</th><th>projection</th><th>interval</th>"
            "<th>market</th><th>vs market</th><th>components</th></tr>")
    body = []
    rows = game.get("rows") or []
    if not rows:
        body.append("<tr>" + _warning_cell(
            [{"reason": "VALUE_ABSENT", "subject": "no rows supplied for this game"}], colspan=6) + "</tr>")
    for row in rows:
        rb = row.get("row_blockers") or []
        # A row may declare its own dependencies. They are evaluated here, by the shell,
        # against the same freshness rules — never trusted to the producer.
        row_blk = blockers + dependency_blockers(row.get("required_inputs"), inputs)
        proj = (row.get("projection") or {})
        pres = resolve_cell(proj.get("value"), row_blk, rb)
        units = proj.get("units")

        unc = row.get("uncertainty") or {}
        lo = resolve_cell(unc.get("lo"), row_blk, rb)
        hi = resolve_cell(unc.get("hi"), row_blk, rb)
        if lo["kind"] == "value" and hi["kind"] == "value":
            level = unc.get("level")
            lvl = f" <span class='u'>{_e(level)}</span>" if level else ""
            interval = ("<td class='num'>" + _fmt_number(lo["value"]) + " &ndash; "
                        + _fmt_number(hi["value"]) + lvl + "</td>")
        else:
            interval = _warning_cell(
                (lo["reasons"] if lo["kind"] == "warning" else hi["reasons"]))

        mkt = row.get("market") or {}
        mres = resolve_cell(mkt.get("line"), row_blk, rb)
        market_cell = _cell(mres, mkt.get("source"))

        if pres["kind"] == "value" and mres["kind"] == "value":
            delta = _number_cell(pres["value"] - mres["value"])
        else:
            reasons = (pres["reasons"] if pres["kind"] == "warning" else mres["reasons"])
            delta = _warning_cell(reasons)

        comps = row.get("components")
        if not comps:
            comp_cell = _warning_cell([{"reason": "VALUE_ABSENT", "subject": "component explanation"}])
        else:
            bits = []
            for c in comps:
                cres = resolve_cell(c.get("contribution"), row_blk, rb)
                if cres["kind"] == "value":
                    bits.append(f"{_e(c.get('name'))} " + _fmt_number(cres["value"], signed=True))
                else:
                    code = cres["reasons"][0].get("reason", "PAYLOAD_UNREADABLE")
                    bits.append(f"{_e(c.get('name'))} <span class='badge'>WARNING</span> {_e(code)}")
            comp_cell = "<td>" + "; ".join(bits) + "</td>"

        ent = row.get("entity_label") or row.get("entity_id")
        ent_cell = (f"<td>{_e(ent)}</td>" if ent else
                    _warning_cell([{"reason": "VALUE_ABSENT", "subject": "entity identity"}]))
        body.append("<tr>" + ent_cell + _cell(pres, units) + interval + market_cell
                    + delta + comp_cell + "</tr>")

    out.append("<table>" + head + "".join(body) + "</table>")
    for note in game.get("notes") or []:
        out.append(f"<p class='meta'>note: {_e(note)}</p>")
    return "".join(out)


def render_payload(payload: Any) -> str:
    """Pure function: view payload dict -> HTML string. No I/O, no model, no defaults."""
    parts = [f"<style>{_CSS}</style>", f"<div class='banner'>{_e(EPISTEMIC_BANNER)}</div>"]

    if not isinstance(payload, dict):
        parts.append("<table><tr>" + _warning_cell(
            [{"reason": "PAYLOAD_UNREADABLE", "subject": "payload is not an object"}]) + "</tr></table>")
        return "".join(parts)

    parts.append(f"<h1>{_e(payload.get('title') or 'Projection view')}</h1>")
    schema = payload.get("schema")
    if schema != VIEW_SCHEMA:
        parts.append("<table><tr>" + _warning_cell(
            [{"reason": "PAYLOAD_UNREADABLE",
              "subject": f"schema {schema!r} is not {VIEW_SCHEMA}"}]) + "</tr></table>")

    src = (payload.get("audit") or {}).get("source")
    parts.append(
        "<p class='meta'>payload <code>{}</code> &middot; as of <code>{}</code> &middot; "
        "source <code>{}</code></p>".format(
            _e((payload.get("audit") or {}).get("payload_id") or "unidentified"),
            _e(payload.get("as_of") or "unstated"),
            _e(src or "unstated"),
        )
    )

    binding = model_binding(payload)
    inputs = evaluate_inputs(payload)
    parts.append(_render_model_block(binding))
    parts.append(_render_inputs(inputs))

    games = payload.get("games") or []
    if not games:
        parts.append("<h2>Games</h2><table><tr>" + _warning_cell(
            [{"reason": "VALUE_ABSENT", "subject": "the payload carries no games"}]) + "</tr></table>")
    for game in games:
        parts.append(_render_game(game, inputs, binding["bound"]))

    parts.append(
        "<p class='footer'>Rendered by ui_shell.py from a payload. Every number on this page "
        "is a value carried in that payload; nothing here was computed by a model, and nothing "
        "here asserts that any model has been promoted. Suppressed cells are shown as WARNING "
        "with a reason code and are never replaced by an estimate, a default or a last-known "
        "value.</p>"
    )
    return "".join(parts)


# ------------------------------------------------------------------------ main
def main() -> int:
    RENDERED.mkdir(exist_ok=True)
    if not FIXTURES.is_dir():
        print(f"FAIL: no fixtures directory at {FIXTURES}")
        return 1
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
