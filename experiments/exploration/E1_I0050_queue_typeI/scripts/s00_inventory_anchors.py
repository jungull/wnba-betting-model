"""S00 -- ANCHORS FIRST, then the explicit allowlist of the 54.

Nothing new is computed until prior screens' published numbers are reproduced from their
own artefacts.  No name-based selection anywhere: the 54 cells come from an explicit
resolution column, the list is printed in full and its count asserted, and the 18
structurally-void cells are asserted disjoint from it.
"""
import json, os, sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *          # noqa

OUT = HERE
np.set_printoptions(suppress=True)
print("PARTITION: seasons present in E0_I0014's frame =", SEASONS_PRESENT)
print("           2025/26 never opened.  n =", n, " candidates =", C, " dependents =", len(DEPS))

rep = {}
def anchor(name, got, want, tol=0.0, note=""):
    ok = (abs(got - want) <= tol) if isinstance(want, (int, float, np.floating)) else (got == want)
    rep[name] = dict(reproduced=float(got) if isinstance(got, (int, float, np.floating)) else got,
                     published=float(want) if isinstance(want, (int, float, np.floating)) else want,
                     ok=bool(ok), note=note)
    print("  [%s] %-58s got %-24s want %-24s %s"
          % ("OK " if ok else "FAIL", name, got, want, note))
    return ok

print("\n=== ANCHOR BLOCK A -- D103 (E1_I0026 retrospective_power.csv) ===")
D103 = pd.read_csv(os.path.join(S26, "out", "retrospective_power.csv"))
key = ["screen", "decision", "family_size_K", "cell"]
# worst null arm == largest mde80_fw, exactly as E1_I0044 reproduced it
g = D103.sort_values("mde80_fw").groupby(key, dropna=False).tail(1)
blind = g["mde80_fw"] > 0.0023        # D103's own blindness bar, stated not assumed
anchor("D103_n_cells", int(len(g)), 1349)
anchor("D103_n_blind", int(blind.sum()), 760)
anchor("D103_blind_frac_repr", repr(float(blind.mean())), repr(0.5633802816901409))

print("\n=== ANCHOR BLOCK B -- E1_I0041 t-statistic family ===")
tf = pd.read_csv(os.path.join(EXPL, "E1_I0041_tstat_family_audit", "TSTAT_CELL_FLOORS.csv"))
deg = tf["degeneracy_ratio"] > 5
sd0 = tf["sd_used_by_D103"] == 0.0
brk = deg | sd0
anchor("E1_I0041_tstat_cells", int(len(tf)), 666)
anchor("E1_I0041_degenerate_gt5", int(deg.sum()), 67)
anchor("E1_I0041_sd_exactly_zero", int(sd0.sum()), 6)
anchor("E1_I0041_overlap", int((deg & sd0).sum()), 0)
anchor("E1_I0041_broken_total", int(brk.sum()), 73)
anchor("E1_I0041_broken_recorded_adequate", int((tf.loc[brk, "mde_published"] <= 0.0023).sum()), 35)

print("\n=== ANCHOR BLOCK C -- E0_I0014 recomputed from its own frame ===")
SR = pd.read_csv(os.path.join(S14, "screen_results.csv"))
z = np.load(os.path.join(S14, "permutation_nulls.npz"), allow_pickle=True)
# vsb
vsb_pub = z["vsb"]
key14 = SR.set_index(["candidate", "dependent"])
tcl = {(r.candidate, r.dependent): r.t_classical for r in SR.itertuples()}
mx_t, nbit, nmm, mx_sd = 0.0, 0, 0, 0.0
sd_pub = {(r.candidate, r.dependent): r.null_correct_sd for r in SR.itertuples()}
p_pub = {(r.candidate, r.dependent): r.p_correct_level for r in SR.itertuples()}
mism_p = 0
for k, _ in DEPS:
    rt = real_t[k]
    dr = draws[k]
    for j, nm in enumerate(names):
        if (nm, k) not in tcl:
            continue
        a, b = float(rt[j]), float(tcl[(nm, k)])
        if np.isfinite(a) and np.isfinite(b):
            mx_t = max(mx_t, abs(a - b) / max(abs(b), 1e-12))
            if a == b:
                nbit += 1
        sd_r = float(np.std(dr[:, j], ddof=1))
        mx_sd = max(mx_sd, abs(sd_r - float(sd_pub[(nm, k)])))
        p_r = float((np.abs(dr[:, j]) >= abs(a)).mean()) if np.isfinite(a) else np.nan
        if np.isfinite(a) and abs(p_r - float(p_pub[(nm, k)])) > 1e-12:
            mism_p += 1
