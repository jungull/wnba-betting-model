#!/usr/bin/env python3
"""prediction_contract_v4.py -- one UNIQUE team-bearing obligation key, honestly named.

Registered: prediction_contract_v4.  SUPERSEDES prediction_contract_v3, which is preserved
as a superseded artifact and is neither modified nor deleted here; this producer only READS
v3's files, to prove that the one thing that changed is the thing that was meant to change.

WHAT WAS WRONG WITH v3, conceded in full
    C1 THE KEY COULD NOT NAME THE THING BEING PREDICTED.  v3 correctly restored the dual-team
       obligations v2 had deduplicated away, and then kept v2's TEAM-BLIND
       `row_uid = pg_uid(player_id, game_id)` as the frame's `row_uid` column.  A key that is
       documented as "not unique -- join on obligation_uid" is not a key.  The cost was not
       theoretical: `cbs_real_frames_v2.build_player_frame(2024, require_attested=True)`
       cannot execute at all against the v3 frame --

           MergeError: Merge keys are not unique in left dataset; not a one-to-one merge
           Duplicates in left:
               game_id  player_id
           1022300169    1641653
           1022400175     203824
           ...

       -- so `contract_baseline_suite_v10` shipped a green gate over a path that raises on its
       first real call.  v4 carries ONE canonical key end to end, `cbs_obligation_key.row_uid`
       = `"ob_" + sha256(player_id, game_id, team_id)`, asserted unique before anything is
       emitted, and retains `player_game_uid` (byte-identical to v2's `pg_uid`) as an explicitly
       NON-KEY legacy linkage column.
    C3 THE MEMBERSHIP RULE WAS DESCRIBED AS SOMETHING IT IS NOT.  v3's registered prose says a
       candidate "APPEARED in one of the latest five prior same-season team games" and its
       limitations say "a player who missed the entire admitted window is NOT a candidate".
       The implementation does no such thing: `by_team_players` pools EVERY master box row for
       the window's team-games, including DNP, DND and NWT rows carrying null minutes.  A
       player who was listed and did not play IS a candidate under v3, and 3,189 obligations
       exist only because of it.  v4 KEEPS the behaviour -- it is the defensible recency-roster
       proxy, and narrowing it would delete real obligations -- and RENAMES it to what it is:
       PRIOR ADMITTED TEAM-GAME BOX MEMBERSHIP, INCLUDING DNP ROWS.  The appeared-only
       counterfactual is measured, not asserted, and its count is written into the receipt.
    C4 ROSTER PROVENANCE WAS NOT BOUND TO ANY CANDIDACY RECORD.  Downstream,
       `cbs_real_frames_v2` derives `src_asof_roster` and `n_roster_games_consumed` by
       RECOMPUTING a trailing window over its own team-game index.  Because availability under
       the +36h policy is monotone in game_date, that recomputation lands on the same maximum
       timestamp as the contract's `admitted_window_bound` -- and v9/v10 read the numeric
       coincidence as agreement.  A coincidence is not a binding.  v4 emits `src_asof_roster`,
       `n_roster_games_consumed`, the window's FIRST and LAST admitted game ids and a digest of
       the exact ordered window, all derived FROM the contract's own candidacy record
       (`admitted_window_bound`, `lookback_games_used`), so a consumer binds to the records that
       decided candidacy instead of re-deriving a number that happens to match.
    C5 THE CUTOFF IDENTITY CHECK COMPARED TWO FIELDS OUT OF EIGHT.  v3 refused to emit unless
       `forecast_cutoff` and `cutoff_policy` matched v2's registered `game.parquet`.  Tip
       provenance -- `exact_cutoff_ok`, `scheduled_tip_time`, `tip_time_source`,
       `tip_time_observed_at`, `tip_time_quality`, `tip_revisions_seen` -- was not compared, so
       a run could reproduce the same cutoff from different evidence and pass.  v4 compares all
       EIGHT and FAILS CLOSED on any one of them.

WHAT IS PRESERVED FROM v3, deliberately and unchanged
    * the AVAILABILITY-CAUSAL admission gate itself -- `availability_bound`,
      `verify_availability_policy`, `resolve_sources` and `load_tip_observations` are IMPORTED
      from the frozen v3 module rather than copied, so there is exactly one gate;
    * the cutoff machinery -- `resolve_tip_times` / `apply_cutoff_policy` imported from the
      frozen v2 module, and now proven identical to v2's registered game.parquet on eight
      fields rather than two;
    * the ROW SET.  v4 changes the KEY and the NAMING, not the universe: all 35,627 obligations
      are expected to survive byte-for-byte at (team_id, game_id, player_id) granularity, and
      `row_diff_vs_v3.json` reports any deviation as a DEFECT rather than smoothing it;
    * the season reset, the strict `bound < cutoff` admission, the visibility of every
      zero-candidate team-game, and the rule that the target game's own rows are never read to
      decide membership.

WHAT v4 IS STILL NOT
    Still a RECENCY-ROSTER PROXY and still not the complete slate.  A player absent from every
    box score in the admitted window -- not even listed as a DNP -- is not a candidate; a debut
    cannot be one; the availability bound is a conservative POLICY, not an observation.

THIS MODULE FITS NOTHING, PREDICTS NOTHING AND SCORES NOTHING.  Every value it produces is an
id, a count, a timestamp, a hash or a boolean.
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))

import asof_invariant as ai                                          # noqa: E402
import cbs_obligation_key as obk                                     # noqa: E402
import prediction_contract_v3 as v3                                  # noqa: E402
# Imported, never modified.  Exactly one availability gate exists in this repo and this is it.
from prediction_contract_v3 import (                                 # noqa: E402
    AVAILABILITY_POLICY_ID, AVAILABILITY_POLICY_LAG_HOURS, availability_bound,
    load_tip_observations, resolve_sources, verify_availability_policy,
)
from prediction_contract_v2 import (                                 # noqa: E402
    CUTOFF_MINUTES_BEFORE_TIP, POLICY_DATE_ONLY, POLICY_EXACT, PREDICTION_SCHEMA,
    QUANTILES, TARGETS, apply_cutoff_policy, g_uid, pg_uid, resolve_tip_times, tg_uid,
)

OUT = REPO / "experiments" / "prediction_contract_v4"
V3_OUT = REPO / "experiments" / "prediction_contract_v3"
V2_OUT = REPO / "experiments" / "prediction_contract_v2"
MASTER = REPO / "data" / "masters" / "master_player.parquet"

CONTRACT_VERSION = "player_game_contract/4"
SUPERSEDES = "player_game_contract/3"
SUPERSEDES_REASON = (
    "v3 restored the dual-team obligations but kept v2's TEAM-BLIND row_uid as the frame's "
    "key, so 28 rows share 14 ids and cbs_real_frames_v2.build_player_frame raises MergeError "
    "on its first real call; v3 also registered its candidate membership as 'appeared in a "
    "prior game' when the implementation pools every prior ADMITTED box row INCLUDING DNP "
    "rows; derived roster provenance from a recomputed feature-history window rather than from "
    "the candidacy record; and proved cutoff identity on two fields out of eight.")

ROSTER_LOOKBACK = 5          # ADMITTED team games looked back to establish candidacy

# --------------------------------------------------------------------------- #
# C3: the membership rule, named for what it does
# --------------------------------------------------------------------------- #
#: The REGISTERED membership rule of v4.  Identical in behaviour to v3; honest in name.
MEMBERSHIP_BOX_INCLUDING_DNP = "prior_admitted_team_game_box_membership_including_dnp/1"
#: The counterfactual v3's prose actually described.  MEASURED for the receipt; never emitted.
MEMBERSHIP_APPEARED_ONLY = "prior_admitted_team_game_appearance_only/1"

MEMBERSHIP_RULE = (
    "A candidate for (team, game) is a player who APPEARS AS A ROW IN THE TEAM'S BOX SCORE for "
    "one of the LATEST FIVE PRIOR SAME-SEASON TEAM GAMES WHOSE APPEARANCE SOURCE BOUND IS "
    "STRICTLY EARLIER THAN THE ROW'S FORECAST CUTOFF. BOX MEMBERSHIP, NOT APPEARANCE: a player "
    "listed with a DNP / DND / NWT reason and null minutes IS a member and IS a candidate. "
    "This is deliberate -- being listed in the travelling box score is the best available "
    "recency-roster evidence in this repository, and requiring actual minutes would delete "
    "3,189 real obligations (measured, see appeared_only_counterfactual) whose players were "
    "demonstrably with the club.")

ADMISSION_RULE = (
    "Latest five ADMITTED prior same-season team games, not latest five scheduled. The "
    "appearance source bound is floor_to_day(game_date) + 36 hours (policy id "
    "'postgame_policy_lag_36h_from_game_date_utc/1'), i.e. noon UTC on the day AFTER the game. "
    "Admission is STRICT: a prior game whose bound EQUALS the cutoff is NOT admitted. The "
    "window never crosses a season boundary, so each season's opener has zero admitted prior "
    "games and therefore zero candidates. " + MEMBERSHIP_RULE)

#: What the supervisor's independent reconstruction predicted for the appeared-only
#: counterfactual.  Recorded so the receipt agrees with it in public or disagrees in public.
EXPECTED_APPEARED_ONLY = {"rows": 32438, "fewer_than_registered": 3189}

#: The row set must NOT move.  v4 changes the key, not the universe.
EXPECTED_ROW_SET = {"granularity": "obligation (team_id, game_id, player_id)",
                    "v3_rows": 35627, "v4_rows": 35627,
                    "v3_only": 0, "v4_only": 0,
                    "claim": "UNCHANGED -- only the KEY changes"}

DIFF_SAMPLE_CAP = 50

#: Where a row's `team_id` comes from, recorded on every row because a v4 key MOVES if a trade
#: is retroactively corrected (see cbs_obligation_key's stated exposure).
TEAM_ID_SOURCE = ("master_player.team_id of the admitted-window box rows that established this "
                  "player's candidacy for this club")

# --------------------------------------------------------------------------- #
# C5: the eight fields that must be identical to v2's registered game.parquet
# --------------------------------------------------------------------------- #
#: (column, kind).  `kind` selects the null-aware comparator: NaT != NaT and NaN != NaN under
#: plain `!=`, so a naive comparison would report every date-only game as a mismatch on
#: `scheduled_tip_time` and then be "fixed" by dropping the field -- which is how a check ends
#: up covering two columns out of eight.
CUTOFF_IDENTITY_FIELDS = (
    ("forecast_cutoff", "datetime"),
    ("cutoff_policy", "string"),
    ("exact_cutoff_ok", "bool"),
    ("scheduled_tip_time", "datetime"),
    ("tip_time_source", "string"),
    ("tip_time_observed_at", "datetime"),
    ("tip_time_quality", "string"),
    ("tip_revisions_seen", "int"),
)
CUTOFF_IDENTITY_RULE = (
    "v4 REFUSES TO EMIT unless all EIGHT of "
    + ", ".join(c for c, _ in CUTOFF_IDENTITY_FIELDS)
    + " are identical, per game, to the registered prediction_contract_v2/game.parquet. v3 "
      "compared only forecast_cutoff and cutoff_policy, so a run that reproduced the same "
      "cutoff from DIFFERENT tip evidence -- a different source, a different observation time, "
      "a different revision count -- would have passed. Any mismatch on any field FAILS "
      "CLOSED: the row diff would otherwise be measuring a change of evidence.")


# --------------------------------------------------------------------------- #
# identity  (C1)
# --------------------------------------------------------------------------- #
def row_uid(player_id, game_id, team_id) -> str:
    """The canonical unique obligation key.  Re-exported from `cbs_obligation_key`."""
    return obk.row_uid(player_id, game_id, team_id)


def player_game_uid(player_id, game_id) -> str:
    """The legacy player-game linkage, byte-identical to v2's `pg_uid`.  NOT a key."""
    return obk.player_game_uid(player_id, game_id)


