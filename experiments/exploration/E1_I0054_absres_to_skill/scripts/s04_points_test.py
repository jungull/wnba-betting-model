"""S04 -- PART S.  THE CENTRAL TEST: does forecasting |residual| improve a forecast of POINTS?

D101 for EVERY number in this file and in SKILL_OR_VARIANCE.md:
  response   y_pts -- total box points
  row set    A4_CLEAN_DEC scored rows (2023-24, n_prior>=8 & prior5 minutes>=24), date-sorted
  SST basis  sum (y_pts - ybar)^2 over the scored rows, about the UNWEIGHTED mean
  weighting  none in the metric; weighting appears only inside a channel's fit
  base       B_PTS = [1, pts__pred_point, minutes__pred_point, pl_pts_mean5, pl_min_mean5,
                      pl_fga_mean5, pl_usg_mean5, pl_start_frac5]
  fit kind   out-of-fold (WF expanding-window primary, GKF secondary)
  statistic  paired dR2 = (SSE_ref - SSE_treat)/SST
  reference  TUNED ridge on B_PTS, lambda by inner time-ordered CV on the training window

Every channel is run FROZEN and UNFROZEN.  Both are reported.
Cluster sign-flip at player-season (primary) and team-season (secondary), R = 5000.
"""
import json, os, sys, time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *  # noqa
from _wf import *      # noqa

ARM = "A4_CLEAN_DEC"
R_SIGNFLIP = 5000
B_PLACEBO = 300
LAM_GRID = [10.0 ** e for e in range(-4, 5)]
THETA_GRID = np.round(np.arange(0.0, 1.001, 0.05), 3)
POWERS = [1, 2]
QS = [10, 20, 30]

mask = ARM_MASKS[ARM]
idx = np.where(mask)[0]
sub0 = f.iloc[idx]
order = np.lexsort((sub0["row_uid"].to_numpy(), sub0["gdate"].to_numpy()))
idx = idx[order]
sub = f.iloc[idx].reset_index(drop=True)
XA = X[idx, :]
y = sub["y_pts"].to_numpy(float)
gdate = sub["gdate"].to_numpy()
pid = sub["player_id"].to_numpy()
seasR = sub["season"].to_numpy()
psblock = pd.factorize(pd.Series(list(zip(seasR, pid))))[0]
tsblock = pd.factorize(pd.Series(list(zip(seasR, sub["team_id"]))))[0]
m = len(sub)
NB = psblock.max() + 1
print("ARM %s  n=%d  player-season blocks=%d  team-season blocks=%d"
      % (ARM, m, NB, tsblock.max() + 1), flush=True)

B_PTS = ["pts__pred_point", "minutes__pred_point", "pl_pts_mean5", "pl_min_mean5",
         "pl_fga_mean5", "pl_usg_mean5", "pl_start_frac5"]
BCOL = [NAME_IX[c] for c in B_PTS]

s01 = json.load(open(os.path.join(HERE, "scripts", "_s01.json")))
THE16 = s01["sets"][str(SEEDS[0])]
VSIG_PTS = sorted({c.split("|")[0] for c in THE16 if c.split("|")[1].split("_")[0] == "pts"})
VALL = list(names)
print("  VSIG[pts] variance-model features: %s" % VSIG_PTS, flush=True)
VCOL = {"VSIG": [NAME_IX[c] for c in VSIG_PTS],
        "VALL": [NAME_IX[c] for c in VALL],
        "VSD": [NAME_IX["pts__pred_sd"]],
        "VLEV": [NAME_IX[MATCHED_LEVEL["pts"]]]}

FOLDS = {"WF": folds_wf(gdate, MIN_TRAIN), "GKF": folds_gkf(pid)}
SCORED = {k: np.sort(np.concatenate([te for _, te in v])) for k, v in FOLDS.items()}
print("  WF folds %d scored %d | GKF folds %d scored %d"
      % (len(FOLDS["WF"]), len(SCORED["WF"]), len(FOLDS["GKF"]), len(SCORED["GKF"])), flush=True)

absres_pts = sub["absres_pts"].to_numpy(float)

# ------------------------------------------------------------- player-season blocks, local
BLOCKS_BY_SEASON = {}
for b in range(NB):
    r = np.where(psblock == b)[0]
    BLOCKS_BY_SEASON.setdefault(int(seasR[r[0]]), []).append(r)


def composed2_local(rng):
    ix = np.arange(m)
    for s, bl in BLOCKS_BY_SEASON.items():
        o = rng.permutation(len(bl))
        for i, b in enumerate(bl):
            don = bl[o[i]]
            ix[b] = don[rng.integers(0, len(don), len(b))]
    return ix


