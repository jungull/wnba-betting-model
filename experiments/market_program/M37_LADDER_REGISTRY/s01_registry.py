# -*- coding: utf-8 -*-
"""M37 -- inventory every evidence-ladder assertion in the market lane.

E0-style diagnostic, NON-CLAIMING. Not a graph node; the same shape as M34/M35/M36.

WHY. M24 needed to gate staking on each opportunity class's M00 evidence-ladder rank and found
nothing to read: no machine-readable per-class ladder status exists anywhere. Before proposing
to build one, the honest first question is whether the labels are actually in use.

They are. A first pass over DECISION_LEDGER.jsonl found exactly ONE decision in 178 mentioning
any ladder label, which looked like the ladder was dead letter. That was wrong, and checking a
second source is what caught it: the labels appear across 14-19 market-lane artifacts each.
They are asserted in NODE REPORTS, and never adjudicated in the LEDGER.

WHAT THIS FILE CAN AND CANNOT DO, because the distinction is the whole point.

  It CAN inventory every place a ladder label is asserted, with the artifact, the class it is
  attached to where that is determinable, and the surrounding sentence.

  It CANNOT establish that a class HOLDS a label. Labels live in prose inside report bodies and
  JSON string fields, frequently NEGATED ("NOT YET -- MARKET_MECHANISM_SUPPORTED ... cannot be
  reached"). A regex that counted those as evidence of a label held would manufacture exactly
  the authority this programme lacks, which is worse than having no registry at all.

So the output is titled ASSERTIONS FOUND, never LABELS HELD, and it carries the polarity of
each mention where that can be read mechanically. Adjudication -- deciding which labels a class
actually holds -- is a ruling, and rulings belong in the ledger, made by a person or a
coordinator, not inferred by a scanner.
"""
from __future__ import annotations

import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
MP = os.path.abspath(os.path.join(HERE, ".."))
LEDGER = os.path.abspath(os.path.join(
    HERE, "..", "..", "player_program", "orchestration", "DECISION_LEDGER.jsonl"))

LABELS = [
    "MARKET_MECHANISM_SUPPORTED", "LINE_MOVEMENT_PREDICTIVE_ONLY",
    "CLOSING_LINE_VALUE_SUPPORTED", "HISTORICALLY_PROFITABLE",
    "EXECUTION_FEASIBLE", "PROSPECTIVELY_SUPPORTED", "PRODUCTION_ELIGIBLE",
]
RANK = {l: i + 1 for i, l in enumerate(LABELS)}

CLASSES = [
    "TRUE_CROSS_BOOK_ARBITRAGE", "MIDDLES_AND_DISLOCATIONS",
    "STALE_LINE_DELAYED_REACTION", "MODEL_VS_MARKET_VALUE",
    "THIRD_PARTY_PROJECTION_VALUE", "PURE_MICROSTRUCTURE", "PROMOTIONAL_VALUE",
]

#: Phrases that flip an assertion negative. Deliberately generous: when in doubt this
#: classifies a mention as NEGATED or UNCLEAR rather than as support, because the failure
#: that matters here is inventing evidence, not missing some.
#: `no ` with a trailing word boundary MISSED "No `EXECUTION_FEASIBLE`" -- a backtick is not
#: a word boundary, so two genuinely negated assertions were classified UNCLEAR. That is the
#: dangerous direction: it makes evidence look MORE supported than it is.
NEG = re.compile(r"\b(not yet|cannot|can ?not|never|no|not reach|unreachable|fails?|"
                 r"unsupportable|absent|insufficient|would need|before any|requires?|"
                 r"neither|none|without)\b", re.I)

SKIP_DIRS = {"__pycache__", "fixtures", "M00_MARKET_PROGRAM_CONTRACT"}
#: The contract DEFINES the labels; defining a term is not asserting it of a class. Excluding
#: it removed a false positive in which two unrelated fragments of one long JSON line were
#: joined into a single "sentence", making arbitrage look un-negated EXECUTION_FEASIBLE and
#: PRODUCTION_ELIGIBLE. Co-occurrence inside a minified JSON line is not a semantic pairing.
SKIP_FILES = set()


def sentences(text):
    """Split on sentence enders and BLANK lines only.

    Splitting on every newline truncated wrapped sentences mid-clause, which is how a
    negating word ended up on a different line from the label it negated.
    """
    return re.split(r"(?<=[.;])\s+|\n\s*\n", text)


