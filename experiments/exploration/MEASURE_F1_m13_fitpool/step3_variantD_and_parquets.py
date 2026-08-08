#!/usr/bin/env python3
"""STEP 5 completion (variant D -> full 2x2) + STEP 4 setup (counterfactual
translation_rows.parquet per variant, so M14 can be re-run downstream).

  2x2 design:                    seasons {2022..2026}      seasons {2022..2024}
    pooled (no time cutoff)      A  = M13 AS PUBLISHED     B
    time-ordered (expanding)     C                         D

  A->B and C->D isolate HOLDOUT INCLUSION.
  A->C and B->D isolate TIME ORDERING.

Writes, per variant, a parquet with M13's exact out_cols schema into
./cf_<variant>/translation_rows.parquet plus a minimal FINDINGS.json carrying
the matching sha256, so the unmodified M14 logic can consume it.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import m13_lib as L  # noqa: E402
import compute_model_vs_market as mvm  # noqa: E402
from step2_variants import fit_all, apply_fit, score_block, SPEC, VARIANT_COLS  # noqa: E402

HEADLINE_TIER = L.HEADLINE_TIER
OUT_COLS = ["row_uid", "game_id", "player_id", "player_name", "season", "evaluation_tier",
            "game_date", "forecast_cutoff", "pred_point", "consensus_line", "pts", "y_over",
            "p_over_normal", "p_over_student_t", "p_over_empirical", "p_over_het_normal",
            "p_over_market_devig", "diff_normal_minus_market", "n_books_at_consensus_line",
            "snap_ret_utc"]

VARIANTS = {
    "A_POOLED_PUBLISHED":  {"seasons": [2022, 2023, 2024, 2025, 2026], "time_ordered": False},
    "B_POOLED_2022_2024":  {"seasons": [2022, 2023, 2024],             "time_ordered": False},
    "C_TIME_ORDERED":      {"seasons": [2022, 2023, 2024, 2025, 2026], "time_ordered": True},
    "D_TIME_ORDERED_2022_2024": {"seasons": [2022, 2023, 2024],        "time_ordered": True},
}


def main():
    outcomes, name_rows, _ = mvm.load_outcomes()
    scored, _ = mvm.load_scored_points(outcomes)
    id_index = mvm.build_identity_index(name_rows)
    market, _, _ = mvm.build_market_frame(id_index)

    m = scored.merge(market, on=["game_id", "player_id"], how="inner", validate="one_to_one")
    ev = m[~(m["pts"] == m["consensus_line"]) & ~(m["pred_point"] == m["consensus_line"])
           & ~(m["p_over_devig"] == 0.5)].copy().reset_index(drop=True)
    ev["y_over"] = (ev["pts"] > ev["consensus_line"]).astype(float)
    ev["p_over_market_devig"] = ev["p_over_devig"]
    ev["threshold"] = ev["pred_point"] - ev["consensus_line"]
    ev["game_date"] = ev["game_date"].astype(str)
    matched_uids = set(m["row_uid"])

    cells, fitinfo = {}, {}
    for tag, cfg in VARIANTS.items():
        fp = scored[(scored["evaluation_tier"] == HEADLINE_TIER)
                    & (scored["season"].isin(cfg["seasons"]))
                    & (~scored["row_uid"].isin(matched_uids))].copy()
        fp["residual"] = fp["pred_point"] - fp["pts"]
        fp["game_date"] = fp["game_date"].astype(str)

        sub = ev.copy()
        if not cfg["time_ordered"]:
            f = fit_all(fp["residual"].to_numpy(), fp["pred_point"].to_numpy())
            ps = apply_fit(f, sub["threshold"].to_numpy(), sub["pred_point"].to_numpy())
            for c, v in ps.items():
                sub[c] = v
            fam = f["family"]
            fitinfo[tag] = {"mode": "pooled", "pool_n": f["n"], "family": fam,
                            "normal_loc": f["normal"]["loc"], "normal_scale": f["normal"]["scale"],
                            "t_df": f["student_t"]["df"], "t_scale": f["student_t"]["scale"],
                            "n_unscorable_thin_pool_rows": 0}
        else:
            ps_sorted = fp.sort_values("game_date", kind="mergesort").reset_index(drop=True)
            dts, res, prd = (ps_sorted["game_date"].to_numpy(),
                             ps_sorted["residual"].to_numpy(), ps_sorted["pred_point"].to_numpy())
            cols = {c: np.full(len(sub), np.nan) for c in VARIANT_COLS.values()}
            fams, pooln, thin = [], [], 0
            for d, idx in sub.groupby("game_date").groups.items():
                idx = np.asarray(idx)
                k = int(np.searchsorted(dts, d, side="left"))
                if k < SPEC["min_pool_n"]:
                    thin += len(idx)
                    continue
                f = fit_all(res[:k], prd[:k])
                fams.append(f["family"]); pooln.append(k)
                out = apply_fit(f, sub.loc[idx, "threshold"].to_numpy(),
                                sub.loc[idx, "pred_point"].to_numpy())
                for c, v in out.items():
                    cols[c][idx] = v
            for c, v in cols.items():
                sub[c] = v
            fam = pd.Series(fams).value_counts().idxmax()
            fitinfo[tag] = {"mode": "time_ordered_expanding", "n_refits": len(fams),
                            "family_counts": pd.Series(fams).value_counts().to_dict(),
                            "family": fam, "pool_n_min": int(min(pooln)), "pool_n_max": int(max(pooln)),
                            "n_unscorable_thin_pool_rows": int(thin)}
            sub = sub[sub["p_over_normal"].notna()].copy()

        sub["diff_normal_minus_market"] = sub["p_over_normal"] - sub["p_over_market_devig"]
        cells[tag] = {t: score_block(d, fam) for t, d in
                      (("A_primary", sub[sub["evaluation_tier"] == HEADLINE_TIER]), ("all_tiers", sub))}
        print(tag, "n", len(sub), "fam", fam,
              "A_primary brier", round(cells[tag]["A_primary"][fam]["brier"], 8),
              cells[tag]["A_primary"]["calib_verdict"])

        # ---- counterfactual parquet in M13's exact schema, for the M14 trace ----
        cf = HERE / f"cf_{tag}"
        cf.mkdir(exist_ok=True)
        rows_out = sub[OUT_COLS].copy()
        rows_out["model_version"] = "cbs_v15_player_oof_v5/1 (arm cbs_v15_player_oof_v5, rev 8)"
        rows_out["translation_schema_version"] = L.TRANSLATION_SCHEMA_VERSION
        rows_out["forecast_cutoff"] = rows_out["forecast_cutoff"].astype(str)
        rows_out.to_parquet(cf / "translation_rows.parquet", index=False)
        h = L.sha256_file(cf / "translation_rows.parquet")
        (cf / "FINDINGS.json").write_text(json.dumps({
            "schema": "COUNTERFACTUAL_STUB_NOT_AN_M13_ARTIFACT",
            "variant": tag, "produced_by": "MEASURE_F1_m13_fitpool/step3",
            "translation_function": {"per_row_output": {"sha256": h, "n_rows": int(len(rows_out))}},
            "calibration": {"headline_verdict": cells[tag]["A_primary"]["calib_verdict"]},
        }, indent=1), encoding="utf-8")
        fitinfo[tag]["parquet_sha256"] = h
        fitinfo[tag]["n_rows"] = int(len(rows_out))

    # ---------------- 2x2 decomposition on the headline Brier gap ------------
    def gap(tag, tier="A_primary"):
        b = cells[tag][tier]
        return b[b["primary_family"]]["brier"] - b["market"]["brier"]

    def gapll(tag, tier="A_primary"):
        b = cells[tag][tier]
        return b[b["primary_family"]]["log_loss"] - b["market"]["log_loss"]

    decomp = {}
    for tier in ("A_primary", "all_tiers"):
        g = {t: gap(t, tier) for t in VARIANTS}
        gl = {t: gapll(t, tier) for t in VARIANTS}
        decomp[tier] = {
            "brier_gap_vs_market": g,
            "logloss_gap_vs_market": gl,
            "effect_of_HOLDOUT_INCLUSION_pooled__B_minus_A": g["B_POOLED_2022_2024"] - g["A_POOLED_PUBLISHED"],
            "effect_of_HOLDOUT_INCLUSION_timeordered__D_minus_C": g["D_TIME_ORDERED_2022_2024"] - g["C_TIME_ORDERED"],
            "effect_of_TIME_ORDERING_full_seasons__C_minus_A": g["C_TIME_ORDERED"] - g["A_POOLED_PUBLISHED"],
            "effect_of_TIME_ORDERING_restricted__D_minus_B": g["D_TIME_ORDERED_2022_2024"] - g["B_POOLED_2022_2024"],
            "total_A_to_D": g["D_TIME_ORDERED_2022_2024"] - g["A_POOLED_PUBLISHED"],
            "published_brier_diff_ci95_width": cells["A_POOLED_PUBLISHED"][tier]["brier_ci95_width"],
        }
        d = decomp[tier]
        tot = abs(d["effect_of_TIME_ORDERING_full_seasons__C_minus_A"]) + abs(d["effect_of_HOLDOUT_INCLUSION_pooled__B_minus_A"])
        d["share_time_ordering"] = (abs(d["effect_of_TIME_ORDERING_full_seasons__C_minus_A"]) / tot) if tot else None
        d["share_holdout_inclusion"] = (abs(d["effect_of_HOLDOUT_INCLUSION_pooled__B_minus_A"]) / tot) if tot else None
        d["total_move_as_fraction_of_published_CI_width"] = abs(d["total_A_to_D"]) / d["published_brier_diff_ci95_width"]

    out = {"spec": SPEC, "variants": {k: dict(v) for k, v in VARIANTS.items()},
           "fit_info": fitinfo, "cells": cells, "decomposition_2x2": decomp}
    (HERE / "step3_variants2x2.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    print()
    print(json.dumps(decomp["A_primary"], indent=1))
    print("wrote step3_variants2x2.json and cf_*/translation_rows.parquet")


if __name__ == "__main__":
    main()
