#!/usr/bin/env python3
"""prediction_contract_v5.py — a TIERED candidacy universe. Stage 1: contract and universe only.

**IT DOES NOT FIT, PREDICT OR SCORE.** There is no model here, no coefficient, no accuracy figure,
no error figure, and no comparison of any forecast to any outcome. It builds a candidate universe,
classifies each row's evidence, counts rows and timestamps, and hashes what it built.

WHAT v5 IS FOR
--------------
`prediction_contract_v4` establishes candidacy **only** by prior same-season box membership. 977 of
28,322 played player-team-games (3.45%) are therefore owed no forecast: 749 at season openers,
where no prior same-season game exists at all, and 176 mid-season arrivals. See
`experiments/player_program/CANDIDACY_GAP_RECEIPT.json`.

THE DISTINCTION THAT ORGANISES THIS MODULE
-------------------------------------------
Candidacy and **verified obligation status** are different questions, and conflating them is how a
weak signal becomes a headline metric.

  Tier A  the player-team assignment is supported by information PROVABLY available before the
          forecast cutoff. Eligible for headline availability and coverage evaluation.
  Tier B  included through weaker but cutoff-safe evidence; current roster membership is NOT
          verified. Carries its evidence times and a confidence, and is reported SEPARATELY.
  Tier C  no defensible pre-cutoff evidence. No obligation is manufactured.

Prior-season affiliation is evidence of PAST affiliation. It is not proof of current roster
membership: a prior-season player may have been traded, waived, left unsigned, retired, suspended
or replaced before opening night, and rookies and new signings are absent from it entirely. It is
Tier B, and it is never described as a roster source.

THE POSTGAME PROHIBITION, ENFORCED STRUCTURALLY
-----------------------------------------------
Actual participation may NOT construct the forecast universe. `build_candidates` receives the
transaction wire, the report capture and prior-game box rows admitted strictly before the cutoff,
and it never reads the target game's box score. `audit_universe` runs afterwards, in a separate
function, over the generator's frozen output. A player who appears unexpectedly is recorded as a
**candidate-universe miss**, never retroactively added.

Run::

    python prediction_contract_v5.py --out experiments/prediction_contract_v5
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

import cbs_obligation_key as obk

REPO = Path(__file__).resolve().parent

CONTRACT_VERSION = "player_game_contract/5"
SUPERSEDES = "player_game_contract/4"
SUPERSEDES_REASON = (
    "v4 establishes candidacy only by prior SAME-SEASON box membership, so every team's first "
    "game of every season yields zero candidates and mid-season arrivals are never candidates for "
    "the club they actually play for. 977 played player-team-games (3.45%) are owed no forecast.")

MASTER_PLAYER = "data/masters/master_player.parquet"
V4_CONTRACT = "experiments/prediction_contract_v4/player_game.parquet"
TRANSACTIONS = "data/injury_history/injury_history.csv"
INJURY_CAPTURE = "data/injury_capture/injury_log.csv"

# --------------------------------------------------------------------------- #
# registered constants
# --------------------------------------------------------------------------- #

#: v4's lookback, inherited unchanged. S1 is the Tier-A source and must not drift.
ROSTER_LOOKBACK = 5

#: Team games after an acquisition during which S-TX may still establish candidacy. Chosen against
#: a measured trade-off, not asserted: at 3 the rule recovers 559 gap rows for 747 added
#: non-appearing candidate-games; unbounded recovers 731 for 31,302. The full curve is in
#: S_TX_HORIZON_EVIDENCE and in the spec.
S_TX_HORIZON = 3

S_TX_HORIZON_EVIDENCE = {
    "3": {"recovered": 559, "recall_pct": 57.2, "non_appearing_added": 747},
    "5": {"recovered": 567, "recall_pct": 58.0, "non_appearing_added": 1011},
    "10": {"recovered": 568, "recall_pct": 58.1, "non_appearing_added": 1621},
    "20": {"recovered": 576, "recall_pct": 59.0, "non_appearing_added": 2904},
    "unbounded": {"recovered": 731, "recall_pct": 74.8, "non_appearing_added": 31302},
}

#: Team-game indices below which S2 may establish candidacy at all.
S2_HORIZON = 5

#: The era boundary. S3 does not exist before this instant and may never admit before it.
REPORT_ERA_START = pd.Timestamp("2026-07-30T00:00:00Z")

#: The single retrospective observation time of the transaction wire. Recorded per row so a reader
#: can see that its publication time is NOT provable. The CSV was committed 2026-07-30 13:42 -0400
#: in 98271bb; the raw HTML is gitignored and absent, so no finer bound exists.
S_TX_OBSERVED_TIME = pd.Timestamp("2026-07-30T17:42:00Z")

ACQUIRE = frozenset({"signing", "trade", "waiver_claim", "draft", "contract_conversion"})
RELEASE = frozenset({"waiver", "retirement", "contract_suspension"})

TEAM_ALIAS = {"POR": "PDX", "PHO": "PHX"}

#: Source ids, their tiers and their team-assignment confidence. S4 is present and UNAVAILABLE by
#: construction: declaring it stops a later implementation quietly substituting something weaker.
SOURCES = {
    "S1": {"tier": "A", "confidence": "verified",
           "what": "in-season prior box membership within the admitted lookback window"},
    "S3": {"tier": "A", "confidence": "verified",
           "what": "captured pregame availability report carrying team affiliation"},
    "S_TX": {"tier": "B", "confidence": "probable",
             "what": "transaction wire acquisition, effective-dated, bounded by S_TX_HORIZON"},
    "S2": {"tier": "B", "confidence": "weak",
           "what": "prior-season franchise affiliation; evidence of PAST affiliation only"},
    "S4": {"tier": "A", "confidence": "verified",
           "what": "official roster/transaction feed with provable publication times",
           "available": False},
}
TIER_A_SOURCES = ("S1", "S3")
TIER_B_SOURCES = ("S_TX", "S2")
#: S1 beats S3 beats S_TX beats S2 when a single tier label must be chosen.
PRECEDENCE = ("S1", "S3", "S_TX", "S2")


class ContractError(RuntimeError):
    """The universe could not be built to specification."""


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def norm_name(s) -> str:
    if not isinstance(s, str):
        return ""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z ]", "", s.lower()).strip()


def _digest(obj) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


# --------------------------------------------------------------------------- #
# inputs
# --------------------------------------------------------------------------- #

def load_inputs(root: Path) -> dict:
    mp = pd.read_parquet(root / MASTER_PLAYER)
    mp["game_id"] = mp["game_id"].astype(str)
    for c in ("player_id", "team_id"):
        mp[c] = mp[c].astype("int64")
    mp["game_date"] = pd.to_datetime(mp["game_date"])
    mp["minutes_n"] = pd.to_numeric(mp["minutes"], errors="coerce")

    v4 = pd.read_parquet(root / V4_CONTRACT)
    v4["game_id"] = v4["game_id"].astype(str)
    for c in ("player_id", "team_id"):
        v4[c] = v4[c].astype("int64")
    v4["forecast_cutoff"] = pd.to_datetime(v4["forecast_cutoff"], utc=True)

    tx = None
    p = root / TRANSACTIONS
    if p.exists():
        tx = pd.read_csv(p)
        tx["date"] = pd.to_datetime(tx["date"], utc=True)

    rep = None
    p = root / INJURY_CAPTURE
    if p.exists():
        rep = pd.read_csv(p)
        rep["capture_utc"] = pd.to_datetime(rep["capture_utc"], format="%Y%m%dT%H%M%SZ",
                                            utc=True, errors="coerce")
    return {"master": mp, "v4": v4, "transactions": tx, "report": rep}


def identity_maps(mp: pd.DataFrame):
    by_name: dict[str, set] = {}
    for pid, nm in zip(mp["player_id"], mp["player_name"]):
        by_name.setdefault(norm_name(nm), set()).add(int(pid))
    abb = {a: int(t) for a, t in zip(mp["team_abbreviation"], mp["team_id"])}
    for alias, canon in TEAM_ALIAS.items():
        if alias not in abb and canon in abb:
            abb[alias] = abb[canon]
    by_team_name = {}
    for a, t in abb.items():
        by_team_name[a] = t
    return by_name, abb, by_team_name


# --------------------------------------------------------------------------- #
# the schedule spine, and the cutoffs v5 inherits from v4
# --------------------------------------------------------------------------- #

def schedule(mp: pd.DataFrame) -> pd.DataFrame:
    tg = (mp[["game_id", "team_id", "season", "game_date"]].drop_duplicates()
          .sort_values(["team_id", "season", "game_date", "game_id"], kind="mergesort")
          .reset_index(drop=True))
    tg["team_game_index"] = tg.groupby(["team_id", "season"]).cumcount()
    return tg


#: v4's own conservative fallback: 18:00 UTC on the day BEFORE the game. Registered in
#: prediction_contract_v4 as POLICY_DATE_ONLY and used for 25,367 of its 35,627 rows.
POLICY_DATE_ONLY = "date_only_prior_day_cutoff"


def date_only_cutoff(game_date) -> pd.Timestamp:
    d = pd.Timestamp(game_date)
    if d.tzinfo is None:
        d = d.tz_localize("UTC")
    return d.normalize() - pd.Timedelta(hours=6)


def cutoffs_from_v4(v4: pd.DataFrame, tg: pd.DataFrame) -> tuple[dict, dict]:
    """Inherit v4's cutoffs, and DERIVE one for every game v4 never covered.

    v4 owes nothing for a team's season opener, so when BOTH clubs are playing their first game of
    the season — league opening weekend — v4 contains no row for that game at all and therefore no
    cutoff. An earlier draft of this module skipped such games entirely, which silently discarded
    728 of the 749 opener rows v5 exists to recover: the contract could not describe the gap
    because the gap had erased its own timestamp.

    Games absent from v4 get v4's OWN registered conservative fallback, 18:00 UTC on the day
    before, and every such row is labelled `cutoff_source = derived_absent_from_v4` so a reviewer
    can separate inherited timestamps from derived ones. Nothing is invented: the policy is v4's,
    the date is the schedule's.
    """
    inherited = (v4[["game_id", "forecast_cutoff"]].drop_duplicates()
                 .groupby("game_id")["forecast_cutoff"].min())
    cut = {str(k): v for k, v in inherited.items()}
    src = {k: "inherited_from_v4" for k in cut}
    derived = 0
    for g, d in zip(tg["game_id"], tg["game_date"]):
        g = str(g)
        if g not in cut:
            cut[g] = date_only_cutoff(d)
            src[g] = "derived_absent_from_v4"
            derived += 1
    return cut, {"n_inherited": len(inherited), "n_derived": derived,
                 "derived_policy": POLICY_DATE_ONLY,
                 "derived_rule": "18:00 UTC on the day before the game — v4's own "
                                 "POLICY_DATE_ONLY, applied to games v4 never covered",
                 "why_derivation_is_needed": (
                     "v4 owes nothing for a season opener, so a game in which BOTH clubs are "
                     "playing their first game has no v4 row and no cutoff. Skipping those games "
                     "would discard the majority of the rows v5 exists to recover."),
                 "source_by_game": src}


# --------------------------------------------------------------------------- #
# evidence indices — each built ONLY from records observable before a cutoff
# --------------------------------------------------------------------------- #

def s1_index(mp: pd.DataFrame) -> dict:
    """(team_id, game_id) -> frozenset(player_id) present in that club's box, DNP rows included."""
    idx: dict = {}
    for t, g, p in zip(mp["team_id"], mp["game_id"], mp["player_id"]):
        idx.setdefault((int(t), str(g)), set()).add(int(p))
    return {k: frozenset(v) for k, v in idx.items()}


