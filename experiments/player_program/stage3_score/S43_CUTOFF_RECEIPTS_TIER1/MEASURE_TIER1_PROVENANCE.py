r"""S43 / D065 tier-1 cutoff-validity PROVENANCE RECEIPTS for ten schedule-fixed fields.

Discharges part of S37 finding A9 (Severity A) under user decision D065, option (a) with
proportional rigour.

WHAT THIS IS.  A provenance demonstration, NOT a per-observation timestamp audit.  The tier-1
discriminator the user set is: *is the VALUE fixed by the schedule before tipoff, or is it
COMPUTED FROM OBSERVATIONS?*  Tier 1 is the former.  Per the coordinator addition to D065, a
tier-1 receipt must additionally name (1) the PRODUCING JOB that materialises the column, (2)
that job's AS-OF BOUND, (3) the provenance chain from schedule source to consumed column, and
(4) sha256 of every file read as evidence.

ROOT (stated explicitly; the main working tree's data has drifted because live captures
continue there):
  C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program
This tree's data/masters/master_team.parquet must hash to the S33/S36 pin
ad79ce5c...8528.  The drifted copy (e8e35b53...) is refused BY NAME, as runner/universe.py
does, not merely by pin failure.

PROHIBITIONS OBSERVED.  No fitting.  No performance number of any kind -- no MAE, Brier,
accuracy, log-loss, delta, or arm-vs-null comparison.  Counts, censuses, hashes and provenance
only.  master_team.parquet's `observed_time` column is a LOCAL FILE MTIME IN MID-2026, not an
as-of bound; it is DROPPED immediately after read and no frame is ever written to disk.  No git
command is run.  Nothing outside this directory is written.

Produces RECEIPTS.json.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

WORKTREE = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
HERE = os.path.dirname(os.path.abspath(__file__))

MASTER_TEAM_PIN = "ad79ce5cdda7e058ba24be45243037252e3795a3e9f0c18cc41b3f12f3c38528"
KNOWN_DRIFTED = "e8e35b539df2d13f2325e207b9fb2ba8b2e96da476eaa0ec877fcf5588a71c19"
D010_EXCLUDED_DATE = "2021-05-14"
UNIVERSE_CLUSTERS, UNIVERSE_ROWS = 1491, 2982

# build_masters.py:80-81 -- the season-type digit map, copied here to TEST the column, never to
# rebuild it.  If the copy and the artifact disagree the test fails loudly.
SEASON_TYPE_BY_DIGIT = {"1": "Preseason", "2": "Regular Season",
                        "3": "All-Star", "4": "Playoffs"}
# sc06_sched_fatigue_diff.py:68-70 -- the arm's pinned standard-offset map.
STANDARD_OFFSETS = {"America/New_York": -5, "America/Toronto": -5,
                    "America/Indiana/Indianapolis": -5, "America/Chicago": -6,
                    "America/Denver": -7, "America/Phoenix": -7, "America/Los_Angeles": -8}
TZ_CAP = 3

READS: dict[str, str] = {}


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def ev(rel: str) -> str:
    """Hash a repo-relative evidence file and record it under its repo-relative name."""
    p = os.path.join(WORKTREE, rel.replace("/", os.sep))
    if not os.path.exists(p):
        raise SystemExit(f"evidence file missing from the PROGRAM WORKTREE: {rel}")
    d = sha256(p)
    READS[rel] = d
    return d


# ------------------------------------------------------------------ evidence set
EVIDENCE = [
    "data/masters/master_team.parquet",
    "data/reference/team_cities.csv",
    "data/reference/collect_bios.py",
    "build_masters.py",
    "experiments/player_program/stage3_score/S36_IMPLEMENT_ARMS/arms/sc06_sched_fatigue_diff.py",
    "experiments/player_program/stage3_score/S36_IMPLEMENT_ARMS/runner/universe.py",
    "experiments/player_program/stage3_score/S36_IMPLEMENT_ARMS/runner/runner_constants.py",
    "experiments/player_program/stage3_score/S36_IMPLEMENT_ARMS/PREBUILD_GAME_ID_DIGEST.json",
    "experiments/player_program/data_lane/D10_FIELD_AVAILABILITY_LEDGER/build_ledger.py",
    "experiments/player_program/data_lane/D10_FIELD_AVAILABILITY_LEDGER/FINDINGS.json",
    "experiments/player_program/data_lane/D10_FIELD_AVAILABILITY_LEDGER/REPORT.md",
    "experiments/player_program/stage3_score/S37_IMPLEMENTATION_AUDIT/S37_REPORT_BODY.md",
    "experiments/player_program/stage3_score/S37_IMPLEMENTATION_AUDIT/SPEC.json",
    "experiments/player_program/stage3_score/S33R_PREREGISTRATION_REPAIR/"
    "MEASURE_A1_DATE_WITNESS.py",
]
for rel in EVIDENCE:
    ev(rel)

MT_PATH = os.path.join(WORKTREE, "data", "masters", "master_team.parquet")
mt_sha = READS["data/masters/master_team.parquet"]
if mt_sha == KNOWN_DRIFTED:
    raise SystemExit("ROOT_PATH_RULE: this is the KNOWN DRIFTED master_team copy. HALT.")
if mt_sha != MASTER_TEAM_PIN:
    raise SystemExit(f"byte pin failed for master_team.parquet: {mt_sha} != {MASTER_TEAM_PIN}")

# ------------------------------------------------------------------ universe
# Rebuilt exactly as runner/universe.py::build_universe lines 127-143.
mt = pd.read_parquet(MT_PATH)
OBSERVED_TIME_DROPPED = "observed_time" in mt.columns
mt = mt.drop(columns=[c for c in ("observed_time",) if c in mt.columns])  # PROHIBITION: 2026 mtime
mt["game_id"] = mt["game_id"].astype(str)
mt["game_date"] = mt["game_date"].astype(str)

keep = mt[(mt["is_home"] == 1) & (mt["game_date"] != D010_EXCLUDED_DATE)]["game_id"]
uni_ids = set(keep.astype(str))
tr = mt[mt["game_id"].isin(uni_ids)].copy()
tr = tr.sort_values(["game_date", "game_id", "team_id"], kind="mergesort").reset_index(drop=True)
tr["team_id"] = tr["team_id"].astype("int64")
tr["opp_team_id"] = tr["opp_team_id"].astype("int64")
tr["is_home"] = tr["is_home"].astype("int64")

if len(uni_ids) != UNIVERSE_CLUSTERS or len(tr) != UNIVERSE_ROWS:
    raise SystemExit(f"universe is {len(uni_ids)}/{len(tr)}, pinned "
                     f"{UNIVERSE_CLUSTERS}/{UNIVERSE_ROWS}. HALT.")

# re-derive the O2 pre-build game_id digest with the program's own canonicalisation
sys.path.insert(0, os.path.join(WORKTREE, "experiments", "player_program", "stage3_score",
                                "S36_IMPLEMENT_ARMS", "runner"))
import canon  # noqa: E402

game_ids = sorted(uni_ids)
built_digest = canon.column_digest(game_ids)
prebuild = json.loads(open(os.path.join(
    WORKTREE, "experiments", "player_program", "stage3_score", "S36_IMPLEMENT_ARMS",
    "PREBUILD_GAME_ID_DIGEST.json"), encoding="utf-8").read())
pinned_digest = prebuild.get("GAME_ID_SET_SHA256")

season_of_row = tr["season"].astype("int64")
stype_of_row = tr["season_type"].astype(str)
playoff_rows = int((stype_of_row == "Playoffs").sum())
playoff_clusters = int(tr.loc[stype_of_row == "Playoffs", "game_id"].nunique())

universe = {
    "root": WORKTREE,
    "master_team_sha256": mt_sha,
    "master_team_pin_matched": True,
    "known_drifted_copy_refused_by_name": KNOWN_DRIFTED,
    "observed_time_column_present_and_dropped_before_any_write": OBSERVED_TIME_DROPPED,
    "d010_excluded_date": D010_EXCLUDED_DATE,
    "clusters": len(uni_ids),
    "team_game_rows": int(len(tr)),
    "per_season_clusters": {str(k): int(v) for k, v in
                            tr.groupby("season")["game_id"].nunique().items()},
    "per_season_type_clusters": {str(k): int(v) for k, v in
                                 tr.groupby("season_type")["game_id"].nunique().items()},
    "per_season_type_rows": {str(k): int(v) for k, v in stype_of_row.value_counts().items()},
    "playoff_rows": playoff_rows,
    "playoff_clusters": playoff_clusters,
    "o2_prebuild_digest_pinned": pinned_digest,
    "o2_prebuild_digest_rederived_here": built_digest,
    "o2_prebuild_digest_match": bool(pinned_digest == built_digest),
}

# =========================================================================================
# PROVENANCE TESTS.  Each is a census over the universe.  A test that returns 0 violations
# demonstrates that the column IS the schedule-fixed quantity it is claimed to be -- it does
# not, and cannot, demonstrate anything about WHEN the bytes were captured.
# =========================================================================================
M: dict[str, dict] = {}

# --- game_id (ledger #0) ------------------------------------------------------------------
gid = tr["game_id"]
rows_per_cluster = tr.groupby("game_id").size()
M["sched.game_id"] = {
    "distinct_game_ids": int(gid.nunique()),
    "all_length_10": bool((gid.str.len() == 10).all()),
    "all_digits": bool(gid.str.isdigit().all()),
    "clusters_with_exactly_2_team_rows": int((rows_per_cluster == 2).sum()),
    "clusters_with_other_than_2_team_rows": int((rows_per_cluster != 2).sum()),
    "duplicate_game_id_team_id_pairs": int(tr.duplicated(["game_id", "team_id"]).sum()),
    "leading_prefix_distribution": {str(k): int(v) for k, v in
                                    gid.str.slice(0, 5).value_counts().items()},
    "o2_digest_rederives_to_the_prebuild_pin": bool(pinned_digest == built_digest),
}

# --- season (ledger #2) -- season == int("20" + game_id[3:5])  (build_masters.py:110-111) --
season_from_gid = ("20" + gid.str[3:5]).astype("int64")
M["sched.season"] = {
    "rule_under_test": 'season == int("20" + game_id[3:5])  [build_masters.py:110-111, applied :572]',
    "rows_tested": int(len(tr)),
    "rows_where_column_disagrees_with_the_game_id_substring": int(
        (season_from_gid != season_of_row).sum()),
    "distinct_seasons": sorted(int(s) for s in season_of_row.unique()),
    "rows_per_season": {str(k): int(v) for k, v in season_of_row.value_counts().items()},
}

# --- season_type (ledger #3) -- season_type == map[game_id[2]]  (build_masters.py:114-115) --
stype_from_gid = gid.str[2].map(SEASON_TYPE_BY_DIGIT).fillna("Unknown")
M["sched.season_type"] = {
    "rule_under_test": "season_type == SEASON_TYPE_BY_DIGIT[game_id[2]]  "
                       "[build_masters.py:80-81 + :114-115, applied :573]",
    "rows_tested": int(len(tr)),
    "rows_where_column_disagrees_with_the_game_id_digit": int(
        (stype_from_gid != stype_of_row).sum()),
    "digit_to_value_observed": {str(k): sorted(set(stype_of_row[gid.str[2] == k]))
                               for k in sorted(set(gid.str[2]))},
    "rows_per_season_type": {str(k): int(v) for k, v in stype_of_row.value_counts().items()},
    "unknown_rows": int((stype_from_gid == "Unknown").sum()),
}

# --- is_home (ledger #4) ------------------------------------------------------------------
home_per_cluster = tr.groupby("game_id")["is_home"].sum()
M["sched.is_home"] = {
    "domain": sorted(int(v) for v in tr["is_home"].unique()),
    "null_rows": int(tr["is_home"].isna().sum()),
    "clusters_with_exactly_one_home_row": int((home_per_cluster == 1).sum()),
    "clusters_violating_exactly_one_home": int((home_per_cluster != 1).sum()),
    "home_rows": int((tr["is_home"] == 1).sum()),
    "away_rows": int((tr["is_home"] == 0).sum()),
}

# --- opp_team_id (ledger #5) -- the pairing complement (build_masters.py:386-391) ----------
pair = tr[["game_id", "team_id"]].merge(tr[["game_id", "team_id"]], on="game_id")
pair = pair[pair["team_id_x"] != pair["team_id_y"]]
expect = pair.set_index(["game_id", "team_id_x"])["team_id_y"]
got = tr.set_index(["game_id", "team_id"])["opp_team_id"]
aligned = expect.reindex(got.index)
M["sched.opp_team_id"] = {
    "rule_under_test": "opp_team_id is the OTHER team_id in the same game_id cluster "
                       "[build_masters.py:386-391, merged :568-570]",
    "rows_tested": int(len(got)),
    "rows_where_opp_team_id_is_not_the_cluster_partner": int((aligned != got).sum()),
    "rows_where_opp_team_id_equals_own_team_id": int((tr["opp_team_id"] == tr["team_id"]).sum()),
    "null_rows": int(tr["opp_team_id"].isna().sum()),
    "distinct_team_ids": int(tr["team_id"].nunique()),
}

# --- rest / venue / timezone: re-derive SC06's own index (sc06:84-114), counts only -------
tc_path = os.path.join(WORKTREE, "data", "reference", "team_cities.csv")
tc = pd.read_csv(tc_path)
tz_by_team: dict[int, str] = {}
for _, r in tc.iterrows():
    tz_by_team[int(r["team_id"])] = str(r["timezone"])
unmapped_zones = sorted({z for z in tz_by_team.values() if z not in STANDARD_OFFSETS})
uni_teams = sorted(int(t) for t in set(tr["team_id"]) | set(tr["opp_team_id"]))
teams_missing_from_team_cities = [t for t in uni_teams if t not in tz_by_team]

s = tr.sort_values(["team_id", "game_date", "game_id"], kind="mergesort").copy()
d = pd.to_datetime(s["game_date"])
s["_d"] = d
prev1_career = s.groupby("team_id", sort=False)["_d"].shift(1)
prev2_career = s.groupby("team_id", sort=False)["_d"].shift(2)
gap1 = (s["_d"] - prev1_career).dt.days
gap2 = (s["_d"] - prev2_career).dt.days
b2b = (gap1 == 1)
third_in_4 = (gap2 <= 3)

# the same-season reading (D10 ledger's definition, and S37 finding B1's card reading)
prev1_season = s.groupby(["team_id", "season"], sort=False)["_d"].shift(1)
gap1_season = (s["_d"] - prev1_season).dt.days
b2b_season = (gap1_season == 1)
games_prev7 = []
for (_tid, _ssn), grp in s.groupby(["team_id", "season"]):
    dd = grp["_d"].sort_values()
    for uid, dt in dd.items():
        games_prev7.append((uid, int(((dd < dt) & (dd >= dt - pd.Timedelta(days=7))).sum())))
g7 = pd.Series(dict(games_prev7)).reindex(s.index)

M["rest.is_back_to_back"] = {
    "consumed_form": "sc06_sched_fatigue_diff.py:91-96  b2b = (game_date - prev game_date == 1 day), "
                     "CAREER clock (groupby team_id alone)",
    "ledger_form": "build_ledger.py:277-278, :298-302  days_since_prev_game == 1, SAME-SEASON clock",
    "rows_tested": int(len(s)),
    "true_rows_career_clock_as_consumed": int(b2b.sum()),
    "true_rows_same_season_clock_as_carded": int(b2b_season.sum()),
    "rows_where_the_two_clocks_disagree": int((b2b.fillna(False) != b2b_season.fillna(False)).sum()),
    "rows_with_no_previous_game_career_clock": int(prev1_career.isna().sum()),
    "rows_with_no_previous_game_same_season_clock": int(prev1_season.isna().sum()),
}
M["rest.games_in_prev_7_days"] = {
    "consumed_form": "sc06_sched_fatigue_diff.py:92-97  third_in_4 = (game_date - 2nd-prior "
                     "game_date <= 3 days) -- the 3-in-4 class named in the S37 A9 table, NOT a "
                     "7-day count",
    "ledger_form": "build_ledger.py:281-286, :303-308  count of same-season games in the prior 7 days",
    "rows_tested": int(len(s)),
    "third_in_four_true_rows_as_consumed": int(third_in_4.sum()),
    "rows_with_fewer_than_two_previous_games": int(prev2_career.isna().sum()),
    "games_in_prev_7_days_value_counts_ledger_form": {
        str(int(k)): int(v) for k, v in g7.value_counts().sort_index().items()},
    "note": "the two are DIFFERENT quantities; the S37 A9 table names ledger #10 'the 3-in-4 class' "
            "and SC06 consumes the 3-in-4 indicator. Both are counted here so neither is implied.",
}

# --- venue_team_id (ledger #12) -- sc06:100-101 -------------------------------------------
venue_team = np.where(s["is_home"].to_numpy() == 1, s["team_id"].to_numpy(),
                      s["opp_team_id"].to_numpy())
s["_venue_team"] = venue_team
home_of_cluster = tr[tr["is_home"] == 1].set_index("game_id")["team_id"]
venue_matches_home = (s["_venue_team"].to_numpy()
                      == home_of_cluster.reindex(s["game_id"]).to_numpy())
M["venue.venue_team_id"] = {
    "rule_under_test": "venue_team_id = is_home ? team_id : opp_team_id "
                       "[sc06_sched_fatigue_diff.py:100-101; ledger build_ledger.py:368-373]",
    "rows_tested": int(len(s)),
    "rows_where_venue_team_id_is_not_the_cluster_home_team": int((~venue_matches_home).sum()),
    "distinct_venue_teams": int(pd.Series(venue_team).nunique()),
    "neutral_site_flag_status_in_the_ledger": "ABSENT (D10 build_ledger.py:262-270)",
}

# --- venue_iana_timezone (ledger #18) -----------------------------------------------------
s["_venue_tz_name"] = [tz_by_team[int(v)] for v in venue_team]
s["_venue_tz_off"] = [STANDARD_OFFSETS[z] for z in s["_venue_tz_name"]]
M["timezone.venue_iana_timezone"] = {
    "rows_tested": int(len(s)),
    "rows_with_a_resolved_iana_zone": int(s["_venue_tz_name"].notna().sum()),
    "rows_unresolved": int(s["_venue_tz_name"].isna().sum()),
    "distinct_zones_on_the_universe": sorted(set(s["_venue_tz_name"])),
    "team_cities_rows": int(len(tc)),
    "team_cities_distinct_team_ids": int(tc["team_id"].nunique()),
    "universe_team_ids_missing_from_team_cities": teams_missing_from_team_cities,
    "zones_in_team_cities_absent_from_the_arm_standard_offset_map": unmapped_zones,
    "arm_fails_closed_on_an_unmapped_zone": "sc06_sched_fatigue_diff.py:78-79 raises ValueError",
}

# --- shift_from_prev_venue_hours (ledger #22) ---------------------------------------------
prev_tz_career = s.groupby("team_id", sort=False)["_venue_tz_off"].shift(1)
tz_shift_career = (s["_venue_tz_off"] - prev_tz_career)
tz_crossed = np.minimum(tz_shift_career.abs().fillna(0.0).to_numpy(dtype=float), TZ_CAP)
prev_tz_season = s.groupby(["team_id", "season"], sort=False)["_venue_tz_off"].shift(1)
tz_shift_season = (s["_venue_tz_off"] - prev_tz_season)
M["timezone.shift_from_prev_venue_hours"] = {
    "consumed_form": "sc06_sched_fatigue_diff.py:99-105  tz_crossed = min(|off(venue) - "
                     "off(prev-game venue)|, 3), CAREER clock, STANDARD offsets (DST not applied)",
    "ledger_form": "build_ledger.py:394-459  signed UTC-offset change from the team's previous "
                   "IN-SEASON venue, DST resolved through zoneinfo on the row's own game_date",
    "rows_tested": int(len(s)),
    "rows_with_no_previous_game_career_clock": int(prev_tz_career.isna().sum()),
    "rows_with_no_previous_game_same_season_clock": int(prev_tz_season.isna().sum()),
    "nonzero_tz_crossed_rows_as_consumed": int((tz_crossed != 0).sum()),
    "tz_crossed_value_counts_as_consumed": {
        str(k): int(v) for k, v in pd.Series(tz_crossed).value_counts().sort_index().items()},
    "rows_where_career_and_same_season_clocks_disagree": int(
        (tz_shift_career.fillna(0) != tz_shift_season.fillna(0)).sum()),
    "dependency_on_a_PLAYED_previous_game": True,
}

# Reconciliation of the consumed quantity against the D10 ledger's published 1,103 non-zero rows.
# The two readings differ on TWO axes -- clock (career vs same-season) and DST (standard offsets vs
# zoneinfo) -- and a reader seeing 1,310 vs 1,103 must be able to see why. Counts only.
from zoneinfo import ZoneInfo  # noqa: E402

_dst_off = []
for z, dt in zip(s["_venue_tz_name"], s["_d"]):
    _dst_off.append(pd.Timestamp(dt).tz_localize(ZoneInfo(z)).utcoffset().total_seconds() / 3600.0)
s["_venue_tz_off_dst"] = _dst_off
prev_dst_season = s.groupby(["team_id", "season"], sort=False)["_venue_tz_off_dst"].shift(1)
tz_shift_dst_season = (s["_venue_tz_off_dst"] - prev_dst_season)
prev_dst_career = s.groupby("team_id", sort=False)["_venue_tz_off_dst"].shift(1)
tz_shift_dst_career = (s["_venue_tz_off_dst"] - prev_dst_career)
_phx = s["_venue_tz_name"] == "America/Phoenix"
_prev_zone = s.groupby("team_id", sort=False)["_venue_tz_name"].shift(1)
_pacific_phx_pair = ((_phx & (_prev_zone == "America/Los_Angeles"))
                     | ((s["_venue_tz_name"] == "America/Los_Angeles")
                        & (_prev_zone == "America/Phoenix")))
M["timezone.shift_from_prev_venue_hours"]["reconciliation_to_the_D10_ledger_number"] = {
    "ledger_published_nonzero_rows": 1103,
    "ledger_reading": "same-season clock, signed, DST resolved via zoneinfo on the row's own "
                      "game_date (build_ledger.py:394-459 and REPORT.md section 4.3)",
    "rederived_here_same_season_dst_resolved_nonzero_rows": int(
        (tz_shift_dst_season.fillna(0) != 0).sum()),
    "rederived_here_career_dst_resolved_nonzero_rows": int(
        (tz_shift_dst_career.fillna(0) != 0).sum()),
    "consumed_reading_career_standard_offsets_nonzero_rows": int((tz_crossed != 0).sum()),
    "rows_whose_venue_and_previous_venue_are_the_America_Phoenix_America_Los_Angeles_pair": int(
        _pacific_phx_pair.sum()),
    "why_they_differ": "America/Phoenix does not observe DST, so under zoneinfo it coincides with "
                       "America/Los_Angeles at -7 throughout the WNBA season and the shift reads "
                       "ZERO; under the arm's pinned STANDARD-offset map the two differ by one "
                       "hour and the shift reads ONE. This is a definitional divergence between "
                       "two readings of ledger #22, not a cutoff-validity question, and it is "
                       "recorded rather than reconciled.",
}

# --- the raise-do-not-assign census: playoff-row dependence on prior-game outcomes ---------
po = stype_of_row == "Playoffs"
M["_playoff_boundary_census"] = {
    "playoff_rows": playoff_rows,
    "playoff_clusters": playoff_clusters,
    "playoff_rows_share_of_universe_rows": round(playoff_rows / len(tr), 6),
    "playoff_clusters_by_season": {str(k): int(v) for k, v in
                                   tr[po.to_numpy()].groupby("season")["game_id"].nunique().items()},
    "regular_season_rows": int((stype_of_row == "Regular Season").sum()),
    "other_season_types": sorted(set(stype_of_row) - {"Playoffs", "Regular Season"}),
}

# =========================================================================================
# THE RECEIPTS
# =========================================================================================
BUILD_MASTERS_ASOF = (
    "NONE. build_masters.py takes no as-of argument, no cutoff, no date bound and no snapshot "
    "id. It globs whatever is present under data/refresh_2026/gamelog_*.parquet, "
    "data/wnba_gamelog_{2021..2024}.parquet, data/wnba_team_gamelog_2024.parquet, the per-game "
    "misc/advanced directories and data/shotcharts/shots_*.parquet, reads each in full, and "
    "records observed_time = max(local file mtime of the contributing files) (:118-120, :594-595). "
    "Every one of those artifacts is a COMPLETED-GAME record and every mtime is a 2026 bulk "
    "scrape. THE JOB HAS NO AS-OF BOUND AND THIS RECEIPT DOES NOT CLAIM ONE.")

BUILD_MASTERS_WHY_SAFE = (
    "What makes these columns tier-1 is not a bound on the job -- there is none -- but that the "
    "job derives them from GAME IDENTITY and never from any quantity produced by the play of the "
    "target game. season and season_type are pure functions of the game_id string; opp_team_id is "
    "the cluster's other team_id; is_home is the MATCHUP orientation token / shotchart HTM-VTM "
    "role. No box-score statistic, score, minute, or outcome enters any of them. A later re-scrape "
    "could only change these values by changing the league's own identity record of the fixture.")

UNIVERSE_ASOF = (
    "runner/universe.py::build_universe (:121-143) is byte-bounded rather than time-bounded: it "
    "refuses to build unless data/masters/master_team.parquet hashes to the pin "
    "ad79ce5c...8528 (:64-77), refuses the known-drifted live copy BY NAME (:71-73), and refuses "
    "to return a frame unless the game_id set re-derives to PREBUILD_GAME_ID_DIGEST.json (:80-90, "
    ":136-140). That is a reproducibility bound, not an as-of bound, and it is reported as such.")

COLLECT_BIOS_ASOF = (
    "OFFLINE AND UNBOUNDED-BY-CONSTRUCTION. data/reference/collect_bios.py::phase_cities "
    "(:201-224) performs NO network read and NO data read that can supply a value: it materialises "
    "team_cities.csv from the CITY_ROWS literal in its own source (:180-198), hand-entered "
    "2026-07-31 at city-level precision (:172-179). Its only read of repository data is "
    "master_team.parquet for join VERIFICATION (:210-218), which can fail the build closed but "
    "cannot inject a value. The D10 ledger's complaint that the file has 'no capture timestamp of "
    "any kind' is correct and, on this reading, expected: there is no capture. The value's "
    "provenance is the producing job's source code, which is a stronger bound than a capture "
    "timestamp would be, because it is fixed for every row of every season simultaneously.")

LEDGER_OBJECTION = (
    "The D10 ledger says, on the timezone table: 'The values are time-invariant in substance, but "
    "time-invariance is an argument, not a timestamp, and this ledger does not accept arguments in "
    "place of evidence.' (build_ledger.py:360-366). That objection is not withdrawn and is not "
    "refuted here. Under user decision D065 the standard of proof for THIS CLASS OF FIELD is "
    "changed: for tier-1 fields a provenance argument PLUS a named producing job with its as-of "
    "bound stated IS now sufficient. The ledger's CUTOFF_UNPROVEN verdicts stand as verdicts "
    "under the ledger's own rule; this receipt does not edit them and did not write to the ledger. "
    "What it records is that the program's standard of proof for these ten fields is now the one "
    "the user set, not the one the ledger applied.")


def receipt(field, ledger_no, tier_by, producing_job, asof, chain, evidence_keys,
            verdict, residual, notes=None):
    return {
        "field": field,
        "ledger_number": ledger_no,
        "tier": 1,
        "tier_assigned_by": tier_by,
        "producing_job": producing_job,
        "asof_bound": asof,
        "provenance_chain": chain,
        "evidence_sha256": {k: READS[k] for k in evidence_keys},
        "measurements": M.get(field, {}),
        "verdict": verdict,
        "residual_risk_not_closed_by_this_receipt": residual,
        **({"notes": notes} if notes else {}),
    }


MT_EV = ["data/masters/master_team.parquet", "build_masters.py",
         "experiments/player_program/stage3_score/S36_IMPLEMENT_ARMS/runner/universe.py",
         "experiments/player_program/stage3_score/S36_IMPLEMENT_ARMS/runner/runner_constants.py",
         "experiments/player_program/stage3_score/S36_IMPLEMENT_ARMS/PREBUILD_GAME_ID_DIGEST.json",
         "experiments/player_program/data_lane/D10_FIELD_AVAILABILITY_LEDGER/build_ledger.py"]
SC06_EV = MT_EV + [
    "experiments/player_program/stage3_score/S36_IMPLEMENT_ARMS/arms/sc06_sched_fatigue_diff.py"]
TC_EV = SC06_EV + ["data/reference/team_cities.csv", "data/reference/collect_bios.py"]

V_OK = "TIER1_RECEIPT_ISSUED"

fields = [
    receipt(
        "sched.game_id", 0, "coordinator",
        "build_masters.py -- the league game identifier is carried through from every source "
        "artifact unchanged; zero-padded to 10 characters at :355 and emitted in the master_team "
        "keep-list at :600-607. Downstream, the universe's game_id SET is fixed by "
        "runner/universe.py::build_universe :131-140 against PREBUILD_GAME_ID_DIGEST.json.",
        BUILD_MASTERS_ASOF + "  " + UNIVERSE_ASOF,
        ["WNBA/NBA-Stats league schedule release issues the 10-digit GAME_ID when the fixture is "
         "published",
         "the id appears verbatim as GAME_ID in every pulled artifact (gamelog_team_*, "
         "gamelog_player_*, misc, advanced, shots_*)",
         "build_masters.py:355 zfill(10) -> build_master_team :600-607 -> "
         "master_team.parquet::game_id",
         "runner/universe.py:127-140 -> the pinned 1,491-cluster game_id set -> every arm's join "
         "key and the (game_date, game_id) sequencing of every EWMA"],
        MT_EV, V_OK,
        "This receipt establishes that game_id is a schedule-issued identifier, not a computed "
        "quantity. It does NOT establish the CORRECTNESS of the (game_date, game_id) SEQUENCING "
        "that consumes it -- that rests on game_date, which is a separate field (ledger #1) with "
        "its own measurement, M_A1_GAME_DATE_CUTOFF_V2, carrying 16 enumerated exception clusters.",
        ["COORDINATOR-ASSIGNED TIER: the user's D065 tier-1 list named opponent, home/away, season "
         "type, rest/B2B/3-in-4 and venue/timezone. game_id was assigned to tier 1 by coordinator "
         "#04 on the ground that it is plainly schedule-fixed and not computed from observations. "
         "Overrulable."]),
    receipt(
        "sched.season", 2, "coordinator",
        "build_masters.py::season_of (:110-111), applied to master_team at :572. The column is "
        "literally int('20' + game_id[3:5]) -- a pure function of the game_id string.",
        BUILD_MASTERS_ASOF + "  Because season is a pure function of game_id, the absence of an "
        "as-of bound on the job cannot affect it: the job reads no source that could supply a "
        "different season for a given game_id.",
        ["schedule release fixes the game_id, whose digits [3:5] are the season year",
         "build_masters.py:110-111 season_of(game_id) -> :572 master_team.season",
         "runner/universe.py:156-161 carries season into the game-cluster frame; :177 derives "
         "era_2024",
         "consumed as: fold assignment on all 17 elements (runner_constants FOLDS), SC06 era, "
         "SC01 two-season window, SC02/SC03/SC10 season clocks"],
        MT_EV, V_OK,
        "Fold assignment is a design-time partition, not a per-row prediction input; this receipt "
        "does not address whether the fold structure itself is sound. It also does not address the "
        "season-year convention for any hypothetical cross-calendar-year fixture; none exists in "
        "this universe.",
        ["COORDINATOR-ASSIGNED TIER: not in the user's named tier-1 list. Assigned by coordinator "
         "#04. Overrulable."]),
    receipt(
        "sched.season_type", 3, "user",
        "build_masters.py::stype_of (:114-115) with SEASON_TYPE_BY_DIGIT (:80-81), applied to "
        "master_team at :573. The column is SEASON_TYPE_BY_DIGIT[game_id[2]] -- a pure function of "
        "the game_id string. Carried into the game frame by runner/universe.py::build_universe "
        ":156-161.",
        BUILD_MASTERS_ASOF + "  As with season, the column is a pure function of game_id, so the "
        "job's lack of an as-of bound cannot change its value.",
        ["schedule release fixes the game_id, whose digit [2] encodes the season type "
         "(1 Preseason, 2 Regular Season, 3 All-Star, 4 Playoffs)",
         "build_masters.py:80-81 + :114-115 stype_of(game_id) -> :573 master_team.season_type",
         "runner/universe.py:156-161 -> games.season_type -> carried into the game frame by "
         "build_universe"],
        MT_EV, V_OK,
        "A PLAYOFF game's existence, participants and seeding are determined by regular-season and "
        "prior-series OUTCOMES. The season_type VALUE for a given game_id is fixed before that "
        "game's own tipoff, so the tier-1 standard as the user stated it is met; but 'fixed by the "
        "schedule' and 'not computed from observations' come apart on playoff rows. See "
        "RAISE-DO-NOT-ASSIGN item 1. Census: "
        f"{playoff_rows} playoff team-game rows / {playoff_clusters} clusters."),
    receipt(
        "sched.is_home", 4, "user",
        "build_masters.py::build_game_index (:308-392). Two producers by declared precedence: "
        "(a) from_matchup (:319-325) reads the MATCHUP orientation token and sets "
        "is_home = not(' @ ' in matchup) at :322, from the team gamelog then the new-era player "
        "gamelog; (b) for 2021-2024, where old-era gamelogs carry no matchup at all, the shotchart "
        "HTM/VTM role columns matched against that game's own tricodes (:345-370). Disagreements "
        "between producers are COUNTED, never averaged (:374-378); precedence dedupe at :379; "
        "exactly-one-home audited per cluster at :382-385. Merged into master_team at :568-570.",
        BUILD_MASTERS_ASOF + "  " + BUILD_MASTERS_WHY_SAFE + "  For is_home specifically the "
        "as-of gap is at its widest: the orientation token is read off a COMPLETED-GAME box "
        "score / shot chart. This receipt asserts the CLASS (which team hosts is fixed at schedule "
        "release) and names the producing job; it does not and cannot assert that the bytes read "
        "were captured before tipoff.",
        ["schedule release fixes the host of every fixture",
         "the host appears as the MATCHUP orientation token ('LVA vs. NYL' / 'NYL @ LVA') in the "
         "team and player gamelogs, and as the HTM/VTM role in the shot charts",
         "build_masters.py:319-325 (' @ ' test at :322) and :345-370 -> build_game_index -> "
         ":568-570 master_team.is_home",
         "runner/universe.py:131 (is_home == 1 selects the cluster spine) and :156-160 (home/away "
         "team assignment)",
         "consumed as: the universe definition; SC01 eta; SC05 home/away split; SC06 venue "
         "attribution (sc06:100-101)"],
        MT_EV, V_OK,
        "Two residuals. (i) The producing artifacts are postgame; the receipt proves class, not "
        "capture time. (ii) sched.neutral_site_flag is ABSENT from the whole repository (D10 "
        "build_ledger.py:262-270), so is_home == 'the game was played in this team's own arena' is "
        "an untested assumption that four families inherit. That is an ACCURACY gap, not a "
        "cutoff-validity gap, and it is unaffected by this receipt."),
    receipt(
        "sched.opp_team_id", 5, "user",
        "build_masters.py::build_game_index (:386-391): a self-join of the (game_id, team_id) "
        "index against itself on game_id, keeping the rows where team_id_x != team_id_y. "
        "Merged into master_team at :568-570 and used again for the opponent box join at :576-581.",
        BUILD_MASTERS_ASOF + "  opp_team_id reads NO source at all beyond the cluster membership "
        "already established by build_game_index: it is the set complement of the row's own "
        "team_id within its game_id. No later source could change it without changing which two "
        "teams the fixture is between.",
        ["schedule release fixes the two teams of every fixture",
         "both teams appear under the same GAME_ID in every pulled artifact",
         "build_masters.py:386-391 self-join on game_id -> :568-570 master_team.opp_team_id",
         "runner/universe.py:151 cast to int64; :156-160 home/away team ids on the cluster frame",
         "consumed as: SC01 matchup ratings; SC10 orthogonalisation covariate; SC06 venue "
         "attribution (sc06:100-101)"],
        MT_EV, V_OK,
        "For PLAYOFF fixtures the opponent is determined by prior-game outcomes. It is still fixed "
        "before that game's own tipoff, so the tier-1 standard is met; but see RAISE-DO-NOT-ASSIGN "
        "item 1 for the ambiguity in the user's stated discriminator on those rows."),
    receipt(
        "rest.is_back_to_back", 9, "user",
        "AS CONSUMED: experiments/player_program/stage3_score/S36_IMPLEMENT_ARMS/arms/"
        "sc06_sched_fatigue_diff.py::fatigue_index (:84-114). b2b is derived IN-FRAME at :91-96 as "
        "(game_date - previous game_date == 1 day) over universe.team_rows. There is NO "
        "materialised is_back_to_back column anywhere in the repository. AS LEDGERED: "
        "D10 build_ledger.py:277-278 and :298-302 derive it independently, same-season.",
        "The producing job is the arm module itself and its ONLY inputs are universe.team_rows' "
        "team_id, game_date and game_id -- all schedule identity. " + UNIVERSE_ASOF + "  The "
        "underlying game_date is byte-pinned via master_team and separately receipted by "
        "S33R MEASURE_A1_DATE_WITNESS.py.",
        ["schedule release fixes each team's fixture dates",
         "master_team.game_date (ledger #1, receipted separately by M_A1)",
         "runner/universe.py:146-147 sequences team_rows by (game_date, game_id, team_id)",
         "sc06_sched_fatigue_diff.py:87-96 per-team shift(1) on game_date -> b2b indicator",
         "consumed as: SC06 fatigue index F, weight 1.0 (sc06:51, :109)"],
        SC06_EV, V_OK,
        "THE DERIVATION USES PLAYED-GAME DATES AS A SURROGATE FOR SCHEDULED DATES. The user's "
        "tier-1 phrase was 'scheduled rest/B2B/3-in-4'; the implementation reads the RESOLVED "
        "universe's game_date, so a postponed fixture contributes its played date, not its "
        "originally scheduled one. This field therefore inherits M_A1's enumerated exception set "
        "(10 release-order displaced clusters + 6 with no second-endpoint witness). SC06 already "
        "carries an A1-SENSITIVITY kill for exactly this dependency (sc06:178-180), which S37 "
        "finding B3 records as never actually wired. Separately, S37 finding B1: SC06 uses a "
        "CAREER previous-game clock where the card specifies a SAME-SEASON one; both counts are "
        "measured above so neither reading is implied."),
    receipt(
        "rest.games_in_prev_7_days", 10, "user",
        "AS CONSUMED (the 3-in-4 class): sc06_sched_fatigue_diff.py::fatigue_index :92-97 -- "
        "third_in_4 = (game_date - second-prior game_date <= 3 days), derived in-frame. AS "
        "LEDGERED (the 7-day count): D10 build_ledger.py:281-286 and :303-308. These are two "
        "different quantities; the S37 A9 table itself names ledger #10 as 'the 3-in-4 class'. "
        "Neither is a materialised column.",
        "Same as rest.is_back_to_back: the producing job is the arm module, its inputs are "
        "team_id, game_date and game_id from the byte-pinned universe. " + UNIVERSE_ASOF,
        ["schedule release fixes each team's fixture dates",
         "master_team.game_date (ledger #1, receipted separately by M_A1)",
         "runner/universe.py:146-147 sequencing",
         "sc06_sched_fatigue_diff.py:92-97 per-team shift(2) on game_date -> third_in_4 indicator",
         "consumed as: SC06 fatigue index F, weight 0.5 (sc06:51, :109)"],
        SC06_EV, V_OK,
        "Same played-date-as-surrogate residual as rest.is_back_to_back, same inheritance of M_A1's "
        "exception set, same S37 B1 career-vs-same-season clock ambiguity. Additionally: the "
        "consumed quantity is NOT the ledger's named quantity. If the program intends ledger #10 "
        "literally (games in the previous 7 days), that column is consumed by nothing in this "
        "slate; if it intends the 3-in-4 indicator, that is what SC06 consumes. Both are counted "
        "above so the receipt does not silently pick one."),
    receipt(
        "venue.venue_team_id", 12, "user",
        "AS CONSUMED: sc06_sched_fatigue_diff.py:100-101 -- "
        "venue = np.where(is_home == 1, team_id, opp_team_id), derived in-frame. AS LEDGERED: "
        "D10 build_ledger.py:368-373, 'the home team of each game, taken from master_team.is_home'. "
        "No materialised column exists.",
        "The field reads NOTHING beyond is_home and opp_team_id, both receipted above. It "
        "introduces no new source and therefore no new as-of exposure. " + UNIVERSE_ASOF,
        ["schedule release fixes the host of every fixture",
         "master_team.is_home + master_team.opp_team_id (ledger #4, #5, receipted above)",
         "sc06_sched_fatigue_diff.py:100-101 -> venue team id",
         "consumed as: SC06 venue attribution, feeding the tz component"],
        SC06_EV, V_OK,
        "Inherits is_home's neutral-site gap in full: with sched.neutral_site_flag ABSENT, "
        "venue_team_id is 'the home team', not 'the team whose arena was used'. The D10 report "
        "calls this assumption load-bearing for four families and nowhere tested. It is an "
        "accuracy gap, not a cutoff-validity gap; this receipt does not close it and does not "
        "claim to."),
    receipt(
        "timezone.venue_iana_timezone", 18, "user",
        "data/reference/collect_bios.py::phase_cities (:201-224), writing "
        "data/reference/team_cities.csv from the CITY_ROWS literal at :180-198. AS CONSUMED: "
        "sc06_sched_fatigue_diff.py::_team_timezone_offsets (:73-81) reads team_cities.csv "
        "directly and maps each IANA zone through the arm's pinned STANDARD_OFFSETS (:68-70), "
        "raising ValueError on any zone not in the map (:78-79).",
        COLLECT_BIOS_ASOF,
        ["a franchise's home arena and its IANA time zone are properties of the fixture location, "
         "fixed long before any tipoff",
         "collect_bios.py:180-198 CITY_ROWS literal (hand-entered 2026-07-31) -> :201-224 "
         "phase_cities -> data/reference/team_cities.csv (16 rows)",
         "sc06_sched_fatigue_diff.py:73-81 team_cities.csv -> {team_id: standard UTC offset}, "
         "fail-closed on an unmapped zone",
         "consumed as: SC06 tz component, weight 0.25 (sc06:51, :109)"],
        TC_EV, V_OK,
        "Three residuals, none of them about cutoff validity. (i) The arm deliberately does NOT "
        "apply DST (sc06:56-67, :136-138) while the D10 ledger's version resolves DST through "
        "zoneinfo (build_ledger.py:447-453) -- two different quantities under one ledger name. "
        "(ii) team_cities.csv is city-level, hand-entered, and the file itself records SEA 2021 "
        "splitting homes with Everett WA (collect_bios.py:177-179). (iii) The zone is the HOME "
        "team's zone, so the neutral-site gap propagates here too."),
    receipt(
        "timezone.shift_from_prev_venue_hours", 22, "user",
        "AS CONSUMED: sc06_sched_fatigue_diff.py:99-105 -- the team's own venue zone offset this "
        "game minus the same team's venue zone offset at its previous game, absolute value, capped "
        "at 3 (:105). SC06's `tz_crossed` IS this quantity. AS LEDGERED: D10 build_ledger.py:394-459, "
        "signed, same-season, DST-resolved.",
        "Inputs are venue_team_id (from is_home/opp_team_id) and team_cities.csv, both receipted "
        "above, plus the (game_date, game_id) sequencing of the byte-pinned universe. No new "
        "source. " + UNIVERSE_ASOF,
        ["schedule release fixes both this fixture's venue and the team's previous fixture's venue",
         "master_team.is_home / opp_team_id -> venue team (ledger #12)",
         "team_cities.csv -> venue IANA zone -> standard UTC offset (ledger #18)",
         "runner/universe.py:146-147 sequencing -> sc06:103 per-team shift(1) on the venue offset",
         "sc06:104-105 |difference|, capped at 3 -> the 0.25-weighted term of F"],
        TC_EV, V_OK,
        "THE KNOWN TENSION, RECORDED NOT PAPERED OVER: this field is schedule-derived and yet it "
        "DEPENDS ON THE PREVIOUS GAME HAVING BEEN PLAYED. Its value on row r is a function of the "
        "team's previous row in the resolved universe, which is only known to be that row once "
        "that game has been played and resolved into the universe. Under the schedule alone, the "
        "previous fixture -- and hence the shift -- is also determined; the two coincide except "
        "where a fixture was postponed or displaced. The user's D065 tier-1 list explicitly named "
        "'venue/timezone', which SETTLES this field as tier 1. The tension is recorded here so the "
        "settlement is visible as a ruling rather than as an omission. Consequence: like the rest "
        "fields, this one inherits M_A1's enumerated game_date exception set, and it carries the "
        "same S37 B1 career-vs-same-season clock ambiguity, measured above.",
        ["THE USER'S NAMING OF 'venue/timezone' IN THE TIER-1 LIST IS WHAT SETTLES THIS FIELD. "
         "Absent that naming, this field would have gone to RAISE-DO-NOT-ASSIGN."]),
]

RAISE_DO_NOT_ASSIGN = [
    {
        "id": "R1",
        "concerns": ["sched.season_type", "sched.opp_team_id", "sched.is_home",
                     "venue.venue_team_id", "timezone.venue_iana_timezone",
                     "timezone.shift_from_prev_venue_hours"],
        "scope": "PLAYOFF ROWS ONLY",
        "census": M["_playoff_boundary_census"],
        "the_boundary": (
            "The user's tier-1 discriminator was stated as: 'is the VALUE fixed by the schedule "
            "before tipoff, or is it COMPUTED FROM OBSERVATIONS? Tier 1 is the former.' On playoff "
            "rows BOTH clauses are true at once. Which teams meet, which of them hosts, in which "
            "arena and in which time zone are all determined by regular-season standings and prior "
            "series RESULTS -- i.e. computed from observations -- and are nonetheless fixed before "
            "that particular game's own tipoff. The two halves of the discriminator do not "
            "partition these rows."),
        "why_this_is_NOT_being_resolved_here": (
            "Assigning a tier IS deciding the standard of proof, and D065 reserves that judgement "
            "to the user. This node does not reassign any field and does not narrow any receipt."),
        "what_this_node_believes_but_did_not_act_on": (
            "The literal tier-1 standard as written ('derives from information fixed before "
            "tipoff') is MET on playoff rows, because prior-game results are fixed before this "
            "game's tipoff and are legitimately available to a strictly-prior model. On that "
            "reading no change is needed. The flag exists because the user's SECOND clause "
            "('computed from observations') would, read alone, exclude them."),
        "cheapest_possible_ruling": (
            "One sentence: 'for tier-1 purposes, information determined by the outcomes of games "
            "that were themselves completed before this game's cutoff counts as fixed before "
            "tipoff.' If the user agrees, R1 closes with no further measurement."),
    },
    {
        "id": "R2",
        "concerns": ["rest.is_back_to_back", "rest.games_in_prev_7_days",
                     "timezone.shift_from_prev_venue_hours"],
        "scope": "ALL ROWS -- 'scheduled' vs 'as played'",
        "the_boundary": (
            "The user's tier-1 list said 'scheduled rest/B2B/3-in-4'. No SCHEDULED-date artifact "
            "exists in this repository -- D10 section 4.1 measured that the only artifact carrying "
            "the schedule is a completed-game box score. Every rest and previous-venue quantity in "
            "this slate is therefore computed from AS-PLAYED dates. The two agree except on "
            "postponed or displaced fixtures, which is precisely the population M_A1 enumerated as "
            "its exception set."),
        "why_this_is_NOT_being_resolved_here": (
            "Ruling that as-played dates satisfy a 'scheduled' tier-1 standard would change the "
            "standard of proof, which is the user's to set. This node records the substitution "
            "instead of assuming it away."),
        "what_would_close_it_cheaply": (
            "Either (a) the user rules that as-played dates are an acceptable stand-in for "
            "scheduled dates for tier-1 purposes given that M_A1 already enumerates the divergent "
            "clusters, or (b) SC06's existing A1-SENSITIVITY kill is actually wired (S37 finding "
            "B3 records that it currently reads nothing), which converts the substitution from an "
            "assumption into a measured sensitivity. Option (b) needs no new data."),
    },
    {
        "id": "R3",
        "concerns": ["rest.games_in_prev_7_days"],
        "scope": "FIELD IDENTITY, not tier",
        "the_boundary": (
            "Ledger #10 is named 'rest.games_in_prev_7_days' and D10 derives a 7-day count. SC06 "
            "consumes a 3-in-4 indicator. The S37 A9 table papers this over with the parenthetical "
            "'(the 3-in-4 class)'. They are different quantities and only one of them is consumed "
            "by any arm. This receipt covers the 3-in-4 indicator that SC06 actually consumes and "
            "counts both."),
        "why_this_is_NOT_being_resolved_here": (
            "Deciding which quantity ledger #10 denotes is a contract question, not a measurement. "
            "It does not change either field's tier -- both are schedule-derived -- but it changes "
            "what the receipt is a receipt FOR."),
    },
]

out = {
    "schema": "s43_tier1_cutoff_receipts/1",
    "node_id": "S43_CUTOFF_RECEIPTS_TIER1",
    "commissioned_by": "user decision D065",
    "discharges": "part of S37 audit finding A9 (Severity A)",
    "epistemic_status": (
        "PROVENANCE RECEIPT. A demonstration that each field's VALUE is fixed by the schedule "
        "before tipoff rather than computed from observations, plus the producing job and its "
        "as-of bound. NOT a per-observation timestamp audit. No fitting; no performance number of "
        "any kind; counts, censuses, hashes and provenance only."),
    "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    "tier1_standard_verbatim_from_D065": (
        "Opponent, home/away, season type, scheduled rest/B2B/3-in-4, venue/timezone: these should "
        "require only a cheap provenance receipt showing they derive from information fixed before "
        "tipoff. ... So don't turn 12 fields into 12 research projects. Establish the minimum "
        "sufficient proof for each field, record it, and unblock fitting."),
    "mandatory_receipt_content_rationale": (
        "A cheap provenance receipt proves the CLASS of a field, not the integrity of the pipeline "
        "that produced it. If a tier-1 field is materialised by a job that happens to backfill "
        "from a later source, a concept-only receipt would not catch it. Naming the producing job "
        "and its as-of bound closes most of that gap at no extra cost."),
    "d10_ledger_objection_engaged_not_evaded": LEDGER_OBJECTION,
    "coordinator_assigned_tier": {
        "fields": ["sched.game_id", "sched.season"],
        "assigned_by": "coordinator #04",
        "ground": ("both are plainly schedule-fixed and not computed from observations: season is "
                   "literally int('20' + game_id[3:5]) and game_id is the league's own fixture "
                   "identifier"),
        "user_named_tier1_list": ["opponent", "home/away", "season type",
                                  "scheduled rest/B2B/3-in-4", "venue/timezone"],
        "note": "Recorded explicitly so the user can overrule the assignment cheaply. If overruled, "
                "these two fields return to the A9 unreceipted set and this node's other eight "
                "receipts are unaffected.",
    },
    "raise_do_not_assign": RAISE_DO_NOT_ASSIGN,
    "universe": universe,
    "fields": fields,
    "prohibitions_observed": {
        "no_fitting": True,
        "no_performance_numbers": True,
        "observed_time_dropped_before_every_write": OBSERVED_TIME_DROPPED,
        "no_frame_written_to_disk": True,
        "no_git_command_run": True,
        "wrote_only_inside": "experiments/player_program/stage3_score/S43_CUTOFF_RECEIPTS_TIER1/",
        "frozen_artifacts_modified": "none",
    },
    "evidence_sha256_all_reads": READS,
}

with open(os.path.join(HERE, "RECEIPTS.json"), "w", encoding="utf-8") as fh:
    json.dump(out, fh, indent=1)

print(json.dumps({
    "node": out["node_id"],
    "fields_receipted": len(fields),
    "verdicts": {f["field"]: f["verdict"] for f in fields},
    "tier_assigned_by": {f["field"]: f["tier_assigned_by"] for f in fields},
    "raise_do_not_assign": [r["id"] for r in RAISE_DO_NOT_ASSIGN],
    "universe": {k: universe[k] for k in
                 ("clusters", "team_game_rows", "playoff_rows", "playoff_clusters",
                  "o2_prebuild_digest_match", "master_team_pin_matched")},
    "n_evidence_files_hashed": len(READS),
}, indent=1))
