#!/usr/bin/env python3
"""stage15_receipts.py — the complete Stage-1.5 receipt set, required before v15 generation.

**Nothing here is scored.** Row counts, tier splits, field presence, hashes and test results only.
No model is fitted, no forecast is read, no metric is computed. `appeared` is used to declare
SCOREABILITY and to count universe misses, never to grade anything.

Run::

    python experiments/player_program/stage15_receipts.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore")

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))

import prediction_contract_v5 as v5                                  # noqa: E402
import prediction_contract_v5_enrich as en                           # noqa: E402

OUT = REPO / "experiments" / "prediction_contract_v5"
TARGETS = en.PLAYER_TARGETS

#: Every file whose bytes can change what the v15 arm would consume. Hashed here so the
#: execution-bound registration `/2` can quote artifacts rather than transcribe names.
IMPLEMENTATION_FILES = (
    "prediction_contract_v5.py",
    "prediction_contract_v5_enrich.py",
    "tests/test_prediction_contract_v5.py",
    "tests/test_prediction_contract_v5_enrich.py",
    "cbs_obligation_key.py",
)

SOURCE_FILES = (
    "data/masters/master_player.parquet",
    "experiments/prediction_contract_v4/player_game.parquet",
    "data/injury_history/injury_history.csv",
    "data/injury_capture/injury_log.csv",
)

COLUMN_DICTIONARY = {
    "row_uid": "canonical obligation key = cbs_obligation_key.row_uid(player_id, game_id, team_id)",
    "universe_tier": "A verified obligation | B fallback candidate. Tier C is never in this file",
    "evaluation_tier": "A_primary | B_transaction_sensitivity | B_s2_weak_fallback",
    "candidate_source": "every source that named this row, pipe-separated, in precedence order",
    "team_assignment_source": "the leading source that assigned the team",
    "team_assignment_confidence": "verified | probable | weak",
    "candidate_evidence_time": "the bound actually used for admission; strictly before the cutoff",
    "candidate_published_time": "when the evidence was published, or NULL if not knowable",
    "candidate_observed_time": "when this repository observed the evidence",
    "roster_evidence_regime": "captured_asof | retrospective_effective_date | weak_prior_season",
    "src_asof_roster": "captured pre-cutoff roster evidence ONLY; NULL when none exists",
    "roster_asof_absent_reason": "the reason, in words, whenever it is NULL",
    "fit_eligible": "may enter coefficient fitting. True for Tier A only, per tier_a_fit_only/1",
    "is_fallback": "S2-only rows: fallback/sensitivity prediction only",
    "is_cold_start": "no prior appearance this season; derived from n_prior_appearances",
    "history_admissible_from": "when this row's outcome becomes historically known (+36h)",
    "history_eligible_after_event": "may inform LATER predictions once admissible; never its own",
    "team_assignment_ambiguous": "this player is claimed by more than one club for this game",
    "team_assignment_ambiguity_state": "unambiguous | claimed_by_multiple_teams__*",
    "n_prior_candidate_obligations": "obligations in the same (player, season) with a strictly "
                                     "earlier cutoff",
    "n_prior_appearances": "admitted prior appearances in the same (player, season)",
    "n_prior_team_games": "admitted prior games of this team this season",
    "prediction_required__<target>": "derived from TIER; never from outcomes",
    "outcome_scoreable__<target>": "derived from OUTCOMES; never from tier",
    "appeared / minutes / pts / fga": "postgame LABELS. Inputs to scoreability declaration and to "
                                      "fitting; they may never be emitted in a forecast artifact",
    "cutoff_source": "inherited_from_v4 | derived_absent_from_v4",
    "cutoff_policy": "the registered cutoff policy for this row",
    "era": "box_only | report_assisted",
}


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=str(HERE / "STAGE15_RECEIPT.json"))
    args = ap.parse_args()

    df = pd.read_parquet(OUT / "player_game_enriched.parquet")
    tc = pd.read_parquet(OUT / "candidacy_exclusions.parquet")
    v4 = pd.read_parquet(REPO / v5.V4_CONTRACT)
    v4k = set(zip(v4["game_id"].astype(str), v4["team_id"].astype("int64"),
                  v4["player_id"].astype("int64")))
    v5k = set(zip(df["game_id"].astype(str), df["team_id"].astype("int64"),
                  df["player_id"].astype("int64")))

    def by_tier(frame, fn):
        return {t: fn(g) for t, g in frame.groupby("evaluation_tier")}

    rows_by_season_tier = {}
    for (s, t), g in df.groupby(["season", "evaluation_tier"]):
        rows_by_season_tier.setdefault(str(int(s)), {})[t] = int(len(g))

    tests = {}
    for name in ("STAGE15_TEST_RECEIPT.json",):
        p = HERE / name
        if p.exists():
            d = json.loads(p.read_text(encoding="utf-8"))
            tests[name] = {"n_checks": d["n_checks"], "n_passed": d["n_passed"],
                           "all_passed": d["all_passed"]}

    receipt = {
        "schema": "stage15_receipt/1",
        "generated_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "stage": "1.5 — contract adapter. NOTHING IS FITTED, PREDICTED OR SCORED.",
        "contract_version": en.CONTRACT_VERSION,

        "schema_and_column_dictionary": {
            "n_columns": int(df.shape[1]),
            "columns": sorted(df.columns.tolist()),
            "dictionary": COLUMN_DICTIONARY,
        },

        "rows": {
            "total": int(len(df)),
            "by_season": {str(int(s)): int(n) for s, n in df.groupby("season").size().items()},
            "by_evaluation_tier": {k: int(v) for k, v in
                                   df["evaluation_tier"].value_counts().items()},
            "by_season_and_tier": rows_by_season_tier,
            "by_universe_tier": {k: int(v) for k, v in df["universe_tier"].value_counts().items()},
            "by_era": {k: int(v) for k, v in df["era"].value_counts().items()},
        },

        "required_predictions_by_target_and_tier": {
            t: by_tier(df, lambda g, t=t: int(g[f"prediction_required__{t}"].sum()))
            for t in TARGETS},
        "scoreable_outcomes_by_target_and_tier": {
            t: by_tier(df, lambda g, t=t: int(g[f"outcome_scoreable__{t}"].sum()))
            for t in TARGETS},
        "required_and_scoreable_are_independent": {
            "required_but_unscoreable_by_target": {
                t: int((df[f"prediction_required__{t}"]
                        & ~df[f"outcome_scoreable__{t}"]).sum()) for t in TARGETS},
            "scoreable_but_not_required": {
                t: int((df[f"outcome_scoreable__{t}"]
                        & ~df[f"prediction_required__{t}"]).sum()) for t in TARGETS},
        },

        "fallback_and_cold_start": {
            "n_fallback": int(df["is_fallback"].sum()),
            "n_cold_start": int(df["is_cold_start"].sum()),
            "by_tier": by_tier(df, lambda g: {"n_fallback": int(g["is_fallback"].sum()),
                                              "n_cold_start": int(g["is_cold_start"].sum())}),
        },

        "fitting_and_history_roles": {
            "rows_entering_coefficient_fitting": int(df["fit_eligible"].sum()),
            "policy": "tier_a_fit_only/1",
            "rows_predicted_but_not_fit": int((~df["fit_eligible"]).sum()),
            "rows_used_only_as_later_historical_observations": int(
                (~df["fit_eligible"] & df["history_eligible_after_event"]).sum()),
            "fallback_only_rows": int(df["is_fallback"].sum()),
            "temporal_rule": ("a Tier B player-game may inform a LATER prediction once its "
                              "outcome is admissible (+36h). It may not affect its own "
                              "prediction, nor one at the same cutoff, nor enter coefficient "
                              "fitting, nor retroactively establish pregame candidacy."),
            "temporal_rule_enforced": "history_admissible_from > forecast_cutoff on every row",
        },

        "tier_b_split": {
            "transaction_derived": int((df["evaluation_tier"]
                                        == "B_transaction_sensitivity").sum()),
            "s2_only_weak": int((df["evaluation_tier"] == "B_s2_weak_fallback").sum()),
            "never_pooled": True,
            "why_s2_is_reported_separately": ("its sole-source appearance rate is 0.87% against "
                                              "34.5% for transaction-derived rows"),
        },

        "exclusions_and_audit_only": {
            "tier_c_rows": int(len(tc)),
            "in_contract": False,
            "artifact": "candidacy_exclusions.parquet",
            "by_season": {str(int(s)): int(n) for s, n in tc.groupby("season").size().items()}
            if len(tc) else {},
            "remaining_universe_misses": int(len(tc)),
            "coverage_accounting_note": ("counted here, never silently discarded and never "
                                         "silently admitted to the contract"),
        },

        "cutoff_sources": {k: int(v) for k, v in df["cutoff_source"].value_counts().items()},
        "cutoff_policies": {str(k): int(v) for k, v in df["cutoff_policy"].value_counts().items()},

        "identity_and_ambiguity": {
            "n_duplicate_row_uid": int(df["row_uid"].duplicated().sum()),
            "n_duplicate_game_team_player": int(
                df.duplicated(["game_id", "team_id", "player_id"]).sum()),
            "n_cross_team_ambiguous_rows": int(df["team_assignment_ambiguous"].sum()),
            "n_distinct_player_games_with_ambiguity": int(
                df.loc[df["team_assignment_ambiguous"], "player_game_uid"].nunique()),
            "ambiguity_states": {k: int(v) for k, v in
                                 df["team_assignment_ambiguity_state"].value_counts().items()},
        },

        "superset_over_v4": {
            "n_v4": len(v4k), "n_v5": len(v5k),
            "n_added": len(v5k - v4k), "n_lost": len(v4k - v5k),
            "superset_holds": not (v4k - v5k),
        },

        "roster_evidence_regimes": {k: int(v) for k, v in
                                    df["roster_evidence_regime"].value_counts().items()},
        "src_asof_roster_null_where_not_captured": int(
            df.loc[df["roster_evidence_regime"] != "captured_asof", "src_asof_roster"].isna()
            .sum()),

        "hashes": {
            "contract_enriched_sha256": _sha(OUT / "player_game_enriched.parquet"),
            "candidate_universe_sha256": _sha(OUT / "player_game.parquet"),
            "exclusions_sha256": _sha(OUT / "candidacy_exclusions.parquet"),
            "implementation": {f: _sha(REPO / f) for f in IMPLEMENTATION_FILES},
            "source_snapshot": {f: _sha(REPO / f) for f in SOURCE_FILES},
        },

        "tests": tests,
        "scoring_permitted": False,
        "next_step": ("register cbs_v15_player_oof_v5/2 with these implementation hashes, then "
                      "request authorization to generate the v15 OOF artifact"),
    }
    Path(args.out).write_text(json.dumps(receipt, indent=2, default=str) + "\n",
                              encoding="utf-8", newline="")
    print(f"wrote {args.out}\n")
    print(f"rows {receipt['rows']['total']}  columns {receipt['schema_and_column_dictionary']['n_columns']}")
    print("by evaluation tier:", receipt["rows"]["by_evaluation_tier"])
    print("fitting rows      :", receipt["fitting_and_history_roles"]
          ["rows_entering_coefficient_fitting"])
    print("predicted not fit :", receipt["fitting_and_history_roles"]["rows_predicted_but_not_fit"])
    print("later-history only:", receipt["fitting_and_history_roles"]
          ["rows_used_only_as_later_historical_observations"])
    print("tier C (audit)    :", receipt["exclusions_and_audit_only"]["tier_c_rows"])
    print("superset over v4  :", receipt["superset_over_v4"])
    print("tests             :", receipt["tests"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
