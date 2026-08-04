#!/usr/bin/env python3
"""TESTS.py — validation for I12_DESIGN_DEPENDENCY_AUDIT.

Standalone runnable (pytest is not installed in this environment). ``main()`` returns 0 when every
check passes and 1 otherwise, and prints one line per check.

Three groups:

  BYTES     the three shared gates are byte-identical to their pinned digests, before and after
            everything this node runs, and this node's module cannot write to disk at all.
  SYNTHETIC unit behaviour of design_dependency_audit on constructed data where the right answer is
            known by construction — including the threshold boundary, where the module must agree
            with feature_gate's own pairwise rule to the last decimal.
  REAL      the same audit against the frozen artifacts, with every number recomputed here rather
            than read out of MEASUREMENTS.json.

Nothing here fits a model, scores an arm, or reads stage2b/SEALED_RESULTS.
"""
from __future__ import annotations

import ast
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.dont_write_bytecode = True          # never write .pyc outside this node's write scope

HERE = Path(__file__).resolve().parent
PP = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(PP))

import feature_gate as fg                                                    # noqa: E402
import design_dependency_audit as A                                          # noqa: E402

PRIOR = PP / "projected_exposure_v1" / "team_possession_prior_v1.parquet"
POSS = PP / "possessions_v2" / "possessions_raw_v2.parquet"

_FAIL: list[str] = []
_PASS: list[str] = []
MEASURED: dict = {}


def check(name: str, cond: bool, detail: str = "") -> bool:
    if cond:
        _PASS.append(name)
    else:
        _FAIL.append(f"{name}: {detail}")
    return bool(cond)


def blocking_kinds(rec: dict) -> set[str]:
    return {f["kind"] for f in rec["blocking"]}


def expect_raise(name: str, design, **kw) -> set[str]:
    try:
        A.assert_design_identified(design, **kw)
    except A.DesignDependencyFailure as exc:
        check(name, bool(exc.record), "exception carried no record")
        return {b["kind"] for b in exc.blocking}
    check(name, False, "assert_design_identified did NOT raise")
    return set()


def corr_pair(n: int, r: float, seed: int = 7) -> tuple[np.ndarray, np.ndarray]:
    """Two vectors whose SAMPLE Pearson correlation is exactly r (to floating point)."""
    rng = np.random.default_rng(seed)
    x = rng.normal(size=n)
    z = rng.normal(size=n)
    x = x - x.mean()
    z = z - z.mean()
    z = z - (z @ x) / (x @ x) * x                     # exactly orthogonal to x
    x = x / np.linalg.norm(x)
    z = z / np.linalg.norm(z)
    y = r * x + np.sqrt(1.0 - r * r) * z
    return x, y


# =============================================================================== BYTES
def t01_frozen_gates_byte_unchanged() -> None:
    st = A.frozen_gate_status()
    MEASURED["frozen_gate_live"] = st["live"]
    for name, pinned in A.FROZEN_GATE_DIGESTS.items():
        check(f"t01_{name}_byte_unchanged", st["live"][name] == pinned,
              f"live {st['live'][name]} != pinned {pinned}")
    check("t01_all_unchanged", st["all_unchanged"], str(st["changed"]))


def t02_thresholds_are_inherited_not_invented() -> None:
    check("t02_rank_tol_is_feature_gates", A.audit_design.__module__ == "design_dependency_audit"
          and fg.RANK_TOL == 1e-8, f"RANK_TOL={fg.RANK_TOL}")
    check("t02_cond_max_is_feature_gates", fg.COND_MAX == 1e6, f"COND_MAX={fg.COND_MAX}")
    check("t02_near_r2_equals_corr_threshold_squared",
          A.NEAR_R2 == 0.999 ** 2 == 0.998001, f"NEAR_R2={A.NEAR_R2}")
    # the module must not have rebound anything on the frozen gate
    check("t02_feature_gate_blocking_set_intact",
          fg.BLOCKING == {"exact_duplicate", "near_collinear", "deterministic_transform_of_offset",
                          "zero_variance", "non_finite", "impossible_scaling", "schema_mismatch",
                          "target_derived", "rank_deficient", "ill_conditioned",
                          "missingness_encodes_outcome", "missingness_informative"},
          str(sorted(fg.BLOCKING)))


