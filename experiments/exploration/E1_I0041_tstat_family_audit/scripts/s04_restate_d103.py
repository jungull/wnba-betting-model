"""E1_I0041 s04 -- RESTATE D103, AND THE STRUCTURAL GATES.

Applies the corrections validated in s03/s03b to the 666 real `t_statistic` cells, using each
screen's own published null draws.  Produces the corrected blind count and STRUCTURAL_GATES.csv.

I do not revise D103.  Corrected figures + evidence only.
"""
import json
import os

import numpy as np
import pandas as pd

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
EXPL = os.path.join(ROOT, "experiments", "exploration")
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D103 = os.path.join(EXPL, "E1_I0026_detection_floor")
P14 = os.path.join(EXPL, "E0_I0014_residual_heterogeneity")
P19 = os.path.join(EXPL, "E0_I0019_availability_forecast")

Z80 = 0.8416212335729143
BEST_LEAD = 0.0023
ALPHA = 0.05
N14 = 13879
_FWT = pd.read_csv(os.path.join(D103, "out", "s04_familywise_thresholds.csv"))
K14, K19 = 348, 318
# read at full stored precision -- a 6-decimal literal leaves a 7.7e-8 relative residual against
# D103's own published floors, which is enough to fail the reconstruction check
TCRIT14 = float(_FWT[(_FWT["arm"] == "N1_within") & (_FWT["K"] == K14)]["q95_maxt"].iloc[0])
TCRIT19 = float(_FWT[(_FWT["arm"] == "N2_entity_swap") & (_FWT["K"] == K19)]["q95_maxt"].iloc[0])
O = {}


def hdr(s):
    print("\n" + "=" * 100 + "\n" + s + "\n" + "=" * 100)


