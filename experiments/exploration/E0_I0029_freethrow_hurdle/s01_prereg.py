"""E0_I0029 s01 -- PREREGISTRATION.  Loads NO data and computes NO statistic.

This file fixes and hashes the candidate list, the bases, the targets, the strata, the nulls and
every analysis choice BEFORE any number is computed.  Any later change is reported as an
added/dropped count against the hash in CANDIDATES_PRESELECTED.md.

s00 ran first, but s00 computes ONLY descriptive quantities that the ideation queue had ALREADY
published (FT share of points, the zero fraction, the two marginal correlations).  It computes no
dR2, no null and nothing that could be used to choose a candidate.  Stated here so the ordering is
on the record rather than asserted later.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ft_base import (BASE_COLS, EWMA_HALFLIFE, HEADLINE_SEASONS, HISTORY_FLOOR, N_DRAWS, OUT,
                     SEASONS, SEED, TARGETS, TARGET_ORDER, hdr, sha)

# =====================================================================================
# CANDIDATES
# =====================================================================================
# `level` is the level at which the candidate ACTUALLY VARIES, and therefore the level of the
# null that carries its verdict.  Getting this wrong is trap 6 (nine confirmations).
CANDIDATES = [
    # ---- F: the player's OWN strictly-prior free-throw mechanism, beyond the target's own history
    dict(name="F01_prior_ftr", family="F", level="player_season",
         desc="player's strictly-prior FTA / strictly-prior FGA -- the free-throw RATE, a shooting"
              " style trait.  Ratio of two prior sums, NOT a mean of ratios."),
    dict(name="F02_prior_fd_pm", family="F", level="player_season",
         desc="player's strictly-prior fouls_drawn per prior minute.  THE OWN-SIDE MAIN EFFECT of"
              " the D085 matchup interaction; in B_MATCHUP from the start."),
    dict(name="F03_prior_ft_pct", family="F", level="player_season",
         desc="player's strictly-prior FTM / strictly-prior FTA -- conversion skill."),
    dict(name="F04_prior_paint_share", family="F", level="player_season",
         desc="player's strictly-prior points_paint / prior pts -- rim pressure draws fouls."),
    dict(name="F05_prior_fga_pm", family="F", level="player_season",
         desc="player's strictly-prior FGA per prior minute -- shot volume."),
    dict(name="F06_prior_fg3a_share", family="F", level="player_season",
         desc="player's strictly-prior FG3A / FGA -- a jump shooter draws fewer shooting fouls."),
    dict(name="F07_prior_hurdle_rate", family="F", level="player_season",
         desc="player's strictly-prior FRACTION OF GAMES WITH fta>0.  THE HURDLE'S OWN PRIOR"
              " MEASUREMENT.  For target y_any_fta this is identical to ref_mean and is therefore"
              " NOT screened on that target (it is already in the base); it is a candidate only on"
              " the other targets."),
    dict(name="F08_prior_fta_given", family="F", level="player_season",
         desc="player's strictly-prior mean FTA over the player's PRIOR GAMES WITH fta>0 -- the"
              " conditional-stage prior.  Undefined until the player has one such game."),
    dict(name="F09_prior_starter_rate", family="F", level="player_season",
         desc="player's strictly-prior fraction of games started.  starter_flag ITSELF IS A"
              " TIP-TIME OBSERVATION AND IS NEVER USED AS A CONTEMPORANEOUS FEATURE."),
    dict(name="F10_prior_pf_pm", family="F", level="player_season",
         desc="player's strictly-prior personal fouls COMMITTED per prior minute -- foul trouble"
              " truncates minutes and therefore trips to the line."),

    # ---- M: the OPPONENT matchup channel.  STEP 2.  Varies at opponent-team-season.
    dict(name="M01_opp_pf_pg", family="M", level="opp_team_season",
         desc="opponent team's strictly-prior personal FOULS COMMITTED per game.  THE OPPONENT-SIDE"
              " MAIN EFFECT of the D085 interaction; in B_MATCHUP from the start."),
    dict(name="M02_opp_allowed_fta_pg", family="M", level="opp_team_season",
         desc="opponent team's strictly-prior FTA ALLOWED per game.  THE CLOSEST PRIOR OPPONENT"
              " MEASUREMENT OF THE TARGET.  Also used as an extra base column in the decomposition"
              " variant B_COMPLETE_PLUS_M02."),
    dict(name="M03_opp_allowed_ftm_pg", family="M", level="opp_team_season",
         desc="opponent team's strictly-prior FTM ALLOWED per game."),
    dict(name="M04_opp_allowed_ft_rate", family="M", level="opp_team_season",
         desc="opponent's strictly-prior FTA-allowed / FGA-allowed -- the rate form, free of the"
              " opponent's pace."),
    dict(name="M05_opp_allowed_hurdle_rate", family="M", level="opp_team_season",
         desc="fraction of OPPOSING PLAYER-GAMES with fta>0 that this opponent has allowed in its"
              " strictly-prior games.  THE CLOSEST PRIOR OPPONENT MEASUREMENT OF STAGE A'S TARGET."),
    dict(name="M06_opp_pace", family="M", level="opp_team_season",
         desc="opponent team's strictly-prior mean pace -- more possessions, more chances."),

    # ---- X: THE INTERACTION.  D085's trap.  Reported ONLY over a base already containing BOTH
    #         of its own main effects.  Any dR2 over B_COMPLETE is reported as a DIAGNOSTIC of the
    #         trap, explicitly labelled, and NEVER as a result.
    dict(name="X01_fd_x_oppfoul", family="X", level="opp_team_season",
         desc="(F02 own prior fouls-drawn per minute, centred) x (M01 opp prior fouls conceded per"
              " game, centred).  THE D085 CANDIDATE, rebuilt on free throws.  Verdict is taken ONLY"
              " over B_MATCHUP = B_COMPLETE + F02 + M01."),
    dict(name="X02_ftr_x_oppftrate", family="X", level="opp_team_season",
         desc="(F01 own prior FT rate, centred) x (M04 opp prior FT-rate allowed, centred).  The"
              " rate-form interaction.  Verdict ONLY over B_MATCHUP2 = B_COMPLETE + F01 + M04."),

    # ---- G: controls
    dict(name="G01_noise", family="G", level="row",
         desc="NEGATIVE CONTROL: iid gaussian, seed-fixed, independent of everything.  Its dR2 must"
              " be indistinguishable from its own null."),
    dict(name="G02_placebo_noop", family="G", level="row",
         desc="NO-OP PLACEBO: an exact affine copy of the base's FIRST column (2.5*ref_mean + 7).  "
              "Its dR2 must be ~0 BY CONSTRUCTION because it is collinear with the base.  Its"
              " OBSERVED SD across draws is published as this screen's FLOOR OF RESOLUTION.  A"
              " placebo that is a genuine no-op tests nothing about perturbation, so s04 ALSO runs"
              " a PERTURBING placebo (G03) and verifies it moves the statistic."),
    dict(name="G03_placebo_perturbed", family="G", level="row",
         desc="PERTURBATION CHECK: ref_mean with 30%% of rows' values swapped pairwise at random."
              " This MUST move the statistic away from the real value; if it does not, the placebo"
              " machinery is inert and every 'no effect' verdict in this screen is uninformative."),
]

# =====================================================================================
# BASES
# =====================================================================================
BASES = {
    "B_SINGLE": dict(cols=BASE_COLS["B_SINGLE"],
                     desc="ref_mean only.  Reported to EXHIBIT reference incompleteness (D087), "
                          "never to carry a verdict."),
    "B_COMPLETE": dict(cols=BASE_COLS["B_COMPLETE"],
                       desc="EVERY available strictly-prior measurement of the target.  A candidate "
                            "is only ALIVE if it survives this."),
    "B_COMPLETE_PLUS_M02": dict(cols=BASE_COLS["B_COMPLETE"] + ["M02_opp_allowed_fta_pg"],
                                desc="decomposition variant: the base already contains the closest "
                                     "prior OPPONENT measurement of the target.  An M candidate "
                                     "must survive this to be an opponent signal rather than a "
                                     "restatement of opponent FT-allowed volume."),
    "B_MATCHUP": dict(cols=BASE_COLS["B_COMPLETE"] + ["F02_prior_fd_pm", "M01_opp_pf_pg"],
                      desc="D085 GUARD.  BOTH main effects of X01 are in the base FROM THE START. "
                           "X01's verdict is taken here and nowhere else."),
    "B_MATCHUP2": dict(cols=BASE_COLS["B_COMPLETE"] + ["F01_prior_ftr", "M04_opp_allowed_ft_rate"],
                       desc="D085 GUARD for X02.  BOTH main effects in the base from the start."),
}

# candidate -> which bases it is screened over
def bases_for(c):
    f = c["family"]
    if f == "X":
        return ["B_COMPLETE", "B_MATCHUP" if c["name"] == "X01_fd_x_oppfoul" else "B_MATCHUP2"]
    if f == "M":
        return ["B_SINGLE", "B_COMPLETE", "B_COMPLETE_PLUS_M02"]
    return ["B_SINGLE", "B_COMPLETE"]


def targets_for(c):
    ts = list(TARGET_ORDER)
    if c["name"] == "F07_prior_hurdle_rate":
        ts = [t for t in ts if t != "y_any_fta"]          # identical to ref_mean there
    return ts


CELLS = []
for c in CANDIDATES:
    for b in bases_for(c):
        if b == "B_COMPLETE_PLUS_M02" and c["name"] == "M02_opp_allowed_fta_pg":
            continue                                       # a column cannot be screened over itself
        for t in targets_for(c):
            CELLS.append(dict(candidate=c["name"], base=b, target=t))

STRATA = {
    "POOLED": "all appeared player-games (minutes>0) in the headline seasons",
    "DECISION": ("n_prior >= 8 AND trailing-5 mean minutes >= 24 -- D081 s06's decision-relevant "
                 "stratum, so figures are comparable with D081/D085/D089/D097"),
}
# CONDITIONAL targets additionally restrict to fta>0 INSIDE each stratum.  D099: the resulting dR2
# is on THAT SUBSET'S SST and is labelled as such in every table.

PREREG = dict(
    screen_id="E0_I0029_freethrow_hurdle",
    question=("Free-throw production is a HURDLE PROCESS -- P(any attempt), attempts given one, "
              "conversion given attempts.  Which stage carries the predictability, does the "
              "opponent's prior fouls-conceded rate add anything beyond the player's own prior "
              "rate once BOTH main effects are in the base (D085), and does any of it reach a "
              "points forecast with an arithmetic ceiling above the dead benchmarks?"),
    targets={k: TARGETS[k] for k in TARGET_ORDER},
    candidates=CANDIDATES,
    bases={k: v for k, v in BASES.items()},
    cells=CELLS,
    strata=STRATA,
    fixed_analysis_choices=dict(
        partition=list(SEASONS),
        headline_seasons=list(HEADLINE_SEASONS),
        holdout_never_read=[2025, 2026],
        rows="appeared player-games only (minutes > 0), data/masters/master_player.parquet",
        r2_convention="plain unweighted OLS R2, SST about the UNWEIGHTED mean (D069)",
        history_minutes_floor_primary=HISTORY_FLOOR,
        history_minutes_floor_sensitivity=[0.0, 5.0, 10.0, 15.0, 20.0],
        floor_note=("THE FLOOR IS APPLIED TO THE HISTORY ONLY -- which prior games contribute to a "
                    "per-minute rate estimate.  It is NEVER applied to the response, because "
                    "filtering the response conditions on an outcome (D091 ruling 3).  The fta>0 "
                    "restriction on the CONDITIONAL targets IS a response condition; that is the "
                    "whole point of a hurdle decomposition, and it is why those stages are "
                    "reported on a labelled subset denominator and are re-expressed on the COMMON "
                    "denominator by the stage-substitution in s04 before any stage is compared to "
                    "any other."),
        ewma_halflife=EWMA_HALFLIFE,
        n_draws=N_DRAWS,
        seed=SEED,
        nulls=("N_ROW (naive, reported for INFLATION ONLY, never a verdict); N_CYCLIC (within-"
               "player cyclic shift, D093 -- a plain shuffle is anticonservative for running-mean "
               "regressors) for player_season candidates; N_ENTITY_SWAP at opponent-team-season "
               "for opp_team_season candidates.  p_correct_level = MAX over the applicable "
               "entity-level nulls.  Cluster-robust SEs are NOT used as a substitute: they moved t "
               "the WRONG way in two screens in this programme."),
        family_wise=("max-t across all cells sharing a target family, standardised by each cell's "
                     "own null mean/sd"),
        ceiling_form=("D084/D089 form: CEILING_dr2 = (|beta| * sd_candidate / sd_y)^2, the variance "
                      "share reachable if 1 sd of the signal moves the target by beta*sd.  "
                      "Benchmarks: 0.002057 (D089, largest measured, ALIVE), 0.001127 (D079, "
                      "dead), 0.000129 (D084, dead).  The base-residualised variant is reported "
                      "alongside."),
        oracle_ladder=("D081/D097 shape, PER STAGE.  HONEST rungs REF / H1 EWMA / H2 trailing-5 / "
                       "H3 prior rate(floored) x prior exposure / H4 walk-forward OLS on "
                       "B_COMPLETE.  ORACLE rungs O1 season-mean target / O2 ACTUAL exposure x "
                       "season-mean rate / O3 within-player-season OLS on ACTUAL exposure / O4 "
                       "ACTUAL exposure x floored prior rate / O5 prior exposure x season-mean "
                       "rate.  EXPOSURE is MINUTES for stages A, B and the composites, and "
                       "REALISED FTA for stage C, because conversion is a per-attempt rate and "
                       "minutes are not its exposure.  That substitution is the only deviation "
                       "from D097's ladder and is declared here."),
        common_denominator=("D099.  Stages B and C live on the fta>0 subset.  A dR2 on that "
                            "subset's SST is NOT comparable to one on the full stratum's.  The "
                            "headline 'which stage carries the predictability' question is "
                            "answered ONLY on SST(ftm) over the FULL stratum, by substituting one "
                            "stage at a time into a composed ftm forecast (s04).  Per-stage dR2 on "
                            "each stage's own SST is reported alongside and is never compared "
                            "across stages."),
        champion=("NEVER loaded, never retrained, never refitted.  Whether the champion models "
                  "free throws at all is answered by READING ITS CODE AND ARTIFACT SCHEMAS, not by "
                  "running it."),
        forbidden=["data/w1_truth/player_game_availability.csv", "data/w1_truth/roster_asof.csv",
                   "data/zone_maps/*"],
        tip_time_note=("starter_flag, minutes, fta, ftm, fouls_drawn and pf for the CURRENT game "
                       "are POST-GAME observations.  They appear ONLY as responses, as declared "
                       "ORACLE rungs, or inside F09's strictly-prior aggregation.  No "
                       "contemporaneous value of any of them is ever a feature."),
    ),
)

PREREG_HASH = sha(PREREG)

if __name__ == "__main__":
    hdr("PREREGISTRATION -- no data loaded, no statistic computed")
    print("  candidates : %d" % len(CANDIDATES))
    print("  bases      : %d" % len(BASES))
    print("  targets    : %d" % len(TARGET_ORDER))
    print("  cells      : %d  (candidate x base x target)" % len(CELLS))
    print("  strata     : %d  -> cell RUNS = %d" % (len(STRATA), len(CELLS) * len(STRATA)))
    print("\n  PREREG SHA256 = %s" % PREREG_HASH)
    json.dump(dict(prereg=PREREG, sha256=PREREG_HASH),
              open(os.path.join(OUT, "_prereg.json"), "w"), indent=2, default=str)
    print("  WROTE _prereg.json")
