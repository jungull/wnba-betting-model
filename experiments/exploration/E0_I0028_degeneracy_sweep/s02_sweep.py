"""E0_I0028 -- STEP 02: run the preregistered degeneracy checklist.

Six defect families (D1-D6) x twenty partitions (P01-P20) x eight (arm, target) cells x
{2022, 2023, 2024, ALL}.  Every threshold is the one fixed in `_prereg.json`; nothing is chosen
here.  Output: `region_table.csv` (every cell, flagged or not) and `defects_table.csv` (the
target-level defect summary), written incrementally.
"""
import json
import os

import numpy as np
import pandas as pd

import dg_base as B

pd.set_option("display.width", 260)
pd.set_option("display.max_columns", 60)

RND = 9                       # decimals at which two predictions count as "the same value"


# ------------------------------------------------------------------ prereg thresholds, verbatim
TH = {
    "D1_min_rows": 100, "D1_max_distinct": 5, "D1_sd_ratio": 0.05,
    "D2_min_rows": 50, "D2_share": 0.01,
    "D3_min_cluster": 50, "D3_min_players": 2,
    "D4_min_rows": 100, "D4_max_distinct_sd": 2, "D4_corr": 0.05,
    "D5_min_rows": 50, "D5_modal_share": 0.01,
    "D6_min_rows": 100, "D6_coverage_tol": 0.10,
}


def binned(s, edges, labels):
    v = pd.to_numeric(s, errors="coerce")
    out = pd.Series(pd.NA, index=s.index, dtype=object)
    for (lo, hi), lab in zip(edges, labels):
        m = (v >= lo) & (v <= hi)
        out[m.fillna(False)] = lab
    out[v.isna()] = "null"
    return out


CNT_EDGES = [(0, 0), (1, 1), (2, 2), (3, 4), (5, 9), (10, 19), (20, 10 ** 9)]
CNT_LABS = ["0", "1", "2", "3-4", "5-9", "10-19", "20+"]


def _S(s):
    """Stringify a partition key so a NULL becomes the LITERAL string "nan".

    WHY THIS EXISTS.  `Series.astype(str)` on an Arrow-backed `str` column leaves missing values as
    a real NaN, not as the four characters "nan".  `groupby(dropna=False)` then makes a group whose
    KEY IS NaN, while the label written to CSV -- via `str(val)` -- is "nan".  Rebuilding the mask
    later by comparing against that label matches NOTHING, because `NaN != "nan"`.
    That is the screen kit's K0 lesson one layer down: A LABEL IS NOT A VALUE.  It is fixed HERE,
    at the point the key is made, so the label and the value are the same object everywhere.
    """
    return s.astype(object).where(s.notna(), "nan").astype(str)


