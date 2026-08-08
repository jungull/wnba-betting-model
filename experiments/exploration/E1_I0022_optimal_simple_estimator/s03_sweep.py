"""E1_I0022 STEP 3 -- SWEEP THE PREREGISTERED ESTIMATOR SURFACE.

Refuses to run unless the recomputed grid hash matches the one preregistered in s02.

For every one of the 15,048 cells this records the SUM OF ABSOLUTE ERRORS in each of
(season x prior-appearance tier x decision-stratum) = 36 buckets, from which every MAE, every
tune/eval split and every stratification in s04 is derived.  No selection happens here -- this step
computes the surface only, so that selection in s04 cannot be contaminated by having looked.
"""
import json
import os
import time

import numpy as np
import pandas as pd

import ose_base as B

t0 = time.time()
PRE = json.load(open(os.path.join(B.OUT, "_prereg.json")))
ghash, ncells = B.grid_hash()
assert ghash == PRE["grid_sha256"], "GRID HASH MISMATCH -- the grid changed after preregistration"
B.hdr("STEP 3 -- SWEEP  (grid sha256 %s verified, %d cells)" % (ghash[:16], ncells))

f = B.load_frame(verbose=True)
codes, starts, ns = B.group_bounds(f)
n = len(f)
mins = f["y_minutes"].to_numpy(float)

# ---- bucketing: season x depth tier x decision stratum -------------------------------------
season = f["season"].to_numpy()
s_idx = np.searchsorted(np.array(B.SCREEN_SEASONS), season)
gp = f["pl_games_prior"].to_numpy(float)
TIER_EDGES = [0, 1, 3, 8, 15, 25]
TIER_NAMES = ["0", "1-2", "3-7", "8-14", "15-24", "25+"]
tier = np.searchsorted(np.array(TIER_EDGES), gp, side="right") - 1
tier = np.clip(tier, 0, len(TIER_NAMES) - 1).astype(int)
m5 = f["pl_min_mean5"].to_numpy(float)
stratum = ((gp >= 8) & (m5 >= 24)).astype(int)          # D081's decision stratum
bcode = (s_idx * len(TIER_NAMES) + tier) * 2 + stratum
NB = len(B.SCREEN_SEASONS) * len(TIER_NAMES) * 2
bn = np.bincount(bcode, minlength=NB).astype(float)
print("  buckets: 3 seasons x %d tiers x 2 stratum = %d ; nonempty=%d ; decision-stratum rows=%d"
      % (len(TIER_NAMES), NB, int((bn > 0).sum()), int(stratum.sum())))
print("  tier sizes: %s" % dict(zip(TIER_NAMES, np.bincount(tier, minlength=6).tolist())))

YCOL = {"pts": "y_pts", "minutes": "y_minutes", "fga": "y_fga", "ppm": "r_ppm"}
CHAMP = {"pts": "pts__pred_point", "minutes": "minutes__pred_point",
         "fga": "fga__pred_point", "ppm": "mdl_ppm"}
D081REF = {"pts": "ref_pts", "minutes": "ref_minutes", "fga": "ref_fga", "ppm": "refB_ppm"}

Y = {t: f[YCOL[t]].to_numpy(float) for t in B.TARGETS}
bucket_champ = {}
bucket_d081 = {}
for t in B.TARGETS:
    bucket_champ[t] = np.bincount(bcode, weights=np.abs(Y[t] - f[CHAMP[t]].to_numpy(float)),
                                  minlength=NB)
    bucket_d081[t] = np.bincount(bcode, weights=np.abs(Y[t] - f[D081REF[t]].to_numpy(float)),
                                 minlength=NB)

# ---- shrinkage targets, one set per (target, mode); independent of floor --------------------
bucket_role = B.role_bucket(f)
print("  role buckets (prior-season MPG tercile; -1 = no previous season in frame): %s"
      % dict(zip(*[x.tolist() for x in np.unique(bucket_role, return_counts=True)])))

BASE = [(t, m) for t in B.TARGETS for m in B.MODES[t] if m != "composite"]
ND = {}
TGT = {}
grand_rows = {}
for t, mode in BASE:
    num, den = B.numden(f, t, mode)
    ND[(t, mode)] = (num, den)
    grand = float(num.sum() / den.sum())
    TGT[(t, mode)], ng = B.build_shrink_targets(f, num, den, bucket_role, grand)
    grand_rows["%s/%s" % (t, mode)] = ng
