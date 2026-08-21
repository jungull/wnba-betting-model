#!/usr/bin/env python
"""test_cbs_player_runner_v18.py — the arm bound to the cold-start core (D167).

`/18` is `/15`'s arm with `/17`'s core underneath it. It forks nothing new: it re-executes
`/15`'s own generated arm source, byte for byte, in a namespace where `_player` — the name
`cbs_v14._run` reads to reach the inner core — is rebound to a shim over `/17`.

  §1  the arm source is `/15`'s, unchanged but for the def name
  §2  exactly one namespace rebinding, and the shim still delegates everything else to `/14`
  §3  the whole repair chain is present: `/17`'s point seam and `/16`'s dispersion seam
  §4  `/15`'s own three ARM_ID rebindings ride along untouched
  §5  the receipt states what this is NOT — 89% of the authorised rule, and why

The behavioural proof that only fallback level 2 moves is not repeated here: it is measured on
real generated output in D167, where level 0 came back bit-identical across 4,972 rows and level
3 across 815, on every target. This suite guards the construction.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cbs_player_coldstart_v16 as cs        # noqa: E402
import cbs_player_runner_v14 as r14          # noqa: E402
import cbs_player_runner_v15 as r15          # noqa: E402
import cbs_player_runner_v17 as r17          # noqa: E402
import cbs_player_runner_v18 as r18          # noqa: E402
import cbs_v14                               # noqa: E402
import cbs_v15                               # noqa: E402

_n = 0
_fail = 0


def ok(cond, label):
    global _n, _fail
    _n += 1
    if cond:
        print("  ok   %s" % label)
    else:
        _fail += 1
        print("  FAIL %s" % label)


print("\n1. THE ARM SOURCE IS /15's, NOT A NEW FORK")
ok(r18.assert_arm_source_unchanged(), "/18's arm source is /15's, byte for byte but for the name")
ok(r18.binding_receipt()["arm_source_changes"] == 0, "the receipt records zero arm source changes")
ok("def _run_v18(" in r18._SRC and "def _run_v15(" not in r18._SRC,
   "only the generated function name differs")
ok(r18.FORKED_FROM == "cbs_player_runner/15", "and it declares /15 as what it binds")

print("\n2. EXACTLY ONE REBINDING, AND THE SHIM STILL DELEGATES")
ok(r18.binding_receipt()["namespace_rebindings"] == ["_player"], "one rebinding: _player")
_changed = [k for k in r15._NS if k in r18._NS and r18._NS[k] is not r15._NS[k]]
ok(_changed == ["_player"], "and nothing else in /15's namespace moved: %s" % _changed)
ok(not [k for k in r15._NS if k not in r18._NS], "no name from /15's namespace was dropped")
ok(r18.assert_core_is_v17(), "the shim's run_player_fold is /17's and it still delegates to /14")
ok(r18._NS["_player"].REQUIRED_PLAYER_FEATURE_SOURCES
   is r14.REQUIRED_PLAYER_FEATURE_SOURCES,
   "an attribute the arm never overrode still resolves to /14's own object")
ok(r18._NS["_player"].run_player_fold is not r14.run_player_fold,
   "while the one entry point that should differ, does")

print("\n3. THE WHOLE REPAIR CHAIN IS PRESENT")
ok("_cs.fold_point" in r17._SRC, "/17 carries the cold-start point seam")
ok(r17.assert_inherits_dispersion_repair(), "and still carries /16's dispersion seam")
ok(r18.binding_receipt()["core_chain"]
   == ["cbs_player_runner/17", "cbs_player_runner/16", "cbs_player_runner/14.run_player_fold"],
   "the receipt names the full chain down to /14's unforked core")
ok(cs.SHORT_HISTORY_LEVEL == 2, "the seam fires on fallback level 2 and nothing else")

print("\n4. /15's OWN REBINDINGS RIDE ALONG UNTOUCHED")
for name in ("ARM_ID", "_restamp", "validate_provenance_sidecar",
             "require_registered_identity_v15"):
    ok(name in r18._NS and r18._NS[name] is r15._NS[name],
       "%-32s is /15's own object" % name)
ok(r18._NS["ARM_ID"] == cbs_v15.ARM_ID and r18._NS["ARM_ID"] != cbs_v14.ARM_ID,
   "so the emitted rows are still stamped as v15's arm, not v14's")
ok(r15.assert_no_source_change()["source_changes"] == 0,
   "and /15's rebound validator is still byte-identical to v14's")

print("\n5. WHAT THIS BINDING IS NOT")
rec = r18.binding_receipt()
ok(rec["is_the_full_authorised_rule"] is False, "the receipt declares it is not the full rule")
ok("DRAFT SLOT" in rec["why_not"], "and names draft slot as the missing input")
ok("4.7611" in rec["why_not"] and "4.2594" in rec["why_not"],
   "and carries the measurement that ruled out the pooled-mean substitute")
ok("level 2 only" in rec["changes_in_emitted_output"],
   "and states that only fallback level 2 changes in the emitted output")

print("\n%d/%d tests passed" % (_n - _fail, _n))
sys.exit(1 if _fail else 0)
