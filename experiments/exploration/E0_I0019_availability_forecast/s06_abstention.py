"""E0_I0019 -- s06: DOES `p_active` INTERACT WITH D076's ABSTENTION RULE?

D076's rule declines to forecast player-games below a prior-appearance threshold, and is measured
on MINUTES skill against a point-in-time prior-mean reference.  `p_active` is a different axis.
Are they the same rule wearing two names, or complementary?

Two abstention curves are produced:
  (1) on AVAILABILITY itself -- Brier skill vs the rich reference R3 as coverage falls;
  (2) on MINUTES -- D076's own metric, 1 - MAE_model/MAE_ref on APPEARED rows, so the answer is
      directly comparable to the numbers in D076's ruling.
"""
import json
import os

import numpy as np
import pandas as pd

import av_base as B
import screenkit as sk

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 140)
OUT = B.OUT
REP = {}

F = pd.read_parquet(os.path.join(OUT, "analysis_frame.parquet"))
B.guard(F, "analysis frame reload")

# ------------------------------------------------------------------ minutes forecasts
B.hdr("s06A -- LOAD THE MINUTES FORECAST (same arm, same walk-forward, same manifest discipline)")
mins = []
for s in B.SCREEN_SEASONS:
    p = os.path.join(B.ARM_DIR["v15"], "predictions__e_minutes_given_active__%d.parquet" % s)
    m = json.load(open(p + ".manifest.json"))
    kit = sk.check_manifest(p)
    print("  season %d  asof=%-9s fit_seasons=%-18s fit_through_season=%s  kit status=%s"
          % (s, m.get("asof_granularity"), m.get("fit_seasons"), m.get("fit_through_season"),
             kit.get("status")))
    assert int(m["fit_through_season"]) <= 2024
    d = pd.read_parquet(p)[["row_uid", "pred_point", "is_fallback", "is_cold_start",
                            "n_prior_games"]]
    d.columns = ["row_uid", "min__pred_point", "min__is_fallback", "min__is_cold_start",
                 "min__n_prior_games"]
    mins.append(d)
MIN = pd.concat(mins, ignore_index=True)
F = F.merge(MIN, on="row_uid", how="left")
print("  minutes forecast attached to %d / %d rows" % (int(F["min__pred_point"].notna().sum()),
                                                       len(F)))
B.guard(F, "frame with minutes forecast")

# ------------------------------------------------------------------ availability abstention
B.hdr("s06B -- ABSTENTION ON AVAILABILITY (Brier skill vs the RICH reference R3)")
y = F["y"].to_numpy(float)
p = F["v15__pred_point"].to_numpy(float)
R3 = F["R3"].to_numpy(float)
COV = [1.00, 0.95, 0.90, 0.80, 0.75, 0.60, 0.50, 0.40, 0.25]


def curve(order_desc, label, yv, pv, rv, cov=COV):
    """order_desc: larger = DECLINE FIRST.  Returns the skill-vs-coverage curve."""
    o = np.argsort(-np.asarray(order_desc, float), kind="mergesort")
    rows = []
    n = len(o)
    for c in cov:
        keep = o[int(round(n * (1 - c))):]
        if len(keep) < 200:
            continue
        bm = float(np.mean((yv[keep] - pv[keep]) ** 2))
        br = float(np.mean((yv[keep] - rv[keep]) ** 2))
        rows.append(dict(rule=label, coverage=c, n=len(keep), brier_model=bm, brier_ref=br,
                         bss=1 - bm / br, base_rate=float(yv[keep].mean())))
    return rows


rules_av = {
    "thin depth first (D076 axis: -pl_games_prior)": -F["pl_games_prior"].fillna(-1).to_numpy(float),
    "model uncertainty first (mdl_pred_entropy)": F["mdl_pred_entropy"].to_numpy(float),
    "boundary p_active first (|p-0.5| ascending)": -np.abs(p - 0.5),
    "low p_active first (-p_active)": -p,
    "is_fallback first": F["mdl_is_fallback"].to_numpy(float),
}
av_rows = []
for lab, ordv in rules_av.items():
    av_rows += curve(ordv, lab, y, p, R3)
