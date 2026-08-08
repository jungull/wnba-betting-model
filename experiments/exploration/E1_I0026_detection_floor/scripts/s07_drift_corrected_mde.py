"""s07_drift_corrected_mde.py -- STAGE 4.  THE HEADLINE NUMBERS, AFTER THE PREREGISTERED
FALSIFICATION CHECK FAILED.

WHAT FAILED AND WHY IT MATTERS.
  PREREGISTRATION s6 committed to abandoning the "compute the null once, reuse it across
  delta" factorisation if the null's width drifted by more than 10% on a planted response.
  s05 measured drifts of -76% (within-player cyclic) to +506% (within-date opponent swap).
  The check therefore FAILED, and this file does what the preregistration said to do: it
  recomputes the null ON THE PLANTED RESPONSE and re-derives every headline MDE from it.

  The drift is not noise and it is not symmetric:
    * within-date opponent swap -- the null WIDENS when an effect is planted, so the s04
      numbers were ANTICONSERVATIVE (too small a floor).
    * within-player cyclic shift -- the null NARROWS, so the s04 numbers were CONSERVATIVE.
  Reporting only s04 would have flattered one null and punished another.

THE CORRECTED DERIVATION.
  The observed statistic is exact:   dR2(delta) = (u + sqrt(delta))^2,  u ~ N(0, sqrt(mu0)),
  with mu0 the delta=0 null mean (this is algebra, not an approximation -- see s06).
  The threshold is whatever a real analyst would compute FROM THE DATA IN HAND, i.e. the
  permutation null run on y(delta):   T(delta) = mu(delta) + t_crit * sd(delta).
  So
        power(delta) = Phi( (sqrt(delta) - sqrt(T(delta))) / sqrt(mu0) )
        MDE80 solves   sqrt(delta) = sqrt(T(delta)) + 0.8416 * sqrt(mu0).

  mu(delta) and sd(delta) are MEASURED here on a small delta grid with the kit, then
  log-log interpolated, and the fixed point is solved on a dense grid.  Nothing is assumed
  about the direction or the size of the drift.
"""
import json
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from df_base import (BASES, CARRIER_OPP, CARRIER_PLAYER, OUT, SEED, BaseFit, hdr, load_frame, sk)
from s04_power import FAMILY_SIZES, cell_arrays, familywise_thresholds, kit_pass
from s06_retrospective import Z80

PROBE_DELTAS = [3e-4, 1e-3, 3e-3, 1e-2]
PROBE_REPS = 6
PROBE_DRAWS = 300
SEED_POWER = SEED + 101

CELLS = []
for sname in ("DECISION", "POOLED"):
    for bname in ("B_SINGLE", "B_COMPLETE"):
        CELLS += [
            (sname, bname, "N_A_within_player_cyclic", CARRIER_PLAYER, "perm_cyclic",
             ["player_id", "season"], None),
            (sname, bname, "N_B_entity_swap_team_season", CARRIER_PLAYER, "entity_swap",
             ["team_id", "season"], None),
            (sname, bname, "N_C_entity_swap_opp_team_season", CARRIER_OPP, "entity_swap",
             ["opp_team_id", "season"], None),
            (sname, bname, "N_D_within_date_opp_swap", CARRIER_OPP, "perm_between",
             ["opp_team_id", "game_id"], "game_date"),
        ]

K_REPORT = [1, 18, 39, 44, 132, 154, 250, 318, 348]


