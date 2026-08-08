"""
E0 I0013 -- the sweep itself.

9 candidate possession-volume formulations x 3 raw counting-stat targets = 27 formulation-target
cells.  Plus the deliberate no-op placebo diagnostic and a volume-heterogeneity pass.

Run:  python run_screen.py     (stdout captured to run_log_screen.txt)
Writes: screen_results.json, placebo_draws_*.csv, noop_diagnostic.csv  -- all into THIS directory.
"""
import json
import os
import time

import numpy as np
import pandas as pd

import pv_base as P
import base as B

rng = np.random.default_rng(P.SEED)
t0 = time.time()

# candidate registry lives in run_screen_defs.py (single source of truth, shared with
# run_maxt_robust.py so the two stages cannot drift apart)
from run_screen_defs import CANDS, DIRECTION_LABEL


# --------------------------------------------------------------------------- fast increments
def prep_fast(y, basecols):
    """QR of the base design once; incremental R2 of any single added column is then O(np).

    NOTE worth stating plainly: D and O*D are already IN the base design, so projecting a
    candidate onto the base residual space ALREADY removes overall opponent defence.  The explicit
    residualisation in P.residualize_and_scale therefore does not change the main-effect dR2 by
    even one ulp -- it is identical by linear algebra.  It is still applied, because it does change
    the interaction terms O x Mres and (O*Mexp) x Mres, and because the reported betas are then on
    the residual scale.  The costume rule is enforced either way.
    """
    X = np.column_stack([np.ones(len(y))] + [np.asarray(c, float) for c in basecols])
    Q, _ = np.linalg.qr(X)
    ry = y - Q @ (Q.T @ y)
    sst = float(((y - y.mean()) ** 2).sum())
    return Q, ry, sst


def incr(Q, ry, sst, m):
    m = np.asarray(m, float)
    if not np.all(np.isfinite(m)):
        m = np.where(np.isfinite(m), m, np.nanmean(m[np.isfinite(m)]))
    rm = m - Q @ (Q.T @ m)
    den = float(rm @ rm)
    if den <= 1e-12:
        return 0.0
    return float((ry @ rm) ** 2 / den) / sst


def center_within(v, seas):
    v = np.asarray(v, float)
    out = np.empty_like(v)
    for s in np.unique(seas):
        m = seas == s
        mu = np.nanmean(v[m])
        out[m] = np.where(np.isfinite(v[m]), v[m] - mu, 0.0)
    return out


# ------------------------------------------------------- team panel (cluster-level permutation)
class TeamPanel:
    """Dense (date x team) forward-filled panel of an ALREADY-COMPUTED pregame team field.

    Used for the CLUSTER-LEVEL permutation null: within a season we permute WHICH TEAM's
    already-computed pregame series a row is assigned to.  That destroys the row<->opponent link
    while preserving the team-season clustering structure of the feature, which is the correct
    grouping level for a team-season aggregate (trap 3).

    This is NOT the no-op form.  No grouping key is permuted and no aggregate is recomputed from
    a permuted key; only the ASSIGNMENT of a computed value to a row changes.
    """

    def __init__(self, teampre, field):
        self.field = field
        self.teams, self.dates, self.vals = {}, {}, {}
        for s, g in teampre.groupby("season"):
            piv = (g.pivot_table(index="gdate", columns="team_id", values=field, aggfunc="first")
                     .sort_index().ffill())
            assert piv.shape[1] == 12, "expected 12 teams in season %s, got %d" % (s, piv.shape[1])
            self.teams[s] = piv.columns.to_numpy()
            self.dates[s] = piv.index.to_numpy()
            self.vals[s] = piv.to_numpy(dtype=float)

    def bind(self, frame, keycol):
        n = len(frame)
        A = np.full((n, 12), np.nan)
        col0 = np.zeros(n, dtype=int)
        seas = frame["season"].to_numpy()
        gd = frame["gdate"].to_numpy()
        key = frame[keycol].to_numpy()
        for s in np.unique(seas):
            m = seas == s
            pos = np.searchsorted(self.dates[s], gd[m], side="right") - 1
            A[m, :] = self.vals[s][pos, :]
            tmap = {t: i for i, t in enumerate(self.teams[s])}
            col0[m] = [tmap[k] for k in key[m]]
        return A, col0, seas


def perm_team(A, col0, seas, rng):
    out = np.empty(len(col0))
    for s in np.unique(seas):
        idx = np.where(seas == s)[0]
        pm = rng.permutation(12)
        out[idx] = A[idx, pm[col0[idx]]]
    return out


