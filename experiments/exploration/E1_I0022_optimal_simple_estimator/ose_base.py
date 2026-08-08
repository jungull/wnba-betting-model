"""E1_I0022 OPTIMAL SIMPLE ESTIMATOR -- local machinery.

WHY LOCAL.  `experiments/exploration/_screen_kit/` is being edited by a concurrently running agent,
so it is NOT imported and NOT read.  Everything this screen needs (MAE, skill, R2, block sign-flip,
partition assertion, cyclic-shift null) is reimplemented here from first principles.  The
cyclic-shift construction is credited to E1_I0021_heterogeneity_diagnostic/hd_base.py
(`cyclic_shift_within_groups`, D093); it is reimplemented here rather than imported so this screen
has no cross-directory code dependency, but the idea is theirs.

QUESTION.  Every screen in this programme has held the SKILL REFERENCE fixed and hunted for
features.  Nobody has optimised the reference.  D090 showed the same forecast scores +46.4% or
+7.1% purely on reference choice; D093 showed a minutes floor flips which estimator form wins.
This screen builds the best STRICTLY-PRIOR-GAMES-ONLY estimator it can for points, minutes, FGA and
points-per-minute, tunes it honestly walk-forward, and asks whether the champion beats it.

PARTITION.  seasons 2022-2024 only (the exploration partition is 2021-2024; the 2021 fold is
degenerate with n_train_rows=0 and is absent from the frozen frame).  Enforced by `assert_partition`
below, which tests VALUES (season ints, date years), never file text.

INPUT.  D081's frozen `E0_I0015_points_skill_decomposition/decomp_frame.parquet`, READ ONLY.  It
carries y_{pts,minutes,fga}, the champion's stored pred_point columns, D076's ref_ columns and
D081's refA_/refB_ rate references.  NOTHING is refitted on the champion (D091 authorises fitting
simple estimators only).

TIME WINDOW.  Every estimator here consumes ONLY rows that are strictly earlier than the row being
scored:
  * same-season player history: rows of the SAME (season, player_id) at an EARLIER position in the
    date-sorted group.  Implemented by compacting the group and indexing history by
    h = (number of admissible prior games), never h+1.
  * previous-season player/league values: seasons are disjoint in calendar time in this frame
    (2022 ends 2022-09-18, 2023 starts 2023-05-21, 2023 ends 2023-10-18, 2024 starts 2024-05-16),
    verified in `assert_season_disjoint`, so a previous-season aggregate is strictly prior.
  * same-season league / role-bucket means: expanding over games on STRICTLY EARLIER DATES in the
    same season.
  * hyperparameters: selected on EARLIER seasons only (see s02).
"""
import hashlib
import json
import os

import numpy as np
import pandas as pd

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
D081 = os.path.join(ROOT, r"experiments\exploration\E0_I0015_points_skill_decomposition")
FRAME = os.path.join(D081, "decomp_frame.parquet")
OUT = os.path.join(ROOT, r"experiments\exploration\E1_I0022_optimal_simple_estimator")

SEED = 20260807
SCREEN_SEASONS = [2022, 2023, 2024]


def hdr(s):
    print("\n" + "=" * 100)
    print(s)
    print("=" * 100)


# ----------------------------------------------------------------------------- partition guard
def assert_partition(f, verbose=True):
    """VALUE-based partition check: every season-valued column in 2021..2024, every date < 2025."""
    viol = []
    checked_season, checked_date = [], []
    for c in f.columns:
        s = f[c]
        if pd.api.types.is_datetime64_any_dtype(s):
            checked_date.append(c)
            yrs = s.dropna().dt.year
            if len(yrs) and (yrs.max() > 2024 or yrs.min() < 2021):
                viol.append((c, "date year range", int(yrs.min()), int(yrs.max())))
        elif pd.api.types.is_integer_dtype(s) or pd.api.types.is_float_dtype(s):
            v = pd.to_numeric(s, errors="coerce").dropna()
            if len(v) == 0:
                continue
            uq = np.unique(v.to_numpy())
            # only treat as a season column if EVERY value looks like a season year
            if uq.min() >= 1990 and uq.max() <= 2100 and np.allclose(uq, np.round(uq)):
                checked_season.append(c)
                if uq.min() < 2021 or uq.max() > 2024:
                    viol.append((c, "season value range", float(uq.min()), float(uq.max())))
    ok = len(viol) == 0
    if verbose:
        print("  partition check: season-valued cols=%s  date cols=%s  violations=%s"
              % (checked_season, checked_date, viol))
    assert ok, "PARTITION VIOLATION: %s" % viol
    return {"ok": ok, "season_cols": checked_season, "date_cols": checked_date}


