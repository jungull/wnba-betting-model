"""Bind ``clustered_inference`` to the REAL possession universe and to a synthetic ground truth.

Read-only. Writes exactly one file, MEASUREMENTS.json, inside this node's own directory.

Two kinds of measurement, kept apart on purpose:

  REAL      structural facts about the 2,982-row / 1,491-cluster universe, plus the design effect
            of clustering on the target column. No model is fitted, no arm is scored, no
            prediction column is contrasted with an outcome. The realised target is read as a
            COLUMN OF NUMBERS to size the clustering penalty; nothing here is a performance claim
            about the incumbent or about any challenger.

  SYNTHETIC coverage of the intervals against a known parameter, where "known" is possible.
            Coverage cannot be measured on real data because the true value is not observable.

Run:  python measure.py
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True          # never leave a .pyc outside this node's directory

import json                                                                   # noqa: E402
from pathlib import Path                                                      # noqa: E402

import numpy as np                                                            # noqa: E402
import pandas as pd                                                           # noqa: E402

HERE = Path(__file__).resolve().parent
PROGRAM = HERE.parents[1]                       # experiments/player_program
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(PROGRAM))

import clustered_inference as cinf                                            # noqa: E402

SEED = 20260804
N_DRAWS = 2000


# --------------------------------------------------------------------------------------------
# REAL universe
# --------------------------------------------------------------------------------------------

def _icc(y: np.ndarray, ci) -> dict:
    """One-way ANOVA intraclass correlation over equal-sized clusters. m=2 here."""
    m = int(ci.sizes[0])
    if not np.all(ci.sizes == m):
        return {"unavailable": "unequal cluster sizes"}
    blocks = np.stack([y[ci.rows_of(c)] for c in range(ci.n_clusters)])
    grand = blocks.mean()
    cmeans = blocks.mean(axis=1)
    G = ci.n_clusters
    msb = m * float(((cmeans - grand) ** 2).sum()) / (G - 1)
    msw = float(((blocks - cmeans[:, None]) ** 2).sum()) / (G * (m - 1))
    icc = (msb - msw) / (msb + (m - 1) * msw) if (msb + (m - 1) * msw) != 0 else float("nan")
    return {"icc": float(icc), "implied_design_effect_1_plus_icc": float(1.0 + icc),
            "sd": float(y.std(ddof=1)), "mean": float(y.mean())}


def real_universe() -> dict:
    import possession_features as pf         # READ-ONLY; load_universe writes nothing

    u = pf.load_universe()
    F = u.frame
    out: dict = {"source": "possession_features.load_universe() (read-only)",
                 "row_universe_digest": u.contract["row_universe_digest"],
                 "universe_contract_id": u.contract.get("contract_id")}

    ci = cinf.build_cluster_index(F["game_id"])
    out["cluster_index"] = ci.describe()
    out["rows_vs_clusters"] = {
        "team_game_rows": ci.n_rows,
        "game_clusters": ci.n_clusters,
        "rows_per_cluster_exact": ci.size_distribution(),
        "statement": (f"{ci.n_rows} team-game rows over {ci.n_clusters} game clusters; every "
                      f"cluster has exactly two rows, so the effective sample size for any "
                      f"game-level shock is {ci.n_clusters}, not {ci.n_rows}"),
    }

    # ---- a cluster must not be split by any partition the program uses --------------------
    splits = {}
    for name, col in (("season", F["season"]), ("season_type", F["season_type"]),
                      ("game_date", F["game_date"]), ("pace_level", F["pace_level"]),
                      ("pace_source", F["pace_source"])):
        try:
            splits[name] = cinf.assert_clusters_not_split(F["game_id"], col,
                                                          partition_name=name)
        except cinf.ClusteredInferenceFailure as exc:
            per = pd.DataFrame({"c": F["game_id"].to_numpy(), "p": col.to_numpy()})
            n_split = int((per.groupby("c", sort=False)["p"].nunique() > 1).sum())
            splits[name] = {
                "partition": name, "clusters_split": n_split,
                "clusters": int(F["game_id"].nunique()),
                "guard": "RAISED",
                "message": str(exc)[:400],
                "consequence": (f"{name} is NOT a legal stratification variable for a game-"
                                f"clustered bootstrap: {n_split} games have two different "
                                f"{name} values across their two team rows, so stratifying on "
                                f"it would require splitting those games. Reported, not "
                                f"resolved"),
            }

    folds = pf.chronological_folds(u)
    fold_reports = {}
    for f in folds:
        member = pd.Series("unused", index=F.index, dtype=object)
        member.loc[f.train_index] = "train"
        member.loc[f.test_index] = "test"
        rep = cinf.assert_clusters_not_split(F["game_id"], member,
                                             partition_name=f"fold:{f.fold_id}")
        train_games = int(F.loc[f.train_index, "game_id"].nunique())
        test_games = int(F.loc[f.test_index, "game_id"].nunique())
        fold_reports[f.fold_id] = {
            "test_season": f.season, "cutoff_date": f.cutoff_date,
            "train_rows": int(len(f.train_index)), "train_game_clusters": train_games,
            "test_rows": int(len(f.test_index)), "test_game_clusters": test_games,
            "clusters_split_train_vs_test": rep["clusters_split"],
            "train_test_row_overlap": int(len(f.train_index.intersection(f.test_index))),
        }
    splits["chronological_folds"] = fold_reports

    tested = pd.Index([])
    for f in folds:
        tested = tested.union(f.test_index)
    never = F.index.difference(tested)
    splits["rows_never_in_any_test_fold"] = {
        "rows": int(len(never)), "game_clusters": int(F.loc[never, "game_id"].nunique()),
        "seasons": sorted(int(s) for s in F.loc[never, "season"].unique()),
        "note": ("the earliest season can never be a test season under an expanding window; it "
                 "is training-only. Reported because a reader who sums the test folds gets "
                 "fewer rows than the universe and must not read that as a missing row"),
    }
    out["partitions"] = splits

    # ---- whole-cluster integrity of actual draws, measured not asserted -------------------
    draws = cinf.draw_cluster_ids(ci, 500, SEED)
    sizes = ci.sizes
    violations = 0
    partial_examples: list[str] = []
    codes = ci.codes
    for b in range(draws.shape[0]):
        rows = cinf.rows_for_cluster_draw(ci, draws[b])
        got = np.bincount(codes[rows], minlength=ci.n_clusters)
        want = np.bincount(draws[b], minlength=ci.n_clusters) * sizes
        bad = np.flatnonzero(got != want)
        if bad.size:
            violations += int(bad.size)
            if len(partial_examples) < 5:
                partial_examples.append(f"draw {b} cluster {ci.keys[bad[0]]}")
    out["whole_cluster_integrity"] = {
        "draws_checked": int(draws.shape[0]),
        "rule": ("for every draw and every game g: rows(g) present == times g was drawn * "
                 "size(g). A split game breaks this equality"),
        "violations": violations, "examples": partial_examples,
        "distinct_clusters_per_draw": {
            "min": int(min(np.unique(draws[b]).shape[0] for b in range(draws.shape[0]))),
            "max": int(max(np.unique(draws[b]).shape[0] for b in range(draws.shape[0]))),
            "mean": float(np.mean([np.unique(draws[b]).shape[0]
                                   for b in range(draws.shape[0])])),
            "expected_1_minus_1_over_e": float((1 - np.exp(-1)) * ci.n_clusters),
        },
    }

    # ---- the price of clustering, on the real target column -------------------------------
    #      DESCRIPTIVE ONLY: the mean of an observed column. Not a metric, not a comparison.
    tgt = F[pf.TARGET_COLUMN].to_numpy(dtype=float)
    out["design_effect_on_target_column"] = {
        "column": pf.TARGET_COLUMN,
        "what_this_is": ("the mean of an observed outcome column and the width penalty that "
                         "clustering imposes on it. No prediction column is read; this is not "
                         "a performance number for any arm"),
        **cinf.cluster_robust_se_mean(tgt, ci),
    }
    gap = F["pace_gap"].to_numpy(dtype=float)
    out["design_effect_on_pace_gap"] = {
        "column": "pace_gap (cutoff-valid feature, own minus opponent pace estimate)",
        **cinf.cluster_robust_se_mean(gap, ci),
    }

    out["within_game_structure"] = {
        "what_this_is": ("the one-way ANOVA intraclass correlation of each column across the two "
                         "rows of a game. For clusters of size 2 the design effect of the mean "
                         "is 1 + icc, which is why icc is reported next to it"),
        "columns": {c: _icc(F[c].to_numpy(dtype=float), ci)
                    for c in (pf.TARGET_COLUMN, "projected_team_off_possessions",
                              "team_pace_estimate", "pace_gap", "pace_evidence_depth",
                              "log_projected_team_off_possessions")},
    }

    # ---- the bootstrap itself, on the real cluster structure -------------------------------
    res = cinf.cluster_bootstrap(cinf.mean_of(tgt), ci, n_draws=N_DRAWS, seed=SEED,
                                 jackknife=True, statistic_name=f"mean({pf.TARGET_COLUMN})")
    out["real_bootstrap"] = cinf.bootstrap_receipt(
        res, universe={"row_universe_digest": u.contract["row_universe_digest"],
                       "team_game_rows": ci.n_rows, "game_clusters": ci.n_clusters},
        methods=("percentile", "basic", "normal", "bca"))
    out["real_bootstrap"]["se_vs_analytic_cr1"] = {
        "bootstrap_se": res.se(),
        "analytic_cr1_se": out["design_effect_on_target_column"]["cluster_robust_se_cr1"],
        "ratio": res.se() / out["design_effect_on_target_column"]["cluster_robust_se_cr1"],
        "note": ("two independent routes to the same standard error. A ratio far from 1 would "
                 "mean one of them is wrong"),
    }

    # ---- stratified by season: clusters resampled within season ----------------------------
    ci_s = cinf.build_cluster_index(F["game_id"], strata=F["season"])
    res_s = cinf.cluster_bootstrap(cinf.mean_of(tgt), ci_s, n_draws=500, seed=SEED,
                                   statistic_name=f"mean({pf.TARGET_COLUMN}) | season-stratified")
    out["season_stratified"] = {
        "clusters_per_stratum": ci_s.describe()["clusters_per_stratum"],
        "se": res_s.se(), "ci_95_percentile": list(res_s.percentile_ci(0.95)),
        "seed": SEED, "n_draws": 500,
        "note": ("a season is a union of whole games, so stratifying by season never splits a "
                 "game; build_cluster_index refuses a stratum assignment that would"),
    }

    # ---- how many draws is enough, measured rather than assumed ----------------------------
    sens = {}
    for nd in (250, 500, 1000, 2000, 4000):
        r = cinf.cluster_bootstrap(cinf.mean_of(tgt), ci, n_draws=nd, seed=SEED,
                                   statistic_name="draw-count sensitivity")
        lo, hi = r.percentile_ci(0.95)
        sens[str(nd)] = {"se": r.se(), "ci_95": [lo, hi], "width": hi - lo}
    out["draw_count_sensitivity"] = {
        "seed": SEED, "by_n_draws": sens,
        "analytic_cr1_se": out["design_effect_on_target_column"]["cluster_robust_se_cr1"],
        "note": ("the SE is stable well before 2,000 draws; the percentile ENDPOINTS keep "
                 "moving longer than the SE does, which is why an endpoint should not be quoted "
                 "to more digits than this table supports"),
    }

    # ---- reproducibility, measured ----------------------------------------------------------
    again = cinf.cluster_bootstrap(cinf.mean_of(tgt), ci, n_draws=N_DRAWS, seed=SEED,
                                   statistic_name=f"mean({pf.TARGET_COLUMN})")
    short = cinf.cluster_bootstrap(cinf.mean_of(tgt), ci, n_draws=250, seed=SEED,
                                   statistic_name="prefix check")
    other = cinf.cluster_bootstrap(cinf.mean_of(tgt), ci, n_draws=N_DRAWS, seed=SEED + 1,
                                   statistic_name="different seed")
    out["reproducibility"] = {
        "same_seed_draw_digest_identical": bool(again.draw_digest == res.draw_digest),
        "same_seed_replicates_bitwise_identical":
            bool(np.array_equal(again.replicates, res.replicates)),
        "max_abs_replicate_difference_same_seed":
            float(np.max(np.abs(again.replicates - res.replicates))),
        "prefix_stable_first_250_bitwise_identical":
            bool(np.array_equal(short.replicates, res.replicates[:250])),
        "different_seed_changes_draws": bool(other.draw_digest != res.draw_digest),
        "different_seed_se": other.se(),
        "same_seed_se": res.se(),
        "statement": ("replicate b is a function of (seed, b) alone via "
                      "SeedSequence(seed).spawn(n_draws)[b]"),
    }
    return out


# --------------------------------------------------------------------------------------------
# SYNTHETIC ground truth — the only place coverage can be measured
# --------------------------------------------------------------------------------------------

def synthetic_coverage(*, n_clusters: int = 1491, cluster_size: int = 2, icc: float = 0.6,
                       n_sims: int = 400, n_draws: int = 400, seed: int = 424242) -> dict:
    """Coverage of a 95% interval for a known mean, under real-shaped clustering.

    DGP: ``y[g,i] = mu + u[g] + e[g,i]``, ``u ~ N(0, icc)``, ``e ~ N(0, 1-icc)``. mu = 0 and is
    KNOWN, which is exactly what the real universe cannot give us.

    Three intervals are compared on identical data: the game-clustered percentile bootstrap, the
    naive ROW-level iid bootstrap (the mistake this module exists to prevent), and the naive iid
    normal interval.
    """
    rng = np.random.default_rng(seed)
    labels = np.repeat(np.arange(n_clusters), cluster_size)
    ci = cinf.build_cluster_index(labels)
    hit_cluster = hit_row = hit_iid = 0
    width_cluster = width_row = width_iid = 0.0
    n = n_clusters * cluster_size
    z = 1.959963984540054
    for s in range(n_sims):
        u = rng.normal(0.0, np.sqrt(icc), size=n_clusters)
        e = rng.normal(0.0, np.sqrt(1.0 - icc), size=n)
        y = np.repeat(u, cluster_size) + e

        r = cinf.cluster_bootstrap(cinf.mean_of(y), ci, n_draws=n_draws, seed=seed + s,
                                   statistic_name="synthetic mean")
        lo, hi = r.percentile_ci(0.95)
        hit_cluster += int(lo <= 0.0 <= hi)
        width_cluster += hi - lo

        idx = rng.integers(0, n, size=(n_draws, n))       # row-level iid bootstrap — WRONG here
        reps = y[idx].mean(axis=1)
        lo2, hi2 = np.quantile(reps, [0.025, 0.975], method="linear")
        hit_row += int(lo2 <= 0.0 <= hi2)
        width_row += float(hi2 - lo2)

        se = float(np.std(y, ddof=1) / np.sqrt(n))
        hit_iid += int(abs(y.mean()) <= z * se)
        width_iid += 2 * z * se

    return {
        "dgp": (f"y[g,i] = mu + u[g] + e[g,i]; mu=0 known; var(u)={icc}, var(e)={1 - icc}; "
                f"{n_clusters} clusters x {cluster_size} rows = {n} rows, matching the shape of "
                f"the real universe"),
        "n_sims": n_sims, "n_bootstrap_draws": n_draws, "seed": seed,
        "nominal_level": 0.95,
        "coverage_game_clustered_percentile": hit_cluster / n_sims,
        "coverage_row_level_iid_bootstrap": hit_row / n_sims,
        "coverage_row_level_iid_normal": hit_iid / n_sims,
        "mean_width_game_clustered": width_cluster / n_sims,
        "mean_width_row_level_iid_bootstrap": width_row / n_sims,
        "mean_width_row_level_iid_normal": width_iid / n_sims,
        "theoretical_design_effect_1_plus_rho_times_m_minus_1": 1.0 + icc * (cluster_size - 1),
        "monte_carlo_se_of_a_coverage_estimate": float(np.sqrt(0.95 * 0.05 / n_sims)),
        "reading": ("the row-level intervals are the ones that under-cover; the size of the gap "
                    "is the cost of treating two rows of one game as two independent draws"),
    }


def synthetic_zero_icc(*, n_sims: int = 300, n_draws: int = 400, seed: int = 99001) -> dict:
    """Control: with NO intra-cluster correlation, clustering must cost (almost) nothing."""
    d = synthetic_coverage(n_clusters=600, cluster_size=2, icc=1e-9, n_sims=n_sims,
                           n_draws=n_draws, seed=seed)
    d["purpose"] = ("a negative control. If the clustered interval were merely wider by "
                    "construction it would over-cover here too; it should not")
    return d


def main() -> int:
    out = {
        "schema": "clustered_inference_measurements/1",
        "node_id": "I10_GENERIC_CLUSTERED_INFERENCE",
        "epistemic_status": ("INFRASTRUCTURE. Utilities in an isolated namespace. Shared "
                             "adoption requires a separate review node; nothing here amends a "
                             "shared contract."),
        "module_sha256": cinf.module_digest(),
        "global_seed": SEED,
        "real": real_universe(),
        "synthetic_coverage_icc_0p6": synthetic_coverage(),
        "synthetic_coverage_icc_0": synthetic_zero_icc(),
    }
    p = cinf.write_json(HERE / "MEASUREMENTS.json", out)
    print(f"wrote {p}")
    print(json.dumps({k: out["real"][k] for k in ("rows_vs_clusters",)}, indent=1,
                     default=str)[:800])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
