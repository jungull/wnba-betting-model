#!/usr/bin/env python3
"""test_gate_invocation.py — regression tests for the invocation gate around feature_gate.audit.

The motivating defect is real and is a property of a signature: ``feature_gate.audit`` accepts
``offset=``, ``target=``, ``outcome_mask=`` and ``test_df=`` as OPTIONAL keyword arguments, so a
caller who omits all four gets ``{"findings": [], "blocking": [], "passed": true}`` from a design
that was never checked for offset determinism, target leakage, outcome-encoding missingness or
train/test schema drift. That record is byte-indistinguishable from a real one.

The fold-degeneracy case is also real and is reproduced here in synthetic form, to the recorded
magnitude: ws3's 2022 training fold carried ``proj_off_poss_share`` with standard deviation
``7.80108356964482e-09`` and the gate blocks it as ``impossible_scaling``, while the pooled audit
over the same eight columns and 35,629 rows returned ``findings: []``. ``test_ws3_shape_*``
rebuilds that shape from a seeded RNG. **ws3 is not re-run and no ws3 artifact is read.**

**Nothing here is scored.** Every frame in this file is synthetic and seeded; no artifact is read,
no model is fitted, no forecast is compared to any outcome. The tests assert gate verdicts,
digests and call ordering.

pytest is NOT installed in this environment. This file has a standalone runner::

    python experiments/player_program/test_gate_invocation.py

It is also importable under pytest if that ever changes, since every test is a zero-argument
module-level ``test_*`` function.
"""

from __future__ import annotations

import json
import sys
import tempfile
import traceback
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import feature_gate                                                            # noqa: E402
import gate_invocation as gi                                                   # noqa: E402

EXPERIMENT = "turnover_p3_synthetic"
ARM = "A"
FOLD = "2022"

#: sentinel meaning "do not pass this keyword at all", so omission is tested as true omission
#: rather than as an explicit None.
OMIT = object()

#: ws3's measured fold-level standard deviation, reproduced exactly in synthetic data.
WS3_DEGENERATE_STD = 7.80108356964482e-09

#: The Case-1 dual-frame declaration used throughout the argument-layer tests below. The dual
#: frame is MANDATORY for every fitted design (contract §8a), and these designs are fitted
#: unchanged, so they declare that and let the wrapper prove it by digest. ``raw_df=df`` is the
#: correct form; the same object is passed and no copy is made.
NO_TRANSFORMATION = gi.no_transformation(
    "the producer emits this frame and it is fitted unchanged; declared so the identity of the "
    "pre-transformation and fitted frames is proven by digest rather than assumed")


# --------------------------------------------------------------------------------------------
# synthetic material
# --------------------------------------------------------------------------------------------

@dataclass
class Case:
    df: pd.DataFrame
    names: list
    offset: pd.Series
    target: pd.Series
    outcome_mask: pd.Series
    test_df: pd.DataFrame


def make_case(n: int = 200, seed: int = 11, prefix: str = "pg") -> Case:
    """A healthy, fully-specified invocation: independent features, real exposure, real target."""
    rng = np.random.default_rng(seed)
    idx = pd.Index([f"{prefix}{i:05d}" for i in range(n)], name="player_game_id")
    df = pd.DataFrame({
        "trailing_turnover_rate": rng.normal(0.13, 0.03, n),
        "trailing_minutes_share": rng.normal(0.55, 0.10, n),
        "opponent_pressure": rng.normal(0.0, 1.0, n),
    }, index=idx)
    names = list(df.columns)
    offset = pd.Series(np.log(rng.gamma(6.0, 6.0, n) + 5.0), index=idx, name="log_exposure")
    target = pd.Series(rng.poisson(2.5, n).astype(float), index=idx, name="turnovers")
    mask = pd.Series(rng.random(n) < 0.7, index=idx, name="did_appear")
    t_idx = pd.Index([f"{prefix}{i:05d}" for i in range(n, n + 80)], name="player_game_id")
    test_df = pd.DataFrame({c: rng.normal(0.0, 1.0, 80) for c in names}, index=t_idx)
    return Case(df, names, offset, target, mask, test_df)


CASE = make_case()


def audit(case: Case = CASE, *, raise_on_block: bool = False, **over) -> dict:
    kw = dict(experiment=EXPERIMENT, arm=ARM, fold=FOLD,
              offset=case.offset, target=case.target,
              outcome_mask=case.outcome_mask, test_df=case.test_df,
              raw_df=case.df, transformation=NO_TRANSFORMATION,
              raise_on_block=raise_on_block)
    kw.update(over)
    for k in [k for k, v in kw.items() if v is OMIT]:
        del kw[k]
    return gi.audit_fold(case.df, case.names, **kw)


def kinds(rep: dict) -> set:
    return {f["kind"] for f in rep["findings"]}


def blocking_kinds(rep: dict) -> set:
    return {f["kind"] for f in rep["blocking"]}


def variant(case: Case, name: str, kind: str):
    """One broken value for one argument. ``kind`` names the failure mode being induced."""
    n = len(case.df)
    idx = case.df.index
    if kind == "null":
        return None
    if kind == "omitted":
        return OMIT
    if kind == "placeholder":
        return {"offset": pd.Series(np.zeros(n), index=idx),
                "target": pd.Series(np.full(n, 3.0), index=idx),
                "outcome_mask": pd.Series(np.ones(n, dtype=bool), index=idx),
                "test_df": case.df}[name]
    if kind == "wrong_length":
        if name == "test_df":
            return pd.DataFrame({c: np.zeros(0) for c in case.names})
        return getattr(case, name).iloc[:-5]
    if kind == "misaligned":
        if name == "test_df":
            return case.df.iloc[::-1]
        return getattr(case, name).iloc[::-1]
    if kind == "different_universe":
        if name == "test_df":
            return case.df.iloc[:50]
        src = getattr(case, name)
        return pd.Series(src.to_numpy(),
                         index=pd.Index([f"zz{i:05d}" for i in range(n)], name=idx.name))
    raise AssertionError(kind)


# --------------------------------------------------------------------------------------------
# 1. the correct invocation
# --------------------------------------------------------------------------------------------

def test_a_fully_correct_invocation_passes_and_actually_calls_the_gate():
    rep = audit()
    assert rep["passed"], rep["blocking"]
    assert rep["gate_invoked"] is True
    assert rep["gate"]["passed"] is True, rep["gate"]["findings"]
    assert rep["complete"] is True
    assert rep["checks_not_run"] == []
    # every check the four arguments exist to enable is live
    for k in ("deterministic_transform_of_offset", "target_derived", "missingness_informative",
              "missingness_encodes_outcome", "schema_mismatch"):
        assert k in rep["checks_enabled"], k


def test_the_receipt_carries_a_digest_identifying_every_argument():
    rep = audit()
    for name in gi.REQUIRED_ARGUMENTS:
        a = rep["arguments"][name]
        assert a["supplied"] is True, name
        assert a["value_digest"] and "sha256=" in a["value_digest"], name
        assert a["index_digest"] and "sha256=" in a["index_digest"], name
        assert a["index_membership_digest"], name
        assert a["n"] is not None, name
    # the digests are of the ACTUAL objects, recomputable by a reader
    assert rep["arguments"]["offset"]["value_digest"] == gi.value_digest(
        CASE.offset, label="offset_values")
    assert rep["arguments"]["target"]["index_digest"] == gi.index_digest(
        CASE.target.index, label="target_index")
    # distinct arguments have distinct digests -- the receipt cannot confuse them
    digests = [rep["arguments"][n]["value_digest"] for n in gi.REQUIRED_ARGUMENTS]
    assert len(set(digests)) == len(digests)


def test_the_receipt_contains_every_field_the_contract_requires():
    rep = audit()
    assert rep["schema"] == gi.RECORD_SCHEMA
    # gate identity and caller identity -- the load-bearing pair
    assert rep["gate_module"]["source_sha256"] and len(rep["gate_module"]["source_sha256"]) == 64
    assert rep["gate_module"]["source_path"].endswith("feature_gate.py")
    assert rep["caller"]["source_sha256"] and len(rep["caller"]["source_sha256"]) == 64
    assert rep["caller"]["source_path"].endswith("test_gate_invocation.py")
    # experiment / arm / fold identity
    assert rep["identity"] == {"experiment": EXPERIMENT, "arm": ARM, "fold": FOLD,
                               "scope": "fold"}
    # design row identity, feature NAME membership and feature ORDER, separately
    d = rep["design"]
    assert d["design_row_identity_digest"] and d["design_row_membership_digest"]
    assert d["feature_order_digest"] and d["feature_name_membership_digest"]
    assert d["feature_order_digest"] != d["feature_name_membership_digest"]
    assert d["training_frame_digest"] and d["design_values_digest"]
    # row counts
    assert rep["row_counts"]["design_rows"] == len(CASE.df)
    assert rep["row_counts"]["offset"] == len(CASE.offset)
    assert rep["row_counts"]["test_df"] == len(CASE.test_df)
    # index-alignment result, per argument
    assert rep["alignment"]["offset"] == "identical"
    assert rep["alignment"]["target"] == "identical"
    assert rep["alignment"]["outcome_mask"] == "identical"
    assert rep["alignment"]["test_df"] == "held_out"
    # current-gate findings, adjudications, verdict, binding
    assert "gate_findings" in rep and isinstance(rep["gate_findings"], list)
    assert rep["adjudications_declared"] == {}
    assert rep["adjudications_applied"] == []
    assert rep["passed"] is True
    assert rep["binding"]["binding_digest"].startswith("binding:sha256=")
    assert rep["gate_arguments"] == {"corr_threshold": 0.999, "target_corr_threshold": 0.98,
                                     "missingness_corr_threshold": 0.5}


def test_feature_order_is_digested_separately_from_feature_membership():
    rep_a = audit()
    rep_b = gi.audit_fold(CASE.df, list(reversed(CASE.names)), experiment=EXPERIMENT, arm=ARM,
                          fold=FOLD, offset=CASE.offset, target=CASE.target,
                          outcome_mask=CASE.outcome_mask, test_df=CASE.test_df,
                          raw_df=CASE.df, transformation=NO_TRANSFORMATION,
                          raise_on_block=False)
    a, b = rep_a["design"], rep_b["design"]
    assert a["feature_name_membership_digest"] == b["feature_name_membership_digest"]
    assert a["feature_order_digest"] != b["feature_order_digest"]
    assert rep_a["binding"]["binding_digest"] != rep_b["binding"]["binding_digest"]


# --------------------------------------------------------------------------------------------
# 2. every required argument, every failure mode, generated one test per (argument, mode)
#
# Each asserts the expected blocking kind AND that feature_gate was never invoked, which is what
# "fails before fitting" means at this layer: the gate call is the last thing that happens before
# a fit, and it did not happen.
# --------------------------------------------------------------------------------------------

