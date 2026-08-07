import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import numpy as np
W = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
N = W + r"\experiments\player_program\stage3_score\S36_IMPLEMENT_ARMS"
sys.path.insert(0, N + r"\runner"); sys.path.insert(0, N + r"\arms")
import universe as U, sc12_robust_input_winsor as SC12
u = U.build_universe(); seas = u.games["season"].to_numpy()
for floor in (False, True):
    d = np.abs(SC12.winsor_terms(u, apply_support_floor=floor)["winsor_correction_diff"])
    per = {int(s): int((d[seas==s]>=2.0).sum()) for s in sorted(set(seas))}
    print("support_floor_applied=%-5s pooled_high_bite=%d  per_season=%s  median=%.6f p90=%.6f max=%.6f" %
          (floor, int((d>=2.0).sum()), per, float(np.median(d)), float(np.quantile(d,0.9)), float(d.max())))
print("carded: 652 pooled, 97/118/102/141/107 test seasons, 87 in 2021, median 1.704 p90 4.7058 max 13.0")
