"""E1_I0039 s04 -- BUILD the fit frame and the three components.  Ends with anchor A8.

Nothing here evaluates a lattice cell.  A8 is a REPRODUCTION of E1_I0034's published P04 minutes
number on E1_I0034's own row set; the screen HALTS if it does not reproduce.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import stk_base as B  # noqa: E402

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 60)

# ---------------------------------------------------------------- prereg guard
import hashlib, json  # noqa: E402
spec = json.load(open(os.path.join(B.OUT, "_prereg.json"), encoding="utf-8"))
got = hashlib.sha256(open(os.path.join(B.OUT, "PREREG.md"), "rb").read()).hexdigest()
if got != spec["sha256"]:
    raise SystemExit("PREREGISTRATION HASH MISMATCH -- REFUSING TO RUN\n stored %s\n got    %s"
                     % (spec["sha256"], got))
print("prereg sha256 %s  MATCH" % got)

RESP = {"minutes": "min_hat", "pts": "pts_hat"}          # explicit dict, 2 entries
assert len(RESP) == 2

# ================================================================= 1. FIT FRAME
B.hdr("1. FIT FRAME -- 2021-2024 regular-season appeared rows.  W2 is SCORED; 2021-2022 TRAIN ONLY")
player = pd.read_parquet(os.path.join(B.SRC_REDIST, "_player_frame.parquet"))
tier = pd.read_parquet(os.path.join(B.SRC_TIER, "tier_frame.parquet"))
work = pd.read_parquet(os.path.join(B.SRC_STACK, "_work.parquet"))

PLAYER_KEEP = ("row_uid", "season", "game_id", "team_id", "player_id", "game_date",
               "appeared", "minutes", "pts", "fga", "min_hat", "pts_hat", "fga_hat",
               "is_fallback", "fallback_level", "is_cold_start", "n_prior_games",
               "base5_minutes", "base5_pts", "base5_fga",
               "nprior_minutes", "nprior_pts", "nprior_fga")
B.assert_allowlist(player, PLAYER_KEEP, 23, "PLAYER_KEEP")
f = player[list(PLAYER_KEEP)].copy()
B.assert_partition(f, "player_all")
f = f[f["game_id"].astype(str).str[:4] == "1022"].copy()          # RS1
f = f[f["appeared"].astype(int) == 1].copy()
for c in ("minutes", "pts", "min_hat", "pts_hat"):
    f = f[np.isfinite(pd.to_numeric(f[c], errors="coerce"))].copy()
f["tg"] = f["game_id"].astype(str) + "_" + f["team_id"].astype(str)
print("  fit frame rows %d ; by season:" % len(f))
print(f.groupby("season").size().to_string())

# ---- established / absence construction, on ALL champion candidate rows (not just appeared)
MINPRIOR = 3.0
pall = player[player["game_id"].astype(str).str[:4] == "1022"].copy()
B.assert_partition(pall, "pall_rs")
pall["established"] = ((pd.to_numeric(pall["nprior_minutes"], errors="coerce") >= MINPRIOR)
                       & pall["base5_minutes"].notna()).astype(int)
pall["_absent"] = ((pall["established"] == 1) & (pall["appeared"].astype(int) == 0)).astype(int)
pall["tg"] = pall["game_id"].astype(str) + "_" + pall["team_id"].astype(str)
CH = ("minutes", "pts")
for ch in CH:
    pall["_f_" + ch] = np.where(pall["_absent"] == 1,
                                pd.to_numeric(pall["base5_" + ch], errors="coerce"), 0.0)
G = (pall.groupby("tg").agg(freed_minutes=("_f_minutes", "sum"), freed_pts=("_f_pts", "sum"),
                            n_absent=("_absent", "sum"), n_elig=("established", "sum"))
     .reset_index())
nrem = (pall[(pall["established"] == 1) & (pall["appeared"].astype(int) == 1)]
        .groupby("tg").size().rename("n_rem").reset_index())
G = G.merge(nrem, on="tg", how="left")
G["n_rem"] = G["n_rem"].fillna(0.0)
print("  team-games %d ; freed>0 in %.4f" % (len(G), float((G["freed_minutes"] > 0).mean())))

# z_i -- absence-blind within-team-game z of base5, computed over ESTABLISHED (not REM)
est = pall[pall["established"] == 1].copy()
for ch in CH:
    g = est.groupby("tg")["base5_" + ch]
    est["z_" + ch] = ((pd.to_numeric(est["base5_" + ch], errors="coerce")
                       - g.transform("mean")) / g.transform("std").replace(0.0, np.nan))
    est["z_" + ch] = est["z_" + ch].fillna(0.0)
f = f.merge(est[["row_uid", "z_minutes", "z_pts"]], on="row_uid", how="left")
f["established"] = f["row_uid"].isin(set(est["row_uid"])).astype(int)
f = f.merge(G, on="tg", how="left")
assert np.isfinite(f["freed_minutes"].to_numpy(float)).all(), "D087: freed reference incomplete"
for ch in CH:
    f["u_" + ch] = np.where(f["n_rem"].to_numpy(float) > 0,
                            f["freed_" + ch].to_numpy(float)
                            / np.maximum(f["n_rem"].to_numpy(float), 1.0), 0.0)
    f["u_" + ch] = np.where(f["established"].to_numpy() == 1, f["u_" + ch], 0.0)
    f["z_" + ch] = f["z_" + ch].fillna(0.0)
    f["uz_" + ch] = f["u_" + ch] * f["z_" + ch]

# ---- structural inputs for A
TIER_KEEP = ("row_uid", "depth_bucket", "draft_bucket")
B.assert_allowlist(tier, TIER_KEEP, 3, "TIER_KEEP_A")
f = f.merge(tier[list(TIER_KEEP)], on="row_uid", how="left")

# ---- tuned simple estimator for B
K = ["season", "player_id", "game_id", "team_id"]
WORK_KEEP = K + ["e_full_pts", "e_full_minutes"]
B.assert_allowlist(work, WORK_KEEP, 6, "WORK_KEEP_B")
w = work[WORK_KEEP].copy()
for c in K:
    w[c] = w[c].astype(str)
    f[c] = f[c].astype(str)
f = f.merge(w, on=K, how="left")
assert not any(c.endswith(("_x", "_y")) for c in f.columns), "silent column collision"
f["season"] = pd.to_numeric(f["season"])
B.assert_partition(f, "fit_frame_final")

f["n_prior"] = pd.to_numeric(f["n_prior_games"], errors="coerce").astype(float)
f["prior5_minutes"] = pd.to_numeric(f["base5_minutes"], errors="coerce").astype(float)
f["DECISION"] = (f["n_prior"] >= 8) & (f["prior5_minutes"] >= 24)
fl = pd.to_numeric(f["fallback_level"], errors="coerce").to_numpy(float)
f["TA"] = (fl == 2.0)
f["TB"] = f["is_fallback"].astype(bool)
f["TC"] = (f["freed_minutes"].to_numpy(float) >= 25.0) & (f["established"].to_numpy() == 1)
f["TC_nominal"] = (f["freed_minutes"].to_numpy(float) >= 25.0)

SCORED = np.isin(f["season"].to_numpy(), np.array(B.SCORED_W2))
print("\n  SCORED (W2) rows in fit frame: %d   (this is U)" % int(SCORED.sum()))
for k in ("TA", "TB", "TC"):
    print("    %s on U: %d" % (k, int((f[k].to_numpy() & SCORED).sum())))
B.anchor("A8-pre  established & freed>=25 on U", int((f["TC"].to_numpy() & SCORED).sum()), 2475)

f.to_parquet(os.path.join(B.OUT, "_fit.parquet"), index=False)
print("  wrote _fit.parquet  (%d rows, %d cols)" % f.shape)

# ================================================================= 2. WALK-FORWARD MACHINERY
B.hdr("2. WALK-FORWARD MACHINERY -- fitted on STRICTLY EARLIER seasons only")


# MIN_TRAIN.  E1_I0034 s06 excludes 2021 from every CHAMPION-based arm because the champion's
# 2021 fold receipt declares `degenerate: true`.  My first draft trained from 2021 and A8 missed
# by 6.7e-2 with M1 catastrophically worse than M0 (dMAE -0.70) -- the degenerate fold poisoning
# the walk-forward slopes.  Recorded in DEFECTS.md as DEF-1 and fixed here.
MIN_TRAIN_CHAMP = B.MIN_TRAIN_CHAMP
MIN_TRAIN_STRUCT = B.MIN_TRAIN_STRUCT


def wf_ols(resid, X, season, apply_mask, fit_mask, scored=B.SCORED_W2,
           min_train=MIN_TRAIN_CHAMP):
    """Fit resid ~ [1] + X on seasons in [min_train, S) for each scored season S; apply on
    `apply_mask` rows of S.  Zero where unavailable.  NO RETROSPECTIVE BASELINE: nothing in this
    function ever sees the scored season's own response."""
    n = len(resid)
    out = np.zeros(n)
    D = np.column_stack([np.ones(n)] + [np.asarray(c, float) for c in X])
    ok = np.isfinite(D).all(axis=1) & np.isfinite(resid)
    for s in scored:
        tr = ok & fit_mask & (season < s) & (season >= min_train)
        te = ok & apply_mask & (season == s)
        if tr.sum() < D.shape[1] + 20 or te.sum() == 0:
            continue
        beta, *_ = np.linalg.lstsq(D[tr], resid[tr], rcond=None)
        out[te] = D[te] @ beta
    return out


