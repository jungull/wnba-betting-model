#!/usr/bin/env python3
"""D036 point 8 / D037 / D038 Prediction Leaderboard generator.

Deterministic: reads exactly six JSON inputs (data_coverage.json,
metrics.json, lifecycle.json, score_config.json,
granular/player_granular_metrics.json, granular/player_granular_coverage.json)
and emits scoreboard.html plus scoreboard_manifest.json.  Given identical
input bytes the emitted HTML is byte-identical (the page's own displayed
timestamps come from the inputs).  The manifest carries its own generation
timestamp and the sha256 of the six inputs, this generator, and the output.

D038 adds the user-facing Prediction Leaderboard experience on top of the
D036/D037 audit layer: summary cards, one sortable/filterable table with one
row per prediction target, a FROZEN Prediction Score transformation
(score_config.json, prediction_score/1.0.0), plain-English subtext, evidence
badges, hover provenance and expandable rows.  The prior evidence sections
(bookie baseline, granular player outcomes, coverage, operational progress,
dropped-cells honesty log, provenance footnotes) are preserved verbatim in
the methodology & evidence layer below the leaderboard.

The two granular/*.json inputs are READ-ONLY: they are pre-computed by
experiments/market_program/SCOREBOARD/granular/compute_player_granular.py and
this generator only selects and formats already-computed fields from them --
it never recomputes a metric.  The Prediction Score is the ONLY derived
quantity on the page and it is computed strictly by the frozen formula in
score_config.json from already-committed error metrics on matched universes;
no score is ever hand-set and unevaluated targets never show a score.
"""
import hashlib
import html
import json
import os
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))

CSS = """  :root {
    --bg: #FAFAF7; --surface: #FFFFFF; --line: #E4E2DB;
    --ink: #1D1E1A; --ink-2: #565750; --ink-3: #8B8B83;
    --accent: #C2571B; --accent-ink: #9C4413;
    --us: #C2571B; --mkt: #33628C; --best: #6B4FA1; --worst: #857F72;
    --ok: #2E7D4F; --ok-bg: #E7F2EA;
    --run: #8A6D1F; --run-bg: #F5EEDA;
    --sealed: #5B5E66; --sealed-bg: #ECECEF;
    --tbd: #8B8B83; --tbd-bg: #F1F0EC;
    --warn: #A04E12; --warn-bg: #F8EBE1;
  }
  @media (prefers-color-scheme: dark) { :root {
    --bg: #14161A; --surface: #1C1F24; --line: #2E323A;
    --ink: #E9E8E2; --ink-2: #A8A9A1; --ink-3: #767770;
    --accent: #E07A3E; --accent-ink: #E8925F;
    --us: #E07A3E; --mkt: #6FA0CC; --best: #A38BD4; --worst: #8C8677;
    --ok: #58A87C; --ok-bg: #1E2E25;
    --run: #C9A94E; --run-bg: #2E2917;
    --sealed: #9DA1AB; --sealed-bg: #262930;
    --tbd: #767770; --tbd-bg: #22242A;
    --warn: #D98147; --warn-bg: #322015;
  }}
  :root[data-theme="light"] {
    --bg: #FAFAF7; --surface: #FFFFFF; --line: #E4E2DB;
    --ink: #1D1E1A; --ink-2: #565750; --ink-3: #8B8B83;
    --accent: #C2571B; --accent-ink: #9C4413;
    --us: #C2571B; --mkt: #33628C; --best: #6B4FA1; --worst: #857F72;
    --ok: #2E7D4F; --ok-bg: #E7F2EA;
    --run: #8A6D1F; --run-bg: #F5EEDA;
    --sealed: #5B5E66; --sealed-bg: #ECECEF;
    --tbd: #8B8B83; --tbd-bg: #F1F0EC;
    --warn: #A04E12; --warn-bg: #F8EBE1;
  }
  :root[data-theme="dark"] {
    --bg: #14161A; --surface: #1C1F24; --line: #2E323A;
    --ink: #E9E8E2; --ink-2: #A8A9A1; --ink-3: #767770;
    --accent: #E07A3E; --accent-ink: #E8925F;
    --us: #E07A3E; --mkt: #6FA0CC; --best: #A38BD4; --worst: #8C8677;
    --ok: #58A87C; --ok-bg: #1E2E25;
    --run: #C9A94E; --run-bg: #2E2917;
    --sealed: #9DA1AB; --sealed-bg: #262930;
    --tbd: #767770; --tbd-bg: #22242A;
    --warn: #D98147; --warn-bg: #322015;
  }
  * { box-sizing: border-box; }
  body { background: var(--bg); color: var(--ink); font: 15px/1.55 ui-sans-serif, system-ui, "Segoe UI", sans-serif; margin: 0; padding: 32px 20px 64px; }
  .wrap { max-width: 1080px; margin: 0 auto; display: flex; flex-direction: column; gap: 28px; }
  .eyebrow { font-size: 11px; font-weight: 700; letter-spacing: .14em; text-transform: uppercase; color: var(--accent-ink); }
  h1 { font-size: 26px; font-weight: 800; margin: 2px 0 0; letter-spacing: -.01em; text-wrap: balance; }
  .stamp { color: var(--ink-3); font-size: 12.5px; margin-top: 6px; }
  .stamp b { color: var(--ink-2); font-weight: 600; }
  h2 { font-size: 13px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; color: var(--ink-2); margin: 0 0 10px; }
  .tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }
  .tile { background: var(--surface); border: 1px solid var(--line); border-radius: 8px; padding: 16px 18px 14px; }
  .tile .k { font-size: 11px; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; color: var(--ink-3); }
  .tile .v { font-size: 30px; font-weight: 800; letter-spacing: -.02em; margin: 4px 0 2px; font-variant-numeric: tabular-nums; }
  .tile .v small { font-size: 14px; font-weight: 600; color: var(--ink-2); letter-spacing: 0; }
  .tile .d { font-size: 12.5px; color: var(--ink-2); }
  .chip { display: inline-flex; align-items: center; gap: 5px; font-size: 10.5px; font-weight: 700; letter-spacing: .06em; padding: 2px 8px; border-radius: 999px; white-space: nowrap; vertical-align: middle; }
  .chip::before { content: ""; width: 6px; height: 6px; border-radius: 50%; background: currentColor; }
  .chip.long { white-space: normal; line-height: 1.3; }
  .c-ok { color: var(--ok); background: var(--ok-bg); }
  .c-run { color: var(--run); background: var(--run-bg); }
  .c-sealed { color: var(--sealed); background: var(--sealed-bg); }
  .c-tbd { color: var(--tbd); background: var(--tbd-bg); }
  .c-na { color: var(--ink-3); background: none; border: 1px dashed var(--line); }
  .c-na::before { display: none; }
  .c-warn { color: var(--warn); background: var(--warn-bg); }
  .tablewrap { background: var(--surface); border: 1px solid var(--line); border-radius: 8px; overflow-x: auto; }
  table { border-collapse: collapse; width: 100%; min-width: 880px; }
  th, td { text-align: left; padding: 10px 14px; border-top: 1px solid var(--line); font-size: 13.5px; vertical-align: top; }
  thead th { border-top: none; font-size: 11px; font-weight: 700; letter-spacing: .09em; text-transform: uppercase; color: var(--ink-3); padding-top: 14px; }
  thead th .dot { display: inline-block; width: 8px; height: 8px; border-radius: 2px; margin-right: 6px; vertical-align: baseline; }
  tbody th[colspan] { background: none; border-top: 1px solid var(--line); font-size: 11px; letter-spacing: .12em; text-transform: uppercase; color: var(--accent-ink); padding: 14px 14px 6px; font-weight: 800; }
  td .num { font-weight: 700; font-variant-numeric: tabular-nums; font-size: 14.5px; }
  td .sub { display: block; color: var(--ink-3); font-size: 11.5px; margin-top: 2px; }
  .metric { font-weight: 600; }
  .metric .sub { font-weight: 400; }
  .prov { cursor: help; color: var(--ink-3); font-size: 11px; border-bottom: 1px dotted var(--ink-3); }
  .foot { font-size: 12.5px; color: var(--ink-2); }
  .foot p { margin: 6px 0; }
  .foot .mark { font-weight: 700; color: var(--ink); }
  details.provnote { font-size: 12px; color: var(--ink-2); margin: 6px 0; border-left: 3px solid var(--line); padding-left: 12px; }
  details.provnote summary { cursor: pointer; font-weight: 600; color: var(--ink); }
  details.provnote code { word-break: break-all; }
  .pipe { display: flex; flex-wrap: wrap; gap: 8px; }
  .pipe .step { border: 1px solid var(--line); background: var(--surface); border-radius: 6px; padding: 8px 12px; font-size: 12px; color: var(--ink-2); }
  .pipe .step b { display: block; font-size: 11px; letter-spacing: .08em; text-transform: uppercase; color: var(--ink); }
  .pipe .step.now { border-color: var(--accent); }
  .pipe .step.now b { color: var(--accent-ink); }
  .log { font-size: 12.5px; color: var(--ink-2); border-left: 3px solid var(--line); padding-left: 14px; }
  .log div { margin: 4px 0; }
  .log b { color: var(--ink); font-weight: 600; }
  section.opsec { border: 1px dashed var(--run); border-radius: 8px; padding: 16px 18px; background: var(--surface); }
  section.opsec h2 { color: var(--run); }
  section.predsec { border-left: 4px solid var(--accent); padding-left: 16px; }
  code { font-family: ui-monospace, Consolas, monospace; font-size: 11.5px; color: var(--ink-2); }
  /* ---------------- D038 leaderboard additions ---------------- */
  .controls { display: flex; flex-wrap: wrap; gap: 10px 18px; align-items: center; font-size: 12.5px; color: var(--ink-2); background: var(--surface); border: 1px solid var(--line); border-radius: 8px; padding: 10px 14px; }
  .controls label { display: inline-flex; gap: 6px; align-items: center; white-space: nowrap; }
  .controls select { font: inherit; font-size: 12.5px; color: var(--ink); background: var(--bg); border: 1px solid var(--line); border-radius: 6px; padding: 3px 6px; }
  #lb-table th.sortable { cursor: pointer; user-select: none; }
  #lb-table th.sortable:hover { color: var(--ink); }
  #lb-table th.sortable::after { content: " \\2195"; opacity: .45; font-size: 10px; }
  #lb-table th[aria-sort="ascending"]::after { content: " \\2191"; opacity: 1; }
  #lb-table th[aria-sort="descending"]::after { content: " \\2193"; opacity: 1; }
  #lb-table { min-width: 1020px; }
  .scorebig { font-size: 22px; font-weight: 800; font-variant-numeric: tabular-nums; letter-spacing: -.02em; }
  .bandtag { display: block; font-size: 11px; color: var(--ink-3); }
  tr.lb-detail > td { background: var(--bg); }
  .lb-expand { font: inherit; font-size: 11px; color: var(--accent-ink); background: none; border: 1px solid var(--line); border-radius: 6px; padding: 1px 8px; cursor: pointer; margin-top: 4px; }
  .detailgrid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 10px 22px; font-size: 12.5px; color: var(--ink-2); }
  .detailgrid b { color: var(--ink); }
  .detailgrid h4 { margin: 0 0 4px; font-size: 11px; letter-spacing: .08em; text-transform: uppercase; color: var(--ink-3); }
  .locked { border: 1px dashed var(--line); border-radius: 8px; padding: 14px 18px; color: var(--ink-2); font-size: 13px; background: var(--surface); }
  @media (max-width: 680px) {
    body { padding: 18px 10px 48px; }
    h1 { font-size: 21px; }
    .tile .v { font-size: 24px; }
    th, td { padding: 8px 10px; font-size: 12.5px; }
    .scorebig { font-size: 18px; }
  }
"""

