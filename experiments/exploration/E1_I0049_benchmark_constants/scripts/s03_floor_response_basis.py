"""E1_I0049 s03 -- PREREG 7 C6: THE FLOORS ARE MEASURED ON A DIFFERENT RESPONSE FROM THE
CONSTANTS THEY ARE QUOTED AGAINST.

E1_I0026/scripts/df_base.py:51 fixes `OUTCOME = "y_ppm"`.  Every benchmark quoted against those
floors (0.002057, 0.001127, 0.000129) is a dR2 on a POINTS response.  This script runs the same
null, on the same rows, with the same base and the same carrier, and measures the floor on:

  ARM P  the y_ppm OLS increment            -- E1_I0026's own statistic (REPRODUCTION ANCHOR)
  ARM T  the transported POINTS statistic    -- D089's own realised (2 d.e - d.d)/SST_pts
  ARM C  the transported POINTS CEILING      -- (d.d)/SST_pts, whose noise floor nobody recorded

All three arms share ONE null draw sequence, so they are matched draw-for-draw.
Draws are stored RAW, SIGNED and UNSTANDARDISED with the full stratum key on every row.

PREREG sha256 4770c3ac21a3e4e4d1c3e277d59dd7b49f1403d7e459e355b851945b58f23dfc
"""
from __future__ import annotations
import json, os, sys, time
import numpy as np
import pandas as pd

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
EXPL = os.path.join(ROOT, r"experiments\exploration")
KIT = os.path.join(EXPL, "_screen_kit")
HERE = os.path.join(EXPL, "E1_I0049_benchmark_constants")
RAW = os.path.join(HERE, "raw")
os.makedirs(RAW, exist_ok=True)
sys.dont_write_bytecode = True
if KIT not in sys.path:
    sys.path.insert(0, KIT)
import screenkit as sk  # noqa: E402

pd.set_option("display.width", 250); pd.set_option("display.max_columns", 80)

D089F = os.path.join(EXPL, "E1_I0018_teammate_volume_channel", "screen_frame.parquet")
D085F = os.path.join(EXPL, "E0_I0016_efficiency_predictors", "screen_frame.parquet")

SEED = 20260808          # E1_I0026's own seed, so ARM P is a bit-for-bit reproduction target
N_DRAWS = 600            # E1_I0026's own draw count
Z80 = 0.8416212335729143
CARRIER = "P01_c04_prevgame"
BASECOLS = ["refB_ppm", "refB_spm", "refB_pps", "refB_mpg"]     # B_COMPLETE
T_LADDER = {1: 1.645, 18: 5.065915, 44: 5.866628, 132: 6.974475}   # E1_I0026's own t_crit column


def hdr(s):
    print("\n" + "=" * 100); print(s); print("=" * 100)


# ---------------------------------------------------------------- frame, E1_I0026's loader ----
hdr("A. FRAME -- E1_I0026/df_base.load_frame() replicated inline (read-only, not imported)")
a = pd.read_parquet(D089F)
b = pd.read_parquet(D085F)
sk.assert_partition(a, verbose=False)
sk.assert_partition(b, verbose=False)
keep_b = ["player_id", "game_id", "A10_opp_defrtg", "A01_opp_efg_allowed", "A02_opp_ts_allowed"]
b2 = b[keep_b].copy()
n0 = len(a)
f = a.merge(b2, on=["player_id", "game_id"], how="inner", validate="one_to_one")
assert len(f) == n0
f = f.sort_values(["player_id", "season", "game_date", "game_id"],
                  kind="stable").reset_index(drop=True)
sk.assert_partition(f, verbose=False)
print("  joined frame %s  seasons=%s" % (f.shape, sorted(f.season.unique())))

f["_m_hat"] = f["prior5_minutes"].fillna(f["refB_mpg"])
DEC = ((f["n_prior"] >= 8).to_numpy() & (f["prior5_minutes"] >= 24).to_numpy(dtype=bool))

cols = ["y_ppm", "y_pts", "_m_hat", CARRIER] + BASECOLS
m = DEC.copy()
for c in cols:
    m &= np.isfinite(pd.to_numeric(f[c], errors="coerce").to_numpy(float))
sub = f.loc[m].reset_index(drop=True)
sk.assert_partition(sub, verbose=False)
print("  DECISION rows after finiteness on %s: n=%d   (E1_I0026 records 5,673)" % (cols, len(sub)))
assert len(sub) == 5673, "row count does not match E1_I0026's published n"

