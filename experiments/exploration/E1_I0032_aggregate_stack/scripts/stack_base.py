"""E1_I0032 -- shared machinery.  Imported by every s0N script; runs nothing on import except the
preregistration hash check, which is fatal on mismatch.

NO CHAMPION FITTING ANYWHERE.  The champion's stored forecasts are read and scored.  Everything
this module fits (the routed-to estimator's hyperparameters are IMPORTED, not fitted; the feature
corrections are walk-forward OLS on seasons strictly earlier than the scored season) is authorised
by D091 and is prior-only by construction.
"""
import hashlib
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.dirname(HERE)
ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
EXP = os.path.join(ROOT, r"experiments\exploration")
KIT = os.path.join(EXP, "_screen_kit")
LADDER_DIR = os.path.join(EXP, "E1_I0027_reference_ladder")

sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
for p in (LADDER_DIR, KIT):
    if p not in sys.path:
        sys.path.insert(0, p)
import refladder as RL          # noqa: E402
import screenkit as SK          # noqa: E402

FORBIDDEN = ("E0_I0029_freethrow_hurdle", "E1_I0031_rapm_as_prior")

TARGETS = ["pts", "minutes", "fga", "ppm"]
SCORED = [2022, 2023, 2024]
SEED = 20260808
PLACEBO_SEED = 424242
N_DRAWS = 4000

TV = os.path.join(EXP, r"E1_I0018_teammate_volume_channel\screen_frame.parquet")
EFF = os.path.join(EXP, r"E0_I0016_efficiency_predictors\screen_frame.parquet")
TIER = os.path.join(EXP, r"E1_I0020_coldstart_tiering\tier_frame.parquet")
AVAIL = os.path.join(EXP, r"E0_I0019_availability_forecast\analysis_frame.parquet")

CHAMP_COL = {"pts": "pts__pred_point", "minutes": "minutes__pred_point",
             "fga": "fga__pred_point", "ppm": None}          # ppm derived, see build()
FALLBACK_COL = {"pts": "pts__fallback_level", "minutes": "minutes__fallback_level",
                "fga": "fga__fallback_level", "ppm": "pts__fallback_level"}


