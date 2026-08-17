"""S12 -- (A) TYPE-I calibration of the composed-2 null at delta = 0, and
         (B) family-wise p for all 348 cells under the composed-2 null.

(A) is the check that decides whether s11's "37 of 54 now have p < 0.05" is a finding or an
artefact.  A null that is too narrow manufactures significance.  Measured against the SAME
protocol used for the injection study, with the effect deleted:
  * effect-free response = the real dependent with the candidate projected out, then
    block-resampled by whole player-season blocks so it keeps its real dependence and carries
    no effect;
  * p from the composed-2 permutation test; rejection at 0.05 two-sided.
E0_I0014's ORIGINAL level-matched null is run on the same synthetic responses, side by side,
so the contrast is on one contrast (D101): same rows, same response, same base, same SST.
"""
import json, os, time
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPL = os.path.dirname(HERE)
S14 = os.path.join(EXPL, "E0_I0014_residual_heterogeneity")
exec(open(os.path.join(HERE, "scripts", "_rebuild_e14.py")).read())

# ---------------------------------------------------------------- (B) family-wise p
print("=== (B) family-wise p under composed-2, all 348 cells, every arm ===")
fw_rows = []
for a in ["A4_CLEAN_DEC", "A3_CLEAN", "A2_DEC", "A1_FULL"]:
    z2 = np.load(os.path.join(HERE, "nulls", "composed2_null_%s.npz" % a), allow_pickle=True)
    maxt = z2["maxt_familywise"]
    nmz = [str(s) for s in z2["names"]]
    dpz = [str(s) for s in z2["dependents"]]
    for k in dpz:
        obs = z2["observed_t__" + k]
        for j, c in enumerate(nmz):
            o = obs[j]
            fw_rows.append(dict(arm=a, cell="%s|%s" % (c, k),
                                observed_abs_t=float(abs(o)) if np.isfinite(o) else np.nan,
                                bar_fw_q95=float(np.nanpercentile(maxt, 95)),
                                p_familywise=(float(np.mean(maxt >= abs(o)))
                                              if np.isfinite(o) else np.nan)))
FW = pd.DataFrame(fw_rows)
FW.to_csv(os.path.join(HERE, "_FAMILYWISE_P_COMPOSED2.csv"), index=False)
for a in ["A4_CLEAN_DEC", "A1_FULL"]:
    s = FW[FW["arm"] == a]
    print("  %-14s bar_fw=%.4f   cells with p_fw < 0.05: %d / %d"
          % (a, s["bar_fw_q95"].iloc[0], int((s["p_familywise"] < 0.05).sum()), len(s)))

BN = pd.read_csv(os.path.join(HERE, "BROKEN_NULLS.csv"))
rem = set(BN.loc[BN["resolution"] == "RE_MEASURED_COMPOSED2", "cell"])
for a in ["A4_CLEAN_DEC", "A1_FULL"]:
    s = FW[(FW["arm"] == a) & (FW["cell"].isin(rem))]
    print("  of the 54 re-measured broken cells on %-14s: p_fw < 0.05 for %d"
          % (a, int((s["p_familywise"] < 0.05).sum())))

# ---------------------------------------------------------------- (A) Type-I
print("\n=== (A) TYPE-I of the composed-2 null (delta = 0) ===")
B_REP = 400
R_NULL = 300
CELLS = ["pl_usg_sd5|pts_absres", "pl_minutes_prior|minutes_absres",
         "pts__pred_cv|fga_absres", "pl_dnp_frac5|pts_sqres",
         "pl_games_prior|pts_absres"]
print("allowlist (%d):" % len(CELLS), CELLS)
assert len(CELLS) == 5

m = n
sc = np.asarray(pd.Categorical(seas).codes, dtype=np.int64)
nsn = int(sc.max() + 1)
oh = np.zeros((m, nsn)); oh[np.arange(m), sc] = 1.0
cn = oh.sum(0)
def dm(M): return M - oh @ ((oh.T @ M) / cn[:, None])
def tsingle(ytil, xt):
    sxx = float(xt @ xt)
    if sxx <= 0: return np.nan
    sxy = float(xt @ ytil); beta = sxy / sxx
    sse = float(ytil @ ytil) - beta * sxy
    se = np.sqrt(max(sse, 0.0) / (m - nsn - 1) / sxx)
    return beta / se if se > 0 else np.nan

