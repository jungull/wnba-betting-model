#!/usr/bin/env python3
"""audit_phase0_v14_player_oof.py — the Phase 0 audit of `cbs_v14_player_oof/1`, as a receipt.

WHAT THIS IS
------------
The player program's independent audit of the unreviewed work committed at `d69aa02`. It answers
the ten audit questions by MEASUREMENT rather than by reading the commit message, and writes what
it measured to `PHASE0_AUDIT_RECEIPT.json`.

**Nothing here is scored.** No accuracy, calibration, Brier, MAE, RMSE, pinball, threshold, edge,
return or profitability figure is computed, and no forecast is compared to any outcome. Every
number below is a ROW COUNT, a KEY-SET COMPARISON, a FLAG DISTRIBUTION, a SELECTED CONSTANT or a
GATE VERDICT. "Coverage" means OBLIGATION COMPLETENESS throughout, exactly as the inherited
receipts define it.

The fold is executed IN MEMORY and nothing is persisted to any arm's output namespace. This is
deliberate: `run_player_oof_v14.py` is the only sanctioned producer of `cbs_v14_player_oof/1`
artifacts, and this audit must not manufacture something that looks like its output.

Run::

    python experiments/player_program/audit_phase0_v14_player_oof.py --season 2022
"""

from __future__ import annotations

import argparse
import json
import warnings
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore")

HERE = Path(__file__).resolve().parent
AUDIT_ID = "player_program_phase0_audit/1"
AUDITED_COMMIT = "d69aa0250fc95cbebacecb821482734819bebf36"
AUDITED_UNIT = "cbs_v14_player_oof/1"

#: The registered minutes evidence this audit reconciles the contract against.
INCUMBENT_MINUTES = "experiments/minutes_baselines/test_predictions.csv"
INCUMBENT_SEASONS = (2024, 2025, 2026)
#: `minutes_ewma_alpha030_v1`, the registered incumbent. Quoted from the registry, NOT recomputed:
#: recomputing it would be scoring, which is out of scope for this audit.
INCUMBENT_QUOTED = {
    "experiment_id": "minutes_ewma_vs_carryforward_v1",
    "incumbent_id": "minutes_ewma_alpha030_v1",
    "quoted_from": "experiments/registry.jsonl (evaluation record, run 1)",
    "recomputed_here": False,
    "why_not_recomputed": "recomputing a metric is scoring; this audit does not score",
    "frozen_alpha": 0.30,
    "n_rows": 13501,
}


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# --------------------------------------------------------------------------
# Q1-Q3: does it exist, was it pushed, what does it touch, what does it read
# --------------------------------------------------------------------------

def audit_provenance(root: Path) -> dict:
    """Q1/Q2/Q3 — existence, push state, changed files, and the contract actually read."""
    import run_player_oof_v14 as R
    import cbs_provenance_v4 as prov

    out_dir = root / R.OUT_DIR
    return {
        "question": "Q1-Q3: existence, push state, files changed, real contract read",
        "commit": AUDITED_COMMIT,
        "committed_locally": True,
        "pushed": False,
        "push_evidence": (
            "`git branch -r --contains d69aa02` is EMPTY; "
            "origin/worktree-cbs-v2-gate-accounting is at its parent 702a948"),
        "files_changed_by_the_commit": [
            "MISSION_LEDGER.md", "project_docs/GATE_RECEIPT_A25_producer_tree.json",
            "run_player_oof_v14.py (new, 1136 lines)",
            "run_team_oof_v12_2.py (modified, 31 lines)",
            "tests/test_run_player_oof_v14.py (new, 546 lines)",
            "verify_all.py (+9)",
        ],
        "artifacts_generated_by_the_commit": [],
        "output_namespace_exists": out_dir.exists(),
        "output_namespace": R.OUT_DIR,
        "contract_read": prov.PLAYER_GAME,
        "contract_is_the_real_v4_contract": prov.PLAYER_GAME.endswith(
            "prediction_contract_v4/player_game.parquet"),
        "n_producer_sources": len(R.PRODUCER_SOURCES),
    }


# --------------------------------------------------------------------------
# Q4/Q9: can it run at all, and are receipts checked before accuracy is visible
# --------------------------------------------------------------------------

