"""
E1_I0043 -- OPPONENT DEFENCE.  Shared machinery.

THE SHARED SCREEN KIT IS NOT IMPORTED AND NOT MODIFIED.  Everything needed is reimplemented here.
`EntitySwap` is a faithful reimplementation of `E0_I0016/ep_base.py::EntitySwap` (read-only), and
that authorship is credited here and in NOTES.md; the anchor reproduction in s01 is the check that
the reimplementation is faithful.

PARTITION.  Seasons 2021-2024 only.  2025/2026 is never read, joined, merged or described.
Enforced on VALUES.  No name-based date detection: a column is checked only if its dtype is
actually datetime (this is the K0 trap -- 'candi-DATE' contains 'date', and pd.to_datetime on a
float column silently returns 1970).

NO NAME-BASED COLUMN SELECTION anywhere in this screen.  Every column list is an explicit literal
allowlist, is printed when resolved, and has its length asserted against a literal.
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
OUT = os.path.join(EXP, "E1_I0043_opponent_defence")
NULLS = os.path.join(OUT, "nulls")
F_EFF = os.path.join(EXP, "E0_I0016_efficiency_predictors")      # D085 frame (opponent family)
F_TV = os.path.join(EXP, "E1_I0018_teammate_volume_channel")     # D089 frame (player refs)

SEED = 20260808
N_DRAWS = 2000
ALLOWED_SEASONS = {2021, 2022, 2023, 2024}
FORBIDDEN_YEARS = (2025, 2026)

# ---- THE ONE CLEAN WINDOW.  E1_I0042 verified 2021 degenerate and 2022 dependent only on 2021.
CLEAN_EVAL_SEASONS = [2023, 2024]
DISCLOSED_CONTRAST_EVAL_SEASONS = [2022]        # reported, never a headline

# ---- EXPLICIT ALLOWLISTS.  Literal, printed, length-asserted.  Never a substring match.
CANDIDATE = ["A10_opp_defrtg"]
BASE_B0_COMPLETE = ["refB_ppm", "refB_spm", "refB_pps", "refB_mpg", "refB_own_usg_pg"]
BASE_B1_HONEST = BASE_B0_COMPLETE + ["D01_tm_poss_per40", "D02_opp_poss_per40"]
BASE_B2_FAMILY = BASE_B1_HONEST + ["A01_opp_efg_allowed", "A02_opp_ts_allowed"]
BASES = {"B0_COMPLETE": BASE_B0_COMPLETE, "B1_HONEST": BASE_B1_HONEST, "B2_FAMILY": BASE_B2_FAMILY}
BASE_LENGTHS = {"B0_COMPLETE": 5, "B1_HONEST": 7, "B2_FAMILY": 9}
NEG_CONTROL = ["G01_noise"]
A_FAMILY = ["A01_opp_efg_allowed", "A02_opp_ts_allowed", "A03_opp_paintpts_allowed",
            "A04_opp_blk", "A05_opp_fg3pct_allowed", "A06_opp_fg3a_share_allowed",
            "A07_opp_ftrate_allowed", "A08_opp_pf", "A09_opp_stl", "A10_opp_defrtg",
            "A11_opp_fastbreak_allowed", "A12_opp_2ndchance_allowed"]
RESPONSES = {"y_ppm": "y_ppm", "y_pts": "y_pts"}


def hdr(s):
    print("\n" + "=" * 104)
    print(s)
    print("=" * 104)


def sha(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")
                                     ).encode("utf-8")).hexdigest()


def prereg_sha():
    with open(os.path.join(OUT, "PREREG.md"), "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


# --------------------------------------------------------------------------- partition gate
def assert_partition(f, label="", verbose=False):
    """VALUE-level gate.  Only genuinely datetime-dtyped columns are checked; nothing is coerced."""
    if "season" in f.columns:
        bad = sorted(set(int(s) for s in pd.unique(f["season"])) - ALLOWED_SEASONS)
        assert not bad, "PARTITION VIOLATION %s: seasons %s" % (label, bad)
    checked = []
    for c in f.columns:
        s = f[c]
        if not pd.api.types.is_datetime64_any_dtype(s):
            continue
        mx = s.max()
        if pd.notna(mx):
            assert mx.year not in FORBIDDEN_YEARS and mx < pd.Timestamp("2025-01-01"), \
                "PARTITION VIOLATION %s: column %s reaches %s" % (label, c, mx)
        checked.append(c)
    if verbose:
        print("  assert_partition PASS %-10s seasons=%s datetime-cols-gated=%s"
              % (label, sorted(set(int(s) for s in pd.unique(f["season"]))), checked))
    return True


# --------------------------------------------------------------------------- loaders (READ ONLY)
def load_frames(verbose=True):
    a = pd.read_parquet(os.path.join(F_EFF, "screen_frame.parquet"))
    b = pd.read_parquet(os.path.join(F_TV, "screen_frame.parquet"))
    a["game_date"] = pd.to_datetime(a["game_date"])
    b["game_date"] = pd.to_datetime(b["game_date"])
    assert_partition(a, "E0_I0016", verbose)
    assert_partition(b, "E1_I0018", verbose)
    if verbose:
        print("  E0_I0016 screen_frame %d rows x %d cols   max_date %s"
              % (len(a), a.shape[1], a["game_date"].max().date()))
        print("  E1_I0018 screen_frame %d rows x %d cols   max_date %s"
              % (len(b), b.shape[1], b["game_date"].max().date()))
    return a, b


def build_merged(verbose=True):
    """Inner merge on (season, player_id, game_id).  Row count asserted against the literal 14852."""
    a, b = load_frames(verbose)
    k = ["season", "player_id", "game_id"]
    take_b = ["prior5_minutes", "y_pts", "y_spm", "TSA", "refB_spm", "refB_pps", "refB_mpg",
              "refB_own_usg_pg", "O01_own_usg_pg"]
    assert len(take_b) == 9, "allowlist length changed"
    m = a.merge(b[k + take_b], on=k, how="inner", suffixes=("", "_tv"))
    assert len(m) == 14852, "merged row count %d != 14852" % len(m)
    m["game_date"] = pd.to_datetime(m["game_date"])
    m = m.sort_values(["season", "player_id", "game_date", "game_id"]).reset_index(drop=True)
    assert_partition(m, "MERGED", verbose)
    m["opp_team_season"] = (m["opp_team_id"].astype(str) + "|" + m["season"].astype(str))
    if verbose:
        print("  MERGED %d rows  players=%d  opp_team_seasons=%d  games=%d  dates=%d"
              % (len(m), m["player_id"].nunique(), m["opp_team_season"].nunique(),
                 m["game_id"].nunique(), m["game_date"].nunique()))
    return m


def decision_mask(m):
    """D081's decision stratum, exactly as E1_I0023/s00_prereg.py defined it."""
    return (pd.to_numeric(m["n_prior"], errors="coerce").to_numpy(float) >= 8.0) & \
           (pd.to_numeric(m["prior5_minutes"], errors="coerce").to_numpy(float) >= 24.0)


