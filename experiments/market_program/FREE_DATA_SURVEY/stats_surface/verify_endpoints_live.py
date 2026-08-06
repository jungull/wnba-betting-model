"""
verify_endpoints_live.py
Track C (FREE STATS SURFACE EXPANSION) — one-time, manual, read-only
live verification of candidate stats.wnba.com/stats.nba.com endpoint
families named in FUNDAMENTALS_SOURCES.md section 1.2:

    - boxscoresummaryv2 (Officials resultSet)
    - boxscorehustlev2
    - boxscoreadvancedv2
    - shotchartdetail
    - leaguedashlineups

Uses the SAME nba_api wrapper + default production headers already
load-bearing in scripts/01_acquisition/*.py (STATS_HEADERS: Host
stats.nba.com, browser User-Agent/Referer, no API key, no auth).

Etiquette for this run: <=10 total requests, >=2s spacing between
requests, against 2 known-real WNBA 2025 game_ids pulled from
data/wnba_gamelog_2025.parquet (already on disk in this repo):

    game_id=1022500001  teams: ATL(1611661330) vs WAS(1611661322)
    game_id=1022500002  teams: MIN(1611661324) vs DAL(1611661321)

NOT scheduled. NOT resumable-capture. NOT wired into cron/CI.
This script's only job is to answer, per endpoint family: does it
respond for WNBA league_id=10, and is the resultSet of interest
non-empty. Output is a JSON coverage report written next to this
script (endpoint_coverage_report.json) for the human/agent review
step that follows.
"""
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from nba_api.stats.endpoints import (
    boxscoresummaryv2,
    boxscorehustlev2,
    boxscoreadvancedv2,
    shotchartdetail,
    leaguedashlineups,
)

WNBA_LEAGUE_ID = "10"
GAME_ID_1 = "1022500001"
GAME_ID_2 = "1022500002"
TEAM_ID_1 = "1611661330"  # ATL, played in GAME_ID_1
SEASON = "2025"

REQUEST_SPACING_SECONDS = 2.0
OUT_PATH = Path(__file__).parent / "endpoint_coverage_report.json"

RESULTS = {}


def record(name, fn):
    """Run one endpoint call, record row counts per resultSet. Never raise past this point."""
    retrieval_ts = datetime.now(timezone.utc).isoformat()
    entry = {
        "retrieval_ts": retrieval_ts,
        "vendor_ts_semantics": "n/a_metadata_probe",  # this script captures no rows for a table,
        "provenance_class": "live_verification_probe",  # only endpoint-availability metadata
    }
    try:
        resp = fn()
        data = resp.get_json() if hasattr(resp, "get_json") else None
        parsed = json.loads(data) if isinstance(data, str) else data
        result_sets = parsed.get("resultSets") or parsed.get("resultSet") or []
        if isinstance(result_sets, dict):
            result_sets = [result_sets]
        summary = [
            {
                "name": rs.get("name"),
                "row_count": len(rs.get("rowSet", [])),
                "headers": rs.get("headers"),
            }
            for rs in result_sets
        ]
        entry.update({"status": "OK", "result_sets": summary})
    except Exception as e:  # noqa: BLE001 -- diagnostic probe only
        entry.update({"status": "ERROR", "error": f"{type(e).__name__}: {e}"})
    RESULTS[name] = entry
    print(f"[{entry['status']}] {name}")


if __name__ == "__main__":
    print(f"--- Live endpoint verification: {len(RESULTS)} calls planned (max 5) ---")
    print(f"Sample game_ids: {GAME_ID_1}, {GAME_ID_2}")

    record(
        "boxscoresummaryv2.Officials",
        lambda: boxscoresummaryv2.BoxScoreSummaryV2(game_id=GAME_ID_1),
    )
    time.sleep(REQUEST_SPACING_SECONDS)

    record(
        "boxscorehustlev2",
        lambda: boxscorehustlev2.BoxScoreHustleV2(game_id=GAME_ID_1),
    )
    time.sleep(REQUEST_SPACING_SECONDS)

    record(
        "boxscoreadvancedv2",
        lambda: boxscoreadvancedv2.BoxScoreAdvancedV2(game_id=GAME_ID_1),
    )
    time.sleep(REQUEST_SPACING_SECONDS)

    record(
        "shotchartdetail",
        lambda: shotchartdetail.ShotChartDetail(
            team_id=TEAM_ID_1,
            player_id=0,
            game_id_nullable=GAME_ID_1,
            context_measure_simple="FGA",
        ),
    )
    time.sleep(REQUEST_SPACING_SECONDS)

    record(
        "leaguedashlineups",
        lambda: leaguedashlineups.LeagueDashLineups(
            league_id=WNBA_LEAGUE_ID, season=SEASON, season_type_all_star="Regular Season"
        ),
    )
    time.sleep(REQUEST_SPACING_SECONDS)

    # Second game_id spot-check limited to the two endpoints most sensitive to
    # per-game population gaps (Officials, hustle) -- keeps total request count <= 10.
    record(
        "boxscoresummaryv2.Officials_game2",
        lambda: boxscoresummaryv2.BoxScoreSummaryV2(game_id=GAME_ID_2),
    )
    time.sleep(REQUEST_SPACING_SECONDS)

    record(
        "boxscorehustlev2_game2",
        lambda: boxscorehustlev2.BoxScoreHustleV2(game_id=GAME_ID_2),
    )

    OUT_PATH.write_text(json.dumps(RESULTS, indent=2))
    print(f"\nWrote {OUT_PATH}")
    print(f"Total requests made: {len(RESULTS)} (budget: <=10)")
