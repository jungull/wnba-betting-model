"""s05_drift_and_n.py -- STAGE 3.

(1) THE PRE-COMMITTED FALSIFICATION CHECK (PREREGISTRATION s6).
    s04 standardises the planted statistic by (mu, sigma) from the delta=0 null.  That is only
    legitimate if the null's WIDTH does not move when an effect is planted.  Here the null is
    RECOMPUTED, with the kit, on planted responses y(delta), and the relative drift in sigma is
    reported.  If drift > 10% at the delta that matters, the factorisation is abandoned there and
    the MDE is recomputed with the drifted sigma.

    NOTE: the `drift` column printed by s04 was NOT this check -- it was the spread of the
    statistic ACROSS REPLICATES, which of course grows with a planted effect.  That column is
    renamed and ignored; this file carries the check the preregistration actually asked for.

(2) THE SAMPLE-SIZE SWEEP.  n is varied by sampling WHOLE PLAYER-SEASONS, never rows, so a
    smaller screen loses clusters the way a real smaller screen does.  The n values are the ones
    that actually appear in the ledger.
"""
import json
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from df_base import (BASES, CARRIER_OPP, CARRIER_PLAYER, OUT, OUTCOME, SEED, BaseFit, hdr,
                     load_frame, sk, stratum_mask)
from s04_power import (DELTAS, FAMILY_SIZES, cell_arrays, dr2_grid, familywise_thresholds,
                       kit_pass, mde_at)

DRIFT_DELTAS = [1e-3, 3e-3, 1e-2]
DRIFT_REPS = 12
DRIFT_DRAWS = 300
N_TARGETS = [3549, 4517, 5111, 5673, 9517, 11738, 14327, 14852]
R_SWEEP = 1000
SEED_POWER = SEED + 101

CHECK_CELLS = [
    ("POOLED", "B_SINGLE", "N_B_entity_swap_team_season", CARRIER_PLAYER, "entity_swap",
     ["team_id", "season"], None),
    ("DECISION", "B_SINGLE", "N_B_entity_swap_team_season", CARRIER_PLAYER, "entity_swap",
     ["team_id", "season"], None),
    ("DECISION", "B_COMPLETE", "N_A_within_player_cyclic", CARRIER_PLAYER, "perm_cyclic",
     ["player_id", "season"], None),
    ("POOLED", "B_SINGLE", "N_D_within_date_opp_swap", CARRIER_OPP, "perm_between",
     ["opp_team_id", "game_id"], "game_date"),
]

SWEEP_NULLS = [
    ("N_A_within_player_cyclic", CARRIER_PLAYER, "perm_cyclic", ["player_id", "season"], None),
    ("N_B_entity_swap_team_season", CARRIER_PLAYER, "entity_swap", ["team_id", "season"], None),
    ("N_D_within_date_opp_swap", CARRIER_OPP, "perm_between", ["opp_team_id", "game_id"],
     "game_date"),
]