def assert_season_disjoint(f, verbose=True):
    g = f.groupby("season")["gdate"].agg(["min", "max"]).sort_index()
    prev_max = None
    for s, row in g.iterrows():
        if prev_max is not None:
            assert row["min"] > prev_max, "seasons overlap in calendar time -- prior-season " \
                                          "aggregates would NOT be strictly prior"
        prev_max = row["max"]
    if verbose:
        print("  season calendar ranges (disjoint, ascending):")
        for s, row in g.iterrows():
            print("    %d  %s .. %s" % (s, row["min"].date(), row["max"].date()))
    return {str(int(s)): [str(r["min"].date()), str(r["max"].date())] for s, r in g.iterrows()}


def load_frame(verbose=True):
    f = pd.read_parquet(FRAME)
    f = f.sort_values(["season", "player_id", "gdate"], kind="stable").reset_index(drop=True)
    if verbose:
        print("  loaded D081 decomp_frame.parquet  shape=%s  seasons=%s"
              % (f.shape, sorted(f["season"].unique())))
    assert_partition(f, verbose=verbose)
    assert set(int(x) for x in f["season"].unique()) <= set(SCREEN_SEASONS)
    assert f["gdate"].max() < pd.Timestamp("2025-01-01")
    assert (f["y_minutes"] > 0).all()
    return f


# ----------------------------------------------------------------------------- metrics
def mae(y, yhat):
    y = np.asarray(y, float)
    yhat = np.asarray(yhat, float)
    m = np.isfinite(y) & np.isfinite(yhat)
    return float(np.mean(np.abs(y[m] - yhat[m])))


def r2_forecast(y, yhat):
    """R2 OF A GIVEN FORECAST: 1 - SSE/SST, SSE about the SUPPLIED yhat (no refit), SST about the
    unweighted mean of y.  D069 denominator convention; D081's `r2_forecast`, NOT the kit's
    `r2_plain` which refits an intercept and slope and therefore reports a LARGER number."""
    y = np.asarray(y, float)
    yhat = np.asarray(yhat, float)
    m = np.isfinite(y) & np.isfinite(yhat)
    y, yhat = y[m], yhat[m]
    sse = float(((y - yhat) ** 2).sum())
    sst = float(((y - y.mean()) ** 2).sum())
    return 1.0 - sse / sst if sst > 0 else float("nan")


def skill(y, yhat_model, yhat_ref):
    """1 - MAE_model / MAE_ref, both on THE SAME rows (rows finite for BOTH forecasts)."""
    y = np.asarray(y, float)
    a = np.asarray(yhat_model, float)
    b = np.asarray(yhat_ref, float)
    m = np.isfinite(y) & np.isfinite(a) & np.isfinite(b)
    mm = float(np.mean(np.abs(y[m] - a[m])))
    mr = float(np.mean(np.abs(y[m] - b[m])))
    return float(1.0 - mm / mr), mm, mr, int(m.sum())


# ----------------------------------------------------------------------------- paired inference
def block_signflip_test(diff, block_codes, n_draws=4000, seed=SEED):
    """Paired permutation for mean(diff), diff_i = |e_A,i| - |e_B,i| on the SAME row i.

    Sign is flipped for a WHOLE (season, player) block at a time.  Row-level flipping would treat
    correlated rows as independent -- the anticonservative null this programme has been burned by.
    Reimplemented from D081's `psd_base.block_signflip_test` (not imported: no kit dependency)."""
    d = np.asarray(diff, float)
    ok = np.isfinite(d)
    d = np.where(ok, d, 0.0)
    uq, inv = np.unique(np.asarray(block_codes), return_inverse=True)
    nb = len(uq)
    bsum = np.bincount(inv, weights=d, minlength=nb)
    n_ok = int(ok.sum())
    real = float(bsum.sum() / n_ok)
    rng = np.random.default_rng(seed)
    signs = rng.choice(np.array([-1.0, 1.0]), size=(n_draws, nb))
    draws = (signs * bsum[None, :]).sum(axis=1) / n_ok
    p = (1.0 + int((np.abs(draws) >= abs(real)).sum())) / (n_draws + 1.0)
    return {"mean_diff": real, "p_two_sided_blockflip": float(p), "n_blocks": int(nb),
            "n_rows": n_ok, "null_sd": float(draws.std(ddof=1)), "n_draws": int(n_draws)}


