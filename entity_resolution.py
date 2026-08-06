#!/usr/bin/env python3
"""Entity resolution for the prospective capture path (O14 adoption, D022).

Adopts the four user-approved O14 proposals (research node
experiments/player_program/ops_lane/O14_OPS_ENTITY_RESOLUTION, design
fix_entity_resolution.py) into production-shaped code:

  F1  identity-keyed history.  Minutes history for a player is taken from her
      player_id across the whole season, not from a team-filtered frame, so a
      mid-season transfer keeps her prior-team games.
  F2  single tenancy.  A player_id belongs to exactly one team as of the
      cutoff -- the team of her most recent game, unless a MORE RECENT injury
      designation names a different team, in which case the designation wins.
      Every roster entry records its `assignment_source`:
      "last_game" or "designation_transfer".
  F3  designations bind by identity, not by (franchise-name, spelling) pair,
      via a CROSS-SEASON identity index plus an explicit, human-curated alias
      table.  There is deliberately NO fuzzy fallback anywhere in this module
      (O14-F4 negative result: fuzzy matching would have recovered nothing).
  F4  fail-closed.  An Out/Doubtful designation that binds to NO player_id
      raises severity BLOCK, not WARN, and materialises an explicit
      cold-start player object rather than silently vanishing.

Capture-time use (injury_capture_daily.py, props_capture_daily.py):
  try_load_capture_index() -> {normalized name -> player_id}, then
  resolve_player_id(raw_name, index).  The raw capture string is ALWAYS
  retained in the artifact; player_id is an added column.  Resolution failure
  must never kill a capture: try_load_capture_index() degrades to {} with a
  stderr warning instead of raising.

Forecast-time use: player_layer_resolved() is the designed replacement for
the roster/availability construction in daily_forecast.player_layer
(daily_forecast.py:640-760).  daily_forecast.py is NOT modified here; the
exact wiring is specified in ops_adoption_tests/O14/B_HANDOFF.md.

Alias table artifact: data/entity_resolution/alias_table.json,
schema "ops_lane/O14/alias_table/1".  Empty by design as of adoption; every
entry must be a human decision with a reason, and rejected candidates are
recorded explicitly in the artifact.
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent

ALIAS_TABLE_PATH = ROOT / "data" / "entity_resolution" / "alias_table.json"
ALIAS_TABLE_SCHEMA = "ops_lane/O14/alias_table/1"
MASTER_PLAYER = ROOT / "data" / "masters" / "master_player.parquet"

MINUTES_ALPHA = 0.30          # daily_forecast.py:112
RECENCY_GAMES = 3             # daily_forecast.py:120


def _norm_name(s: str) -> str:            # daily_forecast.py:606-609, verbatim
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", s.lower())


class Gaps:
    """Minimal standalone gaps ledger with the same .add(sev, area, msg)
    surface as daily_forecast.Gaps.  Used by tests and by any caller that has
    no forecast run in flight.  Accepts BLOCK (see B_HANDOFF.md for the
    daily_forecast.Gaps taxonomy change, which is C-owned)."""

    def __init__(self):
        self.items: list[tuple[str, str, str]] = []

    def add(self, sev, area, msg):
        self.items.append((sev, area, msg))

    def by_sev(self, sev):
        return [i for i in self.items if i[0] == sev]


# ---------------------------------------------------------------------------
# alias table + identity index (F3)
# ---------------------------------------------------------------------------

def load_alias_table(path=None) -> dict:
    """capture-name (normalized) -> player_id.  Explicit and auditable; there
    is no fuzzy fallback anywhere in this path.  A missing file is an empty
    table; a file with the wrong schema id is an error, never a guess."""
    path = ALIAS_TABLE_PATH if path is None else Path(path)
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    schema = raw.get("schema")
    if schema != ALIAS_TABLE_SCHEMA:
        raise ValueError(f"alias table {path} declares schema {schema!r}; "
                         f"this reader only accepts {ALIAS_TABLE_SCHEMA!r}")
    return {_norm_name(k): int(v) for k, v in raw.get("aliases", {}).items()}


def build_identity_index(p_all, season: int) -> dict:
    """normalized name -> player_id.  Season first (so a name reused across
    eras binds to the current holder), then any earlier season, so a returning
    player is a KNOWN identity rather than an unresolvable string.
    (Port of O14 fix_entity_resolution.build_identity_index, verbatim.)"""
    idx: dict[str, int] = {}
    for sub in (p_all[p_all.season < season], p_all[p_all.season == season]):
        for pid, nm in (sub[["player_id", "player_name"]]
                        .drop_duplicates().itertuples(index=False)):
            idx[_norm_name(nm)] = int(pid)
    return idx


def resolve_player_id(name, name_to_id: dict):
    """Normalized-exact lookup only.  Returns int player_id or None.
    NO fuzzy fallback, by design (O14-F4 negative result)."""
    if name is None:
        return None
    return name_to_id.get(_norm_name(name))


def load_capture_index(master_path=None, alias_path=None, season=None) -> dict:
    """Cross-season identity index + alias overlay, for capture-time
    resolution.  Raises on failure -- see try_load_capture_index for the
    capture-safe wrapper."""
    import pandas as pd
    master_path = MASTER_PLAYER if master_path is None else Path(master_path)
    p_all = pd.read_parquet(master_path,
                            columns=["player_id", "player_name", "season"])
    season = int(p_all.season.max()) if season is None else int(season)
    idx = build_identity_index(p_all, season)
    idx.update(load_alias_table(alias_path))
    return idx


def try_load_capture_index(master_path=None, alias_path=None, season=None) -> dict:
    """Capture-safe wrapper: a capture must NEVER die because resolution is
    unavailable (props cannot be backfilled).  Degrades to {} with an explicit
    stderr warning; the writers then leave player_id blank."""
    try:
        return load_capture_index(master_path, alias_path, season)
    except Exception as e:
        print(f"WARNING: entity-resolution index unavailable "
              f"({type(e).__name__}: {e}); player_id will be left blank",
              file=sys.stderr)
        return {}


# ---------------------------------------------------------------------------
# resolved player layer (F1-F4) -- designed replacement for the roster /
# availability construction in daily_forecast.player_layer (lines 640-760).
# Port of O14 fix_entity_resolution.player_layer_resolved, extended per the
# approved proposal text with `assignment_source` on every roster entry and
# with the output keys daily_forecast's downstream consumers already read
# (n_cold_start, designations_counts, roster_last_game, report_only).
# ---------------------------------------------------------------------------

def _ewma(m):
    if not len(m):
        return None
    return float(m.ewm(alpha=MINUTES_ALPHA, adjust=True).mean().iloc[-1])


def player_layer_resolved(teams: list, p, inj, abbr_to_name: dict, gaps,
                          p_all=None, season=None, alias_path=None) -> dict:
    """teams: team abbreviations on the slate.  p: current-season
    master_player frame (as-of the slate date).  inj: latest designation per
    (team, player) at the cutoff.  p_all: whole master (all seasons) for the
    cross-season identity index; defaults to p.  gaps: any object with
    .add(severity, component, message) accepting BLOCK/WARN/INFO."""
    import numpy as np
    import pandas as pd  # noqa: F401  (callers pass pandas frames)

    p_all = p if p_all is None else p_all
    season = int(p.season.max()) if season is None else season
    name_to_id = build_identity_index(p_all, season)
    name_to_id.update(load_alias_table(alias_path))
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
                                "team": r.team, "abbr": claim_team,
                                "reason": getattr(r, "reason", None)})
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
                                 "claim_name": r.player,
                                 "reason": getattr(r, "reason", None)}

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
    transfer_ids = {t["player_id"] for t in transfers}

    out: dict = {}
    for team_ab in sorted(team_set):
        tp = p[p.team_abbreviation == team_ab]
        if not len(tp):
            gaps.add("WARN", "player-layer", f"{team_ab}: no season rows in "
                     "master_player — roster unknown")
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
            d = designations.get(pid) or {}
            rec = {"player": id_to_name.get(pid, str(pid)), "player_id": pid,
                   "games_played": int(len(hist)),
                   "min_ewma": _ewma(hist.minutes),
                   "last_played": (str(hist.game_date.max().date())
                                   if len(hist) else None),
                   "cold_start": len(hist) == 0,
                   "history_spans_teams": teams_this_season,
                   "transferred_in_season": len(teams_this_season) > 1,
                   "assignment_source": ("designation_transfer"
                                         if pid in transfer_ids
                                         else "last_game"),
                   "designation": d.get("status"),
                   "reason": d.get("reason")}
            (outs if rec["designation"] == "Out" else avail).append(rec)
        # F4: explicit unresolved cold-start objects.  Their placement
        # authority is the designation itself, so assignment_source is
        # designation_transfer; cold_start_unresolved distinguishes them.
        for u in unbound:
            if u["abbr"] == team_ab:
                rec = {"player": u["player"], "player_id": None,
                       "games_played": 0, "min_ewma": None,
                       "last_played": None, "cold_start": True,
                       "history_spans_teams": [], "transferred_in_season": False,
                       "assignment_source": "designation_transfer",
                       "designation": u["status"], "reason": u["reason"],
                       "cold_start_unresolved": True}
                (outs if u["status"] == "Out" else avail).append(rec)
        # bound designations for identities assigned here but OUTSIDE the
        # recency roster: keep the baseline's explicit visibility (repo
        # doctrine: every degradation recorded, none silent).
        report_only = []
        for pid, d in designations.items():
            if assign.get(pid) != team_ab or pid in roster_ids:
                continue
            ph = p[p.player_id == pid]
            last_rostered = (str(ph.game_date.max().date())
                             if len(ph) else None)
            report_only.append({"player": d["claim_name"],
                                "status": d["status"],
                                "in_season_history": bool(len(ph)),
                                "last_rostered": last_rostered})
            if d["status"] == "Out":
                gaps.add("INFO", "player-layer", f"{team_ab}: "
                         f"{d['claim_name']} (Out) is on the injury report "
                         f"but outside the {RECENCY_GAMES}-game recency "
                         f"roster (last rostered {last_rostered}) — long-term "
                         "absentee, already excluded from the availability "
                         "estimate")
            else:
                gaps.add("WARN", "player-layer", f"{team_ab}: "
                         f"{d['claim_name']} ({d['status']}) is outside the "
                         f"{RECENCY_GAMES}-game recency roster (last rostered "
                         f"{last_rostered}) but NOT Out — a possible RETURN "
                         "the recency roster cannot see; the availability "
                         "estimate may understate tonight's rotation")
        ew = [a["min_ewma"] for a in avail if a["min_ewma"] is not None]
        dc: dict = {}
        for a in avail + outs:
            if a["designation"]:
                dc[a["designation"]] = dc.get(a["designation"], 0) + 1
        out[team_ab] = {
            "availability_data": have_inj, "available": avail, "out": outs,
            "n_roster": len(roster_ids), "n_out": len(outs),
            "n_cold_start": sum(1 for a in avail if a["cold_start"]),
            "sum_min_ewma_available": float(np.nansum(ew)) if ew else None,
            "vacated_min_ewma": float(np.nansum(
                [o["min_ewma"] for o in outs if o["min_ewma"] is not None])),
            "designations_counts": dc,
            "report_only": report_only,
            "unmatched_injury_rows": [f"{u['player']} ({u['status']})"
                                      for u in unbound if u["abbr"] == team_ab],
            "designation_transfers_in": [t for t in transfers
                                         if t["to"] == team_ab],
            "roster_last_game": (str(tp[tp.game_id.isin(recent)]
                                     .game_date.max().date())
                                 if len(recent) else None),
            "unknown_roster": False,
        }
    return out