# ------------------------------------------------------------------ preregistration guard
def prereg():
    with open(os.path.join(OUT, "_prereg.json"), encoding="utf-8") as fh:
        spec = json.load(fh)
    stored = spec.pop("sha256")
    for k in ("n_components_continuous", "n_components_separate_response",
              "n_placebo_components", "added_after_hashing", "dropped_after_hashing"):
        spec.pop(k, None)
    txt = json.dumps(spec, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    got = hashlib.sha256(txt.encode("utf-8")).hexdigest()
    if got != stored:
        raise SystemExit("PREREGISTRATION HASH MISMATCH -- REFUSING TO RUN\n  stored %s\n  got    %s"
                         % (stored, got))
    spec["sha256"] = stored
    return spec


def guard_paths(*paths):
    for p in paths:
        for f in FORBIDDEN:
            if f in p:
                raise SystemExit("REFUSED: %s is a live agent's directory" % f)


# ------------------------------------------------------------------ estimator configurations
def cfg_naive(t):
    """The deliberately naive single-window estimator: ONE half-life for every target, no shrink."""
    return dict(mode="equal", half_life=5.0, shrink="none", k=0.0, floor=0.0)


def cfg_from_canon(t, use_hl, use_shrink, hl_override=None, k_override=None):
    c = RL.CANON[t]
    mode = c["mode"] if use_hl else "equal"
    hl = float(c["half_life"]) if use_hl else 5.0
    if hl_override is not None:
        hl = float(hl_override)
        mode = "equal"
    shrink = c["shrink"] if use_shrink else "none"
    k = float(c["k"]) if use_shrink else 0.0
    if k_override is not None:
        k = float(k_override)
        shrink = "prior_season"
    return dict(mode=mode, half_life=hl, shrink=shrink, k=k, floor=0.0)


def estimate(f, t, cfg):
    """One estimator cell -> row-level prior-only forecast, via refladder's engine."""
    return RL._estimate(f, t, cfg["mode"], "ewma", float(cfg["half_life"]),
                        cfg["shrink"], float(cfg["k"]), float(cfg["floor"]))


# ------------------------------------------------------------------ walk-forward OLS correction
def wf_correction(resid, X, season, apply_mask, fit_mask):
    """Fit `resid ~ [1, X]` on seasons STRICTLY EARLIER than each scored season; return the
    predicted correction, zero where `apply_mask` is False or the fit is unavailable.

    THE INFERENCE STEP IS PRIOR-ONLY TOO.  Nothing in this function ever sees the scored season's
    own response.
    """
    n = len(resid)
    out = np.zeros(n)
    D = np.column_stack([np.ones(n)] + [np.asarray(c, float) for c in X])
    ok = np.isfinite(D).all(axis=1) & np.isfinite(resid)
    for s in SCORED:
        tr = ok & fit_mask & (season < s)
        te = ok & apply_mask & (season == s)
        if tr.sum() < D.shape[1] + 20 or te.sum() == 0:
            continue
        beta, *_ = np.linalg.lstsq(D[tr], resid[tr], rcond=None)
        out[te] = D[te] @ beta
    return out


def wf_feature_correction(resid, x, season, mask):
    """The PURE SLOPE contribution of adding feature `x` to a model that ALREADY has an intercept.

    correction = fit[1, x] - fit[1], both walk-forward on the identical rows.  Without this
    subtraction a 'feature' component silently carries a walk-forward INTERCEPT RECALIBRATION of
    the base, which is not the component and is not in the preregistered list.  This screen found
    that the hard way: a home-advantage correction fitted as [1, home] returned dR2 -1.379e-03 on
    the R4 reference -- thirty times D104's analytic ceiling -- entirely from the intercept.

    D089, D099 and D104 all measured base-vs-base-plus-x with an intercept in BOTH arms.  This is
    that comparison.
    """
    with_x = wf_correction(resid, [x], season, mask, mask)
    int_only = wf_correction(resid, [], season, mask, mask)
    return with_x - int_only


def prior_season_tercile_top(usg, season):
    """Top tercile of prior own usage, cut on STRICTLY EARLIER seasons only (prior-only)."""
    n = len(usg)
    top = np.zeros(n, bool)
    for s in SCORED:
        tr = (season < s) & np.isfinite(usg)
        te = (season == s) & np.isfinite(usg)
        if tr.sum() < 100 or te.sum() == 0:
            continue
        cut = float(np.quantile(usg[tr], 2.0 / 3.0))
        top[te] = usg[te] >= cut
    return top


# ------------------------------------------------------------------ scoring
def r2c(y, yhat, sst):
    y = np.asarray(y, float)
    yhat = np.asarray(yhat, float)
    return 1.0 - float(((y - yhat) ** 2).sum()) / float(sst)


def paired(y, a, b, groups, name_a="A", name_b="B", n_draws=N_DRAWS, seed=SEED):
    """Clustered paired sign-flip.  Publishes null_mean and null_sd beside p (D103 ruling 2)."""
    res = SK.paired_forecast_comparison(np.asarray(y, float), np.asarray(a, float),
                                        np.asarray(b, float), groups=groups, n_draws=n_draws,
                                        seed=seed, name_a=name_a, name_b=name_b,
                                        alternative="two_sided")
    dr = np.asarray(res["draws"], float)
    return dict(n=int(res["n"]), n_clusters=int(res["n_groups"]),
                dr2=float(res["dr2_a_minus_b"]), p=float(res["p"]),
                null_mean=float(dr.mean()), null_sd=float(dr.std(ddof=1)),
                p_row_NAIVE=float(res["p_row_level_NAIVE"]),
                inflation=float(res["inflation"]))
