#!/usr/bin/env python3
"""
WNBA data refresh & repair — one-shot, resumable collection run.
Fills every gap found in the July 2026 completeness audit:

  Phase A: 2021 postseason gamelogs (player+team) + play-by-play
  Phase B: 2023 misc-stats REPAIR (paint / PFD / fastbreak / 2nd-chance / pts-off-TOV, per game)
  Phase C: 2025 catch-up — everything after 2025-07-03 (regular + postseason)
  Phase D: 2026 season to date (15 teams incl. Toronto Tempo, Portland Fire)
  Phase E: validation report

Run from the repo root (wnba-betting-model/):   python collect_refresh.py
Requires:  pip install nba_api pandas pyarrow
Resumable: every per-game fetch is checkpointed to disk; re-running skips completed work.
Outputs:   data/refresh_2026/   (never overwrites existing data files)
Runtime:   roughly 60-120 min with polite rate limiting. Safe to interrupt and re-run.

NOTE (July 2026): stats.nba.com retired the V2 per-game endpoints (PlayByPlayV2 returns
empty JSON — nba_api issue #591; BoxScoreMiscV2 returns empty datasets). This script uses
the V3 endpoints. V3 schemas are camelCase (pointsPaint, foulsDrawn, ...) and differ from
the V2-schema files in data/playbyplay/ — downstream code needs a V2/V3 normalizer.
"""
import json, time, random, sys
from pathlib import Path

import pandas as pd

try:
    from nba_api.stats.endpoints import leaguegamelog, boxscoremiscv3, playbyplayv3, boxscoreadvancedv3
except ImportError:
    sys.exit("Run first:  pip install nba_api pandas pyarrow")

OUT = Path("data/refresh_2026")
(OUT / "pbp").mkdir(parents=True, exist_ok=True)
(OUT / "misc").mkdir(exist_ok=True)
(OUT / "advanced").mkdir(exist_ok=True)
LEAGUE = "10"  # WNBA
BASE_SLEEP = 1.0

def polite():
    time.sleep(BASE_SLEEP + random.uniform(0, 0.8))

def fetch(fn, tag, retries=5):
    """Call an nba_api endpoint constructor with exponential backoff."""
    delay = 4
    for i in range(retries):
        try:
            r = fn()
            polite()
            return r
        except Exception as e:
            print(f"    retry {i+1}/{retries} for {tag}: {str(e)[:90]}")
            time.sleep(delay); delay = min(delay * 2, 240)
    print(f"    FAILED permanently: {tag}")
    FAILURES.append(tag)
    return None

FAILURES = []

def extract(r, kind, tag):
    """Pull the dataframe out of a V3 response; empty/malformed responses -> None, never a crash."""
    if r is None:
        return None
    try:
        df = r.get_data_frames()[0] if kind == "pbp" else r.player_stats.get_data_frame()
        if df is None or not len(df):
            print(f"    empty response: {tag}")
            FAILURES.append(f"empty {tag}")
            return None
        return df
    except Exception as e:
        print(f"    extract failed for {tag}: {str(e)[:70]}")
        FAILURES.append(f"extract {tag}")
        return None

def save(df, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)

def get_gamelog(season, season_type, who):  # who: 'P' player | 'T' team
    r = fetch(lambda: leaguegamelog.LeagueGameLog(
        league_id=LEAGUE, season=season, season_type_all_star=season_type,
        player_or_team_abbreviation=who, timeout=60), f"gamelog {season} {season_type} {who}")
    return r.get_data_frames()[0] if r else pd.DataFrame()

def per_game(game_ids, kind):
    """kind: 'misc' | 'pbp' | 'advanced'. Checkpointed per game."""
    folder = OUT / ("pbp" if kind == "pbp" else kind)
    todo = [g for g in game_ids if not (folder / f"{kind}_{g}.parquet").exists()]
    print(f"  {kind}: {len(todo)} to fetch ({len(game_ids)-len(todo)} already done)")
    for n, gid in enumerate(todo, 1):
        if kind == "misc":
            tag = f"misc {gid}"
            r = fetch(lambda: boxscoremiscv3.BoxScoreMiscV3(game_id=gid, timeout=60), tag)
        elif kind == "advanced":
            tag = f"adv {gid}"
            r = fetch(lambda: boxscoreadvancedv3.BoxScoreAdvancedV3(game_id=gid, timeout=60), tag)
        else:
            tag = f"pbp {gid}"
            r = fetch(lambda: playbyplayv3.PlayByPlayV3(game_id=gid, timeout=60), tag)
        df = extract(r, kind, tag)
        if df is not None:
            save(df, folder / f"{kind}_{gid}.parquet")
        if n % 25 == 0:
            print(f"    …{n}/{len(todo)}  (cooldown)"); time.sleep(20)

