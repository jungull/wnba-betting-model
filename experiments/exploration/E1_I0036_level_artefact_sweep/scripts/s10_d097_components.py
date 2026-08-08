"""S10 -- D097 debt, part 2.  DISCLOSED POST-HOC EXTENSION of the preregistered protocol.

WHY THIS EXISTS (declared honestly): s09 ran the injection exactly as PREREG 5.3 specified and
N_CYCLIC PASSED it (power 0.95 at 0.002057).  But under the REAL response N_CYCLIC's null mean
(7.90e-03) sits ABOVE the observed statistic (6.49e-03) -- a distribution that contains the
effect, not one that excludes it.  The preregistered injection cannot catch that, because
shuffling the base residuals destroys exactly the BETWEEN-PLAYER response structure that
N_CYCLIC fails to destroy in the carrier.

So this step asks the sharper question the preregistered one could not:
  can each null detect a signal planted along the component of the carrier where the REAL
  effect actually lives (98.19% between-player)?

This is an ADDED test, not a preregistered one, and it is reported as such.  It also runs the
DECISION stratum (>=8 prior appearances) under the matched null, which PREREG 6.5 requires for
the verdict.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab import (BaseFit, DELTAS, EXP, FLOOR_1CELL, FLOOR_132, OUT, R_DRAWS, SEED,
                 assert_partition, hdr, injection_power, mde80, null_draws, perm_p, resolve,
                 var_share_between)

HEADLINE_SEASONS = (2022, 2023, 2024)
TARGET, CAND = "y_oreb", "R08_player_ra_share"

F = pd.read_parquet(os.path.join(EXP, "E0_I0024_reb_ast_characterisation",
                                 "screen_frame.parquet"))
F["game_date"] = pd.to_datetime(F["game_date"])
assert_partition(F, "screen_frame")
F = F[F["season"].isin(HEADLINE_SEASONS)].reset_index(drop=True)
BASE = resolve(F, ["ref_mean__y_oreb", "ref_ewma__y_oreb", "ref_trail5__y_oreb",
                   "ref_rate_x_min__y_oreb", "ref_mean_minutes", "ref_trail5_minutes",
                   "ref_pct__y_oreb", "ref_mean_pace", "n_prior", "is_home"],
               10, "B_COMPLETE(y_oreb)")

rows_out = []
inj_out = []

for STRAT in ["POOLED", "DECISION"]:
    hdr(f"STRATUM {STRAT}")
    d = F.dropna(subset=[TARGET, CAND] + BASE)
    if STRAT == "DECISION":
        d = d[d["DECISION"] == 1]
    d = d.reset_index(drop=True)
    for c in BASE:
        assert int(d[c].notna().sum()) == len(d), f"A_REF_COVERAGE FAILED {c}"
    print(f"  n = {len(d)}   A_REF_COVERAGE ok on {len(BASE)} base columns")

    y = d[TARGET].to_numpy(float)
    X = d[BASE].to_numpy(float)
    x = d[CAND].to_numpy(float)
    bf = BaseFit(y, X)
    obs = bf.dr2(x)
    pl = d["player_id"].to_numpy()
    plseas = pd.Series(d["player_id"].astype(str) + "_" + d["season"].astype(str)).to_numpy()
    seas = d["season"].to_numpy()
    gdate = d["game_date"].to_numpy()

    xb = pd.Series(x).groupby(pd.Series(plseas)).transform("mean").to_numpy()
    xw = x - xb
    print(f"  observed dR2 = {obs:.6e}")
    print(f"  var share between player-season = {var_share_between(x, plseas):.4f}")
    print(f"  dR2 between-only = {bf.dr2(xb):.6e}   within-only = {bf.dr2(xw):.6e}")

    # ceiling first (PREREG 5.5)
    ex = bf.resid_x(x)
    ceil = (bf.beta(x) * float(np.std(ex, ddof=1)) / float(np.std(y, ddof=1))) ** 2
    print(f"  CEILING = {ceil:.6e}  ({ceil / FLOOR_1CELL:.2f}x single-cell floor, "
          f"{ceil / FLOOR_132:.2f}x 132-cell floor)")

    NULLS = {"N_ROW": ("N_ROW", None, None),
             "N_CYCLIC": ("N_CYCLIC", plseas, None),
             "N_PSWAP": ("N_SWAP", plseas, seas)}
    for name, (kind, grp, blk) in NULLS.items():
        rr = np.random.default_rng(SEED + abs(hash(name + STRAT)) % 100000)
        Xp = null_draws(kind, x, rr, groups=grp, order_key=gdate, blocks=blk, R=R_DRAWS)
        EX = bf.resid_X(Xp)
        den = np.einsum("ij,ij->j", EX, EX)
        draws = ((bf.e @ EX) ** 2 / den) / bf.sst
        p = perm_p(obs, draws)

        # --- ADDED: component-targeted injection ---
        comp = {}
        for cname, cvec in [("FULL", x), ("BETWEEN", xb), ("WITHIN", xw)]:
            pw = injection_power(bf, cvec, EX, np.random.default_rng(SEED + 11),
                                 deltas=[0.0, 0.000500, 0.001127, 0.002057], nrep=60)
            comp[cname] = pw
            for _, r in pw.iterrows():
                inj_out.append(dict(stratum=STRAT, null=name, planted_along=cname,
                                    delta=r["delta"], power=r["power"],
                                    achieved=r["achieved_dr2_med"], nrep=r["nrep"]))
        pb = float(comp["BETWEEN"].loc[comp["BETWEEN"]["delta"] == 0.002057, "power"].iloc[0])
        pf = float(comp["FULL"].loc[comp["FULL"]["delta"] == 0.002057, "power"].iloc[0])
        pwn = float(comp["WITHIN"].loc[comp["WITHIN"]["delta"] == 0.002057, "power"].iloc[0])
        t1 = float(comp["FULL"].loc[comp["FULL"]["delta"] == 0.0, "power"].iloc[0])

        blind = "BLIND_TO_BETWEEN" if pb < 0.80 else ""
        blindw = "BLIND_TO_WITHIN" if pwn < 0.80 else ""
        contains = "NULL_MEAN_ABOVE_OBSERVED" if draws.mean() > obs else ""
        print(f"\n  {name:9s} p={p:.6f}  null_mean={draws.mean():.4e} "
              f"null_sd={draws.std(ddof=1):.4e}")
        print(f"    injection power @0.002057:  FULL={pf:.2f}  BETWEEN={pb:.2f}  "
              f"WITHIN={pwn:.2f}   typeI={t1:.2f}")
        print(f"    flags: {' '.join(z for z in [blind, blindw, contains] if z) or 'none'}")
        rows_out.append(dict(
            stratum=STRAT, n=len(d), null=name, obs_dr2=obs, p=p,
            null_mean=float(draws.mean()), null_sd=float(draws.std(ddof=1)), R=R_DRAWS,
            ceiling=ceil,
            pow_full_at_best=pf, pow_between_at_best=pb, pow_within_at_best=pwn,
            typeI=t1, flag_blind_between=(pb < 0.80), flag_blind_within=(pwn < 0.80),
            flag_null_mean_above_obs=bool(draws.mean() > obs)))

R = pd.DataFrame(rows_out)
I = pd.DataFrame(inj_out)
hdr("SUMMARY -- WHICH NULL CAN SEE WHICH COMPONENT")
print(R.to_string(index=False))
R.to_csv(os.path.join(OUT, "D097_COMPONENT_NULLS.csv"), index=False)
I.to_csv(os.path.join(OUT, "D097_COMPONENT_INJECTION.csv"), index=False)
print("\nwrote D097_COMPONENT_NULLS.csv, D097_COMPONENT_INJECTION.csv")
