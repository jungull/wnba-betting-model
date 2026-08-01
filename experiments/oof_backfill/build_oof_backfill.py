#!/usr/bin/env python3
"""base_predictions_oof_2022_2023_v1 -- extend the channel walk-forward BACKWARDS.

Registered experiment: base_predictions_oof_2022_2023_v1 (regime A, primary
metric margin_mae, incumbent none_infrastructure).  This script never registers;
it builds.

WHY
    The conditional-edge / council line of work must train on genuine
    chronological out-of-fold predictions.  The only cross-model aligned OOF set
    is experiments/channel_reval/predictions_v2.csv -- 673 games, and under
    conditional_edge_design_freeze_v2 the legitimate weight-FITTING slice is
    2024 alone (229 games, ~90 dates).  That is too thin.  Extending OOF
    backwards to 2022 and 2023 roughly triples it.

WHAT IS AND IS NOT CHANGED
    The estimator is IDENTICAL.  This script imports run_reval and calls its own
    functions -- build_features, tune_alphas, make_games, fit_calibrations,
    apply_calibrations -- in the same order main() does.  Those six are verified
    pure with respect to TRAIN_YEARS / TEST_YEARS (they never read them), so the
    ONLY thing that varies here is the training window, exactly as registered.
    run_audits does read TEST_YEARS, so the module global is set before it runs.

    Per the registration, params are refit PER TARGET SEASON on all strictly
    earlier seasons: 2022 trains on 2021 alone, 2023 trains on 2021-2022.

THE REPRODUCTION GATE (registration, mandatory)
    Before any new season may be emitted, re-running this machinery with the
    committed window must reproduce predictions_v2.csv's rows to ~1e-12.  A
    failure means this is not the same estimator and the build STOPS.  Run:

        python experiments/oof_backfill/build_oof_backfill.py --reproduce
        python experiments/oof_backfill/build_oof_backfill.py --emit

    --emit re-runs the gate itself and refuses to write if it fails.

THE 2022 CAVEAT, CARRIED EVERYWHERE
    2022 trains on a single prior season.  Its predictions are structurally
    weaker than 2023's and must be flagged wherever they are used.  The manifest
    and the report both record it; downstream consumers should read
    fit_through_by_season rather than assuming a uniform fit window.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "experiments" / "channel_reval"))

import evalharness as eh                                    # noqa: E402
import asof_invariant as ai                                 # noqa: E402
import run_reval as rr                                      # noqa: E402

EXPERIMENT_ID = "base_predictions_oof_2022_2023_v1"
COMMITTED = REPO / "experiments" / "channel_reval" / "predictions_v2.csv"
OUT_CSV = HERE / "predictions_oof_2022_2023.csv"
OUT_JSON = HERE / "run_summary.json"
TARGETS = [2022, 2023]
TOL = 1e-12

PRED_COLS = ["GAME_ID", "GAME_DATE_h", "season_h", "season_type_h",
             "TEAM_ABBREVIATION_h", "TEAM_ABBREVIATION_a", "any_fallback",
             "fallback_row_h", "fallback_row_a", "margin_true", "total_true",
             "team_pts_h", "team_pts_a",
             "raw_margin_uncal", "raw_margin_cal", "str_margin_uncal", "str_margin_cal",
             "raw_home_cal", "raw_away_cal", "str_home_cal", "str_away_cal",
             "raw_total_cal", "str_total_cal", "naive_margin_pred"]

NUMERIC = ["margin_true", "total_true", "team_pts_h", "team_pts_a",
           "raw_margin_uncal", "raw_margin_cal", "str_margin_uncal", "str_margin_cal",
           "raw_home_cal", "raw_away_cal", "str_home_cal", "str_away_cal",
           "raw_total_cal", "str_total_cal", "naive_margin_pred"]


def _fit_and_predict(D: pd.DataFrame, train_seasons: list[int], test_seasons: list[int],
                     param_season: int) -> tuple[pd.DataFrame, dict, dict]:
    """Run the unmodified estimator with an arbitrary train/test window.

    ``param_season`` names the split whose train window supplies every fitted
    parameter (alphas and calibrations), mirroring main()'s use of the 2024
    split for all three committed test seasons.
    """
    splits = eh.walk_forward_by_season(
        D, date_col="GAME_DATE", season_col="season",
        min_train_seasons=len(train_seasons), test_seasons=test_seasons,
    )
    by_name = {s.name: s for s in splits}
    outer = by_name[f"season:{param_season}"]

    got = sorted(D.loc[outer.train_idx, "season"].unique())
    assert got == sorted(train_seasons), f"train window {got} != {sorted(train_seasons)}"

    alphas, _ = rr.tune_alphas(D, outer)
    F = rr.build_features(D, alphas)
    games = rr.make_games(F)

    train_ids = set(D.loc[outer.train_idx, "GAME_ID"])
    tg = games[games.GAME_ID.isin(train_ids) & games.eligible]
    assert sorted(tg.season_h.unique()) == sorted(train_seasons)
    cal = rr.fit_calibrations(tg)
    games = rr.apply_calibrations(games, cal)

    frames = []
    for s in test_seasons:
        ids = set(D.loc[by_name[f"season:{s}"].test_idx, "GAME_ID"])
        sel = games[games.GAME_ID.isin(ids)].copy()
        assert (sel.season_h == s).all()
        frames.append(sel)
    test = pd.concat(frames, ignore_index=True)
    return test[test.eligible].copy(), alphas, cal


def _max_dev(mine: pd.DataFrame, ref: pd.DataFrame) -> tuple[float, str | None]:
    m = mine[mine.GAME_ID.isin(ref.GAME_ID)][PRED_COLS].sort_values("GAME_ID").reset_index(drop=True)
    r = ref.sort_values("GAME_ID").reset_index(drop=True)
    worst, col = 0.0, None
    for c in NUMERIC:
        d = float(np.nanmax(np.abs(m[c].to_numpy(float) - r[c].to_numpy(float))))
        if d > worst:
            worst, col = d, c
    return worst, col


def reproduce(D: pd.DataFrame) -> bool:
    """Registration gate: same machinery + committed window == predictions_v2.csv.

    The registered gate is on the 2024 ROWS specifically, and that wording matters.
    2026 is a live season: the daily refresh keeps adding games, so the rebuild
    legitimately contains rows that did not exist when predictions_v2.csv was
    committed.  A naive whole-file row-count comparison fails on that alone and
    would report data recency as estimator drift.  So: 2024 rows are the gate,
    the full committed intersection is a stronger sensitivity check, and any
    rows present only in the rebuild are reported as new data and must be
    2026-only -- a surplus row in a CLOSED season would be a real defect and
    fails the gate.
    """
    print("REPRODUCTION GATE -- committed window 2021-2023 -> 2024/2025/2026")
    et, alphas, cal = _fit_and_predict(
        D, train_seasons=[2021, 2022, 2023], test_seasons=[2024, 2025, 2026],
        param_season=2024)
    ref = pd.read_csv(COMMITTED)

    missing = sorted(set(ref.GAME_ID) - set(et.GAME_ID))
    if missing:
        print(f"  FAIL: {len(missing)} committed games absent from the rebuild: {missing[:8]}")
        return False

    surplus = et[~et.GAME_ID.isin(ref.GAME_ID)]
    bad = surplus[surplus.season_h != 2026]
    if len(bad):
        print(f"  FAIL: {len(bad)} surplus rows in CLOSED seasons "
              f"{sorted(bad.season_h.unique())} -- that is estimator drift, not new data")
        return False
    if len(surplus):
        print(f"  note: {len(surplus)} rebuild-only rows, all 2026 (live season has advanced "
              f"since predictions_v2.csv was committed): {sorted(surplus.GAME_ID)}")

    d24, c24 = _max_dev(et, ref[ref.season_h == 2024])
    dall, call = _max_dev(et, ref)
    print(f"  alphas={alphas}  n_train_games={cal['n_train_games']}")
    print(f"  2024 rows (registered gate): n={int((ref.season_h == 2024).sum())}  "
          f"max abs dev {d24:.3e} (worst {c24})")
    print(f"  full committed intersection : n={len(ref)}  "
          f"max abs dev {dall:.3e} (worst {call})")
    ok = d24 <= TOL and dall <= TOL
    print(f"  GATE: {'PASS' if ok else 'FAIL'} (tol {TOL:.0e})")
    return ok


def emit(D: pd.DataFrame) -> int:
    if not reproduce(D):
        print("\nSTOPPING: the backward extension is not the same estimator.")
        return 1

    print("\nEMIT -- backward extension, params refit per target season")
    out, per_season, audit_report = [], {}, {}
    for s in TARGETS:
        # int() matters: D.season carries numpy int64, which is not JSON
        # serializable and would blow up write_manifest after the CSV is on disk.
        train = [int(x) for x in sorted(D.season.unique()) if int(x) < s]
        et, alphas, cal = _fit_and_predict(D, train_seasons=train, test_seasons=[s],
                                           param_season=s)

        rr.TEST_YEARS = [s]                     # run_audits reads this global
        F = rr.build_features(D, alphas)
        audits = rr.run_audits(D, alphas, rr.make_games(F))
        if not audits["passed"]:
            print(f"  {s}: LEAKAGE AUDIT FAILED -- refusing to emit")
            return 1

        src = D.loc[D.season.isin(train), "GAME_DATE"].max()
        per_season[s] = {"train_seasons": train, "alphas": alphas,
                         "n_train_games": int(cal["n_train_games"]),
                         "n_games": int(len(et)),
                         "fit_through": str(pd.Timestamp(src).date()),
                         "thin_history": len(train) == 1}
        audit_report[s] = {"removal_mismatch_rows": audits["removal_mismatch_rows"],
                           "perturbation_mismatch_rows": audits["perturbation_mismatch_rows"],
                           "n_games_audited": audits["n_games_audited"]}
        print(f"  {s}: train {train} | alphas {alphas} | {len(et)} eligible games "
              f"| audits PASS{'  [THIN HISTORY]' if len(train) == 1 else ''}")
        out.append(et[PRED_COLS])

    allp = pd.concat(out, ignore_index=True).sort_values(
        ["season_h", "GAME_ID"]).reset_index(drop=True)
    allp.to_csv(OUT_CSV, index=False)

    # Context only, explicitly development data -- never a promotion signal.
    context = {}
    for s in TARGETS:
        sub = allp[allp.season_h == s]
        context[s] = {
            "n": int(len(sub)),
            "model_margin_mae": float((sub.str_margin_cal - sub.margin_true).abs().mean()),
            "naive_margin_mae": float((sub.naive_margin_pred - sub.margin_true).abs().mean()),
        }
        print(f"  {s}: model margin MAE {context[s]['model_margin_mae']:.3f} "
              f"vs naive {context[s]['naive_margin_mae']:.3f}  (development data)")

    bound = max(pd.Timestamp(v["fit_through"]) for v in per_season.values())
    ai.write_manifest(
        OUT_CSV,
        producer="experiments/oof_backfill/build_oof_backfill.py",
        fit_through_date=bound,
        fit_through_season=max(v["train_seasons"][-1] for v in per_season.values()),
        fit_seasons=sorted({x for v in per_season.values() for x in v["train_seasons"]}),
        asof_granularity="season",
        fit_through_by_season={s: v["fit_through"] for s, v in per_season.items()},
        notes=("Backward walk-forward extension of the channel base model. Params are refit "
               "PER TARGET SEASON on strictly earlier seasons only: 2022 trains on 2021 alone "
               "(THIN HISTORY -- structurally weaker, flag wherever used), 2023 trains on "
               "2021-2022. Estimator identical to run_reval.py; only the training window "
               "differs, verified by a 1e-12 reproduction of predictions_v2.csv. Development "
               "data: not a holdout and not promotable evidence."),
        extra={"experiment_id": EXPERIMENT_ID, "per_season": per_season,
               "reproduction_gate": {"reference": "experiments/channel_reval/predictions_v2.csv",
                                     "tolerance": TOL, "passed": True}},
    )

    OUT_JSON.write_text(json.dumps(
        {"experiment_id": EXPERIMENT_ID, "targets": TARGETS, "per_season": per_season,
         "leakage_audits": audit_report, "context_mae_development_only": context,
         "reproduction_gate_passed": True, "rows_emitted": int(len(allp))},
        indent=1, default=str), encoding="utf-8")

    print(f"\nwrote {OUT_CSV.name} ({len(allp)} rows), manifest, run_summary.json")
    prior = len(pd.read_csv(COMMITTED).query("season_h == 2024"))
    print(f"conditional-edge fitting sample: {prior} -> {prior + len(allp)} games")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reproduce", action="store_true", help="run the gate only")
    ap.add_argument("--emit", action="store_true", help="gate, then build 2022 and 2023")
    a = ap.parse_args()
    if not (a.reproduce or a.emit):
        ap.error("choose --reproduce or --emit")

    reg = eh.get_registration(EXPERIMENT_ID)
    print(f"registration OK: {EXPERIMENT_ID} (registered {reg['registered_at']}, "
          f"regime {reg['regime']})")
    D = rr.load_base()
    print(f"base rows {len(D)}, seasons {sorted(D.season.unique())}\n")

    return emit(D) if a.emit else (0 if reproduce(D) else 1)


if __name__ == "__main__":
    sys.exit(main())
