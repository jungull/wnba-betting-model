"""
build_shell.py -- builds shell.html, a static rendering of the market screen shell against
the fixtures in fixtures/*.json, using the rules in render.py.

PRODUCT SCAFFOLD built against fixtures. Carries no market claim and must not imply that
any edge, signal or tradable opportunity exists: fixtures render as fixtures.

This script performs NO network I/O and opens NO socket. It reads local fixture JSON files,
runs them through render.py, and writes a single self-contained static HTML file. There is no
client-side fetch/XHR/WebSocket in the emitted page -- all values are baked in at build time,
which is the only way "fixtures only; no live wiring" can be a structurally enforced property
rather than a promise. Run: `python build_shell.py` from this directory.
"""

from __future__ import annotations

import json
import html as html_lib
from datetime import datetime, timezone
from pathlib import Path

import render as R

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"


def load(name: str):
    with open(FIXTURES / name, "r", encoding="utf-8") as f:
        return json.load(f)


def now_reference() -> datetime:
    manifest = load("manifest.json")
    return datetime.fromisoformat(manifest["fixture_now_reference"].replace("Z", "+00:00"))


def esc(x) -> str:
    return html_lib.escape(str(x))


def freshness_stamp_html(freshness: dict) -> str:
    return (
        f'<span class="freshness freshness-{esc(freshness["status"]).lower()}">'
        f'retrieval_ts={esc(freshness["retrieval_ts"])} '
        f'age_s={esc(round(freshness["age_seconds"], 1)) if freshness["age_seconds"] is not None else "n/a"} '
        f'bound_s={esc(freshness["max_staleness_bound_seconds"])} '
        f'status={esc(freshness["status"])}</span>'
    )


def render_consensus_section(now: datetime) -> str:
    c = load("consensus.json")
    row = R.render_numeric_signal(
        label="consensus_no_vig_prob_over",
        value=c.get("consensus_no_vig_prob_over"),
        retrieval_ts=c.get("retrieval_ts"),
        max_staleness_bound_seconds=c.get("max_staleness_bound_seconds"),
        now=now,
        evidence_labels_held=c.get("evidence_labels_held"),
    )
    if row["display"] == "warning":
        body = f'<div class="warning">WARNING: {esc(row["reason"])}</div>{freshness_stamp_html(row["freshness"])}'
    else:
        body = (
            f'<div class="value">{esc(row["value"])}</div>'
            f'<div class="tier">tier={esc(c.get("tier"))} n_books={esc(c.get("n_books_contributing"))}</div>'
            f'{freshness_stamp_html(row["freshness"])}'
            f'<div class="actionable">actionable={esc(row["actionable"])}</div>'
        )
    return f'<section class="card"><h2>Consensus</h2>{body}</section>'


def render_cross_book_section(now: datetime) -> str:
    data = load("cross_book_quotes.json")
    rows_html = []
    for q in data["quotes"]:
        row = R.render_numeric_signal(
            label=f'{q["book"]} over',
            value=q.get("price_over_american"),
            retrieval_ts=q.get("retrieval_ts"),
            max_staleness_bound_seconds=q.get("max_staleness_bound_seconds"),
            now=now,
        )
        if row["display"] == "warning":
            rows_html.append(
                f'<tr><td>{esc(q["book"])}</td><td class="warning">WARNING: {esc(row["reason"])}</td>'
                f'<td>{freshness_stamp_html(row["freshness"])}</td></tr>'
            )
        else:
            rows_html.append(
                f'<tr><td>{esc(q["book"])}</td><td>{esc(row["value"])}</td>'
                f'<td>{freshness_stamp_html(row["freshness"])}</td></tr>'
            )
    table = (
        '<table><thead><tr><th>Book</th><th>Price (over, american)</th><th>Freshness</th></tr></thead>'
        f'<tbody>{"".join(rows_html)}</tbody></table>'
    )
    return f'<section class="card"><h2>Cross-book quotes</h2>{table}</section>'


def render_stale_residuals_section(now: datetime) -> str:
    data = load("stale_book_residuals.json")
    rows_html = []
    for cand in data["candidates"]:
        arb_ok = R.check_reserved_arbitrage_term(cand["opportunity_class"], cand["opportunity_class"])
        rendered = R.render_reaction_time_claim(cand)
        if rendered["display"] == "UNSUPPORTABLE":
            rows_html.append(
                f'<div class="warning">UNSUPPORTABLE claim ({esc(cand["candidate_id"])}): '
                f'missing {esc(rendered["missing_fields"])}</div>'
            )
        else:
            rows_html.append(
                f'<div class="reaction-claim">'
                f'<div>{esc(cand["candidate_id"])} class={esc(cand["opportunity_class"])} '
                f'reserved_term_ok={esc(arb_ok)}</div>'
                f'<div>t=[{esc(rendered["t_lower"])}, {esc(rendered["t_upper"])}] '
                f'censor={esc(rendered["censor_type"])} tier={esc(rendered["tier"])}</div>'
                f'<div>poll_event_s={esc(rendered["poll_interval_event_seconds"])} '
                f'poll_quote_s={esc(rendered["poll_interval_quote_seconds"])}</div>'
                f'<div>vendor_latency_bound={esc(rendered["vendor_latency_bound"])}</div>'
                f'<div>clock_skew_bound={esc(rendered["clock_skew_bound"])}</div>'
                f'<div>n_trusted={esc(rendered["n_trusted"])} n_excluded={esc(rendered["n_excluded"])}</div>'
                f'<div class="actionable">actionable={esc(rendered["actionable"])}</div>'
                f'</div>'
            )
    return f'<section class="card"><h2>Stale-book residuals (reaction-time claims)</h2>{"".join(rows_html)}</section>'


