#!/usr/bin/env python3
"""cbs_real_frames.py — `cbs_real_frames/1`, the real causal season-fold adapter.

v8's `cbs_real_adapter.py` audited and manifested frames that somebody else had
already built. Nothing in the repository built them. This module does: it joins
the contract to the masters, derives the twelve Stage-A features and the four team
channels, attaches row-level source-policy timestamps, and returns fold frames the
v9 runner would accept — together with schema, join, timestamp, provenance and
identity receipts.

**IT DOES NOT FIT, PREDICT OR SCORE.** There is no model here, no coefficient, no
accuracy or coverage figure, no profitability evaluation, and nothing that relates
a feature to an outcome. It builds frames and hashes them.

THE FEATURE DEFINITIONS ARE PORTED, NOT INVENTED
------------------------------------------------
`minutes_twostage.py` (registered `minutes_twostage_availability_v1`) already
derives all twelve. Its definitions are reproduced here — the 0.30 EWMA alpha, the
45-day and 20-game caps, the `min(k, 10)` denominator, the DNP prefix rule, the
`returning_flag` conjunction — so this adapter matches registered semantics rather
than inventing a second dialect.

ONE DELIBERATE DIVERGENCE, AND IT IS THE POINT
----------------------------------------------
`minutes_twostage` walks history **positionally**: `shift(1).ffill()` over the
ordered frame. v7 established that position is not knowability — a game played the
evening before a morning cutoff is prior in every sort key and its box score may
not have existed yet. Every feature here is therefore computed over the
**availability-admitted** prior set: a prior game contributes only when its
outcome-availability timestamp is strictly earlier than the current row's cutoff,
under the same registered `+36h` policy the runner uses.

Under the daily WNBA cadence that usually excludes a team's most recent game. That
is the gate working, and it means these features will **not** equal
`minutes_twostage`'s on the same rows. The difference is causal, deliberate and
disclosed.

DECISIONS THIS ADAPTER MAKES, STATED RATHER THAN ASSUMED
---------------------------------------------------------
* **Playoffs are kept.** `minutes_twostage` filters to `season_type == "Regular
  Season"`; the contract carries 2,478 playoff obligations. Dropping them would
  fail obligation coverage, so they are kept and this is an extension of the
  registered universe.
* **`appeared` comes from the contract**, not from `minutes.notna()`. Six rows are
  on the box score with exactly zero minutes; the contract calls them
  `appeared=False, in_target_box=True`, and `minutes_twostage` drops them entirely.
  The contract's reading is authoritative here.
* **The DNP prefix rule is kept as registered** (`DNP*`→CD, `NWT*`→NWT, else INJ),
  including the 82 rows whose reason text disagrees with their prefix. That is
  registered behaviour and is not silently "fixed".
* **`side = "home" if is_home == 1 else "away"`.** No such mapping existed in the
  repository; this is an adapter decision.
* **The contract's `team_id` wins** where it disagrees with the master's (8
  mid-season-trade rows). The obligation belongs to the team whose game index it
  was drawn from.
* **Contract rows with no master row** (3,154, all `appeared=False`) receive the
  registered declared defaults. Documented as an approximation, not an invention.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

import cbs_provenance as prov
from cbs_frame_identity import frames_digest
from cbs_generator import DAYS_CAP, MISS_CAP, P_ACTIVE_FEATURES
from cbs_v5 import REQUIRED_CHANNELS
from cbs_v7 import (OUTCOME_AVAILABILITY_POLICY_ID,
                    OUTCOME_AVAILABILITY_POLICY_LAG_HOURS)
from cbs_v9 import REQUIRED_PLAYER_FEATURE_SOURCES, REQUIRED_TEAM_FEATURE_SOURCES

ADAPTER_ID = "cbs_real_frames/1"
FOLD_RECEIPT_SCHEMA = "cbs_real_fold_receipt/1"

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

SOURCE_POLICIES = {
    "prior_game_availability": (
        "the outcome-availability timestamp of the most recent ADMITTED prior game "
        "for this player/team-season, under the registered +36h policy"),
    "no_prior_game_admitted": (
        "no prior game was readable at this cutoff, so no gamelog was consulted and "
        "the bound falls back to the schedule bound"),
    "schedule_day_before_noon_utc": (
        "noon UTC on the day before the game; the schedule is a pregame fact"),
}


class RealFrameError(RuntimeError):
    """The real inputs cannot be assembled into a causal fold."""


# --------------------------------------------------------------------------
# loading, with attestation enforced first
# --------------------------------------------------------------------------

def load_inputs(root: Path | str = REPO_ROOT, *, require_attested: bool = True):
    """Read the contract and masters, refusing unattested inputs.

    The attestation check runs before a single byte is turned into a feature. An
    adapter that builds frames from artifacts nothing attests has a provenance
    chain with a hole in the middle, and the hole would be invisible downstream.
    """
    root = Path(root)
    if require_attested:
        audit = prov.audit(root)
        if audit["hard_blockers"]:
            raise RealFrameError(
                "refusing to build frames; provenance preconditions are not met: "
                + "; ".join(f"{b['artifact']}: {b['detail']}"
                            for b in audit["hard_blockers"]))
    pg = pd.read_parquet(root / prov.PLAYER_GAME)
    tg = pd.read_parquet(root / prov.TEAM_GAME)
    mp = pd.read_parquet(root / prov.MASTER_PLAYER)
    mt = pd.read_parquet(root / prov.MASTER_TEAM)
    for f in (mp, mt):
        f["game_date"] = pd.to_datetime(f["game_date"], format="%Y-%m-%d")
    for f in (pg, tg):
        f["game_date"] = pd.to_datetime(f["game_date"])
    return pg, tg, mp, mt


def dnp_class(v) -> str | None:
    """The registered prefix rule, reproduced verbatim from minutes_twostage.py.

    `DNP*` -> CD, `NWT*` -> NWT, anything else -> INJ. The rule keys on the
    PREFIX, not the reason text, so 82 rows are classed against their own wording
    (`DNP - Injury/Illness` -> CD, `DND - Coach's Decision` -> INJ). That is
    registered behaviour; changing it here would fork the semantics silently.
    """
    if not isinstance(v, str) or not v.strip():
        return None
    u = v.upper()
    if u.startswith("DNP"):
        return "CD"
    if u.startswith("NWT"):
        return "NWT"
    return "INJ"


def availability_of(game_date: pd.Series) -> pd.Series:
    """The registered +36h conservative policy bound. Policy, never observed."""
    return (pd.to_datetime(game_date, utc=True).dt.floor("D")
            + pd.Timedelta(hours=OUTCOME_AVAILABILITY_POLICY_LAG_HOURS))


def schedule_bound(game_date: pd.Series) -> pd.Series:
    """Noon UTC the day before the game."""
    return (pd.to_datetime(game_date, utc=True).dt.floor("D")
            - pd.Timedelta(days=1)
            + pd.Timedelta(hours=SCHEDULE_BOUND_HOURS_BEFORE_GAME_DAY))


# --------------------------------------------------------------------------
# the causal player frame
# --------------------------------------------------------------------------

def build_player_frame(season: int, root: Path | str = REPO_ROOT, *,
                       require_attested: bool = True) -> dict:
    """Assemble the causal player fold for `season:<season>`.

    Returns train / test / universe frames plus receipts. Nothing is fitted and
    nothing is predicted; the frames are built and hashed.
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
    # every unmatched contract row is a candidate who never reached the box score
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
    # which players appeared in each team-game (played rows only)
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

    feats = {c: np.zeros(len(pg), dtype=float) for c in P_ACTIVE_FEATURES}
    feats["days_since_last_appearance"][:] = DAYS_CAP
    src_gamelog = np.empty(len(pg), dtype=object)
    src_policy = np.empty(len(pg), dtype=object)

    hist: dict[tuple, list] = {}
    for i in range(len(pg)):
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
        # player who has one. The known-row fixture in tests/test_cbs_v9.py exists
        # to catch exactly this.
        cls = None
        for h in reversed(adm):
            if isinstance(h["dnp_class"], str) and h["dnp_class"]:
                cls = h["dnp_class"]
                break
        feats["prev_dnp_cd"][i] = float(cls == "CD")
        feats["prev_dnp_inj"][i] = float(cls == "INJ")
        feats["prev_dnp_nwt"][i] = float(cls == "NWT")

        # team-index features over ADMITTED team games
        tkey = (int(pg.at[i, "team_id"]), s)
        tg_all = team_games.get(tkey, [])
        adm_tg = [g for g in tg_all if g[2] < cut]
        k = len(adm_tg)
        feats["team_gp_season"][i] = float(k)
        if k:
            own = [pid in appeared_by_game.get(g[1], ()) for g in adm_tg]
            feats["played_last_team_game"][i] = float(own[-1])
            n = min(k, TEAM_WINDOW)
            feats["played_share_l10_team_games"][i] = float(sum(own[-n:])) / n
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

        # row-level source policy
        if adm:
            src_gamelog[i] = max(h["avail"] for h in adm)
            src_policy[i] = "prior_game_availability"
        else:
            src_gamelog[i] = None
            src_policy[i] = "no_prior_game_admitted"

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

    # ---- row-level source timestamps -------------------------------------
    sched = schedule_bound(pg["game_date"])
    if (sched >= pg["cutoff"]).any():
        raise RealFrameError(
            f"{int((sched >= pg['cutoff']).sum())} rows have a schedule bound at or "
            f"after their own cutoff; the frozen schedule policy does not hold")
    gl = pd.Series(list(src_gamelog), index=pg.index)
    gl = pd.to_datetime(gl, utc=True).fillna(sched)
    pg["src_asof_gamelog"] = gl.map(lambda t: t.isoformat())
    pg["src_asof_roster"] = pg["src_asof_gamelog"]
    pg["src_asof_schedule"] = sched.map(lambda t: t.isoformat())
    pg["src_policy_gamelog"] = src_policy
    pg["src_policy_schedule"] = "schedule_day_before_noon_utc"
    pg["outcome_availability_source"] = "policy"
    pg["outcome_availability_policy_id"] = OUTCOME_AVAILABILITY_POLICY_ID

    late = int((pd.to_datetime(pg["src_asof_gamelog"], utc=True)
                >= pg["cutoff"]).sum())
    if late:
        raise RealFrameError(
            f"{late} rows read a gamelog source at or after their own cutoff")

    keep = ["row_uid", "player_id", "team_id", "season", "game_id", "game_date",
            "forecast_cutoff", "appeared", "minutes", "points", "fga",
            "fold_id"] + [c for c in P_ACTIVE_FEATURES
                          if c not in ("p_plays_prior", "player_gp_season")] + [
        "src_asof_gamelog", "src_asof_roster", "src_asof_schedule",
        "src_policy_gamelog", "src_policy_schedule",
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
                              REQUIRED_PLAYER_FEATURE_SOURCES),
    }


