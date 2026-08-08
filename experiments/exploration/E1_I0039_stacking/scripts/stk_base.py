"""E1_I0039_stacking -- local machinery.

THE QUESTION.  Three separately validated improvements have never been measured together:

  A  COLD-START TIERING          D092, retargeted by D102 -> route `fallback_level == 2`
  B  FALLBACK ROUTING to a tuned simple estimator   D094 -> route the champion's `is_fallback`
  C  MINUTES REDISTRIBUTION      D116 -> on team-games with >= 25 minutes freed by an absence,
                                 spread the freed minutes EVENLY over the remaining rotation

Do they compose?

LEVEL DECLARATION.  A and B are PLAYER-GAME-level treatments switched by a per-row champion flag.
C is a TEAM-GAME-level treatment (the absence is a property of the team-game) whose forecast term
varies WITHIN the team-game across remaining players.  The nulls are matched accordingly
(D115): paired sign-flip blocked at TEAM-GAME for every forecast-comparison cell, because a
row-level flip would be anticonservative for C and merely conservative for A and B.

CONDITIONING DECLARED.  C's absence indicator is REALISED, not forecast, because both pre-game
injury sources return UNVERIFIABLE from screenkit.check_manifest (E1_I0034 PREREG s1).  Every
cell that contains C is therefore an ORACLE-ON-ABSENCE CEILING and is labelled ORACLEABS.

NO PRODUCTION CHANGE IS ENACTED.  The champion's stored forecasts are read and scored, never
refitted.  All three components remain unauthorised.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
EXP = os.path.join(ROOT, "experiments", "exploration")
OUT = os.path.join(EXP, "E1_I0039_stacking")

# READ-ONLY source screens.  Nothing in this screen writes outside OUT.
SRC_TIER = os.path.join(EXP, "E1_I0020_coldstart_tiering")
SRC_OSE = os.path.join(EXP, "E1_I0022_optimal_simple_estimator")
SRC_REDIST = os.path.join(EXP, "E1_I0034_redistribution")
SRC_STACK = os.path.join(EXP, "E1_I0032_aggregate_stack")

SEED = 20260815
N_DRAWS = 20000

# ---------------------------------------------------------------- PARTITION
# 2021-2024 exploration ONLY.  2025 and 2026 are a sealed confirmation holdout and are NEVER read.
EXPLORATION_SEASONS = (2021, 2022, 2023, 2024)
# W2: the primary scored window.  2023-2024, matching E1_I0034's RSP-W2 exactly, because the
# champion's 2021 fold is declared degenerate and C's walk-forward increment needs a strictly
# earlier SCORED season.  Keeping every cell on W2 keeps A, B and C on IDENTICAL rows (D101).
SCORED_W2 = (2023, 2024)
SEALED = (2025, 2026)


def assert_partition(df, label, col="season"):
    """Value-level partition guard.  Raises if any sealed season appears."""
    vals = set(pd.unique(df[col]).tolist())
    bad = vals & set(SEALED)
    assert not bad, "PARTITION VIOLATION in %s: sealed seasons present %s" % (label, sorted(bad))
    stray = vals - set(EXPLORATION_SEASONS)
    assert not stray, "PARTITION: unexpected seasons in %s: %s" % (label, sorted(stray))
    print("  PARTITION OK  %-22s seasons=%s n=%d" % (label, sorted(vals), len(df)))


def assert_allowlist(frame, cols, n, label):
    """EXPLICIT allowlists only.  No substring / name-based column selection anywhere in this
    screen -- five findings in this programme died to substring matching."""
    cols = list(cols)
    assert len(cols) == n, "%s: allowlist length %d != declared %d" % (label, len(cols), n)
    missing = [c for c in cols if c not in frame.columns]
    assert not missing, "%s: missing columns %s" % (label, missing)
    print("  ALLOWLIST %-16s resolved %d/%d: %s" % (label, len(cols), n, cols))
    return cols


def hdr(s):
    print("\n" + "=" * 104)
    print(s)
    print("=" * 104)


def anchor(label, got, want, tol=0.0):
    d = abs(float(got) - float(want))
    ok = d <= tol
    print("  ANCHOR %-52s want %-22s got %-22s |d|=%.3e  %s"
          % (label, want, got, d, "EXACT" if d == 0 else ("OK" if ok else "*** MISMATCH ***")))
    assert ok, "ANCHOR FAILED: %s want %s got %s" % (label, want, got)
    return ok


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
    try:
        if o is not None and not isinstance(o, str) and np.isscalar(o) and pd.isna(o):
            return None
    except Exception:
        pass
    return o


def dump(obj, name):
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as fh:
        json.dump(jsonable(obj), fh, indent=1, sort_keys=True)


# ---------------------------------------------------------------- metrics
def mae(y, yhat):
    return float(np.mean(np.abs(np.asarray(y, float) - np.asarray(yhat, float))))


def sst_of(y):
    y = np.asarray(y, float)
    return float(np.sum((y - y.mean()) ** 2))


def r2_common(y, yhat, sst):
    y = np.asarray(y, float)
    yhat = np.asarray(yhat, float)
    return float(1.0 - np.sum((y - yhat) ** 2) / sst)


# ---------------------------------------------------------------- null: paired block sign-flip
def paired_signflip_block(loss_a, loss_b, block_codes, n_draws=N_DRAWS, seed=SEED,
                          alternative="two_sided"):
    """N2 -- PAIRED BLOCK SIGN-FLIP on the per-row loss difference, blocked at TEAM-GAME.

    Statistic = mean(loss_b - loss_a) = how much better arm A is than arm B.

    WHY TEAM-GAME.  Component C's treatment (an absence) is a team-game property, so all rows of
    a team-game share it; a row-level flip would be ANTICONSERVATIVE for any cell containing C.
    For A and B, whose treatment varies at player-game level, a team-game block is CONSERVATIVE
    rather than wrong.  D115 requires the null to match the level the candidate varies at; where
    the lattice mixes levels the coarser (conservative) block is the only choice that is valid
    for every cell on a COMMON row set.  Identical construction to E1_I0034 redist_base.py.
    """
    d = np.asarray(loss_b, float) - np.asarray(loss_a, float)
    codes = np.asarray(block_codes)
    ok = np.isfinite(d)
    d = d[ok]
    codes = codes[ok]
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
            "alternative": alternative, "scheme": "paired_signflip_block_teamgame",
            "draws": draws}


def mde80_analytic(null_sd):
    """The PROGRAMME'S analytic rule, 2.80 x null_sd.  D113/D116 place it under active suspicion
    of being ANTI-CONSERVATIVE by 1.22x-3.40x.  Never quoted here without the injection-verified
    floor beside it, and every number in this screen is labelled with which floor backs it."""
    return float(2.80 * null_sd)


# D116's own injection-verified rescale factors, measured on THIS EXACT null family
# (paired block sign-flip at team-game) on THIS EXACT row set (E1_I0034 RSP-W2), per response.
# Source: D116 "A_PARTIAL_INDEPENDENT_READ_ON_D113" -- the analytic power rule is anti-conservative
# by these factors on minutes / attempts / points respectively.  Carried forward, not re-derived,
# and labelled INJECTION_VERIFIED_CARRIED wherever it backs a number.
D116_INJECTION_FACTOR = {"minutes": 1.22, "fga": 1.61, "pts": 3.40}


def mde80_injection(null_sd, response):
    """Injection-verified floor = analytic floor x D116's measured anti-conservatism factor."""
    return float(2.80 * null_sd * D116_INJECTION_FACTOR[response])


