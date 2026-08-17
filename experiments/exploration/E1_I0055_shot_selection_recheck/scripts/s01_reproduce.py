"""S01 -- REPRODUCE THE PUBLISHED RESULT FIRST.  Anchors A1-A9 of PREREG.md sec 3.

Nothing new is computed here.  Every number is a target published by
E1_I0004_shot_selection (or E1_I0051_constraint_sweep for A9) and its deviation.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ss_base import (CLEAN, HERE, OUT, PARTITION, RA, SRC, ZONES, ZoneSuff,  # noqa
                     assert_partition, build_frame, decision_frame, hdr, perm_maps,
                     row_beta, season_groups)

PUB_SEED = 20260807          # the parent screen's seed, transcribed
PUB_DRAWS = 5000

TARGET_ROW = {"Restricted Area": 0.7742726671354552,
              "In The Paint (Non-RA)": 0.6529896973770617,
              "Mid-Range": 0.5558250299356523,
              "Corner 3": 0.32472289963558754,
              "Above the Break 3": 0.5629840482545649}
TARGET_CLU = {"Restricted Area": 0.9193293906251634,
              "In The Paint (Non-RA)": 0.9573065893798413,
              "Mid-Range": 0.8107877872674014,
              "Corner 3": 0.6377490716953922,
              "Above the Break 3": 0.7916478162560328}
TARGET_NULLMU = {"Restricted Area": -0.0004875570814531993,
                 "In The Paint (Non-RA)": -0.0018761153363469926,
                 "Mid-Range": 0.0032109681843979975,
                 "Corner 3": -0.019736014477837092,
                 "Above the Break 3": -0.0012719775060356373}
TARGET_NULLSD = {"Restricted Area": 0.15473938432791973,
                 "In The Paint (Non-RA)": 0.20523248884998496,
                 "Mid-Range": 0.15774133896861817,
                 "Corner 3": 0.1538566723102876,
                 "Above the Break 3": 0.15200298685114547}
TARGET_FWE = {"Restricted Area": 0.0001999600079984003,
              "In The Paint (Non-RA)": 0.0023995200959808036,
              "Mid-Range": 0.0009998000399920016,
              "Corner 3": 0.060187962407518496,
              "Above the Break 3": 0.0001999600079984003}
TARGET_R2_RA = 0.035209        # NOTES.md sec 4
TARGET_N_ROWS = 51473
TARGET_N_PG = 10307

RES = {"anchors": []}


def anchor(aid, what, target, got, tol, unit=""):
    dev = float(got - target) if target is not None else float("nan")
    ok = bool(abs(dev) <= tol) if target is not None else False
    RES["anchors"].append(dict(id=aid, what=what, target=target, reproduced=float(got),
                               abs_deviation=abs(dev), tolerance=tol, PASS=ok, unit=unit))
    print(f"  [{aid}] {what:<58} target={target!r}  got={got!r}  "
          f"|dev|={abs(dev):.3e}  {'PASS' if ok else '*** FAIL ***'}")
    return ok


# ================================================================= A8: REBUILD =====
hdr("A8. INDEPENDENT REBUILD of selection_frame.parquet from the 132,558 raw shots")
print("  The frozen baseline module is NOT imported; S1 is transcribed directly as")
print("  EWMA_0.03(zone share)[strictly prior] and role_prior_fga as EWMA_0.30(FGA).")
MINE, PANEL, SHOTS5, TGW = build_frame(verbose=True)
PUB = pd.read_parquet(os.path.join(SRC, "selection_frame.parquet"))
# FILTER-POINT
PUB = PUB[PUB["season"].isin(PARTITION)].copy()
assert_partition(PUB, "published selection_frame")
print(f"\n  rebuilt rows = {len(MINE)}   published rows = {len(PUB)}")

KEY = ["zone", "player_id", "season", "game_id"]
m = MINE.sort_values(KEY, kind="stable").reset_index(drop=True)
p = PUB.sort_values(KEY, kind="stable").reset_index(drop=True)
same_keys = bool(len(m) == len(p) and (m[KEY].to_numpy() == p[KEY].to_numpy()).all())
anchor("A8.keys", "rebuilt row keys identical to published", 1.0,
       1.0 if same_keys else 0.0, 0.0)
CELLCOLS = ["fga", "z_att", "share", "S1", "S2", "resid_S1", "OS", "opp_share_prior",
            "lg_share_prior", "role_prior_fga", "n_prior"]
if same_keys:
    for c in CELLCOLS:
        d = float(np.nanmax(np.abs(m[c].to_numpy(float) - p[c].to_numpy(float))))
        anchor(f"A8.{c}", f"max|rebuilt - published| on {c}", 0.0, d, 1e-12)

FRAME = m if same_keys else p.copy()
FRAME_SOURCE = "INDEPENDENT_REBUILD" if same_keys else "PUBLISHED_FRAME_FALLBACK"
print(f"\n  frame used for every later statistic: {FRAME_SOURCE}")

anchor("A6.rows", "selection analysis rows", float(TARGET_N_ROWS), float(len(FRAME)), 0.0)
anchor("A6.pg", "selection player-games", float(TARGET_N_PG),
       float(FRAME[["player_id", "season", "game_id"]].drop_duplicates().shape[0]), 0.0)

# ============================================================ A1/A2/A3/A7: BETAS ===
hdr("A1/A2/A3/A7. ROW-LEVEL and CLUSTER-LEVEL betas, and R2")
D = FRAME.rename(columns={"resid_S1": "y", "OS": "x", "OPP_TEAM_ID": "opp"})
dd = D.dropna(subset=["y", "x"])
CANON = sorted(set(f"{a}_{b}" for a, b in zip(dd["season"], dd["opp"])))
print(f"  canonical clusters (season_opponent) = {len(CANON)}")
SUFF = {z: ZoneSuff(D, z, CANON) for z in ZONES}
for z in ZONES:
    S = SUFF[z]
    anchor(f"A1/A2.{z}", f"row-level beta, {z}", TARGET_ROW[z],
           row_beta(S.y_row, S.x_row), 1e-12)
for z in ZONES:
    anchor(f"A3.{z}", f"cluster-level beta, {z}", TARGET_CLU[z],
           SUFF[z].stat(SUFF[z].xc), 1e-12)
S = SUFF[RA]
X = np.column_stack([np.ones(S.N), S.x_row])
b, *_ = np.linalg.lstsq(X, S.y_row, rcond=None)
e = S.y_row - X @ b
r2 = 1.0 - float(e @ e) / S.SSTy
anchor("A7.R2", "R2 Restricted Area (unweighted, SST about unweighted mean)",
       TARGET_R2_RA, r2, 5e-7)

# ================================================== A4/A5: THE PUBLISHED NULL ======
hdr("A4/A5. THE PUBLISHED PERMUTATION NULL, re-run from the parent screen's seed")
print(f"  {PUB_DRAWS} draws, seed {PUB_SEED}+1, opponent-team labels permuted WITHIN")
print("  SEASON, the whole five-zone vector travelling with the team.\n")
grps = season_groups(CANON)
rng = np.random.default_rng(PUB_SEED + 1)
mat = np.empty((PUB_DRAWS, len(ZONES)))
for i in range(PUB_DRAWS):
    pm = perm_maps(grps, rng)
    for j, z in enumerate(ZONES):
        mat[i, j] = SUFF[z].stat(SUFF[z].xc[pm])
mu = mat.mean(axis=0)
sd = mat.std(axis=0, ddof=1)
for j, z in enumerate(ZONES):
    anchor(f"A4.mu.{z}", f"null mean, {z}", TARGET_NULLMU[z], float(mu[j]), 1e-12)
    anchor(f"A4.sd.{z}", f"null sd, {z}", TARGET_NULLSD[z], float(sd[j]), 1e-12)

zmat = (mat - mu) / sd
maxz = zmat.max(axis=1)
maxabs = np.abs(zmat).max(axis=1)
argmax = zmat.argmax(axis=1)
print()
for j, z in enumerate(ZONES):
    br = row_beta(SUFF[z].y_row, SUFF[z].x_row)
    zr = (br - mu[j]) / sd[j]
    p1 = float(((maxz >= zr).sum() + 1) / (PUB_DRAWS + 1))
    anchor(f"A5.{z}", f"family-wise p (row-level real, 1-sided), {z}", TARGET_FWE[z],
           p1, 1e-12)

hdr("SINGLE-CELL DOMINANCE OF THE FAMILY-WISE BAR (never previously reported)")
dom = {ZONES[k]: float((argmax == k).mean()) for k in range(len(ZONES))}
for z, v in sorted(dom.items(), key=lambda kv: -kv[1]):
    print(f"  {z:<24} supplies the max-z in {v * 100:6.2f}% of {PUB_DRAWS} draws")
RES["familywise_single_cell_dominance_published_null"] = dom

np.savez_compressed(
    os.path.join(OUT, "raw", "A45_published_null_draws_signed_raw.npz"),
    beta_draws=mat, zones=np.array(ZONES, dtype=object), null="N_TSSWAP_published",
    statistic="cluster_level_beta", arm="RAW", frozen="FROZEN",
    rowset="ALL_PUBLISHED_2021_2024", seed=PUB_SEED + 1, n_draws=PUB_DRAWS)

# ============================================================ A9: DECISION STRATUM =
hdr("A9. DECISION-STRATUM MACHINERY -- anchor against E1_I0051's 3,167 / 764")
DEC = decision_frame(verbose=True)
mp = pd.read_parquet(os.path.join(os.path.dirname(SRC), "..", "..", "data", "masters",
                                  "master_player.parquet"), columns=["season"]) \
    if False else None
reg = DEC[(DEC["season_type"] == "Regular Season") & (DEC["season"].isin(CLEAN))]
sub = reg[reg["DECISION"]]
nblocks = sub[["game_id", "team_id"]].drop_duplicates().shape[0]
anchor("A9.n", "E1_I0051 DECISION x CLEAN 2023-24 rows", 3167.0, float(len(sub)), 0.0)
anchor("A9.blocks", "E1_I0051 DECISION x CLEAN 2023-24 team-game blocks", 764.0,
       float(nblocks), 0.0)

# ============================================================================ WRITE
hdr("WRITE")
RES["frame_source"] = FRAME_SOURCE
RES["n_pass"] = int(sum(a["PASS"] for a in RES["anchors"]))
RES["n_anchors"] = len(RES["anchors"])
RES["n_exact_zero"] = int(sum(1 for a in RES["anchors"] if a["abs_deviation"] == 0.0))
print(f"  anchors: {RES['n_pass']} / {RES['n_anchors']} PASS, "
      f"{RES['n_exact_zero']} at exactly 0.000e+00")
FRAME.to_parquet(os.path.join(HERE, "_frame.parquet"), index=False)
TGW.to_parquet(os.path.join(HERE, "_tgw.parquet"), index=False)
DEC.to_parquet(os.path.join(HERE, "_dec.parquet"), index=False)
json.dump(RES, open(os.path.join(HERE, "_s01.json"), "w", encoding="utf-8"), indent=2,
          default=float)
print("  wrote _frame.parquet, _tgw.parquet, _dec.parquet, _s01.json")
print(f"  PARTITION RE-ASSERT: {sorted(FRAME['season'].unique())}")
print("\nDone.")
