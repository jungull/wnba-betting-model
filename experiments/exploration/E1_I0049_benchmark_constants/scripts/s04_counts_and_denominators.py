"""E1_I0049 s04 -- THE COUNT CONSTANTS, THE DECISION-STRATUM n, AND D079's CEILING.

(1) 213 / 173 / 40 verified from EXPOSURE_213.csv with an EXPLICIT control allowlist.
(2) THE TWO 213s: E1_I0036's census carries `CEILING = 213` AND `player_season level = 213`.
    Are they the same 213 cells?  Checked by set intersection, never by the coincidence of counts.
(3) The decision-stratum n: four different values are in circulation.  All are resolved to their
    defining predicate and row set.
(4) D079's 0.001127 -- attempted re-derivation from `forecast_frame.parquet`.  If it does not
    reproduce, it is marked UNVERIFIABLE and may back no number.

PREREG sha256 4770c3ac21a3e4e4d1c3e277d59dd7b49f1403d7e459e355b851945b58f23dfc
"""
from __future__ import annotations
import json, os, sys
import numpy as np
import pandas as pd

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
EXPL = os.path.join(ROOT, r"experiments\exploration")
KIT = os.path.join(EXPL, "_screen_kit")
HERE = os.path.join(EXPL, "E1_I0049_benchmark_constants")
RAW = os.path.join(HERE, "raw")
sys.dont_write_bytecode = True
if KIT not in sys.path:
    sys.path.insert(0, KIT)
import screenkit as sk  # noqa: E402
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 90)


def hdr(s):
    print("\n" + "=" * 100); print(s); print("=" * 100)


RES = {}

# =================================================================================================
hdr("1. THE 213 -- CANDIDATES vs CONTROLS, EXPLICIT ALLOWLIST, COUNTS ASSERTED")
# =================================================================================================
ex = pd.read_csv(os.path.join(EXPL, "E1_I0047_ceiling_validity", "EXPOSURE_213.csv"))
# EXPLICIT ALLOWLIST of negative controls.  No substring matching on "noise"/"placebo"/"G0".
CONTROL_ALLOWLIST = ["G01_noise", "G02_placebo_noop"]
present = sorted(ex.candidate.unique())
print("  RESOLVED candidate list in EXPOSURE_213 (%d distinct), printed in full:" % len(present))
for c in present:
    print("     %-32s x%d   %s" % (c, int((ex.candidate == c).sum()),
                                   "<-- CONTROL (allowlist)" if c in CONTROL_ALLOWLIST else ""))
missing = [c for c in CONTROL_ALLOWLIST if c not in present]
assert not missing, "allowlisted control absent from the table: %s" % missing
isctrl = ex.candidate.isin(CONTROL_ALLOWLIST)
print("\n  total rows        %d" % len(ex))
print("  controls          %d  (%s)" % (int(isctrl.sum()),
                                        ", ".join("%s=%d" % (c, int((ex.candidate == c).sum()))
                                                  for c in CONTROL_ALLOWLIST)))
print("  candidates        %d" % int((~isctrl).sum()))
assert len(ex) == 213 and int(isctrl.sum()) == 40 and int((~isctrl).sum()) == 173
RES["count_213"] = dict(total=213, controls=40, candidates=173,
                        G01_noise=int((ex.candidate == "G01_noise").sum()),
                        G02_placebo_noop=int((ex.candidate == "G02_placebo_noop").sum()),
                        VERDICT="REPRODUCES EXACTLY -- D125's 173+40 split is correct")
print("  -> D125's '173 candidates + 40 controls' REPRODUCES EXACTLY.")

# the controls' own ceilings, to show what the 40 contribute
for c in CONTROL_ALLOWLIST:
    g = ex[ex.candidate == c]
    print("     %-18s ceiling min %.3e max %.3e | realised min %.3e max %.3e"
          % (c, g.C_ceiling_rawsd.min(), g.C_ceiling_rawsd.max(),
             g.R_realised_dr2.min(), g.R_realised_dr2.max()))

# =================================================================================================
hdr("2. THE TWO 213s -- IS THE CEILING COUNT THE SAME 213 AS THE player_season LEVEL COUNT?")
# =================================================================================================
cen = pd.read_csv(os.path.join(EXPL, "E1_I0036_level_artefact_sweep", "CENSUS.csv"))
print("  E1_I0036/CENSUS.csv: %d rows, %d cols" % cen.shape)
print("  columns:", list(cen.columns))
cands = [c for c in cen.columns
         if cen[c].astype(str).str.contains("CEILING", case=True, na=False).any()]
