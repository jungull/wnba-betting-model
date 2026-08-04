"""
U13_MONITORING_INTERFACE -- standalone test suite. No pytest.

PRODUCT SCAFFOLD built against fixtures. Carries no scientific claim and must not imply a model
has been promoted.

Run:  python experiments/player_program/product_lane/U13_MONITORING_INTERFACE/TESTS.py
main() returns 0 when every check passes and 1 otherwise.

The suite is organised around the node's three acceptance criteria:

  A. stale inputs, missing lineups and failed jobs are each INDIVIDUALLY visible
  B. rollback state is visible
  C. a silent failure is impossible: absence of data renders as an explicit alert

Section C is the load-bearing one and is tested three ways: per-fixture assertions, an exhaustive
ablation sweep over every field of a healthy snapshot, and a rendered-text scan proving the
suppressed numeral never reaches the panel.
"""

from __future__ import annotations

import copy
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import monitor_schema as S                     # noqa: E402
from monitor_state import evaluate             # noqa: E402
from render_monitor import render_text         # noqa: E402

PROGRAM = os.path.abspath(os.path.join(HERE, "..", ".."))
FIXTURES = os.path.join(HERE, "fixtures")

FAILURES = []
CHECKS = [0]


def check(condition, label, detail=""):
    CHECKS[0] += 1
    if condition:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}  {detail}")
        FAILURES.append(f"{label} :: {detail}")
    return bool(condition)


def load_fixture(name):
    with open(os.path.join(FIXTURES, f"{name}.json"), encoding="utf-8") as fh:
        return json.load(fh)


def evaluate_fixture(name):
    fx = load_fixture(name)
    return fx, evaluate(fx.get("snapshot"), fx.get("evaluated_at_utc"))


def shown(ev):
    return [r for r in ev["projection_rows"] if r["display"]["kind"] == S.DISPLAY_NUMBER]


def codes(ev):
    return {a["code"] for a in ev["alerts"]}


# ---------------------------------------------------------------------------------------------
# 0. fixtures load and are self-describing
# ---------------------------------------------------------------------------------------------

def test_fixtures_load():
    print("\n[0] fixtures")
    names = sorted(f[:-5] for f in os.listdir(FIXTURES) if f.endswith(".json"))
    check(len(names) >= 8, "at least eight fixtures exist", f"found {names}")
    for name in names:
        fx = load_fixture(name)
        check(fx.get("synthetic") is True, f"fixture {name} declares itself synthetic")
        check(bool(fx.get("evaluated_at_utc")), f"fixture {name} pins an evaluation clock")
        check("PRODUCT SCAFFOLD" in (fx.get("epistemic_status") or ""),
              f"fixture {name} carries the epistemic status")
    return names


# ---------------------------------------------------------------------------------------------
# A. the four failure classes are individually visible
# ---------------------------------------------------------------------------------------------

def test_declared_expectations(names):
    print("\n[A] every fixture meets its own declared expectation")
    for name in names:
        fx, ev = evaluate_fixture(name)
        exp = fx.get("expect") or {}
        if "serving" in exp:
            check(ev["serving"] == exp["serving"],
                  f"{name}: serving == {exp['serving']}", f"got {ev['serving']}")
        if "n_projections_shown" in exp:
            check(ev["counters"]["n_projections_shown"] == exp["n_projections_shown"],
                  f"{name}: {exp['n_projections_shown']} projection(s) shown",
                  f"got {ev['counters']['n_projections_shown']}")
        for code in exp.get("must_alert_codes", []):
            check(code in codes(ev), f"{name}: raises {code}", f"alerts={sorted(codes(ev))}")


