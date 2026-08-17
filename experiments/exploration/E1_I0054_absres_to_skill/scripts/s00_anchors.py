"""S00 -- ANCHORS.  Nothing else in this screen runs until every one of these passes.

R-A1  my t_classical, 348 cells, full frame          vs E0_I0014/screen_results.csv
R-A2  my delta_r2_plain_unweighted, 348 cells        vs the same file
R-A3  my A4 observed signed t and dR2, 54 queue cells vs E1_I0050/CORRECTED_VERDICTS.csv
R-C   single-cell dominance of E0_I0014's PUBLISHED family-wise bar, from its own draws
"""
import json, os, sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *  # noqa

print("frame n=%d  seasons=%s  candidates=%d  dependents=%d  cells=%d"
      % (n, SEASONS_PRESENT, C, len(DEP_NAMES), C * len(DEP_NAMES)), flush=True)
print("PLAYER-scheme %d  TEAM-scheme %d" % (int(is_player.sum()), int((~is_player).sum())))

out = {}

# ------------------------------------------------------------------------ R-A1/R-A2
SR = pd.read_csv(os.path.join(S14, "screen_results.csv"))
SR["cell"] = SR["candidate"] + "|" + SR["dependent"]
pub = SR.set_index("cell")
assert len(SR) == C * len(DEP_NAMES), "cell count mismatch: %d vs %d" % (len(SR), C * len(DEP_NAMES))
assert sorted(set(SR["candidate"])) == sorted(names), "candidate set mismatch"

ctx_full = arm_context(ARM_MASKS["A1_FULL"])
rows = []
for k in DEP_NAMES:
    beta, t, dr2 = t_and_dr2(ctx_full["Yt"][k], ctx_full["Xzt"], ctx_full["df"], ctx_full["SST"][k])
    for j, nm in enumerate(names):
        rows.append(dict(cell="%s|%s" % (nm, k), candidate=nm, dependent=k,
                         my_t=float(t[j]), my_dr2=float(dr2[j]), my_beta=float(beta[j])))
MINE = pd.DataFrame(rows).set_index("cell")
J = MINE.join(pub[["t_classical", "delta_r2_plain_unweighted", "beta_per_sd"]], how="inner")
assert len(J) == C * len(DEP_NAMES)

dt = (J["my_t"] - J["t_classical"]).abs()
rel = dt / J["t_classical"].abs().clip(lower=1e-12)
ddr = (J["my_dr2"] - J["delta_r2_plain_unweighted"]).abs()
db = (J["my_beta"] - J["beta_per_sd"]).abs()
nbit = int((J["my_t"].to_numpy() == J["t_classical"].to_numpy()).sum())
print("\nR-A1  max |dt| %.3e   max rel |dt| %.3e   bitwise-identical %d/%d"
      % (dt.max(), rel.max(), nbit, len(J)))
print("R-A2  max |ddR2| %.3e   max |dbeta| %.3e" % (ddr.max(), db.max()))
out["R_A1_max_abs_dt"] = float(dt.max())
out["R_A1_max_rel_dt"] = float(rel.max())
out["R_A1_bitwise_identical"] = nbit
out["R_A1_n_cells"] = int(len(J))
out["R_A2_max_abs_ddr2"] = float(ddr.max())
out["R_A2_max_abs_dbeta"] = float(db.max())
assert rel.max() < 1e-9, "R-A1 FAILED"
assert ddr.max() < 1e-12, "R-A2 FAILED"
print("R-A1 PASS   R-A2 PASS")

# ---------------------------------------------------------------------------- R-A3
CV = pd.read_csv(os.path.join(S50, "CORRECTED_VERDICTS.csv"))
a4 = CV[CV["arm"] == "A4_CLEAN_DEC"].copy()
CELLS54 = sorted(a4["cell"].tolist())
assert len(CELLS54) == 54 and len(set(CELLS54)) == 54

ctx4 = arm_context(ARM_MASKS["A4_CLEAN_DEC"])
print("\nA4_CLEAN_DEC  n=%d  df=%d  seasons=%s"
      % (ctx4["m"], ctx4["df"], sorted(set(int(s) for s in ctx4["ss"]))))
gp4 = blocks_on(ARM_MASKS["A4_CLEAN_DEC"], "player_id")
gt4 = blocks_on(ARM_MASKS["A4_CLEAN_DEC"], "team_id")
nbp = sum(len(v) for v in gp4.values()); nbt = sum(len(v) for v in gt4.values())
print("player-season blocks %d   team-season blocks %d" % (nbp, nbt))
assert ctx4["m"] == 3549, ctx4["m"]
assert nbp == 174, nbp

