#!/usr/bin/env python
"""Standalone test suite for the D11 live-information capture. pytest is not installed.

EPISTEMIC STATUS: PROSPECTIVE CAPTURE INFRASTRUCTURE. Builds the record that would make future
features cutoff-provable. Creates no historical evidence and repairs no historical gap.

Run:    python TESTS.py
Exit:   0 when every test passes, 1 otherwise.

These are unit, synthetic, identity and schema tests only. Nothing is fitted, scored or compared
against any historical performance number.
"""

from __future__ import annotations

import json
import shutil
import sys
import traceback
from pathlib import Path

import capture_schema as cs
import capture_ledger as cl
import selftest_capture as st

LANE_DIR = Path(__file__).resolve().parent
TMP = LANE_DIR / "_tests_tmp"

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str):
    def deco(fn):
        def wrapped():
            try:
                fn()
                RESULTS.append((name, True, ""))
            except Exception:                                    # noqa: BLE001
                RESULTS.append((name, False, traceback.format_exc(limit=4)))
        wrapped.__name__ = fn.__name__
        return wrapped
    return deco


def assert_raises(code, fn, *a, **kw):
    try:
        fn(*a, **kw)
    except cs.CaptureError as exc:
        assert exc.code == code, f"expected {code}, got {exc.code}: {exc}"
        return exc
    raise AssertionError(f"expected {code}, nothing raised")


def fresh_ledger(name, registry=None, clock=None):
    root = TMP / name
    if root.exists():
        shutil.rmtree(root)
    reg = registry or st.REGISTRY
    return cl.CaptureLedger(root, reg, clock=clock or st.FakeClock())


# ---------------------------------------------------------------------------------------------
# schema
# ---------------------------------------------------------------------------------------------

@check("domains: exactly the eight contract criteria, one domain each")
def t_domains():
    assert len(cs.DOMAINS) == 8, len(cs.DOMAINS)
    crits = sorted(d["contract_criterion"] for d in cs.DOMAINS.values())
    assert crits == sorted(cs.CONTRACT_CRITERIA), crits
    assert len(set(crits)) == 8


@check("schema: required field missing is refused")
def t_required():
    assert_raises("SCHEMA_VIOLATION", cs.validate_payload, "injury_designation",
                  {"season": 2026, "team": "A", "player": "P"})


@check("schema: undeclared field is refused")
def t_undeclared():
    assert_raises("SCHEMA_VIOLATION", cs.validate_payload, "coaching_change",
                  {"season": 2026, "team": "A", "head_coach": "C", "change_type": "HIRE",
                   "whatever": 1})


@check("schema: value outside the declared enum is refused")
def t_enum():
    assert_raises("SCHEMA_VIOLATION", cs.validate_payload, "injury_designation",
                  {"season": 2026, "team": "A", "player": "P", "designation": "MAYBE"})


@check("schema: attributable news requires a non-empty attribution")
def t_attribution():
    ok = {"source_item_id": "x", "headline": "h", "attributed_to": "R", "claim_type": "REPORT"}
    cs.validate_payload("news", ok)
    assert_raises("SCHEMA_VIOLATION", cs.validate_payload, "news", dict(ok, attributed_to=""))
    bad = dict(ok)
    bad.pop("attributed_to")
    assert_raises("SCHEMA_VIOLATION", cs.validate_payload, "news", bad)


@check("blocklist: every realised-outcome key and prefix is refused in every domain")
def t_blocklist():
    base = {"season": 2026, "team": "A", "player": "P", "designation": "OUT"}
    for k in ["minutes", "game_minutes", "is_overtime", "possessions", "pace",
              "regulation_seconds_remaining", "non_competitive_conservative"]:
        assert_raises("PROHIBITED_PAYLOAD_KEY", cs.validate_payload, "injury_designation",
                      dict(base, **{k: 1}))
    for k in ["realised_minutes", "actual_starters", "score_diff_offense_start",
              "stint_id", "boxscore_row", "off_p1", "def_p3", "final_score_home"]:
        assert_raises("PROHIBITED_PAYLOAD_KEY", cs.validate_payload, "injury_designation",
                      dict(base, **{k: 1}))
    # case-insensitivity
    assert_raises("PROHIBITED_PAYLOAD_KEY", cs.validate_payload, "injury_designation",
                  dict(base, **{"Game_Minutes": 40}))


