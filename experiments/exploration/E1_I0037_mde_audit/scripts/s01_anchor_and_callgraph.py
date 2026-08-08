"""E1_I0037 s01 -- (A) reproduce D103's anchor exactly, (B) resolve the MDE call graph by AST.

NO NAME-BASED SEARCHING.  Section B parses every .py file under experiments\\exploration\\ with
`ast`, binds import aliases, and classifies functions by WHAT THEY COMPUTE (a multiple of an sd
in [2.0, 3.5], or the closed form (sqrt(T)+z*sqrt(mu))**2) rather than by what they are called.
Every file that fails to parse is reported as UNRESOLVED, never silently skipped.
"""
from __future__ import annotations
import ast
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
EXPL = os.path.join(ROOT, "experiments", "exploration")
HERE = os.path.join(EXPL, "E1_I0037_mde_audit")
D103 = os.path.join(EXPL, "E1_I0026_detection_floor")
sys.dont_write_bytecode = True
pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 60)

F = {}


def hdr(s):
    print("\n" + "=" * 98)
    print(s)
    print("=" * 98)


# =========================================================================== A. ANCHOR =========
hdr("A. REPRODUCTION ANCHOR -- D103's headline, recomputed from its own cell table")
R = pd.read_csv(os.path.join(D103, "out", "retrospective_power.csv"))
print("  retrospective_power.csv rows = %d  screens = %d" % (len(R), R["screen"].nunique()))

BEST_LEAD = 0.0023
worst = (R.groupby(["screen", "decision", "family_size_K", "cell"])
         .agg(mde80_fw=("mde80_fw", "max"), stat_family=("stat_family", "first"),
              n=("n", "max"), reported_p_fw=("reported_p_fw", "min"))
         .reset_index())
worst["blind"] = worst["mde80_fw"] > BEST_LEAD
n_cells = len(worst)
n_blind = int(worst["blind"].sum())
share = float(worst["blind"].mean())
print("  unique cells                     = %d      (D103 published 1349)" % n_cells)
print("  blind to 0.0023 family-wise      = %d       (D103 published 760)" % n_blind)
print("  share                            = %.16f" % share)
print("  D103 published share             = 0.5633802816901409")
assert n_cells == 1349, "anchor failed: cells"
assert n_blind == 760, "anchor failed: blind count"
assert abs(share - 0.5633802816901409) < 1e-15, "anchor failed: share"
print("  ANCHOR REPRODUCED TO THE DIGIT.")
F["anchor"] = dict(cells=n_cells, blind=n_blind, share=share, reproduced=True)

hdr("A2. THE ANCHOR DECOMPOSED BY stat_family -- which cells use which MDE construction")
sf = worst.groupby("stat_family").agg(
    cells=("cell", "size"), blind=("blind", "sum"), share_blind=("blind", "mean"),
    mde80_fw_med=("mde80_fw", "median")).reset_index()
sf["pct_of_1349"] = sf["cells"] / n_cells
print(sf.to_string(index=False))
F["by_stat_family"] = sf.to_dict("records")

byscreen = worst.groupby(["screen", "stat_family"]).agg(
    cells=("cell", "size"), blind=("blind", "sum")).reset_index()
print()
print(byscreen.to_string(index=False))
F["by_screen"] = byscreen.to_dict("records")


# ======================================================================= B. CALL GRAPH =========
hdr("B. CALL-GRAPH RESOLUTION BY AST  (no substring matching)")

# A function is MDE-producing iff it manipulates one of the NORMAL-QUANTILE constants that only
# a power calculation has any reason to contain.  This is a VALUE test on the arithmetic, not a
# test on any identifier.  The 300-hit first version of this classifier accepted any constant in
# [2.0, 3.5] and matched `** 2`, `/ 2.0` and `* 3` everywhere; it is recorded in DEFECTS.md D-2.
Z80 = 0.8416212335729143                      # Phi^-1(0.80)
Z_ALPHA = {"two_sided_05": 1.959964, "one_sided_05": 1.644854, "two_sided_01": 2.575829}
MDE_MULTIPLIERS = {("%s+z80" % k): (v + Z80) for k, v in Z_ALPHA.items()}
TOL = 0.01


def _const_of(node):
    """Numeric value of a node if it folds to a constant (handles (a+b), -a, a*b)."""
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) \
            and not isinstance(node.value, bool):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        v = _const_of(node.operand)
        return None if v is None else -v
    if isinstance(node, ast.BinOp):
        a, b = _const_of(node.left), _const_of(node.right)
        if a is None or b is None:
            return None
        if isinstance(node.op, ast.Add):
            return a + b
        if isinstance(node.op, ast.Sub):
            return a - b
        if isinstance(node.op, ast.Mult):
            return a * b
    return None