def cyclic_shift_within_groups(x, starts, ns, rng):
    """Rotate each group's series by a random offset.  Rows MUST be sorted by group then DATE.

    CREDIT: E1_I0021_heterogeneity_diagnostic/hd_base.py (D093).  D093 measured that a plain
    within-player SHUFFLE is ANTICONSERVATIVE for autocorrelated prior-history series -- it returned
    p=0.0015 where the honest null returned p=0.39 -- because the shuffle destroys serial
    correlation that the real series has.  A cyclic shift preserves each group's marginal
    distribution AND its serial structure exactly and destroys only the alignment to the response."""
    out = np.empty_like(x)
    for a, n in zip(starts, ns):
        if n <= 1:
            out[a:a + n] = x[a:a + n]
            continue
        k = int(rng.integers(0, n))
        out[a:a + n] = np.roll(x[a:a + n], k)
    return out


def group_bounds(f, keys=("season", "player_id")):
    """Contiguous-block starts/lengths for a frame ALREADY sorted by keys then gdate."""
    codes = f.groupby(list(keys), sort=False).ngroup().to_numpy()
    change = np.flatnonzero(np.r_[True, codes[1:] != codes[:-1]])
    ns = np.diff(np.r_[change, len(codes)])
    return codes, change, ns


# ----------------------------------------------------------------------------- estimator engine
MEMORIES = ([("expanding", 0.0)]
            + [("sma", float(w)) for w in [1, 2, 3, 5, 8, 10, 15, 20, 30]]
            + [("ewma", float(h)) for h in [0.5, 1, 2, 3, 5, 8, 12, 20, 40]])
SHRINKS = ([("none", 0.0)]
           + [(t, float(k)) for t in ["league", "prior_season", "role"]
              for k in [0.5, 1, 2, 4, 8, 16, 32]])
FLOORS = [0.0, 5.0, 10.0, 15.0]
MODES = {"pts": ["equal", "minutes_weighted", "composite"],
         "minutes": ["equal", "minutes_weighted"],
         "fga": ["equal", "minutes_weighted"],
         "ppm": ["ratio_of_prior_sums", "mean_of_prior_ratios"]}
TARGETS = ["pts", "minutes", "fga", "ppm"]


def numden(f, target, mode):
    """Per-game (numerator, denominator) contribution of one PRIOR game under a given mode.

    The estimator is always sum(w_j * num_j) / sum(w_j * den_j) over admissible prior games j, with
    w_j the memory weight.  This makes RATIO-OF-PRIOR-SUMS vs MEAN-OF-PRIOR-RATIOS a *dimension*
    (den = the real denominator vs den = 1), exactly as D093 requires, rather than a choice."""
    mins = f["y_minutes"].to_numpy(float)
    if target == "ppm":
        if mode == "ratio_of_prior_sums":
            return f["y_pts"].to_numpy(float), mins
        return f["r_ppm"].to_numpy(float), np.ones(len(f))
    v = f["y_" + target].to_numpy(float)
    if mode == "minutes_weighted":
        return v * mins, mins
    return v, np.ones(len(f))


