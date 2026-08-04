#!/usr/bin/env python
"""test_frozen_path_guard.py — proof that the frozen-path guard fails CLOSED.

INFRASTRUCTURE. Demonstrates the guard rejects what it must reject. Does not modify any
shared gate: enforcement is added at the call site, never inside feature_gate.py.

Every check here drives ``scripts/frozen_path_guard.py:main()`` and asserts on its exit code
and its printed verdict. Nothing re-implements the guard's decision and then tests the
re-implementation -- that is how a guard test manufactures its own green.

Three properties are established:

  1. REJECTION. A change to a frozen directory, a frozen file, an Arm D path, or an EDIT to
     an existing registry record makes ``main()`` return 1 and print FAIL.
  2. PERMISSION. A lane workspace path, and an APPEND to a registry, make ``main()`` return 0.
     Rejection tests alone are worthless: a guard that rejects everything passes all of them.
  3. BYTE IDENTITY. feature_gate.py, comparison_gate.py and gate_invocation.py hash to exactly
     the values pinned in ``scripts/reconcile_repo.py:PINNED_CONTRACTS``.

Two anti-manufactured-negative measures, because this program has already produced one
manufactured negative from a silently-failing string match:

  * every "is permitted" assertion is paired with a near-miss path that MUST be rejected, so a
    guard that had simply stopped matching anything could not pass both halves;
  * the append-only harness serves the base revision through a stub, so the suite also runs
    REAL ``git show`` read-only against this repository and asserts the stub is faithful --
    including that ``git show`` on a nonexistent path really does return nonzero, which is the
    branch the guard treats as "new file".

No git state is mutated. No file outside a per-test temporary directory is written.
Standalone; no third-party imports; pytest is not required.

Run::

    python experiments/player_program/orchestration/tests/test_frozen_path_guard.py
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import graph_lib as G            # noqa: E402
import frozen_path_guard as FPG  # noqa: E402
import reconcile_repo as RR      # noqa: E402

REAL_REPO = G.REPO
ARM_REGISTRY = "experiments/player_program/arm_registry.jsonl"
PREREG_REGISTRY = "experiments/player_program/registry.jsonl"

FAILED: list[str] = []


def check(cond, msg):
    if not cond:
        FAILED.append(msg)
        print(f"  FAIL  {msg}")
    return bool(cond)


# ---------------------------------------------------------------- harness

def run_guard(argv, repo=None, fake_git=None):
    """Drive the guard's real main(). Returns (exit_code, captured_stdout).

    ``repo`` temporarily redirects graph_lib.REPO so the append-only tests can operate on a
    throwaway tree instead of this repository. ``fake_git`` swaps the module-local handle the
    guard uses to fetch the base revision; it is never installed into the real subprocess
    module, and both are restored unconditionally.
    """
    buf = io.StringIO()
    old_argv, old_repo, old_sub = sys.argv, G.REPO, FPG.subprocess
    sys.argv = ["frozen_path_guard.py"] + list(argv)
    if repo is not None:
        G.REPO = Path(repo)
    if fake_git is not None:
        FPG.subprocess = fake_git
    try:
        with contextlib.redirect_stdout(buf):
            rc = FPG.main()
    finally:
        sys.argv, G.REPO, FPG.subprocess = old_argv, old_repo, old_sub
    return rc, buf.getvalue()


class FakeGit:
    """Stands in for the ``subprocess`` module as the guard uses it: ``git show BASE:PATH``.

    Faithfulness to real git is not assumed -- it is asserted, in
    test_the_append_only_harness_matches_real_git.
    """

    def __init__(self, contents):
        self.contents = dict(contents)   # {"BASE:PATH": text or None}
        self.calls: list[list[str]] = []

    def run(self, argv, **kwargs):
        self.calls.append(list(argv))
        if argv[:2] != ["git", "show"]:
            raise AssertionError(f"harness saw an unexpected command: {argv}")
        text = self.contents.get(argv[2])
        if text is None:
            return subprocess.CompletedProcess(
                argv, 128, "", f"fatal: path exists on disk, but not in the given revision\n")
        return subprocess.CompletedProcess(argv, 0, text, "")


@contextlib.contextmanager
def registry_case(base_text, disk_text, rel=ARM_REGISTRY, base="HEAD"):
    """A throwaway tree holding ``disk_text`` at ``rel``, with ``base_text`` as its base revision.

    ``base_text=None`` means the path does not exist in the base revision (a brand-new file).
    ``disk_text=None`` means the working-tree file has been deleted.
    """
    with tempfile.TemporaryDirectory(prefix="fpg_") as tmp:
        target = Path(tmp) / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if disk_text is not None:
            with open(target, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(disk_text)
        yield tmp, FakeGit({f"{base}:{rel}": base_text})


def lines(*recs):
    return "".join(r + "\n" for r in recs)


BASE_RECORDS = [
    '{"arm": "D_ewma_shrunk", "k": 200, "alpha": 0.1}',
    '{"arm": "K0_MATCHED", "scope": "per_arm"}',
    '{"arm": "K0_FLAT", "scope": "diagnostic_only"}',
]
BASE_TEXT = lines(*BASE_RECORDS)


# ---------------------------------------------------------------- 1. rejection

FROZEN_DIR_CASES = [p + "some_new_artifact.parquet" for p in G.FROZEN_PREFIXES]

# Near-misses: a name that merely SHARES A PREFIX with a frozen directory is not frozen.
# If the guard degraded into "reject everything", these would fail and the suite would go red.
FROZEN_DIR_NEAR_MISSES = [
    "experiments/player_program/possessions_v3/x.parquet",
    "experiments/player_program/validation_v2/x.json",
    "experiments/player_program/discovery_wave_2/x.md",
    "experiments/player_program/fits_v1_notes.md",
]


def test_a_change_to_a_frozen_directory_is_rejected():
    check(len(G.FROZEN_PREFIXES) >= 12,
          f"expected >=12 frozen directories, graph_lib declares {len(G.FROZEN_PREFIXES)}")
    for p in FROZEN_DIR_CASES:
        rc, out = run_guard(["--paths", p])
        check(rc == 1, f"frozen directory must be REJECTED (exit 1), got {rc}: {p}")
        check("FAIL" in out and "frozen directory" in out,
              f"rejection must name the rule 'frozen directory': {p}")
        check("Severity A" in out, f"rejection must be reported at Severity A: {p}")
    for p in FROZEN_DIR_NEAR_MISSES:
        rc, out = run_guard(["--paths", p])
        check(rc == 0, f"a path that merely resembles a frozen directory must PASS: {p}")
    print(f"  ok    {len(FROZEN_DIR_CASES)} frozen directories rejected, "
          f"{len(FROZEN_DIR_NEAR_MISSES)} near-miss paths still permitted")


def test_a_change_to_a_frozen_file_is_rejected():
    # The two registries are frozen files too, but they are the append-only exemption: they
    # are routed to _append_only_ok instead of being rejected outright. They are covered by
    # test_an_edit_to_an_existing_registry_record_is_rejected.
    outright = [p for p in G.FROZEN_FILES if p not in FPG.APPEND_ONLY]
    check(len(outright) == len(G.FROZEN_FILES) - 2,
          "exactly the two registries are exempt from outright rejection")
    for p in outright:
        rc, out = run_guard(["--paths", p])
        check(rc == 1, f"frozen file must be REJECTED (exit 1), got {rc}: {p}")
    # The four shared contracts by name, so this criterion cannot pass vacuously if
    # FROZEN_FILES were ever emptied.
    for p in ("experiments/player_program/feature_gate.py",
              "experiments/player_program/comparison_gate.py",
              "experiments/player_program/gate_invocation.py",
              "experiments/player_program/receipt_integrity.py"):
        check(p in G.FROZEN_FILES, f"{p} must be declared frozen")
        rc, out = run_guard(["--paths", p])
        check(rc == 1 and "frozen file" in out, f"shared contract must be REJECTED: {p}")
    # Windows-style separators must not launder a frozen path past the guard.
    rc, out = run_guard(["--paths", r"experiments\player_program\feature_gate.py"])
    check(rc == 1, "a backslash-separated frozen path must still be REJECTED")
    print(f"  ok    {len(outright)} frozen files rejected outright, incl. backslash form; "
          f"{len(FPG.APPEND_ONLY)} registries routed to the append-only check")


def test_an_arm_d_path_is_rejected():
    arm_d = [
        "experiments/player_program/fits_v1/D_ewma_shrunk.json",
        "experiments/player_program/arm_incumbent.py",
        "experiments/player_program/stage2b/P38_BLINDED_FIT/D_ewma_shrunk_refit.json",
        "experiments/player_program/ops_lane/I10/copy_of_arm_incumbent.py",
        "experiments/player_program/product_lane/U11_UI_SHELL/D_ewma_shrunk_card.py",
        "experiments/player_program/orchestration/tests/D_ewma_shrunk_fixture.json",
    ]
    for p in arm_d:
        rc, out = run_guard(["--paths", p])
        check(rc == 1, f"Arm D path must be REJECTED (exit 1), got {rc}: {p}")
    # Only the first two of those are caught by a directory/file rule; the rest are caught
    # ONLY by the Arm D marker. Assert the marker rule is what fired.
    for p in arm_d[2:]:
        rc, out = run_guard(["--paths", p])
        check("Arm D marker" in out, f"must be rejected by the Arm D marker rule, not incidentally: {p}")
    # Near-miss: a different arm is not Arm D.
    for p in ("experiments/player_program/stage2b/P38_BLINDED_FIT/C_kalman.json",
              "experiments/player_program/stage2b/P38_BLINDED_FIT/arm_challenger.py"):
        rc, out = run_guard(["--paths", p])
        check(rc == 0, f"a non-Arm-D challenger path must PASS: {p}")
    check(G.ARM_D_MARKERS == ["D_ewma_shrunk", "arm_incumbent.py"],
          f"Arm D markers changed: {G.ARM_D_MARKERS}")
    print(f"  ok    {len(arm_d)} Arm D paths rejected, 2 non-Arm-D challenger paths permitted")


def test_an_edit_to_an_existing_registry_record_is_rejected():
    edited_first = lines("MUTATED" + BASE_RECORDS[0][7:], *BASE_RECORDS[1:])
    edited_mid = lines(BASE_RECORDS[0],
                       '{"arm": "K0_MATCHED", "scope": "global"}',
                       BASE_RECORDS[2])
    edited_last = lines(*BASE_RECORDS[:2],
                        '{"arm": "K0_FLAT", "scope": "authoritative"}')
    cases = [(edited_first, 1), (edited_mid, 2), (edited_last, 3)]
    for rel in (ARM_REGISTRY, PREREG_REGISTRY):
        for disk_text, idx in cases:
            with registry_case(BASE_TEXT, disk_text, rel=rel) as (tmp, git):
                rc, out = run_guard(["--paths", rel], repo=tmp, fake_git=git)
            check(rc == 1, f"an EDIT to existing record {idx} of {rel} must be REJECTED, got {rc}")
            check(f"existing record {idx} was EDITED" in out,
                  f"rejection must name the edited record; got: {out.strip()!r}")
            check("append-only" in out, "rejection must cite the append-only rule")
            check(git.calls and git.calls[0][:3] == ["git", "show", f"HEAD:{rel}"],
                  "the guard must fetch the base revision of the registry to compare")
    # An edit hidden behind an otherwise legitimate append is still an edit.
    sneaky = lines(BASE_RECORDS[0], '{"arm": "K0_MATCHED", "scope": "global"}',
                   BASE_RECORDS[2], '{"arm": "E_new", "prereg": "P37"}')
    with registry_case(BASE_TEXT, sneaky) as (tmp, git):
        rc, out = run_guard(["--paths", ARM_REGISTRY], repo=tmp, fake_git=git)
    check(rc == 1 and "existing record 2 was EDITED" in out,
          "an edit concealed inside a growing file must still be REJECTED")
    print("  ok    edits to records 1/2/3 of both registries rejected, incl. an edit hidden under an append")


def test_truncating_or_deleting_a_registry_is_rejected():
    truncated = lines(*BASE_RECORDS[:2])
    with registry_case(BASE_TEXT, truncated) as (tmp, git):
        rc, out = run_guard(["--paths", ARM_REGISTRY], repo=tmp, fake_git=git)
    check(rc == 1, "dropping a record must be REJECTED")
    check("record count fell from 3 to 2" in out, f"must report the record loss; got {out.strip()!r}")

    with registry_case(BASE_TEXT, None) as (tmp, git):
        rc, out = run_guard(["--paths", ARM_REGISTRY], repo=tmp, fake_git=git)
    check(rc == 1, "deleting the registry must be REJECTED")
    check("DELETED" in out, f"must report the deletion; got {out.strip()!r}")

    with registry_case(BASE_TEXT, "") as (tmp, git):
        rc, out = run_guard(["--paths", ARM_REGISTRY], repo=tmp, fake_git=git)
    check(rc == 1, "emptying the registry must be REJECTED")
    print("  ok    truncation, emptying and deletion of a registry all rejected")


def test_a_registry_append_does_not_mask_a_frozen_violation_in_the_same_change():
    appended = BASE_TEXT + '{"arm": "E_new", "prereg": "P37"}\n'
    with registry_case(BASE_TEXT, appended) as (tmp, git):
        rc, out = run_guard(
            ["--paths", ARM_REGISTRY, "experiments/player_program/feature_gate.py"],
            repo=tmp, fake_git=git)
    check(rc == 1, "a permitted append must not launder a frozen-file change in the same batch")
    check("NOTE" in out and "append-only OK" in out, "the append should still be reported as a NOTE")
    check("FAIL" in out and "feature_gate.py" in out, "the frozen file must still be named in a FAIL")
    check("1 frozen-path violation" in out, f"exactly one hard violation expected; got {out.strip()!r}")
    print("  ok    a legal append cannot mask an illegal frozen-file change")


# ---------------------------------------------------------------- 2. permission

LANE_WORKSPACES = [
    "experiments/player_program/orchestration/tests/test_frozen_path_guard.py",
    "experiments/player_program/orchestration/PROGRAM_GRAPH.json",
    "experiments/player_program/stage2b/P22_POSTGAME_SURROGATE_GUARD/REPORT.md",
    "experiments/player_program/data_lane/D10_FIELD_AVAILABILITY_LEDGER/FINDINGS.json",
    "experiments/player_program/product_lane/U11_UI_SHELL/app.py",
    "experiments/player_program/ops_lane/I10_GENERIC_CLUSTERED_INFERENCE/boot.py",
    "experiments/player_program/possession_features_v2/candidate.py",
]


def test_a_lane_workspace_path_is_permitted():
    for p in LANE_WORKSPACES:
        rc, out = run_guard(["--paths", p])
        check(rc == 0, f"lane workspace must be PERMITTED (exit 0), got {rc}: {p}")
        check("no frozen-path violation" in out, f"must report a clean verdict: {p}")
        check("FAIL" not in out, f"a permitted path must print no FAIL: {p}")
    rc, out = run_guard(["--paths"] + LANE_WORKSPACES)
    check(rc == 0, "the whole lane-workspace batch must be PERMITTED")
    check(f"{len(LANE_WORKSPACES)} changed path(s)" in out,
          f"the guard must account for every path it was handed; got {out.strip()!r}")
    print(f"  ok    {len(LANE_WORKSPACES)} lane workspace paths permitted, individually and as a batch")


def test_an_append_to_the_registry_is_permitted():
    one = BASE_TEXT + '{"arm": "E_new", "prereg": "P37"}\n'
    many = BASE_TEXT + lines('{"arm": "E_new", "prereg": "P37"}',
                             '{"arm": "F_new", "prereg": "P37"}')
    for rel in (ARM_REGISTRY, PREREG_REGISTRY):
        for disk_text, n_new in ((one, 4), (many, 5)):
            with registry_case(BASE_TEXT, disk_text, rel=rel) as (tmp, git):
                rc, out = run_guard(["--paths", rel], repo=tmp, fake_git=git)
            check(rc == 0, f"an APPEND to {rel} must be PERMITTED (exit 0), got {rc}")
            check(f"append-only OK: 3 -> {n_new} records" in out,
                  f"append must be reported with both counts; got {out.strip()!r}")
            check("NOTE" in out and "FAIL" not in out,
                  f"an append is a NOTE, never a FAIL; got {out.strip()!r}")
    # A no-op touch of the registry is also permitted.
    with registry_case(BASE_TEXT, BASE_TEXT) as (tmp, git):
        rc, out = run_guard(["--paths", ARM_REGISTRY], repo=tmp, fake_git=git)
    check(rc == 0 and "append-only OK: 3 -> 3 records" in out,
          "an unchanged registry must be PERMITTED")
    # A registry that does not exist in the base revision is a new file, not an edit.
    with registry_case(None, BASE_TEXT) as (tmp, git):
        rc, out = run_guard(["--paths", ARM_REGISTRY], repo=tmp, fake_git=git)
    check(rc == 0 and "new file" in out,
          f"a registry absent from the base revision must be PERMITTED as a new file; got {out.strip()!r}")
    print("  ok    appends of 1 and 2 records permitted on both registries; no-op and new-file permitted")


def test_an_empty_change_set_is_permitted():
    rc, out = run_guard(["--paths"])
    check(rc == 0 and "no changed paths" in out, f"an empty change set must PASS; got {out.strip()!r}")
    print("  ok    empty change set permitted")


# ------------------------------------------- 3. the harness itself is not lying

def _real_git_show(rev_path):
    return subprocess.run(["git", "show", rev_path], cwd=str(REAL_REPO),
                          capture_output=True, text=True)


def test_the_append_only_harness_matches_real_git():
    """Prove the stub's two branches are the branches real git actually produces.

    A negative is not evidence until the search that produced it is known to work. The
    "new file" branch of _append_only_ok keys off a nonzero return code from ``git show``;
    this asserts real git really does return nonzero for an absent path, and zero with
    content for a present one. Read-only: `git show` mutates nothing.
    """
    present = _real_git_show(f"HEAD:{ARM_REGISTRY}")
    check(present.returncode == 0,
          f"real git show must succeed for a tracked path (rc={present.returncode})")
    check(len(present.stdout.splitlines()) > 0, "the tracked registry has records at HEAD")

    absent = _real_git_show("HEAD:experiments/player_program/definitely_not_a_tracked_file.jsonl")
    check(absent.returncode != 0,
          "real git show must return NONZERO for an absent path -- this is the 'new file' branch")
    check(absent.stdout == "", "an absent path yields no stdout")

    stub = FakeGit({f"HEAD:{ARM_REGISTRY}": "a\nb\n"})
    hit = stub.run(["git", "show", f"HEAD:{ARM_REGISTRY}"], capture_output=True, text=True)
    miss = stub.run(["git", "show", "HEAD:nope"], capture_output=True, text=True)
    check(hit.returncode == 0 and hit.stdout == "a\nb\n", "stub hit mirrors real git: rc 0 + content")
    check(miss.returncode != 0 and miss.stdout == "",
          "stub miss mirrors real git: nonzero rc + empty stdout")
    print(f"  ok    real git show: rc 0 / {len(present.stdout.splitlines())} records present, "
          f"rc {absent.returncode} absent; stub matches both branches")


def test_the_guard_agrees_with_real_git_on_this_repository():
    """End-to-end, no stub: run the guard on the live registry with real git.

    The expected verdict is derived from the live tree rather than hard-coded, so this stays
    correct whether or not the registry has been appended to since HEAD.
    """
    head = _real_git_show(f"HEAD:{ARM_REGISTRY}")
    if head.returncode != 0:
        check(False, f"{ARM_REGISTRY} is not tracked at HEAD; cannot run the live comparison")
        return
    head_lines = head.stdout.splitlines()
    disk_path = REAL_REPO / ARM_REGISTRY
    if not disk_path.is_file():
        check(False, f"{ARM_REGISTRY} missing from the working tree")
        return
    disk_lines = disk_path.read_text(encoding="utf-8").splitlines()
    expect_ok = (len(disk_lines) >= len(head_lines)
                 and all(a == b for a, b in zip(head_lines, disk_lines)))

    rc, out = run_guard(["--paths", ARM_REGISTRY])
    check(rc == (0 if expect_ok else 1),
          f"guard verdict must match the independently computed one "
          f"(expected ok={expect_ok}, exit={rc})")
    if expect_ok:
        check(f"append-only OK: {len(head_lines)} -> {len(disk_lines)} records" in out,
              f"live counts must be reported; got {out.strip()!r}")
    print(f"  ok    live registry {len(head_lines)} -> {len(disk_lines)} records, "
          f"guard exit {rc}, agrees with an independent recomputation")


# ---------------------------------------------------------------- 4. byte identity

REQUIRED_CONTRACTS = [
    "experiments/player_program/feature_gate.py",
    "experiments/player_program/comparison_gate.py",
    "experiments/player_program/gate_invocation.py",
]


def test_the_shared_gates_are_byte_unchanged():
    pinned = RR.PINNED_CONTRACTS
    check(len(pinned) >= 3,
          f"reconcile_repo.PINNED_CONTRACTS must not be empty (has {len(pinned)}) -- "
          f"an empty pin set would make this whole test vacuous")
    for rel in REQUIRED_CONTRACTS:
        if not check(rel in pinned, f"{rel} must be pinned in reconcile_repo.PINNED_CONTRACTS"):
            continue
        path = REAL_REPO / rel
        if not check(path.is_file(), f"{rel} is missing from the working tree"):
            continue
        raw = path.read_bytes()
        actual = hashlib.sha256(raw).hexdigest()
        check(actual == pinned[rel],
              f"FROZEN ARTIFACT DIVERGED (Severity A): {rel} "
              f"expected {pinned[rel][:12]} actual {actual[:12]}")
        # The comparison must be capable of failing: one flipped byte must change the digest.
        check(hashlib.sha256(raw + b"\n").hexdigest() != actual,
              f"the hash comparison for {rel} cannot detect a change -- test is vacuous")
        print(f"  ok    {rel}  {len(raw)} bytes  {actual[:12]}")
    # receipt_integrity.py is frozen too; report it even though it is not in the criteria.
    extra = "experiments/player_program/receipt_integrity.py"
    if extra in pinned and (REAL_REPO / extra).is_file():
        actual = G.sha256_file(REAL_REPO / extra)
        check(actual == pinned[extra], f"FROZEN ARTIFACT DIVERGED (Severity A): {extra}")
        print(f"  ok    {extra}  {actual[:12]}  (beyond the stated criteria)")


def test_the_guard_and_its_frozen_lists_were_not_weakened():
    """The guard's own decision surface, asserted explicitly.

    A weakened list is the cheapest way to make a guard suite go green while the guard stops
    guarding. These assertions are what the mutation exercise (see REPORT) is checked against.
    """
    check(FPG.APPEND_ONLY == {ARM_REGISTRY, PREREG_REGISTRY},
          f"the append-only exemption must cover exactly the two registries: {FPG.APPEND_ONLY}")
    for rel in FPG.APPEND_ONLY:
        check(rel in G.FROZEN_FILES,
              f"{rel} is exempted as append-only but is not frozen -- it would never be inspected")
    check(len(G.FROZEN_PREFIXES) >= 12, "frozen directory list was shortened")
    check(len(G.FROZEN_FILES) >= 28, f"frozen file list was shortened to {len(G.FROZEN_FILES)}")
    check(all(p.endswith("/") for p in G.FROZEN_PREFIXES),
          "every frozen prefix must end in '/' or it would match sibling names by prefix")
    print(f"  ok    {len(G.FROZEN_PREFIXES)} frozen dirs, {len(G.FROZEN_FILES)} frozen files, "
          f"{len(G.ARM_D_MARKERS)} Arm D markers, {len(FPG.APPEND_ONLY)} append-only exemptions")


TESTS = [
    test_a_change_to_a_frozen_directory_is_rejected,
    test_a_change_to_a_frozen_file_is_rejected,
    test_an_arm_d_path_is_rejected,
    test_an_edit_to_an_existing_registry_record_is_rejected,
    test_truncating_or_deleting_a_registry_is_rejected,
    test_a_registry_append_does_not_mask_a_frozen_violation_in_the_same_change,
    test_a_lane_workspace_path_is_permitted,
    test_an_append_to_the_registry_is_permitted,
    test_an_empty_change_set_is_permitted,
    test_the_append_only_harness_matches_real_git,
    test_the_guard_agrees_with_real_git_on_this_repository,
    test_the_shared_gates_are_byte_unchanged,
    test_the_guard_and_its_frozen_lists_were_not_weakened,
]


def main():
    print("=" * 78)
    print("test_frozen_path_guard - the frozen-path guard must fail CLOSED")
    print("=" * 78)
    for fn in TESTS:
        print(f"\n--- {fn.__name__} ---")
        fn()
    print("\n" + "=" * 78)
    if FAILED:
        print(f"FAIL: {len(FAILED)} check(s)")
        for m in FAILED:
            print(f"  - {m}")
    else:
        print("PASS - all checks green")
    print("=" * 78)
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