def finite_mask(m, cols):
    ok = np.ones(len(m), bool)
    for c in cols:
        ok &= np.isfinite(pd.to_numeric(m[c], errors="coerce").to_numpy(float))
    return ok


def coverage_report(m, cols, mask, label, P):
    """D087 guard: assert coverage counts for every base column rather than assuming them."""
    rows = []
    n = int(mask.sum())
    for c in cols:
        v = pd.to_numeric(m[c], errors="coerce").to_numpy(float)
        nn = int(np.isfinite(v[mask]).sum())
        rows.append(dict(base=label, column=c, rows_in_stratum=n, finite=nn,
                         missing=n - nn, coverage=nn / n if n else np.nan))
        P("    coverage %-24s %-22s %6d/%6d = %.6f" % (label, c, nn, n, nn / n if n else np.nan))
        assert nn == n, "REFERENCE INCOMPLETENESS: %s covers %d of %d rows" % (c, nn, n)
    return rows


# --------------------------------------------------------------------------- OLS / dR2
def ols(X, y):
    return np.linalg.lstsq(X, y, rcond=None)[0]


def design(v, cols, mask):
    n = int(mask.sum())
    X = np.empty((n, len(cols) + 1), float)
    X[:, 0] = 1.0
    for j, c in enumerate(cols):
        X[:, j + 1] = v[c][mask]
    return X


