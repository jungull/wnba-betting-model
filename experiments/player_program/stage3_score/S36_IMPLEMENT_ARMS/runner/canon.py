#!/usr/bin/env python3
"""canon.py -- the S32B column-digest canonicalisation, stated in full and reproducible.

Epistemic status: IMPLEMENTATION. Unit/synthetic/identity/schema tests only; no comparative
historical performance is revealed.

This module exists to close the ONE documented gap S35 carried forward into S36:

    S35 VERIFICATION, one_documented_gap_carried_not_hidden:
      "the projected_team_off_possessions byte pin also carries a join_key_sha256; the pin states
       join_key_columns [game_id, team_id] but not the inter-column separator convention, so the
       join-key digest did NOT reproduce under this node's reading."
      obligation: "S36 must state the join-key separator convention explicitly when it recomputes
       byte pins under R10, so the pin becomes reproducible by a third party."

It is closed here BY MEASUREMENT, not by assertion, and WITHOUT changing any digest: the frozen
`join_key_sha256` values are reproduced bit-for-bit by the conventions written below. See
`BYTE_PIN_CANONICALISATION.md` for the search that established the two-column separator and
`tests/TESTS_canon.py` for the executable proof against all four frozen pins.

THE TWO SEPARATORS (they are different characters, which is exactly why the pin was ambiguous):

  * INTER-ROW separator  : U+001F  UNIT SEPARATOR      (joins one row's key to the next)
  * INTRA-KEY separator  : U+001E  RECORD SEPARATOR    (joins game_id to team_id WITHIN one key)

A single-column join key never exercises the intra-key separator, which is why the three
`score_baseline_rows` pins (join_key_column = "game_id") always reproduced while the one
two-column pin (join_key_columns = [game_id, team_id]) did not.
"""
from __future__ import annotations

import hashlib
from typing import Any, Iterable, Sequence

import numpy as np

#: joins successive rows of a column / key sequence
UNIT_SEP = "\x1f"
#: joins the components of a composite (multi-column) join key WITHIN one row
RECORD_SEP = "\x1e"

CANONICALISATION_STATEMENT = (
    "floats via repr(float(v)) (NaN->'nan'); ints via str(int(v)); timestamps via .isoformat(); "
    "else str(v); joined with U+001F; UTF-8; sha256 hexdigest"
)
JOIN_KEY_SEPARATOR_STATEMENT = (
    "composite join keys join their component columns WITHIN a row with U+001E (RECORD SEPARATOR) "
    "and join successive rows with U+001F (UNIT SEPARATOR); single-column join keys therefore "
    "reduce to the plain U+001F-joined column digest. Rows are ordered by the pin's own sort_rule "
    "before joining. Established by measurement at S36 against the frozen pin "
    "join_key_sha256=6b8b2709af3890c40a2fbc14eec36f02a5eae048aece1480ce7f3929126dd59b; no digest "
    "was changed to make it reproduce."
)


def canon_value(v: Any) -> str:
    """The S32B per-value canonicalisation. Order of the checks is load-bearing:
    numpy bools are integers to `isinstance`, and pandas NA / None must reach 'nan'."""
    if v is None:
        return "nan"
    if isinstance(v, (bool, np.bool_)):
        return str(bool(v))
    if isinstance(v, (float, np.floating)):
        return repr(float(v))
    if isinstance(v, (int, np.integer)):
        return str(int(v))
    if hasattr(v, "isoformat"):
        return v.isoformat()
    try:
        import pandas as pd  # local: keeps canon.py importable without pandas
        if v is pd.NA or (not isinstance(v, str) and pd.isna(v)):
            return "nan"
    except Exception:
        pass
    return str(v)


def column_digest(values: Iterable[Any]) -> str:
    """sha256 over the U+001F-joined canonicalised values, in the order given.

    The caller is responsible for applying the pin's sort_rule first -- ordering is part of the
    pin, not of this function, and hiding it here would let a caller silently digest a different
    row order."""
    return hashlib.sha256(
        UNIT_SEP.join(canon_value(v) for v in values).encode("utf-8")).hexdigest()


def join_key_digest(rows: Sequence[Sequence[Any]]) -> str:
    """sha256 over composite join keys.

    `rows` is a sequence of per-row component tuples, already in the pin's sort order. Each row's
    components are canonicalised and joined with U+001E; the rows are then joined with U+001F.
    A one-component key reduces exactly to `column_digest`."""
    keys = [RECORD_SEP.join(canon_value(c) for c in row) for row in rows]
    return hashlib.sha256(UNIT_SEP.join(keys).encode("utf-8")).hexdigest()


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_json_sha256(obj: Any) -> str:
    """The cycle-1 P35 canonicalisation used for card hashes and manifest digests."""
    import json
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
