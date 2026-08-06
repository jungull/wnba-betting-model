"""M05_EVENT_MARKET_LINKAGE -- deterministic event-to-quote linkage with
explicit censoring intervals.

Implements sections A and B of the frozen methodology baseline
`experiments/market_program/W1_DRAFTS/EVENT_LINKAGE_AND_METHODOLOGY.md`
(sha256 5d91f6d36c15b14fa57ef070a544dc4ca2df876f4b217c0fafa667ee1d13854d,
adopted by MARKET_PROGRAM_CONTRACT.md section 0.4) under the amendment-4
timestamp-uncertainty discipline of MARKET_PROGRAM_CONTRACT.md section 6.

Design commitments enforced in code, not in prose:

  * Every event and every quote-change is keyed on OUR first-seen capture
    timestamps.  Vendor-asserted stamps (`last_update`, `published_utc`) are
    carried in an advisory field and are never keyed on, never compared
    against witnessed bounds, and never sharpen an interval.
  * Censoring intervals come from the ACTUAL poll log (the recorded list of
    successful poll instants), never from a nominal cadence.
  * Entity resolution is normalized-exact against a frozen, hashed ER map,
    plus an explicit alias table in the O14 capture-layer format
    (`data/entity_resolution/alias_table.json` schema `ops_lane/O14/...`).
    There is NO fuzzy fallback anywhere in this module.  An unresolvable
    entity fails closed: the record is retained with reason
    ENTITY_UNRESOLVED and excluded, never silently dropped.
  * The linkage is a pure function: link(events, series, poll_logs, er_map,
    config) -> canonical bytes.  Same inputs, same bytes.
  * The ten exclusion reason codes of baseline section A.7 are the only
    exclusion vocabulary.  Excluded records are retained, never patched.
  * Reaction times are intervals [t_lower, t_upper], widened per B.1, with
    the full amendment-4 mandatory field set on every claim object (contract
    section 6.1) and the sharpness prohibition of section 6.2 enforced by
    SharpnessViolation.

Stdlib only.  No pandas, no network, no writes outside the caller's choice.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import re
import unicodedata

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# The ten exclusion reason codes -- baseline A.7, verbatim vocabulary.
# CONFOUNDED@h is parameterized; reason_code_confounded(h) renders it.
REASON_ENTITY_UNRESOLVED = "ENTITY_UNRESOLVED"
REASON_AMBIGUOUS_PRE = "AMBIGUOUS_PRE"
REASON_CONFOUNDED_PREFIX = "CONFOUNDED@"          # CONFOUNDED@h
REASON_SUSPENDED = "SUSPENDED_ACROSS_EVENT"
REASON_UNRESOLVED_AT_GRID = "UNRESOLVED_AT_GRID"
REASON_POLL_GAP = "POLL_GAP_EXCEEDS_HORIZON"
REASON_IN_PLAY_ONLY = "IN_PLAY_ONLY"
REASON_TRUNCATED = "TRUNCATED_AT_COMMENCE"
REASON_TIER_INSUFFICIENT = "TIER_INSUFFICIENT"
REASON_CLOCK_UNBOUNDED = "CLOCK_UNBOUNDED"

ALL_REASON_FAMILIES = [
    REASON_ENTITY_UNRESOLVED, REASON_AMBIGUOUS_PRE, REASON_CONFOUNDED_PREFIX,
    REASON_SUSPENDED, REASON_UNRESOLVED_AT_GRID, REASON_POLL_GAP,
    REASON_IN_PLAY_ONLY, REASON_TRUNCATED, REASON_TIER_INSUFFICIENT,
    REASON_CLOCK_UNBOUNDED,
]

# Record-level precedence (frozen): the first applicable code is the single
# primary reason.  Window-level codes can become record-primary only in the
# degenerate cases handled in _record_status().
RECORD_REASON_PRECEDENCE = [
    REASON_ENTITY_UNRESOLVED, REASON_TIER_INSUFFICIENT, REASON_IN_PLAY_ONLY,
    REASON_CLOCK_UNBOUNDED, REASON_SUSPENDED, REASON_AMBIGUOUS_PRE,
    REASON_TRUNCATED, REASON_POLL_GAP, REASON_CONFOUNDED_PREFIX,
    REASON_UNRESOLVED_AT_GRID,
]

ABSENT = "__ABSENT__"          # a series observed as not offered at a poll
UNBOUNDED = "UNBOUNDED"        # vendor latency without a sourced bound
UNMEASURED = "UNMEASURED"      # clock skew without a per-run measurement
INF = "INF"                    # right-censored upper bound

TIER_ORDER = {"T0": 0, "T1": 1, "T2": 2}

DEFAULT_CONFIG = {
    "config_version": "M05.1.0",
    "horizons_min": [1, 2, 5, 10, 15, 30, 60],
    "guard_polls": 1,
    "game_level_markets": ["h2h", "spreads", "totals"],
    "series_key_includes_line": False,   # see DESIGN_BASELINE.md delta DB-1
    "lookahead_s": 48 * 3600,            # event -> candidate games window
    "allow_t1": False,
    # vendor -> {"seconds": int, "source": str} or "UNBOUNDED"
    "vendor_latency_bounds": {},
    "default_vendor_latency": UNBOUNDED,
    # {"epsilon_max_s": int, "method": str} or "UNMEASURED"
    "clock_skew": UNMEASURED,
    "severity_taxonomy": ["OUT", "DOUBTFUL", "QUESTIONABLE", "PROBABLE",
                          "AVAILABLE", "SUSPENSION", "TRADE", "REST",
                          "OTHER"],
}


class SharpnessViolation(Exception):
    """Raised when a point estimate finer than the measurement grid is
    requested (baseline B.3 / contract section 6.2)."""


class LinkageError(Exception):
    pass


# ---------------------------------------------------------------------------
# Canonical serialization, hashing, timestamps
# ---------------------------------------------------------------------------

def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True)


def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


_TS_RE = re.compile(r"^(\d{4})-?(\d{2})-?(\d{2})[T ]?(\d{2}):?(\d{2}):?(\d{2})")

_EPOCH = _dt.datetime(1970, 1, 1)


def parse_ts(s) -> int:
    """UTC timestamp string -> epoch seconds. Accepts '20260730T150132Z' and
    '2026-07-31T00:10:00Z'. UTC always; no local-timezone dependence."""
    if isinstance(s, int):
        return s
    m = _TS_RE.match(str(s).strip())
    if not m:
        raise LinkageError(f"unparseable timestamp: {s!r}")
    y, mo, d, h, mi, se = (int(g) for g in m.groups())
    return int((_dt.datetime(y, mo, d, h, mi, se) - _EPOCH).total_seconds())


def fmt_ts(t: int) -> str:
    return (_EPOCH + _dt.timedelta(seconds=int(t))).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Entity resolution -- normalized-exact + explicit aliases, NO fuzzy path
# ---------------------------------------------------------------------------

def norm_name(s: str) -> str:
    """Verbatim the O14 capture-layer normalization
    (experiments/player_program/ops_lane/O14_OPS_ENTITY_RESOLUTION/
    fix_entity_resolution.py::_norm_name, itself daily_forecast.py:606-609)."""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", s.lower())


def game_key(home: str, away: str, commence_ts: int) -> str:
    return f"{norm_name(home)}|{norm_name(away)}|{int(commence_ts)}"


class ERMap:
    """Frozen entity-resolution map. Built once, hashed, then read-only.

    dict shape:
      teams:   {normalized team name -> team_id}
      players: {normalized player name -> player_id}
      games:   {game_key(home, away, commence_ts) -> game_id}
      aliases: O14 alias-table 'aliases' object (capture name -> player_id);
               explicit and auditable, exactly like O14 -- no fuzzy fallback.
    Resolution failure returns None; callers MUST fail closed on None.
    """

    def __init__(self, d: dict):
        self._teams = {norm_name(k): v for k, v in d.get("teams", {}).items()}
        self._players = {norm_name(k): v for k, v in d.get("players", {}).items()}
        self._players.update(
            {norm_name(k): v for k, v in d.get("aliases", {}).items()})
        self._games = dict(d.get("games", {}))
        self._team_games = {}
        for gk, gid in self._games.items():
            hn, an, cts = gk.rsplit("|", 2)
            for tn in (hn, an):
                self._team_games.setdefault(tn, []).append((int(cts), gid))
        for v in self._team_games.values():
            v.sort()
        self.map_hash = sha256_hex(canonical_json({
            "teams": self._teams, "players": self._players,
            "games": self._games}))

    def resolve_team(self, name: str):
        return self._teams.get(norm_name(name))

    def resolve_player(self, name: str):
        return self._players.get(norm_name(name))

    def resolve_game(self, home: str, away: str, commence_ts: int):
        return self._games.get(game_key(home, away, commence_ts))

    def games_for_team(self, name: str, t_lo: int, t_hi: int):
        """Games of a (resolved-by-exact-name) team with commence in
        (t_lo, t_hi]. Returns [(commence_ts, game_id)]."""
        out = []
        for cts, gid in self._team_games.get(norm_name(name), []):
            if t_lo < cts <= t_hi:
                out.append((cts, gid))
        return out

    def commence_of(self, game_id: str):
        for gk, gid in self._games.items():
            if gid == game_id:
                return int(gk.rsplit("|", 1)[1])
        return None


# ---------------------------------------------------------------------------
# Poll log -- the ACTUAL record of successful polls, never a nominal cadence
# ---------------------------------------------------------------------------

class PollLog:
    """Sorted unique successful-poll instants for ONE stream."""

    def __init__(self, instants):
        self.polls = sorted(set(int(parse_ts(t)) for t in instants))
        if not self.polls:
            raise LinkageError("empty poll log")
        self.log_hash = sha256_hex(",".join(str(p) for p in self.polls))

    def prev(self, t: int):
        """Largest poll strictly before t, else None."""
        lo, hi, ans = 0, len(self.polls) - 1, None
        while lo <= hi:
            mid = (lo + hi) // 2
            if self.polls[mid] < t:
                ans = self.polls[mid]
                lo = mid + 1
            else:
                hi = mid - 1
        return ans

    def next_after(self, t: int):
        """Smallest poll strictly after t, else None."""
        lo, hi, ans = 0, len(self.polls) - 1, None
        while lo <= hi:
            mid = (lo + hi) // 2
            if self.polls[mid] > t:
                ans = self.polls[mid]
                hi = mid - 1
            else:
                lo = mid + 1
        return ans

    def has_poll_in(self, lo_excl: int, hi_incl: int) -> bool:
        p = self.next_after(lo_excl)
        return p is not None and p <= hi_incl

    def interval_ending_at(self, t_seen: int):
        """Censoring interval (t_prev, t_seen] for an observation first seen
        at poll t_seen. Returns (t_prev|None, t_seen). t_prev None means
        t_seen is the stream's first poll (baseline, not an event)."""
        if t_seen not in set(self.polls):
            raise LinkageError(
                f"t_seen {t_seen} is not a recorded poll of this stream; "
                "intervals derive from the actual poll log only")
        return self.prev(t_seen), t_seen

    def gap_at(self, t_seen: int):
        p = self.prev(t_seen)
        return None if p is None else t_seen - p


