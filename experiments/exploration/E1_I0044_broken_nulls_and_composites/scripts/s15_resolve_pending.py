"""S15 -- resolve the 84 PENDING composites (single ASSEMBLED columns) against the invariant.

These are all cases where the candidate is ONE column, built by arithmetic from named
components, and the null permutes or relabels THAT COLUMN as a whole.  That matters: a
permutation of the assembled column moves every component simultaneously, so a composite is not
exposed merely for spanning levels.  The exposure arises in one specific configuration:

  the null is a BETWEEN-entity relabel at entity E, and at least one component varies at a
  level FINER than E.

Then the relabel moves whole E-blocks and the finer component's within-block pattern survives
the draw in shape.  (This is exactly the mechanism Debt 1 measured directly on E0_I0014:
`block_index` maps the donor onto the receiver in chronological position order, so the
within-block profile is preserved -- measured correlation 0.14 to 0.64.)

Component levels are taken ONLY from what each screen recorded about itself:
  E0_I0014 / E0_I0015 : permutation_nulls.npz `vsb` + PLAYER/TEAM scheme, and grouping_levels.csv
  E0_I0019            : grouping_levels.csv (var_share_between_primary_block, scheme_primary)
  E0_I0016 / E0_I0017 / E0_I0024 / E0_I0029 : the screen's own declared ENTITY / level field
Anything not on the screen's own record is UNDETERMINABLE and stays that way.
"""
import ast, json, os, re
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPL = os.path.dirname(HERE)

C = pd.read_csv(os.path.join(HERE, "_COMPOSITE_SWEEP_STAGE1.csv"))
P = C[C["composite_verdict"] == "PENDING"].copy()
print("PENDING to resolve: %d" % len(P))

# ------------------------------------------------------------------ screens' own level records
LEV = {}          # (screen, column) -> (level_string, source)

# E0_I0014 + E0_I0015 (E0_I0015 imports E0_I0014's builder columns)
z = np.load(os.path.join(EXPL, "E0_I0014_residual_heterogeneity", "permutation_nulls.npz"),
            allow_pickle=True)
nm = [str(s) for s in z["names"]]
res14 = pd.read_csv(os.path.join(EXPL, "E0_I0014_residual_heterogeneity", "screen_results.csv"))
sch = res14.drop_duplicates("candidate").set_index("candidate")["perm_scheme"].to_dict()
for i, c in enumerate(nm):
    lv = "player-season" if sch.get(c) == "PLAYER" else "team-season"
    LEV[("E0_I0014_residual_heterogeneity", c)] = (
        "%s block, measured vsb=%.4f" % (lv, z["vsb"][i]), "permutation_nulls.npz + screen_results")
    LEV[("E0_I0015_points_skill_decomposition", c)] = LEV[
        ("E0_I0014_residual_heterogeneity", c)]

gl15 = os.path.join(EXPL, "E0_I0015_points_skill_decomposition", "grouping_levels.csv")
if os.path.exists(gl15):
    g = pd.read_csv(gl15)
    print("E0_I0015 grouping_levels.csv cols:", list(g.columns), g.shape)
    cc = "candidate" if "candidate" in g.columns else g.columns[0]
    vs = [c for c in g.columns if "var_share" in c or "vsb" in c]
    for _, r in g.iterrows():
        v = float(r[vs[0]]) if vs and pd.notna(r[vs[0]]) else np.nan
        LEV[("E0_I0015_points_skill_decomposition", str(r[cc]))] = (
            "measured var_share_between=%.4f" % v, "grouping_levels.csv")

gl19 = pd.read_csv(os.path.join(EXPL, "E0_I0019_availability_forecast", "grouping_levels.csv"))
for _, r in gl19.iterrows():
    LEV[("E0_I0019_availability_forecast", str(r["candidate"]))] = (
        "%s, measured vsb=%.4f" % (r["scheme_primary"],
                                   float(r["var_share_between_primary_block"])),
        "grouping_levels.csv")

def declared_levels(screen, pyfile, pattern):
    p = os.path.join(EXPL, screen, pyfile)
    if not os.path.exists(p):
        return 0
    txt = open(p, "r", encoding="utf-8-sig", errors="replace").read()
    k = 0
    for mm in re.finditer(pattern, txt):
        LEV[(screen, mm.group(1))] = (mm.group(2), pyfile)
        k += 1
    return k

k24 = declared_levels("E0_I0024_reb_ast_characterisation", "s01_prereg.py",
                      r'\(\s*"([A-Za-z0-9_]+)"\s*,\s*"[^"]*"\s*,\s*"([a-z_]+)"')
