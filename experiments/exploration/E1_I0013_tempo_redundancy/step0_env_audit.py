"""E1 I0013 -- Step 0: independent environment audit.

Three things, none of which is trusted from the E0 screen or the coordinator:
  1. Does a game-TOTALS market archive exist anywhere in this worktree?
  2. Manifest gate (13.2.2) on every artifact this E1 will read -- asof_granularity must be "row".
  3. Partition coverage of the candidate market files, tested on COLUMN VALUES, not a byte scan.

Nothing here reads, joins, plots or describes 2025/2026 VALUES.  Season coverage is reported as a
presence/absence count only, which is the same category of statement as a manifest check.
"""
import json
import os
import sys

import pandas as pd

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
OUT = os.path.join(ROOT, r"experiments\exploration\E1_I0013_tempo_redundancy")
PARTITION = {2021, 2022, 2023, 2024}

rep = {}


def hdr(s):
    print("\n" + "=" * 88)
    print(s)
    print("=" * 88)


# ------------------------------------------------------------------ 1. market archive search
hdr("1. GAME-TOTALS MARKET ARCHIVE -- does one exist in this worktree?")
hits = []
for dp, dn, fn in os.walk(ROOT):
    if ".git" in dp.split(os.sep):
        continue
    for f in fn:
        lf = f.lower()
        if "master_odds" in lf:
            hits.append(os.path.join(dp, f))
print("  filename search for 'master_odds' anywhere under the worktree: %d hit(s)" % len(hits))
for h in hits:
    print("    " + h)
rep["master_odds_hits"] = hits

# every csv/parquet whose name suggests odds/totals/lines/market
cand = []
for dp, dn, fn in os.walk(ROOT):
    if ".git" in dp.split(os.sep):
        continue
    for f in fn:
        lf = f.lower()
        if not (lf.endswith(".csv") or lf.endswith(".parquet")):
            continue
        if any(k in lf for k in ["odds", "total", "line", "market", "book", "prop", "closing"]):
            cand.append(os.path.relpath(os.path.join(dp, f), ROOT))
cand = sorted(set(cand))
print("\n  files whose NAME suggests market data (%d):" % len(cand))
for c in cand:
    print("    " + c)
rep["market_named_files"] = cand


# ------------------------------------------------------------------ 2. manifests
hdr("2. MANIFEST GATE (13.2.2) on artifacts this E1 will read")
man = {}
for rel in [r"data\masters\master_player.parquet", r"data\masters\master_team.parquet"]:
    p = os.path.join(ROOT, rel + ".manifest.json")
    ok = os.path.exists(p)
    if ok:
        with open(p, "r", encoding="utf-8") as f:
            m = json.load(f)
        g = m.get("asof_granularity")
        man[rel] = dict(exists=True, asof_granularity=g,
                        usable=(g == "row"),
                        fit_seasons=m.get("fit_seasons"),
                        content_sha256=m.get("content_sha256"))
        print("  %-40s asof_granularity=%r -> %s" % (os.path.basename(rel), g,
                                                     "USABLE (row-bounded; filtering suffices)"
                                                     if g == "row" else "UNUSABLE"))
    else:
        man[rel] = dict(exists=False)
        print("  %-40s NO MANIFEST -> UNUSABLE" % os.path.basename(rel))
rep["manifests"] = man

# manifest presence for every market-named file we might have wanted
mm = {}
for c in cand:
    p = os.path.join(ROOT, c + ".manifest.json")
    mm[c] = os.path.exists(p)
print("\n  manifest present for market-named files: %d of %d"
      % (sum(mm.values()), len(mm)))
for k, v in mm.items():
    if v:
        print("    HAS MANIFEST: " + k)
rep["market_file_manifest_present"] = mm


# ------------------------------------------------------------------ 3. partition coverage by VALUE
hdr("3. PARTITION COVERAGE OF MARKET-LIKE FILES -- tested on column VALUES")


