"""Synthetic fixtures for M05_EVENT_MARKET_LINKAGE.

Every fixture's true event-to-quote assignment is known BY CONSTRUCTION:
the builder places the polls, the state transitions, and the commence time,
and returns alongside the tables a `truth` dict stating what the linkage
must find.  All timestamps are synthetic (year 2030) so no test can ever
secretly lean on a real capture stamp (the M00-U5 principle applied to
fully synthetic data -- no T2 bytes are used at all).

Entities are deliberately fictional: no real WNBA team or player name
appears, so entity resolution success can only come from the fixture's own
frozen ER map, never from any real-world table.
"""
from __future__ import annotations

import linkage as L

T0 = L.parse_ts("2030-01-01T00:00:00Z")

HOME, AWAY = "Alpha City Foxes", "Beta Town Owls"
HOME2, AWAY2 = "Delta Port Cranes", "Echo Falls Pikes"
P1, P2 = "Cara Swift", "Dee Long"


def _mk(t):
    return L.fmt_ts(T0 + t)


def er_map(commence_offsets):
    """ER map with games at given offsets (seconds from T0)."""
    games = {}
    for i, off in enumerate(commence_offsets):
        games[L.game_key(HOME, AWAY, T0 + off)] = f"G{i+1}"
    return L.ERMap({
        "teams": {HOME: "T_FOX", AWAY: "T_OWL", HOME2: "T_CRN", AWAY2: "T_PIK"},
        "players": {P1: 9001, P2: 9002},
        "games": games,
    })


def injury_rows(entries):
    """entries: list of (t_offset, team, player, status)."""
    return [{"capture_utc": _mk(t), "report_date": "2030-01-01",
             "game_date": "2030-01-01", "team": team, "player": player,
             "status": status, "reason": "-", "source": "synthetic_official"}
            for t, team, player, status in entries]


def quote_rows(entries, commence_off, book="bookx", market="h2h",
               outcome=HOME, home=HOME, away=AWAY):
    """entries: list of (t_offset, price) or (t_offset, None) meaning the
    row is simply not emitted at that poll (absence)."""
    rows = []
    for t, price in entries:
        if price is None:
            continue
        rows.append({"snapshot_utc": _mk(t),
                     "commence_time": _mk(commence_off),
                     "home_team": home, "away_team": away,
                     "bookmaker": book, "market": market,
                     "outcome": outcome, "point": "",
                     "price": str(price),
                     "last_update": _mk(t - 7)})  # advisory only, never keyed
    return rows


def resolve_injury_row(er):
    def fn(row):
        tid = er.resolve_team(row["team"])
        if tid is None:
            return None
        out = {"team_id": tid}
        pid = er.resolve_player(row["player"])
        if pid is not None:
            out["player_id"] = pid
        return out
    return fn


def report_key(row, t_seen):
    return [row["source"], row["report_date"], t_seen]


MEASURED_CONFIG = {
    "clock_skew": {"epsilon_max_s": 2, "method": "synthetic NTP fixture"},
    "vendor_latency_bounds": {"bookx": {"seconds": 30,
                                        "source": "synthetic bound"}},
    "default_vendor_latency": L.UNBOUNDED,
}


def build(events_entries, quote_entries, *, commence_off,
          event_polls, quote_polls, config_extra=None, er=None,
          quote_kwargs=None):
    """Assemble one fixture: returns dict with everything link() needs."""
    er = er or er_map([commence_off])
    cfg = dict(MEASURED_CONFIG)
    cfg.update(config_extra or {})
    epl = L.PollLog([_mk(t) for t in event_polls])
    qpl = L.PollLog([_mk(t) for t in quote_polls])
    inj = injury_rows(events_entries)
    events, exc_events = L.build_events_full_state(
        inj, epl, stream="injury", tier="T0",
        entity_fields=("team", "player"), state_field="status",
        report_key_fn=report_key, er_map=er,
        resolve_fn=resolve_injury_row(er))
    qrows = quote_rows(quote_entries, commence_off, **(quote_kwargs or {}))
    series, exc_rows, n_inplay = L.build_quote_series(
        qrows, qpl, er, {**L.DEFAULT_CONFIG, **cfg})
    return {"er": er, "cfg": cfg, "epl": epl, "qpl": qpl,
            "events": events, "excluded_events": exc_events,
            "series": series, "excluded_rows": exc_rows,
            "n_inplay": n_inplay}


# ---------------------------------------------------------------------------
# Named fixtures
# ---------------------------------------------------------------------------
MIN = 60
HOUR = 3600


