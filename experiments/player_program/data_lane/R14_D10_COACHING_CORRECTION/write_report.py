#!/usr/bin/env python3
"""write_report.py — emits REPORT.md for R14_D10_COACHING_CORRECTION.

The prose is fixed; every number in it is re-read from CORRECTION.json and asserted before the
file is written. If a measurement changes and the prose does not, this script fails loudly rather
than shipping a report that disagrees with the artifact it describes.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

REPORT = r"""# R14_D10_COACHING_CORRECTION — correcting D10's manufactured negative on the coaching family

## Epistemic status

> REMEDIATION of a confirmed FALSE NEGATIVE. D10 reported the coaching family ABSENT with 0
> coverage on an assertion contradicted by the bytes of a file it had itself loaded. This node
> RE-MEASURES; it may not simply restate D12's numbers, because relaying an unverified figure is
> the failure mode that produced the defect.

D10's ledger is **not edited**. Its four ABSENT rows stand in
`data_lane/D10_FIELD_AVAILABILITY_LEDGER/FINDINGS.json` with the failure on the record. This
correction is a separate artifact and says so in its own bytes
(`parent_artifact_modified: false`, verified by TESTS.py section 8).

---

## 1. The claim being corrected

`D10_FIELD_AVAILABILITY_LEDGER/REPORT.md` section 4.8, "Coaching — nothing exists":

> All four fields (`head_coach_identity`, `coach_tenure_games`, `coach_change_flag`,
> `rotation_policy`) are **ABSENT**, coverage 0 in every season and every fold.

and its supporting evidence string, recorded verbatim in `FINDINGS.json` for all four fields:

> exhaustive search of the worktree for a coaching source found NOTHING. `grep -rn -i coach` over
> features/, data/ and experiments/player_program/ returns only (a) free-text "Coach's Decision"
> reason strings inside injury_log.csv, which name no coach, and (b) two orchestration prompt
> filenames.

Three of those four verdicts are wrong. The fourth (`rotation_policy`) survives.

---

## 2. What is actually in the file

`data/injury_history/injury_history.csv`
(sha256 `6aec435c94af3da10adc793c9978afbe33749cdff8f97a194939db564ed2f33b`, 8,340 rows, 916,886
bytes) carries **49 rows in category `front_office`**. All 49 are enumerated in
`CORRECTION.json -> front_office_rows` and in `front_office_rows_v1.csv`, one record per row, with
the raw note preserved.

Produced by `remeasure_coaching.py`; independently re-derived in `TESTS.py` through the **stdlib
`csv` module**, deliberately bypassing pandas so that a pandas-version-specific string behaviour
cannot make both routes wrong in the same direction.

| measurement | value |
|---|---|
| `front_office` rows | **49** |
| parsed by the event grammar | 49 (0 unparsed) |
| rows naming a coaching role | **48** |
| rows naming a non-coaching role | **1** — `James Wade resigns as GM for Chicago Sky.` |
| actions | hire 29, fire 11, resign 9 |
| roles | head coach 41, interim head coach 7, general manager 1 |
| distinct named people | 34 |
| event date range | 2021-05-03 to 2025-12-03 |
| franchises with at least one event | 14 of 15 (all but MIN) |
| franchises unmappable to `master_team` | 0 |

The very first two matches of the grep D10 says it ran are:

```
data/injury_history/injury_history.csv:255:2021-05-03,ATL,,,Nicki Collen resigns as Head Coach for Atlanta Dream.,front_office,...
data/injury_history/injury_history.csv:256:2021-05-03,ATL,,,The Atlanta Dream hired Mike Peterson as Interim Head Coach.,front_office,...
```

These name a coach. The command D10 cites as its evidence of absence refutes D10 on its first two
lines of output. That is not an inference — `diagnose_false_negative()` re-runs the command as a
subprocess and records the return code, the line count and the first two matches into
`CORRECTION.json`.

`scrape_injury_history.py:400-402` shows the category was created on purpose: any transaction note
matching `head coach | general manager | hired | resigns | fired | named | coach` is emitted as
`front_office`. The coaching data was captured deliberately, not incidentally.

---

## 3. The 2,882 COACH'S DECISION rows are noise and are excluded

The one true thing in D10's evidence string is that the file is dominated by DNP reason strings.
Measured:

