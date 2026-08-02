#!/usr/bin/env python3
"""cbs_real_frames_v2.py — `cbs_real_frames/2`, source-specific gate accounting.

`cbs_real_frames/1` (frozen under `contract_baseline_suite_v9`) built the first
real causal fold: availability-admitted history, the ported `minutes_twostage`
transforms, the four-channel identity, and row-level source receipts. All of that
is kept here, unchanged in substance. Two defects are repaired.

**IT DOES NOT FIT, PREDICT OR SCORE.** There is no model here, no coefficient, no
accuracy, coverage or error figure, no profitability evaluation, and nothing that
relates a feature to an outcome. It builds frames, counts rows and timestamps,
and hashes what it built.

DEFECT 1 — THE REPORTED SOURCE WAS NOT THE SOURCE CONSUMED
----------------------------------------------------------
Four of the twelve Stage-A player features — `played_last_team_game`,
`played_share_l10_team_games`, `games_missed_streak` and `team_gp_season` — read
the TEAM's admitted game index, not the player's own obligation history. `/1`
nevertheless set `src_asof_gamelog` from the player's own admitted rows alone,
and set `src_asof_roster` to a straight copy of it. Two consequences, both
measured on the real contract (35,615 obligations, seasons 2021-2026):

* rows whose consumed TEAM evidence was strictly NEWER than the maximum the row
  reported — the receipt understated how recent its inputs were;
* rows labelled `no_prior_game_admitted` — "nothing was consulted" — that had in
  fact consumed a team-game index and produced non-default team features from it.

`/2` computes a bound PER SOURCE, from the records that source actually read:

* ``src_asof_gamelog`` — max availability over the admitted PLAYER obligation
  rows consumed. That set is `adm`: every admitted prior obligation, because the
  `prev_dnp_*` carry-forward scans all of them, not only the appearances.
* ``src_asof_team_gamelog`` — max availability over the admitted TEAM games
  consumed. That set is `adm_tg`, all of it, because `team_gp_season` counts the
  whole admitted index.
* ``src_asof_roster`` — a candidate-roster bound derived from the admitted prior
  team games in which this player's candidacy was actually READ. That is a
  trailing window of `adm_tg`, not all of it: `played_last_team_game` reads one
  game, `played_share_l10_team_games` reads `min(k, 10)`, and
  `games_missed_streak` scans back to the first admitted appearance. The window
  is their union, and the bound is the max availability over it. It is derived
  from those records; it is NOT a copy of the gamelog bound.
* ``src_asof_schedule`` — unchanged: noon UTC on the day before the game.

Because availability under the registered `+36h` policy is a monotone function of
`game_date` and `adm_tg` is date-ordered, the roster bound and the team-gamelog
bound COINCIDE NUMERICALLY whenever candidacy read anything. That is stated
rather than hidden: they are still separate sources, derived from different
record sets, carrying independent policy labels, and the roster window is
reported per row (`n_roster_games_consumed`) so the claim is checkable. What is
NOT true, and what `/1` asserted, is that the roster bound equals the PLAYER
gamelog bound.

``feature_asof`` is the MAXIMUM of all four bounds, and every source carries its
own policy label, so `no_prior_game_admitted` is emitted only against a source
that genuinely consumed nothing.

DEFECT 2 — A PREFIX RULE THAT CONTRADICTED ITS OWN TEXT
--------------------------------------------------------
`/1` reproduced `minutes_twostage`'s prefix rule (`DNP*`->CD, `NWT*`->NWT, else
INJ) and disclosed that it maps 82 rows against their own reason text — `DNP -
Injury/Illness` to CD, `DND - Coach's Decision` to INJ. `/1` kept it because it
was registered behaviour. `/2` is a NEW registered feature specification and no
model result has been produced from it, so nothing is invalidated by fixing the
semantics now; freezing them later, after a result exists, would be the moment
the change becomes unavailable.

The taxonomy is an EXPLICIT TABLE (`DNP_CLASS_TABLE`) over the 22 exact
`dnp_reason` strings present in `data/masters/master_player.parquet`, not a regex
that guesses. Anything the table does not contain maps to ``UNKNOWN`` — a real
fourth class, never a silent fall-through to INJ.

Precedence, where the rules could disagree:

1. explicit ``Coach's Decision`` wording -> ``CD``;
2. an ``NWT`` prefix -> ``NWT``;
3. injury / illness / concussion / health-and-safety / reconditioning wording
   -> ``INJ``;
4. everything else -> ``UNKNOWN``.

Rule 2 beats rule 3, so `NWT - Injury/Illness` is NWT, not INJ. `NWT` is a
directly observed roster state — the player was not in uniform — and it is a
different fact from an in-uniform health scratch. The prefix rule agreed on
these rows, and `/2` does not disturb them.

JUDGEMENT CALLS, STATED
-----------------------
* **`DND - Personal` (6 rows) -> UNKNOWN. `NWT - Personal` (58) -> NWT.**
  A personal absence is neither a health event nor a rotation choice. Calling it
  INJ (the prefix rule's answer for `DND - Personal`) manufactures a health
  signal from a row that carries none, and calling it CD manufactures a
  performance signal. UNKNOWN is the honest bucket, and the explicit-unknown
  class exists exactly so this row does not have to be guessed. `NWT - Personal`
  is different only because the NWT prefix is itself the observation: the player
  was not with the team. "Personal" is the sub-reason, not a contradiction of it.
* **`NWT - League Suspension` (5) and `NWT_TEAM_SUSPENSION` (1) -> NWT.**
  A suspension is a disciplinary status, not a health event and not a coach's
  in-game rotation decision. Both strings carry the NWT prefix and both describe
  a player who was not with the team, which is what NWT means. The prefix rule
  also said NWT; this is a coincidence of agreement, not inheritance.
* **`DND - Rest` (15) -> CD, `DNP - Rest` (2) -> CD, `NWT - Rest` (10) -> NWT.**
  Rest is load management: a discretionary decision by the team to hold a HEALTHY
  player. That is what CD means, and it is emphatically not an injury — the
  prefix rule's INJ for `DND - Rest` is the same fabrication as for `DND -
  Personal`. `NWT - Rest` goes to NWT under rule 2 for the same reason as the
  suspensions: not being with the team is the stronger, directly observed fact,
  and it is the class the feature `prev_dnp_nwt` was built to carry.
* **`DND_INELIGIBLE_TO_PLAY` (1) -> UNKNOWN.** Ineligibility is an
  administrative status — paperwork, contract, league registration. It has no
  health content and no rotation content. The prefix rule called it INJ.
* **The SCREAMING_SNAKE variants and the no-space `DND-Return to Competition
  Reconditioning` are keys in the table**, so they are classed by their meaning
  rather than by whether somebody's scraper inserted a space.

**No parity with `/1` is claimed.** `dnp_taxonomy_diff()` reports, from the real
master, the exact number of rows whose class changes, per (old, new) pair. The
prefix rule is kept importable as `legacy_prefix_dnp_class` FOR THAT AUDIT ONLY;
no feature in this module is derived from it.

A fourth class has one consequence worth naming: an `UNKNOWN` prior DNP is the
most recent DNP, so it stops the carry-forward scan, but it sets none of
`prev_dnp_cd/inj/nwt`. Those three would then be indistinguishable from "this
player has no prior DNP at all". They are not left indistinguishable: the frame
carries a diagnostic `prev_dnp_unknown` column. It is NOT added to
`P_ACTIVE_FEATURES`, which stays frozen at twelve; it exists so the ambiguity is
visible rather than silent. `returning_flag` keeps its registered conjunction
(`INJ` or `NWT` only), so an UNKNOWN prior DNP does not set it.

EVERYTHING ELSE IS `/1`, DELIBERATELY
-------------------------------------
The availability-admitted history rule, the `+36h` policy, the 0.30 EWMA alpha,
the 45-day and 20-game caps, the `min(k, 10)` denominator, playoffs kept,
`appeared` taken from the contract, the contract's `team_id` winning over the
master's, the `is_home` -> side mapping, and the four-channel identity check are
all carried forward from `cbs_real_frames/1` unchanged. Their rationale is in
that module's docstring and is not repeated here.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

import cbs_provenance as _prov_v2
import cbs_provenance_v3 as prov   # reconciled at fan-in: the v3 contract is the
                                   # registered row universe for v10, so the
                                   # adapter must read v3, not the superseded v2
from cbs_frame_identity import frames_digest
from cbs_generator import DAYS_CAP, MISS_CAP, P_ACTIVE_FEATURES
from cbs_real_frames import dnp_class as legacy_prefix_dnp_class
from cbs_v5 import REQUIRED_CHANNELS
from cbs_v7 import (OUTCOME_AVAILABILITY_POLICY_ID,
                    OUTCOME_AVAILABILITY_POLICY_LAG_HOURS)
from cbs_v9 import REQUIRED_PLAYER_FEATURE_SOURCES, REQUIRED_TEAM_FEATURE_SOURCES

ADAPTER_ID = "cbs_real_frames/2"
FOLD_RECEIPT_SCHEMA = "cbs_real_fold_receipt/2"
DNP_TAXONOMY_ID = "cbs_dnp_taxonomy/1"

REPO_ROOT = Path(__file__).resolve().parent

#: frozen in minutes_twostage.py:83, from `minutes_ewma_vs_carryforward_v1`
EWMA_ALPHA = 0.30
#: share of the last N ADMITTED appearances that were starts
START_SHARE_WINDOW = 5
#: denominator cap for played_share_l10_team_games
TEAM_WINDOW = 10

#: The schedule is knowable well before the game. Frozen bound: noon UTC on the
#: day BEFORE the game. Strictly earlier than both registered cutoff policies —
#: 18:00Z the prior day, and tip minus 90 minutes — and asserted to be so.
SCHEDULE_BOUND_HOURS_BEFORE_GAME_DAY = 12.0

#: The player frame now REPORTS the team index it consumes, so the receipt's
#: source list is a strict superset of what v8/v9 require.
PLAYER_FRAME_SOURCES = tuple(REQUIRED_PLAYER_FEATURE_SOURCES) + \
    ("src_asof_team_gamelog",)
TEAM_FRAME_SOURCES = tuple(REQUIRED_TEAM_FEATURE_SOURCES)

#: The composite: the maximum over every source the row actually consumed.
FEATURE_ASOF_COL = "feature_asof"

SOURCE_POLICIES = {
    "prior_player_game_availability": (
        "max outcome-availability over the ADMITTED PRIOR OBLIGATION ROWS of this "
        "player-season that the row actually read, under the registered +36h "
        "policy; the whole admitted set, because the prev_dnp carry-forward scans "
        "all of it and not only the appearances"),
    "prior_team_game_availability": (
        "max outcome-availability over the ADMITTED PRIOR TEAM GAMES of this "
        "team-season that the row actually read; the whole admitted index, "
        "because team_gp_season counts all of it"),
    "admitted_team_game_candidacy": (
        "max outcome-availability over the trailing window of admitted prior team "
        "games in which this player's candidacy was actually read: the union of "
        "the last-game lookup, the min(k,10) share window, and the missed-streak "
        "scan-back. Derived from those records, not copied from the gamelog bound"),
    "no_prior_game_admitted": (
        "THIS SOURCE consumed nothing at this cutoff: no record of this kind was "
        "readable, so nothing of this kind was consulted and this source's bound "
        "falls back to the schedule bound. Emitted per source, never as a claim "
        "about the row as a whole"),
    "schedule_day_before_noon_utc": (
        "noon UTC on the day before the game; the schedule is a pregame fact"),
}

NO_EVIDENCE_POLICY = "no_prior_game_admitted"


# --------------------------------------------------------------------------
# the frozen DNP taxonomy
# --------------------------------------------------------------------------

DNP_CLASSES = ("CD", "INJ", "NWT", "UNKNOWN")

#: The 22 exact `dnp_reason` strings present in
#: `data/masters/master_player.parquet`, each frozen to a class BY MEANING.
#: An explicit table, not a regex: the taxonomy is auditable line by line and a
#: new string cannot be absorbed by an accident of prefix matching.
DNP_CLASS_TABLE: dict[str, str] = {
    # --- explicit coach's-decision wording -> CD ---------------------------
    "DNP - Coach's Decision": "CD",
    "DND - Coach's Decision": "CD",          # prefix rule said INJ
    # --- rest is load management on a HEALTHY player -> CD -----------------
    "DNP - Rest": "CD",
    "DND - Rest": "CD",                      # prefix rule said INJ
    # --- NWT prefix: not with the team, whatever the sub-reason -> NWT -----
    "NWT - Injury/Illness": "NWT",
    "NWT - Not With Team": "NWT",
    "NWT - Personal": "NWT",
    "NWT - Health and Safety Protocols": "NWT",
    "NWT - Rest": "NWT",
    "NWT - League Suspension": "NWT",
    "NWT_CONCUSSION_PROTOCOL": "NWT",
    "NWT_TEAM_SUSPENSION": "NWT",
    # --- injury / illness / concussion / H&S / reconditioning -> INJ -------
    "DND - Injury/Illness": "INJ",
    "DNP - Injury/Illness": "INJ",           # prefix rule said CD
    "DND - Concussion Protocol": "INJ",
    "DNP - Concussion Protocol": "INJ",      # prefix rule said CD
    "DND - Health and Safety Protocols": "INJ",
    "DND_HEALTH_AND_SAFETY_PROTOCOLS": "INJ",
    "DND-Return to Competition Reconditioning": "INJ",
    # --- neither health nor rotation: refuse to guess -> UNKNOWN -----------
    "DND - Personal": "UNKNOWN",             # prefix rule said INJ
    "DNP - Personal": "UNKNOWN",             # prefix rule said CD
    "DND_INELIGIBLE_TO_PLAY": "UNKNOWN",     # prefix rule said INJ
}


class RealFrameError(RuntimeError):
    """The real inputs cannot be assembled into a causal fold."""


def dnp_class(v) -> str | None:
    """Frozen semantic taxonomy. Table lookup, with EXPLICIT unknown handling.

    Returns ``None`` for a row that carries no reason at all (the player was not
    a DNP), one of ``CD`` / ``INJ`` / ``NWT`` for a string in the frozen table,
    and ``UNKNOWN`` for any other non-empty string. Nothing falls through to INJ.
    """
    if not isinstance(v, str) or not v.strip():
        return None
    if v in DNP_CLASS_TABLE:
        return DNP_CLASS_TABLE[v]
    return DNP_CLASS_TABLE.get(v.strip(), "UNKNOWN")


def dnp_taxonomy_diff(root: Path | str = REPO_ROOT) -> dict:
    """Count, from the real master, the rows this taxonomy RECLASSIFIES.

    Row counting only. No parity is claimed with the prefix rule and none is
    asserted; the point of this function is to state the size of the disagreement
    exactly rather than to minimise it.
    """
    mp = pd.read_parquet(Path(root) / _prov_v2.MASTER_PLAYER, columns=["dnp_reason"])
    s = mp["dnp_reason"]
    s = s[s.notna() & s.astype(str).str.strip().ne("")]
    old = s.map(legacy_prefix_dnp_class)
    new = s.map(dnp_class)
    pairs: dict[str, int] = {}
    for o, n in zip(old, new):
        if o != n:
            pairs[f"{o}->{n}"] = pairs.get(f"{o}->{n}", 0) + 1
    per_reason = {}
    for reason, cnt in s.value_counts().items():
        o, n = legacy_prefix_dnp_class(reason), dnp_class(reason)
        per_reason[reason] = {"rows": int(cnt), "prefix_rule": o, "semantic": n,
                              "changed": o != n}
    return {
        "taxonomy": DNP_TAXONOMY_ID,
        "n_dnp_rows": int(len(s)),
        "n_distinct_reasons": int(s.nunique()),
        "n_reasons_not_in_table": int(sum(1 for r in s.unique()
                                          if r not in DNP_CLASS_TABLE)),
        "class_counts_prefix_rule": {k: int(v) for k, v in
                                     old.value_counts().items()},
        "class_counts_semantic": {k: int(v) for k, v in new.value_counts().items()},
        "n_rows_changed": int((old != new).sum()),
        "changes_by_pair": dict(sorted(pairs.items())),
        "per_reason": per_reason,
    }


# --------------------------------------------------------------------------
# loading, with attestation enforced first
# --------------------------------------------------------------------------

def load_inputs(root: Path | str = REPO_ROOT, *, require_attested: bool = True):
    """Read the contract and masters, refusing unattested inputs.

    Unchanged from `/1`: the attestation check runs before a single byte is
    turned into a feature.
    """
    root = Path(root)
    if require_attested:
        audit = prov.audit(root)
        if audit["hard_blockers"]:
            raise RealFrameError(
                "refusing to build frames; provenance preconditions are not met: "
                + "; ".join(f"{b['artifact']}: {b['detail']}"
                            for b in audit["hard_blockers"]))
    pg = pd.read_parquet(root / prov.PLAYER_GAME_V3)
    tg = pd.read_parquet(root / prov.TEAM_GAME_V3)
    mp = pd.read_parquet(root / _prov_v2.MASTER_PLAYER)
    mt = pd.read_parquet(root / _prov_v2.MASTER_TEAM)
    for f in (mp, mt):
        f["game_date"] = pd.to_datetime(f["game_date"], format="%Y-%m-%d")
    for f in (pg, tg):
        f["game_date"] = pd.to_datetime(f["game_date"])
    return pg, tg, mp, mt


def availability_of(game_date: pd.Series) -> pd.Series:
    """The registered +36h conservative policy bound. Policy, never observed."""
    return (pd.to_datetime(game_date, utc=True).dt.floor("D")
            + pd.Timedelta(hours=OUTCOME_AVAILABILITY_POLICY_LAG_HOURS))


def schedule_bound(game_date: pd.Series) -> pd.Series:
    """Noon UTC the day before the game."""
    return (pd.to_datetime(game_date, utc=True).dt.floor("D")
            - pd.Timedelta(days=1)
            + pd.Timedelta(hours=SCHEDULE_BOUND_HOURS_BEFORE_GAME_DAY))


def roster_window_length(own: list[bool]) -> int:
    """How many trailing admitted team games the CANDIDACY features actually read.

    `own[j]` is "this player appeared in admitted prior team game j", oldest
    first. Three features read it and each reads a different amount:

    * `played_last_team_game` -> the last 1;
    * `played_share_l10_team_games` -> the last `min(k, 10)`;
    * `games_missed_streak` -> scans backwards until the first appearance, so it
      touches `streak + 1` games, or all `k` if the player never appeared.

    The window is their union. Returns 0 for an empty admitted index, in which
    case no candidacy evidence was read at all.
    """
    k = len(own)
    if not k:
        return 0
    w = max(1, min(k, TEAM_WINDOW))
    streak = 0
    for a in reversed(own):
        streak += 1
        if a:
            break
    return min(k, max(w, streak))


# --------------------------------------------------------------------------
# the causal player frame
# --------------------------------------------------------------------------

def build_player_frame(season: int, root: Path | str = REPO_ROOT, *,
                       require_attested: bool = True) -> dict:
    """Assemble the causal player fold for `season:<season>`.

    Returns train / test / universe frames plus receipts. Nothing is fitted and
    nothing is predicted; the frames are built, counted and hashed.
    """
    root = Path(root)
    pg, tg, mp, mt = load_inputs(root, require_attested=require_attested)

    pg = pg[pg["season"] <= season].copy()
    if not len(pg):
        raise RealFrameError(f"no contract rows at or before season {season}")

    # ---- join for the two master-only columns ---------------------------
    m = mp[["game_id", "player_id", "starter_flag", "dnp_reason"]].copy()
    m["player_id"] = m["player_id"].astype("int64")
    pg["player_id"] = pg["player_id"].astype("int64")
    before = len(pg)
    pg = pg.merge(m, on=["game_id", "player_id"], how="left", validate="1:1")
    join = {"left_rows": int(before), "matched": int(pg["starter_flag"].notna().sum()),
            "unmatched": int(pg["starter_flag"].isna().sum())}
    unmatched_appeared = int(pg.loc[pg["starter_flag"].isna(), "appeared"].sum())
    join["unmatched_that_appeared"] = unmatched_appeared
    if unmatched_appeared:
        raise RealFrameError(
            f"{unmatched_appeared} contract rows report appeared=True but have no "
            f"master box row; the join is not trustworthy")

    pg["dnp_class"] = pg["dnp_reason"].map(dnp_class)
    pg["starter_flag"] = pd.to_numeric(pg["starter_flag"], errors="coerce").fillna(0.0)
    pg["appeared"] = pg["appeared"].astype(bool)
    pg = pg.rename(columns={"pts": "points"})
    pg["minutes"] = pd.to_numeric(pg["minutes"], errors="coerce")
    pg["points"] = pd.to_numeric(pg["points"], errors="coerce")
    pg["fga"] = pd.to_numeric(pg["fga"], errors="coerce")

    # ---- team game index, availability-gated ------------------------------
    mt2 = mt[mt["season"] <= season].copy()
    mt2 = mt2.sort_values(["team_id", "season", "game_date", "game_id"],
                          kind="mergesort")
    mt2["team_avail"] = availability_of(mt2["game_date"])
    appeared_by_game = (pg.loc[pg["appeared"], ["game_id", "player_id"]]
                        .groupby("game_id")["player_id"].apply(set).to_dict())

    team_games: dict[tuple, list] = {}
    for tid, s, gd, gid, av in zip(mt2["team_id"], mt2["season"], mt2["game_date"],
                                   mt2["game_id"], mt2["team_avail"]):
        team_games.setdefault((int(tid), int(s)), []).append((gd, gid, av))

    # ---- per-row causal derivation ---------------------------------------
    pg["cutoff"] = pd.to_datetime(pg["forecast_cutoff"], utc=True)
    pg["avail"] = availability_of(pg["game_date"])
    pg = pg.sort_values(["player_id", "season", "forecast_cutoff", "game_id"],
                        kind="mergesort").reset_index(drop=True)

    n = len(pg)
    feats = {c: np.zeros(n, dtype=float) for c in P_ACTIVE_FEATURES}
    feats["days_since_last_appearance"][:] = DAYS_CAP
    prev_unknown = np.zeros(n, dtype=float)

    # --- SOURCE-SPECIFIC bounds, one per source, from the records consumed --
    src_gamelog = np.empty(n, dtype=object)
    src_team = np.empty(n, dtype=object)
    src_roster = np.empty(n, dtype=object)
    pol_gamelog = np.empty(n, dtype=object)
    pol_team = np.empty(n, dtype=object)
    pol_roster = np.empty(n, dtype=object)
    n_player_rows = np.zeros(n, dtype=np.int64)
    n_team_games = np.zeros(n, dtype=np.int64)
    n_roster_games = np.zeros(n, dtype=np.int64)

    hist: dict[tuple, list] = {}
    for i in range(n):
        pid = int(pg.at[i, "player_id"])
        s = int(pg.at[i, "season"])
        cut = pg.at[i, "cutoff"]
        key = (pid, s)
        prior = hist.setdefault(key, [])
        # ADMITTED = outcome availability strictly before this row's cutoff
        adm = [h for h in prior if h["avail"] < cut]
        played = [h for h in adm if h["appeared"]]

        if played:
            mins = np.asarray([h["minutes"] for h in played], dtype=float)
            w = (1.0 - EWMA_ALPHA) ** np.arange(len(mins) - 1, -1, -1)
            feats["min_ewma"][i] = float(np.sum(w * mins) / np.sum(w))
            feats["started_last"][i] = float(played[-1]["starter"])
            tail = played[-START_SHARE_WINDOW:]
            feats["start_share_l5"][i] = float(
                np.mean([h["starter"] for h in tail]))
            gap = (pg.at[i, "game_date"] - played[-1]["date"]).days
            feats["days_since_last_appearance"][i] = float(min(gap, DAYS_CAP))

        # prev_dnp_* : the ffilled class of the most recent ADMITTED dnp row.
        # The `isinstance(..., str)` test is load-bearing: a non-DNP row's class
        # arrives from pandas as NaN, and `if NaN:` is TRUE, so a truthiness test
        # stops the scan at the first non-DNP row and reports "no prior DNP" for a
        # player who has one.
        cls = None
        for h in reversed(adm):
            if isinstance(h["dnp_class"], str) and h["dnp_class"]:
                cls = h["dnp_class"]
                break
        feats["prev_dnp_cd"][i] = float(cls == "CD")
        feats["prev_dnp_inj"][i] = float(cls == "INJ")
        feats["prev_dnp_nwt"][i] = float(cls == "NWT")
        prev_unknown[i] = float(cls == "UNKNOWN")

        # team-index features over ADMITTED team games
        tkey = (int(pg.at[i, "team_id"]), s)
        tg_all = team_games.get(tkey, [])
        adm_tg = [g for g in tg_all if g[2] < cut]
        k = len(adm_tg)
        feats["team_gp_season"][i] = float(k)
        own: list[bool] = []
        if k:
            own = [pid in appeared_by_game.get(g[1], ()) for g in adm_tg]
            feats["played_last_team_game"][i] = float(own[-1])
            nw = min(k, TEAM_WINDOW)
            feats["played_share_l10_team_games"][i] = float(sum(own[-nw:])) / nw
            ms = 0
            for a in reversed(own):
                if a:
                    break
                ms += 1
            feats["games_missed_streak"][i] = float(min(ms, MISS_CAP))
        else:
            feats["games_missed_streak"][i] = 0.0

        feats["returning_flag"][i] = float(
            feats["played_last_team_game"][i] == 0 and cls in ("INJ", "NWT"))

        # ---- per-source bounds, from the records this row actually read ----
        n_player_rows[i] = len(adm)
        if adm:
            src_gamelog[i] = max(h["avail"] for h in adm)
            pol_gamelog[i] = "prior_player_game_availability"
        else:
            src_gamelog[i] = None
            pol_gamelog[i] = NO_EVIDENCE_POLICY

        n_team_games[i] = k
        if k:
            src_team[i] = max(g[2] for g in adm_tg)
            pol_team[i] = "prior_team_game_availability"
        else:
            src_team[i] = None
            pol_team[i] = NO_EVIDENCE_POLICY

        rw = roster_window_length(own)
        n_roster_games[i] = rw
        if rw:
            src_roster[i] = max(g[2] for g in adm_tg[k - rw:])
            pol_roster[i] = "admitted_team_game_candidacy"
        else:
            src_roster[i] = None
            pol_roster[i] = NO_EVIDENCE_POLICY

        prior.append({"avail": pg.at[i, "avail"], "appeared": bool(pg.at[i, "appeared"]),
                      "minutes": float(pg.at[i, "minutes"])
                      if pd.notna(pg.at[i, "minutes"]) else 0.0,
                      "starter": float(pg.at[i, "starter_flag"]),
                      "date": pg.at[i, "game_date"],
                      "dnp_class": (pg.at[i, "dnp_class"]
                                    if isinstance(pg.at[i, "dnp_class"], str)
                                    else None)})

    for c, v in feats.items():
        if c not in ("p_plays_prior", "player_gp_season"):   # runner-derived
            pg[c] = v
    #: diagnostic only; NOT a member of the frozen twelve
    pg["prev_dnp_unknown"] = prev_unknown

    # ---- row-level source timestamps -------------------------------------
    sched = schedule_bound(pg["game_date"])
    if (sched >= pg["cutoff"]).any():
        raise RealFrameError(
            f"{int((sched >= pg['cutoff']).sum())} rows have a schedule bound at or "
            f"after their own cutoff; the frozen schedule policy does not hold")

    def _bound(arr) -> pd.Series:
        """A source's bound, falling back to the schedule bound when it read
        nothing. The fallback keeps the column total and the composite defined;
        the POLICY column, not the timestamp, is what records emptiness."""
        return pd.to_datetime(pd.Series(list(arr), index=pg.index),
                              utc=True).fillna(sched)

    b_gl = _bound(src_gamelog)
    b_tm = _bound(src_team)
    b_rs = _bound(src_roster)
    composite = pd.concat([b_gl, b_tm, b_rs, sched], axis=1).max(axis=1)

    pg["src_asof_gamelog"] = b_gl.map(lambda t: t.isoformat())
    pg["src_asof_team_gamelog"] = b_tm.map(lambda t: t.isoformat())
    pg["src_asof_roster"] = b_rs.map(lambda t: t.isoformat())
    pg["src_asof_schedule"] = sched.map(lambda t: t.isoformat())
    pg[FEATURE_ASOF_COL] = composite.map(lambda t: t.isoformat())
    pg["src_policy_gamelog"] = pol_gamelog
    pg["src_policy_team_gamelog"] = pol_team
    pg["src_policy_roster"] = pol_roster
    pg["src_policy_schedule"] = "schedule_day_before_noon_utc"
    pg["n_src_player_rows_consumed"] = n_player_rows
    pg["n_src_team_games_consumed"] = n_team_games
    pg["n_roster_games_consumed"] = n_roster_games
    pg["outcome_availability_source"] = "policy"
    pg["outcome_availability_policy_id"] = OUTCOME_AVAILABILITY_POLICY_ID

    # every source, not just the gamelog, must be strictly before the cutoff
    for col in ("src_asof_gamelog", "src_asof_team_gamelog", "src_asof_roster",
                "src_asof_schedule", FEATURE_ASOF_COL):
        late = int((pd.to_datetime(pg[col], utc=True) >= pg["cutoff"]).sum())
        if late:
            raise RealFrameError(
                f"{late} rows report {col} at or after their own cutoff")
    # the composite must dominate every component it is built from
    for col in ("src_asof_gamelog", "src_asof_team_gamelog", "src_asof_roster",
                "src_asof_schedule"):
        under = int((pd.to_datetime(pg[col], utc=True) > composite).sum())
        if under:
            raise RealFrameError(
                f"{under} rows report {col} newer than the composite "
                f"{FEATURE_ASOF_COL}; the composite is not a maximum")

    keep = ["row_uid", "player_id", "team_id", "season", "game_id", "game_date",
            "forecast_cutoff", "appeared", "minutes", "points", "fga",
            "fold_id"] + [c for c in P_ACTIVE_FEATURES
                          if c not in ("p_plays_prior", "player_gp_season")] + [
        "prev_dnp_unknown",
        "src_asof_gamelog", "src_asof_team_gamelog", "src_asof_roster",
        "src_asof_schedule", FEATURE_ASOF_COL,
        "src_policy_gamelog", "src_policy_team_gamelog", "src_policy_roster",
        "src_policy_schedule", "n_src_player_rows_consumed",
        "n_src_team_games_consumed", "n_roster_games_consumed",
        "outcome_availability_source", "outcome_availability_policy_id"]
    frame = pg[keep].copy()
    frame["minutes"] = frame["minutes"].fillna(0.0)
    frame["points"] = frame["points"].fillna(0.0)
    frame["fga"] = frame["fga"].fillna(0.0)

    train = frame[frame["season"] < season].reset_index(drop=True)
    test = frame[frame["season"] == season].reset_index(drop=True)

    uni_cols = ["row_uid", "fold_id", "forecast_cutoff"]
    universe = pg.loc[pg["season"] == season, uni_cols + ["appeared"]].copy()
    universe = universe.reset_index(drop=True)
    for t in ("p_active", "e_minutes_given_active", "attempts_usage",
              "player_scoring_distribution"):
        universe[f"prediction_required__{t}"] = True
        universe[f"outcome_scoreable__{t}"] = (
            universe["appeared"].astype(bool) if t != "p_active" else True)

    return {
        "kind": "player", "season": season,
        "train": train, "test": test, "universe": universe,
        "receipts": _receipts("player", season, train, test, universe, join, pg,
                              PLAYER_FRAME_SOURCES),
    }


# --------------------------------------------------------------------------
# the causal team frame
# --------------------------------------------------------------------------

def build_team_frame(season: int, root: Path | str = REPO_ROOT, *,
                     require_attested: bool = True,
                     withhold_current_outcomes: bool = False) -> dict:
    """Assemble the causal team fold. `withhold_current_outcomes` drops every
    outcome column from the test frame, exercising the outcome-free interface.

    Carried from `/1` with one addition: the composite `feature_asof`, so both
    sides of a fold report a bound of the same name and the same meaning.
    """
    root = Path(root)
    _pg, tg, _mp, mt = load_inputs(root, require_attested=require_attested)

    tg = tg[tg["season"] <= season].copy()
    m = mt[["game_id", "team_id", "is_home", "pts", "ftm", "fgm", "fg3m",
            "points_paint"]].copy()
    for f in (tg, m):
        f["team_id"] = f["team_id"].astype("int64")
    before = len(tg)
    tg = tg.merge(m, on=["game_id", "team_id"], how="left", validate="1:1")
    join = {"left_rows": int(before), "matched": int(tg["pts"].notna().sum()),
            "unmatched": int(tg["pts"].isna().sum())}
    if join["unmatched"]:
        raise RealFrameError(
            f"{join['unmatched']} team-game obligations have no master box row")

    # the four registered channel expressions, confirmed against
    # build_channel_base_v2.py and re-validated by build_masters.v2_channel_identity
    tg["ch_ft"] = tg["ftm"].astype(float)
    tg["ch_3pt"] = 3.0 * tg["fg3m"].astype(float)
    tg["ch_paint"] = tg["points_paint"].astype(float)
    tg["ch_np2"] = 2.0 * (tg["fgm"].astype(float) - tg["fg3m"].astype(float)) \
        - tg["points_paint"].astype(float)
    tg["team_points"] = tg["pts"].astype(float)
    if (tg["ch_np2"] < 0).any():
        raise RealFrameError(
            f"{int((tg['ch_np2'] < 0).sum())} rows have a negative non-paint-2 "
            f"channel; the box-score identity does not hold")
    identity_gap = (tg["ch_ft"] + tg["ch_3pt"] + tg["ch_paint"] + tg["ch_np2"]
                    - tg["team_points"]).abs().max()
    if identity_gap > 1e-9:
        raise RealFrameError(
            f"channel identity violated by up to {identity_gap}; the four channels "
            f"must reconstruct team_points exactly")

    # adapter decision carried from /1: no is_home -> side mapping existed
    tg["side"] = np.where(tg["is_home"].astype(int) == 1, "home", "away")

    tg["cutoff"] = pd.to_datetime(tg["forecast_cutoff"], utc=True)
    tg["avail"] = availability_of(tg["game_date"])
    tg = tg.sort_values(["team_id", "game_date", "game_id"],
                        kind="mergesort").reset_index(drop=True)

    src = np.empty(len(tg), dtype=object)
    pol = np.empty(len(tg), dtype=object)
    ncons = np.zeros(len(tg), dtype=np.int64)
    hist: dict[tuple, list] = {}
    for i in range(len(tg)):
        key = (int(tg.at[i, "team_id"]), int(tg.at[i, "season"]))
        prior = hist.setdefault(key, [])
        adm = [a for a in prior if a < tg.at[i, "cutoff"]]
        ncons[i] = len(adm)
        if adm:
            src[i], pol[i] = max(adm), "prior_team_game_availability"
        else:
            src[i], pol[i] = None, NO_EVIDENCE_POLICY
        prior.append(tg.at[i, "avail"])

    sched = schedule_bound(tg["game_date"])
    if (sched >= tg["cutoff"]).any():
        raise RealFrameError("schedule bound is not strictly before every cutoff")
    gl = pd.to_datetime(pd.Series(list(src), index=tg.index), utc=True).fillna(sched)
    composite = pd.concat([gl, sched], axis=1).max(axis=1)
    tg["src_asof_team_gamelog"] = gl.map(lambda t: t.isoformat())
    tg["src_asof_schedule"] = sched.map(lambda t: t.isoformat())
    tg[FEATURE_ASOF_COL] = composite.map(lambda t: t.isoformat())
    tg["src_policy_team_gamelog"] = pol
    tg["src_policy_schedule"] = "schedule_day_before_noon_utc"
    tg["n_src_team_games_consumed"] = ncons
    tg["outcome_availability_source"] = "policy"
    tg["outcome_availability_policy_id"] = OUTCOME_AVAILABILITY_POLICY_ID

    outcome_cols = [f"ch_{c}" for c in REQUIRED_CHANNELS] + ["team_points"]
    keep = ["row_uid", "team_id", "game_id", "season", "game_date",
            "forecast_cutoff", "side", "fold_id"] + outcome_cols + [
        "src_asof_team_gamelog", "src_asof_schedule", FEATURE_ASOF_COL,
        "src_policy_team_gamelog", "src_policy_schedule",
        "n_src_team_games_consumed", "outcome_availability_source",
        "outcome_availability_policy_id"]
    frame = tg[keep].copy()

    train = frame[frame["season"] < season].reset_index(drop=True)
    test = frame[frame["season"] == season].reset_index(drop=True)
    if withhold_current_outcomes:
        test = test.drop(columns=outcome_cols)

    universe = tg.loc[tg["season"] == season,
                      ["row_uid", "fold_id", "forecast_cutoff"]].reset_index(drop=True)
    universe["prediction_required__team_game_distribution"] = True
    universe["outcome_scoreable__team_game_distribution"] = True

    return {
        "kind": "team", "season": season,
        "train": train, "test": test, "universe": universe,
        "receipts": _receipts("team", season, train, test, universe, join, tg,
                              TEAM_FRAME_SOURCES),
    }


# --------------------------------------------------------------------------
# receipts
# --------------------------------------------------------------------------

def _receipts(kind, season, train, test, universe, join, full, sources) -> dict:
    """Schema, join, row-count, timestamp, provenance and identity. No model claim.

    The timestamp block is now computed over EVERY source the frame reports, and
    additionally reports, per source, how many rows are newer than the composite
    (which must be zero by construction) and how many consumed nothing.
    """
    cut = pd.to_datetime(test["forecast_cutoff"], utc=True)
    ts = test[list(sources)].apply(pd.to_datetime, utc=True)
    asof = ts.max(axis=1)
    if FEATURE_ASOF_COL in test.columns:
        composite = pd.to_datetime(test[FEATURE_ASOF_COL], utc=True)
    else:                                          # pragma: no cover - defensive
        composite = asof
    lead = (cut - composite)
    pol_cols = [c for c in full.columns if c.startswith("src_policy_")]
    policy_counts = {c: full[c].value_counts().to_dict() for c in pol_cols}
    src_cols = [c for c in full.columns if c.startswith("src_asof_")]
    per_source = {}
    for c in src_cols:
        v = pd.to_datetime(full[c], utc=True)
        comp = pd.to_datetime(full[FEATURE_ASOF_COL], utc=True) \
            if FEATURE_ASOF_COL in full.columns else v
        fcut = pd.to_datetime(full["forecast_cutoff"], utc=True)
        per_source[c] = {
            "n_newer_than_composite": int((v > comp).sum()),
            "n_at_cutoff": int((v == fcut).sum()),
            "n_after_cutoff": int((v > fcut).sum()),
        }
    return {
        "schema": FOLD_RECEIPT_SCHEMA, "adapter": ADAPTER_ID, "kind": kind,
        "fold_id": f"season:{season}",
        "row_counts": {"train": int(len(train)), "test": int(len(test)),
                       "universe": int(len(universe)),
                       "train_seasons": sorted(int(s) for s in
                                               pd.unique(train["season"]))
                       if len(train) else []},
        "join": join,
        "schema_check": {
            "test_columns": sorted(map(str, test.columns)),
            "sources_present": [c for c in sources if c in test.columns],
            "sources_missing": [c for c in sources if c not in test.columns],
        },
        "timestamps": {
            "sources": list(sources),
            "composite_column": FEATURE_ASOF_COL,
            "n_at_cutoff": int((composite == cut).sum()),
            "n_after_cutoff": int((composite > cut).sum()),
            "n_composite_below_a_source": int((asof > composite).sum()),
            "per_source": per_source,
            "min_lead_seconds": float(lead.min().total_seconds()) if len(test) else None,
            "max_lead_seconds": float(lead.max().total_seconds()) if len(test) else None,
        },
        "provenance": {
            "outcome_availability_source": "policy",
            "outcome_availability_policy_id": OUTCOME_AVAILABILITY_POLICY_ID,
            "any_observed_source": False,
            "row_level_policies": policy_counts,
            "policy_definitions": SOURCE_POLICIES,
            "dnp_taxonomy": DNP_TAXONOMY_ID,
        },
        "identity": frames_digest({"train": train, "test": test,
                                   "universe": universe}),
    }


def build_fold(season: int, root: Path | str = REPO_ROOT, **kw) -> dict:
    """Both sides of one season fold, with a combined receipt."""
    p = build_player_frame(season, root, **kw)
    t = build_team_frame(season, root, **{k: v for k, v in kw.items()
                                          if k != "withhold_current_outcomes"})
    return {"season": season, "player": p, "team": t,
            "receipts": {"player": p["receipts"], "team": t["receipts"]}}


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="cbs_real_frames/2 frame builder")
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--root", default=str(REPO_ROOT))
    ap.add_argument("--out", default=None)
    ap.add_argument("--dnp-diff", action="store_true",
                    help="also report the DNP reclassification counts")
    args = ap.parse_args()
    fold = build_fold(args.season, args.root)
    rep = {"schema": FOLD_RECEIPT_SCHEMA, "adapter": ADAPTER_ID,
           "generated_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
           "scope": ("frame construction, schema, join, timestamp, provenance and "
                     "identity only: nothing fitted, nothing predicted, no model "
                     "coverage or accuracy, no scoring, no profitability"),
           "receipts": fold["receipts"]}
    if args.dnp_diff:
        rep["dnp_taxonomy_diff"] = dnp_taxonomy_diff(args.root)
    text = json.dumps(rep, indent=2, default=str) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
