"""Family G — officiating interactions (#73-78). Expectations LOW.

Ref crew assignments for tonight are public pre-game (schedule fact). Crew
tendencies are strictly-prior expanding means over each ref's own game
sequence, cross-season (refs are not players; the per-season reset rule
governs player trends — documented in REPORT.md), league-centered.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .common import Candidate, TEAM_ALPHA, sew, sratio_ew, shrink, center_by_date


def f73_ftr_x_crew_fta(ctx, alpha):
    P = ctx.P
    crew = ctx.crew_on_P(["crew_fta_c"])["crew_fta_c"]
    ftr = sratio_ew(P, P["fta"], P["minutes"], alpha) * 36.0
    fc = center_by_date(P, ftr)
    return (fc * crew).fillna(0.0)


def f74_star_whistle(ctx, alpha):
    P = ctx.P
    crew = ctx.crew_on_P(["crew_fta_c"])["crew_fta_c"]
    us = sew(P, P["usage36"], alpha)
    uc = center_by_date(P, us)
    return (uc * crew).fillna(0.0)


def f75_foulprone_x_tightcrew(ctx, alpha):
    P = ctx.P
    crew = ctx.crew_on_P(["crew_pf_c"])["crew_pf_c"]
    pf36 = sratio_ew(P, P["pf"], P["minutes"], alpha) * 36.0
    pc = center_by_date(P, pf36)
    return (pc * crew).fillna(0.0)


def f76_crewpace_x_transition(ctx, alpha):
    P = ctx.P
    crew = ctx.crew_on_P(["crew_pace_c"])["crew_pace_c"]
    fb = sratio_ew(P, P["points_fast_break"], P["pts"].clip(lower=1.0), alpha)
    fc = center_by_date(P, fb)
    return (fc * crew).fillna(0.0)


def f77_tech_x_techrefs(ctx, alpha):
    P = ctx.P
    crew = ctx.crew_on_P(["crew_tech_c"])["crew_tech_c"]
    pb = ctx.pbp_on_P(["tech_fouls"])
    # career strictly-prior technical rate (rare events -> cross-season cum)
    order = P.sort_values(["player_id", "game_date", "game_id"], kind="mergesort").index
    Po = P.loc[order]
    ct = pb["tech_fouls"].loc[order].groupby(Po["player_id"]).transform(
        lambda x: x.cumsum().shift(1))
    cg = Po.groupby("player_id").cumcount().astype(float)
    rate = (ct / cg.replace(0.0, np.nan)).reindex(P.index)
    rc = center_by_date(P, rate)
    return (rc * crew).fillna(0.0)


def f78_personal_ref_history(ctx, alpha):
    """Player's strictly-prior mean pts/36 in games officiated by each of
    tonight's refs, minus their overall prior mean; shrunk k=15 games per ref;
    averaged over the crew. Cross-season by construction."""
    P = ctx.P
    off = ctx.officials_long()
    pr = P[["player_id", "game_id", "game_date", "pts", "minutes"]].copy()
    pr["pts36"] = pr["pts"] / pr["minutes"] * 36.0
    m = pr.merge(off, on="game_id", how="inner")
    m = m.sort_values(["player_id", "OFFICIAL_ID", "game_date", "game_id"],
                      kind="mergesort")
    grp = [m["player_id"], m["OFFICIAL_ID"]]
    m["ref_mean"] = m["pts36"].groupby(grp).transform(
        lambda x: x.expanding().mean().shift(1))
    m["ref_n"] = m.groupby(["player_id", "OFFICIAL_ID"]).cumcount().astype(float)
    # overall prior mean (career)
    order = P.sort_values(["player_id", "game_date", "game_id"], kind="mergesort").index
    Po = P.loc[order]
    overall = (Po["pts"] / Po["minutes"] * 36.0).groupby(Po["player_id"]).transform(
        lambda x: x.expanding().mean().shift(1)).reindex(P.index)
    ov_map = pd.DataFrame({"player_id": P["player_id"], "game_id": P["game_id"],
                           "overall": overall})
    m = m.merge(ov_map, on=["player_id", "game_id"], how="left")
    m["dev"] = shrink(m["ref_mean"] - m["overall"], m["ref_n"], k=15.0)
    agg = m.groupby(["player_id", "game_id"])["dev"].mean().reset_index()
    out = P[["player_id", "game_id"]].merge(agg, on=["player_id", "game_id"],
                                            how="left")["dev"]
    out.index = P.index
    return out.fillna(0.0)


CANDIDATES = [
    Candidate(73, "ftr_x_crew_fta", "G", f73_ftr_x_crew_fta, alpha_swept=True,
              channels=["ft"]),
    Candidate(74, "star_whistle_proxy", "G", f74_star_whistle, alpha_swept=True,
              channels=["ft"]),
    Candidate(75, "foulprone_x_crewpf", "G", f75_foulprone_x_tightcrew,
              alpha_swept=True),
    Candidate(76, "crewpace_x_transition", "G", f76_crewpace_x_transition,
              alpha_swept=True),
    Candidate(77, "tech_x_techcrew", "G", f77_tech_x_techrefs,
              note="speculative per catalog; tiny samples"),
    Candidate(78, "personal_ref_history", "G", f78_personal_ref_history,
              note="likely pure noise per catalog; cheap to kill"),
]
