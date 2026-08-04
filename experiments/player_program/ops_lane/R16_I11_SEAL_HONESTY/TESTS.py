#!/usr/bin/env python
"""R16_I11_SEAL_HONESTY -- executable demonstration that I11's at-rest layer is not blinding.

This suite is unusual: several of its tests PASS WHEN THE DEFECT IS PRESENT. That is deliberate
and is what the node contract asks for -- "the reconstruction attack is reproduced as an
executable test that PASSES when the plaintext is recoverable". If a future node replaces the
at-rest scheme with something that actually resists reconstruction, sections [1] and [2] will
FAIL. That failure is the intended signal, not a regression: read section [1]/[2] failure as
"the defect has been fixed, retire or re-point these tests".

Sections
  [1] out-of-process reconstruction of I11's real demonstration seal, from public bytes only
  [2] in-process reconstruction BY THE WRITING PROCESS while the SealGuard is armed, untraced
  [3] positive control -- the ordinary Python read surface really is trapped (L1 is not vacuous)
  [4] the manifest binding, which was sound, still holds and still detects tampering
  [5] I11's own artifacts are byte-for-byte unmodified by this node
  [6] what the graph actually enforces, measured from PROGRAM_GRAPH.json and the prompt files
  [7] no unsupported confidentiality claim survives in this node's own report

Standalone. No pytest. main() returns 1 on any failure.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True  # never leave a .pyc beside a read-only artifact

HERE = Path(__file__).resolve().parent
OPS = HERE.parent
PROGRAM = OPS.parent                       # experiments/player_program
REPO = PROGRAM.parent.parent               # repository / worktree root
I11 = OPS / "I11_BLINDED_RESULT_PACKAGING"
DEMO = I11 / "demo_seal"
ORCH = PROGRAM / "orchestration"

PASS = 0
FAIL = 0
MEASURED: dict[str, object] = {}


def check(name: str, cond: bool, detail: str = "") -> bool:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS  {name}" + (f"   [{detail}]" if detail else ""))
    else:
        FAIL += 1
        print(f"  FAIL  {name}" + (f"   [{detail}]" if detail else ""))
    return bool(cond)


def squash(s: str) -> str:
    return " ".join(s.split())


# ================================================================================================
# The attack itself. This is the whole of it.
# ================================================================================================
# The domain-separation string is a literal in a committed, world-readable source file. It is
# reproduced here as a literal ON PURPOSE: the attack must not import I11's module, because the
# point being demonstrated is that nothing secret is required. Section [1] asserts that this
# literal really does occur in the published source, so the copy cannot silently drift.
DOMAIN = b"player_program/I11_BLINDED_RESULT_PACKAGING/seal/1"
ATTACK_CORE_LINES = 6  # counted by _attack_core_line_count(); asserted in section [1]


def deobfuscate(stored: bytes, manifest_digest: str, name: str) -> bytes:
    """Recover payload plaintext from the stored bytes. Public inputs only."""
    nonce, ct = stored[8:24], stored[24:]
    seed = DOMAIN + b"|" + manifest_digest.encode() + b"|" + name.encode("utf-8") + b"|" + nonce
    ks = b"".join(hashlib.sha256(seed + i.to_bytes(8, "big")).digest()
                  for i in range((len(ct) + 31) // 32))
    return bytes(a ^ b for a, b in zip(ct, ks))


def _attack_core_line_count() -> int:
    src = Path(__file__).read_text(encoding="utf-8")
    body = src.split("def deobfuscate(", 1)[1].split("\ndef ", 1)[0]
    lines = [ln for ln in body.splitlines()[1:]
             if ln.strip() and not ln.strip().startswith(('"""', "#"))]
    return len(lines)