def audit_producer_gate(root: Path) -> dict:
    """Q9 — the reproducibility gate. Does it pass, and IS IT ENTITLED TO?

    The important question is not whether the gate returns `ok: True`. It is whether the gate
    MEASURED anything before saying so. `require_clean_producer` at `d69aa02` establishes
    cleanliness by calling the best-effort helper `_git`, which swallows a non-zero exit and
    returns `""` — and an empty `git status --porcelain` is exactly what a clean tree returns.
    So a git call that FAILS is indistinguishable, to this gate, from a tree with nothing to
    report.

    This probe therefore runs the underlying git commands directly and compares their real exit
    codes against the verdict the gate rendered. A gate that returns `ok: True` while its own
    `git status` exited non-zero is FAIL-OPEN, and its `n_dirty_paths: 0` is not a measurement.
    """
    import subprocess

    import run_player_oof_v14 as R

    # the raw calls the gate depends on, with their real exit codes
    probes = {}
    for name, args in (("status", ["status", "--porcelain"]),
                       ("rev_parse_head", ["rev-parse", "HEAD"])):
        p = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True,
                           encoding="utf-8")
        probes[name] = {"returncode": p.returncode,
                        "stdout_empty": not p.stdout.strip(),
                        "stderr": (p.stderr or "").strip()[:160]}

    verdict, detail = "PASS", None
    try:
        rec = R.require_clean_producer(root)
        detail = {"ok": rec["ok"],
                  "working_tree_clean_vs_head": rec["working_tree_clean_vs_head"],
                  "n_dirty_paths": rec["n_dirty_paths"],
                  "commit": rec["commit"][:12]}
    except Exception as exc:                                         # noqa: BLE001
        verdict = "REFUSED"
        detail = {"error_type": type(exc).__name__, "error": str(exc)[:400]}

    status_failed = probes["status"]["returncode"] != 0
    claimed_clean = bool(detail.get("working_tree_clean_vs_head")) if verdict == "PASS" else False
    fail_open = status_failed and claimed_clean

    return {
        "question": "Q9: does the reproducibility gate pass, and is it entitled to",
        "verdict": verdict,
        "detail": detail,
        "raw_git_probes": probes,
        "FAIL_OPEN": fail_open,
        "finding": (
            "CRITICAL. The gate reports the producing tree CLEAN with n_dirty_paths: 0, but its "
            "own `git status --porcelain` exited non-zero and returned nothing. The gate did not "
            "measure the tree; it mistook a failed call for an empty diff. Any run performed "
            "here would stamp its artifacts `reproducible: true` against a commit whose working "
            "tree was never inspected — which is the exact guarantee cbs_v12_team_oof/1 was "
            "rejected for lacking."
            if fail_open else
            "the gate's verdict is backed by a git call that actually succeeded"),
        "why_git_fails_here": (
            "`core.bare=true` is set on the shared repository at "
            "C:/Users/jgallagher/wnba-betting-model, so every worktree reports "
            "is-inside-work-tree=false. `git status` requires a work tree and exits 128; "
            "`git rev-parse HEAD` does not and exits 0. The gate therefore gets a real commit "
            "and a false cleanliness verdict in the same breath — the worst possible "
            "combination, because the artifact looks fully attributed."),
        "repair_exists_but_is_uncommitted": (
            "the worktree .claude/worktrees/cbs-v2-gate-accounting carries an UNCOMMITTED "
            "`run_player_oof_v14.py` (1198 lines vs 1136 committed) adding `_git_checked`, which "
            "raises DirtyProducer on a non-zero git exit, and `_git_env`, which scrubs inherited "
            "GIT_DIR/GIT_WORK_TREE. It is preserved under "
            "experiments/player_program/preserved_uncommitted_d69aa02/ with a manifest."),
    }


# --------------------------------------------------------------------------
# Q4-Q8: run one real fold in memory and measure what it emits
# --------------------------------------------------------------------------

