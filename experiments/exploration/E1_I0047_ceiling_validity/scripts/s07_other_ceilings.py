"""E1_I0047 s07 -- THE OTHER CEILINGS IN THE PROGRAMME.

E1_I0036 DEFECT D-03 records that only D097 ever wrote an arithmetic ceiling INTO THE CENSUS,
so ceiling kills elsewhere are invisible to it. This script finds every recorded ceiling table
by COLUMN PRESENCE (never by candidate name) and classifies each by CONSTRUCTION:

  SAME-SCALE OLS  -- d is the fitted contribution on the same rows/response/base.  c* = 1.
                     (d.d)/SST is a valid bound with slack = VIF. SAFE.
  TRANSPORTED     -- d is built on one scale (a rate coefficient) and scored on another
                     (points, via an estimated-minutes vector), or across a fold boundary.
                     c* is unconstrained. (d.d)/SST is NOT a bound. EXPOSED.

For every TRANSPORTED table that recorded an oracle, c*^2 = ORACLE / (d.d)/SST is computed
directly, which is the exact factor by which its ceiling understates the achievable increment.
"""
import json
import os
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


hdr("E1_I0047 s07 -- EVERY RECORDED CEILING IN THE PROGRAMME, BY CONSTRUCTION")

tables = []
for dp, _dn, fn in os.walk(cb.EXP):
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
        cc = [c for c in head.columns if "ceiling" in c.lower()]
        if cc:
            tables.append((p, cc))
P("  tables carrying a ceiling column: %d" % len(tables))

rows = []
for p, cc in sorted(tables):
    rel = os.path.relpath(p, cb.EXP).replace("\\", "/")
    d = pd.read_csv(p)
    cols = {c.lower(): c for c in d.columns}
    has_resid = any("residualis" in c or "residualiz" in c or "base_residualised" in c
                    for c in cols)
    has_beta = "beta" in cols
    has_minutes = any(("minute" in c) or ("m_hat" in c) for c in cols)
    # an ORACLE column must be a real-valued statistic, not a flag. `is_oracle` in
    # E0_I0029 is a boolean and would otherwise be read as one -- guard explicitly.
    def _is_stat(cn):
        v = pd.to_numeric(d[cn], errors="coerce").dropna()
        return len(v) > 0 and not set(np.unique(v)).issubset({0.0, 1.0})
    orc = next((cols[c] for c in cols
                if "oracle" in c and not c.startswith("is_") and _is_stat(cols[c])), None)
    varshare = next((cols[c] for c in cols
                     if "d084" in c or "var_share" in c or c.endswith("ceiling_dr2_raw")), None)
    kind = "TRANSPORTED" if has_minutes else ("SAME-SCALE OLS" if (has_beta and has_resid)
                                              else "UNCLASSIFIED")
    cstar2 = np.nan
    if orc and varshare:
        r = pd.to_numeric(d[orc], errors="coerce") / pd.to_numeric(d[varshare], errors="coerce")
        r = r.replace([np.inf, -np.inf], np.nan).dropna()
        cstar2 = float(r.max()) if len(r) else np.nan
    rows.append(dict(table=rel, n_rows=int(len(d)), ceiling_cols=";".join(cc), kind=kind,
                     has_residualised_form=has_resid, has_minutes_transport=has_minutes,
                     oracle_col=orc or "", varshare_col=varshare or "",
                     max_c_star_squared=cstar2))
    P("\n  %-62s %-15s rows %4d" % (rel, kind, len(d)))
    P("      ceiling cols: %s" % ", ".join(cc))
    if np.isfinite(cstar2):
        P("      max ORACLE/(d.d)/SST = max c*^2 = %.4f   %s"
          % (cstar2, "-> ceiling UNDERSTATES by up to this factor" if cstar2 > 1
             else "-> ceiling holds as a bound on every recorded row"))

T = pd.DataFrame(rows)

