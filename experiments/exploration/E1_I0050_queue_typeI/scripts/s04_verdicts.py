"""S04 -- apply the validity rule, and recompute the corrected p and family-wise status
from E1_I0044's SAVED SIGNED DRAWS rather than from its CSV.

D101 for every number:
  response  : the cell's own dependent (one of 6), never mixed
  row set   : the arm's own rows (A4 = 3,549 decision-stratum rows 2023-24; A1 = 13,879)
  base      : season fixed effects on the arm's own seasons
  SST basis : season-demeaned response on the arm's own rows
  weighting : unweighted
  statistic : signed one-column classical t; ALL floors are one-column floors
  family    : 348 cells (58 candidates x 6 dependents), one shared gather index per draw
Nothing is compared across arms.
"""
import json, math, os, sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *          # noqa

TOL = 0.075          # PREREG section 4
Z80 = 0.8416212335729143
D103_FAMILY_BAR = 0.0023
D103_SINGLE_CELL_FLOOR = 0.00102

s00 = json.load(open(os.path.join(HERE, "scripts", "_s00.json")))
CELLS = s00["cells54"]
PUB1000 = set(s00["published_pfw_exactly_one"])
SR = pd.read_csv(os.path.join(S14, "screen_results.csv"))
SR["cell"] = SR["candidate"] + "|" + SR["dependent"]
S = SR.set_index("cell")


def cp(k, nrep):
    def binc(a, bb, x):
        if x <= 0: return 0.0
        if x >= 1: return 1.0
        if x > (a + 1.0) / (a + bb + 2.0):
            return 1.0 - binc(bb, a, 1.0 - x)
        lb = math.lgamma(a) + math.lgamma(bb) - math.lgamma(a + bb)
        front = math.exp(math.log(x) * a + math.log(1 - x) * bb - lb) / a
        fv, c, d = 1.0, 1.0, 0.0
        for i in range(300):
            mm = i // 2
            if i == 0: num = 1.0
            elif i % 2 == 0: num = (mm * (bb - mm) * x) / ((a + 2 * mm - 1) * (a + 2 * mm))
            else: num = -((a + mm) * (a + bb + mm) * x) / ((a + 2 * mm) * (a + 2 * mm + 1))
            d = 1 + num * d
            d = 1e-30 if abs(d) < 1e-30 else d
            d = 1 / d
            c = 1 + num / c
            c = 1e-30 if abs(c) < 1e-30 else c
            fv *= c * d
            if abs(1 - c * d) < 1e-12: break
        return front * (fv - 1)
    def solve(t, a, bb):
        lo, hi = 0.0, 1.0
        for _ in range(200):
            mid = .5 * (lo + hi)
            if binc(a, bb, mid) < t: lo = mid
            else: hi = mid
        return .5 * (lo + hi)
    return (0.0 if k == 0 else solve(0.025, k, nrep - k + 1),
            1.0 if k == nrep else solve(0.975, k + 1, nrep - k))


