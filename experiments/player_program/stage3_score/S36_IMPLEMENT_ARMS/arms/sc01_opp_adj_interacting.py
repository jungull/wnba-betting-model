#!/usr/bin/env python3
"""SC01_OPP_ADJ_INTERACTING -- opponent-adjusted interacting strength. 3 elements.

Epistemic status: IMPLEMENTATION. Unit/synthetic/identity/schema tests only; no comparative
historical performance is revealed.

FROZEN FORMULA (SPEC_V2 /arms/0, arm_block_sha256 2bdf2678...):

  cutoff-refit rating model on strictly-prior two-season-window team-game rows:
      pts_ij = mu + off_i - def_j + eta*home_ij + eps
  ridge on (off, def), sum-to-zero identification, lambda per fold from the pinned grid
  {2, 8, 32, 128} by the pinned train-tail rule. Element heads (train-OLS / train-IRLS):
      E2: y = a + b*C_margin + c*[(off_H - def_A) - (off_A - def_H)]
      E1: y = a + b*C_total  + c*[(off_H - def_A) + (off_A - def_H)]
      E3: logit(p) = a + b*C_margin + c*[strength margin]

PINNED, NOT CHOSEN HERE: two-season observation window; sum-to-zero constraint; grid
{2,8,32,128}; train-tail 80/20 selection rule; cold start off = def = 0 for a team with zero
window rows; no row is ever dropped.

CUTOFF SEMANTICS. This arm's lineage says "ratings consume only resolved-universe rows with
game_date STRICTLY EARLIER than the predicted game" -- a DATE cutoff, not the (date, game_id)
row cutoff the per-team clocks use. That is the card's own wording and it is honoured literally:
same-day games all see the same ratings. One consequence worth stating plainly, because it is a
property of the frozen design and not of this implementation: a same-day earlier game cannot
inform a same-day later game's ratings.

IDENTIFICATION. Ridge shrinks (off, def) toward 0 and `mu` is free, so the fitted effects are
already near-centred; the sum-to-zero constraint is then imposed exactly by re-centring off and
def separately over the window's ACTIVE teams and absorbing both shifts into `mu`. That is an
exact reparameterisation of the same fitted surface -- it moves no residual -- and it makes the
card's "level absorbed by mu" literally true rather than approximately true.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runner"))

from _head import linear_head, select_lambda_train_tail  # noqa: E402
from estimators import fit_ols  # noqa: E402
from runner_interface import ElementSpec  # noqa: E402

ARM_ID = "SC01_OPP_ADJ_INTERACTING"
FORMULA = ("cutoff-refit ridge rating model pts_ij = mu + off_i - def_j + eta*home_ij + eps on "
           "strictly-prior two-season-window resolved-universe rows; heads add one recombined "
           "strength term to the null-granted composite")
WINDOW_SEASONS = 2
LAMBDA_GRID = (2.0, 8.0, 32.0, 128.0)
COLD_START = "team with zero window rows (expansion debut): off = def = 0; no row is ever dropped"
EARLY_STRATUM_PREDICATE = "max(n_H, n_A) <= 12"        # A3 pinned reading
EARLY_STRATUM_POOLED = 472                              # A3 pinned count
EARLY_STRATUM_PER_TEST_SEASON = {2022: 75, 2023: 76, 2024: 74, 2025: 81, 2026: 92}


def _fit_ratings_at_cutoff(prior: pd.DataFrame, teams: np.ndarray, lam: float) -> dict:
    """One ridge rating fit on the rows strictly prior to a cutoff date."""
    T = len(teams)
    pos = {t: i for i, t in enumerate(teams)}
    n = len(prior)
    X = np.zeros((n, 2 + 2 * T))
    X[:, 0] = 1.0                                        # mu
    X[:, 1] = prior["is_home"].to_numpy(dtype=float)      # eta
    for r, (ti, tj) in enumerate(zip(prior["team_id"].to_numpy(), prior["opp_team_id"].to_numpy())):
        X[r, 2 + pos[ti]] = 1.0                           # off_i
        X[r, 2 + T + pos[tj]] = -1.0                      # -def_j
    y = prior["pts"].to_numpy(dtype=float)
    penalise = np.zeros(2 + 2 * T, dtype=bool)
    penalise[2:] = True                                   # ridge on (off, def) ONLY
    fit = fit_ols(X, y, columns=("mu", "eta"), ridge=lam, penalise=penalise)
    mu, eta = fit.coef[0], fit.coef[1]
    off = fit.coef[2:2 + T].copy()
    dfn = fit.coef[2 + T:].copy()
    # exact sum-to-zero reparameterisation; the surface is unchanged
    mu = mu + off.mean() - dfn.mean()
    off = off - off.mean()
    dfn = dfn - dfn.mean()
    return {"mu": float(mu), "eta": float(eta),
            "off": dict(zip(teams.tolist(), off.tolist())),
            "def": dict(zip(teams.tolist(), dfn.tolist()))}


def ratings_by_cutoff(universe, lam: float) -> pd.DataFrame:
    """(off_H - def_A) and (off_A - def_H) for every game, at that game's date cutoff."""
    tr = universe.team_rows
    games = universe.games
    dates = np.sort(games["game_date"].unique())
    seasons = {d: int(games.loc[games["game_date"] == d, "season"].iloc[0]) for d in dates}

    per_date = {}
    for d in dates:
        s = seasons[d]
        prior = tr[(tr["game_date"] < d) & (tr["season"] >= s - (WINDOW_SEASONS - 1))]
        if len(prior) < 4:
            per_date[d] = None
            continue
        teams = np.unique(np.concatenate([prior["team_id"].to_numpy(),
                                          prior["opp_team_id"].to_numpy()]))
        per_date[d] = _fit_ratings_at_cutoff(prior, teams, lam)

    oh, da, oa, dh = [], [], [], []
    for d, h, a in zip(games["game_date"], games["home_team_id"], games["away_team_id"]):
        r = per_date[d]
        if r is None:
            oh.append(0.0); da.append(0.0); oa.append(0.0); dh.append(0.0)
            continue
        oh.append(r["off"].get(h, 0.0)); dh.append(r["def"].get(h, 0.0))
        oa.append(r["off"].get(a, 0.0)); da.append(r["def"].get(a, 0.0))
    oh, da, oa, dh = map(np.asarray, (oh, da, oa, dh))
    return pd.DataFrame({"game_id": games["game_id"].to_numpy(),
                         "strength_margin_interacting": (oh - da) - (oa - dh),
                         "strength_total_interacting": (oh - da) + (oa - dh)})


