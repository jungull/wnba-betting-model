"""S11 -- assemble BROKEN_NULLS.csv: all 73 cells, mechanism, resolution, corrected class."""
import json, os
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPL = os.path.dirname(HERE)
S14 = os.path.join(EXPL, "E0_I0014_residual_heterogeneity")
BEST = 0.0023        # D103's best-lead comparison
FLOOR1 = 0.00102     # D103's single-cell floor

tf = pd.read_csv(os.path.join(EXPL, "E1_I0041_tstat_family_audit", "TSTAT_CELL_FLOORS.csv"))
brk = tf[(tf["degeneracy_ratio"] > 5) | (tf["sd_used_by_D103"] == 0.0)].copy()
assert len(brk) == 73

DIAG = pd.read_csv(os.path.join(HERE, "_E0_I0014_CELL_DIAG.csv")).set_index("cell")
SB = pd.read_csv(os.path.join(HERE, "_STATISTIC_BLINDNESS.csv")).set_index("cell")
RM1 = pd.read_csv(os.path.join(HERE, "_REMEASURE_ALL_ARMS.csv"))
RM2 = pd.read_csv(os.path.join(HERE, "_REMEASURE2_ALL_ARMS.csv"))
E19 = pd.read_csv(os.path.join(HERE, "_E0_I0019_ARMS.csv"))

# both of E0_I0014's original schemes, per cell, so we can say whether EITHER worked
z = np.load(os.path.join(S14, "permutation_nulls.npz"), allow_pickle=True)
nm14 = [str(s) for s in z["names"]]
dp14 = [str(s) for s in z["dependents"]]
both = {}
for j, c in enumerate(nm14):
    for k in dp14:
        r = {}
        for tag, key in (("BETWEEN-block", "bet__"), ("WITHIN-block", "win__"),
                         ("row-NAIVE", "row__")):
            a = z[key + k][:, j]
            sd = a.std(ddof=1)
            r[tag] = float(a.mean() / sd) if sd > 0 else np.inf
        both["%s|%s" % (c, k)] = r

VOID = {"pts__pred_sd", "minutes__pred_sd", "fga__pred_sd"}

def arm(df, a):
    return df[df["arm"] == a].set_index("cell")
A2 = {a: arm(RM2, a) for a in ["A4_CLEAN_DEC", "A3_CLEAN", "A2_DEC", "A1_FULL"]}
A1c = {a: arm(RM1, a) for a in ["A4_CLEAN_DEC", "A1_FULL"]}

def klass(mde):
    if not np.isfinite(mde):
        return "UNVERIFIABLE"
    return "ADEQUATELY_POWERED" if mde <= BEST else "BLIND"

