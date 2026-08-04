#!/usr/bin/env python3
"""repro_runner.py — deterministic commands, seed manifests and artifact reconciliation.

WHAT THIS IS FOR
----------------
A number in this program is only citable if someone else can obtain the same number from the same
bytes. Today a run is described in prose ("I ran the census script") and the description is
unfalsifiable: it names no seed, no commit, no input hash, and no output hash. Rerunning it and
getting a different answer is indistinguishable from rerunning it and getting the same one.

This module makes a run a FALSIFIABLE OBJECT. ``record()`` executes a command and writes a
manifest that binds, in one signed-by-digest structure:

    the exact argv and working directory        the seeds, injected into the run, not observed
    the repository commit and dirty state       every source file the run ACTUALLY imported
    the sha256 of every declared input          the sha256 of every byte the run emitted
    the interpreter and package versions        the exit code

``verify()`` re-executes that command into a FRESH directory under the recorded bindings and
compares the new bytes with the recorded bytes. Anything that differs is a typed divergence.

THE THREE THINGS IT REFUSES TO DO
---------------------------------
1. It does not accept a divergence quietly. ``verify()`` raises ``ReproDivergence`` by default and
   the CLI exits non-zero. There is no "close enough" comparison anywhere in this file: outputs
   are compared as sha256 over bytes, not as parsed values with a tolerance.
2. It does not let the runner narrate its own provenance. The caller declares which sources it
   thinks matter; the execution wrapper reports which modules the interpreter ACTUALLY loaded from
   inside the program tree, and this module re-hashes those files from disk itself. A file that
   was imported but not bound is ``unbound_imported_source`` — a failure, not a footnote. This is
   the caller-manufactured-provenance lesson from ``construction_receipt.py`` applied to runs.
3. It does not treat a matching output as proof that the manifest is true. If an input hash,
   a source hash, a seed binding or the manifest digest itself has moved, the run FAILS even when
   the outputs happen to be byte-identical, because the manifest has stopped describing the run.

THREE SEVERITY CLASSES, AND WHY THE COMMIT IS NOT IN THE FIRST TWO
------------------------------------------------------------------
    class A  REPRODUCTION      the bytes did not come back                      -> FAIL
    class B  BINDING_INTEGRITY the manifest no longer describes the run         -> FAIL
    class C  CONTEXT           the world moved in a way the bytes survived      -> REPORTED

Class C exists for one honest reason. The commit is bound — recorded, re-read and compared — but
a manifest recorded before its own files are committed will ALWAYS be verified at a later commit,
because the coordinator commits after validating the node. If commit movement were class A, every
manifest in this repository would self-invalidate the moment it was committed, and the runner
would be useless. So: content hashes decide, the commit corroborates. This is the same ordering
``receipt_integrity.py`` uses for mtime versus hash, and it is stated rather than hidden. A commit
that moved while any bound source BYTE also moved is not class C — it is
``source_hash_divergence``, class B, and it fails.

A class C finding is never dropped: the verdict becomes ``PASS_WITH_CONTEXT_FINDINGS``, never a
bare ``PASS``, so a reader cannot mistake a moved world for an unmoved one.

WHAT THIS DOES NOT PROVE
------------------------
Reproducing on this machine, at this interpreter, from these bytes. It says nothing about a
different platform, a different pandas, or a run whose non-determinism is finer than the outputs
it writes. It proves nothing scientific about any arm, target or feature.

CLI
---
    python repro_runner.py verify   runs/<name>/MANIFEST.json
    python repro_runner.py inspect  runs/<name>/MANIFEST.json
    python repro_runner.py reconcile runs/<name>/MANIFEST.json
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True          # never leave a .pyc outside this node's directory

import argparse                                                               # noqa: E402
import hashlib                                                                # noqa: E402
import json                                                                   # noqa: E402
import os                                                                     # noqa: E402
import platform                                                               # noqa: E402
import shutil                                                                 # noqa: E402
import subprocess                                                             # noqa: E402
import uuid                                                                   # noqa: E402
from datetime import datetime, timezone                                       # noqa: E402
from pathlib import Path                                                      # noqa: E402

HERE = Path(__file__).resolve().parent
PROGRAM = HERE.parents[1]                       # experiments/player_program
ROOT = HERE.parents[3]                          # repository worktree root

SCHEMA = "repro_run_manifest/2"
VERIFICATION_SCHEMA = "repro_verification/2"
EXEC_WRAPPER = "_repro_exec.py"

#: the bytes did not come back. Nothing else in this module is allowed to outrank these.
CLASS_A_REPRODUCTION = frozenset({
    "command_failed",              # the recorded command did not exit 0 on replay
    "exit_code_divergence",        # it exited, but not with the recorded status
    "output_missing",              # a recorded output was not produced
    "output_extra",                # the replay produced a file the manifest does not record
    "output_hash_divergence",      # THE defect this runner exists to catch
})

#: the manifest has stopped describing the run. A failure even if the outputs matched.
CLASS_B_BINDING = frozenset({
    "manifest_tampered",           # recomputed manifest_digest != recorded manifest_digest
    "manifest_unsigned",           # no manifest_digest at all
    "seed_binding_absent",         # the manifest records no seed for a seeded runner
    "input_missing",               # a bound input is not on disk
    "input_hash_divergence",       # a bound input's bytes moved
    "input_mutated_by_run",        # the run wrote to something it declared as an input
    "source_missing",              # a bound source file is not on disk
    "source_hash_divergence",      # a bound source's bytes moved
    "source_mutated_during_run",   # a source changed between import and post-run hashing
    "unbound_imported_source",     # the run imported program code the manifest does not bind
})

#: the world moved in a way the bytes survived. Reported, never dropped, never blocking alone.
CLASS_C_CONTEXT = frozenset({
    "code_commit_moved",
    "code_tracking_status_changed",
    "worktree_dirty",
    "environment_divergence",
})

BLOCKING = CLASS_A_REPRODUCTION | CLASS_B_BINDING
ALL_KINDS = BLOCKING | CLASS_C_CONTEXT

SEVERITY = ({k: "A_REPRODUCTION" for k in CLASS_A_REPRODUCTION}
            | {k: "B_BINDING_INTEGRITY" for k in CLASS_B_BINDING}
            | {k: "C_CONTEXT" for k in CLASS_C_CONTEXT})


class ReproDivergence(RuntimeError):
    """Raised by ``verify`` on any class A or class B finding. Carries the full report."""

    def __init__(self, message: str, report: dict):
        super().__init__(message)
        self.report = report


class ReproRunnerError(RuntimeError):
    pass


# --------------------------------------------------------------------------- #
# primitives
# --------------------------------------------------------------------------- #
def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with Path(p).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_json(obj) -> str:
    """One byte sequence per value. Used for the manifest digest and for every emitted file."""
    return json.dumps(obj, sort_keys=True, ensure_ascii=True, separators=(",", ":"),
                      allow_nan=False)


def write_json(path: Path, obj, *, pretty: bool = True) -> None:
    text = (json.dumps(obj, sort_keys=True, ensure_ascii=True, indent=2, allow_nan=False)
            if pretty else canonical_json(obj))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(text + "\n")


def digest_manifest(m: dict) -> str:
    """sha256 over the canonical form of everything EXCEPT the digest field itself."""
    body = {k: v for k, v in m.items() if k != "manifest_digest"}
    return hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()


def relpath(p: Path, root: Path = ROOT) -> str:
    p = Path(p).resolve()
    try:
        return str(p.relative_to(Path(root).resolve())).replace("\\", "/")
    except ValueError:
        return str(p).replace("\\", "/")


def hash_tree(d: Path) -> dict[str, dict]:
    """Every file under ``d``, keyed by posix-relative name, hashed. Order-independent."""
    d = Path(d)
    out: dict[str, dict] = {}
    for p in sorted(d.rglob("*")):
        if p.is_file():
            out[str(p.relative_to(d)).replace("\\", "/")] = {
                "sha256": sha256_file(p), "bytes": p.stat().st_size}
    return out


# --------------------------------------------------------------------------- #
# git — READ ONLY. Never a mutating subcommand.
# --------------------------------------------------------------------------- #
_READ_ONLY_GIT = frozenset({"rev-parse", "log", "status", "ls-files"})


def _git(root: Path, *args: str) -> str | None:
    if not args or args[0] not in _READ_ONLY_GIT:
        raise ReproRunnerError(f"refusing to run a non-read-only git subcommand: {args[:1]}")
    try:
        r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True,
                           timeout=60)
    except Exception:                                                    # noqa: BLE001
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def git_context(root: Path, paths: list[str] | None = None) -> dict:
    """Commit, branch, and per-path tracked/dirty state. Corroboration, never the decider."""
    inside = _git(root, "rev-parse", "--is-inside-work-tree")
    if inside != "true":
        return {"git_available": False}
    ctx = {
        "git_available": True,
        "commit": _git(root, "rev-parse", "HEAD"),
        "commit_utc": _git(root, "log", "-1", "--format=%cI"),
        "branch": _git(root, "rev-parse", "--abbrev-ref", "HEAD"),
    }
    for rel in paths or []:
        tracked = _git(root, "ls-files", "--error-unmatch", rel) is not None
        dirty = bool(_git(root, "status", "--porcelain", "--", rel))
        ctx.setdefault("paths", {})[rel] = {"tracked": tracked, "dirty": dirty}
    return ctx


# --------------------------------------------------------------------------- #
# environment
# --------------------------------------------------------------------------- #
def environment() -> dict:
    pkgs = {}
    for name in ("numpy", "pandas", "pyarrow"):
        try:
            pkgs[name] = __import__(name).__version__
        except Exception:                                                # noqa: BLE001
            pkgs[name] = None
    return {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "system": platform.system(),
        "machine": platform.machine(),
        "packages": pkgs,
    }


# --------------------------------------------------------------------------- #
# execution
# --------------------------------------------------------------------------- #
def _child_env(seeds: dict) -> dict:
    """The seeds are INJECTED, not observed. PYTHONHASHSEED must be set before the interpreter
    starts, which is why it is an environment variable and not a call inside the payload."""
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = str(seeds["python_hash_seed"])
    env["REPRO_SEED"] = str(seeds["seed"])
    env["PYTHONDONTWRITEBYTECODE"] = "1"     # never write a .pyc outside this node's directory
    env.pop("PYTHONSTARTUP", None)
    return env


def execute(payload: Path, argv_tail: list[str], *, seeds: dict, cwd: Path,
            closure_out: Path, timeout: int = 1800, program_root: Path = PROGRAM,
            repo_root: Path = ROOT) -> dict:
    """Run the payload under the wrapper. Returns exit code, streams and the import closure.

    ``program_root`` scopes which loaded modules count as bound program code; the tests point it
    at a temporary tree so the closure machinery is exercised on synthetic files.
    """
    wrapper = HERE / EXEC_WRAPPER
    if not wrapper.exists():
        raise ReproRunnerError(f"execution wrapper missing: {wrapper}")
    argv = [sys.executable, str(wrapper), str(payload), *argv_tail]
    env = _child_env(seeds)
    env["REPRO_CLOSURE_OUT"] = str(closure_out)
    env["REPRO_PROGRAM_ROOT"] = str(program_root)
    env["REPRO_ROOT"] = str(repo_root)
    r = subprocess.run(argv, cwd=str(cwd), env=env, capture_output=True, text=True,
                       timeout=timeout)
    closure = []
    if closure_out.exists():
        closure = json.loads(closure_out.read_text(encoding="utf-8"))
    return {"argv": argv, "exit_code": r.returncode, "stdout": r.stdout, "stderr": r.stderr,
            "import_closure": closure}


# --------------------------------------------------------------------------- #
# record
# --------------------------------------------------------------------------- #
def record(run_dir: Path, *, payload: Path, argv_tail: list[str] | None = None,
           inputs: dict[str, Path], seed: int, python_hash_seed: int = 0,
           declared_sources: list[Path] | None = None, root: Path = ROOT,
           program: Path = PROGRAM, description: str = "", timeout: int = 1800) -> dict:
    """Execute once and write ``run_dir/MANIFEST.json`` plus ``run_dir/outputs/``.

    ``inputs`` maps a label to a path. Every input is hashed BEFORE and AFTER the run: a run that
    writes to its own declared input is ``input_mutated_by_run``, which no output comparison would
    ever have caught.
    """
    run_dir = Path(run_dir)
    out_dir = run_dir / "outputs"
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    seeds = {"seed": int(seed), "python_hash_seed": int(python_hash_seed),
             "bound_via": {"seed": "environment variable REPRO_SEED",
                           "python_hash_seed": "environment variable PYTHONHASHSEED",
                           "python_random": "random.seed(REPRO_SEED) in " + EXEC_WRAPPER,
                           "numpy_legacy": "numpy.random.seed(REPRO_SEED) in " + EXEC_WRAPPER}}

    inputs_before = {}
    for label, p in inputs.items():
        p = Path(p)
        if not p.exists():
            raise ReproRunnerError(f"declared input does not exist: {label} -> {p}")
        inputs_before[label] = {"path": relpath(p, root), "sha256": sha256_file(p),
                                "bytes": p.stat().st_size}

    # ``{OUT}`` is the ONLY thing that may differ between the recorded run and its replay: the
    # replay writes to a fresh directory so it cannot be handed the recorded bytes by accident.
    argv_tail = list(argv_tail or [])
    closure_out = run_dir / "_import_closure.json"
    res = execute(Path(payload), [t.replace("{OUT}", str(out_dir)) for t in argv_tail],
                  seeds=seeds, cwd=root, closure_out=closure_out, timeout=timeout,
                  program_root=Path(program), repo_root=root)
    if res["exit_code"] != 0:
        raise ReproRunnerError(
            f"payload exited {res['exit_code']}; refusing to record a manifest for a failed run\n"
            f"--- stderr ---\n{res['stderr'][-4000:]}")

    inputs_after = {label: sha256_file(root / v["path"]) for label, v in inputs_before.items()}
    mutated = [k for k, v in inputs_before.items() if inputs_after[k] != v["sha256"]]
    if mutated:
        raise ReproRunnerError(f"the run mutated its own declared inputs: {mutated}")

    # sources: what the caller declared, UNION what the interpreter actually loaded from the
    # program tree. The wrapper reports WHICH files; this module hashes them itself.
    declared = {relpath(Path(p), root) for p in (declared_sources or [])}
    imported = {c["path"] for c in res["import_closure"]}
    bound = sorted(declared | imported)
    src: dict[str, dict] = {}
    for rel in bound:
        p = root / rel
        entry = {"sha256": sha256_file(p) if p.exists() else None,
                 "bytes": p.stat().st_size if p.exists() else None,
                 "declared_by_caller": rel in declared,
                 "imported_at_runtime": rel in imported}
        hit = [c for c in res["import_closure"] if c["path"] == rel]
        if hit and hit[0].get("sha256") and hit[0]["sha256"] != entry["sha256"]:
            raise ReproRunnerError(f"source changed while the run was executing: {rel}")
        src[rel] = entry

    gctx = git_context(root, bound + [relpath(Path(payload), root)])

    outputs = hash_tree(out_dir)
    if not outputs:
        raise ReproRunnerError("the run produced no output files; there is nothing to reproduce")

    manifest = {
        "schema": SCHEMA,
        "run_name": run_dir.name,
        "run_id": str(uuid.uuid4()),
        "recorded_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "description": description,
        "recorded_by": relpath(Path(__file__), root),
        "command": {
            "argv_recorded": [_portable_argv_token(a, root) for a in res["argv"]],
            "payload": relpath(Path(payload), root),
            "argv_tail": list(argv_tail or []),
            "cwd": relpath(root, root) or ".",
            "note": "argv_recorded is the literal process argv with absolute paths rewritten "
                    "repo-relative; verify() rebuilds it from payload + argv_tail so a manifest "
                    "moved to another checkout still runs.",
        },
        "seeds": seeds,
        "environment": environment(),
        "code": {
            "program_root": relpath(Path(program), root),
            "commit": gctx.get("commit"),
            "commit_utc": gctx.get("commit_utc"),
            "branch": gctx.get("branch"),
            "git_available": gctx.get("git_available", False),
            "path_state": gctx.get("paths", {}),
            "sources": src,
            "source_closure_measured": True,
            "source_closure_note": "every module the interpreter loaded from the program tree, "
                                   "reported by " + EXEC_WRAPPER + " and re-hashed from disk here",
        },
        "inputs": inputs_before,
        "outputs": outputs,
        "exit_code": res["exit_code"],
        "stdout_sha256": hashlib.sha256(res["stdout"].encode("utf-8")).hexdigest(),
    }
    manifest["manifest_digest"] = digest_manifest(manifest)
    write_json(run_dir / "MANIFEST.json", manifest)
    if closure_out.exists():
        closure_out.unlink()
    return manifest


def _portable_argv_token(a: str, root: Path) -> str:
    p = Path(a)
    try:
        if p.is_absolute() and p.exists():
            return relpath(p, root)
    except OSError:
        pass
    return a


# --------------------------------------------------------------------------- #
# verify
# --------------------------------------------------------------------------- #
def verify(manifest_path: Path, *, root: Path = ROOT, workdir: Path | None = None,
           raise_on_divergence: bool = True, keep_workdir: bool = False,
           timeout: int = 1800) -> dict:
    """Re-execute the recorded command under the recorded bindings and compare bytes.

    Returns a machine-readable report. Raises ``ReproDivergence`` on any class A or class B
    finding unless ``raise_on_divergence=False`` — and even then the finding is in the report and
    the verdict is FAIL. There is no code path in this module that returns PASS with a blocking
    finding present.
    """
    manifest_path = Path(manifest_path)
    root = Path(root)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    findings: list[dict] = []

    def add(kind: str, subject: str, **detail):
        if kind not in ALL_KINDS:
            raise ReproRunnerError(f"undeclared divergence kind: {kind}")
        findings.append({"kind": kind, "severity": SEVERITY[kind], "subject": subject, **detail})

    # -- 0. the manifest must not have been edited after it was signed ------------ #
    recorded_digest = manifest.get("manifest_digest")
    if not recorded_digest:
        add("manifest_unsigned", "MANIFEST.json",
            why="no manifest_digest, so nothing binds the fields to each other")
    else:
        actual_digest = digest_manifest(manifest)
        if actual_digest != recorded_digest:
            add("manifest_tampered", "MANIFEST.json", recorded=recorded_digest,
                recomputed=actual_digest,
                why="a field was edited after the manifest was written; every binding below is "
                    "unreliable and this run cannot be accepted on any evidence it carries")

    # -- 1. seeds must be bound --------------------------------------------------- #
    seeds = manifest.get("seeds") or {}
    for key in ("seed", "python_hash_seed"):
        if not isinstance(seeds.get(key), int):
            add("seed_binding_absent", key,
                why="the manifest records no integer seed, so the run cannot be re-executed "
                    "under the conditions it claims")

    # -- 2. inputs ---------------------------------------------------------------- #
    for label, rec in (manifest.get("inputs") or {}).items():
        p = root / rec["path"]
        if not p.exists():
            add("input_missing", label, path=rec["path"])
            continue
        now = sha256_file(p)
        if now != rec["sha256"]:
            add("input_hash_divergence", label, path=rec["path"], recorded=rec["sha256"],
                on_disk=now,
                why="the bytes this run consumed are not the bytes on disk now; the manifest no "
                    "longer describes a run anyone can repeat")

    # -- 3. code: content decides, the commit corroborates ------------------------ #
    code = manifest.get("code") or {}
    src = code.get("sources") or {}
    source_moved = False
    for rel, rec in src.items():
        p = root / rel
        if not p.exists():
            add("source_missing", rel)
            source_moved = True
            continue
        now = sha256_file(p)
        if rec.get("sha256") and now != rec["sha256"]:
            source_moved = True
            add("source_hash_divergence", rel, recorded=rec["sha256"], on_disk=now,
                why="program code the run actually imported has changed since it was recorded")

    live = git_context(root, list(src) + [manifest["command"]["payload"]])
    if code.get("commit") and live.get("commit") and code["commit"] != live["commit"]:
        if source_moved:
            pass        # already a class B source_hash_divergence; the commit only explains it
        else:
            add("code_commit_moved", "HEAD", recorded=code["commit"], live=live["commit"],
                why="the repository advanced, but every bound source byte is identical. Content "
                    "decides; the commit is recorded as corroboration. This is REPORTED, never "
                    "dropped: the verdict cannot be a bare PASS while this is present.")
    for rel, was in (code.get("path_state") or {}).items():
        now = (live.get("paths") or {}).get(rel)
        if now and now.get("tracked") != was.get("tracked"):
            add("code_tracking_status_changed", rel, recorded=was, live=now,
                why="the file moved between tracked and untracked; commit ancestry is not "
                    "available for the untracked side")
        if now and now.get("dirty") and not was.get("dirty"):
            add("worktree_dirty", rel, recorded=was, live=now)

    # -- 4. environment ------------------------------------------------------------ #
    env_now, env_then = environment(), manifest.get("environment") or {}
    env_delta = {k: {"recorded": env_then.get(k), "live": env_now.get(k)}
                 for k in env_now if env_then.get(k) != env_now.get(k)}
    if env_delta:
        add("environment_divergence", "interpreter_or_packages", delta=env_delta,
            why="the interpreter or a numeric package changed. If the outputs still match "
                "byte-for-byte the reproduction held anyway; this is recorded so a later reader "
                "knows the replay was not on identical footing.")

    # -- 5. RE-EXECUTE and compare bytes ------------------------------------------- #
    tmp = Path(workdir) if workdir else (manifest_path.parent / "_verify")
    if tmp.exists():
        shutil.rmtree(tmp)
    out_dir = tmp / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = root / manifest["command"]["payload"]
    tail = [t.replace("{OUT}", str(out_dir)) for t in manifest["command"]["argv_tail"]]
    replay = {"exit_code": None}
    try:
        replay = execute(payload, tail, seeds=seeds, cwd=root,
                         closure_out=tmp / "_import_closure.json", timeout=timeout,
                         program_root=root / (code.get("program_root") or relpath(PROGRAM, root)),
                         repo_root=root)
    except Exception as exc:                                             # noqa: BLE001
        add("command_failed", manifest["command"]["payload"], error=repr(exc)[:400])
    else:
        if replay["exit_code"] != manifest.get("exit_code", 0):
            add("exit_code_divergence", manifest["command"]["payload"],
                recorded=manifest.get("exit_code", 0), replay=replay["exit_code"],
                stderr=replay["stderr"][-2000:])

        # every module the replay imported must be bound by the manifest
        for c in replay["import_closure"]:
            if c["path"] not in src:
                add("unbound_imported_source", c["path"],
                    why="the replay imported program code the manifest does not bind, so a "
                        "change to that file would not have been detected by this runner")

    got = hash_tree(out_dir)
    want = manifest.get("outputs") or {}
    for name, rec in sorted(want.items()):
        if name not in got:
            add("output_missing", name, recorded=rec["sha256"])
        elif got[name]["sha256"] != rec["sha256"]:
            add("output_hash_divergence", name, recorded=rec["sha256"],
                replay=got[name]["sha256"], recorded_bytes=rec["bytes"],
                replay_bytes=got[name]["bytes"],
                why="THE reproduction failure: the same command, the same seeds and the same "
                    "inputs did not return the same bytes")
    for name in sorted(set(got) - set(want)):
        add("output_extra", name, replay=got[name]["sha256"],
            why="the replay emitted a file the recorded run did not; the manifest does not "
                "describe everything this command produces")

    blocking = [f for f in findings if f["kind"] in BLOCKING]
    context = [f for f in findings if f["kind"] in CLASS_C_CONTEXT]
    verdict = ("FAIL" if blocking else
               ("PASS_WITH_CONTEXT_FINDINGS" if context else "PASS"))
    report = {
        "schema": VERIFICATION_SCHEMA,
        "manifest": relpath(manifest_path, root),
        "run_name": manifest.get("run_name"),
        "run_id_recorded": manifest.get("run_id"),
        "verified_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "verified_at_commit": live.get("commit"),
        "verdict": verdict,
        "byte_identical": not any(f["kind"] in CLASS_A_REPRODUCTION for f in findings),
        "outputs_compared": len(want),
        "outputs_matching": sum(1 for n, r in want.items()
                                if n in got and got[n]["sha256"] == r["sha256"]),
        "inputs_checked": len(manifest.get("inputs") or {}),
        "sources_checked": len(src),
        "findings": findings,
        "blocking_findings": len(blocking),
        "context_findings": len(context),
        "replay_outputs": got,
        "epistemic_status": "INFRASTRUCTURE. Makes a run rerunnable and checkable. Proves "
                            "nothing scientific.",
    }
    if not keep_workdir and tmp.exists():
        shutil.rmtree(tmp, ignore_errors=True)
    if blocking and raise_on_divergence:
        raise ReproDivergence(
            f"{len(blocking)} blocking divergence(s) verifying {manifest.get('run_name')}: "
            + "; ".join(f"{f['kind']}:{f['subject']}" for f in blocking[:6]), report)
    return report


# --------------------------------------------------------------------------- #
# artifact reconciliation — manifest vs disk vs PROGRAM_STATE
# --------------------------------------------------------------------------- #
#: where a receipt on disk records the hash of an input this node's runs consume, but the program
#: state file does not publish it. Read-only bindings; this module never edits a receipt. Each
#: entry is (receipt path relative to the program dir, JSON path inside it).
RECEIPT_BINDINGS: dict[str, tuple[str, tuple]] = {
    "experiments/player_program/possessions_v2/possessions_raw_v2.parquet":
        ("possessions_v2/POSSESSION_INTEGRITY_RECEIPT_V2.json", ("integrity", "artifact_sha256")),
    "experiments/player_program/projected_exposure_v1/team_possession_prior_v1.parquet":
        ("projected_exposure_v1/PROJECTED_EXPOSURE_RECEIPT.json",
         ("outputs", "team_possession_prior_v1.parquet", "sha256")),
}


def _resolve(obj, path: tuple):
    cur = obj
    for seg in path:
        if not isinstance(cur, dict) or seg not in cur:
            return None
        cur = cur[seg]
    return cur if isinstance(cur, str) else None


def reconcile(manifest_path: Path, *, root: Path = ROOT,
              program_state: Path | None = None) -> dict:
    """Four-way reconciliation for every input a manifest binds.

        the hash the MANIFEST recorded when the run consumed the artifact
        the hash of the BYTES ON DISK now
        the hash PROGRAM_STATE.json publishes for it, where it publishes one
        the hash the artifact's own RECEIPT records, where a binding is declared above

    A manifest can agree with the bytes on disk while both disagree with what the program
    publishes. Comparing only two of the four would clear exactly that case, which is the
    receipt-drift shape ``receipt_integrity.py`` was written for, one level up at the RUN layer.
    An input for which fewer than two independent hashes exist is reported as
    ``UNCORROBORATED`` — not as a pass.
    """
    root = Path(root)
    ps_path = Path(program_state) if program_state else (PROGRAM / "PROGRAM_STATE.json")
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    published: dict[str, dict] = {}
    if ps_path.exists():
        S = json.loads(ps_path.read_text(encoding="utf-8"))
        for aid, rec in (S.get("canonical_artifacts") or {}).items():
            fam = rec.get("family")
            for fname, h in (rec.get("artifact_sha256") or {}).items():
                published[f"experiments/player_program/{fam}/{fname}"] = {
                    "artifact_id": aid, "published_sha256": h}

    rows = []
    for label, rec in (manifest.get("inputs") or {}).items():
        p = root / rec["path"]
        on_disk = sha256_file(p) if p.exists() else None
        pub = published.get(rec["path"])
        receipt_hash = receipt_src = None
        if rec["path"] in RECEIPT_BINDINGS:
            rel, jpath = RECEIPT_BINDINGS[rec["path"]]
            rp = PROGRAM / rel
            if rp.exists():
                receipt_hash = _resolve(json.loads(rp.read_text(encoding="utf-8")), jpath)
                receipt_src = f"{relpath(rp, root)}:{'.'.join(jpath)}"
        row = {"input": label, "path": rec["path"], "in_manifest": rec["sha256"],
               "on_disk": on_disk,
               "published_in_program_state": (pub or {}).get("published_sha256"),
               "in_artifact_receipt": receipt_hash, "receipt_source": receipt_src,
               "artifact_id": (pub or {}).get("artifact_id"),
               "registered_canonical": pub is not None}
        independent = [v for v in (row["on_disk"], row["published_in_program_state"],
                                   row["in_artifact_receipt"]) if v is not None]
        vals = {v for v in ([row["in_manifest"]] + independent) if v is not None}
        row["n_independent_hashes"] = len(independent)
        row["agree"] = len(vals) == 1
        if not row["agree"]:
            row["verdict"] = "DISAGREE"
        elif len(independent) < 2:
            row["verdict"] = "UNCORROBORATED"
            row["note"] = ("the manifest and the bytes agree, but nothing else on disk publishes "
                           "a hash for this file, so a coordinated change would be invisible")
        else:
            row["verdict"] = "AGREE"
        rows.append(row)
    disagreements = [r for r in rows if not r["agree"]]
    return {
        "schema": "repro_artifact_reconciliation/2",
        "manifest": relpath(Path(manifest_path), root),
        "program_state": relpath(ps_path, root),
        "program_state_present": ps_path.exists(),
        "rows": rows,
        "n_inputs": len(rows),
        "n_registered_canonical": sum(1 for r in rows if r["registered_canonical"]),
        "n_uncorroborated": sum(1 for r in rows if r["verdict"] == "UNCORROBORATED"),
        "n_disagreements": len(disagreements),
        "verdict": "FAIL" if disagreements else "PASS",
    }


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("command", choices=("verify", "inspect", "reconcile"))
    ap.add_argument("manifest")
    ap.add_argument("--keep-workdir", action="store_true")
    a = ap.parse_args(argv)
    mp = Path(a.manifest)
    if not mp.is_absolute():
        mp = (Path.cwd() / mp).resolve()

    if a.command == "inspect":
        m = json.loads(mp.read_text(encoding="utf-8"))
        ok = digest_manifest(m) == m.get("manifest_digest")
        print(f"run           : {m.get('run_name')}  ({m.get('run_id')})")
        print(f"recorded      : {m.get('recorded_utc')}")
        print(f"commit        : {(m.get('code') or {}).get('commit')}")
        print(f"seed          : {(m.get('seeds') or {}).get('seed')}  "
              f"PYTHONHASHSEED={(m.get('seeds') or {}).get('python_hash_seed')}")
        print(f"inputs bound  : {len(m.get('inputs') or {})}")
        print(f"sources bound : {len((m.get('code') or {}).get('sources') or {})}")
        print(f"outputs bound : {len(m.get('outputs') or {})}")
        print(f"digest        : {'INTACT' if ok else 'TAMPERED'}")
        return 0 if ok else 1

    if a.command == "reconcile":
        rep = reconcile(mp)
        print(canonical_json(rep)[:200] + " ...")
        for r in rep["rows"]:
            print(f"  {r['verdict']:15s} {r['path']}   "
                  f"[{r['n_independent_hashes']} independent hash(es)]")
        print(f"verdict: {rep['verdict']}  ({rep['n_disagreements']} disagreement(s), "
              f"{rep['n_uncorroborated']} uncorroborated)")
        return 0 if rep["verdict"] == "PASS" else 1

    try:
        rep = verify(mp, keep_workdir=a.keep_workdir)
    except ReproDivergence as exc:
        rep = exc.report
        print(str(exc))
    for f in rep["findings"]:
        print(f"  [{f['severity']}] {f['kind']}: {f['subject']}")
    print(f"verdict: {rep['verdict']}  "
          f"({rep['outputs_matching']}/{rep['outputs_compared']} outputs byte-identical, "
          f"{rep['blocking_findings']} blocking, {rep['context_findings']} context)")
    return 0 if rep["verdict"] != "FAIL" else 1


if __name__ == "__main__":
    sys.exit(main())
