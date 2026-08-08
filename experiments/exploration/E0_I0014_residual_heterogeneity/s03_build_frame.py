"""Step 1 + frame construction.  Establishes point-in-time provenance of the residuals, builds the
analysis frame, and writes it to analysis_frame.parquet inside this directory only."""
import json
import os

import numpy as np
import pandas as pd

import rh_base as B

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 80)

B.hdr("STEP 1a -- PROVENANCE OF THE RESIDUAL SET (fold receipts)")
prov = {}
for s in [2021, 2022, 2023, 2024]:
    fr = json.load(open(os.path.join(B.OOF, "fold_receipt__%d.json" % s)))
    prov[s] = dict(train_seasons=fr["train_seasons"], n_train_rows=fr["n_train_rows"],
                   n_test_rows=fr["n_test_rows"], model_was_fitted=fr["model_was_fitted"],
                   degenerate=fr["degenerate"],
                   cold_start_declared_constant_only=fr["cold_start_declared_constant_only"],
                   fold_boundary_ok=fr["receipts"]["fold_boundary"]["ok"],
                   provenance_history_ok=fr["receipts"]["provenance_history"]["ok"],
                   own_outcome_never_informed_its_forecast=fr["own_outcome_never_informed_its_forecast"],
                   forecast_scored_against_outcome=fr["forecast_scored_against_outcome"],
                   fit_through_date=fr["fit_through_date"])
    print("  season %d  train_seasons=%-18s n_train=%-6d n_test=%-5d fitted=%-5s degenerate=%s"
          % (s, fr["train_seasons"], fr["n_train_rows"], fr["n_test_rows"],
             fr["model_was_fitted"], fr["degenerate"]))
print("  -> 2021 fold is DEGENERATE (no model fitted). EXCLUDED. Screen seasons =", B.SCREEN_SEASONS)

B.hdr("STEP 1b -- MANIFEST CHECKS")
mp = B.load_master()
con = B.load_contract()
print("  data/w1_truth/player_game_availability.csv:")
am = json.load(open(os.path.join(B.ROOT, "data", "w1_truth", "player_game_availability.csv.manifest.json")))
print("     asof_granularity=%s fit_through_season=%s -> UNUSABLE, NOT OPENED"
      % (am["asof_granularity"], am["fit_through_season"]))
print("  data/w1_truth/roster_asof.csv:")
rm = json.load(open(os.path.join(B.ROOT, "data", "w1_truth", "roster_asof.csv.manifest.json")))
print("     asof_granularity=%s fit_through_season=%s -> UNUSABLE, NOT OPENED"
      % (rm["asof_granularity"], rm["fit_through_season"]))
print("  experiments/minutes_baselines/test_predictions.csv: NO SIBLING MANIFEST -> NOT USED"
      if not os.path.exists(os.path.join(B.ROOT, "experiments", "minutes_baselines",
                                         "test_predictions.csv.manifest.json"))
      else "  minutes_baselines has a manifest")

B.hdr("STEP 1c -- LOAD OOF PREDICTIONS (per-season, each bounded at its own season)")
oof = B.load_oof()
for t, d in oof.items():
    print("  %-8s rows=%d seasons=%s" % (t, len(d), sorted(d["__season"].unique())))

B.hdr("STEP 1d -- EMPIRICAL LEAK PROBES ON THE FORECASTS")
con_s = con[con["season"].isin(B.SCREEN_SEASONS)].copy()
z = con_s[["row_uid", "game_id", "team_id", "player_id", "season", "gdate", "minutes", "pts",
           "fga", "appeared",
           "outcome_scoreable__player_scoring_distribution",
           "outcome_scoreable__e_minutes_given_active",
           "outcome_scoreable__attempts_usage"]].copy()
for t, d in oof.items():
    z = z.merge(d.drop(columns=["__season"]), on="row_uid", how="left")

# probe 1: cold-start rows must carry an identical pooled constant (no player-specific info)
for t in ["pts", "minutes", "fga"]:
    cs = z[z["%s__is_cold_start" % t] == True]
    nun = cs.groupby("season")["%s__pred_point" % t].nunique()
    print("  probe1 cold-start distinct pred_point per season, %-8s: %s"
          % (t, dict(nun)))

# probe 2: forecast must not correlate with the SAME player's LATER-game outcome any more than
# with the earlier-game outcome once the prior mean is controlled -- crude version: correlation of
# pred_point with the player's FUTURE season-remainder mean, minus with the PRIOR mean.
zz = z[z["appeared"] == True].sort_values(["season", "player_id", "gdate"]).copy()
for t, ycol in [("pts", "pts"), ("minutes", "minutes"), ("fga", "fga")]:
    g = zz.groupby(["season", "player_id"], sort=False)[ycol]
    prior = g.transform(lambda x: x.shift(1).expanding().mean())
    fut = g.transform(lambda x: x[::-1].shift(1).expanding().mean()[::-1])
    p = pd.to_numeric(zz["%s__pred_point" % t], errors="coerce")
    m = np.isfinite(p) & np.isfinite(prior) & np.isfinite(fut)
    cp = np.corrcoef(p[m], prior[m])[0, 1]
    cf = np.corrcoef(p[m], fut[m])[0, 1]
    print("  probe2 %-8s corr(pred, PRIOR-mean)=%+.4f   corr(pred, FUTURE-mean)=%+.4f  "
          "(n=%d)  [a point-in-time forecast should track PRIOR at least as tightly]"
          % (t, cp, cf, int(m.sum())))

