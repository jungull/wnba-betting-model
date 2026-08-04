"""U12_PREDICTION_HISTORY -- tests.

EPISTEMIC STATUS: PRODUCT SCAFFOLD built against fixtures. Carries no scientific claim and must
not imply a model has been promoted.

Repo convention (pytest is NOT installed): standalone runnable script whose main() returns 1 on
failure. Run:

    python experiments/player_program/product_lane/U12_PREDICTION_HISTORY/TESTS.py

Every tamper test operates on a THROWAWAY ledger in the system temp directory. Nothing here
writes outside this node's own directory except that temp directory, and nothing here runs git,
reads a sealed result, or executes an estimator.
"""

from __future__ import annotations

import json
import pathlib
import re
import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import prediction_history as ph  # noqa: E402
from build_fixture_history import (  # noqa: E402
    MODEL_A, MODEL_B, T0, fresh_inputs, key,
)

FAILURES: list[str] = []
SKIPS: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name}  {detail}")
        FAILURES.append(f"{name}: {detail}")


def skip(name: str, why: str) -> None:
    print(f"  SKIP  {name}  ({why})")
    SKIPS.append(f"{name}: {why}")


def raises(name: str, fn, *a, expect: str = "", **k) -> None:
    """Assert the call is refused, and (when `expect` is given) refused for the RIGHT reason --
    a test that passes on an incidental error is worse than no test."""
    try:
        fn(*a, **k)
    except ph.HistoryError as e:
        if expect and expect.lower() not in str(e).lower():
            check(name, False, f"refused, but for the wrong reason: {e}")
            return
        print(f"  PASS  {name}  (refused: {str(e)[:70]})")
        return
    check(name, False, "no HistoryError raised")


CUTOFF = datetime(2026, 8, 2, 23, 0, 0, tzinfo=timezone.utc)


def _k(player: str = "T_PLAYER_1", game: str = "T_GAME_1") -> dict:
    return key(game, "T_TEAM_1", player, "fixture_target_units", CUTOFF)


def _seed(tmp: pathlib.Path, n: int = 3) -> tuple[pathlib.Path, list[dict]]:
    """A small ledger: one key with n revisions."""
    led = tmp / ph.LEDGER_NAME
    recs = []
    prev_id = None
    for i in range(n):
        at = T0 + timedelta(hours=i)
        recs.append(ph.append_prediction(led, ph.make_record(
            _k(), MODEL_A, fresh_inputs(at), 20.0 + i, units="units", appended_at=at,
            revision_index=i, revises_record_id=prev_id,
            revision_reason=None if i == 0 else f"revision {i}")))
        prev_id = recs[-1]["record_id"]
    return led, recs


def _rewrite(led: pathlib.Path, records: list[dict]) -> None:
    """Out-of-band rewrite -- what an ATTACKER does. The module offers no such function."""
    led.write_text("".join(
        json.dumps(r, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
        for r in records), encoding="utf-8")


def codes(report: dict) -> set[str]:
    return {f["code"] for f in report["findings"]}


# --------------------------------------------------------------------------- #
def t_append_only_by_construction() -> None:
    print("\n[1] the module offers no way to edit or delete a record")
    src = (HERE / "prediction_history.py").read_text(encoding="utf-8")

    writes = re.findall(r"\.open\(\s*([\"'])([arw+bt]+)\1", src)
    modes = sorted({m for _, m in writes})
    check("the ledger is only ever opened 'a' (append) or 'r' (read)",
          set(modes) <= {"a", "r", "rb"}, f"open modes found: {modes}")

    public = [n for n in dir(ph) if not n.startswith("_")]
    forbidden = [n for n in public
                 if re.search(r"(update|delete|edit|overwrite|rewrite|patch|drop)", n, re.I)]
    check("no update/delete/edit/rewrite function is exported", forbidden == [], str(forbidden))

    write_fns = [n for n in public if callable(getattr(ph, n))
                 and re.search(r"(append|write)", n, re.I)]
    check("exactly one write primitive is exported (append_prediction)",
          write_fns == ["append_prediction"], str(write_fns))


def t_earlier_bytes_never_change() -> None:
    print("\n[2] appending never disturbs a byte of what is already written")
    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)
        led, recs = _seed(tmp, 2)
        before = led.read_bytes()
        at = T0 + timedelta(hours=5)
        ph.append_prediction(led, ph.make_record(
            _k("T_PLAYER_2"), MODEL_B, fresh_inputs(at), 12.0, units="units", appended_at=at))
        after = led.read_bytes()
        check("the file grew", len(after) > len(before))
        check("every previously written byte is identical",
              after[:len(before)] == before)
        check("the earlier records still verify", ph.verify_ledger(led)["ok"])


