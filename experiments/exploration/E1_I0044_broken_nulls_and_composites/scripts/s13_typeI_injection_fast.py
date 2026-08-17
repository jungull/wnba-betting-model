"""S13 -- TYPE-I calibration and INJECTION verification of the composed-2 null.  Fast form.

Speed note (and it is a real methodological point, not just an optimisation): the permuted
CARRIER does not depend on the response, so a pool of permuted columns can be generated once
per cell and reused across replicates and across the effect grid.  A pool of POOL draws is
built; each replicate draws R_NULL of them WITHOUT replacement, so replicates do not all share
one permutation set.  (s10/s12's slower form rebuilt every index and was killed at PIDs 35364
and 31472, both launched by this screen and recorded in _s10_pid.txt / _s12_pid.txt.)

Two questions, in this order:
  A. TYPE-I at delta = 0.  If the composed-2 null over-rejects, s11's "37 of 54 now have
     p < 0.05" is an artefact and must not be reported as a finding.  E0_I0014's own
     level-matched null and the row-naive null are run on the SAME synthetic responses
     (D101: one contrast -- same rows, same response, same base, same SST).
  B. INJECTION: the grid point at which measured power reaches 0.80, against the analytic
     MDE80 = (bar_abs + z80*sd_signed)^2 / n.
"""
import json, os, time
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPL = os.path.dirname(HERE)
S14 = os.path.join(EXPL, "E0_I0014_residual_heterogeneity")
exec(open(os.path.join(HERE, "scripts", "_rebuild_e14.py")).read())

Z80 = 0.8416212335729143
POOL = 600
R_NULL = 300
B_TYPEI = 400
B_POWER = 150
GRID = np.array([0.0000, 0.0002, 0.0005, 0.0010, 0.0015, 0.0020, 0.0030, 0.0045, 0.0070])
CELLS = ["pl_usg_sd5|pts_absres", "pl_minutes_prior|minutes_absres",
         "pts__pred_cv|fga_absres", "pl_dnp_frac5|pts_sqres",
         "pl_games_prior|pts_absres"]
print("allowlist (%d cells), printed and asserted:" % len(CELLS))
for c in CELLS: print("   ", c)
assert len(CELLS) == 5 and len(set(CELLS)) == 5

m = n
sc = np.asarray(pd.Categorical(seas).codes, dtype=np.int64)
nsn = int(sc.max() + 1)
oh = np.zeros((m, nsn)); oh[np.arange(m), sc] = 1.0
cnv = oh.sum(0)
def dm(M): return M - oh @ ((oh.T @ M) / cnv[:, None])
DF = m - nsn - 1

def tcols(ytil, Mt):
    """t of ytil on each column of the ALREADY-DEMEANED matrix Mt"""
    with np.errstate(invalid="ignore", divide="ignore"):
        sxx = (Mt * Mt).sum(0)
        sxy = Mt.T @ ytil
        beta = np.where(sxx > 0, sxy / sxx, np.nan)
        sse = float(ytil @ ytil) - beta * sxy
        se = np.sqrt(np.maximum(sse, 0.0) / DF / np.where(sxx > 0, sxx, np.nan))
        return np.where(se > 0, beta / se, np.nan)

def blocks_of(keycol):
    sub = pd.DataFrame({"loc": np.arange(n), "s": seas, "k": f[keycol].to_numpy()})
    g = {}
    for (s, k), gg in sub.groupby(["s", "k"], sort=False):
        g.setdefault(s, []).append(gg["loc"].to_numpy())
    return g
GP = blocks_of("player_id"); GT = blocks_of("team_id")

def i_composed2(G, rng):
    idx = np.arange(n)
    for s, bl in G.items():
        order = rng.permutation(len(bl))
        for i, b in enumerate(bl):
            don = bl[order[i]]
            idx[b] = don[rng.integers(0, len(don), len(b))]
    return idx
def i_within(G, rng):
    idx = np.arange(n)
    for s, bl in G.items():
        for b in bl:
            idx[b] = b[rng.permutation(len(b))]
    return idx
def i_between(G, rng):
    idx = np.arange(n)
    for s, bl in G.items():
        order = rng.permutation(len(bl))
        for i, b in enumerate(bl):
            don = bl[order[i]]
            idx[b] = don[np.arange(len(b)) % len(don)]
    return idx
def i_row(G, rng):
    idx = np.arange(n)
    for s in np.unique(seas):
        mm = np.where(seas == s)[0]
        idx[mm] = mm[rng.permutation(len(mm))]
    return idx

def block_resample_matrix(vec, G, rng, B):
    out = np.empty((n, B))
    for bi in range(B):
        for s, bl in G.items():
            pick = rng.integers(0, len(bl), len(bl))
            for i, b in enumerate(bl):
                don = bl[pick[i]]
                out[b, bi] = vec[don[np.arange(len(b)) % len(don)]]
    return out

t0 = time.time()
ti_rows, inj_rows = [], []
RM = pd.read_csv(os.path.join(HERE, "_REMEASURE2_ALL_ARMS.csv"))
A1 = RM[RM["arm"] == "A1_FULL"].set_index("cell")

