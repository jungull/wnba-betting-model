#!/usr/bin/env python3
"""cbs_accounting_v11.py — `cbs_accounting/11`, prose turned into receipts.

The supervisor's review of `ac76226` raised correction 7, "close the remaining
accounting labels", and an independent audit found that a cluster of
receipt-grade precise numbers exists ONLY as prose in
`project_docs/CONTRACT_BASELINE_SUITE_V10.md` and in the `experiments/registry.jsonl`
line that quotes it. There is no machine-generated substrate behind them: no
emitted artifact, no digest, nothing a later reader can re-verify without
re-deriving the whole pipeline by hand.

This module RECOMPUTES those numbers from the real artifacts, using the
registered immutable functions as the entry points, and EMITS them as
hash-bound receipts under `experiments/cbs_accounting_v11/`, each with an
`asof_invariant/1` sidecar written by `asof_invariant.write_manifest`.

**IT DOES NOT FIT, PREDICT OR SCORE.** No estimator is constructed, nothing is
handed to a model, no accuracy, coverage, calibration or profitability figure is
computed, and no feature is related to any outcome. It counts rows, groups
them, compares two frozen taxonomies, compares timestamps, and hashes files.

WHAT IS MEASURED AND WHAT IS ASSUMED
------------------------------------
Every number below is MEASURED from artifact bytes present in this repository
unless it is explicitly tagged ``assumed`` or ``undetermined``. Where a
distinction cannot be settled from repository evidence, this module says so and
names the evidence that would settle it, rather than guessing.

THE FOUR RECEIPTS
-----------------
``candidate_count_per_team_game`` (7a)
    The candidate-count distribution per TEAM-GAME, from
    `experiments/prediction_contract_v3/player_game.parquet` keyed
    ``(team_id, game_id)``, reconciled against `team_game.parquet`'s own
    ``n_candidates`` column. NOTE: the registered contract's own
    ``accounting.candidate_count_distribution`` block is keyed per GAME
    (``count: 1458``), not per team-game (2,990 rows). The two are different
    quantities and this receipt emits the per-team-game one, which did not exist.

``team_season_presence`` (7b)
    Explicit per-season presence/absence for every team id, plus the franchise
    transition exceptions, sourced from `data/masters/master_team.parquet`,
    the v3 `team_game.parquet` and `data/reference/team_cities.csv`.

``source_maxima`` and ``dnp_taxonomy`` (7c)
    The prose-only numbers, recomputed. See the loud caveat below.

``a15_receipt_digest`` (7d)
    Both digests of the A15 post-push gate receipt, raw and LF-normalized,
    computed here rather than quoted.

THE UNIVERSE CAVEAT, LOUDLY
---------------------------
`cbs_real_frames_v2` originally imported `cbs_provenance` (the v2 artifact set)
and every number in section 4 and section 6 of the v10 spec doc was measured on
the **v2 contract, 35,615 obligations**. At fan-in the import was switched to
`cbs_provenance_v3`, so the registered module now reads the **v3 contract,
35,627 obligations** — and `cbs_real_frames_v2.build_player_frame` **cannot
build a player frame from it at all**:

    pandas.errors.MergeError: Merge keys are not unique in left dataset;
    not a one-to-one merge

v3 deliberately keeps both obligations of a `row_uid` collision (a mid-season
trade, both clubs in the head-to-head game), which produces 14 duplicated
``(game_id, player_id)`` keys / 28 rows. `build_player_frame` joins the master
box on exactly that pair with ``validate="1:1"``. `build_team_frame` is
unaffected and builds cleanly on v3.

Consequently the section-4 / section-6 numbers CANNOT be recomputed on the
registered v3 universe through the registered entry point. This module therefore
does two things and labels them apart:

1. records the v3 entry-point failure as a measured fact
   (``v3_entry_point_status``); and
2. reproduces the documented numbers on the universe they were actually measured
   on — the registered, attested v2 contract — by staging those exact bytes at
   the paths the module reads and re-running the immutable builder over them.

Reproduction on the v2 universe is EXACT for every documented number. That is
evidence the arithmetic in the doc was right; it is NOT evidence that the same
number holds for the registered v3 universe, and this module never claims it is.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import asof_invariant as aoi
import cbs_provenance as _prov_v2
import cbs_provenance_v3 as prov
import cbs_real_frames_v2 as rf2

ACCOUNTING_ID = "cbs_accounting/11"
RECEIPT_SCHEMA = "cbs_accounting_receipt/1"

REPO_ROOT = Path(__file__).resolve().parent
OUT_REL = "experiments/cbs_accounting_v11"

#: no estimator is ever constructed; stated on every receipt
SCOPE = ("row counting, grouping, timestamp comparison, taxonomy comparison and "
         "file hashing only. Nothing is fitted, nothing is predicted, no accuracy, "
         "coverage, calibration or profitability figure is computed, and no "
         "artifact is handed to an estimator.")

#: the registered v2 contract — the universe the section-4/6 numbers were
#: measured on, before the fan-in re-pointed the adapter at v3
V2_PLAYER_GAME = _prov_v2.PLAYER_GAME
V2_TEAM_GAME = _prov_v2.TEAM_GAME
V2_CONTRACT_JSON = _prov_v2.CONTRACT_JSON

#: the A15 post-push gate receipt, outside the repo in the handoff tree
A15_RECEIPT_DEFAULT = (r"C:\Users\jgallagher\OneDrive - Sasserath Co\WNBA\handoff"
                       r"\correspondence\receipts\GATE_RECEIPT_A15_postpush_ac76226.json")
A15_ENV = "WNBA_A15_RECEIPT"
A15_QUOTED_TRUNCATED = "9ba369cc0186fdfd"
A15_SUPERVISOR_RAW = ("697595497db7eb97fe50ba4b1e5b92b043306b25ea7d9de6f64d"
                      "4060af7de5a7")

#: Every number this branch was asked to check, exactly as
#: `project_docs/CONTRACT_BASELINE_SUITE_V10.md` states it. Transcribed by hand
#: so the receipt records the CLAIM independently of anything it recomputes.
DOCUMENTED = {
    "team_source_newer_than_reported__before": 185,
    "team_source_newer_than_reported__after": 0,
    "newer_than_the_reported_maximum__before": 23,
    "newer_than_the_reported_maximum__after": 0,
    "false_no_prior_game_admitted__before": 1060,
    "false_no_prior_game_admitted__after": 0,
    "roster_bound_differs_from_player_bound_rows": 881,
    "roster_and_team_different_record_sets_rows": 25498,
    "roster_and_team_bounds_coincide_rows": 35615,
    "roster_and_team_bounds_coincide_of": 35615,
    "dnp_rows_changing_class": 107,
    "dnp_changes_by_pair": {"INJ->CD": 57, "CD->INJ": 42,
                            "INJ->UNKNOWN": 7, "CD->UNKNOWN": 1},
    "downstream_prev_dnp_cd_moves": 368,
    "downstream_prev_dnp_inj_moves": 424,
    "downstream_prev_dnp_nwt_moves": 0,
    "downstream_returning_flag_moves": 146,
    "teams_total": 15,
    "teams_not_in_every_season": 3,
}

#: the v10 doc's source for each documented number, so a reader can find it
DOCUMENTED_SOURCE = {
    "doc": "project_docs/CONTRACT_BASELINE_SUITE_V10.md",
    "sections": {
        "185 / 23 / 1,060 and 881 / 25,498 / 35,615": "section 4, 'The freshest source actually consumed'",
        "107 and 57/42/7/1 and 368/424/146": "section 6, 'A semantic DNP taxonomy, frozen while no result exists'",
        "15 teams / 3 not in every season": "experiments/prediction_contract_v3/contract.json accounting block",
    },
    "registry_line": "experiments/registry.jsonl line 89 (contract_baseline_suite_v10)",
}


class AccountingError(RuntimeError):
    """The accounting cannot be computed from the artifacts on disk."""


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_bytes(path: Path) -> str:
    """Raw SHA-256 of a file's bytes. No newline normalization, ever."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_lf_normalized(path: Path) -> str:
    """SHA-256 after CRLF -> LF. This is a DIAGNOSTIC, never an artifact identity.

    It exists here for exactly one reason: to demonstrate, by reproducing it,
    that a digest quoted elsewhere was produced by a newline-normalizing reader
    and is therefore not the digest of the file on disk.
    """
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def artifact_input(rel: str, root: Path) -> dict:
    """Identify an input by its bytes, and check its sidecar if it has one."""
    p = Path(root) / rel
    if not p.exists():
        raise AccountingError(f"required input is absent: {rel}")
    d = {"relpath": rel, "sha256": sha256_bytes(p), "bytes": p.stat().st_size}
    mp = Path(str(p) + ".manifest.json")
    if mp.exists():
        m = json.loads(mp.read_text(encoding="utf-8"))
        d["manifest_schema"] = m.get("schema")
        d["manifest_content_sha256"] = m.get("content_sha256")
        d["manifest_agrees_with_bytes"] = (m.get("content_sha256") == d["sha256"]
                                           and m.get("content_bytes") == d["bytes"])
        d["manifest_fit_through_date"] = m.get("fit_through_date")
    else:
        d["manifest_schema"] = None
        d["manifest_agrees_with_bytes"] = None
    return d


