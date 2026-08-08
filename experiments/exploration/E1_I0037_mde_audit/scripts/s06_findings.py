"""E1_I0037 s06 -- assemble FINDINGS.json from the stage outputs. No new statistics."""
from __future__ import annotations
import hashlib
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
HERE = os.path.join(ROOT, "experiments", "exploration", "E1_I0037_mde_audit")
sys.dont_write_bytecode = True


def load(n):
    return json.load(open(os.path.join(HERE, n), encoding="utf-8"))


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


s01, s02, s03, s04, s05 = (load("_s0%d.json" % i) for i in (1, 2, 3, 4, 5))
D = pd.read_csv(os.path.join(HERE, "SIMULATION.csv"))
C = pd.read_csv(os.path.join(HERE, "MDE_CENSUS.csv"))


def q(s):
    s = pd.Series(s).replace([np.inf, -np.inf], np.nan).dropna()
    return dict(n=int(len(s)), min=float(s.min()), p10=float(s.quantile(.1)),
                median=float(s.median()), p90=float(s.quantile(.9)), max=float(s.max()))


F = {
    "screen": "E1_I0037_mde_audit",
    "question": ("Is the programme's analytic MDE80 = 2.802 x null_sd anti-conservative because "
                 "null_sd is computed from an effect-carrying vector, as E1_I0035 D-3 / D113 "
                 "claims, and if so by how much and how generally?"),
    "partition": "2021-2024 exploration only; 2025/26 never opened",
    "prereg_sha256": open(os.path.join(HERE, "PREREG.sha256"), encoding="utf-8").read().strip(),

    "VERDICT": {
        "claim_as_stated": "REFUTED",
        "the_6_6x": ("NOT REPRODUCIBLE. E1_I0035 compared an injection floor measured on the Xb "
                     "response contrast (0.0025) against an analytic floor computed from the Xa "
                     "contrast's null_sd (0.00038). Different response vectors -- a D101 "
                     "denominator violation. Recomputed like-for-like from that screen's own "
                     "frame: Xa 1.02x, Xb 0.76x."),
        "mechanism_as_stated": ("MISATTRIBUTED, and in the reassuring direction. An "
                                "effect-carrying null_sd INFLATES the quoted floor, making the "
                                "analytic form CONSERVATIVE. It cannot produce anti-conservatism."),
        "a_real_defect_does_exist": ("YES, but it is the CRITICAL VALUE, not the variance. The "
                                     "rejection threshold t_crit*sd(e) also grows with the "
                                     "effect. Size is governed by BLOCK COUNT alone."),
        "generality": ("232 quoted figures across 4 screens use the affected construction, but "
                       "on their ACTUAL designs the bias is <= 9% everywhere except one place: "
                       "D103's family-wise threshold on E1_I0023's 48-cluster cells, where the "
                       "MDE is infinite."),
    },

    "anchor_reproduced_before_new_statistics": s01["anchor"],

    "construction_confirmed_at_source": {
        "shared_kit": ("_screen_kit\\screenkit.py::paired_forecast_comparison lines 2143-2170: "
                       "d = (y-a)**2 - (y-b)**2 (OBSERVED); csum = bincount(gcodes, weights=d); "
                       "draws = -(signs @ csum)/sst; sd = draws.std(ddof=1). Nothing permuted or "
                       "resampled -- only signs flipped on observed block sums."),
        "local_copies": ["E1_I0035\\scripts\\av_base.py::paired_signflip_block lines 273-294",
                         "E1_I0034\\scripts\\redist_base.py::paired_signflip_block lines 235-256"],
        "C1_effect_carrying": True,
    },

    "call_graph_resolution_no_name_matching": {
        "py_files_enumerated": s01["callgraph"]["py_files"],
        "parsed_ok": s01["callgraph"]["parsed"],
        "UNRESOLVED_parse_failures": s01["callgraph"]["unresolved"],
        "unresolved_reason": "UTF-8 BOM (U+FEFF); all seven named in run_log_s01.txt",
        "mde_producing_functions": len(s01["callgraph"]["producers"]),
        "classified_by": ("the arithmetic performed -- a constant within 0.01 of "
                          "z_alpha + Phi^-1(0.80), or Phi^-1(0.80) itself -- NOT by any "
                          "identifier"),
        "call_sites_resolved": len(s01["call_sites"]),
    },

    "two_hypotheses_separated": {
        "H_A_null_sd_contaminated": {
            "real": True, "direction": "CONSERVATIVE (inflates the quoted floor) -- the safe one",
            "sd_obs_over_sd_centred": q(D["inflation_sd_obs_over_centred"]),
            "by_observed_effect_SE": s02["by_obs_effect"],
            "corroborates_E1_I0034": ("E1_I0034 measured 0.963-1.013 on its own cells; that is "
                                      "what H_A predicts when the observed effect is small."),
        },
        "H_B_rule_miscalibrated": {
            "real": True, "direction": "ANTI-CONSERVATIVE -- this is the genuine defect",
            "governed_by": "number of blocks; NOT n, NOT sigma, NOT effect size",
            "E_inj_over_2.802_x_sd_centred_by_block_count": s03["H_A_H_B"]["by_nb"],
            "closed_form": ("u^2(1 - t_crit^2/nb) - 2*z80*u + (z80^2 - t_crit^2) >= 0, "
                            "u = effect/SE"),
        },
    },

    "ratio_distribution": {
        "n_conditions": int(len(D)),
        "n_with_finite_crossing": int(np.isfinite(D["ratio_E_over_A_obs"]).sum()),
        "E_inj_over_A_obs_the_D3_comparison": q(D["ratio_E_over_A_obs"]),
        "E_inj_over_A_centred": q(D["ratio_E_over_A_ctr"]),
        "E_inj_over_A_oracle": q(D["ratio_E_over_A_oracle"]),
        "6_6x_lies_beyond": "the maximum of every column above",
    },

    "structural_results": {
        "signflip_cannot_reject_below_six_blocks": {
            "p_min": "2^(1-nb)", "requires": "nb >= 6 for alpha=0.05",
            "measured_type_I_R2000": s03["signflip_floor"],
        },
        "mde_is_infinite_when_t_crit_ge_sqrt_nb": {
            "verified_by_simulation_not_algebra": True,
            "sweep": "0.5 SE to 1e7 SE",
            "cases": s05["verification"],
        },
    },

    "d103_exposure": dict(s04["d103"], **{
        "qualitative_conclusion_survives": True,
        "movement_pp": 100 * (s04["d103"]["share_after_H_B"]
                              - s04["d103"]["share_published"]),
        "affected_family": "paired (E1_I0023) only, 30 of 1349 cells = 2.2%",
        "unaffected": "1319 cells on permutation nulls",
        "larger_unquantified_exposure": {
            "family": "t_statistic",
            "cells": 666, "share_of_1349": 0.4937,
            "blind_verdicts_carried": 518, "share_of_760_blind": 0.6816,
            "problem": ("MDE80 = ((t_crit+z80)*sd_t)^2/n was NEVER validated; D103's validate() "
                        "gate reads s04_mde_table.csv, which contains only increment cells"),
            "recommendation": "this is the next power screen, not another sign-flip pass",
        },
    }),

    "census": {
        "total_figures": int(len(C)),
        "by_classification": {k: int(v) for k, v in
                              C.groupby("classification").size().to_dict().items()},
        "on_effect_carrying_nulls": int(C["effect_carrying_null"].sum()),
        "screens_affected": sorted(C.loc[C["effect_carrying_null"], "screen"].unique().tolist()),
    },

    "machinery_checks_MY_OWN": {
        "S1_type_I_at_committed_R2000": {r["nb"]: r["type_I_R2000"] for r in
                                         s03["signflip_floor"]},
        "S1_grid_R400_note": ("the s02 grid ran at R=400 against a band computed for R=2000; "
                              "that understates calibration -- see DEFECTS.md D-5"),
        "S2_discrimination_pass": int(D["S2_pass"].sum()),
        "S3_degenerate_plant_guard": ("discriminates: constant plant sd/|mean| = 0.000000 fires, "
                                      "plant onto real noise 0.482362 does not"),
        "S4_large_nb_recovery_E_inj_over_A_oracle": 0.9604,
        "S5_FRESH_vs_FLIP": s02["fresh_vs_flip"],
        "first_run_was_degenerate": ("YES -- type-I 0.0000 in all 648 FRESH conditions; caught by "
                                     "S1; defective output preserved at "
                                     "SIMULATION_DEFECTIVE_s02run1.csv. See DEFECTS.md D-1."),
        "null_mean_gt_observed_diagnostic": ("STRUCTURALLY VACUOUS on this family: sign-flip "
                                             "draws are +/- a fixed set of block sums so "
                                             "E[draws]=0 exactly. It cannot police sign-flip "
                                             "nulls. Coverage gap, not a clean bill of health."),
    },

    "proposed_fix": {
        "location": "PROPOSED_FIX\\mde_signflip.py  (NOT applied to the shared kit)",
        "tests": "PROPOSED_FIX\\test_mde_signflip.py -- 23 assertions, all passing",
        "p_value_unchanged": "verified to 0.000e+00 over four cells (T4)",
        "guards": ["assert_null_sd_not_effect_carrying (the assertion the brief asked for)",
                   "assert_signflip_can_reject (nb >= 6)",
                   "assert_mde_is_finite (t_crit < sqrt(nb))"],
        "known_limitation": ("the fix is WORSE than the incumbent below 16 blocks; it now warns "
                             "that no data-driven MDE is stable there. See DEFECTS.md D-3."),
    },

    "predictions_for_other_screens_not_adjudicated_here": {
        "E1_I0034_implied_effective_block_counts": s03["e1_i0034_implied_blocks"],
        "note": ("E1_I0034's reported 1.22x/1.61x/3.40x imply effective block counts of 16.1, "
                 "8.1 and 4.9 under the block-count law. 4.9 is BELOW SIX, where the sign-flip "
                 "cannot reject at all. Checkable against that screen's own cluster counts; "
                 "E1_I0038 owns it."),
        "E1_I0033": ("36 blocks -> H_B factor 1.085. Its P02 and s10 cells have near-zero "
                     "observed effects so H_A does not rescue them; both become ~9% MORE "
                     "underpowered. Its NOTES.md section 5 labels an analytic table 'Power "
                     "verified by injection' -- that label is wrong whatever else is decided."),
    },

    "deliverable_hashes": {f: sha(os.path.join(HERE, f)) for f in
                           sorted(os.listdir(HERE)) if os.path.isfile(os.path.join(HERE, f))
                           and f.endswith((".md", ".csv"))},
}

with open(os.path.join(HERE, "FINDINGS.json"), "w", encoding="utf-8") as fh:
    json.dump(F, fh, indent=2, default=float)
print("wrote FINDINGS.json (%d bytes)" % os.path.getsize(os.path.join(HERE, "FINDINGS.json")))
print("VERDICT: %s" % F["VERDICT"]["claim_as_stated"])
print("D103 share: %.4f -> %.4f (%+.2f pp)"
      % (F["d103_exposure"]["share_published"], F["d103_exposure"]["share_after_H_B"],
         F["d103_exposure"]["movement_pp"]))
