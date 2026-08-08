"""E1_I0018 TEAMMATE VOLUME CHANNEL -- shared loader, reference builder, fast dR2, null helpers.

WHAT THIS SCREEN IS.  D085 (E0_I0016_efficiency_predictors) screened 44 candidates for predictors
    of scoring EFFICIENCY and cleared essentially nothing.  ONE candidate survived everything and
    was set aside because it answered a different question:

        C04_teammate_usg_present -- sum of the STRICTLY PRIOR per-game usage of the OTHER players
        who appear in TODAY's box score.

        dR2 0.00330 on points-per-minute, family-wise p 0.0017; STRENGTHENS to 0.00496 on the
        decision stratum (>=8 prior appearances, >=24 trailing-5 minutes, n=5,673); DEAD on true
        shooting (fw p 0.885) and on eFG (fw p 1.000).

    Alive on ppm and dead on both conversion measures => the channel is SHOTS-PER-MINUTE, not
    points-per-shot.  POINTS = MINUTES x SHOTS-PER-MINUTE x POINTS-PER-SHOT, and D081 put the
    points error ~3:1 on the per-minute step.  Nobody has tested whether the volume channel
    REACHES POINTS.  That is this screen.

E1 CHARACTER: still exploration.  EVERY OUTPUT HERE IS A LEAD, NEVER A RESULT.  No promotion
    threshold, no bootstrap, no registry/ledger/graph-event entry, no preregistration obligation.

PARTITION (GRAPH_POLICY 13.2): seasons 2021-2024 ONLY, enforced by screenkit.assert_partition,
    a VALUE test on parsed dates and season-valued columns.  No regex/byte scan is used as a
    partition check anywhere in this screen.

INPUTS AND THEIR MANIFEST VERDICTS (screenkit.check_manifest, read from disk at call time):
    data/masters/master_player.parquet    asof_granularity "row" -> USABLE_IF_FILTERED   [USED]
    data/masters/master_team.parquet      asof_granularity "row" -> USABLE_IF_FILTERED   [USED]
    data/w1_truth/player_game_availability.csv, data/w1_truth/roster_asof.csv
                                          "artifact", fit_through_season 2026 -> UNUSABLE
                                          [NOT OPENED -- filtering does not help.  This is exactly
                                          the file an availability screen reaches for first, and it
                                          is forbidden.  Availability is REBUILT FROM BOX
                                          MEMBERSHIP, the D076 method, as D085 also did.]
    E0_I0016_efficiency_predictors/screen_frame.parquet -- read READ-ONLY as the REPRODUCTION
                                          TARGET only.  Its provenance is s01_build_frame.py in
                                          that frozen directory.

R2 CONVENTION (D069): plain unweighted OLS R2, SST about the UNWEIGHTED mean, declared explicitly.

NO MODEL FITTING IS AUTHORISED.  The champion is never loaded and never retrained.  The only
    fitting anywhere is the screening regression `y ~ 1 + <base> + candidate`, whose IN-SAMPLE
    increment is compared against a permutation null and NEVER against zero.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
KIT = os.path.join(ROOT, r"experiments\exploration\_screen_kit")
OUT = os.path.join(ROOT, r"experiments\exploration\E1_I0018_teammate_volume_channel")
D085 = os.path.join(ROOT, r"experiments\exploration\E0_I0016_efficiency_predictors")
MP_PATH = os.path.join(ROOT, r"data\masters\master_player.parquet")
MT_PATH = os.path.join(ROOT, r"data\masters\master_team.parquet")
D085_FRAME = os.path.join(D085, "screen_frame.parquet")

if KIT not in sys.path:
    sys.path.insert(0, KIT)
import screenkit as sk  # noqa: E402

SEED = 20260808
SEASONS = (2021, 2022, 2023, 2024)
MIN_PRIOR_APPEARANCES = 3      # identical to D085's frame filter, so the row set is reproducible
N_DRAWS = 600                  # identical to D085

os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.dont_write_bytecode = True

pd.set_option("display.width", 230)
pd.set_option("display.max_columns", 120)


def hdr(s):
    print("\n" + "=" * 100)
    print(s)
    print("=" * 100)


# =====================================================================================
# strictly-prior expanding helpers.  .shift(1) ALWAYS PRECEDES .expanding().
# Copied verbatim from E0_I0016/ep_base.py (frozen, read-only) so the reproduction is exact.
# =====================================================================================
def prior_sum(df, keys, col):
    return df.groupby(keys, sort=False)[col].transform(lambda x: x.shift(1).expanding().sum())


def prior_mean(df, keys, col):
    return df.groupby(keys, sort=False)[col].transform(lambda x: x.shift(1).expanding().mean())


def prior_count(df, keys, col):
    return df.groupby(keys, sort=False)[col].transform(lambda x: x.shift(1).expanding().count())


def safe_div(a, b):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        r = np.where(np.isfinite(b) & (b != 0), a / b, np.nan)
    return r


def league_prior_mean(df, seasoncol, datecol, valcol):
    """Expanding league mean over rows strictly EARLIER IN THE SAME SEASON.  Cold-start only."""
    fs = df.sort_values([seasoncol, datecol, "game_id"], kind="stable")
    cum = fs.groupby(seasoncol, sort=False)[valcol].transform(
        lambda x: x.shift(1).expanding().mean())
    return cum.reindex(df.index)


# =====================================================================================
# FAST INCREMENTAL R2 -- verified against screenkit.delta_r2_plain in s01 on real data.
# Adapted from E0_I0016/ep_base.py::BaseFit, generalised to a MULTI-COLUMN base, which is what
# the D087 complete-reference check needs.
# =====================================================================================
class BaseFit:
    """Precomputed residualiser for a fixed base design [1, base...].

    dR2 of adding candidate x is ((e . xt)^2 / (xt . xt)) / SST, with e = y residualised on the
    base and xt = x residualised on the base.  Algebraically identical to
    screenkit.delta_r2_plain(y, base, [base, x]).  D069 convention: SST about the UNWEIGHTED mean.
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

    def beta_sign(self, x):
        b = self.beta(x)
        return float(np.sign(b))

    def fitted_with(self, x):
        """In-sample fitted values of y ~ 1 + base + x.  A SCREENING REGRESSION, NOT A MODEL."""
        x = np.asarray(x, float)
        Xf = np.column_stack([self.X, x])
        beta, *_ = np.linalg.lstsq(Xf, self.y, rcond=None)
        return Xf @ beta

    def fitted_base(self):
        return self.X @ (self.XtXi @ (self.X.T @ self.y))