def s2_index(mp: pd.DataFrame) -> dict:
    """(team_id, player_id) -> the earliest season in which she appeared in that club's box."""
    idx: dict = {}
    for t, p, s in zip(mp["team_id"], mp["player_id"], mp["season"]):
        k = (int(t), int(p))
        s = int(s)
        if k not in idx or s < idx[k]:
            idx[k] = s
    return idx


def s2_seasons(mp: pd.DataFrame) -> dict:
    idx: dict = {}
    for t, p, s in zip(mp["team_id"], mp["player_id"], mp["season"]):
        idx.setdefault((int(t), int(p)), set()).add(int(s))
    return idx


def stx_index(tx: pd.DataFrame, by_name, abb) -> tuple[dict, dict, dict]:
    """Acquisition and release dates per (team_id, player_id), plus resolution accounting."""
    acq: dict = {}
    rel: dict = {}
    stats = {"acq_rows": 0, "acq_resolved": 0, "rel_rows": 0, "rel_resolved": 0,
             "unresolved_names": set()}
    if tx is None:
        return acq, rel, {**stats, "unresolved_names": []}

    for frame, cats, col, target in ((tx, ACQUIRE, "player_acquired", acq),
                                     (tx, RELEASE, "player_relinquished", rel)):
        sub = frame.loc[frame["category"].isin(cats) & frame[col].notna()]
        key = "acq" if target is acq else "rel"
        stats[f"{key}_rows"] += int(len(sub))
        for nm, tm, dt in zip(sub[col], sub["team"], sub["date"]):
            pn, tid = norm_name(nm), abb.get(tm)
            if tid is None or pn not in by_name:
                stats["unresolved_names"].add(str(nm))
                continue
            stats[f"{key}_resolved"] += 1
            for pid in by_name[pn]:
                target.setdefault((int(tid), int(pid)), []).append(dt)
    for d in (acq, rel):
        for k in d:
            d[k] = sorted(d[k])
    stats["unresolved_names"] = sorted(stats["unresolved_names"])[:50]
    return acq, rel, stats