y_ppm = sub["y_ppm"].to_numpy(float)
y_pts = sub["y_pts"].to_numpy(float)
mh = sub["_m_hat"].to_numpy(float)
B = sub[BASECOLS].to_numpy(float)
x_real = sub[CARRIER].to_numpy(float)

X = np.column_stack([np.ones(len(sub)), B])
XtXi = np.linalg.pinv(X.T @ X)
b0 = XtXi @ (X.T @ y_ppm)
fit_base_ppm = X @ b0
e_ppm = y_ppm - fit_base_ppm
sst_ppm = float(((y_ppm - y_ppm.mean()) ** 2).sum())

pts_ref = fit_base_ppm * mh
e_pts = y_pts - pts_ref
sst_pts = float(((y_pts - y_pts.mean()) ** 2).sum())

print("""
  DENOMINATORS, stated in full (D101):
    ARM P  response y_ppm  | n=%d | SST=%.6f (about the unweighted mean) | no weights
           base [1, refB_ppm, refB_spm, refB_pps, refB_mpg] | statistic: OLS increment dR2
    ARM T  response y_pts  | n=%d | SST=%.6f (about the unweighted mean) | no weights
           same base, coefficient fitted on y_ppm and TRANSPORTED by per-row m_hat
           statistic: (2 d.e - d.d)/SST_pts, D089's realised paired-forecast dR2
    ARM C  response y_pts  | same rows, same SST | statistic: (d.d)/SST_pts, the ceiling itself
""" % (len(sub), sst_ppm, len(sub), sst_pts))


def three_stats(xv):
    """One carrier vector -> (ARM P, ARM T, ARM C).  Signed, unstandardised."""
    xt = xv - X @ (XtXi @ (X.T @ xv))
    den = float(xt @ xt)
    if not np.isfinite(den) or den <= 1e-12:
        return 0.0, 0.0, 0.0
    num = float(e_ppm @ xt)
    armP = (num * num / den) / sst_ppm
    beta = num / den
    d = beta * xt * mh
    dd, de = float(d @ d), float(d @ e_pts)
    armT = (2 * de - dd) / sst_pts
    armC = dd / sst_pts
    return armP, armT, armC


rP, rT, rC = three_stats(x_real)
xt_r = x_real - X @ (XtXi @ (X.T @ x_real))
beta_r = float(e_ppm @ xt_r) / float(xt_r @ xt_r)
d_r = beta_r * xt_r * mh
c_star_real = float(d_r @ e_pts) / float(d_r @ d_r)
oracle_real = float(d_r @ e_pts) ** 2 / (float(d_r @ d_r) * sst_pts)
print("  REAL carrier: ARM P (y_ppm dR2) = %.10f" % rP)
print("                ARM T (points realised) = %.10f" % rT)
print("                ARM C (points ceiling (d.d)/SST) = %.10f" % rC)
print("                c* = %.10f   ORACLE = %.10f" % (c_star_real, oracle_real))

# ------------------------------------------------------------------- the null, three arms -----
hdr("B. ONE NULL SEQUENCE, THREE MATCHED ARMS -- entity swap team-season, %d draws, seed %d"
    % (N_DRAWS, SEED))
dat = sub[["season", "player_id", "team_id", "opp_team_id", "game_id", "game_date"]].copy()
dat["feat"] = x_real

collected = {"P": [], "T": [], "C": []}


def stat_fn_all(dfr):
    xv = pd.to_numeric(dfr["feat"], errors="coerce").to_numpy(float)
    p, t, c = three_stats(xv)
    collected["P"].append(p); collected["T"].append(t); collected["C"].append(c)
    return p        # ARM P is what the kit sees, so its p/mean/sd reproduce E1_I0026 exactly


t0 = time.time()
res = sk.entity_swap_null(stat_fn_all, dat, ["team_id", "season"], N_DRAWS, SEED,
                          feature_col="feat", date_col="game_date", season_col="season",
                          tiebreak_col="game_id", alternative="greater")
print("  kit returned in %.1fs: real=%.6e mean=%.6e sd=%.6e p=%.4f n_groups=%s"
      % (time.time() - t0, res["real"], res["mean"], res["sd"], res["p"], res.get("n_groups")))

# the kit calls stat_fn once on the real frame too; drop that call if present
for k in collected:
    collected[k] = np.asarray(collected[k], float)
print("  stat_fn invocations captured: %d (n_draws=%d)" % (len(collected["P"]), N_DRAWS))
kit_draws = np.asarray(res["draws"], float)
# Align to the kit's own draw vector rather than guessing which call was the real frame.
# The extra invocation is the real-frame evaluation; find and drop it by exact positional match.
capP = collected["P"]
keep = None
for drop in range(len(capP)):
    trial = np.delete(capP, drop)
    if len(trial) == len(kit_draws) and np.allclose(trial, kit_draws, rtol=0, atol=0):
        keep = drop
        break
