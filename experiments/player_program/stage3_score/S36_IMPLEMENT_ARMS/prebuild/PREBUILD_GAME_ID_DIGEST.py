#!/usr/bin/env python3
"""PREBUILD_GAME_ID_DIGEST.py -- discharges S35 obligation O2 (S34 Severity C note C4).

Epistemic status: IMPLEMENTATION. Unit/synthetic/identity/schema tests only; no comparative
historical performance is revealed.

    O2: "before any design matrix is constructed, S36 MUST emit a pre-build digest of the game_id
         set of the 1,491-cluster universe and pin it into its own receipt, converting
         invariants.rows - deferred to S36 on all 17 records - from a deferred invariant into a
         receipted one BEFORE any fit runs."
    on_mismatch: "HALT before fitting."

THIS SCRIPT IMPORTS NOTHING THAT CAN BUILD A DESIGN MATRIX. That is deliberate and structural:
the obligation says "before any design matrix is constructed", and the cheapest way to make that
true rather than merely claimed is for the discharging script to be incapable of constructing one.
It imports `canon` (pure hashing) and `runner_constants` (pure pins) and nothing else from the
node. `universe.build_universe()` -- which everything downstream must call -- refuses to return a
frame unless this script's receipt exists and its digest re-derives.

Order of operations, fail-closed at every step:
  1. ROOT_PATH_RULE: hash data/masters/master_team.parquet in the PROGRAM WORKTREE; HALT on
     mismatch, and HALT BY NAME if the bytes are the known drifted copy.
  2. Re-derive the universe from those bytes (is_home==1, minus the D010 opening date).
  3. Re-derive every pinned census number rather than accepting S35's claim.
  4. Measure identity with the frozen store's league_average_v1 game_id set.
  5. Emit the digest and the receipt.

Run:  python prebuild/PREBUILD_GAME_ID_DIGEST.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runner"))

import pandas as pd  # noqa: E402

import runner_constants as K  # noqa: E402
from canon import (CANONICALISATION_STATEMENT, JOIN_KEY_SEPARATOR_STATEMENT,  # noqa: E402
                   column_digest, sha256_file)
from obligations import (O2_DIGEST_RULE, O2_ON_MISMATCH, O2_PREBUILD_DIGEST,  # noqa: E402
                         stamp_program_alpha, verify_obligation_text)

RECEIPT_PATH = Path(__file__).resolve().parents[1] / "PREBUILD_GAME_ID_DIGEST.json"


class PrebuildHalt(RuntimeError):
    """O2/O1 halt. The caller must stop and report, never proceed."""


def _halt(msg: str) -> None:
    raise PrebuildHalt(msg)


def verify_root_path_rule() -> dict:
    """Obligation O1 / ROOT_PATH_RULE. Verified HERE, independently, at this node -- the fact that
    the coordinator already checked it is not evidence (RESEARCH_CONTRACT_V1 Phase 2.1)."""
    K.assert_program_worktree()
    rel = "data/masters/master_team.parquet"
    path = K.artifact_path(rel)
    got = sha256_file(path)
    expect = K.INPUT_PINS[rel]
    if got == K.KNOWN_DRIFTED_MASTER_TEAM_SHA256:
        _halt(f"ROOT_PATH_RULE VIOLATED: {path} hashes to the KNOWN DRIFTED data-worktree copy "
              f"({got}). {K.ROOT_PATH_RULE} {O2_ON_MISMATCH}")
    if got != expect:
        _halt(f"ROOT_PATH_RULE VIOLATED: {path} sha256 {got} != pinned {expect}. HALT. Do not "
              f"build. A silent rebuild on drifted bytes voids the preregistration.")
    return {"rule": K.ROOT_PATH_RULE, "path_read": str(path),
            "path_is_program_worktree": True, "sha256": got, "pinned_sha256": expect,
            "match": True, "verified_independently_at_s36": True,
            "known_drifted_copy_sha256_refused_by_name": K.KNOWN_DRIFTED_MASTER_TEAM_SHA256}


def rederive_universe(mt: pd.DataFrame) -> dict:
    """Re-derive the 1,491-cluster universe from the pinned bytes. Every count is measured here,
    not copied from the freeze; the freeze's numbers are then compared to what was measured."""
    home = mt[mt["is_home"] == 1].copy()
    full_clusters = home["game_id"].nunique()
    full_rows = len(mt)

    first_date = str(mt["game_date"].min())
    excluded = home[home["game_date"].astype(str) == K.D010_EXCLUDED_DATE]
    universe_home = home[home["game_date"].astype(str) != K.D010_EXCLUDED_DATE].copy()
    game_ids = sorted(universe_home["game_id"].astype(str).tolist())
    n_clusters = len(set(game_ids))
    universe_rows = mt[mt["game_id"].isin(set(game_ids))]

    per_season = (universe_home.groupby("season")["game_id"].nunique().sort_index()
                  .astype(int).to_dict())
    per_season = {int(k): int(v) for k, v in per_season.items()}

    # E3 well-definedness and score completeness -- re-derived, not accepted.
    n_null_pts = int(universe_rows["pts"].isna().sum() + universe_rows["opp_pts"].isna().sum())
    ties = int((universe_home["pts"] == universe_home["opp_pts"]).sum())

    findings = []
    if full_clusters != K.FULL_SCHEDULE_CLUSTERS:
        findings.append(f"full schedule clusters {full_clusters} != {K.FULL_SCHEDULE_CLUSTERS}")
    if full_rows != K.FULL_SCHEDULE_ROWS:
        findings.append(f"full schedule rows {full_rows} != {K.FULL_SCHEDULE_ROWS}")
    if first_date != K.D010_EXCLUDED_DATE:
        findings.append(f"first game_date {first_date} != D010 excluded date "
                        f"{K.D010_EXCLUDED_DATE}")
    if len(excluded) != K.D010_EXCLUDED_CLUSTERS:
        findings.append(f"D010 excluded clusters {len(excluded)} != {K.D010_EXCLUDED_CLUSTERS}")
    if n_clusters != K.UNIVERSE_CLUSTERS:
        findings.append(f"universe clusters {n_clusters} != {K.UNIVERSE_CLUSTERS}")
    if len(universe_rows) != K.UNIVERSE_ROWS:
        findings.append(f"universe rows {len(universe_rows)} != {K.UNIVERSE_ROWS}")
    if per_season != K.PER_SEASON_CLUSTERS:
        findings.append(f"per-season census {per_season} != {K.PER_SEASON_CLUSTERS}")
    if n_null_pts != 0:
        findings.append(f"{n_null_pts} null score values in the universe")
    if ties != 0:
        findings.append(f"{ties} settled ties -- E3_HOME_WIN_PROB would not be well defined")
    if len(game_ids) != len(set(game_ids)):
        findings.append("duplicate game_id among is_home==1 rows")

    return {"game_ids": game_ids, "n_clusters": n_clusters, "n_rows": int(len(universe_rows)),
            "per_season_clusters": per_season,
            "full_schedule": {"clusters": int(full_clusters), "rows": int(full_rows)},
            "d010": {"excluded_date": K.D010_EXCLUDED_DATE,
                     "excluded_clusters": int(len(excluded)),
                     "first_game_date_in_artifact": first_date, "caveat": K.D010_CAVEAT},
            "settled_ties": ties, "null_score_values": n_null_pts,
            "findings": findings}