def block_clusters(frame, keycol):
    df = pd.DataFrame({"i": np.arange(len(frame)), "s": frame["season"].to_numpy(),
                       "k": frame[keycol].to_numpy(), "d": frame["gdate"].to_numpy()})
    df = df.sort_values(["s", "k", "d"])
    groups = {}
    for (s, k), g in df.groupby(["s", "k"], sort=False):
        groups.setdefault(s, []).append(g["i"].to_numpy())
    return groups


def perm_block(groups, v, rng):
    """Cluster-level permutation for a player-level feature: whole player-season blocks of
    ALREADY-COMPUTED values are reassigned to other player-seasons within the same season,
    cycling by position when block lengths differ.  Nothing is recomputed."""
    out = np.empty(len(v))
    for s, blocks in groups.items():
        order = rng.permutation(len(blocks))
        for i, b in enumerate(blocks):
            don = blocks[order[i]]
            out[b] = v[don[np.arange(len(b)) % len(don)]]
    return out


def perm_rows(v, seas, rng):
    """The NAIVE row-level permutation.  Reported ONLY to show how much too narrow the wrong null
    is for a team-season aggregate.  It is never used for a verdict."""
    out = np.empty(len(v))
    for s in np.unique(seas):
        idx = np.where(seas == s)[0]
        out[idx] = rng.permutation(v[idx])
    return out


def summarize(draws, real, label):
    a = np.asarray(draws, float)
    a = a[np.isfinite(a)]
    return dict(label=label, n_draws=int(len(a)), mean=float(a.mean()), sd=float(a.std(ddof=1)),
                p95=float(np.percentile(a, 95)), max=float(a.max()),
                frac_ge_real=float((a >= real).mean()))


# =============================================================================== load
P.hdr("LOAD + PARTITION + HAZARD CHECKS")
mp = B.load_player()
P.guard(mp, "master_player after load")            # FILTER-POINT (applied inside base.load_player)
mt = B.load_team()
P.guard(mt, "master_team after load")              # FILTER-POINT (applied inside base.load_team)
B.poss_sanity(mp)
_pace = pd.to_numeric(mp["pace"], errors="coerce").fillna(0)
print("  HAZARD master_player.pace       : max=%.1f  corr(pace,minutes)=%+.4f  -> CORRUPT, NOT USED"
      % (_pace.max(), float(np.corrcoef(_pace, mp["minutes"].fillna(0))[0, 1])))
print("  HAZARD master_player.possessions: max=%.1f  corr(poss,minutes)=%+.4f  -> CLEAN, USED"
      % (mp["possessions"].max(),
         float(np.corrcoef(mp["possessions"].fillna(0), mp["minutes"].fillna(0))[0, 1])))
print("  HAZARD master_player.position   : lineup-slot label -> NOT USED anywhere in this screen")

TEAM = P.build_team_pre(mt)
print("  team pregame coverage (non-null pace48): %.3f of team-games" % TEAM["pace48"].notna().mean())
PANEL = {f: TeamPanel(TEAM, f) for f in P.TEAM_FIELDS}

opp_ren = {f: "opp_" + f for f in P.TEAM_FIELDS}
own_ren = {f: "own_" + f for f in P.TEAM_FIELDS}

RESULTS = {"cells": [], "noop": None, "heterogeneity": [], "meta": {}}
FRAMES = {}

