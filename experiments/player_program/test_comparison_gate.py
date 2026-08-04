#!/usr/bin/env python3
"""test_comparison_gate.py — regression tests for the baseline-parity gate.

The motivating case is real. In P1/P2, fitted challengers carried an unpenalised free intercept
that the unfitted frozen incumbent (Arm D) did not have:

    K0 (intercept-only, challenger's own pipeline, zero features)   2.96419
    frozen Arm D                                                    2.96745
    free-recalibration gain                                         0.00326

A challenger reporting a gain of 0.0020 over Arm D had therefore demonstrated nothing: a model
with no substantive features at all already obtained more than that from pipeline freedom alone.
``test_ws2_real_case_*`` pins those exact numbers.

**Nothing here is scored.** Every metric in this file is a literal supplied to the gate; no
artifact is read, no model is fitted, no forecast is compared to any outcome. The tests assert
gate verdicts and arithmetic on numbers written down in this file.

Run under pytest if it is available::

    python -m pytest experiments/player_program/test_comparison_gate.py -q

`pytest` is NOT installed in this environment, so the file is also directly runnable::

    python experiments/player_program/test_comparison_gate.py
"""

from __future__ import annotations

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

#: one fully specified pipeline, all sixteen dimensions stated.
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
    "candidate_universe": "all 35,629 Tier A obligations incl. the 8,278 non-appearers",
    "post_processing": "none",
    "prediction_universe": "identical to candidate_universe",
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


# --------------------------------------------------------------------------------------------
# the sixteen dimensions actually exist
# --------------------------------------------------------------------------------------------

def test_sixteen_dimensions_are_declared():
    assert len(cg.DIMENSIONS) == 16, cg.DIMENSIONS
    assert len(set(cg.DIMENSIONS)) == 16
    for required in ("intercept_treatment", "calibration_freedom", "penalty_treatment",
                     "exposure_offset", "training_rows", "evaluation_rows",
                     "chronological_folds", "clipping", "link_function", "preprocessing",
                     "missing_value_handling", "companion_components", "fallback_rules",
                     "candidate_universe", "post_processing", "prediction_universe"):
        assert required in cg.DIMENSIONS, required
    assert set(BASE) == set(cg.DIMENSIONS), "the fixture must state every dimension"


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
    inc = incumbent(intercept_treatment="none: frozen coefficients, no fitted intercept",
                    penalty_treatment="none: unfitted, frozen at registration",
                    training_rows="none: unfitted, frozen at registration")
    rep = run(challenger(), inc, k0(), WEAK)
    assert not rep["passed"]
    bk = kinds(rep, "blocking")
    assert "gain_within_free_flexibility" in bk
    mism = [f for f in rep["findings"] if f["kind"] == "dimension_mismatch"]
    assert {f["dimension"] for f in mism} == {"intercept_treatment", "penalty_treatment",
                                              "training_rows"}, mism
    assert all(f["pair"] == "challenger|incumbent" for f in mism)


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
    assert rep["n_dimensions"] == 16
    assert rep["pairs_checked"] == ["challenger|k0", "challenger|incumbent"]


# --------------------------------------------------------------------------------------------
# each dimension blocks on its own
# --------------------------------------------------------------------------------------------

