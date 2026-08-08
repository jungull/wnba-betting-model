"""E1_I0031 RAPM AS PRIOR -- shared machinery.

USER'S SUGGESTION (direct).  "the wnba might even have a stat for this already like player plus
    minus which we should at least factor in or compete against."

ARTIFACTS
  data/rapm/rapm_walkforward.csv          -- asof_granularity "season", walk-forward, USED.
  data/rapm/rapm_v0.csv                   -- asof_granularity "artifact" -> FORBIDDEN, NOT OPENED.
  data/masters/master_player.parquet      -- asof_granularity "row", filtered at the filter-point.
  E0_I0015/decomp_frame.parquet           -- D081's frozen scored frame (READ ONLY).
  E1_I0022/estimator_surface.csv          -- D094's 15,048-cell grid (READ ONLY, built upon).

PARTITION.  Exploration partition is 2021-2024.  The RAPM artifact carries FIVE emit seasons
    (2022,2023,2024,2025,2026); the 2025 and 2026 emit rows are DROPPED AT THE FILTER-POINT and are
    never read, joined, plotted or described.  The scored frame is 2022-2024 (the 2021 champion fold
    is degenerate); 2021 enters only as RAPM training data inside the artifact itself.

WHY THE MACHINERY IS LOCAL.  Five other agents are running in sibling directories.  `_screen_kit`
    is explicitly declared stable and IS imported (for check_manifest / assert_partition /
    paired_forecast_comparison).  The estimator engine is credited to and reimplemented from
    E1_I0022/ose_base.py (D094); the cyclic-shift null is credited to E1_I0021/hd_base.py (D093);
    the cold-start placeholder is credited to E1_I0020/ct_base.py (D092).  Nothing in those
    directories is written to.

TIME WINDOW OF EVERY INGREDIENT -- see NOTES.md TIME-WINDOW TABLE.
"""
import hashlib
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
KIT = os.path.join(ROOT, r"experiments\exploration\_screen_kit")
OUT = os.path.join(ROOT, r"experiments\exploration\E1_I0031_rapm_as_prior")
D081 = os.path.join(ROOT, r"experiments\exploration\E0_I0015_points_skill_decomposition")
D092 = os.path.join(ROOT, r"experiments\exploration\E1_I0020_coldstart_tiering")
D094 = os.path.join(ROOT, r"experiments\exploration\E1_I0022_optimal_simple_estimator")
FRAME = os.path.join(D081, "decomp_frame.parquet")
SURFACE = os.path.join(D094, "estimator_surface.csv")
RAPM = os.path.join(ROOT, r"data\rapm\rapm_walkforward.csv")
RAPM_SEASONS = os.path.join(ROOT, r"data\rapm\rapm_walkforward_seasons.csv")
MASTER = os.path.join(ROOT, r"data\masters\master_player.parquet")
BIOS = os.path.join(ROOT, r"data\reference\player_bios.csv")

if KIT not in sys.path:
    sys.path.insert(0, KIT)
import screenkit as sk  # noqa: E402

SEED = 20260808
PARTITION = [2021, 2022, 2023, 2024]
SCREEN_SEASONS = [2022, 2023, 2024]     # emit seasons we may look at
HOLDOUT = {2025, 2026}
N_DRAWS = 2000
TARGETS = ["pts", "minutes", "fga", "ppm"]

os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.dont_write_bytecode = True
pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 100)


def hdr(s):
    print("\n" + "=" * 100)
    print(s)
    print("=" * 100)


def sub(s):
    print("\n--- %s " % s + "-" * max(0, 96 - len(s)))


# ------------------------------------------------------------------ partition guards (VALUES only)
def guard(df, where, cols=("season",)):
    """VALUE test on named season columns.  Never a text scan."""
    seen = {}
    for c in cols:
        if c not in df.columns:
            continue
        v = pd.to_numeric(df[c], errors="coerce").dropna()
        s = set(int(x) for x in v.unique())
        bad = s & HOLDOUT
        if bad:
            raise SystemExit("PARTITION VIOLATION at %s col=%s: %s" % (where, c, sorted(bad)))
        seen[c] = sorted(s)
    print("  guard ok  %-46s n=%-7d %s" % (where, len(df), seen))


