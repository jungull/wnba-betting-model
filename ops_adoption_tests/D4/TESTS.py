#!/usr/bin/env python3
"""D-4 adoption tests — per-game execution scope (D-c) + forecast log SCHEMA/2.

Run:  python ops_adoption_tests/D4/TESTS.py       (exit 0 = all checks pass)

Covers, against the adopted code (not a copy):
  A. SCHEMA/2 writer: log_forecast emits schema evalharness/forecast_log/2
     with the additive optional alt_model_predictions (present-as-null).
  B. Reader tolerance: verify_chain / read_forecasts accept mixed /1 + /2
     chains; /1 records stand.
  C. verify_chain schema enforcement: /2 missing the field, /1 carrying the
     field, and unknown schemas are all localized failures.
  D. Obligation-keyed dedup (D-c limb 2): the same (game_id,
     decision_time_label, model_version_hash) obligation is refused at a
     DIFFERENT wall-clock cutoff — the exact case the shipped
     (game, cutoff, model) key could never catch. New model hash / other
     game / other label still log. Chain-level DuplicateForecastError stays
     underneath.
  E. Per-game scope (D-c limb 1): scope_slate_to_games declares exclusions;
     out-of-scope logging refused; game_ids=None preserves whole-slate
     behaviour byte-for-byte.
  F. Per-game isolation: one poisoned game neither aborts nor contaminates
     the remaining slate, at BOTH the forecast stage (forecast_slate) and
     the chain-write stage (log_row_to_chain).
  G. Migration tool: shipped, read-only w.r.t. the log, idempotent, atomic
     report; exercised against FIXTURES ONLY (never the live log).
  H. Live log (READ-ONLY): the real forecasts/forecast_log.jsonl still
     verifies under the tolerant reader; no row was rewritten.

All chain writes go to this directory's _scratch_chains/ or a tempdir.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))

from evalharness.forecast_log import (  # noqa: E402
    DuplicateForecastError,
    ForecastValidationError,
    GENESIS_PREV_SHA256,
    KNOWN_SCHEMAS,
    REQUIRED_FIELDS,
    REQUIRED_FIELDS_V2,
    SCHEMA,
    SCHEMA_V1,
    SCHEMA_V2,
    canonical_json,
    log_forecast,
    read_forecasts,
    record_sha256,
    verify_chain,
)
import daily_forecast as df  # noqa: E402

N_CHECKS = 0
FAILS: list[str] = []


def check(name: str, cond: bool) -> None:
    global N_CHECKS
    N_CHECKS += 1
    print(f"[{'PASS' if cond else 'FAIL'}] {name}")
    if not cond:
        FAILS.append(name)


def raises(exc_type, fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except exc_type:
        return True
    except Exception:
        return False
    return False


# ---------------------------------------------------------------------------
# synthetic fixtures
# ---------------------------------------------------------------------------

MH = "a" * 64
CUTOFF = datetime(2026, 8, 6, 12, 0, 0, tzinfo=timezone.utc)


def v1_record(idx: int, prev: str, game_id="G_V1", label="T-24h",
              cutoff="2026-08-01T12:00:00+00:00", extra=None) -> dict:
    """A record exactly as the /1 writer would have produced it."""
    rec = {
        "schema": SCHEMA_V1, "record_idx": idx, "prev_record_sha256": prev,
        "logged_at_utc": "2026-08-01T11:00:00.000000+00:00",
        "game_id": game_id, "forecast_cutoff": cutoff,
        "decision_time_label": label, "model_version_hash": MH,
        "data_snapshot_hash": "b" * 64,
        "w1_extraction": None,
        "core_only_prediction": {"margin": 1.0, "total": 160.0},
        "core_plus_w1_prediction": None,
        "market_line": None, "market_price": None, "market_book": None,
        "market_source": None, "predicted_close": None,
        "intended_bet_decision": "not_applicable", "paper_stake": 0.0,
    }
    if extra:
        rec.update(extra)
    return rec


def base_kwargs(i=0, **over):
    kw = dict(
        game_id=f"G2{i:03d}",
        forecast_cutoff=f"2026-08-{(i % 27) + 1:02d}T19:00:00+00:00",
        decision_time_label="T-24h",
        model_version_hash=MH,
        data_snapshot_hash="b" * 64,
        core_only_prediction={"margin": 3.5 + i, "total": 161.0},
        logged_at_utc=f"2026-08-05T10:{i:02d}:00+00:00",
    )
    kw.update(over)
    return kw


def team_state(abbr: str) -> dict:
    return {"abbr": abbr, "prior_games": 10, "fallback": False,
            "fta_t": 20.0, "ftpct_t": 0.8, "pf_t": 18.0,
            "fg3a_t": 25.0, "fg3m_t": 9.0, "fg3a_allow_t": 24.0,
            "raw_ft": 15.0, "raw_3pt": 27.0,
            "raw_paint": 34.0, "paint_allow_t": 32.0,
            "raw_np2": 10.0, "np2_allow_t": 9.0}


LG = {"lg_pf": 18.0, "lg_fta": 20.0, "lg_ftpct": 0.8, "lg_fg3a": 25.0,
      "lg_fg3m": 9.0, "lg_ft": 15.0, "lg_3pt": 27.0, "lg_paint": 33.0,
      "lg_np2": 10.0, "n_league_rows": 100}
PARAMS = {"cal_str_margin": [0.0, 1.0], "cal_str_home": [0.0, 1.0],
          "cal_str_away": [0.0, 1.0]}


def make_game(gid: str, home: str, away: str, hours_to_tip=8.0) -> dict:
    return {"home": home, "away": away,
            "home_name": home, "away_name": away,
            "event_time": CUTOFF + timedelta(hours=hours_to_tip),
            "api_event_id": f"ev-{gid}",
            "game_id": gid, "game_id_provisional": False,
            "crew": None, "ref_capture_utc": None,
            "market": dict(df._NULL_MARKET), "odds_event": True}


def log_row(r, log_path, cutoff=CUTOFF, model_hash=MH, scoped=None,
            gaps=None):
    return df.log_row_to_chain(
        r, players={}, cutoff=cutoff, model_hash=model_hash,
        snapshot_hash="b" * 64, snapshot_desc="synthetic",
        generated_at="2026-08-06T12:00:00+00:00", observed_time=None,
        git_head="deadbeef", odds_prov={}, live=False, log_path=log_path,
        scoped_game_ids=scoped, gaps=gaps or df.Gaps())


# ---------------------------------------------------------------------------
# A. SCHEMA/2 writer
# ---------------------------------------------------------------------------

def test_a_schema2_writer(tmp: Path):
    check("A1 SCHEMA constant is /2", SCHEMA == SCHEMA_V2 ==
          "evalharness/forecast_log/2")
    check("A2 SCHEMA_V1 unchanged", SCHEMA_V1 == "evalharness/forecast_log/1")
    check("A3 /2 required set = /1 + alt_model_predictions",
          REQUIRED_FIELDS_V2 - REQUIRED_FIELDS == {"alt_model_predictions"})
    check("A4 KNOWN_SCHEMAS is exactly {/1, /2}",
          set(KNOWN_SCHEMAS) == {SCHEMA_V1, SCHEMA_V2})

    path = tmp / "a_chain.jsonl"
    rec = log_forecast(log_path=path, **base_kwargs(0))
    check("A5 new record is schema /2", rec["schema"] == SCHEMA_V2)
    check("A6 alt_model_predictions present-as-null when omitted",
          "alt_model_predictions" in rec and rec["alt_model_predictions"] is None)
    rec2 = log_forecast(log_path=path, **base_kwargs(
        1, alt_model_predictions={"ridge_score_level_w2c1_v1": {"margin": 2.25}}))
    check("A7 alt_model_predictions round-trips",
          read_forecasts(path)[1]["alt_model_predictions"] ==
          {"ridge_score_level_w2c1_v1": {"margin": 2.25}})
    check("A8 chain of /2 records verifies", verify_chain(path).ok)
    check("A9 non-mapping alt_model_predictions refused",
          raises(ForecastValidationError, log_forecast, log_path=path,
                 **base_kwargs(2, alt_model_predictions=5)))
    check("A10 NaN inside alt_model_predictions refused (no-imputation)",
          raises(ForecastValidationError, log_forecast, log_path=path,
                 **base_kwargs(3, alt_model_predictions={"m": float("nan")})))
    check("A11 empty {} permitted (alt layer ran, produced nothing)",
          log_forecast(log_path=path, **base_kwargs(
              4, alt_model_predictions={}))["alt_model_predictions"] == {})


# ---------------------------------------------------------------------------
# B. mixed /1 + /2 reader tolerance
# ---------------------------------------------------------------------------

def test_b_mixed_chain(tmp: Path):
    path = tmp / "b_mixed.jsonl"
    r0 = v1_record(0, GENESIS_PREV_SHA256)
    path.write_text(canonical_json(r0) + "\n", encoding="utf-8", newline="\n")
    rep = verify_chain(path)
    check("B1 pure /1 chain still verifies (records stand)", rep.ok)
    rec = log_forecast(log_path=path, **base_kwargs(0, game_id="G_V2"))
    rep2 = verify_chain(path)
    check("B2 /2 appended after /1 — mixed chain verifies",
          rep2.ok and rep2.n_records == 2)
    check("B3 /2 record chains onto the /1 record",
          rec["prev_record_sha256"] == record_sha256(r0))
    parsed = read_forecasts(path)
    check("B4 read_forecasts returns both versions",
          [p["schema"] for p in parsed] == [SCHEMA_V1, SCHEMA_V2])
    served = df.served_obligation_keys(parsed)
    check("B5 obligation keys derivable from BOTH schemas",
          served == {("G_V1", "T-24h", MH), ("G_V2", "T-24h", MH)})
    check("B6 obligation guard honours obligations served under /1",
          raises(df.ObligationAlreadyServedError, df.obligation_guard, path,
                 game_id="G_V1", decision_time_label="T-24h",
                 model_version_hash=MH))


# ---------------------------------------------------------------------------
# C. verify_chain schema enforcement
# ---------------------------------------------------------------------------

def test_c_schema_enforcement(tmp: Path):
    # /2 record missing the /2-only field
    p1 = tmp / "c_missing.jsonl"
    log_forecast(log_path=p1, **base_kwargs(0))
    rec = json.loads(p1.read_text(encoding="utf-8").strip())
    del rec["alt_model_predictions"]
    p1.write_text(canonical_json(rec) + "\n", encoding="utf-8", newline="\n")
    rep = verify_chain(p1)
    check("C1 /2 record missing alt_model_predictions is localized",
          not rep.ok and rep.first_bad_index == 0
          and "alt_model_predictions" in rep.reason)

    # /1 record smuggling the /2-only field
    p2 = tmp / "c_smuggle.jsonl"
    r = v1_record(0, GENESIS_PREV_SHA256, extra={"alt_model_predictions": None})
    p2.write_text(canonical_json(r) + "\n", encoding="utf-8", newline="\n")
    rep2 = verify_chain(p2)
    check("C2 /1 record carrying the /2-only field is refused (drift visible)",
          not rep2.ok and rep2.first_bad_index == 0
          and "/2-only" in rep2.reason)

    # unknown schema
    p3 = tmp / "c_unknown.jsonl"
    r3 = v1_record(0, GENESIS_PREV_SHA256,
                   extra={"schema": "evalharness/forecast_log/3"})
    p3.write_text(canonical_json(r3) + "\n", encoding="utf-8", newline="\n")
    rep3 = verify_chain(p3)
    check("C3 unknown schema is refused, not silently accepted",
          not rep3.ok and rep3.first_bad_index == 0
          and "unknown schema" in rep3.reason)


# ---------------------------------------------------------------------------
# D. obligation-keyed dedup (D-c limb 2)
# ---------------------------------------------------------------------------

def test_d_obligation_dedup(tmp: Path):
    path = tmp / "d_chain.jsonl"
    g = make_game("G100", "HME", "AWY")
    state = {"HME": team_state("HME"), "AWY": team_state("AWY")}
    row, srows = df.forecast_one_game(
        g, state=state, lg=LG, params=PARAMS, players={}, cutoff=CUTOFF,
        season=2026, gaps=df.Gaps())
    check("D1 synthetic game forecasts (fixture sanity)",
          row["forecast"] is not None and row["label"] == "T-8h"
          and len(srows) == 2)

    check("D2 first serving logs", log_row(row, path) == "logged")
    # THE D-c REPRODUCTION, now refused: same obligation, LATER wall clock.
    check("D3 same obligation at a different wall-clock cutoff is REFUSED",
          log_row(row, path, cutoff=CUTOFF + timedelta(minutes=15))
          == "skipped_obligation")
    check("D4 chain still has exactly one record for the obligation",
          verify_chain(path).n_records == 1)
    check("D5 a NEW frozen model version may re-serve the obligation",
          log_row(row, path, model_hash="c" * 64) == "logged")
    g2 = make_game("G200", "HM2", "AW2")
    state2 = {"HM2": team_state("HM2"), "AW2": team_state("AW2")}
    row2, _ = df.forecast_one_game(
        g2, state=state2, lg=LG, params=PARAMS, players={}, cutoff=CUTOFF,
        season=2026, gaps=df.Gaps())
    check("D6 a different game at the same label is not deduped",
          log_row(row2, path) == "logged")
    row_other_label = dict(row)
    row_other_label["label"] = "T-30m"
    check("D7 a different label for the same game is not deduped",
          log_row(row_other_label, path,
                  cutoff=CUTOFF + timedelta(hours=7, minutes=30)) == "logged")
    check("D8 chain verifies after all servings", verify_chain(path).ok)

    # chain-level DuplicateForecastError remains underneath (exact same key)
    p2 = tmp / "d_dup.jsonl"
    log_forecast(log_path=p2, **base_kwargs(0))
    check("D9 chain-level exact-key duplicate still refused underneath",
          raises(DuplicateForecastError, log_forecast, log_path=p2,
                 **base_kwargs(0)))
    check("D10 obligation_guard direct: refuses served triple",
          raises(df.ObligationAlreadyServedError, df.obligation_guard, p2,
                 game_id="G2000", decision_time_label="T-24h",
                 model_version_hash=MH))


# ---------------------------------------------------------------------------
# E. per-game scope (D-c limb 1)
# ---------------------------------------------------------------------------

def test_e_scope(tmp: Path):
    slate = [make_game("A", "H1", "A1"), make_game("B", "H2", "A2"),
             make_game("C", "H3", "A3")]
    kept, decl = df.scope_slate_to_games(slate, None, "2026-08-06",
                                         CUTOFF, "unscoped")
    check("E1 game_ids=None preserves the whole slate, no declaration",
          kept == slate and decl is None)

    kept2, decl2 = df.scope_slate_to_games(slate, ["B", "Z"], "2026-08-06",
                                           CUTOFF, "test scope")
    check("E2 scoped slate keeps only the requested game",
          [g["game_id"] for g in kept2] == ["B"])
    d = decl2.to_dict()
    check("E3 declaration names every excluded game",
          d["excluded_game_ids"] == ["A", "C"] and d["scope"] == "per_game"
          and d["n_slate_games"] == 3)
    check("E4 absent requested id is noted, not silently dropped",
          any("Z" in n for n in d["notes"]))
    decl_path = decl2.write(tmp / "scope_declaration.json")
    check("E5 declaration writes as valid JSON",
          json.loads(decl_path.read_text(encoding="utf-8"))
          ["excluded_game_ids"] == ["A", "C"])

    check("E6 out-of-scope logging refused before touching the chain",
          raises(df.OutOfScopeError, df.obligation_guard,
                 tmp / "e_none.jsonl", game_id="A",
                 decision_time_label="T-24h", model_version_hash=MH,
                 scoped_to_game_ids=["B"]))
    check("E7 no chain file was created by the refusal",
          not (tmp / "e_none.jsonl").exists())


# ---------------------------------------------------------------------------
# F. per-game isolation (one failing game never aborts the slate)
# ---------------------------------------------------------------------------

def test_f_isolation(tmp: Path):
    # forecast stage: poisoned state raises inside the game unit
    bad = make_game("GBAD", "PBAD", "PBD2")
    good = make_game("GOOD", "HME", "AWY")
    state = {"PBAD": {}, "PBD2": {},
             "HME": team_state("HME"), "AWY": team_state("AWY")}
    gaps = df.Gaps()
    rows, snaps = df.forecast_slate(
        [bad, good], state=state, lg=LG, params=PARAMS, players={},
        cutoff=CUTOFF, season=2026, gaps=gaps)
    check("F1 both games produce rows (COMPLETENESS RULE)", len(rows) == 2)
    check("F2 poisoned game degrades EXPLICITLY",
          rows[0]["forecast"] is None
          and str(rows[0]["skip_reason"]).startswith("unhandled per-game failure"))
    check("F3 the failure is in the gaps ledger, not silent",
          any(g["component"] == "forecast" and "isolated" in g["message"]
              for g in gaps.items))
    check("F4 the good game is uncontaminated",
          rows[1]["forecast"] is not None and len(snaps) == 2)

    # chain-write stage: a poisoned row fails alone
    path = tmp / "f_chain.jsonl"
    poisoned = dict(rows[1])
    poisoned["game_id"] = "GPOISON"
    poisoned["market"] = {}          # KeyError inside the write unit
    st_bad = log_row(poisoned, path)
    st_no_forecast = log_row(rows[0], path)     # NO_FORECAST completeness row
    st_good = log_row(rows[1], path)
    check("F5 poisoned chain write fails alone", st_bad == "failed")
    check("F6 NO_FORECAST row still logged (completeness)",
          st_no_forecast == "logged")
    check("F7 good row still logged after the failure", st_good == "logged")
    recs = read_forecasts(path)
    check("F8 chain verifies with exactly the two survivable records",
          verify_chain(path).ok and len(recs) == 2)
    check("F9 NO_FORECAST record carries explicit status + reason",
          recs[0]["core_only_prediction"]["status"] == "NO_FORECAST"
          and "unhandled per-game failure"
          in recs[0]["core_only_prediction"]["no_forecast_reason"])
    check("F10 records written by the job are schema /2 with the field",
          all(r["schema"] == SCHEMA_V2 and "alt_model_predictions" in r
              for r in recs))


# ---------------------------------------------------------------------------
# G. migration tool (fixtures only — NEVER the live log)
# ---------------------------------------------------------------------------

def test_g_migration_tool(tmp: Path):
    fixture = tmp / "g_fixture.jsonl"
    r0 = v1_record(0, GENESIS_PREV_SHA256)
    fixture.write_text(canonical_json(r0) + "\n", encoding="utf-8",
                       newline="\n")
    log_forecast(log_path=fixture, **base_kwargs(0, game_id="G_MIG"))
    before = fixture.read_bytes()

    script = REPO / "migrate_forecast_log_schema2.py"
    out1 = tmp / "census1.json"
    p1 = subprocess.run([sys.executable, str(script), "--log", str(fixture),
                         "--report", str(out1)],
                        cwd=str(REPO), capture_output=True, text=True)
    check("G1 migration tool exits 0 on a healthy mixed chain",
          p1.returncode == 0)
    rep = json.loads(out1.read_text(encoding="utf-8"))
    check("G2 census counts /1 and /2 correctly",
          rep["n_schema_v1"] == 1 and rep["n_schema_v2"] == 1
          and rep["chain_ok"] is True and rep["ok"] is True)
    check("G3 the log is byte-identical after the tool ran (read-only)",
          fixture.read_bytes() == before)
    out2 = tmp / "census2.json"
    p2 = subprocess.run([sys.executable, str(script), "--log", str(fixture),
                         "--report", str(out2)],
                        cwd=str(REPO), capture_output=True, text=True)
    check("G4 idempotent: second run, identical census",
          p2.returncode == 0 and out1.read_text(encoding="utf-8")
          == out2.read_text(encoding="utf-8"))

    broken = tmp / "g_broken.jsonl"
    lines = fixture.read_text(encoding="utf-8").splitlines()
    broken.write_text(lines[1] + "\n", encoding="utf-8", newline="\n")
    p3 = subprocess.run([sys.executable, str(script), "--log", str(broken)],
                        cwd=str(REPO), capture_output=True, text=True)
    check("G5 migration tool exits 1 on a broken chain", p3.returncode == 1)


# ---------------------------------------------------------------------------
# H. the live log, READ-ONLY: /1 records stand under the tolerant reader
# ---------------------------------------------------------------------------

def test_h_live_log_readonly():
    live = REPO / "forecasts" / "forecast_log.jsonl"
    before = live.read_bytes()
    rep = verify_chain(live)
    recs = read_forecasts(live)
    check("H1 live chain verifies under the /2-aware reader",
          rep.ok and rep.n_records == len(recs))
    check("H2 every live record is schema /1 and stands untouched",
          all(r["schema"] == SCHEMA_V1 for r in recs)
          and all("alt_model_predictions" not in r for r in recs))
    check("H3 live log bytes unchanged by this suite (read-only)",
          live.read_bytes() == before)


def main() -> int:
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        test_a_schema2_writer(tmp)
        test_b_mixed_chain(tmp)
        test_c_schema_enforcement(tmp)
        test_d_obligation_dedup(tmp)
        test_e_scope(tmp)
        test_f_isolation(tmp)
        test_g_migration_tool(tmp)
    test_h_live_log_readonly()
    print(f"\n{N_CHECKS} checks, {N_CHECKS - len(FAILS)} passing, "
          f"{len(FAILS)} failing")
    if FAILS:
        for f in FAILS:
            print(f"  FAILED: {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