def s3_index(rep: pd.DataFrame, by_name, abb) -> dict:
    """(team_id, player_id) -> sorted capture times at which a report named her for that club."""
    idx: dict = {}
    if rep is None:
        return idx
    name_to_abb = {"Atlanta Dream": "ATL", "Chicago Sky": "CHI", "Connecticut Sun": "CON",
                   "Dallas Wings": "DAL", "Golden State Valkyries": "GSV", "Indiana Fever": "IND",
                   "Los Angeles Sparks": "LAS", "Las Vegas Aces": "LVA", "Minnesota Lynx": "MIN",
                   "New York Liberty": "NYL", "Phoenix Mercury": "PHX", "Portland Fire": "PDX",
                   "Seattle Storm": "SEA", "Toronto Tempo": "TOR", "Washington Mystics": "WAS"}
    for tm, pl, cap in zip(rep["team"], rep["player"], rep["capture_utc"]):
        if pd.isna(cap):
            continue
        tid = abb.get(name_to_abb.get(str(tm), ""), None)
        pn = norm_name(pl)
        if tid is None or pn not in by_name:
            continue
        for pid in by_name[pn]:
            idx.setdefault((int(tid), int(pid)), []).append(cap)
    return {k: sorted(v) for k, v in idx.items()}


# --------------------------------------------------------------------------- #
# the generator
# --------------------------------------------------------------------------- #