def assert_partition_values(f, where="", allow_before=(), verbose=True):
    """Every season-valued numeric column in 2021..2024; every datetime year in 2021..2024.

    `allow_before` names columns permitted to hold values STRICTLY EARLIER than 2021 (there are
    none in this screen by default).  A value >= 2025 is FATAL in every column, always.
    """
    viol, checked_s, checked_d = [], [], []
    for c in f.columns:
        s = f[c]
        if pd.api.types.is_datetime64_any_dtype(s):
            checked_d.append(c)
            y = s.dropna().dt.year
            if len(y) and (int(y.max()) > 2024 or int(y.min()) < 2021):
                viol.append((c, "date-year", int(y.min()), int(y.max())))
        elif pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s):
            v = pd.to_numeric(s, errors="coerce").dropna()
            if len(v) == 0:
                continue
            uq = np.unique(v.to_numpy(float))
            if uq.min() >= 1990 and uq.max() <= 2100 and np.allclose(uq, np.round(uq)):
                checked_s.append(c)
                hi_bad = uq.max() > 2024
                lo_bad = uq.min() < 2021 and c not in allow_before
                if hi_bad or lo_bad:
                    viol.append((c, "season-value", float(uq.min()), float(uq.max())))
    if viol:
        raise SystemExit("PARTITION VIOLATION at %s: %s" % (where, viol))
    if verbose:
        print("  assert_partition_values %-24s PASS  season_cols=%s date_cols=%s"
              % (where, checked_s, checked_d))
    return {"season_cols": checked_s, "date_cols": checked_d}


# ------------------------------------------------------------------------------------- io helpers
def jdump(obj, name):
    p = os.path.join(OUT, name)
    with open(p, "w") as fh:
        json.dump(obj, fh, indent=2, default=_jsan)
    print("  wrote %s" % name)
    return p


def _jsan(o):
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, pd.Timestamp):
        return str(o)
    return str(o)


def wcsv(df, name):
    for c in ("season", "emit_season"):
        if c in df.columns:
            guard(df, "write:" + name, cols=(c,))
            break
    df.to_csv(os.path.join(OUT, name), index=False)
    print("  wrote %s (%d rows)" % (name, len(df)))


def sha256_text(t):
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


# ============================================================================== RAPM loader
# Fixed-lambda net columns are COMPARABLE ACROSS EMIT SEASONS.  `net_100` / `orapm_100` /
# `drapm_100` are at `lambda_chosen`, which VARIES BY EMIT SEASON by a factor of ~50 in this
# artifact (2022: 100000 fallback_max_grid; 2023: 33000; 2024: 2000) -- so their SCALE is not
# comparable across seasons and they are used ONLY after within-emit-season standardisation.
RAPM_FIXED = ["net_100_lam500", "net_100_lam1000", "net_100_lam2000", "net_100_lam5000"]
RAPM_CHOSEN = ["orapm_100", "drapm_100", "net_100"]


