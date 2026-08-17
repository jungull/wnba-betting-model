"""S14 -- assemble COMPOSITE_SWEEP.csv for all 540 (screen, candidate) pairs.

Two sources, both explicit:
  1. _CLASSIFY_RAW.csv -- automated classification from the construction EXPRESSION in source
     (s06 located the site, s08 parsed the right-hand side with `ast`).
  2. OVERRIDE below -- candidates whose "name" is an ARM, a MODEL SPECIFICATION or a STRATUM
     rather than a column, and therefore has no assignment site.  Each override records the
     construction file:line, the component list, the level of every component and the null
     scheme, all read from source.  Every override is keyed on the EXACT (screen, candidate)
     string; the resolved list is printed and its count asserted.  No substring matching.

The invariant under test: A COMPOSITE CANDIDATE REQUIRES A NULL VALID FOR EVERY COMPONENT IT
CONTAINS.  Two forms, because the programme uses two kinds of null:
  * PERMUTATION-OF-THE-CANDIDATE nulls -- EXPOSED if any component survives the permutation
    (is invariant under it) AND the statistic can see that component.  A PRODUCT is NOT exposed
    merely for spanning levels: if the permuted factor multiplies the whole term, permuting it
    destroys the term.
  * PAIRED SIGN-FLIP / CLUSTER nulls -- EXPOSED if the cluster is STRICTLY FINER than the
    coarsest level any component varies at, because then the dependence that component induces
    is not covered.
"""
import json, os
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPL = os.path.dirname(HERE)

K = pd.read_csv(os.path.join(HERE, "_CLASSIFY_RAW.csv"))
K["candidate"] = K["candidate"].astype(str)
assert len(K) == 540, len(K)

# level ordering, coarse -> fine, for the cluster-coverage test
ORDER = ["constant", "season", "season-date", "player", "player-season", "team-season",
         "opp-team-season", "team-game", "opp-team-game", "game", "player-game", "row"]
RANK = {l: i for i, l in enumerate(ORDER)}

def coarsest(levels):
    ls = [l for l in levels if l in RANK]
    return min(ls, key=lambda l: RANK[l]) if ls else None

# ---------------------------------------------------------------------------- OVERRIDES
# (screen, candidate) -> dict.  Every field read from source by direct inspection; the
# file:line for each is in the `evidence` field.
O = {}
def add(scr, cand, cls, comps, levels, null, nulllevel, verdict, why, ev):
    O[(scr, cand)] = dict(candidate_class=cls, components=comps, component_levels=levels,
                          null_scheme=null, null_permutes_or_clusters_at=nulllevel,
                          composite_verdict=verdict, verdict_reason=why, evidence=ev)

S30 = "E1_I0030_home_advantage_accounting"
S31 = "E1_I0031_rapm_as_prior"
S32 = "E1_I0032_aggregate_stack"
S33 = "E1_I0033_aggregation_level"
S34 = "E1_I0034_redistribution"
S20 = "E1_I0020_coldstart_tiering"
S22 = "E1_I0022_optimal_simple_estimator"
S25 = "E1_I0025_threshold_vs_refit"
S27 = "E1_I0027_reference_ladder"
S35 = "E1_I0035_availability_sum"
S04 = "E1_I0004_efficiency_transfer"
S04v = "E1_I0004_efficiency_transfer_v2"

# ---- E1_I0030 : strata + accounting rows -------------------------------------------------
for c in ["ALL_2021_2024", "REGULAR_SEASON"]:
    add(S30, c, "NOT_A_FEATURE__STRATUM", [], [], "n/a (stratum key)", "n/a", "NOT_APPLICABLE",
        "stratum key, not a candidate; the AUDIT_TABLE_EXT row is a name-harvesting artefact",
        "s02_team_effect.py:61-62; team_effect.csv has separate stratum and candidate columns")
for c, comps, lev in [
    ("__RECON_G_team_pts", ["t.pts", "t.is_home"], ["team-game", "team-game"]),
    ("__RECON_within_player", ["fbar=(f_h+f_a)/2", "pbar_h-pbar_a"],
     ["player (pooled over 4 seasons) / partition-scalar denominator", "player (pooled)"]),
    ("__RECON_composition", ["pbar_bar", "f_h-f_a"], ["player (pooled)", "player (pooled)"]),
]:
    add(S30, c, "COMPOSITE_ACCOUNTING_TERM", comps, lev,
        "per-game sign flip with the WHOLE decomposition recomputed per draw", "game",
        "NOT_EXPOSED",
        "the null recomputes f and pbar from the flipped labels (decompose_from_labels), so it "
        "does move the player-venue aggregation; the game-level flip is coarser than nothing "
        "the term depends on except season structure -- see the CAUTION column",
        "s03_player_reconcile.py:197-210 (recompute), 218-228 (draw loop), 308-314 (rows)")
