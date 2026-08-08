"""E1_I0027 -- THE CANONICAL REFERENCE LADDER.  Importable implementation.

WHY THIS FILE EXISTS
    Every skill figure in this programme is a statement about a PAIR -- a forecast and a reference --
    and the programme has been reporting them as statements about the forecast.  D090 (+46.4% vs
    +7.1%), D093 (+0.22% vs +4.24%), D094 (+3.71% vs -4.41%, an 8.12-point swing) and D099 (a ~4x
    inflation from a subset SST) are four recorded instances.  D069 ruled that past numbers cannot
    be rescaled by a multiplier and must be RE-RUN.  A re-run needs ONE fixed reference to re-run
    AGAINST.  This module is that reference, expressed as a single function of (target, frame).

THE CONTRACT
    ladder(frame, target)  ->  DataFrame with one column per rung, aligned to `frame`'s index.
    Every rung is STRICTLY PRIOR-GAMES-ONLY.  Nothing in this module reads the row being scored,
    any row on the same date, or any row in the future.  The one exception is named, counted and
    reported: `GRAND` (see `_league_rung`), which fires only on rows that have neither an earlier
    game in their own season nor a previous season present in the frame -- i.e. opening rows of the
    frame's first season, which are never in any evaluation set used here.

THE RUNGS, WEAKEST TO STRONGEST
    R0_LEAGUE          a league / base-rate constant: the same-season expanding league value over
                       STRICTLY EARLIER DATES, chained to the previous season's league value.
    R1_PLAYER_EXPAND   the player's own expanding prior mean.  THIS IS THE PROGRAMME'S INCUMBENT
                       "naive" reference -- the one D094 showed is beatable by 1.3-7.8%.  It is on
                       the ladder so that every legacy figure has a named rung to sit on.
    R2_EWMA_TUNED      a tuned EWMA of the player's own prior games, with form / half-life /
                       shrinkage taken from D094's 15,048-cell grid (see CANON below).  NOT
                       re-searched here.
    R3_RATE_X_MINUTES  a composite: EWMA(target per minute) x EWMA(minutes).  DEGENERATE for
                       target="minutes" and flagged as such rather than silently duplicated.
    R4_RICH_LOOKUP     a walk-forward OLS blend of the player's own prior measurements of the target
                       AND of its components (minutes, per-minute rate, previous season, history
                       depth) plus the league rung.  Coefficients are fitted on seasons STRICTLY
                       EARLIER than the season being scored, so the inference machinery is
                       prior-only too (the retrospective-baseline trap has six recorded instances,
                       one of which entered through exactly this door).

WHAT IS REUSED RATHER THAN RE-DERIVED (D094 / E1_I0022, `estimator_surface.csv`, 15,048 cells)
    * EWMA beats SMA beats expanding on all four measured targets.
    * Half-lives differ ~20x across targets: minutes 2, fga 5, pts 8, ppm 40.
    * Shrinkage is weak and NEVER toward the league -- always toward the player's own prior season.
    * A realised-minutes floor on the history hurts monotonically, so the floor is fixed at 0.
    The exact selected cells were decoded from `surface_keys.parquet` + `selected_cells.npz`
    (global row indices) and are transcribed verbatim into CANON.

CREDIT
    The prior-sum engine (compaction + prefix arrays indexed at h, never h+1), the shrinkage-target
    chain and the role bucket are adapted from E1_I0022_optimal_simple_estimator/ose_base.py (D094),
    which in turn credits E1_I0021/hd_base.py (D093) for the cyclic-shift null and E0_I0015/psd_base
    (D081) for the block sign-flip.  Those files are frozen and are READ, never written.
"""
import hashlib
import json

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------- target vocabulary
#: Canonical target names -> the frame columns that may carry them, in preference order.
TARGET_COLUMNS = {
    "pts":     ["y_pts", "pts", "points"],
    "minutes": ["y_minutes", "minutes", "min"],
    "fga":     ["y_fga", "fga", "attempts"],
    "ppm":     ["y_ppm"],          # derived from pts/minutes when absent
    "reb":     ["y_reb", "reb", "rebounds"],
    "ast":     ["y_ast", "ast", "assists"],
}
TARGETS = ["pts", "minutes", "fga", "ppm", "reb", "ast"]
ALIASES = {"points": "pts", "attempts": "fga", "shot_attempts": "fga",
           "points_per_minute": "ppm", "rebounds": "reb", "assists": "ast"}