def load_rapm(verbose=True):
    """rapm_walkforward.csv, FILTERED to emit seasons 2022-2024 at the FILTER-POINT.

    Returns (frame, provenance_dict).  Every provenance claim is re-derived here from the
    artifact's OWN COLUMN VALUES -- the coordinator's manifest check is not inherited.
    """
    man = sk.check_manifest(RAPM, verbose=False)
    raw = pd.read_csv(RAPM)
    n_raw = len(raw)
    raw["train_seasons"] = raw["train_seasons"].astype(str)

    # ---- STEP 1 VERIFICATION, on VALUES, BEFORE any filtering ----------------------------------
    prov = {"manifest_status": man.get("status"),
            "manifest_asof_granularity": man.get("asof_granularity", man.get("granularity")),
            "manifest_raw": {k: v for k, v in man.items() if k != "manifest"},
            "n_rows_raw": n_raw,
            "emit_seasons_raw": sorted(int(x) for x in raw["season"].unique())}
    bad = []
    per_emit = {}
    for s, g in raw.groupby("season"):
        toks = set()
        for t in g["train_seasons"].unique():
            for part in str(t).split(","):
                part = part.strip()
                if "-" in part:
                    a, b = part.split("-")
                    toks.update(range(int(a), int(b) + 1))
                elif part:
                    toks.add(int(part))
        mx = max(toks)
        fts = sorted(int(x) for x in g["fit_through_season"].unique())
        per_emit[int(s)] = {"train_season_tokens": sorted(toks),
                            "max_train_season": int(mx),
                            "fit_through_season_values": fts,
                            "n_rows": int(len(g)),
                            "n_players": int(g["player_id"].nunique()),
                            "strictly_prior": bool(mx < int(s)),
                            "lambda_chosen": sorted(float(x) for x in g["lambda_chosen"].unique()),
                            "lambda_source": sorted(g["lambda_source"].astype(str).unique())}
        if mx >= int(s):
            bad.append((int(s), int(mx)))
        if any(f >= int(s) for f in fts):
            bad.append((int(s), "fit_through_season>=emit:%s" % fts))
    prov["per_emit_season_raw"] = per_emit
    prov["strict_prior_violations"] = bad
    prov["strict_prior_verified"] = (len(bad) == 0)
    # row-level, not just group-level
    def _maxtok(t):
        toks = []
        for part in str(t).split(","):
            part = part.strip()
            if "-" in part:
                a, b = part.split("-")
                toks.append(int(b))
            elif part:
                toks.append(int(part))
        return max(toks)
    rowmax = raw["train_seasons"].map(_maxtok)
    n_rowviol = int((rowmax >= raw["season"]).sum())
    n_ftviol = int((raw["fit_through_season"] >= raw["season"]).sum())
    prov["row_level_train_ge_emit"] = n_rowviol
    prov["row_level_fitthrough_ge_emit"] = n_ftviol
    prov["row_level_clean"] = (n_rowviol == 0 and n_ftviol == 0)
    prov["train_seasons_is_cumulative"] = {int(s): v["train_season_tokens"]
                                           for s, v in per_emit.items()}

    # ---- FILTER-POINT: drop 2025/2026 emit rows ------------------------------------------------
    r = raw[raw["season"].isin(SCREEN_SEASONS)].copy()
    prov["n_rows_after_partition_filter"] = int(len(r))
    prov["n_rows_dropped_holdout_emit"] = int(n_raw - len(r))
    prov["emit_seasons_kept"] = sorted(int(x) for x in r["season"].unique())
    # minutes_2021_24 is a 2021-2024 aggregate -> in-partition by construction; keep.
    guard(r, "rapm_walkforward after filter")

    # ---- within-emit-season standardisation of the lambda_chosen columns -----------------------
    for c in RAPM_CHOSEN:
        r["z_" + c] = r.groupby("season")[c].transform(
            lambda v: (v - v.mean()) / v.std(ddof=0) if v.std(ddof=0) > 0 else v * 0.0)
    for c in RAPM_FIXED:
        r["z_" + c] = r.groupby("season")[c].transform(
            lambda v: (v - v.mean()) / v.std(ddof=0) if v.std(ddof=0) > 0 else v * 0.0)
    r["log_total_poss"] = np.log1p(r["total_poss"].astype(float))

    if verbose:
        print("  rapm_walkforward  raw=%d  kept=%d  emit_seasons_kept=%s (dropped %d holdout rows)"
              % (n_raw, len(r), prov["emit_seasons_kept"], prov["n_rows_dropped_holdout_emit"]))
        print("  strict-prior verified on VALUES: %s   row-level clean: %s"
              % (prov["strict_prior_verified"], prov["row_level_clean"]))
    return r, prov


def load_rapm_seasons():
    s = pd.read_csv(RAPM_SEASONS)
    s = s[s["season"].isin(SCREEN_SEASONS)].copy()
    guard(s, "rapm_walkforward_seasons after filter")
    return s


# ============================================================================== base frame loader
def load_frame(verbose=True):
    f = pd.read_parquet(FRAME)
    f = f.sort_values(["season", "player_id", "gdate"], kind="stable").reset_index(drop=True)
    assert set(int(x) for x in f["season"].unique()) <= set(SCREEN_SEASONS)
    assert f["gdate"].max() < pd.Timestamp("2025-01-01")
    assert (f["y_minutes"] > 0).all()
    f["y_ppm"] = f["r_ppm"].astype(float)
    if verbose:
        print("  decomp_frame  shape=%s  seasons=%s  max_date=%s"
              % (f.shape, sorted(f["season"].unique()), f["gdate"].max().date()))
    return f


