#!/usr/bin/env python
"""test_cbs_player_dispersion_v16.py — the per-row dispersion repair (D136 / D137).

D136 established on bytes that the shipped per-row uncertainty is a per-season constant:
`cbs_v5.dispersion` returns a scalar and the runner broadcasts it across every test row.
D137 authorised repairing it. `cbs_player_runner/16` is `cbs_player_runner/14` forked at exactly
that one line; this suite is what would catch its regression.

  §1  the fork is minimal — one seam, generated from `/14`'s live source
  §2  the DEFECT is reproduced on this fixture, so §3 is measured against something real:
      `/14` emits ONE distinct `pred_sd` per target, range exactly 0.0
  §3  `/16` emits genuine per-row variation, and the variation is not noise: a row with no
      usable prior history gets the pool sd to the bit, and the multiplier is bounded
  §4  the seam is CONFINED — every point forecast, component, fallback level, cold flag,
      prior count and quantile offset is `/14`'s, and `/14`'s own numbers do not move
  §5  the dispersion is STRICTLY PRE-GAME by construction, proved by perturbation rather
      than asserted: no row's own outcome reaches its own dispersion

Everything fitted here is fitted on synthetic fixtures. Nothing is scored.

Run as a script (this repository has no pytest installed)::

    python tests/test_cbs_player_dispersion_v16.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tests"))

import cbs_player_dispersion_v16 as disp        # noqa: E402
import cbs_player_runner_v14 as core14          # noqa: E402
import cbs_player_runner_v16 as fork16          # noqa: E402
import cbs_v7                                   # noqa: E402
import cbs_v8                                   # noqa: E402
import cbs_v14                                  # noqa: E402
from cbs_v5 import PLAYER_SORT_KEYS             # noqa: E402

#: The fixture, the identity and `/14`'s own result are REUSED from `/14`'s suite rather than
#: rebuilt, so the two runners are compared on frames that are identical by construction and a
#: drift in the fixture cannot be mistaken for a difference between the runners. Importing it
#: also re-runs `/14`'s 126 checks, which is the point: this repair must not move them.
print("--- reusing tests/test_cbs_v14.py's fixture (its own checks run first) ---")
import test_cbs_v14 as t14                      # noqa: E402

_n = 0

CONDITIONAL = ("e_minutes_given_active", "attempts_usage", "player_scoring_distribution")


def ok(cond, label):
    global _n
    _n += 1
    if not cond:
        print(f"  FAIL {label}")
        raise SystemExit(1)
    print(f"  ok   {label}")


# =========================================================================== #
print("\n1. the fork is minimal — one seam against /14's LIVE source")
# =========================================================================== #
D = fork16.assert_minimal_fork()
ok(D["n_permitted_seams"] == 1 and D["n_changed_lines"] == 4,
   "the fork changes exactly one seam (four unified-diff lines with the def rename)")
ok(D["seam"]["old"] == "pd.Series(sd_v, index=test.index), off, fold_id=fold_id,",
   "and the seam it replaces is the per-season-constant broadcast itself")
ok(D["namespace_overrides"] == ["_disp"],
   "the only name introduced is the dispersion module; every other name is /14's own object")

#: INNER CORE against INNER CORE. `cbs_v14.run_player_fold` is the ARM: it calls the core behind
#: `build_legacy_identity_shim` with `cbs_v8`'s synthetic digest and then restamps. Comparing the
#: arm's output to the core's would compare two different layers, so the shim is reused verbatim
#: and both runners are invoked exactly as `cbs_v14._run` invokes `/14`.
_SHIM = cbs_v14.build_legacy_identity_shim(t14.TRAIN, t14.TEST, t14.UNI,
                                           snapshot_manifest=t14.MAN)
_KW = dict(config_hash=cbs_v8.SYNTHETIC_CONFIG_HASH,
           snapshot_hash=cbs_v8.snapshot_identity(_SHIM), snapshot_manifest=_SHIM,
           universe=t14.UNI, synthetic=True, allow_declared_defaults=False)

R14 = core14.run_player_fold(t14.TRAIN, t14.TEST, t14.FOLD, **_KW)
R16 = fork16.run_player_fold(t14.TRAIN, t14.TEST, t14.FOLD, **_KW)
ok(R16["scoring_permitted"] is True,
   f"the repaired fold passes every receipt (failed={R16['failed_receipts']})")
ok(R16["diagnostics"]["degenerate"] is False and R14["diagnostics"]["degenerate"] is False,
   "and both runs are NONDEGENERATE, so the comparison is against a fitted arm")

P14 = R14["predictions"]
P16 = R16["predictions"]


# =========================================================================== #
print("\n2. the DEFECT is reproduced: /14 emits ONE distinct pred_sd per target")
# =========================================================================== #
for tgt in CONDITIONAL:
    s = P14[tgt]["pred_sd"].astype(float)
    ok(s.round(9).nunique() == 1 and float(s.max() - s.min()) == 0.0,
       f"/14 {tgt}: 1 distinct pred_sd over {len(s)} rows, range exactly 0.0")


# =========================================================================== #
print("\n3. /16 emits GENUINE per-row variation, anchored on the pool sd")
# =========================================================================== #
for tgt in CONDITIONAL:
    s = P16[tgt]["pred_sd"].astype(float)
    pool = float(R14["diagnostics"]["dispersion"][tgt]["sd"])
    ok(s.round(9).nunique() > 1 and float(s.max() - s.min()) > 0.0,
       f"/16 {tgt}: {s.round(9).nunique()} distinct pred_sd over {len(s)} rows, "
       f"range {float(s.max() - s.min()):.6f}")
    m = (s / pool).to_numpy()
    ok(np.isfinite(m).all()
       and m.min() >= disp.MULTIPLIER_LOW - 1e-12 and m.max() <= disp.MULTIPLIER_HIGH + 1e-12,
       f"and every multiplier lies inside [{disp.MULTIPLIER_LOW}, {disp.MULTIPLIER_HIGH}]")
    ok(bool(np.isclose(m, 1.0).any()),
       "and at least one row sits exactly at the pool sd — a row with no usable prior "
       "history is NOT given a fabricated spread")

_z = P16["e_minutes_given_active"]
_np = _z["n_prior_games"].astype(float).to_numpy()
_mz = (_z["pred_sd"].astype(float)
       / float(R14["diagnostics"]["dispersion"]["e_minutes_given_active"]["sd"])).to_numpy()
ok(bool((_np == 0).any()) and np.allclose(_mz[_np == 0], 1.0),
   "every row with ZERO prior appearances gets the pool sd to the bit (w = 0 by construction)")
ok(disp.conditional_sd(4.0, pd.Series([np.nan, 2.0]), pd.Series([0.0, 10.0]),
                       vol_ref=float("nan")).eq(4.0).all(),
   "and an undefined normaliser degrades to the incumbent rather than to NaN")


# =========================================================================== #
print("\n4. the seam is CONFINED — nothing but pred_sd moved")
# =========================================================================== #
for tgt in ("p_active",) + CONDITIONAL:
    a, b = P14[tgt], P16[tgt]
    ok(list(a.columns) == list(b.columns) and len(a) == len(b),
       f"{tgt}: same columns and row count as /14")
    same = [c for c in a.columns if c not in ("pred_sd", "arm_id", "model_hash")]
    diff = [c for c in same if not a[c].equals(b[c])]
    ok(diff == [] if tgt != "p_active" else diff == [],
       f"and every other emitted column is IDENTICAL to /14's ({len(same)} compared)")

for tgt in CONDITIONAL:
    ok(float(R14["diagnostics"]["dispersion"][tgt]["sd"])
       == float(R16["diagnostics"]["dispersion"][tgt]["sd"]),
       f"{tgt}: the scalar cbs_v5.dispersion returned is UNCHANGED — the repair "
       f"re-allocates the fold's dispersion across rows, it does not re-estimate it")
    ok(R14["diagnostics"]["fitted_state"][tgt]["dispersion_offsets"]
       == R16["diagnostics"]["fitted_state"][tgt]["dispersion_offsets"],
       "and the additive quantile offsets are still the inherited fold-level ones")

ok(R14["diagnostics"]["selected"] == R16["diagnostics"]["selected"],
   "every selected lambda, alpha and boundary is /14's")
ok(R14["provenance_sidecar_digest"] is not None
   and P14["p_active"].equals(P16["p_active"]),
   "and p_active — which emits no dispersion at all — is byte-for-byte /14's")


# =========================================================================== #
print("\n5. STRICTLY PRE-GAME, proved by perturbation rather than asserted")
# =========================================================================== #
_comb = cbs_v7.combine_history_frames(t14.TRAIN, t14.TEST)
if "appeared" not in _comb.columns:
    _comb["appeared"] = np.nan
_plan = cbs_v7.build_walk_forward_plan(_comb, group_cols=["player_id", "season"],
                                       sort_cols=list(PLAYER_SORT_KEYS))
_act = _comb["appeared"].astype(float).fillna(0.0).astype(bool)
_ctr = cbs_v7.conditional_center(_plan, _comb, _act, "e_minutes_given_active",
                                 minutes_alpha=0.3, rate_alpha=0.3)
L = disp.assert_no_own_row_leakage(_plan, _comb["minutes"], _ctr, 0.3, mask=_act)
ok(L["n_own_row_moved"] == 0 and L["n_rows_perturbed"] > 0,
   f"perturbing each of {L['n_rows_perturbed']} outcomes by +1000 moves NO row's own "
   f"dispersion input")
ok(L["n_downstream_moved"] > 0,
   f"and it does move {L['n_downstream_moved']} strictly-later ones, so the check is not "
   f"vacuous against a function that ignores its outcome argument")

_vol = disp.prior_abs_error_ewma(_plan, _comb["minutes"], _ctr, 0.3, mask=_act)
ok(bool(_vol.isna().any()) and bool(_vol.notna().any()),
   "the volatility is undefined exactly where no prior row was admitted, and defined elsewhere")

_rc = disp.dispersion_receipt(P16["e_minutes_given_active"]["pred_sd"],
                              float(R16["diagnostics"]["dispersion"]
                                    ["e_minutes_given_active"]["sd"]),
                              target="e_minutes_given_active")
ok(_rc["strictly_pre_game"] is True and _rc["n_distinct"] > 1
   and _rc["conditioned_on"] == ["prior_abs_error_ewma", "n_prior_appearances"],
   "and the receipt records what the row-level sd was conditioned on, not merely that it varies")

print(f"\n{_n}/{_n} tests passed")