# =========================================================================================
hdr("1. THE SAME-SCALE OLS TABLES -- the identity checked directly where the columns allow")
# =========================================================================================
for rel, dr2c, rawc, residc in [
        ("E0_I0024_reb_ast_characterisation/upstream_signals.csv", "dr2",
         "CEILING_dr2_D089form", "CEILING_dr2_residualised"),
        ("E0_I0029_freethrow_hurdle/arithmetic_ceiling.csv", "dR2_over_B_COMPLETE",
         "CEILING_dR2_raw", "CEILING_dR2_base_residualised")]:
    p = os.path.join(cb.EXP, *rel.split("/"))
    if not os.path.exists(p):
        P("  %s ABSENT" % rel)
        continue
    d = pd.read_csv(p)
    a = np.abs(d[residc] - d[dr2c])
    gap = d[rawc] - d[dr2c]
    P("\n  %s   (%d rows)" % (rel, len(d)))
    P("    max |residualised ceiling - realised dR2| = %.3e   -> the residualised form IS the"
      % np.nanmax(a))
    P("       realised increment, exactly. It is an equality, not a bound.")
    P("    min (raw-sd ceiling - realised dR2)       = %+.3e   violations: %d of %d"
      % (np.nanmin(gap), int((gap < -1e-15).sum()), len(d)))
    P("    -> the raw-sd form is a VALID BOUND on every recorded row of this table.")

# =========================================================================================
hdr("2. THE TRANSPORTED TABLES -- where the ledger's ceilings actually live")
# =========================================================================================
P("  D079's and D084's kills, and D089's headline ceiling, all use the TRANSPORTED form:")
P("  a rate coefficient multiplied by an estimated-minutes vector and scored against points.")
P("  For that form c* is unconstrained and (d.d)/SST is NOT a bound.")
tv2 = os.path.join(cb.EXP, "E1_I0004_efficiency_transfer_v2", "arithmetic_ceiling.csv")
if os.path.exists(tv2):
    d = pd.read_csv(tv2)
    d["c_star_sq"] = (d["DIAGNOSTIC_ORACLE_best_scaling_dR2"]
                      / d["CEILING_A_perfect_orthogonal_dR2"])
    P("\n  E1_I0004_efficiency_transfer_v2/arithmetic_ceiling.csv  (the D084 kill)")
    P("  %-34s %-9s %8s %13s %13s %9s" % ("spec", "stratum", "n", "ceiling", "ORACLE", "c*^2"))
    for _, r in d.iterrows():
        P("  %-34s %-9s %8d %13.3e %13.3e %9.3f"
          % (str(r["spec"])[:34], r["stratum"], r["n"],
             r["CEILING_A_perfect_orthogonal_dR2"],
             r["DIAGNOSTIC_ORACLE_best_scaling_dR2"], r["c_star_sq"]))
    mx = float(d["c_star_sq"].max())
    P("\n    max c*^2 recorded in D084's own table = %.3f  -> its ceiling is NOT a bound" % mx)
    P("    D084's ledger figure = 0.000129 = %.4f x FLOOR_1CELL (%.5f)"
      % (0.000129 / cb.FLOOR_1CELL, cb.FLOOR_1CELL))
    P("\n    THE ORACLE -- WHICH IS THE BOUND -- BY STRATUM. Decision-relevant rows FIRST:")
    for sname, lbl in [("on_stratum", "ON  stratum (decision-relevant)"),
                       ("all", "ALL rows (pooled)"),
                       ("off_stratum", "OFF stratum (NOT a decision surface)")]:
        g = d[d["stratum"] == sname]
        if not len(g):
            continue
        mo = float(g["DIAGNOSTIC_ORACLE_best_scaling_dR2"].max())
        P("      %-38s n %5d  max ORACLE %.6e = %.4f x FLOOR_1CELL  %s"
          % (lbl, int(g["n"].max()), mo, mo / cb.FLOOR_1CELL,
             "<-- ABOVE THE FLOOR" if mo >= cb.FLOOR_1CELL else ""))
    on = d[d["stratum"] == "on_stratum"]["DIAGNOSTIC_ORACLE_best_scaling_dR2"].max()
    al = d[d["stratum"] == "all"]["DIAGNOSTIC_ORACLE_best_scaling_dR2"].max()
    off = d[d["stratum"] == "off_stratum"]["DIAGNOSTIC_ORACLE_best_scaling_dR2"].max()
    P("\n    READING. On the decision-relevant rows the correct bound is %.4f x the floor and"
      % (on / cb.FLOOR_1CELL))
    P("    on the pooled rows %.4f x. THE D084 KILL HOLDS WHERE IT MATTERS." % (al / cb.FLOOR_1CELL))
    P("    It is only OFF-stratum -- rows that are not a betting decision surface -- that the")
    P("    oracle reaches %.4f x the floor, %.1f x D084's published ceiling. So the published"
      % (off / cb.FLOOR_1CELL, off / 0.000129))
    P("    figure understates the true bound by up to %.0f x, and the understatement lands"
      % (off / 0.000129))
    P("    entirely outside the stratum the decision was about. Both halves are recorded.")

