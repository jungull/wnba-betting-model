"""S37 criterion 4: is P22 postgame_surrogate_guard FIT FOR PURPOSE on SCORE surrogates?

Measured, not asserted. Two designs are audited with the ONLY prohibited basis the guard module
supplies (realised_duration_basis):
  A. the real S36 score-lane feature columns
  B. the same, plus THREE deliberate current-game realized-SCORE leaks
If the guard blocks (B) it discriminates score surrogates. If it passes (B), it does not.
"""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import numpy as np, pandas as pd
W = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
P22 = W + r"\experiments\player_program\stage2b\P22_POSTGAME_SURROGATE_GUARD"
N = W + r"\experiments\player_program\stage3_score\S36_IMPLEMENT_ARMS"
sys.path.insert(0, N + r"\runner"); sys.path.insert(0, N + r"\arms"); sys.path.insert(0, P22)

import runner_constants as K, universe as U
import postgame_surrogate_guard as G
import sc06_sched_fatigue_diff as SC06
import sc10_form_trend as SC10
import sc12_robust_input_winsor as SC12

u = U.build_universe()
g = u.games.reset_index(drop=True)
POSS = W + r"\experiments\player_program\possessions_v2\possessions_raw_v2.parquet"
import os
print("possessions artifact present:", os.path.exists(POSS))

basis = G.realised_duration_basis(g.index, game_id=g["game_id"], possessions_path=POSS, repo_root=W)
print("prohibited basis columns:", basis.names)
print("basis level counts:", {c: int(basis.frame[c].dropna().nunique()) for c in basis.frame.columns})

frame = pd.DataFrame(index=g.index)
frame["composite_pred_margin"] = g["C_margin"].to_numpy(float)
frame["composite_pred_total"] = g["C_total"].to_numpy(float)
frame["fatigue_diff"] = SC06.fatigue_terms(u)["fatigue_diff"]
frame["form_spread_short_net"] = SC10.spread_terms(u)["form_spread_short_net"]
frame["winsor_correction_diff"] = SC12.winsor_terms(u)["winsor_correction_diff"]
CLEAN = list(frame.columns)

# --- the three deliberate SCORE leaks -------------------------------------------------------
frame["LEAK_current_game_margin"] = g["E2_FINAL_MARGIN_HOME"].to_numpy(float)
frame["LEAK_current_game_total_scaled"] = 3.0 * g["E1_GAME_TOTAL"].to_numpy(float) - 17.5
frame["LEAK_current_game_home_pts"] = g["home_pts"].to_numpy(float)
LEAKS = ["LEAK_current_game_margin", "LEAK_current_game_total_scaled", "LEAK_current_game_home_pts"]

specs = {c: G.LagSpec(column=c, kind=G.DERIVED_NO_JOIN,
                      rationale="declared by the caller as derived-in-frame") for c in frame.columns}

for label, names in (("A: clean score-lane columns", CLEAN), ("B: clean + 3 realized-SCORE leaks", CLEAN + LEAKS)):
    rep = G.audit(frame, names, prohibited=basis, lag_specs=specs, raise_on_block=False)
    print()
    print("### design %s" % label)
    print("  passed:", rep["passed"], " n_blocking:", len(rep["blocking"]),
          " finding kinds:", sorted({f['kind'] for f in rep['findings']}))
    for c in LEAKS:
        if c in names:
            d = rep["per_column"][c]["dependency"]
            print("   %-34s verdicts vs duration basis: %s" % (
                c, {q: {k: v for k, v in dd.items() if k in
                        ("column_is_function_of_prohibited","prohibited_is_function_of_column",
                         "column_exact_affine_of_prohibited","pearson_r")} for q, dd in d.items()}))

print()
print("=== counterfactual: the SAME guard with a SCORE prohibited basis ===")
score_basis = G.ProhibitedBasis(
    frame=pd.DataFrame({"realized_margin": g["E2_FINAL_MARGIN_HOME"].to_numpy(float),
                        "realized_total": g["E1_GAME_TOTAL"].to_numpy(float),
                        "realized_home_pts": g["home_pts"].to_numpy(float)}, index=g.index),
    source={"note": "constructed by the S37 auditor; NOT supplied by the P22 module"},
    note="current-game realized score quantities")
rep2 = G.audit(frame, CLEAN + LEAKS, prohibited=score_basis, lag_specs=specs, raise_on_block=False)
print("  passed:", rep2["passed"], " n_blocking:", len(rep2["blocking"]))
print("  blocked features:", sorted({f['feature'] for f in rep2['blocking']}))
