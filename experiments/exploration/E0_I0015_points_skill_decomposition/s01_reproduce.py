"""STEP 1 -- REPRODUCE D076's THREE SKILL NUMBERS FIRST.

If MINUTES +3.55% / FGA +0.12% / POINTS -0.22% do not come back, everything downstream is
meaningless and this screen STOPS.  Also runs the manifest checks, the value-based partition check
and the no-op placebo up front, so nothing later is built on an unverified input.
"""
import json
import os

import numpy as np
import pandas as pd

import psd_base as B
import screenkit as sk

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 60)

OUT = {}

B.hdr("STEP 1a -- MANIFEST CHECKS via screenkit.check_manifest (VALUES, not text)")
ART = [
    (r"data\masters\master_player.parquet", "D076 input"),
    (r"experiments\prediction_contract_v4\player_game.parquet", "D076 input"),
    (r"experiments\cbs_v15_player_oof_v5\attempt_001\predictions__player_scoring_distribution__2022.parquet", "OOF pts 2022"),
    (r"experiments\cbs_v15_player_oof_v5\attempt_001\predictions__player_scoring_distribution__2023.parquet", "OOF pts 2023"),
    (r"experiments\cbs_v15_player_oof_v5\attempt_001\predictions__player_scoring_distribution__2024.parquet", "OOF pts 2024"),
    (r"experiments\cbs_v15_player_oof_v5\attempt_001\predictions__e_minutes_given_active__2022.parquet", "OOF min 2022"),
    (r"experiments\cbs_v15_player_oof_v5\attempt_001\predictions__e_minutes_given_active__2023.parquet", "OOF min 2023"),
    (r"experiments\cbs_v15_player_oof_v5\attempt_001\predictions__e_minutes_given_active__2024.parquet", "OOF min 2024"),
    (r"experiments\cbs_v15_player_oof_v5\attempt_001\predictions__attempts_usage__2022.parquet", "OOF fga 2022"),
    (r"experiments\cbs_v15_player_oof_v5\attempt_001\predictions__attempts_usage__2023.parquet", "OOF fga 2023"),
    (r"experiments\cbs_v15_player_oof_v5\attempt_001\predictions__attempts_usage__2024.parquet", "OOF fga 2024"),
    (r"data\w1_truth\player_game_availability.csv", "REFUSED by D076"),
    (r"data\w1_truth\roster_asof.csv", "REFUSED by D076"),
    (r"experiments\minutes_baselines\test_predictions.csv", "no manifest, D076 refused"),
]
man = []
for rel, why in ART:
    r = sk.check_manifest(os.path.join(B.ROOT, rel), verbose=True)
    man.append(dict(artifact=rel, role=why, asof_granularity=r["asof_granularity"],
                    status=r["status"], usable_at_e0_e1=r["usable_at_e0_e1"],
                    fit_through_season=r["fit_through_season"],
                    filtering_helps=r["filtering_helps"]))
OUT["manifest_checks"] = man

print("\n  READING OF THE OOF ARTIFACTS (inherited from D076, restated so it is not implicit):")
print("  each per-season prediction file is asof_granularity='artifact', which is normally UNUSABLE")
print("  because filtering cannot rescue a mixed-bound file.  These are NOT mixed-bound: each file's")
print("  own fit_through_season equals its own season (2022->2022, 2023->2023, 2024->2024), so the")
print("  WHOLE artifact sits inside the 2021-2024 exploration partition and NO filtering is relied")
print("  on.  D076 made this call; this screen inherits it and would collapse with it.")
bad = [m for m in man if m["role"].startswith("OOF") and
       (m["fit_through_season"] is None or int(m["fit_through_season"]) > 2024)]
assert not bad, "an OOF artifact is bound past 2024: %s" % bad
print("  verified: every OOF artifact's own fit_through_season <= 2024.")

for m in man:
    if m["role"] in ("REFUSED by D076", "no manifest, D076 refused"):
        print("  NOT OPENED: %-52s status=%s" % (m["artifact"], m["status"]))

