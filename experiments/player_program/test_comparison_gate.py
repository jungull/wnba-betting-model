#!/usr/bin/env python3
"""test_comparison_gate.py — regression tests for the two-layer baseline-parity gate.

The motivating case is real. In P1/P2, fitted challengers carried an unpenalised free intercept
that the unfitted frozen incumbent (Arm D) did not have:

    K0 (intercept-only, challenger's own pipeline, zero features)   2.96419
    frozen Arm D                                                    2.96745
    free-recalibration gain                                         0.00326

A challenger reporting a gain of 0.0020 over Arm D had therefore demonstrated nothing: a model
with no substantive features at all already obtained more than that from pipeline freedom alone.
``test_ws2_real_case_*`` pins those exact numbers.

The gate enforces TWO contracts, and the tests are organised around them:

    LAYER A  challenger vs its matched K0        strict; a mismatch is blocking and is NOT
                                                 adjudicable by an ordinary reason
    LAYER B  challenger vs the frozen incumbent  a structural difference MAY be adjudicated, but
                                                 only with a stated reason AND a named code from
                                                 the closed LAYER_B_REASON_CODES enum

**Nothing here is scored.** Every metric in this file is a literal supplied to the gate; no
artifact is read, no model is fitted, no forecast is compared to any outcome. The tests assert
gate verdicts and arithmetic on numbers written down in this file.

Run under pytest if it is available::

    python -m pytest experiments/player_program/test_comparison_gate.py -q

`pytest` is NOT installed in this environment, so the file is also directly runnable::

    python experiments/player_program/test_comparison_gate.py
"""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import comparison_gate as cg                                                   # noqa: E402

# --------------------------------------------------------------------------------------------
# the real WS2 numbers
# --------------------------------------------------------------------------------------------
K0_MAE = 2.96419            # intercept-only control, challenger's own pipeline, zero features
ARM_D_MAE = 2.96745         # frozen substantive incumbent
FREE_FLEX = ARM_D_MAE - K0_MAE                     # 0.00326 — the free-recalibration gain

# a challenger that "beats" Arm D by 0.0020, i.e. by LESS than the featureless control does
WEAK_CHALLENGER_MAE = 2.96545
# a challenger whose advantage is real: 0.01745 over Arm D, 0.01419 net of free flexibility
STRONG_CHALLENGER_MAE = 2.95000

STRONG = {"challenger": STRONG_CHALLENGER_MAE, "k0": K0_MAE, "incumbent": ARM_D_MAE}
WEAK = {"challenger": WEAK_CHALLENGER_MAE, "k0": K0_MAE, "incumbent": ARM_D_MAE}

FOLDS = ("2021", "2022", "2023", "2024", "2025")

#: one fully specified pipeline, every dimension stated.
BASE = {
    "intercept_treatment": "free, unpenalised",
    "calibration_freedom": "none: no post-fit rescaling, recentring or isotonic fix-up",
    "penalty_treatment": "ridge l2=1.0 on slopes; intercept NOT penalised",
    "exposure_offset": "log(projected_player_possessions/1)",
    "training_rows": "rows:n=27351:sha256=1111111111111111",
    "evaluation_rows": "rows:n=35629:sha256=2222222222222222",
    "chronological_folds": FOLDS,
    "clipping": "predictions clipped to [0.0, 25.0]",
    "link_function": "log",
    "preprocessing": "no standardisation; raw rates",
    "missing_value_handling": "drop rows with any null; never impute",
    "companion_components": ("projected_player_possessions/1", "team_possession_prior/1"),
    "fallback_rules": "none: a declining component fails the row",
    "aggregation": ("sum of player-level predictions over prediction_universe to the team total; "
                    "non-appearers contribute predicted_rate x zero projected exposure; summed "
                    "AFTER clipping, BEFORE post_processing"),
    "candidate_universe": "all 35,629 Tier A obligations incl. the 8,278 non-appearers",
    "post_processing": "none",
    "prediction_universe": "identical to candidate_universe",
}

# --------------------------------------------------------------------------------------------
# the three structural allowances a frozen formula genuinely needs, expressed in the new form
# --------------------------------------------------------------------------------------------
FROZEN_INCUMBENT = {
    "intercept_treatment": "none: frozen coefficients, no fitted intercept",
    "penalty_treatment": "none: unfitted, frozen at registration",
    "training_rows": "none: unfitted, frozen at registration",
}

FROZEN_ADJUDICATIONS = {
    "challenger|incumbent:intercept_treatment": {
        "code": "incumbent_is_frozen_formula",
        "reason": ("Arm D is frozen and unfitted by registration; it structurally cannot carry a "
                   "fitted intercept. K0 measures what that freedom is worth (0.00326) and the "
                   "challenger is credited only for challenger_vs_k0."),
    },
    "challenger|incumbent:penalty_treatment": {
        "code": "incumbent_is_frozen_formula",
        "reason": ("Arm D estimates no coefficients, so there is nothing for a penalty to apply "
                   "to. The challenger's ridge is not an advantage over a formula that is not fit."),
    },
    "challenger|incumbent:training_rows": {
        "code": "incumbent_has_no_training_rows",
        "reason": ("Arm D was never fitted, so it has no training row set. evaluation_rows is "
                   "identical on both sides and is NOT adjudicated."),
    },
}


def side(name: str, role: str, *, features: tuple[str, ...] = (),
         pipeline_id: str = "turnover_p2_v1", **over) -> cg.SideSpec:
    d = dict(BASE)
    d.update(over)
    return cg.SideSpec(name=name, role=role, pipeline_id=pipeline_id,
                       substantive_features=tuple(features), **d)


def challenger(**over) -> cg.SideSpec:
    return side("arm_H_role_expansion", "challenger",
                features=("expanded_role_bounded", "displaced_involvement"), **over)


def k0(*, features: tuple[str, ...] = (), **over) -> cg.SideSpec:
    return side("K0_intercept_only", "k0", features=features, **over)


def incumbent(**over) -> cg.SideSpec:
    """Arm D, described as if refit through the identical pipeline (the matched case)."""
    return side("arm_D_turnover_rate_pooled_baseline_v1", "incumbent",
                features=("ewma_turnover_rate",),
                pipeline_id="turnover_rate_pooled_baseline_v1", **over)


def frozen_incumbent(**over) -> cg.SideSpec:
    """Arm D as it ACTUALLY is: a registered frozen formula, not a fit."""
    d = dict(FROZEN_INCUMBENT)
    d.update(over)
    return incumbent(**d)


def kinds(rep: dict, key: str = "findings") -> list[str]:
    return [f["kind"] for f in rep[key]]


def run(ch, inc, ctrl, metrics, **kw) -> dict:
    """Audit once for the report and once for the raise, and assert the two agree."""
    rep = cg.audit_fold(ch, inc, ctrl, metrics, raise_on_block=False, **kw)
    raised = False
    try:
        cg.audit_fold(ch, inc, ctrl, metrics, raise_on_block=True, **kw)
    except cg.ComparisonGateFailure:
        raised = True
    assert raised == (not rep["passed"]), \
        f"raise behaviour must track passed: raised={raised} passed={rep['passed']}"
    return rep


def layer_block(rep: dict, layer: str) -> dict:
    return next(b for b in rep["decision_table"]["layers"] if b["layer"] == layer)


# --------------------------------------------------------------------------------------------
# the dimensions actually exist, and the Layer A prose mapping is complete
# --------------------------------------------------------------------------------------------

def test_seventeen_dimensions_are_declared():
    assert len(cg.DIMENSIONS) == 17, cg.DIMENSIONS
    assert len(set(cg.DIMENSIONS)) == len(cg.DIMENSIONS)
    for required in ("intercept_treatment", "calibration_freedom", "penalty_treatment",
                     "exposure_offset", "training_rows", "evaluation_rows",
                     "chronological_folds", "clipping", "link_function", "preprocessing",
                     "missing_value_handling", "companion_components", "fallback_rules",
                     "aggregation",
                     "candidate_universe", "post_processing", "prediction_universe"):
        assert required in cg.DIMENSIONS, required
    assert set(BASE) == set(cg.DIMENSIONS), "the fixture must state every dimension"


def test_aggregation_is_a_real_dimension_of_its_own():
    """Player-level predictions have to become a team total somehow; that choice is a dimension."""
    assert "aggregation" in cg.DIMENSIONS
    assert cg.DIMENSION_TO_LAYER_A_NAME["aggregation"] == "aggregation"
    rep = run(challenger(), incumbent(aggregation="mean of player predictions, then x5"), k0(),
              STRONG)
    assert not rep["passed"]
    f = next(x for x in rep["blocking"] if x.get("dimension") == "aggregation")
    assert f["kind"] == "dimension_mismatch" and f["layer"] == cg.LAYER_B


def test_aggregation_blocks_when_omitted_like_every_other_dimension():
    d = dict(BASE)
    d.pop("aggregation")
    ch = {"name": "arm_H", "pipeline_id": "turnover_p2_v1", "substantive_features": ("f",), **d}
    rep = run(ch, incumbent(), k0(), STRONG)
    assert not rep["passed"], "an omitted aggregation must not pass"
    assert any(f["kind"] == "dimension_unspecified" and f["dimension"] == "aggregation"
               for f in rep["blocking"])