def render_history_section(now: datetime) -> str:
    data = load("line_price_history.json")
    rows_html = []
    for p in data["points"]:
        row = R.render_numeric_signal(
            label=p["point_id"],
            value=p.get("price_over_american"),
            retrieval_ts=p.get("retrieval_ts"),
            max_staleness_bound_seconds=p.get("max_staleness_bound_seconds"),
            now=now,
        )
        if row["display"] == "warning":
            rows_html.append(f'<tr><td>{esc(p["point_id"])}</td><td class="warning">WARNING: {esc(row["reason"])}</td><td>{freshness_stamp_html(row["freshness"])}</td></tr>')
        else:
            rows_html.append(f'<tr><td>{esc(p["point_id"])}</td><td>{esc(row["value"])}</td><td>{freshness_stamp_html(row["freshness"])}</td></tr>')
    table = f'<table><thead><tr><th>Point</th><th>Price</th><th>Freshness</th></tr></thead><tbody>{"".join(rows_html)}</tbody></table>'
    return f'<section class="card"><h2>Line / price history ({esc(data["book"])})</h2>{table}<div class="note">{esc(data["note"])}</div></section>'


def render_events_section() -> str:
    data = load("information_events.json")
    rows_html = []
    for e in data["events"]:
        rows_html.append(
            f'<div class="event"><div>{esc(e["event_id"])} [{esc(e["event_type"])}] linkage_tier={esc(e["linkage_tier"])}</div>'
            f'<div>{esc(e["description"])}</div>'
            f'<div>event_ts={esc(e["event_ts"])} retrieval_ts={esc(e.get("retrieval_ts"))}</div></div>'
        )
    return f'<section class="card"><h2>Information events</h2>{"".join(rows_html)}</section>'


def render_projection_section(now: datetime) -> str:
    p = load("our_projection.json")
    freshness = R.compute_freshness(p.get("retrieval_ts"), p.get("max_staleness_bound_seconds"), now)
    return (
        '<section class="card"><h2>Our projection (S-FUND, frozen)</h2>'
        f'<div class="value">{esc(p["projected_value"])}</div>'
        f'<div>{esc(p["source_model"])}</div>'
        f'<div>publication_ts={esc(p["publication_ts"])} commence_ts={esc(p["commence_ts"])} '
        f'strictly_before_commence={esc(p["publication_strictly_before_commence"])}</div>'
        f'{freshness_stamp_html(freshness)}'
        f'<div class="note">{esc(p["note"])}</div></section>'
    )


def render_edge_section(now: datetime) -> str:
    data = load("edge_estimate.json")
    blocks = []
    for opp in data["opportunities"]:
        rendered = R.render_usable_edge(opp, now)
        if rendered["display"] == "warning":
            blocks.append(
                f'<div class="warning">WARNING ({esc(rendered.get("opportunity_id"))}): '
                f'{esc(rendered["reason"])} {freshness_stamp_html(rendered["freshness"])}</div>'
            )
        else:
            blocks.append(
                f'<div class="edge">{esc(rendered["opportunity_id"])} class={esc(rendered["opportunity_class"])} '
                f'usable_edge={esc(round(rendered["usable_edge"], 4))} capacity={esc(rendered["capacity_status"])} '
                f'{freshness_stamp_html(rendered["freshness"])} '
                f'<span class="actionable">actionable={esc(rendered["actionable"])}</span></div>'
            )
    return f'<section class="card"><h2>Edge estimate + uncertainty</h2>{"".join(blocks)}</section>'


def render_age_section(now: datetime) -> str:
    data = load("opportunity_age.json")
    blocks = []
    for opp in data["opportunities"]:
        rendered = R.render_opportunity_age(opp, now)
        if rendered["display"] == "warning":
            blocks.append(
                f'<div class="warning">WARNING ({esc(rendered.get("opportunity_id"))}): '
                f'{esc(rendered["reason"])} {freshness_stamp_html(rendered["freshness"])}</div>'
            )
        else:
            blocks.append(
                f'<div class="age">{esc(rendered["opportunity_id"])} age_interval_s='
                f'[{esc(round(rendered["age_lower_seconds"], 1))}, {esc(round(rendered["age_upper_seconds"], 1))}] '
                f'poll_grid_s={esc(rendered["poll_grid_seconds"])} '
                f'{freshness_stamp_html(rendered["freshness"])}</div>'
            )
    return f'<section class="card"><h2>Opportunity age</h2>{"".join(blocks)}</section>'