def attach_rapm(f, r, verbose=True):
    """Join RAPM on (emit season == row season, player_id).

    A 2022 row therefore receives the RAPM estimate FITTED ON 2021 ONLY; a 2023 row receives one
    fitted on 2021-2022; a 2024 row one fitted on 2021-2023.  Nothing in the joined value reads the
    row's own season.  The join key `season` is the RAPM EMIT season, never its fit season.
    """
    cols = (["season", "player_id", "off_poss", "def_poss", "total_poss", "log_total_poss",
             "lambda_chosen"] + RAPM_CHOSEN + RAPM_FIXED
            + ["z_" + c for c in RAPM_CHOSEN] + ["z_" + c for c in RAPM_FIXED])
    out = f.merge(r[cols], on=["season", "player_id"], how="left", validate="m:1")
    out["has_rapm"] = out["net_100_lam2000"].notna()
    if verbose:
        cov = out.groupby("season")["has_rapm"].agg(["mean", "sum", "size"])
        print("  RAPM join coverage by season (row level):")
        print(cov.to_string())
        pl = out.groupby(["season", "player_id"])["has_rapm"].first()
        print("  RAPM coverage at player-season level: %d / %d = %.3f"
              % (int(pl.sum()), len(pl), float(pl.mean())))
    return out


# ============================================================================== metrics
def mae(y, yhat):
    y = np.asarray(y, float)
    yhat = np.asarray(yhat, float)
    m = np.isfinite(y) & np.isfinite(yhat)
    return float(np.mean(np.abs(y[m] - yhat[m])))


def r2_forecast(y, yhat):
    """D069 convention: 1 - SSE/SST, SSE about the SUPPLIED forecast, SST about mean(y).  No refit."""
    y = np.asarray(y, float)
    yhat = np.asarray(yhat, float)
    m = np.isfinite(y) & np.isfinite(yhat)
    y, yhat = y[m], yhat[m]
    sse = float(((y - yhat) ** 2).sum())
    sst = float(((y - y.mean()) ** 2).sum())
    return 1.0 - sse / sst if sst > 0 else float("nan")


def skill(y, a, b):
    """1 - MAE_a/MAE_b on rows finite for BOTH forecasts (constraint 6: same rows, both sides)."""
    y = np.asarray(y, float)
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    m = np.isfinite(y) & np.isfinite(a) & np.isfinite(b)
    ma = float(np.mean(np.abs(y[m] - a[m])))
    mb = float(np.mean(np.abs(y[m] - b[m])))
    return float(1.0 - ma / mb), ma, mb, int(m.sum())


# ------------------------------------------------------------ OLS / dR2 on a COMMON denominator
def _design(X, intercept=True):
    X = np.asarray(X, float)
    if X.ndim == 1:
        X = X[:, None]
    return np.column_stack([np.ones(len(X)), X]) if intercept else X


def ols_fit_predict(y, X, mask_fit=None):
    A = _design(X)
    y = np.asarray(y, float)
    m = np.isfinite(y) & np.isfinite(A).all(axis=1)
    if mask_fit is not None:
        m = m & mask_fit
    beta, *_ = np.linalg.lstsq(A[m], y[m], rcond=None)
    return A @ beta, beta, m


def dr2_common_denominator(y, X_base, X_full, sst_mask=None):
    """dR2 with BOTH SSEs and the SST taken on the SAME row set (D099).

    Returns (r2_base, r2_full, dR2, n_rows, sst).  The denominator SST is the one of the row set
    named by `sst_mask` (default: the rows scored).  Callers that want a subset's dR2 expressed on
    the FULL stratum's SST pass the full-stratum SST explicitly via `sst_override`.
    """
    y = np.asarray(y, float)
    Ab, Af = _design(X_base), _design(X_full)
    m = np.isfinite(y) & np.isfinite(Ab).all(axis=1) & np.isfinite(Af).all(axis=1)
    if sst_mask is not None:
        m = m & sst_mask
    yy = y[m]
    bb, *_ = np.linalg.lstsq(Ab[m], yy, rcond=None)
    ff, *_ = np.linalg.lstsq(Af[m], yy, rcond=None)
    sse_b = float(((yy - Ab[m] @ bb) ** 2).sum())
    sse_f = float(((yy - Af[m] @ ff) ** 2).sum())
    sst = float(((yy - yy.mean()) ** 2).sum())
    return {"r2_base": 1 - sse_b / sst, "r2_full": 1 - sse_f / sst,
            "dr2": (sse_b - sse_f) / sst, "n": int(m.sum()), "sst": sst,
            "sse_base": sse_b, "sse_full": sse_f}


