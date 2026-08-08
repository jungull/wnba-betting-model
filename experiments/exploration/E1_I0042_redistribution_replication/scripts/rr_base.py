"""E1_I0042 -- local machinery for the redistribution replication screen.

OWNED BY THIS SCREEN.  Nothing here writes outside
experiments/exploration/E1_I0042_redistribution_replication/.  The shared _screen_kit is NOT
imported and NOT modified -- sibling agents hold it open.

THE QUESTION.  Component C (D116 / E1_I0034 minutes redistribution) is the only component that
reaches the decision stratum, where E1_I0039 measured +1.73% on minutes.  That rests on ONE clean
walk-forward window.  This module supplies the arms, the null, the floors and the guards needed to
retest it -- or kill it.

LEVEL DECLARATION.  The redistribution term is a TEAM-GAME-level property (the absence belongs to
the team-game) whose per-row value varies within the team-game.  Every null here is a paired
sign-flip BLOCKED AT TEAM-GAME (D115).  A row-level flip would be anticonservative.

CONDITIONING.  The absence indicator is REALISED, not forecast: both pre-game injury sources
return manifest_present == false, and UNVERIFIABLE is not a pass.  EVERY cell produced through
this module is an ORACLE-ON-ABSENCE CEILING (ORACLEABS).
"""
from __future__ import annotations

import hashlib
import json
import os

import numpy as np
import pandas as pd

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
EXP = os.path.join(ROOT, "experiments", "exploration")
OUT = os.path.join(EXP, "E1_I0042_redistribution_replication")

SRC_REDIST = os.path.join(EXP, "E1_I0034_redistribution")
SRC_STACK39 = os.path.join(EXP, "E1_I0039_stacking")
SRC_CHAMP = os.path.join(ROOT, "experiments", "cbs_v15_player_oof_v5", "attempt_001")

SEED = 20260817
N_DRAWS = 20000

# ------------------------------------------------------------------ PARTITION
EXPLORATION_SEASONS = (2021, 2022, 2023, 2024)
SEALED = (2025, 2026)
# Set by s01 from the receipts.  Hard-coded here ONLY as the value s01 must confirm; s01 raises
# if the receipts disagree, so this constant can never silently drift from the evidence.
ADMISSIBLE_SCORED = (2023, 2024)
MIN_TRAIN = 2022


def assert_partition(df, label, col="season"):
    vals = set(pd.unique(pd.to_numeric(df[col], errors="coerce")).tolist())
    vals = {int(v) for v in vals if v == v}
    bad = vals & set(SEALED)
    assert not bad, "PARTITION VIOLATION in %s: sealed seasons present %s" % (label, sorted(bad))
    stray = vals - set(EXPLORATION_SEASONS)
    assert not stray, "PARTITION: unexpected seasons in %s: %s" % (label, sorted(stray))
    print("  PARTITION OK  %-20s seasons=%s n=%d" % (label, sorted(vals), len(df)))


def assert_allowlist(frame, cols, n, label):
    """EXPLICIT allowlists only.  No substring / name-based column selection anywhere in this
    screen -- five findings in this programme died to substring matching."""
    cols = list(cols)
    assert len(cols) == n, "%s: allowlist length %d != declared %d" % (label, len(cols), n)
    assert len(set(cols)) == n, "%s: duplicate names in allowlist" % label
    missing = [c for c in cols if c not in frame.columns]
    assert not missing, "%s: missing columns %s" % (label, missing)
    print("  ALLOWLIST %-12s %d/%d resolved" % (label, len(cols), n))
    return cols


def hdr(s):
    print("\n" + "=" * 106)
    print(s)
    print("=" * 106)