def wf_arm(offset, Xcols, y, season, scored=B.SCORED_W2, min_train=MIN_TRAIN_CHAMP):
    """ONE ARM = offset + walk-forward fit of (y - offset) on [1] + Xcols.

    An INTERCEPT IS HELD IN BOTH ARMS of every comparison: the base arm is `Xcols = []`, i.e.
    offset + a walk-forward intercept, and a candidate arm is offset + a walk-forward fit that
    also has that intercept.  E1_I0032 documented a HIGH defect where fitting [1, x] against a
    BARE offset smuggled in a walk-forward intercept recalibration and returned a number thirty
    times an arithmetic ceiling with the WRONG SIGN.  Constructing both arms this way designs
    that defect out rather than guarding against it.

    NOTE, recorded as DEF-2: an earlier draft computed the candidate arm as
    base + (fit[1,X] - fit[1]) on the residual y - base.  That is algebraically the same ONLY if
    the intercept is constant across the training pool; it is not, because scored season 2023 is
    also a TRAINING season for 2024 and had already had its intercept subtracted.  A8c missed by
    2.3e-4.  Replaced with E1_I0034's own single-regression construction, which is the byte-level
    equivalent.
    """
    n = len(y)
    D = np.column_stack([np.ones(n)] + [np.asarray(c, float) for c in Xcols])
    out = np.full(n, np.nan)
    r = np.asarray(y, float) - np.asarray(offset, float)
    for s in scored:
        tr = (season < s) & (season >= min_train)
        te = (season == s)
        if tr.sum() < D.shape[1] + 20 or te.sum() == 0:
            continue
        beta, *_ = np.linalg.lstsq(D[tr], r[tr], rcond=None)
        out[te] = D[te] @ beta
    return np.asarray(offset, float) + out


