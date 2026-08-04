#!/usr/bin/env python3
"""build_ledger.py — D10_FIELD_AVAILABILITY_LEDGER.

Field-level availability and cutoff-validity coverage across every candidate source, measured
against the frozen possession row universe (``team_possession_universe/1``: 2,982 team-game rows
over 1,491 game clusters) and broken out BY SEASON and BY FOLD.

READ-ONLY. Nothing outside
``experiments/player_program/data_lane/D10_FIELD_AVAILABILITY_LEDGER/`` is written. Nothing is
fitted, predicted or scored. No comparative historical performance of any challenger is read.

THREE DISTINCTIONS THIS FILE REFUSES TO COLLAPSE
------------------------------------------------
  availability   the field exists and resolves for some fraction of the row universe.
  eligibility    the field is cutoff-valid — its value was provably observable at the declared
                 pregame cutoff for that row.
  admission      neither of the above. Nothing here admits anything into any model.

THE DECLARED PREGAME CUTOFF IS NOT INVENTED HERE
------------------------------------------------
It is read per game from ``experiments/prediction_contract_v4/game.parquet``
(``forecast_cutoff``), which the repository already fixes as either
``exact_tip_T-90m`` (tip minus 90 minutes, only where a tip observation qualified) or
``date_only_prior_day_cutoff`` (18:00 UTC on the day BEFORE the game). All 1,491 universe games
join to a cutoff.

VERDICT VOCABULARY
------------------
  CUTOFF_VALID      a per-row source observation timestamp exists AND is <= the row's own
                    forecast_cutoff, measured, for the rows counted as covered.
  CUTOFF_UNPROVEN   no per-row source observation timestamp, OR the only timestamp available is
                    later than the cutoff (a retrospective scrape). NEVER assumed valid.
  CUTOFF_INVALID    the value is a realised property of the target game itself. Using it pregame
                    would be leakage.
  ABSENT            no source for this field exists anywhere that was searched.

A CUTOFF_UNPROVEN field carries a ``structural_class`` so the reader can tell a static geographic
constant apart from a postgame box score. The class is an explanation of WHY the proof is missing.
It is not a downgrade of the verdict and it never substitutes for a timestamp.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from datetime import timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PROGRAM = HERE.parents[1]                      # experiments/player_program
ROOT = PROGRAM.parents[1]                      # repo worktree root
sys.path.insert(0, str(PROGRAM))

import possession_features as pf               # noqa: E402

DATA = ROOT / "data"
CONTRACT_V4_GAME = ROOT / "experiments" / "prediction_contract_v4" / "game.parquet"

MASTER_TEAM = DATA / "masters" / "master_team.parquet"
MASTER_PLAYER = DATA / "masters" / "master_player.parquet"
TEAM_CITIES = DATA / "reference" / "team_cities.csv"
TIP_TIMES = DATA / "reference" / "tip_times.csv"
INJURY_LOG = DATA / "injury_capture" / "injury_log.csv"
INJURY_HISTORY = DATA / "injury_history" / "injury_history.csv"
NEWS_ITEMS = DATA / "news_capture" / "news_items.csv"
REF_ASSIGNMENTS = DATA / "ref_assignments" / "assignments_log.csv"
ROSTER_ASOF = DATA / "w1_truth" / "roster_asof.csv"

#: injury_history / injury_capture use franchise labels that predate two relocations-in-name.
#: team_cities carries BOTH sides of each rename, so the alias map only has to reach a row that
#: exists there.
ABBR_ALIAS = {"POR": "PDX", "PHO": "PHO", "PHX": "PHX"}
FULLNAME_TO_ABBR = {
    "Atlanta Dream": "ATL", "Chicago Sky": "CHI", "Connecticut Sun": "CON",
    "Dallas Wings": "DAL", "Golden State Valkyries": "GSV", "Indiana Fever": "IND",
    "Las Vegas Aces": "LVA", "Los Angeles Sparks": "LAS", "Minnesota Lynx": "MIN",
    "New York Liberty": "NYL", "Phoenix Mercury": "PHX", "Portland Fire": "PDX",
    "Seattle Storm": "SEA", "Toronto Tempo": "TOR", "Washington Mystics": "WAS",
}


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def src(p: Path) -> dict:
    if not p.exists():
        return {"path": str(p.relative_to(ROOT)).replace("\\", "/"), "present": False}
    return {"path": str(p.relative_to(ROOT)).replace("\\", "/"), "present": True,
            "bytes": p.stat().st_size, "sha256": sha256(p)}


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0088
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp = p2 - p1
    dl = np.radians(lon2 - lon1)
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


# --------------------------------------------------------------------------- #
# universe + cutoffs + folds
# --------------------------------------------------------------------------- #

def build_spine():
    u = pf.load_universe()
    f = u.frame.copy()
    f["game_id"] = f["game_id"].astype(str)
    f["game_date"] = pd.to_datetime(f["game_date"])

    g = pd.read_parquet(CONTRACT_V4_GAME)
    g["game_id"] = g["game_id"].astype(str)
    f = f.merge(g[["game_id", "forecast_cutoff", "cutoff_policy", "exact_cutoff_ok",
                   "scheduled_tip_time", "tip_time_observed_at", "tip_time_quality"]],
                on="game_id", how="left")
    f.index = pd.Index([f"{a}:{b}" for a, b in zip(f.game_id, f.team_id)], name="team_game_uid")

    folds = pf.chronological_folds(u)
    fold_masks = {}
    for fo in folds:
        fold_masks[fo.fold_id] = {
            "cutoff_date": str(fo.cutoff_date),
            "test_season": int(fo.season),
            "train_uids": set(u.frame.loc[fo.train_index].pipe(
                lambda d: [f"{a}:{b}" for a, b in zip(d.game_id.astype(str), d.team_id)])),
            "test_uids": set(u.frame.loc[fo.test_index].pipe(
                lambda d: [f"{a}:{b}" for a, b in zip(d.game_id.astype(str), d.team_id)])),
        }
    return u, f, fold_masks


# --------------------------------------------------------------------------- #
# coverage accounting
# --------------------------------------------------------------------------- #

def coverage_block(spine: pd.DataFrame, fold_masks: dict, covered: pd.Series,
                   valid: pd.Series | None = None) -> dict:
    """Coverage of ``covered`` (bool per team-game row), by season and by fold.

    ``valid`` is the strictly narrower mask: covered AND provably observed at or before the row's
    own forecast_cutoff. It is reported separately at every level, never folded into coverage.
    """
    covered = covered.reindex(spine.index).fillna(False).astype(bool)
    if valid is None:
        valid = pd.Series(False, index=spine.index)
    valid = valid.reindex(spine.index).fillna(False).astype(bool) & covered

    def cell(mask):
        n = int(mask.sum())
        if n == 0:
            return {"rows": 0, "covered": 0, "coverage": None,
                    "cutoff_valid": 0, "cutoff_valid_rate": None}
        c = int((covered & mask).sum())
        v = int((valid & mask).sum())
        return {"rows": n, "covered": c, "coverage": round(c / n, 6),
                "cutoff_valid": v, "cutoff_valid_rate": round(v / n, 6)}

    all_mask = pd.Series(True, index=spine.index)
    out = {"overall": cell(all_mask), "by_season": {}, "by_season_type": {}, "by_fold": {}}
    for s, grp in spine.groupby("season"):
        out["by_season"][str(int(s))] = cell(spine.index.isin(grp.index))
    for st, grp in spine.groupby("season_type"):
        out["by_season_type"][str(st)] = cell(spine.index.isin(grp.index))
    for fid, fm in fold_masks.items():
        out["by_fold"][fid] = {
            "test_season": fm["test_season"], "cutoff_date": fm["cutoff_date"],
            "train": cell(pd.Series(spine.index.isin(list(fm["train_uids"])), index=spine.index)),
            "test": cell(pd.Series(spine.index.isin(list(fm["test_uids"])), index=spine.index)),
        }
    # game-cluster counts, so nobody reads a team-game number as a game number
    gid = spine["game_id"]
    out["overall"]["game_clusters"] = int(gid.nunique())
    out["overall"]["game_clusters_covered"] = int(gid[covered].nunique())
    return out


FIELDS: list[dict] = []


def field(family, name, **kw):
    rec = {"family": family, "field": name}
    rec.update(kw)
    FIELDS.append(rec)
    return rec


# --------------------------------------------------------------------------- #
def main() -> int:
    u, spine, fold_masks = build_spine()
    n = len(spine)
    idx = spine.index
    FALSE = pd.Series(False, index=idx)
    TRUE = pd.Series(True, index=idx)
    cutoff = spine["forecast_cutoff"]

    sources = {
        "possession_universe": {"artifact": "team_possession_universe/1",
                                "row_universe_digest": u.row_universe_digest,
                                "team_game_rows": n, "game_clusters": int(spine.game_id.nunique())},
        "contract_v4_game": src(CONTRACT_V4_GAME),
        "master_team": src(MASTER_TEAM),
        "master_player": src(MASTER_PLAYER),
        "team_cities": src(TEAM_CITIES),
        "tip_times": src(TIP_TIMES),
        "injury_log_captured": src(INJURY_LOG),
        "injury_history_wire": src(INJURY_HISTORY),
        "news_items": src(NEWS_ITEMS),
        "ref_assignments": src(REF_ASSIGNMENTS),
        "roster_asof": src(ROSTER_ASOF),
    }

    # ------------------------------------------------------------------ #
    # master_team — the schedule spine, and its single retrospective observation time
    # ------------------------------------------------------------------ #
    mt = pd.read_parquet(MASTER_TEAM)
    mt["game_id"] = mt["game_id"].astype(str)
    mt["game_date"] = pd.to_datetime(mt["game_date"])
    mt.index = pd.Index([f"{a}:{b}" for a, b in zip(mt.game_id, mt.team_id)])
    mt_obs = pd.to_datetime(mt["observed_time"], utc=True, format="mixed")
    mt_obs_u = mt_obs.reindex(idx)
    mt_u = mt.reindex(idx)
    mt_only = mt.index.difference(idx)
    mt_only_detail = (mt.loc[mt_only, ["game_id", "team_id", "game_date", "season",
                                       "season_type"]]
                      .assign(game_date=lambda d: d.game_date.dt.strftime("%Y-%m-%d"))
                      .to_dict("records"))
    master_team_obs_distinct = sorted(mt_obs.dropna().astype(str).unique().tolist())
    master_team_obs_after_cutoff = int((mt_obs_u > cutoff).sum())
    master_team_obs_after_game = int((mt_obs_u > (spine.game_date.dt.tz_localize("UTC")
                                                  + timedelta(days=1))).sum())

    def mt_present(col):
        return mt_u[col].notna() if col in mt_u else FALSE

    for col, label in [("game_id", "sched.game_id"), ("game_date", "sched.game_date"),
                       ("season", "sched.season"), ("season_type", "sched.season_type"),
                       ("is_home", "sched.is_home"), ("opp_team_id", "sched.opp_team_id"),
                       ("team_abbreviation", "sched.team_abbreviation")]:
        field("schedules", label, verdict="CUTOFF_UNPROVEN",
              structural_class="schedule_fact_attested_only_by_a_postgame_artifact",
              source="master_team", source_timestamp_column="observed_time",
              source_timestamp_granularity="artifact_batch (10 distinct values for 2,990 rows)",
              evidence=("the value is a scheduling fact and was in principle knowable pregame, but "
                        "the ONLY artifact in the repository that carries it is a completed-game "
                        "team box score whose observed_time is a retrospective bulk scrape. "
                        f"{master_team_obs_after_cutoff} of {n} universe rows carry an "
                        "observed_time strictly AFTER their own forecast_cutoff; "
                        f"{master_team_obs_after_game} carry one after the game itself. No "
                        "pre-cutoff observation of the schedule exists anywhere that was searched."),
              coverage=coverage_block(spine, fold_masks, mt_present(col), valid=FALSE))

    field("schedules", "sched.neutral_site_flag", verdict="ABSENT",
          structural_class="no_source",
          source=None, source_timestamp_column=None,
          evidence=("grep -rn -i 'neutral' over the worktree returns only PBP "
                    "NEUTRALDESCRIPTION text and unrelated 'neutralized' feature language. No "
                    "column, file or code anywhere marks a game as played at a neutral site. "
                    "Every venue attribute below therefore INHERITS the unverified assumption "
                    "that the venue is the home team's own arena."),
          coverage=coverage_block(spine, fold_masks, FALSE))

    # ------------------------------------------------------------------ #
    # rest — derived from the schedule spine, therefore inherits its provenance
    # ------------------------------------------------------------------ #
    sch = spine[["game_id", "team_id", "game_date", "season"]].copy()
    sch = sch.sort_values(["team_id", "game_date"])
    prev_date = sch.groupby(["team_id", "season"])["game_date"].shift(1)
    days_rest = (sch["game_date"] - prev_date).dt.days.reindex(idx)
    prev_date = prev_date.reindex(idx)

    g7 = []
    for (tid, ssn), grp in spine.groupby(["team_id", "season"]):
        d = grp["game_date"].sort_values()
        for uid, dt in d.items():
            g7.append((uid, int(((d < dt) & (d >= dt - timedelta(days=7))).sum())))
    games_prev7 = pd.Series(dict(g7)).reindex(idx)

    rest_note = ("derived by this node from the schedule spine only (team_id, season, game_date "
                 "of games strictly earlier than the row's own). It carries master_team's "
                 "provenance and cannot be better than it: the derivation adds no observation.")
    field("rest", "rest.days_since_prev_game", verdict="CUTOFF_UNPROVEN",
          structural_class="derived_from_schedule_fact",
          source="derived from master_team", source_timestamp_column=None,
          evidence=rest_note + " Undefined at each team's first game of a season by construction "
                   f"({int(days_rest.isna().sum())} of {n} rows), which is censoring, not "
                   "missingness.",
          coverage=coverage_block(spine, fold_masks, days_rest.notna(), valid=FALSE))
    field("rest", "rest.is_back_to_back", verdict="CUTOFF_UNPROVEN",
          structural_class="derived_from_schedule_fact",
          source="derived from master_team", source_timestamp_column=None,
          evidence=rest_note + f" Resolves to True on {int((days_rest == 1).sum())} rows.",
          coverage=coverage_block(spine, fold_masks, days_rest.notna(), valid=FALSE))
    field("rest", "rest.games_in_prev_7_days", verdict="CUTOFF_UNPROVEN",
          structural_class="derived_from_schedule_fact",
          source="derived from master_team", source_timestamp_column=None,
          evidence=rest_note + " Defined on every row (0 at a season opener is a real count, "
                   "not a null).",
          coverage=coverage_block(spine, fold_masks, games_prev7.notna(), valid=FALSE))
    field("rest", "rest.is_season_opener", verdict="CUTOFF_UNPROVEN",
          structural_class="derived_from_schedule_fact",
          source="derived from master_team", source_timestamp_column=None,
          evidence=rest_note + f" True on {int(days_rest.isna().sum())} rows.",
          coverage=coverage_block(spine, fold_masks, TRUE, valid=FALSE))

    # ------------------------------------------------------------------ #
    # venues / travel / elevation / time zones — team_cities.csv, one static table
    # ------------------------------------------------------------------ #
    tc = pd.read_csv(TEAM_CITIES)
    tc["first_season"] = tc["first_season"].astype(float)
    tc["last_season"] = tc["last_season"].astype(float)

    _city_memo: dict = {}

    def city_row(team_id, season):
        """The team_cities row EFFECTIVE for this team in this season.

        team_cities carries both sides of the two franchise renames (PHO/PHX, POR/PDX) as separate
        rows with first_season/last_season windows, so a season-aware lookup is required; taking
        the first matching team_id would silently attach the wrong abbreviation.
        """
        if team_id is None or pd.isna(team_id):
            return None
        key = (int(team_id), int(season))
        if key in _city_memo:
            return _city_memo[key]
        c = tc[tc.team_id == key[0]]
        if c.empty:
            _city_memo[key] = None
            return None
        eff = c[(c.first_season <= key[1])
                & (c.last_season.isna() | (c.last_season >= key[1]))]
        _city_memo[key] = (eff.iloc[0] if len(eff) else c.iloc[0])
        return _city_memo[key]

    home_team = mt_u["team_id"].where(mt_u["is_home"] == 1)
    game_home = (mt[mt.is_home == 1].drop_duplicates("game_id")
                 .set_index("game_id")["team_id"])
    venue_team = spine["game_id"].map(game_home)

    def venue_attr(team_series, col):
        vals = []
        for t, s in zip(team_series, spine["season"]):
            r = city_row(t, s)
            vals.append(None if r is None else r[col])
        return pd.Series(vals, index=idx)

    venue_cols = {c: venue_attr(venue_team, c)
                  for c in ("city", "arena", "lat", "lon", "elevation_ft", "timezone")}

    tc_note = ("data/reference/team_cities.csv is a 16-row hand-assembled static reference with "
               "NO capture timestamp of any kind — no column, no sidecar manifest, no fetch "
               "record. collect_bios.py states in a comment that lat/lon are city-level and "
               "elevation_ft approximate. The values are time-invariant in substance, but "
               "time-invariance is an argument, not a timestamp, and this ledger does not accept "
               "arguments in place of evidence. Venue attribution additionally assumes the venue "
               "is the home team's arena; see sched.neutral_site_flag, which is ABSENT.")

    field("venues", "venue.venue_team_id", verdict="CUTOFF_UNPROVEN",
          structural_class="derived_from_schedule_fact",
          source="master_team (is_home)", source_timestamp_column="observed_time",
          evidence="the home team of each game, taken from master_team.is_home. Inherits "
                   "master_team's retrospective observation time.",
          coverage=coverage_block(spine, fold_masks, venue_team.notna(), valid=FALSE))
    for c, label in [("arena", "venue.arena_name"), ("city", "venue.city")]:
        field("venues", label, verdict="CUTOFF_UNPROVEN",
              structural_class="static_reference_without_capture_timestamp",
              source="team_cities", source_timestamp_column=None, evidence=tc_note,
              coverage=coverage_block(spine, fold_masks, venue_cols[c].notna(), valid=FALSE))
    for c, label in [("lat", "travel.venue_lat"), ("lon", "travel.venue_lon")]:
        field("travel", label, verdict="CUTOFF_UNPROVEN",
              structural_class="static_reference_without_capture_timestamp",
              source="team_cities", source_timestamp_column=None, evidence=tc_note,
              coverage=coverage_block(spine, fold_masks, venue_cols[c].notna(), valid=FALSE))
    field("elevation", "elevation.venue_elevation_ft", verdict="CUTOFF_UNPROVEN",
          structural_class="static_reference_without_capture_timestamp",
          source="team_cities", source_timestamp_column=None, evidence=tc_note,
          coverage=coverage_block(spine, fold_masks, venue_cols["elevation_ft"].notna(),
                                  valid=FALSE))
    field("time_zones", "timezone.venue_iana_timezone", verdict="CUTOFF_UNPROVEN",
          structural_class="static_reference_without_capture_timestamp",
          source="team_cities", source_timestamp_column=None, evidence=tc_note,
          coverage=coverage_block(spine, fold_masks, venue_cols["timezone"].notna(), valid=FALSE))

    # previous-venue derived quantities: travel distance, elevation delta, tz shift
    ordered = spine.sort_values(["team_id", "game_date"])
    prev_venue = pd.Series(index=idx, dtype=object)
    for (tid, ssn), grp in spine.groupby(["team_id", "season"]):
        gg = grp.sort_values("game_date")
        pv = pd.Series(venue_team.reindex(gg.index)).shift(1)
        prev_venue.loc[gg.index] = pv.values

    prev_lat = venue_attr(prev_venue, "lat")
    prev_lon = venue_attr(prev_venue, "lon")
    prev_elev = venue_attr(prev_venue, "elevation_ft")
    prev_tz = venue_attr(prev_venue, "timezone")

    trav = pd.Series(haversine_km(venue_cols["lat"].astype(float), venue_cols["lon"].astype(float),
                                  prev_lat.astype(float), prev_lon.astype(float)), index=idx)
    field("travel", "travel.km_from_prev_venue", verdict="CUTOFF_UNPROVEN",
          structural_class="derived_from_static_reference_and_schedule",
          source="derived: team_cities lat/lon + master_team schedule",
          source_timestamp_column=None,
          evidence=("haversine great-circle km between this row's venue and the same team's "
                    "previous in-season venue, computed by this node (WGS84 mean radius "
                    "6371.0088 km). It is city-level precision by construction, and it is a "
                    "SCHEDULE-ORDER surrogate for travel, not an itinerary: no flight, "
                    "departure, arrival or lodging record exists anywhere in the repository. "
                    f"Median non-null {float(np.nanmedian(trav.astype(float))):.1f} km, max "
                    f"{float(np.nanmax(trav.astype(float))):.1f} km. " + tc_note),
          coverage=coverage_block(spine, fold_masks, trav.notna(), valid=FALSE))

    elev_delta = venue_cols["elevation_ft"].astype(float) - prev_elev.astype(float)
    field("elevation", "elevation.delta_from_prev_venue_ft", verdict="CUTOFF_UNPROVEN",
          structural_class="derived_from_static_reference_and_schedule",
          source="derived: team_cities elevation_ft + master_team schedule",
          source_timestamp_column=None,
          evidence=("this row's venue elevation minus the same team's previous in-season venue "
                    "elevation. The only WNBA venues above 1,000 ft in team_cities are LVA "
                    "(2,030), PHO/PHX (1,090) and ATL (1,010); the elevation axis is a "
                    "three-arena contrast, not a continuum. " + tc_note),
          coverage=coverage_block(spine, fold_masks, elev_delta.notna(), valid=FALSE))

    def utc_offset(tzname, when):
        if tzname is None or (isinstance(tzname, float) and math.isnan(tzname)) or pd.isna(when):
            return np.nan
        return ZoneInfo(str(tzname)).utcoffset(when.to_pydatetime()).total_seconds() / 3600.0

    tz_off = pd.Series([utc_offset(t, d) for t, d in zip(venue_cols["timezone"],
                                                          spine["game_date"])], index=idx)
    prev_tz_off = pd.Series([utc_offset(t, d) for t, d in zip(prev_tz, spine["game_date"])],
                            index=idx)
    tz_shift = tz_off - prev_tz_off
    field("time_zones", "timezone.venue_utc_offset_hours", verdict="CUTOFF_UNPROVEN",
          structural_class="derived_from_static_reference_and_schedule",
          source="derived: team_cities IANA zone resolved on the row's game_date",
          source_timestamp_column=None,
          evidence=("the IANA zone resolved to a real UTC offset on the row's own game_date via "
                    "zoneinfo, so DST is handled rather than assumed. NOTE the repository's own "
                    "features/common.py::TZ_OFFSET is a FIXED integer map that does not resolve "
                    "DST and does not distinguish America/Phoenix (no DST) from "
                    "America/Los_Angeles; that map is a different quantity from this column. "
                    + tc_note),
          coverage=coverage_block(spine, fold_masks, tz_off.notna(), valid=FALSE))
    field("time_zones", "timezone.shift_from_prev_venue_hours", verdict="CUTOFF_UNPROVEN",
          structural_class="derived_from_static_reference_and_schedule",
          source="derived: team_cities + master_team schedule", source_timestamp_column=None,
          evidence=("signed UTC-offset change from the team's previous in-season venue. Non-zero "
                    f"on {int((tz_shift.fillna(0) != 0).sum())} of {n} rows. " + tc_note),
          coverage=coverage_block(spine, fold_masks, tz_shift.notna(), valid=FALSE))

    # ------------------------------------------------------------------ #
    # tip times
    # ------------------------------------------------------------------ #
    tt = pd.read_csv(TIP_TIMES, dtype={"game_id": str})
    tt_map = tt.drop_duplicates("game_id").set_index("game_id")
    has_tt = spine["game_id"].isin(set(tt_map.index))
    tip_cols = {c: spine["game_id"].map(tt_map[c]) for c in
                ("tip_utc", "tip_hour_local", "tip_dow_local", "source_table",
                 "n_snapshots", "n_commence_variants")}

    tt_note = ("data/reference/tip_times.csv is built by collect_bios.py::phase_tips, which takes "
               "the LATEST odds snapshot per game ('the final scheduled tip that source saw') and "
               "DOES NOT retain odds_snapshot_timestamp in the output. The underlying odds tables "
               "carry a per-snapshot timestamp; this file discards it. A latest-snapshot value "
               "cannot be shown to predate the cutoff — the latest snapshot may postdate the tip "
               "itself. Every row is therefore CUTOFF_UNPROVEN as this file stands, and the "
               "unprovenness is a property of the DERIVATION, not of the underlying odds feed.")
    field("tip_times", "tip.tip_utc__tip_times_csv", verdict="CUTOFF_UNPROVEN",
          structural_class="pregame_observable_source_with_the_timestamp_dropped_in_derivation",
          source="tip_times", source_timestamp_column=None, evidence=tt_note,
          coverage=coverage_block(spine, fold_masks, tip_cols["tip_utc"].notna(), valid=FALSE))
    for c, label in [("tip_hour_local", "tip.tip_hour_local"),
                     ("tip_dow_local", "tip.tip_dow_local")]:
        field("tip_times", label, verdict="CUTOFF_UNPROVEN",
              structural_class="pregame_observable_source_with_the_timestamp_dropped_in_derivation",
              source="tip_times", source_timestamp_column=None,
              evidence=tt_note + " Localised through team_cities.timezone, so it also inherits "
                       "that table's absent capture timestamp.",
              coverage=coverage_block(spine, fold_masks, tip_cols[c].notna(), valid=FALSE))

    # the cutoff-screened tip, from the contract itself
    tip_obs = pd.to_datetime(spine["tip_time_observed_at"], utc=True)
    tip_sched = pd.to_datetime(spine["scheduled_tip_time"], utc=True)
    tip_valid = tip_sched.notna() & tip_obs.notna() & (tip_obs <= cutoff)
    field("tip_times", "tip.scheduled_tip_time__contract_v4_screened", verdict="CUTOFF_VALID",
          structural_class="per_row_observation_timestamp_screened_against_the_cutoff",
          source="contract_v4_game", source_timestamp_column="tip_time_observed_at",
          source_timestamp_granularity="per game",
          evidence=("prediction_contract_v2::resolve_tip_times admits an observation only when "
                    "observed_at < tip - 90 minutes, takes the LATEST qualifying observation, and "
                    "fails closed to a date-only policy otherwise. This node re-measured the "
                    "screen: of the rows carrying a scheduled_tip_time, "
                    f"{int(tip_valid.sum())} of {int(tip_sched.notna().sum())} have "
                    "tip_time_observed_at <= their own forecast_cutoff. This is the ONLY field "
                    "in this entire ledger that clears the cutoff test on historical rows, and "
                    f"it clears it on {int(tip_valid.sum())} of {n} team-game rows "
                    f"({tip_valid.mean():.1%})."),
          coverage=coverage_block(spine, fold_masks, tip_sched.notna(), valid=tip_valid))

    field("tip_times", "tip.tip_hour_et__pbp_wallclock", verdict="CUTOFF_INVALID",
          structural_class="derived_from_the_target_game_s_own_event_stream",
          source="data/playbyplay (WCTIMESTRING) / data/refresh_2026/pbp (period-start "
                 "description text)", source_timestamp_column=None,
          evidence=("features/common.py derives tip_hour_et from the play-by-play wall clock. "
                    "The play-by-play of a game is produced BY that game. A tip hour read off the "
                    "target game's own event stream is not a pregame observation of the schedule; "
                    "it is a postgame reconstruction of it. The legacy store carries WCTIMESTRING "
                    "directly; the modern CDN store carries no wall-clock column at all and would "
                    "need the '(7:03 PM EST)' substring parsed out of the period-start "
                    "description. Coverage is reported as 0 because this node did not derive it: "
                    "deriving a CUTOFF_INVALID surrogate to quantify it would be building the "
                    "thing the verdict rejects."),
          coverage=coverage_block(spine, fold_masks, FALSE))

    # ------------------------------------------------------------------ #
    # injuries
    # ------------------------------------------------------------------ #
    il = pd.read_csv(INJURY_LOG)
    il["capture_utc_ts"] = pd.to_datetime(il["capture_utc"], format="%Y%m%dT%H%M%SZ", utc=True)
    il["abbr"] = il["team"].map(FULLNAME_TO_ABBR)
    il["game_date_ts"] = pd.to_datetime(il["game_date"], errors="coerce")
    il_unmapped = int(il["abbr"].isna().sum())

    abbr_by_teamid = mt.drop_duplicates("team_id").set_index("team_id")["team_abbreviation"]
    spine_abbr = spine["team_id"].map(abbr_by_teamid)

    # a universe row is COVERED by the captured availability feed iff at least one captured row
    # names that team for that game date; CUTOFF_VALID iff at least one such row was captured at
    # or before the row's own forecast_cutoff.
    il_keyed = il.dropna(subset=["abbr", "game_date_ts"])
    il_cov, il_val = {}, {}
    grp = il_keyed.groupby(["abbr", "game_date_ts"])["capture_utc_ts"].min()
    for uid, (ab, gd, cut) in zip(idx, zip(spine_abbr, spine.game_date, cutoff)):
        k = (ab, gd)
        il_cov[uid] = k in grp.index
        il_val[uid] = bool(k in grp.index and pd.notna(cut) and grp.get(k) <= cut)
    il_cov = pd.Series(il_cov)
    il_val = pd.Series(il_val)

    il_note = ("data/injury_capture/injury_log.csv is the ONLY availability source in the "
               "repository with a genuine per-row observation timestamp (capture_utc, "
               f"{il.capture_utc_ts.min().isoformat()} to {il.capture_utc_ts.max().isoformat()}). "
               f"It holds {len(il)} rows over report dates "
               f"{il.report_date.min()}..{il.report_date.max()} and covers no game before "
               "2026-07-30. Revisions are preserved as separate timestamped rows rather than "
               "overwritten. Within its span it is genuinely point-in-time; outside its span it "
               "does not exist. NOTE the game_date column is null on "
               f"{int(il.game_date.isna().sum())} of {len(il)} rows (all source=espn), which are "
               "unattributable to a specific game and are excluded from the join.")
    for label, note in [("injury.status", "the Out/Questionable/Probable designation"),
                        ("injury.reason", "the free-text reason string"),
                        ("injury.report_date", "the report date the designation was issued for")]:
        field("injuries", label, verdict="CUTOFF_VALID",
              structural_class="per_row_capture_timestamp_within_span_only",
              source="injury_log_captured", source_timestamp_column="capture_utc",
              source_timestamp_granularity="per row",
              evidence=f"{note}. " + il_note + " Coverage below is measured at team-game level "
                       "against the possession universe and is zero for every season before 2026 "
                       "by construction, not by accident.",
              coverage=coverage_block(spine, fold_masks, il_cov, valid=il_val))

    ih = pd.read_csv(INJURY_HISTORY)
    ih["date_ts"] = pd.to_datetime(ih["date"], errors="coerce")
    ih["abbr"] = ih["team"].replace({"POR": "PDX"})
    ih_obs_note = ("data/injury_history/injury_history.csv is a Basketball-Reference scrape whose "
                   "per-row `date` is a real EFFECTIVE date, but whose observation time is a "
                   "SINGLE retrospective moment: ROSTER_SOURCE_AUDIT_RECEIPT.json records the CSV "
                   "as committed 2026-07-30 in 98271bb, so all "
                   f"{len(ih)} rows — including 2021 ones — were observed on one day, after every "
                   "cutoff in the universe except the last few days of 2026. The raw HTML that "
                   "might have carried a fetch timestamp is gitignored and absent. "
                   "Basketball-Reference edits transaction pages in place, so a re-scrape cannot "
                   "be diffed. There is no publication_time column and none is recoverable.")

    for cat, label in [("missed_game_injury", "injury.missed_game_injury_wire"),
                       ("missed_game_other", "injury.missed_game_other_wire")]:
        sub = ih[ih.category == cat]
        keys = set(zip(sub.abbr, sub.date_ts))
        cov = pd.Series([(a, d) in keys for a, d in zip(spine_abbr, spine.game_date)], index=idx)
        field("injuries", label, verdict="CUTOFF_UNPROVEN",
              structural_class="retrospective_archive_single_observation_time",
              source="injury_history_wire", source_timestamp_column="date (EFFECTIVE date only)",
              source_timestamp_granularity="per row effective date; observation time is one "
                                           "constant for all rows",
              evidence=(f"category={cat}, {len(sub)} rows. " + ih_obs_note + " A did-not-play row "
                        "dated the day of the game is also, by construction, knowable only once "
                        "the game has been played or the report published; the archive does not "
                        "distinguish the two."),
              coverage=coverage_block(spine, fold_masks, cov, valid=FALSE))

    # ------------------------------------------------------------------ #
    # transactions
    # ------------------------------------------------------------------ #
    ACQ = {"signing", "trade", "draft", "waiver_claim", "contract_conversion"}
    REL = {"waiver", "retirement", "contract_suspension"}
    for cats, label, human in [(ACQ, "transactions.acquisition_effective_date", "acquisitions"),
                               (REL, "transactions.release_effective_date", "releases")]:
        sub = ih[ih.category.isin(cats)].dropna(subset=["date_ts"])
        # A team-game is COVERED iff the team has >= 1 such record whose effective date falls
        # inside the SAME SEASON YEAR and strictly earlier than the row's own game_date.
        # "Any record ever, at any date" is the vacuous version of this question -- it resolves
        # True on essentially every row and measures nothing. The in-season restriction is what
        # makes the number informative, and it is the same restriction the roster rules use.
        by_team_year: dict = {}
        for (a, y), g in sub.groupby([sub.abbr, sub.date_ts.dt.year]):
            by_team_year[(a, int(y))] = np.sort(g.date_ts.values)
        cov, counts = {}, {}
        for uid, (ab, gd, ssn) in zip(idx, zip(spine_abbr, spine.game_date, spine.season)):
            arr = by_team_year.get((ab, int(ssn)))
            k = 0 if arr is None else int((arr < np.datetime64(gd)).sum())
            counts[uid] = k
            cov[uid] = k > 0
        counts = pd.Series(counts)
        field("transactions", label, verdict="CUTOFF_UNPROVEN",
              structural_class="retrospective_archive_single_observation_time",
              source="injury_history_wire", source_timestamp_column="date (EFFECTIVE date only)",
              source_timestamp_granularity="per row effective date; observation time is one "
                                           "constant for all rows",
              evidence=(f"{human}: categories {sorted(cats)}, {len(sub)} dated rows. Coverage "
                        "below is 'this team has at least one such record with an effective date "
                        "inside the same season year and strictly earlier than this row's "
                        "game_date' — the weakest condition under which the field could inform "
                        f"the row at all. Median prior in-season records per covered row: "
                        f"{float(counts[counts > 0].median()):.0f}; max {int(counts.max())}. "
                        + ih_obs_note + " The prior audit ROSTER_SOURCE_AUDIT_RECEIPT.json "
                        "already rules this source Regime B and Tier B, never Tier A; this ledger "
                        "measures it and does not reopen that ruling."),
              coverage=coverage_block(spine, fold_masks, pd.Series(cov), valid=FALSE))

    field("transactions", "transactions.observation_time", verdict="CUTOFF_UNPROVEN",
          structural_class="retrospective_archive_single_observation_time",
          source="injury_history_wire", source_timestamp_column="(none in the file)",
          source_timestamp_granularity="one constant for all rows, recovered from the commit that "
                                       "added the file, not from the file",
          evidence=("the observation time of the entire transaction archive is a single moment, "
                    "2026-07-30, and it is not IN the artifact — it is recoverable only from git "
                    "history (98271bb) as recorded by ROSTER_SOURCE_AUDIT_RECEIPT.json. A field "
                    "whose observation time lives outside the bytes it describes cannot be "
                    "checked by any producer or gate that reads only the bytes. Coverage is "
                    "reported as the share of universe rows whose own forecast_cutoff is EARLIER "
                    "than that single observation moment — i.e. the share for which the archive "
                    "is provably retrospective."),
          coverage=coverage_block(
              spine, fold_masks,
              pd.Series(cutoff < pd.Timestamp("2026-07-30", tz="UTC"), index=idx), valid=FALSE))

    field("transactions", "transactions.publication_time", verdict="ABSENT",
          structural_class="no_source",
          source="injury_history_wire", source_timestamp_column=None,
          evidence=("no column in any transaction artifact records when a move was PUBLISHED. "
                    "ROSTER_SOURCE_AUDIT_RECEIPT.json states publication_time is null and not "
                    "recoverable. Without it, no transaction record can be shown to have been "
                    "public before any historical cutoff, no matter how plausible same-day "
                    "reporting is."),
          coverage=coverage_block(spine, fold_masks, FALSE))
    field("transactions", "transactions.official_league_wire", verdict="ABSENT",
          structural_class="no_source",
          source=None, source_timestamp_column=None,
          evidence=("the official wnba.com transaction log is not captured anywhere in data/ and "
                    "nothing in the repository fetches it; prosportstransactions.com sits behind "
                    "a Cloudflare challenge and was not scraped. Both facts are recorded in "
                    "ROSTER_SOURCE_AUDIT_RECEIPT.json and re-confirmed by this node: no file "
                    "under data/ carries either source."),
          coverage=coverage_block(spine, fold_masks, FALSE))

    # ------------------------------------------------------------------ #
    # roster continuity
    # ------------------------------------------------------------------ #
    mp = pd.read_parquet(MASTER_PLAYER, columns=["game_id", "game_date", "season", "team_id",
                                                 "player_id", "starter_flag", "minutes",
                                                 "observed_time"])
    mp["game_date"] = pd.to_datetime(mp["game_date"])
    mp_obs = pd.to_datetime(mp["observed_time"], utc=True, format="mixed")

    prior_members, prior_n, cont = {}, {}, {}
    for (tid, ssn), grp in mp.groupby(["team_id", "season"]):
        by_date = {d: set(g.player_id) for d, g in grp.groupby("game_date")}
        dates = sorted(by_date)
        seen: set = set()
        prev: set = set()
        for d in dates:
            uids = spine.index[(spine.team_id == tid) & (spine.game_date == d)]
            for uid in uids:
                prior_members[uid] = len(seen)
                prior_n[uid] = len(prev)
                cont[uid] = (len(by_date[d] & prev) / len(prev)) if prev else np.nan
            prev = by_date[d]
            seen |= by_date[d]
    prior_members = pd.Series(prior_members).reindex(idx)
    cont = pd.Series(cont).reindex(idx)

    field("roster_continuity", "roster.prior_in_season_box_membership", verdict="CUTOFF_UNPROVEN",
          structural_class="prior_game_outcome_artifact_observed_retrospectively",
          source="master_player", source_timestamp_column="observed_time",
          source_timestamp_granularity="artifact_batch, all values 2026",
          evidence=("the v4/v5 contract's Tier-A candidacy rule S1: a player who appeared in a "
                    "STRICTLY EARLIER in-season box for this team. The rule's LOGIC is "
                    "cutoff-safe — a prior game's box exists before this game's cutoff. But the "
                    "only artifact carrying it, master_player, has observed_time values that are "
                    "all 2026 bulk scrapes, so the FILE cannot prove the box was observed before "
                    "the cutoff even though the underlying event was. This ledger records that "
                    "gap rather than accepting the logic in place of the timestamp. Coverage "
                    "below is 'at least one prior in-season appearance exists for this team', "
                    f"median prior distinct players {np.nanmedian(prior_members.astype(float)):.0f}."),
          coverage=coverage_block(spine, fold_masks, prior_members.fillna(0) > 0, valid=FALSE))
    field("roster_continuity", "roster.continuity_vs_prev_game", verdict="CUTOFF_UNPROVEN",
          structural_class="prior_game_outcome_artifact_observed_retrospectively",
          source="derived from master_player", source_timestamp_column="observed_time",
          evidence=("share of this game's dressed players who also appeared in the team's "
                    "immediately previous in-season game. Undefined at season openers "
                    f"({int(cont.isna().sum())} of {n} rows). NOTE this quantity uses THIS game's "
                    "own box to determine who dressed, so as written it is a POSTGAME "
                    "description of continuity, not a pregame feature. It is listed here because "
                    "the acceptance criteria name roster continuity as a field; a pregame version "
                    "would have to be built from a projected rotation, which exists "
                    "(projected_player_possessions/1) and is a different artifact."),
          coverage=coverage_block(spine, fold_masks, cont.notna(), valid=FALSE))
    field("roster_continuity", "roster.starter_flag", verdict="CUTOFF_INVALID",
          structural_class="realised_property_of_the_target_game",
          source="master_player", source_timestamp_column="observed_time",
          evidence=("who actually started the game being predicted. This is a realised outcome of "
                    "the target game. It is listed so that it is on the record as rejected, not "
                    "merely unmentioned. No projected-starters artifact with a pregame timestamp "
                    "exists."),
          coverage=coverage_block(spine, fold_masks, TRUE, valid=FALSE))

    ra = pd.read_csv(ROSTER_ASOF)
    field("roster_continuity", "roster.roster_asof_tenure", verdict="CUTOFF_INVALID",
          structural_class="derived_from_box_scores_first_appearance",
          source="roster_asof", source_timestamp_column=None,
          evidence=(f"data/w1_truth/roster_asof.csv, {len(ra)} rows. Its name invites the "
                    "opposite conclusion, which is why it is stated here: first_game_date is the "
                    "date a player FIRST APPEARED, which is exactly the information that arrives "
                    "too late to establish affiliation before that game. It carries no per-row "
                    "timestamp — only one artifact-level fit_through_date. "
                    "ROSTER_SOURCE_AUDIT_RECEIPT.json rules it UNUSABLE for candidacy and this "
                    "node concurs."),
          coverage=coverage_block(spine, fold_masks, FALSE))

    il_team_cov = pd.Series([bool(a in set(il.abbr.dropna())) and gd >= pd.Timestamp("2026-07-30")
                             for a, gd in zip(spine_abbr, spine.game_date)], index=idx)
    field("roster_continuity", "roster.captured_availability_affiliation", verdict="CUTOFF_VALID",
          structural_class="per_row_capture_timestamp_within_span_only",
          source="injury_log_captured", source_timestamp_column="capture_utc",
          source_timestamp_granularity="per row",
          evidence=("the captured pregame availability report names a team for every listed "
                    "player, so within its span it can affiliate a player with no prior box row — "
                    "the only source in the repository that can. Its span begins 2026-07-30, "
                    f"which is {int(il_team_cov.sum())} of {n} universe team-game rows."),
          coverage=coverage_block(spine, fold_masks, il_cov, valid=il_val))

    # ------------------------------------------------------------------ #
    # coaching
    # ------------------------------------------------------------------ #
    coach_ev = ("exhaustive search of the worktree for a coaching source found NOTHING. "
                "`grep -rn -i coach` over features/, data/ and experiments/player_program/ "
                "returns only (a) free-text \"Coach's Decision\" reason strings inside "
                "injury_log.csv, which name no coach, and (b) two orchestration prompt filenames. "
                "`find . -iname '*coach*'` returns two markdown files and no data file. There is "
                "no head-coach column, no coach identity table, no tenure record and no "
                "coaching-change log anywhere. PLAYER_MODEL_CAPABILITY_MATRIX.md independently "
                "records this track as `not started` with 'No code, artifact or registration'.")
    for label in ("coaching.head_coach_identity", "coaching.coach_tenure_games",
                  "coaching.coach_change_flag", "coaching.rotation_policy"):
        field("coaching", label, verdict="ABSENT", structural_class="no_source",
              source=None, source_timestamp_column=None, evidence=coach_ev,
              coverage=coverage_block(spine, fold_masks, FALSE))

    # ------------------------------------------------------------------ #
    # opponent history
    # ------------------------------------------------------------------ #
    meets, days_since = {}, {}
    for (a, b), grp in spine.groupby(["team_id", "opp_team_id"]):
        gg = grp.sort_values("game_date")
        dates = list(gg["game_date"])
        for i, uid in enumerate(gg.index):
            same_season = [d for j, d in enumerate(dates)
                           if j < i and gg["season"].iloc[j] == gg["season"].iloc[i]]
            meets[uid] = len(same_season)
            days_since[uid] = ((dates[i] - same_season[-1]).days if same_season else np.nan)
    meets = pd.Series(meets).reindex(idx)
    days_since = pd.Series(days_since).reindex(idx)

    field("opponent_history", "opponent.n_prior_meetings_this_season",
          verdict="CUTOFF_UNPROVEN", structural_class="derived_from_schedule_fact",
          source="derived from master_team", source_timestamp_column="observed_time",
          evidence=("count of strictly earlier same-season games between the same ordered pair. "
                    f"Zero on {int((meets == 0).sum())} of {n} rows (first meeting of the "
                    "season). Inherits master_team's retrospective observation time."),
          coverage=coverage_block(spine, fold_masks, meets.notna(), valid=FALSE))
    field("opponent_history", "opponent.days_since_last_meeting",
          verdict="CUTOFF_UNPROVEN", structural_class="derived_from_schedule_fact",
          source="derived from master_team", source_timestamp_column="observed_time",
          evidence=f"undefined on the {int(days_since.isna().sum())} rows that are a first "
                   "same-season meeting; that is censoring, not missingness.",
          coverage=coverage_block(spine, fold_masks, days_since.notna(), valid=FALSE))
    field("opponent_history", "opponent.prior_game_evidence_depth",
          verdict="CUTOFF_UNPROVEN", structural_class="frozen_producer_prior_games_only",
          source="projected_exposure_v1/team_possession_prior_v1.parquet "
                 "(carried in the possession universe as opp_n_history_games / "
                 "opp_pace_evidence_depth)",
          source_timestamp_column=None,
          evidence=("the frozen pace producer's count of the opponent's prior games backing its "
                    "pace estimate, capped at the declared window of 10. Its CONSTRUCTION is "
                    "prior-games-only and attested by PROJECTED_EXPOSURE_RECEIPT.json / "
                    "PROJECTED_EXPOSURE_VALIDATION.json (35/35). But those receipts attest "
                    "construction order, not observation time: the artifact carries no capture "
                    "timestamp per row, so it is UNPROVEN under this ledger's rule even though "
                    "its construction is validated. This is the sharpest case in the ledger of "
                    "the difference between 'validated' and 'timestamped'."),
          coverage=coverage_block(spine, fold_masks, spine["opp_n_history_games"].notna(),
                                  valid=FALSE))
    field("opponent_history", "opponent.opp_pace_estimate",
          verdict="CUTOFF_UNPROVEN", structural_class="frozen_producer_prior_games_only",
          source="projected_exposure_v1/team_possession_prior_v1.parquet",
          source_timestamp_column=None,
          evidence=("same artifact and same reasoning as opponent.prior_game_evidence_depth. "
                    "Note the possession feature contract deliberately admits only the CONTRAST "
                    "(pace_gap), because team and opponent pace estimates together span the "
                    "exposure offset. Availability of the level is not eligibility of the level."),
          coverage=coverage_block(spine, fold_masks, spine["opp_pace_estimate"].notna(),
                                  valid=FALSE))
    field("opponent_history", "opponent.prior_box_aggregates",
          verdict="CUTOFF_UNPROVEN", structural_class="prior_game_outcome_artifact_observed_"
                                                      "retrospectively",
          source="master_team", source_timestamp_column="observed_time",
          evidence=("any trailing aggregate of the opponent's STRICTLY EARLIER box scores is "
                    "available for every row that has a prior same-season game. It is the same "
                    "artifact-timestamp gap as roster.prior_in_season_box_membership: the events "
                    "precede the cutoff, the file's observation of them does not. NOTE separately "
                    "that master_team's TARGET-game columns are realised outcomes and "
                    "possession_features.py explicitly inspects and excludes the whole file for "
                    "that reason."),
          coverage=coverage_block(spine, fold_masks, meets.fillna(0) > 0, valid=FALSE))

    # ------------------------------------------------------------------ #
    # adjacent captured feeds, named so their absence from the field list is deliberate
    # ------------------------------------------------------------------ #
    nw = pd.read_csv(NEWS_ITEMS)
    rf = pd.read_csv(REF_ASSIGNMENTS)
    adjacent = {
        "news_capture": {
            "rows": int(len(nw)), "timestamp_columns": ["capture_utc", "published_utc"],
            "span": [str(nw.published_utc.min()), str(nw.published_utc.max())],
            "note": "genuinely point-in-time within its span, but the CONTENT is prose. It is not "
                    "a field source without a registered extraction layer.",
        },
        "ref_assignments": {
            "rows": int(len(rf)), "timestamp_columns": ["capture_utc"],
            "span": [str(rf.capture_utc.min()), str(rf.capture_utc.max())],
            "note": "officiating crew per game with a per-row capture_utc. Not one of the twelve "
                    "field families this node was asked for; recorded here so its existence is "
                    "not lost.",
        },
    }

    # ------------------------------------------------------------------ #
    out = {
        "schema": "field_availability_ledger/1",
        "node_id": "D10_FIELD_AVAILABILITY_LEDGER",
        "epistemic_status": ("VERIFIED_READ_ONLY_DERIVATION. An availability ledger. Availability "
                             "is not eligibility and eligibility is not admission."),
        "generated_utc": pd.Timestamp.utcnow().isoformat(),
        "row_universe": {
            "contract": "team_possession_universe/1",
            "row_universe_digest": u.row_universe_digest,
            "team_game_rows": n,
            "game_clusters": int(spine.game_id.nunique()),
            "note": ("2,982 team-game rows over 1,491 game clusters. The event/contract universe "
                     "is WIDER: prediction_contract_v4/game.parquet and "
                     "EVENT_SOURCE_INVENTORY.json both carry 1,495 games and master_team carries "
                     "2,990 team-game rows. The 4-game / 8-row difference is the possession "
                     "producer's own exclusion and is reported, not reconciled here."),
        },
        "cutoff_definition": {
            "source": "experiments/prediction_contract_v4/game.parquet::forecast_cutoff",
            "policies": {
                "exact_tip_T-90m": "scheduled tip minus 90 minutes, admitted only where an "
                                   "observation satisfied observed_at < tip - 90 min",
                "date_only_prior_day_cutoff": "18:00 UTC on the day BEFORE the game",
            },
            "universe_games_joined_to_a_cutoff": int(spine.game_id.nunique()),
            "policy_counts_over_universe_team_games":
                spine["cutoff_policy"].value_counts().to_dict(),
            "rule": ("a field is CUTOFF_VALID for a row only if a per-row source observation "
                     "timestamp exists and is <= that row's forecast_cutoff. No timestamp means "
                     "CUTOFF_UNPROVEN. Structural plausibility is never a substitute."),
        },
        "fold_structure": {
            "source": "possession_features.chronological_folds()",
            "kind": "expanding-window chronological, one fold per season with at least one "
                    "strictly earlier season; games never split across folds",
            "folds": {fid: {"test_season": fm["test_season"], "cutoff_date": fm["cutoff_date"],
                            "train_rows": len(fm["train_uids"]), "test_rows": len(fm["test_uids"])}
                      for fid, fm in fold_masks.items()},
            "note": ("prediction_contract_v5/player_game_enriched.parquet carries a different and "
                     "degenerate fold_id of the form 'season:YYYY' (six values, no train/test "
                     "split). The two are not the same object and this ledger uses the "
                     "chronological folds because the possession target is what the program is "
                     "selecting on."),
        },
        "sources": sources,
        "cross_artifact_row_reconciliation": {
            "master_team_rows": int(len(mt)),
            "possession_universe_rows": n,
            "rows_in_master_team_not_in_universe": int(len(mt_only)),
            "excluded_rows": mt_only_detail,
            "finding": ("the 8-row difference between master_team (2,990) and the possession "
                        "universe (2,982) is not scattered: it is EXACTLY the four games of "
                        "2021-05-14, the opening day of the 2021 season, all eight team-games. "
                        "The pace producer has no prior-games evidence at all on opening day of "
                        "the first season in the archive, so those rows carry no projected "
                        "exposure and fall out of the universe. Every coverage figure in this "
                        "ledger is therefore computed on a universe that already excludes the "
                        "single hardest cold-start day in the data, which flatters any "
                        "prior-games-only field by construction."),
            "consequence_measured": ("roster.prior_in_season_box_membership is covered on 2,914 "
                                     "rows while rest.days_since_prev_game is covered on 2,906. "
                                     "The 8-row gap is the same 8 rows: master_player knows of a "
                                     "prior 2021-05-14 game that the possession universe does not "
                                     "contain, so 8 of the universe's season openers look like "
                                     "non-openers to a master_player-based derivation and like "
                                     "openers to a universe-based one."),
        },
        "captured_feed_vs_cutoff_policy": {
            "question": "can the one genuinely point-in-time availability feed be consumed under "
                        "the repository's own declared cutoff policy?",
            "universe_rows_overlapping_the_feed_span": int(il_cov.sum()),
            "of_those_cutoff_valid": int(il_val.sum()),
            "feed_span": [str(il.capture_utc_ts.min()), str(il.capture_utc_ts.max())],
            "universe_last_game_date": str(spine.game_date.max().date()),
            "finding": ("the feed and the cutoff policy are structurally mismatched. Official "
                        "pregame availability reports are published ON game day. The "
                        "date_only_prior_day_cutoff policy sits at 18:00 UTC the day BEFORE. So "
                        "on any game that did not earn an exact_tip_T-90m cutoff, the report "
                        "does not yet exist at the cutoff and the feed is unusable no matter how "
                        "well captured it is. Of the 12 universe team-game rows the feed overlaps "
                        "at all, 2 clear their own cutoff — and those 2 are the single game that "
                        "carries an exact tip cutoff. This is a POLICY interaction, not a capture "
                        "failure, and it will persist for every future game that lacks a "
                        "qualifying tip observation."),
        },
        "master_team_observation_time": {
            "distinct_values": master_team_obs_distinct,
            "n_distinct": len(master_team_obs_distinct),
            "universe_rows_observed_after_own_cutoff": master_team_obs_after_cutoff,
            "universe_rows_observed_after_own_game": master_team_obs_after_game,
        },
        "injury_log_team_labels_unmapped": il_unmapped,
        "adjacent_captured_feeds_not_in_the_field_list": adjacent,
        "fields": FIELDS,
        "verdict_counts": {},
    }
    vc: dict = {}
    for f_ in FIELDS:
        vc[f_["verdict"]] = vc.get(f_["verdict"], 0) + 1
    out["verdict_counts"] = vc

    (HERE / "FINDINGS.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    print(f"fields: {len(FIELDS)}  verdicts: {vc}")
    print(f"universe {n} team-games / {spine.game_id.nunique()} clusters")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