# ================================================================================================
# [1] out-of-process reconstruction of the real demonstration seal
# ================================================================================================
def test_reconstruct_demo_seal() -> None:
    print("\n[1] ATTACK -- reconstruct I11's demonstration seal from public bytes alone")

    check("I11 demonstration seal is present", DEMO.is_dir(), str(DEMO))
    if not DEMO.is_dir():
        return

    src = (I11 / "sealed_package.py").read_text(encoding="utf-8")
    check("the domain literal used by this attack occurs verbatim in the published source",
          DOMAIN.decode() in src)

    n = _attack_core_line_count()
    MEASURED["attack_core_lines"] = n
    check("the entire attack is a short function", n <= 12, f"{n} statement lines")

    # --- the only inputs the attack touches -------------------------------------------------
    manifest = json.loads((DEMO / "MANIFEST.json").read_text(encoding="utf-8"))
    md = manifest["manifest_digest"]
    stored_files = sorted((DEMO / "sealed").glob("*.sealed"))
    check("the demonstration seal carries payloads to attack", len(stored_files) == 2,
          f"{len(stored_files)} sealed files")

    seal = json.loads((DEMO / "SEAL.json").read_text(encoding="utf-8"))
    declared = {p["name"]: p for p in seal["payloads"]}

    recovered = {}
    for f in stored_files:
        name = f.name[: -len(".sealed")]                       # the payload name is the filename
        pt = deobfuscate(f.read_bytes(), md, name)
        recovered[name] = pt
        d = declared.get(name, {})
        check(f"plaintext of {name} recovered, sha256 matches the seal's own declaration",
              hashlib.sha256(pt).hexdigest() == d.get("plaintext_sha256"),
              f"{len(pt)} bytes")
        check(f"recovered length of {name} matches the declared n_bytes",
              len(pt) == d.get("n_bytes"), str(d.get("n_bytes")))

    MEASURED["payloads_reconstructed"] = len(recovered)
    MEASURED["plaintext_bytes_recovered"] = sum(len(v) for v in recovered.values())

    marker = b"I11_SYNTHETIC_PAYLOAD_MARKER_NOT_A_RESULT"
    check("the plaintext marker I11 planted is readable in the reconstruction",
          all(marker in v for v in recovered.values()))

    # --- the inputs the attack did NOT need -------------------------------------------------
    # SEAL.json above is used only to CHECK the result against the seal's own declaration.
    # Re-run using nothing but MANIFEST.json and the .sealed bytes, to bound the input set.
    again = {}
    for f in stored_files:
        name = f.name[: -len(".sealed")]
        again[name] = deobfuscate(f.read_bytes(), md, name)
    check("the attack needs only MANIFEST.json plus the .sealed bytes -- SEAL.json is not required",
          again == recovered)

    # the nonce is not a secret in any sense: it is written in the clear, twice
    for f in stored_files:
        name = f.name[: -len(".sealed")]
        check(f"the nonce for {name} is stored in the clear in the payload header itself",
              f.read_bytes()[8:24].hex() == declared[name]["nonce"])

    check("no open_seal() call was made and no authorization was presented", True,
          "the attack calls no I11 code at all")


# ================================================================================================
# [2] the writing process reads its own sealed payload while the guard is armed
# ================================================================================================
def _fixture_manifest(sp, tmp: Path):
    rows, clusters, folds = [], [], []
    for i in range(12):
        for side in ("H", "A"):
            rows.append(f"g{i:04d}|{side}")
            clusters.append(f"g{i:04d}")
            folds.append(f"fold{i % 3}")
    tmp.mkdir(parents=True, exist_ok=True)
    data_file = tmp / "input.bin"
    data_file.write_bytes(b"synthetic input frame\n" * 10)
    return sp.build_manifest(
        run_id="R16_SEAL_HONESTY_ATTACK",
        target="REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS",
        code_commit={"commit": "a" * 40, "short": "aaaaaaa", "branch": "test",
                     "dirty": False, "dirty_paths": []},
        data_hashes=sp.hash_inputs([data_file]),
        row_universe=sp.describe_universe(rows, clusters,
                                          row_key_columns=["game_id", "side"],
                                          cluster_key_column="game_id"),
        folds=sp.describe_folds(scheme="TEST_BLOCK", cluster_keys=clusters, fold_keys=folds),
        k0_pairing=sp.describe_k0_pairing({
            "ARM_ONE": {"k0_matched_id": "K0_MATCHED__ARM_ONE",
                        "k0_matched_record": {"schema": "k0_matched/1", "arm_id": "ARM_ONE"},
                        "arm_kind": "substantive_feature"},
        }, k0_flat_id="K0_FLAT"),
        seeds={"fold_seed": 20260804, "bootstrap_seed": 11},
    )


