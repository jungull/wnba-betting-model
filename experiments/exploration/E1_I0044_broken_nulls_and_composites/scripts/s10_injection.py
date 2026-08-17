"""S10 -- INJECTION VERIFICATION of the composed-2 null's analytic floor.

The analytic floor is  MDE80 = (bar_abs + z80*sd_signed)^2 / n.  E1_I0041 validated that FORM
against an injection-verified floor to a median ratio of 0.989 across 96 synthetic conditions.
Here it is verified directly, on the real E0_I0014 frame, under the composed-2 null, so that at
least some of this screen's floors are labelled INJECTION_VERIFIED rather than ANALYTIC.

Protocol (pre-stated in PREREG 1, "Floors"):
  * take the real candidate column x (season-demeaned, z-scored) -- the SAME vector that is
    later tested (E1_I0041 DEFECTS D-1: its first run planted along a different carrier and the
    whole simulation was degenerate);
  * build an effect-free response by BLOCK-RESAMPLING the real dependent's within-season
    residual after x is projected out, whole player-season blocks at a time, so the response
    keeps its real dependence structure and carries no effect;
  * plant delta*x, scaled so the planted dR2 hits a target on the grid;
  * run the composed-2 permutation test at the cell's own per-cell bar and count rejections.

Power at the analytic MDE80 should be ~0.80.  E_inj is the grid point at which measured power
first reaches 0.80.
"""
import json, os, time
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPL = os.path.dirname(HERE)
S14 = os.path.join(EXPL, "E0_I0014_residual_heterogeneity")
exec(open(os.path.join(HERE, "scripts", "_rebuild_e14.py")).read())

Z80 = 0.8416212335729143
B_REP = 120
R_NULL = 300
GRID = np.array([0.0002, 0.0005, 0.0010, 0.0015, 0.0020, 0.0030, 0.0045, 0.0070])

RM = pd.read_csv(os.path.join(HERE, "_REMEASURE2_ALL_ARMS.csv"))
A1 = RM[RM["arm"] == "A1_FULL"].set_index("cell")

# EXPLICIT ALLOWLIST, printed and asserted -- no substring selection anywhere.
CELLS = ["pl_usg_sd5|pts_absres", "pl_minutes_prior|minutes_absres",
         "pts__pred_cv|fga_absres", "pl_dnp_frac5|pts_sqres",
         "pl_games_prior|pts_absres"]
print("injection allowlist (%d cells):" % len(CELLS))
for c in CELLS: print("   ", c)
assert len(CELLS) == 5 and len(set(CELLS)) == 5
for c in CELLS: assert c in A1.index, c

mask = np.ones(n, bool)
m = n
sc = np.asarray(pd.Categorical(seas).codes, dtype=np.int64)
nsn = int(sc.max() + 1)
oh = np.zeros((m, nsn)); oh[np.arange(m), sc] = 1.0
cn = oh.sum(0)
def dm(M): return M - oh @ ((oh.T @ M) / cn[:, None])
def tsingle(ytil, xt):
    sxx = float(xt @ xt)
    if sxx <= 0: return np.nan
    sxy = float(xt @ ytil)
    beta = sxy / sxx
    sse = float(ytil @ ytil) - beta * sxy
    df = m - nsn - 1
    se = np.sqrt(max(sse, 0.0) / df / sxx)
    return beta / se if se > 0 else np.nan

def build_blocks(keycol):
    sub = pd.DataFrame({"loc": np.arange(n), "s": seas, "k": f[keycol].to_numpy()})
    g = {}
    for (s, k), gg in sub.groupby(["s", "k"], sort=False):
        g.setdefault(s, []).append(gg["loc"].to_numpy())
    return g
GP = build_blocks("player_id"); GT = build_blocks("team_id")

def composed_index(groups, rng):
    idx = np.arange(n)
    for s, blocks in groups.items():
        order = rng.permutation(len(blocks))
        for i, b in enumerate(blocks):
            don = blocks[order[i]]
            idx[b] = don[rng.integers(0, len(don), len(b))]
    return idx

