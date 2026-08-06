"""
capture_sxbet.py -- SX Bet WNBA public market-data capture.

Authority: DECISION_LEDGER.jsonl D035_EXCHANGE_DISPOSITIONS (2026-08-06T19:30:08Z),
relaying the user's ruling that the official-documented-API reading of SX Bet's
Terms and Conditions controls: capture proceeds at gentle read-only rates against
SX Bet's own documented public endpoints, provenance EXCHANGE_PUBLIC_API,
VENDOR_ASSERTED timestamps, disposition reversible if SX Bet ever objects.

Contract: experiments/market_program/M00_MARKET_PROGRAM_CONTRACT/MARKET_PROGRAM_CONTRACT.md
(sha256 1152dcd3bf74000f700844bc8bfc0df25de61a067f59534a714ac4f2f20265de, verified at build time)
Section 6.3 (amendment-4 schema fields) and Section 4 (point-in-time integrity) apply.

Prior verification: experiments/market_program/EXCHANGE_CAPTURE/sxbet/
API_AND_WNBA_VERIFICATION_2026-08-06.md (league 1384, 60 active markets at that
time, marketHash + sportXeventId keys) and TERMS_OF_USE_VERIFIED_2026-08-06.md /
HALT_USER_REQUIRED.md (the ToS tension, now resolved by D035, not erased -- see
README section at bottom of this file).

OWNERSHIP: this directory (experiments/market_program/EXCHANGE_CAPTURE/sxbet/) only.

Standing discipline in this file:
  - No git operations. No subagent dispatch.
  - <=1 request per second against api.sx.bet (their documented limits are
    200-500 req/min; this stays far under all of them).
  - Honest, identifying User-Agent naming this research project and a contact.
  - No credentials. SX Bet's market-data reads require none (verified).
  - Flags and data only. Every row carries is_order=false structurally --
    nothing this script writes is, or could be replayed as, an order. Orders
    observed on SX Bet's public order book are captured as inert data about
    other market participants' resting orders, never as anything this program
    could submit.
  - Every row carries the full amendment-4 field set (M00 contract Section 6.3):
    vendor_ts, vendor_ts_semantics, retrieval_ts, ingestion_ts,
    max_staleness_bound, poll_interval_at_capture, vendor_latency_note,
    payload_hash, prev_snapshot_ref.
  - Append-only JSONL. A changed value is a new row with prev_snapshot_ref
    pointing at the prior row's payload_hash for the same key; an unchanged
    value is deduplicated (not rewritten) and counted in the poll log.
  - Resumable state (state/sxbet_state.json): last payload_hash and last-seen
    timestamp per (table, key), so a fresh process resumes the dedup/prev-ref
    chain correctly rather than restarting it.
  - A poll_log.jsonl row per HTTP attempt: endpoint, status, latency, counts,
    and every failure -- never a silent drop.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

try:
    import requests
except ImportError:  # pragma: no cover - environment guard, not exercised in tests
    requests = None  # type: ignore

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

BASE_URL = "https://api.sx.bet"
LEAGUE_ID = 1384  # WNBA main league (game markets) -- verified 2026-08-06
SPORT_ID = 1  # Basketball

USER_AGENT = (
    "wnba-betting-model-research/1.0 "
    "(+contact: jgallagher@sasscpas.com; read-only public market-data capture; "
    "SX Bet WNBA league 1384; see D035_EXCHANGE_DISPOSITIONS in "
    "experiments/player_program/orchestration/DECISION_LEDGER.jsonl)"
)

MIN_REQUEST_INTERVAL_SECONDS = 1.05  # enforces <=1 rps with margin, far under
                                      # SX Bet's documented 200-500 req/min limits
MARKET_HASH_BATCH_SIZE = 20  # keeps GET query strings short and predictable

PROVENANCE = "EXCHANGE_PUBLIC_API"
VENDOR_TS_LABEL = "VENDOR_ASSERTED"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DATA_DIR = os.path.join(SCRIPT_DIR, "data")
DEFAULT_STATE_PATH = os.path.join(SCRIPT_DIR, "state", "sxbet_state.json")
DEFAULT_LOG_PATH = os.path.join(SCRIPT_DIR, "logs", "poll_log.jsonl")

TABLE_FILES = {
    "markets": "markets.jsonl",
    "best_line": "best_line.jsonl",
    "orderbook": "orderbook.jsonl",
    "trades": "trades.jsonl",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def sha256_hex(obj: Any) -> str:
    """Deterministic content hash of a JSON-serializable object."""
    canonical = json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
# Rate limiter
# --------------------------------------------------------------------------


class RateLimiter:
    """Enforces a minimum wall-clock gap between successive HTTP calls."""

    def __init__(self, min_interval_seconds: float = MIN_REQUEST_INTERVAL_SECONDS,
                 sleep_fn: Callable[[float], None] = time.sleep,
                 time_fn: Callable[[], float] = time.monotonic):
        self.min_interval = min_interval_seconds
        self._sleep = sleep_fn
        self._time = time_fn
        self._last_call: Optional[float] = None

    def wait(self) -> None:
        if self._last_call is not None:
            elapsed = self._time() - self._last_call
            remaining = self.min_interval - elapsed
            if remaining > 0:
                self._sleep(remaining)
        self._last_call = self._time()


# --------------------------------------------------------------------------
# HTTP client (thin, injectable for tests)
# --------------------------------------------------------------------------


class SxBetClient:
    """Wraps SX Bet's documented public GET endpoints. No auth, no writes."""

    def __init__(self, base_url: str = BASE_URL, rate_limiter: Optional[RateLimiter] = None,
                 session: Optional[Any] = None, poll_log: Optional[List[dict]] = None,
                 timeout: float = 20.0):
        self.base_url = base_url
        self.rate_limiter = rate_limiter or RateLimiter()
        self.session = session or (requests.Session() if requests else None)
        if self.session is not None:
            self.session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
        self.poll_log: List[dict] = poll_log if poll_log is not None else []
        self.timeout = timeout

    def _get(self, path: str, params: Optional[dict] = None, cycle_id: str = "") -> Tuple[Optional[dict], dict]:
        """GET path, return (parsed_json_or_None, log_row). Never raises for HTTP-level
        failures -- every failure is captured in the log row instead of a silent drop."""
        self.rate_limiter.wait()
        url = f"{self.base_url}{path}"
        started = now_iso()
        t0 = time.monotonic()
        log_row = {
            "cycle_id": cycle_id,
            "attempt_id": str(uuid.uuid4()),
            "endpoint": path,
            "url": url,
            "params": params,
            "started_ts": started,
        }
        if self.session is None:
            log_row.update({
                "finished_ts": now_iso(),
                "latency_ms": 0,
                "http_status": None,
                "ok": False,
                "error": "no HTTP session available (requests not installed)",
                "n_returned": 0,
            })
            self.poll_log.append(log_row)
            return None, log_row

        try:
            resp = self.session.get(url, params=params, timeout=self.timeout)
            latency_ms = round((time.monotonic() - t0) * 1000, 1)
            log_row["finished_ts"] = now_iso()
            log_row["latency_ms"] = latency_ms
            log_row["http_status"] = resp.status_code
            if resp.status_code != 200:
                log_row["ok"] = False
                log_row["error"] = f"non-200 status: {resp.status_code}; body[:300]={resp.text[:300]!r}"
                log_row["n_returned"] = 0
                self.poll_log.append(log_row)
                return None, log_row
            try:
                parsed = resp.json()
            except ValueError as exc:
                log_row["ok"] = False
                log_row["error"] = f"non-JSON body: {exc}"
                log_row["n_returned"] = 0
                self.poll_log.append(log_row)
                return None, log_row
            if parsed.get("status") != "success":
                log_row["ok"] = False
                log_row["error"] = f"API status != success: {parsed.get('status')!r}"
                log_row["n_returned"] = 0
                self.poll_log.append(log_row)
                return None, log_row
            log_row["ok"] = True
            log_row["error"] = None
            self.poll_log.append(log_row)
            return parsed, log_row
        except Exception as exc:  # network error, timeout, etc. -- reported, not dropped
            log_row["finished_ts"] = now_iso()
            log_row["latency_ms"] = round((time.monotonic() - t0) * 1000, 1)
            log_row["http_status"] = None
            log_row["ok"] = False
            log_row["error"] = f"{type(exc).__name__}: {exc}"
            log_row["n_returned"] = 0
            self.poll_log.append(log_row)
            return None, log_row

    def get_active_markets(self, league_id: int = LEAGUE_ID, cycle_id: str = "") -> Tuple[List[dict], dict]:
        parsed, log_row = self._get("/markets/active", params={"leagueId": league_id}, cycle_id=cycle_id)
        if parsed is None:
            return [], log_row
        markets = parsed.get("data", {}).get("markets", [])
        log_row["n_returned"] = len(markets)
        return markets, log_row

    def get_orders(self, market_hashes: List[str], cycle_id: str = "") -> Tuple[List[dict], dict]:
        parsed, log_row = self._get(
            "/orders", params={"marketHashes": ",".join(market_hashes)}, cycle_id=cycle_id
        )
        if parsed is None:
            return [], log_row
        orders = parsed.get("data", [])
        if isinstance(orders, dict):  # defensive: API has changed shape between endpoints before
            orders = orders.get("orders", [])
        log_row["n_returned"] = len(orders)
        return orders, log_row

    def get_trades(self, market_hashes: List[str], cycle_id: str = "") -> Tuple[List[dict], dict]:
        parsed, log_row = self._get(
            "/trades", params={"marketHashes": ",".join(market_hashes)}, cycle_id=cycle_id
        )
        if parsed is None:
            return [], log_row
        data = parsed.get("data", {})
        trades = data.get("trades", []) if isinstance(data, dict) else data
        log_row["n_returned"] = len(trades)
        return trades, log_row


