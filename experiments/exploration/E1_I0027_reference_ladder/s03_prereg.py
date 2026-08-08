"""E1_I0027 s03 -- PREREGISTRATION.  RUNS BEFORE ANY RE-PRICED FIGURE IS COMPUTED.

Constraint 5 of the brief: PREREGISTER AND HASH the ladder definition before computing any
re-priced figure.  This script:
  1. selects the two hyperparameters D094 never measured (rebound and assist half-lives) on TRAIN
     SEASONS ONLY, and on the canonical frame only;
  2. freezes the whole ladder definition, hashes it, and writes REFERENCE_LADDER.md + _prereg.json;
  3. fixes, in advance, WHICH leads will be re-priced, on WHICH row sets, against WHICH rung, and
     what the denominator rule is;
  4. records what would count as "the ranking changes".

Nothing here reads a lead's result.  s04 and s05 re-hash the frozen spec and assert equality.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import refladder as RL                                     # noqa: E402

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
EXP = os.path.join(ROOT, r"experiments\exploration")
OUT = HERE

CANON_FRAME = os.path.join(EXP, r"E0_I0024_reb_ast_characterisation\screen_frame.parquet")
TRAIN_SEASONS = [2021, 2022]          # selection only; disjoint from every evaluation set
EVAL_SEASONS = [2023, 2024]


def hdr(s):
    print("\n" + "=" * 100)
    print(s)
    print("=" * 100)


hdr("E1_I0027 PREREGISTRATION")
print("  ladder hash BEFORE reb/ast selection: %s" % RL.ladder_hash())

hdr("1. canonical frame (READ ONLY)")
raw = pd.read_parquet(CANON_FRAME)
print("  %s" % CANON_FRAME)
print("  shape=%s  seasons=%s" % (raw.shape, sorted(raw["season"].unique())))
f, dcol = RL.normalise(raw, verbose=True)
print("  partition: %s" % RL.assert_partition(f, verbose=True))
print("  season calendar ranges:")
RL.assert_season_disjoint(f, "_date", verbose=True)
for t in RL.TARGETS:
    try:
        y = RL.target_series(f, t)
        print("    %-8s available  n_finite=%d  mean=%.4f  sd=%.4f"
              % (t, int(np.isfinite(y).sum()), np.nanmean(y), np.nanstd(y, ddof=1)))
    except KeyError as e:
        print("    %-8s NOT AVAILABLE (%s)" % (t, e))

hdr("2. half-life selection for the two targets D094 never measured")
print("  selection set: seasons %s ONLY.  Evaluation set: seasons %s." % (TRAIN_SEASONS, EVAL_SEASONS))
print("  grid = D094's EWMA half-life grid, unchanged: %s" % RL.HALF_LIFE_GRID)
sel_log = {}
for t in ["reb", "ast"]:
    print("\n  target %s:" % t)
    hl, rows = RL.select_half_life(f, t, TRAIN_SEASONS, verbose=True)
    RL.CANON[t]["half_life"] = float(hl)
    RL.CANON[t]["source"] = ("selected in E1_I0027 on train seasons %s only, D094's grid, "
                             "mode/shrinkage adopted from D094 unchanged" % TRAIN_SEASONS)
    sel_log[t] = {"chosen_half_life": float(hl),
                  "curve": [{"half_life": a, "train_mae": b, "n": c} for a, b, c in rows]}
    print("    CHOSEN half_life = %s" % hl)

hdr("3. the frozen ladder")
spec = RL.ladder_spec_text()
print(spec)
h = RL.ladder_hash()
print("\n  SHA-256 = %s" % h)

hdr("4. the re-price plan, fixed in advance")
PLAN = {
    "canonical_rung": RL.CANONICAL_RUNG,
    "also_reported_on": ["R1_PLAYER_EXPAND", "R2_EWMA_TUNED"],
    "leads": [
        {"lead": "D089_teammate_volume_prior_only",
         "quoted": 0.0023492235735382717,
         "quoted_what": "walk-forward paired points dR2 of P01_c04_prevgame over B_COMPLETE "
                        "(refB_ppm, refB_spm, refB_pps, refB_mpg, refB_own_usg_pg), DECISION "
                        "stratum, n=4517",
         "frame": "E1_I0018_teammate_volume_channel/screen_frame.parquet",
         "feature": "P01_c04_prevgame", "response": "pts",
         "repriceable": True,
         "why": "the feature column and the response are both frozen in the screen's own frame; "
                "only the REFERENCE changes"},
        {"lead": "D099_opponent_defence",
         "quoted_ppm": 0.005028055896625616, "quoted_points": 0.0033354248642841694,
         "quoted_what": "pooled defence main effect on the full DECISION stratum (n=4514) against "
                        "B_COMPLETE, common denominator",
         "frame": "E1_I0018 screen_frame joined to E0_I0016 screen_frame for A10_opp_defrtg",
         "feature": "A10_opp_defrtg", "response": ["pts", "ppm"],
         "repriceable": True,
         "why": "same construction as D089 with a different feature column"},
        {"lead": "D092_coldstart_tiering",
         "quoted": 0.0351,
         "quoted_what": "pooled points SKILL (1 - MAE ratio) of the operating rule against D076's "
                        "reference, which the same screen showed to be partly degenerate",
         "frame": "E1_I0020_coldstart_tiering/tier_frame.parquet + placeholders_pts.csv",
         "response": "pts", "repriceable": True,
         "why": "the quoted number IS a reference comparison; substituting the rung is the whole "
                "operation"},
        {"lead": "D074_D079_shot_mix_attempts",
         "quoted": 0.016853345987369095,
         "quoted_what": "end-to-end walk-forward dR2 on RESTRICTED-AREA ATTEMPT COUNTS",
         "repriceable": False,
         "why_not": "the response is a ZONE-LEVEL attempt count.  The ladder defines a rung for "
                    "TOTAL attempts (fga), not for attempts within a shot zone, and the lead's base "
                    "is a five-zone system of forecasts.  Re-pricing it means rebuilding the zone "
                    "forecasts, i.e. re-running the pipeline.  SKIPPED PER THE BRIEF rather than "
                    "approximated by substituting total FGA, which would be a different quantity "
                    "wearing the same name."},
        {"lead": "D072_I0009_additive_pressure",
         "quoted": 0.000413,
         "quoted_what": "walk-forward plain-OLS dR2 on TURNOVERS PER 100 OFFENSIVE POSSESSIONS",
         "repriceable": False,
         "why_not": "the response is a team-pressure RATE that is not one of the six ladder "
                    "targets, and its base is a fitted multi-term pressure model rather than a "
                    "reference forecast.  There is no rung to re-price it onto without defining a "
                    "seventh target and re-running the whole screen.  SKIPPED PER THE BRIEF."},
    ],
    "denominator_rule": [
        "Two dR2 figures are comparable only if ALL of the following hold.",
        "D1 SAME RESPONSE: the same variable in the same units.  No rescaling makes a dR2 on "
        "turnover-rate comparable to a dR2 on points (D072 ruling 4).",
        "D2 SAME SCORED ROWS: the identical row set, not merely the same n.",
        "D3 SAME DENOMINATOR: SST computed on that full scored row set about ITS OWN unweighted "
        "mean.  A subset's SST is never a valid denominator for a figure that will be compared to a "
        "stratum-wide figure (D099: a ~4x inflation).",
        "D4 SAME WEIGHTING in all three of the fit, the SSE and the SST (D072 ruling 2).",
        "D5 SAME BASE: both increments measured over the same reference model (D090, D094).",
        "If D2 fails but D1/D4/D5 hold, the figures become comparable after BOTH are re-expressed "
        "on a common denominator: dR2_common = SSE_reduction / SST_common, SST_common being the SST "
        "of the common scored row set.  If D1 fails, they are NOT comparable and no denominator "
        "fixes it.",
    ],
    "what_would_count_as_the_ranking_changing":
        "The leads that share the POINTS response (D089, D099, D092) are ranked by their re-priced "
        "figure on the canonical rung and a common denominator.  THE RANKING CHANGES if any pair "
        "swaps order relative to the order implied by the currently quoted figures.  This is "
        "declared BEFORE the figures are computed.  A rank swap means every prioritisation decision "
        "taken on the quoted numbers rested on an artefact; no swap means the reference problem is "
        "a REPORTING problem, not a DECISION problem.  Both answers are reportable and neither is "
        "the preferred outcome.",
    "nulls": "Correct-level only.  Paired cluster sign-flip at (season, player) for forecast "
             "comparisons; SCHEME_WITHIN_CYCLIC for prior-history regressors (D093: the plain "
             "within-player shuffle is anticonservative and the kit now refuses it).  Row-level "
             "nulls are computed FOR CONTRAST ONLY and always reported beside the correct one.",
    "no_champion_fitting": "The champion is never refitted.  Only its stored forecast columns are "
                           "scored.",
}
print(json.dumps(PLAN, indent=1)[:4000])

hdr("5. writing the frozen artefacts")
extra = {"plan": PLAN, "half_life_selection": sel_log,
         "canonical_frame": CANON_FRAME,
         "train_seasons_for_selection": TRAIN_SEASONS, "eval_seasons": EVAL_SEASONS,
         "frozen_at_step": "s03_prereg, before any re-priced figure"}
h2 = RL.dump_spec(os.path.join(OUT, "_prereg.json"), extra=extra)
print("  _prereg.json written, sha256 = %s" % h2)

tw = RL.time_window_table_df()
tw.to_csv(os.path.join(OUT, "time_window_table.csv"), index=False)
print("  time_window_table.csv written (%d rows)" % len(tw))
print(tw.to_string())

# ------------------------------------------------------------------ REFERENCE_LADDER.md
md = []
md.append("# The canonical reference ladder\n")
md.append("**SHA-256 of the definition below: `%s`**\n" % h2)
md.append("Frozen by `s03_prereg.py` before any re-priced figure was computed. "
          "Implementation: `refladder.py`. Reproduce the hash with "
          "`refladder.ladder_hash()` after loading `_prereg.json`'s `canon` block.\n")
md.append("## Why this exists\n")
md.append("Every skill figure in this programme is a statement about a **pair** — a forecast and a "
          "reference — and the programme has been reporting them as statements about the forecast. "
          "Four instances are on the record: D090 (+46.4% vs +7.1% for one availability forecast), "
          "D093 (+0.22% vs +4.24%), D094 (minutes +3.71% vs −4.41%, an 8.12-point swing that forced "
          "a withdrawal), D099 (a headline inflated ~4x by a subset's SST). D069 ruled that such "
          "numbers cannot be rescaled and must be **re-run**. A re-run needs one fixed thing to run "
          "against. This is it.\n")
md.append("## The rungs\n")
md.append("| rung | what it is | prior-only construction |\n|---|---|---|")
md.append("| `R0_LEAGUE` | a league / base-rate constant | same-season league value over strictly "
          "earlier **dates** → previous season's league value → GRAND (named, counted, never in an "
          "evaluation set) |")
md.append("| `R1_PLAYER_EXPAND` | the player's own expanding prior mean | **this is the programme's "
          "incumbent reference** — the one D094 showed is beatable by 1.3–7.8%. It is on the ladder "
          "so every legacy figure has a named rung to sit on |")
md.append("| `R2_EWMA_TUNED` | a tuned EWMA of the player's own prior games | form, half-life and "
          "shrinkage **imported from D094's 15,048-cell grid**, not re-searched |")
md.append("| `R3_RATE_X_MINUTES` | a rate × minutes composite | EWMA(target per minute) × "
          "EWMA(minutes, half-life 2). **Degenerate for `minutes`** and returned as NaN there "
          "rather than silently duplicating R2 |")
md.append("| `R4_RICH_LOOKUP` | the player's own prior measurements of the target **and its "
          "components**, blended | walk-forward OLS on `{R0, R1, R2, R3, prior-minutes EWMA, "
          "prior-rate EWMA, prior-season player mean, log1p(n_prior)}`, coefficients fitted on "
          "seasons **strictly earlier** than the season being scored |")
md.append("\n**The canonical rung for re-pricing is `%s`.**\n" % RL.CANONICAL_RUNG)
md.append("## Per-target settings\n")
md.append("| target | mode | EWMA half-life | shrink toward | k | history minutes-floor | source |")
md.append("|---|---|---|---|---|---|---|")
for t in RL.TARGETS:
    c = RL.CANON[t]
    md.append("| `%s` | %s | %s | %s | %s | %s | %s |"
              % (t, c["mode"], c["half_life"], c["shrink"], c["k"], c["floor"], c["source"]))
md.append("\nThree of D094's findings are adopted wholesale rather than re-tested: EWMA beats SMA "
          "beats expanding on every measured target; shrinkage is weak and **never toward the "
          "league** — always toward the player's own prior season; and a realised-minutes floor on "
          "the history hurts monotonically, so the floor is fixed at 0 everywhere. The half-lives "
          "differ by a factor of 20 across targets (minutes 2, attempts 5, points 8, points-per-"
          "minute 40), which is itself the reason a single 'average to date' reference is wrong for "
          "all of them at once.\n")
md.append("## The denominator rule\n")
for line in PLAN["denominator_rule"]:
    md.append("- " + line)
md.append("\n## Time-window table (rungs **and** inference)\n")
md.append("| stage | ingredient | window consumed | verdict |\n|---|---|---|---|")
for a, b, c, d in RL.TIME_WINDOW_TABLE:
    md.append("| %s | %s | %s | %s |" % (a, b, c, d))
md.append("\n## How to reuse this\n")
md.append("```python\n"
          "import refladder as RL\n"
          "rungs, meta = RL.ladder(my_frame, 'points')      # any of pts/minutes/fga/ppm/reb/ast\n"
          "ref = rungs[RL.CANONICAL_RUNG].to_numpy()        # align on meta['frame'], not on the\n"
          "y   = RL.target_series(meta['frame'], 'points')  # caller's original index\n"
          "sst = float(((y[m] - y[m].mean())**2).sum())     # ONE denominator, fixed for every arm\n"
          "```\n")
md.append("The frame must carry `season`, `player_id`, a datetime column, `minutes`, and the "
          "target. Nothing else is required. `RL.assert_partition` and "
          "`RL.assert_season_disjoint` run inside `ladder()` and will raise rather than let a "
          "previous-season aggregate be used where seasons overlap in calendar time.\n")
with open(os.path.join(OUT, "REFERENCE_LADDER.md"), "w", encoding="utf-8") as fh:
    fh.write("\n".join(md))
print("  REFERENCE_LADDER.md written")
print("\nPREREGISTRATION COMPLETE.  No re-priced figure has been computed.")