_EXPECTED = {
    ("offset", "omitted"): "argument_omitted",
    ("target", "omitted"): "argument_omitted",
    ("outcome_mask", "omitted"): "argument_omitted",
    ("test_df", "omitted"): "argument_omitted",
    ("offset", "null"): "argument_null",
    ("target", "null"): "argument_null",
    ("outcome_mask", "null"): "argument_null",
    ("test_df", "null"): "argument_null",
    ("offset", "wrong_length"): "argument_length_mismatch",
    ("target", "wrong_length"): "argument_length_mismatch",
    ("outcome_mask", "wrong_length"): "argument_length_mismatch",
    ("test_df", "wrong_length"): "argument_empty",
    ("offset", "misaligned"): "argument_misaligned",
    ("target", "misaligned"): "argument_misaligned",
    ("outcome_mask", "misaligned"): "argument_misaligned",
    ("test_df", "misaligned"): "test_df_overlaps_design",
    ("offset", "different_universe"): "argument_universe_mismatch",
    ("target", "different_universe"): "argument_universe_mismatch",
    ("outcome_mask", "different_universe"): "argument_universe_mismatch",
    ("test_df", "different_universe"): "test_df_overlaps_design",
    ("offset", "placeholder"): "argument_is_placeholder_default",
    ("target", "placeholder"): "argument_is_placeholder_default",
    ("outcome_mask", "placeholder"): "argument_is_placeholder_default",
    ("test_df", "placeholder"): "argument_is_placeholder_default",
}


def _make_argument_test(name: str, mode: str, expected: str):
    def t():
        rep = audit(**{name: variant(CASE, name, mode)})
        assert expected in blocking_kinds(rep), (name, mode, sorted(blocking_kinds(rep)))
        assert any(f.get("argument") == name for f in rep["blocking"]
                   if f["kind"] == expected), (name, mode)
        assert rep["passed"] is False
        assert rep["gate_invoked"] is False, "the gate ran; the failure did not precede the model"
        assert "gate_not_invoked" in kinds(rep)
    t.__doc__ = f"{name} / {mode} -> {expected}"
    return t


for _n, _m in _EXPECTED:
    globals()[f"test_argument_{_n}_{_m}_blocks"] = _make_argument_test(
        _n, _m, _EXPECTED[(_n, _m)])


def test_omission_names_the_checks_it_would_have_deleted():
    for name in gi.REQUIRED_ARGUMENTS:
        rep = audit(**{name: OMIT})
        f = [x for x in rep["blocking"] if x["kind"] == "argument_omitted"][0]
        assert set(f["disabled_checks"]) == set(gi.ARGUMENT_ENABLES[name]), name
        assert rep["checks_enabled"] == sorted(
            {k for other in gi.REQUIRED_ARGUMENTS if other != name
             for k in gi.ARGUMENT_ENABLES[other]}), name


def test_a_right_length_wrong_universe_argument_is_caught_by_the_membership_digest():
    bad = variant(CASE, "offset", "different_universe")
    assert len(bad) == len(CASE.offset)                       # the length is innocent
    assert gi.value_digest(bad) == gi.value_digest(CASE.offset)   # so are the VALUES
    rep = audit(offset=bad)
    f = [x for x in rep["blocking"] if x["kind"] == "argument_universe_mismatch"][0]
    assert f["n_shared_labels"] == 0
    assert f["n_only_in_argument"] == len(CASE.df)
    assert (f["design_index_membership_digest"]
            != f["argument_index_membership_digest"])
    assert rep["gate_invoked"] is False


def test_a_bare_ndarray_has_no_row_identity_and_blocks():
    rep = audit(offset=CASE.offset.to_numpy())
    assert "argument_row_identity_absent" in blocking_kinds(rep)
    assert rep["gate_invoked"] is False


def test_a_non_boolean_outcome_mask_blocks():
    m = pd.Series(np.where(np.arange(len(CASE.df)) % 3 == 0, np.nan, 1.0), index=CASE.df.index)
    rep = audit(outcome_mask=m)
    assert "argument_not_boolean" in blocking_kinds(rep)


def test_a_constant_non_zero_offset_blocks_as_a_constant():
    rep = audit(offset=pd.Series(np.full(len(CASE.df), 2.5), index=CASE.df.index))
    assert "argument_constant" in blocking_kinds(rep)


def test_an_all_nan_target_blocks():
    rep = audit(target=pd.Series(np.full(len(CASE.df), np.nan), index=CASE.df.index))
    assert "argument_all_non_finite" in blocking_kinds(rep)


def test_placeholder_findings_explain_why_the_check_is_dead():
    rep = audit(outcome_mask=variant(CASE, "outcome_mask", "placeholder"))
    f = [x for x in rep["blocking"] if x["kind"] == "argument_is_placeholder_default"][0]
    assert f["placeholder"] == "all True"
    assert "off_diag" in f["detail"]


# --------------------------------------------------------------------------------------------
# 3. silent reorder vs explicit deterministic alignment
# --------------------------------------------------------------------------------------------

def test_a_silent_reorder_blocks_and_is_not_repaired():
    rep = audit(offset=CASE.offset.iloc[::-1])
    f = [x for x in rep["blocking"] if x["kind"] == "argument_misaligned"][0]
    assert f["n_positions_differing"] == len(CASE.df)
    assert f["argument_index_digest"] != f["design_index_digest"]
    assert rep["alignment"]["offset"] == "misaligned"
    assert rep["alignment_steps"] == []
    assert rep["gate_invoked"] is False


def test_an_explicit_deterministic_alignment_passes_and_is_recorded():
    rep = audit(offset=CASE.offset.iloc[::-1],
                align={"offset": "reindex_to_design_index"})
    assert rep["passed"], rep["blocking"]
    assert rep["alignment"]["offset"] == "realigned_explicitly"
    assert len(rep["alignment_steps"]) == 1
    step = rep["alignment_steps"][0]
    assert step["method"] == "reindex_to_design_index"
    assert step["index_digest_as_supplied"] != step["index_digest_as_audited"]
    assert step["value_digest_as_supplied"] != step["value_digest_as_audited"]
    # what was AUDITED is the design's own row order
    assert step["index_digest_as_audited"] == gi.index_digest(CASE.df.index,
                                                              label="offset_index")
    assert rep["arguments"]["offset"]["alignment"]["status"] == "realigned_explicitly"
    assert "argument_realigned" in kinds(rep)


def test_alignment_cannot_rescue_a_different_universe():
    rep = audit(offset=variant(CASE, "offset", "different_universe"),
                align={"offset": "reindex_to_design_index"})
    assert "argument_universe_mismatch" in blocking_kinds(rep)
    assert rep["alignment_steps"] == []


def test_alignment_cannot_rescue_a_wrong_length():
    rep = audit(target=variant(CASE, "target", "wrong_length"),
                align={"target": "reindex_to_design_index"})
    assert "argument_length_mismatch" in blocking_kinds(rep)


def test_an_unknown_alignment_method_blocks():
    rep = audit(offset=CASE.offset.iloc[::-1], align={"offset": "sort_and_hope"})
    assert "unknown_alignment_method" in blocking_kinds(rep)
    assert "argument_misaligned" in blocking_kinds(rep)


def test_a_blanket_alignment_string_is_not_an_explicit_step():
    rep = audit(offset=CASE.offset.iloc[::-1], align="reindex_to_design_index")
    assert "unknown_alignment_method" in blocking_kinds(rep)


def test_an_unnecessary_alignment_declaration_is_recorded_but_does_not_block():
    rep = audit(align={"offset": "reindex_to_design_index"})
    assert rep["passed"], rep["blocking"]
    assert "alignment_unused" in kinds(rep)


# --------------------------------------------------------------------------------------------
# 4. the failure precedes the model
# --------------------------------------------------------------------------------------------

def test_guarded_fit_does_not_reach_the_fit_when_an_argument_is_omitted():
    calls = []
    with tempfile.TemporaryDirectory() as d:
        try:
            gi.guarded_fit(lambda rec, bound: calls.append("fitted"),
                           CASE.df, CASE.names, experiment=EXPERIMENT, arm=ARM, fold=FOLD,
                           receipt_path=Path(d) / "r.json",
                           target=CASE.target, outcome_mask=CASE.outcome_mask,
                           test_df=CASE.test_df)          # offset omitted
        except gi.GateInvocationFailure as e:
            assert "argument_omitted" in str(e)
        else:
            raise AssertionError("guarded_fit did not raise")
    assert calls == [], "the fit ran despite a missing required argument"


def test_the_gate_itself_is_never_called_when_an_argument_is_omitted():
    seen = []
    real = feature_gate.audit
    gi.feature_gate.audit = lambda *a, **k: seen.append(k) or real(*a, **k)
    try:
        rep = audit(target=OMIT)
    finally:
        gi.feature_gate.audit = real
    assert seen == [], "feature_gate.audit was called with an unvalidated argument set"
    assert rep["gate_invoked"] is False
    assert "gate_not_invoked" in kinds(rep)


def test_guarded_fit_runs_the_fit_only_after_the_receipt_is_on_disk():
    observed = {}

    def fit(record, bound):
        observed["receipt_exists_at_fit_time"] = Path(record["receipt_path"]).exists()
        observed["bound"] = bound
        return "fitted"

    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "gate" / "fold_2022.json"
        rep, result = gi.guarded_fit(fit, CASE.df, CASE.names, experiment=EXPERIMENT, arm=ARM,
                                     fold=FOLD, receipt_path=p, offset=CASE.offset,
                                     target=CASE.target, outcome_mask=CASE.outcome_mask,
                                     test_df=CASE.test_df, raw_df=CASE.df,
                                     transformation=NO_TRANSFORMATION)
        assert result == "fitted"
        assert observed["receipt_exists_at_fit_time"] is True
        assert rep["receipt_written"] is True
        on_disk = json.loads(p.read_text(encoding="utf-8"))
        assert on_disk["binding"]["binding_digest"] == rep["binding"]["binding_digest"]
    assert set(observed["bound"]) == set(gi.REQUIRED_ARGUMENTS)


def test_guarded_fit_hands_back_the_realigned_objects_so_the_caller_fits_what_was_audited():
    observed = {}
    with tempfile.TemporaryDirectory() as d:
        gi.guarded_fit(lambda rec, bound: observed.update(bound),
                       CASE.df, CASE.names, experiment=EXPERIMENT, arm=ARM, fold=FOLD,
                       receipt_path=Path(d) / "r.json",
                       offset=CASE.offset.iloc[::-1],
                       align={"offset": "reindex_to_design_index"},
                       target=CASE.target, outcome_mask=CASE.outcome_mask,
                       test_df=CASE.test_df, raw_df=CASE.df,
                       transformation=NO_TRANSFORMATION)
    assert list(observed["offset"].index) == list(CASE.df.index)
    assert gi.value_digest(observed["offset"]) == gi.value_digest(CASE.offset)


