#!/usr/bin/env python3
"""S32B_K0_CONTRACT/MEASURE.py -- every number, column name and digest cited by
K0_MATCHED_SCHEMA_SCORE.json and REPORT.md, re-derived from the frozen artifacts.

Read-only everywhere except this node's own directory. Never touches any
SEALED_RESULTS directory. Deliberately does NOT read any metric/performance
value out of score_baselines.json: only the `producer` and `inputs` provenance
blocks are extracted (S30 section 4: floor values are referenced, not quoted).

Column-digest canonicalisation (the byte-pin convention this node freezes):
  * rows filtered to one `method` value;
  * sorted ascending by `game_id` (int64 sort when the dtype is integral,
    lexicographic on str(game_id) otherwise), ties impossible (game_id unique
    per method -- asserted);
  * each value canonicalised: floats via repr(float(v)) (NaN -> 'nan'),
    integers via str(int(v)), pandas timestamps via .isoformat(), everything
    else via str(v);
  * joined with U+001F, encoded UTF-8, sha256 hex digest.

Run:  python experiments/player_program/stage3_score/S32B_K0_CONTRACT/MEASURE.py
Writes MEASUREMENTS.json alongside itself. Exit 0 on success, 1 on any
verification failure (a pinned hash not matching bytes on disk).
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]  # worktree root, machine-independent (verifier finding 5)
NODE = ROOT / "experiments/player_program/stage3_score/S32B_K0_CONTRACT"

ROWS_PATH = ROOT / "experiments/market_program/SCORE_BASELINES/score_baseline_rows.parquet"
BUILDER_PATH = ROOT / "experiments/market_program/SCORE_BASELINES/build_score_baselines.py"
BASELINES_JSON_PATH = ROOT / "experiments/market_program/SCORE_BASELINES/score_baselines.json"
GATE_PATH = ROOT / "experiments/player_program/comparison_gate.py"
P26_SCHEMA_PATH = ROOT / "experiments/player_program/stage2b/P26_ARM_SPECIFIC_K0_CONTRACT/K0_MATCHED_SCHEMA.json"
S30_MD_PATH = ROOT / "experiments/player_program/stage3_score/S30_TARGET_CONTRACT/CYCLE2_TARGET_CONTRACT.md"
S30_JSON_PATH = ROOT / "experiments/player_program/stage3_score/S30_TARGET_CONTRACT/TARGET_CONTRACT.json"

# The S30 machine summary's pins, checked against bytes on disk below.
S30_PIN_ROWS_PARQUET = "5d1fc4c9af2334a6edd6ddffab91fe7cff5596578d9995937859a86cfc1e1452"
S30_PIN_FULL_EDITION = "87cd094af1dbc3af49d77d6a1d745f1f728a7d40214bb26bb60edbffd67d1710"


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def canon(v) -> str:
    if v is None:
        return "None"
    if isinstance(v, (float, np.floating)):
        return repr(float(v))
    if isinstance(v, (bool, np.bool_)):
        return str(bool(v))
    if isinstance(v, (int, np.integer)):
        return str(int(v))
    if isinstance(v, pd.Timestamp):
        return v.isoformat()
    return str(v)


def column_digest(series: pd.Series) -> dict:
    vals = [canon(v) for v in series.tolist()]
    h = hashlib.sha256("\x1f".join(vals).encode("utf-8")).hexdigest()
    return {"sha256": h, "n_values": len(vals),
            "n_nan": int(pd.isna(series).sum())}


def main() -> int:
    failures: list[str] = []
    meas: dict = {"node": "S32B_K0_CONTRACT", "measure_script": "MEASURE.py"}

    # ---- file digests -------------------------------------------------------
    meas["file_sha256"] = {
        "score_baseline_rows.parquet": sha256_file(ROWS_PATH),
        "build_score_baselines.py": sha256_file(BUILDER_PATH),
        "score_baselines.json": sha256_file(BASELINES_JSON_PATH),
        "comparison_gate.py": sha256_file(GATE_PATH),
        "P26_K0_MATCHED_SCHEMA.json": sha256_file(P26_SCHEMA_PATH),
        "S30_CYCLE2_TARGET_CONTRACT.md": sha256_file(S30_MD_PATH),
        "S30_TARGET_CONTRACT.json": sha256_file(S30_JSON_PATH),
    }

    # ---- verify the S30 pins against bytes on disk --------------------------
    pin_checks = {
        "score_baseline_rows.parquet_matches_S30_pin":
            meas["file_sha256"]["score_baseline_rows.parquet"] == S30_PIN_ROWS_PARQUET,
        "CYCLE2_TARGET_CONTRACT.md_matches_S30_json_pin":
            meas["file_sha256"]["S30_CYCLE2_TARGET_CONTRACT.md"] == S30_PIN_FULL_EDITION,
    }
    meas["pin_checks"] = pin_checks
    for k, ok in pin_checks.items():
        if not ok:
            failures.append(f"PIN MISMATCH: {k}")

    # ---- the frozen gate's machine dimensions, from the imported module -----
    sys.path.insert(0, str(ROOT / "experiments/player_program"))
    import comparison_gate as cg  # noqa: E402
    meas["comparison_gate"] = {
        "n_dimensions": len(cg.DIMENSIONS),
        "dimensions": list(cg.DIMENSIONS),
        "layer_a_strict_prose_names": sorted(cg.LAYER_A_STRICT.keys()),
        "k0_blocks_on_substantive_features":
            "k0_has_substantive_features" in cg.BLOCKING,
        "none_sentinel": cg.NONE,
    }
    if len(cg.DIMENSIONS) != 17:
        failures.append("comparison_gate.DIMENSIONS != 17")

    # ---- the builder's resolved parameters, from the imported module --------
    import importlib.util
    spec = importlib.util.spec_from_file_location("build_score_baselines", BUILDER_PATH)
    bsb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bsb)  # module-level constants only; main() is guarded
    meas["builder_resolved_parameters"] = {
        "EFF_EWMA_SPAN": bsb.EFF_EWMA_SPAN,
        "EFF_ALPHA": bsb.EFF_ALPHA,
        "EFF_MIN_HISTORY": bsb.EFF_MIN_HISTORY,
        "BLEND": bsb.BLEND,
        "MODEL_VERSIONS": dict(bsb.MODEL_VERSIONS),
        "EVIDENCE_CLASS": bsb.EVIDENCE_CLASS,
    }

    # ---- provenance blocks ONLY from score_baselines.json (no metrics) ------
    with open(BASELINES_JSON_PATH, "r", encoding="utf-8") as f:
        sb = json.load(f)
    meas["score_baselines_provenance_only"] = {
        "producer_path": sb["producer"]["path"],
        "producer_sha256": sb["producer"]["sha256"],
        "inputs": {k: {"path": v["path"], "sha256": v["sha256"]}
                   for k, v in sb["inputs"].items()},
        "note": ("ONLY producer+inputs extracted; no metric value was read out "
                 "of this file by this node (S30 section 4 discipline)."),
    }
    if sb["producer"]["sha256"] != meas["file_sha256"]["build_score_baselines.py"]:
        failures.append("builder source on disk != producer sha256 recorded in "
                        "score_baselines.json (the builder was edited after the "
                        "frozen store was produced)")
    meas["pin_checks"]["builder_on_disk_matches_recorded_producer"] = (
        sb["producer"]["sha256"] == meas["file_sha256"]["build_score_baselines.py"])

    # input artifacts on disk vs the store's recorded input hashes
    input_disk = {}
    for key, rec in sb["inputs"].items():
        p = ROOT / rec["path"]
        if p.exists():
            d = sha256_file(p)
            input_disk[key] = {"path": rec["path"], "sha256_on_disk": d,
                               "matches_recorded": d == rec["sha256"]}
            if d != rec["sha256"]:
                failures.append(f"input artifact drifted: {key}")
        else:
            input_disk[key] = {"path": rec["path"], "sha256_on_disk": None,
                               "matches_recorded": False}
            failures.append(f"input artifact missing on disk: {key}")
    meas["input_artifacts_on_disk"] = input_disk

    # ---- the frozen composite store: columns, coverage, column digests ------
    df = pd.read_parquet(ROWS_PATH)
    meas["score_baseline_rows"] = {
        "n_rows_total": int(len(df)),
        "columns_in_file_order": list(df.columns),
        "dtypes": {c: str(df[c].dtype) for c in df.columns},
        "methods": sorted(df["method"].unique().tolist()),
        "game_id_dtype": str(df["game_id"].dtype),
    }

    per_method: dict = {}
    for method, sub in df.groupby("method"):
        if pd.api.types.is_integer_dtype(sub["game_id"]):
            sub = sub.sort_values("game_id", kind="mergesort")
            sort_rule = "int64 ascending"
        else:
            sub = sub.assign(_k=sub["game_id"].astype(str)).sort_values(
                "_k", kind="mergesort").drop(columns=["_k"])
            sort_rule = "lexicographic on str(game_id) ascending"
        if sub["game_id"].nunique() != len(sub):
            failures.append(f"game_id not unique within method {method}")
        seasons = {}
        for s, ss in sub.groupby("season"):
            seasons[str(int(s))] = {
                "n_games": int(len(ss)),
                "n_p_home_nonnull": int(ss["p_home"].notna().sum())
                if "p_home" in ss.columns else None,
            }
        per_method[method] = {
            "n_rows": int(len(sub)),
            "n_distinct_game_ids": int(sub["game_id"].nunique()),
            "sort_rule": sort_rule,
            "per_season": seasons,
            "column_digests": {c: column_digest(sub[c]) for c in sub.columns},
        }
    meas["per_method"] = per_method

    # sanity: composite pred_total == pred_home + pred_away to fp tolerance
    comp = df[df["method"] == "composite_pace_x_eff_v1"]
    if len(comp):
        tot_gap = float(np.nanmax(np.abs(
            comp["pred_home"] + comp["pred_away"] - comp["pred_total"])))
        mar_gap = float(np.nanmax(np.abs(
            comp["pred_home"] - comp["pred_away"] - comp["pred_margin"])))
        meas["composite_identities"] = {
            "max_abs_pred_home_plus_away_minus_total": tot_gap,
            "max_abs_pred_home_minus_away_minus_margin": mar_gap,
        }
    else:
        failures.append("no composite_pace_x_eff_v1 rows in the frozen store")

    # base-universe context (S30 section 2): 1491 clusters / 2982 team-game rows
    meas["s30_base_universe_reference"] = {"game_clusters": 1491,
                                          "team_game_rows": 2982}
    if len(comp):
        meas["composite_coverage_vs_base_universe"] = {
            "composite_games": int(comp["game_id"].nunique()),
            "fraction_of_1491": round(comp["game_id"].nunique() / 1491.0, 6),
            "composite_games_with_p_home": int(comp["p_home"].notna().sum()),
            "fraction_with_p_home_of_1491":
                round(float(comp["p_home"].notna().sum()) / 1491.0, 6),
        }

    meas["verification_failures"] = failures
    out = NODE / "MEASUREMENTS.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(meas, f, indent=2, default=str)
    print(f"wrote {out}")
    print(f"failures: {len(failures)}")
    for msg in failures:
        print("  FAIL:", msg)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