def chunk(items: List[str], size: int) -> Iterable[List[str]]:
    for i in range(0, len(items), size):
        yield items[i:i + size]


# --------------------------------------------------------------------------
# Parsing / row construction
# --------------------------------------------------------------------------


def parse_markets(raw_markets: List[dict]) -> List[dict]:
    """Validate and normalize raw /markets/active rows. Raises on structural
    schema violations rather than silently coercing -- schema enforcement per
    the D035/M00 discipline."""
    out = []
    required = ("marketHash", "sportXeventId", "type", "gameTime", "status")
    for m in raw_markets:
        missing = [k for k in required if k not in m]
        if missing:
            raise ValueError(f"market row missing required fields {missing}: {m!r}")
        out.append(m)
    return out


def parse_orders(raw_orders: List[dict]) -> List[dict]:
    required = ("marketHash", "orderHash", "percentageOdds", "isMakerBettingOutcomeOne",
                "totalBetSize", "fillAmount", "orderStatus")
    out = []
    for o in raw_orders:
        missing = [k for k in required if k not in o]
        if missing:
            raise ValueError(f"order row missing required fields {missing}: {o!r}")
        out.append(o)
    return out


def parse_trades(raw_trades: List[dict]) -> List[dict]:
    required = ("marketHash", "fillHash", "stake", "odds", "createdAt", "tradeStatus")
    out = []
    for t in raw_trades:
        missing = [k for k in required if k not in t]
        if missing:
            raise ValueError(f"trade row missing required fields {missing}: {t!r}")
        out.append(t)
    return out