def t_tamper_detection() -> None:
    print("\n[3] an edit, a deletion, a reorder, a truncation and a forged id are all detected")
    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)
        led, recs = _seed(tmp, 3)
        check("the untampered ledger verifies", ph.verify_ledger(led)["ok"],
              str(ph.verify_ledger(led)["findings"]))

        # (a) edit a value in an already-written record
        m = [dict(r) for r in recs]
        m[0] = dict(m[0]); m[0]["projection"] = dict(m[0]["projection"]); \
            m[0]["projection"]["point"] = 999.0
        _rewrite(led, m)
        c = codes(ph.verify_ledger(led))
        check("(a) an edited value is caught", "RECORD_DIGEST_MISMATCH" in c, str(sorted(c)))
        check("(a) the edit also breaks the id derivation", "RECORD_ID_NOT_DERIVABLE" in c,
              str(sorted(c)))

        # (b) delete the middle record
        _rewrite(led, [recs[0], recs[2]])
        c = codes(ph.verify_ledger(led))
        check("(b) a deleted record is caught", "CHAIN_BROKEN" in c, str(sorted(c)))
        check("(b) the head sidecar also disagrees", "HEAD_COUNT_MISMATCH" in c, str(sorted(c)))

        # (c) reorder
        _rewrite(led, [recs[1], recs[0], recs[2]])
        check("(c) a reordered ledger is caught", "CHAIN_BROKEN" in codes(ph.verify_ledger(led)))

        # (d) truncate the tail -- only the sidecar can see this
        _rewrite(led, recs[:2])
        c = codes(ph.verify_ledger(led))
        check("(d) a truncated tail is caught by the head sidecar",
              {"HEAD_COUNT_MISMATCH", "HEAD_DIGEST_MISMATCH"} & c != set(), str(sorted(c)))
        check("(d) the chain ALONE cannot see a truncation (stated limit, not a bug)",
              "CHAIN_BROKEN" not in c, str(sorted(c)))

        # (e) forge a record_id, keeping the chain digest consistent with the forged body
        f = [dict(r) for r in recs]
        f[2] = dict(f[2]); f[2]["record_id"] = "0" * 32
        body = {k: v for k, v in f[2].items()
                if k not in ("prev_record_sha256", "record_sha256")}
        f[2]["record_sha256"] = ph.chain_digest(f[2]["prev_record_sha256"], body)
        _rewrite(led, f)
        c = codes(ph.verify_ledger(led))
        check("(e) a forged record_id is caught", "RECORD_ID_NOT_DERIVABLE" in c, str(sorted(c)))

        # (f) duplicate a record line out of band
        _rewrite(led, [recs[0], recs[1], recs[1], recs[2]])
        c = codes(ph.verify_ledger(led))
        check("(f) a duplicated record is caught", "DUPLICATE_RECORD_ID" in c, str(sorted(c)))

        # (g) a tampered ledger may not be extended
        at = T0 + timedelta(hours=9)
        raises("(g) append refuses to extend a ledger that does not verify",
               ph.append_prediction, led,
               ph.make_record(_k("T_PLAYER_9"), MODEL_A, fresh_inputs(at), 5.0,
                              units="units", appended_at=at))


def t_model_binding_required() -> None:
    print("\n[4] a record cannot exist without a model version and artifact hashes")
    with tempfile.TemporaryDirectory() as td:
        led = pathlib.Path(td) / ph.LEDGER_NAME
        good = ph.make_record(_k(), MODEL_A, fresh_inputs(T0), 10.0, units="u", appended_at=T0)
        check("the well-formed record appends", ph.append_prediction(led, good)["record_id"] != "")

        for label, model, why in (
            ("no model_version",
             {k: v for k, v in MODEL_A.items() if k != "model_version"}, "model_version"),
            ("blank model_version", {**MODEL_A, "model_version": "   "}, "model_version"),
            ("no artifact_sha256",
             {k: v for k, v in MODEL_A.items() if k != "artifact_sha256"}, "artifact_sha256"),
            ("empty artifact map", {**MODEL_A, "artifact_sha256": {}}, "artifact_sha256"),
            ("artifact hash not sha256",
             {**MODEL_A, "artifact_sha256": {"w": "deadbeef"}}, "hex"),
            ("uppercase hex", {**MODEL_A, "artifact_sha256": {"w": "A" * 64}}, "hex"),
            ("no promotion_status",
             {k: v for k, v in MODEL_A.items() if k != "promotion_status"}, "promotion_status"),
        ):
            raises(f"refuses a record with {label}", ph.make_record,
                   _k("T_PLAYER_X"), model, fresh_inputs(T0), 10.0, units="u", appended_at=T0,
                   expect=why)

    print("      (a model_version and its artifact hashes are DATA the caller supplies;")
    print("       the store never infers which model produced a number)")