def test_stale_input_visible():
    print("\n[A1] a stale input is individually visible")
    _, ev = evaluate_fixture("stale_input")
    stale_rows = [r for r in ev["input_rows"] if r["status"] == S.INPUT_STALE]
    check(len(stale_rows) == 1, "exactly one input row is STALE", f"{stale_rows}")
    row = stale_rows[0]
    check(row["input_id"] == "odds_feed", "the stale row names the input", row["input_id"])
    check(row["age_seconds"] is not None and row["age_seconds"] > row["max_age_seconds"],
          "the row carries the measured age and the breached limit",
          f"age={row['age_seconds']} limit={row['max_age_seconds']}")
    other = [r for r in ev["input_rows"] if r["input_id"] != "odds_feed"]
    check(all(r["status"] == S.INPUT_OK for r in other),
          "the healthy inputs are NOT collapsed into the same alarm",
          f"{[(r['input_id'], r['status']) for r in other]}")
    check(not any(c.startswith("LINEUP_") or c.startswith("JOB_") for c in codes(ev)),
          "a stale input does not masquerade as a lineup or job failure", f"{sorted(codes(ev))}")
    check(not shown(ev), "no projection renders while a required input is stale")


def test_missing_lineup_visible():
    print("\n[A2] a missing lineup is individually visible and entity-scoped")
    _, ev = evaluate_fixture("missing_lineup")
    missing = [r for r in ev["lineup_rows"] if r["status"] == S.LINEUP_MISSING]
    check(len(missing) == 1, "exactly one lineup row is MISSING", f"{missing}")
    check(missing[0]["team"] == "AAA", "the row names the team", missing[0]["team"])
    check(missing[0]["n_players"] is None,
          "the row does not fabricate a player count", f"{missing[0]['n_players']}")
    kept = shown(ev)
    check(len(kept) == 1 and kept[0]["team"] == "BBB",
          "the team WITH a lineup still renders; the gap is scoped to the affected entity",
          f"{[r['team'] for r in kept]}")
    suppressed = [r for r in ev["projection_rows"] if r["display"]["kind"] == S.DISPLAY_ALERT]
    check(len(suppressed) == 1 and "LINEUP_MISSING" in suppressed[0]["display"]["codes"],
          "the affected projection is suppressed and names the cause",
          f"{[r['display'] for r in suppressed]}")


def test_undeclared_lineup_dependency_still_gates():
    print("\n[A2b] forgetting to declare the lineup dependency does not buy a number")
    fx = load_fixture("missing_lineup")
    snap = copy.deepcopy(fx["snapshot"])
    for p in snap["projections"]:
        p["depends_on_lineups"] = []          # the projection now claims no lineup dependency
    ev = evaluate(snap, fx["evaluated_at_utc"])
    teams = {r["team"] for r in shown(ev)}
    check("AAA" not in teams,
          "the projection for the team with no lineup is still withheld", f"shown={teams}")


def test_failed_jobs_visible():
    print("\n[A3] failed, never-run and late jobs are three distinct states")
    _, ev = evaluate_fixture("failed_job")
    by_id = {r["job_id"]: r for r in ev["job_rows"]}
    check(by_id["nightly_feature_build"]["status"] == S.JOB_FAILED,
          "an outright failure reads FAILED", by_id["nightly_feature_build"]["status"])
    check(by_id["lineup_poll"]["status"] == S.JOB_DID_NOT_RUN,
          "a job that was due with no run reads DID_NOT_RUN", by_id["lineup_poll"]["status"])
    check(by_id["odds_poll"]["status"] == S.JOB_LATE,
          "a job DECLARING SUCCEEDED but completing after its own cutoff is downgraded to LATE",
          f"declared={by_id['odds_poll']['declared_outcome']} "
          f"status={by_id['odds_poll']['status']}")
    lat = by_id["odds_poll"]["latency_minutes_past_cutoff"]
    check(lat is not None and abs(lat - 11.133) < 0.01,
          "the measured latency past cutoff is carried on the row", f"{lat}")
    check(len({by_id[j]["status"] for j in by_id}) == 3,
          "the three pathologies do not collapse into one status")
    check(not shown(ev), "no projection renders while a blocking job has failed")