def test_the_layer_a_prose_mapping_covers_every_dimension_exactly_once():
    """The contract names thirteen things; the module has seventeen. The map is documented."""
    covered = [d for dims in cg.LAYER_A_STRICT.values() for d in dims]
    assert sorted(covered) == sorted(cg.DIMENSIONS), covered
    assert len(covered) == len(set(covered)), "no dimension may appear under two prose names"
    for prose in ("rows and universe", "folds", "offset", "intercept", "penalty treatment",
                  "clipping", "link", "preprocessing", "missingness", "companion components",
                  "fallback", "aggregation", "post-processing"):
        assert prose in cg.LAYER_A_STRICT, prose
    assert set(cg.LAYER_A_STRICT["rows and universe"]) == {
        "training_rows", "evaluation_rows", "candidate_universe", "prediction_universe"}
    assert cg.LAYER_A_STRICT["offset"] == ("exposure_offset",)
    # calibration_freedom is a post-fit rescaling, so it lives under the prose "post-processing"
    assert "calibration_freedom" in cg.LAYER_A_STRICT["post-processing"]
    assert cg.DIMENSION_TO_LAYER_A_NAME["training_rows"] == "rows and universe"


def test_the_two_layers_are_bound_to_the_two_pairs():
    assert cg.PAIR_LAYER["challenger|k0"] == cg.LAYER_A
    assert cg.PAIR_LAYER["challenger|incumbent"] == cg.LAYER_B
    assert cg.finding_layer({"kind": "dimension_mismatch", "pair": "challenger|k0"}) == cg.LAYER_A
    assert cg.finding_layer({"kind": "k0_missing"}) == cg.LAYER_A
    assert cg.finding_layer({"kind": "metric_missing", "side": "k0"}) == cg.LAYER_EVIDENCE


# --------------------------------------------------------------------------------------------
# the real WS2 case
# --------------------------------------------------------------------------------------------

def test_ws2_real_case_free_flexibility_gain_is_0_0033():
    rep = cg.gain_report({"challenger": WEAK_CHALLENGER_MAE, "k0": K0_MAE,
                          "incumbent": ARM_D_MAE}, metric_name="operational_team_mae")
    g = rep["gains"]
    assert abs(g["k0_vs_incumbent"] - 0.00326) < 1e-9, g
    assert abs(rep["free_flexibility_gain"] - 0.0033) < 5e-5, rep["free_flexibility_gain"]
    assert abs(g["challenger_vs_incumbent"] - 0.00200) < 1e-9, g
    assert abs(g["challenger_vs_k0"] - (-0.00126)) < 1e-9, g
    # the three quantities are separate and the decomposition identity is asserted, never assumed
    assert rep["gain_identity_holds"] is True
    assert abs(rep["net_of_free_flexibility"] - g["challenger_vs_k0"]) < 1e-12
    assert set(g) == {"challenger_vs_incumbent", "challenger_vs_k0", "k0_vs_incumbent"}
    assert "gain" not in rep, "there must be no single collapsed headline number"
    # and challenger_vs_k0 is named as the PRIMARY test, with the denied credit stated as a number
    assert rep["primary_incremental_test"] == "challenger_vs_k0"
    assert abs(rep["primary_incremental_value"] - (-0.00126)) < 1e-9
    assert abs(rep["credit_denied_to_challenger"] - 0.00326) < 1e-9


def test_ws2_real_case_weak_challenger_is_flagged():
    """Everything matched; the ONLY defect is that the claimed gain is inside the K0 gap."""
    rep = run(challenger(), incumbent(), k0(), WEAK)
    assert not rep["passed"]
    assert set(kinds(rep, "blocking")) == {"gain_within_free_flexibility"}, kinds(rep, "blocking")
    f = next(x for x in rep["findings"] if x["kind"] == "gain_within_free_flexibility")
    assert abs(f["k0_vs_incumbent"] - 0.00326) < 1e-9
    assert abs(f["challenger_vs_incumbent"] - 0.00200) < 1e-9
    assert f["net_of_free_flexibility"] < 0


def test_ws2_real_case_as_it_actually_happened():
    """The historical shape: the frozen incumbent had no fitted intercept at all.

    Both defects must surface — the unmatched dimension AND the fact that the reported gain sits
    inside what the featureless control already obtains.
    """
    rep = run(challenger(), frozen_incumbent(), k0(), WEAK)
    assert not rep["passed"]
    bk = kinds(rep, "blocking")
    assert "gain_within_free_flexibility" in bk
    mism = [f for f in rep["findings"] if f["kind"] == "dimension_mismatch"]
    assert {f["dimension"] for f in mism} == {"intercept_treatment", "penalty_treatment",
                                              "training_rows"}, mism
    assert all(f["pair"] == "challenger|incumbent" for f in mism)
    assert all(f["layer"] == cg.LAYER_B for f in mism), "these are Layer B, not Layer A"


def test_ws2_real_case_in_the_new_two_layer_form():
    """The real case, expressed the way the gate now wants it.

    LAYER A is clean: K0 is the challenger's own pipeline with the features removed, so nothing
    differs. LAYER B carries the three structural allowances a frozen formula genuinely needs,
    each with a named code. And the challenger is DENIED credit for the 0.00326 that K0 already
    captured: challenger_vs_k0 is -0.00126, so the comparison still blocks.
    """
    rep = run(challenger(), frozen_incumbent(), k0(), WEAK, adjudications=FROZEN_ADJUDICATIONS)
    assert not rep["passed"]

    # -- LAYER A: nothing at all between the challenger and its own control
    a = layer_block(rep, cg.LAYER_A)
    assert a["clean"] is True and a["n_findings"] == 0 and a["n_blocking"] == 0, a
    assert a["dimensions_in_mismatch"] == []

    # -- LAYER B: three structural differences, all adjudicated, all still visible
    b = layer_block(rep, cg.LAYER_B)
    assert b["n_structural_differences"] == 3
    assert b["n_blocking"] == 0 and b["n_adjudicated"] == 3
    by_dim = {sd["dimension"]: sd for sd in b["structural_differences"]}
    assert set(by_dim) == {"intercept_treatment", "penalty_treatment", "training_rows"}
    assert all(sd["adjudicated"] for sd in by_dim.values())
    assert by_dim["intercept_treatment"]["reason_code"] == "incumbent_is_frozen_formula"
    assert by_dim["penalty_treatment"]["reason_code"] == "incumbent_is_frozen_formula"
    assert by_dim["training_rows"]["reason_code"] == "incumbent_has_no_training_rows"
    # the exact difference is stated, not merely that one exists
    assert by_dim["intercept_treatment"]["challenger_value"] == "free, unpenalised"
    assert by_dim["intercept_treatment"]["incumbent_value"] == \
        "none: frozen coefficients, no fitted intercept"
    # and K0 quantifies what each allowance is worth
    assert all(abs(sd["quantified_by_k0"] - 0.00326) < 1e-9 for sd in by_dim.values())

    # -- the challenger is denied credit for the flexibility K0 already captured
    dt = rep["decision_table"]
    assert dt["primary_incremental_test"] == "challenger_vs_k0"
    assert abs(dt["primary_incremental_value"] - (-0.00126)) < 1e-9
    assert abs(dt["credit_denied_to_challenger"] - 0.00326) < 1e-9
    # THE HARD RULE: it beats production (+0.002) and fails its own control (-0.00126)
    assert dt["headline_judgment"]["verdict"] == "beats_incumbent_but_fails_k0"
    assert dt["headline_judgment"]["features_bought_anything_beyond_k0"] is False
    assert dt["feature_value_demonstrated"] is False
    assert dt["challenger_still_improves_frozen_incumbent"] is True
    assert set(kinds(rep, "blocking")) == {"gain_within_free_flexibility"}, kinds(rep, "blocking")

    # -- and the codes invoked are counted by name
    assert dt["reason_codes_invoked"] == {"incumbent_is_frozen_formula": 2,
                                          "incumbent_has_no_training_rows": 1}
    assert dt["flexibility_was_waved_through"] is True and dt["n_waved_through"] == 3


def test_the_same_two_layer_case_passes_when_the_features_actually_buy_something():
    """Same three Layer B allowances; a challenger that genuinely exceeds its own control."""
    rep = run(challenger(), frozen_incumbent(), k0(), STRONG, adjudications=FROZEN_ADJUDICATIONS)
    assert rep["passed"], rep["blocking"]
    dt = rep["decision_table"]
    assert abs(dt["primary_incremental_value"] - 0.01419) < 1e-9
    assert abs(dt["credit_denied_to_challenger"] - 0.00326) < 1e-9
    assert dt["headline_judgment"]["verdict"] == "features_bought_incremental_value"
    assert layer_block(rep, cg.LAYER_A)["clean"] is True
    assert rep["n_adjudicated"] == 3


def test_a_genuine_gain_exceeding_free_flexibility_passes():
    rep = run(challenger(), incumbent(), k0(), STRONG)
    assert rep["passed"], rep["blocking"]
    g = rep["gains"]
    assert abs(g["challenger_vs_incumbent"] - 0.01745) < 1e-9
    assert abs(g["k0_vs_incumbent"] - 0.00326) < 1e-9
    assert abs(g["challenger_vs_k0"] - 0.01419) < 1e-9