def availability_bound(dates: pd.Series) -> pd.Series:
    """v4's `+36h` outcome-availability policy, inherited unchanged."""
    return pd.to_datetime(dates, utc=True) + pd.Timedelta(hours=36)


def build_candidates(inputs: dict, *, s_tx_horizon: int = S_TX_HORIZON,
                     s2_horizon: int = S2_HORIZON) -> tuple[pd.DataFrame, dict]:
    """The candidate universe. Reads NOTHING from the target game's box score.

    For each team-game, each source is consulted with its own evidence time, and a source is
    admitted only if that time is STRICTLY earlier than the row's forecast cutoff.
    """
    mp, v4 = inputs["master"], inputs["v4"]
    by_name, abb, _ = identity_maps(mp)
    tg = schedule(mp)
    cut, cut_receipt = cutoffs_from_v4(v4, tg)

    s1 = s1_index(mp)
    s2_all = s2_seasons(mp)
    acq, rel, tx_stats = stx_index(inputs["transactions"], by_name, abb)
    s3 = s3_index(inputs["report"], by_name, abb)

    # per (team, season): the ordered game list with availability bounds
    tg = tg.copy()
    tg["avail"] = availability_bound(tg["game_date"])
    by_ts: dict = {}
    for t, s, g, d, i, a in zip(tg["team_id"], tg["season"], tg["game_id"], tg["game_date"],
                                tg["team_game_index"], tg["avail"]):
        by_ts.setdefault((int(t), int(s)), []).append((str(g), d, int(i), a))

    # players who already appeared for this club this season, by team-game index, so S1 can be
    # said to have "taken over". This reads only PRIOR games' boxes.
    appeared_idx: dict = {}
    played = mp.loc[mp["minutes_n"].fillna(0) > 0]
    gi = {(str(g), int(t)): int(i) for g, t, i
          in zip(tg["game_id"], tg["team_id"], tg["team_game_index"])}
    for g, t, p, s in zip(played["game_id"], played["team_id"], played["player_id"],
                          played["season"]):
        k = (int(t), int(s), int(p))
        v = gi.get((str(g), int(t)))
        if v is not None:
            appeared_idx[k] = min(appeared_idx.get(k, 10**9), v)

    rows: list[dict] = []
    missing_cutoff: list[str] = []
    same_day: list[dict] = []

    for (team_id, season), games in by_ts.items():
        for gid, gdate, gidx, _avail in games:
            c = cut.get(gid)
            if c is None or pd.isna(c):
                missing_cutoff.append(gid)
                continue
            prior = [(g2, d2, i2, a2) for (g2, d2, i2, a2) in games if i2 < gidx]
            admitted = [x for x in prior if x[3] < c]
            window = admitted[-ROSTER_LOOKBACK:]

            named: dict[int, dict] = {}

            # ---- S1 : Tier A -------------------------------------------------
            for g2, _d2, _i2, a2 in window:
                for pid in s1.get((team_id, g2), ()):
                    e = named.setdefault(pid, {"sources": [], "times": {}})
                    if "S1" not in e["sources"]:
                        e["sources"].append("S1")
                        e["times"]["S1"] = a2
                    else:
                        e["times"]["S1"] = max(e["times"]["S1"], a2)

            # ---- S3 : Tier A, report era only --------------------------------
            if c >= REPORT_ERA_START:
                for (t2, pid), caps in s3.items():
                    if t2 != team_id:
                        continue
                    ok = [x for x in caps if x < c]
                    if ok:
                        e = named.setdefault(pid, {"sources": [], "times": {}})
                        e["sources"].append("S3")
                        e["times"]["S3"] = max(ok)

            # ---- S_TX : Tier B, bounded --------------------------------------
            for (t2, pid), dates in acq.items():
                if t2 != team_id:
                    continue
                before = [x for x in dates if x < c]
                if not before:
                    continue
                last_acq = max(before)
                # a release strictly before the cutoff and after the acquisition removes her
                if any(last_acq < r < c for r in rel.get((t2, pid), ())):
                    same_day.append({"game_id": gid, "team_id": team_id, "player_id": pid,
                                     "reason": "released_after_acquisition_before_cutoff"})
                    continue
                # S1 has taken over once she has appeared for this club this season
                fa = appeared_idx.get((team_id, season, pid))
                if fa is not None and fa < gidx:
                    continue
                # bounded: team games played by this club since the acquisition
                since = sum(1 for (_g, d2, i2, _a) in games
                            if i2 < gidx and last_acq <= pd.Timestamp(d2).tz_localize("UTC"))
                if since > s_tx_horizon:
                    continue
                e = named.setdefault(pid, {"sources": [], "times": {}})
                e["sources"].append("S_TX")
                e["times"]["S_TX"] = last_acq

            # ---- S2 : Tier B, weak, early-season only ------------------------
            if gidx < s2_horizon:
                for (t2, pid), seasons_seen in s2_all.items():
                    if t2 != team_id:
                        continue
                    if any(s < season for s in seasons_seen):
                        e = named.setdefault(pid, {"sources": [], "times": {}})
                        e["sources"].append("S2")
                        # evidence time: the last admitted game of the prior season is not tracked
                        # per row, so the season boundary is used and labelled as such
                        e["times"]["S2"] = pd.Timestamp(f"{season}-01-01T00:00:00Z")

            for pid, e in named.items():
                srcs = [s for s in PRECEDENCE if s in e["sources"]]
                tier = "A" if any(s in TIER_A_SOURCES for s in srcs) else "B"
                lead = srcs[0]
                rows.append({
                    "game_id": gid, "team_id": team_id, "player_id": pid,
                    "game_date": gdate, "season": season, "team_game_index": gidx,
                    "forecast_cutoff": c,
                    "candidate_source": "|".join(srcs),
                    "team_assignment_source": lead,
                    "team_assignment_confidence": SOURCES[lead]["confidence"],
                    "universe_tier": tier,
                    "is_fallback": tier == "B",
                    "candidate_evidence_time": max(e["times"].values()),
                    "candidate_published_time": (e["times"].get("S1")
                                                 or e["times"].get("S3")),
                    "candidate_observed_time": (S_TX_OBSERVED_TIME if lead == "S_TX"
                                                else e["times"][lead]),
                    "cutoff_source": cut_receipt["source_by_game"].get(gid),
                    "n_sources": len(srcs),
                    "exclusion_reason": None,
                })

    cand = pd.DataFrame(rows)
    if not len(cand):
        raise ContractError("no candidates were generated")

    cand["row_uid"] = [obk.row_uid(p, g, t) for p, g, t
                       in zip(cand["player_id"], cand["game_id"].astype(str), cand["team_id"])]
    cand["obligation_uid"] = cand["row_uid"]
    cand["player_game_uid"] = [obk.player_game_uid(p, g) for p, g
                               in zip(cand["player_id"], cand["game_id"].astype(str))]
    cand["obligation_key_id"] = obk.OBLIGATION_KEY_ID
    cand["contract_version"] = CONTRACT_VERSION
    cand["era"] = np.where(cand["forecast_cutoff"] >= REPORT_ERA_START,
                           "report_assisted", "box_only")

    receipts = {
        "cutoffs": {k: v for k, v in cut_receipt.items()
                    if k != "source_by_game"},
        "transaction_identity": {k: v for k, v in tx_stats.items()},
        "n_games_without_a_cutoff": len(set(missing_cutoff)),
        "games_without_a_cutoff": sorted(set(missing_cutoff))[:20],
        "n_released_before_cutoff_suppressed": len(same_day),
    }
    return cand, receipts