def test_rollback_visible():
    print("\n[B] rollback state is visible")
    _, active = evaluate_fixture("rollback_active")
    rb = active["rollback_row"]
    check(rb["state"] == S.ROLLBACK_ACTIVE, "ACTIVE rollback is reported as ACTIVE", rb["state"])
    check(rb["active_model_version"] and rb["previous_model_version"],
          "both the serving and the superseded version are named", f"{rb}")
    check("ROLLBACK_ACTIVE" in codes(active),
          "an active rollback always raises its banner, even while serving")
    check(len(shown(active)) == 2,
          "an active rollback does not suppress: the numbers are real, the banner is mandatory")
    panel = render_text(active)
    check("ROLLBACK" in panel and rb["previous_model_version"] in panel,
          "the rendered panel shows the rollback block and the superseded version")

    _, pending = evaluate_fixture("rollback_pending")
    check(pending["rollback_row"]["state"] == S.ROLLBACK_PENDING, "PENDING is reported")
    check(not shown(pending),
          "while a rollback is in flight the serving version is indeterminate, so nothing renders")

    # fail-closed: an absent rollback block is UNKNOWN, not NONE
    ev = evaluate({"schema": S.SNAPSHOT_SCHEMA}, "2026-08-04T22:40:00Z")
    check(ev["rollback_row"]["state"] == S.ROLLBACK_UNKNOWN,
          "an absent rollback block reads UNKNOWN, never NONE", ev["rollback_row"]["state"])
    ev2 = evaluate({"schema": S.SNAPSHOT_SCHEMA, "rollback": {"state": "definitely_fine"}},
                   "2026-08-04T22:40:00Z")
    check(ev2["rollback_row"]["state"] == S.ROLLBACK_UNKNOWN,
          "an out-of-vocabulary rollback state reads UNKNOWN", ev2["rollback_row"]["state"])


# ---------------------------------------------------------------------------------------------
# C. silent failure is impossible
# ---------------------------------------------------------------------------------------------

def test_silent_failure_attempt():
    print("\n[C1] a snapshot with numbers and no evidence shows no numbers")
    fx, ev = evaluate_fixture("silent_failure_attempt")
    check(not shown(ev), "zero projections render", f"{shown(ev)}")
    check(ev["serving"] == "SUPPRESSED", "the banner says SUPPRESSED", ev["serving"])
    panel = render_text(ev)
    for numeral in ("81.25", "79.5"):
        check(numeral not in panel,
              f"the numeral {numeral} never reaches the rendered panel")
    check(S.ALERT_CELL_TEXT in panel, "the cells render the explicit alert token")
    check(ev["counters"]["n_alerts_critical"] > 0, "critical alerts are raised")


def test_empty_and_garbage_inputs():
    print("\n[C2] the evaluator is fail-closed on absent and malformed input")
    cases = {
        "None": None,
        "empty dict": {},
        "list": [1, 2, 3],
        "string": "everything is fine",
        "wrong schema": {"schema": "something/else", "projections": [
            {"game_key": "g", "team": "t", "metric": "m", "value": 99.9}]},
    }
    for label, payload in cases.items():
        try:
            ev = evaluate(payload, "2026-08-04T22:40:00Z")
        except Exception as exc:                                  # noqa: BLE001
            check(False, f"evaluate({label}) does not raise", repr(exc))
            continue
        check(ev["serving"] == "SUPPRESSED", f"evaluate({label}) suppresses", ev["serving"])
        check(not shown(ev), f"evaluate({label}) shows no numbers")
        check(ev["counters"]["n_alerts"] > 0, f"evaluate({label}) raises at least one alert")
        panel = render_text(ev)
        check("99.9" not in panel, f"evaluate({label}) never prints the smuggled value")
    # a missing clock is itself a failure
    ev = evaluate(load_fixture("healthy")["snapshot"], None)
    check("CLOCK_UNKNOWN" in codes(ev) and not shown(ev),
          "no evaluation clock means nothing can be aged, so nothing renders")


