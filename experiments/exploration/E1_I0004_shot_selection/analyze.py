"""E1 I0004b -- nulls at the CORRECT grouping level, five-zone family-wise
correction, role/volume concentration, fixed effects, persistence.

WHY THE NULL IS BUILT THE WAY IT IS
-----------------------------------
The regressor is an OPPONENT-TEAM-SEASON quantity: 12 teams x 4 seasons = 48
distinct defensive units, whose value is shared across thousands of rows. In this
program a naive ROW-LEVEL null has twice been shown to be 1.0-3.8x too narrow, and
CLUSTER-ROBUST SEs have been observed to RAISE t in one case and lower it in
another -- they are not a reliable substitute. So the headline p-values here come
from a permutation null built at the OPPONENT-TEAM-SEASON level: the already
computed allowance VALUES are reshuffled across teams within season and re-assigned
to rows. The row-level null is reported alongside so the inflation factor is visible.

THE FIVE-ZONE FAMILY. Every draw permutes TEAM LABELS, and the whole five-zone
allowance vector travels with the team. That preserves the cross-zone correlation
structure, which is what makes a max-t family-wise correction valid here.

D0 -- the defective no-op (permute the grouping KEY then RECOMPUTE the aggregate
from it) -- is run ON PURPOSE as a positive diagnostic. Signature: reproduces the
real number with sd EXACTLY 0.000000.

PARTITION: 2021-2024, inherited from the frames, re-asserted on load and before
every write. R2 convention: plain unweighted OLS, 1 - SSE/SST about the unweighted
mean (D069).
"""
import json
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
PARTITION = [2021, 2022, 2023, 2024]
RA = "Restricted Area"
ZONES = [RA, "In The Paint (Non-RA)", "Mid-Range", "Corner 3", "Above the Break 3"]
N_DRAWS = 5000
N_DRAWS_ROW = 2000
N_DRAWS_D0 = 400
N_DRAWS_FE = 2000
SEED = 20260807
ROLE_CUTS = (6.0, 11.0)

pd.set_option("display.width", 230)


def hdr(s):
    print("\n" + "=" * 100)
    print(s)
    print("=" * 100)


# ================================================================= load ===========
hdr("0. LOAD FRAMES -- exploration partition re-asserted")
SEL = pd.read_parquet(os.path.join(HERE, "selection_frame.parquet"))
CONV = pd.read_parquet(os.path.join(HERE, "conversion_frame.parquet"))
# FILTER-POINT 1
SEL = SEL[SEL["season"].isin(PARTITION)].copy()
CONV = CONV[CONV["season"].isin(PARTITION)].copy()
assert set(SEL["season"].unique()) <= set(PARTITION), "PARTITION VIOLATION"
assert set(CONV["season"].unique()) <= set(PARTITION), "PARTITION VIOLATION"
print(f"  selection_frame  rows={len(SEL):>7}  seasons={sorted(SEL['season'].unique())}")
print(f"  conversion_frame rows={len(CONV):>7}  seasons={sorted(CONV['season'].unique())}")

SEL = SEL.rename(columns={"resid_S1": "y", "OS": "x", "OPP_TEAM_ID": "opp",
                          "player_id": "pid", "TEAM_ID": "team"})
CONV = CONV.rename(columns={"resid": "y", "OC": "x", "OPP_TEAM_ID": "opp",
                            "PLAYER_ID": "pid", "zone_name": "zone"})
CONV["team"] = np.nan

FAMILIES = {"selection": SEL, "conversion": CONV}


# ============================================================ OLS + cluster SE ====
def ols_cluster(y, x, cluster):
    y = np.asarray(y, float)
    X = np.column_stack([np.ones(len(y)), np.asarray(x, float)])
    XtX_inv = np.linalg.inv(X.T @ X)
    b = XtX_inv @ (X.T @ y)
    e = y - X @ b
    sse = float(e @ e)
    sst = float(((y - y.mean()) ** 2).sum())
    n, kp = X.shape
    cl = pd.Series(list(cluster), dtype=object)
    meat = np.zeros((kp, kp))
    for _, idx in cl.groupby(cl.values, sort=False).indices.items():
        u = X[idx].T @ e[idx]
        meat += np.outer(u, u)
    G = cl.nunique()
    adj = (G / max(G - 1, 1)) * ((n - 1) / (n - kp))
    V = XtX_inv @ (adj * meat) @ XtX_inv
    return dict(n=int(n), beta=float(b[1]),
                se_naive=float(np.sqrt(sse / (n - kp) * XtX_inv[1, 1])),
                se_cluster=float(np.sqrt(V[1, 1])), n_clusters=int(G),
                t_cluster=float(b[1] / np.sqrt(V[1, 1])),
                t_naive=float(b[1] / np.sqrt(sse / (n - kp) * XtX_inv[1, 1])),
                r2_unweighted_about_unweighted_mean=float(1 - sse / sst))


