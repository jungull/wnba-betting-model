"""contract.py -- load the M00 taxonomy AND its amendments, and verify both.

Reads the frozen bytes rather than trusting a class id typed into a detector. Before this
module existed, `board.py` hard-coded class-id strings, which is precisely how a product
surface drifts from the contract it claims to enforce -- a renamed class or a typo and the
board is emitting a label the taxonomy does not contain, silently.

`load()` composes `TAXONOMY.json` with `TAXONOMY_AMENDMENTS.json` and asserts:
  * the base file still hashes to the value the amendment record pins;
  * every amendment names a ledgered decision and a verbatim user authorization;
  * no amendment redefines an existing class id (additive only);
  * the reserved-terms ruling is untouched.

Any failure raises. A board that cannot verify its own taxonomy must not render.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
M00 = HERE.parent / "M00_MARKET_PROGRAM_CONTRACT"
TAXONOMY_PATH = M00 / "TAXONOMY.json"
AMENDMENTS_PATH = M00 / "TAXONOMY_AMENDMENTS.json"


@dataclass(frozen=True)
class Contract:
    classes: dict           # class_id -> class dict
    base_sha256: str
    amendment_version: int | None
    amended_class_ids: tuple[str, ...]
    reserved_terms: dict
    execution_modes: tuple[str, ...]
    default_execution_mode: str

    def is_class(self, class_id: str) -> bool:
        return class_id in self.classes

    def require(self, class_id: str) -> dict:
        if class_id not in self.classes:
            raise KeyError(
                f"'{class_id}' is not a class in the M00 taxonomy or its amendments. "
                f"Known: {sorted(self.classes)}. A rendering node may not mint a class."
            )
        return self.classes[class_id]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load() -> Contract:
    if not TAXONOMY_PATH.is_file():
        raise FileNotFoundError(f"M00 taxonomy missing at {TAXONOMY_PATH}")
    base_hash = _sha256(TAXONOMY_PATH)
    tax = json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))

    classes = {c["id"]: c for c in tax["opportunity_taxonomy"]["classes"]}
    amended: list[str] = []
    version = None

    if AMENDMENTS_PATH.is_file():
        am = json.loads(AMENDMENTS_PATH.read_text(encoding="utf-8"))
        version = am.get("version")

        pinned = am.get("base_sha256")
        if pinned != base_hash:
            raise RuntimeError(
                "TAXONOMY.json no longer matches the base_sha256 its amendment record pins:\n"
                f"  on disk : {base_hash}\n  pinned  : {pinned}\n"
                "The base contract changed under an amendment written against an older version. "
                "Refusing to compose a taxonomy from two files that disagree about the base."
            )

        auth = am.get("authorization") or {}
        if not auth.get("ledgered_decision") or not auth.get("verbatim"):
            raise RuntimeError(
                "The amendment record does not cite BOTH a ledgered decision and a verbatim "
                "user authorization. M00's amendment_procedure requires a ledgered decision "
                "citing user authorization; an amendment without both is a Severity A breach."
            )

        for c in am.get("new_classes", []):
            cid = c["id"]
            if cid in classes:
                raise RuntimeError(
                    f"amendment redefines existing class '{cid}'. Amendments are ADDITIVE only; "
                    "redefining a frozen class is not an amendment, it is a rewrite."
                )
            classes[cid] = c
            amended.append(cid)

        if am.get("unchanged") and "reserved_terms" not in " ".join(am["unchanged"]):
            raise RuntimeError("amendment must explicitly affirm reserved_terms are unchanged")

    reserved = tax["opportunity_taxonomy"]["reserved_terms"]
    if "TRUE_CROSS_BOOK_ARBITRAGE" not in reserved.get("arbitrage", ""):
        raise RuntimeError("the reserved-terms ruling on `arbitrage` is not intact")

    modes = tuple(m["id"] for m in tax["execution_mode_ladder"]["modes"])
    if "SHADOW" not in modes:
        raise RuntimeError("SHADOW is not in the execution-mode ladder")

    return Contract(
        classes=classes,
        base_sha256=base_hash,
        amendment_version=version,
        amended_class_ids=tuple(amended),
        reserved_terms=reserved,
        execution_modes=modes,
        default_execution_mode="SHADOW",
    )


if __name__ == "__main__":
    c = load()
    print(f"base sha256      : {c.base_sha256}")
    print(f"amendment version: {c.amendment_version}")
    print(f"classes ({len(c.classes)}):")
    for cid in c.classes:
        mark = "  [amended]" if cid in c.amended_class_ids else ""
        print(f"  - {cid}{mark}")
    print(f"execution modes  : {c.execution_modes}")
