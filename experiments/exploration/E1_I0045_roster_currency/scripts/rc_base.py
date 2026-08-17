"""E1_I0045_roster_currency -- local machinery.

INDEPENDENT REIMPLEMENTATION.  Nothing is imported from E1_I0035's `av_base`; the definitions
below are rebuilt from the same registered sources so that the reproduction of E1_I0035's
anchors is an independent path rather than a re-execution of its code.  Where a definition must
match E1_I0035 for D101 comparability (row sets, response, SST basis, block levels, metric
formulae) that is stated in the docstring of the function concerned.

PARTITION.  2021-2024 only.  2025 and 2026 parquet files sit in the same directories and are
NEVER enumerated by any loader here.  `assert_partition` raises on their presence.

NO NAME-BASED COLUMN SELECTION.  Every column set is an explicit tuple; `pick` prints the
resolved list and asserts the count.

WRITE SCOPE.  Every path written by this screen is under OUT.  Nothing else is written.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
OUT = os.path.join(ROOT, "experiments", "exploration", "E1_I0045_roster_currency")

TEAM_ARM = os.path.join(ROOT, "experiments", "cbs_v12_team_oof_v2", "attempt_001")
PLAYER_ARM = os.path.join(ROOT, "experiments", "cbs_v15_player_oof_v5", "attempt_001")
CV4 = os.path.join(ROOT, "experiments", "prediction_contract_v4")
CV5 = os.path.join(ROOT, "experiments", "prediction_contract_v5")
MASTER_TEAM = os.path.join(ROOT, "data", "masters", "master_team.parquet")
MASTER_PLAYER = os.path.join(ROOT, "data", "masters", "master_player.parquet")
TRANSACTIONS = os.path.join(ROOT, "data", "injury_history", "injury_history.csv")

SEED = 20260811
EXPLORATION_SEASONS = (2021, 2022, 2023, 2024)
SCORED_SEASONS = (2022, 2023, 2024)
CLEAN_WINDOW = (2023, 2024)          # the one clean window; 2021 degenerate, 2022 trains on it
FORBIDDEN_SEASONS = (2025, 2026)

#: v4/v5's outcome-availability policy: a game's box score is observable 36h after tip.
AVAIL_LAG_HOURS = 36

sys.dont_write_bytecode = True


def hdr(s):
    print("\n" + "=" * 100)
    print(s)
    print("=" * 100)


def sha256_text(t):
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


def sha256_file(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


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
        return str(o)
    try:
        if o is not None and not isinstance(o, str) and np.isscalar(o) and pd.isna(o):
            return None
    except (TypeError, ValueError):
        pass
    return o


def assert_partition(df, where):
    if "season" not in df.columns:
        return df
    bad = sorted(set(pd.to_numeric(df["season"], errors="coerce").dropna().astype(int))
                 & set(FORBIDDEN_SEASONS))
    if bad:
        raise RuntimeError("PARTITION VIOLATION in %s: seasons %s present" % (where, bad))
    return df


def pick(df, cols, where, quiet=False):
    cols = tuple(cols)
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise KeyError("%s: missing columns %s" % (where, missing))
    out = df[list(cols)].copy()
    if not quiet:
        print("    [pick] %-36s -> %d cols: %s" % (where, len(cols), list(cols)))
    assert out.shape[1] == len(cols)
    return out


# ----------------------------------------------------------------------------- loaders
def load_arm(dirpath, target, seasons=EXPLORATION_SEASONS):
    for s in seasons:
        if s in FORBIDDEN_SEASONS:
            raise RuntimeError("refusing to open season %s" % s)
    fr = []
    for s in seasons:
        p = os.path.join(dirpath, "predictions__%s__%d.parquet" % (target, s))
        d = pd.read_parquet(p)
        d["season"] = s
        fr.append(d)
    return assert_partition(pd.concat(fr, ignore_index=True), "load_arm/%s" % target)


MASTER_TEAM_COLS = ("game_id", "season", "season_type", "game_date", "team_id", "opp_team_id",
                    "is_home", "pts", "fga", "fta", "ftm", "reb", "ast", "minutes")
MASTER_PLAYER_COLS = ("game_id", "season", "season_type", "game_date", "team_id", "player_id",
                      "player_name", "position", "starter_flag", "dnp_reason", "minutes",
                      "pts", "fga", "fta", "ftm", "reb", "ast")


def load_team_master(seasons=EXPLORATION_SEASONS):
    t = pd.read_parquet(MASTER_TEAM)
    t = t[t["season"].isin(seasons)].copy()
    assert_partition(t, "master_team")
    t = pick(t, MASTER_TEAM_COLS, "master_team")
    t["game_date"] = pd.to_datetime(t["game_date"])
    for c in ("pts", "fga", "fta", "ftm", "reb", "ast", "minutes"):
        t[c] = pd.to_numeric(t[c], errors="coerce").astype(float)
    return t.sort_values(["season", "team_id", "game_date", "game_id"],
                         kind="stable").reset_index(drop=True)


def load_player_master(seasons=EXPLORATION_SEASONS):
    p = pd.read_parquet(MASTER_PLAYER)
    p = p[p["season"].isin(seasons)].copy()
    assert_partition(p, "master_player")
    p = pick(p, MASTER_PLAYER_COLS, "master_player")
    p["game_date"] = pd.to_datetime(p["game_date"])
    p["minutes"] = pd.to_numeric(p["minutes"], errors="coerce")
    p["appeared"] = (p["minutes"].fillna(0.0) > 0.0).astype(int)
    p["minutes"] = p["minutes"].fillna(0.0)
    for c in ("pts", "fga", "fta", "ftm", "reb", "ast"):
        p[c] = pd.to_numeric(p[c], errors="coerce").fillna(0.0).astype(float)
    return p.sort_values(["season", "player_id", "game_date", "game_id"],
                         kind="stable").reset_index(drop=True)


# ----------------------------------------------------------------------------- identity map
def reconstruct_identity(team_master, player_master):
    """row_uid -> (player_id, game_id, team_id), RECOMPUTED from cbs_obligation_key/1.

    contract v5 -- the arm's actual row universe -- has NO sibling manifest and is therefore
    UNVERIFIABLE; it may not back a number.  The map is rebuilt from the registered canonical key
    over (team-game) x (every player seen anywhere in the partition) and cross-checked to exact
    agreement against the manifest-verified contract v4 on every shared row.
    """
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from cbs_obligation_key import CANONICAL_KEY_FIELDS, stable_hash
    assert tuple(CANONICAL_KEY_FIELDS) == ("player_id", "game_id", "team_id"), \
        "canonical key field order changed; the map rule must be re-derived"
    tg = team_master[["game_id", "team_id"]].drop_duplicates()
    players = np.sort(player_master["player_id"].unique())
    print("    team-games=%d  players=%d  triples=%d"
          % (len(tg), len(players), len(tg) * len(players)))
    g = np.repeat(tg["game_id"].to_numpy(), len(players))
    t = np.repeat(tg["team_id"].to_numpy(), len(players))
    p = np.tile(players, len(tg))
    uid = ["ob_" + stable_hash(int(pp), str(gg), int(tt)) for pp, gg, tt in zip(p, g, t)]
    m = pd.DataFrame({"row_uid": uid, "player_id": p, "game_id": g, "team_id": t})
    if m["row_uid"].duplicated().any():
        raise RuntimeError("reconstructed row_uid is not unique")
    return m


# ----------------------------------------------------------------------------- metrics
def mae(y, yhat):
    y = np.asarray(y, float); yhat = np.asarray(yhat, float)
    return float(np.mean(np.abs(y - yhat)))


def rmse(y, yhat):
    y = np.asarray(y, float); yhat = np.asarray(yhat, float)
    return float(np.sqrt(np.mean((y - yhat) ** 2)))


def bias(y, yhat):
    return float(np.mean(np.asarray(yhat, float) - np.asarray(y, float)))


def r2_common(y, yhat, sst):
    y = np.asarray(y, float); yhat = np.asarray(yhat, float)
    return float(1.0 - np.sum((y - yhat) ** 2) / sst)


def sst_of(y):
    y = np.asarray(y, float)
    return float(np.sum((y - y.mean()) ** 2))


def brier(y, p):
    y = np.asarray(y, float); p = np.asarray(p, float)
    return float(np.mean((p - y) ** 2))


def logloss(y, p, eps=1e-12):
    y = np.asarray(y, float)
    p = np.clip(np.asarray(p, float), eps, 1 - eps)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def auc(y, s):
    y = np.asarray(y, float); s = np.asarray(s, float)
    ok = np.isfinite(y) & np.isfinite(s)
    y, s = y[ok], s[ok]
    n1 = float(y.sum()); n0 = float(len(y) - n1)
    if n1 == 0 or n0 == 0:
        return float("nan")
    r = pd.Series(s).rank(method="average").to_numpy()
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n0))


EPS = 1e-6


def logit(p):
    p = np.clip(np.asarray(p, float), EPS, 1 - EPS)
    return np.log(p / (1 - p))


def sigmoid(z):
    return 1.0 / (1.0 + np.exp(-np.clip(z, -40, 40)))


def fit_logistic_1d(x, y, n_iter=200, ridge=1e-6, min_n=30):
    """Newton IRLS on [1, x].  Returns (a, b) or None.  Intercept-only if x is constant."""
    x = np.asarray(x, float); y = np.asarray(y, float)
    if len(x) < min_n:
        return None
    if np.std(x) < 1e-9:
        m = np.clip(y.mean(), EPS, 1 - EPS)
        return (float(np.log(m / (1 - m))), 0.0)
    X = np.column_stack([np.ones(len(x)), x])
    beta = np.zeros(2)
    for _ in range(n_iter):
        p = sigmoid(X @ beta)
        W = np.clip(p * (1 - p), 1e-9, None)
        z = X.T @ (y - p) - ridge * beta
        H = X.T @ (X * W[:, None]) + ridge * np.eye(2)
        step = np.linalg.solve(H, z)
        beta = beta + step
        if np.max(np.abs(step)) < 1e-10:
            break
    return (float(beta[0]), float(beta[1]))


def fit_intercept_only(x, y):
    """Intercept-only logistic recalibration: sigma(a + 1*logit p).  Used for the FROZEN /
    UNFROZEN contrast -- it moves the shared level and nothing else."""
    x = np.asarray(x, float); y = np.asarray(y, float)
    if len(x) < 30:
        return None
    a = 0.0
    for _ in range(200):
        p = sigmoid(a + x)
        W = np.clip(p * (1 - p), 1e-9, None).sum()
        step = (y - p).sum() / max(W, 1e-9)
        a += step
        if abs(step) < 1e-12:
            break
    return float(a)


# ----------------------------------------------------------------------------- nulls
def paired_signflip_block(loss_a, loss_b, block_codes, n_draws, seed,
                          alternative="two_sided"):
    """PAIRED BLOCK SIGN-FLIP on the per-row loss difference.

    Statistic mean(loss_b - loss_a): how much better A is than B.  Whole blocks flip together.
    D108: the block level must match the level the quantity varies at.  Team comparisons block at
    TEAM-SEASON, player comparisons at PLAYER-SEASON.
    """
    d = np.asarray(loss_b, float) - np.asarray(loss_a, float)
    codes = np.asarray(block_codes)
    ok = np.isfinite(d)
    d = d[ok]; codes = codes[ok]
    uniq, inv = np.unique(codes, return_inverse=True)
    nb = len(uniq)
    n = len(d)
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
            "alternative": alternative, "draws": draws}


def mde80(null_sd):
    """Two-sided 5%, 80% power: 2.802 * null_sd.  D103 requires this beside every comparison."""
    return float(2.801585 * null_sd)


def injection_power(diff_noise, block_codes, effect, n_draws, seed, n_reps=200):
    """VERIFY BY INJECTION (D108).  Detection rate at nominal 0.05.

    `diff_noise` is a REAL per-row paired loss-difference vector, centred to mean zero, so it
    describes a NO-EFFECT world with this data's dispersion and block structure.  Planting a
    CONSTANT onto a loss vector instead is degenerate (E1_I0035 DEFECTS D-1) and is not done here.
    """
    d0 = np.asarray(diff_noise, float)
    ok = np.isfinite(d0)
    d0 = d0[ok]
    codes = np.asarray(block_codes)[ok]
    d0 = d0 - d0.mean()
    uniq, inv = np.unique(codes, return_inverse=True)
    rng = np.random.default_rng(seed)
    hits = 0
    for i in range(n_reps):
        s = rng.choice(np.array([-1.0, 1.0]), size=len(uniq))[inv]
        d = d0 * s + effect
        r = paired_signflip_block(np.zeros_like(d), d, codes, n_draws, seed + 1000 + i)
        hits += int(r["p"] < 0.05)
    return float(hits) / n_reps


def type_I_rate(diff_noise, block_codes, n_draws, seed, n_reps=400):
    d0 = np.asarray(diff_noise, float)
    ok = np.isfinite(d0)
    d0 = d0[ok] - d0[ok].mean()
    codes = np.asarray(block_codes)[ok]
    uniq, inv = np.unique(codes, return_inverse=True)
    rng = np.random.default_rng(seed)
    ps = []
    for i in range(n_reps):
        s = rng.choice(np.array([-1.0, 1.0]), size=len(uniq))[inv]
        ps.append(paired_signflip_block(np.zeros_like(d0 * s), d0 * s, codes, n_draws,
                                        seed + 5000 + i)["p"])
    return np.array(ps)


def verdict(p, effect, mde):
    if p < 0.05 and abs(effect) > mde:
        return "ESTABLISHED"
    if p < 0.05:
        return "NOT ESTABLISHED (underpowered)"
    return "NOT ESTABLISHED"


def dump(obj, name):
    open(os.path.join(OUT, name), "w", encoding="utf-8").write(
        json.dumps(jsonable(obj), indent=2))