def season_games(season, types=("Regular Season", "Playoffs")):
    """Return dict of {season_type: (player_df, team_df)} and the union of game ids."""
    out, ids = {}, set()
    for st in types:
        p = get_gamelog(season, st, "P"); t = get_gamelog(season, st, "T")
        if len(p): p["season_type"] = st
        if len(t): t["season_type"] = st
        out[st] = (p, t)
        ids |= set(t.GAME_ID.unique()) if len(t) else set()
    return out, sorted(ids)

def main():
    report = {}

    # ---------- Phase A: 2021 postseason ----------
    print("\n== Phase A: 2021 postseason ==")
    logs, ids = season_games("2021", types=("Playoffs",))
    p, t = logs["Playoffs"]
    if len(p): save(p, OUT / "gamelog_player_2021_playoffs.parquet")
    if len(t): save(t, OUT / "gamelog_team_2021_playoffs.parquet")
    per_game(ids, "pbp"); per_game(ids, "misc"); per_game(ids, "advanced")
    report["2021_postseason_games"] = len(ids)

    # ---------- Phase B: 2023 misc repair ----------
    print("\n== Phase B: 2023 misc-stats repair ==")
    _, ids23 = season_games("2023")
    per_game(ids23, "misc")
    report["2023_misc_games"] = len(ids23)

    # ---------- Phase C: 2025 catch-up ----------
    print("\n== Phase C: 2025 full season ==")
    logs, ids25 = season_games("2025")
    for st, (p, t) in logs.items():
        tag = st.lower().replace(" ", "_")
        if len(p): save(p, OUT / f"gamelog_player_2025_{tag}.parquet")
        if len(t): save(t, OUT / f"gamelog_team_2025_{tag}.parquet")
    # existing repo copy covers games through 2025-07-03; fetch per-game data for the rest
    have = {f.stem.split("_")[1] for f in Path("data/playbyplay").glob("pbp_*.parquet")}
    new25 = [g for g in ids25 if g not in have]
    per_game(new25, "pbp"); per_game(ids25, "misc"); per_game(new25, "advanced")
    report["2025_games_total"] = len(ids25); report["2025_games_new"] = len(new25)

    # ---------- Phase D: 2026 season to date ----------
    print("\n== Phase D: 2026 season to date ==")
    logs, ids26 = season_games("2026")
    for st, (p, t) in logs.items():
        tag = st.lower().replace(" ", "_")
        if len(p): save(p, OUT / f"gamelog_player_2026_{tag}.parquet")
        if len(t): save(t, OUT / f"gamelog_team_2026_{tag}.parquet")
    per_game(ids26, "pbp"); per_game(ids26, "misc"); per_game(ids26, "advanced")
    report["2026_games_to_date"] = len(ids26)

    # ---------- Phase E: validation ----------
    print("\n== Phase E: validation ==")
    misc_files = list((OUT / "misc").glob("misc_*.parquet"))
    m23 = [f for f in misc_files if f.stem.startswith("misc_1042300") or f.stem.startswith("misc_1022300")]
    ok = 0
    for f in m23[:50]:
        d = pd.read_parquet(f)
        paint_col = "PTS_PAINT" if "PTS_PAINT" in d.columns else ("pointsPaint" if "pointsPaint" in d.columns else None)
        if paint_col and d[paint_col].fillna(0).sum() > 0:
            ok += 1
    report["2023_misc_files"] = len(m23)
    report["2023_misc_sample_nonzero_paint"] = f"{ok}/{min(len(m23),50)}"
    report["pbp_files_total_new"] = len(list((OUT / "pbp").glob("pbp_*.parquet")))
    report["pbp_schema_new_files"] = "v3 (camelCase; differs from data/playbyplay v2 files)"
    report["permanent_failures"] = FAILURES

    print(json.dumps(report, indent=2))
    (OUT / "collection_report.json").write_text(json.dumps(report, indent=2))
    print("\nDone. Outputs in data/refresh_2026/. "
          "Commit and push:  git checkout -b data-refresh-2026 && git add data/refresh_2026 "
          "&& git commit -m 'Data refresh: 2021 PS, 2023 misc repair, 2025 completion, 2026 to date' "
          "&& git push -u origin data-refresh-2026")

if __name__ == "__main__":
    main()
