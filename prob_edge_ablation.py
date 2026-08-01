#!/usr/bin/env python3
"""prob_edge_mechanism_ablation_v1 -- which mechanism label is correct?

Registered: prob_edge_mechanism_ablation_v1 (regime A, primary metric log_loss).
DIAGNOSTIC ONLY.  No betting policy, no threshold, no promotion pathway.

THE QUESTION
    calibrated_prob_edge_v1's report said "the projection carries no information", citing a
    MARGINAL correlation corr(p_over, disagree) = +0.007.  John's review 2026-08-01 is right
    that this is stronger than the artifact supports: a marginal correlation does not measure
    INCREMENTAL information conditional on market probability, and a collinear predictor
    inside a penalised model can be shrunk toward zero while still carrying conditional signal.

    So: is the correct label (A) "the projection adds no incremental information", or
    (B) "the full probability model fails despite some limited projection information"?

THE DECISIVE CONTRAST is (6) FULL minus (5) MARKET + NON-PROJECTION CONTROLS.  That is the
projection's incremental value given the market and every other control.

WHAT THIS MAY NOT DO (registration): it may not select a feature set, re-tune the parent, or
construct any betting rule.  A specification that scores better here does NOT become a
candidate policy -- that would be specification search against already-seen outcomes.  The
only output is a mechanism label.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))
import evalharness as eh                                          # noqa: E402
from calibrated_prob_edge import (                                # noqa: E402
    FEATURES, LAMBDA_GRID, FIT_SEASON, DEV_SEASON, DESC_SEASON,
    load, prepare, fit_logistic, predict, standardise, logloss, brier,
    calib_slope_intercept,
)

EXPERIMENT_ID = "prob_edge_mechanism_ablation_v1"
OUT = REPO / "experiments" / "prob_edge_ablation"
SEED = 20260801
N_BOOT = 2000

NON_PROJ = [f for f in FEATURES if f != "disagree"]

SPECS = {
    "1_constant":              [],
    "2_market_only":           ["mkt_imp_over"],
    "3_projection_only":       ["disagree"],
    "4_market_plus_projection": ["mkt_imp_over", "disagree"],
    "5_market_plus_controls":  NON_PROJ,
    "6_full_registered":       list(FEATURES),
}


def pick_lambda(X: np.ndarray, y: np.ndarray, dates: np.ndarray) -> float:
    """Leave-one-DATE-out CV inside the training fold only.

    Selected INDEPENDENTLY per specification: holding one spec's lambda across different
    dimensionalities would confound regularisation with information.
    """
    if X.shape[1] == 0:
        return 0.0
    best = None
    for lam in LAMBDA_GRID:
        ll = []
        for dt in np.unique(dates):
            m = dates == dt
            if (~m).sum() < 50:
                continue
            w = fit_logistic(X[~m], y[~m], lam)
            ll.append(logloss(y[m], predict(w, X[m])))
        s = float(np.mean(ll))
        if best is None or s < best[1]:
            best = (lam, s)
    return best[0]


def row_losses(y: np.ndarray, p: np.ndarray) -> np.ndarray:
    q = np.clip(p, 1e-12, 1 - 1e-12)
    return -(y * np.log(q) + (1 - y) * np.log(1 - q))


def paired_delta_ci(loss_a: np.ndarray, loss_b: np.ndarray, dates: np.ndarray,
                    rng: np.random.Generator, alpha: float = 0.10) -> dict:
    """Paired per-row log-loss delta (a - b), bootstrapped over GAME DATES.

    Negative means specification `a` is BETTER.  Dates are the resampling unit because rows
    on one slate share a common shock.
    """
    d = loss_a - loss_b
    uniq = np.unique(dates)
    idx = {u: np.flatnonzero(dates == u) for u in uniq}
    boot = np.empty(N_BOOT)
    for i in range(N_BOOT):
        pick = rng.choice(uniq, size=len(uniq), replace=True)
        boot[i] = d[np.concatenate([idx[u] for u in pick])].mean()
    lo, hi = np.quantile(boot, [alpha / 2, 1 - alpha / 2])
    return {"delta_mean": float(d.mean()), "ci90_low": float(lo), "ci90_high": float(hi),
            "excludes_zero": bool(lo > 0 or hi < 0)}


def main() -> int:
    reg = eh.get_registration(EXPERIMENT_ID)
    print(f"registration OK: {EXPERIMENT_ID} (registered {reg['registered_at']}, "
          f"regime {reg['regime']})\nDIAGNOSTIC ONLY -- no policy, no promotion.\n")
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)

    d, _ = prepare(load())
    fit = d[d.season == FIT_SEASON]
    yf = fit.y_over.to_numpy()
    fdates = fit.game_date.to_numpy()
    print(f"fitting slice {FIT_SEASON}: {len(fit)} rows, {fit.game_date.nunique()} dates\n")

    models, results, losses = {}, {}, {}
    for name, feats in SPECS.items():
        if feats:
            Xf, mu, sd = standardise(fit[feats])
            lam = pick_lambda(Xf, yf, fdates)
            w = fit_logistic(Xf, yf, lam)
        else:
            Xf, mu, sd, lam, w = None, None, None, 0.0, None
        models[name] = (feats, mu, sd, w)
        base = float(yf.mean())
        results[name] = {"features": feats, "lambda": lam, "slices": {}}
        print(f"{name:26s} k={len(feats)} lambda={lam}")

        for label, season in [("fit_2024", FIT_SEASON), ("dev_2025", DEV_SEASON),
                              ("desc_2026", DESC_SEASON)]:
            s = d[d.season == season]
            ys = s.y_over.to_numpy()
            if feats:
                Xs, _, _ = standardise(s[feats], mu, sd)
                p = predict(w, Xs)
            else:
                p = np.full(len(s), base)          # training-fold base rate
            slope, icept = calib_slope_intercept(ys, p)
            results[name]["slices"][label] = {
                "n": int(len(s)), "log_loss": logloss(ys, p), "brier": brier(ys, p),
                "calib_slope": slope, "calib_intercept": icept}
            losses[(name, label)] = row_losses(ys, p)

    # ---- the contrasts -------------------------------------------------
    contrasts = {
        "DECISIVE  (6)-(5)  projection's incremental value given market + all controls":
            ("6_full_registered", "5_market_plus_controls"),
        "companion (4)-(2)  projection's incremental value given market alone":
            ("4_market_plus_projection", "2_market_only"),
        "context   (2)-(1)  market's value over a constant":
            ("2_market_only", "1_constant"),
        "context   (3)-(1)  projection ALONE over a constant":
            ("3_projection_only", "1_constant"),
        "context   (5)-(2)  non-projection controls' value given market":
            ("5_market_plus_controls", "2_market_only"),
    }
    print("\nPaired log-loss deltas (negative = first spec BETTER), "
          "90% CI bootstrapped over game dates")
    con_out = {}
    for title, (a, b) in contrasts.items():
        con_out[title] = {}
        print(f"\n{title}")
        for label in ("fit_2024", "dev_2025", "desc_2026"):
            s = d[d.season == {"fit_2024": FIT_SEASON, "dev_2025": DEV_SEASON,
                               "desc_2026": DESC_SEASON}[label]]
            r = paired_delta_ci(losses[(a, label)], losses[(b, label)],
                                s.game_date.to_numpy(), rng)
            con_out[title][label] = r
            print(f"  {label:10s} delta {r['delta_mean']:+.6f} "
                  f"[{r['ci90_low']:+.6f}, {r['ci90_high']:+.6f}]"
                  f"{'  EXCLUDES ZERO' if r['excludes_zero'] else '  spans zero'}")

    # ---- the registered decision rule -----------------------------------
    dec = con_out["DECISIVE  (6)-(5)  projection's incremental value given market + all controls"]
    improves = [lab for lab in ("dev_2025", "desc_2026")
                if dec[lab]["excludes_zero"] and dec[lab]["delta_mean"] < 0]
    label_supported = len(improves) == 0
    verdict = ("A: the projection adds no incremental information"
               if label_supported else
               "B: the full probability model fails despite some limited projection information")
    print("\n" + "=" * 78)
    print(f"MECHANISM LABEL -> {verdict}")
    print(f"  out-of-fitting slices where (6) beats (5) with CI excluding zero: "
          f"{improves or 'none'}")
    print("=" * 78)

    payload = {"experiment_id": EXPERIMENT_ID, "diagnostic_only": True,
               "specifications": results, "contrasts": con_out,
               "decision_rule": ("label A supported iff (6)-(5) shows no log-loss improvement "
                                 "whose date-clustered CI excludes zero on 2025 AND 2026"),
               "slices_improving": improves, "mechanism_label": verdict,
               "may_not_promote": True, "may_not_select_features": True}
    (OUT / "results.json").write_text(json.dumps(payload, indent=1), encoding="utf-8")

    rows = [{"spec": n, "slice": lab, **v}
            for n, r in results.items() for lab, v in r["slices"].items()]
    pd.DataFrame(rows).to_csv(OUT / "specification_table.csv", index=False)
    print(f"\nwrote {OUT/'results.json'} and specification_table.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