| measurement | value |
|---|---|
| rows whose `notes` contain "coach", any case | **2,930** |
| rows whose `notes` contain `COACH'S DECISION` | **2,882** |
| surface forms | `COACH'S DECISION` 2,526 / `COACH'S DECISION [playoffs]` 341 / `COACH'S DECISION [commissioners-cup-final]` 15 |
| category of every one of them | `missed_game_other` (2,882 of 2,882) |
| `front_office` rows whose note contains "coach" | 48 |
| arithmetic | 2,930 = 2,882 + 48, exact, no remainder |

These 2,882 rows are **excluded from the coaching family** and are not counted as coaching
identity anywhere in this correction. They are an ESPN did-not-play *reason* on a *player* row.
They name no coach, carry no identity, no tenure and no change event, and they are already
measured by D10 as `injury.missed_game_other_wire`. Counting them as coaching data would inflate
the family to 2,882 rows of noise and bury the 49 rows that carry signal — the mirror image of
the error being corrected.

TESTS.py asserts this structurally rather than by eyeball: every one of the 2,882 matches the bare
reason-string shape with an optional bracketed context suffix; none contains an identity verb
(`hired|fired|resigns|named`); none is parseable as a coaching event; none is in `front_office`.

The acceptance criterion for this node reads "the ~2,930 COACH'S DECISION rows". **That figure is
slightly off and I am not going to restate it.** 2,930 is the count of rows mentioning "coach" in
any case; 2,882 is the count of COACH'S DECISION rows. The 48-row difference is exactly the
coaching signal. Both numbers are in `CORRECTION.json`.

---

## 4. How the false negative was produced

Four candidate mechanisms were tested against the actual bytes. Two reproduce something, two do
not, and the artifact records which is which rather than picking the most rhetorically satisfying.

**(a) The grep D10 cites — does NOT reproduce the negative.**
`grep -rn -i coach data/injury_history/` returns 2,930 lines, 48 of them inside `front_office`
rows, the first two of them at the very top of the output. Re-run as a subprocess; `returncode 0`,
`reproduces_d10_negative: false`. D10's stated evidence does not support D10's stated conclusion.
D10 attributed the hits to `injury_log.csv` — that file exists and has 74 coach-mentioning lines,
and it sorts alphabetically *before* `injury_history.csv` in a recursive walk of `data/`. The
plausible reading is that D10 recognised the first file, recognised the DNP noise class, and
stopped.

**(c) The mechanism that DOES reproduce it — a hardcoded category whitelist.**
`build_ledger.py:572` loads the file. It then subsets it three times, by literal category sets:

```
line 581  ("missed_game_injury", ...), ("missed_game_other", ...)
line 603  ACQ = {"signing", "trade", "draft", "waiver_claim", "contract_conversion"}
line 604  REL = {"waiver", "retirement", "contract_suspension"}
```

The file contains **eleven** categories. That union names **ten**. The omitted one is
`front_office`, and `front_office` is exactly where head-coach identity lives. Measured: D10's
whitelist reaches 8,291 of 8,340 rows; the 49 rows it never touches are precisely the 49 coaching
rows. `reproduces_d10_negative: true`.

D10 never ran `category.value_counts()`. It enumerated a list it brought with it, and the list was
short by one. Having the file in memory is not the same as having looked at it.

**(d) Where the short list came from — an upstream document/bytes contradiction.**
`experiments/player_program/ROSTER_SOURCE_AUDIT_RECEIPT.json` describes this source in prose as

> "the Basketball-Reference WNBA transaction wire ... signings, trades, drafts, waivers, waiver
> claims, contract conversions and suspensions, plus per-game ESPN did-not-play rows"

— ten categories, `front_office` absent, "coach" never mentioned. The *same file*, a few lines
earlier, carries the machine-readable category counts including `"front_office": 49`. D10's three
category sets are that prose, transliterated. **This is a contradiction between a document and the
bytes inside one artifact, and per standing rule 1 it is reported, not reconciled.** The receipt is
not in this node's write scope and has not been touched.

**(b) A real trap that is NOT what happened here, recorded anyway.**
On these exact bytes under pandas 3.0.5, every text column reads as `StringDtype`, not `object`.
Consequently:

```
[c for c in df.columns if df[c].dtype == object]             -> []
[c for c in df.columns if pd.api.types.is_object_dtype(...)] -> []
[c for c in df.columns if pd.api.types.is_string_dtype(...)] -> all 7
df["notes"].str.contains("Coach")                            -> 48
```

