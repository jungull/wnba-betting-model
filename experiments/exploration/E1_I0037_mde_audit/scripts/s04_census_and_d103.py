"""E1_I0037 s04 -- MDE_CENSUS.csv and D103_EXPOSURE.

The census is built by WALKING the FINDINGS.json trees and classifying each quoted figure by the
RATIO IT BEARS TO ITS OWN null_sd -- an arithmetic fingerprint, not a key name.  Three analytic
fingerprints exist in this programme:

    2.800000  = 1.9600 + 0.8400   (E1_I0033, E1_I0034)
    2.801585  = 1.959964 + 0.841621 (E1_I0035)
    2.486622  = 1.645 + 0.841621  (E1_I0026 stat_family='paired', per-cell)

A figure that is NOT a constant multiple of any null_sd in its own record is an injection or
closed-form crossing and is classified as such.
"""
from __future__ import annotations
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
EXPL = os.path.join(ROOT, "experiments", "exploration")
HERE = os.path.join(EXPL, "E1_I0037_mde_audit")
D103 = os.path.join(EXPL, "E1_I0026_detection_floor")
LEDGER = os.path.join(ROOT, "experiments", "player_program", "orchestration",
                      "DECISION_LEDGER.jsonl")
sys.dont_write_bytecode = True
pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 60)
Z80 = 0.8416212335729143
F = {}

FINGERPRINTS = {2.800000: "ANALYTIC_2.800xSD", 2.801585: "ANALYTIC_2.8016xSD",
                2.486622: "ANALYTIC_(1.645+z80)xSD"}


def hdr(s):
    print("\n" + "=" * 98)
    print(s)
    print("=" * 98)


def walk(o, pre=""):
    if isinstance(o, dict):
        for k, v in o.items():
            for r in walk(v, pre + "." + str(k)):
                yield r
    elif isinstance(o, list):
        for i, v in enumerate(o):
            for r in walk(v, pre + "[%d]" % i):
                yield r
    else:
        yield pre, o


POWERISH = ("mde", "floor", "detect", "resolution", "power", "null_sd", "nullsd", "sensitiv")


def is_powerish(keypath):
    leaf = keypath.split(".")[-1].split("[")[0].lower()
    return any(t in leaf for t in POWERISH)


# =============================================================================== A. CENSUS =====
hdr("A. CENSUS -- every quoted power figure, classified by arithmetic fingerprint")
rows = []
findings = []
for dp, dn, fn in os.walk(EXPL):
    dn[:] = [d for d in dn if d != "__pycache__"]
    for f in fn:
        if f == "FINDINGS.json":
            findings.append(os.path.join(dp, f))
print("  FINDINGS.json files found: %d" % len(findings))

for path in sorted(findings):
    screen = os.path.relpath(path, EXPL).split(os.sep)[0]
    if screen == "E1_I0037_mde_audit":
        continue
    try:
        J = json.load(open(path, encoding="utf-8"))
    except Exception as exc:                                    # noqa: BLE001
        rows.append(dict(source=path, key="<UNPARSEABLE>", value=np.nan, screen=screen,
                         classification="UNRESOLVED", evidence=repr(exc)[:120]))
        continue
    leaves = list(walk(J))
    # index every null_sd-like leaf by its PARENT record so ratios can be formed within-record
    sds = {}
    for kp, v in leaves:
        leaf = kp.split(".")[-1].split("[")[0].lower()
        if isinstance(v, (int, float)) and not isinstance(v, bool) and "null_sd" in leaf.replace(
                "nullsd", "null_sd"):
            parent = kp.rsplit(".", 1)[0]
            sds.setdefault(parent, []).append(float(v))
    for kp, v in leaves:
        if not is_powerish(kp):
            continue
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            continue
        leaf = kp.split(".")[-1].split("[")[0].lower()
        if "null_sd" in leaf.replace("nullsd", "null_sd"):
            continue
        parent = kp.rsplit(".", 1)[0]
        cls, ev = "INJECTION_OR_OTHER", ""
        cand = sds.get(parent, [])
        for sd in cand:
            if sd and np.isfinite(sd) and sd != 0:
                r = float(v) / sd
                for fp, lab in FINGERPRINTS.items():
                    if abs(r - fp) < 5e-4:
                        cls, ev = lab, "value/null_sd = %.6f in the same record" % r
                        break
            if cls != "INJECTION_OR_OTHER":
                break
        if cls == "INJECTION_OR_OTHER" and cand:
            ev = "value/null_sd = %s (no constant fingerprint)" % (
                ", ".join("%.3f" % (float(v) / s) for s in cand[:3] if s))
        rows.append(dict(source=path, key=kp, value=float(v), screen=screen,
                         classification=cls, evidence=ev))