for c, comps in [("__RECON_sum_of_parts", ["__RECON_within_player", "__RECON_composition"]),
                 ("__RECON_residual", ["sum_of_parts", "__RECON_G_team_pts"]),
                 ("__RECON_within_via_minutes", ["fbar", "mbar_h-mbar_a", "ppm_h,ppm_a"]),
                 ("__RECON_within_via_ppm", ["fbar", "mbar_h,mbar_a", "ppm_h-ppm_a"])]:
    add(S30, c, "COMPOSITE_ACCOUNTING_TERM", comps,
        ["player (pooled over 4 seasons)"] * len(comps),
        "NONE -- no null of any kind is computed for this row", "n/a", "UNDETERMINABLE",
        "published with EMPTY null_sd / t / p; it is not in decomposition_term_nulls, so the "
        "composite invariant cannot be evaluated: there is no null to evaluate",
        "s03_player_reconcile.py:315-323; _s03.json decomposition_term_nulls covers only "
        "G / within_player / composition; player_reconciliation.csv rows 21-24 have empty p")
add(S30, "hhi_minutes", "COMPOSITE_RATIO",
    ["player-game minutes", "team-game total minutes"], ["player-game", "team-game"],
    "paired game sign flip", "game", "NOT_EXPOSED",
    "the cluster (game) is COARSER than both component levels, so it covers the dependence "
    "either can induce",
    "s03_player_reconcile.py:261-264 (construction), :295 (null); ha_base.py:172")
add(S30, "starter_minute_share", "COMPOSITE_RATIO",
    ["starter minutes (player-game, gated by starter_flag)", "team-game total minutes"],
    ["player-game", "team-game"], "paired game sign flip", "game", "NOT_EXPOSED",
    "cluster coarser than every component", "s03_player_reconcile.py:265-268, :295")
for c in ["pts_eq", "min_eq", "fga_eq", "fta_eq", "fg3a_eq", "ppm_eq", "fgapm_eq", "ftapm_eq"]:
    add(S30, c, ("COMPOSITE_RATIO" if c in ("ppm_eq", "fgapm_eq", "ftapm_eq") else "ATOMIC_AGG"),
        ["player-game quantity", "team-game player count"], ["player-game", "team-game"],
        "paired game sign flip", "game", "NOT_EXPOSED",
        "team-game mean of a player-game quantity, differenced within game; the game-level "
        "cluster is coarser than every component", "s03_player_reconcile.py:246-254, :295")

# ---- E1_I0031 --------------------------------------------------------------------------
add(S31, "pm_all", "BUNDLE",
    ["pm_ewma5_imp", "pm_ewma2_imp", "pm_run_mean_imp", "pm_per36_prior_imp",
     "pm_prev_season_imp"],
    ["player-game (vsb 0.5937)", "player-game (vsb 0.4458)", "player-game (vsb 0.7275)",
     "player-game (vsb 0.5718)", "player-season CONSTANT (vsb 1.0000)"],
    "cyclic shift within player-season", "player-season (WITHIN)", "EXPOSED",
    "a cyclic shift is the IDENTITY on pm_prev_season_imp (max within-group spread 0.000e+00), "
    "so the null cannot move one of the five components.  This is E1_I0040's finding, "
    "reproduced here, and it is the only previously-known instance.  DISCHARGED for 16 of its "
    "32 kills by the component's own matched relabel p already on disk (max dR2 contribution "
    "4.83e-05); 7 remain UNRESOLVED.",
    "s06_plusminus.py:38-40 (bundle), :116-118 (null choice), :49 assert_constant_within; "
    "E1_I0040 MEASURED_VARIANCE_SHARES.csv, EXPOSED_DISCHARGE.csv")
add(S31, "RAPM_as_feature", "BUNDLE",
    ["net_100_lam2000_imp", "net_100_lam500_imp", "net_100_lam1000_imp", "net_100_lam5000_imp",
     "z_net_100_imp", "z_orapm_100_imp", "z_drapm_100_imp", "log_total_poss_imp",
     "has_rapm_f", "z_net_x_poss"],
    ["player-season"] * 9 + ["player-season (product of two player-season constants)"],
    "whole player-season relabel", "player-season (BETWEEN)", "NOT_EXPOSED",
    "every component is constant within player-season and the null relabels whole "
    "player-seasons, so it moves all ten together.  CAUTION recorded: only 4 of the 10 are "
    "asserted constant in source, and the season-mean imputation inserts a SEASON-level "
    "constant on ~18% of rows which the relabeller then moves as if it were player content.",
    "s02_feature.py:27, :71-96; s01_prereg.py:25-36 (assert covers 4 of 10)")

