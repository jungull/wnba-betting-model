#!/usr/bin/env python3
"""MEASURE.py -- re-derivation of every figure P26 cites.

Nothing here is asserted from the V2 stop-condition packet. Every number below is computed from
the frozen artifacts named in EVIDENCE_PACKET_V2.sources, using the SAME construction as
stage2a/build_evidence_packet.py:realised_pace() (regulation-equivalent = n_off_poss * 40 /
game_minutes, game_minutes = 40 + 5*max(0, max_period-4)).

Read-only. Writes MEASUREMENTS.json into this node's own directory and nothing else.

Run:  python experiments/player_program/stage2b/P26_ARM_SPECIFIC_K0_CONTRACT/MEASURE.py
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PP = HERE.parents[1]                       # experiments/player_program
PRIOR = PP / "projected_exposure_v1" / "team_possession_prior_v1.parquet"
POSS = PP / "possessions_v2" / "possessions_raw_v2.parquet"
PACKET = PP / "stage2a" / "EVIDENCE_PACKET_V2.json"
REGULATION_MIN = 40.0


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def realised_pace() -> pd.DataFrame:
    p = pd.read_parquet(POSS, columns=["game_id", "season_type", "period", "offense_team_id"])
    n = (p.groupby(["game_id", "offense_team_id"]).size().rename("n_off_poss")
         .reset_index().rename(columns={"offense_team_id": "team_id"}))
    g = p.groupby("game_id").agg(max_period=("period", "max")).reset_index()
    g["game_minutes"] = REGULATION_MIN + 5.0 * np.maximum(0, g["max_period"] - 4)
    n = n.merge(g, on="game_id", how="left", validate="m:1")
    n["realised_off_poss"] = n["n_off_poss"] * REGULATION_MIN / n["game_minutes"]
    n["went_ot"] = n["max_period"] > 4
    return n[["game_id", "team_id", "realised_off_poss", "went_ot", "max_period"]]


def bias_share(e: np.ndarray) -> dict:
    e = e[np.isfinite(e)]
    return {"n": int(len(e)),
            "mean_err": float(e.mean()),
            "squared_bias": float(e.mean() ** 2),
            "mse": float((e ** 2).mean()),
            "bias_share_of_mse": float(e.mean() ** 2 / (e ** 2).mean())}


def main() -> int:
    out: dict = {"schema": "p26_measurements/1",
                 "artifacts": {str(p.relative_to(PP.parents[1])): sha(p) for p in (PRIOR, POSS)}}

    P = pd.read_parquet(PRIOR)
    R = realised_pace()
    D = P.merge(R, on=["game_id", "team_id"], how="left", validate="1:1")
    D["game_date"] = pd.to_datetime(D["game_date"])
    D["pred"] = D["projected_team_off_possessions"]
    D["err"] = D["pred"] - D["realised_off_poss"]
    res = D[D["pace_resolved"] & D["err"].notna()].copy()

    # ---- M1 universe -----------------------------------------------------------------------
    out["M1_universe"] = {
        "team_game_rows_total": int(len(P)),
        "resolved_rows": int(len(res)),
        "unresolved_rows": int(len(P) - len(res)),
        "game_clusters_resolved": int(res["game_id"].nunique()),
        "game_clusters_total": int(P["game_id"].nunique()),
        "rows_per_resolved_cluster_min": int(res.groupby("game_id").size().min()),
        "rows_per_resolved_cluster_max": int(res.groupby("game_id").size().max()),
        "by_pace_source_all_rows": {k: int(v) for k, v in
                                    P["pace_source"].value_counts().sort_index().items()},
    }

    # ---- M2 pooled bias / variance ---------------------------------------------------------
    e = res["err"].to_numpy(float)
    out["M2_pooled"] = {
        **bias_share(e),
        "residual_variance_ddof1": float(np.var(e, ddof=1)),
        "target_variance_ddof1": float(res["realised_off_poss"].var(ddof=1)),
        "variance_explained_vs_target": float(
            1.0 - np.var(e, ddof=1) / res["realised_off_poss"].var(ddof=1)),
        "projected_variance_ddof1": float(res["pred"].var(ddof=1)),
        "var_projected_over_var_target": float(
            res["pred"].var(ddof=1) / res["realised_off_poss"].var(ddof=1)),
    }

    # ---- M3 (S6) bias share by tier ---------------------------------------------------------
    res = res.sort_values(["team_id", "game_date"])
    res["game_no_in_season"] = res.groupby(["team_id", "season"]).cumcount() + 1
    strata = {}
    for src, s in res.groupby("pace_source"):
        strata[str(src)] = bias_share(s["err"].to_numpy(float))
    for label, mask in (("season_openers_gno_le_3", res["game_no_in_season"] <= 3),
                        ("season_openers_gno_eq_1", res["game_no_in_season"] == 1),
                        ("pace_level_gt_1", res["pace_level"] > 1)):
        strata[label] = bias_share(res.loc[mask, "err"].to_numpy(float))
    out["M3_bias_share_by_stratum"] = strata

    # ---- M4 (S7) per-fold tier support ------------------------------------------------------
    ct = (res.groupby(["pace_source", "season"]).size().unstack(fill_value=0).sort_index())
    out["M4_pace_source_by_season"] = {str(i): {str(c): int(v) for c, v in r.items()}
                                       for i, r in ct.iterrows()}
    out["M4_identically_zero_fold_cells"] = [
        {"pace_source": str(i), "season": str(c)}
        for i, r in ct.iterrows() for c, v in r.items() if int(v) == 0]

    # ---- M5 (packet claim) pace_level>1 vs game_no_in_season<=3 -------------------------------
    a = (res["pace_level"] > 1).to_numpy()
    b = (res["game_no_in_season"] <= 3).to_numpy()
    out["M5_tier_equals_game_no_le_3"] = {
        "n": int(len(a)),
        "agree": int((a == b).sum()),
        "off_diagonal_total": int((a != b).sum()),
        "tier_true_gno_false": int((a & ~b).sum()),
        "tier_false_gno_true": int((~a & b).sum()),
        "packet_claim": "pace_level > 1 is algebraically identical to game_no_in_season <= 3 "
                        "(2982/2982, zero off-diagonal)",
    }

    # ---- M6 (S5) own + opp == 2 * projected --------------------------------------------------
    g = res[["game_id", "team_id", "team_pace_estimate", "pred"]].copy()
    tot = g.groupby("game_id")["team_pace_estimate"].transform("sum")
    two_sided = g.groupby("game_id")["team_pace_estimate"].transform("size") == 2
    gg = g[two_sided].copy()
    gg["own"] = gg["team_pace_estimate"]
    gg["opp"] = tot[two_sided] - gg["team_pace_estimate"]
    dev = (gg["own"] + gg["opp"] - 2.0 * gg["pred"]).abs()
    out["M6_offset_identity"] = {
        "rows_two_sided": int(len(gg)),
        "max_abs_deviation": float(dev.max()),
        "corr_own_projected": float(np.corrcoef(gg["own"], gg["pred"])[0, 1]),
        "corr_own_opp": float(np.corrcoef(gg["own"], gg["opp"])[0, 1]),
        "gate_pairwise_threshold": 0.999,
    }

    # ---- M7 comparison_gate structure --------------------------------------------------------
    import sys
    sys.path.insert(0, str(PP))
    import comparison_gate as CG                                        # noqa: E402
    src = (PP / "comparison_gate.py").read_text(encoding="utf-8")
    out["M7_comparison_gate"] = {
        "n_dimensions": len(CG.DIMENSIONS),
        "dimensions": list(CG.DIMENSIONS),
        "roles": list(CG.ROLES),
        "has_calibration_slope_dimension": any("slope" in d for d in CG.DIMENSIONS),
        "has_calibration_freedom_dimension": "calibration_freedom" in CG.DIMENSIONS,
        "sidespec_fields_with_arm_key": [f for f in ("arm_id", "k0_kind", "control_kind")
                                         if f in CG.SideSpec.__dataclass_fields__],
        "occurrences_of_K0_MATCHED_in_source": src.count("K0_MATCHED"),
        "occurrences_of_K0_FLAT_in_source": src.count("K0_FLAT"),
        "occurrences_of_slope_in_source": src.lower().count("slope"),
        "k0_substantive_feature_rule": "k0_has_substantive_features fires when "
                                       "k0.n_substantive_features > 0",
    }

    # ---- M8 arm registry: which Stage 2B possession arms exist yet ---------------------------
    arms = []
    for line in (PP / "arm_registry.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        arms.append({"kind": d.get("kind"), "experiment_id": d.get("experiment_id")})
    out["M8_arm_registry"] = {
        "records_total": len(arms),
        "kind_arm_count": sum(1 for a in arms if a["kind"] == "arm"),
        "stage2b_possession_arm_ids": [a["experiment_id"] for a in arms
                                       if a["kind"] == "arm" and "stage2b" in
                                       str(a["experiment_id"]).lower()],
    }

    # ---- M9 packet's own K0 spec, verbatim ---------------------------------------------------
    pk = json.loads(PACKET.read_text(encoding="utf-8"))
    out["M9_packet_control_specification"] = pk["control_specification"]
    out["M9_packet_k0_matched_is_single_object"] = not isinstance(
        pk["control_specification"]["K0_MATCHED"].get("definition"), dict)
    out["M9_packet_bias_variance_block"] = pk["bias_variance"]

    (HERE / "MEASUREMENTS.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