def _docstrings(tree: ast.AST) -> set[int]:
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                out.add(id(body[0].value))
    return out


def t03_module_cannot_write_and_cannot_reach_sealed_results() -> None:
    """Static check on this node's own three files: no write-mode ``open``, no ``Path.write_*`` or
    frame serialisation except MEASURE.py's single write into this directory, and no executable
    string naming the sealed-results directory. Docstrings are exempt from the last check — this
    file has to be able to say what it forbids."""
    sentinel = "SEALED" + "_RESULTS"
    for fname in ("design_dependency_audit.py", "MEASURE.py", "TESTS.py"):
        src = (HERE / fname).read_text()
        tree = ast.parse(src)
        docs = _docstrings(tree)
        bad: list[str] = []
        sealed: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                    and id(node) not in docs and sentinel in node.value:
                sealed.append(f"{fname}:{node.lineno}")
            if isinstance(node, ast.Call):
                f = node.func
                nm = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
                if nm in {"write_text", "write_bytes", "to_parquet", "to_csv", "mkdir", "unlink",
                          "rmtree", "chmod"}:
                    bad.append(f"{fname}:{node.lineno}:{nm}")
                if nm == "open":
                    for a in list(node.args[1:]) + [k.value for k in node.keywords
                                                    if k.arg == "mode"]:
                        if isinstance(a, ast.Constant) and any(m in str(a.value)
                                                               for m in ("w", "a", "x", "+")):
                            bad.append(f"{fname}:{node.lineno}:open-write")
        allowed = {"MEASURE.py": 1}.get(fname, 0)     # MEASURE.py writes MEASUREMENTS.json, once
        check(f"t03_{fname}_no_unexpected_writes", len(bad) <= allowed, str(bad))
        check(f"t03_{fname}_no_sealed_path", not sealed, str(sealed))


# =========================================================================== SYNTHETIC
def t10_exact_three_term_dependency_synthetic() -> None:
    """a + b == 2*offset, built by construction. feature_gate passes X; this audit must not."""
    rng = np.random.default_rng(0)
    a = 80 + rng.normal(0, 3, 400)
    b = 80 + rng.normal(0, 3, 400)
    off = (a + b) / 2.0
    y = off + rng.normal(0, 1, 400)
    df = pd.DataFrame({"a": a, "b": b, "off": off})

    fg_rec = fg.audit(df, ["a", "b"], offset=off, target=y)
    check("t10_feature_gate_passes_the_gap", fg_rec["passed"] and not fg_rec["findings"],
          f"feature_gate findings {[f['kind'] for f in fg_rec['findings']]}")
    MEASURED["t10_feature_gate_max_pairwise_corr"] = round(
        max(abs(np.corrcoef(a, off)[0, 1]), abs(np.corrcoef(a, b)[0, 1])), 6)

    kinds = expect_raise("t10_audit_blocks",
                         A.Design(df, x=["a", "b"], offset=["off"], label="synthetic exact"),
                         target=y)
    for k in ("augmented_rank_deficient", "affine_reconstruction",
              "offset_reconstructed_by_design", "offset_reconstructed_by_x"):
        check(f"t10_kind_{k}", k in kinds, f"got {sorted(kinds)}")

    rec = A.audit_design(A.Design(df, x=["a", "b"], offset=["off"]), target=y)
    rel = rec["affine_reconstruction"]["null_space_relations"]
    check("t10_one_relation_recovered", len(rel) == 1, f"{len(rel)} relations")
    if rel:
        c = rel[0]["coefficients"]
        norm = {k: round(v / c["off"], 6) for k, v in c.items()}
        check("t10_relation_is_a_plus_b_minus_2off",
              norm["a"] == norm["b"] == -0.5 and norm["off"] == 1.0, str(norm))
        check("t10_relation_exact", rel[0]["max_abs_deviation"] < 1e-9,
              str(rel[0]["max_abs_deviation"]))
        check("t10_minimal_subset_is_the_pair",
              rec["offset_reconstruction"]["off"]["minimal_reconstructing_subset"]["columns"]
              == ["a", "b"], str(rec["offset_reconstruction"]["off"]))
    check("t10_slope_freedom_flag", rec["grants_offset_slope_freedom"] is True, "")