def block_resample(vec, groups, rng):
    """resample WHOLE blocks (within season) with replacement, cycling to the receiver length"""
    out = np.empty(n)
    for s, blocks in groups.items():
        pick = rng.integers(0, len(blocks), len(blocks))
        for i, b in enumerate(blocks):
            don = blocks[pick[i]]
            out[b] = vec[don[np.arange(len(b)) % len(don)]]
    return out

rows = []
t0 = time.time()
for cell in CELLS:
    cand, dep = cell.split("|")
    j = names.index(cand)
    G = GP if is_player[j] else GT
    x = dm(Xz[:, j].reshape(-1, 1))[:, 0]
    sxx = float(x @ x)
    y = dict(DEPS)[dep]
    yt = dm(y.reshape(-1, 1))[:, 0]
    # effect-free base: project x out of the real response, then block-resample it
    b0 = float(x @ yt) / sxx
    e0 = yt - b0 * x
    barc = float(A1.loc[cell, "bar_percell_abs_t"])
    sdc = float(A1.loc[cell, "null_sd_signed_t"])
    mde_analytic = (barc + Z80 * sdc) ** 2 / n
    rng = np.random.default_rng(4400 + j)
    powers = []
    for target in GRID:
        rej = 0
        for b in range(B_REP):
            eb = dm(block_resample(e0, G, rng).reshape(-1, 1))[:, 0]
            sse0 = float(eb @ eb)
            # solve delta so that dR2 = delta^2*sxx / (sse0 + delta^2*sxx) = target
            d2 = target * sse0 / (sxx * (1.0 - target))
            delta = np.sqrt(d2)
            yb = eb + delta * x
            ybt = dm(yb.reshape(-1, 1))[:, 0]
            tobs = tsingle(ybt, x)
            cnt = 0
            for _ in range(R_NULL):
                ip = composed_index(G, rng)
                xp = dm(Xz[ip, j].reshape(-1, 1))[:, 0]
                if abs(tsingle(ybt, xp)) >= abs(tobs):
                    cnt += 1
            # per-cell rejection at the 0.05 two-sided level of the cell's OWN composed null
            if (cnt + 1) / (R_NULL + 1) <= 0.05:
                rej += 1
        pw = rej / B_REP
        powers.append(pw)
        print("  %-32s target dR2 %.5f  power %.3f  (%.0fs)"
              % (cell, target, pw, time.time() - t0), flush=True)
    powers = np.array(powers)
    above = np.where(powers >= 0.80)[0]
    if len(above) == 0:
        e_inj = np.nan; note = "ABOVE_GRID_MAX"
    elif above[0] == 0:
        e_inj = float(GRID[0]); note = "BELOW_GRID_MIN"
    else:
        i1 = above[0]; i0 = i1 - 1
        w = (0.80 - powers[i0]) / (powers[i1] - powers[i0])
        e_inj = float(GRID[i0] + w * (GRID[i1] - GRID[i0])); note = "INTERPOLATED"
    rows.append(dict(cell=cell, n=n, bar_percell_abs_t=barc, null_sd_signed_t=sdc,
                     mde80_analytic=mde_analytic, E_inj=e_inj, e_inj_note=note,
                     ratio_analytic_over_injected=(mde_analytic / e_inj
                                                   if np.isfinite(e_inj) else np.nan),
                     powers=json.dumps(dict(zip([float(g) for g in GRID],
                                                [float(p) for p in powers])))))
    print("  -> %-32s MDE80_analytic %.6f  E_inj %.6f  ratio %.4f  [%s]"
          % (cell, mde_analytic, e_inj, rows[-1]["ratio_analytic_over_injected"], note), flush=True)

I = pd.DataFrame(rows)
I.to_csv(os.path.join(HERE, "INJECTION_VERIFICATION.csv"), index=False)
print("\nratio analytic/injected: min %.4f  median %.4f  max %.4f"
      % (I["ratio_analytic_over_injected"].min(), I["ratio_analytic_over_injected"].median(),
         I["ratio_analytic_over_injected"].max()))
print("DONE s10")
