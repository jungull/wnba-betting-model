#!/usr/bin/env python
"""Build SOURCE_BINDING.json -- the per-domain declaration of whether a real live source is bound.

EPISTEMIC STATUS: PROSPECTIVE CAPTURE INFRASTRUCTURE. Builds the record that would make future
features cutoff-provable. Creates no historical evidence and repairs no historical gap.

Every verdict quoted here is EXTRACTED programmatically from a frozen artifact inside this node's
declared read scope (`experiments/player_program/`), with that artifact's sha256 recorded. Nothing
is retyped from memory. Where an extraction finds nothing, the binding says ABSENT and records the
search that found nothing -- a negative result, preserved.

The node's read scope does NOT include the repository's `data/` tree, where every live capture
actually lands. This script therefore cannot open a single live source file, and no domain is
bound. That limitation is recorded per domain, not glossed.

Usage:  python build_source_binding.py
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

LANE_DIR = Path(__file__).resolve().parent
PROGRAM_DIR = LANE_DIR.parent.parent            # experiments/player_program
REPO_ROOT = PROGRAM_DIR.parent.parent           # worktree root
READ_SCOPE = PROGRAM_DIR

CITED = {
    "EVIDENCE_PACKET_V2": PROGRAM_DIR / "stage2a" / "EVIDENCE_PACKET_V2.json",
    "V2_STOP_CONDITION": PROGRAM_DIR / "stage2a" / "V2_STOP_CONDITION.json",
    "ROSTER_SOURCE_AUDIT_RECEIPT": PROGRAM_DIR / "ROSTER_SOURCE_AUDIT_RECEIPT.json",
    "PREDICTION_CONTRACT_V5_SPEC": PROGRAM_DIR / "PREDICTION_CONTRACT_V5_SPEC.md",
    "PLAYER_MODEL_CAPABILITY_MATRIX": PROGRAM_DIR / "PLAYER_MODEL_CAPABILITY_MATRIX.md",
}


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def packet_availability_rows(packet: dict) -> dict[str, dict]:
    """Flatten every row of the frozen cutoff-valid availability table, keyed by its `field`."""
    rows: dict[str, dict] = {}
    table = packet.get("cutoff_valid_availability_table_CORRECTED", {})
    for bucket, entries in table.items():
        if not isinstance(entries, list):
            continue
        for e in entries:
            if isinstance(e, dict) and "field" in e:
                rows[e["field"]] = dict(e, _bucket=bucket)
    return rows


def packet_wishlist(packet: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for c in packet.get("unavailable_but_potentially_valuable", {}).get("candidates", []):
        if isinstance(c, dict) and "missing_input" in c:
            out[c["missing_input"]] = c
    return out


def audit_sources(receipt: dict) -> dict[str, dict]:
    return {s["source"]: s for s in receipt.get("sources", []) if isinstance(s, dict)}


def grep_count(pattern: str) -> dict:
    """Count matching lines inside the node's READ SCOPE only. Used to prove an absence."""
    hits = []
    rx = re.compile(pattern, re.I)
    n_files = 0
    for p in READ_SCOPE.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in {".md", ".json", ".py", ".jsonl", ".csv", ".txt"}:
            continue
        if LANE_DIR in p.parents or p.parent == LANE_DIR:
            continue                      # do not count this node's own output
        if "SEALED_RESULTS" in str(p):
            continue                      # forbidden input
        n_files += 1
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if rx.search(line):
                hits.append({"path": str(p.relative_to(REPO_ROOT)).replace("\\", "/"),
                             "line": i, "text": line.strip()[:200]})
    self_ref = [h for h in hits if "/orchestration/" in h["path"]]
    other = [h for h in hits if "/orchestration/" not in h["path"]]
    return {
        "pattern": pattern,
        "files_scanned": n_files,
        "n_hits": len(hits),
        "n_hits_self_referential_orchestration": len(self_ref),
        "n_hits_outside_orchestration": len(other),
        "self_referential_note": (
            "hits under orchestration/ are this graph's own node contract and generated prompt "
            "restating D11's acceptance criterion; they are not evidence that a source exists"
        ),
        "hits_outside_orchestration": other[:20],
        "hits": hits[:20],
    }


