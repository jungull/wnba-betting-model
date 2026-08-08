"""
STEP 1 -- audit the actual configuration that governs the wls_r2 bias.

Reads ONLY copies (inside this directory) of the frozen E0/E1 screen outputs.
Nothing outside this directory is written.

Partition: 2021-2024 ONLY, verified on COLUMN VALUES.
"""
import json
import numpy as np
import pandas as pd

D = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\exploration\E1_I0009_r2_rerun"
EXPLORATION_SEASONS = [2021, 2022, 2023, 2024]

out = {}

# ---------------------------------------------------------------- partition
f1 = pd.read_csv(f"{D}/player_game_analysis.csv", parse_dates=["game_date"])
t1 = pd.read_csv(f"{D}/team_game_defense.csv", parse_dates=["game_date"])
f0 = pd.read_csv(f"{D}/E0_player_game_analysis.csv", parse_dates=["game_date"])
t0 = pd.read_csv(f"{D}/E0_team_game_defense.csv", parse_dates=["game_date"])

part = {}
for name, d in (("E1_player_game_analysis", f1), ("E1_team_game_defense", t1),
                ("E0_player_game_analysis", f0), ("E0_team_game_defense", t0)):
    seasons = sorted(int(x) for x in d["season"].unique())
    years = sorted(int(x) for x in d["game_date"].dt.year.unique())
    assert set(seasons).issubset(set(EXPLORATION_SEASONS)), f"PARTITION VIOLATION {name}"
    assert set(years).issubset({2021, 2022, 2023, 2024}), f"PARTITION VIOLATION {name} date"
    part[name] = dict(rows=int(len(d)), season_column_values=seasons, game_date_years=years)
    print(f"  {name:26s} rows={len(d):6d} seasons={seasons} date_years={years}")
out["partition_verification"] = dict(
    method="season column VALUES and game_date.dt.year VALUES; no byte/regex scan",
    detail=part, holdout_2025_2026_touched=False)
print("PARTITION VERIFIED on column values only (2021-2024).\n")

# ---------------------------------------------------------------- manifests
out["manifest_check"] = dict(
    inputs_of_build_data=[
        "experiments/player_program/turnover_targets_v1/player_turnover_targets_v1.parquet",
        "experiments/player_program/possessions_v2/possessions_raw_v2.parquet"],
    sibling_manifest_json_present=False,
    checked_how="directory listing of both parquet directories; no <artifact>.manifest.json exists",
    note=("No sibling manifest exists for either input, so asof_granularity cannot be read. "
          "Both are raw row-per-game / row-per-possession tallies with an explicit season column "
          "and no fitted cross-season parameter, so row-level partition filtering bounds them. "
          "This is a PROGRAM GAP, not a clean pass: the manifest rule cannot be executed as "
          "written for these two artifacts. This measurement re-uses the FROZEN CSVs the screens "
          "already wrote, which are themselves verified 2021-2024 on column values."))

# ---------------------------------------------------------------- (b) weights
def wstats(w, label):
    s = dict(variable="realised_off_possessions", n=int(len(w)),
             min=float(w.min()), max=float(w.max()), mean=float(w.mean()),
             sd=float(w.std(ddof=1)), cv=float(w.std(ddof=1) / w.mean()),
             max_over_min=float(w.max() / w.min()) if w.min() > 0 else None,
             p01=float(np.percentile(w, 1)), p99=float(np.percentile(w, 99)),
             n_zero=int((w == 0).sum()), uniform=bool(np.allclose(w, w[0])))
    print(f"  weights [{label}] var={s['variable']} n={s['n']} min={s['min']:.4f} max={s['max']:.4f} "
          f"mean={s['mean']:.4f} sd={s['sd']:.4f} cv={s['cv']:.4f} max/min={s['max_over_min']:.2f}")
    return s

w1 = f1["realised_off_possessions"].to_numpy(float)
w0 = f0["realised_off_possessions"].to_numpy(float)
print("(b) WEIGHT DISPERSION")
out["weights"] = dict(E1=wstats(w1, "E1"), E0=wstats(w0, "E0"))

# ---------------------------------------------------------------- (c) response
def ystats(y, w, label):
    s = dict(variable="turnovers_per_100_off_poss", n=int(len(y)),
             mean=float(y.mean()), sd=float(y.std(ddof=1)),
             mean_over_sd=float(y.mean() / y.std(ddof=1)),
             weighted_mean=float(np.average(y, weights=w)),
             min=float(y.min()), max=float(y.max()),
             frac_zero=float((y == 0).mean()), centered=bool(abs(y.mean()) < 1e-9))
    print(f"  response [{label}] mean={s['mean']:.5f} sd={s['sd']:.5f} "
          f"mean/sd={s['mean_over_sd']:.5f} wmean={s['weighted_mean']:.5f} centered={s['centered']}")
    return s

y1 = f1["turnovers_per_100_off_poss"].to_numpy(float)
y0 = f0["turnovers_per_100_off_poss"].to_numpy(float)
print("\n(c) RESPONSE CENTERING")
out["response"] = dict(E1=ystats(y1, w1, "E1"), E0=ystats(y0, w0, "E0"))