def _leaf_paths(obj, prefix=()):
    """Every addressable location in a nested dict/list snapshot."""
    out = [prefix] if prefix else []
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.extend(_leaf_paths(v, prefix + (k,)))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out.extend(_leaf_paths(v, prefix + (i,)))
    return out


def _delete_at(obj, path):
    cur = obj
    for step in path[:-1]:
        cur = cur[step]
    last = path[-1]
    if isinstance(cur, dict):
        cur.pop(last, None)
    elif isinstance(cur, list) and isinstance(last, int) and 0 <= last < len(cur):
        cur.pop(last)


def test_ablation_sweep():
    """
    Exhaustive monotonicity property.

    Deleting information from a healthy snapshot may never INCREASE the number of rendered
    numbers, and every deletion that touches a serving dependency must strictly reduce it.
    This is the machine-checkable form of 'absence of data can never render as a number'.
    """
    print("\n[C3] ablation sweep over every field of the healthy snapshot")
    fx = load_fixture("healthy")
    clock = fx["evaluated_at_utc"]
    baseline = evaluate(fx["snapshot"], clock)
    n_base = baseline["counters"]["n_projections_shown"]
    check(n_base == 2, "baseline healthy snapshot shows both projections", f"{n_base}")

    paths = _leaf_paths(fx["snapshot"])
    regressions = []
    silent = []
    n_reduced = 0
    for path in paths:
        snap = copy.deepcopy(fx["snapshot"])
        try:
            _delete_at(snap, path)
        except (KeyError, IndexError, TypeError):
            continue
        try:
            ev = evaluate(snap, clock)
        except Exception as exc:                                  # noqa: BLE001
            regressions.append((path, f"raised {exc!r}"))
            continue
        n = ev["counters"]["n_projections_shown"]
        if n > n_base:
            regressions.append((path, f"shown rose {n_base} -> {n}"))
        if n < n_base:
            n_reduced += 1
            if not ev["alerts"]:
                silent.append((path, "fewer numbers shown but NO alert raised"))
        # every suppressed projection must carry at least one explanatory code
        for row in ev["projection_rows"]:
            if row["display"]["kind"] == S.DISPLAY_ALERT and not row["display"]["codes"]:
                silent.append((path, "alert cell with no code"))

    check(len(paths) >= 100, f"the sweep covers {len(paths)} snapshot locations")
    check(not regressions, "deleting information never increases the number of rendered numbers",
          f"{regressions[:5]}")
    check(not silent, "no deletion reduces output without raising an alert", f"{silent[:5]}")
    check(n_reduced >= 20,
          f"{n_reduced} of {len(paths)} deletions actually suppressed a projection "
          "(the sweep bites)")
    print(f"        swept {len(paths)} locations; {n_reduced} suppressed a projection")


def test_null_sweep():
    print("\n[C4] null sweep: setting any field to null never yields more numbers")
    fx = load_fixture("healthy")
    clock = fx["evaluated_at_utc"]
    n_base = evaluate(fx["snapshot"], clock)["counters"]["n_projections_shown"]
    bad = []
    for path in _leaf_paths(fx["snapshot"]):
        snap = copy.deepcopy(fx["snapshot"])
        cur = snap
        try:
            for step in path[:-1]:
                cur = cur[step]
            cur[path[-1]] = None
        except (KeyError, IndexError, TypeError):
            continue
        try:
            ev = evaluate(snap, clock)
        except Exception as exc:                                  # noqa: BLE001
            bad.append((path, repr(exc)))
            continue
        if ev["counters"]["n_projections_shown"] > n_base:
            bad.append((path, "nulling a field produced MORE rendered numbers"))
    check(not bad, "nulling any field is never rewarded with a number", f"{bad[:5]}")


def test_stale_snapshot_is_a_failure():
    print("\n[C5] a frozen dashboard is a failing dashboard")
    fx = load_fixture("healthy")
    ev = evaluate(fx["snapshot"], "2026-08-05T04:00:00Z")   # ~5h after the snapshot was generated
    check("SNAPSHOT_STALE" in codes(ev),
          "an old snapshot raises SNAPSHOT_STALE", f"{sorted(codes(ev))}")
    check(not shown(ev), "an old snapshot renders no numbers: the last good frame is not reused")


