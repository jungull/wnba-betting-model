"""O14 adoption tests (bundle B, decision D022).

Repo convention: standalone runnable script, main() returns 1 on failure.
pytest is not installed and is not used.

T1-T4, T6 are the research node's synthetic contract tests, ported verbatim
against the ADOPTED production module (entity_resolution.player_layer_resolved)
and the vendored baseline (baseline_port.py).  T5 is the node's real replay
(Aneesah Morrow, 2026-08-02), pointed at THIS worktree's committed data
snapshot -- never the live main worktree; it SKIPs when the capture window is
not in the snapshot (base 735b63b predates 2026-08-02, so it SKIPs here).

T7-T12 cover what the port does not: the alias-table artifact and its
no-fuzzy contract, assignment_source recording, the forward-only capture
writers (injury + props), and the shipped-not-run migration script.

Run:  python ops_adoption_tests/O14/test_o14.py
"""
from __future__ import annotations

import csv
import json
import shutil
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]                       # the adoption worktree
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))

from baseline_port import player_layer_baseline, _ewma       # noqa: E402
from entity_resolution import (Gaps, _norm_name, load_alias_table,  # noqa: E402
                               player_layer_resolved, resolve_player_id,
                               ALIAS_TABLE_PATH, ALIAS_TABLE_SCHEMA)

SCRATCH = HERE / "_scratch"
A2N = {"AAA": "Alpha", "BBB": "Beta"}

FAILURES: list[str] = []
CHECKS = {"run": 0, "passed": 0}


def check(cond, label, detail=""):
    CHECKS["run"] += 1
    if cond:
        CHECKS["passed"] += 1
    print(("  PASS  " if cond else "  FAIL  ") + label
          + (f"  [{detail}]" if detail else ""))
    if not cond:
        FAILURES.append(label)


def frame(rows):
    p = pd.DataFrame(rows, columns=["game_id", "game_date", "team_abbreviation",
                                    "player_id", "player_name", "minutes"])
    p["season"] = 2026
    p["game_date"] = pd.to_datetime(p.game_date)
    return p


def team_rows(team, gids, dates, extra=()):
    """A filler player so every team has a roster independent of the subject."""
    out = []
    for g, d in zip(gids, dates):
        out.append((g, d, team, 9000 + hash(team) % 97, f"Filler {team}", 20.0))
    return out + list(extra)


# ---------------------------------------------------------------------------
# T1-T6: research-node contract tests, ported
# ---------------------------------------------------------------------------
def t1_transfer_history_truncation():
    print("T1  transferred player's prior-team history must not be discarded")
    subj = [(f"A{i}", f"2026-07-{10+i:02d}", "AAA", 1, "Subject Player", 30.0)
            for i in range(5)]
    subj += [("B9", "2026-08-01", "BBB", 1, "Subject Player", 20.0)]
    p = frame(team_rows("AAA", [f"A{i}" for i in range(5)],
                        [f"2026-07-{10+i:02d}" for i in range(5)])
              + team_rows("BBB", ["B7", "B8", "B9"],
                          ["2026-07-28", "2026-07-30", "2026-08-01"])
              + subj)
    inj = pd.DataFrame(columns=["team", "player", "status"])
    b = player_layer_baseline(["AAA", "BBB"], p, inj, A2N, Gaps())
    f = player_layer_resolved(["AAA", "BBB"], p, inj, A2N, Gaps())
    bs = next(r for r in b["BBB"]["available"] if r["player"] == "Subject Player")
    fs = next(r for r in f["BBB"]["available"] if r["player"] == "Subject Player")
    identity = _ewma(pd.Series([30.0] * 5 + [20.0]))
    check(bs["games_played"] == 1, "baseline sees 1 of 6 games", str(bs["games_played"]))
    check(abs(bs["min_ewma"] - 20.0) < 1e-9, "baseline EWMA = the single new-team game",
          f"{bs['min_ewma']:.4f}")
    check(fs["games_played"] == 6, "fix sees all 6 games", str(fs["games_played"]))
    check(abs(fs["min_ewma"] - identity) < 1e-9, "fix EWMA = identity EWMA",
          f"{fs['min_ewma']:.4f} vs {identity:.4f}")
    check(fs["transferred_in_season"] is True, "fix flags the transfer")
    return abs(bs["min_ewma"] - identity)


