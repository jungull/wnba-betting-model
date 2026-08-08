"""E0_I0029 FREE-THROW HURDLE -- shared loader, prior-only helpers, fast dR2, null machinery.

WHY THIS SCREEN EXISTS.  Free throws are 17.37% of points and the one substantial scoring channel
    this programme has never screened; D084's ruling names it explicitly untested.  `fta == 0` on
    46.4% of rows, so free-throw production is a HURDLE PROCESS -- first WHETHER a player reaches
    the line, then HOW MANY attempts, then CONVERSION -- and every screen so far has modelled
    rates only.  A signal living in the hurdle would have been invisible to all of them.

THE THREE STAGES ARE MEASURED SEPARATELY.
    A  y_any_fta      1{fta>0}          binary, FULL row set
    B  y_fta_given    fta | fta>0       count,  CONDITIONAL row set
    C  y_ftm_given    ftm | fta>0       made,   CONDITIONAL row set (exposure = REALISED fta)

D099 DENOMINATOR RULE.  B and C live on a SUBSET.  A dR2 computed on a subset's SST is NOT
    comparable to one on the full stratum's.  Every table in this screen carries an explicit
    `denominator` column, and the headline "which stage carries the predictability" question is
    answered on a SINGLE COMMON DENOMINATOR -- SST(ftm) over the FULL decision stratum -- by the
    stage-oracle substitution in s04.  Per-stage dR2 on each stage's own SST is reported alongside
    and is NEVER compared across stages.

PARTITION.  Seasons 2021-2024 ONLY, HEADLINE 2022-2024 (matching D081/D097 reproduction rows).
    2025/2026 is never read, joined, plotted or described.  Enforced by assert_partition on VALUES.

THE SHARED KIT (_screen_kit) IS NOT IMPORTED.  Everything needed is implemented here, following
    E0_I0024/rb_base.py (READ-ONLY), which in turn credits E1_I0018/tv_base.py and
    E1_I0021_heterogeneity_diagnostic/hd_base.py.  The cyclic-shift and entity-swap nulls are
    reproduced from those files.

TRAP 3 -- RETROSPECTIVE BASELINES (six instances, one via the INFERENCE machinery).  Every
    reference is strictly prior-games-only: .shift(1) ALWAYS precedes .expanding()/.rolling(),
    inside (season, entity), on rows sorted by date then game_id.  s02 verifies this by BRUTE
    FORCE recomputation on a random sample rather than by inspection.

TRAP 5 -- AUTOCORRELATION (D093).  Prior-history regressors are running means and strongly
    autocorrelated; a plain within-player shuffle is anticonservative.  A WITHIN-PLAYER CYCLIC
    SHIFT is used instead.

TRAP 6 -- CORRECT-LEVEL NULLS (nine confirmations).  Opponent terms vary at opponent-team-season
    and are nulled by ENTITY SWAP at that level.  The row-level null is reported ALONGSIDE every
    verdict to expose the inflation factor and is NEVER itself a verdict.  Cluster-robust SEs are
    not used as a substitute; they moved t the WRONG way twice in this programme.

D085 -- THE INTERACTION TRAP.  The foul-draw matchup interaction cleared family-wise on all three
    outcomes and then went to EXACTLY ZERO once its own two main effects were in the base.  Here
    BOTH main effects are in the base FROM THE START (B_MATCHUP) and the interaction is only ever
    reported over that base.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
OUT = os.path.join(ROOT, r"experiments\exploration\E0_I0029_freethrow_hurdle")
MP_PATH = os.path.join(ROOT, r"data\masters\master_player.parquet")
MT_PATH = os.path.join(ROOT, r"data\masters\master_team.parquet")

SEED = 20260808
SEASONS = (2021, 2022, 2023, 2024)
HEADLINE_SEASONS = (2022, 2023, 2024)
N_DRAWS = 600
HISTORY_FLOOR = 10.0          # applied to HISTORY ONLY, never to the response (D091 ruling 3)
EWMA_HALFLIFE = 5.0

# FORBIDDEN -- never opened.  Listed so the check is explicit rather than implicit.
FORBIDDEN = [
    os.path.join(ROOT, r"data\w1_truth\player_game_availability.csv"),
    os.path.join(ROOT, r"data\w1_truth\roster_asof.csv"),
    os.path.join(ROOT, r"data\zone_maps"),
]

os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.dont_write_bytecode = True
pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 200)

# ---------------------------------------------------------------------------- targets
# rowset: FULL      = every appeared player-game in the stratum
#         CONDITIONAL = the fta>0 subset of the same stratum
TARGETS = {
    "y_any_fta":   dict(rowset="FULL",        exposure="minutes", stage="A",
                        desc="1{fta>0} -- THE HURDLE"),
    "y_fta_given": dict(rowset="CONDITIONAL", exposure="minutes", stage="B",
                        desc="fta | fta>0 -- attempts given at least one"),
    "y_ftm_given": dict(rowset="CONDITIONAL", exposure="fta",     stage="C",
                        desc="ftm | fta>0 -- conversion given attempts (exposure = REALISED fta)"),
    "y_fta":       dict(rowset="FULL",        exposure="minutes", stage="AB",
                        desc="fta unconditional -- the composed A x B"),
    "y_ftm":       dict(rowset="FULL",        exposure="minutes", stage="ABC",
                        desc="ftm unconditional -- FREE-THROW POINTS, the composed A x B x C"),
    "y_pts":       dict(rowset="FULL",        exposure="minutes", stage="ANCHOR",
                        desc="points -- CALIBRATION ANCHOR ONLY (D081/D097), no new claim"),
}
TARGET_ORDER = ["y_any_fta", "y_fta_given", "y_ftm_given", "y_fta", "y_ftm", "y_pts"]

# the advanced-box "percentage" companion for each target (a prior-only rate reference)
TARGET_PCT = {
    "y_any_fta":   "usage_percentage",
    "y_fta_given": "usage_percentage",
    "y_ftm_given": "true_shooting_percentage",
    "y_fta":       "usage_percentage",
    "y_ftm":       "usage_percentage",
    "y_pts":       "usage_percentage",
}

BASE_COLS = {
    # D087: REFERENCE INCOMPLETENESS is the top-ranked source of false results here.  The same
    # result has moved 6.5x, 4.6x and 8.12 points on reference choice alone.  B_COMPLETE puts
    # EVERY available strictly-prior measurement of the target in the base.  A candidate is only
    # reported ALIVE if it survives B_COMPLETE.
    "B_SINGLE": ["ref_mean"],
    "B_COMPLETE": ["ref_mean", "ref_ewma", "ref_trail5", "ref_rate_x_min", "ref_mean_minutes",
                   "ref_trail5_minutes", "ref_pct", "ref_mean_pace", "n_prior", "is_home"],
}
# target-specific columns inside a base (get the "__<target>" suffix in the built frame)
TARGET_SPECIFIC = ("ref_mean", "ref_ewma", "ref_trail5", "ref_rate_x_min", "ref_pct")


def basecols_for(base_name, target):
    out = []
    for c in BASE_COLS[base_name]:
        out.append(c + "__" + target if c in TARGET_SPECIFIC else c)
    return out


def hdr(s):
    print("\n" + "=" * 100)
    print(s)
    print("=" * 100)


def sha(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"),
                                     default=str).encode("utf-8")).hexdigest()


# ============================================================================= manifests
def manifest_status(path):
    """Read the sidecar manifest FROM DISK at call time.  A MISSING MANIFEST IS UNVERIFIABLE,
    NEVER A PASS -- 68 shared artifacts in this repo have no manifest at all."""
    mpath = path + ".manifest.json"
    if not os.path.exists(mpath):
        return dict(artifact=os.path.relpath(path, ROOT), manifest_present=False,
                    asof_granularity=None, fit_through_season=None,
                    status="UNVERIFIABLE_NO_MANIFEST", usable=None)
    m = json.load(open(mpath))
    g, fts = m.get("asof_granularity"), m.get("fit_through_season")
    if g == "row":
        st, us = "USABLE_IF_FILTERED", True
    elif g == "artifact":
        ok = fts is not None and fts <= 2024
        st, us = ("USABLE_ARTIFACT_WITHIN_PARTITION" if ok else "UNUSABLE"), ok
    else:
        st, us = "UNVERIFIABLE_UNKNOWN_GRANULARITY", None
    return dict(artifact=os.path.relpath(path, ROOT), manifest_present=True, asof_granularity=g,
                fit_through_season=fts, status=st, usable=us,
                content_sha256=m.get("content_sha256"))


def assert_partition(df, season_cols=("season",), date_cols=("game_date",), verbose=True):
    """VALUE test: parse season-valued columns and date columns and assert nothing lies outside
    2021-2024.  Never scans names or bytes."""
    viol, seen = [], {}
    for c in season_cols:
        if c in df.columns:
            v = sorted(pd.unique(pd.to_numeric(df[c], errors="coerce").dropna()).tolist())
            seen[c] = v
            bad = [x for x in v if x not in SEASONS]
            if bad:
                viol.append("season col %s has %s" % (c, bad))
    for c in date_cols:
        if c in df.columns:
            d = pd.to_datetime(df[c], errors="coerce")
            yrs = sorted(pd.unique(d.dt.year.dropna()).astype(int).tolist())
            seen[c] = yrs
            bad = [y for y in yrs if y not in SEASONS]
            if bad:
                viol.append("date col %s has years %s" % (c, bad))
    ok = len(viol) == 0
    if verbose:
        print("  assert_partition ok=%s  %s" % (ok, seen))
    assert ok, "PARTITION VIOLATION: %s" % viol
    return dict(ok=ok, seen=seen)


# ============================================================================= prior-only helpers
# In EVERY one of these, .shift(1) precedes the accumulator.  That is the whole of trap 3.
def prior_sum(df, keys, col):
    return df.groupby(list(keys), sort=False)[col].transform(
        lambda x: x.shift(1).expanding().sum())


def prior_mean(df, keys, col):
    return df.groupby(list(keys), sort=False)[col].transform(
        lambda x: x.shift(1).expanding().mean())


def prior_count(df, keys, col):
    return df.groupby(list(keys), sort=False)[col].transform(
        lambda x: x.shift(1).expanding().count())


def prior_trail(df, keys, col, k=5):
    return df.groupby(list(keys), sort=False)[col].transform(
        lambda x: x.shift(1).rolling(k, min_periods=1).mean())


def prior_ewma(df, keys, col, halflife=EWMA_HALFLIFE):
    return df.groupby(list(keys), sort=False)[col].transform(
        lambda x: x.shift(1).ewm(halflife=halflife, min_periods=1).mean())


def league_prior_mean(df, valcol, seasoncol="season", datecol="game_date", tiecol="game_id"):
    """Expanding league mean over rows strictly EARLIER IN THE SAME SEASON.  COLD START ONLY."""
    fs = df.sort_values([seasoncol, datecol, tiecol], kind="stable")
    cum = fs.groupby(seasoncol, sort=False)[valcol].transform(
        lambda x: x.shift(1).expanding().mean())
    return cum.reindex(df.index)


def safe_div(a, b):
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(np.isfinite(b) & (b != 0), a / b, np.nan)


# ============================================================================= fast incremental R2
class BaseFit:
    """Precomputed residualiser for a fixed base design [1, base...].

    dR2 of adding candidate x is ((e . xt)^2 / (xt . xt)) / SST, with e = y residualised on the
    base and xt = x residualised on the base.  Algebraically identical to refitting
    y ~ 1 + base + x and differencing R2.  D069 convention: SST about the UNWEIGHTED mean.
    Verified against a literal two-fit difference in s03 before any null is drawn.

    Adapted from E0_I0024/rb_base.py (read-only), which adapted E1_I0018/tv_base.py.
    """

    def __init__(self, y, base):
        y = np.asarray(y, float)
        base = np.asarray(base, float)
        if base.ndim == 1:
            base = base[:, None]
        self.n = len(y)
        X = np.column_stack([np.ones(self.n), base])
        self.X = X
        self.XtXi = np.linalg.pinv(X.T @ X)
        self.y = y
        self.e = y - X @ (self.XtXi @ (X.T @ y))
        self.sst = float(((y - y.mean()) ** 2).sum())
        self.r2_base = 1.0 - float(self.e @ self.e) / self.sst if self.sst > 0 else np.nan

    def resid_x(self, x):
        x = np.asarray(x, float)
        return x - self.X @ (self.XtXi @ (self.X.T @ x))

    def dr2(self, x):
        xt = self.resid_x(x)
        den = float(xt @ xt)
        if not np.isfinite(den) or den <= 1e-12:
            return 0.0
        num = float(self.e @ xt)
        return (num * num / den) / self.sst

    def beta(self, x):
        """OLS coefficient on x in y ~ 1 + base + x (Frisch-Waugh)."""
        xt = self.resid_x(x)
        den = float(xt @ xt)
        if den <= 1e-12:
            return 0.0
        return float((self.e @ xt) / den)

    def resid_sd(self, x):
        return float(np.std(self.resid_x(x), ddof=1))


def r2_plain(y, yhat):
    y = np.asarray(y, float)
    yhat = np.asarray(yhat, float)
    m = np.isfinite(y) & np.isfinite(yhat)
    y, yhat = y[m], yhat[m]
    sst = float(((y - y.mean()) ** 2).sum())
    sse = float(((y - yhat) ** 2).sum())
    return 1.0 - sse / sst if sst > 0 else np.nan


def mae(y, yhat):
    y = np.asarray(y, float)
    yhat = np.asarray(yhat, float)
    m = np.isfinite(y) & np.isfinite(yhat)
    return float(np.mean(np.abs(y[m] - yhat[m])))


def rmse(y, yhat):
    y = np.asarray(y, float)
    yhat = np.asarray(yhat, float)
    m = np.isfinite(y) & np.isfinite(yhat)
    return float(np.sqrt(np.mean((y[m] - yhat[m]) ** 2)))


# ============================================================================= null machinery
def group_blocks(codes_sorted):
    """`codes_sorted` MUST already be sorted by (entity, date).  Returns starts and lengths."""
    uq, start = np.unique(codes_sorted, return_index=True)
    ends = np.append(start[1:], len(codes_sorted))
    return uq, start, (ends - start)


def cyclic_shift_within_groups(x, group_starts, group_ns, rng):
    """Rotate each group's series by a random offset.  Rows MUST be sorted by group, then DATE.

    D093's trap.  A cyclic shift preserves each entity's marginal distribution AND its serial
    correlation structure exactly, and destroys only the alignment to the response.  A plain
    shuffle destroys the autocorrelation and is anticonservative for running-mean regressors
    (p 0.0015 vs an honest 0.39 in D093).  Credited to E1_I0021/hd_base.py (read-only).
    """
    out = np.empty_like(x)
    for a, n in zip(group_starts, group_ns):
        if n <= 1:
            out[a:a + n] = x[a:a + n]
            continue
        k = int(rng.integers(0, n))
        out[a:a + n] = np.roll(x[a:a + n], k)
    return out


def entity_swap_within_season(x, ent_codes, season_codes, rng):
    """CORRECT-LEVEL NULL for a candidate that varies at an ENTITY (e.g. opponent-team-season).

    Within each season the entities' whole ordered value-series are reassigned to one another.
    Entity A's rows receive entity pi(A)'s series, wrapping cyclically when lengths differ.  This
    preserves each series' own level and serial structure and destroys only the alignment between
    an entity's profile and the responses it faces.  Nine confirmations in this programme say this
    is the right null; a row-level shuffle is far too narrow.
    """
    out = np.empty_like(x)
    for s in np.unique(season_codes):
        smask = np.flatnonzero(season_codes == s)
        ents = ent_codes[smask]
        uq = np.unique(ents)
        if len(uq) < 2:
            out[smask] = x[smask]
            continue
        perm = rng.permutation(len(uq))
        idx_by_ent = {e: smask[ents == e] for e in uq}
        for i, e in enumerate(uq):
            src = uq[perm[i]]
            dst_rows = idx_by_ent[e]
            src_vals = x[idx_by_ent[src]]
            k = len(dst_rows)
            if len(src_vals) == 0:
                out[dst_rows] = np.nan
                continue
            reps = int(np.ceil(k / len(src_vals)))
            out[dst_rows] = np.tile(src_vals, reps)[:k]
    return out


def row_shuffle(x, rng):
    """NAIVE row-level shuffle.  REPORTED FOR INFLATION ONLY -- NEVER A VERDICT."""
    return x[rng.permutation(len(x))]


def perm_p(real, draws, alternative="greater"):
    d = np.asarray(draws, float)
    d = d[np.isfinite(d)]
    if len(d) == 0:
        return float("nan")
    if alternative == "greater":
        return float((1.0 + int((d >= real).sum())) / (len(d) + 1.0))
    return float((1.0 + int((np.abs(d) >= abs(real)).sum())) / (len(d) + 1.0))


def maxt_family(store):
    """Family-wise max-t across a dict of cell_key -> draws.  Standardise each cell's draws by its
    own null mean/sd, then take the max over cells within each draw index."""
    keys = list(store.keys())
    D = np.vstack([np.asarray(store[k], float) for k in keys])
    mu = D.mean(axis=1, keepdims=True)
    sd = D.std(axis=1, ddof=1, keepdims=True)
    sd = np.where(sd > 1e-300, sd, np.nan)
    T = (D - mu) / sd
    return keys, mu[:, 0], sd[:, 0], np.nanmax(T, axis=0)


def fw_p(real, key, keys_index, mu, sd, maxt):
    i = keys_index[key]
    if not np.isfinite(sd[i]) or sd[i] <= 0:
        return float("nan"), float("nan")
    t = (real - mu[i]) / sd[i]
    return float(t), float((1.0 + int((maxt >= t).sum())) / (len(maxt) + 1.0))


# ============================================================================= normal tail (no scipy)
def norm_sf(z):
    """Upper tail of the standard normal.  scipy is NOT installed in this environment, so the
    complementary error function is implemented here (Abramowitz & Stegun 7.1.26 has only ~1e-7
    absolute accuracy; this uses the standard continued-fraction-free rational approximation with
    |eps| < 1.2e-7, which is ample -- every verdict in this screen is carried by a PERMUTATION p,
    and these z's are reported for orientation only)."""
    z = np.asarray(z, float)
    t = 1.0 / (1.0 + 0.5 * np.abs(z) / np.sqrt(2.0))
    y = t * np.exp(-(np.abs(z) / np.sqrt(2.0)) ** 2 - 1.26551223 + t * (
        1.00002368 + t * (0.37409196 + t * (0.09678418 + t * (-0.18628806 + t * (
            0.27886807 + t * (-1.13520398 + t * (1.48851587 + t * (
                -0.82215223 + t * 0.17087277)))))))))
    erfc = np.where(z >= 0, y, 2.0 - y)
    return 0.5 * erfc


def jsonable(o):
    if isinstance(o, dict):
        return {str(k): jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [jsonable(v) for v in o]
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.ndarray):
        return [jsonable(v) for v in o.tolist()]
    if isinstance(o, pd.Timestamp):
        return str(o)
    return o
