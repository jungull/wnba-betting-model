"""Exercise sealed_package.py end to end against the REAL program artifacts and record what it
measured. Writes `demo_seal/` and `MEASUREMENTS.json`, both inside this node's directory.

    python demo_seal.py

The payloads sealed here are SYNTHETIC. This node has no results, produces none, and reads none.
What is real is everything the manifest BINDS: the commit, the input hashes, the 2,982-row /
1,491-cluster universe read out of the frozen exposure artifact, the season fold structure, and
the K0_MATCHED record digests taken from P26's example specifications.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PROGRAM = HERE.parents[1]           # experiments/player_program
REPO = PROGRAM.parents[1]           # worktree root
sys.path.insert(0, str(HERE))

import sealed_package as sp                       # noqa: E402
from surface_probe import probe_surfaces          # noqa: E402

DEMO = HERE / "demo_seal"
UNIVERSE_ARTIFACT = PROGRAM / "projected_exposure_v1" / "team_possession_prior_v1.parquet"
K0_EXAMPLES = PROGRAM / "stage2b" / "P26_ARM_SPECIFIC_K0_CONTRACT" / "K0_MATCHED_EXAMPLES.json"

DECLARED_INPUTS = [
    "stage2a/EVIDENCE_PACKET_V2.json",
    "stage2a/V2_STOP_CONDITION.json",
    "PROGRAM_STATE.json",
    "RESEARCH_CONTRACT_V1.md",
    "GATE_INVOCATION_CONTRACT.md",
    "projected_exposure_v1/team_possession_prior_v1.parquet",
]

MARKER = b"I11_SYNTHETIC_PAYLOAD_MARKER_NOT_A_RESULT"


def main() -> int:
    M: dict = {"schema": "i11_measurements/1",
               "node": "I11_BLINDED_RESULT_PACKAGING",
               "epistemic_status": "INFRASTRUCTURE. Enforces the seal mechanically rather than "
                                   "by convention.",
               "payloads_are": "SYNTHETIC. This node holds no experimental results.",
               "environment": {"python": sys.version.split()[0], "pandas": pd.__version__,
                               "numpy": np.__version__},
               "row_digest_source": sp.ROW_DIGEST_SOURCE}

    # -- code commit ---------------------------------------------------------------------------
    commit = sp.read_code_commit(REPO)
    M["code_commit"] = {k: v for k, v in commit.items() if k != "dirty_paths"}
    M["code_commit"]["n_dirty_paths"] = len(commit["dirty_paths"])

    # -- data hashes ---------------------------------------------------------------------------
    data_hashes = sp.hash_inputs(DECLARED_INPUTS, root=PROGRAM)
    M["data_hashes"] = data_hashes

    # -- row universe, measured out of the frozen artifact -------------------------------------
    df = pd.read_parquet(UNIVERSE_ARTIFACT)
    resolved = df[df["pace_resolved"] == True].copy()          # noqa: E712
    rows = [f"{g}|{t}" for g, t in zip(resolved["game_id"], resolved["team_id"])]
    clusters = [str(g) for g in resolved["game_id"]]
    universe = sp.describe_universe(rows, clusters,
                                    row_key_columns=["game_id", "team_id"],
                                    cluster_key_column="game_id")
    per_cluster = resolved.groupby("game_id").size().value_counts().to_dict()
    M["row_universe"] = {
        "artifact": str(UNIVERSE_ARTIFACT.relative_to(REPO)).replace("\\", "/"),
        "selector": "pace_resolved == True",
        "rows_in_artifact": int(len(df)),
        "rows_excluded_unresolved": int((~df["pace_resolved"]).sum()),
        "n_rows": universe["n_rows"],
        "n_clusters": universe["n_clusters"],
        "rows_per_cluster_histogram": {str(k): int(v) for k, v in per_cluster.items()},
        "row_digest": universe["row_digest"],
        "cluster_digest": universe["cluster_digest"],
        "packet_claim": {"team_game_rows": 2982, "game_clusters": 1491},
        "matches_packet_claim": universe["n_rows"] == 2982 and universe["n_clusters"] == 1491,
    }

    # -- folds: season blocks. a cluster must never straddle a fold ----------------------------
    seasons = [str(s) for s in resolved["season"]]
    folds = sp.describe_folds(scheme="SEASON_BLOCK", cluster_keys=clusters, fold_keys=seasons)
    M["folds"] = {"scheme": folds["scheme"], "n_folds": folds["n_folds"],
                  "cluster_split_check": folds["cluster_split_check"],
                  "assignment_digest": folds["assignment_digest"],
                  "folds": [{k: f[k] for k in ("fold", "n_rows", "n_clusters")}
                            for f in folds["folds"]]}

    # negative control: a row-level random k-fold, which is what "5-fold CV" naively means
    rng = np.random.default_rng(20260804)
    random_folds = [f"rf{i}" for i in rng.integers(0, 5, size=len(clusters))]
    split_ct = sum(1 for _, fs in
                   pd.DataFrame({"c": clusters, "f": random_folds}).groupby("c")["f"].nunique()
                   .items() if fs > 1)
    try:
        sp.describe_folds(scheme="ROW_LEVEL_RANDOM_5", cluster_keys=clusters,
                          fold_keys=random_folds)
        refused = False
        err = None
    except sp.ManifestError as e:
        refused, err = True, str(e).split(";")[0]
    M["negative_control_row_level_random_5fold"] = {
        "seed": 20260804, "clusters_split_across_folds": int(split_ct),
        "refused_by_describe_folds": refused, "message": err}

    # -- K0 pairing, digesting the REAL P26 example specifications ------------------------------
    k0_records = json.loads(K0_EXAMPLES.read_text(encoding="utf-8"))
    entries = {arm_id: {"k0_matched_id": f"K0_MATCHED__{arm_id}",
                        "k0_matched_record": rec,
                        "arm_kind": rec.get("arm_kind")}
               for arm_id, rec in k0_records.items()}
    k0 = sp.describe_k0_pairing(entries, k0_flat_id="K0_FLAT")
    M["k0_pairing"] = {"source": str(K0_EXAMPLES.relative_to(REPO)).replace("\\", "/"),
                       "source_sha256": sp.sha256_file(K0_EXAMPLES),
                       "n_arms": k0["n_arms"], "authoritative_control": k0["authoritative_control"],
                       "k0_flat_role": k0["k0_flat_role"], "arms": k0["arms"]}

    seeds = {"fold_seed": 20260804, "bootstrap_seed": 902144, "init_seed": 7}
    M["seeds"] = seeds

    # -- build the manifest ---------------------------------------------------------------------
    manifest = sp.build_manifest(
        run_id="I11_DEMONSTRATION_SEAL_v1",
        target="REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS",
        code_commit=commit, data_hashes=data_hashes, row_universe=universe,
        folds=folds, k0_pairing=k0, seeds=seeds,
        extra={"note": "DEMONSTRATION ONLY. Synthetic payloads. Not an experiment."})
    M["manifest"] = {"run_id": manifest["run_id"], "target": manifest["target"],
                     "digest_covers": manifest["digest_covers"],
                     "manifest_digest": manifest["manifest_digest"],
                     "bindings_present": sorted(manifest["bindings"])}

    # determinism: rebuild and compare
    manifest2 = sp.build_manifest(
        run_id="I11_DEMONSTRATION_SEAL_v1",
        target="REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS",
        code_commit=commit, data_hashes=data_hashes, row_universe=universe,
        folds=folds, k0_pairing=k0, seeds=seeds,
        extra={"note": "DEMONSTRATION ONLY. Synthetic payloads. Not an experiment."})
    M["manifest"]["digest_stable_across_rebuild"] = (
        manifest2["manifest_digest"] == manifest["manifest_digest"])

    # -- seal ------------------------------------------------------------------------------------
    if DEMO.exists():
        shutil.rmtree(DEMO)
    payload_a = MARKER + b"\n" + b"synthetic fold table, no result content\n" * 64
    payload_b = {"schema": "synthetic/1", "marker": MARKER.decode(),
                 "folds": [f["fold"] for f in folds["folds"]]}
    with sp.SealedWriter(DEMO, manifest, actor="I11 demonstration",
                         node_id="I11_BLINDED_RESULT_PACKAGING") as w:
        w.write_payload("synthetic_predictions.bin", payload_a)
        w.write_json_payload("synthetic_fold_table.json", payload_b)
        # the seal is armed: prove the writer cannot read what it just wrote
        stored = DEMO / sp.PAYLOAD_DIR / "synthetic_predictions.bin.sealed"
        scratch = HERE / "_probe_scratch"
        scratch.mkdir(exist_ok=True)
        surfaces = probe_surfaces(stored, DEMO / sp.PAYLOAD_DIR, scratch, MARKER)
        summary = w.finalize()
    shutil.rmtree(HERE / "_probe_scratch", ignore_errors=True)

    M["read_surface_probe"] = {k: v for k, v in surfaces.items()}
    M["read_surface_probe_totals"] = {
        "trapped": sum(1 for v in surfaces.values() if v["outcome"] == "TRAPPED"),
        "not_trapped_no_plaintext": sum(1 for v in surfaces.values()
                                        if v["outcome"] == "NOT_TRAPPED_NO_PLAINTEXT"),
        "leaked": sum(1 for v in surfaces.values() if v["outcome"] == "LEAKED"),
        "n_surfaces": len(surfaces)}
    M["seal"] = {"root": str(DEMO.relative_to(REPO)).replace("\\", "/"), **summary}

    # at-rest evidence
    on_disk = (DEMO / sp.PAYLOAD_DIR / "synthetic_predictions.bin.sealed").read_bytes()
    M["at_rest"] = {
        "plaintext_bytes": len(payload_a),
        "stored_bytes": len(on_disk),
        "marker_present_in_stored_bytes": MARKER in on_disk,
        "longest_common_8byte_run_with_plaintext": sum(
            1 for i in range(len(payload_a) - 8) if payload_a[i:i + 8] in on_disk),
        "note": "OBFUSCATION, NOT CONFIDENTIALITY -- the keystream is derived from public "
                "material. It removes accidental disclosure, not deliberate disclosure."}

    # -- verify (no disclosure), then open (logged), then verify again ---------------------------
    v_before = sp.verify_seal(DEMO)
    M["verify_before_open"] = {"ok": v_before["ok"], "failures": v_before["failures"],
                               "bindings_present": v_before["bindings_present"],
                               "n_opens": v_before["open_log"]["n_opens"],
                               "discloses_payload_content":
                                   v_before["discloses_payload_content"],
                               "payloads": v_before["payloads"]}
    M["verify_result_contains_marker"] = MARKER.decode() in json.dumps(v_before)

    opened = sp.open_seal(DEMO, actor="I11 demonstration",
                          reason="demonstrate that opening is separate and logged",
                          authorization_ref="graph node I11_BLINDED_RESULT_PACKAGING",
                          node_id="I11_BLINDED_RESULT_PACKAGING")
    got = opened.payload("synthetic_predictions.bin")
    M["open"] = {"round_trip_byte_identical": got == payload_a,
                 "log_entry": opened.log_entry,
                 "status_after": sp.seal_status(DEMO)["state"]}
    v_after = sp.verify_seal(DEMO)
    M["verify_after_open"] = {"ok": v_after["ok"], "n_opens": v_after["open_log"]["n_opens"],
                              "chain_ok": v_after["open_log"]["chain_ok"]}

    (HERE / "MEASUREMENTS.json").write_text(
        json.dumps(M, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    print(json.dumps({k: M[k] for k in ("row_universe", "read_surface_probe_totals", "seal",
                                        "verify_after_open")}, indent=2)[:2000])
    print("\nwrote", HERE / "MEASUREMENTS.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