print("  shrink targets built for %d (target,mode) bases" % len(BASE))
print("  rows taking the GRAND (whole-frame) fallback -- 2022 opening-date rows only: %s"
      % grand_rows)
# VERIFY the claim rather than asserting it in prose.  Rows on the OPENING DATE of each season have
# no strictly-earlier same-season game (135 rows, all three seasons) -- that is correct and expected.
# What matters is the next link in the chain: 2023/2024 opening-date rows fall back to the PREVIOUS
# SEASON's league value, which is strictly prior; only 2022's opening-date rows reach GRAND.
_num0, _den0 = ND[("pts", "equal")]
_nolg = ~np.isfinite(B._expanding_league_ratio(f, _num0, _den0))
_noprev = _nolg & ~np.isfinite(B._prev_season_league(f, _num0, _den0))
print("  rows with NO same-season prior league history (opening dates): %d, seasons=%s"
      % (int(_nolg.sum()), sorted(set(season[_nolg].tolist()))))
print("  ...of which reach the GRAND whole-frame fallback: %d, seasons=%s  (MUST be 2022 only)"
      % (int(_noprev.sum()), sorted(set(season[_noprev].tolist()))))
assert set(season[_noprev].tolist()) <= {2022}, "GRAND fallback touches an EVALUATION season"
GRAND_ROWS_MASK = _noprev

# ---- sweep ----------------------------------------------------------------------------------
rec_keys = []
rec_sae = []
for fi, floor in enumerate(B.FLOORS):
    for mem in B.MEMORIES:
        S = {}
        for t, mode in BASE:
            num, den = ND[(t, mode)]
            S[(t, mode)] = B.prior_sums(num, den, mins, starts, ns, floor, mem)
        for sh in B.SHRINKS:
            est = {}
            for t, mode in BASE:
                est[(t, mode)] = B.apply_shrink(*S[(t, mode)], TGT[(t, mode)], sh)
            est[("pts", "composite")] = (est[("minutes", "equal")]
                                         * est[("ppm", "ratio_of_prior_sums")])
            for t in B.TARGETS:
                for mode in B.MODES[t]:
                    e = est[(t, mode)]
                    ae = np.abs(Y[t] - e)
                    rec_keys.append((t, mode, mem[0], mem[1], sh[0], sh[1], floor))
                    rec_sae.append(np.bincount(bcode, weights=ae, minlength=NB))
        print("    floor=%4.1f memory=%-9s %-5s   cells so far %6d   %.1fs"
              % (floor, mem[0], mem[1], len(rec_keys), time.time() - t0))

SAE = np.asarray(rec_sae)
assert len(rec_keys) == ncells, "swept %d cells, preregistered %d" % (len(rec_keys), ncells)
print("\n  swept %d cells in %.1fs" % (len(rec_keys), time.time() - t0))

keys = pd.DataFrame(rec_keys, columns=["target", "mode", "memory_kind", "memory_param",
                                       "shrink_target", "shrink_k", "floor"])
np.savez_compressed(os.path.join(B.OUT, "surface_sae.npz"), sae=SAE, bn=bn, bcode=bcode,
                    champ=np.array([bucket_champ[t] for t in B.TARGETS]),
                    d081=np.array([bucket_d081[t] for t in B.TARGETS]),
                    targets=np.array(B.TARGETS), tier_names=np.array(TIER_NAMES),
                    seasons=np.array(B.SCREEN_SEASONS))
keys.to_parquet(os.path.join(B.OUT, "surface_keys.parquet"), index=False)
json.dump({"grid_sha256": ghash, "n_cells": int(ncells), "n_buckets": int(NB),
           "tier_names": TIER_NAMES, "tier_edges": TIER_EDGES,
           "bucket_counts": bn.tolist(), "grand_fallback_rows": grand_rows,
           "grand_fallback_row_index": np.flatnonzero(GRAND_ROWS_MASK).tolist(),
           "grand_fallback_seasons": sorted(set(season[GRAND_ROWS_MASK].tolist())),
           "decision_stratum_rows": int(stratum.sum()),
           "decision_stratum_def": "pl_games_prior >= 8 AND pl_min_mean5 >= 24 (D081)",
           "elapsed_s": time.time() - t0},
          open(os.path.join(B.OUT, "_s03.json"), "w"), indent=2)
print("  wrote surface_sae.npz + surface_keys.parquet")
print("DONE s03")