def _strength(universe, fold, estimand: str, cache: dict) -> tuple[np.ndarray, dict]:
    """Lambda is selected once per fold on the fold's TRAINING clusters by the pinned train-tail
    rule; the selected ratings column is then materialised for every row of the universe."""
    key = ("lambda", fold["fold_id"], estimand)
    col = ("strength_total_interacting" if estimand == "E1_GAME_TOTAL"
           else "strength_margin_interacting")
    tgt = universe.games[estimand].to_numpy(dtype=float)
    C = universe.games["C_total" if estimand == "E1_GAME_TOTAL" else "C_margin"].to_numpy(float)

    def fit_and_score(lam, inner, tail):
        x = cache.setdefault(lam, ratings_by_cutoff(universe, lam))[col].to_numpy(float)
        X = np.column_stack([np.ones(len(x)), C, x])
        f = fit_ols(X[inner], tgt[inner])
        return float(np.mean(np.abs(tgt[tail] - X[tail] @ f.coef)))

    if key not in cache:
        cache[key] = select_lambda_train_tail(fold["train_idx"], LAMBDA_GRID, fit_and_score)
    sel = cache[key]
    x = cache.setdefault(sel["selected"], ratings_by_cutoff(universe, sel["selected"]))[
        col].to_numpy(float)
    return x, {"lambda_selection": sel, "ratings_column": col,
               "cutoff_semantics": "strictly earlier game_date (the card's own wording)",
               "identification": "exact sum-to-zero reparameterisation, level absorbed by mu",
               "cold_start": COLD_START}


def _build(estimand: str, term: str):
    def build(universe, fold, cache=None):
        cache = {} if cache is None else cache
        x, fc = _strength(universe, fold, estimand, cache)
        return linear_head(universe, estimand, {term: x}, fold_constants=fc)
    return build


KILLS_ARM = (
    f"early-season stratum failure: Delta-MAE(E2) vs K0 <= 0 in the early stratum, pinned to ONE "
    f"predicate - BOTH teams at most 12 same-season strictly-prior completed games "
    f"({EARLY_STRATUM_PREDICATE}; measured stratum {EARLY_STRATUM_POOLED} pooled / "
    f"75/76/74/81/92 per test season)",
    "shrinkage collapse: the pinned selection rule drives lambda to the grid maximum in >= 4 of 5 "
    "folds",
    "side-gain cancellation: per-side MAE improves but game-level Delta <= 0 with the covariance "
    "receipt showing side gains cancelling",
)
RECEIPTS = ("early_stratum_delta_table", "per_fold_ridge_path_table", "section5_covariance",
            "R-A1-EXCEPTIONS")

ELEMENTS = [
    ElementSpec(
        element_id="SC01_OPP_ADJ_INTERACTING::E2_FINAL_MARGIN_HOME", arm_id=ARM_ID,
        estimand="E2_FINAL_MARGIN_HOME", primary_metric="mae", arm_kind="substantive_feature",
        family_primary="FAM_S2_OPP_INTERACTION",
        card_sha256="2cce2b9d485937f27dd7037e63e3d32e7ce3d064221e33bb01385f7e7ce47718",
        build=_build("E2_FINAL_MARGIN_HOME", "strength_margin_interacting"),
        kill_conditions=KILLS_ARM, mandatory_receipts=RECEIPTS,
        notes=("SECTION-5 COVARIANCE OBLIGATION is BINDING: per-side residual variances, "
               "home/away residual covariance and corr(e_home, e_away) are first-class receipted "
               "sealed outputs",)),
    ElementSpec(
        element_id="SC01_OPP_ADJ_INTERACTING::E3_HOME_WIN_PROB", arm_id=ARM_ID,
        estimand="E3_HOME_WIN_PROB", primary_metric="brier_raw_model_probability",
        arm_kind="substantive_feature", family_primary="FAM_S2_OPP_INTERACTION",
        card_sha256="580c306e8cdb896e5f278f0001fae38bc2fd26ad9f2554c2fe855bbb93dfa9da",
        build=_build("E3_HOME_WIN_PROB", "strength_margin_interacting"),
        kill_conditions=KILLS_ARM, mandatory_receipts=RECEIPTS + ("R_SC08_FLOOR",),
        notes=("R_SC08_FLOOR is registered here as a NON-GATING agreement receipt (O5)",)),
    ElementSpec(
        element_id="SC01_OPP_ADJ_INTERACTING::E1_GAME_TOTAL", arm_id=ARM_ID,
        estimand="E1_GAME_TOTAL", primary_metric="mae", arm_kind="substantive_feature",
        family_primary="FAM_S2_OPP_INTERACTION",
        card_sha256="4b74bf2b00606bcc194bb376476942b87f937b66ffc765f811114fdebbdf4c14",
        build=_build("E1_GAME_TOTAL", "strength_total_interacting"),
        kill_conditions=KILLS_ARM, mandatory_receipts=RECEIPTS),
]
