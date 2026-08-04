"""I11_BLINDED_RESULT_PACKAGING -- generic sealed-result and integrity-manifest tooling.

INFRASTRUCTURE. Enforces the seal mechanically rather than by convention.

Task-isolated namespace. Nothing here amends a shared contract, and nothing here is imported by
any frozen module. It reuses `comparison_gate.row_digest` READ-ONLY so that a row set described
here and a row set described by the frozen comparison gate produce the SAME string.

------------------------------------------------------------------------------------------------
What this module gives you
------------------------------------------------------------------------------------------------

    build_manifest(...)   -> a manifest that BINDS, in one digest:
                             code commit | data hashes | row universe | folds | K0 pairing | seeds
                             Every one of the six is REQUIRED. A missing or malformed binding
                             raises ManifestError; it cannot be defaulted away.

    SealedWriter(...)     -> a write-only handle on a sealed directory. It has NO read method,
                             and while it is open the ordinary Python read surface is trapped for
                             every path under the seal: an attempt by the writing process to read
                             what it just wrote raises SealViolation and is recorded.

    verify_seal(root)     -> integrity verification that RETURNS NO PLAINTEXT. Payload bytes are
                             streamed into hashlib and discarded. This is the primitive a result-
                             integrity verifier uses to confirm "this is the preregistered run"
                             without learning which arm won.

    open_seal(root, ...)  -> the ONLY way to obtain plaintext. It is a separate operation, it
                             refuses to open a seal that fails verification, and it appends a
                             hash-chained record to SEAL_OPEN_LOG.jsonl BEFORE any byte is
                             returned. Deleting or editing a log line breaks the chain.

------------------------------------------------------------------------------------------------
Threat model -- stated plainly, because the alternative is theatre
------------------------------------------------------------------------------------------------

The adversary this module defeats is the *careless writing process*: a runner that fits arms,
writes results, and would otherwise be one `pd.read_parquet` away from seeing them. It is NOT a
defence against a hostile process with filesystem access and the same privileges, and no
same-process, same-filesystem mechanism can be.

Two independent layers, both measured in TESTS.py and MEASUREMENTS.json:

  L1  in-process read trap. builtins.open / io.open / os.open / os.listdir / os.scandir are
      patched for the duration of the writer. Covers pathlib, shutil and anything that routes
      through them. Does NOT cover a native reader that opens the file in C (pyarrow does).

  L2  at-rest obfuscation. Payloads are stored XORed with a SHA-256 counter keystream derived
      from PUBLIC material (domain string, manifest digest, payload name, stored nonce). This is
      OBFUSCATION, NOT CONFIDENTIALITY -- the keystream is derivable by anyone holding the seal.
      What it buys is that *no read surface*, native ones included, yields plaintext by accident.
      Getting plaintext requires calling open_seal(), which logs.

L1 without L2 leaks to native readers. L2 without L1 is trivially undone. Together, an accidental
disclosure is impossible and a deliberate one is a logged, non-repudiable act.
"""
from __future__ import annotations

import builtins
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

# --------------------------------------------------------------------------------------------
# constants
# --------------------------------------------------------------------------------------------

MANIFEST_SCHEMA = "sealed_manifest/1"
SEAL_SCHEMA = "sealed_seal/1"
OPEN_LOG_SCHEMA = "seal_open_log/1"
FOLD_SCHEMA = "fold_assignment/1"
UNIVERSE_SCHEMA = "row_universe/1"
K0_PAIRING_SCHEMA = "k0_pairing/1"

DOMAIN = b"player_program/I11_BLINDED_RESULT_PACKAGING/seal/1"
PAYLOAD_MAGIC = b"SEALPKG1"
NONCE_BYTES = 16
CHUNK = 32 * 1024  # multiple of 32 so keystream counters stay block-aligned

MANIFEST_NAME = "MANIFEST.json"
SEAL_NAME = "SEAL.json"
OPEN_LOG_NAME = "SEAL_OPEN_LOG.jsonl"
OPEN_HEAD_NAME = "SEAL_OPEN_HEAD.json"
VIOLATION_NAME = "SEAL_VIOLATIONS.jsonl"
PAYLOAD_DIR = "sealed"

REQUIRED_BINDINGS = ("code_commit", "data_hashes", "row_universe", "folds", "k0_pairing", "seeds")

_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_HEX40 = re.compile(r"^[0-9a-f]{40}$")


class ManifestError(ValueError):
    """A binding is missing, malformed, or internally inconsistent."""


class SealViolation(RuntimeError):
    """The writing process tried to touch the sealed payloads."""


class SealIntegrityError(RuntimeError):
    """The seal does not verify against its own manifest."""


# --------------------------------------------------------------------------------------------
# canonicalisation and digests
# --------------------------------------------------------------------------------------------