def row_stat(y, x):
    y = np.asarray(y, float)
    x = np.asarray(x, float)
    med = float(np.median(x))
    hi = x > med
    return dict(corr=float(np.corrcoef(y, x)[0, 1]),
                beta=float(np.polyfit(x, y, 1)[0]),
                diff=float(y[hi].mean() - y[~hi].mean()))


# =================================== cluster sufficient statistics machinery ======
class ZoneSuff:
    """Sufficient statistics for OLS of y on an OPPONENT-TEAM-SEASON-CONSTANT x.

    When x is constant within cluster, beta / corr / hi-lo diff depend on the data
    only through (n_c, sum(y)_c, x_c) plus SST(y) and N. That makes an exact
    5000-draw permutation at the cluster level essentially free.
    """

    def __init__(self, df, zone, canonical_keys):
        d = df[df["zone"] == zone]
        d = d[["y", "x", "opp", "season"]].dropna()
        self.zone = zone
        self.N = len(d)
        self.y_row = d["y"].to_numpy(float)
        self.x_row = d["x"].to_numpy(float)
        self.season_row = d["season"].to_numpy()
        self.opp_row = d["opp"].to_numpy()
        self.cluster_key = list(canonical_keys)
        pos = {k: i for i, k in enumerate(canonical_keys)}
        inv = np.array([pos[f"{a}_{b}"] for a, b in zip(d["season"], d["opp"])], int)
        K = len(canonical_keys)
        self.nc = np.bincount(inv, minlength=K).astype(float)
        self.Syc = np.bincount(inv, weights=self.y_row, minlength=K)
        self.present = self.nc > 0
        self.xc = np.divide(np.bincount(inv, weights=self.x_row, minlength=K), self.nc,
                            out=np.zeros(K), where=self.present)
        self.Sy = float(self.y_row.sum())
        self.ybar = self.Sy / self.N
        self.SSTy = float(((self.y_row - self.ybar) ** 2).sum())
        self.inv = inv

    def stat(self, xc):
        p = self.present
        nc, Syc = self.nc[p], self.Syc[p]
        xv = xc[p]
        xbar = float((nc * xv).sum() / self.N)
        dx = xv - xbar
        Sxx = float((nc * dx * dx).sum())
        Sxy = float((dx * (Syc - nc * self.ybar)).sum())
        beta = Sxy / Sxx
        corr = Sxy / np.sqrt(Sxx * self.SSTy)
        o = np.argsort(xv, kind="stable")
        cn = np.cumsum(nc[o])
        lo_i = min(int(np.searchsorted(cn, (self.N - 1) / 2.0 + 0.5)), len(o) - 1)
        hi_i = min(int(np.searchsorted(cn, self.N / 2.0 + 0.5)), len(o) - 1)
        med = 0.5 * (xv[o][lo_i] + xv[o][hi_i])
        m = xv > med
        if m.all() or (~m).all():
            diff = np.nan
        else:
            diff = (Syc[m].sum() / nc[m].sum() - Syc[~m].sum() / nc[~m].sum())
        return dict(beta=float(beta), corr=float(corr), diff=float(diff))


def season_groups(keys):
    """keys are 'season_team' strings -> list of index arrays, one per season."""
    seasons = np.array([k.split("_")[0] for k in keys])
    return [np.where(seasons == s)[0] for s in np.unique(seasons)]


def perm_maps(groups, rng):
    """Permute TEAM labels within season. Returns an index array into the cluster
    list such that cluster (s,t) receives the value belonging to (s, pi(t))."""
    n = sum(len(g) for g in groups)
    out = np.arange(n)
    for m in groups:
        out[m] = rng.permutation(m)
    return out