def t2_double_rostering():
    print("T2  one identity may not occupy two recency rosters")
    subj = [("A3", "2026-07-30", "AAA", 1, "Subject Player", 25.0),
            ("B3", "2026-08-01", "BBB", 1, "Subject Player", 18.0)]
    p = frame(team_rows("AAA", ["A1", "A2", "A3"],
                        ["2026-07-26", "2026-07-28", "2026-07-30"])
              + team_rows("BBB", ["B1", "B2", "B3"],
                          ["2026-07-27", "2026-07-29", "2026-08-01"]) + subj)
    inj = pd.DataFrame(columns=["team", "player", "status"])
    b = player_layer_baseline(["AAA", "BBB"], p, inj, A2N, Gaps())
    f = player_layer_resolved(["AAA", "BBB"], p, inj, A2N, Gaps())
    bn = [t for t in ("AAA", "BBB")
          if any(r["player"] == "Subject Player" for r in b[t]["available"])]
    fn = [t for t in ("AAA", "BBB")
          if any(r["player"] == "Subject Player" for r in f[t]["available"])]
    check(bn == ["AAA", "BBB"], "baseline double-rosters the player", str(bn))
    check(fn == ["BBB"], "fix assigns her to the most recent team only", str(fn))


def t3_out_under_new_team_before_ingest():
    print("T3  an Out published under the NEW team, before the master has a "
          "game for that team, must still fire the gate")
    subj = [(f"A{i}", f"2026-07-{24+2*i:02d}", "AAA", 1, "Subject Player", 32.0)
            for i in range(3)]
    p = frame(team_rows("AAA", ["A0", "A1", "A2"],
                        ["2026-07-24", "2026-07-26", "2026-07-28"])
              + team_rows("BBB", ["B1", "B2", "B3"],
                          ["2026-07-25", "2026-07-27", "2026-07-29"]) + subj)
    inj = pd.DataFrame([{"team": "Beta", "player": "Subject Player", "status": "Out"}])
    gb, gf = Gaps(), Gaps()
    b = player_layer_baseline(["AAA", "BBB"], p, inj, A2N, gb)
    f = player_layer_resolved(["AAA", "BBB"], p, inj, A2N, gf)
    b_avail_A = [r["player"] for r in b["AAA"]["available"]]
    check("Subject Player" in b_avail_A,
          "baseline still counts the Out player AVAILABLE for her old team")
    check(b["BBB"]["n_out"] == 0, "baseline fires no Out anywhere",
          f"BBB n_out={b['BBB']['n_out']}")
    check(any("matches NO ONE" in m for _, _, m in gb.items),
          "baseline emits only the documented WARN")
    f_avail_A = [r["player"] for r in f["AAA"]["available"]]
    check("Subject Player" not in f_avail_A, "fix removes her from the old team")
    check(any(r["player"] == "Subject Player" for r in f["BBB"]["out"]),
          "fix fires the Out gate at the new team")
    check(abs(f["BBB"]["vacated_min_ewma"] - 32.0) < 1e-9,
          "fix attributes her vacated minutes to the new team",
          f"{f['BBB']['vacated_min_ewma']:.3f}")


def t4_fail_closed_cold_start():
    print("T4  an Out that binds to no identity must fail CLOSED, not WARN")
    p = frame(team_rows("AAA", ["A1", "A2", "A3"],
                        ["2026-07-26", "2026-07-28", "2026-07-30"])
              + team_rows("BBB", ["B1", "B2", "B3"],
                          ["2026-07-27", "2026-07-29", "2026-08-01"]))
    inj = pd.DataFrame([{"team": "Alpha", "player": "Nobody Atall", "status": "Out"}])
    gb, gf = Gaps(), Gaps()
    player_layer_baseline(["AAA", "BBB"], p, inj, A2N, gb)
    f = player_layer_resolved(["AAA", "BBB"], p, inj, A2N, gf)
    check(not gb.by_sev("BLOCK") and gb.by_sev("WARN"),
          "baseline degrades to WARN and continues")
    check(bool(gf.by_sev("BLOCK")), "fix raises BLOCK")
    check(any(r.get("cold_start_unresolved") for r in f["AAA"]["out"]),
          "fix materialises an explicit unresolved cold-start object")