def t_revision_is_a_new_record() -> None:
    print("\n[5] a revised prediction is a new record, never an edit")
    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)
        led, recs = _seed(tmp, 3)
        all_recs = ph.read_records(led)

        check("three records exist for one prediction key",
              len({r["key_uid"] for r in all_recs}) == 1 and len(all_recs) == 3)
        check("their record_ids are all distinct",
              len({r["record_id"] for r in all_recs}) == 3)
        check("the earlier values are still readable",
              [r["projection"]["point"] for r in all_recs] == [20.0, 21.0, 22.0],
              str([r["projection"]["point"] for r in all_recs]))

        cur = ph.view_current(all_recs)
        check("view_current returns exactly one record per key", len(cur) == 1)
        only = next(iter(cur.values()))
        check("the current record is the highest revision", only["revision_index"] == 2)
        check("the superseded records are retained, not removed",
              len(ph.view_superseded(all_recs)) == 2)
        check("each revision names the record it superseded",
              [r["revises_record_id"] for r in all_recs]
              == [None, all_recs[0]["record_id"], all_recs[1]["record_id"]])

        at = T0 + timedelta(hours=7)
        # wrong revision index
        raises("refuses a revision that reuses an existing revision_index",
               ph.append_prediction, led,
               ph.make_record(_k(), MODEL_A, fresh_inputs(at), 30.0, units="u", appended_at=at,
                              revision_index=1, revises_record_id=all_recs[0]["record_id"]))
        # forking a non-head record
        raises("refuses a revision that forks a superseded record",
               ph.append_prediction, led,
               ph.make_record(_k(), MODEL_A, fresh_inputs(at), 30.0, units="u", appended_at=at,
                              revision_index=3, revises_record_id=all_recs[0]["record_id"]))
        # a second revision-0 for a key that already has history
        raises("refuses a second revision 0 for an existing key",
               ph.append_prediction, led,
               ph.make_record(_k(), MODEL_A, fresh_inputs(at), 30.0, units="u", appended_at=at))
        # a first record that claims to revise something
        raises("refuses a first record that claims to revise something",
               ph.append_prediction, led,
               ph.make_record(_k("T_PLAYER_NEW"), MODEL_A, fresh_inputs(at), 30.0, units="u",
                              appended_at=at, revision_index=1,
                              revises_record_id=all_recs[0]["record_id"]))

        check("after the four refusals the ledger is unchanged (3 records)",
              len(ph.read_records(led)) == 3)
        check("and it still verifies", ph.verify_ledger(led)["ok"])

        good = ph.append_prediction(led, ph.make_record(
            _k(), MODEL_B, fresh_inputs(at), 30.0, units="u", appended_at=at,
            revision_index=3, revises_record_id=all_recs[2]["record_id"],
            revision_reason="legitimate correction"))
        check("a legitimate next revision is accepted", good["revision_index"] == 3)
        check("the model version may change between revisions and is recorded per record",
              good["model"]["model_version"] != all_recs[2]["model"]["model_version"])
        check("the superseded record's bytes are untouched by the revision",
              ph.read_records(led)[2] == all_recs[2])


