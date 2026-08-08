import os, glob
import pandas as pd
import numpy as np

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
OUT = os.path.join(ROOT, "experiments", "exploration", "IDEATION_QUEUE", "_data_feasibility2.txt")
L = []


def say(s):
    L.append(str(s))


mp = pd.read_parquet(os.path.join(ROOT, "data", "masters", "master_player.parquet"))
mp["gd"] = pd.to_datetime(mp["game_date"])

say("#" * 90)
say("### DNP STRUCTURE (the 15.97% of rows with null minutes)")
dnp = mp[mp["minutes"].isna()]
say("dnp rows: %d of %d (%.4f)" % (len(dnp), len(mp), len(dnp) / len(mp)))
say("dnp_reason non-null on dnp rows: %d" % dnp["dnp_reason"].notna().sum())
say("dnp_reason non-null on PLAYED rows: %d" % mp[mp['minutes'].notna()]["dnp_reason"].notna().sum())
vc = dnp["dnp_reason"].fillna("<NULL>").value_counts()
say("dnp_reason value counts (top 40):")
for k, v in vc.head(40).items():
    say("   %-70s %d" % (str(k)[:70], v))
say("distinct dnp_reason values: %d" % dnp["dnp_reason"].nunique())
say("dnp rows by season:\n%s" % dnp.groupby("season").size().to_string())
say("EXPLORATION PARTITION (2021-2024) dnp rows: %d" % len(dnp[dnp.season <= 2024]))

say("#" * 90)
say("### MINUTES-PLAYED DISTRIBUTION (garbage-time / realised-minutes floor feasibility)")
m = mp["minutes"].dropna()
say("n=%d mean=%.3f" % (len(m), m.mean()))
for q in [0.01, 0.05, 0.10, 0.25, 0.5, 0.75, 0.9, 0.99]:
    say("  q%.2f = %.2f" % (q, m.quantile(q)))
for f in [0, 5, 10, 12, 15, 20, 24, 25, 30]:
    say("  rows with minutes >= %2d : %6d (%.4f)" % (f, (m >= f).sum(), (m >= f).mean()))

say("#" * 90)
say("### STARTER FLAG")
say(mp["starter_flag"].value_counts(dropna=False).to_string())
say("starter_flag nulls: %d" % mp["starter_flag"].isna().sum())

say("#" * 90)
say("### POSITION column in master_player")
say(mp["position"].value_counts(dropna=False).head(20).to_string())

say("#" * 90)
say("### CHANNEL COLUMNS coverage (points_paint etc) by season, non-null fraction among PLAYED rows")
played = mp[mp["minutes"].notna()]
chan = ["points_off_turnovers", "points_second_chance", "points_fast_break", "points_paint",
        "fouls_drawn", "blocks_against", "blk_misc", "pf_misc",
        "usage_percentage", "estimated_usage_percentage", "true_shooting_percentage",
        "offensive_rebound_percentage", "defensive_rebound_percentage", "assist_percentage",
        "possessions", "pace", "pie", "offensive_rating", "defensive_rating",
        "estimated_offensive_rating", "estimated_defensive_rating"]
say("col".ljust(36) + "".join(str(s).rjust(9) for s in sorted(played.season.unique())))
for c in chan:
    row = c.ljust(36)
    for s in sorted(played.season.unique()):
        sub = played[played.season == s]
        row += ("%.3f" % sub[c].notna().mean()).rjust(9)
    say(row)

say("#" * 90)
say("### PLAYBYPLAY / OFFICIALS COVERAGE BY SEASON")
gids = set(os.path.basename(p)[4:-8] for p in glob.glob(os.path.join(ROOT, "data", "playbyplay", "pbp_*.parquet")))
oids = set(os.path.basename(p)[10:-8] for p in glob.glob(os.path.join(ROOT, "data", "officials", "officials_*.parquet")))
games = mp[["game_id", "season", "season_type"]].drop_duplicates()
games["has_pbp"] = games.game_id.astype(str).isin(gids)
games["has_off"] = games.game_id.astype(str).isin(oids)
say(games.groupby(["season"]).agg(n=("game_id", "size"), pbp=("has_pbp", "sum"), off=("has_off", "sum")).to_string())
say("total games=%d pbp=%d officials=%d" % (len(games), games.has_pbp.sum(), games.has_off.sum()))

say("#" * 90)
say("### PBP SCHEMA (one file)")
f0 = sorted(glob.glob(os.path.join(ROOT, "data", "playbyplay", "pbp_*.parquet")))[0]
d = pd.read_parquet(f0)
say("file=%s shape=%s" % (os.path.basename(f0), (d.shape,)))
say("columns: %s" % list(d.columns))
say(d.head(4).to_string()[:2500])

say("#" * 90)
say("### SHOTCHART SCHEMA")
f0 = os.path.join(ROOT, "data", "shotcharts", "shots_2023_regular.parquet")
if os.path.exists(f0):
    d = pd.read_parquet(f0)
    say("shots_2023_regular shape=%s" % (d.shape,))
    say("columns: %s" % list(d.columns))
    say("null frac:")
    for c, v in d.isna().mean().sort_values(ascending=False).items():
        if v > 0:
            say("   %-34s %.4f" % (c, v))
    say(d.head(3).to_string()[:2000])
for sf in sorted(glob.glob(os.path.join(ROOT, "data", "shotcharts", "shots_*.parquet"))):
    d = pd.read_parquet(sf, columns=None)
    say("  %-34s rows=%7d cols=%d" % (os.path.basename(sf), len(d), len(d.columns)))

say("#" * 90)
say("### STINTS / LINEUPS SCHEMA")
for p in [os.path.join(ROOT, "data", "derived", "stints.parquet"),
          os.path.join(ROOT, "data", "lineups", "lineups_2023_24.parquet"),
          os.path.join(ROOT, "data", "derived", "starters.csv"),
          os.path.join(ROOT, "data", "possessions", "possessions.parquet")]:
    say("-" * 70)
    say("FILE %s exists=%s" % (p, os.path.exists(p)))
    if not os.path.exists(p):
        continue
    d = pd.read_parquet(p) if p.endswith("parquet") else pd.read_csv(p, low_memory=False)
    say("  shape=%s" % (d.shape,))
    say("  columns: %s" % list(d.columns))
    say(d.head(2).to_string()[:1400])

say("#" * 90)
say("### INJURY HISTORY SCHEMA")
p = os.path.join(ROOT, "data", "injury_history", "injury_history.csv")
d = pd.read_csv(p, low_memory=False)
say("shape=%s" % (d.shape,))
say("columns: %s" % list(d.columns))
for c in d.columns:
    if d[c].dtype == object and d[c].nunique() < 30:
        say("  values %-24s: %s" % (c, sorted(d[c].dropna().astype(str).unique())[:30]))
say(d.head(4).to_string()[:2000])

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(L))
print("WROTE", OUT, len(L))
