"""Permutation-integrity regression tests (audit deliverable B).

Runnable two ways:
    python -m pytest tests/ -q                    (if pytest is installed)
    python tests/test_permutation_integrity.py    (plain runner, no dependencies)

WHAT THIS GUARDS
----------------
``joint_differential_v1`` shipped a permutation probe with two variants.  The
FAITHFUL null reshuffled the train targets and refit the whole chain (channel
ridges AND the margin calibration) on the shuffled targets.  A second variant
refit the ridges on shuffled targets but recalibrated on the TRUE train margins
-- handing the null one genuinely-fitted degree of freedom, so it could not
collapse (perm mean 11.3005 against a naive 11.4088 and a faithful 11.4730).

The general failure mode: ANY quantity fitted on unpermuted data that survives
into the permuted path -- a calibration slope, a shrinkage constant, a tuned
alpha, a threshold, a residual pool, a feature or cell SELECTION.  A null
carrying such a quantity is not a null, and every p-value read off it is wrong.

These tests build the failure modes on synthetic data where the ground truth is
known by construction, and assert that stated audit rules separate them:

  (1) known-ZERO signal + faithful null  -> the null collapses and the real
      model is NOT distinguishable from it
  (2) known signal + faithful null       -> the null still collapses and the
      real model IS distinguishable (the rules have power, not just safety)
  (3) THE TEETH. Deliberately-defective pipelines that MUST be caught:
      (3a) statistical: calibration refit on true targets -> the null beats the
           published no-skill baseline, which a valid null cannot do
      (3b) structural: a null whose output changes when the TRUE targets are
           relabelled in a way that leaves the PERMUTED targets identical is,
           by construction, reading unpermuted data. Deterministic, no
           statistics, catches defects too small to show up in a mean
      (3c) selection hoisted outside the permutation loop -> manufactures a
           FALSE POSITIVE at the p-value floor on data with no signal at all

If a future edit weakens the audit rules, the (3) tests go green when they
should be red, and this file fails.

CALIBRATION NOTE (a live finding, pinned below):
``joint_differential.PERM_NEAR_NAIVE_TOL = 0.35`` is LOOSER than the defect it
was meant to catch -- the observed defective null beat naive by only 0.108, so
the configured collapse gate would have reported PASS on it.  The defect was
caught by a human reading the diagnostic line, not by the gate.
:func:`audit_permutation_null` therefore scales its tolerance to the naive MAE,
and ``test_configured_tolerance_is_too_loose`` pins the finding.
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# --------------------------------------------------------------------------- #
# a minimal stand-in for the repo's fitting chain
#   standardize -> ridge (unpenalized intercept) -> linear calibration
# the same three-stage shape as joint_differential's per-channel chain
# --------------------------------------------------------------------------- #

def standardize_fit(X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mu = X.mean(axis=0)
    sd = X.std(axis=0, ddof=0)
    sd[sd < 1e-12] = 1.0
    return mu, sd


def ridge_fit(Z: np.ndarray, y: np.ndarray, lam: float) -> tuple[np.ndarray, float]:
    """Ridge with an UNPENALIZED intercept (centre y, solve, recover intercept)."""
    ybar = float(y.mean())
    beta = np.linalg.solve(Z.T @ Z + lam * np.eye(Z.shape[1]), Z.T @ (y - ybar))
    return beta, ybar


def linfit(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """Least-squares y ~ a + b*x. Degenerate x -> (mean(y), 0)."""
    xv = float(np.var(x))
    if xv < 1e-15:
        return float(np.mean(y)), 0.0
    b = float(np.cov(x, y, ddof=0)[0, 1] / xv)
    return float(np.mean(y) - b * np.mean(x)), b


def mae(e: np.ndarray) -> float:
    return float(np.mean(np.abs(e)))


# --------------------------------------------------------------------------- #
# synthetic data with KNOWN ground truth
# --------------------------------------------------------------------------- #

def make_data(rng, n_tr=400, n_te=400, p=45, signal=0.0, noise=11.0,
              home=1.6, stale_drift=2.8):
    """Gaussian design; y = home + signal * (X @ w) + noise.

    ``signal=0`` gives provably zero relationship between X and y -- any
    apparent skill is fitting noise.  ``noise``/``home`` sit at this repo's
    margin scale so the numbers read like the real thing.

    ``naive_const`` is the PUBLISHED no-skill baseline: a home-advantage
    constant carried over from an earlier era and therefore ``stale_drift``
    points off the current mean.  That staleness is not fixture convenience --
    it is the reason a defective null can beat "naive" at all, and the same
    thing happened for real: joint_differential's true-calibration null
    predicted (approximately) the train mean, a better constant than the naive
    home-advantage predictor, so it scored 11.3005 against naive's 11.4088
    while the faithful null scored 11.4730.

    The signal and noise components are exactly mean-centred before assembly, so
    E[y] is exactly ``home`` in both splits.  That pins the fixture on the
    mechanism under test instead of on sampling noise in the split means, which
    at n=400 and sigma=11 would otherwise swamp a 2.8-point staleness.
    """
    X_tr = rng.normal(size=(n_tr, p))
    X_te = rng.normal(size=(n_te, p))
    w = rng.normal(size=p)
    w /= np.linalg.norm(w)

    def _y(X, n):
        s = X @ w
        e = rng.normal(scale=noise, size=n)
        return home + signal * (s - s.mean()) + (e - e.mean())

    return {"X_tr": X_tr, "y_tr": _y(X_tr, n_tr),
            "X_te": X_te, "y_te": _y(X_te, n_te),
            "naive_const": home - stale_drift}


# --------------------------------------------------------------------------- #
# the pipeline, faithful and deliberately defective
# --------------------------------------------------------------------------- #

def fit_score(X_tr, y_tr, X_te, y_te, lam, *, cal_target=None) -> float:
    """standardize -> ridge -> linear calibration on (X_tr, y_tr); test MAE.

    ``cal_target`` overrides the target the FINAL CALIBRATION is fit against.
    Passing the TRUE targets while ``y_tr`` is permuted is the defect.
    """
    mu, sd = standardize_fit(X_tr)
    Z_tr, Z_te = (X_tr - mu) / sd, (X_te - mu) / sd
    beta, b0 = ridge_fit(Z_tr, y_tr, lam)
    pred_tr, pred_te = Z_tr @ beta + b0, Z_te @ beta + b0
    a, b = linfit(pred_tr, y_tr if cal_target is None else cal_target)
    return mae(a + b * pred_te - y_te)


def permutation_probe(data, lam=30.0, n_perm=60, seed=0, *,
                      defect: str = "none", index_perms=None) -> dict:
    """Run the real fit and ``n_perm`` permuted refits; return the probe record.

    defect
      "none"     faithful: shuffle y_tr and refit EVERYTHING on the shuffled
                 targets (ridge AND calibration)
      "truecal"  the joint_differential defect, verbatim: the ridge refits on
                 permuted targets, the calibration refits on the TRUE ones

    ``index_perms`` pins the exact row permutations (used by the structural
    invariance test, which needs two runs to see identical permuted vectors).
    """
    X_tr, y_tr = data["X_tr"], data["y_tr"]
    X_te, y_te = data["X_te"], data["y_te"]
    rng = np.random.default_rng(seed)
    if index_perms is None:
        index_perms = [rng.permutation(len(y_tr)) for _ in range(n_perm)]
    n_perm = len(index_perms)

    naive = mae(data["naive_const"] - y_te)
    real = fit_score(X_tr, y_tr, X_te, y_te, lam)

    perm = []
    for idx in index_perms:
        yp = y_tr[idx]
        cal = y_tr if defect == "truecal" else None     # true targets leak in
        perm.append(fit_score(X_tr, yp, X_te, y_te, lam, cal_target=cal))
    perm = np.asarray(perm, float)

    n_le = int(np.sum(perm <= real))
    return {
        "defect": defect, "n_perm": n_perm,
        "real_mae": real, "naive_mae": naive,
        "perm_mean": float(perm.mean()),
        "perm_min": float(perm.min()), "perm_max": float(perm.max()),
        "p_value": (1 + n_le) / (n_perm + 1),
        "mean_perm_minus_naive": float(perm.mean()) - naive,
        "perm_maes": [round(float(v), 6) for v in perm],
    }


# --------------------------------------------------------------------------- #
# THE AUDIT RULES under test
# --------------------------------------------------------------------------- #

# A null that beats the published no-skill baseline by more than this fraction
# of that baseline has retained a fitted degree of freedom. 0.5% of an ~11-point
# naive MAE is ~0.055 -- tight enough to catch the observed 0.108 defect, loose
# enough not to trip on Monte-Carlo noise at n_perm >= 30.
NEAR_NAIVE_FRAC = 0.005
MAX_P = 0.05


def audit_permutation_null(res: dict, *, max_p: float = MAX_P,
                           near_naive_frac: float = NEAR_NAIVE_FRAC) -> dict:
    """Statistical verdict on a permutation probe.

    ``null_collapsed`` is the INTEGRITY check: a legitimate null, having no
    information about the target, cannot systematically beat the published
    no-skill baseline.  If it does, something in the chain was fitted on
    unpermuted data.

    ``signal_detected`` is the INFERENCE: the real model sits outside the null.

    A probe is only evidence when ``null_collapsed`` is True.  Reading
    ``signal_detected`` off a non-collapsed null is reading a broken instrument.
    """
    tol = near_naive_frac * res["naive_mae"]
    collapsed = res["mean_perm_minus_naive"] >= -tol
    detected = res["p_value"] <= max_p
    return {
        "null_collapsed": bool(collapsed),
        "signal_detected": bool(detected),
        "evidence_admissible": bool(collapsed),
        "verdict": ("DEFECTIVE-NULL" if not collapsed
                    else "SIGNAL" if detected else "NO-SIGNAL"),
        "tolerance_used": tol,
    }


def null_reads_only_permuted_targets(data, lam=30.0, n_perm=12, seed=0, *,
                                     defect: str = "none") -> dict:
    """STRUCTURAL integrity check -- no statistics, no tolerance, no luck.

    Relabel the true targets by a fixed permutation ``pi`` and compose the draw
    permutations with ``pi^-1``.  Both runs then see BIT-IDENTICAL permuted
    target vectors.  A faithful null is a function of the permuted targets
    alone, so its per-draw MAEs must be identical.  Any null that also reads the
    TRUE targets -- a calibration, a shrinkage constant, a threshold, a
    selection -- moves, and is thereby caught.

    Returns {"invariant": bool, "max_abs_dev": float, ...}.
    """
    rng = np.random.default_rng(seed)
    n = len(data["y_tr"])
    perms = [rng.permutation(n) for _ in range(n_perm)]
    pi = rng.permutation(n)
    pi_inv = np.argsort(pi)

    a = permutation_probe(data, lam=lam, seed=seed, defect=defect,
                          index_perms=perms)
    relabelled = dict(data, y_tr=data["y_tr"][pi])
    b = permutation_probe(relabelled, lam=lam, seed=seed, defect=defect,
                          index_perms=[pi_inv[p] for p in perms])

    dev = float(np.max(np.abs(np.asarray(a["perm_maes"]) - np.asarray(b["perm_maes"]))))
    return {"invariant": dev <= 1e-9, "max_abs_dev": dev,
            "defect": defect, "n_perm": n_perm}


# --------------------------------------------------------------------------- #
# a bet-mining fixture: selection inside vs outside the permutation loop
# --------------------------------------------------------------------------- #

def mining_probe(rng_seed: int, n_rows=600, n_cells=120, cell_frac=0.25,
                 n_perm=40, *, hoist_selection: bool = False) -> dict:
    """Pre-registered battery of cells over rows with PURE-NOISE outcomes.

    Observed statistic: the best cell's mean outcome -- a MAXIMUM over the
    battery, so it is upward-biased under the null by construction.

    Faithful null: permute the outcomes and recompute the MAXIMUM over the SAME
    full battery, so the null carries the same selection advantage.
    Defective null: permute the outcomes but score ONLY the cell that won on the
    true outcomes -- selection hoisted outside the loop.  The null then has no
    selection advantage, and the observed maximum beats it essentially always.

    This is the pocket_mining / props_edge shape: nothing is "fitted", yet the
    same defect appears as soon as the SELECTION is not redone per replicate.
    """
    rng = np.random.default_rng(rng_seed)
    outcomes = rng.normal(size=n_rows)                       # ZERO signal
    cells = rng.random(size=(n_cells, n_rows)) < cell_frac   # registered battery
    cells[cells.sum(axis=1) < 20] = True                     # keep cells non-tiny

    def cell_means(y):
        return (cells @ y) / cells.sum(axis=1)

    obs = cell_means(outcomes)
    best = int(np.argmax(obs))
    observed = float(obs[best])

    null = []
    for _ in range(n_perm):
        yp = outcomes[rng.permutation(n_rows)]
        m = cell_means(yp)
        null.append(float(m[best]) if hoist_selection else float(m.max()))
    null = np.asarray(null)

    n_ge = int(np.sum(null >= observed))
    return {"hoisted": hoist_selection, "observed": observed,
            "null_mean": float(null.mean()), "null_max": float(null.max()),
            "p_value": (1 + n_ge) / (n_perm + 1), "n_perm": n_perm,
            "best_cell": best}


# --------------------------------------------------------------------------- #
# (1) known-ZERO signal, faithful null -> collapse, no detection
# --------------------------------------------------------------------------- #

def test_zero_signal_faithful_null_collapses():
    for seed in (11, 12, 13, 14, 15, 16):
        d = make_data(np.random.default_rng(seed), signal=0.0)
        res = permutation_probe(d, seed=seed + 900)
        v = audit_permutation_null(res)
        assert v["null_collapsed"], (seed, res, v)
        assert not v["signal_detected"], (seed, res, v)
        assert v["verdict"] == "NO-SIGNAL", (seed, res, v)
        # a model fitting pure noise cannot beat every permutation of itself
        assert res["real_mae"] >= res["perm_min"], (seed, res)


# --------------------------------------------------------------------------- #
# (2) known signal, faithful null -> collapse AND detection
# --------------------------------------------------------------------------- #

def test_known_signal_is_detected():
    for seed in (21, 22, 23, 24, 25, 26):
        d = make_data(np.random.default_rng(seed), signal=6.0)
        res = permutation_probe(d, seed=seed + 900)
        v = audit_permutation_null(res)
        assert v["null_collapsed"], (seed, res, v)
        assert v["signal_detected"], (seed, res, v)
        assert v["verdict"] == "SIGNAL", (seed, res, v)
        # the real model beats every permutation, not merely the mean
        assert res["real_mae"] < res["perm_min"], (seed, res)
        assert res["real_mae"] < res["naive_mae"], (seed, res)


# --------------------------------------------------------------------------- #
# (3a) TEETH: the joint_differential defect, statistically
# --------------------------------------------------------------------------- #

def test_truecal_defect_is_caught_statistically():
    """A null recalibrated on TRUE train targets must be refused.

    Ground truth is ZERO signal.  The defective null does not collapse: the
    true-target calibration drives its slope to ~0, so it predicts the train
    mean -- a better constant than the published naive baseline, which no
    information-free null is entitled to find.
    """
    caught = 0
    seeds = (31, 32, 33, 34, 35, 36, 37, 38)
    for seed in seeds:
        d = make_data(np.random.default_rng(seed), signal=0.0)
        faithful = permutation_probe(d, seed=seed + 900, defect="none")
        defective = permutation_probe(d, seed=seed + 900, defect="truecal")

        # the defect's signature, reproduced: the broken null scores BETTER
        # (lower MAE) than the faithful null on identical draws
        assert defective["perm_mean"] < faithful["perm_mean"], (seed, faithful, defective)
        # and it lands below the published baseline, where the faithful sits above
        assert faithful["mean_perm_minus_naive"] > 0, (seed, faithful)

        assert audit_permutation_null(faithful)["null_collapsed"], (seed, faithful)
        vd = audit_permutation_null(defective)
        if not vd["null_collapsed"]:
            caught += 1
            assert vd["verdict"] == "DEFECTIVE-NULL", (seed, defective, vd)
            assert not vd["evidence_admissible"], (seed, vd)

    assert caught >= len(seeds) - 1, (
        f"the audit rule caught the true-calibration defect on only "
        f"{caught}/{len(seeds)} seeds -- the suite has lost its teeth")


# --------------------------------------------------------------------------- #
# (3b) TEETH: the structural detector -- deterministic, no tolerance
# --------------------------------------------------------------------------- #

def test_null_must_depend_only_on_permuted_targets():
    """Relabel the true targets, hold the permuted targets fixed, demand silence.

    This catches the defect with no statistics at all: it is a pure statement
    about what the null is a function of.  It therefore also catches defects far
    too small to move a mean -- the ones a tolerance-based gate would miss.
    """
    for seed in (51, 52, 53):
        d = make_data(np.random.default_rng(seed), signal=0.0)

        ok = null_reads_only_permuted_targets(d, seed=seed + 7, defect="none")
        assert ok["invariant"], (seed, ok)
        assert ok["max_abs_dev"] == 0.0, (seed, ok)

        bad = null_reads_only_permuted_targets(d, seed=seed + 7, defect="truecal")
        assert not bad["invariant"], (
            f"seed {seed}: the true-calibration null was invariant to relabelling "
            f"the TRUE targets (max dev {bad['max_abs_dev']:.3e}) -- the "
            f"structural detector is no longer detecting anything")
        assert bad["max_abs_dev"] > 1e-6, (seed, bad)

    # the detector must also be clean on data WITH signal (it tests structure,
    # not skill, so signal must not change its verdict)
    d = make_data(np.random.default_rng(54), signal=6.0)
    assert null_reads_only_permuted_targets(d, seed=61, defect="none")["invariant"]
    assert not null_reads_only_permuted_targets(d, seed=61, defect="truecal")["invariant"]


# --------------------------------------------------------------------------- #
# (3c) TEETH: selection hoisted outside the loop -> FALSE POSITIVE on noise
# --------------------------------------------------------------------------- #

def test_hoisted_selection_manufactures_false_positive():
    """Cell selection on true outcomes, reused under permutation, invents signal.

    Ground truth is ZERO signal.  Re-selecting inside the loop gives the honest
    NO-SIGNAL answer.  Hoisting the selection outside the loop strips the null
    of the selection advantage the observed statistic enjoys, and the p-value
    collapses to its floor on pure noise.  This is the screening / bet-mining
    analogue of the joint_differential defect and the reason cell selection must
    be redone inside every permutation replicate.
    """
    n_perm = 40
    seeds = (41, 42, 43, 44, 45, 46)
    false_pos = honest_pos = 0
    for seed in seeds:
        honest = mining_probe(seed, n_perm=n_perm, hoist_selection=False)
        hoisted = mining_probe(seed, n_perm=n_perm, hoist_selection=True)
        assert honest["observed"] == hoisted["observed"], (seed, honest, hoisted)
        # the broken null is systematically lower: it lost the maximum
        assert hoisted["null_mean"] < honest["null_mean"], (seed, honest, hoisted)
        false_pos += hoisted["p_value"] <= MAX_P
        honest_pos += honest["p_value"] <= MAX_P

    assert false_pos >= len(seeds) - 1, (
        f"hoisted selection produced only {false_pos}/{len(seeds)} false "
        f"positives -- the fixture no longer reproduces the defect, so this "
        f"test is no longer proving anything")
    assert honest_pos <= 1, (
        f"the honest re-select-inside null produced {honest_pos}/{len(seeds)} "
        f"positives on zero-signal data -- fixture or null is broken")
    assert false_pos > honest_pos, (false_pos, honest_pos)


# --------------------------------------------------------------------------- #
# the rules' own guard rails
# --------------------------------------------------------------------------- #

def test_audit_rule_would_have_caught_the_real_defect():
    """Replay the numbers joint_differential actually printed.

    Faithful null 11.4730, true-cal diagnostic 11.3005, naive 11.4088
    (experiments/joint_differential/REPORT.md, audit 3).  The rule must clear
    the faithful null and reject the diagnostic one.
    """
    faithful = {"naive_mae": 11.4088, "perm_mean": 11.4730, "p_value": 0.0323,
                "mean_perm_minus_naive": 11.4730 - 11.4088}
    truecal = {"naive_mae": 11.4088, "perm_mean": 11.3005, "p_value": 0.0323,
               "mean_perm_minus_naive": 11.3005 - 11.4088}
    assert audit_permutation_null(faithful)["null_collapsed"]
    assert audit_permutation_null(faithful)["verdict"] == "SIGNAL"
    assert not audit_permutation_null(truecal)["null_collapsed"]
    assert audit_permutation_null(truecal)["verdict"] == "DEFECTIVE-NULL"


def test_configured_tolerance_is_too_loose():
    """PIN: joint_differential.PERM_NEAR_NAIVE_TOL would NOT have caught it.

    The shipped gate allows the null to beat naive by 0.35 MAE points; the
    observed defect beat it by 0.108.  The defect was found by a human reading
    the diagnostic line, not by the gate.  If that constant is ever tightened
    below the observed gap, update this pin -- until then it stands as the
    record that the automated gate had no teeth here.
    """
    observed_gap = 11.3005 - 11.4088                 # -0.1083
    shipped_tol = 0.35                               # PERM_NEAR_NAIVE_TOL
    assert observed_gap >= -shipped_tol, observed_gap                 # gate PASSES
    assert observed_gap < -(NEAR_NAIVE_FRAC * 11.4088), observed_gap  # this rule FAILS

    src = Path(__file__).resolve().parent.parent / "joint_differential.py"
    if src.exists():
        line = [ln for ln in src.read_text(encoding="utf-8").splitlines()
                if ln.startswith("PERM_NEAR_NAIVE_TOL")]
        assert line, "PERM_NEAR_NAIVE_TOL not found -- update this pin"
        assert "0.35" in line[0], (
            f"PERM_NEAR_NAIVE_TOL changed ({line[0].strip()}); re-derive whether "
            f"the gate now catches a {abs(observed_gap):.4f} MAE null-inflation")


def test_probe_record_is_self_consistent():
    d = make_data(np.random.default_rng(7), signal=0.0)
    res = permutation_probe(d, n_perm=20, seed=7)
    assert res["perm_min"] <= res["perm_mean"] <= res["perm_max"]
    assert 1 / 21 <= res["p_value"] <= 1.0
    assert abs(res["mean_perm_minus_naive"]
               - (res["perm_mean"] - res["naive_mae"])) < 1e-12
    # identical seeds reproduce exactly (a probe you cannot rerun is not evidence)
    assert permutation_probe(d, n_perm=20, seed=7) == res
    # different seeds do not (a probe that ignores its seed is not a probe)
    assert permutation_probe(d, n_perm=20, seed=8)["perm_maes"] != res["perm_maes"]


def _run_all():
    tests = [(n, f) for n, f in sorted(globals().items())
             if n.startswith("test_") and callable(f)]
    failures = []
    for name, fn in tests:
        try:
            fn()
            print(f"PASS  {name}")
        except Exception:
            failures.append(name)
            print(f"FAIL  {name}")
            traceback.print_exc()
    print(f"\n{len(tests) - len(failures)}/{len(tests)} tests passed")
    if failures:
        print("FAILED:", *failures, sep="\n  - ")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(_run_all())