# Static, input-independent script: sorting (every column, both directions,
# blank values always last), filtering (only ever toggles row.hidden --
# never touches a cell value), and row expansion.  No metric is computed or
# rewritten in the browser.
JS = """(function () {
  var table = document.getElementById('lb-table');
  if (!table) return;
  var tbody = table.tBodies[0];
  var headers = table.tHead.rows[0].cells;
  var state = { key: null, dir: -1 };
  function mainRows() { return Array.prototype.slice.call(tbody.querySelectorAll('tr.lb-row')); }
  function detailFor(r) { return tbody.querySelector('tr.lb-detail[data-for="' + r.id + '"]'); }
  function val(row, key) {
    var v = row.getAttribute('data-' + key);
    if (v === null || v === '') return null;
    var n = Number(v);
    return (v !== '' && !isNaN(n)) ? n : v.toLowerCase();
  }
  function sortBy(key, dir) {
    var rows = mainRows();
    rows.sort(function (a, b) {
      var va = val(a, key), vb = val(b, key);
      var oa = Number(a.getAttribute('data-order')), ob = Number(b.getAttribute('data-order'));
      if (va === null && vb === null) return oa - ob;
      if (va === null) return 1;  /* blanks last in BOTH directions */
      if (vb === null) return -1;
      if (va < vb) return -1 * dir;
      if (va > vb) return 1 * dir;
      return oa - ob;
    });
    rows.forEach(function (r) {
      tbody.appendChild(r);
      var d = detailFor(r);
      if (d) tbody.appendChild(d);
    });
  }
  Array.prototype.forEach.call(headers, function (th) {
    var key = th.getAttribute('data-key');
    if (!key) return;
    th.addEventListener('click', function () {
      if (state.key === key) { state.dir = -state.dir; }
      else { state.key = key; state.dir = th.getAttribute('data-default-dir') === 'asc' ? 1 : -1; }
      Array.prototype.forEach.call(headers, function (h) { h.removeAttribute('aria-sort'); });
      th.setAttribute('aria-sort', state.dir === 1 ? 'ascending' : 'descending');
      sortBy(key, state.dir);
    });
  });
  /* Filters only hide rows; they never alter a metric value (acceptance check 9). */
  function applyFilters() {
    var levelEl = document.getElementById('f-level');
    var verEl = document.getElementById('f-verified');
    var mktEl = document.getElementById('f-market');
    var level = levelEl ? levelEl.value : 'all';
    var ver = verEl ? verEl.checked : false;
    var mkt = mktEl ? mktEl.checked : false;
    mainRows().forEach(function (r) {
      var hide = false;
      if (level !== 'all' && r.getAttribute('data-level') !== level) hide = true;
      if (ver && r.getAttribute('data-verified') !== '1') hide = true;
      if (mkt && r.getAttribute('data-market-covered') !== '1') hide = true;
      r.hidden = hide;
      var d = detailFor(r);
      if (d) d.hidden = hide || d.getAttribute('data-open') !== '1';
    });
  }
  ['f-level', 'f-verified', 'f-market', 'f-season', 'f-cutoff'].forEach(function (id) {
    var el = document.getElementById(id);
    if (el) el.addEventListener('change', applyFilters);
  });
  Array.prototype.forEach.call(document.querySelectorAll('button.lb-expand'), function (btn) {
    btn.addEventListener('click', function () {
      var d = tbody.querySelector('tr.lb-detail[data-for="' + btn.getAttribute('data-for') + '"]');
      if (!d) return;
      var open = d.getAttribute('data-open') === '1';
      d.setAttribute('data-open', open ? '0' : '1');
      d.hidden = open;
      btn.setAttribute('aria-expanded', open ? 'false' : 'true');
      btn.textContent = open ? '+ details' : '\\u2212 details';
    });
  });
})();"""


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def esc(s):
    return html.escape(str(s), quote=True)


def fmt(x, dp=4):
    return f"{x:,.{dp}f}" if isinstance(x, float) else f"{x:,}"


def fmt1(x):
    return f"{x:,.1f}"


def prov_title(prefix, row):
    """Assemble the full provenance text used in the title popover."""
    p = row.get("provenance", {})
    src = p.get("source_artifact", {})
    lin = p.get("commit_lineage", {})
    bits = [
        prefix,
        f"model version: {row.get('model_version')}",
        f"target: {row.get('target')}",
        f"cutoff: {row.get('cutoff')}",
        f"universe: {row.get('universe')}",
        f"date range: {row.get('date_range')}",
        f"evidence class: {row.get('evidence_class')}",
        f"source: {src.get('path')} sha256={src.get('sha256')}",
        f"commit lineage: {lin.get('recorded_head')} ({lin.get('note', lin.get('recorded_where', ''))})",
        f"computed at: {p.get('computation_timestamp_utc')}",
    ]
    return " | ".join(str(b) for b in bits if b is not None)


def chip(kind, text, title=None, long=False):
    cls = {"ok": "c-ok", "run": "c-run", "pend": "c-sealed", "tbd": "c-tbd", "na": "c-na", "warn": "c-warn"}[kind]
    t = f' title="{esc(title)}"' if title else ""
    lg = " long" if long else ""
    return f'<span class="chip {cls}{lg}"{t}>{esc(text)}</span>'


def get_row(metrics, row_id):
    for r in metrics["rows"]:
        if r["row_id"] == row_id:
            return r
    raise KeyError(row_id)


def pooled(baseline_rows, snapshot_class, variant):
    for r in baseline_rows:
        if r["season"] == "POOLED" and r["snapshot_class"] == snapshot_class and r["variant"] == variant:
            return r
    raise KeyError((snapshot_class, variant))


PENDING = "NOT-YET-EVALUATED-PENDING-AUDIT"

# ---------------------------------------------------------------- D037: granular player outcomes
GRANULAR_STATS = [
    ("points", "Points"),
    ("rebounds", "Rebounds"),
    ("assists", "Assists"),
    ("steals", "Steals"),
    ("blocks", "Blocks"),
    ("threes_made", "Threes made"),
    ("turnovers", "Turnovers"),
    ("minutes", "Minutes"),
]
NAIVE_VARIANTS = ("trailing_5_mean", "season_to_date_mean", "league_mean")
NAIVE_VARIANT_LABELS = {
    "trailing_5_mean": "trailing-5 mean",
    "season_to_date_mean": "season-to-date mean",
    "league_mean": "league mean",
}
LEGACY_PROBED_STATS = {"points", "minutes"}
LEGACY_PROBE_NOTE = (
    "PROBE_LEGACY.md verdict: RECEIPTABLE -- committed OOF prediction artifacts "
    "(cbs_v15_player_oof_v5, cbs_v14_player_oof, oof_backfill) exist on disk with "
    "per-fold cutoff-discipline receipts and sha256 manifests. Per D037, no legacy "
    "number is rendered until a verification node executes the full checklist (byte "
    "integrity, producer digest, cutoff discipline, universe, config/snapshot "
    "pinning, generation-only claim, tier semantics)."
)


def best_naive_pooled(granular_metrics, stat_key):
    """Select the naive baseline variant with the lowest pooled MAE for a stat.

    Selection only -- the pooled MAE values themselves are read verbatim from
    granular/player_granular_metrics.json, never recomputed.
    """
    variants = granular_metrics["naive_baselines"][stat_key]
    best_variant = min(NAIVE_VARIANTS, key=lambda v: variants[v]["pooled"]["mae"])
    return best_variant, variants[best_variant]["pooled"]


def naive_prov_title(row, granular_metrics):
    bits = [
        "naive baseline (best of three by pooled MAE)",
        f"model version: {row.get('model_version')}",
        f"target: {row.get('target')}",
        f"cutoff: {row.get('cutoff')}",
        f"universe: {row.get('universe')}",
        f"date range: {row.get('date_range')}",
        f"evidence class: {row.get('evidence_class')}",
        f"n_player_games: {row.get('n_player_games')}",
        f"mae: {row.get('mae')}",
        f"mae 95% CI: [{row.get('mae_ci95', {}).get('lo')}, {row.get('mae_ci95', {}).get('hi')}]",
        f"producer: {granular_metrics.get('producer')} sha256={granular_metrics.get('producer_sha256')}",
        f"contract sha256: {granular_metrics.get('contract_sha256')}",
        f"computed at: {granular_metrics.get('generated_utc')}",
    ]
    return " | ".join(str(b) for b in bits)


def market_prov_title(row, granular_metrics):
    bits = [
        "market threshold (all books pooled)",
        f"model version: {row.get('model_version')}",
        f"target: {row.get('target')}",
        f"cutoff: {row.get('cutoff')}",
        f"universe: {row.get('universe')}",
        f"date range: {row.get('date_range')}",
        f"evidence class: {row.get('evidence_class')}",
        f"vig method: {row.get('vig_method')}",
        f"vig preregistration sha256: {row.get('vig_preregistration_hash')}",
        f"devig_brier: {row.get('devig_brier')}",
        f"devig_ou_accuracy: {row.get('devig_ou_accuracy')}",
        f"n_quote_rows: {row.get('n_quote_rows')}",
        f"n_player_games: {row.get('n_player_games')}",
        f"computed at: {granular_metrics.get('generated_utc')}",
    ]
    return " | ".join(str(b) for b in bits)


# ==================================================================== D038
# Frozen Prediction Score machinery.  The constants below MUST match
# score_config.json (prediction_score/1.0.0); build refuses to run otherwise.
SCORE_VERSION = "prediction_score/1.0.0"
SCORE_CONSTANTS = {"offset": 50, "slope": 100, "clamp_min": 0, "clamp_max": 100}
BADGE_RANK = {"VERIFIED": 0, "PROMISING": 1, "PRELIMINARY": 2, "PENDING": 3, "NOT_CAPTURED": 4}
BADGE_CHIP_KIND = {"VERIFIED": "ok", "PROMISING": "run", "PRELIMINARY": "warn", "PENDING": "pend", "NOT_CAPTURED": "na"}
LEVEL_SAMPLE_UNITS = {"player": "player-games", "team": "team-games", "game": "games"}


def verify_score_config(cfg):
    ps = cfg["prediction_score"]
    if ps["version"] != SCORE_VERSION:
        raise SystemExit(f"score_config version {ps['version']!r} != generator's frozen {SCORE_VERSION!r}; refusing to build")
    if ps["constants"] != SCORE_CONSTANTS:
        raise SystemExit("score_config constants diverge from the generator's frozen constants; refusing to build")
    if not ps.get("frozen") or not cfg.get("frozen"):
        raise SystemExit("score_config must be frozen; refusing to build")


def compute_prediction_score(model_error, baseline_error):
    """FROZEN prediction_score/1.0.0: score = clamp(50 + 100*skill, 0, 100),
    skill = (baseline_error - model_error) / baseline_error.  Higher is always
    better; 50 = baseline quality; one point = one percentage point of error
    reduced vs the declared baseline on the identical universe."""
    if model_error is None or baseline_error is None or baseline_error <= 0:
        return None, None
    skill = (baseline_error - model_error) / baseline_error
    raw = SCORE_CONSTANTS["offset"] + SCORE_CONSTANTS["slope"] * skill
    clamped = max(SCORE_CONSTANTS["clamp_min"], min(SCORE_CONSTANTS["clamp_max"], raw))
    return int(round(clamped)), skill


def band_label(score, cfg):
    for b in cfg["prediction_score"]["bands"]:
        if b["min"] <= score <= b["max"]:
            return b["label"]
    return "unbanded"


def compute_market_advantage(model_error, market_error, matched):
    """FROZEN market_advantage/1.0.0: advantage = (market_error - model_error)
    / market_error, positive = our model better.  Returns None unless BOTH
    errors exist AND the universes/cutoffs are matched -- an unmatched
    comparison is never computed (acceptance check 4)."""
    if not matched or model_error is None or market_error is None or market_error <= 0:
        return None
    return (market_error - model_error) / market_error


def advantage_label(adv, cfg):
    t = cfg["market_advantage"]["label_thresholds"]
    if adv >= t["strong_min"]:
        return "Strong advantage"
    if adv >= t["meaningful_min"]:
        return "Meaningful advantage"
    if adv > t["market_level_abs_max"]:
        return "Slight advantage"
    if adv >= -t["market_level_abs_max"]:
        return "Market-level"
    return "Market currently better"


