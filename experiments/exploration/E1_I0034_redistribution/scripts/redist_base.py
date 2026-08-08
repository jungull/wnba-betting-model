"""E1_I0034 REDISTRIBUTION -- local machinery.

THE QUESTION.  E1_I0033 (D111) established that when a pre-game top-3 player is absent the TEAM
TOTAL barely moves: beta = +0.0284, 95% CI [-0.0569, +0.1137], and an ORACLE absence indicator
buys the team points forecast -0.00004 MAE against a floor of 0.00584.  Substitution is
essentially complete AT THE TEAM LEVEL.  Its closing observation is this screen's question:
the team scores the same, but DIFFERENT PEOPLE SCORE THEM.  Where does the absent player's
minutes / shot attempts / points go, and is that redistribution forecastable pre-game?

LEVEL DECLARATION (D111 ruling 1).  Everything here is measured at the REMAINING-PLAYER-GAME
level, nested in team-games.  That is the level at which the candidate (a beneficiary share)
varies, and it is therefore also the level the null must match (D108 ruling 4).

CONDITIONING DECLARED (D091 ruling 3 pattern).  The absence indicator is REALISED.  The two
pre-game injury sources in this repo -- data/injury_capture/injury_log.csv and
data/injury_history/injury_history.csv -- BOTH return manifest_present:false / UNVERIFIABLE from
screenkit.check_manifest, and UNVERIFIABLE is not a pass, so neither may back a number here.
Every forecast comparison in this screen is therefore an ORACLE-ON-ABSENCE CEILING, labelled as
such in its own cell name, exactly as E1_I0033 labelled its team-level equivalent.

INPUTS AND PROVENANCE  (identical path to E1_I0033/scripts/agg_base.py, deliberately, so the
anchors reproduce on bytes)
  data/masters/master_player.parquet        row granularity, USABLE_IF_FILTERED
  data/masters/master_team.parquet          row granularity, USABLE_IF_FILTERED
  experiments/prediction_contract_v4/*      row granularity, USABLE_IF_FILTERED
  experiments/cbs_v15_player_oof_v5/attempt_001   the CHAMPION player arm (D076 names it)
  data/reference/player_bios.csv            position_raw / draft_number, for cell P07
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
OUT = os.path.join(ROOT, "experiments", "exploration", "E1_I0034_redistribution")

sys.dont_write_bytecode = True
for _p in (KIT, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import screenkit as sk  # noqa: E402

SEED = 20260814
EXPLORATION_SEASONS = (2021, 2022, 2023, 2024)
SCORED_SEASONS = (2022, 2023, 2024)   # 2021 fold is declared degenerate in the champion arm

PLAYER_ARM = os.path.join(ROOT, "experiments", "cbs_v15_player_oof_v5", "attempt_001")
CV4 = os.path.join(ROOT, "experiments", "prediction_contract_v4")
MASTER_TEAM = os.path.join(ROOT, "data", "masters", "master_team.parquet")
MASTER_PLAYER = os.path.join(ROOT, "data", "masters", "master_player.parquet")
BIOS = os.path.join(ROOT, "data", "reference", "player_bios.csv")

# ---- EXPLICIT COLUMN ALLOWLISTS.  NO NAME-BASED / SUBSTRING SELECTION ANYWHERE IN THIS SCREEN.
# Five findings in this programme died to substring matching.  Every column set below is written
# out in full, resolved against the frame, printed, and its length asserted.
CHANNELS = ("minutes", "fga", "pts")           # the three redistributed quantities
CHANNEL_N = 3
PLAYER_BOX_COLS = ("game_id", "team_id", "player_id", "season", "game_date",
                   "minutes", "fga", "pts", "appeared", "position", "starter_flag")
PLAYER_BOX_N = 11
BIOS_COLS = ("player_id", "season", "position_raw", "draft_number")
BIOS_N = 4


def assert_allowlist(frame, cols, n, label):
    cols = list(cols)
    assert len(cols) == n, "%s: allowlist length %d != declared %d" % (label, len(cols), n)
    missing = [c for c in cols if c not in frame.columns]
    assert not missing, "%s: missing columns %s" % (label, missing)
    print("  ALLOWLIST %-18s resolved %d/%d: %s" % (label, len(cols), n, cols))
    return cols


def hdr(s):
    print("\n" + "=" * 100)
    print(s)
    print("=" * 100)


def sha256_text(t):
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def jsonable(o):
    if isinstance(o, dict):
        return {str(k): jsonable(v) for k, v in o.items() if k != "draws"}
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
        return str(o.date())
    try:
        if o is not None and not isinstance(o, str) and np.isscalar(o) and pd.isna(o):
            return None
    except Exception:
        pass
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
              "stl", "blk", "tov", "pf", "pts", "minutes"]:
        t[c] = pd.to_numeric(t[c], errors="coerce").astype(float)
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


def sst_of(y):
    y = np.asarray(y, float)
    return float(np.sum((y - y.mean()) ** 2))


def r2_common(y, yhat, sst):
    y = np.asarray(y, float); yhat = np.asarray(yhat, float)
    return float(1.0 - np.sum((y - yhat) ** 2) / sst)


# ----------------------------------------------------------------------------- nulls
def within_teamgame_shuffle(stat_fn, frame, block_col, cand_cols, n_draws, seed,
                            alternative="two_sided"):
    """N1 -- THE PRIMARY NULL.  Permute the CANDIDATE columns among the REMAINING PLAYERS
    WITHIN a team-game, holding the realised outcomes in place.

    WHY THIS LEVEL.  The candidate in every primary cell is a per-remaining-player quantity
    (predicted beneficiary share, position match, depth rank) that varies WITHIN a team-game.
    D108 ruling 4 requires the null to match where the candidate varies; D108's degenerate case
    was a WITHIN-PLAYER cyclic shift applied to a BETWEEN-PLAYER candidate, which a rotation
    preserves exactly.  A within-team-game shuffle destroys exactly the association being tested
    -- which player in this team-game gets the freed volume -- while preserving (a) the team-game
    marginal totals, (b) the absence itself, and (c) each player's own outcome.  Power is
    VERIFIED BY INJECTION in s06 before any verdict is read from it.
    """
    f = frame.reset_index(drop=True)
    codes = f[block_col].to_numpy()
    order = np.argsort(codes, kind="stable")
    csorted = codes[order]
    bounds = np.flatnonzero(np.r_[True, csorted[1:] != csorted[:-1]])
    sizes = np.diff(np.r_[bounds, len(csorted)])
    real = float(stat_fn(f))
    rng = np.random.default_rng(seed)
    vals = {c: f[c].to_numpy() for c in cand_cols}
    draws = np.empty(n_draws, float)
    work = f.copy()
    for d in range(n_draws):
        perm = np.empty(len(f), dtype=np.int64)
        for a, n in zip(bounds, sizes):
            perm[a:a + n] = order[a + rng.permutation(n)]
        inv = np.empty(len(f), dtype=np.int64)
        inv[order] = perm
        for c in cand_cols:
            work[c] = vals[c][inv]
        draws[d] = stat_fn(work)
    if alternative == "two_sided":
        hit = int((np.abs(draws) >= abs(real) - 1e-15).sum())
    elif alternative == "greater":
        hit = int((draws >= real - 1e-15).sum())
    else:
        hit = int((draws <= real + 1e-15).sum())
    return {"real": real, "n_rows": int(len(f)), "n_blocks": int(len(bounds)),
            "n_draws": int(n_draws), "null_mean": float(draws.mean()),
            "null_sd": float(draws.std(ddof=1)),
            "p": float((1.0 + hit) / (n_draws + 1.0)),
            "alternative": alternative, "scheme": "within_teamgame_shuffle", "draws": draws}


def paired_signflip_block(loss_a, loss_b, block_codes, n_draws, seed,
                          alternative="two_sided"):
    """N2 -- PAIRED BLOCK SIGN-FLIP on a per-row loss difference, blocked at team-GAME.

    Statistic mean(loss_b - loss_a): how much better arm A is than arm B.  Used ONLY for the
    forecast-comparison cells, where both arms forecast the SAME row so the contrast is paired.
    The block is the team-game because the absence -- the treatment -- is a team-game property,
    so all rows of a team-game share it and a row-level flip would be anticonservative.
    CREDIT: E1_I0033/scripts/agg_base.paired_signflip_block, blocked one level finer.
    """
    d = np.asarray(loss_b, float) - np.asarray(loss_a, float)
    codes = np.asarray(block_codes)
    ok = np.isfinite(d)
    d = d[ok]; codes = codes[ok]
    uniq, inv = np.unique(codes, return_inverse=True)
    nb = len(uniq); n = len(d)
    real = float(d.mean())
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
    return {"real": real, "n_rows": int(n), "n_blocks": int(nb), "n_draws": int(n_draws),
            "null_mean": float(draws.mean()), "null_sd": float(draws.std(ddof=1)),
            "p": float((1.0 + hit) / (n_draws + 1.0)),
            "alternative": alternative, "scheme": "paired_signflip_block_teamgame",
            "draws": draws}


def teamgame_signflip(values, n_draws, seed, alternative="two_sided"):
    """N3 -- team-game-level sign flip on a per-team-game statistic (used for the team-level
    closure cell P01, whose unit IS the team-game)."""
    d = np.asarray(values, float)
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
    return {"real": real, "n_units": int(n), "n_draws": int(n_draws),
            "null_mean": float(draws.mean()), "null_sd": float(draws.std(ddof=1)),
            "p": float((1.0 + hit) / (n_draws + 1.0)),
            "alternative": alternative, "scheme": "teamgame_signflip", "draws": draws}


def mde80(null_sd):
    """Minimum detectable effect at 80% power, two-sided alpha 0.05, from the null sd.
    2.80 = 1.96 + 0.84.  Same convention E1_I0033 used, so the numbers are comparable."""
    return float(2.80 * null_sd)


# ----------------------------------------------------------------------------- prior-only history
def prior_trailing(frame, entity_cols, value_col, k, date_col="game_date",
                   mask_col=None):
    """STRICTLY PRIOR trailing-k mean over an entity's EARLIER rows.

    For row i the statistic uses rows [i-k, i) of that entity's block ONLY; row i is NEVER
    included.  If `mask_col` is given, only rows where mask==1 are folded into the accumulator
    (so a 'trailing-5 minutes when the player actually played' is expressible), but the statistic
    is still WRITTEN for every row.  Returns (values, n_prior_used) aligned to `frame`'s ORIGINAL
    index order.

    RETROSPECTIVE-BASELINE CHECK (six instances found in this programme): the write happens
    BEFORE the fold, the accumulator is a bounded deque of strictly earlier rows, and no
    season-level or game-level aggregate is used anywhere.  s02 asserts that the FIRST row of
    every entity block is NaN, which is the observable signature of the property.
    """
    f = frame.reset_index(drop=False).rename(columns={"index": "_orig"})
    f = f.sort_values(list(entity_cols) + [date_col, "game_id"], kind="stable")
    vals = pd.to_numeric(f[value_col], errors="coerce").to_numpy(float)
    use = (np.ones(len(f), bool) if mask_col is None
           else f[mask_col].to_numpy().astype(bool))
    codes = f.groupby(list(entity_cols), sort=False).ngroup().to_numpy()
    change = np.flatnonzero(np.r_[True, codes[1:] != codes[:-1]])
    ns = np.diff(np.r_[change, len(codes)])
    out = np.full(len(f), np.nan)
    cnt = np.zeros(len(f))
    for a, n in zip(change, ns):
        buf = []
        for j in range(n):
            i = a + j
            out[i] = (float(np.mean(buf)) if buf else np.nan)
            cnt[i] = len(buf)
            if use[i] and np.isfinite(vals[i]):
                buf.append(vals[i])
                if len(buf) > k:
                    buf.pop(0)
    res = pd.DataFrame({"_orig": f["_orig"].to_numpy(), "_stat": out, "_nprior": cnt})
    res = res.sort_values("_orig")
    return res["_stat"].to_numpy(), res["_nprior"].to_numpy()