# ============================================================================== inference
def block_signflip(diff, block_codes, n_draws=N_DRAWS, seed=SEED):
    """Paired sign-flip, WHOLE (season, player) block at a time.  Row-level flipping is
    anticonservative here and this programme has been burned by it (D081, D093)."""
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
            "n_rows": n_ok, "null_sd": float(draws.std(ddof=1)), "n_draws": int(n_draws)}, draws


class PlayerSeasonRelabeller:
    """CORRECT-LEVEL NULL for PLAYER-SEASON-CONSTANT features (constraint 4).

    RAPM is constant within (season, player_id).  Permuting it ROW-WISE, or shuffling it WITHIN a
    player, destroys nothing real and gives an anticonservative null -- and the kit refuses the
    within-player shuffle for exactly this reason.  The honest null RELABELS WHOLE PLAYER-SEASONS:
    draw a permutation of the distinct player-seasons and broadcast their value blocks back to the
    rows.  Block sizes and the number of rows per player-season are preserved exactly.

    THE WHOLE BLOCK MOVES UNDER ONE PERMUTATION.  Permuting each RAPM column independently would
    destroy the internal correlation between orapm/drapm/net and between lambda levels, which is a
    real structural property of the artifact and is not what the null is meant to break.  One
    permutation per draw keeps the block intact and destroys only its alignment to the response.
    """

    def __init__(self, ps_codes):
        codes = np.asarray(ps_codes)
        uq, inv = np.unique(codes, return_inverse=True)
        self.inv = inv
        self.n_groups = len(uq)
        # index of the FIRST row of each group -- vectorised, no Python loop
        order = np.argsort(inv, kind="stable")
        sorted_inv = inv[order]
        firsts = np.flatnonzero(np.r_[True, sorted_inv[1:] != sorted_inv[:-1]])
        self.first_idx = order[firsts]

    def block_values(self, X):
        """One row of values per player-season, in group-code order."""
        X = np.asarray(X, float)
        return X[self.first_idx] if X.ndim > 1 else X[self.first_idx]

    def draw(self, block_vals, rng):
        """Return a row-level array/matrix under one whole-block relabelling."""
        perm = rng.permutation(self.n_groups)
        return block_vals[perm][self.inv]


def cyclic_shift_within_groups(x, starts, ns, rng):
    """Rotate each group's series by a random offset.  Rows MUST be sorted by group then DATE.

    CREDIT: E1_I0021/hd_base.py (D093).  A plain within-group SHUFFLE is anticonservative for
    autocorrelated prior-history series (D093 measured p=0.0015 against an honest p=0.39); a cyclic
    shift preserves the marginal AND the serial structure and destroys only the alignment.
    """
    out = np.empty_like(x)
    for a, n in zip(starts, ns):
        if n <= 1:
            out[a:a + n] = x[a:a + n]
            continue
        k = int(rng.integers(0, n))
        out[a:a + n] = np.roll(x[a:a + n], k)
    return out


def group_bounds(f, keys=("season", "player_id")):
    codes = f.groupby(list(keys), sort=False).ngroup().to_numpy()
    change = np.flatnonzero(np.r_[True, codes[1:] != codes[:-1]])
    ns = np.diff(np.r_[change, len(codes)])
    return codes, change, ns


def assert_constant_within(f, col, keys=("season", "player_id")):
    g = f.groupby(list(keys), sort=False)[col].nunique(dropna=True)
    bad = int((g > 1).sum())
    assert bad == 0, "%s is NOT constant within %s (%d violating groups)" % (col, keys, bad)
    return True


# ============================================================================== D094 estimator engine
# Reimplemented from E1_I0022/ose_base.py (D094).  CREDIT: that screen.  Reimplemented rather than
# imported so that nothing in a sibling experiment directory is depended on at runtime.
def numden(f, target, mode):
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
    """S_num, S_den, S_w over STRICTLY PRIOR admissible games.  Prefix arrays indexed at h, the
    number of admissible games STRICTLY BEFORE the row -- never h+1.  D094's construction."""
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
        h = np.zeros(ln, dtype=np.int64)
        if m:
            h = np.searchsorted(comp, np.arange(ln), side="left")
        cn = num[sl][comp]
        cd = den[sl][comp]
        if kind == "expanding":
            pn = np.r_[0.0, np.cumsum(cn)]
            pd_ = np.r_[0.0, np.cumsum(cd)]
            S_num[sl] = pn[h]
            S_den[sl] = pd_[h]
            S_w[sl] = np.arange(m + 1, dtype=float)[h]
        elif kind == "sma":
            w = int(par)
            pn = np.r_[0.0, np.cumsum(cn)]
            pd_ = np.r_[0.0, np.cumsum(cd)]
            lo = np.maximum(h - w, 0)
            S_num[sl] = pn[h] - pn[lo]
            S_den[sl] = pd_[h] - pd_[lo]
            S_w[sl] = (h - lo).astype(float)
        else:
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


