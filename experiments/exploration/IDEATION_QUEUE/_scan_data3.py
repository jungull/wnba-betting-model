import os, glob, json
import pandas as pd
import numpy as np

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
OUT = os.path.join(ROOT, "experiments", "exploration", "IDEATION_QUEUE", "_data_feasibility3.txt")
L = []
def say(s):
    L.append(str(s))

mp = pd.read_parquet(os.path.join(ROOT, "data", "masters", "master_player.parquet"))

say("### CONFIRM: master_player.position is populated ONLY for starters?")
mp["pos_blank"] = mp["position"].astype(str).str.strip() == ""
say(pd.crosstab(mp["starter_flag"], mp["pos_blank"]).to_string())
say("=> position non-blank count: %d ; starter_flag==1 count: %d" % ((~mp.pos_blank).sum(), (mp.starter_flag == 1).sum()))

say("")
say("### POSSESSIONS coverage by season")
po = pd.read_parquet(os.path.join(ROOT, "data", "possessions", "possessions.parquet"),
                     columns=["game_id", "season", "possession_idx"])
g = po.groupby("season").agg(poss=("possession_idx", "size"), games=("game_id", "nunique"))
say(g.to_string())
allg = mp[["game_id", "season"]].drop_duplicates().groupby("season").size()
say("master games by season:\n%s" % allg.to_string())

say("")
say("### INJURY_HISTORY category distribution and date range")
ih = pd.read_csv(os.path.join(ROOT, "data", "injury_history", "injury_history.csv"), low_memory=False)
say(ih["category"].value_counts(dropna=False).to_string())
ih["d"] = pd.to_datetime(ih["date"], errors="coerce")
say("date range: %s .. %s ; nulls %d" % (ih.d.min(), ih.d.max(), ih.d.isna().sum()))
say("rows by year:\n%s" % ih.groupby(ih.d.dt.year).size().to_string())
for cat in ih["category"].dropna().unique():
    sub = ih[ih.category == cat]
    say("  --- %s (n=%d) sample notes:" % (cat, len(sub)))
    for n in sub["notes"].dropna().head(3):
        say("        %s" % str(n)[:150])

say("")
say("### FORECASTS DIRECTORY")
for base in ["forecasts", "leaderboards", "evalharness"]:
    p = os.path.join(ROOT, base)
    if os.path.isdir(p):
        fs = sorted(os.listdir(p))
        say("%s : %d entries : %s" % (base, len(fs), fs[:25]))

say("")
say("### SHOTCHART: does the exploration partition support opponent-on-court linkage?")
sc = pd.read_parquet(os.path.join(ROOT, "data", "shotcharts", "shots_2023_regular.parquet"))
say("GAME_EVENT_ID present: %s ; nunique games %d" % ("GAME_EVENT_ID" in sc.columns, sc.GAME_ID.nunique()))
say("SHOT_ZONE_BASIC values: %s" % sorted(sc.SHOT_ZONE_BASIC.dropna().unique().tolist()))
say("ACTION_TYPE nunique: %d ; top: %s" % (sc.ACTION_TYPE.nunique(), sc.ACTION_TYPE.value_counts().head(12).to_dict()))
say("clock: PERIOD/MINUTES_REMAINING/SECONDS_REMAINING all present -> early/late clock derivable? %s"
    % all(c in sc.columns for c in ["PERIOD", "MINUTES_REMAINING", "SECONDS_REMAINING"]))

say("")
say("### PBP: can we get shot-clock / event sequence? EVENTMSGTYPE distribution on one game")
f0 = sorted(glob.glob(os.path.join(ROOT, "data", "playbyplay", "pbp_*.parquet")))[100]
d = pd.read_parquet(f0)
say("file %s" % os.path.basename(f0))
say(d.EVENTMSGTYPE.value_counts().to_string())

say("")
say("### LINEUPS provenance: retrieval_ts and whether it is season-aggregate (future-reading)")
lu = pd.read_parquet(os.path.join(ROOT, "data", "lineups", "lineups_2021_22.parquet"))
say("shape %s ; GROUP_SET %s ; SEASON_STR %s" % (lu.shape, lu.GROUP_SET.unique()[:3], lu.SEASON_STR.unique()[:3]))
say("retrieval_ts sample: %s" % lu.retrieval_ts.iloc[0])
say("provenance_class: %s" % lu.provenance_class.unique()[:3])
say("vendor_ts_semantics: %s" % lu.vendor_ts_semantics.unique()[:3])

say("")
say("### FREE THROW / FOUL DRAW channel sanity on played rows (exploration partition)")
pl = mp[(mp.minutes.notna()) & (mp.season <= 2024)]
say("n exploration played rows: %d ; players %d" % (len(pl), pl.player_id.nunique()))
for c in ["fta", "ftm", "fouls_drawn", "pts", "fga", "fg3a", "oreb", "dreb", "ast", "tov", "stl", "blk"]:
    say("  %-14s mean=%8.4f sd=%8.4f  share_of_pts=%s" % (c, pl[c].mean(), pl[c].std(), ""))
say("  points identity check: mean pts=%.4f ; 2*(fgm-fg3m)+3*fg3m+ftm mean=%.4f"
    % (pl.pts.mean(), (2 * (pl.fgm - pl.fg3m) + 3 * pl.fg3m + pl.ftm).mean()))
say("  FT points share of total points: %.4f" % (pl.ftm.sum() / pl.pts.sum()))
say("  3PT points share: %.4f" % (3 * pl.fg3m.sum() / pl.pts.sum()))
say("  2PT points share: %.4f" % (2 * (pl.fgm - pl.fg3m).sum() / pl.pts.sum()))

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(L))
print("WROTE", OUT, len(L))