def badge_for_evidence_class(evidence_class, cfg):
    if evidence_class is None:
        return "PENDING"
    m = cfg["evidence_badges"]["evidence_class_prefix_map"]
    for prefix, badge in m.items():
        if str(evidence_class).startswith(prefix):
            return badge
    return "PENDING"


# ------------------------------------------------------------ target resolvers
def resolve_model(tcfg, metrics, gm):
    """Our-model evidence for a target, or None if unevaluated.  Values are
    read verbatim from metrics.json / granular our_model rows."""
    row_id = tcfg.get("model_row")
    if row_id:
        try:
            r = get_row(metrics, row_id)
        except KeyError:
            r = None
        if r is not None and r.get("status") == "MEASURED":
            m = r["metrics"]
            return {
                "error": m.get("mae"), "rmse": m.get("rmse"), "bias": m.get("bias"),
                "n": m.get("n_team_games") or m.get("n_player_games") or m.get("n"),
                "universe": r.get("universe"), "cutoff": r.get("cutoff"),
                "evidence_class": r.get("evidence_class"), "row": r,
                "title": prov_title("our model", r),
                "updated": (r.get("provenance", {}).get("computation_timestamp_utc") or "")[:10],
            }
        # else: fall through to the granular our_model pathway below -- a
        # metrics.json model_row is preferred when MEASURED but its absence
        # (e.g. fixtures without the row) never masks a granular evaluated result.
    stat = tcfg.get("granular_stat")
    om = gm.get("our_model", {})
    if stat and isinstance(om.get("rows"), dict) and stat in om["rows"]:
        r = om["rows"][stat].get("pooled")
        if r and r.get("mae") is not None:
            return {
                "error": r.get("mae"), "rmse": r.get("rmse"), "bias": r.get("bias"),
                "n": r.get("n_player_games"),
                "universe": r.get("universe"), "cutoff": r.get("cutoff"),
                "evidence_class": r.get("evidence_class"), "row": r,
                "title": naive_prov_title(r, gm).replace("naive baseline (best of three by pooled MAE)", "our model (granular pooled)"),
                "updated": str(gm.get("generated_utc", ""))[:10],
            }
    return None


def resolve_baseline(tcfg, cfg, metrics, gm):
    spec = cfg["baselines"][tcfg["baseline"]]
    if spec["kind"] == "best_of_three_naive_pooled_mae":
        variant, row = best_naive_pooled(gm, tcfg["granular_stat"])
        return {
            "pending": False, "name": f"{NAIVE_VARIANT_LABELS[variant]} baseline",
            "variant": variant, "error": row["mae"], "n": row["n_player_games"],
            "universe": row.get("universe"), "cutoff": row.get("cutoff"),
            "ci": row.get("mae_ci95"), "row": row,
            "title": naive_prov_title(row, gm),
        }
    # declared-pending kinds
    name = "a basic naive baseline (declared, pending computation)"
    title = spec.get("note", "declared pending")
    if tcfg["baseline"] == "naive_trio_declared_pending":
        try:
            nrow = get_row(metrics, "naive_baseline_league_mean")
            title = nrow["evidence_class"]
        except KeyError:
            pass
    return {"pending": True, "name": name, "error": None, "n": None, "universe": None, "title": title}


def resolve_market(tcfg, metrics, gm):
    key = tcfg["market"]
    if key == "props_threshold_points":
        mp = gm["market_threshold"]["points"]["pooled_books"]["pooled"]
        return {"state": "measured", "metric": "devig_brier", "metric_label": "de-vigged O/U Brier",
                "error": mp["devig_brier"], "n": mp["n_player_games"],
                "universe": mp.get("universe"), "cutoff": mp.get("cutoff"), "row": mp,
                "title": market_prov_title(mp, gm)}
    if key == "props_not_captured":
        return {"state": "not_captured",
                "note": "no prop lines captured for this stat -- player_points is the only market family in the archive"}
    if key == "market_does_not_price":
        return {"state": "not_priced", "note": "the market does not price this target directly"}
    if key == "bookie_not_computed":
        return {"state": "not_computed", "note": "not computed in the baseline artifact; never inferred"}
    if key in ("bookie_late_cross_total", "bookie_late_cross_spread", "bookie_late_cross_moneyline"):
        bb = get_row(metrics, "bookie_baseline")
        late_x = pooled(bb["metrics"]["rows"], "LATE", "cross_book")
        fam = {"bookie_late_cross_total": ("total", "mae", "MAE"),
               "bookie_late_cross_spread": ("spread", "mae", "MAE"),
               "bookie_late_cross_moneyline": ("moneyline", "brier", "de-vigged Brier")}[key]
        block = late_x[fam[0]]
        return {"state": "measured", "metric": fam[1], "metric_label": fam[2],
                "error": block[fam[1]], "n": block["n"],
                "universe": bb.get("universe"), "cutoff": bb.get("cutoff"), "row": block,
                "title": prov_title("market consensus (LATE class, cross-book, de-vigged)", bb)
                         + " | CAVEAT: " + bb["caveat_text_verbatim"]}
    raise KeyError(key)


def universes_match(a, b):
    """Matched-universe rule (frozen in score_config): exact universe-string
    equality AND identical N.  Never a fuzzy or partial match."""
    if not a or not b:
        return False
    return (a.get("universe") is not None and a.get("universe") == b.get("universe")
            and a.get("n") is not None and a.get("n") == b.get("n"))


def cutoffs_match(a, b):
    return a.get("cutoff") is not None and a.get("cutoff") == b.get("cutoff")


# ------------------------------------------------------------ leaderboard rows
def build_leaderboard_rows(cfg, coverage, metrics, lifecycle, gm, gc):
    verify_score_config(cfg)
    ps = cfg["prediction_score"]
    tol_bands = cfg["tolerance_bands"]["bands"]
    rows = []
    for order, tcfg in enumerate(cfg["targets"]):
        model = resolve_model(tcfg, metrics, gm)
        baseline = resolve_baseline(tcfg, cfg, metrics, gm)
        market = resolve_market(tcfg, metrics, gm)
        unit = tcfg["unit"]
        level = tcfg["level"]
        sample_units = LEVEL_SAMPLE_UNITS[level]

        badge = badge_for_evidence_class(model["evidence_class"], cfg) if model else "PENDING"

        # ---- Prediction Score (frozen formula, matched universes only)
        score = skill = None
        score_reason = None
        if model is None:
            score_reason = ("TBD -- no evaluated model run exists for this target; unevaluated targets never "
                            "show a score (no attractive placeholders, acceptance check 3)")
        elif baseline.get("pending"):
            score_reason = ("TBD -- model measured but the declared matched-universe baseline is still pending; "
                            "a score is never computed against a missing or unmatched baseline")
        elif badge not in ps["eligibility"]["allowed_model_evidence_badges"]:
            score_reason = f"TBD -- model evidence badge {badge} is below the minimum evidence requirement"
        elif not universes_match(model, baseline):
            score_reason = ("TBD -- model and baseline universes are not identical (exact universe string + "
                            "identical N required); unmatched universes are never compared")
        elif model["n"] < ps["eligibility"]["min_n_by_level"][level]:
            score_reason = (f"TBD -- n={model['n']} below the frozen minimum of "
                            f"{ps['eligibility']['min_n_by_level'][level]} {sample_units}")
        else:
            score, skill = compute_prediction_score(model["error"], baseline["error"])

        # ---- typical miss + plain-English subtext
        if model is not None and model.get("error") is not None and tcfg["kind"] == "scalar":
            miss = model["error"]
            miss_display = f'<span class="num">{fmt1(miss)} {esc(unit)}</span>'
            subtext = cfg["display"]["subtext_template"].format(miss=fmt1(miss), unit=unit)
        elif model is not None and tcfg["kind"] == "probability":
            miss = None
            miss_display = f'<span class="num">{model["error"]:.4f} Brier</span>'
            subtext = "probability quality (Brier: 0 = perfect, 0.25 = coin flip)"
        else:
            miss = None
            miss_display = chip("tbd", "TBD", "our model has not been evaluated on this target yet")
            if not baseline.get("pending"):
                subtext = cfg["display"]["benchmark_subtext_template"].format(
                    baseline=baseline["name"], miss=fmt1(baseline["error"]), unit=unit)
            elif market.get("state") == "measured" and market["metric"] == "mae":
                subtext = (f"No model prediction evaluated yet — market consensus is usually within "
                           f"{fmt1(market['error'])} {unit} of the actual result")
            elif market.get("state") == "measured":
                subtext = (f"No model prediction evaluated yet — market consensus de-vigged Brier is "
                           f"{market['error']:.4f} (0 = perfect, 0.25 = coin flip)")
            else:
                subtext = "No model prediction evaluated yet and no benchmark computed for this target"

        # ---- within target range (tolerance bands frozen in config)
        tol_key = tcfg.get("tolerance_key")
        if tol_key:
            band = tol_bands[tol_key]
            range_display = (f'±{band["tolerance"]} {esc(band["unit"])} declared'
                             f'<span class="sub">hit-rate not yet computed for any evaluated row</span>')
        else:
            range_display = ('<span class="sub">no target range declared — bands are frozen in '
                             'score_config.json and are never invented per-target</span>')

        # ---- improvement vs basic model
        imp_cfg = cfg["improvement_vs_basic_model"]
        improve_num = None
        if score is not None:
            if abs(skill) < imp_cfg["roughly_equal_band_abs_skill"]:
                improve_text = imp_cfg["labels"]["roughly_equal"].format(baseline=baseline["name"])
            elif skill > 0:
                improve_text = f"{skill * 100:.0f}% more accurate than a {baseline['name']} prediction"
            else:
                improve_text = imp_cfg["labels"]["worse"].format(baseline=baseline["name"])
            improve_num = round(skill * 100, 1)
            improve_title = (f"baseline: {baseline['name']} | metric: {ps['error_metric_by_target_kind'][tcfg['kind']]} | "
                             f"baseline value: {baseline['error']} | model value: {model['error']} | "
                             f"universe: {model['universe']} | n: {model['n']} | "
                             f"baseline 95% CI: {json.dumps(baseline.get('ci'))} | " + baseline["title"])
            improve_display = f'<span class="num" title="{esc(improve_title)}">{esc(improve_text)}</span>'
        elif model is not None and baseline.get("pending"):
            improve_display = chip("tbd", "Pending", imp_cfg["labels"]["pending_baseline"] + " | " + str(baseline["title"]))
            improve_display += '<span class="sub">baseline declared, not yet computed on this universe</span>'
        elif model is not None and not baseline.get("pending") and not universes_match(model, baseline):
            # Model evaluated, baseline evaluated -- but NOT on the identical universe.
            # Never faked from the unmatched numbers (D036 point 6 / D038): stays TBD.
            improve_display = chip("tbd", "Pending — matched universe", imp_cfg["labels"]["pending_universe_mismatch"]
                                   + " | model universe: " + str(model["universe"])
                                   + " | baseline universe: " + str(baseline["universe"]))
            improve_display += (f'<span class="sub">unmatched-universe reference only, never compared: our model '
                                f'{fmt1(model["error"])} {esc(unit)} vs {esc(baseline["name"])} '
                                f'{fmt1(baseline["error"])} {esc(unit)} (n={baseline["n"]:,})</span>')
        else:
            improve_display = chip("tbd", "Pending", imp_cfg["labels"]["pending_model"])
            if not baseline.get("pending"):
                improve_display += (f'<span class="sub">declared baseline on file: {esc(baseline["name"])}, '
                                    f'{fmt1(baseline["error"])} {esc(unit)} typical miss (n={baseline["n"]:,})</span>')

        # ---- market advantage (matched universes + cutoffs only, and NEVER
        # across metrics: the model must carry the market's own metric)
        market_num = None
        mc = model["row"].get("market_comparison") if model is not None else None
        if mc is not None:
            # A pre-computed, already-matched-universe comparison selected verbatim
            # from metrics.json (itself selected verbatim from MODEL_VS_MARKET/
            # model_vs_market.json by build_metrics.py) -- never recomputed here,
            # and on a metric (paired O/U accuracy) the generic devig_brier path
            # cannot use because no model probability/Brier exists for this row.
            adv = mc["advantage"]
            label = advantage_label(adv, cfg)
            kind = "ok" if adv > cfg["market_advantage"]["label_thresholds"]["market_level_abs_max"] else ("warn" if label == "Market currently better" else "run")
            market_num = round(adv * 100, 1)
            ci = mc.get("advantage_ci95")
            ci_txt = f' · 95% CI [{ci[0] * 100:+.2f}, {ci[1] * 100:+.2f}] pts' if ci else ""
            mc_src = mc.get("source", {})
            mc_title = (
                f'{mc.get("question", "")} verdict: {mc.get("verdict", "")} | metric: {mc["metric_label"]} '
                f'(paired difference, positive = model better) | model {mc["metric_label"]}: {mc["model_value"]:.4f} '
                f'| market {mc["metric_label"]}: {mc["market_value"]:.4f} | raw comparison: model {mc["model_value"]:.4f} '
                f'vs market {mc["market_value"]:.4f} = {adv * 100:+.2f} pts{ci_txt} | n={mc["n"]:,} | '
                f'universe: {mc.get("universe")} | {mc.get("market_brier_note", "")} | {mc.get("timing_advisory", "")} | '
                f'source: {mc_src.get("path")} sha256={mc_src.get("sha256")}'
            )
            market_display = (
                chip(kind, label, mc_title) +
                f'<span class="sub">{adv * 100:+.1f} {esc(mc["metric_label"])} points vs market'
                f'{ci_txt} · n={mc["n"]:,} (matched-universe paired comparison; hover for the raw comparison)</span>'
            )
        elif market.get("state") == "measured":
            matched = model is not None and universes_match(model, {"universe": market.get("universe"), "n": market.get("n")}) and cutoffs_match(model, market)
            model_market_error = None
            if model is not None:
                if market["metric"] == "mae":
                    model_market_error = model["error"]
                else:
                    src_row = model["row"]
                    model_market_error = (src_row.get("metrics", {}) or {}).get(market["metric"]) if "metrics" in src_row else src_row.get(market["metric"])
            adv = compute_market_advantage(model_market_error, market["error"], matched and model_market_error is not None)
            if adv is not None:
                label = advantage_label(adv, cfg)
                kind = "ok" if adv > cfg["market_advantage"]["label_thresholds"]["market_level_abs_max"] else ("warn" if label == "Market currently better" else "run")
                market_num = round(adv * 100, 1)
                market_display = (chip(kind, label, market["title"]) +
                                  f'<span class="sub">{adv * 100:+.1f}% lower {esc(market["metric_label"])} than market consensus '
                                  f'(positive = we did better) · n={market["n"]:,}</span>')
            elif model is not None:
                market_display = (chip("na", "Not comparable", "model and market universes/cutoffs are not identical; "
                                       "unmatched comparisons are never computed | " + market["title"]) +
                                  '<span class="sub">universes not matched — never compared</span>')
            else:
                sub = (f'market benchmark on file: {market["error"]:.4f} {esc(market["metric_label"])} · '
                       f'n={market["n"]:,} (T1 vendor-asserted)')
                market_display = chip("pend", "Pending", "our model is not yet evaluated; the market benchmark is measured "
                                      "and waiting | " + market["title"]) + f'<span class="sub">{sub}</span>'
        elif market.get("state") == "not_captured":
            market_display = chip("warn", "Not comparable", market["note"]) + '<span class="sub">no prop lines in archive</span>'
        elif market.get("state") == "not_priced":
            market_display = chip("na", "Not comparable", market["note"])
        else:
            market_display = chip("tbd", "Not comparable", market["note"]) + '<span class="sub">never inferred</span>'

        # ---- sample
        if model is not None and model.get("n"):
            sample_n = model["n"]
            sample_display = f'{sample_n:,} {sample_units}<span class="sub">our model</span>'
        elif not baseline.get("pending"):
            sample_n = baseline["n"]
            sample_display = f'{sample_n:,} player-games<span class="sub">benchmark</span>'
        elif market.get("state") == "measured":
            sample_n = market["n"]
            sample_display = f'{sample_n:,} games<span class="sub">market benchmark</span>'
        else:
            sample_n = None
            sample_display = '<span class="sub">—</span>'

        # ---- last updated (from inputs, never the build clock)
        if model is not None and model.get("updated"):
            updated = model["updated"]
        elif not baseline.get("pending"):
            updated = str(gm.get("generated_utc", ""))[:10]
        else:
            updated = str(metrics.get("generated_utc", ""))[:10]

        badge_title = {
            "VERIFIED": "audited blind walk-forward or adequate prospective evaluation",
            "PROMISING": "positive retrospective result, not yet confirmed by audit",
            "PRELIMINARY": "receipted retrospective development evidence; not blind-audited; "
                           "matched-baseline comparison pending",
            "PENDING": "implementation exists, evaluation not completed. Lifecycle: "
                       "BUILT → AUDITED → FITTING → EVALUATED/SEALED → ADJUDICATED",
            "NOT_CAPTURED": "the data does not exist",
        }[badge]
        if model is not None:
            badge_title += " | evidence class: " + str(model["evidence_class"])

        rows.append({
            "id": tcfg["id"], "label": tcfg["label"], "level": level, "unit": unit, "order": order,
            "kind": tcfg["kind"], "tcfg": tcfg,
            "model": model, "baseline": baseline, "market": market,
            "score": score, "skill": skill, "score_reason": score_reason,
            "band": band_label(score, cfg) if score is not None else None,
            "miss": miss,
            "miss_display": miss_display, "subtext": subtext,
            "range_display": range_display,
            "improve_display": improve_display, "improve_num": improve_num,
            "market_display": market_display, "market_num": market_num,
            "sample_n": sample_n, "sample_display": sample_display,
            "badge": badge, "badge_title": badge_title, "badge_rank": BADGE_RANK[badge],
            "updated": updated,
            "market_covered": 1 if (mc is not None or market.get("state") == "measured") else 0,
            "verified": 1 if badge == "VERIFIED" else 0,
        })
    return rows