def canonical_bytes(obj: Any) -> bytes:
    """Deterministic JSON encoding. Two structurally equal objects give identical bytes."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_obj(obj: Any) -> str:
    return sha256_bytes(canonical_bytes(obj))


def sha256_file(path: str | os.PathLike) -> str:
    h = hashlib.sha256()
    with _REAL_OPEN(str(path), "rb") as fh:
        for chunk in iter(lambda: fh.read(CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# row_digest: reuse the FROZEN shared implementation so that a row set described here and the same
# row set described by comparison_gate produce the same string. Read-only import; never modified.
_PROGRAM_ROOT = Path(__file__).resolve().parents[2]
if str(_PROGRAM_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROGRAM_ROOT))

ROW_DIGEST_SOURCE = "comparison_gate.row_digest (frozen shared contract)"
_NO_BYTECODE = sys.dont_write_bytecode
sys.dont_write_bytecode = True   # importing a frozen module must not write a .pyc beside it
try:  # pragma: no cover - exercised by TESTS.py test_interop
    from comparison_gate import row_digest as row_digest  # type: ignore  # noqa: F401
except Exception as _exc:  # pragma: no cover
    ROW_DIGEST_SOURCE = f"LOCAL FALLBACK -- frozen import failed: {_exc!r}"

    def row_digest(keys: Any, *, sort: bool = True, label: str = "rows") -> str:  # type: ignore
        vals = [repr(float(v)) if isinstance(v, float) else str(v) for v in list(keys)]
        if sort:
            vals = sorted(vals)
        h = hashlib.sha256("\x00".join(vals).encode("utf-8")).hexdigest()
        return f"{label}:n={len(vals)}:sha256={h[:32]}"
finally:
    sys.dont_write_bytecode = _NO_BYTECODE


_DIGEST_N = re.compile(r"^(?P<label>[^:]+):n=(?P<n>\d+):sha256=(?P<h>[0-9a-f]{32})$")


def digest_count(d: str) -> int:
    """The row count a row_digest string carries. Lets a manifest cross-check its own claims."""
    m = _DIGEST_N.match(d or "")
    if not m:
        raise ManifestError(f"not a row_digest string: {d!r}")
    return int(m.group("n"))


# --------------------------------------------------------------------------------------------
# the read trap (layer L1)
# --------------------------------------------------------------------------------------------

_REAL_OPEN = builtins.open
_REAL_IO_OPEN = io.open
_REAL_OS_OPEN = os.open
_REAL_LISTDIR = os.listdir
_REAL_SCANDIR = os.scandir

_GUARDS: list["SealGuard"] = []
_GUARD_LOCK = threading.RLock()
_TOKEN = threading.local()

TRAPPED_SURFACES = ("builtins.open", "io.open", "os.open", "os.listdir", "os.scandir")


def _norm_forms(p: Any) -> tuple[str, ...]:
    """Every spelling of a path that must compare equal.

    On Windows the temp directory is frequently an 8.3 short name (JGALLA~1) while
    `Path.resolve()` returns the long name. A guard that normalised only one way would silently
    fail to cover its own directory -- a seal that looks armed and is not. Both forms are kept.
    """
    try:
        s = os.fspath(p)
    except TypeError:
        return ()  # a file descriptor, or something we cannot resolve to a path
    if isinstance(s, bytes):
        s = s.decode("utf-8", "replace")
    a = os.path.normcase(os.path.abspath(s))
    try:
        r = os.path.normcase(os.path.realpath(s))
    except OSError:
        r = a
    return (a,) if a == r else (a, r)


def _check(path: Any, api: str, mode: Any = None) -> None:
    if not _GUARDS:
        return
    forms = _norm_forms(path)
    if not forms:
        return
    allowed = getattr(_TOKEN, "allow_root", None)
    for g in list(_GUARDS):
        if not g.covers(forms):
            continue
        if allowed is not None and allowed in g.root_forms:
            return  # the writer's own API-mediated write
        p = forms[0]
        g.record(api=api, path=p, mode=str(mode))
        raise SealViolation(
            f"{api} on sealed path is refused: {p}\n"
            f"the process that writes a seal may not read it. "
            f"plaintext requires open_seal(), which is logged."
        )


def _guarded_open(file, mode="r", *a, **k):
    _check(file, "builtins.open", mode)
    return _REAL_OPEN(file, mode, *a, **k)


def _guarded_io_open(file, mode="r", *a, **k):
    _check(file, "io.open", mode)
    return _REAL_IO_OPEN(file, mode, *a, **k)


def _guarded_os_open(path, flags, *a, **k):
    _check(path, "os.open", flags)
    return _REAL_OS_OPEN(path, flags, *a, **k)


def _guarded_listdir(path="."):
    _check(path, "os.listdir", None)
    return _REAL_LISTDIR(path)


def _guarded_scandir(path="."):
    _check(path, "os.scandir", None)
    return _REAL_SCANDIR(path)


def _install() -> None:
    builtins.open = _guarded_open
    io.open = _guarded_io_open
    os.open = _guarded_os_open
    os.listdir = _guarded_listdir
    os.scandir = _guarded_scandir


def _uninstall() -> None:
    builtins.open = _REAL_OPEN
    io.open = _REAL_IO_OPEN
    os.open = _REAL_OS_OPEN
    os.listdir = _REAL_LISTDIR
    os.scandir = _REAL_SCANDIR


class SealGuard:
    """Traps the ordinary read surface for one directory subtree.

    Usable on its own (`with SealGuard(path): ...`) by any process that wants to prove it did not
    read a directory, not only by SealedWriter.
    """

    def __init__(self, root: str | os.PathLike):
        self.root = str(Path(root).resolve())
        forms = set(_norm_forms(self.root)) | set(_norm_forms(root))
        self.root_forms = tuple(sorted(forms))
        self.norm_root = self.root_forms[0]
        self.violations: list[dict] = []
        self._entered = False

    def covers(self, path_forms: tuple[str, ...]) -> bool:
        for p in path_forms:
            for r in self.root_forms:
                if p == r or p.startswith(r + os.sep):
                    return True
        return False

    def record(self, *, api: str, path: str, mode: str) -> None:
        self.violations.append({"schema": "seal_violation/1", "ts": _utcnow(),
                                "api": api, "mode": mode, "path": path})

    def __enter__(self) -> "SealGuard":
        with _GUARD_LOCK:
            if not _GUARDS:
                _install()
            _GUARDS.append(self)
        self._entered = True
        return self

    def __exit__(self, *exc) -> bool:
        with _GUARD_LOCK:
            if self in _GUARDS:
                _GUARDS.remove(self)
            if not _GUARDS:
                _uninstall()
        self._entered = False
        return False


def active_guard_for(root: str | os.PathLike) -> SealGuard | None:
    """Any armed guard that covers `root`, or that guards a subtree of it.

    A writer arms its guard on the payload subdirectory, which is *below* the seal root, so a
    naive containment test in one direction would let the writer open its own seal.
    """
    forms = _norm_forms(str(Path(root).resolve())) + _norm_forms(root)
    for g in list(_GUARDS):
        if g.covers(forms):
            return g
        for n in forms:
            if any(r == n or r.startswith(n + os.sep) for r in g.root_forms):
                return g
    return None


class _WriteToken:
    """Marks the current thread's writes as API-mediated, for exactly one guarded root."""

    def __init__(self, norm_root: str):
        self.norm_root = norm_root
        self.prev = None

    def __enter__(self):
        self.prev = getattr(_TOKEN, "allow_root", None)
        _TOKEN.allow_root = self.norm_root
        return self

    def __exit__(self, *exc):
        _TOKEN.allow_root = self.prev
        return False


