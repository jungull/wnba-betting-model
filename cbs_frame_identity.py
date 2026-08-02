#!/usr/bin/env python3
"""cbs_frame_identity.py — a type-preserving, null-distinct frame digest.

WHY THIS MODULE EXISTS
----------------------
`cbs_v8.frame_digest` rendered every cell with `str(v)`, mapping a null and an
empty string to the same token, and an integer `1` and the string `"1"` to the
same token. Frame binding is the check that stands between a mutated frame and
the fitting code, so a collision there is not cosmetic: a frame whose `None` was
replaced by `""`, or whose numeric key was replaced by its text form, kept its
identity and reached the model.

The encoding here tags every cell with its type and keeps null distinct from
every representable value:

    None / NaN / NaT / pd.NA  ->  ["null", ""]
    True                      ->  ["bool", "true"]
    1                         ->  ["int", "1"]
    1.0                       ->  ["float", "1.0"]
    "1"                       ->  ["str", "1"]
    ""                        ->  ["str", ""]
    Timestamp(...)            ->  ["ts", "...+00:00"]

so `None != ""`, `1 != "1"`, `1 != 1.0` and `True != 1`.

WHAT IS DELIBERATELY *NOT* DISTINGUISHED
----------------------------------------
All null flavours collapse to one token. `None`, `np.nan`, `pd.NaT` and `pd.NA`
are the same claim — "no value" — and which one a frame carries is an artifact of
pandas dtype plumbing that changes under an innocuous `reindex` or `concat`.
Distinguishing them would make the digest fragile without making it safer.

Row and column ORDER are also deliberately not distinguished: columns are sorted
by name and rows by `row_uid`, so a shuffled or reordered frame is the same
artifact. That is a required property — the runners sort internally — and it is
what makes the digest a statement about content rather than about layout.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json

import numpy as np
import pandas as pd

FRAME_IDENTITY_SCHEMA = "cbs_frame_identity/2"

#: the single token every null flavour collapses to
NULL_TOKEN = ["null", ""]


class FrameIdentityError(RuntimeError):
    """A frame cannot be given a canonical identity."""


def _is_null(v) -> bool:
    """True for every null flavour, without raising on array-likes.

    `pd.isna` returns an ARRAY for a list or ndarray cell, and `bool()` of that
    raises. Such a cell is not null, so the ambiguity is resolved by treating a
    non-scalar answer as "not null" rather than letting the exception escape.
    """
    if v is None or v is pd.NaT:
        return True
    try:
        res = pd.isna(v)
    except (TypeError, ValueError):
        return False
    return bool(res) if isinstance(res, (bool, np.bool_)) else False


def encode_cell(v) -> list:
    """One cell -> `[type_tag, text]`, null-distinct and type-preserving."""
    if _is_null(v):
        return list(NULL_TOKEN)
    # bool BEFORE int: Python's bool is a subclass of int, so the natural order
    # would silently encode True as ["int", "1"] and collide with the integer 1.
    if isinstance(v, (bool, np.bool_)):
        return ["bool", "true" if bool(v) else "false"]
    if isinstance(v, (int, np.integer)):
        return ["int", str(int(v))]
    if isinstance(v, (float, np.floating)):
        # repr keeps full precision; a rounded rendering would let two genuinely
        # different floats share an identity
        return ["float", repr(float(v))]
    if isinstance(v, (pd.Timestamp, _dt.datetime)):
        return ["ts", pd.Timestamp(v).isoformat()]
    if isinstance(v, _dt.date):
        return ["date", v.isoformat()]
    if isinstance(v, (bytes, bytearray)):
        return ["bytes", bytes(v).hex()]
    if isinstance(v, str):
        return ["str", v]
    if isinstance(v, (list, tuple, np.ndarray)):
        return ["seq", json.dumps([encode_cell(x) for x in list(v)],
                                  separators=(",", ":"))]
    if isinstance(v, dict):
        return ["map", json.dumps({str(k): encode_cell(x)
                                   for k, x in sorted(v.items(), key=lambda kv: str(kv[0]))},
                                  separators=(",", ":"))]
    return ["repr", f"{type(v).__module__}.{type(v).__name__}:{v!r}"]


def frame_digest(frame: pd.DataFrame, *, key: str = "row_uid") -> str:
    """A canonical, order-independent, type-preserving digest of a frame.

    Sorting on `key` makes the digest independent of row order; sorting the
    column names makes it independent of column order. Everything else about the
    content is inside the hash.
    """
    if not isinstance(frame, pd.DataFrame):
        raise FrameIdentityError("frame_digest requires a DataFrame")
    if key not in frame.columns:
        raise FrameIdentityError(f"cannot digest a frame without {key!r}")
    if frame[key].isna().any():
        raise FrameIdentityError(
            f"{int(frame[key].isna().sum())} rows have a null {key!r}; the sort that "
            f"makes this digest order-independent would not be well defined")
    if frame[key].duplicated().any():
        raise FrameIdentityError(
            f"{int(frame[key].duplicated().sum())} duplicate {key!r} values; the row "
            f"order after sorting would depend on input order")

    cols = sorted(map(str, frame.columns))
    d = frame.reindex(columns=cols).sort_values(key, kind="mergesort")
    rows = [[encode_cell(v) for v in rec]
            for rec in d.astype(object).to_numpy().tolist()]
    payload = {"schema": FRAME_IDENTITY_SCHEMA, "key": key, "columns": cols,
               "n_rows": int(len(d)), "rows": rows}
    return hashlib.sha256(json.dumps(payload, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def frames_digest(frames: dict, *, key: str = "row_uid") -> dict:
    """`{name: digest}` for a mapping of frames, skipping `None`."""
    return {name: frame_digest(f, key=key) for name, f in sorted(frames.items())
            if f is not None}
