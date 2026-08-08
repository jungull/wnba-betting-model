"""
E1_I0025 -- THRESHOLD vs REFIT ARTEFACT.  Shared machinery.

WHAT THIS CONFIRMATION EXISTS FOR.  E1_I0023 (decision D098) killed its preregistered usage x
    defence interaction and then raised a much larger lead: inside the TOP VOLUME TERCILE the
    opponent-defence MAIN effect is walk-forward dR2 +0.023863 (points-per-minute) and +0.018703
    (points) on the decision stratum against a COMPLETE prior reference, n=1687.  D098's own
    disclosure item 8 leaves a tension standing: a TIER-RESTRICTED REFIT gains +0.024 while a POOLED
    usage x defence INTERACTION gains +0.0002, and D098 states in terms that the INTERMEDIATE
    specification -- a pooled model carrying a TIER-DUMMY x DEFENCE term -- was not tested.  This
    screen tests it, and separates the refit from the signal directly.

WHY THE D098 MODULES ARE IMPORTED RATHER THAN REIMPLEMENTED.  The whole point of this confirmation
    is that its numbers are comparable to D098's.  A reimplementation introduces exactly the class of
    discrepancy the comparison cannot tolerate, so D098's `uid_base`, `s00_prereg`,
    `s02_interaction_forecast`, `s05_placebos` and `s07_stress` are imported READ-ONLY from their
    own directory and their loaders / design / null functions are called unchanged.  Nothing in
    D098's directory is written: `sys.dont_write_bytecode` is set before the first import and every
    script is executed with `python -B`, so not even a __pycache__ entry is created there.  No
    `main()` from any of those modules is ever called.  D098 in turn imports nothing from
    `_screen_kit`.

PARTITION.  Seasons 2021-2024 only, inherited from D098's value-level gate (`assert_partition`),
    which is executed inside every load.  2021 is a TRAINING fold only; every scored row is
    2022-2024.  2025/2026 is never read, joined, plotted or described.

THE CHAMPION IS NEVER TOUCHED.  No champion forecast is loaded, scored, retrained or modified.
    Fitting screening models in the exploration lane is authorised by D091 ruling 1.
"""
import hashlib
import json
import os
import sys

sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

import numpy as np           # noqa: E402
import pandas as pd          # noqa: E402

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
EXP = os.path.join(ROOT, r"experiments\exploration")
D098DIR = os.path.join(EXP, "E1_I0023_usage_defence_interaction")
OUT = os.path.join(EXP, "E1_I0025_threshold_vs_refit")     # THE ONLY DIRECTORY THIS SCREEN WRITES

if D098DIR not in sys.path:
    sys.path.insert(0, D098DIR)
import uid_base as ub                    # noqa: E402  (D098, read-only)
import s00_prereg as pr                  # noqa: E402  (D098, read-only)
import s02_interaction_forecast as s02   # noqa: E402  (D098, read-only)
import s05_placebos as s05               # noqa: E402  (D098, read-only)
import s07_stress as s07                 # noqa: E402  (D098, read-only)

DEFENCE = "A10_opp_defrtg"
UCOL = pr.USAGE_MAIN                 # O01_own_usg_pg
BASE = pr.BASE_COMPLETE              # the COMPLETE prior reference: 5 columns
SCORED = pr.PREREG["partition"]["scored_seasons"]     # [2022, 2023, 2024]
SEED = ub.SEED                       # 20260808 -- D098's seed, so shared draws line up
N_SWAP = s05.N_SWAP                  # 500, D098's within-date opponent-swap draw count
N_RANDOM_TIER = 500
TN = {0: "T1_low", 1: "T2_mid", 2: "T3_high"}

# D098's published anchors, quoted here BEFORE anything is recomputed.
D098_ANCHORS = {
    "tier_refit_defence_maineffect_ppm_DECISION_T3": 0.023862917871899772,
    "tier_refit_defence_maineffect_points_DECISION_T3": 0.018702810112816066,
    "pooled_linear_interaction_ppm_DECISION_ALL": 0.00020296622240270165,
    "pooled_linear_interaction_points_DECISION_ALL": 0.0010051448507570257,
    "pooled_defence_maineffect_ppm_DECISION_ALL": 0.005028055896625616,
    "pooled_defence_maineffect_points_DECISION_ALL": 0.0033354248642841694,
    "n_scored_T3_DECISION": 1687,
    "ceiling_decision_stratum": 0.01280821,
    "largest_prior_ceiling_D089": 0.002057,
}


