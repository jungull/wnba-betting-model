"""Synthetic-data tests for the evaluation harness (ROADMAP Phase 0.5).

Runnable two ways:
    python -m pytest tests/ -q          (if pytest is installed)
    python tests/test_evalharness.py    (plain runner, no dependencies)

Coverage map (letters per the harness build spec):
  (a) outer/inner/calibration splits provably disjoint and time-ordered
  (b) a deliberately time-leaking tuning setup raises
  (c) registry refuses unregistered / late-registered evaluation; run numbers
  (d) locked holdout refuses exposure before claim and refuses a second claim
  (e) bootstrap CIs seed-reproducible; cluster counts correct
  (f) gate truth-table: PASS / FAIL-on-pooled / FAIL-on-CI / FAIL-on-season /
      FAIL-on-coverage (+ joint hook, + not-provided visibility)
  (g) metrics match hand-computed values
  (+) compare joins/refusals, frozen-baseline tamper check, leaderboard render
"""

from __future__ import annotations

import json
import sys
import tempfile
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evalharness import (  # noqa: E402
    GateThresholds,
    register,
    begin_evaluation,
    record_evaluation,
    list_evaluations,
    read_records,
    walk_forward_by_season,
    walk_forward_by_date_blocks,
    inner_tuning_splits,
    calibration_carveout,
    declare_holdout,
    claim_holdout,
    expose_holdout,
    strip_holdout,
    compare_to_incumbent,
    cluster_bootstrap_ci,
    load_frozen_baselines,
    render_leaderboards,
    LeakageError,
    HoldoutError,
    HoldoutNotClaimedError,
    HoldoutAlreadyClaimedError,
    UnregisteredExperimentError,
    LateRegistrationError,
    DuplicateRegistrationError,
    ComparisonError,
    FrozenBaselineTamperedError,
)
from evalharness import metrics as M  # noqa: E402
from evalharness.baselines import FROZEN_BASELINES_PATH  # noqa: E402

TH = {"min_improvement": 0.10, "harm_ci_bound": 0.05, "per_season_tolerance": 0.15}


