#!/usr/bin/env python3
"""D036 point 8 / D037 scoreboard generator.

Deterministic: reads exactly five JSON inputs (data_coverage.json,
metrics.json, lifecycle.json, granular/player_granular_metrics.json,
granular/player_granular_coverage.json) and emits scoreboard.html plus
scoreboard_manifest.json.  Given identical input bytes the emitted HTML is
byte-identical (the page's own displayed timestamps come from the inputs).
The manifest carries its own generation timestamp and the sha256 of the five
inputs, this generator, and the output.

The two granular/*.json inputs are READ-ONLY: they are pre-computed by
experiments/market_program/SCOREBOARD/granular/compute_player_granular.py and
this generator only selects and formats already-computed fields from them --
it never recomputes a metric.

The visual system (tokens, chips, tiles, table anatomy) is preserved from the
prior hand-edited scoreboard.html, which this generated page replaces.
Operational progress and predictive evidence are visually and semantically
distinct sections.  Every displayed number carries a provenance popover
(title attribute) and an expandable footnote.
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
"""


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
        f"n_quote_rows: {row.get('n_quote_rows')}",
        f"n_player_games: {row.get('n_player_games')}",
        f"computed at: {granular_metrics.get('generated_utc')}",
    ]
    return " | ".join(str(b) for b in bits)


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


def build_html(coverage, metrics, lifecycle, granular_metrics, granular_coverage):
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
    a(f"<title>WNBA Model vs Market — Scoreboard (generated)</title>\n<style>\n{CSS}</style>\n")
    a('<div class="wrap">')

    # header ---------------------------------------------------------------
    a('<header>')
    a('<div class="eyebrow">WNBA Program · Persistent Scoreboard · GENERATED — do not hand-edit</div>')
    a('<h1>How close are we to reality — and how close are the bookies?</h1>')
    a(f'<div class="stamp">Inputs computed <b>{esc(metrics["generated_utc"])}</b> (metrics) · <b>{esc(coverage["generated_utc"])}</b> (coverage) · '
      f'{esc(lifecycle["updated_note"])}</div>')
    a('</header>')

    # headline tiles ---------------------------------------------------------
    a('<section class="predsec">')
    a('<h2>Headline numbers — predictive evidence only</h2>')
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
    a(f'<div class="tile"><div class="k">Challenger field · 22 arms</div>'
      f'<div class="v">{pending_chip}</div>'
      f'<div class="d">{esc(lifecycle["challenger_field"]["statement"])} '
      f'{chip("run", "BUILT", lifecycle["challenger_field"]["source"]["record"])}</div></div>')
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
    a('<h2>Scoreboard — model vs market vs reality</h2>')
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
    a('<section class="foot">')
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

    a('</div>\n')
    return "\n".join(parts)


def main(indir=HERE, outdir=None):
    outdir = outdir or indir
    inputs = {
        "data_coverage.json": os.path.join(indir, "data_coverage.json"),
        "metrics.json": os.path.join(indir, "metrics.json"),
        "lifecycle.json": os.path.join(indir, "lifecycle.json"),
        "granular/player_granular_metrics.json": os.path.join(indir, "granular", "player_granular_metrics.json"),
        "granular/player_granular_coverage.json": os.path.join(indir, "granular", "player_granular_coverage.json"),
    }
    docs = {}
    for name, path in inputs.items():
        with open(path, encoding="utf-8") as f:
            docs[name] = json.load(f)

    page = build_html(
        docs["data_coverage.json"], docs["metrics.json"], docs["lifecycle.json"],
        docs["granular/player_granular_metrics.json"], docs["granular/player_granular_coverage.json"],
    )
    out_html = os.path.join(outdir, "scoreboard.html")
    with open(out_html, "w", encoding="utf-8", newline="\n") as f:
        f.write(page)

    generator_path = os.path.abspath(__file__)
    manifest = {
        "schema": "market_program/SCOREBOARD/manifest/1",
        "decision_authority": "D036_SCOREBOARD_MEASUREMENT_SEMANTICS point 8, D037_GRANULAR_PLAYER_SCOREBOARD",
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
