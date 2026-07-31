"""backfill_manifests.py — attest the fitted artifacts that predate the manifest convention.

Step 2 of ``project_docs/PLAN_2026-07-31_W1_AUDIT_AND_BAKEOFF.md`` (frozen as
``plan_freeze_2026_07_31``), serving ``screening_protocol_amendment_v5`` C3-BLOCKING:
no result may support a promotion, nomination or freeze decision until every fitted
artifact it consumes carries a manifest recording ``fit_through`` as WHEN THE SOURCE
INFORMATION BECAME AVAILABLE.

``asof_invariant.py --scan`` reports 20 unattested artifacts. They were all built
before the manifest convention existed, so their fit windows live in producer
constants, filenames and column values rather than in a sidecar. This script writes
those sidecars.

THE RULE THIS SCRIPT OBEYS
--------------------------
Every ``fit_through_date`` written here is DERIVED FROM EVIDENCE THAT IS NAMED IN
THE TABLE BELOW, and the evidence string is copied into the manifest's ``notes``
so a reader can check the claim without reading this file. An artifact whose fit
window cannot be evidenced is reported as BLOCKED and gets no manifest — an
unattested artifact is a known gap, while a guessed manifest is a false attestation,
and the second is much worse. That asymmetry is the whole point of C3.

DERIVING "END OF SEASON s"
--------------------------
``max(game_date)`` for the season, plus one day at 12:00 UTC.

The offset is not padding. ``game_date`` is a DATE, and ``to_utc`` reads a bare date
as midnight UTC — which is BEFORE the games played on it. A 2024-10-20 artifact
stamped 2024-10-20T00:00Z would pass an as-of check against a forecast committed at
2024-10-20T12:00Z, while actually containing the result of a game that tipped that
evening. Next-day noon UTC (08:00 ET) strictly bounds any WNBA game played on the
date, including a late tip that runs to overtime. Conservative in the safe direction:
it can only make the invariant refuse more.

USAGE
-----
    python backfill_manifests.py            # report what would be written
    python backfill_manifests.py --write    # write the sidecars
    python asof_invariant.py --scan         # confirm
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path
from typing import Any, Callable

import pandas as pd

import asof_invariant as aoi

ROOT = Path(__file__).resolve().parent
MASTER_TEAM = ROOT / "data" / "masters" / "master_team.parquet"


# --------------------------------------------------------------------------- #
# season calendar, read once from the master table
# --------------------------------------------------------------------------- #

def load_season_ends() -> dict[int, _dt.datetime]:
    """{season: latest instant by which every game of that season had finished}."""
    df = pd.read_parquet(MASTER_TEAM, columns=["season", "game_date"])
    df["game_date"] = pd.to_datetime(df["game_date"])
    out: dict[int, _dt.datetime] = {}
    for season, sub in df.groupby(df["season"].astype(int)):
        last = sub["game_date"].max().to_pydatetime()
        out[int(season)] = (last + _dt.timedelta(days=1)).replace(
            hour=12, minute=0, second=0, microsecond=0, tzinfo=_dt.timezone.utc)
    return out


SEASON_END: dict[int, _dt.datetime] = {}


def end_of(season: int) -> _dt.datetime:
    if season not in SEASON_END:
        raise KeyError(f"season {season} not present in {MASTER_TEAM.name}")
    return SEASON_END[season]


def end_of_last(seasons: list[int]) -> _dt.datetime:
    return max(end_of(s) for s in seasons)


# --------------------------------------------------------------------------- #
# per-artifact derivations that read the artifact itself
# --------------------------------------------------------------------------- #

def _walkforward_rapm(path: Path) -> dict[str, Any]:
    """rapm_walkforward*.csv carry their own ``fit_through_season`` column.

    The file states, per row, which seasons it was fit through. That is better
    evidence than any constant in the producer, so it is read rather than assumed.
    """
    df = pd.read_csv(path, usecols=["season", "fit_through_season"])
    by_season = {
        int(s): end_of(int(sub["fit_through_season"].max()))
        for s, sub in df.groupby(df["season"].astype(int))
    }
    return {
        "asof_granularity": "season",
        "fit_through_by_season": by_season,
        "fit_through_date": max(by_season.values()),
        "fit_through_season": int(df["fit_through_season"].max()),
        "fit_seasons": sorted({int(x) for x in df["fit_through_season"].unique()}),
        "evidence": (
            "the artifact's own fit_through_season column, per season "
            f"({len(by_season)} emit seasons: "
            + ", ".join(f"{s}<-{v.year}" for s, v in sorted(by_season.items())) + ")"),
    }


def _residual_pool(path: Path) -> dict[str, Any]:
    """residual_pool.csv carries a ``date`` column; the max IS the fit_through."""
    df = pd.read_csv(path, usecols=["date", "season"])
    last = pd.to_datetime(df["date"]).max().to_pydatetime()
    seasons = sorted({int(s) for s in df["season"].unique()})
    return {
        "asof_granularity": "artifact",
        "fit_through_date": (last + _dt.timedelta(days=1)).replace(
            hour=12, minute=0, second=0, microsecond=0, tzinfo=_dt.timezone.utc),
        "fit_through_season": max(seasons),
        "fit_seasons": seasons,
        "evidence": (
            f"max(date) over the pool's own rows = {last.date()}; seasons present "
            f"= {seasons}. dist_margin_cover.py already asserts the pool holds zero "
            "test-era (2024+) rows, so this is a check of that assertion, not a "
            "substitute for it."),
    }


def _crew_factors(path: Path) -> dict[str, Any]:
    """crew_factors.csv is ROW-walk-forward: each game's prior uses only earlier games.

    No season-level bound describes it — priors for a game in the middle of a
    season already include that season's earlier games. Declared granularity "row"
    so ``assert_asof_for_season`` refuses rather than silently approximating.
    """
    df = pd.read_csv(path, usecols=["game_date", "season"])
    last = pd.to_datetime(df["game_date"]).max().to_pydatetime()
    seasons = sorted({int(s) for s in df["season"].unique()})
    return {
        "asof_granularity": "row",
        "fit_through_date": (last + _dt.timedelta(days=1)).replace(
            hour=12, minute=0, second=0, microsecond=0, tzinfo=_dt.timezone.utc),
        "fit_through_season": max(seasons),
        "fit_seasons": seasons,
        "evidence": (
            f"max(game_date) over the artifact's own rows = {last.date()}. Row-wise "
            "walk-forward: w4_refs.py builds each crew prior from games strictly "
            "BEFORE that game's date, so the artifact-level bound is correct but "
            "coarse, and consumers must filter on the row's own game_date. The "
            "shrinkage K is separately tuned on inner folds inside 2021-2023 "
            "(w4_refs.py, 'K is tuned on inner walk-forward folds strictly inside "
            "2021-2023')."),
    }


def _zone_map(path: Path) -> dict[str, Any]:
    """Zone maps look season-partitioned but are NOT season-clean.

    The per-season files carry a ``season`` column, which invites declaring season
    granularity. That would be wrong. Their shrunk columns (fg_pct_shrunk,
    share_shrunk, pps_shrunk) apply K values from shrinkage_priors.csv, which is
    POOLED ACROSS EVERY SEASON IN THE BUILD — so a 2021 row's shrunk value was
    influenced by 2026 games. Declaring season granularity here would attest a
    promise the file does not keep.

    Artifact granularity, bounded by the latest season present. This is the open
    "zone-map K contamination" question (HANDOFF_2026-07-31 §3 item 7, severity
    argued but not measured); the manifest records the dependency rather than
    resolving it.
    """
    df = pd.read_csv(path, usecols=["season"]) if _has_col(path, "season") else None
    if df is not None:
        seasons = sorted({int(s) for s in df["season"].unique()})
    else:
        # shrinkage_priors.csv has no season column precisely because it is pooled.
        seasons = sorted(SEASON_END)
    return {
        "asof_granularity": "artifact",
        "fit_through_date": end_of_last(seasons),
        "fit_through_season": max(seasons),
        "fit_seasons": seasons,
        "evidence": (
            f"seasons present = {seasons}; bounded by the LATEST because the shrunk "
            "columns depend on shrinkage_priors.csv, whose K is pooled across all "
            "seasons in the build. Season granularity is deliberately NOT declared: "
            "a 2021 row's shrunk value saw later seasons. Open item: zone-map K "
            "contamination severity is argued, not measured (HANDOFF_2026-07-31 "
            "section 3 item 7)."),
    }


def _has_col(path: Path, col: str) -> bool:
    return col in pd.read_csv(path, nrows=0).columns


def _static(seasons: list[int], evidence: str,
            granularity: str = "artifact") -> Callable[[Path], dict[str, Any]]:
    """A fit window known from a producer constant, a filename or an in-file field."""
    def derive(_path: Path) -> dict[str, Any]:
        return {
            "asof_granularity": granularity,
            "fit_through_date": end_of_last(seasons),
            "fit_through_season": max(seasons),
            "fit_seasons": sorted(seasons),
            "evidence": evidence,
        }
    return derive


# --------------------------------------------------------------------------- #
# the curated table — every row names its evidence
# --------------------------------------------------------------------------- #

CONTAMINATED_SUMMARY = (
    "CONTAMINATED FOR GENERAL CONSUMPTION. This file mixes fitted parameters "
    "(2021-2023) with TEST-ERA RESULTS (2024-2026) in the same document, so the "
    "artifact-level bound is the latest season it reports on, not the latest season "
    "it was fit on. Consuming only the fitted subkeys is legitimate; consuming the "
    "file is not. Split the file if a consumer needs the parameters at score time."
)

TABLE: list[tuple[str, str, Callable[[Path], dict[str, Any]]]] = [
    # ---- data/rapm ---------------------------------------------------------
    ("data/rapm/rapm_v0.csv", "build_rapm.py",
     _static([2021, 2022, 2023, 2024],
             "build_rapm.py line 74: TRAIN_SEASONS = {'2021','2022','2023','2024'}. "
             "This is the artifact whose misuse motivated asof_invariant_audit_v1 -- "
             "two registered experiments scored 2024 as a TEST season while consuming "
             "it. The manifest now makes that refusable automatically.")),
    ("data/rapm/rapm_walkforward.csv", "build_rapm_walkforward.py", _walkforward_rapm),
    ("data/rapm/rapm_walkforward_seasons.csv", "build_rapm_walkforward.py", _walkforward_rapm),

    # ---- data/zone_maps ----------------------------------------------------
    ("data/zone_maps/shrinkage_priors.csv", "build_zone_maps.py", _zone_map),
    ("data/zone_maps/player_zone_offense.csv", "build_zone_maps.py", _zone_map),
    ("data/zone_maps/team_zone_offense.csv", "build_zone_maps.py", _zone_map),
    ("data/zone_maps/team_zone_defense.csv", "build_zone_maps.py", _zone_map),
    ("data/zone_maps/league_zone_averages.csv", "build_zone_maps.py", _zone_map),

    # ---- evalharness -------------------------------------------------------
    ("evalharness/frozen_baselines.json", "evalharness/baselines.py",
     _static([2021, 2022, 2023, 2024, 2025],
             "the file's own per-row 'sample' fields: the three channel baselines and "
             "the channel market benchmark cite the '308-game 2024-25 walk-forward "
             "test', the two minutes baselines cite 2024 played rows, and the two "
             "circa/all market benchmarks cite '2021-25 odds-covered games'. Latest "
             "evidence is therefore the 2025 season. These are MEASURED REFERENCE "
             "VALUES rather than fitted parameters, but they are frozen numbers "
             "derived from games and a consumer can leak through them just the same.")),

    # ---- experiments -------------------------------------------------------
    ("experiments/channel_reval/predictions_v2.csv", "channel_reval (rebuild_rr)",
     _static([2024, 2025, 2026],
             "the file holds the 673 TEST games (2024-2026) and their realised "
             "margins/totals, not fitted parameters. Its predictions come from "
             "calibrations fit on 2021-2023, but the file itself contains outcomes, "
             "so the artifact-level bound is the last test season. A consumer wanting "
             "the clean object wants the calibration, not this table.")),
    ("experiments/channel_reval/run_summary.json", "channel_reval (rebuild_rr)",
     _static([2024, 2025, 2026],
             "alphas and calibration are fit on 2021-2023 (TRAIN_YEARS), but the same "
             "document carries per_season_table, channel_table and gate_verdict over "
             "the 2024-2026 test. " + CONTAMINATED_SUMMARY)),
    ("experiments/dist_margin_cover/residual_pool.csv", "dist_margin_cover.py", _residual_pool),
    ("experiments/w2_integration/calibration_params.json", "w2_integration.py",
     _static([2024, 2025, 2026],
             "alphas and both calibrations are fit on 2021-2023 (w2_integration.py: "
             "'All fitted parameters (chain alphas, both calibrations) come from "
             "2021-2023'), but the same document carries incumbent_reproduced with "
             "per-season 2024/2025/2026 values (REPRO_BY_SEASON). "
             + CONTAMINATED_SUMMARY)),
    ("experiments/w4_refs/crew_factors.csv", "w4_refs.py", _crew_factors),
    ("experiments/w6_retrospective/zscore_params.json", "w6_retrospective",
     _static([2021, 2022, 2023],
             "the file's own top-level field: train_seasons = [2021, 2022, 2023]. "
             "Contains standardisation parameters only, no test-era values.")),

    # ---- experiments/rapm_multiseason: the filename states the window -------
    ("experiments/rapm_multiseason/rapm_v1_decay_pooled_train2021_24.csv", "build_rapm_v1.py",
     _static([2021, 2022, 2023, 2024], "filename suffix 'train2021_24'.")),
    ("experiments/rapm_multiseason/rapm_v1_prior_anchored_train2021_24.csv", "build_rapm_v1.py",
     _static([2021, 2022, 2023, 2024], "filename suffix 'train2021_24'.")),
    ("experiments/rapm_multiseason/rapm_v1_singleseason_extlambda_train2021_24.csv", "build_rapm_v1.py",
     _static([2021, 2022, 2023, 2024], "filename suffix 'train2021_24'.")),
    ("experiments/rapm_multiseason/rapm_v1_decay_pooled_train2021_26.csv", "build_rapm_v1.py",
     _static([2021, 2022, 2023, 2024, 2025, 2026],
             "filename suffix 'train2021_26'. FIT THROUGH THE CURRENT SEASON: this "
             "artifact can score nothing in 2021-2026 and exists for descriptive use "
             "only. The manifest now makes any attempt to score with it fail closed.")),
    ("experiments/rapm_multiseason/rapm_v1_prior_anchored_train2021_26.csv", "build_rapm_v1.py",
     _static([2021, 2022, 2023, 2024, 2025, 2026],
             "filename suffix 'train2021_26'. FIT THROUGH THE CURRENT SEASON: "
             "descriptive use only, cannot score any season it covers.")),
]


# --------------------------------------------------------------------------- #
# driver
# --------------------------------------------------------------------------- #

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--write", action="store_true",
                    help="write the sidecars (default: report only)")
    ap.add_argument("--force", action="store_true",
                    help="rewrite manifests that already exist")
    args = ap.parse_args(argv)

    global SEASON_END
    SEASON_END = load_season_ends()
    print("season calendar (latest instant by which the season had finished):")
    for s in sorted(SEASON_END):
        print(f"  {s}  {SEASON_END[s].isoformat()}")
    print()

    written, skipped, blocked = 0, 0, []

    for rel, producer, derive in TABLE:
        path = ROOT / rel
        if not path.exists():
            blocked.append((rel, "artifact does not exist"))
            print(f"BLOCKED  {rel}  -- artifact does not exist")
            continue
        if aoi.manifest_path(path).exists() and not args.force:
            print(f"skip     {rel}  -- manifest already present")
            skipped += 1
            continue
        try:
            d = derive(path)
        except Exception as exc:                      # evidence unreadable => refuse
            blocked.append((rel, f"{type(exc).__name__}: {exc}"))
            print(f"BLOCKED  {rel}  -- cannot derive fit window: {exc}")
            continue

        gran = d["asof_granularity"]
        ftd = d["fit_through_date"]
        print(f"{'write   ' if args.write else 'would   '} {rel}")
        print(f"           granularity={gran}  fit_through={ftd.isoformat()}  "
              f"fit_seasons={d['fit_seasons']}")
        if not args.write:
            continue

        aoi.write_manifest(
            path,
            producer=producer,
            fit_through_date=ftd,
            fit_through_season=d["fit_through_season"],
            fit_seasons=d["fit_seasons"],
            asof_granularity=gran,
            fit_through_by_season=d.get("fit_through_by_season"),
            notes=(
                "Backfilled by backfill_manifests.py under screening_protocol_"
                "amendment_v5 C3-BLOCKING; the artifact predates the manifest "
                "convention. EVIDENCE FOR THE FIT WINDOW: " + d["evidence"] + " "
                "fit_through_date is max(game_date) of the last fit season plus one "
                "day at 12:00 UTC, which strictly bounds any WNBA game played on that "
                "date; a bare date would read as midnight UTC and sit BEFORE the games "
                "it is meant to cover."),
            extra={"backfilled": True,
                   "backfill_basis": d["evidence"],
                   "governed_by": "plan_freeze_2026_07_31"},
        )
        written += 1

    print()
    print(f"{written} written, {skipped} already present, {len(blocked)} BLOCKED")
    for rel, why in blocked:
        print(f"  BLOCKED {rel}: {why}")
    if not args.write:
        print("\n(report only -- re-run with --write)")
    return 1 if blocked else 0


if __name__ == "__main__":
    sys.exit(main())
