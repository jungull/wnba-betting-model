#!/usr/bin/env python
"""test_cbs_player_coldstart_v16.py — the cold-start splice (D092 / D137 / D139).

D092 recommended the rule. D137 authorised it on condition it *reproduce its validated numbers*.
D139 then found the authorisation cannot be executed as written: D092's headline 4.02 came from a
variant INCLUDING listed position while its own ruling 2 says to drop it, and the specified rule
yields 4.032479.

  §1  the arithmetic behaves — blend weights, clipping, the position term's on/off seam
  §2  the splice is CONFINED: above the tier nothing moves, proved and the guard shown to fire
  §3  the DEFECT is reproduced on the artifact, so §4 is measured against something real:
      the champion emits an essentially constant forecast on 1,061 rows
  §4  BOTH variants reproduce their recorded numbers to 5e-6, and the 0.008145 gap between the
      authorised rule and the validated headline is asserted explicitly, so the inconsistency
      lives in the test output and not only in a decision record

Nothing here is scored against a market and nothing is fitted. Exploration artifact only.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cbs_player_coldstart_v16 as cs  # noqa: E402

_n = 0
_fail = 0


def ok(cond, msg):
    global _n, _fail
    _n += 1
    if cond:
        print("  ok   %s" % msg)
    else:
        _fail += 1
        print("  FAIL %s" % msg)


def close(a, b, tol=5e-6):
    return abs(float(a) - float(b)) <= tol


ART = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "experiments", "exploration", "E1_I0020_coldstart_tiering")
HAVE = os.path.exists(os.path.join(ART, "placeholder_frame.parquet"))

print("\n1. THE ARITHMETIC")
ok(cs.blend_weight([0])[0] == 0.0, "no prior games -> weight 0, the forecast is pure structural")
ok(close(cs.blend_weight([2])[0], 0.5), "two prior games -> half own, half structural")
ok(close(cs.blend_weight([4])[0], 2 / 3), "four prior games -> two thirds own")
ok(close(cs.structural_prior([10.0], [12.0], [9.0])[0], 11.0),
   "structural = league + depth deviation + draft deviation")
_off = cs.structural_prior([10.0], [12.0], [9.0], [13.0])[0]
_on = cs.structural_prior([10.0], [12.0], [9.0], [13.0], include_listed_position=True)[0]
ok(close(_off, 11.0) and close(_on, 14.0),
   "the listed-position term is OFF by default and additive when switched on")
ok(_off != _on, "the discarded variant stays reachable, so the choice is auditable both ways")
try:
    cs.structural_prior([10.0], [12.0], [9.0], None, include_listed_position=True)
    ok(False, "asking for the position term without the column must raise")
except ValueError:
    ok(True, "asking for the position term without the column raises rather than silently drops")
ok(cs.coldstart_forecast([-5.0], [0], [0.0], [-3.0], [-4.0])[0] == 0.0,
   "the blend is clipped at zero (D092 saw a minimum of -0.10)")
ok(close(cs.coldstart_forecast([99.0], [0], [10.0], [12.0], [9.0])[0],
         cs.coldstart_forecast([0.0], [0], [10.0], [12.0], [9.0])[0]),
   "a zero-history row ignores its own running mean entirely")

print("\n2. THE SPLICE IS CONFINED")
_champ = np.array([1.0, 2.0, 3.0, 4.0])
_tier = np.array([True, False, True, False])
_out = cs.splice(_champ, _tier, np.full(4, 9.0))
ok(np.array_equal(_out, np.array([9.0, 2.0, 9.0, 4.0])), "only flagged rows are replaced")
try:
    cs.assert_above_tier_untouched(np.array([1.0, 5.0]), np.array([1.0, 2.0]),
                                   np.array([True, False]))
    ok(False, "the guard must fire when a non-tier row moves")
except AssertionError:
    ok(True, "the guard fires when a non-tier row moves, so it is not vacuous")
try:
    cs.splice(np.zeros(3), np.zeros(3, bool), np.zeros(2))
    ok(False, "mismatched shapes must raise")
except ValueError:
    ok(True, "mismatched shapes raise instead of broadcasting silently")


def _built(target, include_pos):
    w = pd.read_parquet(os.path.join(ART, "placeholder_frame.parquet"))
    tier = w["pts__is_fallback"].to_numpy(bool)
    n = w["pl_games_prior"].to_numpy(float)
    ph = pd.read_csv(os.path.join(ART, "placeholders_%s.csv" % target))
    rep = cs.coldstart_forecast(ph["P1full_running_mean"], n, ph["league"],
                                ph["P4_teamrole"], ph["P3_draft_bin"], ph["P2_position"],
                                include_listed_position=include_pos)
    out = cs.splice(w["champ_" + target], tier, rep)
    return w, ph, tier, w["t_" + target].to_numpy(float), out, w["champ_" + target].to_numpy(float)


if not HAVE:
    print("\n3-4. SKIPPED — E1_I0020 artifact frame not present")
else:
    print("\n3. THE DEFECT, REPRODUCED ON THE ARTIFACT")
    w, ph, tier, y, out, champ = _built("pts", False)
    ok(int(tier.sum()) == cs.ANCHORS["tier_rows"],
       "the tier is the %d rows the authorisation was priced on" % cs.ANCHORS["tier_rows"])
    ok(float(np.std(champ[tier])) < 0.02,
       "the champion's forecast sd on those rows is %.6f — it is not looking at the player"
       % float(np.std(champ[tier])))
    ok(float(np.std(y[tier])) > 5.0,
       "while the actual outcome sd is %.2f — the flatness is the forecast's, not the world's"
       % float(np.std(y[tier])))
    ok(close(np.mean(np.abs(y[tier] - champ[tier])), cs.ANCHORS["pts"]["champion"]),
       "champion tier MAE reproduces at %.6f" % cs.ANCHORS["pts"]["champion"])

    print("\n4. BOTH VARIANTS REPRODUCE, AND THE INCONSISTENCY IS ASSERTED")
    for target in ("pts", "minutes"):
        for inc, key in ((False, "authorised_no_position"), (True, "position_inclusive")):
            _, _, t2, y2, o2, _ = _built(target, inc)
            got = float(np.mean(np.abs(y2[t2] - o2[t2])))
            ok(close(got, cs.ANCHORS[target][key]),
               "%-7s %-22s tier MAE %.6f" % (target, key, cs.ANCHORS[target][key]))

    _, _, t_a, y_a, o_a, _ = _built("pts", False)
    _, _, _, _, o_b, _ = _built("pts", True)
    gap = float(np.mean(np.abs(y_a[t_a] - o_a[t_a])) - np.mean(np.abs(y_a[t_a] - o_b[t_a])))
    ok(close(gap, 0.008145),
       "the AUTHORISED rule is worse than the VALIDATED headline by exactly %.6f points; if "
       "this moves, D139's finding has changed and the ledger must say so" % 0.008145)

    ref = ph["P1_ref_D076"].to_numpy(float)
    base = float(np.mean(np.abs(y - ref)))
    for inc, key in ((False, "authorised_no_position"), (True, "position_inclusive")):
        rep = cs.coldstart_forecast(ph["P1full_running_mean"], w["pl_games_prior"], ph["league"],
                                    ph["P4_teamrole"], ph["P3_draft_bin"], ph["P2_position"],
                                    include_listed_position=inc)
        sp = cs.splice(w["champ_pts"], tier, rep)
        skill = (base - float(np.mean(np.abs(y - sp)))) / base * 100
        ok(close(skill, cs.ANCHORS["pooled_skill_pts"][key], tol=0.002),
           "pooled points skill %-22s %+.3f%%" % (key, cs.ANCHORS["pooled_skill_pts"][key]))

    cs.assert_above_tier_untouched(out, champ, tier)
    ok(True, "on real data the splice is a no-op above the tier")
    ok(int(np.sum(~np.isclose(out, champ))) <= int(tier.sum()),
       "no more rows changed than there are tier rows")

    r = cs.coldstart_receipt(out, champ, tier, y, target="pts")
    ok(r["n_tier"] == cs.ANCHORS["tier_rows"] and r["untouched_above_tier"] is True,
       "the receipt records the tier size and that nothing above it moved")
    ok(r["replacement_sd_on_tier"] > 2.0 and r["champion_sd_on_tier"] < 0.02,
       "the receipt shows the repair varies by player (%.3f) where the champion did not (%.4f)"
       % (r["replacement_sd_on_tier"], r["champion_sd_on_tier"]))
    ok(r["tier_mae_spliced"] < r["tier_mae_champion"],
       "and that the tier error fell, %.4f -> %.4f"
       % (r["tier_mae_champion"], r["tier_mae_spliced"]))

print("\n%d/%d tests passed" % (_n - _fail, _n))
sys.exit(1 if _fail else 0)