anchor("E0_I0014_t_classical_max_rel", mx_t, 3.939e-15, 1e-16, "E1_I0044 got 3.939e-15")
anchor("E0_I0014_t_classical_bitwise", nbit, 276)
anchor("E0_I0014_null_correct_sd_maxabs", mx_sd, 2.220e-16, 1e-16)
anchor("E0_I0014_p_correct_level_mismatches", mism_p, 0)

print("\n=== ANCHOR BLOCK D -- the published family-wise bar (this is the 1.000 question) ===")
FW = json.load(open(os.path.join(S14, "familywise_summary.json")))
anchor("E0_I0014_maxt_correct_mean", FW["null_maxt_correct"]["mean"], 27.577598195648264, 1e-12)
anchor("E0_I0014_maxt_correct_p95", FW["null_maxt_correct"]["p95"], 29.12663204615966, 1e-12)
anchor("E0_I0014_maxt_rownaive_p95", FW["null_maxt_row_naive"]["p95"], 3.7295261371093513, 1e-12)
anchor("E0_I0014_obs_max_abs_t", FW["observed_max_abs_t_whole_screen"], 41.60553110904952, 1e-12)
# reproduce maxt_cor from the saved draws
maxt_cor = np.stack([np.abs(draws[k]) for k, _ in DEPS], 0).max(axis=0).max(axis=1)
anchor("maxt_cor_mean_recomputed", float(maxt_cor.mean()), FW["null_maxt_correct"]["mean"], 1e-9)
anchor("maxt_cor_p95_recomputed", float(np.percentile(maxt_cor, 95)),
       FW["null_maxt_correct"]["p95"], 1e-9)

print("\n=== ANCHOR BLOCK E -- E1_I0044's own outputs ===")
BN = pd.read_csv(os.path.join(S44, "BROKEN_NULLS.csv"))
anchor("E1_I0044_broken_rows", int(len(BN)), 73)
res = BN["resolution"].value_counts().to_dict()
print("   resolution counts:", res)
anchor("E1_I0044_re_measured", int((BN["resolution"] == "RE_MEASURED_COMPOSED2").sum()), 54)
RM2 = pd.read_csv(os.path.join(S44, "_REMEASURE2_ALL_ARMS.csv"))
FWC = pd.read_csv(os.path.join(S44, "_FAMILYWISE_P_COMPOSED2.csv"))
TIC = pd.read_csv(os.path.join(S44, "TYPE_I_CALIBRATION.csv"))

# ---------------- THE ALLOWLIST -------------------------------------------------
CELLS54 = sorted(BN.loc[BN["resolution"] == "RE_MEASURED_COMPOSED2", "cell"].tolist())

# The void set is identified BY MEASUREMENT, not by reading a label: a candidate is void
# when its design column is annihilated by the screen's own base (season fixed effects).
# The label is then used only as a cross-check.
SXX_ALL = {nm: float((Xztil[:, j] ** 2).sum()) for j, nm in enumerate(names)}
VOID_CANDS_MEASURED = sorted([nm for nm, v in SXX_ALL.items() if v < 1e-6])
VOID18 = sorted([c for c in BN["cell"] if c.split("|")[0] in VOID_CANDS_MEASURED])
VOID18_LABELLED = sorted(BN.loc[BN["resolution_reason"].str.startswith("STRUCTURALLY_VOID"),
                                "cell"].tolist())
print("\n   void candidates BY MEASUREMENT (sxx after base < 1e-6):", VOID_CANDS_MEASURED)
print("   sxx of those:", [SXX_ALL[c] for c in VOID_CANDS_MEASURED])
print("   sxx median over all other candidates: %.4e"
      % np.median([v for k, v in SXX_ALL.items() if k not in VOID_CANDS_MEASURED]))
anchor("void_measured_equals_labelled", VOID18 == VOID18_LABELLED, True)
NONULL = sorted(BN.loc[~BN["cell"].isin(CELLS54 + VOID18), "cell"].tolist())
print("\n--- EXPLICIT ALLOWLIST: the 54 re-measured cells, printed in full ---")
for i, c in enumerate(CELLS54):
    print("   %2d  %s" % (i + 1, c))
assert len(CELLS54) == 54 and len(set(CELLS54)) == 54, "allowlist is not 54 distinct cells"
print("\n--- the 18 STRUCTURALLY VOID cells (must NOT appear above) ---")
for c in VOID18:
    print("   VOID  %s" % c)