def compute_best_line(orders_by_market: Dict[str, List[dict]]) -> List[dict]:
    """Best-line summary per market per side, derived from the public resting
    order book. 'Best' = the highest percentageOdds among ACTIVE, unfilled-
    remaining orders on that side (percentageOdds is SX Bet's fixed-point
    implied-probability-style price for the maker's side; a higher value is
    the more favorable price on offer to a taker on that side)."""
    out = []
    for market_hash, orders in orders_by_market.items():
        for side_flag, side_name in ((True, "outcomeOne"), (False, "outcomeTwo")):
            side_orders = [
                o for o in orders
                if o.get("isMakerBettingOutcomeOne") == side_flag
                and o.get("orderStatus") == "ACTIVE"
            ]
            if not side_orders:
                out.append({
                    "marketHash": market_hash,
                    "side": side_name,
                    "n_active_orders": 0,
                    "best_percentage_odds": None,
                    "best_order_hash": None,
                    "total_available_stake": "0",
                })
                continue

            def _odds_key(o: dict) -> int:
                try:
                    return int(o["percentageOdds"])
                except (TypeError, ValueError):
                    return -1

            best = max(side_orders, key=_odds_key)
            total_available = sum(
                max(int(o.get("totalBetSize", 0)) - int(o.get("fillAmount", 0)), 0)
                for o in side_orders
            )
            out.append({
                "marketHash": market_hash,
                "side": side_name,
                "n_active_orders": len(side_orders),
                "best_percentage_odds": best.get("percentageOdds"),
                "best_order_hash": best.get("orderHash"),
                "total_available_stake": str(total_available),
            })
    return out


# --------------------------------------------------------------------------
# State store (resumability + dedup/prev-ref chain)
# --------------------------------------------------------------------------


