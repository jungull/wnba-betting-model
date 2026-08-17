"""E1_I0047 s06 -- INDEPENDENT VERIFICATION OF E1_I0043's D-01, AND A SEARCH FOR THE PATTERN.

PREREG section 8.  E1_I0023/NOTES.md item 7 discloses the ceiling statistic's noise floor as
"up to 3.98e-04".  E1_I0043 D-01 says the true maximum in that screen's own artifact is
4.375669e-03 and the understatement is 11x.  Verified here under THREE scopes, because the
sentence's literal scope is narrower than the use it is put to, and the factor differs by scope.

Then: every recorded table in the programme that carries BOTH a negative-control flag and a
ceiling column is scanned for the same pattern -- a single quoted floor standing in for a
distribution.  Discovery is by COLUMN PRESENCE, never by candidate name.
"""
import json
import os
import re
import sys

import numpy as np
import pandas as pd

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import cv_base as cb  # noqa: E402

LOG = []


def P(s=""):
    print(s)
    LOG.append(str(s))


def hdr(s):
    P("\n" + "=" * 100 + "\n" + s + "\n" + "=" * 100)


hdr("E1_I0047 s06 -- THE CEILING NOISE FLOOR")

ac = pd.read_csv(os.path.join(cb.D098, "arithmetic_ceiling.csv"))
nc = ac[ac["is_negative_control"] == True].copy()  # noqa: E712
P("  E1_I0023/arithmetic_ceiling.csv : %d rows, %d flagged is_negative_control"
  % (len(ac), len(nc)))
P("  DISCLOSED SENTENCE (E1_I0023/NOTES.md item 7, quoted verbatim):")
P('    "The pure-noise interaction control returns a walk-forward ceiling of up to 3.98e-04')
P('     purely from estimation noise in its own coefficient. Ceilings below roughly 4e-04 here')
P('     are not distinguishable from that floor."')

DISCLOSED = 3.98e-04
scopes = [
    ("1 LITERAL   (interaction + walk-forward)", (nc["contrast"] == "INTERACTION")
     & (nc["fit"] == "walk_forward")),
    ("2 WALK-FWD  (both contrasts, walk-forward)", nc["fit"] == "walk_forward"),
    ("3 WHOLE TABLE (every negative-control row)", pd.Series(True, index=nc.index)),
]
res = []
P("\n  %-44s %2s %13s %13s %8s %8s" % ("scope", "n", "max 1sd form", "max D084 form",
                                       "x disc", "x disc"))
for lbl, m in scopes:
    g = nc[m]
    m1, m2 = float(g["ceiling_1sd_form"].max()), float(g["ceiling_D084_form_var_share"].max())
    P("  %-44s %2d %13.6e %13.6e %8.2f %8.2f"
      % (lbl, len(g), m1, m2, m1 / DISCLOSED, m2 / DISCLOSED))
    am = g.loc[g["ceiling_1sd_form"].idxmax()]
    P("      argmax(1sd): %s / %s / %s / %s" % (am["stratum"], am["tier"], am["contrast"],
                                                am["fit"]))
    res.append(dict(scope=lbl, n=int(len(g)), max_ceiling_1sd=m1, max_ceiling_D084=m2,
                    disclosed=DISCLOSED, understatement_1sd=m1 / DISCLOSED,
                    understatement_D084=m2 / DISCLOSED,
                    argmax_stratum=am["stratum"], argmax_tier=am["tier"],
                    argmax_contrast=am["contrast"], argmax_fit=am["fit"]))

P("\n  VERDICT ON D-01: E1_I0043's 11x is CONFIRMED under the scope the sentence is USED in")
P("  (whole table -- the sentence's second clause, 'ceilings below roughly 4e-04 HERE', is a")
P("  claim about every ceiling in the screen, not only the interaction ones).")
P("  Under the sentence's LITERAL first clause the understatement is %.2fx, not 11x."
  % res[0]["understatement_1sd"])