# --------------------------------------------------------------------------------------------
# matched pipelines pass
# --------------------------------------------------------------------------------------------

def test_matched_pipelines_pass():
    rep = run(challenger(), incumbent(), k0(), STRONG)
    assert rep["passed"], rep["blocking"]
    assert rep["blocking"] == []
    assert "dimension_mismatch" not in kinds(rep)
    assert "dimension_unspecified" not in kinds(rep)
    assert rep["n_dimensions"] == len(cg.DIMENSIONS) == 17
    assert rep["pairs_checked"] == ["challenger|k0", "challenger|incumbent"]


# --------------------------------------------------------------------------------------------
# each dimension blocks on its own
# --------------------------------------------------------------------------------------------

def _one_dimension_blocks(dimension: str, other_value, *, on: str = "incumbent"):
    ch, inc, ctrl = challenger(), incumbent(), k0()
    if on == "incumbent":
        inc = incumbent(**{dimension: other_value})
        pair, layer = "challenger|incumbent", cg.LAYER_B
    else:
        ctrl = k0(**{dimension: other_value})
        pair, layer = "challenger|k0", cg.LAYER_A
    rep = run(ch, inc, ctrl, STRONG)
    assert not rep["passed"], f"{dimension} mismatch did not block"
    assert set(kinds(rep, "blocking")) == {"dimension_mismatch"}, kinds(rep, "blocking")
    f = rep["blocking"][0]
    assert f["dimension"] == dimension, f
    assert f["pair"] == pair, f
    assert f["layer"] == layer, f
    assert f["left_value"] != f["right_value"]
    return rep


def test_challenger_only_intercept_blocks():
    rep = _one_dimension_blocks("intercept_treatment",
                                "none: frozen coefficients, no fitted intercept")
    f = rep["blocking"][0]
    assert f["left_value"] == "free, unpenalised"


def test_mismatched_exposure_offset_blocks():
    _one_dimension_blocks("exposure_offset", "log(realised_minutes) — NOT the exposure bridge")


def test_different_clipping_blocks():
    _one_dimension_blocks("clipping", "no clipping")


def test_different_evaluation_rows_blocks():
    _one_dimension_blocks("evaluation_rows", "rows:n=27351:sha256=deadbeefdeadbeef")


def test_different_training_rows_blocks():
    _one_dimension_blocks("training_rows", "rows:n=20000:sha256=cafecafecafecafe")


def test_different_companion_components_blocks():
    _one_dimension_blocks("companion_components",
                          ("projected_player_possessions/1",))          # team prior dropped


def test_a_k0_side_mismatch_blocks_too():
    """Parity is checked on challenger|k0 as well; K0 is not exempt from the contract."""
    _one_dimension_blocks("calibration_freedom",
                          "affine post-fit rescaling of the fold mean", on="k0")


def test_row_digest_describes_row_sets_and_is_order_insensitive():
    a = cg.row_digest(["g1:p1", "g1:p2", "g2:p3"])
    b = cg.row_digest(["g2:p3", "g1:p1", "g1:p2"])
    c = cg.row_digest(["g1:p1", "g1:p2"])
    assert a == b and a != c
    assert a.startswith("rows:n=3:sha256=")
    rep = run(challenger(training_rows=cg.row_digest(["a", "b", "c"])),
              incumbent(training_rows=cg.row_digest(["c", "b", "a"])),
              k0(training_rows=cg.row_digest(["b", "a", "c"])), STRONG)
    assert rep["passed"], rep["blocking"]


# --------------------------------------------------------------------------------------------
# LAYER A — strict. A mismatch against the challenger's OWN control is not adjudicable.
# --------------------------------------------------------------------------------------------

def test_every_layer_a_dimension_blocks_and_is_not_adjudicable_by_an_ordinary_reason():
    """K0 is the challenger's pipeline with the features removed. Nothing may differ.

    An ordinary reason — however well written — does not excuse a Layer A mismatch, and the
    refused attempt is itself blocking so it cannot sit unnoticed in a manifest.
    """
    ordinary = ("the K0 run was produced on a different night by a slightly different harness; "
                "we are confident it makes no material difference")
    for dim in cg.DIMENSIONS:
        ctrl = k0(**{dim: "DIFFERENT-ON-K0"})
        adj = {f"challenger|k0:{dim}": ordinary}
        rep = cg.audit_fold(challenger(), incumbent(), ctrl, STRONG, adjudications=adj,
                            raise_on_block=False)
        assert not rep["passed"], f"a Layer A mismatch on {dim} was waved through"
        bk = kinds(rep, "blocking")
        assert "dimension_mismatch" in bk, (dim, bk)
        assert "layer_a_not_adjudicable" in bk, (dim, bk)
        f = next(x for x in rep["findings"]
                 if x["kind"] == "dimension_mismatch" and x["dimension"] == dim)
        assert f["layer"] == cg.LAYER_A and f["adjudicated"] is False, f
        assert rep["adjudications_applied"] == [], (dim, rep["adjudications_applied"])


def test_a_layer_b_reason_code_cannot_be_used_to_excuse_a_layer_a_mismatch():
    adj = {"challenger|k0:intercept_treatment": {
        "code": "incumbent_is_frozen_formula",
        "reason": "the control is frozen too, honestly"}}
    rep = cg.audit_fold(challenger(), incumbent(),
                        k0(intercept_treatment="none: frozen"), STRONG,
                        adjudications=adj, raise_on_block=False)
    assert not rep["passed"]
    bk = kinds(rep, "blocking")
    assert "layer_a_not_adjudicable" in bk and "dimension_mismatch" in bk, bk
    f = next(x for x in rep["findings"] if x["kind"] == "layer_a_not_adjudicable")
    assert f["reason_code"] == "incumbent_is_frozen_formula"
    assert cg.LAYER_A_OVERRIDE_CODE in f["detail"]


def test_the_layer_a_override_exists_but_is_loud_and_permanent():
    """There IS an extraordinary route. It cannot be taken quietly."""
    adj = {"challenger|k0:preprocessing": {
        "code": cg.LAYER_A_OVERRIDE_CODE,
        "layer_a_override": True,
        "reason": ("the K0 artefact was produced before the standardisation change; regenerating "
                   "it is scheduled, and this comparison is explicitly provisional")}}
    rep = run(challenger(), incumbent(), k0(preprocessing="z-scored inputs"), STRONG,
              adjudications=adj)
    assert rep["passed"], rep["blocking"]
    # the mismatch is still there, adjudicated and attributed
    f = next(x for x in rep["findings"]
             if x["kind"] == "dimension_mismatch" and x["dimension"] == "preprocessing")
    assert f["adjudicated"] is True and f["layer"] == cg.LAYER_A
    assert f["adjudication_code"] == cg.LAYER_A_OVERRIDE_CODE
    # and a separate, non-suppressible notice was raised
    assert "layer_a_parity_overridden" in kinds(rep)
    dt = rep["decision_table"]
    assert layer_block(rep, cg.LAYER_A)["n_overridden"] == 1
    assert dt["flexibility_was_waved_through"] is True
    assert cg.LAYER_A_OVERRIDE_CODE in dt["reason_codes_invoked"]
    assert "FLEXIBILITY WAVED THROUGH" in dt["text"]


def test_the_layer_a_override_needs_the_explicit_flag_as_well_as_the_code():
    adj = {"challenger|k0:preprocessing": {
        "code": cg.LAYER_A_OVERRIDE_CODE,          # no layer_a_override: True
        "reason": "trying to take the extraordinary route without saying so"}}
    rep = cg.audit_fold(challenger(), incumbent(), k0(preprocessing="z-scored inputs"), STRONG,
                        adjudications=adj, raise_on_block=False)
    assert not rep["passed"]
    assert "layer_a_not_adjudicable" in kinds(rep, "blocking")


def test_k0_missing_is_layer_a_and_not_adjudicable_by_an_ordinary_reason():
    rep = cg.audit_fold(challenger(), incumbent(), None,
                        {"challenger": STRONG_CHALLENGER_MAE, "incumbent": ARM_D_MAE},
                        adjudications={"k0_missing": "no control was run for this arm"},
                        raise_on_block=False)
    assert not rep["passed"]
    bk = kinds(rep, "blocking")
    assert "k0_missing" in bk and "layer_a_not_adjudicable" in bk, bk


# --------------------------------------------------------------------------------------------
# LAYER B — a structural difference may be adjudicated, but only with a NAMED CODE
# --------------------------------------------------------------------------------------------

def test_layer_b_structural_difference_with_a_valid_code_passes_and_stays_visible():
    adj = {"challenger|incumbent:intercept_treatment": {
        "code": "incumbent_has_no_fitted_intercept",
        "reason": ("Arm D is frozen and unfitted by registration; the size of the resulting "
                   "advantage is measured by k0_vs_incumbent = 0.00326")}}
    inc = incumbent(intercept_treatment="none: frozen coefficients, no fitted intercept")

    bare = cg.audit_fold(challenger(), inc, k0(), STRONG, raise_on_block=False)
    assert not bare["passed"]

    rep = run(challenger(), inc, k0(), STRONG, adjudications=adj)
    assert rep["passed"], rep["blocking"]
    assert len(rep["findings"]) == len(bare["findings"]), "adjudication must not delete findings"

    f = next(x for x in rep["findings"]
             if x["kind"] == "dimension_mismatch" and x["dimension"] == "intercept_treatment")
    assert f["adjudicated"] is True and f["layer"] == cg.LAYER_B
    assert f["adjudication_code"] == "incumbent_has_no_fitted_intercept"
    assert abs(f["quantified_by_k0"] - 0.00326) < 1e-9, "the allowance must be quantified by K0"
    assert rep["decision_table"]["reason_codes_invoked"] == {
        "incumbent_has_no_fitted_intercept": 1}