# ---- E1_I0032 -------------------------------------------------------------------------
add(S32, "CHAMPION", "NOT_A_FEATURE__ARM_LABEL", ["champ_pts/minutes/fga/ppm"],
    ["player-game"], "clustered paired sign flip", "player-season", "NOT_APPLICABLE",
    "the baseline arm; adds nothing", "s08_stack.py:118-121; s06_build.py:130-138")
for c in ["STEP0", "STEP1", "STEP2", "STEP3"]:
    add(S32, c, "COMPOSITE_MODEL_SPEC",
        {"STEP0": [], "STEP1": ["C1 route mask", "naive EWMA estimator"],
         "STEP2": ["C1", "C3 half-life"],
         "STEP3": ["C1", "C3", "C4 shrink to own prior season"]}[c],
        {"STEP0": [], "STEP1": ["player-game", "player-game"],
         "STEP2": ["player-game", "target-scalar"],
         "STEP3": ["player-game", "target-scalar", "player-season"]}[c],
        "clustered paired sign flip", "player-season", "NOT_EXPOSED",
        "every component varies at player-game or finer within the player-season cluster, or is "
        "a target-level constant; the cluster covers the dependence",
        "s08_stack.py:72-87 (build), :94 (null); stack_base.py:162-173; s06_build.py:123 cluster")
add(S32, "STEP4", "COMPOSITE_MODEL_SPEC",
    ["A10_opp_defrtg (DEF)", "TOP usage gate", "season tercile cut"],
    ["opp-team-game", "player (between-player share 0.8413)", "season"],
    "clustered paired sign flip", "player-season", "EXPOSED",
    "the added term is an OPPONENT-TEAM-GAME regressor gated by a PLAYER-level selector, but "
    "the null clusters at player-season, which is STRICTLY FINER than opp-team-season.  The "
    "dependence induced across all players facing the same opponent is not covered.  This is "
    "a decided increment (increment_dR2 0.001723, increment_p 0.004749), so the exposure is "
    "not vacuous.",
    "s08_stack.py:37-39 (FEAT), :85-86 (correction), :94 (null); s06_build.py:48-53 join, :123 "
    "cluster; E1_I0040 MEASURED_VARIANCE_SHARES.csv row 21 (DEF between-player 0.01604)")
add(S32, "STEP5", "COMPOSITE_MODEL_SPEC", ["P01_c04_prevgame"],
    ["player-game (a team-game roster sum MINUS the player's own term; between-player 0.2731)"],
    "clustered paired sign flip", "player-season", "EXPOSED",
    "P01 is a team-game sum with the own term removed, so it carries a TEAM-GAME component "
    "shared by every teammate in the same game; the player-season cluster does not cover it.  "
    "increment_p 0.2259 -- no verdict is at risk.",
    "E1_I0018/s01_build_frame.py:154; s08_stack.py:38, :94")
add(S32, "STEP6", "COMPOSITE_MODEL_SPEC", ["is_home (HOME)"],
    ["team-game (between-player share 0.005025)"],
    "clustered paired sign flip", "player-season", "EXPOSED",
    "HOME is a TEAM-GAME column under a PLAYER-SEASON cluster -- the sharpest level mismatch "
    "found in the sweep.  increment_p 0.3872 -- no verdict is at risk.",
    "s06_build.py:65-67, :127; s08_stack.py:39, :94")
add(S32, "STACK", "COMPOSITE_MODEL_SPEC",
    ["C1", "C3", "C4", "C6 (DEF x TOP x season cut)", "C5 (P01)", "C7 (HOME)"],
    ["player-game", "target-scalar", "player-season", "opp-team-game / player / season",
     "player-game + team-game", "team-game"],
    "clustered paired sign flip", "player-season", "EXPOSED",
    "the full stack contains C6, C5 and C7, all of which carry components coarser than the "
    "player-season cluster.  HEADLINE cell: pts/POOLED dR2 0.034218, p 0.000250.",
    "s08_stack.py:48-49, :111, :121, :94")
add(S32, "FULL_STACK", "COMPOSITE_MODEL_SPEC", ["same object as STACK"], ["as STACK"],
    "clustered paired sign flip", "player-season", "EXPOSED",
    "same forecast as STACK, different baseline (ablation matrix)", "s08_stack.py:155-159")