def hdr(s):
    print("\n" + "=" * 100)
    print(s)
    print("=" * 100)


def sha(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")
                                     ).encode("utf-8")).hexdigest()


class Tee(object):
    """Collect a run log while printing it."""

    def __init__(self):
        self.lines = []

    def __call__(self, x=""):
        print(x)
        self.lines.append(str(x))

    def write(self, path):
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(self.lines) + "\n")


# --------------------------------------------------------------------------- frame construction
NEED_EXTRA = ["G01_noise", "y_ppm", "y_pts", "_m_hat", "refB_mpg", "refB_ppm"]


def build(P):
    """D098's frame, D098's placebo columns, D098's tier labels.  Read-only throughout."""
    m, ncl = s02.build_frame(P)
    m, unit = s05.build_placebos(m, P)
    need = list(dict.fromkeys(BASE + [UCOL, DEFENCE] + NEED_EXTRA))
    v = {c: pd.to_numeric(m[c], errors="coerce").to_numpy(float) for c in need}
    ub.assert_partition(m)
    P("  partition gate PASS on the merged frame (seasons %s)" % sorted(m["season"].unique()))
    return m, v, need, ncl, unit


def decision_mask(m, v, need):
    """D098's DECISION stratum, complete-case on exactly the columns D098's s07 required."""
    mask = s02.stratum_mask(m, "DECISION")
    for c in need:
        mask &= np.isfinite(v[c])
    return mask


def tier_labels(m, v, mask, axis=UCOL):
    """D098's `s07.tiers_for`: tercile cut points from the FIRST TRAINING FOLD (2021) only."""
    return s07.tiers_for(m, v, mask, axis)


# --------------------------------------------------------------------------- fold construction
def folds(m, mask_pool, mask_tier, min_tr=300, min_te=80):
    """Walk-forward folds, gated on the TIER-RESTRICTED arm exactly as D098's s04/s05 gate them.

    Returns (season, tr_pool, tr_tier, te) where `te` is the TIER-RESTRICTED scored selection.  Every
    rung of the ladder is scored on the SAME `te` rows, which is what makes the numbers comparable.
    """
    ssn = m["season"].to_numpy()
    out = []
    for s in SCORED:
        tr_t = mask_tier & (ssn < s)
        te = mask_tier & (ssn == s)
        tr_p = mask_pool & (ssn < s)
        if tr_t.sum() < min_tr or te.sum() < min_te or tr_p.sum() < min_tr:
            continue
        out.append((s, tr_p, tr_t, te))
    return out


# --------------------------------------------------------------------------- design matrices
def Z(v, sel):
    """[1, COMPLETE prior reference (5 cols), prior usage].  The no-defence base, D098's."""
    n = int(sel.sum())
    return [np.ones(n)] + [v[c][sel] for c in BASE] + [v[UCOL][sel]]


def dummies(tier, sel):
    t = tier[sel]
    return [(t == 1).astype(float), (t == 2).astype(float)]


def design(rung, arm, v, sel, dvals, tier, uc, dc):
    """Every specification in the ladder, in one place.

    rung L1 : pooled, ONE defence coefficient                      (defence main effect, pooled)
    rung L2 : pooled, defence + LINEAR usage x defence             (D098's interaction, as a family)
    rung L3 : pooled, tier dummies + defence + TIER-DUMMY x DEFENCE  <-- THE DECISIVE TEST
    rung L4 : TIER-RESTRICTED refit, defence                       (D098's +0.023863 construction)
    Every rung's arm 'B' is the same model with EVERY defence-carrying column removed, so each
    rung's dR2 is the increment attributable to the defence family at that rung.
    """
    cols = Z(v, sel)
    d = dvals[sel]
    u = v[UCOL][sel]
    if rung in ("L3",):
        cols += dummies(tier, sel)
    if arm == "B":
        return np.column_stack(cols)
    if rung == "L1":
        cols += [d]
    elif rung == "L2":
        cols += [d, (u - uc) * (d - dc)]
    elif rung == "L3":
        D1, D2 = dummies(tier, sel)
        cols += [d, D1 * (d - dc), D2 * (d - dc)]
    elif rung == "L4":
        cols += [d]
    else:
        raise ValueError(rung)
    return np.column_stack(cols)