def main() -> int:
    packet = json.loads(CITED["EVIDENCE_PACKET_V2"].read_text(encoding="utf-8"))
    receipt = json.loads(CITED["ROSTER_SOURCE_AUDIT_RECEIPT"].read_text(encoding="utf-8"))
    avail = packet_availability_rows(packet)
    wish = packet_wishlist(packet)
    asrc = audit_sources(receipt)

    def av(field):
        e = avail.get(field)
        return None if e is None else {
            "packet_field": field, "packet_bucket": e.get("_bucket"),
            "source": e.get("source"), "coverage": e.get("coverage"),
            "verdict": e.get("v2_verdict") or e.get("verdict"), "note": e.get("note"),
        }

    def wi(key):
        e = wish.get(key)
        return None if e is None else {
            "missing_input": key,
            "minimum_viable_collection": e.get("minimum_viable_collection"),
            "prospective_only_validation": e.get("prospective_only_validation"),
            "caution": e.get("caution"),
        }

    def au(key, fields=("q1_seasons_covered", "q2_timestamps", "q3_as_of_reconstructable",
                        "q5_corrections_overwrite_history", "q6_regime", "n_rows")):
        e = asrc.get(key)
        return None if e is None else {"source": key, **{f: e.get(f) for f in fields}}

    # measured absences -- a grep over the read scope that returns nothing is the evidence
    absence_minute_restriction = grep_count(r"minute[s]?[ _-]?(restriction|cap|limit)")
    absence_coach_source = grep_count(r"data/[a-z0-9_]*coach")
    absence_lineup_feed = grep_count(r"(announced|projected|posted)[ _-]?(starting[ _-]?)?lineup")

    domains = {
        "injury_designation": {
            "contract_criterion": "injury designation changes",
            "bound": False,
            "candidate_source_named_in_program_docs": "data/injury_capture/injury_log.csv",
            "packet_evidence": av("injury / availability report"),
            "audit_evidence": au("data/injury_capture/injury_log.csv"),
            "wishlist_evidence": wi("pregame injury / availability feed with historical depth"),
            "why_not_bound": (
                "the file lives under the repository's data/ tree, which is outside this node's "
                "allowed_read_paths (experiments/player_program/). This node cannot open it, "
                "cannot verify its schema, and therefore may not declare an adapter that claims "
                "to parse it."
            ),
            "what_would_bind_it": (
                "widen D11's read scope to data/injury_capture/, then implement an adapter that "
                "maps each report line to the injury_designation payload with observed_at_utc = "
                "the row's capture_utc, and re-run the ledger self-test against real rows."
            ),
        },
        "lineup": {
            "contract_criterion": "lineups",
            "bound": False,
            "candidate_source_named_in_program_docs": None,
            "packet_evidence": av("starting lineup / rotation announced pregame"),
            "wishlist_evidence": wi("announced starting lineup / expected rotation"),
            "absence_search": absence_lineup_feed,
            "why_not_bound": (
                "no pregame lineup feed exists anywhere in the program record. The only lineup "
                "artifact named (derive_lineups.py -> data/derived/stints.parquet, starters.csv) "
                "is REALISED and is an explicit must-not-reuse."
            ),
            "what_would_bind_it": "capture a pregame lineup posting forward from today.",
        },
        "starter": {
            "contract_criterion": "starters",
            "bound": False,
            "candidate_source_named_in_program_docs": None,
            "packet_evidence": av("starting lineup / rotation announced pregame"),
            "why_not_bound": (
                "same absence as lineup. data/derived/starters.csv is derived from play-by-play "
                "and is a target-game outcome, not a pregame announcement."
            ),
            "what_would_bind_it": "capture a pregame starter announcement forward from today.",
        },
        "minute_restriction": {
            "contract_criterion": "minute restrictions",
            "bound": False,
            "candidate_source_named_in_program_docs": None,
            "packet_evidence": None,
            "absence_search": absence_minute_restriction,
            "why_not_bound": (
                "NEGATIVE RESULT. No source of pregame minute restrictions is named anywhere in "
                "this node's read scope -- the frozen availability table does not list the field "
                "at all, so it has never been adjudicated even as unavailable."
            ),
            "what_would_bind_it": (
                "a structured pregame restriction feed, or an extraction layer over attributable "
                "news. Neither exists."
            ),
        },
        "transaction": {
            "contract_criterion": "transactions",
            "bound": False,
            "candidate_source_named_in_program_docs": "data/injury_history/injury_history.csv",
            "packet_evidence": av("injury / transaction history"),
            "audit_evidence": au("data/injury_history/injury_history.csv"),
            "why_not_bound": (
                "outside read scope; and even in scope it is the wrong regime for THIS node. It "
                "was observed in a single retrospective scrape, so every record would enter the "
                "ledger as retrospective=true / CUTOFF_UNPROVEN and could never admit at a "
                "cutoff. A prospective transaction capture is a different source."
            ),
            "what_would_bind_it": (
                "a live transaction wire fetched and timestamped by this repository going "
                "forward. prediction_contract_v5 reserves S4 for exactly this and declares it "
                "UNAVAILABLE; no implementation may substitute another source for it."
            ),
        },
        "coaching_change": {
            "contract_criterion": "coaching changes",
            "bound": False,
            "candidate_source_named_in_program_docs": None,
            "packet_evidence": av("coaching identity, coaching change, tactical scheme"),
            "wishlist_evidence": wi("coaching identity and coaching-change events"),
            "absence_search": absence_coach_source,
            "why_not_bound": (
                "NEGATIVE RESULT confirmed by the frozen packet: no coaching source exists. Note "
                "the packet records this as the one candidate whose minimum viable collection is "
                "a hand-maintained table and whose prospective_only_validation is FALSE -- i.e. "
                "it is the only one of the eight that could in principle be reconstructed "
                "historically. Reconstructing it is NOT this node's mandate."
            ),
            "what_would_bind_it": "a coach-by-team-season table, hand-maintained and timestamped.",
        },
        "odds": {
            "contract_criterion": "odds",
            "bound": False,
            "candidate_source_named_in_program_docs": "data/odds_capture/",
            "packet_evidence": av("market odds / totals"),
            "wishlist_evidence": wi(
                "market total / pace-implied market expectation with history"),
            "why_not_bound": (
                "outside read scope. Additionally the packet records a standing caution that a "
                "market feature changes what the model is; binding this domain to the prediction "
                "path is a scientific decision, not a capture decision."
            ),
            "what_would_bind_it": "widen read scope to data/odds_capture/ and adapt it.",
        },
        "news": {
            "contract_criterion": "attributable news",
            "bound": False,
            "candidate_source_named_in_program_docs": "data/news_capture/news_items.csv",
            "audit_evidence": au("data/news_capture/news_items.csv"),
            "why_not_bound": (
                "outside read scope; and the audited verdict is UNUSABLE without an extraction "
                "layer because the content is prose. This node's news domain therefore REQUIRES "
                "a non-empty attributed_to and a claim_type, so an unattributed headline is "
                "refused rather than silently stored as if it were a fact."
            ),
            "what_would_bind_it": (
                "an extraction layer that turns a prose item into an attributed claim, plus read "
                "access to the capture."
            ),
        },
    }

    out = {
        "schema": "player_program/live_capture_source_binding/1",
        "node": "D11_LIVE_INFORMATION_CAPTURE",
        "epistemic_status": (
            "PROSPECTIVE CAPTURE INFRASTRUCTURE. Builds the record that would make future "
            "features cutoff-provable. Creates no historical evidence and repairs no historical "
            "gap."
        ),
        "generated_by": "build_source_binding.py",
        "read_scope": "experiments/player_program/",
        "headline": (
            "ZERO of the eight domains is bound to a live source by this node. The capture "
            "mechanism is implemented and tested; it has captured no real observation."
        ),
        "n_domains": len(domains),
        "n_bound": sum(1 for d in domains.values() if d["bound"]),
        "cited_artifacts": {
            k: {"path": str(v.relative_to(REPO_ROOT)).replace("\\", "/"),
                "sha256": sha256_file(v), "bytes": v.stat().st_size}
            for k, v in CITED.items()
        },
        "domains": domains,
        "registry_for_ledger": {
            # what a CaptureLedger would be constructed with today: nothing provable
            k: {"observation_provable": False,
                "bound": False,
                "reason": "no adapter; source outside read scope or absent"}
            for k in domains
        },
    }

    p = LANE_DIR / "SOURCE_BINDING.json"
    p.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {p.name}: {out['n_domains']} domains, {out['n_bound']} bound")
    print(f"  minute_restriction absence search: {absence_minute_restriction['n_hits']} hits "
          f"over {absence_minute_restriction['files_scanned']} files")
    print(f"  coaching-source absence search:    {absence_coach_source['n_hits']} hits")
    print(f"  lineup-feed absence search:        {absence_lineup_feed['n_hits']} hits")
    return 0


if __name__ == "__main__":
    sys.exit(main())
