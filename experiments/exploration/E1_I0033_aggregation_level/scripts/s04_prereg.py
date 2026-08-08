"""S04 -- PREREGISTRATION.  Written and HASHED before a single comparison statistic exists.

Everything that follows in s05..s09 reads this file back and asserts the hash is unchanged.
Additions and drops after hashing are counted and reported, never silently absorbed.
"""
import hashlib, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import agg_base as ab

PREREG_TEXT = r"""
E1_I0033 AGGREGATION LEVEL -- PREREGISTERED COMPARISON LIST
===========================================================
Screen id      : E1_I0033_aggregation_level
Partition      : 2021-2024 ONLY.  2025 and 2026 are NEVER read, joined, plotted or described.
Scored seasons : 2022, 2023, 2024.  2021 is EXCLUDED from scoring in BOTH arms because BOTH
                 fold receipts declare degenerate:true / model_was_fitted:false /
                 cold_start_declared_constant_only:true for that fold.  The team arm's 2021
                 file is a single constant 82.0 across all 418 rows (nunique == 1).
Seed           : 20260809

REPRODUCTION BEFORE MEASUREMENT
-------------------------------
No new statistic is computed until two published anchors reproduce on bytes:
  A1  D104's team home-advantage contrast: +0.965090 points per game on 888 REGULAR-SEASON
      games, seasons 2021-2024, master_team.
  A2  D076's appeared player-game count: 13,879 over seasons 2022-2024 in the champion arm's
      obligation set.
If either fails, the screen halts and says so.

IDENTITY MAP -- WHY IT IS RECONSTRUCTED RATHER THAN READ
--------------------------------------------------------
The champion player arm's fold receipts BIND prediction_contract_v4 artifacts, but every one of
its 26,614 emitted row_uids (2021-2024) belongs to prediction_contract_v5's universe, which is
strictly larger (6,333 vs 5,563 rows in 2022).  prediction_contract_v5 has NO SIBLING MANIFEST:
check_manifest returns UNVERIFIABLE, and UNVERIFIABLE IS NOT A PASS.
Therefore the map row_uid -> (player_id, game_id, team_id) is RECONSTRUCTED by recomputing the
canonical key from cbs_obligation_key.py (OBLIGATION_KEY_ID cbs_obligation_key/1,
CANONICAL_KEY_FIELDS = (player_id, game_id, team_id)) over the cross product of
  * team-games from data/masters/master_team.parquet   (manifest: row-granular, USABLE_IF_FILTERED)
  * players from data/masters/master_player.parquet    (manifest: row-granular, USABLE_IF_FILTERED)
restricted to 2021-2024 on COLUMN VALUES.
The reconstruction is then CHECKED for exact agreement against prediction_contract_v4's
manifest-verified map on the rows the two share.  contract v5 is used for NOTHING that enters a
number; if it is opened at all it is only to report agreement, and that is labelled.

RESPONSE AND ROW SETS
---------------------
Response : TEAM POINTS in a team-game, master_team.pts.  One number per (game_id, team_id).
RS1 (HEADLINE) : season in {2022,2023,2024} AND season_type == "Regular Season" AND the team arm
                 emitted a forecast AND at least one champion player forecast exists for that
                 team-game.  Expected n ~ 1,392.
RS2            : the same but season_type == "Playoffs".  Reported SEPARATELY and never pooled
                 into a headline.  D104's reason is adopted: playoff home court is AWARDED to the
                 better seed, so the stratum is not exchangeable with the regular season.
SST            : computed ONCE on RS1 about its own unweighted mean and passed as an EXPLICIT
                 argument to every R2 (D101 rule D3).  No code path computes a subset's own SST.

DENOMINATOR DECLARATION (D099 / D101)
-------------------------------------
Every figure in the top-down-vs-bottom-up table shares: the SAME response (team points), the
SAME row set (RS1), the SAME SST, NO weighting anywhere, and NO base.  They are therefore
comparable to each other.  THEY ARE NOT COMPARABLE TO ANY PLAYER-LEVEL dR2 IN THIS LEDGER, and
no comparison to one is made.  Where a player-level and a team-level quantity must be set beside
each other, ONLY skill-against-a-matched-reference at each level is shown, and the text states
that the two responses differ.

FORECAST ARMS (all forecast TEAM POINTS on RS1)
-----------------------------------------------
A_TEAM              cbs_v12_team_oof_v2/attempt_001 pred_point.  Stored forecast, scored as-is.
                    NOTHING IS REFIT.  cbs_v12_team_oof/1 is PROVISIONAL_SUPERSEDED and unused.
B1_BOTTOMUP_AVAIL   sum over the team-game's champion rows of p_active_hat * pts_hat.
                    PRE-GAME KNOWABLE.  HEADLINE bottom-up arm.
B2_BOTTOMUP_RAW     sum over the team-game's champion rows of pts_hat, unweighted.
                    PRE-GAME KNOWABLE, deliberately naive.
B3_ORACLE_ROSTER    ***ORACLE***  sum of pts_hat over rows with REALISED appeared == 1.
                    USES THE REALISED ROSTER.  DIAGNOSTIC ONLY.  EXCLUDED FROM EVERY HEADLINE
                    AND FROM EVERY RANKING.
B4_BOTTOMUP_CAL     B1 after a WALK-FORWARD affine recalibration: intercept and slope fitted by
                    OLS of team points on B1 using STRICTLY EARLIER SEASONS ONLY.
C1_BLEND            w*A_TEAM + (1-w)*B1_BOTTOMUP_AVAIL, w chosen to minimise squared error on
                    STRICTLY EARLIER SEASONS ONLY, clipped to [0,1].
C2_PRORATE          B1 rescaled so the team-game total equals A_TEAM.  This is A_TEAM by
                    construction and is carried only to make that point explicit.

REFERENCES (matched, prior-history-only, team level)
----------------------------------------------------
R0_LEAGUE        expanding league mean of team points over STRICTLY EARLIER games.
R1_TEAM_EXPAND   the team's expanding mean over its STRICTLY EARLIER same-season games,
                 shrunk to R0 by k/(k+n_prior) with k fitted on strictly earlier seasons.
R2_TEAM_EWMA     the same with an EWMA half-life selected on STRICTLY EARLIER SEASONS from the
                 grid [1,2,3,5,8,12,20,40] games.
MATCHED REFERENCE FOR SKILL = R2_TEAM_EWMA.  All three rungs are published (D101 ruling 4: a
finding whose sign depends on the rung cannot be quoted as a bare number).

PRIMARY PREREGISTERED CELLS (14)
--------------------------------
P01  A_TEAM            vs B1_BOTTOMUP_AVAIL     THE CENTRAL TEST
P02  A_TEAM            vs R2_TEAM_EWMA
P03  B1_BOTTOMUP_AVAIL vs R2_TEAM_EWMA
P04  C1_BLEND          vs A_TEAM
P05  B3_ORACLE_ROSTER  vs B1_BOTTOMUP_AVAIL     ORACLE.  diagnostic only.
P06  B4_BOTTOMUP_CAL   vs B1_BOTTOMUP_AVAIL
P07  FT_COMPOSED       vs FT_FLAT               step 3
P08  FT_COMPOSED       vs BASE_NO_VENUE         step 3
P09  team points   : LEVEL_TEAM vs LEVEL_PLAYER (matched-construction EWMA, step 5)
P10  team FGA      : LEVEL_TEAM vs LEVEL_PLAYER
P11  team FTA      : LEVEL_TEAM vs LEVEL_PLAYER
P12  team FTM      : LEVEL_TEAM vs LEVEL_PLAYER
P13  team REB      : LEVEL_TEAM vs LEVEL_PLAYER
P14  team AST      : LEVEL_TEAM vs LEVEL_PLAYER
Fourteen cells, under D103 ruling 1's ~18-cell ceiling.  Anything else computed is EXPLORATORY,
is labelled EXPLORATORY, and carries no verdict.

STEP 5 MATCHED-CONSTRUCTION DETAIL (P09-P14)
--------------------------------------------
The estimator class is held FIXED and only the AGGREGATION LEVEL varies.  For a quantity Q:
  LEVEL_TEAM   = the team's EWMA of Q over its strictly earlier same-season team-games,
                 shrunk to the expanding league mean, half-life and k tuned on earlier seasons.
  LEVEL_PLAYER = sum over the team-game's pre-game-knowable candidate roster of
                 p_active_hat * (that player's EWMA of Q per appearance over their strictly
                 earlier same-season games, shrunk to the league per-appearance mean), with the
                 SAME half-life grid and the SAME tuning rule.
Both are scored against the SAME team-level response Q on the SAME rows with the SAME SST.
p_active_hat is the champion's own availability forecast, so no realised roster enters either.

STEP 3 FREE-THROW COMPOSITION
-----------------------------
D104 established: the venue effect is 97.6% free throws and specifically +1.087 ATTEMPTS with
accuracy contributing +0.4 percentage points.  So the POINTS value of the venue edge depends on
who shoots them.  Define, for a team-game,
    venue_fta_edge = (2*is_home - 1) * 0.5 * 1.087        (home +0.5435, away -0.5435)
    FT_COMPOSED    = base + beta * venue_fta_edge * ft_pct_prior(team)
    FT_FLAT        = base + beta * venue_fta_edge * ft_pct_prior(LEAGUE)
    BASE_NO_VENUE  = base
where ft_pct_prior is the team's FTM/FTA over its STRICTLY EARLIER same-season games shrunk to
the strictly-prior league rate, base is R2_TEAM_EWMA, and beta is fitted by OLS on STRICTLY
EARLIER SEASONS ONLY.  FT_FLAT and FT_COMPOSED differ ONLY by team-specific FT%.
D108 WARNING HONOURED: the opponent free-throw channel collapses to one degree of freedom, so
the MAIN EFFECTS (prior FT%, prior FTA rate, is_home) ARE IN THE BASE FROM THE START and the
composition is tested as an increment over a base that already carries them.  The spread across
teams of ft_pct_prior, and the points it implies, are reported whatever the significance is.

NULLS AND THEIR POWER
---------------------
N1  PAIRED BLOCK SIGN-FLIP on the per-row absolute-error difference, blocks = TEAM-SEASON.
    Carries every verdict.  Reported with null_mean and null_sd beside p (D103 ruling 2).
N1b the same with blocks = GAME.
N2  row-level sign-flip.  CONTRAST ONLY.  NEVER carries a verdict.  Published to give the
    inflation factor.
D108 IS HONOURED EXPLICITLY: the within-player cyclic shift is NOT USED anywhere in this screen.
Every candidate here varies at TEAM-GAME or BETWEEN-TEAM level, which a within-player rotation
preserves exactly, so the cyclic null would have no power at all.
POWER IS VERIFIED BY INJECTION BEFORE ANY NULL CARRIES A VERDICT.  A known constant is added to
one arm's forecast at sizes {0.05, 0.10, 0.25, 0.50, 1.00} points of MAE difference, and each
null must recover it.  A null that fails to detect a planted signal is reported as having no
power and its verdicts are withdrawn.

CONTROLS
--------
NEG1  NEGATIVE CONTROL.  A_TEAM's forecast is replaced by the forecast issued to a DIFFERENT,
      randomly chosen team playing on the SAME DATE.  The team-level advantage must vanish.
NEG2  NEGATIVE CONTROL.  The bottom-up sum is rebuilt from a randomly chosen OTHER team's
      candidate roster on the same date.  Must vanish.
PLACEBO  NO-OP.  The identity transform applied through the whole scoring path must reproduce
      the real statistic with maximum deviation EXACTLY 0.0.  A placebo that moves means the
      pipeline is not deterministic and the screen halts.
PERTURBATION CHECK  The negative controls must be VERIFIED TO ACTUALLY PERTURB: the fraction of
      rows whose forecast value changed is reported, and if it is not > 0.9 the control is
      declared vacuous (D093 K7) and discarded rather than cited.

DECISION RULES (hashed before any statistic)
--------------------------------------------
DR1  "TEAM LEVEL WINS FOR TEAM POINTS" iff MAE(A_TEAM) < MAE(B1_BOTTOMUP_AVAIL) AND N1 p < 0.05.
DR2  "THE LEVELS AGREE" iff N1 p >= 0.05 OR |MAE(A)-MAE(B1)| < 0.01 * MAE(R2_TEAM_EWMA).
DR3  "BOTTOM-UP WINS" iff MAE(B1) < MAE(A_TEAM) AND N1 p < 0.05.
DR4  GAP ATTRIBUTION, computed only if DR1 fires.  With G = MAE(B1) - MAE(A_TEAM):
       roster share      = (MAE(B1) - MAE(B3_ORACLE_ROSTER)) / G     [ORACLE-BASED, labelled]
       level-bias share  = (MAE(B1) - MAE(B4_BOTTOMUP_CAL))  / G
       residual share    = 1 - roster share - level-bias share, attributed jointly to error
                           compounding across ~10-14 forecasts and to per-player forecast
                           quality, which are separated by the variance accounting in s07 and
                           NOT by this arithmetic.
     Shares may exceed 1 or go negative; if they do that is reported, not clipped.
DR5  For P09-P14 the winner is the level with the lower MAE, and the cell is called DECIDED only
     if N1 p < 0.05.  Otherwise it is UNDECIDED, never "the levels agree".
DR6  Any comparison whose null fails the injection power check is reported as NOT ESTABLISHED,
     never as ABSENT (D108 ruling 4).

WHERE THIS SCREEN COULD HAVE CHEATED -- declared in advance
-----------------------------------------------------------
C-1  Summing only the players who actually appeared.  That is B3 and it is labelled ORACLE and
     excluded from every headline.  It is the single largest available cheat here.
C-2  Choosing the blend weight w or the EWMA half-life on the scored season.  Both are fitted on
     STRICTLY EARLIER SEASONS ONLY, and the 2022 fold, which has only 2021 available, is
     reported separately so a reader can see what the thinnest fit does.
C-3  Recalibrating B1's level using the scored season's mean.  B4 uses earlier seasons only.
C-4  Picking the reference rung that flatters the conclusion.  All three rungs are published.
C-5  Dropping the playoff stratum after seeing it.  It is excluded HERE, before any statistic,
     for D104's stated structural reason, and reported separately anyway.
C-6  Quietly using contract v5, which has no manifest, to define the roster.  The identity map
     is reconstructed from the canonical key instead and cross-checked against v4.
C-7  Comparing a team-level dR2 to a player-level one.  Prohibited by the denominator
     declaration above and not done.
"""