def test_layer_b_adjudication_with_an_unrecognised_code_blocks():
    adj = {"challenger|incumbent:intercept_treatment": {
        "code": "its_fine_honestly",
        "reason": "a perfectly good sentence attached to a code nobody agreed to"}}
    rep = cg.audit_fold(challenger(),
                        incumbent(intercept_treatment="none: frozen"), k0(), STRONG,
                        adjudications=adj, raise_on_block=False)
    assert not rep["passed"]
    bk = kinds(rep, "blocking")
    assert "adjudication_code_unrecognised" in bk, bk
    assert "dimension_mismatch" in bk, "the difference it tried to excuse must still block"
    f = next(x for x in rep["findings"] if x["kind"] == "adjudication_code_unrecognised")
    assert f["supplied_code"] == "its_fine_honestly"
    assert sorted(cg.LAYER_B_REASON_CODES) == f["recognised_codes"]


def test_layer_b_adjudication_with_no_code_at_all_blocks():
    """Free text alone is no longer an adjudication on Layer B."""
    adj = {"challenger|incumbent:intercept_treatment":
           "Arm D is frozen and unfitted; this is fine and everybody knows it"}
    rep = cg.audit_fold(challenger(),
                        incumbent(intercept_treatment="none: frozen"), k0(), STRONG,
                        adjudications=adj, raise_on_block=False)
    assert not rep["passed"]
    bk = kinds(rep, "blocking")
    assert "adjudication_code_missing" in bk and "dimension_mismatch" in bk, bk


def test_layer_b_adjudication_with_a_code_but_no_reason_blocks():
    """A code alone is not an adjudication either; adjudication_without_reason still governs."""
    adj = {"challenger|incumbent:intercept_treatment": {"code": "incumbent_is_frozen_formula"}}
    rep = cg.audit_fold(challenger(),
                        incumbent(intercept_treatment="none: frozen"), k0(), STRONG,
                        adjudications=adj, raise_on_block=False)
    assert not rep["passed"]
    bk = kinds(rep, "blocking")
    assert "adjudication_without_reason" in bk, bk
    assert "dimension_mismatch" in bk, bk
    assert rep["adjudications_applied"] == []
    assert "adjudication_without_reason" in cg.NON_ADJUDICABLE


def test_layer_b_cannot_excuse_different_evaluation_rows_or_folds():
    """A frozen formula has no TRAINING rows. It is still scored on the SAME evaluation rows."""
    for dim, other in (("evaluation_rows", "rows:n=100:sha256=abcabcabc"),
                       ("chronological_folds", ("2024", "2025"))):
        adj = {f"challenger|incumbent:{dim}": {
            "code": "incumbent_is_frozen_formula",
            "reason": "the frozen arm only has predictions for part of the window"}}
        rep = cg.audit_fold(challenger(), incumbent(**{dim: other}), k0(), STRONG,
                            adjudications=adj, raise_on_block=False)
        assert not rep["passed"], dim
        bk = kinds(rep, "blocking")
        assert "layer_b_dimension_not_adjudicable" in bk, (dim, bk)
        assert "dimension_mismatch" in bk, (dim, bk)
    assert cg.LAYER_B_NON_ADJUDICABLE_DIMENSIONS == frozenset(
        {"evaluation_rows", "chronological_folds"})


def test_layer_b_adjudication_without_k0_to_quantify_it_blocks():
    """A structural allowance may only be granted when K0 says what it is worth."""
    adj = {"challenger|incumbent:intercept_treatment": {
        "code": "incumbent_is_frozen_formula",
        "reason": "frozen by registration"}}
    rep = cg.audit_fold(challenger(), incumbent(intercept_treatment="none: frozen"), k0(),
                        {"challenger": STRONG_CHALLENGER_MAE, "incumbent": ARM_D_MAE},
                        adjudications=adj, raise_on_block=False)
    assert not rep["passed"]
    bk = kinds(rep, "blocking")
    assert "layer_b_adjudication_unquantified" in bk, bk
    assert "dimension_mismatch" in bk, bk


def test_the_reason_code_enum_is_closed_and_documented():
    assert "incumbent_is_frozen_formula" in cg.LAYER_B_REASON_CODES
    assert "incumbent_has_no_training_rows" in cg.LAYER_B_REASON_CODES
    assert "calibration_difference_quantified_by_k0" in cg.LAYER_B_REASON_CODES
    for code, doc in cg.LAYER_B_REASON_CODES.items():
        assert isinstance(doc, str) and len(doc) > 40, code
    # the Layer A override is a recognised code but is NOT a Layer B allowance
    assert cg.LAYER_A_OVERRIDE_CODE in cg.REASON_CODES
    assert cg.LAYER_A_OVERRIDE_CODE not in cg.LAYER_B_REASON_CODES
    assert set(cg.LAYER_B_REASON_CODES) < set(cg.REASON_CODES)


# --------------------------------------------------------------------------------------------
# K0 is mandatory and must really be K0
# --------------------------------------------------------------------------------------------

def test_missing_k0_blocks():
    rep = run(challenger(), incumbent(), None,
              {"challenger": STRONG_CHALLENGER_MAE, "incumbent": ARM_D_MAE})
    assert not rep["passed"]
    assert "k0_missing" in kinds(rep, "blocking")
    # and with no K0 there is no free-flexibility gain to report at all
    assert rep["gains"]["k0_vs_incumbent"] is None
    assert rep["gains"]["challenger_vs_k0"] is None
    assert rep["free_flexibility_gain"] is None
    assert rep["decision_table"]["headline_judgment"]["verdict"] == "undetermined"


def test_k0_with_substantive_features_blocks():
    rep = run(challenger(), incumbent(), k0(features=("expanded_role_bounded",)), STRONG)
    assert not rep["passed"]
    assert "k0_has_substantive_features" in kinds(rep, "blocking")


def test_k0_from_a_different_pipeline_blocks():
    rep = run(challenger(), incumbent(), k0(pipeline_id="a_separately_written_control"), STRONG)
    assert not rep["passed"]
    assert "k0_not_from_challenger_pipeline" in kinds(rep, "blocking")


def test_a_featureless_challenger_blocks():
    rep = run(side("not_really_a_challenger", "challenger", features=()), incumbent(), k0(),
              STRONG)
    assert not rep["passed"]
    assert "challenger_has_no_substantive_features" in kinds(rep, "blocking")


def test_require_matched_k0_raises_without_one_and_returns_a_report_with_one():
    raised = False
    try:
        cg.require_matched_k0(challenger(), None)
    except cg.ComparisonGateFailure as exc:
        raised = True
        assert "k0_missing" in str(exc)
    assert raised, "require_matched_k0 must refuse a comparison with no control"

    rep = cg.require_matched_k0(challenger(), k0())
    assert rep["matched"] is True and rep["passed"] is True
    assert rep["n_dimensions"] == len(cg.DIMENSIONS) == 17
    assert rep["layer"] == cg.LAYER_A
    assert rep["decision_table"]["scope"] == "layer_a_k0_match"
    json.dumps(rep["decision_table"])


# --------------------------------------------------------------------------------------------
# an unspecified dimension is a hard error, never a silent pass
# --------------------------------------------------------------------------------------------

def test_unspecified_dimension_blocks():
    d = dict(BASE)
    d.pop("link_function")
    ch = {"name": "arm_H", "pipeline_id": "turnover_p2_v1",
          "substantive_features": ("expanded_role_bounded",), **d}
    rep = run(ch, incumbent(), k0(), STRONG)
    assert not rep["passed"], "an omitted dimension must not pass"
    unspec = [f for f in rep["findings"] if f["kind"] == "dimension_unspecified"]
    assert [f["dimension"] for f in unspec] == ["link_function"], unspec
    assert unspec[0]["side"] == "challenger"
    assert "dimension_unspecified" in kinds(rep, "blocking")
    # it must be reported as UNSPECIFIED, not silently compared as equal or as a mismatch
    assert not any(f["kind"] == "dimension_mismatch" and f["dimension"] == "link_function"
                   for f in rep["findings"])


def test_every_dimension_blocks_when_omitted():
    """Not one of the seventeen may be silently defaulted."""
    for dim in cg.DIMENSIONS:
        d = dict(BASE)
        d.pop(dim)
        ch = {"name": "arm_H", "pipeline_id": "turnover_p2_v1",
              "substantive_features": ("f",), **d}
        rep = cg.audit_fold(ch, incumbent(), k0(), STRONG, raise_on_block=False)
        assert not rep["passed"], f"omitting {dim} passed"
        assert any(f["kind"] == "dimension_unspecified" and f["dimension"] == dim
                   for f in rep["blocking"]), dim


