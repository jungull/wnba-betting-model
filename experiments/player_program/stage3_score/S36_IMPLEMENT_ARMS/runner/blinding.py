#!/usr/bin/env python3
"""blinding.py -- the runner REFUSES to fit against the real universe at S36.

Epistemic status: IMPLEMENTATION. Unit/synthetic/identity/schema tests only; no comparative
historical performance is revealed.

This is the mechanism that makes acceptance criterion 2 -- "no performance number emitted
anywhere" -- structural rather than a promise about author discipline. S35 is explicit:

    NOT_AUTHORISED_FITTING: "This freeze does NOT authorise fitting. Fitting requires a PASSED
    S37 implementation audit. Until S37 passes, no arm and no K0 may be fitted and no performance
    number may be computed."

The predicate never inspects performance. It inspects only STRUCTURAL signatures of the frozen
real universe:

  * row count in {2982, 2990}          (universe / full contract schedule)
  * cluster count in {1491, 1495}
  * any fold_id in the frozen D006 list
  * any supplied artifact hashing to a frozen real-artifact sha256

Building features and design matrices on the real universe IS authorised ("construction of
feature matrices, K0_MATCHED constructions and the receipted diagnostics each card names, on the
pinned universe and the pinned row base"), so the refusal sits at the FIT boundary, not at the
build boundary. `assert_may_build` is therefore permissive and `assert_may_fit` is not.

Tests exercise the unseal branch ONLY by injecting an explicit mapping via `env=`; they never set
the real environment variable, and they assert it is absent from os.environ.
"""
from __future__ import annotations

import os
from pathlib import Path

import runner_constants as K
from canon import sha256_file


class BlindingViolation(RuntimeError):
    """A blinded context tried to fit real folds. The caller must not proceed."""


def real_signatures(*, n_rows=None, n_clusters=None, fold_ids=None,
                    artifact_paths=None, artifact_hashes=None) -> list[dict]:
    sigs: list[dict] = []
    if n_rows is not None and int(n_rows) in K.REAL_UNIVERSE_ROW_COUNTS:
        sigs.append({"kind": "real_row_count", "value": int(n_rows)})
    if n_clusters is not None and int(n_clusters) in K.REAL_UNIVERSE_CLUSTER_COUNTS:
        sigs.append({"kind": "real_cluster_count", "value": int(n_clusters)})
    for fid in (fold_ids or []):
        if str(fid) in K.REAL_FOLD_IDS:
            sigs.append({"kind": "real_fold_id", "value": str(fid)})
    hashes = [str(h).lower() for h in (artifact_hashes or [])]
    for p in (artifact_paths or []):
        p = Path(p)
        if p.exists():
            hashes.append(sha256_file(p))
    for h in hashes:
        if h in K.REAL_ARTIFACT_SHA256:
            sigs.append({"kind": "real_artifact_sha256", "value": h})
    return sigs


def assert_may_fit(*, n_rows=None, n_clusters=None, fold_ids=None, artifact_paths=None,
                   artifact_hashes=None, env=None) -> dict:
    """Raise BlindingViolation on any real signature unless the unseal flag is present in `env`."""
    env = os.environ if env is None else env
    unsealed = K.UNSEAL_ENV_FLAG in env
    sigs = real_signatures(n_rows=n_rows, n_clusters=n_clusters, fold_ids=fold_ids,
                           artifact_paths=artifact_paths, artifact_hashes=artifact_hashes)
    receipt = {"schema": "s36_blinding_check/1", "unseal_flag": K.UNSEAL_ENV_FLAG,
               "unsealed": bool(unsealed), "real_signatures": sigs,
               "not_authorised_fitting": K.NOT_AUTHORISED_FITTING,
               "checked": {"n_rows": n_rows, "n_clusters": n_clusters,
                           "fold_ids": [str(f) for f in (fold_ids or [])]}}
    if sigs and not unsealed:
        raise BlindingViolation(
            f"S36 may not fit real folds: {sigs}. {K.NOT_AUTHORISED_FITTING} "
            f"(the unseal flag {K.UNSEAL_ENV_FLAG} belongs to S38 and to nothing earlier.)")
    return receipt


def assert_may_build(**_) -> dict:
    """Building feature matrices on the real universe is explicitly AUTHORISED by the freeze.
    This exists so the distinction is written down in code rather than left to the reader."""
    return {"schema": "s36_build_authorisation/1", "authorised": True,
            "authority": ("S35 what_this_freeze_authorises.AUTHORISED: 'construction of feature "
                          "matrices, K0_MATCHED constructions and the receipted diagnostics each "
                          "card names, on the pinned universe and the pinned row base'")}