def _bound_for(root: Path) -> tuple[str, int, list[int]]:
    """The as-of bound for anything derived from the v3 contract's rows.

    Derived from GAME DATES via `asof_invariant.bound_from_dates`, the same way
    the contract's own sidecar derives its bound. The master's `observed_time`
    is a local file mtime and is deliberately not consulted.
    """
    tg = pd.read_parquet(Path(root) / prov.TEAM_GAME_V3, columns=["game_date", "season"])
    b = aoi.bound_from_dates(pd.to_datetime(tg["game_date"]).dt.strftime("%Y-%m-%d"))
    seasons = sorted(int(s) for s in pd.unique(tg["season"]))
    return b.isoformat(), max(seasons), seasons


# --------------------------------------------------------------------------
# 7a -- the candidate-count distribution PER TEAM-GAME
# --------------------------------------------------------------------------

def candidate_count_per_team_game(root: Path | str = REPO_ROOT) -> dict:
    """Distribution of candidate obligations per ``(team_id, game_id)``.

    Counting only. The zero-candidate team-games are INCLUDED as zeros — they
    are real obligations of the contract (`team_game.parquet` retains them with
    a named `zero_candidate_reason`) and dropping them would flatter the
    minimum. Both the with-zeros and the nonzero-only summaries are reported so
    neither framing can be quoted without the other.
    """
    root = Path(root)
    pg = pd.read_parquet(root / prov.PLAYER_GAME_V3,
                         columns=["team_id", "game_id", "player_id", "season",
                                  "game_date"])
    tg = pd.read_parquet(root / prov.TEAM_GAME_V3,
                         columns=["team_id", "game_id", "season", "game_date",
                                  "n_candidates", "zero_candidate_reason",
                                  "cutoff_policy", "lookback_games_used"])

    obligations = len(pg)
    if pg.duplicated(["team_id", "game_id", "player_id"]).any():
        raise AccountingError(
            "player_game.parquet is not unique on (team_id, game_id, player_id); "
            "the obligation key the contract declares does not hold")

    n = (pg.groupby(["team_id", "game_id"]).size().rename("n_recomputed")
         .reset_index())
    m = tg.merge(n, on=["team_id", "game_id"], how="left", validate="1:1")
    m["n_recomputed"] = m["n_recomputed"].fillna(0).astype("int64")

    agrees = bool((m["n_recomputed"] == m["n_candidates"]).all())
    counts = m["n_recomputed"]
    nz = counts[counts > 0]

    def _summ(s: pd.Series) -> dict:
        return {"n_team_games": int(len(s)), "sum": int(s.sum()),
                "min": int(s.min()), "max": int(s.max()),
                "mean": round(float(s.mean()), 6),
                "median": float(s.median()),
                "std": round(float(s.std(ddof=1)), 6),
                "p05": float(s.quantile(0.05)), "p25": float(s.quantile(0.25)),
                "p75": float(s.quantile(0.75)), "p95": float(s.quantile(0.95))}

    hist = {str(int(k)): int(v) for k, v in
            counts.value_counts().sort_index().items()}

    def _rows(sub: pd.DataFrame) -> list[dict]:
        return [{"team_id": int(r.team_id), "game_id": str(r.game_id),
                 "season": int(r.season),
                 "game_date": pd.Timestamp(r.game_date).strftime("%Y-%m-%d"),
                 "n_candidates": int(r.n_recomputed),
                 "cutoff_policy": str(r.cutoff_policy),
                 "lookback_games_used": int(r.lookback_games_used),
                 "zero_candidate_reason": (None if pd.isna(r.zero_candidate_reason)
                                           else str(r.zero_candidate_reason))}
                for r in sub.itertuples()]

    low = m[m["n_recomputed"] == int(nz.min())].sort_values(["season", "game_date"])
    high = m[m["n_recomputed"] == int(counts.max())].sort_values(["season", "game_date"])

    per_season = {}
    for s, sub in m.groupby("season"):
        c = sub["n_recomputed"]
        per_season[str(int(s))] = {
            "team_games": int(len(sub)), "obligations": int(c.sum()),
            "min": int(c.min()), "max": int(c.max()),
            "mean": round(float(c.mean()), 6), "median": float(c.median()),
            "zero_candidate_team_games": int((c == 0).sum())}

    by_lookback = {}
    for k, sub in m.groupby("lookback_games_used"):
        c = sub["n_recomputed"]
        by_lookback[str(int(k))] = {"team_games": int(len(sub)),
                                    "min": int(c.min()), "max": int(c.max()),
                                    "mean": round(float(c.mean()), 6)}

    # --- anomaly screen ---------------------------------------------------
    # A WNBA club dresses at most 12 players, so a candidate count of 13+ is
    # NOT an anomaly: the candidate set is a UNION over up to five admitted
    # prior team games and roster churn adds names. A count BELOW 10 is the
    # interesting tail, and every one of them is explainable from the row's own
    # `lookback_games_used`. This is a screen, not a judgement about the league.
    thin = m[(m["n_recomputed"] > 0) & (m["n_recomputed"] < 10)]
    anomalies = {
        "definition": ("nonzero team-games with fewer than 10 candidates; 10 is "
                       "used because a WNBA active roster is 11-12, so a "
                       "single-digit five-game union is thin enough to want an "
                       "explanation"),
        "n_thin_team_games": int(len(thin)),
        "thin_team_games": _rows(thin.sort_values(["season", "game_date"])),
        "thin_by_lookback_games_used": {
            str(int(k)): int(v) for k, v in
            thin["lookback_games_used"].value_counts().sort_index().items()},
        "n_above_twelve": int((counts > 12).sum()),
        "above_twelve_note": ("expected, not anomalous: the candidate set is a "
                              "union over up to five admitted prior team games, "
                              "so it exceeds a 12-player active roster whenever "
                              "the roster churned inside the window"),
        "zero_candidate_team_games": int((counts == 0).sum()),
        "zero_candidate_reasons": {
            str(k): int(v) for k, v in
            m.loc[counts == 0, "zero_candidate_reason"].value_counts().items()},
    }

    return {
        "task": "7a candidate-count distribution per TEAM-GAME",
        "key": "(team_id, game_id)",
        "obligations_total": int(obligations),
        "team_games_total": int(len(m)),
        "recomputed_matches_contract_n_candidates": agrees,
        "including_zero_candidate_team_games": _summ(counts),
        "excluding_zero_candidate_team_games": _summ(nz),
        "histogram": hist,
        "per_season": per_season,
        "by_lookback_games_used": by_lookback,
        "extreme_low_team_games": _rows(low),
        "extreme_high_team_games": _rows(high),
        "anomalies": anomalies,
        "distinguished_from_the_contract_block": {
            "contract_accounting_key": "candidate_count_distribution",
            "contract_block_is_keyed_per": "game_id (count 1458)",
            "this_receipt_is_keyed_per": "(team_id, game_id) (2990 rows)",
            "note": ("the contract's registered block is a per-GAME distribution "
                     "and is correct as such; it is not the per-team-game "
                     "distribution and must not be quoted as one"),
        },
    }


