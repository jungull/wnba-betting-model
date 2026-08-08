"""S00 -- PREREGISTRATION.  Writes CANDIDATES_PRESELECTED.md and hashes it BEFORE any statistic.

Nothing in this file reads an outcome.  It is run first, its hash is recorded, and s02..s06 assert
that the file on disk still hashes to the recorded value.
"""
from __future__ import annotations

import json
import os

import ha_base as hb

PREREG_MD = os.path.join(hb.OUT, "CANDIDATES_PRESELECTED.md")
PREREG_JSON = os.path.join(hb.OUT, "_prereg.json")

# --------------------------------------------------------------------------- the candidate list
# Every quantity whose home-minus-away contrast this screen will report.  Fixed here, before any
# statistic is computed, so the family size used for multiplicity control is not chosen after
# seeing which cells moved.
TEAM_CANDIDATES = [
    ("pts", "team points"),
    ("poss", "possessions, box estimator FGA-OREB+TOV+0.44*FTA"),
    ("ppp", "points per possession"),
    ("minutes", "team minutes played (the shared budget)"),
    ("fga", "field goal attempts"),
    ("fg2a", "two-point attempts"),
    ("fg3a", "three-point attempts"),
    ("fta", "free throw attempts"),
    ("fgm", "field goals made"),
    ("fg2m", "two-point makes"),
    ("fg3m", "three-point makes"),
    ("ftm", "free throws made"),
    ("fg_pct", "field goal percentage"),
    ("fg2_pct", "two-point percentage"),
    ("fg3_pct", "three-point percentage"),
    ("ft_pct", "free throw percentage"),
    ("efg_pct", "effective field goal percentage"),
    ("ts_pct", "true shooting percentage"),
    ("oreb", "offensive rebounds"),
    ("dreb", "defensive rebounds"),
    ("tov", "turnovers"),
    ("ast", "assists"),
    ("pf", "personal fouls"),
    ("fouls_drawn", "fouls drawn"),
    ("pts_per_min", "team points per team minute"),
]

PLAYER_CANDIDATES = [
    ("pts", "player points"),
    ("minutes", "player minutes"),
    ("ppm", "player points per minute"),
    ("fga", "player field goal attempts"),
    ("fga_per_min", "player FGA per minute"),
    ("fta", "player free throw attempts"),
    ("fta_per_min", "player FTA per minute"),
    ("fg3a", "player three-point attempts"),
    ("efg_pct", "player effective field goal percentage"),
    ("ts_pct", "player true shooting percentage"),
    ("n_players_used", "number of players with minutes > 0 per team-game"),
    ("hhi_minutes", "Herfindahl concentration of the minutes distribution"),
    ("starter_minute_share", "share of team minutes taken by starters"),
]

# --------------------------------------------------------------------------- forecast test
MAIN_EFFECT_SPEC = {
    "targets": ["pts", "minutes", "ppm", "fga"],
    "references": {
        "REF_EXPANDING_COMPLETE": (
            "expanding mean over EVERY prior game of the player in the same season, "
            "strictly earlier date; falls back to the player's whole previous season, then to the "
            "same-season strictly-prior league mean.  COMPLETE in the required sense: it uses every "
            "available prior measurement of the target in the base, not a truncated window."),
        "REF_EWMA8_COMPLETE": (
            "EWMA half-life 8 games over EVERY prior game of the player in the same season, same "
            "fallback chain.  Included because E1_I0022 (D0xx ANSWER.md) showed the programme's "
            "long-standing running-mean baseline is beatable by 1.3-7.8%, so a home/away term must "
            "clear the STRONGER reference to count."),
        "REF_VENUE_SPLIT_EXPANDING": (
            "expanding mean over the player's prior games AT THE SAME VENUE TYPE (home games use "
            "prior home games only; away games use prior away games only), same fallback chain "
            "ending at the ALL-GAMES expanding mean.  This is the DIRECT TEST OF REFERENCE "
            "ABSORPTION: if a home/away increment is real but hidden inside a blended reference, "
            "splitting the reference by venue must recover it."),
        "REF_VENUE_SPLIT_EWMA8": "as above with EWMA half-life 8.",
    },
    "increment_under_test": (
        "ADD a single home/away main-effect term to the reference: yhat = ref + beta*(is_home - "
        "mean_is_home), with beta estimated WALK-FORWARD on strictly earlier seasons only.  This is "
        "the MAIN-EFFECT test.  D076 screened home/away as a predictor of |residual| -- WHERE THE "
        "MODEL ERRS -- which is a different question and is not this one."),
    "evaluation": ("walk-forward: fit beta on seasons < s, score season s, for s in {2022,2023,"
                   "2024}.  Reported POOLED and on the D081 DECISION STRATUM (>=8 prior "
                   "appearances in season AND trailing-5-game mean minutes >=24)."),
    "denominator_rule_D099": (
        "every dR2 and every skill number is reported on a COMMON DENOMINATOR -- the SST / MAE of "
        "the FULL pooled evaluation stratum -- and the subset-SST version is reported beside it and "
        "labelled, never substituted."),
}

