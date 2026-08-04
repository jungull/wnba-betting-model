"""I11_BLINDED_RESULT_PACKAGING -- tests for sealed_package.py. Standalone; no pytest.

    python TESTS.py

Returns 1 on any failure. Writes only into a temporary directory, which it removes.
"""
from __future__ import annotations

import io
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import sealed_package as sp                                      # noqa: E402
from surface_probe import MUST_TRAP, TRAPPED, probe_surfaces     # noqa: E402

FAILURES: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(("  PASS  " if cond else "  FAIL  ") + name + (("  -- " + detail) if detail else ""))
    if not cond:
        FAILURES.append(name)


def raises(name: str, exc, fn, *a, **k) -> None:
    try:
        fn(*a, **k)
    except exc as e:
        check(name, True, type(e).__name__)
        return
    except Exception as e:  # noqa: BLE001
        check(name, False, f"raised {type(e).__name__} instead of {exc.__name__}: {e}")
        return
    check(name, False, "no exception raised")


# --------------------------------------------------------------------------------------------
# fixtures -- a small synthetic universe with the same SHAPE as the real one:
# 2 rows per cluster, clusters never split across folds.
# --------------------------------------------------------------------------------------------

def fixture_universe(n_clusters: int = 12):
    rows, clusters, folds = [], [], []
    for i in range(n_clusters):
        for side in ("H", "A"):
            rows.append(f"g{i:04d}|{side}")
            clusters.append(f"g{i:04d}")
            folds.append(f"fold{i % 3}")
    return rows, clusters, folds


def fixture_bindings(tmp: Path):
    rows, clusters, folds = fixture_universe()
    data_file = tmp / "input.bin"
    data_file.write_bytes(b"synthetic input frame\n" * 10)
    return {
        "run_id": "TEST_RUN_1",
        "target": "REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS",
        "code_commit": {"commit": "a" * 40, "short": "aaaaaaa", "branch": "test",
                        "dirty": False, "dirty_paths": []},
        "data_hashes": sp.hash_inputs([data_file]),
        "row_universe": sp.describe_universe(rows, clusters,
                                             row_key_columns=["game_id", "side"],
                                             cluster_key_column="game_id"),
        "folds": sp.describe_folds(scheme="TEST_BLOCK", cluster_keys=clusters, fold_keys=folds),
        "k0_pairing": sp.describe_k0_pairing({
            "ARM_ONE": {"k0_matched_id": "K0_MATCHED__ARM_ONE",
                        "k0_matched_record": {"schema": "k0_matched/1", "arm_id": "ARM_ONE"},
                        "arm_kind": "substantive_feature"},
            "ARM_TWO": {"k0_matched_id": "K0_MATCHED__ARM_TWO",
                        "k0_matched_record": {"schema": "k0_matched/1", "arm_id": "ARM_TWO"},
                        "arm_kind": "calibration_only"},
        }, k0_flat_id="K0_FLAT"),
        "seeds": {"fold_seed": 20260804, "bootstrap_seed": 11},
    }


# --------------------------------------------------------------------------------------------
# 1. the manifest binds all six, and every one is mandatory
# --------------------------------------------------------------------------------------------
def test_manifest_requires_six(tmp: Path) -> None:
    print("\n[1] the manifest binds code commit, data hashes, row universe, folds, K0, seeds")
    b = fixture_bindings(tmp)
    m = sp.build_manifest(**b)
    check("manifest builds with all six", m["manifest_digest"] is not None)
    for name in sp.REQUIRED_BINDINGS:
        bad = dict(b)
        bad[name] = {}
        raises(f"omitting {name} is refused", sp.ManifestError, sp.build_manifest, **bad)
    present = set(m["bindings"])
    check("all six bindings present in the manifest", present == set(sp.REQUIRED_BINDINGS),
          str(sorted(present)))
    check("digest covers the bindings block", "bindings" in m["digest_covers"])
    check("digest does NOT cover created_at", "created_at" not in m["digest_covers"])
    raises("run_id required", sp.ManifestError, sp.build_manifest, **{**b, "run_id": ""})
    raises("target required", sp.ManifestError, sp.build_manifest, **{**b, "target": ""})


