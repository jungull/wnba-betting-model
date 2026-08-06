"""MARKET_IMPLIED_PROJECTIONS -- the props-to-projection engine (D033 track).

Reads player-prop rows (line + over/under American prices per book),
removes vig via M11_CONSENSUS_MODEL's PREREGISTERED method, combines books
with M11's declared-preregistered-uniform weights, estimates the implied
distribution mean via implied_mean.py's preregistered Normal-dispersion
inversion, and lands the result as a D033 source-agnostic projection row
(projection_schema.py) with `source="MARKET_IMPLIED"`.

DATA SOURCES THIS ENGINE RUNS OVER (per the D033 dispatch mandate):
  (a) data/props_capture/historical/master_props_historical.csv on the LIVE
      worktree -- READ ONLY. Classified T1_VENDOR_ASSERTED per
      D027_PROPS_HISTORICAL_BOUNDED_USES; the dispatch mandate states
      explicitly that "D027 bounded uses permit benchmark construction with
      T1 labels." Every row this engine builds from (a) carries
      tier="T1", timestamp_quality="VENDOR_ASSERTED", and the D027 caveat
      (below) verbatim in `source_extra.d027_caveat`.
  (b) a SAMPLE of the live data/props_capture/master_props.csv -- READ ONLY,
      same tier/caveat treatment (this engine does not itself run a capture
      client; it only reads already-captured rows).

Neither run performs, claims, or is cited for any timing, latency, lead-lag,
CLV, stale-window, or executability claim (M00 section 4.3 / D027). This
engine is BENCHMARK-CONSTRUCTION machinery only: it produces implied-mean
rows for comparison against fundamental-model projections and against each
other, never a market-state-at-time-T claim.

Contract: MARKET_PROGRAM_CONTRACT.md sha256
1152dcd3bf74000f700844bc8bfc0df25de61a067f59534a714ac4f2f20265de

Stdlib only (uses csv, no pandas dependency, to keep this track
self-contained and independently auditable).
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
from collections import Counter, defaultdict

_HERE = os.path.dirname(os.path.abspath(__file__))
_M11_DIR = os.path.normpath(os.path.join(_HERE, "..", "M11_CONSENSUS_MODEL"))
sys.path = [p for p in sys.path if p not in (_M11_DIR, _HERE)]
sys.path.insert(0, _M11_DIR)
sys.path.insert(0, _HERE)  # local modules must shadow M11's own same-named modules

import consensus as m11          # noqa: E402
import implied_mean as im        # noqa: E402
import projection_schema as sch  # noqa: E402


def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# D027 caveat -- reproduced from DECISION_LEDGER.jsonl D027_PROPS_HISTORICAL_
# BOUNDED_USES (coordinator ruling, 2026-08-06), carried verbatim on every
# row this engine derives from either props archive.
# ---------------------------------------------------------------------------
D027_CAVEAT_TEXT = (
    "Classified T1_VENDOR_ASSERTED (D027_PROPS_HISTORICAL_BOUNDED_USES). "
    "Carries the M00 bounded-use classes of the T2 archive (coverage "
    "census, fixtures, calibration WITH unknown-timing caveats, "
    "settlement/identifier inventory, priors) plus benchmark construction "
    "for the market-implied-projections track, per the D033 dispatch "
    "mandate. NO timing, latency, lead-lag, CLV, stale-window, or "
    "executability claim may cite it."
)
D027_CAVEAT_SHA256 = sha256_hex(D027_CAVEAT_TEXT)

M00_USE_CLASS = "D027-T1-BENCHMARK-CONSTRUCTION"


# ---------------------------------------------------------------------------
# CSV loading -- both known schemas
# ---------------------------------------------------------------------------

HISTORICAL_COLUMNS = {
    "game_id", "api_event_id", "home_team", "away_team", "commence_time",
    "snapshot_requested_utc", "snapshot_returned_utc", "bookmaker_key",
    "market_key", "player_name", "line", "over_price", "under_price",
    "last_update",
}
LIVE_COLUMNS = {
    "api_event_id", "home_team", "away_team", "commence_time",
    "bookmaker_key", "market_key", "player_name", "line", "over_price",
    "under_price", "snapshot_utc", "last_update",
}


def _sniff_kind(fieldnames):
    fs = set(fieldnames)
    if "game_id" in fs:
        return "historical"
    return "live"


def load_props_rows(path, max_rows=None):
    """Yields normalized raw prop rows. Read-only; never writes the source
    file. `max_rows` caps how many CSV data rows are read (for the live
    sample), not how many output rows are produced."""
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        kind = _sniff_kind(reader.fieldnames)
        n = 0
        for row in reader:
            if max_rows is not None and n >= max_rows:
                break
            n += 1
            game_id = row.get("game_id") if kind == "historical" else None
            capture_ts_raw = (row.get("snapshot_returned_utc")
                               or row.get("snapshot_utc")
                               or row.get("last_update"))
            yield {
                "kind": kind,
                "game_id": game_id,
                "api_event_id": row.get("api_event_id"),
                "home_team": row.get("home_team"),
                "away_team": row.get("away_team"),
                "commence_time": row.get("commence_time"),
                "bookmaker_key": row.get("bookmaker_key"),
                "market_key": row.get("market_key"),
                "player_name": row.get("player_name"),
                "line_raw": row.get("line"),
                "over_price_raw": row.get("over_price"),
                "under_price_raw": row.get("under_price"),
                "capture_ts_raw": capture_ts_raw,
                "last_update_raw": row.get("last_update"),
            }


def _to_float(s):
    if s is None or s == "":
        return None
    try:
        return float(s)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Grouping: one output row per (game_key, player_name, market_key)
# ---------------------------------------------------------------------------

def group_rows(raw_rows):
    groups = defaultdict(list)
    for r in raw_rows:
        game_key = r["game_id"] or r["api_event_id"]
        key = (game_key, r["player_name"], r["market_key"])
        groups[key].append(r)
    return groups


def _consensus_line(rows):
    """Mode of quoted lines; ties broken by the smallest line value for
    determinism (fixture T-tie exercises this)."""
    lines = [ln for ln in (_to_float(r["line_raw"]) for r in rows) if ln is not None]
    if not lines:
        return None
    counts = Counter(lines)
    max_count = max(counts.values())
    candidates = sorted(ln for ln, c in counts.items() if c == max_count)
    return candidates[0]


REASON_MISSING_PRICE = "MISSING_OR_INVALID_PRICE"
REASON_OFF_CONSENSUS_LINE = "OFF_CONSENSUS_LINE"
REASON_UNSUPPORTED_MARKET = "UNSUPPORTED_MARKET_NO_DISPERSION_PRIOR"
REASON_DEGENERATE_PROBABILITY = "DEGENERATE_PROBABILITY_0_OR_1"


class RowResult:
    __slots__ = ("row", "skip_reason", "group_key")

    def __init__(self, row=None, skip_reason=None, group_key=None):
        self.row = row
        self.skip_reason = skip_reason
        self.group_key = group_key


def build_projection_row(game_key_tuple, player_name, market_key, rows,
                          *, source_label="props_archive"):
    """Build one D033 row (or a RowResult carrying a skip_reason) from all
    raw prop rows sharing one (game, player, market) group."""
    game_id, api_event_id = game_key_tuple
    group_key = (game_id or api_event_id, player_name, market_key)

    if market_key not in im.SIGMA_BY_MARKET:
        return RowResult(skip_reason=REASON_UNSUPPORTED_MARKET, group_key=group_key)

    consensus_line = _consensus_line(rows)
    if consensus_line is None:
        return RowResult(skip_reason=REASON_MISSING_PRICE, group_key=group_key)

    quotes = []
    n_off_line = 0
    n_missing_price = 0
    for r in rows:
        ln = _to_float(r["line_raw"])
        if ln != consensus_line:
            n_off_line += 1
            continue
        over_p = _to_float(r["over_price_raw"])
        under_p = _to_float(r["under_price_raw"])
        if over_p is None or under_p is None or over_p == 0 or under_p == 0:
            n_missing_price += 1
            continue
        try:
            capture_ts = m11.parse_ts(r["capture_ts_raw"])
        except Exception:
            n_missing_price += 1
            continue
        q = m11.make_quote(
            bookmaker=r["bookmaker_key"], price=over_p, capture_ts=capture_ts,
            tier="T1", vendor_ts=r.get("last_update_raw"),
            vendor_ts_semantics="unknown_unverified",
            market=market_key, outcome="over", point=consensus_line,
        )
        q["opposite_price"] = under_p
        quotes.append(q)

    if not quotes:
        return RowResult(skip_reason=REASON_MISSING_PRICE, group_key=group_key)

    try:
        cobj = m11.consensus_fair_value(
            quotes, allow_t1=True, weights_status="PREREGISTERED_UNIFORM",
            game_id=game_id or api_event_id,
        )
    except m11.ConsensusError:
        return RowResult(skip_reason=REASON_MISSING_PRICE, group_key=group_key)

    if cobj["n_trusted"] == 0 or cobj["consensus_fair_prob"] is None:
        return RowResult(skip_reason=REASON_MISSING_PRICE, group_key=group_key)

    p_over = cobj["consensus_fair_prob"]
    try:
        implied_mu, sigma_used, method_note = im.implied_mean_from_probability(
            market_key=market_key, line=consensus_line, vig_free_over_prob=p_over)
    except im.ImpliedMeanError:
        return RowResult(skip_reason=REASON_DEGENERATE_PROBABILITY, group_key=group_key)

    sample_row = rows[0]
    commence_time = sample_row.get("commence_time")
    snapshot_ts_max = max(
        (m11.fmt_ts(q["capture_ts"]) for q in quotes), default=None)

    source_extra = {
        "consensus_line": consensus_line,
        "vig_free_over_probability": p_over,
        "implied_mean": implied_mu,
        "sigma_used": sigma_used,
        "implied_mean_method_note": method_note,
        "book_dispersion": cobj["uncertainty_std"],
        "disagreement_score": cobj["disagreement_score"],
        "number_of_books": cobj["n_trusted"],
        "n_off_consensus_line": n_off_line,
        "n_missing_or_invalid_price": n_missing_price,
        "vig_method": cobj["vig_method"],
        "vig_method_preregistration_hash": cobj["vig_method_preregistration_hash"],
        "dispersion_preregistration_hash": im.DISPERSION_PREREGISTRATION_HASH,
        "m11_consensus_object": cobj,
        "m00_use_class": M00_USE_CLASS,
        "d027_caveat": D027_CAVEAT_TEXT,
        "d027_caveat_sha256": D027_CAVEAT_SHA256,
        "source_archive_label": source_label,
        "home_team": sample_row.get("home_team"),
        "away_team": sample_row.get("away_team"),
    }

    row = sch.new_row(
        player_key_raw=player_name,
        player_key_resolution="RAW_NAME_UNRESOLVED",
        game_id=game_id,
        game_key_raw=game_id or api_event_id,
        game_key_resolution="RESOLVED_GAME_ID" if game_id else "RAW_EVENT_KEY_UNRESOLVED",
        scheduled_tipoff_ts=commence_time,
        source="MARKET_IMPLIED",
        source_snapshot_ts=snapshot_ts_max,
        stat_projections={market_key: {"mean": implied_mu, "unit": "per_game"}},
        status="UNKNOWN",
        salary=None,
        source_quality="MARKET_IMPLIED",
        timestamp_quality="VENDOR_ASSERTED",
        source_extra=source_extra,
        poll_interval_quote=cobj["poll_interval_quote"],
        vendor_latency_bound="UNBOUNDED",
        clock_skew_bound="UNMEASURED",
        tier="T1",
        n_trusted=cobj["n_trusted"],
        n_excluded=cobj["n_excluded"] + n_off_line + n_missing_price,
    )
    return RowResult(row=row, group_key=group_key)


def run_engine(path, *, max_rows=None, source_label="props_archive"):
    """Runs the full engine over one props CSV. Returns
    (rows, coverage_report) where `rows` is the list of built D033 rows and
    `coverage_report` tallies groups seen / rows built / skip reasons, plus
    the distinct-player-game coverage this track's mandate asks for."""
    raw = list(load_props_rows(path, max_rows=max_rows))
    groups = group_rows(raw)

    out_rows = []
    skip_counts = Counter()
    player_games_seen = set()
    player_games_covered = set()

    for (game_key, player_name, market_key), rows in groups.items():
        pg_key = (game_key, player_name)
        player_games_seen.add(pg_key)
        game_id_vals = {r["game_id"] for r in rows if r["game_id"]}
        api_event_vals = {r["api_event_id"] for r in rows if r["api_event_id"]}
        game_id = next(iter(game_id_vals), None)
        api_event_id = next(iter(api_event_vals), None)
        result = build_projection_row(
            (game_id, api_event_id), player_name, market_key, rows,
            source_label=source_label)
        if result.row is not None:
            out_rows.append(result.row)
            player_games_covered.add(pg_key)
        else:
            skip_counts[result.skip_reason] += 1

    coverage_report = {
        "source_file": os.path.basename(path),
        "source_label": source_label,
        "n_raw_rows_read": len(raw),
        "n_groups_player_game_market": len(groups),
        "n_output_rows": len(out_rows),
        "n_groups_skipped": sum(skip_counts.values()),
        "skip_reason_counts": dict(skip_counts),
        "n_distinct_player_games_seen": len(player_games_seen),
        "n_distinct_player_games_with_at_least_one_implied_mean_row": len(player_games_covered),
        "player_game_coverage_rate": (
            round(len(player_games_covered) / len(player_games_seen), 4)
            if player_games_seen else None
        ),
    }
    return out_rows, coverage_report


def write_rows_jsonl(rows, path):
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(canonical_json(r) + "\n")