P("  BOTH are reported. The finding survives; its size depends on how the sentence is read,")
P("  and E1_I0043 quoted one number where two are needed. Recorded in this screen's DEFECTS.md.")

# the cell D098 headlined, and its matched noise floor
hl = ac[(ac.defence == "A10_opp_defrtg") & (ac.stratum == "DECISION")
        & (ac.tier == "T3_high_usage") & (ac.contrast == "MAIN_EFFECT")
        & (ac.fit == "walk_forward")].iloc[0]
mn = nc[(nc.stratum == "DECISION") & (nc.tier == "T3_high_usage")
        & (nc.contrast == "MAIN_EFFECT") & (nc.fit == "walk_forward")].iloc[0]
hdr("2. THE MATCHED NOISE FLOOR FOR D098's HEADLINE CELL")
P("  cell: A10_opp_defrtg / DECISION / T3_high_usage / MAIN_EFFECT / walk_forward, n=%d"
  % hl["n"])
P("    ceiling (D084 form)                       %.8f" % hl["ceiling_D084_form_var_share"])
P("    matched pure-noise control, SAME cell     %.8f" % mn["ceiling_D084_form_var_share"])
P("    ratio                                     %.3fx"
  % (hl["ceiling_D084_form_var_share"] / mn["ceiling_D084_form_var_share"]))
P("    ratio implied by the disclosed floor      %.2fx"
  % (hl["ceiling_D084_form_var_share"] / DISCLOSED))
P("  E1_I0043 reported 3.08x against 4.163e-03; reproduced here as %.3fx against %.6e."
  % (hl["ceiling_D084_form_var_share"] / mn["ceiling_D084_form_var_share"],
     mn["ceiling_D084_form_var_share"]))
P("  AND, separately established in s02: that same cell's REALISED statistic (%.8f) EXCEEDS"
  % hl["realised_paired_dr2_points"])
P("  its own published ceiling (%.8f) by %.0f%%. The ceiling was wrong in BOTH directions at"
  % (hl["ceiling_D084_form_var_share"],
     100 * (hl["realised_paired_dr2_points"] / hl["ceiling_D084_form_var_share"] - 1)))
P("  once: too small to be a bound, and quoted against a floor 11x too low.")

# =========================================================================================
hdr("3. DOES THE PATTERN APPEAR ELSEWHERE?  (discovery by COLUMN PRESENCE, not by name)")
# =========================================================================================
P("  Rule: walk every .csv under experiments/exploration; keep any table with BOTH a column")
P("  whose name contains 'ceiling' AND a column whose name contains 'negative_control'.")
found = []
root = cb.EXP
for dp, _dn, fn in os.walk(root):
    if os.path.basename(dp) == os.path.basename(cb.OUT):
        continue
    for f in fn:
        if not f.endswith(".csv"):
            continue
        p = os.path.join(dp, f)
        try:
            head = pd.read_csv(p, nrows=0)
        except Exception:
            continue
        cols = [c.lower() for c in head.columns]
        ceil_cols = [c for c in head.columns if "ceiling" in c.lower()]
        nc_cols = [c for c in head.columns if "negative_control" in c.lower()]
        if ceil_cols and nc_cols:
            found.append((p, ceil_cols, nc_cols))
P("  tables found: %d" % len(found))
pattern = []
for p, ceil_cols, nc_cols in found:
    d = pd.read_csv(p)
    flag = d[nc_cols[0]]
    flag = flag.astype(str).str.lower().isin(["true", "1"])
    rel = os.path.relpath(p, root).replace("\\", "/")
    P("\n  %s" % rel)
    P("    ceiling columns: %s   control flag: %s   rows %d (controls %d)"
      % (", ".join(ceil_cols), nc_cols[0], len(d), int(flag.sum())))
    if flag.sum() == 0:
        P("    no control rows -- nothing to check")
        continue
    for cc in ceil_cols:
        v = pd.to_numeric(d.loc[flag, cc], errors="coerce").dropna()
        if not len(v):
            continue
        spread = float(v.max() / v.median()) if v.median() > 0 else np.nan
        P("    %-34s controls: min %.4e  median %.4e  MAX %.4e   max/median %.1fx"
          % (cc, v.min(), v.median(), v.max(), spread))
        pattern.append(dict(table=rel, ceiling_col=cc, n_controls=int(len(v)),
                            ctrl_min=float(v.min()), ctrl_median=float(v.median()),
                            ctrl_max=float(v.max()), max_over_median=spread))