def test_digest_binds(tmp: Path) -> None:
    print("\n[2] altering any bound field changes the manifest digest")
    b = fixture_bindings(tmp)
    base = sp.build_manifest(**b)["manifest_digest"]
    again = sp.build_manifest(**b)["manifest_digest"]
    check("digest is deterministic across rebuilds", base == again, base[:16])

    rows, clusters, folds = fixture_universe()
    mutations = {
        "code_commit": {**b["code_commit"], "commit": "b" * 40},
        "data_hashes": {"other.bin": {"sha256": "c" * 64, "n_bytes": 1}},
        "row_universe": sp.describe_universe(rows[:-2], clusters[:-2],
                                             row_key_columns=["game_id", "side"],
                                             cluster_key_column="game_id"),
        "folds": sp.describe_folds(scheme="OTHER_BLOCK", cluster_keys=clusters, fold_keys=folds),
        "k0_pairing": sp.describe_k0_pairing({
            "ARM_ONE": {"k0_matched_id": "K0_MATCHED__ARM_ONE_v2",
                        "k0_matched_record": {"schema": "k0_matched/1", "arm_id": "ARM_ONE"},
                        "arm_kind": "substantive_feature"}}),
        "seeds": {"fold_seed": 20260804, "bootstrap_seed": 12},
    }
    for name, val in mutations.items():
        alt = dict(b)
        alt[name] = val
        if name == "row_universe":
            alt["folds"] = sp.describe_folds(scheme="TEST_BLOCK", cluster_keys=clusters[:-2],
                                             fold_keys=folds[:-2])
        d = sp.build_manifest(**alt)["manifest_digest"]
        check(f"changing {name} changes the digest", d != base)

    m = sp.build_manifest(**b)
    check("manifest_digest_of() reproduces the stored digest",
          sp.manifest_digest_of(m) == m["manifest_digest"])
    tampered = json.loads(json.dumps(m))
    tampered["bindings"]["seeds"]["fold_seed"] = 999
    check("tampering with a binding is detectable by recomputation",
          sp.manifest_digest_of(tampered) != tampered["manifest_digest"])


# --------------------------------------------------------------------------------------------
# 3. structural invariants the manifest refuses to record
# --------------------------------------------------------------------------------------------
def test_fold_cluster_integrity() -> None:
    print("\n[3] a game may never be split across folds")
    rows, clusters, folds = fixture_universe()
    ok = sp.describe_folds(scheme="TEST_BLOCK", cluster_keys=clusters, fold_keys=folds)
    check("clean assignment is accepted", ok["cluster_split_check"].startswith("PASS"))
    check("fold row counts sum to the universe",
          sum(f["n_rows"] for f in ok["folds"]) == len(rows))
    split = list(folds)
    split[1] = "fold2"          # second row of cluster g0000 sent to another fold
    raises("split cluster is refused at construction", sp.ManifestError,
           sp.describe_folds, scheme="TEST_BLOCK", cluster_keys=clusters, fold_keys=split)

    tmp = Path(tempfile.mkdtemp())
    try:
        b = fixture_bindings(tmp)
        short = sp.describe_folds(scheme="TEST_BLOCK", cluster_keys=clusters[:-2],
                                  fold_keys=folds[:-2])
        raises("fold totals that disagree with the row universe are refused",
               sp.ManifestError, sp.build_manifest, **{**b, "folds": short})
        one = sp.describe_folds(scheme="TEST_BLOCK", cluster_keys=clusters,
                                fold_keys=["only"] * len(clusters))
        raises("a single fold is refused", sp.ManifestError,
               sp.build_manifest, **{**b, "folds": one})
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_k0_pairing_rules() -> None:
    print("\n[4] K0_MATCHED is per-arm and authoritative; K0_FLAT is diagnostic only")
    good = sp.describe_k0_pairing({
        "A": {"k0_matched_id": "K0M_A", "k0_matched_record": {"a": 1}},
        "B": {"k0_matched_id": "K0M_B", "k0_matched_record": {"b": 1}},
    }, k0_flat_id="K0_FLAT")
    check("per-arm map is accepted", good["n_arms"] == 2)
    check("K0_FLAT is recorded diagnostic_only", good["k0_flat_role"] == "diagnostic_only")
    check("K0_MATCHED is the authoritative control",
          good["authoritative_control"] == "K0_MATCHED")
    check("the matched control is bound by DIGEST, not by name",
          sp.describe_k0_pairing({"A": {"k0_matched_id": "K0M_A",
                                        "k0_matched_record": {"a": 2}}})["arms"]["A"]
          ["k0_matched_digest"] != good["arms"]["A"]["k0_matched_digest"])

    raises("empty pairing refused", sp.ManifestError, sp.describe_k0_pairing, {})
    raises("arm without a matched control refused", sp.ManifestError,
           sp.describe_k0_pairing, {"A": {"k0_matched_record": {"a": 1}}})
    raises("arm without a matched-control RECORD refused", sp.ManifestError,
           sp.describe_k0_pairing, {"A": {"k0_matched_id": "K0M_A"}})
    raises("one matched control shared by two arms refused", sp.ManifestError,
           sp.describe_k0_pairing,
           {"A": {"k0_matched_id": "SHARED", "k0_matched_record": {"a": 1}},
            "B": {"k0_matched_id": "SHARED", "k0_matched_record": {"b": 1}}})
    raises("K0_FLAT named as a matched control refused", sp.ManifestError,
           sp.describe_k0_pairing,
           {"A": {"k0_matched_id": "K0_FLAT", "k0_matched_record": {"a": 1}}})
    raises("the declared flat control reused as matched refused", sp.ManifestError,
           sp.describe_k0_pairing,
           {"A": {"k0_matched_id": "FLAT_DIAG", "k0_matched_record": {"a": 1}}},
           k0_flat_id="FLAT_DIAG")