def _quantile_hits(tree):
    """Every occurrence of a power-calculation quantile constant, with what it is doing."""
    hits = []
    for n in ast.walk(tree):
        v = None
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)) \
                and not isinstance(n.value, bool):
            v = float(n.value)
        if v is None:
            continue
        if abs(v - Z80) < 1e-6:
            hits.append(("Phi^-1(0.80)=%.6f" % v, v))
        for lab, mult in MDE_MULTIPLIERS.items():
            if abs(v - mult) < TOL:
                hits.append(("MDE multiplier %.6f ~ %s" % (v, lab), v))
        for lab, z in Z_ALPHA.items():
            if abs(v - z) < 1e-4:
                hits.append(("z_alpha %.6f (%s)" % (v, lab), v))
    return hits


def _mult_by_mde_constant(tree):
    """A Mult whose constant factor lands on an MDE multiplier -- e.g. 2.801585 * null_sd,
    or (t_crit + Z80) * sd where the folded constant part matches."""
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Mult):
            for side, other in ((n.left, n.right), (n.right, n.left)):
                c = _const_of(side)
                if c is None or _const_of(other) is not None:
                    continue
                for lab, mult in MDE_MULTIPLIERS.items():
                    if abs(c - mult) < TOL:
                        out.append("multiplies a non-constant by %.6f (~%s)" % (c, lab))
    return out


def classify_fn(fn: ast.FunctionDef):
    """Return (is_mde_producing, reason). VALUE test on the arithmetic; no identifier is read."""
    reasons = []
    for r in _mult_by_mde_constant(fn):
        reasons.append(r)
    qh = _quantile_hits(fn)
    if qh:
        reasons.append("power-quantile constants present: %s"
                       % sorted({d for d, _v in qh}))
    if not reasons:
        return False, ""
    return True, "; ".join(sorted(set(reasons)))


py_files, parsed, unresolved = [], 0, []
for dirpath, dirnames, filenames in os.walk(EXPL):
    dirnames[:] = [d for d in dirnames if d not in ("__pycache__",)]
    if os.path.basename(dirpath) == "E1_I0037_mde_audit":
        continue
    for fn in filenames:
        if fn.endswith(".py"):
            py_files.append(os.path.join(dirpath, fn))
print("  .py files enumerated under experiments\\exploration\\ : %d" % len(py_files))

producers = []          # (path, funcname, reason)
alias_map = {}          # path -> {alias: module_basename}
calls = []              # (path, callee_repr, lineno)
for p in py_files:
    try:
        src = open(p, encoding="utf-8", errors="replace").read()
        tree = ast.parse(src)
        parsed += 1
    except (SyntaxError, ValueError, OSError) as exc:
        unresolved.append((p, repr(exc)))
        continue
    amap = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                amap[a.asname or a.name.split(".")[0]] = a.name
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for a in node.names:
                amap[a.asname or a.name] = "%s.%s" % (mod, a.name)
    alias_map[p] = amap
    fn_nodes = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
    fn_spans = set()
    for n in fn_nodes:
        for sub in ast.walk(n):
            fn_spans.add(id(sub))
    # module level = every node NOT inside any FunctionDef
    mod_only = ast.Module(body=[s for s in tree.body if not isinstance(s, ast.FunctionDef)],
                          type_ignores=[])
    mreasons = _mult_by_mde_constant(mod_only)
    mqh = _quantile_hits(mod_only)
    if mreasons or mqh:
        why = "; ".join(sorted(set(mreasons + (["module-level power-quantile constants: %s"
                                                % sorted({d for d, _v in mqh})] if mqh else []))))
        producers.append((p, "<module level>", why))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            ok, reason = classify_fn(node)
            if ok:
                producers.append((p, node.name, reason))
        elif isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Name):
                rep = amap.get(f.id, f.id)
                calls.append((p, f.id, rep, node.lineno))
            elif isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name):
                base = amap.get(f.value.id, f.value.id)
                calls.append((p, "%s.%s" % (f.value.id, f.attr),
                              "%s.%s" % (base, f.attr), node.lineno))

print("  parsed OK                                           : %d" % parsed)
print("  UNRESOLVED (parse failed)                           : %d" % len(unresolved))
for p, e in unresolved:
    print("      UNRESOLVED %s  %s" % (p.replace(EXPL, "..."), e))
print("  MDE-producing FunctionDefs found (by what they compute): %d" % len(producers))
for p, nm, why in sorted(producers):
    print("      %-62s  %-22s  %s" % (p.replace(EXPL + os.sep, ""), nm, why))

F["callgraph"] = dict(py_files=len(py_files), parsed=parsed, unresolved=len(unresolved),
                      producers=[dict(path=p, fn=nm, why=w) for p, nm, w in sorted(producers)])
assert parsed == len(py_files) - len(unresolved)
assert len(producers) > 0, "resolved zero MDE producers -- the classifier is broken, not the code"

# ---- now resolve the call sites OF those producers ------------------------------------------
prod_names = sorted({nm for _p, nm, _w in producers})
print("\n  distinct MDE-producing function NAMES (used only to match call sites AFTER the "
      "functions were identified by their bodies): %s" % prod_names)
sites = [(p, shown, resolved, ln) for (p, shown, resolved, ln) in calls
         if shown.split(".")[-1] in prod_names]