# ======================================================= 1. REAL EFFECT SIZES =====
hdr("1. REAL EFFECT SIZES -- both families, all five zones")
print("  'row-level' uses x as it actually varies within team-season (the reported")
print("  number). 'cluster-level' replaces x by its team-season mean -- this is the")
print("  like-for-like comparator for the permutation null, whose x is by construction")
print("  team-season constant. R2 = plain unweighted OLS, SST about the unweighted mean.\n")
suff = {}
real = {}
CANON = {}
for fam, df in FAMILIES.items():
    d = df.dropna(subset=["y", "x"])
    CANON[fam] = sorted(set(f"{a}_{b}" for a, b in zip(d["season"], d["opp"])))
    suff[fam] = {}
    real[fam] = {}
    print(f"  --- {fam.upper()} ---   canonical clusters (season_opponent) = "
          f"{len(CANON[fam])}")
    print(f"  {'zone':<24}{'n':>8}{'corr':>10}{'diff':>10}{'beta':>10}"
          f"{'SE(cl)':>10}{'t(cl)':>8}{'t(naive)':>10}{'R2':>11}"
          f"   cluster-level corr/beta")
    for z in ZONES:
        S = ZoneSuff(df, z, CANON[fam])
        suff[fam][z] = S
        rs = row_stat(S.y_row, S.x_row)
        oc = ols_cluster(S.y_row, S.x_row,
                         [f"{a}_{b}" for a, b in zip(S.season_row, S.opp_row)])
        cs = S.stat(S.xc)
        real[fam][z] = dict(row=rs, cluster=cs, ols=oc)
        print(f"  {z:<24}{oc['n']:>8}{rs['corr']:>+10.4f}{rs['diff']:>+10.4f}"
              f"{rs['beta']:>+10.4f}{oc['se_cluster']:>10.4f}{oc['t_cluster']:>+8.2f}"
              f"{oc['t_naive']:>+10.2f}{oc['r2_unweighted_about_unweighted_mean']:>11.6f}"
              f"   {cs['corr']:>+9.4f}{cs['beta']:>+9.4f}")
    print()


# ================================ 2. PERMUTATION NULLS AT THE CORRECT LEVEL =======
hdr("2. PERMUTATION NULL -- OPPONENT-TEAM-SEASON LEVEL (the correct grouping level)")
print(f"  {N_DRAWS} draws, seed {SEED}. Team labels are permuted WITHIN SEASON and the")
print("  whole five-zone allowance vector travels with the team, so the cross-zone")
print("  correlation structure survives and max-t across the family is valid.\n")

draws = {}          # draws[fam][z][metric] -> array
for fam in FAMILIES:
    grps = season_groups(CANON[fam])
    rng = np.random.default_rng(SEED + 1)
    acc = {z: {m: np.empty(N_DRAWS) for m in ("beta", "corr", "diff")} for z in ZONES}
    for i in range(N_DRAWS):
        p = perm_maps(grps, rng)
        for z in ZONES:
            S = suff[fam][z]
            st = S.stat(S.xc[p])
            for m in ("beta", "corr", "diff"):
                acc[z][m][i] = st[m]
    draws[fam] = acc
    print(f"  {fam}: {N_DRAWS} draws done ({len(CANON[fam])} clusters "
          f"= {len(set(k.split('_')[1] for k in CANON[fam]))} teams x "
          f"{len(set(k.split('_')[0] for k in CANON[fam]))} seasons)")

# ---------------------------------------------------- row-level (naive) null -----
print(f"\n  Row-level (NAIVE, KNOWN-TOO-NARROW) null for contrast: {N_DRAWS_ROW} draws,")
print("  values shuffled across ROWS within season -- destroys the clustering.")
draws_row = {}
for fam in FAMILIES:
    rng = np.random.default_rng(SEED + 7)
    acc = {z: {m: np.empty(N_DRAWS_ROW) for m in ("beta", "corr", "diff")} for z in ZONES}
    for z in ZONES:
        S = suff[fam][z]
        xr = S.x_row.copy()
        yv = S.y_row
        seasons = S.season_row
        masks = [seasons == ssn for ssn in PARTITION]
        for i in range(N_DRAWS_ROW):
            vv = xr.copy()
            for m in masks:
                vv[m] = rng.permutation(xr[m])
            st = row_stat(yv, vv)
            for k in ("beta", "corr", "diff"):
                acc[z][k][i] = st[k]
    draws_row[fam] = acc
    print(f"  {fam}: row-level null done")

print("\n  INFLATION FACTOR -- sd(correct cluster-level null) / sd(naive row-level null)")
print(f"  {'family':<12}{'zone':<24}{'metric':<7}{'sd cluster':>13}{'sd row':>12}{'inflation':>11}")
inflation = {}
for fam in FAMILIES:
    inflation[fam] = {}
    for z in ZONES:
        inflation[fam][z] = {}
        for m in ("beta", "corr", "diff"):
            sc = float(np.std(draws[fam][z][m], ddof=1))
            sr = float(np.std(draws_row[fam][z][m], ddof=1))
            inflation[fam][z][m] = dict(sd_cluster=sc, sd_row=sr, inflation=float(sc / sr))
            print(f"  {fam:<12}{z:<24}{m:<7}{sc:>13.6f}{sr:>12.6f}{sc / sr:>11.2f}x")


