"""s10_assemble.py -- final deliverables.  Assembles FINDINGS.json, promotes the two named
CSVs to the screen root, and concatenates every stage log into run_log.txt.
"""
import glob
import hashlib
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from df_base import HERE, OUT, hdr

BEST_LEAD = 0.0023
CEIL_D079 = 0.001127
CEIL_D084 = 0.000129

prereg = os.path.join(HERE, "PREREGISTRATION.md")
PREREG_SHA = hashlib.sha256(open(prereg, "rb").read()).hexdigest()

mde = pd.read_csv(os.path.join(OUT, "s07_mde_drift_corrected.csv"))
mde_ps = pd.read_csv(os.path.join(OUT, "s09_player_season_swap_mde.csv"))
ALL = pd.concat([mde, mde_ps], ignore_index=True)
ALL.to_csv(os.path.join(HERE, "mde_table.csv"), index=False)

pc = pd.read_csv(os.path.join(OUT, "power_curves.csv"))
pc.to_csv(os.path.join(HERE, "power_curves.csv"), index=False)
rp = pd.read_csv(os.path.join(OUT, "retrospective_power.csv"))
rp.to_csv(os.path.join(HERE, "retrospective_power.csv"), index=False)

sv = pd.read_csv(os.path.join(OUT, "s08_screen_verdicts.csv"))
un = pd.read_csv(os.path.join(OUT, "s08_uninformative_nulls_by_screen.csv"))
cv = pd.read_csv(os.path.join(OUT, "s08_cell_verdicts.csv"))
fw = pd.read_csv(os.path.join(OUT, "s04_familywise_thresholds.csv"))
nvn = pd.read_csv(os.path.join(OUT, "s05_mde_vs_n.csv"))
dr = pd.read_csv(os.path.join(OUT, "s07_null_drift_probe.csv"))
val = pd.read_csv(os.path.join(OUT, "s06_validation_analytic_vs_simulated.csv"))
nm = pd.read_csv(os.path.join(OUT, "s03_null_meta.csv"))


def M(stratum, base, null, K):
    q = ALL[(ALL.stratum == stratum) & (ALL.base == base) & (ALL["null"] == null)
            & (ALL.family_size_K == K)]
    return float(q["mde80_DRIFT_CORRECTED"].iloc[0]) if len(q) else None


NULL_LABEL = {
    "N_A_within_player_cyclic": "within-player cyclic shift",
    "N_B_entity_swap_team_season": "entity swap, team-season",
    "N_C_entity_swap_opp_team_season": "entity swap, opponent-team-season",
    "N_D_within_date_opp_swap": "within-date opponent swap",
    "N_E_entity_swap_player_season": "entity swap, player-season",
}

headline = {}
for stratum in ("DECISION", "POOLED"):
    for base in ("B_SINGLE", "B_COMPLETE"):
        for null in NULL_LABEL:
            for K in (1, 18, 44, 132, 318):
                v = M(stratum, base, null, K)
                if v is not None:
                    headline["%s|%s|%s|K%d" % (stratum, base, null, K)] = v

