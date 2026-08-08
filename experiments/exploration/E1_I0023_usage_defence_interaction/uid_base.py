"""
E1_I0023 -- USAGE x OPPONENT-DEFENCE INTERACTION.  Shared loader / fitting / inference machinery.

WHAT THIS SCREEN TESTS.  D093 (E1_I0021) established a STRUCTURAL fact: per-player sensitivity to
    opponent defence rises with the player's own strictly-prior usage (Spearman +0.320, family-wise
    p 0.0035 under the cyclic-shift null, both negative controls null).  That says NOTHING about
    whether a usage x defence INTERACTION TERM improves a forecast.  This screen asks that second
    question, and asks it against a COMPLETE prior reference, because reference incompleteness is
    the top-ranked explanation for this programme's nulls (D090: the same forecast scored +46.4% or
    +7.1% by reference choice alone).

WHY THE KIT IS NOT IMPORTED.  `experiments\\exploration\\_screen_kit` is being edited concurrently by
    another agent and this screen was directed not to import it.  Everything needed is reimplemented
    here: the partition gate, the OLS/dR2 machinery, the paired cluster-level forecast comparison and
    the permutation nulls.  `cyclic_shift_within_groups` and `group_slopes_fast` are
    REIMPLEMENTATIONS OF D093's `hd_base.py` (E1_I0021, read-only) and that authorship is credited
    here and in NOTES.md; the step-1 reproduction is the check that the reimplementation is faithful.

PARTITION.  Seasons 2021-2024 only (effectively 2022-2024 for every scored figure; 2021 appears only
    as a TRAINING fold in the walk-forward, exactly as D089 used it).  2025/2026 is never read,
    joined, plotted or described.  Enforced on VALUES by `assert_partition` below.

THE CHAMPION IS NEVER TOUCHED.  No champion forecast is loaded, scored, retrained or modified.
    Fitting pooled screening models in the exploration lane is authorised by D091 ruling 1.
"""
import hashlib
import json
import os
import sys

import numpy as np
import pandas as pd

sys.dont_write_bytecode = True
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
EXP = os.path.join(ROOT, r"experiments\exploration")
OUT = os.path.join(EXP, "E1_I0023_usage_defence_interaction")
D085F = os.path.join(EXP, "E0_I0016_efficiency_predictors")
D089F = os.path.join(EXP, "E1_I0018_teammate_volume_channel")

SEED = 20260808                 # same seed constant D093 used, so its nulls reproduce bit-for-bit
ALLOWED_SEASONS = {2021, 2022, 2023, 2024}
SCORED_SEASONS = [2022, 2023, 2024]
FORBIDDEN_YEARS = (2025, 2026)


def hdr(s):
    print("\n" + "=" * 100)
    print(s)
    print("=" * 100)


def sha(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")
                                     ).encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- partition gate
def assert_partition(f, verbose=False):
    """VALUE-level partition gate.  Reimplemented locally; does not import the shared kit.

    Checks (a) every `season` value is inside the exploration partition and (b) no datetime column
    carries a 2025 or 2026 timestamp.  Columns whose name merely LOOKS like a date but whose values
    are not datetimes are skipped rather than coerced -- coercion is how a gate produces a false
    pass.
    """
    if "season" in f.columns:
        bad = sorted(set(int(s) for s in pd.unique(f["season"])) - ALLOWED_SEASONS)
        assert not bad, "PARTITION VIOLATION: seasons %s outside %s" % (bad, sorted(ALLOWED_SEASONS))
    checked = []
    for c in f.columns:
        s = f[c]
        if not pd.api.types.is_datetime64_any_dtype(s):
            continue
        mx = s.max()
        if pd.notna(mx):
            assert mx.year not in FORBIDDEN_YEARS and mx < pd.Timestamp("2025-01-01"), \
                "PARTITION VIOLATION: column %s reaches %s" % (c, mx)
        checked.append(c)
    if verbose:
        print("  assert_partition PASS  seasons=%s  datetime cols gated=%s"
              % (sorted(set(int(s) for s in pd.unique(f["season"]))) if "season" in f.columns
                 else "n/a", checked))
    return True


# --------------------------------------------------------------------------- loaders (READ ONLY)
def load_eff(verbose=True, include_2021=True):
    """D085's FROZEN screen_frame (opponent-allowance family).  READ ONLY."""
    f = pd.read_parquet(os.path.join(D085F, "screen_frame.parquet"))
    f["game_date"] = pd.to_datetime(f["game_date"])
    assert_partition(f)
    if not include_2021:
        f = f.loc[f["season"] != 2021]
    f = f.sort_values(["season", "player_id", "game_date"]).reset_index(drop=True)
    if verbose:
        print("  D085 screen_frame: %d rows seasons=%s max_date=%s"
              % (len(f), sorted(f["season"].unique()), f["game_date"].max().date()))
    return f


