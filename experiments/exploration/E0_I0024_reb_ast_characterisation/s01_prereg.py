"""E0_I0024 s01 -- PREREGISTRATION.  Writes CANDIDATES_PRESELECTED.md and _prereg.json with a
SHA256 over the candidate list.  NO STATISTIC IS COMPUTED IN THIS FILE and no frame is loaded.

The hash is taken over the fully-specified cell list (target x base x candidate x null level).
Any later addition or removal is reported as an added/dropped count against this hash.
"""
import hashlib
import json
import os
import sys

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
OUT = os.path.join(ROOT, r"experiments\exploration\E0_I0024_reb_ast_characterisation")
sys.dont_write_bytecode = True

# ---------------------------------------------------------------- targets
TARGETS = {
    "y_oreb": "offensive rebounds, player-game count",
    "y_dreb": "defensive rebounds, player-game count",
    "y_reb":  "total rebounds, player-game count (oreb+dreb; identity asserted against box `reb`)",
    "y_ast":  "assists, player-game count",
    "y_pts":  "points -- CALIBRATION ANCHOR ONLY.  Already characterised by D081.  Carried through "
              "the identical ladder/ceiling machinery so the rebound and assist numbers are "
              "compared to points ON THIS FRAME rather than across frames.  No new claim is made "
              "about points.",
}

# ---------------------------------------------------------------- bases
BASES = {
    "B_SINGLE": ["ref_mean"],
    "B_COMPLETE": [
        "ref_mean",          # expanding prior mean of the target
        "ref_ewma",          # EWMA of prior target, halflife 5 games
        "ref_trail5",        # trailing-5 prior mean of the target
        "ref_rate_x_min",    # (FLOORED prior per-minute rate) x (prior mean minutes)
        "ref_mean_minutes",  # prior mean minutes
        "ref_trail5_minutes",
        "ref_pct",           # prior mean of the matching advanced percentage
        "ref_mean_pace",     # prior mean pace (opportunity volume)
        "n_prior",           # history depth
        "is_home",
    ],
}
BASE_NOTE = ("D087 REFERENCE INCOMPLETENESS is the top-ranked explanation for this programme's "
             "nulls.  B_COMPLETE puts EVERY available strictly-prior measurement of the target in "
             "the base.  A candidate is only reported as alive if it survives B_COMPLETE.")

# ---------------------------------------------------------------- candidates
# level = the entity at which the candidate VARIES, and therefore the level of the correct null.
CANDIDATES = [
    # --- Family R: SHOT-LOCATION MIX -> REBOUNDS (D087/D074/D079 upstream) ---
    ("R01_opp_allowed_miss_pg",   "opp team's strictly-prior mean MISSED field goals allowed per game (box)",         "opp_team_season", "R"),
    ("R02_opp_allowed_ra_share",  "opp team's strictly-prior share of ALLOWED attempts from Restricted Area",         "opp_team_season", "R"),
    ("R03_opp_allowed_atb3_share","opp team's strictly-prior share of ALLOWED attempts Above the Break 3",            "opp_team_season", "R"),
    ("R04_opp_allowed_mid_share", "opp team's strictly-prior share of ALLOWED attempts Mid-Range",                    "opp_team_season", "R"),
    ("R05_opp_allowed_long_miss_pg","opp team's strictly-prior MISSED 3PA allowed per game (long rebounds)",          "opp_team_season", "R"),
    ("R06_own_atb3_share",        "own team's strictly-prior share of OWN attempts Above the Break 3",                "team_season",     "R"),
    ("R07_own_miss_pg",           "own team's strictly-prior mean MISSED field goals per game",                       "team_season",     "R"),
    ("R08_player_ra_share",       "player's OWN strictly-prior share of own attempts from Restricted Area",           "player_season",   "R"),
    ("R09_opp_allowed_paint_share","opp team's strictly-prior share of ALLOWED attempts in the paint (RA + non-RA)",  "opp_team_season", "R"),
    ("R10_opp_allowed_oreb_pg",   "opp team's strictly-prior mean OFFENSIVE rebounds ALLOWED per game (box) -- the "
                                  "closest prior opponent measurement of the target; also used as an EXTRA base "
                                  "column in the decomposition variant B_COMPLETE_PLUS_R10",                          "opp_team_season", "R"),
    # --- Family A: TEAMMATE AVAILABILITY -> ASSISTS (D089 upstream) ---
    ("A01_c04_prevgame",          "sum of strictly-prior per-game USAGE of the OTHER players who appeared in the "
                                  "team's PREVIOUS game box.  Construction credited to D089 "
                                  "E1_I0018_teammate_volume_channel/s01_build_frame.py (P01_c04_prevgame), "
                                  "reproduced here, READ-ONLY.  The TIP-TIME variant T01 is a POST-GAME "
                                  "observation and is NEVER BUILT.",                                                  "team_season",     "A"),
    ("A02_n_present_prevgame",    "count of players in the team's PREVIOUS game box (D089 P05)",                       "team_season",     "A"),
    ("A03_absent_usg_prevgame",   "strictly-prior usage of players ABSENT from the previous game box (D089 P04)",      "team_season",     "A"),
    ("A04_teammate_prior_fgm_pg", "sum of strictly-prior per-game FGM of the OTHER players in the previous game box "
                                  "-- an assist requires a teammate to MAKE a shot, so this is the "
                                  "mechanism-specific form of A01",                                                    "team_season",     "A"),
    ("A05_teammate_prior_fgpct",  "usage-weighted strictly-prior FG% of the OTHER players in the previous game box",    "team_season",     "A"),
    # --- controls ---
    ("G01_noise",                 "NEGATIVE CONTROL: iid gaussian, seed-fixed, independent of everything",             "row",             "G"),
    ("G02_placebo_noop",          "NO-OP PLACEBO: an exact affine copy of the base's first column.  Its dR2 must be "
                                  "~0 by construction; its OBSERVED SD across draws is reported as the floor of "
                                  "resolution of this screen.",                                                        "row",             "G"),
]

