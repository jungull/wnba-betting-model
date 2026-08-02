#!/usr/bin/env python3
"""cbs_identity_v3.py — `cbs_frame_identity/3`: reject before hashing.

WHY A `/3`
----------
`cbs_frame_identity.py` (`/2`, frozen under `contract_baseline_suite_v9`) closed
the two collisions v8 had — a null hashing like an empty string, an integer
hashing like its own text form. It did so by type-tagging every *cell*. It did
not type-tag the two things that sit either side of a cell: the **column label**
it lives under, and the **container** it may live inside. Three collisions
survived, and all three are reachable without exotic input.

**(a) Integer-labelled columns are silently DROPPED.**
`/2`'s `frame_digest` does::

    cols = sorted(map(str, frame.columns))
    d = frame.reindex(columns=cols)

`map(str, ...)` turns the integer label `1` into the string `"1"`, and
`reindex(columns=["1", ...])` then looks for a column *named* `"1"`, which does
not exist. Pandas supplies an all-NaN column instead. The real column's contents
never reach the hash at all, so **any two frames that differ only inside
integer-labelled columns share an identity**::

    A = pd.DataFrame({"row_uid": ["r1"]}); A[1] = [10]
    B = pd.DataFrame({"row_uid": ["r1"]}); B[1] = [20]
    fid.frame_digest(A) == fid.frame_digest(B)     # -> True under /2

This is worse than an aliasing bug. It is not that two different things hash
alike by accident; it is that a whole column is invisible to the check that
exists to notice a changed column.

**(b) Mapping keys `1` and `"1"` alias inside a dict cell.**
`/2`'s `encode_cell` type-tags the dict's *values* and then renders its *keys*
with `str(k)`, which is precisely the defect `/2` was written to remove — moved
one level down::

    fid.frame_digest(F({1: "a"})) == fid.frame_digest(F({"1": "a"}))   # True

**(c) A list and a tuple are the same `["seq", ...]`.**
`/2` funnels `list`, `tuple` and `np.ndarray` through one `"seq"` tag, so a
container swap is invisible::

    fid.frame_digest(F([1, 2])) == fid.frame_digest(F((1, 2)))          # True

WHAT `/3` DOES INSTEAD
----------------------
The supervisor's stated contract, implemented literally and as the DEFAULT:
**string-only column names, scalar-only cells, rejected BEFORE hashing.**

Rejection rather than richer encoding is the right shape here because all three
collisions come from the same source: the encoder was asked to flatten a
structure whose distinctions the digest could not carry. Encoding harder only
moves the ambiguity — a `/3` that tagged containers would still have to decide
whether `np.int64(1)` and `1` are the same mapping key, and the CBS frames have
no legitimate use for a container cell or a non-string column label anyway. So
the ambiguous input never reaches the hash. Nothing is hashed until the frame has
been proved to contain only things this digest can faithfully distinguish, which
means a rejected frame produces **no identity at all** rather than a weak one.

`STRICT_CONTAINERS` mode is offered for callers outside the CBS real path who
genuinely carry container cells. It type-tags container kinds and encodes mapping
keys with the same type-preserving encoder used for values, so (b) and (c) are
distinguished rather than refused. It is NOT the default and the real path must
not select it: the mode is part of the hashed payload, so a strict digest and a
scalar-only digest of the same frame are different strings and cannot be
confused for one another.

WHAT IS STILL DELIBERATELY NOT DISTINGUISHED
--------------------------------------------
Everything `/2` chose not to distinguish, for `/2`'s reasons, unchanged:

* All null flavours (`None`, `np.nan`, `pd.NaT`, `pd.NA`) collapse to one token.
  Which one a frame carries is pandas dtype plumbing that changes under an
  innocuous `reindex` or `concat`.
* Row order and column order. Rows sort by `row_uid`, columns sort by name; a
  shuffled frame is the same artifact. The runners sort internally, so this is a
  required property, and it is what makes the digest a statement about content.

And everything `/2` refused is still refused: a frame with no key column, a null
key, or a duplicated key has no well-defined canonical order and gets no digest.
`/3` adds one refusal in the same spirit — a **duplicated column label**, whose
`reindex` result depends on input order.
"""

from __future__ import annotations

import collections.abc as _abc
import datetime as _dt
import hashlib
import json

import numpy as np
import pandas as pd

FRAME_IDENTITY_SCHEMA = "cbs_frame_identity/3"

#: the schema this one supersedes, named so a reader can find the diff
SUPERSEDES = "cbs_frame_identity/2"

#: the single token every null flavour collapses to (unchanged from /2)
NULL_TOKEN = ["null", ""]

#: default mode: string-only column names, scalar-only cells, rejected first
SCALAR_ONLY = "scalar_only"
#: opt-in mode: containers admitted, type-tagged by kind, mapping keys encoded
STRICT_CONTAINERS = "strict_containers"
MODES = (SCALAR_ONLY, STRICT_CONTAINERS)

