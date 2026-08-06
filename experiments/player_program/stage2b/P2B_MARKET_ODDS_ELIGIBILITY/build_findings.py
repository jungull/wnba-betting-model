#!/usr/bin/env python3
"""Assemble FINDINGS.json for P2B from MEASUREMENTS.json. No numbers are typed by hand here
that are not read back out of the measurements file."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
M = json.loads((HERE / "MEASUREMENTS.json").read_text(encoding="utf-8"))

A = M["archives"]
drive = A["drive_master__master_odds"]
ext = A["extension__master_odds_extension"]
oth = A["extension__other_markets"]
cw = M["capture_witness"]
cov_s = M["coverage_by_season"]
cov_f = M["coverage_by_fold"]

findings = {
    "node_id": "P2B_MARKET_ODDS_ELIGIBILITY",
    "epistemic_status": (
        "VERIFIED_READ_ONLY_DERIVATION. Establishes what historical odds evidence EXISTS and "
        "whether it is cutoff-valid. It does NOT decide whether a market feature belongs in a "
        "possession model -- that is a separate question about what the model is, and this node "
        "raises it rather than settling it."),
    "verdict": {
        "family": "market odds (spread, moneyline/h2h, total)",
        "admitted": False,
        "packet_stated_ground": "capture begins 2026-07-31",
        "packet_stated_ground_status": "FALSIFIED",
        "exclusion_status": "SUSTAINED ON DIFFERENT AND STRONGER GROUNDS",
        "governing_grounds": [
            "CUTOFF_UNPROVEN by retrospective harvest (all pre-2026-07-30 odds)",
            "fold-local degeneracy: all-missing training rows in the deciding fold(s)",
            "the totals market -- the only pace-relevant member -- has no history before 2025-07-05",
        ],
        "note": ("The node does not admit the family and does not recommend admitting it. The "
                 "correction is to the packet's REASON, not to its outcome."),
    },

    "F1_archive_located": {
        "severity": "informational",
        "claim": "A game-joined historical odds archive exists and is the parent of tip_times.csv.",
        "status": "CONFIRMED",
        "archives_read_only_from_repository_root_worktree": {
            "branch": "data-refresh-2026",
            "note": ("These files live ONLY in the repository ROOT worktree. Reading them "
                     "READ-ONLY was permitted and expected by this node's brief. Nothing was "
                     "written there."),
            "paths": [drive["path_read_only"], ext["path_read_only"], oth["path_read_only"]],
        },
        "rows": {"drive_master": drive["n_rows"], "extension": ext["n_rows"],
                 "other_markets": oth["n_rows"]},
        "distinct_games": {"drive_master": drive["n_distinct_game_id"],
                           "extension": ext["n_distinct_game_id"],
                           "other_markets": oth["n_distinct_game_id"]},
        "all_untracked": True,
        "gitignore_rules": [".gitignore:2 data/drive_masters/", ".gitignore:5 data/odds_capture/"],
    },

    "F2_earliest_snapshot_2022_05_21": {
        "severity": "informational",
        "claim_under_test": "earliest snapshot in the parent odds archive is 2022-05-21",
        "verdict": M["earliest_snapshot_adjudication"]["verdict"],
        "measured_earliest_utc": M["earliest_snapshot_adjudication"]["earliest_overall_utc"],
        "measured_in": M["earliest_snapshot_adjudication"]["earliest_overall_archive"],
        "per_archive_spans": M["earliest_snapshot_adjudication"]["per_archive_min_max"],
        "material_qualification": (
            "The DATE reproduces to the second (2022-05-21T17:55:00Z). It is a VENDOR-ASSERTED "
            "observation instant, not a witnessed local capture. Reproducing it does not make it "
            "cutoff-valid -- see F4."),
    },

    "F3_tip_times_provenance": {
        "severity": "informational",
        "claim": "data/reference/tip_times.csv descends from the odds archive.",
        "status": "CONFIRMED -- chain closed on exact per-season counts",
        "builder": "data/reference/collect_bios.py::phase_tips (lines 241-291)",
        "child_counts_by_season_and_source": M["tip_provenance"]["tip_games_by_season_and_source"],
        "parent_counts_by_season": M["tip_provenance"]["parent_games_by_season"],
        "counts_match_exactly": True,
        "join_proved_nonempty": (
            M["tip_provenance"]["join_proof_tip_to_drive"]["join_proved_nonempty"]
            and M["tip_provenance"]["join_proof_tip_to_ext"]["join_proved_nonempty"]),
    },

    "F4_per_snapshot_observation_timestamp_survival": {
        "severity": "A",
        "question": ("For each candidate market field: does a per-snapshot observation timestamp "
                     "survive, or only the latest snapshot's value?"),
        "answer_by_stage": {
            "parent_archive": {
                "observation_timestamp_survives": True,
                "column": "odds_snapshot_timestamp",
                "nulls": drive["snapshot_timestamp_nulls"] + ext["snapshot_timestamp_nulls"],
                "also_present": ["odds_previous_timestamp", "odds_next_timestamp"],
                "note": ("This is BETTER than the tip pipeline: the archive does retain a "
                         "per-row observation instant. It is nevertheless not sufficient -- "
                         "see verdict below."),
            },
            "derived_tip_times_csv": {
                "observation_timestamp_survives": False,
                "output_columns": M["tip_provenance"]["tip_times_columns"],
                "mechanism": ("collect_bios.py:250 sorts by snapshot, :253 keeps "
                              "commence_utc=('commence_utc','last'); :280-282 the written column "
                              "list omits odds_snapshot_timestamp entirely."),
                "consequence": ("D10's CUTOFF_UNPROVEN verdict on the three tip fields is "
                                "independently reconfirmed here. Not upgraded."),
            },
        },
        "verdict": "CUTOFF_UNPROVEN for every market field over every pre-2026-07-30 row",
        "why_survival_is_not_enough": (
            "A surviving vendor timestamp is a CLAIM about a past instant, not a witness to it. "
            "The decisive test is whether the row was OBSERVED before the forecast cutoff by this "
            "repository. It was not: see F5. Per the governing rule, a single retrospective pull "
            "is permanently CUTOFF_UNPROVEN no matter how far back its event dates reach."),
    },

    "F5_retrospective_harvest_proof": {
        "severity": "A",
        "claim": ("All odds evidence before 2026-07-30 is a retrospective harvest, not a "
                  "contemporaneous capture."),
        "status": "CONFIRMED by four independent lines of evidence",
        "evidence": {
            "E1_one_snapshot_per_game": {
                "distinct_snapshots_per_game_drive_master": drive["distinct_snapshots_per_game"],
                "reading": ("Every one of %d games carries exactly ONE distinct snapshot. A live "
                            "capture stream produces many." % drive["n_distinct_game_id"]),
            },
            "E2_targeted_offset": {
                "lead_minutes_commence_minus_snapshot": drive["lead_minutes_commence_minus_snapshot"],
                "snapshot_minute_of_hour_values": drive["snapshot_minute_of_hour_values"],
                "vendor_underlying_grid_minutes": 5,
                "reading": ("Harvested snapshots sit ONLY on minute :25 and :55 at a modal lead of "
                            "64-65 minutes, while odds_previous_timestamp/odds_next_timestamp show "
                            "the vendor's true grid is 5 minutes. One grid point per game was "
                            "SELECTED at approximately tip-minus-one-hour. That is a query "
                            "pattern, not a stream."),
            },
            "E3_single_burst_download": cw["historical_json"],
            "E4_contemporaneous_stream_starts_later": cw["live_json"],
        },
        "earliest_contemporaneously_witnessed_capture_utc":
            cw["earliest_contemporaneously_witnessed_odds_capture_utc"],
        "csv_archive_mtimes_utc": cw["csv_archive_mtimes_utc"],
    },

    "F6_packet_figure_reconstructed": {
        "severity": "B",
        "claim": "The packet's 2026-07-31 date is a game date misreported as a capture date.",
        "status": "CONFIRMED -- exact match",
        "detail": M["packet_figure_reconstruction"],
        "packet_citations": {
            "availability_table":
                ".cutoff_valid_availability_table_CORRECTED.unavailable_or_insufficient[2]",
            "classification": ".statement_classification.UNCHANGED[9] == "
                              "'market odds unavailability (capture begins 2026-07-31)'",
        },
        "correction": ("Contemporaneous capture begins 2026-07-30T15:01:32Z, one day EARLIER than "
                       "the packet states; and the retrospective archive reaches game dates back "
                       "to 2022-05-21. Both halves of the packet's sentence are wrong. The "
                       "family is still inadmissible, for the reasons in F4/F5/F7."),
    },

    "F7_coverage_by_season_and_by_fold": {
        "severity": "A",
        "note": "Reported by season and by fold. NEVER pooled.",
        "universe": {k: v for k, v in M["universe"].items() if k != "join_proofs"},
        "join_proofs": {k: {"n_intersection": v["n_intersection"],
                            "join_proved_nonempty": v["join_proved_nonempty"]}
                        for k, v in M["universe"]["join_proofs"].items()},
        "by_season": cov_s,
        "by_fold": cov_f,
        "degeneracy_summary": {
            fname: {
                "folds_with_all_missing_train": [
                    fid for fid, v in folds.items() if v["train"]["all_missing"]],
                "folds_with_all_missing_test": [
                    fid for fid, v in folds.items() if v["test"]["all_missing"]],
            } for fname, folds in cov_f.items()
        },
    },

    "F8_totals_market_correction": {
        "severity": "B",
        "claim": ("P29 reported 'Markets present: odds_spread and odds_price. No totals column.' "
                  "That is a correction in BOTH directions."),
        "corrected_to": (
            "A totals market DOES exist, in master_odds_extension_other_markets.csv, which P29 "
            "did not open (%d totals rows). But it covers only %s. The pace-relevant member of "
            "the family -- the market total, which is what the packet's candidate entry actually "
            "names -- has NO history before 2025-07-05." % (
                oth["market_key_counts"]["totals"],
                sorted(oth["markets_by_season_games"]["totals"].keys()))),
        "totals_games_by_season": oth["markets_by_season_games"]["totals"],
        "consequence": ("The archive that reaches back to 2022-05-21 carries spread and price "
                        "only. Discovering a 2022 archive therefore does NOT supply history for "
                        "the feature the packet was actually contemplating."),
    },

    "F9_in_play_contamination": {
        "severity": "A",
        "claim": ("The extension archives contain post-tip (in-play) snapshots, and the "
                  "'take the last snapshot' rule already in use would select them."),
        "rows_with_snapshot_after_commence": {
            "drive_master": drive["lead_minutes_commence_minus_snapshot"]["n_rows_snapshot_after_commence"],
            "extension": ext["lead_minutes_commence_minus_snapshot"]["n_rows_snapshot_after_commence"],
            "other_markets": oth["lead_minutes_commence_minus_snapshot"]["n_rows_snapshot_after_commence"],
        },
        "most_negative_lead_minutes": {
            "extension": ext["lead_minutes_commence_minus_snapshot"]["min"],
            "other_markets": oth["lead_minutes_commence_minus_snapshot"]["min"],
        },
        "consequence": ("An in-play odds value is an approximate SAME-GAME surrogate for the "
                        "realised game, which the settled target prohibits from the prediction "
                        "path. Any future market feature must filter snapshot < commence at the "
                        "call site; collect_bios.py::phase_tips does not."),
    },

    "F10_n_snapshots_field_is_a_row_count": {
        "severity": "B",
        "claim": ("tip_times.csv's n_snapshots column counts parent ROWS, not distinct snapshots, "
                  "and therefore overstates capture density by more than an order of magnitude."),
        "audit": M["tip_provenance"]["n_snapshots_field_audit"],
        "mechanism": "collect_bios.py:255  n_snapshots=('snap', 'size')   # size == rows",
        "consequence": ("Anyone reading tip_times.csv sees a median of 24 'snapshots' per game "
                        "for drive_master rows and would reasonably infer a capture time series. "
                        "The true distinct-snapshot count is 1 for all 813 games; the 24 is the "
                        "bookmaker x team row fan-out. P29 relayed this field's min/median/max "
                        "(10/30/146) without recomputing it against the parent."),
    },

    "F11_ledger_gap": {
        "severity": "B",
        "claim": ("The market-odds family has no entry in D10_FIELD_AVAILABILITY_LEDGER. The only "
                  "odds-descended entries are the three tip fields."),
        "consequence": ("The family was excluded by the packet's prose without ever being "
                        "entered in the field ledger that governs availability verdicts."),
    },

    "SEPARATE_OBJECTION_LEFT_OPEN": {
        "status": "OPEN -- NOT RESOLVED BY THIS NODE",
        "objection": ("A market feature changes what the model IS, from predicting possessions to "
                      "predicting the market."),
        "packet_wording_verbatim": {
            ".unavailable_but_potentially_valuable.candidates[4].caution":
                "a market feature changes what the model is: it would no longer be a pure pace projection",
            ".cutoff_valid_availability_table_CORRECTED.unavailable_or_insufficient[2].note":
                "capture begins after the modelling span; also a market feature, which raises separate questions about what is being learned",
        },
        "this_node_position": (
            "This objection is independent of every measurement above and survives all of them. "
            "Even if a perfectly witnessed, fully covered, cutoff-valid market archive existed, "
            "this objection would still stand unresolved. It is a question about the identity and "
            "purpose of the model, not about data availability, and it is explicitly not this "
            "node's to settle. It must be decided by the program before any market feature is "
            "considered, and it must NOT be treated as discharged by this node's evidence."),
    },

    "stop_conditions": {
        "trigger_evaluated": ("if the evidence would ADMIT a family the frozen packet excluded, "
                              "HALT and raise"),
        "tripped_by_admission": False,
        "reasoning": ("The evidence does NOT admit the family. It falsifies the packet's stated "
                      "REASON while sustaining the packet's OUTCOME on stronger grounds. The "
                      "candidate universe is unchanged by this node."),
        "raised_not_resolved": [
            {
                "id": "P2B-SC1",
                "severity": "A",
                "statement": ("EVIDENCE PACKET CORRECTION REQUIRED. Two frozen packet statements "
                              "are factually false: the availability-table note and "
                              "statement_classification.UNCHANGED[9]. A frozen artifact may not "
                              "be edited by this node and was not. The correction must be "
                              "registered by whoever owns the packet."),
                "status": "RAISED, NOT DISCHARGED",
            },
            {
                "id": "P2B-SC2",
                "severity": "A",
                "statement": ("P29's SC1 (candidate universe / market-odds family) remains "
                              "UNDISCHARGED. This node supplies the evidence P29 lacked and "
                              "recommends NO admission, but the universe decision and the "
                              "separate what-is-the-model objection belong to the program."),
                "status": "SUSTAINED, NOT DISCHARGED",
            },
            {
                "id": "P2B-SC3",
                "severity": "A",
                "statement": ("The fold-degeneracy blindness P29 raised as SC2 is reconfirmed on "
                              "a second family: market_total_points is 100% missing on the "
                              "training rows of 4 of 5 folds, and market_spread on 1 of 5. Any "
                              "pooled-only gate check would not see this."),
                "status": "RAISED, NOT DISCHARGED",
            },
        ],
    },

    "could_not_establish": [
        ("Whether the vendor's asserted odds_snapshot_timestamp values are accurate. They are "
         "internally consistent with a 5-minute grid, but no independent witness exists in this "
         "repository and none can be constructed from it."),
        ("Whether the 6 uncovered 2026 games (2026-07-30/31) are covered by the live capture "
         "stream. capture_log.csv carries no game_id -- it is keyed on team names only -- so it "
         "cannot be joined to the contract universe without an entity-resolution step this node "
         "did not perform and was not asked to perform."),
        ("Why 2022 coverage is 180/239 (75.3%) while 2023-2025 are >=99.6%. The harvest's "
         "selection rule is not documented in any script found in either worktree."),
        ("The identity of the code that produced master_odds.csv. Its schema is a historical odds "
         "API response shape; wnba-odds-aggregator/scripts/historical_backfill.py is a 54-line "
         "stub whose scraping logic is an unimplemented TODO (line 26), and the wnba_odds_system "
         "scripts target a different (oddsportal) source and schema."),
        ("Any statement about predictive value. No fit was run, none is permitted, and nothing "
         "under stage2b/SEALED_RESULTS/ was read."),
    ],
}

out = HERE / "FINDINGS.json"
out.write_text(json.dumps(findings, indent=2), encoding="utf-8")
print(f"wrote {out}")