# --------------------------------------------------------------------------
# the causal team frame
# --------------------------------------------------------------------------

def build_team_frame(season: int, root: Path | str = REPO_ROOT, *,
                     require_attested: bool = True,
                     withhold_current_outcomes: bool = False) -> dict:
    """Assemble the causal team fold. `withhold_current_outcomes` drops every
    outcome column from the test frame, exercising the outcome-free interface."""
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

    # adapter decision: no is_home -> side mapping existed anywhere in the repo
    tg["side"] = np.where(tg["is_home"].astype(int) == 1, "home", "away")

    tg["cutoff"] = pd.to_datetime(tg["forecast_cutoff"], utc=True)
    tg["avail"] = availability_of(tg["game_date"])
    tg = tg.sort_values(["team_id", "game_date", "game_id"],
                        kind="mergesort").reset_index(drop=True)

    src = np.empty(len(tg), dtype=object)
    pol = np.empty(len(tg), dtype=object)
    hist: dict[tuple, list] = {}
    for i in range(len(tg)):
        key = (int(tg.at[i, "team_id"]), int(tg.at[i, "season"]))
        prior = hist.setdefault(key, [])
        adm = [a for a in prior if a < tg.at[i, "cutoff"]]
        if adm:
            src[i], pol[i] = max(adm), "prior_game_availability"
        else:
            src[i], pol[i] = None, "no_prior_game_admitted"
        prior.append(tg.at[i, "avail"])

    sched = schedule_bound(tg["game_date"])
    if (sched >= tg["cutoff"]).any():
        raise RealFrameError("schedule bound is not strictly before every cutoff")
    gl = pd.to_datetime(pd.Series(list(src), index=tg.index), utc=True).fillna(sched)
    tg["src_asof_team_gamelog"] = gl.map(lambda t: t.isoformat())
    tg["src_asof_schedule"] = sched.map(lambda t: t.isoformat())
    tg["src_policy_team_gamelog"] = pol
    tg["src_policy_schedule"] = "schedule_day_before_noon_utc"
    tg["outcome_availability_source"] = "policy"
    tg["outcome_availability_policy_id"] = OUTCOME_AVAILABILITY_POLICY_ID

    outcome_cols = [f"ch_{c}" for c in REQUIRED_CHANNELS] + ["team_points"]
    keep = ["row_uid", "team_id", "game_id", "season", "game_date",
            "forecast_cutoff", "side", "fold_id"] + outcome_cols + [
        "src_asof_team_gamelog", "src_asof_schedule", "src_policy_team_gamelog",
        "src_policy_schedule", "outcome_availability_source",
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
                              REQUIRED_TEAM_FEATURE_SOURCES),
    }