def _one_dimension_blocks(dimension: str, other_value, *, on: str = "incumbent"):
    ch, inc, ctrl = challenger(), incumbent(), k0()
    if on == "incumbent":
        inc = incumbent(**{dimension: other_value})
        pair = "challenger|incumbent"
    else:
        ctrl = k0(**{dimension: other_value})
        pair = "challenger|k0"
    rep = run(ch, inc, ctrl, STRONG)
    assert not rep["passed"], f"{dimension} mismatch did not block"
    assert set(kinds(rep, "blocking")) == {"dimension_mismatch"}, kinds(rep, "blocking")
    f = rep["blocking"][0]
    assert f["dimension"] == dimension, f
    assert f["pair"] == pair, f
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
    assert rep["n_dimensions"] == 16


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
    """Not one of the sixteen may be silently defaulted."""
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

    It is not, however, forgettable: the finding stays in the report with its reason, and K0 is
    what quantifies the size of the difference that was waved through.
    """
    inc = incumbent(intercept_treatment="none: frozen coefficients, no fitted intercept")
    reason = ("Arm D is frozen and unfitted by registration; it structurally cannot carry a "
              "fitted intercept. The magnitude of the resulting advantage is measured by K0 "
              "(k0_vs_incumbent = 0.00326) and the challenger must exceed it.")
    adj = {"challenger|incumbent:intercept_treatment": reason}

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

    # and it is surfaced separately so a reader cannot miss it
    assert rep["n_adjudicated"] == 1
    assert rep["adjudications_applied"] == [
        {"kind": "dimension_mismatch", "dimension": "intercept_treatment",
         "pair": "challenger|incumbent", "side": None,
         "adjudication_key": "challenger|incumbent:intercept_treatment",
         "adjudication_reason": reason}]


def test_adjudication_by_bare_dimension_name_also_works_and_carries_metadata():
    inc = incumbent(clipping="no clipping")
    adj = {"clipping": {"reason": "the frozen incumbent predates the clipping rule",
                        "by": "coordinator", "date": "2026-08-04"}}
    rep = run(challenger(), inc, k0(), STRONG, adjudications=adj)
    assert rep["passed"], rep["blocking"]
    f = next(x for x in rep["findings"] if x["kind"] == "dimension_mismatch")
    assert f["adjudicated"] is True
    assert f["adjudication_by"] == "coordinator"
    assert f["adjudication_date"] == "2026-08-04"


def test_adjudication_without_a_reason_fails():
    inc = incumbent(intercept_treatment="none: frozen, unfitted")
    for bad in (True, "", "   ", {"by": "coordinator"}, {"reason": ""}):
        rep = run(challenger(), inc, k0(), STRONG,
                  adjudications={"challenger|incumbent:intercept_treatment": bad})
        assert not rep["passed"], f"a reasonless adjudication ({bad!r}) was accepted"
        bk = kinds(rep, "blocking")
        assert "adjudication_without_reason" in bk, bk
        # and the difference it tried to excuse is still blocking
        assert "dimension_mismatch" in bk, bk


def test_the_free_flexibility_finding_is_itself_adjudicable_but_visible():
    reason = "reported as a negative result; retained for the ledger, not promoted"
    rep = run(challenger(), incumbent(), k0(), WEAK,
              adjudications={"gain_within_free_flexibility": reason})
    assert rep["passed"], rep["blocking"]
    f = next(x for x in rep["findings"] if x["kind"] == "gain_within_free_flexibility")
    assert f["adjudicated"] is True and f["adjudication_reason"] == reason
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
    assert rep["consolidated"]["passed"]
    assert rep["reference_case"]["k0_intercept_only"] == 2.96419
    assert rep["reference_case"]["frozen_arm_d"] == 2.96745


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


def test_manifest_adjudication_reaches_every_fold_and_stays_visible():
    m = _manifest(_clean_folds(), dict(STRONG))
    m["incumbent"] = incumbent(intercept_treatment="none: frozen, unfitted")
    reason = "Arm D is frozen and unfitted; K0 measures what that is worth (0.00326)"
    m["adjudications"] = {"challenger|incumbent:intercept_treatment": reason}
    rep = cg.audit(m)
    assert rep["passed"], rep["blocking"]
    assert rep["n_adjudicated"] == 6, rep["n_adjudicated"]     # 5 folds + the consolidation
    for f in FOLDS:
        assert rep["folds"][f]["n_adjudicated"] == 1
        assert rep["folds"][f]["adjudications_applied"][0]["adjudication_reason"] == reason
    assert all(a["adjudication_reason"] == reason for a in rep["adjudications_applied"])


# --------------------------------------------------------------------------------------------
# reporting shape
# --------------------------------------------------------------------------------------------

def test_the_report_is_json_serialisable_and_never_collapses_the_three_gains():
    import json
    rep = cg.audit(_manifest(_clean_folds(), dict(STRONG)))
    text = json.dumps(rep, default=str)
    assert len(text) > 0
    for scope in [rep["consolidated"]] + list(rep["folds"].values()):
        assert set(scope["gains"]) == {"challenger_vs_incumbent", "challenger_vs_k0",
                                       "k0_vs_incumbent"}
        assert scope["free_flexibility_gain"] == scope["gains"]["k0_vs_incumbent"]
        assert "gain" not in scope


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


def test_every_blocking_kind_is_declared_in_the_blocking_set():
    assert "gain_within_free_flexibility" in cg.BLOCKING
    assert "adjudication_without_reason" in cg.NON_ADJUDICABLE
    assert cg.NON_ADJUDICABLE <= cg.BLOCKING
    # informational kinds must NOT be blocking
    for k in ("gain_marginal_over_free_flexibility", "free_flexibility_gain_negative",
              "adjudication_unused"):
        assert k not in cg.BLOCKING, k


# --------------------------------------------------------------------------------------------

def main() -> int:
    tests = [(n, f) for n, f in list(globals().items())
             if n.startswith("test_") and callable(f)]
    print("=" * 78)
    print("comparison_gate — baseline-parity regression tests")
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