for c in ["PLACEBO_STACK", "PLACEBO_FULL"]:
    add(S32, c, "COMPOSITE_MODEL_SPEC", ["placebo mirrors of the six components"],
        ["same levels as the real components, by construction"],
        "clustered paired sign flip", "player-season", "EXPOSED",
        "placebo arm carrying the identical level structure; exposed for the same reason and "
        "reported so the placebo is not silently treated as clean",
        "s08_stack.py:42-46, :112, :230, :239")
for c in ["v14", "v15"]:
    add(S32, c, "COMPOSITE_MODEL_SPEC",
        ["stored p_active forecast", "pl_days_since_appear bin", "(season x bin) logit offset"],
        ["player-game", "player-game", "season-bin"],
        "clustered paired sign flip", "player-season", "NOT_EXPOSED",
        "every component is player-game or a season-level scalar; the season-bin offset is "
        "common to both arms of the paired comparison and cancels",
        "s09_availability.py:36-63")

# ---- E1_I0033 --------------------------------------------------------------------------
add(S33, "B1_BOTTOMUP_AVAIL", "COMPOSITE_SUM",
    ["p_active_hat", "pts_hat"], ["player-game", "player-game"],
    "paired block sign flip", "team-season", "NOT_EXPOSED",
    "a team-game aggregate of player-game terms, clustered at team-season -- coarser than "
    "every component.  The screen states in advance why the within-player cyclic null is NOT "
    "used here.", "s06_topdown_vs_bottomup.py:82-88; s08:130 cluster")
add(S33, "B3_ORACLE_ROSTER", "COMPOSITE_SUM", ["pts_hat", "realised appeared flag"],
    ["player-game", "player-game (REALISED -- oracle)"],
    "paired block sign flip", "team-season", "NOT_APPLICABLE",
    "declared ORACLE in advance and excluded from every headline and every ranking",
    "s06_topdown_vs_bottomup.py:89-90, :185, :240")
for c, comps, lev in [
    ("P07", ["_ftpct_c", "_ftarate_c", "_composed_term vs _flat_term"],
     ["team-game", "team-game", "team-game x season-date league running"]),
    ("P07b_EXPLORATORY", ["_ftpct_c", "_ftarate_c", "_flat_term", "_delta_term"],
     ["team-game", "team-game", "team-game", "team-game"]),
    ("P08", ["_ftpct_c", "_ftarate_c", "_composed_term"],
     ["team-game", "team-game", "team-game"])]:
    add(S33, c, "COMPOSITE_MODEL_SPEC", comps, lev, "paired block sign flip", "team-season",
        "NOT_EXPOSED", "cluster (team-season) is coarser than every component level",
        "s09_ft_composition.py:118-156, :179-183")
for c in ["P09", "P10", "P11", "P12", "P13"]:
    add(S33, c, "COMPOSITE_MODEL_SPEC",
        ["team EWMA prefix", "team prev-season shrink target", "league running", "(h,k)"],
        ["team-game", "team-season", "season-date", "season"],
        "paired block sign flip", "team-season", "NOT_EXPOSED",
        "cluster equals or is coarser than every component except the season-level tuning "
        "constants, which are common to both arms and cancel",
        "s08_which_level.py:25-107, :130")
for c in ["X1_EXPLORATORY", "X2_EXPLORATORY"]:
    add(S33, c, "COMPOSITE_MODEL_SPEC",
        ["B1_BOTTOMUP_AVAIL", "sum_p_active", "prior_roster_size", "affine (a,b)"],
        ["team-game", "team-game", "team-game", "season"],
        "paired block sign flip", "team-season", "NOT_EXPOSED",
        "cluster coarser than every component; declared exploratory and added after the hash",
        "s07:72-87; s11_findings.py:23-27")

# ---- E1_I0034 --------------------------------------------------------------------------
for c in ["FREED_minutes", "FREED_fga", "FREED_pts"]:
    add(S34, c, "COMPOSITE_SUM", ["base5_<ch> of absent players", "absence indicator"],
        ["team-game (measured frac_within_teamgame = 0.0 for the derived u)", "team-game"],
        "N4 permute freed within season", "season", "UNDETERMINABLE",
        "the screen's own candidate_level_audit.csv measures over PLAYER and TEAM-GAME, but "
        "the null's entity is SEASON; the share the invariant needs is not on disk at that "
        "entity and this screen did not invent one.  This is E1_I0040's 3 undeterminable cells, "
        "confirmed and left undeterminable.",
        "s05_frame.py:57-61, :84; s06_cells.py:107-133; candidate_level_audit.csv")
for c in ["P01_LEAKAGE_minutes", "P01_LEAKAGE_fga", "P01_LEAKAGE_pts"]:
    add(S34, c, "NOT_A_FEATURE__CELL_ID", ["cell identifier for the FREED_* candidate"], [],
        "N4 permute freed within season", "season", "UNDETERMINABLE",
        "same three cells as above, under their cell name rather than their candidate name",
        "s06_cells.py:108-133")