def t11_clean_design_passes() -> None:
    """No false positive: an orthogonal, well-conditioned design must pass cleanly."""
    rng = np.random.default_rng(1)
    n = 500
    off = 80 + rng.normal(0, 3, n)
    x1 = rng.normal(0, 1, n)
    x2 = rng.normal(0, 1, n)
    nu = rng.normal(0, 1, n)
    y = off + 0.4 * x1 + rng.normal(0, 1, n)
    df = pd.DataFrame({"off": off, "x1": x1, "x2": x2, "nu": nu})
    rec = A.audit_design(A.Design(df, x=["x1", "x2"], offset=["off"], nuisance=["nu"]), target=y)
    check("t11_clean_passes", rec["passed"], str(sorted(blocking_kinds(rec))))
    check("t11_full_rank", rec["augmented_rank"]["full_rank"], str(rec["augmented_rank"]))
    check("t11_no_slope_freedom", rec["grants_offset_slope_freedom"] is False, "")
    MEASURED["t11_condition_number"] = round(rec["augmented_rank"]["condition_number"], 6)


def t12_threshold_boundary_agrees_with_feature_gate() -> None:
    """One regressor: R^2 == r^2, so this module's NEAR_R2 and feature_gate's corr_threshold must
    fire on exactly the same inputs. Checked on both sides of 0.999."""
    for r, should_block in ((0.9991, True), (0.9989, False)):
        x, o = corr_pair(600, r)
        df = pd.DataFrame({"x": 50 + 3 * x, "off": 80 + 4 * o})
        emp_r = float(np.corrcoef(df.x, df.off)[0, 1])
        MEASURED[f"t12_empirical_corr_{r}"] = round(emp_r, 9)
        try:
            fg.audit(df, ["x"], offset=df.off.to_numpy(float))
            fg_blocked = False
        except fg.FeatureGateFailure:
            fg_blocked = True
        rec = A.audit_design(A.Design(df, x=["x"], offset=["off"]), run_feature_gate=False)
        mine = "candidate_affine_in_offset" in blocking_kinds(rec)
        check(f"t12_feature_gate_r{r}", fg_blocked is should_block, f"fg_blocked={fg_blocked}")
        check(f"t12_audit_r{r}", mine is should_block, f"audit_blocked={mine}")
        check(f"t12_agreement_r{r}", mine == fg_blocked, f"{mine} vs {fg_blocked}")
        MEASURED[f"t12_r2_on_offset_{r}"] = rec["candidate_vs_offset"]["x"]["r2_on_offset"]
        if not should_block:
            check("t12_partial_is_report_only",
                  "offset_partially_explained" in rec["finding_kinds"] and rec["passed"],
                  str(rec["finding_kinds"]))


def t13_nuisance_block_attribution() -> None:
    """An innocent X does not make the design innocent: the nuisance block alone can reconstruct
    the offset, and the finding must name the nuisance block."""
    rng = np.random.default_rng(2)
    n = 400
    n1 = rng.normal(0, 1, n)
    n2 = rng.normal(0, 1, n)
    off = 2 * n1 - 3 * n2 + 10
    df = pd.DataFrame({"x": rng.normal(0, 1, n), "n1": n1, "n2": n2, "off": off})
    rec = A.audit_design(A.Design(df, x=["x"], offset=["off"], nuisance=["n1", "n2"]))
    kinds = blocking_kinds(rec)
    check("t13_by_nuisance", "offset_reconstructed_by_nuisance" in kinds, str(sorted(kinds)))
    check("t13_not_by_x", "offset_reconstructed_by_x" not in kinds, str(sorted(kinds)))
    check("t13_x_itself_clean",
          rec["candidate_vs_offset"]["x"]["r2_on_offset"] < 0.5,
          str(rec["candidate_vs_offset"]))