C = pd.DataFrame(rows)
# ---- add the D103 retrospective cells, which are the bulk of the programme's quoted floors ----
R = pd.read_csv(os.path.join(D103, "out", "retrospective_power.csv"))
fam_cls = {"increment": "ANALYTIC_CLOSED_FORM_on_PERMUTATION_null",
           "t_statistic": "ANALYTIC_CLOSED_FORM_on_PERMUTATION_null_UNVALIDATED",
           "paired": "ANALYTIC_(1.645+z80)xSD_on_EFFECT_CARRYING_SIGNFLIP"}
for r in R.itertuples():
    rows.append(dict(source=os.path.join(D103, "out", "retrospective_power.csv"),
                     key="row:%s|%s|%s" % (r.screen, r.cell, r.null_arm),
                     value=float(r.mde80_fw), screen=r.screen,
                     classification=fam_cls[r.stat_family],
                     evidence="stat_family=%s n=%s n_clusters=%s" % (r.stat_family, r.n,
                                                                     r.n_clusters)))
C = pd.DataFrame(rows)
C["effect_carrying_null"] = C["classification"].isin(
    ["ANALYTIC_2.800xSD", "ANALYTIC_2.8016xSD", "ANALYTIC_(1.645+z80)xSD",
     "ANALYTIC_(1.645+z80)xSD_on_EFFECT_CARRYING_SIGNFLIP"])
C.to_csv(os.path.join(HERE, "MDE_CENSUS.csv"), index=False)
print("  census rows: %d" % len(C))
print()
print(C.groupby("classification").agg(figures=("value", "size"),
                                      screens=("screen", "nunique")).to_string())
print()
print("  by screen (analytic-on-effect-carrying-null only):")
print(C[C.effect_carrying_null].groupby(["screen", "classification"])
      .size().rename("figures").to_string())
F["census_counts"] = C.groupby("classification").size().to_dict()
F["census_effect_carrying"] = int(C.effect_carrying_null.sum())
F["census_total"] = int(len(C))

# =========================================================================== B. D103 EXPOSURE ==
hdr("B. D103 EXPOSURE -- how much does the 56.3% move?")
z80 = Z80


def law_ratio(nb, t_crit):
    """true_MDE / ((t_crit + z80) * sd_correct), from the effect-carrying critical value.

    Reject when |mean(d)| >= t_crit * sd(e), sd(e)^2 = e^2/nb + SE^2.  80% power needs
    e - z80*SE >= t_crit*sqrt(e^2/nb + SE^2).  Solve in u = e/SE."""
    a = 1.0 - t_crit * t_crit / nb
    c = z80 * z80 - t_crit * t_crit
    if a <= 0:
        return float("inf")
    disc = 4 * z80 * z80 - 4 * a * c
    if disc < 0:
        return float("inf")
    u = (2 * z80 + np.sqrt(disc)) / (2 * a)
    return u / (t_crit + z80)


worst = (R.groupby(["screen", "decision", "family_size_K", "cell"])
         .agg(mde80_fw=("mde80_fw", "max"), stat_family=("stat_family", "first"),
              n=("n", "max"), n_clusters=("n_clusters", "max"),
              t_crit=("mde80_fw", "size"), reported_p_fw=("reported_p_fw", "min"))
         .reset_index())
BEST = 0.0023
worst["blind_published"] = worst["mde80_fw"] > BEST
print("  published: %d cells, %d blind (%.4f)"
      % (len(worst), worst.blind_published.sum(), worst.blind_published.mean()))

pf = worst[worst.stat_family == "paired"]
print("\n  the EFFECT-CARRYING family (E1_I0023, stat_family='paired'):")
print("     unique cells                 : %d of %d  (%.2f%%)"
      % (len(pf), len(worst), 100 * len(pf) / len(worst)))
print("     currently counted blind      : %d" % int(pf.blind_published.sum()))
print("     cluster counts (n_clusters)  : min=%s med=%s max=%s"
      % (pf.n_clusters.min(), pf.n_clusters.median(), pf.n_clusters.max()))

# the family-wise t_crit E1_I0023's cells were given
FWT = 6.0        # fw q95 max-t at K=120 is ~6.5-7.0 per E1_I0026 NOTES; use the published grid
tc_row = pd.read_csv(os.path.join(D103, "out", "s04_familywise_thresholds.csv"))
tc = tc_row[(tc_row.arm == "N2_entity_swap") & (tc_row.K == 132)]["q95_maxt"]
FWT = float(tc.iloc[0]) if len(tc) else FWT
print("     family-wise t_crit used      : %.3f (N2_entity_swap, K=132 grid point)" % FWT)