def perm_vectors(bf, sub, carrier, kind, level, block, n, seed):
    """n permuted carriers, kept as residualised VECTORS so an effect can be planted along one."""
    vecs = []

    def cap(dfr, _bf=bf, _v=vecs):
        x = pd.to_numeric(dfr["feat"], errors="coerce").to_numpy(float)
        xt = _bf.resid_x(x)
        _v.append(xt)
        b = float(xt @ xt)
        a = float(_bf.e @ xt)
        return (a * a / b) / _bf.sst if b > 1e-12 else 0.0

    d = sub[["season", "player_id", "team_id", "opp_team_id", "game_id", "game_date"]].copy()
    d["feat"] = sub[carrier].to_numpy(float)
    if kind == "entity_swap":
        sk.entity_swap_null(cap, d, level, n, seed, feature_col="feat", date_col="game_date",
                            season_col="season", tiebreak_col="game_id")
    elif kind == "perm_cyclic":
        sk.permutation_null(cap, d, level, n, seed, feature_col="feat",
                            scheme=sk.SCHEME_WITHIN_CYCLIC, order_col="game_date")
    else:
        sk.permutation_null(cap, d, level, n, seed, feature_col="feat",
                            scheme=sk.SCHEME_BETWEEN, block_col=block)
    return vecs[:n]


def solve_mde(mu0, dgrid, mus, sds, t_crit, dmax=3e-2):
    """Fixed point of sqrt(delta) = sqrt(mu(delta) + t_crit*sd(delta)) + z80*sqrt(mu0),
    on a dense log grid with mu(.) and sd(.) log-log interpolated from the probe."""
    lg = np.log(np.asarray(dgrid, float))
    lmu = np.log(np.maximum(np.asarray(mus, float), 1e-14))
    lsd = np.log(np.maximum(np.asarray(sds, float), 1e-14))
    dd = np.geomspace(1e-5, dmax, 4000)
    ld = np.log(dd)
    mu_d = np.exp(np.interp(ld, lg, lmu))
    sd_d = np.exp(np.interp(ld, lg, lsd))
    T = mu_d + t_crit * sd_d
    lhs = np.sqrt(dd)
    rhs = np.sqrt(np.maximum(T, 0.0)) + Z80 * np.sqrt(max(mu0, 0.0))
    sgn = lhs - rhs
    idx = np.where(sgn >= 0)[0]
    if len(idx) == 0:
        return float("nan"), "ABOVE_%.0e" % dmax
    i = idx[0]
    if i == 0:
        return float(dd[0]), "AT_OR_BELOW_1e-5"
    x0, x1, y0, y1 = ld[i - 1], ld[i], sgn[i - 1], sgn[i]
    return float(np.exp(x0 + (0 - y0) * (x1 - x0) / (y1 - y0))), "OK"