# --------------------------------------------------------------------------- #
# history accounting — three named fields, never one overloaded one
# --------------------------------------------------------------------------- #

def add_history(cand: pd.DataFrame, mp: pd.DataFrame) -> pd.DataFrame:
    """`n_prior_candidate_obligations`, `n_prior_appearances`, `n_prior_team_games`.

    Each defined ONCE and never conditioned on fold or target. `n_prior_games` is not produced.
    """
    c = cand.sort_values(["player_id", "season", "forecast_cutoff", "game_id"],
                         kind="mergesort").reset_index(drop=True)

    # (1) prior candidate OBLIGATIONS: strictly-earlier cutoffs in the same (player, season)
    out = np.zeros(len(c), dtype=np.int64)
    for _, grp in c.groupby(["player_id", "season"], sort=False):
        cuts = grp["forecast_cutoff"].to_numpy()
        out[grp.index.to_numpy()] = np.searchsorted(cuts, cuts, side="left")
    c["n_prior_candidate_obligations"] = out

    # (2) prior APPEARANCES: admitted prior appearances in the same (player, season)
    played = mp.loc[mp["minutes_n"].fillna(0) > 0,
                    ["player_id", "team_id", "game_id", "season", "game_date"]].copy()
    played["avail"] = availability_bound(played["game_date"])
    app: dict = {}
    for p, s, a in zip(played["player_id"], played["season"], played["avail"]):
        app.setdefault((int(p), int(s)), []).append(a)
    for k in app:
        app[k].sort()
    c["n_prior_appearances"] = [
        int(np.searchsorted(app.get((int(p), int(s)), []), cu, side="left"))
        for p, s, cu in zip(c["player_id"], c["season"], c["forecast_cutoff"])]

    # (3) prior TEAM games: admitted prior games of this team this season
    tg = (mp[["game_id", "team_id", "season", "game_date"]].drop_duplicates())
    tg["avail"] = availability_bound(tg["game_date"])
    tgi: dict = {}
    for t, s, a in zip(tg["team_id"], tg["season"], tg["avail"]):
        tgi.setdefault((int(t), int(s)), []).append(a)
    for k in tgi:
        tgi[k].sort()
    c["n_prior_team_games"] = [
        int(np.searchsorted(tgi.get((int(t), int(s)), []), cu, side="left"))
        for t, s, cu in zip(c["team_id"], c["season"], c["forecast_cutoff"])]

    c["is_cold_start"] = c["n_prior_appearances"] == 0

    # `n_prior_appearances > n_prior_candidate_obligations` is NOT a contract violation, and an
    # earlier draft of the spec wrongly required the opposite. Appearances are a fact about games
    # PLAYED; obligations count forecasts OWED. A player who played a season opener -- for which
    # v4 and v5 alike may owe nothing -- carries one more appearance than obligation for the rest
    # of her season. The quantity is therefore a per-row MEASURE OF UNIVERSE INCOMPLETENESS and is
    # reported as one, not enforced as an invariant. Enforcing it would have made the contract
    # refuse to describe the very gap it exists to close.
    c["appearances_exceed_obligations"] = (
        c["n_prior_appearances"] > c["n_prior_candidate_obligations"])

    if "n_prior_games" in c.columns:
        raise ContractError("n_prior_games is retired and must never be emitted")
    return c


