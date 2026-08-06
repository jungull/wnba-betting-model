#!/usr/bin/env python3
"""seed_manifest.py -- the frozen seed manifest (P33 seed_manifest_plan, carried by P35).

    master_seed = 20260806
    seed(purpose, fold_id, b) = first 4 bytes of
        sha256(utf8('{master_seed}|{fold_id}|{purpose}|{b}')) as big-endian unsigned int

One stream per (purpose, fold): draw b's RNG is seeded independently from the derived seed, so
draw b is identical for every arm and every null evaluated in that fold -- pairing is a property
of the derivation, not of caller discipline. IRLS is deterministic; no fit-time seed exists.
"""
from __future__ import annotations

import hashlib

import numpy as np

from runner_constants import (MASTER_SEED, SEED_DERIVATION, SEED_PURPOSE_TEST,
                              SEED_PURPOSE_TRAIN)

_PURPOSES = (SEED_PURPOSE_TEST, SEED_PURPOSE_TRAIN)


def derive_seed(purpose: str, fold_id: str, b: int, master_seed: int = MASTER_SEED) -> int:
    """EXACTLY the frozen derivation string. Not a tuning knob."""
    msg = f"{master_seed}|{fold_id}|{purpose}|{b}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(msg).digest()[:4], "big")


def rng_for(purpose: str, fold_id: str, b: int) -> np.random.Generator:
    return np.random.Generator(np.random.PCG64(derive_seed(purpose, fold_id, b)))


def seed_stream_digest(purpose: str, fold_id: str, n_draws: int) -> str:
    """sha256 over the comma-joined decimal seeds of the whole stream: lets a receipt pin every
    seed actually used without storing 10,000 integers."""
    h = hashlib.sha256()
    for b in range(n_draws):
        h.update(str(derive_seed(purpose, fold_id, b)).encode())
        h.update(b",")
    return h.hexdigest()


def build_manifest(fold_ids, n_test_draws: int, n_train_draws: int) -> dict:
    """The seed-manifest record embedded in every runner receipt."""
    per_fold = {}
    for fid in fold_ids:
        per_fold[str(fid)] = {
            SEED_PURPOSE_TEST: {
                "n_draws": int(n_test_draws),
                "first_seeds": [derive_seed(SEED_PURPOSE_TEST, fid, b) for b in range(3)],
                "stream_sha256": seed_stream_digest(SEED_PURPOSE_TEST, fid, n_test_draws)},
            SEED_PURPOSE_TRAIN: {
                "n_draws": int(n_train_draws),
                "first_seeds": [derive_seed(SEED_PURPOSE_TRAIN, fid, b) for b in range(3)],
                "stream_sha256": seed_stream_digest(SEED_PURPOSE_TRAIN, fid, n_train_draws)},
        }
    return {"schema": "p36_seed_manifest/1", "master_seed": MASTER_SEED,
            "derivation": SEED_DERIVATION, "purposes": list(_PURPOSES),
            "fitting": "IRLS is deterministic; no fit-time seed exists",
            "per_fold": per_fold}
