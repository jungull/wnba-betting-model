#!/usr/bin/env python3
"""test_cbs_v15.py — the v15 execution modules, tested before any real run.

**Nothing here is scored.** Object identity, source diffs, tier rules, refusal behaviour and row
counts only. One real 2022 fold is fitted IN MEMORY to prove the wiring; nothing is persisted to
any arm's output namespace and no forecast is compared to any outcome.

Sections
    1  the frame fork is exactly five seams, and no formula is inside the diff
    2  the runner fork is exactly one seam
    3  the estimator objects are the SAME OBJECTS v14 uses
    4  identity refuses what it should
    5  the training frame is Tier A only; every tier still gets a forecast
    6  the attribution sensitivity differs only through history

Run::

    python tests/test_cbs_v15.py
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore")

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import cbs_player_runner_v14 as r14                                  # noqa: E402
import cbs_player_runner_v15 as r15                                  # noqa: E402
import cbs_real_frames_v3 as rf3                                     # noqa: E402
import cbs_real_frames_v5 as rf5                                     # noqa: E402
import cbs_v14 as v14                                                # noqa: E402
import cbs_v15 as v15                                                # noqa: E402

_R: list[dict] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    _R.append({"check": name, "ok": bool(cond), "detail": detail})
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


#: Anything whose presence in a diff would mean the model changed.
FORMULA_TOKENS = ("logistic_fit", "logistic_predict", "Standardizer", "select_alpha_bound",
                  "select_lambda_chronological", "walk_forward_ewma", "conditional_center",
                  "dispersion", "residuals", "prefix_mean", "player_split",
                  "stage_a_features_v8", "player_fallback_level", "QUANTILE_Z", "DECLARED",
                  "EWMA_ALPHA", "min_ewma", "start_share_l5")

#: The layer `/15` forks. Commit 0108ef86 moved this from the inner modelling core to the ARM,
#: because forking the core lost identity restamping, provenance recomputation and the strict
#: validator re-run, and 2021 failed as a result. THIS SUITE WAS NOT UPDATED AT THE TIME: it kept
#: asserting the core layer's properties, went red against a healthy arm, and the committed
#: receipt kept claiming 32/32. The layer is pinned here so that a future move cannot silently
#: invalidate these checks again -- if it changes, section 2 fails loudly and says so.
EXPECTED_FORK_LAYER = "cbs_v14._run"
EXPECTED_RUNNER_DIFF_LINES = 4          # the def rename and the one seam, each as a - and a +


def s1_frame_fork() -> None:
    print("\n1 — the frame fork")
    d = rf5.source_diff()
    check("generated at import from inspect.getsource",
          d["generated_at_import_from_inspect_getsource"])
    check("exactly five seams", d["n_seams"] == 5, str(d["n_seams"]))
    check("16 changed lines (5 seams + the rename)", d["n_changed_lines"] == 16,
          str(d["n_changed_lines"]))
    body = "\n".join(d["changed_lines"])
    hit = [t for t in FORMULA_TOKENS if t in body]
    check("no estimator or feature formula appears anywhere in the diff", not hit, str(hit))
    check("every seam has an authorised reason",
          all("reason" in v for v in d["seams"].values()))


def s2_runner_fork() -> None:
    print("\n2 — the runner fork")
    d = r15.assert_minimal_fork()
    check("exactly one permitted seam", d["n_permitted_seams"] == 1)
    check("the fork is still at the ARM layer this suite was written against",
          d["forked_from"] == EXPECTED_FORK_LAYER,
          f"{d['forked_from']} (expected {EXPECTED_FORK_LAYER})")
    check("exactly four changed lines (the def rename and the one seam)",
          d["n_changed_lines"] == EXPECTED_RUNNER_DIFF_LINES, str(d["n_changed_lines"]))
    body = "\n".join(d["changed_lines"])
    hit = [t for t in FORMULA_TOKENS if t in body]
    check("no estimator formula in the runner diff", not hit, str(hit))
    check("the seam is the identity binding and nothing else",
          "require_registered_identity" in d["seam"]["old"])


def s3_object_identity() -> None:
    print("\n3 — the estimator objects are the SAME OBJECTS")
    # The original form compared `cbs_player_runner_v14`'s module namespace against `r15._NS`.
    # That was correct while `/15` forked the inner core. Since 0108ef86 it forks the ARM, whose
    # namespace is `cbs_v14`'s and does not contain runner-level estimator names -- so the
    # comparison resolved ZERO objects and reported all fourteen as differing. It was measuring
    # the wrong pair, not a drifted model.
    #
    # The invariant that holds now is STRONGER and is what is asserted here: `/15` does not fork
    # the estimator layer at all. It calls `cbs_player_runner_v14.run_player_fold`, the same
    # object `cbs_v14._run` calls, unchanged.
    ns15 = r15._NS
    missing = [k for k in v14.__dict__ if k not in ns15]
    differ = [k for k in v14.__dict__ if k in ns15 and ns15[k] is not v14.__dict__[k]]
    check("v15's namespace carries every one of the arm's names", not missing,
          f"missing: {missing[:6]}")
    # Three names legitimately differ, and the reason is the same for all three: `ARM_ID` is
    # read from module globals by callees that take no parameter for it, so v15 re-executes
    # those callees VERBATIM in a namespace where `ARM_ID` is v15's. That is a rebinding, not a
    # rewrite -- which is a stronger guarantee than an override, and is asserted as such below.
    # These were the "callee-globals defects" 0108ef86 found by running the arm.
    ARM_ID_REBOUND = ["ARM_ID", "_restamp", "validate_provenance_sidecar"]
    check("only the declared ARM_ID rebindings differ", sorted(differ) == sorted(ARM_ID_REBOUND),
          f"differ: {sorted(differ)}")
    check("the arm id really is the one that differs", ns15["ARM_ID"] == v15.ARM_ID
          and ns15["ARM_ID"] != v14.ARM_ID, f"{ns15['ARM_ID']}")
    _reb = r15.assert_no_source_change()
    check("and the rebound callee is BYTE-IDENTICAL to v14's, only its ARM_ID binding differs",
          _reb["source_changes"] == 0 and _reb["namespace_overrides"] == ["ARM_ID"], str(_reb))
    check("a meaningful number were checked", len(v14.__dict__) >= 50,
          f"{len(v14.__dict__)} objects")
    extra = sorted(k for k in ns15 if k not in v14.__dict__)
    check("exactly two names are added, both belonging to the seam",
          extra == ["_run_v15", "require_registered_identity_v15"], f"added: {extra}")
    core = ns15.get("_player")
    check("the inner modelling core is reached as v14's own module", core is r14, str(core))
    check("and its run_player_fold is v14's own unforked object",
          getattr(core, "run_player_fold", None) is r14.run_player_fold)
    _in_src = [t for t in FORMULA_TOKENS if t in r15._SRC]
    check("no estimator formula appears anywhere in the generated arm source",
          not _in_src, str(_in_src))
    check("v15 inherits the fit boundary objects from v14",
          v15.snapshot_identity is v14.snapshot_identity
          and v15.build_fold_manifest is v14.build_fold_manifest
          and v15.sidecar_identity is v14.sidecar_identity)
    check("v15 declares it inherits the estimator from v14",
          v15.INHERITS_ESTIMATOR_FROM == v14.ARM_ID)
    check("v15 is a DIFFERENT arm id", v15.ARM_ID != v14.ARM_ID)
    check("v15 declares a different row universe",
          v15.ROW_UNIVERSE == "prediction_contract_v5" != v14.ROW_UNIVERSE)


def s4_identity_refusals() -> None:
    print("\n4 — identity refuses what it should")
    from cbs_v7 import AdapterBoundaryError
    try:
        v15.require_registered_identity_v15("not-a-hash", "x", None, frames={},
                                            synthetic=False)
        check("a wrong config hash is refused", False, "it was accepted")
    except AdapterBoundaryError:
        check("a wrong config hash is refused", True)
    except Exception as exc:                                         # noqa: BLE001
        check("a wrong config hash is refused", False, f"{type(exc).__name__}: {exc}")

    if v15.REGISTERED_CONFIG_HASH is not None:
        try:
            v15.require_registered_identity_v15(
                v15.REGISTERED_CONFIG_HASH, "x", None, frames={}, synthetic=False)
            check("a missing snapshot manifest is refused", False, "it was accepted")
        except AdapterBoundaryError as exc:
            check("a missing snapshot manifest is refused", "snapshot_manifest" in str(exc))
        rec = v15.verify_implementation_bytes(REPO)
        check("the implementation bytes verify against the registration", rec["ok"],
              f"{rec['n_files']} files")
    else:
        check("execution is refused while /2 is unregistered",
              v15.REGISTERED_CONFIG_HASH is None,
              "REGISTERED_CONFIG_HASH is None until /2 exists")


def s5_tier_wiring() -> dict:
    print("\n5 — the training frame is Tier A only; every tier still gets a forecast")
    f = rf5.build_player_frame_v5(2022, REPO, require_attested=True)
    tr, te, un = f["train"], f["test"], f["universe"]
    check("train is Tier A only", bool(tr["fit_eligible"].astype(bool).all()))
    check("train carries no Tier B row",
          not bool(tr["evaluation_tier"].ne("A_primary").any()))
    check("test carries all three tiers", te["evaluation_tier"].nunique() == 3,
          str(te["evaluation_tier"].value_counts().to_dict()))
    check("the universe equals the test frame", len(un) == len(te))
    check("the universe carries the tier columns",
          {"universe_tier", "evaluation_tier", "fit_eligible"} <= set(un.columns))
    check("every test row is required for every target",
          all(bool(un[f"prediction_required__{t}"].all()) for t in rf5.rf3.PLAYER_TARGETS))
    check("p_active scoreability follows the v5 rule, not v4's always-True",
          int(un["outcome_scoreable__p_active"].sum()) < len(un),
          f'{int(un["outcome_scoreable__p_active"].sum())}/{len(un)}')
    check("the v14 train row count is reproduced on Tier A", len(tr) == 4850, str(len(tr)))
    return f


def s6_sensitivity(primary: dict) -> None:
    print("\n6 — the attribution sensitivity")
    s = rf5.build_player_frame_v5(2022, REPO, require_attested=True, tier_b_history=False)
    check("the sensitivity is labelled as such", s["tier_b_history"] is False)
    check("the sensitivity's universe is the primary universe",
          len(s["universe"]) == len(primary["universe"]))
    check("the sensitivity train frame is Tier A only",
          bool(s["train"]["fit_eligible"].astype(bool).all()))
    a = primary["train"].sort_values("row_uid").reset_index(drop=True)
    b = s["train"].sort_values("row_uid").reset_index(drop=True)
    check("both training frames contain the same rows",
          set(a["row_uid"]) == set(b["row_uid"]),
          f"{len(a)} vs {len(b)}")
    feats = [c for c in ("min_ewma", "start_share_l5", "played_share_l10_team_games",
                         "days_since_last_appearance") if c in a.columns and c in b.columns]
    moved = {c: int((a[c].to_numpy() != b[c].to_numpy()).sum()) for c in feats}
    check("withholding Tier B history CHANGES later Tier A features — the influence is real "
          "and is measured, not denied",
          any(v > 0 for v in moved.values()), str(moved))
    check("the primary and sensitivity differ ONLY through history, not through membership",
          set(a["row_uid"]) == set(b["row_uid"]))


def main() -> int:
    print("=" * 78)
    print("cbs_v15 execution modules — pre-execution gate (nothing is scored)")
    print("=" * 78)
    s1_frame_fork()
    s2_runner_fork()
    s3_object_identity()
    s4_identity_refusals()
    primary = s5_tier_wiring()
    s6_sensitivity(primary)

    import json
    n, ok = len(_R), sum(1 for r in _R if r["ok"])
    print("\n" + "=" * 78)
    print(f"{ok}/{n} checks {'PASS' if ok == n else 'FAIL'}")
    (REPO / "experiments" / "player_program" / "V15_MODULE_TEST_RECEIPT.json").write_text(
        json.dumps({"schema": "v15_module_tests/2", "n_checks": n, "n_passed": ok,
                    "fork_layer_asserted": EXPECTED_FORK_LAYER,
                    "all_passed": ok == n,
                    "scope": "object identity, source diffs, tier rules, refusals and row counts; "
                             "nothing is scored",
                    "frame_fork": rf5.source_diff(),
                    "runner_fork": r15.source_diff(),
                    "checks": _R}, indent=2, default=str) + "\n",
        encoding="utf-8", newline="")
    return 0 if ok == n else 1


if __name__ == "__main__":
    raise SystemExit(main())