# ---------------------------------------------------------------------- the pipeline
def run_pipeline(folds, Xcand, vmodel="VSIG", seed=20260808):
    """One full out-of-fold pass.  Returns a dict of channel -> (yhat over all rows, nan
    where unscored) plus the out-of-fold vhat.  Xcand is the candidate matrix used for the
    VARIANCE model only; the mean base always comes from the real XA."""
    vcols = VCOL[vmodel]
    P = {}
    def put(k, te, val):
        P.setdefault(k, np.full(m, np.nan))[te] = val

    vhat_oof = np.full(m, np.nan)
    for tr, te in folds:
        # ---- variance model on the training window (in-sample for tr, out-of-sample for te)
        Xv_tr = Xcand[np.ix_(tr, vcols)]
        lamv = tune_lambda(Xv_tr, absres_pts[tr], LAM_GRID) if len(vcols) > 3 else 0.0
        av, bv = ridge_fit(Xv_tr, absres_pts[tr], lamv)
        v_tr = np.maximum(av + Xv_tr @ bv, 1e-6)
        v_te = np.maximum(av + Xcand[np.ix_(te, vcols)] @ bv, 1e-6)
        vhat_oof[te] = v_te

        # ---- tuned reference
        Xb_tr, Xb_te = XA[np.ix_(tr, BCOL)], XA[np.ix_(te, BCOL)]
        lam = tune_lambda(Xb_tr, y[tr], LAM_GRID)
        a0, b0 = ridge_fit(Xb_tr, y[tr], lam)
        ref_tr = a0 + Xb_tr @ b0
        ref_te = a0 + Xb_te @ b0
        put("REF", te, ref_te)
        put("RAW_INCUMBENT", te, XA[te, NAME_IX["pts__pred_point"]])
        mref_tr = float(ref_tr.mean())

        def emit(tag, tr_fit, te_fit):
            put(tag + "|UNFROZEN", te, te_fit)
            put(tag + "|FROZEN", te, te_fit - (float(tr_fit.mean()) - mref_tr))

        # ---- S1 variance-weighted fitting
        c = float(np.percentile(v_tr, 10))
        for p in POWERS:
            w = 1.0 / np.maximum(v_tr, c) ** p
            w = w / w.mean()
            aw, bw = wls_fit(Xb_tr, y[tr], w, lam=lam)
            emit("S1_WLS_p%d" % p, aw + Xb_tr @ bw, aw + Xb_te @ bw)

        # ---- S2 shrinkage proportional to predicted error, theta tuned on the training window
        med = float(np.median(v_tr))
        best, bth = np.inf, 0.0
        for th in THETA_GRID:
            k = 1.0 / (1.0 + th * (v_tr / med - 1.0))
            pr = y[tr].mean() + k * (ref_tr - y[tr].mean())
            e = y[tr] - pr
            s = float(e @ e)
            if s < best:
                best, bth = s, th
        kt = 1.0 / (1.0 + bth * (v_te / med - 1.0))
        ktr = 1.0 / (1.0 + bth * (v_tr / med - 1.0))
        emit("S2_SHRINK", y[tr].mean() + ktr * (ref_tr - y[tr].mean()),
             y[tr].mean() + kt * (ref_te - y[tr].mean()))
        put("S2_theta", te, np.full(len(te), bth))

        # ---- S3 mean augmentation
        A_tr = np.column_stack([Xb_tr, v_tr]); A_te = np.column_stack([Xb_te, v_te])
        la = tune_lambda(A_tr, y[tr], LAM_GRID)
        a3, b3 = ridge_fit(A_tr, y[tr], la)
        emit("S3_ADD_VHAT", a3 + A_tr @ b3, a3 + A_te @ b3)
        I_tr = np.column_stack([A_tr, v_tr * XA[tr, NAME_IX["pts__pred_point"]]])
        I_te = np.column_stack([A_te, v_te * XA[te, NAME_IX["pts__pred_point"]]])
        li = tune_lambda(I_tr, y[tr], LAM_GRID)
        a3i, b3i = ridge_fit(I_tr, y[tr], li)
        emit("S3_ADD_VHAT_X_LEVEL", a3i + I_tr @ b3i, a3i + I_te @ b3i)

        # ---- S4 two-stage: variance model on THIS mean model's own residuals, then GLS
        r_tr = np.abs(y[tr] - ref_tr)
        lam2 = tune_lambda(Xv_tr, r_tr, LAM_GRID) if len(vcols) > 3 else 0.0
        a2, b2 = ridge_fit(Xv_tr, r_tr, lam2)
        v2_tr = np.maximum(a2 + Xv_tr @ b2, 1e-6)
        v2_te = np.maximum(a2 + Xcand[np.ix_(te, vcols)] @ b2, 1e-6)
        c2 = float(np.percentile(v2_tr, 10))
        w2 = 1.0 / np.maximum(v2_tr, c2) ** 2
        w2 = w2 / w2.mean()
        ag, bg = wls_fit(Xb_tr, y[tr], w2, lam=lam)
        emit("S4_TWOSTAGE", ag + Xb_tr @ bg, ag + Xb_te @ bg)

        # ---- S5 abstention thresholds from the TRAINING window only
        for q in QS:
            put("S5_keep_q%d" % q, te, (v_te <= np.percentile(v_tr, 100 - q)).astype(float))
    P["VHAT"] = vhat_oof
    return P


