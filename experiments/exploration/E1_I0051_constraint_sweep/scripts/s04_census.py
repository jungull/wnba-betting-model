"""E1_I0051 -- s04.  THE CENSUS.

Every response in every screen under experiments/exploration/, classified against the PREREG §2
rule.  The classification of each row is a JUDGEMENT recorded together with the verbatim evidence
that supports it; the SCREEN LIST is enumerated from the filesystem, not typed, so no screen can be
silently omitted.

PREREG §2 rule:  a response is CONSTRAINED iff its components must sum to, or be bounded by,
something FIXED AT A HIGHER LEVEL -- determined independently of the components themselves.

  * player MINUTES sum to 200 + 25*n_OT.  FIXED BY THE RULES.  -> CONSTRAINED
  * player POINTS / ATTEMPTS / REBOUNDS sum to the team total, WHICH IS ITSELF THE OUTCOME.
    -> NOT CONSTRAINED.  Modelling them independently implies a total; it does not break a budget.
  * a SHARE response y_i / sum_j y_j sums to 1 by construction -> CONSTRAINED, but SELF-IMPOSED.
  * `p_active` over a roster: the realised roster size is a RANDOM VARIABLE (sd 1.0077, range
    6-12), not a budget -> NOT CONSTRAINED (soft).  Treated in AVAILABILITY_AS_CONSTRAINT.md.
  * a per-EVENT allocation (exactly one player is credited with each rebound) -> CONSTRAINED,
    budget exactly 1, fixed at a higher level.

NO NAME-BASED SELECTION.  Every screen id below is an explicit literal, and the literal list is
asserted against the directory enumeration; a mismatch in either direction HALTS.
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cs_base as B  # noqa: E402

pd.set_option("display.width", 250)
pd.set_option("display.max_rows", 300)

NA = "NOT-APPLICABLE"
VIO = "VIOLATED"
HON = "HONOURED"
ND = "NOT-DETERMINABLE"
NR = "NO-RESPONSE"

# screen | response (verbatim where short) | kind | what it sums to | fixed higher up? | class |
# published verdict on that response | evidence quote | exposure note
C = [
 # ---------------------------------------------------------------- E0
 ("E0_I0003_rebound_interaction", "DRB/ORB secure rate = secured / opportunities", "share",
  "the player's own opportunity count", "no", NA, "iterate-not-justified",
  "'+1 ORB opportunity to the 5 offense players, +1 DRB opportunity to the 5 defense players, and "
  "+1 secured to whichever specific player the event credits'", ""),
 ("E0_I0003_rebound_interaction", "per-event outcome (which of the 10 secures the rebound)",
  "probability", "exactly 1 rebound per event", "YES -- exactly one is credited", VIO,
  "null (the one opponent-context interaction tested was null)",
  "same quote: exactly one player is credited per event",
  "EXPOSURE NIL: the verdict is a null and a null that flips sign is still a null; E1_I0036 "
  "already re-levelled the rebound family and D111 survived"),
 ("E0_I0004_shot_location_allowance", "shot-level make/miss residual", "probability",
  "nothing -- the shooter is given", "no", NA, "iterate (narrowed to Restricted Area)", "", ""),
 ("E0_I0005_turnover_interaction", "turnovers_per_100_off_poss", "rate",
  "nothing -- denominator is the player's OWN on-court possessions", "no", NA,
  "kill (the interaction)", "'it is a possessions proxy, not a touches count'", ""),
 ("E0_I0006_usage_redistribution", "Top-1 teammate's share of total positive delta_usage",
  "share", "the sum of the positive deltas -- itself the sum", "no", NA, "kill",
  "placebo mean 0.539 EXCEEDS the real-absence mean 0.470", ""),
 ("E0_I0006_usage_redistribution", "usage_percentage (the underlying quantity)", "rate",
  "MEASURED: team-game sum 1.7016, sd 0.2341, cv 0.1376 -- no lattice", "no", NA, "kill",
  "measured in out/s00b.txt; fails PREREG S1a", ""),
 ("E0_I0008_height_differential", "offensive/defensive_rebound_percentage", "share",
  "available rebounds while on court", "no", NA, "lead, UNCONFIRMED pending rebuild", "", ""),
 ("E0_I0008_height_differential", "is_orb (per rebound event)", "probability",
  "exactly 1 rebound per event", "YES", VIO, "ambiguous null",
  "'is_orb here is measuring which team is credited'",
  "EXPOSURE NIL: ambiguous null; same reasoning as E0_I0003"),
 ("E0_I0009_additive_pressure", "turnovers_per_100_off_poss", "rate", "nothing", "no", NA,
  "keep-as-lead", "", ""),
 ("E0_I0010_positional_matchup", "points / rebounds / assists per 100 possessions", "rate",
  "nothing", "no", NA, "kill on all three", "", ""),
 ("E0_I0011_tendency_estimator", "MINUTES, raw per-game total", "level",
  "200 + 25*n_OT team-minutes", "YES -- BY THE RULES", VIO, "KILL (minutes)",
  "'minutes -- kill'; the screen has no roster-sum step anywhere",
  "EXPOSURE LOW: the published verdict on minutes is a kill"),
 ("E0_I0011_tendency_estimator", "points / rebounds / assists, raw per-game totals", "count",
  "the team total, which is itself the outcome", "no", NA, "keep-as-lead x3", "", ""),
 ("E0_I0012_layer3_noncollinear", "per-100-possession rate (pts/reb/ast)", "rate", "nothing",
  "no", NA, "29 of 30 killed, 1 caveated survivor",
  "'sum(player possessions) / (5 x team possessions) has median 0.992' -- a DATA check, not a "
  "constraint on the response", ""),
 ("E0_I0013_possession_volume", "raw counting stat (pts/reb/ast)", "count",
  "the team total, itself the outcome", "no", NA, "26 of 27 killed", "", ""),
 ("E0_I0014_residual_heterogeneity", "|residual| and residual^2 of points / MINUTES / FGA",
  "residual magnitude", "nothing -- an error magnitude has no budget", "no", NA,
  "mostly null; 4 usable leads",
  "the response is the error magnitude, not the quantity",
  "INHERITED ONLY: the minutes FORECAST it characterises violates the budget, but this screen's "
  "own response does not"),
 ("E0_I0015_points_skill_decomposition", "MINUTES (level)", "level", "200 + 25*n_OT",
  "YES -- BY THE RULES", VIO, "minutes skill +6.14% on the decision stratum",
  "'kind: level' for minutes; no roster-sum step anywhere",
  "EXPOSURE: the largest published positive minutes number in the programme"),
 ("E0_I0015_points_skill_decomposition", "points, FGA (levels); ppm/fpm/ppf (rates)",
  "level / rate", "the team total, itself the outcome", "no", NA,
  "points skill not distinguishable from zero", "", ""),
 ("E0_I0016_efficiency_predictors", "y_ppm = pts/minutes; y_ts; y_efg", "rate", "nothing", "no",
  NA, "3 clear family-wise, 2 of 3 fail their own kill test", "", ""),
 ("E0_I0017_shot_quality_efficiency", "y_ppm, y_ts, y_efg", "rate", "nothing", "no", NA,
  "null on the decision-relevant outcome", "", ""),
 ("E0_I0019_availability_forecast", "appeared (binary) / p_active", "probability",
  "the realised roster size -- a RANDOM VARIABLE (sd 1.0077, range 6-12)", "NO -- soft", NA,
  "p_active is genuinely good; honest headline +7.1%",
  "PREREG P1: a roster sum is not a budget",
  "TREATED SEPARATELY in AVAILABILITY_AS_CONSTRAINT.md"),
 ("E0_I0024_reb_ast_characterisation", "y_oreb, y_dreb, y_reb, y_ast, y_pts", "count",
  "the team total, itself the outcome", "no", NA, "consolidating null", "", ""),
 ("E0_I0028_degeneracy_sweep", "champion OUTPUT near-constancy on pts/MINUTES/FGA/p_active",
  "diagnostic", "n/a -- the statistic is output dispersion", "no", NA,
  "zero new degenerate regions",
  "no signed candidate statistic on minutes exists -> fails PREREG S3", ""),
 ("E0_I0029_freethrow_hurdle", "y_any_fta / y_fta_given / y_ftm_given / y_fta / y_ftm / y_pts",
  "probability / count", "the team total, itself the outcome", "no", NA,
  "player side closed; opponent side open",
  "'the decomposition is exactly mean-preserving'", ""),
 # ---------------------------------------------------------------- E1
 ("E1_I0004_efficiency_transfer", "VOID -- the directory declares itself ABANDONED", "-", "-",
  "-", NR, "VOID: 'MUST NOT be reused: any number, any contrast, any p-value, any verdict'",
  "ABANDONED.md", "EXCLUDED FROM EVERY COUNT"),
 ("E1_I0004_efficiency_transfer_v2", "MINUTES (y_minutes)", "level", "200 + 25*n_OT",
  "YES -- BY THE RULES", VIO, "KILL", "'responses | y_pts, y_minutes, y_fga, r_ppm, r_ppf'",
  "EXPOSURE LOW: killed on arithmetic, not on power"),
 ("E1_I0004_efficiency_transfer_v2", "y_pts, y_fga, r_ppm, r_ppf", "count / rate",
  "the team total, itself the outcome", "no", NA, "KILL", "", ""),
 ("E1_I0004_fga_forecast", "zone attempt counts; fg_pts; pts_total_box", "count",
  "the team total, itself the outcome", "no", NA, "attempts keep / points kill", "", ""),
 ("E1_I0004_rim_finishing", "Restricted-Area conversion", "probability", "nothing", "no", NA,
  "existence keeps; E0 magnitude killed", "", ""),
 # RECLASSIFIED from NOT-DETERMINABLE to VIOLATED after reading the SOURCE rather than the docs.
 # See NOTES.md section 4.  This is the ONE screen in the census whose violated response carries a
 # LIVE POSITIVE LEAD rather than a null.
 ("E1_I0004_shot_selection", "share_z -- share of the PLAYER'S OWN FGA in each of 5 zones",
  "share", "1, across 5 zones within the player-game", "YES -- SELF-IMPOSED (a share response)",
  VIO, "selection channel KEEP-AS-LEAD: beta +0.7743 row / +0.9193 cluster, R2 0.035209, "
  "player-game dR2 +0.0191, permutation p 0.0002 unadjusted AND family-wise (both at the 1/5001 "
  "resolution floor)",
  "analyze.py:200 'for z in ZONES:' -> a separate degree-1 np.polyfit per zone; "
  "dr2_playergame.py:69 'for z in ZONES:' -> five separate lstsq fits of z_att on 1 + S1*fga. "
  "A case-insensitive search of the whole directory for softmax|multinomial|dirichlet|simplex|"
  "renorm|normalis|normaliz|'sum to 1'|jointly|compositional returns ONE hit, the word "
  "'compositional' used descriptively in NOTES.md:167.  Nothing ties the five predicted shares "
  "to 1.",
  "**THE ONLY EXPOSED LIVE LEAD IN THE CENSUS.**  Five independent per-zone OLS fits with no "
  "constraint.  And it is provable rather than merely unchecked: the regressor OS_z is built as "
  "pre_z/pre_tot - lg_share_prior_z, so SUM_z OS_z = 0 by construction; the fitted increment to "
  "the share vector is SUM_z b_z*OS_z, which is identically zero ONLY IF ALL FIVE b_z ARE EQUAL. "
  "They are +0.774 / +0.653 / +0.556 / +0.325 / +0.563 -- spread by more than 2x.  THE FIVE "
  "FITTED SHARES PROVABLY DO NOT SUM TO 1.  NOT RE-MEASURED HERE (it needs the shotchart frame); "
  "recorded as the single highest-value follow-up."),
 ("E1_I0008_height_mismatch", "OREB% / DREB%", "share", "available rebounds while on court",
  "no", NA, "KILL at the Stage 1 gate", "", ""),
 ("E1_I0009_additive_pressure", "turnovers_per_100_off_poss", "rate", "nothing", "no", NA,
  "keep-as-lead", "", ""),
 ("E1_I0009_r2_rerun", "turnovers_per_100_off_poss", "rate", "nothing", "no", NA,
  "verdict holds, effect size weakens", "", ""),
 ("E1_I0011_split_alpha", "points, rebounds, assists", "count",
  "the team total, itself the outcome", "no", NA, "keep-as-lead x3", "", ""),
 ("E1_I0012_survivor_2021drop", "rebounds", "count", "the team total, itself the outcome", "no",
  NA, "KILL", "", ""),
 ("E1_I0013_tempo_redundancy", "raw assist count", "count", "the team total", "no", NA, "KILL",
  "'The response is the raw assist count, used as-is. Not centered.'", ""),
 ("E1_I0018_teammate_volume_channel", "y_ppm, y_spm, y_pps, y_ts, y_efg, points", "rate / count",
  "nothing / the team total", "no", NA, "tip-time survives but is unusable; prior partly survives",
  "", ""),
 ("E1_I0020_coldstart_tiering", "MINUTES", "level", "200 + 25*n_OT", "YES -- BY THE RULES", VIO,
  "operating rule adopted: 'cuts ... the minutes error by nearly half' on ~8% of rows",
  "'three targets -- points (pts), minutes, points-per-minute (ppm)'",
  "EXPOSURE: an OPERATING RULE rests on this; the rule is a per-player blend with no roster sum"),
 ("E1_I0020_coldstart_tiering", "points, ppm", "count / rate", "the team total / nothing", "no",
  NA, "same rule", "", ""),
 ("E1_I0021_heterogeneity_diagnostic", "y_ppm_floor = pts/minutes", "rate", "nothing", "no", NA,
  "heterogeneity not real; one usage x defence axis", "", ""),
 ("E1_I0022_optimal_simple_estimator", "MINUTES", "level", "200 + 25*n_OT", "YES -- BY THE RULES",
  VIO, "tuned EWMA ties the champion on minutes",
  "'four targets -- points, minutes, FGA, points-per-minute'",
  "EXPOSURE: this is the estimator every later minutes screen inherits"),
 ("E1_I0022_optimal_simple_estimator", "points, FGA, ppm, pts_per_fga, fga_per_min",
  "count / rate", "the team total / nothing", "no", NA, "champion beats it where it models", "",
  ""),
 ("E1_I0023_usage_defence_interaction", "y_ppm, y_spm, y_pts, TSA", "rate / count",
  "nothing / the team total", "no", NA, "interaction killed; a new lead raised", "", ""),
 ("E1_I0025_threshold_vs_refit", "points-per-minute; points", "rate / count",
  "nothing / the team total", "no", NA, "UNRESOLVED", "", ""),
 ("E1_I0026_detection_floor", "y_ppm", "rate", "nothing", "no", NA,
  "power failure established (56% of cells blind)", "", ""),
 ("E1_I0027_reference_ladder", "MINUTES (one of six targets)", "level", "200 + 25*n_OT",
  "YES -- BY THE RULES", VIO, "ranking unchanged; only 2 of 5 leads were commensurable",
  "'Six targets: points, minutes, attempts, points-per-minute, rebounds, assists.'",
  "EXPOSURE LOW: the screen's finding is about commensurability, not about a minutes effect"),
 ("E1_I0027_reference_ladder", "points, attempts, ppm, rebounds, assists", "count / rate",
  "the team total / nothing", "no", NA, "same", "", ""),
 ("E1_I0030_home_advantage_accounting", "team points; player points", "count / level",
  "the team total (team-level response); the minutes budget is used as a CLOSURE ARGUMENT",
  "no (points); YES (minutes, and it is honoured)", HON,
  "effect located in free throws; structurally unexploitable at player level",
  "'Minutes cannot hide it. A team plays 200 minutes in regulation, and overtime adds 25 more'; "
  "'team minutes are IDENTICAL for both teams in 970 of 970 games (200 + 25 per shared overtime)'",
  "THE ONE SCREEN THAT USED THE MINUTES BUDGET CORRECTLY -- to CLOSE a hiding place before "
  "measuring it"),
 ("E1_I0031_rapm_as_prior", "MINUTES", "level", "200 + 25*n_OT", "YES -- BY THE RULES", VIO,
  "mostly null; worth ~1/3 of a percentage point",
  "'four targets, pts, minutes, fga, ppm'",
  "EXPOSURE LOW: null verdict; also the only screen with all 32 within-entity-null exposed cells "
  "(E1_I0040), none of them a flip"),
 ("E1_I0031_rapm_as_prior", "pts, fga, ppm", "count / rate", "the team total / nothing", "no",
  NA, "same", "", ""),
 ("E1_I0032_aggregate_stack", "MINUTES", "level", "200 + 25*n_OT", "YES -- BY THE RULES", VIO,
  "partially established, commercially null",
  "'points, minutes, attempts, points-per-minute'",
  "EXPOSURE LOW: 'not one of those 947 rows is in the decision stratum. Zero.'"),
 ("E1_I0032_aggregate_stack", "points, attempts, ppm", "count / rate",
  "the team total / nothing", "no", NA, "same", "", ""),
 ("E1_I0032_aggregate_stack", "p_active (binary, Brier)", "probability",
  "the realised roster size -- a random variable", "NO -- soft", NA, "same", "",
  "TREATED in AVAILABILITY_AS_CONSTRAINT.md"),
 ("E1_I0033_aggregation_level", "TEAM POINTS in a team-game (master_team.pts)", "count",
  "n/a -- this IS the team total", "no", HON,
  "team level wins on all six quantities; bottom-up penalty measured",
  "'The quantities that are allocations of a shared, fixed team budget -- shot attempts out of "
  "~200 team minutes and ~80 possessions -- do not [survive summing], because modelling ten "
  "players separately throws away the constraint'",
  "THE SCREEN THAT DISCOVERED THE CONSTRAINT.  It measured it rather than violating it."),
 ("E1_I0034_redistribution", "MINUTES (the LEVEL, not Delta)", "level", "200 + 25*n_OT",
  "YES -- BY THE RULES", VIO,
  "redistribution ESTABLISHED for minutes on large absences (+1.82% vs champion)",
  "'a team's trailing-form minutes do not sum to 200 -- they sum to 199 when everyone is healthy "
  "and to 250 when three rotation players are out'; 'Fix the trailing-form arithmetic before "
  "anything else. ... This is the same class of defect as D111 ruling 3'",
  "**THE VIOLATION IS SELF-DECLARED AND UNREPAIRED.**  The screen names it, quantifies it at 250 "
  "against 200, attributes it to D111 ruling 3, and does not fix it."),
 ("E1_I0034_redistribution", "FGA, points (levels)", "count",
  "the team total, itself the outcome", "no", NA, "points CLOSED negative", "", ""),
 ("E1_I0035_availability_sum", "p_active as a probability forecast of appearance", "probability",
  "the realised roster size -- a RANDOM VARIABLE", "NO -- soft", NA,
  "defect confirmed and anatomised; no repair enacted",
  "'the model expects 10.34 players to take the floor when 9.40 actually do'",
  "TREATED IN FULL in AVAILABILITY_AS_CONSTRAINT.md"),
 ("E1_I0035_availability_sum", "exposure allocation of 200 team-minutes", "share",
  "200 team-minutes", "YES -- BY THE RULES", HON,
  "the producer renormalises, so a uniform rescaling cancels exactly",
  "'it hands out a fixed 200 team-minutes in proportion to p_active x expected minutes, so any "
  "uniform error in p_active divides out exactly'",
  "HONOURED BY THE PRODUCER.  This is the one place in the programme where the 200-minute budget "
  "is actually enforced, and it is enforced in shipping code rather than in a screen."),
 ("E1_I0035_availability_sum", "team points (master_team.pts)", "count", "n/a", "no", NA,
  "same", "", ""),
 ("E1_I0036_level_artefact_sweep", "y_oreb and the D097 family, re-levelled to team-game",
  "count", "the team total, itself the outcome", "no", HON,
  "level-artefact hypothesis NOT SUPPORTED; the negative record survives",
  "'an offensive rebound is an allocation of a shared budget: exactly one player collects each "
  "one. D111's rule says allocations of a shared budget do not survive aggregation from below'",
  "HONOURED: it re-levelled to the aggregation the constraint implies and measured the result"),
 ("E1_I0037_mde_audit", "none -- a methods audit of MDE80", "-", "-", "-", NR,
  "the claim is false as stated, true in a weaker form", "", ""),
 ("E1_I0038_within_entity_null_audit", "none -- a meta-audit of 1,999 census cells", "-", "-",
  "-", NR, "survives in bulk, not intact: 83 of 1,580 exposed", "", ""),
 ("E1_I0039_stacking", "MINUTES", "level", "200 + 25*n_OT", "YES -- BY THE RULES", VIO,
  "NULL on the bettable population: all 20 decision-stratum cells NOT ESTABLISHED",
  "'Responses: minutes, pts.'",
  "EXPOSURE LOW: every decision-stratum cell is already a null"),
 ("E1_I0039_stacking", "pts", "count", "the team total", "no", NA, "same", "", ""),
 ("E1_I0040_audit_extension", "none -- a meta-audit of 30 screens", "-", "-", "-", NR,
  "115 of 2,671 exposed programme-wide, zero flips", "", ""),
 ("E1_I0041_tstat_family_audit", "none -- a methods audit of a t -> dR2 conversion", "-", "-",
  "-", NR, "D103 corrected, conclusion strengthened", "", ""),
 ("E1_I0042_redistribution_replication", "MINUTES", "level", "200 + 25*n_OT",
  "YES -- BY THE RULES", VIO,
  "sign replicates (+1.774% frozen), size does not (0.55x its floor); threshold rule KILLED",
  "'Responses: minutes and pts, and they are NEVER compared to each other'; it reproduces "
  "E1_I0034's 198.96 / 201.08 / 201.50 / 191.44 / 184.02 accounting exactly",
  "**INHERITS E1_I0034'S UNREPAIRED VIOLATION.**  It reproduced the 250-against-200 arithmetic and "
  "did not repair it either."),
 ("E1_I0042_redistribution_replication", "pts", "count", "the team total", "no", NA,
  "points cells all negative", "", ""),
 ("E1_I0043_opponent_defence", "y_ppm", "rate", "nothing", "no", NA,
  "alive as measurement, dead as corroboration", "", ""),
 ("E1_I0044_broken_nulls_and_composites", "inherited residual magnitudes", "residual magnitude",
  "nothing", "no", NA, "kills mostly stand; 0 of 35 survive on the clean window", "", ""),
 ("E1_I0045_roster_currency", "appeared (Brier)", "probability", "the realised roster size",
  "NO -- soft", NA, "NOT ESTABLISHED; model hygiene, not a commercial gain", "",
  "TREATED in AVAILABILITY_AS_CONSTRAINT.md"),
 ("E1_I0045_roster_currency", "exposure misallocation in team-minutes", "share",
  "200 team-minutes", "YES -- BY THE RULES", HON, "misallocation 8.912 -> 2.438 min",
  "'and changed the allocation by literally zero' (of the uniform arm)",
  "HONOURED: measured against the 200-minute budget the producer enforces"),
 ("E1_I0046_allocation", "R1_s_pts / R2_s_min / R3_s_fga = y_i / SUM_j y_j", "share",
  "1, within the team-game", "YES -- SELF-IMPOSED by conditioning on the realised total", HON,
  "allocation forecastable; 3 of 4 candidates flip sign under the constraint",
  "'every share sums to 1 within its team-game to < 1e-12', asserted on real and synthetic data",
  "THE REFERENCE SCREEN.  It created its own constraint and honoured it."),
 ("E1_I0047_ceiling_validity", "y_reb / y_oreb / y_dreb / y_ast / y_pts as recorded per cell",
  "count", "the team total, itself the outcome", "no", NA,
  "all 213 ceilings safe; none reopens", "", ""),
 ("E1_I0048_shipped_roster_path", "none -- a code/provenance audit", "-", "-", "-", NR,
  "closed; repaired in production 2026-08-06", "", ""),
 ("E1_I0049_benchmark_constants", "y_pts; y_ppm; fg_pts", "count / rate",
  "the team total / nothing", "no", NA,
  "arithmetic correct, vocabulary wrong; no killed cell reopens", "", ""),
 ("E1_I0050_queue_typeI", "none stated -- the screen is at s00 only", "-", "-", "-", ND,
  "no verdict exists",
  "the directory contains no markdown at all and states no response",
  "NOT-DETERMINABLE because the screen is incomplete, not because the evidence is ambiguous"),
 ("AUDIT_baseline_provenance", "none -- a repo-wide provenance audit", "-", "-", "-", NR,
  "defect confirmed, multiple instances", "", ""),
 ("AUDIT_SCREEN_INTEGRITY", "none -- an audit of two known defects", "-", "-", "-", NR,
  "clean; no verdict downgraded", "", ""),
 ("MEASURE_F1_m13_fitpool", "M13's translation residual distribution", "residual distribution",
  "nothing", "no", NA, "verdict survives", "", ""),
 ("MANIFEST_REMEDIATION", "none -- a manifest classification plan", "-", "-", "-", NR,
  "plan only; no new contamination", "", ""),
 ("IDEATION_QUEUE", "none -- a queue, not a screen", "-", "-", "-", NR, "n/a", "", ""),
 ("_screen_kit", "none -- shared machinery, NOT MODIFIED BY THIS SCREEN", "-", "-", "-", NR,
  "n/a", "", ""),
 # ---- TWO SCREENS THAT DID NOT EXIST WHEN THIS SCREEN'S CENSUS SWEEP BEGAN.  Both were created
 # by SIBLING AGENTS RUNNING CONCURRENTLY and were caught only because the census enumerates the
 # directory rather than trusting a typed list.  Neither is read for its verdict (they have none
 # yet); both are recorded so the census is honest about its own currency.
 ("E1_I0052_identity_key_divergence", "none stated -- an identity/key provenance audit", "-", "-",
  "-", NR, "IN PROGRESS at the time of this census -- no verdict document exists",
  "directory contains run logs and CSVs, no verdict markdown",
  "CONCURRENT SIBLING.  Not read for a verdict."),
 ("E1_I0053_minutes", "R1_min (MINUTES, level) and R2_smin (minutes share)", "level / share",
  "200 + 25*n_OT; and 1", "YES -- BY THE RULES", HON,
  "IN PROGRESS at the time of this census -- PREREG.md is hashed, no VERDICT exists yet",
  "its PREREG.md carries RAW and PROJ arms on both responses and the same 3,167-row "
  "decision-stratum clean window",
  "**DIRECT COLLISION WITH THIS SCREEN'S RE-MEASUREMENT.**  A sibling agent independently selected "
  "MINUTES as the response worth projecting.  That is corroboration of this screen's selection "
  "rule and it is also a duplication.  E1_I0053 is the DEDICATED minutes screen and is more "
  "thorough on that response than this sweep is; where the two disagree, prefer E1_I0053.  See "
  "VERDICT.md and DEFECTS.md D-02."),
 ("E1_I0051_constraint_sweep", "M_level_min (MINUTES, level); S_share_min (share)",
  "level / share", "200 + 25*n_OT; and 1", "YES -- BY THE RULES", HON,
  "this screen -- see VERDICT.md",
  "measured: T_min lands on the 25-lattice on 1,776 of 1,776 team-games, max residual 0.066667",
  "SELF-REPORTED so the census is complete"),
]

cols = ["screen", "response", "response_kind", "components_sum_to", "fixed_at_higher_level",
        "classification", "published_verdict_on_this_response", "evidence_quote", "exposure_note"]
cen = pd.DataFrame(C, columns=cols)

B.hdr("CENSUS INTEGRITY -- the screen list is ENUMERATED, not typed")
dirs = sorted([n for n in os.listdir(B.EXP)
               if os.path.isdir(os.path.join(B.EXP, n))])
listed = sorted(cen["screen"].unique())
missing = [x for x in dirs if x not in listed]
extra = [x for x in listed if x not in dirs]
print("  directories under experiments/exploration : %d" % len(dirs))
print("  distinct screens in the census            : %d" % len(listed))
print("  in the directory but NOT in the census    : %s" % (missing or "NONE"))
print("  in the census but NOT a directory         : %s" % (extra or "NONE"))
assert not missing, "CENSUS INCOMPLETE -- these screens have no census row: %s" % missing
assert not extra, "CENSUS HAS PHANTOM SCREENS: %s" % extra

B.hdr("THE COUNTS -- NOT-APPLICABLE IS REPORTED FIRST, AS THE PREREG REQUIRES")
scr = cen[~cen["classification"].isin([NR])]
by_screen = {}
for s, g in cen.groupby("screen"):
    cl = set(g["classification"])
    if cl == {NR}:
        by_screen[s] = NR
    elif VIO in cl:
        by_screen[s] = VIO
    elif HON in cl:
        by_screen[s] = HON
    elif ND in cl:
        by_screen[s] = ND
    else:
        by_screen[s] = NA
sc = pd.Series(by_screen)
print("\n  BY RESPONSE ROW (n = %d rows):" % len(cen))
print(cen["classification"].value_counts().to_string())
print("\n  BY SCREEN (n = %d directories), worst classification per screen:" % len(sc))
print(sc.value_counts().to_string())
print("\n  screens classified VIOLATED:")
for s in sorted(sc[sc == VIO].index):
    print("    - %s" % s)
print("\n  screens classified HONOURED:")
for s in sorted(sc[sc == HON].index):
    print("    - %s" % s)
print("\n  screens classified NOT-DETERMINABLE:")
for s in sorted(sc[sc == ND].index):
    print("    - %s" % s)

cen["screen_level_classification"] = cen["screen"].map(by_screen)
cen.to_csv(os.path.join(B.OUT, "CONSTRAINT_CENSUS.csv"), index=False)

B.hdr("EVERY VIOLATED ROW, WITH ITS RESPONSE")
v = cen[cen["classification"] == VIO][["screen", "response", "published_verdict_on_this_response"]]
print(v.to_string(index=False))

B.dump("s04", dict(prereg_sha=B.prereg_sha(), n_rows=len(cen), n_screens=len(sc),
                   by_screen=by_screen,
                   counts_by_row=cen["classification"].value_counts().to_dict(),
                   counts_by_screen=sc.value_counts().to_dict()))
print("\nwrote CONSTRAINT_CENSUS.csv  (%d response rows over %d screens)" % (len(cen), len(sc)))
B.hdr("DONE s04")