def _expanding_league_ratio(f, num, den):
    s = f["season"].to_numpy()
    d = f["gdate"].to_numpy()
    out = np.full(len(f), np.nan)
    for ss in np.unique(s):
        m = np.flatnonzero(s == ss)
        order = m[np.argsort(d[m], kind="stable")]
        dd = d[order]
        cn = np.r_[0.0, np.cumsum(num[order])]
        cd = np.r_[0.0, np.cumsum(den[order])]
        first = np.searchsorted(dd, dd, side="left")
        with np.errstate(invalid="ignore", divide="ignore"):
            out[order] = np.where(cd[first] > 0, cn[first] / cd[first], np.nan)
    return out


def _prev_season_league(f, num, den):
    s = f["season"].to_numpy()
    tot = {}
    for ss in np.unique(s):
        m = s == ss
        tot[int(ss)] = float(num[m].sum()) / float(den[m].sum())
    return np.array([tot.get(int(x) - 1, np.nan) for x in s])


def _prev_season_player(f, num, den):
    key = pd.DataFrame({"season": f["season"].to_numpy(), "pid": f["player_id"].to_numpy(),
                        "n": num, "d": den})
    g = key.groupby(["season", "pid"], sort=False)[["n", "d"]].sum()
    val = g["n"] / g["d"].replace(0.0, np.nan)
    lut = {(int(a) + 1, int(b)): float(v) for (a, b), v in val.items()}
    return np.array([lut.get((int(a), int(b)), np.nan)
                     for a, b in zip(f["season"].to_numpy(), f["player_id"].to_numpy())])


def role_bucket(f):
    s = f["season"].to_numpy()
    pid = f["player_id"].to_numpy()
    mpg = (pd.DataFrame({"season": s, "pid": pid, "m": f["y_minutes"].to_numpy(float)})
           .groupby(["season", "pid"])["m"].mean())
    buckets = {}
    for ss in np.unique(s):
        prev = int(ss) - 1
        if prev not in set(int(k[0]) for k in mpg.index):
            continue
        subm = mpg.loc[prev]
        q1, q2 = np.quantile(subm.to_numpy(float), [1 / 3, 2 / 3])
        for p, v in subm.items():
            buckets[(int(ss), int(p))] = 0 if v <= q1 else (1 if v <= q2 else 2)
    return np.array([buckets.get((int(a), int(b)), -1) for a, b in zip(s, pid)], dtype=np.int64)


def _expanding_bucket_ratio(f, num, den, bucket):
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
    lg = _expanding_league_ratio(f, num, den)
    prev_lg = _prev_season_league(f, num, den)
    league = np.where(np.isfinite(lg), lg, prev_lg)
    n_grand = int((~np.isfinite(league)).sum())
    league = np.where(np.isfinite(league), league, grand_fallback)
    ps = _prev_season_player(f, num, den)
    prior_season = np.where(np.isfinite(ps), ps, league)
    rl = _expanding_bucket_ratio(f, num, den, bucket)
    role = np.where(np.isfinite(rl), rl, league)
    return ({"league": league, "prior_season": prior_season, "role": role,
             "_prior_season_raw": ps}, n_grand)


def apply_shrink(S_num, S_den, S_w, targets, shrink):
    kind, k = shrink
    with np.errstate(invalid="ignore", divide="ignore"):
        raw = np.where(S_den > 0, S_num / np.where(S_den > 0, S_den, np.nan), np.nan)
    if kind == "none":
        return np.where(np.isfinite(raw), raw, targets["league"])
    T = targets[kind]
    ne = np.where(np.isfinite(raw), S_w, 0.0)
    r = np.where(np.isfinite(raw), raw, 0.0)
    return (ne * r + k * T) / (ne + k)
