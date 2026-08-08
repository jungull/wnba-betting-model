"""
E0_I0017 S04 -- WHY A REAL eFG/TS EFFECT DOES NOT REACH POINTS PER MINUTE.

s02/s03 found a stable, sign-consistent, decision-stratum-surviving effect of prior shot mix on
y_efg and y_ts, and NOTHING on y_ppm.  A null on ppm alongside a strong effect on eFG is only
interesting if the mechanism is understood, so this step tests the obvious candidate mechanism:

    ppm = points/minute ~= (points per shot) x (shots per minute)

If a player who shoots closer converts better (eFG up) but also takes FEWER shots per minute, the
two channels offset and points per minute is unmoved.  This is a VOLUME-OFFSET hypothesis and it
is directly testable with the same machinery: screen the same shot-mix candidates against a
shots-per-minute outcome and read the SIGN against the eFG sign.

E0 CHARACTER: this is a mechanism sketch to make a null interpretable, not a result.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sq_base import (  # noqa: E402
    OUT, sk, SEED, N_DRAWS, ENTITY_COLS, hdr, BaseFit, safe_div, prior_sum_many,
)

pd.set_option("display.width", 240)
f = pd.read_parquet(os.path.join(OUT, "screen_frame.parquet"))
f = f.sort_values(["season", "player_id", "game_date", "game_id"], kind="stable").reset_index(drop=True)
sk.assert_partition(f, verbose=False)
info = {}

# ---- volume outcome + its own strictly-prior reference (same construction as every other ref) ----
f["y_fgapm"] = safe_div(f["fga"], f["minutes"])
QS = prior_sum_many(f, ["season", "player_id"], ["fga", "minutes"])
b = pd.Series(safe_div(QS["fga"], QS["minutes"]), index=f.index)
lg = f.sort_values(["season", "game_date", "game_id"], kind="stable") \
      .groupby("season", sort=False)["y_fgapm"].transform(lambda x: x.shift(1).expanding().mean()) \
      .reindex(f.index)
f["refB_fgapm"] = b.fillna(lg)
print("  y_fgapm mean=%.4f  refB_fgapm finite=%d of %d"
      % (f["y_fgapm"].mean(), int(f["refB_fgapm"].notna().sum()), len(f)))

BASE_FULL = ["refB_ppm", "refB_ts", "refB_efg"]
CANDS = ["A02_share_lt5ft", "A03_share_restricted", "A04_share_paint", "A11_share_layup_action",
         "A01_dist_mean", "B01_dist_t5", "B02_lt5ft_t5", "D01_xefg_zone", "D03_xefg_action",
         "A08_share_3pa", "A10_share_selfcreate_action", "A09_share_catch_action"]


def swap_index_draws(d, entity_cols, n_draws, seed):
    sw = sk.EntitySwap(d, list(entity_cols), date_col="game_date", season_col="season",
                       tiebreak_col="game_id")
    rng = np.random.default_rng(seed)
    idx = np.empty((n_draws, len(d)), dtype=np.int32)
    ar = np.arange(len(d), dtype=float)
    for j in range(n_draws):
        idx[j] = np.rint(sw.draw(ar, rng)).astype(np.int32)
    return idx


hdr("1. THE SAME CANDIDATES AGAINST eFG, AGAINST SHOTS-PER-MINUTE, AND AGAINST ppm")
rows = []
for ci, c in enumerate(CANDS):
    x = pd.to_numeric(f[c], errors="coerce")
    mask = (np.isfinite(x) & np.isfinite(f["refB_fgapm"]) & np.isfinite(f["y_fgapm"])
            & np.all([np.isfinite(f[bb]) for bb in BASE_FULL], axis=0))
    d0 = f[mask].reset_index(drop=True)
    IDX = swap_index_draws(d0, ENTITY_COLS[c], N_DRAWS, SEED + 91000 + ci)
    xf = d0[c].to_numpy(float)
    out = {"candidate": c, "n": int(len(d0))}
    for lbl, ycol, bcols in [
            ("efg", "y_efg", BASE_FULL),
            ("fga_per_min", "y_fgapm", BASE_FULL + ["refB_fgapm"]),
            ("ppm", "y_ppm", BASE_FULL)]:
        yv = d0[ycol].to_numpy(float)
        base = np.column_stack([d0[bb].to_numpy(float) for bb in bcols])
        bf = BaseFit(yv, base)
        real = bf.dr2(xf)
        dr = np.array([bf.dr2(xf[IDX[j]]) for j in range(N_DRAWS)])
        xt = bf.resid_x(xf); den = float(xt @ xt)
        beta = float(bf.e @ xt) / den if den > 1e-12 else 0.0
        out["dR2_" + lbl] = float(real)
        out["sign_" + lbl] = float(np.sign(beta))
        out["p_" + lbl] = float((1.0 + (dr >= real).sum()) / (N_DRAWS + 1.0))
        out["spread_" + lbl] = float(beta * (np.nanpercentile(xf, 90) - np.nanpercentile(xf, 10)))
    out["signs_oppose"] = bool(out["sign_efg"] * out["sign_fga_per_min"] < 0)
    rows.append(out)
    print("  [%2d/%2d] %s" % (ci + 1, len(CANDS), c))

T = pd.DataFrame(rows)
cols = ["candidate", "n", "dR2_efg", "sign_efg", "p_efg", "spread_efg",
        "dR2_fga_per_min", "sign_fga_per_min", "p_fga_per_min", "spread_fga_per_min",
        "dR2_ppm", "sign_ppm", "p_ppm", "signs_oppose"]
print("\n" + T[cols].to_string(index=False))
T.to_csv(os.path.join(OUT, "s04_volume_offset.csv"), index=False)

n_opp = int(T["signs_oppose"].sum())
print("\n  candidates whose eFG effect and shots-per-minute effect have OPPOSING signs: %d of %d"
      % (n_opp, len(T)))
print("  candidates significant on eFG (p<0.05): %d" % int((T["p_efg"] < 0.05).sum()))
print("  candidates significant on shots-per-minute (p<0.05): %d" % int((T["p_fga_per_min"] < 0.05).sum()))
print("  candidates significant on ppm (p<0.05): %d" % int((T["p_ppm"] < 0.05).sum()))
info["volume_offset"] = {
    "n_candidates": int(len(T)), "n_signs_oppose": n_opp,
    "n_sig_efg": int((T["p_efg"] < 0.05).sum()),
    "n_sig_fga_per_min": int((T["p_fga_per_min"] < 0.05).sum()),
    "n_sig_ppm": int((T["p_ppm"] < 0.05).sum()),
}

hdr("2. DOES THE eFG GAIN BUY ANY POINTS?  practical spreads side by side")
print("  spread_efg          = change in eFG      over the candidate's p10 -> p90")
print("  spread_fga_per_min  = change in FGA/min  over the same range")
print("  spread_ppm          = change in pts/min  over the same range")
print(T[["candidate", "spread_efg", "spread_fga_per_min", "spread_ppm"]].to_string(index=False))
print("\n  mean |spread_ppm| = %.5f pts/min; at ~30 minutes that is %.3f points per game."
      % (T["spread_ppm"].abs().mean(), 30.0 * T["spread_ppm"].abs().mean()))
info["mean_abs_ppm_spread_points_per_30min"] = float(30.0 * T["spread_ppm"].abs().mean())

with open(os.path.join(OUT, "_s04.json"), "w", encoding="utf-8") as fh:
    json.dump(info, fh, indent=2, default=str)
print("\nwrote s04_volume_offset.csv, _s04.json")