# two corrections, applied separately (the coordinator asked for H_A and H_B kept apart)
print("\n  CORRECTION H_A (remove the effect contamination from null_sd).")
print("     Direction: contamination INFLATES the quoted floor, so removing it makes floors")
print("     SMALLER and cells LESS blind.  Magnitude on the two real cells I measured:")
print("        E1_I0035 team Xb   contamination 2.435  -> floor falls 4.595 -> 1.887")
print("        E1_I0035 player Xa contamination 1.003  -> floor essentially unchanged")
print("     E1_I0023's cells are not in my scope to recompute (I do not hold its loss vectors),")
print("     so H_A's correction factor for D103 is bounded, not point-estimated:")
print("        contamination in [1.00, 2.44] -> paired floors currently OVERSTATED by up to 2.4x")

print("\n  CORRECTION H_B (block-count miscalibration of the rule).")
rowsx = []
for r in pf.itertuples():
    nb = r.n_clusters if np.isfinite(r.n_clusters) and r.n_clusters > 0 else np.nan
    lr = law_ratio(nb, FWT) if np.isfinite(nb) else np.nan
    rowsx.append(dict(cell=r.cell, n=r.n, n_clusters=nb, mde80_published=r.mde80_fw,
                      H_B_factor=lr, mde80_H_B_corrected=r.mde80_fw * lr,
                      blind_published=r.blind_published,
                      blind_after_H_B=(r.mde80_fw * lr) > BEST if np.isfinite(lr) else True))
PX = pd.DataFrame(rowsx)
PX.to_csv(os.path.join(HERE, "d103_paired_family_correction.csv"), index=False)
print("     H_B factor over the 30 paired cells: min=%.3f med=%.3f max=%.3f  (n_clusters "
      "min=%.0f med=%.0f)"
      % (PX.H_B_factor.min(), PX.H_B_factor.median(), PX.H_B_factor.max(),
         PX.n_clusters.min(), PX.n_clusters.median()))
print("     blind BEFORE H_B: %d of %d      blind AFTER H_B: %d of %d"
      % (PX.blind_published.sum(), len(PX), PX.blind_after_H_B.sum(), len(PX)))

new_blind = int(worst.blind_published.sum()
                - PX.blind_published.sum() + PX.blind_after_H_B.sum())
print("\n  WHOLE-AUDIT EFFECT OF H_B ALONE:")
print("     published : %d of %d blind = %.4f (56.3%%)"
      % (worst.blind_published.sum(), len(worst), worst.blind_published.mean()))
print("     H_B-corr  : %d of %d blind = %.4f"
      % (new_blind, len(worst), new_blind / len(worst)))
print("     movement  : %+d cells, %+.2f percentage points"
      % (new_blind - worst.blind_published.sum(),
         100 * (new_blind / len(worst) - worst.blind_published.mean())))
F["d103"] = dict(cells=int(len(worst)), blind_published=int(worst.blind_published.sum()),
                 share_published=float(worst.blind_published.mean()),
                 paired_cells=int(len(PX)),
                 paired_blind_published=int(PX.blind_published.sum()),
                 paired_blind_after_H_B=int(PX.blind_after_H_B.sum()),
                 blind_after_H_B=int(new_blind),
                 share_after_H_B=float(new_blind / len(worst)),
                 H_B_factor_median=float(PX.H_B_factor.median()),
                 fw_t_crit=FWT)

hdr("C. THE UNQUANTIFIED EXPOSURE -- what I could NOT bound")
print("  1. stat_family='t_statistic' -- %d of 1349 cells (%.1f%%), E0_I0014 and E0_I0019."
      % (int((worst.stat_family == 't_statistic').sum()),
         100 * (worst.stat_family == 't_statistic').mean()))
print("     Its formula MDE80 = ((t_crit + z80) * sd_t)^2 / n was NEVER validated against the")
print("     simulated power surface -- s06's validate() reads s04_mde_table.csv, which contains")
print("     only 'increment' cells.  These 666 cells carry 518 of the 760 blind verdicts, i.e.")
print("     %.1f%% of the entire blind count rests on an unvalidated conversion."
      % (100 * 518 / 760))
print("     THIS IS A LARGER EXPOSURE THAN THE ONE I WAS SENT TO AUDIT, and I have not")
print("     quantified it.  It is a different defect (a scale conversion, not an effect-carrying")
print("     null) and needs its own screen.")
print()
print("  2. E1_I0033's 30+ quoted floors are all 2.800 x null_sd on a paired block sign-flip at")
print("     team-season with 36 blocks.  At nb=36 the H_B factor is %.3f -- small.  But two of"
      % law_ratio(36, 1.959964))
print("     its cells (P02 'significant AND underpowered', s10 'floor 0.00584') have near-zero")
print("     observed effects, so H_A does not rescue them and H_B raises their floors ~9%%.")
print("     Direction: those two verdicts get MORE underpowered, not less.")

open(os.path.join(HERE, "_s04.json"), "w", encoding="utf-8").write(
    json.dumps(F, indent=2, default=float))
print("\nDONE s04")