# ---------------------------------------------------------------------------
# Events (baseline A.1) and quote series / changes (A.2)
# ---------------------------------------------------------------------------

def _event_id(stream, entity_keys, old_state, new_state, t_seen):
    return "EV_" + sha256_hex(canonical_json(
        [stream, entity_keys, old_state, new_state, t_seen]))[:16]


def _report_id(stream, report_key):
    return "RP_" + sha256_hex(canonical_json([stream, report_key]))[:16]


def build_events_full_state(rows, poll_log: PollLog, *, stream: str,
                            tier: str, entity_fields, state_field: str,
                            report_key_fn, er_map: ERMap,
                            resolve_fn, advisory_fields=()):
    """Diff a FULL-STATE-per-poll stream (e.g. the injury log: every poll
    records the complete current designations) into first-seen state
    transitions.

    resolve_fn(row) -> dict of resolved entity ids, or None if resolution
    fails (fail closed -> ENTITY_UNRESOLVED, retained).
    Returns (events, excluded_events)."""
    by_poll = {}
    for r in rows:
        t = parse_ts(r["capture_utc"])
        by_poll.setdefault(t, {})
        ek = tuple(str(r[f]) for f in entity_fields)
        by_poll[t][ek] = (r[state_field], r)
    events, excluded = [], []
    polls_seen = sorted(by_poll)
    for t in polls_seen:
        if t not in set(poll_log.polls):
            raise LinkageError(
                f"stream {stream}: capture at {fmt_ts(t)} not in poll log")
    prev_state: dict = {}
    for i, t in enumerate(polls_seen):
        cur = by_poll[t]
        if i == 0:
            prev_state = {k: v[0] for k, v in cur.items()}
            continue
        t_prev_poll = polls_seen[i - 1]
        keys = set(prev_state) | set(cur)
        for ek in sorted(keys):
            old = prev_state.get(ek, ABSENT)
            new = cur[ek][0] if ek in cur else ABSENT
            if old == new:
                continue
            row = cur[ek][1] if ek in cur else by_poll[t_prev_poll][ek][1]
            resolved = resolve_fn(row)
            base = {
                "event_id": _event_id(stream, list(ek), old, new, t),
                "stream": stream,
                "report_id": _report_id(stream, report_key_fn(row, t)),
                "entity_raw": dict(zip(entity_fields, ek)),
                "old_state": old, "new_state": new,
                "t_prev": t_prev_poll, "t_seen": t,
                "tier": tier,
                "advisory": {f: row.get(f) for f in advisory_fields},
            }
            if resolved is None:
                base["exclusion_reason"] = REASON_ENTITY_UNRESOLVED
                excluded.append(base)      # retained, never dropped
            else:
                base["entity"] = resolved
                events.append(base)
        prev_state = {k: v[0] for k, v in cur.items()}
    return events, excluded


