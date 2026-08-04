#!/usr/bin/env python3
"""build_measurements.py — emit MEASUREMENTS.json. Every number in REPORT.md comes from here.

Nothing in this file asserts a figure. Each entry records the value AND the call that produced it,
so a reader can re-derive it without trusting the prose.

Run:  python build_measurements.py
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import json                                                                   # noqa: E402
import subprocess                                                             # noqa: E402
import tempfile                                                               # noqa: E402
import shutil                                                                 # noqa: E402
from datetime import datetime, timezone                                       # noqa: E402
from pathlib import Path                                                      # noqa: E402

HERE = Path(__file__).resolve().parent
PROGRAM = HERE.parents[1]
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE))

import repro_runner as rr                                                     # noqa: E402

RUN = HERE / "runs" / "universe_census"
MANIFEST = RUN / "MANIFEST.json"


def main() -> int:
    M: dict = {"schema": "i13_measurements/1",
               "generated_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
               "epistemic_status": ("INFRASTRUCTURE. Makes a run rerunnable and checkable. "
                                    "Proves nothing scientific."),
               "measurements": []}

    def rec(claim, value, how):
        M["measurements"].append({"claim": claim, "value": value, "how_measured": how})

    man = json.loads(MANIFEST.read_text(encoding="utf-8"))

    # ---- 1. the recorded run reproduces byte-identically ------------------------------- #
    v1 = rr.verify(MANIFEST, raise_on_divergence=False)
    rec("the real recorded run reproduces byte-identically from its manifest",
        {"verdict": v1["verdict"], "byte_identical": v1["byte_identical"],
         "outputs_matching": v1["outputs_matching"], "outputs_compared": v1["outputs_compared"],
         "blocking_findings": v1["blocking_findings"],
         "context_findings": v1["context_findings"],
         "output_sha256": {k: v["sha256"] for k, v in man["outputs"].items()}},
        "repro_runner.verify(runs/universe_census/MANIFEST.json)")

    # ---- 2. reproduction is stable across repeats, not a one-off ------------------------ #
    v2 = rr.verify(MANIFEST, raise_on_divergence=False)
    rec("a second independent replay returns the same bytes again",
        {"verdict": v2["verdict"],
         "replay_sha256": {k: v["sha256"] for k, v in v2["replay_outputs"].items()},
         "identical_to_first_replay":
             {k: v["sha256"] for k, v in v1["replay_outputs"].items()}
             == {k: v["sha256"] for k, v in v2["replay_outputs"].items()}},
        "repro_runner.verify(...) called twice, replay_outputs compared")

    # ---- 3. the seed binding is load-bearing (negative control) ------------------------- #
    tmp = Path(tempfile.mkdtemp(prefix="i13_seed_"))
    try:
        alt = tmp / "MANIFEST.json"
        m2 = dict(man)
        m2["seeds"] = dict(man["seeds"]) | {"seed": man["seeds"]["seed"] + 1}
        m2["manifest_digest"] = rr.digest_manifest(m2)
        rr.write_json(alt, m2)
        vs = rr.verify(alt, raise_on_divergence=False)
        diverged = sorted(f["subject"] for f in vs["findings"]
                          if f["kind"] == "output_hash_divergence")
        rec("changing ONLY the recorded seed changes the recorded bytes, so the seed binding is "
            "load-bearing rather than decorative",
            {"seed_recorded": man["seeds"]["seed"], "seed_tried": m2["seeds"]["seed"],
             "verdict": vs["verdict"], "outputs_that_diverged": diverged,
             "outputs_that_held": sorted(set(man["outputs"]) - set(diverged))},
            "copy the manifest, increment seeds.seed by 1, re-sign, verify")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # ---- 4. what the manifest actually binds -------------------------------------------- #
    rec("bindings carried by the recorded manifest",
        {"seed": man["seeds"]["seed"], "python_hash_seed": man["seeds"]["python_hash_seed"],
         "commit": man["code"]["commit"], "branch": man["code"]["branch"],
         "inputs_bound": len(man["inputs"]),
         "sources_bound": len(man["code"]["sources"]),
         "sources": sorted(man["code"]["sources"]),
         "sources_declared_by_caller": sorted(
             k for k, v in man["code"]["sources"].items() if v["declared_by_caller"]),
         "sources_discovered_by_measuring_the_import_closure": sorted(
             k for k, v in man["code"]["sources"].items() if not v["declared_by_caller"]),
         "outputs_bound": len(man["outputs"]),
         "manifest_digest": man["manifest_digest"],
         "run_id": man["run_id"]},
        "read runs/universe_census/MANIFEST.json")

    # ---- 5. four-way artifact reconciliation --------------------------------------------- #
    rc = rr.reconcile(MANIFEST)
    rec("four-way reconciliation of every input the run consumed "
        "(manifest / disk / PROGRAM_STATE.json / the artifact's own receipt)",
        {"verdict": rc["verdict"], "n_inputs": rc["n_inputs"],
         "n_disagreements": rc["n_disagreements"],
         "n_registered_canonical": rc["n_registered_canonical"],
         "n_uncorroborated": rc["n_uncorroborated"],
         "rows": [{"path": r["path"], "verdict": r["verdict"],
                   "independent_hashes": r["n_independent_hashes"],
                   "registered_canonical": r["registered_canonical"]} for r in rc["rows"]]},
        "repro_runner.reconcile(runs/universe_census/MANIFEST.json)")

    # ---- 6. PROGRAM_STATE coverage of the artifact the primary target is built from ------ #
    S = json.loads((PROGRAM / "PROGRAM_STATE.json").read_text(encoding="utf-8"))
    text = json.dumps(S)
    poss = PROGRAM / "possessions_v2" / "possessions_raw_v2.parquet"
    poss_receipt = json.loads(
        (PROGRAM / "possessions_v2" / "POSSESSION_INTEGRITY_RECEIPT_V2.json")
        .read_text(encoding="utf-8"))
    rec("PROGRAM_STATE.json publishes a frozen hash for 3 artifact families; the possessions "
        "artifact the primary target is computed from is not among them",
        {"canonical_artifacts_published": sorted(S["canonical_artifacts"]),
         "possessions_raw_v2_mentioned_anywhere_in_PROGRAM_STATE":
             "possessions_raw_v2" in text,
         "possessions_v2_has_its_own_receipt_on_disk": True,
         "receipt_recorded_sha256": poss_receipt["integrity"]["artifact_sha256"],
         "on_disk_sha256": rr.sha256_file(poss),
         "receipt_matches_disk":
             poss_receipt["integrity"]["artifact_sha256"] == rr.sha256_file(poss),
         "sibling_artifact_with_no_hash_in_that_receipt":
             "possessions_v2/player_season_possessions_v2.parquet",
         "sibling_on_disk_sha256": rr.sha256_file(
             PROGRAM / "possessions_v2" / "player_season_possessions_v2.parquet")},
        "read PROGRAM_STATE.json and POSSESSION_INTEGRITY_RECEIPT_V2.json; sha256 both parquets")

    # ---- 7. PROGRAM_STATE shared-contract hashes vs disk --------------------------------- #
    sc = {}
    for name, v in (S.get("shared_contracts") or {}).items():
        p = ROOT / v["path"]
        sc[name] = {"published": v["sha256"], "on_disk": rr.sha256_file(p) if p.exists() else None}
        sc[name]["agree"] = sc[name]["published"] == sc[name]["on_disk"]
    rec("PROGRAM_STATE.json's published shared-contract hashes still match the bytes on disk",
        {"all_agree": all(v["agree"] for v in sc.values()), "detail": sc},
        "sha256 each path in PROGRAM_STATE.shared_contracts")

    # ---- 8. PROGRAM_STATE provenance commit vs live HEAD --------------------------------- #
    live = rr.git_context(ROOT)
    gf = S["generated_from"]
    rec("PROGRAM_STATE.generated_from records the commit it was generated at, not live state; "
        "the runner therefore reads the commit from git, never from PROGRAM_STATE",
        {"program_state_generated_from_head": gf["head"],
         "program_state_generated_from_working_tree_state": gf["working_tree_state"],
         "live_head": live.get("commit"), "live_branch": live.get("branch"),
         "same": gf["head"] == live.get("commit"),
         "program_state_says_so_itself": S["authority"][:120] + "..."},
        "git rev-parse HEAD (read-only) vs PROGRAM_STATE.generated_from.head")

    # ---- 9. the census the run produced --------------------------------------------------- #
    census = json.loads((RUN / "outputs" / "universe_census.json").read_text(encoding="utf-8"))
    rec("the recorded run's census of the team-game universe",
        {"team_game_rows": census["team_game_rows"], "game_clusters": census["game_clusters"],
         "cluster_size_distribution": census["cluster_size_distribution"],
         "row_universe_digest": census["row_universe_digest"],
         "universe_contract_id": census["universe_contract_id"],
         "target_column": census["target_column"],
         "target_summary": census["target_summary"],
         "seasons": census["seasons"]},
        "runs/universe_census/outputs/universe_census.json, produced by "
        "payload_universe_census.py via possession_features.load_universe() (read-only)")

    # ---- 10. how seeds were bound in this program BEFORE this node --------------------------- #
    import re
    rng_pat = re.compile(r"default_rng\s*\(|np\.random\.seed\s*\(|random\.seed\s*\(")
    seeded_files, mine = [], str(HERE)
    for p in sorted(PROGRAM.rglob("*.py")):
        if str(p).startswith(mine) or "stage2b/SEALED_RESULTS" in p.as_posix():
            continue
        try:
            if rng_pat.search(p.read_text(encoding="utf-8", errors="ignore")):
                seeded_files.append(p.relative_to(ROOT).as_posix())
        except OSError:
            continue
    manifests = {}
    for p in sorted(PROGRAM.rglob("MANIFEST.json")):
        if str(p).startswith(mine):
            continue
        try:
            t = p.read_text(encoding="utf-8", errors="ignore").lower()
        except OSError:
            continue
        manifests[p.relative_to(ROOT).as_posix()] = {
            "mentions_seed": "seed" in t, "mentions_commit": "commit" in t,
            "mentions_sha256": "sha256" in t}
    rec("seeds in this program are literals inside source files; what else on disk binds a seed "
        "alongside a commit and hashes",
        {"program_py_files_that_construct_an_RNG": len(seeded_files),
         "examples": seeded_files[:8],
         "other_files_named_MANIFEST.json": manifests,
         "snapshot_caveat": "sibling lane nodes were writing concurrently during this wave; this "
                            "is a snapshot at generated_utc, taken with the command below. It is "
                            "a keyword scan, NOT a claim about what those manifests verify."},
        "regex scan of experiments/player_program/**/*.py for default_rng( | np.random.seed( | "
        "random.seed(, excluding this node and stage2b/SEALED_RESULTS")

    # ---- 11. the test suite ---------------------------------------------------------------- #
    r = subprocess.run([sys.executable, str(HERE / "TESTS.py")], capture_output=True, text=True,
                       cwd=str(ROOT), timeout=1800)
    passes = r.stdout.count("  PASS  ")
    fails = r.stdout.count("  FAIL  ")
    skips = r.stdout.count("  SKIP  ")
    rec("the node's own test suite", {"exit_code": r.returncode, "checks_passed": passes,
                                      "checks_failed": fails, "checks_skipped": skips},
        "python TESTS.py, counting PASS/FAIL/SKIP lines")

    rr.write_json(HERE / "MEASUREMENTS.json", M)
    print(json.dumps({m["claim"][:70]: m["value"] if not isinstance(m["value"], dict)
                      else list(m["value"])[:4] for m in M["measurements"]}, indent=2))
    print(f"\nwrote {HERE / 'MEASUREMENTS.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