def fit_folds(m, v, basecols, dcol, mask, eval_seasons, arm):
    """Walk-forward.  Train strictly on earlier seasons; score on each eval season.

    arm = UNFROZEN   -- refit the whole augmented model; intercept and base coefficients free.
    arm = FROZEN     -- intercept AND every base coefficient held at the base fit; only the
                        defence coefficient is estimated, on the base's training residual, against
                        a TRAIN-MEAN-CENTRED defence column, so no mean shift can be smuggled in.
    arm = INTERCEPT_ONLY -- a free intercept shift and NO defence column at all.

    Returns concatenated eval-fold vectors so SST is computed ONCE on a common denominator (D101).
    """
    ssn = m["season"].to_numpy()
    y_all, yb_all, ya_all, idx_all, betas = [], [], [], [], []
    for s in eval_seasons:
        tr = mask & (ssn < s)
        te = mask & (ssn == s)
        if tr.sum() < 300 or te.sum() < 80:
            continue
        Xb_tr, Xb_te = design(v, basecols, tr), design(v, basecols, te)
        y_tr, y_te = v[dcol[1]][tr], v[dcol[1]][te]
        bb = ols(Xb_tr, y_tr)
        yb = Xb_te @ bb
        dname = dcol[0]
        if arm == "INTERCEPT_ONLY":
            c = float((y_tr - Xb_tr @ bb).mean())
            ya = yb + c
            betas.append(c)
        else:
            dbar = float(v[dname][tr].mean())
            d_tr = v[dname][tr] - dbar
            d_te = v[dname][te] - dbar
            if arm == "UNFROZEN":
                Xa_tr = np.column_stack([Xb_tr, d_tr])
                Xa_te = np.column_stack([Xb_te, d_te])
                ba = ols(Xa_tr, y_tr)
                ya = Xa_te @ ba
                betas.append(float(ba[-1]))
            elif arm == "FROZEN":
                r_tr = y_tr - Xb_tr @ bb
                dd = float(d_tr @ d_tr)
                g = float(d_tr @ r_tr) / dd if dd > 0 else 0.0
                ya = yb + g * d_te
                betas.append(g)
            else:
                raise ValueError(arm)
        y_all.append(y_te)
        yb_all.append(yb)
        ya_all.append(ya)
        idx_all.append(np.flatnonzero(te))
    if not y_all:
        return None
    y = np.concatenate(y_all)
    yb = np.concatenate(yb_all)
    ya = np.concatenate(ya_all)
    idx = np.concatenate(idx_all)
    sst = float(((y - y.mean()) ** 2).sum())
    sse_b = float(((y - yb) ** 2).sum())
    sse_a = float(((y - ya) ** 2).sum())
    return dict(dr2=(sse_b - sse_a) / sst, sst=sst, sse_base=sse_b, sse_aug=sse_a,
                n=len(y), beta=float(np.mean(betas)), y=y, yb=yb, ya=ya, idx=idx,
                n_folds=len(y_all))


class Cell:
    """A frozen cell: identical response, row set, SST basis, weighting and base across every draw.

    The ONLY thing a null draw is permitted to change is the defence column's VALUES.  Everything
    else -- rows, folds, base columns, response, SST -- is fixed at construction.  This is the D101
    denominator rule implemented rather than asserted.
    """

    def __init__(self, m, v, basecols, dname, yname, mask, eval_seasons, arm):
        self.m, self.v, self.basecols = m, dict(v), basecols
        self.dname, self.yname, self.mask = dname, yname, mask
        self.eval_seasons, self.arm = eval_seasons, arm

    def dr2(self, dvals=None):
        v = self.v
        if dvals is not None:
            v = dict(self.v)
            v[self.dname] = dvals
        r = fit_folds(self.m, v, self.basecols, (self.dname, self.yname), self.mask,
                      self.eval_seasons, self.arm)
        return np.nan if r is None else r["dr2"]

    def full(self):
        return fit_folds(self.m, self.v, self.basecols, (self.dname, self.yname), self.mask,
                         self.eval_seasons, self.arm)