def season_coverage(relpath, season_cols=("season", "season_h"), date_cols=("game_date", "date",
                                                                            "GAME_DATE_h",
                                                                            "commence_time")):
    p = os.path.join(ROOT, relpath)
    try:
        df = pd.read_csv(p, low_memory=False)
    except Exception as e:  # noqa: BLE001
        return dict(error=str(e))
    info = dict(n_rows=int(len(df)), columns=list(df.columns))
    sc = next((c for c in season_cols if c in df.columns), None)
    if sc:
        s = pd.to_numeric(df[sc], errors="coerce").dropna().astype(int)
        vc = s.value_counts().sort_index()
        info["season_col"] = sc
        info["rows_by_season"] = {int(k): int(v) for k, v in vc.items()}
        info["n_rows_in_partition_2021_2024"] = int(s.isin(PARTITION).sum())
    dc = next((c for c in date_cols if c in df.columns), None)
    if dc:
        d = pd.to_datetime(df[dc], errors="coerce", utc=True).dropna()
        if len(d):
            info["date_col"] = dc
            info["min_date"] = str(d.min().date())
            din = d[(d.dt.year >= 2021) & (d.dt.year <= 2024)]
            info["n_rows_dated_2021_2024"] = int(len(din))
            info["min_date_in_partition"] = str(din.min().date()) if len(din) else None
            info["max_date_in_partition"] = str(din.max().date()) if len(din) else None
    return info


TO_CHECK = [
    r"experiments\totals_groundwork\bookie_totals_per_game.csv",
    r"experiments\totals_groundwork\model_vs_bookie_totals_paired.csv",
    r"experiments\totals_head\game_level_totals.csv",
    r"data\props_capture\historical\master_props_historical.csv",
]
cov = {}
for rel in TO_CHECK:
    if not os.path.exists(os.path.join(ROOT, rel)):
        cov[rel] = dict(exists=False)
        print("\n  %s -> DOES NOT EXIST" % rel)
        continue
    info = season_coverage(rel)
    info["exists"] = True
    cov[rel] = info
    print("\n  %s" % rel)
    print("    n_rows=%s" % info.get("n_rows"))
    print("    columns=%s" % (info.get("columns")[:24],))
    if "rows_by_season" in info:
        print("    rows by season (value test): %s" % info["rows_by_season"])
        print("    rows inside exploration partition 2021-2024: %d"
              % info["n_rows_in_partition_2021_2024"])
    if "min_date_in_partition" in info:
        print("    rows dated 2021-2024: %d  (range %s .. %s)"
              % (info["n_rows_dated_2021_2024"], info["min_date_in_partition"],
                 info["max_date_in_partition"]))
rep["market_file_coverage"] = cov


# the one file that carries a totals-market column INSIDE the partition
hdr("3b. IS THERE ANY NON-NULL MARKET TOTAL INSIDE 2021-2024?")
p = os.path.join(ROOT, r"experiments\totals_head\game_level_totals.csv")
if os.path.exists(p):
    g = pd.read_csv(p, low_memory=False)
    g["season"] = pd.to_numeric(g["season"], errors="coerce")
    gin = g[g["season"].isin(PARTITION)]
    col = "bookie_consensus_total"
    nn = int(pd.to_numeric(gin[col], errors="coerce").notna().sum()) if col in gin.columns else -1
    print("  experiments\\totals_head\\game_level_totals.csv")
    print("    rows inside 2021-2024                : %d" % len(gin))
    print("    NON-NULL %-28s: %d" % (col, nn))
    print("    seasons present in file (value test) : %s"
          % sorted(int(x) for x in g["season"].dropna().unique()))
    rep["game_level_totals_partition"] = dict(
        n_rows_in_partition=int(len(gin)), n_nonnull_bookie_total_in_partition=nn,
        seasons_present=sorted(int(x) for x in g["season"].dropna().unique()))

p2 = os.path.join(ROOT, r"experiments\totals_groundwork\bookie_totals_per_game.csv")
if os.path.exists(p2):
    b = pd.read_csv(p2, low_memory=False)
    b["season"] = pd.to_numeric(b["season"], errors="coerce")
    nin = int(b["season"].isin(PARTITION).sum())
    print("\n  experiments\\totals_groundwork\\bookie_totals_per_game.csv")
    print("    total rows                           : %d" % len(b))
    print("    rows inside 2021-2024                : %d" % nin)
    print("    earliest season present (value test) : %d" % int(b["season"].min()))
    rep["bookie_totals_per_game_partition"] = dict(
        n_rows_total=int(len(b)), n_rows_in_partition=nin,
        earliest_season=int(b["season"].min()))

with open(os.path.join(OUT, "step0_env_audit.json"), "w", encoding="utf-8") as f:
    json.dump(rep, f, indent=1, default=str)
print("\n  wrote step0_env_audit.json")