F = {
    "screen_id": "E1_I0026_detection_floor",
    "character": "E1 DIAGNOSTIC -- a measurement of the programme's own machinery. "
                 "No lead, no result, no promotion, no registry/ledger/graph-event entry.",
    "question": "What is the smallest effect this programme's designs can detect, and how much "
                "of its ~1,000-cell negative record is a power failure rather than a finding?",
    "preregistration": {
        "file": "PREREGISTRATION.md",
        "sha256": PREREG_SHA,
        "hashed_before_any_statistic": True,
        "design_grid_declared": {
            "strata": ["POOLED (n=14,852)", "DECISION (n_prior>=8 & prior5_minutes>=24, n=5,673)"],
            "bases": ["B_SINGLE [1, refB_ppm]",
                      "B_COMPLETE [1, refB_ppm, refB_spm, refB_pps, refB_mpg]"],
            "nulls_declared": 4,
            "row_level_contrast_only": True,
            "effect_grid": "0 plus 25 log-spaced points 1e-5 .. 1e-2",
            "replicates": 2000,
            "family_sizes": [1, 18, 39, 44, 132, 154, 250, 318, 348],
        },
        "added_after_hashing": {
            "count": 1,
            "items": [
                "N_E entity swap at PLAYER-SEASON (s09). Added AFTER the s07 results showed the "
                "two declared player-level nulls sit at 48 and 343/600 clusters and disagree by "
                "3-5x, which made 'is cluster count the binding constraint' answerable and "
                "unanswered. It is a NULL, not a candidate; it cannot manufacture an effect. "
                "Its result is NEGATIVE for the hypothesis that motivated it."],
        },
        "dropped_after_hashing": {"count": 0, "items": []},
        "declared_check_outcome": "FAILED -- see null_width_drift below. The preregistration "
                                  "committed to abandoning the reuse-the-null factorisation if "
                                  "drift exceeded 10%. It did (-76% to +506%), so every headline "
                                  "MDE was recomputed with the null measured ON THE PLANTED "
                                  "RESPONSE (s07). Both the corrected and the uncorrected numbers "
                                  "are on disk.",
    },
    "partition": {"seasons": [2021, 2022, 2023, 2024],
                  "enforced_by": "screenkit.assert_partition (value test) after every load and "
                                 "every filter",
                  "2025_2026_read": False},
    "inputs": {
        "primary_frame": "E1_I0018_teammate_volume_channel/screen_frame.parquet (14,852 rows) "
                         "-- the frame that produced D089, the programme's best-ever lead",
        "joined_frame": "E0_I0016_efficiency_predictors/screen_frame.parquet (opponent columns)",
        "join": "1:1 on (player_id, game_id), lossless, asserted",
        "family_wise_null_matrix": "E1_I0018/permutation_draws.npz -- 154 cells x 600 draws, the "
                                   "programme's own between-cell correlation",
        "kit": "_screen_kit/screenkit.py, imported not copied",
        "structure": {"players": 247, "teams": 12, "games": 827, "dates": 313,
                      "team_seasons": 48, "player_seasons": 600},
    },
    "machinery_checks": {
        "fast_dr2_vs_screenkit_delta_r2_plain_abs_diff": 7.551e-17,
        "closed_form_vs_literal_refit_worst_abs_diff": 1.457e-16,
        "type1_at_delta0_per_cell_range": [
            float(pc["power_per_cell_alpha05"][pc.planted_dr2 == 0].min()),
            float(pc["power_per_cell_alpha05"][pc.planted_dr2 == 0].max())],
        "type1_at_delta0_per_cell_median": float(
            pc["power_per_cell_alpha05"][pc.planted_dr2 == 0].median()),
        "type1_nominal": 0.05,
        "analytic_mde_vs_simulated_median_ratio_familywise": float(val["ratio"].median()),
        "analytic_mde_vs_simulated_median_ratio_percell": float(val["ratio_percell"].median()),
    },
    "null_width_drift": {
        "what_it_is": "relative change in the permutation null's sd when an effect is planted",
        "preregistered_threshold": 0.10,
        "verdict": "EXCEEDED -- factorisation abandoned as preregistered",
        "by_null": {},
    },
    "MDE80_drift_corrected": headline,
    "family_wise_thresholds_q95_maxt": {
        "%s|K%d" % (r.arm, r.K): {"q95_maxt": r.q95_maxt,
                                  "extrapolated": bool(r.extrapolated_beyond_real_family)}
        for r in fw.itertuples()},
    "benchmarks": {"best_ever_lead_D089_walkforward_points_dr2": BEST_LEAD,
                   "arithmetic_ceiling_D079_shot_mix_to_points": CEIL_D079,
                   "arithmetic_ceiling_D084_conversion_to_points": CEIL_D084,
                   "only_prior_resolution_figure_D097": [1.6e-4, 2.2e-4]},
    "retrospective": {
        "cells_with_a_published_null_width": int(len(cv)),
        "screens_covered": int(cv["screen"].nunique()),
        "share_blind_to_best_lead_0.0023_familywise": float(cv["blind_to_best_lead_fw"].mean()),
        "share_blind_to_D079_ceiling_familywise": float(cv["blind_to_D079_ceiling_fw"].mean()),
        "share_blind_to_D084_ceiling_familywise": float(cv["blind_to_D084_ceiling_fw"].mean()),
        "uninformative_nulls_total": int(un["uninformative_nulls"].sum()),
        "by_screen": sv.to_dict("records"),
        "uninformative_nulls_by_screen": un.to_dict("records"),
    },
    "mde_vs_n": nvn.to_dict("records"),
    "where_i_could_have_cheated": [
        "CARRIER CHOICE. Two carriers were fixed in the preregistration before any statistic and "
        "neither was changed. A carrier with more between-entity variance would have flattered "
        "every entity-swap floor.",
        "REUSING THE UNPLANTED NULL WIDTH. Declared with a test that could fail; it DID fail, and "
        "the headline numbers are the recomputed ones. The uncorrected numbers are kept on disk "
        "beside them (s04_mde_table.csv) rather than deleted.",
        "REPORTING THE PER-CELL FLOOR ONLY. The per-cell floor is 1.9-2.3x better than the "
        "family-wise one. Both are reported everywhere and the verdict quotes the family-wise one.",
        "EXTRAPOLATING K > 154. The real null matrix has 154 cells; K in {250, 318, 348} samples "
        "cells with replacement and is flagged in every row of the threshold table. The max-t "
        "threshold is flat from K=132 to K=348, so the extrapolation carries little weight.",
        "STRATUM SHOPPING. Both strata are reported for every null and both are in the verdict.",
        "GRID ENDPOINTS. Fixed at 1e-5..1e-2 in the preregistration, three orders of magnitude "
        "around every ceiling in the ledger.",
        "HINDSIGHT FLAGGING. The retrospective uses only each screen's design -- its published "
        "null width, its n, its family size. No screen's RESULT enters the decision about whether "
        "it was powered.",
        "A SINGLE FRAME. The power curves are measured on ONE frame (D089's). It is the "
        "programme's best-instrumented and most favourable one, so the floors here are if "
        "anything optimistic for the rest of the programme. The retrospective, which covers seven "
        "screens, is the check on that.",
        "N_E WAS ADDED AFTER HASHING. It is a null, its result went AGAINST the hypothesis that "
        "motivated adding it, and it is counted in added_after_hashing.",
    ],
    "incidental_not_a_lead": (
        "A10_opp_defrtg (strictly-prior opponent defensive rating) carries an in-sample screening "
        "dR2 of 0.0082-0.0086 against y_ppm on the DECISION stratum, p=0.0017 on both "
        "opponent-level nulls. It was used here ONLY as a carrier for opponent-level power "
        "measurement. It is a single uncorrected in-sample cell on an outcome D085 did not screen "
        "it against (D085 screened the A-family against EFFICIENCY, not points-per-minute). It is "
        "recorded so it is not lost, and it is NOT raised as a lead."),
}

