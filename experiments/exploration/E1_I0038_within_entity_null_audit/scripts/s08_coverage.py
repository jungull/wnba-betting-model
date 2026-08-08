"""S08 -- CENSUS COVERAGE.  How much of the programme's recorded evidence does the 8-screen
census NOT cover, and how much of THAT used a within-entity null?

Universe U2 (PREREG 2): every FINDINGS.json under experiments/exploration/.
No cell is classified from a FINDINGS.json narrative field.  This step counts what is
INVISIBLE to the audit, which is a finding about the record, not about the cells.
"""
import glob
import json
import os
import re
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab38 import EXP, OUT, hdr

CENSUS_SCREENS = {
    "E0_I0014_residual_heterogeneity", "E0_I0016_efficiency_predictors",
    "E0_I0017_shot_quality_efficiency", "E0_I0019_availability_forecast",
    "E0_I0024_reb_ast_characterisation", "E0_I0029_freethrow_hurdle",
    "E1_I0018_teammate_volume_channel", "E1_I0023_usage_defence_interaction",
}

# tokens that name a WITHIN-entity permutation scheme, in any of this programme's dialects
WITHIN_TOK = ["within_entity", "p_within", "within_block", "cyclic", "N_CYCLIC",
              "SCHEME_WITHIN", "within_cyclic", "player_within", "within_date_demeaned"]
BETWEEN_TOK = ["entity_swap", "eswap", "pswap", "N_ENTITY", "N_PSWAP", "N_TSWAP", "N_OSWAP",
               "p_between", "between_block", "SCHEME_BETWEEN", "block_index", "signflip",
               "sign_flip", "teamgame_between", "teamseason_between"]

hdr("1. FINDINGS.json INVENTORY")
fj = sorted(glob.glob(os.path.join(EXP, "**", "FINDINGS.json"), recursive=True))
fj = [p for p in fj if "E1_I0038" not in p]
rows = []
for p in fj:
    rel = os.path.relpath(p, EXP).replace("\\", "/")
    screen = rel.split("/")[0]
    try:
        txt = open(p, encoding="utf-8", errors="replace").read()
    except Exception as e:
        rows.append(dict(screen=screen, path=rel, bytes=-1, err=str(e)[:60]))
        continue
    rows.append(dict(
        screen=screen, path=rel, bytes=len(txt),
        in_census=screen in CENSUS_SCREENS,
        mentions_within_scheme=any(t.lower() in txt.lower() for t in WITHIN_TOK),
        mentions_between_scheme=any(t.lower() in txt.lower() for t in BETWEEN_TOK),
        mentions_null_mean=("null_mean" in txt or "nullmean" in txt),
        mentions_var_share=("var_share" in txt),
    ))
C = pd.DataFrame(rows)
print(f"  FINDINGS.json files: {len(C)}   distinct screens: {C['screen'].nunique()}")
print(f"  screens INSIDE the census : {C.loc[C['in_census'], 'screen'].nunique()}")
print(f"  screens OUTSIDE the census: {C.loc[~C['in_census'], 'screen'].nunique()}")

hdr("2. SCREENS OUTSIDE THE CENSUS THAT MENTION A WITHIN-ENTITY PERMUTATION SCHEME")
out = C[~C["in_census"]].groupby("screen").agg(
    files=("path", "size"),
    within=("mentions_within_scheme", "any"),
    between=("mentions_between_scheme", "any"),
    null_mean=("mentions_null_mean", "any"),
    var_share=("mentions_var_share", "any")).reset_index()
print(out.to_string(index=False))
print(f"\n  outside-census screens mentioning a WITHIN-entity scheme: "
      f"{int(out['within'].sum())} of {len(out)}")
print("  *** These are OUTSIDE the audited census.  Their cells are NOT in AUDIT_TABLE.csv and")
print("      their exposure is UNKNOWN, not zero.  This is the audit's outer boundary. ***")

hdr("3. CSV CELL TABLES OUTSIDE THE CENSUS CARRYING A WITHIN-ENTITY p COLUMN")
csvs = sorted(glob.glob(os.path.join(EXP, "**", "*.csv"), recursive=True))
hits = []
for p in csvs:
    rel = os.path.relpath(p, EXP).replace("\\", "/")
    screen = rel.split("/")[0]
    if screen in CENSUS_SCREENS or screen == "E1_I0038_within_entity_null_audit":
        continue
    try:
        cols = list(pd.read_csv(p, nrows=0).columns)
    except Exception:
        continue
    w = [c for c in cols if any(t.lower() in c.lower() for t in WITHIN_TOK)]
    if not w:
        continue
    try:
        n = sum(1 for _ in open(p, encoding="utf-8", errors="replace")) - 1
    except Exception:
        n = -1
    hits.append(dict(screen=screen, file=rel, rows=n, within_cols="|".join(w),
                     has_null_mean=any("null_mean" in c or "nullmean" in c for c in cols),
                     has_var_share=any("var_share" in c for c in cols)))
H = pd.DataFrame(hits)
if len(H):
    print(H.to_string(index=False))
    print(f"\n  {len(H)} tables across {H['screen'].nunique()} out-of-census screens carry a "
          f"within-entity p column, totalling {int(H.loc[H['rows'] > 0, 'rows'].sum())} rows.")
else:
    print("  none")

C.to_csv(os.path.join(OUT, "CENSUS_COVERAGE.csv"), index=False)
(H if len(H) else pd.DataFrame(columns=["screen", "file", "rows", "within_cols"])).to_csv(
    os.path.join(OUT, "OUT_OF_CENSUS_WITHIN_NULL_TABLES.csv"), index=False)
json.dump(dict(
    findings_json_files=len(C), screens_total=int(C["screen"].nunique()),
    screens_in_census=int(C.loc[C["in_census"], "screen"].nunique()),
    screens_out_of_census=int(C.loc[~C["in_census"], "screen"].nunique()),
    out_of_census_mentioning_within=int(out["within"].sum()),
    out_of_census_tables_with_within_col=len(H),
    out_of_census_rows_in_those_tables=int(H.loc[H["rows"] > 0, "rows"].sum()) if len(H) else 0,
), open(os.path.join(OUT, "scripts", "_s08.json"), "w"), indent=1)
print("\nwrote CENSUS_COVERAGE.csv, OUT_OF_CENSUS_WITHIN_NULL_TABLES.csv")