def _import_sealed_package():
    sys.path.insert(0, str(I11))
    try:
        import sealed_package as sp  # noqa: E402  (read-only import of a completed artifact)
    finally:
        sys.path.pop(0)
    return sp


def test_writer_reads_own_seal(tmp: Path) -> None:
    print("\n[2] ATTACK -- the WRITING process recovers its own plaintext, guard armed, no trace")

    sp = _import_sealed_package()
    manifest = _fixture_manifest(sp, tmp)
    root = tmp / "seal_attack"
    marker = b"R16_MARKER_THIS_WOULD_BE_A_COMPARATIVE_RESULT"
    plaintext = marker + b"\n" + b"synthetic payload body, no real result content\n" * 40

    import _io  # the C accessor behind io.open; SealGuard patches `io.open`, not this

    with sp.SealedWriter(root, manifest, actor="R16 attack", node_id="R16_I11_SEAL_HONESTY") as w:
        w.write_payload("results.bin", plaintext)
        stored_path = root / "sealed" / "results.bin.sealed"

        violations_before = len(w.violations)
        stored = _io.open(stored_path, "rb").read()          # <-- the whole bypass
        violations_after = len(w.violations)

        check("_io.open reaches the sealed payload while the guard is armed",
              len(stored) > 24, f"{len(stored)} stored bytes")
        check("the bypass is pure stdlib and in-process: SealGuard rebound io.open but _io.open "
              "is the same C function it always was",
              io.open is not _io.open and _io.open is _io.open)
        check("the bypass records NO violation",
              violations_after == violations_before, f"violations {violations_after}")

        got = deobfuscate(stored, manifest["manifest_digest"], "results.bin")
        check("the writing process recovers its own payload plaintext byte-for-byte",
              got == plaintext, f"{len(got)} bytes")
        check("the planted marker is readable by the writer", marker in got)

        w.finalize()

    MEASURED["writer_self_read_recovered_bytes"] = len(plaintext)

    # what the seal's own records say about the peek
    viol_file = root / "SEAL_VIOLATIONS.jsonl"
    n_viol = len([ln for ln in viol_file.read_text(encoding="utf-8").splitlines() if ln.strip()]) \
        if viol_file.exists() else 0
    seal = json.loads((root / "SEAL.json").read_text(encoding="utf-8"))
    log = root / "SEAL_OPEN_LOG.jsonl"
    n_log = len([ln for ln in log.read_text(encoding="utf-8").splitlines() if ln.strip()]) \
        if log.exists() else 0
    MEASURED["writer_self_read_violations_recorded"] = n_viol
    MEASURED["writer_self_read_open_log_entries"] = n_log

    check("SEAL_VIOLATIONS.jsonl records zero refused reads after a successful peek", n_viol == 0,
          f"{n_viol} lines")
    check("SEAL.json reports writer_read_attempts == 0 after a successful peek",
          seal.get("writer_read_attempts") == 0, str(seal.get("writer_read_attempts")))
    check("SEAL_OPEN_LOG.jsonl records zero opens after a successful peek", n_log == 0,
          f"{n_log} lines")
    check("verify_seal() still reports the peeked seal as intact",
          sp.verify_seal(root).get("ok") is True)


