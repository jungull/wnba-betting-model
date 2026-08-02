"""The canonical, unique, team-bearing prediction-obligation key.

This module is the SINGLE definition of the v4/v11 prediction key.  It exists because the
v10 gate was green while the real player path could not execute at all: `prediction_contract_v3`
restored dual-team obligations but kept the team-blind `row_uid = pg_uid(player_id, game_id)`,
so `cbs_real_frames_v2.build_player_frame(2024, require_attested=True)` dies at the master join
with `MergeError: Merge keys are not unique in left dataset`.

Reproduced verbatim before this module was written::

    MergeError: Merge keys are not unique in left dataset; not a one-to-one merge
    Duplicates in left:
        game_id  player_id
    1022300169    1641653
    1022400175     203824
    ...

Across 2021-2026, 28 rows share 14 team-blind ids; through 2024, 22 rows form 11 collision
groups.  A merge fix alone is insufficient, because the team-blind id also silently corrupts
coverage accounting, the runner's reindexing, the master starter/DNP join, and team-history
appearance evidence.  So the key itself changes, once, everywhere.

Three names, deliberately distinct
----------------------------------

``row_uid``
    The CANONICAL UNIQUE PREDICTION KEY: ``sha256(player_id, game_id, team_id)``.  Exactly one
    forecast is owed per value.  Everything downstream -- contract, frame, universe, manifest,
    runner, prediction, exclusion, coverage, scoring, provenance -- keys on this.

``player_game_uid``
    The LEGACY player-game linkage, ``sha256(player_id, game_id)``, byte-identical to v2's
    ``pg_uid``.  Retained so v1/v2-era joins keep working.  It is NOT unique across obligations
    and must never be used as a primary key or as a coverage-accounting key again.

``obligation_uid``
    An explicit alias of ``row_uid``, kept because `prediction_contract_v3` introduced the name
    ``ob_uid`` and readers of that code will look for it.  Same bytes as ``row_uid``.

A design tension this module records rather than hides
------------------------------------------------------

The v1 contract chose a team-blind id ON PURPOSE.  `prediction_contract.row_uid`'s own docstring
says it is derived from ``(player_id, game_id)`` only, "not from date, team or season, all of
which can be restated or corrected later", so that a uid does not move when a team is restated.

That reasoning is real and is NOT refuted here: if a trade is later corrected in the source data,
a v4 ``row_uid`` WILL move, whereas a v2 one would not.  The v4 key accepts that cost because the
alternative is strictly worse -- a key that cannot uniquely name the thing being predicted cannot
support a merge, a coverage count, or a scoring join, and the v10 failure is what that costs in
practice.  Stability of a name is worth less than uniqueness of a referent.  The exposure is
bounded and stated: it is a re-keying risk under retroactive trade correction, and it is the
reason `team_id_source` is recorded alongside every emitted key.
"""

from __future__ import annotations

import hashlib

#: Registered identifier for this key definition.  Consumers assert on it so that a frame built
#: under a different key rule can never be silently adopted.
OBLIGATION_KEY_ID = "cbs_obligation_key/1"

#: The exact field order hashed for the canonical key.  Recorded so a receipt can prove which
#: order produced a given digest.
CANONICAL_KEY_FIELDS = ("player_id", "game_id", "team_id")

#: The exact field order hashed for the retained legacy linkage id.
LEGACY_KEY_FIELDS = ("player_id", "game_id")

ROW_UID_PREFIX = "ob_"
PLAYER_GAME_UID_PREFIX = "pg_"

#: Digest width, matching every other uid in this repository.
_DIGEST_HEX = 16


def stable_hash(*parts: object) -> str:
    """Byte-identical to `prediction_contract.stable_hash` / `prediction_contract_v2.stable_hash`.

    Reimplemented here rather than imported so that this module has no import-time dependency
    on a registered, immutable contract module.  `tests/test_cbs_obligation_key.py` asserts the
    equality against both originals; if either ever drifts, that test fails rather than this
    module silently diverging.
    """
    h = hashlib.sha256()
    for p in parts:
        h.update(str(p).encode("utf-8"))
        h.update(b"\x1f")
    return h.hexdigest()[:_DIGEST_HEX]