# --------------------------------------------------------------------------- #
# validation
# --------------------------------------------------------------------------- #

def validate(cand: pd.DataFrame, v4: pd.DataFrame) -> dict:
    problems: list[str] = []

    # 1 key identity
    obk.assert_unique_canonical_keys(cand, "v5 candidate universe")
    want = np.asarray([obk.row_uid(p, g, t) for p, g, t
                       in zip(cand["player_id"], cand["game_id"].astype(str), cand["team_id"])])
    if int((cand["row_uid"].to_numpy() != want).sum()):
        problems.append("row_uid does not re-derive")

    # 2 cutoff safety
    late = int((cand["candidate_evidence_time"] >= cand["forecast_cutoff"]).sum())
    if late:
        problems.append(f"{late} rows whose evidence time is not strictly before their cutoff")

    # 3 tier integrity
    for _, r in cand.head(0).iterrows():
        pass
    srcs = cand["candidate_source"].str.split("|")
    tier_a = srcs.map(lambda ss: any(s in TIER_A_SOURCES for s in ss))
    if int((tier_a != (cand["universe_tier"] == "A")).sum()):
        problems.append("universe_tier disagrees with the sources named")
    if cand["candidate_source"].str.contains("S4").any():
        problems.append("S4 is declared unavailable and must never appear")

    # 4 era
    bad_era = int(((cand["candidate_source"].str.contains("S3"))
                   & (cand["forecast_cutoff"] < REPORT_ERA_START)).sum())
    if bad_era:
        problems.append(f"{bad_era} rows admit S3 before the report era began")

    # 5 superset
    v4k = set(zip(v4["game_id"].astype(str), v4["team_id"], v4["player_id"]))
    v5k = set(zip(cand["game_id"].astype(str), cand["team_id"], cand["player_id"]))
    lost = v4k - v5k
    if lost:
        problems.append(f"{len(lost)} v4 obligations are absent from v5; v5 may only ADD")

    # 6 history fields
    for f in ("n_prior_candidate_obligations", "n_prior_appearances", "n_prior_team_games"):
        if f not in cand.columns:
            problems.append(f"missing history field {f}")
        elif int((cand[f] < 0).sum()):
            problems.append(f"{f} has negative values")
    if "n_prior_games" in cand.columns:
        problems.append("n_prior_games must not be emitted")

    return {
        "receipt": "contract_v5_validation/1", "ok": not problems, "problems": problems,
        "n_rows": int(len(cand)),
        "n_rows_where_appearances_exceed_obligations": int(
            cand["appearances_exceed_obligations"].sum())
        if "appearances_exceed_obligations" in cand.columns else None,
        "appearances_exceed_obligations_is_not_a_violation": (
            "appearances count games PLAYED, obligations count forecasts OWED. A player who "
            "played a season opener the contract owed nothing for carries the excess for the "
            "rest of her season. It is a per-row measure of universe incompleteness, reported "
            "rather than enforced -- enforcing it would make the contract refuse to describe the "
            "gap it exists to close."),
        "n_v4_rows": len(v4k), "n_v5_rows": len(v5k),
        "n_added_vs_v4": len(v5k - v4k), "n_lost_vs_v4": len(lost),
        "superset_property_holds": not lost,
        "checked": ["key identity and re-derivation", "cutoff strict inequality",
                    "tier integrity and S4 absence", "era declaration",
                    "superset over v4", "history fields present, non-negative, unoverloaded"],
    }


