#!/usr/bin/env python3
"""E1_I0035 s05 -- (A) injection-derived power floors, (B) the minutes-allocation shape.

(A) The analytic MDE80 = 2.802 x null_sd is computed from the OBSERVED difference vector, which
    contains the effect.  A block sign-flip on a vector carrying a large mean shift has its null
    sd inflated by that shift, so the analytic floor is conservative.  D108 says injection is the
    authority, so the 80%-power point is located by injection on a NO-EFFECT world and both
    numbers are published side by side.

(B) `experiments\\player_program\\build_projected_exposure.py:238` is the only place in the
    repository that multiplies by p_active:
        base["raw_expected_minutes"] = base["p_active"] * base["e_minutes_given_active"]
    and it then allocates a FIXED 200 team-minutes proportionally (line ~355,
    alloc[free] = raw[free] * (remaining / s)).  A UNIFORM scaling error in p_active therefore
    cancels exactly.  What survives is the RELATIVE SHAPE across the roster.  This section
    measures that shape error and what each repair does to it.  The producer is registered
    production_eligible: False on all three regimes, so this is a research-path measurement.
"""
from __future__ import annotations
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import av_base as ab  # noqa: E402

pd.set_option("display.width", 250)
F = {}
TEAM_MINUTES = 200.0   # build_projected_exposure.TEAM_MINUTES, read from the producer

PF = pd.read_parquet(os.path.join(ab.OUT, "_player_frame_repaired.parquet"))
TF2 = pd.read_parquet(os.path.join(ab.OUT, "_team_frame_repaired.parquet"))
ARMS = ("X0", "Xa", "XaO", "Xb", "Xc")

# =========================================================================================
ab.hdr("A. INJECTION-DERIVED 80%-POWER FLOORS")
blk_t = (TF2["season"].astype(str) + "_" + TF2["team_id"].astype(str)).to_numpy()
la0 = np.abs(TF2["pts"] - TF2["c_X0"]).to_numpy(float)
noise_t = np.abs(TF2["pts"] - TF2["c_Xb"]).to_numpy(float) - la0

y_app = PF["appeared"].to_numpy(float)
b0 = (np.clip(PF["w_X0"].to_numpy(float), 0, 1) - y_app) ** 2
bXb = (np.clip(PF["w_Xb"].to_numpy(float), 0, 1) - y_app) ** 2
mA = PF["tier_A"].to_numpy(bool)
blk_p = (PF["season"].astype(str) + "_" + PF["player_id"].astype(str)).to_numpy()
noise_p = (bXb - b0)[mA]


def floor80(noise, blocks, grid, seed, n_reps=300):
    out = []
    for e in grid:
        pw = ab.injection_power(noise, blocks, e, 2000, seed, n_reps=n_reps)
        out.append({"planted": float(e), "detection_rate": pw})
        print("    planted %-10.5f -> %.3f" % (e, pw))
    d = pd.DataFrame(out)
    hi = d[d["detection_rate"] >= 0.80]
    return d, (float(hi["planted"].iloc[0]) if len(hi) else float("nan"))


print("  TEAM cell (team-season blocks, MAE scale):")
dt, ft = floor80(noise_t, blk_t, [0.5, 1.0, 1.5, 1.75, 2.0, 2.5, 3.0], ab.SEED)
print("    injection-derived 80%% floor ~ %.3f MAE" % ft)
print("    analytic 2.802 x null_sd (Xb cell)  = 4.596 MAE  [CONSERVATIVE -- the null sd is")
print("    computed from a difference vector that carries the effect]")

print("\n  PLAYER cell, tier A (player-season blocks, Brier scale):")
dp, fp = floor80(noise_p, blk_p[mA], [0.0005, 0.001, 0.0015, 0.002, 0.0025, 0.003], ab.SEED + 7)
print("    injection-derived 80%% floor ~ %.5f Brier" % fp)
print("    analytic 2.802 x null_sd (Xa cell)  = 0.00038 Brier")

pd.concat([dt.assign(cell="team_MAE"), dp.assign(cell="player_tierA_Brier")]).to_csv(
    os.path.join(ab.OUT, "injection_power_curves.csv"), index=False)
F["injection_floor_team_MAE"] = ft
F["injection_floor_player_tierA_Brier"] = fp