def measure_league_average_identity(game_ids: list[str]) -> dict:
    """O2.must_also_report: 'the measured identity with the frozen store's league_average_v1
    game_id set (the interim pin S34 confirmed holds)'."""
    rel = "experiments/market_program/SCORE_BASELINES/score_baseline_rows.parquet"
    path = K.artifact_path(rel)
    got = sha256_file(path)
    if got != K.INPUT_PINS[rel]:
        _halt(f"frozen store byte pin failed: {rel} sha256 {got} != {K.INPUT_PINS[rel]}")
    sb = pd.read_parquet(path)
    la = set(sb.loc[sb["method"] == K.FALLBACK_METHOD, "game_id"].astype(str))
    comp = set(sb.loc[sb["method"] == K.COMPOSITE_METHOD, "game_id"].astype(str))
    u = set(game_ids)
    uncovered = sorted(u - comp)
    uncovered_by_season = {}
    if uncovered:
        idx = sb.drop_duplicates("game_id").set_index(sb.drop_duplicates("game_id")["game_id"]
                                                      .astype(str))["season"]
        for g in uncovered:
            s = int(idx.get(g, -1))
            uncovered_by_season[s] = uncovered_by_season.get(s, 0) + 1
    return {
        "league_average_v1_n": len(la), "universe_n": len(u),
        "identity_holds": la == u,
        "in_universe_not_in_league_average": sorted(u - la),
        "in_league_average_not_in_universe": sorted(la - u),
        "composite_pace_x_eff_v1_n": len(comp),
        "composite_uncovered_clusters": len(uncovered),
        "composite_uncovered_by_season": dict(sorted(uncovered_by_season.items())),
        "composite_uncovered_game_ids": uncovered,
        "expected_uncovered_from_card": K.N_COMPOSITE_UNCOVERED,
        "expected_uncovered_by_season_from_card": K.COMPOSITE_UNCOVERED_BY_SEASON,
    }


