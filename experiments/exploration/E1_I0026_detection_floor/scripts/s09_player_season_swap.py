"""s09_player_season_swap.py -- STEP 4's cheapest candidate lever, measured rather than asserted.

Every correct-level null this programme runs on a PLAYER-level candidate is anchored either at
TEAM-SEASON (48 clusters: 12 teams x 4 seasons -- a hard ceiling that no number of extra rows
inside 2021-2024 can raise) or at the within-player cyclic shift (which asks the WITHIN-player
question and therefore carries the feature's whole between-player association inside its own
null).  Neither is the between-PLAYER question at the player level.

`entity_swap_null(entity_cols=["player_id","season"])` is that null, it is already a kit
function, and it has 600 clusters instead of 48.  This file measures its drift-corrected MDE80
so the recommendation in POWER_VERDICT.md is a number rather than a hope.
"""
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from df_base import CARRIER_PLAYER, OUT, SEED, BaseFit, hdr, load_frame
from s04_power import cell_arrays, familywise_thresholds, kit_pass
from s07_drift_corrected_mde import (K_REPORT, PROBE_DELTAS, PROBE_DRAWS, PROBE_REPS, SEED_POWER,
                                     perm_vectors, solve_mde)

CELLS = [(s, b, "N_E_entity_swap_player_season", CARRIER_PLAYER, "entity_swap",
          ["player_id", "season"], None)
         for s in ("DECISION", "POOLED") for b in ("B_SINGLE", "B_COMPLETE")]

if __name__ == "__main__":
    t0 = time.time()
    f = load_frame(verbose=False)
    FW = familywise_thresholds()
    probe_rows, out_rows = [], []
    hdr("PLAYER-SEASON ENTITY SWAP -- 600 clusters instead of 48")
    for sname, bname, nname, carrier, kind, level, block in CELLS:
        sub, y, B, bf = cell_arrays(f, sname, bname, carrier)
        r0 = kit_pass(bf, sub, carrier, kind, level, block, 600, SEED, [])
        c0 = np.asarray(r0["draws"], float)
        mu0, sd0 = float(np.nanmean(c0)), float(np.nanstd(c0, ddof=1))
        vecs = perm_vectors(bf, sub, carrier, kind, level, block, PROBE_REPS, SEED_POWER)
        dgrid, mus, sds = [1e-6], [mu0], [sd0]
        for dlt in PROBE_DELTAS:
            mm, ss = [], []
            for rep, xt_r in enumerate(vecs):
                b1 = float(xt_r @ xt_r)
                if not np.isfinite(b1) or b1 <= 1e-12:
                    continue
                c1 = float(np.sqrt(dlt * bf.sst / b1))
                rp = kit_pass(BaseFit(y + c1 * xt_r, B), sub, carrier, kind, level, block,
                              PROBE_DRAWS, SEED + 7000 + rep, [])
                dr = np.asarray(rp["draws"], float)
                mm.append(float(np.nanmean(dr))); ss.append(float(np.nanstd(dr, ddof=1)))
            dgrid.append(dlt); mus.append(float(np.median(mm))); sds.append(float(np.median(ss)))
            probe_rows.append(dict(stratum=sname, base=bname, null=nname, delta=dlt,
                                   mu_null=mus[-1], sd_null=sds[-1], mu_null_delta0=mu0,
                                   sd_null_delta0=sd0,
                                   rel_drift_sd=float((sds[-1] - sd0) / sd0)))
        for K in K_REPORT:
            tc = FW[("N2_entity_swap", K)]["q95_maxt"] if K > 1 else 1.645
            mde, st = solve_mde(mu0, dgrid, mus, sds, tc)
            out_rows.append(dict(stratum=sname, base=bname, null=nname, carrier=carrier,
                                 n=int(len(sub)), n_clusters=int(r0.get("n_groups", -1)),
                                 family_size_K=K, t_crit=float(tc), mu_null_delta0=mu0,
                                 sd_null_delta0=sd0, mde80_DRIFT_CORRECTED=mde, status=st))
        z = [r for r in out_rows if r["stratum"] == sname and r["base"] == bname]
        print("  %-9s %-11s n=%-6d clusters=%-4d mu0=%.2e sd0=%.2e | MDE80 K=1 %.2e  K=18 %.2e"
              "  K=132 %.2e" % (sname, bname, len(sub), r0.get("n_groups", -1), mu0, sd0,
                                z[0]["mde80_DRIFT_CORRECTED"], z[1]["mde80_DRIFT_CORRECTED"],
                                z[4]["mde80_DRIFT_CORRECTED"]))
        pd.DataFrame(out_rows).to_csv(os.path.join(OUT, "s09_player_season_swap_mde.csv"),
                                      index=False)
        pd.DataFrame(probe_rows).to_csv(os.path.join(OUT, "s09_player_season_swap_probe.csv"),
                                        index=False)
    print("\n  total %.1fs" % (time.time() - t0))