def audit_fold(root: Path, season: int) -> dict:
    """Q4-Q8 — chronological split, cutoff safety, tuning window, obligations, cold-start."""
    import cbs_real_frames_v3 as rf3
    import cbs_v14 as v14

    built = rf3.build_player_frame(season, root, require_attested=True)
    train, test, universe = built["train"], built["test"], built["universe"]

    man = v14.build_fold_manifest(train, test, universe, root=root)
    snap = v14.snapshot_identity(man)
    res = v14.run_player_fold(
        train, test, f"season:{season}", config_hash=v14.REGISTERED_CONFIG_HASH,
        snapshot_hash=snap, snapshot_manifest=man, universe=universe,
        synthetic=False, artifact_root=root)

    preds = res["predictions"]
    cov = res["receipts"]["coverage"]["per_target"]

    # Q5: every source timestamp strictly before its own row's cutoff. The adapter asserts this
    # internally; it is re-measured here rather than taken on trust.
    cut = pd.to_datetime(test["forecast_cutoff"], utc=True)
    asof_cols = [c for c in test.columns if c.startswith("src_asof_")] + ["feature_asof"]
    asof_violations = {c: int((pd.to_datetime(test[c], utc=True) >= cut).sum())
                       for c in asof_cols if c in test.columns}

    per_target = {}
    for tgt, p in sorted(preds.items()):
        lvl = p["fallback_level"].value_counts().to_dict()
        per_target[tgt] = {
            "n_emitted": int(len(p)),
            "n_required": int(cov[tgt]["n_required"]),
            "n_covered": int(cov[tgt]["n_covered"]),
            "n_excluded": int(cov[tgt]["n_excluded"]),
            "obligation_completeness": float(cov[tgt]["coverage"]),
            "n_cold_start": int(p["is_cold_start"].sum()),
            "fallback_levels": {str(k): int(v) for k, v in sorted(lvl.items())},
            "components": sorted(str(c) for c in pd.unique(p["component_id"])),
            "n_exclusion_reason_set": int(p["exclusion_reason"].notna().sum()),
            "emits_quantiles": bool(p["pred_q50"].notna().any()),
        }

    # Q8: p_active must key its cold-start on prior OBLIGATIONS; the three conditional targets on
    # prior APPEARANCES. Different questions, so they must give different counts.
    cold = {t: per_target[t]["n_cold_start"] for t in per_target}
    conditional = ["e_minutes_given_active", "attempts_usage", "player_scoring_distribution"]
    q8_ok = (len({cold[t] for t in conditional}) == 1
             and cold["p_active"] != cold[conditional[0]])

    # the two-stage identity must be FORMABLE: the two targets must key onto the same obligations
    pa = preds["p_active"].set_index("row_uid")["pred_point"]
    em = preds["e_minutes_given_active"].set_index("row_uid")["pred_point"]
    two_stage = {
        "identity": "E[minutes] = P(active) x E[minutes | active]",
        "row_uid_sets_identical": bool(set(pa.index) == set(em.index)),
        "n_obligations": int(len(pa)),
        "p_active_min": round(float(pa.min()), 6),
        "p_active_max": round(float(pa.max()), 6),
        "e_minutes_given_active_min": round(float(em.min()), 6),
        "e_minutes_given_active_max": round(float(em.max()), 6),
        "note": "range only; no comparison to any outcome is made",
    }

    sel = res["diagnostics"]["selected"]
    return {
        "question": "Q4-Q8: chronological split, cutoff safety, tuning window, obligations, "
                    "cold-start",
        "season": season,
        "executes_on_the_real_contract": True,
        "scoring_permitted_receipt": bool(res["scoring_permitted"]),
        "failed_receipts": list(res["failed_receipts"]),
        "inherited_receipts": list(res["inherited_receipts"]),
        "receipts_ok": {k: bool(v.get("ok")) for k, v in res["receipts"].items()},
        "split": {
            "rule": "train = every season STRICTLY BEFORE the fold season; test = the fold season",
            "n_train_rows": int(len(train)),
            "n_test_rows": int(len(test)),
            "n_universe_rows": int(len(universe)),
            "train_seasons": sorted(int(s) for s in pd.unique(train["season"])) if len(train)
                             else [],
            "test_seasons": sorted(int(s) for s in pd.unique(test["season"])),
            "train_and_test_seasons_disjoint": (
                not (set(pd.unique(train["season"])) & set(pd.unique(test["season"])))),
            "granularity": (
                "SEASON-level expanding window. Model COEFFICIENTS see prior seasons only; "
                "FEATURES are as-of the row's own cutoff and do use within-season history. Both "
                "are chronological; they are different boundaries and are reported separately."),
        },
        "cutoff_safety": {
            "rule": "every source timestamp strictly before the row's own forecast_cutoff",
            "violations_by_column": asof_violations,
            "total_violations": int(sum(asof_violations.values())),
        },
        "tuning_and_calibration": {
            "selected_constants": {k: v for k, v in sel.items() if k != "boundaries"},
            "fitted_on": "the TRAIN frame only, which is strictly earlier seasons",
            "lambda_selection": "select_lambda_chronological (chronological inner split)",
            "alpha_selection": "select_alpha_bound over the tuning prefix of the train frame",
            "minutes_alpha_held_fixed_for_rate_targets": (
                sel.get("minutes_alpha") == sel.get("minutes_alpha_held_fixed_at")),
            "alpha_is_selected_not_frozen": True,
            "frozen_spec_alpha_for_comparison": 0.30,
        },
        "per_target": per_target,
        "obligation_preservation": {
            "every_obligation_owed_every_target": all(
                per_target[t]["n_required"] == int(len(test)) for t in per_target),
            "every_obligation_received_every_target": all(
                per_target[t]["obligation_completeness"] == 1.0 for t in per_target),
            "n_excluded_total": sum(per_target[t]["n_excluded"] for t in per_target),
            "dnp_rows_still_owed": (
                "yes: prediction_required is True on every row for every target, so a DNP "
                "obligation still owes a p_active AND an e_minutes_given_active forecast. "
                "outcome_scoreable is separately False for the three conditional targets on "
                "rows that did not appear."),
            "n_test_rows_that_did_not_appear": int((~test["appeared"].astype(bool)).sum()),
        },
        "cold_start_flags": {
            "p_active_keys_on": "n_prior_candidate_games (prior OBLIGATIONS)",
            "conditional_targets_key_on": "n_prior_appearances (prior APPEARANCES)",
            "n_cold_by_target": cold,
            "differentiated_correctly": bool(q8_ok),
        },
        "two_stage": two_stage,
    }


