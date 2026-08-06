#!/usr/bin/env python3
"""contract_constants.py -- frozen bytes from the M00 contract, loaded not retyped.

PRODUCT SCAFFOLD built against fixtures. Carries no market claim and must not imply that
any edge, signal or tradable opportunity exists: fixtures render as fixtures.

Hand-transcribing contract prose into Python string literals is how a shell quietly drifts
from the contract it claims to enforce -- a stray dash or wrapped line and the "verbatim"
claim is false. This module instead reads
`experiments/market_program/M00_MARKET_PROGRAM_CONTRACT/TAXONOMY.json` at import time and
exposes exactly the substructures the market screen needs: the evidence ladder, the D024
execution-mode ladder, the hard-risk-control checklist, and the bounded final-state-archive
use classes with their caveat texts and hashes. `TAXONOMY_SHA256` is pinned so a change to
the frozen file is caught rather than silently absorbed -- import fails loudly if the file
moves under us, per the node prompt's frozen-bytes-govern-over-prose rule.

market_view.py imports these constants; it does not re-read the taxonomy file itself.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
TAXONOMY_PATH = (
    HERE.parent / "M00_MARKET_PROGRAM_CONTRACT" / "TAXONOMY.json"
)
TAXONOMY_SHA256 = "c83e25e783a4ee8642a26dd416362e46c2c34196ff8f8354977c28b72940a12c"
CONTRACT_SHA256 = "1152dcd3bf74000f700844bc8bfc0df25de61a067f59534a714ac4f2f20265de"


def _load_taxonomy() -> dict:
    raw = TAXONOMY_PATH.read_bytes()
    got = hashlib.sha256(raw).hexdigest()
    if got != TAXONOMY_SHA256:
        raise RuntimeError(
            "TAXONOMY.json bytes no longer match the pinned sha256 this node was told to "
            f"verify: got {got}, expected {TAXONOMY_SHA256}. Frozen bytes govern over "
            "prose -- refusing to render against an unverified contract file."
        )
    return json.loads(raw.decode("utf-8"))


_TAXONOMY = _load_taxonomy()

# ---------------------------------------------------------------------------------------
# evidence_ladder -- seven strictly ordered labels, taken verbatim from TAXONOMY.json.
# ---------------------------------------------------------------------------------------
LADDER_LABELS: tuple[dict, ...] = tuple(_TAXONOMY["evidence_ladder"]["labels"])
LADDER_RANK_BY_ID = {row["id"]: row["rank"] for row in LADDER_LABELS}
LADDER_IDS = tuple(row["id"] for row in LADDER_LABELS)
LADDER_TOP_RANK = max(row["rank"] for row in LADDER_LABELS)
PRODUCTION_ELIGIBLE = "PRODUCTION_ELIGIBLE"
assert PRODUCTION_ELIGIBLE in LADDER_IDS, "PRODUCTION_ELIGIBLE missing from taxonomy ladder"
assert LADDER_RANK_BY_ID[PRODUCTION_ELIGIBLE] == LADDER_TOP_RANK, (
    "PRODUCTION_ELIGIBLE is not the top rung; the actionability gate below assumes it is"
)

# ---------------------------------------------------------------------------------------
# execution_mode_ladder -- the D024 four-mode ladder, taken verbatim from TAXONOMY.json.
# ---------------------------------------------------------------------------------------
EXECUTION_MODES: tuple[dict, ...] = tuple(_TAXONOMY["execution_mode_ladder"]["modes"])
EXECUTION_MODE_IDS = tuple(row["id"] for row in EXECUTION_MODES)
EXECUTION_MODE_MEANING = {row["id"]: row["meaning"] for row in EXECUTION_MODES}
EXECUTION_MODE_GATE = {row["id"]: row.get("gate") for row in EXECUTION_MODES}
DEFAULT_EXECUTION_MODE = "SHADOW"  # D024: "Default and starting mode for every strategy."
assert DEFAULT_EXECUTION_MODE in EXECUTION_MODE_IDS

HARD_RISK_CONTROLS: tuple[str, ...] = tuple(
    _TAXONOMY["execution_mode_ladder"]["hard_risk_controls_before_any_non_shadow_order"]
)

# ---------------------------------------------------------------------------------------
# final_state_archive_ruling.permitted_uses -- the M00-Ux caveat texts and their frozen
# hashes, taken verbatim from TAXONOMY.json (not recomputed here -- the taxonomy's own
# caveat_sha256 field is trusted as-is, since it is itself inside the pinned file).
# ---------------------------------------------------------------------------------------
_ARCHIVE = _TAXONOMY["final_state_archive_ruling"]
M00_PERMITTED_USES: dict[str, dict] = {
    row["use_class"]: {
        "name": row["name"],
        "caveat_text": row["caveat_text"],
        "caveat_sha256": row["caveat_sha256"],
    }
    for row in _ARCHIVE["permitted_uses"]
}
M00_USE_CLASS_IDS = tuple(sorted(M00_PERMITTED_USES))
M00_PROHIBITED_USES: tuple[str, ...] = tuple(_ARCHIVE["prohibited_uses"])

# Only M00-U4 ("coarse cross-season price-level context ... descriptive display and
# sanity-checking only; never a feature, never a benchmark") is even shaped like something
# that could legitimately show up as a *label* on a market screen's descriptive panel. The
# other five use classes (coverage census, vig calibration, settlement inventory, fixture
# corpora, prior elicitation) describe research or engineering uses, not something a
# per-opportunity market view renders. market_view.py accepts ONLY M00-U4 on a T2-tier
# data point and rejects every other tier-T2 use as a contract violation at render time --
# this is this shell's own restriction, tighter than the six-use contract enumeration,
# adopted because C.2 prohibits every timing/benchmark use a market screen would otherwise
# be tempted to make of the archive.
M00_USE_CLASS_ACCEPTED_ON_SCREEN = "M00-U4"
assert M00_USE_CLASS_ACCEPTED_ON_SCREEN in M00_PERMITTED_USES
