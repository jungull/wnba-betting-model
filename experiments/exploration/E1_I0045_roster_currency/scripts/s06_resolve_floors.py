#!/usr/bin/env python3
"""E1_I0045 s06 -- RESOLVE the tier-B injection floors that s05's grid did not reach.

s05 swept planted Brier effects up to 0.002.  On tier B the per-row loss difference is an order of
magnitude more dispersed than on tier A, so no tested value reached 80 % power and the harness
emitted `injection_floor_80pct = NaN`, which its verdict rule then read as "below the floor".
That is WRONG: the effect (0.0169) is eight times the largest value tested, not below it.  The bug
is recorded in DEFECTS.md as D-1 and fixed here by extending the grid.  No verdict from s05's
tier-B cells is carried forward; the ones below replace them.
"""
from __future__ import annotations
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rc_base as rb  # noqa: E402

pd.set_option("display.width", 250)
F = {}

PF = pd.read_parquet(os.path.join(rb.OUT, "_PF_arms.parquet"))
y = PF["appeared"].to_numpy(float)
mA = PF["tier_A"].to_numpy(bool)
blk_p = (PF["season"].astype(str) + "_" + PF["player_id"].astype(str)).to_numpy()

GRID = (0.001, 0.002, 0.004, 0.008, 0.012, 0.016, 0.024, 0.032)
rows = []
for wl, wm in (("FULL 2022-2024", PF["season"].isin(rb.SCORED_SEASONS).to_numpy()),
               ("CLEAN 2023-2024", PF["season"].isin(rb.CLEAN_WINDOW).to_numpy())):
    for a, ref in (("Xa_plus", "Xa"), ("Z_R3_union_S2", "Xa"), ("Z_R3_union_S2", "Xa_plus")):
        m = (~mA) & wm
        ba = (np.clip(PF["w_" + a].to_numpy(float), 0, 1) - y) ** 2
        br = (np.clip(PF["w_" + ref].to_numpy(float), 0, 1) - y) ** 2
        r = rb.paired_signflip_block(ba[m], br[m], blk_p[m], 20000, rb.SEED + 7)
        nz = (ba - br)[m]
        pw = {e: rb.injection_power(nz, blk_p[m], e, 2000, rb.SEED + 7, n_reps=200) for e in GRID}
        floor = min([e for e, v in pw.items() if v >= 0.80], default=None)
        print("  %-16s %-14s vs %-8s  delta=%+.6f  p=%.5f  MDE80(signflip)=%.6f"
              % (wl, a, ref, r["real"], r["p"], rb.mde80(r["null_sd"])))
        print("      injection sweep: %s" % {k: round(v, 3) for k, v in pw.items()})
        print("      80%% floor = %s   ->  %s"
              % (floor, "ESTABLISHED" if (r["p"] < 0.05 and floor is not None
                                          and abs(r["real"]) > floor)
                 else "NOT ESTABLISHED"))
        rows.append({"window": wl, "row_set": "RS1P-B (tier B)", "arm": a, "reference": ref,
                     "delta_Brier": r["real"], "p": r["p"], "null_sd": r["null_sd"],
                     "MDE80_signflip": rb.mde80(r["null_sd"]),
                     "injection_floor_80pct": floor, "n_blocks": r["n_blocks"],
                     "power_floor_kind": "INJECTION-VERIFIED",
                     "verdict": ("ESTABLISHED" if (r["p"] < 0.05 and floor is not None
                                                   and abs(r["real"]) > floor)
                                 else "NOT ESTABLISHED")})
R = pd.DataFrame(rows)
R.to_csv(os.path.join(rb.OUT, "tierB_resolved_floors.csv"), index=False)
F["tierB_resolved"] = rows
rb.dump(F, "_s06.json")
print("\nDONE s06")
