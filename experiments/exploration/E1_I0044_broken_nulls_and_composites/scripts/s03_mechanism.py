"""S03 -- pin the MECHANISM of each broken null by measurement, not by inspection of names.

Three candidate mechanisms are tested explicitly:

M-VOID   the candidate has ZERO within-season variance, so it is annihilated by the screen's
         own base (season fixed effects).  The statistic does not exist; the null cannot.
         TEST: number of distinct values per season; sxx of the season-demeaned z-scored column.

M-WITHIN the WITHIN-block shuffle preserves each block's MEAN exactly, so the between-block
         share vsb of the candidate survives the permutation untouched.  If the association
         lives in that component, the "null" contains the alternative.
         TEST: (i) exact preservation of block means under within_block_index;
               (ii) t of the permuted column against t of the block-mean-only column.

M-BETWEEN the BETWEEN-block reassignment `idx[b] = don[arange(len(b)) % len(don)]` maps the
         donor's rows onto the receiver's rows IN CHRONOLOGICAL POSITION ORDER, so the
         WITHIN-block ordinal/time profile survives.
         TEST: correlation between the permuted column's within-block deviation and the real
         column's within-block deviation, across draws.

STATISTIC-BLINDNESS (E1_I0040's principle, applied BEFORE condemning anything):
         multiply the component the null is blind to by 10, then delete it, and measure the
         change in the target statistic.  A cell is only condemned if the statistic MOVES.
"""
import json, os
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPL = os.path.dirname(HERE)
S14 = os.path.join(EXPL, "E0_I0014_residual_heterogeneity")
exec(open(os.path.join(HERE, "scripts", "_rebuild_e14.py")).read())
# _rebuild_e14 provides: f, seas, n, X, Xz, names, schemes, is_player, gp, gt,
#                        demean_mat, tvec, DEPS, Ytil, Xztil, NS, z, use_between, draws, real_t

OUT = {}
BROKEN = pd.read_csv(os.path.join(HERE, "_E0_I0014_CELL_DIAG.csv"))
bc = sorted(BROKEN.loc[BROKEN["is_broken"], "candidate"].unique())
print("broken candidates (%d):" % len(bc), bc)

# ------------------------------------------------------------------ M-VOID test
print("\n=== M-VOID: within-season variation of every broken candidate ===")
void_rows = []
for nm in bc:
    j = names.index(nm)
    nd = [int(len(np.unique(X[seas == s, j]))) for s in np.unique(seas)]
    wsd = [float(X[seas == s, j].std()) for s in np.unique(seas)]
    sxx = float((Xztil[:, j] ** 2).sum())
    void_rows.append(dict(candidate=nm, n_distinct_per_season=nd,
                          within_season_sd=wsd, sxx_after_base=sxx))
    print("  %-22s distinct/season=%s  sd/season=%s  sxx=%.6e"
          % (nm, nd, ["%.3e" % v for v in wsd], sxx))
VOID = {r["candidate"] for r in void_rows if max(r["within_season_sd"]) == 0.0}
print("  M-VOID candidates (zero within-season variance):", sorted(VOID))
OUT["M_VOID_candidates"] = sorted(VOID)

# ------------------------------------------------------------------ M-WITHIN test
print("\n=== M-WITHIN: does the within-block shuffle preserve block means exactly? ===")
def within_block_index(groups, n, rng):
    idx = np.arange(n)
    for s, blocks in groups.items():
        for b in blocks:
            idx[b] = b[rng.permutation(len(b))]
    return idx
def block_index(groups, n, rng):
    idx = np.arange(n)
    for s, blocks in groups.items():
        order = rng.permutation(len(blocks))
        for i, b in enumerate(blocks):
            don = blocks[order[i]]
            idx[b] = don[np.arange(len(b)) % len(don)]
    return idx

rng = np.random.default_rng(20260808)
wp = within_block_index(gp, n, rng)
mx = 0.0
for s, blocks in gp.items():
    for b in blocks:
        mx = max(mx, float(abs(Xz[wp[b]][:, :].mean(0) - Xz[b].mean(0)).max()))
print("  max |block mean(permuted) - block mean(real)| over all 475 blocks x 58 candidates: %.3e"
      % mx)
OUT["M_WITHIN_max_blockmean_change"] = mx

# block-mean-only column vs full column: how much of the observed t does the mean carry?
def blockmean_col(v, groups):
    out = np.zeros_like(v)
    for s, blocks in groups.items():
        for b in blocks:
            out[b] = v[b].mean()
    return out