def obligation_uid(player_id, game_id, team_id) -> str:
    """Alias of :func:`row_uid`, for readers of v3's `ob_uid` name."""
    return obk.obligation_uid(player_id, game_id, team_id)


def v3_obligation_uid(team_id, player_id, game_id) -> str:
    """v3's digest, reproduced so v3 rows can be MAPPED to v4 rows rather than confused."""
    return obk.v3_ob_uid_equivalent(team_id, player_id, game_id)


def window_digest(game_ids) -> str:
    """A digest of the EXACT ordered admitted window that established candidacy.

    This is the part of C4 that a timestamp cannot do: two different record sets can share a
    maximum availability bound, but they cannot share this digest.
    """
    return "rw_" + obk.stable_hash(*[str(g) for g in game_ids])


# --------------------------------------------------------------------------- #
# C5: cutoff identity, eight fields, fail closed
# --------------------------------------------------------------------------- #
def _mismatch_mask(a: pd.Series, b: pd.Series, kind: str) -> pd.Series:
    """Null-aware inequality.  Two nulls AGREE; a null against a value DISAGREES."""
    if kind == "datetime":
        a = pd.to_datetime(a, utc=True, errors="coerce")
        b = pd.to_datetime(b, utc=True, errors="coerce")
    elif kind == "int":
        a = pd.to_numeric(a, errors="coerce")
        b = pd.to_numeric(b, errors="coerce")
    elif kind == "bool":
        a = a.map(lambda x: None if pd.isna(x) else bool(x))
        b = b.map(lambda x: None if pd.isna(x) else bool(x))
    else:
        a = a.map(lambda x: None if (x is None or (isinstance(x, float) and pd.isna(x)))
                  else str(x))
        b = b.map(lambda x: None if (x is None or (isinstance(x, float) and pd.isna(x)))
                  else str(x))
    na_a, na_b = a.isna(), b.isna()
    both_present = ~na_a & ~na_b
    return (na_a != na_b) | (both_present & (a != b))


def compare_cutoff_fields(games: pd.DataFrame, ref: pd.DataFrame) -> dict:
    """Compare all eight cutoff/tip-provenance fields per game.  Pure; never raises.

    Separated from the assertion so the fail-closed behaviour can be exercised field by field
    in a test without a parquet on disk.
    """
    cols = [c for c, _ in CUTOFF_IDENTITY_FIELDS]
    a = games[["game_id"] + cols].copy()
    b = ref[["game_id"] + cols].copy()
    a["game_id"] = a.game_id.astype(str)
    b["game_id"] = b.game_id.astype(str)
    m = a.merge(b, on="game_id", how="outer", suffixes=("_v4", "_ref"), indicator=True)

    problems: list[str] = []
    n_missing = int((m._merge != "both").sum())
    if n_missing:
        problems.append(f"{n_missing} games present in one contract and not the other")
    both = m[m._merge == "both"]
    per_field: dict[str, dict] = {}
    for col, kind in CUTOFF_IDENTITY_FIELDS:
        bad = _mismatch_mask(both[f"{col}_v4"], both[f"{col}_ref"], kind)
        n = int(bad.sum())
        per_field[col] = {
            "kind": kind, "mismatches": n, "ok": n == 0,
            "sample": [str(x) for x in both.loc[bad, "game_id"].head(5)] if n else [],
        }
        if n:
            problems.append(f"{n} games whose {col} differs from the registered v2 value")
    return {
        "receipt": "cutoff_identity/2",
        "rule": CUTOFF_IDENTITY_RULE,
        "fields_compared": [c for c, _ in CUTOFF_IDENTITY_FIELDS],
        "n_fields_compared": len(CUTOFF_IDENTITY_FIELDS),
        "fields_compared_by_v3": ["forecast_cutoff", "cutoff_policy"],
        "games_compared": int(len(both)),
        "games_only_on_one_side": n_missing,
        "per_field": per_field,
        "ok": not problems,
        "problems": problems,
    }


def require_cutoff_identity(games: pd.DataFrame, ref: pd.DataFrame) -> dict:
    """FAIL CLOSED on any of the eight fields."""
    rec = compare_cutoff_fields(games, ref)
    if not rec["ok"]:
        raise SystemExit(
            "REFUSING TO EMIT -- v4's cutoff identity does not match the registered v2 "
            "game.parquet on all eight fields:\n  " + "\n  ".join(rec["problems"])
            + "\nThe row diff would then be measuring a change of tip evidence, not the change "
              "of key. Check that both tip sources resolved (see resolve_sources(); "
              "data/odds_capture/ is gitignored and absent from worktree checkouts -- set "
              "WNBA_ODDS_EXT or run from a checkout that has it).")
    return rec