#: D094's selected cells, transcribed from E1_I0022 surface_keys.parquet at the global indices in
#: selected_cells.npz (tune-B column: hyperparameters chosen on 2022-2023, evaluated on 2023-2024).
#: `mode` follows D094's vocabulary:
#:   equal                = num target, den 1
#:   minutes_weighted     = num target*minutes, den minutes
#:   composite            = EWMA(minutes, same cell) * EWMA(ppm ratio-of-prior-sums, same cell)
#:   ratio_of_prior_sums  = num pts, den minutes          (rate targets)
#:   mean_of_prior_ratios = num pts/minutes, den 1        (rate targets)
CANON = {
    "pts":     dict(mode="composite",            half_life=8.0,  shrink="prior_season", k=0.5,
                    floor=0.0, source="D094 idx 3044"),
    "minutes": dict(mode="equal",                half_life=2.0,  shrink="none",         k=0.0,
                    floor=0.0, source="D094 idx 2379"),
    "fga":     dict(mode="equal",                half_life=5.0,  shrink="prior_season", k=0.5,
                    floor=0.0, source="D094 idx 2849"),
    "ppm":     dict(mode="mean_of_prior_ratios", half_life=40.0, shrink="prior_season", k=2.0,
                    floor=0.0, source="D094 idx 3662"),
    # D094 never measured rebounds or assists.  Their half-lives are selected inside this screen on
    # TRAIN SEASONS ONLY (see `select_half_life`) and written back into CANON by the prereg script,
    # which freezes and hashes the result BEFORE any re-priced figure is computed.  The mode and the
    # shrinkage rule are NOT re-searched: D094's finding (weak, toward the player's own prior
    # season, never toward the league) is adopted wholesale.
    "reb":     dict(mode="equal", half_life=None, shrink="prior_season", k=0.5, floor=0.0,
                    source="SELECTED-IN-SCREEN on train seasons only"),
    "ast":     dict(mode="equal", half_life=None, shrink="prior_season", k=0.5, floor=0.0,
                    source="SELECTED-IN-SCREEN on train seasons only"),
}

#: The half-life grid offered to `select_half_life`.  Identical to D094's EWMA grid; no new values.
HALF_LIFE_GRID = [0.5, 1.0, 2.0, 3.0, 5.0, 8.0, 12.0, 20.0, 40.0]

RUNGS = ["R0_LEAGUE", "R1_PLAYER_EXPAND", "R2_EWMA_TUNED", "R3_RATE_X_MINUTES", "R4_RICH_LOOKUP"]

#: The rung this screen re-prices everything against.  Fixed in the preregistration.
CANONICAL_RUNG = "R4_RICH_LOOKUP"


# --------------------------------------------------------------------------- partition guard
class PartitionViolation(AssertionError):
    pass


def assert_partition(f, allowed=(2021, 2024), verbose=False):
    """VALUE-based partition check.  Tests values, never file text or file names.

    Deliberately narrower than the kit's K0/K4 gate: it checks only columns whose NAME marks them as
    the row's observation season or its date, because D092 recorded (K4, HIGH) that a value-shaped
    gate raises on clean data whenever a year-valued PLAYER ATTRIBUTE such as `draft_year` is
    present.  Naming the checked columns explicitly is the fix D092 specified; hiding a real leak by
    passing `season_cols=['season']` to a broader gate is the workaround it warned against.
    """
    lo, hi = allowed
    viol, checked = [], []
    for c in f.columns:
        s = f[c]
        name = c.lower()
        if pd.api.types.is_datetime64_any_dtype(s):
            checked.append(c)
            yr = s.dropna().dt.year
            if len(yr) and (yr.max() > hi or yr.min() < lo):
                viol.append((c, "date year", int(yr.min()), int(yr.max())))
        elif name == "season" or name.endswith("_season") and "draft" not in name:
            v = pd.to_numeric(s, errors="coerce").dropna()
            if len(v):
                checked.append(c)
                if v.min() < lo or v.max() > hi:
                    viol.append((c, "season value", float(v.min()), float(v.max())))
    if viol:
        raise PartitionViolation("PARTITION VIOLATION: %s" % viol)
    if verbose:
        print("  partition ok; columns checked on VALUES: %s" % checked)
    return {"ok": True, "checked_columns": checked, "allowed": [lo, hi]}


