#!/usr/bin/env python3
"""seed_manifest.py -- the frozen cycle-2 seed manifest.

Epistemic status: IMPLEMENTATION. Unit/synthetic/identity/schema tests only; no comparative
historical performance is revealed.

SPEC_V2.seed_manifest_plan, carried by the S35 freeze:

    master_seed = 20260807
    seed(purpose, fold_id, b) = first 4 bytes of
        sha256(utf8('{master_seed}|{fold_id}|{purpose}|{b}')) as big-endian unsigned int

    test_bootstrap : 10,000 draws, "one stream per fold, SHARED by every arm and every null in
                     that fold (paired comparisons)"
    train_refit    :  2,000 draws, "one stream per fold, shared by arm and its null"

PAIRING IS A PROPERTY OF THE DERIVATION, NOT OF CALLER DISCIPLINE. Draw b's generator depends on
(master_seed, fold_id, purpose, b) and on nothing else -- not on the arm, not on the element, not
on call order. Two elements evaluated in the same fold therefore see the SAME resampled cluster
index set for draw b whether or not the caller remembered to want that.
"""
from __future__ import annotations

import hashlib

import numpy as np

import runner_constants as K

PURPOSES = (K.SEED_PURPOSE_TEST, K.SEED_PURPOSE_TRAIN)


def derive_seed(purpose: str, fold_id: str, b: int, master_seed: int = K.MASTER_SEED) -> int:
    """EXACTLY the frozen derivation string. Not a tuning knob."""
    if purpose not in PURPOSES:
        raise ValueError(f"unregistered seed purpose {purpose!r}; the manifest pins {PURPOSES}")
    msg = f"{master_seed}|{fold_id}|{purpose}|{b}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(msg).digest()[:4], "big")


def rng_for(purpose: str, fold_id: str, b: int) -> np.random.Generator:
    return np.random.Generator(np.random.PCG64(derive_seed(purpose, fold_id, b)))


def seed_stream_digest(purpose: str, fold_id: str, n_draws: int) -> str:
    """sha256 over the comma-joined decimal seeds of a whole stream: a receipt can pin every seed
    actually used without storing 10,000 integers."""
    h = hashlib.sha256()
    for b in range(n_draws):
        h.update(str(derive_seed(purpose, fold_id, b)).encode())
        h.update(b",")
    return h.hexdigest()


def build_manifest(fold_ids=K.FOLD_IDS, n_test_draws: int = K.B_TEST,
                   n_train_draws: int = K.B_TRAIN_REFIT) -> dict:
    per_fold = {}
    for fid in fold_ids:
        per_fold[str(fid)] = {
            K.SEED_PURPOSE_TEST: {
                "n_draws": int(n_test_draws),
                "first_seeds": [derive_seed(K.SEED_PURPOSE_TEST, fid, b) for b in range(3)],
                "stream_sha256": seed_stream_digest(K.SEED_PURPOSE_TEST, fid, n_test_draws)},
            K.SEED_PURPOSE_TRAIN: {
                "n_draws": int(n_train_draws),
                "first_seeds": [derive_seed(K.SEED_PURPOSE_TRAIN, fid, b) for b in range(3)],
                "stream_sha256": seed_stream_digest(K.SEED_PURPOSE_TRAIN, fid, n_train_draws)},
        }
    return {"schema": "s36_seed_manifest/1", "master_seed": K.MASTER_SEED,
            "derivation": K.SEED_DERIVATION, "purposes": list(PURPOSES),
            "fitting": K.FITTING_DETERMINISM,
            "sharing": ("one stream per (purpose, fold); draw b is identical for every arm and "
                        "every null in that fold, so comparisons are paired by construction"),
            "per_fold": per_fold}
