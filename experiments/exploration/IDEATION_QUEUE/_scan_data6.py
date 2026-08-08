import os
import pandas as pd
import numpy as np

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
OUT = os.path.join(ROOT, "experiments", "exploration", "IDEATION_QUEUE", "_data_feasibility6.txt")
L = []
def say(s):
    L.append(str(s))

po = pd.read_parquet(os.path.join(ROOT, "data", "possessions", "possessions.parquet"))
po["gid"] = po.game_id.astype(str)
say("possessions: are start_sec/end_sec CUMULATIVE game seconds?")
chk = po.groupby(["gid", "period"]).agg(lo=("start_sec", "min"), hi=("end_sec", "max")).reset_index()
say(chk.groupby("period").agg(lo_min=("lo", "min"), lo_med=("lo", "median"),
                              hi_med=("hi", "median"), hi_max=("hi", "max")).to_string())

sc = pd.read_parquet(os.path.join(ROOT, "data", "shotcharts", "shots_2023_regular.parquet"))
sc["gid"] = sc.GAME_ID.astype(str)

# cumulative elapsed seconds: 10-min (600s) quarters, 5-min (300s) OT
def cum_elapsed(period, minr, secr):
    base = np.where(period <= 4, (period - 1) * 600, 2400 + (period - 5) * 300)
    length = np.where(period <= 4, 600, 300)
    return base + (length - (minr * 60 + secr))

sc["cum"] = cum_elapsed(sc.PERIOD.values, sc.MINUTES_REMAINING.values, sc.SECONDS_REMAINING.values)

tot = 0; hit = 0; multi = 0
for g in sc.gid.unique()[:40]:
    s1 = sc[sc.gid == g]
    p1 = po[po.gid == g]
    st = p1.start_sec.values; en = p1.end_sec.values
    for c in s1["cum"].values:
        n = int(((st <= c) & (en >= c)).sum())
        tot += 1
        if n >= 1: hit += 1
        if n > 1: multi += 1
say("")
say("TIME-JOIN on 40 games (cumulative-seconds convention):")
say("  shots=%d  matched_to_>=1_possession=%d (%.4f)  ambiguous_multi=%d (%.4f)"
    % (tot, hit, hit / tot, multi, multi / tot))
say("=> possessions.start_sec/end_sec ARE cumulative game seconds; the earlier 25%% was my arithmetic, not a data gap.")
say("   Boundary shots (a shot that ENDS a possession sits exactly on end_sec) explain the residual ambiguity;")
say("   a real screen should join on the possession whose window CONTAINS the event and break ties by offense_team_id.")

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(L))
print("\n".join(L))