for null, lab in NULL_LABEL.items():
    q = dr[dr["null"] == null]
    if len(q):
        F["null_width_drift"]["by_null"][lab] = {
            "rel_drift_sd_at_delta_1e-3": float(q[q.delta == 1e-3]["rel_drift_sd"].median()),
            "rel_drift_sd_at_delta_1e-2": float(q[q.delta == 1e-2]["rel_drift_sd"].median()),
            "direction": ("null WIDENS when an effect is planted -> the uncorrected floor was "
                          "ANTICONSERVATIVE"
                          if q[q.delta == 1e-2]["rel_drift_sd"].median() > 0 else
                          "null NARROWS when an effect is planted -> the uncorrected floor was "
                          "CONSERVATIVE")}

with open(os.path.join(HERE, "FINDINGS.json"), "w", encoding="utf-8") as fh:
    json.dump(F, fh, indent=2, default=str)

logs = sorted(glob.glob(os.path.join(OUT, "run_s*.txt")))
with open(os.path.join(HERE, "run_log.txt"), "w", encoding="utf-8") as fh:
    for p in logs:
        fh.write("\n" + "#" * 100 + "\n### %s\n" % os.path.basename(p) + "#" * 100 + "\n")
        fh.write(open(p, encoding="utf-8", errors="replace").read())

hdr("ASSEMBLED")
for k in ("power_curves.csv", "retrospective_power.csv", "mde_table.csv", "FINDINGS.json",
          "run_log.txt"):
    p = os.path.join(HERE, k)
    print("  %-28s %10d bytes" % (k, os.path.getsize(p)))
print("\n  preregistration sha256 = %s" % PREREG_SHA)