for c in ["P02_TILT_minutes", "P02_TILT_fga", "P02_TILT_pts", "u * z"]:
    add(S34, c, "COMPOSITE_PRODUCT", ["u_<ch>", "z_<ch>"],
        ["team-game (measured frac_within_teamgame 0.0000)",
         "between-player within team-game (measured frac_within_teamgame 0.9729)"],
        "N1 within-team-game shuffle of (base5, z)", "team-game (WITHIN)", "NOT_EXPOSED",
        "the product's team-game factor u is CONSTANT within the permuting block, so shuffling "
        "z within the team-game destroys the whole product; measured shares are the screen's "
        "own (u*z frac_within_teamgame 0.9535-0.9600)",
        "s05_frame.py:85; s06_cells.py:141-173; candidate_level_audit.csv")
for c in ["P05_POSITION_MATCH_minutes", "u * posmatch"]:
    add(S34, c, "COMPOSITE_PRODUCT", ["u_minutes", "posmatch"],
        ["team-game", "between-player within team-game (measured frac_within_teamgame 0.5883)"],
        "N1 within-team-game shuffle of (base5, z, posmatch)", "team-game (WITHIN)",
        "NOT_EXPOSED",
        "same argument as u*z; note posmatch is the least within-team-game of the three "
        "(41.2% of its variance is BETWEEN team-games), so this is the marginal case",
        "s05_frame.py:90-100; s06_cells.py:240-265; candidate_level_audit.csv")
for c in ["P03_minutes", "P03_fga", "P03_pts", "P03_vs_base5_minutes", "P03_vs_base5_fga",
          "P03_vs_base5_pts", "P04_vs_champion_minutes", "P04_vs_champion_fga",
          "P04_vs_champion_pts"]:
    add(S34, c, "COMPOSITE_MODEL_SPEC", ["base5", "z", "u", "u*z", "(champion offset for P04)"],
        ["player-game", "between-player within team-game", "team-game",
         "between-player within team-game", "player-game"],
        "N2 paired block sign flip at team-game", "team-game", "NOT_EXPOSED",
        "the cluster is the team-game, which is the coarsest level any component varies at; "
        "the screen states the reason in source",
        "redist_base.py:225-233; s06_cells.py:186, :203-231")

# ---- E1_I0020 --------------------------------------------------------------------------
for c, comps, lev, verdict, why in [
    ("P0_champion", ["stored champion point forecast"], ["player-game"], "NOT_EXPOSED",
     "single stored forecast"),
    ("P1_ref_D076", ["own expanding prior mean", "same-season league expanding mean",
                     "frame mean"], ["player-game", "season-date", "constant"], "NOT_EXPOSED",
     "components are player-game or a league scalar common to both arms"),
    ("P1full_running_mean", ["own_season running mean", "league running", "frame mean"],
     ["player-game", "season-date", "constant"], "NOT_EXPOSED", "as above"),
    ("P2_position", ["pos_group", "shrunk group mean", "mu"],
     ["player (MEASURED: COARSER_LEVEL_FOUND/player)", "pos-group x season-fold", "season"],
     "NOT_EXPOSED", "purely between-player; the paired null clusters at player-season, which "
                    "is finer than player -- but a player appears in at most one player-season "
                    "per season and the fold is a season, so no coarser dependence is left "
                    "uncovered within a season"),
    ("P3_draft_bin", ["draft_bucket", "shrunk bucket mean", "mu"],
     ["player (MEASURED)", "bucket x season-fold", "season"], "NOT_EXPOSED", "as P2_position"),
    ("P3_draft_ols", ["log(draft_pick)", "1[round>=2]", "OLS beta", "undrafted_mean"],
     ["player", "player", "season-fold", "season-fold"], "NOT_EXPOSED", "as P2_position"),
    ("P4_teamrole", ["depth_bucket", "shrunk depth mean", "mu"],
     ["player-game (MEASURED: NO_COARSER_LEVEL_EXISTS)", "bucket x season-fold", "season"],
     "NOT_EXPOSED", "the only structural component varying within a player-season; the "
                    "player-season cluster covers it"),
    ("P5a_draft_x_depth", ["draft_bucket", "depth_bucket", "cell value", "league fill"],
     ["player", "player-game", "bucket-pair x season-fold", "season"], "NOT_EXPOSED",
     "cluster (player-season) is coarser than player-game and the player-level factor is "
     "constant inside the cluster"),
    ("P5b_pos_x_draft", ["pos_group", "draft_bucket", "cell value", "league fill"],
     ["player", "player", "pos x bucket x season-fold", "season"], "NOT_EXPOSED",
     "purely between-player, constant within a player-season"),
    ("P5c_additive", ["mu", "pos-mu", "draft_bin-mu", "depth-mu"],
     ["season", "player", "player", "player-game"], "NOT_EXPOSED",
     "spans season / player / player-game; the player-season cluster is coarser than "
     "player-game and the player-level terms are constant inside it"),
]:
    add(S20, c, ("COMPOSITE_MODEL_SPEC" if c.startswith("P5") or c.startswith("P3_draft_ols")
                 else "COMPOSITE_PRIOR" if c.startswith(("P1", "P2", "P3", "P4"))
                 else "ATOMIC"),
        comps, lev, "clustered paired sign flip (paired_forecast_comparison)",
        "player-season", verdict, why,
        "s03_placeholders.py:165-211 (build); ct_base.py:447-456 (null, groups = "
        "_group_codes(f, ['season','player_id'])); _s04.json grouping_levels")