def prior_sums(num, den, mins, starts, ns, floor, memory):
    """S_num, S_den, S_w over STRICTLY PRIOR admissible games, for every row.

    Admissible = the prior game's realised minutes >= `floor` (D093: a realised-minutes floor on the
    HISTORY removes 39.3% of per-minute variance; the floor is never applied to the target row).
    `memory` is ("expanding",0) | ("sma",w) | ("ewma",half_life).

    CONSTRUCTION.  Inside each (season, player) block, the admissible games are compacted in date
    order.  Row at block position p sees exactly the first h = #admissible games strictly before p.
    Prefix arrays are indexed at h, never h+1 -- that is the whole prior-only guarantee."""
    kind, par = memory
    n = len(num)
    S_num = np.zeros(n)
    S_den = np.zeros(n)
    S_w = np.zeros(n)
    lam = 0.5 ** (1.0 / par) if kind == "ewma" else None
    for a, ln in zip(starts, ns):
        sl = slice(a, a + ln)
        ok = mins[sl] >= floor
        comp = np.flatnonzero(ok)
        m = len(comp)
        # h[p] = number of admissible games strictly before position p
        h = np.zeros(ln, dtype=np.int64)
        if m:
            h = np.searchsorted(comp, np.arange(ln), side="left")
        cn = num[sl][comp]
        cd = den[sl][comp]
        if kind == "expanding":
            pn = np.r_[0.0, np.cumsum(cn)]
            pd_ = np.r_[0.0, np.cumsum(cd)]
            pw = np.arange(m + 1, dtype=float)
            S_num[sl] = pn[h]
            S_den[sl] = pd_[h]
            S_w[sl] = pw[h]
        elif kind == "sma":
            w = int(par)
            pn = np.r_[0.0, np.cumsum(cn)]
            pd_ = np.r_[0.0, np.cumsum(cd)]
            lo = np.maximum(h - w, 0)
            S_num[sl] = pn[h] - pn[lo]
            S_den[sl] = pd_[h] - pd_[lo]
            S_w[sl] = (h - lo).astype(float)
        else:  # ewma, decayed toward the most recent admissible prior game
            en = np.zeros(m + 1)
            ed = np.zeros(m + 1)
            ew = np.zeros(m + 1)
            for j in range(1, m + 1):
                en[j] = lam * en[j - 1] + cn[j - 1]
                ed[j] = lam * ed[j - 1] + cd[j - 1]
                ew[j] = lam * ew[j - 1] + 1.0
            S_num[sl] = en[h]
            S_den[sl] = ed[h]
            S_w[sl] = ew[h]
    return S_num, S_den, S_w


# --------------------------------------------------------------- shrinkage targets (prior-only)
def _expanding_league_ratio(f, num, den):
    """sum(num)/sum(den) over games on STRICTLY EARLIER DATES in the same season.

    Date-blocked, not row-blocked: every row on date d sees all season rows with date < d and none
    with date == d.  (A plain shift(1) inside a date-sorted season would let a row see other games
    played the SAME day, which are not available pre-game.)"""
    s = f["season"].to_numpy()
    d = f["gdate"].to_numpy()
    out = np.full(len(f), np.nan)
    for ss in np.unique(s):
        m = np.flatnonzero(s == ss)
        order = m[np.argsort(d[m], kind="stable")]
        dd = d[order]
        cn = np.r_[0.0, np.cumsum(num[order])]
        cd = np.r_[0.0, np.cumsum(den[order])]
        # first index of each date == number of rows on strictly earlier dates
        first = np.searchsorted(dd, dd, side="left")
        with np.errstate(invalid="ignore", divide="ignore"):
            out[order] = np.where(cd[first] > 0, cn[first] / cd[first], np.nan)
    return out


def _prev_season_league(f, num, den):
    """Whole previous season's league value.  Seasons are calendar-disjoint => strictly prior."""
    s = f["season"].to_numpy()
    tot = {}
    for ss in np.unique(s):
        m = s == ss
        tot[int(ss)] = float(num[m].sum()) / float(den[m].sum())
    return np.array([tot.get(int(x) - 1, np.nan) for x in s])


def _prev_season_player(f, num, den):
    """The player's OWN whole previous-season value (same aggregation as the mode)."""
    key = pd.DataFrame({"season": f["season"].to_numpy(), "pid": f["player_id"].to_numpy(),
                        "n": num, "d": den})
    g = key.groupby(["season", "pid"], sort=False)[["n", "d"]].sum()
    val = (g["n"] / g["d"].replace(0.0, np.nan))
    lut = {(int(a) + 1, int(b)): float(v) for (a, b), v in val.items()}
    return np.array([lut.get((int(a), int(b)), np.nan)
                     for a, b in zip(f["season"].to_numpy(), f["player_id"].to_numpy())])


def role_bucket(f):
    """Prior-only role bucket: tercile of the player's PREVIOUS-SEASON minutes per game.

    Cutpoints are computed from the previous season's own distribution (never from the current
    season), so the bucket for a 2024 row uses only 2023 information.  Players with no previous
    season in the frame get bucket -1 ("unknown"), which is itself a role signal (rookie/returner)."""
    s = f["season"].to_numpy()
    pid = f["player_id"].to_numpy()
    mpg = (pd.DataFrame({"season": s, "pid": pid, "m": f["y_minutes"].to_numpy(float)})
           .groupby(["season", "pid"])["m"].mean())
    buckets = {}
    for ss in np.unique(s):
        prev = int(ss) - 1
        if (prev,) not in {(k[0],) for k in mpg.index}:
            continue
        sub = mpg.loc[prev]
        q1, q2 = np.quantile(sub.to_numpy(float), [1 / 3, 2 / 3])
        for p, v in sub.items():
            buckets[(int(ss), int(p))] = 0 if v <= q1 else (1 if v <= q2 else 2)
    return np.array([buckets.get((int(a), int(b)), -1) for a, b in zip(s, pid)], dtype=np.int64)


