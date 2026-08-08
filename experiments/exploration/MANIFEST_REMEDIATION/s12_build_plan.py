# -*- coding: utf-8 -*-
"""Build REMEDIATION_PLAN.json and REMEDIATION_PLAN.md from the code-traced classifications.

Every entry with confidence HIGH/MEDIUM carries a quoted evidence file:line that was READ.
Entries the sweep did not open carry granularity UNDETERMINED and confidence NONE -- these are
declared, not guessed (constraint: an honest UNDETERMINED beats a confident guess).
"""
import json, os, collections

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
OUT = os.path.join(ROOT, "experiments", "exploration", "MANIFEST_REMEDIATION")

inv = {r["artifact"]: r for r in json.load(open(os.path.join(OUT, "inventory_shared68.json"), encoding="utf-8"))}

# ---------------------------------------------------------------------------
# CLASSIFICATIONS. granularity: ROW | ARTIFACT | UNDETERMINED
# holdout_risk: NONE (build hard-filters to 2021-2024 or is capture-timestamped)
#             | PARTITION_ONLY_LOOKAHEAD (pools within 2021-2024, never touches 2025/26)
#             | SPANS_HOLDOUT (file contains/embeds 2025-2026 derived values)
#             | UNKNOWN
# ---------------------------------------------------------------------------
C = {}

def add(art, gran, conf, holdout, evidence, remedy, cost, note, lead=None, program=None):
    C[art] = dict(proposed_asof_granularity=gran, confidence=conf, holdout_risk=holdout,
                  evidence=evidence, remedy=remedy, estimated_cost=cost, note=note,
                  lead=lead, program=program)

E = lambda f, l, t: {"file": f, "line": l, "quote": t}

# ---- exploration frames -----------------------------------------------------
add(r"experiments\exploration\E0_I0011_tendency_estimator\frame.parquet", "ARTIFACT", "HIGH",
    "PARTITION_ONLY_LOOKAHEAD",
    [E("experiments/exploration/E0_I0011_tendency_estimator/build_frame.py", 109,
       'h = sel.loc[sel["is_home"] == 1, s].mean()   # HOME_MULT pooled over ALL of 2021-2022'),
     E("experiments/exploration/E0_I0011_tendency_estimator/build_frame.py", 115,
       'MEAN_POSS = float(sel["game_poss"].mean())   # single pooled constant'),
     E("experiments/exploration/E0_I0011_tendency_estimator/build_frame.py", 161,
       'df["prior_" + s] = df["prior_" + s].fillna(float(sel[s].mean()))  # pooled fallback'),
     E("experiments/exploration/E0_I0011_tendency_estimator/build_frame.py", 154,
       'prior["season"] = prior["season"] + 1   # LEGITIMATE season offset: full-season mean of S applied to S+1'),
     E("experiments/exploration/E0_I0011_tendency_estimator/build_frame.py", 33,
       'tm = tm[tm["season"].isin(PARTITION)].copy()   # FILTER-POINT before any pooling')],
    "manifest-only", "5 min",
    "Pooled HOME_MULT/MEAN_POSS/fallback means are estimated on the SELECTION seasons 2021-2022 and "
    "frozen. That is a genuine pooled step, so the file is NOT row-granular. It is also filtered to "
    "the partition BEFORE any pooling, so no 2025/2026 value can reach a row. The prior-season merge "
    "at line 152-154 uses the season+1 offset and is legitimate.", lead="I0011", program="exploration")

add(r"experiments\exploration\E1_I0011_split_alpha\frame.parquet", "ARTIFACT", "HIGH",
    "PARTITION_ONLY_LOOKAHEAD",
    [E("experiments/exploration/E1_I0011_split_alpha/build_frame.py", 83,
       'med = mp.groupby("season")["game_date"].transform("median")  # season-pooled split point'),
     E("experiments/exploration/E1_I0011_split_alpha/build_frame.py", 55,
       'mp = mp[mp["season"].isin(PARTITION)].copy()   # FILTER-POINT (immediately after load)'),
     E("experiments/exploration/E1_I0011_split_alpha/build_frame.py", 76,
       'mp["std_minutes"] = (g["minutes"].shift(1)... expanding(1).mean())  # strictly prior, clean')],
    "manifest-only", "5 min",
    "Every predictor column is strictly-prior (shift(1)+expanding, cumcount). The ONLY pooled step is "
    "the `half` column: a within-season game_date median over the whole season. That is a within-"
    "partition look-ahead, not holdout contamination -- the file is filtered to 2021-2024 at line 55 "
    "before the median is taken. Declaring 'row' would be false because of `half`.",
    lead="I0011", program="exploration")

add(r"experiments\exploration\E1_I0004_rim_finishing\_validate_sandbox\frame.parquet", "ARTIFACT", "HIGH",
    "PARTITION_ONLY_LOOKAHEAD",
    [E("(sha256 comparison)", 0,
       "BYTE-IDENTICAL to E1_I0011_split_alpha/frame.parquet, sha256 311BFDA27F6D97EF...")],
    "manifest-only", "2 min",
    "Not an independently built artifact: a byte-identical copy of the E1_I0011 frame placed in the "
    "rim-finishing baseline-validation sandbox. Inherits that file's classification exactly.",
    lead="I0004", program="exploration")