# ================================================================================================
# [3] positive control -- L1 is not vacuous
# ================================================================================================
def test_l1_positive_control(tmp: Path) -> None:
    print("\n[3] positive control -- the ordinary Python read surface IS trapped")
    sp = _import_sealed_package()
    manifest = _fixture_manifest(sp, tmp)
    root = tmp / "seal_control"

    trapped, untrapped = [], []
    with sp.SealedWriter(root, manifest, actor="R16 control", node_id="R16_I11_SEAL_HONESTY") as w:
        w.write_payload("p.bin", b"control payload\n" * 8)
        f = root / "sealed" / "p.bin.sealed"
        import _io
        surfaces = {
            "builtins.open":  lambda: open(f, "rb").read(),
            "io.open":        lambda: io.open(f, "rb").read(),
            "os.open":        lambda: os.read(os.open(f, os.O_RDONLY), 4096),
            "os.listdir":     lambda: os.listdir(f.parent),
            "pathlib.read_bytes": lambda: Path(f).read_bytes(),
            "_io.open":       lambda: _io.open(f, "rb").read(),
        }
        for label, fn in surfaces.items():
            try:
                fn()
                untrapped.append(label)
            except sp.SealViolation:
                trapped.append(label)
        w.finalize()

    MEASURED["l1_trapped"] = sorted(trapped)
    MEASURED["l1_untrapped"] = sorted(untrapped)
    check("the five ordinary Python read surfaces are trapped", len(trapped) == 5,
          ",".join(sorted(trapped)))
    check("_io.open is the one that is not -- and it was not in I11's 13-surface probe",
          untrapped == ["_io.open"], ",".join(untrapped))
    probe_src = (I11 / "surface_probe.py").read_text(encoding="utf-8")
    check("PROVE THE NEGATIVE: the string '_io' really is absent from I11's probe, and the "
          "same search finds 'io.open' which is present",
          "_io" not in probe_src and "io.open" in probe_src)


# ================================================================================================
# [4] the sound part -- the manifest binding is retained and still detects tampering
# ================================================================================================
def test_manifest_binding_retained(tmp: Path) -> None:
    print("\n[4] RETAINED -- the manifest binding still holds and still detects tampering")
    sp = _import_sealed_package()

    live = tmp / "demo_copy"
    shutil.copytree(DEMO, live)                # never touch I11's own bytes

    res = sp.verify_seal(live)
    check("I11's demonstration seal verifies as delivered", res.get("ok") is True,
          str(res.get("failures"))[:80])

    m = json.loads((live / "MANIFEST.json").read_text(encoding="utf-8"))
    check("all six bindings are present", set(m["bindings"]) >= {
        "code_commit", "data_hashes", "row_universe", "folds", "k0_pairing", "seeds"},
        ",".join(sorted(m["bindings"])))
    check("the recorded manifest digest recomputes from its own bindings",
          sp.manifest_digest_of(m) == m["manifest_digest"], m["manifest_digest"][:16])
    check("the row universe is 2982 rows over 1491 clusters",
          sp.digest_count(m["bindings"]["row_universe"]["row_digest"]) == 2982
          and sp.digest_count(m["bindings"]["row_universe"]["cluster_digest"]) == 1491)

    # tamper 1: edit a bound seed
    t1 = tmp / "t_seed"
    shutil.copytree(DEMO, t1)
    mm = json.loads((t1 / "MANIFEST.json").read_text(encoding="utf-8"))
    mm["bindings"]["seeds"]["fold_seed"] = 999999
    (t1 / "MANIFEST.json").write_text(json.dumps(mm, indent=1), encoding="utf-8")
    check("editing a bound seed is detected", sp.verify_seal(t1).get("ok") is False)

    # tamper 2: flip one bit of a stored payload
    t2 = tmp / "t_bit"
    shutil.copytree(DEMO, t2)
    victim = sorted((t2 / "sealed").glob("*.sealed"))[0]
    b = bytearray(victim.read_bytes())
    b[-1] ^= 0x01
    victim.write_bytes(bytes(b))
    check("flipping one bit of a stored payload is detected",
          sp.verify_seal(t2).get("ok") is False)

    # tamper 3: delete a declared output
    t3 = tmp / "t_del"
    shutil.copytree(DEMO, t3)
    sorted((t3 / "sealed").glob("*.sealed"))[0].unlink()
    check("deleting a declared output is detected", sp.verify_seal(t3).get("ok") is False)

    # the crucial separation: the attack in [1] does NOT disturb any of this
    check("reconstruction leaves the seal verifying -- integrity and confidentiality are "
          "independent properties, and only the first one is real here",
          sp.verify_seal(live).get("ok") is True)