def render_execution_warnings_section() -> str:
    data = load("execution_warnings.json")
    checklist = R.render_hard_risk_control_checklist(data)
    rows_html = "".join(
        f'<tr class="{esc(r["display"])}"><td>{esc(r["control"])}</td><td>{esc(r["satisfied"])}</td></tr>'
        for r in checklist["rows"]
    )
    return (
        '<section class="card"><h2>Execution warnings (hard risk controls)</h2>'
        f'<table><thead><tr><th>Control</th><th>Satisfied</th></tr></thead><tbody>{rows_html}</tbody></table>'
        f'<div class="note">all_controls_present={esc(checklist["all_controls_present"])} '
        f'any_satisfied={esc(checklist["any_satisfied"])} -- non-SHADOW execution is not available in this scaffold.</div>'
        '</section>'
    )


def render_mode_badge_section() -> str:
    data = load("mode_state.json")
    blocks = []
    for scenario in data["scenarios"]:
        badge = R.render_mode_badge(scenario)
        warn = f' <span class="warning">{esc(badge["warning"])}</span>' if badge["warning"] else ""
        blocks.append(
            f'<div class="mode-scenario">scenario={esc(scenario["scenario_id"])} '
            f'<span class="mode-badge mode-{esc(badge["badge_mode"]).lower()}">MODE: {esc(badge["badge_mode"])}</span> '
            f'requested={esc(badge["requested_mode"])}{warn}</div>'
        )
    return f'<section class="card"><h2>Mode badge</h2>{"".join(blocks)}</section>'


CSS = """
body { font-family: system-ui, sans-serif; margin: 0; padding: 1.5rem; background: #0b0d12; color: #e6e8eb; }
@media (prefers-color-scheme: light) { body { background: #f6f7f9; color: #14161a; } }
h1 { font-size: 1.3rem; }
.banner { border: 2px solid #c9a227; background: rgba(201,162,39,0.12); padding: 0.75rem 1rem; margin-bottom: 1rem; border-radius: 6px; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 1rem; }
.card { border: 1px solid #333; border-radius: 8px; padding: 1rem; background: rgba(255,255,255,0.03); overflow-x: auto; }
.card h2 { margin-top: 0; font-size: 1rem; }
table { border-collapse: collapse; width: 100%; font-size: 0.85rem; }
th, td { border: 1px solid #444; padding: 0.3rem 0.5rem; text-align: left; }
.warning, .warning_control_absent_from_fixture { color: #ff6b6b; font-weight: 600; }
.freshness { display: block; font-size: 0.75rem; opacity: 0.75; }
.freshness-stale { color: #ff6b6b; }
.freshness-absent { color: #ff6b6b; }
.freshness-fresh, .freshness-fresh_no_bound { color: #52c97a; }
.actionable { font-size: 0.8rem; font-weight: 600; }
.mode-badge { display: inline-block; padding: 0.15rem 0.5rem; border-radius: 999px; font-weight: 700; }
.mode-shadow { background: #2b4a6f; color: #cfe3ff; }
.mode-confirm { background: #6f5a2b; color: #ffe9c2; }
.mode-auto { background: #6f2b2b; color: #ffc2c2; }
.mode-off { background: #333; color: #ccc; }
.note { font-size: 0.75rem; opacity: 0.7; margin-top: 0.5rem; }
.event, .reaction-claim, .edge, .age, .mode-scenario { border-top: 1px solid #333; padding: 0.4rem 0; font-size: 0.85rem; }
"""


def build() -> str:
    now = now_reference()
    manifest = load("manifest.json")
    sections = "".join(
        [
            render_consensus_section(now),
            render_cross_book_section(now),
            render_stale_residuals_section(now),
            render_history_section(now),
            render_events_section(),
            render_projection_section(now),
            render_edge_section(now),
            render_age_section(now),
            render_execution_warnings_section(),
        ]
    )
    mode_section = render_mode_badge_section()
    html_doc = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>M25 Market UI Fixtures Shell</title>
<style>{CSS}</style></head>
<body>
<div class="banner">
  <strong>PRODUCT SCAFFOLD built against fixtures.</strong> Carries no market claim and must
  not imply that any edge, signal or tradable opportunity exists: fixtures render as fixtures.
  Built {esc(datetime.now(timezone.utc).isoformat())}. Fixture reference clock (fixture_now_reference):
  {esc(manifest["fixture_now_reference"])}. m00_use_class={esc(manifest["m00_use_class"])}.
  No live quote is wired into this page -- every value below was baked in at build time from
  local JSON fixtures under fixtures/.
</div>
<h1>Market screen shell (fixtures)</h1>
{mode_section}
<div class="grid">
{sections}
</div>
</body></html>
"""
    return html_doc


if __name__ == "__main__":
    out = HERE / "shell.html"
    out.write_text(build(), encoding="utf-8")
    print(f"wrote {out}")
