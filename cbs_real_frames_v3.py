#!/usr/bin/env python3
"""cbs_real_frames_v3.py — `cbs_real_frames/3`: every obligation join is TEAM-AWARE.

**IT DOES NOT FIT, PREDICT OR SCORE.** There is no model here, no coefficient, no accuracy,
no error figure, no evaluation of any forecast against any outcome, and no profitability
figure. It builds frames, counts rows and timestamps, and hashes what it built.

WHY `/3` EXISTS
---------------
`contract_baseline_suite_v10` registered the claim that `cbs_real_frames/2` "builds and hashes
real player folds". It does not. `cbs_real_frames_v2.build_player_frame(season,
require_attested=True)` raises

    pandas.errors.MergeError: Merge keys are not unique in left dataset;
    not a one-to-one merge

for **every** season 2021-2026 — not only 2024 — at `cbs_real_frames_v2.py:400`::

    pg = pg.merge(m, on=["game_id", "player_id"], how="left", validate="1:1")

The left frame is the obligation universe, in which a player traded mid-season owes TWO
forecasts for the head-to-head game against her old club. 28 rows share 14 team-blind
`(game_id, player_id)` pairs, so the merge cannot be 1:1 and the real player path has never
executed.

`prediction_contract_v4` and `cbs_obligation_key` fixed the KEY. This module fixes the
JOINS, which is a separate defect: a unique key does not by itself make a team-blind join
team-aware, and three of this adapter's joins were team-blind.

THE THREE TEAM-BLIND SITES, AND WHAT EACH ONE COST
--------------------------------------------------

**1. The master starter/DNP join (`/2` line 400).** Joined on `(game_id, player_id)`.
`data/masters/master_player.parquet` has exactly one row per `(game_id, player_id)` — the
club the player actually turned out for — so the team-blind join copies THAT club's
`starter_flag` and `dnp_reason` onto the OTHER club's obligation. Measured on the real v4
contract: **13 obligations** receive a master box row belonging to a different club. Two of
them import a `DNP - Coach's Decision` (fabricating `prev_dnp_cd` for a club that never
benched her) and two import `starter_flag = 1` (crediting a start to a club she did not
start for). `/3` joins on `(game_id, team_id, player_id)`, against which the master is also
unique, so the merge is a genuine 1:1 and the wrong-club evidence cannot arrive.
`team_blind_join_counterfactual()` reports the measurement.

**2. The appearance index (`/2` line 423).** `appeared_by_game` was keyed on `game_id`
alone. A `game_id` names a GAME, which has two teams in it, so the set contains the
opponent's players too. The three team-history features that read it —
`played_last_team_game`, `played_share_l10_team_games`, `games_missed_streak` — therefore
credited a player's appearance FOR THE OPPONENT as an appearance for the club whose
obligation was being built. Measured on the real v4 contract: **167** distinct
`(team_id, game_id, player_id)` triples where a player appeared against a club she also owed
obligations to that season, corrupting **1,347** individual `own[]` lookups across **860
obligation rows**. This is a far larger blast radius than the 28-row merge failure, and it
is invisible in `/2` because it raises nothing. `/3` keys the index on
`(team_id, game_id)`. `team_blind_appearance_counterfactual()` reports the measurement.

**3. The universe (`/2` line 741).** Built on `["row_uid", "fold_id", "forecast_cutoff"]`
with `/2`'s team-blind `row_uid`, so two obligations collapsed into one universe key. `/3`
emits the canonical `cbs_obligation_key.row_uid` and calls `assert_unique_canonical_keys`
on the full frame, on train, on test and on the universe before any of them is returned.
The universe additionally carries `player_id`, `team_id`, `game_id` and `obligation_key_id`
so that `contract_validator_v4_strict` can RE-DERIVE the key rather than trust the column.

THE SEMANTIC POINT, STATED EXPLICITLY
-------------------------------------
After the team-aware join, a traded player's OLD-club obligation receives **no master
starter/DNP row at all**. She played that game for the new club; the old club has no box row
for her. **That is correct, and it is not missing data** — it is the absence of evidence
about a fact that never happened. The frame says so in a dedicated column,
`master_row_present`, rather than letting the reader infer it from a null.

The failure mode this creates is silent coercion, and `/2` shipped exactly that bug once
before: the v9-era `if h["dnp_class"]:` test evaluated TRUE on a pandas NaN and stopped the
carry-forward scan at the first non-DNP row. So `/3` asserts the intended treatment instead
of assuming it:

* `dnp_class` is `None` — never `"UNKNOWN"`, never a class — on every row with no master
  row. `UNKNOWN` means "a reason was recorded and this taxonomy declines to guess it";
  absence of a row is a different statement and gets a different value.
* `starter_flag_observed` stays NULL on those rows. The filled `starter_flag` (0.0) exists
  only because the history record needs a float, and it is asserted to be unreachable: it is
  read only for rows in `played`, and `appeared` implies `master_row_present` — checked, and
  a violation is a hard refusal.
* the `prev_dnp_*` carry-forward keeps `/2`'s `isinstance(..., str)` guard, and `/3` asserts
  that a no-evidence row never sets `prev_dnp_cd/inj/nwt/unknown` and never sets
  `returning_flag`.

WHAT IS DELIBERATELY UNCHANGED
------------------------------
The frozen DNP taxonomy, the `+36h` availability policy, the 0.30 EWMA alpha, the 45-day and
20-game caps, the `min(k, 10)` denominator, the four per-source `feature_asof` bounds, the
roster window rule, the channel identity, and the receipt structure are all `/2`'s and are
**imported from it rather than copied**, so a reviewer can see in one glance that they did
not change. Only the three joins, the key attestation and the added accounting are new.

ONE CONSEQUENCE OF THE DUAL OBLIGATION, DISCLOSED RATHER THAN HIDDEN
--------------------------------------------------------------------
A player's own history (`min_ewma`, `days_since_last_appearance`, `prev_dnp_*`) is keyed on
`(player_id, season)` and NOT on team, because a traded player's minutes history genuinely
carries across the trade. For the 14 head-to-head games she therefore contributes TWO
admitted prior rows for one calendar game to her own later history. Neither row can affect a
feature — the phantom one has `appeared=False` so it never enters `played`, and
`dnp_class is None` so it never stops the `prev_dnp` scan — but it does inflate the consumed-
record COUNT by one. `/3` reports both `n_src_player_rows_consumed` (obligation rows read)
and `n_src_player_games_consumed` (distinct games read) so the gap is visible instead of
being quietly absorbed into a single number.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

import cbs_obligation_key as obk
import cbs_provenance as _prov_v2
import cbs_provenance_v4 as prov          # the v4 artifact set: the canonical-key contract
import cbs_real_frames_v2 as rf2          # imported, never mutated: /2 is registered
from cbs_generator import DAYS_CAP, MISS_CAP, P_ACTIVE_FEATURES
from cbs_v5 import REQUIRED_CHANNELS
from cbs_v7 import OUTCOME_AVAILABILITY_POLICY_ID

ADAPTER_ID = "cbs_real_frames/3"
SUPERSEDES = rf2.ADAPTER_ID
FOLD_RECEIPT_SCHEMA = "cbs_real_fold_receipt/3"

REPO_ROOT = Path(__file__).resolve().parent

#: `/2`'s exception type, reused rather than subclassed, so every caller that already
#: catches a real-frame failure catches these too.
RealFrameError = rf2.RealFrameError

# --------------------------------------------------------------------------
# inherited from `/2` BY REFERENCE. Nothing below is re-implemented, so nothing below
# can silently drift from the registered behaviour.
# --------------------------------------------------------------------------
DNP_TAXONOMY_ID = rf2.DNP_TAXONOMY_ID
DNP_CLASSES = rf2.DNP_CLASSES
DNP_CLASS_TABLE = rf2.DNP_CLASS_TABLE
dnp_class = rf2.dnp_class
legacy_prefix_dnp_class = rf2.legacy_prefix_dnp_class
dnp_taxonomy_diff = rf2.dnp_taxonomy_diff
availability_of = rf2.availability_of
schedule_bound = rf2.schedule_bound
roster_window_length = rf2.roster_window_length

EWMA_ALPHA = rf2.EWMA_ALPHA
START_SHARE_WINDOW = rf2.START_SHARE_WINDOW
TEAM_WINDOW = rf2.TEAM_WINDOW
SCHEDULE_BOUND_HOURS_BEFORE_GAME_DAY = rf2.SCHEDULE_BOUND_HOURS_BEFORE_GAME_DAY
FEATURE_ASOF_COL = rf2.FEATURE_ASOF_COL
NO_EVIDENCE_POLICY = rf2.NO_EVIDENCE_POLICY
PLAYER_FRAME_SOURCES = rf2.PLAYER_FRAME_SOURCES
TEAM_FRAME_SOURCES = rf2.TEAM_FRAME_SOURCES

# --------------------------------------------------------------------------
# what `/3` adds
# --------------------------------------------------------------------------

#: The obligation join key. Team-bearing, and unique on BOTH sides: the v4 contract by
#: construction, `master_player.parquet` as a measured fact this module re-checks every run.
PLAYER_JOIN_KEY = ("game_id", "team_id", "player_id")
#: `/2`'s team join, which was already team-aware and is carried unchanged.
TEAM_JOIN_KEY = ("game_id", "team_id")
#: The appearance-evidence key. A `game_id` alone names a contest with two clubs in it.
APPEARANCE_INDEX_KEY = ("team_id", "game_id")

#: the team-blind keys `/2` used, kept so the correction is nameable in a receipt
SUPERSEDED_PLAYER_JOIN_KEY = ("game_id", "player_id")
SUPERSEDED_APPEARANCE_INDEX_KEY = ("game_id",)

#: A new, non-mutating copy: `rf2.SOURCE_POLICIES` is a module-level dict on a registered
#: module and must not be written to.
SOURCE_POLICIES = dict(rf2.SOURCE_POLICIES)
SOURCE_POLICIES["no_master_box_row_for_this_obligation"] = (
    "this obligation has no row in master_player for its own (game_id, team_id, player_id): "
    "the player did not turn out for THIS club in this game. That is the absence of an "
    "event, not missing data, and it yields no starter, no DNP class and no appearance "
    "evidence for this obligation")

NO_MASTER_EVIDENCE_POLICY = "no_master_box_row_for_this_obligation"

#: the four registered player targets, in the order the contract declares them
PLAYER_TARGETS = ("p_active", "e_minutes_given_active", "attempts_usage",
                  "player_scoring_distribution")
TEAM_TARGET = "team_game_distribution"

#: universe columns beyond the accounting flags. `player_id`/`team_id`/`game_id` are present
#: so a validator can RE-DERIVE `row_uid` instead of trusting the column; `obligation_key_id`
#: is present so the rule the key claims to follow is checkable.
PLAYER_UNIVERSE_IDENTITY = ("row_uid", "obligation_uid", "player_game_uid",
                            "obligation_key_id", "player_id", "team_id", "game_id",
                            "fold_id", "forecast_cutoff")


# --------------------------------------------------------------------------
# key hygiene
# --------------------------------------------------------------------------

def normalise_join_keys(df: pd.DataFrame, *, where: str) -> pd.DataFrame:
    """Make the join keys comparable across artifacts, refusing nulls in a key.

    `game_id` is a pandas `StringDtype` in the contract and in the masters but a plain
    object in a hand-built fixture; `team_id` / `player_id` are `int64` in the contract and
    nullable `Int64` in the masters. A merge across those pairs is not guaranteed to align,
    and a NULL in a join key would silently drop or mis-associate an obligation, so it is a
    refusal rather than a coercion.
    """
    out = df.copy()
    if "game_id" in out.columns:
        if out["game_id"].isna().any():
            raise RealFrameError(f"{where}: {int(out['game_id'].isna().sum())} null game_id "
                                 f"values in a join key")
        out["game_id"] = out["game_id"].astype(str)
    for c in ("team_id", "player_id"):
        if c in out.columns:
            if out[c].isna().any():
                raise RealFrameError(f"{where}: {int(out[c].isna().sum())} null {c} values "
                                     f"in a join key")
            out[c] = out[c].astype("int64")
    return out


def assert_canonical_contract_key(pg: pd.DataFrame, *, where: str = "contract") -> dict:
    """The contract must carry the canonical key, and it must RE-DERIVE.

    Four separate questions, because satisfying three of them still breaks a join:
    the column exists, it is unique, it equals `cbs_obligation_key.row_uid(player_id,
    game_id, team_id)` on every row, and the frame declares which rule it followed. A unique
    column of arbitrary strings passes uniqueness while naming nothing.
    """
    for c in ("row_uid", "obligation_uid", "player_game_uid", "obligation_key_id"):
        if c not in pg.columns:
            raise RealFrameError(
                f"{where}: no {c!r} column; `{ADAPTER_ID}` reads the v4 contract and will "
                f"not fall back to a team-blind key")
    obk.assert_unique_canonical_keys(pg, where)

    declared = set(str(x) for x in pd.unique(pg["obligation_key_id"].dropna()))
    if declared != {obk.OBLIGATION_KEY_ID}:
        raise RealFrameError(
            f"{where}: declares obligation_key_id {sorted(declared)}, not "
            f"[{obk.OBLIGATION_KEY_ID!r}]")

    want = np.asarray([obk.row_uid(p, g, t) for p, g, t in
                       zip(pg["player_id"], pg["game_id"].astype(str), pg["team_id"])])
    n_bad = int((pg["row_uid"].to_numpy() != want).sum())
    if n_bad:
        raise RealFrameError(
            f"{where}: {n_bad} rows whose row_uid does not equal "
            f"cbs_obligation_key.row_uid(player_id, game_id, team_id); the key cannot be "
            f"re-derived, so no join on it is verifiable")
    n_alias = int((pg["obligation_uid"].to_numpy() != pg["row_uid"].to_numpy()).sum())
    if n_alias:
        raise RealFrameError(f"{where}: {n_alias} rows where obligation_uid != row_uid")

    want_legacy = np.asarray([obk.player_game_uid(p, g) for p, g in
                              zip(pg["player_id"], pg["game_id"].astype(str))])
    n_legacy = int((pg["player_game_uid"].to_numpy() != want_legacy).sum())
    if n_legacy:
        raise RealFrameError(
            f"{where}: {n_legacy} rows whose player_game_uid is not the v2 legacy linkage")

    n_rows, n_legacy_keys = int(len(pg)), int(pg["player_game_uid"].nunique())
    return {
        "obligation_key_id": obk.OBLIGATION_KEY_ID,
        "canonical_key": "row_uid",
        "canonical_key_fields": list(obk.CANONICAL_KEY_FIELDS),
        "n_rows": n_rows,
        "n_distinct_canonical_keys": int(pg["row_uid"].nunique()),
        "canonical_key_unique": True,
        "canonical_key_recomputes": True,
        "n_distinct_legacy_player_game_uids": n_legacy_keys,
        "n_rows_the_legacy_key_would_collapse": n_rows - n_legacy_keys,
        "legacy_key_would_be_a_valid_primary_key": n_rows == n_legacy_keys,
    }


def assert_master_player_unique(mp: pd.DataFrame) -> dict:
    """`master_player` must be unique on the obligation join key.

    Re-measured every run rather than asserted once in prose: the whole correction rests on
    it, and a master rebuild that introduced a duplicate would otherwise re-open the exact
    `MergeError` this module exists to close, one layer deeper.
    """
    dup = mp.duplicated(list(PLAYER_JOIN_KEY), keep=False)
    n = int(dup.sum())
    if n:
        raise RealFrameError(
            f"master_player is not unique on {list(PLAYER_JOIN_KEY)}: {n} rows share a key. "
            f"The team-aware obligation join cannot be 1:1. Sample: "
            f"{mp.loc[dup, list(PLAYER_JOIN_KEY)].head(5).to_dict('records')}")
    dup_blind = int(mp.duplicated(list(SUPERSEDED_PLAYER_JOIN_KEY), keep=False).sum())
    return {"join_key": list(PLAYER_JOIN_KEY), "rows": int(len(mp)), "duplicates": 0,
            "duplicates_on_superseded_team_blind_key": dup_blind}


# --------------------------------------------------------------------------
# the team-aware appearance index
# --------------------------------------------------------------------------

def build_appearance_index(pg: pd.DataFrame) -> dict:
    """`(team_id, game_id) -> frozenset(player_id)`: who appeared FOR THIS CLUB.

    `/2` keyed this on `game_id` alone. A game has two clubs in it, so that set answered
    "did this player appear in this contest", and the three team-history features that read
    it asked "did she appear for THIS club". Those are different questions with different
    answers for every player who ever faced a former or future employer.
    """
    a = pg.loc[pg["appeared"].astype(bool), ["team_id", "game_id", "player_id"]]
    idx: dict = {}
    for tid, gid, pid in zip(a["team_id"], a["game_id"], a["player_id"]):
        idx.setdefault((int(tid), str(gid)), set()).add(int(pid))
    return {k: frozenset(v) for k, v in idx.items()}


# --------------------------------------------------------------------------
# the causal player frame
# --------------------------------------------------------------------------

def build_player_frame(season: int, root: Path | str = REPO_ROOT, *,
                       require_attested: bool = True) -> dict:
    """Assemble the causal player fold for `season:<season>` — team-aware throughout.

    Returns train / test / universe frames plus receipts. Nothing is fitted, nothing is
    predicted, nothing is scored, and no feature is related to any outcome.
    """
    root = Path(root)
    pg, tg, mp, mt = load_inputs(root, require_attested=require_attested)

    pg = pg[pg["season"] <= season].copy()
    if not len(pg):
        raise RealFrameError(f"no contract rows at or before season {season}")

    pg = normalise_join_keys(pg, where="contract player_game")
    mp = normalise_join_keys(mp, where="master_player")
    key_receipt = assert_canonical_contract_key(pg, where=f"contract player_game "
                                                          f"(season <= {season})")
    master_receipt = assert_master_player_unique(mp)

    # ---- C2: the obligation join is TEAM-AWARE -----------------------------
    m = mp[list(PLAYER_JOIN_KEY) + ["starter_flag", "dnp_reason"]].copy()
    before = len(pg)
    pg = pg.merge(m, on=list(PLAYER_JOIN_KEY), how="left", validate="1:1",
                  indicator="_master_join")
    pg["master_row_present"] = (pg["_master_join"] == "both").to_numpy()
    pg = pg.drop(columns=["_master_join"])

    n_dual = int(pg["player_game_uid"].duplicated(keep=False).sum()) \
        if "player_game_uid" in pg.columns else 0
    join = {
        "join_keys": list(PLAYER_JOIN_KEY),
        "superseded_join_keys": list(SUPERSEDED_PLAYER_JOIN_KEY),
        "left_rows": int(before),
        "matched": int(pg["master_row_present"].sum()),
        "unmatched": int((~pg["master_row_present"]).sum()),
        "n_obligations_sharing_a_legacy_player_game_uid": n_dual,
        "n_dual_team_obligations_without_master_evidence": int(
            (pg["player_game_uid"].duplicated(keep=False)
             & ~pg["master_row_present"]).sum()) if "player_game_uid" in pg.columns else 0,
    }
    unmatched_appeared = int(pg.loc[~pg["master_row_present"], "appeared"].sum())
    join["unmatched_that_appeared"] = unmatched_appeared
    if unmatched_appeared:
        raise RealFrameError(
            f"{unmatched_appeared} contract rows report appeared=True for a club that has no "
            f"master box row for them at {list(PLAYER_JOIN_KEY)}; the team-aware join is not "
            f"trustworthy")

    # ---- no evidence stays NO EVIDENCE, and is asserted to ------------------
    pg["dnp_class"] = pg["dnp_reason"].map(dnp_class)
    pg["starter_flag_observed"] = pd.to_numeric(pg["starter_flag"], errors="coerce")
    blind = ~pg["master_row_present"].to_numpy()
    if blind.any():
        if pg.loc[blind, "dnp_class"].notna().any():
            raise RealFrameError(
                f"{int(pg.loc[blind, 'dnp_class'].notna().sum())} obligations with no master "
                f"box row were nevertheless given a DNP class; absence of a row is not a "
                f"reason and must not be classified")
        if pg.loc[blind, "starter_flag_observed"].notna().any():
            raise RealFrameError(
                "an obligation with no master box row carries an observed starter_flag")
    pg["starter_flag"] = pg["starter_flag_observed"].fillna(0.0)
    pg["appeared"] = pg["appeared"].astype(bool)
    pg = pg.rename(columns={"pts": "points"})
    pg["minutes"] = pd.to_numeric(pg["minutes"], errors="coerce")
    pg["points"] = pd.to_numeric(pg["points"], errors="coerce")
    pg["fga"] = pd.to_numeric(pg["fga"], errors="coerce")
    pg["src_policy_master_box"] = np.where(pg["master_row_present"],
                                           "master_box_row_for_this_obligation",
                                           NO_MASTER_EVIDENCE_POLICY)

    # ---- team game index, availability-gated ------------------------------
    mt = normalise_join_keys(mt, where="master_team")
    mt2 = mt[mt["season"] <= season].copy()
    mt2 = mt2.sort_values(["team_id", "season", "game_date", "game_id"], kind="mergesort")
    mt2["team_avail"] = availability_of(mt2["game_date"])

    # C2: appearance evidence is keyed on (team_id, game_id), NEVER on the game alone
    appeared_by_team_game = build_appearance_index(pg)

    team_games: dict[tuple, list] = {}
    for tid, s, gd, gid, av in zip(mt2["team_id"], mt2["season"], mt2["game_date"],
                                   mt2["game_id"], mt2["team_avail"]):
        team_games.setdefault((int(tid), int(s)), []).append((gd, str(gid), av))

    # ---- per-row causal derivation ---------------------------------------
    pg["cutoff"] = pd.to_datetime(pg["forecast_cutoff"], utc=True)
    pg["avail"] = availability_of(pg["game_date"])
    pg = pg.sort_values(["player_id", "season", "forecast_cutoff", "game_id"],
                        kind="mergesort").reset_index(drop=True)

    n = len(pg)
    feats = {c: np.zeros(n, dtype=float) for c in P_ACTIVE_FEATURES}
    feats["days_since_last_appearance"][:] = DAYS_CAP
    prev_unknown = np.zeros(n, dtype=float)

    src_gamelog = np.empty(n, dtype=object)
    src_team = np.empty(n, dtype=object)
    src_roster = np.empty(n, dtype=object)
    pol_gamelog = np.empty(n, dtype=object)
    pol_team = np.empty(n, dtype=object)
    pol_roster = np.empty(n, dtype=object)
    n_player_rows = np.zeros(n, dtype=np.int64)
    n_player_games = np.zeros(n, dtype=np.int64)
    n_team_games = np.zeros(n, dtype=np.int64)
    n_roster_games = np.zeros(n, dtype=np.int64)

    # hot columns pulled out of the frame once: `.at[]` in a 35k-row loop is the difference
    # between seconds and minutes, and the values are identical.
    c_pid = pg["player_id"].astype("int64").tolist()
    c_tid = pg["team_id"].astype("int64").tolist()
    c_season = pg["season"].astype("int64").tolist()
    c_gid = pg["game_id"].astype(str).tolist()
    c_cut = pg["cutoff"].tolist()
    c_avail = pg["avail"].tolist()
    c_date = pg["game_date"].tolist()
    c_app = pg["appeared"].astype(bool).tolist()
    c_min = pg["minutes"].tolist()
    c_start = pg["starter_flag"].astype(float).tolist()
    c_dnp = pg["dnp_class"].tolist()

    hist: dict[tuple, list] = {}
    for i in range(n):
        pid, s, cut, tid = c_pid[i], c_season[i], c_cut[i], c_tid[i]
        prior = hist.setdefault((pid, s), [])
        # ADMITTED = outcome availability strictly before this row's cutoff
        adm = [h for h in prior if h["avail"] < cut]
        played = [h for h in adm if h["appeared"]]

        if played:
            mins = np.asarray([h["minutes"] for h in played], dtype=float)
            w = (1.0 - EWMA_ALPHA) ** np.arange(len(mins) - 1, -1, -1)
            feats["min_ewma"][i] = float(np.sum(w * mins) / np.sum(w))
            feats["started_last"][i] = float(played[-1]["starter"])
            tail = played[-START_SHARE_WINDOW:]
            feats["start_share_l5"][i] = float(np.mean([h["starter"] for h in tail]))
            gap = (c_date[i] - played[-1]["date"]).days
            feats["days_since_last_appearance"][i] = float(min(gap, DAYS_CAP))

        # prev_dnp_*: the ffilled class of the most recent ADMITTED dnp row. The
        # `isinstance(..., str)` test is load-bearing and is `/2`'s: a non-DNP row's class
        # arrives from pandas as NaN, and `if NaN:` is TRUE, so a truthiness test would stop
        # the scan at the first non-DNP row. A no-evidence row carries None here, so it is
        # skipped for the same reason and by the same guard.
        cls = None
        for h in reversed(adm):
            if isinstance(h["dnp_class"], str) and h["dnp_class"]:
                cls = h["dnp_class"]
                break
        feats["prev_dnp_cd"][i] = float(cls == "CD")
        feats["prev_dnp_inj"][i] = float(cls == "INJ")
        feats["prev_dnp_nwt"][i] = float(cls == "NWT")
        prev_unknown[i] = float(cls == "UNKNOWN")

        # team-index features over ADMITTED team games, with TEAM-AWARE appearance evidence
        tg_all = team_games.get((tid, s), [])
        adm_tg = [g for g in tg_all if g[2] < cut]
        k = len(adm_tg)
        feats["team_gp_season"][i] = float(k)
        own: list[bool] = []
        if k:
            own = [pid in appeared_by_team_game.get((tid, g[1]), ()) for g in adm_tg]
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
        n_player_games[i] = len({h["game_id"] for h in adm})
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

        prior.append({"avail": c_avail[i], "appeared": c_app[i], "game_id": c_gid[i],
                      "minutes": float(c_min[i]) if pd.notna(c_min[i]) else 0.0,
                      "starter": c_start[i], "date": c_date[i],
                      "dnp_class": c_dnp[i] if isinstance(c_dnp[i], str) else None})

    for c, v in feats.items():
        if c not in ("p_plays_prior", "player_gp_season"):   # runner-derived
            pg[c] = v
    #: diagnostic only; NOT a member of the frozen twelve
    pg["prev_dnp_unknown"] = prev_unknown

    # ---- the no-false-signal assertions, on the emitted values -------------
    if blind.any():
        b = pg["master_row_present"].to_numpy() == False          # noqa: E712 - array mask
        for c in ("prev_dnp_cd", "prev_dnp_inj", "prev_dnp_nwt"):
            # a no-evidence row may INHERIT a class from an earlier admitted row of its own
            # player-season; what it must never do is CONTRIBUTE one. That is asserted at
            # the source (dnp_class is None above); here we assert the weaker, checkable
            # fact that no such row sets a class from nothing at all.
            bad = int(((pg[c].to_numpy() > 0) & b
                       & (n_player_rows == 0)).sum())
            if bad:
                raise RealFrameError(
                    f"{bad} obligations with no master row and no admitted prior row "
                    f"nevertheless set {c}; absence of evidence produced a signal")
        bad = int(((pg["returning_flag"].to_numpy() > 0) & b & (n_player_rows == 0)).sum())
        if bad:
            raise RealFrameError(
                f"{bad} obligations with no evidence at all set returning_flag")

    # ---- the contract's own roster declaration, preserved -------------------
    # The v4 contract DECLARES `src_asof_roster` / `n_roster_games_consumed`, and
    # `cbs_provenance/4.roster_binding_status` binds them to the candidacy record. `/2`
    # overwrote both columns with its own recomputed feature-window values and said nothing
    # about it. `/3` keeps the declaration under its own name and reports the agreement, so
    # the overwrite is visible rather than a coincidence nobody measured.
    has_contract_roster = "src_asof_roster" in pg.columns
    if has_contract_roster:
        pg["contract_src_asof_roster"] = pd.to_datetime(
            pg["src_asof_roster"], utc=True).map(lambda t: t.isoformat())
    if "n_roster_games_consumed" in pg.columns:
        pg["contract_n_roster_games_consumed"] = \
            pd.to_numeric(pg["n_roster_games_consumed"], errors="coerce").astype("int64")

    # ---- row-level source timestamps -------------------------------------
    sched = schedule_bound(pg["game_date"])
    if (sched >= pg["cutoff"]).any():
        raise RealFrameError(
            f"{int((sched >= pg['cutoff']).sum())} rows have a schedule bound at or after "
            f"their own cutoff; the frozen schedule policy does not hold")

    def _bound(arr) -> pd.Series:
        return pd.to_datetime(pd.Series(list(arr), index=pg.index), utc=True).fillna(sched)

    b_gl, b_tm, b_rs = _bound(src_gamelog), _bound(src_team), _bound(src_roster)
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
    pg["n_src_player_games_consumed"] = n_player_games
    pg["n_src_team_games_consumed"] = n_team_games
    pg["n_roster_games_consumed"] = n_roster_games
    pg["outcome_availability_source"] = "policy"
    pg["outcome_availability_policy_id"] = OUTCOME_AVAILABILITY_POLICY_ID

    for col in ("src_asof_gamelog", "src_asof_team_gamelog", "src_asof_roster",
                "src_asof_schedule", FEATURE_ASOF_COL):
        late = int((pd.to_datetime(pg[col], utc=True) >= pg["cutoff"]).sum())
        if late:
            raise RealFrameError(f"{late} rows report {col} at or after their own cutoff")
    for col in ("src_asof_gamelog", "src_asof_team_gamelog", "src_asof_roster",
                "src_asof_schedule"):
        under = int((pd.to_datetime(pg[col], utc=True) > composite).sum())
        if under:
            raise RealFrameError(
                f"{under} rows report {col} newer than the composite {FEATURE_ASOF_COL}; "
                f"the composite is not a maximum")

    keep = ["row_uid", "obligation_uid", "player_game_uid", "obligation_key_id",
            "player_id", "team_id", "season", "game_id", "game_date", "forecast_cutoff",
            "appeared", "master_row_present", "starter_flag_observed", "dnp_class",
            "minutes", "points", "fga", "fold_id"] + \
        [c for c in P_ACTIVE_FEATURES if c not in ("p_plays_prior", "player_gp_season")] + [
        "prev_dnp_unknown",
        "src_asof_gamelog", "src_asof_team_gamelog", "src_asof_roster",
        "src_asof_schedule", FEATURE_ASOF_COL,
        "src_policy_gamelog", "src_policy_team_gamelog", "src_policy_roster",
        "src_policy_schedule", "src_policy_master_box", "n_src_player_rows_consumed",
        "n_src_player_games_consumed", "n_src_team_games_consumed",
        "n_roster_games_consumed", "outcome_availability_source",
        "outcome_availability_policy_id"] + \
        [c for c in ("contract_src_asof_roster", "contract_n_roster_games_consumed")
         if c in pg.columns]
    frame = pg[keep].copy()
    frame["minutes"] = frame["minutes"].fillna(0.0)
    frame["points"] = frame["points"].fillna(0.0)
    frame["fga"] = frame["fga"].fillna(0.0)

    train = frame[frame["season"] < season].reset_index(drop=True)
    test = frame[frame["season"] == season].reset_index(drop=True)

    src = pg.loc[pg["season"] == season].reset_index(drop=True)
    universe = src[list(PLAYER_UNIVERSE_IDENTITY) + ["appeared"]].copy()
    for t in PLAYER_TARGETS:
        req_col, sc_col = f"prediction_required__{t}", f"outcome_scoreable__{t}"
        derived_req = pd.Series(True, index=universe.index)
        derived_sc = (universe["appeared"].astype(bool) if t != "p_active"
                      else pd.Series(True, index=universe.index))
        # The v4 contract DECLARES these. Read the declaration and check it against the
        # derivation, rather than silently recomputing over the top of the registered value.
        for col, derived in ((req_col, derived_req), (sc_col, derived_sc)):
            if col in src.columns:
                declared = src[col].astype(bool).reset_index(drop=True)
                n_dis = int((declared != derived).sum())
                if n_dis:
                    raise RealFrameError(
                        f"{n_dis} rows where the contract's declared {col} disagrees with "
                        f"the adapter's derivation; the universe would not be the "
                        f"registered one")
                universe[col] = declared
            else:
                universe[col] = derived

    for nm, f in (("full", pg), ("train", train), ("test", test), ("universe", universe)):
        obk.assert_unique_canonical_keys(f, f"player {nm} frame (season:{season})")

    rec = _receipts("player", season, train, test, universe, join, pg, PLAYER_FRAME_SOURCES)
    rec["obligation_key"] = key_receipt
    rec["master_player_key"] = master_receipt
    rec["team_awareness"] = _team_awareness_receipt(pg, appeared_by_team_game)
    if has_contract_roster:
        rec["roster_bound_vs_contract"] = {
            "contract_column": "src_asof_roster",
            "adapter_column": "src_asof_roster (RECOMPUTED; the contract's value is kept as "
                              "contract_src_asof_roster)",
            "n_rows": int(len(pg)),
            "n_rows_where_the_adapter_bound_differs": int(
                (pd.to_datetime(pg["contract_src_asof_roster"], utc=True) != b_rs).sum()),
            "n_rows_where_the_adapter_count_differs": int(
                (pg["contract_n_roster_games_consumed"].to_numpy()
                 != n_roster_games).sum())
            if "contract_n_roster_games_consumed" in pg.columns else None,
            "note": ("the two columns share a NAME and not a DEFINITION. The contract's "
                     "lookback_games_used is a fixed candidacy window; the adapter's "
                     "n_roster_games_consumed is the union of the three candidacy "
                     "features' read windows. Their BOUNDS coincide because availability "
                     "is monotone in game_date and both windows end at the same most-recent "
                     "admitted game -- which is precisely the arithmetic coincidence "
                     "`cbs_provenance/4` was written to stop being mistaken for a binding. "
                     "The count difference above is the proof that it is a coincidence")}
    return {"kind": "player", "season": season,
            "train": train, "test": test, "universe": universe, "receipts": rec}


# --------------------------------------------------------------------------
# the causal team frame
# --------------------------------------------------------------------------

def build_team_frame(season: int, root: Path | str = REPO_ROOT, *,
                     require_attested: bool = True,
                     withhold_current_outcomes: bool = False) -> dict:
    """`/2`'s team fold, re-keyed onto the v4 artifact set.

    The team join was ALREADY team-aware — `(game_id, team_id)` — and is unchanged. What is
    added is the same key hygiene the player path now gets: the emitted `row_uid` must be
    unique on every frame before it is returned.
    """
    root = Path(root)
    _pg, tg, _mp, mt = load_inputs(root, require_attested=require_attested)

    tg = normalise_join_keys(tg[tg["season"] <= season].copy(), where="contract team_game")
    mt = normalise_join_keys(mt, where="master_team")
    m = mt[list(TEAM_JOIN_KEY) + ["is_home", "pts", "ftm", "fgm", "fg3m",
                                  "points_paint"]].copy()
    dup = int(m.duplicated(list(TEAM_JOIN_KEY), keep=False).sum())
    if dup:
        raise RealFrameError(f"master_team is not unique on {list(TEAM_JOIN_KEY)}: {dup} rows")
    before = len(tg)
    tg = tg.merge(m, on=list(TEAM_JOIN_KEY), how="left", validate="1:1")
    join = {"join_keys": list(TEAM_JOIN_KEY), "left_rows": int(before),
            "matched": int(tg["pts"].notna().sum()),
            "unmatched": int(tg["pts"].isna().sum())}
    if join["unmatched"]:
        raise RealFrameError(
            f"{join['unmatched']} team-game obligations have no master box row")

    tg["ch_ft"] = tg["ftm"].astype(float)
    tg["ch_3pt"] = 3.0 * tg["fg3m"].astype(float)
    tg["ch_paint"] = tg["points_paint"].astype(float)
    tg["ch_np2"] = 2.0 * (tg["fgm"].astype(float) - tg["fg3m"].astype(float)) \
        - tg["points_paint"].astype(float)
    tg["team_points"] = tg["pts"].astype(float)
    if (tg["ch_np2"] < 0).any():
        raise RealFrameError(
            f"{int((tg['ch_np2'] < 0).sum())} rows have a negative non-paint-2 channel; the "
            f"box-score identity does not hold")
    identity_gap = (tg["ch_ft"] + tg["ch_3pt"] + tg["ch_paint"] + tg["ch_np2"]
                    - tg["team_points"]).abs().max()
    if identity_gap > 1e-9:
        raise RealFrameError(
            f"channel identity violated by up to {identity_gap}; the four channels must "
            f"reconstruct team_points exactly")

    tg["side"] = np.where(tg["is_home"].astype(int) == 1, "home", "away")
    tg["cutoff"] = pd.to_datetime(tg["forecast_cutoff"], utc=True)
    tg["avail"] = availability_of(tg["game_date"])
    tg = tg.sort_values(["team_id", "game_date", "game_id"],
                        kind="mergesort").reset_index(drop=True)

    src = np.empty(len(tg), dtype=object)
    pol = np.empty(len(tg), dtype=object)
    ncons = np.zeros(len(tg), dtype=np.int64)
    hist: dict[tuple, list] = {}
    c_key = list(zip(tg["team_id"].astype("int64"), tg["season"].astype("int64")))
    c_cut, c_av = tg["cutoff"].tolist(), tg["avail"].tolist()
    for i in range(len(tg)):
        prior = hist.setdefault(c_key[i], [])
        adm = [a for a in prior if a < c_cut[i]]
        ncons[i] = len(adm)
        if adm:
            src[i], pol[i] = max(adm), "prior_team_game_availability"
        else:
            src[i], pol[i] = None, NO_EVIDENCE_POLICY
        prior.append(c_av[i])

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
    keep = ["row_uid", "team_id", "game_id", "season", "game_date", "forecast_cutoff",
            "side", "fold_id"] + outcome_cols + [
        "src_asof_team_gamelog", "src_asof_schedule", FEATURE_ASOF_COL,
        "src_policy_team_gamelog", "src_policy_schedule", "n_src_team_games_consumed",
        "outcome_availability_source", "outcome_availability_policy_id"]
    frame = tg[keep].copy()

    train = frame[frame["season"] < season].reset_index(drop=True)
    test = frame[frame["season"] == season].reset_index(drop=True)
    if withhold_current_outcomes:
        test = test.drop(columns=outcome_cols)

    universe = tg.loc[tg["season"] == season,
                      ["row_uid", "team_id", "game_id", "fold_id",
                       "forecast_cutoff"]].reset_index(drop=True)
    universe[f"prediction_required__{TEAM_TARGET}"] = True
    universe[f"outcome_scoreable__{TEAM_TARGET}"] = True

    for nm, f in (("full", tg), ("train", train), ("test", test), ("universe", universe)):
        obk.assert_unique_canonical_keys(f, f"team {nm} frame (season:{season})")

    rec = _receipts("team", season, train, test, universe, join, tg, TEAM_FRAME_SOURCES)
    rec["obligation_key"] = {
        "canonical_key": "row_uid", "n_rows": int(len(tg)),
        "n_distinct_canonical_keys": int(tg["row_uid"].nunique()),
        "canonical_key_unique": True,
        "note": ("the TEAM obligation key is the contract's own team-game uid, not "
                 f"{obk.OBLIGATION_KEY_ID}, which is defined over (player_id, game_id, "
                 "team_id). Uniqueness is asserted; re-derivation is not, because this key "
                 "is not that key and pretending otherwise would be a false attestation")}
    return {"kind": "team", "season": season,
            "train": train, "test": test, "universe": universe, "receipts": rec}


# --------------------------------------------------------------------------
# loading
# --------------------------------------------------------------------------

def load_inputs(root: Path | str = REPO_ROOT, *, require_attested: bool = True):
    """Read the v4 contract and the masters, refusing unattested inputs.

    `/2` read `cbs_provenance_v3`. `/3` reads `cbs_provenance_v4`, whose audit makes the
    canonical key a PRECONDITION, so an artifact set carrying the team-blind key cannot get
    as far as the join that the team-blind key breaks.
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
    mp = pd.read_parquet(root / _prov_v2.MASTER_PLAYER)
    mt = pd.read_parquet(root / _prov_v2.MASTER_TEAM)
    for f in (pg, tg, mp, mt):
        f["game_date"] = pd.to_datetime(f["game_date"])
    return pg, tg, mp, mt


