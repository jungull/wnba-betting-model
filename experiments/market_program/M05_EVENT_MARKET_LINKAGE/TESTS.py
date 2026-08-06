"""M05_EVENT_MARKET_LINKAGE -- validation suite.

Run:  python experiments/market_program/M05_EVENT_MARKET_LINKAGE/TESTS.py

Synthetic-fixture tests validate the linkage against assignments known by
construction (fixtures.py; all timestamps synthetic, no real capture stamp
can leak into a timing assertion).  The final test is a real-tape smoke
probe, read-only against the live worktree; it SKIPs cleanly when that
worktree is absent so the suite is location-independent.

Exit code 0 iff every non-skipped test passes.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import linkage as L
import fixtures as F

RESULTS = []


def check(name, fn):
    try:
        fn()
        RESULTS.append((name, "PASS", ""))
    except AssertionError as e:
        RESULTS.append((name, "FAIL", str(e)))
    except Exception as e:  # noqa: BLE001 -- a crash is a failure, reported
        RESULTS.append((name, "FAIL", f"{type(e).__name__}: {e}"))


def skip(name, why):
    RESULTS.append((name, "SKIP", why))


AM4_FIELDS = ["t_lower", "t_upper", "poll_interval_event",
              "poll_interval_quote", "vendor_latency_bound",
              "clock_skew_bound", "censor_type", "tier",
              "n_trusted", "n_excluded", "exclusion_reasons"]


def assert_am4(claim, where):
    for f in AM4_FIELDS:
        assert f in claim, f"{where}: amendment-4 field {f!r} missing"
    assert claim["censor_type"] in ("interval", "right"), \
        f"{where}: censor_type must be interval|right, never exact"


# ---------------------------------------------------------------------------
# T01 clean case: deterministic first-seen keying, exact interval arithmetic
# ---------------------------------------------------------------------------
def t01():
    fx = F.fx_clean()
    res = F.run(fx)
    assert res["n_records"] == 1, res["n_records"]
    r = res["records"][0]
    assert r["status"] == "TRUSTED", r["primary_reason"]
    tr = fx["truth"]
    assert r["event_interval"] == tr["event_interval"], r["event_interval"]
    pre, post = r["windows"]["PRE"], r["windows"]["POST_FIRST"]
    assert pre["status"] == "OK" and [pre["q_lo"], pre["q_up"]] == tr["pre"]
    assert post["status"] == "OK" and [post["q_lo"], post["q_up"]] == tr["post"]
    c = r["claim"]
    assert_am4(c, "T01")
    assert c["t_lower"] == tr["t_lower"], c["t_lower"]
    assert c["t_upper"] == tr["t_upper"], c["t_upper"]
    assert c["measurement_grid_s"] == tr["grid"], c["measurement_grid_s"]
    assert c["verdict"] == "BOUNDED"
    assert c["poll_interval_event"] == 300 and c["poll_interval_quote"] == 300
    # sub-hour horizons on a 5-min grid: H+5.. resolve, H+1/H+2 exceed width
    assert r["windows"]["H+5"]["status"] == "OK"
    assert r["windows"]["H+1"]["status"] == L.REASON_POLL_GAP


# ---------------------------------------------------------------------------
# T02 determinism: same inputs -> same bytes; input order irrelevant
# ---------------------------------------------------------------------------
def t02():
    fx = F.fx_clean()
    r1, r2 = F.run(fx), F.run(fx)
    assert r1["result_hash"] == r2["result_hash"]
    fx2 = F.fx_clean()
    fx2["events"] = list(reversed(fx2["events"]))
    fx2["series"] = dict(reversed(list(fx2["series"].items())))
    r3 = F.run(fx2)
    assert r3["result_hash"] == r1["result_hash"], "input order changed bytes"


# ---------------------------------------------------------------------------
# T03 UNRESOLVED_AT_GRID when the quote grid cannot resolve the horizon
# ---------------------------------------------------------------------------
def t03():
    fx = F.fx_grid_unresolved()
    res = F.run(fx)
    r = res["records"][0]
    tr = fx["truth"]
    for w in tr["unresolved"]:
        assert r["windows"][w]["status"] == L.REASON_UNRESOLVED_AT_GRID, \
            (w, r["windows"][w])
    for w in tr["poll_gap"]:
        assert r["windows"][w]["status"] == L.REASON_POLL_GAP, (w, r["windows"][w])
    for w in tr["ok"]:
        assert r["windows"][w]["status"] == "OK", (w, r["windows"][w])


# ---------------------------------------------------------------------------
# T04 hourly tape with jitter: even H+60 dies when the event interval is
# 3601s wide -- the real tape's regime
# ---------------------------------------------------------------------------
def t04():
    fx = F.fx_hourly_jitter()
    res = F.run(fx)
    r = res["records"][0]
    assert r["event_interval"][1] - r["event_interval"][0] == 3601
    for w in fx["truth"]["all_horizons_poll_gap"]:
        assert r["windows"][w]["status"] == L.REASON_POLL_GAP, \
            (w, r["windows"][w]["status"])


# ---------------------------------------------------------------------------
# T05 ambiguity is excluded, never resolved
# ---------------------------------------------------------------------------
def t05():
    fx = F.fx_ambiguous()
    res = F.run(fx)
    assert res["n_records"] == 1
    r = res["records"][0]
    assert r["status"] == "EXCLUDED"
    assert r["primary_reason"] == L.REASON_AMBIGUOUS_PRE
    assert r["claim"] is None
    assert res["exclusion_reason_distribution"][L.REASON_AMBIGUOUS_PRE] == 1


# ---------------------------------------------------------------------------
# T06 out-of-hours announcement: wide interval, never patched or midpointed
# ---------------------------------------------------------------------------
def t06():
    fx = F.fx_overnight()
    res = F.run(fx)
    r = res["records"][0]
    tr = fx["truth"]
    assert r["event_interval"] == tr["event_interval"]
    width = r["event_interval"][1] - r["event_interval"][0]
    assert width == tr["width"] == 11 * 3600
    for h in (1, 2, 5, 10, 15, 30, 60):
        assert r["windows"][f"H+{h}"]["status"] == L.REASON_POLL_GAP
    c = r["claim"]
    assert_am4(c, "T06")
    assert c["t_lower"] == 0
    assert c["t_upper"] == 43234, c["t_upper"]        # (46800+2)-(3600-32)
    assert c["poll_interval_event"] == 11 * 3600


# ---------------------------------------------------------------------------
# T07 suspension across the event -> excluded, routed away from latency use
# ---------------------------------------------------------------------------
def t07():
    fx = F.fx_suspended()
    res = F.run(fx)
    r = res["records"][0]
    assert r["status"] == "EXCLUDED"
    assert r["primary_reason"] == L.REASON_SUSPENDED
    assert r["suspended_across_event"] is True
    assert r["claim"] is None


# ---------------------------------------------------------------------------
# T08 multi-player report: one report_id, ONE composite game-level record
# ---------------------------------------------------------------------------
def t08():
    fx = F.fx_multi_player()
    res = F.run(fx)
    assert res["n_records"] == fx["truth"]["n_records"], res["n_records"]
    r = res["records"][0]
    assert r["composite_members"] is not None
    assert len(r["composite_members"]) == fx["truth"]["n_members"]
    assert r["status"] == "TRUSTED"


# ---------------------------------------------------------------------------
# T09 same-poll pile-up of DIFFERENT reports: mutual confounding
# ---------------------------------------------------------------------------
def t09():
    fx = F.fx_same_poll_pileup()
    res = F.run(fx)
    assert res["n_records"] == 2, res["n_records"]
    for r in res["records"]:
        assert r["status"] == "EXCLUDED"
        assert r["primary_reason"] == L.REASON_CONFOUNDED_PREFIX + "POST"
        assert r["confounded_at"].get("POST") is True


# ---------------------------------------------------------------------------
# T10 unlinkable entities fail closed and are REPORTED, never dropped
# ---------------------------------------------------------------------------
def t10():
    fx = F.fx_entity_unresolved()
    res = F.run(fx)
    assert res["n_unlinkable_events"] == fx["truth"]["n_unlinkable_events"]
    assert res["n_unlinkable_quote_rows"] == fx["truth"]["n_unlinkable_rows"]
    assert res["unlinkable_events"][0]["exclusion_reason"] == \
        L.REASON_ENTITY_UNRESOLVED
    assert res["unlinkable_quote_rows"][0]["exclusion_reason"] == \
        L.REASON_ENTITY_UNRESOLVED
    assert res["exclusion_reason_distribution"][L.REASON_ENTITY_UNRESOLVED] == 2
    # and no fuzzy fallback exists to consult: resolution is exact-only
    assert fx["er"].resolve_team("Gamma Village Cats") is None
    assert fx["er"].resolve_team("alpha city foxes") == "T_FOX"  # exact-normalized


# ---------------------------------------------------------------------------
# T11 windows never cross commence
# ---------------------------------------------------------------------------
def t11():
    fx = F.fx_truncated()
    res = F.run(fx)
    r = res["records"][0]
    assert r["status"] == "EXCLUDED"
    assert r["primary_reason"] == L.REASON_TRUNCATED
    assert r["windows"]["POST_FIRST"]["status"] == L.REASON_TRUNCATED


# ---------------------------------------------------------------------------
# T12 in-play exclusion is structural at series construction
# ---------------------------------------------------------------------------
def t12():
    fx = F.fx_inplay()
    assert fx["n_inplay"] == fx["truth"]["n_inplay"], fx["n_inplay"]
    for s in fx["series"].values():
        assert all(p < s["commence_ts"] for p, _ in s["timeline"])
    res = F.run(fx)
    assert res["n_inplay_rows_dropped"] == fx["truth"]["n_inplay"]
    assert res["exclusion_reason_distribution"][L.REASON_IN_PLAY_ONLY] == \
        fx["truth"]["n_inplay"]


# ---------------------------------------------------------------------------
# T13 right-censoring when no repricing is observed before CLOSE
# ---------------------------------------------------------------------------
def t13():
    fx = F.fx_right_censored()
    res = F.run(fx)
    r = res["records"][0]
    assert r["status"] == "TRUSTED"
    c = r["claim"]
    assert_am4(c, "T13")
    assert c["censor_type"] == "right"
    assert c["t_upper"] == L.INF


# ---------------------------------------------------------------------------
# T14 UNBOUNDED vendor latency: claim degrades to UNSUPPORTABLE, grid
# unbounded, comparisons INDISTINGUISHABLE_AT_GRID, points refused
# ---------------------------------------------------------------------------
def t14():
    fx = F.fx_unbounded_vendor()
    res = F.run(fx)
    r = res["records"][0]
    c = r["claim"]
    assert_am4(c, "T14")
    assert c["vendor_latency_bound"]["bookx"] == L.UNBOUNDED
    assert c["measurement_grid_s"] == L.UNBOUNDED
    assert c["verdict"] == "UNSUPPORTABLE"
    assert c["fine_grained_admissible"] is False
    assert L.compare_reaction_claims(c, c, 10 ** 9) == \
        "INDISTINGUISHABLE_AT_GRID"
    try:
        L.assert_sharpness(60, c["measurement_grid_s"])
        raise AssertionError("sharpness violation not raised")
    except L.SharpnessViolation:
        pass


# ---------------------------------------------------------------------------
# T15 no clock-skew measurement -> CLOCK_UNBOUNDED, no claims (real tape)
# ---------------------------------------------------------------------------
def t15():
    fx = F.fx_clock_unmeasured()
    res = F.run(fx)
    r = res["records"][0]
    assert r["status"] == "EXCLUDED"
    assert r["primary_reason"] == L.REASON_CLOCK_UNBOUNDED
    assert r["claim"] is None
    try:
        L.widen_interval(0, 10, 30, None)
        raise AssertionError("widening with UNMEASURED skew not refused")
    except L.LinkageError:
        pass


# ---------------------------------------------------------------------------
# T16 any T2 input -> TIER_INSUFFICIENT, structurally
# ---------------------------------------------------------------------------
def t16():
    fx = F.fx_tier_t2()
    res = F.run(fx)
    r = res["records"][0]
    assert r["status"] == "EXCLUDED"
    assert r["primary_reason"] == L.REASON_TIER_INSUFFICIENT
    assert r["tier"] == "T2"


# ---------------------------------------------------------------------------
# T17 sharpness prohibition on a bounded grid
# ---------------------------------------------------------------------------
def t17():
    fx = F.fx_clean()
    res = F.run(fx)
    c = res["records"][0]["claim"]
    g = c["measurement_grid_s"]
    assert L.assert_sharpness(g + 1, g) is True
    try:
        L.assert_sharpness(g - 1, g)
        raise AssertionError("finer-than-grid point not refused")
    except L.SharpnessViolation:
        pass
    assert L.compare_reaction_claims(c, c, g) == "INDISTINGUISHABLE_AT_GRID"
    assert L.compare_reaction_claims(c, c, 2 * g + 1) == "DISTINGUISHABLE"
    # rendered statements are intervals, never bare points
    assert "[" in c["statement"] and "grid" in c["statement"]


# ---------------------------------------------------------------------------
# T18 censoring intervals come from the ACTUAL poll log only
# ---------------------------------------------------------------------------
def t18():
    fx = F.fx_overnight()
    # the actual previous poll is 11h earlier; a nominal-hourly assumption
    # would claim 1h. The interval must be the actual one.
    lo, up = fx["epl"].interval_ending_at(F.T0 + 12 * 3600)
    assert lo == F.T0 + 3600 and up == F.T0 + 12 * 3600
    try:
        fx["epl"].interval_ending_at(F.T0 + 2 * 3600)   # not a poll instant
        raise AssertionError("non-poll t_seen accepted")
    except L.LinkageError:
        pass
    # events whose capture time is not in the poll log are refused outright
    bad = F.injury_rows([(0, F.HOME, F.P1, "Out"),
                         (12345, F.HOME, F.P1, "Probable")])
    try:
        L.build_events_full_state(
            bad, fx["epl"], stream="injury", tier="T0",
            entity_fields=("team", "player"), state_field="status",
            report_key_fn=F.report_key, er_map=fx["er"],
            resolve_fn=F.resolve_injury_row(fx["er"]))
        raise AssertionError("capture outside poll log accepted")
    except L.LinkageError:
        pass


# ---------------------------------------------------------------------------
# T19 all ten exclusion reason codes are reachable and used
# ---------------------------------------------------------------------------
def t19():
    seen = set()
    for mk in (F.fx_clean, F.fx_grid_unresolved, F.fx_hourly_jitter,
               F.fx_ambiguous, F.fx_overnight, F.fx_suspended,
               F.fx_multi_player, F.fx_same_poll_pileup,
               F.fx_entity_unresolved, F.fx_truncated, F.fx_inplay,
               F.fx_right_censored, F.fx_clock_unmeasured, F.fx_tier_t2):
        res = F.run(mk())
        for k in res["exclusion_reason_distribution"]:
            seen.add(k.split("@")[0] + "@" if "@" in k else k)
        for wdist in res["horizon_window_status_distribution"].values():
            for k in wdist:
                if k != "OK":
                    seen.add(k.split("@")[0] + "@" if "@" in k else k)
    expected = {
        L.REASON_ENTITY_UNRESOLVED, L.REASON_AMBIGUOUS_PRE,
        "CONFOUNDED@", L.REASON_SUSPENDED, L.REASON_UNRESOLVED_AT_GRID,
        L.REASON_POLL_GAP, L.REASON_IN_PLAY_ONLY, L.REASON_TRUNCATED,
        L.REASON_TIER_INSUFFICIENT, L.REASON_CLOCK_UNBOUNDED,
    }
    missing = expected - seen
    assert not missing, f"reason codes never exercised: {missing}"


# ---------------------------------------------------------------------------
# T20 vendor-asserted stamps are advisory-only: carried, never keyed on
# ---------------------------------------------------------------------------
def t20():
    fx = F.fx_clean()
    res = F.run(fx)
    r = res["records"][0]
    c = r["claim"]
    # every timing quantity in the claim derives from poll instants
    polls = set(fx["qpl"].polls) | set(fx["epl"].polls)
    e_lo, e_up = r["event_interval"]
    assert e_lo in polls and e_up in polls
    pw = r["windows"]["POST_FIRST"]
    assert pw["q_lo"] in polls and pw["q_up"] in polls
    # the vendor stamp exists on the series (advisory) but no claim field
    # contains it: the fixture's last_update is always poll-7s, which can
    # never coincide with a poll instant
    s = list(fx["series"].values())[0]
    assert s["advisory_last_update"], "fixture should carry advisory stamps"
    for v in (c["t_lower"], c["t_upper"]):
        if isinstance(v, int):
            # bounds are poll differences +/- declared bounds, never
            # vendor-stamp differences; checked exactly in T01/T06
            pass
    assert c["channel"] == "WITNESSED"


# ---------------------------------------------------------------------------
# T21 aggregate claims keep the amendment-4 field set and stay intervals
# ---------------------------------------------------------------------------
def t21():
    c1 = F.run(F.fx_clean())["records"][0]["claim"]
    c2 = F.run(F.fx_overnight())["records"][0]["claim"]
    agg = L.aggregate_claim([c1, c2], {"AMBIGUOUS_PRE": 3})
    assert_am4(agg, "T21")
    assert agg["n_trusted"] == 2 and agg["n_excluded"] == 3
    assert agg["t_lower"] == 0 and agg["t_upper"] == 43234
    assert agg["measurement_grid_s"] == 43234
    assert L.aggregate_claim([], {}) is None


# ---------------------------------------------------------------------------
# T22 real-tape smoke probe (read-only; SKIP when live worktree absent)
# ---------------------------------------------------------------------------
LIVE_ROOT = "C:/Users/jgallagher/wnba-betting-model"


def t22():
    import real_tape_probe as P
    out = P.run_probe(LIVE_ROOT, max_quote_rows=8000, write_json=False)
    assert out["n_records"] > 0, "probe linked nothing"
    # the current tape has no clock-skew measurement: nothing may reach
    # TRUSTED, CLOCK_UNBOUNDED must appear, and no reaction claim may exist
    dist = out["exclusion_reason_distribution"]
    assert out["n_trusted"] == 0, "TRUSTED records on a skewless tape"
    assert dist.get(L.REASON_CLOCK_UNBOUNDED, 0) > 0, dist
    assert out["claims_emitted"] == 0


def main():
    tests = [
        ("T01_clean_pre_post_and_bound_arithmetic", t01),
        ("T02_determinism_bytes", t02),
        ("T03_unresolved_at_grid", t03),
        ("T04_hourly_jitter_poll_gap", t04),
        ("T05_ambiguous_excluded_not_resolved", t05),
        ("T06_overnight_gap_never_patched", t06),
        ("T07_suspended_across_event", t07),
        ("T08_multi_player_composite_report", t08),
        ("T09_same_poll_pileup_confounded", t09),
        ("T10_entity_unresolved_fails_closed", t10),
        ("T11_truncated_at_commence", t11),
        ("T12_inplay_structural", t12),
        ("T13_right_censored", t13),
        ("T14_unbounded_vendor_unsupportable", t14),
        ("T15_clock_unbounded", t15),
        ("T16_tier_insufficient", t16),
        ("T17_sharpness_prohibition", t17),
        ("T18_actual_poll_log_only", t18),
        ("T19_all_ten_reason_codes_reachable", t19),
        ("T20_vendor_stamps_advisory_only", t20),
        ("T21_aggregate_claim_fields", t21),
    ]
    for name, fn in tests:
        check(name, fn)

    if os.path.isdir(os.path.join(LIVE_ROOT, "data", "odds_capture")):
        check("T22_real_tape_smoke_readonly", t22)
    else:
        skip("T22_real_tape_smoke_readonly", "live worktree not present")

    n_fail = sum(1 for _, s, _ in RESULTS if s == "FAIL")
    for name, status, msg in RESULTS:
        line = f"{status:4s}  {name}"
        if msg:
            line += f"  -- {msg}"
        print(line)
    summary = {
        "suite": "M05_EVENT_MARKET_LINKAGE/TESTS.py",
        "n_pass": sum(1 for _, s, _ in RESULTS if s == "PASS"),
        "n_fail": n_fail,
        "n_skip": sum(1 for _, s, _ in RESULTS if s == "SKIP"),
    }
    print(json.dumps(summary))
    sys.exit(1 if n_fail else 0)


if __name__ == "__main__":
    main()