def test_train_test_schema_drift_blocks_before_the_gate_call():
    rep = audit(test_df=CASE.test_df.drop(columns=[CASE.names[0]]))
    assert "train_test_schema_mismatch" in blocking_kinds(rep)
    assert rep["gate_invoked"] is False
    f = [x for x in rep["blocking"] if x["kind"] == "train_test_schema_mismatch"][0]
    assert f["missing_in_test"] == [CASE.names[0]]


# --------------------------------------------------------------------------------------------
# 5. the receipt: writable, and bound to its inputs
# --------------------------------------------------------------------------------------------

def test_an_unwritable_receipt_path_blocks():
    with tempfile.TemporaryDirectory() as d:
        blocker = Path(d) / "not_a_directory.txt"
        blocker.write_text("this is a file, not a directory", encoding="utf-8")
        rep = audit(receipt_path=blocker / "receipt.json")
    assert "receipt_unwritable" in blocking_kinds(rep)
    assert rep["passed"] is False
    assert rep["receipt_written"] is False


def test_guarded_fit_will_not_fit_when_the_receipt_cannot_be_written():
    calls = []
    with tempfile.TemporaryDirectory() as d:
        blocker = Path(d) / "not_a_directory.txt"
        blocker.write_text("x", encoding="utf-8")
        try:
            gi.guarded_fit(lambda rec, bound: calls.append("fitted"),
                           CASE.df, CASE.names, experiment=EXPERIMENT, arm=ARM, fold=FOLD,
                           receipt_path=blocker / "receipt.json", offset=CASE.offset,
                           target=CASE.target, outcome_mask=CASE.outcome_mask,
                           test_df=CASE.test_df)
        except gi.GateInvocationFailure as e:
            assert "receipt_unwritable" in str(e)
        else:
            raise AssertionError("guarded_fit fitted without an archived receipt")
    assert calls == []


def test_guarded_fit_will_not_fit_without_a_declared_receipt_path():
    calls = []
    try:
        gi.guarded_fit(lambda rec, bound: calls.append("fitted"), CASE.df, CASE.names,
                       experiment=EXPERIMENT, arm=ARM, fold=FOLD, receipt_path=None,
                       offset=CASE.offset, target=CASE.target,
                       outcome_mask=CASE.outcome_mask, test_df=CASE.test_df)
    except gi.GateInvocationFailure as e:
        assert "receipt_not_declared" in str(e)
    else:
        raise AssertionError("guarded_fit fitted with no receipt declared at all")
    assert calls == []


def test_a_receipt_verifies_against_the_inputs_it_was_written_for():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "r.json"
        audit(receipt_path=p, raise_on_block=True)
        stored = json.loads(p.read_text(encoding="utf-8"))
    v = gi.verify_receipt(stored, CASE.df, CASE.names, experiment=EXPERIMENT, arm=ARM,
                          fold=FOLD, offset=CASE.offset, target=CASE.target,
                          outcome_mask=CASE.outcome_mask, test_df=CASE.test_df,
                          raw_df=CASE.df, transformation=NO_TRANSFORMATION)
    assert v["passed"] is True
    assert v["binding_matches"] is True
    assert "receipt_binding_verified" in kinds(v)


def test_a_receipt_cannot_be_reused_for_a_different_design():
    rec = audit(raise_on_block=True)
    other = make_case(seed=99, prefix="qq")
    v = gi.verify_receipt(rec, other.df, other.names, experiment=EXPERIMENT, arm=ARM, fold=FOLD,
                          offset=other.offset, target=other.target,
                          outcome_mask=other.outcome_mask, test_df=other.test_df,
                          raw_df=other.df, transformation=NO_TRANSFORMATION,
                          raise_on_block=False)
    assert "receipt_reuse_detected" in blocking_kinds(v)
    assert v["binding_matches"] is False
    f = [x for x in v["blocking"] if x["kind"] == "receipt_reuse_detected"][0]
    assert "design_row_identity_digest" in f["diverging_fields"]


def test_a_receipt_cannot_be_reused_for_a_different_target_alone():
    rec = audit(raise_on_block=True)
    swapped = pd.Series(CASE.target.to_numpy()[::-1], index=CASE.df.index)
    v = gi.verify_receipt(rec, CASE.df, CASE.names, experiment=EXPERIMENT, arm=ARM, fold=FOLD,
                          offset=CASE.offset, target=swapped,
                          outcome_mask=CASE.outcome_mask, test_df=CASE.test_df,
                          raw_df=CASE.df, transformation=NO_TRANSFORMATION,
                          raise_on_block=False)
    assert "receipt_reuse_detected" in blocking_kinds(v)
    assert "target_value_digest" in [f for f in v["blocking"]
                                     if f["kind"] == "receipt_reuse_detected"][0][
        "diverging_fields"]


def test_a_receipt_cannot_be_reused_for_a_different_fold_or_arm():
    rec = audit(raise_on_block=True)
    for over in ({"fold": "2023"}, {"arm": "B"}, {"experiment": "something_else"}):
        kw = dict(experiment=EXPERIMENT, arm=ARM, fold=FOLD)
        kw.update(over)
        v = gi.verify_receipt(rec, CASE.df, CASE.names, offset=CASE.offset, target=CASE.target,
                              outcome_mask=CASE.outcome_mask, test_df=CASE.test_df,
                              raw_df=CASE.df, transformation=NO_TRANSFORMATION,
                              raise_on_block=False, **kw)
        assert "receipt_reuse_detected" in blocking_kinds(v), over


def test_receipt_reuse_is_non_adjudicable():
    assert "receipt_reuse_detected" in gi.NON_ADJUDICABLE
    assert "receipt_unwritable" in gi.NON_ADJUDICABLE


def test_the_binding_pins_the_gate_source_hash_and_the_caller_source_hash():
    rec = audit(raise_on_block=True)
    f = rec["binding"]["fields"]
    assert f["gate_source_sha256"] == rec["gate_module"]["source_sha256"]
    assert f["caller_source_sha256"] == rec["caller"]["source_sha256"]
    # a receipt whose gate hash differs is bound to a different implementation
    tampered = json.loads(json.dumps(rec))
    tampered["binding"]["fields"]["gate_source_sha256"] = "0" * 64
    v = gi.verify_receipt(tampered, CASE.df, CASE.names, experiment=EXPERIMENT, arm=ARM,
                          fold=FOLD, offset=CASE.offset, target=CASE.target,
                          outcome_mask=CASE.outcome_mask, test_df=CASE.test_df,
                          raw_df=CASE.df, transformation=NO_TRANSFORMATION,
                          raise_on_block=False)
    assert "receipt_reuse_detected" in blocking_kinds(v)


# --------------------------------------------------------------------------------------------
# 6. per fold and on the final assembled design -- the ws3 shape
# --------------------------------------------------------------------------------------------

FOLD_IDS = ("2021", "2022", "2023", "2024")


def make_chronological_case(degenerate_fold: str | None = "2022", per_fold: int = 60,
                            seed: int = 5):
    """Folds that are healthy pooled, with one fold carrying a near-zero-variance column.

    Reproduces the ws3 shape from a seeded RNG: ``proj_off_poss_share`` has standard deviation
    ``7.80108356964482e-09`` inside one fold and ordinary variation everywhere else, so the
    pooled statistic is dominated by the healthy folds.
    """
    rng = np.random.default_rng(seed)
    frames, offs, tgts, masks = {}, {}, {}, {}
    for f in FOLD_IDS:
        idx = pd.Index([f"{f}-{i:04d}" for i in range(per_fold)], name="player_game_id")
        if f == degenerate_fold:
            z = rng.standard_normal(per_fold)
            z = (z - z.mean()) / z.std()
            poss = 0.42 + z * WS3_DEGENERATE_STD
        else:
            poss = rng.normal(0.42, 0.05, per_fold)
        frames[f] = pd.DataFrame({
            "proj_off_poss_share": poss,
            "trailing_turnover_rate": rng.normal(0.13, 0.03, per_fold),
            "opponent_pressure": rng.normal(0.0, 1.0, per_fold),
        }, index=idx)
        offs[f] = pd.Series(np.log(rng.gamma(6.0, 6.0, per_fold) + 5.0), index=idx)
        tgts[f] = pd.Series(rng.poisson(2.5, per_fold).astype(float), index=idx)
        masks[f] = pd.Series(rng.random(per_fold) < 0.7, index=idx)

    names = list(frames[FOLD_IDS[0]].columns)
    h_idx = pd.Index([f"holdout-{i:04d}" for i in range(50)], name="player_game_id")
    holdout = pd.DataFrame({c: rng.normal(0.0, 1.0, 50) for c in names}, index=h_idx)

    folds = []
    for i, f in enumerate(FOLD_IDS):
        nxt = frames[FOLD_IDS[i + 1]] if i + 1 < len(FOLD_IDS) else holdout
        folds.append(gi.FoldInvocation(fold=f, df=frames[f], names=names, offset=offs[f],
                                       target=tgts[f], outcome_mask=masks[f], test_df=nxt,
                                       raw_df=frames[f], transformation=NO_TRANSFORMATION))
    pooled = pd.concat([frames[f] for f in FOLD_IDS])
    final = gi.FoldInvocation(fold="final_design", df=pooled, names=names,
                              offset=pd.concat([offs[f] for f in FOLD_IDS]),
                              target=pd.concat([tgts[f] for f in FOLD_IDS]),
                              outcome_mask=pd.concat([masks[f] for f in FOLD_IDS]),
                              test_df=holdout,
                              raw_df=pooled, transformation=NO_TRANSFORMATION)
    return folds, final, pooled, names


def test_ws3_shape_the_pooled_design_passes_while_one_fold_blocks():
    folds, final, pooled, names = make_chronological_case()
    rep = gi.audit_run(run_id="ws3_shape_synthetic", experiment=EXPERIMENT, arm=ARM,
                       folds=folds, final_design=final, expected_folds=FOLD_IDS,
                       raise_on_block=False)
    assert rep["n_folds"] == 4
    assert rep["final_design"]["passed"] is True, rep["final_design"]["blocking"]
    assert rep["final_design"]["gate"]["findings"] == []
    assert rep["folds_failed"] == ["2022"]
    bad = rep["folds"]["2022"]
    assert bad["passed"] is False
    assert "impossible_scaling" in {f["kind"] for f in bad["gate"]["blocking"]}
    scaling = [f for f in bad["gate"]["blocking"] if f["kind"] == "impossible_scaling"][0]
    assert scaling["feature"] == "proj_off_poss_share"
    assert scaling["std"] < 1e-8
    assert abs(scaling["std"] - WS3_DEGENERATE_STD) < 1e-16
    # the pooled statistic is healthy for the same column
    assert pooled["proj_off_poss_share"].std() > 1e-3
    for other in ("2021", "2023", "2024"):
        assert rep["folds"][other]["passed"] is True, rep["folds"][other]["blocking"]
    assert "pooled_healthy_fold_degenerate" in kinds(rep)
    assert "fold_invocation_failed" in blocking_kinds(rep)
    assert rep["passed"] is False