def test_seeds_and_commit(tmp: Path) -> None:
    print("\n[5] seeds are explicit integers; the commit is a real sha")
    b = fixture_bindings(tmp)
    for bad in ({"s": None}, {"s": 1.5}, {"s": "42"}, {"s": True}, {}):
        raises(f"seeds={bad} refused", sp.ManifestError,
               sp.build_manifest, **{**b, "seeds": bad})
    raises("non-sha commit refused", sp.ManifestError, sp.build_manifest,
           **{**b, "code_commit": {"commit": "HEAD", "branch": "x", "dirty": False}})
    raises("commit without an explicit dirty flag refused", sp.ManifestError,
           sp.build_manifest, **{**b, "code_commit": {"commit": "a" * 40, "branch": "x"}})
    dirty = {"commit": "a" * 40, "branch": "x", "dirty": True, "dirty_paths": ["f"]}
    raises("dirty tree refused when require_clean_tree", sp.ManifestError, sp.build_manifest,
           **{**b, "code_commit": dirty, "require_clean_tree": True})
    check("dirty tree is RECORDED, not silently dropped, when not required",
          sp.build_manifest(**{**b, "code_commit": dirty})
          ["bindings"]["code_commit"]["dirty"] is True)
    raises("a missing declared input is an error, not a null entry",
           sp.ManifestError, sp.hash_inputs, [tmp / "does_not_exist.bin"])


# --------------------------------------------------------------------------------------------
# 6. the sealed directory cannot be read by the writing process
# --------------------------------------------------------------------------------------------
PLAINTEXT = b"ARM_ONE_FOLD_MAE=1.2345 THIS_IS_A_RESULT_MARKER"


def build_seal(tmp: Path, name: str = "seal") -> tuple[Path, dict]:
    b = fixture_bindings(tmp)
    m = sp.build_manifest(**b)
    root = tmp / name
    with sp.SealedWriter(root, m, actor="test", node_id="I11_TESTS") as w:
        w.write_payload("results.bin", PLAINTEXT)
        w.write_json_payload("fold_table.json", {"folds": ["fold0", "fold1", "fold2"]})
        summary = w.finalize()
    return root, summary