for cell in CELLS:
    cand, dep = cell.split("|")
    j = names.index(cand)
    G = GP if is_player[j] else GT
    x = dm(Xz[:, j].reshape(-1, 1))[:, 0]
    sxx = float(x @ x)
    yt = dm(dict(DEPS)[dep].reshape(-1, 1))[:, 0]
    e0 = yt - (float(x @ yt) / sxx) * x
    rng = np.random.default_rng(7700 + j)

    # permuted-carrier pools, one per scheme, built ONCE
    pools = {}
    for tag, gen in (("COMPOSED2", i_composed2),
                     ("E0_I0014_LEVEL_MATCHED", i_between if use_between[j] else i_within),
                     ("ROW_NAIVE", i_row)):
        P = np.empty((n, POOL))
        for d in range(POOL):
            P[:, d] = Xz[gen(G, rng), j]
        pools[tag] = dm(P)
    print("  %-32s pools built (%.0fs)" % (cell, time.time() - t0), flush=True)

    def pvals(Y, tag):
        """two-sided permutation p for each column of Y against pool `tag`"""
        out = np.empty(Y.shape[1])
        for c in range(Y.shape[1]):
            yc = Y[:, c]
            tobs = abs(tcols(yc, x.reshape(-1, 1))[0])
            sel = rng.choice(POOL, size=R_NULL, replace=False)
            tn = np.abs(tcols(yc, pools[tag][:, sel]))
            out[c] = (np.sum(tn >= tobs) + 1) / (R_NULL + 1)
        return out

    # ---------------- A. Type-I
    E = dm(block_resample_matrix(e0, G, rng, B_TYPEI))
    r = dict(cell=cell, B_reps=B_TYPEI, R_null=R_NULL, pool=POOL)
    for tag in ("COMPOSED2", "E0_I0014_LEVEL_MATCHED", "ROW_NAIVE"):
        r["typeI_" + tag.lower()] = float(np.mean(pvals(E, tag) <= 0.05))
    r["mc_se_at_0.05"] = float(np.sqrt(0.05 * 0.95 / B_TYPEI))
    ti_rows.append(r)
    print("  %-32s TYPE-I  composed2 %.4f | E0_I0014 %.4f | row %.4f  (mc se %.4f) [%.0fs]"
          % (cell, r["typeI_composed2"], r["typeI_e0_i0014_level_matched"],
             r["typeI_row_naive"], r["mc_se_at_0.05"], time.time() - t0), flush=True)

    # ---------------- B. injection power
    barc = float(A1.loc[cell, "bar_percell_abs_t"])
    sdc = float(A1.loc[cell, "null_sd_signed_t"])
    mde_analytic = (barc + Z80 * sdc) ** 2 / n
    powers = []
    for target in GRID:
        Eb = dm(block_resample_matrix(e0, G, rng, B_POWER))
        sse0 = (Eb * Eb).sum(0)
        d2 = target * sse0 / (sxx * (1.0 - target)) if target > 0 else np.zeros(B_POWER)
        Yb = dm(Eb + np.sqrt(d2)[None, :] * x[:, None])
        pw = float(np.mean(pvals(Yb, "COMPOSED2") <= 0.05))
        powers.append(pw)
        print("     target dR2 %.5f  power %.3f  (%.0fs)" % (target, pw, time.time() - t0),
              flush=True)
    powers = np.array(powers)
    ab = np.where(powers >= 0.80)[0]
    if len(ab) == 0:
        e_inj, note = np.nan, "ABOVE_GRID_MAX"
    elif ab[0] == 0:
        e_inj, note = float(GRID[0]), "BELOW_GRID_MIN"
    else:
        i1 = ab[0]; i0 = i1 - 1
        w = (0.80 - powers[i0]) / (powers[i1] - powers[i0])
        e_inj, note = float(GRID[i0] + w * (GRID[i1] - GRID[i0])), "INTERPOLATED"
    inj_rows.append(dict(cell=cell, n=n, B_reps=B_POWER, R_null=R_NULL,
                         bar_percell_abs_t=barc, null_sd_signed_t=sdc,
                         mde80_analytic=mde_analytic, E_inj=e_inj, e_inj_note=note,
                         power_at_zero=float(powers[0]),
                         ratio_analytic_over_injected=(mde_analytic / e_inj
                                                       if np.isfinite(e_inj) and e_inj > 0
                                                       else np.nan),
                         powers=json.dumps(dict(zip([float(g) for g in GRID],
                                                    [float(p) for p in powers])))))
    print("  -> %-32s MDE80_analytic %.6f  E_inj %.6f  ratio %s  [%s]"
          % (cell, mde_analytic, e_inj, inj_rows[-1]["ratio_analytic_over_injected"], note),
          flush=True)

T = pd.DataFrame(ti_rows); T.to_csv(os.path.join(HERE, "TYPE_I_CALIBRATION.csv"), index=False)
I = pd.DataFrame(inj_rows); I.to_csv(os.path.join(HERE, "INJECTION_VERIFICATION.csv"), index=False)
print("\n=== TYPE-I SUMMARY (nominal 0.05) ===")
print(T[["cell", "typeI_composed2", "typeI_e0_i0014_level_matched", "typeI_row_naive"]]
      .to_string(index=False))
print("median  composed2 %.4f | E0_I0014 level-matched %.4f | row-naive %.4f"
      % (T["typeI_composed2"].median(), T["typeI_e0_i0014_level_matched"].median(),
         T["typeI_row_naive"].median()))
print("\n=== INJECTION SUMMARY ===")
print(I[["cell", "mde80_analytic", "E_inj", "ratio_analytic_over_injected",
         "e_inj_note", "power_at_zero"]].to_string(index=False))
print("DONE s13")