def t5_real_morrow_2026_08_02():
    print("T5  REAL replay: Aneesah Morrow, captured Out by Toronto on "
          "2026-08-02, master visible only under Connecticut "
          "(reads THIS worktree's committed snapshot, never the live repo)")
    mp = ROOT / "data" / "masters" / "master_player.parquet"
    il = ROOT / "data" / "injury_capture" / "injury_log.csv"
    if not (mp.exists() and il.exists()):
        print("  SKIP  snapshot not present")
        return
    inj = pd.read_csv(il)
    inj = inj[inj.capture_utc == "20260802T210004Z"]
    if not len(inj):
        print("  SKIP  capture 20260802T210004Z not in this worktree's "
              "snapshot (base 735b63b ends 2026-08-01)")
        return
    p_all = pd.read_parquet(mp)
    cutoff = pd.Timestamp("2026-08-02T21:00:04Z")
    p = p_all[(p_all.season == 2026)
              & (pd.to_datetime(p_all.game_date).dt.tz_localize("UTC")
                 < cutoff.normalize())].copy()
    a2n = {"CON": "Connecticut Sun", "TOR": "Toronto Tempo"}
    inj = inj[inj.team.isin(a2n.values())]
    gb, gf = Gaps(), Gaps()
    b = player_layer_baseline(["CON", "TOR"], p, inj, a2n, gb)
    f = player_layer_resolved(["CON", "TOR"], p, inj, a2n, gf,
                              p_all=p_all, season=2026)
    b_con = {r["player"]: r for r in b["CON"]["available"]}
    check("Aneesah Morrow" in b_con,
          "baseline counts an OUT player AVAILABLE for her former team")
    check(not any(r["player"] == "Aneesah Morrow" for r in b["TOR"]["out"]),
          "baseline's Phase-3 Out gate does NOT fire for her anywhere")
    f_con = [r["player"] for r in f["CON"]["available"]]
    check("Aneesah Morrow" not in f_con, "fix removes her from Connecticut")
    check(any(r["player"] == "Aneesah Morrow" for r in f["TOR"]["out"]),
          "fix fires the Out gate at Toronto")


def t6_no_regression_when_nothing_moves():
    print("T6  with no transfers and no unbound designations the fix must "
          "agree with the baseline exactly")
    rows = []
    for t in ("AAA", "BBB"):
        for i in range(3):
            for k in range(4):
                rows.append((f"{t}{i}", f"2026-07-{25+i:02d}", t,
                             1000 + hash(t) % 13 * 10 + k, f"{t} Player {k}",
                             10.0 + 3 * k + i))
    p = frame(rows)
    inj = pd.DataFrame([{"team": "Alpha", "player": "AAA Player 2", "status": "Out"},
                        {"team": "Beta", "player": "BBB Player 0", "status": "Probable"}])
    b = player_layer_baseline(["AAA", "BBB"], p, inj, A2N, Gaps())
    f = player_layer_resolved(["AAA", "BBB"], p, inj, A2N, Gaps())
    for t in ("AAA", "BBB"):
        check(sorted(r["player"] for r in b[t]["available"])
              == sorted(r["player"] for r in f[t]["available"]),
              f"{t}: identical available set")
        check(abs((b[t]["sum_min_ewma_available"] or 0)
                  - (f[t]["sum_min_ewma_available"] or 0)) < 1e-9,
              f"{t}: identical sum_min_ewma_available",
              f"{b[t]['sum_min_ewma_available']} vs {f[t]['sum_min_ewma_available']}")
        check(b[t]["n_out"] == f[t]["n_out"], f"{t}: identical n_out")


# ---------------------------------------------------------------------------
# T7-T12: adoption coverage the port does not provide
# ---------------------------------------------------------------------------
def _two_team_frame():
    subj = [(f"A{i}", f"2026-07-{24+2*i:02d}", "AAA", 1, "Subject Player", 32.0)
            for i in range(3)]
    return frame(team_rows("AAA", ["A0", "A1", "A2"],
                           ["2026-07-24", "2026-07-26", "2026-07-28"])
                 + team_rows("BBB", ["B1", "B2", "B3"],
                             ["2026-07-25", "2026-07-27", "2026-07-29"]) + subj)