def assert_season_disjoint(f, date_col, verbose=False):
    """Previous-season aggregates are strictly prior ONLY IF seasons are disjoint in calendar time."""
    g = f.groupby("season")[date_col].agg(["min", "max"]).sort_index()
    prev = None
    for s, r in g.iterrows():
        if prev is not None and not (r["min"] > prev):
            raise AssertionError("seasons overlap in calendar time; previous-season aggregates "
                                 "would NOT be strictly prior")
        prev = r["max"]
    if verbose:
        for s, r in g.iterrows():
            print("    season %s  %s .. %s" % (s, r["min"].date(), r["max"].date()))
    return {str(int(s)): [str(r["min"].date()), str(r["max"].date())] for s, r in g.iterrows()}


# --------------------------------------------------------------------------- frame normalisation
def resolve_target(target):
    t = ALIASES.get(str(target).lower(), str(target).lower())
    if t not in TARGETS:
        raise KeyError("unknown target %r; known: %s" % (target, TARGETS))
    return t


def normalise(frame, date_col=None, verbose=False):
    """Return a copy sorted by (season, player_id, date) with canonical helper columns.

    REQUIRED of `frame`: season, player_id, a datetime column, minutes.
    The returned frame carries `_date`, `_minutes` and whichever of y_pts / y_fga / y_reb / y_ast
    it could resolve.  Sorting is STABLE and is what every prior-only construction below relies on.
    """
    f = frame.copy()
    if date_col is None:
        cands = [c for c in ("gdate", "game_date", "date") if c in f.columns]
        if not cands:
            cands = [c for c in f.columns if pd.api.types.is_datetime64_any_dtype(f[c])]
        if not cands:
            raise KeyError("no date column found; pass date_col=")
        date_col = cands[0]
    f["_date"] = pd.to_datetime(f[date_col])
    mcol = next((c for c in TARGET_COLUMNS["minutes"] if c in f.columns), None)
    if mcol is None:
        raise KeyError("no minutes column found")
    f["_minutes"] = pd.to_numeric(f[mcol], errors="coerce").astype(float)
    f["_y_minutes"] = f["_minutes"]
    for t in ("pts", "fga", "reb", "ast"):
        c = next((c for c in TARGET_COLUMNS[t] if c in f.columns), None)
        if c is not None:
            f["_y_" + t] = pd.to_numeric(f[c], errors="coerce").astype(float)
    if "_y_pts" in f.columns:
        with np.errstate(invalid="ignore", divide="ignore"):
            f["_y_ppm"] = np.where(f["_minutes"] > 0, f["_y_pts"] / f["_minutes"], np.nan)
    f = f.sort_values(["season", "player_id", "_date"], kind="stable").reset_index(drop=True)
    if verbose:
        print("  normalised: n=%d seasons=%s date=%s..%s"
              % (len(f), sorted(f["season"].unique()), f["_date"].min().date(),
                 f["_date"].max().date()))
    return f, date_col


def target_series(f, target):
    """The realised response for `target` on a normalised frame."""
    t = resolve_target(target)
    col = "_y_" + t
    if col not in f.columns:
        raise KeyError("frame does not carry target %r (looked for %s)" % (t, TARGET_COLUMNS[t]))
    return f[col].to_numpy(float)


# --------------------------------------------------------------------------- prior-sum engine
def _group_bounds(f):
    codes = f.groupby(["season", "player_id"], sort=False).ngroup().to_numpy()
    starts = np.flatnonzero(np.r_[True, codes[1:] != codes[:-1]])
    ns = np.diff(np.r_[starts, len(codes)])
    return codes, starts, ns


def _numden(f, target, mode):
    """(numerator, denominator) contribution of ONE PRIOR GAME under a given aggregation mode.

    The estimator is always sum(w_j*num_j)/sum(w_j*den_j) over admissible prior games j.  This makes
    ratio-of-prior-sums vs mean-of-prior-ratios a DIMENSION (den = the real denominator vs den = 1)
    rather than a hidden choice -- D093's requirement, adopted from D094's `numden`.
    """
    t = resolve_target(target)
    mins = f["_minutes"].to_numpy(float)
    if mode == "ratio_of_prior_sums":
        base = "pts" if t == "ppm" else t
        return f["_y_" + base].to_numpy(float), mins
    if mode == "mean_of_prior_ratios":
        if t == "ppm":
            v = f["_y_ppm"].to_numpy(float)
        else:
            with np.errstate(invalid="ignore", divide="ignore"):
                v = np.where(mins > 0, f["_y_" + t].to_numpy(float) / mins, np.nan)
        return v, np.ones(len(f))
    v = f["_y_" + t].to_numpy(float)
    if mode == "minutes_weighted":
        return v * mins, mins
    return v, np.ones(len(f))          # "equal" (and "composite", handled by the caller)


