import os, sys, json
import pandas as pd
import numpy as np

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
OUT = os.path.join(ROOT, "experiments", "exploration", "IDEATION_QUEUE", "_data_feasibility.txt")
L = []


def say(s):
    L.append(str(s))
    print(s)


def describe(path, label, nrows_preview=3):
    say("=" * 90)
    say("ARTIFACT: %s  ->  %s" % (label, path))
    if not os.path.exists(path):
        say("  MISSING")
        return None
    say("  size_bytes: %d" % os.path.getsize(path))
    man = path + ".manifest.json"
    say("  manifest_present: %s" % os.path.exists(man))
    try:
        if path.endswith(".parquet"):
            df = pd.read_parquet(path)
        else:
            df = pd.read_csv(path, low_memory=False)
    except Exception as e:
        say("  READ_FAIL: %s" % e)
        return None
    say("  shape: %s" % (df.shape,))
    say("  columns (%d): %s" % (len(df.columns), list(df.columns)))
    return df


# ---- master player
mp = describe(os.path.join(ROOT, "data", "masters", "master_player.parquet"), "master_player")
if mp is not None:
    for c in ("season", "game_date", "game_id", "player_id", "team_id", "minutes"):
        if c in mp.columns:
            say("  %s: dtype=%s nunique=%s nulls=%d" % (c, mp[c].dtype, mp[c].nunique(), mp[c].isna().sum()))
    if "season" in mp.columns:
        say("  rows by season:\n%s" % mp.groupby("season").size().to_string())
    say("  NULL FRACTION by column (only cols with >0 nulls):")
    nf = mp.isna().mean()
    for c, v in nf[nf > 0].sort_values(ascending=False).items():
        say("    %-40s %.4f" % (c, v))

mt = describe(os.path.join(ROOT, "data", "masters", "master_team.parquet"), "master_team")

bios = describe(os.path.join(ROOT, "data", "reference", "player_bios.csv"), "player_bios")
if bios is not None:
    say("  NULL FRACTION:")
    nf = bios.isna().mean()
    for c, v in nf.sort_values(ascending=False).items():
        say("    %-40s %.4f" % (c, v))
    for c in bios.columns:
        if bios[c].dtype == object and bios[c].nunique() < 40:
            say("  values %s: %s" % (c, sorted(bios[c].dropna().unique().tolist())[:40]))

# ---- directories
for d in ("shotcharts", "playbyplay", "possessions", "injury_history", "lineups", "derived",
          "officials", "ref_assignments", "w1_truth", "zone_maps", "rapm", "news_capture",
          "injury_capture", "props_capture"):
    p = os.path.join(ROOT, "data", d)
    say("=" * 90)
    say("DIR: %s" % p)
    if not os.path.isdir(p):
        say("  MISSING")
        continue
    fs = sorted(os.listdir(p))
    say("  n_entries: %d" % len(fs))
    say("  sample: %s" % fs[:14])
    nman = sum(1 for f in fs if f.endswith(".manifest.json"))
    say("  manifest_files: %d" % nman)

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(L))
print("WROTE", OUT)