# --------------------------------------------------------------------------------------------
# at-rest obfuscation (layer L2)
# --------------------------------------------------------------------------------------------

def _seed(manifest_digest: str, name: str, nonce: bytes) -> bytes:
    return DOMAIN + b"|" + manifest_digest.encode() + b"|" + name.encode("utf-8") + b"|" + nonce


def _keystream(seed: bytes, counter: int, nblocks: int) -> bytes:
    out = bytearray()
    for i in range(nblocks):
        out += hashlib.sha256(seed + (counter + i).to_bytes(8, "big")).digest()
    return bytes(out)


def _xor(data: bytes, seed: bytes, block_offset: int) -> bytes:
    nblocks = (len(data) + 31) // 32
    ks = _keystream(seed, block_offset, nblocks)
    return bytes(a ^ b for a, b in zip(data, ks))


# --------------------------------------------------------------------------------------------
# binding builders -- each one MEASURES rather than accepts a claim
# --------------------------------------------------------------------------------------------

def read_code_commit(repo_root: str | os.PathLike) -> dict:
    """Read-only git. Never mutates. Raises if the commit cannot be established."""
    root = str(Path(repo_root).resolve())

    def git(*args: str) -> str:
        r = subprocess.run(["git", "-C", root, *args], capture_output=True, text=True)
        if r.returncode != 0:
            raise ManifestError(f"git {' '.join(args)} failed: {r.stderr.strip()}")
        return r.stdout.strip()

    commit = git("rev-parse", "HEAD")
    branch = git("rev-parse", "--abbrev-ref", "HEAD")
    porcelain = git("status", "--porcelain")
    dirty_paths = sorted(ln[3:] for ln in porcelain.splitlines() if ln.strip())
    return {"commit": commit, "short": commit[:7], "branch": branch,
            "dirty": bool(dirty_paths), "dirty_paths": dirty_paths}


def hash_inputs(paths: Iterable[str | os.PathLike], *, root: str | os.PathLike | None = None) -> dict:
    """sha256 every declared input. A missing file is an error, never a null entry."""
    out: dict[str, dict] = {}
    for p in paths:
        full = Path(root, p) if root is not None else Path(p)
        full = full.resolve()
        if not full.is_file():
            raise ManifestError(f"declared input does not exist: {full}")
        key = str(p).replace("\\", "/")
        out[key] = {"sha256": sha256_file(full), "n_bytes": full.stat().st_size}
    if not out:
        raise ManifestError("data_hashes may not be empty")
    return out


def describe_universe(row_keys: Sequence[Any], cluster_keys: Sequence[Any], *,
                      row_key_columns: Sequence[str], cluster_key_column: str) -> dict:
    """Digest the row universe AND its cluster structure. Both counts are carried, never one."""
    row_keys = list(row_keys)
    cluster_keys = list(cluster_keys)
    if len(row_keys) != len(cluster_keys):
        raise ManifestError("row_keys and cluster_keys must be parallel")
    if not row_keys:
        raise ManifestError("row universe may not be empty")
    if len(set(map(str, row_keys))) != len(row_keys):
        raise ManifestError("row keys are not unique -- the row universe is not a set of rows")
    uniq_clusters = sorted({str(c) for c in cluster_keys})
    return {
        "schema": UNIVERSE_SCHEMA,
        "row_key_columns": list(row_key_columns),
        "cluster_key_column": cluster_key_column,
        "n_rows": len(row_keys),
        "n_clusters": len(uniq_clusters),
        "row_digest": row_digest(row_keys, label="rows"),
        "cluster_digest": row_digest(uniq_clusters, label="clusters"),
    }