def row_uid(player_id, game_id, team_id) -> str:
    """The canonical unique prediction obligation key.

    Team-bearing by construction: a player traded mid-season owes two DIFFERENT teams a forecast
    in their head-to-head game, and those are two obligations, not one.
    """
    return ROW_UID_PREFIX + stable_hash(int(player_id), str(game_id), int(team_id))


#: Explicit alias.  Same bytes as `row_uid`; kept for readers of `prediction_contract_v3.ob_uid`.
def obligation_uid(player_id, game_id, team_id) -> str:
    """Alias of :func:`row_uid`.  Identical output; provided for naming continuity."""
    return row_uid(player_id, game_id, team_id)


def player_game_uid(player_id, game_id) -> str:
    """The retained legacy player-game linkage id, byte-identical to v2's ``pg_uid``.

    NOT unique across obligations.  Never a primary key, never a coverage key.
    """
    return PLAYER_GAME_UID_PREFIX + stable_hash(int(player_id), str(game_id))


def v3_ob_uid_equivalent(team_id, player_id, game_id) -> str:
    """`prediction_contract_v3.ob_uid` reproduced, for diffing v3 against v4.

    v3 hashed ``(team_id, player_id, game_id)``; v4 hashes ``(player_id, game_id, team_id)`` per
    the supervisor's registered field order.  The two are therefore DIFFERENT digests for the
    same obligation.  That is intentional and must not be papered over: v4's receipt maps between
    them explicitly rather than allowing a v3 digest to be mistaken for a v4 one.
    """
    return "ob_" + stable_hash(int(team_id), int(player_id), str(game_id))


def assert_unique_canonical_keys(df, where: str = "frame") -> None:
    """Fail closed if ``row_uid`` is not unique.

    This is the check whose absence let v10 ship a green gate over an unexecutable path.  It is
    deliberately an unconditional raise, not a warning and not a dropped duplicate: silently
    de-duplicating is exactly how v2 deleted 14 obligations without a receipt.
    """
    if "row_uid" not in df.columns:
        raise KeyError(f"{where}: no 'row_uid' column; cannot verify obligation uniqueness")
    dup = df["row_uid"].duplicated(keep=False)
    n = int(dup.sum())
    if n:
        sample = df.loc[dup, ["row_uid"]].head(10).to_dict("records")
        raise ValueError(
            f"{where}: canonical row_uid is NOT unique -- {n} rows share a key "
            f"({OBLIGATION_KEY_ID}). This is the v10 defect. Sample: {sample}"
        )


def key_receipt() -> dict:
    """A machine-readable description of the key rule, for embedding in manifests/receipts."""
    return {
        "obligation_key_id": OBLIGATION_KEY_ID,
        "canonical_key": "row_uid",
        "canonical_key_fields": list(CANONICAL_KEY_FIELDS),
        "canonical_key_prefix": ROW_UID_PREFIX,
        "legacy_linkage_key": "player_game_uid",
        "legacy_key_fields": list(LEGACY_KEY_FIELDS),
        "legacy_key_prefix": PLAYER_GAME_UID_PREFIX,
        "alias": "obligation_uid",
        "digest": "sha256, first 16 hex chars, 0x1f-delimited utf-8 fields",
        "supersedes": (
            "prediction_contract_v2.pg_uid as the primary key, and "
            "prediction_contract_v3.ob_uid as the obligation digest (different field order)"
        ),
        "known_exposure": (
            "a retroactive trade correction moves a v4 row_uid, which a team-blind v2 key would "
            "not; accepted deliberately because a non-unique key cannot support merge, coverage "
            "or scoring joins"
        ),
    }
