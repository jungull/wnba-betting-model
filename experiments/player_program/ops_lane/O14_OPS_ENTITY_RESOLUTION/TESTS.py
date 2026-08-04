"""O14_OPS_ENTITY_RESOLUTION -- tests.

Repo convention: standalone runnable script, main() returns 1 on failure.
pytest is not installed and is not used.

T1-T4, T6 are SYNTHETIC and deterministic -- they are the contract of the fix.
T5 replays a REAL captured situation (Aneesah Morrow, 2026-08-02) read-only
from the repository-root worktree; if that snapshot is not present the test
reports SKIP and does not fail the suite.

Run:  python TESTS.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fix_entity_resolution import (Gaps, player_layer_baseline,  # noqa: E402
                                   player_layer_resolved, _ewma)

LIVE_REPO = Path(r"C:\Users\jgallagher\wnba-betting-model")
A2N = {"AAA": "Alpha", "BBB": "Beta"}

FAILURES: list[str] = []


def check(cond, label, detail=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + (f"  [{detail}]" if detail else ""))
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
    for i, (g, d) in enumerate(zip(gids, dates)):
        out.append((g, d, team, 9000 + hash(team) % 97, f"Filler {team}", 20.0))
    return out + list(extra)


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


def t5_real_morrow_2026_08_02():
    print("T5  REAL replay: Aneesah Morrow, captured Out by Toronto on "
          "2026-08-02, master visible only under Connecticut")
    mp = LIVE_REPO / "data" / "masters" / "master_player.parquet"
    il = LIVE_REPO / "data" / "injury_capture" / "injury_log.csv"
    if not (mp.exists() and il.exists()):
        print("  SKIP  live snapshot not present")
        return
    p_all = pd.read_parquet(mp)
    cutoff = pd.Timestamp("2026-08-02T21:00:04Z")
    p = p_all[(p_all.season == 2026)
              & (pd.to_datetime(p_all.game_date).dt.tz_localize("UTC")
                 < cutoff.normalize())].copy()
    inj = pd.read_csv(il)
    inj = inj[inj.capture_utc == "20260802T210004Z"]
    if not len(inj):
        print("  SKIP  capture 20260802T210004Z not in the log")
        return
    a2n = {"CON": "Connecticut Sun", "TOR": "Toronto Tempo"}
    inj = inj[inj.team.isin(a2n.values())]
    gb, gf = Gaps(), Gaps()
    b = player_layer_baseline(["CON", "TOR"], p, inj, a2n, gb)
    f = player_layer_resolved(["CON", "TOR"], p, inj, a2n, gf,
                              p_all=p_all, season=2026)
    b_con = {r["player"]: r for r in b["CON"]["available"]}
    check("Aneesah Morrow" in b_con,
          "baseline counts an OUT player AVAILABLE for her former team")
    if "Aneesah Morrow" in b_con:
        check(b_con["Aneesah Morrow"]["min_ewma"] > 20,
              "and attributes >20 projected minutes to her",
              f"{b_con['Aneesah Morrow']['min_ewma']:.2f}")
    check(any("Aneesah Morrow" in m and "matches NO ONE" in m
              for _, _, m in gb.items),
          "baseline emits the documented 'matches NO ONE' WARN for Toronto")
    check(not any(r["player"] == "Aneesah Morrow" for r in b["TOR"]["out"]),
          "baseline's Phase-3 Out gate does NOT fire for her anywhere")
    f_con = [r["player"] for r in f["CON"]["available"]]
    check("Aneesah Morrow" not in f_con, "fix removes her from Connecticut")
    check(any(r["player"] == "Aneesah Morrow" for r in f["TOR"]["out"]),
          "fix fires the Out gate at Toronto")
    d = (b["CON"]["sum_min_ewma_available"] or 0) - (f["CON"]["sum_min_ewma_available"] or 0)
    print(f"  INFO  CON sum_min_ewma_available: baseline "
          f"{b['CON']['sum_min_ewma_available']:.2f} -> fix "
          f"{f['CON']['sum_min_ewma_available']:.2f}  (delta {d:+.2f} min)")


def main() -> int:
    d = t1_transfer_history_truncation()
    print(f"  INFO  T1 baseline EWMA error vs identity: {d:.3f} minutes")
    t2_double_rostering()
    t3_out_under_new_team_before_ingest()
    t4_fail_closed_cold_start()
    t5_real_morrow_2026_08_02()
    t6_no_regression_when_nothing_moves()
    print()
    if FAILURES:
        print(f"FAILED ({len(FAILURES)}): " + "; ".join(FAILURES))
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