for k in [1, 2, 3, 5, 10]:
    add(S20, "P5d_blend_k%d" % k, "COMPOSITE_MODEL_SPEC",
        ["own_season running mean", "P5c_additive struct", "lam = n/(n+k)", "k"],
        ["player-game", "season + player + player-game", "player-game", "constant"],
        "clustered paired sign flip", "player-season", "NOT_EXPOSED",
        "a between-player structural prior blended with a within-player running quantity; the "
        "cluster is coarser than every varying component",
        "s03_placeholders.py:200-206; ct_base.py:447-456")
for k in [2, 3, 5]:
    add(S20, "P5e_careerblend_k%d" % k, "COMPOSITE_MODEL_SPEC",
        ["own_career running mean", "P5c_additive struct", "lamc = n_career/(n_career+k)", "k"],
        ["player-game (career, CROSSES SEASONS)", "season + player + player-game",
         "player-game (crosses seasons)", "constant"],
        "clustered paired sign flip", "player-season", "EXPOSED",
        "n_career and own_career accumulate ACROSS seasons, so they induce dependence between "
        "a player's 2022, 2023 and 2024 player-seasons; the cluster is (season, player_id), "
        "which splits exactly that dependence.  This is a component coarser than the cluster.",
        "s03_placeholders.py:207-209 (own_career, n_career = pl_career_games_prior); "
        "rh_base.py:176-177 (groupby player_id only, no season); ct_base.py:447-448 cluster")
for c in ["TIER_DATA_POOR", "sub_0_priors", "sub_1_2_priors", "2024"]:
    add(S20, c, "NOT_A_FEATURE__STRATUM", [], [], "n/a", "n/a", "NOT_APPLICABLE",
        "row-set cell, not a candidate", "s04_decompose_and_crossover.py:34-38")

# ---- E1_I0022 --------------------------------------------------------------------------
for c in ["tier_0", "tier_1-2", "tier_3-7", "tier_8-14", "tier_15-24", "tier_25+",
          "tier_lt3_priors", "tier_ge3_priors", "pooled_wf", "decision_stratum_wf",
          "outside_decision_stratum_wf"]:
    add(S22, c, "NOT_A_FEATURE__STRATUM", [], [], "block sign flip at player-season",
        "player-season", "NOT_APPLICABLE",
        "row-set slice of the walk-forward evaluation rows, not a candidate; the two arms are "
        "identical across slices.  CAUTION: tier_lt3/ge3 OVERLAP the numbered tiers, so the "
        "eleven are not a partition.",
        "s05_inference_and_where.py:31-37, :82-85")

# ---- E1_I0025 --------------------------------------------------------------------------
add(S25, "L1_pooled_defence_main", "COMPOSITE_MODEL_SPEC", ["A10_opp_defrtg"], ["team-game"],
    "within-date opponent swap of the defence value + cluster sign flip at opp-team-season",
    "team-game / opp-team-season", "NOT_EXPOSED",
    "single defence-family column, permuted at its own level",
    "cbase.py:180-181; E1_I0023/s05_placebos.py:95-103; s00_prereg.py:85")
add(S25, "L2_pooled_linear_interaction", "COMPOSITE_PRODUCT",
    ["A10_opp_defrtg (d)", "O01_own_usg_pg (u)", "fold-level centring uc, dc"],
    ["team-game", "player-game", "fold"],
    "within-date opponent swap of d", "team-game", "NOT_EXPOSED",
    "the interaction (u-uc)*(d-dc) contains the PERMUTED factor d as a multiplicative term, so "
    "permuting d destroys the whole defence family including the interaction.  A mechanical "
    "'composite spans two levels' rule would condemn this cell and would be wrong.",
    "cbase.py:182-183; E1_I0023/s05_placebos.py:95-103")