def default_sort_key(r):
    """Default order (frozen in score_config defaults): scored rows first
    (evidence badge, then score desc), then evaluated-without-score rows by
    badge, then unevaluated targets in registry order."""
    if r["score"] is not None:
        group = 0
    elif r["model"] is not None:
        group = 1
    else:
        group = 2
    return (group, r["badge_rank"], -(r["score"] if r["score"] is not None else 0), r["order"])


# ------------------------------------------------------------ detail rows
def detail_html(r, cfg, metrics, gm, gc):
    """Expandable per-target evidence: baselines, market, seasons, coverage,
    limitations, provenance.  All values verbatim from inputs."""
    parts = ['<div class="detailgrid">']
    tcfg = r["tcfg"]

    # our model block
    parts.append("<div><h4>Our model</h4>")
    if r["model"] is not None:
        m = r["model"]
        bias_txt = f'{m["bias"]:+.4f}' if m.get("bias") is not None else "— (not adjudicated: P40 reports the pooled null MAE, not a bias term)"
        parts.append(f'<b>{fmt(m["error"])}</b> {esc(cfg["prediction_score"]["error_metric_by_target_kind"][r["kind"]])} '
                     f'· n={m["n"]:,}<br>bias {bias_txt} · RMSE {fmt(m["rmse"]) if m.get("rmse") is not None else "—"}<br>'
                     f'universe: {esc(m["universe"])}<br>cutoff: {esc(m["cutoff"])}<br>'
                     f'evidence: {esc(m["evidence_class"])}')
    else:
        parts.append(esc(PENDING) + "<br>" + esc(gm.get("our_model", {}).get(
            "note", "no evaluated model artifact exists for this target")))
    parts.append("</div>")

    # baseline block
    parts.append("<div><h4>Basic model (declared baseline)</h4>")
    b = r["baseline"]
    if not b.get("pending"):
        ci = b.get("ci") or {}
        parts.append(f'<b>{fmt(b["error"])}</b> MAE · {esc(b["name"])} · n={b["n"]:,}<br>'
                     f'95% CI [{ci.get("lo", 0):.4f}, {ci.get("hi", 0):.4f}] ({esc(ci.get("method", "—"))})<br>')
        stat = tcfg.get("granular_stat")
        if stat:
            parts.append("all three variants (pooled MAE): " + " · ".join(
                f'{esc(NAIVE_VARIANT_LABELS[v])} {gm["naive_baselines"][stat][v]["pooled"]["mae"]:.4f}'
                for v in NAIVE_VARIANTS) + "<br>")
            seasons = sorted(k for k in gm["naive_baselines"][stat][b["variant"]]
                             if k != "pooled" and isinstance(gm["naive_baselines"][stat][b["variant"]][k], dict)
                             and "mae" in gm["naive_baselines"][stat][b["variant"]][k])
            if seasons:
                parts.append("season-by-season (" + esc(NAIVE_VARIANT_LABELS[b["variant"]]) + "): " + " · ".join(
                    f'{esc(s)} {gm["naive_baselines"][stat][b["variant"]][s]["mae"]:.3f}' for s in seasons))
    else:
        parts.append("DECLARED-PENDING — " + esc(b["title"]))
    parts.append("</div>")

    # market block
    parts.append("<div><h4>Market</h4>")
    mk = r["market"]
    if mk.get("state") == "measured":
        parts.append(f'<b>{mk["error"]:.4f}</b> {esc(mk["metric_label"])} · n={mk["n"]:,}<br>')
        if mk["metric"] == "devig_brier" and "devig_ou_accuracy" in mk.get("row", {}):
            row = mk["row"]
            parts.append(f'de-vigged O/U accuracy {row["devig_ou_accuracy"]:.4f} · threshold MAE '
                         f'{row["threshold_mae"]:.4f} (line-vs-outcome distance, NOT a projection MAE)<br>')
        parts.append("cutoff: " + esc(mk.get("cutoff")) + "<br>T1 vendor-asserted snapshot; no timing/CLV inference")
    else:
        parts.append(esc(mk.get("note", "—")))
    parts.append("</div>")

    # seasons / diagnostics for the incumbent
    if tcfg.get("model_row") and r["model"] is not None and r["model"]["row"].get("season_splits"):
        splits = r["model"]["row"]["season_splits"]
        parts.append("<div><h4>Season-by-season (model arm D vs league-constant arm A — diagnostic, not a scored baseline)</h4>")
        parts.append(" · ".join(
            f'{esc(s)}: D {splits[s]["D_ewma_shrunk"]:.3f} / A {splits[s]["A_league_constant"]:.3f}'
            for s in sorted(splits)))
        parts.append("</div>")

    # known limitations + provenance
    parts.append("<div><h4>Known limitations</h4>")
    lims = []
    if r["score"] is None:
        lims.append(esc(r["score_reason"] or "score pending"))
    if mk.get("state") == "measured":
        lims.append("market timestamps are vendor-asserted (T1), never witnessed closing lines")
    if not b.get("pending") and tcfg.get("granular_stat"):
        lims.append(f'cold-start rows excluded from lagged baselines: '
                    f'{b["row"].get("n_cold_start_excluded", 0):,}')
    lims.append("prediction error ≠ threshold distance ≠ probability quality ≠ market advantage ≠ betting profitability")
    parts.append("<br>".join(lims) + "</div>")

    parts.append("<div><h4>Provenance</h4>")
    provs = []
    if r["model"] is not None:
        provs.append("model: " + esc(r["model"]["title"]))
    if not b.get("pending"):
        provs.append("baseline: " + esc(b["title"]))
    if mk.get("state") == "measured":
        provs.append("market: " + esc(mk["title"]))
    if not provs:
        provs.append("no evaluated artifact yet; see metrics.json declared-pending rows")
    parts.append('<br>'.join(f'<span style="word-break:break-word">{p}</span>' for p in provs))
    parts.append("</div></div>")
    return "".join(parts)