def test_alert_cell_is_never_numeric():
    print("\n[C6] the alert token is never mistakable for a value")
    check(not re.match(r"^[\d\s.+-]*$", S.ALERT_CELL_TEXT),
          "the alert token contains no numeral-only rendering", S.ALERT_CELL_TEXT)
    check(S.ALERT_CELL_TEXT.strip() not in ("", "-", "--", "n/a", "0"),
          "the alert token is not a blank or a dash", S.ALERT_CELL_TEXT)
    for name in sorted(f[:-5] for f in os.listdir(FIXTURES) if f.endswith(".json")):
        _, ev = evaluate_fixture(name)
        for row in ev["projection_rows"]:
            d = row["display"]
            if d["kind"] == S.DISPLAY_ALERT:
                if "value" in d or re.search(r"\d", d["text"]):
                    check(False, f"{name}: suppressed cell leaks a value", f"{d}")
                    return
    check(True, "no suppressed cell in any fixture carries or prints a value")


def test_unbound_reality():
    print("\n[C7] pointed at the repository's real capture state, the panel shows nothing")
    _, ev = evaluate_fixture("unbound_reality")
    unbound = [r for r in ev["input_rows"] if r["status"] == S.INPUT_UNBOUND]
    check(len(unbound) == 8, "all eight D11 domains render UNBOUND", f"{len(unbound)}")
    check(not shown(ev), "no projection renders when no source is bound")
    panel = render_text(ev)
    check("81.25" not in panel and "79.5" not in panel,
          "the plausible fixture values never reach the panel")


# ---------------------------------------------------------------------------------------------
# D. model-agnosticism
# ---------------------------------------------------------------------------------------------