add(S25, "L3_pooled_tier_dummy_x_defence", "COMPOSITE_PRODUCT",
    ["d", "tier dummies D1,D2", "dc"], ["team-game", "player-game", "fold"],
    "within-date opponent swap of d", "team-game", "NOT_EXPOSED",
    "same argument as L2; the tier dummies are in BOTH arms, so only the d-carrying columns "
    "are being tested and all of them contain d as a factor",
    "cbase.py:175-176, :184-186")
add(S25, "L4_tier_restricted_refit", "COMPOSITE_MODEL_SPEC",
    ["d", "tier-restricted fit population"], ["team-game", "player-game"],
    "within-date opponent swap of d", "team-game", "NOT_EXPOSED",
    "identical columns to L1; only the fit population differs", "cbase.py:187-188, :200")
for c in ["POOLED", "points"]:
    add(S25, c, "NOT_A_FEATURE__STRATUM", [], [], "n/a", "n/a", "NOT_APPLICABLE",
        "POOLED is a stratum id and 'points' is a response id.  CAUTION: 'POOLED' carries TWO "
        "distinct meanings in this screen -- a stratum and a fit population -- which is exactly "
        "the substring collision the programme warns about.",
        "E1_I0023/s00_prereg.py:67-71; cbase.py:196, :270")
for c in ["ROWSHUFFLE", "PLAYERBLOCK"]:
    add(S25, c, "NOT_A_FEATURE__NULL_SCHEME", [], [], "n/a", "n/a", "NOT_APPLICABLE",
        "a placebo/null scheme name, not a candidate",
        "cbase.py:295-336; c04_placebo_random_tiers.py:86-87")

# ---- E1_I0027 --------------------------------------------------------------------------
for c in ["-0.0002961142343277", "-1.0570163212486603e-05", "0.0035722898272361",
          "0.0039145919604981", "0.0045498548762125", "0.0045748709111776",
          "0.0051773646242858", "0.0064193656303963", "0.0096470153400169",
          "0.0102777472750601", "0.0112794646108451", "8.323895376183277e-05"]:
    add(S27, c, "NOT_A_FEATURE__HARVEST_ARTEFACT", [], [], "n/a", "n/a", "NOT_APPLICABLE",
        "E1_I0027 writes NO candidate column.  These twelve strings are the values of "
        "reprice_by_rung.csv's FIRST column, dr2_common_sst, picked up by the downstream "
        "auditor's fallback str(r.iloc[0]).  The real candidate identity is in the `feature` "
        "column (P01_c04_prevgame / A10_opp_defrtg / G01_noise), which the harvester never read.",
        "E1_I0040/scripts/s04_audit_table.py:490-492 (cc=None), :544 (fallback); "
        "E1_I0027/s05_reprice.py:94-99, :213-228")
add(S27, "R4_RICH_LOOKUP", "COMPOSITE_SUM",
    ["f_R0_league", "f_R1_expand", "f_R2_ewma", "f_R3_composite", "f_prior_minutes_ewma",
     "f_prior_rate_ewma", "f_prior_season_player", "f_log1p_n_prior", "OLS blend beta"],
    ["season", "player-game", "player-game", "player-game", "player-game", "player-game",
     "player-season", "player-game", "season"],
    "clustered paired sign flip", "player-season", "NOT_EXPOSED",
    "a walk-forward OLS blend of 7-8 terms, all at player-season or finer plus season-level "
    "scalars common to both arms.  CAUTION recorded separately: the SAME player-season cluster "
    "is used for the A10_opp_defrtg lead, whose value varies at opponent-team-season, and this "
    "screen never measures that component's variance share.",
    "refladder.py:102-105, :476-537; s05_reprice.py:86-99, :127")

# ---- E1_I0035 --------------------------------------------------------------------------
add(S35, "XaO", "COMPOSITE_MODEL_SPEC",
    ["p_active_hat", "logit/sigmoid recalibration coefficients (a,b)", "stratum", "pts_hat"],
    ["player-game", "scored-season x stratum (IN-SAMPLE)", "player-game", "player-game"],
    "paired block sign flip", "team-season (team arm) / player-season (player arm)",
    "NOT_APPLICABLE",
    "declared ORACLE in source and in PREREG; fitted on the scored season itself and excluded "
    "from every verdict", "s04_repairs.py:116-125, :223-229, :272-278, :343-351")

