"""S03 -- What null scheme did each of the 30 screens actually USE to decide a cell?

Column names are not enough (E1_I0038's own lesson: five findings died to substring matching), so
this reads the SOURCE. For every .py in the 30 screens it records every line that names a
permutation scheme, then classifies the screen's DECISION null by what its own scripts construct.
Read-only outside this screen's directory.
"""
import os, re, json
import pandas as pd

EXPL = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\exploration"
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CENSUS = {"E0_I0014_residual_heterogeneity", "E0_I0016_efficiency_predictors",
          "E0_I0017_shot_quality_efficiency", "E0_I0019_availability_forecast",
          "E0_I0024_reb_ast_characterisation", "E0_I0029_freethrow_hurdle",
          "E1_I0018_teammate_volume_channel", "E1_I0023_usage_defence_interaction"}
cov = pd.read_csv(os.path.join(EXPL, "E1_I0038_within_entity_null_audit", "CENSUS_COVERAGE.csv"))
TARGETS = [s for s in sorted(cov["screen"].unique()) if s not in CENSUS]

# scheme vocabulary, taken from the kit and from the census screens' own code
PATS = {
    "WITHIN_ENTITY": re.compile(
        r"SCHEME_WITHIN|within_block|within_player|within_entity|within_group|cyclic_shift|"
        r"N_CYCLIC|np\.roll|roll\(|shift_within|within-shuffle|within_shuffle", re.I),
    "BETWEEN_ENTITY": re.compile(
        r"SCHEME_BETWEEN|N_ESWAP|N_PSWAP|entity_swap|entity swap|player_swap|block_reassign|"
        r"sign[_ ]?flip|signflip|cluster_sign|team_game_block|between_entity|swap_entities|"
        r"permute_entity|group_shuffle|shuffle_groups|SCHEME_ENTITY", re.I),
    "ROW": re.compile(r"SCHEME_ROW|N_ROW|row_level|row-level|free_shuffle|np\.random\.permutation\(n\)|"
                      r"shuffle\(\s*y\s*\)|row_null", re.I),
    "COVARIATE": re.compile(r"covariate_perm|permute_covariate|covariate permutation|cov_null", re.I),
    "PLACEBO": re.compile(r"placebo|noise_column|noop_placebo|G01_noise", re.I),
}

rows = []
for sc in TARGETS:
    d = os.path.join(EXPL, sc)
    for root, _dd, files in os.walk(d):
        for fn in files:
            if not fn.lower().endswith(".py"):
                continue
            fp = os.path.join(root, fn)
            try:
                src = open(fp, "r", encoding="utf-8", errors="replace").read()
            except Exception:
                continue
            for ln, line in enumerate(src.splitlines(), 1):
                s = line.strip()
                if not s or s.startswith("#"):
                    continue
                for k, pat in PATS.items():
                    if pat.search(s):
                        rows.append(dict(screen=sc, scheme=k,
                                         file=os.path.relpath(fp, EXPL).replace("\\", "/"),
                                         line=ln, code=s[:200]))
H = pd.DataFrame(rows)
H.to_csv(os.path.join(HERE, "SCHEME_CODE_HITS.csv"), index=False)

piv = (H.groupby(["screen", "scheme"]).size().unstack(fill_value=0)
       if len(H) else pd.DataFrame())
piv = piv.reindex(TARGETS, fill_value=0)
for c in ["WITHIN_ENTITY", "BETWEEN_ENTITY", "ROW", "COVARIATE", "PLACEBO"]:
    if c not in piv.columns:
        piv[c] = 0
piv = piv[["WITHIN_ENTITY", "BETWEEN_ENTITY", "ROW", "COVARIATE", "PLACEBO"]]
piv.to_csv(os.path.join(HERE, "SCHEME_BY_SCREEN.csv"))
print(piv.to_string())

print("\n--- WITHIN_ENTITY hits in detail (the only ones that can be exposed) ---")
w = H[H.scheme == "WITHIN_ENTITY"]
for sc, g in w.groupby("screen"):
    print("\n### %s  (%d lines)" % (sc, len(g)))
    for _, r in g.head(25).iterrows():
        print("   %s:%d  %s" % (os.path.basename(r["file"]), r["line"], r["code"][:150]))