def t7_alias_table_no_fuzzy():
    print("T7  alias table: explicit alias binds; a near-miss without an "
          "alias must NOT bind (no fuzzy fallback); wrong schema is an error")
    p = _two_team_frame()
    inj = pd.DataFrame([{"team": "Alpha", "player": "Subject Playr",  # typo
                         "status": "Out"}])
    gf = Gaps()
    f = player_layer_resolved(["AAA", "BBB"], p, inj, A2N, gf)
    check(bool(gf.by_sev("BLOCK")),
          "near-miss spelling does NOT bind without an alias (BLOCK)")
    check(any(r.get("cold_start_unresolved") for r in f["AAA"]["out"]),
          "and produces the explicit unresolved object")
    alias_p = SCRATCH / "alias_ok.json"
    alias_p.write_text(json.dumps({"schema": ALIAS_TABLE_SCHEMA,
                                   "aliases": {"Subject Playr": 1},
                                   "rejected_candidates": []}),
                       encoding="utf-8")
    gf2 = Gaps()
    f2 = player_layer_resolved(["AAA", "BBB"], p, inj, A2N, gf2,
                               alias_path=alias_p)
    check(not gf2.by_sev("BLOCK"), "with a human-curated alias row it binds")
    check(any(r["player"] == "Subject Player" and r["player_id"] == 1
              for r in f2["AAA"]["out"]),
          "alias-bound Out fires the gate on the resolved identity")
    bad_p = SCRATCH / "alias_bad.json"
    bad_p.write_text(json.dumps({"schema": "ops_lane/O14/alias_table/999",
                                 "aliases": {}}), encoding="utf-8")
    try:
        load_alias_table(bad_p)
        check(False, "wrong alias-table schema raises ValueError")
    except ValueError:
        check(True, "wrong alias-table schema raises ValueError")


def t8_assignment_source():
    print("T8  every roster entry records assignment_source "
          "(last_game vs designation_transfer)")
    p = _two_team_frame()
    inj = pd.DataFrame([{"team": "Beta", "player": "Subject Player",
                         "status": "Out"}])
    f = player_layer_resolved(["AAA", "BBB"], p, inj, A2N, Gaps())
    filler = next(r for r in f["AAA"]["available"]
                  if r["player"] == "Filler AAA")
    subj = next(r for r in f["BBB"]["out"] if r["player"] == "Subject Player")
    check(filler["assignment_source"] == "last_game",
          "game-derived entry: last_game", filler["assignment_source"])
    check(subj["assignment_source"] == "designation_transfer",
          "designation-claimed transfer: designation_transfer",
          subj["assignment_source"])
    check(f["BBB"]["designation_transfers_in"]
          and f["BBB"]["designation_transfers_in"][0]["from"] == "AAA",
          "team dict records the transfer provenance")
    all_recs = [r for t in ("AAA", "BBB")
                for r in f[t]["available"] + f[t]["out"]]
    check(all("assignment_source" in r for r in all_recs),
          "assignment_source present on every roster entry")