def test_a_run_with_a_degenerate_fold_raises_by_default():
    folds, final, _, _ = make_chronological_case()
    try:
        gi.audit_run(run_id="ws3_shape_synthetic", experiment=EXPERIMENT, arm=ARM,
                     folds=folds, final_design=final)
    except gi.GateInvocationFailure as e:
        assert "fold_invocation_failed" in str(e)
    else:
        raise AssertionError("audit_run did not raise on a degenerate fold")


def test_absence_of_a_per_fold_record_is_itself_a_failure():
    _, final, _, _ = make_chronological_case()
    rep = gi.audit_run(run_id="pooled_only", experiment=EXPERIMENT, arm=ARM, folds=[],
                       final_design=final, raise_on_block=False)
    assert "no_per_fold_record" in blocking_kinds(rep)
    assert rep["passed"] is False
    assert rep["final_design"]["passed"] is True     # the pooled audit passed, and does not count
    assert "no_per_fold_record" in gi.NON_ADJUDICABLE


def test_absence_of_a_final_design_record_is_a_failure():
    folds, _, _, _ = make_chronological_case(degenerate_fold=None)
    rep = gi.audit_run(run_id="folds_only", experiment=EXPERIMENT, arm=ARM, folds=folds,
                       final_design=None, raise_on_block=False)
    assert "no_final_design_record" in blocking_kinds(rep)


def test_a_healthy_run_passes_every_fold_and_the_final_design():
    folds, final, _, _ = make_chronological_case(degenerate_fold=None)
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "GATE_INVOCATION_RECEIPT.json"
        rep = gi.audit_run(run_id="healthy", experiment=EXPERIMENT, arm=ARM, folds=folds,
                           final_design=final, expected_folds=FOLD_IDS, receipt_path=p)
        assert rep["passed"] is True, rep["blocking"]
        stored = json.loads(p.read_text(encoding="utf-8"))
    assert stored["schema"] == gi.RECEIPT_SCHEMA
    assert set(stored["folds"]) == set(FOLD_IDS)
    assert stored["final_design"]["identity"]["scope"] == "final_design"
    for fid in FOLD_IDS:
        rec = stored["folds"][fid]
        assert rec["identity"]["fold"] == fid
        assert rec["gate_invoked"] is True
        assert rec["gate_module"]["source_sha256"] == stored["gate_module"]["source_sha256"]
        for name in gi.REQUIRED_ARGUMENTS:
            assert rec["arguments"][name]["value_digest"], (fid, name)
    # each fold is bound to its OWN inputs
    digests = [stored["folds"][f]["binding"]["binding_digest"] for f in FOLD_IDS]
    assert len(set(digests)) == len(digests)


def test_a_declared_fold_that_was_never_audited_is_a_failure():
    folds, final, _, _ = make_chronological_case(degenerate_fold=None)
    rep = gi.audit_run(run_id="missing_fold", experiment=EXPERIMENT, arm=ARM, folds=folds[:3],
                       final_design=final, expected_folds=FOLD_IDS, raise_on_block=False)
    assert "fold_set_mismatch" in blocking_kinds(rep)
    f = [x for x in rep["blocking"] if x["kind"] == "fold_set_mismatch"][0]
    assert f["missing"] == ["2024"]


def test_a_duplicate_fold_id_blocks():
    folds, final, _, _ = make_chronological_case(degenerate_fold=None)
    rep = gi.audit_run(run_id="dupe", experiment=EXPERIMENT, arm=ARM,
                       folds=list(folds) + [folds[0]], final_design=final,
                       raise_on_block=False)
    assert "duplicate_fold_id" in blocking_kinds(rep)


def test_a_run_receipt_cannot_be_reused_for_different_folds():
    folds, final, _, _ = make_chronological_case(degenerate_fold=None)
    rep = gi.audit_run(run_id="healthy", experiment=EXPERIMENT, arm=ARM, folds=folds,
                       final_design=final)
    ok = gi.verify_run_receipt(rep, run_id="healthy", experiment=EXPERIMENT, arm=ARM,
                               folds=folds, final_design=final)
    assert ok["passed"] is True
    bad = gi.verify_run_receipt(rep, run_id="healthy", experiment=EXPERIMENT, arm=ARM,
                                folds=folds[:2], final_design=final, raise_on_block=False)
    assert "receipt_reuse_detected" in blocking_kinds(bad)


# --------------------------------------------------------------------------------------------
# 7. identity, declarations and adjudication
# --------------------------------------------------------------------------------------------

def test_an_unnamed_experiment_arm_or_fold_blocks():
    for over in ({"experiment": ""}, {"arm": ""}, {"fold": ""}):
        rep = audit(**over)
        assert "identity_unspecified" in blocking_kinds(rep), over
        assert rep["gate_invoked"] is False


def test_identity_is_non_adjudicable():
    rep = audit(experiment="", adjudications={"identity_unspecified": "we know who we are"})
    assert "identity_unspecified" in blocking_kinds(rep)


def test_a_declared_inapplicable_argument_passes_but_the_record_is_incomplete():
    rep = audit(test_df=OMIT,
                not_applicable={"test_df": "feature selection stage; no held-out frame exists "
                                           "yet and none will be scored"})
    assert rep["passed"] is True, rep["blocking"]
    assert rep["complete"] is False
    assert rep["checks_not_run"] == ["schema_mismatch"]
    assert "audit_incomplete" in kinds(rep)
    assert "argument_declared_not_applicable" in kinds(rep)
    assert rep["arguments"]["test_df"]["declared_not_applicable"].startswith("feature selection")


def test_declaring_an_argument_inapplicable_without_a_reason_blocks():
    rep = audit(test_df=OMIT, not_applicable={"test_df": ""})
    assert "not_applicable_without_reason" in blocking_kinds(rep)


def test_declaring_an_argument_inapplicable_and_supplying_it_blocks():
    rep = audit(not_applicable={"test_df": "it is not applicable"})
    assert "not_applicable_contradicted" in blocking_kinds(rep)


def test_declaring_an_unknown_argument_blocks():
    rep = audit(not_applicable={"offsett": "typo"})
    assert "unknown_argument_declared" in blocking_kinds(rep)


def test_an_adjudicable_finding_can_be_adjudicated_with_a_reason_and_is_recorded_forever():
    rep = audit(offset=CASE.offset.to_numpy(),
                adjudications={"offset:argument_row_identity_absent":
                               "producer emits a positional ndarray; row identity is proven "
                               "upstream by the exposure bridge receipt"})
    assert rep["passed"] is True, rep["blocking"]
    assert len(rep["adjudications_applied"]) == 1
    a = rep["adjudications_applied"][0]
    assert a["kind"] == "argument_row_identity_absent"
    assert a["argument"] == "offset"
    assert "exposure bridge" in a["adjudication_reason"]


def test_an_adjudication_without_a_reason_blocks():
    rep = audit(adjudications={"offset:argument_row_identity_absent": ""})
    assert "adjudication_without_reason" in blocking_kinds(rep)


def test_omission_cannot_be_adjudicated_away():
    rep = audit(target=OMIT,
                adjudications={"target:argument_omitted": "we do not have the target here"})
    assert "argument_omitted" in blocking_kinds(rep)
    assert rep["passed"] is False


def test_misalignment_and_universe_mismatch_cannot_be_adjudicated_away():
    for name, mode, kind in (("offset", "misaligned", "argument_misaligned"),
                             ("target", "different_universe", "argument_universe_mismatch")):
        rep = audit(**{name: variant(CASE, name, mode)},
                    adjudications={f"{name}:{kind}": "trust me"})
        assert kind in blocking_kinds(rep), (name, mode)


def test_a_stale_adjudication_is_reported_but_does_not_block():
    rep = audit(adjudications={"offset:argument_constant": "left over from an earlier arm"})
    assert rep["passed"] is True, rep["blocking"]
    assert "adjudication_unused" in kinds(rep)


# --------------------------------------------------------------------------------------------
# 8. the module's own declarations
# --------------------------------------------------------------------------------------------

def test_every_argument_enables_a_real_feature_gate_finding_kind():
    for name, enabled in gi.ARGUMENT_ENABLES.items():
        assert name in gi.REQUIRED_ARGUMENTS
        for k in enabled:
            assert k in feature_gate.BLOCKING, (name, k)


def test_non_adjudicable_is_a_subset_of_blocking_and_informational_is_disjoint_from_it():
    assert gi.NON_ADJUDICABLE <= gi.BLOCKING
    assert not (gi.INFORMATIONAL & gi.BLOCKING)


def test_the_gate_and_the_caller_are_both_identified_by_source_hash():
    ident = gi.gate_module_identity()
    assert ident["source_sha256"] and len(ident["source_sha256"]) == 64
    assert ident["RANK_TOL"] == feature_gate.RANK_TOL
    assert ident["COND_MAX"] == feature_gate.COND_MAX
    assert set(ident["blocking_kinds"]) == set(feature_gate.BLOCKING)
    caller = gi.caller_identity()
    assert caller["source_path"].endswith("test_gate_invocation.py")
    assert caller["resolution"] == "stack"


def test_a_failing_gate_record_is_recovered_in_full_and_never_reports_passed_true():
    """feature_gate raises on block, carrying only six findings; the record must survive intact."""
    df = CASE.df.copy()
    df["duplicate_of_pressure"] = df["opponent_pressure"]
    names = list(df.columns)
    rep = gi.audit_fold(df, names, experiment=EXPERIMENT, arm=ARM, fold=FOLD,
                        offset=CASE.offset, target=CASE.target,
                        outcome_mask=CASE.outcome_mask,
                        test_df=CASE.test_df.assign(duplicate_of_pressure=0.0),
                        raw_df=df, transformation=NO_TRANSFORMATION,
                        raise_on_block=False)
    assert rep["gate_invoked"] is True
    assert rep["gate"]["raised"] is True
    assert rep["gate"]["passed"] is False
    assert "exact_duplicate" in {f["kind"] for f in rep["gate"]["blocking"]}
    assert len(rep["gate"]["findings"]) >= len(rep["gate"]["blocking"])
    assert "gate_blocked" in blocking_kinds(rep)
    assert rep["passed"] is False


