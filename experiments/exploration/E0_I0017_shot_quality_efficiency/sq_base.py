"""
E0_I0017 SHOT QUALITY vs EFFICIENCY -- shared constants, loaders, strictly-prior helpers, fast dR2.

WHAT THIS SCREEN IS.  E0 breadth screen of PRE-GAME-FORECASTABLE SHOT-QUALITY features against
    player scoring EFFICIENCY.  D081 localised the champion player model's points failure at the
    per-minute efficiency step.  D081 (550 generic-state cells), D084 (opponent zone conversion) and
    D085 (44 basketball-specific candidates) all died.  D085 named exactly one surface it could not
    screen -- SHOT QUALITY -- because data/shotcharts/* has no manifest.  This screen resolves that
    provenance question by VALUE TEST (s00) and then screens the surface.

    E0 CHARACTER: fast, permissive, time-boxed, explicitly NON-CLAIMING.  Every output is a LEAD,
    NEVER A RESULT.  No bootstrap, no promotion threshold, no registry entry.

PARTITION: seasons 2021-2024 ONLY, enforced by screenkit.assert_partition (a VALUE test).
    shots_2025_*, shots_2026_*, pbp_10225*/10226*, and every master row with season>=2025 are
    never read.

THE CRITICAL DESIGN CONSTRAINT.  Shot quality is measured FROM the game being predicted, so the
    REALISED version is useless and forbidden.  Every realised per-game shot aggregate in this
    screen exists ONLY as an intermediate; it is converted to a strictly-prior forecast by
    `.shift(1)` BEFORE any `.expanding()` or `.rolling()`, inside (season, entity) ordered by date,
    and the realised column is dropped before screening.  s01 asserts by construction that every
    candidate is NaN on an entity's first appearance in a season.

R2 CONVENTION (D069): plain unweighted OLS R2, SST about the UNWEIGHTED mean.

NO MODEL FITTING.  The champion is never loaded and never retrained.  The only fitting is the
    two-column screening regression y ~ 1 + reference + candidate, whose in-sample increment is
    compared against a permutation null and NEVER against zero.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
KIT = os.path.join(ROOT, r"experiments\exploration\_screen_kit")
OUT = os.path.join(ROOT, r"experiments\exploration\E0_I0017_shot_quality_efficiency")
SHOTDIR = os.path.join(ROOT, r"data\shotcharts")
PBPDIR = os.path.join(ROOT, r"data\playbyplay")
MP_PATH = os.path.join(ROOT, r"data\masters\master_player.parquet")

if KIT not in sys.path:
    sys.path.insert(0, KIT)
import screenkit as sk  # noqa: E402

SEED = 20260808
SEASONS = (2021, 2022, 2023, 2024)
MIN_PRIOR_APPEARANCES = 3
N_DRAWS = 600
TRAIL = 5

os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.dont_write_bytecode = True

CANDIDATES_SHA256 = "15314c2163cb9b65c761d8bc859505578d5f474a4044a8442f0cc5cf42c5851f"

OUTCOMES = ("ppm", "ts", "efg")

# ---- the 39 preselected candidates, in the order and with the ids of CANDIDATES_PRESELECTED.md ---
FAMILY_A = ["A01_dist_mean", "A02_share_lt5ft", "A03_share_restricted", "A04_share_paint",
            "A05_share_midrange", "A06_share_corner3", "A07_share_abovebreak3", "A08_share_3pa",
            "A09_share_catch_action", "A10_share_selfcreate_action", "A11_share_layup_action",
            "A12_share_plain_jumpshot"]
FAMILY_B = ["B01_dist_t5", "B02_lt5ft_t5", "B03_restricted_t5", "B04_dist_trend",
            "B05_lt5ft_trend", "B06_3pa_trend"]
FAMILY_C = ["C01_assisted_share", "C02_assisted_share_3pt", "C03_assisted_share_2pt",
            "C04_assisted_share_t5", "C05_assisted_trend"]
FAMILY_D = ["D01_xefg_zone", "D02_xpps_zone", "D03_xefg_action", "D04_xefg_minus_own"]
FAMILY_E = ["E01_opp_dist_conceded", "E02_opp_lt5ft_conceded", "E03_opp_restricted_conceded",
            "E04_opp_xefg_conceded", "E05_opp_3pa_conceded", "E06_opp_assisted_conceded"]
FAMILY_F = ["F01_dist_x_oppdist", "F02_lt5ft_x_opplt5ft", "F03_xefg_x_oppxefg", "F04_3pa_x_opp3pa"]
FAMILY_G = ["G01_noise", "G02_ref_echo"]
CANDIDATES = FAMILY_A + FAMILY_B + FAMILY_C + FAMILY_D + FAMILY_E + FAMILY_F + FAMILY_G
FAMILY_OF = {}
for _fam, _lst in [("A_own_profile", FAMILY_A), ("B_form_trend", FAMILY_B), ("C_assisted", FAMILY_C),
                   ("D_quality_index", FAMILY_D), ("E_opp_conceded", FAMILY_E),
                   ("F_interaction", FAMILY_F), ("G_control", FAMILY_G)]:
    for _c in _lst:
        FAMILY_OF[_c] = _fam

# entity a candidate "belongs to" -- used to choose the entity_swap grouping
ENTITY_COLS = {}
for _c in FAMILY_A + FAMILY_B + FAMILY_C + FAMILY_D + FAMILY_F + ["G02_ref_echo"]:
    ENTITY_COLS[_c] = ["player_id", "season"]
for _c in FAMILY_E:
    ENTITY_COLS[_c] = ["opp_team_id", "season"]
ENTITY_COLS["G01_noise"] = ["player_id", "season"]

# interactions -> their own two main effects (D085's lesson)
INTERACTION_MAINS = {
    "F01_dist_x_oppdist": ["A01_dist_mean", "E01_opp_dist_conceded"],
    "F02_lt5ft_x_opplt5ft": ["A02_share_lt5ft", "E02_opp_lt5ft_conceded"],
    "F03_xefg_x_oppxefg": ["D01_xefg_zone", "E04_opp_xefg_conceded"],
    "F04_3pa_x_opp3pa": ["A08_share_3pa", "E05_opp_3pa_conceded"],
}

ZONES = ["Restricted Area", "In The Paint (Non-RA)", "Mid-Range", "Left Corner 3",
         "Right Corner 3", "Above the Break 3", "Backcourt"]

CATCH_ACTIONS_PREFIX = ("Cutting", "Alley Oop", "Putback", "Tip", "Dunk")
CATCH_ACTIONS_EXACT = ("Layup Shot", "Jump Shot")
SELFCREATE_PREFIX = ("Pullup", "Step Back", "Driving", "Turnaround", "Fadeaway", "Running",
                     "Floating")


def hdr(s):
    print("\n" + "=" * 100)
    print(s)
    print("=" * 100)


def safe_div(a, b):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(np.isfinite(b) & (b != 0), a / b, np.nan)


# =====================================================================================
# strictly-prior helpers.  .shift(1) ALWAYS PRECEDES .expanding()/.rolling().
# =====================================================================================
def prior_sum(df, keys, col):
    """Expanding sum of STRICTLY PRIOR values of `col` inside `keys`.  NaN before the first."""
    return df.groupby(keys, sort=False)[col].transform(lambda x: x.shift(1).expanding().sum())


def prior_sum_many(df, keys, cols):
    """Vectorised prior_sum over many columns at once (transform per column is slow at 60 cols)."""
    g = df.groupby(keys, sort=False)[list(cols)]
    return g.transform(lambda x: x.shift(1).expanding().sum())


def trail_sum_many(df, keys, cols, window):
    """Sum over the entity's `window` most recent STRICTLY PRIOR rows."""
    g = df.groupby(keys, sort=False)[list(cols)]
    return g.transform(lambda x: x.shift(1).rolling(window, min_periods=1).sum())