def fx_clean():
    """5-minute grids on both streams.  P1 goes Questionable->Out first seen
    at poll +30m (interval (+25m,+30m]).  Clean PRE change at (+10m,+15m],
    clean POST change at (+40m,+45m].  Commence +8h.
    Truth: PRE=(600,900], POST_FIRST=(2400,2700], H+5 UNRESOLVED (no quote
    poll in (+30m,+35m]... quote polls every 5m so +35m poll EXISTS -> OK),
    reaction claim exactly t_lower=566, t_upper=1234, grid=634 (see TESTS).
    """
    polls = [i * 5 * MIN for i in range(0, 97)]  # +0 .. +8h, 5-min grid
    events = []
    for t in polls[:12]:  # up to +55m, full state each poll
        st = "Out" if t >= 30 * MIN else "Questionable"
        events.append((t, HOME, P1, st))
    quotes = []
    for t in polls:
        if t < 15 * MIN:
            price = -200
        elif t < 45 * MIN:
            price = -215          # change first seen at +15m: (600,900]
        else:
            price = -260          # change first seen at +45m: (2400,2700]
        quotes.append((t, price))
    fx = build(events, quotes, commence_off=8 * HOUR,
               event_polls=[t for t in polls[:12]], quote_polls=polls)
    fx["truth"] = {
        "event_interval": [T0 + 25 * MIN, T0 + 30 * MIN],
        "pre": [T0 + 10 * MIN, T0 + 15 * MIN],
        "post": [T0 + 40 * MIN, T0 + 45 * MIN],
        "t_lower": 566, "t_upper": 1234, "grid": 634,
    }
    return fx


def fx_grid_unresolved():
    """Event stream 5-min, quote stream HOURLY.  Event width 300s <= h*60
    for h>=5, but no quote poll lands inside (e_up, e_up+h] for h<60
    -> UNRESOLVED_AT_GRID for H+5..H+30, resolvable at H+60."""
    event_polls = [i * 5 * MIN for i in range(0, 13)]        # to +60m
    quote_polls = [0, HOUR, 2 * HOUR, 3 * HOUR, 4 * HOUR]
    # first seen at +25m -> interval (+20m,+25m]; e_up+30m = +55m falls short
    # of the next hourly quote poll, so H+30 is genuinely unresolvable
    events = [(t, HOME, P1, "Out" if t >= 25 * MIN else "Probable")
              for t in event_polls]
    quotes = [(t, -200 if t < 2 * HOUR else -240) for t in quote_polls]
    fx = build(events, quotes, commence_off=6 * HOUR,
               event_polls=event_polls, quote_polls=quote_polls)
    fx["truth"] = {"unresolved": ["H+5", "H+10", "H+15", "H+30"],
                   "poll_gap": ["H+1", "H+2"],   # width 300 > 60,120
                   "ok": ["H+60"]}
    return fx


def fx_hourly_jitter():
    """Both streams hourly with +1s jitter on the event side: the event
    interval is 3601s, one second wider than the H+60 horizon ->
    POLL_GAP_EXCEEDS_HORIZON even at H+60. This is the real tape's regime."""
    event_polls = [0, HOUR, 2 * HOUR + 1, 3 * HOUR + 1]
    quote_polls = [0, HOUR, 2 * HOUR, 3 * HOUR, 4 * HOUR, 5 * HOUR]
    events = [(t, HOME, P1, "Out" if t >= 2 * HOUR else "Probable")
              for t in event_polls]
    quotes = [(t, -200 if t < 4 * HOUR else -230) for t in quote_polls]
    fx = build(events, quotes, commence_off=8 * HOUR,
               event_polls=event_polls, quote_polls=quote_polls)
    fx["truth"] = {"event_width": 3601,
                   "all_horizons_poll_gap": ["H+1", "H+2", "H+5", "H+10",
                                             "H+15", "H+30", "H+60"]}
    return fx


def fx_ambiguous():
    """The only quote change overlaps the event interval -> AMBIGUOUS_PRE,
    record excluded, retained."""
    polls = [i * 10 * MIN for i in range(0, 25)]
    events = [(t, HOME, P1, "Out" if t >= 40 * MIN else "Questionable")
              for t in polls[:8]]
    # quote change first seen at +40m: interval (30m,40m] overlaps event
    # interval (30m,40m] exactly
    quotes = [(t, -200 if t < 40 * MIN else -250) for t in polls]
    fx = build(events, quotes, commence_off=6 * HOUR,
               event_polls=polls[:8], quote_polls=polls)
    fx["truth"] = {"primary_reason": L.REASON_AMBIGUOUS_PRE}
    return fx


