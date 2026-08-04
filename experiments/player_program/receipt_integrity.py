#!/usr/bin/env python3
"""receipt_integrity.py — PERMANENT receipt-integrity gate for registered artifact families.

Born from the turnover receipt-drift defect: `canonical_player_events/1` was rebuilt under the
source-aware exact-duplicate policy (`source_aware_exact_duplicate/1`, 7 byte-identical legacy rows
dropped), `player_turnover_targets/1` was rebuilt on top of it, and **the validation receipt was
never regenerated**. For four hours the frozen, published receipt for a FROZEN AND VALID artifact
asserted 42,083 turnover events, 39,279 player-attributed and a 2,989/2,990 external
reconciliation with one named off-by-one disagreement, while the artifact on disk contained
42,082 / 39,278 and reconciled 2,990/2,990 exactly. Nothing in the program noticed. The receipt
still said `"verdict": "PASS"`, and it was that PASS — not the artifact — that downstream work read.

A receipt is a claim about a specific sequence of bytes. It certifies nothing once those bytes
change. `"verdict": "PASS"` next to a stale hash is worse than no receipt at all, because it
converts an unvalidated artifact into an apparently validated one.

Call `audit_family(name)` or `sweep()` before trusting any registered artifact. Both return a
machine-readable audit and raise `ReceiptIntegrityFailure` on a blocking finding unless it is
explicitly adjudicated with a recorded reason.

Blocking finding kinds (13):

    artifact_missing              a declared artifact file is not on disk
    receipt_missing               a declared receipt is not on disk
    receipt_unreadable            the receipt is not parseable JSON
    receipt_hash_absent           the receipt records no hash for a declared artifact
    artifact_hash_mismatch        recorded content hash != recomputed content hash
    input_hash_mismatch           a pinned upstream input has changed since the receipt was written
    count_divergence              a count recorded in the receipt != the count recomputed from the artifact
    count_unrecomputable          the recount raised; fail closed rather than skip the cross-check
    producer_sha_absent           the receipt pins no producer, so producer drift is undetectable
    producer_version_divergence   producer/validator source hash differs from the hash in the receipt
    contract_version_divergence   schema / contract / parser version differs between artifact and receipt
    receipt_predates_artifact     the artifact was rebuilt and the receipt was not regenerated
    validation_verdict_not_pass   the receipt records a verdict that is not PASS

Non-blocking finding kinds:

    receipt_records_no_counts     the receipt carries no count this module knows how to recompute
    artifact_version_unbound      the artifact carries a version column no receipt records

Run::  python experiments/player_program/receipt_integrity.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np, pandas as pd                                                # noqa: E401,F401
import pyarrow.parquet as pq

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

BLOCKING = {"artifact_missing", "receipt_missing", "receipt_unreadable", "receipt_hash_absent",
            "artifact_hash_mismatch", "input_hash_mismatch", "count_divergence",
            "count_unrecomputable", "producer_sha_absent", "producer_version_divergence",
            "contract_version_divergence", "receipt_predates_artifact",
            "validation_verdict_not_pass"}

#: a producer writes the artifact and then its receipt, so the receipt is always the later file.
#: the tolerance absorbs filesystem timestamp granularity only -- it is NOT a grace period for a
#: rebuild. A rebuild moves the content hash, and the hash check is what actually decides.
MTIME_TOLERANCE_S = 2.0

_MISSING = object()


class ReceiptIntegrityFailure(RuntimeError):
    pass


# --------------------------------------------------------------------------- #
# primitives
# --------------------------------------------------------------------------- #
def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve(obj, path):
    """Resolve a JSON path. A ``check:<name>`` segment selects one record out of a checks list.

    Validation receipts in this program bury their counts inside ``checks[].detail``, keyed by the
    check name rather than by position. Positional indexing would silently bind to the wrong check
    the moment a validator gains or reorders a gate.
    """
    cur = obj
    for seg in path:
        if isinstance(seg, str) and seg.startswith("check:"):
            want = seg[len("check:"):]
            if not isinstance(cur, list):
                return _MISSING
            hit = [x for x in cur if isinstance(x, dict) and x.get("check") == want]
            if len(hit) != 1:
                return _MISSING
            cur = hit[0]
        elif isinstance(cur, dict):
            if seg not in cur:
                return _MISSING
            cur = cur[seg]
        elif isinstance(cur, list) and isinstance(seg, int):
            if seg >= len(cur):
                return _MISSING
            cur = cur[seg]
        else:
            return _MISSING
    return cur


def _distinct_column_values(path: Path, column: str) -> list:
    try:
        v = pd.read_parquet(path, columns=[column])[column]
    except Exception:                                                    # noqa: BLE001
        return []
    return sorted({str(x) for x in pd.unique(v)})


# --------------------------------------------------------------------------- #
# recounts -- recomputed from the artifact bytes, never from any receipt
# --------------------------------------------------------------------------- #
def _recount_turnover_targets(d: Path) -> dict[str, int]:
    P = pd.read_parquet(d / "player_turnover_targets_v1.parquet",
                        columns=["turnovers", "realised_off_possessions",
                                 "zero_possession_exposure", "rate_defined"])
    T = pd.read_parquet(d / "team_turnover_reconciliation_v1.parquet",
                        columns=["team_turnovers_total", "player_attributed",
                                 "team_unattributed", "diff_vs_external"])
    dv = T["diff_vs_external"]
    return {
        "player_game_rows": int(len(P)),
        "player_game_rows_with_zero_turnovers": int((P["turnovers"] == 0).sum()),
        "player_game_rows_with_turnovers": int((P["turnovers"] > 0).sum()),
        "player_turnovers_total": int(P["turnovers"].sum()),
        "team_game_rows": int(len(T)),
        "team_player_attributed": int(T["player_attributed"].sum()),
        "team_unattributed": int(T["team_unattributed"].sum()),
        "team_turnovers_total": int(T["team_turnovers_total"].sum()),
        "team_exact": int((dv == 0).sum()),
        "team_off_by_one": int((dv.abs() == 1).sum()),
        "team_larger": int((dv.abs() > 1).sum()),
        "player_rows_with_positive_exposure": int((P["realised_off_possessions"] > 0).sum()),
        "player_rows_zero_exposure": int(P["zero_possession_exposure"].sum()),
        "rate_defined_rows": int(P["rate_defined"].sum()),
    }


def _recount_event_contract(d: Path) -> dict[str, int]:
    f = d / "canonical_player_events_v1.parquet"
    E = pd.read_parquet(f, columns=["game_id", "event_family", "source_system", "quality",
                                    "taxonomy_from_text", "score_out_of_sequence"])
    fam = E["event_family"].astype(str)
    src = E["source_system"].astype(str)
    return {
        "canonical_rows": int(pq.ParquetFile(f).metadata.num_rows),
        "universe_games": int(E["game_id"].nunique()),
        "turnover_rows": int((fam == "turnover").sum()),
        "turnover_rows_cdn": int(((fam == "turnover") & (src == "nba_cdn_playbyplay")).sum()),
        "turnover_rows_legacy": int(((fam == "turnover") & (src == "nba_playbyplayv2")).sum()),
        "rebound_rows": int((fam == "rebound").sum()),
        "replay_rows": int((fam == "replay_or_administrative").sum()),
        "quality_ok_rows": int((E["quality"].astype(str) == "ok").sum()),
        "quality_degraded_rows": int((E["quality"].astype(str) == "degraded").sum()),
        "taxonomy_from_text_rows": int(E["taxonomy_from_text"].astype(bool).sum()),
        "score_out_of_sequence_rows": int(E["score_out_of_sequence"].astype(bool).sum()),
    }


def _recount_projected_exposure(d: Path) -> dict[str, int]:
    pace = pd.read_parquet(d / "team_possession_prior_v1.parquet", columns=["game_id"])
    return {
        "player_rows": int(pq.ParquetFile(d / "projected_player_possessions_v1.parquet")
                           .metadata.num_rows),
        "rotation_rows": int(pq.ParquetFile(d / "projected_team_rotations_v1.parquet")
                             .metadata.num_rows),
        "pace_rows": int(pq.ParquetFile(d / "team_possession_prior_v1.parquet").metadata.num_rows),
        "pace_games": int(pace["game_id"].nunique()),
    }


# --------------------------------------------------------------------------- #
# family specifications
# --------------------------------------------------------------------------- #
FAMILIES: dict[str, dict] = {
    "projected_exposure_v1": {
        "artifact_id": "projected_player_possessions/1",
        "dir": "projected_exposure_v1",
        "producer": "build_projected_exposure.py",
        "validator": "validate_projected_exposure.py",
        "artifacts": {
            "players": "projected_player_possessions_v1.parquet",
            "rotations": "projected_team_rotations_v1.parquet",
            "pace": "team_possession_prior_v1.parquet",
        },
        "recount": _recount_projected_exposure,
        "expected_versions": {"players": {"contract_version": "player_game_contract/5"}},
        "version_bindings": [],
        "receipts": [
            {
                "file": "PROJECTED_EXPOSURE_RECEIPT.json",
                "role": "producer",
                "identity": {"schema": ("schema",),
                             "artifact_id": ("artifact_id",),
                             "pace_artifact_id": ("pace_artifact_id",)},
                "expect_identity": {"schema": "projected_exposure_receipt/1",
                                    "artifact_id": "projected_player_possessions/1",
                                    "pace_artifact_id": "team_possession_prior/1"},
                "hashes": {
                    "players": ("outputs", "projected_player_possessions_v1.parquet", "sha256"),
                    "rotations": ("outputs", "projected_team_rotations_v1.parquet", "sha256"),
                    "pace": ("outputs", "team_possession_prior_v1.parquet", "sha256"),
                },
                "producer_sha": ("producer", "sha256_after"),
                "inputs": {
                    ("inputs", "contract_v5", "sha256"):
                        "experiments/prediction_contract_v5/player_game_enriched.parquet",
                    ("inputs", "possessions", "sha256"):
                        "experiments/player_program/possessions_v2/possessions_raw_v2.parquet",
                },
                "counts": [
                    {"path": ("outputs", "projected_player_possessions_v1.parquet", "rows"),
                     "count": "player_rows"},
                    {"path": ("outputs", "projected_team_rotations_v1.parquet", "rows"),
                     "count": "rotation_rows"},
                    {"path": ("outputs", "team_possession_prior_v1.parquet", "rows"),
                     "count": "pace_rows"},
                    {"path": ("universe", "games"), "count": "pace_games"},
                ],
            },
            {
                "file": "PROJECTED_EXPOSURE_VALIDATION.json",
                "role": "validation",
                "identity": {"schema": ("schema",), "artifact_id": ("artifact_id",)},
                "expect_identity": {"schema": "projected_exposure_validation/2",
                                    "artifact_id": "projected_player_possessions/1"},
                "hashes": {
                    "players": ("artifact_sha256", "projected_player_possessions_v1.parquet"),
                    "rotations": ("artifact_sha256", "projected_team_rotations_v1.parquet"),
                    "pace": ("artifact_sha256", "team_possession_prior_v1.parquet"),
                },
                "producer_sha": ("producer_sha256",),
                "validator_sha": ("validator_sha256",),
                "verdict": ("verdict",),
                "counts": [
                    {"path": ("checks", "check:home_away_accounting_reconciles", "detail",
                              "team_game_rows_total"), "count": "rotation_rows"},
                    {"path": ("checks", "check:pace_matches_independent_rederivation", "detail",
                              "team_games"), "count": "pace_rows"},
                    {"path": ("checks", "check:grain_arithmetic_reconciles", "detail", "games"),
                     "count": "pace_games"},
                    {"path": ("checks", "check:per_regime_reconciliation_closes", "detail",
                              "games"), "count": "pace_games"},
                ],
            },
        ],
    },
    "event_contract_v1": {
        "artifact_id": "canonical_player_events/1",
        "dir": "event_contract_v1",
        "producer": "build_canonical_events.py",
        "validator": "validate_canonical_events.py",
        "artifacts": {"events": "canonical_player_events_v1.parquet"},
        "recount": _recount_event_contract,
        "expected_versions": {"events": {"parser_version": "canonical_player_events/1",
                                         "contract_version": "player_event_contract/1"}},
        # the artifact CARRIES its own parser/contract version in every row; the receipt states
        # them separately. A producer that changes one without the other is exactly the drift.
        "version_bindings": [
            {"artifact": "events", "column": "parser_version",
             "receipt": "EVENT_NORMALISATION_RECEIPT.json", "path": ("parser_version",)},
            {"artifact": "events", "column": "contract_version",
             "receipt": "EVENT_NORMALISATION_RECEIPT.json", "path": ("contract_version",)},
        ],
        "receipts": [
            {
                "file": "EVENT_NORMALISATION_RECEIPT.json",
                "role": "producer",
                "identity": {"schema": ("schema",), "artifact_id": ("artifact_id",),
                             "experiment_id": ("experiment_id",)},
                "expect_identity": {"schema": "canonical_event_receipt/1",
                                    "artifact_id": "canonical_player_events/1",
                                    "experiment_id": "canonical_player_events_v1"},
                "hashes": {"events": ("artifact_sha256",)},
                "producer_sha": ("producer", "sha256_after"),
                "counts": [
                    {"path": ("canonical_rows",), "count": "canonical_rows"},
                    {"path": ("row_reconciliation", "canonical_total"), "count": "canonical_rows"},
                    {"path": ("universe_games",), "count": "universe_games"},
                    {"path": ("quality_counts", "ok"), "count": "quality_ok_rows"},
                    {"path": ("quality_counts", "degraded"), "count": "quality_degraded_rows"},
                    {"path": ("taxonomy_from_text_rows",), "count": "taxonomy_from_text_rows"},
                    {"path": ("flag_counts", "taxonomy_from_text"),
                     "count": "taxonomy_from_text_rows"},
                    {"path": ("flag_counts", "score_out_of_sequence"),
                     "count": "score_out_of_sequence_rows"},
                    {"path": ("family_counts_by_source", "turnover", "nba_cdn_playbyplay"),
                     "count": "turnover_rows_cdn"},
                    {"path": ("family_counts_by_source", "turnover", "nba_playbyplayv2"),
                     "count": "turnover_rows_legacy"},
                ],
            },
            {
                "file": "EVENT_VALIDATION.json",
                "role": "validation",
                "identity": {"schema": ("schema",), "artifact_id": ("artifact_id",)},
                "expect_identity": {"schema": "canonical_event_validation/1",
                                    "artifact_id": "canonical_player_events/1"},
                "hashes": {"events": ("artifact_sha256",)},
                "producer_sha": ("producer_sha256",),
                "validator_sha": ("validator_sha256",),
                "verdict": ("verdict",),
                "counts": [
                    {"path": ("checks", "check:all_universe_games_accounted", "detail", "events"),
                     "count": "canonical_rows"},
                    {"path": ("checks", "check:all_universe_games_accounted", "detail", "games"),
                     "count": "universe_games"},
                    {"path": ("checks", "check:canonical_keys_unique", "detail", "rows"),
                     "count": "canonical_rows"},
                    {"path": ("checks", "check:deterministic_rebuild", "detail", "rows_compared"),
                     "count": "canonical_rows"},
                    {"path": ("checks", "check:row_counts_reconcile_to_raw", "detail",
                              "canonical_total"), "count": "canonical_rows"},
                    {"path": ("checks", "check:structural_comparison_with_possessions", "detail",
                              "event_rows"), "count": "canonical_rows"},
                    {"path": ("checks", "check:no_future_information_used", "detail",
                              "rows_traceable_to_own_game_file"), "count": "canonical_rows"},
                    {"path": ("checks", "check:no_information_from_outside_the_event_file",
                              "detail", "event_files"), "count": "universe_games"},
                    {"path": ("checks", "check:taxonomy_covers_all_raw_values", "detail",
                              "rows_typed_from_description_text"),
                     "count": "taxonomy_from_text_rows"},
                ],
            },
        ],
    },
    "turnover_targets_v1": {
        "artifact_id": "player_turnover_targets/1",
        "dir": "turnover_targets_v1",
        "producer": "build_turnover_targets.py",
        "validator": "validate_turnover_targets.py",
        "artifacts": {"player": "player_turnover_targets_v1.parquet",
                      "team": "team_turnover_reconciliation_v1.parquet"},
        "recount": _recount_turnover_targets,
        "expected_versions": {},
        "version_bindings": [],
        "receipts": [
            {
                "file": "TURNOVER_TARGET_RECEIPT.json",
                "role": "producer",
                "identity": {"schema": ("schema",), "artifact_id": ("artifact_id",),
                             "experiment_id": ("experiment_id",)},
                "expect_identity": {"schema": "turnover_target_receipt/1",
                                    "artifact_id": "player_turnover_targets/1",
                                    "experiment_id": "turnover_target_contract_v1"},
                "hashes": {"player": ("artifact_sha256", "player"),
                           "team": ("artifact_sha256", "team")},
                "producer_sha": ("producer_sha256",),
                # the defect travelled along exactly this edge: the events artifact was rebuilt
                # under the dedup policy and this receipt kept pointing at the pre-dedup bytes.
                "inputs": {
                    ("inputs", "events"):
                        "experiments/player_program/event_contract_v1/"
                        "canonical_player_events_v1.parquet",
                    ("inputs", "possessions"):
                        "experiments/player_program/possessions_v2/possessions_raw_v2.parquet",
                    ("inputs", "master_player"): "data/masters/master_player.parquet",
                    ("inputs", "master_team"): "data/masters/master_team.parquet",
                },
                "counts": [
                    {"path": ("counts", "player_game_rows"), "count": "player_game_rows"},
                    {"path": ("counts", "player_game_rows_with_zero_turnovers"),
                     "count": "player_game_rows_with_zero_turnovers"},
                    {"path": ("counts", "team_game_rows"), "count": "team_game_rows"},
                    {"path": ("counts", "player_attributed"), "count": "team_player_attributed"},
                    {"path": ("counts", "team_unattributed"), "count": "team_unattributed"},
                    {"path": ("exposure", "player_rows_with_positive_exposure"),
                     "count": "player_rows_with_positive_exposure"},
                    {"path": ("exposure", "player_rows_zero_exposure"),
                     "count": "player_rows_zero_exposure"},
                    {"path": ("exposure", "rate_defined_rows"), "count": "rate_defined_rows"},
                    {"path": ("external_reconciliation_preview", "team_exact"),
                     "count": "team_exact"},
                    {"path": ("external_reconciliation_preview", "team_off_by_one"),
                     "count": "team_off_by_one"},
                    {"path": ("external_reconciliation_preview", "team_larger"),
                     "count": "team_larger"},
                ],
            },
            {
                "file": "TURNOVER_VALIDATION.json",
                "role": "validation",
                "identity": {"schema": ("schema",), "artifact_id": ("artifact_id",),
                             "experiment_id": ("experiment_id",)},
                "expect_identity": {"schema": "turnover_target_validation/1",
                                    "artifact_id": "player_turnover_targets/1",
                                    "experiment_id": "turnover_target_contract_v1"},
                "hashes": {"player": ("artifact_sha256", "player"),
                           "team": ("artifact_sha256", "team")},
                "producer_sha": ("producer_sha256",),
                "verdict": ("verdict",),
                "counts": [
                    {"path": ("checks", "check:mechanism_sums_to_player_total", "detail",
                              "player_rows"), "count": "player_game_rows"},
                    {"path": ("checks", "check:mechanism_sums_to_player_total", "detail",
                              "total_turnovers"), "count": "player_turnovers_total"},
                    {"path": ("checks", "check:mechanism_sums_to_player_total", "detail",
                              "total_from_mechanisms"), "count": "player_turnovers_total"},
                    {"path": ("checks", "check:components_sum_to_team_total", "detail",
                              "team_games"), "count": "team_game_rows"},
                    {"path": ("checks", "check:components_sum_to_team_total", "detail",
                              "player_attributed"), "count": "team_player_attributed"},
                    {"path": ("checks", "check:components_sum_to_team_total", "detail",
                              "team_unattributed"), "count": "team_unattributed"},
                    {"path": ("checks", "check:components_sum_to_team_total", "detail",
                              "team_total"), "count": "team_turnovers_total"},
                    {"path": ("checks", "check:no_duplicate_grain", "detail", "player_rows"),
                     "count": "player_game_rows"},
                    {"path": ("checks", "check:no_duplicate_grain", "detail", "team_rows"),
                     "count": "team_game_rows"},
                    {"path": ("checks", "check:zero_turnover_rows_retained", "detail",
                              "zero_turnover_rows"), "count": "player_game_rows_with_zero_turnovers"},
                    {"path": ("checks", "check:zero_turnover_rows_retained", "detail",
                              "nonzero_rows"), "count": "player_game_rows_with_turnovers"},
                    {"path": ("checks", "check:no_player_on_both_teams", "detail",
                              "players_with_turnovers"), "count": "player_game_rows_with_turnovers"},
                    {"path": ("checks", "check:universe_excludes_non_appearances", "detail",
                              "appeared_rows"), "count": "player_game_rows"},
                    {"path": ("checks", "check:exposure_coverage", "detail",
                              "rows_with_positive_exposure"),
                     "count": "player_rows_with_positive_exposure"},
                    {"path": ("checks", "check:exposure_coverage", "detail",
                              "rows_zero_reconstructed_exposure"),
                     "count": "player_rows_zero_exposure"},
                    {"path": ("checks", "check:exposure_coverage", "detail", "rate_defined_rows"),
                     "count": "rate_defined_rows"},
                    {"path": ("checks", "check:external_team_reconciliation", "detail",
                              "team_games"), "count": "team_game_rows"},
                    {"path": ("checks", "check:external_team_reconciliation", "detail", "exact"),
                     "count": "team_exact"},
                    {"path": ("checks", "check:external_team_reconciliation", "detail",
                              "off_by_one"), "count": "team_off_by_one"},
                    {"path": ("checks", "check:external_team_reconciliation", "detail", "larger"),
                     "count": "team_larger"},
                    {"path": ("checks", "check:external_player_reconciliation", "detail",
                              "rows_compared"), "count": "player_game_rows"},
                ],
            },
        ],
    },
}


# --------------------------------------------------------------------------- #
# adjudication
# --------------------------------------------------------------------------- #
def finding_key(f: dict) -> str:
    return "|".join([str(f.get("family", "-")), str(f.get("receipt", "-")),
                     str(f["kind"]), str(f.get("subject", "-"))])


def _adjudication_for(f: dict, adjudicated: dict) -> object:
    for k in (finding_key(f),
              f"{f.get('family', '-')}|{f.get('receipt', '-')}|{f['kind']}",
              f"{f.get('family', '-')}|{f['kind']}"):
        if adjudicated.get(k):
            return adjudicated[k]
    return None


# --------------------------------------------------------------------------- #
# the audit
# --------------------------------------------------------------------------- #
def audit_family(name: str, spec: dict | None = None, base: Path | None = None,
                 root: Path | None = None, adjudicated: dict | None = None,
                 mtime_tolerance_s: float = MTIME_TOLERANCE_S,
                 recount: bool = True, raise_on_block: bool = True) -> dict:
    """Audit one registered artifact family. Returns a machine-readable dict.

    ``base`` is the directory holding the family directory and the producer/validator sources
    (defaults to this module's directory). ``root`` is the repository root used to resolve pinned
    upstream inputs. Tests point both at temporary copies; nothing here writes.
    """
    spec = spec or FAMILIES[name]
    base = Path(base) if base is not None else HERE
    root = Path(root) if root is not None else ROOT
    adjudicated = adjudicated or {}
    fdir = base / spec["dir"]
    findings: list[dict] = []

    def add(kind: str, subject: str, **detail):
        findings.append({"family": name, "kind": kind, "subject": subject, **detail})

    # -- artifacts on disk and their true content hashes ---------------------- #
    actual_hash: dict[str, str] = {}
    artifact_mtime: dict[str, float] = {}
    for key, fname in spec["artifacts"].items():
        p = fdir / fname
        if not p.exists():
            add("artifact_missing", key, receipt="-", path=str(p))
            continue
        actual_hash[key] = sha256_file(p)
        artifact_mtime[key] = p.stat().st_mtime

    # -- producer / validator source hashes ---------------------------------- #
    src_hash: dict[str, str | None] = {}
    for role in ("producer", "validator"):
        rel = spec.get(role)
        if not rel:
            src_hash[role] = None
            continue
        p = base / rel
        src_hash[role] = sha256_file(p) if p.exists() else None

    # -- version columns carried by the artifact itself ----------------------- #
    artifact_versions: dict[str, dict[str, list]] = {}
    for key, cols in (spec.get("expected_versions") or {}).items():
        if key not in actual_hash:
            continue
        p = fdir / spec["artifacts"][key]
        for col, expected in cols.items():
            vals = _distinct_column_values(p, col)
            artifact_versions.setdefault(key, {})[col] = vals
            if len(vals) != 1:
                add("contract_version_divergence", f"{key}.{col}", receipt="-",
                    reason="the artifact does not carry one single version",
                    values_in_artifact=vals[:8])
            elif vals[0] != expected:
                add("contract_version_divergence", f"{key}.{col}", receipt="-",
                    reason="artifact version differs from the registered contract version",
                    in_artifact=vals[0], registered=expected)
    for b in spec.get("version_bindings") or []:
        key = b["artifact"]
        if key not in actual_hash:
            continue
        p = fdir / spec["artifacts"][key]
        vals = artifact_versions.get(key, {}).get(b["column"])
        if vals is None:
            vals = _distinct_column_values(p, b["column"])
            artifact_versions.setdefault(key, {})[b["column"]] = vals
        rp = fdir / b["receipt"]
        if not rp.exists():
            continue
        try:
            rj = json.loads(rp.read_text(encoding="utf-8"))
        except Exception:                                                # noqa: BLE001
            continue
        rec = resolve(rj, b["path"])
        if rec is _MISSING:
            add("artifact_version_unbound", f"{key}.{b['column']}", receipt=b["receipt"],
                reason="the artifact carries this version but the receipt does not record it")
        elif len(vals) == 1 and str(rec) != vals[0]:
            add("contract_version_divergence", f"{key}.{b['column']}", receipt=b["receipt"],
                reason="version differs between artifact and receipt",
                in_artifact=vals[0], in_receipt=str(rec))

    # -- recount from the artifact bytes ------------------------------------- #
    counts: dict[str, int] = {}
    recount_error: str | None = None
    if recount and spec.get("recount") is not None and len(actual_hash) == len(spec["artifacts"]):
        try:
            counts = spec["recount"](fdir)
        except Exception as exc:                                         # noqa: BLE001
            recount_error = f"{type(exc).__name__}: {exc}"
            add("count_unrecomputable", "__recount__", receipt="-", error=recount_error)

    # -- per receipt ---------------------------------------------------------- #
    receipts_seen: dict[str, dict] = {}
    for r in spec["receipts"]:
        rname = r["file"]
        rp = fdir / rname
        if not rp.exists():
            add("receipt_missing", rname, receipt=rname, path=str(rp))
            continue
        try:
            R = json.loads(rp.read_text(encoding="utf-8"))
        except Exception as exc:                                         # noqa: BLE001
            add("receipt_unreadable", rname, receipt=rname,
                error=f"{type(exc).__name__}: {exc}")
            continue
        receipts_seen[rname] = R
        rmtime = rp.stat().st_mtime

        # identity / contract fields
        for label, path in (r.get("identity") or {}).items():
            got = resolve(R, path)
            want = (r.get("expect_identity") or {}).get(label)
            if got is _MISSING:
                add("contract_version_divergence", label, receipt=rname,
                    reason="the receipt does not state this contract field", expected=want)
            elif want is not None and got != want:
                add("contract_version_divergence", label, receipt=rname,
                    reason="the receipt states a different contract identity",
                    in_receipt=got, registered=want)

        # artifact content hashes
        for key in spec["artifacts"]:
            path = (r.get("hashes") or {}).get(key)
            if path is None:
                add("receipt_hash_absent", key, receipt=rname,
                    reason="this receipt declares no hash for a declared artifact")
                continue
            rec = resolve(R, path)
            if rec is _MISSING or not isinstance(rec, str):
                add("receipt_hash_absent", key, receipt=rname, json_path=list(path))
            elif key in actual_hash and rec != actual_hash[key]:
                add("artifact_hash_mismatch", key, receipt=rname,
                    in_receipt=rec, on_disk=actual_hash[key],
                    reason="the receipt certifies bytes that are no longer on disk")

        # pinned upstream inputs
        for path, rel in (r.get("inputs") or {}).items():
            rec = resolve(R, path)
            if rec is _MISSING or not isinstance(rec, str):
                continue
            ip = root / rel
            if not ip.exists():
                add("input_hash_mismatch", rel, receipt=rname,
                    reason="a pinned upstream input is missing", in_receipt=rec, on_disk=None)
                continue
            got = sha256_file(ip)
            if got != rec:
                add("input_hash_mismatch", rel, receipt=rname,
                    in_receipt=rec, on_disk=got,
                    reason="a pinned upstream input changed after this receipt was written; "
                           "the artifact it certifies was built from different bytes")

        # producer / validator pinning
        for role, key in (("producer", "producer_sha"), ("validator", "validator_sha")):
            path = r.get(key)
            if path is None:
                if role == "producer":
                    add("producer_sha_absent", role, receipt=rname,
                        reason="the receipt pins no producer, so producer drift is undetectable")
                continue
            rec = resolve(R, path)
            if rec is _MISSING or not isinstance(rec, str):
                add("producer_sha_absent", role, receipt=rname, json_path=list(path))
            elif src_hash.get(role) is None:
                add("producer_version_divergence", role, receipt=rname,
                    reason="the pinned source file is not on disk", in_receipt=rec, on_disk=None)
            elif rec != src_hash[role]:
                add("producer_version_divergence", role, receipt=rname,
                    in_receipt=rec, on_disk=src_hash[role],
                    reason=f"the {role} source changed after this receipt was written")

        # recorded verdict
        vpath = r.get("verdict")
        if vpath is not None:
            v = resolve(R, vpath)
            if v is _MISSING or str(v).upper() != "PASS":
                add("validation_verdict_not_pass", "verdict", receipt=rname,
                    in_receipt=(None if v is _MISSING else v))

        # counts recorded vs counts recomputed
        bound = 0
        for c in r.get("counts") or []:
            ckey = c.get("count")
            if ckey is None:
                continue
            rec = resolve(R, c["path"])
            if rec is _MISSING:
                continue
            if ckey not in counts:
                if recount and recount_error is None and spec.get("recount") is not None:
                    add("count_unrecomputable", ckey, receipt=rname,
                        json_path=list(c["path"]),
                        error="no recount produced this key")
                continue
            bound += 1
            if int(rec) != int(counts[ckey]):
                add("count_divergence", ckey, receipt=rname,
                    json_path=list(c["path"]),
                    in_receipt=int(rec), recomputed=int(counts[ckey]),
                    delta=int(rec) - int(counts[ckey]))
        if bound == 0 and counts:
            add("receipt_records_no_counts", rname, receipt=rname,
                reason="nothing in this receipt could be cross-checked against the artifact")

        # rebuilt-without-revalidation: the receipt must not predate the artifact it certifies
        for key, amt in artifact_mtime.items():
            if rmtime + mtime_tolerance_s < amt:
                add("receipt_predates_artifact", key, receipt=rname,
                    artifact_mtime=datetime.fromtimestamp(amt, timezone.utc).isoformat(),
                    receipt_mtime=datetime.fromtimestamp(rmtime, timezone.utc).isoformat(),
                    seconds_stale=round(amt - rmtime, 3),
                    reason="the artifact was written after this receipt; it was rebuilt without "
                           "regenerating the receipt")

    # -- adjudication and verdict -------------------------------------------- #
    blocking = []
    for f in findings:
        if f["kind"] not in BLOCKING:
            continue
        adj = _adjudication_for(f, adjudicated)
        if adj:
            f["adjudicated"] = adj
        else:
            blocking.append(f)

    out = {
        "family": name,
        "artifact_id": spec.get("artifact_id"),
        "dir": str(fdir),
        "artifacts": {k: {"file": spec["artifacts"][k], "sha256": actual_hash.get(k)}
                      for k in spec["artifacts"]},
        "producer_sha256": src_hash.get("producer"),
        "validator_sha256": src_hash.get("validator"),
        "artifact_versions": artifact_versions,
        "recomputed_counts": counts,
        "recount_error": recount_error,
        "receipts_checked": [r["file"] for r in spec["receipts"]],
        "findings": findings,
        "blocking": blocking,
        "passed": len(blocking) == 0,
        "note": "a receipt is a claim about specific bytes; it certifies nothing once they change",
    }
    if blocking and raise_on_block:
        raise ReceiptIntegrityFailure(json.dumps(blocking[:6], default=str))
    return out


def sweep(families: list[str] | None = None, base: Path | None = None, root: Path | None = None,
          adjudicated: dict | None = None, mtime_tolerance_s: float = MTIME_TOLERANCE_S,
          recount: bool = True, raise_on_block: bool = True) -> dict:
    """Audit every registered family. Never stops at the first failure."""
    names = families or list(FAMILIES)
    results, blocking = {}, []
    for n in names:
        r = audit_family(n, base=base, root=root, adjudicated=adjudicated,
                         mtime_tolerance_s=mtime_tolerance_s, recount=recount,
                         raise_on_block=False)
        results[n] = r
        blocking.extend(r["blocking"])
    out = {
        "schema": "receipt_integrity_sweep/1",
        "swept_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "families": names,
        "per_family": {n: {"passed": results[n]["passed"],
                           "n_findings": len(results[n]["findings"]),
                           "n_blocking": len(results[n]["blocking"]),
                           "blocking_kinds": sorted({f["kind"] for f in results[n]["blocking"]}),
                           "counts_cross_checked": len(results[n]["recomputed_counts"])}
                       for n in names},
        "results": results,
        "blocking": blocking,
        "blocking_kinds": sorted({f["kind"] for f in blocking}),
        "passed": len(blocking) == 0,
    }
    if blocking and raise_on_block:
        raise ReceiptIntegrityFailure(json.dumps(blocking[:6], default=str))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="receipt-integrity sweep")
    ap.add_argument("--family", action="append", choices=sorted(FAMILIES),
                    help="restrict the sweep (repeatable)")
    ap.add_argument("--json", type=Path, help="write the full machine-readable sweep here")
    ap.add_argument("--no-recount", action="store_true",
                    help="skip artifact recomputation (hash and version checks only)")
    a = ap.parse_args(argv)

    s = sweep(families=a.family, recount=not a.no_recount, raise_on_block=False)
    for n in s["families"]:
        r = s["per_family"][n]
        print(f"  {'PASS' if r['passed'] else 'FAIL'}  {n:<24} "
              f"findings {r['n_findings']:>2}  blocking {r['n_blocking']:>2}  "
              f"counts cross-checked {r['counts_cross_checked']:>2}")
    for f in s["blocking"]:
        print(f"    BLOCK {f['family']}/{f.get('receipt', '-')}: {f['kind']} [{f['subject']}] "
              f"{f.get('reason', '')}")
    if a.json:
        a.json.write_text(json.dumps(s, indent=2, default=str), encoding="utf-8")
        print(f"  wrote {a.json}")
    print(f"\n{'PASS' if s['passed'] else 'FAIL'} -- {len(s['blocking'])} blocking finding(s) "
          f"across {len(s['families'])} famil{'y' if len(s['families']) == 1 else 'ies'}")
    return 0 if s["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