def t_absence_never_renders_as_a_number() -> None:
    print("\n[6] absence, staleness and failure render as warnings, never as numbers")
    at = T0
    cases = {
        "missing lineup": fresh_inputs(at, lineup=False),
        "stale feed": fresh_inputs(at, feed_age_s=7200),
    }
    bad_ts = fresh_inputs(at)
    bad_ts[1] = {**bad_ts[1], "observed_at": "not-a-timestamp"}
    cases["unparseable input timestamp"] = bad_ts
    future = fresh_inputs(at)
    future[1] = {**future[1],
                 "observed_at": (at + timedelta(hours=3)).isoformat().replace("+00:00", "Z")}
    cases["input timestamp in the future"] = future

    for label, inputs in cases.items():
        r = ph.make_record(_k(), MODEL_A, inputs, 42.0, interval=[40.0, 44.0], units="u",
                           appended_at=at)
        rend = ph.render_record(r)
        check(f"{label}: status is WITHHELD", r["status"] == ph.STATUS_WITHHELD, r["status"])
        check(f"{label}: the caller's number is discarded",
              r["projection"]["point"] is None and r["projection"]["interval"] is None,
              str(r["projection"]))
        check(f"{label}: it renders non-numerically", rend["is_numeric"] is False)
        check(f"{label}: the rendered text names a cause", bool(rend["blocking_codes"]))
        check(f"{label}: '42' does not appear in the rendered text",
              "42" not in rend["display"], rend["display"])

    # a caller supplying no number at all, and declaring no cause, still cannot be silent
    r = ph.make_record(_k(), MODEL_A, fresh_inputs(at), None, appended_at=at)
    check("a null projection with no declared cause becomes MODEL_OUTPUT_MISSING",
          any(w["code"] == "MODEL_OUTPUT_MISSING" for w in r["warnings"]), str(r["warnings"]))

    # a declared upstream failure
    r = ph.make_record(_k(), MODEL_A, fresh_inputs(at), None, appended_at=at,
                       extra_warnings=[{"code": "UPSTREAM_JOB_FAILED",
                                        "severity": ph.SEVERITY_BLOCKING, "detail": "exit 1"}])
    check("a declared job failure is WITHHELD and renders its cause",
          r["status"] == ph.STATUS_WITHHELD
          and "UPSTREAM_JOB_FAILED" in ph.render_record(r)["display"])

    # hand-built records that try to smuggle a number past a blocking warning
    base = ph.make_record(_k(), MODEL_A, fresh_inputs(at, lineup=False), 42.0, units="u",
                          appended_at=at)
    forced = dict(base)
    forced["status"] = ph.STATUS_OK
    forced["projection"] = {"point": 42.0, "interval": None, "units": "u"}
    raises("a hand-built OK record carrying a blocking warning is rejected",
           ph.validate_record, forced, positioned=False, expect="may not be status OK")
    smuggled = dict(base)
    smuggled["projection"] = {"point": 42.0, "interval": None, "units": "u"}
    raises("a hand-built WITHHELD record carrying a number is rejected",
           ph.validate_record, smuggled, positioned=False,
           expect="may not carry any numeric projection")
    smuggled2 = dict(base)
    smuggled2["projection"] = {"point": None, "interval": [40.0, 44.0], "units": "u"}
    raises("a WITHHELD record carrying only an INTERVAL is also rejected",
           ph.validate_record, smuggled2, positioned=False,
           expect="may not carry any numeric projection")

    # an advisory warning does NOT suppress a number
    r = ph.make_record(_k(), MODEL_A, fresh_inputs(at), 42.0, units="u", appended_at=at,
                       extra_warnings=[{"code": "WIDE_INTERVAL",
                                        "severity": ph.SEVERITY_ADVISORY, "detail": "wide"}])
    check("an advisory warning still allows a number, and is shown alongside it",
          r["status"] == ph.STATUS_OK and ph.render_record(r)["is_numeric"] is True
          and "WIDE_INTERVAL" in ph.render_record(r)["display"])

    # a non-required input that is absent is advisory, not blocking
    opt = fresh_inputs(at)
    opt.append({"input_id": "optional_context", "artifact_sha256": None, "observed_at": None,
                "required": False})
    r = ph.make_record(_k(), MODEL_A, opt, 42.0, units="u", appended_at=at)
    check("an absent OPTIONAL input is advisory and does not withhold",
          r["status"] == ph.STATUS_OK
          and any(w["code"] == ph.W_INPUT_MISSING for w in r["warnings"]))


