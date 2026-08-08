"""Merge the automated manifest sweep with the two delegated sweeps' manifest findings,
and split screen-local intermediates from genuine shared/upstream inputs."""
import json, io, os

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
OUT = os.path.join(ROOT, "experiments", "exploration", "AUDIT_baseline_provenance")
d = json.load(io.open(os.path.join(OUT, "MISSING_MANIFESTS.json"), encoding="utf-8"))


def is_local(res, cons):
    if not res:
        return False
    dirn = os.path.dirname(res)
    return all(c.startswith(dirn) for c in cons)


shared, local = [], []
seen = set()
for r in d["UNVERIFIABLE_no_manifest"]:
    if r["resolved"] in seen:
        continue
    seen.add(r["resolved"])
    (local if is_local(r["resolved"], r["consumers"]) else shared).append(
        {"artifact": r["resolved"], "consumers": r["consumers"]})

# additions found by the two delegated sweeps (paths verified below)
EXTRA_NO_MANIFEST = [
    ("data\\props_capture\\historical\\master_props_historical.csv",
     ["MODEL_VS_MARKET", "M13_PLAYER_VALUE_TRANSLATION", "M14_MODEL_MARKET_RESIDUAL",
      "props_edge.py", "calibrated_prob_edge.py"]),
    ("data\\props_capture\\master_props.csv", ["props_edge.py"]),
    ("experiments\\totals_groundwork\\bookie_totals_per_game.csv",
     ["totals_head.py:419", "totals_online.py:384"]),
    ("experiments\\totals_groundwork\\exploratory_bias_fix_per_game.csv", ["totals_online.py:424"]),
    ("experiments\\props_edge\\bet_universe_per_book.csv",
     ["conditional_edge.py", "calibrated_prob_edge.py", "prob_edge_ablation.py"]),
    ("experiments\\props_edge\\bet_universe_best_line.csv",
     ["conditional_edge.py", "calibrated_prob_edge.py", "prob_edge_ablation.py"]),
    ("experiments\\clv_transfer\\bet_log.csv", ["conditional_edge.py:55", "pocket_mining.py:95"]),
    ("experiments\\clv_transfer\\flat_stake_sim.csv", ["conditional_edge.py", "pocket_mining.py"]),
    ("experiments\\oracle_bracket\\game_level_margins.csv", ["clv_transfer.py:78"]),
    ("experiments\\dist_margin_cover\\game_level_dist.csv", ["pocket_mining.py:90"]),
    ("experiments\\w2_integration\\game_level_predictions.csv", ["joint_differential.py:101"]),
    ("experiments\\minutes_twostage\\test_predictions_m1.csv", ["oracle_bracket.py:54"]),
    ("experiments\\minutes_twostage\\test_predictions_m2.csv", ["oracle_bracket.py:55"]),
    ("experiments\\market_program\\M13_PLAYER_VALUE_TRANSLATION\\translation_rows.parquet",
     ["M14_MODEL_MARKET_RESIDUAL\\build_residual.py:66"]),
    ("experiments\\market_program\\SCORE_BASELINES\\market_paired_rows.parquet",
     ["emitted for downstream leaderboard reuse"]),
    ("experiments\\player_program\\fits_v1\\p3_coefficients_v1.parquet",
     ["fit_rate_and_p3.py", "run_p3_downstream.py"]),
]
for p, cons in EXTRA_NO_MANIFEST:
    full = os.path.join(ROOT, p)
    shared.append({"artifact": p, "consumers": cons,
                   "exists_on_disk": os.path.exists(full),
                   "source": "delegated sweep"})

ARTIFACT_GRANULAR = [
    {"artifact": "experiments\\channel_reval\\predictions_v2.csv",
     "asof_granularity": "artifact", "fit_through_season": 2026,
     "consumers": ["bottomup_3pt.py", "w4_refs.py", "totals_head.py:165", "totals_online.py:121",
                   "joint_differential.py:491", "dist_margin_cover.py", "clv_transfer.py:107",
                   "conditional_edge.py:485", "pocket_mining.py:89", "oracle_bracket.py:168",
                   "experiments\\player_program\\run_p3_downstream.py:39 (A_incumbent)",
                   "experiments\\player_program\\p3_concentration_addendum.py:46"],
     "note": ("Its own manifest says the file holds the TEST games AND their realised outcomes, "
              "so the artifact-level bound is the last test season. Under GRAPH_POLICY 13.2.2 "
              "filtering by season DOES NOT make it usable at E0/E1.")},
    {"artifact": "data\\rapm\\rapm_v0.csv", "asof_granularity": "artifact",
     "fit_seasons": [2021, 2022, 2023, 2024],
     "consumers": ["joint_differential.py:463 (DISCLOSED, clean-seasons variant published)",
                   "oracle_bracket.py:213 (NOT DISCLOSED)"],
     "note": ("The manifest's own backfill_basis names this as the artifact whose misuse "
              "motivated asof_invariant_audit_v1.")},
]

d["shared_or_upstream_no_manifest"] = shared
d["screen_local_intermediates_no_manifest"] = local
d["artifact_granular_UNUSABLE_at_E0_E1"] = ARTIFACT_GRANULAR
d["counts"]["shared_or_upstream_no_manifest"] = len(shared)
d["counts"]["screen_local_intermediates_no_manifest"] = len(local)
d["named_in_brief_confirmed_no_manifest"] = [
    "experiments\\player_program\\turnover_targets_v1\\player_turnover_targets_v1.parquet",
    "experiments\\player_program\\possessions_v2\\possessions_raw_v2.parquet"]
d["whole_directories_with_zero_manifests"] = [
    "experiments\\player_program\\possession_features_v1",
    "experiments\\player_program\\turnover_p1_v1",
    "experiments\\player_program\\turnover_p2_v1",
    "experiments\\player_program\\turnover_targets_v1",
    "experiments\\player_program\\projected_exposure_v1",
    "experiments\\player_program\\fits_v1",
    "experiments\\player_program\\validation_v1"]

with io.open(os.path.join(OUT, "MISSING_MANIFESTS.json"), "w", encoding="utf-8") as f:
    json.dump(d, f, indent=1)
print("shared/upstream no-manifest:", len(shared))
print("screen-local intermediates :", len(local))
print("artifact-granular entries  :", len(ARTIFACT_GRANULAR))
for p, _ in EXTRA_NO_MANIFEST:
    print("  exists=%-5s %s" % (os.path.exists(os.path.join(ROOT, p)), p))