def build_quote_series(rows, poll_log: PollLog, er_map: ERMap, config,
                       *, tier="T0"):
    """Group witnessed odds rows into per-key series of per-poll observations.

    Row fields: snapshot_utc, commence_time, home_team, away_team, bookmaker,
    market, outcome, point, price.

    In-play exclusion is STRUCTURAL: rows with snapshot >= commence never
    enter a series (contract section 4.4); they are counted, not kept.
    Unresolvable games fail closed into excluded_rows. Returns
    (series_map, excluded_rows, n_inplay_dropped)."""
    series: dict = {}
    excluded_rows = []
    n_inplay = 0
    poll_set = set(poll_log.polls)
    for r in rows:
        t = parse_ts(r["snapshot_utc"])
        cts = parse_ts(r["commence_time"])
        if t >= cts:
            n_inplay += 1          # structural in-play exclusion
            continue
        if t not in poll_set:
            raise LinkageError(
                f"quote snapshot {fmt_ts(t)} not in the odds poll log")
        gid = er_map.resolve_game(r["home_team"], r["away_team"], cts)
        if gid is None:
            excluded_rows.append(
                {"row": {k: r.get(k) for k in
                         ("snapshot_utc", "home_team", "away_team",
                          "bookmaker", "market", "outcome")},
                 "exclusion_reason": REASON_ENTITY_UNRESOLVED})
            continue
        key_parts = [gid, r["bookmaker"], r["market"], str(r["outcome"])]
        if config["series_key_includes_line"]:
            key_parts.append(str(r.get("point", "")))
        skey = "|".join(key_parts)
        s = series.setdefault(skey, {
            "series_key": skey, "game_id": gid,
            "bookmaker": r["bookmaker"], "market": r["market"],
            "outcome": str(r["outcome"]), "commence_ts": cts,
            "tier": tier, "obs": {},
            "advisory_last_update": {}})
        state = (str(r.get("point", "")), str(r.get("price", "")))
        s["obs"][t] = state
        if r.get("last_update"):
            s["advisory_last_update"][t] = r["last_update"]
    for s in series.values():
        polls = [p for p in poll_log.polls
                 if p < s["commence_ts"]]
        s["observed_polls"] = polls
        s["timeline"] = [(p, s["obs"].get(p, ABSENT)) for p in polls]
    return series, excluded_rows, n_inplay


