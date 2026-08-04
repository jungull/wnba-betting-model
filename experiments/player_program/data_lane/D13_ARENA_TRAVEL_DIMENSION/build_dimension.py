#!/usr/bin/env python3
"""
D13_ARENA_TRAVEL_DIMENSION -- build the unique effective-dated team/arena/travel
dimension from data/reference/team_cities.csv.

Epistemic status: REFERENCE DATA + INVARIANT. Fixes the S2 fan-out hazard at its source.

This script MEASURES. It does not assert. Every number it prints is computed here.

Outputs (all under this node's write scope):
  arena_dimension_v1.csv        one row per (team_id, season) -- the DECLARED KEY
  arena_dimension_v1.meta.json  column-by-column derivation + provenance
  venue_pair_travel_v1.csv      ordered venue-pair great-circle + tz-offset deltas
  MEASUREMENTS.json             everything measured, for REPORT.md and FINDINGS.json

Run:  python experiments/player_program/data_lane/D13_ARENA_TRAVEL_DIMENSION/build_dimension.py
from the worktree root.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]  # worktree root

SRC_CITIES = ROOT / "data" / "reference" / "team_cities.csv"
SRC_MASTER = ROOT / "data" / "masters" / "master_team.parquet"
SRC_PRIOR = (
    ROOT
    / "experiments"
    / "player_program"
    / "projected_exposure_v1"
    / "team_possession_prior_v1.parquet"
)

# Open-ended effective interval sentinel. NOT a real season; chosen far above any
# season the data can contain, and asserted to be so below.
OPEN_END = 9999

# Earth mean radius, IUGG. Fixed here so the derivation is auditable.
EARTH_RADIUS_KM = 6371.0088


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    """Great-circle distance on a sphere of radius EARTH_RADIUS_KM."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def utc_offset_hours(tzname: str, when: dt.datetime) -> float:
    off = when.replace(tzinfo=None).astimezone(ZoneInfo(tzname)).utcoffset()
    # build an aware datetime in that zone instead -- the above is ambiguous on
    # naive input, so do it explicitly:
    aware = when.replace(tzinfo=ZoneInfo(tzname))
    off = aware.utcoffset()
    assert off is not None
    return off.total_seconds() / 3600.0


