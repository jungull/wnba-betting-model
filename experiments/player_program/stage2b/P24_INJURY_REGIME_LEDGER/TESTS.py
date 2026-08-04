"""P24_INJURY_REGIME_LEDGER -- standalone checks.

Re-derives this node's load-bearing numbers INDEPENDENTLY of measure_injury_regimes.py
(no import of it) and asserts FINDINGS.json agrees. Repo convention: main() returns 1
on failure. pytest is not available and is not used.

Run from the worktree root:
    python experiments/player_program/stage2b/P24_INJURY_REGIME_LEDGER/TESTS.py
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
FAILS: list[str] = []


def check(name: str, got, want) -> None:
    if got == want:
        print(f"  PASS  {name}: {got}")
    else:
        print(f"  FAIL  {name}: got {got!r}, want {want!r}")
        FAILS.append(name)


def main() -> int:
    f = HERE / "FINDINGS.json"
    if not f.exists():
        print("FAIL: FINDINGS.json missing -- run measure_injury_regimes.py first")
        return 1
    F = json.loads(f.read_text(encoding="utf-8"))

    inj = pd.read_csv(ROOT / "data" / "injury_history" / "injury_history.csv", dtype=str)
    prior = pd.read_parquet(ROOT / "experiments" / "player_program" /
                            "projected_exposure_v1" / "team_possession_prior_v1.parquet")
    prior["game_date"] = pd.to_datetime(prior["game_date"])

    print("== input identity ==")
    h = hashlib.sha256(
        (ROOT / "data" / "injury_history" / "injury_history.csv").read_bytes()).hexdigest()
    check("injury_history.csv sha256 pinned in FINDINGS",
          h, F["inputs"]["injury_history_csv"]["sha256"])
    check("registry source_snapshot sha256 equals the bytes",
          F["registered_consumer_binding"]["bytes_agree_with_the_receipt"], True)

    print("== the S3 split ==")
    is_r = inj["category"].str.startswith("missed_game")
    check("total rows", int(len(inj)), 8340)
    check("regime R (missed_game_*) rows", int(is_r.sum()), 5373)
    check("regime T (wire) rows", int((~is_r).sum()), 2967)
    check("FINDINGS verdict on the packet's split",
          F["S3_split_reproduction"]["verdict"], "AGREE")

    print("== regime is a source partition, not a label ==")
    fam = inj["source_page"].str.extract(r"^(espn_summary|bbref_transactions)")[0]
    check("regime R rows from espn_summary only",
          int((fam[is_r] == "espn_summary").sum()), 5373)
    check("regime T rows from bbref_transactions only",
          int((fam[~is_r] == "bbref_transactions").sum()), 2967)

    print("== no source timestamp exists ==")
    ts_cols = [c for c in inj.columns
               if any(k in c.lower() for k in ("time", "stamp", "observed", "captured",
                                               "asof", "fetched", "reported",
                                               "announced", "updated"))]
    check("timestamp-like columns", ts_cols, [])
    check("date is date-granularity only",
          sorted({int(x) for x in inj["date"].str.len().unique()}), [10])
    check("raw payload dir absent (provenance unrecoverable)",
          (ROOT / "data" / "injury_history" / "raw").exists(), False)

    print("== nothing is eligible ==")
    check("ELIGIBLE rows", F["classification_ledger"]["ELIGIBLE"], 0)
    check("fitted-universe contribution",
          F["classification_ledger"]["fitted_feature_universe_contribution"], 0)
    check("availability-report contribution",
          F["classification_ledger"]["availability_report_contribution"], 8340)
    check("regime R classification",
          F["regime_R_realised_participation"]["classification"], "NOT A PREGAME FEATURE")
    check("regime T classification",
          F["regime_T_announcement_wire"]["classification"], "CUTOFF_UNPROVEN")

    print("== six folds, all zero, both universes reported ==")
    rows = F["coverage_by_season_and_fold"]["rows"]
    check("fold count", len(rows), 6)
    check("folds are the six seasons", [r["fold"] for r in rows],
          [2021, 2022, 2023, 2024, 2025, 2026])
    check("ELIGIBLE zero in every fold",
          sorted({r["ELIGIBLE_rows"] for r in rows}), [0])
    check("cutoff-valid coverage zero in every fold",
          sorted({r["cutoff_valid_coverage_of_fitted_universe_pct"] for r in rows}), [0.0])
    check("fold team-game rows sum to the scheduled universe",
          sum(r["team_game_rows"] for r in rows), int(len(prior)))
    check("fold resolved rows sum to the resolved universe",
          sum(r["team_game_rows_resolved"] for r in rows), int(prior["pace_resolved"].sum()))
    check("resolved universe is the packet's 2982", int(prior["pace_resolved"].sum()), 2982)
    check("resolved clusters are the packet's 1491",
          int(prior[prior["pace_resolved"]]["game_id"].nunique()), 1491)
    check("fold R rows sum to 5373", sum(r["regime_R_rows"] for r in rows), 5373)
    check("fold T rows sum to 2967", sum(r["regime_T_rows"] for r in rows), 2967)

    print("== regime R contemporaneity, re-derived ==")
    cities = pd.read_csv(ROOT / "data" / "reference" / "team_cities.csv")
    m = dict(zip(cities["abbreviation"], cities["team_id"]))
    m["PHX"], m["POR"] = m["PHO"], m["PDX"]
    prior["ds"] = prior["game_date"].dt.strftime("%Y-%m-%d")
    played = set(zip(prior["team_id"], prior["ds"]))
    r = inj[is_r]
    hit = sum((m.get(t), d) in played for t, d in zip(r["team"], r["date"]))
    check("regime R rows landing on a contract game for that team", hit, 5354)
    miss = r[[(m.get(t), d) not in played for t, d in zip(r["team"], r["date"])]]
    check("every non-landing row is a Commissioner's Cup final row",
          bool(miss["notes"].str.contains(r"\[commissioners-cup-final\]").all()), True)
    key = set(zip(r["team"].map(m), r["date"]))
    contam = sum((t, d) in key for t, d in zip(prior["team_id"], prior["ds"]))
    check("team-games a naive same-day R join would contaminate", contam, 2337)

    print("== span truncation ==")
    check("injury file last date", inj["date"].max(), "2026-07-29")
    check("contract last game date", prior["game_date"].max().strftime("%Y-%m-%d"), "2026-07-31")
    check("team-game rows postdating the injury file",
          int((prior["game_date"] > pd.Timestamp("2026-07-29")).sum()), 12)
    check("FINDINGS corrects the packet's 'full contract span'",
          F["span_gaps"]["verdict"].startswith("CORRECT"), True)

    print("== declared-cutoff bands ==")
    b = F["declared_cutoff_test"]["bands_relative_to_the_next_game_for_that_team"]
    check("bands sum to the testable regime-T rows",
          sum(b.values()), F["declared_cutoff_test"]["regime_T_rows_tested"])
    check("testable rows + null-team rows = 2967",
          F["declared_cutoff_test"]["regime_T_rows_tested"]
          + F["regime_T_announcement_wire"]["rows_with_null_team"], 2967)
    check("ambiguous D-1 rows", b["AMBIGUOUS_D_MINUS_1"], 313)
    check("consumer touches zero regime-R rows",
          F["declared_cutoff_test"]["consumer"]["regime_R_rows_consumed"], 0)

    print("== documentation reproduction ==")
    check("INJURY_HISTORY.md coverage table agrees on all six seasons",
          F["documentation_table_reproduction"]["all_agree"], True)

    print("== stop condition is raised, not resolved ==")
    check("one stop condition tripped", len(F["stop_conditions"]["tripped"]), 1)
    check("it is raised, not resolved",
          F["stop_conditions"]["tripped"][0]["action"], "RAISED, NOT RESOLVED")

    print("== report carries the verbatim epistemic-status line ==")
    rep = (HERE / "REPORT.md").read_text(encoding="utf-8")
    line = ("VERIFIED_READ_ONLY_DERIVATION. Classifies fields by epistemic regime. A "
            "field passing classification is ELIGIBLE for consideration, which is not "
            "the same as useful or admitted.")
    check("epistemic-status line present verbatim", line in rep, True)

    print()
    if FAILS:
        print(f"FAILED {len(FAILS)} check(s): {FAILS}")
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