def _prior_sums(num, den, mins, starts, ns, floor, kind, par):
    """S_num, S_den, S_w over STRICTLY PRIOR admissible games, for every row.

    Inside each (season, player) block the admissible games (realised minutes >= floor) are
    compacted in date order; the row at block position p sees exactly the first
    h = #admissible games strictly before p.  Prefix arrays are indexed at h, NEVER h+1 -- that
    single fact is the whole prior-only guarantee.  Adapted from D094's `prior_sums`.
    """
    n = len(num)
    S_num = np.zeros(n)
    S_den = np.zeros(n)
    S_w = np.zeros(n)
    lam = 0.5 ** (1.0 / par) if kind == "ewma" else None
    for a, ln in zip(starts, ns):
        sl = slice(a, a + ln)
        comp = np.flatnonzero(mins[sl] >= floor)
        m = len(comp)
        h = np.searchsorted(comp, np.arange(ln), side="left") if m else np.zeros(ln, np.int64)
        cn = np.nan_to_num(num[sl][comp], nan=0.0)
        cd = np.nan_to_num(den[sl][comp], nan=0.0)
        if kind == "expanding":
            pn = np.r_[0.0, np.cumsum(cn)]
            pdn = np.r_[0.0, np.cumsum(cd)]
            S_num[sl], S_den[sl], S_w[sl] = pn[h], pdn[h], np.arange(m + 1, dtype=float)[h]
        elif kind == "sma":
            w = int(par)
            pn = np.r_[0.0, np.cumsum(cn)]
            pdn = np.r_[0.0, np.cumsum(cd)]
            lo = np.maximum(h - w, 0)
            S_num[sl], S_den[sl] = pn[h] - pn[lo], pdn[h] - pdn[lo]
            S_w[sl] = (h - lo).astype(float)
        else:
            en = np.zeros(m + 1)
            ed = np.zeros(m + 1)
            ew = np.zeros(m + 1)
            for j in range(1, m + 1):
                en[j] = lam * en[j - 1] + cn[j - 1]
                ed[j] = lam * ed[j - 1] + cd[j - 1]
                ew[j] = lam * ew[j - 1] + 1.0
            S_num[sl], S_den[sl], S_w[sl] = en[h], ed[h], ew[h]
    return S_num, S_den, S_w


# ------------------------------------------------------- prior-only shrinkage / fallback targets
def _expanding_league(f, num, den):
    """sum(num)/sum(den) over games on STRICTLY EARLIER DATES in the same season.

    DATE-blocked, not row-blocked.  A plain shift(1) inside a date-sorted season would let a row see
    other games played the SAME DAY, which are not available pre-game.  Adapted from D094.
    """
    s = f["season"].to_numpy()
    d = f["_date"].to_numpy()
    out = np.full(len(f), np.nan)
    for ss in np.unique(s):
        m = np.flatnonzero(s == ss)
        order = m[np.argsort(d[m], kind="stable")]
        dd = d[order]
        cn = np.r_[0.0, np.nancumsum(num[order])]
        cd = np.r_[0.0, np.nancumsum(den[order])]
        first = np.searchsorted(dd, dd, side="left")   # #rows on strictly earlier dates
        with np.errstate(invalid="ignore", divide="ignore"):
            out[order] = np.where(cd[first] > 0, cn[first] / cd[first], np.nan)
    return out


def _prev_season_league(f, num, den):
    s = f["season"].to_numpy()
    tot = {}
    for ss in np.unique(s):
        m = s == ss
        dd = np.nansum(den[m])
        tot[int(ss)] = float(np.nansum(num[m]) / dd) if dd > 0 else np.nan
    return np.array([tot.get(int(x) - 1, np.nan) for x in s])


def _prev_season_player(f, num, den):
    k = pd.DataFrame({"season": f["season"].to_numpy(), "pid": f["player_id"].to_numpy(),
                      "n": num, "d": den})
    g = k.groupby(["season", "pid"], sort=False)[["n", "d"]].sum()
    val = g["n"] / g["d"].replace(0.0, np.nan)
    lut = {(int(a) + 1, int(b)): float(v) for (a, b), v in val.items()}
    return np.array([lut.get((int(a), int(b)), np.nan)
                     for a, b in zip(f["season"].to_numpy(), f["player_id"].to_numpy())])