def detect_quote_changes(s, poll_log: PollLog):
    """First-seen transitions of a series: price move, line move, appear
    (reopen), disappear (suspend). Interval-censored (t_prev, t_seen]."""
    changes = []
    tl = s["timeline"]
    for i in range(1, len(tl)):
        (tp, old), (tc, new) = tl[i - 1], tl[i]
        if old == new:
            continue
        if old == ABSENT:
            kind = "APPEAR"
        elif new == ABSENT:
            kind = "DISAPPEAR"
        elif old[0] != new[0]:
            kind = "LINE_MOVE"
        else:
            kind = "PRICE_MOVE"
        changes.append({"q_lo": tp, "q_up": tc, "kind": kind,
                        "old": old, "new": new})
    return changes


def detect_suspensions(s):
    """Pregame suspension episodes: (disappear interval, reopen interval or
    None if still absent at CLOSE)."""
    episodes, open_ep = [], None
    for ch in detect_quote_changes(s, None):
        if ch["kind"] == "DISAPPEAR":
            open_ep = {"suspend_lo": ch["q_lo"], "suspend_up": ch["q_up"],
                       "reopen_lo": None, "reopen_up": None}
        elif ch["kind"] == "APPEAR" and open_ep is not None:
            open_ep["reopen_lo"], open_ep["reopen_up"] = ch["q_lo"], ch["q_up"]
            episodes.append(open_ep)
            open_ep = None
    if open_ep is not None:
        episodes.append(open_ep)
    return episodes


# ---------------------------------------------------------------------------
# B.1 widening, B.2 reaction bounds, B.3 sharpness
# ---------------------------------------------------------------------------

def vendor_bound(config, vendor):
    vb = config["vendor_latency_bounds"].get(vendor,
                                             config["default_vendor_latency"])
    return vb


def _lmax_seconds(vb):
    return None if vb == UNBOUNDED else int(vb["seconds"])


def widen_interval(lo, up, l_max, eps):
    """B.1: t_true in [t_prev - L_max - eps, t_seen + eps].
    l_max None (UNBOUNDED) -> lower bound unbounded (None).
    eps None (UNMEASURED) -> caller must have tainted CLOCK_UNBOUNDED first;
    widening with unmeasured skew is refused."""
    if eps is None:
        raise LinkageError("cannot widen with UNMEASURED clock skew; the row "
                           "is CLOCK_UNBOUNDED and must be excluded")
    w_up = up + eps
    w_lo = None if l_max is None else lo - l_max - eps
    return w_lo, w_up


def measurement_grid(d_event, d_quote, l_max_total, eps):
    """G = delta_event + delta_quote + L_max(all vendors) + 2*eps.
    Returns int seconds, or UNBOUNDED if any term is unbounded/unmeasured."""
    if l_max_total is None or eps is None or d_event is None or d_quote is None:
        return UNBOUNDED
    return int(d_event + d_quote + l_max_total + 2 * eps)