pat = pd.DataFrame(pattern)
P("\n  SPREAD OF THE NOISE FLOOR WITHIN A SINGLE SCREEN'S OWN CONTROL ROWS:")
P("    max/median ratio: min %.1fx  median %.1fx  max %.1fx over %d (table, column) pairs"
  % (pat["max_over_median"].min(), pat["max_over_median"].median(),
     pat["max_over_median"].max(), len(pat)))
P("    pairs where the max exceeds the median by >= 5x : %d of %d"
  % (int((pat["max_over_median"] >= 5).sum()), len(pat)))
P("\n  THE GENERAL FINDING, which is larger than D-01: the ceiling statistic's noise floor is")
P("  NOT ONE NUMBER. It varies by stratum, tier, contrast and fit within a single screen by")
P("  up to %.0fx. Any screen that quotes 'the noise floor' as a scalar is quoting a summary of"
  % pat["max_over_median"].max())
P("  a distribution and will understate it somewhere. The correct disclosure is per stratum,")
P("  and the correct comparison for a given cell is the control row MATCHED to that cell.")

# does any screen's prose quote a single scalar noise floor?
hdr("4. WHICH SCREENS QUOTE A SCALAR NOISE FLOOR IN PROSE?")
P("  Grep of NOTES.md / VERDICT.md / CEILING.md for a sentence containing both a ceiling word")
P("  and 'noise floor'. Text search over this programme's own prose, not candidate selection.")
hits = []
for dp, _dn, fn in os.walk(root):
    for f in fn:
        if not f.endswith(".md"):
            continue
        p = os.path.join(dp, f)
        try:
            txt = open(p, encoding="utf-8").read()
        except Exception:
            continue
        for m in re.finditer(r"[^\n]*noise floor[^\n]*", txt, re.I):
            line = m.group(0).strip()
            if "ceiling" in line.lower() or "ceiling" in txt[max(0, m.start() - 300):m.start()].lower():
                rel = os.path.relpath(p, root).replace("\\", "/")
                nums = re.findall(r"\d\.\d+e-\d+|\d\.\d{3,}", line)
                hits.append(dict(file=rel, line=line[:170], numbers=";".join(nums)))
seen = set()
for h in hits:
    kk = (h["file"], h["line"][:60])
    if kk in seen:
        continue
    seen.add(kk)
    P("    %-58s %s" % (h["file"], h["line"][:110]))
P("  %d distinct prose lines" % len(seen))

pat.to_csv(os.path.join(cb.OUT, "NOISE_FLOOR_TABLES.csv"), index=False)
with open(os.path.join(HERE, "_s06.json"), "w", encoding="utf-8") as fh:
    json.dump(dict(scopes=res, tables=pattern, prose_hits=hits[:40],
                   headline_ceiling=float(hl["ceiling_D084_form_var_share"]),
                   headline_realised=float(hl["realised_paired_dr2_points"]),
                   matched_noise_floor=float(mn["ceiling_D084_form_var_share"]),
                   ratio_matched=float(hl["ceiling_D084_form_var_share"]
                                       / mn["ceiling_D084_form_var_share"])),
              fh, indent=2, default=float)
with open(os.path.join(HERE, "run_log_s06.txt"), "w", encoding="utf-8") as fh:
    fh.write("\n".join(LOG))
P("\n  wrote NOISE_FLOOR_TABLES.csv, _s06.json, run_log_s06.txt")
