"""E0_I0019 -- s05: repair the per-cell p labelling (DEF-4), report PRACTICAL SPREADS, and
DECOMPOSE every family-wise survivor against its own components (constraint 4 / D087).

No permutation is re-run: the draws saved by s04 are re-read from permutation_nulls.npz.
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
CJ = json.load(open(os.path.join(OUT, "candidates.json")))
CANDS = CJ["candidates"]
DEPNAMES = list(CJ["dependents"].keys())
FAMOF = {c: fam for fam, cs in CJ["families"].items() for c in cs}
LV = pd.read_csv(os.path.join(OUT, "grouping_levels.csv"))
VSB = dict(zip(LV["candidate"], LV["var_share_between_primary_block"]))
SCHEME_PRIM = dict(zip(LV["candidate"], LV["scheme_primary"]))
IDENT = dict(zip(LV["candidate"], LV["secondary_is_identity"]))
z = np.load(os.path.join(OUT, "permutation_nulls.npz"))
OLD = pd.read_csv(os.path.join(OUT, "screen_results.csv"))
N_DRAWS = z["maxt_primary"].shape[0]

B.hdr("s05A -- REPAIRED PER-CELL P-VALUES (DEF-4): two schemes, two questions, no max()")
rows = []
for ci, c in enumerate(CANDS):
    prim = SCHEME_PRIM[c]
    sec = "player_within" if prim == "player_between" else "teamseason_between"
    for di, dname in enumerate(DEPNAMES):
        o = OLD[(OLD["candidate"] == c) & (OLD["dependent"] == dname)].iloc[0]
        t = o["t"]
        rec = dict(candidate=c, family=FAMOF[c], dependent=dname, beta=o["beta"], t=t, n=o["n"],
                   var_share_between=VSB[c], scheme_between=prim,
                   p_familywise=o["p_familywise"])
        for tag, s in [("between", prim), ("within", sec), ("row", "row")]:
            a = z["null_%s" % s][:, ci, di]
            a = a[np.isfinite(a)]
            if len(a) == 0 or not np.isfinite(t):
                rec["p_" + tag] = np.nan
                rec["nullmean_" + tag] = np.nan
                rec["nullsd_" + tag] = np.nan
                continue
            rec["p_" + tag] = float((1 + (np.abs(a) >= abs(t)).sum()) / (1 + len(a)))
            rec["nullmean_" + tag] = float(a.mean())
            rec["nullsd_" + tag] = float(a.std())
        rec["within_null_degenerate"] = bool(
            np.isfinite(rec.get("nullsd_within", np.nan)) and rec["nullsd_within"] > 0 and
            abs(rec["nullmean_within"]) / rec["nullsd_within"] > 5.0)
        rec["inflation_between_over_row"] = (rec["nullsd_between"] / rec["nullsd_row"]
                                             if rec.get("nullsd_row") else np.nan)
        rows.append(rec)
RES = pd.DataFrame(rows)
RES.to_csv(os.path.join(OUT, "screen_results_repaired.csv"), index=False)
print("  within-scheme nulls flagged DEGENERATE (shuffle barely moves the statistic): %d / %d"
      % (int(RES["within_null_degenerate"].sum()), len(RES)))
print("  per-cell sd inflation (between / row): median=%.3fx range %.3f-%.3f"
      % (RES["inflation_between_over_row"].median(), RES["inflation_between_over_row"].min(),
         RES["inflation_between_over_row"].max()))

B.hdr("s05B -- ATTRITION, STATED HONESTLY")
skill_deps = ["skill_vs_R1", "skill_vs_R2", "skill_vs_R3", "llskill_vs_R3"]
rich_deps = ["skill_vs_R3", "llskill_vs_R3"]
att = dict(
    cells=len(RES),
    p05_row_naive=int((RES["p_row"] < 0.05).sum()),
    p05_between=int((RES["p_between"] < 0.05).sum()),
    p05_within_nondegenerate=int(((RES["p_within"] < 0.05) &
                                  (~RES["within_null_degenerate"])).sum()),
    familywise=int((RES["p_familywise"] < 0.05).sum()),
    familywise_candidates=int(RES.loc[RES["p_familywise"] < 0.05, "candidate"].nunique()),
    familywise_on_skill=int(((RES["p_familywise"] < 0.05) &
                             RES["dependent"].isin(skill_deps)).sum()),
    familywise_on_RICH_reference=int(((RES["p_familywise"] < 0.05) &
                                      RES["dependent"].isin(rich_deps)).sum()),
    familywise_on_RICH_candidates=int(RES.loc[(RES["p_familywise"] < 0.05) &
                                              RES["dependent"].isin(rich_deps),
                                              "candidate"].nunique()),
    negative_controls_surviving=int(((RES["family"] == "Z_negative_control") &
                                     (RES["p_familywise"] < 0.05)).sum()),
)
for k, v in att.items():
    print("    %-36s %d" % (k, v))
REP["attrition"] = att

print("\n  the ONLY cells that clear FAMILY-WISE against the RICH walk-forward reference R3:")
rich = RES[(RES["p_familywise"] < 0.05) & RES["dependent"].isin(rich_deps)].sort_values(
    "t", key=lambda s: s.abs(), ascending=False)
print(rich[["candidate", "family", "dependent", "t", "n", "var_share_between", "p_between",
            "p_within", "within_null_degenerate", "p_familywise"]]
      .to_string(index=False, float_format=lambda v: "%.4f" % v))
REP["familywise_vs_rich_reference"] = rich.to_dict("records")

B.hdr("s05C -- PRACTICAL SPREAD: decile tables for every family-wise survivor candidate")
y = F["y"].to_numpy(float)
p = F["v15__pred_point"].to_numpy(float)
R2 = F["R2"].to_numpy(float)
R3 = F["R3"].to_numpy(float)
brier_m = (y - p) ** 2
brier_R3 = (y - R3) ** 2
brier_R2 = (y - R2) ** 2

surv_c = sorted(RES.loc[RES["p_familywise"] < 0.05, "candidate"].unique())
sp_rows = []
for c in surv_c:
    v = pd.to_numeric(F[c], errors="coerce")
    m = np.isfinite(v)
    if m.sum() < 500:
        continue
    q = pd.qcut(v[m].rank(method="first"), 10, labels=False, duplicates="drop")
    d = pd.DataFrame(dict(dec=q.to_numpy(), y=y[m.to_numpy()], p=p[m.to_numpy()],
                          bm=brier_m[m.to_numpy()], b3=brier_R3[m.to_numpy()],
                          b2=brier_R2[m.to_numpy()], v=v[m].to_numpy()))
    g = d.groupby("dec").agg(n=("y", "size"), cand_med=("v", "median"),
                             obs_rate=("y", "mean"), mean_pred=("p", "mean"),
                             brier_model=("bm", "mean"), brier_R3=("b3", "mean"),
                             brier_R2=("b2", "mean"))
    g["calib_gap"] = g["obs_rate"] - g["mean_pred"]
    g["bss_vs_R3"] = 1.0 - g["brier_model"] / g["brier_R3"]
    g["bss_vs_R2"] = 1.0 - g["brier_model"] / g["brier_R2"]
    g.insert(0, "candidate", c)
    g = g.reset_index()
    sp_rows.append(g)
    lo, hi = g.iloc[0], g.iloc[-1]
    sp_rows.append(None) if False else None
SPREAD = pd.concat(sp_rows, ignore_index=True)
SPREAD.to_csv(os.path.join(OUT, "decile_tables.csv"), index=False)

summ = []
for c, g in SPREAD.groupby("candidate"):
    summ.append(dict(candidate=c, family=FAMOF[c],
                     calib_gap_min=g["calib_gap"].min(), calib_gap_max=g["calib_gap"].max(),
                     calib_gap_spread=g["calib_gap"].max() - g["calib_gap"].min(),
                     bss_vs_R3_min=g["bss_vs_R3"].min(), bss_vs_R3_max=g["bss_vs_R3"].max(),
                     bss_vs_R3_spread=g["bss_vs_R3"].max() - g["bss_vs_R3"].min(),
                     bss_vs_R2_min=g["bss_vs_R2"].min(), bss_vs_R2_max=g["bss_vs_R2"].max(),
                     bss_vs_R2_spread=g["bss_vs_R2"].max() - g["bss_vs_R2"].min(),
                     worst_decile_bss_vs_R3=g.loc[g["bss_vs_R3"].idxmin(), "dec"],
                     n_min=int(g["n"].min())))
SUM = pd.DataFrame(summ).sort_values("bss_vs_R3_spread", ascending=False)
print("  PRACTICAL SPREAD, ordered by how much Brier skill against the RICH reference R3 varies")
print("  between the best and worst decile of the candidate:")
print(SUM[["candidate", "family", "bss_vs_R3_min", "bss_vs_R3_max", "bss_vs_R3_spread",
           "calib_gap_min", "calib_gap_max", "calib_gap_spread"]]
      .to_string(index=False, float_format=lambda v: "%.4f" % v))
SUM.to_csv(os.path.join(OUT, "practical_spread_summary.csv"), index=False)
REP["practical_spread"] = SUM.to_dict("records")

print("\n  Full decile table for the three widest spreads on skill-vs-R3:")
for c in SUM["candidate"].head(3):
    print("\n  --- %s ---" % c)
    print(SPREAD[SPREAD["candidate"] == c][
        ["dec", "n", "cand_med", "obs_rate", "mean_pred", "calib_gap", "brier_model",
         "brier_R3", "bss_vs_R3"]].to_string(index=False, float_format=lambda v: "%.4f" % v))

B.hdr("s05D -- DECOMPOSITION OF SURVIVORS AGAINST THEIR OWN COMPONENTS (D087)")
print("  A candidate that shows differential skill against R3 may be doing nothing but")
print("  re-entering R3's own blind spot.  For each survivor on a RICH-reference dependent, add")
print("  the candidate ITSELF to the reference and ask whether the differential survives.")
dec_rows = []
for c in sorted(rich["candidate"].unique()):
    v = pd.to_numeric(F[c], errors="coerce")
    m = np.isfinite(v).to_numpy()
    yy, pp, rr = y[m], p[m], R3[m]
    vv = v[m].to_numpy(float)
    # R3+ : R3 augmented with the candidate, by OLS on the SCORED rows.  This is deliberately
    # GENEROUS to the reference (it is fitted in-sample, the model is not), which is the right
    # direction for a blind-spot test: if p_active still wins against an in-sample-fitted
    # augmented reference, the increment is not the reference's blind spot.
    X = np.column_stack([np.ones(m.sum()), rr, vv])
    bb, *_ = np.linalg.lstsq(X, yy, rcond=None)
    r3p = np.clip(X @ bb, 1e-6, 1 - 1e-6)
    dec_rows.append(dict(
        candidate=c, n=int(m.sum()),
        brier_model=B.brier(yy, pp), brier_R3=B.brier(yy, rr),
        brier_R3_plus_candidate=B.brier(yy, r3p),
        bss_model_vs_R3=1 - B.brier(yy, pp) / B.brier(yy, rr),
        bss_model_vs_R3plus=1 - B.brier(yy, pp) / B.brier(yy, r3p),
        share_of_gap_explained_by_candidate=(
            (B.brier(yy, rr) - B.brier(yy, r3p)) / max(B.brier(yy, rr) - B.brier(yy, pp), 1e-12))))
DEC = pd.DataFrame(dec_rows).sort_values("share_of_gap_explained_by_candidate", ascending=False)
print(DEC.to_string(index=False, float_format=lambda v: "%.5f" % v))
DEC.to_csv(os.path.join(OUT, "survivor_decomposition.csv"), index=False)
REP["survivor_decomposition"] = DEC.to_dict("records")
print("\n  READ THIS COLUMN: share_of_gap_explained_by_candidate is how much of p_active's Brier")
print("  advantage over R3 is recovered simply by handing R3 the candidate. Near 1.0 means the")
print("  'conditional edge' was the reference's blind spot; near 0 means it was not.")

B.hdr("s05E -- SCHEDULE FAMILY: IS IT THE DEAD FAMILY IN NEW CLOTHES?")
sch = RES[RES["family"] == "F_schedule"]
print(sch[["candidate", "dependent", "t", "n", "p_between", "p_row", "p_familywise"]]
      .to_string(index=False, float_format=lambda v: "%.4f" % v))
print("\n  schedule family: %d cells, max |t| = %.4f, family-wise survivors = %d"
      % (len(sch), sch["t"].abs().max(), int((sch["p_familywise"] < 0.05).sum())))
sd_sp = SPREAD[SPREAD["candidate"].isin(sch["candidate"].unique())]
if len(sd_sp):
    print(sd_sp.groupby("candidate")[["bss_vs_R3"]].agg(["min", "max"]).to_string())
REP["schedule_family"] = dict(cells=len(sch), max_abs_t=float(sch["t"].abs().max()),
                              familywise_survivors=int((sch["p_familywise"] < 0.05).sum()),
                              per_cell=sch.to_dict("records"))

json.dump(REP, open(os.path.join(OUT, "s05_spreads.json"), "w"), indent=2, default=str)
print("\nwrote screen_results_repaired.csv, decile_tables.csv, practical_spread_summary.csv,")
print("      survivor_decomposition.csv, s05_spreads.json")
print("DONE")
