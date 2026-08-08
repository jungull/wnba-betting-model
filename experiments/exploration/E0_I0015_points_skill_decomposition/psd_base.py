"""
E0_I0015 POINTS SKILL DECOMPOSITION -- shared loader / rate builder / paired-inference machinery.

QUESTION.  D076 (E0_I0014) measured the champion player model's SKILL against a point-in-time
    expanding prior-appearance-mean reference on the pre-existing season-chronological walk-forward
    `experiments/cbs_v15_player_oof_v5/attempt_001/`, 2022-2024, 13,879 appeared player-games:
        MINUTES +3.55%   FGA +0.12%   POINTS -0.22%
    Skill is LOST somewhere along POINTS = MINUTES x POINTS-PER-MINUTE.  This screen finds where.

PARTITION (GRAPH_POLICY 13.2): seasons 2021-2024 ONLY, effectively 2022-2024 because D076
    established the 2021 fold is degenerate (n_train_rows=0, model_was_fitted=false).  Enforced by
    screenkit.assert_partition -- a VALUE test on parsed dates and season-valued columns.  No
    regex/byte scan of file contents is used as a partition check anywhere.

INPUT.  D076's frozen `analysis_frame.parquet` is READ ONLY and never modified.  It already carries
    y_{pts,minutes,fga}, the three model pred_points, D076's ref_{pts,minutes,fga}, and 58 pre-game
    candidate columns.  D076's own provenance work is relied on and re-verified in s01.

RATE DEFINITIONS (preregistered before any result was computed -- see NOTES.md section 8):
    ppm  points per minute      = pts / minutes                (minutes > 0 on every row: verified)
    fpm  FGA per minute         = fga / minutes
    ppf  points per FGA         = pts / fga                    (UNDEFINED where fga == 0)
    The MODEL's implied rate is the RATIO OF ITS OWN POINT FORECASTS, e.g. ppm_model =
    pts__pred_point / minutes__pred_point.  Nothing new is fitted; the champion is not re-trained.

REFERENCE (trap 2 -- retrospective baselines, five instances found in this program).  Every
    reference here is STRICTLY PRIOR-GAMES-ONLY: sort by game_date inside (season, player_id), then
    .shift(1) BEFORE any expanding().  Two variants are built for every rate and both are reported,
    because choosing one after seeing the answer would be a place to cheat:
      REF-A "mean of prior ratios"   expanding mean of the player's own prior per-game rate values.
                                     This is the exact structural analogue of D076's level reference.
      REF-B "ratio of prior sums"    sum(prior numerator) / sum(prior denominator).  A strictly
                                     better estimator of a rate, hence a HARDER reference.
    Cold fallback for both: the expanding league mean over games strictly earlier in the same
    season.  See the TIME-WINDOW TABLE in NOTES.md.

SKILL.  skill = 1 - MAE_model / MAE_reference, both computed on THE SAME ROWS.  D076's most
    important methodological lesson is that predicting ERROR is not predicting DIFFERENTIAL SKILL:
    one of its candidates cut points MAE by 9.9% while moving skill by +0.00007, because the naive
    reference improved just as much on those rows.  Raw MAE reduction is never a verdict here.

R2 CONVENTION (D069): plain unweighted OLS R2, SST about the UNWEIGHTED mean.  screenkit.r2_plain.

PAIRED INFERENCE.  The headline comparisons (H1 vs H2 etc.) are PAIRED contrasts of two forecasts'
    absolute errors on the same rows, which is not a feature-permutation problem and which the
    screen kit does not cover.  A (season, player_id) BLOCK SIGN-FLIP permutation is used: the
    paired difference d_i = |e_A,i| - |e_B,i| has its sign flipped for a WHOLE player-season block
    at a time, which preserves the clustering the kit's row-level null would destroy.  This is
    declared as a kit gap in NOTES.md section 7 and is NOT presented as a kit function.

HAZARDS honoured (inherited from D076, re-verified in s01): data/w1_truth/player_game_availability
    .csv and roster_asof.csv are asof_granularity "artifact" bound at 2026 -> UNUSABLE, NOT OPENED.
    experiments/minutes_baselines/test_predictions.csv has NO sibling manifest -> UNVERIFIABLE,
    NOT USED.  master_player.pace/pace_per40/estimated_pace are corrupt -> NOT READ.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
KIT = os.path.join(ROOT, r"experiments\exploration\_screen_kit")
OUT = os.path.join(ROOT, r"experiments\exploration\E0_I0015_points_skill_decomposition")
D076 = os.path.join(ROOT, r"experiments\exploration\E0_I0014_residual_heterogeneity")
FRAME = os.path.join(D076, "analysis_frame.parquet")

if KIT not in sys.path:
    sys.path.insert(0, KIT)
import screenkit as sk  # noqa: E402

SEED = 20260807                      # same seed D076 used, for comparability
SCREEN_SEASONS = [2022, 2023, 2024]
COVERAGE_GRID = [1.00, 0.90, 0.80, 0.75, 0.60, 0.50, 0.40, 0.25, 0.10]

os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.dont_write_bytecode = True


def hdr(s):
    print("\n" + "=" * 100)
    print(s)
    print("=" * 100)


def load_frame(verbose=True):
    """Read D076's FROZEN analysis frame.  READ ONLY -- this screen never writes to D076's dir."""
    f = pd.read_parquet(FRAME)
    f = f.sort_values(["season", "player_id", "gdate"]).reset_index(drop=True)
    if verbose:
        print("  loaded D076 analysis_frame.parquet  shape=%s  seasons=%s  max_date=%s"
              % (f.shape, sorted(f["season"].unique()), f["gdate"].max().date()))
    sk.assert_partition(f, verbose=verbose)
    assert set(f["season"].unique()) <= set(SCREEN_SEASONS)
    assert f["gdate"].max() < pd.Timestamp("2025-01-01")
    assert (f["y_minutes"] > 0).all(), "a zero-minute row would make every rate undefined"
    return f


# --------------------------------------------------------------------------- prior-only references
def _expanding_prior_mean(f, valcol):
    """Expanding mean of the player's own STRICTLY PRIOR same-season values of `valcol`.

    Construction: the frame is already sorted (season, player_id, gdate); .shift(1) is applied
    BEFORE .expanding().mean(), so row i sees rows 0..i-1 of its own (season, player) group and
    nothing else.  NaN where the player has no prior appearance this season.
    """
    return f.groupby(["season", "player_id"], sort=False)[valcol].transform(
        lambda x: x.shift(1).expanding().mean())


def _expanding_prior_ratio(f, numcol, dencol):
    """sum(prior numerator) / sum(prior denominator) inside (season, player), strictly prior."""
    g = f.groupby(["season", "player_id"], sort=False)
    num = g[numcol].transform(lambda x: x.shift(1).expanding().sum())
    den = g[dencol].transform(lambda x: x.shift(1).expanding().sum())
    return num / den.replace(0.0, np.nan)


def _league_prior_mean(f, valcol):
    """Expanding league mean over games strictly EARLIER IN THE SAME SEASON (date order).

    Cold-start fallback only.  Same construction D076 used for its level references.
    """
    fs = f.sort_values(["season", "gdate"], kind="stable")
    cum = fs.groupby("season", sort=False)[valcol].transform(
        lambda x: x.shift(1).expanding().mean())
    return cum.reindex(f.index)


def build_references(f, verbose=True):
    """Attach every prior-only reference this screen uses.  ALL are strictly prior-games-only.

    Levels   : ref_pts / ref_minutes / ref_fga are D076's own columns, already in the frame; they
               are NOT rebuilt here (reproduction must use the frozen ones).  refX_* are this
               screen's independent rebuild of the same construction, used only to confirm the
               reproduction is not accidentally reading D076's arithmetic.
    Rates    : for each of ppm / fpm / ppf, REF-A (mean of prior ratios) and REF-B (ratio of prior
               sums), each with the same-season expanding league-mean cold fallback.
    """
    f = f.copy()
    f["r_ppm"] = f["y_pts"] / f["y_minutes"]
    f["r_fpm"] = f["y_fga"] / f["y_minutes"]
    f["r_ppf"] = np.where(f["y_fga"] > 0, f["y_pts"] / f["y_fga"].replace(0, np.nan), np.nan)

    # ---- independent rebuild of D076's LEVEL references (reproduction cross-check) ----
    n_global_fallback = {}
    for t in ["pts", "minutes", "fga"]:
        prior = _expanding_prior_mean(f, "y_" + t)
        lg = _league_prior_mean(f, "y_" + t)
        filled = prior.fillna(lg)
        n_global_fallback[t] = int(filled.isna().sum())
        f["refX_" + t] = filled.fillna(f["y_" + t].mean())

    # ---- RATE references ----
    rate_spec = {"ppm": ("y_pts", "y_minutes"), "fpm": ("y_fga", "y_minutes"),
                 "ppf": ("y_pts", "y_fga")}
    for rt, (num, den) in rate_spec.items():
        col = "r_" + rt
        a = _expanding_prior_mean(f, col)
        b = _expanding_prior_ratio(f, num, den)
        lg = _league_prior_mean(f, col)
        f["refA_" + rt] = a.fillna(lg).fillna(f[col].mean())
        f["refB_" + rt] = b.fillna(lg).fillna(f[col].mean())
        n_global_fallback[rt + "_A"] = int(a.fillna(lg).isna().sum())
        n_global_fallback[rt + "_B"] = int(b.fillna(lg).isna().sum())

    # ---- MODEL implied rates: ratios of the champion's OWN point forecasts, nothing refitted ----
    f["mdl_ppm"] = f["pts__pred_point"] / f["minutes__pred_point"]
    f["mdl_fpm"] = f["fga__pred_point"] / f["minutes__pred_point"]
    f["mdl_ppf"] = np.where(f["fga__pred_point"] > 0,
                            f["pts__pred_point"] / f["fga__pred_point"].replace(0, np.nan), np.nan)

    if verbose:
        print("  reference construction: strictly-prior expanding, .shift(1) BEFORE .expanding()")
        print("  rows still NaN after player-prior AND same-season league-prior fallback "
              "(these take the whole-sample-mean fallback D076 also used): %s" % n_global_fallback)
    return f, n_global_fallback


# --------------------------------------------------------------------------- skill
def mae(y, yhat):
    y = np.asarray(y, float)
    yhat = np.asarray(yhat, float)
    return float(np.mean(np.abs(y - yhat)))


def r2_forecast(y, yhat):
    """R2 OF A GIVEN FORECAST: 1 - SSE/SST, SSE about the SUPPLIED yhat, SST about the unweighted
    mean of y.  D069 convention on the denominator.

    *** THIS IS NOT screenkit.r2_plain. ***  `screenkit.r2_plain(y, X)` treats its second argument
    as REGRESSORS and fits an intercept and slope by OLS, so calling it with a forecast reports the
    R2 of the BEST LINEAR RESCALING of that forecast, which is >= the forecast's own R2.  Measured
    here on the frozen frame: points 0.4747 (kit, refit) vs 0.4694 (as-is) -- and 0.4694 is the
    number D076 published, via its own `rh_base.r2_plain(y, yhat)` which has the SAME NAME and
    DIFFERENT SEMANTICS.  Both are reported in FINDINGS.json, labelled.  See NOTES.md section 7.
    """
    y = np.asarray(y, float)
    yhat = np.asarray(yhat, float)
    sse = float(((y - yhat) ** 2).sum())
    sst = float(((y - y.mean()) ** 2).sum())
    return 1.0 - sse / sst if sst > 0 else float("nan")


def skill(y, yhat_model, yhat_ref):
    """1 - MAE_model/MAE_ref.  BOTH computed on the SAME rows -- that is the whole point."""
    mm, mr = mae(y, yhat_model), mae(y, yhat_ref)
    return float(1.0 - mm / mr), mm, mr


# --------------------------------------------------------------------------- paired block sign-flip
def block_signflip_test(diff, block_codes, n_draws=2000, seed=SEED, return_draws=False):
    """Paired permutation test for mean(diff) at the (season, player) BLOCK level.

    diff_i = |e_A,i| - |e_B,i| for two forecasts scored on the SAME row i.  Under the null that the
    two forecasts are exchangeable for a given player-season, the sign of the WHOLE block's
    contribution may be flipped.  Flipping per ROW would treat 13,879 correlated rows as
    independent and is exactly the anticonservative row-level null this program has found wrong six
    times; flipping per block preserves the clustering.

    NOT a screen-kit function -- the kit has no paired/sign-flip scheme.  Declared in NOTES.md.
    Returns two-sided p on |mean(diff)|.
    """
    d = np.asarray(diff, float)
    ok = np.isfinite(d)
    d = np.where(ok, d, 0.0)
    codes = np.asarray(block_codes)
    uq, inv = np.unique(codes, return_inverse=True)
    nb = len(uq)
    # per-block sums and counts (counts use only finite rows so the mean stays honest)
    bsum = np.bincount(inv, weights=d, minlength=nb)
    n_ok = int(ok.sum())
    real = float(bsum.sum() / n_ok)
    rng = np.random.default_rng(seed)
    draws = np.empty(n_draws, float)
    for i in range(n_draws):
        s = rng.choice(np.array([-1.0, 1.0]), size=nb)
        draws[i] = float((bsum * s).sum() / n_ok)
    p = (1.0 + int((np.abs(draws) >= abs(real)).sum())) / (n_draws + 1.0)
    res = {"mean_diff": real, "p_two_sided_blockflip": float(p), "n_blocks": nb,
           "n_rows": n_ok, "null_sd": float(draws.std(ddof=1)), "n_draws": int(n_draws),
           "seed": int(seed)}
    if return_draws:
        res["draws"] = draws
    return res


def block_codes_player_season(f):
    return sk._group_codes(f, ["season", "player_id"])


# --------------------------------------------------------------------------- abstention
def abstention_curve(f, feature, y, yhat_model, yhat_ref, ascending=True, grid=None):
    """Skill vs coverage when the WORST-ranked rows on `feature` are abstained on.

    `ascending=True` keeps the rows with the SMALLEST feature values.  The reference is recomputed
    on the SAME kept rows at every coverage -- the D076 lesson: a rule that cuts model MAE while
    cutting the reference's MAE by as much carries no differential skill.
    """
    grid = grid or COVERAGE_GRID
    v = pd.to_numeric(pd.Series(feature), errors="coerce").to_numpy(float)
    y = np.asarray(y, float)
    m = np.asarray(yhat_model, float)
    r = np.asarray(yhat_ref, float)
    fin = np.isfinite(v) & np.isfinite(y) & np.isfinite(m) & np.isfinite(r)
    order = np.argsort(np.where(fin, v, np.inf), kind="stable")
    if not ascending:
        order = np.argsort(np.where(fin, -v, np.inf), kind="stable")
    rows = []
    n = int(fin.sum())
    for cov in grid:
        k = max(int(round(cov * n)), 30)
        keep = order[:k]
        keep = keep[fin[keep]]
        if len(keep) < 30:
            continue
        s, mm, mr = skill(y[keep], m[keep], r[keep])
        rows.append(dict(coverage=cov, n_kept=int(len(keep)), model_mae=mm, ref_mae=mr, skill=s))
    return pd.DataFrame(rows)
