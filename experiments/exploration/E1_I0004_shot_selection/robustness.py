"""E1 I0004b -- robustness for the selection channel, and the family-wise p-values
for the ROW-LEVEL reals (the numbers actually reported).

THE THING THIS SCRIPT EXISTS TO KILL
------------------------------------
The selection result is positive in ALL FIVE zones, which raises an obvious
mechanical worry: the opponent's prior-games allowed shot-mix is measured against
the offences it happened to face, and one of those offences may be THIS player's
own team, or THIS player. If so, part of the correlation is the shooting team
being correlated with itself. Two stricter regressors are built to test it:

  OS_exT : opponent's prior allowed shares EXCLUDING every prior game against the
           shooting team. Removes the whole own-team channel.
  OS_exP : opponent's prior allowed shares EXCLUDING this player's own prior
           attempts against that opponent. Removes the own-player channel only.

Both remain STRICTLY PRIOR-GAMES-ONLY. Neither was preselected -- both were added
after seeing the headline, as stricter checks; that is disclosed in NOTES.md.

Also here: the S2 own-share baseline (shrunk expanding prior share) instead of S1,
and an attempt-WEIGHTED variant whose R2 uses standard weighted SST about the
WEIGHTED mean, declared as such (D069).

PARTITION: 2021-2024 only, filter-pointed on every load and before every write.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
PARTITION = [2021, 2022, 2023, 2024]
TYPES = ["regular", "playoffs"]
RA = "Restricted Area"
ZONES = [RA, "In The Paint (Non-RA)", "Mid-Range", "Corner 3", "Above the Break 3"]
MIN_PRE_TOTAL = 200
N_DRAWS = 5000
SEED = 20260807
pd.set_option("display.width", 230)


def hdr(s):
    print("\n" + "=" * 100)
    print(s)
    print("=" * 100)


# ============================================================== rebuild raw shots ==
hdr("0. RELOAD RAW SHOTS -- exploration partition only")
dfs = []
for ssn in PARTITION:
    for t in TYPES:
        d = pd.read_parquet(os.path.join(REPO, "data", "shotcharts",
                                         f"shots_{ssn}_{t}.parquet"))
        d["season"] = ssn
        # FILTER-POINT 1
        d = d[d["season"].isin(PARTITION)]
        dfs.append(d)
shots = pd.concat(dfs, ignore_index=True)
# FILTER-POINT 2
shots = shots[shots["season"].isin(PARTITION)].copy()
shots["game_date"] = pd.to_datetime(shots["GAME_DATE"], format="%Y%m%d")
assert shots["game_date"].dt.year.max() <= 2024, "PARTITION VIOLATION"
shots["zone"] = shots["SHOT_ZONE_BASIC"].map(
    lambda z: "Corner 3" if z in ("Left Corner 3", "Right Corner 3") else z)
gt = shots.groupby("GAME_ID")["TEAM_ID"].unique()
opp = {}
for gid, teams in gt.items():
    if len(teams) == 2:
        opp[(gid, teams[0])] = teams[1]
        opp[(gid, teams[1])] = teams[0]
shots["OPP_TEAM_ID"] = [opp.get((g, t), np.nan)
                        for g, t in zip(shots["GAME_ID"], shots["TEAM_ID"])]
shots = shots[shots["OPP_TEAM_ID"].notna()].copy()
shots["OPP_TEAM_ID"] = shots["OPP_TEAM_ID"].astype(shots["TEAM_ID"].dtype)
s5 = shots[shots["zone"].isin(ZONES)].copy()
print(f"  rows={len(s5)}  seasons={sorted(s5['season'].unique())}")

# league prior share, strictly BEFORE the current calendar date
lgd = s5.groupby(["season", "game_date", "zone"]).size().rename("a").reset_index()
lgd = lgd.sort_values(["season", "zone", "game_date"], kind="stable")
lgd["cum"] = lgd.groupby(["season", "zone"], sort=False)["a"].cumsum() - lgd["a"]
lgt = (s5.groupby(["season", "game_date"]).size().rename("t").reset_index()
       .sort_values(["season", "game_date"], kind="stable"))
lgt["cumt"] = lgt.groupby("season", sort=False)["t"].cumsum() - lgt["t"]
lgd = lgd.merge(lgt[["season", "game_date", "cumt"]], on=["season", "game_date"])
lgd["lg_share_prior"] = lgd["cum"] / lgd["cumt"]

# ---- opponent-game totals, all / vs shooting team / vs player
og = (s5.groupby(["OPP_TEAM_ID", "TEAM_ID", "season", "GAME_ID", "game_date", "zone"])
      .size().rename("a").reset_index())
w = og.pivot_table(index=["OPP_TEAM_ID", "TEAM_ID", "season", "GAME_ID", "game_date"],
                   columns="zone", values="a", fill_value=0).reset_index()
for z in ZONES:
    if z not in w.columns:
        w[z] = 0
w = w.sort_values(["OPP_TEAM_ID", "season", "game_date", "GAME_ID"],
                  kind="stable").reset_index(drop=True)
w["tot"] = w[ZONES].sum(axis=1)
ka = [w["OPP_TEAM_ID"], w["season"]]
kt = [w["OPP_TEAM_ID"], w["season"], w["TEAM_ID"]]
w["preA_tot"] = w.groupby(ka, sort=False)["tot"].cumsum() - w["tot"]
w["preT_tot"] = w.groupby(kt, sort=False)["tot"].cumsum() - w["tot"]
for z in ZONES:
    w["preA_" + z] = w.groupby(ka, sort=False)[z].cumsum() - w[z]
    w["preT_" + z] = w.groupby(kt, sort=False)[z].cumsum() - w[z]

# player-level prior contribution to the opponent's allowance
pg = (s5.groupby(["OPP_TEAM_ID", "PLAYER_ID", "season", "GAME_ID", "game_date", "zone"])
      .size().rename("a").reset_index())
pw = pg.pivot_table(index=["OPP_TEAM_ID", "PLAYER_ID", "season", "GAME_ID", "game_date"],
                    columns="zone", values="a", fill_value=0).reset_index()
for z in ZONES:
    if z not in pw.columns:
        pw[z] = 0
pw = pw.sort_values(["OPP_TEAM_ID", "PLAYER_ID", "season", "game_date", "GAME_ID"],
                    kind="stable").reset_index(drop=True)
pw["ptot"] = pw[ZONES].sum(axis=1)
kp = [pw["OPP_TEAM_ID"], pw["season"], pw["PLAYER_ID"]]
pw["preP_tot"] = pw.groupby(kp, sort=False)["ptot"].cumsum() - pw["ptot"]
for z in ZONES:
    pw["preP_" + z] = pw.groupby(kp, sort=False)[z].cumsum() - pw[z]

# ---- long form regressors
recs = []
for z in ZONES:
    a = w[["OPP_TEAM_ID", "TEAM_ID", "season", "GAME_ID", "game_date",
           "preA_tot", "preT_tot", "preA_" + z, "preT_" + z]].copy()
    a["zone"] = z
    a = a.rename(columns={"preA_" + z: "preA_z", "preT_" + z: "preT_z"})
    recs.append(a)
OSW = pd.concat(recs, ignore_index=True)
OSW = OSW.merge(lgd[["season", "game_date", "zone", "lg_share_prior"]],
                on=["season", "game_date", "zone"], how="left")
OSW["den_all"] = OSW["preA_tot"]
OSW["den_exT"] = OSW["preA_tot"] - OSW["preT_tot"]
OSW["OS"] = np.where(OSW["den_all"] >= MIN_PRE_TOTAL,
                     OSW["preA_z"] / OSW["den_all"] - OSW["lg_share_prior"], np.nan)
OSW["OS_exT"] = np.where(OSW["den_exT"] >= MIN_PRE_TOTAL,
                         (OSW["preA_z"] - OSW["preT_z"]) / OSW["den_exT"]
                         - OSW["lg_share_prior"], np.nan)

recs = []
for z in ZONES:
    a = pw[["OPP_TEAM_ID", "PLAYER_ID", "season", "GAME_ID",
            "preP_tot", "preP_" + z]].copy()
    a["zone"] = z
    a = a.rename(columns={"preP_" + z: "preP_z"})
    recs.append(a)
PSW = pd.concat(recs, ignore_index=True)

# ================================================= merge onto the selection frame ==
hdr("1. MERGE ONTO THE SELECTION FRAME")
SEL = pd.read_parquet(os.path.join(HERE, "selection_frame.parquet"))
# FILTER-POINT 3
SEL = SEL[SEL["season"].isin(PARTITION)].copy()
assert set(SEL["season"].unique()) <= set(PARTITION), "PARTITION VIOLATION"
SEL = SEL.merge(OSW[["OPP_TEAM_ID", "season", "GAME_ID", "zone", "OS_exT"]]
                .rename(columns={"GAME_ID": "game_id"}),
                on=["OPP_TEAM_ID", "season", "game_id", "zone"], how="left")
SEL = SEL.merge(PSW.rename(columns={"GAME_ID": "game_id", "PLAYER_ID": "player_id"}),
                on=["OPP_TEAM_ID", "player_id", "season", "game_id", "zone"], how="left")
SEL = SEL.merge(OSW[["OPP_TEAM_ID", "season", "GAME_ID", "zone", "preA_z", "preA_tot",
                     "lg_share_prior"]]
                .rename(columns={"GAME_ID": "game_id",
                                 "lg_share_prior": "lg_chk"}).drop_duplicates(
                    ["OPP_TEAM_ID", "season", "game_id", "zone"]),
                on=["OPP_TEAM_ID", "season", "game_id", "zone"], how="left")
SEL[["preP_z", "preP_tot"]] = SEL[["preP_z", "preP_tot"]].fillna(0.0)
den = SEL["preA_tot"] - SEL["preP_tot"]
SEL["OS_exP"] = np.where(den >= MIN_PRE_TOTAL,
                         (SEL["preA_z"] - SEL["preP_z"]) / den - SEL["lg_chk"], np.nan)
print(f"  rows={len(SEL)}  OS non-null={int(SEL['OS'].notna().sum())}  "
      f"OS_exT non-null={int(SEL['OS_exT'].notna().sum())}  "
      f"OS_exP non-null={int(SEL['OS_exP'].notna().sum())}")
print(f"  sanity: corr(OS, OS_exT) = "
      f"{SEL[['OS', 'OS_exT']].dropna().corr().iloc[0, 1]:.4f}; "
      f"corr(OS, OS_exP) = {SEL[['OS', 'OS_exP']].dropna().corr().iloc[0, 1]:.4f}")


# ============================================================= shared machinery =====
def season_groups(keys):
    seasons = np.array([k.split("_")[0] for k in keys])
    return [np.where(seasons == s)[0] for s in np.unique(seasons)]


def perm_maps(groups, rng):
    n = sum(len(g) for g in groups)
    out = np.arange(n)
    for m in groups:
        out[m] = rng.permutation(m)
    return out


def cluster_perm_beta(d, ycol, xcol, wcol=None, n_draws=N_DRAWS, seed=SEED + 51):
    """Plain unweighted OLS slope (or weighted if wcol given), plus a permutation
    null at the OPPONENT-TEAM-SEASON level. Returns row-level and cluster-level reals."""
    d = d[[ycol, xcol, "season", "OPP_TEAM_ID"] + ([wcol] if wcol else [])].dropna()
    y = d[ycol].to_numpy(float)
    x = d[xcol].to_numpy(float)
    wt = d[wcol].to_numpy(float) if wcol else np.ones(len(d))
    key = np.array([f"{a}_{b}" for a, b in zip(d["season"], d["OPP_TEAM_ID"])])
    uk, inv = np.unique(key, return_inverse=True)
    K = len(uk)
    grps = season_groups(list(uk))
    Wc = np.bincount(inv, weights=wt, minlength=K)
    Syc = np.bincount(inv, weights=wt * y, minlength=K)
    xc = np.bincount(inv, weights=wt * x, minlength=K) / Wc
    W = wt.sum()
    ybar = (wt * y).sum() / W
    # weighted SST about the WEIGHTED mean (declared); == plain SST when wt == 1
    SSTy = float((wt * (y - ybar) ** 2).sum())

    def st(xv):
        xb = (Wc * xv).sum() / W
        dx = xv - xb
        Sxx = (Wc * dx * dx).sum()
        Sxy = (dx * (Syc - Wc * ybar)).sum()
        return Sxy / Sxx, Sxy / np.sqrt(Sxx * SSTy)

    beta_c, corr_c = st(xc)
    xb = (wt * x).sum() / W
    beta_r = float((wt * (x - xb) * (y - ybar)).sum() / (wt * (x - xb) ** 2).sum())
    corr_r = float((wt * (x - xb) * (y - ybar)).sum()
                   / np.sqrt((wt * (x - xb) ** 2).sum() * SSTy))
    # unweighted-OLS R2 (or weighted SST about the weighted mean if wcol given)
    resid = y - (ybar - beta_r * xb) - beta_r * x
    r2 = float(1 - (wt * resid ** 2).sum() / SSTy)
    rng = np.random.default_rng(seed)
    nd = np.empty(n_draws)
    for i in range(n_draws):
        nd[i] = st(xc[perm_maps(grps, rng)])[0]
    mu, sd = float(nd.mean()), float(nd.std(ddof=1))
    return dict(n=int(len(d)), n_clusters=int(K),
                beta_row=beta_r, corr_row=corr_r, beta_cluster=float(beta_c),
                corr_cluster=float(corr_c), r2=r2,
                perm_null_mean=mu, perm_null_sd=sd,
                z_cluster=float((beta_c - mu) / sd), z_row=float((beta_r - mu) / sd),
                p_cluster=float(((nd >= beta_c).sum() + 1) / (n_draws + 1)),
                p_row=float(((nd >= beta_r).sum() + 1) / (n_draws + 1)),
                n_draws=n_draws,
                weighting=("attempt-weighted; SST is standard weighted SST about the "
                           "WEIGHTED mean" if wcol else
                           "unweighted; SST about the UNWEIGHTED mean"))


hdr("2. SELECTION -- stricter opponent regressors, all five zones")
print("""  OS      preselected headline regressor
  OS_exT  drops every prior game the opponent played against the SHOTING team
  OS_exP  drops this player's own prior attempts against the opponent
  Reported: row-level beta (the number carried forward), cluster-level beta (the
  like-for-like comparator for the null), and the opponent-team-season permutation p.\n""")
rob = {}
print(f"  {'zone':<24}{'regressor':<10}{'n':>7}{'beta_row':>10}{'beta_clu':>10}"
      f"{'null sd':>10}{'z_clu':>8}{'p_clu':>9}{'z_row':>8}{'p_row':>9}{'R2':>10}")
for z in ZONES:
    d = SEL[SEL["zone"] == z]
    rob[z] = {}
    for xc_name in ("OS", "OS_exT", "OS_exP"):
        r = cluster_perm_beta(d, "resid_S1", xc_name)
        rob[z][xc_name] = r
        print(f"  {z:<24}{xc_name:<10}{r['n']:>7}{r['beta_row']:>+10.4f}"
              f"{r['beta_cluster']:>+10.4f}{r['perm_null_sd']:>10.4f}"
              f"{r['z_cluster']:>+8.2f}{r['p_cluster']:>9.4f}{r['z_row']:>+8.2f}"
              f"{r['p_row']:>9.4f}{r['r2']:>10.6f}")

hdr("3. SELECTION -- alternative own-share baseline (S2) and attempt weighting")
print("  S2 = expanding attempt-weighted prior-games share shrunk to the expanding prior")
print("  league share (K=50). Same strictly-prior window as S1, different smoothing.")
print("  The weighted row declares standard weighted SST about the WEIGHTED mean (D069).\n")
print(f"  {'zone':<24}{'spec':<28}{'n':>7}{'beta_row':>10}{'beta_clu':>10}"
      f"{'z_clu':>8}{'p_clu':>9}{'R2':>10}")
alt = {}
for z in ZONES:
    d = SEL[SEL["zone"] == z]
    alt[z] = {}
    for nm, yc, wc in [("S1 baseline, unweighted", "resid_S1", None),
                       ("S2 baseline, unweighted", "resid_S2", None),
                       ("S1 baseline, attempt-weighted", "resid_S1", "fga")]:
        r = cluster_perm_beta(d, yc, "OS", wcol=wc)
        alt[z][nm] = r
        print(f"  {z:<24}{nm:<28}{r['n']:>7}{r['beta_row']:>+10.4f}"
              f"{r['beta_cluster']:>+10.4f}{r['z_cluster']:>+8.2f}{r['p_cluster']:>9.4f}"
              f"{r['r2']:>10.6f}")

# ================== 4. FAMILY-WISE p FOR THE ROW-LEVEL REALS (both families) =======
hdr("4. FAMILY-WISE max-t FOR THE ROW-LEVEL REALS (the numbers actually reported)")
print("""  Section 3 of analyze.py corrected the CLUSTER-LEVEL reals. The number carried
  forward is the ROW-LEVEL beta, which is attenuated by within-team-season noise in
  the regressor. Its family-wise p is computed here against the same null, using the
  same per-zone standardisation. This is the STRICTER of the two readings and it is
  the one reported in FINDINGS.json alongside the cluster-level one.\n""")
draws = pd.read_csv(os.path.join(HERE, "permutation_draws_cluster.csv"))
an = json.load(open(os.path.join(HERE, "analysis_results.json"), encoding="utf-8"))
fwrow = {}
for fam in ("selection", "conversion"):
    sub = draws[(draws["family"] == fam) & (draws["metric"] == "beta")]
    mat = np.column_stack([sub[sub["zone"] == z].sort_values("draw")["value"].to_numpy()
                           for z in ZONES])
    mu = mat.mean(axis=0)
    sd = mat.std(axis=0, ddof=1)
    zmat = (mat - mu) / sd
    maxz = zmat.max(axis=1)
    maxabs = np.abs(zmat).max(axis=1)
    nD = mat.shape[0]
    fwrow[fam] = {}
    print(f"  --- {fam.upper()} ---")
    print(f"  {'zone':<24}{'beta_row':>10}{'z_row':>8}{'p_unadj':>10}"
          f"{'p_FWE_1s':>11}{'p_FWE_2s':>11}   {'beta_clu':>9}{'p_FWE_clu':>11}")
    for j, z in enumerate(ZONES):
        br = an["real"][fam][z]["row"]["beta"]
        bc = an["real"][fam][z]["cluster"]["beta"]
        zr = (br - mu[j]) / sd[j]
        zc = (bc - mu[j]) / sd[j]
        p_un = float(((mat[:, j] >= br).sum() + 1) / (nD + 1))
        p1 = float(((maxz >= zr).sum() + 1) / (nD + 1))
        p2 = float(((maxabs >= abs(zr)).sum() + 1) / (nD + 1))
        p1c = float(((maxz >= zc).sum() + 1) / (nD + 1))
        fwrow[fam][z] = dict(beta_row=float(br), z_row=float(zr),
                             p_unadjusted_one_sided=p_un,
                             p_familywise_one_sided=p1, p_familywise_two_sided=p2,
                             beta_cluster=float(bc), z_cluster=float(zc),
                             p_familywise_one_sided_cluster=p1c, n_draws=int(nD))
        print(f"  {z:<24}{br:>+10.4f}{zr:>+8.2f}{p_un:>10.4f}{p1:>11.4f}{p2:>11.4f}"
              f"   {bc:>+9.4f}{p1c:>11.4f}")
    print()

hdr("5. WRITE")
payload = dict(seasons=PARTITION, n_draws=N_DRAWS, seed=SEED,
               min_pre_total=MIN_PRE_TOTAL,
               stricter_opponent_regressors=rob, alternative_baseline=alt,
               familywise_rowlevel=fwrow,
               r2_convention=("plain unweighted OLS 1 - SSE/SST about the UNWEIGHTED "
                              "mean, except the row explicitly labelled "
                              "attempt-weighted, which uses standard weighted SST "
                              "about the WEIGHTED mean"))
assert set(SEL["season"].unique()) <= set(PARTITION), "PARTITION VIOLATION before write"
json.dump(payload, open(os.path.join(HERE, "robustness_results.json"), "w",
                        encoding="utf-8"), indent=2, default=float)
SEL[["zone", "player_id", "season", "game_id", "OPP_TEAM_ID", "resid_S1", "resid_S2",
     "OS", "OS_exT", "OS_exP", "fga", "role_prior_fga"]].to_parquet(
    os.path.join(HERE, "selection_frame_robust.parquet"), index=False)
print(f"  wrote robustness_results.json, selection_frame_robust.parquet")
print(f"  PARTITION RE-ASSERT: {sorted(SEL['season'].unique())}")
print("\nDone.")