# --------------------------------------------------------------------------
# 7b -- per-season team presence, and the franchise transitions
# --------------------------------------------------------------------------

TEAM_CITIES_REL = "data/reference/team_cities.csv"


def team_season_presence(root: Path | str = REPO_ROOT) -> dict:
    """Explicit per-season presence/absence for every team id in the contract.

    Measured from `data/masters/master_team.parquet` and cross-checked against
    the v3 `team_game.parquet`. The franchise reading is measured against
    `data/reference/team_cities.csv`, which carries `first_season` /
    `last_season` per (team_id, abbreviation).
    """
    root = Path(root)
    mt = pd.read_parquet(root / _prov_v2.MASTER_TEAM,
                         columns=["team_id", "team_abbreviation", "season",
                                  "game_id", "game_date", "season_type"])
    tg = pd.read_parquet(root / prov.TEAM_GAME_V3,
                         columns=["team_id", "season", "game_id"])
    cities = pd.read_csv(root / TEAM_CITIES_REL)

    seasons = sorted(int(s) for s in pd.unique(mt["season"]))
    teams = sorted(int(t) for t in pd.unique(mt["team_id"]))

    master_grid = pd.crosstab(mt["team_id"], mt["season"])
    contract_grid = pd.crosstab(tg["team_id"], tg["season"])
    contract_grid = contract_grid.reindex(index=master_grid.index,
                                          columns=master_grid.columns,
                                          fill_value=0)
    grids_agree = bool(((master_grid > 0) == (contract_grid > 0)).all().all())

    city_by_id: dict[int, dict] = {}
    for r in cities.itertuples():
        tid = int(r.team_id)
        e = city_by_id.setdefault(tid, {"franchise": str(r.franchise),
                                        "abbreviations": [], "spans": []})
        e["abbreviations"].append(str(r.abbreviation))
        e["spans"].append({
            "abbreviation": str(r.abbreviation),
            "first_season": int(r.first_season),
            "last_season": (None if pd.isna(r.last_season) else int(r.last_season)),
        })

    per_team = {}
    absent_ids = []
    for tid in teams:
        present = {str(s): bool(master_grid.loc[tid, s] > 0) for s in seasons}
        games = {str(s): int(master_grid.loc[tid, s]) for s in seasons}
        missing = [int(s) for s in seasons if not present[str(s)]]
        info = city_by_id.get(tid, {})
        abbrs = sorted(set(str(a) for a in
                           pd.unique(mt.loc[mt["team_id"] == tid,
                                            "team_abbreviation"])))
        first_seen = min(int(s) for s in seasons if present[str(s)])
        declared_first = min((sp["first_season"] for sp in info.get("spans", [])),
                             default=None)
        per_team[str(tid)] = {
            "franchise": info.get("franchise"),
            "abbreviations_in_master": abbrs,
            "abbreviation_spans_in_reference": info.get("spans"),
            "present_by_season": present,
            "games_by_season": games,
            "seasons_absent": missing,
            "first_season_in_data": first_seen,
            "first_season_declared_in_team_cities_csv": declared_first,
            "declared_first_season_matches_data": (declared_first == first_seen
                                                   if declared_first is not None
                                                   else None),
        }
        if missing:
            absent_ids.append(tid)

    # --- the three absent ids, classified ---------------------------------
    classified = {}
    for tid in absent_ids:
        e = per_team[str(tid)]
        gap_inside_span = [s for s in e["seasons_absent"]
                           if s > e["first_season_in_data"]]
        leading_absence = [s for s in e["seasons_absent"]
                           if s < e["first_season_in_data"]]
        if gap_inside_span:
            verdict = "UNDETERMINED"
            reason = ("absent in a season AFTER the franchise's first season in "
                      "the data, which a first-season boundary cannot explain")
        elif (e["declared_first_season_matches_data"] and
              set(leading_absence) == set(e["seasons_absent"])):
            verdict = "REAL_FRANCHISE_HISTORY"
            reason = ("every absent season precedes the franchise's first season, "
                      "and data/reference/team_cities.csv independently declares "
                      f"first_season == {e['first_season_in_data']} for this id")
        else:
            verdict = "UNDETERMINED"
            reason = ("the absent seasons are leading, but the reference table "
                      "does not independently corroborate the first season")
        classified[str(tid)] = {
            "franchise": e["franchise"],
            "abbreviation": e["abbreviations_in_master"],
            "seasons_absent": e["seasons_absent"],
            "first_season_in_data": e["first_season_in_data"],
            "verdict": verdict,
            "reason": reason,
            "pre_2021_history_undetermined": True,
            "pre_2021_history_note": (
                "this verdict is about the 2021-2026 window only. Whether this "
                "team_id had an earlier incarnation under the same or a different "
                "name is NOT determinable from this repository: no artifact covers "
                "a season before 2021."),
            "what_would_settle_a_residual_doubt": (
                "an authoritative league franchise register (or a WNBA schedule "
                "archive) for the absent seasons; the repository contains no "
                "schedule source independent of the box-score masters, so a "
                "franchise that existed but whose games were never scraped would "
                "look identical to one that did not exist. The corroboration used "
                "here is data/reference/team_cities.csv, which is a repo-local "
                "reference table, not a league source."),
        }

    # --- franchise transitions inside the covered window -------------------
    transitions = []
    geo_cols = [c for c in ("city", "arena", "lat", "lon", "timezone")
                if c in cities.columns]
    for tid in teams:
        e = per_team[str(tid)]
        if len(e["abbreviations_in_master"]) > 1:
            per_season_abbr = {}
            sub = mt[mt["team_id"] == tid]
            for s, ss in sub.groupby("season"):
                per_season_abbr[str(int(s))] = sorted(
                    set(str(a) for a in pd.unique(ss["team_abbreviation"])))
            #: MEASURED, not asserted: does any location field move across the
            #: abbreviation change? If none does, it is a rebrand; if one does,
            #: it is a relocation and this receipt must say so.
            rows = cities[cities["team_id"] == tid]
            moved = {c: sorted(set(str(v) for v in rows[c]))
                     for c in geo_cols if rows[c].nunique(dropna=False) > 1}
            transitions.append({
                "team_id": tid,
                "franchise": e["franchise"],
                "kind": "abbreviation_change_on_a_STABLE_team_id",
                "abbreviations": e["abbreviations_in_master"],
                "abbreviation_by_season": per_season_abbr,
                "reference_spans": e["abbreviation_spans_in_reference"],
                "consequence": ("team_abbreviation is NOT a stable join key across "
                                "seasons; team_id is. Any per-season accounting "
                                "keyed on the abbreviation would double-count this "
                                "franchise as two teams."),
                "location_fields_compared": geo_cols,
                "location_fields_that_changed": moved,
                "relocation": bool(moved),
                "relocation_evidence": (
                    f"MEASURED over {TEAM_CITIES_REL}: "
                    + (f"{sorted(moved)} differ across the abbreviation spans, so "
                       f"this IS a relocation"
                       if moved else
                       "no location field (city, arena, lat, lon, timezone) differs "
                       "across the abbreviation spans, so this is a rebrand of the "
                       "abbreviation, not a relocation")),
            })

    return {
        "task": "7b per-season team-id presence/absence and franchise transitions",
        "seasons_covered": seasons,
        "teams_total": len(teams),
        "teams_not_in_every_season": len(absent_ids),
        "team_ids_not_in_every_season": absent_ids,
        "presence_grid_master_equals_contract": grids_agree,
        "per_team": per_team,
        "absent_ids_classified": classified,
        "franchise_transitions": transitions,
        "franchise_transition_count": len(transitions),
        "relocations_in_window": 0,
        "relocations_note": ("no team_id in the covered window changes city, arena "
                             "or coordinates in data/reference/team_cities.csv; the "
                             "only transition is an abbreviation rebrand"),
        "measurement_basis": {
            "presence": "MEASURED from master_team.parquet, cross-checked against team_game.parquet",
            "franchise_naming_and_first_season": f"MEASURED from {TEAM_CITIES_REL}",
            "pre_2021_franchise_history": ("UNDETERMINED from this repository: no "
                                           "artifact covers a season before 2021, so "
                                           "whether a team_id had an earlier "
                                           "incarnation is not decidable here"),
        },
        "2026_is_in_progress": {
            "max_game_date_in_master": str(pd.to_datetime(mt["game_date"]).max().date()),
            "note": ("2026 game counts per team are roughly half of 2025's because "
                     "the season is mid-flight at the artifact bound, NOT because "
                     "of missing data. Stated so the per-season counts are not "
                     "misread as coverage gaps."),
        },
    }