def test_writer_is_write_only(tmp: Path) -> None:
    print("\n[6] the writing process has no read path into its own seal")
    root, summary = build_seal(tmp, "seal_wo")

    w_attrs = [a for a in dir(sp.SealedWriter) if not a.startswith("_")]
    check("SealedWriter exposes no read method", not any(
        a.startswith("read") or a in ("payload", "open", "get", "load") for a in w_attrs),
        str(sorted(w_attrs)))
    check("write_payload returns a digest, not bytes",
          all(isinstance(v, str) and len(v) == 64
              for v in summary["payload_plaintext_digests"].values()))
    check("finalize reports zero read attempts by the writer",
          summary["writer_read_attempts"] == 0)

    stored = root / sp.PAYLOAD_DIR / "results.bin.sealed"
    scratch = tmp / "scratch"
    scratch.mkdir(exist_ok=True)
    with sp.SealGuard(root / sp.PAYLOAD_DIR):
        table = probe_surfaces(stored, root / sp.PAYLOAD_DIR, scratch, PLAINTEXT[:20])
    for surface in MUST_TRAP:
        check(f"trapped: {surface}", table[surface]["outcome"] == TRAPPED,
              table[surface]["detail"])
    leaked = [k for k, v in table.items() if v["outcome"] == "LEAKED"]
    check("no probed surface recovered plaintext", not leaked, str(leaked))
    for native in ("pandas.read_parquet", "pyarrow.OSFile", "separate python process"):
        print(f"  INFO  {native}: {table[native]['outcome']} -- {table[native]['detail']}")

    # a write attempt that got through would have left this file behind
    check("no stray file was created by the write probe",
          not (root / sp.PAYLOAD_DIR / "probe_write.tmp").exists())

    # the guard also fires DURING writing, on the live writer
    b = fixture_bindings(tmp)
    m = sp.build_manifest(**b)
    with sp.SealedWriter(tmp / "seal_live", m, actor="t", node_id="I11_TESTS") as w:
        w.write_payload("r.bin", PLAINTEXT)
        target = tmp / "seal_live" / sp.PAYLOAD_DIR / "r.bin.sealed"
        raises("a live writer reading back its own payload is refused",
               sp.SealViolation, lambda: open(target, "rb").read())
        check("the refusal is recorded as a violation", len(w.violations) == 1,
              json.dumps(w.violations[:1]))
        s2 = w.finalize()
    check("finalize reports the attempted read", s2["writer_read_attempts"] == 1)
    check("a violation record is written next to the seal",
          (tmp / "seal_live" / sp.VIOLATION_NAME).is_file())

    check("the trap is uninstalled when no guard is armed", open is sp._REAL_OPEN)
    check("io.open is restored too", io.open is sp._REAL_IO_OPEN)


def test_at_rest(tmp: Path) -> None:
    print("\n[7] the sealed bytes on disk are not the plaintext")
    root, _ = build_seal(tmp, "seal_rest")
    stored = (root / sp.PAYLOAD_DIR / "results.bin.sealed").read_bytes()
    check("stored payload does not contain the plaintext", PLAINTEXT not in stored)
    check("stored payload shares no 8-byte run with the plaintext",
          not any(PLAINTEXT[i:i + 8] in stored for i in range(len(PLAINTEXT) - 8)))
    check("stored payload carries the seal magic", stored.startswith(sp.PAYLOAD_MAGIC))
    check("stored length = magic + nonce + plaintext length",
          len(stored) == len(sp.PAYLOAD_MAGIC) + sp.NONCE_BYTES + len(PLAINTEXT))
    r2, _ = build_seal(tmp, "seal_rest2")
    other = (r2 / sp.PAYLOAD_DIR / "results.bin.sealed").read_bytes()
    check("the same plaintext seals to different bytes under a fresh nonce", other != stored)