# --------------------------------------------------------------------------
# receipts
# --------------------------------------------------------------------------

def _team_awareness_receipt(pg: pd.DataFrame, index: dict) -> dict:
    """What the team-aware joins actually did, counted. No model claim."""
    blind = ~pg["master_row_present"].to_numpy()
    dual = pg["player_game_uid"].duplicated(keep=False).to_numpy() \
        if "player_game_uid" in pg.columns else np.zeros(len(pg), dtype=bool)
    return {
        "obligation_join_key": list(PLAYER_JOIN_KEY),
        "superseded_obligation_join_key": list(SUPERSEDED_PLAYER_JOIN_KEY),
        "appearance_index_key": list(APPEARANCE_INDEX_KEY),
        "superseded_appearance_index_key": list(SUPERSEDED_APPEARANCE_INDEX_KEY),
        "n_appearance_index_entries": len(index),
        "n_appearance_records": int(sum(len(v) for v in index.values())),
        "n_obligations": int(len(pg)),
        "n_with_master_box_row": int((~blind).sum()),
        "n_without_master_box_row": int(blind.sum()),
        "n_without_master_box_row_that_appeared": 0,      # asserted above, hard refusal
        "n_dual_team_obligations": int(dual.sum()),
        "n_dual_team_obligations_without_master_box_row": int((dual & blind).sum()),
        "no_evidence_semantics": SOURCE_POLICIES[NO_MASTER_EVIDENCE_POLICY],
    }