# ---- E1_I0004 / v2 ---------------------------------------------------------------------
for c in ["A", "B"]:
    add(S04, c, "COMPOSITE_PRODUCT",
        ["W__zone (player shot mix)", "POINT_VALUE (constant)", "LAMBDA_D074 (frozen constant)",
         "OC__zone (opponent zone allowance, centred)"],
        ["player-game", "constant", "constant", "opp-team-game"],
        "clustered paired sign flip at opp_team_season (+ P3 whole-opponent reassignment "
        "placebo)", "opp-team-season", "NOT_EXPOSED",
        "the signal is a PRODUCT in which the opponent factor OC is a multiplicative term, so "
        "reassigning whole opponent-team-seasons destroys the whole signal; the player mix w_z "
        "cannot carry it alone",
        "E1_I0004/s02_build.py:190-197, :217-220; s03_contrast.py:97-99")
for c in ["SPEC_RA", "SPEC_RA_UNCENTRED", "SPEC_RA_XSCENTRED", "SPEC_ALL5_GLOBAL",
          "SPEC_ALL5_GLOBAL_UNCENTRED", "SPEC_ALL5_GLOBAL_XSCENTRED", "SPEC_ALL5_PERZONE",
          "SPEC_ALL5_PERZONE_UNCENTRED", "SPEC_ALL5_PERZONE_XSCENTRED"]:
    add(S04v, c, "COMPOSITE_PRODUCT",
        ["w_z (player shot mix)", "PV_z", "beta_z (frozen)", "allowance OC / OCc / OCc_xs"],
        ["player-game", "constant", "constant",
         "opp-team-game, centred by a (season, date, zone) league scalar"],
        "clustered paired sign flip at opp_team_season; P3 whole-opponent-team-season "
        "reassignment placebo", "opp-team-season", "NOT_EXPOSED",
        "same product argument as v1.  The centring term is a season-date-zone scalar shared by "
        "every team on the date, which the screen shows cannot manufacture cross-sectional "
        "differences between opponents.",
        "E1_I0004_v2/s02_build.py:122-136, :164-168; etv2_base.py:218-257; "
        "s03_contrast.py:81-83; s03b_placebo.py:93-102")

print("OVERRIDES defined: %d" % len(O))

# ---- apply -----------------------------------------------------------------------------
rows = []
n_override_hit = 0
for _, r in K.iterrows():
    key = (r["screen"], r["candidate"])
    base = dict(screen=r["screen"], candidate=r["candidate"],
                construction_file=r["best_file"], construction_line=r["best_line"],
                construction_expr=r["construction_expr"],
                resolution_kind=r["resolution_kind"],
                auto_class=r["candidate_class"], auto_components=r["components"])
    if key in O:
        n_override_hit += 1
        o = O[key]
        base.update(candidate_class=o["candidate_class"],
                    components=json.dumps(o["components"]),
                    component_levels=json.dumps(o["component_levels"]),
                    null_scheme=o["null_scheme"],
                    null_permutes_or_clusters_at=o["null_permutes_or_clusters_at"],
                    composite_verdict=o["composite_verdict"],
                    verdict_reason=o["verdict_reason"],
                    evidence=o["evidence"], classification_source="SOURCE_READ")
    else:
        cls = r["candidate_class"]
        is_comp = str(cls).startswith(("COMPOSITE", "BUNDLE"))
        base.update(candidate_class=cls,
                    components=r["components"],
                    component_levels=json.dumps([]),
                    null_scheme="", null_permutes_or_clusters_at="",
                    composite_verdict=("NOT_APPLICABLE" if cls == "ATOMIC" else
                                       "UNDETERMINABLE" if str(cls).startswith("UNDETERMINABLE")
                                       else "PENDING"),
                    verdict_reason="", evidence="", classification_source="EXPRESSION_PARSE")
    rows.append(base)
C = pd.DataFrame(rows)
print("override rows matched: %d of %d defined" % (n_override_hit, len(O)))
miss = [k for k in O if k not in set(zip(K["screen"], K["candidate"]))]
print("overrides that matched NOTHING (must be 0 or explained): %d" % len(miss))
for k in miss:
    print("   MISS", k)
assert len(C) == 540
C.to_csv(os.path.join(HERE, "_COMPOSITE_SWEEP_STAGE1.csv"), index=False)
print("\n=== class counts after overrides ===")
print(C["candidate_class"].value_counts().to_string())
print("\n=== verdict counts ===")
print(C["composite_verdict"].value_counts().to_string())
print("\n=== PENDING (composite by expression, null validity not yet assessed) ===")
P = C[C["composite_verdict"] == "PENDING"]
print(P.groupby("screen").size().to_string())
print(P[["screen", "candidate", "candidate_class", "construction_expr"]].to_string(index=False))
print("\nDONE s14")