add(r"experiments\exploration\E1_I0008_height_mismatch\frame.parquet", "ARTIFACT", "HIGH",
    "PARTITION_ONLY_LOOKAHEAD",
    [E("experiments/exploration/E1_I0008_height_mismatch/build_frame.py", 117,
       'What DOES apply: the minutes WEIGHTS are full-season, so the aggregate is not strictly '
       'pregame-observable at game t.   [the script says so itself]'),
     E("experiments/exploration/E1_I0008_height_mismatch/build_frame.py", 133,
       'season_minutes.groupby(["team_id","season"])["minutes"].rank(...)  # top-8 by TOTAL SEASON minutes'),
     E("experiments/exploration/E1_I0008_height_mismatch/build_frame.py", 90,
       'mp = mp[mp["season"].isin(EXPLORATION_SEASONS)].copy()  # FILTER-POINT')],
    "manifest-only", "5 min",
    "Opponent roster/rotation height aggregates use full-season minutes weights and a top-8 rank on "
    "total season minutes -- both read later games in the same season. The script documents this "
    "itself at line 114-118. Lead I0008 is KILLED, so this is housekeeping.",
    lead="I0008", program="exploration")

for a in [r"experiments\exploration\E1_I0011_split_alpha\grid_metrics.parquet",
          r"experiments\exploration\E1_I0004_rim_finishing\_validate_sandbox\grid_metrics.parquet"]:
    add(a, "ARTIFACT", "HIGH", "PARTITION_ONLY_LOOKAHEAD",
        [E("experiments/exploration/E1_I0011_split_alpha/grid.py", 157,
           'met.to_parquet(HERE + r"\\grid_metrics.parquet", index=False)'),
         E("(lineage)", 0, "built from E1_I0011 frame.parquet, which is artifact-granular; "
           "grid metrics are themselves aggregates over the whole evaluation set")],
        "manifest-only", "5 min",
        "A grid of evaluation METRICS, each computed by pooling over the whole evaluation set. "
        "Artifact-granular by construction as well as by inheritance. The two paths are byte-identical "
        "(sha256 D6580165...).", lead="I0011", program="exploration")

# ---- I0009 / I0005 pressure frames -----------------------------------------
LOO_EV = lambda f: [
    E(f, 163, '# 4a. E0-comparable LOO tendency (hindsight; NOT pregame-observable)'),
    E(f, 167, 'tov["loo_poss"] = tov["season_poss"] - tov["realised_off_possessions"]'),
    E(f, 116, 'tot = (team_game.groupby(["team_id","season"]).agg(s_poss=("def_poss","sum"), ...))'),
    E("experiments/exploration/E0_I0009_additive_pressure/pressure_lib.py", 39,
      'lg = team_game.groupby("season").agg(p=("def_poss","sum"), t=("def_tov","sum"), ...)'),
    E("experiments/exploration/E0_I0009_additive_pressure/pressure_lib.py", 55,
      'self.anchor[(team, season)] = self.league_mean[season]   # CURRENT season full-season mean'),
    E("experiments/exploration/E0_I0009_additive_pressure/pressure_lib.py", 97,
      'anchor = self.league_pts_mean[season]   # defrtg always shrunk to the current season league mean'),
]
for a, f, lead in [
    (r"experiments\exploration\E1_I0009_additive_pressure\player_game_analysis.csv",
     "experiments/exploration/E1_I0009_additive_pressure/build_data.py", "I0009"),
    (r"experiments\exploration\E0_I0009_additive_pressure\player_game_analysis.csv",
     "experiments/exploration/E0_I0009_additive_pressure/build_data.py", "I0009"),
    (r"experiments\exploration\E0_I0005_turnover_interaction\player_game_analysis.csv",
     "experiments/exploration/E0_I0005_turnover_interaction/build_data.py", "I0005"),
]:
    add(a, "ARTIFACT", "HIGH", "PARTITION_ONLY_LOOKAHEAD", LOO_EV(f), "manifest-only", "10 min",
        "TWO independent season-pooling steps. (1) The `*_loo` columns are whole-season-minus-this-game "
        "leave-one-out -- they read LATER games in the same season; the script labels them 'hindsight; "
        "NOT pregame-observable'. (2) The `*_pregame` columns, despite the name, are shrunk toward an "
        "anchor that is the CURRENT season's full-season league mean whenever no prior season exists, "
        "and ALWAYS for defrtg. Both are confined to 2021-2024 by hard column-value asserts, so this is "
        "within-partition look-ahead, not holdout contamination. The file must not be manifested 'row'.",
        lead=lead, program="exploration")

for a, f, lead in [
    (r"experiments\exploration\E1_I0009_additive_pressure\team_game_defense.csv",
     "experiments/exploration/E1_I0009_additive_pressure/build_data.py", "I0009"),
    (r"experiments\exploration\E0_I0009_additive_pressure\team_game_defense.csv",
     "experiments/exploration/E0_I0009_additive_pressure/build_data.py", "I0009"),
]:
    add(a, "ARTIFACT", "HIGH", "PARTITION_ONLY_LOOKAHEAD",
        [E(f, 116, 'tot = (team_game.groupby(["team_id","season"]).agg(s_poss=("def_poss","sum"), ...))'),
         E(f, 120, 'loo_poss = team_game["s_poss"] - team_game["def_poss"]'),
         E("experiments/exploration/E0_I0009_additive_pressure/pressure_lib.py", 97,
           'anchor = self.league_pts_mean[season]'),
         E(f, 109, 'assert set(team_game["season"].unique()).issubset(set(EXPLORATION_SEASONS))')],
        "manifest-only", "10 min",
        "Same two pooling steps as its player-level sibling: season LOO columns plus a current-season "
        "full-season league anchor in the shrinkage. Partition-asserted on column values.",
        lead=lead, program="exploration")