# ------------------------------------------------------------ leaderboard render
LB_COLUMNS = [
    ("target", "Prediction target", "asc"),
    ("score", "Prediction Score", "desc"),
    ("miss", "Typical Miss", "asc"),
    ("range", "Within Target Range", "desc"),
    ("improve", "Improvement vs Basic Model", "desc"),
    ("market", "Market Advantage", "desc"),
    ("n", "Sample", "desc"),
    ("evidence", "Evidence", "asc"),
    ("updated", "Last Updated", "desc"),
]


def render_leaderboard(rows, cfg, metrics, gm, gc):
    parts = []
    a = parts.append
    ordered = sorted(rows, key=default_sort_key)

    a('<section class="predsec">')
    a('<h2>Prediction Leaderboard — one row per target · click any column to sort · rows expand for full evidence</h2>')
    a('<div class="controls">')
    a('<label>Show <select id="f-level"><option value="all">All targets</option>'
      '<option value="player">Player targets</option><option value="team">Team targets</option>'
      '<option value="game">Game targets</option></select></label>')
    a('<label><input type="checkbox" id="f-verified"> Verified only</label>')
    a('<label><input type="checkbox" id="f-market"> Market-covered only</label>')
    a('<label>Season <select id="f-season"><option value="pooled">All seasons (pooled)</option></select></label>')
    a('<label>Cutoff <select id="f-cutoff"><option value="pregame_pooled">Pregame (pooled archive)</option></select></label>')
    a(f'<span class="sub" style="font-size:11.5px;color:var(--ink-3)">{esc(cfg["defaults"]["filter_note"])}</span>')
    a('</div>')
    a('<div class="tablewrap"><table id="lb-table" data-score-version="' + esc(SCORE_VERSION) + '">')
    a('<thead><tr>' + ''.join(
        f'<th class="sortable" data-key="{k}" data-default-dir="{d}" scope="col">{esc(label)}</th>'
        for k, label, d in LB_COLUMNS) + '</tr></thead><tbody>')

    for r in ordered:
        attrs = {
            "target": r["label"].lower(),
            "score": "" if r["score"] is None else r["score"],
            "miss": "" if r["miss"] is None else f'{r["miss"]:.6f}',
            "range": "",
            "improve": "" if r["improve_num"] is None else r["improve_num"],
            "market": "" if r["market_num"] is None else r["market_num"],
            "n": "" if r["sample_n"] is None else r["sample_n"],
            "evidence": r["badge_rank"],
            "updated": r["updated"],
            "level": r["level"],
            "verified": r["verified"],
            "market-covered": r["market_covered"],
            "order": r["order"],
        }
        attr_s = " ".join(f'data-{k}="{esc(v)}"' for k, v in attrs.items())
        a(f'<tr class="lb-row" id="lb-{esc(r["id"])}" {attr_s}>')

        # target
        a(f'<td class="metric">{esc(r["label"])}<span class="sub">{esc(r["level"])}-level · {esc(r["unit"])}</span>'
          f'<button class="lb-expand" type="button" data-for="lb-{esc(r["id"])}" aria-expanded="false">+ details</button></td>')

        # score
        if r["score"] is not None:
            score_title = (f"Prediction Score {r['score']} ({r['band']}) | formula {SCORE_VERSION}: "
                           f"score = clamp(50 + 100*skill, 0, 100), skill = (baseline_error - model_error)/baseline_error | "
                           f"model error: {r['model']['error']} | baseline error: {r['baseline']['error']} | "
                           f"baseline: {r['baseline']['name']} | universe: {r['model']['universe']} | n: {r['model']['n']} | "
                           + str(r["model"]["title"]))
            a(f'<td title="{esc(score_title)}"><span class="scorebig">{r["score"]}</span>'
              f'<span class="bandtag">{esc(r["band"])}</span>'
              f'<span class="sub">{esc(r["subtext"])}</span></td>')
        else:
            a(f'<td>{chip("tbd", "TBD", r["score_reason"])}'
              f'<span class="sub">{esc(r["subtext"])}</span></td>')

        # typical miss
        miss_title = r["model"]["title"] if r["model"] is not None else "our model has not been evaluated on this target yet"
        a(f'<td title="{esc(miss_title)}">{r["miss_display"]}</td>')

        # within range
        a(f'<td>{r["range_display"]}</td>')

        # improvement
        a(f'<td>{r["improve_display"]}</td>')

        # market advantage
        a(f'<td>{r["market_display"]}</td>')

        # sample
        a(f'<td><span class="num">{r["sample_display"]}</span></td>')

        # evidence
        a(f'<td>{chip(BADGE_CHIP_KIND[r["badge"]], r["badge"], r["badge_title"])}</td>')

        # updated
        a(f'<td><span class="sub">{esc(r["updated"])}</span></td>')
        a('</tr>')

        # detail row
        a(f'<tr class="lb-detail" data-for="lb-{esc(r["id"])}" data-open="0" hidden>'
          f'<td colspan="{len(LB_COLUMNS)}">{detail_html(r, cfg, metrics, gm, gc)}</td></tr>')

    a('</tbody></table></div>')
    a('<p class="foot">Default order: strongest verified evidence first, then highest Prediction Score, '
      'then evaluated-but-unscored rows, then unevaluated targets. Blank cells always sort last, in both '
      'directions. Filters only hide rows — they never change a number.</p>')
    a('</section>')
    return "\n".join(parts)


# ------------------------------------------------------------ summary cards
def render_cards(rows, cfg, gm):
    ordered = sorted(rows, key=default_sort_key)
    scored = [r for r in ordered if r["score"] is not None]
    parts = []
    a = parts.append
    a('<section class="predsec">')
    a('<h2>At a glance</h2>')
    a('<div class="tiles">')

    # Best Prediction
    if scored:
        r = scored[0]
        a(f'<div class="tile"><div class="k">Best Prediction</div>'
          f'<div class="v">{r["score"]} <small>{esc(r["band"])}</small></div>'
          f'<div class="d">{esc(r["label"])} — {esc(r["subtext"])}. '
          f'{chip(BADGE_CHIP_KIND[r["badge"]], r["badge"], r["badge_title"])}</div></div>')
    else:
        measured = [r for r in ordered if r["model"] is not None]
        extra = ""
        if measured:
            m = measured[0]
            extra = (f' Closest measured model result so far: {esc(m["label"].lower())} — {esc(m["subtext"])} '
                     f'({esc(m["badge"].lower())}; matched-baseline comparison pending).')
        a(f'<div class="tile"><div class="k">Best Prediction</div>'
          f'<div class="v">{chip("tbd", "TBD")}</div>'
          f'<div class="d">No target has a Prediction Score yet — scores unlock after the first audited '
          f'blind evaluation (P37→P40), never before.{extra}</div></div>')

    # Largest Market Advantage
    advs = [r for r in ordered if r["market_num"] is not None
            and r["market_num"] > cfg["market_advantage"]["label_thresholds"]["market_level_abs_max"] * 100]
    if advs:
        r = max(advs, key=lambda x: (x["market_num"], -x["order"]))
        a(f'<div class="tile"><div class="k">Largest Market Advantage</div>'
          f'<div class="v">{r["market_num"]:+.1f}<small>%</small></div>'
          f'<div class="d">{esc(r["label"])} — lower error than market consensus on a matched universe.</div></div>')
    else:
        a('<div class="tile"><div class="k">Largest Market Advantage</div>'
          f'<div class="v">{chip("tbd", "Not yet demonstrated")}</div>'
          '<div class="d">No model-vs-market comparison on a matched, timestamp-aligned universe exists yet. '
          'Market benchmarks are measured and waiting.</div></div>')

    # Most Reliable Result
    candidates = []
    for r in rows:
        if r["model"] is not None and r["model"].get("n"):
            candidates.append((r["model"]["n"], 0, r["order"], r, "our model", str(r["model"]["evidence_class"])))
        if not r["baseline"].get("pending"):
            candidates.append((r["baseline"]["n"], 1, r["order"], r, "basic benchmark (" + r["baseline"]["name"] + ")",
                               str(r["baseline"]["row"].get("evidence_class", "NAIVE_BASELINE"))))
        if r["market"].get("state") == "measured":
            candidates.append((r["market"]["n"], 2, r["order"], r, "market benchmark",
                               str(r["market"].get("row", {}).get("evidence_class", "MARKET (T1 vendor-asserted)"))))
    if candidates:
        n, _, _, r, kind, ecls = sorted(candidates, key=lambda c: (-c[0], c[1], c[2]))[0]
        a(f'<div class="tile"><div class="k">Most Reliable Result</div>'
          f'<div class="v">{n:,} <small>{esc(LEVEL_SAMPLE_UNITS[r["level"]] if kind == "our model" else "player-games" if r["level"] == "player" else "games")}</small></div>'
          f'<div class="d">{esc(r["label"])} — {esc(kind)} · evidence class {esc(ecls.split(" — ")[0].split(" -- ")[0])}.</div></div>')
    else:
        a('<div class="tile"><div class="k">Most Reliable Result</div>'
          f'<div class="v">{chip("tbd", "TBD")}</div><div class="d">No evaluated result on file.</div></div>')

    # Betting Edge -- prospective executable edge status ONLY; predictive
    # accuracy is never substituted for betting profitability.
    a('<div class="tile"><div class="k">Betting Edge</div>'
      f'<div class="v">{chip("tbd", "Not yet demonstrated")}</div>'
      '<div class="d">Prospective sample accumulating. This card reports executable betting performance only '
      '— it will never repackage predictive accuracy as profitability. States: Not yet demonstrated → '
      'Promising — not yet confirmed → Verified — see betting performance.</div></div>')

    a('</div>')
    a('</section>')
    return "\n".join(parts)


# ------------------------------------------------------------ methodology
def render_methodology(cfg, lifecycle):
    ps = cfg["prediction_score"]
    ma = cfg["market_advantage"]
    parts = []
    a = parts.append
    a('<section class="foot" id="score-methodology">')
    a('<h2>How the Prediction Score works — frozen before any model result was visible</h2>')
    a(f'<p><span class="mark">Formula ({esc(ps["version"])}, frozen {esc(cfg["frozen_utc"])}).</span> '
      f'<code>{esc(ps["formula"])}</code> — {esc(ps["interpretation"])} Rounding: {esc(ps["rounding"])}.</p>')
    a('<p><span class="mark">Eligibility.</span> A score exists only when our model has an evaluated run AND the '
      'declared baseline is evaluated on the identical universe (' + esc(ps["eligibility"]["universe_match_rule"]) +
      '), with at least ' + ", ".join(f'{v} {esc(ps["eligibility"]["min_n_units"][k])} ({k})'
                                      for k, v in ps["eligibility"]["min_n_by_level"].items()) +
      '. ' + " ".join(esc(x) for x in ps["never_rules"]) + '</p>')
    a('<p><span class="mark">Bands.</span> ' + " · ".join(
        f'<b>{b["min"]}–{b["max"]} {esc(b["label"])}</b> ({esc(b["plain"])})' for b in ps["bands"]) + '</p>')
    a('<p><span class="mark">Tolerance bands (frozen; never tuned to improve presentation).</span> ' + " · ".join(
        f'{esc(k)} ±{v["tolerance"]} {esc(v["unit"])}' for k, v in cfg["tolerance_bands"]["bands"].items()) +
      '. Targets without a declared band show “no target range declared”.</p>')
    a(f'<p><span class="mark">Market Advantage ({esc(ma["version"])}).</span> <code>{esc(ma["formula"])}</code>. '
      + esc(ma["never_collapse_rule"]) + ' Requirements: ' + "; ".join(esc(x) for x in ma["eligibility"]) + '. Labels: '
      + ", ".join(esc(x) for x in ma["labels"]) + '.</p>')
    a('<p><span class="mark">Distinct axes, never merged.</span> prediction error ≠ threshold distance ≠ '
      'probability quality ≠ market advantage ≠ betting profitability. A prop line is a threshold, not '
      'automatically a point projection.</p>')
    a('<p><span class="mark">Evidence badges.</span> ' + " · ".join(
        f'<b>{esc(k)}</b>: {esc(v)}' for k, v in cfg["evidence_badges"]["definitions"].items()) +
      '. ' + esc(cfg["evidence_badges"]["never_sealed_rule"]) + '.</p>')
    a('</section>')

    # player leaderboard locked state
    pl = cfg["player_leaderboard"]
    a('<section>')
    a('<h2>Player-level leaderboards</h2>')
    a(f'<div class="locked">{chip("pend", pl["status"])} <b>{esc(pl["locked_text"])}</b><br>'
      'Rankings unlock only when every requirement holds: ' + "; ".join(esc(x) for x in pl["unlock_requirements"]) +
      '. Rule: ' + esc(pl["never_rule"]) + '. Schema is ready: ' + esc(", ".join(pl["schema_ready"]["row"])) + '.</div>')
    a('</section>')
    return "\n".join(parts)