B.hdr("STEP 1b -- LOAD D076's FROZEN FRAME + VALUE-BASED PARTITION CHECK")
f = B.load_frame(verbose=True)
part = sk.assert_partition(f, verbose=False)
OUT["partition_check"] = {"ok": part["ok"], "season_cols": part["checked_season_cols"],
                          "date_cols": part["checked_date_cols"],
                          "skipped_name_only": part["skipped_name_only"],
                          "violations": part["violations"],
                          "method": "screenkit.assert_partition -- parses COLUMN VALUES "
                                    "(season ints, date years); never scans text or names"}
print("  partition PASS=%s  season values=%s" % (part["ok"], part["checked_season_cols"]))
print("  columns skipped because the NAME looked season-like but the VALUES are not seasons: %d"
      % len(part["skipped_name_only"]))

B.hdr("STEP 1c -- REPRODUCE THE THREE HEADLINE SKILL NUMBERS")
D076_PUBLISHED = {"pts": dict(model_mae=4.1909, ref_mae=4.1816, skill=-0.0022, r2=0.4694),
                  "minutes": dict(model_mae=5.0797, ref_mae=5.2669, skill=0.0355, r2=0.6194),
                  "fga": dict(model_mae=2.6376, ref_mae=2.6406, skill=0.0012, r2=0.5893)}
f2, nfb = B.build_references(f, verbose=True)
OUT["cold_fallback_counts"] = nfb

rep = []
print("\n  %-9s %8s %11s %11s %11s %11s %11s %11s" %
      ("target", "n", "model MAE", "ref MAE", "skill", "d(skill)", "R2 plain", "d(R2)"))
for t in ["pts", "minutes", "fga"]:
    y = f2["y_" + t].to_numpy(float)
    p = f2["%s__pred_point" % t].to_numpy(float)
    r = f2["ref_" + t].to_numpy(float)                  # D076's OWN frozen reference column
    s, mm, mr = B.skill(y, p, r)
    r2 = sk.r2_plain(y, p[:, None])                     # D069 plain unweighted, SST about unwtd mean
    pub = D076_PUBLISHED[t]
    print("  %-9s %8d %11.4f %11.4f %+11.6f %+11.2e %11.4f %+11.2e"
          % (t, len(y), mm, mr, s, s - pub["skill"], r2, r2 - pub["r2"]))
    rep.append(dict(target=t, n=int(len(y)), model_mae=mm, ref_mae=mr, skill=s,
                    published_skill=pub["skill"], abs_delta_skill=abs(s - pub["skill"]),
                    published_model_mae=pub["model_mae"],
                    abs_delta_model_mae=abs(mm - pub["model_mae"]),
                    published_ref_mae=pub["ref_mae"],
                    abs_delta_ref_mae=abs(mr - pub["ref_mae"]),
                    r2_plain_unweighted=r2, published_r2=pub["r2"],
                    abs_delta_r2=abs(r2 - pub["r2"])))

# independent rebuild of the reference from scratch (does not read D076's ref_ columns)
print("\n  INDEPENDENT REBUILD of the same prior-mean reference (this screen's own code path):")
for t in ["pts", "minutes", "fga"]:
    y = f2["y_" + t].to_numpy(float)
    p = f2["%s__pred_point" % t].to_numpy(float)
    rx = f2["refX_" + t].to_numpy(float)
    s, mm, mr = B.skill(y, p, rx)
    d = float(np.max(np.abs(f2["ref_" + t] - f2["refX_" + t])))
    print("    %-9s skill=%+.6f  max|refX - D076 ref| = %.3e" % (t, s, d))
    rep[[x["target"] for x in rep].index(t)]["independent_rebuild_skill"] = s
    rep[[x["target"] for x in rep].index(t)]["max_abs_ref_rebuild_diff"] = d

maxd = max(x["abs_delta_skill"] for x in rep)
REPRODUCED = maxd < 5e-5          # published to 2 decimal places in percent -> 5e-5 on the fraction
print("\n  MAX |delta skill| vs D076's published values = %.3e  ->  REPRODUCED = %s"
      % (maxd, REPRODUCED))
if not REPRODUCED:
    raise SystemExit("STOP: D076's skill numbers did NOT reproduce. Everything downstream is void.")
OUT["reproduction"] = rep
OUT["reproduced"] = bool(REPRODUCED)

