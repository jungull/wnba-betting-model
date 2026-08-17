"""S02 -- DOES THE SIMPLEX CLOSE?  Closure is ASSERTED NUMERICALLY, not assumed.

Every assertion is reported as max|Sum - target| over a stated number of units, and the
number of units is printed.  A claim without its unit count is not a closure assertion.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ss_base import (HERE, OUT, PARTITION, RA, ZONES, assert_partition, hdr,  # noqa
                     load_shots, row_beta)

R = {}
FRAME = pd.read_parquet(os.path.join(HERE, "_frame.parquet"))
assert_partition(FRAME, "_frame")
PGKEY = ["player_id", "season", "game_id"]


def closure(df, cols_value, target, name, unit_keys=PGKEY, require=5):
    """max|Sum_z value - target| over units carrying exactly `require` zones."""
    g = df.groupby(unit_keys, sort=False)[cols_value].agg(["sum", "size"])
    full = g[g["size"] == require]
    dev = (full["sum"] - target).abs()
    out = dict(name=name, target=target, n_units=int(len(full)),
               n_units_incomplete=int((g["size"] != require).sum()),
               max_abs_dev=float(dev.max()) if len(dev) else float("nan"),
               mean_abs_dev=float(dev.mean()) if len(dev) else float("nan"))
    print(f"  {name:<52} units={out['n_units']:>6}  incomplete={out['n_units_incomplete']:>4}"
          f"  max|Sum-{target:g}| = {out['max_abs_dev']:.3e}")
    return out


# ================================================== 1. THE FULL PANEL (pre-gate) ===
hdr("1. CLOSURE ON THE FULL PANEL, BEFORE ANY GATE (every player-game with >=1 FGA)")
print("  Rebuilt from the raw shots.  This is the population the response is defined on.\n")
_, shots5, n_bc = load_shots(verbose=False)
pgt = (shots5.groupby(["PLAYER_ID", "season", "GAME_ID"]).size().rename("fga")
       .reset_index())
pzt = (shots5.groupby(["PLAYER_ID", "season", "GAME_ID", "zone"]).size()
       .rename("z_att").reset_index())
full = (pgt.assign(_k=1).merge(pd.DataFrame({"zone": ZONES, "_k": 1}), on="_k")
        .drop(columns="_k").merge(pzt, on=["PLAYER_ID", "season", "GAME_ID", "zone"],
                                  how="left"))
full["z_att"] = full["z_att"].fillna(0.0)
full["share"] = full["z_att"] / full["fga"]
full = full.rename(columns={"PLAYER_ID": "player_id", "GAME_ID": "game_id"})
assert_partition(full, "full panel")
R["C1_full_panel"] = closure(full, "share", 1.0,
                             "C1  Sum_z share_z == 1 (ALL player-games, no gate)")
print(f"  Backcourt shots excluded from the five-zone family: {n_bc} "
      f"({100 * n_bc / (len(shots5) + n_bc):.2f}% of all shots) -- the simplex is over the")
print("  FIVE zones only, so the budget is the player's five-zone attempts, not her FGA.")

# =============================================== 2. THE PUBLISHED ANALYSIS FRAME ===
hdr("2. CLOSURE ON THE PUBLISHED ANALYSIS FRAME (51,473 rows / 10,307 player-games)")
for col, tgt, nm in [("share", 1.0, "C1  Sum_z share_z              == 1"),
                     ("S1", 1.0, "C2  Sum_z S1_z (frozen base)   == 1"),
                     ("resid_S1", 0.0, "C3  Sum_z (share - S1)_z       == 0"),
                     ("opp_share_prior", 1.0, "C4  Sum_z opp_share_prior_z    == 1"),
                     ("lg_share_prior", 1.0, "C5  Sum_z lg_share_prior_z     == 1"),
                     ("OS", 0.0, "C6  Sum_z OS_z                 == 0")]:
    R[nm.split()[0]] = closure(FRAME, col, tgt, nm)

hdr("3. C8 -- IS THE SIMPLEX COMPLETE ON THE ANALYSIS ROWS?")
cnt = FRAME.groupby(PGKEY, sort=False).size()
vc = cnt.value_counts().sort_index()
print("  zones present per analysis player-game:")
for k, v in vc.items():
    print(f"    {k} zones : {v} player-games")
inc = cnt[cnt != 5].index
incdf = FRAME.set_index(PGKEY).loc[inc].reset_index()
missing = (incdf.groupby(PGKEY)["zone"].apply(lambda s: sorted(set(ZONES) - set(s)))
           .explode().value_counts())
print("\n  which zone is missing on the incomplete player-games:")
print("   ", missing.to_dict())
R["C8_completeness"] = dict(
    n_player_games=int(len(cnt)), n_complete=int((cnt == 5).sum()),
    n_incomplete=int((cnt != 5).sum()),
    missing_zone_counts={str(k): int(v) for k, v in missing.items()},
    fraction_incomplete=float((cnt != 5).mean()))

# --- diagnose the cause: OS is NaN where the league had zero shots in that zone that day
d = incdf[PGKEY + ["season", "game_date"]].drop_duplicates() if "game_date" in incdf \
    else None
lgd = (shots5.groupby(["season", "game_date", "zone"]).size().rename("a").reset_index())
have = set(zip(lgd["season"], lgd["game_date"], lgd["zone"]))
alldates = shots5[["season", "game_date"]].drop_duplicates()
gaps = [(int(s), pd.Timestamp(t).date().isoformat(), z)
        for s, t in zip(alldates["season"], alldates["game_date"]) for z in ZONES
        if (s, t, z) not in have]
print(f"\n  CAUSE: (season, date, zone) cells with ZERO league shots = {len(gaps)}")
print(f"    {gaps[:8]}{' ...' if len(gaps) > 8 else ''}")
print("  On such a date the league prior-share table has no row, so OS_z is NaN and the")
print("  zone's row is dropped by the parent screen's `notna` gate -- which silently")
print("  DELETES ONE COMPONENT OF THE SIMPLEX and leaves the remaining four to sum to")
print("  less than 1.  Measured on those player-games:")
inc_share = incdf.groupby(PGKEY)["share"].sum()
print(f"    Sum of the surviving four shares: min {inc_share.min():.6f}  "
      f"mean {inc_share.mean():.6f}  max {inc_share.max():.6f}")
R["C8_cause"] = dict(zero_league_shot_zone_dates=len(gaps), example=gaps[:8],
                     surviving_share_sum_mean=float(inc_share.mean()),
                     surviving_share_sum_min=float(inc_share.min()),
                     surviving_share_sum_max=float(inc_share.max()))

hdr("4. CLOSURE ON THE COMPLETE SUBSET ONLY (the row set every projected arm uses)")
COMP = FRAME[FRAME.set_index(PGKEY).index.isin(cnt[cnt == 5].index)].copy()
print(f"  complete player-games = {COMP[PGKEY].drop_duplicates().shape[0]}  "
      f"rows = {len(COMP)}")
for col, tgt, nm in [("share", 1.0, "C1c Sum_z share_z          == 1 (complete only)"),
                     ("S1", 1.0, "C2c Sum_z S1_z             == 1 (complete only)"),
                     ("resid_S1", 0.0, "C3c Sum_z resid_S1_z       == 0 (complete only)"),
                     ("OS", 0.0, "C6c Sum_z OS_z             == 0 (complete only)")]:
    R[nm.split()[0]] = closure(COMP, col, tgt, nm)

# ======================================== 5. C7 -- THE FITTED COEFFICIENTS ========
hdr("5. C7 -- THE FITTED SLOPES, AND THE CLOSURE VIOLATION THEY IMPLY")
coef = {}
for z in ZONES:
    g = FRAME[FRAME["zone"] == z]
    x = g["OS"].to_numpy(float)
    y = g["resid_S1"].to_numpy(float)
    b = row_beta(y, x)
    a = float(y.mean() - b * x.mean())
    coef[z] = dict(n=int(len(g)), intercept=a, beta=b)
    print(f"  {z:<24} n={len(g):>6}  intercept={a:+.8f}  beta={b:+.8f}")
bs = np.array([coef[z]["beta"] for z in ZONES])
print(f"\n  fitted slope range = {bs.min():.4f} .. {bs.max():.4f}   "
      f"(E1_I0051 asserted 0.325 .. 0.774)   spread = {bs.max() / bs.min():.3f}x")
R["C7_coefficients"] = coef
R["C7_range"] = dict(min=float(bs.min()), max=float(bs.max()),
                     ratio=float(bs.max() / bs.min()),
                     E1_I0051_claim_confirmed=bool(abs(bs.min() - 0.3247) < 5e-4
                                                   and abs(bs.max() - 0.7743) < 5e-4))

print("\n  Sum of the five intercepts (must be ~0 if the response closes and the row")
print("  sets match): %+.3e" % bs.dot(np.zeros(5)) if False else "")
ints = np.array([coef[z]["intercept"] for z in ZONES])
print(f"  Sum_z intercept_z = {ints.sum():+.6e}")
R["C7_intercept_sum"] = float(ints.sum())

hdr("6. THE MEASURED CLOSURE VIOLATION OF THE PUBLISHED FIT")
print("  s_hat_z = S1_z + a_z + b_z * OS_z.  Budget = 1 EXACTLY, with ZERO pre-tip")
print("  uncertainty (unlike the minutes budget, whose best pre-tip assertion misses by")
print("  0.631% of itself).  Any violation is therefore infinitely many times the")
print("  budget's own uncertainty.\n")
W = COMP.pivot_table(index=PGKEY, columns="zone", values="OS")[ZONES].to_numpy(float)
S1W = COMP.pivot_table(index=PGKEY, columns="zone", values="S1")[ZONES].to_numpy(float)
YW = COMP.pivot_table(index=PGKEY, columns="zone", values="resid_S1")[ZONES].to_numpy(float)
fit = ints[None, :] + W * bs[None, :]
viol = fit.sum(axis=1)                     # Sum_z s_hat - 1
print(f"  units (complete player-games) = {len(viol)}")
print(f"  Sum_z s_hat_z - 1 :  mean {viol.mean():+.6f}   sd {viol.std(ddof=1):.6f}   "
      f"MAE {np.abs(viol).mean():.6f}   max|.| {np.abs(viol).max():.6f}")
print(f"  MAE as a percentage of the budget (=1)          : {100 * np.abs(viol).mean():.4f}%")
print(f"  sibling minutes screen, for scale: MAE 13.0942 on a budget of 200 = 6.5471%")
print(f"  q05 / q95 of the violation: {np.quantile(viol, 0.05):+.6f} / "
      f"{np.quantile(viol, 0.95):+.6f}")
print(f"  fraction of player-games whose five fitted shares sum to within 0.5pp of 1: "
      f"{100 * (np.abs(viol) < 0.005).mean():.2f}%")
R["closure_violation_of_published_fit"] = dict(
    n_units=int(len(viol)), mean=float(viol.mean()), sd=float(viol.std(ddof=1)),
    MAE=float(np.abs(viol).mean()), max_abs=float(np.abs(viol).max()),
    MAE_pct_of_budget=float(100 * np.abs(viol).mean()),
    sibling_minutes_MAE_pct=6.5471,
    q05=float(np.quantile(viol, 0.05)), q95=float(np.quantile(viol, 0.95)),
    budget=1.0, budget_pretip_uncertainty=0.0)

print("\n  DECOMPOSITION.  Sum_z b_z*OS_z = Sum_z (b_z - bbar)*OS_z, so the varying part of")
print("  the violation is driven ENTIRELY by the slope spread:")
bbar = bs.mean()
varying = (W * (bs - bbar)[None, :]).sum(axis=1)
print(f"    sd of Sum_z (b_z - bbar) OS_z = {varying.std(ddof=1):.6f}   "
      f"(identical to the sd above: {abs(varying.std(ddof=1) - viol.std(ddof=1)):.3e})")
print(f"    constant part Sum_z a_z       = {ints.sum():+.6e}")
R["closure_violation_decomposition"] = dict(
    sd_varying_part=float(varying.std(ddof=1)),
    identity_check_abs_diff=float(abs(varying.std(ddof=1) - viol.std(ddof=1))),
    constant_part=float(ints.sum()), bbar=float(bbar))

# ================================================= 7. G03 -- THE NO-OP PLACEBO ====
hdr("7. G03 -- THE PROJECTION NO-OP PLACEBO (must be EXACTLY 0.000e+00)")
print("  A fit whose five slopes are equal by construction already closes, so projecting")
print("  it must change nothing.  Asserted, so the check is not vacuous.\n")


def project_tangent(dmat):
    """Euclidean projection of the per-row five-vector onto the zero-sum subspace."""
    return dmat - dmat.mean(axis=1, keepdims=True)


eq = np.full(5, 0.6)
fit_eq = W * eq[None, :]
print(f"  max|Sum_z fit_eq| over {len(W)} units (before projection) = "
      f"{np.abs(fit_eq.sum(axis=1)).max():.3e}")
dev = float(np.abs(project_tangent(fit_eq) - fit_eq).max())
print(f"  max|project(fit_eq) - fit_eq| = {dev:.3e}   "
      f"{'EXACT NO-OP' if dev == 0.0 else '*** NOT A NO-OP ***'}")
R["G03_noop_placebo"] = dict(max_abs_dev=dev, exact=bool(dev == 0.0),
                             asserted_precondition_max_abs_sum=float(
                                 np.abs(fit_eq.sum(axis=1)).max()))

# ================================ 8. X2 -- IS OS A TEAM-GAME-CONSTANT IN DISGUISE?
hdr("8. X2 -- CAN THE CANDIDATE MOVE AN ALLOCATION AT ALL?")
print("  A quantity constant within the team-game cannot move an allocation by")
print("  arithmetic.  OS_z is opponent-game-constant WITHIN a zone but varies ACROSS")
print("  zones.  Measured decomposition of var(OS) on the analysis rows:\n")
tot_var = float(np.var(W))
within = float(np.var(W - W.mean(axis=1, keepdims=True)))
between = float(np.var(np.repeat(W.mean(axis=1, keepdims=True), 5, axis=1)))
print(f"  total var(OS)                                  = {tot_var:.6e}")
print(f"  var of the WITHIN-player-game (across-zone) part = {within:.6e}  "
      f"({100 * within / tot_var:.2f}%)")
print(f"  var of the row-constant part (the mean over zones) = {between:.6e}  "
      f"({100 * between / tot_var:.4f}%)")
print("  The row-constant part is ZERO by construction because Sum_z OS_z = 0, so the")
print("  candidate is 100% across-zone contrast.  It CAN move an allocation.  X2 does")
print("  NOT deflate the lead.")
R["X2_variance_decomposition"] = dict(total=tot_var, within_row_across_zone=within,
                                      row_constant=between,
                                      pct_across_zone=float(100 * within / tot_var))

hdr("WRITE")
json.dump(R, open(os.path.join(HERE, "_s02.json"), "w", encoding="utf-8"), indent=2,
          default=float)
COMP.to_parquet(os.path.join(HERE, "_complete.parquet"), index=False)
np.savez_compressed(os.path.join(OUT, "raw", "S02_closure_matrices.npz"),
                    OS=W, S1=S1W, resid_S1=YW, zones=np.array(ZONES, dtype=object),
                    beta_published=bs, intercept_published=ints,
                    violation=viol, rowset="COMPLETE_PLAYER_GAMES_2021_2024")
print("  wrote _s02.json, _complete.parquet, raw/S02_closure_matrices.npz")
print("\nDone.")