def fx_overnight():
    """Event interval spans a synthetic 11h poller gap; it stays a wide
    interval, never patched, unusable below its own width."""
    event_polls = [0, HOUR, 12 * HOUR, 13 * HOUR]
    quote_polls = [0, HOUR, 12 * HOUR, 13 * HOUR, 14 * HOUR]
    events = [(t, HOME, P1, "Out" if t >= 12 * HOUR else "Probable")
              for t in event_polls]
    quotes = [(t, -200 if t < 13 * HOUR else -280) for t in quote_polls]
    fx = build(events, quotes, commence_off=16 * HOUR,
               event_polls=event_polls, quote_polls=quote_polls)
    fx["truth"] = {"event_interval": [T0 + HOUR, T0 + 12 * HOUR],
                   "width": 11 * HOUR}
    return fx


def fx_suspended():
    """Series disappears across the event interval and reopens after ->
    SUSPENDED_ACROSS_EVENT."""
    polls = [i * 10 * MIN for i in range(0, 31)]
    events = [(t, HOME, P1, "Out" if t >= 60 * MIN else "Questionable")
              for t in polls[:10]]
    quotes = []
    for t in polls:
        if 50 * MIN <= t < 80 * MIN:
            quotes.append((t, None))          # suspended: rows absent
        else:
            quotes.append((t, -200 if t < 80 * MIN else -240))
    fx = build(events, quotes, commence_off=8 * HOUR,
               event_polls=polls[:10], quote_polls=polls)
    fx["truth"] = {"primary_reason": L.REASON_SUSPENDED}
    return fx


def fx_multi_player():
    """One report flips BOTH P1 and P2 to Out at the same poll -> two
    player events, one report_id, ONE composite record on the game series."""
    polls = [i * 10 * MIN for i in range(0, 25)]
    events = []
    for t in polls[:8]:
        st = "Out" if t >= 40 * MIN else "Questionable"
        events.append((t, HOME, P1, st))
        events.append((t, HOME, P2, st))
    quotes = [(t, -200 if t < 60 * MIN else -260) for t in polls]
    fx = build(events, quotes, commence_off=8 * HOUR,
               event_polls=polls[:8], quote_polls=polls)
    fx["truth"] = {"n_records": 1, "n_members": 2}
    return fx


def fx_same_poll_pileup():
    """Two DIFFERENT reports (different report_date) first seen at the same
    poll -> identical intervals, mutually confounded at every horizon."""
    polls = [i * 10 * MIN for i in range(0, 25)]
    rows = []
    for t in polls[:8]:
        st1 = "Out" if t >= 40 * MIN else "Questionable"
        rows.append({"capture_utc": _mk(t), "report_date": "2030-01-01",
                     "game_date": "2030-01-01", "team": HOME, "player": P1,
                     "status": st1, "reason": "-", "source": "synthetic_official"})
        rows.append({"capture_utc": _mk(t), "report_date": "2030-01-02",
                     "game_date": "2030-01-01", "team": HOME, "player": P2,
                     "status": st1, "reason": "-", "source": "synthetic_official"})
    er = er_map([8 * HOUR])
    epl = L.PollLog([_mk(t) for t in polls[:8]])
    qpl = L.PollLog([_mk(t) for t in polls])
    events, exc = L.build_events_full_state(
        rows, epl, stream="injury", tier="T0",
        entity_fields=("team", "player"), state_field="status",
        report_key_fn=lambda r, t: [r["source"], r["report_date"], t],
        er_map=er, resolve_fn=resolve_injury_row(er))
    quotes = quote_rows([(t, -200 if t < 60 * MIN else -260) for t in polls],
                        8 * HOUR)
    series, exc_rows, n_inplay = L.build_quote_series(
        quotes, qpl, er, L.DEFAULT_CONFIG)
    return {"er": er, "cfg": dict(MEASURED_CONFIG), "epl": epl, "qpl": qpl,
            "events": events, "excluded_events": exc, "series": series,
            "excluded_rows": exc_rows, "n_inplay": n_inplay,
            "truth": {"n_records": 2, "both_confounded": True}}