@check("digest: stable to key order, sensitive to content; entity_key needs its key fields")
def t_digest():
    a = {"season": 2026, "team": "A", "player": "P", "designation": "OUT"}
    b = {"designation": "OUT", "player": "P", "team": "A", "season": 2026}
    assert cs.payload_digest(a) == cs.payload_digest(b)
    assert cs.payload_digest(a) != cs.payload_digest(dict(a, designation="AVAILABLE"))
    assert cs.entity_key("injury_designation", a) == cs.entity_key("injury_designation", b)
    # a change to a NON-key field keeps the entity but changes the digest
    c = dict(a, reason="ankle")
    assert cs.entity_key("injury_designation", c) == cs.entity_key("injury_designation", a)
    assert cs.payload_digest(c) != cs.payload_digest(a)
    assert_raises("SCHEMA_VIOLATION", cs.entity_key, "injury_designation",
                  {"season": 2026, "team": "", "player": "P", "designation": "OUT"})


# ---------------------------------------------------------------------------------------------
# ledger semantics
# ---------------------------------------------------------------------------------------------

@check("ledger: first_seen -> change -> reaffirmation, with first_seen copied forward unchanged")
def t_change_semantics():
    clock = st.FakeClock()
    led = fresh_ledger("t_change", clock=clock)
    p = {"season": 2026, "team": "A", "player": "P", "designation": "QUESTIONABLE"}
    clock.value = st.ts(0)
    r0 = led.append("injury_designation", "SELFTEST_LIVE_FEED", p, st.ts(0))
    clock.value = st.ts(10)
    r1 = led.append("injury_designation", "SELFTEST_LIVE_FEED", dict(p, designation="OUT"),
                    st.ts(10))
    clock.value = st.ts(20)
    r2 = led.append("injury_designation", "SELFTEST_LIVE_FEED", dict(p, designation="OUT"),
                    st.ts(20))
    assert (r0["change_kind"], r0["change_index"]) == ("first_seen", 0)
    assert (r1["change_kind"], r1["change_index"]) == ("change", 1)
    assert (r2["change_kind"], r2["change_index"]) == ("reaffirmation", 1)
    assert r0["first_seen_at_utc"] == r1["first_seen_at_utc"] == r2["first_seen_at_utc"]
    assert r1["prev_payload_digest"] == r0["payload_digest"]
    assert r1["revision_of"] == r0["record_id"]
    hist = led.history(r0["entity_key"])
    assert len(hist) == 3
    assert [h["payload"]["designation"] for h in hist] == ["QUESTIONABLE", "OUT", "OUT"]
    assert led.verify()["ok"]


@check("ledger: append never rewrites -- the file only ever grows by a prefix-preserving write")
def t_append_only():
    clock = st.FakeClock()
    led = fresh_ledger("t_append", clock=clock)
    prev = b""
    for i in range(5):
        clock.value = st.ts(i)
        led.append("odds", "SELFTEST_LIVE_FEED",
                   {"game_key": "G", "book": "B", "market": "TOTAL", "line": 160.0 + i},
                   st.ts(i))
        now = led.path.read_bytes()
        assert now.startswith(prev) and len(now) > len(prev)
        prev = now
    assert len(led.read_records()) == 5


@check("no backdating: four distinct rejections, and none of them writes a byte")
def t_backdating():
    clock = st.FakeClock()
    led = fresh_ledger("t_backdate", clock=clock)
    clock.value = st.ts(50)
    led.append("odds", "SELFTEST_LIVE_FEED",
               {"game_key": "G", "book": "B", "market": "TOTAL", "line": 160.0}, st.ts(50))
    before = led.path.read_bytes()

    clock.value = st.ts(60)
    assert_raises("BACKDATED_OBSERVATION", led.append, "odds", "SELFTEST_LIVE_FEED",
                  {"game_key": "G", "book": "B", "market": "SPREAD", "line": -3.0}, st.ts(10))
    assert_raises("FUTURE_OBSERVATION", led.append, "odds", "SELFTEST_LIVE_FEED",
                  {"game_key": "G", "book": "B", "market": "SPREAD", "line": -3.0}, st.ts(999))
    assert_raises("PUBLISHED_AFTER_OBSERVED", led.append, "news", "SELFTEST_LIVE_FEED",
                  {"source_item_id": "n1", "headline": "h", "attributed_to": "R",
                   "claim_type": "REPORT"}, st.ts(55), published_at_utc=st.ts(58))
    assert_raises("RETROSPECTIVE_CLAIMS_EARLY_OBSERVATION", led.append, "transaction",
                  "SELFTEST_BULK_ARCHIVE",
                  {"transaction_key": "t1", "transaction_type": "SIGNING", "player": "P"},
                  st.ts(55), retrospective=True)
    assert led.path.read_bytes() == before, "a rejected append modified the ledger"


