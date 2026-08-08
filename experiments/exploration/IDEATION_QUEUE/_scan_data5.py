import os
import pandas as pd
import numpy as np

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
OUT = os.path.join(ROOT, "experiments", "exploration", "IDEATION_QUEUE", "_data_feasibility5.txt")
L = []
def say(s):
    L.append(str(s))

po = pd.read_parquet(os.path.join(ROOT, "data", "possessions", "possessions.parquet"))
po["gid"] = po.game_id.astype(str)
say("possessions season dtype: %s ; values %s" % (po.season.dtype, sorted(po.season.astype(str).unique())))

sc = pd.read_parquet(os.path.join(ROOT, "data", "shotcharts", "shots_2023_regular.parquet"))
sc["gid"] = sc.GAME_ID.astype(str)
allp = set(po.gid)
say("shot rows whose GAME_ID is present in possessions: %d / %d (%.4f)"
    % (sc.gid.isin(allp).sum(), len(sc), sc.gid.isin(allp).mean()))
say("distinct shot games matched: %d / %d" % (sc[sc.gid.isin(allp)].gid.nunique(), sc.gid.nunique()))

# demonstrate an actual time-join on one game
g = sc.gid.iloc[0]
s1 = sc[sc.gid == g].copy()
p1 = po[po.gid == g].copy()
s1["sec_in_period"] = np.where(s1.PERIOD <= 4, 600, 300) - (s1.MINUTES_REMAINING * 60 + s1.SECONDS_REMAINING)
matched = 0
for _, r in s1.iterrows():
    cand = p1[(p1.period == r.PERIOD) & (p1.start_sec <= r.sec_in_period) & (p1.end_sec >= r.sec_in_period)]
    if len(cand) >= 1:
        matched += 1
say("DEMO time-join on game %s: %d shots, %d matched to exactly-one-or-more possession window (%.3f)"
    % (g, len(s1), matched, matched / max(len(s1), 1)))
say("=> on-court DEFENDER FIVE is attachable to each shot via possessions, with NO raw pbp file.")

# holdout coverage of the same join
sc26 = pd.read_parquet(os.path.join(ROOT, "data", "shotcharts", "shots_2026_regular.parquet"))
sc26["gid"] = sc26.GAME_ID.astype(str)
say("2026 shot rows matched to possessions: %.4f (%d games)"
    % (sc26.gid.isin(allp).mean(), sc26[sc26.gid.isin(allp)].gid.nunique()))

say("")
say("### GARBAGE TIME from possessions")
po["margin"] = (po.home_pts_before - po.away_pts_before).abs()
late = po[po.period >= 4]
say("period>=4 possessions: %d ; |margin|>=20 among them: %.4f" % (len(late), (late.margin >= 20).mean()))
say("all possessions |margin|>=20: %.4f ; >=15: %.4f" % ((po.margin >= 20).mean(), (po.margin >= 15).mean()))
say("games with OT (period>=5): %d of %d" % (po[po.period >= 5].gid.nunique(), po.gid.nunique()))
say("end_reason values: %s" % po.end_reason.value_counts().head(15).to_dict())

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(L))
print("WROTE", OUT)
