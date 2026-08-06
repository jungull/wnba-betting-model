#!/usr/bin/env python3
"""blinding.py -- the runner REFUSES to run against real folds unless P38_UNSEALED exists.

Structural refusal, fail closed (P36 mandate). The predicate never inspects performance; it
inspects only structural signatures of the frozen real universe / contract schedule:

  * row count in {2982, 2990}            (universe / full contract schedule)
  * game-cluster count in {1491, 1495}
  * any fold_id in the frozen D006 list
  * any supplied input artifact whose bytes hash to a frozen real-artifact sha256

The unseal branch is controlled by the P38_UNSEALED environment flag. Tests exercise it ONLY by
injecting an explicit mapping via `env=`; they never set the real environment variable, and they
assert it is absent from os.environ.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

from runner_constants import (REAL_ARTIFACT_SHA256, REAL_FOLD_IDS,
                              REAL_UNIVERSE_CLUSTER_COUNTS, REAL_UNIVERSE_ROW_COUNTS,
                              UNSEAL_ENV_FLAG)


class BlindingViolation(RuntimeError):
    """Raised when a blinded run touches real-fold structure. The caller must not proceed."""


def _sha256_file(p) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def assert_not_real(*, n_rows: int | None = None, n_clusters: int | None = None,
                    fold_ids=None, artifact_paths=None, artifact_hashes=None,
                    env=None) -> dict:
    """Raise BlindingViolation on any real-fold signature unless the unseal flag exists in `env`
    (default: the real process environment). Returns the blinding receipt on success."""
    env = os.environ if env is None else env
    unsealed = UNSEAL_ENV_FLAG in env
    signatures = []

    if n_rows is not None and int(n_rows) in REAL_UNIVERSE_ROW_COUNTS:
        signatures.append({"kind": "real_row_count", "value": int(n_rows)})
    if n_clusters is not None and int(n_clusters) in REAL_UNIVERSE_CLUSTER_COUNTS:
        signatures.append({"kind": "real_cluster_count", "value": int(n_clusters)})
    for fid in (fold_ids or []):
        if str(fid) in REAL_FOLD_IDS:
            signatures.append({"kind": "real_fold_id", "value": str(fid)})
    hashes = [str(h).lower() for h in (artifact_hashes or [])]
    for p in (artifact_paths or []):
        p = Path(p)
        if p.exists():
            hashes.append(_sha256_file(p))
    for h in hashes:
        if h in REAL_ARTIFACT_SHA256:
            signatures.append({"kind": "real_artifact_sha256", "value": h})

    receipt = {"schema": "p36_blinding_check/1", "unseal_flag": UNSEAL_ENV_FLAG,
               "unsealed": bool(unsealed), "real_signatures": signatures,
               "checked": {"n_rows": n_rows, "n_clusters": n_clusters,
                           "fold_ids": [str(f) for f in (fold_ids or [])],
                           "n_artifact_hashes": len(hashes)}}
    if signatures and not unsealed:
        raise BlindingViolation(
            f"real-fold structure detected without {UNSEAL_ENV_FLAG}: {signatures}")
    return receipt


def assert_not_real_frame(df, cluster_col: str, fold_ids=None, artifact_paths=None,
                          env=None) -> dict:
    return assert_not_real(n_rows=len(df), n_clusters=int(df[cluster_col].nunique()),
                           fold_ids=fold_ids, artifact_paths=artifact_paths, env=env)
