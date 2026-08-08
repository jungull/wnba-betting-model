"""E0_I0019 -- s01: THE PROVENANCE GATE.  Nothing downstream runs if this does not pass.

Establishes that `p_active` is point-in-time and out-of-sample, by (A) reading the walk-forward
receipts, (B) VERIFYING D076's artifact-partition reasoning on VALUES rather than inheriting it,
and (C) four independent leak probes, two of D076's design and two of this screen's own.
Writes s01_provenance.json and the analysis frame.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

import av_base as B
import screenkit as sk

pd.set_option("display.width", 240)
pd.set_option("display.max_columns", 120)
OUT = B.OUT
REP = {}

# =====================================================================================
B.hdr("s01A -- WALK-FORWARD RECEIPTS (both arms, 2021-2024)")
# =====================================================================================
rec = {}
for arm, d in B.ARM_DIR.items():
    rec[arm] = {}
    for s in B.PARTITION:
        fr = json.load(open(os.path.join(d, "fold_receipt__%d.json" % s)))
        rr = fr["receipts"]
        rec[arm][s] = dict(
            train_seasons=fr["train_seasons"], n_train_rows=fr["n_train_rows"],
            n_test_rows=fr["n_test_rows"], model_was_fitted=fr["model_was_fitted"],
            degenerate=fr["degenerate"],
            cold_start_declared_constant_only=fr["cold_start_declared_constant_only"],
            p_active_in_targets=("p_active" in fr["targets"]),
            fold_boundary_ok=rr["fold_boundary"]["ok"],
            provenance_history_ok=rr["provenance_history"]["ok"],
            own_outcome_never_informed_its_forecast=fr["own_outcome_never_informed_its_forecast"],
            forecast_scored_against_outcome=fr["forecast_scored_against_outcome"],
            evaluation_metric_calculated=fr["evaluation_metric_calculated"],
            failed_receipts=fr["failed_receipts"],
            fit_through_date=fr["fit_through_date"])
        print("  %-4s %d  train=%-22s n_train=%-6d n_test=%-5d fitted=%-5s degen=%-5s "
              "fold_boundary=%s prov_hist=%s own_outcome_never_informed=%s scored=%s"
              % (arm, s, fr["train_seasons"], fr["n_train_rows"], fr["n_test_rows"],
                 fr["model_was_fitted"], fr["degenerate"], rr["fold_boundary"]["ok"],
                 rr["provenance_history"]["ok"],
                 fr["own_outcome_never_informed_its_forecast"],
                 fr["forecast_scored_against_outcome"]))
        # every train season strictly precedes the fold season
        assert all(int(t) < s for t in fr["train_seasons"]), "train season not strictly prior"
print("  -> 2021 is DEGENERATE in BOTH arms (n_train=0, model_was_fitted=false). EXCLUDED.")
print("  -> SCREEN SEASONS =", B.SCREEN_SEASONS)
REP["A_fold_receipts"] = rec

# =====================================================================================
B.hdr("s01B -- MANIFESTS, AND THE ARTIFACT-GRANULARITY QUESTION")
# =====================================================================================
print("  screenkit.check_manifest verdict field is `status`.")
pa15, meta15 = B.load_p_active("v15")
pa14, meta14 = B.load_p_active("v14")
REP["B_manifest_v15"] = meta15
REP["B_manifest_v14"] = meta14
print("\n  Every p_active file is asof_granularity='artifact' -> screenkit says UNUSABLE, which is")
print("  the correct GENERIC verdict.  D076's specific argument is that each file's OWN")
print("  fit_through_season equals its own season, so the artifact is wholly inside the")
print("  partition.  s01C VERIFIES THAT ON VALUES instead of inheriting it.")

print("\n  contract_v5 (v15's declared row universe) manifest presence:")
c5 = os.path.join(B.ROOT, r"experiments\prediction_contract_v5")
for fn in sorted(os.listdir(c5)):
    if fn.endswith(".manifest.json"):
        print("    manifest found:", fn)
have = [fn for fn in os.listdir(c5) if fn.endswith(".manifest.json")]
print("    -> %d manifests in prediction_contract_v5.  NO SIBLING MANIFEST => UNVERIFIABLE,"
      " NOT OPENED (same rule D076 applied to minutes_baselines/test_predictions.csv)." % len(have))
REP["B_contract_v5_manifests"] = have

print("\n  FORBIDDEN artifacts -- MANIFEST ONLY, data never opened:")
forb = {}
for rel in ["data/w1_truth/player_game_availability.csv", "data/w1_truth/roster_asof.csv"]:
    p = os.path.join(B.ROOT, rel.replace("/", os.sep))
    raw = json.load(open(p + ".manifest.json"))
    st = sk.check_manifest(p)
    forb[rel] = dict(status=st.get("status"), asof_granularity=raw.get("asof_granularity"),
                     fit_through_season=raw.get("fit_through_season"), opened=False)
    print("    %-46s status=%-13s asof=%-9s fit_through_season=%s -> NOT OPENED"
          % (rel, st.get("status"), raw.get("asof_granularity"), raw.get("fit_through_season")))
REP["B_forbidden"] = forb

# =====================================================================================
B.hdr("s01C -- VERIFY THE ARTIFACT SITS INSIDE ITS OWN SEASON (VALUE TEST, NOT INHERITED)")
# =====================================================================================
con = B.load_contract()
key = con[["row_uid", "game_id", "team_id", "player_id", "season", "gdate", "minutes", "pts",
           "fga", "appeared", "in_target_box", "appeared_for_other_team", "candidate_at_cutoff",
           "prediction_required__p_active", "outcome_scoreable__p_active",
           "forecast_cutoff", "clustering_unit"]].copy()

verif = {}
for arm, pa in [("v15", pa15), ("v14", pa14)]:
    z = pa.merge(key[["row_uid", "season", "gdate"]], on="row_uid", how="left")
    tab = {}
    for s in B.SCREEN_SEASONS:
        sub = z[z["__file_season"] == s]
        matched = sub[sub["season"].notna()]
        seasons_seen = sorted(set(int(x) for x in matched["season"].unique()))
        dmin, dmax = matched["gdate"].min(), matched["gdate"].max()
        tab[s] = dict(rows_in_file=int(len(sub)),
                      rows_joined_to_contract_v4=int(len(matched)),
                      rows_not_in_contract_v4=int(sub["season"].isna().sum()),
                      distinct_contract_seasons=seasons_seen,
                      min_game_date=str(dmin.date()), max_game_date=str(dmax.date()))
        print("  %-4s file %d: rows=%-6d joined=%-6d unjoined=%-5d contract seasons seen=%s "
              "dates %s..%s" % (arm, s, len(sub), len(matched), int(sub["season"].isna().sum()),
                                seasons_seen, dmin.date(), dmax.date()))
        assert seasons_seen == [s], "artifact %s/%d contains other seasons: %s" % (arm, s, seasons_seen)
        assert dmax < pd.Timestamp("2025-01-01")
    verif[arm] = tab
REP["C_artifact_inside_own_season"] = verif
print("  VERDICT: every joined row of every per-season p_active artifact carries the file's own")
print("  season and a game_date inside it.  The artifact-level as-of bound is therefore not")
print("  relied upon for partitioning -- the values themselves are inside 2022-2024.")

# also confirm forecast_cutoff strictly precedes the game date on 100% of rows (probe 3 setup)
for arm, pa in [("v15", pa15), ("v14", pa14)]:
    z = pa.merge(key[["row_uid", "gdate"]], on="row_uid", how="inner")
    fc = pd.to_datetime(z["forecast_cutoff"], utc=True).dt.tz_localize(None)
    gd = pd.to_datetime(z["gdate"])
    bad = int((fc >= gd + pd.Timedelta(days=1)).sum())
    before = int((fc < gd + pd.Timedelta(days=1)).sum())
    print("  %-4s forecast_cutoff earlier than end of game day on %d/%d rows (violations=%d)"
          % (arm, before, len(z), bad))
    REP.setdefault("C_cutoff", {})[arm] = dict(n=int(len(z)), violations=bad,
                                               min_lead_days=float((gd - fc).dt.total_seconds().min() / 86400.0))

# =====================================================================================
B.hdr("s01D -- BUILD THE SCORING FRAME (availability rebuilt from master_player box membership)")
# =====================================================================================
mp = B.load_master()
box = (mp.groupby(["game_id", "team_id", "player_id"], as_index=False)
         .agg(box_minutes=("minutes", "max"), box_rows=("player_id", "size")))
box["appeared_box"] = box["box_minutes"] > 0

f = key[key["season"].isin(B.SCREEN_SEASONS)].copy()
f = f.merge(box, on=["game_id", "team_id", "player_id"], how="left")
f["appeared_box"] = f["appeared_box"].fillna(False)
agree = float((f["appeared_box"].astype(bool) == f["appeared"].astype(bool)).mean())
print("  contract `appeared` vs master_player box-membership rebuild: agreement = %.6f (n=%d)"
      % (agree, len(f)))
print(pd.crosstab(f["appeared"].astype(bool), f["appeared_box"].astype(bool)).to_string())
REP["D_availability_rebuild_agreement"] = dict(agreement=agree, n=int(len(f)))
if agree < 0.9999:
    B.defect("D-availability-rebuild-disagreement",
             "master_player box-membership rebuild of `appeared` disagrees with contract v4 "
             "`appeared` on %.6f of rows (n=%d). Using the BOX REBUILD as the outcome, as D076 "
             "did, and reporting the discrepancy." % (1 - agree, len(f)))

f["y"] = f["appeared_box"].astype(float)           # OUTCOME = box membership with minutes > 0
print("  scoreable flag: outcome_scoreable__p_active True on %d / %d rows"
      % (int(f["outcome_scoreable__p_active"].sum()), len(f)))
f = f[f["outcome_scoreable__p_active"] == True].copy()
f = f[f["prediction_required__p_active"] == True].copy()
print("  after keeping prediction_required & outcome_scoreable p_active rows: n=%d" % len(f))

for arm, pa in [("v15", pa15), ("v14", pa14)]:
    d = pa[["row_uid", "pred_point", "is_fallback", "fallback_level", "is_cold_start",
            "n_prior_games", "component_id", "model_hash", "config_hash", "data_snapshot_hash"]].copy()
    d.columns = ["row_uid"] + ["%s__%s" % (arm, c) for c in d.columns[1:]]
    f = f.merge(d, on="row_uid", how="left")
for arm in ["v15", "v14"]:
    miss = int(f["%s__pred_point" % arm].isna().sum())
    print("  %-4s predictions missing on %d / %d contract rows" % (arm, miss, len(f)))
    REP.setdefault("D_missing_pred", {})[arm] = miss

f = f[f["v15__pred_point"].notna() & f["v14__pred_point"].notna()].copy()
f = f.sort_values(["season", "player_id", "gdate", "game_id"]).reset_index(drop=True)
print("  FINAL SCORED FRAME n=%d  (both arms present, 2022-2024)" % len(f))
print(f.groupby("season").agg(n=("y", "size"), appear_rate=("y", "mean")).to_string())
B.guard(f, "scored frame")
sk.assert_partition(f, verbose=True)

# =====================================================================================
B.hdr("s01E -- LEAK PROBE 1 (D076's): cold-start rows must carry ONE pooled constant per season")
# =====================================================================================
p1 = {}
for arm in ["v15", "v14"]:
    cs = f[f["%s__is_cold_start" % arm] == True]
    nun = cs.groupby("season")["%s__pred_point" % arm].nunique().to_dict()
    vals = cs.groupby("season")["%s__pred_point" % arm].agg(lambda x: sorted(set(np.round(x, 8)))[:4]).to_dict()
    p1[arm] = dict(n_cold_start=int(len(cs)), distinct_per_season={int(k): int(v) for k, v in nun.items()},
                   values={int(k): [float(z) for z in v] for k, v in vals.items()})
    print("  %-4s cold-start n=%-5d distinct pred_point per season = %s   values=%s"
          % (arm, len(cs), nun, vals))
REP["E_probe1_cold_start"] = p1

# =====================================================================================
B.hdr("s01F -- LEAK PROBE 2 (D076's): forecast must track PRIOR appearance rate more tightly "
      "than the REMAINING-season appearance rate")
# =====================================================================================
g = f.groupby(["season", "player_id"], sort=False)["y"]
f["_prior_rate"] = g.transform(lambda x: x.shift(1).expanding().mean())
f["_future_rate"] = g.transform(lambda x: x[::-1].shift(1).expanding().mean()[::-1])
p2 = {}
for arm in ["v15", "v14"]:
    p = pd.to_numeric(f["%s__pred_point" % arm], errors="coerce")
    m = np.isfinite(p) & np.isfinite(f["_prior_rate"]) & np.isfinite(f["_future_rate"])
    cp = float(np.corrcoef(p[m], f["_prior_rate"][m])[0, 1])
    cf = float(np.corrcoef(p[m], f["_future_rate"][m])[0, 1])
    p2[arm] = dict(n=int(m.sum()), corr_prior=cp, corr_future=cf, prior_minus_future=cp - cf,
                   passes=bool(cp >= cf))
    print("  %-4s corr(pred, PRIOR rate)=%+.4f   corr(pred, FUTURE rate)=%+.4f   diff=%+.4f  n=%d"
          % (arm, cp, cf, cp - cf, int(m.sum())))
REP["F_probe2_prior_vs_future"] = p2

# =====================================================================================
B.hdr("s01G -- LEAK PROBE 3 (THIS SCREEN'S OWN, #1): within-stratum discrimination must be "
      "MODEST, not degenerate")
# =====================================================================================
print("  A forecast that had read its own outcome would separate appeared from not-appeared")
print("  almost perfectly INSIDE a stratum of identical pre-game state.  Strata are formed on")
print("  (n_prior_games decile x prior-appearance-rate quintile), both strictly-prior.")
f["_npg"] = pd.to_numeric(f["v15__n_prior_games"], errors="coerce").fillna(0.0)
q_npg = pd.qcut(f["_npg"].rank(method="first"), 10, labels=False, duplicates="drop")
pr = f["_prior_rate"].fillna(-1.0)
q_pr = pd.qcut(pr.rank(method="first"), 5, labels=False, duplicates="drop")
f["_stratum"] = q_npg.astype(str) + "|" + q_pr.astype(str)
p3 = {}
for arm in ["v15", "v14"]:
    aucs, ns = [], []
    for st, gg in f.groupby("_stratum"):
        if gg["y"].nunique() < 2 or len(gg) < 40:
            continue
        a = B.auc_mw(gg["y"], gg["%s__pred_point" % arm])
        if np.isfinite(a):
            aucs.append(a)
            ns.append(len(gg))
    aucs = np.array(aucs)
    ns = np.array(ns, float)
    wm = float((aucs * ns).sum() / ns.sum())
    p3[arm] = dict(n_strata=int(len(aucs)), weighted_mean_within_stratum_auc=wm,
                   max_within_stratum_auc=float(aucs.max()), min=float(aucs.min()),
                   pooled_auc=float(B.auc_mw(f["y"], f["%s__pred_point" % arm])),
                   passes=bool(wm < 0.90))
    print("  %-4s strata=%-3d  weighted-mean within-stratum AUC=%.4f  max=%.4f  pooled AUC=%.4f"
          % (arm, len(aucs), wm, aucs.max(), B.auc_mw(f["y"], f["%s__pred_point" % arm])))
print("  A leaked forecast would show within-stratum AUC ~1.0.  Threshold declared BEFORE the")
print("  run: fail if weighted-mean within-stratum AUC >= 0.90.")
REP["G_probe3_within_stratum_auc"] = p3

# =====================================================================================
B.hdr("s01H -- LEAK PROBE 4 (THIS SCREEN'S OWN, #2): the forecast must be BLIND to the "
      "REMAINDER of the player's season once prior state is held")
# =====================================================================================
print("  Regress the forecast on the player's strictly-FUTURE remaining-season appearance rate")
print("  AFTER absorbing the strictly-PRIOR rate and prior-game count. A point-in-time forecast")
print("  has no channel to the remainder except persistence, which the prior state absorbs.")
p4 = {}
for arm in ["v15", "v14"]:
    d = f[np.isfinite(f["_prior_rate"]) & np.isfinite(f["_future_rate"])].copy()
    yv = pd.to_numeric(d["%s__pred_point" % arm], errors="coerce").to_numpy(float)
    X = np.column_stack([np.ones(len(d)), d["_prior_rate"].to_numpy(float),
                         d["_npg"].to_numpy(float)])
    beta, *_ = np.linalg.lstsq(X, yv, rcond=None)
    resid_pred = yv - X @ beta
    fut = d["_future_rate"].to_numpy(float)
    beta2, *_ = np.linalg.lstsq(X, fut, rcond=None)
    resid_fut = fut - X @ beta2
    r = float(np.corrcoef(resid_pred, resid_fut)[0, 1])
    # same quantity for the OWN-ROW outcome, which the forecast IS allowed to be good at
    yy = d["y"].to_numpy(float)
    beta3, *_ = np.linalg.lstsq(X, yy, rcond=None)
    r_own = float(np.corrcoef(resid_pred, yy - X @ beta3)[0, 1])
    p4[arm] = dict(n=int(len(d)), partial_corr_pred_vs_future_remainder=r,
                   partial_corr_pred_vs_own_outcome=r_own, passes=bool(abs(r) < 0.25))
    print("  %-4s partial corr(pred, FUTURE-remainder rate | prior rate, n_prior) = %+.4f"
          % (arm, r))
    print("       partial corr(pred, OWN outcome            | prior rate, n_prior) = %+.4f  n=%d"
          % (r_own, len(d)))
print("  Threshold declared BEFORE the run: fail if |partial corr with the future remainder|")
print("  >= 0.25.  A modest positive value is EXPECTED and is not evidence of leakage -- it is")
print("  persistence the two-term control does not fully absorb (screenkit K1's lesson).")
REP["H_probe4_partial_future"] = p4

# =====================================================================================
B.hdr("s01I -- LEAK PROBE 5: fold identity hashes are CONSTANT within a fold and DIFFER across")
# =====================================================================================
p5 = {}
for arm in ["v15", "v14"]:
    t = f.groupby("season")[["%s__model_hash" % arm, "%s__config_hash" % arm,
                             "%s__data_snapshot_hash" % arm]].nunique()
    mh = f.groupby("season")["%s__model_hash" % arm].agg(lambda x: x.iloc[0]).to_dict()
    p5[arm] = dict(nunique_per_season=t.to_dict(), model_hash_by_season=mh,
                   distinct_model_hashes=int(f["%s__model_hash" % arm].nunique()))
    print("  %-4s distinct hashes per season:\n%s" % (arm, t.to_string()))
    print("       distinct model_hash across the three folds = %d"
          % f["%s__model_hash" % arm].nunique())
REP["I_probe5_hashes"] = p5

# =====================================================================================
B.hdr("s01J -- PROVENANCE VERDICT")
# =====================================================================================
checks = {
    "walk_forward_train_seasons_strictly_prior": True,
    "fold_boundary_receipt_ok_all_screened_folds": all(
        rec[a][s]["fold_boundary_ok"] for a in rec for s in B.SCREEN_SEASONS),
    "provenance_history_receipt_ok_all_screened_folds": all(
        rec[a][s]["provenance_history_ok"] for a in rec for s in B.SCREEN_SEASONS),
    "own_outcome_never_informed_its_forecast_all_folds": all(
        rec[a][s]["own_outcome_never_informed_its_forecast"] for a in rec for s in B.PARTITION),
    "forecast_never_scored_in_the_arm": all(
        not rec[a][s]["forecast_scored_against_outcome"] for a in rec for s in B.PARTITION),
    "2021_degenerate_and_excluded": all(rec[a][2021]["degenerate"] for a in rec),
    "artifact_values_inside_own_season": True,
    "cutoff_precedes_game_all_rows": all(REP["C_cutoff"][a]["violations"] == 0 for a in ["v15", "v14"]),
    "probe1_cold_start_single_constant": all(
        all(v == 1 for v in p1[a]["distinct_per_season"].values()) for a in ["v15", "v14"]),
    "probe2_tracks_prior_more_than_future": all(p2[a]["passes"] for a in ["v15", "v14"]),
    "probe3_within_stratum_auc_not_degenerate": all(p3[a]["passes"] for a in ["v15", "v14"]),
    "probe4_blind_to_future_remainder": all(p4[a]["passes"] for a in ["v15", "v14"]),
    "forbidden_artifacts_not_opened": True,
    "contract_v5_not_opened_no_manifest": True,
}
for k, v in checks.items():
    print("  %-58s %s" % (k, "PASS" if v else "FAIL"))
verdict = "ESTABLISHED" if all(checks.values()) else "NOT ESTABLISHED"
print("\n  PROVENANCE VERDICT: %s" % verdict)
REP["J_checks"] = checks
REP["J_verdict"] = verdict

f = f.drop(columns=["_prior_rate", "_future_rate", "_stratum"])
f.to_parquet(os.path.join(OUT, "scored_frame.parquet"), index=False)
print("  wrote scored_frame.parquet  shape=%s" % (f.shape,))
json.dump(REP, open(os.path.join(OUT, "s01_provenance.json"), "w"), indent=2, default=str)
print("  wrote s01_provenance.json")
if verdict != "ESTABLISHED":
    raise SystemExit("PROVENANCE NOT ESTABLISHED -- STOPPING, per the task's gate.")
print("\nDONE")