# ---- player_program pipeline -----------------------------------------------
add(r"experiments\player_program\projected_exposure_v1\team_possession_prior_v1.parquet", "ROW", "HIGH",
    "NONE",
    [E("experiments/player_program/build_projected_exposure.py", 296,
       'same = [v for (d, s, v) in h if d < r.game_date and s == r.season]'),
     E("experiments/player_program/build_projected_exposure.py", 297,
       'prev = [v for (d, s, v) in h if d < r.game_date and s == r.season - 1]'),
     E("experiments/player_program/build_projected_exposure.py", 280,
       'league_prior_mean = (by_date["sum"].cumsum().shift(1) / by_date["count"].cumsum().shift(1))'),
     E("experiments/player_program/build_projected_exposure.py", 268,
       'sched = base[["game_id","team_id","game_date","season"]]  # identity columns ONLY from base')],
    "manifest-only", "5 min",
    "CLEAN. Every pace estimate uses a strict d < r.game_date cutoff; the league fallback is a "
    "cumsum().shift(1) by date. Crucially it does NOT inherit the cbs_v15 prediction contamination: "
    "build_pace() takes only game_id/team_id/game_date/season from `base`, never a predicted value. "
    "Its other input, possessions_raw_v2, is per-game derived. This is the highest-priority item in "
    "the sweep (3 PASSED nodes) and it is safe.", program="player_program")

add(r"experiments\player_program\projected_exposure_v1\projected_player_possessions_v1.parquet",
    "ARTIFACT", "HIGH", "SPANS_HOLDOUT",
    [E("experiments/player_program/build_projected_exposure.py", 190,
       'for f in sorted(PRED_DIR.glob("predictions__p_active__*.parquet"))  # ALL seasons incl. 2025/2026'),
     E("experiments/player_program/build_projected_exposure.py", 238,
       'base["raw_expected_minutes"] = base["p_active"] * base["e_minutes_given_active"]'),
     E("experiments/cbs_v15_player_oof_v5/attempt_001/predictions__p_active__2021.parquet.manifest.json", 4,
       '"asof_granularity": "artifact"   [the INPUT declares artifact granularity]')],
    "manifest-only", "15 min",
    "INHERITANCE. Every allocated minute is a function of raw_expected_minutes = p_active x "
    "e_minutes_given_active, both read from cbs_v15_player_oof_v5 prediction files whose OWN manifests "
    "declare asof_granularity='artifact'. The glob concatenates all seasons 2021-2026 into one file. "
    "Weakest-link rule: this artifact is artifact-granular. MITIGATING (do not lose this): each "
    "per-season prediction file was fit only on STRICTLY PRIOR seasons (the 2024 file's manifest says "
    "fit_seasons [2021,2022,2023]), so a 2021 row did not see 2026. The binary row/artifact vocabulary "
    "cannot express that; see the convention decision in group 3.", program="player_program")

add(r"experiments\player_program\projected_exposure_v1\projected_team_rotations_v1.parquet",
    "ARTIFACT", "HIGH", "SPANS_HOLDOUT",
    [E("experiments/player_program/build_projected_exposure.py", 627,
       'teams.to_parquet(OUT / "projected_team_rotations_v1.parquet", index=False)'),
     E("experiments/player_program/build_projected_exposure.py", 238,
       'base["raw_expected_minutes"] = base["p_active"] * base["e_minutes_given_active"]')],
    "manifest-only", "10 min",
    "Team-level roll-up of the same allocation; identical inheritance from the cbs_v15 predictions.",
    program="player_program")

add(r"experiments\player_program\turnover_targets_v1\player_turnover_targets_v1.parquet", "ROW", "HIGH",
    "NONE",
    [E("experiments/player_program/build_turnover_targets.py", 108,
       'expo = long.groupby(["game_id","offense_team_id","player_id"]).size()  # keyed on game_id'),
     E("experiments/player_program/build_turnover_targets.py", 128,
       'tot = pa.groupby(["game_id","turnover_team_id","attributed_player_id"]).size()'),
     E("experiments/player_program/build_turnover_targets.py", 150,
       'players["turnovers_per_100_off_poss"] = 100.0 * turnovers / realised_off_possessions')],
    "manifest-only", "5 min",
    "CLEAN. A realised-OUTCOME target artifact. EVERY aggregation is keyed on game_id -- there is no "
    "cross-game, cross-season or population-level step anywhere in the file. Each row's value is that "
    "player-game's own realised turnovers over its own realised possessions, bounded by its own date.",
    program="player_program")

add(r"experiments\player_program\turnover_targets_v1\team_turnover_reconciliation_v1.parquet", "ROW", "HIGH",
    "NONE",
    [E("experiments/player_program/build_turnover_targets.py", 162,
       'team_tot = T_team.groupby(["game_id","turnover_team_id"]).size()'),
     E("experiments/player_program/build_turnover_targets.py", 189,
       'players.groupby(["game_id","team_id"])["turnovers"].sum()')],
    "manifest-only", "5 min",
    "CLEAN, same reasoning: strictly game-keyed reconciliation of realised team turnovers.",
    program="player_program")