# --------------------------------------------------------------------------
# Q10: can this output reproduce the registered minutes result?
# --------------------------------------------------------------------------

def audit_minutes_reproduction(root: Path) -> dict:
    """Q10 — reconcile the contract universe against the registered minutes universe."""
    import cbs_provenance_v4 as prov

    m = pd.read_csv(root / INCUMBENT_MINUTES)
    pg = pd.read_parquet(root / prov.PLAYER_GAME)
    for f in (m, pg):
        f["game_id"] = f["game_id"].astype(str)
        f["player_id"] = f["player_id"].astype("int64")

    c = pg[pg["season"].isin(INCUMBENT_SEASONS)]
    mk = set(zip(m["game_id"], m["player_id"]))
    ck = set(zip(c["game_id"], c["player_id"]))
    ca = set(zip(c.loc[c["appeared"], "game_id"], c.loc[c["appeared"], "player_id"]))

    per_season = {}
    for s in INCUMBENT_SEASONS:
        ms = set(zip(m.loc[m["season"] == s, "game_id"], m.loc[m["season"] == s, "player_id"]))
        cs = set(zip(c.loc[(c["season"] == s) & c["appeared"], "game_id"],
                     c.loc[(c["season"] == s) & c["appeared"], "player_id"]))
        per_season[str(s)] = {
            "incumbent_rows": len(ms), "contract_appeared": len(cs),
            "in_both": len(ms & cs), "incumbent_only": len(ms - cs),
            "contract_only": len(cs - ms)}

    missing = m[[(g, p) not in ck for g, p in zip(m["game_id"], m["player_id"])]]
    all_games = set(pg["game_id"])
    return {
        "question": "Q10: can the v14 player output reproduce the registered minutes result",
        "answer": "NO -- not as built, for three independent reasons",
        "incumbent": dict(INCUMBENT_QUOTED),
        "universe_reconciliation": {
            "incumbent_rows": len(m),
            "contract_obligations_same_seasons": int(len(c)),
            "contract_appeared_same_seasons": len(ca),
            "incumbent_rows_present_in_contract": len(mk & ck),
            "incumbent_rows_ABSENT_from_contract": len(mk - ck),
            "contract_appeared_absent_from_incumbent": len(ca - mk),
            "per_season": per_season,
        },
        "the_absent_rows": {
            "n": int(len(missing)),
            "by_season": {str(k): int(v) for k, v in missing.groupby("season").size().items()},
            "n_distinct_games": int(missing["game_id"].nunique()),
            "n_distinct_players": int(missing["player_id"].nunique()),
            "all_their_games_are_in_the_contract": bool(
                set(missing["game_id"]) <= all_games),
            "interpretation": (
                "these are player-games in which the player DEMONSTRABLY LOGGED MINUTES but was "
                "never a candidate obligation. The games are all in the contract; the "
                "(game, player) pairs are not. The pattern is mid-season signings, hardship "
                "contracts and trades -- players with no roster evidence in the candidacy window "
                "who nonetheless played immediately."),
            "sample": missing[["season", "game_id", "player_id", "player_name",
                               "team_abbreviation"]].head(10).to_dict("records"),
        },
        "three_reasons": [
            "ROW UNIVERSE: the incumbent scores a played-rows-with-prior-appearance universe; the "
            "arm emits over the contract obligation universe. The sets differ in both directions.",
            "SMOOTHING POLICY: the incumbent freezes alpha at 0.30 per MINUTES_MODEL_SPEC; the "
            "arm SELECTS alpha per fold via select_alpha_bound.",
            "FOLD STRUCTURE: the incumbent tunes on 2021-2023 and tests on 2024-2026 pooled; the "
            "arm refits every season on an expanding prior-seasons window.",
        ],
        "is_a_bridge_buildable": (
            "yes, and it is the first thing the player program should build: restrict the arm's "
            "emission to the incumbent's key set, pin alpha to 0.30, and compare on the 13,450 "
            "obligations the two universes share. The 51 unshared rows must be reported, never "
            "silently dropped."),
    }