rows = []
for _, b in brk.iterrows():
    cell = b["cell"]; scr = b["screen"]
    cand = cell.split("|")[0]; dep = cell.split("|")[1]
    d103_class = "ADEQUATELY_POWERED" if b["mde_published"] <= BEST else "BLIND"
    rec = dict(
        screen=scr, cell=cell, candidate=cand, dependent=dep, n_published=int(b["n"]),
        d103_sd_used=float(b["sd_used_by_D103"]),
        d103_degeneracy_ratio=float(b["degeneracy_ratio"]),
        d103_mde_published=float(b["mde_published"]),
        d103_classification=d103_class,
        broken_kind=("SD_EXACTLY_ZERO" if b["sd_used_by_D103"] == 0.0 else "DEGENERATE_GT5"),
    )
    if scr == "E0_I0014_residual_heterogeneity":
        d = DIAG.loc[cell]
        rec.update(
            null_scheme_used=d["null_used"], candidate_vsb=float(d["vsb"]),
            n_blocks=int(d["n_blocks"]),
            n_unique_draws_published=int(d["n_unique_draws"]),
            statistic_constant_under_null=bool(d["n_unique_draws"] == 1),
            permutation_set_trivial=bool(d["n_blocks"] < 6),
            max_within_block_spread_z=float(d["max_within_block_spread_z"]),
            degeneracy_BETWEEN_arm=both[cell]["BETWEEN-block"],
            degeneracy_WITHIN_arm=both[cell]["WITHIN-block"],
            degeneracy_rowNAIVE_arm=both[cell]["row-NAIVE"],
        )
        if cand in VOID:
            rec["mechanism"] = "M-VOID: candidate has ONE distinct value per season; " \
                               "collinear with the base (season fixed effects); sxx after " \
                               "base <= 4.6e-26 against 1.3876e+04 for every other candidate"
            rec["statistic_blindness_max_abs_change"] = (
                float(SB.loc[cell, "max_abs_change"]) if cell in SB.index else np.nan)
            rec["resolution"] = "PERMANENTLY_UNVERIFIABLE"
            rec["resolution_reason"] = "STRUCTURALLY_VOID -- no statistic exists, so no null " \
                                       "can exist.  dR2 is identically 0 after the base."
        else:
            rec["mechanism"] = (
                "M-WITHIN: the within-block shuffle preserves each block mean EXACTLY "
                "(measured 1.776e-15), so the between-block share of the candidate survives "
                "and carries the association"
                if d["null_used"] == "WITHIN-block" else
                "M-BETWEEN: block_index maps the donor block onto the receiver IN "
                "CHRONOLOGICAL POSITION ORDER and truncates a long donor to its first len(b) "
                "rows, so the within-block ordinal profile survives the reassignment")
            rec["statistic_blindness_max_abs_change"] = float(SB.loc[cell, "max_abs_change"])
            rec["resolution"] = "RE_MEASURED_COMPOSED2"
            rec["resolution_reason"] = "composed-2 null (donor block resampled uniformly, " \
                                       "positions randomised) destroys both blind spots"
        for a in ["A4_CLEAN_DEC", "A3_CLEAN", "A2_DEC", "A1_FULL"]:
            r2 = A2[a].loc[cell]
            pre = {"A4_CLEAN_DEC": "A4", "A3_CLEAN": "A3", "A2_DEC": "A2", "A1_FULL": "A1"}[a]
            rec["%s_n" % pre] = int(r2["n"])
            rec["%s_n_blocks" % pre] = int(r2["n_blocks"])
            rec["%s_null_mean_signed_t" % pre] = float(r2["null_mean_signed_t"])
            rec["%s_null_sd_signed_t" % pre] = float(r2["null_sd_signed_t"])
            rec["%s_degeneracy_ratio" % pre] = float(r2["degeneracy_ratio"])
            rec["%s_null_functions" % pre] = bool(
                abs(r2["null_mean_signed_t"]) < 0.20 and 1.10 <= r2["degeneracy_ratio"] <= 1.60)
            rec["%s_observed_dr2" % pre] = float(r2["observed_dr2"])
            rec["%s_p_two_sided" % pre] = float(r2["p_two_sided"])
            rec["%s_mde80_percell" % pre] = float(r2["mde80_percell"])
            rec["%s_mde80_familywise" % pre] = float(r2["mde80_familywise"])
            rec["%s_class_percell" % pre] = klass(r2["mde80_percell"])
            rec["%s_below_single_cell_floor" % pre] = bool(r2["observed_dr2"] < FLOOR1)
        rec["corrected_classification_LIKE_FOR_LIKE_A1"] = rec["A1_class_percell"]
        rec["corrected_classification_DECISION_STRATUM_A4"] = rec["A4_class_percell"]
        if cand in VOID:
            rec["corrected_classification_LIKE_FOR_LIKE_A1"] = "PERMANENTLY_UNVERIFIABLE"
            rec["corrected_classification_DECISION_STRATUM_A4"] = "PERMANENTLY_UNVERIFIABLE"
    else:
        # E0_I0019 pl_opps_prior|brier -- resolved from its own draw archive, no refit
        pb = E19[E19["arm"] == "player_between"].iloc[0]
        pw = E19[E19["arm"] == "player_within"].iloc[0]
        rw = E19[E19["arm"] == "row"].iloc[0]
        rec.update(
            null_scheme_used="player_between (BETWEEN player-season relabel)",
            candidate_vsb=0.093425, n_blocks=np.nan,
            n_unique_draws_published=int(pb["n_unique"]),
            statistic_constant_under_null=False, permutation_set_trivial=False,
            degeneracy_BETWEEN_arm=float(pb["degeneracy_ratio"]),
            degeneracy_WITHIN_arm=float(pw["degeneracy_ratio"]),
            degeneracy_rowNAIVE_arm=float(rw["degeneracy_ratio"]),
            mechanism="M-BETWEEN: a BETWEEN-player-season relabel applied to a candidate whose "
                      "own recorded var_share_between is 0.0934 -- 91% of it lives WITHIN the "
                      "block the relabel cannot move.  BOTH block arms on disk are degenerate "
                      "(5.01 and 5.14); only the row-NAIVE arm is centred (1.368), and the "
                      "screen's own measurement shows that arm is anticonservative.",
            statistic_blindness_max_abs_change=np.nan,
            resolution="PERMANENTLY_UNVERIFIABLE",
            resolution_reason="NO FUNCTIONING NULL ON DISK.  Repairable only by a 2,000-draw "
                              "composed null on E0_I0019's own frame, which is a refit and was "
                              "not run here.  Bound reported in VERDICT, not adopted.")
        rec["corrected_classification_LIKE_FOR_LIKE_A1"] = "PERMANENTLY_UNVERIFIABLE"
        rec["corrected_classification_DECISION_STRATUM_A4"] = "PERMANENTLY_UNVERIFIABLE"
    rec["floor_basis"] = "ANALYTIC"      # upgraded to INJECTION_VERIFIED in s12 where applicable
    rows.append(rec)

