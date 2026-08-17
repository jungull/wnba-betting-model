"""s00 -- FEASIBILITY PROBE, run BEFORE PREREG.md exists.

It looks ONLY at the candidate side and at row counts.  It never computes any relationship between
a candidate and either response, and it never fits anything.  Its job is to decide, before the
prereg is written and hashed, (a) whether each candidate's ingredients exist at all, and
(b) AT WHAT LEVEL each candidate actually varies -- which fixes its null.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mn_base as A                                                    # noqa: E402

A.hdr("s00 PROBE -- candidate-side only.  No response relationship is computed.")
d, tg, closure = A.build_frame(verbose=True)
d, rep = A.add_candidate_columns(d, verbose=True)

dm = A.decision_mask(d)
season = d["season"].to_numpy()
clean = np.isin(season, A.CLEAN_EVAL_SEASONS)

A.hdr("ROW COUNTS")
for nm, m in [("ALL_APPEARED", np.ones(len(d), bool)),
              ("DECISION", dm),
              ("DECISION_CLEAN_2023_24", dm & clean),
              ("ALL_CLEAN_2023_24", clean),
              ("DECISION_TRAIN_le2022", dm & (season <= 2022)),
              ("DECISION_DISCLOSED_2022", dm & (season == 2022))]:
    print("  %-24s n=%6d  players=%4d  team-games=%5d  dates=%4d"
          % (nm, m.sum(), d.loc[m, "player_id"].nunique(), d.loc[m, "tg"].nunique(),
             d.loc[m, "game_date"].nunique()))

A.hdr("VARIANCE LEVEL OF EVERY CANDIDATE -- this fixes the null, and it is measured, not assumed")
rows = []
tg_code = d["tg_code"].to_numpy()
n_tg = int(tg_code.max()) + 1
cnt = np.bincount(tg_code, minlength=n_tg).astype(float)
for c in A.CANDIDATES:
    x = d[c].to_numpy(float)
    gm = np.bincount(tg_code, weights=x, minlength=n_tg) / cnt
    between = float(np.var(gm[tg_code], ddof=0))
    total = float(np.var(x, ddof=0))
    share_between = between / total if total > 0 else np.nan
    n_const = int(np.sum(np.abs(x - gm[tg_code]) < 1e-12))
    rows.append(dict(candidate=c, sd=float(np.std(x, ddof=1)),
                     var_share_BETWEEN_team_game=share_between,
                     var_share_WITHIN_team_game=1.0 - share_between,
                     frac_rows_equal_to_tg_mean=n_const / len(x),
                     declared=("TG_CONSTANT" if c in A.TG_CONSTANT_CANDIDATES + ["G02_tg_noise"]
                               else "WITHIN_TG")))
    print("  %-20s sd %10.5f  var share BETWEEN tg %.6f  WITHIN tg %.6f   declared %s"
          % (c, rows[-1]["sd"], share_between, 1.0 - share_between, rows[-1]["declared"]))
pd.DataFrame(rows).to_csv(os.path.join(A.OUT, "out", "_s00_candidate_levels.csv"), index=False)

A.hdr("CANDIDATE COVERAGE ON THE DECISION STRATUM, CLEAN WINDOW")
m = dm & clean
for c in A.CANDIDATES:
    x = d.loc[m, c].to_numpy(float)
    print("  %-20s n=%5d  mean %+11.5f  sd %10.5f  min %+10.4f  p50 %+10.4f  max %+10.4f  "
          "n_distinct %5d"
          % (c, len(x), x.mean(), x.std(ddof=1), x.min(), np.median(x), x.max(),
             len(np.unique(np.round(x, 10)))))

A.hdr("NULL BLOCK COUNTS -- reported because below six blocks a two-sided sign-flip cannot reject")
sw1 = A.WithinTeamGameSwap(d)
sw2 = A.WithinDateTeamGameSwap(d)
sw3 = A.PlayerSeriesSwap(d)
print("  N_TGSWAP   groups=%d  blocks=%d" % (sw1.n_groups, sw1.n_blocks))
print("  N_TGBLOCK  groups=%d  blocks=%d  (dates carrying >1 team-game)" % (sw2.n_groups, sw2.n_blocks))
print("  N_PSWAP    groups=%d (player-seasons)  blocks=%d (team-seasons)" % (sw3.n_groups, sw3.n_blocks))
print("  scored team-game blocks, DECISION x clean window = %d"
      % d.loc[dm & clean, "tg"].nunique())

A.hdr("IS THE TEAM-GAME MINUTES BUDGET ACTUALLY FIXED?")
t = d.drop_duplicates("tg")["T_min"].to_numpy(float)
print("  T_min over %d team-games: mean %.4f  sd %.4f  min %.2f  max %.2f  frac==200 %.4f"
      % (len(t), t.mean(), t.std(ddof=1), t.min(), t.max(), float(np.mean(np.abs(t - 200) < 1e-9))))

d.to_parquet(os.path.join(A.SCR, "_frame.parquet"), index=False)
print("\n  frame cached -> _frame.parquet   rows=%d  cols=%d" % d.shape)
