"""E1_I0035_availability_sum -- local machinery.

THE QUESTION.  E1_I0033 reported that the champion player arm's availability forecast
`p_active_hat` sums to ~10.34 per team-game where ~9.40 players actually play, and that the
excess sits in tier-B fallback rows carrying p_active ~0.52 against a realised appearance rate
of ~0.10.  This screen (1) reproduces those numbers from source without taking them on trust,
(2) locates the emitting code, (3) characterises the tier-B population, (4) measures candidate
repairs at BOTH the team and the player level, and (5) determines whether the defect reaches
production.

PARTITION.  2021-2024 only.  2025 and 2026 parquet files sit in the same directories and are
NEVER enumerated by any loader here.  Every season list is explicit; `assert_partition` refuses
any frame containing a forbidden season.

NO NAME-BASED COLUMN SELECTION.  Every column set below is an explicit tuple, the resolved list
is printed, and the count is asserted.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
OUT = os.path.join(ROOT, "experiments", "exploration", "E1_I0035_availability_sum")
KIT = os.path.join(ROOT, "experiments", "exploration", "_screen_kit")

TEAM_ARM = os.path.join(ROOT, "experiments", "cbs_v12_team_oof_v2", "attempt_001")
PLAYER_ARM = os.path.join(ROOT, "experiments", "cbs_v15_player_oof_v5", "attempt_001")
CV4 = os.path.join(ROOT, "experiments", "prediction_contract_v4")
MASTER_TEAM = os.path.join(ROOT, "data", "masters", "master_team.parquet")
MASTER_PLAYER = os.path.join(ROOT, "data", "masters", "master_player.parquet")
BIOS = os.path.join(ROOT, "data", "reference", "player_bios.csv")

SEED = 20260810
EXPLORATION_SEASONS = (2021, 2022, 2023, 2024)
SCORED_SEASONS = (2022, 2023, 2024)
FORBIDDEN_SEASONS = (2025, 2026)

sys.dont_write_bytecode = True

# ---- the declared constant, read from the implementation rather than transcribed -----------
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def declared_p_active_constant() -> float:
    """Read DECLARED['p_active']['point'] out of cbs_generator.py WITHOUT importing the arm.

    Importing cbs_generator drags in the whole adapter stack.  The constant is a module-level
    literal, so it is parsed out of the AST.  If the parse fails this raises rather than
    guessing -- a number nobody can point at in the source may not back a claim.
    """
    import ast
    src = open(os.path.join(ROOT, "cbs_generator.py"), encoding="utf-8").read()
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "DECLARED" for t in node.targets):
            # DECLARED's other entries reference module-level Names (TEAM_POINTS_FLOOR), so the
            # whole dict is not literal-evaluable. Only the p_active entry is read, by key.
            for k, v in zip(node.value.keys, node.value.values):
                if isinstance(k, ast.Constant) and k.value == "p_active":
                    sub = ast.literal_eval(v)
                    return float(sub["point"])
    raise RuntimeError("DECLARED['p_active']['point'] not found in cbs_generator.py")


def hdr(s):
    print("\n" + "=" * 96)
    print(s)
    print("=" * 96)


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
        return str(o.date())
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


def pick(df, cols, where):
    """Explicit allowlist column selection.  Prints the resolved list and asserts the count.

    NO substring matching anywhere in this screen (five prior findings died to it).
    """
    cols = tuple(cols)
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise KeyError("%s: missing columns %s" % (where, missing))
    out = df[list(cols)].copy()
    print("    [pick] %-34s -> %d cols: %s" % (where, len(cols), list(cols)))
    assert out.shape[1] == len(cols)
    return out


# ----------------------------------------------------------------------------- loaders
def load_arm(dirpath, target, seasons=EXPLORATION_SEASONS):
    """Explicit season enumeration.  2025/2026 parquet files are never named."""
    for s in seasons:
        if s in FORBIDDEN_SEASONS:
            raise RuntimeError("refusing to open season %s" % s)
    fr = []
    for s in seasons:
        p = os.path.join(dirpath, "predictions__%s__%d.parquet" % (target, s))
        d = pd.read_parquet(p)
        d["season"] = s
        fr.append(d)
    out = pd.concat(fr, ignore_index=True)
    return assert_partition(out, "load_arm/%s" % target)


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

    prediction_contract_v5 -- which is the champion arm's actual row universe -- has NO sibling
    manifest and is therefore UNVERIFIABLE.  It may not back a number.  So the map is rebuilt
    from the registered canonical key over the cross product of (team-game) x (every player
    seen anywhere in the partition), and then CROSS-CHECKED to exact agreement against the
    manifest-verified contract v4 on every row the two share.
    """
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
    """Mann-Whitney AUC with tie correction."""
    y = np.asarray(y, float); s = np.asarray(s, float)
    ok = np.isfinite(y) & np.isfinite(s)
    y, s = y[ok], s[ok]
    n1 = float(y.sum()); n0 = float(len(y) - n1)
    if n1 == 0 or n0 == 0:
        return float("nan")
    r = pd.Series(s).rank(method="average").to_numpy()
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n0))


# ----------------------------------------------------------------------------- nulls
def paired_signflip_block(loss_a, loss_b, block_codes, n_draws, seed,
                          alternative="two_sided"):
    """PAIRED BLOCK SIGN-FLIP on the per-row loss difference.

    Statistic: mean(loss_b - loss_a) -- how much better A is than B.  Whole blocks flip
    together.  D108: the block level MUST match the level the quantity varies at.  Every
    team-level comparison in this screen blocks at TEAM-SEASON; every player-level comparison
    blocks at PLAYER-SEASON, because a repair to p_active moves a whole player's series at once.
    Power is VERIFIED BY INJECTION for each before any verdict is taken.
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
    """VERIFY BY INJECTION (D108).  Returns the detection rate at nominal 0.05.

    `diff_noise` is a REAL per-row paired loss-difference vector, centred to mean zero so it
    describes a NO-EFFECT world with this data's actual dispersion and block structure.  Each
    replicate draws a fresh no-effect world by flipping whole blocks' signs (the same operation
    the null itself uses, so the noise is exchangeable by construction), adds the planted
    `effect`, and runs the full null.

    An earlier version of this function planted a CONSTANT onto a loss vector.  That is
    degenerate: the resulting per-row difference is exactly `effect` everywhere, so the null sd
    scales linearly with `effect` and the detection rate is identical at every effect size.  It
    reported 1.000 at every planted value and measured nothing.  Recorded in DEFECTS.md as D-1.
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
        # run the block sign-flip directly on the planted difference vector
        r = paired_signflip_block(np.zeros_like(d), d, codes, n_draws, seed + 1000 + i)
        hits += int(r["p"] < 0.05)
    return float(hits) / n_reps


def type_I_rate(diff_noise, block_codes, n_draws, seed, n_reps=400):
    """Type-I rate at nominal 0.05 under a genuine no-effect world (planted effect exactly 0)."""
    d0 = np.asarray(diff_noise, float)
    ok = np.isfinite(d0)
    d0 = d0[ok] - d0[ok].mean()
    codes = np.asarray(block_codes)[ok]
    uniq, inv = np.unique(codes, return_inverse=True)
    rng = np.random.default_rng(seed)
    ps = []
    for i in range(n_reps):
        s = rng.choice(np.array([-1.0, 1.0]), size=len(uniq))[inv]
        d = d0 * s
        ps.append(paired_signflip_block(np.zeros_like(d), d, codes, n_draws,
                                        seed + 5000 + i)["p"])
    return np.array(ps)