The idiomatic pandas-2 way of locating text columns to search finds **zero columns** in a file that
is almost entirely text, and reports nothing to search without raising. That is a live silent
false-negative mechanism on this data. It is **not** D10's mechanism — `build_ledger.py` contains
no dtype-based column scan — and the artifact says so explicitly rather than letting a plausible
story stand in for the measured one.

Guarding against exactly this class of error, this node's own tests use **positive controls**: the
searcher is first shown to find `head coach`, a string provably present in 15 files including
`injury_history.csv`, before any of its zeroes are believed.

---

## 5. Re-measured coverage

Measured against the frozen possession universe — **2,982 team-game rows over 1,491 game
clusters**, `row_universe_digest raw_index_membership:n=2982:sha256=61f69db015f3270c7f0fd182a92e0371`
— rebuilt in this node from `possession_features.load_universe()`, with per-row
`forecast_cutoff` joined from `experiments/prediction_contract_v4/game.parquet` and folds from
`possession_features.chronological_folds()`. **No file under `data_lane/D12_COACHING_HISTORY` is
read by `remeasure_coaching.py`.**

`coaching.head_coach_identity` is COVERED for a row iff the 49-row archive names a specific head
coach for that team strictly before that row's `game_date`, via a hire event the archive actually
contains, with no intervening departure. No carry-back, no left-censored inference, no stale name
carried past a firing, no ambiguity admitted. A team whose coach was appointed before the archive
window opens (2021-05-03) has no hire event and is **not** covered.

| field | D10 | corrected verdict | covered / 2,982 | coverage | cutoff_valid |
|---|---|---|---|---|---|
| `coaching.head_coach_identity` | ABSENT, 0 | PRESENT_RETROSPECTIVE / CUTOFF_UNPROVEN | 2,101 | 0.7046 | **0** |
| `coaching.head_coach_event_present` | (not in D10) | PRESENT_RETROSPECTIVE / CUTOFF_UNPROVEN | 2,213 | 0.7421 | **0** |
| `coaching.coach_tenure_games` | ABSENT, 0 | PRESENT_RETROSPECTIVE / CUTOFF_UNPROVEN | 2,101 | 0.7046 | **0** |
| `coaching.coach_change_flag` | ABSENT, 0 | PRESENT_RETROSPECTIVE / CUTOFF_UNPROVEN | 218 | 0.0731 | **0** |
| `coaching.rotation_policy` | ABSENT, 0 | **ABSENT** (survives) | 0 | 0.0 | 0 |

Game clusters with a named coach: 1,260 of 1,491.

### By season — `coaching.head_coach_identity`

| season | rows | covered | coverage | cutoff_valid | franchises with no name all season |
|---|---|---|---|---|---|
| 2021 | 410 | 58 | 0.1415 | 0 | 10 |
| 2022 | 478 | 206 | 0.4310 | 0 | 6 |
| 2023 | 520 | 435 | 0.8365 | 0 | 2 |
| 2024 | 524 | 432 | 0.8244 | 0 | 2 |
| 2025 | 620 | 570 | 0.9194 | 0 | 1 |
| 2026 | 430 | 400 | 0.9302 | 0 | 1 |

The monotone rise is the archive filling in: the window opens 2021-05-03, so early seasons are
dominated by incumbents the archive never saw hired. By season type: Regular Season 1,970/2,770
(0.7112), Playoffs 131/212 (0.6179).

### By fold — `coaching.head_coach_identity`

| fold | test season | train rows | train covered | train cov | test rows | test covered | test cov |
|---|---|---|---|---|---|---|---|
| train_lt_2022 | 2022 | 410 | 58 | 0.1415 | 478 | 206 | 0.4310 |
| train_lt_2023 | 2023 | 888 | 264 | 0.2973 | 520 | 435 | 0.8365 |
| train_lt_2024 | 2024 | 1,408 | 699 | 0.4964 | 524 | 432 | 0.8244 |
| train_lt_2025 | 2025 | 1,932 | 1,131 | 0.5854 | 620 | 570 | 0.9194 |
| train_lt_2026 | 2026 | 2,552 | 1,701 | 0.6665 | 430 | 400 | 0.9302 |

`cutoff_valid` is 0 in every train cell and every test cell of every fold, for every field.
TESTS.py enumerates all 5 fields x (1 overall + 6 seasons + 2 season types + 5 folds x 2) cells
and asserts it.

### The other fields