def build_granular_section(granular_metrics, granular_coverage):
    """D037 GRANULAR PLAYER OUTCOMES section.

    One row per stat; columns are Our model | Best naive baseline |
    Market (threshold, player_points only) | Notes. Every number displayed
    here is read verbatim from granular/player_granular_metrics.json /
    granular/player_granular_coverage.json -- this function only selects,
    formats and labels.
    """
    gm = granular_metrics
    gc = granular_coverage
    market_points = gm["market_threshold"]["points"]["pooled_books"]["pooled"]

    pend_title = (
        "Lifecycle: BUILT → AUDITED → FITTING → EVALUATED/SEALED → ADJUDICATED. "
        "Blind fits have not run for the granular player targets."
    )
    pending_chip = chip("pend", PENDING, pend_title, long=True)
    legacy_chip = chip("warn", "LEGACY RECEIPTABLE - VERIFICATION QUEUED", LEGACY_PROBE_NOTE, long=True)
    not_captured = chip(
        "warn", "NOT CAPTURED (single-family archive)",
        "The props archive holds exactly one market family: player_points. No rebounds, "
        "assists, steals, blocks, threes, turnovers or minutes prop lines exist in it.",
        long=True,
    )

    parts = []
    a = parts.append
    a('<section class="predsec">')
    a('<h2>Granular player outcomes (D037) — model vs naive floor vs market, independent of moneyline pricing</h2>')
    a(f'<p class="foot">Player-game universe: <b>{gc["n_player_games_total"]:,}</b> player-games, seasons '
      f'{gc["seasons"][0]}–{gc["seasons"][-1]} ({gc["unique_game_dates"]:,} unique calendar dates, '
      f'{gc["unique_games"]:,} unique games). One row per stat; naive baselines are strictly-lagged and computed '
      f'from owned gamelogs; nothing on this page is recomputed from the granular inputs, only selected and labeled.</p>')
    a('<div class="tablewrap"><table>')
    a('<thead><tr>'
      '<th style="width:14%">Stat</th>'
      '<th><span class="dot" style="background:var(--us)"></span>Our model</th>'
      '<th><span class="dot" style="background:var(--best)"></span>Best naive baseline</th>'
      '<th><span class="dot" style="background:var(--mkt)"></span>Market (threshold, player_points only)</th>'
      '<th style="width:20%">Notes</th></tr></thead><tbody>')

    for stat_key, label in GRANULAR_STATS:
        best_variant, best_row = best_naive_pooled(gm, stat_key)
        naive_title = naive_prov_title(best_row, gm)
        naive_cell = (
            f'<span class="num">{best_row["mae"]:.4f} MAE</span>'
            f'<span class="sub">{esc(NAIVE_VARIANT_LABELS[best_variant])} · '
            f'95% CI [{best_row["mae_ci95"]["lo"]:.4f}, {best_row["mae_ci95"]["hi"]:.4f}] · '
            f'n={best_row["n_player_games"]:,} · {esc(best_row["evidence_class"])} ⁹</span> '
            f'{chip("ok", "NAIVE_BASELINE", naive_title)}'
        )

        our_cell = f'{pending_chip} {legacy_chip}' if stat_key in LEGACY_PROBED_STATS else pending_chip

        if stat_key == "points":
            mkt_title = market_prov_title(market_points, gm)
            mkt_cell = (
                f'<span class="num">{market_points["devig_ou_accuracy"]:.4f} OU acc.</span>'
                f'<span class="sub">de-vigged Brier {market_points["devig_brier"]:.4f} · '
                f'threshold MAE {market_points["threshold_mae"]:.4f} (line-vs-outcome distance, '
                f'NOT a projection MAE ¹⁰) · n={market_points["n_player_games"]:,} player-games / '
                f'{market_points["n_quote_rows"]:,} quote rows</span> '
                f'{chip("ok", "MEASURED — T1 VENDOR-ASSERTED", mkt_title)}'
            )
        else:
            mkt_cell = not_captured

        if stat_key == "points":
            notes = ("Threshold metrics are primary per D036 point 5. " + LEGACY_PROBE_NOTE)
        elif stat_key == "minutes":
            notes = LEGACY_PROBE_NOTE
        else:
            notes = (
                "No legacy artifact registered for this target -- the legacy lane never "
                "targeted it, so the column is ABSENT, not unreceipted (PROBE_LEGACY.md)."
            )

        a(f'<tr><td class="metric">{esc(label)}</td>'
          f'<td>{our_cell}</td>'
          f'<td>{naive_cell}</td>'
          f'<td>{mkt_cell}</td>'
          f'<td class="foot">{esc(notes)}</td></tr>')

    a('</tbody></table></div>')
    a('<p class="foot"><span class="mark">⁹ Naive baseline selection.</span> Best of three strictly-lagged '
      'baselines by pooled MAE: trailing-5 mean, season-to-date mean, league mean -- all three computed '
      'pregame-by-construction from owned gamelogs, full provenance in the popover.</p>')
    a('<p class="foot"><span class="mark">¹⁰ Threshold vs projection.</span> A market line is a threshold, '
      'not a projection: threshold MAE measures the distance between the posted line and the realized stat and, '
      'per D036 point 5, is NOT comparable to a projection MAE. De-vigged OU accuracy and Brier are the primary, '
      'comparable market quantities.</p>')
    a('</section>')
    return "\n".join(parts)


def granular_coverage_tile(granular_metrics, granular_coverage):
    """Seven-counts coverage tile for the granular player archive (D037),
    selected verbatim from granular/player_granular_coverage.json's
    market_join_audit block -- never recomputed."""
    gc = granular_coverage
    mja = gc["market_join_audit"]
    per_book = granular_metrics["market_threshold"]["points"]["per_book"]
    g7 = {
        "n_raw_prop_rows": mja["n_raw_rows"],
        "n_quote_rows_matched": mja["n_quote_rows_matched"],
        "n_quote_rows_unmatched": mja["n_quote_rows_unmatched"],
        "n_player_games_matched": mja["n_matched_player_games"],
        "n_player_games_unmatched": mja["n_unmatched_player_games"],
        "unique_books": len(per_book),
        "unique_market_families": len(mja["market_families_supported"]),
    }
    return (
        '<div class="tile"><div class="k">Granular player archive · player_granular_coverage.json</div><div class="d">'
        f'<b>{gc["n_player_games_total"]:,}</b> player-game universe (seasons {gc["seasons"][0]}–{gc["seasons"][-1]}) · '
        f'<b>{g7["n_raw_prop_rows"]:,}</b> raw prop rows · '
        f'<b>{g7["n_quote_rows_matched"]:,}</b> quote rows matched · '
        f'<b>{g7["n_quote_rows_unmatched"]:,}</b> quote rows unmatched · '
        f'<b>{g7["n_player_games_matched"]:,}</b> player-games matched · '
        f'<b>{g7["n_player_games_unmatched"]:,}</b> player-games unmatched · '
        f'<b>{g7["unique_books"]}</b> books · '
        f'<b>{g7["unique_market_families"]}</b> market family (player_points only)</div></div>'
    )