def reaction_claim(event, change, *, config, quote_poll_gap, vendors,
                   tier, censor_type, n_trusted=1, n_excluded=0,
                   exclusion_reasons=None):
    """Build ONE reaction-time claim object carrying the full amendment-4
    mandatory field set (contract section 6.1). Never returns a bare point.

    change: dict with q_lo/q_up for censor_type='interval'; for
    censor_type='right', q_lo is the last pregame observation instant and
    q_up is ignored (upper bound is INF)."""
    skew = config["clock_skew"]
    eps = None if skew == UNMEASURED else int(skew["epsilon_max_s"])
    vlb = {v: vendor_bound(config, v) for v in sorted(vendors)}
    l_terms = [_lmax_seconds(b) for b in vlb.values()]
    l_total = None if any(x is None for x in l_terms) or not l_terms \
        else sum(l_terms)
    d_event = event["t_seen"] - event["t_prev"]

    if eps is None:
        # CLOCK_UNBOUNDED taint: a numeric bound cannot be stated at all.
        t_lower, t_upper, verdict = 0, UNBOUNDED, "UNSUPPORTABLE"
    else:
        e_lo_w, e_up_w = widen_interval(event["t_prev"], event["t_seen"],
                                        l_total, eps)
        if censor_type == "right":
            q_lo_w = (None if l_total is None
                      else change["q_lo"] - l_total - eps)
            t_lower = 0 if (q_lo_w is None or e_up_w is None) \
                else max(0, q_lo_w - e_up_w)
            t_upper = INF
        else:
            q_lo_w, q_up_w = widen_interval(change["q_lo"], change["q_up"],
                                            l_total, eps)
            t_lower = 0 if q_lo_w is None else max(0, q_lo_w - e_up_w)
            t_upper = UNBOUNDED if e_lo_w is None else q_up_w - e_lo_w
        verdict = "BOUNDED" if (t_upper not in (UNBOUNDED,)
                                and l_total is not None) else "UNSUPPORTABLE"

    grid = measurement_grid(d_event, quote_poll_gap, l_total, eps)
    claim = {
        # --- amendment-4 mandatory fields, contract section 6.1 ---
        "t_lower": t_lower,
        "t_upper": t_upper,
        "poll_interval_event": d_event,
        "poll_interval_quote": quote_poll_gap,
        "vendor_latency_bound": vlb,
        "clock_skew_bound": skew,
        "censor_type": censor_type,            # interval | right, never exact
        "tier": tier,
        "n_trusted": n_trusted,
        "n_excluded": n_excluded,
        "exclusion_reasons": exclusion_reasons or {},
        # --- derived discipline fields ---
        "measurement_grid_s": grid,
        "fine_grained_admissible": grid != UNBOUNDED,
        "verdict": verdict,
        "channel": "WITNESSED",
    }
    claim["statement"] = render_claim_statement(claim)
    return claim


def render_claim_statement(claim):
    """Render a claim as an interval sentence. Never emits a bare point."""
    g = claim["measurement_grid_s"]
    gtxt = "grid UNBOUNDED (vendor latency or clock skew unbounded)" \
        if g == UNBOUNDED else f"grid {g} s"
    if claim["verdict"] == "UNSUPPORTABLE":
        return (f"UNSUPPORTABLE as a bounded reaction time ({gtxt}); "
                f"witnessed ordering only, censor_type={claim['censor_type']}")
    up = claim["t_upper"]
    uptxt = "unobserved before close (right-censored)" if up == INF else f"{up} s"
    return (f"reaction within [{claim['t_lower']} s, {uptxt}] of the event "
            f"interval ({gtxt}; tier {claim['tier']})")


def assert_sharpness(precision_s, grid):
    """Refuse any point statement finer than the grid (B.3)."""
    if grid == UNBOUNDED:
        raise SharpnessViolation(
            "no point estimate is admissible: measurement grid is UNBOUNDED")
    if precision_s < grid:
        raise SharpnessViolation(
            f"point precision {precision_s}s finer than grid {grid}s")
    return True


def compare_reaction_claims(a, b, delta_s):
    """Comparative claim 'A faster than B by delta'. Below the combined grid
    the registered verdict is INDISTINGUISHABLE_AT_GRID (B.3)."""
    ga, gb = a["measurement_grid_s"], b["measurement_grid_s"]
    if ga == UNBOUNDED or gb == UNBOUNDED:
        return "INDISTINGUISHABLE_AT_GRID"
    return "DISTINGUISHABLE" if abs(delta_s) > ga + gb \
        else "INDISTINGUISHABLE_AT_GRID"


# ---------------------------------------------------------------------------
# Window construction (A.3), isolation (A.4), suspensions (A.5)
# ---------------------------------------------------------------------------

def _overlaps(a_lo, a_up, b_lo, b_up):
    return a_up > b_lo and a_lo < b_up


