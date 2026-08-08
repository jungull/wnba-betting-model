"""E1_I0041 s05 -- per-cell ratio distributions on the REAL 666 cells, plus FINDINGS.json."""
import json
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C = pd.read_csv(os.path.join(HERE, "TSTAT_CELL_FLOORS.csv"))
S = pd.read_csv(os.path.join(HERE, "SIMULATION.csv"))
B = pd.read_csv(os.path.join(HERE, "FAMILYWISE_BAR.csv"))
J = {k: json.load(open(os.path.join(HERE, "_s0%s.json" % k)))
     for k in ("1", "2_probe", "3", "3b", "4")}


def hdr(s):
    print("\n" + "=" * 100 + "\n" + s + "\n" + "=" * 100)


def q(v):
    v = pd.Series(v).replace([np.inf, -np.inf], np.nan).dropna()
    return dict(n=int(len(v)), min=float(v.min()), p10=float(v.quantile(.1)),
                median=float(v.median()), p90=float(v.quantile(.9)), max=float(v.max()))


hdr("A. PER-CELL RATIO DISTRIBUTIONS ON THE REAL 666 CELLS  (corrected / published)")
for c in ("mde_RA_fold_only", "mde_RB_own_bar", "mde_RC_sidak"):
    C["r_" + c] = C[c] / C["mde_published"]
OUT = {}
for scr, g in C.groupby("screen"):
    print("\n  %s (%d cells)" % (scr, len(g)))
    OUT[scr] = {}
    for c in ("mde_RA_fold_only", "mde_RB_own_bar", "mde_RC_sidak"):
        s = q(g["r_" + c])
        OUT[scr][c] = s
        print("    %-20s min=%.3f p10=%.3f median=%.3f p90=%.3f max=%.3g  (n=%d)"
              % (c.replace("mde_", ""), s["min"], s["p10"], s["median"], s["p90"],
                 s["max"], s["n"]))
    ng = g[g["degeneracy_ratio"] <= 5]
    print("    -- excluding the %d degenerate-null cells --" % (len(g) - len(ng)))
    for c in ("mde_RA_fold_only", "mde_RB_own_bar", "mde_RC_sidak"):
        s = q(ng["r_" + c])
        OUT[scr][c + "_nondegenerate"] = s
        print("    %-20s min=%.3f p10=%.3f median=%.3f p90=%.3f max=%.3g  (n=%d)"
              % (c.replace("mde_", ""), s["min"], s["p10"], s["median"], s["p90"],
                 s["max"], s["n"]))
C.to_csv(os.path.join(HERE, "TSTAT_CELL_FLOORS.csv"), index=False)

hdr("B. THE THREE BARS, IN UNITS OF EACH CELL'S OWN CORRECT sd(t)")
C["bar_published_in_sd"] = C["t_crit"] * C["sd_used_by_D103"] / C["sd_signed"]
C["bar_own_in_sd"] = C["bar_own"] / C["sd_signed"]
for scr, g in C.groupby("screen"):
    print("  %s" % scr)
    print("    D103's published bar     : median %6.3f sd(t)" % g["bar_published_in_sd"].median())
    print("    the screen's OWN bar     : median %6.3f sd(t)" % g["bar_own_in_sd"].median())
    print("    Sidak-normal, K indep    :        %6.3f sd(t)" % g["z_sidak"].iloc[0])

hdr("C. FINDINGS")
F = dict(
    experiment="E1_I0041_tstat_family_audit",
    question=("Is D103's t_statistic scale conversion -- 666 of 1,349 cells, 518 of 760 blind "
              "verdicts -- correct, in which direction is it wrong, and by how much?"),
    prereg_sha256="869a92f0bb041c825c9cf73de5f19ca9cf239b292b8756ad702fd095deafe660",
    partition="2021-2024 exploration only; 2025/26 never opened",
    anchor=J["1"]["anchor"],
    family_census=J["1"]["family_census"],

    conversion=dict(
        source="E1_I0026_detection_floor/scripts/s06_retrospective.py:66-77",
        formula="MDE80 = ((t_crit + z80) * sd_null_t)**2 / n",
        call_sites=4, call_sites_file="s06_retrospective.py lines 167,168,201,202",
        assumption_a_scale_identity=dict(
            claim="dR2 = t^2/(t^2+df) ~= t^2/n",
            verdict="SOUND -- verified on real cells, not simulated",
            evidence=J["1"]["identity_check_E0_I0014"]),
        assumption_c_signed_statistic=dict(
            claim="the statistic is signed and its null mean cancels",
            verdict=("VIOLATED for E0_I0014's 348 cells: null_correct_sd is sd(|t|). "
                     "HOLDS for E0_I0019's 318 cells: nullsd_between is sd(t)."),
            evidence=dict(E0_I0014=J["1"]["E0_I0014_null_storage"]["source_line"],
                          E0_I0019=J["1"]["E0_I0019_null_storage"]["source_line"])),
        assumption_e_threshold_scale=dict(
            claim="t_crit is a valid multiplier of a t-scale null sd",
            verdict=("VIOLATED for all 666: t_crit is the q95 max of a standardised DELTA-R^2 "
                     "statistic (right-skewed), 6.686/6.974 sd; the correctly calibrated "
                     "family-wise bar for K independent near-normal cells is 3.795/3.773 sd."),
            measured_by="s03b, 60,000-draw null cloud with a held-out calibration half")),

    gate=dict(claim_by_E1_I0037="validate() reads a file containing only increment cells",
              confirmed_at_source=True,
              detail=J["1"]["gate"],
              other_validation_found=False,
              unparsable_files_checked=20,
              only_D103_unparsable_file="scripts/s06b_ns.py -- a parquet shape probe, validates nothing"),

    machinery=dict(S1_type1=J["3"]["S1"], S2_nondegeneracy=J["3"]["S2"],
                   S3_fold_recovery=J["3"]["S3"], S4_closed_form_pass=J["3"].get("S4_pass"),
                   S5_null_sd_drift=J["3"]["S5"],
                   defective_run_preserved="SIMULATION_DEFECTIVE_s03run1.csv"),

    simulation_ratio_distribution=J["3"]["ratios"],
    familywise_bar_calibration=J["3b"]["by_tag"],
    real_cell_ratio_distribution=OUT,

    restatement=J["4"]["restatement"],
    degenerate_nulls=J["4"]["degenerate"],
    structural_gates=J["4"]["gates"],

    headline=dict(
        published_blind="760 / 1349 = 0.5633802816901409",
        primary_correction="R-B (each screen's own family-wise bar): 908 / 1349 = 0.6731, +148 cells, +10.97 pp",
        fold_only="R-A: 886 / 1349 = 0.6568, +126 cells, +9.34 pp",
        counter_result="R-C (Sidak-normal bar): 613 / 1349 = 0.4544, -147 cells, -10.90 pp",
        direction=("The conversion is defective and ANTI-CONSERVATIVE relative to the decision "
                   "rule each screen actually applied: D103 understates how blind the "
                   "t_statistic family was.  Against a textbook Sidak bar the sign reverses, "
                   "and that is reported with equal prominence."),
        qualitative_verdict="D103's conclusion SURVIVES and STRENGTHENS under the primary correction"),
)
json.dump(F, open(os.path.join(HERE, "FINDINGS.json"), "w"), indent=2, default=str)
print(json.dumps(F["headline"], indent=2))
print("\nwrote FINDINGS.json")