def assert_cutoff_identity_vs_v2(games: pd.DataFrame) -> dict:
    """Load v2's frozen game.parquet and require identity on all eight fields.

    `data/odds_capture/master_odds_extension.csv` is gitignored and therefore ABSENT from a
    worktree checkout while still being repository data.  A producer that quietly ran without
    it resolves 2 exact tips instead of 407 and flips 1,086 games to the date-only policy; the
    resulting diff would be a fabricated finding.  This is the guard that stops it, and v4
    widens it from two fields to eight.
    """
    p = V2_OUT / "game.parquet"
    if not p.exists():
        raise SystemExit(f"cannot verify cutoff identity: {p} is missing. v4's row diff is "
                         f"only interpretable against the registered v2 artifact.")
    ref = pd.read_parquet(p)
    rec = require_cutoff_identity(games, ref)
    rec["compared_against"] = {"artifact": str(p.relative_to(REPO).as_posix()),
                               "sha256": ai.content_hash(p), "rows": int(len(ref))}
    return rec


# --------------------------------------------------------------------------- #
# C3 + C1: the candidate universe
# --------------------------------------------------------------------------- #
def _team_game_index(mp: pd.DataFrame) -> pd.DataFrame:
    """Every (team, game) that exists, date-ordered, INDEPENDENT of the membership rule.

    Built from the full master, never from the membership-filtered pool: a counterfactual that
    also shrank the team-game INDEX would silently move the admission window as well as the
    membership rule, and the two effects could not be told apart.
    """
    d = mp[["team_id", "game_id", "game_date", "season"]].dropna().drop_duplicates().copy()
    d["game_id"] = d.game_id.astype(str)
    d["game_date"] = pd.to_datetime(d.game_date)
    return (d.sort_values(["team_id", "season", "game_date", "game_id"])
            .reset_index(drop=True))


def _membership_pool(mp: pd.DataFrame, membership: str) -> dict:
    """(team_id, game_id) -> the player ids that count as members under `membership`."""
    d = mp[["game_id", "team_id", "player_id", "minutes"]].copy()
    d = d.dropna(subset=["game_id", "team_id", "player_id"])
    d["game_id"] = d.game_id.astype(str)
    if membership == MEMBERSHIP_APPEARED_ONLY:
        d = d[pd.to_numeric(d.minutes, errors="coerce").fillna(0) > 0]
    elif membership != MEMBERSHIP_BOX_INCLUDING_DNP:
        raise SystemExit(f"unknown membership rule {membership!r}")
    return {k: v.player_id.unique() for k, v in d.groupby(["team_id", "game_id"], sort=False)}