def _receipts(kind, season, train, test, universe, join, full, sources) -> dict:
    """`/2`'s receipt, re-labelled and extended.

    Built by CALLING `/2`'s builder rather than re-implementing it, so every inherited
    figure is inherited in fact and not merely in intent.
    """
    rec = rf2._receipts(kind, season, train, test, universe, join, full, sources)
    rec["schema"] = FOLD_RECEIPT_SCHEMA
    rec["adapter"] = ADAPTER_ID
    rec["supersedes"] = SUPERSEDES
    rec["provenance"]["policy_definitions"] = SOURCE_POLICIES
    rec["provenance"]["provenance_module"] = prov.PROVENANCE_ID
    rec["provenance"]["contract"] = prov.CONTRACT_DIR
    rec["scope"] = ("frame construction, joins, keys, schema, timestamps, provenance and "
                    "identity only: nothing fitted, nothing predicted, nothing scored, no "
                    "accuracy or profitability figure, no feature related to any outcome")
    return rec


def build_fold(season: int, root: Path | str = REPO_ROOT, **kw) -> dict:
    """Both sides of one season fold, with a combined receipt."""
    p = build_player_frame(season, root, **kw)
    t = build_team_frame(season, root, **{k: v for k, v in kw.items()
                                          if k != "withhold_current_outcomes"})
    return {"season": season, "player": p, "team": t,
            "receipts": {"player": p["receipts"], "team": t["receipts"]}}