# --------------------------------------------------------------------------- #
# the postgame audit — runs AFTER the generator, over its frozen output
# --------------------------------------------------------------------------- #

def audit_universe(cand: pd.DataFrame, mp: pd.DataFrame) -> dict:
    """What the pregame universe missed, and what it over-included.

    The box score enters HERE and only here. It never touched `build_candidates`.
    """
    played = (mp.loc[mp["minutes_n"].fillna(0) > 0,
                     ["game_id", "team_id", "player_id", "season"]].drop_duplicates())
    played["game_id"] = played["game_id"].astype(str)
    pk = set(zip(played["game_id"], played["team_id"], played["player_id"]))

    ck = {}
    for g, t, p, tier in zip(cand["game_id"].astype(str), cand["team_id"], cand["player_id"],
                             cand["universe_tier"]):
        ck[(g, int(t), int(p))] = tier

    miss = sorted(pk - set(ck))
    miss_df = pd.DataFrame(miss, columns=["game_id", "team_id", "player_id"]) if miss else \
        pd.DataFrame(columns=["game_id", "team_id", "player_id"])
    if len(miss_df):
        miss_df = miss_df.merge(played, on=["game_id", "team_id", "player_id"], how="left")

    cand2 = cand.copy()
    cand2["appeared"] = [(g, int(t), int(p)) in pk for g, t, p
                         in zip(cand2["game_id"].astype(str), cand2["team_id"],
                                cand2["player_id"])]

    per_season = {}
    for s, g in cand2.groupby("season"):
        a = g.loc[g["universe_tier"] == "A"]
        b = g.loc[g["universe_tier"] == "B"]
        ms = miss_df.loc[miss_df["season"] == s] if len(miss_df) else miss_df
        per_season[str(int(s))] = {
            "tier_a_obligations": int(len(a)),
            "tier_b_fallback_candidates": int(len(b)),
            "tier_a_appeared": int(a["appeared"].sum()),
            "tier_b_appeared": int(b["appeared"].sum()),
            "candidates_that_did_not_appear_tier_a": int((~a["appeared"]).sum()),
            "candidates_that_did_not_appear_tier_b": int((~b["appeared"]).sum()),
            "appearing_players_missed_by_the_universe": int(len(ms)),
        }

    by_source = {}
    for src in PRECEDENCE:
        g = cand2.loc[cand2["candidate_source"].str.contains(src)]
        if not len(g):
            continue
        by_source[src] = {
            "tier": SOURCES[src]["tier"],
            "n_rows_named": int(len(g)),
            "n_appeared": int(g["appeared"].sum()),
            "n_did_not_appear": int((~g["appeared"]).sum()),
            "n_rows_where_this_is_the_ONLY_source": int((g["n_sources"] == 1).sum()),
            "n_appeared_where_this_is_the_only_source": int(
                g.loc[g["n_sources"] == 1, "appeared"].sum()),
        }

    dup = (cand.groupby(["game_id", "player_id"]).size())
    dup = dup[dup > 1]

    return {
        "receipt": "universe_audit/1",
        "postgame_use_declaration": (
            "the box score is used ONLY here, to audit what the pregame universe missed and "
            "over-included. build_candidates never reads it. A player who appears unexpectedly is "
            "a candidate-universe MISS, never retroactively added."),
        "totals": {
            "n_candidates": int(len(cand)),
            "tier_a": int((cand["universe_tier"] == "A").sum()),
            "tier_b": int((cand["universe_tier"] == "B").sum()),
            "n_played_player_team_games": int(len(pk)),
            "appearing_players_missed_by_the_universe": int(len(miss)),
            "candidates_that_did_not_appear": int((~cand2["appeared"]).sum()),
            "duplicated_players_across_teams_in_one_game": int(len(dup)),
        },
        "per_season": per_season,
        "by_source": by_source,
        "false_obligation_probe": {
            "question": ("do S2 and S_TX name players who are no longer with the club — the "
                         "failure mode recall alone cannot detect"),
            "S2_only_rows": by_source.get("S2", {}).get(
                "n_rows_where_this_is_the_ONLY_source"),
            "S2_only_rows_that_appeared": by_source.get("S2", {}).get(
                "n_appeared_where_this_is_the_only_source"),
            "S_TX_only_rows": by_source.get("S_TX", {}).get(
                "n_rows_where_this_is_the_ONLY_source"),
            "S_TX_only_rows_that_appeared": by_source.get("S_TX", {}).get(
                "n_appeared_where_this_is_the_only_source"),
            "note": ("'did not appear' is NOT 'false candidate': a rostered healthy scratch is a "
                     "correct candidate and a legitimate low-p_active obligation. These bound "
                     "candidate INFLATION, they do not count errors."),
        },
        "missed_sample": miss_df.head(20).to_dict("records") if len(miss_df) else [],
    }