def load_tv(verbose=True, include_2021=True):
    """D089's FROZEN screen_frame (teammate-volume channel).  READ ONLY."""
    f = pd.read_parquet(os.path.join(D089F, "screen_frame.parquet"))
    f["game_date"] = pd.to_datetime(f["game_date"])
    assert_partition(f)
    if not include_2021:
        f = f.loc[f["season"] != 2021]
    f = f.sort_values(["season", "player_id", "game_date"]).reset_index(drop=True)
    if verbose:
        print("  D089 screen_frame: %d rows seasons=%s max_date=%s"
              % (len(f), sorted(f["season"].unique()), f["game_date"].max().date()))
    return f


def build_merged(verbose=True, include_2021=True, tv_cols=None):
    """Merge D085's opponent frame onto D089's player frame on (season, player_id, game_id).

    D093's `s02.build_merged` is reproduced EXACTLY when include_2021=False and
    tv_cols=D093's three columns; the extra columns and 2021 rows requested here are additive and
    never change the merge keys or the row set at a given season filter.
    """
    if tv_cols is None:
        tv_cols = ["P01_c04_prevgame", "O01_own_usg_pg", "G01_noise"]
    a = load_eff(verbose=verbose, include_2021=include_2021)
    b = load_tv(verbose=verbose, include_2021=include_2021)
    k = ["season", "player_id", "game_id"]
    m = a.merge(b[k + [c for c in tv_cols if c not in k]], on=k, how="inner", suffixes=("", "_tv"))
    m = m.rename(columns={"G01_noise_tv": "G01_noise_tvframe"})
    m["game_date"] = pd.to_datetime(m["game_date"])
    m = m.sort_values(["season", "player_id", "game_date"]).reset_index(drop=True)
    assert_partition(m)
    assert np.allclose(m["y_ppm"], m["pts"] / m["minutes"])
    return m


# --------------------------------------------------------------------------- D093 reproduction bits
def floor_subset(m, floor):
    """D093 s02.floor_subset, reimplemented.  Realised-minutes floor + floor-aware persistence ref."""
    s = m.loc[m["minutes"] >= float(floor)].copy()
    s = s.sort_values(["season", "player_id", "game_date"]).reset_index(drop=True)
    s["y_ppm_floor"] = s["pts"] / s["minutes"]
    prior = s.groupby(["season", "player_id"], sort=False)["y_ppm_floor"].transform(
        lambda x: x.shift(1).expanding().mean())
    fs = s.sort_values(["season", "game_date"], kind="stable")
    lg = fs.groupby("season", sort=False)["y_ppm_floor"].transform(
        lambda x: x.shift(1).expanding().mean()).reindex(s.index)
    s["refA_ppm_floor"] = prior.fillna(lg).fillna(s["y_ppm_floor"].mean())
    return s


def complete_case(s, cols):
    ok = np.ones(len(s), bool)
    for c in cols:
        if c in s.columns:
            ok &= np.isfinite(pd.to_numeric(s[c], errors="coerce").to_numpy(float))
    return s.loc[ok].reset_index(drop=True), int((~ok).sum())


def group_slopes_fast(x, y, gcode, ng, min_games=8):
    """VECTORISED per-group within-demeaned OLS slope + se.  Reimplementation of D093 hd_base."""
    n = np.bincount(gcode, minlength=ng).astype(float)
    sx = np.bincount(gcode, weights=x, minlength=ng)
    sy = np.bincount(gcode, weights=y, minlength=ng)
    with np.errstate(invalid="ignore", divide="ignore"):
        mx = sx / n
        my = sy / n
    xc = x - mx[gcode]
    yc = y - my[gcode]
    sxx = np.bincount(gcode, weights=xc * xc, minlength=ng)
    sxy = np.bincount(gcode, weights=xc * yc, minlength=ng)
    with np.errstate(invalid="ignore", divide="ignore"):
        beta = np.where(sxx > 0, sxy / np.where(sxx > 0, sxx, 1.0), np.nan)
    resid = yc - np.where(np.isfinite(beta), beta, 0.0)[gcode] * xc
    sse = np.bincount(gcode, weights=resid * resid, minlength=ng)
    dof = n - 2.0
    with np.errstate(invalid="ignore", divide="ignore"):
        s2 = np.where(dof > 0, sse / np.where(dof > 0, dof, 1.0), np.nan)
        se = np.sqrt(np.where(sxx > 0, s2 / np.where(sxx > 0, sxx, 1.0), np.nan))
    valid = (n >= min_games) & (sxx > 0) & np.isfinite(beta) & np.isfinite(se) & (dof > 0)
    return beta, se, n, valid