# ------------------------------------------------------------------ TYPE-I PER CELL
ti = []
for arm in ("A4_CLEAN_DEC", "A1_FULL"):
    p = os.path.join(HERE, "_TYPEI_RAW_%s.csv" % arm)
    if not os.path.exists(p):
        print("MISSING %s -- arm reported UNVERIFIABLE" % p); continue
    T = pd.read_csv(p)
    T["not_estimable"] = T.get("not_estimable", "").fillna("")
    for cell, g in T.groupby("cell"):
        g = g.set_index("generator")
        rec = dict(arm=arm, cell=cell, candidate=cell.split("|")[0],
                   dependent=cell.split("|")[1],
                   n=int(g["n"].iloc[0]), n_blocks=int(g["n_blocks"].iloc[0]),
                   n_synthetic_datasets_per_generator=int(g["B_reps"].iloc[0]),
                   n_null_draws_per_replicate=int(g["R_null"].iloc[0]),
                   permuted_carrier_pool=int(g["pool"].iloc[0]),
                   level_matched_scheme=g["level_matched_scheme"].iloc[0])
        if g["not_estimable"].iloc[0] != "":
            rec.update(not_estimable=g["not_estimable"].iloc[0],
                       null_validity="UNVERIFIABLE_IN_STRATUM_NO_STATISTIC")
            ti.append(rec); continue
        rec["not_estimable"] = ""
        for gen in ("EXCH", "CIRCSHIFT", "BLOCKBOOT"):
            for sch in ("COMPOSED2", "LEVEL_MATCHED", "ROW_NAIVE"):
                v = float(g.loc[gen, "typeI_" + sch])
                rec["typeI_%s_%s" % (sch, gen)] = v
                if sch == "COMPOSED2":
                    lo, hi = cp(int(round(v * rec["n_synthetic_datasets_per_generator"])),
                                rec["n_synthetic_datasets_per_generator"])
                    rec["cp95_lo_COMPOSED2_%s" % gen] = lo
                    rec["cp95_hi_COMPOSED2_%s" % gen] = hi
        e, cS, bb = (rec["typeI_COMPOSED2_EXCH"], rec["typeI_COMPOSED2_CIRCSHIFT"],
                     rec["typeI_COMPOSED2_BLOCKBOOT"])
        worst_h0 = max(e, cS)
        rec["typeI_COMPOSED2_worst_H0_generator"] = worst_h0
        if worst_h0 > TOL:
            rec["null_validity"] = "INVALID_ANTICONSERVATIVE"
        elif worst_h0 <= 0.025:
            rec["null_validity"] = "ACCEPTABLE_CONSERVATIVE"
        else:
            rec["null_validity"] = "ACCEPTABLE"
        rec["confounded_with_block_position"] = bool(bb > TOL and worst_h0 <= TOL)
        rec["level_matched_null_validity"] = (
            "INVALID_ANTICONSERVATIVE"
            if max(rec["typeI_LEVEL_MATCHED_EXCH"], rec["typeI_LEVEL_MATCHED_CIRCSHIFT"]) > TOL
            else "ACCEPTABLE")
        rec["row_naive_null_validity"] = (
            "INVALID_ANTICONSERVATIVE"
            if max(rec["typeI_ROW_NAIVE_EXCH"], rec["typeI_ROW_NAIVE_CIRCSHIFT"]) > TOL
            else "ACCEPTABLE")
        ti.append(rec)
TI = pd.DataFrame(ti)
TI["nominal_level"] = 0.05
TI["acceptance_tolerance"] = TOL
TI.to_csv(os.path.join(HERE, "TYPEI_PER_CELL.csv"), index=False)
print("wrote TYPEI_PER_CELL.csv", TI.shape)

for arm in sorted(TI["arm"].unique()):
    a = TI[TI["arm"] == arm]
    print("\n=== %s : null validity over the 54 ===" % arm)
    print(a["null_validity"].value_counts().to_string())
    est = a[a["not_estimable"] == ""]
    if len(est):
        print("   COMPOSED2 worst-H0 Type-I: median %.4f  max %.4f   (nominal 0.05, tol %.3f)"
              % (est["typeI_COMPOSED2_worst_H0_generator"].median(),
                 est["typeI_COMPOSED2_worst_H0_generator"].max(), TOL))
        print("   confounded with block position (BLOCKBOOT > tol, H0 gens fine): %d of %d"
              % (int(est["confounded_with_block_position"].sum()), len(est)))
        print("   E0_I0014's OWN level-matched null invalid on: %d of %d"
              % (int((est["level_matched_null_validity"] != "ACCEPTABLE").sum()), len(est)))
        print("   row-naive null invalid on: %d of %d"
              % (int((est["row_naive_null_validity"] != "ACCEPTABLE").sum()), len(est)))