def test_explicit_none_is_accepted_where_a_dimension_does_not_apply():
    rep = run(challenger(post_processing=cg.NONE), incumbent(post_processing=cg.NONE),
              k0(post_processing=cg.NONE), STRONG)
    assert rep["passed"], rep["blocking"]


def test_a_typoed_dimension_key_blocks():
    d = dict(BASE)
    d.pop("link_function")
    d["linkfunction"] = "log"                      # typo: leaves link_function unspecified
    ch = {"name": "arm_H", "pipeline_id": "turnover_p2_v1",
          "substantive_features": ("f",), **d}
    rep = run(ch, incumbent(), k0(), STRONG)
    assert not rep["passed"]
    bk = kinds(rep, "blocking")
    assert "unknown_dimension" in bk and "dimension_unspecified" in bk, bk


def test_a_missing_pipeline_id_blocks():
    rep = run(side("arm_H", "challenger", features=("f",), pipeline_id=""), incumbent(), k0(),
              STRONG)
    assert not rep["passed"]
    assert "pipeline_id_unspecified" in kinds(rep, "blocking")


def test_pipeline_id_is_documented_as_asserted_not_demonstrated():
    """The remaining gap is machine-readable, not just prose in a docstring."""
    gap = next(g for g in cg.REMAINING_GAPS
               if g["gap"] == "pipeline_id_is_asserted_not_demonstrated")
    assert "producer-source digest binding" in gap["fix"]
    assert gap["status"].startswith("NOT IMPLEMENTED")
    rep = run(challenger(), incumbent(), k0(), STRONG)
    assert rep["remaining_gaps"][0]["gap"] == "pipeline_id_is_asserted_not_demonstrated"
    assert any("pipeline_id" in c["gap"] for c in rep["decision_table"]["caveats"])
    assert rep["sides"]["k0"]["pipeline_id_is_asserted_not_demonstrated"] is True


def test_a_missing_metric_blocks():
    rep = run(challenger(), incumbent(), k0(),
              {"challenger": STRONG_CHALLENGER_MAE, "k0": K0_MAE})
    assert not rep["passed"]
    f = [x for x in rep["blocking"] if x["kind"] == "metric_missing"]
    assert f and f[0]["side"] == "incumbent", rep["blocking"]


# --------------------------------------------------------------------------------------------
# adjudication: allowed, but permanently visible
# --------------------------------------------------------------------------------------------

def test_adjudicated_difference_passes_but_stays_visible():
    """The frozen incumbent genuinely cannot have a fitted intercept. That is adjudicable.

    It is not, however, forgettable: the finding stays in the report with its reason AND its code,
    and K0 is what quantifies the size of the difference that was waved through.
    """
    inc = incumbent(intercept_treatment="none: frozen coefficients, no fitted intercept")
    reason = ("Arm D is frozen and unfitted by registration; it structurally cannot carry a "
              "fitted intercept. The magnitude of the resulting advantage is measured by K0 "
              "(k0_vs_incumbent = 0.00326) and the challenger must exceed it.")
    adj = {"challenger|incumbent:intercept_treatment":
           {"code": "incumbent_is_frozen_formula", "reason": reason}}

    bare = cg.audit_fold(challenger(), inc, k0(), STRONG, raise_on_block=False)
    assert not bare["passed"]

    rep = run(challenger(), inc, k0(), STRONG, adjudications=adj)
    assert rep["passed"], rep["blocking"]

    # the finding did NOT vanish
    assert len(rep["findings"]) == len(bare["findings"]), "adjudication must not delete findings"
    f = next(x for x in rep["findings"]
             if x["kind"] == "dimension_mismatch" and x["dimension"] == "intercept_treatment")
    assert f["adjudicated"] is True
    assert f["adjudication_reason"] == reason
    assert f["adjudication_key"] == "challenger|incumbent:intercept_treatment"

    # and it is surfaced separately so a reader cannot miss it — with its layer and its code
    assert rep["n_adjudicated"] == 1
    assert rep["adjudications_applied"] == [
        {"kind": "dimension_mismatch", "dimension": "intercept_treatment",
         "pair": "challenger|incumbent", "side": None, "layer": cg.LAYER_B,
         "reason_code": "incumbent_is_frozen_formula",
         "adjudication_key": "challenger|incumbent:intercept_treatment",
         "adjudication_reason": reason}]


def test_adjudication_by_bare_dimension_name_also_works_and_carries_metadata():
    inc = incumbent(clipping="no clipping")
    adj = {"clipping": {"code": "incumbent_predates_this_rule",
                        "reason": "the frozen incumbent predates the clipping rule",
                        "by": "coordinator", "date": "2026-08-04"}}
    rep = run(challenger(), inc, k0(), STRONG, adjudications=adj)
    assert rep["passed"], rep["blocking"]
    f = next(x for x in rep["findings"] if x["kind"] == "dimension_mismatch")
    assert f["adjudicated"] is True
    assert f["adjudication_by"] == "coordinator"
    assert f["adjudication_date"] == "2026-08-04"
    assert f["adjudication_code"] == "incumbent_predates_this_rule"


def test_adjudication_without_a_reason_fails():
    inc = incumbent(intercept_treatment="none: frozen, unfitted")
    for bad in (True, "", "   ", {"by": "coordinator"}, {"reason": ""},
                {"code": "incumbent_is_frozen_formula"}):
        rep = run(challenger(), inc, k0(), STRONG,
                  adjudications={"challenger|incumbent:intercept_treatment": bad})
        assert not rep["passed"], f"a reasonless adjudication ({bad!r}) was accepted"
        bk = kinds(rep, "blocking")
        assert "adjudication_without_reason" in bk, bk
        # and the difference it tried to excuse is still blocking
        assert "dimension_mismatch" in bk, bk


def test_the_free_flexibility_finding_is_itself_adjudicable_but_visible():
    """An evidence-layer finding; a code is optional there, a reason never is."""
    reason = "reported as a negative result; retained for the ledger, not promoted"
    rep = run(challenger(), incumbent(), k0(), WEAK,
              adjudications={"gain_within_free_flexibility": reason})
    assert rep["passed"], rep["blocking"]
    f = next(x for x in rep["findings"] if x["kind"] == "gain_within_free_flexibility")
    assert f["adjudicated"] is True and f["adjudication_reason"] == reason
    assert f["layer"] == cg.LAYER_EVIDENCE
    assert abs(f["k0_vs_incumbent"] - 0.00326) < 1e-9


def test_a_stale_adjudication_is_surfaced_not_silently_ignored():
    rep = run(challenger(), incumbent(), k0(), STRONG,
              adjudications={"clipping": "left over from an earlier comparison"})
    assert rep["passed"], rep["blocking"]
    assert "adjudication_unused" in kinds(rep)


# --------------------------------------------------------------------------------------------
# per fold AND on the consolidated manifest
# --------------------------------------------------------------------------------------------

def _manifest(fold_metrics: dict, consolidated: dict, **kw) -> dict:
    m = {"comparison_id": "arm_H_vs_arm_D", "metric_name": "operational_team_mae",
         "lower_is_better": True,
         "challenger": challenger(), "k0": k0(), "incumbent": incumbent(),
         "folds": fold_metrics, "consolidated": consolidated}
    m.update(kw)
    return m


def _clean_folds() -> dict:
    return {f: {"challenger": STRONG_CHALLENGER_MAE, "k0": K0_MAE, "incumbent": ARM_D_MAE}
            for f in FOLDS}


def test_manifest_audit_runs_every_fold_and_the_consolidation():
    rep = cg.audit(_manifest(_clean_folds(), dict(STRONG)))
    assert rep["passed"], rep["blocking"]
    assert rep["n_folds"] == 5
    assert sorted(rep["folds"]) == sorted(FOLDS)
    for f in FOLDS:
        assert rep["folds"][f]["passed"]
        assert abs(rep["folds"][f]["gains"]["k0_vs_incumbent"] - 0.00326) < 1e-9
        assert rep["folds"][f]["decision_table"]["scope"] == f
    assert rep["consolidated"]["passed"]
    assert rep["reference_case"]["k0_intercept_only"] == 2.96419
    assert rep["reference_case"]["frozen_arm_d"] == 2.96745
    assert rep["decision_table"]["gains_source"] == "consolidated"


def test_one_bad_fold_blocks_the_manifest_even_when_the_consolidation_looks_fine():
    """A consolidated comparison can average away a fold whose whole advantage was free."""
    folds = _clean_folds()
    folds["2022"] = {"challenger": WEAK_CHALLENGER_MAE, "k0": K0_MAE, "incumbent": ARM_D_MAE}
    rep = cg.audit(_manifest(folds, dict(STRONG)), raise_on_block=False)
    assert not rep["passed"]
    assert rep["consolidated"]["passed"], "the consolidated number alone would have passed"
    assert rep["folds"]["2022"]["passed"] is False
    assert all(rep["folds"][f]["passed"] for f in FOLDS if f != "2022")
    bad = [f for f in rep["blocking"] if f["kind"] == "gain_within_free_flexibility"]
    assert len(bad) == 1 and bad[0]["fold"] == "2022", bad
    raised = False
    try:
        cg.audit(_manifest(folds, dict(STRONG)))
    except cg.ComparisonGateFailure:
        raised = True
    assert raised