@dataclass
class StateStore:
    path: str
    data: dict = field(default_factory=lambda: {"keys": {}, "cycles": []})

    @classmethod
    def load(cls, path: str) -> "StateStore":
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            return cls(path=path, data=data)
        return cls(path=path, data={"keys": {}, "cycles": []})

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self.data, fh, indent=2, sort_keys=True)
        os.replace(tmp, self.path)

    def get(self, table: str, key: str) -> Optional[dict]:
        return self.data["keys"].get(f"{table}:{key}")

    def put(self, table: str, key: str, payload_hash: str, retrieval_ts: str) -> None:
        self.data["keys"][f"{table}:{key}"] = {
            "payload_hash": payload_hash,
            "last_retrieval_ts": retrieval_ts,
        }

    def record_cycle(self, cycle_summary: dict) -> None:
        self.data["cycles"].append(cycle_summary)


# --------------------------------------------------------------------------
# Row envelope + append-only writer with dedup/prev-ref chaining
# --------------------------------------------------------------------------


def build_envelope(*, table: str, key: str, content: dict, vendor_ts: Optional[Any],
                    vendor_ts_semantics: str, vendor_latency_note: str,
                    retrieval_ts: str, poll_interval_at_capture: Optional[float],
                    state: StateStore, cycle_id: str) -> Tuple[Optional[dict], bool]:
    """Builds the full amendment-4 row envelope for one (table, key, content)
    observation. Returns (row_or_None, was_new). If the content is byte-
    identical to the prior observation for this key, returns (None, False) --
    the caller must NOT write a row (dedup), but should count it.
    """
    payload_hash = sha256_hex(content)
    prior = state.get(table, key)
    if prior is not None and prior["payload_hash"] == payload_hash:
        return None, False

    prev_ref = prior["payload_hash"] if prior is not None else None
    ingestion_ts = now_iso()
    row = {
        "row_id": str(uuid.uuid4()),
        "table": table,
        "key": key,
        "cycle_id": cycle_id,
        "is_order": False,
        "provenance": PROVENANCE,
        "content": content,
        "vendor_ts": vendor_ts,
        "vendor_ts_label": VENDOR_TS_LABEL,
        "vendor_ts_semantics": vendor_ts_semantics,
        "retrieval_ts": retrieval_ts,
        "ingestion_ts": ingestion_ts,
        "max_staleness_bound": poll_interval_at_capture,
        "poll_interval_at_capture": poll_interval_at_capture,
        "vendor_latency_note": vendor_latency_note,
        "payload_hash": payload_hash,
        "prev_snapshot_ref": prev_ref,
    }
    state.put(table, key, payload_hash, retrieval_ts)
    return row, True


def append_jsonl(path: str, rows: List[dict]) -> None:
    if not rows:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True, default=str))
            fh.write("\n")


def append_poll_log(path: str, rows: List[dict]) -> None:
    if not rows:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True, default=str))
            fh.write("\n")


# --------------------------------------------------------------------------
# One capture cycle
# --------------------------------------------------------------------------


VENDOR_LATENCY_NOTES = {
    "markets": (
        "No per-row vendor update timestamp is exposed by /markets/active; "
        "gameTime is the scheduled tip-off, not a last-changed time. "
        "vendor_ts is null; staleness is bounded only by poll_interval_at_capture."
    ),
    "best_line": (
        "Derived from /orders, which carries no book-last-change timestamp "
        "distinct from our own retrieval. vendor_ts_semantics=unknown_unverified "
        "per M00 contract Section 6.3 default."
    ),
    "orderbook": (
        "SX Bet /orders exposes no book-last-change timestamp; apiExpiry is an "
        "expiry, not a last-change time. vendor_ts_semantics=unknown_unverified."
    ),
    "trades": (
        "createdAt is SX Bet's own recorded trade-creation time (their system "
        "clock), not independently witnessed by us and not confirmed by vendor "
        "documentation to be book_last_change; treated conservatively as "
        "unknown_unverified per the M00 contract Section 6.3 default until "
        "confirmed."
    ),
}