def score(P, scored, cluster_primary, cluster_secondary, tag, scheme, vmodel):
    yy = y[scored]
    sst = float(((yy - yy.mean()) ** 2) .sum())
    e_ref = yy - P["REF"][scored]
    out = []
    base = dict(arm=ARM, scheme=scheme, variance_model=vmodel, response="y_pts",
                n_scored=int(len(scored)), n_blocks_primary=int(len(np.unique(cluster_primary))),
                SST=sst, R_signflip=R_SIGNFLIP,
                base_columns=";".join(B_PTS), reference="TUNED_RIDGE_ON_B_PTS")
    r2ref = 1.0 - float((e_ref @ e_ref)) / sst
    for k in sorted(P):
        if k in ("REF", "VHAT", "S2_theta") or k.startswith("S5_keep"):
            continue
        yh = P[k][scored]
        if not np.isfinite(yh).all():
            continue
        e = yy - yh
        d = e_ref ** 2 - e ** 2
        dr2 = float(d.sum()) / sst
        obs, p1, draws = signflip_p(d, cluster_primary, R_SIGNFLIP, seed=20260808)
        _o, p2, _d = signflip_p(d, cluster_secondary, R_SIGNFLIP, seed=20260809)
        ch, fro = (k.split("|") + ["NA"])[:2] if "|" in k else (k, "NA")
        rec = dict(base, channel=ch, intercept_arm=fro,
                   r2_reference=r2ref, r2_treatment=1.0 - float(e @ e) / sst,
                   delta_r2_points=dr2,
                   rmse_reference=float(np.sqrt((e_ref ** 2).mean())),
                   rmse_treatment=float(np.sqrt((e ** 2).mean())),
                   signflip_p_player_season=p1, signflip_p_team_season=p2,
                   floor_points_K1=FLOOR_POINTS_K1, floor_points_K132=FLOOR_POINTS_K132,
                   clears_floor_K1=bool(dr2 >= FLOOR_POINTS_K1),
                   improves_points_PREREG_RULE=bool(dr2 > 0 and p1 < 0.05
                                                    and dr2 >= FLOOR_POINTS_K1))
        out.append(rec)
    # the raw incumbent, for context only
    return out


t0 = time.time()
rows, s5rows = [], []
for scheme, folds in FOLDS.items():
    scored = SCORED[scheme]
    for vmodel in ("VSIG", "VALL", "VSD", "VLEV"):
        P = run_pipeline(folds, XA, vmodel=vmodel)
        rows += score(P, scored, psblock[scored], tsblock[scored], "main", scheme, vmodel)
        if vmodel == "VSIG":
            np.savez_compressed(os.path.join(RAW, "points_test_%s_%s.npz" % (scheme, vmodel)),
                                arm=np.array([ARM]), scheme=np.array([scheme]),
                                vmodel=np.array([vmodel]),
                                row_uid=sub["row_uid"].to_numpy().astype(str),
                                season=seasR, player_id=pid,
                                team_id=sub["team_id"].to_numpy(),
                                gdate=gdate.astype("datetime64[D]").astype(int),
                                player_season_block=psblock, team_season_block=tsblock,
                                scored=scored, y_pts=y,
                                **{("pred__" + k): v for k, v in P.items()})
        # ---- S5 abstention, scored on MSE only (explicitly NOT a dR2 skill claim)
        yy = y[scored]
        e_ref = yy - P["REF"][scored]
        mse_all = float((e_ref ** 2).mean())
        rng = np.random.default_rng(20260808)
        for q in QS:
            keep = P["S5_keep_q%d" % q][scored] > 0.5
            if keep.sum() < 50:
                continue
            mse_keep = float((e_ref[keep] ** 2).mean())
            k = int(keep.sum())
            rand = np.array([float((e_ref[rng.choice(len(yy), k, replace=False)] ** 2).mean())
                             for _ in range(2000)])
            s5rows.append(dict(arm=ARM, scheme=scheme, variance_model=vmodel,
                               response="y_pts", q_dropped_pct=q, n_scored=int(len(scored)),
                               n_retained=k, mse_all_scored=mse_all, mse_retained=mse_keep,
                               mse_reduction_vs_all=1.0 - mse_keep / mse_all,
                               mse_random_subset_mean=float(rand.mean()),
                               mse_random_subset_q025=float(np.percentile(rand, 2.5)),
                               p_vs_random_subsets=float((np.sum(rand <= mse_keep) + 1)
                                                         / (len(rand) + 1)),
                               NOTE="abstention changes WHICH rows are forecast, not the "
                                    "forecast; this is a variance result, not a skill result"))
        print("  %-4s %-5s done (%.0fs)" % (scheme, vmodel, time.time() - t0), flush=True)