# ================================================================= 3. ANCHOR A8
B.hdr("3. ANCHOR A8 -- reproduce E1_I0034's P04 minutes cell on E1_I0034's OWN row set")
rem = pd.read_parquet(os.path.join(B.SRC_REDIST, "_rem_frame.parquet"))
r = rem[rem["season"].isin(B.SCORED_W2)].copy()
r_all = rem.copy()          # 2021-2024, for the walk-forward fit pool
y = pd.to_numeric(r_all["minutes"], errors="coerce").to_numpy(float)
ch = pd.to_numeric(r_all["min_hat"], errors="coerce").to_numpy(float)
sea = r_all["season"].to_numpy()
uu = pd.to_numeric(r_all["u_minutes"], errors="coerce").to_numpy(float)
uz = pd.to_numeric(r_all["uz_minutes"], errors="coerce").to_numpy(float)
M0 = wf_arm(ch, [], y, sea)
M1 = wf_arm(ch, [uu, uz], y, sea)
sel = np.isin(sea, np.array(B.SCORED_W2)) & (pd.to_numeric(r_all["freed_minutes"],
                                                           errors="coerce").to_numpy(float) >= 25.0)
print("  n on the >=25 stratum: %d" % int(sel.sum()))
mae0 = float(np.mean(np.abs(y[sel] - M0[sel])))
mae1 = float(np.mean(np.abs(y[sel] - M1[sel])))
print("  MAE(M0') %.15f   MAE(M1') %.15f   dMAE %.15f" % (mae0, mae1, mae0 - mae1))
B.anchor("A8a E1_I0034 P04 minutes n", int(sel.sum()), 2475)
B.anchor("A8b E1_I0034 P04 minutes MAE(M0')", mae0, 5.101386713527127, tol=1e-6)
B.anchor("A8c E1_I0034 P04 minutes dMAE", mae0 - mae1, 0.09269264623364977, tol=1e-6)
print("\n  A8 REPRODUCED.  The C machinery in this screen is byte-compatible with D116's.")