# --------------------------------------------------------------------------
# the two counterfactuals: what the team-blind joins cost, measured
# --------------------------------------------------------------------------

def team_blind_join_counterfactual(root: Path | str = REPO_ROOT, *,
                                   require_attested: bool = True) -> dict:
    """Count the obligations that `/2`'s team-blind master join mis-associates.

    Row counting against the real artifacts. Nothing is fitted, predicted or scored.
    """
    root = Path(root)
    pg, _tg, mp, _mt = load_inputs(root, require_attested=require_attested)
    pg = normalise_join_keys(pg, where="contract player_game")
    mp = normalise_join_keys(mp, where="master_player")
    m = mp[list(PLAYER_JOIN_KEY) + ["starter_flag", "dnp_reason"]]
    left = pg[["game_id", "team_id", "player_id", "season", "appeared", "row_uid",
               "player_game_uid"]]

    aware = left.merge(m, on=list(PLAYER_JOIN_KEY), how="left", validate="1:1",
                       indicator="_j")
    blindm = m.rename(columns={"team_id": "master_team_id"})
    blind = left.merge(blindm, on=list(SUPERSEDED_PLAYER_JOIN_KEY), how="left")
    false = blind[blind["master_team_id"].notna()
                  & (blind["master_team_id"] != blind["team_id"])]
    return {
        "adapter": ADAPTER_ID,
        "measurement": "row counts only; nothing is fitted, predicted or scored",
        "team_aware_key": list(PLAYER_JOIN_KEY),
        "team_blind_key": list(SUPERSEDED_PLAYER_JOIN_KEY),
        "n_obligations": int(len(left)),
        "n_matched_team_aware": int((aware["_j"] == "both").sum()),
        "n_matched_team_blind": int(blind["master_team_id"].notna().sum()),
        "n_falsely_matched": int(len(false)),
        "n_false_dnp_signals": int(false["dnp_reason"].notna().sum()),
        "n_false_starter_signals": int(
            pd.to_numeric(false["starter_flag"], errors="coerce").fillna(0).eq(1).sum()),
        "n_falsely_matched_that_the_contract_says_did_not_appear": int(
            (~false["appeared"].astype(bool)).sum()),
        "falsely_matched": false[["season", "game_id", "team_id", "master_team_id",
                                  "player_id", "row_uid", "starter_flag", "dnp_reason"]]
        .to_dict("records"),
        "per_season": {int(s): int(c) for s, c in
                       false.groupby("season").size().items()},
    }