def main():
    h = hashlib.sha256(PREREG_TEXT.encode("utf-8")).hexdigest()
    out = {
        "screen_id": "E1_I0033_aggregation_level",
        "prereg_sha256": h,
        "seed": ab.SEED,
        "partition": list(ab.EXPLORATION_SEASONS),
        "scored_seasons": list(ab.SCORED_SEASONS),
        "n_primary_cells": 14,
        "primary_cells": ["P%02d" % i for i in range(1, 15)],
        "text": PREREG_TEXT,
    }
    with open(os.path.join(ab.OUT, "_prereg.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    with open(os.path.join(ab.OUT, "COMPARISONS_PRESELECTED.md"), "w", encoding="utf-8") as fh:
        fh.write("# COMPARISONS PRESELECTED -- E1_I0033_aggregation_level\n\n")
        fh.write("**sha256 of the preregistered text below: `%s`**\n\n" % h)
        fh.write("Hashed at write time, before any comparison statistic existed. Every "
                 "downstream script reads this file back and asserts the hash is unchanged; "
                 "additions and drops are counted in FINDINGS.json.\n\n")
        fh.write("```\n" + PREREG_TEXT + "\n```\n")
    print("PREREG sha256 = %s" % h)
    print("wrote _prereg.json and COMPARISONS_PRESELECTED.md")


def assert_unchanged():
    p = os.path.join(ab.OUT, "_prereg.json")
    d = json.load(open(p, encoding="utf-8"))
    h = hashlib.sha256(d["text"].encode("utf-8")).hexdigest()
    assert h == d["prereg_sha256"], "PREREG HASH MISMATCH -- the preregistration was edited"
    assert h == hashlib.sha256(PREREG_TEXT.encode("utf-8")).hexdigest(), \
        "PREREG TEXT IN s04_prereg.py NO LONGER MATCHES THE HASHED FILE"
    return d


if __name__ == "__main__":
    main()