def test_per_feature_gate_adjudication_is_passed_through_and_recorded():
    """The gate's own adjudication is keyed by FEATURE, and design-level findings key on
    ``__design__``. Adjudicating only the duplicated column leaves ``rank_deficient`` blocking,
    which is feature_gate's behaviour and is deliberately not smoothed over here."""
    df = CASE.df.copy()
    df["duplicate_of_pressure"] = df["opponent_pressure"]
    names = list(df.columns)
    test = CASE.test_df.assign(duplicate_of_pressure=0.0)
    partial = gi.audit_fold(df, names, experiment=EXPERIMENT, arm=ARM, fold=FOLD,
                            offset=CASE.offset, target=CASE.target,
                            outcome_mask=CASE.outcome_mask, test_df=test,
                            raw_df=df, transformation=NO_TRANSFORMATION,
                            gate_adjudicated={"opponent_pressure": True,
                                              "duplicate_of_pressure": True},
                            raise_on_block=False)
    assert partial["gate"]["passed"] is False
    assert {f["kind"] for f in partial["gate"]["blocking"]} == {"rank_deficient"}

    full = gi.audit_fold(df, names, experiment=EXPERIMENT, arm=ARM, fold=FOLD,
                         offset=CASE.offset, target=CASE.target,
                         outcome_mask=CASE.outcome_mask, test_df=test,
                         raw_df=df, transformation=NO_TRANSFORMATION,
                         gate_adjudicated={"opponent_pressure": True,
                                           "duplicate_of_pressure": True,
                                           "__design__": True},
                         raise_on_block=False)
    assert full["gate_adjudicated"] == {"opponent_pressure": True,
                                        "duplicate_of_pressure": True, "__design__": True}
    assert full["gate"]["passed"] is True
    assert full["passed"] is True, full["blocking"]


# --------------------------------------------------------------------------------------------
# 9. THE DUAL FRAME — contract §8a, the ws2 class
#
# ws2's `build_constructions()` imputed to 0.0 BEFORE the gate was called, so the gate saw a fully
# populated design with no missingness and passed every fold. The null mask survived as a value.
# Everything below is synthetic and seeded; **no ws2 artifact is read and nothing is scored**. The
# shape is rebuilt to the recorded magnitude so the test documents the defect rather than citing
# it from memory.
# --------------------------------------------------------------------------------------------

WS2_N_APPEARERS = 27351
WS2_N_NON_APPEARERS = 8278
WS2_N_ROWS = WS2_N_APPEARERS + WS2_N_NON_APPEARERS                     # 35629
WS2_NON_ZERO = {"transfer_direct": 25522, "transfer_allocated": 25522,
                "transfer_role_sensitive": 9577}

#: filled in by the tests; printed by ``main`` so the assurance level each case reaches is part of
#: the run output rather than something a reader has to infer.
ASSURANCE_OBSERVED: dict = {}


def note_assurance(label: str, rep: dict) -> dict:
    ASSURANCE_OBSERVED[label] = (rep.get("assurance"), bool(rep.get("stage1_pass")))
    return rep


@dataclass
class DualCase:
    raw: pd.DataFrame
    transformed: pd.DataFrame
    names: list
    offset: pd.Series
    target: pd.Series
    outcome_mask: pd.Series
    test_df: pd.DataFrame
    transformation: dict


def make_ws2_case(seed: int = 2202) -> DualCase:
    """The ws2 shape at its recorded magnitude, from a seeded RNG.

    ``transfer_direct`` and ``transfer_allocated`` are null on EXACTLY the 8,278 non-appearers, so
    their null mask is an exact appearance indicator with zero off-diagonal. They are additionally
    zero on 1,829 appearers, which is what makes 25,522 the non-zero count rather than 27,351.
    ``transfer_role_sensitive`` is null on the non-appearers AND on 17,774 appearers, leaving
    9,577 non-zero — the weaker one-directional version of the same leak.
    """
    rng = np.random.default_rng(seed)
    n = WS2_N_ROWS
    idx = pd.Index([f"pg{i:06d}" for i in range(n)], name="player_game_id")
    appeared = np.zeros(n, dtype=bool)
    appeared[rng.permutation(n)[:WS2_N_APPEARERS]] = True
    app_pos = np.flatnonzero(appeared)

    def transfer(n_non_zero: int, zero_the_rest: bool, mu: float, sd: float):
        col = np.full(n, np.nan)
        pick = rng.permutation(app_pos)
        col[pick[:n_non_zero]] = np.abs(rng.normal(mu, sd, n_non_zero)) + 0.05
        if zero_the_rest:                       # explicit zeros, NOT nulls
            col[pick[n_non_zero:]] = 0.0
        return col

    raw = pd.DataFrame({
        "transfer_direct": transfer(WS2_NON_ZERO["transfer_direct"], True, 1.0, 0.6),
        "transfer_allocated": transfer(WS2_NON_ZERO["transfer_allocated"], True, 0.8, 0.5),
        "transfer_role_sensitive": transfer(WS2_NON_ZERO["transfer_role_sensitive"],
                                            False, 1.2, 0.7),
        "trailing_minutes_share": rng.normal(0.55, 0.10, n),
    }, index=idx)
    names = list(raw.columns)
    transformed = raw.fillna(0.0)

    offset = pd.Series(np.log(rng.gamma(6.0, 4.0, n) + 4.0), index=idx, name="log_proj_minutes")
    y = np.where(appeared, rng.poisson(2.2, n).astype(float), 0.0)
    target = pd.Series(y, index=idx, name="turnovers")
    mask = pd.Series(appeared, index=idx, name="did_appear")
    t_idx = pd.Index([f"ho{i:06d}" for i in range(600)], name="player_game_id")
    test_df = pd.DataFrame({c: rng.normal(0.5, 0.3, 600) for c in names}, index=t_idx)

    transformation = {
        "kind": "imputation",
        "description": "build_constructions() fills the transfer columns to 0.0 before the design "
                       "is handed to the fitter",
        "operations": [{"columns": ["transfer_direct", "transfer_allocated",
                                    "transfer_role_sensitive"],
                        "method": "fill_constant", "value": 0.0,
                        "reason": "a missing transfer row is treated as no transfer",
                        "cutoff_valid": True}],
    }
    return DualCase(raw, transformed, names, offset, target, mask, test_df, transformation)


WS2 = make_ws2_case()


def ws2_audit(**over) -> dict:
    """The ws2 invocation with a fully HONEST declaration. It still blocks, which is the point:
    the defect is not that the caller lied about the imputation, it is that the null mask being
    imputed encoded the outcome."""
    kw = dict(experiment="ws2_synthetic", arm="A", fold="2024",
              offset=WS2.offset, target=WS2.target, outcome_mask=WS2.outcome_mask,
              test_df=WS2.test_df, raw_df=WS2.raw, transformation=WS2.transformation,
              fitted_matrix=WS2.transformed[WS2.names], raise_on_block=False)
    kw.update(over)
    for k in [k for k, v in kw.items() if v is OMIT]:
        del kw[k]
    return gi.audit_fold(WS2.transformed, WS2.names, **kw)


# ---- 1. the raw missingness perfectly separates appearing from non-appearing candidates ------

def test_ws2_raw_missingness_perfectly_separates_appearers_from_non_appearers():
    assert len(WS2.raw) == WS2_N_ROWS == 35629
    assert int(WS2.outcome_mask.sum()) == WS2_N_APPEARERS == 27351
    assert int((~WS2.outcome_mask).sum()) == WS2_N_NON_APPEARERS == 8278
    om = WS2.outcome_mask.to_numpy()
    for c in ("transfer_direct", "transfer_allocated"):
        miss = WS2.raw[c].isna().to_numpy()
        assert int(miss.sum()) == WS2_N_NON_APPEARERS
        assert np.array_equal(miss, ~om), c            # an EXACT appearance indicator
    role = WS2.raw["transfer_role_sensitive"].isna().to_numpy()
    assert bool(role[~om].all())                       # null on every non-appearer
    assert int((~role).sum()) == WS2_NON_ZERO["transfer_role_sensitive"]
    # and after the fill, a non-zero value certifies appearance
    for c, n_nz in WS2_NON_ZERO.items():
        v = WS2.transformed[c].to_numpy()
        assert int((v != 0.0).sum()) == n_nz, c
        assert bool((v[~om] == 0.0).all()), c
        assert int((v[om] != 0.0).sum()) == n_nz, c


# ---- 2. zero-imputation removes all nulls ---------------------------------------------------

def test_ws2_zero_imputation_removes_every_null():
    assert int(WS2.raw[WS2.names].isna().to_numpy().sum()) > 0
    assert int(WS2.transformed[WS2.names].isna().to_numpy().sum()) == 0


# ---- 3. transformed-only auditing would PASS -- why the old wrapper was blind ----------------

def test_ws2_transformed_only_auditing_passes_which_is_why_the_old_wrapper_was_blind():
    """The gate is not wrong here and neither was the argument layer. Both are complete on what
    they can see, and what they can see is a frame with no missingness."""
    direct = feature_gate.audit(WS2.transformed, WS2.names, offset=WS2.offset.to_numpy(),
                                target=WS2.target.to_numpy(),
                                outcome_mask=WS2.outcome_mask.to_numpy(), test_df=WS2.test_df)
    assert direct["passed"] is True, direct["findings"]
    assert direct["blocking"] == []
    assert "missingness_encodes_outcome" not in {f["kind"] for f in direct["findings"]}
    assert "missingness_informative" not in {f["kind"] for f in direct["findings"]}
    # every required argument is supplied, valid, aligned and non-placeholder, so the
    # argument-omission layer -- the whole of this module before §8a -- reports nothing at all
    args = gi.validate_arguments(WS2.transformed, WS2.names, experiment="ws2_synthetic", arm="A",
                                 fold="2024", offset=WS2.offset, target=WS2.target,
                                 outcome_mask=WS2.outcome_mask, test_df=WS2.test_df,
                                 raise_on_block=False)
    assert args["passed"] is True, args["blocking"]
    assert args["blocking"] == []
    assert args["complete"] is True


# ---- 4. dual-frame auditing BLOCKS, before the gate and therefore before the fit -------------

def test_ws2_dual_frame_auditing_blocks_before_the_model():
    rep = note_assurance("ws2_dual_frame", ws2_audit())
    assert rep["passed"] is False
    assert rep["gate_invoked"] is False, "the fitted design was audited; the failure did not " \
                                         "precede the model"
    assert rep["stage_failed"] == "dual_frame"
    assert "gate_not_invoked" in kinds(rep)
    assert rep["assurance"] == "FAILED"
    assert rep["stage1_pass"] is False
    b = blocking_kinds(rep)
    assert "missingness_mask_converted_to_values" in b
    assert "value_pattern_encodes_outcome" in b
    assert "raw_frame_gate_blocked" in b
    # the RAW audit is where feature_gate fired, on the frame the fitter never saw
    raw_audit = rep["dual_frame"]["raw_audit"]
    assert rep["dual_frame"]["raw_gate_invoked"] is True
    assert raw_audit["passed"] is False
    assert "missingness_encodes_outcome" in {f["kind"] for f in raw_audit["findings"]}


