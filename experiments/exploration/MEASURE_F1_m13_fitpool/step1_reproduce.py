#!/usr/bin/env python3
"""STEP 1 -- reproduce M13's published numbers EXACTLY, byte-for-byte where possible.

Runs m13_lib.main() (a verbatim copy of build_translation.py with only its four
path constants repointed, and its output directory redirected to ./repro_out/ so
NOTHING is written inside M13). Then diffs every published quantity.

READ-ONLY with respect to M13/M14. No registry, no ledger.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import m13_lib  # noqa: E402

M13 = m13_lib.MARKET_PROGRAM / "M13_PLAYER_VALUE_TRANSLATION"
PUB = json.loads((M13 / "FINDINGS.json").read_text(encoding="utf-8"))


def main():
    print("=" * 78)
    print("STEP 1: reproducing M13 by executing the copied pipeline")
    print("=" * 78)
    m13_lib.main()

    rep = json.loads((m13_lib.HERE / "FINDINGS.json").read_text(encoding="utf-8"))

    deltas = {}

    def cmp(label, a, b):
        if a is None or b is None:
            deltas[label] = {"published": a, "reproduced": b, "abs_delta": None}
            return
        if isinstance(a, str) or isinstance(b, str):
            deltas[label] = {"published": a, "reproduced": b,
                             "identical": bool(a == b)}
            return
        deltas[label] = {"published": a, "reproduced": b, "abs_delta": abs(float(b) - float(a))}

    pd_ = PUB["distributional_assumption"]
    rd_ = rep["distributional_assumption"]
    cmp("fit_pool.n", pd_["fit_pool"]["n"], rd_["fit_pool"]["n"])
    for k in ("mean", "std_ddof1", "median", "skewness_fisher_pearson", "excess_kurtosis",
              "min", "max", "p05", "p95"):
        cmp(f"residual_diagnostics.{k}", pd_["residual_diagnostics"][k], rd_["residual_diagnostics"][k])
    for k in ("loc", "scale", "loglik", "aic"):
        cmp(f"normal_fit.{k}", pd_["normal_fit"][k], rd_["normal_fit"][k])
    for k in ("loc", "df", "scale", "loglik", "aic"):
        cmp(f"student_t_fit.{k}", pd_["student_t_fit"][k], rd_["student_t_fit"][k])
    cmp("primary_family_selected", pd_["model_selection"]["primary_family_selected"],
        rd_["model_selection"]["primary_family_selected"])
    for i, side in enumerate(("lo", "hi")):
        cmp(f"param_ci.loc_ci95.{side}",
            pd_["propagated_parameter_uncertainty"]["loc_ci95"][i],
            rd_["propagated_parameter_uncertainty"]["loc_ci95"][i])
        cmp(f"param_ci.scale_ci95.{side}",
            pd_["propagated_parameter_uncertainty"]["scale_ci95"][i],
            rd_["propagated_parameter_uncertainty"]["scale_ci95"][i])
    for k in ("intercept_mean_abs_resid", "slope_per_pred_point", "t_stat",
              "bin_level_pearson_r_meanpred_vs_stdresid", "row_level_spearman_absresid_vs_pred"):
        cmp(f"het.{k}", pd_["heteroscedasticity_check"][k], rd_["heteroscedasticity_check"][k])

    for tier in ("A_primary", "all_tiers"):
        pc, rc = PUB["calibration"]["cells"][tier], rep["calibration"]["cells"][tier]
        cmp(f"{tier}.n_player_games", pc["n_player_games"], rc["n_player_games"])
        cmp(f"{tier}.n_games", pc["n_games"], rc["n_games"])
        cmp(f"{tier}.over_base_rate", pc["over_base_rate"], rc["over_base_rate"])
        for fam in ("market", "normal", "student_t", "empirical", "het_normal"):
            cmp(f"{tier}.{fam}.brier", pc[fam]["brier"], rc[fam]["brier"])
            cmp(f"{tier}.{fam}.log_loss", pc[fam]["log_loss"], rc[fam]["log_loss"])
        for m in ("primary_vs_market_brier_diff_ci95", "primary_vs_market_logloss_diff_ci95"):
            for side in ("lo", "hi"):
                cmp(f"{tier}.{m}.{side}", pc[m][side], rc[m][side])
            cmp(f"{tier}.{m}.width", pc[m]["hi"] - pc[m]["lo"], rc[m]["hi"] - rc[m]["lo"])
        for k, v in pc["sensitivity_across_variants"].items():
            cmp(f"{tier}.sens.{k}", v, rc["sensitivity_across_variants"][k])

    cmp("headline_verdict", PUB["calibration"]["headline_verdict"],
        rep["calibration"]["headline_verdict"])
    cmp("translation_rows.sha256", PUB["translation_function"]["per_row_output"]["sha256"],
        rep["translation_function"]["per_row_output"]["sha256"])
    cmp("translation_rows.n_rows", PUB["translation_function"]["per_row_output"]["n_rows"],
        rep["translation_function"]["per_row_output"]["n_rows"])
    cmp("FINDINGS.result_hash", PUB["result_hash"], rep["result_hash"])
    cmp("integrity.n_matched",
        PUB["inventory"]["model_vs_market_prior_work"]["integrity_cross_check_vs_reproduced_join"]["n_matched_player_games_this_run"],
        rep["inventory"]["model_vs_market_prior_work"]["integrity_cross_check_vs_reproduced_join"]["n_matched_player_games_this_run"])
    cmp("integrity.n_evaluable",
        PUB["inventory"]["model_vs_market_prior_work"]["integrity_cross_check_vs_reproduced_join"]["n_evaluable_matched_player_games_this_run"],
        rep["inventory"]["model_vs_market_prior_work"]["integrity_cross_check_vs_reproduced_join"]["n_evaluable_matched_player_games_this_run"])

    numeric = [v["abs_delta"] for v in deltas.values() if v.get("abs_delta") is not None]
    worst = max(numeric) if numeric else 0.0
    worst_key = max((k for k in deltas if deltas[k].get("abs_delta") is not None),
                    key=lambda k: deltas[k]["abs_delta"]) if numeric else None
    strings_ok = all(v.get("identical", True) for v in deltas.values() if "identical" in v)

    summary = {
        "max_abs_numeric_delta": worst,
        "max_abs_numeric_delta_field": worst_key,
        "n_numeric_fields_compared": len(numeric),
        "all_string_fields_identical": bool(strings_ok),
        "string_field_status": {k: v for k, v in deltas.items() if "identical" in v},
        "REPRODUCED": bool(worst == 0.0 and strings_ok),
        "per_field": deltas,
    }
    (HERE / "step1_reproduction.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print()
    print("max abs numeric delta :", worst, "  (field:", worst_key, ")")
    print("string fields identical:", strings_ok)
    for k, v in summary["string_field_status"].items():
        print("   ", k, "->", v)
    print("REPRODUCED EXACTLY   :", summary["REPRODUCED"])


if __name__ == "__main__":
    main()