#: the mode the CBS real path must use, named so the requirement is greppable
REAL_PATH_MODE = SCALAR_ONLY


class FrameIdentityError(RuntimeError):
    """A frame cannot be given a canonical identity."""


class NonStringColumnLabel(FrameIdentityError):
    """A column label is not a `str`, so `str(label)` would alias it.

    Raised BEFORE hashing. Under `/2` such a column was not merely aliased, it
    was dropped: `reindex` on the stringified name found nothing and filled NaN,
    so the column's contents never entered the digest.
    """


class NonScalarCell(FrameIdentityError):
    """A cell holds a list, tuple, dict, set or ndarray.

    Raised BEFORE hashing. Under `/2` a list and a tuple shared the `"seq"` tag,
    and a mapping key `1` was rendered `str(1)` and aliased its own text form.
    """


class DuplicateColumnLabel(FrameIdentityError):
    """Two columns share a label, so the canonical column order is ambiguous."""


# --------------------------------------------------------------------------
# cell encoding
# --------------------------------------------------------------------------

def _is_null(v) -> bool:
    """True for every null flavour, without raising on array-likes.

    `pd.isna` returns an ARRAY for a list or ndarray cell and `bool()` of that
    raises, so a non-scalar answer is resolved as "not null" rather than letting
    the exception escape. Such a cell is rejected later by the scalar contract;
    it must not blow up the check that is on its way to rejecting it.
    """
    if v is None or v is pd.NaT:
        return True
    try:
        res = pd.isna(v)
    except (TypeError, ValueError):
        return False
    return bool(res) if isinstance(res, (bool, np.bool_)) else False


def is_container(v) -> bool:
    """True for the cell shapes the scalar-only contract refuses.

    Tested through `collections.abc` rather than a fixed tuple of types so that
    a `namedtuple`, a `deque`, an `OrderedDict` or any other sequence/mapping/set
    is caught by the same rule. `str`, `bytes` and `bytearray` are sequences in
    the abstract sense but are scalars for this purpose and are excluded.
    """
    if isinstance(v, (str, bytes, bytearray)):
        return False
    if isinstance(v, np.ndarray):
        return True
    return isinstance(v, (_abc.Mapping, _abc.Set, _abc.Sequence))


def _encode_scalar(v) -> list:
    """One scalar cell -> `[type_tag, text]`. `/2`'s encoding, unchanged."""
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
    return ["repr", f"{type(v).__module__}.{type(v).__name__}:{v!r}"]


def _container_tag(v) -> str:
    """The kind tag for a container, so a list and a tuple cannot share one."""
    if isinstance(v, np.ndarray):
        return "ndarray"
    if isinstance(v, _abc.Mapping):
        return "map" if isinstance(v, dict) else f"map:{type(v).__name__}"
    if isinstance(v, frozenset):
        return "frozenset"
    if isinstance(v, _abc.Set):
        return "set"
    if isinstance(v, tuple):
        return "tuple"
    if isinstance(v, list):
        return "list"
    return f"seq:{type(v).__name__}"


def encode_cell(v, *, mode: str = SCALAR_ONLY) -> list:
    """One cell -> `[type_tag, text]`, null-distinct and type-preserving.

    Under the default `SCALAR_ONLY` mode a container cell RAISES rather than
    being flattened, so no ambiguous value ever reaches the hash.
    """
    if mode not in MODES:
        raise FrameIdentityError(f"mode {mode!r} not in {MODES}")
    if is_container(v):
        if mode == SCALAR_ONLY:
            raise NonScalarCell(
                f"a cell holds a {type(v).__name__}, and the scalar-only identity "
                f"contract refuses it BEFORE hashing. Under {SUPERSEDES} a list and "
                f"a tuple shared one 'seq' tag and a mapping key 1 was rendered as "
                f"str(1), so a container swap could keep a frame's identity. Flatten "
                f"the column into scalar columns, or pass mode={STRICT_CONTAINERS!r} "
                f"if you are outside the CBS real path and genuinely need containers.")
        tag = _container_tag(v)
        if isinstance(v, _abc.Mapping):
            # keys go through the SAME type-preserving encoder as values, so a
            # key 1 and a key "1" are ["int","1"] and ["str","1"] and differ
            items = [[encode_cell(k, mode=mode), encode_cell(x, mode=mode)]
                     for k, x in v.items()]
            items.sort(key=lambda kv: json.dumps(kv[0], separators=(",", ":")))
            return [tag, json.dumps(items, separators=(",", ":"))]
        if isinstance(v, _abc.Set):
            # a set has no order of its own; sort the ENCODED elements so the
            # digest does not depend on iteration order
            enc = sorted((json.dumps(encode_cell(x, mode=mode), separators=(",", ":"))
                          for x in v))
            return [tag, json.dumps(enc, separators=(",", ":"))]
        seq = v.tolist() if isinstance(v, np.ndarray) else list(v)
        return [tag, json.dumps([encode_cell(x, mode=mode) for x in seq],
                                separators=(",", ":"))]
    return _encode_scalar(v)