def test_ws2_the_conversion_finding_names_the_columns_and_carries_the_off_diagonal():
    rep = ws2_audit()
    conv = [f for f in rep["blocking"] if f["kind"] == "missingness_mask_converted_to_values"]
    assert {f["feature"] for f in conv} == {"transfer_direct", "transfer_allocated"}
    for f in conv:
        assert f["n_missing_raw"] == WS2_N_NON_APPEARERS
        assert f["n_missing_transformed"] == 0
        assert f["n_nulls_filled"] == WS2_N_NON_APPEARERS
        assert f["off_diagonal_rows"] == 0
        assert "sha256=" in f["raw_missing_mask_digest"]
    assert "missingness_mask_converted_to_values" in gi.NON_ADJUDICABLE


def test_ws2_the_value_pattern_check_sees_the_leak_in_the_transformed_frame_alone():
    rep = ws2_audit()
    vp = [f for f in rep["blocking"] if f["kind"] == "value_pattern_encodes_outcome"]
    assert {f["feature"] for f in vp} == set(WS2_NON_ZERO)
    for f in vp:
        assert f["value"] == 0.0
        assert f["side_carrying_value"] == "outcome_negative"
        assert f["n_rows_on_that_side"] == WS2_N_NON_APPEARERS
        assert f["n_other_side_without_value"] == WS2_NON_ZERO[f["feature"]]


def test_ws2_guarded_fit_never_reaches_the_model():
    calls = []
    with tempfile.TemporaryDirectory() as d:
        try:
            gi.guarded_fit(lambda rec, bound: calls.append("fitted"),
                           WS2.transformed, WS2.names, experiment="ws2_synthetic", arm="A",
                           fold="2024", receipt_path=Path(d) / "ws2.json",
                           offset=WS2.offset, target=WS2.target,
                           outcome_mask=WS2.outcome_mask, test_df=WS2.test_df,
                           raw_df=WS2.raw, transformation=WS2.transformation,
                           fitted_matrix=WS2.transformed[WS2.names])
        except gi.GateInvocationFailure:
            pass
        else:
            raise AssertionError("guarded_fit fitted the ws2 design")
    assert calls == []


def test_ws2_an_honest_adjudication_of_the_value_pattern_cannot_rescue_the_conversion():
    """The value pattern is a judgement about data and is adjudicable. The conversion of an
    outcome-encoding raw null mask into values is not, so adjudicating the former alone leaves
    the invocation blocked — which is the correct precedence."""
    rep = ws2_audit(adjudications={
        "value_pattern_encodes_outcome": "transfers are genuinely zero for non-participants"})
    assert rep["passed"] is False
    assert "missingness_mask_converted_to_values" in blocking_kinds(rep)
    assert "value_pattern_encodes_outcome" not in blocking_kinds(rep)


# --------------------------------------------------------------------------------------------
# 10. a legitimate, cutoff-valid imputation PASSES -- specification §5
# --------------------------------------------------------------------------------------------

def make_legit_case(n: int = 1200, seed: int = 77) -> DualCase:
    """Missingness that is available at the cutoff and unrelated to the target game.

    ``trailing_rest_days`` is null for a player's first appearance of the season. That fact is
    known before tip-off, it is not produced by the target game, and it is not associated with
    whether the player appears in it. The fill constant is the MEDIAN OF THE TRAINING ROWS ONLY,
    it is frozen, and the same frozen constant is applied to the held-out frame.
    """
    rng = np.random.default_rng(seed)
    idx = pd.Index([f"lg{i:05d}" for i in range(n)], name="player_game_id")
    appeared = rng.random(n) < 0.72
    rest = rng.integers(0, 7, n).astype(float)
    missing = rng.random(n) < 0.15                       # independent of `appeared`
    rest[missing] = np.nan
    raw = pd.DataFrame({"trailing_rest_days": rest,
                        "trailing_turnover_rate": rng.normal(0.13, 0.03, n),
                        "opponent_pressure": rng.normal(0.0, 1.0, n)}, index=idx)
    names = list(raw.columns)

    fill = float(np.nanmedian(raw["trailing_rest_days"].to_numpy()))     # fitted on TRAINING rows
    transformed = raw.copy()
    transformed["trailing_rest_days"] = raw["trailing_rest_days"].fillna(fill)

    t_idx = pd.Index([f"ho{i:05d}" for i in range(300)], name="player_game_id")
    t_rest = rng.integers(0, 7, 300).astype(float)
    t_rest[rng.random(300) < 0.15] = np.nan
    test_df = pd.DataFrame({"trailing_rest_days": t_rest,
                            "trailing_turnover_rate": rng.normal(0.13, 0.03, 300),
                            "opponent_pressure": rng.normal(0.0, 1.0, 300)}, index=t_idx)
    test_df["trailing_rest_days"] = test_df["trailing_rest_days"].fillna(fill)   # SAME constant

    offset = pd.Series(np.log(rng.gamma(6.0, 5.0, n) + 5.0), index=idx)
    target = pd.Series(rng.poisson(2.4, n).astype(float), index=idx)
    mask = pd.Series(appeared, index=idx)

    transformation = {
        "kind": "imputation",
        "description": "trailing_rest_days is null on a player's first appearance of the season; "
                       "the null is a data-availability fact known at the prediction cutoff and "
                       "is not produced by the target game",
        "operations": [{
            "columns": ["trailing_rest_days"],
            "method": "fill_constant",
            "value": fill,
            "reason": "median rest of the chronological training rows, frozen and reapplied "
                      "unchanged to the held-out frame",
            "cutoff_valid": True,
            "available_at_cutoff": True,
            "frozen_parameters": {"statistic": "median", "value": fill},
            "fitted_on_row_universe_digest": gi.index_digest(idx, sort=True,
                                                             label="design_index_membership"),
            "applied_to_test_frame": True,
        }],
    }
    return DualCase(raw, transformed, names, offset, target, mask, test_df, transformation)


LEGIT = make_legit_case()
LEGIT_FILL = float(LEGIT.transformation["operations"][0]["value"])


def legit_audit(**over) -> dict:
    kw = dict(experiment="legit_imputation", arm="A", fold="2024",
              offset=LEGIT.offset, target=LEGIT.target, outcome_mask=LEGIT.outcome_mask,
              test_df=LEGIT.test_df, raw_df=LEGIT.raw, transformation=LEGIT.transformation,
              fitted_matrix=LEGIT.transformed[LEGIT.names], raise_on_block=False)
    kw.update(over)
    for k in [k for k, v in kw.items() if v is OMIT]:
        del kw[k]
    return gi.audit_fold(LEGIT.transformed, LEGIT.names, **kw)


def test_a_legitimate_cutoff_valid_imputation_passes():
    rep = note_assurance("legitimate_imputation", legit_audit())
    assert rep["passed"] is True, rep["blocking"]
    assert rep["gate_invoked"] is True
    assert rep["gate"]["passed"] is True, rep["gate"]["findings"]
    assert rep["dual_frame"]["case"] == "transformation"
    assert rep["assurance"] == "RAW_PROVENANCE_ASSERTED"        # no producer provenance supplied
    assert rep["stage1_pass"] is False
    assert "raw_provenance_asserted_not_verified" in kinds(rep)


def test_the_legitimate_imputation_demonstrates_every_obligation_the_contract_names():
    rep = legit_audit()
    dual = rep["dual_frame"]
    op = dual["transformation"]["operations"][0]
    prof = dual["identity"]["raw_missingness"]["per_column"]["trailing_rest_days"]

    # 1. the missingness is available at the prediction cutoff, and says so
    assert op["cutoff_valid"] is True
    assert "prediction cutoff" in dual["transformation"]["description"]
    # 2. the raw null mask is NOT associated with appearance or with the target
    assert prof["n_missing"] > 0
    assert prof["is_exact_outcome_indicator"] is False
    assert prof["off_diagonal_rows"] > 0
    raw_kinds = {f["kind"] for f in dual["raw_audit"]["findings"]}
    assert raw_kinds == {"missingness_present"}
    assert dual["raw_audit"]["passed"] is True
    # 3. the rule was fitted only on the chronological training rows
    assert op["fitted_on_row_universe_digest"] == rep["design"]["design_row_membership_digest"]
    assert op["frozen_parameters"] == {"statistic": "median", "value": LEGIT_FILL}
    # 4. the same frozen rule was applied to the held-out fold
    assert op["applied_to_test_frame"] is True
    assert int(LEGIT.test_df["trailing_rest_days"].isna().sum()) == 0
    assert LEGIT_FILL in set(LEGIT.test_df["trailing_rest_days"].unique().tolist())
    # 5. the transformation is recorded, and bound
    assert rep["binding"]["fields"]["transformation_spec_digest"].startswith(
        "transformation:sha256=")
    assert rep["binding"]["fields"]["transformation_kind"] == "imputation"
    # 6. raw and transformed reconcile, row-wise and column-wise
    recon = dual["reconciliation"]
    assert recon["rows"] == "identical"
    assert recon["columns"] == "reconciled"
    assert recon["feature_order_reconciles"] is True
    assert recon["columns_changed"] == ["trailing_rest_days"]
    assert recon["undeclared_changed_columns"] == []
    # 7. the exact audited transformed matrix is the one fitted
    assert dual["fitted_matrix"]["declared"] is True
    assert dual["fitted_matrix"]["matches"] is True
    assert (dual["fitted_matrix"]["digest"]
            == gi.matrix_digest(LEGIT.transformed, LEGIT.names))
    # and the per-column RAW missingness masks are digested, as §8a requires
    assert all("sha256=" in v["missing_mask_digest"]
               for v in dual["identity"]["raw_missingness"]["per_column"].values())


def test_a_producer_backed_transformation_reaches_the_full_stage_one_pass():
    prov = {"producer_source_path": str(Path(__file__).resolve()),
            "producer_source_sha256": gi._sha256_file(Path(__file__).resolve()),
            "input_manifest": {str(Path(gi.__file__).resolve().parent / "feature_gate.py"): None},
            "feature_construction_receipt": str(Path(__file__).resolve()),
            "experiment": "legit_imputation", "arm": "A",
            "row_universe_digest": gi.index_digest(LEGIT.raw.index, sort=True,
                                                   label="raw_index_membership")}
    rep = note_assurance("producer_backed_transformation", legit_audit(provenance=prov))
    assert rep["passed"] is True, rep["blocking"]
    assert rep["assurance"] == "TRANSFORMATION_VERIFIED"
    assert rep["stage1_pass"] is True
    assert rep["dual_frame"]["provenance"]["verified"] is True
    assert rep["dual_frame"]["provenance"]["row_universe_digest_matches"] is True
    assert "raw_provenance_asserted_not_verified" not in kinds(rep)