# --------------------------------------------------------------------------- nulls
def _group_codes(df, cols):
    key = df[cols[0]].astype(str)
    for c in cols[1:]:
        key = key + "|" + df[c].astype(str)
    return pd.factorize(key, sort=True)[0]


class EntitySwap:
    """N_ESWAP -- reassign whole entity-season SERIES to other entity-seasons inside the same season.

    FAITHFUL REIMPLEMENTATION of `E0_I0016/ep_base.py::EntitySwap` (read-only).  Rows are grouped by
    entity-season and ordered by (date, game_id).  Per draw, entity-seasons are permuted inside each
    season; an entity of length n_e receives its partner's values at PROPORTIONAL positions, so
    series length and within-season temporal shape are preserved.

    Exchangeability tested: the OPPONENT ENTITY LABELS.  This is a BETWEEN-entity null, matched to
    the level `A10_opp_defrtg` varies at.  A within-player null is structurally blind to it.

    WHAT IT DOES NOT DO.  It does not preserve the exact marginal when partners differ in length;
    it does not preserve cross-entity correlation; it is a label randomisation, not a bootstrap.
    """

    def __init__(self, df, entity_cols, date_col="game_date", season_col="season"):
        codes = _group_codes(df, entity_cols)
        order = np.lexsort((df["game_id"].to_numpy(), df[date_col].to_numpy(), codes))
        self.n = len(df)
        oc = codes[order]
        starts = np.flatnonzero(np.r_[True, oc[1:] != oc[:-1]])
        ends = np.r_[starts[1:], len(oc)]
        seasons = df[season_col].to_numpy()
        self.groups = [(int(seasons[order[s:e][0]]), order[s:e]) for s, e in zip(starts, ends)]
        self.by_season = {}
        for gi, (s, _) in enumerate(self.groups):
            self.by_season.setdefault(s, []).append(gi)
        self.n_groups = len(self.groups)
        self.n_blocks_per_season = {s: len(g) for s, g in self.by_season.items()}

    def draw(self, x, rng):
        out = np.empty_like(x)
        for s, gis in self.by_season.items():
            perm = rng.permutation(len(gis))
            for a, b in enumerate(perm):
                ia, ib = self.groups[gis[a]][1], self.groups[gis[b]][1]
                na, nb = len(ia), len(ib)
                pos = (np.round(np.arange(na) / max(na - 1, 1) * max(nb - 1, 0)).astype(int)
                       if na > 1 else np.zeros(na, int))
                out[ia] = x[ib][pos]
        return out


class WithinDateOppSwap:
    """N_DATE -- permute the opponent-team-game defence values among the games on the same date.

    A between-entity null at a finer block than the season swap: it holds the calendar fixed and
    asks whether WHICH opponent a player faced on a given night carries information.  Blocks are
    dates; the exchangeable units inside a block are the distinct opponent-team-games on that date.
    """

    def __init__(self, df, date_col="game_date"):
        d = df[date_col].to_numpy()
        u = _group_codes(df, ["opp_team_id", "game_id"])
        self.blocks = []
        for dt in np.unique(d):
            rows = np.flatnonzero(d == dt)
            units, first = [], {}
            for r in rows:
                first.setdefault(u[r], []).append(r)
            units = list(first.values())
            if len(units) > 1:
                self.blocks.append(units)
        self.n_groups = sum(len(b) for b in self.blocks)
        self.n_blocks = len(self.blocks)

    def draw(self, x, rng):
        out = x.copy()
        for units in self.blocks:
            perm = rng.permutation(len(units))
            for a, b in enumerate(perm):
                ia, ib = units[a], units[b]
                na, nb = len(ia), len(ib)
                pos = (np.round(np.arange(na) / max(na - 1, 1) * max(nb - 1, 0)).astype(int)
                       if na > 1 else np.zeros(na, int))
                out[np.asarray(ia)] = x[np.asarray(ib)][pos]
        return out


