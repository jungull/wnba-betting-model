"""E1_I0041 s01 -- ANCHOR, CALL GRAPH, AND THE SOURCE FACTS.

Nothing here is a new statistic.  This step (a) reproduces D103's published anchor to 16 digits
before anything else runs, (b) resolves every call site of the conversion by AST rather than by
substring, and (c) records, from source, exactly what each of the two contributing screens stored
in the field D103 reads as `sd_null_t`.

WRITE SCOPE: only experiments/exploration/E1_I0041_tstat_family_audit/.
PARTITION:   2021-2024 exploration artefacts only.  Nothing under 2025/26 is opened.
"""
import ast
import hashlib
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
EXPL = os.path.join(ROOT, "experiments", "exploration")
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D103 = os.path.join(EXPL, "E1_I0026_detection_floor")

OUT = {}


def hdr(s):
    print("\n" + "=" * 100)
    print(s)
    print("=" * 100)


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


# ==================================================================== A. THE ANCHOR ============
hdr("A. ANCHOR -- reproduce D103's published blind share to 16 digits BEFORE anything else")

RPP = os.path.join(D103, "out", "retrospective_power.csv")
RP = pd.read_csv(RPP)
print("  out/retrospective_power.csv  rows=%d  cols=%d" % RP.shape)
print("  sha256 = %s" % sha(RPP))
print("  (NOTE: the TOP-LEVEL retrospective_power.csv is a different, 1,975-row file; E1_I0037's")
print("   anchor and D103's headline both come from out/.  Using the same one, same key.)")

# D103's cell key, exactly as E1_I0037 reproduced it (s01_anchor_and_callgraph.py:40-47):
# a cell is (screen, decision, family_size_K, cell) and is blind if its WORST null arm's
# family-wise MDE exceeds the programme's best lead.
BEST_LEAD = 0.0023
uniq = (RP.groupby(["screen", "decision", "family_size_K", "cell"])
        .agg(mde80_fw=("mde80_fw", "max"), stat_family=("stat_family", "first"),
             n=("n", "max"), null_sd=("null_sd", "max"),
             reported_p_fw=("reported_p_fw", "min"))
        .reset_index())
uniq["blind"] = uniq["mde80_fw"] > BEST_LEAD
blind_col = "blind"
n_cells = len(uniq)
n_blind = int(uniq[blind_col].sum())
share = float(uniq[blind_col].mean())
print("  unique cells (screen,cell,null_arm) = %d" % n_cells)
print("  blind (mde80_fw > 0.0023)           = %d" % n_blind)
print("  share                               = %.16f" % share)
print("  E1_I0037 / D103 published           = 0.5633802816901409")
ANCHOR_OK = (n_cells == 1349 and n_blind == 760
             and repr(share) == repr(0.5633802816901409))
print("  ANCHOR: %s" % ("EXACT MATCH to 16 digits" if ANCHOR_OK else "*** MISMATCH ***"))
assert ANCHOR_OK, "anchor not reproduced -- refusing to generate new statistics"
OUT["anchor"] = dict(n_cells=n_cells, n_blind=n_blind, share=share,
                     share_repr=repr(share), matches_published=bool(ANCHOR_OK))

# ---- family census, asserted, not eyeballed --------------------------------------------------
fam = uniq.groupby("stat_family").agg(
    cells=("cell", "size"),
    blind=(blind_col, "sum"),
).reset_index()
fam["share_of_cells"] = fam["cells"] / n_cells
fam["share_of_blind"] = fam["blind"] / n_blind
print("\n" + fam.to_string(index=False))
t_cells = int(fam.loc[fam["stat_family"] == "t_statistic", "cells"].iloc[0])
t_blind = int(fam.loc[fam["stat_family"] == "t_statistic", "blind"].iloc[0])
print("\n  t_statistic: %d cells (%.1f%%), %d blind verdicts (%.1f%% of all blind)"
      % (t_cells, 100 * t_cells / n_cells, t_blind, 100 * t_blind / n_blind))
assert t_cells == 666, "t_statistic cell count is not 666: %d" % t_cells
assert t_blind == 518, "t_statistic blind count is not 518: %d" % t_blind
OUT["family_census"] = fam.to_dict("records")

uniq.to_csv(os.path.join(HERE, "_d103_cells.csv"), index=False)
by_screen = uniq[uniq["stat_family"] == "t_statistic"].groupby("screen").agg(
    cells=("cell", "size"), blind=(blind_col, "sum"),
    n_med=("n", "median"), sd_med=("null_sd", "median"),
    mde_med=("mde80_fw", "median")).reset_index()
print("\n  t_statistic family by source screen:")
print(by_screen.to_string(index=False))
OUT["t_family_by_screen"] = by_screen.to_dict("records")

