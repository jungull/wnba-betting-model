#!/usr/bin/env python3
"""test_construction_receipt.py — regression tests for producer-emitted construction provenance.

The motivating defect is real and is a property of an interface: ``gate_invocation``'s
``provenance=`` was a MAPPING the caller assembled at the invocation site, so a runner that hashed
its own source file and re-digested the frame it was already holding reached ``IDENTITY_VERIFIED``
— a full Stage 1 pass — while the repository could demonstrate nothing about where that frame came
from. ``test_3_*`` below is that exact mapping: it verifies in every field it declares and still
reports ``RAW_PROVENANCE_ASSERTED``.

These tests exercise the REAL possession-prior construction path, not a synthetic stand-in. They
read the frozen canonical artifacts READ-ONLY and hash them before and after every run.
**Perturbation tests operate on TEMPORARY COPIES**; no test writes, moves or touches
``projected_exposure_v1/`` or ``possessions_v2/``, and ``test_amendment_1_*`` asserts that as a
hash equality rather than as a promise.

**Nothing here is fitted and nothing here is scored.** No projection is compared against any
realised possession and no accuracy, error, likelihood or skill statistic is computed;
``test_amendment_7_*`` asserts that over the source of all three modules.

pytest is NOT installed in this environment. This file has a standalone runner::

    python experiments/player_program/test_construction_receipt.py

It is also importable under pytest if that ever changes, since every test is a zero-argument
module-level ``test_*`` function.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import traceback
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import construction_receipt as cr                                               # noqa: E402
import gate_invocation as gi                                                    # noqa: E402
import possession_features as pf                                                # noqa: E402

HERE = Path(__file__).resolve().parent

#: persists for the process. Receipts must stay on disk while the audits that read them run.
WORK = Path(tempfile.mkdtemp(prefix="construction_receipt_tests_"))

#: filled in by the tests; printed by ``main`` so the level each case reaches is part of the run
#: output rather than something a reader has to infer.
ASSURANCE_OBSERVED: dict = {}


def note_assurance(label: str, rep: dict) -> dict:
    ASSURANCE_OBSERVED[label] = (rep.get("assurance"), bool(rep.get("stage1_pass")))
    return rep


def kinds(rep: dict) -> set:
    return {f["kind"] for f in rep["findings"]}


def blocking_kinds(rep: dict) -> set:
    return {f["kind"] for f in rep["blocking"]}


# --------------------------------------------------------------------------------------------
# fixtures over the REAL frozen artifacts, built once and memoised
# --------------------------------------------------------------------------------------------

CANONICAL = {
    "team_possession_prior_v1.parquet": pf.PRIOR_PARQUET,
    "possessions_raw_v2.parquet": pf.POSSESSIONS_PARQUET,
}

_CACHE: dict = {}


def canonical_hashes() -> dict:
    return {k: cr._sha256_file(v) for k, v in CANONICAL.items()}


def real_universe() -> pf.PossessionUniverse:
    """The real universe, from the canonical artifacts, READ-ONLY."""
    if "universe" not in _CACHE:
        _CACHE["universe"] = pf.load_universe()
    return _CACHE["universe"]


def built() -> dict:
    """Every fold and the final design, constructed once, each with its receipt on disk."""
    if "built" not in _CACHE:
        u = real_universe()
        d = WORK / "real_receipts"
        d.mkdir(parents=True, exist_ok=True)
        _CACHE["built"] = {c.fold_id: c
                           for c in pf.construct_all(u, receipt_dir=d, run_id="tests")}
    return _CACHE["built"]


def a_fold() -> pf.ConstructedFrame:
    """One representative chronological fold."""
    return built()["train_lt_2024"]


def audit_real(c: pf.ConstructedFrame, **over) -> dict:
    kw = dict(pf.gate_kwargs(c))
    kw.update(over)
    kw.setdefault("raise_on_block", False)
    return gi.audit_fold(c.frame, c.feature_names, **kw)


def copy_frozen_inputs(dest: Path) -> dict:
    """Temp COPIES of every frozen artifact and receipt the producer reads.

    Perturbation tests alter THESE. The canonical bytes are never written by this file.
    """
    dest.mkdir(parents=True, exist_ok=True)
    out = {}
    for key, src in (("prior_path", pf.PRIOR_PARQUET),
                     ("exposure_receipt_path", pf.EXPOSURE_RECEIPT),
                     ("exposure_validation_path", pf.EXPOSURE_VALIDATION),
                     ("possessions_path", pf.POSSESSIONS_PARQUET),
                     ("possessions_receipt_path", pf.POSSESSIONS_RECEIPT)):
        dst = dest / Path(src).name
        shutil.copy2(src, dst)
        out[key] = dst
    return out


# --------------------------------------------------------------------------------------------
# a synthetic Case-2 producer, for the one condition the real path cannot demonstrate honestly.
#
# The possession producer emits its frame and it is fitted unchanged, and its universe carries no
# missingness at all, so there is no legitimate transformation for it to declare. Inventing one
# would be inventing a Stage 2 hypothesis. The transformation case is therefore demonstrated on a
# seeded frame with genuine, cutoff-valid missingness — and its receipt is emitted by this module
# acting as the producer, with the frame in hand, exactly as a real producer emits one.
# --------------------------------------------------------------------------------------------

@dataclass
class TransformCase:
    raw: pd.DataFrame
    transformed: pd.DataFrame
    names: list
    offset: pd.Series
    target: pd.Series
    outcome_mask: pd.Series
    test_df: pd.DataFrame
    transformation: dict
    receipt_path: Path


def make_transform_case() -> TransformCase:
    rng = np.random.default_rng(4242)
    n = 900
    idx = pd.Index([f"tg{i:05d}" for i in range(n)], name="team_game_uid")
    appeared = rng.random(n) < 0.72
    rest = rng.integers(0, 7, n).astype(float)
    rest[rng.random(n) < 0.18] = np.nan                 # missing on FIRST games, not on outcomes
    raw = pd.DataFrame({"trailing_rest_days": rest,
                        "trailing_pace_gap": rng.normal(0.0, 3.0, n),
                        "opponent_pressure": rng.normal(0.0, 1.0, n)}, index=idx)
    names = list(raw.columns)
    fill = float(np.nanmedian(raw["trailing_rest_days"].to_numpy()))
    transformed = raw.copy()
    transformed["trailing_rest_days"] = raw["trailing_rest_days"].fillna(fill)

    t_idx = pd.Index([f"ho{i:05d}" for i in range(240)], name="team_game_uid")
    test_df = pd.DataFrame({c: rng.normal(0.0, 1.0, 240) for c in names}, index=t_idx)
    test_df["trailing_rest_days"] = test_df["trailing_rest_days"].abs().round() + fill * 0

    offset = pd.Series(np.log(rng.gamma(6.0, 6.0, n) + 5.0), index=idx)
    target = pd.Series(rng.poisson(3.1, n).astype(float), index=idx)
    mask = pd.Series(appeared, index=idx)

    transformation = {
        "kind": "imputation",
        "description": "trailing_rest_days is null on a club's first game of a season; the null "
                       "is a data-availability fact known at the prediction cutoff and is not "
                       "produced by the target game",
        "operations": [{
            "columns": ["trailing_rest_days"], "method": "fill_constant", "value": fill,
            "reason": "median rest of the chronological training rows, frozen and reapplied "
                      "unchanged to the held-out frame",
            "cutoff_valid": True, "available_at_cutoff": True,
            "frozen_parameters": {"statistic": "median", "value": fill},
            "fitted_on_row_universe_digest": gi.index_digest(
                idx, sort=True, label="design_index_membership"),
            "applied_to_test_frame": True,
        }],
    }
    receipt_path = emit_synthetic_receipt(
        raw, names, experiment="synthetic_transformation", arm="A", fold="2024",
        offset=offset, target=target, outcome_mask=mask, transformation=transformation,
        tag="transform_case")
    return TransformCase(raw, transformed, names, offset, target, mask, test_df,
                         transformation, receipt_path)


def emit_synthetic_receipt(frame: pd.DataFrame, names, *, experiment: str, arm: str, fold: str,
                           scope: str = "fold", offset=None, target=None, outcome_mask=None,
                           transformation=None, tag: str = "case",
                           producer_path=None) -> Path:
    """Materialise a source artifact and emit a real construction receipt for ``frame``."""
    d = WORK / "synthetic_producer"
    d.mkdir(parents=True, exist_ok=True)
    artifact = d / f"source__{tag}.csv"
    frame.to_csv(artifact, index=True)
    source = cr.source_declaration(
        artifact, role="feature_source", artifact_id=f"synthetic_source/{tag}", cutoff_valid=True,
        cutoff_rationale="seeded synthetic frame; the null mask is a first-game availability fact "
                         "known at the cutoff and no column is a function of the target game",
        coverage={"rows": int(len(frame))})
    keys = pd.DataFrame({"row_uid": [str(x) for x in frame.index]}, index=frame.index)
    universe = cr.universe_contract(
        keys, contract_id=f"synthetic_universe/{tag}", row_identity_columns=["row_uid"],
        description="the seeded synthetic row universe this test constructs")
    path = d / f"CONSTRUCTION_RECEIPT__{tag}.json"
    cr.emit_construction_receipt(
        receipt_path=path, experiment=experiment, arm=arm, fold=fold, scope=scope,
        run_id=f"synthetic::{tag}", frame=frame, feature_names=list(names), universe=universe,
        fold_identity=cr.fold_declaration(fold_id=fold, kind=scope, n_rows=int(len(frame))),
        cutoff=cr.cutoff_contract(
            decision_time_rule="synthetic: no column is a function of a post-cutoff observation",
            fold_cutoff=fold),
        sources=[source], feature_set_id=f"synthetic/{tag}", transformation=transformation,
        gate_arguments={"offset": offset, "target": target, "outcome_mask": outcome_mask},
        producer_path=producer_path)
    return path


def transform_case() -> TransformCase:
    if "transform" not in _CACHE:
        _CACHE["transform"] = make_transform_case()
    return _CACHE["transform"]


# ============================================================================================
# THE TEN REQUIRED CONDITIONS — specification §4
# ============================================================================================

def test_1_producer_emitted_receipt_and_unchanged_frame_reaches_identity_verified():
    c = a_fold()
    rep = note_assurance("real_possession_fold", audit_real(c))
    assert rep["passed"] is True, rep["blocking"]
    assert rep["gate_invoked"] is True and rep["gate"]["passed"] is True
    assert rep["dual_frame"]["case"] == "identity"
    assert rep["assurance"] == "IDENTITY_VERIFIED"
    assert rep["stage1_pass"] is True

    got = rep["dual_frame"]["construction_receipt"]
    assert got["claimed"] is True and got["source"] == "path"
    assert got["verified"] is True and got["grants_assurance"] is True
    assert got["receipt_path"] == str(c.receipt_path)
    assert got["producer_source_path"].endswith("possession_features.py")
    assert got["producer_source_sha256"] == cr._sha256_file(HERE / "possession_features.py")
    assert got["producing_commit"]["resolved"] is True and got["producing_commit"]["sha"]
    assert got["checks"]["cross_module_digest_agreement"] is True
    assert "construction_receipt_verified" in kinds(rep)
    # ...and the receipt's digests are BOUND into the gate record, so it cannot be swapped later
    f = rep["binding"]["fields"]
    assert f["construction_receipt_verified"] is True
    assert f["construction_receipt_digest"].startswith("construction:sha256=")
    assert len(f["construction_frozen_source_manifest"]) == 2


def test_2_producer_emitted_receipt_with_a_declared_transformation_reaches_transformation_verified():
    t = transform_case()
    rep = note_assurance("synthetic_declared_imputation", gi.audit_fold(
        t.transformed, t.names, experiment="synthetic_transformation", arm="A", fold="2024",
        offset=t.offset, target=t.target, outcome_mask=t.outcome_mask, test_df=t.test_df,
        raw_df=t.raw, transformation=t.transformation,
        fitted_matrix=t.transformed[t.names], construction_receipt=t.receipt_path,
        raise_on_block=False))
    assert rep["passed"] is True, rep["blocking"]
    assert rep["dual_frame"]["case"] == "transformation"
    assert rep["dual_frame"]["raw_gate_invoked"] is True
    assert rep["dual_frame"]["raw_audit"]["passed"] is True
    assert rep["assurance"] == "TRANSFORMATION_VERIFIED"
    assert rep["stage1_pass"] is True
    assert rep["dual_frame"]["construction_receipt"]["verified"] is True
    # the receipt describes the RAW frame, which is the frame whose null mask the gate audited
    rec = rep["dual_frame"]["construction_receipt"]["receipt"]
    prof = rec["produced_frame_provenance"]["raw_frame"]["missingness"]
    assert prof["n_missing_cells"] > 0
    assert "trailing_rest_days" in prof["columns_with_missing"]


def test_3_caller_created_provenance_cannot_reach_a_verified_status():
    c = a_fold()

    # (a) a provenance MAPPING, complete and internally consistent, verifying in every field
    prov = {"producer_source_path": str(HERE / "possession_features.py"),
            "producer_source_sha256": cr._sha256_file(HERE / "possession_features.py"),
            "input_manifest": {str(pf.PRIOR_PARQUET): cr._sha256_file(pf.PRIOR_PARQUET)},
            "feature_construction_receipt": str(c.receipt_path),
            "experiment": pf.EXPERIMENT, "arm": pf.ARM,
            "row_universe_digest": gi.index_digest(c.frame.index, sort=True,
                                                   label="raw_index_membership")}
    kw = pf.gate_kwargs(c)
    kw.pop("construction_receipt")
    mapped = note_assurance("caller_manufactured_mapping", gi.audit_fold(
        c.frame, c.feature_names, provenance=prov, raise_on_block=False, **kw))
    assert mapped["passed"] is True, mapped["blocking"]
    assert mapped["dual_frame"]["provenance"]["verified"] is True      # every field checks out
    assert mapped["dual_frame"]["provenance"]["grants_assurance"] is False
    assert mapped["assurance"] == "RAW_PROVENANCE_ASSERTED"            # and it grants nothing
    assert mapped["stage1_pass"] is False
    assert "producer_construction_receipt_absent" in kinds(mapped)

    # (b) the receipt's own CONTENT, offered inline instead of as a path, is refused outright
    body = json.loads(Path(c.receipt_path).read_text(encoding="utf-8"))
    inline = note_assurance("inline_receipt_body", audit_real(c, construction_receipt=body))
    assert "construction_receipt_not_read_from_disk" in blocking_kinds(inline)
    assert inline["assurance"] == "FAILED"
    assert inline["gate_invoked"] is False
    assert inline["dual_frame"]["construction_receipt"]["source"] == "inline"

    # (c) and it cannot be adjudicated away, because an escape hatch would reopen the defect
    still = audit_real(c, construction_receipt=body,
                       adjudications={**pf.OUTCOME_MASK_ADJUDICATION,
                                      "construction_receipt_not_read_from_disk":
                                          "we are confident this receipt is genuine"})
    assert "construction_receipt_not_read_from_disk" in blocking_kinds(still)
    assert "construction_receipt_not_read_from_disk" in gi.NON_ADJUDICABLE
    assert "construction_receipt_unverifiable" in gi.NON_ADJUDICABLE


def test_4_altered_producer_code_blocks():
    d = WORK / "altered_producer"
    d.mkdir(parents=True, exist_ok=True)
    producer_copy = d / "possession_features_copy.py"
    shutil.copy2(HERE / "possession_features.py", producer_copy)

    u = real_universe()
    fold = pf.chronological_folds(u)[2]
    c = pf.construct(u, receipt_dir=d, run_id="altered_producer", fold=fold,
                     producer_path=producer_copy)
    ok = cr.verify_construction_receipt(c.receipt_path, frame=c.frame,
                                        feature_names=c.feature_names,
                                        experiment=pf.EXPERIMENT, arm=pf.ARM, fold=c.fold_id,
                                        scope="fold")
    assert ok["verified"] is True, ok["blocking"]

    producer_copy.write_text(producer_copy.read_text(encoding="utf-8") + "\n# edited\n",
                             encoding="utf-8")

    after = cr.verify_construction_receipt(c.receipt_path, frame=c.frame,
                                           feature_names=c.feature_names,
                                           experiment=pf.EXPERIMENT, arm=pf.ARM, fold=c.fold_id,
                                           scope="fold")
    assert after["verified"] is False
    assert "producer_source_digest_mismatch" in {f["kind"] for f in after["blocking"]}

    rep = note_assurance("altered_producer_source", audit_real(c))
    assert "construction_receipt_unverifiable" in blocking_kinds(rep)
    assert rep["assurance"] == "FAILED"
    assert rep["gate_invoked"] is False                   # the failure precedes the gate and the fit
    assert cr._sha256_file(HERE / "possession_features.py") != cr._sha256_file(producer_copy)


def test_5_altered_input_artifact_blocks():
    d = WORK / "altered_artifact"
    paths = copy_frozen_inputs(d)
    before_canonical = canonical_hashes()

    u = pf.load_universe(**paths)
    fold = pf.chronological_folds(u)[0]
    c = pf.construct(u, receipt_dir=d, run_id="altered_artifact", fold=fold)
    ok = cr.verify_construction_receipt(c.receipt_path, frame=c.frame,
                                        feature_names=c.feature_names, experiment=pf.EXPERIMENT,
                                        arm=pf.ARM, fold=c.fold_id, scope="fold")
    assert ok["verified"] is True, ok["blocking"]
    # the receipt bound the COPY, and the copy is byte-identical to the canonical artifact
    manifest = {s["path"]: s["sha256"]
                for s in ok["receipt"]["frozen_source_provenance"]["sources"]}
    assert manifest[str(paths["prior_path"].resolve())] == before_canonical[
        "team_possession_prior_v1.parquet"]

    with open(paths["prior_path"], "ab") as fh:                       # perturb the COPY only
        fh.write(b"\x00")

    after = cr.verify_construction_receipt(c.receipt_path, frame=c.frame,
                                           feature_names=c.feature_names, experiment=pf.EXPERIMENT,
                                           arm=pf.ARM, fold=c.fold_id, scope="fold")
    assert after["verified"] is False
    assert "source_artifact_digest_mismatch" in {f["kind"] for f in after["blocking"]}

    rep = note_assurance("altered_frozen_artifact", audit_real(c))
    assert "construction_receipt_unverifiable" in blocking_kinds(rep)
    assert rep["assurance"] == "FAILED"
    assert rep["gate_invoked"] is False
    assert canonical_hashes() == before_canonical         # the canonical bytes never moved


def test_6_altered_row_universe_blocks():
    c = a_fold()
    fewer = c.frame.iloc[:-5]

    at_receipt = cr.verify_construction_receipt(c.receipt_path, frame=fewer,
                                                feature_names=c.feature_names,
                                                experiment=pf.EXPERIMENT, arm=pf.ARM,
                                                fold=c.fold_id, scope="fold")
    assert at_receipt["verified"] is False
    assert "row_universe_mismatch" in {f["kind"] for f in at_receipt["blocking"]}

    # a REORDER keeps the membership and loses the order, and is caught as its own thing
    shuffled = c.frame.iloc[::-1]
    reordered = cr.verify_construction_receipt(c.receipt_path, frame=shuffled,
                                               feature_names=c.feature_names,
                                               experiment=pf.EXPERIMENT, arm=pf.ARM,
                                               fold=c.fold_id, scope="fold")
    assert "row_order_mismatch" in {f["kind"] for f in reordered["blocking"]}

    # and at the gate, with every argument subset consistently so the ARGUMENT layer is clean
    kw = pf.gate_kwargs(c)
    kw.update(offset=c.offset.iloc[:-5], target=c.target.iloc[:-5],
              outcome_mask=c.outcome_mask.iloc[:-5], raw_df=fewer,
              fitted_matrix=fewer[c.feature_names], raise_on_block=False)
    rep = note_assurance("altered_row_universe", gi.audit_fold(fewer, c.feature_names, **kw))
    assert "construction_receipt_unverifiable" in blocking_kinds(rep)
    assert rep["assurance"] == "FAILED"
    assert rep["gate_invoked"] is False


def test_7_altered_raw_frame_blocks():
    c = a_fold()
    tampered = c.frame.copy()
    col = c.feature_names[0]
    tampered.iloc[0, tampered.columns.get_loc(col)] = float(tampered[col].iloc[0]) + 1.0

    at_receipt = cr.verify_construction_receipt(c.receipt_path, frame=tampered,
                                                feature_names=c.feature_names,
                                                experiment=pf.EXPERIMENT, arm=pf.ARM,
                                                fold=c.fold_id, scope="fold")
    assert at_receipt["verified"] is False
    assert "raw_frame_digest_mismatch" in {f["kind"] for f in at_receipt["blocking"]}

    kw = pf.gate_kwargs(c)
    kw.update(raw_df=tampered, fitted_matrix=tampered[c.feature_names], raise_on_block=False)
    rep = note_assurance("altered_raw_frame", gi.audit_fold(tampered, c.feature_names, **kw))
    assert "construction_receipt_unverifiable" in blocking_kinds(rep)
    assert rep["assurance"] == "FAILED"
    assert rep["gate_invoked"] is False

    # a NULL introduced where the producer recorded none is caught by the mask digests alone
    nulled = c.frame.copy()
    nulled.iloc[3, nulled.columns.get_loc(col)] = np.nan
    masked = cr.verify_construction_receipt(c.receipt_path, frame=nulled,
                                            feature_names=c.feature_names,
                                            experiment=pf.EXPERIMENT, arm=pf.ARM,
                                            fold=c.fold_id, scope="fold")
    assert "missingness_digest_mismatch" in {f["kind"] for f in masked["blocking"]}
    assert col in [f for b in masked["blocking"] if b["kind"] == "missingness_digest_mismatch"
                   for f in b["columns"]]


def test_8_auditing_one_matrix_and_fitting_another_blocks():
    c = a_fold()
    other = c.fitted_matrix.copy()
    other[c.feature_names[0]] = other[c.feature_names[0]] * 2.0     # a standardised copy, say
    rep = note_assurance("fitted_matrix_is_not_the_audited_one",
                         audit_real(c, fitted_matrix=other))
    assert "audited_matrix_is_not_the_fitted_matrix" in blocking_kinds(rep)
    assert rep["assurance"] == "FAILED"
    assert rep["gate_invoked"] is False
    assert rep["dual_frame"]["fitted_matrix"]["matches"] is False
    assert "audited_matrix_is_not_the_fitted_matrix" in gi.NON_ADJUDICABLE


def test_9_a_copied_receipt_reused_for_another_fold_or_cutoff_blocks():
    b = built()
    donor, target = b["train_lt_2023"], b["train_lt_2025"]

    forged = WORK / "forged" / Path(target.receipt_path).name
    forged.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(donor.receipt_path, forged)                  # the same bytes, a different name

    at_receipt = cr.verify_construction_receipt(forged, frame=target.frame,
                                                feature_names=target.feature_names,
                                                experiment=pf.EXPERIMENT, arm=pf.ARM,
                                                fold=target.fold_id, scope="fold")
    assert at_receipt["verified"] is False
    got = {f["kind"] for f in at_receipt["blocking"]}
    assert "fold_identity_mismatch" in got
    assert "row_universe_mismatch" in got

    rep = note_assurance("copied_receipt_other_fold", audit_real(target,
                                                                construction_receipt=forged))
    assert "construction_receipt_unverifiable" in blocking_kinds(rep)
    assert rep["assurance"] == "FAILED"

    # the same receipt against its OWN fold but a DIFFERENT declared cutoff
    cutoff = cr.verify_construction_receipt(donor.receipt_path, frame=donor.frame,
                                            feature_names=donor.feature_names,
                                            experiment=pf.EXPERIMENT, arm=pf.ARM,
                                            fold=donor.fold_id, scope="fold",
                                            cutoff=target.cutoff)
    assert "cutoff_contract_mismatch" in {f["kind"] for f in cutoff["blocking"]}


def test_10_failure_to_write_the_producer_receipt_blocks_before_fitting():
    # (a) the producer cannot archive its construction, so it produces no frame at all
    d = WORK / "unwritable"
    d.mkdir(parents=True, exist_ok=True)
    blocker = d / "not_a_directory.txt"
    blocker.write_text("x", encoding="utf-8")
    u = real_universe()
    raised = None
    try:
        pf.construct(u, receipt_dir=blocker, run_id="unwritable",
                     fold=pf.chronological_folds(u)[0])
    except cr.ConstructionReceiptFailure as e:
        raised = e
    assert raised is not None, "an unwritable construction receipt must not yield a frame"
    assert "could not be written" in str(raised)

    # (b) and a gate handed a receipt path that was never written blocks before any fit
    c = a_fold()
    missing = d / "never_written.json"
    assert not missing.exists()
    rep = note_assurance("receipt_never_written", audit_real(c, construction_receipt=missing))
    assert "construction_receipt_unverifiable" in blocking_kinds(rep)
    assert "construction_receipt_absent" in {
        k for f in rep["blocking"] if f["kind"] == "construction_receipt_unverifiable"
        for k in (f.get("problems") or [])}
    assert rep["gate_invoked"] is False
    assert rep["assurance"] == "FAILED"

    fitted = {"called": False}

    def _fit(record, bound):                                  # pragma: no cover - must not run
        fitted["called"] = True
        return "model"

    kw = pf.gate_kwargs(c)
    kw["construction_receipt"] = str(missing)
    try:
        gi.guarded_fit(_fit, c.frame, c.feature_names,
                       receipt_path=WORK / "unwritable" / "gate.json", **kw)
    except gi.GateInvocationFailure:
        pass
    else:                                                     # pragma: no cover - must not happen
        raise AssertionError("guarded_fit must refuse to fit without a verifiable receipt")
    assert fitted["called"] is False


# ============================================================================================
# AMENDMENT §4 — the seven additional dry-run checks, verified independently
# ============================================================================================

def test_amendment_1_canonical_parquet_hashes_are_unchanged_before_and_after_the_run():
    before = canonical_hashes()
    out = pf.dry_run(WORK / "amendment_dry_run", run_id="amendment", verbose=False)
    after = canonical_hashes()
    assert before == after, "the run changed a canonical artifact"
    assert out["canonical_artifacts_unchanged"] is True
    assert out["canonical_artifact_hashes_before"] == out["canonical_artifact_hashes_after"]
    assert before == out["canonical_artifact_hashes_after"]
    _CACHE["dry_run"] = out


def test_amendment_2_the_receipt_references_the_current_frozen_artifact_hashes():
    c = a_fold()
    manifest = {s["path"]: s["sha256"]
                for s in c.receipt["frozen_source_provenance"]["sources"]}
    assert manifest[str(pf.PRIOR_PARQUET.resolve())] == cr._sha256_file(pf.PRIOR_PARQUET)
    assert manifest[str(pf.POSSESSIONS_PARQUET.resolve())] == cr._sha256_file(
        pf.POSSESSIONS_PARQUET)
    # and the pre-existing artifact / validation receipts still certify those same bytes
    src = c.receipt["frozen_source_provenance"]["sources"][0]
    assert src["artifact_receipt"]["matches_current_artifact_bytes"] is True
    assert src["validation_receipt"]["matches_current_artifact_bytes"] is True
    assert src["validation_receipt"]["verdict"] == "PASS"
    # ...which is a LEGACY attestation, and the receipt says so in its own words
    assert c.receipt["frozen_source_provenance"]["established_by_this_receipt"] is False
    assert c.receipt["frozen_source_provenance"]["status"] == "legacy_receipts_only"
    assert c.receipt["produced_frame_provenance"]["established_by_this_receipt"] is True


def test_amendment_3_changing_a_frozen_source_path_or_hash_blocks():
    d = WORK / "moved_source"
    paths = copy_frozen_inputs(d)
    u = pf.load_universe(**paths)
    c = pf.construct(u, receipt_dir=d, run_id="moved_source", fold=pf.chronological_folds(u)[0])
    assert cr.verify_construction_receipt(
        c.receipt_path, frame=c.frame, feature_names=c.feature_names,
        experiment=pf.EXPERIMENT, arm=pf.ARM, fold=c.fold_id, scope="fold")["verified"] is True

    # a PATH that no longer resolves
    moved = d / "renamed_prior.parquet"
    paths["prior_path"].rename(moved)
    gone = cr.verify_construction_receipt(c.receipt_path, frame=c.frame,
                                          feature_names=c.feature_names, experiment=pf.EXPERIMENT,
                                          arm=pf.ARM, fold=c.fold_id, scope="fold")
    assert gone["verified"] is False
    assert "source_artifact_unreadable" in {f["kind"] for f in gone["blocking"]}

    # a HASH edited inside the receipt, without re-binding it
    body = json.loads(Path(c.receipt_path).read_text(encoding="utf-8"))
    body["frozen_source_provenance"]["sources"][0]["sha256"] = "0" * 64
    edited = d / "edited_receipt.json"
    edited.write_text(json.dumps(body, indent=2), encoding="utf-8")
    tampered = cr.verify_construction_receipt(edited, frame=c.frame,
                                              feature_names=c.feature_names,
                                              experiment=pf.EXPERIMENT, arm=pf.ARM,
                                              fold=c.fold_id, scope="fold")
    assert tampered["verified"] is False
    got = {f["kind"] for f in tampered["blocking"]}
    assert "construction_receipt_self_binding_broken" in got
    assert "source_manifest_mismatch" in got


def test_amendment_4_incumbent_k0_and_challenger_share_one_team_game_universe():
    u = real_universe()
    rep = pf.parity_report(u)
    assert rep["parity"] is True and rep["diverging_fields"] == []
    ins = rep["inputs"]
    assert {ins[k]["row_universe_digest"] for k in ins} == {u.row_universe_digest}
    assert {ins[k]["row_order_digest"] for k in ins} == {u.contract["row_order_digest"]}
    assert {ins[k]["offset_digest"] for k in ins} == {ins["challenger"]["offset_digest"]}
    assert {ins[k]["target_digest"] for k in ins} == {ins["challenger"]["target_digest"]}
    assert ins["incumbent"]["n_features"] == 0 and ins["k0"]["n_features"] == 0
    assert ins["challenger"]["features"] == list(pf.FEATURE_NAMES)

    # per fold, too: the three are drawn from the same rows at every cutoff
    for fold in pf.chronological_folds(u):
        sub = pf.parity_report(u, fold.train_index)
        assert sub["parity"] is True, (fold.fold_id, sub["diverging_fields"])

    # and a challenger drawn from a DIFFERENT universe is refused rather than compared
    c = a_fold()
    other = cr.universe_contract(
        c.frame.iloc[:-1], contract_id=pf.UNIVERSE_CONTRACT_ID,
        row_identity_columns=list(pf.ROW_IDENTITY_COLUMNS), description="a different universe")
    mismatched = cr.verify_construction_receipt(
        c.receipt_path, frame=c.frame, feature_names=c.feature_names, experiment=pf.EXPERIMENT,
        arm=pf.ARM, fold=c.fold_id, scope="fold", universe=other)
    assert "universe_contract_mismatch" in {f["kind"] for f in mismatched["blocking"]}


def test_amendment_5_a_receipt_from_one_fold_cannot_validate_another_fold():
    b = built()
    ids = [k for k in b if k != "final_design"]
    for donor_id in ids:
        for target_id in ids:
            rep = cr.verify_construction_receipt(
                b[donor_id].receipt_path, frame=b[target_id].frame,
                feature_names=b[target_id].feature_names, experiment=pf.EXPERIMENT, arm=pf.ARM,
                fold=target_id, scope="fold")
            if donor_id == target_id:
                assert rep["verified"] is True, (donor_id, rep["blocking"])
            else:
                assert rep["verified"] is False, (donor_id, target_id)
                assert "fold_identity_mismatch" in {f["kind"] for f in rep["blocking"]}


def test_amendment_6_a_final_design_receipt_cannot_be_reused_as_a_fold_receipt():
    b = built()
    final, fold = b["final_design"], b["train_lt_2026"]
    assert final.scope == "final_design" and fold.scope == "fold"

    rep = cr.verify_construction_receipt(final.receipt_path, frame=fold.frame,
                                         feature_names=fold.feature_names,
                                         experiment=pf.EXPERIMENT, arm=pf.ARM,
                                         fold=fold.fold_id, scope="fold")
    assert rep["verified"] is False
    diverging = [f for f in rep["blocking"] if f["kind"] == "fold_identity_mismatch"][0]
    assert "scope" in diverging["diverging"] and "fold" in diverging["diverging"]

    # even offered for its OWN rows, the scope alone is enough to refuse it as a fold receipt
    same_rows = cr.verify_construction_receipt(final.receipt_path, frame=final.frame,
                                               feature_names=final.feature_names,
                                               experiment=pf.EXPERIMENT, arm=pf.ARM,
                                               fold=final.fold_id, scope="fold")
    assert same_rows["verified"] is False
    assert "fold_identity_mismatch" in {f["kind"] for f in same_rows["blocking"]}

    at_gate = note_assurance("final_design_receipt_as_fold",
                             audit_real(fold, construction_receipt=final.receipt_path))
    assert "construction_receipt_unverifiable" in blocking_kinds(at_gate)
    assert at_gate["assurance"] == "FAILED"


def test_amendment_7_no_accuracy_metric_is_read_or_computed_anywhere():
    # Tokens that would be present if anything here scored a projection against an outcome, or
    # fitted anything. They are assembled from halves so the literals do not appear in this file
    # and the scan can therefore include this file itself rather than exempting it.
    forbidden = tuple(a + b for a, b in (
        ("r2_", "score"), ("roc_", "auc"), ("log_", "loss"), ("bri", "er"),
        ("mean_squared_", "error"), ("mean_absolute_", "error"), ("accuracy_", "score"),
        ("skl", "earn"), ("stats", "models"), ("explained_", "variance"),
        (".f", "it("), ("IR", "LS"), ("co", "ef_"), ("Ridge", "CV"), ("Poi", "sson(")))
    for mod in ("construction_receipt.py", "possession_features.py",
                "test_construction_receipt.py"):
        text = (HERE / mod).read_text(encoding="utf-8")
        hit = [t for t in forbidden if t in text]
        assert not hit, (mod, hit)
    out = _CACHE.get("dry_run") or pf.dry_run(WORK / "amendment_dry_run_2", run_id="amendment2",
                                              verbose=False)
    assert out["nothing_fitted"] is True and out["nothing_scored"] is True
    assert "no_accuracy_computed" in out
    flat = json.dumps(out, default=str).lower()
    for t in tuple(a + b for a, b in (("rm", "se"), ("r", "2_"), ("a", "uc"), ("log_", "loss"),
                                      ("bri", "er"), ("ski", "ll"), ("dev", "iance"))):
        assert t not in flat, t


# ============================================================================================
# the producer, the receipt as a document, and the module contracts
# ============================================================================================

def test_the_real_possession_path_reaches_identity_verified_on_every_fold_and_the_final_design():
    out = _CACHE.get("dry_run") or pf.dry_run(WORK / "dry_run_all", run_id="all", verbose=False)
    _CACHE["dry_run"] = out
    assert out["parity"]["parity"] is True
    assert len(out["folds"]) == 6
    for r in out["folds"]:
        note_assurance(f"real::{r['fold']}", {"assurance": r["assurance"],
                                              "stage1_pass": r["stage1_pass"]})
        assert r["receipt_verified"] is True, (r["fold"], r["receipt_blocking"])
        assert r["gate_passed"] is True, (r["fold"], r["blocking"])
        assert r["assurance"] == "IDENTITY_VERIFIED", r["fold"]
        assert r["stage1_pass"] is True, r["fold"]
    # the five folds are complete; the final assembled design has no frame after it to check
    # schema drift against, and says so rather than passing as though the check had run
    folds = {r["fold"]: r for r in out["folds"]}
    assert all(folds[f]["complete"] for f in folds if f != "final_design")
    assert folds["final_design"]["complete"] is False
    assert folds["final_design"]["checks_not_run"] == ["schema_mismatch"]


def test_the_two_modules_compute_the_same_digests_over_the_same_objects():
    """The producer must not depend on the gate, so the digest algebra is implemented twice.

    That duplication is only safe if it cannot drift silently, which is what this asserts.
    """
    c = a_fold()
    assert cr.matrix_digest(c.frame, c.feature_names) == gi.matrix_digest(c.frame,
                                                                         c.feature_names)
    assert cr.index_digest(c.frame.index, sort=True) == gi.index_digest(c.frame.index, sort=True)
    assert cr.index_digest(c.frame.index) == gi.index_digest(c.frame.index)
    assert cr.values_digest(c.offset, label="offset_values") == gi.value_digest(
        c.offset, label="offset_values")
    got = cr.missingness_profile(c.frame, c.feature_names)
    want = gi._missingness_profile(c.frame, c.feature_names)
    assert got["aggregate_digest"] == want["aggregate_digest"]
    for col in c.feature_names:
        assert got["per_column"][col]["missing_mask_digest"] == \
            want["per_column"][col]["missing_mask_digest"]
    # scalar formatting is where a duplicated algebra drifts first
    for v in (True, False, 1, -3, 0.5, float("nan"), None, "x", np.int64(7), np.float64(2.5)):
        assert cr.scalar_repr(v) == gi._scalar_repr(v), v


def test_the_receipt_carries_every_field_the_contract_requires():
    c = a_fold()
    r = c.receipt
    assert r["schema"] == cr.CONSTRUCTION_RECEIPT_SCHEMA
    ident, prod = r["identity"], r["produced_frame_provenance"]
    assert ident["experiment"] == pf.EXPERIMENT and ident["arm"] == pf.ARM
    assert ident["fold"] == c.fold_id and ident["scope"] == "fold"
    assert ident["run_id"] and ident["run_uid"]
    assert prod["producer"]["source_path"].endswith("possession_features.py")
    assert len(prod["producer"]["source_sha256"]) == 64
    assert prod["commit"]["resolved"] is True and len(prod["commit"]["sha"]) == 40
    assert prod["cutoff"]["decision_time_rule"] and prod["cutoff"]["fold_cutoff"]
    assert prod["cutoff"]["per_row_decision_time_column"] == pf.DECISION_TIME_COLUMN
    assert prod["fold"]["fold_id"] == c.fold_id and prod["fold"]["kind"] == "fold"
    assert prod["fold"]["first_decision_time"] and prod["fold"]["last_decision_time"]
    assert prod["universe"]["row_universe_digest"] and prod["universe"]["row_order_digest"]
    assert prod["features"]["names"] == list(pf.FEATURE_NAMES)
    assert prod["features"]["feature_order_digest"] and \
        prod["features"]["feature_name_membership_digest"]
    assert prod["raw_frame"]["values_digest"] and prod["raw_frame"]["row_identity_digest"]
    per_col = prod["raw_frame"]["missingness"]["per_column"]
    assert set(per_col) == set(pf.FEATURE_NAMES)
    assert all("sha256=" in v["missing_mask_digest"] for v in per_col.values())
    assert prod["generation"]["result"] == "ok" and prod["generation"]["failure"] is None
    assert prod["output"]["digest"] == cr.matrix_digest(c.frame, c.feature_names)
    assert set(prod["gate_argument_digests"]) == {"offset", "target", "outcome_mask"}
    # every source carries a cutoff-validity declaration WITH a rationale
    for s in r["frozen_source_provenance"]["sources"]:
        assert isinstance(s["cutoff_valid"], bool)
        assert isinstance(s["cutoff_rationale"], str) and s["cutoff_rationale"].strip()
        assert s["role"] in cr.SOURCE_ROLES
        assert len(s["sha256"]) == 64
    assert r["binding"]["receipt_digest"] == cr.receipt_digest(cr.binding_fields(r))


def test_the_claim_boundary_is_carried_and_states_what_is_not_established():
    c = a_fold()
    b = c.receipt["claim_boundary"]
    assert b["frozen_source_provenance_status"] == "legacy_receipts_only"
    assert "does not add construction provenance to any upstream canonical artifact" in \
        b["does_not_establish"]
    assert "team_possession_prior_v1" in b["stage"]
    # the boundary travels into the gate record, so a reader of the receipt sees it too
    rep = audit_real(c)
    assert rep["dual_frame"]["construction_receipt"]["claim_boundary"] == b


def test_a_failed_construction_is_recordable_and_blocks():
    d = WORK / "failed_construction"
    d.mkdir(parents=True, exist_ok=True)
    c = a_fold()
    keys = pd.DataFrame({"row_uid": [str(x) for x in c.frame.index]}, index=c.frame.index)
    path = d / "FAILED.json"
    cr.emit_construction_receipt(
        receipt_path=path, experiment=pf.EXPERIMENT, arm=pf.ARM, fold=c.fold_id, scope="fold",
        run_id="failed", frame=c.frame, feature_names=c.feature_names,
        universe=cr.universe_contract(keys, contract_id=pf.UNIVERSE_CONTRACT_ID,
                                      row_identity_columns=["row_uid"],
                                      description="the fold's rows"),
        fold_identity=cr.fold_declaration(fold_id=c.fold_id, kind="fold", n_rows=len(c.frame)),
        cutoff=cr.cutoff_contract(decision_time_rule="as declared"),
        sources=real_universe().sources, generation_result="failed",
        failure={"reason": "a downstream invariant did not hold", "stage": "assertion"})
    rep = cr.verify_construction_receipt(path, frame=c.frame, feature_names=c.feature_names,
                                         experiment=pf.EXPERIMENT, arm=pf.ARM, fold=c.fold_id,
                                         scope="fold")
    assert rep["verified"] is False
    assert "construction_failed" in {f["kind"] for f in rep["blocking"]}
    # ...and it cannot be emitted without a failure state at all
    try:
        cr.emit_construction_receipt(
            receipt_path=d / "x.json", experiment=pf.EXPERIMENT, arm=pf.ARM, fold=c.fold_id,
            run_id="r", frame=c.frame, feature_names=c.feature_names,
            universe=cr.universe_contract(keys, contract_id="u", row_identity_columns=["row_uid"],
                                          description="d"),
            fold_identity=cr.fold_declaration(fold_id=c.fold_id, kind="fold", n_rows=1),
            cutoff=cr.cutoff_contract(decision_time_rule="r"), sources=real_universe().sources,
            generation_result="failed")
    except cr.ConstructionReceiptFailure as e:
        assert "failure state" in str(e)
    else:                                                     # pragma: no cover - must not happen
        raise AssertionError("a failed construction must record its failure state")


def test_the_producer_refuses_to_describe_a_construction_it_cannot_describe_honestly():
    c = a_fold()
    keys = pd.DataFrame({"row_uid": [str(x) for x in c.frame.index]}, index=c.frame.index)
    uc = cr.universe_contract(keys, contract_id="u", row_identity_columns=["row_uid"],
                              description="d")
    base = dict(receipt_path=WORK / "refused.json", experiment=pf.EXPERIMENT, arm=pf.ARM,
                fold=c.fold_id, run_id="r", frame=c.frame, feature_names=c.feature_names,
                universe=uc,
                fold_identity=cr.fold_declaration(fold_id=c.fold_id, kind="fold",
                                                  n_rows=len(c.frame)),
                cutoff=cr.cutoff_contract(decision_time_rule="r"),
                sources=real_universe().sources)

    def refuses(**over) -> str:
        kw = dict(base)
        kw.update(over)
        try:
            cr.emit_construction_receipt(**kw)
        except cr.ConstructionReceiptFailure as e:
            return str(e)
        raise AssertionError(f"emission should have been refused for {sorted(over)}")

    assert "positional" in refuses(frame=c.frame.reset_index(drop=True))
    assert "absent from the constructed frame" in refuses(feature_names=["not_a_column"])
    assert "no declared source artifacts" in refuses(sources=[])
    assert "experiment" in refuses(experiment="  ")
    assert "contradicts fold" in refuses(fold="some_other_fold")
    assert "duplicate feature names" in refuses(
        feature_names=list(c.feature_names) + [c.feature_names[0]])
    # a universe contract that is not the frame's own rows cannot be declared for it
    other = cr.universe_contract(keys.iloc[:-2], contract_id="u",
                                 row_identity_columns=["row_uid"], description="d")
    assert "not the declared universe contract" in refuses(universe=other)


def test_a_feature_source_that_does_not_assert_cutoff_validity_is_refused():
    try:
        cr.source_declaration(pf.PRIOR_PARQUET, role="feature_source", cutoff_valid=False,
                              cutoff_rationale="we did not check")
    except cr.ConstructionReceiptFailure as e:
        assert "does NOT assert cutoff validity" in str(e)
    else:                                                     # pragma: no cover - must not happen
        raise AssertionError("a non-cutoff-valid feature source must be refused")
    # a rationale is mandatory even when validity IS asserted
    try:
        cr.source_declaration(pf.PRIOR_PARQUET, role="feature_source", cutoff_valid=True,
                              cutoff_rationale="   ")
    except cr.ConstructionReceiptFailure as e:
        assert "cutoff_rationale is mandatory" in str(e)
    else:                                                     # pragma: no cover - must not happen
        raise AssertionError("a source declaration without a rationale must be refused")
    # an unreadable source cannot be declared at all
    try:
        cr.source_declaration(WORK / "does_not_exist.parquet", role="feature_source",
                              cutoff_valid=True, cutoff_rationale="r")
    except cr.ConstructionReceiptFailure as e:
        assert "unreadable at construction time" in str(e)
    else:                                                     # pragma: no cover - must not happen
        raise AssertionError("an unreadable source must be refused")


def test_the_producer_declares_its_target_as_an_outcome_and_keeps_it_out_of_the_features():
    c = a_fold()
    roles = {s["role"]: s for s in c.receipt["frozen_source_provenance"]["sources"]}
    assert set(roles) == {"feature_source", "outcome_source"}
    assert roles["outcome_source"]["cutoff_valid"] is False
    assert roles["feature_source"]["cutoff_valid"] is True
    assert pf.TARGET_COLUMN not in c.feature_names
    assert pf.OFFSET_COLUMN not in c.feature_names
    assert "projected_team_off_possessions" not in c.feature_names
    assert "team_pace_estimate" not in c.feature_names
    # the target IS carried, so the gate's target-leakage checks are live rather than deleted
    rep = audit_real(c)
    for k in ("target_derived", "missingness_informative", "missingness_encodes_outcome",
              "deterministic_transform_of_offset", "schema_mismatch"):
        assert k in rep["checks_enabled"], k
    assert rep["arguments"]["target"]["value_digest"] == gi.value_digest(
        c.target, label="target_values")


def test_the_outcome_mask_is_supplied_truthfully_and_adjudicated_rather_than_withheld():
    c = a_fold()
    rep = audit_real(c)
    assert rep["arguments"]["outcome_mask"]["supplied"] is True
    applied = {a["kind"] for a in rep["adjudications_applied"]}
    assert "argument_is_placeholder_default" in applied
    reason = [a["adjudication_reason"] for a in rep["adjudications_applied"]
              if a["kind"] == "argument_is_placeholder_default"][0]
    assert "constant TRUE over this universe" in reason
    # withholding it instead would have been the defect this whole module exists to refuse
    kw = pf.gate_kwargs(c)
    kw.pop("outcome_mask")
    kw["raise_on_block"] = False
    withheld = gi.audit_fold(c.frame, c.feature_names, **kw)
    assert "argument_omitted" in blocking_kinds(withheld)
    assert withheld["gate_invoked"] is False


def test_the_gate_argument_digests_the_producer_recorded_are_checked():
    c = a_fold()
    other = c.offset * 1.5
    rep = cr.verify_construction_receipt(
        c.receipt_path, frame=c.frame, feature_names=c.feature_names, experiment=pf.EXPERIMENT,
        arm=pf.ARM, fold=c.fold_id, scope="fold",
        gate_arguments={"offset": other, "target": c.target, "outcome_mask": c.outcome_mask})
    assert rep["verified"] is False
    assert "gate_argument_digest_mismatch" in {f["kind"] for f in rep["blocking"]}
    # and the gate performs the same comparison with the arguments it was actually handed
    kw = pf.gate_kwargs(c)
    kw.update(offset=other, raise_on_block=False)
    at_gate = gi.audit_fold(c.frame, c.feature_names, **kw)
    assert "construction_receipt_unverifiable" in blocking_kinds(at_gate)


def test_the_construction_kinds_are_declared_consistently():
    assert not (cr.BLOCKING & cr.INFORMATIONAL)
    gate_side = {"construction_receipt_not_read_from_disk", "construction_receipt_unverifiable"}
    assert gate_side <= gi.BLOCKING
    assert gate_side <= gi.NON_ADJUDICABLE
    assert {"producer_construction_receipt_absent", "construction_receipt_verified"} <= \
        gi.INFORMATIONAL
    assert not (gi.INFORMATIONAL & gi.BLOCKING)
    assert gi.ASSURANCE_LEVELS == ("IDENTITY_VERIFIED", "TRANSFORMATION_VERIFIED",
                                   "RAW_PROVENANCE_ASSERTED", "FAILED")
    # every construction-receipt binding field is an INPUT field of the gate receipt, so a gate
    # receipt cannot be carried across a change of construction receipt
    for k in ("construction_receipt_claimed", "construction_receipt_verified",
              "construction_receipt_digest", "construction_producer_source_sha256",
              "construction_frozen_source_manifest"):
        assert k in gi._INPUT_BINDING_FIELDS, k


def test_a_gate_receipt_cannot_be_reused_across_a_changed_construction_receipt():
    b = built()
    c, other = b["train_lt_2024"], b["train_lt_2023"]
    rec = audit_real(c)
    assert rec["passed"] is True, rec["blocking"]
    kw = pf.gate_kwargs(c)
    for k in ("adjudications", "experiment", "arm", "fold", "scope"):
        kw.pop(k, None)
    v = gi.verify_receipt(rec, c.frame, c.feature_names, experiment=pf.EXPERIMENT, arm=pf.ARM,
                          fold=c.fold_id, scope="fold", raise_on_block=False,
                          **{**kw, "construction_receipt": str(other.receipt_path)})
    assert "receipt_reuse_detected" in blocking_kinds(v)
    diverging = [x for x in v["blocking"] if x["kind"] == "receipt_reuse_detected"][0][
        "diverging_fields"]
    assert "construction_receipt_verified" in diverging or \
        "construction_receipt_digest" in diverging


# --------------------------------------------------------------------------------------------

def main() -> int:
    tests = [(n, f) for n, f in list(globals().items())
             if n.startswith("test_") and callable(f)]
    print("=" * 100)
    print("construction_receipt / possession_features — producer-emitted construction provenance")
    print(f"({len(tests)} tests; nothing is fitted, nothing is scored; the canonical artifacts are")
    print(" read-only and every perturbation runs against a temporary copy)")
    print("=" * 100)
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
    print("=" * 100)
    if ASSURANCE_OBSERVED:
        print("assurance level reached, by case:")
        for label in sorted(ASSURANCE_OBSERVED):
            level, stage1 = ASSURANCE_OBSERVED[label]
            print(f"  {label:<42} {level:<26} stage1_pass={stage1}")
        print()
        print("  The verified levels above are reached ONLY through a producer-emitted")
        print("  construction receipt read from disk and re-derived against real files.")
        print("  caller_manufactured_mapping verifies in every field it declares and still")
        print("  reports RAW_PROVENANCE_ASSERTED.")
    print("=" * 100)
    print(f"canonical artifacts after the run: {json.dumps(canonical_hashes(), indent=2)}")
    print(f"{npass} passed, {nfail} failed, {len(tests)} total")
    return 1 if nfail else 0


if __name__ == "__main__":
    raise SystemExit(main())