for T in P.TARGETS:
    P.hdr("TARGET = %s   (RAW COUNTING STAT, not a per-possession rate)" % T.upper())
    d = B.build_base(mp, T)
    d = P.add_player_pregame(d)
    P.guard(d, "player frame target=%s" % T)       # FILTER-POINT

    d = d.merge(TEAM[["season", "game_id", "team_id"] + P.TEAM_FIELDS]
                .rename(columns={"team_id": "opp_team_id", **opp_ren}),
                on=["season", "game_id", "opp_team_id"], how="left")
    d = d.merge(TEAM[["season", "game_id", "team_id"] + P.TEAM_FIELDS].rename(columns=own_ren),
                on=["season", "game_id", "team_id"], how="left")
    d["exp_gposs"] = 0.5 * (d["opp_pace48"] + d["own_pace48"])

    need = ["own_pre", "def_pre", "Mexp", "ppm", "usg_pre", "exp_gposs"] + \
           [c["name"] for c in CANDS if c["side"] in ("opp", "own")]
    W = d[d["is_analysis"]].dropna(subset=need + ["s"]).copy().reset_index(drop=True)
    P.guard(W, "analysis frame target=%s" % T)     # FILTER-POINT
    print("  analysis rows=%d  players=%d  games=%d  per-season n=%s"
          % (len(W), W["player_id"].nunique(), W["game_id"].nunique(),
             {int(k): int(v) for k, v in W.groupby("season").size().items()}))

    W["O"] = B.zwithin(W, "own_pre")
    W["D"] = B.zwithin(W, "def_pre")
    W["OD"] = W["O"] * W["D"]
    W["ME"] = B.zwithin(W, "Mexp")
    W["OME"] = W["O"] * W["ME"]
    y = W["s"].to_numpy(float)
    basecols = [W["O"].values, W["D"].values, W["OD"].values, W["ME"].values, W["OME"].values]
    Q, ry, sst = prep_fast(y, basecols)
    r2b = P.r2(y, basecols)
    print("  BASE  y ~ O + D + O*D + Mexp + O*Mexp    R2_base = %.5f   (plain unweighted OLS, D069)"
          % r2b)
    print("  sanity  R2(Mexp only)=%.5f   R2(O*Mexp only)=%.5f   sd(y)=%.3f"
          % (P.r2(y, [W["ME"].values]), P.r2(y, [W["OME"].values]), y.std()))
    seas = W["season"].to_numpy()
    FRAMES[T] = dict(W=W, y=y, Q=Q, ry=ry, sst=sst, basecols=basecols, seas=seas, r2b=r2b)

    print("\n  %-14s %10s %9s %8s %8s %8s %6s | %8s %8s %8s | %9s %10s"
          % ("candidate", "dR2_M", "beta_M", "t_ols", "t_clust", "G", "coll",
             "plc_mean", "plc_sd", "frac>=", "dR2_OxM", "dR2_XxM"))

    for cd in CANDS:
        nm = cd["name"]
        Mz = B.zwithin(W, nm).to_numpy(float)
        Mres = P.residualize_and_scale(Mz, W["D"].values, W["OD"].values)
        OM = W["O"].values * Mres
        XM = W["OME"].values * Mres

        dR2_M = incr(Q, ry, sst, Mz)
        clus = W[cd["cluster"]].astype(str) + "_" + W["season"].astype(str)
        cs = P.cluster_se(y, basecols + [Mres], clus)
        r_coll, r_coll_per = B.collinearity(W, nm)

        r_m = P.r2(y, basecols + [Mres])
        dR2_OxM = P.r2(y, basecols + [Mres, OM]) - r_m
        dR2_XxM = P.r2(y, basecols + [Mres, XM]) - r_m
        b_OxM = float(P.ols(y, basecols + [Mres, OM])[0][-1])
        b_XxM = float(P.ols(y, basecols + [Mres, XM])[0][-1])

        per_season = []
        for s in P.PARTITION:
            gi = np.where(seas == s)[0]
            if len(gi) < 200:
                continue
            bc = [c[gi] for c in basecols]
            yg = y[gi]
            qg, ryg, sstg = prep_fast(yg, bc)
            per_season.append(dict(season=int(s), n=int(len(gi)),
                                   dR2_M=float(incr(qg, ryg, sstg, Mres[gi])),
                                   beta_M=float(P.ols(yg, bc + [Mres[gi]])[0][-1])))
        signs = [np.sign(r["beta_M"]) for r in per_season]
        same_sign = bool(abs(sum(signs)) == len(signs))

        # ---------------- placebos ----------------
        if cd["side"] in ("opp", "own", "both"):
            keycol = "opp_team_id" if cd["side"] in ("opp", "both") else "team_id"
            A, c0, sq = PANEL[cd["field"]].bind(W, keycol)
            if cd["side"] != "both":
                chk = A[np.arange(len(W)), c0]
                ok = np.isfinite(chk) & np.isfinite(W[nm].values)
                assert ok.mean() > 0.99 and np.allclose(chk[ok], W[nm].values[ok], atol=1e-8), \
                    "panel does not reproduce the real value for %s" % nm
                cl_draws = [incr(Q, ry, sst, center_within(perm_team(A, c0, sq, rng), sq))
                            for _ in range(P.NDRAW)]
            else:
                A2, c02, _ = PANEL["pace48"].bind(W, "team_id")
                cl_draws = [incr(Q, ry, sst, center_within(
                    0.5 * (perm_team(A, c0, sq, rng) + perm_team(A2, c02, sq, rng)), sq))
                    for _ in range(P.NDRAW)]
            cl_label = "cluster permutation: team-season -> row assignment permuted within season"
        else:
            groups = block_clusters(W, cd["cluster"])
            v = W[nm].to_numpy(float)
            cl_draws = [incr(Q, ry, sst, center_within(perm_block(groups, v, rng), seas))
                        for _ in range(P.NDRAW)]
            cl_label = "cluster permutation: player-season blocks reassigned within season"

        naive = [incr(Q, ry, sst, center_within(perm_rows(W[nm].to_numpy(float), seas, rng), seas))
                 for _ in range(P.NDRAW)]

        plc = summarize(cl_draws, dR2_M, cl_label)
        plc_naive = summarize(naive, dR2_M, "NAIVE row-level permutation (reported for contrast "
                                            "only; too narrow for a team aggregate)")

        pd.DataFrame({"cluster_perm_dR2_M": cl_draws, "naive_row_perm_dR2_M": naive}) \
            .to_csv(os.path.join(P.OUT, "placebo_draws_%s_%s.csv" % (T, nm)), index=False)

        print("  %-14s %10.6f %9.4f %8.2f %8.2f %8d %+6.2f | %8.6f %8.6f %8.3f | %9.6f %10.6f"
              % (nm, dR2_M, cs["beta"], cs["t_classical"], cs["t_cluster"], cs["n_clusters"],
                 r_coll, plc["mean"], plc["sd"], plc["frac_ge_real"], dR2_OxM, dR2_XxM))

        RESULTS["cells"].append(dict(
            target=T, candidate=nm, direction=cd["direction"],
            direction_label=DIRECTION_LABEL[cd["direction"]],
            construction=cd["construction"], cluster_key=cd["cluster"], n=int(len(W)),
            R2_base=float(r2b), dR2_M=float(dR2_M), beta_M=cs["beta"],
            se_classical=cs["se_classical"], t_classical=cs["t_classical"],
            se_cluster=cs["se_cluster"], t_cluster=cs["t_cluster"],
            n_clusters=cs["n_clusters"],
            collinearity_vs_overall_opp_def=float(r_coll),
            collinearity_per_season={str(k): float(v) for k, v in r_coll_per.items()},
            dR2_OxM=float(dR2_OxM), beta_OxM=b_OxM, dR2_XxM=float(dR2_XxM), beta_XxM=b_XxM,
            per_season=per_season, beta_same_sign_all_seasons=same_sign,
            placebo=plc, placebo_naive_row_level=plc_naive))