def t14_multi_column_offset_sum_is_audited() -> None:
    """A two-term offset (log exposure + log D) enters as its SUM; reconstructing the SUM is what
    grants the free slope, so the sum must be audited even when neither term alone is spanned."""
    rng = np.random.default_rng(3)
    n = 400
    o1 = rng.normal(0, 1, n)
    o2 = rng.normal(0, 1, n)
    s = o1 + o2
    x1 = s + rng.normal(0, 1e-9, n)          # spans the SUM, not either term
    df = pd.DataFrame({"o1": o1, "o2": o2, "x1": x1})
    rec = A.audit_design(A.Design(df, x=["x1"], offset=["o1", "o2"]))
    rr = rec["offset_reconstruction"]
    check("t14_sum_audited", A.OFFSET_SUM in rr, str(list(rr)))
    check("t14_sum_reconstructed", rr[A.OFFSET_SUM]["r2_on_design"] >= A.NEAR_R2,
          str(rr[A.OFFSET_SUM]))
    check("t14_neither_term_alone", rr["o1"]["r2_on_design"] < A.NEAR_R2
          and rr["o2"]["r2_on_design"] < A.NEAR_R2,
          f'o1={rr["o1"]["r2_on_design"]} o2={rr["o2"]["r2_on_design"]}')
    check("t14_blocks", not rec["passed"], "")


