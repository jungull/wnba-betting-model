"""Family A — venue, time, and travel context (#1-6, 8, 10-11).

Venue/tip/rest/trip attributes of the CURRENT game are schedule facts (known
pre-tip); all performance components are shifted as-of trends.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .common import (Candidate, TZ_OFFSET, sew, venue_split_asof, bucket_dev,
                     shrink, gps)

LEAGUE_HOME_LIFT_PTS36 = 0.38   # catalog case-study constant (league mean)


def _venue_sign(P):
    return (P["is_home"].astype(float) - 0.5) * 2.0   # +1 home, -1 away


def f01_home_lift(ctx, alpha):
    P = ctx.P
    lift = venue_split_asof(P, P["pts"] / P["minutes"] * 36.0, alpha,
                            k=20.0, prior=LEAGUE_HOME_LIFT_PTS36)
    return (lift * _venue_sign(P) * 0.5).fillna(0.0)


def _venue_pct_split(ctx, alpha, num_col, den_col, k):
    """Shrunken as-of home-vs-away percentage differential x venue sign."""
    P = ctx.P
    out = {}
    for name, home in (("h", 1), ("a", 0)):
        m = P["is_home"].astype(float).eq(home)
        grp = [P["player_id"], P["season"], m]
        cn = P[num_col].where(m).groupby(grp).transform(lambda x: x.cumsum().shift(1))
        cd = P[den_col].where(m).groupby(grp).transform(lambda x: x.cumsum().shift(1))
        r = (cn / cd.replace(0.0, np.nan)).where(m)
        r = r.groupby(gps(P)).ffill()          # carry venue ratio to later rows
        d = cd.where(m).groupby(gps(P)).ffill()
        out[name] = (r, d)
    diff = out["h"][0] - out["a"][0]
    n_eff = pd.concat([out["h"][1], out["a"][1]], axis=1).min(axis=1)
    return (shrink(diff, n_eff.fillna(0.0), k) * _venue_sign(P) * 0.5).fillna(0.0)


def f02_home_3ppct(ctx, alpha):
    return _venue_pct_split(ctx, alpha, "fg3m", "fg3a", k=60.0)


def f03_home_ftpct(ctx, alpha):
    return _venue_pct_split(ctx, alpha, "ftm", "fta", k=40.0)


def f04_home_usage_shift(ctx, alpha):
    P = ctx.P
    lift = venue_split_asof(P, P["usage36"], alpha, k=20.0, prior=0.0)
    return (lift * _venue_sign(P) * 0.5).fillna(0.0)


def f05_home_minutes_shift(ctx, alpha):
    P = ctx.P
    lift = venue_split_asof(P, P["minutes"], alpha, k=20.0, prior=0.0)
    return (lift * _venue_sign(P) * 0.5).fillna(0.0)


def f06_rest_profile(ctx, alpha):
    """Personal rest-bucket deviation, per channel (surprise vs frozen baseline
    in this rest bucket, shrunken; personalized-only — see common.bucket_dev)."""
    P = ctx.P
    out = {}
    for ch, base in ctx.baselines.items():
        d = P[f"r_{ch}"] - base
        out[ch] = bucket_dev(P, P["rest_bucket"], d, k=10.0)
    return out


def f08_tz_shift(ctx, alpha):
    P = ctx.P
    # venue = home team's city: build game -> home abbr map
    home_rows = P[P["is_home"].astype(float).eq(1)][["game_id", "team_abbreviation"]]
    game_home = home_rows.drop_duplicates("game_id").set_index("game_id")["team_abbreviation"]
    venue = P["game_id"].map(game_home)
    tz = venue.map(TZ_OFFSET).astype(float)
    prev_tz = tz.groupby(gps(P)).shift(1)
    return (tz - prev_tz).abs().fillna(0.0)


def f10_tip_split(ctx, alpha):
    """Personal afternoon-vs-evening split x tonight's tip class. Tip hour from
    PBP wall clock (ET) -> venue-local via TZ_OFFSET; afternoon = local < 17.
    (Deviation from catalog sketch: odds commence times only exist for the
    quarantined era; PBP wall clock covers 2021-24 — documented.)"""
    P = ctx.P
    game = ctx.pbp()["game"].set_index("game_id")["tip_hour_et"]
    home_rows = P[P["is_home"].astype(float).eq(1)][["game_id", "team_abbreviation"]]
    game_home = home_rows.drop_duplicates("game_id").set_index("game_id")["team_abbreviation"]
    venue_tz = P["game_id"].map(game_home).map(TZ_OFFSET).astype(float)
    local_tip = P["game_id"].map(game).astype(float) + venue_tz
    is_aft = (local_tip < 17.0).astype(float)
    out = {}
    for ch, base in ctx.baselines.items():
        d = P[f"r_{ch}"] - base
        dev = bucket_dev(P, pd.Series(np.where(is_aft == 1, "aft", "eve"),
                                      index=P.index), d, k=10.0)
        out[ch] = dev
    return out


def f11_trip_position(ctx, alpha):
    P = ctx.P
    tcols = ctx.team_cols_on_P(["venue_run_pos"])
    sign = _venue_sign(P) * -1.0   # away trip position positive, home-stand negative
    return (tcols["t_venue_run_pos"] * sign * -1.0).fillna(0.0)


CANDIDATES = [
    Candidate(1, "home_lift_shrunk", "A", f01_home_lift, alpha_swept=True,
              note="pts/36 home-away EWMA split, shrunk to +0.38 league mean, x venue sign"),
    Candidate(2, "home_3ppct_diff", "A", f02_home_3ppct, channels=["fg3"],
              note="cum 3P% home-away diff (shifted), shrunk k=60 att, x venue sign"),
    Candidate(3, "home_ftpct_diff", "A", f03_home_ftpct, channels=["ft"],
              note="cum FT% home-away diff (shifted), shrunk k=40 att, x venue sign"),
    Candidate(4, "home_usage_shift", "A", f04_home_usage_shift, alpha_swept=True),
    Candidate(5, "home_minutes_shift", "A", f05_home_minutes_shift, alpha_swept=True),
    Candidate(6, "rest_bucket_profile", "A", f06_rest_profile,
              note="personal shrunken surprise-vs-baseline in rest bucket {<=1,2,3+}"),
    Candidate(8, "timezone_shift", "A", f08_tz_shift,
              note="|venue tz - previous-game venue tz| hours (schedule fact)"),
    Candidate(10, "tip_time_split", "A", f10_tip_split,
              note="personal afternoon/evening surprise profile; tip from PBP wall clock"),
    Candidate(11, "trip_position", "A", f11_trip_position,
              note="nth consecutive same-venue game, signed away=+ (schedule fact)"),
]