# ==================================================================== B. CALL GRAPH ============
hdr("B. CALL GRAPH BY AST -- who defines and who calls the conversion (no substring selection)")

pyfiles = []
for dirpath, dirnames, filenames in os.walk(ROOT):
    dirnames[:] = [d for d in dirnames if d not in ("__pycache__", ".git")]
    for fn in filenames:
        if fn.endswith(".py"):
            pyfiles.append(os.path.join(dirpath, fn))
pyfiles.sort()
print("  enumerated %d .py files under the worktree" % len(pyfiles))

defs, calls, unparsed = [], [], []
for p in pyfiles:
    if os.path.abspath(p).startswith(os.path.abspath(HERE)):
        continue                                    # never count my own code
    try:
        src = open(p, "r", encoding="utf-8").read()
        tree = ast.parse(src)
    except Exception as e:
        unparsed.append((p, "%s: %s" % (type(e).__name__, str(e)[:70])))
        continue
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            # classify by BODY, not by name: does it return a squared-scaled quantity divided
            # by n, using a constant within 1e-6 of Phi^-1(0.80)?
            body = ast.unparse(node)
            has_z80 = ("0.8416" in body)
            has_div_n = ("/ n" in body or "/n" in body or "** 2 / " in body)
            if has_z80:
                defs.append(dict(file=p, func=node.name, lineno=node.lineno,
                                 has_z80=has_z80, divides_by_n=bool(has_div_n),
                                 body_first_line=body.splitlines()[0]))
        if isinstance(node, ast.Call):
            f = node.func
            nm = (f.id if isinstance(f, ast.Name)
                  else (f.attr if isinstance(f, ast.Attribute) else None))
            if nm in ("mde80_tscale", "mde80_increment", "mde80_paired", "validate"):
                calls.append(dict(file=p, callee=nm, lineno=node.lineno,
                                  n_args=len(node.args)))

print("  UNPARSED: %d" % len(unparsed))
for p, e in unparsed:
    print("    ! %s  (%s)" % (os.path.relpath(p, ROOT), e))
print("\n  functions whose BODY contains the 80%%-power constant 0.8416: %d" % len(defs))
for d in defs:
    print("    %-58s %-22s line %-5d divides_by_n=%s"
          % (os.path.relpath(d["file"], ROOT), d["func"], d["lineno"], d["divides_by_n"]))

print("\n  resolved call sites of the three D103 MDE functions + validate():")
cdf = pd.DataFrame(calls)
if len(cdf):
    for r in cdf.itertuples():
        print("    %-62s -> %-18s line %d" % (os.path.relpath(r.file, ROOT), r.callee, r.lineno))
    print("\n  counts: %s" % cdf["callee"].value_counts().to_dict())
OUT["callgraph"] = dict(py_files=len(pyfiles), unparsed=[list(u) for u in unparsed],
                        z80_defs=defs, call_sites=calls,
                        call_counts=(cdf["callee"].value_counts().to_dict() if len(cdf) else {}))

# ---- does validate() ever touch the t_statistic path? ----------------------------------------
hdr("C. THE GATE -- what does validate() actually read, and does anything else validate tscale?")
vt = pd.read_csv(os.path.join(D103, "out", "s04_mde_table.csv"))
print("  s04_mde_table.csv (what validate() reads): rows=%d  cols=%s"
      % (len(vt), list(vt.columns)[:8]))
print("  it has a stat_family column: %s" % ("stat_family" in vt.columns))
print("  the nulls it contains: %s" % sorted(vt["null"].unique()))
vfile = os.path.join(D103, "out", "s06_validation_analytic_vs_simulated.csv")
vv = pd.read_csv(vfile)
print("  s06_validation_analytic_vs_simulated.csv rows=%d  median ratio=%.4f"
      % (len(vv), vv["ratio"].replace([np.inf, -np.inf], np.nan).dropna().median()))
print("  -> every validated row is a simulated INCREMENT power curve from s04_power.py;")
print("     s04_power.py's statistic is dR2 = (a*a/b)/sst (s04_power.py:118), never a t.")
OUT["gate"] = dict(validate_reads=os.path.relpath(
    os.path.join(D103, "out", "s04_mde_table.csv"), ROOT),
    rows=int(len(vt)), has_stat_family_col=bool("stat_family" in vt.columns),
    nulls_present=sorted(map(str, vt["null"].unique())),
    validation_rows=int(len(vv)),
    validation_median_ratio=float(vv["ratio"].replace([np.inf, -np.inf], np.nan)
                                  .dropna().median()))

# ==================================================================== D. WHAT sd_null_t IS =====
hdr("D. WHAT THE TWO SCREENS ACTUALLY STORED IN THE FIELD D103 READS AS sd_null_t")