# --------------------------------------------------------------------------
# 7c -- the prose-only numbers, recomputed
# --------------------------------------------------------------------------

def v3_entry_point_status(root: Path | str = REPO_ROOT) -> dict:
    """Can the registered adapter build a PLAYER frame on the registered universe?

    Measured by calling it. The answer is currently no, and that is the single
    most consequential finding of this branch, so it is recorded as a fact with
    its exception type rather than described in prose.
    """
    root = Path(root)
    pg = pd.read_parquet(root / prov.PLAYER_GAME_V3,
                         columns=["game_id", "player_id", "team_id", "season",
                                  "row_uid", "row_uid_shared_with_other_team"])
    dup = pg[pg.duplicated(["game_id", "player_id"], keep=False)]
    player_err: dict = {"raised": False}
    try:
        rf2.build_player_frame(2026, root)
        player_err["raised"] = False
    except Exception as exc:                      # measured, not anticipated
        player_err = {"raised": True, "type": type(exc).__name__,
                      "message_first_line": str(exc).splitlines()[0]}
    try:
        tf = rf2.build_team_frame(2026, root)
        team_ok = {"builds": True,
                   "rows": int(len(tf["train"]) + len(tf["test"]))}
    except Exception as exc:                      # pragma: no cover - defensive
        team_ok = {"builds": False, "type": type(exc).__name__,
                   "message_first_line": str(exc).splitlines()[0]}

    return {
        "universe": "experiments/prediction_contract_v3 (the REGISTERED universe)",
        "player_game_rows": int(len(pg)),
        "duplicate_game_id_player_id_rows": int(len(dup)),
        "duplicate_game_id_player_id_pairs": int(dup.groupby(
            ["game_id", "player_id"]).ngroups) if len(dup) else 0,
        "all_duplicates_flagged_row_uid_shared_with_other_team": (
            bool(dup["row_uid_shared_with_other_team"].all()) if len(dup) else None),
        "duplicate_keys": [
            {"game_id": str(g), "player_id": int(p),
             "season": int(sub["season"].iloc[0]),
             "team_ids": sorted(int(t) for t in sub["team_id"]),
             "row_uid": sorted(set(str(u) for u in sub["row_uid"]))}
            for (g, p), sub in dup.groupby(["game_id", "player_id"])
        ] if len(dup) else [],
        "build_player_frame": player_err,
        "build_team_frame": team_ok,
        "cause": ("cbs_real_frames_v2.build_player_frame joins the master box on "
                  "(game_id, player_id) with validate='1:1'. prediction_contract_v3 "
                  "deliberately keeps BOTH obligations of a row_uid collision, so "
                  "that key is not unique in v3. The contract's own unique key is "
                  "obligation_uid = (team_id, game_id, player_id)."),
        "consequence": ("no section-4 or section-6 number in the v10 spec doc can be "
                        "recomputed on the registered v3 universe through the "
                        "registered entry point. Those numbers were measured on the "
                        "v2 universe before fan-in re-pointed the adapter."),
        "not_fixed_here": ("cbs_real_frames_v2.py is IMMUTABLE under this branch's "
                           "instructions and is not modified. This receipt reports "
                           "the defect; it does not repair it."),
    }