def describe_folds(*, scheme: str, cluster_keys: Sequence[Any], fold_keys: Sequence[Any]) -> dict:
    """Row-level fold assignment, checked for cluster integrity.

    A cluster that appears in two folds is a split game. That is refused here, at construction,
    not flagged in prose later.
    """
    cluster_keys = [str(c) for c in cluster_keys]
    fold_keys = [str(f) for f in fold_keys]
    if len(cluster_keys) != len(fold_keys):
        raise ManifestError("cluster_keys and fold_keys must be parallel")
    if not cluster_keys:
        raise ManifestError("fold assignment may not be empty")
    seen: dict[str, set[str]] = {}
    for c, f in zip(cluster_keys, fold_keys):
        seen.setdefault(c, set()).add(f)
    split = sorted(c for c, fs in seen.items() if len(fs) > 1)
    if split:
        raise ManifestError(
            f"{len(split)} cluster(s) are split across folds; a game may never be split. "
            f"first offenders: {split[:5]}"
        )
    folds: dict[str, dict] = {}
    for c, f in zip(cluster_keys, fold_keys):
        d = folds.setdefault(f, {"fold": f, "n_rows": 0, "clusters": set()})
        d["n_rows"] += 1
        d["clusters"].add(c)
    fold_records = []
    for f in sorted(folds):
        d = folds[f]
        fold_records.append({"fold": f, "n_rows": d["n_rows"], "n_clusters": len(d["clusters"]),
                             "cluster_digest": row_digest(sorted(d["clusters"]), label="clusters")})
    return {
        "schema": FOLD_SCHEMA,
        "scheme": scheme,
        "n_folds": len(fold_records),
        "n_rows": len(cluster_keys),
        "n_clusters": len(seen),
        "cluster_split_check": "PASS -- no cluster appears in more than one fold",
        "folds": fold_records,
        "assignment_digest": row_digest([f"{c}\x1f{f}" for c, f in zip(cluster_keys, fold_keys)],
                                        label="assignment"),
    }


def describe_k0_pairing(entries: Mapping[str, Mapping[str, Any]], *,
                        k0_flat_id: str | None = None) -> dict:
    """K0_MATCHED is a MAP KEYED BY arm_id. Never one universal control.

    Each entry: {"k0_matched_id": str, "k0_matched_record": obj|bytes, "arm_kind": str}.
    The record is digested, so the pairing binds the actual frozen specification, not its name.
    """
    if not entries:
        raise ManifestError("k0_pairing may not be empty")
    arms: dict[str, dict] = {}
    matched_ids: dict[str, str] = {}
    for arm_id, e in entries.items():
        if not isinstance(arm_id, str) or not arm_id.strip():
            raise ManifestError(f"bad arm_id: {arm_id!r}")
        mid = e.get("k0_matched_id")
        if not isinstance(mid, str) or not mid.strip():
            raise ManifestError(f"arm {arm_id}: k0_matched_id is required")
        if mid.upper().startswith("K0_FLAT"):
            raise ManifestError(
                f"arm {arm_id}: K0_FLAT is diagnostic only and may never be the matched control")
        if k0_flat_id is not None and mid == k0_flat_id:
            raise ManifestError(f"arm {arm_id}: matched control is the flat diagnostic control")
        if mid in matched_ids:
            raise ManifestError(
                f"K0_MATCHED {mid!r} is shared by arms {matched_ids[mid]!r} and {arm_id!r}; "
                f"the matched control is PER ARM")
        matched_ids[mid] = arm_id
        rec = e.get("k0_matched_record")
        if rec is None:
            raise ManifestError(f"arm {arm_id}: k0_matched_record is required")
        rec_bytes = rec if isinstance(rec, bytes) else canonical_bytes(rec)
        arms[arm_id] = {
            "k0_matched_id": mid,
            "k0_matched_digest": sha256_bytes(rec_bytes),
            "arm_kind": e.get("arm_kind"),
        }
    return {
        "schema": K0_PAIRING_SCHEMA,
        "authoritative_control": "K0_MATCHED",
        "k0_flat_id": k0_flat_id,
        "k0_flat_role": "diagnostic_only",
        "n_arms": len(arms),
        "arms": arms,
    }


def _validate_code_commit(v: Any) -> None:
    if not isinstance(v, Mapping):
        raise ManifestError("code_commit must be an object")
    c = v.get("commit")
    if not isinstance(c, str) or not _HEX40.match(c):
        raise ManifestError(f"code_commit.commit must be a 40-hex sha, got {c!r}")
    if not isinstance(v.get("branch"), str) or not v["branch"].strip():
        raise ManifestError("code_commit.branch is required")
    if not isinstance(v.get("dirty"), bool):
        raise ManifestError("code_commit.dirty must be an explicit boolean")


def _validate_data_hashes(v: Any) -> None:
    if not isinstance(v, Mapping) or not v:
        raise ManifestError("data_hashes must be a non-empty object")
    for k, e in v.items():
        h = e.get("sha256") if isinstance(e, Mapping) else e
        if not isinstance(h, str) or not _HEX64.match(h):
            raise ManifestError(f"data_hashes[{k!r}] is not a 64-hex sha256: {h!r}")


def _validate_universe(v: Any) -> None:
    if not isinstance(v, Mapping) or v.get("schema") != UNIVERSE_SCHEMA:
        raise ManifestError("row_universe must be built by describe_universe()")
    nr, nc = v.get("n_rows"), v.get("n_clusters")
    if not isinstance(nr, int) or nr <= 0:
        raise ManifestError("row_universe.n_rows must be a positive int")
    if not isinstance(nc, int) or nc <= 0:
        raise ManifestError("row_universe.n_clusters must be a positive int")
    if nc > nr:
        raise ManifestError("row_universe: more clusters than rows")
    if digest_count(v["row_digest"]) != nr:
        raise ManifestError("row_universe.row_digest disagrees with n_rows")
    if digest_count(v["cluster_digest"]) != nc:
        raise ManifestError("row_universe.cluster_digest disagrees with n_clusters")


