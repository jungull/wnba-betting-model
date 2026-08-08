"""STEP 1 -- VERIFY PROVENANCE ON VALUES, INDEPENDENTLY OF THE COORDINATOR'S CHECK.

Refuses to proceed if any RAPM row's training seasons are not STRICTLY PRIOR to its emit season.
Also characterises the artifact's cross-season comparability, which turns out to be the first real
hazard: `lambda_chosen` varies by a factor of 50 across emit seasons, so `net_100` / `orapm_100` /
`drapm_100` are NOT on a common scale across seasons.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rp_base as B  # noqa: E402

B.hdr("STEP 1a -- rapm_v0.csv IS FORBIDDEN: assert it is never opened by this screen")
print("  rapm_v0.csv manifest asof_granularity is 'artifact' (bound at 2026) -> UNUSABLE.")
print("  This screen NEVER opens data/rapm/rapm_v0.csv.  The only RAPM read is:")
print("    %s" % B.RAPM)
print("  and its per-season companion %s" % B.RAPM_SEASONS)

B.hdr("STEP 1b -- MANIFEST, RE-CHECKED HERE (not inherited)")
r, prov = B.load_rapm(verbose=True)
print("  manifest status .............. %s" % prov["manifest_status"])
print("  manifest asof_granularity .... %s" % prov["manifest_asof_granularity"])

B.hdr("STEP 1c -- STRICT-PRIOR VERIFICATION ON THE ARTIFACT'S OWN COLUMN VALUES")
print("  per emit season (BEFORE the partition filter, so the check covers every row in the file):")
rows = []
for s in sorted(prov["per_emit_season_raw"]):
    v = prov["per_emit_season_raw"][s]
    print("    emit=%d  train_seasons=%s  max_train=%d  fit_through_season=%s  "
          "strictly_prior=%s  n=%d  players=%d"
          % (s, v["train_season_tokens"], v["max_train_season"], v["fit_through_season_values"],
             v["strictly_prior"], v["n_rows"], v["n_players"]))
    rows.append({"emit_season": s, "train_seasons": ",".join(str(x) for x in
                                                             v["train_season_tokens"]),
                 "max_train_season": v["max_train_season"],
                 "fit_through_season": v["fit_through_season_values"][0],
                 "strictly_prior": v["strictly_prior"], "n_rows": v["n_rows"],
                 "n_players": v["n_players"],
                 "lambda_chosen": v["lambda_chosen"][0],
                 "lambda_source": v["lambda_source"][0],
                 "in_exploration_partition": s in B.SCREEN_SEASONS})
print("\n  ROW-LEVEL checks (every row, not just group maxima):")
print("    rows with max(train_seasons) >= emit season .... %d" % prov["row_level_train_ge_emit"])
print("    rows with fit_through_season >= emit season .... %d" % prov["row_level_fitthrough_ge_emit"])
if not (prov["strict_prior_verified"] and prov["row_level_clean"]):
    raise SystemExit("STOP: STRICT-PRIOR VIOLATION IN rapm_walkforward.csv -> %s"
                     % prov["strict_prior_violations"])
print("\n  VERDICT: every row's training seasons are STRICTLY PRIOR to its emit season.  PASS.")
print("  CORRECTION TO THE BRIEF: train_seasons is CUMULATIVE, not prior-season-only.")
print("    emit 2022 <- 2021 ; emit 2023 <- 2021-2022 ; emit 2024 <- 2021-2023 (expanding window).")
print("    `fit_through_season` is the LAST training season, which is what the manifest note names.")
print("    This is still strictly prior, and it is MORE data, but it is not 'the prior season only'.")

B.hdr("STEP 1d -- CROSS-SEASON COMPARABILITY HAZARD (found here, not in the manifest)")
ss = B.load_rapm_seasons()
print(ss[["season", "fit_through_season", "train_seasons", "n_train_possessions", "n_players",
          "lambda_chosen", "lambda_source", "sd_net_100", "replacement_net_100_p25",
          "unseen_slot_pct", "thin_history_caveat"]].to_string(index=False))
print("""
  READ THIS CAREFULLY.  `lambda_chosen` is 100000 (2022, 'fallback_max_grid'), 33000 (2023) and
  2000 (2024).  The 2022 fit had ONE training season, no inner validation season was available, and
  the selector fell back to the maximum of the grid -- i.e. maximal shrinkage.  The consequence is
  visible in sd_net_100: 0.095 (2022), 0.373 (2023), 2.372 (2024) -- a 25x spread in the SCALE of
  the same column.  net_100 for 2022 is very nearly a constant.

  THEREFORE:
    * `net_100`, `orapm_100`, `drapm_100` are used ONLY after WITHIN-EMIT-SEASON standardisation
      (z_ prefix).  Pooling them raw across seasons would let 2024 dominate purely by scale.
    * the PRIMARY continuous RAPM measure in this screen is a FIXED-lambda column
      (net_100_lam2000), which IS on a common scale across emit seasons by construction.
    * 2022 is additionally flagged thin_history_caveat=True by the artifact's own producer.