add(r"experiments\player_program\turnover_p1_v1\turnover_p1_predictions_intrinsic.parquet",
    "ARTIFACT", "HIGH", "SPANS_HOLDOUT",
    [E("experiments/player_program/run_turnover_p1.py", 77,
       '# advance history AFTER predicting the whole day   [arms A-D are strictly prior: CLEAN]'),
     E("experiments/player_program/run_turnover_p1.py", 71,
       'out["B_career_shrunk"] = (cx + EB_PRIOR_K * r_lg) / (cn + EB_PRIOR_K)  # r_lg = running prior-day league mean'),
     E("experiments/player_program/run_turnover_p1.py", 108,
       'R = R.merge(PX, on=["game_id","team_id","player_id"], how="left")  # <-- PX = projected_player_possessions_v1'),
     E("experiments/player_program/run_turnover_p1.py", 113,
       'df = R if name == "intrinsic" else both   # the intrinsic frame STILL carries the merged projected column')],
    "manifest-only", "10 min",
    "MIXED, and the mix is the finding. The four rate arms A-D are genuinely row-clean: a strict "
    "day-by-day chronological pass that advances history only AFTER predicting the whole day, with a "
    "preregistered (not learned) EB_PRIOR_K. BUT line 108 merges projected_off_possessions from the "
    "artifact-granular projected exposure artifact, and that column is still present in the written "
    "'intrinsic' frame. Weakest link makes the FILE artifact-granular even though its headline "
    "estimator is clean. Worth stating on the manifest so the clean part is not lost.",
    program="player_program")

add(r"experiments\player_program\turnover_p1_v1\turnover_p1_predictions_operational_corrected.parquet",
    "ARTIFACT", "HIGH", "SPANS_HOLDOUT",
    [E("experiments/player_program/run_turnover_p1_universe_fix.py", 291,
       'O.to_parquet(OUT / "turnover_p1_predictions_operational_corrected.parquet", index=False)'),
     E("experiments/player_program/run_turnover_p1.py", 112,
       '("operational", "projected_off_possessions")  # exposure IS the projected artifact')],
    "manifest-only", "10 min",
    "The operational track multiplies each rate by projected_off_possessions, so it inherits the "
    "cbs_v15 chain directly and unambiguously.", program="player_program")

add(r"experiments\player_program\turnover_p2_v1\turnover_role_context_features_v1.parquet",
    "ARTIFACT", "HIGH", "SPANS_HOLDOUT",
    [E("experiments/player_program/run_turnover_p2.py", 113,
       'F["proj_minutes_share"] = F["projected_minutes"] / g["projected_minutes"].transform("sum")'),
     E("experiments/player_program/run_turnover_p2.py", 100,
       'columns=[... "projected_minutes", "projected_off_possessions", "p_active"]  # from projected_exposure_v1'),
     E("experiments/player_program/run_turnover_p2.py", 126,
       'snap_min = dict(ewm_min); snap_fga = dict(ewm_fga)   # trailing features ARE strictly prior: clean')],
    "manifest-only", "10 min",
    "Feature group 1 (proj_minutes_share, proj_off_poss_share, proj_rotation_rank, "
    "proj_top5_concentration) is derived from projected_player_possessions_v1 and inherits its "
    "artifact granularity. Feature groups 2-3 (trailing EWMA) are strictly prior and clean -- the "
    "day loop snapshots state BEFORE applying the day's updates. Mixed file, artifact-granular overall.",
    program="player_program")

add(r"experiments\player_program\fits_v1\p3_coefficients_v1.parquet", "ARTIFACT", "HIGH", "SPANS_HOLDOUT",
    [E("experiments/player_program/fit_rate_and_p3.py", 391,
       '"model": "pooled empirical-Bayes shrinkage; player effect shrunk toward the league ..."'),
     E("experiments/player_program/fit_rate_and_p3.py", 164,
       'beta = ridge_solve(D, lo, ld)   # a single global ridge fit over the whole training window'),
     E("experiments/player_program/fit_rate_and_p3.py", 144,
       'tr = d[d["season"] < test_s]   # WALK-FORWARD: train strictly earlier seasons'),
     E("experiments/player_program/fit_rate_and_p3.py", 182,
       '"training_cutoff_season": int(test_s) - 1, "player_id": int(p),   # per-ROW declared cutoff'),
     E("experiments/player_program/fit_rate_and_p3.py", 35,
       'TEST_SEASONS = (2022, 2023, 2024, 2025, 2026)   # so rows exist whose training window includes 2025')],
    "manifest-only", "15 min",
    "A FIT artifact, and the most interesting case in the sweep. Granularity is unambiguously "
    "ARTIFACT: a coefficient is one number pooled over every possession in its training window, with "
    "empirical-Bayes shrinkage toward a league prior. But the fit is WALK-FORWARD (train strictly "
    "earlier seasons) and -- unusually -- EVERY ROW CARRIES ITS OWN `training_cutoff_season`. So the "
    "file is self-describing: rows with cutoff <= 2024 saw only exploration-partition data, and rows "
    "with cutoff 2025 did not. Because TEST_SEASONS runs to 2026, the file DOES contain rows fit "
    "through 2025, so the file as a whole spans the holdout -- but a consumer can filter on "
    "`training_cutoff_season` and know exactly what it has. That column is the strongest existing "
    "argument for the convention decision in group 3.", program="player_program")