AV = pd.DataFrame(av_rows)
print(AV.pivot_table(index="rule", columns="coverage", values="bss")
      .to_string(float_format=lambda v: "%+.4f" % v))
AV.to_csv(os.path.join(OUT, "abstention_availability.csv"), index=False)
REP["availability_abstention"] = AV.to_dict("records")

# ------------------------------------------------------------------ minutes abstention (D076)
B.hdr("s06C -- ABSTENTION ON MINUTES, D076's OWN METRIC (appeared rows, 1 - MAE/MAE_ref)")
M = F[(F["y"] == 1.0) & F["min__pred_point"].notna()].copy()
M["y_min"] = pd.to_numeric(M["box_minutes"], errors="coerce").astype(float)
M = M.sort_values(["season", "player_id", "gdate", "game_id"]).reset_index(drop=True)
g = M.groupby(["season", "player_id"], sort=False)["y_min"]
ref = g.transform(lambda x: x.shift(1).expanding().mean())
Md = M.sort_values(["season", "gdate"])
cum = Md.groupby("season")["y_min"].transform(lambda x: x.shift(1).expanding().mean())
cum = cum.reindex(M.index)
M["ref_min"] = ref.fillna(cum).fillna(M["y_min"].mean())
M["abs_model"] = (M["y_min"] - M["min__pred_point"]).abs()
M["abs_ref"] = (M["y_min"] - M["ref_min"]).abs()
print("  appeared rows with a minutes forecast: %d" % len(M))
print("  pooled: model MAE=%.4f  prior-mean-ref MAE=%.4f  SKILL=%+.5f"
      % (M["abs_model"].mean(), M["abs_ref"].mean(),
         1 - M["abs_model"].mean() / M["abs_ref"].mean()))
print("  (D076 reported pooled minutes skill +0.03555 on 13,879 rows -- reproduced here as a")
print("   provenance cross-check, not as a new claim.)")
REP["minutes_pooled"] = dict(n=int(len(M)), mae_model=float(M["abs_model"].mean()),
                             mae_ref=float(M["abs_ref"].mean()),
                             skill=float(1 - M["abs_model"].mean() / M["abs_ref"].mean()))


def mcurve(order_desc, label, cov=COV):
    o = np.argsort(-np.asarray(order_desc, float), kind="mergesort")
    am = M["abs_model"].to_numpy(float)
    ar = M["abs_ref"].to_numpy(float)
    rows = []
    n = len(o)
    for c in cov:
        keep = o[int(round(n * (1 - c))):]
        if len(keep) < 200:
            continue
        rows.append(dict(rule=label, coverage=c, n=len(keep), mae_model=float(am[keep].mean()),
                         mae_ref=float(ar[keep].mean()),
                         skill=float(1 - am[keep].mean() / ar[keep].mean())))
    return rows


pM = M["v15__pred_point"].to_numpy(float)
rules_min = {
    "D076: thin depth first (-pl_games_prior)": -M["pl_games_prior"].fillna(-1).to_numpy(float),
    "D076: is_fallback first": M["mdl_is_fallback"].to_numpy(float),
    "NEW: low p_active first": -pM,
    "NEW: boundary p_active first (|p-0.5| asc)": -np.abs(pM - 0.5),
    "NEW: high p_active entropy first": M["mdl_pred_entropy"].to_numpy(float),
    "COMBINED: rank(-depth) + rank(entropy)": (
        pd.Series(-M["pl_games_prior"].fillna(-1).to_numpy(float)).rank().to_numpy() +
        pd.Series(M["mdl_pred_entropy"].to_numpy(float)).rank().to_numpy()),
}
mr = []
for lab, ordv in rules_min.items():
    mr += mcurve(ordv, lab)
MC = pd.DataFrame(mr)
print("\n  MINUTES SKILL vs COVERAGE:")
print(MC.pivot_table(index="rule", columns="coverage", values="skill")
      .to_string(float_format=lambda v: "%+.5f" % v))