# ---------------------------------------------------------------- cell map
# which candidate families are tested against which targets
CELL_MAP = [
    # primary
    ("y_oreb", "R"), ("y_dreb", "R"), ("y_reb", "R"),
    ("y_ast",  "A"),
    # SPECIFICITY CROSS-TESTS: the assist signal on rebounds and the rebound signal on assists.
    # A signal that fires everywhere is a frame artefact, not a mechanism.
    ("y_oreb", "A_SPEC"), ("y_dreb", "A_SPEC"), ("y_reb", "A_SPEC"),
    ("y_ast",  "R_SPEC"),
    # controls on every target
    ("y_oreb", "G"), ("y_dreb", "G"), ("y_reb", "G"), ("y_ast", "G"), ("y_pts", "G"),
]
SPEC_A = ["A01_c04_prevgame"]      # the single best-evidenced assist candidate, on rebound targets
SPEC_R = ["R01_opp_allowed_miss_pg"]  # the single best-evidenced rebound candidate, on assists

byfam = {}
for nm, desc, lvl, fam in CANDIDATES:
    byfam.setdefault(fam, []).append(nm)

CELLS = []
for tgt, fam in CELL_MAP:
    if fam == "A_SPEC":
        names = SPEC_A
    elif fam == "R_SPEC":
        names = SPEC_R
    else:
        names = byfam[fam]
    for nm in names:
        for b in ["B_SINGLE", "B_COMPLETE"]:
            CELLS.append(dict(target=tgt, base=b, candidate=nm))
# the decomposition variant demanded by constraint 4: rebound candidates against a base that
# ALREADY CONTAINS the closest opponent measurement of the target.
for tgt in ["y_oreb", "y_dreb", "y_reb"]:
    for nm in [c for c in byfam["R"] if c != "R10_opp_allowed_oreb_pg"]:
        CELLS.append(dict(target=tgt, base="B_COMPLETE_PLUS_R10", candidate=nm))