def build_windows(event, s, changes, quote_poll_log: PollLog, config):
    """A.3 window table for one (event, series) pair. Pure; no exclusion
    decisions here beyond per-window codes."""
    e_lo, e_up = event["t_prev"], event["t_seen"]
    cts = s["commence_ts"]
    width = e_up - e_lo
    win = {}

    pre_candidates = [c for c in changes if c["q_up"] <= e_lo]
    ambiguous = [c for c in changes
                 if _overlaps(c["q_lo"], c["q_up"], e_lo, e_up)]
    post = [c for c in changes if c["q_lo"] >= e_up]

    if pre_candidates:
        c = pre_candidates[-1]
        win["PRE"] = {"status": "OK", "q_lo": c["q_lo"], "q_up": c["q_up"],
                      "kind": c["kind"], "state": c["new"]}
    elif ambiguous:
        win["PRE"] = {"status": REASON_AMBIGUOUS_PRE}
    else:
        # no change before the event: the pre-event state is the series
        # state at the last poll <= e_lo, if any
        pre_obs = [(p, v) for p, v in s["timeline"] if p <= e_lo]
        if pre_obs:
            p, v = pre_obs[-1]
            win["PRE"] = {"status": "OK_STATE_ONLY", "obs_at": p, "state": v}
        else:
            win["PRE"] = {"status": "EMPTY"}

    win["AMBIGUOUS_CHANGES"] = len(ambiguous)

    if post:
        c = post[0]
        win["POST_FIRST"] = {"status": "OK", "q_lo": c["q_lo"],
                             "q_up": c["q_up"], "kind": c["kind"],
                             "state": c["new"]}
    else:
        last_obs = [(p, v) for p, v in s["timeline"] if p >= e_up]
        if last_obs:
            win["POST_FIRST"] = {"status": "RIGHT_CENSORED",
                                 "last_obs_at": last_obs[-1][0]}
        else:
            win["POST_FIRST"] = {"status": REASON_TRUNCATED}

    for h in config["horizons_min"]:
        hs = h * 60
        wname = f"H+{h}"
        if e_up + hs >= cts:
            win[wname] = {"status": REASON_TRUNCATED}
            continue
        if width > hs:
            # A.5: an interval wider than the horizon is unusable in any
            # window narrower than its own width
            win[wname] = {"status": REASON_POLL_GAP,
                          "event_interval_s": width}
            continue
        if not quote_poll_log.has_poll_in(e_up, e_up + hs):
            win[wname] = {"status": REASON_UNRESOLVED_AT_GRID,
                          "next_quote_poll": quote_poll_log.next_after(e_up)}
            continue
        obs = [(p, v) for p, v in s["timeline"] if e_up < p <= e_up + hs]
        p, v = obs[-1]
        win[wname] = {"status": "OK", "obs_at": p, "state": v,
                      "obs_interval": [quote_poll_log.prev(p), p]}

    close_obs = [(p, v) for p, v in s["timeline"] if v != ABSENT]
    if close_obs:
        p, v = close_obs[-1]
        win["CLOSE"] = {"status": "OK", "obs_at": p, "state": v}
    else:
        win["CLOSE"] = {"status": REASON_IN_PLAY_ONLY}
    return win


def isolation_flags(event, siblings, horizons_min, guard_s):
    """A.4: per-horizon confounding. siblings = other events linked to the
    same series (composite level for game series)."""
    flags = {}
    e_lo, e_up = event["t_prev"], event["t_seen"]
    for h in horizons_min + ["POST"]:
        hs = (h * 60) if isinstance(h, int) else 0
        span = (e_lo - guard_s, e_up + hs)
        confounded = False
        for o in siblings:
            if o["event_id"] == event["event_id"]:
                continue
            o_span = (o["t_prev"] - guard_s, o["t_seen"] + hs)
            if _overlaps(span[0], span[1], o_span[0], o_span[1]):
                confounded = True
                break
        key = f"H+{h}" if isinstance(h, int) else "POST"
        flags[key] = confounded
    return flags


def suspension_overlap(event, episodes, close_ts):
    """A.5: does any suspension interval overlap/cover the event interval?"""
    e_lo, e_up = event["t_prev"], event["t_seen"]
    for ep in episodes:
        s_lo = ep["suspend_lo"]
        s_up = ep["reopen_up"] if ep["reopen_up"] is not None else close_ts
        if _overlaps(s_lo, s_up, e_lo, e_up):
            return True
    return False


# ---------------------------------------------------------------------------
# The linkage: pure function of frozen inputs (A.8)
# ---------------------------------------------------------------------------

def _record_status(event, s, win, iso, susp, config):
    """Single primary reason code per A.7, by frozen precedence."""
    skew_ok = config["clock_skew"] != UNMEASURED
    tier_min = max((event["tier"], s["tier"]), key=lambda t: TIER_ORDER[t])
    if TIER_ORDER[tier_min] >= TIER_ORDER["T2"]:
        return "EXCLUDED", REASON_TIER_INSUFFICIENT, tier_min
    if tier_min == "T1" and not config["allow_t1"]:
        return "EXCLUDED", REASON_TIER_INSUFFICIENT, tier_min
    if win["CLOSE"]["status"] == REASON_IN_PLAY_ONLY:
        return "EXCLUDED", REASON_IN_PLAY_ONLY, tier_min
    if not skew_ok:
        return "EXCLUDED", REASON_CLOCK_UNBOUNDED, tier_min
    if susp:
        return "EXCLUDED", REASON_SUSPENDED, tier_min
    if win["PRE"]["status"] == REASON_AMBIGUOUS_PRE:
        return "EXCLUDED", REASON_AMBIGUOUS_PRE, tier_min
    if win["POST_FIRST"]["status"] == REASON_TRUNCATED:
        return "EXCLUDED", REASON_TRUNCATED, tier_min
    if iso.get("POST"):
        return "EXCLUDED", REASON_CONFOUNDED_PREFIX + "POST", tier_min
    return "TRUSTED", None, tier_min