# ============================================ 3. PER-ZONE p AND FAMILY-WISE max-t =
hdr("3. FIVE-ZONE FAMILY-WISE CORRECTION -- max-t permutation")
print("""  Per-zone unadjusted one-sided p = frac{draw beta >= real beta}.
  Family-wise: each zone's beta is standardised by ITS OWN permutation null
  (z = (beta - null mean)/null sd), the maximum z over the five zones is taken
  WITHIN EACH DRAW (the same team permutation across all zones), and the
  family-wise p for a zone is frac{max-over-zones z(draw) >= that zone's real z}.
  Preselected form: ONE-SIDED (the hypothesis is directional -- a defence that
  allows more of something should see more of it). The two-sided max-|z| version is
  reported too, and it is the stricter of the two.\n""")

fw = {}
for fam in FAMILIES:
    zmat = np.empty((N_DRAWS, len(ZONES)))
    zreal = np.empty(len(ZONES))
    nullmu, nullsd = {}, {}
    for j, z in enumerate(ZONES):
        b = draws[fam][z]["beta"]
        mu, sd = float(b.mean()), float(b.std(ddof=1))
        nullmu[z], nullsd[z] = mu, sd
        zmat[:, j] = (b - mu) / sd
        zreal[j] = (real[fam][z]["cluster"]["beta"] - mu) / sd
    maxz = zmat.max(axis=1)
    maxabsz = np.abs(zmat).max(axis=1)
    fw[fam] = {}
    print(f"  --- {fam.upper()} ---")
    print(f"  {'zone':<24}{'real beta':>11}{'null mean':>11}{'null sd':>10}{'z':>8}"
          f"{'p_unadj':>10}{'p_FWE_1s':>11}{'p_FWE_2s':>11}")
    for j, z in enumerate(ZONES):
        b = draws[fam][z]["beta"]
        rb = real[fam][z]["cluster"]["beta"]
        p_un = float(((b >= rb).sum() + 1) / (N_DRAWS + 1))
        p_un_lo = float(((b <= rb).sum() + 1) / (N_DRAWS + 1))
        p_fwe1 = float(((maxz >= zreal[j]).sum() + 1) / (N_DRAWS + 1))
        p_fwe2 = float(((maxabsz >= abs(zreal[j])).sum() + 1) / (N_DRAWS + 1))
        corr_r = real[fam][z]["cluster"]["corr"]
        cb = draws[fam][z]["corr"]
        p_corr = float(((cb >= corr_r).sum() + 1) / (N_DRAWS + 1))
        db = draws[fam][z]["diff"]
        dr = real[fam][z]["cluster"]["diff"]
        p_diff = float(((db >= dr).sum() + 1) / (N_DRAWS + 1))
        fw[fam][z] = dict(real_beta_cluster=rb, real_beta_row=real[fam][z]["row"]["beta"],
                          null_mean=nullmu[z], null_sd=nullsd[z], z=float(zreal[j]),
                          p_unadjusted_one_sided_upper=p_un,
                          p_unadjusted_one_sided_lower=p_un_lo,
                          p_familywise_maxz_one_sided=p_fwe1,
                          p_familywise_maxabsz_two_sided=p_fwe2,
                          p_corr_unadjusted=p_corr, p_diff_unadjusted=p_diff,
                          real_corr_cluster=corr_r, real_diff_cluster=dr,
                          n_draws=N_DRAWS)
        print(f"  {z:<24}{rb:>+11.4f}{nullmu[z]:>+11.4f}{nullsd[z]:>10.4f}"
              f"{zreal[j]:>+8.2f}{p_un:>10.4f}{p_fwe1:>11.4f}{p_fwe2:>11.4f}")
    # row-level real scored against the same correct null (conservative cross-check)
    print(f"  {'':<24}row-level real beta scored against the SAME cluster-level null:")
    for j, z in enumerate(ZONES):
        b = draws[fam][z]["beta"]
        rbr = real[fam][z]["row"]["beta"]
        p = float(((b >= rbr).sum() + 1) / (N_DRAWS + 1))
        fw[fam][z]["p_rowlevel_real_vs_cluster_null"] = p
        print(f"    {z:<24}{rbr:>+11.4f}  p={p:.4f}")
    # naive row-level null p, to show what the WRONG null would have said
    print(f"  {'':<24}what the NAIVE row-level null would have said (WRONG):")
    for j, z in enumerate(ZONES):
        b = draws_row[fam][z]["beta"]
        rbr = real[fam][z]["row"]["beta"]
        p = float(((b >= rbr).sum() + 1) / (N_DRAWS_ROW + 1))
        fw[fam][z]["p_naive_rowlevel_null"] = p
        print(f"    {z:<24}{rbr:>+11.4f}  p_naive={p:.4f}")
    print()