assert keep is not None, "could not align captured stat_fn calls with the kit's draw vector"
print("  -> dropped invocation index %d (the real-frame call); "
      "remaining %d match kit draws EXACTLY (atol=0)" % (keep, len(kit_draws)))
drawsP = np.delete(collected["P"], keep)
drawsT = np.delete(collected["T"], keep)
drawsC = np.delete(collected["C"], keep)
assert len(drawsP) == N_DRAWS, len(drawsP)

# ---------------- ANCHOR: ARM P must reproduce E1_I0026's recorded null moments ----------------
hdr("C. ANCHOR -- ARM P reproduces E1_I0026's recorded null mean and sd for this exact cell")
meta = pd.read_csv(os.path.join(EXPL, "E1_I0026_detection_floor", "out", "s03_null_meta.csv"))
row = meta[(meta.stratum == "DECISION") & (meta.base == "B_COMPLETE")
           & (meta["null"] == "N_B_entity_swap_team_season")]
print(row.to_string(index=False))
ANCH = []
if len(row) == 1:
    r = row.iloc[0]
    for nm, rec, rep in [("real_dr2", r.real_dr2, res["real"]),
                         ("null_mean", r.null_mean, float(np.mean(drawsP))),
                         ("null_sd", r.null_sd, float(np.std(drawsP, ddof=1))),
                         ("n", r.n, len(sub))]:
        d = abs(float(rep) - float(rec))
        ANCH.append(dict(id="A15_" + nm, recorded=float(rec), reproduced=float(rep), diff=d,
                         PASS=bool(d <= max(1e-9, 1e-5 * abs(float(rec))))))
        print("  [%s] A15_%-10s recorded %.12g  reproduced %.12g  |d|=%.3e"
              % ("PASS" if ANCH[-1]["PASS"] else "FAIL", nm, rec, rep, d))
    # the kit's own reported mean/sd
    print("  (kit-reported mean %.12g sd %.12g)" % (res["mean"], res["sd"]))

# --------------------------------------------------------------------- floors, both scales ----
hdr("D. THE FLOOR ON EACH SCALE -- same rows, same base, same null, same draws")
out = []
for arm, draws, real, resp, stat in [
        ("P_y_ppm_OLS_increment", drawsP, rP, "y_ppm", "OLS increment dR2"),
        ("T_points_transported_realised", drawsT, rT, "y_pts", "(2 d.e - d.d)/SST_pts"),
        ("C_points_transported_ceiling", drawsC, rC, "y_pts", "(d.d)/SST_pts")]:
    mu = float(np.mean(draws)); sd = float(np.std(draws, ddof=1))
    q95 = float(np.quantile(draws, 0.95))
    for K, tc in T_LADDER.items():
        T = mu + tc * sd
        mde = (np.sqrt(T) + Z80 * np.sqrt(max(mu, 0.0))) ** 2 if T >= 0 and mu >= 0 else np.nan
        out.append(dict(arm=arm, response=resp, statistic=stat, stratum="DECISION",
                        base="B_COMPLETE", null="N_B_entity_swap_team_season", carrier=CARRIER,
                        n=len(sub), n_draws=N_DRAWS, seed=SEED, family_size_K=K, t_crit=tc,
                        null_mean=mu, null_sd=sd, null_q95=q95, real=real,
                        MDE80_analytic=float(mde)))
fl = pd.DataFrame(out)
print(fl[["arm", "response", "family_size_K", "null_mean", "null_sd", "null_q95", "real",
          "MDE80_analytic"]].to_string(index=False, float_format=lambda z: "%.6g" % z))
fl.to_csv(os.path.join(RAW, "_s03_floors_by_response.csv"), index=False)

