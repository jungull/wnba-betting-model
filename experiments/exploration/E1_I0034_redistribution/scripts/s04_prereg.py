"""S04 -- HASH THE PREREGISTRATION.

PREREG.md is hashed here and RE-ASSERTED at the top of every later step.  If a single byte of it
changes after this point, every downstream script halts.
"""
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import redist_base as rb

PREREG = os.path.join(rb.OUT, "PREREG.md")
LOCK = os.path.join(rb.OUT, "_prereg.json")

CELLS = [
    "P01_LEAKAGE_minutes", "P01_LEAKAGE_fga", "P01_LEAKAGE_pts",
    "P02_TILT_minutes", "P02_TILT_fga", "P02_TILT_pts",
    "P03_GAIN_vs_BASE5_ORACLEABS_minutes", "P03_GAIN_vs_BASE5_ORACLEABS_fga",
    "P03_GAIN_vs_BASE5_ORACLEABS_pts",
    "P04_GAIN_vs_CHAMPION_ORACLEABS_minutes", "P04_GAIN_vs_CHAMPION_ORACLEABS_fga",
    "P04_GAIN_vs_CHAMPION_ORACLEABS_pts",
    "P05_POSITION_MATCH_minutes", "P06_NEGCONTROL_PSEUDOABSENCE_minutes",
]


def write():
    h = rb.sha256_file(PREREG)
    rec = {"prereg_path": "PREREG.md", "prereg_sha256": h,
           "n_bytes": os.path.getsize(PREREG),
           "n_cells": len(CELLS), "cells": CELLS,
           "primary_row_set": "RSP-W2 (REM rows, seasons 2023-2024)",
           "secondary_row_set": "RSP-W1 (REM rows, seasons 2022-2024) -- DECLARED SECONDARY",
           "seed": rb.SEED,
           "nulls": {
               "N1": "within-team-game shuffle of the candidate among REM rows",
               "N2": "paired block sign-flip on the per-row loss difference, team-game blocks",
               "N4": "permutation of FREED across team-games within season"},
           "absence_conditioning": ("REALISED. both pre-game injury sources are UNVERIFIABLE and "
                                    "are refused. every forecast cell is an ORACLE CEILING.")}
    with open(LOCK, "w", encoding="utf-8") as f:
        json.dump(rec, f, indent=1)
    print("PREREG sha256 = %s" % h)
    print("bytes = %d, cells = %d" % (rec["n_bytes"], rec["n_cells"]))
    return rec


def assert_unchanged():
    with open(LOCK, "r", encoding="utf-8") as f:
        rec = json.load(f)
    h = rb.sha256_file(PREREG)
    assert h == rec["prereg_sha256"], (
        "PREREG.md CHANGED after hashing.\n  locked %s\n  now    %s" % (rec["prereg_sha256"], h))
    return rec


if __name__ == "__main__":
    write()