print("\n[stage 1 (27 cells) done in %.1fs]" % (time.time() - t0))

# ====================================================================== NO-OP DIAGNOSTIC (trap 4)
P.hdr("DELIBERATE NO-OP PLACEBO DIAGNOSTIC (run on purpose; expect sd EXACTLY 0.000000)")
print("""  Defective form: permute the GROUPING KEY (team_id / opp_team_id) consistently everywhere
  and then RECOMPUTE the team aggregate from the permuted key.  The permuted cell is the same row
  set under a bijection, so every row still receives its own true value.  Signature: the real
  number is reproduced with sd exactly 0.000000.""")
Tn = "pts"
F = FRAMES[Tn]
Wn, yn, Qn, ryn, sstn, seasn = F["W"], F["y"], F["Q"], F["ry"], F["sst"], F["seas"]
real_noop = incr(Qn, ryn, sstn, B.zwithin(Wn, "opp_pace48").to_numpy(float))
noop_draws = []
mt_keys = mt[["season", "team_id"]].drop_duplicates()
for it in range(P.NDRAW):
    mt2 = mt.copy()
    newt = np.empty(len(mt2), dtype="int64")
    newo = np.empty(len(mt2), dtype="int64")
    mapping = {}
    for s in P.PARTITION:
        tids = np.sort(mt_keys.loc[mt_keys["season"] == s, "team_id"].to_numpy())
        mapping[s] = dict(zip(tids, rng.permutation(tids)))
    for i, (s, a, b_) in enumerate(zip(mt2["season"].to_numpy(), mt2["team_id"].to_numpy(),
                                       mt2["opp_team_id"].to_numpy())):
        newt[i] = mapping[s][a]
        newo[i] = mapping[s][b_]
    mt2["team_id"] = newt
    mt2["opp_team_id"] = newo
    # recompute the aggregate FROM THE PERMUTED KEY (this is the defect being demonstrated)
    tp = B.team_possessions(mt2)
    t = mt2.merge(tp[["game_id", "team_id", "team_poss"]], on=["game_id", "team_id"], how="left")
    t["n_poss"] = t["team_poss"]
    t["n_min"] = pd.to_numeric(t["minutes"], errors="coerce")
    p_ = B.prior_expanding(t, ["season", "team_id"], ["n_poss", "n_min"], "pr_")
    gm = p_["pr_n_min"] / 5.0
    v = np.where(gm > 0, p_["pr_n_poss"] * 48.0 / gm, np.nan)
    v = np.where(p_["pr_n_poss"] >= P.MIN_PRIOR_POSS_TEAM, v, np.nan)
    TE2 = p_[["season", "game_id", "team_id"]].copy()
    TE2["pace48_noop"] = v
    Wn2 = Wn[["season", "game_id", "team_id", "opp_team_id"]].copy()
    Wn2["opp_team_id"] = [mapping[s][k] for s, k in zip(Wn2["season"], Wn2["opp_team_id"])]
    Wn2 = Wn2.merge(TE2.rename(columns={"team_id": "opp_team_id"}),
                    on=["season", "game_id", "opp_team_id"], how="left")
    noop_draws.append(incr(Qn, ryn, sstn, center_within(Wn2["pace48_noop"].to_numpy(float), seasn)))