# ============================================================ 4. D0 DEFECTIVE NO-OP
hdr("4. D0 -- THE DEFECTIVE NO-OP, RUN ON PURPOSE (positive diagnostic)")
print("""  Permute the GROUPING KEY and then RECOMPUTE the aggregate from the permuted key.
  A bijective relabel maps each permuted cell onto exactly the same row set under a
  different name, so every row still receives its OWN true value. Expected signature:
  every draw reproduces the real number, sd EXACTLY 0.000000. It tests NOTHING; it is
  here so the genuine controls above can be seen to be genuine by contrast.\n""")
d0_out = {}
for fam in FAMILIES:
    S = suff[fam][RA]
    K = len(S.nc)
    grps = season_groups(CANON[fam])
    rng = np.random.default_rng(SEED + 11)
    ref = S.stat(S.xc)
    dr = {m: np.empty(N_DRAWS_D0) for m in ("beta", "corr", "diff")}
    for i in range(N_DRAWS_D0):
        p = perm_maps(grps, rng)
        # RECOMPUTE the aggregate from the permuted key: relabel rows, then average
        # within the new label. Bijective => identical partition, identical values.
        inv_p = np.empty_like(p)
        inv_p[p] = np.arange(K)
        relabel = inv_p[S.inv]
        nc = np.bincount(relabel, minlength=K).astype(float)
        xc = np.divide(np.bincount(relabel, weights=S.x_row, minlength=K), nc,
                       out=np.zeros(K), where=nc > 0)
        st = S.stat(xc[inv_p])
        for m in ("beta", "corr", "diff"):
            dr[m][i] = st[m]
    sig = all(float(np.max(np.abs(dr[m] - ref[m]))) == 0.0
              and float(np.std(dr[m], ddof=1)) < 1e-12 for m in ("beta", "corr", "diff"))
    d0_out[fam] = dict(zone=RA, kind="DEFECTIVE_NOOP", n_draws=N_DRAWS_D0,
                       reference=ref, defect_signature_confirmed=bool(sig),
                       **{m: dict(mean=float(dr[m].mean()), sd=float(np.std(dr[m], ddof=1)),
                                  max_abs_dev_from_reference=float(np.max(np.abs(dr[m] - ref[m]))))
                          for m in ("beta", "corr", "diff")})
    print(f"  {fam} / {RA}:")
    for m in ("beta", "corr", "diff"):
        print(f"    {m:<5} ref={ref[m]:+.10f}  mean={dr[m].mean():+.10f}  "
              f"sd={np.std(dr[m], ddof=1):.10f}  max|dev|={np.max(np.abs(dr[m] - ref[m])):.2e}")
    print(f"    DEFECT SIGNATURE PRESENT (reproduces the real number, sd exactly 0): {sig}")


# ==================================================== 5. ROLE / VOLUME CONCENTRATION
hdr("5. ROLE / VOLUME CONCENTRATION")
print(f"""  Role feature: role_prior_fga = EWMA_0.30 of the player's FGA per game over their
  STRICTLY PRIOR games this season (the frozen baseline's exposure channel). It reads
  PRIOR GAMES ONLY -- no future information, and no season aggregate.
  Two binnings are reported because they can disagree:
    (a) PRESELECTED ABSOLUTE cut points {ROLE_CUTS} FGA/game  -- fixed before looking;
    (b) WITHIN-SEASON EMPIRICAL TERTILES of the same prior-only feature -- the cut
        points are a function of the cross-sectional distribution of a prior-only
        quantity, so they read no outcome, but they are data-dependent.
  Interaction model (plain unweighted OLS):  y ~ 1 + x + r_c + x*r_c,
  with r_c = role centred at its mean. p-values for the interaction coefficient come
  from the SAME opponent-team-season permutation.\n""")


def role_bins_abs(r):
    return np.where(r < ROLE_CUTS[0], "low", np.where(r < ROLE_CUTS[1], "mid", "high"))


def role_bins_tertile(df, col="role"):
    out = pd.Series(index=df.index, dtype=object)
    for ssn, g in df.groupby("season"):
        q = g[col].quantile([1 / 3, 2 / 3]).to_numpy()
        out.loc[g.index] = np.where(g[col] < q[0], "low",
                                    np.where(g[col] < q[1], "mid", "high"))
    return out