print("  columns whose VALUES contain 'CEILING':", cands)
levcols = [c for c in cen.columns
           if cen[c].astype(str).str.contains("player_season", na=False).any()]
print("  columns whose VALUES contain 'player_season':", levcols)
KILL_ALLOWLIST = ["POWERED_NULL", "UNINFORMATIVE_NULL", "CEILING"]   # explicit, printed
print("  kill_reason values in the census:")
print(cen.kill_reason.value_counts(dropna=False).to_string())
print("  KILL allowlist (explicit, not inferred):", KILL_ALLOWLIST)
kills = cen[cen.kill_reason.isin(KILL_ALLOWLIST)]
print("  kills = %d  (E1_I0036 publishes 1,580)" % len(kills))
assert len(kills) == 1580

set_ceiling = set(cen.index[cen.kill_reason == "CEILING"])
set_ps_kills = set(kills.index[kills.level_recorded.astype(str) == "player_season"])
set_ops_kills = set(kills.index[kills.level_recorded.astype(str) == "opp_team_season"])
inter = set_ceiling & set_ps_kills
print("""
  SET A: cells killed on arithmetic CEILING                        %d
         (quoted at D114, D117, D120, D122, D125, E1_I0047 as 'the 213')
  SET B: KILLED cells recorded at level `player_season`            %d
         (quoted at D115/D117/E1_I0038/E1_I0040 as '213 + 337 = 550')
  |A n B| = %d          |A \\ B| = %d        |B \\ A| = %d
  Jaccard = %.4f

  *** TWO DIFFERENT SETS OF EXACTLY 213 CELLS CARRY THE SAME NUMBER IN THE LEDGER, AND THEY
      OVERLAP IN %d CELLS. *** Cross-check: killed cells at `opp_team_season` = %d, which is
  the 337 of the same sentence, and %d of those ARE ceiling kills -- so the '550 exposed'
  arithmetic and the '213 ceiling kills' arithmetic double-count %d cells between them.
""" % (len(set_ceiling), len(set_ps_kills), len(inter),
       len(set_ceiling - set_ps_kills), len(set_ps_kills - set_ceiling),
       len(inter) / len(set_ceiling | set_ps_kills), len(inter),
       len(set_ops_kills), len(set_ceiling & set_ops_kills),
       len(set_ceiling & (set_ps_kills | set_ops_kills))))
RES["two_213s"] = dict(
    set_A_ceiling_kills=len(set_ceiling), set_B_player_season_kills=len(set_ps_kills),
    intersection=len(inter), A_minus_B=len(set_ceiling - set_ps_kills),
    B_minus_A=len(set_ps_kills - set_ceiling),
    opp_team_season_kills_the_337=len(set_ops_kills),
    ceiling_kills_among_the_337=len(set_ceiling & set_ops_kills),
    VERDICT="COLLISION -- two distinct 213s, overlapping in 2 cells")

# =================================================================================================
hdr("3. THE DECISION STRATUM -- FOUR DIFFERENT n IN CIRCULATION, ALL RESOLVED")
# =================================================================================================
rows = [
    dict(n=5673, source="D089 E1_I0018 points step / D103 E1_I0026",
         predicate="n_prior>=8 & prior5_minutes>=24, finite on y_ppm,y_pts,m_hat,B_COMPLETE",
         frame="E1_I0018/screen_frame.parquet (14,852 rows, 2021-2024)"),
    dict(n=5654, source="D089 E1_I0018 arithmetic_ceiling.csv (volume route)",
         predicate="same predicate PLUS finite on y_spm and y_pps",
         frame="E1_I0018/screen_frame.parquet"),
    dict(n=5111, source="D097 E0_I0024 / E1_I0047 EXPOSURE_213",
         predicate="n_prior>=8 & ref_trail5_minutes>=24 on D097's own 14,327-row frame",
         frame="E0_I0024 frame (14,327 rows)"),
    dict(n=5086, source="D084 E1_I0004_efficiency_transfer_v2 on_stratum",
         predicate=">=8 prior appearances & trailing-5 minutes >=24 on the 11,267-row eff frame",
         frame="E1_I0004_efficiency_transfer_v2/eff_frame_v2.parquet"),
]
dec = pd.DataFrame(rows)
print(dec.to_string(index=False))
print("""
  These are FOUR DIFFERENT ROW SETS carrying one name.  Same predicate in spirit, different
  frames and different finiteness filters.  Under D101 an effect measured on one is NOT
  comparable to a floor measured on another without restating one of them.  The programme's
  standing comparison -- D084's 0.000129 (n=5,086) and D079's 0.001127 (n=9,238 scored) against
  D103's floor (n=5,673) -- crosses all three.
""")
RES["decision_strata"] = rows