B.hdr("STEP 2a -- BUILD PRE-GAME CANDIDATES (strictly prior windows)")
PL = B.build_player_pregame(mp)
print("  player pre-game cols:", [c for c in PL.columns if c.startswith("pl_")])
T = B.build_team_pregame(mp)
print("  team pre-game cols  :", [c for c in T.columns if c.startswith(("tm_", "opp_"))])
PT = B.build_player_team_state(mp, T)
print("  player-team cols    :", [c for c in PT.columns if c.startswith("pl_")])

B.hdr("STEP 2b -- ASSEMBLE ANALYSIS FRAME")
f = z.merge(PL.drop(columns=["season", "gdate"]), on=["game_id", "team_id", "player_id"], how="left")
f = f.merge(T.drop(columns=["opp_team_id"]), on=["season", "team_id", "game_id"], how="left")
f = f.merge(PT, on=["game_id", "team_id", "player_id"], how="left")

# scoreable + appeared for ALL THREE targets so one frame and one block map serves the whole screen
m = (f["appeared"] == True)
for c in ["outcome_scoreable__player_scoring_distribution",
          "outcome_scoreable__e_minutes_given_active", "outcome_scoreable__attempts_usage"]:
    m &= (f[c] == True)
f = f[m].copy()
print("  scoreable+appeared rows:", len(f))

for t, ycol in [("pts", "pts"), ("minutes", "minutes"), ("fga", "fga")]:
    y = pd.to_numeric(f[ycol], errors="coerce").astype(float)
    p = pd.to_numeric(f["%s__pred_point" % t], errors="coerce").astype(float)
    f["y_" + t] = y
    f["resid_" + t] = y - p
    f["absres_" + t] = (y - p).abs()
    f["sqres_" + t] = (y - p) ** 2

# --- honest point-in-time REFERENCE forecast (for skill, not for the residual itself) ---
f = f.sort_values(["season", "player_id", "gdate"]).reset_index(drop=True)
for t, ycol in [("pts", "pts"), ("minutes", "minutes"), ("fga", "fga")]:
    g = f.groupby(["season", "player_id"], sort=False)["y_" + t]
    ref = g.transform(lambda x: x.shift(1).expanding().mean())
    # cold rows: league mean over games strictly earlier in the same season
    f["_y"] = f["y_" + t]
    fs = f.sort_values(["season", "gdate"])
    cum = fs.groupby("season")["_y"].transform(lambda x: x.shift(1).expanding().mean())
    cum = cum.reindex(f.index)
    f["ref_" + t] = ref.fillna(cum).fillna(f["y_" + t].mean())
    f["refabs_" + t] = (f["y_" + t] - f["ref_" + t]).abs()
f = f.drop(columns=["_y"])

f["gdate"] = pd.to_datetime(f["gdate"])
B.guard(f, "analysis frame")
assert f["gdate"].max() < pd.Timestamp("2025-01-01")
f.to_parquet(os.path.join(B.OUT, "analysis_frame.parquet"), index=False)
print("  wrote analysis_frame.parquet  shape=%s" % (f.shape,))

B.hdr("BASELINE ERROR LEVELS (pooled, 2022-2024, appeared rows)")
summ = []
for t in ["pts", "minutes", "fga"]:
    mae = f["absres_" + t].mean()
    rmae = f["refabs_" + t].mean()
    r2 = B.r2_plain(f["y_" + t], f["y_" + t] - f["resid_" + t])
    print("  %-8s n=%d  model MAE=%.4f  RMSE=%.4f  prior-mean-ref MAE=%.4f  skill=%+.4f  "
          "plain-unweighted-R2=%.4f" % (t, len(f), mae, np.sqrt(f["sqres_" + t].mean()), rmae,
                                        1 - mae / rmae, r2))
    summ.append(dict(target=t, n=int(len(f)), model_mae=float(mae),
                     model_rmse=float(np.sqrt(f["sqres_" + t].mean())),
                     ref_prior_mean_mae=float(rmae), skill_vs_ref=float(1 - mae / rmae),
                     r2_plain_unweighted=float(r2)))
json.dump(dict(provenance_by_season=prov, baselines=summ),
          open(os.path.join(B.OUT, "step1_provenance.json"), "w"), indent=2, default=str)
print("\nDONE")
