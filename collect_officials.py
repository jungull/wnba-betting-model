#!/usr/bin/env python3
"""
W4 referee crawl — officials per game for every game in the universe, 2021-2026.

BoxScoreSummaryV3 first (V2 has known data gaps for games on/after 2025-04-10),
V2 fallback for older games if V3 misses. One parquet per game:
  data/officials/officials_<gid>.parquet   (OFFICIAL_ID/first/last or V3 equivalents + GAME_ID)
Checkpointed + resumable like collect_refresh.py. ~1,500 calls; run AFTER other
stats-API crawls finish (one crawler per host at a time).
Game universe: repo season gamelogs + data/refresh_2026 gamelogs (no extra calls).
"""
import sys
import time
import random
from pathlib import Path

import pandas as pd

try:
    from nba_api.stats.endpoints import boxscoresummaryv2
except ImportError:
    sys.exit("Run first:  pip install nba_api pandas pyarrow")
try:
    from nba_api.stats.endpoints import boxscoresummaryv3
    HAVE_V3 = True
except ImportError:
    HAVE_V3 = False

OUT = Path("data/officials")
OUT.mkdir(parents=True, exist_ok=True)


def universe():
    ids = set()
    for p in Path("data").glob("wnba_gamelog_20??.parquet"):
        ids |= set(pd.read_parquet(p, columns=["GAME_ID"]).GAME_ID.astype(str))
    for p in Path("data/refresh_2026").glob("gamelog_team_*.parquet"):
        ids |= set(pd.read_parquet(p, columns=["GAME_ID"]).GAME_ID.astype(str))
    return sorted(ids)


def officials_for(gid):
    if HAVE_V3:
        try:
            r = boxscoresummaryv3.BoxScoreSummaryV3(game_id=gid, timeout=60)
            for df in r.get_data_frames():
                cols = {c.lower() for c in df.columns}
                if len(df) and ({"officialid"} & cols or {"official_id"} & cols
                                or ("personid" in cols and "assignment" in " ".join(cols))):
                    return df, "v3"
        except Exception:
            pass
    try:
        r = boxscoresummaryv2.BoxScoreSummaryV2(game_id=gid, timeout=60)
        df = r.officials.get_data_frame()
        if len(df):
            return df, "v2"
    except Exception:
        pass
    return None, None


def main():
    ids = universe()
    todo = [g for g in ids if not (OUT / f"officials_{g}.parquet").exists()]
    print(f"{len(ids)} games in universe; {len(todo)} to fetch (v3 available: {HAVE_V3})")
    fails = []
    for n, gid in enumerate(todo, 1):
        df, src = officials_for(gid)
        if df is not None:
            df = df.copy()
            df["GAME_ID"], df["SOURCE"] = gid, src
            df.to_parquet(OUT / f"officials_{gid}.parquet", index=False)
        else:
            fails.append(gid)
            print(f"  no officials for {gid}")
        time.sleep(1.0 + random.uniform(0, 0.6))
        if n % 25 == 0:
            print(f"  ...{n}/{len(todo)} (cooldown)")
            time.sleep(15)
    print(f"done; permanent misses: {len(fails)}")
    if fails:
        (OUT / "missing_officials.txt").write_text("\n".join(fails))


if __name__ == "__main__":
    main()