# --------------------------------------------------------------------------------------------
# 8. verification discloses nothing
# --------------------------------------------------------------------------------------------
def test_verify(tmp: Path) -> None:
    print("\n[8] verification proves the run without opening it")
    root, summary = build_seal(tmp, "seal_v")
    v = sp.verify_seal(root)
    check("clean seal verifies", v["ok"], str(v["failures"]))
    check("all six bindings confirmed present",
          set(v["bindings_present"]) == set(sp.REQUIRED_BINDINGS))
    check("verification reports zero opens", v["open_log"]["n_opens"] == 0)
    blob = json.dumps(v)
    check("the verification result contains no plaintext",
          PLAINTEXT.decode() not in blob and "THIS_IS_A_RESULT_MARKER" not in blob)
    check("every declared output is confirmed present",
          all(p["present"] and p["stored_sha256_ok"] and p["plaintext_sha256_ok"]
              for p in v["payloads"]))

    # payload tamper
    root2, _ = build_seal(tmp, "seal_tamper")
    f = root2 / sp.PAYLOAD_DIR / "results.bin.sealed"
    raw = bytearray(f.read_bytes())
    raw[-1] ^= 0xFF
    f.write_bytes(bytes(raw))
    v2 = sp.verify_seal(root2)
    check("a flipped payload bit fails verification", not v2["ok"], str(v2["failures"])[:120])

    # manifest tamper
    root3, _ = build_seal(tmp, "seal_mtamper")
    mf = root3 / sp.MANIFEST_NAME
    man = json.loads(mf.read_bytes())
    man["bindings"]["seeds"]["fold_seed"] = 1
    mf.write_bytes(sp.canonical_bytes(man))
    v3 = sp.verify_seal(root3)
    check("an altered seed fails verification", not v3["ok"])
    check("the failure names the manifest binding",
          any("manifest_digest" in f for f in v3["failures"]), str(v3["failures"])[:160])

    # missing declared output
    root4, _ = build_seal(tmp, "seal_missing")
    (root4 / sp.PAYLOAD_DIR / "fold_table.json.sealed").unlink()
    v4 = sp.verify_seal(root4)
    check("a missing declared output fails verification", not v4["ok"])
    check("the failure names the missing output",
          any("missing" in f for f in v4["failures"]), str(v4["failures"])[:160])


# --------------------------------------------------------------------------------------------
# 9. opening is a separate, logged operation
# --------------------------------------------------------------------------------------------
def test_open_is_logged(tmp: Path) -> None:
    print("\n[9] opening a seal is separate and logged")
    root, _ = build_seal(tmp, "seal_open")
    check("a fresh seal has an empty open log", sp.read_open_log(root) == [])
    check("status before opening is SEALED", sp.seal_status(root)["state"] == "SEALED")

    o = sp.open_seal(root, actor="coordinator", reason="P39 integrity verification",
                     authorization_ref="TESTS.py", node_id="I11_TESTS")
    check("round-trip plaintext is byte-identical", o.payload("results.bin") == PLAINTEXT)
    check("json payload round-trips",
          o.json_payload("fold_table.json")["folds"] == ["fold0", "fold1", "fold2"])

    log = sp.read_open_log(root)
    check("the open appended exactly one log entry", len(log) == 1, json.dumps(log)[:200])
    e = log[0]
    for field in ("actor", "reason", "authorization_ref", "node_id", "manifest_digest",
                  "payloads_disclosed", "ts", "prev_hash", "entry_hash"):
        check(f"log entry records {field}", field in e and e[field] not in (None, "", []))
    check("status after opening is OPENED", sp.seal_status(root)["state"] == "OPENED")

    sp.open_seal(root, actor="second reader", reason="adjudication",
                 authorization_ref="TESTS.py", node_id="I11_TESTS", payloads=["results.bin"])
    log = sp.read_open_log(root)
    check("a second open appends a second entry", len(log) == 2)
    check("the second entry records only what it asked for",
          log[1]["payloads_disclosed"] == ["results.bin"])
    chain = sp.verify_open_log(root, log[0]["manifest_digest"])
    check("the open-log hash chain verifies", chain["chain_ok"], str(chain["failures"]))
    check("verify_seal reports the open count", sp.verify_seal(root)["open_log"]["n_opens"] == 2)

    raises("unknown payload name refused", KeyError, sp.open_seal, root, actor="a",
           reason="r", authorization_ref="x", node_id="n", payloads=["nope"])
    check("the refused open logged nothing", len(sp.read_open_log(root)) == 2)

    # log tampering -- done last, because it deliberately corrupts this seal
    lp = root / sp.OPEN_LOG_NAME
    lines = lp.read_bytes().splitlines()
    lp.write_bytes(lines[0] + b"\n")                       # delete the second (last) open
    v = sp.verify_seal(root)
    check("deleting the LAST log line is caught by the head anchor", not v["ok"],
          str(v["failures"])[:160])
    lp.write_bytes(b"\n".join(lines) + b"\n")
    check("restoring the log restores verification", sp.verify_seal(root)["ok"])
    first = json.loads(lines[0])
    first["actor"] = "somebody else"
    lp.write_bytes(sp.canonical_bytes(first) + b"\n" + lines[1] + b"\n")
    check("editing a log entry breaks the chain check", not sp.verify_seal(root)["ok"])
    lp.write_bytes(b"\n".join(lines) + b"\n")
    (root / sp.OPEN_HEAD_NAME).unlink()
    check("removing the head anchor is itself a failure", not sp.verify_seal(root)["ok"])