`coaching.coach_change_flag` (at least one head-coach event dated inside the row's own season year
and strictly before the game) is covered for 218 rows, all in 2021-2023; **2024, 2025 and 2026 are
0.0** because every head-coach event in those years is dated between September and December —
after the last game of the season. Max in-season prior events for a single row: 3. A row that is
not covered is a row where the archive records no dateable in-season change; that is an
unobserved negative, not a measured "no change", because the archive's completeness for a season
cannot be established from the bytes.

`coaching.coach_tenure_games` (games since appointment, countable against the universe) coincides
exactly with `head_coach_identity` here — every named coach in this archive is named *by* a hire
event carrying its own date — range 0 to 224 games. It is reported as a separate field so the
coincidence is not silently assumed for some future source where identity and tenure would come
apart.

`coaching.head_coach_event_present` is the weak measure (this team has at least one head-coach
event ever earlier), reported so the 112-row gap between "the family exists for this team" and
"the field resolves for this row" — rows whose only prior event is a firing — is visible rather
than collapsed.

---

## 6. Presence is not cutoff validity. cutoff_valid stays 0.

The corrected verdict is **PRESENT_RETROSPECTIVE / CUTOFF_UNPROVEN**. The family exists. It is
not admissible, and nothing here admits anything.

`injury_history.csv` carries an EFFECTIVE date and nothing else — measured: no capture,
publication or observation column exists in its seven columns. Its observation time is a single
retrospective moment for all 8,340 rows, recovered from git history (commit `98271bb`,
2026-07-30 13:42 -0400) via `ROSTER_SOURCE_AUDIT_RECEIPT.json`, not from the artifact. A coaching
change effective 2022-05-25 is a true fact about 2022-05-25, and such moves are in practice
reported the same day — but plausibility is not a timestamp.

**The boundary was measured, not waved past.** Ten universe rows (five games, 2026-07-29 to
2026-07-31) have a `forecast_cutoff` on or after the archive's observation date, and all ten have
a named head coach. Eight of them have a cutoff on or after the recovered commit *timestamp*
(2026-07-30 17:42 UTC). A weaker rule — "the archive file existed before this row's cutoff" —
would therefore score 8 rows valid. **This node does not apply that rule and records 0**, for
three reasons that are themselves measured:

1. the ordering is unverifiable from the artifact: the observation moment is not in the bytes, so
   no gate that reads only the bytes can check it;
2. only one snapshot was ever taken and Basketball-Reference edits transaction pages in place, so
   today's bytes cannot be shown to equal the bytes that stood at that moment;
3. cutoff validity in the D10 ledger is a per-row property backed by a per-row timestamp, and a
   single file-level commit time is not one.

This is recorded in `CORRECTION.json -> cutoff_validity.boundary_case_examined` so a later reader
can see the boundary was examined and rejected on stated grounds. **Correcting ABSENT to PRESENT
moves the presence column and nothing else.** The cutoff-valid feature set is unchanged.

---

## 7. Cross-check against D12 — a check, not a source

Run after the fact by `cross_check_vs_d12.py`, which feeds nothing in `CORRECTION.json`. If it
were deleted every number above would be unchanged.

**Source-level counts: full agreement, ten of ten.** Two independently written scripts reading the
same bytes both get 49 `front_office`, 2,930 coach-any-case, 2,882 DNP, 48 coaching-identity rows,
1 non-coaching remainder, 34 distinct people, 29 hires, 19 coaching departures, 7 interim, and the
identical 2021-05-03 to 2025-12-03 range. That is meaningful agreement precisely because neither
number was copied.

**Universe: identical, and a trap for readers.** D12's `MEASUREMENTS.json` headlines
`all_rows_in_file: 2990 / 1495 games`. That is the *pre-filter* parquet. After D12's own
`pace_resolved == True` filter its working universe is 2,982 rows over 1,491 clusters — set-equal
to the frozen universe, 0 rows on either side of the symmetric difference. **A reader who takes
2,990 as D12's denominator will compute wrong rates.** Reported as a contradiction between a
document's headline and its own working set.

**Coverage: differs by 124 team-games, definitionally.** D12's `NAMED_*` statuses sum to 2,225
team-games against this node's 2,101. D12 answers a *team-season* question about the season's
opening coach and applies one status to all of that team-season's games; it admits
`NAMED_START_LEFT_CENSORED` (inferring a 2021 incumbent backwards from a later firing) and
`NAMED_OPEN_END_CARRIED_FORWARD_UNVERIFIED` (carrying a name past the last event), neither of
which this node counts. This node answers a *row-level* question at each game date and admits
neither. Neither number is wrong; they are **not interchangeable**, and the D10 ledger must carry
the row-level one because the ledger's unit is the team-game. D12 reaches CUTOFF_UNPROVEN /
NOT_ADMITTED independently, agreeing with this node.