# --------------------------------------------------------------------------- TRAVEL: DIRECTION
# *** PREREGISTERED DIRECTIONAL HYPOTHESIS, FIXED BEFORE ANY STATISTIC IS COMPUTED. ***
TRAVEL_PREREG = {
    "zone_definition": (
        "each venue's UTC CLOCK OFFSET during the WNBA season (all games fall in US daylight-saving "
        "time), taken from data/reference/team_cities.csv timezone strings.  America/Phoenix does "
        "NOT observe DST, so in season Phoenix's clock EQUALS Pacific's and a PHO<->LAS/LVA/SEA trip "
        "is a SAME-ZONE trip.  Using the timezone STRING as the zone would manufacture crossings "
        "that do not exist; the offset is used instead."),
    "construction": (
        "for each team-game, tz_delta = utc_offset(this game's venue) - utc_offset(the venue of that "
        "team's IMMEDIATELY PRECEDING game in the same season).  Strictly prior schedule only.  A "
        "team's first game of a season has no predecessor and is excluded from the travel arms."),
    "sign_convention": "tz_delta > 0 means the team moved EAST (to a later local clock).",
    "DIRECTIONAL_HYPOTHESIS": (
        "EASTBOUND crossings (tz_delta >= +1) HURT the travelling team, because an eastward shift "
        "requires a circadian PHASE ADVANCE, which is the harder direction and the one with an "
        "established literature.  PREDICTED SIGN: NEGATIVE effect of eastbound on the team's points "
        "and on the team's points per possession.  This sign is fixed now; a positive effect of "
        "eastbound travel is a REFUTATION of the mechanism, not a finding."),
    "internal_controls": {
        "WESTBOUND": ("tz_delta <= -1.  Phase DELAY, the easier direction.  If westbound shows the "
                      "same size effect as eastbound, the mechanism is refuted -- what is being "
                      "measured is travel or schedule, not circadian disruption."),
        "SAME_ZONE_TRAVEL": ("tz_delta == 0 but a DIFFERENT venue from the previous game.  Real "
                             "travel, no circadian component.  Same refutation logic."),
        "NO_TRAVEL": "same venue as the previous game (a home stand, or a two-game road set).",
    },
    "known_trap_disclosed": (
        "rest and schedule state have died in FOUR screens across THREE targets in this programme.  "
        "Eastbound travel is correlated with rest days and with road-trip position, so this arm must "
        "clear a HIGH bar and the screen must say plainly whether it is that dead family in new "
        "clothes.  Rest days and the home/away indicator are therefore included as covariates in the "
        "adjusted arm, and the raw and adjusted contrasts are both reported."),
    "null": (
        "tz_delta varies WITHIN a team-season and is NOT balanced within a game, so neither the "
        "paired game sign-flip nor a between-group permutation applies.  The null is a CYCLIC SHIFT "
        "of the travel indicator within each (season, team_id) series, date-ordered -- it preserves "
        "the marginal distribution AND the schedule's serial structure (road trips come in runs) and "
        "destroys only the alignment to the outcome.  A within-group SHUFFLE is refused: the K6 "
        "defect, and D093 measured a shuffle-vs-cyclic gap tracking regressor autocorrelation at "
        "+0.83."),
}

HETEROGENEITY_PREREG = {
    "question": "does the home/away effect differ ACROSS PLAYERS beyond sampling noise?",
    "statistic": ("spread (sd, and IQR) of the per-player home-minus-away mean difference in the "
                  "target, over players with >= 20 home and >= 20 away appearances in 2021-2024"),
    "null": ("CYCLIC SHIFT of is_home within each player's date-ordered series (K6 / D093).  A "
             "within-player SHUFFLE is NOT used: D093 found an apparent heterogeneity that was "
             "entirely an artefact of the shuffle destroying serial structure and that vanished "
             "under the cyclic shift."),
    "vacuous_control_run_anyway": (
        "the relabel-the-player-key arm is run and REPORTED, because it is the control an analyst "
        "reaches for first and it is a literal no-op (K7).  Reporting it as a no-op is the point."),
    "D093_ceiling_noted": ("per-player models LOST to the player's own average on every one of five "
                          "best-sampled players; this screen does not claim otherwise."),
}

NEGATIVE_CONTROLS = {
    "NC1_shuffled_home": ("is_home replaced by a random half-and-half label assigned per game "
                          "(one team gets 1, the other 0).  Must show no effect."),
    "NC2_jersey_parity": ("parity of the team_id integer -- a genuinely meaningless team-game "
                          "attribute balanced-ish within games.  Must show no effect."),
    "NC3_noop_placebo": ("the identity transform, run through screenkit.noop_placebo, to prove the "
                         "harness reports a vacuous control as vacuous.  Beside it, a placebo that "
                         "MUST perturb (the per-game sign flip itself) with its observed sd, to "
                         "prove the real control is not the identity."),
}


