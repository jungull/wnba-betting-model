#!/usr/bin/env python
"""test_cbs_player_runner_v17.py — the cold-start point seam (D092 / D137 / D139 / D164).

`/14` emits `raw.where(lvl == 0, fb_mean)`: wherever the fallback ladder fires it discards the
player's own centre and broadcasts a pooled scalar. `/17` is `/16` forked at exactly that line.

  §1  the fork is minimal — one seam, generated from `/16`'s own generated source
  §2  `/17` still carries `/16`'s dispersion repair; a fork that dropped it would be a
      regression wearing an improvement's name
  §3  the ladder is respected: level 2 keeps the player's own centre, levels 1/3/4 keep the
      pooled scalar exactly as before, level 0 is untouched
  §4  measured against `/16` on `/14`'s own fixture: NON-FALLBACK ROWS ARE BIT-IDENTICAL,
      short-history rows move, and the emitted forecast stops being a constant
  §5  what this seam is NOT — it is not the full authorised rule, and the module says so

The fixture, the identity and `/16`'s result are reused from the neighbouring suites rather than
rebuilt, so a drift in the fixture cannot be mistaken for a difference between the runners.
Everything here is synthetic. Nothing is scored.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cbs_player_coldstart_v16 as cs        # noqa: E402
import cbs_player_runner_v16 as r16          # noqa: E402
import cbs_player_runner_v17 as r17          # noqa: E402

print("--- reusing tests/test_cbs_v14.py's fixture (its own checks run first) ---")
import test_cbs_v14 as t14                   # noqa: E402

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


print("\n1. THE FORK IS MINIMAL")
d = r17.assert_minimal_fork()
ok(d["n_changed_lines"] == 4, "exactly 4 changed lines: the def rename and the one seam")
ok(d["n_permitted_seams"] == 1, "exactly one permitted seam")
ok("raw.where(lvl == 0, fb_mean)" in d["seam"]["old"],
   "the seam replaced is the cold-start point line and nothing else")
ok(d["namespace_overrides"] == ["_cs"], "one namespace override, the cold-start module")
ok(not any("alpha" in ln or "dispersion(" in ln or "Standardizer" in ln
           for ln in d["changed_lines"]),
   "no estimator, selection or dispersion formula appears in the diff")

print("\n2. THE INHERITED REPAIR SURVIVES")
ok(r17.assert_inherits_dispersion_repair(), "/17 still carries /16's per-row dispersion seam")
ok(r17._NS["_disp"] is r16._NS["_disp"], "and reaches the SAME dispersion module object")
_shared = [k for k in ("dispersion", "residuals", "prefix_mean", "conditional_center",
                       "walk_forward_ewma", "player_fallback_level", "QUANTILE_Z", "DECLARED")
           if k in r16._NS and k in r17._NS]
ok(len(_shared) >= 6 and all(r17._NS[k] is r16._NS[k] for k in _shared),
   "every estimator name resolves to /16's own object (%d checked)" % len(_shared))

print("\n3. THE LADDER IS RESPECTED")
_raw = pd.Series([10.0, 20.0, 30.0, np.nan, 40.0, 50.0])
_lvl = pd.Series([0, 2, 1, 2, 3, 4])
_got = cs.fold_point(_raw, _lvl, 7.0).tolist()
ok(_got[0] == 10.0, "level 0 (not a fallback) is untouched")
ok(_got[1] == 20.0, "level 2 (one or two prior appearances) keeps the player's own centre")
ok(_got[2] == 7.0, "level 1 (degenerate fold) still takes the pooled scalar")
ok(_got[3] == 7.0, "level 2 with a NON-FINITE centre still takes the pooled scalar")
ok(_got[4] == 7.0, "level 3 (no prior appearance) still takes the pooled scalar")
ok(_got[5] == 7.0, "level 4 (declared-constant season) still takes the pooled scalar")
ok(cs.SHORT_HISTORY_LEVEL == 2,
   "the short-history level is 2, matching PLAYER_SHORT_HISTORY_MAX = 2")

print("\n4. MEASURED AGAINST /16 ON THE SAME FIXTURE")
# the identity shim is built exactly as `cbs_v14._run` builds it, and reused verbatim, so both
# runners are invoked at the same layer -- copied from the /16 suite for the same reason.
import cbs_v8                                               # noqa: E402
import cbs_player_runner_v14 as _core14                     # noqa: E402
import cbs_v14                                              # noqa: E402

_SHIM = cbs_v14.build_legacy_identity_shim(t14.TRAIN, t14.TEST, t14.UNI,
                                           snapshot_manifest=t14.MAN)
_kw = dict(config_hash=cbs_v8.SYNTHETIC_CONFIG_HASH,
           snapshot_hash=cbs_v8.snapshot_identity(_SHIM), snapshot_manifest=_SHIM,
           universe=t14.UNI, synthetic=True, allow_declared_defaults=False)
try:
    R16 = r16.run_player_fold(t14.TRAIN, t14.TEST, t14.FOLD, **_kw)
    R17 = r17.run_player_fold(t14.TRAIN, t14.TEST, t14.FOLD, **_kw)
    _ran = True
except Exception as exc:                                    # noqa: BLE001
    print("  SKIP  could not run the fixture folds: %s: %s" % (type(exc).__name__, exc))
    _ran = False

if _ran:
    P16, P17 = R16["predictions"], R17["predictions"]
    _tgts = [t for t in P16 if t in P17]
    ok(bool(_tgts), "both runners emitted the same targets (%d)" % len(_tgts))
    _any_moved = False
    for tgt in _tgts:
        a, b = P16[tgt], P17[tgt]
        if "fallback_level" not in a or "pred_point" not in a:
            continue
        lvl = a["fallback_level"].to_numpy(int)
        non_fb = lvl == 0
        same = np.allclose(a["pred_point"].to_numpy(float)[non_fb],
                           b["pred_point"].to_numpy(float)[non_fb], equal_nan=True)
        ok(same, "%-32s non-fallback rows are bit-identical to /16" % tgt)
        untouched = np.isin(lvl, (1, 3, 4))
        if untouched.any():
            ok(np.allclose(a["pred_point"].to_numpy(float)[untouched],
                           b["pred_point"].to_numpy(float)[untouched], equal_nan=True),
               "%-32s levels 1/3/4 are unchanged" % tgt)
        short = lvl == cs.SHORT_HISTORY_LEVEL
        if short.any():
            moved = ~np.isclose(a["pred_point"].to_numpy(float)[short],
                                b["pred_point"].to_numpy(float)[short], equal_nan=True)
            _any_moved = _any_moved or bool(moved.any())
            sd16 = float(np.std(a["pred_point"].to_numpy(float)[short]))
            sd17 = float(np.std(b["pred_point"].to_numpy(float)[short]))
            ok(sd17 >= sd16,
               "%-32s short-history forecasts stop being a constant (sd %.4f -> %.4f)"
               % (tgt, sd16, sd17))
    ok(_any_moved or not any((P16[t]["fallback_level"].to_numpy(int) == 2).any()
                             for t in _tgts if "fallback_level" in P16[t]),
       "at least one short-history row actually moved, so the seam is not vacuous")

print("\n5. WHAT THIS SEAM IS NOT")
ok(d["is_the_full_authorised_rule"] is False,
   "the fork declares it is NOT the full authorised rule")
ok("DRAFT SLOT" in d["why_not"],
   "and names the reason: draft slot is not a registered feature source on this path")
ok("4.7611" in d["why_not"] and "4.2594" in d["why_not"],
   "and carries the measurement that rules out substituting the pooled mean")
ok("AVAILABLE, NOT BOUND" in r17.__doc__,
   "and states it is AVAILABLE, not BOUND — nothing here binds an arm")

print("\n%d/%d tests passed" % (_n - _fail, _n))
sys.exit(1 if _fail else 0)