# --------------------------------------------- recompute p from E1_I0044's SAVED DRAWS
print("\n=== recomputing composed-2 p and family-wise p from the saved signed draws ===")
ver = []
for arm in ("A4_CLEAN_DEC", "A1_FULL"):
    z2 = np.load(os.path.join(S44, "nulls", "composed2_null_%s.npz" % arm), allow_pickle=True)
    nm = [str(x) for x in z2["names"]]
    dps = [str(x) for x in z2["dependents"]]
    R = int(z2["R"][0]); N = int(z2["n"][0])
    maxt = z2["maxt_familywise"]
    bar95 = float(np.percentile(maxt, 95))
    # rebuild the bar from the raw draws as a check on the stored one
    allt = np.concatenate([np.abs(z2["t_signed__" + k]) for k in dps], axis=1)
    bar95_rebuilt = float(np.percentile(np.nanmax(allt, axis=1), 95))
    # a bar over ONLY the cells whose composed-2 null this screen validated
    okcells = set(TI.loc[(TI["arm"] == arm) &
                         (TI["null_validity"].astype(str).str.startswith("ACCEPTABLE")),
                         "cell"])
    colmask = np.array([("%s|%s" % (nm[j], k)) in okcells
                        for k in dps for j in range(len(nm))])
    bar95_validated = (float(np.percentile(np.nanmax(allt[:, colmask], axis=1), 95))
                       if colmask.sum() else np.nan)
    print("  %s  R=%d n=%d  bar95 stored %.4f  rebuilt %.4f  (validated-cells-only bar %.4f, k=%d)"
          % (arm, R, N, bar95, bar95_rebuilt, bar95_validated, int(colmask.sum())))
    RM2 = pd.read_csv(os.path.join(S44, "_REMEASURE2_ALL_ARMS.csv"))
    RM2 = RM2[RM2["arm"] == arm].set_index("cell")
    for cell in CELLS:
        cand, dep = cell.split("|")
        j = nm.index(cand)
        dv = z2["t_signed__" + dep][:, j]
        obs = float(z2["observed_t__" + dep][j])
        dr2 = float(z2["observed_dr2__" + dep][j])
        fin = np.isfinite(dv)
        rec = dict(arm=arm, cell=cell, candidate=cand, dependent=dep, n=N,
                   n_blocks=int(RM2.loc[cell, "n_blocks"]), R_draws=R,
                   observed_signed_t=obs, observed_dr2=dr2,
                   null_mean_signed_t=float(dv[fin].mean()),
                   null_sd_signed_t=float(dv[fin].std(ddof=1)))
        if not np.isfinite(obs):
            rec.update(p_percell_plus1=np.nan, p_familywise_plus1=np.nan,
                       not_estimable="OBSERVED_T_NOT_FINITE")
            ver.append(rec); continue
        a = np.abs(dv[fin])
        # (k+1)/(R+1): E1_I0044 used k/R, which can return an impossible p of exactly 0
        rec["p_percell_E1_I0044_convention"] = float((a >= abs(obs)).mean())
        rec["p_percell_plus1"] = float((np.sum(a >= abs(obs)) + 1) / (len(a) + 1))
        rec["p_familywise_E1_I0044_convention"] = float((maxt >= abs(obs)).mean())
        rec["p_familywise_plus1"] = float((np.sum(maxt >= abs(obs)) + 1) / (len(maxt) + 1))
        rec["bar_familywise_q95"] = bar95
        rec["bar_familywise_q95_validated_cells_only"] = bar95_validated
        rec["p_familywise_validated_family_plus1"] = float(
            (np.sum(np.nanmax(allt[:, colmask], axis=1) >= abs(obs)) + 1) / (R + 1)
            if colmask.sum() else np.nan)
        bar_pc = float(np.percentile(a, 97.5))
        sd = rec["null_sd_signed_t"]
        rec["bar_percell_abs_t"] = bar_pc
        rec["mde80_percell_ANALYTIC"] = (bar_pc + Z80 * sd) ** 2 / N
        rec["mde80_familywise_ANALYTIC"] = (bar95 + Z80 * sd) ** 2 / N
        rec["floor_basis"] = "ANALYTIC"
        rec["not_estimable"] = ""
        ver.append(rec)
V = pd.DataFrame(ver)

# cross-check against E1_I0044's own CSV (an anchor on my own re-derivation)
chk = pd.read_csv(os.path.join(S44, "_REMEASURE2_ALL_ARMS.csv"))
mg = V.merge(chk[["arm", "cell", "p_two_sided", "observed_dr2", "observed_t"]],
             on=["arm", "cell"], suffixes=("", "_pub"))
d1 = (mg["p_percell_E1_I0044_convention"] - mg["p_two_sided"]).abs().max()
d2 = (mg["observed_dr2"] - mg["observed_dr2_pub"]).abs().max()
d3 = (mg["observed_signed_t"] - mg["observed_t"]).abs().max()
print("  ANCHOR (my re-derivation vs E1_I0044's CSV): max |dp| %.3e  |ddR2| %.3e  |dt| %.3e"
      % (d1, d2, d3))
assert d1 < 1e-12 and d2 < 1e-12 and d3 < 1e-12, "re-derivation does not match the published CSV"