def test_a_manifest_with_no_per_fold_entries_blocks():
    rep = cg.audit(_manifest({}, dict(STRONG)), raise_on_block=False)
    assert not rep["passed"]
    assert "no_per_fold_audit" in kinds(rep, "blocking")


def test_a_manifest_with_no_consolidation_blocks():
    m = _manifest(_clean_folds(), dict(STRONG))
    m["consolidated"] = None
    rep = cg.audit(m, raise_on_block=False)
    assert not rep["passed"]
    assert "no_consolidated_audit" in kinds(rep, "blocking")


def test_auditing_a_subset_of_the_declared_folds_blocks():
    folds = {f: _clean_folds()[f] for f in ("2021", "2022")}
    rep = cg.audit(_manifest(folds, dict(STRONG)), raise_on_block=False)
    assert not rep["passed"]
    f = next(x for x in rep["blocking"] if x["kind"] == "fold_set_mismatch")
    assert f["missing"] == ["2023", "2024", "2025"], f


def test_per_fold_row_overrides_keep_parity():
    """training/evaluation rows legitimately differ BY fold; they must still match ACROSS sides."""
    folds = {}
    for i, f in enumerate(FOLDS):
        ov = {"training_rows": cg.row_digest([f"{f}:{j}" for j in range(100 + i)]),
              "evaluation_rows": cg.row_digest([f"{f}:eval:{j}" for j in range(50 + i)])}
        folds[f] = {"challenger": STRONG_CHALLENGER_MAE, "k0": K0_MAE, "incumbent": ARM_D_MAE,
                    "overrides": {r: dict(ov) for r in ("challenger", "k0", "incumbent")}}
    rep = cg.audit(_manifest(folds, dict(STRONG)))
    assert rep["passed"], rep["blocking"]
    assert (rep["folds"]["2021"]["sides"]["challenger"]["dimensions"]["training_rows"]
            != rep["folds"]["2022"]["sides"]["challenger"]["dimensions"]["training_rows"])


def test_a_per_fold_override_applied_to_only_one_side_blocks():
    folds = _clean_folds()
    folds["2023"] = {**folds["2023"],
                     "overrides": {"challenger": {"training_rows": "rows:n=1:sha256=zz"}}}
    rep = cg.audit(_manifest(folds, dict(STRONG)), raise_on_block=False)
    assert not rep["passed"]
    bad = [f for f in rep["blocking"]
           if f["kind"] == "dimension_mismatch" and f["dimension"] == "training_rows"]
    assert bad and all(f["fold"] == "2023" for f in bad), bad
    # a per-fold override that breaks challenger|k0 is a LAYER A defect
    assert any(f["layer"] == cg.LAYER_A for f in bad), bad


def test_manifest_adjudication_reaches_every_fold_and_stays_visible():
    m = _manifest(_clean_folds(), dict(STRONG))
    m["incumbent"] = incumbent(intercept_treatment="none: frozen, unfitted")
    reason = "Arm D is frozen and unfitted; K0 measures what that is worth (0.00326)"
    m["adjudications"] = {"challenger|incumbent:intercept_treatment":
                          {"code": "incumbent_is_frozen_formula", "reason": reason}}
    rep = cg.audit(m)
    assert rep["passed"], rep["blocking"]
    assert rep["n_adjudicated"] == 6, rep["n_adjudicated"]     # 5 folds + the consolidation
    for f in FOLDS:
        assert rep["folds"][f]["n_adjudicated"] == 1
        assert rep["folds"][f]["adjudications_applied"][0]["adjudication_reason"] == reason
        assert rep["folds"][f]["adjudications_applied"][0]["reason_code"] == \
            "incumbent_is_frozen_formula"
    assert all(a["adjudication_reason"] == reason for a in rep["adjudications_applied"])
    assert rep["decision_table"]["reason_codes_invoked"] == {"incumbent_is_frozen_formula": 6}


def test_the_full_ws2_manifest_in_two_layer_form():
    """Every fold, the frozen incumbent, the three named allowances, and a denied credit."""
    m = _manifest(_clean_folds(), dict(WEAK))
    m["incumbent"] = frozen_incumbent()
    m["adjudications"] = dict(FROZEN_ADJUDICATIONS)
    rep = cg.audit(m, raise_on_block=False)
    assert not rep["passed"], "the consolidated challenger sits inside the free-flexibility gap"
    assert all(rep["folds"][f]["passed"] for f in FOLDS), "the folds themselves are fine"
    assert rep["consolidated"]["passed"] is False
    dt = rep["decision_table"]
    assert dt["reason_codes_invoked"] == {"incumbent_is_frozen_formula": 12,
                                          "incumbent_has_no_training_rows": 6}
    assert layer_block(rep, cg.LAYER_A)["clean"] is True
    assert abs(dt["credit_denied_to_challenger"] - 0.00326) < 1e-9
    assert dt["headline_judgment"]["verdict"] == "beats_incumbent_but_fails_k0"
    assert dt["feature_value_demonstrated"] is False


# --------------------------------------------------------------------------------------------
# the decision table
# --------------------------------------------------------------------------------------------

def test_the_decision_table_is_present_json_serialisable_and_names_every_code():
    m = _manifest(_clean_folds(), dict(STRONG))
    m["incumbent"] = frozen_incumbent(clipping="no clipping")
    adj = dict(FROZEN_ADJUDICATIONS)
    adj["challenger|incumbent:clipping"] = {
        "code": "incumbent_predates_this_rule",
        "reason": "the frozen arm was registered before the clipping rule existed"}
    m["adjudications"] = adj
    rep = cg.audit(m)
    assert rep["passed"], rep["blocking"]

    for scope in [rep] + [rep["consolidated"]] + list(rep["folds"].values()):
        dt = scope["decision_table"]
        json.dumps(dt)                                    # strictly serialisable, no default=
        assert dt["schema"] == "comparison_gate.decision_table/2"
        assert [row["row"] for row in dt["gains"]] == [
            "challenger_vs_incumbent", "k0_vs_incumbent", "challenger_vs_k0"]
        assert dt["primary_incremental_test"] == "challenger_vs_k0"
        assert [b["layer"] for b in dt["layers"]] == [cg.LAYER_A, cg.LAYER_B, cg.LAYER_EVIDENCE]
        # every code that was applied anywhere in this scope is named in the table
        applied = {a["reason_code"] for a in scope["adjudications_applied"]
                   if a["reason_code"]}
        assert applied <= set(dt["reason_codes_invoked"]), (applied, dt["reason_codes_invoked"])
        assert dt["flexibility_was_waved_through"] is True
        assert dt["n_waved_through"] == len(dt["unmatched_flexibility_waved_through"])

    dt = rep["decision_table"]
    assert set(dt["reason_codes_invoked"]) == {"incumbent_is_frozen_formula",
                                               "incumbent_has_no_training_rows",
                                               "incumbent_predates_this_rule"}
    assert dt["reason_codes_invoked"]["incumbent_predates_this_rule"] == 6
    text = rep["decision_table_text"]
    for code in dt["reason_codes_invoked"]:
        assert code in text, code
    assert "FLEXIBILITY WAVED THROUGH" in text
    assert "PRIMARY TEST OF FEATURE VALUE" in text
    assert "credit DENIED to challenger" in text


def test_the_decision_table_shows_a_clean_comparison_as_clean():
    rep = cg.audit(_manifest(_clean_folds(), dict(STRONG)))
    dt = rep["decision_table"]
    assert dt["flexibility_was_waved_through"] is False
    assert dt["reason_codes_invoked"] == {}
    assert dt["unmatched_flexibility_waved_through"] == []
    assert "no flexibility waved through" in dt["text"]
    assert dt["headline_judgment"]["verdict"] == "features_bought_incremental_value"
    assert dt["identity_holds"] is True


def test_the_decision_table_makes_a_blocked_layer_a_defect_obvious():
    rep = cg.audit_fold(challenger(), incumbent(), k0(link_function="identity"), STRONG,
                        raise_on_block=False)
    a = layer_block(rep, cg.LAYER_A)
    assert a["clean"] is False
    assert a["dimensions_in_mismatch"] == ["link_function"]
    assert a["n_blocking"] == 1
    assert "LAYER A MISMATCH" in rep["decision_table_text"]
    assert a["strict_dimension_map"]["link"] == ["link_function"]


# --------------------------------------------------------------------------------------------
# THE HARD RULE — beats the incumbent, fails K0, never called beneficial
# --------------------------------------------------------------------------------------------

