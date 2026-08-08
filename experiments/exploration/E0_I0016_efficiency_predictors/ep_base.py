"""
E0_I0016 EFFICIENCY PREDICTORS -- shared loader, reference builder, fast dR2, null helpers.

WHAT THIS SCREEN IS.  E0 breadth screen for PRE-GAME observables that predict player scoring
    EFFICIENCY.  D081 localised the champion player model's points failure precisely at the
    per-minute efficiency step (points error ~3:1 efficiency over minutes; a perfect rate forecast
    cuts points MAE 58.5%).  D081 then ran 550 cells of GENERIC pre-game state against rate skill
    and cleared 0 of 330 rate cells family-wise.  This screen therefore avoids generic state
    entirely and reaches for basketball-specific mechanisms.

    E0 CHARACTER: fast, permissive, time-boxed, explicitly NON-CLAIMING.  Every output here is a
    LEAD, NEVER A RESULT, and may not be cited as evidence.

PARTITION (GRAPH_POLICY 13.2): seasons 2021-2024 ONLY.  Enforced by screenkit.assert_partition,
    a VALUE test on parsed dates and season-valued columns.  No regex/byte scan is used as a
    partition check anywhere in this screen -- that check has produced false hits three times in
    this program, once from a column merely NAMED with a season-like string.

INPUTS AND THEIR MANIFEST VERDICTS (screenkit.check_manifest, read from disk at call time):
    data/masters/master_player.parquet   asof_granularity "row"  -> USABLE_IF_FILTERED   [USED]
    data/masters/master_team.parquet     asof_granularity "row"  -> USABLE_IF_FILTERED   [USED]
    E0_I0014/analysis_frame.parquet      NO SIBLING MANIFEST     -> UNVERIFIABLE         [NOT USED]
    data/shotcharts/*.parquet            NO SIBLING MANIFEST     -> UNVERIFIABLE         [NOT USED]
    data/w1_truth/player_game_availability.csv, roster_asof.csv
                                         "artifact", fit_through_season 2026 -> UNUSABLE [NOT OPENED]
    data/zone_maps/*                     forbidden by the brief                          [NOT OPENED]
    master_player.pace / pace_per40 / estimated_pace are recorded corrupt (D081)          [NOT READ]

    Consequence worth stating plainly: because shotcharts carry no manifest, the shot-quality
    proxies in family E are BOX-SCORE SHADOWS (3PA share, paint-points share, blocked-shot rate),
    not true shot-quality measures.  Assisted-shot share, average shot distance and early-clock
    share are NOT SCREENED AT ALL by this screen.

REFERENCE (trap 2 -- retrospective baselines, five instances in this program).  Every reference and
    every candidate is built by sorting inside (season, entity) by date and applying .shift(1)
    BEFORE any .expanding().  Nothing here reads the current game or any later game, with three
    deliberately-flagged TIP-TIME exceptions in family C (C04, C05, C08) that read TODAY'S box
    membership.  See the TIME-WINDOW TABLE in NOTES.md, which names every constructed column.

R2 CONVENTION (D069): plain unweighted OLS R2, SST about the UNWEIGHTED mean.

NO MODEL FITTING.  The champion is never loaded and never retrained.  The only fitting anywhere in
    this screen is the two-column screening regression `y ~ 1 + reference + candidate`, whose
    in-sample increment is compared against a permutation null and NEVER against zero.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
KIT = os.path.join(ROOT, r"experiments\exploration\_screen_kit")
OUT = os.path.join(ROOT, r"experiments\exploration\E0_I0016_efficiency_predictors")
MP_PATH = os.path.join(ROOT, r"data\masters\master_player.parquet")
MT_PATH = os.path.join(ROOT, r"data\masters\master_team.parquet")

if KIT not in sys.path:
    sys.path.insert(0, KIT)
import screenkit as sk  # noqa: E402

SEED = 20260807
SEASONS = (2021, 2022, 2023, 2024)
MIN_PRIOR_APPEARANCES = 3          # permissive E0 floor; the decision stratum (>=8) is a follow-up
N_DRAWS = 600

os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.dont_write_bytecode = True


def hdr(s):
    print("\n" + "=" * 100)
    print(s)
    print("=" * 100)


# =====================================================================================
# strictly-prior expanding helpers.  .shift(1) ALWAYS PRECEDES .expanding().
# =====================================================================================
def prior_sum(df, keys, col):
    """Expanding sum of STRICTLY PRIOR values of `col` inside `keys`.  NaN before the first."""
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
    """Expanding league mean over rows strictly EARLIER IN THE SAME SEASON (date order).

    Cold-start fallback only.  Same construction D076/D081 used.
    """
    fs = df.sort_values([seasoncol, datecol, "game_id"], kind="stable")
    cum = fs.groupby(seasoncol, sort=False)[valcol].transform(
        lambda x: x.shift(1).expanding().mean())
    return cum.reindex(df.index)


# =====================================================================================
# FAST INCREMENTAL R2 -- verified against screenkit.delta_r2_plain in s01
# =====================================================================================
class BaseFit:
    """Precomputed residualiser for the fixed base design [1, reference].

    dR2 of adding a candidate x to the base is
        dR2 = ((e . xt)^2 / (xt . xt)) / SST
    where e is y residualised on the base and xt is x residualised on the base.  This is
    algebraically identical to screenkit.delta_r2_plain(y, base, [base, x]) and is ~40x faster,
    which is what makes 264 cells x 2 valid nulls x 600 draws affordable.  s01 asserts the identity
    on real data to 1e-10 against the kit before any screening result is produced.
    """

    def __init__(self, y, ref):
        y = np.asarray(y, float)
        ref = np.asarray(ref, float)
        self.n = len(y)
        X = np.column_stack([np.ones(self.n), ref])
        self.X = X
        self.XtXi = np.linalg.pinv(X.T @ X)
        self.y = y
        self.e = y - X @ (self.XtXi @ (X.T @ y))
        self.sst = float(((y - y.mean()) ** 2).sum())
        self.ref = ref

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

    def fitted_with(self, x):
        """In-sample fitted values of y ~ 1 + ref + x.  Screening regression, not a model."""
        x = np.asarray(x, float)
        Xf = np.column_stack([self.X, x])
        beta, *_ = np.linalg.lstsq(Xf, self.y, rcond=None)
        return Xf @ beta


def mae(y, yhat):
    return float(np.mean(np.abs(np.asarray(y, float) - np.asarray(yhat, float))))


# =====================================================================================
# entity-season BETWEEN / WITHIN decomposition
# =====================================================================================
ENTITY = {}
for _c in ["A01_opp_efg_allowed", "A02_opp_ts_allowed", "A03_opp_paintpts_allowed", "A04_opp_blk",
           "A05_opp_fg3pct_allowed", "A06_opp_fg3a_share_allowed", "A07_opp_ftrate_allowed",
           "A08_opp_pf", "A09_opp_stl", "A10_opp_defrtg", "A11_opp_fastbreak_allowed",
           "A12_opp_2ndchance_allowed", "B04_matchup_ftrate", "B05_matchup_fouldraw",
           "D02_opp_poss_per40", "E04_3pt_vs_opp_perim", "E05_paint_vs_opp_rim"]:
    ENTITY[_c] = ("opp_team_season", ["opp_team_id", "season"])
for _c in ["C01_tm_usage_hhi", "C02_tm_ast_per_game", "C03_tm_ast_rate",
           "C04_teammate_usg_present", "C05_top_usg_teammate_out",
           "C06_top_usg_teammate_out_lastgame", "C07_pl_usage_rank", "C08_vacated_usg",
           "D01_tm_poss_per40", "D03_pace_sum", "D05_transition_x_pace", "D06_tm_fastbreak_pts"]:
    ENTITY[_c] = ("team_season", ["team_id", "season"])
for _c in ["B01_pl_ftrate", "B02_pl_ftpct", "B03_pl_fouls_drawn_per36", "B06_pl_ftpts_per36",
           "D04_pl_fastbreak_share", "E01_pl_fg3a_share", "E02_pl_paintpts_share",
           "E03_pl_blocked_rate", "E06_pl_efg_prior", "E07_pl_2ndchance_share",
           "F01_b2b_x_fg3a_share", "F02_b2b_x_ftrate", "F03_minutes_load_7d",
           "F04_load_x_fg3a_share", "G01_noise"]:
    ENTITY[_c] = ("player_season", ["player_id", "season"])

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


class EntitySwap:
    """N2 -- reassign whole entity-season SERIES to other entity-seasons inside the same season.

    *** DECLARED KIT GAP.  This is NOT a screenkit function. ***  screenkit ships only
    `scheme=SCHEME_BETWEEN`, which REQUIRES the feature to be constant within groups, and forcing
    it onto a within-varying feature with `allow_nonconstant=True` is what the kit itself calls a p
    "manufactured rather than measured", because the draws lose 100% of the within-group variation
    that the real statistic keeps.  Every candidate in this screen is an expanding prior, so every
    candidate is within-varying, so the between-entity question -- which is the WHOLE question for
    an opponent-defence family -- has no valid scheme in the kit.

    Exchangeability tested: the ENTITY LABELS.  Under H0 that which entity a row is attached to
    carries no information about the outcome beyond the reference, relabelling entities leaves the
    joint distribution unchanged.

    Construction.  Rows are grouped by entity-season and ordered by date within it.  Per draw,
    entity-seasons are permuted inside each season; an entity of length n_e receives its partner's
    values at PROPORTIONAL positions round(k/(n_e-1) * (n_e'-1)), so position 0 maps to position 0
    and the last to the last.  Series length and within-season temporal shape are preserved --
    which matters, because an early-season expanding prior is mechanically noisier than a
    late-season one and a null that scrambled that would not be comparing like with like.

    WHAT IT DOES NOT DO.  It does not preserve the exact marginal distribution when partners differ
    in length (values are resampled with repetition under the proportional map); it does not
    preserve cross-entity correlation structure; and it is a randomisation of labels, not a
    bootstrap, so it says nothing about sampling variability of the effect size.
    """

    def __init__(self, df, entity_cols, date_col="game_date", season_col="season"):
        codes = sk._group_codes(df, entity_cols)
        order = np.lexsort((df["game_id"].to_numpy(), df[date_col].to_numpy(), codes))
        self.n = len(df)
        self.groups = []
        oc = codes[order]
        starts = np.flatnonzero(np.r_[True, oc[1:] != oc[:-1]])
        ends = np.r_[starts[1:], len(oc)]
        seasons = df[season_col].to_numpy()
        for s, e in zip(starts, ends):
            idx = order[s:e]
            self.groups.append((int(seasons[idx[0]]), idx))
        self.by_season = {}
        for gi, (ssn, _) in enumerate(self.groups):
            self.by_season.setdefault(ssn, []).append(gi)
        self.n_groups = len(self.groups)

    def draw(self, x, rng):
        out = np.empty(self.n, dtype=float)
        for ssn, gis in self.by_season.items():
            perm = rng.permutation(len(gis))
            for a, b in zip(gis, [gis[p] for p in perm]):
                ia, ib = self.groups[a][1], self.groups[b][1]
                na, nb = len(ia), len(ib)
                if na == 1 or nb == 1:
                    src = np.zeros(na, dtype=np.int64)
                else:
                    src = np.rint(np.arange(na) / (na - 1) * (nb - 1)).astype(np.int64)
                out[ia] = x[ib[src]]
        return out


def entity_swap_null(bf, x, swapper, n_draws, seed):
    """Permutation null from `EntitySwap`.  p is the add-one estimator, so it is never 0."""
    rng = np.random.default_rng(seed)
    real = bf.dr2(x)
    draws = np.empty(n_draws, float)
    for i in range(n_draws):
        draws[i] = bf.dr2(swapper.draw(x, rng))
    n_ext = int((draws >= real).sum())
    return {"real": float(real), "draws": draws, "mean": float(draws.mean()),
            "sd": float(draws.std(ddof=1)), "p": float((1.0 + n_ext) / (n_draws + 1.0)),
            "n_groups": swapper.n_groups}


def decompose(df, col, entity_cols):
    """Split a feature into an entity-season MEAN (constant within entity-season) and the
    mean-free remainder.

    WHY.  screenkit's own guidance is explicit that scheme="between" applied to a feature that
    varies WITHIN its groups annihilates 100% of the within-group variation and yields a p that is
    "manufactured rather than measured", while scheme="within" is the literal identity for a
    feature that is constant within groups.  Every candidate here is an expanding prior, so it is
    neither: it varies within its entity-season AND carries most of its signal at the entity-season
    level.  Screening the two components separately gives each one a scheme for which it is a VALID
    null, and both components are basketball-meaningful:
        __between = the entity's season-level level     (e.g. how good this defence is)
        __within  = the entity's within-season deviation (e.g. what form it is in right now)
    """
    g = df.groupby(entity_cols, sort=False)[col]
    m = g.transform("mean")
    return m, df[col] - m