""")
sd = r.groupby("season")[B.RAPM_CHOSEN + B.RAPM_FIXED].std(ddof=0)
print("  post-filter within-season SD of each RAPM column (2022-2024 only):")
print(sd.to_string())

B.hdr("STEP 1e -- SEASON GRANULARITY: WHAT IT DOES AND DOES NOT DISCHARGE (D080)")
print("""
  asof_granularity 'season' SATISFIES the partition guard: the value attached to a 2023 row is a
  season-level object whose inputs all predate the 2023 season, so no 2023+ information crosses.
  It DOES NOT discharge the retrospective check on its own -- a season-granular artifact could still
  have been built retrospectively.  Here the artifact's OWN train_seasons / fit_through_season
  columns were checked on values above and are strictly prior, which is stronger than season
  boundedness and IS what discharges it.

  THE LIMITATION THAT TRAVELS WITH EVERY RESULT BELOW: RAPM is a SLOW-MOVING PRIOR.  It takes ONE
  value per player per season.  It cannot move when a player's role changes in June, when they come
  back from injury, when a teammate is traded, or when they get hot.  Any within-season form signal
  it appears to carry is an artefact of something else.  It is a level, not a trajectory.
""")

B.hdr("STEP 1f -- COVERAGE AGAINST THE SCORED FRAME")
f = B.load_frame()
fr = B.attach_rapm(f, r)
cov = (fr.groupby(["season", "has_rapm"]).size().unstack(fill_value=0)
       .rename(columns={False: "no_rapm", True: "has_rapm"}))
print(cov.to_string())
first = fr.groupby(["season", "player_id"])["has_rapm"].first().reset_index()
print("\n  player-seasons in the scored frame WITHOUT a RAPM value, by season:")
print(first[~first["has_rapm"]].groupby("season").size().to_string())
rows_df = pd.DataFrame(rows)
B.wcsv(rows_df[rows_df["in_exploration_partition"]].drop(columns=["in_exploration_partition"]),
       "provenance_emit_seasons.csv")
print("\n  (the 2025/2026 emit rows are verified above and then DROPPED; they are not written to any"
      "\n   output table, and no 2025/2026 value is described anywhere in this screen.)")

B.jdump({"provenance": prov,
         "rapm_seasons_table": ss.to_dict("records"),
         "coverage_rows_by_season": cov.to_dict(),
         "n_frame_rows": int(len(fr)),
         "n_frame_rows_with_rapm": int(fr["has_rapm"].sum()),
         "frac_frame_rows_with_rapm": float(fr["has_rapm"].mean())}, "_s00.json")
print("\nSTEP 1 COMPLETE -- provenance VERIFIED independently.")