add(r"experiments\player_program\possessions_v2\possessions_raw_v2.parquet", "ROW", "HIGH", "NONE",
    [E("experiments/player_program/possession_artifact_v2.py", 4,
       '**NOTHING IS FITTED.** No RAPM, no rate model, no ridge penalty, no player ranking ...'),
     E("experiments/player_program/possession_artifact_v2.py", 116,
       'prev_end = pos.groupby("game_id")["end_sec"].shift(1)   # within-game only')],
    "manifest-only", "5 min",
    "A derived EVENT artifact: possessions reconstructed per game from the play-by-play. The only "
    "ordering operation is a within-game shift(1). Nothing is fitted (the module header says so and "
    "the code bears it out). Each possession row is bounded by its own game's date.",
    program="player_program")

add(r"experiments\player_program\possessions_v1\possessions_raw_v1.parquet", "ROW", "MEDIUM", "NONE",
    [E("experiments/player_program/possession_artifact_v1.py", 4,
       '**NOTHING IS FITTED.** No RAPM, no rate model, no ridge penalty, no player ranking, no offensive ...')],
    "manifest-only", "5 min",
    "Superseded v1 of the possession artifact; same non-fitting per-game construction as v2. "
    "MEDIUM rather than HIGH because only the module contract header was read, not the full body.",
    program="player_program")

add(r"data\possessions\possessions.parquet", "ROW", "MEDIUM", "NONE",
    [E("experiments/player_program/possession_artifact_v1.py", 4,
       '**NOTHING IS FITTED.** ...  [same producer family as possessions_raw_v1]')],
    "manifest-only", "5 min",
    "The repo-level possession store, same per-game non-fitted construction. MEDIUM: producer "
    "identified and its no-fit contract read, full body not traced.", program="player_program")

add(r"experiments\player_program\event_contract_v1\canonical_player_events_v1.parquet", "ROW", "HIGH", "NONE",
    [E("experiments/player_program/build_canonical_events.py", 295,
       '"""Normalise ONE game and apply keying, ordering and provenance.'),
     E("experiments/player_program/build_canonical_events.py", 300,
       'df = normalise_legacy(game_id, path) if source == "legacy" else normalise_cdn(game_id, path)')],
    "manifest-only", "5 min",
    "A schema-normalisation artifact built one game at a time from two raw play-by-play stores. "
    "'Normalise' here means schema harmonisation, not statistical normalisation -- this is exactly the "
    "kind of regex false-positive the brief warns about, and reading the function confirms it is "
    "per-game. Each event row is bounded by its own game.", program="player_program")

for a, prod in [
    (r"experiments\prediction_contract_v5\player_game_enriched.parquet", "prediction_contract_v5_enrich.py"),
    (r"experiments\prediction_contract_v5\candidacy_exclusions.parquet", "prediction_contract_v5_enrich.py"),
    (r"experiments\prediction_contract_v5\player_game.parquet", "prediction_contract_v5.py"),
]:
    add(a, "ROW", "HIGH", "NONE",
        [E(prod, 13, '1. pre-cutoff CANDIDATE and FEATURE information  -- Stage 1 frozen output'),
         E(prod, 15, '3. PREDICTION OBLIGATIONS -- derived from tier, never from outcomes'),
         E("experiments/idea_log.jsonl", 0,
           'H1 correction record, notable_row_granular_and_therefore_SAFE: '
           '"experiments/prediction_contract_v*/**.parquet"')],
        "manifest-only", "5 min",
        "The v5 contract adds per-row outcome LABELS and obligation declarations to a frozen per-row "
        "candidate universe. No fit, no pooled statistic, no cross-row aggregation -- the module's "
        "whole discipline is that each row's cutoff bounds its own evidence. Independently corroborated "
        "by the H1 correction record, which already names prediction_contract_v* as row-granular.",
        program="player_program")

# ---- market program ---------------------------------------------------------
add(r"experiments\market_program\SCORE_BASELINES\score_baseline_rows.parquet", "ROW", "HIGH", "NONE",
    [E("experiments/market_program/SCORE_BASELINES/build_score_baselines.py", 348,
       'cum_n = by_date["n"].cumsum().shift(1)'),
     E("experiments/market_program/SCORE_BASELINES/build_score_baselines.py", 386,
       'h = [(p, o) for (d, p, o) in hist.get((team_id, season), []) if d < date]'),
     E("experiments/market_program/SCORE_BASELINES/build_score_baselines.py", 425,
       'train = d[d["season"] < s]   # walk-forward calibration, strictly prior seasons only')],
    "manifest-only", "5 min",
    "CLEAN. Three independent as-of constructions and no pooled one: strictly-lagged league expanding "
    "means by date, team season-to-date with an explicit d < date filter, and a win-probability "
    "logistic calibrated walk-forward on strictly prior seasons. The `ridge=1e-9` in fit_logistic_1d "
    "is numerical conditioning, not shrinkage toward a population prior.", program="market_program")