def t15_fold_local_degeneracy() -> None:
    """Pooled healthy, fold degenerate — GATE_INVOCATION_CONTRACT section 4. The pooled design is
    full rank; one fold has a constant column."""
    rng = np.random.default_rng(4)
    n = 600
    fold = np.repeat([1, 2, 3], n // 3)
    # constant inside fold 1 only; varies pooled and inside folds 2 and 3
    flag = np.where(fold == 1, 0.0, rng.normal(0, 1, n))
    df = pd.DataFrame({"off": 80 + rng.normal(0, 3, n), "x": rng.normal(0, 1, n),
                       "flag": flag, "fold": fold, "cluster": np.arange(n) // 2})
    rec = A.audit_design(A.Design(df, x=["x", "flag"], offset=["off"], fold="fold",
                                  cluster="cluster"))
    check("t15_pooled_full_rank", rec["augmented_rank"]["full_rank"], str(rec["augmented_rank"]))
    kinds = blocking_kinds(rec)
    check("t15_fold_zero_variance", "fold_local_zero_variance" in kinds, str(sorted(kinds)))
    check("t15_fold_named", rec["folds"]["1"]["zero_variance_columns"] == ["flag"],
          str(rec["folds"]["1"]))
    check("t15_other_folds_clean",
          rec["folds"]["2"]["zero_variance_columns"] == []
          and rec["folds"]["3"]["zero_variance_columns"] == [], "")
    check("t15_no_cluster_split", rec["cluster_fold_check"]["n_clusters_split"] == 0,
          str(rec["cluster_fold_check"]))

    # and a design whose clusters DO straddle folds must be caught
    df2 = df.assign(cluster=np.arange(n) % 100)
    rec2 = A.audit_design(A.Design(df2, x=["x"], offset=["off"], fold="fold", cluster="cluster"))
    check("t15_cluster_split_caught", "cluster_split_across_folds" in blocking_kinds(rec2),
          str(sorted(blocking_kinds(rec2))))


def t16_adjudication_semantics() -> None:
    rng = np.random.default_rng(5)
    n = 300
    a = rng.normal(0, 1, n)
    b = rng.normal(0, 1, n)
    df = pd.DataFrame({"a": a, "b": b, "off": (a + b) / 2})
    des = A.Design(df, x=["a", "b"], offset=["off"])
    base = A.audit_design(des)
    adj = A.audit_design(des, adjudicated={
        "augmented_rank_deficient": "adjudicated for this unit test only",
        "affine_reconstruction": "adjudicated for this unit test only",
        "offset_reconstructed_by_design": "adjudicated for this unit test only",
        "offset_reconstructed_by_x": "adjudicated for this unit test only"})
    check("t16_base_blocks", not base["passed"], "")
    check("t16_adjudicated_leaves_blocking", adj["passed"], str(sorted(blocking_kinds(adj))))
    check("t16_adjudicated_stays_in_findings",
          base["finding_kinds"] == adj["finding_kinds"],
          f"{base['finding_kinds']} vs {adj['finding_kinds']}")
    check("t16_adjudication_recorded", set(adj["adjudicated"]) and
          all(isinstance(v, str) for v in adj["adjudicated"].values()), "")
    empty = A.audit_design(des, adjudicated={"augmented_rank_deficient": "  "})
    check("t16_reasonless_adjudication_blocks",
          "adjudication_without_reason" in blocking_kinds(empty)
          and "augmented_rank_deficient" in blocking_kinds(empty),
          str(sorted(blocking_kinds(empty))))


def t17_degenerate_inputs() -> None:
    rng = np.random.default_rng(6)
    n = 200
    df = pd.DataFrame({"x": rng.normal(0, 1, n), "off": 80 + rng.normal(0, 3, n),
                       "const": np.ones(n), "zero_off": np.zeros(n),
                       "text": ["a"] * n, "nanny": np.where(np.arange(n) < 50, np.nan,
                                                            rng.normal(0, 1, n))})
    r_missing = A.audit_design(A.Design(df, x=["nope"], offset=["off"]))
    check("t17_missing_column", "column_missing_from_frame" in blocking_kinds(r_missing), "")
    r_text = A.audit_design(A.Design(df, x=["text"], offset=["off"]))
    check("t17_non_numeric", "column_not_numeric" in blocking_kinds(r_text), "")
    r_nooff = A.audit_design(A.Design(df, x=["x"]))
    check("t17_offset_block_empty", "offset_block_empty" in blocking_kinds(r_nooff), "")
    r_zero = A.audit_design(A.Design(df, x=["x"], offset=["zero_off"]))
    check("t17_placeholder_offset", "offset_is_placeholder" in blocking_kinds(r_zero), "")
    r_const = A.audit_design(A.Design(df, x=["x", "const"], offset=["off"]))
    check("t17_zero_variance_column", "design_column_zero_variance" in blocking_kinds(r_const), "")
    r_nan = A.audit_design(A.Design(df, x=["x", "nanny"], offset=["off"]))
    check("t17_complete_case_counted",
          r_nan["n_complete_rows"] == 150 and r_nan["n_rows"] == 200, str(r_nan["n_complete_rows"]))
    check("t17_row_loss_is_report_only",
          "complete_case_row_loss" in r_nan["finding_kinds"]
          and "complete_case_row_loss" not in blocking_kinds(r_nan), "")
    r_small = A.audit_design(A.Design(df.head(5), x=["x"], offset=["off"]))
    check("t17_insufficient_rows", "insufficient_complete_rows" in blocking_kinds(r_small), "")
    r_dup = A.audit_design(A.Design(df, x=["x"], offset=["off"], nuisance=["x"]))
    check("t17_block_membership", "block_membership_ambiguous" in blocking_kinds(r_dup), "")


def t18_determinism_and_receipt() -> None:
    rng = np.random.default_rng(8)
    n = 300
    a = rng.normal(0, 1, n)
    b = rng.normal(0, 1, n)
    df = pd.DataFrame({"a": a, "b": b, "off": (a + b) / 2})
    r1 = A.audit_design(A.Design(df, x=["a", "b"], offset=["off"], label="L"))
    r2 = A.audit_design(A.Design(df, x=["a", "b"], offset=["off"], label="L"))
    check("t18_receipt_stable", r1["receipt_sha256"] == r2["receipt_sha256"],
          f'{r1["receipt_sha256"]} != {r2["receipt_sha256"]}')
    r3 = A.audit_design(A.Design(df, x=["b", "a"], offset=["off"], label="L"))
    check("t18_order_invariant_kinds", blocking_kinds(r1) == blocking_kinds(r3),
          f"{sorted(blocking_kinds(r1))} vs {sorted(blocking_kinds(r3))}")
    rel1 = r1["affine_reconstruction"]["null_space_relations"][0]["coefficients"]
    rel3 = r3["affine_reconstruction"]["null_space_relations"][0]["coefficients"]
    norm = lambda c: {k: round(v / c["off"], 6) for k, v in c.items()}                 # noqa: E731
    check("t18_relation_order_invariant", norm(rel1) == norm(rel3), f"{norm(rel1)} {norm(rel3)}")


def t19_augmented_rank_is_feature_gates_own_arithmetic() -> None:
    """The rank/condition numbers must come from feature_gate.design_rank_report itself, applied to
    the wider frame — not from a re-implementation that could drift from the frozen gate."""
    rng = np.random.default_rng(9)
    n = 350
    a = rng.normal(0, 1, n)
    b = rng.normal(0, 1, n)
    df = pd.DataFrame({"a": a, "b": b, "nu": rng.normal(0, 1, n), "off": (a + b) / 2})
    names = ["a", "b", "off", "nu"]
    rec = A.audit_design(A.Design(df, x=["a", "b"], offset=["off"], nuisance=["nu"]))
    direct = fg.design_rank_report(df, names)
    got = rec["augmented_rank"]
    check("t19_produced_by", got.get("produced_by") == "feature_gate.design_rank_report", "")
    for k in ("numerical_rank", "n_features", "full_rank", "condition_number", "singular_values"):
        check(f"t19_{k}_identical", got[k] == direct[k], f"{got[k]} != {direct[k]}")
    # and the block order the audit uses is X, offset, nuisance
    check("t19_block_order", rec["design"]["blocks"] == {"x": ["a", "b"], "offset": ["off"],
                                                         "nuisance": ["nu"]}, "")


# ================================================================================ REAL
def build_panel() -> pd.DataFrame:
    prior = pd.read_parquet(PRIOR)
    s = prior.groupby("game_id")["team_pace_estimate"].transform("sum")
    prior = prior.assign(own_est=prior.team_pace_estimate, opp_est=s - prior.team_pace_estimate)
    d = prior[prior.pace_resolved].copy()
    d = d[np.isfinite(d.own_est) & np.isfinite(d.opp_est)
          & np.isfinite(d.projected_team_off_possessions)].reset_index(drop=True)
    poss = pd.read_parquet(POSS, columns=["game_id", "offense_team_id", "period"])
    gm = poss.groupby("game_id")["period"].max().rename("max_period").reset_index()
    gm["game_minutes"] = 40 + 5 * np.maximum(0, gm.max_period - 4)
    nn = (poss.groupby(["game_id", "offense_team_id"]).size().rename("n_off_poss").reset_index()
          .rename(columns={"offense_team_id": "team_id"}))
    nn = nn.merge(gm[["game_id", "game_minutes"]], on="game_id", validate="m:1")
    nn["target"] = nn.n_off_poss * 40.0 / nn.game_minutes
    d = d.merge(nn[["game_id", "team_id", "target"]], on=["game_id", "team_id"],
                how="left", validate="1:1")
    d["contrast_own_minus_opp"] = d.own_est - d.opp_est
    for lvl in sorted(d.pace_source.unique()):
        d[f"src_{lvl}"] = (d.pace_source == lvl).astype(float)
    return d


def t20_real_universe(d: pd.DataFrame) -> None:
    MEASURED["real_rows"] = int(len(d))
    MEASURED["real_clusters"] = int(d.game_id.nunique())
    check("t20_rows_2982", len(d) == 2982, str(len(d)))
    check("t20_clusters_1491", d.game_id.nunique() == 1491, str(d.game_id.nunique()))
    dev = (d.own_est + d.opp_est) - 2 * d.projected_team_off_possessions
    MEASURED["real_identity_max_abs_deviation"] = float(np.abs(dev).max())
    check("t20_identity_exact", float(np.abs(dev).max()) == 0.0, str(float(np.abs(dev).max())))


def t21_real_gap_and_closure(d: pd.DataFrame) -> None:
    off = d.projected_team_off_possessions.to_numpy(float)
    y = d.target.to_numpy(float)
    fg_rec = fg.audit(d, ["own_est", "opp_est"], offset=off, target=y)
    MEASURED["real_feature_gate_passed"] = bool(fg_rec["passed"])
    MEASURED["real_feature_gate_findings"] = [f["kind"] for f in fg_rec["findings"]]
    check("t21_feature_gate_still_passes_S5", fg_rec["passed"] and not fg_rec["findings"],
          str(MEASURED["real_feature_gate_findings"]))
    check("t21_feature_gate_rank_saw_only_two_columns",
          fg_rec["design_rank"]["n_features"] == 2 and fg_rec["design_rank"]["full_rank"], "")

    des = A.Design(d, x=["own_est", "opp_est"], offset=["projected_team_off_possessions"],
                   fold="season", cluster="game_id", label="A")
    kinds = expect_raise("t21_audit_blocks_S5", des, target=y)
    for k in ("augmented_rank_deficient", "affine_reconstruction",
              "offset_reconstructed_by_design", "offset_reconstructed_by_x",
              "fold_local_rank_deficient", "fold_local_offset_reconstructed"):
        check(f"t21_kind_{k}", k in kinds, str(sorted(kinds)))
    rec = A.audit_design(des, target=y)
    MEASURED["real_augmented_rank"] = (rec["augmented_rank"]["numerical_rank"],
                                       rec["augmented_rank"]["n_features"])
    MEASURED["real_augmented_condition_number"] = rec["augmented_rank"]["condition_number"]
    check("t21_rank_2_of_3", MEASURED["real_augmented_rank"] == (2, 3),
          str(MEASURED["real_augmented_rank"]))
    check("t21_condition_above_ceiling",
          rec["augmented_rank"]["condition_number"] > fg.COND_MAX,
          str(rec["augmented_rank"]["condition_number"]))
    rel = rec["affine_reconstruction"]["null_space_relations"]
    check("t21_one_relation", len(rel) == 1, str(len(rel)))
    if rel:
        c = rel[0]["coefficients"]
        norm = {k: round(v / c["projected_team_off_possessions"], 6) for k, v in c.items()}
        MEASURED["real_recovered_relation"] = rel[0]["expression"]
        MEASURED["real_relation_max_abs_deviation"] = rel[0]["max_abs_deviation"]
        check("t21_relation_is_S5",
              norm["own_est"] == norm["opp_est"] == -0.5
              and norm["projected_team_off_possessions"] == 1.0, str(norm))
        check("t21_relation_exact_in_data_units", rel[0]["max_abs_deviation"] <= 1e-12,
              str(rel[0]["max_abs_deviation"]))
    r2 = rec["offset_reconstruction"]["projected_team_off_possessions"]
    MEASURED["real_r2_offset_on_design"] = r2["r2_on_design"]
    check("t21_r2_exactly_one", r2["r2_on_design"] == 1.0, str(r2["r2_on_design"]))
    check("t21_minimal_subset",
          r2["minimal_reconstructing_subset"]["columns"] == ["own_est", "opp_est"], str(r2))
    check("t21_every_fold_blocked", len(rec["folds"]) == 6
          and all(not v["rank"]["full_rank"] for v in rec["folds"].values()),
          str({k: v["rank"]["full_rank"] for k, v in rec["folds"].items()}))
    check("t21_no_cluster_split", rec["cluster_fold_check"]["n_clusters_split"] == 0,
          str(rec["cluster_fold_check"]))


def t22_real_nuisance_variant_and_clean_variant(d: pd.DataFrame) -> None:
    y = d.target.to_numpy(float)
    b = A.audit_design(A.Design(d, x=["own_est"], nuisance=["opp_est"],
                                offset=["projected_team_off_possessions"],
                                fold="season", cluster="game_id"), target=y)
    check("t22_B_blocks", not b["passed"], "")
    check("t22_B_x_alone_innocent",
          abs(b["offset_reconstruction"]["projected_team_off_possessions"]["r2_on_x"]
              - 0.598834643468) < 1e-9,
          str(b["offset_reconstruction"]))
    check("t22_B_feature_gate_sees_one_feature",
          b["feature_gate_record"]["design_rank"]["n_features"] == 1, "")

    c = A.audit_design(A.Design(d, x=["contrast_own_minus_opp"],
                                offset=["projected_team_off_possessions"],
                                fold="season", cluster="game_id"), target=y)
    MEASURED["real_clean_design_r2_offset"] = (
        c["offset_reconstruction"]["projected_team_off_possessions"]["r2_on_design"])
    check("t22_C_passes", c["passed"], str(sorted(blocking_kinds(c))))
    check("t22_C_no_false_positive_folds",
          all(v["rank"]["full_rank"] for v in c["folds"].values()), str(c["folds"]))


def t23_real_tier_dummy_designs(d: pd.DataFrame) -> None:
    y = d.target.to_numpy(float)
    levels = [f"src_{s}" for s in sorted(d.pace_source.unique())]
    full = A.audit_design(A.Design(d, x=["contrast_own_minus_opp"],
                                   offset=["projected_team_off_possessions"], nuisance=levels,
                                   fold="season", cluster="game_id"), target=y)
    check("t23_full_dummy_set_rank_deficient",
          "augmented_rank_deficient" in blocking_kinds(full), str(sorted(blocking_kinds(full))))
    dropped = A.audit_design(A.Design(d, x=["contrast_own_minus_opp"],
                                      offset=["projected_team_off_possessions"],
                                      nuisance=levels[1:], fold="season", cluster="game_id"),
                             target=y)
    check("t23_reference_dropped_pooled_full_rank",
          dropped["augmented_rank"]["full_rank"], str(dropped["augmented_rank"]))
    degenerate = sorted(k for k, v in dropped["folds"].items() if not v["rank"]["full_rank"])
    MEASURED["real_tier_folds_rank_deficient_after_dropping_reference"] = degenerate
    MEASURED["real_tier_fold_zero_variance"] = {k: v["zero_variance_columns"]
                                                for k, v in dropped["folds"].items()}
    check("t23_pooled_healthy_fold_degenerate",
          degenerate == ["2021", "2022", "2023", "2024"], str(degenerate))
    check("t23_2021_zero_variance",
          dropped["folds"]["2021"]["zero_variance_columns"] == ["src_team_window_prior_season"],
          str(dropped["folds"]["2021"]))


def t24_real_duplicate_tier_encoding(d: pd.DataFrame) -> None:
    y = d.target.to_numpy(float)
    levels = [f"src_{s}" for s in sorted(d.pace_source.unique())]
    rec = A.audit_design(A.Design(d, x=["contrast_own_minus_opp"],
                                  offset=["projected_team_off_possessions"],
                                  nuisance=levels[1:] + ["pace_level"],
                                  fold="season", cluster="game_id"), target=y)
    check("t24_duplicate_encoding_blocked",
          "augmented_rank_deficient" in blocking_kinds(rec), str(sorted(blocking_kinds(rec))))
    bij = bool(d.groupby("pace_source")["pace_level"].nunique().max() == 1
               and d.groupby("pace_level")["pace_source"].nunique().max() == 1)
    MEASURED["real_pace_level_bijective_with_pace_source"] = bij
    check("t24_bijection_measured", bij, "pace_level is not a bijection of pace_source")


def t25_measurements_file_matches_a_fresh_run(d: pd.DataFrame) -> None:
    p = HERE / "MEASUREMENTS.json"
    if not p.exists():
        check("t25_measurements_present", False, "MEASUREMENTS.json missing — run MEASURE.py")
        return
    M = json.loads(p.read_text())
    check("t25_rows", M["panel_rows"] == len(d), str(M["panel_rows"]))
    check("t25_clusters", M["panel_game_clusters"] == d.game_id.nunique(),
          str(M["panel_game_clusters"]))
    check("t25_module_digest",
          M["module_sha256"] == hashlib.sha256(
              (HERE / "design_dependency_audit.py").read_bytes()).hexdigest(),
          "MEASUREMENTS.json was produced by different module bytes — rerun MEASURE.py")
    check("t25_gate_digests_recorded",
          M["frozen_gate_status"]["live"] == A.FROZEN_GATE_DIGESTS,
          str(M["frozen_gate_status"]["live"]))
    check("t25_p25_agreement",
          all(v.get("agrees") for v in M["p25_agreement_on_shared_numbers"].values()),
          json.dumps(M["p25_agreement_on_shared_numbers"]))


def t26_gates_unchanged_after_everything() -> None:
    live = A.frozen_gate_digests()
    for name, pinned in A.FROZEN_GATE_DIGESTS.items():
        check(f"t26_{name}_unchanged_after_run", live[name] == pinned,
              f"{live[name]} != {pinned}")


def main() -> int:
    t01_frozen_gates_byte_unchanged()
    t02_thresholds_are_inherited_not_invented()
    t03_module_cannot_write_and_cannot_reach_sealed_results()

    t10_exact_three_term_dependency_synthetic()
    t11_clean_design_passes()
    t12_threshold_boundary_agrees_with_feature_gate()
    t13_nuisance_block_attribution()
    t14_multi_column_offset_sum_is_audited()
    t15_fold_local_degeneracy()
    t16_adjudication_semantics()
    t17_degenerate_inputs()
    t18_determinism_and_receipt()
    t19_augmented_rank_is_feature_gates_own_arithmetic()

    d = build_panel()
    t20_real_universe(d)
    t21_real_gap_and_closure(d)
    t22_real_nuisance_variant_and_clean_variant(d)
    t23_real_tier_dummy_designs(d)
    t24_real_duplicate_tier_encoding(d)
    t25_measurements_file_matches_a_fresh_run(d)
    t26_gates_unchanged_after_everything()

    print(f"passed {len(_PASS)}  failed {len(_FAIL)}")
    for f in _FAIL:
        print("FAIL  " + f)
    print(json.dumps(MEASURED, indent=1, default=str))
    return 1 if _FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
