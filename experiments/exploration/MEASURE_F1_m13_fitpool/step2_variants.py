#!/usr/bin/env python3
"""STEPS 2/3/5 -- three variants of M13's residual-distribution fit, side by side.

  A  POOLED_PUBLISHED     fit_pool = A_primary, seasons {2022..2026}, row-level
                          exclusion only, NO time cutoff.  == what M13 published.
  B  POOLED_2022_2024     identical to A except seasons {2022,2023,2024}.
                          Isolates HOLDOUT INCLUSION (2025/2026 in the pool).
  C  TIME_ORDERED         seasons {2022..2026}, and for every scored row the
                          fit pool is restricted to residuals from games with
                          game_date STRICTLY BEFORE that row's game_date
                          (expanding window, refit at every distinct eval date).
                          Isolates TIME ORDERING.

Everything downstream of the fit (the four distributional variants, the AIC
family selection, the scoring, the cluster bootstrap, the verdict rule) is the
SAME CODE, imported from m13_lib (the verbatim copy of build_translation.py).

PRE-REGISTERED BEFORE ANY VARIANT WAS RUN (see SPEC block below).
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import m13_lib as L  # noqa: E402
import compute_model_vs_market as mvm  # noqa: E402  (already on sys.path via m13_lib)

# ============================ SPEC (pre-registered) ==========================
SPEC = {
    "min_pool_n": 500,
    "min_pool_rule": ("A scored row is UNSCORABLE under variant C if its strictly-prior "
                      "expanding fit pool holds fewer than 500 residuals. Unscorable rows are "
                      "COUNTED AND DROPPED from variant C. There is NO fallback to the pooled "
                      "fit -- a fallback would silently reintroduce the defect being measured. "
                      "500 chosen so the bootstrap-free s.e. on the fitted scale is ~3% relative "
                      "(scale/sqrt(2n)); fixed before any variant was executed."),
    "common_subset_rule": ("All three variants are ALSO scored on the identical COMMON SUBSET "
                           "(rows scorable under C) so that any A-vs-C delta cannot be an "
                           "artifact of a changing evaluation universe."),
    "family_selection": ("Same AIC rule as published (k=2 normal vs k=3 student_t). For A and B "
                         "it is applied once to the single pool. For C it is applied per distinct "
                         "eval date to that date's expanding pool -- the faithful analogue. The "
                         "per-date winner is recorded."),
    "noise_benchmark": ("Every A-vs-variant delta in Brier/log-loss is additionally tested with a "
                        "paired game-date cluster bootstrap on the per-row DIFFERENCE OF "
                        "DIFFERENCES (same seed/n_boot/method as the node), so a delta can be "
                        "compared against the artifact's own sampling noise rather than eyeballed."),
    "seasons_C": "{2022..2026} -- C holds the season set FIXED at A's, so A->C isolates time ordering alone.",
    "authored": "before any variant result was observed",
}
# ============================================================================

HEADLINE_TIER = L.HEADLINE_TIER
VARIANT_COLS = {"normal": "p_over_normal", "student_t": "p_over_student_t",
                "empirical": "p_over_empirical", "het_normal": "p_over_het_normal"}


def fit_all(res: np.ndarray, pred: np.ndarray) -> dict:
    """Every fitted object M13 derives from a residual pool, using M13's own code."""
    nf = L.fit_normal(res)
    nf["aic"] = L.aic(nf["loglik"], k=2)
    tf = L.fit_student_t_by_moment_ll_grid(res)
    tf["aic"] = L.aic(tf["loglik"], k=3)
    fam = "student_t" if tf["aic"] < nf["aic"] else "normal"
    X = np.column_stack([np.ones(len(pred)), pred])
    beta, *_ = np.linalg.lstsq(X, np.abs(res), rcond=None)
    return {"normal": nf, "student_t": tf, "family": fam,
            "beta": (float(beta[0]), float(beta[1])),
            "sorted_resid": np.sort(res), "n": int(len(res)),
            "diag": L.moment_stats(res)}


