#!/usr/bin/env python3
"""
Standalone leakage audit for the channel re-validation -- same pipeline
functions as run_reval.py (imported, not copied), extended to force ALL
fallback-flagged games into the audited sample regardless of eligibility.

Exists because run 1 of chanreval_2026_structural_repaired audited 60 eligible
games (0 fallback: no fallback game was eligible -- every expansion team's
first 5 opponents were themselves under the 5-game floor), leaving the
league-prior substitution path unaudited. This script closes that hole without
re-invoking compare_to_incumbent (no duplicate evaluation record on the
registry). run_reval.py's own audit now includes fallback games too, so any
future full rerun covers them automatically.

Writes audit_extended.json.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1]))

import run_reval as rr
import evalharness as eh

D = rr.load_base()
splits = eh.walk_forward_by_season(
    D, date_col="GAME_DATE", season_col="season",
    min_train_seasons=3, test_seasons=rr.TEST_YEARS,
)
outer24 = {s.name: s for s in splits}["season:2024"]
alphas, _ = rr.tune_alphas(D, outer24)
F = rr.build_features(D, alphas)
games = rr.make_games(F)
audits = rr.run_audits(D, alphas, games)
audits["note"] = ("60 seeded eligible test games + all 15 fallback-flagged games "
                  "(ineligible; the substitution path still computes features on them)")
audits["alphas"] = alphas
print(json.dumps(audits, indent=2))
with open(HERE / "audit_extended.json", "w", encoding="utf-8") as fh:
    json.dump(audits, fh, indent=2)
if not audits["passed"]:
    raise SystemExit("leakage audit FAILED")
print("wrote audit_extended.json")