# ---------------------------------------------------------------- fixed analysis choices
CHOICES = dict(
    partition="seasons 2021-2024 only; HEADLINE = 2022-2024 (matching D081's reproduction rows); "
              "2021 reported only as a labelled power sensitivity.  2025/2026 never read.",
    rows="appeared player-games only (minutes > 0), master_player.parquet",
    decision_stratum="n_prior >= 8 AND trailing-5 mean minutes >= 24 -- D081 s06's decision-"
                     "relevant stratum, so figures are comparable with D081/D085/D089",
    history_minutes_floor_primary=10.0,
    history_minutes_floor_sensitivity=[0.0, 5.0, 10.0, 15.0, 20.0],
    floor_note="THE FLOOR IS APPLIED TO THE HISTORY ONLY -- which prior games contribute to a "
               "per-minute rate estimate.  It is NEVER applied to the response, because filtering "
               "the response conditions on an outcome (D091 ruling 3).  D093 measured a response "
               "floor removing 39.3% of per-minute variance; that is a measurement result, not a "
               "licence to filter the response here.",
    ewma_halflife=5.0,
    r2_convention="plain unweighted OLS R2, SST about the UNWEIGHTED mean (D069)",
    n_draws=600,
    seed=20260808,
    nulls="N_ROW (naive, reported for INFLATION ONLY, never a verdict); "
          "N_ENTITY_SWAP at the candidate's declared level (whole entity time-series reassigned "
          "within season, preserving serial structure); "
          "N_CYCLIC (within-player cyclic shift, D093's autocorrelation trap -- a plain shuffle is "
          "anticonservative, p 0.0015 vs an honest 0.39, implementation credited to "
          "E1_I0021_heterogeneity_diagnostic/hd_base.py, READ-ONLY).  "
          "p_correct_level = MAX over the applicable entity-level nulls.",
    family_wise="max-t across all cells sharing a target family, standardised by each cell's own "
                "null mean/sd",
    ceiling_form="D084/D089 form: CEILING_dr2 = (|beta| * sd_candidate / sd_y)^2, i.e. the variance "
                 "share reachable if 1 sd of the signal moves the target by beta*sd.  Benchmarks: "
                 "0.002057 (D089, largest measured, alive), 0.001127 (dead), 0.000129 (dead).  The "
                 "base-residualised variant is reported alongside.",
    oracle_ladder="REF/H honest rungs (strictly prior only) vs O1 season-mean target, O2 ACTUAL "
                  "minutes x season-mean rate, O3 within-player-season OLS on ACTUAL minutes, "
                  "O4 ACTUAL minutes x honest prior rate, O5 honest prior minutes x season-mean "
                  "rate.  D081's ladder shape, with the champion rungs omitted BECAUSE NO CHAMPION "
                  "REBOUND OR ASSIST FORECAST EXISTS (D088).",
    champion="NEVER loaded, never retrained, never refitted.  D088 established the champion carries "
             "no rebound and no assist forecast, which is why this screen exists.",
    forbidden=["data/w1_truth/player_game_availability.csv", "data/w1_truth/roster_asof.csv",
               "data/zone_maps/*"],
    forbidden_note="NOT OPENED.  Availability is rebuilt from box membership (minutes>0), the D076 "
                   "method.  Zones are derived from raw per-shot SHOT_ZONE_BASIC in "
                   "data/shotcharts/, which carries NO MANIFEST and is therefore reported as "
                   "UNVERIFIABLE; row-granularity value evidence was reproduced in s00b at "
                   "1.000000 of 132,558 rows and is a MITIGATION, not a manifest.",
)

payload = dict(screen_id="E0_I0024_reb_ast_characterisation",
               targets=TARGETS, bases=BASES, base_note=BASE_NOTE,
               candidates=[dict(name=n, desc=d, level=l, family=f) for n, d, l, f in CANDIDATES],
               cells=CELLS, choices=CHOICES)
blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
HASH = hashlib.sha256(blob.encode("utf-8")).hexdigest()
payload["prereg_sha256"] = HASH
payload["n_cells"] = len(CELLS)
payload["n_candidates"] = len(CANDIDATES)

json.dump(payload, open(os.path.join(OUT, "_prereg.json"), "w"), indent=2)

lines = []
lines.append("# E0_I0024 -- PRESELECTED CANDIDATES (preregistered before any statistic)\n")
lines.append("**PREREG SHA256 = `%s`**\n" % HASH)
lines.append("- candidates: **%d**" % len(CANDIDATES))
lines.append("- cells (target x base x candidate): **%d**" % len(CELLS))
lines.append("- added since hash: **0**   dropped since hash: **0**  (updated by s05 if this changes)\n")
lines.append("This list was fixed and hashed by `s01_prereg.py`, which loads no data and computes "
             "no statistic. Any later change is reported as an added/dropped count against the "
             "hash above.\n")
lines.append("## Targets\n")
for k, v in TARGETS.items():
    lines.append("- `%s` -- %s" % (k, v))
lines.append("\n## Bases\n")
lines.append(BASE_NOTE + "\n")
for k, v in BASES.items():
    lines.append("- **%s**: `%s`" % (k, "`, `".join(v)))
lines.append("- **B_COMPLETE_PLUS_R10**: B_COMPLETE + `R10_opp_allowed_oreb_pg` -- the "
             "decomposition variant. A rebound candidate must survive against a base that already "
             "contains the closest prior *opponent* measurement of the target.\n")
lines.append("\n## Candidates\n")
lines.append("| name | family | varies at (null level) | description |")
lines.append("|---|---|---|---|")
for n, d, l, f in CANDIDATES:
    lines.append("| `%s` | %s | `%s` | %s |" % (n, f, l, d.replace("\n", " ")))
lines.append("\n## Fixed analysis choices\n")
for k, v in CHOICES.items():
    lines.append("- **%s**: %s" % (k, v))
open(os.path.join(OUT, "CANDIDATES_PRESELECTED.md"), "w", encoding="utf-8").write(
    "\n".join(lines) + "\n")

print("PREREG SHA256 = %s" % HASH)
print("candidates = %d   cells = %d" % (len(CANDIDATES), len(CELLS)))
from collections import Counter
print("cells by target: %s" % dict(Counter(c["target"] for c in CELLS)))
print("cells by base:   %s" % dict(Counter(c["base"] for c in CELLS)))
print("WROTE CANDIDATES_PRESELECTED.md, _prereg.json")