mine4 = {}
for k in DEP_NAMES:
    beta, t, dr2 = t_and_dr2(ctx4["Yt"][k], ctx4["Xzt"], ctx4["df"], ctx4["SST"][k])
    for j, nm in enumerate(names):
        mine4["%s|%s" % (nm, k)] = (float(t[j]), float(dr2[j]))
a4 = a4.set_index("cell")
d_t, d_r = [], []
for c in CELLS54:
    if not np.isfinite(a4.loc[c, "observed_signed_t"]):
        continue
    d_t.append(abs(mine4[c][0] - a4.loc[c, "observed_signed_t"]))
    d_r.append(abs(mine4[c][1] - a4.loc[c, "observed_dr2"]))
print("R-A3  n comparable %d   max |dt| %.3e   max |ddR2| %.3e"
      % (len(d_t), max(d_t), max(d_r)))
out["R_A3_n"] = len(d_t)
out["R_A3_max_abs_dt"] = float(max(d_t))
out["R_A3_max_abs_ddr2"] = float(max(d_r))
assert max(d_t) < 1e-9 and max(d_r) < 1e-9, "R-A3 FAILED"
print("R-A3 PASS")

# the 16, formed by NUMERIC predicate on E1_I0050's table -- no substring anywhere
sel = a4[(a4["p_familywise_plus1"] < 0.05)
         & (a4["null_validity"].astype(str).str.startswith("ACCEPTABLE"))]
THE16 = sorted(sel.index.tolist())
print("\nE1_I0050's A4 family-wise-significant set, by numeric predicate: %d cells" % len(THE16))
for c in THE16:
    print("   %-34s t=%+8.3f  dR2=%.6f  pfw=%.5f" % (c, a4.loc[c, "observed_signed_t"],
                                                     a4.loc[c, "observed_dr2"],
                                                     a4.loc[c, "p_familywise_plus1"]))
out["published_16"] = THE16
out["cells54"] = CELLS54

# ------------------------------------------------------------------------------ R-C
# Single-cell dominance of E0_I0014's PUBLISHED bar, rebuilt from its own saved draws.
z = np.load(os.path.join(S14, "permutation_nulls.npz"), allow_pickle=True)
zn = [str(s) for s in z["names"]]
assert zn == names, "published draw column order differs from my rebuild"
ub = z["use_between"]
cor = {k: np.where(ub[None, :], z["bet__" + k], z["win__" + k]) for k in DEP_NAMES}
ALL = np.concatenate([cor[k] for k in DEP_NAMES], axis=1)          # (1000, 348)
cellnames = ["%s|%s" % (nm, k) for k in DEP_NAMES for nm in names]
mx = ALL.max(axis=1)
arg = ALL.argmax(axis=1)
vc = pd.Series([cellnames[i] for i in arg]).value_counts()
fw = json.load(open(os.path.join(S14, "familywise_summary.json")))
print("\nR-C  PUBLISHED bar rebuilt from E0_I0014's own draws")
print("   mean %.4f  p95 %.4f   (published json: mean %.4f  p95 %.4f)   |d| %.2e / %.2e"
      % (mx.mean(), np.percentile(mx, 95), fw["null_maxt_correct"]["mean"],
         fw["null_maxt_correct"]["p95"],
         abs(mx.mean() - fw["null_maxt_correct"]["mean"]),
         abs(np.percentile(mx, 95) - fw["null_maxt_correct"]["p95"])))
print("   top cell supplies the bar in %d of %d draws : %s"
      % (int(vc.iloc[0]), len(mx), vc.index[0]))
print("   distinct cells that ever supply the bar: %d" % len(vc))
out["published_bar_mean"] = float(mx.mean())
out["published_bar_p95"] = float(np.percentile(mx, 95))
out["published_bar_json_mean"] = float(fw["null_maxt_correct"]["mean"])
out["published_bar_json_p95"] = float(fw["null_maxt_correct"]["p95"])
out["published_bar_top_cell"] = str(vc.index[0])
out["published_bar_top_cell_share"] = float(vc.iloc[0] / len(mx))
out["published_bar_n_distinct_suppliers"] = int(len(vc))
assert abs(mx.mean() - fw["null_maxt_correct"]["mean"]) < 1e-9

json.dump(out, open(os.path.join(HERE, "scripts", "_s00.json"), "w"), indent=2)
print("\nDONE s00 -- all anchors pass")
