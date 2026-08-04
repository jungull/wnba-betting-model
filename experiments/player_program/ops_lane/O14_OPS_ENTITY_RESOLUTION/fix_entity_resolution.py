"""O14_OPS_ENTITY_RESOLUTION -- baseline port + designed fix, isolated.

`player_layer_baseline` is a faithful port of `daily_forecast.py:640-760`
(the frozen prospective player layer).  It exists so the defect can be
reproduced without executing the real forecaster's slate/odds/network path,
and so a fix can be diffed against it.  It is NOT a replacement, and NOTHING
in this file is imported by the production path.

`player_layer_resolved` is the DESIGNED FIX.  It is confined to this node's
directory and merges nothing.  Four changes, each traceable to a measured
defect (see REPORT.md / MEASUREMENTS.json):

  F1  identity-keyed history.  Minutes history for a player is taken from her
      player_id across the whole season, not from the team-filtered frame.
      Fixes: baseline discards prior-team rows of a mid-season transfer
      (daily_forecast.py:654 + 674).
  F2  single-tenancy.  A player_id belongs to exactly one team as of the
      cutoff -- the team of her most recent game, unless a MORE RECENT injury
      designation names a different team, in which case the designation wins
      and the assignment is flagged `designation_transfer`.
      Fixes: baseline can put one player on two teams' recency rosters and
      count her minutes twice (daily_forecast.py:662-665, 743).
  F3  designations bind by identity, not by (franchise-name, spelling) pair.
      A designation is attached to the player_id it resolves to, wherever she
      is rostered.  Fixes: an Out published under the new franchise before the
      master has ingested a game for that franchise cannot fire the Phase-3
      gate (daily_forecast.py:667-669, 685, 731-735).
  F4  fail-closed.  An Out/Doubtful designation that binds to NO player_id
      raises severity BLOCK, not WARN, and produces an explicit cold-start
      player object rather than silently vanishing.

The fix deliberately does NOT introduce fuzzy matching: resolution is still
normalized-exact, plus an explicit, auditable alias table (empty by default).
Measurement M4 shows fuzzy matching would have recovered nothing on this feed.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

MINUTES_ALPHA = 0.30          # daily_forecast.py:112
RECENCY_GAMES = 3             # daily_forecast.py:120

ALIAS_TABLE = Path(__file__).resolve().parent / "alias_table.json"


def _norm_name(s: str) -> str:            # daily_forecast.py:606-609, verbatim
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", s.lower())


class Gaps:
    """Minimal stand-in for daily_forecast.Gaps -- collects (sev, area, msg)."""

    def __init__(self):
        self.items: list[tuple[str, str, str]] = []

    def add(self, sev, area, msg):
        self.items.append((sev, area, msg))

    def by_sev(self, sev):
        return [i for i in self.items if i[0] == sev]


def _ewma(m: pd.Series):
    if not len(m):
        return None
    return float(m.ewm(alpha=MINUTES_ALPHA, adjust=True).mean().iloc[-1])


# ---------------------------------------------------------------------------
# BASELINE -- faithful port of daily_forecast.py:640-760
# ---------------------------------------------------------------------------
def player_layer_baseline(teams: list[str], p: pd.DataFrame, inj: pd.DataFrame,
                          abbr_to_name: dict, gaps: Gaps) -> dict:
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


# ---------------------------------------------------------------------------
# FIX
# ---------------------------------------------------------------------------
def load_aliases() -> dict:
    """capture-name (normalized) -> player_id.  Explicit and auditable; there
    is no fuzzy fallback anywhere in this path."""
    if not ALIAS_TABLE.exists():
        return {}
    raw = json.loads(ALIAS_TABLE.read_text(encoding="utf-8"))
    return {_norm_name(k): int(v) for k, v in raw.get("aliases", {}).items()}


def build_identity_index(p_all: pd.DataFrame, season: int) -> dict:
    """normalized name -> player_id.  Season first (so a name reused across
    eras binds to the current holder), then any earlier season, so a returning
    player is a KNOWN identity rather than an unresolvable string."""
    idx: dict[str, int] = {}
    for sub in (p_all[p_all.season < season], p_all[p_all.season == season]):
        for pid, nm in sub[["player_id", "player_name"]].drop_duplicates().itertuples(index=False):
            idx[_norm_name(nm)] = int(pid)
    return idx


def player_layer_resolved(teams: list[str], p: pd.DataFrame, inj: pd.DataFrame,
                          abbr_to_name: dict, gaps: Gaps,
                          p_all: pd.DataFrame | None = None,
                          season: int | None = None) -> dict:
    p_all = p if p_all is None else p_all
    season = int(p.season.max()) if season is None else season
    name_to_id = build_identity_index(p_all, season)
    name_to_id.update(load_aliases())
    id_to_name = (p[["player_id", "player_name"]].drop_duplicates()
                  .set_index("player_id").player_name.to_dict())
    have_inj = len(inj) > 0
    team_set = set(teams)

    # ---- resolve every designation to an identity, once, globally (F3/F4) --
    designations: dict[int, dict] = {}
    unbound: list[dict] = []
    if have_inj:
        for r in inj.itertuples():
            pid = name_to_id.get(_norm_name(r.player))
            claim_team = abbr_to_name and next(
                (ab for ab, nm in abbr_to_name.items() if nm == r.team), None)
            if pid is None:
                unbound.append({"player": r.player, "status": r.status,
                                "team": r.team, "abbr": claim_team})
                sev = "BLOCK" if r.status in ("Out", "Doubtful") else "WARN"
                gaps.add(sev, "entity-resolution",
                         f"{r.team}: designation {r.status!r} for {r.player!r} "
                         "resolves to NO player identity in any season — "
                         "cold start or unlisted alias. "
                         + ("FAIL-CLOSED: the availability estimate for this "
                            "team is not trustworthy until an alias or a "
                            "cold-start object is supplied."
                            if sev == "BLOCK" else
                            "Recorded as a cold-start player object."))
                continue
            designations[pid] = {"status": r.status, "claim_team": claim_team,
                                 "claim_name": r.player}

    # ---- single tenancy (F2) ------------------------------------------------
    s = p.sort_values(["game_date", "game_id"])
    last_team = s.groupby("player_id").team_abbreviation.last().to_dict()
    assign: dict[int, str] = dict(last_team)
    transfers = []
    for pid, d in designations.items():
        ct = d["claim_team"]
        if ct and ct in team_set and assign.get(pid) not in (None, ct):
            transfers.append({"player_id": pid,
                              "player": id_to_name.get(pid, d["claim_name"]),
                              "from": assign.get(pid), "to": ct})
            assign[pid] = ct
            gaps.add("INFO", "entity-resolution",
                     f"{d['claim_name']} reassigned "
                     f"{last_team.get(pid)} -> {ct} on the authority of a more "
                     "recent injury-report listing (designation_transfer)")

    out: dict = {}
    for team_ab in sorted(team_set):
        tp = p[p.team_abbreviation == team_ab]
        if not len(tp):
            gaps.add("WARN", "player-layer", f"{team_ab}: no season rows")
            out[team_ab] = {"available": [], "out": [], "unknown_roster": True}
            continue
        tgames = sorted(tp.game_id.unique(),
                        key=lambda gid: tp[tp.game_id == gid].game_date.iloc[0])
        recent = set(tgames[-RECENCY_GAMES:])
        seen = set(tp[tp.game_id.isin(recent)].player_id.unique())
        # F2: keep only players still assigned here; add players assigned here
        # by a designation_transfer even with no game for this team yet.
        roster_ids = {pid for pid in seen if assign.get(pid) == team_ab}
        roster_ids |= {t["player_id"] for t in transfers if t["to"] == team_ab}
        avail, outs = [], []
        for pid in sorted(roster_ids):
            # F1: identity history across the whole season, not team-filtered
            hist = (p[(p.player_id == pid) & p.minutes.notna() & (p.minutes > 0)]
                    .sort_values(["game_date", "game_id"]))
            teams_this_season = sorted(set(hist.team_abbreviation))
            rec = {"player": id_to_name.get(pid, str(pid)), "player_id": pid,
                   "games_played": int(len(hist)),
                   "min_ewma": _ewma(hist.minutes),
                   "cold_start": len(hist) == 0,
                   "history_spans_teams": teams_this_season,
                   "transferred_in_season": len(teams_this_season) > 1,
                   "designation": (designations.get(pid) or {}).get("status")}
            (outs if rec["designation"] == "Out" else avail).append(rec)
        for u in unbound:
            if u["abbr"] == team_ab:
                rec = {"player": u["player"], "player_id": None,
                       "games_played": 0, "min_ewma": None, "cold_start": True,
                       "history_spans_teams": [], "transferred_in_season": False,
                       "designation": u["status"], "cold_start_unresolved": True}
                (outs if u["status"] == "Out" else avail).append(rec)
        ew = [a["min_ewma"] for a in avail if a["min_ewma"] is not None]
        out[team_ab] = {
            "availability_data": have_inj, "available": avail, "out": outs,
            "n_roster": len(roster_ids), "n_out": len(outs),
            "sum_min_ewma_available": float(np.nansum(ew)) if ew else None,
            "vacated_min_ewma": float(np.nansum(
                [o["min_ewma"] for o in outs if o["min_ewma"] is not None])),
            "unmatched_injury_rows": [f"{u['player']} ({u['status']})"
                                      for u in unbound if u["abbr"] == team_ab],
            "designation_transfers_in": [t for t in transfers if t["to"] == team_ab],
            "unknown_roster": False,
        }
    return out