def test_a_producer_backed_untransformed_design_reaches_identity_verified():
    prov = {"producer_source_path": str(Path(__file__).resolve()),
            "row_universe_digest": gi.index_digest(CASE.df.index, sort=True,
                                                   label="raw_index_membership")}
    rep = note_assurance("producer_backed_identity", audit(provenance=prov))
    assert rep["passed"] is True, rep["blocking"]
    assert rep["dual_frame"]["case"] == "identity"
    assert rep["assurance"] == "IDENTITY_VERIFIED"
    assert rep["stage1_pass"] is True


def test_a_caller_asserted_raw_frame_does_not_receive_producer_backed_assurance():
    asserted = note_assurance("caller_asserted_identity", audit())
    assert asserted["passed"] is True, asserted["blocking"]
    assert asserted["assurance"] == "RAW_PROVENANCE_ASSERTED"
    assert asserted["stage1_pass"] is False
    assert asserted["dual_frame"]["provenance"]["claimed"] is False
    assert "raw_provenance_asserted_not_verified" in kinds(asserted)
    # ...and the levels are the four the specification names, no more and no fewer
    assert gi.ASSURANCE_LEVELS == ("IDENTITY_VERIFIED", "TRANSFORMATION_VERIFIED",
                                   "RAW_PROVENANCE_ASSERTED", "FAILED")
    assert set(gi.STAGE1_PASS_LEVELS) == {"IDENTITY_VERIFIED", "TRANSFORMATION_VERIFIED"}


# --------------------------------------------------------------------------------------------
# 11. one test per required failure condition -- specification §4
# --------------------------------------------------------------------------------------------

def test_condition_1_only_the_transformed_frame_is_supplied():
    rep = note_assurance("only_transformed_frame", ws2_audit(raw_df=OMIT, transformation=None,
                                                             fitted_matrix=OMIT))
    assert "raw_frame_absent" in blocking_kinds(rep)
    assert "transformation_undeclared" in blocking_kinds(rep)
    assert rep["gate_invoked"] is False
    assert rep["passed"] is False
    assert rep["assurance"] == "FAILED"
    # withholding the raw frame does not hide the leak: the fitted values still separate the
    # outcome, which is why the requirement is unconditional rather than triggered by suspicion
    assert "value_pattern_encodes_outcome" in blocking_kinds(rep)
    assert "raw_frame_absent" in gi.NON_ADJUDICABLE


def test_condition_1_is_mandatory_even_for_a_design_with_no_missingness_at_all():
    """A clean, fully populated design with no separating value pattern still may not be fitted
    without its raw frame. This is the resolved rule: the requirement is unconditional, because a
    populated transformed frame cannot reveal that a raw frame was withheld."""
    rep = audit(raw_df=OMIT, transformation=None)
    assert int(CASE.df.isna().to_numpy().sum()) == 0
    assert "raw_frame_absent" in blocking_kinds(rep)
    assert "value_pattern_encodes_outcome" not in kinds(rep)   # nothing suspicious to see
    assert rep["gate_invoked"] is False
    assert rep["assurance"] == "FAILED"


def test_condition_2_kind_none_but_the_two_frames_differ():
    other = CASE.df.copy()
    other.iloc[0, 0] = other.iloc[0, 0] + 1.0
    rep = audit(raw_df=other)
    assert "declared_identity_contradicted" in blocking_kinds(rep)
    f = [x for x in rep["blocking"] if x["kind"] == "declared_identity_contradicted"][0]
    assert f["raw_frame_values_digest"] != f["audited_matrix_digest"]
    assert rep["gate_invoked"] is False
    assert "declared_identity_contradicted" in gi.NON_ADJUDICABLE


def test_condition_3_a_transformation_occurred_and_no_specification_is_provided():
    rep = legit_audit(transformation=None)
    assert "transformation_undeclared" in blocking_kinds(rep)
    assert rep["gate_invoked"] is False
    assert "transformation_undeclared" in gi.NON_ADJUDICABLE


def test_condition_3_a_malformed_specification_is_not_a_specification():
    for spec, field in (
            ({"kind": "imputation", "description": "d",
              "operations": [{"columns": ["trailing_rest_days"], "method": "fill_constant",
                              "reason": "r"}]}, "cutoff_valid"),
            ({"kind": "imputation", "description": "d",
              "operations": [{"columns": ["trailing_rest_days"], "method": "fill_constant",
                              "cutoff_valid": True}]}, "reason"),
            ({"kind": "not_a_kind", "description": "d", "operations": []}, "kind"),
            ({"kind": "imputation", "operations": []}, "description"),
            ("i filled some nulls", None)):
        rep = legit_audit(transformation=spec)
        assert "transformation_declaration_malformed" in blocking_kinds(rep), spec
        assert rep["gate_invoked"] is False
    # a declared column that is not a feature of this design is a typo, and is surfaced
    rep = legit_audit(transformation={
        **LEGIT.transformation,
        "operations": [{**LEGIT.transformation["operations"][0],
                        "columns": ["trailing_rest_dayz"]}]})
    assert "transformation_declaration_malformed" in blocking_kinds(rep)


def test_condition_4_an_outcome_encoding_raw_null_mask_filled_into_values():
    rep = ws2_audit()
    assert "missingness_mask_converted_to_values" in blocking_kinds(rep)
    assert rep["gate_invoked"] is False


def test_condition_5_the_audited_matrix_is_not_the_matrix_handed_to_the_fitter():
    standardised = LEGIT.transformed[LEGIT.names].copy()
    standardised = (standardised - standardised.mean()) / standardised.std()
    rep = legit_audit(fitted_matrix=standardised)
    assert "audited_matrix_is_not_the_fitted_matrix" in blocking_kinds(rep)
    f = [x for x in rep["blocking"]
         if x["kind"] == "audited_matrix_is_not_the_fitted_matrix"][0]
    assert f["audited_matrix_digest"] != f["fitted_matrix_digest"]
    assert rep["gate_invoked"] is False
    # a caller who transformed and did not declare the matrix at all is also blocked
    undeclared = legit_audit(fitted_matrix=OMIT)
    assert "fitted_matrix_undeclared" in blocking_kinds(undeclared)
    # ...and an ndarray of the audited values IS the audited matrix
    ok = legit_audit(fitted_matrix=LEGIT.transformed[LEGIT.names].to_numpy())
    assert ok["passed"] is True, ok["blocking"]
    assert ok["dual_frame"]["fitted_matrix"]["matches"] is True


def test_condition_6_row_universes_differ_without_an_authorised_row_operation():
    extra = LEGIT.raw.iloc[:5].rename(index=lambda s: "extra-" + str(s))
    wider = pd.concat([LEGIT.raw, extra])
    rep = legit_audit(raw_df=wider)
    assert "raw_transformed_row_identity_mismatch" in blocking_kinds(rep)
    f = [x for x in rep["blocking"]
         if x["kind"] == "raw_transformed_row_identity_mismatch"][0]
    assert f["relation"] == "subset"
    assert f["n_only_in_raw"] == 5
    assert rep["gate_invoked"] is False
    assert "raw_transformed_row_identity_mismatch" in gi.NON_ADJUDICABLE

    # declared explicitly, the same drop is allowed, recorded, and the raw audit runs on exactly
    # the rows that were fitted
    authorised = legit_audit(raw_df=wider, transformation={
        **LEGIT.transformation,
        "row_operations": [{"kind": "drop_rows", "cutoff_valid": True,
                            "reason": "five candidate rows were dropped before fitting because "
                                      "their exposure projection was unavailable"}]})
    assert authorised["passed"] is True, authorised["blocking"]
    assert authorised["dual_frame"]["reconciliation"]["rows"] == "authorised_subset"
    assert authorised["dual_frame"]["reconciliation"]["n_rows_dropped"] == 5
    assert "authorised_row_operation" in kinds(authorised)


def test_condition_7_columns_added_removed_or_reordered_without_a_declaration():
    dropped = LEGIT.raw.drop(columns=["opponent_pressure"])
    rep = legit_audit(raw_df=dropped)
    assert "raw_transformed_column_mismatch" in blocking_kinds(rep)
    f = [x for x in rep["blocking"] if x["kind"] == "raw_transformed_column_mismatch"][0]
    assert f["relation"] == "added"
    assert f["features_absent_from_raw"] == ["opponent_pressure"]
    assert rep["gate_invoked"] is False

    reordered = LEGIT.raw[list(reversed(LEGIT.names))]
    rep2 = legit_audit(raw_df=reordered)
    assert "raw_transformed_column_mismatch" in blocking_kinds(rep2)
    assert {x["relation"] for x in rep2["blocking"]
            if x["kind"] == "raw_transformed_column_mismatch"} == {"reordered"}

    # declared, the construction of a column absent from the producer's frame is allowed
    declared = legit_audit(raw_df=dropped, transformation={
        **LEGIT.transformation,
        "column_operations": [{"kind": "construct", "cutoff_valid": True,
                               "reason": "opponent_pressure is built in the design assembler "
                                         "from pre-cutoff schedule data"}]})
    assert declared["passed"] is True, declared["blocking"]
    assert "authorised_column_operation" in kinds(declared)
    assert "raw_audit_restricted" in kinds(declared)


def test_condition_8_producer_provenance_claimed_but_unverifiable():
    for prov, problem in (
            ({"producer_source_path": "no/such/producer.py",
              "row_universe_digest": gi.index_digest(CASE.df.index, sort=True,
                                                     label="raw_index_membership")},
             "producer_source_path:unreadable"),
            ({"producer_source_path": str(Path(__file__).resolve()),
              "row_universe_digest": "raw_index_membership:n=1:sha256=deadbeef"},
             "row_universe_digest:mismatch"),
            ({"producer_source_path": str(Path(__file__).resolve()),
              "producer_source_sha256": "0" * 64,
              "row_universe_digest": gi.index_digest(CASE.df.index, sort=True,
                                                     label="raw_index_membership")},
             "producer_source_sha256:mismatch"),
            ({"producer_source_path": str(Path(__file__).resolve())},
             "row_universe_digest:absent"),
            ({"producer_source_path": str(Path(__file__).resolve()),
              "row_universe_digest": gi.index_digest(CASE.df.index, sort=True,
                                                     label="raw_index_membership"),
              "arm": "Z"}, "arm:mismatch")):
        rep = audit(provenance=prov)
        assert "producer_provenance_unverifiable" in blocking_kinds(rep), prov
        f = [x for x in rep["blocking"]
             if x["kind"] == "producer_provenance_unverifiable"][0]
        assert problem in f["problems"], (prov, f["problems"])
        assert rep["gate_invoked"] is False
        assert rep["assurance"] == "FAILED"
    assert "producer_provenance_unverifiable" in gi.NON_ADJUDICABLE