def _validate_folds(v: Any, universe: Mapping) -> None:
    if not isinstance(v, Mapping) or v.get("schema") != FOLD_SCHEMA:
        raise ManifestError("folds must be built by describe_folds()")
    if v.get("n_folds", 0) < 2:
        raise ManifestError("folds.n_folds must be at least 2")
    if sum(f["n_rows"] for f in v["folds"]) != universe["n_rows"]:
        raise ManifestError("fold row counts do not sum to the row universe")
    if sum(f["n_clusters"] for f in v["folds"]) != universe["n_clusters"]:
        raise ManifestError("fold cluster counts do not sum to the cluster universe")


def _validate_k0(v: Any) -> None:
    if not isinstance(v, Mapping) or v.get("schema") != K0_PAIRING_SCHEMA:
        raise ManifestError("k0_pairing must be built by describe_k0_pairing()")
    if v.get("authoritative_control") != "K0_MATCHED":
        raise ManifestError("K0_MATCHED is the sole authoritative control")
    if v.get("k0_flat_role") != "diagnostic_only":
        raise ManifestError("K0_FLAT must be recorded as diagnostic_only")
    if not v.get("arms"):
        raise ManifestError("k0_pairing.arms may not be empty")


def _validate_seeds(v: Any) -> None:
    if not isinstance(v, Mapping) or not v:
        raise ManifestError("seeds must be a non-empty object")
    for k, s in v.items():
        if isinstance(s, bool) or not isinstance(s, int):
            raise ManifestError(f"seed {k!r} must be an explicit integer, got {s!r}")


def build_manifest(*, run_id: str, code_commit: Mapping, data_hashes: Mapping,
                   row_universe: Mapping, folds: Mapping, k0_pairing: Mapping,
                   seeds: Mapping, target: str, extra: Mapping | None = None,
                   require_clean_tree: bool = False) -> dict:
    """Bind the six required things into one digest. Every one is required.

    `manifest_digest` covers schema, run_id, target and all six bindings. It deliberately does NOT
    cover `created_at`: the same run rebuilt tomorrow must produce the same digest.
    """
    if not isinstance(run_id, str) or not run_id.strip():
        raise ManifestError("run_id is required")
    if not isinstance(target, str) or not target.strip():
        raise ManifestError("target is required")
    bindings = {"code_commit": code_commit, "data_hashes": data_hashes,
                "row_universe": row_universe, "folds": folds,
                "k0_pairing": k0_pairing, "seeds": seeds}
    for name in REQUIRED_BINDINGS:
        if bindings.get(name) in (None, {}, [], ""):
            raise ManifestError(f"binding {name!r} is required and may not be empty")
    _validate_code_commit(code_commit)
    if require_clean_tree and code_commit.get("dirty"):
        raise ManifestError("working tree is dirty and require_clean_tree=True")
    _validate_data_hashes(data_hashes)
    _validate_universe(row_universe)
    _validate_folds(folds, row_universe)
    _validate_k0(k0_pairing)
    _validate_seeds(seeds)

    body = {"schema": MANIFEST_SCHEMA, "run_id": run_id, "target": target,
            "bindings": {k: json.loads(canonical_bytes(v)) for k, v in bindings.items()}}
    if extra:
        body["extra"] = json.loads(canonical_bytes(extra))
    manifest = dict(body)
    manifest["created_at"] = _utcnow()
    manifest["digest_covers"] = ["schema", "run_id", "target", "bindings"] + (["extra"] if extra else [])
    manifest["manifest_digest"] = sha256_obj(body)
    return manifest


def manifest_digest_of(manifest: Mapping) -> str:
    """Recompute the digest from the manifest's own covered fields."""
    covered = manifest.get("digest_covers")
    if not covered:
        raise ManifestError("manifest has no digest_covers field")
    body = {k: manifest[k] for k in covered}
    return sha256_obj(body)


# --------------------------------------------------------------------------------------------
# the sealed writer
# --------------------------------------------------------------------------------------------

