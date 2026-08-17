"""S09 -- final consistency pass.  Every number asserted in the markdown is re-read here."""
import json, os
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
J = pd.read_csv(os.path.join(HERE, "CORRECTED_VERDICTS.csv"))
T = pd.read_csv(os.path.join(HERE, "TYPEI_PER_CELL.csv"))
F = json.load(open(os.path.join(HERE, "FINDINGS.json")))
ok = True
def chk(lab, got, want):
    global ok
    good = (got == want)
    ok &= good
    print("  [%s] %-62s got %-8s want %s" % ("OK " if good else "!!", lab, got, want))

a4 = J[J["arm"] == "A4_CLEAN_DEC"]
t4 = T[T["arm"] == "A4_CLEAN_DEC"]
acc4 = t4["null_validity"].astype(str).str.startswith("ACCEPTABLE")
chk("A4: cells in queue", len(a4), 54)
chk("A4: null acceptable", int(acc4.sum()), 48)
chk("A4: no statistic in stratum", int((t4["null_validity"] ==
     "UNVERIFIABLE_IN_STRATUM_NO_STATISTIC").sum()), 4)
chk("A4: null invalid", int((t4["null_validity"] == "INVALID_ANTICONSERVATIVE").sum()), 2)
chk("A4: per-cell p<0.05 (E1_I0044's 37)", int((a4["p_percell_plus1"] < 0.05).sum()), 37)
m = a4.merge(t4[["cell", "null_validity"]], on="cell")
chk("A4: of the 37, null acceptable",
    int(((m["p_percell_plus1"] < 0.05) &
         m["null_validity_y"].astype(str).str.startswith("ACCEPTABLE")).sum()), 35)
chk("A4: family-wise p<0.05 (E1_I0044's 17)", int((a4["p_familywise_plus1"] < 0.05).sum()), 17)
chk("A4: family-wise survivors, acceptable + unconfounded",
    int((a4["corrected_verdict"] == "FAMILYWISE_SIGNIFICANT").sum()), 16)
s = a4[a4["corrected_verdict"] == "FAMILYWISE_SIGNIFICANT"]
chk("A4: survivors all clear D103 single-cell floor 0.00102",
    int(s["clears_D103_single_cell_floor_0.00102"].sum()), 16)
chk("A4: survivors with published p_fw == 1.000 (15; the 16th is the bar cell itself)",
    int((s["published_p_familywise_whole_screen"] == 1.0).sum()), 15)
chk("A4: survivors ALSO not significant on E0_I0014's own per-cell column",
    int((s["published_p_correct_level"] >= 0.05).sum()), 6)
print("  A4 survivor dR2 range: %.5f - %.5f  (n=%d, blocks=%d)"
      % (s["observed_dr2"].min(), s["observed_dr2"].max(), s["n"].iloc[0], s["n_blocks"].iloc[0]))

a1 = J[J["arm"] == "A1_FULL"]; t1 = T[T["arm"] == "A1_FULL"]
chk("A1: null acceptable",
    int(t1["null_validity"].astype(str).str.startswith("ACCEPTABLE").sum()), 53)
chk("A1: family-wise survivors clean",
    int((a1["corrected_verdict"] == "FAMILYWISE_SIGNIFICANT").sum()), 24)
chk("A1: of the 49 published-1.000, acceptable null",
    int((a1["published_pfw_is_exactly_1.000"] &
         a1["null_validity"].astype(str).str.startswith("ACCEPTABLE")).sum()), 48)
chk("A1: of those, family-wise p<0.05",
    int((a1["published_pfw_is_exactly_1.000"] &
         a1["null_validity"].astype(str).str.startswith("ACCEPTABLE") &
         (a1["p_familywise_plus1"] < 0.05)).sum()), 31)
chk("published p_correct_level < 0.05 among the 54",
    int((a4["published_p_correct_level"] < 0.05).sum()), 25)

print("\n-- storage discipline: are the saved draws SIGNED? --")
for f in ("typeI_raw_A4_CLEAN_DEC.npz", "typeI_raw_A1_FULL.npz",
          "posadj_composed2_A4_CLEAN_DEC.npz", "posadj_composed2_A1_FULL.npz"):
    z = np.load(os.path.join(HERE, "nulls", f), allow_pickle=True)
    ks = [k for k in z.files if k.startswith(("tobs__", "tnull5__", "t_signed__"))]
    neg = sum(1 for k in ks[:60] if np.nanmin(z[k]) < 0)
    print("   %-34s %4d stat arrays, %d of the first %d contain negative values -> SIGNED"
          % (f, len(ks), neg, min(60, len(ks))))
    assert neg > 0, "no negative values found -- draws may have been stored as |t|"

print("\n-- deliverables present --")
for f in ("PREREG.md", "PREREG.sha256", "TYPEI_PER_CELL.csv", "CORRECTED_VERDICTS.csv",
          "WHY_1.000.md", "SHAPE_RULE.md", "VERDICT.md", "NOTES.md", "DEFECTS.md",
          "FINDINGS.json"):
    p = os.path.join(HERE, f)
    print("   %-26s %s  %d bytes" % (f, "OK" if os.path.exists(p) else "MISSING",
                                     os.path.getsize(p) if os.path.exists(p) else 0))

print("\nALL CONSISTENT" if ok else "\n*** MISMATCH ***")