def blocks_of(keycol):
    sub = pd.DataFrame({"loc": np.arange(n), "s": seas, "k": f[keycol].to_numpy()})
    g = {}
    for (s, k), gg in sub.groupby(["s", "k"], sort=False):
        g.setdefault(s, []).append(gg["loc"].to_numpy())
    return g
GP = blocks_of("player_id"); GT = blocks_of("team_id")

def idx_composed2(groups, rng):
    idx = np.arange(n)
    for s, bl in groups.items():
        order = rng.permutation(len(bl))
        for i, b in enumerate(bl):
            don = bl[order[i]]
            idx[b] = don[rng.integers(0, len(don), len(b))]
    return idx
def idx_within(groups, rng):
    idx = np.arange(n)
    for s, bl in groups.items():
        for b in bl:
            idx[b] = b[rng.permutation(len(b))]
    return idx
def idx_between(groups, rng):
    idx = np.arange(n)
    for s, bl in groups.items():
        order = rng.permutation(len(bl))
        for i, b in enumerate(bl):
            don = bl[order[i]]
            idx[b] = don[np.arange(len(b)) % len(don)]
    return idx
def block_resample(vec, groups, rng):
    out = np.empty(n)
    for s, bl in groups.items():
        pick = rng.integers(0, len(bl), len(bl))
        for i, b in enumerate(bl):
            don = bl[pick[i]]
            out[b] = vec[don[np.arange(len(b)) % len(don)]]
    return out

t0 = time.time()
rows = []
for cell in CELLS:
    cand, dep = cell.split("|")
    j = names.index(cand)
    G = GP if is_player[j] else GT
    x = dm(Xz[:, j].reshape(-1, 1))[:, 0]
    sxx = float(x @ x)
    yt = dm(dict(DEPS)[dep].reshape(-1, 1))[:, 0]
    e0 = yt - (float(x @ yt) / sxx) * x
    rng = np.random.default_rng(9900 + j)
    rej = {"COMPOSED2": 0, "E0_I0014_LEVEL_MATCHED": 0, "ROW_NAIVE": 0}
    matched = idx_between if use_between[j] else idx_within
    for b in range(B_REP):
        eb = dm(block_resample(e0, G, rng).reshape(-1, 1))[:, 0]
        tobs = tsingle(eb, x)
        for tag, gen in (("COMPOSED2", idx_composed2), ("E0_I0014_LEVEL_MATCHED", matched)):
            c = 0
            for _ in range(R_NULL):
                ip = gen(G, rng)
                if abs(tsingle(eb, dm(Xz[ip, j].reshape(-1, 1))[:, 0])) >= abs(tobs):
                    c += 1
            if (c + 1) / (R_NULL + 1) <= 0.05:
                rej[tag] += 1
        # row-naive on the same synthetic response
        c = 0
        for _ in range(R_NULL):
            ir = np.arange(n)
            for s in np.unique(seas):
                mm = np.where(seas == s)[0]
                ir[mm] = mm[rng.permutation(len(mm))]
            if abs(tsingle(eb, dm(Xz[ir, j].reshape(-1, 1))[:, 0])) >= abs(tobs):
                c += 1
        if (c + 1) / (R_NULL + 1) <= 0.05:
            rej["ROW_NAIVE"] += 1
    r = dict(cell=cell, B_reps=B_REP, R_null=R_NULL,
             typeI_composed2=rej["COMPOSED2"] / B_REP,
             typeI_E0_I0014_level_matched=rej["E0_I0014_LEVEL_MATCHED"] / B_REP,
             typeI_row_naive=rej["ROW_NAIVE"] / B_REP)
    se = np.sqrt(0.05 * 0.95 / B_REP)
    r["mc_se_at_0.05"] = float(se)
    rows.append(r)
    print("  %-32s composed2 %.4f | E0_I0014 level-matched %.4f | row-naive %.4f  (mc se %.4f)"
          " [%.0fs]" % (cell, r["typeI_composed2"], r["typeI_E0_I0014_level_matched"],
                        r["typeI_row_naive"], se, time.time() - t0), flush=True)
T = pd.DataFrame(rows)
T.to_csv(os.path.join(HERE, "TYPE_I_CALIBRATION.csv"), index=False)
print("\nmedian Type-I: composed2 %.4f | E0_I0014 level-matched %.4f | row-naive %.4f"
      % (T["typeI_composed2"].median(), T["typeI_E0_I0014_level_matched"].median(),
         T["typeI_row_naive"].median()))
print("DONE s12")