hdr("E. THE COMPARISON THE PROGRAMME HAS BEEN MAKING, AND THE MATCHED ONE")
pub = {1: 0.00102, 18: 0.00190, 44: 0.00209, 132: 0.00235}
for K in [1, 132]:
    fP = fl[(fl.arm.str.startswith("P")) & (fl.family_size_K == K)].MDE80_analytic.iloc[0]
    fT = fl[(fl.arm.str.startswith("T")) & (fl.family_size_K == K)].MDE80_analytic.iloc[0]
    fC = fl[(fl.arm.str.startswith("C")) & (fl.family_size_K == K)].MDE80_analytic.iloc[0]
    print("""
  K = %d
    published floor (drift-corrected, y_ppm)            %.6f
    this screen, ARM P analytic (y_ppm, same null)      %.6f   <- calibrates the analytic form
    this screen, ARM T analytic (POINTS, D089's stat)   %.6f   <- the MATCHED floor
    this screen, ARM C analytic (POINTS, the ceiling)   %.6f   <- noise floor OF THE CEILING
    ratio ARM T / ARM P                                 %.3fx
    0.002057 vs ARM T floor                             %.3fx
    0.0033139 (realised, same cell) vs ARM T floor      %.3fx
""" % (K, pub[K], fP, fT, fC, fT / fP, 0.0020571994 / fT, 0.0033139323 / fT))

hdr("E2. THE CONTROL D089 NEVER RECORDED -- the NOISE FLOOR OF THE CEILING STATISTIC ITSELF")
cmu, csd = float(np.mean(drawsC)), float(np.std(drawsC, ddof=1))
cq95 = float(np.quantile(drawsC, 0.95))
print("""
  Same rows, same base, same carrier, same null, %d entity-swap draws.  The statistic is the
  ceiling itself, (d.d)/SST_pts, computed through the identical transported path.

    null mean of the CEILING statistic        %.6e
    null sd                                   %.6e
    null q95 (the matched noise floor)        %.6e
    D089's published ceiling, var-share form  %.6e   = %.3fx its own q95 noise floor
    D089's published ceiling, per-sd form     %.6e   = %.3fx its own q95 noise floor
    D089's ORACLE (the true bound)            %.6e   = %.3fx
    p (share of draws >= the real ceiling)    %.4f

  CAUTION, D101: this null mean (%.3e) is of the same ORDER as D084's entire published ceiling
  (1.294e-04).  Those are DIFFERENT rows, a DIFFERENT frame and a DIFFERENT SST, so the pair is
  NOT_COMPARABLE and no ratio is formed here.  It is recorded only as an order-of-magnitude
  caution about ceilings of size ~1e-04 measured on designs of this shape.
""" % (N_DRAWS, cmu, csd, cq95, rC, rC / cq95, 0.0020571994, 0.0020571994 / cq95,
       oracle_real, oracle_real / cq95,
       float((1 + np.sum(drawsC >= rC)) / (N_DRAWS + 1)), cmu))

# --------------------------------------------------------------- store raw signed draws --------
hdr("F. RAW SIGNED UNSTANDARDISED DRAWS, FULL STRATUM KEY ON EVERY ROW")
key = "DECISION|B_COMPLETE|N_B_entity_swap_team_season|%s" % CARRIER
np.savez_compressed(
    os.path.join(RAW, "s03_null_draws_signed_raw.npz"),
    stratum_key=np.array([key]),
    arms=np.array(["P_y_ppm_OLS_increment", "T_points_transported_realised",
                   "C_points_transported_ceiling"]),
    responses=np.array(["y_ppm", "y_pts", "y_pts"]),
    draws_P_y_ppm=drawsP, draws_T_points_realised=drawsT, draws_C_points_ceiling=drawsC,
    real_P=np.array([rP]), real_T=np.array([rT]), real_C=np.array([rC]),
    n=np.array([len(sub)]), n_draws=np.array([N_DRAWS]), seed=np.array([SEED]),
    sst_ppm=np.array([sst_ppm]), sst_pts=np.array([sst_pts]),
    note=np.array(["raw signed unstandardised; no absolute values; stratum key on every arm"]))
pd.DataFrame({"stratum_key": key, "draw_index": np.arange(N_DRAWS),
              "P_y_ppm_OLS_increment": drawsP,
              "T_points_transported_realised": drawsT,
              "C_points_transported_ceiling": drawsC}).to_csv(
    os.path.join(RAW, "s03_null_draws_signed_raw.csv"), index=False)
print("  wrote raw/s03_null_draws_signed_raw.{npz,csv}  (%d draws x 3 arms, signed, raw)"
      % N_DRAWS)

json.dump({"anchors": ANCH,
           "real": {"ARM_P_y_ppm": rP, "ARM_T_points_realised": rT,
                    "ARM_C_points_ceiling": rC, "c_star": c_star_real, "oracle": oracle_real},
           "n": len(sub), "seed": SEED, "n_draws": N_DRAWS,
           "sst_ppm": sst_ppm, "sst_pts": sst_pts},
          open(os.path.join(RAW, "_s03.json"), "w"), indent=1)
print("\nDONE s03")
