"""
s00 -- PREREGISTRATION.  Runs BEFORE any statistic is computed.

Writes CANDIDATES_PRESELECTED.md and _prereg.json, both carrying a SHA-256 over the relationship
list, the minutes-floor grid, the headline settings and the inference settings.  Every later script
RE-HASHES the list it actually uses and asserts the hash is unchanged, and reports added/dropped
counts.  That converts "we preregistered" from a claim into a checkable fact (D085 ruling 4).
"""
import json
import os
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import hd_base as hb  # noqa: E402

# ---------------------------------------------------------------- the preregistered grid
MINUTES_FLOOR_GRID = [0, 10, 15, 20, 25, 30]

# Headline floor for the pooling diagnostic, fixed A PRIORI before any spread was computed.
# 20 realised minutes is chosen as "a rotation player played a real game", not by evidence.
HEADLINE_FLOOR = 20
MIN_GAMES_PER_PLAYER = 8
N_DRAWS = 2000
SEED = 20260808

# ---------------------------------------------------------------- the preregistered relationships
# Each entry: id, frame, x column, y column, why it is on the list, and the sign the program's
# earlier pooled work would predict.  NOTHING is added after seeing a result.
RELATIONSHIPS = [
    {"id": "R01_prior_efficiency_persistence", "frame": "D085_eff", "x": "refA_ppm_floor",
     "y": "y_ppm_floor", "source": "D081 (E0_I0015) -- points-per-minute vs the player's own "
     "strictly-prior expanding mean rate; the persistence term the whole program leans on",
     "expected_sign": "positive"},
    {"id": "R02_opp_efg_allowed", "frame": "D085_eff", "x": "A01_opp_efg_allowed",
     "y": "y_ppm_floor", "source": "D085 (E0_I0016) opponent-allowance family, cell A01",
     "expected_sign": "positive"},
    {"id": "R03_opp_ts_allowed", "frame": "D085_eff", "x": "A02_opp_ts_allowed",
     "y": "y_ppm_floor", "source": "D085 (E0_I0016) opponent-allowance family, cell A02",
     "expected_sign": "positive"},
    {"id": "R04_opp_defrtg", "frame": "D085_eff", "x": "A10_opp_defrtg",
     "y": "y_ppm_floor", "source": "D085 (E0_I0016) opponent-allowance family, cell A10",
     "expected_sign": "positive"},
    {"id": "R05_teammate_volume_pregame", "frame": "D089_tv", "x": "P01_c04_prevgame",
     "y": "y_ppm_floor", "source": "D089 (E1_I0018) teammate-volume channel, STRICTLY PRE-GAME "
     "variant. The tip-time variant T01 is deliberately EXCLUDED: D089 ruling 2 forbids quoting it "
     "as a result because it is computed from a post-game observation",
     "expected_sign": "negative"},
    {"id": "R06_own_usage", "frame": "D089_tv", "x": "O01_own_usg_pg",
     "y": "y_ppm_floor", "source": "D089 (E1_I0018) own-usage term, the player-side half of the "
     "volume channel", "expected_sign": "positive"},
]

NEGATIVE_CONTROLS = [
    {"id": "NC1_noise_eff_frame", "frame": "D085_eff", "x": "G01_noise", "y": "y_ppm_floor",
     "source": "pure noise column frozen into D085's screen frame"},
    {"id": "NC2_noise_tv_frame", "frame": "D089_tv", "x": "G01_noise", "y": "y_ppm_floor",
     "source": "pure noise column frozen into D089's screen frame"},
]