---

## 8. What I could not establish

- **Whether the archive is complete for coaching changes.** 14 franchises have at least one event;
  MIN has none. Whether that means Minnesota had no coaching change in 2021-2026 or that
  Basketball-Reference did not log one cannot be determined from the bytes. Every "not covered"
  row is an *unobserved* negative, never a measured "no change".
- **Whether the 2021 incumbents are recoverable.** 10 of 15 franchises have no name at all in
  2021. D12 fills some of these by inferring backwards from later firings; that inference is not
  checkable against this archive and is not adopted here.
- **Whether the raw HTML would carry a fetch timestamp.** `bbref_transactions_*.html` is
  gitignored and absent from the worktree; 0 raw source pages are resident. The
  single-observation-time finding therefore cannot be tightened.
- **Why D10 attributed the hits to `injury_log.csv`.** Mechanism (c) explains the *measurement*
  failure conclusively. Whether the prose was written from a truncated grep, from the receipt's
  prose, or from both is not determinable from artifacts.
- **Whether MIN's absence is an entity-resolution failure.** 0 of 49 rows failed to map to
  `master_team`, so it is not a mapping bug in what is present; whether an unlogged MIN event
  exists upstream is outside these bytes.

---

## 9. Stop conditions

**None tripped.** Explicitly:

- The primary target, `REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS`, is untouched.
- The K0 structure, the inference structure and the candidate universe are untouched.
- **The cutoff-valid feature set is unchanged.** Every field in this correction is
  CUTOFF_UNPROVEN or ABSENT with `cutoff_valid = 0`; nothing becomes admissible.
- Leakage status is unchanged. Nothing here is a same-game realised property.
- The incumbent `D_ewma_shrunk` was not read, retuned or compared. No comparative historical
  performance of any challenger was inspected; nothing under `stage2b/SEALED_RESULTS/` was opened.
  TESTS.py asserts the measurement code contains no `SEALED_RESULTS` or `stage2b` reference and no
  metric token.

Two things a downstream reader should carry forward, neither of which this node resolves:

1. **`ROSTER_SOURCE_AUDIT_RECEIPT.json`'s prose contradicts its own counts.** Any node that reads
   that receipt's `what_it_is` string as the source's category inventory will repeat D10's
   omission. The receipt is frozen relative to this node and is reported, not edited.
2. **Other data-lane nodes may have inherited the same ten-category list.** This node did not
   audit them; it had no scope to.

---

## 10. Files

All inside `experiments/player_program/data_lane/R14_D10_COACHING_CORRECTION/`.

| file | what it is |
|---|---|
| `CORRECTION.json` | required machine-readable output: all 49 rows enumerated and classified, the noise class, the re-measured coverage by season/season-type/fold, the four-mechanism diagnosis, the cutoff-validity boundary |
| `REPORT.md` | this file, emitted by `write_report.py` |
| `remeasure_coaching.py` | produces `CORRECTION.json`. Reads only the source bytes, the universe and the folds |
| `cross_check_vs_d12.py` | produces `cross_check_vs_D12.json`. Runs after, feeds nothing |
| `TESTS.py` | standalone check suite, all passing, `main()` returns 1 on failure. Re-derives every source count through the stdlib `csv` module; positive controls on every negative |
| `write_report.py` | emits `REPORT.md` and asserts every headline number in it against `CORRECTION.json` before writing |
| `front_office_rows_v1.csv` | the 49 rows, flat, one per line |
| `coverage_by_row_v1.csv` | per-team-game coverage, 2,982 rows, so the headline is auditable row by row |
| `cross_check_vs_D12.json` | the cross-check result |

Reproduce:

```
python experiments/player_program/data_lane/R14_D10_COACHING_CORRECTION/remeasure_coaching.py
python experiments/player_program/data_lane/R14_D10_COACHING_CORRECTION/cross_check_vs_d12.py
python experiments/player_program/data_lane/R14_D10_COACHING_CORRECTION/TESTS.py
python experiments/player_program/data_lane/R14_D10_COACHING_CORRECTION/write_report.py
```