def apply_fit(fit: dict, threshold: np.ndarray, pred_point: np.ndarray) -> dict:
    nf, tf = fit["normal"], fit["student_t"]
    b0, b1 = fit["beta"]
    sigma_row = np.clip(b0 + b1 * pred_point, 0.5, None) * math.sqrt(math.pi / 2.0)
    return {
        "p_over_normal": L.normal_cdf(threshold, loc=nf["loc"], scale=nf["scale"]),
        "p_over_student_t": L.student_t_cdf(threshold, df=tf["df"], loc=tf["loc"], scale=tf["scale"]),
        "p_over_empirical": L.empirical_cdf(threshold, fit["sorted_resid"]),
        "p_over_het_normal": 0.5 * (1.0 + L._erf_vec((threshold - nf["loc"]) / (sigma_row * math.sqrt(2.0)))),
    }


def score_block(sub: pd.DataFrame, primary_family: str) -> dict:
    y = sub["y_over"].to_numpy()
    mp = sub["p_over_market_devig"].to_numpy()
    out = {"n_player_games": int(len(sub)), "n_games": int(sub["game_id"].nunique()),
           "n_date_clusters": int(sub["game_date"].nunique()),
           "over_base_rate": float(y.mean()),
           "primary_family": primary_family,
           "market": {"brier": L.brier_score(mp, y), "log_loss": L.log_loss(mp, y)}}
    for name, col in VARIANT_COLS.items():
        p = sub[col].to_numpy()
        out[name] = {"brier": L.brier_score(p, y), "log_loss": L.log_loss(p, y),
                     "mean_p_over": float(p.mean()), "call_over_rate": float((p > 0.5).mean())}
    pp = sub[VARIANT_COLS[primary_family]].to_numpy()
    out["primary_vs_market_brier_diff_ci95"] = L.paired_cluster_bootstrap_diff(
        (pp - y) ** 2, (mp - y) ** 2, sub["game_date"].to_numpy())
    eps = L.EPS_LOGLOSS
    llp = -(y * np.log(np.clip(pp, eps, 1 - eps)) + (1 - y) * np.log(1 - np.clip(pp, eps, 1 - eps)))
    llm = -(y * np.log(np.clip(mp, eps, 1 - eps)) + (1 - y) * np.log(1 - np.clip(mp, eps, 1 - eps)))
    out["primary_vs_market_logloss_diff_ci95"] = L.paired_cluster_bootstrap_diff(
        llp, llm, sub["game_date"].to_numpy())
    b = out["primary_vs_market_brier_diff_ci95"]
    out["calib_verdict"] = ("TRANSLATION_BETTER_CALIBRATED_THAN_MARKET" if b["hi"] < 0
                            else "TRANSLATION_WORSE_CALIBRATED_THAN_MARKET" if b["lo"] > 0
                            else "INDISTINGUISHABLE_FROM_MARKET_AT_THIS_N")
    out["brier_ci95_width"] = float(b["hi"] - b["lo"])
    ll = out["primary_vs_market_logloss_diff_ci95"]
    out["logloss_ci95_width"] = float(ll["hi"] - ll["lo"])
    return out