def scan_artifacts():
    out = []
    for root, dirs, files in os.walk(MP):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        if os.path.basename(root).startswith("M37_"):
            continue
        for fn in files:
            if fn in SKIP_FILES or not fn.lower().endswith((".md", ".json")):
                continue
            path = os.path.join(root, fn)
            try:
                text = open(path, encoding="utf-8", errors="ignore").read()
            except OSError:
                continue
            for s in sentences(text):
                labs = [l for l in LABELS if l in s]
                if not labs:
                    continue
                cls = [c for c in CLASSES if c in s]
                out.append({
                    "artifact": os.path.relpath(path, MP).replace("\\", "/"),
                    "labels": labs,
                    "classes": cls,
                    "polarity": "NEGATED" if NEG.search(s) else "UNCLEAR",
                    "sentence": re.sub(r"\s+", " ", s).strip()[:240],
                })
    return out


def main():
    print("=" * 94)
    print("M37 -- evidence-ladder ASSERTIONS FOUND (not labels held)")
    print("=" * 94)

    led = [json.loads(l) for l in open(LEDGER, encoding="utf-8") if l.strip()]
    led_hits = [d for d in led if any(l in json.dumps(d) for l in LABELS)]
    print("\n1. THE LEDGER -- where adjudication would live")
    print("   decisions                       : %d" % len(led))
    print("   decisions naming any ladder label: %d" % len(led_hits))
    for d in led_hits:
        print("     %s" % d.get("decision_id"))
    print("   => the ladder is NOT adjudicated in the ledger.")

    a = scan_artifacts()
    print("\n2. THE ARTIFACTS -- where the labels actually appear")
    print("   assertions found : %d across %d artifacts"
          % (len(a), len({x['artifact'] for x in a})))

    print("\n   by label:")
    for l in LABELS:
        hits = [x for x in a if l in x["labels"]]
        neg = sum(1 for x in hits if x["polarity"] == "NEGATED")
        print("     %-30s rung %d  %3d assertions (%d negated)"
              % (l, RANK[l], len(hits), neg))

    print("\n   by class (assertions naming BOTH a class and a label in one sentence):")
    any_paired = False
    for c in CLASSES:
        hits = [x for x in a if c in x["classes"]]
        if hits:
            any_paired = True
            labs = sorted({l for x in hits for l in x["labels"]})
            neg = sum(1 for x in hits if x["polarity"] == "NEGATED")
            print("     %-30s %2d assertions, %d negated, labels %s"
                  % (c, len(hits), neg, labs))
        else:
            print("     %-30s  0 assertions pairing it with any label" % c)

    print("\n" + "=" * 94)
    print("WHAT THIS ESTABLISHES")
    print("  The ladder is IN USE in node reports and NOT adjudicated in the ledger.")
    if not any_paired:
        print("  NOT ONE sentence in the lane pairs an opportunity class with a ladder label.")
        print("  The labels are discussed in the abstract; no class is graded by them.")
    print("  No class can be said to HOLD any label on this evidence, and this file does not")
    print("  say one does. Adjudication is a RULING and belongs in the ledger; a scanner over")
    print("  prose cannot supply it, and pretending otherwise would manufacture the authority")
    print("  the programme lacks. M24's eligibility gate must stay FAIL-CLOSED.")
    print("=" * 94)

    with open(os.path.join(HERE, "LADDER_REGISTRY.json"), "w", encoding="utf-8") as f:
        json.dump({
            "epistemic_status": "ASSERTIONS FOUND, NOT LABELS HELD. A scan of prose cannot "
                                "adjudicate the evidence ladder; only a ledger ruling can.",
            "ledger_decisions": len(led),
            "ledger_decisions_naming_a_label": [d.get("decision_id") for d in led_hits],
            "adjudicated_in_ledger": False,
            "assertions_found": len(a),
            "artifacts_touched": sorted({x["artifact"] for x in a}),
            "by_label": {l: {"rank": RANK[l],
                             "assertions": sum(1 for x in a if l in x["labels"]),
                             "negated": sum(1 for x in a if l in x["labels"]
                                            and x["polarity"] == "NEGATED")}
                         for l in LABELS},
            "by_class": {c: sum(1 for x in a if c in x["classes"]) for c in CLASSES},
            "any_class_holds_a_label": False,
            "m24_gate_must_stay_fail_closed": True,
            "assertions": a,
        }, f, indent=1)
    print("\nwrote LADDER_REGISTRY.json")


if __name__ == "__main__":
    main()
