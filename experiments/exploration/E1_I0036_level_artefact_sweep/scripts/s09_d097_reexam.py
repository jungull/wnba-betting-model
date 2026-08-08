"""S09 -- THE D097 DEBT.  R08_player_ra_share -> y_oreb, killed by the within-player cyclic null.

Executes PREREG section 6, in the preregistered order:
  1. reproduce D097's dr2 = 0.006488 exactly (GATE)
  2. decompose R08's variance between/within player
  3. run N_ROW, N_CYCLIC, N_PSWAP and INJECT into every one of them
  4. declare the matched null
  5. verdict + MDE80
(step 6, the re-levelling half, is s11)
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab import (BaseFit, DELTAS, EXP, FLOOR_1CELL, OUT, R_DRAWS, SEED, assert_partition,
                 hdr, injection_power, mde80, null_draws, perm_p, r2_twofit, resolve,
                 var_share_between)

rng = np.random.default_rng(SEED)

HEADLINE_SEASONS = (2022, 2023, 2024)     # D097's own headline row set
TARGET = "y_oreb"
CAND = "R08_player_ra_share"
D097_DR2 = 0.0064880  # POOLED / B_COMPLETE, as recorded in upstream_signals.csv
D097_N = 13784

# --------------------------------------------------------------------------- frame
hdr("1. LOAD D097's OWN FRAME (re-examination must sit on D097's exact rows -- D101)")
F = pd.read_parquet(os.path.join(EXP, "E0_I0024_reb_ast_characterisation",
                                 "screen_frame.parquet"))
F["game_date"] = pd.to_datetime(F["game_date"])
assert_partition(F, "screen_frame")
F = F[F["season"].isin(HEADLINE_SEASONS)].reset_index(drop=True)
print(f"  headline frame {F.shape} (seasons {HEADLINE_SEASONS})")

# EXPLICIT allowlist -- B_COMPLETE for y_oreb, exactly as rb_base.BASE_COLS defines it
BASE = resolve(F, ["ref_mean__y_oreb", "ref_ewma__y_oreb", "ref_trail5__y_oreb",
                   "ref_rate_x_min__y_oreb", "ref_mean_minutes", "ref_trail5_minutes",
                   "ref_pct__y_oreb", "ref_mean_pace", "n_prior", "is_home"],
               10, "B_COMPLETE(y_oreb)")

d = F.dropna(subset=[TARGET, CAND] + BASE).reset_index(drop=True)
print(f"  analysis rows n = {len(d)}   (D097 recorded n = {D097_N})")
assert len(d) == D097_N, f"ROW SET MISMATCH: {len(d)} vs {D097_N}"

# D087 reference-incompleteness guard: every base column covers every analysis row
for c in BASE:
    cov = int(d[c].notna().sum())
    assert cov == len(d), f"A_REF_COVERAGE FAILED for {c}: {cov}/{len(d)}"
print(f"  A_REF_COVERAGE ok: all {len(BASE)} base columns cover all {len(d)} rows")

y = d[TARGET].to_numpy(float)
X = d[BASE].to_numpy(float)
x = d[CAND].to_numpy(float)
bf = BaseFit(y, X)

# --------------------------------------------------------------------------- 1. anchor
hdr("2. ANCHOR REPRODUCTION (GATE)")
fast = bf.dr2(x)
lit = r2_twofit(y, np.column_stack([X, x])) - r2_twofit(y, X)
print(f"  fast dR2 (Frisch-Waugh) = {fast:.10f}")
print(f"  literal two-fit dR2     = {lit:.10f}")
print(f"  D097 recorded dR2       = {D097_DR2:.10f}")
print(f"  |fast - literal|        = {abs(fast - lit):.3e}")
print(f"  |fast - D097|           = {abs(fast - D097_DR2):.3e}")
assert abs(fast - lit) < 1e-12, "fast/literal identity failed"
assert abs(fast - D097_DR2) < 5e-7, "ANCHOR REPRODUCTION FAILED -- halt per PREREG 7"
print("  >>> ANCHOR REPRODUCED. Gate passed.")

# --------------------------------------------------------------------------- ceiling
hdr("3. ARITHMETIC CEILING BEFORE FITTING (PREREG 5.5)")
ex = bf.resid_x(x)
beta = bf.beta(x)
sd_y = float(np.std(y, ddof=1))
sd_ex = float(np.std(ex, ddof=1))
ceiling = (beta * sd_ex / sd_y) ** 2
print(f"  beta={beta:.6f}  sd(resid carrier)={sd_ex:.6f}  sd(y)={sd_y:.6f}")
print(f"  CEILING (residualised form) = {ceiling:.6e}")
print(f"  single-cell floor           = {FLOOR_1CELL:.6e}")
print(f"  CEILING/floor               = {ceiling / FLOOR_1CELL:.3f}x")
print("  VERDICT: " + ("CEILING ABOVE FLOOR -- fitting is warranted"
                       if ceiling >= FLOOR_1CELL else
                       "CEILING BELOW FLOOR -- NOT FIT"))
assert ceiling >= FLOOR_1CELL, "ceiling below floor -- would not fit"

# --------------------------------------------------------------------------- 2. variance
hdr("4. WHERE DOES R08 ACTUALLY VARY?  (decides which null can possibly have power)")
pl = d["player_id"].to_numpy()
plseas = pd.Series(d["player_id"].astype(str) + "_" + d["season"].astype(str)).to_numpy()
vs_player = var_share_between(x, pl)
vs_plseas = var_share_between(x, plseas)
print(f"  var share BETWEEN players           = {vs_player:.4f}")
print(f"  var share BETWEEN player-seasons    = {vs_plseas:.4f}")
print(f"  var share WITHIN player (residual)  = {1 - vs_player:.4f}")
# and where does the SIGNAL live: between-player vs within-player component of the carrier
xb = pd.Series(x).groupby(pd.Series(pl)).transform("mean").to_numpy()
xw = x - xb
dr2_between = bf.dr2(xb)
dr2_within = bf.dr2(xw)
print(f"  dR2 using ONLY the between-player component of R08 = {dr2_between:.6e}")
print(f"  dR2 using ONLY the within-player component of R08  = {dr2_within:.6e}")
print(f"  share of the measured effect carried BETWEEN players = "
      f"{dr2_between / (dr2_between + dr2_within):.4f}")

# --------------------------------------------------------------------------- 3. nulls
hdr("5. THREE NULLS + INJECTION VERIFICATION (PREREG 5.2 / 5.3) -- D108 MANDATE")
seas = d["season"].to_numpy()
gdate = d["game_date"].to_numpy()
NULLS = {
    "N_ROW":    dict(kind="N_ROW", groups=None, blocks=None),
    "N_CYCLIC": dict(kind="N_CYCLIC", groups=plseas, blocks=None),
    "N_PSWAP":  dict(kind="N_SWAP", groups=plseas, blocks=seas),
}
npz = {}
res = []
powtabs = {}
for name, spec in NULLS.items():
    print(f"\n---- {name} ----")
    rr = np.random.default_rng(SEED + abs(hash(name)) % 10000)
    Xp = null_draws(spec["kind"], x, rr, groups=spec["groups"], order_key=gdate,
                    blocks=spec["blocks"], R=R_DRAWS)
    EX = bf.resid_X(Xp)
    num = bf.e @ EX
    den = np.einsum("ij,ij->j", EX, EX)
    draws = (num ** 2 / den) / bf.sst
    p = perm_p(fast, draws)
    print(f"  observed dR2 = {fast:.6e}")
    print(f"  null_mean = {draws.mean():.6e}   null_sd = {draws.std(ddof=1):.6e}   R={R_DRAWS}")
    print(f"  sd inflation vs N_ROW = "
          f"{draws.std(ddof=1) / (npz['N_ROW'].std(ddof=1) if 'N_ROW' in npz else draws.std(ddof=1)):.3f}")
    print(f"  p = {p:.6f}")
    npz[name] = draws

    pw = injection_power(bf, x, EX, np.random.default_rng(SEED + 7))
    powtabs[name] = pw
    print("  INJECTION:")
    for _, r in pw.iterrows():
        print(f"    delta={r['delta']:.6f}  achieved={r['achieved_dr2_med']:.6e}  "
              f"power={r['power']:.2f}  {r['benchmark']}")
    m = mde80(pw)
    det_best = float(pw.loc[pw["delta"] == 0.002057, "power"].iloc[0])
    typeI = float(pw.loc[pw["delta"] == 0.0, "power"].iloc[0])
    status = ("DEGENERATE -- cannot detect the programme's largest live effect"
              if det_best < 0.80 else
              "ANTICONSERVATIVE" if typeI > 0.10 else "USABLE")
    print(f"  MDE80 = {m:.6e}   power@0.002057 = {det_best:.2f}   typeI@0 = {typeI:.3f}"
          f"   STATUS = {status}")
    res.append(dict(null=name, n=len(d), obs_dr2=fast, p=p,
                    null_mean=float(draws.mean()), null_sd=float(draws.std(ddof=1)),
                    R=R_DRAWS, mde80=m, power_at_best_live=det_best, typeI_at_0=typeI,
                    status=status))

R = pd.DataFrame(res)
hdr("6. VERDICT TABLE")
print(R.to_string(index=False))

usable = R[R["status"] == "USABLE"]
if len(usable):
    matched = usable.sort_values("null_sd", ascending=False).iloc[0]
    print(f"\n  MATCHED NULL (PREREG 6.4: usable, most conservative) = {matched['null']}")
    print(f"  p under the matched null = {matched['p']:.6f}")
    print(f"  MDE80 under the matched null = {matched['mde80']:.6e}")
    print(f"  observed dR2 = {fast:.6e}  -> "
          f"{'ABOVE' if fast > matched['mde80'] else 'BELOW'} the matched null's MDE80")
    print("\n  D097's kill was made under N_CYCLIC (p = 0.996672).")
    cy = R[R["null"] == "N_CYCLIC"].iloc[0]
    print(f"  N_CYCLIC here: p={cy['p']:.6f}  status={cy['status']}  "
          f"power@0.002057={cy['power_at_best_live']:.2f}")
else:
    print("\n  NO USABLE NULL -- every candidate null failed injection.")

# --------------------------------------------------------------------------- save
np.savez_compressed(os.path.join(OUT, "nulls", "d097_r08_null_draws.npz"),
                    **{k: v for k, v in npz.items()},
                    observed_dr2=np.array([fast]))
R.to_csv(os.path.join(OUT, "D097_NULL_COMPARISON.csv"), index=False)
pd.concat([p.assign(null=k) for k, p in powtabs.items()]).to_csv(
    os.path.join(OUT, "D097_INJECTION_POWER.csv"), index=False)
pd.DataFrame([dict(
    candidate=CAND, target=TARGET, stratum="POOLED", base="B_COMPLETE", n=len(d),
    dr2_reproduced=fast, dr2_recorded_D097=D097_DR2,
    ceiling_residualised=ceiling, ceiling_over_floor=ceiling / FLOOR_1CELL,
    var_share_between_player=vs_player, var_share_between_player_season=vs_plseas,
    dr2_between_component=dr2_between, dr2_within_component=dr2_within,
    share_effect_between=dr2_between / (dr2_between + dr2_within),
)]).to_csv(os.path.join(OUT, "D097_DECOMPOSITION.csv"), index=False)
print("\nwrote D097_NULL_COMPARISON.csv, D097_INJECTION_POWER.csv, D097_DECOMPOSITION.csv, "
      "nulls/d097_r08_null_draws.npz")
