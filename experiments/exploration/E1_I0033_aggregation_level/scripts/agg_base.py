"""E1_I0033 AGGREGATION LEVEL -- local machinery.

THE QUESTION.  The user argues that the level at which you model is a design choice that
determines what is knowable, not a neutral implementation detail.  This screen tests it by
forecasting the SAME response -- team points per game -- top-down (a team-level arm) and
bottom-up (summing the champion's player forecasts), on identical rows, walk-forward,
strictly prior-only.

INPUTS AND THEIR PROVENANCE
  experiments/cbs_v12_team_oof_v2/attempt_001/   the TEAM arm.  cbs_v12_team_oof/1 is marked
      PROVISIONAL_SUPERSEDED (dirty producing tree, fail-open resume) and is NOT used.  /2
      refuses a dirty tree, digests producing sources, validates artifacts on resume.
      2021 fold: degenerate:true, model_was_fitted:false, declared-constant only -> EXCLUDED,
      exactly as D076 excluded the player arm's 2021 fold.
  experiments/cbs_v15_player_oof_v5/attempt_001/ the CHAMPION player arm (D076 names it).
  experiments/prediction_contract_v4/player_game.parquet  supplies candidate_at_cutoff, the
      PRE-GAME-KNOWABLE ROSTER, and the row_uid <-> (game_id, team_id, player_id) map.
  experiments/prediction_contract_v4/team_game.parquet    the row_uid <-> (game_id, team_id) map.
  data/masters/master_team.parquet   OUTCOMES ONLY (team points and box channels).
  data/masters/master_player.parquet OUTCOMES and strictly-prior player history.

THE ROSTER PROBLEM, HANDLED EXPLICITLY.  Summing only the players who actually appeared uses
realised information.  Three constructions are carried and labelled:
  B1  AVAILABILITY-WEIGHTED  sum over candidate_at_cutoff rows of p_active_hat * pts_hat.
      PRE-GAME KNOWABLE.  This is the headline bottom-up arm.
  B2  UNWEIGHTED CANDIDATE   sum over candidate_at_cutoff rows of pts_hat.  Pre-game knowable
      and deliberately naive; it must overshoot, and by how much is informative.
  B3  ORACLE ROSTER          sum over rows with realised appeared==1 of pts_hat.  USES THE
      REALISED ROSTER.  ORACLE.  DIAGNOSTIC ONLY.  EXCLUDED FROM EVERY HEADLINE.

THE NULL.  Both arms forecast the SAME row, so the comparison is PAIRED.  The correct-level
null is a sign flip on the per-row loss difference, blocked at the level the arms can differ
-- team-season -- since a team's whole forecast series shares its fitted state.  The
within-player cyclic shift is DEGENERATE here (D108): every candidate in this screen varies
BETWEEN entities or at team-game level, which a rotation preserves.  Power is VERIFIED BY
INJECTION for every null before any verdict is taken from it.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
KIT = os.path.join(ROOT, "experiments", "exploration", "_screen_kit")
LADDER = os.path.join(ROOT, "experiments", "exploration", "E1_I0027_reference_ladder")
OUT = os.path.join(ROOT, "experiments", "exploration", "E1_I0033_aggregation_level")

sys.dont_write_bytecode = True
for _p in (KIT, LADDER):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import screenkit as sk  # noqa: E402

SEED = 20260809
EXPLORATION_SEASONS = (2021, 2022, 2023, 2024)
SCORED_SEASONS = (2022, 2023, 2024)   # 2021 folds are degenerate in BOTH arms

TEAM_ARM = os.path.join(ROOT, "experiments", "cbs_v12_team_oof_v2", "attempt_001")
PLAYER_ARM = os.path.join(ROOT, "experiments", "cbs_v15_player_oof_v5", "attempt_001")
CV4 = os.path.join(ROOT, "experiments", "prediction_contract_v4")
MASTER_TEAM = os.path.join(ROOT, "data", "masters", "master_team.parquet")
MASTER_PLAYER = os.path.join(ROOT, "data", "masters", "master_player.parquet")


def hdr(s):
    print("\n" + "=" * 100)
    print(s)
    print("=" * 100)


def sha256_text(t):
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


def jsonable(o):
    if isinstance(o, dict):
        return {str(k): jsonable(v) for k, v in o.items() if k != "draws"}
    if isinstance(o, (list, tuple)):
        return [jsonable(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, np.ndarray):
        return [jsonable(v) for v in o.tolist()]
    if isinstance(o, pd.Timestamp):
        return str(o.date())
    if pd.isna(o) if np.isscalar(o) and not isinstance(o, str) else False:
        return None
    return o


# ----------------------------------------------------------------------------- loaders
def load_arm(dirpath, target, seasons=EXPLORATION_SEASONS):
    fr = []
    for s in seasons:
        p = os.path.join(dirpath, "predictions__%s__%d.parquet" % (target, s))
        d = pd.read_parquet(p)
        d["season"] = s
        fr.append(d)
    return pd.concat(fr, ignore_index=True)


def load_team_master(seasons=EXPLORATION_SEASONS):
    t = pd.read_parquet(MASTER_TEAM)
    t = t[t["season"].isin(seasons)].copy()
    t["game_date"] = pd.to_datetime(t["game_date"])
    t["is_home"] = t["is_home"].astype(int)
    for c in ["fgm", "fga", "fg3m", "fg3a", "ftm", "fta", "oreb", "dreb", "reb", "ast",
              "stl", "blk", "tov", "pf", "pts", "minutes", "fouls_drawn"]:
        t[c] = pd.to_numeric(t[c], errors="coerce").astype(float)
    t["fg2m"] = t["fgm"] - t["fg3m"]
    t["fg2a"] = t["fga"] - t["fg3a"]
    return t.sort_values(["season", "team_id", "game_date", "game_id"],
                         kind="stable").reset_index(drop=True)


def load_player_master(seasons=EXPLORATION_SEASONS):
    p = pd.read_parquet(MASTER_PLAYER)
    p = p[p["season"].isin(seasons)].copy()
    p["game_date"] = pd.to_datetime(p["game_date"])
    p["is_home"] = p["is_home"].astype(int)
    for c in ["fgm", "fga", "fg3m", "fg3a", "ftm", "fta", "oreb", "dreb", "reb", "ast",
              "stl", "blk", "tov", "pf", "pts", "minutes"]:
        p[c] = pd.to_numeric(p[c], errors="coerce").astype(float)
    p["appeared"] = (p["minutes"].fillna(0.0) > 0.0).astype(int)
    p["minutes"] = p["minutes"].fillna(0.0)
    for c in ["fgm", "fga", "fg3m", "fg3a", "ftm", "fta", "oreb", "dreb", "reb", "ast",
              "stl", "blk", "tov", "pts"]:
        p[c] = p[c].fillna(0.0)
    return p.sort_values(["season", "player_id", "game_date", "game_id"],
                         kind="stable").reset_index(drop=True)


# ----------------------------------------------------------------------------- metrics
def mae(y, yhat):
    y = np.asarray(y, float); yhat = np.asarray(yhat, float)
    return float(np.mean(np.abs(y - yhat)))


def r2_common(y, yhat, sst):
    """R2 of a GIVEN forecast against an EXPLICIT denominator (D101 rule D3).

    `sst` is passed in rather than computed, so no code path can accidentally use a subset's
    own SST.  Nothing is refit at scoring time.
    """
    y = np.asarray(y, float); yhat = np.asarray(yhat, float)
    return float(1.0 - np.sum((y - yhat) ** 2) / sst)


def sst_of(y):
    y = np.asarray(y, float)
    return float(np.sum((y - y.mean()) ** 2))


def skill_mae(y, yhat, yref):
    return float(1.0 - mae(y, yhat) / mae(y, yref))


# ----------------------------------------------------------------------------- nulls
def paired_signflip_block(loss_a, loss_b, block_codes, n_draws, seed,
                          alternative="two_sided"):
    """PAIRED BLOCK SIGN-FLIP on the per-row loss difference.

    Statistic: mean(loss_b - loss_a), i.e. how much better arm A is than arm B.  Under the null
    that the two arms are exchangeable, the sign of a whole BLOCK's contribution may be flipped.
    Blocks are team-seasons: a team's whole forecast series shares its fitted state in both arms,
    so rows within a team-season are not independent and a ROW-level flip would be
    anticonservative in the usual way.

    Returns null_mean and null_sd beside p, as D103 ruling 2 requires.
    """
    d = np.asarray(loss_b, float) - np.asarray(loss_a, float)
    codes = np.asarray(block_codes)
    ok = np.isfinite(d)
    d = d[ok]; codes = codes[ok]
    uniq, inv = np.unique(codes, return_inverse=True)
    nb = len(uniq)
    n = len(d)
    real = float(d.mean())
    # block sums, so a flip negates the whole block at once
    bs = np.bincount(inv, weights=d, minlength=nb)
    rng = np.random.default_rng(seed)
    signs = rng.choice(np.array([-1.0, 1.0]), size=(n_draws, nb))
    draws = (signs * bs[None, :]).sum(axis=1) / n
    if alternative == "two_sided":
        hit = int((np.abs(draws) >= abs(real) - 1e-15).sum())
    elif alternative == "greater":
        hit = int((draws >= real - 1e-15).sum())
    else:
        hit = int((draws <= real + 1e-15).sum())
    sd = float(draws.std(ddof=1))
    return {"real": real, "n_rows": int(n), "n_blocks": int(nb), "n_draws": int(n_draws),
            "null_mean": float(draws.mean()), "null_sd": sd,
            "p": float((1.0 + hit) / (n_draws + 1.0)),
            "alternative": alternative, "draws": draws}


def paired_signflip_row(loss_a, loss_b, n_draws, seed, alternative="two_sided"):
    """THE NAIVE ROW-LEVEL CONTRAST.  Computed only to publish the inflation factor.
    NEVER carries a verdict."""
    d = np.asarray(loss_b, float) - np.asarray(loss_a, float)
    d = d[np.isfinite(d)]
    n = len(d)
    real = float(d.mean())
    rng = np.random.default_rng(seed)
    signs = rng.choice(np.array([-1.0, 1.0]), size=(n_draws, n))
    draws = (signs * d[None, :]).mean(axis=1)
    if alternative == "two_sided":
        hit = int((np.abs(draws) >= abs(real) - 1e-15).sum())
    else:
        hit = int((draws >= real - 1e-15).sum())
    return {"real": real, "n_rows": int(n), "n_draws": int(n_draws),
            "null_mean": float(draws.mean()), "null_sd": float(draws.std(ddof=1)),
            "p_row_level_NAIVE": float((1.0 + hit) / (n_draws + 1.0)), "draws": draws}


def game_signflip(diff, n_draws, seed, alternative="two_sided"):
    """Exact per-game sign flip for a WITHIN-GAME PAIRED contrast (home minus away).
    CREDIT: E1_I0030_home_advantage_accounting/ha_base.paired_game_signflip (D104)."""
    d = np.asarray(diff, float)
    d = d[np.isfinite(d)]
    n = len(d)
    real = float(d.mean())
    rng = np.random.default_rng(seed)
    signs = rng.choice(np.array([-1.0, 1.0]), size=(n_draws, n))
    draws = (signs * d[None, :]).mean(axis=1)
    if alternative == "two_sided":
        hit = int((np.abs(draws) >= abs(real) - 1e-15).sum())
    elif alternative == "greater":
        hit = int((draws >= real - 1e-15).sum())
    else:
        hit = int((draws <= real + 1e-15).sum())
    return {"real": real, "n_games": int(n), "n_draws": int(n_draws),
            "null_mean": float(draws.mean()), "null_sd": float(draws.std(ddof=1)),
            "p": float((1.0 + hit) / (n_draws + 1.0)),
            "alternative": alternative, "draws": draws}


# ----------------------------------------------------------------------------- prior-only history
def prior_prefix_stat(frame, entity_cols, num_col, den_col=None, half_life=None,
                      date_col="game_date"):
    """STRICTLY PRIOR expanding or EWMA statistic over an entity's earlier games.

    Rows are sorted by entity then date; for row i the statistic uses rows [start, i) of that
    entity's block ONLY.  Row i itself is never included -- that is the whole point, and it is
    asserted downstream by checking that the first row of every block is NaN.

    half_life=None gives the plain expanding mean.  Otherwise weights are 0.5 ** (age/half_life)
    where age is measured in GAMES BACK (1 = immediately previous), which is the same convention
    E1_I0027_reference_ladder uses.
    """
    f = frame.sort_values(list(entity_cols) + [date_col, "game_id"],
                          kind="stable").reset_index(drop=True)
    num = pd.to_numeric(f[num_col], errors="coerce").to_numpy(float)
    den = (np.ones(len(f)) if den_col is None
           else pd.to_numeric(f[den_col], errors="coerce").to_numpy(float))
    codes = f.groupby(list(entity_cols), sort=False).ngroup().to_numpy()
    change = np.flatnonzero(np.r_[True, codes[1:] != codes[:-1]])
    ns = np.diff(np.r_[change, len(codes)])
    out = np.full(len(f), np.nan)
    cnt = np.zeros(len(f))
    for a, n in zip(change, ns):
        sn = 0.0; sd = 0.0; c = 0
        if half_life is None:
            for j in range(n):
                out[a + j] = (sn / sd) if (c > 0 and sd > 0) else np.nan
                cnt[a + j] = c
                v = num[a + j]; w = den[a + j]
                if np.isfinite(v) and np.isfinite(w):
                    sn += v; sd += w; c += 1
        else:
            decay = 0.5 ** (1.0 / float(half_life))
            for j in range(n):
                out[a + j] = (sn / sd) if (c > 0 and sd > 0) else np.nan
                cnt[a + j] = c
                sn *= decay; sd *= decay
                v = num[a + j]; w = den[a + j]
                if np.isfinite(v) and np.isfinite(w):
                    sn += v; sd += w; c += 1
    f["_stat"] = out
    f["_nprior"] = cnt
    return f