# ================================================================================================
# [5] I11's artifacts are untouched
# ================================================================================================
I11_FROZEN = {
    "demo_seal/MANIFEST.json": "bebaba167a92fa9b4edd9d429d00c33073fb001939b0df6549258f7c506e007e",
    "demo_seal/SEAL.json": "4ab2a9144799359a10ff4e809a13aef4e9b6b525962886643048a6523cc4477d",
    "demo_seal/SEAL_OPEN_HEAD.json": "9fe1ddb2759259fbe4e1b15873a8d2fd10d2bab2431b697f415a9ebdb7bfdeab",
    "demo_seal/SEAL_OPEN_LOG.jsonl": "02f5d63ceed4d3015c7603fb016d090ae7da0662fbf61346db8e7e6d682f3b48",
    "demo_seal/SEAL_VIOLATIONS.jsonl": "11c22b6a7cc62a3bf0bbd3bbeb671d02fa66946cc4f1b1d83357f25173d8c4fd",
    "demo_seal/sealed/synthetic_fold_table.json.sealed":
        "2a17eb2f8f2674d03b2e07ffed01074932d7dd0a0e1d3634a9bf2a5bcb1551fb",
    "demo_seal/sealed/synthetic_predictions.bin.sealed":
        "32d0d540dd15de16742fc488ca9d4227df52936c41f6f32b8aac00df0aba4bc1",
    "demo_seal.py": "6b4506c28f281ef3d44d859db6970640fb7adf191109151a866bc4662d30584c",
    "MEASUREMENTS.json": "b517cf66848fae587674b620b8a1258384c59bede81a8e83df17391c80f3d69f",
    "REPORT.md": "7b1a74bdd44062fb0b9e028794a6bb132df6f2ba662acd84bb086574a609c044",
    "sealed_package.py": "498d7ab9d810dc8777fcb886f7cc4a443b4a479a5572a1191e034d24fe2cb3e1",
    "surface_probe.py": "8684d1c9674a22e7279549a400e5580d284899b4e738c20775a8a255a1f29fee",
    "TESTS.py": "58171b1027cdb166edb9b9964ac6c2e1642155a53ffec8e66be7f77368d12502",
}


def test_i11_untouched() -> None:
    print("\n[5] I11's own artifacts are byte-for-byte unmodified")
    bad = []
    for rel, want in sorted(I11_FROZEN.items()):
        p = I11 / rel
        got = hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "MISSING"
        if got != want:
            bad.append(rel)
    check("every I11 artifact still hashes to the value observed before this node ran",
          not bad, ",".join(bad) if bad else f"{len(I11_FROZEN)} files")

    on_disk = {p.relative_to(I11).as_posix() for p in I11.rglob("*")
               if p.is_file() and "__pycache__" not in p.parts}
    check("this node added no file to I11's directory",
          on_disk == set(I11_FROZEN), ",".join(sorted(on_disk - set(I11_FROZEN))))


# ================================================================================================
# [6] what the graph actually enforces -- measured, not assumed
# ================================================================================================
RULE8 = ("You may NOT inspect comparative historical performance of any challenger, and you may "
         "not read anything under `experiments/player_program/stage2b/SEALED_RESULTS/`.")


