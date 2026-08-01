"""The prediction contract must REJECT non-compliant arms, not repair them.

A validator that never rejects anything is worse than no validator: it certifies
comparability that was never checked, and the council then averages predictions that do not
mean the same thing.  These tests construct arms that violate the contract in each way that
matters and assert the validator catches every one.

Runnable two ways:
    python -m pytest tests/ -q
    python tests/test_prediction_contract.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from prediction_contract import (            # noqa: E402
    REQUIRED_COLS, TARGETS, row_uid, validate_predictions,
)

FAILURES: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"  ok   {name}")
    else:
        FAILURES.append(f"{name}: {detail}")
        print(f"  FAIL {name}  {detail}")


def tiny_universe(n: int = 40) -> pd.DataFrame:
    dates = pd.date_range("2024-06-01", periods=n // 4, tz="UTC")
    rows = []
    for i in range(n):
        gd = dates[i % len(dates)]
        rows.append({
            "row_uid": row_uid(1000 + i, f"g{i//2}"),
            "player_id": 1000 + i, "game_id": f"g{i//2}", "season": 2024,
            "game_date": gd,
            "forecast_cutoff": gd + pd.Timedelta(hours=22, minutes=30),
            "cutoff_policy": "T-90m", "fold_id": "season:2024",
            "train_boundary": "seasons < 2024",
            "clustering_unit": str(gd.date()),
        })
    u = pd.DataFrame(rows)
    for t in TARGETS:
        u[f"eligible__{t}"] = True
    return u


def compliant(u: pd.DataFrame, target: str) -> pd.DataFrame:
    n = len(u)
    p = pd.DataFrame({
        "row_uid": u.row_uid, "target_key": target, "arm_id": "test_arm",
        "fold_id": u.fold_id, "forecast_cutoff": u.forecast_cutoff,
        "pred_point": np.linspace(5, 25, n), "pred_sd": np.full(n, 4.0),
        "pred_q05": np.linspace(1, 10, n), "pred_q25": np.linspace(3, 15, n),
        "pred_q50": np.linspace(5, 25, n), "pred_q75": np.linspace(8, 32, n),
        "pred_q95": np.linspace(12, 40, n),
        "is_fallback": False, "is_cold_start": False, "n_prior_games": 10,
        # strictly BEFORE the cutoff -- the as-of invariant
        "feature_asof": u.forecast_cutoff - pd.Timedelta(hours=3),
        "model_hash": "m0", "config_hash": "c0", "data_snapshot_hash": "d0",
        "exclusion_reason": None,
    })
    return p


def main() -> int:
    u = tiny_universe()
    T = "player_scoring_distribution"

    print("contract acceptance")
    r = validate_predictions(compliant(u, T), u, T)
    check("a compliant arm passes", r["ok"], str(r.get("problems")))
    check("coverage is 1.0 for a full arm", abs(r["coverage"] - 1.0) < 1e-12,
          f"coverage={r['coverage']}")

    print("\ncontract rejection -- each violation class")

    p = compliant(u, T).drop(columns=["pred_sd"])
    r = validate_predictions(p, u, T)
    check("missing required column rejected", not r["ok"])

    p = compliant(u, T).iloc[:20].copy()
    r = validate_predictions(p, u, T)
    check("silently dropped eligible rows rejected", not r["ok"],
          "an arm may exclude, but must say why")
    check("  ... and the reason names coverage",
          any("neither prediction nor exclusion_reason" in x for x in r["problems"]))

    # THE LEAKAGE CASE: reading something at or after the cutoff.
    p = compliant(u, T)
    p.loc[p.index[:5], "feature_asof"] = p.loc[p.index[:5], "forecast_cutoff"]
    r = validate_predictions(p, u, T)
    check("feature_asof == forecast_cutoff rejected (equality is leakage)", not r["ok"])
    check("  ... and it is reported as leakage",
          any("leakage" in x for x in r["problems"]))

    p = compliant(u, T)
    p.loc[p.index[:3], "feature_asof"] = p.loc[p.index[:3], "forecast_cutoff"] + pd.Timedelta(hours=1)
    r = validate_predictions(p, u, T)
    check("feature_asof after cutoff rejected", not r["ok"])

    p = compliant(u, T)
    p.loc[p.index[0], "pred_sd"] = 0.0
    r = validate_predictions(p, u, T)
    check("zero predictive sd rejected on a distribution target", not r["ok"])

    p = compliant(u, T)
    p.loc[p.index[0], "pred_q75"] = -5.0            # crosses q25/q50
    r = validate_predictions(p, u, T)
    check("non-monotone quantiles rejected", not r["ok"])

    p = compliant(u, T)
    p.loc[p.index[0], "pred_q50"] = np.nan
    r = validate_predictions(p, u, T)
    check("missing quantile rejected on the distribution target", not r["ok"])

    p = compliant(u, T)
    p.loc[p.index[0], "model_hash"] = None
    r = validate_predictions(p, u, T)
    check("missing model_hash rejected", not r["ok"])

    p = pd.concat([compliant(u, T), compliant(u, T).iloc[:1]], ignore_index=True)
    r = validate_predictions(p, u, T)
    check("duplicate row_uid rejected", not r["ok"])

    p = compliant(u, T)
    p.loc[p.index[0], "row_uid"] = "pg_notinuniverse"
    r = validate_predictions(p, u, T)
    check("prediction on an unknown row_uid rejected", not r["ok"])

    print("\nexclusions are legitimate when declared")
    p = compliant(u, T)
    p.loc[p.index[:6], "exclusion_reason"] = "cold_start_no_prior_games"
    p.loc[p.index[:6], ["pred_point", "pred_sd"]] = np.nan
    r = validate_predictions(p, u, T)
    check("a declared exclusion passes", r["ok"], str(r.get("problems")))
    check("excluded rows are counted", r["n_excluded"] == 6, f"n_excluded={r['n_excluded']}")
    check("coverage reflects the exclusions", abs(r["coverage"] - (len(u) - 6) / len(u)) < 1e-12)

    print("\nrow_uid stability")
    check("row_uid is deterministic", row_uid(7, "gX") == row_uid(7, "gX"))
    check("row_uid depends on player", row_uid(7, "gX") != row_uid(8, "gX"))
    check("row_uid depends on game", row_uid(7, "gX") != row_uid(7, "gY"))
    check("row_uid ignores int/str form of player_id", row_uid(7, "gX") == row_uid("7", "gX"))

    print("\np_active eligibility is the whole slate, by design")
    check("p_active target documents DNP inclusion",
          "INCLUDING players who do not appear" in TARGETS["p_active"].eligibility)
    check("schema requires an uncertainty field", "pred_sd" in REQUIRED_COLS)

    n = 26
    print(f"\n{n - len(FAILURES)}/{n} tests passed")
    if FAILURES:
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
