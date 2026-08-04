"""Tests for the D-c reproduction and the candidate fix. Synthetic data only.

Repo convention: standalone runnable, main() returns 1 on failure (pytest is
not installed).

    python experiments/player_program/ops_lane/O12_PER_GAME_EXECUTION_SCOPE/TESTS.py

Writes only into this node's own directory (a scratch chain under
_scratch_chains/, deleted and rebuilt each run). It appends to no real chain.
It reads the two real chains read-only, and only their metadata fields.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from evalharness.forecast_log import (            # noqa: E402
    DuplicateForecastError, log_forecast, read_forecasts, verify_chain,
)

_spec = importlib.util.spec_from_file_location(
    "per_game_obligation_scope", HERE / "per_game_obligation_scope.py")
pgos = importlib.util.module_from_spec(_spec)
sys.modules["per_game_obligation_scope"] = pgos   # dataclasses needs this
_spec.loader.exec_module(pgos)

SCRATCH = HERE / "_scratch_chains"
MODEL_HASH = "a" * 64
OTHER_HASH = "b" * 64
SNAP_HASH = "c" * 64
TIP = datetime(2026, 8, 4, 23, 0, tzinfo=timezone.utc)

FAILURES: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))
    if not cond:
        FAILURES.append(f"{name}: {detail}")


def core(game_id: str) -> dict:
    return {"model": "synthetic_test_model", "home_team": "AAA", "away_team": "BBB",
            "margin": 1.0, "total": 160.0, "game_id": game_id}


def firing_cutoffs(nominal: datetime, n: int, step_min: int = 15) -> list[datetime]:
    """n scheduler firings ending at the nominal instant, microsecond-resolution
    wall clocks — exactly what daily_forecast.py:893-895 produces with no --cutoff."""
    return [nominal - timedelta(minutes=step_min * (n - 1 - i), microseconds=17 * (i + 1))
            for i in range(n)]


# --------------------------------------------------------------------------
# 1. reproduction: the shipped dedup key cannot refuse a repeat serving
# --------------------------------------------------------------------------

def test_reproduction_shipped_key_never_refuses() -> None:
    print("\n[1] reproduction — shipped key on (game_id, forecast_cutoff, model_hash)")
    path = SCRATCH / "repro.jsonl"
    nominal = TIP - timedelta(minutes=30)          # the T-30m obligation
    refused = 0
    for c in firing_cutoffs(nominal, 4):
        try:
            log_forecast(game_id="G1", forecast_cutoff=c, decision_time_label="T-30m",
                         model_version_hash=MODEL_HASH, data_snapshot_hash=SNAP_HASH,
                         core_only_prediction=core("G1"), log_path=path)
        except DuplicateForecastError:
            refused += 1
    recs = read_forecasts(path)
    check("four 15-minute firings produce four chain records for ONE obligation",
          len(recs) == 4, f"n_records={len(recs)}")
    check("the chain's duplicate refusal never fires", refused == 0,
          f"refusals={refused}")
    check("all four records carry distinct forecast_cutoff values",
          len({r["forecast_cutoff"] for r in recs}) == 4)
    check("all four carry the SAME (game, label, model) obligation identity",
          len(pgos.served_obligation_keys(recs)) == 1)
    check("chain still verifies (the defect is semantic, not integrity)",
          verify_chain(path).ok)


# --------------------------------------------------------------------------
# 2. the fix refuses the repeat servings
# --------------------------------------------------------------------------

def test_fix_refuses_repeat_serving() -> None:
    print("\n[2] fix — obligation-keyed refusal at the call site")
    path = SCRATCH / "fixed.jsonl"
    nominal = TIP - timedelta(minutes=30)
    logged = refused = 0
    for c in firing_cutoffs(nominal, 4):
        try:
            pgos.guarded_log_forecast(
                log_forecast, read_forecasts=read_forecasts, log_path=path,
                game_id="G1", decision_time_label="T-30m",
                model_version_hash=MODEL_HASH, forecast_cutoff=c,
                data_snapshot_hash=SNAP_HASH, core_only_prediction=core("G1"))
            logged += 1
        except pgos.ObligationAlreadyServedError:
            refused += 1
    check("the obligation is served exactly once", logged == 1, f"logged={logged}")
    check("the other three firings are refused", refused == 3, f"refused={refused}")
    check("exactly one record on disk", len(read_forecasts(path)) == 1)
    check("chain verifies", verify_chain(path).ok)


# --------------------------------------------------------------------------
# 3. the fix must NOT collapse genuinely distinct obligations
# --------------------------------------------------------------------------

def test_fix_preserves_distinct_obligations() -> None:
    print("\n[3] regression — distinct obligations and distinct models still log")
    path = SCRATCH / "distinct.jsonl"
    ok = True
    for lab, hrs in pgos.CONTRACT_LABELS:
        pgos.guarded_log_forecast(
            log_forecast, read_forecasts=read_forecasts, log_path=path,
            game_id="G1", decision_time_label=lab, model_version_hash=MODEL_HASH,
            forecast_cutoff=TIP - timedelta(hours=hrs, microseconds=3),
            data_snapshot_hash=SNAP_HASH, core_only_prediction=core("G1"))
    check("all four contract labels for one game are logged",
          len(read_forecasts(path)) == 4)
    # a genuinely new frozen model version may re-serve the same obligation
    pgos.guarded_log_forecast(
        log_forecast, read_forecasts=read_forecasts, log_path=path,
        game_id="G1", decision_time_label="T-30m", model_version_hash=OTHER_HASH,
        forecast_cutoff=TIP - timedelta(minutes=30), data_snapshot_hash=SNAP_HASH,
        core_only_prediction=core("G1"))
    check("a NEW model_version_hash may re-serve the same obligation",
          len(read_forecasts(path)) == 5)
    # a second game is untouched
    pgos.guarded_log_forecast(
        log_forecast, read_forecasts=read_forecasts, log_path=path,
        game_id="G2", decision_time_label="T-30m", model_version_hash=MODEL_HASH,
        forecast_cutoff=TIP - timedelta(minutes=30), data_snapshot_hash=SNAP_HASH,
        core_only_prediction=core("G2"))
    check("a different game at the same label is not deduped",
          len(read_forecasts(path)) == 6)
    check("chain verifies", verify_chain(path).ok and ok)


# --------------------------------------------------------------------------
# 4. per-game scoping is declared, never silent
# --------------------------------------------------------------------------

def test_scoping_is_declared_not_silent() -> None:
    print("\n[4] per-game scope — declared, and enforced at the call site")
    slate = [{"game_id": "G1"}, {"game_id": "G2"}, {"game_id": "G3"}]
    now = datetime(2026, 8, 4, 22, 30, tzinfo=timezone.utc)
    kept, decl = pgos.scope_slate_to_games(slate, ["G2"], "2026-08-04", now,
                                           "serving G2 T-30m obligation")
    check("scoped run keeps exactly the named game",
          [g["game_id"] for g in kept] == ["G2"])
    check("the declaration names every excluded game (no silent filtering)",
          decl.to_dict()["excluded_game_ids"] == ["G1", "G3"])
    check("the declaration records the full slate size",
          decl.to_dict()["n_slate_games"] == 3)
    kept_all, decl_all = pgos.scope_slate_to_games(slate, None, "2026-08-04", now, "")
    check("game_ids=None preserves existing whole-slate behaviour exactly",
          len(kept_all) == 3 and decl_all is None)

    path = SCRATCH / "scoped.jsonl"
    try:
        pgos.guarded_log_forecast(
            log_forecast, read_forecasts=read_forecasts, log_path=path,
            game_id="G3", decision_time_label="T-30m",
            model_version_hash=MODEL_HASH, scoped_to_game_ids=["G2"],
            forecast_cutoff=now, data_snapshot_hash=SNAP_HASH,
            core_only_prediction=core("G3"))
        check("a scoped run cannot log an out-of-scope game", False, "no raise")
    except pgos.OutOfScopeError:
        check("a scoped run cannot log an out-of-scope game", True)
    check("nothing was written by the refused call", not path.exists())


# --------------------------------------------------------------------------
# 5. obligation construction
# --------------------------------------------------------------------------

def test_obligations() -> None:
    print("\n[5] obligation construction and due-ness")
    obls = pgos.obligations_for_game("G1", TIP)
    check("four obligations per game", len(obls) == 4)
    t30 = [o for o in obls if o.decision_time_label == "T-30m"][0]
    check("T-30m nominal instant is tip minus 30 minutes",
          t30.nominal_cutoff_utc == TIP - timedelta(minutes=30))
    # a 20-minute lead makes T-30m due from TIP-50m onward, not before
    due = pgos.due_obligations(obls, TIP - timedelta(minutes=35), set(), MODEL_HASH)
    check("T-30m is due 35 minutes before tip under a 20-minute lead",
          "T-30m" in {o.decision_time_label for o in due})
    due2 = pgos.due_obligations(obls, TIP - timedelta(minutes=55), set(), MODEL_HASH)
    check("T-30m is not yet due 55 minutes before tip (lead boundary is 50)",
          "T-30m" not in {o.decision_time_label for o in due2})
    served = {t30.key(MODEL_HASH)}
    due3 = pgos.due_obligations(obls, TIP - timedelta(minutes=35), served, MODEL_HASH)
    check("an already-served obligation is not re-listed as due",
          "T-30m" not in {o.decision_time_label for o in due3})
    check("nothing is due after tip",
          pgos.due_obligations(obls, TIP + timedelta(minutes=1), set(), MODEL_HASH) == [])


# --------------------------------------------------------------------------
# 6. the mirrored constant matches the source of truth
# --------------------------------------------------------------------------

def test_contract_labels_mirror() -> None:
    print("\n[6] mirrored CONTRACT_LABELS matches daily_forecast.py")
    src = (REPO / "daily_forecast.py").read_text(encoding="utf-8")
    line = [l for l in src.splitlines() if l.startswith("CONTRACT_LABELS")]
    check("daily_forecast.py defines CONTRACT_LABELS", len(line) == 1)
    if line:
        ns: dict = {}
        exec(line[0], ns)
        check("mirror is byte-equivalent to the source list",
              ns["CONTRACT_LABELS"] == pgos.CONTRACT_LABELS,
              f"source={ns['CONTRACT_LABELS']}")


# --------------------------------------------------------------------------
# 7. backward compatibility against the real chains (read-only)
# --------------------------------------------------------------------------

def test_real_chains_readonly() -> None:
    print("\n[7] real chains — read-only backward-compatibility check")
    official = REPO / "forecasts" / "forecast_log.jsonl"
    scratch = REPO / "experiments" / "forecast_dryrun" / "scratch_chain.jsonl"
    for p, expect_repeats in ((official, 0), (scratch, 3)):
        recs = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
        keys = [(r["game_id"], r["decision_time_label"], r["model_version_hash"])
                for r in recs]
        repeats = len(keys) - len(set(keys))
        shipped = [(r["game_id"], r["forecast_cutoff"], r["model_version_hash"])
                   for r in recs]
        check(f"{p.name}: shipped key finds zero repeats",
              len(shipped) - len(set(shipped)) == 0)
        check(f"{p.name}: obligation key finds {expect_repeats} repeat serving(s)",
              repeats == expect_repeats, f"n_records={len(recs)} repeats={repeats}")


# --------------------------------------------------------------------------
# 8. the label a record claims is a function of the firing instant
# --------------------------------------------------------------------------

def test_label_is_assigned_by_wall_clock() -> None:
    print("\n[8] decision_time_label drifts with the firing instant")

    def nearest_label(h: float) -> str:      # daily_forecast.py:598-599
        return min(pgos.CONTRACT_LABELS, key=lambda lh: abs(h - lh[1]))[0]

    check("nearest_label has no proximity bound: 4.776h from tip reads T-8h",
          nearest_label(4.776) == "T-8h")
    check("...and 4.716h from tip reads T-90m — a 3.6-minute drift flips it",
          nearest_label(4.716) == "T-90m")
    # reproduce the flip against the real scratch-chain records for game 1022600212
    p = REPO / "experiments" / "forecast_dryrun" / "scratch_chain.jsonl"
    recs = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    obs = [(r["core_only_prediction"]["hours_to_tip_at_cutoff"], r["decision_time_label"])
           for r in recs if r["game_id"] == "1022600212"]
    check("the real chain's labels are exactly nearest_label(hours_to_tip)",
          all(nearest_label(h) == lab for h, lab in obs), f"observed={obs}")


def main() -> int:
    if SCRATCH.exists():
        shutil.rmtree(SCRATCH)
    SCRATCH.mkdir(parents=True)
    test_reproduction_shipped_key_never_refuses()
    test_fix_refuses_repeat_serving()
    test_fix_preserves_distinct_obligations()
    test_scoping_is_declared_not_silent()
    test_obligations()
    test_contract_labels_mirror()
    test_real_chains_readonly()
    test_label_is_assigned_by_wall_clock()
    print("\n" + ("ALL TESTS PASSED" if not FAILURES
                  else f"{len(FAILURES)} FAILURE(S):\n  " + "\n  ".join(FAILURES)))
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