@check("no backdating: an entity may not be observed before its own first sighting, cross-source")
def t_backdate_cross_source():
    clock = st.FakeClock()
    reg = cl.SourceRegistry({
        "FEED_A": {"observation_provable": True},
        "FEED_B": {"observation_provable": True},
    })
    led = fresh_ledger("t_xsrc", registry=reg, clock=clock)
    p = {"season": 2026, "team": "A", "player": "P", "designation": "OUT"}
    clock.value = st.ts(30)
    led.append("injury_designation", "FEED_A", p, st.ts(30))
    clock.value = st.ts(40)
    # FEED_B has no watermark of its own, so only the entity guard can catch this
    assert_raises("BACKDATED_ENTITY_OBSERVATION", led.append, "injury_designation", "FEED_B",
                  dict(p, designation="AVAILABLE"), st.ts(20))


@check("retrospective records are CUTOFF_UNPROVEN and are never admitted at any cutoff")
def t_retrospective():
    clock = st.FakeClock()
    led = fresh_ledger("t_retro", clock=clock)
    clock.value = st.ts(0)
    r = led.append("transaction", "SELFTEST_BULK_ARCHIVE",
                   {"transaction_key": "t1", "transaction_type": "SIGNING", "player": "P"},
                   st.ts(0), retrospective=True, effective_at_utc="2021-05-14T00:00:00Z")
    assert r["cutoff_basis"] == cl.CUTOFF_UNPROVEN
    assert r["effective_at_utc"] == "2021-05-14T00:00:00Z"
    assert led.admissible_at("2099-01-01T00:00:00Z") == {}
    # a non-provable source is CUTOFF_UNPROVEN even without the retrospective flag
    clock.value = st.ts(1)
    r2 = led.append("transaction", "SELFTEST_BULK_ARCHIVE",
                    {"transaction_key": "t2", "transaction_type": "WAIVER", "player": "Q"},
                    st.ts(1))
    assert r2["cutoff_basis"] == cl.CUTOFF_UNPROVEN
    assert led.admissible_at("2099-01-01T00:00:00Z") == {}


@check("admission is strict: observed_at == cutoff does not admit; observed_at < cutoff does")
def t_strict_cutoff():
    clock = st.FakeClock()
    led = fresh_ledger("t_cutoff", clock=clock)
    clock.value = st.ts(10)
    led.append("odds", "SELFTEST_LIVE_FEED",
               {"game_key": "G", "book": "B", "market": "TOTAL", "line": 160.0}, st.ts(10))
    assert len(led.admissible_at(st.ts(10))) == 0
    assert len(led.admissible_at(st.ts(11))) == 1
    clock.value = st.ts(20)
    led.append("odds", "SELFTEST_LIVE_FEED",
               {"game_key": "G", "book": "B", "market": "TOTAL", "line": 165.0}, st.ts(20))
    adm = led.admissible_at(st.ts(15))
    assert [r["payload"]["line"] for r in adm.values()] == [160.0], "cutoff leaked a later line"
    adm2 = led.admissible_at(st.ts(25))
    assert [r["payload"]["line"] for r in adm2.values()] == [165.0]


