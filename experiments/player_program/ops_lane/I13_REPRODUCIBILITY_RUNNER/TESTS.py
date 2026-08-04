#!/usr/bin/env python3
"""I13_REPRODUCIBILITY_RUNNER — tests.

Repo convention: standalone runnable script, ``main()`` returns 1 on failure. pytest is not
installed and is not used.

T1-T10 are SYNTHETIC and hermetic: they build a throwaway tree under the OS temp directory, record
a manifest against it, then perturb exactly one binding and assert the runner fails in the named
way. They are the contract of the runner. They touch no program artifact.

T11-T13 replay the REAL recorded run in ``runs/universe_census/``. If the frozen artifacts it
consumes are not present, those tests report SKIP and do not fail the suite.

Nothing here writes outside this node's directory or the OS temp directory. No git command is run
by the tests other than the read-only ones inside ``repro_runner``.

Run:  python TESTS.py
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import json                                                                   # noqa: E402
import shutil                                                                 # noqa: E402
import tempfile                                                               # noqa: E402
from pathlib import Path                                                      # noqa: E402

HERE = Path(__file__).resolve().parent
PROGRAM = HERE.parents[1]
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE))

import repro_runner as rr                                                     # noqa: E402

FAILURES: list[str] = []
SKIPS: list[str] = []


def check(cond, label, detail=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + (f"  [{detail}]" if detail else ""))
    if not cond:
        FAILURES.append(label)


def skip(label, why):
    print(f"  SKIP  {label}  [{why}]")
    SKIPS.append(label)


def kinds(report) -> set[str]:
    return {f["kind"] for f in report["findings"]}


# --------------------------------------------------------------------------------------------
# synthetic scaffolding
# --------------------------------------------------------------------------------------------
DETERMINISTIC_PAYLOAD = '''\
import sys, os, json, hashlib, random
sys.dont_write_bytecode = True
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import helper_lib

out = Path(sys.argv[sys.argv.index("--out") + 1]); out.mkdir(parents=True, exist_ok=True)
seed = int(os.environ["REPRO_SEED"])
random.seed(seed)
data = Path(__file__).resolve().parent.joinpath("input_data.txt").read_text(encoding="utf-8")
draws = [random.randint(0, 10 ** 9) for _ in range(50)]
body = {"seed": seed, "input_sha256": hashlib.sha256(data.encode()).hexdigest(),
        "draws": draws, "helper": helper_lib.CONSTANT}
with (out / "result.json").open("w", encoding="utf-8", newline="\\n") as fh:
    fh.write(json.dumps(body, sort_keys=True, indent=2) + "\\n")
'''

NONDETERMINISTIC_PAYLOAD = '''\
import sys, os, time, uuid
sys.dont_write_bytecode = True
from pathlib import Path
out = Path(sys.argv[sys.argv.index("--out") + 1]); out.mkdir(parents=True, exist_ok=True)
(out / "result.json").write_text('{"nonce": "%s"}\\n' % uuid.uuid4(), encoding="utf-8")
'''

FAILING_PAYLOAD = '''\
import sys
sys.dont_write_bytecode = True
sys.stderr.write("deliberate failure\\n")
sys.exit(3)
'''

MUTATING_PAYLOAD = '''\
import sys, os
sys.dont_write_bytecode = True
from pathlib import Path
here = Path(__file__).resolve().parent
out = Path(sys.argv[sys.argv.index("--out") + 1]); out.mkdir(parents=True, exist_ok=True)
p = here / "input_data.txt"
p.write_text(p.read_text(encoding="utf-8") + "x", encoding="utf-8")
(out / "result.json").write_text("{}\\n", encoding="utf-8")
'''

HELPER = 'CONSTANT = "v1"\n'


def build_tree(tmp: Path, payload_src: str = DETERMINISTIC_PAYLOAD) -> dict:
    tmp.mkdir(parents=True, exist_ok=True)
    (tmp / "payload.py").write_text(payload_src, encoding="utf-8", newline="\n")
    (tmp / "helper_lib.py").write_text(HELPER, encoding="utf-8", newline="\n")
    (tmp / "input_data.txt").write_text("the bytes this run consumed\n", encoding="utf-8",
                                        newline="\n")
    return {"payload": tmp / "payload.py", "inputs": {"data": tmp / "input_data.txt"}}


def record_synthetic(tmp: Path, *, seed: int = 12345, payload_src: str = DETERMINISTIC_PAYLOAD,
                     declared_sources=None) -> dict:
    t = build_tree(tmp, payload_src)
    return rr.record(tmp / "run", payload=t["payload"], argv_tail=["--out", "{OUT}"],
                     inputs=t["inputs"], seed=seed, python_hash_seed=0, root=tmp, program=tmp,
                     declared_sources=declared_sources or [t["payload"]],
                     description="synthetic", timeout=180)


def resign(manifest_path: Path) -> None:
    """Re-sign a manifest after an intentional edit, so a test can isolate ONE divergence
    instead of tripping manifest_tampered on every case."""
    m = json.loads(manifest_path.read_text(encoding="utf-8"))
    m["manifest_digest"] = rr.digest_manifest(m)
    rr.write_json(manifest_path, m)


def edit_manifest(manifest_path: Path, fn, *, sign: bool = True) -> None:
    m = json.loads(manifest_path.read_text(encoding="utf-8"))
    fn(m)
    if sign:
        m["manifest_digest"] = rr.digest_manifest(m)
    rr.write_json(manifest_path, m)


def vfy(tmp: Path, **kw) -> dict:
    return rr.verify(tmp / "run" / "MANIFEST.json", root=tmp, raise_on_divergence=False, **kw)


# --------------------------------------------------------------------------------------------
# T1  a recorded run reproduces byte-identically from its manifest
# --------------------------------------------------------------------------------------------
def t1_byte_identical(tmp: Path):
    print("T1  a recorded run reproduces byte-identically from its manifest")
    m = record_synthetic(tmp)
    r = vfy(tmp)
    check(r["verdict"] == "PASS", "verdict is PASS", r["verdict"])
    check(r["byte_identical"] is True, "byte_identical is True")
    check(r["outputs_matching"] == r["outputs_compared"] == 1,
          "every recorded output came back byte-identical",
          f"{r['outputs_matching']}/{r['outputs_compared']}")
    check(not r["findings"], "no findings at all", str(kinds(r)))
    check(rr.digest_manifest(m) == m["manifest_digest"], "the manifest is self-consistent")
    return m


# --------------------------------------------------------------------------------------------
# T2  seeds are bound -- and the binding is load-bearing
# --------------------------------------------------------------------------------------------
def t2_seed_is_load_bearing(tmp: Path):
    print("T2  the seed is bound, and changing it in the manifest is caught as a divergence")
    m = record_synthetic(tmp, seed=12345)
    check(isinstance(m["seeds"]["seed"], int) and isinstance(m["seeds"]["python_hash_seed"], int),
          "the manifest binds an integer seed and an integer PYTHONHASHSEED",
          f"seed={m['seeds']['seed']} hashseed={m['seeds']['python_hash_seed']}")
    edit_manifest(tmp / "run" / "MANIFEST.json", lambda d: d["seeds"].__setitem__("seed", 999))
    r = vfy(tmp)
    check(r["verdict"] == "FAIL", "a different seed FAILS verification", r["verdict"])
    check("output_hash_divergence" in kinds(r),
          "and it fails as output_hash_divergence -- the seed really drove the bytes",
          str(sorted(kinds(r))))
    check(r["byte_identical"] is False, "byte_identical is False")


def t2b_seed_binding_absent(tmp: Path):
    print("T2b unseeded manifests are rejected rather than run anyway")
    record_synthetic(tmp)
    edit_manifest(tmp / "run" / "MANIFEST.json", lambda d: d["seeds"].pop("seed", None))
    r = vfy(tmp)
    check("seed_binding_absent" in kinds(r), "seed_binding_absent is raised", str(sorted(kinds(r))))
    check(r["verdict"] == "FAIL", "and the verdict is FAIL", r["verdict"])


# --------------------------------------------------------------------------------------------
# T3  input hashes are bound
# --------------------------------------------------------------------------------------------
def t3_input_hash_bound(tmp: Path):
    print("T3  input hashes are bound; a changed input FAILS even before the bytes are compared")
    m = record_synthetic(tmp)
    check(all(len(v["sha256"]) == 64 for v in m["inputs"].values()),
          "every declared input carries a sha256", str(list(m["inputs"])))
    (tmp / "input_data.txt").write_text("different bytes\n", encoding="utf-8", newline="\n")
    r = vfy(tmp)
    check("input_hash_divergence" in kinds(r), "input_hash_divergence is raised",
          str(sorted(kinds(r))))
    check(r["verdict"] == "FAIL", "verdict is FAIL", r["verdict"])


def t3b_input_missing(tmp: Path):
    print("T3b a vanished input is a failure, not a skipped check")
    record_synthetic(tmp)
    (tmp / "input_data.txt").unlink()
    r = vfy(tmp)
    check("input_missing" in kinds(r), "input_missing is raised", str(sorted(kinds(r))))
    check(r["verdict"] == "FAIL", "verdict is FAIL", r["verdict"])


def t3c_input_mutated_by_run(tmp: Path):
    print("T3c a run that writes to its own declared input is refused at record time")
    raised = None
    try:
        record_synthetic(tmp, payload_src=MUTATING_PAYLOAD)
    except rr.ReproRunnerError as exc:
        raised = str(exc)
    check(raised is not None and "mutated its own declared inputs" in raised,
          "record() refuses to write a manifest for a run that mutated an input",
          (raised or "no exception")[:80])


# --------------------------------------------------------------------------------------------
# T4  the code commit is bound, and source CONTENT outranks it
# --------------------------------------------------------------------------------------------
def t4_source_content_outranks_commit(tmp: Path):
    print("T4  bound source code: a content change FAILS; a commit-only move is REPORTED")
    m = record_synthetic(tmp)
    check("code" in m and "commit" in m["code"], "the manifest has a commit field at all")
    check(len(m["code"]["sources"]) >= 1, "at least one source is bound",
          str(sorted(m["code"]["sources"])))
    (tmp / "helper_lib.py").write_text('CONSTANT = "v2"\n', encoding="utf-8", newline="\n")
    r = vfy(tmp)
    check("source_hash_divergence" in kinds(r),
          "changing an imported source raises source_hash_divergence", str(sorted(kinds(r))))
    check(r["verdict"] == "FAIL", "verdict is FAIL", r["verdict"])


def t4b_commit_moved_is_reported_not_silent(tmp: Path):
    print("T4b a commit that moved while every source byte held is reported, never silent")
    record_synthetic(tmp)
    mp = tmp / "run" / "MANIFEST.json"
    edit_manifest(mp, lambda d: d["code"].__setitem__("commit", "0" * 40))
    # the synthetic tree is not a git repository, so force the comparison by supplying a live
    # commit the way git_context would.
    real_git = rr.git_context

    def fake_git(root, paths=None):
        ctx = {"git_available": True, "commit": "1" * 40, "commit_utc": None, "branch": "synthetic"}
        for rel in paths or []:
            ctx.setdefault("paths", {})[rel] = {"tracked": True, "dirty": False}
        return ctx

    rr.git_context = fake_git
    try:
        r = vfy(tmp)
    finally:
        rr.git_context = real_git
    check("code_commit_moved" in kinds(r), "code_commit_moved is reported",
          str(sorted(kinds(r))))
    check(r["verdict"] == "PASS_WITH_CONTEXT_FINDINGS",
          "the verdict is NOT a bare PASS while a context finding is present", r["verdict"])
    check(r["blocking_findings"] == 0, "and it is not blocking on its own")
    check(rr.SEVERITY["code_commit_moved"] == "C_CONTEXT",
          "code_commit_moved is declared class C")


# --------------------------------------------------------------------------------------------
# T5  a nondeterministic payload is caught, not rubber-stamped
# --------------------------------------------------------------------------------------------
def t5_nondeterminism_is_caught(tmp: Path):
    print("T5  a genuinely nondeterministic payload FAILS verification")
    record_synthetic(tmp, payload_src=NONDETERMINISTIC_PAYLOAD)
    r = vfy(tmp)
    check("output_hash_divergence" in kinds(r),
          "output_hash_divergence is raised on a payload that embeds a fresh uuid each run",
          str(sorted(kinds(r))))
    check(r["verdict"] == "FAIL", "verdict is FAIL", r["verdict"])
    check(r["byte_identical"] is False, "byte_identical is False")


# --------------------------------------------------------------------------------------------
# T6  a failing command never becomes a recorded run
# --------------------------------------------------------------------------------------------
def t6_failing_command(tmp: Path):
    print("T6  a command that exits non-zero is never recorded as a reproducible run")
    raised = None
    try:
        record_synthetic(tmp, payload_src=FAILING_PAYLOAD)
    except rr.ReproRunnerError as exc:
        raised = str(exc)
    check(raised is not None and "exited 3" in raised,
          "record() refuses to write a manifest for a failed command",
          (raised or "no exception")[:80])
    check(not (tmp / "run" / "MANIFEST.json").exists(), "and no manifest was written")


# --------------------------------------------------------------------------------------------
# T7  the manifest is signed; editing it is detected
# --------------------------------------------------------------------------------------------
def t7_manifest_tampering(tmp: Path):
    print("T7  the manifest is signed by digest; an unsigned edit is detected")
    record_synthetic(tmp)
    mp = tmp / "run" / "MANIFEST.json"
    edit_manifest(mp, lambda d: d["outputs"]["result.json"].__setitem__("sha256", "0" * 64),
                  sign=False)
    r = vfy(tmp)
    check("manifest_tampered" in kinds(r), "manifest_tampered is raised", str(sorted(kinds(r))))
    check(r["verdict"] == "FAIL", "verdict is FAIL", r["verdict"])
    edit_manifest(mp, lambda d: d.pop("manifest_digest", None), sign=False)
    r2 = vfy(tmp)
    check("manifest_unsigned" in kinds(r2), "a manifest with no digest at all is also caught",
          str(sorted(kinds(r2))))


# --------------------------------------------------------------------------------------------
# T8  provenance is observed, not narrated
# --------------------------------------------------------------------------------------------
def t8_closure_is_observed(tmp: Path):
    print("T8  the import closure is measured, not declared: an unbound import FAILS")
    m = record_synthetic(tmp)
    check("helper_lib.py" in " ".join(m["code"]["sources"]),
          "record() discovered helper_lib.py, which the caller never declared",
          str(sorted(m["code"]["sources"])))
    check(m["code"]["sources"][[k for k in m["code"]["sources"]
                                if k.endswith("helper_lib.py")][0]]["declared_by_caller"] is False,
          "and marked it as NOT declared by the caller")
    mp = tmp / "run" / "MANIFEST.json"
    edit_manifest(mp, lambda d: [d["code"]["sources"].pop(k) for k in
                                 [x for x in d["code"]["sources"] if x.endswith("helper_lib.py")]])
    r = vfy(tmp)
    check("unbound_imported_source" in kinds(r),
          "dropping it from the manifest raises unbound_imported_source", str(sorted(kinds(r))))
    check(r["verdict"] == "FAIL", "verdict is FAIL", r["verdict"])


# --------------------------------------------------------------------------------------------
# T9  outputs: missing and extra are both failures
# --------------------------------------------------------------------------------------------
def t9_output_set(tmp: Path):
    print("T9  the output SET is bound, not just the hashes of the ones we remembered")
    record_synthetic(tmp)
    mp = tmp / "run" / "MANIFEST.json"
    edit_manifest(mp, lambda d: d["outputs"].__setitem__(
        "never_written.txt", {"sha256": "0" * 64, "bytes": 0}))
    r = vfy(tmp)
    check("output_missing" in kinds(r), "a recorded output that does not come back is a failure",
          str(sorted(kinds(r))))
    edit_manifest(mp, lambda d: (d["outputs"].pop("never_written.txt"),
                                 d["outputs"].pop("result.json")))
    r2 = vfy(tmp)
    check("output_extra" in kinds(r2),
          "a produced file the manifest does not record is also a failure",
          str(sorted(kinds(r2))))
    check(r2["verdict"] == "FAIL", "verdict is FAIL", r2["verdict"])


# --------------------------------------------------------------------------------------------
# T10  a divergence is never silently accepted
# --------------------------------------------------------------------------------------------
def t10_never_silent(tmp: Path):
    print("T10 no divergence is silently accepted, on any code path")
    check(rr.BLOCKING == (rr.CLASS_A_REPRODUCTION | rr.CLASS_B_BINDING),
          "BLOCKING is exactly class A plus class B")
    check(not (rr.BLOCKING & rr.CLASS_C_CONTEXT), "class C is disjoint from BLOCKING")
    check(set(rr.SEVERITY) == rr.ALL_KINDS, "every declared kind carries a severity")
    check(all(k in rr.ALL_KINDS for k in rr.SEVERITY), "no severity names an undeclared kind")

    record_synthetic(tmp)
    (tmp / "input_data.txt").write_text("changed\n", encoding="utf-8", newline="\n")
    raised = None
    try:
        rr.verify(tmp / "run" / "MANIFEST.json", root=tmp)      # default: raise
    except rr.ReproDivergence as exc:
        raised = exc
    check(raised is not None, "verify() RAISES by default on a blocking divergence")
    check(raised is not None and raised.report["verdict"] == "FAIL",
          "and the report it carries says FAIL")

    rc = rr.main(["verify", str(tmp / "run" / "MANIFEST.json")])
    check(rc == 1, "the CLI exits 1 on a blocking divergence", f"exit={rc}")

    # the undecidable-looking case: outputs match, but a binding moved. Still a failure.
    unknown = None
    try:
        rr.verify.__globals__          # touch nothing; assert the kind vocabulary is closed
        r = vfy(tmp)
        unknown = [f["kind"] for f in r["findings"] if f["kind"] not in rr.ALL_KINDS]
    except Exception as exc:                                             # noqa: BLE001
        unknown = [repr(exc)]
    check(unknown == [], "no finding escapes the declared vocabulary", str(unknown))


# --------------------------------------------------------------------------------------------
# T11-T13  the REAL recorded run
# --------------------------------------------------------------------------------------------
REAL = HERE / "runs" / "universe_census" / "MANIFEST.json"


def t11_real_run_reproduces():
    print("T11 the REAL recorded run reproduces byte-identically")
    if not REAL.exists():
        skip("T11", "runs/universe_census/MANIFEST.json is not present")
        return
    m = json.loads(REAL.read_text(encoding="utf-8"))
    missing = [v["path"] for v in m["inputs"].values() if not (ROOT / v["path"]).exists()]
    if missing:
        skip("T11", f"frozen inputs absent: {missing[:2]}")
        return
    r = rr.verify(REAL, raise_on_divergence=False)
    check(r["byte_identical"] is True,
          "every recorded output of the real run came back byte-identical",
          f"{r['outputs_matching']}/{r['outputs_compared']}")
    check(r["verdict"] in ("PASS", "PASS_WITH_CONTEXT_FINDINGS"),
          "verdict is PASS or PASS_WITH_CONTEXT_FINDINGS", r["verdict"])
    check(r["blocking_findings"] == 0, "no blocking findings",
          str(sorted(k for k in kinds(r) if k in rr.BLOCKING)))
    for f in r["findings"]:
        print(f"  INFO  context finding: {f['kind']} :: {f['subject']}")
    print(f"  INFO  real run verified at commit {r['verified_at_commit']}")


def t12_real_run_bindings():
    print("T12 the real run binds seeds, a commit and input hashes")
    if not REAL.exists():
        skip("T12", "manifest not present")
        return
    m = json.loads(REAL.read_text(encoding="utf-8"))
    check(isinstance(m["seeds"]["seed"], int), "seed is bound", str(m["seeds"]["seed"]))
    check(isinstance(m["seeds"]["python_hash_seed"], int), "PYTHONHASHSEED is bound")
    check(bool(m["code"]["commit"]) and len(m["code"]["commit"]) == 40,
          "a 40-char commit is bound", str(m["code"]["commit"])[:12])
    check(len(m["inputs"]) >= 2 and all(len(v["sha256"]) == 64 for v in m["inputs"].values()),
          "every input carries a sha256", f"{len(m['inputs'])} inputs")
    check(len(m["code"]["sources"]) >= 2,
          "the measured import closure bound more than the payload alone",
          str(len(m["code"]["sources"])))
    check(rr.digest_manifest(m) == m["manifest_digest"], "the manifest digest is intact")
    census = HERE / "runs" / "universe_census" / "outputs" / "universe_census.json"
    if census.exists():
        c = json.loads(census.read_text(encoding="utf-8"))
        check(c["team_game_rows"] == 2982 and c["game_clusters"] == 1491,
              "the recorded census is the declared universe: 2,982 rows over 1,491 clusters",
              f"{c['team_game_rows']}/{c['game_clusters']}")
        check(c["cluster_size_distribution"] == {"2": 1491},
              "every game cluster holds exactly two team-game rows",
              str(c["cluster_size_distribution"]))


def t13_real_run_reconciles():
    print("T13 four-way artifact reconciliation of the real run's inputs")
    if not REAL.exists():
        skip("T13", "manifest not present")
        return
    rep = rr.reconcile(REAL)
    for row in rep["rows"]:
        print(f"  INFO  {row['verdict']:15s} {row['path']}  "
              f"({row['n_independent_hashes']} independent)")
    check(rep["n_disagreements"] == 0,
          "no input disagrees between manifest, disk, PROGRAM_STATE and its receipt",
          str([r["path"] for r in rep["rows"] if not r["agree"]]))
    check(rep["verdict"] == "PASS", "reconciliation verdict is PASS", rep["verdict"])
    print(f"  INFO  {rep['n_registered_canonical']}/{rep['n_inputs']} inputs are registered "
          f"canonical artifacts in PROGRAM_STATE.json; {rep['n_uncorroborated']} are "
          f"UNCORROBORATED (one hash source only)")


# --------------------------------------------------------------------------------------------
def main() -> int:
    tmpbase = Path(tempfile.mkdtemp(prefix="i13_repro_"))
    try:
        for i, fn in enumerate((t1_byte_identical, t2_seed_is_load_bearing,
                                t2b_seed_binding_absent, t3_input_hash_bound, t3b_input_missing,
                                t3c_input_mutated_by_run, t4_source_content_outranks_commit,
                                t4b_commit_moved_is_reported_not_silent,
                                t5_nondeterminism_is_caught, t6_failing_command,
                                t7_manifest_tampering, t8_closure_is_observed, t9_output_set,
                                t10_never_silent)):
            fn(tmpbase / f"case{i:02d}")
            print()
    finally:
        shutil.rmtree(tmpbase, ignore_errors=True)

    t11_real_run_reproduces()
    print()
    t12_real_run_bindings()
    print()
    t13_real_run_reconciles()
    print()

    if SKIPS:
        print(f"SKIPPED ({len(SKIPS)}): " + "; ".join(SKIPS))
    if FAILURES:
        print(f"FAILED ({len(FAILURES)}): " + "; ".join(FAILURES))
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
