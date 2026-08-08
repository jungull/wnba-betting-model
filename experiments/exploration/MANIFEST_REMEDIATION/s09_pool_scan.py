"""Locate CANDIDATE pooling steps in producer scripts, then print them with context
so a human/agent READS them. A regex hit is never a finding on its own (constraint 3)."""
import os, re, io, json

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
OUT = os.path.join(ROOT, "experiments", "exploration", "MANIFEST_REMEDIATION")

PRODUCERS = [
    # (artifact, producer script)
    ("experiments/prediction_contract_v5/player_game_enriched.parquet", "prediction_contract_v5_enrich.py"),
    ("experiments/prediction_contract_v5/player_game.parquet", "prediction_contract_v5.py"),
    ("experiments/prediction_contract_v5/candidacy_exclusions.parquet", "prediction_contract_v5_enrich.py"),
    ("experiments/player_program/event_contract_v1/canonical_player_events_v1.parquet", "experiments/player_program/build_canonical_events.py"),
    ("experiments/player_program/turnover_p1_v1/turnover_p1_predictions_intrinsic.parquet", "experiments/player_program/run_turnover_p1.py"),
    ("experiments/player_program/turnover_p1_v1/turnover_p1_predictions_operational_corrected.parquet", "experiments/player_program/run_turnover_p1_universe_fix.py"),
    ("experiments/player_program/turnover_p2_v1/turnover_role_context_features_v1.parquet", "experiments/player_program/run_turnover_p2.py"),
    ("experiments/player_program/fits_v1/p3_coefficients_v1.parquet", "experiments/player_program/fit_rate_and_p3.py"),
    ("experiments/market_program/SCORE_BASELINES/score_baseline_rows.parquet", "experiments/market_program/SCORE_BASELINES/build_score_baselines.py"),
    ("experiments/market_program/SCORE_BASELINES/market_paired_rows.parquet", "experiments/market_program/SCORE_BASELINES/build_score_baselines.py"),
    ("experiments/market_program/M13_PLAYER_VALUE_TRANSLATION/translation_rows.parquet", "experiments/market_program/M13_PLAYER_VALUE_TRANSLATION/build_translation.py"),
    ("experiments/player_program/data_lane/D12_COACHING_HISTORY/team_season_coverage_v1.csv", "experiments/player_program/data_lane/D12_COACHING_HISTORY/build_coaching_history.py"),
    ("experiments/exploration/E0_I0005_turnover_interaction/player_game_analysis.csv", "experiments/exploration/E0_I0005_turnover_interaction/build_data.py"),
    ("experiments/exploration/E0_I0009_additive_pressure/player_game_analysis.csv", "experiments/exploration/E0_I0009_additive_pressure/build_data.py"),
    ("experiments/exploration/E1_I0009_additive_pressure/player_game_analysis.csv", "experiments/exploration/E1_I0009_additive_pressure/build_data.py"),
    ("data/reference/player_bios.csv", "data/reference/collect_bios.py"),
    ("data/reference/team_cities.csv", "data/reference/collect_bios.py"),
    ("data/possessions/possessions.parquet", "experiments/player_program/possession_artifact_v1.py"),
    ("experiments/player_program/possessions_v1/possessions_raw_v1.parquet", "experiments/player_program/possession_artifact_v1.py"),
    ("experiments/player_program/possessions_v2/possessions_raw_v2.parquet", "experiments/player_program/possession_artifact_v2.py"),
]

# patterns that INDICATE a pooled / population-level step worth reading
POOL = re.compile(
    r"(?:^|\W)(?:"
    r"shrink\w*|prior_var|tau|lambda_shrink"
    r"|zscore|z_score|zwithin|z_within|standard_scal|StandardScaler|normali[sz]"
    r"|\.mean\(\)\s*$|groupby\(\s*\[?[\"']season[\"']"
    r"|transform\(\s*[\"']mean[\"']|transform\(\s*[\"']median[\"']|transform\(\s*[\"']std[\"']"
    r"|leave_one_out|loo_|\.fit\(|OLS|WLS|LinearRegression|Ridge|Lasso|Logit"
    r"|quantile\(|rank\(|qcut|\.median\(\)|\.std\(\)"
    r")", re.I)

# patterns that indicate a STRICT as-of construction (the safe kind)
SAFE = re.compile(r"shift\(1\)|expanding\(|rolling\(|<\s*r?\.?game_date|cumsum\(\)\.shift|ewm\(", re.I)

report = {}
lines_out = []
for art, prod in PRODUCERS:
    path = os.path.join(ROOT, prod.replace("/", os.sep))
    if not os.path.exists(path):
        lines_out.append("\n#### %s\n   PRODUCER NOT FOUND: %s" % (art, prod))
        report[art] = {"producer": prod, "found": False}
        continue
    txt = io.open(path, encoding="utf-8", errors="replace").read()
    L = txt.split("\n")
    pool_hits, safe_hits = [], []
    for i, ln in enumerate(L, 1):
        if POOL.search(ln):
            pool_hits.append((i, ln.strip()))
        if SAFE.search(ln):
            safe_hits.append((i, ln.strip()))
    report[art] = {"producer": prod, "found": True, "n_lines": len(L),
                   "n_pool_candidates": len(pool_hits), "n_asof_markers": len(safe_hits),
                   "pool_candidates": [{"line": i, "text": t[:220]} for i, t in pool_hits],
                   "asof_markers": [{"line": i, "text": t[:220]} for i, t in safe_hits]}
    lines_out.append("\n#### %s\n     producer: %s  (%d lines)" % (art, prod, len(L)))
    lines_out.append("     AS-OF markers (%d):" % len(safe_hits))
    for i, t in safe_hits[:12]:
        lines_out.append("        %s:%d  %s" % (prod, i, t[:170]))
    lines_out.append("     POOL candidates (%d)  << READ THESE:" % len(pool_hits))
    for i, t in pool_hits[:22]:
        lines_out.append("        %s:%d  %s" % (prod, i, t[:170]))

json.dump(report, open(os.path.join(OUT, "pool_scan.json"), "w", encoding="utf-8"), indent=1)
open(os.path.join(OUT, "pool_scan.txt"), "w", encoding="utf-8").write("\n".join(lines_out))
print("\n".join(lines_out))