# --------------------------------------------------------------------------
# receipts
# --------------------------------------------------------------------------

def _receipts(kind, season, train, test, universe, join, full, sources) -> dict:
    """Schema, join, row-count, timestamp, provenance and identity. No model claim."""
    cut = pd.to_datetime(test["forecast_cutoff"], utc=True)
    ts = test[list(sources)].apply(pd.to_datetime, utc=True)
    asof = ts.max(axis=1)
    lead = (cut - asof)
    pol_cols = [c for c in full.columns if c.startswith("src_policy_")]
    policy_counts = {c: full[c].value_counts().to_dict() for c in pol_cols}
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
            "n_at_cutoff": int((asof == cut).sum()),
            "n_after_cutoff": int((asof > cut).sum()),
            "min_lead_seconds": float(lead.min().total_seconds()) if len(test) else None,
            "max_lead_seconds": float(lead.max().total_seconds()) if len(test) else None,
        },
        "provenance": {
            "outcome_availability_source": "policy",
            "outcome_availability_policy_id": OUTCOME_AVAILABILITY_POLICY_ID,
            "any_observed_source": False,
            "row_level_policies": policy_counts,
            "policy_definitions": SOURCE_POLICIES,
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
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--root", default=str(REPO_ROOT))
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    fold = build_fold(args.season, args.root)
    rep = {"schema": FOLD_RECEIPT_SCHEMA, "adapter": ADAPTER_ID,
           "generated_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
           "scope": ("frame construction, schema, join, timestamp, provenance and "
                     "identity only: nothing fitted, nothing predicted, no model "
                     "coverage or accuracy, no scoring, no profitability"),
           "receipts": fold["receipts"]}
    text = json.dumps(rep, indent=2, default=str) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