def partitions(d):
    """The 20 preregistered partitions.  EVERY key is PRE-GAME OBSERVABLE (prereg C3)."""
    P = {}
    P["P01_global"] = pd.Series("ALL", index=d.index)
    P["P02_is_fallback"] = _S(d["is_fallback"].astype("boolean"))
    P["P03_fallback_level"] = _S(d["fallback_level"])
    P["P04_component_id"] = _S(d["component_id"])
    P["P05_is_cold_start"] = _S(d["is_cold_start"].astype("boolean"))
    P["P06_n_prior_games_bin"] = binned(d["n_prior_games"], CNT_EDGES, CNT_LABS)
    P["P07_n_prior_appearances_bin"] = binned(d["n_prior_appearances"], CNT_EDGES, CNT_LABS)
    P["P08_residual_pool_n_bin"] = binned(d["residual_pool_n"],
                                          [(-1, -1), (0, 0), (1, 9), (10, 49), (50, 10 ** 9)],
                                          ["-1(sentinel)", "0", "1-9", "10-49", "50+"])
    P["P09_selected_alpha_isnull"] = _S(d["selected_alpha"].isna())
    P["P10_team_prior_games_bin"] = binned(d["team_prior_games"],
                                           [(0, 0), (1, 2), (3, 5), (6, 10), (11, 10 ** 9)],
                                           ["0", "1-2", "3-5", "6-10", "11+"])
    P["P11_candidate_at_cutoff"] = _S(d["candidate_at_cutoff"])
    P["P12_exact_cutoff_ok"] = _S(d["exact_cutoff_ok"])
    P["P13_tip_time_quality"] = _S(d["tip_time_quality"])
    P["P14_player_season_game_index_bin"] = binned(d["player_season_game_index"],
                                                   CNT_EDGES, CNT_LABS)
    for pid, col in (("P15_universe_tier", "universe_tier"),
                     ("P16_evaluation_tier", "evaluation_tier"),
                     ("P17_fit_eligible", "fit_eligible"),
                     ("P18_candidate_source", "candidate_source"),
                     ("P19_team_assignment_confidence", "team_assignment_confidence"),
                     ("P20_roster_evidence_regime", "roster_evidence_regime")):
        P[pid] = (pd.Series("NOT_AVAILABLE", index=d.index)
                  if d[col].isna().all() else _S(d[col]))
    # INVARIANT: every partition key is a plain str Series with no missing value left, so the
    # label written to disk and the value used to rebuild the mask are the same thing.
    for pid, k in P.items():
        assert k.isna().sum() == 0, "partition %s still carries a real NULL key" % pid
    return P


