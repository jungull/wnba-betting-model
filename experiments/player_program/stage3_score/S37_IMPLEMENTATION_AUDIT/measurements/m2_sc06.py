import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import numpy as np, pandas as pd
W = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
N = W + r"\experiments\player_program\stage3_score\S36_IMPLEMENT_ARMS"
sys.path.insert(0, N + r"\runner"); sys.path.insert(0, N + r"\arms")
import runner_constants as K, universe as U
import sc06_sched_fatigue_diff as SC06

tc = pd.read_csv(K.artifact_path("data/reference/team_cities.csv"))
print("team_cities.csv rows:", len(tc), "cols:", list(tc.columns))
print("distinct IANA zones present:", sorted(tc['timezone'].unique()))
print("SC06 STANDARD_OFFSETS keys (%d):" % len(SC06.STANDARD_OFFSETS), sorted(SC06.STANDARD_OFFSETS))
print("keys NOT present in team_cities:", sorted(set(SC06.STANDARD_OFFSETS) - set(tc['timezone'])))

u = U.build_universe()
tz = SC06._team_timezone_offsets()
tr = u.team_rows.sort_values(["team_id","game_date","game_id"], kind="mergesort").copy()
d = pd.to_datetime(tr["game_date"]); tr["_d"]=d
# implementation (career clock)
prev1_i = tr.groupby("team_id", sort=False)["_d"].shift(1)
prev2_i = tr.groupby("team_id", sort=False)["_d"].shift(2)
venue = np.where(tr["is_home"].to_numpy()==1, tr["team_id"].to_numpy(), tr["opp_team_id"].to_numpy())
tr["_venue_tz"] = [tz[int(v)] for v in venue]
prev_tz_i = tr.groupby("team_id", sort=False)["_venue_tz"].shift(1)
# card reading (same-season clock)
prev1_c = tr.groupby(["team_id","season"], sort=False)["_d"].shift(1)
prev2_c = tr.groupby(["team_id","season"], sort=False)["_d"].shift(2)
prev_tz_c = tr.groupby(["team_id","season"], sort=False)["_venue_tz"].shift(1)

def F_of(prev1, prev2, prevtz):
    b2b = ((tr["_d"]-prev1).dt.days == 1).astype(float).to_numpy()
    t34 = ((tr["_d"]-prev2).dt.days <= 3).astype(float).to_numpy()
    tzc = np.minimum((tr["_venue_tz"]-prevtz).abs().fillna(0.0).to_numpy(float), SC06.TZ_CAP)
    F = SC06.W_B2B*b2b + SC06.W_3IN4*t34 + SC06.W_TZ*tzc
    return np.where(prev1.isna().to_numpy(), 0.0, F)

F_impl = F_of(prev1_i, prev2_i, prev_tz_i)
F_card = F_of(prev1_c, prev2_c, prev_tz_c)
diff = ~np.isclose(F_impl, F_card)
print()
print("=== SC06 F: implementation (career clock) vs card reading (same-season clock) ===")
print("team-game rows where F differs:", int(diff.sum()), "of", len(tr))
sub = tr[diff].copy(); sub["F_impl"]=F_impl[diff]; sub["F_card"]=F_card[diff]
print("by season:", sub.groupby("season").size().to_dict())
print("all are season-first-games?", bool(prev1_c[diff].isna().all()))
print("sample:"); print(sub[["game_id","team_id","season","game_date","F_impl","F_card"]].head(12).to_string())
print("distinct F_impl values on differing rows:", sorted(set(np.round(F_impl[diff],4))))

# effect on the game-level differenced feature and on the |F_H-F_A|>=1 subset
from universe import attach_side
fi_impl = pd.DataFrame({"game_id":tr["game_id"].to_numpy(),"team_id":tr["team_id"].to_numpy(),"F":F_impl})
fi_card = pd.DataFrame({"game_id":tr["game_id"].to_numpy(),"team_id":tr["team_id"].to_numpy(),"F":F_card})
gi = attach_side(u.games, fi_impl, "F","H","A", fill=0.0); di = (gi["H"]-gi["A"]).to_numpy(float)
gc = attach_side(u.games, fi_card, "F","H","A", fill=0.0); dc = (gc["H"]-gc["A"]).to_numpy(float)
print()
print("game clusters where fatigue_diff differs:", int((~np.isclose(di,dc)).sum()))
print("|F_H-F_A|>=1 subset  impl:", int((np.abs(di)>=1).sum()), " card-reading:", int((np.abs(dc)>=1).sum()))
seas = u.games["season"].to_numpy()
for s in (2022,2023,2024,2025,2026):
    m = seas==s
    print("   %d  impl=%d  card=%d" % (s, int((np.abs(di[m])>=1).sum()), int((np.abs(dc[m])>=1).sum())))