def _raises(exc_type, fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except exc_type:
        return True
    except Exception as e:  # pragma: no cover
        raise AssertionError(
            f"expected {exc_type.__name__}, got {type(e).__name__}: {e}"
        ) from e
    raise AssertionError(f"expected {exc_type.__name__}, nothing raised")


def make_games(seasons=(2022, 2023, 2024), dates_per_season=30, games_per_date=2):
    """Deterministic synthetic schedule: seasons in disjoint calendar years."""
    rows = []
    gid = 0
    for s in seasons:
        start = pd.Timestamp(f"{s}-05-15")
        for d in range(dates_per_season):
            date = start + pd.Timedelta(days=d)
            for g in range(games_per_date):
                gid += 1
                rows.append({
                    "game_id": f"G{gid:05d}",
                    "game_date": date,
                    "season": s,
                    "home_team": f"T{(gid % 6) + 1}",
                })
    return pd.DataFrame(rows)


# ===========================================================================
# (a) splits: provably disjoint and time-ordered
# ===========================================================================

def test_a_outer_season_splits_disjoint_and_time_ordered():
    df = make_games()
    splits = walk_forward_by_season(df, min_train_seasons=1)
    assert len(splits) == 2, "3 seasons, expanding -> 2 outer folds"
    dates = pd.to_datetime(df["game_date"])
    for sp in splits:
        assert len(np.intersect1d(sp.train_idx, sp.test_idx)) == 0
        assert dates.loc[sp.train_idx].max() < dates.loc[sp.test_idx].min(), \
            "max(train_time) must be < min(test_time)"
        assert sp.train_end < sp.test_start
    # expanding: second fold trains on both earlier seasons
    assert set(df.loc[splits[1].train_idx, "season"]) == {2022, 2023}
    assert set(df.loc[splits[1].test_idx, "season"]) == {2024}


def test_a_outer_date_block_splits_disjoint_and_time_ordered():
    df = make_games(seasons=(2024,), dates_per_season=60)
    splits = walk_forward_by_date_blocks(df, block_days=7, min_train_days=21)
    assert len(splits) >= 4
    dates = pd.to_datetime(df["game_date"])
    seen_test = set()
    for sp in splits:
        assert len(np.intersect1d(sp.train_idx, sp.test_idx)) == 0
        assert dates.loc[sp.train_idx].max() < dates.loc[sp.test_idx].min()
        assert not (seen_test & set(sp.test_idx)), "test blocks must not overlap"
        seen_test |= set(sp.test_idx)
    # expanding train: later folds contain earlier folds' train rows
    assert set(splits[0].train_idx) <= set(splits[-1].train_idx)


def test_a_inner_splits_strictly_inside_outer_train():
    df = make_games()
    outer = walk_forward_by_season(df)[1]        # train 2022+2023, test 2024
    folds = inner_tuning_splits(df, outer, n_folds=3)
    assert len(folds) == 3
    dates = pd.to_datetime(df["game_date"])
    outer_train = set(outer.train_idx)
    for f in folds:
        assert set(f.train_idx) <= outer_train and set(f.val_idx) <= outer_train, \
            "inner folds must draw only from the outer training window"
        assert len(np.intersect1d(f.train_idx, f.val_idx)) == 0
        assert dates.loc[f.train_idx].max() < dates.loc[f.val_idx].min()
        assert f.val_end < outer.test_start


def test_a_calibration_carveout_disjoint_time_ordered():
    df = make_games()
    outer = walk_forward_by_season(df)[1]
    cal = calibration_carveout(df, outer, calib_frac=0.25)
    dates = pd.to_datetime(df["game_date"])
    assert set(cal.fit_idx) | set(cal.calib_idx) == set(outer.train_idx)
    assert len(np.intersect1d(cal.fit_idx, cal.calib_idx)) == 0
    assert dates.loc[cal.fit_idx].max() < dates.loc[cal.calib_idx].min()
    assert cal.calib_end < outer.test_start, "calibration precedes the test window"


def test_a_interleaved_seasons_raise():
    # a "season" whose dates sit in the MIDDLE of another season's dates:
    # train would then contain games played after the test set begins, and the
    # splitter must refuse to construct that fold.
    df = make_games(seasons=(2024,), dates_per_season=20)
    mid = (df["game_date"] >= pd.Timestamp("2024-05-20")) & \
          (df["game_date"] <= pd.Timestamp("2024-05-23"))
    df.loc[mid, "season"] = 2025                # interleaved label
    _raises(LeakageError, walk_forward_by_season, df)


# ===========================================================================
# (b) deliberately time-leaking tuning setup raises
# ===========================================================================

def test_b_leaky_inner_tuning_raises():
    df = make_games()
    outer = walk_forward_by_season(df)[1]
    leaky = np.concatenate([outer.train_idx, outer.test_idx[:10]])
    _raises(LeakageError, inner_tuning_splits, df, outer, candidate_idx=leaky)


# ===========================================================================
# (c) registry refuses unregistered / late-registered evaluation
# ===========================================================================

def test_c_registry_refuses_unregistered():
    with tempfile.TemporaryDirectory() as tmp:
        reg = Path(tmp) / "registry.jsonl"
        _raises(UnregisteredExperimentError, begin_evaluation,
                "never_registered", registry_path=reg)


def test_c_registry_refuses_late_registration():
    with tempfile.TemporaryDirectory() as tmp:
        reg = Path(tmp) / "registry.jsonl"
        register("exp_late", "h", "f", "margin_mae", TH, "incumbent", "A",
                 registry_path=reg)
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        _raises(LateRegistrationError, begin_evaluation, "exp_late",
                registry_path=reg, eval_time=past)
        # equal timestamps are also refused (not strictly earlier)
        reg_rec = read_records(reg)[-1]
        _raises(LateRegistrationError, begin_evaluation, "exp_late",
                registry_path=reg, eval_time=reg_rec["registered_at"])


def test_c_registry_duplicate_registration_raises():
    with tempfile.TemporaryDirectory() as tmp:
        reg = Path(tmp) / "registry.jsonl"
        register("exp_dup", "h", "f", "margin_mae", TH, "inc", "A", registry_path=reg)
        _raises(DuplicateRegistrationError, register, "exp_dup", "h2", "f2",
                "margin_mae", TH, "inc", "A", registry_path=reg)


def test_c_registry_run_numbers_visible():
    with tempfile.TemporaryDirectory() as tmp:
        reg = Path(tmp) / "registry.jsonl"
        register("exp_runs", "h", "f", "margin_mae", TH, "inc", "A", registry_path=reg)
        r1 = record_evaluation("exp_runs", {"metric": 9.5}, registry_path=reg)
        r2 = record_evaluation("exp_runs", {"metric": 9.4}, registry_path=reg)
        assert r1["run_number"] == 1 and r2["run_number"] == 2
        evs = list_evaluations("exp_runs", registry_path=reg)
        assert [e["run_number"] for e in evs] == [1, 2], \
            "repeated experimentation must be recorded, not hidden"


# ===========================================================================
# (d) locked holdout: dark until claimed; single, irreversible claim
# ===========================================================================

def _holdout_setup(reg):
    df = make_games()
    declare_holdout("final_2024", seasons=[2024],
                    description="locked final season", registry_path=reg)
    register("exp_hold", "h", "f", "margin_mae", TH, "inc", "A", registry_path=reg)
    return df


def test_d_holdout_dark_until_claimed():
    with tempfile.TemporaryDirectory() as tmp:
        reg = Path(tmp) / "registry.jsonl"
        df = _holdout_setup(reg)
        work = strip_holdout(df, "final_2024", registry_path=reg)
        assert set(work["season"]) == {2022, 2023}, "strip removes holdout rows"
        _raises(HoldoutNotClaimedError, expose_holdout, df, "final_2024",
                "exp_hold", registry_path=reg)


def test_d_holdout_refuses_second_claim():
    with tempfile.TemporaryDirectory() as tmp:
        reg = Path(tmp) / "registry.jsonl"
        df = _holdout_setup(reg)
        claim_holdout("final_2024", "exp_hold", registry_path=reg)
        rows = expose_holdout(df, "final_2024", "exp_hold", registry_path=reg)
        assert set(rows["season"]) == {2024}
        register("exp_hold2", "h", "f", "margin_mae", TH, "inc", "A", registry_path=reg)
        _raises(HoldoutAlreadyClaimedError, claim_holdout, "final_2024",
                "exp_hold2", registry_path=reg)
        _raises(HoldoutAlreadyClaimedError, claim_holdout, "final_2024",
                "exp_hold", registry_path=reg)   # even the claimant cannot re-claim
        # claim is on the append-only ledger
        kinds = [r["kind"] for r in read_records(reg)]
        assert kinds.count("holdout_claimed") == 1


def test_d_holdout_expose_only_for_claimant():
    with tempfile.TemporaryDirectory() as tmp:
        reg = Path(tmp) / "registry.jsonl"
        df = _holdout_setup(reg)
        register("exp_other", "h", "f", "margin_mae", TH, "inc", "A", registry_path=reg)
        claim_holdout("final_2024", "exp_hold", registry_path=reg)
        _raises(HoldoutNotClaimedError, expose_holdout, df, "final_2024",
                "exp_other", registry_path=reg)


def test_d_holdout_claim_requires_registration_and_declaration():
    with tempfile.TemporaryDirectory() as tmp:
        reg = Path(tmp) / "registry.jsonl"
        df = _holdout_setup(reg)
        _raises(UnregisteredExperimentError, claim_holdout, "final_2024",
                "ghost_experiment", registry_path=reg)
        _raises(HoldoutError, declare_holdout, "final_2024", seasons=[2024],
                registry_path=reg)   # redeclare refused


# ===========================================================================
# (e) bootstrap: seed-reproducible, cluster counts correct
# ===========================================================================

def test_e_bootstrap_seed_reproducible_and_cluster_counts():
    rng = np.random.default_rng(7)
    n_dates, per = 40, 3
    dates = np.repeat(np.arange(n_dates), per)
    vals = rng.normal(0.1, 1.0, size=n_dates * per)
    a = cluster_bootstrap_ci(vals, dates, n_boot=500, seed=123)
    b = cluster_bootstrap_ci(vals, dates, n_boot=500, seed=123)
    c = cluster_bootstrap_ci(vals, dates, n_boot=500, seed=124)
    assert (a["low"], a["high"]) == (b["low"], b["high"]), "same seed -> same CI"
    assert (a["low"], a["high"]) != (c["low"], c["high"]), "different seed -> different CI"
    assert a["n_clusters"] == n_dates
    mb1 = cluster_bootstrap_ci(vals, dates, n_boot=500, seed=9,
                               method="moving_block", block_len=5)
    mb2 = cluster_bootstrap_ci(vals, dates, n_boot=500, seed=9,
                               method="moving_block", block_len=5)
    assert (mb1["low"], mb1["high"]) == (mb2["low"], mb2["high"])
    assert mb1["block_len"] == 5 and mb1["n_clusters"] == n_dates
    assert a["low"] < a["high"]


def test_e_compare_seed_reproducible_and_team_sensitivity():
    with tempfile.TemporaryDirectory() as tmp:
        reg = Path(tmp) / "registry.jsonl"
        register("exp_seed", "h", "f", "margin_mae", TH, "inc", "A", registry_path=reg)
        ch, inc = _gate_frames(_deltas_constant(0.3, jitter=0.2))
        r1 = compare_to_incumbent(ch, inc, experiment_id="exp_seed",
                                  registry_path=reg, seed=42, n_boot=400,
                                  record=False)
        r2 = compare_to_incumbent(ch, inc, experiment_id="exp_seed",
                                  registry_path=reg, seed=42, n_boot=400,
                                  record=False)
        assert (r1.ci_low, r1.ci_high) == (r2.ci_low, r2.ci_high)
        n_dates = ch["game_date"].nunique()
        assert r1.n_clusters == n_dates, "primary clustering = game dates"
        assert r1.ci_sensitivity_team is not None
        assert r1.ci_sensitivity_team[2] == ch["home_team"].nunique(), \
            "team sensitivity clusters = distinct teams"


# ===========================================================================
# (f) gate truth-table on engineered residual sets
# ===========================================================================

def _deltas_constant(value, jitter=0.0, seasons=(2022, 2023, 2024), n_dates=20):
    """Per-date delta plan: {season: [delta per date]} (constant + tiny wobble)."""
    return {
        s: [value + (jitter * ((d % 2) * 2 - 1)) for d in range(n_dates)]
        for s in seasons
    }


def _gate_frames(date_deltas, games_per_date=2):
    """Build challenger/incumbent prediction frames whose per-game paired
    delta (|inc resid| - |ch resid|) equals the planned per-date delta:
    y_true = 0, challenger predicts 5, incumbent predicts 5 + delta."""
    rows_ch, rows_inc = [], []
    gid = 0
    for season, deltas in date_deltas.items():
        start = pd.Timestamp(f"{season}-05-15")
        for d, delta in enumerate(deltas):
            date = start + pd.Timedelta(days=d)
            for g in range(games_per_date):
                gid += 1
                game_id = f"G{gid:05d}"
                rows_ch.append({
                    "game_id": game_id, "game_date": date, "season": season,
                    "home_team": f"T{(gid % 6) + 1}",
                    "y_true": 0.0, "y_pred": 5.0,
                })
                rows_inc.append({
                    "game_id": game_id, "y_true": 0.0, "y_pred": 5.0 + delta,
                })
    return pd.DataFrame(rows_ch), pd.DataFrame(rows_inc)


def _run_gate_case(date_deltas, *, coverage=(0.95, 0.95), joint=None, tag="case"):
    with tempfile.TemporaryDirectory() as tmp:
        reg = Path(tmp) / "registry.jsonl"
        register(f"exp_{tag}", "gate truth-table case", "synthetic",
                 "margin_mae", TH, "incumbent_structural_chains", "A",
                 registry_path=reg)
        ch, inc = _gate_frames(date_deltas)
        res = compare_to_incumbent(
            ch, inc, experiment_id=f"exp_{tag}", registry_path=reg,
            coverage=coverage, joint_check=joint, seed=1, n_boot=800,
        )
        ledger = list_evaluations(f"exp_{tag}", registry_path=reg)
        assert len(ledger) == 1 and ledger[0]["results"]["verdict"] == res.verdict, \
            "verdict + numbers must land on the registry ledger"
        return res


def test_f_gate_pass():
    res = _run_gate_case(_deltas_constant(0.3, jitter=0.05),
                         joint=lambda: True, tag="pass")
    assert res.promote and res.verdict == "PASS" and res.failed_gates == []
    assert all(v is True for v in res.gates.values()), res.gates
    assert abs(res.pooled_improvement - 0.3) < 1e-9


def test_f_gate_fail_on_pooled():
    res = _run_gate_case(_deltas_constant(0.02, jitter=0.005), tag="pooled")
    assert res.gates["gate1_pooled_improvement"] is False
    assert res.gates["gate2_ci_excludes_harm"] is True, \
        "tiny-but-consistent improvement fails on size, not on harm"
    assert res.gates["gate3_per_season_non_inferiority"] is True
    assert not res.promote and res.failed_gates == ["gate1_pooled_improvement"]


def test_f_gate_fail_on_ci():
    # date-level alternation +3.00 / -2.76: pooled +0.12 (clears gate 1) but
    # between-date variance is huge -> 90% CI reaches past -0.05 harm bound.
    plan = {
        s: [3.0 if d % 2 == 0 else -2.76 for d in range(20)]
        for s in (2022, 2023, 2024)
    }
    res = _run_gate_case(plan, tag="ci")
    assert abs(res.pooled_improvement - 0.12) < 1e-9
    assert res.gates["gate1_pooled_improvement"] is True
    assert res.gates["gate2_ci_excludes_harm"] is False, \
        f"CI [{res.ci_low}, {res.ci_high}] should include harm beyond -0.05"
    assert res.gates["gate3_per_season_non_inferiority"] is True
    assert not res.promote and res.failed_gates == ["gate2_ci_excludes_harm"]


def test_f_gate_fail_on_season():
    plan = _deltas_constant(0.3, seasons=(2022, 2023))
    plan[2024] = [-0.2] * 20                     # one season degrades > 0.15
    res = _run_gate_case(plan, tag="season")
    assert res.gates["gate1_pooled_improvement"] is True
    assert res.gates["gate2_ci_excludes_harm"] is True
    assert res.gates["gate3_per_season_non_inferiority"] is False
    assert res.gate_details["gate3_per_season_non_inferiority"]["worst_season"] == "2024"
    assert not res.promote and res.failed_gates == ["gate3_per_season_non_inferiority"]


def test_f_gate_fail_on_coverage():
    res = _run_gate_case(_deltas_constant(0.3, jitter=0.05),
                         coverage=(0.90, 0.95), tag="cov")
    assert res.gates["gate5_coverage"] is False
    assert not res.promote and res.failed_gates == ["gate5_coverage"], \
        "a better metric on fewer predictions is an automatic rejection"


def test_f_gate_fail_on_joint():
    res = _run_gate_case(_deltas_constant(0.3, jitter=0.05),
                         joint=lambda: (False, "channel residual covariance broke"),
                         tag="joint")
    assert res.gates["gate4_joint_forecast"] is False
    assert not res.promote and res.failed_gates == ["gate4_joint_forecast"]


def test_f_gate_not_provided_is_visible_not_veto():
    res = _run_gate_case(_deltas_constant(0.3, jitter=0.05),
                         coverage=None, joint=None, tag="np")
    assert res.gates["gate4_joint_forecast"] is None
    assert res.gates["gate5_coverage"] is None
    assert res.promote, "not-provided does not veto"
    assert res.gate_details["gate5_coverage"]["status"] == "not_provided", \
        "…but it is recorded, visibly"


# ===========================================================================
# compare: joins, refusals, hand-computed numbers
# ===========================================================================

def _tiny_compare_frames():
    ch = pd.DataFrame({
        "game_id": ["A", "B", "C", "D"],
        "game_date": pd.to_datetime(
            ["2024-06-01", "2024-06-01", "2025-06-02", "2025-06-02"]),
        "season": [2024, 2024, 2025, 2025],
        "home_team": ["T1", "T2", "T1", "T2"],
        "y_true": [10.0, -5.0, 3.0, 7.0],
        "y_pred": [11.0, -4.0, 5.0, 9.0],       # |resid| = 1, 1, 2, 2
    })
    inc = pd.DataFrame({
        "game_id": ["A", "B", "C", "D"],
        "y_true": [10.0, -5.0, 3.0, 7.0],
        "y_pred": [12.0, -1.0, 3.0, 15.0],      # |resid| = 2, 4, 0, 8
    })
    return ch, inc


def test_compare_hand_computed_numbers():
    with tempfile.TemporaryDirectory() as tmp:
        reg = Path(tmp) / "registry.jsonl"
        register("exp_hand", "h", "f", "margin_mae", TH, "inc", "A", registry_path=reg)
        ch, inc = _tiny_compare_frames()
        res = compare_to_incumbent(ch, inc, experiment_id="exp_hand",
                                   registry_path=reg, coverage=(1.0, 1.0),
                                   n_boot=200, seed=3)
        assert res.n_games == 4 and res.n_clusters == 2
        assert abs(res.metric_incumbent - 3.5) < 1e-12     # (2+4+0+8)/4
        assert abs(res.metric_challenger - 1.5) < 1e-12    # (1+1+2+2)/4
        assert abs(res.pooled_improvement - 2.0) < 1e-12   # deltas 1,3,-2,6
        by_season = {r["season"]: r for r in res.per_season}
        assert abs(by_season["2024"]["delta"] - 2.0) < 1e-12
        assert abs(by_season["2025"]["delta"] - 2.0) < 1e-12
        # both date-cluster means are exactly 2.0 -> degenerate CI at 2.0
        assert abs(res.ci_low - 2.0) < 1e-12 and abs(res.ci_high - 2.0) < 1e-12
        assert res.promote


def test_compare_refuses_truth_mismatch():
    with tempfile.TemporaryDirectory() as tmp:
        reg = Path(tmp) / "registry.jsonl"
        register("exp_truth", "h", "f", "margin_mae", TH, "inc", "A", registry_path=reg)
        ch, inc = _tiny_compare_frames()
        inc.loc[2, "y_true"] = 4.0
        _raises(ComparisonError, compare_to_incumbent, ch, inc,
                experiment_id="exp_truth", registry_path=reg)


def test_compare_refuses_duplicate_games_and_partial_overlap():
    with tempfile.TemporaryDirectory() as tmp:
        reg = Path(tmp) / "registry.jsonl"
        register("exp_guard", "h", "f", "margin_mae", TH, "inc", "A", registry_path=reg)
        ch, inc = _tiny_compare_frames()
        dup = pd.concat([ch, ch.iloc[[0]]], ignore_index=True)
        _raises(ComparisonError, compare_to_incumbent, dup, inc,
                experiment_id="exp_guard", registry_path=reg)
        short = inc.iloc[:3]
        _raises(ComparisonError, compare_to_incumbent, ch, short,
                experiment_id="exp_guard", registry_path=reg)
        res = compare_to_incumbent(ch, short, experiment_id="exp_guard",
                                   registry_path=reg, allow_partial_overlap=True,
                                   record=False)
        assert res.n_games == 3 and res.n_only_challenger == 1, \
            "partial overlap allowed only explicitly, with counts on record"


def test_compare_refuses_unregistered_experiment():
    with tempfile.TemporaryDirectory() as tmp:
        reg = Path(tmp) / "registry.jsonl"
        ch, inc = _tiny_compare_frames()
        _raises(UnregisteredExperimentError, compare_to_incumbent, ch, inc,
                experiment_id="ghost", registry_path=reg)


# ===========================================================================
# (g) metrics vs hand-computed values
# ===========================================================================

def test_g_mae_rmse_hand():
    assert M.mae([1, 2, 3], [2, 2, 5]) == 1.0                    # (1+0+2)/3
    assert abs(M.rmse([1, 2], [3, 5]) - np.sqrt(6.5)) < 1e-12    # (4+9)/2
    _raises(ValueError, M.mae, [1, np.nan], [1, 1])              # NaN refused


def test_g_pinball_hand():
    # y=[3,1]; tau=0.5 preds [2,2]: 0.5*1 and 0.5*1 -> 0.5
    # tau=0.9 preds [4,3]: y<q both: 0.1*1 and 0.1*2 -> mean 0.15
    out = M.pinball_loss([3, 1], [[2, 4], [2, 3]], [0.5, 0.9])
    assert np.allclose(out, [0.5, 0.15])
    assert abs(M.mean_pinball_loss([3, 1], [[2, 4], [2, 3]], [0.5, 0.9]) - 0.325) < 1e-12
    _raises(ValueError, M.pinball_loss, [1.0], [[1.0]], [1.5])


def test_g_crps_hand_and_naive_crosscheck():
    # y=0, ensemble {-1, 1}: E|X-y|=1, 0.5*E|X-X'|=0.5 -> CRPS 0.5
    assert abs(M.crps_ensemble([0.0], [[-1.0, 1.0]])[0] - 0.5) < 1e-12
    # single-member ensemble reduces to absolute error
    assert abs(M.crps_ensemble([2.0], [[5.0]])[0] - 3.0) < 1e-12
    # sorted-sample identity == naive double loop on random data
    rng = np.random.default_rng(11)
    y = rng.normal(size=5)
    x = rng.normal(size=(5, 7))
    fast = M.crps_ensemble(y, x)
    for i in range(5):
        t1 = np.mean(np.abs(x[i] - y[i]))
        t2 = np.mean(np.abs(x[i][:, None] - x[i][None, :])) / 2.0
        assert abs(fast[i] - (t1 - t2)) < 1e-12


def test_g_brier_logloss_hand():
    assert abs(M.brier_score([1, 0], [0.8, 0.3]) - 0.065) < 1e-12
    want = -(np.log(0.8) + np.log(0.75)) / 2.0
    assert abs(M.log_loss([1, 0], [0.8, 0.25]) - want) < 1e-12
    assert np.isfinite(M.log_loss([1, 0], [1.0, 0.0]))           # clipped
    _raises(ValueError, M.brier_score, [1, 2], [0.5, 0.5])       # non-binary
    _raises(ValueError, M.log_loss, [1, 0], [1.2, 0.5])          # p out of range


def test_g_reliability_table_hand():
    t = M.reliability_table([0, 1, 1, 0], [0.1, 0.9, 0.8, 0.6], n_bins=2)
    assert list(t["n"]) == [1, 3]
    assert abs(t.loc[0, "mean_predicted"] - 0.1) < 1e-12
    assert abs(t.loc[0, "observed_rate"] - 0.0) < 1e-12
    assert abs(t.loc[1, "mean_predicted"] - (0.9 + 0.8 + 0.6) / 3) < 1e-12
    assert abs(t.loc[1, "observed_rate"] - 2 / 3) < 1e-12
    # empty bins are kept (with n=0), never hidden
    t2 = M.reliability_table([1], [0.95], n_bins=10)
    assert len(t2) == 10 and t2["n"].sum() == 1 and t2.loc[9, "n"] == 1


def test_g_interval_coverage_hand():
    out = M.interval_coverage([0, 5, 10], [-1, 6, 9], [1, 7, 11])
    assert abs(out["empirical"] - 2 / 3) < 1e-12 and out["n_covered"] == 2
    ok = M.interval_coverage([0, 5], [-1, 4], [1, 6], nominal=1.0, tol=0.0)
    assert ok["ok"] is True
    bad = M.interval_coverage([0, 5, 10, 20], [-1, 6, 9, 21], [1, 7, 11, 22],
                              nominal=0.9, tol=0.05)
    assert bad["ok"] is False                                    # 0.5 vs 0.9
    _raises(ValueError, M.interval_coverage, [0], [2], [1])      # lower > upper


# ===========================================================================
# frozen baselines + leaderboards
# ===========================================================================

def test_frozen_baselines_load_and_tamper_refusal():
    fb = load_frozen_baselines()
    vals = dict(zip(fb["id"], fb["value"]))
    assert vals["home_advantage_only"] == 11.22
    assert vals["raw_trend_channel_sum"] == 10.53
    assert vals["incumbent_structural_chains"] == 9.54
    assert vals["minutes_carry_forward"] == 5.42
    assert vals["minutes_expanding_mean"] == 5.12
    assert (fb["kind"] == "market_benchmark").sum() >= 2, "market rows present"
    with tempfile.TemporaryDirectory() as tmp:
        # edited value -> refused
        doc = json.loads(FROZEN_BASELINES_PATH.read_text(encoding="utf-8"))
        doc["baselines"][0]["value"] = 9.99
        p = Path(tmp) / "tampered.json"
        p.write_text(json.dumps(doc), encoding="utf-8")
        _raises(FrozenBaselineTamperedError, load_frozen_baselines, p)
        # removed pinned row -> refused
        doc2 = json.loads(FROZEN_BASELINES_PATH.read_text(encoding="utf-8"))
        doc2["baselines"] = doc2["baselines"][1:]
        p2 = Path(tmp) / "missing.json"
        p2.write_text(json.dumps(doc2), encoding="utf-8")
        _raises(FrozenBaselineTamperedError, load_frozen_baselines, p2)
        # unpinned extra row -> refused (nothing joins the frozen table quietly)
        doc3 = json.loads(FROZEN_BASELINES_PATH.read_text(encoding="utf-8"))
        doc3["baselines"].append({
            "id": "sneaky", "model": "m", "metric": "mae", "value": 1.0,
            "sample": "s", "provenance": "p", "kind": "frozen_baseline"})
        p3 = Path(tmp) / "extra.json"
        p3.write_text(json.dumps(doc3), encoding="utf-8")
        _raises(FrozenBaselineTamperedError, load_frozen_baselines, p3)


def test_leaderboards_render():
    with tempfile.TemporaryDirectory() as tmp:
        reg = Path(tmp) / "registry.jsonl"
        out = Path(tmp) / "boards"
        # a forecasting experiment, evaluated through the full compare path
        register("exp_board", "beats incumbent", "synthetic", "margin_mae", TH,
                 "incumbent_structural_chains", "A", registry_path=reg,
                 decision_time="T-24h")
        ch, inc = _gate_frames(_deltas_constant(0.3, jitter=0.05))
        compare_to_incumbent(ch, inc, experiment_id="exp_board",
                             registry_path=reg, coverage=(0.95, 0.95),
                             joint_check=lambda: True, seed=5, n_boot=300)
        # a quarantined probabilistic experiment via plain evaluate()
        register("exp_w3_transfer", "NBA transfer", "quarantined", "crps", TH,
                 "incumbent_structural_chains", "A", registry_path=reg,
                 quarantined=True)
        record_evaluation("exp_w3_transfer",
                          {"metric_challenger": 7.7, "verdict": "FAIL",
                           "gates": {}}, registry_path=reg)
        paths = render_leaderboards(registry_path=reg, out_dir=out)
        assert set(paths) == {"FORECASTING", "PROBABILISTIC", "MARKET", "BETTING"}
        fc = paths["FORECASTING"].read_text(encoding="utf-8")
        pb = paths["PROBABILISTIC"].read_text(encoding="utf-8")
        for board_text in (fc, pb,
                           paths["MARKET"].read_text(encoding="utf-8"),
                           paths["BETTING"].read_text(encoding="utf-8")):
            for pinned in ("11.22", "10.53", "9.54", "5.42", "5.12", "8.46"):
                assert pinned in board_text, \
                    "frozen rows appear on every leaderboard render"
        assert "exp_board" in fc and "PASS" in fc
        assert "exp_w3_transfer" in pb and "QUARANTINED" in pb, \
            "quarantined experiments post win or lose"
        assert "exp_w3_transfer" not in fc, "board routing by metric"


# ===========================================================================
# plain runner
# ===========================================================================

def test_c_registry_regime_required_and_validated():
    """ROADMAP four-regimes rule: every registration declares exactly one of
    A/B/C/D; anything else refuses; lowercase input normalizes; the field is
    stored on the ledger record."""
    import tempfile
    from evalharness.registry import RegistryError
    with tempfile.TemporaryDirectory() as tmp:
        reg = Path(tmp) / "registry.jsonl"
        # missing regime -> TypeError (required positional)
        _raises(TypeError, register, "exp_noregime", "h", "f", "margin_mae",
                TH, "inc", registry_path=reg)
        # invalid regime -> RegistryError
        _raises(RegistryError, register, "exp_badregime", "h", "f",
                "margin_mae", TH, "inc", "X", registry_path=reg)
        # lowercase normalizes and is stored
        rec = register("exp_regime_d", "h", "f", "margin_mae", TH, "inc",
                       "d", registry_path=reg)
        assert rec["regime"] == "D", rec
        stored = get_registration("exp_regime_d", registry_path=reg)
        assert stored["regime"] == "D", stored


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