add(r"experiments\market_program\SCORE_BASELINES\market_paired_rows.parquet", "ROW", "MEDIUM", "NONE",
    [E("experiments/market_program/SCORE_BASELINES/build_score_baselines.py", 804,
       'paired_rows.to_parquet(OUT_DIR / "market_paired_rows.parquet", index=False)'),
     E("experiments/market_program/SCORE_BASELINES/build_score_baselines.py", 348,
       'cum_n = by_date["n"].cumsum().shift(1)   [same producer, same as-of discipline]')],
    "manifest-only", "10 min",
    "Same producer as score_baseline_rows; pairs baseline rows against captured market lines, each "
    "carrying its own snapshot timestamp. MEDIUM: the pairing block itself was not read line by line.",
    program="market_program")

add(r"experiments\market_program\M13_PLAYER_VALUE_TRANSLATION\translation_rows.parquet",
    "ARTIFACT", "MEDIUM", "UNKNOWN",
    [E("experiments/market_program/M13_PLAYER_VALUE_TRANSLATION/build_translation.py", 390,
       'q = pd.qcut(fp["pred_point"], 10, duplicates="drop")   # deciles over the WHOLE population'),
     E("experiments/market_program/M13_PLAYER_VALUE_TRANSLATION/build_translation.py", 401,
       'r_pred = pd.Series(fp["pred_point"]).rank().to_numpy()   # full-population rank'),
     E("experiments/market_program/M13_PLAYER_VALUE_TRANSLATION/build_translation.py", 405,
       '# heteroscedastic normal: |residual| ~ a + b*pred_point (closed-form OLS)')],
    "human-decision", "already in flight",
    "Full-population qcut deciles, full-population ranks and a closed-form OLS variance model -- all "
    "pooled steps. DO NOT ACT ON THIS ONE HERE: a concurrent agent (MEASURE_F1_m13_fitpool) is "
    "measuring exactly this fit pool, and D075 records the M13 finding as HALT-AND-RAISED and "
    "USER_REQUIRED because it touches PASSED nodes. Listed for completeness only.",
    program="market_program")

# ---- capture / reference dimension files ------------------------------------
CAPS = [
    (r"data\injury_capture\injury_log.csv", "capture_utc, report_date, game_date", "O14 PASSED"),
    (r"data\injury_history\injury_history.csv", "date", "P24 PASSED"),
    (r"data\ref_assignments\assignments_log.csv", "capture_utc, game_date", "O11 PASSED"),
    (r"experiments\market_program\INJURY_OFFICIAL\live\capture_log.csv",
     "attempted_ts_utc, retrieval_ts_utc", "M06 + P2B PASSED"),
    (r"experiments\market_program\INJURY_OFFICIAL\live\injury_snapshots.csv",
     "retrieval_ts_utc, ingestion_ts_utc, provider_publication_ts_*, url_slot_ts_*", "M06 PASSED"),
    (r"experiments\market_program\INJURY_OFFICIAL\live\status_transitions.csv",
     "t_lower_utc_bound, t_upper_utc_bound", "M06 PASSED"),
    (r"data\props_capture\historical\master_props_historical.csv",
     "snapshot_requested_utc, snapshot_returned_utc, last_update", "M13 + M14 PASSED"),
    (r"data\props_capture\master_props.csv", "snapshot_utc, last_update", "-"),
    (r"data\reference\tip_times.csv", "game_date, tip_utc", "-"),
    (r"data\masters\master_player.csv", "game_date, observed_time", "-"),
]
for a, cols, nodes in CAPS:
    add(a, "ROW", "HIGH", "NONE",
        [E("experiments/exploration/MANIFEST_REMEDIATION/s10_capture_headers.py", 0,
           "header inspection: per-row as-of columns present -> " + cols)],
        "manifest-only", "5 min",
        "An append-only CAPTURE or per-game record. Every row carries its own observation/capture "
        "timestamp, so each row is bounded by its own as-of time by construction. Nothing is fitted "
        "and nothing is aggregated across rows. Consumed by: " + nodes,
        program="capture")

add(r"data\reference\team_cities.csv", "ROW", "HIGH", "NONE",
    [E("data/reference/collect_bios.py", 203,
       'df = pd.DataFrame(CITY_ROWS, columns=[...])   # a hardcoded offline constant'),
     E("data/reference/collect_bios.py", 213,
       'chk = master_keys.merge(df, ...)   # join-VERIFY only; no value is derived from the master')],
    "manifest-only", "5 min",
    "A 16-row static geography dimension (city, arena, lat/lon, elevation, timezone) built from a "
    "hardcoded literal. No time-varying value, no fit, no data-derived field. The master is read only "
    "to VERIFY that every key joins. Highest consumer count among the reference files (6, two PASSED "
    "nodes) and completely inert.", program="reference")

add(r"data\reference\player_bios.csv", "ROW", "MEDIUM", "NONE",
    [E("data/reference/collect_bios.py", 438,
       'out = REF / "player_bios.csv"   # keyed (player_id, season)'),
     E("experiments/exploration/MANIFEST_REMEDIATION/s11_bios_probe.py", 0,
       'probe on 2021-2024 rows only: age varies across seasons for 182/184 multi-season players; '
       'weight_lbs for 44/184; position_raw/college/country for 0/184')],
    "manifest-only", "15 min",
    "Biographical attributes keyed (player_id, season). The probe settles the question the brief would "
    "otherwise leave open: the values are NOT one current-state pull replicated across a player's "
    "seasons -- age and weight genuinely vary season to season, so each row is a per-season fact. "
    "position_raw/college/country are constant because they are genuinely time-invariant. MEDIUM not "
    "HIGH for one reason: spot-checking `age` against `birthdate` suggests it may be off by about a "
    "year (Taurasi shows 40 in 2021). That is a DATA-QUALITY question, not a granularity one, but it "
    "deserves a five-minute check before the manifest is written.", program="reference")

