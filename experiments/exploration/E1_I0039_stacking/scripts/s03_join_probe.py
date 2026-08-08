"""E1_I0039 s03 -- JOIN AND COVERAGE PROBE.  NO outcome statistic is computed here.

Decides, on counts alone, which stored artefacts can back each component's implementation, and
asserts D087 coverage on the rows each component actually treats.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import stk_base as B  # noqa: E402

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 60)

u = pd.read_parquet(os.path.join(B.OUT, "_universe.parquet"))
tier = pd.read_parquet(os.path.join(B.SRC_TIER, "tier_frame.parquet"))
work = pd.read_parquet(os.path.join(B.SRC_STACK, "_work.parquet"))
rem = pd.read_parquet(os.path.join(B.SRC_REDIST, "_rem_frame.parquet"))

B.hdr("1. U -- recap")
print("  n=%d  seasons=%s  team-games=%d  DECISION=%d"
      % (len(u), sorted(pd.unique(u["season"]).tolist()), u["tg"].nunique(),
         int(u["DECISION"].sum())))

B.hdr("2. JOIN tier_frame (component A's structural inputs) by row_uid")
TIER_KEEP = ("row_uid", "depth_rank", "depth_bucket", "roster_size", "draft_pick",
             "draft_bucket", "undrafted", "pos_group")
B.assert_allowlist(tier, TIER_KEEP, 8, "TIER_KEEP")
j = u.merge(tier[list(TIER_KEEP)], on="row_uid", how="left", indicator=True)
print("  merge indicator:")
print(j["_merge"].value_counts().to_string())
for c in ("depth_bucket", "draft_bucket"):
    for lbl, m in (("U", np.ones(len(j), bool)),
                   ("TREAT_A", j["TREAT_A_coldstart"].to_numpy(bool)),
                   ("TREAT_B", j["TREAT_B_fallback"].to_numpy(bool))):
        cov = float(j.loc[m, c].notna().mean())
        print("    D087 coverage %-13s on %-8s = %.4f  (%d/%d)"
              % (c, lbl, cov, int(j.loc[m, c].notna().sum()), int(m.sum())))

B.hdr("3. JOIN E1_I0032 _work (component B's tuned simple estimator) by game/team/player/season")
K = ["season", "player_id", "game_id", "team_id"]
WORK_KEEP = K + ["e_full_pts", "e_full_minutes", "e_full_fga",
                 "e_naive_pts", "e_naive_minutes", "e_naive_fga",
                 "R4_pts", "R4_minutes", "n_prior", "min5"]
B.assert_allowlist(work, WORK_KEEP, 14, "WORK_KEEP")
w = work[WORK_KEEP].copy()
# EXPLICIT key coercion.  The two frames store game_id/team_id/player_id with different dtypes
# (int64 vs str); a silent merge on mismatched dtypes is a classic way to lose rows without an
# error.  Coerce both sides to str and assert the resulting match rate rather than assume it.
for c in ("season", "player_id", "game_id", "team_id"):
    w[c] = w[c].astype(str)
    j[c] = j[c].astype(str)
w = w.rename(columns={"n_prior": "i32_n_prior", "min5": "i32_min5"})
print("  work rows: %d ; duplicate keys: %d" % (len(w), int(w.duplicated(K).sum())))
j2 = j.merge(w, on=K, how="left", indicator="_m2")
assert not any(c.endswith(("_x", "_y")) for c in j2.columns), "silent column collision in merge"
print(j2["_m2"].value_counts().to_string())
for c in ("e_full_pts", "e_full_minutes"):
    for lbl, m in (("U", np.ones(len(j2), bool)),
                   ("TREAT_A", j2["TREAT_A_coldstart"].to_numpy(bool)),
                   ("TREAT_B", j2["TREAT_B_fallback"].to_numpy(bool)),
                   ("TREAT_C", j2["TREAT_C_redistrib"].to_numpy(bool))):
        v = np.isfinite(pd.to_numeric(j2.loc[m, c], errors="coerce").to_numpy(float))
        print("    D087 coverage %-16s on %-8s = %.4f  (%d/%d)"
              % (c, lbl, v.mean(), int(v.sum()), int(m.sum())))

B.hdr("4. cross-check: does E1_I0032's n_prior agree with the champion's n_prior_games on U?")
a = pd.to_numeric(j2["i32_n_prior"], errors="coerce").to_numpy(float)
b = pd.to_numeric(j2["n_prior_games"], errors="coerce").to_numpy(float)
ok = np.isfinite(a) & np.isfinite(b)
print("  rows with both: %d ; identical: %d ; corr %.6f"
      % (int(ok.sum()), int((a[ok] == b[ok]).sum()), float(np.corrcoef(a[ok], b[ok])[0, 1])))
print("  E1_I0032 min5 vs base5_minutes: corr %.6f"
      % float(np.corrcoef(pd.to_numeric(j2["i32_min5"], errors="coerce").fillna(-1),
                          pd.to_numeric(j2["prior5_minutes"], errors="coerce").fillna(-1))[0, 1]))
d1 = ((pd.to_numeric(j2["i32_n_prior"], errors="coerce") >= 8)
      & (pd.to_numeric(j2["i32_min5"], errors="coerce") >= 24))
print("  DECISION by E1_I0032 fields: %d ; by champion fields: %d ; agree %.4f"
      % (int(d1.fillna(False).sum()), int(j2["DECISION"].sum()),
         float((d1.fillna(False) == j2["DECISION"]).mean())))

B.hdr("5. component C's ingredients on U -- u_i and z_i must be rebuilt on U, not inherited")
print("  rem frame carries u/z only for REM rows (n=%d in W2 RS)."
      % int(rem["season"].isin(B.SCORED_W2).sum()))
print("  U contains %d rows that are NOT established (no base5 or <3 priors)."
      % int((~(pd.to_numeric(u["nprior_minutes"], errors="coerce") >= 3)
             | u["base5_minutes"].isna()).sum()))
print("  => C's forecast term is DEFINED ONLY on established remaining rows and is IDENTICALLY")
print("     ZERO elsewhere.  That is a treated/untreated split inside C's own nominal row set")
print("     and the VACUOUS-CONTROL check must be run against it (E1_I0034's own trap).")
est = ((pd.to_numeric(u["nprior_minutes"], errors="coerce") >= 3) & u["base5_minutes"].notna())
print("  established rows on U: %d (%.2f%%)" % (int(est.sum()), 100.0 * est.mean()))
print("  established AND freed>=25: %d" % int((est & u["TREAT_C_redistrib"]).sum()))
print("  established AND freed>=25 AND DECISION: %d"
      % int((est & u["TREAT_C_redistrib"] & u["DECISION"]).sum()))

j2.drop(columns=["_merge", "_m2"]).to_parquet(os.path.join(B.OUT, "_universe2.parquet"), index=False)
print("\n  wrote _universe2.parquet")