class WithinPlayerCyclic:
    """N_WITHIN -- cyclic shift of the defence column inside each player-season.  CONTRAST ONLY.

    Never a verdict in this screen.  It is computed so that this screen DEMONSTRATES the blindness
    of a within-entity null to a between-entity candidate rather than citing another screen for it.
    """

    def __init__(self, df, entity_cols=("player_id", "season"), date_col="game_date"):
        codes = _group_codes(df, list(entity_cols))
        order = np.lexsort((df["game_id"].to_numpy(), df[date_col].to_numpy(), codes))
        oc = codes[order]
        starts = np.flatnonzero(np.r_[True, oc[1:] != oc[:-1]])
        ends = np.r_[starts[1:], len(oc)]
        self.groups = [order[s:e] for s, e in zip(starts, ends)]
        self.n_groups = len(self.groups)

    def draw(self, x, rng):
        out = np.empty_like(x)
        for idx in self.groups:
            k = int(rng.integers(0, len(idx))) if len(idx) > 1 else 0
            out[idx] = np.roll(x[idx], k)
        return out


class WithinEntityShuffle:
    """N_BLIND -- free shuffle of the candidate INSIDE each opponent-team-season.  CONTRAST ONLY.

    THIS is the null D085 used as its `p_N1_within_entity` arm, and it is the null the programme's
    within-entity-null audit (D115/D117) is about.  It preserves each opponent-team-season's MEAN
    of the candidate exactly, and 77.1% of this candidate's variance is exactly that mean, so the
    null is structurally near-blind to it BY CONSTRUCTION.  Run here so that this screen
    DEMONSTRATES the blindness on its own cell instead of citing another screen for it.

    NOTE ON A COMMON CONFUSION, recorded because this screen made it first: a within-PLAYER null is
    NOT the blind null for this candidate.  A player faces many different opponents, so shuffling
    the opponent's rating across a player's games does destroy the signal.  The blind null is the
    one that permutes WITHIN THE ENTITY THE CANDIDATE IS CONSTANT-ISH IN -- the opponent-team-season.
    """

    def __init__(self, df, entity_cols=("opp_team_id", "season")):
        codes = _group_codes(df, list(entity_cols))
        order = np.argsort(codes, kind="stable")
        oc = codes[order]
        starts = np.flatnonzero(np.r_[True, oc[1:] != oc[:-1]])
        ends = np.r_[starts[1:], len(oc)]
        self.groups = [order[s:e] for s, e in zip(starts, ends)]
        self.n_groups = len(self.groups)

    def draw(self, x, rng):
        out = np.empty_like(x)
        for idx in self.groups:
            out[idx] = x[rng.permutation(idx)]
        return out


def run_null(cell, swapper, n_draws=N_DRAWS, seed=SEED, label=""):
    """Signed statistics only.  Absolute values are never stored.  p is the add-one estimator."""
    rng = np.random.default_rng(seed)
    x = cell.v[cell.dname]
    real = float(cell.dr2())
    draws = np.empty(n_draws, float)
    for i in range(n_draws):
        draws[i] = cell.dr2(swapper.draw(x, rng))
    ok = np.isfinite(draws)
    d = draws[ok]
    mean, sd = float(d.mean()), float(d.std(ddof=1))
    return dict(label=label, real=real, draws=draws, n_draws=int(n_draws), n_finite=int(ok.sum()),
                null_mean=mean, null_sd=sd,
                z=(real - mean) / sd if sd > 0 else np.nan,
                p=float((1.0 + int((d >= real).sum())) / (len(d) + 1.0)),
                n_groups=int(getattr(swapper, "n_groups", -1)))


def save_null(name, res, extra=None):
    """RAW, UNSTANDARDISED draws.  Standardising erases the null mean irrecoverably."""
    payload = dict(draws_raw_unstandardised=res["draws"],
                   observed_signed=np.array([res["real"]]),
                   null_mean=np.array([res["null_mean"]]),
                   null_sd=np.array([res["null_sd"]]),
                   n_groups=np.array([res["n_groups"]]),
                   n_draws=np.array([res["n_draws"]]),
                   label=np.array([res["label"]]))
    for k, val in (extra or {}).items():
        payload[k] = np.array([val])
    np.savez(os.path.join(NULLS, name + ".npz"), **payload)
    return os.path.join(NULLS, name + ".npz")