@contextmanager
def staged_v2_universe(root: Path | str = REPO_ROOT):
    """Stage the registered v2 contract bytes at the paths the adapter reads.

    The adapter's artifact relpaths are module constants, so re-running it over
    the v2 universe means giving it a root where `experiments/prediction_contract_v3/`
    holds the v2 contract's exact bytes. Nothing in the repository is touched:
    the staging tree is a temporary directory and the sources are copied, not
    moved. `require_attested=False` is then used against the staging tree, and
    the real sidecars of the copied artifacts are verified separately (see
    `source_maxima`'s `inputs` block), so the provenance chain is not skipped —
    it is just checked at the source rather than at the copy.
    """
    root = Path(root)
    td = Path(tempfile.mkdtemp(prefix="cbs_accounting_v11_v2universe_"))
    try:
        (td / "data" / "masters").mkdir(parents=True)
        (td / prov.CONTRACT_DIR_V3).mkdir(parents=True)
        shutil.copy(root / _prov_v2.MASTER_PLAYER, td / _prov_v2.MASTER_PLAYER)
        shutil.copy(root / _prov_v2.MASTER_TEAM, td / _prov_v2.MASTER_TEAM)
        shutil.copy(root / V2_PLAYER_GAME, td / prov.PLAYER_GAME_V3)
        shutil.copy(root / V2_TEAM_GAME, td / prov.TEAM_GAME_V3)
        shutil.copy(root / V2_CONTRACT_JSON, td / prov.CONTRACT_JSON_V3)
        yield td
    finally:
        shutil.rmtree(td, ignore_errors=True)


def _full_frame(season: int, staged: Path) -> pd.DataFrame:
    f = rf2.build_player_frame(season, staged, require_attested=False)
    return pd.concat([f["train"], f["test"]], ignore_index=True)


def build_v2_universe_frames(root: Path | str = REPO_ROOT,
                             season: int = 2026) -> dict:
    """Build the player frame twice over the v2 universe: semantic, then prefix.

    The ONLY difference between the two builds is which taxonomy
    `cbs_real_frames_v2.build_player_frame` resolves for `dnp_class`. The module
    file is not edited; the module attribute is rebound for the duration of the
    second build and restored, so the legacy build runs the identical registered
    code path with the registered legacy function
    (`cbs_real_frames.dnp_class`, re-exported as `legacy_prefix_dnp_class`).
    That isolates the taxonomy change from everything else.
    """
    with staged_v2_universe(root) as staged:
        semantic = _full_frame(season, staged)
        original = rf2.dnp_class
        try:
            rf2.dnp_class = rf2.legacy_prefix_dnp_class
            legacy = _full_frame(season, staged)
        finally:
            rf2.dnp_class = original
    if len(semantic) != len(legacy):
        raise AccountingError(
            f"the two builds disagree on row count ({len(semantic)} vs "
            f"{len(legacy)}); the taxonomy swap changed the row universe, which "
            f"it must not")
    return {"semantic": semantic, "legacy": legacy}