print("\n  t of the BLOCK-MEAN-ONLY component vs the full candidate (WITHIN-null cells):")
wr = []
for nm in bc:
    if nm in VOID: continue
    j = names.index(nm)
    G = gp if is_player[j] else gt
    bm = demean_mat(blockmean_col(Xz[:, j], G).reshape(-1, 1))[:, 0]
    wd = demean_mat((Xz[:, j] - blockmean_col(Xz[:, j], G)).reshape(-1, 1))[:, 0]
    for k, _ in DEPS:
        cell = "%s|%s" % (nm, k)
        if not bool(BROKEN.set_index("cell").loc[cell, "is_broken"]): continue
        yt = Ytil[k]
        t_full = real_t[k][j]
        t_bm = tvec(yt, bm.reshape(-1, 1), NS)[1][0]
        t_wd = tvec(yt, wd.reshape(-1, 1), NS)[1][0]
        wr.append(dict(cell=cell, candidate=nm, dep=k,
                       null_used=("BETWEEN-block" if use_between[j] else "WITHIN-block"),
                       t_full=float(t_full), t_blockmean_only=float(t_bm),
                       t_withindev_only=float(t_wd)))
WR = pd.DataFrame(wr)
print(WR.to_string(index=False))
WR.to_csv(os.path.join(HERE, "_COMPONENT_T.csv"), index=False)

# ------------------------------------------------------------------ M-BETWEEN test
print("\n=== M-BETWEEN: does the block reassignment preserve the within-block ordinal profile? ===")
ip = block_index(gp, n, rng)
# within-block deviation of the permuted column vs of the real column, per candidate
rows = []
for nm in bc:
    if nm in VOID: continue
    j = names.index(nm)
    G = gp if is_player[j] else gt
    real_dev = Xz[:, j] - blockmean_col(Xz[:, j], G)
    permcol = Xz[ip, j] if is_player[j] else Xz[block_index(gt, n, rng), j]
    perm_dev = permcol - blockmean_col(permcol, G)
    ok = np.isfinite(real_dev) & np.isfinite(perm_dev)
    c = float(np.corrcoef(real_dev[ok], perm_dev[ok])[0, 1]) if real_dev[ok].std() > 0 else np.nan
    rows.append(dict(candidate=nm, corr_withinblock_dev_real_vs_permuted=c))
BD = pd.DataFrame(rows)
print(BD.to_string(index=False))
OUT["M_BETWEEN_corr_withinblock_dev"] = BD.set_index("candidate").iloc[:, 0].to_dict()

# ------------------------------------------------------------------ STATISTIC-BLINDNESS test
print("\n=== STATISTIC-BLINDNESS (E1_I0040 principle): perturb the blind component ===")
sb = []
for nm in bc:
    if nm in VOID:   # nothing to perturb -- statistic does not exist
        continue
    j = names.index(nm)
    G = gp if is_player[j] else gt
    base = Xz[:, j]
    bm = blockmean_col(base, G)
    dev = base - bm
    if use_between[j]:
        blindpart, other = dev, bm          # BETWEEN null is blind to the within-block deviation
        lbl = "within-block deviation"
    else:
        blindpart, other = bm, dev          # WITHIN null is blind to the block mean
        lbl = "block mean"
    v_x10 = demean_mat((other + 10.0 * blindpart).reshape(-1, 1))[:, 0]
    v_del = demean_mat(other.reshape(-1, 1))[:, 0]
    for k, _ in DEPS:
        cell = "%s|%s" % (nm, k)
        if not bool(BROKEN.set_index("cell").loc[cell, "is_broken"]): continue
        yt = Ytil[k]
        t0 = float(real_t[k][j])
        t10 = float(tvec(yt, v_x10.reshape(-1, 1), NS)[1][0])
        tdel = float(tvec(yt, v_del.reshape(-1, 1), NS)[1][0])
        sb.append(dict(cell=cell, candidate=nm, dep=k, blind_component=lbl,
                       t_as_measured=t0, t_blind_x10=t10, t_blind_deleted=tdel,
                       max_abs_change=max(abs(t10 - t0), abs(tdel - t0))))
SB = pd.DataFrame(sb)
print(SB.to_string(index=False))
print("\n  MIN of max_abs_change over the %d testable broken cells: %.6e"
      % (len(SB), SB["max_abs_change"].min()))
print("  cells where the statistic CANNOT see the blind component (<1e-10): %d"
      % int((SB["max_abs_change"] < 1e-10).sum()))
SB.to_csv(os.path.join(HERE, "_STATISTIC_BLINDNESS.csv"), index=False)
OUT["blindness_min_change"] = float(SB["max_abs_change"].min())
OUT["blindness_n_immune"] = int((SB["max_abs_change"] < 1e-10).sum())
OUT["blindness_n_tested"] = int(len(SB))

with open(os.path.join(HERE, "scripts", "_s03.json"), "w") as fh:
    json.dump(OUT, fh, indent=2, default=str)
print("\nDONE s03")