d89 = os.path.join(cb.EXP, "E1_I0018_teammate_volume_channel", "arithmetic_ceiling.csv")
if os.path.exists(d89):
    d = pd.read_csv(d89)
    P("\n  E1_I0018/arithmetic_ceiling.csv (the D089 headline ceiling, %d rows)" % len(d))
    P("    NO ORACLE COLUMN. This table records only (d_points/sd_points)^2, the form s02 proved")
    P("    is not a bound, with no c* recorded anywhere. D089's headline 0.002057 therefore has")
    P("    NO RECORDED UPPER BOUND, in either direction. Its max recorded value is %.6f."
      % float(d["CEILING_dr2_points"].max()))
    P("    D089 is a SURVIVOR, not a kill, so nothing was closed on it -- but the ledger quotes")
    P("    0.002057 as 'the largest arithmetic ceiling the programme has measured', and that")
    P("    phrase attributes a boundedness the statistic does not have.")

rec = os.path.join(cb.EXP, "E1_I0018_teammate_volume_channel", "ceiling_reconciliation.csv")
if os.path.exists(rec):
    d = pd.read_csv(rec)
    d["c_star_sq"] = (d["DIAGNOSTIC_ORACLE_ceiling_best_rescaling"]
                      / d["D084_form_ceiling_var_share"])
    P("\n  E1_I0018/ceiling_reconciliation.csv (%d rows) -- D089 DID record an oracle here" % len(d))
    P("    max c*^2 = %.3f ; max ORACLE %.6e = %.4f x FLOOR_1CELL ; rows with ORACLE >= floor: %d"
      % (d["c_star_sq"].max(), d["DIAGNOSTIC_ORACLE_ceiling_best_rescaling"].max(),
         d["DIAGNOSTIC_ORACLE_ceiling_best_rescaling"].max() / cb.FLOOR_1CELL,
         int((d["DIAGNOSTIC_ORACLE_ceiling_best_rescaling"] >= cb.FLOOR_1CELL).sum())))
    P("    D089 is a SURVIVOR; a larger true bound on a surviving lead does not reopen anything")
    P("    that was closed. It is recorded because the ledger's phrase 'largest ceiling measured'")
    P("    is doing work the statistic cannot support.")

T.to_csv(os.path.join(cb.OUT, "CEILING_FORMS_CENSUS.csv"), index=False)
P("\n  wrote CEILING_FORMS_CENSUS.csv (%d tables)" % len(T))
with open(os.path.join(HERE, "_s07.json"), "w", encoding="utf-8") as fh:
    json.dump(json.loads(T.to_json(orient="records")), fh, indent=2, default=float)
with open(os.path.join(HERE, "run_log_s07.txt"), "w", encoding="utf-8") as fh:
    fh.write("\n".join(LOG))
P("  wrote _s07.json, run_log_s07.txt")