def build_evidence_layer(coverage, metrics, lifecycle, granular_metrics, granular_coverage):
    """The full D036/D037 audit surface, preserved verbatim beneath the
    leaderboard: raw headline tiles, model-vs-market table, granular player
    outcomes, operational progress, coverage counts, the dropped-cells honesty
    log, per-cell provenance footnotes, and the unlock pipeline."""
    inc = get_row(metrics, "incumbent_operational_team_attributed_turnovers")
    inc_in = get_row(metrics, "incumbent_intrinsic_team_attributed_turnovers")
    bb = get_row(metrics, "bookie_baseline")
    rank = get_row(metrics, "fixed_identity_book_ranking")
    naive = [get_row(metrics, f"naive_baseline_{k}") for k in ("league_mean", "rolling_team_average", "last_five_games")]
    props = coverage["props_archive"]
    feat = coverage["featured_archive"]
    p7 = props["seven_counts"]
    f7 = feat["seven_counts"]

    rows = bb["metrics"]["rows"]
    late_x = pooled(rows, "LATE", "cross_book")
    early_x = pooled(rows, "EARLY", "cross_book")
    late_b = pooled(rows, "LATE", "best_book")

    bb_title = prov_title("bookie baseline (re-emitted verbatim)", bb) + " | CAVEAT: " + bb["caveat_text_verbatim"]
    inc_title = prov_title("frozen incumbent", inc)
    inc_in_title = prov_title("frozen incumbent, intrinsic track", inc_in)
    cutoff_note = ("Vendor-asserted EARLY (~16:00Z) and LATE (~23:30Z) request classes are the ONLY cutoffs this tape "
                   "supports. Never opening or closing lines. No timing, latency, reaction or CLV inference.")
    pend_title = ("Lifecycle: BUILT → AUDITED → FITTING → EVALUATED/SEALED → ADJUDICATED. Blind fits have not run; "
                  "this cell opens only after P37 audit, P38 blind fits, P39 integrity and P40 adjudication.")
    rank_title = prov_title("fixed-identity book ranking", rank) + " | " + rank["declared_reason"]
    naive_title = naive[0]["evidence_class"]

    pending_chip = chip("pend", PENDING, pend_title, long=True)
    na = chip("na", "N/A")
    dp = chip("tbd", "DECLARED-PENDING", rank_title)

    mkt_sub = f'vendor-asserted LATE class · bias {late_x["total"]["bias"]:+.2f} · n={late_x["total"]["n"]:,}'

    parts = []
    a = parts.append

    # headline tiles ---------------------------------------------------------
    a('<section class="predsec">')
    a('<h2>Headline raw numbers — predictive evidence only</h2>')
    a('<div class="tiles">')
    a(f'<div class="tile"><div class="k">Frozen incumbent · team-attributed turnovers</div>'
      f'<div class="v">{inc["metrics"]["mae"]:.4f} <small>MAE</small></div>'
      f'<div class="d">Arm D (EWMA-shrunk), operational track, n={inc["metrics"]["n_team_games"]:,} team-games, seasons 2021–2026. '
      f'The only receipted model number today — and it is a TURNOVER MAE, not a possession MAE (the old label was wrong). '
      f'{chip("ok", "MEASURED", inc_title)} <span class="prov" title="{esc(inc_title)}">ⓘ provenance</span></div></div>')
    a(f'<div class="tile"><div class="k">Market baseline · LATE snapshot class, pooled 2022–26</div>'
      f'<div class="v">{late_x["spread"]["mae"]:.2f} <small>spread MAE</small></div>'
      f'<div class="d">Totals {late_x["total"]["mae"]:.2f} MAE · de-vigged Brier {late_x["moneyline"]["brier"]:.3f} · '
      f'n={late_x["spread"]["n"]:,}/{late_x["total"]["n"]:,}/{late_x["moneyline"]["n"]:,}. Vendor-asserted snapshot class, never a closing line. '
      f'{chip("ok", "MEASURED — T1 VENDOR-ASSERTED", bb_title)} <span class="prov" title="{esc(bb_title)}">ⓘ provenance</span></div></div>')
    cf = lifecycle["challenger_field"]
    cf_state = cf.get("lifecycle_state", "BUILT")
    cf_kind = {"BUILT": "run", "AUDITED": "run", "FITTING": "run",
               "EVALUATED/SEALED": "run", "ADJUDICATED": "ok"}.get(cf_state, "run")
    cf_value = pending_chip if cf_state in ("BUILT", "AUDITED", "FITTING") else chip(cf_kind, cf_state, cf["source"]["record"])
    a(f'<div class="tile"><div class="k">Challenger field · 22 arms</div>'
      f'<div class="v">{cf_value}</div>'
      f'<div class="d">{esc(cf["statement"])} '
      f'{chip(cf_kind, cf_state, cf["source"]["record"])}</div></div>')
    tpc = get_row(metrics, "team_possessions_champion")
    tpc_title = prov_title("frozen incumbent, VERIFIED possessions null (P40 adjudication)", tpc)
    a(f'<div class="tile"><div class="k">Team possessions (regulation-equivalent) · VERIFIED</div>'
      f'<div class="v">{tpc["metrics"]["mae"]:.4f} <small>MAE</small></div>'
      f'<div class="d">Frozen incumbent K0_MATCHED null, five-fold blind walk-forward, n={tpc["metrics"]["n_team_games"]:,} pooled '
      f'OOF rows / {tpc["metrics"]["n_clusters"]:,} clusters. Supersedes the 2.9675 turnover-lane figure above with correct '
      f'labeling of BOTH numbers (D042) — this is the possessions number, that one is turnovers; never the same target. '
      f'{chip("ok", "VERIFIED", tpc_title)} <span class="prov" title="{esc(tpc_title)}">ⓘ provenance</span></div></div>')
    a(f'<div class="tile"><div class="k">Props archive coverage (re-audited)</div>'
      f'<div class="v">{p7["unique_calendar_dates_with_prop_lines"]:,} <small>unique calendar dates</small></div>'
      f'<div class="d">{p7["unique_event_ids_with_prop_lines"]:,} events · {p7["unique_event_snapshot_pairs_with_prop_lines"]:,} event-snapshot pairs · '
      f'{p7["unique_player_games"]:,} player-games · {p7["normalized_prop_rows"]:,} normalized prop rows · {p7["unique_books"]} books · '
      f'{p7["unique_market_families"]} market family ({esc(", ".join(props["market_families"]))}). '
      f'{chip("warn", "T1 VENDOR-ASSERTED", props["tier_caveat"])}</div></div>')
    a('</div>')
    a('</section>')

    # main table ---------------------------------------------------------------
    a('<section class="predsec">')
    a('<h2>Raw scoreboard — model vs market vs reality</h2>')
    a('<div class="tablewrap"><table>')
    a('<thead><tr>'
      '<th style="width:24%">Metric (vs actual outcome)</th>'
      '<th><span class="dot" style="background:var(--us)"></span>Our model</th>'
      '<th><span class="dot" style="background:var(--mkt)"></span>Market avg</th>'
      '<th><span class="dot" style="background:var(--best)"></span>Best book</th>'
      '<th><span class="dot" style="background:var(--worst)"></span>Worst book</th>'
      '<th style="width:17%">Head-to-head</th></tr></thead><tbody>')

    a('<tr><th colspan="6">Team level</th></tr>')

    # incumbent row
    a('<tr><td class="metric">Team-attributed turnovers<span class="sub">frozen incumbent — relabeled from the old '
      '&quot;Possessions&quot; cell, which its receipt does not support ¹</span></td>'
      f'<td><span class="num">{inc["metrics"]["mae"]:.4f} MAE</span>'
      f'<span class="sub">bias {inc["metrics"]["bias"]:+.4f} · RMSE {inc["metrics"]["rmse"]:.4f} · n={inc["metrics"]["n_team_games"]:,} team-games · '
      f'intrinsic track {inc_in["metrics"]["mae"]:.4f} (n={inc_in["metrics"]["n_team_games"]:,}) ²</span> '
      f'{chip("ok", "MEASURED", inc_title)}</td>'
      f'<td>{na}<span class="sub">not directly priced by the books</span></td>'
      f'<td>{na}</td><td>{na}</td><td>{na}</td></tr>')

    # possessions champion (D042: P40 primary adjudication, VERIFIED)
    a('<tr><td class="metric">Team possessions (regulation-equivalent)<span class="sub">frozen incumbent\'s '
      'K0_MATCHED null, VERIFIED by P40 blind walk-forward adjudication — the correctly-labeled possessions '
      'number the turnover row above is NOT ¹¹</span></td>'
      f'<td><span class="num">{tpc["metrics"]["mae"]:.4f} MAE</span>'
      f'<span class="sub">n={tpc["metrics"]["n_team_games"]:,} pooled OOF rows / {tpc["metrics"]["n_clusters"]:,} clusters · '
      f'five D006 test folds · challenger field: {tpc["adjudication_summary"]["n_pass_primary"]}/{tpc["adjudication_summary"]["fitted_elements"]} elements promoted</span> '
      f'{chip("ok", "VERIFIED", tpc_title)}</td>'
      f'<td>{na}<span class="sub">not directly priced by the books</span></td>'
      f'<td>{na}</td><td>{na}</td><td>{na}</td></tr>')

    # game total
    a('<tr><td class="metric">Game total<span class="sub">combined points</span></td>'
      f'<td>{pending_chip}</td>'
      f'<td><span class="num">{late_x["total"]["mae"]:.4f} MAE</span><span class="sub">{esc(mkt_sub)} · '
      f'EARLY class {early_x["total"]["mae"]:.4f}, n={early_x["total"]["n"]:,} ³</span> {chip("ok", "MEASURED", bb_title)}</td>'
      f'<td><span class="num">{late_b["total"]["mae"]:.4f}</span><span class="sub">FanDuel — single FIXED pre-declared identity, not a ranking · '
      f'n={late_b["total"]["n"]:,} ⁴</span> {chip("ok", "MEASURED", bb_title)}</td>'
      f'<td>{dp}<span class="sub">per-book rows absent from baseline outputs ⁴</span></td>'
      f'<td>{chip("tbd", "TBD", "requires identical as-of universes and paired game-clustered uncertainty (D036 point 7)")}<span class="sub">needs blind fits first ⁵</span></td></tr>')

    # spread
    a('<tr><td class="metric">Margin (spread)<span class="sub">final scoring margin</span></td>'
      f'<td>{pending_chip}</td>'
      f'<td><span class="num">{late_x["spread"]["mae"]:.4f} MAE</span><span class="sub">vendor-asserted LATE class · bias {late_x["spread"]["bias"]:+.2f} · '
      f'n={late_x["spread"]["n"]:,} · EARLY class {early_x["spread"]["mae"]:.4f}, n={early_x["spread"]["n"]:,} ³</span> {chip("ok", "MEASURED", bb_title)}</td>'
      f'<td><span class="num">{late_b["spread"]["mae"]:.4f}</span><span class="sub">FanDuel fixed identity · n={late_b["spread"]["n"]:,} ⁴</span> {chip("ok", "MEASURED", bb_title)}</td>'
      f'<td>{dp}<span class="sub">⁴</span></td>'
      f'<td>{chip("tbd", "TBD", "requires identical as-of universes")}<span class="sub">⁵</span></td></tr>')

    # win prob
    a('<tr><td class="metric">Win probability<span class="sub">de-vigged Brier · log-loss · 10-bin calibration in source artifact</span></td>'
      f'<td>{pending_chip}</td>'
      f'<td><span class="num">{late_x["moneyline"]["brier"]:.4f} Brier</span><span class="sub">log-loss {late_x["moneyline"]["log_loss"]:.4f} · de-vigged '
      f'({esc(bb["vig_method"])}) · vendor-asserted LATE class · n={late_x["moneyline"]["n"]:,} · EARLY {early_x["moneyline"]["brier"]:.4f}, n={early_x["moneyline"]["n"]:,} ³</span> '
      f'{chip("ok", "MEASURED", bb_title)}</td>'
      f'<td><span class="num">{late_b["moneyline"]["brier"]:.4f}</span><span class="sub">FanDuel fixed identity · LL {late_b["moneyline"]["log_loss"]:.4f} · n={late_b["moneyline"]["n"]:,} ⁴</span> {chip("ok", "MEASURED", bb_title)}</td>'
      f'<td>{dp}<span class="sub">⁴</span></td>'
      f'<td>{chip("tbd", "TBD", "requires identical as-of universes")}<span class="sub">⁵</span></td></tr>')

    # team total
    a('<tr><td class="metric">Team total<span class="sub">single-team points</span></td>'
      f'<td>{chip("tbd", "TBD", "no model artifact exists for this target")}</td>'
      f'<td>{dp}<span class="sub">not computed in the baseline artifact; never inferred</span></td>'
      f'<td>{dp}</td><td>{dp}</td><td>{chip("tbd", "TBD")}</td></tr>')

    # naive baselines
    a('<tr><td class="metric">Naive baselines<span class="sub">league mean · rolling team average · last-5 — required on every target ⁶</span></td>'
      f'<td colspan="5">{chip("tbd", "DECLARED-PENDING", naive_title)}'
      '<span class="sub">emitted as declared-pending rows in metrics.json — walk-forward-clean computation was not performed this session and is never invented</span></td></tr>')

    a('<tr><th colspan="6">Player level</th></tr>')

    # player points
    a('<tr><td class="metric">Player points<span class="sub">de-vigged over/under probability is the primary quantity ⁷</span></td>'
      f'<td>{chip("tbd", "TBD", "props are last in the pipeline by design; no model artifact exists")}</td>'
      f'<td>{dp}<span class="sub">archive on disk: {p7["unique_calendar_dates_with_prop_lines"]:,} unique calendar dates · '
      f'{p7["unique_event_snapshot_pairs_with_prop_lines"]:,} event-snapshot pairs · {p7["normalized_prop_rows"]:,} normalized rows · '
      f'{p7["unique_books"]} books (T1 vendor-asserted); accuracy-vs-outcome not yet computed ⁸</span></td>'
      f'<td>{dp}</td><td>{dp}</td><td>{chip("tbd", "TBD")}</td></tr>')

    # other prop families
    a('<tr><td class="metric">Player rebounds / assists / threes<span class="sub">per prop family</span></td>'
      f'<td>{chip("tbd", "TBD")}</td>'
      f'<td>{chip("warn", "NOT CAPTURED", "re-audit of the props archive found exactly one market family: player_points. No rebounds, assists or threes prop lines exist in it. The prior claim (verified real May 2023 onward) was wrong for these families.")}'
      '<span class="sub">props archive holds <b>player_points only</b> — the old claim for these families is withdrawn ⁸</span></td>'
      f'<td>{na}</td><td>{na}</td><td>{na}</td></tr>')

    # minutes
    a('<tr><td class="metric">Projected minutes<span class="sub">vs actual minutes</span></td>'
      f'<td>{chip("tbd", "TBD", "reconstruction planned; no artifact exists")}</td>'
      f'<td>{na}<span class="sub">market prices props, not minutes</span></td>'
      f'<td>{na}</td><td>{na}</td><td>{chip("tbd", "TBD")}</td></tr>')

    a('</tbody></table></div>')
    a('</section>')

    # D037 granular player outcomes section --------------------------------------
    a(build_granular_section(granular_metrics, granular_coverage))

    # operational section — visually distinct -----------------------------------
    a('<section class="opsec">')
    a('<h2>Operational progress — NOT predictive evidence</h2>')
    a('<div class="log">')
    for item in lifecycle["operational_progress"]:
        kind = "ok" if item["chip"] == "MEASURED" else "run"
        a(f'<div>{chip(kind, item["chip"], item["source"])} {esc(item["text"])} '
          f'<span class="prov" title="{esc(item["source"])}">ⓘ</span></div>')
    a('</div>')
    a(f'<p class="foot">Lifecycle ladder: <b>{esc(" → ".join(lifecycle["ladder"]))}</b>. {esc(lifecycle["sealed_replacement_rule"])}.</p>')
    a('</section>')

    # coverage detail ------------------------------------------------------------
    a('<section>')
    a('<h2>Data coverage — the seven counts (the phrase “game days” is banned)</h2>')
    a('<div class="tiles">')
    a(f'<div class="tile"><div class="k">Props archive · {esc(props["path"].split("/")[-1])}</div><div class="d">'
      f'<b>{p7["unique_calendar_dates_with_prop_lines"]:,}</b> unique calendar dates with prop lines '
      f'(of {props["context_counts"]["unique_calendar_dates_queried"]:,} queried) · '
      f'<b>{p7["unique_event_ids_with_prop_lines"]:,}</b> unique events · '
      f'<b>{p7["unique_event_snapshot_pairs_with_prop_lines"]:,}</b> unique event-snapshot pairs · '
      f'<b>{p7["unique_player_games"]:,}</b> unique player-games · '
      f'<b>{p7["normalized_prop_rows"]:,}</b> normalized prop rows · '
      f'<b>{p7["unique_books"]}</b> books · '
      f'<b>{p7["unique_market_families"]}</b> market family ({esc(", ".join(props["market_families"]))}) · '
      f'dates with lines {esc(props["date_range_with_lines"][0])} → {esc(props["date_range_with_lines"][1])} · '
      f'sha256 <code>{esc(props["sha256"][:16])}…</code></div></div>')
    a(f'<div class="tile"><div class="k">Featured archive · {esc(feat["path"].split("/")[-1])}</div><div class="d">'
      f'<b>{f7["unique_calendar_dates_requested"]:,}</b> unique calendar dates · '
      f'<b>{f7["unique_event_ids"]:,}</b> unique events · '
      f'<b>{f7["unique_event_snapshot_pairs"]:,}</b> unique event-snapshot pairs · '
      f'<b>{feat["snapshot_lines_total"]:,}</b> snapshot records · '
      f'<b>{f7["normalized_outcome_rows"]:,}</b> normalized outcome rows · '
      f'<b>{f7["unique_books"]}</b> books · '
      f'<b>{f7["unique_market_families"]}</b> market families ({esc(", ".join(feat["market_families"]))}) · '
      f'events commence {esc(feat["commence_time_range_of_events"][0][:10])} → {esc(feat["commence_time_range_of_events"][1][:10])} · '
      f'sha256 <code>{esc(feat["sha256"][:16])}…</code></div></div>')
    a(granular_coverage_tile(granular_metrics, granular_coverage))
    a('</div>')
    a(f'<p class="foot">{esc(props["tier_caveat"])}. The old “833 game days” figure is withdrawn: 833 is the count of event-snapshot records with a non-empty payload, not calendar dates. '
      f'The granular player archive (D037) player-game universe is <b>{granular_coverage["n_player_games_total"]:,}</b>, distinct from the props/featured event-snapshot counts above.</p>')
    a('</section>')

    # dropped cells ---------------------------------------------------------------
    a('<section class="foot" id="dropped-cells">')
    a('<h2>Cells dropped to their lifecycle state — honesty log</h2>')
    for c in lifecycle["cells_dropped"]:
        a(f'<p><span class="mark">DROPPED:</span> {esc(c["old_cell"])}<br>'
          f'<b>Why:</b> {esc(c["why_dropped"])}<br><b>Disposition:</b> {esc(c["disposition"])}</p>')
    a('</section>')

    # evidence notes / footnotes -----------------------------------------------------
    a('<section class="foot">')
    a('<h2>Evidence notes and per-cell provenance footnotes</h2>')
    a('<p><span class="mark">¹ Relabeled cell.</span> The receipted source identifies 2.9675 as the operational team-attributed turnover MAE of frozen Arm D, computed on the corrected Tier-A candidate universe. The prior “Possessions (reg-equiv)” label and “n=1,491 games” claim are not supported by the receipt and are withdrawn.</p>')
    a('<p><span class="mark">² Intrinsic track, defined.</span> ' + esc(inc_in["cutoff"]) + '</p>')
    a('<p><span class="mark">³ The only cutoffs the tape supports.</span> ' + esc(cutoff_note) + '</p>')
    a('<p><span class="mark">⁴ Fixed-identity rule.</span> Best/worst book means FIXED bookmaker identities ranked over the same matched universe and cutoff with a minimum common-sample threshold (declared: ≥200 matched games per book within a snapshot class). Per-game closest-book selection is prohibited. ' + esc(rank["declared_reason"]) + '</p>')
    a('<p><span class="mark">⁵ Head-to-head standard.</span> Comparisons only on identical as-of universes with paired game-clustered uncertainty; no mixed-timestamp comparisons, ever.</p>')
    a('<p><span class="mark">⁶ Naive baselines.</span> Required on every target (D036 point 6); shown as declared-pending until computed with walk-forward leakage discipline.</p>')
    a('<p><span class="mark">⁷ Threshold-first rule.</span> A single prop line yields a de-vigged over/under probability — the primary quantity. Threshold MAE is explicitly distinct from projection MAE. Implied means are null absent alternate lines or an out-of-sample-calibrated distribution.</p>')
    a('<p><span class="mark">⁸ Archive caveat (verbatim, frozen).</span> ' + esc(bb["caveat_text_verbatim"]) + '</p>')
    cps = get_row(metrics, "challenger_program_summary")
    a('<p><span class="mark">¹¹ Team possessions vs team-attributed turnovers.</span> These are two DIFFERENT '
      'targets on two different pooled universes; ADJUDICATION.json records explicitly that they are not '
      'cross-comparable (different row sets and pooling). Possessions is now VERIFIED (P40 blind walk-forward '
      'adjudication, D042); turnovers remains the PRELIMINARY receipt-cited development figure. Challenger '
      'program result: ' + esc(cps["plain_english"]) + ' Strongest lead: ' +
      esc(cps["metrics"]["strongest_lead"]["arm_id"]) + f' (delta_MAE {cps["metrics"]["strongest_lead"]["delta_mae_pooled"]:+.5f}, '
      f'uncorrected p={cps["metrics"]["strongest_lead"]["p_two_sided_uncorrected"]:.3f}); ' +
      esc(cps["metrics"]["strongest_lead"]["why_it_failed"]) + '</p>')

    for r in [inc, inc_in, bb, rank] + naive:
        p = r.get("provenance", {})
        src = p.get("source_artifact", {})
        a('<details class="provnote"><summary>' + esc(r["row_id"]) + ' — full provenance</summary><p>'
          + f'status: <b>{esc(r["status"])}</b> · evidence class: {esc(r["evidence_class"])}<br>'
          + f'model version: {esc(r.get("model_version"))}<br>target: {esc(r.get("target"))}<br>'
          + f'cutoff: {esc(r.get("cutoff"))}<br>universe: {esc(r.get("universe"))}<br>date range: {esc(r.get("date_range"))}<br>'
          + (f'source artifact: <code>{esc(src.get("path"))}</code> sha256 <code>{esc(src.get("sha256"))}</code><br>' if src else '')
          + f'commit lineage: <code>{esc(json.dumps(p.get("commit_lineage")) if p.get("commit_lineage") else None)}</code><br>'
          + f'computation timestamp: {esc(p.get("computation_timestamp_utc"))}'
          + '</p></details>')
    a('</section>')

    # pipeline ------------------------------------------------------------------
    a('<section>')
    a('<h2>Where the pending cells unlock</h2>')
    a('<div class="pipe">')
    for step in lifecycle["pipeline"]:
        cls = "step now" if step["now"] else "step"
        a(f'<div class="{cls}"><b>{esc(step["label"])}</b>{esc(step["text"])}</div>')
    a('</div>')
    a('</section>')
    return "\n".join(parts)


