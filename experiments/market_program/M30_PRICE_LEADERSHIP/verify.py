"""verify.py -- re-derive this node's claims from scratch. Run before quoting anything.

Exists because the preregistration was very nearly broken by a cosmetic edit: renumbering
the node from M29 to M30 rewrote the title line inside the hash-frozen PREREG.md, which
silently invalidated the freeze that is the whole basis for calling s01 confirmatory. The
hash check below would have caught it on the next run; it now runs on every run.

Run: python verify.py
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import sys

PASS = FAIL = 0


def check(label: str, ok: bool, why: str = "") -> None:
    global PASS, FAIL
    if ok:
        PASS += 1
        print("  PASS  %s" % label)
    else:
        FAIL += 1
        print("  FAIL  %s" % label + (("\n          " + why) if why else ""))


def main() -> int:
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    print("=" * 86)
    print("M30 PRICE LEADERSHIP -- verification")
    print("=" * 86)

    print("\n1. The preregistration is intact")
    raw = io.open("PREREG.md", "rb").read()
    got = hashlib.sha256(raw).hexdigest()
    want = io.open("PREREG.sha256").read().split()[0]
    check("PREREG.md matches its frozen sha256", got == want,
          "frozen %s\n          actual %s\n          A prereg that can be edited is not a "
          "prereg. Restore it; do not re-hash it." % (want, got))
    check("the frozen prereg still carries its ORIGINAL text", b"M29 PRICE LEADERSHIP" in raw,
          "the node was renumbered to M30 but the frozen document is never edited (D158)")

    print("\n2. Findings are present, and carry the hash and the tape pin")
    for f in ("FINDINGS.json", "FINDINGS_s02.json", "FINDINGS_s03.json"):
        if not os.path.exists(f):
            check("%s exists" % f, False, "run the stage that produces it")
            continue
        d = json.load(open(f, encoding="utf-8"))
        check("%s records the prereg hash" % f, d.get("prereg_sha256") == want)
        check("%s pins the tape" % f, bool(d.get("as_of")),
              "the capture job keeps running; an unpinned result is not reproducible")

    print("\n3. The preregistered primary is reported as UNEVALUATED, not quietly replaced")
    d1 = json.load(open("FINDINGS.json", encoding="utf-8"))
    prim = d1.get("primary") or {}
    check("s01's preregistered median really is degenerate",
          abs(prim.get("diff_median", 1.0)) < 1e-9,
          "if this ever becomes non-zero the DEFECTS.md story is wrong and must be rewritten")
    defects = io.open("DEFECTS.md", encoding="utf-8").read()
    check("DEFECTS.md says P1-P3 are not evaluated", "NOT EVALUATED" in defects)
    for n in range(1, 6):
        check("DEFECT %d is recorded" % n, ("## DEFECT %d" % n) in defects)

    print("\n4. The post-hoc stages are labelled as post-hoc")
    for f in ("s02_secondary.py", "s03_beats_consensus.py"):
        src = io.open(f, encoding="utf-8").read()
        check("%s declares itself POST-HOC" % f, "POST-HOC" in src)
        check("%s declares it reads no outcome" % f,
              "NO GAME OUTCOME IS READ" in src,
              "the partition claim must be visible in the file that does the work")

    print("\n5. The headline numbers re-derive from the findings files")
    d3 = json.load(open("FINDINGS_s03.json", encoding="utf-8"))
    live, hist = d3.get("live", {}), d3.get("hist", {})
    check("the replication actually ran", bool(hist) and hist.get("n", 0) > 10000,
          "the loader once silently dropped all 292 hist files and reported no observations")
    check("both samples agree on the fraction beating consensus",
          abs(live.get("frac_beating_consensus", 0) - hist.get("frac_beating_consensus", 1)) < 0.002,
          "the tightness of this agreement is what makes the node credible")
    check("betting blind loses in both samples",
          live["all"]["mean"] < -0.03 and hist["all"]["mean"] < -0.03)
    check("best-of-book shopping still loses in both samples",
          live["best_of_book"]["mean"] < 0 and hist["best_of_book"]["mean"] < 0,
          "shopping is necessary and nowhere near sufficient")
    check("the 3pp bucket is positive in both samples",
          live["gap_0.030"]["mean"] > 0 and hist["gap_0.030"]["mean"] > 0)
    check("the 1.5pp bucket is negative in both samples",
          live["gap_0.015"]["mean"] < 0 and hist["gap_0.015"]["mean"] < 0,
          "if this flips, the threshold in M28/consensus_edge.py is wrong")

    print("\n" + "=" * 86)
    print("%s -- %d/%d checks" % ("VERIFIED" if not FAIL else "FAILED", PASS, PASS + FAIL))
    print("=" * 86)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