def render():
    L = []
    L.append("# E1_I0030 -- PRESELECTED CANDIDATES AND PREREGISTERED DIRECTION")
    L.append("")
    L.append("Written and hashed by `s00_prereg.py` BEFORE any statistic was computed. "
             "`s02`-`s06` re-hash this file at run time and refuse to proceed if it has changed.")
    L.append("")
    L.append("Partition: **2021-2024 only**. 2025 and 2026 are never read, joined, plotted or "
             "described.")
    L.append("")
    L.append("## 1. Team-level candidates (home minus away, within-game paired)")
    L.append("")
    L.append("| # | column | meaning |")
    L.append("|---|---|---|")
    for i, (c, d) in enumerate(TEAM_CANDIDATES, 1):
        L.append("| %d | `%s` | %s |" % (i, c, d))
    L.append("")
    L.append("## 2. Player-level candidates (home minus away)")
    L.append("")
    L.append("| # | column | meaning |")
    L.append("|---|---|---|")
    for i, (c, d) in enumerate(PLAYER_CANDIDATES, 1):
        L.append("| %d | `%s` | %s |" % (i, c, d))
    L.append("")
    L.append("**Family size for multiplicity control: %d team cells + %d player cells = %d.**"
             % (len(TEAM_CANDIDATES), len(PLAYER_CANDIDATES),
                len(TEAM_CANDIDATES) + len(PLAYER_CANDIDATES)))
    L.append("")
    L.append("## 3. The main-effect forecast test")
    L.append("")
    for k, v in MAIN_EFFECT_SPEC.items():
        if isinstance(v, dict):
            L.append("**%s**" % k)
            L.append("")
            for kk, vv in v.items():
                L.append("- `%s` -- %s" % (kk, vv))
            L.append("")
        elif isinstance(v, list):
            L.append("**%s**: %s" % (k, ", ".join("`%s`" % x for x in v)))
            L.append("")
        else:
            L.append("**%s**: %s" % (k, v))
            L.append("")
    L.append("## 4. TRAVEL -- the preregistered direction")
    L.append("")
    for k, v in TRAVEL_PREREG.items():
        if isinstance(v, dict):
            L.append("**%s**" % k)
            L.append("")
            for kk, vv in v.items():
                L.append("- `%s` -- %s" % (kk, vv))
            L.append("")
        else:
            L.append("**%s**: %s" % (k, v))
            L.append("")
    L.append("## 5. Heterogeneity")
    L.append("")
    for k, v in HETEROGENEITY_PREREG.items():
        L.append("**%s**: %s" % (k, v))
        L.append("")
    L.append("## 6. Negative controls and placebo")
    L.append("")
    for k, v in NEGATIVE_CONTROLS.items():
        L.append("- `%s` -- %s" % (k, v))
    L.append("")
    L.append("## 7. What would count as the effect being LOCATED")
    L.append("")
    L.append("The reconciliation is the deliverable and it cannot return 'nothing'. It is complete "
             "when, for the team-level home-minus-away points gap `G`:")
    L.append("")
    L.append("1. the sum over players of the player-level home-minus-away points contribution "
             "equals `G` to within floating-point error, and")
    L.append("2. `G` is expressed as an EXACT identity in components "
             "(`G = 2*dFG2M + 3*dFG3M + dFTM`), each of which is further split into a VOLUME part "
             "and an ACCURACY part, and")
    L.append("3. the shared-budget facts (team minutes, possessions) are measured rather than "
             "assumed, so that any component that CANNOT carry the effect is shown to be unable to "
             "rather than merely found small.")
    L.append("")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    hb.hdr("S00 PREREGISTRATION")
    txt = render()
    with open(PREREG_MD, "w", encoding="utf-8") as fh:
        fh.write(txt)
    h = hb.sha256_file(PREREG_MD)
    rec = {
        "prereg_file": os.path.basename(PREREG_MD),
        "prereg_sha256": h,
        "n_team_candidates": len(TEAM_CANDIDATES),
        "n_player_candidates": len(PLAYER_CANDIDATES),
        "family_size": len(TEAM_CANDIDATES) + len(PLAYER_CANDIDATES),
        "team_candidates": [c for c, _ in TEAM_CANDIDATES],
        "player_candidates": [c for c, _ in PLAYER_CANDIDATES],
        "travel_prereg": TRAVEL_PREREG,
        "main_effect_spec": MAIN_EFFECT_SPEC,
        "heterogeneity_prereg": HETEROGENEITY_PREREG,
        "negative_controls": NEGATIVE_CONTROLS,
        "seed": hb.SEED,
    }
    with open(PREREG_JSON, "w", encoding="utf-8") as fh:
        json.dump(rec, fh, indent=2)
    print("  wrote %s" % PREREG_MD)
    print("  SHA256 = %s" % h)
    print("  family size = %d" % rec["family_size"])
    print("  PREREGISTERED DIRECTION: eastbound (tz_delta >= +1) HURTS the travelling team "
          "(negative on points and on points per possession).")


def assert_prereg_unchanged():
    """Called by every downstream stage."""
    import json as _json
    with open(PREREG_JSON, "r", encoding="utf-8") as fh:
        rec = _json.load(fh)
    now = hb.sha256_file(PREREG_MD)
    assert now == rec["prereg_sha256"], (
        "PREREGISTRATION CHANGED after hashing: %s != %s" % (now, rec["prereg_sha256"]))
    return rec
