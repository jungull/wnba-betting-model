"""S01 -- read-only structural probe of the 73 broken-null cells.

Question: WHY is each null degenerate?  Candidate mechanisms, all measurable:
  M1 STATISTIC CONSTANT UNDER THE NULL  -- the permutation is (near-)identity for this
     candidate, so every draw returns (nearly) the observed t.  Detect: n_unique draws,
     sd, and max within-permuting-entity spread of the candidate column.
  M2 TRIVIAL PERMUTATION SET           -- too few blocks / too few distinct arrangements.
     Detect: block count, block-size distribution, count of size-1 blocks.
  M3 COLLINEAR WITH THE BLOCK STRUCTURE-- candidate is a deterministic function of the
     block id, so any within-block shuffle is the identity.
  M4 FOLDING ARTEFACT ONLY             -- sd(|t|) is small merely because mean|t| is large
     and the signed null is fine.  Detect: recover sd(t) by moments.
  M5 NON-FINITE COERCION               -- s04_screen.py:215 writes 0.0 for non-finite t.

Read-only. No 2025/26 data. E0_I0014's analysis_frame.parquet is asserted season<=2024.
"""
import json, os
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPL = os.path.dirname(HERE)
S14 = os.path.join(EXPL, "E0_I0014_residual_heterogeneity")
S19 = os.path.join(EXPL, "E0_I0019_availability_forecast")

tf = pd.read_csv(os.path.join(EXPL, "E1_I0041_tstat_family_audit", "TSTAT_CELL_FLOORS.csv"))
broken = tf[(tf["degeneracy_ratio"] > 5) | (tf["sd_used_by_D103"] == 0.0)].copy()
assert len(broken) == 73
print("broken by screen:", broken["screen"].value_counts().to_dict())

# ---------------------------------------------------------------- E0_I0014 draws
z = np.load(os.path.join(S14, "permutation_nulls.npz"), allow_pickle=True)
names = [str(s) for s in z["names"]]
deps = [str(s) for s in z["dependents"]]
use_between = z["use_between"]
vsb = z["vsb"]
print("E0_I0014: %d candidates x %d dependents = %d cells" % (len(names), len(deps),
                                                              len(names) * len(deps)))

# frame (for M1/M3 measurement)
fr = pd.read_parquet(os.path.join(S14, "analysis_frame.parquet"))
assert fr["season"].max() <= 2024, fr["season"].max()
print("analysis_frame:", fr.shape, "seasons", sorted(fr["season"].unique()))
print("frame cols (first 60):", list(fr.columns)[:60])

res = pd.read_csv(os.path.join(S14, "screen_results.csv"))
print("screen_results cols:", list(res.columns))
print(res.head(2).to_string())

meta = {}
meta["e14_names"] = names
meta["e14_deps"] = deps
meta["e14_use_between"] = use_between.astype(int).tolist()
meta["e14_vsb"] = [None if not np.isfinite(v) else float(v) for v in vsb]

with open(os.path.join(HERE, "scripts", "_s01.json"), "w") as f:
    json.dump(meta, f, indent=2)
print("DONE s01 probe")