# --------------------------------------------------------------------------
# the pre-hash contract
# --------------------------------------------------------------------------

def require_string_columns(frame: pd.DataFrame) -> list[str]:
    """Every column label must be a `str`, and no label may repeat.

    Returns the sorted label list. Raises before any cell is touched.
    """
    bad = [(i, c) for i, c in enumerate(frame.columns) if not isinstance(c, str)]
    if bad:
        raise NonStringColumnLabel(
            f"{len(bad)} column label(s) are not strings: "
            f"{[(i, c, type(c).__name__) for i, c in bad[:5]]}. "
            f"{SUPERSEDES} stringified labels with str() and then reindexed on the "
            f"stringified name, which does not exist — pandas filled an all-NaN "
            f"column, so the real column's VALUES never entered the digest and two "
            f"frames differing only inside an integer-labelled column hashed alike. "
            f"Rename these columns to strings before asking for an identity.")
    labels = [str(c) for c in frame.columns]
    seen, dup = set(), []
    for c in labels:
        (dup.append(c) if c in seen else seen.add(c))
    if dup:
        raise DuplicateColumnLabel(
            f"duplicated column label(s) {sorted(set(dup))}: the canonical column "
            f"order would depend on input order, so no stable identity exists")
    return sorted(labels)


def require_scalar_cells(frame: pd.DataFrame, *, max_report: int = 5) -> int:
    """No cell may be a list, tuple, dict, set or ndarray. Raises before hashing.

    Returns the number of cells inspected, so a caller can record that the scan
    actually happened rather than trusting that it did.
    """
    offenders: list[tuple[int, str, str]] = []
    n = 0
    for col in frame.columns:
        series = frame[col]
        n += len(series)
        if series.dtype != object:
            # a non-object dtype cannot hold a python container, so the per-cell
            # scan is skipped rather than paid for on every numeric column
            continue
        for i, v in enumerate(series.to_numpy(dtype=object)):
            if is_container(v):
                if len(offenders) < max_report:
                    offenders.append((i, str(col), type(v).__name__))
    if offenders:
        raise NonScalarCell(
            f"container cell(s) found at (row_position, column, type) "
            f"{offenders}: the scalar-only identity contract refuses them BEFORE "
            f"hashing. Under {SUPERSEDES} a list and a tuple shared the 'seq' tag "
            f"and a mapping key 1 aliased the string '1', so such a cell could be "
            f"swapped without moving the frame's identity.")
    return n


def require_digestible(frame: pd.DataFrame, *, key: str = "row_uid",
                       mode: str = SCALAR_ONLY) -> dict:
    """Prove a frame CAN be given a faithful identity. Nothing is hashed here.

    This is the whole point of `/3`: the checks run first and stand alone, so a
    frame that cannot be faithfully encoded is rejected rather than being given a
    weak identity. Returns a receipt describing what was checked.
    """
    if mode not in MODES:
        raise FrameIdentityError(f"mode {mode!r} not in {MODES}")
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
    cols = require_string_columns(frame)
    n_cells = require_scalar_cells(frame) if mode == SCALAR_ONLY else None
    return {"receipt": "frame_identity_precheck/1", "ok": True,
            "schema": FRAME_IDENTITY_SCHEMA, "mode": mode, "key": key,
            "n_rows": int(len(frame)), "columns": cols,
            "string_columns_verified": True,
            "scalar_cells_verified": mode == SCALAR_ONLY,
            "n_cells_scanned": n_cells}


# --------------------------------------------------------------------------
# the digest
# --------------------------------------------------------------------------

def frame_digest(frame: pd.DataFrame, *, key: str = "row_uid",
                 mode: str = SCALAR_ONLY) -> str:
    """A canonical, order-independent, type-preserving digest of a frame.

    The contract is checked FIRST and in full; only a frame that passes is
    hashed. Sorting on `key` makes the digest independent of row order and
    sorting the labels makes it independent of column order — everything else
    about the content is inside the hash, including the mode, so a scalar-only
    digest and a strict-container digest of the same frame are different strings.
    """
    require_digestible(frame, key=key, mode=mode)
    # labels are proved to be strings, so this reindex is exact rather than a
    # lookup on a stringified name that may match nothing
    cols = sorted(frame.columns)
    d = frame.reindex(columns=cols).sort_values(key, kind="mergesort")
    rows = [[encode_cell(v, mode=mode) for v in rec]
            for rec in d.astype(object).to_numpy().tolist()]
    payload = {"schema": FRAME_IDENTITY_SCHEMA, "mode": mode, "key": key,
               "columns": cols, "n_rows": int(len(d)), "rows": rows}
    return hashlib.sha256(json.dumps(payload, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def frames_digest(frames: dict, *, key: str = "row_uid",
                  mode: str = SCALAR_ONLY) -> dict:
    """`{name: digest}` for a mapping of frames, skipping `None`."""
    return {name: frame_digest(f, key=key, mode=mode)
            for name, f in sorted(frames.items()) if f is not None}