@check("derived files are a pure function of the ledger: delete and replay reproduces them")
def t_replay():
    clock = st.FakeClock()
    led = fresh_ledger("t_replay", clock=clock)
    for i in range(4):
        clock.value = st.ts(i)
        led.append("odds", "SELFTEST_LIVE_FEED",
                   {"game_key": f"G{i%2}", "book": "B", "market": "TOTAL", "line": 160.0 + i},
                   st.ts(i))
    led.write_derived()
    a = (led.root / cl.STATE_FILE).read_text(encoding="utf-8")
    b = (led.root / cl.WATERMARK_FILE).read_text(encoding="utf-8")
    (led.root / cl.STATE_FILE).unlink()
    (led.root / cl.WATERMARK_FILE).unlink()
    led2 = cl.CaptureLedger(led.root, st.REGISTRY, clock=clock)
    led2.write_derived()
    assert (led.root / cl.STATE_FILE).read_text(encoding="utf-8") == a
    assert (led.root / cl.WATERMARK_FILE).read_text(encoding="utf-8") == b


# ---------------------------------------------------------------------------------------------
# tamper detection -- verify() must catch a hand-edited ledger
# ---------------------------------------------------------------------------------------------

def _tampered(name, mutate) -> dict:
    clock = st.FakeClock()
    led = fresh_ledger(name, clock=clock)
    p = {"season": 2026, "team": "A", "player": "P", "designation": "QUESTIONABLE"}
    clock.value = st.ts(0)
    led.append("injury_designation", "SELFTEST_LIVE_FEED", p, st.ts(0))
    clock.value = st.ts(10)
    led.append("injury_designation", "SELFTEST_LIVE_FEED", dict(p, designation="OUT"), st.ts(10))
    assert led.verify()["ok"], "baseline should be clean"
    lines = [json.loads(x) for x in
             led.path.read_text(encoding="utf-8").splitlines() if x.strip()]
    mutate(lines)
    led.path.write_text(
        "".join(cs.canonical_json(x) + "\n" for x in lines), encoding="utf-8")
    return cl.CaptureLedger(led.root, st.REGISTRY, clock=clock).verify()


@check("derived files carry no wall-clock field: regenerating twice is byte-identical")
def t_derived_idempotent():
    clock = st.FakeClock()
    led = fresh_ledger("t_idem", clock=clock)
    clock.value = st.ts(0)
    led.append("odds", "SELFTEST_LIVE_FEED",
               {"game_key": "G", "book": "B", "market": "TOTAL", "line": 160.0}, st.ts(0))
    led.write_derived()
    snap = {f: (led.root / f).read_bytes()
            for f in (cl.STATE_FILE, cl.WATERMARK_FILE, cl.MANIFEST_FILE)}
    clock.value = st.ts(999)                       # a different wall clock must not matter
    led.write_derived()
    for f, b in snap.items():
        assert (led.root / f).read_bytes() == b, f"{f} changed with no ledger change"


@check("verify: catches an overwritten first_seen_at_utc")
def t_tamper_first_seen():
    rep = _tampered("t_tamper_fs", lambda ls: ls[1].__setitem__(
        "first_seen_at_utc", "2026-08-04T12:10:00Z"))
    codes = {v["code"] for v in rep["violations"]}
    assert not rep["ok"]
    assert "FIRST_SEEN_MUTATED" in codes, codes


@check("verify: catches a payload edited in place")
def t_tamper_payload():
    def mut(ls):
        ls[1]["payload"]["designation"] = "AVAILABLE"
    rep = _tampered("t_tamper_pl", mut)
    codes = {v["code"] for v in rep["violations"]}
    assert not rep["ok"]
    assert "PAYLOAD_DIGEST_MISMATCH" in codes, codes
    assert "RECORD_ID_MISMATCH" in codes, codes


@check("verify: catches a deleted intermediate record (the chain breaks)")
def t_tamper_delete():
    clock = st.FakeClock()
    led = fresh_ledger("t_tamper_del", clock=clock)
    p = {"season": 2026, "team": "A", "player": "P", "designation": "QUESTIONABLE"}
    for i, d in enumerate(["QUESTIONABLE", "DOUBTFUL", "OUT"]):
        clock.value = st.ts(i * 10)
        led.append("injury_designation", "SELFTEST_LIVE_FEED", dict(p, designation=d),
                   st.ts(i * 10))
    assert led.verify()["ok"]
    lines = led.path.read_text(encoding="utf-8").splitlines()
    led.path.write_text(lines[0] + "\n" + lines[2] + "\n", encoding="utf-8")
    rep = cl.CaptureLedger(led.root, st.REGISTRY, clock=clock).verify()
    codes = {v["code"] for v in rep["violations"]}
    assert not rep["ok"]
    assert "CHAIN_BROKEN" in codes and "INGEST_SEQ_NOT_CONTIGUOUS" in codes, codes