def cell_stats(s, target):
    """Every D1-D6 statistic for one cell.  Ordering note: the OUTCOME is used ONLY here, on the
    measurement side; the cell itself was already defined by pre-game columns alone."""
    n = len(s)
    p = s["pred_point"].round(RND)
    vc = p.value_counts()
    sc = s[s["scoreable"]]
    y = sc["y"].to_numpy(float)
    r = dict(n_rows=n, n_scoreable=len(sc))

    # ---- D1 constant / near-constant ----
    r["n_distinct_pred"] = int(p.nunique())
    r["sd_pred"] = float(p.std(ddof=1)) if n > 1 else np.nan
    r["sd_truth"] = float(np.std(y, ddof=1)) if len(y) > 1 else np.nan
    r["sd_ratio"] = (r["sd_pred"] / r["sd_truth"]
                     if (r["sd_truth"] and np.isfinite(r["sd_truth"]) and r["sd_truth"] > 0)
                     else np.nan)
    r["top1_share"] = float(vc.iloc[0] / n) if n else np.nan
    r["top1_value"] = float(vc.index[0]) if n else np.nan
    r["top2_share"] = float(vc.iloc[:2].sum() / n) if n else np.nan
    r["D1_flag"] = bool(n >= TH["D1_min_rows"] and
                        (r["n_distinct_pred"] <= TH["D1_max_distinct"] or
                         (np.isfinite(r["sd_ratio"]) and r["sd_ratio"] < TH["D1_sd_ratio"])))

    # ---- D2 clipping / saturation ----
    pv = p.to_numpy(float)
    r["share_at_cell_min"] = float(np.mean(pv == np.nanmin(pv))) if n else np.nan
    r["share_at_cell_max"] = float(np.mean(pv == np.nanmax(pv))) if n else np.nan
    r["share_at_zero"] = float(np.mean(pv == 0.0)) if n else np.nan
    r["share_at_one"] = float(np.mean(pv == 1.0)) if n else np.nan
    r["D2_flag"] = bool(n >= TH["D2_min_rows"] and
                        max(r["share_at_cell_min"], r["share_at_cell_max"], r["share_at_zero"],
                            r["share_at_one"]) >= TH["D2_share"] and r["n_distinct_pred"] > 1)

    # ---- D3 duplicated prediction VECTORS ----
    cols = ["pred_point", "pred_sd"] + B.QCOLS
    # NaN-safe: round to RND, then build one string key per row via numpy (a plain str-join over
    # object dtype dies on the all-NaN pred_sd/quantile columns that p_active emits).
    arr = np.round(s[cols].to_numpy(dtype=float), RND)
    vec = pd.Series(["|".join("nan" if not np.isfinite(x) else repr(x) for x in row)
                     for row in arr], index=s.index)
    sz = vec.value_counts()
    big = sz.index[0] if len(sz) else None
    r["dup_cluster_size"] = int(sz.iloc[0]) if len(sz) else 0
    r["n_distinct_pred_vectors"] = int(len(sz))
    if big is not None:
        gb = s[(vec == big).to_numpy()]
        r["dup_cluster_players"] = int(gb["player_id"].nunique())
        r["dup_cluster_games"] = int(gb["game_id"].nunique())
        r["dup_cluster_seasons"] = int(gb["season"].nunique())
    else:
        r["dup_cluster_players"] = r["dup_cluster_games"] = r["dup_cluster_seasons"] = 0
    r["D3_flag"] = bool(r["dup_cluster_size"] >= TH["D3_min_cluster"]
                        and r["dup_cluster_players"] >= TH["D3_min_players"])

    # ---- D4 degenerate uncertainty ----
    sd = s["pred_sd"]
    r["n_distinct_pred_sd"] = int(sd.round(RND).nunique(dropna=True))
    r["sd_null_share"] = float(sd.isna().mean())
    r["sd_zero_share"] = float((sd.fillna(-1) == 0).mean())
    if len(sc) > 2 and sc["pred_sd"].notna().any():
        a = sc["pred_sd"].to_numpy(float)
        b = np.abs(sc["y"].to_numpy(float) - sc["pred_point"].to_numpy(float))
        m = np.isfinite(a) & np.isfinite(b)
        r["corr_sd_absresid"] = (float(np.corrcoef(a[m], b[m])[0, 1])
                                 if m.sum() > 2 and np.std(a[m]) > 0 else np.nan)
    else:
        r["corr_sd_absresid"] = np.nan
    r["D4_flag"] = bool(n >= TH["D4_min_rows"] and
                        (r["n_distinct_pred_sd"] <= TH["D4_max_distinct_sd"]
                         or r["sd_null_share"] == 1.0
                         or (np.isfinite(r["corr_sd_absresid"])
                             and abs(r["corr_sd_absresid"]) < TH["D4_corr"])))

    # ---- D5 sentinel ----
    r["modal_value"] = r["top1_value"]
    r["modal_share"] = r["top1_share"]
    r["modal_n_seasons"] = int(s.loc[p == vc.index[0], "season"].nunique()) if n else 0
    r["D5_flag"] = bool(n >= TH["D5_min_rows"] and r["modal_share"] >= TH["D5_modal_share"])

    # ---- D6 quantile incoherence ----
    q = s[B.QCOLS].to_numpy(float)
    if np.isfinite(q).any():
        cross = np.zeros(len(s), bool)
        for i in range(4):
            cross |= (q[:, i] > q[:, i + 1] + 1e-12)
        r["q_cross_rows"] = int(np.nansum(cross))
        pp = s["pred_point"].to_numpy(float)
        outside = (pp < q[:, 0] - 1e-12) | (pp > q[:, 4] + 1e-12)
        r["point_outside_interval_rows"] = int(np.nansum(outside))
        if len(sc) >= 2:
            qs = sc[B.QCOLS].to_numpy(float)
            ys = sc["y"].to_numpy(float)
            ok = np.isfinite(qs).all(axis=1) & np.isfinite(ys)
            r["cov90"] = (float(np.mean((ys[ok] >= qs[ok, 0]) & (ys[ok] <= qs[ok, 4])))
                          if ok.any() else np.nan)
            r["cov50"] = (float(np.mean((ys[ok] >= qs[ok, 1]) & (ys[ok] <= qs[ok, 3])))
                          if ok.any() else np.nan)
        else:
            r["cov90"] = r["cov50"] = np.nan
        r["quantiles_present"] = True
    else:
        r["q_cross_rows"] = r["point_outside_interval_rows"] = 0
        r["cov90"] = r["cov50"] = np.nan
        r["quantiles_present"] = False
    r["D6_flag"] = bool(
        r["q_cross_rows"] > 0 or r["point_outside_interval_rows"] > 0
        or (n >= TH["D6_min_rows"] and r["quantiles_present"]
            and ((np.isfinite(r["cov90"]) and abs(r["cov90"] - 0.90) > TH["D6_coverage_tol"])
                 or (np.isfinite(r["cov50"]) and abs(r["cov50"] - 0.50) > TH["D6_coverage_tol"]))))

    r["any_flag"] = bool(r["D1_flag"] or r["D2_flag"] or r["D3_flag"] or r["D4_flag"]
                         or r["D5_flag"] or r["D6_flag"])
    return r