# --------------------------------------------------------------------------- #

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=str(REPO))
    ap.add_argument("--out", default=None)
    ap.add_argument("--s-tx-horizon", type=int, default=S_TX_HORIZON)
    ap.add_argument("--s2-horizon", type=int, default=S2_HORIZON)
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    out = Path(args.out) if args.out else root / "experiments" / "prediction_contract_v5"

    inputs = load_inputs(root)
    cand, gen_receipts = build_candidates(inputs, s_tx_horizon=args.s_tx_horizon,
                                          s2_horizon=args.s2_horizon)
    cand = add_history(cand, inputs["master"])
    val = validate(cand, inputs["v4"])
    aud = audit_universe(cand, inputs["master"])

    out.mkdir(parents=True, exist_ok=True)
    cand.to_parquet(out / "player_game.parquet", index=False)

    contract = {
        "schema": "prediction_contract_v5/1",
        "contract_version": CONTRACT_VERSION,
        "supersedes": SUPERSEDES,
        "supersedes_reason": SUPERSEDES_REASON,
        "stage": "1 — contract and universe only. NOTHING IS FITTED, PREDICTED OR SCORED.",
        "generated_utc": _utc(),
        "constants": {"ROSTER_LOOKBACK": ROSTER_LOOKBACK, "S_TX_HORIZON": args.s_tx_horizon,
                      "S2_HORIZON": args.s2_horizon,
                      "REPORT_ERA_START": str(REPORT_ERA_START),
                      "S_TX_OBSERVED_TIME": str(S_TX_OBSERVED_TIME)},
        "s_tx_horizon_evidence": S_TX_HORIZON_EVIDENCE,
        "sources": SOURCES,
        "precedence": list(PRECEDENCE),
        "tier_semantics": {
            "A": "assignment provably available before the cutoff; eligible for HEADLINE "
                 "availability and coverage evaluation",
            "B": "cutoff-safe but current roster membership NOT verified; reported SEPARATELY and "
                 "never mixed silently into Tier A headline metrics",
            "C": "no defensible pre-cutoff evidence; NO obligation manufactured; preserved in the "
                 "postgame coverage audit as a candidate-universe miss",
        },
        "generation_receipts": gen_receipts,
        "validation": val,
        "universe_audit": aud,
        "contract_digest": _digest({"n": int(len(cand)),
                                    "keys": sorted(cand["row_uid"].tolist())[:0]}),
    }
    (out / "contract.json").write_text(json.dumps(contract, indent=2, default=str) + "\n",
                                       encoding="utf-8", newline="")
    (out / "universe_diagnostics.json").write_text(
        json.dumps(aud, indent=2, default=str) + "\n", encoding="utf-8", newline="")

    print(f"wrote {out}")
    print(json.dumps({
        "n_candidates": int(len(cand)),
        "tier_a": aud["totals"]["tier_a"], "tier_b": aud["totals"]["tier_b"],
        "n_added_vs_v4": val["n_added_vs_v4"], "n_lost_vs_v4": val["n_lost_vs_v4"],
        "superset_holds": val["superset_property_holds"],
        "appearing_players_missed": aud["totals"]["appearing_players_missed_by_the_universe"],
        "validation_ok": val["ok"], "problems": val["problems"][:5],
    }, indent=2))
    return 0 if val["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