def t9_injury_writer_forward():
    print("T9  injury writer: v2 on a fresh log; v1-header log is appended "
          "v1-shaped with prior bytes untouched")
    import injury_capture_daily as icd
    idx = {_norm_name("Subject Player"): 1}
    rows = [{"report_date": "2026-08-06", "game_date": "2026-08-06",
             "team": "Alpha", "player": "Subject Player", "status": "Out",
             "reason": "knee"},
            {"report_date": "2026-08-06", "game_date": "2026-08-06",
             "team": "Beta", "player": "Mystery Person", "status": "Available",
             "reason": ""}]
    saved_out, saved_log = icd.OUTDIR, icd.LOGCSV
    try:
        icd.OUTDIR = SCRATCH / "inj_fresh"
        icd.LOGCSV = icd.OUTDIR / "injury_log.csv"
        icd.append_log("20260806T120000Z", rows, "test", name_to_id=idx)
        with open(icd.LOGCSV, newline="", encoding="utf-8") as fh:
            got = list(csv.reader(fh))
        check(got[0] == icd.CSV_HEADER_V2, "fresh log gets the v2 header")
        check(got[1][4] == "Subject Player" and got[1][8] == "1",
              "resolved row: raw string retained, player_id populated",
              str(got[1]))
        check(got[2][4] == "Mystery Person" and got[2][8] == "",
              "unresolved row: player_id blank, NO fuzzy fallback")

        icd.OUTDIR = SCRATCH / "inj_legacy"
        icd.OUTDIR.mkdir(parents=True, exist_ok=True)
        icd.LOGCSV = icd.OUTDIR / "injury_log.csv"
        with open(icd.LOGCSV, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(icd.CSV_HEADER)
            w.writerow(["20260801T150005Z", "2026-08-01", "2026-08-01",
                        "Alpha", "Old Row", "Out", "ankle", "wnba_official"])
        before = icd.LOGCSV.read_bytes()
        icd.append_log("20260806T120000Z", rows, "test", name_to_id=idx)
        after = icd.LOGCSV.read_bytes()
        check(after[:len(before)] == before,
              "existing bytes are untouched (LIVE-DATA RULE)")
        with open(icd.LOGCSV, newline="", encoding="utf-8") as fh:
            got = list(csv.reader(fh))
        check(got[0] == icd.CSV_HEADER, "legacy header not rewritten")
        check(all(len(r) == len(icd.CSV_HEADER) for r in got[1:]),
              "appended rows stay v1-shaped (never a ragged CSV)")
    finally:
        icd.OUTDIR, icd.LOGCSV = saved_out, saved_log


def t10_props_writer_forward():
    print("T10 props writer: v2 on a fresh master; v1-header master is "
          "appended v1-shaped with prior bytes untouched")
    import props_capture_daily as pcd
    idx = {_norm_name("Subject Player"): 1}
    base = {"api_event_id": "ev1", "home_team": "Alpha", "away_team": "Beta",
            "commence_time": "2026-08-06T23:00:00Z", "bookmaker_key": "bk",
            "market_key": "player_points", "line": 14.5, "over_price": -110,
            "under_price": -110, "snapshot_utc": "20260806T120000Z",
            "last_update": "2026-08-06T11:59:00Z"}
    rows = [dict(base, player_name="Subject Player"),
            dict(base, player_name="Mystery Person")]
    pcd.resolve_player_ids(rows, name_to_id=idx)
    check(rows[0]["player_id"] == "1" and rows[1]["player_id"] == "",
          "capture-time resolution: known -> id, unknown -> blank")
    fresh = SCRATCH / "props_fresh.csv"
    n, v2 = pcd.append_master(rows, master_path=fresh)
    with open(fresh, newline="", encoding="utf-8") as fh:
        got = list(csv.reader(fh))
    check(v2 and got[0] == pcd.COLUMNS_V2, "fresh master gets the v2 header")
    check(got[1][6] == "Subject Player" and got[1][12] == "1",
          "raw player_name retained alongside the resolved id")
    legacy = SCRATCH / "props_legacy.csv"
    with open(legacy, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(pcd.COLUMNS)
        w.writerow(["ev0", "Alpha", "Beta", "2026-08-01T23:00:00Z", "bk",
                    "player_points", "Old Row", "12.5", "-110", "-110",
                    "20260801T120000Z", "2026-08-01T11:59:00Z"])
    before = legacy.read_bytes()
    n, v2 = pcd.append_master(rows, master_path=legacy)
    after = legacy.read_bytes()
    check(after[:len(before)] == before,
          "existing bytes are untouched (LIVE-DATA RULE)")
    with open(legacy, newline="", encoding="utf-8") as fh:
        got = list(csv.reader(fh))
    check((not v2) and got[0] == pcd.COLUMNS
          and all(len(r) == len(pcd.COLUMNS) for r in got[1:]),
          "legacy master: v1 header kept, appended rows v1-shaped")


def t11_migration_idempotent_atomic():
    print("T11 migration script: dry-run writes nothing; apply adds the "
          "column, fills only resolvable rows, preserves raw; rerun is a "
          "byte-identical no-op")
    import migrate_o14_capture_player_id as mig
    idx = {_norm_name("Subject Player"): 1, _norm_name("Other Player"): 2}
    fix = SCRATCH / "mig_injury.csv"
    with open(fix, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["capture_utc", "report_date", "game_date", "team",
                    "player", "status", "reason", "source"])
        w.writerow(["20260801T150005Z", "2026-08-01", "2026-08-01", "Alpha",
                    "Subject Player", "Out", "knee", "wnba_official"])
        w.writerow(["20260801T150005Z", "2026-08-01", "2026-08-01", "Beta",
                    "Mystery Person", "Available", "", "wnba_official"])
        w.writerow(["20260801T150005Z", "2026-08-01", "2026-08-01", "Alpha",
                    "Other Player", "Probable", "", "wnba_official"])
    before = fix.read_bytes()
    s = mig.migrate_csv(fix, "player", idx, apply=False)
    check(s["changed"] and not s["applied"] and fix.read_bytes() == before,
          "dry run reports changes and writes nothing")
    s = mig.migrate_csv(fix, "player", idx, apply=True)
    check(s["applied"] and s["added_column"] and s["filled"] == 2
          and s["unresolved"] == ["Mystery Person"],
          "apply: column added, 2 filled, 1 unresolved", str(s))
    with open(fix, newline="", encoding="utf-8") as fh:
        got = list(csv.reader(fh))
    check(got[0][-1] == "player_id" and len(got) == 4,
          "header extended, row count preserved")
    check([r[4] for r in got[1:]] == ["Subject Player", "Mystery Person",
                                      "Other Player"],
          "raw capture strings preserved in order")
    check([r[8] for r in got[1:]] == ["1", "", "2"],
          "ids filled where resolvable, blank otherwise (no fuzzy)")
    after_first = fix.read_bytes()
    s2 = mig.migrate_csv(fix, "player", idx, apply=True)
    check(not s2["changed"] and not s2["applied"]
          and fix.read_bytes() == after_first,
          "second apply: no change, no write, bytes identical (idempotent)")
    check(not list(fix.parent.glob(fix.name + ".*.migrating")),
          "no temp file left behind (atomic replace)")
    try:
        mig.migrate_csv(fix, "player_name", idx, apply=False)
        check(False, "wrong name column raises ValueError")
    except ValueError:
        check(True, "wrong name column raises ValueError")


def t12_alias_artifact_installed():
    print("T12 the persistent alias-table artifact is installed")
    check(ALIAS_TABLE_PATH.exists(),
          f"artifact exists at {ALIAS_TABLE_PATH.relative_to(ROOT)}")
    doc = json.loads(ALIAS_TABLE_PATH.read_text(encoding="utf-8"))
    check(doc.get("schema") == "ops_lane/O14/alias_table/1",
          "schema id is ops_lane/O14/alias_table/1")
    check(doc.get("aliases") == {}, "aliases empty by design")
    names = {c.get("name") for c in doc.get("rejected_candidates", [])}
    check(names == {"Iliana Rupert", "Megan Gustafson"},
          "explicit rejected-candidate records carried over", str(names))
    check(load_alias_table() == {}, "load_alias_table() accepts the artifact")


def main() -> int:
    if SCRATCH.exists():
        shutil.rmtree(SCRATCH)
    SCRATCH.mkdir(parents=True)
    d = t1_transfer_history_truncation()
    print(f"  INFO  T1 baseline EWMA error vs identity: {d:.3f} minutes")
    t2_double_rostering()
    t3_out_under_new_team_before_ingest()
    t4_fail_closed_cold_start()
    t5_real_morrow_2026_08_02()
    t6_no_regression_when_nothing_moves()
    t7_alias_table_no_fuzzy()
    t8_assignment_source()
    t9_injury_writer_forward()
    t10_props_writer_forward()
    t11_migration_idempotent_atomic()
    t12_alias_artifact_installed()
    print()
    print(f"checks run: {CHECKS['run']}, passed: {CHECKS['passed']}")
    if FAILURES:
        print(f"FAILED ({len(FAILURES)}): " + "; ".join(FAILURES))
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