# ---------------------------------------------------------------- walk-forward arms
# MIN_TRAIN.  E1_I0034 s06 excludes 2021 from every CHAMPION-based arm because the champion's
# 2021 fold receipt declares `degenerate: true`.  See DEFECTS.md DEF-1.
MIN_TRAIN_CHAMP = 2022
MIN_TRAIN_STRUCT = 2021


def wf_arm(offset, Xcols, y, season, scored=SCORED_W2, min_train=MIN_TRAIN_CHAMP):
    """ONE ARM = offset + walk-forward fit of (y - offset) on [1] + Xcols.

    Season S is fitted on seasons [min_train, S) ONLY -- NO RETROSPECTIVE BASELINE; nothing here
    ever sees the scored season's own response.

    AN INTERCEPT IS HELD IN BOTH ARMS of every comparison: the base arm is `Xcols = []`, i.e.
    offset + a walk-forward intercept, and a candidate arm is offset + a walk-forward fit that
    also has that intercept.  E1_I0032 documented a HIGH defect where fitting [1, x] against a
    BARE offset smuggled in a walk-forward intercept recalibration and returned a number thirty
    times an arithmetic ceiling with the WRONG SIGN.  This construction designs it out.

    Byte-compatible with E1_I0034 s06 `wf_predict`; verified by anchor A8 to 5.1e-16.
    """
    n = len(y)
    D = np.column_stack([np.ones(n)] + [np.asarray(c, float) for c in Xcols])
    out = np.full(n, np.nan)
    r = np.asarray(y, float) - np.asarray(offset, float)
    for s in scored:
        tr = (season < s) & (season >= min_train)
        te = (season == s)
        if tr.sum() < D.shape[1] + 20 or te.sum() == 0:
            continue
        beta, *_ = np.linalg.lstsq(D[tr], r[tr], rcond=None)
        out[te] = D[te] @ beta
    return np.asarray(offset, float) + out