class InterSuff:
    """Sufficient statistics for y ~ 1 + x + r + x*r with x cluster-constant."""

    def __init__(self, y, x, r, inv, ncl):
        self.n = np.bincount(inv, minlength=ncl).astype(float)
        self.Sr = np.bincount(inv, weights=r, minlength=ncl)
        self.Sr2 = np.bincount(inv, weights=r * r, minlength=ncl)
        self.Sy = np.bincount(inv, weights=y, minlength=ncl)
        self.Sry = np.bincount(inv, weights=r * y, minlength=ncl)
        self.N = len(y)
        self.SSTy = float(((y - y.mean()) ** 2).sum())

    def coefs(self, xc):
        n, Sr, Sr2, Sy, Sry = self.n, self.Sr, self.Sr2, self.Sy, self.Sry
        x, x2 = xc, xc * xc
        A = np.array([
            [n.sum(), (x * n).sum(), Sr.sum(), (x * Sr).sum()],
            [(x * n).sum(), (x2 * n).sum(), (x * Sr).sum(), (x2 * Sr).sum()],
            [Sr.sum(), (x * Sr).sum(), Sr2.sum(), (x * Sr2).sum()],
            [(x * Sr).sum(), (x2 * Sr).sum(), (x * Sr2).sum(), (x2 * Sr2).sum()]])
        b = np.array([Sy.sum(), (x * Sy).sum(), Sry.sum(), (x * Sry).sum()])
        return np.linalg.solve(A, b)


role_out = {}
for fam, df in FAMILIES.items():
    role_out[fam] = {}
    if fam == "selection":
        d = df[df["zone"] == RA].dropna(subset=["y", "x", "role_prior_fga"]).copy()
        d["role"] = d["role_prior_fga"]
    else:
        # conversion frame carries no role column; rebuild the same prior-only feature
        # from the selection frame's player-game role (identical construction).
        rr = (SEL[SEL["zone"] == RA][["pid", "season", "game_id", "role_prior_fga"]]
              .drop_duplicates())
        d = df[df["zone"] == RA].merge(
            rr.rename(columns={"game_id": "GAME_ID"}),
            left_on=["pid", "season", "GAME_ID"], right_on=["pid", "season", "GAME_ID"],
            how="inner")
        d = d.dropna(subset=["y", "x", "role_prior_fga"]).copy()
        d["role"] = d["role_prior_fga"]
    d["bin_abs"] = role_bins_abs(d["role"].to_numpy())
    d["bin_ter"] = role_bins_tertile(d)
    key = [f"{a}_{b}" for a, b in zip(d["season"], d["opp"])]
    ukeys, inv = np.unique(np.array(key), return_inverse=True)
    grps = season_groups(list(ukeys))
    ncl = len(ukeys)
    xc_full = np.bincount(inv, weights=d["x"].to_numpy(float), minlength=ncl) / \
        np.bincount(inv, minlength=ncl).astype(float)

    print(f"  --- {fam.upper()} / {RA} ---   n = {len(d)}")
    for binname in ("bin_abs", "bin_ter"):
        lbl = "PRESELECTED absolute cuts" if binname == "bin_abs" else "within-season tertiles"
        print(f"\n  {lbl}")
        print(f"  {'group':<8}{'n':>8}{'mean FGA/g':>12}{'beta':>10}{'SE(cl)':>10}"
              f"{'t(cl)':>8}{'null sd':>10}{'z(perm)':>9}{'p_perm':>9}{'R2':>11}")
        role_out[fam][binname] = {}
        for grp in ("low", "mid", "high"):
            g = d[d[binname] == grp]
            if len(g) < 100:
                continue
            oc = ols_cluster(g["y"], g["x"],
                             [f"{a}_{b}" for a, b in zip(g["season"], g["opp"])])
            ginv = inv[d[binname].to_numpy() == grp]
            gy = g["y"].to_numpy(float)
            gx = g["x"].to_numpy(float)
            gnc = np.bincount(ginv, minlength=ncl).astype(float)
            gSy = np.bincount(ginv, weights=gy, minlength=ncl)
            gxc = np.divide(np.bincount(ginv, weights=gx, minlength=ncl), gnc,
                            out=np.zeros(ncl), where=gnc > 0)
            keep = gnc > 0

            def gstat(xv):
                N = gnc[keep].sum()
                xb = (gnc[keep] * xv[keep]).sum() / N
                dx = xv[keep] - xb
                Sxx = (gnc[keep] * dx * dx).sum()
                yb = gSy[keep].sum() / N
                Sxy = (dx * (gSy[keep] - gnc[keep] * yb)).sum()
                return Sxy / Sxx

            rng = np.random.default_rng(SEED + 21)
            nd = np.empty(N_DRAWS_FE)
            for i in range(N_DRAWS_FE):
                p = perm_maps(grps, rng)
                nd[i] = gstat(gxc[p])
            realb = gstat(gxc)
            sd = float(nd.std(ddof=1))
            pz = float((realb - nd.mean()) / sd)
            pp = float(((nd >= realb).sum() + 1) / (N_DRAWS_FE + 1))
            role_out[fam][binname][grp] = dict(
                n=int(len(g)), mean_role_fga=float(g["role"].mean()),
                beta_row=oc["beta"], beta_cluster=float(realb),
                se_cluster=oc["se_cluster"], t_cluster=oc["t_cluster"],
                perm_null_sd=sd, perm_z=pz, perm_p_one_sided=pp,
                r2_unweighted_about_unweighted_mean=oc["r2_unweighted_about_unweighted_mean"])
            print(f"  {grp:<8}{len(g):>8}{g['role'].mean():>12.2f}{oc['beta']:>+10.4f}"
                  f"{oc['se_cluster']:>10.4f}{oc['t_cluster']:>+8.2f}{sd:>10.4f}"
                  f"{pz:>+9.2f}{pp:>9.4f}"
                  f"{oc['r2_unweighted_about_unweighted_mean']:>11.6f}")

    # ---- continuous interaction
    r = d["role"].to_numpy(float)
    rc = r - r.mean()
    IS = InterSuff(d["y"].to_numpy(float), d["x"].to_numpy(float), rc, inv, ncl)
    creal = IS.coefs(xc_full)
    rng = np.random.default_rng(SEED + 31)
    nd = np.empty(N_DRAWS_FE)
    for i in range(N_DRAWS_FE):
        p = perm_maps(grps, rng)
        nd[i] = IS.coefs(xc_full[p])[3]
    sd = float(nd.std(ddof=1))
    pp2 = float(((np.abs(nd - nd.mean()) >= abs(creal[3] - nd.mean())).sum() + 1)
                / (N_DRAWS_FE + 1))
    role_out[fam]["interaction"] = dict(
        model="y ~ 1 + x + role_centred + x*role_centred (plain unweighted OLS)",
        coef_x=float(creal[1]), coef_role=float(creal[2]), coef_interaction=float(creal[3]),
        perm_null_mean=float(nd.mean()), perm_null_sd=sd,
        perm_z=float((creal[3] - nd.mean()) / sd),
        perm_p_two_sided=pp2, n=int(len(d)), n_draws=N_DRAWS_FE)
    print(f"\n  interaction coef (x * centred role) = {creal[3]:+.5f}   "
          f"null sd = {sd:.5f}   z = {(creal[3] - nd.mean()) / sd:+.2f}   "
          f"two-sided perm p = {pp2:.4f}")
    print(f"  main effect at mean role: {creal[1]:+.4f}\n")