# ------------------------------------------------------------------- CORRECTED VERDICTS
J = V.merge(TI[["arm", "cell", "null_validity", "confounded_with_block_position",
                "typeI_COMPOSED2_EXCH", "typeI_COMPOSED2_CIRCSHIFT",
                "typeI_COMPOSED2_BLOCKBOOT", "typeI_COMPOSED2_worst_H0_generator",
                "cp95_hi_COMPOSED2_EXCH", "cp95_hi_COMPOSED2_CIRCSHIFT",
                "n_synthetic_datasets_per_generator"]],
            on=["arm", "cell"], how="left")
J["published_p_correct_level"] = [S.loc[c, "p_correct_level"] for c in J["cell"]]
J["published_p_familywise_whole_screen"] = [S.loc[c, "p_familywise_whole_screen"] for c in J["cell"]]
J["published_pfw_is_exactly_1.000"] = J["cell"].isin(PUB1000)


def verdict(r):
    if str(r["null_validity"]).startswith("UNVERIFIABLE"):
        return "UNVERIFIABLE_NO_STATISTIC_IN_STRATUM"
    if r["null_validity"] == "INVALID_ANTICONSERVATIVE":
        return "UNVERIFIABLE_NULL_FAILS_TYPE_I"
    if not np.isfinite(r["p_familywise_plus1"]):
        return "UNVERIFIABLE_NO_FINITE_STATISTIC"
    if r["p_familywise_plus1"] < 0.05:
        return ("FAMILYWISE_SIGNIFICANT_BUT_CONFOUNDED_WITH_BLOCK_POSITION"
                if r["confounded_with_block_position"] else "FAMILYWISE_SIGNIFICANT")
    if r["p_percell_plus1"] < 0.05:
        return ("PERCELL_SIGNIFICANT_ONLY_CONFOUNDED"
                if r["confounded_with_block_position"] else "PERCELL_SIGNIFICANT_ONLY")
    return "NOT_SIGNIFICANT"


J["corrected_verdict"] = J.apply(verdict, axis=1)
J["clears_D103_single_cell_floor_0.00102"] = J["observed_dr2"] >= D103_SINGLE_CELL_FLOOR
J["dr2_exceeds_D103_bar_0.0023_NOTE_DIFFERENT_RESPONSE"] = J["observed_dr2"] >= D103_FAMILY_BAR
J["D101_note"] = ("dR2 here is on |residual| or squared-residual of a forecast, on this arm's "
                  "own rows/base/SST; D103's 0.0023 bar is a dR2 on D089 walk-forward POINTS. "
                  "The two are NOT the same denominator and the comparison is descriptive only.")
J.to_csv(os.path.join(HERE, "CORRECTED_VERDICTS.csv"), index=False)
print("\nwrote CORRECTED_VERDICTS.csv", J.shape)

for arm in ("A4_CLEAN_DEC", "A1_FULL"):
    a = J[J["arm"] == arm]
    if not len(a): continue
    print("\n=== %s -- corrected verdicts over the 54 ===" % arm)
    print(a["corrected_verdict"].value_counts().to_string())
    fw = a[a["corrected_verdict"].str.startswith("FAMILYWISE_SIGNIFICANT")]
    print("   family-wise significant with an acceptable null: %d" % len(fw))
    if len(fw):
        print(fw.sort_values("observed_dr2", ascending=False)[
            ["cell", "n", "n_blocks", "observed_dr2", "p_percell_plus1",
             "p_familywise_plus1", "typeI_COMPOSED2_worst_H0_generator",
             "confounded_with_block_position",
             "clears_D103_single_cell_floor_0.00102"]].to_string(index=False))

# ------------------------------------------------------------------------ PREREG P2
print("\n=== PREREG P2 : the 49 cells whose published p_familywise is exactly 1.000 ===")
for arm in ("A1_FULL", "A4_CLEAN_DEC"):
    a = J[(J["arm"] == arm) & (J["published_pfw_is_exactly_1.000"])]
    if not len(a): continue
    ok = a[a["null_validity"].astype(str).str.startswith("ACCEPTABLE")]
    print("   %s : of %d, %d have an acceptable null; %d of those reach family-wise p<0.05"
          % (arm, len(a), len(ok), int((ok["p_familywise_plus1"] < 0.05).sum())))
print("DONE s04")