def main():
    print("loading (same machinery M13 uses)...")
    outcomes, name_rows, _ = mvm.load_outcomes()
    scored, _ = mvm.load_scored_points(outcomes)
    id_index = mvm.build_identity_index(name_rows)
    market, _, _ = mvm.build_market_frame(id_index)

    m = scored.merge(market, on=["game_id", "player_id"], how="inner", validate="one_to_one")
    push = (m["pts"] == m["consensus_line"])
    model_nocall = (m["pred_point"] == m["consensus_line"])
    market_nocall = (m["p_over_devig"] == 0.5)
    ev = m[~push & ~model_nocall & ~market_nocall].copy()
    ev["y_over"] = (ev["pts"] > ev["consensus_line"]).astype(float)
    ev["p_over_market_devig"] = ev["p_over_devig"]
    ev["threshold"] = ev["pred_point"] - ev["consensus_line"]
    matched_row_uids = set(m["row_uid"])

    # --- COLUMN-VALUE partition tests (never a text/regex scan) --------------
    ev_seasons = sorted(int(s) for s in ev["season"].unique())
    ev_dates = ev["game_date"].astype(str)
    partition = {
        "eval_universe_seasons_observed_from_column_values": ev_seasons,
        "eval_universe_min_game_date": str(ev_dates.min()),
        "eval_universe_max_game_date": str(ev_dates.max()),
        "eval_rows_per_season": {str(k): int(v) for k, v in
                                 ev["season"].value_counts().sort_index().items()},
    }
    print("partition:", json.dumps(partition))

    def build_pool(seasons):
        fp = scored[(scored["evaluation_tier"] == HEADLINE_TIER)
                    & (scored["season"].isin(seasons))
                    & (~scored["row_uid"].isin(matched_row_uids))].copy()
        fp["residual"] = fp["pred_point"] - fp["pts"]
        fp["game_date"] = fp["game_date"].astype(str)
        return fp

    pool_A = build_pool([2022, 2023, 2024, 2025, 2026])
    pool_B = build_pool([2022, 2023, 2024])
    print("pool A n =", len(pool_A), " pool B n =", len(pool_B))
    partition["pool_A_seasons_from_column_values"] = sorted(int(s) for s in pool_A["season"].unique())
    partition["pool_B_seasons_from_column_values"] = sorted(int(s) for s in pool_B["season"].unique())
    partition["pool_A_rows_per_season"] = {str(k): int(v) for k, v in
                                           pool_A["season"].value_counts().sort_index().items()}

    results = {}
    ev_all = ev.copy()

    # ---------------- A and B: single pooled fit ----------------------------
    fits_static = {}
    for tag, pool in (("A_POOLED_PUBLISHED", pool_A), ("B_POOLED_2022_2024", pool_B)):
        f = fit_all(pool["residual"].to_numpy(), pool["pred_point"].to_numpy())
        fits_static[tag] = f
        ps = apply_fit(f, ev_all["threshold"].to_numpy(), ev_all["pred_point"].to_numpy())
        for c, v in ps.items():
            ev_all[f"{tag}__{c}"] = v
        print(tag, "n_pool", f["n"], "family", f["family"],
              "normal loc/scale", round(f["normal"]["loc"], 6), round(f["normal"]["scale"], 6),
              "t df/scale", f["student_t"]["df"], round(f["student_t"]["scale"], 6))

    # ---------------- C: expanding window, refit per eval date --------------
    tag = "C_TIME_ORDERED"
    pool_sorted = pool_A.sort_values("game_date", kind="mergesort").reset_index(drop=True)
    pool_dates = pool_sorted["game_date"].to_numpy()
    pool_res = pool_sorted["residual"].to_numpy()
    pool_pred = pool_sorted["pred_point"].to_numpy()

    ev_all["game_date"] = ev_all["game_date"].astype(str)
    per_date_fits = []
    thin_rows = 0
    thin_dates = []
    cols = {c: np.full(len(ev_all), np.nan) for c in VARIANT_COLS.values()}
    fam_by_date = {}
    ev_all = ev_all.reset_index(drop=True)
    for d, idx in ev_all.groupby("game_date").groups.items():
        idx = np.asarray(idx)
        k = int(np.searchsorted(pool_dates, d, side="left"))   # strictly-before
        if k < SPEC["min_pool_n"]:
            thin_rows += len(idx)
            thin_dates.append({"game_date": d, "pool_n": k, "n_rows": int(len(idx))})
            continue
        f = fit_all(pool_res[:k], pool_pred[:k])
        fam_by_date[d] = f["family"]
        per_date_fits.append({"game_date": d, "pool_n": f["n"], "family": f["family"],
                              "normal_loc": f["normal"]["loc"], "normal_scale": f["normal"]["scale"],
                              "t_df": f["student_t"]["df"], "t_scale": f["student_t"]["scale"],
                              "het_b0": f["beta"][0], "het_b1": f["beta"][1],
                              "pool_max_date_used": str(pool_dates[k - 1]),
                              "skew": f["diag"]["skewness_fisher_pearson"],
                              "exkurt": f["diag"]["excess_kurtosis"]})
        ps = apply_fit(f, ev_all.loc[idx, "threshold"].to_numpy(),
                       ev_all.loc[idx, "pred_point"].to_numpy())
        for c, v in ps.items():
            cols[c][idx] = v
    for c, v in cols.items():
        ev_all[f"{tag}__{c}"] = v
    print(tag, "refits:", len(per_date_fits), " thin/unscorable rows:", thin_rows)

    # ---- LEAK ASSERTION on column values: no fit row may be >= the eval date
    max_used = {r["game_date"]: r["pool_max_date_used"] for r in per_date_fits}
    leak_violations = [d for d, mx in max_used.items() if mx >= d]
    print("time-ordering violations (pool_max_date >= eval_date):", len(leak_violations))

    scorable = ev_all[f"{tag}__p_over_normal"].notna()
    common = ev_all[scorable].copy()

    # ---------------- score every variant on both universes -----------------
    fam_C_mode = pd.Series(list(fam_by_date.values())).value_counts().to_dict() if fam_by_date else {}
    primary_C = max(fam_C_mode, key=fam_C_mode.get) if fam_C_mode else "student_t"

    def score_variant(tag, df, fam):
        sub = df.copy()
        for name, col in VARIANT_COLS.items():
            sub[col] = sub[f"{tag}__{col}"]
        blocks = {}
        for tier, tdf in (("A_primary", sub[sub["evaluation_tier"] == HEADLINE_TIER]),
                          ("all_tiers", sub)):
            blocks[tier] = score_block(tdf, fam)
        return blocks

    fams = {"A_POOLED_PUBLISHED": fits_static["A_POOLED_PUBLISHED"]["family"],
            "B_POOLED_2022_2024": fits_static["B_POOLED_2022_2024"]["family"],
            "C_TIME_ORDERED": primary_C}

    for universe_name, udf in (("full_eval_universe", ev_all), ("common_subset", common)):
        for tg in ("A_POOLED_PUBLISHED", "B_POOLED_2022_2024", "C_TIME_ORDERED"):
            if universe_name == "full_eval_universe" and tg == "C_TIME_ORDERED" and thin_rows:
                continue
            results.setdefault(universe_name, {})[tg] = score_variant(tg, udf, fams[tg])
            print(universe_name, tg, "A_primary brier",
                  round(results[universe_name][tg]["A_primary"][fams[tg]]["brier"], 6),
                  results[universe_name][tg]["A_primary"]["calib_verdict"])

    # ---------------- delta-of-delta noise tests (A vs B, A vs C) -----------
    dod = {}
    for tier in ("A_primary", "all_tiers"):
        sub = common[common["evaluation_tier"] == HEADLINE_TIER] if tier == "A_primary" else common
        y = sub["y_over"].to_numpy()
        eps = L.EPS_LOGLOSS

        def per_row(tg, fam):
            p = sub[f"{tg}__{VARIANT_COLS[fam]}"].to_numpy()
            sq = (p - y) ** 2
            ll = -(y * np.log(np.clip(p, eps, 1 - eps)) + (1 - y) * np.log(1 - np.clip(p, eps, 1 - eps)))
            return sq, ll

        aq, al = per_row("A_POOLED_PUBLISHED", fams["A_POOLED_PUBLISHED"])
        for tg in ("B_POOLED_2022_2024", "C_TIME_ORDERED"):
            vq, vl = per_row(tg, fams[tg])
            dod[f"{tier}::{tg}_minus_A"] = {
                "brier_delta_ci95": L.paired_cluster_bootstrap_diff(vq, aq, sub["game_date"].to_numpy()),
                "logloss_delta_ci95": L.paired_cluster_bootstrap_diff(vl, al, sub["game_date"].to_numpy()),
                "brier_delta_point": float(vq.mean() - aq.mean()),
                "logloss_delta_point": float(vl.mean() - al.mean()),
            }
            c = dod[f"{tier}::{tg}_minus_A"]
            c["brier_delta_excludes_zero"] = bool(c["brier_delta_ci95"]["lo"] > 0 or c["brier_delta_ci95"]["hi"] < 0)
            c["logloss_delta_excludes_zero"] = bool(c["logloss_delta_ci95"]["lo"] > 0 or c["logloss_delta_ci95"]["hi"] < 0)

    pdf = pd.DataFrame(per_date_fits)
    out = {
        "spec": SPEC,
        "partition_tests_on_column_values": partition,
        "pool_sizes": {"A": int(len(pool_A)), "B": int(len(pool_B)),
                       "C_min_expanding": int(pdf["pool_n"].min()) if len(pdf) else None,
                       "C_max_expanding": int(pdf["pool_n"].max()) if len(pdf) else None,
                       "C_median_expanding": float(pdf["pool_n"].median()) if len(pdf) else None},
        "static_fits": {k: {"n": v["n"], "family_selected": v["family"],
                            "normal": {kk: v["normal"][kk] for kk in ("loc", "scale", "loglik", "aic")},
                            "student_t": {kk: v["student_t"][kk] for kk in ("loc", "df", "scale", "loglik", "aic")},
                            "het_beta0": v["beta"][0], "het_beta1": v["beta"][1],
                            "diag": v["diag"]}
                        for k, v in fits_static.items()},
        "time_ordered_fit_summary": {
            "n_refits": int(len(pdf)),
            "n_unscorable_thin_pool_rows": int(thin_rows),
            "thin_dates": thin_dates,
            "time_ordering_violations": leak_violations,
            "family_selected_counts": fam_C_mode,
            "primary_family_used_for_verdict": primary_C,
            "normal_loc": {"min": float(pdf["normal_loc"].min()), "max": float(pdf["normal_loc"].max()),
                           "first": float(pdf["normal_loc"].iloc[0]), "last": float(pdf["normal_loc"].iloc[-1]),
                           "mean": float(pdf["normal_loc"].mean())},
            "normal_scale": {"min": float(pdf["normal_scale"].min()), "max": float(pdf["normal_scale"].max()),
                             "first": float(pdf["normal_scale"].iloc[0]), "last": float(pdf["normal_scale"].iloc[-1]),
                             "mean": float(pdf["normal_scale"].mean())},
            "t_df": {"min": int(pdf["t_df"].min()), "max": int(pdf["t_df"].max()),
                     "counts": {str(k): int(v) for k, v in pdf["t_df"].value_counts().sort_index().items()}},
            "t_scale": {"min": float(pdf["t_scale"].min()), "max": float(pdf["t_scale"].max()),
                        "first": float(pdf["t_scale"].iloc[0]), "last": float(pdf["t_scale"].iloc[-1])},
            "het_b1": {"min": float(pdf["het_b1"].min()), "max": float(pdf["het_b1"].max())},
        },
        "n_eval_full": int(len(ev_all)),
        "n_eval_common_subset": int(len(common)),
        "cells": results,
        "delta_of_delta_vs_A_on_common_subset": dod,
    }
    (HERE / "step2_variants.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    pdf.to_csv(HERE / "time_ordered_per_date_fits.csv", index=False)
    print("wrote step2_variants.json + time_ordered_per_date_fits.csv")


if __name__ == "__main__":
    main()