noop = summarize(noop_draws, real_noop, "DEFECTIVE no-op: grouping key permuted, aggregate recomputed")
noop["real_dR2_M"] = float(real_noop)
noop["max_abs_deviation_from_real"] = float(np.max(np.abs(np.array(noop_draws) - real_noop)))
pd.DataFrame({"noop_dR2_M": noop_draws}).to_csv(os.path.join(P.OUT, "noop_diagnostic.csv"), index=False)
print("  cell = opp_pace48 x pts")
print("  real dR2_M                = %.10f" % real_noop)
print("  no-op mean                = %.10f" % noop["mean"])
print("  no-op sd                  = %.10f   <-- the defect signature" % noop["sd"])
print("  max |draw - real|         = %.3e" % noop["max_abs_deviation_from_real"])
real_cell = [c for c in RESULTS["cells"] if c["target"] == "pts" and c["candidate"] == "opp_pace48"][0]
print("  BY CONTRAST the real cluster placebo for the same cell: mean=%.8f sd=%.8f (non-degenerate)"
      % (real_cell["placebo"]["mean"], real_cell["placebo"]["sd"]))
RESULTS["noop"] = noop

# ====================================================================== HETEROGENEITY (direction 5)
P.hdr("VOLUME HETEROGENEITY (direction 5): terciles of pregame minutes and pregame usage")
HET_CANDS = ["ppm", "opp_pace48", "exp_gposs", "opp_orebA100", "opp_missO48"]
for T in P.TARGETS:
    F = FRAMES[T]
    W, y, basecols, seas = F["W"], F["y"], F["basecols"], F["seas"]
    for split in ["Mexp", "usg_pre"]:
        q = W.groupby("season")[split].transform(
            lambda x: pd.qcut(x, 3, labels=[0, 1, 2], duplicates="drop"))
        q = pd.to_numeric(q.astype("object"), errors="coerce").to_numpy(dtype=float)
        for nm in HET_CANDS:
            Mz = B.zwithin(W, nm).to_numpy(float)
            Mres = P.residualize_and_scale(Mz, W["D"].values, W["OD"].values)
            row = dict(target=T, candidate=nm, split=split, terciles=[])
            for tq in [0, 1, 2]:
                gi = np.where(q == tq)[0]
                if len(gi) < 300:
                    continue
                bc = [c[gi] for c in basecols]
                qg, ryg, sstg = prep_fast(y[gi], bc)
                row["terciles"].append(dict(
                    tercile=int(tq), n=int(len(gi)),
                    mean_split=float(W[split].to_numpy()[gi].mean()),
                    dR2_M=float(incr(qg, ryg, sstg, Mres[gi])),
                    beta_M=float(P.ols(y[gi], bc + [Mres[gi]])[0][-1])))
            RESULTS["heterogeneity"].append(row)
            print("  %-4s %-13s by %-8s  " % (T, nm, split) +
                  "  ".join("T%d n=%d dR2=%.6f b=%+.4f"
                            % (r["tercile"], r["n"], r["dR2_M"], r["beta_M"])
                            for r in row["terciles"]))

# ====================================================================== write
RESULTS["meta"] = dict(
    seasons=P.PARTITION, n_cells=len(RESULTS["cells"]), n_draws=P.NDRAW, seed=P.SEED,
    r2_convention="plain unweighted OLS R2 = 1 - SSE/SST, SST about the unweighted mean (D069). "
                  "No weighted regression anywhere; the defective wls_r2 helper is not imported.",
    base_model="y_count ~ O + D + O*D + Mexp + O*Mexp",
    elapsed_sec=round(time.time() - t0, 1))
with open(os.path.join(P.OUT, "screen_results.json"), "w", encoding="utf-8") as f:
    json.dump(RESULTS, f, indent=1, default=float)
print("\n  wrote screen_results.json   (%d cells, %.1fs total)"
      % (len(RESULTS["cells"]), time.time() - t0))
