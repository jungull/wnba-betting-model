#!/usr/bin/env python3
"""prob_edge_mechanism_ablation_v2 -- which mechanism label is correct?

Registered: prob_edge_mechanism_ablation_v2 (regime A, primary metric log_loss).
Succeeds v1, whose market arm used a VIG-INCLUSIVE one-sided price.
DIAGNOSTIC ONLY.  No betting policy, no threshold, no promotion pathway.

THE QUESTION
    calibrated_prob_edge_v1's report said "the projection carries no information", citing a
    MARGINAL correlation corr(p_over, disagree) = +0.007.  John's review 2026-08-01 is right
    that this is stronger than the artifact supports: a marginal correlation does not measure
    INCREMENTAL information conditional on market probability, and a collinear predictor
    inside a penalised model can be shrunk toward zero while still carrying conditional signal.

    So: is the correct label (A) "the projection adds no incremental information", or
    (B) "the full probability model fails despite some limited projection information"?

THE PRIMARY CONTRAST is (8) FULL minus (7) DE-VIGGED MARKET + NON-PROJECTION CONTROLS: the
projection's incremental value given the fairest market representation and every other
control.  All other contrasts are SECONDARY, uncorrected for the comparison family, and are
diagnostic LEADS only.

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
    _amer_imp, FEATURES, LAMBDA_GRID, FIT_SEASON, DEV_SEASON, DESC_SEASON,
    load, prepare, fit_logistic, predict, standardise, logloss, brier,
    calib_slope_intercept,
)

EXPERIMENT_ID = "prob_edge_mechanism_ablation_v2"
OUT = REPO / "experiments" / "prob_edge_ablation_v2"
SEED = 20260801
N_BOOT = 2000

NON_PROJ_CTRL = [f for f in FEATURES if f not in ("disagree", "mkt_imp_over")]

#: kind: "constant" = training-fold base rate; "direct" = the named column used AS the
#: prediction with no fitting at all; "fitted" = L2 logistic on the named features.
#: Separating direct from fitted is the point of v2 -- it distinguishes what the market
#: actually says from what a fitted transform of it can be made to say.
SPECS = {
    "1_constant":              ("constant", []),
    "2_raw_vig_direct":        ("direct",   ["mkt_imp_over"]),
    "3_devig_direct":          ("direct",   ["p_market_devig"]),
    "4_devig_calibrated":      ("fitted",   ["p_market_devig"]),
    "5_projection_only":       ("fitted",   ["disagree"]),
    "6_devig_plus_projection": ("fitted",   ["p_market_devig", "disagree"]),
    "7_devig_plus_controls":   ("fitted",   ["p_market_devig"] + NON_PROJ_CTRL),
    "8_full_registered":       ("fitted",   list(FEATURES)),
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
    # DE-VIGGED market probability. Both sides come from the SAME book and the SAME
    # simultaneous snapshot, so the two-way overround divides out cleanly.
    q_o = _amer_imp(d.over_price.to_numpy())
    q_u = _amer_imp(d.under_price.to_numpy())
    d = d.copy()
    d["p_market_devig"] = q_o / (q_o + q_u)
    d["overround"] = q_o + q_u
    print(f"de-vig: mean overround {d.overround.mean():.4f} (1.0 = no vig) over {len(d)} rows")
    fit = d[d.season == FIT_SEASON]
    yf = fit.y_over.to_numpy()
    fdates = fit.game_date.to_numpy()
    print(f"fitting slice {FIT_SEASON}: {len(fit)} rows, {fit.game_date.nunique()} dates\n")

    models, results, losses = {}, {}, {}
    for name, (kind, feats) in SPECS.items():
        if kind == "fitted":
            Xf, mu, sd = standardise(fit[feats])
            lam = pick_lambda(Xf, yf, fdates)
            w = fit_logistic(Xf, yf, lam)
        else:
            Xf, mu, sd, lam, w = None, None, None, None, None
        models[name] = (feats, mu, sd, w)
        base = float(yf.mean())
        results[name] = {"kind": kind, "features": feats, "lambda": lam, "slices": {}}
        print(f"{name:26s} kind={kind:8s} k={len(feats)} lambda={lam}")

        for label, season in [("fit_2024", FIT_SEASON), ("dev_2025", DEV_SEASON),
                              ("desc_2026", DESC_SEASON)]:
            s = d[d.season == season]
            ys = s.y_over.to_numpy()
            if kind == "fitted":
                Xs, _, _ = standardise(s[feats], mu, sd)
                p = predict(w, Xs)
            elif kind == "direct":
                p = s[feats[0]].to_numpy(float)    # the market AS IT STANDS, unfitted
            else:
                p = np.full(len(s), base)          # training-fold base rate
            slope, icept = calib_slope_intercept(ys, p)
            results[name]["slices"][label] = {
                "n": int(len(s)), "log_loss": logloss(ys, p), "brier": brier(ys, p),
                "calib_slope": slope, "calib_intercept": icept}
            losses[(name, label)] = row_losses(ys, p)

    # ---- the contrasts -------------------------------------------------
    contrasts = {
        "PRIMARY   (8)-(7)  projection's incremental value given de-vigged market + controls":
            ("8_full_registered", "7_devig_plus_controls"),
        "companion (6)-(4)  projection given de-vigged market alone":
            ("6_devig_plus_projection", "4_devig_calibrated"),
        "secondary (3)-(2)  cost of vig inclusion, both unfitted":
            ("3_devig_direct", "2_raw_vig_direct"),
        "secondary (4)-(3)  what fitted recalibration adds to the de-vigged market":
            ("4_devig_calibrated", "3_devig_direct"),
        "secondary (3)-(1)  de-vigged market over a constant, unfitted":
            ("3_devig_direct", "1_constant"),
        "secondary (5)-(1)  projection ALONE over a constant":
            ("5_projection_only", "1_constant"),
        "secondary (7)-(4)  non-projection controls given the de-vigged market":
            ("7_devig_plus_controls", "4_devig_calibrated"),
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
    dec = con_out["PRIMARY   (8)-(7)  projection's incremental value given de-vigged market + controls"]
    improves = [lab for lab in ("dev_2025", "desc_2026")
                if dec[lab]["excludes_zero"] and dec[lab]["delta_mean"] < 0]
    label_supported = len(improves) == 0
    verdict = ("A: the projection adds no incremental information"
               if label_supported else
               "B: the full probability model fails despite some limited projection information")
    print("\n" + "=" * 78)
    print(f"MECHANISM LABEL -> {verdict}")
    print(f"  out-of-fitting slices where (8) beats (7) with CI excluding zero: "
          f"{improves or 'none'}")
    print("=" * 78)

    payload = {"experiment_id": EXPERIMENT_ID, "diagnostic_only": True,
               "specifications": results, "contrasts": con_out,
               "decision_rule": ("label A supported iff (8)-(7) shows no log-loss improvement "
                                 "whose date-clustered CI excludes zero on 2025 AND 2026"),
               "slices_improving": improves, "mechanism_label": verdict,
               "may_not_promote": True, "may_not_select_features": True,
               "secondary_contrasts_uncorrected": (
                   "Only the PRIMARY projection contrast is the registered decisive "
                   "diagnostic. Every 'secondary' line is one of several contrasts across "
                   "multiple specifications and slices with NO family-wise correction, so "
                   "each is a diagnostic LEAD consistent with an interpretation, never a "
                   "confirmed general mechanism.")}
    (OUT / "results.json").write_text(json.dumps(payload, indent=1), encoding="utf-8")

    rows = [{"spec": n, "slice": lab, **v}
            for n, r in results.items() for lab, v in r["slices"].items()]
    pd.DataFrame(rows).to_csv(OUT / "specification_table.csv", index=False)
    print(f"\nwrote {OUT/'results.json'} and specification_table.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
