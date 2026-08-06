#!/usr/bin/env python3
"""MEASURE.py — F11_PLAYER_ALLOCATION_ARCHITECTURE

Every number quoted in TARGET_CONTRACT_DRAFT.md and REPORT.md is produced here.
Read-only. Fits nothing, scores nothing, opens no SEALED_RESULTS path.

Run:
    python experiments/player_program/future_research/F11_PLAYER_ALLOCATION_ARCHITECTURE/MEASURE.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PP = HERE.parents[1]                      # experiments/player_program
ROOT = PP.parents[1]                      # repo root

EXPOSURE = PP / "projected_exposure_v1" / "projected_player_possessions_v1.parquet"
ROTATIONS = PP / "projected_exposure_v1" / "projected_team_rotations_v1.parquet"
PACE = PP / "projected_exposure_v1" / "team_possession_prior_v1.parquet"
POSS = PP / "possessions_v2" / "possessions_raw_v2.parquet"
TOV = PP / "turnover_targets_v1" / "player_turnover_targets_v1.parquet"

out: dict = {
    "schema": "f11_measurements/1",
    "node_id": "F11_PLAYER_ALLOCATION_ARCHITECTURE",
    "epistemic_status": (
        "DIAGNOSTIC AND TARGET-CONTRACT DRAFT ONLY. Discovery work being unblocked is NOT "
        "authorisation to fit. Fitting requires a target contract, a matched K0, cutoff-valid "
        "evidence, a preregistration and an independent gate review."),
    "nothing_fitted": True,
    "nothing_scored": True,
}

d = pd.read_parquet(EXPOSURE)
out["projected_player_possessions_v1"] = {
    "path": str(EXPOSURE.relative_to(ROOT)).replace("\\", "/"),
    "rows": int(len(d)),
    "distinct_games": int(d.game_id.nunique()),
    "distinct_team_games": int(d.groupby(["game_id", "team_id"]).ngroups),
    "distinct_players": int(d.player_id.nunique()),
    "contract_version": {str(k): int(v) for k, v in d.contract_version.value_counts().items()},
    "regime_rows": {str(k): int(v) for k, v in d.regime.value_counts().items()},
    "evidence_class_rows": {str(k): int(v) for k, v in d.evidence_class.value_counts().items()},
    "information_available_at_cutoff": {str(k): int(v) for k, v in
                                        d.information_available_at_cutoff.value_counts().items()},
    "historically_captured_asof": {str(k): int(v) for k, v in
                                   d.historically_captured_asof.value_counts().items()},
    "operationally_plausible": {str(k): int(v) for k, v in
                                d.operationally_plausible.value_counts().items()},
    "production_eligible": {str(k): int(v) for k, v in d.production_eligible.value_counts().items()},
    "cutoff_policy_rows": {str(k): int(v) for k, v in d.cutoff_policy.value_counts().items()},
}

# ---- the conservation identity, per regime (never pooled across regimes) ----
regimes = {}
for reg, sub in d.groupby("regime"):
    g = sub.groupby(["game_id", "team_id"]).agg(
        player_off=("projected_off_possessions", "sum"),
        team_off=("projected_team_off_possessions", "first"),
        minutes=("projected_minutes", "sum"))
    ratio = g.player_off / g.team_off
    regimes[str(reg)] = {
        "rows": int(len(sub)),
        "team_games": int(len(g)),
        "games": int(sub.game_id.nunique()),
        "max_abs_deviation_of_player_possession_sum_from_5x_team": float(np.abs(ratio - 5.0).max()),
        "min_team_minutes_sum": float(g.minutes.min()),
        "max_team_minutes_sum": float(g.minutes.max()),
    }
out["conservation_identity_by_regime"] = regimes

# ---- is possession allocation anything other than minutes allocation? ----
a = d[d.regime == "tier_a_only"].copy()
implied_off = a.projected_minutes / 40.0 * a.projected_team_off_possessions
implied_def = a.projected_minutes / 40.0 * a.projected_opp_off_possessions
a["min_share"] = a.projected_minutes / a.groupby(["game_id", "team_id"]).projected_minutes.transform("sum")
a["poss_share"] = (a.projected_off_possessions
                   / a.groupby(["game_id", "team_id"]).projected_off_possessions.transform("sum"))
out["allocation_has_one_free_quantity"] = {
    "regime": "tier_a_only",
    "max_abs_diff_off_poss_vs_minutes_over_40_times_team_poss": float(
        (a.projected_off_possessions - implied_off).abs().max()),
    "max_abs_diff_def_poss_vs_minutes_over_40_times_opp_poss": float(
        (a.projected_def_possessions - implied_def).abs().max()),
    "max_abs_diff_minute_share_vs_possession_share": float((a.min_share - a.poss_share).abs().max()),
    "interpretation": ("projected possession share IS projected minute share, to floating point. "
                       "The allocation layer as built has ONE free quantity: minutes."),
}

# ---- primary-tier coverage and fallback structure ----
prim = {
    "team_games": int(a.groupby(["game_id", "team_id"]).ngroups),
    "games": int(a.game_id.nunique()),
    "rows": int(len(a)),
    "players": int(a.player_id.nunique()),
    "team_games_by_season": {int(s): int(x.groupby(["game_id", "team_id"]).ngroups)
                             for s, x in a.groupby("season")},
    "rows_by_season_and_cutoff_policy": {
        int(s): {str(c): int(n) for c, n in x.cutoff_policy.value_counts().items()}
        for s, x in a.groupby("season")},
    "rows_by_season_pred_is_fallback": {
        int(s): {str(c): int(n) for c, n in x.pred_is_fallback.value_counts().items()}
        for s, x in a.groupby("season")},
    "cold_start_rows": {str(k): int(v) for k, v in a.is_cold_start.value_counts().items()},
}
prim["team_games_present_in_widest_regime_but_absent_from_primary"] = int(
    d[d.regime == "tier_a_plus_tx_b_plus_s2"].groupby(["game_id", "team_id"]).ngroups
    - prim["team_games"])
out["primary_regime_tier_a_only"] = prim

# ---- pace layer ----
p = pd.read_parquet(PACE)
res = p[p.pace_resolved]
out["team_possession_prior_v1"] = {
    "path": str(PACE.relative_to(ROOT)).replace("\\", "/"),
    "rows": int(len(p)),
    "team_games": int(p.groupby(["game_id", "team_id"]).ngroups),
    "games": int(p.game_id.nunique()),
    "pace_resolved_true": int(res.shape[0]),
    "pace_resolved_true_games": int(res.game_id.nunique()),
    "pace_unresolved": int((~p.pace_resolved).sum()),
    "season_type": {str(k): int(v) for k, v in p.season_type.value_counts().items()},
}

r = pd.read_parquet(ROTATIONS)
out["projected_team_rotations_v1"] = {
    "rows": int(len(r)),
    "status": {str(k): int(v) for k, v in r.status.value_counts().items()},
    "rotation_plausibility": {str(k): int(v) for k, v in r.rotation_plausibility.value_counts().items()},
    "by_regime_status": {str(reg): {str(k): int(v) for k, v in sub.status.value_counts().items()}
                         for reg, sub in r.groupby("regime")},
    "by_regime_rotation_plausibility": {
        str(reg): {str(k): int(v) for k, v in sub.rotation_plausibility.value_counts().items()}
        for reg, sub in r.groupby("regime")},
}

# ---- realised (outcome-side) evidence a future estimand would have to be graded against ----
q = pd.read_parquet(POSS)
qg = set(map(tuple, q[["game_id", "offense_team_id"]].drop_duplicates().values))
pg = set(map(tuple, a[["game_id", "team_id"]].drop_duplicates().values))
qv = q[q.lineup_valid_ten]
qvg = set(map(tuple, qv[["game_id", "offense_team_id"]].drop_duplicates().values))
out["realised_possession_evidence"] = {
    "path": str(POSS.relative_to(ROOT)).replace("\\", "/"),
    "possession_rows": int(len(q)),
    "games": int(q.game_id.nunique()),
    "offense_team_games": len(qg),
    "lineup_valid_ten_true": int(q.lineup_valid_ten.sum()),
    "lineup_valid_ten_false": int((~q.lineup_valid_ten).sum()),
    "primary_team_games_with_no_realised_offense_rows": len(pg - qg),
    "primary_team_games_with_no_valid_ten_offense_rows": len(pg - qvg),
    "role_declared_by_registry": "REALISED historical reconstruction; cannot be used as forecast exposure",
}

t = pd.read_parquet(TOV)
out["player_turnover_targets_v1"] = {
    "path": str(TOV.relative_to(ROOT)).replace("\\", "/"),
    "rows": int(len(t)),
    "games": int(t.game_id.nunique()),
    "team_games": int(t.groupby(["game_id", "team_id"]).ngroups),
    "players": int(t.player_id.nunique()),
    "scoreable_true": int(t.scoreable.sum()),
    "rate_defined_true": int(t.rate_defined.sum()),
    "rate_defined_false": int((~t.rate_defined).sum()),
    "has_realised_off_possessions_column": bool("realised_off_possessions" in t.columns),
    "has_minutes_column": bool("minutes" in t.columns),
}

(HERE / "MEASUREMENTS.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
print(json.dumps(out, indent=1))