class SealedWriter:
    """A WRITE-ONLY handle on a sealed directory.

    There is no read method on this class. Not a discouraged one -- none. write_payload returns a
    digest, never bytes. While the writer is open, the read trap is armed for the payload subtree.
    """

    def __init__(self, seal_root: str | os.PathLike, manifest: Mapping, *,
                 actor: str, node_id: str):
        self.root = Path(seal_root).resolve()
        self.payload_dir = self.root / PAYLOAD_DIR
        self.manifest = json.loads(canonical_bytes(manifest))
        if self.manifest.get("schema") != MANIFEST_SCHEMA:
            raise ManifestError("SealedWriter requires a manifest from build_manifest()")
        if manifest_digest_of(self.manifest) != self.manifest["manifest_digest"]:
            raise ManifestError("manifest digest does not match its own bindings")
        self.manifest_digest = self.manifest["manifest_digest"]
        self.actor = actor
        self.node_id = node_id
        self._payloads: dict[str, dict] = {}
        self._guard: SealGuard | None = None
        self._finalized = False

    # -- lifecycle ---------------------------------------------------------------------------
    def __enter__(self) -> "SealedWriter":
        self.payload_dir.mkdir(parents=True, exist_ok=True)
        self._guard = SealGuard(self.payload_dir).__enter__()
        return self

    def __exit__(self, *exc) -> bool:
        if self._guard is not None:
            self._guard.__exit__(*exc)
            self._guard = None
        return False

    @property
    def violations(self) -> list[dict]:
        return list(self._guard.violations) if self._guard else []

    # -- writing -----------------------------------------------------------------------------
    def write_payload(self, name: str, data: bytes) -> str:
        """Seal one payload. Returns its PLAINTEXT DIGEST -- never its content."""
        if self._guard is None:
            raise SealViolation("SealedWriter must be used as a context manager; the read trap "
                                "is armed on __enter__ and a payload may not be written without it")
        if self._finalized:
            raise SealViolation("the seal is closed; a finalized seal accepts no further payloads")
        if not re.match(r"^[A-Za-z0-9._-]+$", name or ""):
            raise ValueError(f"payload name must be a simple filename, got {name!r}")
        if name in self._payloads:
            raise SealViolation(f"payload {name!r} already sealed; a seal is write-once")
        if not isinstance(data, (bytes, bytearray)):
            raise TypeError("payload data must be bytes")
        data = bytes(data)
        nonce = os.urandom(NONCE_BYTES)
        seed = _seed(self.manifest_digest, name, nonce)
        stored = self.payload_dir / (name + ".sealed")
        h_plain = hashlib.sha256(data)
        h_stored = hashlib.sha256()
        with _WriteToken(self._guard.norm_root if self._guard else ""):
            with open(stored, "wb") as fh:
                head = PAYLOAD_MAGIC + nonce
                fh.write(head)
                h_stored.update(head)
                for off in range(0, max(len(data), 1), CHUNK):
                    piece = data[off:off + CHUNK]
                    if not piece:
                        break
                    ct = _xor(piece, seed, off // 32)
                    fh.write(ct)
                    h_stored.update(ct)
        rec = {"name": name, "stored_file": f"{PAYLOAD_DIR}/{name}.sealed",
               "nonce": nonce.hex(), "n_bytes": len(data),
               "plaintext_sha256": h_plain.hexdigest(), "stored_sha256": h_stored.hexdigest()}
        self._payloads[name] = rec
        return rec["plaintext_sha256"]

    def write_json_payload(self, name: str, obj: Any) -> str:
        return self.write_payload(name, canonical_bytes(obj))

    # -- closing -----------------------------------------------------------------------------
    def finalize(self) -> dict:
        """Write MANIFEST.json, SEAL.json and the empty open log. Returns digests only."""
        if self._finalized:
            raise SealViolation("already finalized")
        if not self._payloads:
            raise SealViolation("refusing to finalize an empty seal")
        self.root.mkdir(parents=True, exist_ok=True)
        payloads = [self._payloads[n] for n in sorted(self._payloads)]
        seal_body = {
            "schema": SEAL_SCHEMA,
            "node_id": self.node_id,
            "actor": self.actor,
            "sealed_at": _utcnow(),
            "manifest_digest": self.manifest_digest,
            "payload_dir": PAYLOAD_DIR,
            "n_payloads": len(payloads),
            "payloads": payloads,
            "public_members": [MANIFEST_NAME, SEAL_NAME, OPEN_LOG_NAME, OPEN_HEAD_NAME,
                               VIOLATION_NAME],
            "sealed_members": [p["stored_file"] for p in payloads],
            "at_rest": "sha256-counter keystream keyed by PUBLIC material "
                       "(domain, manifest_digest, payload name, nonce). "
                       "OBFUSCATION, NOT CONFIDENTIALITY.",
            "disclosure_rule": "plaintext is obtainable only via open_seal(), which appends to "
                               f"{OPEN_LOG_NAME} before returning any byte",
            "writer_read_attempts": len(self.violations),
        }
        seal = dict(seal_body)
        seal["seal_digest"] = sha256_obj(seal_body)
        _write_public(self.root / MANIFEST_NAME, canonical_bytes(self.manifest))
        _write_public(self.root / SEAL_NAME, canonical_bytes(seal))
        log = self.root / OPEN_LOG_NAME
        if not log.exists():
            _write_public(log, b"")
        _write_head(self.root, 0, _genesis(self.manifest_digest))
        vio = self.violations
        if vio:
            _write_public(self.root / VIOLATION_NAME,
                          b"".join(canonical_bytes(v) + b"\n" for v in vio))
        self._finalized = True
        return {"manifest_digest": self.manifest_digest, "seal_digest": seal["seal_digest"],
                "n_payloads": len(payloads), "writer_read_attempts": len(vio),
                "payload_plaintext_digests": {p["name"]: p["plaintext_sha256"] for p in payloads}}


def _write_public(path: Path, data: bytes) -> None:
    """Public seal members live at the seal root, outside the guarded payload subtree."""
    with _REAL_OPEN(str(path), "wb") as fh:
        fh.write(data)


# --------------------------------------------------------------------------------------------
# verification without disclosure
# --------------------------------------------------------------------------------------------

def _read_public_json(path: Path) -> Any:
    with _REAL_OPEN(str(path), "rb") as fh:
        return json.loads(fh.read().decode("utf-8"))


def read_open_log(seal_root: str | os.PathLike) -> list[dict]:
    p = Path(seal_root).resolve() / OPEN_LOG_NAME
    if not p.exists():
        return []
    with _REAL_OPEN(str(p), "rb") as fh:
        raw = fh.read().decode("utf-8")
    return [json.loads(ln) for ln in raw.splitlines() if ln.strip()]


def _entry_hash(entry: Mapping) -> str:
    body = {k: v for k, v in entry.items() if k != "entry_hash"}
    return sha256_obj(body)


def _genesis(manifest_digest: str) -> str:
    return sha256_bytes(DOMAIN + b"|genesis|" + manifest_digest.encode())


def _write_head(root: Path, seq: int, head_hash: str) -> None:
    """The head anchor. A pure hash chain detects edits and mid-deletions but NOT truncation of
    the tail -- dropping the last open would leave a self-consistent log. The anchor is a second
    file that must agree; erasing an open now requires two coordinated edits instead of one.
    It is not tamper-PROOF. The durable anchor is the coordinator's commit of both files."""
    _write_public(root / OPEN_HEAD_NAME, canonical_bytes(
        {"schema": "seal_open_head/1", "seq": seq, "head_hash": head_hash,
         "updated_at": _utcnow()}))


def verify_open_log(seal_root: str | os.PathLike, manifest_digest: str) -> dict:
    root = Path(seal_root).resolve()
    entries = read_open_log(root)
    genesis = _genesis(manifest_digest)
    prev = genesis
    failures = []
    for i, e in enumerate(entries):
        if e.get("seq") != i + 1:
            failures.append(f"open log entry {i}: seq is {e.get('seq')!r}, expected {i + 1}")
        if e.get("prev_hash") != prev:
            failures.append(f"open log entry {i}: chain broken (prev_hash mismatch)")
        if _entry_hash(e) != e.get("entry_hash"):
            failures.append(f"open log entry {i}: entry_hash does not match its content")
        prev = e.get("entry_hash")
    head_file = root / OPEN_HEAD_NAME
    if not head_file.is_file():
        failures.append(f"{OPEN_HEAD_NAME} is missing; the open log has no anchor")
    else:
        head = _read_public_json(head_file)
        if head.get("seq") != len(entries):
            failures.append(
                f"open-log anchor says {head.get('seq')} open(s), the log carries {len(entries)}; "
                f"an open record was removed")
        elif head.get("head_hash") != prev:
            failures.append("open-log anchor does not match the log head")
    return {"n_opens": len(entries), "chain_ok": not failures, "failures": failures,
            "head_hash": prev, "genesis": genesis}


def verify_seal(seal_root: str | os.PathLike) -> dict:
    """Confirm the seal IS the run its manifest describes. Returns NO plaintext.

    Payload bytes are streamed through hashlib and discarded. Nothing derived from payload
    content, other than digests already public in SEAL.json, appears in the return value.
    """
    root = Path(seal_root).resolve()
    failures: list[str] = []
    result: dict[str, Any] = {"schema": "seal_verification/1", "seal_root": str(root),
                              "checked_at": _utcnow(), "discloses_payload_content": False}
    for name in (MANIFEST_NAME, SEAL_NAME):
        if not (root / name).is_file():
            failures.append(f"missing public member {name}")
    if failures:
        result.update({"ok": False, "failures": failures})
        return result

    manifest = _read_public_json(root / MANIFEST_NAME)
    seal = _read_public_json(root / SEAL_NAME)
    result["manifest_digest"] = manifest.get("manifest_digest")
    result["run_id"] = manifest.get("run_id")

    try:
        recomputed = manifest_digest_of(manifest)
    except ManifestError as e:
        recomputed = None
        failures.append(f"manifest not digestible: {e}")
    if recomputed is not None and recomputed != manifest.get("manifest_digest"):
        failures.append("manifest_digest does not match the manifest bindings -- "
                        "a bound field was altered after sealing")
    result["manifest_digest_recomputed"] = recomputed

    seal_body = {k: v for k, v in seal.items() if k != "seal_digest"}
    if sha256_obj(seal_body) != seal.get("seal_digest"):
        failures.append("seal_digest does not match SEAL.json content")
    if seal.get("manifest_digest") != manifest.get("manifest_digest"):
        failures.append("SEAL.json and MANIFEST.json disagree about the manifest digest")

    # each of the six bindings must be present in the manifest that the digest covers
    bindings = manifest.get("bindings", {})
    for b in REQUIRED_BINDINGS:
        if not bindings.get(b):
            failures.append(f"binding {b!r} absent from the manifest")
    result["bindings_present"] = sorted(k for k in REQUIRED_BINDINGS if bindings.get(k))

    payload_results = []
    for p in seal.get("payloads", []):
        stored = root / p["stored_file"].replace("/", os.sep)
        rec = {"name": p["name"], "n_bytes": p["n_bytes"], "present": stored.is_file()}
        if not rec["present"]:
            failures.append(f"declared output missing: {p['stored_file']}")
            payload_results.append(rec)
            continue
        h_stored = hashlib.sha256()
        h_plain = hashlib.sha256()
        seed = _seed(manifest["manifest_digest"], p["name"], bytes.fromhex(p["nonce"]))
        with _REAL_OPEN(str(stored), "rb") as fh:
            head = fh.read(len(PAYLOAD_MAGIC) + NONCE_BYTES)
            h_stored.update(head)
            if head[:len(PAYLOAD_MAGIC)] != PAYLOAD_MAGIC:
                failures.append(f"{p['name']}: not a sealed payload file")
            off = 0
            while True:
                ct = fh.read(CHUNK)
                if not ct:
                    break
                h_stored.update(ct)
                h_plain.update(_xor(ct, seed, off // 32))   # plaintext exists only inside this
                off += len(ct)                              # expression, and is discarded
        rec["stored_sha256_ok"] = (h_stored.hexdigest() == p["stored_sha256"])
        rec["plaintext_sha256_ok"] = (h_plain.hexdigest() == p["plaintext_sha256"])
        rec["n_bytes_ok"] = (off == p["n_bytes"])
        if not rec["stored_sha256_ok"]:
            failures.append(f"{p['name']}: stored bytes do not match the sealed digest")
        if not rec["plaintext_sha256_ok"]:
            failures.append(f"{p['name']}: recovered plaintext does not match the sealed digest")
        if not rec["n_bytes_ok"]:
            failures.append(f"{p['name']}: byte count differs from the sealed record")
        payload_results.append(rec)
    result["payloads"] = payload_results

    log = verify_open_log(root, manifest.get("manifest_digest", ""))
    result["open_log"] = log
    if not log["chain_ok"]:
        failures.extend(log["failures"])

    vio = root / VIOLATION_NAME
    result["writer_read_attempts"] = seal.get("writer_read_attempts", 0)
    result["violation_file_present"] = vio.is_file()

    result["ok"] = not failures
    result["failures"] = failures
    return result


# --------------------------------------------------------------------------------------------
# opening -- a separate, logged operation
# --------------------------------------------------------------------------------------------

class OpenedSeal:
    """Plaintext access, granted only after an open was logged."""

    def __init__(self, root: Path, seal: Mapping, manifest_digest: str, log_entry: Mapping):
        self._root = root
        self._seal = seal
        self._md = manifest_digest
        self.log_entry = json.loads(canonical_bytes(log_entry))
        self.names = [p["name"] for p in seal.get("payloads", [])]

    def payload(self, name: str) -> bytes:
        for p in self._seal.get("payloads", []):
            if p["name"] == name:
                stored = self._root / p["stored_file"].replace("/", os.sep)
                seed = _seed(self._md, name, bytes.fromhex(p["nonce"]))
                out = bytearray()
                with _REAL_OPEN(str(stored), "rb") as fh:
                    fh.read(len(PAYLOAD_MAGIC) + NONCE_BYTES)
                    off = 0
                    while True:
                        ct = fh.read(CHUNK)
                        if not ct:
                            break
                        out += _xor(ct, seed, off // 32)
                        off += len(ct)
                got = sha256_bytes(bytes(out))
                if got != p["plaintext_sha256"]:
                    raise SealIntegrityError(f"{name}: plaintext digest mismatch on open")
                return bytes(out)
        raise KeyError(name)

    def json_payload(self, name: str) -> Any:
        return json.loads(self.payload(name).decode("utf-8"))


def open_seal(seal_root: str | os.PathLike, *, actor: str, reason: str,
              authorization_ref: str, node_id: str,
              payloads: Sequence[str] | None = None) -> OpenedSeal:
    """The ONLY route to plaintext.

    Refuses if a SealGuard is armed on this seal (the writing process may not open its own seal).
    Refuses if verification fails -- a divergence is a failure, never a silently accepted open.
    Appends a hash-chained log entry BEFORE returning the handle.
    """
    root = Path(seal_root).resolve()
    for a in (actor, reason, authorization_ref, node_id):
        if not isinstance(a, str) or not a.strip():
            raise ValueError("actor, reason, authorization_ref and node_id are all required")

    g = active_guard_for(root)
    if g is not None:
        raise SealViolation(
            f"a seal guard is armed on {g.root}; the writing process may not open its own seal")

    ver = verify_seal(root)
    if not ver["ok"]:
        raise SealIntegrityError("refusing to open a seal that does not verify: "
                                 + "; ".join(ver["failures"]))

    seal = _read_public_json(root / SEAL_NAME)
    md = ver["manifest_digest"]
    known = [p["name"] for p in seal.get("payloads", [])]
    requested = list(payloads) if payloads is not None else known
    unknown = [n for n in requested if n not in known]
    if unknown:
        raise KeyError(f"no such payload(s): {unknown}")

    existing = read_open_log(root)
    prev = existing[-1]["entry_hash"] if existing else _genesis(md)
    entry = {"schema": OPEN_LOG_SCHEMA, "seq": len(existing) + 1, "ts": _utcnow(),
             "actor": actor, "node_id": node_id, "reason": reason,
             "authorization_ref": authorization_ref, "manifest_digest": md,
             "seal_digest": seal.get("seal_digest"), "verify_ok": True,
             "payloads_disclosed": sorted(requested), "prev_hash": prev}
    entry["entry_hash"] = _entry_hash(entry)
    with _REAL_OPEN(str(root / OPEN_LOG_NAME), "ab") as fh:
        fh.write(canonical_bytes(entry) + b"\n")
        fh.flush()
        os.fsync(fh.fileno())
    _write_head(root, entry["seq"], entry["entry_hash"])

    return OpenedSeal(root, seal, md, entry)


def seal_status(seal_root: str | os.PathLike) -> dict:
    """Public status. Reads only public members; never touches a payload."""
    root = Path(seal_root).resolve()
    if not (root / SEAL_NAME).is_file():
        return {"exists": False, "seal_root": str(root)}
    seal = _read_public_json(root / SEAL_NAME)
    log = read_open_log(root)
    return {"exists": True, "seal_root": str(root),
            "manifest_digest": seal.get("manifest_digest"),
            "seal_digest": seal.get("seal_digest"),
            "n_payloads": seal.get("n_payloads"),
            "n_opens": len(log),
            "state": "OPENED" if log else "SEALED",
            "last_open": log[-1] if log else None}