def cyclic_shift_within_groups(x, group_starts, group_ns, rng):
    """Rotate each group's series by a random offset.  Rows MUST be sorted group-then-date.

    THE HONEST NULL FOR AUTOCORRELATED REGRESSORS (D093 constraint 2).  A plain within-player
    shuffle destroys the regressor's serial structure and is ANTICONSERVATIVE: D093 measured
    p 0.0015 under the shuffle where this null returns p 0.39.  Reimplementation of D093 hd_base.
    """
    out = np.empty_like(x)
    for a, n in zip(group_starts, group_ns):
        if n <= 1:
            out[a:a + n] = x[a:a + n]
            continue
        k = int(rng.integers(0, n))
        out[a:a + n] = np.roll(x[a:a + n], k)
    return out


def spearman(a, b):
    ok = np.isfinite(a) & np.isfinite(b)
    if ok.sum() < 10:
        return np.nan
    ra = pd.Series(a[ok]).rank().to_numpy()
    rb = pd.Series(b[ok]).rank().to_numpy()
    sa, sb = ra.std(), rb.std()
    if sa == 0 or sb == 0:
        return np.nan
    return float(np.mean((ra - ra.mean()) * (rb - rb.mean())) / (sa * sb))


# --------------------------------------------------------------------------- forecasting machinery
def mae(y, yhat):
    y = np.asarray(y, float)
    yhat = np.asarray(yhat, float)
    m = np.isfinite(y) & np.isfinite(yhat)
    return float(np.mean(np.abs(y[m] - yhat[m])))


def r2_of_forecast(y, yhat):
    """1 - SSE/SST of a GIVEN forecast.  NOT an OLS refit (D081's r2_plain name collision)."""
    y = np.asarray(y, float)
    yhat = np.asarray(yhat, float)
    sse = float(((y - yhat) ** 2).sum())
    sst = float(((y - y.mean()) ** 2).sum())
    return float(1.0 - sse / sst) if sst > 0 else np.nan


def ols(X, y):
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    return b


def paired_cluster_test(y, pred_a, pred_b, cluster_codes, n_clusters, n_draws=2000, seed=SEED):
    """Paired dR2 of forecast A over forecast B with a WHOLE-CLUSTER SIGN-FLIP null.

    dR2 = (SSE_B - SSE_A) / SST, i.e. the R2 forecast A adds over forecast B on identical rows.
    The null flips the SIGN of every row's paired squared-error difference inside a whole cluster,
    which preserves the within-cluster correlation of the differences.  Rows inside a cluster are
    NOT independent -- one opponent-team-season carries a single defence value all season -- so the
    row-level null is anticonservative.  BOTH are returned and the CLUSTER one is the verdict; this
    programme has confirmed the wrong-null trap nine times.

    `cluster_codes` must be GLOBAL codes (the same integer means the same opponent-team-season in
    every cell), so that a shared seed produces the SAME sign pattern in every cell.  That coupling
    is what makes the max-statistic family-wise null across cells legitimate rather than a stack of
    independently drawn maxima.
    """
    y = np.asarray(y, float)
    a = np.asarray(pred_a, float)
    b = np.asarray(pred_b, float)
    d = (y - b) ** 2 - (y - a) ** 2            # positive where A is better
    sst = float(((y - y.mean()) ** 2).sum())
    obs = float(d.sum() / sst)
    codes = np.asarray(cluster_codes, int)
    per_cluster = np.bincount(codes, weights=d, minlength=n_clusters)
    rng = np.random.default_rng(seed)
    signs = rng.choice(np.array([-1.0, 1.0]), size=(n_draws, n_clusters))
    draws = (signs @ per_cluster) / sst
    p_cluster = (1.0 + int((np.abs(draws) >= abs(obs)).sum())) / (n_draws + 1.0)
    rng2 = np.random.default_rng(seed + 7)
    rdraws = np.empty(n_draws)
    for k in range(n_draws):
        s = rng2.choice(np.array([-1.0, 1.0]), size=len(d))
        rdraws[k] = float((s * d).sum() / sst)
    p_row = (1.0 + int((np.abs(rdraws) >= abs(obs)).sum())) / (n_draws + 1.0)
    sd_c = float(np.std(draws, ddof=1))
    sd_r = float(np.std(rdraws, ddof=1))
    return dict(dr2_a_minus_b=obs, p_cluster=p_cluster, p_row_NAIVE=p_row,
                n_clusters_present=int(len(np.unique(codes))), null_sd_cluster=sd_c,
                null_sd_row=sd_r,
                null_width_inflation_cluster_over_row=(sd_c / sd_r if sd_r > 0 else np.nan),
                draws_cluster=draws)


def usage_terciles(u_train, u_apply):
    """Tercile cut points taken from the TRAINING rows only and applied forward.

    PRE-GAME IDENTIFIABLE: `u` is the player's strictly-prior usage per game, and the cut points
    come from earlier seasons, so a tier label could have been assigned before tip-off.
    """
    q = np.quantile(u_train, [1.0 / 3.0, 2.0 / 3.0])
    return np.digitize(u_apply, q), q