def _expanding_bucket_ratio(f, num, den, bucket):
    """Same as _expanding_league_ratio but within (season, role bucket)."""
    s = f["season"].to_numpy()
    d = f["gdate"].to_numpy()
    out = np.full(len(f), np.nan)
    for ss in np.unique(s):
        for bb in np.unique(bucket):
            m = np.flatnonzero((s == ss) & (bucket == bb))
            if len(m) == 0:
                continue
            order = m[np.argsort(d[m], kind="stable")]
            dd = d[order]
            cn = np.r_[0.0, np.cumsum(num[order])]
            cd = np.r_[0.0, np.cumsum(den[order])]
            first = np.searchsorted(dd, dd, side="left")
            with np.errstate(invalid="ignore", divide="ignore"):
                out[order] = np.where(cd[first] > 0, cn[first] / cd[first], np.nan)
    return out


def build_shrink_targets(f, num, den, bucket, grand_fallback):
    """The three shrinkage targets for one (target, mode), each with a documented prior-only chain.

    league       : same-season expanding league value -> previous season's league value -> GRAND.
    prior_season : the player's own previous-season value -> league chain.
    role         : same-season expanding value within the player's prior-season role tercile ->
                   league chain.
    GRAND is the whole-frame value and is the ONLY non-prior-only ingredient anywhere in this
    screen.  It fires exclusively on rows whose season has no strictly-earlier game AND whose season
    has no predecessor in the frame -- i.e. opening-date rows of 2022 only.  Every walk-forward
    EVALUATION row (2023, 2024) has a previous season, so GRAND never touches the headline.
    Counted and reported in FINDINGS.json as `grand_fallback_rows`."""
    lg = _expanding_league_ratio(f, num, den)
    prev_lg = _prev_season_league(f, num, den)
    league = np.where(np.isfinite(lg), lg, prev_lg)
    n_grand = int((~np.isfinite(league)).sum())
    league = np.where(np.isfinite(league), league, grand_fallback)

    ps = _prev_season_player(f, num, den)
    prior_season = np.where(np.isfinite(ps), ps, league)

    rl = _expanding_bucket_ratio(f, num, den, bucket)
    role = np.where(np.isfinite(rl), rl, league)
    return {"league": league, "prior_season": prior_season, "role": role}, n_grand


def apply_shrink(S_num, S_den, S_w, targets, shrink):
    """est = (n_eff * raw + k * T) / (n_eff + k).  n_eff is the DECAYED COUNT of admissible prior
    games (S_w), so k is a pseudo-count of prior games and k=0 is exactly the unshrunk estimator.
    With no admissible history (S_w == 0 or S_den == 0) the estimator returns T."""
    kind, k = shrink
    with np.errstate(invalid="ignore", divide="ignore"):
        raw = np.where(S_den > 0, S_num / np.where(S_den > 0, S_den, np.nan), np.nan)
    if kind == "none":
        # no shrinkage target: fall back to the league value only where there is no history at all
        T = targets["league"]
        return np.where(np.isfinite(raw), raw, T)
    T = targets[kind]
    ne = np.where(np.isfinite(raw), S_w, 0.0)
    r = np.where(np.isfinite(raw), raw, 0.0)
    return (ne * r + k * T) / (ne + k)


# ----------------------------------------------------------------------------- prereg hash
def sha256_text(t):
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


def grid_rows():
    rows = []
    for t in TARGETS:
        for mode in MODES[t]:
            for mem in MEMORIES:
                for sh in SHRINKS:
                    for fl in FLOORS:
                        rows.append((t, mode, mem[0], mem[1], sh[0], sh[1], fl))
    return rows


def grid_hash():
    rows = grid_rows()
    txt = "\n".join("|".join(str(x) for x in r) for r in sorted(rows))
    return sha256_text(txt), len(rows)