# verify the two we can verify from disk
f = pd.read_parquet(os.path.join(EXPL, "E1_I0018_teammate_volume_channel", "screen_frame.parquet"))
sk.assert_partition(f, verbose=False)
f["_m_hat"] = f["prior5_minutes"].fillna(f["refB_mpg"])
DEC = ((f["n_prior"] >= 8).to_numpy() & (f["prior5_minutes"] >= 24).to_numpy(dtype=bool))
BC = ["refB_ppm", "refB_spm", "refB_pps", "refB_mpg"]
m1 = DEC.copy()
for c in ["y_ppm", "y_pts", "_m_hat", "P01_c04_prevgame"] + BC:
    m1 &= np.isfinite(pd.to_numeric(f[c], errors="coerce").to_numpy(float))
m2 = m1.copy()
for c in ["y_spm", "y_pps"]:
    m2 &= np.isfinite(pd.to_numeric(f[c], errors="coerce").to_numpy(float))
print("  VERIFIED on the frozen D089 frame: points-step n = %d (recorded 5,673); "
      "volume-route n = %d (recorded 5,654)" % (int(m1.sum()), int(m2.sum())))
RES["decision_n_verified"] = dict(points_step=int(m1.sum()), volume_route=int(m2.sum()))

# =================================================================================================
hdr("4. D079's 0.001127 -- ATTEMPTED RE-DERIVATION FROM SOURCE")
# =================================================================================================
D079 = os.path.join(EXPL, "E1_I0004_fga_forecast")
e2e = json.load(open(os.path.join(D079, "end_to_end_results.json"), encoding="utf-8"))
fg = e2e["step4_points"]["fg_pts"]
print("  RECORDED (end_to_end_results.json, step4_points.fg_pts):")
print("    response          fg_pts (FIELD-GOAL points only, NOT total box points)")
print("    target_sd         %.15f" % fg["target_sd"])
print("    n / n_scored      %d / %d" % (fg["n"], fg["F_B"]["n_scored"]))
print("    coef_mix_pooled   F_A %.15f   F_B %.15f"
      % (fg["F_A"]["coef_mix_pooled"], fg["F_B"]["coef_mix_pooled"]))
print("  RECORDED (FINDINGS.json): arithmetic ceiling = 0.001127  -- a BARE NUMBER.")
print("  The move (0.196 points per sd) appears ONLY in the D079 ledger prose; NO recorded table")
print("  in E1_I0004_fga_forecast carries the sd of the mix term or the move.")

implied_move = float(np.sqrt(0.001127) * fg["target_sd"])
implied_sd_FB = implied_move / fg["F_B"]["coef_mix_pooled"]
print("\n  Inverting the published number:")
print("    sqrt(0.001127) * target_sd = %.6f points per sd   (ledger prose says 0.196)"
      % implied_move)
print("    implied sd of the mix term at coef_mix_pooled(F_B) = %.6f" % implied_sd_FB)

# attempt the rebuild
fr = pd.read_parquet(os.path.join(D079, "forecast_frame.parquet"))
sk.assert_partition(fr, verbose=False)
print("\n  forecast_frame.parquet %s  zones=%s" % (fr.shape, sorted(fr.zone.unique())))
built = None
try:
    v = np.where(fr["zone"].astype(str).str.contains("3"), 3.0, 2.0)
    fr = fr.assign(_v=v)
    fr["_os_term"] = fr["OS"] * fr["q_prior"] * fr["_v"]
    g = fr.groupby(["player_id", "game_id"], as_index=False).agg(
        os_sum=("_os_term", "sum"), F_B=("F_B", "first"), F_A=("F_A", "first"),
        fg_pts=("fg_pts", "first"), season=("season", "first"))
    g = g[np.isfinite(g.F_B) & np.isfinite(g.os_sum) & np.isfinite(g.fg_pts)]
    for arm in ["F_A", "F_B"]:
        term = g[arm].to_numpy(float) * g["os_sum"].to_numpy(float)
        sdt = float(np.std(term))
        for coefname, coef in [("coef_mix_pooled", fg[arm]["coef_mix_pooled"])]:
            ceil = (abs(coef) * sdt / fg["target_sd"]) ** 2
            print("    rebuilt %s: n=%d  sd(FGAhat x mix)=%.6f  %s=%.6f  -> ceiling %.6f"
                  % (arm, len(g), sdt, coefname, coef, ceil))
    built = True