def mae(y, yhat):
    return float(np.mean(np.abs(np.asarray(y, float) - np.asarray(yhat, float))))


# =====================================================================================
# NULL MACHINERY.  Identical in construction to D085's, so the reproduction is like-for-like.
#   N1 = screenkit.permutation_null(scheme=SCHEME_WITHIN) at the entity level, block_col="season"
#   N2 = screenkit.entity_swap_null  (the K2 fix -- now A KIT FUNCTION, no longer a declared gap)
#   N3 = screenkit ROW_LEVEL, CONTRAST ONLY, never a verdict
# =====================================================================================
CANDIDATE_KEYS = {
    "row": None,
    "player_game": ["player_id", "game_id"],
    "team_game": ["team_id", "game_id"],
    "opp_team_game": ["opp_team_id", "game_id"],
    "game": ["game_id"],
    "player_season": ["player_id", "season"],
    "team_season": ["team_id", "season"],
    "opp_team_season": ["opp_team_id", "season"],
    "season": ["season"],
}

ENTITY_TEAM = ("team_season", ["team_id", "season"])
ENTITY_PLAYER = ("player_season", ["player_id", "season"])


def run_nulls(bf, d, x, lvl_cols, n_draws=N_DRAWS, seed=SEED):
    """N1 (within-entity-season) + N3 (row, contrast) via null_width_comparison, and N2 via the
    kit's entity_swap_null.  Returns draws so a family-wise max-t can be built over everything."""
    d = d.copy()
    d["feat"] = x

    def stat_fn(dfr, _bf=bf):
        return _bf.dr2(pd.to_numeric(dfr["feat"], errors="coerce").to_numpy(float))

    cw = sk.null_width_comparison(stat_fn, d, lvl_cols, n_draws, seed, feature_col="feat",
                                  block_col="season", alternative="greater",
                                  scheme=sk.SCHEME_WITHIN)
    n2 = sk.entity_swap_null(stat_fn, d, lvl_cols, n_draws, seed, feature_col="feat",
                             date_col="game_date", season_col="season", tiebreak_col="game_id",
                             alternative="greater")
    n1 = cw["correct"]
    return {
        "real": float(n1["real"]),
        "p_N1_within_entity": float(n1["p"]), "null_sd_N1": float(n1["sd"]),
        "null_mean_N1": float(n1["mean"]),
        "p_N2_entity_swap": float(n2["p"]), "null_sd_N2": float(n2["sd"]),
        "null_mean_N2": float(n2["mean"]),
        "p_correct_level": float(max(n1["p"], n2["p"])),
        "p_row_level_NAIVE": float(cw["p_row_level_NAIVE"]),
        "null_sd_row_NAIVE": float(cw["row_level"]["sd"]),
        "inflation_N1_over_row": float(cw["inflation"]),
        "inflation_N2_over_row": float(n2["sd"] / cw["row_level"]["sd"])
        if cw["row_level"]["sd"] > 0 else float("nan"),
        "draws_N1": np.asarray(n1["draws"], float),
        "draws_N2": np.asarray(n2["draws"], float),
    }


def maxt_family(store):
    """Family-wise max-t across a dict of cell_key -> draws.  Standardise each cell's draws by its
    own null mean/sd, then take the max over cells within each draw index."""
    keys = list(store.keys())
    D = np.vstack([store[k] for k in keys])
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