def prior_count(df, keys, col):
    return df.groupby(keys, sort=False)[col].transform(lambda x: x.shift(1).expanding().count())


def league_prior_mean(df, seasoncol, datecol, valcol):
    """Expanding league mean over rows strictly EARLIER IN THE SAME SEASON (date order).

    Cold-start fallback only.  Same construction D076/D081/D085 used.
    """
    fs = df.sort_values([seasoncol, datecol, "game_id"], kind="stable")
    cum = fs.groupby(seasoncol, sort=False)[valcol].transform(lambda x: x.shift(1).expanding().mean())
    return cum.reindex(df.index)


# =====================================================================================
# FAST INCREMENTAL R2 -- asserted against screenkit.delta_r2_plain in s01 before any result
# =====================================================================================
class BaseFit:
    """Precomputed residualiser for a fixed base design [1, base_cols...].

    dR2 of adding a candidate x is ((e . xt)^2 / (xt . xt)) / SST, with e = y residualised on the
    base and xt = x residualised on the base.  Algebraically identical to
    screenkit.delta_r2_plain(y, base, [base, x]) and ~40x faster, which is what makes
    117 cells x 2 nulls x 600 draws affordable.  D069 convention: SST about the UNWEIGHTED mean.
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

    def beta_sign(self, x):
        xt = self.resid_x(x)
        den = float(xt @ xt)
        if den <= 1e-12:
            return 0.0
        return float(np.sign(float(self.e @ xt)))


def mae(y, yhat):
    return float(np.mean(np.abs(np.asarray(y, float) - np.asarray(yhat, float))))