def main(write: bool = True) -> dict:
    obligation_text = verify_obligation_text()
    root = verify_root_path_rule()

    mt = pd.read_parquet(K.artifact_path("data/masters/master_team.parquet"))
    uni = rederive_universe(mt)
    if uni["findings"]:
        _halt("universe re-derivation disagrees with the frozen pins: "
              + "; ".join(uni["findings"]) + " -- " + O2_ON_MISMATCH)

    # THE DIGEST. Sorted lexicographically on str(game_id) ascending, U+001F-joined, UTF-8.
    digest = column_digest(uni["game_ids"])

    la = measure_league_average_identity(uni["game_ids"])
    la_findings = []
    if not la["identity_holds"]:
        la_findings.append("league_average_v1 game_id set is NOT identical to the universe")
    if la["composite_uncovered_clusters"] != K.N_COMPOSITE_UNCOVERED:
        la_findings.append(f"composite-uncovered clusters {la['composite_uncovered_clusters']} != "
                           f"carded {K.N_COMPOSITE_UNCOVERED}")
    if la["composite_uncovered_by_season"] != K.COMPOSITE_UNCOVERED_BY_SEASON:
        la_findings.append(f"composite-uncovered by season {la['composite_uncovered_by_season']} "
                           f"!= carded {K.COMPOSITE_UNCOVERED_BY_SEASON}")
    if la_findings:
        _halt("frozen-store identity checks failed: " + "; ".join(la_findings) + " -- "
              + O2_ON_MISMATCH)

    receipt = {
        "schema": "s36_prebuild_game_id_digest/1",
        "node": "S36_IMPLEMENT_ARMS",
        "discharges": "S35 downstream_obligations.O2_S36_GAME_ID_PREBUILD_DIGEST "
                      "(S34 Severity C note C4)",
        "epistemic_status": ("IMPLEMENTATION. Unit/synthetic/identity/schema tests only; no "
                             "comparative historical performance is revealed."),
        "obligation_verbatim": O2_PREBUILD_DIGEST,
        "digest_rule_verbatim": O2_DIGEST_RULE,
        "on_mismatch_verbatim": O2_ON_MISMATCH,
        "emitted_before_any_design_matrix": True,
        "structural_guarantee": ("this script imports only canon (pure hashing), runner_constants "
                                 "(pure pins) and obligations (pure text); it cannot construct a "
                                 "design matrix, and universe.build_universe() refuses to return "
                                 "a frame unless this receipt exists and re-derives"),
        "root_path_rule": root,
        "obligation_text_check": obligation_text,

        "GAME_ID_SET_SHA256": digest,
        "n_clusters": uni["n_clusters"],
        "n_team_game_rows": uni["n_rows"],
        "per_season_census": uni["per_season_clusters"],
        "per_season_census_expected": K.PER_SEASON_CLUSTERS,
        "per_season_census_matches": uni["per_season_clusters"] == K.PER_SEASON_CLUSTERS,
        "full_schedule_reference": uni["full_schedule"],
        "d010": uni["d010"],
        "settled_ties": uni["settled_ties"],
        "null_score_values": uni["null_score_values"],
        "e3_well_defined": uni["settled_ties"] == 0,
        "league_average_v1_identity": la,

        "canonicalisation": CANONICALISATION_STATEMENT,
        "join_key_separator_convention": JOIN_KEY_SEPARATOR_STATEMENT,
        "sort_rule": "lexicographic on str(game_id) ascending",
        "closes_invariants_rows_deferral_on": K.N_ELEMENT_CARDS,
        "invariants_rows_now_receipted": (
            "all 17 element cards carried invariants.rows = 'TO_BE_EMITTED_AT_S36_BUILD'. This "
            "receipt IS that emission: the row digest is byte-identical for arm and K0 by "
            "construction (both sides read the same pinned game_id set) and the S36 build fails "
            "closed on any mismatch."),
        "first_3_game_ids": uni["game_ids"][:3],
        "last_3_game_ids": uni["game_ids"][-3:],
    }
    stamp_program_alpha(receipt)

    if write:
        RECEIPT_PATH.write_text(json.dumps(receipt, indent=1, sort_keys=False) + "\n",
                                encoding="utf-8")
    return receipt


if __name__ == "__main__":
    r = main()
    print("GAME_ID_SET_SHA256 =", r["GAME_ID_SET_SHA256"])
    print("n_clusters         =", r["n_clusters"], "(expected 1491)")
    print("n_team_game_rows   =", r["n_team_game_rows"], "(expected 2982)")
    print("per_season_census  =", r["per_season_census"])
    print("league_average_v1 identity holds =", r["league_average_v1_identity"]["identity_holds"])
    print("settled ties =", r["settled_ties"], " null scores =", r["null_score_values"])
    print("receipt ->", RECEIPT_PATH)