# ---------------------------------------------------------------- step-1 components (frozen)
STEP1_COMPONENTS = [
    {"component": "minutes", "kind": "LEVEL", "y": "y_minutes",
     "model": "minutes__pred_point", "ref_frozen": "ref_minutes", "ref_refit": "refF_minutes"},
    {"component": "fga", "kind": "LEVEL", "y": "y_fga",
     "model": "fga__pred_point", "ref_frozen": "ref_fga", "ref_refit": "refF_fga"},
    {"component": "pts", "kind": "LEVEL", "y": "y_pts",
     "model": "pts__pred_point", "ref_frozen": "ref_pts", "ref_refit": "refF_pts"},
    {"component": "pts_per_min", "kind": "RATE", "y": "r_ppm", "model": "mdl_ppm",
     "ref_frozen": "refA_ppm", "ref_refit": "refFA_ppm"},
    {"component": "pts_per_min", "kind": "RATE", "y": "r_ppm", "model": "mdl_ppm",
     "ref_frozen": "refB_ppm", "ref_refit": "refFB_ppm"},
    {"component": "fga_per_min", "kind": "RATE", "y": "r_fpm", "model": "mdl_fpm",
     "ref_frozen": "refA_fpm", "ref_refit": "refFA_fpm"},
    {"component": "fga_per_min", "kind": "RATE", "y": "r_fpm", "model": "mdl_fpm",
     "ref_frozen": "refB_fpm", "ref_refit": "refFB_fpm"},
    {"component": "pts_per_fga", "kind": "RATE", "y": "r_ppf", "model": "mdl_ppf",
     "ref_frozen": "refA_ppf", "ref_refit": "refFA_ppf"},
    {"component": "pts_per_fga", "kind": "RATE", "y": "r_ppf", "model": "mdl_ppf",
     "ref_frozen": "refB_ppf", "ref_refit": "refFB_ppf"},
]

# ---------------------------------------------------------------- step-3 structure covariates
# Strictly PRE-GAME player characteristics that per-player coefficients are tested against, only if
# step 2 is positive.  Preregistered now so the list cannot be grown to find a correlation.
STRUCTURE_COVARIATES = [
    "usage_tier_prior",      # tercile of the player's own strictly-prior mean usage
    "minutes_tier_prior",    # tercile of the player's own strictly-prior mean minutes
    "role_stability_prior",  # strictly-prior mean of pl_start_frac5 / start-switch behaviour
    "team_pace_prior",       # strictly-prior team possessions per 40
    "experience_prior",      # pl_career_games_prior at the player's first retained game
    "n_games_retained",      # sample size after the floor (a nuisance covariate, reported)
]

PREREG = {
    "screen": "E1_I0021_heterogeneity_diagnostic",
    "partition": [2022, 2023, 2024],
    "minutes_floor_grid": MINUTES_FLOOR_GRID,
    "headline_floor": HEADLINE_FLOOR,
    "min_games_per_player": MIN_GAMES_PER_PLAYER,
    "n_draws": N_DRAWS,
    "seed": SEED,
    "relationships": RELATIONSHIPS,
    "negative_controls": NEGATIVE_CONTROLS,
    "step1_components": STEP1_COMPONENTS,
    "structure_covariates": STRUCTURE_COVARIATES,
    "step2_null_scheme": "WITHIN-PLAYER permutation: each player's own games are shuffled, which "
                         "preserves that player's sample size and their marginal distribution of "
                         "x and destroys ONLY the within-player alignment of x to y. The statistic "
                         "is the SD of per-player slopes, computed by the identical code path on "
                         "the real frame and on every draw.",
    "step2_statistic": "sd of per-player OLS slopes (both precision-weighted and unweighted), "
                       "players with >= min_games rows after the floor",
    "decision_rule": "A relationship is called HETEROGENEOUS only if the observed spread exceeds "
                     "the within-player null at p < 0.05 AND survives the max-statistic family-wise "
                     "null across the 6 preregistered relationships at the headline floor AND its "
                     "negative control does not.",
}

PREREG_HASH = hb.sha(PREREG)


