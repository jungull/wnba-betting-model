"""TEST-ONLY vendored baseline for the O14 adoption suite.

`player_layer_baseline` is the faithful port of daily_forecast.py:640-760
shipped by the research node (experiments/player_program/ops_lane/
O14_OPS_ENTITY_RESOLUTION/fix_entity_resolution.py, vendored verbatim).  It
exists so the adopted fix can be diffed against the frozen baseline behaviour
without executing the real forecaster.  NOTHING imports this from production.
"""
from __future__ import annotations

import re
import unicodedata

import numpy as np
import pandas as pd

MINUTES_ALPHA = 0.30          # daily_forecast.py:112
RECENCY_GAMES = 3             # daily_forecast.py:120


def _norm_name(s: str) -> str:            # daily_forecast.py:606-609, verbatim
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _ewma(m: pd.Series):
    if not len(m):
        return None
    return float(m.ewm(alpha=MINUTES_ALPHA, adjust=True).mean().iloc[-1])


def player_layer_baseline(teams: list, p: pd.DataFrame, inj: pd.DataFrame,
                          abbr_to_name: dict, gaps) -> dict:
    out: dict = {}
    have_inj = len(inj) > 0
    for team_ab in sorted(teams):
        tp = p[p.team_abbreviation == team_ab]
        if not len(tp):
            gaps.add("WARN", "player-layer", f"{team_ab}: no season rows")
            out[team_ab] = {"available": [], "out": [], "unknown_roster": True}
            continue
        tgames = sorted(tp.game_id.unique(),
                        key=lambda gid: tp[tp.game_id == gid].game_date.iloc[0])
        recent = set(tgames[-RECENCY_GAMES:])
        roster = tp[tp.game_id.isin(recent)].player_name.unique()
        team_inj = (inj[inj.team == abbr_to_name.get(team_ab, "?")]
                    if len(inj) else pd.DataFrame())
        inj_by_norm = ({_norm_name(r.player): r for r in team_inj.itertuples()}
                       if len(team_inj) else {})
        matched, avail, outs = set(), [], []
        for name in sorted(roster):
            hist = (tp[(tp.player_name == name) & tp.minutes.notna()
                       & (tp.minutes > 0)].sort_values(["game_date", "game_id"]))
            rec = {"player": name, "games_played": int(len(hist)),
                   "min_ewma": _ewma(hist.minutes),
                   "cold_start": len(hist) == 0, "designation": None}
            hit = inj_by_norm.get(_norm_name(name))
            if hit is not None:
                matched.add(_norm_name(name))
                rec["designation"] = hit.status
            (outs if rec["designation"] == "Out" else avail).append(rec)
        season_by_norm = {_norm_name(n): n for n in tp.player_name.unique()}
        unmatched = []
        for n, r in inj_by_norm.items():
            if n in matched:
                continue
            if season_by_norm.get(n) is None:
                unmatched.append(f"{r.player} ({r.status})")
                gaps.add("WARN", "player-layer",
                         f"{team_ab}: injury-report player {r.player!r} "
                         f"({r.status}) matches NO ONE in the team's season "
                         "history — new signing or name mismatch; if the "
                         "status is Out and the player is rostered under "
                         "another spelling, the gate did NOT fire")
        ew = [a["min_ewma"] for a in avail if a["min_ewma"] is not None]
        out[team_ab] = {
            "availability_data": have_inj, "available": avail, "out": outs,
            "n_roster": len(roster), "n_out": len(outs),
            "sum_min_ewma_available": float(np.nansum(ew)) if ew else None,
            "vacated_min_ewma": float(np.nansum(
                [o["min_ewma"] for o in outs if o["min_ewma"] is not None])),
            "unmatched_injury_rows": unmatched, "unknown_roster": False,
        }
    return out