def _league_rung(f, num, den):
    """R0: expanding same-season league -> previous season's league -> GRAND.

    GRAND is the whole-frame value and is the ONLY non-prior-only ingredient in this module.  It can
    fire only on a row that has (a) no strictly-earlier game in its own season AND (b) no previous
    season present in the frame -- opening-date rows of the frame's FIRST season.  Those rows are
    never in an evaluation set here (every evaluation season has a predecessor).  The count is
    returned so it can be reported rather than assumed to be zero.
    """
    lg = _expanding_league(f, num, den)
    prev = _prev_season_league(f, num, den)
    out = np.where(np.isfinite(lg), lg, prev)
    n_grand = int((~np.isfinite(out)).sum())
    dd = np.nansum(den)
    grand = float(np.nansum(num) / dd) if dd > 0 else np.nan
    return np.where(np.isfinite(out), out, grand), n_grand, grand


def _shrink(S_num, S_den, S_w, league, prior_season, kind, k):
    """est = (n_eff*raw + k*T)/(n_eff + k), n_eff = the DECAYED count of admissible prior games.

    k is therefore a pseudo-count of prior games and k=0 is exactly the unshrunk estimator.  With no
    admissible history the estimator returns T.  Adapted from D094's `apply_shrink`.
    """
    with np.errstate(invalid="ignore", divide="ignore"):
        raw = np.where(S_den > 0, S_num / np.where(S_den > 0, S_den, np.nan), np.nan)
    if kind == "none":
        return np.where(np.isfinite(raw), raw, league)
    T = prior_season if kind == "prior_season" else league
    T = np.where(np.isfinite(T), T, league)
    ne = np.where(np.isfinite(raw), S_w, 0.0)
    r = np.where(np.isfinite(raw), raw, 0.0)
    with np.errstate(invalid="ignore", divide="ignore"):
        return (ne * r + k * T) / (ne + k)


def _estimate(f, target, mode, kind, par, shrink, k, floor, minutes_half_life=None):
    """One fully specified estimator cell -> a row-level forecast.  Prior-games-only throughout.

    `minutes_half_life` controls the MINUTES arm of a composite.  Left None it equals `par`, which
    is D094's construction and is what R2 must use to reproduce D094's selected cell for `pts`.
    R3 passes the minutes-optimal half-life (2) explicitly, which is what makes R3 a genuinely
    different rung from R2 rather than a copy of it.
    """
    t = resolve_target(target)
    if mode == "composite":
        if t == "ppm":
            # A RATE target has no "x minutes" arm.  Its component composite is the ratio of the
            # prior COMPONENT SUMS -- prior points over prior minutes -- as against the mean of the
            # per-game ratios.  D093 established that this is a DIMENSION, not a stylistic choice:
            # which of the two wins flips under a history minutes floor.
            return _estimate(f, "ppm", "ratio_of_prior_sums", kind, par, shrink, k, floor)
        mhl = par if minutes_half_life is None else float(minutes_half_life)
        mshrink, mk = ("none", 0.0) if minutes_half_life is not None else (shrink, k)
        a = _estimate(f, "minutes", "equal", kind, mhl, mshrink, mk, floor)
        if t == "pts" and minutes_half_life is None:
            # D094's exact composite: EWMA(minutes) x EWMA(ppm, ratio-of-prior-sums), same cell.
            b = _estimate(f, "ppm", "ratio_of_prior_sums", kind, par, shrink, k, floor)
            return a * b
        # rate x minutes: EWMA(target per minute) x EWMA(minutes)
        r = _estimate(f, t, "mean_of_prior_ratios", kind, par, shrink, k, floor)
        return a * r
    num, den = _numden(f, t, mode)
    mins = f["_minutes"].to_numpy(float)
    _, starts, ns = _group_bounds(f)
    S = _prior_sums(num, den, mins, starts, ns, floor, kind, par)
    league, _, _ = _league_rung(f, num, den)
    ps = _prev_season_player(f, num, den)
    return _shrink(*S, league, ps, shrink, k)


def n_prior_games(f):
    """Count of the player's STRICTLY EARLIER games in the same season, for every row."""
    _, starts, ns = _group_bounds(f)
    out = np.zeros(len(f))
    for a, ln in zip(starts, ns):
        out[a:a + ln] = np.arange(ln, dtype=float)
    return out