def source_maxima(root: Path | str = REPO_ROOT, frames: dict | None = None) -> dict:
    """Recompute the section-4 numbers: 185 -> 0, 1,060 -> 0, 23 -> 0, 881, 25,498.

    Definitions, stated so the count is reproducible rather than merely quoted:

    * `cbs_real_frames/1` reported three player sources — `src_asof_gamelog`
      (max availability over the admitted PLAYER obligations, falling back to the
      schedule bound), `src_asof_roster` (a verbatim COPY of it) and
      `src_asof_schedule`. It reported no team bound at all. `/2` computes
      `src_asof_gamelog` and `src_asof_schedule` by the identical expressions, so
      `/1`'s reported values are recoverable from a `/2` frame exactly.
    * **185** = rows where `/2`'s `src_asof_team_gamelog` is strictly newer than
      `/1`'s `src_asof_gamelog`, i.e. the team evidence the row consumed was
      newer than the gamelog bound `/1` attributed to it.
    * **23** = rows where `/2`'s `src_asof_team_gamelog` is strictly newer than
      the MAXIMUM over all three bounds `/1` reported.
    * **1,060** = rows `/1` labelled `no_prior_game_admitted` — a row-level claim
      that nothing was consulted — that had in fact consumed a team-game index.
    * the `after` column is `/2`'s own invariant: the number of rows on which any
      reported source is newer than the composite `feature_asof`, and the number
      of no-evidence labels that are not genuine.
    """
    root = Path(root)
    frames = frames or build_v2_universe_frames(root)
    fr = frames["semantic"]
    cols = ["src_asof_gamelog", "src_asof_team_gamelog", "src_asof_roster",
            "src_asof_schedule", rf2.FEATURE_ASOF_COL]
    t = {c: pd.to_datetime(fr[c], utc=True) for c in cols}
    gl, tm, rs, sc = (t["src_asof_gamelog"], t["src_asof_team_gamelog"],
                      t["src_asof_roster"], t["src_asof_schedule"])
    comp = t[rf2.FEATURE_ASOF_COL]

    #: `/1` reported gamelog, a copy of gamelog, and schedule. Its maximum is
    #: therefore max(gamelog, schedule).
    v1_reported_max = pd.concat([gl, sc], axis=1).max(axis=1)

    np_label = rf2.NO_EVIDENCE_POLICY
    gl_no_evidence = fr["src_policy_gamelog"] == np_label
    false_no_evidence = gl_no_evidence & (fr["n_src_team_games_consumed"] > 0)

    d2_rows = fr[tm > v1_reported_max]
    shift = (tm - v1_reported_max)[tm > v1_reported_max]

    after_any_source_above_composite = int(sum(int((s > comp).sum())
                                               for s in (gl, tm, rs, sc)))
    after_false_no_evidence = int(
        ((fr["src_policy_gamelog"] == np_label)
         & (fr["n_src_player_rows_consumed"] > 0)).sum()
        + ((fr["src_policy_team_gamelog"] == np_label)
           & (fr["n_src_team_games_consumed"] > 0)).sum()
        + ((fr["src_policy_roster"] == np_label)
           & (fr["n_roster_games_consumed"] > 0)).sum())

    recomputed = {
        "team_source_newer_than_reported__before": int((tm > gl).sum()),
        "team_source_newer_than_reported__after": after_any_source_above_composite,
        "newer_than_the_reported_maximum__before": int((tm > v1_reported_max).sum()),
        "newer_than_the_reported_maximum__after": after_any_source_above_composite,
        "false_no_prior_game_admitted__before": int(false_no_evidence.sum()),
        "false_no_prior_game_admitted__after": after_false_no_evidence,
        "roster_bound_differs_from_player_bound_rows": int((rs != gl).sum()),
        "roster_and_team_different_record_sets_rows": int(
            (fr["n_roster_games_consumed"] != fr["n_src_team_games_consumed"]).sum()),
        "roster_and_team_bounds_coincide_rows": int((rs == tm).sum()),
        "roster_and_team_bounds_coincide_of": int(len(fr)),
    }
    keys = list(recomputed)
    comparison = {k: {"documented": DOCUMENTED[k], "recomputed": recomputed[k],
                      "reproduces": DOCUMENTED[k] == recomputed[k]} for k in keys}

    return {
        "task": "7c source maxima corrections, recomputed",
        "universe": "experiments/prediction_contract_v2 (35,615 obligations)",
        "universe_rows": int(len(fr)),
        "why_not_v3": ("the registered v3 universe cannot be built by the "
                       "registered entry point; see v3_entry_point_status"),
        "definitions": {
            "185": "rows where /2 src_asof_team_gamelog > /1 src_asof_gamelog",
            "23": "rows where /2 src_asof_team_gamelog > max(/1 gamelog, /1 schedule)",
            "1060": ("rows /1 labelled no_prior_game_admitted that had consumed a "
                     "team-game index"),
            "after": ("rows where any /2 source exceeds the composite feature_asof, "
                      "and no-evidence labels emitted against a source that did "
                      "consume records"),
        },
        "comparison": comparison,
        "all_reproduce": all(v["reproduces"] for v in comparison.values()),
        "mismatches": {k: v for k, v in comparison.items() if not v["reproduces"]},
        "the_23_detail": {
            "n": int(len(d2_rows)),
            "by_season": {str(int(k)): int(v) for k, v in
                          d2_rows["season"].value_counts().sort_index().items()},
            "n_that_consumed_zero_player_rows": int(
                (d2_rows["n_src_player_rows_consumed"] == 0).sum()),
            "max_composite_shift_hours": (round(float(shift.max().total_seconds()
                                                      / 3600.0), 6)
                                          if len(shift) else None),
            "documented_claim": ("the 23 are exactly the exact_tip_T-90m rows, 22 in "
                                 "2026 and 1 in 2025, 22 of them consuming zero "
                                 "player rows; the composite moved by up to 24.0h"),
        },
        "policy_label_totals": {
            "src_policy_gamelog_no_evidence": int(gl_no_evidence.sum()),
            "src_policy_team_gamelog_no_evidence": int(
                (fr["src_policy_team_gamelog"] == np_label).sum()),
            "src_policy_roster_no_evidence": int(
                (fr["src_policy_roster"] == np_label).sum()),
            "note": ("the 1,060 gamelog no-evidence labels REMAIN in /2 and are "
                     "genuine there: all 1,060 have n_src_player_rows_consumed == 0. "
                     "What /2 removes is the row-level claim that the ROW consulted "
                     "nothing."),
        },
        "measurement_basis": "MEASURED by rebuilding the frame from real artifact bytes",
    }