def test_beats_incumbent_but_fails_k0_is_labelled_not_beneficial_in_the_table_row_itself():
    """The state the whole module exists for, and the words it must be given.

    The label has to live on the ROW, not in a footnote elsewhere in the report: a consumer that
    renders only the gains rows must still be unable to call this a feature win.
    """
    rep = cg.audit_fold(challenger(), incumbent(), k0(), WEAK, raise_on_block=False)
    dt = rep["decision_table"]

    # the state: positive against production, non-positive against its own control
    assert dt["challenger_still_improves_frozen_incumbent"] is True
    assert dt["primary_incremental_value"] < 0
    assert dt["beats_incumbent_but_fails_k0"] is True
    assert dt["feature_value_demonstrated"] is False
    assert dt["not_beneficial_label"] == cg.NOT_BENEFICIAL_LABEL

    rows = {r["row"]: r for r in dt["gains"]}
    # the operational row carries the not-beneficial verdict, in words, itself
    cvi_row = rows["challenger_vs_incumbent"]
    assert cvi_row["value"] > 0
    assert cvi_row["verdict"] == "beats_incumbent_but_fails_k0"
    assert cvi_row["label"] == cg.NOT_BENEFICIAL_LABEL
    assert "NOT BENEFICIAL" in cvi_row["label"]
    assert cvi_row["attributes_value_to_features"] is False
    assert cvi_row["operational_relevance_only"] is True
    # and so does the primary row
    cvk_row = rows["challenger_vs_k0"]
    assert cvk_row["feature_value_demonstrated"] is False
    assert cvk_row["is_primary_test"] is True
    assert cvk_row["attributes_value_to_features"] is True
    assert "NOT BENEFICIAL" in cvk_row["label"]

    # the rendered table cannot be skimmed past either
    text = dt["text"]
    assert "NOT BENEFICIAL" in text
    assert "must NOT be described as a beneficial feature" in text


def test_no_report_ever_calls_that_state_beneficial():
    """Sweep every verdict string the module can emit for this state."""
    rep = cg.audit_fold(challenger(), incumbent(), k0(), WEAK, raise_on_block=False)
    hj = rep["decision_table"]["headline_judgment"]
    assert hj["feature_value_demonstrated"] is False
    assert hj["challenger_still_improves_frozen_incumbent"] is True
    assert "NOT BENEFICIAL" in hj["label"] and "NOT BENEFICIAL" in hj["statement"]
    assert "must NOT be described as a beneficial feature" in hj["statement"]
    # a challenger that is behind on BOTH contrasts is a different, plainer verdict
    behind = cg.audit_fold(challenger(), incumbent(), k0(),
                           {"challenger": 2.99, "k0": K0_MAE, "incumbent": ARM_D_MAE},
                           raise_on_block=False)
    bhj = behind["decision_table"]["headline_judgment"]
    assert bhj["verdict"] == "features_bought_nothing_beyond_k0"
    assert bhj["challenger_still_improves_frozen_incumbent"] is False
    assert behind["decision_table"]["beats_incumbent_but_fails_k0"] is False


def test_layer_a_is_named_the_primary_test_and_layer_b_only_operational_relevance():
    rep = cg.audit_fold(challenger(), frozen_incumbent(), k0(), STRONG,
                        adjudications=FROZEN_ADJUDICATIONS, raise_on_block=False)
    a, b = layer_block(rep, cg.LAYER_A), layer_block(rep, cg.LAYER_B)
    assert a["is_primary_test_of_feature_value"] is True
    assert a["role"] == "primary_test_of_feature_value"
    assert a["contrast"] == "challenger_vs_k0"
    assert b["is_primary_test_of_feature_value"] is False
    assert b["role"] == "operational_relevance_only"
    assert "OPERATIONAL RELEVANCE ONLY" in b["attribution_limit"]
    assert "cannot attribute" in b["attribution_limit"]
    assert rep["decision_table"]["primary_test_layer"] == cg.LAYER_A


# --------------------------------------------------------------------------------------------
# Layer B must report ALL of it: exact values, code, three contrasts, uncertainty, both verdicts
# --------------------------------------------------------------------------------------------

def test_the_layer_b_report_contains_everything_it_is_required_to_contain():
    unc = {"challenger_vs_incumbent": {"se": 0.0021, "ci": [0.0133, 0.0216], "ci_level": 0.95,
                                       "method": "paired bootstrap over folds, 10k draws"},
           "challenger_vs_k0": {"se": 0.0019, "ci": [0.0104, 0.0180], "ci_level": 0.95,
                                "method": "paired bootstrap over folds, 10k draws"}}
    rep = run(challenger(), frozen_incumbent(), k0(), STRONG,
              adjudications=FROZEN_ADJUDICATIONS, uncertainty=unc)
    assert rep["passed"], rep["blocking"]
    b = layer_block(rep, cg.LAYER_B)

    # 1. the exact structural mismatch — which dimension AND the two differing values
    sd = {x["dimension"]: x for x in b["structural_differences"]}
    assert set(sd) == {"intercept_treatment", "penalty_treatment", "training_rows"}
    assert sd["training_rows"]["challenger_value"] == "rows:n=27351:sha256=1111111111111111"
    assert sd["training_rows"]["incumbent_value"] == "none: unfitted, frozen at registration"
    assert sd["training_rows"]["values_differ"] is True
    assert sd["training_rows"]["challenger_value"] in sd["training_rows"]["exact_difference"]
    assert sd["training_rows"]["incumbent_value"] in sd["training_rows"]["exact_difference"]

    # 2. its named reason code
    assert sd["training_rows"]["reason_code"] == "incumbent_has_no_training_rows"

    # 3/4/5. all three paired contrasts
    assert abs(b["contrasts"]["challenger_vs_incumbent"] - 0.01745) < 1e-9
    assert abs(b["contrasts"]["k0_vs_incumbent"] - 0.00326) < 1e-9
    assert abs(b["contrasts"]["challenger_vs_k0"] - 0.01419) < 1e-9

    # 6. uncertainty for ALL contrasts, present whether supplied or not
    ub = b["uncertainty"]
    assert set(ub) == set(cg.CONTRASTS)
    assert ub["challenger_vs_incumbent"]["supplied"] is True
    assert abs(ub["challenger_vs_incumbent"]["se"] - 0.0021) < 1e-12
    assert ub["challenger_vs_incumbent"]["ci"] == [0.0133, 0.0216]
    assert ub["challenger_vs_incumbent"]["ci_level"] == 0.95
    assert "bootstrap" in ub["challenger_vs_incumbent"]["method"]
    assert ub["k0_vs_incumbent"]["supplied"] is False
    assert "NO UNCERTAINTY SUPPLIED" in ub["k0_vs_incumbent"]["statement"]

    # 7. whether the feature adds anything beyond free flexibility
    assert b["feature_adds_beyond_free_flexibility"] is True
    # 8. whether the overall challenger still improves the frozen incumbent
    assert b["challenger_still_improves_frozen_incumbent"] is True


def test_the_exact_mismatch_values_reach_both_the_findings_and_the_rendered_output():
    rep = cg.audit_fold(challenger(), incumbent(clipping="no clipping"), k0(), STRONG,
                        raise_on_block=False)
    f = next(x for x in rep["findings"]
             if x["kind"] == "dimension_mismatch" and x["dimension"] == "clipping")
    assert f["left_value"] == "predictions clipped to [0.0, 25.0]"
    assert f["right_value"] == "no clipping"
    assert f["left_value"] in f["detail"] and f["right_value"] in f["detail"]
    sd = layer_block(rep, cg.LAYER_B)["structural_differences"][0]
    assert sd["challenger_value"] == "predictions clipped to [0.0, 25.0]"
    assert sd["incumbent_value"] == "no clipping"
    text = rep["decision_table_text"]
    assert "predictions clipped to [0.0, 25.0]" in text and "no clipping" in text


# --------------------------------------------------------------------------------------------
# uncertainty
# --------------------------------------------------------------------------------------------

def test_uncertainty_is_reported_as_absent_rather_than_omitted():
    rep = run(challenger(), incumbent(), k0(), STRONG)
    ub = rep["uncertainty"]["by_contrast"]
    assert set(ub) == set(cg.CONTRASTS), "a slot for every contrast, always"
    for c in cg.CONTRASTS:
        assert ub[c]["supplied"] is False
        assert ub[c]["se"] is None and ub[c]["ci"] is None
        assert "NO UNCERTAINTY SUPPLIED" in ub[c]["statement"]
        assert ub[c]["available"] is True, "the contrast itself was computable"
    assert rep["uncertainty"]["any_supplied"] is False
    assert rep["uncertainty"]["contrasts_without_uncertainty"] == list(cg.CONTRASTS)
    for row in rep["decision_table"]["gains"]:
        assert row["uncertainty"] is not None, "the row must carry the slot, not drop it"
        assert row["uncertainty"]["supplied"] is False
    assert "NO UNCERTAINTY SUPPLIED" in rep["decision_table_text"]


def test_uncertainty_is_carried_per_contrast_when_supplied():
    unc = {"challenger_vs_k0": {"se": 0.0019, "ci": [0.0104, 0.0180], "ci_level": 0.95,
                                "method": "paired bootstrap"},
           "k0_vs_incumbent": 0.0007,                       # a bare number reads as a std error
           "nonsense_contrast": {"se": 1.0}}
    rep = run(challenger(), incumbent(), k0(), STRONG, uncertainty=unc)
    ub = rep["uncertainty"]["by_contrast"]
    assert ub["challenger_vs_k0"]["supplied"] is True
    assert ub["challenger_vs_k0"]["ci"] == [0.0104, 0.0180]
    assert "paired bootstrap" in ub["challenger_vs_k0"]["statement"]
    assert ub["k0_vs_incumbent"]["supplied"] is True
    assert abs(ub["k0_vs_incumbent"]["se"] - 0.0007) < 1e-12
    assert ub["k0_vs_incumbent"]["ci"] is None
    assert ub["challenger_vs_incumbent"]["supplied"] is False
    assert rep["uncertainty"]["all_supplied"] is False
    assert rep["uncertainty"]["contrasts_without_uncertainty"] == ["challenger_vs_incumbent"]
    assert rep["uncertainty"]["unrecognised_contrast_keys"] == ["nonsense_contrast"]
    row = next(r for r in rep["decision_table"]["gains"] if r["row"] == "challenger_vs_k0")
    assert row["uncertainty"]["se"] == 0.0019
    assert "se=0.001900" in rep["decision_table_text"]