# ============================================================= 6. FIXED EFFECTS ====
hdr("6. FIXED EFFECTS -- is it within-player, or composition?")
print("  Within transformation on the response AND the regressor, then plain OLS.")
print(f"  Permutation p from the same opponent-team-season null ({N_DRAWS_FE} draws).\n")


def fe_beta(y, x, grp):
    gy = y - np.bincount(grp, weights=y) [grp] / np.bincount(grp)[grp]
    gx = x - np.bincount(grp, weights=x)[grp] / np.bincount(grp)[grp]
    return float((gx * gy).sum() / (gx * gx).sum())


fe_out = {}
for fam, df in FAMILIES.items():
    d = df[df["zone"] == RA].dropna(subset=["y", "x"]).copy()
    key = np.array([f"{a}_{b}" for a, b in zip(d["season"], d["opp"])])
    ukeys, inv = np.unique(key, return_inverse=True)
    grps = season_groups(list(ukeys))
    ncl = len(ukeys)
    nc = np.bincount(inv, minlength=ncl).astype(float)
    xc = np.bincount(inv, weights=d["x"].to_numpy(float), minlength=ncl) / nc
    y = d["y"].to_numpy(float)
    fe_out[fam] = {}
    specs = [("player_season", d["pid"].astype(str) + "_" + d["season"].astype(str))]
    if fam == "selection":
        specs.append(("shooting_team_season", d["team"].astype(str) + "_" + d["season"].astype(str)))
    for nm, gs in specs:
        _, gidx = np.unique(gs.to_numpy(), return_inverse=True)
        realb = fe_beta(y, xc[inv], gidx)
        rng = np.random.default_rng(SEED + 41)
        nd = np.empty(N_DRAWS_FE)
        for i in range(N_DRAWS_FE):
            p = perm_maps(grps, rng)
            nd[i] = fe_beta(y, xc[p][inv], gidx)
        sd = float(nd.std(ddof=1))
        pp = float(((nd >= realb).sum() + 1) / (N_DRAWS_FE + 1))
        nog = fe_beta(y, xc[inv], np.zeros(len(y), int))
        fe_out[fam][nm] = dict(beta_no_fe_cluster_x=float(nog), beta_with_fe=float(realb),
                               n_groups=int(gs.nunique()), perm_null_sd=sd,
                               perm_z=float((realb - nd.mean()) / sd),
                               perm_p_one_sided=pp, n=int(len(d)))
        print(f"  {fam:<12}{RA:<20}{nm:<22} beta(no FE)={nog:+.4f}  beta(FE)={realb:+.4f}  "
              f"groups={gs.nunique():>5}  perm z={(realb - nd.mean()) / sd:+.2f}  p={pp:.4f}")


