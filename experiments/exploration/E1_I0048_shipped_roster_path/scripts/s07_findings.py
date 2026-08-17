#!/usr/bin/env python3
"""s07 — assemble FINDINGS.json from the artifacts the earlier steps wrote."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent.parent


def j(name):
    return json.loads((HERE / name).read_text(encoding="utf-8"))


s01, s03, s04, s05, s06 = j("_s01.json"), j("_s03.json"), j("_s04.json"), \
    j("_s05.json"), j("_s06.json")
FID = pd.read_csv(HERE / "FIDELITY.csv")
C = pd.read_csv(HERE / "SHIPPED_DAMAGE.csv")

F = {
  "screen": "E1_I0048_shipped_roster_path",
  "question": ("Characterise and quantify the roster-currency defect at "
               "daily_forecast.py:647-665, the only defect found in the "
               "preceding 24h that sits on the shipped scheduled path."),
  "verdict": ("The defect was real and is REPAIRED IN PRODUCTION as of commit "
              "55d84f1e (2026-08-06 19:47Z), one day after it was reported. "
              "E1_I0045 read a research-worktree copy of daily_forecast.py "
              "that production had already diverged from. Of the 40 shipped "
              "records emitted by the defective code, ZERO contain a stale "
              "player-club pairing, a name-key duplicate, or a name-key drop, "
              "and ZERO reach the decision stratum. Nothing anywhere reads the "
              "roster rows. The live-path concern is closed."),
  "enacted": "NOTHING. No production file was modified.",

  "partition_boundary": {
    "shipped_log_span": "2026-07-31T14:28Z .. 2026-08-08T23:45Z",
    "partition": "ENTIRELY WITHIN THE SEALED 2025/26 CONFIRMATION HOLDOUT",
    "activity_performed": ("descriptive counts of rows and names emitted by a "
                           "production code path (permitted characterisation "
                           "of a production defect)"),
    "activity_refused": ("any skill statistic on sealed output; no outcome "
                         "column was loaded at any point"),
    "enforcement": ("eight-column allowlist asserted present and a seven-column "
                    "outcome blocklist asserted absent in s02/s03/s05; printed "
                    "in each run log")
  },

  "anchors": {"n_confirmed": s01["n_confirmed"], "n_total": s01["n_total"],
              "n_exact_zero_diff": s01["n_exact_zero"],
              "note": ("all recomputed from E1_I0045 _PF.parquet and from "
                       "source files; never transcribed from prose")},

  "era_split": {
    "method": ("git sha read from provenance.source_version inside each shipped "
               "record, then `git show <sha>:daily_forecast.py` (read-only)"),
    "repair_commit": "55d84f1edd11e9412cc993f0a64e7d9a260cb32b",
    "repair_time_local": "2026-08-06 15:47:04 -0400",
    "pre_repair_records": "record_idx 0..39",
    "post_repair_records": "record_idx 40..63",
    "worktree_copy_matches": "735b63bcb4e313e9505d9eb4cf5812355bf95f9b (was production 2026-08-01)"
  },

  "fidelity_gate": {
    "why": ("the shipped log records aggregates and Out-names only; the roster "
            "name list is never written, so the rule had to be re-executed"),
    "criteria": ("n_roster and n_out integer-equal, out_home/out_away sets "
                 "equal, sum_min_ewma_available and vacated_min_ewma equal to 1e-9"),
    "pre_repair_slots": s03["pre_repair_slots"],
    "pre_repair_reproduced": s03["fidelity_passed"],
    "post_repair_slots": s06["post_repair_slots"],
    "post_repair_reproduced": s06["reproduced"],
    "post_repair_failures": ("3 slots, one player (PHX, Kara Dunn) whose only "
                             "master row is dated on the slate date and is "
                             "excluded by the code's own game_date<slate_date "
                             "filter; input drift, backs no number"),
    "manifest_crosscheck": ("16/16 team-slots on the 2026-07-31 slate reproduce "
                            "against the manifest-verified worktree master")
  },

  "shipped_damage": {
    "denominator_team_slots": s03["fidelity_passed"],
    "stale_phantom_pairings": s03["stale_phantom_emissions"],
    "name_collisions_player_dropped": s03["name_collisions"],
    "name_variants_player_duplicated": s03["name_variants"],
    "slots_where_two_keys_differ": s03["slots_keys_differ"],
    "decision_stratum_affected": s03["n_cases_decision_stratum"],
    "decision_stratum_definition": "n_prior_app_season >= 8 AND trail5_min >= 24",
    "E1_I0045_predicate_ported_verbatim": s03["departed_emissions_E1_I0045_rule"],
    "of_which_arrivals_not_yet_debuted": s03["arrival_not_debuted_emissions"],
    "named_cases": (C[["case", "record_idx", "slate_date", "team", "player_id",
                       "player_name"]].to_dict("records") if len(C) else []),
    "own_defect": ("D-1: the E1_I0045 departure predicate inverts meaning on "
                   "the shipped roster, which already requires current "
                   "box-score membership. 9 apparent phantoms were all correct "
                   "rostering of new arrivals.")
  },

  "consumers": {
    "player_layer_refs_across_12_product_surfaces": s04["product_surface_player_layer_refs"],
    "player_layer_refs_across_every_forecast_log_reader": s04["log_reader_player_layer_refs"],
    "logger_treats_core_only_prediction_as": "opaque blob (serialised + hashed, never indexed)",
    "reaches_team_forecast": False,
    "verdict": "the shipped roster rows are WRITE-ONLY / cosmetic"
  },

  "name_key": {
    "stable_id_available_at_the_site": s05["player_id_available"],
    "null_player_id_rows": s05["null_player_id"],
    "distance_from_the_line_that_ignored_it": "same DataFrame, 18 lines",
    "windows_simulated": s05["total_windows"],
    "windows_where_keys_differ": s05["windows_keys_differ"],
    "exploration_2021_2024": {"windows": 1940, "differ": 196, "rate": 0.1010},
    "sealed_2025": {"windows": 620, "differ": 0},
    "sealed_2026": {"windows": 470, "differ": 8,
                    "all_attributable_to": "player_id 1643490 Eliska Hamzova/Joklova, MIN"},
    "offending_identities": s05["n_offender_identities"],
    "direction": ("every difference is +1 or +2: the DUPLICATION mode. The drop "
                  "mode has zero instances - no player_name maps to >1 player_id"),
    "categories": ["diacritics (7, absorbed by _norm_name)",
                   "hyphenated surname (1)", "maiden/married (2)",
                   "name-order transliteration (1)"]
  },

  "weakest_result_against_own_conclusion": {
    "statement": ("The shipped zero is timing, not safety. The last roster "
                  "window in which the name-key duplication would have fired "
                  "was ~2026-07-09 (MIN, Eliska Hamzova/Joklova). The shipped "
                  "log opens 2026-07-31 - 22 days later. Three weeks earlier a "
                  "start to regime D would have shipped a 15-name MIN roster "
                  "containing one player twice."),
    "secondary": ["'reaches nothing' is a snapshot of today's repository; the "
                  "layer is labelled v0/informational and the obvious v1 feeds "
                  "the forecast",
                  "a token-count consumer trace cannot prove the absence of a "
                  "dynamic JSON-walk access path, only that none of the eight "
                  "readers uses one"]
  },

  "fix_cost": {
    "status": "ALREADY PAID - not by this screen and not by this programme's research lane",
    "production_files_touched_by_the_paid_fix": 7,
    "artifacts_added": ["entity_resolution.py",
                        "ops_adoption_tests/O14/test_o14.py",
                        "ops_adoption_tests/O14/baseline_port.py",
                        "ops_adoption_tests/O14/B_HANDOFF.md",
                        "data/entity_resolution/alias_table.json"],
    "research_files_invalidated": 0,
    "residue_unenacted": ["R-1 worktree copy still carries the old code (cost 0, do nothing)",
                          "R-2 entity_resolution.py docstring says daily_forecast.py is NOT modified; it was",
                          "R-3 records 0-39 permanently carry pre-repair rosters inside the hash chain - do not attempt a fix",
                          "R-4 alias table empty by design; a name first seen on an injury report now fails closed with BLOCK"],
    "comparison": ("E1_I0045 priced the contract-side currency rule at ~32 "
                   "player_program files + cbs_v12-v15 + 10 screens + contract "
                   "tests for an indistinguishable benefit. It remains "
                   "unenacted and this screen recommends nothing about it.")
  },

  "defects_logged": {
    "D-1": "MINE: E1_I0045's departed predicate ported verbatim inverted its meaning (9 false phantoms)",
    "D-2": "MINE, caught in-turn: top-level key scan of the shipped log missed the nested player layer",
    "D-3": "E1_I0045 D-2 cites a worktree file as production without recording worktree or sha",
    "D-4": "the master that production reads has NO MANIFEST; the manifest lives on the research copy",
    "D-5": "E1_I0035/REACH.md, cited by the brief as required reading, does not exist"
  },

  "process": {
    "scripts": ["s01_anchors.py", "s02_shipped.py", "s03_damage.py",
                "s04_consumers.py", "s05_name_key.py", "s06_postrepair.py",
                "s07_findings.py"],
    "background_tasks_launched_and_stopped_by_own_id": ["bvfqtp4qz"],
    "blanket_process_kills": "NONE - no taskkill, no Get-Process|Stop-Process",
    "git_write_commands": "NONE - git show / git log -s are reads",
    "write_scope": "experiments/exploration/E1_I0048_shipped_roster_path/ only",
    "shared_screen_kit_modified": False
  }
}

out = HERE / "FINDINGS.json"
out.write_text(json.dumps(F, indent=2), encoding="utf-8")
print(f"wrote {out} ({out.stat().st_size} B)")
print(f"anchors {s01['n_confirmed']}/{s01['n_total']} "
      f"({s01['n_exact_zero']} at exactly 0.000e+00)")
print(f"pre-repair fidelity {s03['fidelity_passed']}/{s03['pre_repair_slots']}")
print(f"stale phantom pairings: {s03['stale_phantom_emissions']}")
print(f"decision stratum affected: {s03['n_cases_decision_stratum']}")
h = hashlib.sha256(out.read_bytes()).hexdigest()
print(f"FINDINGS.json sha256 {h}")