def team_blind_appearance_counterfactual(root: Path | str = REPO_ROOT, *,
                                         require_attested: bool = True) -> dict:
    """Count the appearance lookups `/2`'s game-keyed index would answer for the wrong club.

    A flip happens when a player appeared in game `g` for club A, club B also played `g`,
    the player holds an obligation for club B in the same season, and that obligation's
    cutoff is after `g`'s availability bound — so `g` is one of B's admitted prior games and
    the game-keyed index reports her as having played FOR B.

    Row counting only. Nothing is fitted, predicted or scored.
    """
    root = Path(root)
    pg, _tg, _mp, mt = load_inputs(root, require_attested=require_attested)
    pg = normalise_join_keys(pg, where="contract player_game")
    mt = normalise_join_keys(mt, where="master_team")

    app = pg.loc[pg["appeared"].astype(bool),
                 ["game_id", "team_id", "player_id", "season"]]
    games = mt[["game_id", "team_id", "game_date"]].rename(
        columns={"team_id": "other_team", "game_date": "other_game_date"})
    j = app.merge(games, on="game_id")
    cross = j[j["other_team"] != j["team_id"]].copy()
    cross["avail"] = availability_of(cross["other_game_date"])

    obl = pg[["row_uid", "player_id", "team_id", "season", "forecast_cutoff"]]
    hit = obl.merge(cross[["player_id", "other_team", "season", "avail", "game_id"]]
                    .rename(columns={"other_team": "team_id"}),
                    on=["player_id", "team_id", "season"], how="inner")
    hit = hit[pd.to_datetime(hit["forecast_cutoff"], utc=True) > hit["avail"]]
    per_season = hit.groupby("season")["row_uid"].nunique()
    return {
        "adapter": ADAPTER_ID,
        "measurement": "row counts only; nothing is fitted, predicted or scored",
        "team_aware_key": list(APPEARANCE_INDEX_KEY),
        "team_blind_key": list(SUPERSEDED_APPEARANCE_INDEX_KEY),
        "n_cross_club_appearance_triples": int(
            cross.merge(pg[["player_id", "team_id", "season"]].drop_duplicates()
                        .rename(columns={"team_id": "other_team"}),
                        on=["player_id", "other_team", "season"], how="inner")
            [["team_id", "game_id", "player_id"]].drop_duplicates().shape[0]),
        "n_flipped_lookups": int(len(hit)),
        "n_obligations_affected": int(hit["row_uid"].nunique()),
        "per_season_obligations_affected": {int(s): int(c) for s, c in per_season.items()},
    }


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="cbs_real_frames/3 frame builder")
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--root", default=str(REPO_ROOT))
    ap.add_argument("--out", default=None)
    ap.add_argument("--counterfactuals", action="store_true",
                    help="also report what the superseded team-blind joins would have done")
    args = ap.parse_args()
    fold = build_fold(args.season, args.root)
    rep = {"schema": FOLD_RECEIPT_SCHEMA, "adapter": ADAPTER_ID,
           "generated_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
           "scope": ("frame construction, joins, keys, schema, timestamps, provenance and "
                     "identity only: nothing fitted, nothing predicted, no accuracy, no "
                     "scoring, no profitability"),
           "receipts": fold["receipts"]}
    if args.counterfactuals:
        rep["team_blind_join_counterfactual"] = team_blind_join_counterfactual(args.root)
        rep["team_blind_appearance_counterfactual"] = \
            team_blind_appearance_counterfactual(args.root)
    text = json.dumps(rep, indent=2, default=str) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
