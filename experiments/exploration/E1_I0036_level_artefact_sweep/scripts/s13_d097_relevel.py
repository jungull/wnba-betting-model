"""S13 -- the OTHER half of the D097 answer (PREREG 6.6): was the LEVEL the problem?

D111 gives rebounds only a 15.7% bottom-up penalty, and an offensive rebound is an ALLOCATION
OF A SHARED BUDGET -- exactly one player collects each one -- which D111's rule says does NOT
survive aggregation from below.  So even if the null was wrong, re-levelling may not be the
fix.  This measures that directly: level R08 UP to the roster and test it against team
offensive rebounds, under the same two level-matched bases used in s12.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab import (BaseFit, EXP, FLOOR_1CELL, OUT, R_DRAWS, SEED, hdr, injection_power,
                 mde80, null_draws, perm_p, resolve, var_share_between)

HEADLINE_SEASONS = (2022, 2023, 2024)
key = ["season", "game_id", "team_id"]

T = pd.read_parquet(os.path.join(OUT, "_team_game_frame_v2.parquet"))
print("team frame", T.shape, "seasons", sorted(pd.unique(T["season"]).tolist()))
assert set(pd.unique(T["season"])) <= {2021, 2022, 2023, 2024}, "A_PARTITION FAILED"

# opponent's prior ALLOWED offensive rebounds per game
oth = T[["season", "game_id", "team_id", "T_oreb"]].rename(
    columns={"team_id": "opp_team_id", "T_oreb": "a_oreb"})
T = T.merge(oth, on=["season", "game_id", "opp_team_id"], how="left")
assert float(T["a_oreb"].notna().mean()) == 1.0, "A_TEAM_JOIN FAILED"
T = T.sort_values(["season", "team_id", "game_date", "game_id"],
                  kind="stable").reset_index(drop=True)
T["_opp_allowed_oreb"] = T.groupby(["season", "team_id"], sort=False)["a_oreb"].transform(
    lambda s: s.shift(1).expanding().mean())
T = T.merge(T[key + ["_opp_allowed_oreb"]].rename(
    columns={"team_id": "opp_team_id", "_opp_allowed_oreb": "M08_opp_allowed_oreb_pg"}),
    on=["season", "game_id", "opp_team_id"], how="left")
print("M08 coverage", float(T["M08_opp_allowed_oreb_pg"].notna().mean()))

# roster attempt-history restricted-area share, levelled UP from D097's own player frame
F97 = pd.read_parquet(os.path.join(EXP, "E0_I0024_reb_ast_characterisation",
                                   "screen_frame.parquet"))
F97 = F97[F97["season"].isin(HEADLINE_SEASONS)].copy()
F97["game_id"] = F97["game_id"].astype(str)
T["game_id"] = T["game_id"].astype(str)
rs = F97.dropna(subset=["R08_player_ra_share"]).groupby(key, as_index=False).agg(
    ROSTER_RA_SHARE=("R08_player_ra_share", "mean"),
    n_with_r08=("R08_player_ra_share", "size"))
T = T.merge(rs, on=key, how="left")
print(f"  D087 coverage assertion: roster RA share present on "
      f"{int(T['ROSTER_RA_SHARE'].notna().sum())}/{len(T)} team-games")

rows = []
for basename, cols, nexp in [
    ("B_TEAM_COMPLETE", ["REFm_T_oreb", "REFe_T_oreb", "REFt_T_oreb", "REF_pace", "REF_fga",
                         "team_n_prior", "is_home"], 7),
    ("B_TEAM_PLUS_OPP", ["REFm_T_oreb", "REFe_T_oreb", "REFt_T_oreb", "REF_pace", "REF_fga",
                         "team_n_prior", "is_home", "M08_opp_allowed_oreb_pg"], 8)]:
    hdr(f"C1_LEVELUP / {basename}:  ROSTER_RA_SHARE -> T_oreb  (TEAM-GAME LEVEL)")
    BASE = resolve(T, cols, nexp, f"{basename}(T_oreb)")
    d = T.dropna(subset=["T_oreb", "ROSTER_RA_SHARE"] + BASE).reset_index(drop=True)
    for c in BASE:
        assert int(d[c].notna().sum()) == len(d), f"A_REF_COVERAGE FAILED {c}"
    print(f"  n = {len(d)}  A_REF_COVERAGE ok on {len(BASE)} columns")
    y = d["T_oreb"].to_numpy(float)
    X = d[BASE].to_numpy(float)
    x = d["ROSTER_RA_SHARE"].to_numpy(float)
    bf = BaseFit(y, X)
    obs = bf.dr2(x)
    ex = bf.resid_x(x)
    ceil = (bf.beta(x) * float(np.std(ex, ddof=1)) / float(np.std(y, ddof=1))) ** 2
    print(f"  r2_base={bf.r2_base:.6f}  dR2={obs:.6e}  CEILING={ceil:.6e} "
          f"({ceil / FLOOR_1CELL:.2f}x single-cell floor)")
    ent = pd.Series(d["team_id"].astype(str) + "_" + d["season"].astype(str)).to_numpy()
    rr = np.random.default_rng(SEED + abs(hash("C1" + basename)) % 100000)
    Xp = null_draws("N_SWAP", x, rr, groups=ent, order_key=d["game_date"].to_numpy(),
                    blocks=d["season"].to_numpy(), R=R_DRAWS)
    EX = bf.resid_X(Xp)
    den = np.einsum("ij,ij->j", EX, EX)
    draws = ((bf.e @ EX) ** 2 / den) / bf.sst
    p = perm_p(obs, draws)
    pw = injection_power(bf, x, EX, np.random.default_rng(SEED + 31),
                         deltas=[0.0, 0.002057, 0.004, 0.010, 0.020], nrep=60)
    m = mde80(pw)
    t1 = float(pw.loc[pw["delta"] == 0.0, "power"].iloc[0])
    pbig = float(pw.loc[pw["delta"] == 0.020, "power"].iloc[0])
    print(f"  N_TSWAP p={p:.6f}  null_mean={draws.mean():.4e}  "
          f"null_sd={draws.std(ddof=1):.4e}")
    print(f"  MDE80={m:.4e}  power@0.020={pbig:.2f}  typeI={t1:.2f}   "
          f"dR2 {'ABOVE' if obs > m else 'BELOW'} MDE80")
    rows.append(dict(cell="C1_LEVELUP", base=basename, candidate="ROSTER_RA_SHARE",
                     response="T_oreb", level="team_game", n=len(d), r2_base=bf.r2_base,
                     dr2=obs, ceiling=ceil, null="N_TSWAP", p_percell=p,
                     null_mean=float(draws.mean()), null_sd=float(draws.std(ddof=1)),
                     R=R_DRAWS, mde80=m, typeI=t1, power_at_0p020=pbig,
                     above_own_mde=bool(obs > m),
                     var_share_between_team=var_share_between(x, ent)))
    np.savez_compressed(os.path.join(OUT, "nulls", f"relevel_C1_{basename}.npz"),
                        draws=draws, observed=np.array([obs]))

R = pd.DataFrame(rows)
hdr("D097 RE-LEVELLING RESULT")
print(R.to_string(index=False))
R.to_csv(os.path.join(OUT, "D097_RELEVEL_CELLS.csv"), index=False)
print("\nwrote D097_RELEVEL_CELLS.csv")