B.hdr("STEP 1d -- LEAK PROBE ON THE REFERENCE (trap 2: READ THE CONSTRUCTION, NOT THE LABEL)")
# The reference is named "prior mean".  Names lie.  Probe it against a deliberately RETROSPECTIVE
# baseline (the player's FULL-season mean, which reads the future) to confirm the probe fires on the
# retrospective one and NOT on ours.
f2["_loo_pts"] = f2.groupby(["season", "player_id"], sort=False)["y_pts"].transform("mean")
pr = sk.future_leakage_probe(f2, baseline_col="_loo_pts", clean_col="ref_pts",
                             entity_col=["season", "player_id"], date_col="gdate",
                             outcome_col="y_pts", verbose=True)
pr2 = sk.future_leakage_probe(f2, baseline_col="ref_pts", clean_col="_loo_pts",
                              entity_col=["season", "player_id"], date_col="gdate",
                              outcome_col="y_pts", verbose=True)
OUT["future_leakage_probe"] = {
    "retrospective_control__full_season_mean": {k: v for k, v in pr.items() if k != "draws"},
    "our_prior_mean_reference": {k: v for k, v in pr2.items() if k != "draws"},
}
for rt in ["ppm", "fpm"]:
    p3 = sk.future_leakage_probe(f2, baseline_col="refA_" + rt, clean_col="refB_" + rt,
                                 entity_col=["season", "player_id"], date_col="gdate",
                                 outcome_col="r_" + rt, verbose=True)
    OUT["future_leakage_probe"]["rate_" + rt + "_refA_vs_refB"] = {
        k: v for k, v in p3.items() if k != "draws"}

B.hdr("STEP 1e -- NO-OP PLACEBO (screenkit.noop_placebo), OBSERVED sd REPORTED")
def stat_points_skill(d):
    return B.skill(d["y_pts"].to_numpy(float), d["pts__pred_point"].to_numpy(float),
                   d["ref_pts"].to_numpy(float))[0]

nop_identity = sk.noop_placebo(stat_points_skill, f2, 200, transform=None, verbose=True)

def relabel_and_recompute(d, rng):
    """THE DEFECTIVE CONTROL, run on purpose: permute the block KEY, then compute a statistic that
    never consults the shuffled label.  Expected verdict: CONFIRMED NO-OP."""
    dd = d.copy()
    dd["player_id"] = rng.permutation(dd["player_id"].to_numpy())
    return dd

nop_relabel = sk.noop_placebo(stat_points_skill, f2, 200, transform=relabel_and_recompute,
                              verbose=True)

def real_shuffle(d, rng):
    """A GENUINE control: shuffle which row receives which already-computed model forecast, inside
    season.  Must NOT be flagged as a no-op."""
    dd = d.copy()
    v = dd["pts__pred_point"].to_numpy(float).copy()
    for s in dd["season"].unique():
        m = np.where(dd["season"].to_numpy() == s)[0]
        v[m] = v[m][rng.permutation(len(m))]
    dd["pts__pred_point"] = v
    return dd

nop_real = sk.noop_placebo(stat_points_skill, f2, 200, transform=real_shuffle, verbose=True)

OUT["noop_placebo"] = {
    "statistic": "points skill vs D076 prior-mean reference",
    "identity_transform": {k: float(v) if isinstance(v, (int, float, np.floating)) else v
                           for k, v in nop_identity.items() if k != "draws"},
    "defective_relabel_key_and_recompute": {k: float(v) if isinstance(v, (int, float, np.floating))
                                            else v for k, v in nop_relabel.items() if k != "draws"},
    "genuine_shuffle_control": {k: float(v) if isinstance(v, (int, float, np.floating)) else v
                                for k, v in nop_real.items() if k != "draws"},
    "observed_sd_identity": float(nop_identity["sd"]),
    "observed_sd_defective_relabel": float(nop_relabel["sd"]),
    "observed_sd_genuine_shuffle": float(nop_real["sd"]),
}
pd.DataFrame({"identity": nop_identity["draws"], "defective_relabel": nop_relabel["draws"],
              "genuine_shuffle": nop_real["draws"]}).to_csv(
    os.path.join(B.OUT, "noop_placebo_draws.csv"), index=False)

f2.to_parquet(os.path.join(B.OUT, "decomp_frame.parquet"), index=False)
print("\n  wrote decomp_frame.parquet  shape=%s" % (f2.shape,))
json.dump(OUT, open(os.path.join(B.OUT, "_s01.json"), "w"), indent=2, default=str)
print("DONE s01")
