"""Family E — lineup context and teammate interaction (#49-60).

Built from possessions.parquet (per-possession 10-player lineups) and the
derive_lineups.py outputs (data/derived/starters.csv). Per-player-game
possession aggregates and same-team pair tables come from Ctx.pgposs() /
Ctx.pairs(). Player-level production attribution inside stint windows is NOT
publicly derivable without event-to-lineup joins for every stat, so #49/#56
use the documented honest reductions (game-level star splits; team
points-per-possession pair lift).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .common import (Candidate, CHANNELS, TEAM_ALPHA, sew, sratio_ew, sroll,
                     shrink, gps, center_by_date)


def _usage_asof(ctx):
    P = ctx.P
    return sew(P, P["usage36"], TEAM_ALPHA)


def f49_star_onoff(ctx, alpha):
    """Game-level with/without-star split (honest reduction of the stint-level
    sketch, documented): star = the team's season-to-date top-as-of-usage
    player (strictly prior); the split is the player's as-of mean
    surprise-vs-baseline in star-absent games minus star-present games
    (shrunk, k=8 each side); screened as split x as-of availability flag
    (star did not play the team's previous game)."""
    P = ctx.P
    u = _usage_asof(ctx).fillna(0.0)
    roster = P.groupby(["game_id", "team_id"])["player_id"].agg(set).to_dict()
    u_by_gt = {k: dict(zip(P["player_id"].to_numpy()[idx], u.to_numpy()[idx]))
               for k, idx in P.groupby(["game_id", "team_id"]).indices.items()}
    team_games = ctx.team().sort_values(["team_id", "season", "game_date"],
                                        kind="mergesort")
    team_games["prev_game_id"] = team_games.groupby(["team_id", "season"])["game_id"].shift(1)
    prev_map = dict(zip(zip(team_games["team_id"], team_games["game_id"]),
                        team_games["prev_game_id"]))
    # star strictly-prior per (game, team): running argmax of as-of usage
    best_val: dict = {}
    best_id: dict = {}
    star_prior: dict = {}
    for tid, season, gid in zip(team_games["team_id"], team_games["season"],
                                team_games["game_id"]):
        key = (tid, season)
        star_prior[(gid, tid)] = best_id.get(key)
        for pid_, uv in u_by_gt.get((gid, tid), {}).items():
            if key not in best_val or uv > best_val[key]:
                best_val[key] = uv
                best_id[key] = pid_
    P_star = [star_prior.get((g, t)) for g, t in zip(P["game_id"], P["team_id"])]
    P_prev = [prev_map.get((t, g)) for t, g in zip(P["team_id"], P["game_id"])]
    star_out = pd.Series([
        float(s is not None and isinstance(pg, str)
              and s not in roster.get((pg, t), set()))
        for s, pg, t in zip(P_star, P_prev, P["team_id"])], index=P.index)
    star_absent_now = pd.Series([
        float(s is not None and s not in roster.get((g, t), set()))
        for s, g, t in zip(P_star, P["game_id"], P["team_id"])], index=P.index)
    # self is never their own star's absentee signal
    is_self = pd.Series([float(s == p) for s, p in zip(P_star, P["player_id"])],
                        index=P.index)
    star_out = star_out * (1.0 - is_self)
    g = gps(P)
    out = {}
    for ch in CHANNELS:
        dev = (P[f"r_{ch}"] - ctx.baselines[ch])
        m_abs = dev.where(star_absent_now == 1).groupby(g).transform(
            lambda s: s.expanding().mean())          # incl-mean, NaN-skipping
        m_abs = m_abs.groupby(g).shift(1)            # strictly prior
        m_pre = dev.where(star_absent_now == 0).groupby(g).transform(
            lambda s: s.expanding().mean())
        m_pre = m_pre.groupby(g).shift(1)
        n_abs = star_absent_now.groupby(g).transform(lambda s: s.cumsum()).groupby(g).shift(1)
        n_pre = (1.0 - star_absent_now).groupby(g).transform(lambda s: s.cumsum()).groupby(g).shift(1)
        split = m_abs - m_pre
        n_eff = pd.concat([n_abs, n_pre], axis=1).min(axis=1)
        out[ch] = (shrink(split, n_eff.fillna(0.0), k=8.0) * star_out).fillna(0.0)
    return out


def f50_usage_absorption(ctx, alpha):
    """Elasticity of own usage to vacated teammate usage x tonight's vacated
    usage. Vacated usage: sum of as-of usage36 of teammates who played in the
    team's last-3 window but not the last game (minutes_twostage vacated
    pattern, usage flavor). Elasticity: shifted expanding OLS slope of own
    usage36 on vacated usage within season, shrunk k=10."""
    P = ctx.P
    u = _usage_asof(ctx).fillna(0.0)
    T = ctx.team().sort_values(["team_id", "season", "game_date"], kind="mergesort")
    roster = P.groupby(["game_id", "team_id"])["player_id"].agg(set).to_dict()
    useq = {}
    for (gid, tid), idx in P.groupby(["game_id", "team_id"]).indices.items():
        useq[(gid, tid)] = dict(zip(P["player_id"].to_numpy()[idx], u.to_numpy()[idx]))
    games_by_team = {k: v for k, v in T.groupby(["team_id", "season"])["game_id"].agg(list).items()}
    vac_by_game = {}
    for (tid, season), games in games_by_team.items():
        last_seen_u: dict = {}
        appear_hist: dict = {}
        for j, gid in enumerate(games):
            cur = roster.get((gid, tid), set())
            v = 0.0
            if j >= 1:
                prev = roster.get((games[j - 1], tid), set())
                window = set()
                for jj in range(max(0, j - 3), j):
                    window |= roster.get((games[jj], tid), set())
                for m in window - prev:
                    v += last_seen_u.get(m, 0.0)
            vac_by_game[(gid, tid)] = v
            for m in cur:
                last_seen_u[m] = useq.get((gid, tid), {}).get(m, last_seen_u.get(m, 0.0))
    P_vac = pd.Series([vac_by_game.get((g, t), 0.0)
                       for g, t in zip(P["game_id"], P["team_id"])], index=P.index)
    # shifted expanding OLS slope of usage36 on vacated within (player, season)
    x, y = P_vac, P["usage36"]
    g = gps(P)
    def cshift(s):
        return s.groupby(g).transform(lambda v: v.cumsum().shift(1))
    n = P["prior_apps"].astype(float)
    sx, sy = cshift(x), cshift(y)
    sxy, sxx = cshift(x * y), cshift(x * x)
    cov = sxy - sx * sy / n.replace(0, np.nan)
    var = sxx - sx ** 2 / n.replace(0, np.nan)
    slope = (cov / var.replace(0, np.nan)).clip(-3, 3)
    slope = shrink(slope, n, k=10.0).fillna(0.0)
    return (slope * P_vac).fillna(0.0)


def f51_lineup_familiarity(ctx, alpha):
    """Mean cumulative shared possessions (season to date) with the 4 teammates
    most shared-with in the player's PREVIOUS game — all strictly prior."""
    P = ctx.P
    pr = ctx.pairs()
    gd = ctx.game_dates()[["game_id", "season"]]
    pr = pr.merge(gd, on="game_id", how="left")
    key = P[["player_id", "season", "game_id"]].copy()
    post = np.full(len(P), np.nan)
    pr_by = {k: v for k, v in pr.groupby(["p1", "season"])}
    idx_by_group = P.groupby(["player_id", "season"]).indices
    gid_np = P["game_id"].to_numpy()
    for (pid, season), idx in idx_by_group.items():
        sub = pr_by.get((pid, season))
        if sub is None:
            continue
        by_game = {g: list(zip(s["p2"], s["n_shared"]))
                   for g, s in sub.groupby("game_id")}
        cum: dict = {}
        for row in idx:
            gid = gid_np[row]
            mates = by_game.get(gid, [])
            # post value for THIS game: top-4 partners tonight, their cum incl tonight
            if mates:
                mates_sorted = sorted(mates, key=lambda t: -t[1])[:4]
                tot = 0.0
                for m, nsh in mates_sorted:
                    tot += cum.get(m, 0.0) + nsh
                post[row] = tot / len(mates_sorted)
            for m, nsh in mates:
                cum[m] = cum.get(m, 0.0) + nsh
    s = pd.Series(post, index=P.index)
    return s.groupby(gps(P)).shift(1).fillna(0.0)


def f52_onfloor_pace_diff(ctx, alpha):
    P = ctx.P
    pg = ctx.pgposs_on_P(["n_on", "dur_on", "n_game_poss", "game_dur"])
    mine = pg["n_on"] / (pg["dur_on"] / 60.0).replace(0.0, np.nan)
    game = pg["n_game_poss"] / (pg["game_dur"] / 60.0).replace(0.0, np.nan)
    return sew(P, (mine - game).fillna(0.0), alpha).fillna(0.0)


def f53_gravity_x_paint(ctx, alpha):
    P = ctx.P
    # teammates' 3PA gravity = team as-of 3PA (slow) minus player's own as-of 3PA
    team3 = ctx.team_cols_on_P(["fg3a_slow"])["t_fg3a_slow"]
    own_3pa = sew(P, P["fg3a"], TEAM_ALPHA).fillna(0.0)
    gravity = (team3 - own_3pa)
    gravity_c = center_by_date(P, gravity)
    reliance = sratio_ew(P, P["cp_paint"], P["pts"].clip(lower=1.0), alpha)
    rc = center_by_date(P, reliance)
    return (gravity_c * rc).fillna(0.0)


def f54_starter_unit_share(ctx, alpha):
    P = ctx.P
    pg = ctx.pgposs_on_P(["n_with3own", "n_on"])
    share = pg["n_with3own"] / pg["n_on"].replace(0.0, np.nan)
    return sew(P, share.fillna(0.0), alpha).fillna(0.0)


def f55_closing_membership(ctx, alpha):
    P = ctx.P
    pg = ctx.pgposs_on_P(["n_closing_on", "n_game_closing"])
    g = gps(P)
    cn = pg["n_closing_on"].groupby(g).transform(lambda x: x.cumsum().shift(1))
    cd = pg["n_game_closing"].groupby(g).transform(lambda x: x.cumsum().shift(1))
    share = cn / cd.replace(0.0, np.nan)
    return shrink(share, cd.fillna(0.0), k=20.0).fillna(0.0)


def f56_best_pair_lift(ctx, alpha):
    """Team ppp with (player+best partner) on floor minus ppp with player on,
    partner off — best partner by cumulative shared OFF possessions, all
    strictly prior, shrunk k=200 possessions."""
    P = ctx.P
    pr = ctx.pairs().merge(ctx.game_dates()[["game_id", "season"]], on="game_id", how="left")
    pg = ctx.pgposs()[["game_id", "player_id", "n_off_on", "off_pts_on"]]
    pg_map = {(g, p): (n, pts) for g, p, n, pts in
              zip(pg["game_id"], pg["player_id"], pg["n_off_on"], pg["off_pts_on"])}
    post = np.full(len(P), np.nan)
    pr_by = {k: v for k, v in pr.groupby(["p1", "season"])}
    idx_by_group = P.groupby(["player_id", "season"]).indices
    gid_np = P["game_id"].to_numpy()
    for (pid, season), idx in idx_by_group.items():
        sub = pr_by.get((pid, season))
        if sub is None:
            continue
        by_game = {g: list(zip(s["p2"], s["n_off_shared"], s["off_pts_shared"]))
                   for g, s in sub.groupby("game_id")}
        cum_n: dict = {}; cum_p: dict = {}
        tot_n = 0.0; tot_p = 0.0
        for row in idx:
            gid = gid_np[row]
            if cum_n:
                t_star = max(cum_n, key=cum_n.get)
                n_with = cum_n[t_star]; p_with = cum_p[t_star]
                n_wo = tot_n - n_with; p_wo = tot_p - p_with
                if n_with >= 20 and n_wo >= 20:
                    lift = p_with / n_with - p_wo / n_wo
                    w = n_with / (n_with + 200.0)
                    post[row] = w * lift
            mates = by_game.get(gid, [])
            for m, n_off, p_off in mates:
                cum_n[m] = cum_n.get(m, 0.0) + n_off
                cum_p[m] = cum_p.get(m, 0.0) + p_off
            g_n, g_p = pg_map.get((gid, pid), (0.0, 0.0))
            tot_n += g_n; tot_p += g_p
    return pd.Series(post, index=P.index).fillna(0.0)


def f57_competition_quality(ctx, alpha):
    P = ctx.P
    pg = ctx.pgposs_on_P(["n_vs3opp", "n_on"])
    share = pg["n_vs3opp"] / pg["n_on"].replace(0.0, np.nan)
    return sew(P, share.fillna(0.0), alpha).fillna(0.0)


def f58_stint_pm_stability(ctx, alpha):
    P = ctx.P
    pg = ctx.pgposs_on_P(["off_pts_on", "def_pts_on", "n_on"])
    net = (pg["off_pts_on"] - pg["def_pts_on"]) / pg["n_on"].replace(0.0, np.nan) * 100.0
    return sroll(P, net.fillna(0.0), 10, "std", min_periods=4).fillna(0.0)


def f59_system_dependence(ctx, alpha):
    P = ctx.P
    ast = ctx.team_cols_on_P(["astrate_sew_c"])["t_astrate_sew_c"]
    p3 = sratio_ew(P, P["fg3a"], P["minutes"], alpha) * 36.0
    p3c = center_by_date(P, p3)
    return (p3c * ast).fillna(0.0)


def f60_second_unit_anchor(ctx, alpha):
    P = ctx.P
    g = gps(P)
    start_share = P["starter_flag"].groupby(g).transform(
        lambda x: x.rolling(5, min_periods=1).mean().shift(1))
    pg = ctx.pgposs_on_P(["n_with3own", "n_on"])
    share = pg["n_with3own"] / pg["n_on"].replace(0.0, np.nan)
    share_sew = sew(P, share.fillna(0.0), TEAM_ALPHA)
    return ((1.0 - start_share.fillna(0.0)) * share_sew.fillna(0.0)).fillna(0.0)


CANDIDATES = [
    Candidate(49, "star_onoff_split", "E", f49_star_onoff,
              note="game-level star in/out split (honest reduction of stint on/off)"),
    Candidate(50, "usage_absorption_elasticity", "E", f50_usage_absorption),
    Candidate(51, "lineup_familiarity", "E", f51_lineup_familiarity),
    Candidate(52, "onfloor_pace_diff", "E", f52_onfloor_pace_diff, alpha_swept=True,
              note="PROXY per catalog: possessions/min on floor vs game"),
    Candidate(53, "gravity_x_paint", "E", f53_gravity_x_paint, alpha_swept=True,
              channels=["paint"]),
    Candidate(54, "starter_unit_share", "E", f54_starter_unit_share, alpha_swept=True,
              note="share of possessions with >=3 own starters (context share, not production split)"),
    Candidate(55, "closing_lineup_membership", "E", f55_closing_membership),
    Candidate(56, "best_pair_lift", "E", f56_best_pair_lift,
              note="team-ppp pair lift (honest reduction; personal attribution not derivable)"),
    Candidate(57, "competition_quality", "E", f57_competition_quality, alpha_swept=True),
    Candidate(58, "stint_pm_stability", "E", f58_stint_pm_stability),
    Candidate(59, "system_dependence", "E", f59_system_dependence, alpha_swept=True,
              channels=["fg3"]),
    Candidate(60, "second_unit_anchor", "E", f60_second_unit_anchor),
]