def run_cycle(client: SxBetClient, state: StateStore, data_dir: str,
              cycle_id: Optional[str] = None,
              league_id: int = LEAGUE_ID,
              poll_interval_seconds: Optional[float] = None) -> dict:
    """Runs one full capture cycle: active markets, per-market order book
    (-> best line + depth), and recent trades. Returns a stats dict; never
    raises for a single failed HTTP call (that failure is in the poll log and
    in the returned stats' 'endpoint_failures' list) -- but DOES raise if
    parsing/schema enforcement fails on a 200 response, since that is a
    structural contract violation worth stopping on rather than silently
    dropping.
    """
    cycle_id = cycle_id or str(uuid.uuid4())
    cycle_started = now_iso()
    stats: dict = {
        "cycle_id": cycle_id,
        "started_ts": cycle_started,
        "league_id": league_id,
        "endpoints_attempted": [],
        "endpoint_failures": [],
        "rows_written": {t: 0 for t in TABLE_FILES},
        "rows_deduped": {t: 0 for t in TABLE_FILES},
        "raw_counts": {},
    }

    # 1. Active markets ----------------------------------------------------
    raw_markets, log_row = client.get_active_markets(league_id=league_id, cycle_id=cycle_id)
    stats["endpoints_attempted"].append("/markets/active")
    if not log_row.get("ok"):
        stats["endpoint_failures"].append({"endpoint": "/markets/active", "error": log_row.get("error")})
        raw_markets = []
    markets = parse_markets(raw_markets)
    stats["raw_counts"]["markets"] = len(markets)

    market_rows = []
    market_hashes: List[str] = []
    for m in markets:
        mh = m["marketHash"]
        market_hashes.append(mh)
        row, is_new = build_envelope(
            table="markets", key=mh, content=m,
            vendor_ts=None, vendor_ts_semantics="unknown_unverified",
            vendor_latency_note=VENDOR_LATENCY_NOTES["markets"],
            retrieval_ts=log_row.get("finished_ts", now_iso()),
            poll_interval_at_capture=poll_interval_seconds,
            state=state, cycle_id=cycle_id,
        )
        if is_new:
            market_rows.append(row)
        else:
            stats["rows_deduped"]["markets"] += 1
    append_jsonl(os.path.join(data_dir, TABLE_FILES["markets"]), market_rows)
    stats["rows_written"]["markets"] = len(market_rows)

    # 2. Order book (per-market depth), batched -----------------------------
    orderbook_rows = []
    best_line_rows = []
    orders_by_market: Dict[str, List[dict]] = {mh: [] for mh in market_hashes}
    n_raw_orders = 0
    if market_hashes:
        for batch in chunk(market_hashes, MARKET_HASH_BATCH_SIZE):
            raw_orders, log_row = client.get_orders(batch, cycle_id=cycle_id)
            stats["endpoints_attempted"].append("/orders")
            if not log_row.get("ok"):
                stats["endpoint_failures"].append({"endpoint": "/orders", "error": log_row.get("error"),
                                                     "batch_size": len(batch)})
                continue
            orders = parse_orders(raw_orders)
            n_raw_orders += len(orders)
            retrieval_ts = log_row.get("finished_ts", now_iso())
            for o in orders:
                mh = o["marketHash"]
                orders_by_market.setdefault(mh, []).append(o)
                # Key is stable per resting order (marketHash + orderHash); a
                # change in fillAmount/orderStatus/etc. produces a NEW
                # payload_hash under the SAME key, which is exactly what
                # chains it via prev_snapshot_ref instead of starting a new,
                # disconnected key.
                key = f"{mh}:{o['orderHash']}"
                row, is_new = build_envelope(
                    table="orderbook", key=key, content=o,
                    vendor_ts=o.get("apiExpiry"), vendor_ts_semantics="unknown_unverified",
                    vendor_latency_note=VENDOR_LATENCY_NOTES["orderbook"],
                    retrieval_ts=retrieval_ts,
                    poll_interval_at_capture=poll_interval_seconds,
                    state=state, cycle_id=cycle_id,
                )
                if is_new:
                    orderbook_rows.append(row)
                else:
                    stats["rows_deduped"]["orderbook"] += 1
    stats["raw_counts"]["orderbook"] = n_raw_orders
    append_jsonl(os.path.join(data_dir, TABLE_FILES["orderbook"]), orderbook_rows)
    stats["rows_written"]["orderbook"] = len(orderbook_rows)

    # 3. Best-line odds, derived from the order book snapshot above --------
    best_lines = compute_best_line(orders_by_market)
    retrieval_ts_best_line = now_iso()
    for bl in best_lines:
        key = f"{bl['marketHash']}:{bl['side']}"
        row, is_new = build_envelope(
            table="best_line", key=key, content=bl,
            vendor_ts=None, vendor_ts_semantics="unknown_unverified",
            vendor_latency_note=VENDOR_LATENCY_NOTES["best_line"],
            retrieval_ts=retrieval_ts_best_line,
            poll_interval_at_capture=poll_interval_seconds,
            state=state, cycle_id=cycle_id,
        )
        if is_new:
            best_line_rows.append(row)
        else:
            stats["rows_deduped"]["best_line"] += 1
    append_jsonl(os.path.join(data_dir, TABLE_FILES["best_line"]), best_line_rows)
    stats["rows_written"]["best_line"] = len(best_line_rows)
    stats["raw_counts"]["best_line"] = len(best_lines)

    # 4. Recent trades (public, immutable once settled), batched -----------
    trade_rows = []
    n_raw_trades = 0
    if market_hashes:
        for batch in chunk(market_hashes, MARKET_HASH_BATCH_SIZE):
            raw_trades, log_row = client.get_trades(batch, cycle_id=cycle_id)
            stats["endpoints_attempted"].append("/trades")
            if not log_row.get("ok"):
                stats["endpoint_failures"].append({"endpoint": "/trades", "error": log_row.get("error"),
                                                     "batch_size": len(batch)})
                continue
            trades = parse_trades(raw_trades)
            n_raw_trades += len(trades)
            retrieval_ts = log_row.get("finished_ts", now_iso())
            for t in trades:
                key = t["fillHash"]
                row, is_new = build_envelope(
                    table="trades", key=key, content=t,
                    vendor_ts=t.get("createdAt"), vendor_ts_semantics="unknown_unverified",
                    vendor_latency_note=VENDOR_LATENCY_NOTES["trades"],
                    retrieval_ts=retrieval_ts,
                    poll_interval_at_capture=poll_interval_seconds,
                    state=state, cycle_id=cycle_id,
                )
                if is_new:
                    trade_rows.append(row)
                else:
                    stats["rows_deduped"]["trades"] += 1
    stats["raw_counts"]["trades"] = n_raw_trades
    append_jsonl(os.path.join(data_dir, TABLE_FILES["trades"]), trade_rows)
    stats["rows_written"]["trades"] = len(trade_rows)

    stats["finished_ts"] = now_iso()
    state.record_cycle({
        "cycle_id": cycle_id,
        "started_ts": stats["started_ts"],
        "finished_ts": stats["finished_ts"],
        "rows_written": stats["rows_written"],
        "rows_deduped": stats["rows_deduped"],
        "raw_counts": stats["raw_counts"],
        "endpoint_failures": stats["endpoint_failures"],
    })
    return stats


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="SX Bet WNBA public market-data capture")
    parser.add_argument("--loop", action="store_true", default=False,
                         help="Run continuously, one cycle per --interval seconds. "
                              "OFF by default; ships off, no scheduling performed by "
                              "this script itself -- a coordinator invokes --loop "
                              "explicitly when it decides to schedule this.")
    parser.add_argument("--interval", type=float, default=300.0,
                         help="Seconds between cycles in --loop mode (default 300).")
    parser.add_argument("--max-cycles", type=int, default=None,
                         help="Stop after this many cycles even in --loop mode (testing/ops aid).")
    parser.add_argument("--data-dir", default=DEFAULT_DATA_DIR)
    parser.add_argument("--state-path", default=DEFAULT_STATE_PATH)
    parser.add_argument("--log-path", default=DEFAULT_LOG_PATH)
    parser.add_argument("--league-id", type=int, default=LEAGUE_ID)
    args = parser.parse_args(argv)

    state = StateStore.load(args.state_path)
    client = SxBetClient()

    n_cycles = 0
    try:
        while True:
            stats = run_cycle(
                client, state, args.data_dir,
                league_id=args.league_id,
                poll_interval_seconds=args.interval if args.loop else None,
            )
            append_poll_log(args.log_path, client.poll_log)
            client.poll_log.clear()
            state.save()
            print(json.dumps(stats, indent=2, default=str))
            n_cycles += 1
            if not args.loop:
                break
            if args.max_cycles is not None and n_cycles >= args.max_cycles:
                break
            time.sleep(args.interval)
    finally:
        # Always flush whatever poll-log rows accumulated, even on error,
        # so a crashed cycle is never a silent drop.
        if client.poll_log:
            append_poll_log(args.log_path, client.poll_log)
        state.save()

    return 0


if __name__ == "__main__":
    sys.exit(main())