B = pd.DataFrame(rows)
assert len(B) == 73
B.to_csv(os.path.join(HERE, "BROKEN_NULLS.csv"), index=False)
print("wrote BROKEN_NULLS.csv", B.shape)

print("\n=== RESOLUTION ===")
print(B["resolution"].value_counts().to_string())
print("\n=== MECHANISM (first token) ===")
print(B["mechanism"].str.split(":").str[0].value_counts().to_string())
print("\n=== D103 class  ->  corrected class (LIKE-FOR-LIKE, arm A1_FULL) ===")
print(pd.crosstab(B["d103_classification"],
                  B["corrected_classification_LIKE_FOR_LIKE_A1"]).to_string())
print("\n=== D103 class  ->  corrected class (DECISION STRATUM, arm A4_CLEAN_DEC) ===")
print(pd.crosstab(B["d103_classification"],
                  B["corrected_classification_DECISION_STRATUM_A4"]).to_string())

adeq = B[B["d103_classification"] == "ADEQUATELY_POWERED"]
print("\n=== THE 35 ===  n=%d" % len(adeq))
print(adeq["corrected_classification_LIKE_FOR_LIKE_A1"].value_counts().to_string())
print("\nby candidate:")
print(adeq.groupby(["candidate", "corrected_classification_LIKE_FOR_LIKE_A1"]).size().to_string())

rem = B[B["resolution"] == "RE_MEASURED_COMPOSED2"]
print("\n=== RE-MEASURED CELLS: p under the composed-2 null ===")
for a, pre in [("A4_CLEAN_DEC", "A4"), ("A1_FULL", "A1")]:
    p = rem["%s_p_two_sided" % pre]
    print("  %-14s  n=%d  p<0.05: %d   min p %.4f   median p %.4f"
          % (a, len(p), int((p < 0.05).sum()), p.min(), p.median()))
print("\n--- cells with composed-2 p < 0.05 on the decision-stratum arm A4 ---")
sv = rem[rem["A4_p_two_sided"] < 0.05]
print(sv[["cell", "A4_n", "A4_observed_dr2", "A4_p_two_sided", "A4_mde80_percell",
          "A4_below_single_cell_floor"]].to_string(index=False)
      if len(sv) else "  (none)")
print("\n--- cells with composed-2 p < 0.05 on A1_FULL ---")
sv1 = rem[rem["A1_p_two_sided"] < 0.05]
print(sv1[["cell", "A1_observed_dr2", "A1_p_two_sided", "A1_mde80_percell",
           "A1_below_single_cell_floor"]].to_string(index=False)
      if len(sv1) else "  (none)")
print("\nDONE s11")
