"""M05 real-tape probe -- READ-ONLY sample run of the linkage against the
live capture worktree.

What it reads (never writes) from the live worktree:
  data/odds_capture/live_*.json          -- FILENAMES ONLY (the odds poll log)
  data/odds_capture/capture_log.csv      -- first MAX_QUOTE_ROWS data rows
  data/injury_capture/injury_log.csv     -- whole file (small; ~1.4k rows)
  data/entity_resolution/alias_table.json-- the adopted O14 alias table

Honesty constraints baked in:
  * clock_skew = UNMEASURED: no per-run NTP skew measurement exists anywhere
    in the capture logs, so every real linkage record is CLOCK_UNBOUNDED and
    NO reaction-time claim is emitted from this tape (contract section 6.3
    taint rule).  The probe's horizon-window statuses are pure poll-grid
    arithmetic and are reported as DIAGNOSTIC, not as claims.
  * vendor latency: no sourced L_max bound exists for the live odds vendor
    -> UNBOUNDED (family F9 is the future home of sourcing one).
  * The ER map is built from exact strings observed in the sample and then
    frozen+hashed before link() runs; player resolution uses the O14 alias
    table (empty by design) -- team/game resolution is exact-normalized,
    and any unresolved row fails closed.
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import linkage as L

NODE_DIR = os.path.dirname(os.path.abspath(__file__))
GAME_MARKETS = ("h2h", "spreads", "totals")


def odds_poll_log_from_filenames(root):
    d = os.path.join(root, "data", "odds_capture")
    pat = re.compile(r"^live_(\d{8}T\d{6}Z)\.json$")
    stamps = [m.group(1) for f in os.listdir(d) if (m := pat.match(f))]
    return stamps


def read_capture_rows(root, max_rows):
    path = os.path.join(root, "data", "odds_capture", "capture_log.csv")
    rows, n_total = [], 0
    with open(path, "r", encoding="utf-8", newline="") as fh:
        rd = csv.DictReader(fh)
        for r in rd:
            n_total += 1
            if n_total <= max_rows and r["market"] in GAME_MARKETS:
                rows.append(r)
    return rows, n_total


def read_injury_rows(root):
    path = os.path.join(root, "data", "injury_capture", "injury_log.csv")
    with open(path, "r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def load_o14_aliases(root):
    path = os.path.join(root, "data", "entity_resolution", "alias_table.json")
    if not os.path.exists(path):
        return {}, "alias_table.json ABSENT"
    with open(path, "r", encoding="utf-8") as fh:
        d = json.load(fh)
    return d.get("aliases", {}), d.get("schema", "?")


def build_er_map(quote_rows, alias_table):
    teams, games = {}, {}
    for r in quote_rows:
        cts = L.parse_ts(r["commence_time"])
        gk = L.game_key(r["home_team"], r["away_team"], cts)
        if gk not in games:
            games[gk] = "G_" + L.sha256_hex(gk)[:12]
        teams.setdefault(r["home_team"], "T_" + L.norm_name(r["home_team"])[:12])
        teams.setdefault(r["away_team"], "T_" + L.norm_name(r["away_team"])[:12])
    return L.ERMap({"teams": teams, "players": {}, "games": games,
                    "aliases": alias_table})


def gap_stats(polls):
    gaps = [b - a for a, b in zip(polls, polls[1:])]
    if not gaps:
        return {}
    gs = sorted(gaps)
    return {"n_polls": len(polls), "n_gaps": len(gaps),
            "min_s": gs[0], "median_s": gs[len(gs) // 2], "max_s": gs[-1],
            "n_gaps_gt_2h": sum(1 for g in gaps if g > 7200),
            "n_gaps_gt_6h": sum(1 for g in gaps if g > 21600)}


def run_probe(root, max_quote_rows=8000, write_json=True):
    quote_rows, n_total_rows = read_capture_rows(root, max_quote_rows)
    injury_rows = read_injury_rows(root)
    aliases, alias_schema = load_o14_aliases(root)

    # poll logs from the ACTUAL record of successful polls -- filenames for
    # odds (each live_*.json is one poll) unioned with witnessed snapshot
    # stamps in the sample; distinct capture_utc for injuries
    odds_stamps = set(odds_poll_log_from_filenames(root))
    odds_stamps |= {r["snapshot_utc"] for r in quote_rows}
    qpl = L.PollLog(sorted(odds_stamps))
    epl = L.PollLog(sorted({r["capture_utc"] for r in injury_rows}))

    er = build_er_map(quote_rows, aliases)

    cfg = {
        # HONEST tape condition: no skew measurement, no sourced vendor bound
        "clock_skew": L.UNMEASURED,
        "vendor_latency_bounds": {},
        "default_vendor_latency": L.UNBOUNDED,
    }

    def resolve_fn(row):
        tid = er.resolve_team(row["team"])
        if tid is None:
            return None            # fail closed
        out = {"team_id": tid}
        pid = er.resolve_player(row["player"])   # O14 aliases only; exact
        if pid is not None:
            out["player_id"] = pid
        return out

    events, exc_events = L.build_events_full_state(
        injury_rows, epl, stream="injury", tier="T0",
        entity_fields=("team", "player"), state_field="status",
        report_key_fn=lambda r, t: [r["source"], r["report_date"], t],
        er_map=er, resolve_fn=resolve_fn)

    series, exc_rows, n_inplay = L.build_quote_series(
        quote_rows, qpl, er, L.DEFAULT_CONFIG)

    res = L.link(events, series, epl, qpl, er, cfg,
                 excluded_events=exc_events, excluded_quote_rows=exc_rows,
                 n_inplay_rows=n_inplay)

    horizon = res["horizon_window_status_distribution"]
    horizon_pct = {}
    for w, dist in sorted(horizon.items(), key=lambda kv: int(kv[0][2:])):
        tot = sum(dist.values())
        horizon_pct[w] = {k: round(100.0 * v / tot, 1)
                          for k, v in sorted(dist.items())}
        horizon_pct[w]["_n"] = tot

    out = {
        "schema": "market_program/M05/real_tape_probe/1",
        "channel": "DIAGNOSTIC -- poll-grid arithmetic only; the tape is "
                   "CLOCK_UNBOUNDED (no skew measurement) and the vendor is "
                   "UNBOUNDED (no sourced latency bound), so nothing here "
                   "is a reaction-time claim",
        "inputs": {
            "root": root,
            "capture_log_rows_total": n_total_rows,
            "capture_log_rows_read_cap": max_quote_rows,
            "quote_rows_used_game_markets": len(quote_rows),
            "injury_rows": len(injury_rows),
            "o14_alias_schema": alias_schema,
            "o14_alias_count": len(aliases),
        },
        "poll_grid": {
            "odds": gap_stats(qpl.polls),
            "injury": gap_stats(epl.polls),
        },
        "er_map_hash": er.map_hash,
        "n_games_in_sample": len({s["game_id"] for s in series.values()}),
        "n_series": len(series),
        "n_events": len(events),
        "n_unlinkable_events": len(exc_events),
        "n_records": res["n_records"],
        "n_trusted": res["n_trusted"],
        "n_inplay_rows_dropped": n_inplay,
        "exclusion_reason_distribution": res["exclusion_reason_distribution"],
        "horizon_window_status_pct": horizon_pct,
        "claims_emitted": sum(1 for r in res["records"] if r["claim"]),
        "config_hash": res["config_hash"],
        "result_hash": res["result_hash"],
    }
    if write_json:
        with open(os.path.join(NODE_DIR, "PROBE_RESULTS.json"), "w",
                  encoding="utf-8") as fh:
            json.dump(out, fh, indent=2, sort_keys=True)
    return out


if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else \
        "C:/Users/jgallagher/wnba-betting-model"
    out = run_probe(root, max_quote_rows=int(
        sys.argv[2]) if len(sys.argv) > 2 else 8000)
    print(json.dumps(out, indent=2, sort_keys=True))