def test_open_refusals(tmp: Path) -> None:
    print("\n[10] opening refuses when it should")
    root, _ = build_seal(tmp, "seal_refuse")
    for kw in ("actor", "reason", "authorization_ref", "node_id"):
        args = {"actor": "a", "reason": "r", "authorization_ref": "x", "node_id": "n"}
        args[kw] = ""
        raises(f"open without {kw} refused", ValueError, sp.open_seal, root, **args)

    bad, _ = build_seal(tmp, "seal_bad")
    f = bad / sp.PAYLOAD_DIR / "results.bin.sealed"
    raw = bytearray(f.read_bytes())
    raw[-1] ^= 0xFF
    f.write_bytes(bytes(raw))
    raises("a seal that fails verification cannot be opened", sp.SealIntegrityError,
           sp.open_seal, bad, actor="a", reason="r", authorization_ref="x", node_id="n")
    check("the refused open left no log entry", sp.read_open_log(bad) == [])

    live = tmp / "seal_guarded"
    m = sp.build_manifest(**fixture_bindings(tmp))
    with sp.SealedWriter(live, m, actor="t", node_id="I11_TESTS") as w:
        w.write_payload("r.bin", PLAINTEXT)
        w.finalize()
        raises("the writing process cannot open its own seal while writing",
               sp.SealViolation, sp.open_seal, live, actor="runner", reason="peek",
               authorization_ref="none", node_id="I11_TESTS")
    check("no open was logged for the refused attempt", sp.read_open_log(live) == [])

    root2, _ = build_seal(tmp, "seal_writeonce")
    m2 = sp.build_manifest(**fixture_bindings(tmp))
    with sp.SealedWriter(tmp / "seal_wonce", m2, actor="t", node_id="I11_TESTS") as w:
        w.write_payload("a.bin", b"x")
        raises("a payload name may not be written twice", sp.SealViolation,
               w.write_payload, "a.bin", b"y")
        w.finalize()
        raises("a finalized seal accepts no further payloads", sp.SealViolation,
               w.write_payload, "b.bin", b"z")
    raises("a writer used outside its context manager refuses to write", sp.SealViolation,
           sp.SealedWriter(tmp / "seal_nocm", m2, actor="t", node_id="n").write_payload,
           "a.bin", b"x")


def test_interop() -> None:
    print("\n[11] interoperability with the frozen shared contract")
    check("row_digest comes from the frozen comparison gate, not a local copy",
          "comparison_gate" in sp.ROW_DIGEST_SOURCE and "FALLBACK" not in sp.ROW_DIGEST_SOURCE,
          sp.ROW_DIGEST_SOURCE)
    try:
        import comparison_gate as cg
        keys = ["g1|H", "g1|A", "g2|H"]
        u = sp.describe_universe(keys, ["g1", "g1", "g2"],
                                 row_key_columns=["k"], cluster_key_column="g")
        check("universe row_digest equals comparison_gate.row_digest on the same keys",
              u["row_digest"] == cg.row_digest(keys), u["row_digest"])
        check("row_digest is order-insensitive, as the frozen gate defines it",
              cg.row_digest(keys) == cg.row_digest(list(reversed(keys))))
    except Exception as e:  # noqa: BLE001
        check("comparison_gate importable", False, repr(e))
    check("digest_count reads the row count back out of the digest",
          sp.digest_count(sp.row_digest(["a", "b", "c"])) == 3)


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="i11_seal_"))
    try:
        test_manifest_requires_six(tmp)
        test_digest_binds(tmp)
        test_fold_cluster_integrity()
        test_k0_pairing_rules()
        test_seeds_and_commit(tmp)
        test_writer_is_write_only(tmp)
        test_at_rest(tmp)
        test_verify(tmp)
        test_open_is_logged(tmp)
        test_open_refusals(tmp)
        test_interop()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("\n%d failure(s)" % len(FAILURES))
    for f in FAILURES:
        print("  FAILED: " + f)
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