# --------------------------------------------------------------------------- half-life selection
def select_half_life(f, target, train_seasons, grid=None, mode="equal",
                     shrink="prior_season", k=0.5, floor=0.0, verbose=False):
    """Pick the EWMA half-life that minimises MAE on TRAIN SEASONS ONLY.

    Used only for rebounds and assists, which D094 never measured.  The selection set is disjoint
    from every evaluation set used in this screen, and the chosen value is frozen and hashed in the
    preregistration before any re-priced figure is computed.
    """
    grid = grid or HALF_LIFE_GRID
    y = target_series(f, target)
    tr = f["season"].isin(list(train_seasons)).to_numpy()
    rows = []
    for hl in grid:
        e = _estimate(f, target, mode, "ewma", float(hl), shrink, k, floor)
        m = tr & np.isfinite(y) & np.isfinite(e)
        rows.append((float(hl), float(np.mean(np.abs(y[m] - e[m]))), int(m.sum())))
    rows.sort(key=lambda r: (r[1], r[0]))
    if verbose:
        for hl, mae, n in sorted(rows):
            print("    half_life %-5s  train MAE %.6f  n=%d" % (hl, mae, n))
    return rows[0][0], rows


# --------------------------------------------------------------------------- the ladder itself
def ladder(frame, target, date_col=None, canon=None, scored_seasons=None, rich_features=True,
           verbose=False):
    """THE DELIVERABLE.  Every rung of the canonical reference ladder for one target on one frame.

    Returns (rungs_df, meta).  `rungs_df` is indexed exactly like the NORMALISED frame, which is
    also returned in `meta["frame"]` -- always align on that, never on the caller's original index.
    """
    t = resolve_target(target)
    cfg = dict((canon or CANON)[t])
    f, date_col = normalise(frame, date_col=date_col, verbose=verbose)
    assert_partition(f)
    assert_season_disjoint(f, "_date")
    y = target_series(f, t)
    mins = f["_minutes"].to_numpy(float)

    num_eq, den_eq = _numden(f, t, "equal")
    league, n_grand, grand = _league_rung(f, num_eq, den_eq)

    out = pd.DataFrame(index=f.index)
    out["R0_LEAGUE"] = league
    out["R1_PLAYER_EXPAND"] = _estimate(f, t, "equal", "expanding", 0.0, "none", 0.0, 0.0)

    hl = cfg["half_life"]
    if hl is None:
        raise ValueError("half_life for target %r is not frozen; run select_half_life and write it "
                         "into the preregistered CANON first" % t)
    out["R2_EWMA_TUNED"] = _estimate(f, t, cfg["mode"], "ewma", float(hl),
                                     cfg["shrink"], float(cfg["k"]), float(cfg["floor"]))

    degenerate_r3 = (t == "minutes")
    if degenerate_r3:
        # A rate x minutes composite for the MINUTES target is minutes/minutes x minutes.  It is
        # reported as NaN rather than silently duplicating R2, so no reader can mistake a copy for
        # an independent rung.
        out["R3_RATE_X_MINUTES"] = np.nan
    else:
        out["R3_RATE_X_MINUTES"] = _estimate(f, t, "composite", "ewma", float(hl),
                                             cfg["shrink"], float(cfg["k"]), float(cfg["floor"]),
                                             minutes_half_life=CANON["minutes"]["half_life"])

    # ---- R4: the rich lookup.  The player's own prior measurements of the target AND components.
    ew_min = _estimate(f, "minutes", "equal", "ewma", CANON["minutes"]["half_life"], "none", 0.0, 0.0)
    ew_rate = _estimate(f, t, "mean_of_prior_ratios", "ewma", float(hl), "prior_season", 0.5, 0.0)
    prev_pl = _prev_season_player(f, num_eq, den_eq)
    npg = n_prior_games(f)
    feats = pd.DataFrame({
        "f_R0_league": out["R0_LEAGUE"].to_numpy(),
        "f_R1_expand": out["R1_PLAYER_EXPAND"].to_numpy(),
        "f_R2_ewma": out["R2_EWMA_TUNED"].to_numpy(),
        "f_prior_minutes_ewma": ew_min,
        "f_prior_rate_ewma": ew_rate,
        "f_prior_season_player": np.where(np.isfinite(prev_pl), prev_pl, out["R0_LEAGUE"]),
        "f_log1p_n_prior": np.log1p(npg),
    })
    if not degenerate_r3:
        feats["f_R3_composite"] = out["R3_RATE_X_MINUTES"].to_numpy()
    if not rich_features:
        feats = feats[["f_R1_expand", "f_R2_ewma"]]
    out["R4_RICH_LOOKUP"], r4_meta = _walk_forward_blend(f, y, feats, scored_seasons)

    meta = {
        "target": t, "n_rows": int(len(f)), "date_col": date_col,
        "canon": cfg, "rungs": list(out.columns),
        "r3_degenerate_for_this_target": bool(degenerate_r3),
        "r3_max_abs_diff_from_r2": (float("nan") if degenerate_r3 else float(np.nanmax(np.abs(
            out["R3_RATE_X_MINUTES"].to_numpy(float) - out["R2_EWMA_TUNED"].to_numpy(float))))),
        "grand_fallback_rows": n_grand, "grand_value": grand,
        "r4_features": list(feats.columns), "r4": r4_meta,
        "seasons": sorted(int(s) for s in f["season"].unique()),
        "frame": f,
    }
    return out, meta