MC.to_csv(os.path.join(OUT, "abstention_minutes.csv"), index=False)
REP["minutes_abstention"] = MC.to_dict("records")

B.hdr("s06D -- THE DECISIVE TEST: DOES p_active ADD ANYTHING *WITHIN* DEPTH STRATA?")
print("  If p_active and D076's depth rule are the same rule wearing two names, then ordering by")
print("  p_active INSIDE a depth stratum should buy nothing.  Split the appeared rows into depth")
print("  quintiles (D076's own cut) and run the abstention curve on p_active entropy inside each.")
M["depth_q"] = pd.qcut(M["pl_games_prior"].rank(method="first"), 5, labels=False,
                       duplicates="drop")
inner = []
for q, gg in M.groupby("depth_q"):
    am = gg["abs_model"].to_numpy(float)
    ar = gg["abs_ref"].to_numpy(float)
    ent = gg["mdl_pred_entropy"].to_numpy(float)
    o = np.argsort(-ent, kind="mergesort")
    base = 1 - am.mean() / ar.mean()
    row = dict(depth_quintile=int(q), n=len(gg),
               median_games_prior=float(gg["pl_games_prior"].median()),
               skill_at_full_coverage=base)
    for c in [0.90, 0.75, 0.60]:
        keep = o[int(round(len(o) * (1 - c))):]
        row["skill_at_cov_%.2f" % c] = float(1 - am[keep].mean() / ar[keep].mean())
    row["gain_from_p_active_at_075"] = row["skill_at_cov_0.75"] - base
    inner.append(row)
IN = pd.DataFrame(inner)
print(IN.to_string(index=False, float_format=lambda v: "%.5f" % v))
IN.to_csv(os.path.join(OUT, "abstention_p_active_within_depth_quintiles.csv"), index=False)
REP["within_depth_quintiles"] = IN.to_dict("records")

print("\n  correlation between the two abstention axes on appeared rows:")
cc = np.corrcoef(M["pl_games_prior"].fillna(0).to_numpy(float),
                 M["mdl_pred_entropy"].to_numpy(float))[0, 1]
cc2 = np.corrcoef(M["pl_games_prior"].fillna(0).to_numpy(float), pM)[0, 1]
print("    corr(pl_games_prior, p_active entropy) = %+.4f" % cc)
print("    corr(pl_games_prior, p_active)         = %+.4f" % cc2)
REP["axis_correlation"] = dict(corr_depth_entropy=float(cc), corr_depth_p_active=float(cc2))

B.hdr("s06E -- AND THE ONE THAT MATTERS FOR BETTING: VOID RISK AT EACH p_active LEVEL")
print("  Player props are typically VOIDED on a no-show, so the operative quantity is the")
print("  probability of a void, and whether it is well estimated.")
cuts = [(0.0, 0.5), (0.5, 0.8), (0.8, 0.9), (0.9, 0.95), (0.95, 1.01)]
vr = []
for lo, hi in cuts:
    m = (p >= lo) & (p < hi)
    if m.sum() == 0:
        continue
    vr.append(dict(p_active_band="[%.2f,%.2f)" % (lo, hi), n=int(m.sum()),
                   share_of_rows=float(m.mean()), predicted_void=float(1 - p[m].mean()),
                   actual_void=float(1 - y[m].mean()),
                   void_gap_pred_minus_actual=float((1 - p[m].mean()) - (1 - y[m].mean()))))
VR = pd.DataFrame(vr)
print(VR.to_string(index=False, float_format=lambda v: "%.4f" % v))
VR.to_csv(os.path.join(OUT, "void_risk_bands.csv"), index=False)
REP["void_risk"] = VR.to_dict("records")

json.dump(REP, open(os.path.join(OUT, "s06_abstention.json"), "w"), indent=2, default=str)
print("\nwrote abstention_availability.csv, abstention_minutes.csv,")
print("      abstention_p_active_within_depth_quintiles.csv, void_risk_bands.csv, s06_abstention.json")
print("DONE")