def build_candidates(mp: pd.DataFrame, cutoffs, lookback: int = ROSTER_LOOKBACK,
                     membership: str = MEMBERSHIP_BOX_INCLUDING_DNP
                     ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Candidates and per-team-game window accounting, keyed on the canonical obligation id.

    Behaviourally identical to `prediction_contract_v3.build_candidates` under the default
    membership rule -- that identity is the point, and `row_diff_vs_v3` proves it on the real
    data.  What changes is the KEY (C1), the honest membership NAME (C3) and the candidacy
    RECORDS carried per row (C4).

    Returns (candidates, windows).  `windows` has one row per team-game INCLUDING the ones with
    no candidates at all: a coverage failure is reported, never hidden.
    """
    team_games = _team_game_index(mp)
    by_team_players = _membership_pool(mp, membership)
    cut = {str(k): pd.Timestamp(v) for k, v in dict(cutoffs).items()}

    rows: list[tuple] = []
    windows: list[dict] = []
    # Grouped by (team_id, SEASON): the window RESETS at every season boundary.
    for (team_id, season), grp in team_games.groupby(["team_id", "season"], sort=False):
        gids = grp.game_id.tolist()
        dates = [pd.Timestamp(x) for x in grp.game_date.tolist()]
        avail = list(availability_bound(pd.Series(dates)))
        for i, gid in enumerate(gids):
            if gid not in cut:
                raise SystemExit(f"no forecast cutoff for game {gid}; refusing to guess one")
            c = cut[gid]
            if pd.isna(c):
                raise SystemExit(f"null forecast cutoff for game {gid}")
            # STRICT: equality is a violation, not a pass.
            admitted = [j for j in range(i) if avail[j] < c]
            window = admitted[-lookback:]
            positional = list(range(max(0, i - lookback), i))
            pool: set = set()
            for j in window:
                pool.update(by_team_players.get((team_id, gids[j]), ()))
            bound = max((avail[j] for j in window), default=pd.NaT)
            wgids = [gids[j] for j in window]
            wdigest = window_digest(wgids) if wgids else None
            windows.append({
                "team_id": team_id, "game_id": gid, "season": season,
                "game_date": dates[i], "team_game_index": i,
                "prior_games_in_season": i,
                "prior_games_admitted": len(admitted),
                "prior_games_excluded_unadmitted": i - len(admitted),
                "lookback_games_used": len(window),
                "lookback_games_positional": len(positional),
                "admitted_window_bound": bound,
                "admitted_window_first_game": wgids[0] if wgids else None,
                "admitted_window_last_game": wgids[-1] if wgids else None,
                "admitted_window_digest": wdigest,
                "window_shifted_vs_positional": window != positional,
                "n_candidates": len(pool),
                "membership_rule_id": membership,
                "zero_candidate_reason": (
                    None if pool else
                    "season_opener_no_prior_in_season_game" if i == 0 else
                    "no_prior_in_season_game_admitted_before_cutoff" if not window else
                    "admitted_window_contained_no_box_rows"),
            })
            for pid in pool:
                rows.append((gid, team_id, pid, dates[i], season, len(window), bound,
                             i - len(admitted), window != positional,
                             wgids[0], wgids[-1], wdigest, len(admitted)))

    c = pd.DataFrame(rows, columns=[
        "game_id", "team_id", "player_id", "game_date", "season", "lookback_games_used",
        "admitted_window_bound", "prior_games_excluded_unadmitted",
        "lookback_window_shifted_vs_positional", "admitted_window_first_game",
        "admitted_window_last_game", "admitted_window_digest", "prior_games_admitted"])

    # ---- C1: the canonical key, and the legacy linkage beside it ------------
    c["row_uid"] = [obk.row_uid(p, g, t)
                    for p, g, t in zip(c.player_id, c.game_id, c.team_id)]
    c["obligation_uid"] = c["row_uid"]                      # explicit alias, same bytes
    c["player_game_uid"] = [obk.player_game_uid(p, g)
                            for p, g in zip(c.player_id, c.game_id)]
    c["v3_obligation_uid"] = [obk.v3_ob_uid_equivalent(t, p, g)
                              for t, p, g in zip(c.team_id, c.player_id, c.game_id)]
    c["player_game_uid_shared_with_other_team"] = \
        c.player_game_uid.duplicated(keep=False).to_numpy()
    c["obligation_key_id"] = obk.OBLIGATION_KEY_ID
    c["membership_rule_id"] = membership
    c["team_id_source"] = TEAM_ID_SOURCE
    # The check whose absence let v10 ship a green gate over an unexecutable path.
    obk.assert_unique_canonical_keys(c, where="prediction_contract_v4.build_candidates")
    return c, pd.DataFrame(windows)


def appeared_only_counterfactual(mp: pd.DataFrame, cutoffs) -> dict:
    """MEASURE the universe v3's prose described, without emitting it.  (C3)

    v3 registered its membership as "appeared in a prior game" while implementing box
    membership.  The honest repair is to rename the implemented rule and to state, in numbers,
    what the described rule would have produced -- so that a reader can see the size of the
    gap between the two rather than take either on faith.
    """
    box, _ = build_candidates(mp, cutoffs, membership=MEMBERSHIP_BOX_INCLUDING_DNP)
    app, appwin = build_candidates(mp, cutoffs, membership=MEMBERSHIP_APPEARED_ONLY)

    def trip(df):
        return {(int(t), str(g), int(p))
                for t, g, p in df[["team_id", "game_id", "player_id"]].to_numpy()}

    tb, ta = trip(box), trip(app)
    lost = tb - ta
    gained = ta - tb                      # must be empty: appeared-only is a strict subset
    n_box, n_app = len(tb), len(ta)
    delta = n_box - n_app

    # Why each lost obligation was lost, from the master itself: the player was a BOX MEMBER of
    # the window but never played in it.
    mins = pd.to_numeric(mp.minutes, errors="coerce")
    n_null_minutes = int(mins.isna().sum())
    n_zero_minutes = int((mins.fillna(-1) == 0).sum())

    exp = EXPECTED_APPEARED_ONLY
    return {
        "receipt": "appeared_only_counterfactual/1",
        "registered_membership": MEMBERSHIP_BOX_INCLUDING_DNP,
        "counterfactual_membership": MEMBERSHIP_APPEARED_ONLY,
        "what_v3_prose_claimed": ("a candidate 'APPEARED in one of the latest five prior "
                                  "same-season team games'; the v3 implementation pools every "
                                  "box row of those games, DNP rows included"),
        "registered_rows": n_box,
        "appeared_only_rows": n_app,
        "obligations_that_exist_only_because_dnp_rows_count": delta,
        "appeared_only_rows_absent_from_registered": len(gained),
        "appeared_only_is_a_strict_subset": not gained,
        "team_games_losing_all_candidates": int((appwin.n_candidates == 0).sum()),
        "master_rows_with_null_minutes": n_null_minutes,
        "master_rows_with_zero_minutes": n_zero_minutes,
        "supervisor_expected": exp,
        "matches_supervisor": {
            "rows": n_app == exp["rows"],
            "fewer_than_registered": delta == exp["fewer_than_registered"],
        },
        "all_match": bool(n_app == exp["rows"] and delta == exp["fewer_than_registered"]),
        "why_the_registered_rule_is_kept": (
            "box membership is the defensible recency-roster proxy: a player listed with a DNP "
            "reason was demonstrably with the club at that game, which is exactly the fact "
            "candidacy is trying to establish. Requiring minutes would delete "
            f"{delta} obligations an arm genuinely owes a forecast for, and would make a "
            "player's candidacy depend on a coach's rotation choice rather than on his "
            "presence. The rule is kept and RENAMED; it is not narrowed."),
    }


# --------------------------------------------------------------------------- #
# C4: roster provenance bound to the candidacy record
# --------------------------------------------------------------------------- #
ROSTER_BINDING_ID = "contract_admitted_window/1"
ROSTER_POLICY_LABEL = "contract_admitted_window_bound"


def attach_roster_provenance(cand: pd.DataFrame) -> pd.DataFrame:
    """Emit `src_asof_roster` / `n_roster_games_consumed` FROM the candidacy record.  (C4)

    Not a recomputation and not a copy of some other bound: `src_asof_roster` IS the contract's
    `admitted_window_bound`, `n_roster_games_consumed` IS `lookback_games_used`, and the window
    that produced them is identified by its first game, its last game and a digest of the exact
    ordered id list.  A downstream frame builder that recomputes a trailing window over its own
    index and lands on the same timestamp can now be CHECKED against these records instead of
    being believed because the numbers agree.
    """
    c = cand.copy()
    c["src_asof_roster"] = pd.to_datetime(c.admitted_window_bound, utc=True)
    c["n_roster_games_consumed"] = c.lookback_games_used.astype("int64")
    c["src_policy_roster"] = ROSTER_POLICY_LABEL
    c["roster_binding_id"] = ROSTER_BINDING_ID
    c["roster_evidence_first_game"] = c.admitted_window_first_game
    c["roster_evidence_last_game"] = c.admitted_window_last_game
    c["roster_evidence_digest"] = c.admitted_window_digest
    if c.n_roster_games_consumed.le(0).any():                       # pragma: no cover
        raise SystemExit("a candidate row reports zero roster games consumed; a candidate "
                         "cannot exist without a non-empty admitted window")
    if c.src_asof_roster.isna().any():                              # pragma: no cover
        raise SystemExit("a candidate row carries a null roster bound")
    return c


def roster_binding_receipt(cand: pd.DataFrame, mp: pd.DataFrame, cutoffs) -> dict:
    """Measure the coincidence v9/v10 mistook for a binding, and say why it is not one.

    The downstream recomputation (`cbs_real_frames_v2`) takes the max availability over a
    trailing window of ALL admitted prior team games.  Availability under the +36h policy is
    monotone in `game_date` and the admitted index is date-ordered, so that maximum is the last
    admitted game's bound -- the same instant the contract's five-game window reports.  The
    timestamps therefore agree on every row while the RECORD SETS differ in size on many of
    them.  Agreement of a maximum over two different sets is not evidence that the same records
    were read.
    """
    cut = {str(k): pd.Timestamp(v) for k, v in dict(cutoffs).items()}
    team_games = _team_game_index(mp)
    # the uncapped recomputation, per team-game
    recomputed: dict[tuple, tuple] = {}
    for (team_id, season), grp in team_games.groupby(["team_id", "season"], sort=False):
        gids = grp.game_id.tolist()
        avail = list(availability_bound(pd.Series([pd.Timestamp(x)
                                                   for x in grp.game_date.tolist()])))
        for i, gid in enumerate(gids):
            adm = [j for j in range(i) if avail[j] < cut[gid]]
            recomputed[(int(team_id), gid)] = (
                (max(avail[j] for j in adm) if adm else pd.NaT), len(adm))

    keys = list(zip(cand.team_id.astype(int), cand.game_id.astype(str)))
    rec_bound = pd.Series([recomputed[k][0] for k in keys], index=cand.index)
    rec_n = pd.Series([recomputed[k][1] for k in keys], index=cand.index)
    contract_bound = pd.to_datetime(cand.admitted_window_bound, utc=True)
    rec_bound = pd.to_datetime(rec_bound, utc=True)

    same_instant = int((contract_bound == rec_bound).sum())
    diff_instant = int(len(cand) - same_instant)
    diff_records = int((rec_n != cand.lookback_games_used).sum())

    return {
        "receipt": "roster_provenance_binding/1",
        "binding_id": ROSTER_BINDING_ID,
        "bound_from": ["admitted_window_bound", "lookback_games_used",
                       "admitted_window_first_game", "admitted_window_last_game",
                       "admitted_window_digest"],
        "not_bound_from": ("a trailing window recomputed over a feature-history team index; "
                           "v9/v10 read the numeric coincidence of the two maxima as a binding"),
        "emitted_columns": {
            "src_asof_roster": "= admitted_window_bound, the contract's own candidacy bound",
            "n_roster_games_consumed": "= lookback_games_used, the admitted games actually "
                                       "pooled for this row (1-5 on every emitted row)",
            "src_policy_roster": ROSTER_POLICY_LABEL,
            "roster_evidence_first_game/last_game/digest": "the identity of the exact ordered "
                                                           "window, which a timestamp cannot "
                                                           "carry",
        },
        "coincidence_measurement": {
            "rows": int(len(cand)),
            "rows_where_the_two_maxima_are_the_same_instant": same_instant,
            "rows_where_they_differ": diff_instant,
            "rows_where_the_RECORD_SETS_differ_in_size": diff_records,
            "share_of_rows_where_the_maxima_agree": round(same_instant / max(len(cand), 1), 6),
            "interpretation": (
                "the maxima agree on every row BY CONSTRUCTION -- availability is monotone in "
                "game_date and both windows end on the same last admitted game -- while the "
                "record sets differ on "
                f"{diff_records} rows. That is precisely why the coincidence cannot stand in "
                "for a binding: it would still hold if the downstream window read a completely "
                "different number of games, which on most rows it does."),
        },
        "why_this_matters": (
            "a receipt that reports 'the roster bound' without naming the records it came from "
            "cannot be falsified. With the window's first game, last game, size and digest on "
            "the row, a consumer that read a different window is detectable."),
    }


# --------------------------------------------------------------------------- #
# the row-diff receipt: the row set must NOT move
# --------------------------------------------------------------------------- #
def _sample(records: list[dict]) -> list[dict]:
    return sorted(records, key=lambda r: (r["season"], r["game_date"], r["team_id"],
                                          r["player_id"]))[:DIFF_SAMPLE_CAP]


def row_diff_vs_v3(cand: pd.DataFrame, mp: pd.DataFrame) -> dict:
    """v3 -> v4 at OBLIGATION granularity.  The row set is claimed UNCHANGED.

    This diff is not looking for an interesting change; it is looking for the ABSENCE of one.
    v4 re-keys and re-names; if a single obligation appears or disappears, the re-key silently
    changed the universe and that is a DEFECT, surfaced here rather than smoothed.
    """
    p3 = V3_OUT / "player_game.parquet"
    if not p3.exists():
        raise SystemExit(f"cannot build the row diff: {p3} is missing")
    pg3 = pd.read_parquet(p3)
    pg3["game_id"] = pg3.game_id.astype(str)

    name = dict(zip(mp.player_id.astype("int64"), mp.player_name)) \
        if "player_name" in mp.columns else {}
    abbr = dict(zip(mp.team_id.astype("int64"), mp.team_abbreviation)) \
        if "team_abbreviation" in mp.columns else {}
    gdate = {str(g): str(pd.Timestamp(d).date())
             for g, d in zip(mp.game_id.astype(str), pd.to_datetime(mp.game_date))}
    gseason = {str(g): int(s) for g, s in zip(mp.game_id.astype(str), mp.season)}

    def triples(df):
        return {(int(t), str(g), int(p))
                for t, g, p in df[["team_id", "game_id", "player_id"]].to_numpy()}

    t3, t4 = triples(pg3), triples(cand)
    only3, only4 = t3 - t4, t4 - t3

    def rec(tr, side):
        t, g, p = tr
        return {"side": side, "season": gseason.get(g, -1), "game_date": gdate.get(g, ""),
                "game_id": g, "team_id": t, "team": abbr.get(t, ""),
                "player_id": p, "player": name.get(p, ""),
                "v3_row_uid": pg_uid(p, g), "v3_obligation_uid": v3_obligation_uid(t, p, g),
                "v4_row_uid": obk.row_uid(p, g, t)}

    unchanged = not only3 and not only4

    # --- the KEY change, stated exactly --------------------------------------
    v3_keys = set(pg3.row_uid)                       # team-blind pg_uid, NOT unique
    v4_keys = set(cand.row_uid)                      # canonical, unique
    legacy = set(cand.player_game_uid)
    v3_ob = set(pg3.obligation_uid) if "obligation_uid" in pg3.columns else set()
    v4_maps_v3 = set(cand.v3_obligation_uid)

    return {
        "receipt": "row_diff/2",
        "contract_version": CONTRACT_VERSION,
        "compared_against": {
            "artifact": str(p3.relative_to(REPO).as_posix()),
            "sha256": ai.content_hash(p3), "rows": int(len(pg3)),
        },
        "claim": ("THE ROW SET IS UNCHANGED. v4 changes the KEY (and the membership NAME and "
                  "the roster provenance BINDING); it does not change which obligations exist. "
                  "Any row-set difference below is a DEFECT of the re-key, not a finding."),
        "expected": EXPECTED_ROW_SET,
        "obligation_level": {
            "granularity": "obligation (team_id, game_id, player_id)",
            "v3_rows": len(t3), "v4_rows": len(t4),
            "v3_only_count": len(only3), "v4_only_count": len(only4),
            "net_change": len(t4) - len(t3),
            "row_set_unchanged": unchanged,
            "v3_only_sample": _sample([rec(x, "v3_only") for x in only3]),
            "v4_only_sample": _sample([rec(x, "v4_only") for x in only4]),
            "defect": None if unchanged else (
                f"{len(only3)} obligations vanished and {len(only4)} appeared while only the "
                f"key was supposed to change; the v4 universe is NOT the v3 universe"),
        },
        "key_level": {
            "v3_key_column": "row_uid = pg_uid(player_id, game_id), TEAM-BLIND and NOT unique",
            "v4_key_column": f"row_uid = {obk.OBLIGATION_KEY_ID}, "
                             f"sha256(player_id, game_id, team_id), UNIQUE",
            "v3_distinct_row_uids": len(v3_keys),
            "v3_rows": int(len(pg3)),
            "v3_rows_sharing_a_row_uid": int(len(pg3) - len(v3_keys)) * 2,
            "v4_distinct_row_uids": len(v4_keys),
            "v4_row_uid_is_unique": len(v4_keys) == len(cand),
            "v4_distinct_player_game_uids": len(legacy),
            "player_game_uid_set_equals_v3_row_uid_set": legacy == v3_keys,
            "v4_reproduces_every_v3_obligation_uid": bool(v3_ob and v4_maps_v3 == v3_ob),
            "v3_obligation_uid_digests_equal_v4_row_uid_digests": False,
            "field_order_note": (
                "v3 hashed (team_id, player_id, game_id); v4 hashes (player_id, game_id, "
                "team_id) per the registered cbs_obligation_key field order. The digests are "
                "therefore DIFFERENT strings for the same obligation, deliberately: a v3 digest "
                "must not be mistakable for a v4 one. v4 carries v3_obligation_uid on every row "
                "so the mapping is explicit rather than inferred."),
        },
        "downstream_merge_note": (
            "the v4 frame still holds 28 rows sharing 14 (game_id, player_id) pairs -- that is "
            "the truth about traded players and it is what the canonical key exists to name. A "
            "consumer must join on row_uid or on (game_id, team_id, player_id). "
            "cbs_real_frames_v2.build_player_frame merges the contract to the master on "
            "(game_id, player_id) with validate='1:1' and therefore STILL raises MergeError "
            "against v4; that is a defect of the frames module, which is immutable here, and it "
            "is reported rather than worked around."),
    }


# --------------------------------------------------------------------------- #
def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    mp = pd.read_parquet(MASTER)
    mp["game_id"] = mp.game_id.astype(str)
    mp["game_date"] = pd.to_datetime(mp.game_date)
    acct: dict = {"master_rows": int(len(mp))}

    pol = verify_availability_policy()
    if not pol["ok"]:
        raise SystemExit(f"availability policy reproduction is not exact: {pol}")
    acct["availability_policy"] = pol
    acct["obligation_key"] = obk.key_receipt()

    # ---- cutoffs: v2's machinery, unchanged, and PROVEN unchanged on EIGHT fields
    sources = resolve_sources()
    acct["tip_source_resolution"] = sources
    games = (mp[["game_id", "game_date", "season"]].drop_duplicates()
             .sort_values("game_date").reset_index(drop=True))
    tips, tip_audit = resolve_tip_times(games, load_tip_observations(sources))
    games = games.merge(tips, on="game_id", how="left")
    games = apply_cutoff_policy(games)
    acct["cutoff_identity_vs_v2"] = assert_cutoff_identity_vs_v2(games)
    acct["games_total"] = int(len(games))
    acct["games_exact_tip"] = int(games.exact_cutoff_ok.sum())
    acct["games_date_only"] = int((~games.exact_cutoff_ok).sum())
    acct["games_with_tip_revisions"] = int((games.tip_revisions_seen > 1).sum())
    acct["tip_provenance_audit"] = tip_audit

    cutoffs = dict(zip(games.game_id, pd.to_datetime(games.forecast_cutoff, utc=True)))

    # ---- the candidate universe, canonically keyed ---------------------------
    cand, win = build_candidates(mp, cutoffs)
    acct["membership_rule_id"] = MEMBERSHIP_BOX_INCLUDING_DNP
    acct["membership_rule"] = MEMBERSHIP_RULE
    acct["admission_rule"] = ADMISSION_RULE
    acct["roster_lookback_admitted_games"] = ROSTER_LOOKBACK
    acct["candidate_obligations"] = int(len(cand))
    acct["candidate_games"] = int(cand.game_id.nunique())
    acct["candidate_distinct_row_uids"] = int(cand.row_uid.nunique())
    acct["row_uid_is_unique"] = bool(cand.row_uid.is_unique)
    acct["candidate_distinct_player_game_uids"] = int(cand.player_game_uid.nunique())
    acct["obligations_sharing_a_player_game_uid"] = int(
        cand.player_game_uid_shared_with_other_team.sum())
    acct["key_note"] = (
        "row_uid is the CANONICAL UNIQUE key: sha256(player_id, game_id, team_id). "
        "player_game_uid is v2's team-blind pg_uid, retained ONLY as a legacy linkage column; "
        "it is not unique and must never be used as a primary or coverage key again. "
        "obligation_uid is an explicit alias of row_uid. v3's obligation_uid digest is carried "
        "as v3_obligation_uid, and is a DIFFERENT string (different field order).")

    # ---- C3: the counterfactual v3's prose described -------------------------
    cf = appeared_only_counterfactual(mp, cutoffs)
    acct["appeared_only_counterfactual"] = cf
    if not cf["appeared_only_is_a_strict_subset"]:                   # pragma: no cover
        raise SystemExit("the appeared-only universe is not a subset of the registered one; "
                         "the membership counterfactual is not what it claims to be")

    # ---- window accounting ---------------------------------------------------
    acct["team_games_total"] = int(len(win))
    acct["team_games_window_shifted_vs_positional"] = int(
        win.window_shifted_vs_positional.sum())
    acct["prior_games_excluded_unadmitted_total"] = int(
        win.prior_games_excluded_unadmitted.sum())
    acct["team_games_with_an_unadmitted_prior_game"] = int(
        (win.prior_games_excluded_unadmitted > 0).sum())
    shifted = win[win.window_shifted_vs_positional]
    acct["window_shift_by_cutoff_policy"] = {
        str(k): int(v) for k, v in
        shifted.merge(games[["game_id", "cutoff_policy"]], on="game_id", how="left")
        .groupby("cutoff_policy").size().items()}
    acct["team_games_with_zero_candidates"] = int((win.n_candidates == 0).sum())
    acct["zero_candidate_reasons"] = {
        str(k): int(v) for k, v in win.zero_candidate_reason.dropna().value_counts().items()}
    acct["games_with_zero_candidates"] = int(len(set(games.game_id) - set(cand.game_id)))
    acct["lookback_games_used_distribution"] = {
        str(k): int(v) for k, v in win.lookback_games_used.value_counts().sort_index().items()}
    openers = win[win.team_game_index == 0]
    acct["season_openers"] = int(len(openers))
    acct["season_openers_with_candidates"] = int((openers.n_candidates > 0).sum())

    # ---- C4: roster provenance, bound to the candidacy record ---------------
    cand = attach_roster_provenance(cand)
    acct["roster_provenance_binding"] = roster_binding_receipt(cand, mp, cutoffs)

    # ---- the row-diff receipt: the row set must NOT have moved --------------
    diff = row_diff_vs_v3(cand, mp)
    (OUT / "row_diff_vs_v3.json").write_text(json.dumps(diff, indent=1, default=str),
                                             encoding="utf-8")
    acct["row_diff_vs_v3"] = {
        "v3_obligations": diff["obligation_level"]["v3_rows"],
        "v4_obligations": diff["obligation_level"]["v4_rows"],
        "v3_only": diff["obligation_level"]["v3_only_count"],
        "v4_only": diff["obligation_level"]["v4_only_count"],
        "row_set_unchanged": diff["obligation_level"]["row_set_unchanged"],
        "defect": diff["obligation_level"]["defect"],
    }
    if not diff["obligation_level"]["row_set_unchanged"]:
        raise SystemExit(
            "REFUSING TO EMIT -- the v4 row set differs from v3's. Only the key was supposed "
            f"to change. {diff['obligation_level']['defect']}")

    # ---- cutoff fields onto the candidate rows ------------------------------
    cand = cand.drop(columns=["season"]).merge(
        games[["game_id", "season", "scheduled_tip_time", "tip_time_source",
               "tip_time_observed_at", "tip_time_quality", "tip_revisions_seen",
               "cutoff_policy", "forecast_cutoff", "exact_cutoff_ok"]],
        on="game_id", how="left")
    obk.assert_unique_canonical_keys(cand, where="after the cutoff merge")

    # HARD POST-CONDITION: the evidence behind a row's candidacy must strictly predate that
    # row's cutoff. If this fires, the gate did not gate.
    bad = int((pd.to_datetime(cand.admitted_window_bound, utc=True)
               >= pd.to_datetime(cand.forecast_cutoff, utc=True)).sum())
    if bad:
        raise SystemExit(f"{bad} rows whose admitted_window_bound is NOT strictly before "
                         f"their forecast_cutoff -- the availability gate is not causal")
    acct["rows_failing_window_bound_before_cutoff"] = bad
    late_roster = int((pd.to_datetime(cand.src_asof_roster, utc=True)
                       >= pd.to_datetime(cand.forecast_cutoff, utc=True)).sum())
    if late_roster:                                                  # pragma: no cover
        raise SystemExit(f"{late_roster} rows report src_asof_roster at or after their cutoff")
    acct["rows_failing_roster_bound_before_cutoff"] = late_roster

    # ---- labels attached AFTERWARDS, joined ON THE OBLIGATION'S TEAM --------
    lab = mp[["game_id", "team_id", "player_id", "minutes", "pts", "fga"]].copy()
    lab = lab.drop_duplicates(["game_id", "team_id", "player_id"])
    pg = cand.merge(lab, on=["game_id", "team_id", "player_id"], how="left")
    obk.assert_unique_canonical_keys(pg, where="after the label join")
    pg["appeared"] = pd.to_numeric(pg.minutes, errors="coerce").fillna(0) > 0
    pg["in_target_box"] = pg.minutes.notna()
    played_elsewhere = {(str(g), int(p)) for g, p, m in
                        zip(mp.game_id, mp.player_id,
                            pd.to_numeric(mp.minutes, errors="coerce").fillna(0)) if m > 0}
    pg["appeared_for_other_team"] = [
        (not a) and ((g, int(p)) in played_elsewhere)
        for a, g, p in zip(pg.appeared, pg.game_id, pg.player_id)]
    acct["candidates_not_in_target_box"] = int((~pg.in_target_box).sum())
    acct["candidates_appeared"] = int(pg.appeared.sum())
    acct["candidates_dnp_or_absent"] = int((~pg.appeared).sum())
    acct["candidates_who_appeared_for_the_other_team"] = int(pg.appeared_for_other_team.sum())
    blind = mp[["game_id", "player_id", "minutes"]].copy()
    blind["player_game_uid"] = [obk.player_game_uid(p, g)
                                for p, g in zip(blind.player_id, blind.game_id)]
    blind = blind.drop_duplicates("player_game_uid")[
        ["player_game_uid", "minutes"]].rename(columns={"minutes": "minutes_blind"})
    chk = pg[["player_game_uid", "appeared"]].merge(blind, on="player_game_uid", how="left")
    acct["rows_where_team_blind_label_would_differ"] = int(
        ((pd.to_numeric(chk.minutes_blind, errors="coerce").fillna(0) > 0) != chk.appeared).sum())

    # ---- obligation vs scoring, three independent flags ---------------------
    pg["candidate_at_cutoff"] = True
    for t, T in TARGETS.items():
        if T.table != "player_game":
            continue
        pg[f"prediction_required__{t}"] = True          # EVERY candidate, all targets
        if t == "p_active":
            score = pg.candidate_at_cutoff
        elif t == "e_minutes_given_active":
            score = pg.appeared
        elif t == "attempts_usage":
            score = pg.appeared & pd.to_numeric(pg.fga, errors="coerce").notna()
        else:
            score = pg.appeared & pd.to_numeric(pg.pts, errors="coerce").notna()
        pg[f"outcome_scoreable__{t}"] = np.asarray(score)
        acct[f"required__{t}"] = int(pg[f"prediction_required__{t}"].sum())
        acct[f"scoreable__{t}"] = int(pg[f"outcome_scoreable__{t}"].sum())

    pg["fold_id"] = "season:" + pg.season.astype(int).astype(str)
    pg["train_boundary"] = pg.season.astype(int).map(lambda s: f"seasons < {s}")
    pg["clustering_unit"] = pg.game_date.dt.date.astype(str)

    # ---- team-game and game tables ------------------------------------------
    tg = (mp[["game_id", "team_id", "game_date", "season"]].drop_duplicates()
          .merge(games[["game_id", "forecast_cutoff", "cutoff_policy", "exact_cutoff_ok",
                        "scheduled_tip_time"]], on="game_id", how="left")
          .merge(win[["game_id", "team_id", "n_candidates", "lookback_games_used",
                      "prior_games_admitted", "prior_games_excluded_unadmitted",
                      "admitted_window_bound", "admitted_window_first_game",
                      "admitted_window_last_game", "admitted_window_digest",
                      "window_shifted_vs_positional", "zero_candidate_reason",
                      "membership_rule_id"]],
                 on=["game_id", "team_id"], how="left"))
    tg["row_uid"] = [tg_uid(t, g) for t, g in zip(tg.team_id, tg.game_id)]
    tg["fold_id"] = "season:" + tg.season.astype(int).astype(str)
    tg["clustering_unit"] = tg.game_date.dt.date.astype(str)
    tg["prediction_required__team_game_distribution"] = True
    tg["outcome_scoreable__team_game_distribution"] = True
    tg["n_roster_games_consumed"] = tg.lookback_games_used.fillna(0).astype("int64")
    tg["src_asof_roster"] = pd.to_datetime(tg.admitted_window_bound, utc=True)
    tg["src_policy_roster"] = np.where(tg.n_roster_games_consumed > 0, ROSTER_POLICY_LABEL,
                                       "no_admitted_prior_team_game")
    acct["team_game_rows"] = int(len(tg))
    acct["team_game_unique"] = int(tg.row_uid.nunique())
    acct["team_game_zero_candidate_rows_retained"] = int((tg.n_candidates.fillna(0) == 0).sum())
    if not tg.row_uid.is_unique:                                     # pragma: no cover
        raise SystemExit("team_game row_uid is not unique")

    gm = games.copy()
    gm["row_uid"] = [g_uid(g) for g in gm.game_id]
    acct["game_rows"] = int(len(gm))
    if not gm.row_uid.is_unique:                                     # pragma: no cover
        raise SystemExit("game row_uid is not unique")

    # FINAL gate before any byte is written.
    obk.assert_unique_canonical_keys(pg, where="emitted player_game.parquet")

    pg.to_parquet(OUT / "player_game.parquet", index=False)
    tg.to_parquet(OUT / "team_game.parquet", index=False)
    gm.to_parquet(OUT / "game.parquet", index=False)

    spec = {
        "contract_version": CONTRACT_VERSION,
        "supersedes": SUPERSEDES,
        "supersedes_reason": SUPERSEDES_REASON,
        "obligation_key": obk.key_receipt(),
        "key_columns": {
            "row_uid": "CANONICAL UNIQUE KEY -- 'ob_' + sha256(player_id, game_id, team_id). "
                       "Exactly one forecast is owed per value. Join on this.",
            "obligation_uid": "explicit alias of row_uid; identical bytes",
            "player_game_uid": "LEGACY LINKAGE ONLY -- 'pg_' + sha256(player_id, game_id), "
                               "byte-identical to prediction_contract_v2.pg_uid. NOT unique "
                               "(28 rows share 14 values) and NEVER a primary or coverage key",
            "v3_obligation_uid": "prediction_contract_v3's digest for the same obligation. A "
                                 "DIFFERENT string from row_uid because v3 hashed (team_id, "
                                 "player_id, game_id); carried so the mapping is explicit",
            "player_game_uid_shared_with_other_team": "True on both rows of a legacy-key "
                                                      "collision",
        },
        "membership_rule_id": MEMBERSHIP_BOX_INCLUDING_DNP,
        "membership_rule": MEMBERSHIP_RULE,
        "admission_rule": ADMISSION_RULE,
        "membership_correction_vs_v3": (
            "v3 registered 'a player who APPEARED in one of the latest five prior same-season "
            "team games' and listed 'a player who missed the entire admitted window is NOT a "
            "candidate' as a limitation. Neither statement described the v3 implementation, "
            "which pooled every ADMITTED box row including DNP / DND / NWT rows with null "
            "minutes. The BEHAVIOUR is unchanged in v4 -- it is the defensible proxy and "
            "narrowing it would delete real obligations -- and the NAME is corrected to "
            "'prior admitted team-game box membership, including DNP rows'."),
        "appeared_only_counterfactual": cf,
        "availability_policy": {
            "policy_id": AVAILABILITY_POLICY_ID,
            "lag_hours": AVAILABILITY_POLICY_LAG_HOURS,
            "formula": "floor_to_day_utc(game_date) + 36h = noon UTC the day AFTER the game",
            "identical_to": ["cbs_v7.OUTCOME_AVAILABILITY_POLICY_LAG_HOURS",
                             "cbs_real_frames.availability_of",
                             "prediction_contract_v3.availability_bound (IMPORTED, not copied)",
                             "asof_invariant.bound_from_dates (for a bare game date)"],
            "kind": "POLICY, never an observation; deliberately NOT derived from "
                    "observed_time, which is a local file mtime",
            "strictness": "admission requires bound < cutoff; EQUALITY IS A VIOLATION",
        },
        "cutoff_identity": CUTOFF_IDENTITY_RULE,
        "roster_provenance_binding": acct["roster_provenance_binding"],
        "universe_kind": "RECENCY-ROSTER PROXY by prior admitted BOX MEMBERSHIP; "
                         "availability-causal; still not the complete slate",
        "preserved_from_v3": [
            "the availability gate itself: availability_bound, verify_availability_policy, "
            "resolve_sources and load_tip_observations are IMPORTED from the frozen v3 module",
            "the ROW SET: all 35,627 obligations, proven unchanged in row_diff_vs_v3.json",
            "the membership BEHAVIOUR (box membership including DNP rows), renamed but not "
            "narrowed",
            "the season reset, the strict bound < cutoff admission, and the visibility of "
            "every zero-candidate team-game",
            "the central invariant: the target game's own rows are never read to decide "
            "membership",
        ],
        "changed_vs_v3": [
            "C1 row_uid is now the CANONICAL UNIQUE team-bearing key "
            f"({obk.OBLIGATION_KEY_ID}); the team-blind pg_uid survives as the non-key column "
            "player_game_uid, and uniqueness is asserted before anything is emitted",
            "C3 the membership rule is registered as prior admitted team-game BOX MEMBERSHIP "
            "INCLUDING DNP ROWS, and the appeared-only counterfactual is measured",
            "C4 src_asof_roster and n_roster_games_consumed are derived FROM the contract's "
            "admitted_window_bound / lookback_games_used and carry the window's first game, "
            "last game and digest -- not from a recomputed feature-history window",
            "C5 cutoff identity against the registered v2 game.parquet is proven on all EIGHT "
            "tip/cutoff fields, not two",
        ],
        "new_columns": {
            "row_uid": "the canonical unique obligation key (REPLACES v3's team-blind row_uid)",
            "player_game_uid": "v3's row_uid value, renamed to what it is",
            "v3_obligation_uid": "v3's obligation digest, for explicit mapping",
            "obligation_key_id": obk.OBLIGATION_KEY_ID,
            "membership_rule_id": MEMBERSHIP_BOX_INCLUDING_DNP,
            "team_id_source": TEAM_ID_SOURCE,
            "src_asof_roster": "= admitted_window_bound; the candidacy evidence bound",
            "n_roster_games_consumed": "= lookback_games_used; the admitted games pooled",
            "src_policy_roster": ROSTER_POLICY_LABEL,
            "roster_binding_id": ROSTER_BINDING_ID,
            "roster_evidence_first_game": "first game id of the admitted window",
            "roster_evidence_last_game": "last game id of the admitted window",
            "roster_evidence_digest": "digest of the exact ordered window game ids",
            "admitted_window_digest": "same digest, on the team-game accounting",
        },
        "renamed_from_v3": {
            "row_uid -> player_game_uid": "the team-blind value keeps its bytes and loses the "
                                          "name 'row_uid', which now means the unique key",
            "obligation_uid -> row_uid": "the unique key is now the row key; the alias "
                                         "obligation_uid still exists but the DIGEST changed "
                                         "because the field order is now (player, game, team)",
            "row_uid_shared_with_other_team -> player_game_uid_shared_with_other_team":
                "renamed rather than reused: a column whose name still said 'row_uid' would "
                "now be describing a different column",
            "admitted_window_contained_no_player_rows -> admitted_window_contained_no_box_rows":
                "the zero-candidate reason now says BOX rows, matching the membership rule",
        },
        "universe_limitations": [
            f"candidacy is inferred from BOX MEMBERSHIP in the team's latest {ROSTER_LOOKBACK} "
            "ADMITTED games -- being listed, whether or not the player played -- because exact "
            "historical rosters, transactions and inactive lists are not reconstructable for "
            "every season",
            "a player who is rostered but absent from every box score in the admitted window "
            "(not even listed as a DNP) is NOT a candidate; this understates the true slate",
            "a debut or new signing with no prior box appearance cannot be a candidate at all",
            "the first game of each team-season has no admitted prior game and yields none",
            "the availability bound is a POLICY, so it is conservative by construction: where "
            "a box score really was published sooner, v4 still refuses to use it",
            "a retroactive TRADE CORRECTION would move a v4 row_uid, which v2's team-blind key "
            "would not; accepted deliberately (see cbs_obligation_key.known_exposure) because "
            "a non-unique key cannot support a merge, a coverage count or a scoring join",
        ],
        "central_invariant": (
            "deleting every target-game player row before constructing the candidate roster "
            "does not change the candidate set; candidacy reads only same-season games that "
            "are strictly prior AND whose appearance data was admitted strictly before the "
            "row's forecast cutoff"),
        "cutoff_policies": {
            POLICY_EXACT: f"forecast_cutoff = scheduled_tip_time - "
                          f"{CUTOFF_MINUTES_BEFORE_TIP} minutes; the ONLY rows usable for "
                          f"exact-cutoff market comparisons",
            POLICY_DATE_ONLY: "18:00 UTC on the day BEFORE the game. Conservative, reported "
                              "separately, and NEVER described as T-90m",
        },
        "targets": {k: asdict(v) for k, v in TARGETS.items()},
        "quantiles": QUANTILES,
        "prediction_schema": PREDICTION_SCHEMA,
        "tables": {"player_game": "one row per pregame OBLIGATION (team x player x game), "
                                  "keyed by the unique row_uid",
                   "team_game": "tg_ -- one row per team x game, including zero-candidate ones",
                   "game": "g_ -- one row per game"},
        "obligation_vs_scoring": (
            "prediction_required and outcome_scoreable are INDEPENDENT. E[minutes|active] is "
            "required for every candidate including eventual DNPs, and scored only where the "
            "player appeared FOR THAT TEAM, so an arm cannot buy coverage by dropping the "
            "inactive."),
        "nothing_is_fitted": (
            "this contract fits nothing, predicts nothing and scores nothing. Every value in "
            "it is an id, a count, a timestamp, a hash or a boolean."),
        "accounting": acct,
        "row_diff_receipt": "row_diff_vs_v3.json",
    }
    (OUT / "contract.json").write_text(json.dumps(spec, indent=1, default=str),
                                       encoding="utf-8")

    # ---- as-of manifests for EVERY artifact ---------------------------------
    seasons = sorted(int(s) for s in pd.unique(gm.season))
    bound = ai.bound_from_dates(pd.to_datetime(gm.game_date))
    inherit = ("As-of bound derived from GAME DATES via asof_invariant.bound_from_dates "
               "(max(game_date) + 1 day at 12:00 UTC). The master's observed_time column is a "
               "LOCAL FILE MTIME and is deliberately NOT used as an as-of bound.")
    ai.write_manifest(
        OUT / "player_game.parquet", producer="prediction_contract_v4.py",
        fit_through_date=ai.bound_from_dates(pd.to_datetime(pg.game_date)),
        fit_through_season=int(pg.season.max()),
        fit_seasons=sorted(int(x) for x in pd.unique(pg.season)),
        asof_granularity="row",
        notes=("Availability-causal pregame candidate universe, keyed by the CANONICAL UNIQUE "
               "obligation id row_uid = 'ob_' + sha256(player_id, game_id, team_id) "
               f"({obk.OBLIGATION_KEY_ID}); player_game_uid is v2's team-blind pg_uid, retained "
               "as a legacy linkage column and NOT unique. Nothing is fitted. Candidacy is BOX "
               "MEMBERSHIP (DNP rows included) in the team's latest five ADMITTED prior "
               "same-season games; target-game rows are attached as LABELS only, joined on "
               "(game_id, team_id, player_id). Each row carries its own forecast_cutoff, "
               "cutoff_policy, admitted_window_bound and the identity of the admitted window "
               "that established its candidacy. " + inherit),
        extra={"contract_version": CONTRACT_VERSION,
               "obligation_key_id": obk.OBLIGATION_KEY_ID,
               "membership_rule_id": MEMBERSHIP_BOX_INCLUDING_DNP,
               "roster_binding_id": ROSTER_BINDING_ID,
               "bound_source": "game_date via asof_invariant.bound_from_dates",
               "supersedes": SUPERSEDES})
    ai.write_manifest(
        OUT / "team_game.parquet", producer="prediction_contract_v4.py",
        fit_through_date=ai.bound_from_dates(pd.to_datetime(tg.game_date)),
        fit_through_season=int(tg.season.max()),
        fit_seasons=sorted(int(x) for x in pd.unique(tg.season)),
        asof_granularity="row",
        notes=("One row per team-game, INCLUDING every zero-candidate team-game, which carries "
               "n_candidates=0 and a named zero_candidate_reason. Each row also carries the "
               "admitted window that decided its candidate set (first game, last game, digest) "
               "and the roster bound derived from it. " + inherit),
        extra={"contract_version": CONTRACT_VERSION,
               "obligation_key_id": obk.OBLIGATION_KEY_ID,
               "membership_rule_id": MEMBERSHIP_BOX_INCLUDING_DNP,
               "roster_binding_id": ROSTER_BINDING_ID,
               "bound_source": "game_date via asof_invariant.bound_from_dates",
               "supersedes": SUPERSEDES})
    ai.write_manifest(
        OUT / "game.parquet", producer="prediction_contract_v4.py",
        fit_through_date=bound, fit_through_season=int(gm.season.max()),
        fit_seasons=seasons, asof_granularity="row",
        notes=("One row per game with its resolved tip provenance and cutoff policy, proven "
               "identical to the registered prediction_contract_v2/game.parquet on all eight "
               "cutoff and tip-provenance fields. " + inherit),
        extra={"contract_version": CONTRACT_VERSION,
               "cutoff_identity_fields": [c for c, _ in CUTOFF_IDENTITY_FIELDS],
               "bound_source": "game_date via asof_invariant.bound_from_dates",
               "supersedes": SUPERSEDES})
    ai.write_manifest(
        OUT / "contract.json", producer="prediction_contract_v4.py",
        fit_through_date=bound, fit_through_season=int(gm.season.max()),
        fit_seasons=seasons, asof_granularity="artifact",
        notes=("contract.json is a POLICY DOCUMENT: it has no game_date and no timestamp of "
               "its own. This bound is INHERITED from the tables it describes via "
               "asof_invariant.bound_from_dates and is not a measurement of this file. "
               f"Cross-check: accounting records candidate_obligations="
               f"{acct['candidate_obligations']}, team_game_rows={acct['team_game_rows']}, "
               f"master_rows={acct['master_rows']}."),
        extra={"contract_version": CONTRACT_VERSION,
               "obligation_key_id": obk.OBLIGATION_KEY_ID,
               "bound_source": "INHERITED from player_game.parquet and team_game.parquet",
               "document_has_no_dates_of_its_own": True, "supersedes": SUPERSEDES})
    ai.write_manifest(
        OUT / "row_diff_vs_v3.json", producer="prediction_contract_v4.py",
        fit_through_date=bound, fit_through_season=int(gm.season.max()),
        fit_seasons=seasons, asof_granularity="artifact",
        notes=("Membership accounting only: row counts and set differences between the v3 and "
               "v4 candidate universes, whose row sets are claimed IDENTICAL. No model, no "
               "prediction, no score. The bound is INHERITED from the game dates of the two "
               "universes it compares."),
        extra={"contract_version": CONTRACT_VERSION,
               "bound_source": "INHERITED from the compared universes' game dates",
               "compared_against": "experiments/prediction_contract_v3/player_game.parquet",
               "supersedes": SUPERSEDES})

    d = diff["obligation_level"]
    ci = acct["cutoff_identity_vs_v2"]
    rb = acct["roster_provenance_binding"]["coincidence_measurement"]
    print(f"contract {CONTRACT_VERSION}  (supersedes {SUPERSEDES})")
    print(f"  key                 {obk.OBLIGATION_KEY_ID}: row_uid = ob_ + "
          f"sha256(player_id, game_id, team_id)")
    print(f"  obligations         {acct['candidate_obligations']} over "
          f"{acct['candidate_games']} games; row_uid unique: {acct['row_uid_is_unique']} "
          f"({acct['candidate_distinct_row_uids']} distinct)")
    print(f"  legacy pg_uid       {acct['candidate_distinct_player_game_uids']} distinct; "
          f"{acct['obligations_sharing_a_player_game_uid']} rows share one")
    print(f"  membership          {MEMBERSHIP_BOX_INCLUDING_DNP}")
    print(f"    appeared-only counterfactual: {cf['appeared_only_rows']} rows "
          f"({cf['obligations_that_exist_only_because_dnp_rows_count']} fewer) | "
          f"matches supervisor: {cf['all_match']}")
    print(f"  roster binding      {ROSTER_BINDING_ID}; maxima coincide on "
          f"{rb['rows_where_the_two_maxima_are_the_same_instant']}/{rb['rows']} rows while "
          f"{rb['rows_where_the_RECORD_SETS_differ_in_size']} rows read different record sets")
    print(f"  cutoff identity     {ci['n_fields_compared']} fields, "
          f"{ci['games_compared']} games, ok={ci['ok']}")
    print(f"  zero-candidate tg   {acct['team_games_with_zero_candidates']} "
          f"({acct['zero_candidate_reasons']})")
    print(f"  appeared / not      {acct['candidates_appeared']} / "
          f"{acct['candidates_dnp_or_absent']}")
    print(f"\n  ROW DIFF vs v3 (obligation granularity)")
    print(f"    v3 {d['v3_rows']} -> v4 {d['v4_rows']}   ({d['net_change']:+d})")
    print(f"    v3-only {d['v3_only_count']}   v4-only {d['v4_only_count']}   "
          f"row set unchanged: {d['row_set_unchanged']}")
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