def _walk_forward_blend(f, y, feats, scored_seasons=None):
    """OLS blend fitted on seasons STRICTLY EARLIER than the season being scored.

    THE INFERENCE MACHINERY IS PRIOR-ONLY TOO.  Constraint 2 of this screen's brief requires the
    time-window audit to cover inference, and D072 recorded the fourth instance of a lead whose
    BASELINE read the future.  A blend fitted on the whole partition would be exactly that.
    Rows in the frame's earliest season have no training seasons and are returned NaN.
    """
    s = f["season"].to_numpy()
    X = feats.to_numpy(float)
    X = np.column_stack([np.ones(len(X)), X])
    seasons = sorted(int(v) for v in np.unique(s))
    scored = sorted(scored_seasons) if scored_seasons else seasons[1:]
    out = np.full(len(f), np.nan)
    per = []
    for ss in scored:
        tr = (s < ss) & np.isfinite(y) & np.isfinite(X).all(axis=1)
        te = (s == ss) & np.isfinite(X).all(axis=1)
        if tr.sum() < X.shape[1] + 10 or te.sum() == 0:
            per.append({"season": ss, "n_train": int(tr.sum()), "n_scored": 0,
                        "skipped": "insufficient training rows"})
            continue
        beta, *_ = np.linalg.lstsq(X[tr], y[tr], rcond=None)
        out[te] = X[te] @ beta
        per.append({"season": ss, "n_train": int(tr.sum()), "n_scored": int(te.sum()),
                    "beta": [float(b) for b in beta]})
    return out, {"scored_seasons": scored, "train_rule": "seasons strictly < scored season",
                 "per_season": per}


# --------------------------------------------------------------------------- scoring conventions
def r2_of_forecast(y, yhat, sst=None):
    """1 - SSE/SST.  SSE about the SUPPLIED forecast (NOTHING IS FITTED), SST about the unweighted
    mean of y on the SAME rows -- unless `sst` is supplied, which is how a COMMON DENOMINATOR is
    imposed (D099).  D069's convention.  Never use the kit's `r2_plain`, which refits."""
    y = np.asarray(y, float)
    yhat = np.asarray(yhat, float)
    m = np.isfinite(y) & np.isfinite(yhat)
    y, yhat = y[m], yhat[m]
    sse = float(((y - yhat) ** 2).sum())
    s = float(((y - y.mean()) ** 2).sum()) if sst is None else float(sst)
    return 1.0 - sse / s if s > 0 else float("nan")


def skill(y, yhat_model, yhat_ref):
    """1 - MAE_model/MAE_ref, both on the rows finite for BOTH forecasts."""
    y = np.asarray(y, float)
    a = np.asarray(yhat_model, float)
    b = np.asarray(yhat_ref, float)
    m = np.isfinite(y) & np.isfinite(a) & np.isfinite(b)
    mm = float(np.mean(np.abs(y[m] - a[m])))
    mr = float(np.mean(np.abs(y[m] - b[m])))
    return float(1.0 - mm / mr), mm, mr, int(m.sum())


def paired_dr2(y, resid_base, x, sst):
    """dR2 of adding ONE column x to a base model, by Frisch-Waugh, on a FIXED denominator.

    `resid_base` is y minus the base fit; `x` must already be residualised against the base's
    regressors by the caller if the base is multivariate.  `sst` is supplied explicitly and is the
    ONLY denominator -- there is no code path here that can compute a subset's own SST by accident.
    That is the D099 defect made structurally impossible rather than merely discouraged.
    """
    e = np.asarray(resid_base, float)
    xt = np.asarray(x, float)
    den = float(xt @ xt)
    if not np.isfinite(den) or den <= 1e-12:
        return 0.0
    num = float(e @ xt)
    return (num * num / den) / float(sst)