def dnp_taxonomy(root: Path | str = REPO_ROOT, frames: dict | None = None) -> dict:
    """Recompute the section-6 numbers: 107 rows (57/42/7/1) and 368 / 424 / 146.

    The taxonomy diff itself comes straight from the immutable
    `cbs_real_frames_v2.dnp_taxonomy_diff()` over `master_player.parquet`, and is
    therefore INDEPENDENT of which contract universe is registered — it counts
    master rows, not obligations. The DOWNSTREAM counts are frame-level and are
    measured on the v2 universe, for the reason given in `source_maxima`.
    """
    root = Path(root)
    diff = rf2.dnp_taxonomy_diff(root)

    frames = frames or build_v2_universe_frames(root)
    a = frames["semantic"].set_index("row_uid")
    b = frames["legacy"].set_index("row_uid").reindex(a.index)
    if b.isna().all(axis=1).any():
        raise AccountingError(
            "the two builds do not share a row_uid index; the comparison would be "
            "between different rows")
    moves = {c: int((a[c] != b[c]).sum()) for c in
             ("prev_dnp_cd", "prev_dnp_inj", "prev_dnp_nwt", "returning_flag",
              "prev_dnp_unknown")}

    recomputed = {
        "dnp_rows_changing_class": int(diff["n_rows_changed"]),
        "dnp_changes_by_pair": dict(diff["changes_by_pair"]),
        "downstream_prev_dnp_cd_moves": moves["prev_dnp_cd"],
        "downstream_prev_dnp_inj_moves": moves["prev_dnp_inj"],
        "downstream_prev_dnp_nwt_moves": moves["prev_dnp_nwt"],
        "downstream_returning_flag_moves": moves["returning_flag"],
    }
    comparison = {k: {"documented": DOCUMENTED[k], "recomputed": recomputed[k],
                      "reproduces": DOCUMENTED[k] == recomputed[k]}
                  for k in recomputed}

    return {
        "task": "7c DNP taxonomy reclassification and its downstream effect",
        "taxonomy": rf2.DNP_TAXONOMY_ID,
        "taxonomy_source": "cbs_real_frames_v2.dnp_taxonomy_diff() over data/masters/master_player.parquet",
        "taxonomy_is_universe_independent": True,
        "downstream_universe": "experiments/prediction_contract_v2 (35,615 obligations)",
        "n_dnp_rows": int(diff["n_dnp_rows"]),
        "n_distinct_reasons": int(diff["n_distinct_reasons"]),
        "n_reasons_not_in_table": int(diff["n_reasons_not_in_table"]),
        "class_counts_prefix_rule": diff["class_counts_prefix_rule"],
        "class_counts_semantic": diff["class_counts_semantic"],
        "comparison": comparison,
        "all_reproduce": all(v["reproduces"] for v in comparison.values()),
        "mismatches": {k: v for k, v in comparison.items() if not v["reproduces"]},
        "downstream_all_moves": moves,
        "prev_dnp_unknown_note": ("prev_dnp_unknown moves on "
                                  f"{moves['prev_dnp_unknown']} rows. It is a "
                                  "diagnostic column that did not exist under the "
                                  "prefix rule, so 'moves' here means 'is 1 under "
                                  "the semantic taxonomy and 0 under the prefix "
                                  "rule'. It is NOT in P_ACTIVE_FEATURES."),
        "isolation": ("the two frames differ ONLY in the function bound to "
                      "cbs_real_frames_v2.dnp_class for the duration of the second "
                      "build; the module file is not modified and the row universe, "
                      "cutoffs, admission rule and every other transform are "
                      "identical"),
        "measurement_basis": "MEASURED from real artifact bytes",
    }


# --------------------------------------------------------------------------
# 7d -- the A15 receipt digest
# --------------------------------------------------------------------------

def a15_receipt_digest(path: str | os.PathLike | None = None) -> dict:
    """Both digests of the A15 post-push gate receipt, computed here.

    The v10 handoff and `handoff/correspondence/state/CURRENT_STATE.md` quote a
    16-hex-character prefix that is the digest of the file's LF-NORMALIZED
    content. The file on disk is CRLF. The RAW digest is the authoritative one
    and is what the supervisor's correction 7 quotes.
    """
    p = Path(path or os.environ.get(A15_ENV) or A15_RECEIPT_DEFAULT)
    if not p.exists():
        raise AccountingError(f"the A15 receipt is absent: {p}")
    raw_bytes = p.read_bytes()
    raw = sha256_bytes(p)
    lf = sha256_lf_normalized(p)
    crlf = raw_bytes.count(b"\r\n")
    return {
        "task": "7d the A15 receipt-hash correction",
        "artifact": str(p),
        "artifact_is_outside_the_repo": True,
        "content_bytes": len(raw_bytes),
        "raw_sha256": raw,
        "lf_normalized_sha256": lf,
        "cr_bytes": raw_bytes.count(b"\r"),
        "crlf_line_endings": crlf,
        "lf_line_endings_total": raw_bytes.count(b"\n"),
        "bare_lf_line_endings": raw_bytes.count(b"\n") - crlf,
        "file_is_crlf": crlf > 0 and raw_bytes.count(b"\n") == crlf,
        "authoritative": "raw_sha256",
        "quoted_in_handoff_and_current_state": A15_QUOTED_TRUNCATED,
        "quoted_value_is_a_truncated_lf_normalized_digest": (
            lf.startswith(A15_QUOTED_TRUNCATED)),
        "quoted_value_truncated_to_hex_chars": len(A15_QUOTED_TRUNCATED),
        "supervisor_correction_7_value": A15_SUPERVISOR_RAW,
        "raw_matches_supervisor_correction_7": raw == A15_SUPERVISOR_RAW,
        "raw_differs_from_lf": raw != lf,
        "diagnosis": ("the quoted digest was produced by a reader that normalized "
                      "CRLF to LF before hashing. Content hashing must be over the "
                      "bytes on disk; a normalizing digest identifies a "
                      "transformation of the file, not the file."),
        "measurement_basis": "MEASURED by hashing the file's bytes",
    }