def main():
    os.makedirs(hb.OUT, exist_ok=True)
    PREREG["prereg_sha256"] = PREREG_HASH
    with open(os.path.join(hb.OUT, "_prereg.json"), "w", encoding="utf-8") as fh:
        json.dump(PREREG, fh, indent=2)

    lines = []
    lines.append("# E1_I0021 -- PRESELECTED RELATIONSHIPS AND FLOOR GRID")
    lines.append("")
    lines.append("**SHA-256 of the preregistered block:** `%s`" % PREREG_HASH)
    lines.append("")
    lines.append("Written by `s00_prereg.py` BEFORE any statistic in this screen was computed. "
                 "Every later script re-hashes the list it actually uses and asserts equality, and "
                 "reports added/dropped counts against this file.")
    lines.append("")
    lines.append("## Partition")
    lines.append("")
    lines.append("Seasons 2022-2024 only (the 2021 fold is degenerate: n_train_rows=0). "
                 "2025 and 2026 are never read, joined, plotted or described.")
    lines.append("")
    lines.append("## Minutes-floor grid (realised minutes of the game being scored)")
    lines.append("")
    lines.append("`%s`  -- headline floor for the pooling diagnostic: **%d minutes**, fixed a "
                 "priori as 'a rotation player played a real game', not chosen by evidence."
                 % (MINUTES_FLOOR_GRID, HEADLINE_FLOOR))
    lines.append("")
    lines.append("**CONDITIONING LABEL.** A realised-minutes floor conditions on an OUTCOME. Every "
                 "figure under a floor answers the measurement question 'given a player got "
                 "meaningful minutes, is their rate predictable?' and is NOT a live forecasting "
                 "increment, because a real forecast must predict minutes first.")
    lines.append("")
    lines.append("## Preregistered relationships (%d)" % len(RELATIONSHIPS))
    lines.append("")
    lines.append("| id | frame | x | y | expected sign | why it is on the list |")
    lines.append("|---|---|---|---|---|---|")
    for r in RELATIONSHIPS:
        lines.append("| `%s` | %s | `%s` | `%s` | %s | %s |"
                     % (r["id"], r["frame"], r["x"], r["y"], r["expected_sign"], r["source"]))
    lines.append("")
    lines.append("## Negative controls (%d)" % len(NEGATIVE_CONTROLS))
    lines.append("")
    lines.append("| id | frame | x | y | what it is |")
    lines.append("|---|---|---|---|---|")
    for r in NEGATIVE_CONTROLS:
        lines.append("| `%s` | %s | `%s` | `%s` | %s |"
                     % (r["id"], r["frame"], r["x"], r["y"], r["source"]))
    lines.append("")
    lines.append("## Step-1 components (D081 reproduction targets, %d cells)"
                 % len(STEP1_COMPONENTS))
    lines.append("")
    lines.append("| component | kind | y | model forecast | frozen reference | floor-refit reference |")
    lines.append("|---|---|---|---|---|---|")
    for c in STEP1_COMPONENTS:
        lines.append("| %s | %s | `%s` | `%s` | `%s` | `%s` |"
                     % (c["component"], c["kind"], c["y"], c["model"], c["ref_frozen"],
                        c["ref_refit"]))
    lines.append("")
    lines.append("## Step-3 structure covariates (used ONLY if step 2 is positive, %d)"
                 % len(STRUCTURE_COVARIATES))
    lines.append("")
    for c in STRUCTURE_COVARIATES:
        lines.append("- `%s`" % c)
    lines.append("")
    lines.append("## Inference")
    lines.append("")
    lines.append("- Null scheme: %s" % PREREG["step2_null_scheme"])
    lines.append("- Statistic: %s" % PREREG["step2_statistic"])
    lines.append("- Draws: %d, seed %d, min games per player %d"
                 % (N_DRAWS, SEED, MIN_GAMES_PER_PLAYER))
    lines.append("- Decision rule: %s" % PREREG["decision_rule"])
    lines.append("")
    with open(os.path.join(hb.OUT, "CANDIDATES_PRESELECTED.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    print("PREREG SHA-256: %s" % PREREG_HASH)
    print("relationships=%d negative_controls=%d step1_cells=%d floors=%s headline_floor=%d"
          % (len(RELATIONSHIPS), len(NEGATIVE_CONTROLS), len(STEP1_COMPONENTS),
             MINUTES_FLOOR_GRID, HEADLINE_FLOOR))
    print("wrote CANDIDATES_PRESELECTED.md and _prereg.json")


if __name__ == "__main__":
    main()