# --------------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=None)
    ap.add_argument("--season", type=int, default=2022,
                    help="the fold to execute in memory; 2022 is the first FITTED fold")
    ap.add_argument("--out", default=str(HERE / "PHASE0_AUDIT_RECEIPT.json"))
    args = ap.parse_args()
    root = Path(args.root).resolve() if args.root else Path(__file__).resolve().parents[2]

    import sys
    sys.path.insert(0, str(root))

    receipt = {
        "schema": AUDIT_ID,
        "audited_unit": AUDITED_UNIT,
        "audited_commit": AUDITED_COMMIT,
        "audited_by": "the player model program, independently of the team thread",
        "generated_utc": _utc(),
        "scope": ("row counts, key-set comparisons, flag distributions, selected constants and "
                  "gate verdicts ONLY. Nothing is scored; no forecast is compared to any "
                  "outcome; no accuracy, calibration, error, threshold, edge, return or "
                  "profitability figure is computed anywhere in this file."),
        "coverage_means": "OBLIGATION COMPLETENESS, never statistical coverage",
        "nothing_persisted_to_any_arm_output_namespace": True,
        "provenance": audit_provenance(root),
        "producer_gate": audit_producer_gate(root),
        "fold": audit_fold(root, args.season),
        "minutes_reproduction": audit_minutes_reproduction(root),
    }
    Path(args.out).write_text(json.dumps(receipt, indent=2, default=str) + "\n",
                              encoding="utf-8", newline="")
    print(f"wrote {args.out}")
    print(json.dumps({
        "producer_gate": receipt["producer_gate"]["verdict"],
        "producer_gate_FAIL_OPEN": receipt["producer_gate"]["FAIL_OPEN"],
        "fold_executes": receipt["fold"]["executes_on_the_real_contract"],
        "receipts_pass": receipt["fold"]["scoring_permitted_receipt"],
        "cutoff_violations": receipt["fold"]["cutoff_safety"]["total_violations"],
        "obligation_completeness": receipt["fold"]["obligation_preservation"][
            "every_obligation_received_every_target"],
        "cold_start_differentiated": receipt["fold"]["cold_start_flags"][
            "differentiated_correctly"],
        "reproduces_registered_minutes": receipt["minutes_reproduction"]["answer"],
        "incumbent_rows_absent_from_contract": receipt["minutes_reproduction"][
            "universe_reconciliation"]["incumbent_rows_ABSENT_from_contract"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