if __name__ == "__main__":
    t_start = time.time()
    f = load_frame(verbose=False)
    FW = familywise_thresholds()

    # =========================================================================================
    hdr("A. PRE-COMMITTED CHECK -- does the NULL WIDTH move when an effect is planted?")
    # =========================================================================================
    drows = []
    for sname, bname, nname, carrier, kind, level, block in CHECK_CELLS:
        sub, y, B, bf = cell_arrays(f, sname, bname, carrier)
        cap0 = []
        r0 = kit_pass(bf, sub, carrier, kind, level, block, DRIFT_DRAWS, SEED, cap0)
        sd0 = float(np.nanstd(np.asarray(r0["draws"], float), ddof=1))

        # DRIFT_REPS permuted carriers, kept as VECTORS so the plant can be built from them.
        vecs = []

        def cap_vec(dfr, _bf=bf, _v=vecs):
            x = pd.to_numeric(dfr["feat"], errors="coerce").to_numpy(float)
            xt = _bf.resid_x(x)
            _v.append(xt)
            bb = float(xt @ xt)
            aa = float(_bf.e @ xt)
            return (aa * aa / bb) / _bf.sst if bb > 1e-12 else 0.0

        d = sub[["season", "player_id", "team_id", "opp_team_id", "game_id",
                 "game_date"]].copy()
        d["feat"] = sub[carrier].to_numpy(float)
        if kind == "entity_swap":
            sk.entity_swap_null(cap_vec, d, level, DRIFT_REPS, SEED_POWER, feature_col="feat",
                                date_col="game_date", season_col="season",
                                tiebreak_col="game_id")
        elif kind == "perm_cyclic":
            sk.permutation_null(cap_vec, d, level, DRIFT_REPS, SEED_POWER, feature_col="feat",
                                scheme=sk.SCHEME_WITHIN_CYCLIC, order_col="game_date")
        else:
            sk.permutation_null(cap_vec, d, level, DRIFT_REPS, SEED_POWER, feature_col="feat",
                                scheme=sk.SCHEME_BETWEEN, block_col=block)

        for dlt in DRIFT_DELTAS:
            sds = []
            for rep in range(min(DRIFT_REPS, len(vecs))):
                xt_r = vecs[rep]
                b1 = float(xt_r @ xt_r)
                if not np.isfinite(b1) or b1 <= 1e-12:
                    continue
                c1 = float(np.sqrt(dlt * bf.sst / b1))
                bf_pl = BaseFit(y + c1 * xt_r, B)      # THE NULL IS RECOMPUTED ON y(delta)
                r2 = kit_pass(bf_pl, sub, carrier, kind, level, block, DRIFT_DRAWS,
                              SEED + 7000 + rep, [])
                sds.append(float(np.nanstd(np.asarray(r2["draws"], float), ddof=1)))
            sds = np.array(sds, float)
            rec = dict(stratum=sname, base=bname, null=nname, delta=dlt,
                       sigma_null_delta0=sd0, sigma_null_planted_median=float(np.median(sds)),
                       sigma_null_planted_max=float(np.max(sds)),
                       rel_drift_median=float(abs(np.median(sds) - sd0) / sd0),
                       rel_drift_max=float(np.max(np.abs(sds - sd0)) / sd0),
                       n_reps=int(len(sds)))
            drows.append(rec)
            print("  %-9s %-11s %-32s delta=%.0e  sigma0=%.3e  planted=%.3e  "
                  "drift_med=%.1f%%  drift_max=%.1f%%"
                  % (sname, bname, nname, dlt, sd0, rec["sigma_null_planted_median"],
                     100 * rec["rel_drift_median"], 100 * rec["rel_drift_max"]))
            pd.DataFrame(drows).to_csv(os.path.join(OUT, "s05_sigma_drift.csv"), index=False)

    dd = pd.DataFrame(drows)
    print("\n  WORST median drift over all checked cells and deltas: %.1f%%"
          % (100 * dd["rel_drift_median"].max()))
    print("  PREREGISTERED THRESHOLD 10%%.  VERDICT: %s"
          % ("FACTORISATION HOLDS" if dd["rel_drift_median"].max() <= 0.10
             else "FACTORISATION FAILS -- MDEs must be recomputed with the drifted sigma"))

    # =========================================================================================
    hdr("B. SAMPLE-SIZE SWEEP -- n varied by dropping WHOLE PLAYER-SEASONS")
    # =========================================================================================
    rng = np.random.default_rng(SEED)
    f = f.copy()
    f["_ps"] = f["player_id"].astype(str) + "|" + f["season"].astype(str)
    ps = f["_ps"].drop_duplicates().to_numpy()
    srows = []
    for n_target in N_TARGETS:
        if n_target >= len(f):
            keep_mask = np.ones(len(f), bool)
        else:
            order = rng.permutation(ps)
            sizes = f.groupby("_ps", sort=False).size()
            cum, chosen = 0, []
            for k in order:
                chosen.append(k)
                cum += int(sizes[k])
                if cum >= n_target:
                    break
            keep_mask = f["_ps"].isin(set(chosen)).to_numpy()
        sub_f = f.loc[keep_mask].reset_index(drop=True)
        sk.assert_partition(sub_f, verbose=False)
        for nname, carrier, kind, level, block in SWEEP_NULLS:
            bname = "B_COMPLETE"
            basecols = BASES[bname]
            cols = [OUTCOME] + basecols + [carrier]
            m = np.ones(len(sub_f), bool)
            for c in cols:
                m &= np.isfinite(pd.to_numeric(sub_f[c], errors="coerce").to_numpy(float))
            s2 = sub_f.loc[m].reset_index(drop=True)
            y = s2[OUTCOME].to_numpy(float)
            B = s2[basecols].to_numpy(float)
            bf = BaseFit(y, B)
            cap0 = []
            r0 = kit_pass(bf, s2, carrier, kind, level, block, 400, SEED, cap0)
            cal = np.asarray(r0["draws"], float)
            mu, sd = float(np.nanmean(cal)), float(np.nanstd(cal, ddof=1))
            tc1 = float(np.nanquantile((cal - mu) / sd, 0.95))
            cap = []
            kit_pass(bf, s2, carrier, kind, level, block, R_SWEEP, SEED_POWER, cap)
            A = np.array([c[0] for c in cap], float)
            Bd = np.array([c[1] for c in cap], float)
            ok = np.isfinite(A) & np.isfinite(Bd) & (Bd > 1e-12)
            A, Bd = A[ok], Bd[ok]
            DR = np.vstack([dr2_grid(A[i], Bd[i], bf.sst, DELTAS) for i in range(len(A))])
            T = (DR - mu) / sd
            arm = "N2_entity_swap" if ("entity_swap" in nname or "opp_swap" in nname) \
                else "N1_within"
            pw1 = (T >= tc1).mean(axis=0)
            row = dict(n_target=n_target, n=int(len(s2)),
                       n_player_seasons=int(s2["_ps"].nunique()),
                       n_clusters=int(r0.get("n_groups", -1)), null=nname, base=bname,
                       carrier=carrier, null_mean=mu, null_sd=sd,
                       type1_at_delta0=float(pw1[0]),
                       mde80_per_cell=mde_at(DELTAS, pw1)[0])
            for K in (44, 132, 318):
                tc = FW[(arm, K)]["q95_maxt"]
                row["mde80_K%d" % K] = mde_at(DELTAS, (T >= tc).mean(axis=0))[0]
            srows.append(row)
            print("  n=%-6d ps=%-4d %-32s clusters=%-5s  MDE80: cell=%s K132=%s"
                  % (row["n"], row["n_player_seasons"], nname, row["n_clusters"],
                     "%.2e" % row["mde80_per_cell"], "%.2e" % row["mde80_K132"]))
            pd.DataFrame(srows).to_csv(os.path.join(OUT, "s05_mde_vs_n.csv"), index=False)

    print("\n  total %.1fs" % (time.time() - t_start))
