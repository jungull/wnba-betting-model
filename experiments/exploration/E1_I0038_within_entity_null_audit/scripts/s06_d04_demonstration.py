"""S06 -- THE D-04 TEST AND THE N_CYCLIC DEMONSTRATION.  PREREG section 6.

R1  ORIGINAL D108 protocol on N_CYCLIC          -> must CERTIFY  (power >= 0.80 @ 0.002057)
R2  MECHANISM: does shuffling residuals destroy the response's between-entity structure?
R3  AMENDED protocol on N_CYCLIC                -> must VOID
R4  AMENDED protocol on N_PSWAP (positive ctrl) -> must PASS
R5  AMENDED protocol on N_CYCLIC vs a WITHIN-varying candidate (specificity ctrl) -> must PASS

The demonstration succeeds ONLY if all five land as preregistered.  Anything less is reported
as partial or failed.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab38 import (BEST_LIVE, BaseFit, DELTAS_D04, EXP, FLOOR_1CELL, FLOOR_132, NREP_D04, OUT,
                   R_DRAWS, SEED, amended_injection, assert_partition, components, hdr, mde80,
                   null_draws, original_injection, perm_p, r2_twofit, resolve,
                   var_share_between)

HEADLINE_SEASONS = (2022, 2023, 2024)
TARGET, CAND = "y_oreb", "R08_player_ra_share"
D097_DR2 = 0.0064880
D097_N = 13784
D097_CYCLIC_NULLMEAN = 0.0078802     # anchor A2 -- from D097's OWN on-disk draws

# ============================================================ GATE: two anchors
hdr("GATE -- ANCHOR A2: D097's OWN RECORDED CYCLIC NULL MEAN, READ FROM ITS OWN BYTES")
z24 = np.load(os.path.join(EXP, "E0_I0024_reb_ast_characterisation", "permutation_draws.npz"))
key = "POOLED|y_oreb|B_COMPLETE|R08_player_ra_share"
d097_draws = z24[key]
a2 = float(np.mean(d097_draws))
print(f"  key                         = {key}")
print(f"  draws                       = {d097_draws.shape[0]}")
print(f"  mean of D097's own draws    = {a2:.10f}")
print(f"  PREREG A2 target            = {D097_CYCLIC_NULLMEAN:.10f}")
print(f"  |diff|                      = {abs(a2 - D097_CYCLIC_NULLMEAN):.3e}")
print(f"  D097's recorded observed dR2= {D097_DR2:.10f}")
print(f"  null_mean > observed ?        {a2 > D097_DR2}   "
      f"(ratio {a2 / D097_DR2:.4f}x)")
assert abs(a2 - D097_CYCLIC_NULLMEAN) < 5e-7, "ANCHOR A2 FAILED -- HALT"
assert a2 > D097_DR2, "A2's ordering claim failed -- HALT"
print("  >>> A2 REPRODUCED.  The flag was sitting in D097's own permutation_draws.npz all along.")

hdr("GATE -- ANCHOR A1: reproduce D097's dR2 = 0.006488 on exactly 13,784 rows")
F = pd.read_parquet(os.path.join(EXP, "E0_I0024_reb_ast_characterisation",
                                 "screen_frame.parquet"))
F["game_date"] = pd.to_datetime(F["game_date"])
assert_partition(F, "E0_I0024/screen_frame")
F = F[F["season"].isin(HEADLINE_SEASONS)].reset_index(drop=True)
BASE = resolve(F, ["ref_mean__y_oreb", "ref_ewma__y_oreb", "ref_trail5__y_oreb",
                   "ref_rate_x_min__y_oreb", "ref_mean_minutes", "ref_trail5_minutes",
                   "ref_pct__y_oreb", "ref_mean_pace", "n_prior", "is_home"],
               10, "B_COMPLETE(y_oreb)")
d = F.dropna(subset=[TARGET, CAND] + BASE).reset_index(drop=True)
print(f"  rows = {len(d)}  (D097 recorded {D097_N})")
assert len(d) == D097_N, "ROW SET MISMATCH -- HALT"
for c in BASE:
    assert int(d[c].notna().sum()) == len(d), f"A_REF_COVERAGE FAILED for {c}"
print(f"  A_REF_COVERAGE ok: all {len(BASE)} base columns cover all {len(d)} rows (D087 guard)")

y = d[TARGET].to_numpy(float)
X = d[BASE].to_numpy(float)
x = d[CAND].to_numpy(float)
bf = BaseFit(y, X)
obs = bf.dr2(x)
lit = r2_twofit(y, np.column_stack([X, x])) - r2_twofit(y, X)
print(f"  fast dR2 (Frisch-Waugh) = {obs:.10f}")
print(f"  literal two-fit dR2     = {lit:.10f}    |diff| = {abs(obs - lit):.3e}")
print(f"  D097 recorded           = {D097_DR2:.10f}    |diff| = {abs(obs - D097_DR2):.3e}")
assert abs(obs - lit) < 1e-12 and abs(obs - D097_DR2) < 5e-7, "ANCHOR A1 FAILED -- HALT"
print("  >>> A1 REPRODUCED.  Both gates passed; the demonstration may proceed.")

plseas = (d["player_id"].astype(str) + "_" + d["season"].astype(str)).to_numpy()
pl = d["player_id"].to_numpy()
seas = d["season"].to_numpy()
gdate = d["game_date"].to_numpy()

# ============================================================ nulls
hdr("BUILD THE TWO NULLS (R = 601 draws each)")
NULLS = {}
for name, (kind, grp, blk) in {"N_CYCLIC": ("N_CYCLIC", plseas, None),
                               "N_PSWAP": ("N_SWAP", plseas, seas)}.items():
    rr = np.random.default_rng(SEED + abs(hash(name)) % 100000)
    Xp = null_draws(kind, x, rr, groups=grp, order_key=gdate, blocks=blk, R=R_DRAWS)
    EX = bf.resid_X(Xp)
    den = np.einsum("ij,ij->j", EX, EX)
    draws = ((bf.e @ EX) ** 2 / den) / bf.sst
    NULLS[name] = dict(EX=EX, draws=draws, p=perm_p(obs, draws),
                       null_mean=float(draws.mean()), null_sd=float(draws.std(ddof=1)))
    print(f"  {name:9s} p={NULLS[name]['p']:.6f}  null_mean={NULLS[name]['null_mean']:.4e}  "
          f"null_sd={NULLS[name]['null_sd']:.4e}  "
          f"flag_null_mean>obs={NULLS[name]['null_mean'] > obs}")
np.savez_compressed(os.path.join(OUT, "nulls", "d04_r08_null_draws.npz"),
                    N_CYCLIC=NULLS["N_CYCLIC"]["draws"], N_PSWAP=NULLS["N_PSWAP"]["draws"],
                    observed_dr2=np.array([obs]),
                    d097_recorded_cyclic_draws=d097_draws)

results, inj_rows = [], []

# ============================================================ R1 -- ORIGINAL protocol
hdr("R1 -- D108's ORIGINAL INJECTION PROTOCOL ON N_CYCLIC (must CERTIFY for D-04 to hold)")
pw1 = original_injection(bf, x, NULLS["N_CYCLIC"]["EX"],
                         np.random.default_rng(SEED + 11), DELTAS_D04, NREP_D04)
print(pw1.to_string(index=False))
p1 = float(pw1.loc[np.isclose(pw1["delta"], BEST_LIVE), "power"].iloc[0])
t1 = float(pw1.loc[np.isclose(pw1["delta"], 0.0), "power"].iloc[0])
m1 = mde80(pw1)
r1_verdict = "CERTIFIED" if (p1 >= 0.80 and t1 <= 0.10) else "REJECTED"
print(f"\n  power @ {BEST_LIVE} = {p1:.2f}   type-I @ 0 = {t1:.2f}   "
      f"MDE80 (injection-verified) = {m1:.4e}")
print(f"  >>> ORIGINAL PROTOCOL VERDICT ON N_CYCLIC: {r1_verdict}")
print(f"      (E1_I0036 reported power 0.95 at 100 replicates; this is {NREP_D04} replicates)")
inj_rows += [dict(run="R1", protocol="ORIGINAL", null="N_CYCLIC", planted_along="FULL", **r)
             for r in pw1.to_dict("records")]

# ============================================================ R2 -- THE MECHANISM
hdr("R2 -- THE MECHANISM: DOES SHUFFLING RESIDUALS DESTROY THE RESPONSE'S ENTITY STRUCTURE?")
print("  D-04's stated cause: the synthetic response y0 = fitted + shuffle(resid) loses the")
print("  BETWEEN-ENTITY structure that N_CYCLIC fails to destroy in the CARRIER, so the test")
print("  and the real candidate exercise different structures.  Measured directly:")
fitted = bf.y - bf.e
rng2 = np.random.default_rng(SEED + 23)
vs_real = var_share_between(y, plseas)
vs_fit = var_share_between(fitted, plseas)
vs_syn = [var_share_between(fitted + bf.e[rng2.permutation(bf.n)], plseas) for _ in range(60)]
vs_syn_m, vs_syn_s = float(np.mean(vs_syn)), float(np.std(vs_syn, ddof=1))
# and the same for the residual itself, which is what carries the association
vs_resid_real = var_share_between(bf.e, plseas)
vs_resid_syn = [var_share_between(bf.e[rng2.permutation(bf.n)], plseas) for _ in range(60)]
print(f"  var share BETWEEN player-season, REAL response y            = {vs_real:.4f}")
print(f"  var share BETWEEN player-season, base FITTED values         = {vs_fit:.4f}")
print(f"  var share BETWEEN player-season, SYNTHETIC y0 (60 draws)    = "
      f"{vs_syn_m:.4f} +/- {vs_syn_s:.4f}")
print(f"  var share BETWEEN player-season, REAL residual e            = {vs_resid_real:.4f}")
print(f"  var share BETWEEN player-season, SHUFFLED residual (60)     = "
      f"{float(np.mean(vs_resid_syn)):.4f} +/- {float(np.std(vs_resid_syn, ddof=1)):.4f}")
collapse = vs_resid_real / float(np.mean(vs_resid_syn))
print(f"\n  >>> the RESIDUAL's between-entity share collapses by {collapse:.2f}x under the "
      f"shuffle.")
print("      That residual is the ONLY part of the synthetic response a planted effect has to")
print("      compete against, so the original protocol hands N_CYCLIC an easier problem than")
print("      the real one.  D-04's stated mechanism is CONFIRMED / REFUTED below.")
r2_confirmed = bool(collapse > 1.5)
print(f"      MECHANISM CONFIRMED: {r2_confirmed}")

# ============================================================ R3 / R4 -- AMENDED protocol
hdr("R3 / R4 -- THE AMENDED PROTOCOL (PREREG 6.4), COMPONENT-WISE")
xb, xw = components(x, plseas)
print(f"  carrier decomposition at player_season:")
print(f"    var share BETWEEN            = {var_share_between(x, plseas):.4f}")
print(f"    dR2 from BETWEEN component   = {bf.dr2(xb):.6e}")
print(f"    dR2 from WITHIN component    = {bf.dr2(xw):.6e}")
for name in ["N_CYCLIC", "N_PSWAP"]:
    print(f"\n---- AMENDED on {name} ----")
    v, pw = amended_injection(bf, x, NULLS[name]["EX"], plseas,
                              np.random.default_rng(SEED + 31), DELTAS_D04, NREP_D04)
    print(pw.pivot_table(index="delta", columns="planted_along", values="power").to_string())
    for k in ["w_between", "dominant_component", "power_full_at_best_live",
              "power_dominant_at_best_live", "type_I_at_zero",
              "mde80_injection_verified_full", "mde80_injection_verified_dominant",
              "ORIGINAL_VERDICT", "AMENDED_VERDICT"]:
        print(f"    {k:36s} = {v[k]}")
    print(f"    {'FLAG_NULL_MEAN_GT_OBSERVED':36s} = "
          f"{NULLS[name]['null_mean'] > obs}  "
          f"(null_mean {NULLS[name]['null_mean']:.4e} vs observed {obs:.4e})")
    results.append(dict(run=("R3" if name == "N_CYCLIC" else "R4"), cell="R08->y_oreb",
                        null=name, n=len(d), observed=obs, p=NULLS[name]["p"],
                        null_mean=NULLS[name]["null_mean"], null_sd=NULLS[name]["null_sd"],
                        flag_null_mean_gt_observed=bool(NULLS[name]["null_mean"] > obs), **v))
    inj_rows += [dict(run=("R3" if name == "N_CYCLIC" else "R4"), protocol="AMENDED",
                      null=name, **r) for r in pw.to_dict("records")]

# ============================================================ R5 -- SPECIFICITY CONTROL
hdr("R5 -- SPECIFICITY CONTROL: THE AMENDED PROTOCOL MUST NOT REJECT A VALID CYCLIC NULL")
print("  Select, ON THE REGRESSOR ALONE and before any response is touched, the D097 candidate")
print("  with the LOWEST between-player-season variance share on these exact 13,784 rows.")
CANDIDATE_COLS = [c for c in F.columns
                  if c.split("_")[0] in {"R01", "R02", "R03", "R04", "R05", "R06", "R07",
                                         "R08", "R09", "R10", "A01", "A02", "A03", "A04",
                                         "A05", "G01"}]
print(f"  D097 candidate columns present in the frame: {len(CANDIDATE_COLS)}")
shares = {}
for c in CANDIDATE_COLS:
    xx = d[c].to_numpy(float)
    if np.isfinite(xx).all() and np.std(xx) > 0:
        shares[c] = var_share_between(xx, plseas)
sh = pd.Series(shares).sort_values()
print("\n  between-player-season variance share, every usable candidate on this row set:")
print(sh.to_string())
WCAND = sh.index[0]
print(f"\n  >>> WITHIN-VARYING CONTROL CANDIDATE = {WCAND}  "
      f"(between-share {sh.iloc[0]:.4f}, i.e. {1 - sh.iloc[0]:.1%} of its variance is WITHIN "
      f"player-season)")
xc = d[WCAND].to_numpy(float)
obs_c = bf.dr2(xc)
rr = np.random.default_rng(SEED + 77)
Xpc = null_draws("N_CYCLIC", xc, rr, groups=plseas, order_key=gdate, R=R_DRAWS)
EXc = bf.resid_X(Xpc)
denc = np.einsum("ij,ij->j", EXc, EXc)
drc = ((bf.e @ EXc) ** 2 / denc) / bf.sst
print(f"  observed dR2 = {obs_c:.6e}   N_CYCLIC p = {perm_p(obs_c, drc):.6f}   "
      f"null_mean = {drc.mean():.4e}  flag={drc.mean() > obs_c}")
v5, pw5 = amended_injection(bf, xc, EXc, plseas, np.random.default_rng(SEED + 79),
                            DELTAS_D04, NREP_D04)
print(pw5.pivot_table(index="delta", columns="planted_along", values="power").to_string())
for k in ["w_between", "dominant_component", "power_full_at_best_live",
          "power_dominant_at_best_live", "type_I_at_zero", "ORIGINAL_VERDICT",
          "AMENDED_VERDICT"]:
    print(f"    {k:36s} = {v5[k]}")
results.append(dict(run="R5", cell=f"{WCAND}->y_oreb", null="N_CYCLIC", n=len(d),
                    observed=obs_c, p=perm_p(obs_c, drc), null_mean=float(drc.mean()),
                    null_sd=float(drc.std(ddof=1)),
                    flag_null_mean_gt_observed=bool(drc.mean() > obs_c), **v5))
inj_rows += [dict(run="R5", protocol="AMENDED", null="N_CYCLIC", **r)
             for r in pw5.to_dict("records")]
np.savez_compressed(os.path.join(OUT, "nulls", "d04_r5_control_null_draws.npz"),
                    N_CYCLIC_control=drc, observed_dr2=np.array([obs_c]))

# ============================================================ THE SCORECARD
hdr("THE PREREGISTERED SCORECARD (PREREG 6.3) -- ALL FIVE MUST LAND")
R = pd.DataFrame(results)
r3 = R[R["run"] == "R3"].iloc[0]
r4 = R[R["run"] == "R4"].iloc[0]
r5 = R[R["run"] == "R5"].iloc[0]
checks = [
    ("R1  ORIGINAL certifies N_CYCLIC", r1_verdict == "CERTIFIED",
     f"power {p1:.2f} @ {BEST_LIVE}, type-I {t1:.2f}"),
    ("R2  shuffle destroys response entity structure", r2_confirmed,
     f"residual between-share collapses {collapse:.2f}x"),
    ("R3  AMENDED voids N_CYCLIC", r3["AMENDED_VERDICT"] == "VOID_FOR_THIS_CANDIDATE",
     f"power on dominant ({r3['dominant_component']}) = "
     f"{r3['power_dominant_at_best_live']:.2f}"),
    ("R4  AMENDED passes N_PSWAP", r4["AMENDED_VERDICT"] == "USABLE",
     f"power on dominant = {r4['power_dominant_at_best_live']:.2f}, "
     f"type-I {r4['type_I_at_zero']:.2f}"),
    ("R5  AMENDED passes N_CYCLIC on a within-varying candidate",
     r5["AMENDED_VERDICT"] == "USABLE",
     f"{WCAND}: dominant={r5['dominant_component']}, "
     f"power={r5['power_dominant_at_best_live']:.2f}"),
]
for label, ok, detail in checks:
    print(f"  [{'PASS' if ok else 'FAIL'}]  {label:56s}  {detail}")
ALL = all(ok for _, ok, _ in checks)
print(f"\n  >>> DEMONSTRATION: {'SUCCEEDED' if ALL else 'PARTIAL / FAILED'} "
      f"({sum(ok for _, ok, _ in checks)}/5 preregistered checks landed)")

R.to_csv(os.path.join(OUT, "D04_PROTOCOL_RESULTS.csv"), index=False)
pd.DataFrame(inj_rows).to_csv(os.path.join(OUT, "D04_INJECTION_POWER.csv"), index=False)
pd.DataFrame([dict(check=a, passed=b, detail=c) for a, b, c in checks]).to_csv(
    os.path.join(OUT, "D04_SCORECARD.csv"), index=False)
json.dump(dict(
    anchor_A1_dr2=obs, anchor_A2_d097_cyclic_null_mean=a2,
    R1_original_verdict=r1_verdict, R1_power_at_best_live=p1, R1_typeI=t1, R1_mde80=m1,
    R2_mechanism_confirmed=r2_confirmed,
    R2_resid_between_share_real=vs_resid_real,
    R2_resid_between_share_shuffled=float(np.mean(vs_resid_syn)),
    R2_collapse_factor=collapse,
    R2_response_between_share_real=vs_real, R2_response_between_share_synth=vs_syn_m,
    R3_amended_verdict=r3["AMENDED_VERDICT"],
    R3_power_dominant=float(r3["power_dominant_at_best_live"]),
    R4_amended_verdict=r4["AMENDED_VERDICT"],
    R5_control_candidate=WCAND, R5_between_share=float(sh.iloc[0]),
    R5_amended_verdict=r5["AMENDED_VERDICT"],
    demonstration_succeeded=ALL, checks_passed=int(sum(ok for _, ok, _ in checks)),
    nrep=NREP_D04, R_draws=R_DRAWS, deltas=DELTAS_D04, seed=SEED,
), open(os.path.join(OUT, "scripts", "_s06.json"), "w"), indent=1)
print("\nwrote D04_PROTOCOL_RESULTS.csv, D04_INJECTION_POWER.csv, D04_SCORECARD.csv, "
      "nulls/d04_*.npz")