# also correlation between y and w, which drives the alignment argument
out["response"]["corr_y_sqrtw_E1"] = float(np.corrcoef(y1, np.sqrt(w1))[0, 1])
out["response"]["corr_y_sqrtw_E0"] = float(np.corrcoef(y0, np.sqrt(w0))[0, 1])
print(f"  corr(y, sqrt(w)) E1 = {out['response']['corr_y_sqrtw_E1']:+.5f}")

# ------------------------------------------------- (a)+(analytic prediction)
def sst_defective(y, w):
    yw = np.sqrt(w) * y
    return float(((yw - yw.mean()) ** 2).sum())

def sst_standard_weighted(y, w):
    mu = np.average(y, weights=w)
    return float((w * (y - mu) ** 2).sum())

def sst_plain(y):
    return float(((y - y.mean()) ** 2).sum())

pred = {}
for label, y, w, season in (("E1", y1, w1, f1["season"].to_numpy(int)),
                            ("E0", y0, w0, f0["season"].to_numpy(int))):
    sd_ = sst_defective(y, w); ss_ = sst_standard_weighted(y, w)
    row = dict(sst_defective=sd_, sst_standard_weighted=ss_,
               predicted_ratio_standard_over_defective=ss_ / sd_,
               predicted_bias_pct=100.0 * (sd_ / ss_ - 1.0) * -1.0)
    # per season (the masks the screens actually fit on)
    row["per_season"] = {}
    for s in EXPLORATION_SEASONS:
        m = season == s
        a, b = sst_defective(y[m], w[m]), sst_standard_weighted(y[m], w[m])
        row["per_season"][str(s)] = dict(sst_defective=a, sst_standard_weighted=b, ratio=b / a)
    pred[label] = row
    print(f"\n(a/analytic) {label}: SST_defective={sd_:.6e}  SST_standard_w={ss_:.6e}  "
          f"ratio(std/def)={ss_/sd_:.6f}  -> reported dR2 is {100*(1-ss_/sd_):.2f}% BELOW standard")
out["analytic_prediction"] = pred

# ------------------------------- the two governing factors, tested directly
print("\n  MECHANISM CHECKS (E1 frame):")
uni = np.ones_like(w1)
r_uniform = sst_standard_weighted(y1, uni) / sst_defective(y1, uni)
yc = y1 - y1.mean()
r_centered = sst_standard_weighted(yc, w1) / sst_defective(yc, w1)
print(f"    uniform weights (w=1)        -> ratio = {r_uniform:.10f}")
print(f"    centered response (mean 0)   -> ratio = {r_centered:.10f}")
print(f"    actual w, actual y           -> ratio = {pred['E1']['predicted_ratio_standard_over_defective']:.10f}")
out["mechanism_checks"] = dict(
    ratio_with_uniform_weights=float(r_uniform),
    ratio_with_centered_response_real_weights=float(r_centered),
    ratio_actual=float(pred["E1"]["predicted_ratio_standard_over_defective"]),
    interpretation=("The defect vanishes (ratio 1.0) if EITHER weights are uniform OR the response "
                    "is centered. Both are present here: w is possessions (dispersed) and y is a "
                    "strictly-positive rate with a large mean-to-sd ratio."))

# ---------------------------------------------------------------- (a) source
out["defective_helper_source"] = dict(
    E0_file=("experiments/exploration/E0_I0009_additive_pressure/analyze.py"),
    E0_function="wls_r2", E0_lines="40-48",
    E0_defect_line="47: sst = float(((yw - yw.mean()) ** 2).sum())   # yw = sqrt(w)*y",
    E0_used_by="delta_r2 (lines 55-62) -> EVERY dR2 E0 published",
    E1_file=("experiments/exploration/E1_I0009_additive_pressure/analyze.py"),
    E1_function_name_note=("E1 has NO function named wls_r2. E1's headline helper is r2_in "
                           "(lines 68-72), which is the STANDARD weighted R2: "
                           "1 - sum(w*r^2)/sum(w*(y-ybar_w)^2) with ybar_w = np.average(y, weights=w)."),
    E1_defective_copy=("delta_r2_e0convention, lines 220-228, inline r2(): "
                       "1 - r@r / ((yw - yw.mean())**2).sum(). Used ONLY in the E0-reconciliation "
                       "block (lines 230-249). It touches NO E1 headline number."),
    E1_oos_helper=("oos_delta, lines 281-301: SST = sum(w_test*(y_test - ybar_train_weighted)^2) "
                   "-- standard weighted SST about the TRAIN weighted mean, NOT defective."),
    CONCLUSION=("The task premise that BOTH screens carry the defect in their published numbers is "
                "INCORRECT for E1. E0's published numbers are defective; E1's are already standard "
                "weighted. The headline +0.004003 is an E1 number and is NOT defective."))

with open(f"{D}/step1_audit.json", "w") as fh:
    json.dump(out, fh, indent=2, default=float)
print("\nwrote step1_audit.json")
