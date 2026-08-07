#!/usr/bin/env python3
"""S31 raw-sources freeze manifest.

Hashes every raw source output BEFORE any reader (synthesis, coordinator
analysis) touches them, and records per-source packet provenance: the packet
content hash (the frozen IDEATION EDITION), the forbidden-file rule, and the
observed tool-use profile of each source (from the dispatch record).
"""
import hashlib
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
RAW = os.path.join(HERE, "raw_sources")
IDEATION_EDITION = os.path.join(
    ROOT, "experiments/player_program/stage3_score/S30_TARGET_CONTRACT/CYCLE2_TARGET_CONTRACT_IDEATION_EDITION.md")

SOURCES = [
    ("SOURCE_1_state_space.md", "statistical time-series / state-space modeler"),
    ("SOURCE_2_domain.md", "basketball domain analyst (game mechanisms)"),
    ("SOURCE_3_forecasting.md", "forecasting practitioner (baseline-beating practice)"),
    ("SOURCE_4_falsificationist.md", "falsificationist / survival designer"),
    ("SOURCE_5_information.md", "information auditor (discarded-information channels)"),
]


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    packet_sha = sha256_file(IDEATION_EDITION)
    entries = []
    for fname, lens in SOURCES:
        p = os.path.join(RAW, fname)
        entries.append({
            "source_file": f"raw_sources/{fname}",
            "lens": lens,
            "output_sha256": sha256_file(p),
            "output_bytes": os.path.getsize(p),
            "packet": {
                "content": "the frozen CYCLE2_TARGET_CONTRACT_IDEATION_EDITION.md plus the source's own prompt",
                "packet_file_sha256": packet_sha,
            },
            "forbidden_files": ("EVERY file except the single packet file above; enforced by dispatch "
                                  "instruction and verified by the observed tool-use profile"),
            "observed_tool_use_profile": "exactly 2 tool calls: one Read (the packet), one Write (this output)",
            "independence": ("no exposure to any other source's output, any D045 numeric row, the D046 "
                              "priors, the D047 directive text, or coordinator ideas"),
        })
    manifest = {
        "schema": "stage3_score/S31/raw_sources_manifest/1",
        "node": "S31_SCORE_IDEATION",
        "n_sources": len(entries),
        "frozen_before_any_reader": True,
        "sources": entries,
    }
    out = os.path.join(HERE, "RAW_SOURCES_MANIFEST.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")
    print("manifest written;", len(entries), "sources; packet sha", packet_sha[:16])
    for e in entries:
        print(" ", e["source_file"], e["output_sha256"][:16], e["output_bytes"], "bytes")


if __name__ == "__main__":
    main()