def t_model_agnostic() -> None:
    print("\n[7] nothing here names a model, an arm or a challenger")
    reg = HERE.parents[1] / "arm_registry.jsonl"
    if not reg.exists():
        skip("arm-registry token scan", f"{reg} absent")
    else:
        tokens: set[str] = set()
        for line in reg.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            d = json.loads(line)
            for k in ("experiment_id", "arm_id", "applies_to"):
                v = d.get(k)
                if isinstance(v, str) and len(v) > 4:
                    tokens.add(v)
            fc = (d.get("extra") or {}).get("frozen_config") or {}
            if isinstance(fc.get("arm_id"), str):
                tokens.add(fc["arm_id"])
        blob = "\n".join((HERE / f).read_text(encoding="utf-8")
                         for f in ("prediction_history.py", "build_fixture_history.py"))
        hits = sorted(t for t in tokens if t in blob)
        check(f"none of the {len(tokens)} registered arm/experiment ids appears in the code",
              hits == [], str(hits))

    blob = "\n".join(
        (HERE / f).read_text(encoding="utf-8")
        for f in ("prediction_history.py", "build_fixture_history.py"))
    for tok in ("D_ewma_shrunk", "ewma_shrunk", "K0_MATCHED", "K0_FLAT", "cbs_v1", "arm_d",
                "Arm D"):
        check(f"the code does not mention {tok!r}", tok not in blob)

    led = HERE / "fixtures" / ph.LEDGER_NAME
    if not led.exists():
        skip("fixture promotion-status scan", "fixture ledger absent")
        return
    recs = ph.read_records(led)
    check("every fixture record declares a promotion status, and none of them is 'promoted'",
          all(r["model"]["promotion_status"] == "not_promoted" for r in recs),
          str(sorted({r["model"]["promotion_status"] for r in recs})))
    check("every fixture model_version is explicitly a fixture",
          all(r["model"]["model_version"].startswith("fixture_model/") for r in recs),
          str(sorted({r["model"]["model_version"] for r in recs})))


def t_committed_fixture() -> None:
    print("\n[8] the committed fixture ledger verifies and matches its own summary")
    led = HERE / "fixtures" / ph.LEDGER_NAME
    summ = HERE / "fixtures" / "FIXTURE_SUMMARY.json"
    if not led.exists() or not summ.exists():
        skip("committed fixture checks", "fixture ledger or summary absent "
                                         "(run build_fixture_history.py)")
        return
    s = json.loads(summ.read_text(encoding="utf-8"))
    rep = ph.verify_ledger(led)
    check("the fixture ledger verifies", rep["ok"], str(rep["findings"]))
    check("its record count matches the summary", rep["n_records"] == s["n_records"],
          f"{rep['n_records']} vs {s['n_records']}")
    check("its bytes match the digest recorded in the summary",
          ph.sha256_hex(led.read_bytes()) == s["ledger_sha256"])
    recs = ph.read_records(led)
    check("it contains at least one WITHHELD record",
          sum(1 for r in recs if r["status"] == ph.STATUS_WITHHELD) >= 1)
    check("it contains at least one multi-revision key",
          any(r["revision_index"] > 0 for r in recs))
    check("it contains more than one model version",
          len({r["model"]["model_version"] for r in recs}) > 1)
    check("no WITHHELD record renders any number",
          all(ph.render_record(r)["is_numeric"] is False
              for r in recs if r["status"] == ph.STATUS_WITHHELD))


def t_key_identity() -> None:
    print("\n[9] the prediction key is re-derivable and may not be partial")
    k = _k()
    check("key_uid is a function of the key alone", ph.key_uid(k) == ph.key_uid(dict(k)))
    check("a different cutoff is a different key",
          ph.key_uid({**k, "forecast_cutoff": "2026-08-03T00:00:00Z"}) != ph.key_uid(k))
    raises("refuses a key missing a field", ph.key_uid,
           {kk: vv for kk, vv in k.items() if kk != "team_id"})
    raises("refuses a key with an empty field", ph.key_uid, {**k, "player_id": ""})
    raises("refuses a key with an unknown field", ph.key_uid, {**k, "note": "x"})


API_RESPONSE = {
    "schema_version": "1.0.0",
    "response_id": "FIXTURE-RESP-1",
    "game": {"game_id": "FIXG0001", "forecast_cutoff_utc": "2026-08-02T23:00:00Z"},
    "model": {"model_version": "fixture_model/api", "model_family": "FIXTURE",
              "promotion_status": "not_promoted",
              "artifact_sha256": {"estimator_weights": "a" * 64}},
    "inputs": [
        {"input_id": "player_history", "sha256": "b" * 64,
         "observed_at_utc": "2026-08-01T17:00:00Z", "max_age_seconds": 86400},
    ],
    "warnings": [],
}