add(r"experiments\player_program\data_lane\D12_COACHING_HISTORY\team_season_coverage_v1.csv",
    "ROW", "MEDIUM", "NONE",
    [E("experiments/player_program/data_lane/D12_COACHING_HISTORY/build_coaching_history.py", 466,
       'season_open = ts.groupby("season")["first_game_date"].min().to_dict()'),
     E("experiments/exploration/MANIFEST_REMEDIATION/s10_capture_headers.py", 0,
       'header: season, team_id, franchise, first_game_date, ... seasons_carried_forward, cutoff_status')],
    "human-decision", "10 min",
    "76 rows, one per team-season. Each row's fields are computed from its OWN season plus "
    "carried-forward PRIOR seasons -- never a later one. So filtering by season IS sufficient and the "
    "policy's purpose is met. The reason this needs a human is a VOCABULARY question, not a safety "
    "one: 'row' is defined as bounded by the row's own DATE, and this row's bound is its own SEASON. "
    "See the convention decision in group 3.", program="player_program")

# ---- legacy / other-program artifacts: NOT individually traced ---------------
LEGACY_SCREEN = [
    r"experiments\exploration\E0_I0014_residual_heterogeneity\screen_results.csv",
    r"experiments\feature_screen\screen_results.csv",
    r"experiments\feature_screen_crossseason\screen_results.csv",
    r"experiments\feature_screen_rebaselined\screen_results.csv",
    r"experiments\feature_screen_run2\screen_results.csv",
    r"experiments\volume_heterogeneity\screen_results.csv",
    r"experiments\feature_archetypes\survivor_summary.csv",
    r"experiments\feature_interactions\survivor_summary.csv",
    r"experiments\feature_screen\survivor_summary.csv",
    r"experiments\feature_screen_crossseason\survivor_summary.csv",
    r"experiments\feature_screen_rebaselined\survivor_summary.csv",
    r"experiments\feature_screen_run2\survivor_summary.csv",
    r"experiments\volume_heterogeneity\survivor_summary.csv",
]
for a in LEGACY_SCREEN:
    add(a, "ARTIFACT", "MEDIUM", "UNKNOWN",
        [E("(structural)", 0,
           "one row per screened FEATURE, not per game: columns are dR2 / p-value / survivor flags, "
           "each of which is a statistic pooled over the whole screened population")],
        "manifest-only", "5 min each",
        "A SCREEN RESULT table, not a feature table. Every cell is a statistic computed over the whole "
        "screened population, so there is no per-row date bound that could exist. Artifact-granular by "
        "construction. MEDIUM because the classification is structural (from the artifact's shape and "
        "its consumers) rather than from reading each of the six screen producers line by line. These "
        "feed only interactions_lab.py / volume_heterogeneity.py, both legacy game-model screens; "
        "AUDIT_SCREEN_INTEGRITY already covers this family.", program="legacy_screen")

LEGACY_MODEL = [
    (r"experiments\channel_reval\channel_base_v2.csv", "channel_reval"),
    (r"experiments\channel_reval\channel_results_v2.csv", "channel_reval"),
    (r"experiments\clv_transfer\bet_log.csv", "clv_transfer"),
    (r"experiments\clv_transfer\flat_stake_sim.csv", "clv_transfer"),
    (r"experiments\props_edge\bet_universe_best_line.csv", "props_edge"),
    (r"experiments\props_edge\bet_universe_per_book.csv", "props_edge"),
    (r"experiments\totals_groundwork\bookie_totals_per_game.csv", "totals_groundwork"),
    (r"experiments\totals_groundwork\exploratory_bias_fix_per_game.csv", "totals_groundwork"),
    (r"experiments\dist_margin_cover\game_level_dist.csv", "dist_margin_cover"),
    (r"experiments\oracle_bracket\game_level_margins.csv", "oracle_bracket"),
    (r"experiments\minutes_twostage\test_predictions_m1.csv", "minutes_twostage"),
    (r"experiments\minutes_twostage\test_predictions_m2.csv", "minutes_twostage"),
    (r"experiments\w2_integration\game_level_predictions.csv", "w2_integration"),
]
for a, fam in LEGACY_MODEL:
    add(a, "UNDETERMINED", "NONE", "UNKNOWN",
        [E("(not traced)", 0, "producer located but build code NOT read in this sweep")],
        "human-decision", "20-40 min each",
        "NOT CLASSIFIED. The producer script was located (see producer_candidates.json) but its build "
        "code was not read, so no granularity is proposed. Stating UNDETERMINED rather than guessing: "
        "these are model/backtest outputs from the game-and-betting program, where a train/test split "
        "fit through 2026 is the norm -- the H1 hazard already lists two siblings of this family "
        "(channel_reval/predictions_v2.csv, w2_integration/calibration_params.json) as contaminated, "
        "so the prior leans ARTIFACT, but a prior is not evidence. None of these is read by any "
        "player-program graph node or any live exploration lead.", program=fam)

# ---------------------------------------------------------------------------
# assemble
# ---------------------------------------------------------------------------
LEAD_STATUS = {"I0004": "LIVE (SCREENED_LEAD_REFRAMED)", "I0005": "superseded by I0009",
               "I0008": "DEAD (KILL at Stage-1 noise-floor gate)",
               "I0009": "LIVE (SCREENED_LEAD_MAGNITUDE_CORRECTED; strongest surviving lead)",
               "I0011": "LIVE (keep-as-lead x3)"}