# --------------------------------------------------------------------------- reproducibility
def sha256_text(t):
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


def ladder_spec_text(canon=None):
    """The EXACT text that is hashed in the preregistration.  Change this and the hash changes."""
    c = canon or CANON
    lines = ["E1_I0027 CANONICAL REFERENCE LADDER v1",
             "rungs=" + "|".join(RUNGS),
             "canonical_rung=" + CANONICAL_RUNG,
             "targets=" + "|".join(TARGETS)]
    for t in TARGETS:
        d = c[t]
        lines.append("%s: mode=%s half_life=%s shrink=%s k=%s floor=%s"
                     % (t, d["mode"], d["half_life"], d["shrink"], d["k"], d["floor"]))
    lines.append("r4_features=intercept|R0|R1|R2|R3(if defined)|prior_minutes_ewma|"
                 "prior_rate_ewma|prior_season_player|log1p_n_prior")
    lines.append("r4_fit=OLS on seasons strictly earlier than the scored season")
    lines.append("denominator=SST of the response on the FULL scored row set, unweighted mean")
    return "\n".join(lines)


def ladder_hash(canon=None):
    return sha256_text(ladder_spec_text(canon))


#: The audit that constraint 2 demands.  Every rung AND every inference step, with its window.
TIME_WINDOW_TABLE = [
    ("R0_LEAGUE", "same-season league value",
     "all games in the same season on STRICTLY EARLIER DATES (date-blocked, so same-day games are "
     "excluded)", "prior-only"),
    ("R0_LEAGUE", "previous-season league value (chain step 2)",
     "the whole previous season; seasons are calendar-disjoint, asserted by assert_season_disjoint",
     "prior-only"),
    ("R0_LEAGUE", "GRAND (chain step 3)",
     "the whole frame; FIRES ONLY on rows with neither an earlier same-season game nor a previous "
     "season in the frame; counted and reported as grand_fallback_rows",
     "NOT prior-only -- named, counted, and never in an evaluation set"),
    ("R1_PLAYER_EXPAND", "player's expanding prior mean",
     "the player's own same-season games at an EARLIER position in the date-sorted group; prefix "
     "arrays indexed at h, never h+1", "prior-only"),
    ("R2_EWMA_TUNED", "tuned EWMA of the player's prior games", "as R1", "prior-only"),
    ("R2_EWMA_TUNED", "half-life / mode / shrinkage (pts, minutes, fga, ppm)",
     "D094's grid, selected on 2022-2023 and evaluated on 2023-2024; imported, not re-searched",
     "prior-only by D094's construction"),
    ("R2_EWMA_TUNED", "half-life (reb, ast)",
     "selected inside this screen on TRAIN SEASONS ONLY, frozen and hashed before any re-priced "
     "figure", "prior-only"),
    ("R2/R3/R4", "shrinkage target `prior_season`",
     "the player's own PREVIOUS season, whole; calendar-disjoint", "prior-only"),
    ("R3_RATE_X_MINUTES", "EWMA(rate) x EWMA(minutes)", "as R1, both factors", "prior-only"),
    ("R4_RICH_LOOKUP", "the feature columns", "each is a rung or a prior-only aggregate above",
     "prior-only"),
    ("R4_RICH_LOOKUP", "THE BLEND COEFFICIENTS (inference step)",
     "OLS fitted on seasons STRICTLY EARLIER than the season being scored; the earliest season is "
     "unscored", "prior-only"),
    ("re-price", "lead coefficients (inference step)",
     "refitted on seasons strictly earlier than the scored season, matching D089/D098's walk-"
     "forward protocol", "prior-only"),
    ("re-price", "the denominator SST",
     "computed on the realised response of the FULL scored row set; uses the response only, never a "
     "forecast, and is identical across every arm of a comparison",
     "uses realised y of the scored set -- as every R2 denominator must; identical across arms"),
]


def time_window_table_df():
    return pd.DataFrame(TIME_WINDOW_TABLE,
                        columns=["stage", "ingredient", "window_consumed", "verdict"])


def dump_spec(path, canon=None, extra=None):
    payload = {"spec_text": ladder_spec_text(canon), "sha256": ladder_hash(canon),
               "canon": canon or CANON, "rungs": RUNGS, "canonical_rung": CANONICAL_RUNG,
               "time_window_table": TIME_WINDOW_TABLE}
    if extra:
        payload.update(extra)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1, default=str)
    return payload["sha256"]
