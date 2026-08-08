#!/usr/bin/env python3
"""E1_I0035 s07 -- DESCRIPTIVE cross-check of the tier proxy.  BACKS NO NUMBER.

Every stratified statistic in this screen uses `tier_A := row_uid in prediction_contract_v4`,
because contract v4 is manifest-verified and contract v5 -- which carries the arm's actual
`universe_tier` column -- is NOT (no sibling manifest -> UNVERIFIABLE).

That proxy is E1_I0033's and it reproduces their tier numbers exactly, which is strong evidence
it is the right set.  This script opens v5 ONCE, purely to DESCRIBE whether the proxy and the
real label agree.  If they disagree the strata in s04 are mislabelled and that becomes a stated
limitation.  No number in FINDINGS.json is changed by whatever this prints -- it is a diagnostic
about a definition, exactly as E1_I0033 opened v5 once to describe its 40 dropped rows.
"""
from __future__ import annotations
import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import av_base as ab  # noqa: E402

PF = pd.read_parquet(os.path.join(ab.OUT, "_player_frame.parquet"))
CV5 = os.path.join(ab.ROOT, "experiments", "prediction_contract_v5")
v5 = pd.read_parquet(os.path.join(CV5, "player_game.parquet"))
v5 = v5[v5["season"].isin(ab.EXPLORATION_SEASONS)].copy()
ab.assert_partition(v5, "cv5")
v5 = ab.pick(v5, ("row_uid", "universe_tier", "is_fallback", "candidate_source",
                  "team_assignment_confidence"), "cv5 DESCRIPTIVE ONLY")

m = PF[["row_uid", "tier_A"]].merge(v5, on="row_uid", how="left")
print("\n  RS1P rows: %d   matched to a v5 row: %d" % (len(m), int(m["universe_tier"].notna().sum())))
xt = pd.crosstab(m["tier_A"], m["universe_tier"], dropna=False)
print("\n  proxy (v4 membership)  x  v5 universe_tier:")
print(xt.to_string())
agree = int(((m["tier_A"]) == (m["universe_tier"] == "A")).sum())
print("\n  agree on %d of %d rows (%.4f%%)" % (agree, len(m), 100.0 * agree / len(m)))

print("\n  v5 candidate_source composition of the PROXY tier-B rows (descriptive):")
print(m.loc[~m["tier_A"], "candidate_source"].value_counts(dropna=False).to_string())
print("\n  v5 team_assignment_confidence of the PROXY tier-B rows (descriptive):")
print(m.loc[~m["tier_A"], "team_assignment_confidence"].value_counts(dropna=False).to_string())

out = {"STATUS": "DESCRIPTIVE ONLY -- prediction_contract_v5 is UNVERIFIABLE (no sibling "
                 "manifest); nothing in FINDINGS.json depends on this",
       "n_rows": int(len(m)), "n_matched": int(m["universe_tier"].notna().sum()),
       "n_agree": agree, "agreement_rate": agree / len(m),
       "crosstab": xt.to_dict(),
       "tierB_candidate_source": m.loc[~m["tier_A"], "candidate_source"]
       .value_counts(dropna=False).to_dict(),
       "tierB_confidence": m.loc[~m["tier_A"], "team_assignment_confidence"]
       .value_counts(dropna=False).to_dict()}
open(os.path.join(ab.OUT, "UNVERIFIABLE_tier_proxy_crosscheck.json"), "w",
     encoding="utf-8").write(json.dumps(ab.jsonable(out), indent=2))
print("\nDONE s07")
