"""S00 -- schema / join-key inspection ONLY.  Writes nothing but a log.

Establishes that decomp_frame (D081's frozen champion-forecast frame) joins to the raw
per-shot files on (season, GAME_ID, PLAYER_ID), and that the opponent team can be resolved
from the two team ids present in a game (a SCHEDULE fact, known pre-game, not a realised
player quantity).
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import etv2_base as E  # noqa: E402
import screenkit as sk  # noqa: E402

pd.set_option("display.width", 240)

E.hdr("S00 -- decomp_frame keys")
f = pd.read_parquet(E.DECOMP_FRAME)
print("  shape=%s  seasons=%s" % (f.shape, sorted(f["season"].unique())))
print("  game_id dtype=%s  sample=%s" % (f["game_id"].dtype, f["game_id"].head(3).tolist()))
print("  player_id dtype=%s  team_id dtype=%s" % (f["player_id"].dtype, f["team_id"].dtype))
print("  gdate range %s .. %s" % (f["gdate"].min().date(), f["gdate"].max().date()))
sk.assert_partition(f, verbose=True)

E.hdr("S00 -- raw shots keys")
shots = E.load_shots(seasons=E.CHAMP_SEASONS, verbose=True)
print("  GAME_ID dtype=%s  sample=%s" % (shots["GAME_ID"].dtype, shots["GAME_ID"].head(3).tolist()))
print("  PLAYER_ID dtype=%s  TEAM_ID dtype=%s" % (shots["PLAYER_ID"].dtype, shots["TEAM_ID"].dtype))
print("  zones present: %s" % sorted(shots["zone"].unique()))
print("  columns: %s" % list(shots.columns))

E.hdr("S00 -- key overlap")
fg = set(f["game_id"].astype(str))
sg = set(shots["GAME_ID"].astype(str))
print("  decomp games=%d  shot games=%d  intersection=%d" % (len(fg), len(sg), len(fg & sg)))
fp = set(zip(f["game_id"].astype(str), f["player_id"].astype(int)))
sp = set(zip(shots["GAME_ID"].astype(str), shots["PLAYER_ID"].astype(int)))
print("  decomp (game,player)=%d  shot (game,player)=%d  intersection=%d"
      % (len(fp), len(sp), len(fp & sp)))
print("  decomp rows with NO shot record (fga==0 rows expected): %d"
      % len(fp - sp))
print("  fga==0 rows in decomp: %d" % int((f["y_fga"] == 0).sum()))

E.hdr("S00 -- opponent resolution from schedule (two team ids per game)")
gt = shots.groupby("GAME_ID")["TEAM_ID"].nunique()
print("  games with exactly 2 teams: %d / %d" % (int((gt == 2).sum()), len(gt)))
oppmap = E.opponent_map(shots)
f["_g"] = f["game_id"].astype(str)
f["opp_team_id"] = [oppmap.get((g, t), np.nan) for g, t in zip(f["_g"], f["team_id"])]
print("  decomp rows with resolved opponent: %d / %d"
      % (int(f["opp_team_id"].notna().sum()), len(f)))

E.hdr("S00 -- stratum sizes")
m = (f["pl_games_prior"] >= 8) & (f["pl_min_mean5"] >= 24)
print("  decision-relevant stratum n=%d (%.1f%% of %d)" % (int(m.sum()), 100 * m.mean(), len(f)))
print("DONE s00")