def anchor(label, got, want, tol=0.0):
    if isinstance(want, (list, tuple)) or isinstance(want, bool) or isinstance(want, str):
        ok = (got == want)
        print("  ANCHOR %-50s want %-24s got %-24s %s"
              % (label, want, got, "EXACT" if ok else "*** MISMATCH ***"))
        assert ok, "ANCHOR FAILED: %s want %r got %r" % (label, want, got)
        return 0.0
    d = abs(float(got) - float(want))
    ok = d <= tol
    print("  ANCHOR %-50s want %-24s got %-24s |d|=%.3e  %s"
          % (label, want, got, d, "EXACT" if d == 0 else ("OK" if ok else "*** MISMATCH ***")))
    assert ok, "ANCHOR FAILED: %s want %s got %s (|d|=%.3e)" % (label, want, got, d)
    return d


def check_prereg():
    spec = json.load(open(os.path.join(OUT, "_prereg.json"), encoding="utf-8-sig"))
    got = hashlib.sha256(open(os.path.join(OUT, "PREREG.md"), "rb").read()).hexdigest()
    if got != spec["sha256"]:
        raise SystemExit("PREREGISTRATION HASH MISMATCH -- REFUSING TO RUN\n"
                         " stored %s\n got    %s" % (spec["sha256"], got))
    print("prereg sha256 %s  MATCH  (%d bytes)" % (got, spec["bytes"]))
    return got


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
        return jsonable(o.tolist())
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


# ------------------------------------------------------------------ null
def signflip_block(loss_a, loss_b, block_codes, n_draws=N_DRAWS, seed=SEED,
                   alternative="two_sided", return_draws=False):
    """N2 -- PAIRED BLOCK SIGN-FLIP on the per-row loss difference, blocked at TEAM-GAME.

    Statistic = mean(loss_b - loss_a): how much better arm A is than arm B.  Identical
    construction to E1_I0034 redist_base.py and E1_I0039 stk_base.py, so cells are comparable
    across the three screens.

    THE null_mean DIAGNOSTIC IS STRUCTURALLY VACUOUS HERE and is recorded as such: the draws are
    +/- fixed block sums, so E[draws] = 0 exactly whatever the effect.  It is never quoted as
    clearing a null.
    """
    d = np.asarray(loss_b, float) - np.asarray(loss_a, float)
    codes = np.asarray(block_codes)
    ok = np.isfinite(d)
    d, codes = d[ok], codes[ok]
    uniq, inv = np.unique(codes, return_inverse=True)
    nb, n = len(uniq), len(d)
    real = float(d.mean()) if n else np.nan
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
    res = {"real": real, "n_rows": int(n), "n_blocks": int(nb), "n_draws": int(n_draws),
           "null_mean": float(draws.mean()), "null_sd": sd,
           "p": float((1.0 + hit) / (n_draws + 1.0)),
           # power arithmetic, reported for EVERY cell (six-block hard floor)
           "p_min_attainable": float(2.0 ** (1 - nb)) if nb < 60 else 0.0,
           "max_attainable_abs_t": float(np.sqrt(nb)),
           "six_block_floor_ok": bool(nb >= 6),
           "MDE80_analytic": float(2.80 * sd),
           "null_mean_diagnostic": "STRUCTURALLY_VACUOUS_on_signflip",
           "alternative": alternative, "scheme": "paired_signflip_block_teamgame"}
    if return_draws:
        res["draws"] = draws
    return res


def cell(y, fa, fb, blocks, mask, label, response, n_draws=N_DRAWS, seed=SEED,
         return_draws=False):
    """One comparison cell.  fa = candidate arm, fb = base arm.  Positive dMAE = candidate better.
    D101: identical rows, identical response, identical base on both sides -- enforced by taking
    ONE mask and applying it to both arms."""
    m = np.asarray(mask, bool) & np.isfinite(fa) & np.isfinite(fb) & np.isfinite(y)
    la = np.abs(y[m] - fa[m])
    lb = np.abs(y[m] - fb[m])
    r = signflip_block(la, lb, blocks[m], n_draws=n_draws, seed=seed, return_draws=return_draws)
    r.update({"label": label, "response": response, "n": int(m.sum()),
              "mae_base": float(lb.mean()) if m.sum() else np.nan,
              "mae_arm": float(la.mean()) if m.sum() else np.nan,
              "dMAE": r["real"],
              "pct_of_MAE": (100.0 * r["real"] / float(lb.mean())) if m.sum() and lb.mean() else np.nan,
              "conditioning": "ORACLEABS"})
    return r


