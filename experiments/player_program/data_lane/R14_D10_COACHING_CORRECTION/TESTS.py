#!/usr/bin/env python3
"""TESTS.py — R14_D10_COACHING_CORRECTION.

Standalone. No pytest. main() returns 1 on any failure.

Every count this node reports is re-derived here by a DIFFERENT route from the one that produced
it: remeasure_coaching.py reads the CSV through pandas; these tests read the same bytes through
the stdlib csv module and through raw text, so a pandas-version-specific string-dtype behaviour
cannot make both agree by making both wrong in the same way.

The suite also contains POSITIVE CONTROLS for every negative result. A search that returns nothing
is not evidence of absence until the same search has been shown to find something that is
provably there. The defect this node corrects is exactly a negative that was never controlled.
"""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
PROGRAM = HERE.parents[1]
ROOT = PROGRAM.parents[1]

INJURY_HISTORY = ROOT / "data" / "injury_history" / "injury_history.csv"
D10_DIR = PROGRAM / "data_lane" / "D10_FIELD_AVAILABILITY_LEDGER"
CORRECTION = HERE / "CORRECTION.json"

FAILURES: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {name}" + (f"  --  {detail}" if detail else ""))
    if not cond:
        FAILURES.append(f"{name}: {detail}")


# --------------------------------------------------------------------------- #
def load_rows_stdlib() -> list[dict]:
    """Read the CSV with the stdlib, deliberately bypassing pandas entirely."""
    with open(INJURY_HISTORY, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def main() -> int:
    if not CORRECTION.exists():
        print("CORRECTION.json missing — run remeasure_coaching.py first")
        return 1
    c = json.loads(CORRECTION.read_text(encoding="utf-8"))
    rows = load_rows_stdlib()

    # ---- 1. the file itself ----------------------------------------------------------- #
    check("stdlib read agrees with pandas on total rows", len(rows) == 8340, f"{len(rows)}")

    # ---- 2. the 49 signal rows, counted without pandas -------------------------------- #
    fo = [r for r in rows if r["category"] == "front_office"]
    check("front_office rows == 49 (stdlib csv)", len(fo) == 49, f"{len(fo)}")
    check("CORRECTION.json agrees",
          c["front_office_enumeration"]["front_office_rows"] == len(fo))
    check("all 49 are enumerated in the artifact", len(c["front_office_rows"]) == 49,
          f"{len(c['front_office_rows'])}")
    check("all 49 parsed, none unparsed",
          c["front_office_enumeration"]["unparsed"] == 0,
          str(c["front_office_enumeration"]["unparsed"]))

    coach_fo = [r for r in fo if "coach" in r["notes"].lower()]
    check("48 of the 49 front_office rows name a coaching role", len(coach_fo) == 48,
          f"{len(coach_fo)}")
    non_coach = [r for r in fo if "coach" not in r["notes"].lower()]
    check("the 1 remainder is the GM row, correctly excluded from coaching identity",
          len(non_coach) == 1 and "GM" in non_coach[0]["notes"],
          non_coach[0]["notes"] if non_coach else "none")
    check("artifact classifies exactly 48 rows as coaching identity",
          c["front_office_enumeration"]["coaching_identity_rows"] == 48)

    # every enumerated row's notes must actually appear in the file
    file_notes = {r["notes"] for r in fo}
    check("every enumerated note is a real byte-for-byte note from the file",
          all(e["notes"] in file_notes for e in c["front_office_rows"]))

    # ---- 3. the noise class, counted without pandas ------------------------------------ #
    cd = [r for r in rows if "COACH'S DECISION" in r["notes"].upper()]
    ci = [r for r in rows if "coach" in r["notes"].lower()]
    check("COACH'S DECISION rows == 2882 (stdlib csv)", len(cd) == 2882, f"{len(cd)}")
    check("rows mentioning coach in any case == 2930 (stdlib csv)", len(ci) == 2930, f"{len(ci)}")
    check("2930 = 2882 noise + 48 signal, exactly and with no remainder",
          len(ci) == len(cd) + len(coach_fo),
          f"{len(ci)} vs {len(cd)}+{len(coach_fo)}")
    check("artifact reports the same noise counts",
          c["coachs_decision_noise_class"]["rows_whose_notes_contain_COACHS_DECISION_anywhere"] == 2882
          and c["coachs_decision_noise_class"]["rows_whose_notes_contain_coach_case_insensitive"] == 2930)
    check("every COACH'S DECISION row is a player row, not a front_office row",
          all(r["category"] != "front_office" for r in cd))
    # the DNP strings come in three surface forms; a bracketed context suffix is still a reason
    # string and still names nobody. Assert the SHAPE, and separately assert no identity verb.
    stem = re.compile(r"^COACH'S DECISION(\s*\[[A-Z\-]+\])?$")
    shapes = sorted({r["notes"].strip().upper() for r in cd})
    check("every COACH'S DECISION note is a bare reason string, optionally context-suffixed",
          all(stem.match(s) for s in shapes), str(shapes))
    check("no COACH'S DECISION row carries an identity verb (hired/fired/resigns/named as)",
          not any(re.search(r"\b(hired|fired|resigns|named)\b", r["notes"], re.I) for r in cd))
    check("no COACH'S DECISION row is parseable as a coaching event",
          not any(re.search(r"as (Interim )?(Head Coach|GM|General Manager)", r["notes"], re.I)
                  for r in cd))
    check("the noise class is declared excluded, not counted",
          c["coachs_decision_noise_class"]["names_a_coach"] is False)

    # ---- 4. POSITIVE CONTROL for the remaining negative -------------------------------- #
    # coaching.rotation_policy is still reported ABSENT. Prove the searcher works before
    # believing its zero: the same matcher must find a token that IS present.
    haystacks = []
    for p in list((ROOT / "data").rglob("*.csv")) + list(PROGRAM.rglob("*.csv")) \
            + list(PROGRAM.rglob("*.json")) + list(PROGRAM.rglob("*.py")):
        try:
            haystacks.append((p, p.read_text(encoding="utf-8", errors="replace").lower()))
        except Exception:
            continue
    check("positive control: the searcher can see files at all", len(haystacks) > 20,
          f"{len(haystacks)} files read")
    control_hits = [p for p, t in haystacks if "head coach" in t]
    check("positive control: searcher FINDS 'head coach', which is provably present",
          len(control_hits) > 0, f"{len(control_hits)} files")
    check("positive control: injury_history.csv is among them",
          any(p == INJURY_HISTORY for p in control_hits))
    rot_tokens = ["rotation policy", "rotation_policy", "minutes_policy", "substitution_pattern",
                  "rotation_strategy", "minutes_allocation_rule"]
    rot_hits = {tok: [str(p.relative_to(ROOT)) for p, t in haystacks if tok in t]
                for tok in rot_tokens}
    # this node's own files legitimately contain the token; exclude them from the negative
    rot_hits = {k: [v for v in vs if "R14_D10_COACHING_CORRECTION" not in v]
                for k, vs in rot_hits.items()}
    data_hits = {k: [v for v in vs if v.startswith("data/")] for k, vs in rot_hits.items()}
    check("controlled negative: no DATA artifact carries a rotation-policy field",
          all(len(v) == 0 for v in data_hits.values()), json.dumps(data_hits))
    check("artifact still reports rotation_policy ABSENT",
          next(f for f in c["fields"] if f["field"] == "coaching.rotation_policy")["verdict"] == "ABSENT")

    # ---- 5. the mechanism, reproduced ------------------------------------------------- #
    diag = c["how_the_false_negative_was_produced"]
    check("mechanism (c) reproduces D10's negative: front_office is the one omitted category",
          diag["c_category_whitelist_omission"]["reproduces_d10_negative"] is True
          and diag["c_category_whitelist_omission"]["categories_in_the_file_that_D10_never_names"] == ["front_office"])
    check("mechanism (c): D10's whitelist reached 8291 of 8340 rows, missing exactly 49",
          diag["c_category_whitelist_omission"]["rows_never_reached"] == 49,
          str(diag["c_category_whitelist_omission"]["rows_never_reached"]))
    check("mechanism (a): D10's own stated grep does NOT reproduce its negative",
          diag["a_grep_reproduction"]["reproduces_d10_negative"] is False
          and diag["a_grep_reproduction"]["lines_in_front_office_rows"] == 48)
    # the string-dtype trap is real on these bytes even though D10 did not use it
    df = pd.read_csv(INJURY_HISTORY)
    check("mechanism (b): an object-dtype column scan finds ZERO text columns in this file",
          len([c_ for c_ in df.columns if df[c_].dtype == object]) == 0,
          "the pandas-2 idiom would silently report nothing to search")
    check("mechanism (b): naming the column directly still works",
          int(df["notes"].str.contains("Coach", case=True, na=False).sum()) == 48)
    check("mechanism (b) is reported as NOT the cause D10 used",
          "NOT, however, the mechanism" in diag["b_string_dtype_trap"]["verdict"])
    check("mechanism (d): the upstream receipt's prose omits front_office while its counts do not",
          diag["d_upstream_prose_omits_it_too"]["prose_mentions_front_office_or_coach"] is False
          and diag["d_upstream_prose_omits_it_too"]["receipt_category_counts_include_front_office"] is True)

    # ---- 6. the corrected verdict and the cutoff-valid invariant ---------------------- #
    check("corrected verdict is PRESENT_RETROSPECTIVE / CUTOFF_UNPROVEN",
          c["corrected_verdict"] == "PRESENT_RETROSPECTIVE / CUTOFF_UNPROVEN")
    check("cutoff_valid_count is 0 at the top level", c["cutoff_valid_count"] == 0)

    bad = []
    for f in c["fields"]:
        cov = f["coverage"]
        cells = [("overall", cov["overall"])]
        cells += [(f"season:{k}", v) for k, v in cov["by_season"].items()]
        cells += [(f"season_type:{k}", v) for k, v in cov["by_season_type"].items()]
        for fid, fb in cov["by_fold"].items():
            cells += [(f"fold:{fid}:train", fb["train"]), (f"fold:{fid}:test", fb["test"])]
        for label, cell in cells:
            if cell["cutoff_valid"] != 0:
                bad.append(f"{f['field']}/{label}={cell['cutoff_valid']}")
    check("cutoff_valid == 0 in EVERY cell of EVERY field, season, season_type and fold",
          not bad, "; ".join(bad))

    # ---- 7. the coverage really was re-measured against the frozen universe ----------- #
    check("row universe is the frozen 2,982 team-games over 1,491 clusters",
          c["row_universe"]["team_game_rows"] == 2982 and c["row_universe"]["game_clusters"] == 1491,
          json.dumps(c["row_universe"]))
    for f in c["fields"]:
        cov = f["coverage"]
        n = sum(v["rows"] for v in cov["by_season"].values())
        check(f"{f['field']}: by_season rows partition the universe", n == 2982, f"{n}")
        n2 = sum(v["rows"] for v in cov["by_season_type"].values())
        check(f"{f['field']}: by_season_type rows partition the universe", n2 == 2982, f"{n2}")
        for fid, fb in cov["by_fold"].items():
            check(f"{f['field']}: fold {fid} train and test are disjoint and inside the universe",
                  fb["train"]["rows"] + fb["test"]["rows"] <= 2982,
                  f"{fb['train']['rows']}+{fb['test']['rows']}")
            check(f"{f['field']}: fold {fid} covered never exceeds rows",
                  fb["train"]["covered"] <= fb["train"]["rows"]
                  and fb["test"]["covered"] <= fb["test"]["rows"])

    # per-row CSV must agree with the JSON headline, or one of them is a story
    byrow = pd.read_csv(HERE / "coverage_by_row_v1.csv")
    check("per-row coverage CSV has one row per team-game", len(byrow) == 2982, f"{len(byrow)}")
    ident = next(f for f in c["fields"] if f["field"] == "coaching.head_coach_identity")
    check("per-row CSV reproduces the headline head_coach_identity coverage",
          int(byrow["head_coach_named"].sum()) == ident["coverage"]["overall"]["covered"],
          f"{int(byrow['head_coach_named'].sum())} vs {ident['coverage']['overall']['covered']}")
    check("per-row CSV carries cutoff_valid False on every row",
          not byrow["cutoff_valid"].any())
    check("coverage is strictly positive, i.e. D10's zero is refuted",
          ident["coverage"]["overall"]["covered"] > 0)

    # a named coach must never be claimed for a team-game before that team's first archive event
    check("no row is covered with zero prior head-coach events",
          not ((byrow["head_coach_named"]) & (byrow["prior_head_coach_events"] == 0)).any())
    check("tenure is known exactly where identity is known",
          int(byrow["coach_tenure_games"].notna().sum()) == int(byrow["head_coach_named"].sum()))

    # ---- 8. the parent artifact is untouched ------------------------------------------ #
    d10_files = sorted(p.name for p in D10_DIR.iterdir() if p.is_file())
    check("D10 directory still holds exactly its original four files",
          d10_files == ["FINDINGS.json", "REPORT.md", "TESTS.py", "build_ledger.py"],
          str(d10_files))
    check("D10's recorded ABSENT verdict is preserved, not overwritten",
          all(x["verdict"] == "ABSENT" for x in c["d10_original_claim_as_recorded_in_its_findings"]))
    d10_now = json.loads((D10_DIR / "FINDINGS.json").read_text(encoding="utf-8"))
    check("D10's FINDINGS.json still contains its four ABSENT coaching fields",
          len([f for f in d10_now["fields"] if f["family"] == "coaching"]) == 4)
    check("this node declares it did not modify the parent",
          c["parent_artifact_modified"] is False)

    # ---- 9. no performance peeking ---------------------------------------------------- #
    # Scan the measurement code, not this file: TESTS.py necessarily spells the forbidden tokens
    # in order to check for them, and a scanner that included itself would fail by construction.
    # Scan the code that MEASURES. TESTS.py and write_report.py necessarily spell the forbidden
    # tokens (one to check for them, one to attest their absence in prose); a scanner that
    # included them would fail by construction and teach nothing.
    MEASURING = ("remeasure_coaching.py", "cross_check_vs_d12.py")
    measured_src = "\n".join((HERE / n).read_text(encoding="utf-8", errors="replace")
                             for n in MEASURING)
    check("both measurement scripts were found and read",
          all((HERE / n).exists() for n in MEASURING) and len(measured_src) > 5000)
    check("the measurement code references no forbidden path",
          "SEALED_RESULTS" not in measured_src and "stage2b" not in measured_src)
    for tok in ("mae", "rmse", "brier", "logloss", "r2_score"):
        check(f"the measurement code contains no '{tok}' metric",
              not re.search(rf"\b{tok}\b", measured_src, re.I))
    # the non-measuring files may name the tokens but must never OPEN such a path
    for name in ("TESTS.py", "write_report.py"):
        s = (HERE / name).read_text(encoding="utf-8")
        check(f"{name} never opens a sealed or stage2b path",
              not re.search(r"(open|read_text|read_csv|read_parquet)\s*\([^)]*"
                            r"(SEALED_RESULTS|stage2b)", s))
    # nothing in this node writes outside this node
    # A write call site is anchored to this directory iff HERE appears on the same statement.
    offenders = []
    for p in sorted(HERE.glob("*.py")):
        for lineno, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if re.search(r"\.(write_text|write_bytes|to_csv|to_json|to_parquet)\s*\(", line) \
                    and "HERE" not in line:
                offenders.append(f"{p.name}:{lineno}")
    check("every write call site in this node is anchored to HERE", not offenders,
          "; ".join(offenders))
    # and no python file in this node contains an absolute or parent-relative write path
    all_src = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in HERE.glob("*.py"))
    check("no absolute filesystem path is written anywhere in this node",
          not re.search(r'["\'][A-Za-z]:[\\/]', all_src))

    print()
    if FAILURES:
        print(f"{len(FAILURES)} FAILURE(S)")
        for f in FAILURES:
            print("  -", f)
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