def t_api_adapter() -> None:
    print("\n[10] an API-shaped response converts to history records, fail-closed")
    at = T0
    served = {"projection_id": "p1", "subject_id": "FIXPLAYER_01", "team_id": "FIXTEAM_A",
              "target": "fixture_target_units", "unit": "units", "status": "ok",
              "withheld_reasons": [], "point": 30.0,
              "uncertainty": {"interval": [25.0, 35.0]}}
    r = ph.record_from_api_response(API_RESPONSE, served, appended_at=at)
    check("a served projection becomes an OK record", r["status"] == ph.STATUS_OK)
    check("its model block is carried through verbatim",
          r["model"] == API_RESPONSE["model"])
    check("the interval survives the conversion",
          r["projection"]["interval"] == [25.0, 35.0], str(r["projection"]))
    check("the API's own ids are kept as context, not as identity",
          r["context"]["response_id"] == "FIXTURE-RESP-1")

    withheld = {**served, "status": "withheld", "withheld_reasons": ["MISSING_LINEUP"],
                "point": 30.0}
    r = ph.record_from_api_response(API_RESPONSE, withheld, appended_at=at)
    check("a withheld projection carrying a number still records no number",
          r["status"] == ph.STATUS_WITHHELD and r["projection"]["point"] is None)
    check("its reason is preserved as a blocking warning",
          "MISSING_LINEUP" in ph.render_record(r)["blocking_codes"])

    silent = {**served, "status": "withheld", "withheld_reasons": [], "point": 30.0}
    r = ph.record_from_api_response(API_RESPONSE, silent, appended_at=at)
    check("a withheld projection that gives NO reason is still refused a number",
          r["status"] == ph.STATUS_WITHHELD
          and "PROJECTION_NOT_SERVED" in ph.render_record(r)["blocking_codes"])

    raises("a response with no model block is refused",
           ph.record_from_api_response, {k: v for k, v in API_RESPONSE.items() if k != "model"},
           served, appended_at=at, expect="response.model is required")

    # Optional interop probe against the concurrently-built U10 node. It is a PROBE: if that node
    # is absent or its shape has moved, this SKIPS with the reason. This node does not depend on
    # it and does not import from it.
    resp_dir = HERE.parent / "U10_PREDICTION_API_SCHEMA" / "fixtures" / "responses"
    if not resp_dir.is_dir():
        skip("U10 interop probe", "U10_PREDICTION_API_SCHEMA fixtures absent")
        return
    files = sorted(resp_dir.glob("*.json"))
    converted = withheld_n = numeric_n = 0
    try:
        for f in files:
            resp = json.loads(f.read_text(encoding="utf-8"))
            # Record-time must come from the RESPONSE, not from this test's clock: judging a
            # foreign fixture's freshness against an unrelated timestamp would manufacture a
            # staleness finding that says nothing about that fixture.
            at = ph.parse_ts(resp.get("generated_at_utc")) or T0
            for proj in resp.get("projections") or []:
                rec = ph.record_from_api_response(resp, proj, appended_at=at)
                converted += 1
                rend = ph.render_record(rec)
                if rec["status"] == ph.STATUS_WITHHELD:
                    withheld_n += 1
                    if rend["is_numeric"]:
                        check("a U10 withheld projection rendered a number", False, f.name)
                else:
                    numeric_n += 1
    except Exception as e:                                              # noqa: BLE001
        skip("U10 interop probe",
             f"converted {converted} projection(s) from {len(files)} response file(s), then: "
             f"{type(e).__name__}: {e}")
        return
    check(f"every projection in {len(files)} U10 fixture response(s) converts "
          f"({converted} projections: {numeric_n} numeric, {withheld_n} withheld)",
          converted > 0, "no projections found")


def main() -> int:
    print("U12_PREDICTION_HISTORY -- TESTS")
    print("PRODUCT SCAFFOLD built against fixtures. Carries no scientific claim and must not "
          "imply a model has been promoted.")
    print("=" * 78)
    t_append_only_by_construction()
    t_earlier_bytes_never_change()
    t_tamper_detection()
    t_model_binding_required()
    t_revision_is_a_new_record()
    t_absence_never_renders_as_a_number()
    t_model_agnostic()
    t_committed_fixture()
    t_key_identity()
    t_api_adapter()
    print("\n" + "=" * 78)
    if SKIPS:
        print(f"{len(SKIPS)} skipped:")
        for s in SKIPS:
            print(f"  - {s}")
    if FAILURES:
        print(f"FAILED ({len(FAILURES)}):")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("all assertions passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