def _forbidden_tokens():
    """Every arm/experiment/artifact identifier the registry knows, plus the frozen incumbent."""
    tokens = {"D_ewma_shrunk"}
    reg = os.path.join(PROGRAM, "arm_registry.jsonl")
    with open(reg, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            for key in ("arm_id", "experiment_id", "artifact_id"):
                v = rec.get(key)
                if isinstance(v, str) and len(v) > 3:
                    tokens.add(v)
    state = os.path.join(PROGRAM, "PROGRAM_STATE.json")
    with open(state, encoding="utf-8") as fh:
        doc = json.load(fh)
    arm = (doc.get("frozen_incumbent") or {}).get("arm")
    if isinstance(arm, str):
        tokens.add(arm)
    return tokens


def test_model_agnostic():
    print("\n[D] the interface surface names no model")
    tokens = _forbidden_tokens()
    check(len(tokens) > 10, f"{len(tokens)} model identifiers collected from the registry")
    surface = ["monitor_schema.py", "monitor_state.py", "render_monitor.py", "build_views.py",
               "make_fixtures.py"]
    surface += [os.path.join("fixtures", f) for f in sorted(os.listdir(FIXTURES))
                if f.endswith(".json")]
    hits = []
    for rel in surface:
        with open(os.path.join(HERE, rel), encoding="utf-8") as fh:
            text = fh.read()
        for tok in tokens:
            if tok in text:
                hits.append((rel, tok))
    check(not hits, "no arm, experiment or artifact identifier appears on the product surface",
          f"{hits[:5]}")

    # the numbers of the frozen incumbent must not appear either
    perf = ["2.9675", "2.896"]
    perf_hits = [(rel, p) for rel in surface for p in perf
                 if p in open(os.path.join(HERE, rel), encoding="utf-8").read()]
    check(not perf_hits, "no incumbent performance figure appears on the product surface",
          f"{perf_hits}")

    # the interface must carry whatever version it is given, whoever produced it
    fx = load_fixture("healthy")
    for label in ("some-model-A", "totally-different-model-B", "x" * 64):
        snap = copy.deepcopy(fx["snapshot"])
        snap["model_binding"]["model_version"] = label
        snap["rollback"]["active_model_version"] = label
        ev = evaluate(snap, fx["evaluated_at_utc"])
        ok = (ev["model_binding"]["model_version"] == label
              and len(shown(ev)) == 2
              and label in render_text(ev))
        check(ok, f"the interface serves an arbitrary model version {label[:24]!r} unchanged")


def test_binding_required():
    print("\n[D2] an unbound or partially bound model version cannot serve")
    fx = load_fixture("healthy")
    for mutation, label in (
        (lambda s: s["model_binding"].pop("model_version"), "no model_version"),
        (lambda s: s["model_binding"].update({"model_version": ""}), "empty model_version"),
        (lambda s: s["model_binding"].pop("artifact_sha256"), "no artifact hashes"),
        (lambda s: s["model_binding"]["artifact_sha256"].update({"feature_bundle": None}),
         "one null artifact hash"),
    ):
        snap = copy.deepcopy(fx["snapshot"])
        mutation(snap)
        ev = evaluate(snap, fx["evaluated_at_utc"])
        check(not shown(ev), f"{label}: nothing renders", f"serving={ev['serving']}")


# ---------------------------------------------------------------------------------------------
# E. outputs on disk are current
# ---------------------------------------------------------------------------------------------

def test_outputs_present_and_current():
    print("\n[E] the committed views match the code that generated them")
    for name in ("MONITOR_VIEWS.md", "MONITOR_EVALUATIONS.json", "REPO_FACTS.json",
                 "MONITOR_CONTRACT.md", "FINDINGS.json", "REPORT.md"):
        check(os.path.exists(os.path.join(HERE, name)), f"{name} exists")
    path = os.path.join(HERE, "MONITOR_EVALUATIONS.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            stored = json.load(fh)["evaluations"]
        drift = []
        for name, stored_ev in stored.items():
            _, fresh = evaluate_fixture(name)
            if fresh["counters"] != stored_ev["counters"] or \
                    fresh["serving"] != stored_ev["serving"]:
                drift.append(name)
        check(not drift, "stored evaluations reproduce from the fixtures", f"{drift}")


def test_report_carries_epistemic_status():
    print("\n[E2] the report carries the epistemic status verbatim")
    verbatim = ("PRODUCT SCAFFOLD built against fixtures. Carries no scientific claim and must "
                "not imply a model has been promoted.")
    path = os.path.join(HERE, "REPORT.md")
    if not os.path.exists(path):
        check(False, "REPORT.md exists")
        return
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    check(verbatim in text, "REPORT.md contains the epistemic-status line verbatim")
    check("no challenger" in text.lower() or "not been promoted" in text.lower()
          or "no model has been promoted" in text.lower(),
          "REPORT.md states that nothing here implies a promotion")


def main():
    print("U13_MONITORING_INTERFACE -- TESTS")
    print("PRODUCT SCAFFOLD built against fixtures. Carries no scientific claim and must not "
          "imply a model has been promoted.")
    names = test_fixtures_load()
    test_declared_expectations(names)
    test_stale_input_visible()
    test_missing_lineup_visible()
    test_undeclared_lineup_dependency_still_gates()
    test_failed_jobs_visible()
    test_rollback_visible()
    test_silent_failure_attempt()
    test_empty_and_garbage_inputs()
    test_ablation_sweep()
    test_null_sweep()
    test_stale_snapshot_is_a_failure()
    test_alert_cell_is_never_numeric()
    test_unbound_reality()
    test_model_agnostic()
    test_binding_required()
    test_outputs_present_and_current()
    test_report_carries_epistemic_status()

    print("\n" + "=" * 78)
    print(f"checks run: {CHECKS[0]}   failures: {len(FAILURES)}")
    for f in FAILURES:
        print(f"  FAILED: {f}")
    print("=" * 78)
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
