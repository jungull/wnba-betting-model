#!/usr/bin/env python3
"""_repro_exec.py — the execution wrapper ``repro_runner`` spawns.

Two jobs, both of which have to happen INSIDE the child process:

1. **Bind the seeds before the payload gets control.** ``PYTHONHASHSEED`` is read by the
   interpreter at start-up and cannot be set from inside; the runner puts it in the child's
   environment. ``random.seed`` and ``numpy.random.seed`` are set here, before the payload is
   loaded, so a payload that reaches for a global RNG is seeded whether or not its author thought
   about it. A payload that wants its own generator reads ``REPRO_SEED``.

2. **Report the import closure the interpreter ACTUALLY built.** After the payload finishes, walk
   ``sys.modules`` and record every module whose file lives under the program tree. This is the
   difference between a run that declares its own provenance and a run whose provenance is
   observed: the payload is not asked what it imported, and cannot answer.

The hashes emitted here are a cross-check only. ``repro_runner`` re-hashes every reported file
from disk itself and compares; a disagreement means a source changed while the run was executing.

This file writes nothing except the closure file the runner names in ``REPRO_CLOSURE_OUT``.
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import hashlib                                                                # noqa: E402
import json                                                                   # noqa: E402
import os                                                                     # noqa: E402
import random                                                                 # noqa: E402
import runpy                                                                  # noqa: E402
from pathlib import Path                                                      # noqa: E402


def _sha256(p: Path) -> str | None:
    try:
        h = hashlib.sha256()
        with p.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def _emit_closure() -> None:
    out = os.environ.get("REPRO_CLOSURE_OUT")
    prog = os.environ.get("REPRO_PROGRAM_ROOT")
    if not out or not prog:
        return
    program = Path(prog).resolve()
    root = Path(os.environ.get("REPRO_ROOT") or program.parents[1]).resolve()
    seen: dict[str, dict] = {}
    for mod in list(sys.modules.values()):
        f = getattr(mod, "__file__", None)
        if not f:
            continue
        try:
            p = Path(f).resolve()
        except OSError:
            continue
        if p.suffix != ".py":
            continue
        try:
            p.relative_to(program)
        except ValueError:
            continue
        rel = str(p.relative_to(root)).replace("\\", "/")
        seen[rel] = {"path": rel, "sha256": _sha256(p),
                     "module": getattr(mod, "__name__", None)}
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    with Path(out).open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps([seen[k] for k in sorted(seen)], sort_keys=True, indent=2) + "\n")


def main() -> int:
    seed_raw = os.environ.get("REPRO_SEED")
    if seed_raw is None:
        sys.stderr.write("_repro_exec: REPRO_SEED is not set; refusing to run an unseeded run\n")
        return 2
    seed = int(seed_raw)
    random.seed(seed)
    try:
        import numpy as np
        np.random.seed(seed % (2 ** 32))
    except Exception:                                                    # noqa: BLE001
        pass

    if len(sys.argv) < 2:
        sys.stderr.write("_repro_exec: usage: _repro_exec.py <payload.py> [args...]\n")
        return 2
    target = str(Path(sys.argv[1]).resolve())
    sys.argv = [target] + sys.argv[2:]

    code = 0
    try:
        runpy.run_path(target, run_name="__main__")
    except SystemExit as exc:
        code = 0 if exc.code is None else (exc.code if isinstance(exc.code, int) else 1)
    finally:
        _emit_closure()
    return code


if __name__ == "__main__":
    sys.exit(main())
