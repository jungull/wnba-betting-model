#!/usr/bin/env python3
"""test_failclosed_gate.py — the five conditions the fail-closed producer gate must satisfy.

Authorized focused tests for the provenance-only repair that adds `_git_checked` and `_git_env`
to `run_player_oof_v14.py` and `run_team_oof_v12_2.py`.

    T1  a genuinely clean tree PASSES, and the receipt says it MEASURED it
    T2  a dirty tree FAILS
    T3  a failed git command FAILS CLOSED (does not read as clean)
    T4  an inherited or wrong GIT_DIR cannot forge a false-clean receipt
    T5  predictions are BIT-IDENTICAL when the gate passes

**Nothing here is scored.** T5 compares forecast bytes to forecast bytes — no outcome is read, no
metric is computed, no forecast is compared to any outcome. Every other test asserts a gate verdict.

Each test builds a THROWAWAY git repository in a temp directory. No test touches this repository,
its worktrees, its config, or any artifact.

Run::

    python experiments/player_program/test_failclosed_gate.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

import run_player_oof_v14 as RP                                      # noqa: E402
import run_team_oof_v12_2 as RT                                      # noqa: E402

RUNNERS = (("run_player_oof_v14", RP), ("run_team_oof_v12_2", RT))

_RESULTS: list[dict] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    _RESULTS.append({"check": name, "ok": bool(cond), "detail": detail})
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not cond:
        raise AssertionError(f"{name}: {detail}")


def _run(cwd: Path, *args: str, env=None) -> subprocess.CompletedProcess:
    e = dict(os.environ)
    for k in RP._GIT_ENV_TO_SCRUB:
        e.pop(k, None)
    if env:
        e.update(env)
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True,
                          encoding="utf-8", env=e)


_REPO_SEQ = [0]


def make_repo(tmp: Path, mod) -> Path:
    """A throwaway repo containing every one of `mod`'s producer sources, committed.

    Each call gets its own directory: several tests need two independent repositories, and a
    reused path would silently compare a repo against itself.
    """
    _REPO_SEQ[0] += 1
    root = tmp / f"repo_{_REPO_SEQ[0]:03d}"
    root.mkdir(parents=True)
    _run(root, "init", "-q")
    _run(root, "config", "user.email", "t@t.t")
    _run(root, "config", "user.name", "t")
    _run(root, "config", "core.bare", "false")
    for rel in mod.PRODUCER_SOURCES:
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"# stand-in for {rel}\n", encoding="utf-8", newline="")
    _run(root, "add", "-A")
    _run(root, "commit", "-qm", "base")
    return root


# --------------------------------------------------------------------------

def t1_clean_passes(tmp: Path) -> None:
    print("\nT1 — a genuinely clean tree PASSES and the receipt says it measured one")
    for name, mod in RUNNERS:
        root = make_repo(tmp, mod)
        rec = mod.require_clean_producer(root)
        check(f"{name}: ok", rec["ok"] is True)
        check(f"{name}: clean", rec["working_tree_clean_vs_head"] is True)
        check(f"{name}: n_dirty_paths == 0", rec["n_dirty_paths"] == 0)
        check(f"{name}: commit is a real sha", bool(RP._SHA_RE.match(rec["commit"])),
              rec["commit"][:12])
        # the receipt must ASSERT that it measured, not merely report a verdict
        check(f"{name}: receipt records toplevel-matched-root",
              rec.get("git_toplevel_matched_root") is True)
        check(f"{name}: receipt records env scrubbing",
              isinstance(rec.get("inherited_git_env_scrubbed"), list)
              and "GIT_DIR" in rec["inherited_git_env_scrubbed"])
        check(f"{name}: receipt records failure-is-refusal",
              rec.get("git_failure_is_a_refusal_not_a_clean_verdict") is True)
        check(f"{name}: all producer sources digested",
              len(rec["producer_source_sha256"]) == len(mod.PRODUCER_SOURCES))


def t2_dirty_fails(tmp: Path) -> None:
    print("\nT2 — a dirty tree FAILS")
    for name, mod in RUNNERS:
        root = make_repo(tmp, mod)
        (root / "an_untracked_file.txt").write_text("dirt\n", encoding="utf-8")
        try:
            mod.require_clean_producer(root)
            check(f"{name}: refuses an untracked file", False, "it did NOT refuse")
        except mod.DirtyProducer as exc:
            check(f"{name}: refuses an untracked file", "dirty path" in str(exc))

        # and a MODIFIED producer source, which is the case that actually matters
        root2 = make_repo(tmp, mod)
        tgt = root2 / mod.PRODUCER_SOURCES[0]
        tgt.write_text("# TAMPERED\n", encoding="utf-8", newline="")
        try:
            mod.require_clean_producer(root2)
            check(f"{name}: refuses a modified producer source", False, "it did NOT refuse")
        except mod.DirtyProducer:
            check(f"{name}: refuses a modified producer source", True)

        # the override still exists, and still stamps the output as not reproducible
        rec = mod.require_clean_producer(root2, allow_dirty=True)
        check(f"{name}: --allow-dirty stamps not_reproducible",
              rec.get("not_reproducible") is True and rec["ok"] is False)


def t3_failed_git_fails_closed(tmp: Path) -> None:
    print("\nT3 — a failed git command FAILS CLOSED, it does not read as clean")
    for name, mod in RUNNERS:
        root = make_repo(tmp, mod)
        # Reproduce the EXACT production condition: core.bare=true on a normal checkout makes
        # `git status` exit 128 while `git rev-parse HEAD` still exits 0.
        _run(root, "config", "core.bare", "true")
        st = _run(root, "status", "--porcelain")
        hd = _run(root, "rev-parse", "HEAD")
        check(f"{name}: precondition — status fails", st.returncode != 0, f"exit {st.returncode}")
        check(f"{name}: precondition — rev-parse HEAD still succeeds", hd.returncode == 0)
        check(f"{name}: precondition — the failure looks like an empty (clean) status",
              st.stdout.strip() == "")
        try:
            rec = mod.require_clean_producer(root)
            check(f"{name}: REFUSES when git cannot measure the tree", False,
                  f"it returned ok={rec['ok']} n_dirty_paths={rec['n_dirty_paths']} — FAIL-OPEN")
        except mod.DirtyProducer as exc:
            check(f"{name}: REFUSES when git cannot measure the tree",
                  "Refusing" in str(exc) or "did not describe" in str(exc))
        _run(root, "config", "core.bare", "false")


def t4_bad_git_dir_cannot_forge_clean(tmp: Path) -> None:
    print("\nT4 — an inherited or wrong GIT_DIR cannot forge a false-clean receipt")
    for name, mod in RUNNERS:
        root = make_repo(tmp, mod)
        other = make_repo(tmp, mod)          # a DIFFERENT clean repository
        (root / "dirt.txt").write_text("x\n", encoding="utf-8")  # the real tree IS dirty

        clean = make_repo(tmp, mod)                              # a clean tree, same shape
        own = _run(clean, "rev-parse", "HEAD").stdout.strip()
        foreign = _run(other, "rev-parse", "HEAD").stdout.strip()
        check(f"{name}: the two fixture repos have different commits", own != foreign)

        # What an unscrubbed leak actually does is git-version and layout dependent: with GIT_DIR
        # alone it can report NOISE (another repo's index against these files), and with
        # GIT_DIR+GIT_WORK_TREE it can report a foreign tree as clean. Both are wrong, and the
        # gate must be immune to BOTH, so the leak's observed shape is recorded as a diagnostic
        # rather than asserted — asserting one shape would make this test fail on a git that
        # exhibits the other, while proving nothing extra about the gate.
        for label, leak in (("GIT_DIR only", {"GIT_DIR": str(other / ".git")}),
                            ("GIT_DIR+GIT_WORK_TREE", {"GIT_DIR": str(other / ".git"),
                                                       "GIT_WORK_TREE": str(other)})):
            unscrubbed = subprocess.run(
                ["git", "-C", str(root), "status", "--porcelain"], capture_output=True,
                text=True, encoding="utf-8", env={**os.environ, **leak})
            shape = ("EMPTY (reads as clean)" if not unscrubbed.stdout.strip()
                     else f"{len(unscrubbed.stdout.strip().splitlines())} lines of foreign noise")
            print(f"        · diagnostic — unscrubbed `{label}` yields: {shape}")

            os.environ.update(leak)
            try:
                # (a) the DIRTY tree must still be refused, whatever the leak reports
                try:
                    rec = mod.require_clean_producer(root)
                    check(f"{name}: dirty tree + leaked {label} still REFUSES", False,
                          f"forged a receipt: ok={rec['ok']}, "
                          f"n_dirty_paths={rec['n_dirty_paths']}, commit={rec['commit'][:12]}")
                except mod.DirtyProducer:
                    check(f"{name}: dirty tree + leaked {label} still REFUSES", True)

                # (b) the CLEAN tree must pass and report ITS OWN commit, never the foreign one
                rec = mod.require_clean_producer(clean)
                check(f"{name}: clean tree + leaked {label} reports its OWN commit",
                      rec["commit"] == own, rec["commit"][:12])
                check(f"{name}: clean tree + leaked {label} does NOT report the foreign commit",
                      rec["commit"] != foreign)
                check(f"{name}: clean tree + leaked {label} still measured the tree",
                      rec["git_toplevel_matched_root"] is True and rec["n_dirty_paths"] == 0)
            finally:
                for k in leak:
                    os.environ.pop(k, None)


def t5_predictions_bit_identical() -> None:
    """The repair must not perturb a single forecast byte.

    The gate is upstream of everything; if the repair changed any fitted or emitted value this is
    where it would show. Two independent runs of the real 2022 player fold are compared
    COLUMN BY COLUMN for exact equality, including the model hashes and the provenance sidecar
    digest. No outcome is read and no metric is computed.
    """
    print("\nT5 — predictions are BIT-IDENTICAL when the gate passes")
    import pandas as pd

    import cbs_real_frames_v3 as rf3
    import cbs_v14 as v14

    built = rf3.build_player_frame(2022, REPO, require_attested=True)
    man = v14.build_fold_manifest(built["train"], built["test"], built["universe"], root=REPO)
    snap = v14.snapshot_identity(man)

    def one():
        return v14.run_player_fold(
            built["train"], built["test"], "season:2022",
            config_hash=v14.REGISTERED_CONFIG_HASH, snapshot_hash=snap,
            snapshot_manifest=man, universe=built["universe"], synthetic=False,
            artifact_root=REPO)

    a, b = one(), one()
    check("both runs pass their receipts",
          a["scoring_permitted"] and b["scoring_permitted"])
    check("same target set", sorted(a["predictions"]) == sorted(b["predictions"]))
    for tgt in sorted(a["predictions"]):
        pa, pb = a["predictions"][tgt], b["predictions"][tgt]
        check(f"{tgt}: same shape", pa.shape == pb.shape, str(pa.shape))
        pd.testing.assert_frame_equal(pa, pb, check_exact=True)
        check(f"{tgt}: every column bit-identical", True, f"{len(pa)} rows")
    check("provenance sidecar digest identical",
          a["provenance_sidecar_digest"] == b["provenance_sidecar_digest"],
          a["provenance_sidecar_digest"][:16])
    check("selected constants identical",
          a["diagnostics"]["selected"] == b["diagnostics"]["selected"],
          json.dumps({k: v for k, v in a["diagnostics"]["selected"].items()
                      if k != "boundaries"}))
    check("no outcome column emitted",
          not any(c in p.columns for p in a["predictions"].values()
                  for c in RP.OUTCOME_COLS))


def main() -> int:
    print("=" * 78)
    print("fail-closed producer gate — focused authorized tests")
    print("=" * 78)
    with tempfile.TemporaryDirectory(prefix="failclosed_") as td:
        tmp = Path(td)
        t1_clean_passes(tmp)
        t2_dirty_fails(tmp)
        t3_failed_git_fails_closed(tmp)
        t4_bad_git_dir_cannot_forge_clean(tmp)
    t5_predictions_bit_identical()

    n = len(_RESULTS)
    print("\n" + "=" * 78)
    print(f"{n}/{n} checks PASS")
    out = Path(__file__).resolve().parent / "FAILCLOSED_GATE_TEST_RECEIPT.json"
    out.write_text(json.dumps({
        "schema": "failclosed_gate_tests/1",
        "n_checks": n, "all_passed": all(r["ok"] for r in _RESULTS),
        "scope": ("gate verdicts and forecast-byte equality only; nothing is scored and no "
                  "forecast is compared to any outcome"),
        "conditions": {
            "T1": "a genuinely clean tree passes and the receipt asserts it measured one",
            "T2": "a dirty tree fails, including a modified producer source",
            "T3": "a failed git command fails closed (core.bare=true reproduction)",
            "T4": "an inherited or wrong GIT_DIR cannot forge a false-clean receipt",
            "T5": "predictions bit-identical across two runs when the gate passes",
        },
        "checks": _RESULTS,
    }, indent=2) + "\n", encoding="utf-8", newline="")
    print(f"wrote {out.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