Nothing outside this directory is written. `data_lane/D10_FIELD_AVAILABILITY_LEDGER/` still holds
exactly its original four files with its four ABSENT coaching verdicts intact, asserted by
TESTS.py.
"""


def main() -> int:
    c = json.loads((HERE / "CORRECTION.json").read_text(encoding="utf-8"))
    fo = c["front_office_enumeration"]
    noise = c["coachs_decision_noise_class"]
    by = {f["field"]: f for f in c["fields"]}
    ident = by["coaching.head_coach_identity"]["coverage"]
    chg = by["coaching.coach_change_flag"]["coverage"]
    pres = by["coaching.head_coach_event_present"]["coverage"]
    diag = c["how_the_false_negative_was_produced"]
    bnd = c["cutoff_validity"]["boundary_case_examined"]

    # Every headline figure in the prose, re-read from the artifact. Any drift fails here.
    expect = [
        ("front_office rows", fo["front_office_rows"], 49),
        ("coaching identity rows", fo["coaching_identity_rows"], 48),
        ("unparsed", fo["unparsed"], 0),
        ("distinct named people", fo["distinct_named_people"], 34),
        ("hires", fo["by_action"]["hire"], 29),
        ("fires", fo["by_action"]["fire"], 11),
        ("resigns", fo["by_action"]["resign"], 9),
        ("interim rows", fo["by_role_class"]["interim_head_coach"], 7),
        ("head_coach rows", fo["by_role_class"]["head_coach"], 41),
        ("teams with events", len(fo["teams_with_at_least_one_event"]), 14),
        ("coach any case", noise["rows_whose_notes_contain_coach_case_insensitive"], 2930),
        ("coachs decision", noise["rows_whose_notes_contain_COACHS_DECISION_anywhere"], 2882),
        ("universe rows", c["row_universe"]["team_game_rows"], 2982),
        ("universe clusters", c["row_universe"]["game_clusters"], 1491),
        ("identity covered", ident["overall"]["covered"], 2101),
        ("identity clusters covered", ident["overall"]["game_clusters_covered"], 1260),
        ("event_present covered", pres["overall"]["covered"], 2213),
        ("change covered", chg["overall"]["covered"], 218),
        ("tenure covered", by["coaching.coach_tenure_games"]["coverage"]["overall"]["covered"], 2101),
        ("rotation covered", by["coaching.rotation_policy"]["coverage"]["overall"]["covered"], 0),
        ("cutoff_valid_count", c["cutoff_valid_count"], 0),
        ("d10 rows never reached", diag["c_category_whitelist_omission"]["rows_never_reached"], 49),
        ("d10 rows reached", diag["c_category_whitelist_omission"]["rows_reached_by_D10s_whitelist"], 8291),
        ("grep fo hits", diag["a_grep_reproduction"]["lines_in_front_office_rows"], 48),
        ("boundary rows date", bnd["rows_whose_cutoff_is_on_or_after_the_archive_DATE"], 10),
        ("boundary rows commit", bnd["rows_whose_cutoff_is_on_or_after_the_commit_TIMESTAMP"], 8),
    ]
    bad = [(n, got, want) for n, got, want in expect if got != want]

    for season, cov, cnt in [("2021", 0.141463, 58), ("2022", 0.430962, 206),
                             ("2023", 0.836538, 435), ("2024", 0.824427, 432),
                             ("2025", 0.919355, 570), ("2026", 0.930233, 400)]:
        cell = ident["by_season"][season]
        if cell["covered"] != cnt or abs(cell["coverage"] - cov) > 1e-6:
            bad.append((f"season {season}", (cell["covered"], cell["coverage"]), (cnt, cov)))
    if c["corrected_verdict"] != "PRESENT_RETROSPECTIVE / CUTOFF_UNPROVEN":
        bad.append(("corrected_verdict", c["corrected_verdict"], "PRESENT_RETROSPECTIVE / CUTOFF_UNPROVEN"))
    if c["parent_artifact_modified"] is not False:
        bad.append(("parent_artifact_modified", c["parent_artifact_modified"], False))

    if bad:
        print("REPORT.md NOT WRITTEN — prose disagrees with CORRECTION.json:")
        for n, got, want in bad:
            print(f"  {n}: artifact={got} prose={want}")
        return 1

    (HERE / "REPORT.md").write_text(REPORT, encoding="utf-8")
    print(f"REPORT.md written; {len(expect)} headline figures verified against CORRECTION.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