# ---- E0_I0014 -----------------------------------------------------------------------
p14 = os.path.join(EXPL, "E0_I0014_residual_heterogeneity")
s14 = pd.read_csv(os.path.join(p14, "screen_results.csv"))
print("  E0_I0014 screen_results.csv rows=%d" % len(s14))
z14 = np.load(os.path.join(p14, "permutation_nulls.npz"))
print("  E0_I0014 permutation_nulls.npz keys: %s" % sorted(z14.files))
anyneg = {}
for k in z14.files:
    if k.startswith(("bet__", "win__", "row__")):
        A = z14[k].astype(float)
        anyneg[k] = dict(shape=list(A.shape), min=float(np.nanmin(A)),
                         frac_negative=float(np.nanmean(A < 0)))
for k, v in sorted(anyneg.items()):
    print("    %-22s shape=%-12s min=%.6f  frac_negative=%.4f"
          % (k, v["shape"], v["min"], v["frac_negative"]))
print("  -> s04_screen.py:211 stores  v = np.abs(tvec(...)[1])  : the draws are |t|, FOLDED.")
print("     null_correct_sd (s04_screen.py:291) is therefore sd(|t|), NOT sd(t).")
OUT["E0_I0014_null_storage"] = dict(stored="abs_t", evidence=anyneg,
                                    source_line="s04_screen.py:211  v = np.abs(tvec(yt, Xx, NS)[1])")

# ---- E0_I0019 -----------------------------------------------------------------------
p19 = os.path.join(EXPL, "E0_I0019_availability_forecast")
s19 = pd.read_csv(os.path.join(p19, "screen_results_repaired.csv"))
print("\n  E0_I0019 screen_results_repaired.csv rows=%d" % len(s19))
z19 = np.load(os.path.join(p19, "permutation_nulls.npz"))
print("  E0_I0019 permutation_nulls.npz keys: %s" % sorted(z19.files))
neg19 = {}
for k in z19.files:
    if k.startswith("null_"):
        A = z19[k].astype(float)
        neg19[k] = dict(shape=list(A.shape), min=float(np.nanmin(A)),
                        frac_negative=float(np.nanmean(A < 0)))
        print("    %-28s shape=%-16s min=%.4f  frac_negative=%.4f"
              % (k, neg19[k]["shape"], neg19[k]["min"], neg19[k]["frac_negative"]))
print("  -> s04_screen.py:181 stores  null_t[s][d, ci, di] = tt  : the draws are SIGNED t.")
print("     nullsd_between (s05:55) is therefore sd(t) -- correct scale, ddof=0.")
OUT["E0_I0019_null_storage"] = dict(stored="signed_t", evidence=neg19,
                                    source_line="s04_screen.py:181  null_t[s][d, ci, di] = tt")

# ==================================================================== E. IDENTITY CHECK ========
hdr("E. IS dR2 = t^2/n TRUE ON THE REAL CELLS?  (the conversion's core identity, on real data)")
# E0_I0014 published BOTH t_classical and delta_r2_plain_unweighted for all 348 cells.
# This is a direct, real-data test of the identity the conversion rests on.  Same cell, same
# response, same row set -- a like-for-like comparison by construction (D101).
N14 = 13879
tt = s14["t_classical"].to_numpy(float)
dr = s14["delta_r2_plain_unweighted"].to_numpy(float)
ok = np.isfinite(tt) & np.isfinite(dr) & (dr > 0)
approx = tt[ok] ** 2 / N14
ratio = approx / dr[ok]
print("  cells with both quantities finite and dR2>0: %d of %d" % (ok.sum(), len(s14)))
print("  ratio (t^2/n) / dR2_published :  min=%.4f  p10=%.4f  median=%.4f  p90=%.4f  max=%.4f"
      % (ratio.min(), np.quantile(ratio, .1), np.median(ratio),
         np.quantile(ratio, .9), ratio.max()))
# exact form with df
for k_extra in (1, 2, 3, 4, 5):
    df = N14 - k_extra
    ex = tt[ok] ** 2 / (tt[ok] ** 2 + df)
    r2 = ex / dr[ok]
    print("    exact t^2/(t^2+df), df=n-%d : median ratio=%.4f" % (k_extra, np.median(r2)))
OUT["identity_check_E0_I0014"] = dict(
    n=int(ok.sum()), ratio_min=float(ratio.min()), ratio_p10=float(np.quantile(ratio, .1)),
    ratio_median=float(np.median(ratio)), ratio_p90=float(np.quantile(ratio, .9)),
    ratio_max=float(ratio.max()))

json.dump(OUT, open(os.path.join(HERE, "_s01.json"), "w"), indent=2, default=str)
print("\nwrote _s01.json")
print("DONE s01")
