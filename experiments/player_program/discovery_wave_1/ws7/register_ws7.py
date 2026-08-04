#!/usr/bin/env python3
"""register_ws7.py -- PREREGISTRATION for discovery workstream ws7_nonlinear_heterogeneous.

Every constant that defines a fitted form lives here and is frozen BEFORE any fit is run.
The runner (`run_ws7.py`) imports from this module and may not introduce a form of its own.

DISCOVERY LANE. Development folds only. Nothing here may replace Arm D, and nothing here is
appended to arm_registry.jsonl.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent

# ---- inherited, unchanged from the P2 fit so that betas sit on the same scale ------------- #
RIDGE_LAMBDA = 10.0          # from register_turnover_p2
INVOLVE_SHRINK_K = 50.0      # from register_turnover_p2, needed to invert the involvement proxy
MIN_TRAIN_ROWS = 2000        # from register_turnover_p2
SEED = 20260730              # evalharness default; stated so the CIs are reproducible

# ---- frozen knot / tier LEVELS. The VALUES are recomputed inside each training fold. ------ #
# Hard constraint: no tier boundary or knot may be read off the full history.
PW_KNOT_QUANTILES = [1 / 3, 2 / 3]        # W1 hinge basis, 2 interior knots
RCS_KNOT_QUANTILES = [0.10, 0.50, 0.90]   # W2 restricted cubic spline, 3 knots -> 1 extra basis

# ---- frozen REPORTING strata. Absolute thresholds, never fitted, never tuned. ------------- #
# Chosen from the marginal feature distribution only; no target quantity was inspected.
STRATA_PLAYER = {
    "primary_creator": "offensive_involvement_proxy >= 0.145",
    "secondary_creator": "0.060 <= offensive_involvement_proxy < 0.145",
    "low_usage": "offensive_involvement_proxy < 0.060",
    "secondary_expanded": "0.060 <= offensive_involvement_proxy < 0.145 and role_change >= +0.020",
    "role_expansion": "role_change >= +0.020",
    "role_contraction": "role_change <= -0.020",
    "abrupt_change": "abs(role_change) >= 0.050",
    "stable_role": "abs(role_change) < 0.050",
    "no_prior_history": "offensive_involvement_proxy is null",
}
INV_PRIMARY = 0.145
INV_LOW = 0.060
RC_EXPAND = 0.020
RC_ABRUPT = 0.050
STRATA_TEAMGAME = {
    "has_abrupt_change": "any candidate with abs(role_change) >= 0.050",
    "no_abrupt_change": "no such candidate",
    "high_displacement": "displaced_involvement >= 0.50",
    "low_displacement": "displaced_involvement < 0.50",
    "top_heavy": "proj_top5_concentration >= 0.70",
    "not_top_heavy": "proj_top5_concentration < 0.70",
}
DISPLACEMENT_HI = 0.50
TOP5_HEAVY = 0.70

# ---- THE ARMS. This list is closed. Seven new bounded nonlinear forms, two linear controls. #
# `spec` is consumed by run_ws7.build_basis; no arm may be added at run time.
ARMS = {
    # ---- bounded nonlinear forms under test (7) ---- #
    "W1_pw_involvement": {
        "form": "piecewise_linear",
        "spec": {"var": "offensive_involvement_proxy", "knot_quantiles": PW_KNOT_QUANTILES},
        "n_params": 3,
        "reads": "does the involvement effect change slope across the usage range?",
    },
    "W2_rcs_involvement": {
        "form": "restricted_cubic_spline",
        "spec": {"var": "offensive_involvement_proxy", "knot_quantiles": RCS_KNOT_QUANTILES},
        "n_params": 2,
        "reads": "smooth nonlinearity in involvement with 3 preregistered knots",
    },
    "W3_expansion_contraction": {
        "form": "asymmetric_split",
        "spec": {"var": "role_change"},
        "n_params": 2,
        "reads": "is role EXPANSION a different effect from role CONTRACTION?",
    },
    "W3b_priorrole_asym": {
        "form": "asymmetric_split_plus_group",
        "spec": {"var": "role_change",
                 "extra": ["trailing_minutes_share", "trailing_rotation_rank"]},
        "n_params": 4,
        "reads": "direct comparator to linear Arm F: was F null because the two signs cancelled?",
    },
    "W4_inv_x_minutes": {
        "form": "interaction",
        "spec": {"a": "offensive_involvement_proxy", "b": "proj_minutes_share"},
        "n_params": 3,
        "reads": "does involvement matter more for players projected heavy minutes?",
    },
    "W5_inv_x_support": {
        "form": "interaction",
        "spec": {"a": "offensive_involvement_proxy", "b": "log1p_player_support"},
        "n_params": 3,
        "reads": "does involvement matter more where the involvement estimate is well supported?",
    },
    "W6_partial_pool_tier": {
        "form": "partial_pool_continuous_tier",
        "spec": {"var": "offensive_involvement_proxy", "tier_var": "trailing_minutes_share"},
        "n_params": 4,
        "reads": ("involvement slope varies smoothly with a continuous role tier; the ridge "
                  "penalty shrinks the tier-varying part toward the pooled slope, which IS the "
                  "partial pooling. Tier = training-fold ECDF percentile, centred."),
    },
    # ---- linear reproduction controls, already published in TURNOVER_P2_RESULTS.json ---- #
    "L_involvement": {
        "form": "linear_control", "spec": {"cols": ["offensive_involvement_proxy"]},
        "n_params": 1, "reads": "reproduction of P2 Arm G (-0.00506 operational)",
    },
    "L_priorrole": {
        "form": "linear_control",
        "spec": {"cols": ["trailing_minutes_share", "trailing_rotation_rank", "role_change"]},
        "n_params": 3, "reads": "reproduction of P2 Arm F (-0.00057 operational)",
    },
}
NEW_VARIANTS = [a for a in ARMS if a.startswith("W")]
CONTROLS = [a for a in ARMS if a.startswith("L_")]

# derived helper column, an algebraic inversion of the P2 involvement proxy. Not new data.
DERIVED = {
    "log1p_player_support": (
        "log1p(clip(offensive_involvement_proxy * (_prior_support + 50) - 50/9, 0, None)). "
        "Inverts the P2 shrunk involvement proxy back to the player's prior EWMA field-goal "
        "attempts, i.e. how much history stands behind the involvement estimate. Built only from "
        "columns already present in the read-only P2 feature artifact, all of which are "
        "prior-games-only by construction."),
}

FORBIDDEN_PAIR = ["proj_minutes_share", "proj_off_poss_share"]

PREREG = {
    "schema": "discovery_ws7_preregistration/1",
    "workstream": "ws7_nonlinear_heterogeneous",
    "wave": "discovery_wave_1",
    "lane": "DISCOVERY (development folds only)",
    "frozen_before_results": True,
    "hypothesis": ("role and involvement effects may be hidden by LINEAR POOLING. The prior "
                   "linear main-effect arms were null or negative on operational team MAE versus "
                   "the frozen incumbent Arm D."),
    "prior_linear_arms_being_re_examined": {
        "prior_role_F": {"mean_mae_reduction": -0.00057, "ci90": [-0.004406, 0.003147]},
        "involvement_G": {"mean_mae_reduction": -0.00506, "ci90": [-0.009646, -0.000614]},
        "teammate_context_H": {"mean_mae_reduction": -0.00069, "ci90": [-0.005398, 0.003629]},
        "note": "read from turnover_p2_v1/TURNOVER_P2_RESULTS.json, operational track",
    },
    "frozen_incumbent": {"arm": "D_ewma_shrunk", "operational_team_mae": 2.9675,
                         "intrinsic_team_mae": 2.8960, "must_not_be_modified": True},
    "estimator": {
        "family": "Poisson", "penalty": f"ridge lambda={RIDGE_LAMBDA}, intercept unpenalised",
        "offset": "log(exposure) + log(frozen Arm D rate), so beta=0 reproduces Arm D",
        "validation": "walk-forward by season; every fold statistic from the training fold only",
        "standardisation": "training-fold mean/sd; missing -> training-fold mean (as in P2)",
        "solver": "IRLS with step-halving; non-convergence falls back to Arm D and is reported",
    },
    "tracks": {
        "intrinsic": "realised exposure. ORACLE DIAGNOSTIC ONLY -- not a decision metric.",
        "operational": "ALL 35,629 Tier A candidates including non-appearers. The decision metric.",
    },
    "sign_convention": ("INCUMBENT(D) absolute error MINUS CHALLENGER absolute error. "
                        "POSITIVE = challenger beats D."),
    "primary_metric": "operational team-game MAE, game-clustered 90% bootstrap CI",
    "arms": ARMS,
    "n_new_variants": len(NEW_VARIANTS),
    "n_linear_controls": len(CONTROLS),
    "multiplicity_statement": (
        f"{len(NEW_VARIANTS)} new bounded nonlinear variants are tested on one primary metric. "
        "No correction is applied to the reported 90% CIs; instead the reader is told the count. "
        "A single nominally positive arm out of 7 at 90% is close to what chance alone delivers "
        "(expected ~0.35 false positives per tail), so no single positive arm is evidence."),
    "hard_constraints": [
        "no unrestricted player-specific slopes -- every form has <= 4 free parameters",
        "role tiers and spline knots are recomputed inside each chronological training fold",
        "proj_minutes_share and proj_off_poss_share are algebraically identical under the v1 "
        "exposure mapping; they are NEVER both included and the gate is asked to prove it",
        "feature_gate.audit() runs per arm per fold before any fit and its JSON is saved",
        "canonical artifacts and Arm D are read-only; nothing is appended to arm_registry.jsonl",
    ],
    "reporting_strata_player": STRATA_PLAYER,
    "reporting_strata_teamgame": STRATA_TEAMGAME,
    "strata_provenance": ("absolute thresholds fixed here from the marginal feature distribution "
                          "before any fit; they are reporting cuts, never model inputs, and are "
                          "not re-tuned after results"),
    "derived_columns": DERIVED,
    "known_confounder_accepted": (
        "log1p_player_support correlates ~0.82 with offensive_involvement_proxy on the pooled "
        "frame, exactly the 'role tiers correlate with support' confounder named in the ledger. "
        "W5 therefore cannot separate a support effect from a usage-level effect; it is reported "
        "as a joint test, not as a clean support test."),
    "prespecified_verdict_rule": (
        "SUPPORTS only if a bounded nonlinear form beats Arm D on operational team MAE with a "
        "90% game-clustered CI excluding zero, AND the same sign appears in the preregistered "
        "stratum where the mechanism predicts it. Otherwise NULL or REFUTES. In-fold-only gains "
        "or intrinsic-only gains do not count."),
}


def main() -> int:
    HERE.mkdir(parents=True, exist_ok=True)
    PREREG["frozen_utc"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    (HERE / "PREREGISTRATION.json").write_text(json.dumps(PREREG, indent=2), encoding="utf-8")
    print(f"froze {len(NEW_VARIANTS)} new variants + {len(CONTROLS)} linear controls")
    for a in ARMS:
        print(f"  {a:26s} {ARMS[a]['form']:32s} p={ARMS[a]['n_params']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