@check("verify: catches a record whose observed_at was pushed backwards")
def t_tamper_backdate():
    rep = _tampered("t_tamper_bd", lambda ls: ls[1].__setitem__(
        "observed_at_utc", "2026-08-04T11:00:00Z"))
    codes = {v["code"] for v in rep["violations"]}
    assert not rep["ok"]
    assert "BACKDATED_OBSERVATION" in codes, codes
    assert "BACKDATED_ENTITY_OBSERVATION" in codes, codes


# ---------------------------------------------------------------------------------------------
# write scope
# ---------------------------------------------------------------------------------------------

@check("scope: a ledger rooted outside the lane directory is refused")
def t_scope():
    assert_raises("SCOPE_VIOLATION", cl.CaptureLedger, LANE_DIR.parent / "NOT_MY_LANE",
                  st.REGISTRY)
    assert_raises("SCOPE_VIOLATION", cl.CaptureLedger, LANE_DIR.parent.parent, st.REGISTRY)
    assert_raises("SCOPE_VIOLATION", cl.assert_in_scope, LANE_DIR / ".." / "escape.json")
    cl.assert_in_scope(LANE_DIR / "ok.json")


@check("scope: every file this node wrote is inside the lane directory")
def t_outputs_in_scope():
    for p in LANE_DIR.rglob("*"):
        cl.assert_in_scope(p)


# ---------------------------------------------------------------------------------------------
# end-to-end and artifacts
# ---------------------------------------------------------------------------------------------

@check("self-test corpus: all ten end-to-end checks pass and the receipt is reproducible")
def t_selftest():
    r1 = st.run(fresh=True)
    assert r1["all_checks_pass"], [k for k, v in r1["checks"].items() if not v]
    assert r1["counts"]["domains_exercised"] == 8
    r2 = st.run(fresh=True)
    assert r2["ledger_sha256"] == r1["ledger_sha256"], "self-test corpus is not deterministic"
    assert r2["counts"] == r1["counts"]


@check("production ledger exists, is empty, and no source is bound")
def t_production_empty():
    st.init_production_ledger()
    led = cl.CaptureLedger(st.PROD_DIR, cl.SourceRegistry({}))
    assert led.read_records() == []
    binding = json.loads((LANE_DIR / "SOURCE_BINDING.json").read_text(encoding="utf-8"))
    assert binding["n_domains"] == 8
    assert binding["n_bound"] == 0
    assert set(binding["domains"]) == set(cs.DOMAINS)
    assert all(not d["bound"] for d in binding["domains"].values())


@check("SOURCE_BINDING cites artifacts whose sha256 still matches the bytes on disk")
def t_binding_hashes():
    import hashlib
    binding = json.loads((LANE_DIR / "SOURCE_BINDING.json").read_text(encoding="utf-8"))
    repo_root = LANE_DIR.parent.parent.parent.parent
    n = 0
    for name, meta in binding["cited_artifacts"].items():
        p = repo_root / meta["path"]
        assert p.exists(), f"{name}: {p} missing"
        got = hashlib.sha256(p.read_bytes()).hexdigest()
        assert got == meta["sha256"], f"{name}: {got} != {meta['sha256']}"
        n += 1
    assert n == 5, n


TESTS = [v for k, v in sorted(globals().items()) if k.startswith("t_") and callable(v)]


def main() -> int:
    TMP.mkdir(parents=True, exist_ok=True)
    try:
        for t in TESTS:
            t()
    finally:
        if TMP.exists():
            shutil.rmtree(TMP, ignore_errors=True)
    n_pass = sum(1 for _, ok, _ in RESULTS if ok)
    for name, ok, tb in RESULTS:
        print(f"{'PASS' if ok else 'FAIL'}  {name}")
        if not ok:
            print(tb)
    print(f"\n{n_pass}/{len(RESULTS)} tests passed")
    return 0 if n_pass == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