def norm_ppf(p):
    """Acklam inverse normal CDF -- no scipy, accurate to ~1e-9."""
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    pl, pu = 0.02425, 1 - 0.02425
    if p < pl:
        q = np.sqrt(-2 * np.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
               ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    if p > pu:
        q = np.sqrt(-2 * np.log(1 - p))
        return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
                ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    q = p - 0.5
    r = q * q
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / \
           (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)


# ================================================================= A. the BOM'd D103 script ====
hdr("A. PREREG §2 RESIDUAL RISK -- read the one unparsable D103 script literally")
p = os.path.join(D103, "scripts", "s06b_ns.py")
txt = open(p, "r", encoding="utf-8-sig").read()
print("  %s  (%d chars)" % (os.path.relpath(p, ROOT), len(txt)))
print("  " + "\n  ".join(txt.splitlines()))
print("  -> contains a validation of the t-scale conversion: %s"
      % ("YES" if "tscale" in txt or "t_statistic" in txt else "NO"))
O["s06b_ns_validates_tscale"] = bool("tscale" in txt or "t_statistic" in txt)

# ================================================================= B. per-cell corrected floors =
hdr("B. THE 666 CELLS -- published floor, and three corrected floors")

# ---- E0_I0014: recover sd(t) from its own saved |t| draws --------------------------------------
z14 = np.load(os.path.join(P14, "permutation_nulls.npz"))
names = [str(x) for x in z14["names"]]
deps = [str(x) for x in z14["dependents"]]
use_between = z14["use_between"]
s14 = pd.read_csv(os.path.join(P14, "screen_results.csv"))
rec = {}
for j, nm in enumerate(names):
    pref = "bet__" if use_between[j] else "win__"
    for k in deps:
        A = z14[pref + k][:, j].astype(float)
        A = A[np.isfinite(A)]
        rec[(nm, k)] = (float(A.std(ddof=1)), float(A.mean()))
s14["sd_abs"] = [rec[(r.candidate, r.dependent)][0] for r in s14.itertuples()]
s14["mean_abs"] = [rec[(r.candidate, r.dependent)][1] for r in s14.itertuples()]
s14["sd_signed"] = np.sqrt(s14["sd_abs"] ** 2 + s14["mean_abs"] ** 2)
s14["degeneracy_ratio"] = s14["mean_abs"] / s14["sd_abs"]

bar14_own = float(np.quantile(pd.read_csv(
    os.path.join(P14, "maxt_null_draws_whole_screen.csv"))["maxt_correct_level"], 0.95))
bar19_own = float(np.quantile(pd.read_csv(
    os.path.join(P19, "maxt_null_draws.csv"))["maxt_correct_level"], 0.95))
print("  each screen's OWN published family-wise bar (q95 of its max|t| null):")
print("    E0_I0014 (348 cells, 1000 draws) = %.4f" % bar14_own)
print("    E0_I0019 (318 cells, 1000 draws) = %.4f" % bar19_own)

zsid14 = norm_ppf(1 - (1 - (1 - ALPHA) ** (1.0 / K14)) / 2.0)
zsid19 = norm_ppf(1 - (1 - (1 - ALPHA) ** (1.0 / K19)) / 2.0)
print("  Sidak-normal bar for K INDEPENDENT two-sided cells, in sd(t) units:")
print("    K=348 -> %.4f sd     K=318 -> %.4f sd" % (zsid14, zsid19))
print("    (s03b measured the same quantity by simulation: median 3.67-3.79 sd)")

s19 = pd.read_csv(os.path.join(P19, "screen_results_repaired.csv"))
s19["sd_signed"] = s19["nullsd_between"].astype(float)
s19["sd_abs"] = np.nan
s19["degeneracy_ratio"] = (s19["nullmean_between"].abs() / s19["nullsd_between"])

rows = []
for r in s14.itertuples():
    rows.append(dict(screen="E0_I0014_residual_heterogeneity",
                     cell="%s|%s" % (r.candidate, r.dependent), n=N14,
                     sd_used_by_D103=float(r.null_correct_sd), sd_signed=float(r.sd_signed),
                     sd_abs=float(r.sd_abs), t_crit=TCRIT14, K=K14,
                     bar_own=bar14_own, z_sidak=zsid14,
                     degeneracy_ratio=float(r.degeneracy_ratio),
                     folded_sd_defect=True))
for r in s19.itertuples():
    rows.append(dict(screen="E0_I0019_availability_forecast",
                     cell="%s|%s" % (r.candidate, r.dependent), n=int(r.n),
                     sd_used_by_D103=float(r.nullsd_between), sd_signed=float(r.sd_signed),
                     sd_abs=np.nan, t_crit=TCRIT19, K=K19,
                     bar_own=bar19_own, z_sidak=zsid19,
                     degeneracy_ratio=float(r.degeneracy_ratio),
                     folded_sd_defect=False))
C = pd.DataFrame(rows)

C["mde_published"] = ((C["t_crit"] + Z80) * C["sd_used_by_D103"]) ** 2 / C["n"]
C["mde_RA_fold_only"] = ((C["t_crit"] + Z80) * C["sd_signed"]) ** 2 / C["n"]
C["mde_RB_own_bar"] = (C["bar_own"] + Z80 * C["sd_signed"]) ** 2 / C["n"]
C["mde_RC_sidak"] = ((C["z_sidak"] + Z80) * C["sd_signed"]) ** 2 / C["n"]

# ---- reproduce D103's own published mde80_fw exactly, as a check --------------------------------
RP = pd.read_csv(os.path.join(D103, "out", "retrospective_power.csv"))
T = RP[RP["stat_family"] == "t_statistic"][["screen", "cell", "mde80_fw", "null_sd", "n"]]
M = C.merge(T, on=["screen", "cell"], how="inner", suffixes=("", "_d103"))
d = (M["mde_published"] - M["mde80_fw"]).abs()
rel = d / M["mde80_fw"]
print("\n  CHECK -- my reconstruction of D103's own mde80_fw for all %d cells:" % len(M))
print("    max abs diff = %.3e   max relative diff = %.3e" % (d.max(), rel.max()))
assert rel.max() < 1e-9, "cannot reproduce D103's published t_statistic floors"
print("    REPRODUCED to 1e-9 relative -- the corrections below are applied to the real thing.")
O["reconstruction_max_rel_diff"] = float(rel.max())

for col, lab in (("mde_published", "as published"),
                 ("mde_RA_fold_only", "R-A: fold fixed, D103's t_crit kept"),
                 ("mde_RB_own_bar", "R-B: the screen's OWN family-wise bar"),
                 ("mde_RC_sidak", "R-C: Sidak-normal bar for K independent cells")):
    print("\n  %-46s  median floor by screen:" % lab)
    for scr, g in C.groupby("screen"):
        print("     %-34s %.6g   blind(>%g): %d / %d"
              % (scr.split("_")[0] + "_" + scr.split("_")[1], g[col].median(), BEST_LEAD,
                 int((g[col] > BEST_LEAD).sum()), len(g)))

C.to_csv(os.path.join(HERE, "TSTAT_CELL_FLOORS.csv"), index=False)

# ================================================================= C. degenerate nulls (C4) =====
hdr("C. C4 -- DEGENERATE NULLS (the shuffle barely moves the statistic)")
print("  reference: for ANY symmetric null, mean(|t|)/sd(|t|) ~ 1.32 (exactly 1.3236 if normal).")
print("  E0_I0019's own criterion for a degenerate null is |mean|/sd > 5 (s05:56-58).")
for scr, g in C.groupby("screen"):
    r = g["degeneracy_ratio"].replace([np.inf, -np.inf], np.nan).dropna()
    print("\n  %s  (n=%d)" % (scr, len(r)))
    print("    ratio: min=%.3f p50=%.3f p90=%.3f p99=%.3f max=%.3g"
          % (r.min(), r.median(), r.quantile(.9), r.quantile(.99), r.max()))
    for thr in (3, 5, 10):
        print("    cells with ratio > %-3d : %d (%.1f%%)"
              % (thr, int((r > thr).sum()), 100 * (r > thr).mean()))
deg = C[C["degeneracy_ratio"] > 5]
print("\n  DEGENERATE cells and what D103 recorded for them:")
print("    total degenerate: %d of 666" % len(deg))
print("    of these, D103's published floor put them BELOW the 0.0023 lead (i.e. counted as")
print("    ADEQUATELY POWERED): %d" % int((deg["mde_published"] <= BEST_LEAD).sum()))
print("    their published floors: median=%.3g  min=%.3g" %
      (deg["mde_published"].median(), deg["mde_published"].min()))
O["degenerate"] = dict(n=int(len(deg)),
                       counted_powered=int((deg["mde_published"] <= BEST_LEAD).sum()),
                       median_published_floor=float(deg["mde_published"].median()))

# ================================================================= D. restated blind counts =====
hdr("D. THE RESTATED D103 BLIND COUNT")
cells = pd.read_csv(os.path.join(HERE, "_d103_cells.csv"))
base_blind = int(cells["blind"].sum())
base_n = len(cells)
print("  as published: %d / %d = %.16f" % (base_blind, base_n, base_blind / base_n))

key = C.set_index(["screen", "cell"])
res = {}
for col, lab in (("mde_published", "published (control -- must reproduce 760)"),
                 ("mde_RA_fold_only", "R-A  fold fixed only"),
                 ("mde_RB_own_bar", "R-B  screen's own family-wise bar"),
                 ("mde_RC_sidak", "R-C  Sidak-normal bar")):
    cc = cells.copy()
    m = cc.merge(C[["screen", "cell", col]], on=["screen", "cell"], how="left")
    newblind = np.where(m[col].notna(), m[col] > BEST_LEAD, m["blind"])
    nb = int(newblind.sum())
    res[col] = dict(label=lab, blind=nb, share=nb / base_n, delta=nb - base_blind)
    print("  %-44s %4d / %d = %.4f   (%+d cells, %+.2f pp)"
          % (lab, nb, base_n, nb / base_n, nb - base_blind,
             100 * (nb / base_n - base_blind / base_n)))
assert res["mde_published"]["blind"] == 760, "control did not reproduce 760"
O["restatement"] = res

# ================================================================= E. structural gates ==========
hdr("E. THE TWO STRUCTURAL GATES FROM E1_I0037, ACROSS THE 666 CELLS")
# block counts, from each screen's own run log / grouping table
sch14 = dict(zip(s14["candidate"], s14["perm_scheme"]))
blk14 = {"PLAYER": 475, "TEAM": 36}
s14["n_blocks"] = [blk14[sch14[c]] if use_between[names.index(c)] else blk14[sch14[c]]
                   for c in s14["candidate"]]
lv = pd.read_csv(os.path.join(P19, "grouping_levels.csv"))
blk19 = {"player_between": 489, "teamgame_between": 1486, "teamseason_between": 36}
sp19 = dict(zip(lv["candidate"], lv["scheme_primary"]))
s19["n_blocks"] = [blk19[sp19[c]] for c in s19["candidate"]]

G = pd.concat([
    pd.DataFrame(dict(screen="E0_I0014_residual_heterogeneity",
                      cell=s14["candidate"] + "|" + s14["dependent"],
                      null_type="permutation_of_carrier", n_blocks=s14["n_blocks"],
                      t_crit=TCRIT14)),
    pd.DataFrame(dict(screen="E0_I0019_availability_forecast",
                      cell=s19["candidate"] + "|" + s19["dependent"],
                      null_type="permutation_of_carrier", n_blocks=s19["n_blocks"],
                      t_crit=TCRIT19))], ignore_index=True)
G["below_six_blocks"] = G["n_blocks"] < 6
G["t_crit_ge_sqrt_nb"] = G["t_crit"] >= np.sqrt(G["n_blocks"])
G["gate_a_applicable"] = False        # p_min = 2^(1-nb) is a SIGN-FLIP identity
G["gate_b_applicable"] = False        # requires a null whose sd carries the effect
G["gate_a_reason"] = ("sign-flip identity p_min=2^(1-nb) does not hold for a permutation null; "
                      "here p_min = 1/(R+1) = 1/1001")
G["gate_b_reason"] = ("requires sd(null) to grow with the planted effect; s03 S5 measured "
                      "sd(delta=0.3)/sd(0) = 1.0001 (p10 0.9987, p90 1.0030) -- flat")
G.to_csv(os.path.join(HERE, "STRUCTURAL_GATES.csv"), index=False)

print("  block counts in the family: %s" % G["n_blocks"].value_counts().to_dict())
print("  GATE A -- fewer than six blocks       : %d of %d cells"
      % (int(G["below_six_blocks"].sum()), len(G)))
print("  GATE B -- t_crit >= sqrt(n_blocks)    : %d of %d cells"
      % (int(G["t_crit_ge_sqrt_nb"].sum()), len(G)))
print("    of which, by screen: %s"
      % G[G["t_crit_ge_sqrt_nb"]].groupby("screen").size().to_dict())
print("\n  APPLICABILITY (decided by measurement, not assertion):")
print("    Gate A: NOT applicable -- %s" % G["gate_a_reason"].iloc[0])
print("    Gate B: NOT applicable -- %s" % G["gate_b_reason"].iloc[0])
print("\n  The applicable analogue for this family is C4 (degenerate permutation nulls):")
print("    %d of 666 cells, %d of them recorded by D103 as adequately powered."
      % (len(deg), int((deg["mde_published"] <= BEST_LEAD).sum())))
O["gates"] = dict(below_six=int(G["below_six_blocks"].sum()),
                  tcrit_ge_sqrt_nb=int(G["t_crit_ge_sqrt_nb"].sum()),
                  tcrit_ge_sqrt_nb_by_screen={k: int(v) for k, v in
                                              G[G["t_crit_ge_sqrt_nb"]].groupby("screen")
                                              .size().items()},
                  gate_a_applicable=False, gate_b_applicable=False,
                  block_counts={int(k): int(v) for k, v in
                                G["n_blocks"].value_counts().items()})

json.dump(O, open(os.path.join(HERE, "_s04.json"), "w"), indent=2, default=str)
print("\nwrote TSTAT_CELL_FLOORS.csv, STRUCTURAL_GATES.csv, _s04.json")