# ------------------------------------------------------------------ arms
def wf_shared(offset, Xcols, y, season, scored, min_train=MIN_TRAIN):
    """SHARED-INTERCEPT arm.  offset + walk-forward fit of (y - offset) on [1] + Xcols, season S
    fitted on [min_train, S) only.  Byte-compatible with E1_I0034 s06 and E1_I0039 stk_base
    (verified by anchors A5-A7 / A13-A14).  An intercept is held in BOTH arms of every comparison,
    which designs out E1_I0032's HIGH defect rather than guarding against it."""
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


def wf_frozen(offset, Xcols, y, season, scored, min_train=MIN_TRAIN):
    """FROZEN-INTERCEPT arm.  The base's walk-forward intercept b(S) is computed FIRST from the
    intercept-only fit and then HELD; the candidate contributes ONLY its slopes, fitted with NO
    intercept on the residual (y - offset - b(S)).

    CONSTRUCTION GUARANTEE: wherever every column of Xcols is 0, this arm is BIT-IDENTICAL to the
    base arm.  Any measured effect therefore lives on rows the treatment actually touches, which
    is what E1_I0039's masking construction could not guarantee on the treated rows themselves.

    Returns (forecast, base_forecast) so the caller can assert the guarantee.
    """
    n = len(y)
    yy = np.asarray(y, float)
    off = np.asarray(offset, float)
    r = yy - off
    b = np.full(n, np.nan)
    ones = np.ones((n, 1))
    for s in scored:
        tr = (season < s) & (season >= min_train)
        te = (season == s)
        if tr.sum() < 21 or te.sum() == 0:
            continue
        beta, *_ = np.linalg.lstsq(ones[tr], r[tr], rcond=None)
        b[te] = ones[te] @ beta
    base = off + b
    if not Xcols:
        return base, base
    X = np.column_stack([np.asarray(c, float) for c in Xcols])
    add = np.full(n, np.nan)
    r2 = r - b                       # residual about the FROZEN base
    for s in scored:
        tr = (season < s) & (season >= min_train)
        te = (season == s)
        if tr.sum() < X.shape[1] + 20 or te.sum() == 0:
            continue
        # the training-pool residual about the frozen base must use THAT season's own b, which is
        # nan on training seasons; recompute the training residual against the same intercept the
        # test season uses, so the slope is fitted on a like-for-like residual.
        bs = float(np.nanmean(b[te]))
        beta, *_ = np.linalg.lstsq(X[tr], (r[tr] - bs), rcond=None)
        add[te] = X[te] @ beta
    add = np.where(np.isfinite(add), add, 0.0)
    return base + np.where(np.isfinite(base), add, np.nan), base


# ------------------------------------------------------------------ floors
def mde80_analytic(null_sd):
    """The programme's analytic rule, 2.80 x null_sd.  D113/D116 place it under active suspicion
    of being ANTI-CONSERVATIVE.  Never quoted in this screen without a measured floor beside it."""
    return float(2.80 * null_sd)


# D116's injection-verified anti-conservatism factors, measured on THIS null family and THIS row
# set.  CARRIED, not re-derived; every number they back is labelled INJECTION_CARRIED.  This
# screen derives its OWN factor for its primary cell in s06 and reports both.
D116_FACTOR = {"minutes": 1.22, "pts": 3.40}


def mde80_carried(null_sd, response):
    return float(2.80 * null_sd * D116_FACTOR[response])


def verdict(dmae, floor, nb):
    """s9 grammar, applied mechanically."""
    if nb < 6:
        return "UNDECIDABLE_SUB_SIX_BLOCKS"
    if not np.isfinite(dmae) or not np.isfinite(floor):
        return "UNDECIDABLE"
    if dmae <= 0:
        return "NEGATIVE_OR_ZERO"
    return "ABOVE_FLOOR" if dmae >= floor else "BELOW_FLOOR_NOT_ESTABLISHED"