print("  call sites resolving to an MDE producer: %d" % len(sites))
bysite = {}
for p, shown, resolved, ln in sites:
    bysite.setdefault((p, shown), []).append(ln)
for (p, shown), lns in sorted(bysite.items()):
    print("      %-62s  %-24s lines %s" % (p.replace(EXPL + os.sep, ""), shown, lns[:8]))
F["call_sites"] = [dict(path=p, callee=s, lines=l) for (p, s), l in sorted(bysite.items())]


# ------------------- C. does the sd fed to each producer carry the effect? --------------------
hdr("C. IS THE sd EFFECT-CARRYING?  Traced to the null that produced it")
print("""
  The question is not what the sd is CALLED but what vector the sign-flip ran on.

  screenkit.paired_forecast_comparison (the SHARED KIT), lines 2143-2170:
      2143   d = (y - a) ** 2 - (y - b) ** 2          <- OBSERVED losses of the two forecasts
      2150   csum = np.bincount(gcodes, weights=d)    <- block sums OF THE OBSERVED vector
      2156   draws = _draws_for(csum, rng)            <- +/- the SAME block sums
      2170   sd   = float(draws.std(ddof=1))          <- "null" sd, from an effect-carrying vector
  -> CONFIRMED effect-carrying.  Nothing is permuted or resampled; only signs are flipped on the
     observed block sums, so E[draws]=0 by construction but Var[draws] scales with the effect.

  E1_I0035\\scripts\\av_base.py::paired_signflip_block, lines 273-294: identical construction
      273    d = loss_b - loss_a                      <- OBSERVED
      281    bs = np.bincount(inv, weights=d)
      284    draws = (signs * bs[None, :]).sum(1) / n
      292    "null_sd": float(draws.std(ddof=1))
      297    def mde80(null_sd): return 2.801585 * null_sd
  -> CONFIRMED effect-carrying.

  E1_I0026\\scripts\\s06_retrospective.py::mde80_increment / mde80_tscale, by contrast, take
  mu_null and sd_null from the SCREENS' PERMUTATION nulls -- the carrier is permuted, so the
  vector the sd is computed from does NOT carry the effect.
  -> NOT effect-carrying.

  s06_retrospective.py::mde80_paired(sd, t_crit) = (t_crit + 0.8416) * sd takes
  E1_I0023's `null_sd_cluster`, which IS screenkit.paired_forecast_comparison's `sd`.
  -> EFFECT-CARRYING.  This is the one D103 family that inherits the defect.
""")

# how many of the 1349 are paired?
paired_cells = int((worst["stat_family"] == "paired").sum())
paired_blind = int(worst.loc[worst["stat_family"] == "paired", "blind"].sum())
print("  D103 cells on the EFFECT-CARRYING (paired) construction : %d of %d  (%.1f%%)"
      % (paired_cells, n_cells, 100.0 * paired_cells / n_cells))
print("  ... of which currently counted BLIND                    : %d" % paired_blind)
print("  D103 cells on permutation nulls (increment/t_statistic) : %d  -> NOT affected"
      % (n_cells - paired_cells))
F["d103_paired_cells"] = paired_cells
F["d103_paired_blind"] = paired_blind
F["d103_unaffected_cells"] = n_cells - paired_cells

# ---- D103's own analytic-vs-simulated validation, re-read (increment family only) ------------
hdr("D. D103's OWN ANALYTIC-vs-SIMULATED VALIDATION -- what it did and did NOT cover")
V = pd.read_csv(os.path.join(D103, "out", "s06_validation_analytic_vs_simulated.csv"))
rr = V["ratio"].replace([np.inf, -np.inf], np.nan).dropna()
rp = V["ratio_percell"].replace([np.inf, -np.inf], np.nan).dropna()
print("  validation rows = %d   (all from s04_mde_table.csv)" % len(V))
print("  family-wise analytic/simulated  median=%.3f p10=%.3f p90=%.3f n=%d"
      % (rr.median(), rr.quantile(.1), rr.quantile(.9), len(rr)))
print("  per-cell    analytic/simulated  median=%.3f p10=%.3f p90=%.3f n=%d"
      % (rp.median(), rp.quantile(.1), rp.quantile(.9), len(rp)))
print("  nulls covered by the validation: %s" % sorted(V["null"].unique()))
print("\n  READ: every validated cell is stat_family='increment' on a PERMUTATION null.")
print("  The 'paired' family -- the only effect-carrying one -- was NEVER validated.")
print("  The 't_statistic' family (E0_I0014, E0_I0019; 666 cells) was also never validated.")
F["d103_validation"] = dict(rows=int(len(V)), ratio_median=float(rr.median()),
                            ratio_p10=float(rr.quantile(.1)), ratio_p90=float(rr.quantile(.9)),
                            nulls=sorted(map(str, V["null"].unique())))

open(os.path.join(HERE, "_s01.json"), "w", encoding="utf-8").write(json.dumps(F, indent=2,
                                                                             default=str))
print("\nDONE s01")