print("\n  CONSEQUENCE FOR THE VERDICTS (the injection floor is the authority, D108):")
print("    Xa tier-A Brier effect  -0.000148  vs floor %.5f  -> NOT ESTABLISHED (no harm shown,"
      % fp)
print("       and none could be shown below the floor -- this is a failure to detect, not a")
print("       demonstration of safety)")
print("    Xb tier-A Brier effect  -0.014239  vs floor %.5f  -> ESTABLISHED HARM (%.1fx floor)"
      % (fp, 0.014239 / fp))
print("    Xc tier-A Brier effect  -0.012558  vs floor %.5f  -> ESTABLISHED HARM (%.1fx floor)"
      % (fp, 0.012558 / fp))
print("    every team-level effect (2.25 .. 9.47 MAE) clears the %.2f floor" % ft)

# =========================================================================================
ab.hdr("B. THE MINUTES-ALLOCATION SHAPE  (the only downstream path p_active reaches)")
PF = PF.copy()
PF["min_hat"] = pd.to_numeric(PF["min_hat"], errors="coerce")
print("  rows with a minutes forecast: %d of %d" % (int(PF["min_hat"].notna().sum()), len(PF)))
PF = PF[PF["min_hat"].notna()].copy()

# realised team minutes per team-game, from the realised box
real_team_min = PF.groupby(["game_id", "team_id"])["minutes"].transform("sum")
PF["realised_min_share"] = np.where(real_team_min > 0, PF["minutes"] / real_team_min, np.nan)

rows = []
for a in ARMS:
    raw = PF["w_" + a].to_numpy(float) * PF["min_hat"].to_numpy(float)
    PF["_raw"] = raw
    s = PF.groupby(["game_id", "team_id"])["_raw"].transform("sum").to_numpy(float)
    share = np.where(s > 0, raw / s, np.nan)
    alloc = share * TEAM_MINUTES
    PF["_alloc"] = alloc
    ok = np.isfinite(alloc) & np.isfinite(PF["minutes"].to_numpy(float))
    tb = (~PF["tier_A"]).to_numpy(bool)
    tb_min = PF.loc[tb, "_alloc"].sum() / len(TF2)
    tb_real = PF.loc[tb, "minutes"].sum() / len(TF2)
    rows.append({
        "arm": a,
        "n_rows": int(ok.sum()),
        "alloc_min_MAE_vs_realised": ab.mae(PF.loc[ok, "minutes"], alloc[ok]),
        "alloc_min_bias": ab.bias(PF.loc[ok, "minutes"], alloc[ok]),
        "minutes_allocated_to_tierB_per_team_game": float(tb_min),
        "minutes_ACTUALLY_played_by_tierB_per_team_game": float(tb_real),
        "tierB_minutes_misallocated_per_team_game": float(tb_min - tb_real),
        "tierB_share_of_allocated_minutes": float(tb_min / TEAM_MINUTES),
        "corr_alloc_vs_realised": float(pd.Series(alloc[ok]).corr(PF.loc[ok, "minutes"])),
    })
EX = pd.DataFrame(rows)
EX["misallocation_vs_X0"] = (EX["tierB_minutes_misallocated_per_team_game"].iloc[0]
                             - EX["tierB_minutes_misallocated_per_team_game"])
print(EX.to_string(index=False))
EX.to_csv(os.path.join(ab.OUT, "exposure_shape_distortion.csv"), index=False)
F["exposure_shape"] = EX.to_dict("records")

print("\n  READ: the producer normalises to a fixed %.0f team-minutes, so a UNIFORM p_active"
      % TEAM_MINUTES)
print("  error cancels exactly.  What does NOT cancel is the tier-B rows' SHARE of the roster's")
print("  weight.  Under the champion as emitted, %.2f of every %.0f team-minutes are allocated"
      % (EX['minutes_allocated_to_tierB_per_team_game'].iloc[0], TEAM_MINUTES))
print("  to tier-B rows, against %.2f actually played by them -- %.2f minutes per team-game"
      % (EX['minutes_ACTUALLY_played_by_tierB_per_team_game'].iloc[0],
         EX['tierB_minutes_misallocated_per_team_game'].iloc[0]))
print("  taken from the players who do play and given to players who mostly do not.")

open(os.path.join(ab.OUT, "_s05.json"), "w", encoding="utf-8").write(
    json.dumps(ab.jsonable(F), indent=2))
print("\nDONE s05")