def score_rung(m, v, rung, fold_list, dvals, tier, resp, ret_pred=False):
    """Walk-forward paired dR2 of a rung's defence family, scored on the fold list's `te` rows.

    L1/L2/L3 are fitted POOLED (all tiers, `tr_pool`).  L4 is fitted TIER-RESTRICTED (`tr_tier`).
    dR2 = (SSE_B - SSE_A) / SST, SST taken on the scored rows -- D098's definition exactly.
    """
    yy, pa, pb, cc, bet = [], [], [], [], []
    for (s, tr_p, tr_t, te) in fold_list:
        tr = tr_t if rung == "L4" else tr_p
        uc = float(v[UCOL][tr].mean())
        dc = float(dvals[tr].mean())
        XB_tr = design(rung, "B", v, tr, dvals, tier, uc, dc)
        XA_tr = design(rung, "A", v, tr, dvals, tier, uc, dc)
        XB_te = design(rung, "B", v, te, dvals, tier, uc, dc)
        XA_te = design(rung, "A", v, te, dvals, tier, uc, dc)
        bB = ub.ols(XB_tr, v[resp["rate_col"]][tr])
        bA = ub.ols(XA_tr, v[resp["rate_col"]][tr])
        sc = v["_m_hat"][te] if resp["scale_by_minutes"] else 1.0
        pb.append((XB_te @ bB) * sc)
        pa.append((XA_te @ bA) * sc)
        yy.append(v[resp["target_col"]][te])
        cc.append(m["_cluster"].to_numpy()[te])
        bet.append(bA[XB_tr.shape[1]:].copy())      # the defence-family coefficients
    y = np.concatenate(yy)
    A = np.concatenate(pa)
    B = np.concatenate(pb)
    C = np.concatenate(cc)
    sst = float(((y - y.mean()) ** 2).sum())
    dr2 = float((((y - B) ** 2).sum() - ((y - A) ** 2).sum()) / sst)
    if ret_pred:
        return dr2, y, A, B, C, sst, bet
    return dr2


def frozen_transplant(m, v, fold_list, dvals, tier, resp, freeze="tier"):
    """TRANSPLANT: freeze the NON-DEFENCE coefficients, then add a defence term on top.

    freeze='tier'   : non-defence coefficients from the TIER-RESTRICTED fit, defence fitted on the
                      tier's training residual.  Asks whether the defence term still earns its keep
                      when it is NOT allowed to re-shuffle the other coefficients.
    freeze='pooled' : non-defence coefficients from the POOLED fit, defence fitted on the tier's
                      training residual.  Asks whether the defence term earns its keep with NO tier
                      refit anywhere.
    The defence coefficient is estimated by OLS of the frozen model's training residual on the
    CENTRED defence column with no free intercept, so the frozen level is genuinely frozen.  By
    Frisch-Waugh this is NOT the full-OLS coefficient unless defence is orthogonal to the base --
    which is the point of the test.
    """
    yy, pa, pb, cc, gam = [], [], [], [], []
    for (s, tr_p, tr_t, te) in fold_list:
        trf = tr_t if freeze == "tier" else tr_p
        uc = float(v[UCOL][trf].mean())
        dc = float(dvals[tr_t].mean())
        XB_trf = design("L4", "B", v, trf, dvals, tier, uc, dc)
        b0 = ub.ols(XB_trf, v[resp["rate_col"]][trf])
        XB_trt = design("L4", "B", v, tr_t, dvals, tier, uc, dc)
        r = v[resp["rate_col"]][tr_t] - XB_trt @ b0
        dctr = dvals[tr_t] - dc
        den = float(dctr @ dctr)
        g = float((r @ dctr) / den) if den > 0 else 0.0
        XB_te = design("L4", "B", v, te, dvals, tier, uc, dc)
        base_pred = XB_te @ b0
        sc = v["_m_hat"][te] if resp["scale_by_minutes"] else 1.0
        pb.append(base_pred * sc)
        pa.append((base_pred + g * (dvals[te] - dc)) * sc)
        yy.append(v[resp["target_col"]][te])
        cc.append(m["_cluster"].to_numpy()[te])
        gam.append(g)
    y, A, B, C = (np.concatenate(yy), np.concatenate(pa), np.concatenate(pb), np.concatenate(cc))
    sst = float(((y - y.mean()) ** 2).sum())
    return dict(dr2=float((((y - B) ** 2).sum() - ((y - A) ** 2).sum()) / sst),
                gamma_mean=float(np.mean(gam)), n=int(len(y))), (y, A, B, C, sst)