def link(events, series_map, event_poll_log: PollLog,
         quote_poll_log: PollLog, er_map: ERMap, config,
         pair_fn=None, excluded_events=None, excluded_quote_rows=None,
         n_inplay_rows=0):
    """The deterministic linkage. Pure function; canonical output.

    pair_fn(event, series_map, er_map, config) -> list of series_keys the
    event is relevant to. Default: game-level pairing via event['game_ids'].
    """
    cfg = dict(DEFAULT_CONFIG)
    cfg.update(config or {})
    config_hash = sha256_hex(canonical_json(cfg))
    if pair_fn is None:
        pair_fn = default_pair_fn

    # Pair events to relevant series, then collapse events that share one
    # report_id AND one censoring interval into a single composite event per
    # series (A.4: game-level analyses cluster on report_id -- one report is
    # one observation, never k).  Events of the same report first seen at
    # DIFFERENT polls are genuinely different sightings and stay separate.
    records = []
    raw_pairs = []
    for ev in sorted(events, key=lambda e: e["event_id"]):
        for skey in sorted(pair_fn(ev, series_map, er_map, cfg)):
            raw_pairs.append((ev, skey))
    merged: dict = {}
    for ev, skey in raw_pairs:
        merged.setdefault(
            (ev["report_id"], skey, ev["t_prev"], ev["t_seen"]), []).append(ev)
    link_units = []
    for (rid, skey, tp, ts), evs in sorted(
            merged.items(), key=lambda kv: kv[0]):
        if len(evs) == 1:
            link_units.append((evs[0], skey))
        else:
            evs = sorted(evs, key=lambda e: e["event_id"])
            comp = {
                "event_id": "EVC_" + sha256_hex(
                    canonical_json([rid, skey, tp, ts]))[:16],
                "report_id": rid, "stream": evs[0]["stream"],
                "entity_raw": evs[0]["entity_raw"],
                "composite_members": [
                    {"event_id": e["event_id"], "entity_raw": e["entity_raw"],
                     "old_state": e["old_state"], "new_state": e["new_state"]}
                    for e in evs],
                "old_state": None, "new_state": None,
                "t_prev": tp, "t_seen": ts,
                "tier": max((e["tier"] for e in evs),
                            key=lambda t: TIER_ORDER[t]),
                "advisory": {},
            }
            link_units.append((comp, skey))
    by_series_events: dict = {}
    for ev, skey in link_units:
        by_series_events.setdefault(skey, []).append(ev)

    for ev, skey in link_units:
        # A.4 guard g = one poll interval of the EVENT stream at the anchor,
        # from the actual poll log (falls back to the stream's median gap
        # only when the event sits at the first poll, which cannot happen
        # for a transition event).
        ev_gap = event_poll_log.gap_at(ev["t_seen"])
        if ev_gap is None:
            gaps = [b - a for a, b in
                    zip(event_poll_log.polls, event_poll_log.polls[1:])]
            ev_gap = sorted(gaps)[len(gaps) // 2] if gaps else 3600
        guard_s = cfg["guard_polls"] * ev_gap
        s = series_map[skey]
        changes = detect_quote_changes(s, quote_poll_log)
        episodes = detect_suspensions(s)
        win = build_windows(ev, s, changes, quote_poll_log, cfg)
        siblings = by_series_events.get(skey, [])
        iso = isolation_flags(ev, siblings, cfg["horizons_min"], guard_s)
        close_ts = s["timeline"][-1][0] if s["timeline"] else s["commence_ts"]
        susp = suspension_overlap(ev, episodes, close_ts)
        status, primary, tier_min = _record_status(ev, s, win, iso, susp, cfg)

        claim = None
        if status == "TRUSTED":
            pf = win["POST_FIRST"]
            if pf["status"] == "OK":
                claim = reaction_claim(
                    ev, {"q_lo": pf["q_lo"], "q_up": pf["q_up"]},
                    config=cfg,
                    quote_poll_gap=pf["q_up"] - pf["q_lo"],
                    vendors=[s["bookmaker"]], tier=tier_min,
                    censor_type="interval")
            elif pf["status"] == "RIGHT_CENSORED":
                claim = reaction_claim(
                    ev, {"q_lo": pf["last_obs_at"]},
                    config=cfg,
                    quote_poll_gap=quote_poll_log.gap_at(pf["last_obs_at"]) or 0,
                    vendors=[s["bookmaker"]], tier=tier_min,
                    censor_type="right")

        rec = {
            "link_id": "LK_" + sha256_hex(
                canonical_json([ev["event_id"], skey]))[:16],
            "event_id": ev["event_id"], "report_id": ev["report_id"],
            "series_key": skey, "game_id": s["game_id"],
            "bookmaker": s["bookmaker"], "market": s["market"],
            "event_interval": [ev["t_prev"], ev["t_seen"]],
            "event_interval_iso": [fmt_ts(ev["t_prev"]), fmt_ts(ev["t_seen"])],
            "status": status, "primary_reason": primary,
            "tier": tier_min,
            "windows": win,
            "confounded_at": {k: v for k, v in iso.items() if v},
            "suspended_across_event": susp,
            "claim": claim,
            "composite_members": ev.get("composite_members"),
            "advisory": ev.get("advisory", {}),   # carried, never keyed on
        }
        records.append(rec)

    reason_dist: dict = {}
    for r in records:
        if r["status"] != "TRUSTED":
            reason_dist[r["primary_reason"]] = \
                reason_dist.get(r["primary_reason"], 0) + 1
    for e in (excluded_events or []):
        reason_dist[e["exclusion_reason"]] = \
            reason_dist.get(e["exclusion_reason"], 0) + 1
    for e in (excluded_quote_rows or []):
        reason_dist[e["exclusion_reason"]] = \
            reason_dist.get(e["exclusion_reason"], 0) + 1
    if n_inplay_rows:
        # rows structurally excluded at series construction (contract 4.4);
        # retained in the raw capture, counted here, never patched back
        reason_dist[REASON_IN_PLAY_ONLY] = \
            reason_dist.get(REASON_IN_PLAY_ONLY, 0) + n_inplay_rows

    window_dist: dict = {}
    for r in records:
        for wname, w in r["windows"].items():
            if wname.startswith("H+"):
                st = w["status"]
                window_dist.setdefault(wname, {})
                window_dist[wname][st] = window_dist[wname].get(st, 0) + 1

    result = {
        "schema": "market_program/M05/linkage_result/1",
        "config": cfg, "config_hash": config_hash,
        "er_map_hash": er_map.map_hash,
        "event_poll_log_hash": event_poll_log.log_hash,
        "quote_poll_log_hash": quote_poll_log.log_hash,
        "n_records": len(records),
        "n_trusted": sum(1 for r in records if r["status"] == "TRUSTED"),
        "n_excluded": sum(1 for r in records if r["status"] != "TRUSTED"),
        "n_unlinkable_events": len(excluded_events or []),
        "n_unlinkable_quote_rows": len(excluded_quote_rows or []),
        "n_inplay_rows_dropped": n_inplay_rows,
        "exclusion_reason_distribution": reason_dist,
        "horizon_window_status_distribution": window_dist,
        "records": sorted(records, key=lambda r: r["link_id"]),
        "unlinkable_events": excluded_events or [],
        "unlinkable_quote_rows": excluded_quote_rows or [],
    }
    result["result_hash"] = sha256_hex(canonical_json(
        {k: v for k, v in result.items() if k != "result_hash"}))
    return result


def default_pair_fn(event, series_map, er_map: ERMap, config):
    """Relevance (A.3): game-level series of every game the event names.
    Player-prop pairing requires a resolved player_id and a props series
    whose key names that player; no fuzzy relevance."""
    gids = set(event.get("game_ids") or [])
    if not gids and "team" in event.get("entity_raw", {}):
        t_lo = event["t_prev"]
        for cts, gid in er_map.games_for_team(
                event["entity_raw"]["team"], t_lo,
                t_lo + config["lookahead_s"]):
            gids.add(gid)
    out = []
    for skey, s in series_map.items():
        if s["game_id"] in gids and s["market"] in config["game_level_markets"]:
            out.append(skey)
    return out


def aggregate_claim(claims, records_excluded_dist):
    """Aggregate many per-link claims into one family-level claim object,
    keeping the amendment-4 field set. Interval statistics stay intervals."""
    if not claims:
        return None
    lowers = [c["t_lower"] for c in claims]
    uppers = [c["t_upper"] for c in claims]
    finite_up = [u for u in uppers if isinstance(u, int)]
    grid_vals = [c["measurement_grid_s"] for c in claims]
    grid = UNBOUNDED if any(g == UNBOUNDED for g in grid_vals) \
        else max(grid_vals)
    vendors: dict = {}
    for c in claims:
        vendors.update(c["vendor_latency_bound"])
    agg = {
        "t_lower": min(lowers),
        "t_upper": (INF if any(u == INF for u in uppers)
                    else (UNBOUNDED if any(u == UNBOUNDED for u in uppers)
                          else max(finite_up))),
        "poll_interval_event": max(c["poll_interval_event"] for c in claims),
        "poll_interval_quote": max(c["poll_interval_quote"] for c in claims),
        "vendor_latency_bound": vendors,
        "clock_skew_bound": claims[0]["clock_skew_bound"],
        "censor_type": "interval" if all(
            c["censor_type"] == "interval" for c in claims) else "right",
        "tier": max((c["tier"] for c in claims), key=lambda t: TIER_ORDER[t]),
        "n_trusted": len(claims),
        "n_excluded": sum(records_excluded_dist.values()),
        "exclusion_reasons": records_excluded_dist,
        "measurement_grid_s": grid,
        "fine_grained_admissible": grid != UNBOUNDED,
        "verdict": "BOUNDED" if all(
            c["verdict"] == "BOUNDED" for c in claims) else "UNSUPPORTABLE",
        "channel": "WITNESSED",
    }
    agg["statement"] = render_claim_statement(agg)
    return agg