S = pd.DataFrame(rows)
S.to_csv(os.path.join(HERE, "POINTS_TEST.csv"), index=False)
pd.DataFrame(s5rows).to_csv(os.path.join(HERE, "ABSTENTION.csv"), index=False)
print("\nwrote POINTS_TEST.csv %s and ABSTENTION.csv" % (S.shape,))
pd.set_option("display.width", 250)
print("\n=== WF / VSIG -- the preregistered primary ===")
print(S[(S.scheme == "WF") & (S.variance_model == "VSIG")]
      [["channel", "intercept_arm", "r2_reference", "r2_treatment", "delta_r2_points",
        "signflip_p_player_season", "signflip_p_team_season", "clears_floor_K1",
        "improves_points_PREREG_RULE"]].round(6).to_string(index=False))
print("\n=== any channel meeting the preregistered decision rule, ANY scheme/vmodel ===")
w = S[S.improves_points_PREREG_RULE]
print("NONE" if not len(w) else w.to_string(index=False))

# ------------------------------------------------------- T2 : Type-I of the PART S statistic
print("\n=== T2 placebo (%d replicates, GKF scheme; see DEFECTS for why not WF) ===" % B_PLACEBO,
      flush=True)
pl = []
for b in range(B_PLACEBO):
    rng = np.random.default_rng(20261000 + b)
    ix = composed2_local(rng)
    Xperm = XA.copy()
    for c in VCOL["VSIG"]:
        Xperm[:, c] = XA[ix, c]
    P = run_pipeline(FOLDS["GKF"], Xperm, vmodel="VSIG")
    sc = SCORED["GKF"]
    for r in score(P, sc, psblock[sc], tsblock[sc], "placebo", "GKF", "VSIG"):
        pl.append(dict(replicate=b, channel=r["channel"], intercept_arm=r["intercept_arm"],
                       delta_r2_points=r["delta_r2_points"],
                       signflip_p_player_season=r["signflip_p_player_season"]))
    if (b + 1) % 50 == 0:
        print("   placebo %d/%d (%.0fs)" % (b + 1, B_PLACEBO, time.time() - t0), flush=True)
PL = pd.DataFrame(pl)
PL.to_csv(os.path.join(HERE, "_T2_PLACEBO_RAW.csv"), index=False)
g = PL.groupby(["channel", "intercept_arm"]).agg(
    n=("delta_r2_points", "size"),
    mean_signed_delta_r2=("delta_r2_points", "mean"),
    sd_signed_delta_r2=("delta_r2_points", "std"),
    typeI_at_0p05=("signflip_p_player_season", lambda s: float((s < 0.05).mean()))).reset_index()
g["centred_ok_abs_mean_lt_2e-4"] = g["mean_signed_delta_r2"].abs() < 2e-4
g["arm"] = ARM
g.to_csv(os.path.join(HERE, "_T2_PLACEBO.csv"), index=False)
print(g.round(6).to_string(index=False))
np.savez_compressed(os.path.join(RAW, "t2_placebo_draws.npz"),
                    arm=np.array([ARM]), B=np.array([B_PLACEBO]),
                    channel=PL["channel"].to_numpy().astype(str),
                    intercept_arm=PL["intercept_arm"].to_numpy().astype(str),
                    replicate=PL["replicate"].to_numpy(),
                    delta_r2_points=PL["delta_r2_points"].to_numpy(),
                    p_player_season=PL["signflip_p_player_season"].to_numpy())
json.dump(dict(n_scored=({k: int(len(v)) for k, v in SCORED.items()}),
               vsig_pts=VSIG_PTS, b_placebo=B_PLACEBO,
               any_channel_improves=bool(len(w) > 0)),
          open(os.path.join(HERE, "scripts", "_s04.json"), "w"), indent=2)
print("\nDONE s04 (%.0fs)" % (time.time() - t0))