def refit_only(m, v, fold_list, tier, resp):
    """REFIT WITHOUT DEFENCE.  The single cleanest measurement of the artefact hypothesis.

    Arm B : the NO-DEFENCE base fitted POOLED on all decision-stratum training rows.
    Arm A : the SAME no-defence base fitted on the TIER's training rows only.
    Scored on the identical tier rows.  Whatever this recovers is the refit's OWN contribution, with
    no defence column anywhere in either arm.
    """
    yy, pa, pb, cc = [], [], [], []
    zero = np.zeros(len(v[UCOL]))
    for (s, tr_p, tr_t, te) in fold_list:
        XB_tr = design("L4", "B", v, tr_p, zero, tier, 0.0, 0.0)
        XA_tr = design("L4", "B", v, tr_t, zero, tier, 0.0, 0.0)
        Xte = design("L4", "B", v, te, zero, tier, 0.0, 0.0)
        bB = ub.ols(XB_tr, v[resp["rate_col"]][tr_p])
        bA = ub.ols(XA_tr, v[resp["rate_col"]][tr_t])
        sc = v["_m_hat"][te] if resp["scale_by_minutes"] else 1.0
        pb.append((Xte @ bB) * sc)
        pa.append((Xte @ bA) * sc)
        yy.append(v[resp["target_col"]][te])
        cc.append(m["_cluster"].to_numpy()[te])
    y, A, B, C = (np.concatenate(yy), np.concatenate(pa), np.concatenate(pb), np.concatenate(cc))
    sst = float(((y - y.mean()) ** 2).sum())
    return dict(dr2=float((((y - B) ** 2).sum() - ((y - A) ** 2).sum()) / sst), n=int(len(y)),
                sst=sst), (y, A, B, C, sst)


# --------------------------------------------------------------------------- random tier machinery
def random_tier_rowshuffle(tier, mask, m, rng):
    """Permute the tier labels among masked rows WITHIN SEASON.

    Preserves each season's tier composition exactly and destroys which rows are high-volume.  The
    null distribution of 'refitting any equally sized subset of these rows'.
    """
    out = tier.copy()
    ssn = m["season"].to_numpy()
    for s in np.unique(ssn):
        idx = np.flatnonzero(mask & (ssn == s))
        if len(idx) > 1:
            out[idx] = tier[idx][rng.permutation(len(idx))]
    return out


def random_tier_playerblock(tier, mask, m, rng):
    """Assign tiers to WHOLE PLAYER-SEASON BLOCKS at random, size-matched on row counts.

    A row-level shuffle breaks the player-block structure of the real tiers, which could make the
    null too easy.  This variant keeps whole player-seasons together and matches the real tier row
    counts as closely as the block sizes allow -- the honest null for 'refitting any player-defined
    subset of this size'.
    """
    idx = np.flatnonzero(mask)
    key = pd.Series(list(zip(m["player_id"].to_numpy()[idx], m["season"].to_numpy()[idx])))
    codes, uq = pd.factorize(key, sort=False)
    nblk = len(uq)
    order = rng.permutation(nblk)
    sizes = np.bincount(codes, minlength=nblk).astype(int)
    targets = [int((tier[idx] == t).sum()) for t in (0, 1, 2)]
    lab = np.empty(nblk, int)
    cum, t, filled = 0, 0, 0
    for b in order:
        while t < 2 and filled >= targets[t]:
            t += 1
            filled = 0
        lab[b] = t
        filled += sizes[b]
        cum += sizes[b]
    out = tier.copy()
    out[idx] = lab[codes]
    return out


def swap_draws(m, unit, n, rng):
    """D098's within-date opponent-swap null: permute defence values among that date's team-games."""
    for _ in range(n):
        yield s05.swap_within_date(m, unit, rng)