rows = []
for art, r in inv.items():
    c = C.get(art)
    if c is None:
        c = dict(proposed_asof_granularity="UNDETERMINED", confidence="NONE", holdout_risk="UNKNOWN",
                 evidence=[E("(not reached)", 0, "not reached in this sweep")],
                 remedy="human-decision", estimated_cost="unknown",
                 note="NOT COVERED by this sweep.", lead=None, program=None)
    passed = r.get("passed_nodes") or []
    lead = c.get("lead")
    if passed:
        liveness, lscore = "LIVE: consumed by PASSED graph node(s) " + ", ".join(passed), 3
    elif lead and "LIVE" in LEAD_STATUS.get(lead, ""):
        liveness, lscore = "LIVE: feeds exploration lead %s -- %s" % (lead, LEAD_STATUS[lead]), 3
    elif lead:
        liveness, lscore = "DEAD: lead %s -- %s" % (lead, LEAD_STATUS.get(lead, "?")), 1
    elif c.get("program") in ("player_program", "capture", "reference", "market_program"):
        liveness, lscore = "LIVE-ADJACENT: in the player/market program lineage, no PASSED node names it", 2
    else:
        liveness, lscore = "DEAD/LEGACY: game-and-betting program only; no player-program consumer", 0

    gran = c["proposed_asof_granularity"]
    if gran == "UNDETERMINED":
        group = 3
    elif gran == "ARTIFACT" and lscore >= 2 and c["holdout_risk"] == "SPANS_HOLDOUT":
        group = 1
    elif c["remedy"] == "human-decision":
        group = 3
    elif lscore == 0:
        group = 4
    else:
        group = 2

    rows.append(dict(
        artifact=art, exists=r["exists"], size_mb=r["size_mb"],
        consumer_count=r["n_consumers"], consumers=r["consumers"],
        passed_node_consumers=passed, consumer_liveness=liveness,
        priority_score=r["n_consumers"] * (lscore + 1),
        proposed_asof_granularity=gran, confidence=c["confidence"],
        holdout_risk=c["holdout_risk"], evidence=c["evidence"],
        remedy=c["remedy"], estimated_cost=c["estimated_cost"],
        group=group, note=c["note"], exploration_lead=lead, program=c.get("program")))

rows.sort(key=lambda x: (-x["priority_score"], x["artifact"]))
for i, x in enumerate(rows, 1):
    x["priority_rank"] = i

GROUPS = {1: "LIVE CONTAMINATION - needs a re-run or a scope decision, not just paperwork",
          2: "SAFE / HONESTLY-BOUNDED - needs only a manifest",
          3: "UNDETERMINED - needs a human decision",
          4: "DEAD or UNUSED - ignorable"}

payload = {
    "schema": "manifest_remediation_plan/1",
    "produced_by": "MANIFEST_REMEDIATION infrastructure-analysis agent",
    "input": "experiments/exploration/AUDIT_baseline_provenance/MISSING_MANIFESTS.json",
    "scope": "the 68 shared/upstream artifacts with no sibling manifest",
    "NO_MANIFEST_WAS_WRITTEN": True,
    "policy": ("GRAPH_POLICY 13.2.2. 'row' = each row bounded by its own date, filtering to 2021-2024 "
               "is sufficient. 'artifact' = the whole file is bounded by its latest input, filtering "
               "does NOT help."),
    "method": ("Producers located by scanning 762 .py files; classification made by READING the build "
               "code and quoting the construction line. Regex was used only to LOCATE candidate lines. "
               "Lineage traced through inputs, so inherited granularity is captured."),
    "holdout_risk_vocabulary": {
        "NONE": "build hard-filters to 2021-2024 before any aggregation, or every row is capture-timestamped",
        "PARTITION_ONLY_LOOKAHEAD": ("pools across rows, but only within 2021-2024 -- a within-season "
                                     "look-ahead, NOT confirmation-holdout contamination"),
        "SPANS_HOLDOUT": "the file contains or embeds values derived from 2025/2026 inputs",
        "UNKNOWN": "not established"},
    "groups": GROUPS,
    "counts": {
        "total": len(rows),
        "by_group": {GROUPS[g]: sum(1 for x in rows if x["group"] == g) for g in sorted(GROUPS)},
        "by_granularity": dict(collections.Counter(x["proposed_asof_granularity"] for x in rows)),
        "by_confidence": dict(collections.Counter(x["confidence"] for x in rows)),
        "by_holdout_risk": dict(collections.Counter(x["holdout_risk"] for x in rows)),
        "consumed_by_a_passed_node": sum(1 for x in rows if x["passed_node_consumers"]),
    },
    "artifacts": rows,
}
json.dump(payload, open(os.path.join(OUT, "REMEDIATION_PLAN.json"), "w", encoding="utf-8"), indent=1)

print("total", len(rows))
print(json.dumps(payload["counts"], indent=1))
print("\nTOP 15 BY PRIORITY")
for x in rows[:15]:
    print("%2d) cons=%-2d %-9s %-6s g%d  %s" % (x["priority_rank"], x["consumer_count"],
          x["proposed_asof_granularity"], x["confidence"], x["group"], x["artifact"]))