def fx_entity_unresolved():
    """Team absent from the frozen ER map -> event fails closed, retained,
    reported; quote row for an unmapped game fails closed likewise."""
    polls = [i * 10 * MIN for i in range(0, 13)]
    events = [(t, "Gamma Village Cats", "Zed Nobody",
               "Out" if t >= 40 * MIN else "Questionable")
              for t in polls[:8]]
    quotes = [(t, -200) for t in polls]
    fx = build(events, quotes, commence_off=6 * HOUR,
               event_polls=polls[:8], quote_polls=polls)
    # one quote row for a game not in the ER map
    bad = {"snapshot_utc": _mk(0), "commence_time": _mk(6 * HOUR),
           "home_team": HOME2, "away_team": AWAY2, "bookmaker": "bookx",
           "market": "h2h", "outcome": HOME2, "point": "", "price": "-110"}
    s2, exc2, _ = L.build_quote_series([bad], fx["qpl"], fx["er"],
                                       L.DEFAULT_CONFIG)
    fx["excluded_rows"] += exc2
    fx["truth"] = {"n_unlinkable_events": 1, "n_unlinkable_rows": 1}
    return fx


def fx_truncated():
    """Event first seen 10 minutes before commence with no later pregame
    quote poll -> TRUNCATED_AT_COMMENCE."""
    event_polls = [0, 30 * MIN, 50 * MIN]
    quote_polls = [0, 20 * MIN, 40 * MIN]
    events = [(t, HOME, P1, "Out" if t >= 50 * MIN else "Probable")
              for t in event_polls]
    quotes = [(t, -200) for t in quote_polls]
    fx = build(events, quotes, commence_off=HOUR,
               event_polls=event_polls, quote_polls=quote_polls)
    fx["truth"] = {"primary_reason": L.REASON_TRUNCATED}
    return fx


def fx_inplay():
    """Rows at/after commence are structurally excluded at series
    construction; a series with only in-play rows never exists."""
    polls = [i * 10 * MIN for i in range(0, 13)]
    event_polls = polls[:6]
    events = [(t, HOME, P1, "Out" if t >= 30 * MIN else "Probable")
              for t in event_polls]
    # commence at +60m; quotes at +0..+120m -- everything >= +60m must drop
    quotes = [(t, -200 if t < 40 * MIN else -230) for t in polls]
    fx = build(events, quotes, commence_off=HOUR,
               event_polls=event_polls, quote_polls=polls)
    fx["truth"] = {"n_inplay": 7,      # polls +60..+120 inclusive, 10-min grid
                   "max_obs_lt_commence": True}
    return fx


def fx_right_censored():
    """No quote change after the event before close -> right-censored claim
    (censor_type='right', t_upper=INF)."""
    polls = [i * 10 * MIN for i in range(0, 25)]
    events = [(t, HOME, P1, "Out" if t >= 40 * MIN else "Questionable")
              for t in polls[:8]]
    quotes = [(t, -215 if t >= 20 * MIN else -200) for t in polls]
    # only change is PRE (first seen +20m); nothing moves after the event
    fx = build(events, quotes, commence_off=8 * HOUR,
               event_polls=polls[:8], quote_polls=polls)
    fx["truth"] = {"censor_type": "right"}
    return fx


def fx_unbounded_vendor():
    """Vendor without a sourced latency bound: claim exists but is
    UNSUPPORTABLE for fine-grained statements; grid UNBOUNDED."""
    fx = fx_clean()
    fx["cfg"] = dict(fx["cfg"])
    fx["cfg"]["vendor_latency_bounds"] = {}          # bookx -> UNBOUNDED
    fx["truth"] = {"verdict": "UNSUPPORTABLE"}
    return fx


def fx_clock_unmeasured():
    """No clock-skew measurement for the run -> every record CLOCK_UNBOUNDED
    (this is the CURRENT REAL TAPE's condition)."""
    fx = fx_clean()
    fx["cfg"] = dict(fx["cfg"])
    fx["cfg"]["clock_skew"] = L.UNMEASURED
    fx["truth"] = {"primary_reason": L.REASON_CLOCK_UNBOUNDED}
    return fx


def fx_tier_t2():
    """A T2 quote series (synthetic stamps standing in for a retrospective
    harvest) -> TIER_INSUFFICIENT, structurally."""
    fx = fx_clean()
    series, exc, n_ip = L.build_quote_series(
        quote_rows([(t, -200 if t < 45 * MIN else -260)
                    for t in [i * 5 * MIN for i in range(0, 97)]],
                   8 * HOUR),
        fx["qpl"], fx["er"], L.DEFAULT_CONFIG, tier="T2")
    fx["series"] = series
    fx["truth"] = {"primary_reason": L.REASON_TIER_INSUFFICIENT}
    return fx


def run(fx):
    return L.link(fx["events"], fx["series"], fx["epl"], fx["qpl"],
                  fx["er"], fx["cfg"],
                  excluded_events=fx.get("excluded_events"),
                  excluded_quote_rows=fx.get("excluded_rows"),
                  n_inplay_rows=fx.get("n_inplay", 0))
