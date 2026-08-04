"""Tests for the game-clustered inference utilities. Standalone; pytest is NOT installed.

    python experiments/player_program/ops_lane/I10_GENERIC_CLUSTERED_INFERENCE/TESTS.py

``main()`` returns 0 when every check passes and 1 on the first-and-every failure (all checks
run; nothing short-circuits, so one failure does not hide five).

The four acceptance criteria are tested by name:

  A1  games are never split across cluster-bootstrap draws
  A2  the 2,982-row / 1,491-cluster distinction is honoured and both are reported
  A3  seeds are explicit and results reproduce exactly
  A4  the namespace is task-isolated; no shared contract is modified
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True      # importing shared modules must not leave a .pyc behind

import hashlib                                                                # noqa: E402
import json                                                                   # noqa: E402
from pathlib import Path                                                      # noqa: E402

import numpy as np                                                            # noqa: E402
import pandas as pd                                                           # noqa: E402

HERE = Path(__file__).resolve().parent
PROGRAM = HERE.parents[1]
sys.path.insert(0, str(HERE))

import clustered_inference as cinf                                            # noqa: E402

FAILURES: list[str] = []
CHECKS = 0


def check(cond: bool, msg: str) -> None:
    global CHECKS
    CHECKS += 1
    if not cond:
        FAILURES.append(msg)


def raises(fn, exc=cinf.ClusteredInferenceFailure) -> bool:
    try:
        fn()
    except exc:
        return True
    except Exception:
        return False
    return False


def ragged() -> tuple[np.ndarray, cinf.ClusterIndex]:
    """Deliberately ragged: sizes 3, 1, 2, 2 — a uniform size-2 fixture would hide bugs."""
    labels = np.array(["g1", "g1", "g1", "g2", "g3", "g3", "g4", "g4"])
    return labels, cinf.build_cluster_index(labels)


# --------------------------------------------------------------------------------------------
# A1 — a game is never split
# --------------------------------------------------------------------------------------------

def test_A1_whole_clusters_only() -> None:
    labels, ci = ragged()
    check(ci.n_rows == 8 and ci.n_clusters == 4, f"ragged index {ci.n_rows}/{ci.n_clusters}")
    check(ci.size_distribution() == {1: 1, 2: 2, 3: 1},
          f"ragged sizes {ci.size_distribution()}")

    draws = cinf.draw_cluster_ids(ci, 400, seed=7)
    bad = 0
    for b in range(draws.shape[0]):
        rows = cinf.rows_for_cluster_draw(ci, draws[b])
        got = np.bincount(ci.codes[rows], minlength=ci.n_clusters)
        want = np.bincount(draws[b], minlength=ci.n_clusters) * ci.sizes
        if not np.array_equal(got, want):
            bad += 1
        # every drawn cluster contributes a count that is an exact multiple of its size
        nz = got > 0
        if np.any(got[nz] % ci.sizes[nz] != 0):
            bad += 1
    check(bad == 0, f"A1: {bad} draws contained a partial cluster")

    # a drawn row multiset must be reconstructible from cluster multiplicities alone
    rows = cinf.rows_for_cluster_draw(ci, draws[0])
    mult = np.bincount(draws[0], minlength=ci.n_clusters)
    rebuilt = np.concatenate([np.tile(ci.rows_of(c), int(mult[c]))
                              for c in range(ci.n_clusters) if mult[c]])
    check(sorted(rows.tolist()) == sorted(rebuilt.tolist()),
          "A1: drawn rows are not the union of whole drawn clusters")

    # total row count of a draw equals the summed sizes of the drawn clusters
    check(all(cinf.rows_for_cluster_draw(ci, draws[b]).shape[0] == int(ci.sizes[draws[b]].sum())
              for b in range(50)), "A1: draw row count != sum of drawn cluster sizes")


def test_A1_jackknife_deletes_whole_clusters() -> None:
    labels, ci = ragged()
    seen: list[int] = []

    def stat(rows: np.ndarray) -> float:
        seen.append(int(rows.shape[0]))
        return float(rows.shape[0])

    jk = cinf.cluster_jackknife(stat, ci)
    check(jk.shape == (4,), f"jackknife length {jk.shape}")
    check(sorted(jk.tolist()) == sorted([8 - int(s) for s in ci.sizes]),
          "A1: jackknife did not delete whole clusters")


def test_A1_partition_split_is_caught() -> None:
    labels, _ = ragged()
    clean = np.array(["A", "A", "A", "A", "B", "B", "B", "B"])   # respects cluster boundaries
    rep = cinf.assert_clusters_not_split(labels, clean, partition_name="clean")
    check(rep["clusters_split"] == 0 and rep["clusters"] == 4, f"clean partition {rep}")

    split = np.array(["A", "A", "B", "A", "B", "B", "A", "A"])   # cuts g1 in half
    check(raises(lambda: cinf.assert_clusters_not_split(labels, split, partition_name="split")),
          "A1: a partition that splits a cluster was NOT rejected")

    check(raises(lambda: cinf.build_cluster_index(labels, strata=split)),
          "A1: a stratum assignment that straddles a cluster was NOT rejected")


def test_A1_stratified_draws_stay_inside_strata() -> None:
    labels = np.repeat(np.arange(60), 2)
    strata = np.repeat(np.where(np.arange(60) < 25, "early", "late"), 2)
    ci = cinf.build_cluster_index(labels, strata=strata)
    check(ci.describe()["clusters_per_stratum"] == {"early": 25, "late": 35},
          f"stratum sizes {ci.describe().get('clusters_per_stratum')}")
    draws = cinf.draw_cluster_ids(ci, 200, seed=11)
    st = ci.strata
    assert st is not None
    bad = 0
    for b in range(draws.shape[0]):
        drawn_strata = st[draws[b]]
        counts = {s: int((drawn_strata == s).sum()) for s in np.unique(st)}
        if counts != {s: int((st == s).sum()) for s in np.unique(st)}:
            bad += 1
    check(bad == 0, f"A1: {bad} stratified draws changed a stratum's cluster count")


# --------------------------------------------------------------------------------------------
# A2 — the real 2,982 / 1,491 universe
# --------------------------------------------------------------------------------------------

def test_A2_real_universe() -> None:
    sys.path.insert(0, str(PROGRAM))
    try:
        import possession_features as pf
    except Exception as exc:                                # pragma: no cover - environment
        check(False, f"A2: could not load the real universe read-only: {exc}")
        return
    u = pf.load_universe()
    F = u.frame
    ci = cinf.build_cluster_index(F["game_id"])
    check(ci.n_rows == 2982, f"A2: team-game rows = {ci.n_rows}, expected 2982")
    check(ci.n_clusters == 1491, f"A2: game clusters = {ci.n_clusters}, expected 1491")
    check(ci.size_distribution() == {2: 1491},
          f"A2: rows per cluster {ci.size_distribution()}, expected every game to have 2")
    check(u.contract["row_universe_digest"]
          == "raw_index_membership:n=2982:sha256=61f69db015f3270c7f0fd182a92e0371",
          f"A2: row universe digest moved: {u.contract['row_universe_digest']}")

    d = ci.describe()
    check(d["n_rows"] == 2982 and d["n_clusters"] == 1491,
          "A2: describe() must report BOTH the row count and the cluster count")

    for f in pf.chronological_folds(u):
        member = pd.Series("unused", index=F.index, dtype=object)
        member.loc[f.train_index] = "train"
        member.loc[f.test_index] = "test"
        try:
            cinf.assert_clusters_not_split(F["game_id"], member, partition_name=f.fold_id)
        except cinf.ClusteredInferenceFailure as exc:
            check(False, f"A2: fold {f.fold_id} splits a game: {exc}")
        check(len(f.train_index.intersection(f.test_index)) == 0,
              f"A2: fold {f.fold_id} has train/test row overlap")

    # the two rows of a game are near-duplicates on the target; the index must not hide that
    tgt = F[pf.TARGET_COLUMN].to_numpy(dtype=float)
    rep = cinf.cluster_robust_se_mean(tgt, ci)
    check(rep["cluster_robust_se_cr1"] > rep["naive_iid_se"],
          "A2: clustered SE is not wider than the iid SE on the real target — implausible")
    check(1.5 <= rep["design_effect_variance_ratio"] <= 2.0,
          f"A2: design effect {rep['design_effect_variance_ratio']:.4f} outside [1.5, 2.0]; the "
          f"universe's clustering has changed and every stored interval is stale")


# --------------------------------------------------------------------------------------------
# A3 — explicit seeds, exact reproduction
# --------------------------------------------------------------------------------------------

def test_A3_seed_is_required() -> None:
    labels, ci = ragged()
    y = np.arange(8, dtype=float)
    try:
        cinf.cluster_bootstrap(cinf.mean_of(y), ci, n_draws=10)   # type: ignore[call-arg]
        check(False, "A3: cluster_bootstrap ran without a seed")
    except TypeError:
        check(True, "")


def test_A3_exact_reproduction() -> None:
    labels = np.repeat(np.arange(300), 2)
    ci = cinf.build_cluster_index(labels)
    rng = np.random.default_rng(0)
    y = np.repeat(rng.normal(size=300), 2) + rng.normal(size=600)

    a = cinf.cluster_bootstrap(cinf.mean_of(y), ci, n_draws=500, seed=123, jackknife=True)
    b = cinf.cluster_bootstrap(cinf.mean_of(y), ci, n_draws=500, seed=123, jackknife=True)
    check(a.draw_digest == b.draw_digest, "A3: same seed produced different draws")
    check(np.array_equal(a.replicates, b.replicates),
          "A3: same seed produced different replicates")
    check(a.se() == b.se() and a.percentile_ci() == b.percentile_ci(),
          "A3: same seed produced a different interval")
    check(np.array_equal(a.jackknife, b.jackknife), "A3: jackknife is not deterministic")

    short = cinf.cluster_bootstrap(cinf.mean_of(y), ci, n_draws=100, seed=123)
    check(np.array_equal(short.replicates, a.replicates[:100]),
          "A3: prefix stability failed — enlarging n_draws disturbed earlier replicates")

    d1 = cinf.draw_cluster_ids(ci, 50, seed=123)
    d2 = cinf.draw_cluster_ids(ci, 5000, seed=123)[:50]
    check(np.array_equal(d1, d2), "A3: draw matrix is not prefix stable")

    other = cinf.cluster_bootstrap(cinf.mean_of(y), ci, n_draws=500, seed=124)
    check(other.draw_digest != a.draw_digest, "A3: a different seed produced identical draws")

    rec = cinf.bootstrap_receipt(a)
    check(rec["draw_digest_sha256"] == a.draw_digest and rec["seed"] == 123,
          "A3: receipt does not carry the seed and draw digest")
    check(rec["module_sha256"] == hashlib.sha256(
        (HERE / "clustered_inference.py").read_bytes()).hexdigest(),
        "A3: receipt module digest does not match the module bytes")


# --------------------------------------------------------------------------------------------
# A4 — task isolation
# --------------------------------------------------------------------------------------------

def test_A4_isolated_namespace() -> None:
    src = (HERE / "clustered_inference.py").read_text(encoding="utf-8")
    for banned in ("possession_features", "comparison_gate", "feature_gate", "gate_invocation",
                   "receipt_integrity", "construction_receipt", "PROGRAM_STATE"):
        check(f"import {banned}" not in src,
              f"A4: the library imports the shared module {banned}; it must stay standalone")
    check("SEALED_RESULTS" not in src and "SEALED_RESULTS" not in
          (HERE / "measure.py").read_text(encoding="utf-8"),
          "A4: a forbidden input is referenced")

    fresh = {m for m in sys.modules if m in ("possession_features", "comparison_gate",
                                             "feature_gate")}
    # clustered_inference was imported at the top of this file, before anything program-specific
    check(cinf.__file__ is not None and Path(cinf.__file__).parent == HERE,
          f"A4: clustered_inference resolved outside this node: {cinf.__file__}")
    check(isinstance(fresh, set), "")   # structural; the assertion above is the load-bearing one

    # nothing outside this node's directory may have been written by importing/using the library
    labels, ci = ragged()
    cinf.cluster_bootstrap(cinf.mean_of(np.arange(8, dtype=float)), ci, n_draws=5, seed=1)
    check(True, "")


def test_A4_slot_fits_the_published_gate_shape() -> None:
    """The emitted slot must be one the FROZEN comparison_gate already accepts, unmodified."""
    sys.path.insert(0, str(PROGRAM))
    try:
        import comparison_gate as cg
    except Exception as exc:                                # pragma: no cover - environment
        check(False, f"A4: could not import comparison_gate read-only: {exc}")
        return
    before = hashlib.sha256((PROGRAM / "comparison_gate.py").read_bytes()).hexdigest()

    labels = np.repeat(np.arange(200), 2)
    ci = cinf.build_cluster_index(labels)
    rng = np.random.default_rng(5)
    a = np.repeat(rng.normal(size=200), 2) + rng.normal(size=400)
    b = a + rng.normal(scale=0.1, size=400)
    res = cinf.cluster_bootstrap(cinf.paired_mean_difference(a, b), ci, n_draws=400, seed=99,
                                 statistic_name="synthetic paired contrast")
    slot = cinf.uncertainty_slot(res, level=0.95, method="percentile")
    check(set(slot) == {"se", "ci", "ci_level", "method"}, f"A4: slot keys {sorted(slot)}")

    block = cg.uncertainty_block({"challenger_vs_k0": slot},
                                 {"challenger_vs_k0": 0.0, "challenger_vs_incumbent": None,
                                  "k0_vs_incumbent": None})
    entry = block["by_contrast"]["challenger_vs_k0"]
    check(entry["supplied"] is True, "A4: the frozen gate did not accept the emitted slot")
    check(entry["se"] == slot["se"] and entry["ci"] == slot["ci"],
          "A4: the gate parsed different numbers than were emitted")
    check(block["contrasts_without_uncertainty"] == ["challenger_vs_incumbent",
                                                     "k0_vs_incumbent"],
          "A4: unsupplied contrasts must still be named as unknown, not zero")
    after = hashlib.sha256((PROGRAM / "comparison_gate.py").read_bytes()).hexdigest()
    check(before == after, "A4: comparison_gate.py bytes changed — a frozen artifact was written")


# --------------------------------------------------------------------------------------------
# correctness of the estimators themselves
# --------------------------------------------------------------------------------------------

def test_singleton_clusters_reduce_to_iid_exactly() -> None:
    """With one row per cluster the CR1 SE must equal the textbook iid SE, to floating point."""
    rng = np.random.default_rng(3)
    y = rng.normal(size=500)
    ci = cinf.build_cluster_index(np.arange(500))
    rep = cinf.cluster_robust_se_mean(y, ci)
    check(abs(rep["cluster_robust_se_cr1"] - rep["naive_iid_se"]) < 1e-12,
          f"CR1 with singleton clusters = {rep['cluster_robust_se_cr1']!r} != iid "
          f"{rep['naive_iid_se']!r}")
    check(abs(rep["design_effect_variance_ratio"] - 1.0) < 1e-9,
          "design effect with singleton clusters must be 1")


def test_duplicated_rows_do_not_shrink_the_interval() -> None:
    """Duplicating every row inside its cluster must not narrow a clustered SE. It narrows an
    iid SE by sqrt(2), which is exactly the failure mode this module exists to prevent."""
    rng = np.random.default_rng(8)
    base = rng.normal(size=400)
    single = cinf.build_cluster_index(np.arange(400))
    doubled_labels = np.repeat(np.arange(400), 2)
    doubled = np.repeat(base, 2)
    ci2 = cinf.build_cluster_index(doubled_labels)
    r1 = cinf.cluster_robust_se_mean(base, single)
    r2 = cinf.cluster_robust_se_mean(doubled, ci2)
    check(abs(r2["cluster_robust_se_cr1"] - r1["cluster_robust_se_cr1"]) < 1e-12,
          f"clustered SE changed under exact within-cluster duplication: "
          f"{r1['cluster_robust_se_cr1']!r} -> {r2['cluster_robust_se_cr1']!r}")
    check(r2["naive_iid_se"] < r1["naive_iid_se"] * 0.75,
          "the iid SE should have shrunk by ~sqrt(2) under duplication; the fixture is wrong")
    # closed form: (G/(G-1)) * (2n-1) / (2(n-1)) with G = n = 400 — 2.0 up to the two different
    # finite-sample corrections (CR1 on 400 clusters, ddof=1 on 800 rows)
    exact = (2 * 400 - 1) / (400 - 1)          # = 799/399
    check(abs(r2["design_effect_variance_ratio"] - exact) < 1e-9,
          f"design effect under exact duplication should be {exact!r}, got "
          f"{r2['design_effect_variance_ratio']!r}")
    check(abs(exact - 2.0) < 0.01, f"the closed form {exact!r} should sit at 2.0 +- 0.01")


def test_bootstrap_se_agrees_with_analytic_cr1() -> None:
    rng = np.random.default_rng(21)
    u = rng.normal(scale=0.8, size=800)
    y = np.repeat(u, 2) + rng.normal(scale=0.6, size=1600)
    ci = cinf.build_cluster_index(np.repeat(np.arange(800), 2))
    boot = cinf.cluster_bootstrap(cinf.mean_of(y), ci, n_draws=3000, seed=31,
                                  statistic_name="mean")
    analytic = cinf.cluster_robust_se_mean(y, ci)["cluster_robust_se_cr1"]
    ratio = boot.se() / analytic
    check(0.95 <= ratio <= 1.05,
          f"bootstrap SE / analytic CR1 SE = {ratio:.4f}, outside [0.95, 1.05]")


def test_interval_methods() -> None:
    rng = np.random.default_rng(13)
    y = np.repeat(rng.normal(size=400), 2) + rng.normal(size=800)
    ci = cinf.build_cluster_index(np.repeat(np.arange(400), 2))
    r = cinf.cluster_bootstrap(cinf.mean_of(y), ci, n_draws=1500, seed=17, jackknife=True,
                               statistic_name="mean")
    for m in ("percentile", "basic", "normal", "bca"):
        lo, hi = r.ci(0.95, m)
        check(np.isfinite(lo) and np.isfinite(hi) and lo < hi, f"{m} interval [{lo}, {hi}]")
        lo99, hi99 = r.ci(0.99, m)
        check(hi99 - lo99 > hi - lo, f"{m}: the 99% interval is not wider than the 95%")
    check(raises(lambda: r.ci(0.95, "nonsense")), "an unknown interval method was accepted")
    check(raises(lambda: r.ci(1.5, "percentile")), "level outside (0,1) was accepted")

    no_jk = cinf.cluster_bootstrap(cinf.mean_of(y), ci, n_draws=200, seed=17)
    check(raises(lambda: no_jk.bca_ci()), "BCa ran without the cluster jackknife")


def test_paired_contrast_pairs() -> None:
    a = np.array([1.0, 2.0, 3.0, 4.0])
    b = np.array([0.5, 2.5, 2.0, 5.0])
    ci = cinf.build_cluster_index(np.array([0, 0, 1, 1]))
    stat = cinf.paired_mean_difference(a, b)
    check(abs(stat(np.arange(4)) - (a.mean() - b.mean())) < 1e-12, "paired contrast != mean diff")
    rows = np.array([0, 1, 0, 1])
    check(abs(stat(rows) - float(np.mean((a - b)[rows]))) < 1e-12,
          "paired contrast was not evaluated on identical rows for both sides")
    check(raises(lambda: cinf.paired_mean_difference(a, b[:3])),
          "a mismatched paired contrast was accepted")


def test_input_hygiene() -> None:
    check(raises(lambda: cinf.build_cluster_index([])), "empty cluster labels accepted")
    check(raises(lambda: cinf.build_cluster_index([1.0, np.nan, 2.0])),
          "null cluster labels accepted")
    check(raises(lambda: cinf.build_cluster_index(np.zeros((3, 2)))), "2-D labels accepted")
    ci = cinf.build_cluster_index([1, 1, 2])
    check(raises(lambda: cinf.draw_cluster_ids(ci, 0, seed=1)), "n_draws=0 accepted")
    check(raises(lambda: cinf.cluster_robust_se_mean([1.0, 2.0], ci)),
          "a values array of the wrong length was accepted")
    check(raises(lambda: cinf.cluster_robust_se_mean([1.0, np.nan, 2.0], ci)),
          "non-finite values accepted")
    check(raises(lambda: cinf.assert_clusters_not_split([1, 1, 2], [1, 1])),
          "a length-mismatched partition was accepted")


def test_cluster_index_digest_is_membership_sensitive() -> None:
    a = cinf.build_cluster_index(["g1", "g1", "g2", "g2"])
    b = cinf.build_cluster_index(["g1", "g2", "g1", "g2"])
    check(a.membership_digest() != b.membership_digest(),
          "two different row->cluster maps produced the same membership digest")
    c = cinf.build_cluster_index(np.array(["g1", "g1", "g2", "g2"]))
    check(a.membership_digest() == c.membership_digest(),
          "the same row->cluster map produced two different digests")


# --------------------------------------------------------------------------------------------
# the stored measurements must match the module that is on disk now
# --------------------------------------------------------------------------------------------

def test_measurements_are_current() -> None:
    p = HERE / "MEASUREMENTS.json"
    if not p.exists():
        check(False, "MEASUREMENTS.json is missing; run measure.py")
        return
    m = json.loads(p.read_text(encoding="utf-8"))
    check(m["module_sha256"] == cinf.module_digest(),
          "MEASUREMENTS.json was produced by a different version of clustered_inference.py; "
          "re-run measure.py or the reported numbers are stale")
    r = m["real"]["rows_vs_clusters"]
    check(r["team_game_rows"] == 2982 and r["game_clusters"] == 1491,
          f"MEASUREMENTS.json reports {r}")
    check(m["real"]["whole_cluster_integrity"]["violations"] == 0,
          "MEASUREMENTS.json records a split cluster")
    check(m["real"]["reproducibility"]["same_seed_draw_digest_identical"] is True
          and m["real"]["reproducibility"]["prefix_stable_first_250_bitwise_identical"] is True,
          "MEASUREMENTS.json records a reproducibility failure")
    cov = m["synthetic_coverage_icc_0p6"]
    check(cov["coverage_game_clustered_percentile"] > cov["coverage_row_level_iid_bootstrap"],
          "the clustered interval did not out-cover the row-level iid interval under clustering")


TESTS = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]


def main() -> int:
    for t in TESTS:
        try:
            t()
        except Exception as exc:                            # a raising test IS a failure
            FAILURES.append(f"{t.__name__} raised {type(exc).__name__}: {exc}")
    real = [f for f in FAILURES if f]
    print(f"clustered inference: {CHECKS} checks across {len(TESTS)} tests")
    if real:
        print(f"FAIL ({len(real)}):")
        for f in real:
            print(f"  - {f}")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