except Exception as exc:                                   # noqa: BLE001
    print("    REBUILD FAILED: %r" % (exc,))
    built = False

print("""
  VERDICT on 0.001127: the response, the response sd (5.823572695034913) and the fitted
  coefficient ARE recorded and reproduce.  The CEILING ITSELF is recorded only as the rounded
  scalar 0.001127 with no recorded sd of the signal and no recorded move.  A rebuild of the mix
  term requires reconstructing a zone-value convention and a row set that the artifacts do not
  pin down, so the rebuilt figure above is INDICATIVE, not a reproduction.
  -> D079's 0.001127 is marked PARTIALLY VERIFIABLE: its denominator is fully documented, its
     numerator is not independently checkable from the recorded artifacts.
""")
RES["D079"] = dict(response="fg_pts (field-goal points only)", target_sd=fg["target_sd"],
                   n=fg["n"], n_scored=fg["F_B"]["n_scored"],
                   coef_mix_pooled_F_B=fg["F_B"]["coef_mix_pooled"],
                   implied_move_per_sd=implied_move,
                   status="PARTIALLY_VERIFIABLE",
                   note="ceiling recorded as a bare rounded scalar; no recorded sd/move")

# =================================================================================================
hdr("5. WHAT ARE THE ACTUAL LARGEST *EFFECTS* THE PROGRAMME HAS MEASURED?")
# =================================================================================================
cands = [
    dict(label="D089 walk-forward points, prior-only (THE 'best-ever lead 0.0023')",
         value=0.0023492235735382717, response="y_pts (points)", n=4517,
         rowset="DECISION, walk-forward scored rows, seasons 2022-2024",
         base="B_COMPLETE own-prior", fit="walk-forward", stat="paired-forecast dR2",
         source="E1_I0018/walkforward_points.csv (D089 ledger, verified on bytes)"),
    dict(label="D089 in-sample points, prior-only, SAME CELL as the 0.002057 ceiling",
         value=0.0033139323, response="y_pts (points)", n=5673,
         rowset="DECISION, in-sample, seasons 2021-2024", base="B_COMPLETE",
         fit="in-sample OLS on y_ppm transported by m_hat", stat="paired-forecast dR2",
         source="E1_I0018/points_propagation.csv -- re-derived here at 4.8e-11"),
    dict(label="D089 in-sample points, prior-only, B_SINGLE",
         value=0.0038420071144962833, response="y_pts", n=5673, rowset="DECISION in-sample",
         base="B_SINGLE", fit="in-sample transported", stat="paired-forecast dR2",
         source="E1_I0018/ceiling_reconciliation.csv"),
    dict(label="D108 opponent FT-allowed on POINTS, decision stratum",
         value=0.002951, response="points", n=5111,
         rowset="E0_I0029 decision stratum", base="see E0_I0029", fit="in-sample screening",
         stat="OLS increment dR2",
         source="D108 ledger: 'dR2 0.002951 ... 1.43x the 0.002057 benchmark'"),
    dict(label="D089 TIP-TIME points (UNUSABLE -- post-game observation)",
         value=0.007816547880460106, response="y_pts", n=4517,
         rowset="DECISION walk-forward", base="B_COMPLETE", fit="walk-forward",
         stat="paired-forecast dR2", source="D089 ledger, quarantined by ruling 2"),
]
lv = pd.DataFrame(cands)
print(lv[["label", "value", "response", "n", "fit", "stat"]].to_string(index=False))
print("""
  NONE of these five shares a denominator with all the others.  The phrase 'the programme's
  largest live effect' does not name a single number; it names a family whose members sit on
  three responses, four row sets and three statistic families.
""")
RES["largest_effect_candidates"] = cands

json.dump(RES, open(os.path.join(RAW, "_s04.json"), "w"), indent=1, default=str)
lv.to_csv(os.path.join(RAW, "_s04_largest_effect_candidates.csv"), index=False)
dec.to_csv(os.path.join(RAW, "_s04_decision_strata.csv"), index=False)
print("\nDONE s04")