def test_uncertainty_flows_through_the_manifest_per_fold_and_consolidated():
    m = _manifest(_clean_folds(), dict(STRONG))
    m["uncertainty"] = {"challenger_vs_k0": {"se": 0.002}}
    m["folds"]["2022"] = {**m["folds"]["2022"],
                          "uncertainty": {"challenger_vs_k0": {"se": 0.009}}}
    rep = cg.audit(m)
    assert rep["passed"], rep["blocking"]
    assert rep["folds"]["2021"]["uncertainty"]["by_contrast"]["challenger_vs_k0"]["se"] == 0.002
    assert rep["folds"]["2022"]["uncertainty"]["by_contrast"]["challenger_vs_k0"]["se"] == 0.009
    assert rep["consolidated"]["uncertainty"]["by_contrast"]["challenger_vs_k0"]["se"] == 0.002
    dt = rep["decision_table"]
    assert dt["uncertainty"]["by_contrast"]["challenger_vs_k0"]["se"] == 0.002
    assert dt["uncertainty"]["by_contrast"]["k0_vs_incumbent"]["supplied"] is False


# --------------------------------------------------------------------------------------------
# named adjudications must be MACHINE-readable, not only prose
# --------------------------------------------------------------------------------------------

def test_every_adjudication_is_enumerable_from_json_without_reading_prose():
    """A consumer parsing the JSON must get dimension, code and reason as structured fields."""
    m = _manifest(_clean_folds(), dict(STRONG))
    m["incumbent"] = frozen_incumbent()
    m["adjudications"] = dict(FROZEN_ADJUDICATIONS)
    rep = cg.audit(m)
    assert rep["passed"], rep["blocking"]

    # round-trip through JSON so nothing can be an in-memory-only convenience
    dt = json.loads(json.dumps(rep["decision_table"]))
    reg = dt["adjudication_register"]
    assert len(reg) == 18 == dt["n_adjudications"], len(reg)   # 3 allowances x 6 scopes
    for a in reg:
        assert set(a) >= {"layer", "kind", "dimension", "reason_code", "reason",
                          "adjudication_key", "pair", "side", "quantified_by_k0", "fold"}
        assert a["layer"] in (cg.LAYER_A, cg.LAYER_B, cg.LAYER_EVIDENCE)
        assert a["dimension"] and a["reason_code"] and a["reason"]
        assert a["reason_code"] in cg.REASON_CODES

    # the register is sufficient on its own to reconstruct what was allowed and why
    pairs = sorted({(a["dimension"], a["reason_code"]) for a in reg})
    assert pairs == [("intercept_treatment", "incumbent_is_frozen_formula"),
                     ("penalty_treatment", "incumbent_is_frozen_formula"),
                     ("training_rows", "incumbent_has_no_training_rows")]
    assert {a["layer"] for a in reg} == {cg.LAYER_B}
    assert len(dt["adjudications_by_layer"][cg.LAYER_B]) == 18
    assert dt["adjudications_by_layer"][cg.LAYER_A] == []

    # and the same records are on the report itself, not only in the table
    applied = json.loads(json.dumps(rep["adjudications_applied"]))
    assert {a["reason_code"] for a in applied} == {"incumbent_is_frozen_formula",
                                                   "incumbent_has_no_training_rows"}
    assert all(a["layer"] == cg.LAYER_B and a["dimension"] for a in applied)


def test_the_machine_readable_register_also_carries_a_layer_a_override():
    adj = {"challenger|k0:preprocessing": {
        "code": cg.LAYER_A_OVERRIDE_CODE, "layer_a_override": True,
        "reason": "the K0 artefact predates the standardisation change; provisional"}}
    rep = cg.audit_fold(challenger(), incumbent(), k0(preprocessing="z-scored inputs"), STRONG,
                        adjudications=adj, raise_on_block=False)
    dt = json.loads(json.dumps(rep["decision_table"]))
    reg = dt["adjudication_register"]
    assert len(reg) == 1
    assert reg[0]["layer"] == cg.LAYER_A
    assert reg[0]["dimension"] == "preprocessing"
    assert reg[0]["reason_code"] == cg.LAYER_A_OVERRIDE_CODE
    assert reg[0]["reason"].startswith("the K0 artefact predates")
    # the waved-through list additionally carries the non-suppressible override notice
    assert len(dt["unmatched_flexibility_waved_through"]) == 2


# --------------------------------------------------------------------------------------------
# reporting shape
# --------------------------------------------------------------------------------------------

def test_the_report_is_json_serialisable_and_never_collapses_the_three_gains():
    rep = cg.audit(_manifest(_clean_folds(), dict(STRONG)))
    text = json.dumps(rep, default=str)
    assert len(text) > 0
    for scope in [rep["consolidated"]] + list(rep["folds"].values()):
        assert set(scope["gains"]) == {"challenger_vs_incumbent", "challenger_vs_k0",
                                       "k0_vs_incumbent"}
        assert scope["free_flexibility_gain"] == scope["gains"]["k0_vs_incumbent"]
        assert "gain" not in scope
        assert scope["decision_table"]["primary_incremental_value"] == \
            scope["gains"]["challenger_vs_k0"]


def test_higher_is_better_metrics_flip_the_sign_convention():
    rep = cg.gain_report({"challenger": 0.62, "k0": 0.60, "incumbent": 0.55},
                         lower_is_better=False, metric_name="pseudo_r2")
    g = rep["gains"]
    assert abs(g["challenger_vs_incumbent"] - 0.07) < 1e-9
    assert abs(g["k0_vs_incumbent"] - 0.05) < 1e-9
    assert abs(g["challenger_vs_k0"] - 0.02) < 1e-9
    assert rep["gain_identity_holds"] is True


def test_a_control_worse_than_the_incumbent_is_reported_not_hidden():
    rep = run(challenger(), incumbent(), k0(),
              {"challenger": 2.95, "k0": 2.98, "incumbent": ARM_D_MAE})
    assert rep["passed"], rep["blocking"]
    assert "free_flexibility_gain_negative" in kinds(rep)
    assert rep["free_flexibility_gain"] < 0


def test_a_gain_only_just_beating_the_control_is_reported_without_blocking():
    # challenger_vs_incumbent 0.005, k0_vs_incumbent 0.00326, net 0.00174 -> real but marginal
    rep = run(challenger(), incumbent(), k0(),
              {"challenger": ARM_D_MAE - 0.005, "k0": K0_MAE, "incumbent": ARM_D_MAE})
    assert rep["passed"], rep["blocking"]
    assert "gain_marginal_over_free_flexibility" in kinds(rep)
    assert rep["decision_table"]["headline_judgment"]["verdict"] == \
        "features_bought_less_than_pipeline_freedom"


def test_every_blocking_kind_is_declared_in_the_blocking_set():
    assert "gain_within_free_flexibility" in cg.BLOCKING
    assert "adjudication_without_reason" in cg.NON_ADJUDICABLE
    assert cg.NON_ADJUDICABLE <= cg.BLOCKING
    for k in ("layer_a_not_adjudicable", "adjudication_code_missing",
              "adjudication_code_unrecognised", "layer_b_dimension_not_adjudicable",
              "layer_b_adjudication_unquantified"):
        assert k in cg.BLOCKING and k in cg.NON_ADJUDICABLE, k
    # informational kinds must NOT be blocking
    for k in ("gain_marginal_over_free_flexibility", "free_flexibility_gain_negative",
              "adjudication_unused", "layer_a_parity_overridden"):
        assert k not in cg.BLOCKING, k


def test_every_finding_carries_its_layer():
    rep = cg.audit_fold(challenger(), frozen_incumbent(), k0(clipping="none"), WEAK,
                        raise_on_block=False)
    assert rep["findings"], "this comparison is a mess; it must produce findings"
    for f in rep["findings"]:
        assert f["layer"] in (cg.LAYER_A, cg.LAYER_B, cg.LAYER_EVIDENCE), f
        assert f["layer_name"] == cg.LAYER_NAMES[f["layer"]]
    layers = {f["layer"] for f in rep["findings"]}
    assert layers == {cg.LAYER_A, cg.LAYER_B, cg.LAYER_EVIDENCE}, layers


# --------------------------------------------------------------------------------------------

def main() -> int:
    tests = [(n, f) for n, f in list(globals().items())
             if n.startswith("test_") and callable(f)]
    print("=" * 78)
    print("comparison_gate — two-layer baseline-parity regression tests")
    print(f"({len(tests)} tests; nothing here is scored)")
    print("=" * 78)
    npass = nfail = 0
    for name, fn in tests:
        try:
            fn()
        except Exception:
            nfail += 1
            print(f"  [FAIL] {name}")
            traceback.print_exc()
        else:
            npass += 1
            print(f"  [PASS] {name}")
    print("=" * 78)
    print(f"{npass} passed, {nfail} failed, {len(tests)} total")
    return 1 if nfail else 0


if __name__ == "__main__":
    raise SystemExit(main())