# --------------------------------------------------------------------------------------------
# 12. the remaining dual-frame obligations
# --------------------------------------------------------------------------------------------

def test_an_imputation_declared_on_a_frame_that_has_no_nulls_left_blocks():
    """Condition: imputation occurred BEFORE the raw audit. The frame presented as raw is already
    filled, so the null mask the gate exists to see never reached it."""
    rep = ws2_audit(raw_df=WS2.transformed)
    assert "imputation_precedes_raw_audit" in blocking_kinds(rep)
    f = [x for x in rep["blocking"] if x["kind"] == "imputation_precedes_raw_audit"][0]
    assert set(f["columns"]) == set(WS2_NON_ZERO)
    assert rep["gate_invoked"] is False
    assert "imputation_precedes_raw_audit" in gi.NON_ADJUDICABLE


def test_a_column_changed_between_the_two_frames_and_not_declared_blocks():
    tampered = LEGIT.transformed.copy()
    tampered["opponent_pressure"] = tampered["opponent_pressure"] * 2.0
    rep = gi.audit_fold(tampered, LEGIT.names, experiment="legit_imputation", arm="A",
                        fold="2024", offset=LEGIT.offset, target=LEGIT.target,
                        outcome_mask=LEGIT.outcome_mask, test_df=LEGIT.test_df,
                        raw_df=LEGIT.raw, transformation=LEGIT.transformation,
                        fitted_matrix=tampered[LEGIT.names], raise_on_block=False)
    assert "column_transformation_undeclared" in blocking_kinds(rep)
    f = [x for x in rep["blocking"] if x["kind"] == "column_transformation_undeclared"][0]
    assert f["columns"] == ["opponent_pressure"]
    assert rep["gate_invoked"] is False


def test_an_imputation_rule_fitted_off_the_training_rows_blocks():
    rep = legit_audit(transformation={
        **LEGIT.transformation,
        "operations": [{**LEGIT.transformation["operations"][0],
                        "fitted_on_row_universe_digest":
                            gi.index_digest(CASE.df.index, sort=True,
                                            label="design_index_membership")}]})
    assert "imputation_rule_fitted_off_training_rows" in blocking_kinds(rep)
    assert rep["gate_invoked"] is False


def test_a_stale_declaration_that_changed_nothing_is_reported_but_does_not_block():
    rep = legit_audit(transformation={
        **LEGIT.transformation,
        "operations": [LEGIT.transformation["operations"][0],
                       {"columns": ["opponent_pressure"], "method": "standardise",
                        "reason": "left over from an earlier arm", "cutoff_valid": True}]})
    assert rep["passed"] is True, rep["blocking"]
    assert "declared_transformation_had_no_effect" in kinds(rep)
    f = [x for x in rep["findings"]
         if x["kind"] == "declared_transformation_had_no_effect"][0]
    assert f["columns"] == ["opponent_pressure"]


def test_the_receipt_binds_both_frames_the_specification_and_the_fitted_matrix():
    rep = legit_audit()
    f = rep["binding"]["fields"]
    for key in ("raw_frame_values_digest", "raw_row_identity_digest", "raw_missingness_digest",
                "transformation_spec_digest", "audited_matrix_digest", "fitted_matrix_digest",
                "transformed_missingness_digest", "raw_feature_order_digest",
                "transformed_feature_order_digest"):
        assert f[key], key
    assert f["raw_frame_supplied"] is True
    assert f["transformation_declared"] is True
    assert f["transformation_kind"] == "imputation"
    assert f["frames_identical"] is False
    assert set(gi.DUAL_BINDING_FIELDS) <= set(f)
    assert set(gi.DUAL_BINDING_FIELDS) <= set(gi._INPUT_BINDING_FIELDS)


def test_a_dual_frame_receipt_cannot_be_reused_across_a_changed_raw_frame():
    rec = legit_audit(raise_on_block=True)
    other_raw = LEGIT.raw.copy()
    other_raw.iloc[0, 0] = 99.0
    v = gi.verify_receipt(rec, LEGIT.transformed, LEGIT.names, experiment="legit_imputation",
                          arm="A", fold="2024", offset=LEGIT.offset, target=LEGIT.target,
                          outcome_mask=LEGIT.outcome_mask, test_df=LEGIT.test_df,
                          raw_df=other_raw, transformation=LEGIT.transformation,
                          fitted_matrix=LEGIT.transformed[LEGIT.names], raise_on_block=False)
    assert "receipt_reuse_detected" in blocking_kinds(v)
    diverging = [x for x in v["blocking"] if x["kind"] == "receipt_reuse_detected"][0][
        "diverging_fields"]
    assert "raw_frame_values_digest" in diverging


def test_a_dual_frame_receipt_cannot_be_reused_across_a_changed_transformation_spec():
    rec = legit_audit(raise_on_block=True)
    other_spec = {**LEGIT.transformation,
                  "operations": [{**LEGIT.transformation["operations"][0], "value": 99.0}]}
    v = gi.verify_receipt(rec, LEGIT.transformed, LEGIT.names, experiment="legit_imputation",
                          arm="A", fold="2024", offset=LEGIT.offset, target=LEGIT.target,
                          outcome_mask=LEGIT.outcome_mask, test_df=LEGIT.test_df,
                          raw_df=LEGIT.raw, transformation=other_spec,
                          fitted_matrix=LEGIT.transformed[LEGIT.names], raise_on_block=False)
    assert "receipt_reuse_detected" in blocking_kinds(v)
    assert "transformation_spec_digest" in [
        x for x in v["blocking"] if x["kind"] == "receipt_reuse_detected"][0]["diverging_fields"]


def test_a_dual_frame_receipt_that_cannot_be_written_blocks():
    with tempfile.TemporaryDirectory() as d:
        blocker = Path(d) / "not_a_directory.txt"
        blocker.write_text("x", encoding="utf-8")
        rep = legit_audit(receipt_path=blocker / "receipt.json")
    assert "receipt_unwritable" in blocking_kinds(rep)
    assert rep["receipt_written"] is False
    assert rep["assurance"] == "FAILED"


def test_the_written_dual_frame_receipt_carries_the_whole_record():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "gate" / "legit.json"
        rep = legit_audit(receipt_path=p, raise_on_block=True)
        stored = json.loads(p.read_text(encoding="utf-8"))
    assert stored["binding"]["binding_digest"] == rep["binding"]["binding_digest"]
    assert stored["assurance"] == rep["assurance"]
    assert stored["dual_frame"]["raw_audit"]["passed"] is True
    assert stored["dual_frame"]["identity"]["raw_missingness"]["per_column"][
        "trailing_rest_days"]["n_missing"] > 0
    assert stored["dual_frame"]["identity"]["transformed_missingness"]["n_missing_cells"] == 0


def test_audit_run_reports_the_worst_assurance_across_its_folds():
    folds, final, _, _ = make_chronological_case(degenerate_fold=None)
    rep = gi.audit_run(run_id="assurance", experiment=EXPERIMENT, arm=ARM, folds=folds,
                       final_design=final, expected_folds=FOLD_IDS)
    note_assurance("audit_run_case1_caller_asserted", rep)
    assert rep["passed"] is True, rep["blocking"]
    assert rep["assurance"] == "RAW_PROVENANCE_ASSERTED"
    assert rep["stage1_pass"] is False
    assert set(rep["assurance_by_fold"]) == set(FOLD_IDS)
    assert set(rep["assurance_by_fold"].values()) == {"RAW_PROVENANCE_ASSERTED"}

    bad = [gi.FoldInvocation(fold=f.fold, df=f.df, names=f.names, offset=f.offset,
                             target=f.target, outcome_mask=f.outcome_mask, test_df=f.test_df)
           for f in folds]                                     # raw frames withheld
    rep2 = gi.audit_run(run_id="assurance_bad", experiment=EXPERIMENT, arm=ARM, folds=bad,
                        final_design=final, raise_on_block=False)
    assert rep2["assurance"] == "FAILED"
    assert rep2["stage1_pass"] is False
    assert "fold_invocation_failed" in blocking_kinds(rep2)


def test_the_new_dual_frame_kinds_are_declared_consistently():
    new_blocking = {"raw_frame_absent", "transformation_undeclared",
                    "transformation_declaration_malformed", "declared_identity_contradicted",
                    "raw_transformed_row_identity_mismatch", "raw_transformed_column_mismatch",
                    "column_transformation_undeclared", "imputation_precedes_raw_audit",
                    "imputation_rule_fitted_off_training_rows", "raw_frame_gate_blocked",
                    "missingness_mask_converted_to_values", "value_pattern_encodes_outcome",
                    "fitted_matrix_undeclared", "audited_matrix_is_not_the_fitted_matrix",
                    "producer_provenance_unverifiable"}
    assert new_blocking <= gi.BLOCKING
    assert gi.NON_ADJUDICABLE <= gi.BLOCKING
    assert not (gi.INFORMATIONAL & gi.BLOCKING)
    # the two DATA judgements stay adjudicable, exactly as gate_blocked is; everything that is a
    # statement about what the caller withheld does not
    assert {"raw_frame_gate_blocked", "value_pattern_encodes_outcome"} & gi.NON_ADJUDICABLE == set()
    assert (new_blocking - {"raw_frame_gate_blocked", "value_pattern_encodes_outcome"}
            ) <= gi.NON_ADJUDICABLE


# --------------------------------------------------------------------------------------------

def main() -> int:
    tests = [(n, f) for n, f in list(globals().items())
             if n.startswith("test_") and callable(f)]
    print("=" * 94)
    print("gate_invocation — invocation-layer regression tests")
    print(f"({len(tests)} tests; nothing here is scored; ws2 and ws3 are reproduced "
          f"synthetically)")
    print("=" * 94)
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
    print("=" * 94)
    if ASSURANCE_OBSERVED:
        print("assurance level reached, by case (contract §8a / specification §3):")
        for label in sorted(ASSURANCE_OBSERVED):
            level, stage1 = ASSURANCE_OBSERVED[label]
            print(f"  {label:<38} {level:<26} stage1_pass={stage1}")
        print("  NOTE: no producer feature-construction receipt or input manifest is wired into")
        print("  this repository's feature producers. Every case that does not construct a")
        print("  provenance= mapping by hand therefore reaches RAW_PROVENANCE_ASSERTED and is NOT")
        print("  a full Stage 1 pass. The two verified cases above supply provenance explicitly.")
        print("=" * 94)
    print(f"{npass} passed, {nfail} failed, {len(tests)} total")
    return 1 if nfail else 0


if __name__ == "__main__":
    raise SystemExit(main())