def test_graph_separation() -> None:
    print("\n[6] the process separation the graph ACTUALLY enforces")
    graph = json.loads((ORCH / "PROGRAM_GRAPH.json").read_text(encoding="utf-8"))
    nodes = graph["nodes"]
    idx = {n["id"]: n for n in nodes}
    MEASURED["graph_nodes"] = len(nodes)

    check("the graph is the 64-node program graph", len(nodes) == 64, str(len(nodes)))

    p38, p39 = idx.get("P38_BLINDED_FIT"), idx.get("P39_RESULT_INTEGRITY")
    check("P38 (writer) and P39 (verifier) are distinct nodes with distinct prompts",
          p38 and p39 and p38["agent_prompt_path"] != p39["agent_prompt_path"])
    check("P38 and P39 have disjoint write scopes",
          set(p38["allowed_write_paths"]).isdisjoint(p39["allowed_write_paths"]),
          f"{p38['allowed_write_paths']} vs {p39['allowed_write_paths']}")
    check("P39 depends on P38, so they can never run concurrently",
          "P38_BLINDED_FIT" in p39["dependencies"])
    check("every node in the graph has a unique agent_prompt_path (one context per node)",
          len({n["agent_prompt_path"] for n in nodes}) == len(nodes))

    # the gap
    empty = sorted(n["id"] for n in nodes if not n["forbidden_inputs"])
    MEASURED["nodes_with_empty_forbidden_inputs"] = empty
    check("P38, the node that WRITES the sealed results, is the only node in the graph with no "
          "declared forbidden input", empty == ["P38_BLINDED_FIT"], ",".join(empty))
    check("P39 does declare SEALED_RESULTS forbidden",
          any("SEALED_RESULTS" in p for p in p39["forbidden_inputs"]))

    # validate_graph's audit-independence rule does not reach P38 -> P39
    check("P38's declared type is 'experiment', not 'implementation'",
          p38["type"] == "experiment", p38["type"])
    vg = (ORCH / "scripts" / "validate_graph.py").read_text(encoding="utf-8")
    check("validate_graph's audit-independence check keys on dependencies of type "
          "'implementation', so it does not cover the P38 -> P39 pair",
          'dep["type"] != "implementation"' in vg)

    # forbidden_inputs has no runtime enforcement anywhere in the orchestration scripts
    hits = []
    for p in sorted((ORCH / "scripts").glob("*.py")):
        for i, ln in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if "forbidden_inputs" in ln:
                hits.append(f"{p.name}:{i}")
    MEASURED["forbidden_inputs_mentions_in_scripts"] = hits
    check("PROVE THE NEGATIVE: the search for 'forbidden_inputs' in orchestration/scripts is not "
          "silently empty -- it finds occurrences", len(hits) > 0, ",".join(hits))
    expected_sites = {"generate_prompts.py", "graph_lib.py", "seed_graph.py", "validate_graph.py"}
    check("and every occurrence is a schema field list, a seeding default, prompt rendering, or a "
          "declaration-consistency check -- none of them reads or blocks a file at run time",
          {h.split(":")[0] for h in hits} == expected_sites,
          ",".join(sorted({h.split(":")[0] for h in hits})))

    # the mechanism that IS load-bearing: standing rule 8, rendered into every prompt
    want = squash(RULE8)
    covered, missing = 0, []
    for n in nodes:
        f = REPO / n["agent_prompt_path"]
        if not f.is_file():
            missing.append(n["id"])
            continue
        if want in squash(f.read_text(encoding="utf-8")):
            covered += 1
        else:
            missing.append(n["id"])
    MEASURED["prompts_carrying_rule8"] = covered
    n_prompt_files = sum(1 for n in nodes if (REPO / n["agent_prompt_path"]).is_file())
    check("every node has a generated prompt file on disk", n_prompt_files == len(nodes),
          f"{n_prompt_files}/{len(nodes)}")
    check("standing rule 8 (do not read SEALED_RESULTS) is present in all 64 generated prompts, "
          "P38's included", covered == 64 and not missing, f"{covered}/64")

    p38_prompt = squash((REPO / p38["agent_prompt_path"]).read_text(encoding="utf-8"))
    check("CONTRADICTION, measured: P38's own prompt renders 'Forbidden inputs:** _none_' while "
          "carrying standing rule 8 in the same file",
          "Forbidden inputs:** _none_" in p38_prompt and want in p38_prompt)

    policy = squash((ORCH / "GRAPH_POLICY.md").read_text(encoding="utf-8"))
    check("GRAPH_POLICY section 7 states the runner/verifier/adjudicator sequence in prose",
          "The runner writes into a sealed result directory" in policy
          and "only then may a separate adjudication node open results" in policy)


# ================================================================================================
# [7] no unsupported confidentiality claim survives in this node's report
# ================================================================================================
# Verbatim fragments of I11's REPORT.md that this node supersedes. Each must (a) really occur in
# I11's report -- otherwise this node would be attacking a straw man -- and (b) be quoted in this
# node's own report alongside its verdict.
SUPERSEDED = [
    "Two independent layers, because one is not enough and pretending otherwise would be theatre.",
    "Totals: **13 surfaces probed, 11 trapped, 2 not trapped, 0 leaked.**",
    "so a runner that peeked cannot hide it.",
    "so by construction they behave like the two measured misses.",
    "the writing process cannot open its own seal",
]