def main() -> int:
    M: dict = {"generated_utc": dt.datetime.now(dt.timezone.utc).isoformat()}

    # ------------------------------------------------------------------ source
    raw = pd.read_csv(SRC_CITIES)
    M["source_files"] = {
        "team_cities_csv": {
            "path": "data/reference/team_cities.csv",
            "sha256": sha256(SRC_CITIES),
            "rows": int(len(raw)),
            "columns": list(raw.columns),
        },
        "master_team_parquet": {
            "path": "data/masters/master_team.parquet",
            "sha256": sha256(SRC_MASTER),
        },
        "team_possession_prior_v1": {
            "path": "experiments/player_program/projected_exposure_v1/team_possession_prior_v1.parquet",
            "sha256": sha256(SRC_PRIOR),
        },
    }

    # --------------------------------------------------- raw hazard restatement
    dup = raw.groupby("team_id").size()
    M["raw_source"] = {
        "rows": int(len(raw)),
        "distinct_team_id": int(raw["team_id"].nunique()),
        "duplicated_team_id": {
            str(k): int(v) for k, v in dup[dup > 1].to_dict().items()
        },
        "last_season_dtype": str(raw["last_season"].dtype),
        "last_season_nulls": int(raw["last_season"].isna().sum()),
        "last_season_non_null_values": sorted(
            raw.loc[raw["last_season"].notna(), "last_season"].tolist()
        ),
        "first_season_dtype": str(raw["first_season"].dtype),
        "first_season_nulls": int(raw["first_season"].isna().sum()),
        "elevation_ft_min": int(raw["elevation_ft"].min()),
        "elevation_ft_max": int(raw["elevation_ft"].max()),
        "rows_elevation_gt_1000": int((raw["elevation_ft"] > 1000).sum()),
        "distinct_franchises_elevation_gt_1000": int(
            raw.loc[raw["elevation_ft"] > 1000, "team_id"].nunique()
        ),
        "distinct_arenas_elevation_gt_1000": int(
            raw.loc[raw["elevation_ft"] > 1000, "arena"].nunique()
        ),
        "distinct_arena_strings": int(raw["arena"].nunique()),
        "distinct_timezones": sorted(raw["timezone"].unique().tolist()),
    }

    # Are the duplicated team_id's rows identical on the physical venue fields?
    d = raw[raw["team_id"].isin(dup[dup > 1].index)]
    phys = ["city", "arena", "lat", "lon", "elevation_ft", "timezone"]
    M["raw_source"]["duplicate_rows_agree_on_physical_fields"] = bool(
        d[phys].drop_duplicates().shape[0] == 1
    )
    M["raw_source"]["duplicate_rows_differ_on"] = [
        c
        for c in raw.columns
        if d[c].nunique(dropna=False) > 1
    ]

    # ------------------------------------------------ effective-date semantics
    # DOCUMENTED SEMANTICS, quoted from the producer data/reference/collect_bios.py:
    #   "One row per (team_id, abbreviation). PHO (2021-2024) and PHX (2025-) are
    #    the same franchise/team_id 1611661317 - the 2025 abbreviation rename."
    # => a row is effective for seasons [first_season, last_season], with a null
    #    last_season meaning "still current" (open-ended).
    dim_src = raw.copy()
    dim_src["eff_first_season"] = dim_src["first_season"].astype("int64")
    dim_src["eff_last_season"] = (
        dim_src["last_season"].fillna(OPEN_END).astype("int64")
    )
    dim_src["eff_last_season_is_open"] = dim_src["last_season"].isna()

    # INVARIANT 1: intervals are well-formed
    bad_interval = dim_src[dim_src["eff_first_season"] > dim_src["eff_last_season"]]

    # INVARIANT 2: intervals within a team_id are disjoint and gapless
    overlaps, gaps = [], []
    for tid, grp in dim_src.sort_values("eff_first_season").groupby("team_id"):
        rows = grp[["eff_first_season", "eff_last_season", "abbreviation"]].values.tolist()
        for i in range(1, len(rows)):
            prev_last = rows[i - 1][1]
            cur_first = rows[i][0]
            if cur_first <= prev_last:
                overlaps.append(
                    {"team_id": int(tid), "prev": rows[i - 1], "cur": rows[i]}
                )
            elif cur_first > prev_last + 1:
                gaps.append({"team_id": int(tid), "prev": rows[i - 1], "cur": rows[i]})

    M["effective_dating"] = {
        "semantics": "row effective for seasons [eff_first_season, eff_last_season]; "
        "null last_season == open-ended, encoded as 9999",
        "documented_by": "data/reference/collect_bios.py, phase_cities() header comment",
        "malformed_intervals": int(len(bad_interval)),
        "overlapping_intervals_within_team_id": overlaps,
        "gaps_within_team_id": gaps,
        "open_end_sentinel": OPEN_END,
    }

    # ------------------------------------------------- corroborate vs the master
    mt = pd.read_parquet(
        SRC_MASTER, columns=["team_id", "team_abbreviation", "season", "game_id", "is_home", "game_date"]
    )
    mk = (
        mt.groupby(["team_id", "team_abbreviation"])["season"]
        .agg(master_first="min", master_last="max")
        .reset_index()
        .rename(columns={"team_abbreviation": "abbreviation"})
    )
    corr = mk.merge(
        dim_src[["team_id", "abbreviation", "eff_first_season", "eff_last_season"]],
        on=["team_id", "abbreviation"],
        how="outer",
        indicator=True,
        validate="1:1",
    )
    max_season = int(mt["season"].max())
    corr["first_agrees"] = corr["master_first"] == corr["eff_first_season"]
    corr["last_agrees"] = corr.apply(
        lambda r: (r["master_last"] == r["eff_last_season"])
        or (r["eff_last_season"] == OPEN_END and r["master_last"] == max_season),
        axis=1,
    )
    M["master_corroboration"] = {
        "master_team_abbrev_pairs": int(len(mk)),
        "merge_indicator_counts": {
            str(k): int(v) for k, v in corr["_merge"].value_counts().to_dict().items()
        },
        "first_season_disagreements": int((~corr["first_agrees"]).sum()),
        "last_season_disagreements": int((~corr["last_agrees"]).sum()),
        "max_season_in_master": max_season,
        "open_end_sentinel_exceeds_max_season": bool(OPEN_END > max_season),
        "disagreement_rows": corr.loc[
            (~corr["first_agrees"]) | (~corr["last_agrees"]),
            ["team_id", "abbreviation", "master_first", "master_last",
             "eff_first_season", "eff_last_season"],
        ].to_dict("records"),
    }

    # ------------------------------------------------------ the target universe
    prior = pd.read_parquet(SRC_PRIOR)
    universe = prior[prior["pace_resolved"]].copy()
    M["universe"] = {
        "definition": "team_possession_prior_v1.parquet where pace_resolved == True",
        "team_game_rows": int(len(universe)),
        "game_clusters": int(universe["game_id"].nunique()),
        "all_rows_in_file": int(len(prior)),
        "all_games_in_file": int(prior["game_id"].nunique()),
        "seasons": sorted(int(s) for s in universe["season"].unique()),
    }

    # ------------------------------------------------------ EXPLODE to the key
    # Declared key: (team_id, season). One row per team-season the interval covers,
    # restricted to seasons that actually occur in the master. NO arbitrary
    # first/last dedup anywhere -- every output row is produced by INTERVAL
    # CONTAINMENT, and uniqueness is proved below rather than imposed.
    seasons = sorted(int(s) for s in mt["season"].unique())
    M["seasons_in_master"] = seasons

    recs = []
    for _, r in dim_src.iterrows():
        for s in seasons:
            if r["eff_first_season"] <= s <= r["eff_last_season"]:
                recs.append(
                    {
                        "team_id": int(r["team_id"]),
                        "season": int(s),
                        "abbreviation": r["abbreviation"],
                        "franchise": r["franchise"],
                        "city": r["city"],
                        "arena": r["arena"],
                        "lat": float(r["lat"]),
                        "lon": float(r["lon"]),
                        "elevation_ft": int(r["elevation_ft"]),
                        "timezone": r["timezone"],
                        "eff_first_season": int(r["eff_first_season"]),
                        "eff_last_season": int(r["eff_last_season"]),
                        "eff_last_season_is_open": bool(r["eff_last_season_is_open"]),
                    }
                )
    dim = pd.DataFrame.from_records(recs)

    # ---------------------------------------------------- derived travel fields
    # venue_id: stable surrogate for the physical building. Derived as the
    # lowercased arena string with non-alphanumerics collapsed. Phoenix's two
    # abbreviation rows share one building and therefore one venue_id.
    dim["venue_id"] = (
        dim["arena"].str.lower().str.replace(r"[^a-z0-9]+", "_", regex=True).str.strip("_")
    )

    # Reference instants for UTC-offset derivation. The WNBA regular season runs
    # inside the northern summer, so JUL_REF is the operative one; JAN_REF exists
    # only to detect whether the zone observes DST at all.
    JUL_REF = dt.datetime(2024, 7, 1, 12, 0)
    JAN_REF = dt.datetime(2024, 1, 15, 12, 0)
    dim["utc_offset_hours_jul"] = dim["timezone"].map(
        lambda z: utc_offset_hours(z, JUL_REF)
    )
    dim["utc_offset_hours_jan"] = dim["timezone"].map(
        lambda z: utc_offset_hours(z, JAN_REF)
    )
    dim["observes_dst"] = dim["utc_offset_hours_jul"] != dim["utc_offset_hours_jan"]
    dim["elevation_m"] = (dim["elevation_ft"] * 0.3048).round(1)

    dim = dim.sort_values(["team_id", "season"]).reset_index(drop=True)

    # -------------------------------------------------------- CARDINALITY TESTS
    key = ["team_id", "season"]
    dup_key = dim.duplicated(subset=key).sum()
    universe_keys = universe[key].drop_duplicates()
    missing = universe_keys.merge(dim[key], on=key, how="left", indicator=True)
    missing = missing[missing["_merge"] == "left_only"]

    # the merge that S2 says is unsafe, now done safely
    before_rows = len(universe)
    before_games = universe["game_id"].nunique()
    before_keyset = set(map(tuple, universe[["game_id", "team_id"]].values))
    merged = universe.merge(dim, on=key, how="left", validate="m:1")
    after_keyset = set(map(tuple, merged[["game_id", "team_id"]].values))

    new_null_cols = {
        c: int(merged[c].isna().sum())
        for c in dim.columns
        if c not in key and merged[c].isna().sum() > 0
    }

    # the merge that S2 says fans out -- measured, not assumed
    naive_dim = raw.copy()
    naive = universe.merge(naive_dim, on="team_id", how="left")
    naive_rows = len(naive)

    M["dimension"] = {
        "declared_key": key,
        "rows": int(len(dim)),
        "distinct_team_id": int(dim["team_id"].nunique()),
        "distinct_venue_id": int(dim["venue_id"].nunique()),
        "duplicate_key_rows": int(dup_key),
        "unique_on_declared_key": bool(dup_key == 0),
        "nulls_by_column": {c: int(dim[c].isna().sum()) for c in dim.columns},
        "team_seasons_per_season": {
            str(k): int(v) for k, v in dim.groupby("season").size().to_dict().items()
        },
    }
    M["cardinality_tests"] = {
        "universe_team_season_keys": int(len(universe_keys)),
        "universe_keys_absent_from_dimension": int(len(missing)),
        "safe_merge_validate": "m:1 on (team_id, season)",
        "rows_before": int(before_rows),
        "rows_after": int(len(merged)),
        "rows_unchanged": bool(len(merged) == before_rows),
        "game_clusters_before": int(before_games),
        "game_clusters_after": int(merged["game_id"].nunique()),
        "game_clusters_unchanged": bool(merged["game_id"].nunique() == before_games),
        "team_game_keyset_identical": bool(before_keyset == after_keyset),
        "null_expansion_by_column": new_null_cols,
        "null_expansion_total": int(sum(new_null_cols.values())),
        "naive_merge_on_team_id_only_rows": int(naive_rows),
        "naive_merge_excess_rows": int(naive_rows - before_rows),
        "naive_merge_affected_team_id": 1611661317,
        "naive_merge_affected_rows_in_universe": int(
            (universe["team_id"] == 1611661317).sum()
        ),
    }

    # ------------------------------------------------------- venue pair travel
    # Again: dedup on the FULL tuple, then PROVE venue_id is unique in the result.
    venues = (
        dim[["venue_id", "arena", "city", "lat", "lon", "elevation_ft", "timezone"]]
        .drop_duplicates()
        .reset_index(drop=True)
    )
    if not venues["venue_id"].is_unique:
        raise SystemExit(
            "FATAL: venue_id is not unique after full-tuple dedup -- two rows share "
            "an arena name but differ on a physical field. Resolve the source, do "
            "not pick a row."
        )
    pairs = []
    for _, a in venues.iterrows():
        for _, b in venues.iterrows():
            km = haversine_km(a["lat"], a["lon"], b["lat"], b["lon"])
            pairs.append(
                {
                    "from_venue_id": a["venue_id"],
                    "to_venue_id": b["venue_id"],
                    "great_circle_km": round(km, 3),
                    "great_circle_mi": round(km * 0.621371, 3),
                    "elevation_gain_ft": int(b["elevation_ft"] - a["elevation_ft"]),
                    "tz_offset_delta_hours_jul": round(
                        utc_offset_hours(b["timezone"], JUL_REF)
                        - utc_offset_hours(a["timezone"], JUL_REF),
                        2,
                    ),
                }
            )
    vp = pd.DataFrame(pairs)

    # distance-matrix invariants
    piv = vp.pivot(index="from_venue_id", columns="to_venue_id", values="great_circle_km")
    diag_max = float(max(abs(piv.loc[v, v]) for v in piv.index))
    sym_max = float((piv - piv.T).abs().to_numpy().max())
    vids = list(piv.index)
    tri_viol = 0
    for i in vids:
        for j in vids:
            for k in vids:
                if piv.loc[i, k] > piv.loc[i, j] + piv.loc[j, k] + 1e-6:
                    tri_viol += 1
    M["venue_pair_travel"] = {
        "distinct_venues": int(len(venues)),
        "ordered_pairs": int(len(vp)),
        "diagonal_max_abs_km": diag_max,
        "symmetry_max_abs_km": sym_max,
        "triangle_inequality_violations": int(tri_viol),
        "max_pair_km": float(vp["great_circle_km"].max()),
        "max_pair": vp.loc[vp["great_circle_km"].idxmax(),
                           ["from_venue_id", "to_venue_id", "great_circle_km"]].to_dict(),
        "max_abs_tz_delta_hours_jul": float(vp["tz_offset_delta_hours_jul"].abs().max()),
        "max_abs_elevation_gain_ft": int(vp["elevation_gain_ft"].abs().max()),
    }

    # ----------------------------------------------- home-venue assignability
    # A team-game's venue is the HOME team's venue. Measure whether is_home is
    # complete and consistent over the universe, and whether any per-game venue
    # override column exists anywhere in the master (it does not -> neutral-site
    # and relocation games are silently mis-located).
    u = universe.merge(
        mt[["game_id", "team_id", "is_home", "game_date"]],
        on=["game_id", "team_id"],
        how="left",
        validate="1:1",
    )
    per_game = u.groupby("game_id")["is_home"].agg(["sum", "size"])
    M["home_venue_assignment"] = {
        "is_home_nulls_in_universe": int(u["is_home"].isna().sum()),
        "games_with_exactly_one_home": int(
            ((per_game["sum"] == 1) & (per_game["size"] == 2)).sum()
        ),
        "games_in_universe": int(len(per_game)),
        "venue_column_present_in_master_team": bool(
            any("venue" in c.lower() or "arena" in c.lower()
                for c in pd.read_parquet(SRC_MASTER).columns)
        ),
    }

    # ------------------------------------- is elevation a team-identity proxy?
    # A field that is a bijection with team_id over the dimension carries no
    # information a team fixed effect does not already carry. Measure it; do not
    # assume it either way.
    # NOTE: deduplicated on the FULL column tuple, never on team_id alone. That
    # makes the result order-independent, and it PROVES rather than imposes the
    # claim that these fields are constant within a team: if any team varied
    # across seasons, static would have more rows than there are teams.
    static = dim[
        ["team_id", "elevation_ft", "timezone", "utc_offset_hours_jul", "venue_id"]
    ].drop_duplicates()
    M["identity_proxy_check"] = {
        "teams": int(dim["team_id"].nunique()),
        "static_rows_equals_team_count": bool(len(static) == dim["team_id"].nunique()),
        "distinct_elevation_ft": int(static["elevation_ft"].nunique()),
        "elevation_is_bijection_with_team_id": bool(
            static["elevation_ft"].nunique() == dim["team_id"].nunique()
        ),
        "distinct_timezone": int(static["timezone"].nunique()),
        "timezone_is_bijection_with_team_id": bool(
            static["timezone"].nunique() == dim["team_id"].nunique()
        ),
        "distinct_utc_offset_hours_jul": int(static["utc_offset_hours_jul"].nunique()),
        "teams_changing_arena_across_seasons": int(
            (dim.groupby("team_id")["venue_id"].nunique() > 1).sum()
        ),
        "teams_changing_elevation_across_seasons": int(
            (dim.groupby("team_id")["elevation_ft"].nunique() > 1).sum()
        ),
    }

    # ------------------------------- game-venue assignment over the universe
    # The venue of a team-game is the HOME team's venue. Attach it and measure
    # what actually varies. This is a DERIVATION DEMONSTRATION, not a feature.
    home = u[u["is_home"] == 1][["game_id", "team_id", "season"]].rename(
        columns={"team_id": "home_team_id"}
    )
    gv = u.merge(home[["game_id", "home_team_id"]], on="game_id", how="left", validate="m:1")
    gv = gv.merge(
        dim[["team_id", "season", "venue_id", "elevation_ft", "timezone",
             "utc_offset_hours_jul", "lat", "lon"]].rename(
            columns={"team_id": "home_team_id", "venue_id": "game_venue_id",
                     "elevation_ft": "game_venue_elevation_ft",
                     "timezone": "game_venue_timezone",
                     "utc_offset_hours_jul": "game_venue_utc_offset_jul",
                     "lat": "game_venue_lat", "lon": "game_venue_lon"}
        ),
        on=["home_team_id", "season"],
        how="left",
        validate="m:1",
    )
    M["game_venue_derivation"] = {
        "rule": "game venue := the dimension row of the HOME team for that season",
        "rows": int(len(gv)),
        "rows_unchanged_vs_universe": bool(len(gv) == before_rows),
        "game_venue_id_nulls": int(gv["game_venue_id"].isna().sum()),
        "distinct_game_venue_elevations_per_team_min": int(
            gv.groupby("team_id")["game_venue_elevation_ft"].nunique().min()
        ),
        "distinct_game_venue_elevations_per_team_max": int(
            gv.groupby("team_id")["game_venue_elevation_ft"].nunique().max()
        ),
        "share_of_team_games_at_own_venue": round(
            float((gv["team_id"] == gv["home_team_id"]).mean()), 6
        ),
        "game_venue_elevation_gt_1000_rows": int(
            (gv["game_venue_elevation_ft"] > 1000).sum()
        ),
        "game_venue_elevation_gt_1000_share": round(
            float((gv["game_venue_elevation_ft"] > 1000).mean()), 6
        ),
        "note": "this attachment is a demonstration that the merge is safe; it is "
                "NOT an admission of any of these columns to a feature matrix",
    }

    # ------------------------------------------------- first_season censoring
    # first_season for pre-2021 franchises is the DATA WINDOW start, not the
    # franchise founding year. Measure how many rows are left-censored.
    M["first_season_censoring"] = {
        "rows_with_first_season_equal_to_window_start": int(
            (dim_src["eff_first_season"] == min(seasons)).sum()
        ),
        "window_start_season": int(min(seasons)),
        "rows_with_first_season_after_window_start": int(
            (dim_src["eff_first_season"] > min(seasons)).sum()
        ),
        "franchises_entering_after_window_start": sorted(
            dim_src.loc[dim_src["eff_first_season"] > min(seasons), "abbreviation"].tolist()
        ),
    }

    # ------------------------- in-season UTC-offset collapse (timezone != offset)
    off = (
        dim[["timezone", "utc_offset_hours_jul", "observes_dst"]]
        .drop_duplicates()
        .sort_values("timezone")
    )
    M["timezone_vs_offset"] = {
        "distinct_iana_zones": int(off["timezone"].nunique()),
        "distinct_july_utc_offsets": int(off["utc_offset_hours_jul"].nunique()),
        "zone_to_july_offset": {
            r["timezone"]: float(r["utc_offset_hours_jul"]) for _, r in off.iterrows()
        },
        "zones_not_observing_dst": sorted(
            off.loc[~off["observes_dst"], "timezone"].tolist()
        ),
        "note": "the IANA zone string and the in-season UTC offset are DIFFERENT "
                "partitions. Six zones collapse to three July offsets. A feature "
                "keyed on the zone string is not the same object as one keyed on "
                "the offset, and the two must not be used interchangeably.",
    }

    # -------------- latent hazard in the shipped producer, measured not assumed
    # data/reference/collect_bios.py phase_tips() does
    #     cities.drop_duplicates("team_id").set_index("team_id")["timezone"]
    # which is exactly the arbitrary-first-row deduplication this node forbids.
    # Measure whether it currently changes any value.
    first_tz = raw.drop_duplicates("team_id", keep="first").set_index("team_id")["timezone"]
    last_tz = raw.drop_duplicates("team_id", keep="last").set_index("team_id")["timezone"]
    disagree = [str(t) for t in first_tz.index if first_tz[t] != last_tz[t]]
    M["producer_latent_dedup_hazard"] = {
        "location": "data/reference/collect_bios.py :: phase_tips()",
        "pattern": 'cities.drop_duplicates("team_id")',
        "team_ids_where_first_and_last_row_disagree_on_timezone": disagree,
        "currently_changes_any_value": bool(disagree),
        "why_it_is_still_a_defect": "it is harmless ONLY because the two Phoenix "
            "rows happen to agree on timezone. Any future effective-dated row that "
            "differs on a physical field (a real relocation) would be silently "
            "resolved by CSV row order.",
        "in_this_node_write_scope": False,
    }

    # -------------------------------------------------- cutoff-validity status
    # The source carries NO row-level asof / source timestamp column. Its only
    # temporal evidence is the single git commit that introduced it. Measure the
    # relation between that commit and the universe's game dates; do not assume.
    SOURCE_COMMIT = "a3677bcdb086b54444db9190c49bf25713f06bcc"
    SOURCE_COMMIT_DATE = "2026-07-31T09:32:28-04:00"
    commit_day = pd.Timestamp("2026-07-31")
    M["cutoff_validity"] = {
        "row_level_source_timestamp_column_present": bool(
            any(c.lower() in {"asof", "as_of", "source_timestamp", "observed_time",
                              "captured_at", "snapshot_timestamp"}
                for c in raw.columns)
        ),
        "source_columns": list(raw.columns),
        "only_temporal_evidence": f"git commit {SOURCE_COMMIT} at {SOURCE_COMMIT_DATE}",
        "universe_min_game_date": str(universe["game_date"].min().date()),
        "universe_max_game_date": str(universe["game_date"].max().date()),
        "universe_rows_on_or_after_source_commit_day": int(
            (universe["game_date"] >= commit_day).sum()
        ),
        "universe_games_on_or_after_source_commit_day": int(
            universe.loc[universe["game_date"] >= commit_day, "game_id"].nunique()
        ),
        "status": "CUTOFF_UNPROVEN",
        "reasoning": "no row-level source timestamp exists, and the file's only "
                     "timestamp is a commit dated at or after every game date in "
                     "the universe. The CONTENT is time-invariant physical fact, "
                     "but time-invariance of content is not a proof of cutoff "
                     "validity of the record, and this node does not treat it as one.",
    }

    # ------------------------------------------------------------------ write
    dim.to_csv(HERE / "arena_dimension_v1.csv", index=False)
    vp.to_csv(HERE / "venue_pair_travel_v1.csv", index=False)

    meta = {
        "artifact": "arena_dimension_v1.csv",
        "declared_key": key,
        "grain": "one row per (team_id, season) that the source's effective-date "
                 "interval covers, restricted to seasons present in master_team",
        "built_by": "experiments/player_program/data_lane/D13_ARENA_TRAVEL_DIMENSION/build_dimension.py",
        "source_sha256": M["source_files"],
        "cutoff_status": "CUTOFF_UNPROVEN_BUT_TIME_INVARIANT -- see REPORT.md. The "
                         "source carries NO row-level source timestamp. Its single "
                         "git commit is 2026-07-31, AFTER every game in the universe.",
        "columns": {
            "team_id": {"derivation": "verbatim from team_cities.csv", "type": "int64"},
            "season": {"derivation": "EXPANDED: every season s in master_team with "
                                     "eff_first_season <= s <= eff_last_season",
                       "type": "int64"},
            "abbreviation": {"derivation": "verbatim; effective-dated (PHO 2021-2024, PHX 2025-)",
                             "type": "str"},
            "franchise": {"derivation": "verbatim", "type": "str"},
            "city": {"derivation": "verbatim; hand-entered 2026-07-31, city-level precision",
                     "type": "str"},
            "arena": {"derivation": "verbatim; the team's PRIMARY home arena for the "
                                    "season. NOT a per-game venue.", "type": "str"},
            "lat": {"derivation": "verbatim from team_cities.csv. Producer states "
                                  "'lat/lon = arena/metro, city-level precision'. "
                                  "Hand-entered, no upstream geocoder recorded.",
                    "type": "float degrees, WGS84 assumed but NOT stated by the source"},
            "lon": {"derivation": "as lat", "type": "float degrees"},
            "elevation_ft": {"derivation": "verbatim. Producer states 'elevation_ft "
                                           "approximate'. No datum, no method, no "
                                           "upstream source recorded.", "type": "int feet"},
            "elevation_m": {"derivation": "elevation_ft * 0.3048, rounded to 0.1 m. "
                                          "Unit conversion only -- inherits the "
                                          "source's stated approximateness.",
                            "type": "float metres"},
            "timezone": {"derivation": "verbatim IANA tz database identifier. "
                                       "Validated here by successful ZoneInfo() "
                                       "construction for all 16 source rows.",
                         "type": "str IANA"},
            "utc_offset_hours_jul": {
                "derivation": "ZoneInfo(timezone).utcoffset() at the fixed reference "
                              "instant 2024-07-01 12:00 local, in hours. The WNBA "
                              "regular season sits inside northern summer, so this "
                              "is the operative offset. It is a FIXED-INSTANT "
                              "reference, not a per-game offset.",
                "type": "float hours"},
            "utc_offset_hours_jan": {
                "derivation": "same at 2024-01-15 12:00 local. Exists ONLY to derive "
                              "observes_dst.", "type": "float hours"},
            "observes_dst": {"derivation": "utc_offset_hours_jul != utc_offset_hours_jan",
                             "type": "bool"},
            "venue_id": {"derivation": "arena.lower() with runs of non-alphanumerics "
                                       "replaced by '_' and stripped. Collapses the two "
                                       "Phoenix abbreviation rows onto one building.",
                         "type": "str surrogate"},
            "eff_first_season": {"derivation": "first_season verbatim (int)", "type": "int64"},
            "eff_last_season": {"derivation": "last_season, with null -> 9999 "
                                              "(open-ended sentinel)", "type": "int64"},
            "eff_last_season_is_open": {"derivation": "last_season.isna()", "type": "bool"},
        },
        "companion": {
            "venue_pair_travel_v1.csv": {
                "grain": "one row per ORDERED (from_venue_id, to_venue_id) pair",
                "great_circle_km": f"haversine on a sphere of radius {EARTH_RADIUS_KM} km "
                                   "(IUGG mean). NOT road/air distance, NOT geodesic on "
                                   "an ellipsoid. Inherits the city-level precision of lat/lon.",
                "great_circle_mi": "great_circle_km * 0.621371",
                "elevation_gain_ft": "to.elevation_ft - from.elevation_ft",
                "tz_offset_delta_hours_jul": "to.utc_offset_hours_jul - from.utc_offset_hours_jul",
            }
        },
        "NOT_provided": [
            "per-game venue (no venue/arena column exists in master_team -- verified)",
            "neutral-site, relocation, in-season arena change and international-game overrides",
            "actual travel path, rest days, or trip origin -- this dimension is STATIC "
            "reference only and asserts nothing about any team's real itinerary",
        ],
    }
    (HERE / "arena_dimension_v1.meta.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )

    M["outputs"] = {
        "arena_dimension_v1.csv": sha256(HERE / "arena_dimension_v1.csv"),
        "venue_pair_travel_v1.csv": sha256(HERE / "venue_pair_travel_v1.csv"),
        "arena_dimension_v1.meta.json": sha256(HERE / "arena_dimension_v1.meta.json"),
    }
    (HERE / "MEASUREMENTS.json").write_text(json.dumps(M, indent=2), encoding="utf-8")
    print(json.dumps(M, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