# =============================================================== 7. PERSISTENCE ====
hdr("7. PERSISTENCE -- per season and by half, inside the exploration partition")
pers = {}
for fam, df in FAMILIES.items():
    pers[fam] = {}
    print(f"  --- {fam.upper()} ---")
    print(f"  {'zone':<24}" + "".join(f"{y:>10}" for y in PARTITION)
          + f"{'signs':>8}{'H1':>10}{'H2':>10}")
    for z in ZONES:
        d = df[(df["zone"] == z)].dropna(subset=["y", "x"])
        bs, hs = [], {}
        for ssn in PARTITION:
            g = d[d["season"] == ssn]
            bs.append(float(np.polyfit(g["x"], g["y"], 1)[0]) if len(g) > 50 else np.nan)
        for hn, m in [("2021_2022", d["season"] <= 2022), ("2023_2024", d["season"] >= 2023)]:
            g = d[m]
            hs[hn] = float(np.polyfit(g["x"], g["y"], 1)[0])
        pers[fam][z] = dict(per_season={str(y): b for y, b in zip(PARTITION, bs)},
                            halves=hs, n_positive=int(sum(b > 0 for b in bs)))
        print(f"  {z:<24}" + "".join(f"{b:>+10.4f}" for b in bs)
              + f"{sum(b > 0 for b in bs):>6}/4{hs['2021_2022']:>+10.4f}{hs['2023_2024']:>+10.4f}")
    print()


# ================================================================== 8. WRITE =======
hdr("8. WRITE")
rows = []
for fam in FAMILIES:
    for z in ZONES:
        for m in ("beta", "corr", "diff"):
            for i, v in enumerate(draws[fam][z][m]):
                rows.append((fam, z, m, "cluster_opp_team_season", i, v))
pd.DataFrame(rows, columns=["family", "zone", "metric", "null_level", "draw", "value"]) \
    .to_csv(os.path.join(HERE, "permutation_draws_cluster.csv"), index=False)
rows = []
for fam in FAMILIES:
    for z in ZONES:
        for m in ("beta", "corr", "diff"):
            for i, v in enumerate(draws_row[fam][z][m]):
                rows.append((fam, z, m, "row_naive", i, v))
pd.DataFrame(rows, columns=["family", "zone", "metric", "null_level", "draw", "value"]) \
    .to_csv(os.path.join(HERE, "permutation_draws_rowlevel.csv"), index=False)

payload = dict(
    n_draws_cluster=N_DRAWS, n_draws_row=N_DRAWS_ROW, n_draws_d0=N_DRAWS_D0,
    n_draws_fe=N_DRAWS_FE, seed=SEED, seasons=PARTITION,
    r2_convention="plain unweighted OLS, R2 = 1 - SSE/SST, SST about the UNWEIGHTED mean",
    real={f: {z: real[f][z] for z in ZONES} for f in FAMILIES},
    familywise=fw, inflation_factor=inflation, d0_defective_noop=d0_out,
    role_concentration=role_out, fixed_effects=fe_out, persistence=pers)
json.dump(payload, open(os.path.join(HERE, "analysis_results.json"), "w",
                        encoding="utf-8"), indent=2, default=float)
print("  wrote analysis_results.json, permutation_draws_cluster.csv, "
      "permutation_draws_rowlevel.csv")
print(f"  PARTITION RE-ASSERT: SEL={sorted(SEL['season'].unique())} "
      f"CONV={sorted(CONV['season'].unique())}")
print("\nDone.")