def main():
    B.hdr("STEP 02 -- PREREGISTERED DEGENERACY SWEEP")
    print("  prereg sha256 verified: %s" % B.assert_prereg())
    w = pd.read_parquet(os.path.join(B.OUT, "work_frame.parquet"))
    B.assert_partition(w[["season", "game_date"]], label="s02 input")
    print("  work frame %s" % (w.shape,))
    print("  thresholds (verbatim from _prereg.json): %s" % json.dumps(TH))

    B.hdr("2a. D081 ANCHOR CROSS-CHECK -- score against D081's OWN stored reference column")
    dc = os.path.join(B.ROOT,
                      r"experiments\exploration\E0_I0015_points_skill_decomposition\decomp_frame.parquet")
    an = []
    if os.path.exists(dc):
        f = pd.read_parquet(dc, columns=["row_uid", "ref_pts", "ref_minutes", "ref_fga", "y_pts",
                                         "y_minutes", "y_fga"])
        # the work frame already carries `ref_*`; rename D081's so the merge cannot collide
        f = f.rename(columns={c: "d081_" + c for c in f.columns if c != "row_uid"})
        for arm in B.ARMS:
            for t, ry, rr in (("player_scoring_distribution", "d081_y_pts", "d081_ref_pts"),
                              ("e_minutes_given_active", "d081_y_minutes", "d081_ref_minutes"),
                              ("attempts_usage", "d081_y_fga", "d081_ref_fga")):
                d = w[(w["arm"] == arm) & (w["target"] == t) & w["scoreable"]]
                m = d.merge(f, on="row_uid", how="inner")
                if not len(m):
                    continue
                s, lm, lr, n = B.skill_of(m[ry], m["pred_point"], m[rr], t)
                s2, _, lr2, _ = B.skill_of(m[ry], m["pred_point"], m["ref"], t)
                an.append(dict(arm=arm, target=t, n=n, skill_vs_D081_ref_pct=round(100 * s, 4),
                               skill_vs_rebuilt_ref_pct=round(100 * s2, 4),
                               mae_D081_ref=round(lr, 5), mae_rebuilt_ref=round(lr2, 5)))
                print("    %-24s %-30s n=%5d  vs D081 ref=%+7.4f%%  vs rebuilt ref=%+7.4f%%"
                      % (arm, t, n, 100 * s, 100 * s2))
        print("\n  D081 published pooled POINTS skill = -0.22%. The v15/points row above is the")
        print("  direct comparison. The rebuilt reference is HARDER (lower MAE), so it scores the")
        print("  champion lower; both are reported and the routing gains below are computed")
        print("  against BOTH denominators so no gain rests on a reference choice.")
    pd.DataFrame(an).to_csv(os.path.join(B.OUT, "anchor_crosscheck.csv"), index=False)

    B.hdr("2b. sweep")
    rows = []
    for arm in B.ARMS:
        for t in B.TARGETS:
            d0 = w[(w["arm"] == arm) & (w["target"] == t)].reset_index(drop=True)
            P = partitions(d0)
            for season in ["ALL", 2022, 2023, 2024]:
                dm = d0 if season == "ALL" else d0[d0["season"] == season]
                if not len(dm):
                    continue
                idx = dm.index
                for pid, key in P.items():
                    k = key.loc[idx]
                    for val, sub in dm.groupby(k.astype(str), dropna=False):
                        if len(sub) < 10:
                            continue
                        st = cell_stats(sub, t)
                        st.update(arm=arm, target=t, season=str(season), partition=pid,
                                  cell=str(val))
                        rows.append(st)
            print("    swept %-24s %-30s cells so far: %d" % (arm, t, len(rows)))
    rt = pd.DataFrame(rows)
    front = ["arm", "target", "season", "partition", "cell", "n_rows", "n_scoreable",
             "n_distinct_pred", "sd_pred", "sd_truth", "sd_ratio", "top1_share", "top1_value",
             "D1_flag", "D2_flag", "D3_flag", "D4_flag", "D5_flag", "D6_flag", "any_flag"]
    rt = rt[front + [c for c in rt.columns if c not in front]]
    rt.to_csv(os.path.join(B.OUT, "region_table.csv"), index=False)
    print("\n  wrote region_table.csv  %s" % (rt.shape,))

    B.hdr("2c. flag counts by defect family (ALL-season cells only, to avoid triple counting)")
    a = rt[rt["season"] == "ALL"]
    for f in ["D1_flag", "D2_flag", "D3_flag", "D4_flag", "D5_flag", "D6_flag"]:
        print("    %-9s flagged %4d of %4d cells" % (f, int(a[f].sum()), len(a)))

    B.hdr("2d. target-level defect summary (P01_global, season=ALL)")
    g = a[a["partition"] == "P01_global"].copy()
    show = ["arm", "target", "n_rows", "n_scoreable", "n_distinct_pred", "sd_pred", "sd_truth",
            "sd_ratio", "top1_share", "top1_value", "n_distinct_pred_sd", "sd_null_share",
            "corr_sd_absresid", "q_cross_rows", "point_outside_interval_rows", "cov90", "cov50",
            "dup_cluster_size", "dup_cluster_players"]
    print(g[show].to_string(index=False))
    g.to_csv(os.path.join(B.OUT, "defects_table.csv"), index=False)

    B.hdr("2e. every D1-flagged cell, season=ALL, ranked by row count")
    d1 = a[a["D1_flag"]].sort_values("n_rows", ascending=False)
    print(d1[["arm", "target", "partition", "cell", "n_rows", "n_distinct_pred", "sd_pred",
              "sd_truth", "sd_ratio", "top1_share"]].to_string(index=False))

    B.hdr("2f. D6 -- quantile crossings and point-outside-interval, anywhere")
    d6 = a[(a["q_cross_rows"] > 0) | (a["point_outside_interval_rows"] > 0)]
    if len(d6):
        print(d6[["arm", "target", "partition", "cell", "n_rows", "q_cross_rows",
                  "point_outside_interval_rows"]].to_string(index=False))
    else:
        print("    NONE. No quantile crossing and no point outside its own [q05,q95] anywhere")
        print("    in 2022-2024, on either arm, on any target that emits quantiles.")

    B.hdr("2g. D6 -- interval coverage against realised outcomes (P01_global)")
    print(g[["arm", "target", "cov90", "cov50", "n_scoreable"]].to_string(index=False))

    B.jwrite("_s02.json", {"prereg_sha256": B.PREREG_SHA, "thresholds": TH,
                           "n_cells": len(rt),
                           "flag_counts": {f: int(a[f].sum()) for f in
                                           ["D1_flag", "D2_flag", "D3_flag", "D4_flag",
                                            "D5_flag", "D6_flag"]},
                           "anchor_crosscheck": an,
                           "global": g[show].to_dict("records")})


if __name__ == "__main__":
    main()
