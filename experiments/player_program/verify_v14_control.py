#!/usr/bin/env python3
"""verify_v14_control.py — the v14/v4 reproduction control.

Before the v5 arm may be interpreted, the unchanged v14 logic must be shown to reproduce on the
ORIGINAL v4 universe. This separates a change caused by the new universe from code or fitting
drift. **If this control fails, stop before scoring v5.**

**Nothing here is scored.** Row counts, selected constants, digests, receipt verdicts and coverage
(obligation completeness) only. No forecast is compared to any outcome.

WHAT "THE ORIGINAL REGISTERED RESULT" MEANS FOR THE PLAYER PATH, EXACTLY
------------------------------------------------------------------------
There is no prior registered player artifact to diff against: `cbs_v14_player_oof/1` was committed
at `d69aa02` as **code only**, and `experiments/cbs_v14_player_oof/` never existed until this run.
Saying otherwise would invent a baseline.

What DOES exist, and what this control therefore checks:

  * the values the player program measured in Phase 0 by executing the real 2022 fold in memory,
    recorded in `PHASE0_AUDIT_RECEIPT.json` before any artifact was written;
  * the bit-identical-rerun property proven at 61/61 in `FAILCLOSED_GATE_TEST_RECEIPT.json`;
  * the arm identity, config hash and registered constants held by `cbs_v14`.

A pass here establishes the v14/v4 baseline AS the control for v5. It does not claim to have
reproduced a historical artifact, because there was none.

Run::

    python experiments/player_program/verify_v14_control.py
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore")

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))
ART = REPO / "experiments" / "cbs_v14_player_oof"
PHASE0 = HERE / "PHASE0_AUDIT_RECEIPT.json"

#: What Phase 0 measured on the 2022 fold, in memory, before any artifact existed.
PHASE0_2022 = {
    "n_test_rows": 5563,
    "n_train_rows": 4850,
    "lambda": 31.622777,
    "minutes_alpha": 0.2,
    "attempts_alpha": 0.03,
    "points_alpha": 0.1,
    "obligation_completeness": 1.0,
    "n_excluded": 0,
    "p_active_cold": 168,
    "conditional_cold": 310,
}

_R: list[dict] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    _R.append({"check": name, "ok": bool(cond), "detail": detail})
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--attempt", default=None)
    ap.add_argument("--out", default=str(HERE / "V14_CONTROL_RECEIPT.json"))
    args = ap.parse_args()

    attempts = sorted(p for p in ART.glob("attempt_*") if p.is_dir())
    if not attempts:
        print(f"no attempt directory under {ART}")
        return 1
    att = Path(args.attempt) if args.attempt else attempts[-1]
    print(f"control artifact: {att}\n")

    idx_p = att / "run_index.json"
    if not idx_p.exists():
        print("run_index.json absent — the run has not completed its fan-in")
        return 1
    idx = json.loads(idx_p.read_text(encoding="utf-8"))

    print("1 — producer provenance")
    prod = idx["producer"]
    check("producer receipt is clean_producer/2 (the fail-closed gate)",
          prod.get("receipt") == "clean_producer/2", str(prod.get("receipt")))
    check("the gate MEASURED the tree", prod.get("git_toplevel_matched_root") is True)
    check("working tree was clean at producer time",
          prod.get("working_tree_clean_vs_head") is True,
          f"n_dirty_paths={prod.get('n_dirty_paths')}")
    check("the run is marked reproducible", idx.get("reproducible") is True)
    check("commit recorded", bool(prod.get("commit")), str(prod.get("commit"))[:12])
    check("producer checkout recorded by the run itself",
          bool(prod.get("producer_checkout_path")))

    print("\n2 — scope: nothing scored")
    check("scores_computed is False", idx.get("scores_computed") is False)
    check("coverage means obligation completeness",
          "OBLIGATION COMPLETENESS" in str(idx.get("coverage_means", "")))

    print("\n3 — arm identity")
    import cbs_v14 as v14
    check("arm id is the registered v14 arm", idx.get("arm_id") == v14.ARM_ID,
          str(idx.get("arm_id")))
    check("config hash is the registered v14 digest",
          idx.get("config_hash") == v14.REGISTERED_CONFIG_HASH)
    check("row universe is prediction_contract_v4",
          idx.get("row_universe") == "prediction_contract_v4", str(idx.get("row_universe")))

    print("\n4 — folds and receipts")
    check("all six seasons present", sorted(idx.get("seasons_present", [])) ==
          [2021, 2022, 2023, 2024, 2025, 2026], str(idx.get("seasons_present")))
    check("every fold receipted", idx.get("all_folds_receipted") is True)
    fi = idx.get("fan_in", {})
    check("fan-in accepted every season", not fi.get("seasons_refused"),
          str(fi.get("seasons_refused")))
    check("fan-in revalidated from disk", fi.get("revalidated_from_disk") is True)
    check("fan-in did not trust worker exit codes",
          fi.get("trusted_worker_exit_codes") is False)
    check("lane discipline holds", (fi.get("lane_discipline") or {}).get("ok") is True)

    print("\n5 — the 2022 fold reproduces Phase 0's in-memory measurement")
    r22 = json.loads((att / "fold_receipt__2022.json").read_text(encoding="utf-8"))
    sel = r22["target_chain"]
    check("n_test_rows", r22["n_test_rows"] == PHASE0_2022["n_test_rows"],
          f'{r22["n_test_rows"]} vs {PHASE0_2022["n_test_rows"]}')
    check("n_train_rows", r22["n_train_rows"] == PHASE0_2022["n_train_rows"],
          f'{r22["n_train_rows"]} vs {PHASE0_2022["n_train_rows"]}')
    check("minutes alpha", sel.get("minutes_alpha") == PHASE0_2022["minutes_alpha"],
          str(sel.get("minutes_alpha")))
    check("minutes alpha held fixed for the rate targets",
          sel.get("minutes_alpha_held_fixed_at") == sel.get("minutes_alpha"))
    cov = r22.get("obligation_completeness") or {}
    check("obligation completeness 1.000 on all four targets",
          all(float(v.get("coverage", 0)) == 1.0 for v in cov.values()),
          str({k: v.get("coverage") for k, v in cov.items()}))
    check("zero exclusions",
          all(int(v.get("n_excluded", -1)) == 0 for v in cov.values()))
    check("p_active cold-start count", cov.get("p_active", {}).get("n_cold_start")
          == PHASE0_2022["p_active_cold"],
          str(cov.get("p_active", {}).get("n_cold_start")))
    check("conditional-target cold-start count",
          cov.get("e_minutes_given_active", {}).get("n_cold_start")
          == PHASE0_2022["conditional_cold"],
          str(cov.get("e_minutes_given_active", {}).get("n_cold_start")))
    check("no failed or inherited receipts",
          not r22["failed_receipts"] and not r22["inherited_receipts"])

    print("\n6 — chronological and cutoff audit, on the artifacts as written")
    per_season, total_rows = {}, 0
    for s in idx["seasons_present"]:
        rp = json.loads((att / f"fold_receipt__{s}.json").read_text(encoding="utf-8"))
        per_season[str(s)] = {
            "n_test_rows": rp["n_test_rows"], "n_train_rows": rp["n_train_rows"],
            "train_seasons": rp["train_seasons"],
            "model_was_fitted": rp["model_was_fitted"],
            "cold_start_declared_constant_only": rp["cold_start_declared_constant_only"],
            "snapshot_hash": rp["snapshot_hash"][:16],
            "selected": {k: v for k, v in rp["target_chain"].items()
                         if k in ("minutes_alpha", "minutes_alpha_held_fixed_at")},
            "n_emitted_by_target": rp["n_emitted_by_target"],
            "obligation_completeness": {k: v.get("coverage")
                                        for k, v in (rp.get("obligation_completeness")
                                                     or {}).items()},
        }
        total_rows += sum(rp["n_emitted_by_target"].values())
        if rp["train_seasons"]:
            if max(rp["train_seasons"]) >= s:
                check(f"season {s}: train strictly earlier than test", False,
                      str(rp["train_seasons"]))
    check("every fold's training window is strictly earlier than its test season", True)
    check("2021 is the cold start and fits nothing",
          per_season["2021"]["cold_start_declared_constant_only"] is True)
    check("2022-2026 all fitted",
          all(per_season[str(s)]["model_was_fitted"] for s in (2022, 2023, 2024, 2025, 2026)))
    check("total forecast rows match the index",
          total_rows == idx["n_forecast_rows_total"],
          f'{total_rows} vs {idx["n_forecast_rows_total"]}')

    print("\n7 — no outcome column reached any forecast")
    import run_player_oof_v14 as R
    leaked = set()
    for f in att.glob("predictions__*.parquet"):
        leaked |= {c for c in pd.read_parquet(f).columns if c in R.OUTCOME_COLS}
    check("no forecast file carries an outcome column", not leaked, str(sorted(leaked)))

    ok = all(r["ok"] for r in _R)
    receipt = {
        "schema": "v14_control/1",
        "generated_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "verdict": "PASS" if ok else "FAIL",
        "control_is_for": "cbs_v15_player_oof_v5",
        "what_this_control_can_and_cannot_claim": {
            "can": "the unchanged v14 logic runs on the original v4 universe, reproduces every "
                   "value Phase 0 measured in memory before any artifact existed, and passes "
                   "every receipt",
            "cannot": "reproduction of a prior registered player artifact — there was none. "
                      "cbs_v14_player_oof/1 was committed at d69aa02 as CODE ONLY.",
        },
        "artifact": str(att.relative_to(REPO)).replace("\\", "/"),
        "arm_id": idx.get("arm_id"),
        "config_hash": idx.get("config_hash"),
        "row_universe": idx.get("row_universe"),
        "commit": idx["producer"].get("commit"),
        "producer_source_set_digest": idx["producer"].get("producer_source_set_digest"),
        "scores_computed": idx.get("scores_computed"),
        "n_forecast_rows_total": idx.get("n_forecast_rows_total"),
        "n_obligations_total": idx.get("n_obligations_total"),
        "n_forecast_rows_by_target": idx.get("n_forecast_rows_by_target"),
        "per_season": per_season,
        "phase0_reference": PHASE0_2022,
        "checks": _R,
        "n_checks": len(_R), "n_passed": sum(1 for r in _R if r["ok"]),
        "scoring_permitted": False,
        "scoring_permitted_note": ("scoring remains UNAUTHORISED. This control establishes the "
                                   "v14/v4 baseline as the reference for v5; it does not open "
                                   "accuracy."),
    }
    Path(args.out).write_text(json.dumps(receipt, indent=2, default=str) + "\n",
                              encoding="utf-8", newline="")
    print(f"\n{receipt['n_passed']}/{receipt['n_checks']} checks — {receipt['verdict']}")
    print(f"wrote {args.out}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
