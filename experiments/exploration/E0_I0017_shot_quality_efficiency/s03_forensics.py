"""
E0_I0017 S03 -- FORENSICS ON THE SURVIVORS.  Try to kill them.

31 of 117 cells cleared family-wise in s02.  That is unlike D081/D084/D085 and is therefore the
exact moment at which a screen manufactures a survivor.  This step attempts four specific kills,
each of which a real signal should survive and an artifact should not.

K1  REFERENCE INCOMPLETENESS.  The s02 base is [1, refB_<outcome>] -- ONE measure of the player's
    own prior efficiency.  `D04_xefg_minus_own` is literally `D01_xefg_zone - refB_efg`, so when
    the outcome is ppm it injects refB_efg into a model that only had refB_ppm.  Its "shot quality"
    signal could be nothing but "prior eFG predicts prior-adjusted points per minute".  KILL TEST:
    re-screen every cell against the FULL own-prior base [1, refB_ppm, refB_ts, refB_efg].  This is
    also the brief's question -- "does shot quality predict efficiency BEYOND the player's own
    prior efficiency?" -- asked as stringently as the data allows.

K2  MECHANICAL MIX IDENTITY.  eFG and TS are BY DEFINITION mix-weighted conversion rates, so a
    prior shot-mix feature predicting y_efg is partly arithmetic rather than a discovery.  KILL
    TEST: report ppm separately throughout; ppm is the champion's actual efficiency step (D081) and
    is not a mix identity.

K3  THE DECISION STRATUM.  D081: on >=8 prior appearances and >=24 trailing-5 minutes (37% of
    rows), points skill is -0.36%, p=0.27.  A lead that exists only on low-minute noise rows is
    not decision-relevant.  KILL TEST: re-screen survivors on that stratum.

K4  SEASON STABILITY.  A real mechanism should not live in one season.  KILL TEST: per-season dR2
    and sign for each survivor.

Nothing here fits a model.  All bases are strictly-prior references; no new transformation of any
candidate is introduced, so no new time-window exposure is created (see NOTES.md TIME-WINDOW
TABLE, which covers inference steps).
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sq_base import (  # noqa: E402
    OUT, sk, SEED, N_DRAWS, CANDIDATES, OUTCOMES, FAMILY_OF, ENTITY_COLS, hdr, BaseFit, prior_sum_many,
)

pd.set_option("display.width", 250)
f = pd.read_parquet(os.path.join(OUT, "screen_frame.parquet"))
res = pd.read_csv(os.path.join(OUT, "screen_results.csv"))
sk.assert_partition(f, verbose=False)
info = {}

# =====================================================================================
hdr("0. THE s02 TABLE SPLIT BY OUTCOME -- ppm is the decision-relevant one (D081)")
# =====================================================================================
for rt in OUTCOMES:
    sub = res[res["outcome"] == rt].sort_values("dR2", ascending=False)
    print("\n--- outcome %s : family-wise clears at 0.05 = %d of %d ---"
          % (rt, int((sub["p_familywise_maxz"] < 0.05).sum()), len(sub)))
    print(sub.head(12)[["candidate", "family", "dR2", "beta_sign", "practical_spread_p10_p90",
                        "p_correct_entityswap", "p_familywise_maxz"]].to_string(index=False))


def swap_index_draws(d, entity_cols, n_draws, seed):
    sw = sk.EntitySwap(d, list(entity_cols), date_col="game_date", season_col="season",
                       tiebreak_col="game_id")
    rng = np.random.default_rng(seed)
    idx = np.empty((n_draws, len(d)), dtype=np.int32)
    ar = np.arange(len(d), dtype=float)
    for j in range(n_draws):
        idx[j] = np.rint(sw.draw(ar, rng)).astype(np.int32)
    return idx


# =====================================================================================
hdr("1. K1 -- THE D04 DECOMPOSITION: is its ppm signal shot quality, or just refB_efg?")
# =====================================================================================
d = f[np.isfinite(f["D01_xefg_zone"]) & np.isfinite(f["y_ppm"]) & np.isfinite(f["refB_ppm"])
      & np.isfinite(f["refB_efg"])].reset_index(drop=True)
y = d["y_ppm"].to_numpy(float)
bf1 = BaseFit(y, d["refB_ppm"].to_numpy(float))
rows = []
for lbl, x in [("D04_xefg_minus_own (= D01 - refB_efg)", d["D04_xefg_minus_own"].to_numpy(float)),
               ("D01_xefg_zone alone", d["D01_xefg_zone"].to_numpy(float)),
               ("refB_efg alone (NOT a shot-quality feature)", d["refB_efg"].to_numpy(float))]:
    rows.append({"added_to_base_[1,refB_ppm]": lbl, "dR2": bf1.dr2(x)})
bf2 = BaseFit(y, np.column_stack([d["refB_ppm"].to_numpy(float), d["refB_efg"].to_numpy(float)]))
for lbl, x in [("D04_xefg_minus_own", d["D04_xefg_minus_own"].to_numpy(float)),
               ("D01_xefg_zone", d["D01_xefg_zone"].to_numpy(float))]:
    rows.append({"added_to_base_[1,refB_ppm,refB_efg]": lbl, "dR2": bf2.dr2(x)})
dec = pd.DataFrame(rows)
print(dec.to_string(index=False))
info["D04_decomposition_ppm"] = dec.to_dict("records")
print("\n  READ THIS: if `refB_efg alone` reproduces most of D04's dR2, then D04's ppm result is")
print("  REFERENCE INCOMPLETENESS -- the player's own prior shooting efficiency, which the ppm")
print("  reference omits -- and NOT a shot-quality discovery.")

# =====================================================================================
hdr("2. K1 FULL -- re-screen all 117 cells against the FULL own-prior base")
# =====================================================================================
BASE_FULL = ["refB_ppm", "refB_ts", "refB_efg"]
k1 = []
for ci, c in enumerate(CANDIDATES):
    xall = pd.to_numeric(f[c], errors="coerce")
    mask = np.isfinite(xall) & np.all([np.isfinite(f[b]) for b in BASE_FULL], axis=0)
    d0 = f[mask].reset_index(drop=True)
    IDX = swap_index_draws(d0, ENTITY_COLS[c], N_DRAWS, SEED + 1000 * ci)
    for rt in OUTCOMES:
        ycol = "y_" + rt
        m = np.isfinite(d0[ycol].to_numpy(float))
        mi = np.flatnonzero(m)
        yv = d0.loc[m, ycol].to_numpy(float)
        base = np.column_stack([d0.loc[m, b].to_numpy(float) for b in BASE_FULL])
        bf = BaseFit(yv, base)
        xf = (d0["refB_" + rt].to_numpy(float) if c == "G02_ref_echo"
              else d0[c].to_numpy(float))
        real = bf.dr2(xf[mi])
        dr = np.array([bf.dr2(xf[IDX[j]][mi]) for j in range(N_DRAWS)])
        p = float((1.0 + (dr >= real).sum()) / (N_DRAWS + 1.0))
        sd = float(dr.std(ddof=1))
        prev = res[(res["candidate"] == c) & (res["outcome"] == rt)].iloc[0]
        k1.append({"candidate": c, "family": FAMILY_OF[c], "outcome": rt, "n": int(len(yv)),
                   "dR2_base_single_ref": float(prev["dR2"]),
                   "p_base_single_ref": float(prev["p_correct_entityswap"]),
                   "pfw_base_single_ref": float(prev["p_familywise_maxz"]),
                   "dR2_base_full_ref": float(real), "p_base_full_ref": p,
                   "z_base_full_ref": float((real - dr.mean()) / sd) if sd > 0 else 0.0,
                   "_draws": (dr - dr.mean()) / (sd if sd > 0 else 1.0),
                   "survival_ratio": float(real / prev["dR2"]) if prev["dR2"] > 0 else np.nan})
    print("  [%2d/%2d] %s" % (ci + 1, len(CANDIDATES), c))

K1 = pd.DataFrame(k1)
D = np.vstack(K1["_draws"].to_list())
maxz = D.max(axis=0)
K1["p_familywise_full_ref"] = [float((1.0 + (maxz >= z).sum()) / (N_DRAWS + 1.0))
                               for z in K1["z_base_full_ref"]]
K1 = K1.drop(columns=["_draws"])
K1 = K1.sort_values("dR2_base_full_ref", ascending=False).reset_index(drop=True)
K1.to_csv(os.path.join(OUT, "k1_full_reference_base.csv"), index=False)
att1 = {"n_cells": int(len(K1)),
        "clears_percand_single_ref": int((res["p_correct_entityswap"] < 0.05).sum()),
        "clears_fw_single_ref": int((res["p_familywise_maxz"] < 0.05).sum()),
        "clears_percand_full_ref": int((K1["p_base_full_ref"] < 0.05).sum()),
        "clears_fw_full_ref": int((K1["p_familywise_full_ref"] < 0.05).sum())}
print("\n" + json.dumps(att1, indent=2))
info["k1_attrition"] = att1
print("\nTOP 20 UNDER THE FULL OWN-PRIOR BASE")
print(K1.head(20)[["candidate", "family", "outcome", "dR2_base_single_ref", "dR2_base_full_ref",
                   "survival_ratio", "p_base_full_ref", "p_familywise_full_ref"]].to_string(index=False))
print("\nppm ONLY, under the full base:")
print(K1[K1["outcome"] == "ppm"].head(12)[
    ["candidate", "family", "dR2_base_single_ref", "dR2_base_full_ref", "survival_ratio",
     "p_base_full_ref", "p_familywise_full_ref"]].to_string(index=False))

# =====================================================================================
hdr("3. K3 -- THE DECISION STRATUM (>=8 prior appearances, >=24 trailing-5 minutes)")
# =====================================================================================
f = f.sort_values(["season", "player_id", "game_date", "game_id"], kind="stable").reset_index(drop=True)
f["_t5min"] = f.groupby(["season", "player_id"], sort=False)["minutes"].transform(
    lambda x: x.shift(1).rolling(5, min_periods=1).mean())
strat = f[(f["n_prior"] >= 8) & (f["_t5min"] >= 24)].reset_index(drop=True)
print("  decision stratum: %d rows (%.1f%% of frame), %d players"
      % (len(strat), 100.0 * len(strat) / len(f), strat["player_id"].nunique()))
info["decision_stratum"] = {"n_rows": int(len(strat)), "frac_of_frame": float(len(strat) / len(f))}

# only candidates that cleared family-wise anywhere in s02 or K1
surv = sorted(set(res.loc[res["p_familywise_maxz"] < 0.05, "candidate"])
              | set(K1.loc[K1["p_familywise_full_ref"] < 0.05, "candidate"]))
print("  candidates carried into the stratum test: %d -> %s" % (len(surv), surv))
k3 = []
for ci, c in enumerate(surv):
    xall = pd.to_numeric(strat[c], errors="coerce")
    mask = np.isfinite(xall) & np.all([np.isfinite(strat[b]) for b in BASE_FULL], axis=0)
    d0 = strat[mask].reset_index(drop=True)
    IDX = swap_index_draws(d0, ENTITY_COLS[c], N_DRAWS, SEED + 33000 + ci)
    for rt in OUTCOMES:
        ycol = "y_" + rt
        m = np.isfinite(d0[ycol].to_numpy(float)); mi = np.flatnonzero(m)
        yv = d0.loc[m, ycol].to_numpy(float)
        for blab, bcols in [("single_ref", ["refB_" + rt]), ("full_ref", BASE_FULL)]:
            base = np.column_stack([d0.loc[m, b].to_numpy(float) for b in bcols])
            bf = BaseFit(yv, base)
            xf = d0[c].to_numpy(float)
            real = bf.dr2(xf[mi])
            dr = np.array([bf.dr2(xf[IDX[j]][mi]) for j in range(N_DRAWS)])
            k3.append({"candidate": c, "outcome": rt, "base": blab, "n": int(len(yv)),
                       "dR2": float(real),
                       "p_correct": float((1.0 + (dr >= real).sum()) / (N_DRAWS + 1.0))})
    print("  [%2d/%2d] %s" % (ci + 1, len(surv), c))
K3 = pd.DataFrame(k3).sort_values("dR2", ascending=False).reset_index(drop=True)
K3.to_csv(os.path.join(OUT, "k3_decision_stratum.csv"), index=False)
print("\nDECISION STRATUM, full_ref base, ppm:")
print(K3[(K3["base"] == "full_ref") & (K3["outcome"] == "ppm")].to_string(index=False))
print("\nDECISION STRATUM, full_ref base, all outcomes, top 15:")
print(K3[K3["base"] == "full_ref"].head(15).to_string(index=False))

# =====================================================================================
hdr("4. K4 -- PER-SEASON STABILITY of the survivors (full_ref base)")
# =====================================================================================
k4 = []
for c in surv:
    for rt in OUTCOMES:
        for s in (2021, 2022, 2023, 2024):
            d0 = f[(f["season"] == s) & np.isfinite(pd.to_numeric(f[c], errors="coerce"))
                   & np.isfinite(f["y_" + rt])
                   & np.all([np.isfinite(f[b]) for b in BASE_FULL], axis=0)]
            if len(d0) < 300:
                continue
            bf = BaseFit(d0["y_" + rt].to_numpy(float),
                         np.column_stack([d0[b].to_numpy(float) for b in BASE_FULL]))
            x = d0[c].to_numpy(float)
            k4.append({"candidate": c, "outcome": rt, "season": s, "n": int(len(d0)),
                       "dR2": bf.dr2(x), "beta_sign": bf.beta_sign(x)})
K4 = pd.DataFrame(k4)
K4.to_csv(os.path.join(OUT, "k4_per_season.csv"), index=False)
piv = K4.pivot_table(index=["candidate", "outcome"], columns="season", values="beta_sign")
cons = piv.apply(lambda r: bool(np.all(r.dropna() > 0) or np.all(r.dropna() < 0)), axis=1)
print("  sign-consistent across all four seasons: %d of %d candidate-outcome pairs"
      % (int(cons.sum()), len(cons)))
print(piv.assign(sign_consistent=cons).to_string())
info["k4_sign_consistent"] = {"n_consistent": int(cons.sum()), "n_pairs": int(len(cons))}

with open(os.path.join(OUT, "_s03.json"), "w", encoding="utf-8") as fh:
    json.dump(info, fh, indent=2, default=str)
print("\nwrote k1_full_reference_base.csv, k3_decision_stratum.csv, k4_per_season.csv, _s03.json")
