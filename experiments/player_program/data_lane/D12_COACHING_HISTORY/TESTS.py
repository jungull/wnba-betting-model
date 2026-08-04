"""
D12_COACHING_HISTORY -- tests.

These are not smoke tests. Each one enforces one of the node's three acceptance criteria
against the emitted bytes:

  AC1  every coaching record carries a source and an effective date
  AC2  the table is not admitted to an experiment before cutoff review
  AC3  ambiguous tenure boundaries are marked, not smoothed

plus an anti-fabrication test (T4): every emitted note is byte-identical to the source row it
claims to come from, which is what makes "retrospectively auditable" mean something.

pytest is not installed in this program. Run:  python TESTS.py   (returns 1 on failure)
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

NODE = Path(__file__).resolve().parent
REPO = NODE.parents[3]
SRC = REPO / "data" / "injury_history" / "injury_history.csv"

EPISTEMIC_STATUS = (
    "REFERENCE DATA. Auditable history only. Explicitly NOT admitted to any experiment "
    "before a cutoff review."
)
ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")

FAILURES: list[str] = []


def check(cond: bool, label: str, detail: str = "") -> None:
    if cond:
        print("  PASS  %s" % label)
    else:
        print("  FAIL  %s  %s" % (label, detail))
        FAILURES.append(label)


def main() -> int:
    ev = pd.read_csv(NODE / "coaching_events_v1.csv", keep_default_na=False)
    tn = pd.read_csv(NODE / "coaching_tenure_v1.csv", keep_default_na=False)
    cv = pd.read_csv(NODE / "team_season_coverage_v1.csv", keep_default_na=False)
    meas = json.loads((NODE / "MEASUREMENTS.json").read_text(encoding="utf-8"))

    print("T1  AC1 -- every event record carries a source and an effective date")
    for col in ("source_dataset", "source_page", "source_note_verbatim"):
        check(
            bool(len(ev)) and (ev[col].astype(str).str.len() > 0).all(),
            "every event row has non-empty %s" % col,
        )
    check(
        (ev["source_row_index"].astype(str).str.len() > 0).all(),
        "every event row has a source_row_index",
    )
    check(
        ev["event_date"].astype(str).map(lambda s: bool(ISO.match(s))).all(),
        "every event row has an ISO effective date",
    )
    check(
        (ev["effective_date_basis"] == "SOURCE_TRANSACTION_DATE").all(),
        "every event row declares the basis of its effective date",
    )

    print("T2  AC1 -- every tenure record is anchored to a source event or flagged as unsourced")
    unanchored = tn[
        (tn["start_event_id"].astype(str) == "")
        & (tn["end_event_id"].astype(str) == "")
        & (~tn["flags"].astype(str).str.contains("NO_COACHING_EVENT_FOR_FRANCHISE_IN_SOURCE"))
    ]
    check(len(unanchored) == 0, "no tenure row is unanchored and unflagged", unanchored.to_string())
    check(
        (tn["source_dataset"].astype(str).str.len() > 0).all(),
        "every tenure row names its source dataset",
    )

    print("T3  AC3 -- every undated boundary is explicitly marked, never smoothed")
    bad_start = tn[(tn["start_date"].astype(str) == "") & (tn["start_basis"] != "LEFT_CENSORED_UNKNOWN")]
    check(len(bad_start) == 0, "undated start => start_basis LEFT_CENSORED_UNKNOWN", bad_start.to_string())
    bad_end = tn[(tn["end_date"].astype(str) == "") & (tn["end_basis"] != "OPEN")]
    check(len(bad_end) == 0, "undated end => end_basis OPEN", bad_end.to_string())
    unflagged = tn[(tn["boundary_ambiguous"].astype(str).str.lower() == "true") & (tn["flags"].astype(str) == "")]
    check(len(unflagged) == 0, "no row is marked ambiguous with an empty flag list")
    # every row whose boundary is not dated at BOTH ends must be flagged ambiguous
    need = tn[
        (tn["start_basis"] != "EVENT_DATED_APPOINTMENT")
        | (~tn["end_basis"].astype(str).str.startswith("EVENT_DATED"))
    ]
    check(
        (need["boundary_ambiguous"].astype(str).str.lower() == "true").all(),
        "every partially-dated spell is marked boundary_ambiguous",
    )
    # an interim appointment is never carried into a later season as settled coverage
    carried_interim = cv[
        cv["coverage_status"].astype(str).str.startswith("NAMED")
        & cv["tenure_ids"].astype(str).isin(
            set(tn.loc[tn["is_interim"].astype(str).str.lower() == "true", "tenure_id"])
        )
        & (pd.to_numeric(cv["seasons_carried_forward"], errors="coerce").fillna(0) >= 1)
    ]
    check(
        len(carried_interim) == 0,
        "no interim spell is carried across a season boundary as NAMED coverage",
        carried_interim.to_string(),
    )

    print("T4  anti-fabrication -- every emitted note is byte-identical to its source row")
    src = pd.read_csv(SRC)
    mism = []
    for _, r in ev.iterrows():
        i = int(r["source_row_index"])
        if str(src.loc[i, "notes"]).strip() != str(r["source_note_verbatim"]).strip():
            mism.append(r["event_id"])
        if str(src.loc[i, "date"]) != str(r["event_date"]):
            mism.append(r["event_id"] + ":date")
        if str(src.loc[i, "source_page"]) != str(r["source_page"]):
            mism.append(r["event_id"] + ":page")
    check(len(mism) == 0, "all %d events round-trip to the source file" % len(ev), str(mism[:10]))
    check(
        int((ev["coach_name"] == "UNPARSED").sum()) == 0,
        "no event was emitted with an unparsed coach name",
    )
    # no coach name may appear that is not a substring of its own source note
    ghosts = [
        r["event_id"]
        for _, r in ev.iterrows()
        if r["coach_name"] not in str(r["source_note_verbatim"])
    ]
    check(len(ghosts) == 0, "every coach name is a literal substring of its source note", str(ghosts))

    print("T5  AC2 -- nothing here is admitted to an experiment")
    for name, df in (("events", ev), ("tenure", tn), ("coverage", cv)):
        check((df["admission_status"] == "NOT_ADMITTED").all(), "%s: admission_status NOT_ADMITTED" % name)
        check((df["cutoff_status"] == "CUTOFF_UNPROVEN").all(), "%s: cutoff_status CUTOFF_UNPROVEN" % name)
    fnd = json.loads((NODE / "FINDINGS.json").read_text(encoding="utf-8"))
    check(fnd.get("epistemic_status") == EPISTEMIC_STATUS, "FINDINGS.json carries the epistemic status verbatim")
    check(
        EPISTEMIC_STATUS in (NODE / "REPORT.md").read_text(encoding="utf-8"),
        "REPORT.md carries the epistemic status verbatim",
    )
    check(
        fnd.get("admission", {}).get("admitted_to_any_experiment") is False,
        "FINDINGS.json declares the table not admitted",
    )

    print("T6  universe reconciliation -- coverage accounts for every team-game, no more, no less")
    check(len(cv) == 76, "coverage has 76 team-seasons, got %d" % len(cv))
    check(
        int(cv["team_games"].sum()) == 2982,
        "coverage team_games sum == 2982 canonical rows, got %d" % int(cv["team_games"].sum()),
    )
    check(
        meas["measurements"]["universe_game_clusters"] == 1491,
        "universe game clusters == 1491",
    )
    check(
        int(cv["coverage_status"].str.startswith("UNKNOWN").sum())
        + int(cv["coverage_status"].str.startswith("NAMED").sum())
        + int((cv["coverage_status"] == "AMBIGUOUS_MULTIPLE_SPELLS").sum())
        == len(cv),
        "every team-season carries a coverage status",
    )

    print()
    if FAILURES:
        print("FAILED %d check(s): %s" % (len(FAILURES), FAILURES))
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
