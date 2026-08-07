"""S37: current-game-deletion invariance at COLUMN grain, measured (not asserted).

For each sampled game g, the CURRENT game's rows of master_team's outcome columns
(pts, opp_pts, and the derived margin/env) are NULLED, every other column and every other row
retained. Each arm's feature constructor is then re-run and the sampled game's OWN feature
values are compared to baseline. Byte identity on the sampled game's row == that game's feature
did not consume its own realized score.
"""
import sys, io, json, dataclasses
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import numpy as np, pandas as pd
W = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
N = W + r"\experiments\player_program\stage3_score\S36_IMPLEMENT_ARMS"
sys.path.insert(0, N + r"\runner"); sys.path.insert(0, N + r"\arms")
import runner_constants as K, universe as U
import sc02_a07_score_transient as SC02
import sc03_season_carryover_prior as SC03
import sc04_hca_league_drift as SC04
import sc05_hca_team_offsets as SC05
import sc06_sched_fatigue_diff as SC06
import sc08_sigma_margin_map as SC08
import sc10_form_trend as SC10
import sc11_league_total_drift as SC11
import sc12_robust_input_winsor as SC12
import sc01_opp_adj_interacting as SC01

u = U.build_universe()
NULLED = ["pts", "opp_pts", "margin", "env"]

def make_variant(base, game_id, mode="perturb"):
    """mode='null' sets the current game's own outcome columns to NaN (the S30 receipt's literal
    deletion). mode='perturb' replaces them with grossly different finite values, which tests the
    same dependence without NaN-propagating into unrelated later rows."""
    tr = base.team_rows.copy()
    m = (tr["game_id"].astype(str) == str(game_id)).to_numpy()
    if mode == "null":
        for c in NULLED:
            tr.loc[m, c] = np.nan
    else:
        tr.loc[m, "pts"] = 999.0
        tr.loc[m, "opp_pts"] = 1.0
        tr.loc[m, "margin"] = tr.loc[m, "pts"] - tr.loc[m, "opp_pts"]
        tr.loc[m, "env"] = tr.loc[m, "pts"] + tr.loc[m, "opp_pts"]
    return U.Universe(games=base.games, team_rows=tr,
                      game_id_digest=base.game_id_digest, receipt=base.receipt)

def feats(uu, want_sc01=False, lam=8.0):
    out = {}
    out.update({("SC02", k): v for k, v in SC02.transient_terms(uu).items()})
    out.update({("SC03", k): v for k, v in SC03.carryover_terms(uu).items()})
    out[("SC04", "hca_lag")] = SC04.hca_lag(uu)
    p = SC05._d_raw_and_counts(uu)
    out[("SC05", "d_raw_H")] = np.asarray(p["d_raw"], dtype=float)
    out.update({("SC06", k): v for k, v in SC06.fatigue_terms(uu).items()})
    out[("SC08", "pace")] = SC08.pace_prior(uu)
    sh, sa = SC08.lagged_margin_sd_sum(uu)
    out[("SC08", "sd_H")] = sh; out[("SC08", "sd_A")] = sa
    out.update({("SC10", k): v for k, v in SC10.spread_terms(uu).items()})
    out[("SC10", "orth_covariate")] = SC10.trailing_opponent_strength_diff(uu)
    out[("SC11", "lt_lag")] = SC11.lt_lag(uu)
    out.update({("SC12", k): v for k, v in SC12.winsor_terms(uu).items()})
    if want_sc01:
        r = SC01.ratings_by_cutoff(uu, lam)
        out[("SC01", "strength_margin")] = r["strength_margin_interacting"].to_numpy(float)
        out[("SC01", "strength_total")] = r["strength_total_interacting"].to_numpy(float)
    return out

gids = u.games["game_id"].tolist()
rng = np.random.default_rng(0)
sample = [gids[i] for i in sorted(rng.choice(len(gids), size=24, replace=False).tolist())]
sample_sc01 = sample[:6]

base = feats(u, want_sc01=True)
pos = {g: i for i, g in enumerate(gids)}
bad = {}
for j, g in enumerate(sample):
    want01 = g in sample_sc01
    v = feats(make_variant(u, g, mode="perturb"), want_sc01=want01)
    i = pos[g]
    for key, col in v.items():
        b = base[key]
        a1, a2 = float(b[i]), float(col[i])
        same = (np.isnan(a1) and np.isnan(a2)) or a1 == a2
        if not same:
            bad.setdefault(key, []).append((g, a1, a2))
print("sampled games:", len(sample), " (SC01 rating rebuild on", len(sample_sc01), "of them)")
print("feature columns tested:", len(base))
print("columns tested:", sorted(str(k) for k in base))
print()
if bad:
    print("!!! CURRENT-GAME-DELETION INVARIANCE VIOLATIONS:")
    for k, v in bad.items():
        print("  ", k, "n_violating_games=", len(v), "example:", v[0])
else:
    print("RESULT: byte identity held on every sampled game for every tested feature column.")
    print("        No tested feature consumed its own game's realized pts/opp_pts.")