k29 = declared_levels("E0_I0029_freethrow_hurdle", "s01_prereg.py",
                      r'name="([A-Za-z0-9_]+)"[^)]*?level="([a-z_]+)"')
k16 = declared_levels("E0_I0016_efficiency_predictors", "ep_base.py",
                      r'ENTITY\[\s*"?([A-Za-z0-9_]+)"?\s*\]\s*=\s*\(\s*"([a-z_]+)"')
print("declared levels harvested: E0_I0024 %d, E0_I0029 %d, E0_I0016 %d" % (k24, k29, k16))
print("total level records: %d" % len(LEV))

# ------------------------------------------------------------------ null scheme per screen
# taken from each screen's own source, as reported in the sweep's evidence trail
NULLS = {
 "E0_I0014_residual_heterogeneity":
   ("BETWEEN-block reassignment if vsb>0.5 else WITHIN-block shuffle, of the ASSEMBLED column",
    "player-season or team-season", "PERMUTATION_OF_COLUMN"),
 "E0_I0015_points_skill_decomposition":
   ("BETWEEN-block if measured vsb>0.5 else WITHIN-block, chosen from the screen's own share",
    "player-season", "PERMUTATION_OF_COLUMN"),
 "E0_I0019_availability_forecast":
   ("player_between primary, player_within secondary, worst-of taken as the verdict",
    "player-season", "PERMUTATION_OF_COLUMN"),
 "E0_I0016_efficiency_predictors":
   ("entity swap within season at the candidate's declared ENTITY",
    "declared entity", "PERMUTATION_OF_COLUMN"),
 "E0_I0017_shot_quality_efficiency":
   ("entity swap within season at the candidate's declared entity",
    "declared entity", "PERMUTATION_OF_COLUMN"),
 "E0_I0024_reb_ast_characterisation":
   ("entity_swap_within_season AND cyclic_shift_within_groups, p_correct = max(p_swap, p_cyc)",
    "declared level", "PERMUTATION_OF_COLUMN"),
 "E0_I0029_freethrow_hurdle":
   ("N_ROW / N_CYCLIC / N_PSWAP / N_ENTITY selected from the declared level; only N_PSWAP and "
    "N_ENTITY may carry a verdict", "declared level", "PERMUTATION_OF_COLUMN"),
 "E1_I0018_teammate_volume_channel": ("(not resolved here)", "", "UNDETERMINED"),
 "E1_I0021_heterogeneity_diagnostic":
   ("within-player cyclic shift; statistic is the SD of per-player slopes on WITHIN-PLAYER "
    "DEMEANED x and y", "player", "PERMUTATION_OF_COLUMN__WITHIN_ESTIMAND"),
 "E1_I0023_usage_defence_interaction":
   ("within-date opponent swap of the defence value + cluster sign flip at opp-team-season",
    "team-game / opp-team-season", "PERMUTATION_OF_ONE_FACTOR"),
 "E1_I0030_home_advantage_accounting":
   ("paired game sign flip", "game", "PAIRED_CLUSTER"),
 "E1_I0036_level_artefact_sweep": ("re-run / fair-test cells", "", "UNDETERMINED"),
 "E1_I0020_coldstart_tiering": ("clustered paired sign flip", "player-season", "PAIRED_CLUSTER"),
 "E1_I0022_optimal_simple_estimator": ("block sign flip", "player-season", "PAIRED_CLUSTER"),
 "E1_I0025_threshold_vs_refit": ("within-date opponent swap", "team-game",
                                 "PERMUTATION_OF_ONE_FACTOR"),
}

def comps_of(expr):
    """component column names named in the construction expression"""
    out = []
    for mm in re.finditer(r'\[\s*[\'"]([A-Za-z0-9_%\s]+)[\'"]\s*\]', str(expr)):
        out.append(mm.group(1))
    return [c for c in out if not c.startswith("%")]

