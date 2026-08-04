#!/usr/bin/env python3
"""make_ledger.py — freeze the eight discovery hypothesis cards before execution."""
import json
from pathlib import Path

L = {
    "schema": "discovery_hypothesis_ledger/1", "wave": "discovery_wave_1",
    "lane": "DISCOVERY (development folds only)",
    "binding_rules": [
        "no discovery result may replace Arm D directly",
        "any promising formulation must later become a NEW frozen challenger under a separate registered evaluation",
        "preserve all null and negative results",
        "feature_gate.audit() must pass before any fit",
    ],
    "frozen_incumbent": {"arm": "D_ewma_shrunk", "K": 200, "alpha": 0.10,
                         "operational_team_mae": 2.9675, "intrinsic_team_mae": 2.8960},
    "workstreams": {},
}
W = L["workstreams"]


def add(k, mech, form, exp, data, supp, fals, conf, met):
    W[k] = {"basketball_mechanism": mech, "exact_formulation": form,
            "expected_direction": exp, "data_and_provenance": data,
            "supports_hypothesis": supp, "falsifies_or_weakens": fals,
            "known_confounders": conf, "metrics": met,
            "development_only": True, "result": "PENDING", "disposition": "PENDING"}


add("ws1_repaired_projected_role",
    "turnover rate changes most when a player occupies a substantially DIFFERENT offensive role than normal, not simply because the role is large",
    "projected minutes share ONLY (never both shares); trailing minutes share; projected minus trailing; rotation-rank change; bounded transform for a materially expanded role; linear plus ONE preregistered bounded nonlinear form (positive/negative role-change split)",
    "role CHANGE positive on turnover rate; role LEVEL near null once change is included",
    "projected_player_possessions/1 tier_a_only; master_player minutes, strictly prior games",
    "role-change coefficient stable across folds AND operational team MAE not worse than D",
    "change term null once level is included, or the gain is confined to one season",
    "projected minutes share is a deterministic transform of the exposure offset; role change correlates with injury context",
    "operational team MAE vs D; intrinsic deviance; season stability")
add("ws2_responsibility_transfer",
    "turnovers rise specifically for players positioned to ABSORB missing teammates offensive responsibility",
    "three frozen constructions: (1) team_displaced_involvement x player_prior_involvement; (2) allocated displaced load proportional to prior creation share; (3) allocated load x projected-role expansion",
    "positive interaction; the player-specific form beats the team-level H arm",
    "P2 feature artifact; frozen prior involvement; tier_a_only candidates",
    "a player-specific transfer form beats team-level displaced_involvement on operational team MAE",
    "no construction beats H, or gains appear only under oracle appearance",
    "absences correlate with opponent quality and with the absent player own rate",
    "operational team MAE vs D and vs H; player deviance")
add("ws3_team_total_plus_allocation",
    "one model should not have to control BOTH how many turnovers a team commits AND which players commit them",
    "stage 1 team-total count model on projected team possessions; stage 2 compositional allocation (multinomial / Dirichlet-multinomial / softmax shares with shrinkage) summing EXACTLY to the stage-1 total",
    "allocation improves player identity WITHOUT harming the team total; G becomes useful in the allocation layer",
    "team_turnover_reconciliation_v1; projected exposure; P2 features",
    "team-total accuracy at least matching the D aggregate AND player allocation deviance improving",
    "the allocation gain requires sacrificing team-total accuracy",
    "team total and allocation share a common exposure error",
    "team-total MAE; allocation deviance; share calibration; both jointly")
add("ws4_ewma_timescale_family",
    "one decay rate cannot suit both stable and unstable roles",
    "effective-half-life family: slow long-memory; incumbent alpha=0.10; fast role-responsive; dual short+long timescale; role-change-GATED decay. Nested chronological development folds only",
    "faster adaptation helps after role shifts and team changes; slow decay remains better for stable roles",
    "P1 target artifact; strictly prior games",
    "a gated or dual-timescale variant beats alpha=0.10 in unstable-role strata AND does not lose in stable strata",
    "no variant beats the incumbent anywhere, or gains vanish out of fold",
    "role instability correlates with injury and with low support",
    "by-stratum deviance and team MAE; post-trade and post-role-shift subsets")
add("ws5_opportunity_proxies",
    "FGA share is an incomplete proxy for ball-handling responsibility",
    "bounded set: FGA share; play-ending involvement (FGA + frozen FT weight x FTA + turnovers); share of team play-ending involvement; short vs long involvement change; involvement rank among projected teammates; projected responsibility share after removing unavailable teammates",
    "play-ending involvement beats FGA share as a rate predictor and especially as an allocation weight",
    "master_player fga and fta; canonical turnover targets; strictly prior games",
    "a proxy improves the conditional rate OR allocation beyond the P1 EWMA",
    "all proxies are redundant with the P1 EWMA turnover rate",
    "involvement is mechanically related to turnovers because turnovers enter the play-ending formula",
    "conditional rate deviance; allocation weight quality; redundancy with D")
add("ws6_mechanism_decomposition",
    "bad passes relate to creation burden; lost balls to handling pressure; offensive fouls to drives; travels to role instability; shot-clock violations are team or lineup driven",
    "diagnostics plus bounded discovery models per mechanism: base rate, support, source-schema stability, player concentration, relation to involvement and to role change, contribution to total-model error",
    "the G player-level gain and team-level loss arise from OFFSETTING mechanism effects",
    "player_turnover_targets_v1 mechanism columns; canonical events",
    "involvement helps one mechanism and hurts another with opposite signs",
    "all mechanisms respond to involvement in the same direction",
    "mechanism mix differs by source schema, which is confounded with season type",
    "per-mechanism deviance and error contribution; NO promotion")
add("ws7_nonlinear_heterogeneous",
    "role and involvement effects may be hidden by linear pooling",
    "piecewise-linear; splines with few preregistered knots; separate expansion vs contraction effects; involvement x projected minutes; involvement x historical support; partial pooling by continuous role tier derived WITHIN each training fold. No unrestricted player-specific slopes",
    "the effect concentrates among primary creators and among secondary creators receiving expanded roles",
    "P2 feature artifact; P1 targets",
    "a bounded nonlinear form beats the linear term out of fold in a preregistered stratum",
    "linear and nonlinear indistinguishable, or gains only in fold",
    "role tiers correlate with support; low-support players are noisier",
    "stratum-wise deviance and operational team MAE")
add("ws8_operational_error_decomposition",
    "where does operational error actually come from: availability, candidate precision, minute allocation, possession allocation, or rate",
    "hold Arm D fixed; five LABELLED diagnostic counterfactuals: (1) full operational; (2) oracle appearance with exposure reallocated among actual participants; (3) Tier A plus actual missing participants; (4) oracle minutes or possessions; (5) realised exposure",
    "exposure-side errors dominate rate error",
    "projected exposure artifact; realised possessions; targets",
    "a clear ordering of incremental error contributions",
    "contributions are diffuse and none dominates",
    "oracle variants are NOT models and are never promotion evidence",
    "incremental team MAE change per counterfactual step")

Path(__file__).resolve().parent.joinpath("HYPOTHESIS_LEDGER.json").write_text(
    json.dumps(L, indent=2), encoding="utf-8")
print("ledger written:", len(W), "workstreams")
