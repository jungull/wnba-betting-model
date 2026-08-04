#!/usr/bin/env python3
"""TESTS.py — structural and arithmetic checks on FINDINGS.json.

Repo convention: standalone runnable script, main() returns 1 on failure. pytest is not installed.

These tests do NOT re-derive coverage. They check that the ledger is internally honest: that
coverage arithmetic closes, that no field claims cutoff-validity its verdict does not support,
that the season partition sums to the declared universe, and that the verdict vocabulary is
closed. A ledger that passed these and reported wrong numbers would still be wrong; a ledger that
failed them is wrong for certain.

    python experiments/player_program/data_lane/D10_FIELD_AVAILABILITY_LEDGER/TESTS.py
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FINDINGS = HERE / "FINDINGS.json"

VERDICTS = {"CUTOFF_VALID", "CUTOFF_UNPROVEN", "CUTOFF_INVALID", "ABSENT"}
REQUIRED_FAMILIES = {
    "injuries", "transactions", "schedules", "rest", "venues", "travel", "elevation",
    "time_zones", "tip_times", "roster_continuity", "coaching", "opponent_history",
}
CELL_KEYS = {"rows", "covered", "coverage", "cutoff_valid", "cutoff_valid_rate"}

FAILURES: list[str] = []


def check(cond: bool, msg: str) -> None:
    if not cond:
        FAILURES.append(msg)


def cells(cov: dict):
    """Every coverage cell in the block, with a label."""
    yield "overall", cov["overall"]
    for k, v in cov["by_season"].items():
        yield f"season/{k}", v
    for k, v in cov["by_season_type"].items():
        yield f"season_type/{k}", v
    for k, v in cov["by_fold"].items():
        yield f"fold/{k}/train", v["train"]
        yield f"fold/{k}/test", v["test"]


def main() -> int:
    check(FINDINGS.exists(), "FINDINGS.json does not exist")
    if FAILURES:
        print("\n".join(FAILURES))
        return 1
    d = json.loads(FINDINGS.read_text(encoding="utf-8"))

    # -- 1. the epistemic-status line survives verbatim -------------------- #
    check(d.get("epistemic_status", "").startswith("VERIFIED_READ_ONLY_DERIVATION"),
          "epistemic_status is missing or not the declared line")
    check("Availability is not eligibility and eligibility is not admission."
          in d.get("epistemic_status", ""),
          "epistemic_status has lost the availability/eligibility/admission clause")

    # -- 2. the universe is the one the program declares ------------------- #
    ru = d["row_universe"]
    check(ru["team_game_rows"] == 2982, f"team_game_rows={ru['team_game_rows']}, expected 2982")
    check(ru["game_clusters"] == 1491, f"game_clusters={ru['game_clusters']}, expected 1491")

    # -- 3. every cutoff is bound ------------------------------------------ #
    cd = d["cutoff_definition"]
    check(cd["universe_games_joined_to_a_cutoff"] == ru["game_clusters"],
          "not every universe game joined to a forecast_cutoff; an unbound cutoff makes every "
          "CUTOFF_VALID verdict in the file unsupported")

    # -- 4. field records are well formed ---------------------------------- #
    fams = set()
    for f in d["fields"]:
        name = f.get("field", "<unnamed>")
        for k in ("family", "field", "verdict", "evidence", "coverage", "structural_class"):
            check(k in f, f"{name}: missing key {k}")
        check(f["verdict"] in VERDICTS, f"{name}: verdict {f['verdict']!r} outside the vocabulary")
        check(isinstance(f.get("evidence"), str) and len(f["evidence"]) > 40,
              f"{name}: evidence is missing or too thin to audit")
        fams.add(f["family"])
    check(REQUIRED_FAMILIES <= fams,
          f"acceptance criteria name families not present: {sorted(REQUIRED_FAMILIES - fams)}")

    # -- 5. coverage arithmetic closes ------------------------------------- #
    n_rows = ru["team_game_rows"]
    for f in d["fields"]:
        name = f["field"]
        cov = f["coverage"]
        for label, c in cells(cov):
            check(CELL_KEYS <= set(c), f"{name}/{label}: malformed cell")
            check(0 <= c["covered"] <= c["rows"],
                  f"{name}/{label}: covered={c['covered']} outside [0, rows={c['rows']}]")
            check(0 <= c["cutoff_valid"] <= c["covered"],
                  f"{name}/{label}: cutoff_valid={c['cutoff_valid']} exceeds covered="
                  f"{c['covered']} — cutoff-validity is a strict subset of coverage")
            if c["rows"]:
                # rates are stored rounded to 6 dp, so the tolerance is half a unit in the last
                # stored place, not machine epsilon.
                check(abs(c["coverage"] - c["covered"] / c["rows"]) <= 5e-7,
                      f"{name}/{label}: coverage rate does not match its own counts")
                check(abs(c["cutoff_valid_rate"] - c["cutoff_valid"] / c["rows"]) <= 5e-7,
                      f"{name}/{label}: cutoff_valid_rate does not match its own counts")
        check(cov["overall"]["rows"] == n_rows,
              f"{name}: overall rows {cov['overall']['rows']} != universe {n_rows}")
        # the season partition must exhaust the universe
        s = sum(c["rows"] for c in cov["by_season"].values())
        check(s == n_rows, f"{name}: by_season rows sum to {s}, universe is {n_rows} — a "
                           "partition that does not exhaust the universe hides rows")
        s = sum(c["rows"] for c in cov["by_season_type"].values())
        check(s == n_rows, f"{name}: by_season_type rows sum to {s}, universe is {n_rows}")
        # every season's covered count must sum back to overall
        s = sum(c["covered"] for c in cov["by_season"].values())
        check(s == cov["overall"]["covered"],
              f"{name}: by_season covered sums to {s} but overall says "
              f"{cov['overall']['covered']}")
        s = sum(c["cutoff_valid"] for c in cov["by_season"].values())
        check(s == cov["overall"]["cutoff_valid"],
              f"{name}: by_season cutoff_valid sums to {s} but overall says "
              f"{cov['overall']['cutoff_valid']}")

    # -- 6. verdicts and numbers cannot contradict each other -------------- #
    for f in d["fields"]:
        name, v, cov = f["field"], f["verdict"], f["coverage"]
        if v in ("CUTOFF_UNPROVEN", "CUTOFF_INVALID", "ABSENT"):
            for label, c in cells(cov):
                check(c["cutoff_valid"] == 0,
                      f"{name}/{label}: verdict {v} but cutoff_valid={c['cutoff_valid']}. A field "
                      "with no proof of pre-cutoff observation may never carry a positive "
                      "cutoff-valid count")
        if v == "ABSENT":
            check(cov["overall"]["covered"] == 0,
                  f"{name}: verdict ABSENT but covered={cov['overall']['covered']}")
            check(f.get("source_timestamp_column") is None,
                  f"{name}: verdict ABSENT but a source timestamp column is named")
        if v == "CUTOFF_VALID":
            check(f.get("source_timestamp_column"),
                  f"{name}: verdict CUTOFF_VALID with no per-row source timestamp column named — "
                  "this is exactly the assumption the node forbids")
            check(cov["overall"]["cutoff_valid"] > 0,
                  f"{name}: verdict CUTOFF_VALID but zero rows actually clear the cutoff")

    # -- 7. the fold structure never splits a game cluster ----------------- #
    folds = d["fold_structure"]["folds"]
    check(len(folds) >= 1, "no folds declared")
    for fid, fo in folds.items():
        check(fo["train_rows"] > 0 and fo["test_rows"] > 0, f"{fid}: empty train or test side")
        check(fo["train_rows"] + fo["test_rows"] <= n_rows,
              f"{fid}: train+test exceeds the universe")
        check(fo["train_rows"] % 2 == 0 and fo["test_rows"] % 2 == 0,
              f"{fid}: an odd team-game count means a game cluster was split across the "
              "train/test boundary, which the program forbids")

    # -- 8. verdict_counts is consistent with the field list --------------- #
    tally: dict = {}
    for f in d["fields"]:
        tally[f["verdict"]] = tally.get(f["verdict"], 0) + 1
    check(tally == d["verdict_counts"],
          f"verdict_counts {d['verdict_counts']} disagrees with the field list {tally}")

    if FAILURES:
        print(f"FAIL — {len(FAILURES)} check(s)")
        for m in FAILURES:
            print("  -", m)
        return 1
    print(f"PASS — {len(d['fields'])} fields, {len(folds)} folds, "
          f"{n_rows} team-game rows / {ru['game_clusters']} clusters")
    print(f"       verdicts: {d['verdict_counts']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