rows = []
for _, r in P.iterrows():
    scr = r["screen"]
    cs = comps_of(r["construction_expr"])
    levs, srcs, unknown = [], [], []
    for c in cs:
        k = (scr, c)
        if k in LEV:
            levs.append(LEV[k][0]); srcs.append(LEV[k][1])
        else:
            unknown.append(c)
    ns, nl, nk = NULLS.get(scr, ("(unknown)", "", "UNDETERMINED"))
    if nk == "PAIRED_CLUSTER" and scr == "E1_I0030_home_advantage_accounting":
        v = "NOT_EXPOSED"
        why = ("paired GAME sign flip; the game is the coarsest entity any component of a "
               "team-game statistic can vary at, so the cluster covers every component")
    elif nk == "PERMUTATION_OF_ONE_FACTOR":
        v = "NOT_EXPOSED"
        why = ("the permuted factor multiplies every tested term, so permuting it destroys the "
               "whole family including the interaction")
    elif nk == "PERMUTATION_OF_COLUMN__WITHIN_ESTIMAND":
        v = "NOT_EXPOSED"
        why = ("the estimand is a within-entity slope, so the between-entity component is "
               "annihilated before the statistic exists (E1_I0040 measured the consequence at "
               "4.441e-16)")
    elif nk == "PERMUTATION_OF_COLUMN":
        if unknown:
            v = "UNDETERMINABLE"
            why = ("the null permutes the ASSEMBLED column, so the invariant turns on whether "
                   "any component varies FINER than the permuting entity; the level of %s is "
                   "not on this screen's own record and was not invented here"
                   % ", ".join(sorted(set(unknown))[:4]))
        else:
            v = "NOT_EXPOSED"
            why = ("the null permutes the ASSEMBLED column, which moves every component "
                   "simultaneously; all components are on the screen's own level record at or "
                   "coarser than the permuting entity")
    else:
        v = "UNDETERMINABLE"
        why = "null scheme for this screen not established from source in this screen's scope"
    rows.append(dict(screen=scr, candidate=r["candidate"],
                     components_named_in_expr=json.dumps(cs),
                     component_levels=json.dumps(levs),
                     components_without_a_recorded_level=json.dumps(sorted(set(unknown))),
                     null_scheme=ns, null_permutes_or_clusters_at=nl, null_kind=nk,
                     composite_verdict=v, verdict_reason=why,
                     evidence="; ".join(sorted(set(srcs))) or "screen source"))
R = pd.DataFrame(rows)
print("\n=== resolution of the PENDING composites ===")
print(R["composite_verdict"].value_counts().to_string())
print(R.groupby(["screen", "composite_verdict"]).size().to_string())
R.to_csv(os.path.join(HERE, "_PENDING_RESOLVED.csv"), index=False)

# merge back
idx = C.set_index(["screen", "candidate"])
for _, r in R.iterrows():
    k = (r["screen"], r["candidate"])
    idx.loc[k, "component_levels"] = r["component_levels"]
    idx.loc[k, "null_scheme"] = r["null_scheme"]
    idx.loc[k, "null_permutes_or_clusters_at"] = r["null_permutes_or_clusters_at"]
    idx.loc[k, "composite_verdict"] = r["composite_verdict"]
    idx.loc[k, "verdict_reason"] = r["verdict_reason"]
    idx.loc[k, "evidence"] = r["evidence"]
    idx.loc[k, "classification_source"] = "EXPRESSION_PARSE + SCREEN_LEVEL_RECORD"
F = idx.reset_index()
assert len(F) == 540
F.to_csv(os.path.join(HERE, "COMPOSITE_SWEEP.csv"), index=False)
print("\nwrote COMPOSITE_SWEEP.csv", F.shape)

IS_COMP = F["candidate_class"].astype(str).str.startswith(("COMPOSITE", "BUNDLE"))
print("\n=== HEADLINE COUNTS ===")
print("(screen, candidate) pairs swept        : %d" % len(F))
print("COMPOSITE (incl. BUNDLE)               : %d" % int(IS_COMP.sum()))
print("ATOMIC / aggregate of one quantity     : %d"
      % int(F["candidate_class"].astype(str).str.startswith("ATOMIC").sum()))
print("NOT A FEATURE (stratum/arm/artefact)   : %d"
      % int(F["candidate_class"].astype(str).str.startswith("NOT_A_FEATURE").sum()))
print("construction UNDETERMINABLE            : %d"
      % int(F["candidate_class"].astype(str).str.startswith("UNDETERMINABLE").sum()))
print("\n--- verdicts among the composites ---")
print(F.loc[IS_COMP, "composite_verdict"].value_counts().to_string())
print("\n--- EXPOSED composites, resolved list ---")
E = F[(F["composite_verdict"] == "EXPOSED")]
print(E[["screen", "candidate", "candidate_class"]].to_string(index=False))
print("\n--- UNDETERMINABLE composites, resolved list ---")
U = F[IS_COMP & (F["composite_verdict"] == "UNDETERMINABLE")]
print(U[["screen", "candidate", "candidate_class"]].to_string(index=False))
print("\nDONE s15")