if __name__ == "__main__":
    t_start = time.time()
    f = load_frame(verbose=False)
    FW = familywise_thresholds()
    s04 = pd.read_csv(os.path.join(OUT, "s04_mde_table.csv"))

    hdr("A. MEASURE mu(delta) AND sd(delta) ON PLANTED RESPONSES -- the kit, on y(delta)")
    # RESUMABLE: results are written after every cell, so a killed run is restarted, not redone.
    probe_rows, out_rows = [], []
    done = set()
    pp, op = (os.path.join(OUT, "s07_null_drift_probe.csv"),
              os.path.join(OUT, "s07_mde_drift_corrected.csv"))
    if os.path.exists(op):
        prev_o = pd.read_csv(op)
        out_rows = prev_o.to_dict("records")
        done = set(zip(prev_o.stratum, prev_o.base, prev_o["null"]))
        if os.path.exists(pp):
            probe_rows = pd.read_csv(pp).to_dict("records")
        print("  resuming: %d cells already complete" % len(done))
    for sname, bname, nname, carrier, kind, level, block in CELLS:
        if (sname, bname, nname) in done:
            continue
        t0 = time.time()
        sub, y, B, bf = cell_arrays(f, sname, bname, carrier)
        # delta = 0 reference, well estimated
        r0 = kit_pass(bf, sub, carrier, kind, level, block, 600, SEED, [])
        c0 = np.asarray(r0["draws"], float)
        mu0, sd0 = float(np.nanmean(c0)), float(np.nanstd(c0, ddof=1))
        vecs = perm_vectors(bf, sub, carrier, kind, level, block, PROBE_REPS, SEED_POWER)
        dgrid, mus, sds = [0.0], [mu0], [sd0]
        for dlt in PROBE_DELTAS:
            mm, ss = [], []
            for rep, xt_r in enumerate(vecs):
                b1 = float(xt_r @ xt_r)
                if not np.isfinite(b1) or b1 <= 1e-12:
                    continue
                c1 = float(np.sqrt(dlt * bf.sst / b1))
                bf_pl = BaseFit(y + c1 * xt_r, B)
                rp = kit_pass(bf_pl, sub, carrier, kind, level, block, PROBE_DRAWS,
                              SEED + 7000 + rep, [])
                dr = np.asarray(rp["draws"], float)
                mm.append(float(np.nanmean(dr)))
                ss.append(float(np.nanstd(dr, ddof=1)))
            dgrid.append(dlt); mus.append(float(np.median(mm))); sds.append(float(np.median(ss)))
            probe_rows.append(dict(stratum=sname, base=bname, null=nname, delta=dlt,
                                   mu_null=float(np.median(mm)), sd_null=float(np.median(ss)),
                                   mu_null_delta0=mu0, sd_null_delta0=sd0,
                                   rel_drift_mu=float((np.median(mm) - mu0) / mu0),
                                   rel_drift_sd=float((np.median(ss) - sd0) / sd0),
                                   reps=len(mm), draws=PROBE_DRAWS))
        # replace the delta=0 entry so interpolation has a finite log-x anchor
        dgrid[0] = 1e-6
        arm = "N2_entity_swap" if ("entity_swap" in nname or "opp_swap" in nname) else "N1_within"
        for K in K_REPORT:
            tc = FW[(arm, K)]["q95_maxt"] if K > 1 else 1.645
            mde, st = solve_mde(mu0, dgrid, mus, sds, tc)
            prev = s04[(s04.stratum == sname) & (s04.base == bname) & (s04["null"] == nname)
                       & (s04.family_size_K == K)]
            out_rows.append(dict(stratum=sname, base=bname, null=nname, carrier=carrier,
                                 n=int(len(sub)), n_clusters=int(r0.get("n_groups", -1)),
                                 family_size_K=K, t_crit=float(tc),
                                 mu_null_delta0=mu0, sd_null_delta0=sd0,
                                 mde80_DRIFT_CORRECTED=mde, status=st,
                                 mde80_s04_uncorrected=(float(prev["mde80_familywise"].iloc[0])
                                                        if len(prev) else np.nan)))
        pd.DataFrame(probe_rows).to_csv(os.path.join(OUT, "s07_null_drift_probe.csv"),
                                        index=False)
        pd.DataFrame(out_rows).to_csv(os.path.join(OUT, "s07_mde_drift_corrected.csv"),
                                      index=False)
        z = [r for r in out_rows if r["stratum"] == sname and r["base"] == bname
             and r["null"] == nname]
        print("  %-9s %-11s %-32s n=%-6d  mu0=%.2e sd0=%.2e | MDE80 K=1 %.2e  K=132 %.2e "
              " (s04 said %.2e / %.2e)  %5.1fs"
              % (sname, bname, nname, len(sub), mu0, sd0,
                 z[0]["mde80_DRIFT_CORRECTED"], z[4]["mde80_DRIFT_CORRECTED"],
                 z[0]["mde80_s04_uncorrected"], z[4]["mde80_s04_uncorrected"],
                 time.time() - t0))

    hdr("B. DRIFT-CORRECTED MDE80 -- THE HEADLINE TABLE")
    O = pd.DataFrame(out_rows)
    piv = O[O.family_size_K.isin([1, 18, 44, 132, 318])].pivot_table(
        index=["stratum", "base", "null", "n", "n_clusters"], columns="family_size_K",
        values="mde80_DRIFT_CORRECTED")
    pd.set_option("display.width", 250)
    print(piv.to_string())
    print("\n  total %.1fs" % (time.time() - t_start))