assert len(VOID18) == 18, "expected 18 structurally void, got %d" % len(VOID18)
leak = sorted(set(CELLS54) & set(VOID18))
print("VOID-LEAK CHECK: |CELLS54 n VOID18| = %d  -> %s" % (len(leak), leak))
assert len(leak) == 0, "STRUCTURALLY VOID CELLS LEAKED INTO THE QUEUE: %s" % leak
print("--- the remaining cell(s):", NONULL)
assert len(CELLS54) + len(VOID18) + len(NONULL) == 73

# independent void check from the frame itself: distinct values per season
print("\n--- independent verification that the 18 are void (from the frame, not the label) ---")
void_cands = sorted({c.split("|")[0] for c in VOID18})
for cand in sorted({c.split("|")[0] for c in CELLS54} | set(void_cands)):
    j = names.index(cand)
    dvs = [len(np.unique(X[seas == s, j])) for s in SEASONS_PRESENT]
    sxx = float((Xztil[:, j] ** 2).sum())
    tag = "VOID-LABELLED" if cand in void_cands else "queue"
    if cand in void_cands or min(dvs) <= 2:
        print("   %-24s distinct-per-season %s  sxx_after_base %.4e   [%s]"
              % (cand, dvs, sxx, tag))
qsxx = {c.split("|")[0]: float((Xztil[:, names.index(c.split("|")[0])] ** 2).sum())
        for c in CELLS54}
print("   min sxx over the 54 queue candidates: %.6e   (void candidates are ~0)"
      % min(qsxx.values()))
assert min(qsxx.values()) > 1.0, "a queue candidate is annihilated by the base"

# ---------------- reproduce E1_I0044's headline counts ---------------------------
print("\n=== ANCHOR BLOCK F -- the 37 / 17 / 41 that this screen exists to test ===")
A4 = RM2[RM2["arm"] == "A4_CLEAN_DEC"].set_index("cell")
q4 = A4.loc[CELLS54]
n37 = int((q4["p_two_sided"] < 0.05).sum())
anchor("E1_I0044_A4_p_lt_0.05", n37, 37)
fw4 = FWC[FWC["arm"] == "A4_CLEAN_DEC"].set_index("cell").loc[CELLS54]
n17 = int((fw4["p_familywise"] < 0.05).sum())
anchor("E1_I0044_A4_familywise_lt_0.05", n17, 17)
pubfw = SR.set_index(["candidate", "dependent"])["p_familywise_whole_screen"]
pfw_pub = np.array([pubfw.loc[(c.split("|")[0], c.split("|")[1])] for c in CELLS54])
anchor("E0_I0014_published_pfw_exactly_1.000", int((pfw_pub == 1.0).sum()), 41)
anchor("E1_I0044_typeI_composed2_median", float(TIC["typeI_composed2"].median()), 0.0525, 1e-12)

print("\n=== ANCHOR SUMMARY ===")
nok = sum(1 for v in rep.values() if v["ok"])
print("   %d of %d anchors reproduced" % (nok, len(rep)))

json.dump(dict(anchors=rep, n_anchors=len(rep), n_ok=nok,
               seasons_present=[int(s) for s in SEASONS_PRESENT],
               cells54=CELLS54, void18=VOID18, other=NONULL,
               published_pfw_exactly_one=[CELLS54[i] for i in range(54) if pfw_pub[i] == 1.0]),
          open(os.path.join(OUT, "scripts", "_s00.json"), "w"), indent=2)
pd.DataFrame(dict(cell=CELLS54,
                  candidate=[c.split("|")[0] for c in CELLS54],
                  dependent=[c.split("|")[1] for c in CELLS54],
                  published_p_correct_level=[p_pub[(c.split("|")[0], c.split("|")[1])] for c in CELLS54],
                  published_p_familywise_whole_screen=pfw_pub,
                  E1_I0044_A4_p_two_sided=q4["p_two_sided"].to_numpy(),
                  E1_I0044_A4_p_familywise=fw4["p_familywise"].to_numpy(),
                  E1_I0044_A4_observed_dr2=q4["observed_dr2"].to_numpy(),
                  E1_I0044_A4_n=q4["n"].to_numpy(),
                  E1_I0044_A4_n_blocks=q4["n_blocks"].to_numpy(),
                  )).to_csv(os.path.join(OUT, "_QUEUE54.csv"), index=False)
print("wrote _QUEUE54.csv  and scripts/_s00.json")
print("DONE s00")