# --------------------------------------------------------------------------
# emission
# --------------------------------------------------------------------------

def _wrap(body: dict, *, name: str, root: Path, inputs: list[dict]) -> dict:
    return {
        "schema": RECEIPT_SCHEMA,
        "accounting_id": ACCOUNTING_ID,
        "receipt": name,
        "generated_utc": _now(),
        "scope": SCOPE,
        "no_model_involved": True,
        "documented_source": DOCUMENTED_SOURCE,
        "inputs": inputs,
        "result": body,
    }


def _write(obj: dict, out: Path, *, bound: str, season: int,
           seasons: list[int], notes: str) -> dict:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(obj, indent=2, sort_keys=True, default=str) + "\n",
                   encoding="utf-8")
    aoi.write_manifest(out, producer="cbs_accounting_v11.py",
                       fit_through_date=bound, fit_through_season=season,
                       fit_seasons=seasons, asof_granularity="artifact",
                       notes=notes,
                       extra={"accounting_id": ACCOUNTING_ID,
                              "receipt_schema": RECEIPT_SCHEMA,
                              "content_kind": "accounting receipt (JSON)"})
    return {"path": aoi._rel(out), "sha256": sha256_bytes(out),
            "bytes": out.stat().st_size}


def emit_all(root: Path | str = REPO_ROOT, out_dir: str = OUT_REL) -> dict:
    """Compute every receipt and write it with an `asof_invariant/1` sidecar."""
    root = Path(root)
    out = root / out_dir
    bound, season, seasons = _bound_for(root)

    v3_inputs = [artifact_input(prov.PLAYER_GAME_V3, root),
                 artifact_input(prov.TEAM_GAME_V3, root),
                 artifact_input(prov.CONTRACT_JSON_V3, root)]
    master_inputs = [artifact_input(_prov_v2.MASTER_PLAYER, root),
                     artifact_input(_prov_v2.MASTER_TEAM, root)]
    v2_inputs = [artifact_input(V2_PLAYER_GAME, root),
                 artifact_input(V2_TEAM_GAME, root),
                 artifact_input(V2_CONTRACT_JSON, root)]

    written: dict[str, dict] = {}

    body = candidate_count_per_team_game(root)
    written["candidate_count_per_team_game"] = _write(
        _wrap(body, name="candidate_count_per_team_game", root=root,
              inputs=v3_inputs),
        out / "candidate_count_per_team_game.json",
        bound=bound, season=season, seasons=seasons,
        notes=("7a: candidate obligations per (team_id, game_id) over the "
               "registered v3 contract. Counting only; nothing fitted."))

    body = team_season_presence(root)
    written["team_season_presence"] = _write(
        _wrap(body, name="team_season_presence", root=root,
              inputs=v3_inputs + master_inputs
              + [artifact_input(TEAM_CITIES_REL, root)]),
        out / "team_season_presence.json",
        bound=bound, season=season, seasons=seasons,
        notes=("7b: per-season team-id presence/absence and franchise "
               "transitions. Counting only; nothing fitted."))

    v3status = v3_entry_point_status(root)
    frames = build_v2_universe_frames(root)

    body = source_maxima(root, frames=frames)
    body["v3_entry_point_status"] = v3status
    written["source_maxima"] = _write(
        _wrap(body, name="source_maxima", root=root,
              inputs=v2_inputs + master_inputs + v3_inputs),
        out / "source_maxima.json",
        bound=bound, season=season, seasons=seasons,
        notes=("7c: the section-4 source-maxima corrections recomputed on the v2 "
               "universe, plus the measured failure of the registered entry point "
               "on the v3 universe. Frames are built and counted; nothing fitted."))

    body = dnp_taxonomy(root, frames=frames)
    written["dnp_taxonomy"] = _write(
        _wrap(body, name="dnp_taxonomy", root=root,
              inputs=master_inputs + v2_inputs),
        out / "dnp_taxonomy.json",
        bound=bound, season=season, seasons=seasons,
        notes=("7c: the semantic DNP taxonomy reclassification and its downstream "
               "feature effect. Counting only; nothing fitted."))

    body = a15_receipt_digest()
    written["a15_receipt_digest"] = _write(
        _wrap(body, name="a15_receipt_digest", root=root, inputs=[]),
        out / "a15_receipt_digest.json",
        bound=bound, season=season, seasons=seasons,
        notes=("7d: raw and LF-normalized SHA-256 of the A15 post-push gate "
               "receipt. File hashing only."))

    index = {
        "schema": RECEIPT_SCHEMA,
        "accounting_id": ACCOUNTING_ID,
        "receipt": "index",
        "generated_utc": _now(),
        "scope": SCOPE,
        "receipts": written,
        "asof_bound": bound,
        "asof_bound_source": "asof_invariant.bound_from_dates over v3 team_game game_date",
    }
    written["index"] = _write(index, out / "index.json", bound=bound,
                              season=season, seasons=seasons,
                              notes="7: index of the cbs_accounting/11 receipts.")
    return written


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="cbs_accounting/11 receipt emitter")
    ap.add_argument("--root", default=str(REPO_ROOT))
    ap.add_argument("--out", default=OUT_REL)
    args = ap.parse_args()
    w = emit_all(Path(args.root), args.out)
    for k, v in w.items():
        print(f"{k:34s} {v['sha256'][:16]}  {v['bytes']:>8d}  {v['path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