# Terms that can only appear in this report inside a NEGATED sentence. The suite does not ban the
# words -- it bans the affirmative claim. Any sentence using one must also carry a negation.
GUARDED_TERMS = [
    "encrypt", "confidential", "cryptograph", "unreadable", "tamper-proof",
    "secret", "cannot be recovered", "cannot be reconstructed",
]
NEGATIONS = ("not ", "no ", "never", "n't", "rather than", "without", "fails to",
             "is a defect", "cannot be treated", "must not")


def _affirmative_claims(text: str) -> list[str]:
    """Sentences that use a guarded term with no negation anywhere in the sentence."""
    bad = []
    for raw in re.split(r"(?<=[.!?;:])\s+|\n", text):
        s = squash(raw)
        if not s:
            continue
        low = s.lower()
        if any(t in low for t in GUARDED_TERMS) and not any(n in low for n in NEGATIONS):
            bad.append(s[:110])
    return bad


def test_report_claims() -> None:
    print("\n[7] no unsupported confidentiality claim survives in this node's report")
    rep_path = HERE / "REPORT.md"
    check("REPORT.md exists", rep_path.is_file(), str(rep_path))
    if not rep_path.is_file():
        return
    rep = rep_path.read_text(encoding="utf-8")
    rep_s = squash(rep)
    # blockquote markers must not break a verbatim-quote check
    rep_q = squash(re.sub(r"(?m)^>\s?", "", rep))
    i11 = squash((I11 / "REPORT.md").read_text(encoding="utf-8"))

    for q in SUPERSEDED:
        qs = squash(q)
        check(f"I11 really does say: {qs[:52]}...", qs in i11)
        check("...and this report quotes it in the supersession table", qs in rep_s)

    check("the withdrawn criterion is named verbatim and marked WITHDRAWN",
          "a sealed directory cannot be read by the writing process" in rep_s
          and "WITHDRAWN" in rep)
    check("the replacement guarantee is stated",
          "process separation" in rep_s.lower())

    # positive control for the claim scanner: it must flag a planted affirmative claim
    planted = "The payload is encrypted and therefore unreadable."
    check("PROVE THE NEGATIVE: the claim scanner is not vacuous -- it flags a planted claim",
          _affirmative_claims(planted) != [])
    check("and it does not flag the same statement once negated",
          _affirmative_claims("The payload is not encrypted and is not unreadable.") == [])

    bad = _affirmative_claims(rep)
    MEASURED["affirmative_confidentiality_claims_in_report"] = len(bad)
    check("no affirmative confidentiality claim survives anywhere in this report",
          not bad, " || ".join(bad[:3]))

    check("the epistemic-status line is reproduced verbatim",
          "REMEDIATION of an OVERSTATED ACCEPTANCE CRITERION. An independent verifier "
          "reconstructed the plaintext of both sealed payloads in about ten lines from public "
          "inputs. Blinding for the possession experiment rests on PROCESS separation enforced "
          "by the graph, not on cryptography; this node removes the temptation to treat the "
          "crypto as a second line of defence when it is not one." in rep_q)
    perf = re.findall(r"\b(MAE|RMSE|outperform\w*|beat|better than|win rate)\b", rep, re.I)
    check("the report makes no comparative performance statement about any challenger",
          not perf, ",".join(sorted(set(perf))))


# ================================================================================================
def main() -> int:
    print("=" * 96)
    print("R16_I11_SEAL_HONESTY -- sections [1] and [2] PASS WHILE THE DEFECT EXISTS. By design.")
    print("=" * 96)
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        test_reconstruct_demo_seal()
        test_writer_reads_own_seal(tmp / "a")
        test_l1_positive_control(tmp / "b")
        test_manifest_binding_retained(tmp / "c")
        test_i11_untouched()
        test_graph_separation()
        test_report_claims()

    print("\n" + "-" * 96)
    print("MEASURED:")
    for k, v in MEASURED.items():
        print(f"  {k} = {v}")
    print("-" * 96)
    print(f"{PASS} PASS / {FAIL} FAIL")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