def build_html(coverage, metrics, lifecycle, score_config, granular_metrics, granular_coverage):
    cfg = score_config
    rows = build_leaderboard_rows(cfg, coverage, metrics, lifecycle, granular_metrics, granular_coverage)
    n_scored = sum(1 for r in rows if r["score"] is not None)

    parts = []
    a = parts.append
    a(f"<title>WNBA Prediction Leaderboard (generated)</title>\n<style>\n{CSS}</style>\n")
    a('<div class="wrap">')

    # header ---------------------------------------------------------------
    a('<header>')
    a('<div class="eyebrow">WNBA Program · Prediction Leaderboard · GENERATED — do not hand-edit</div>')
    a('<h1>What do we predict best — and how close are we to reality?</h1>')
    if n_scored == 0:
        a('<div class="stamp"><b>Status today:</b> benchmarks and market calibration are measured; our models are '
          'built and awaiting blind evaluation — no target has a Prediction Score yet, and none is invented.</div>')
    else:
        a(f'<div class="stamp"><b>Status today:</b> {n_scored} of {len(rows)} targets carry a Prediction Score '
          f'under the frozen {esc(SCORE_VERSION)} formula.</div>')
    a(f'<div class="stamp">Inputs computed <b>{esc(metrics["generated_utc"])}</b> (metrics) · <b>{esc(coverage["generated_utc"])}</b> (coverage) · '
      f'{esc(lifecycle["updated_note"])}</div>')
    a('</header>')

    # summary cards + leaderboard ---------------------------------------------
    a(render_cards(rows, cfg, granular_metrics))
    a(render_leaderboard(rows, cfg, metrics, granular_metrics, granular_coverage))

    # methodology & evidence layer ---------------------------------------------
    a('<div id="methodology">')
    a('<header><div class="eyebrow">Methodology &amp; evidence layer — every raw number, caveat and receipt</div></header>')
    a(render_methodology(cfg, lifecycle))
    a(build_evidence_layer(coverage, metrics, lifecycle, granular_metrics, granular_coverage))
    a('</div>')

    a('</div>\n')
    a(f'<script>\n{JS}\n</script>')
    return "\n".join(parts)


def main(indir=HERE, outdir=None):
    outdir = outdir or indir
    inputs = {
        "data_coverage.json": os.path.join(indir, "data_coverage.json"),
        "metrics.json": os.path.join(indir, "metrics.json"),
        "lifecycle.json": os.path.join(indir, "lifecycle.json"),
        "score_config.json": os.path.join(indir, "score_config.json"),
        "granular/player_granular_metrics.json": os.path.join(indir, "granular", "player_granular_metrics.json"),
        "granular/player_granular_coverage.json": os.path.join(indir, "granular", "player_granular_coverage.json"),
    }
    docs = {}
    for name, path in inputs.items():
        with open(path, encoding="utf-8") as f:
            docs[name] = json.load(f)

    page = build_html(
        docs["data_coverage.json"], docs["metrics.json"], docs["lifecycle.json"], docs["score_config.json"],
        docs["granular/player_granular_metrics.json"], docs["granular/player_granular_coverage.json"],
    )
    out_html = os.path.join(outdir, "scoreboard.html")
    with open(out_html, "w", encoding="utf-8", newline="\n") as f:
        f.write(page)

    generator_path = os.path.abspath(__file__)
    manifest = {
        "schema": "market_program/SCOREBOARD/manifest/1",
        "decision_authority": "D036_SCOREBOARD_MEASUREMENT_SEMANTICS point 8, D037_GRANULAR_PLAYER_SCOREBOARD, D038 Prediction Leaderboard (LEADERBOARD_SPEC.md)",
        "score_formula_version": SCORE_VERSION,
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "inputs": {name: {"path": path.replace("\\", "/"), "sha256": sha256_file(path)} for name, path in inputs.items()},
        "generator": {"path": generator_path.replace("\\", "/"), "sha256": sha256_file(generator_path)},
        "output": {"path": out_html.replace("\\", "/"), "sha256": sha256_file(out_html)},
    }
    out_manifest = os.path.join(outdir, "scoreboard_manifest.json")
    with open(out_manifest, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")
    print("wrote", out_html)
    print("wrote", out_manifest)
    return out_html, out_manifest


if __name__ == "__main__":
    indir = sys.argv[1] if len(sys.argv) > 1 else HERE
    outdir = sys.argv[2] if len(sys.argv) > 2 else indir
    main(indir, outdir)
