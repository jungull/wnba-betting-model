# P24_INJURY_REGIME_LEDGER — S3: injury data split into explicit epistemic regimes, with cutoff-valid coverage

**Node:** `P24_INJURY_REGIME_LEDGER` · **Lane:** possession · **Type:** audit · **Role:** cutoff-validity auditor
**Severity on failure:** A

## Epistemic status of this output

> VERIFIED_READ_ONLY_DERIVATION. Classifies fields by epistemic regime. A field passing classification is ELIGIBLE for consideration, which is not the same as useful or admitted.

Nothing here fits, scores, promotes or admits anything. Nothing here reads
`stage2b/SEALED_RESULTS/`. No comparative historical performance of any challenger was inspected.

---

## Headline

`data/injury_history/injury_history.csv` is **two artifacts wearing one filename**, and neither is
currently usable as a pregame feature.

| regime | rows | source family | classification |
|---|---:|---|---|
| **R — realised participation** (`missed_game_injury`, `missed_game_other`) | **5,373** | `espn_summary_<eventid>.json` boxscores | **NOT A PREGAME FEATURE** |
| **T — announcement wire** (signing, waiver, trade, draft, contract_suspension, waiver_claim, retirement, front_office, contract_conversion) | **2,967** | `bbref_transactions_<year>.html` | **CUTOFF_UNPROVEN** |
| | **8,340** | | **ELIGIBLE: 0** |

**Cutoff-valid coverage of the fitted feature universe is 0 of 2,982 resolved team-game rows
(0 of 2,990 scheduled) in every one of the six chronological folds.** That is a negative result and
it is reported as one. Availability coverage is separately high and is reported alongside, as the
acceptance criteria require.

---

## Reproduction

Everything below comes from one script, run from the worktree root:

```
python experiments/player_program/stage2b/P24_INJURY_REGIME_LEDGER/measure_injury_regimes.py
```

It writes `FINDINGS.json` (machine-readable, all figures) and `REGIME_LEDGER.csv` (the regime x
classification x source x category grid). It reads only; it writes only inside this node's
directory. Verify with:

```
python -c "import json;json.load(open('experiments/player_program/stage2b/P24_INJURY_REGIME_LEDGER/FINDINGS.json'))"
python experiments/player_program/stage2b/P24_INJURY_REGIME_LEDGER/TESTS.py
```

Input pinned by hash: `data/injury_history/injury_history.csv`
`sha256 = 6aec435c94af3da10adc793c9978afbe33749cdff8f97a194939db564ed2f33b`, 916,886 bytes.

---

## What I measured

### 1. The 5,373 / 2,967 split of the 8,340 rows — **AGREE, and it is stronger than the packet states**

`V2_STOP_CONDITION.json` S3 claims `total_rows 8340`, `missed_game_star_rows 5373`,
`announcement_dated_rows 2967`. Re-derived:

```
python -c "import pandas as pd; d=pd.read_csv('data/injury_history/injury_history.csv'); print(d['category'].value_counts())"
```

`missed_game_other 3131` + `missed_game_injury 2242` = **5,373**. Remainder = **2,967**
(`signing 1455`, `waiver 795`, `draft 260`, `trade 252`, `contract_suspension 111`,
`front_office 49`, `retirement 21`, `waiver_claim 18`, `contract_conversion 6`). Total **8,340**.
**AGREE on all three figures.**

The split is not a naming coincidence. Cross-tabulating `category` against the source-file family
gives a **perfect partition**: all 5,373 `missed_game_*` rows come from
`espn_summary_<eventid>.json`; all 2,967 wire rows come from `bbref_transactions_<year>.html`.
Zero rows cross. The two regimes have **disjoint provenance**, which is a firmer basis for the
split than the category label alone.

### 2. Regime R is contemporaneous **by construction**, not by inference

`scrape_injury_history.py::parse_espn_dnp()` reads
`boxscore.players[].statistics[].athletes[]`, keeps rows where `ath["didNotPlay"]` is truthy, and
stamps each row with `g["date"]` — the date of that same game. The row's **only** evidentiary
source is the completed game's own boxscore.

Measured consequences:

* 1,318 distinct source pages; **0** pages carry more than one distinct row date.
* 553 distinct row dates; **548** are contract game dates.
* **5,354 of 5,373 rows (99.6464%)** name a team that played a contract game on that exact date.
* The 19 exceptions fall on 5 dates (2022-07-26, 2023-08-15, 2024-06-25, 2025-07-01, 2026-06-30)
  and **all 19 carry the `[commissioners-cup-final]` tag** — a game outside the contract universe.
  Not a join defect.
* A naive date join of regime R onto the team-game spine attaches a row describing that game's own
  realised absences to **2,337 of 2,990 team-games (78.2%)**, touching **1,313 of 1,495 game
  clusters**.

A `didNotPlay` flag is a realised participation outcome of the target game. There is **no lag at
all** between the observation and the event it describes. This is not "cutoff unproven"; it is a
target-game outcome. **Classified NOT A PREGAME FEATURE.**

Every other realised-participation or retrospective field in the file inherits this: the file
carries no other realised-outcome column, so the classification is exhaustive over regime R.

Lagged use over strictly earlier games is a *different object* with its own (separately unproven)
cutoff argument. **This node does not adjudicate or license it.**

### 3. No row in either regime has a source timestamp

The file has 7 columns: `date, team, player_acquired, player_relinquished, notes, category,
source_page`. Columns matching any timestamp-like pattern (`time`, `stamp`, `observed`, `captured`,
`asof`, `fetched`, `reported`, `announced`, `updated`): **zero**. `date` is date-granularity only —
every value is exactly 10 characters, no time component, span `2021-01-07 .. 2026-07-29`.

The acceptance criterion is *"a source timestamp at or before the declared pregame cutoff"*. An
event date is not a source timestamp. **All 8,340 rows are therefore CUTOFF_UNPROVEN on criterion
(a)**, and regime R additionally fails criterion (c).

The observation time is a **single retrospective moment**, and I re-derived it rather than taking
the receipt's word:

```
git log --diff-filter=A --format="%h %ad %s" --date=iso -- data/injury_history/injury_history.csv
-> 98271bb  2026-07-30 13:42:00 -0400  Add historical injury/absence/transaction archive 2021-2026 (8,340 rows)
```

This **AGREES** with `ROSTER_SOURCE_AUDIT_RECEIPT.json` `q2_timestamps`. Consequence measured here:
against the repository's one declared pregame cutoff rule (18:00 UTC the day before the game), that
single observation time of `2026-07-30T17:42Z` postdates the cutoff of **2,984 of 2,990 team-game
rows**. Only **6** rows — 3 games on 2026-07-31 — could ever be served by this artifact under a
capture argument.

### 4. Testing regime T against the one declared pregame cutoff

The possession lane declares **no** pregame cutoff. The only declared cutoff anywhere in the
repository is `prediction_contract_v4/v5`'s `forecast_cutoff`, whose registered date-only fallback
(`prediction_contract_v5.date_only_cutoff`, `POLICY_DATE_ONLY`) is **18:00 UTC on the day before
the game**. I applied that published policy to this node's own team-game universe as a task-specific
wrapper at the call site — I did not import, read or modify the contract module's artifacts.

A date-only row's true observation time lies in `[d 00:00Z, d 23:59:59Z]`. Relative to the next
contract game for the named team:

| band | rows | meaning |
|---|---:|---|
| `d <= D-2` UNAMBIGUOUSLY_PRE | 2,350 | whole interval precedes the cutoff |
| `d = D-1` **AMBIGUOUS** | **313** | the 18:00Z cutoff splits the interval |
| `d >= D` POST_CUTOFF | 281 | whole interval at or after the cutoff |
| 23 rows carry a null `team` and are untestable | 23 | |

The 313 ambiguous rows affect **229 team-games**.

**This is where a real defect lives.** `prediction_contract_v5.py` does
`pd.to_datetime(tx["date"], utc=True)`, pinning every date-only announcement to `00:00Z` — the
**earliest** instant in its true interval — and then admits on `x < c`. The ambiguity is resolved
silently, and always in the direction that admits. It is not a demonstrated leak; it is a
systematic bias in the direction that leaks.

### 5. Designation semantics — documented, but they are the wrong semantics

`project_docs/INJURY_HISTORY.md` does document a category table, so criterion (b) is nominally met
for regime T. But the documented semantics are **transaction-type** semantics. There is **no
availability designation anywhere in the file** — no Out / Doubtful / Questionable / Probable, no
probability of playing, in either regime. The producing document says so itself under *Known
limitations*: there is no historical pregame status signal in this artifact, and the live capture
starting 2026-07-30 exists to begin collecting one.

Three categories are documented but have **zero rows**: `activation`, `missed_game_unspecified`,
`other`. Zero categories appear in the data that are absent from the doc. The missing `activation`
matters: `INJURY_HISTORY.md` states a `contract_suspension` "holds until the next
`activation`/`signing` row", and there are 111 suspensions and **0** activations, so that stated
close-out mechanism never fires in this file.

### 6. Coverage by season and by fold

Fold construction, per `EVIDENCE_PACKET_V2.inference_specification.fold_construction`:
*chronological, nested by season; a game is NEVER split across folds.* `V2_STOP_CONDITION` S7
enumerates six chronological folds, 2021-2026. **Fold identifier == season.**

Universe reported **both ways**, per the packet's `do_not_substitute` rule: **2,982 team-game rows /
1,491 game clusters** resolved; **2,990 / 1,495** scheduled. The 8-row / 4-game difference is the
`unresolved_no_prior_games` stratum.

| fold | team-games (resolved) | clusters (resolved) | R rows | T rows | **ELIGIBLE** | **cutoff-valid coverage** | avail: TG with >=1 prior T row | avail: within 30d | ambiguous D-1 T rows | leakage exposure: TG with a same-day R row |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2021 | 418 (410) | 209 (205) | 691 | 460 | **0** | **0.0%** | 418 (100%) | 309 | 51 | 316 (75.6%) |
| 2022 | 478 (478) | 239 (239) | 748 | 513 | **0** | **0.0%** | 478 (100%) | 382 | 63 | 351 (73.4%) |
| 2023 | 520 (520) | 260 (260) | 852 | 447 | **0** | **0.0%** | 520 (100%) | 445 | 44 | 380 (73.1%) |
| 2024 | 524 (524) | 262 (262) | 971 | 412 | **0** | **0.0%** | 524 (100%) | 402 | 38 | 413 (78.8%) |
| 2025 | 620 (620) | 310 (310) | 1,221 | 564 | **0** | **0.0%** | 620 (100%) | 517 | 72 | 510 (82.3%) |
| 2026 | 430 (430) | 215 (215) | 890 | 571 | **0** | **0.0%** | 430 (100%) | 344 | 45 | 367 (85.3%) |

Two readings must not be confused:

* **The ELIGIBLE and cutoff-valid columns are zero in all six folds.** That is the answer to the
  mandate. It is uniform, so there is no fold-degeneracy story here — the field is absent from every
  fold equally.
* **The availability columns are 100% in all six folds.** Per the acceptance criteria,
  CUTOFF_UNPROVEN rows stay in availability reports while being excluded from the fitted feature
  universe. They are reported, and they are *not* evidence of usability.
* **The leakage-exposure column is what a careless join would produce**, not what anything currently
  does. It rises monotonically 2021 to 2026 (75.6% to 85.3%) with roster size and DNP reporting
  density.

### 7. Span truncation — the packet's "full contract span" is **CORRECTED**

`EVIDENCE_PACKET_V2` records the source as *"8,340 rows, 2021-01-07 .. 2026-07-29, full contract
span"*. Measured: the contract universe's last game date is **2026-07-31**; the injury file's last
row is **2026-07-29**. **12 team-game rows over 6 game clusters** (game dates 2026-07-30 and
2026-07-31) postdate every row in the file. The span is **not** the full contract span. Severity B —
it does not change a fitted design, because nothing is fitted on this field.

### 8. Documentation coverage table — **AGREE, all six seasons, all four columns**

The `Coverage` table in `project_docs/INJURY_HISTORY.md` reproduces exactly against the bytes for
every season on `total`, `missed_game_injury`, `missed_game_other` and wire count. Recorded because
it was checked, not because it was doubtful.

### 9. The one registered consumer

`experiments/player_program/arm_registry.jsonl` binds `data/injury_history/injury_history.csv` in
**`cbs_v15_player_oof_v5` revisions 2 through 8** (player lane). The registry's
`source_snapshot_sha256` for the file is
`6aec435c94af3da10adc793c9978afbe33749cdff8f97a194939db564ed2f33b`, which **matches the bytes on
disk**. No artifact/receipt disagreement.

`prediction_contract_v5.py` consumes it via
`ACQUIRE = {signing, trade, waiver_claim, draft, contract_conversion}` and
`RELEASE = {waiver, retirement, contract_suspension}` — **2,918 of the 2,967 regime-T rows**
(the 49 `front_office` rows carry no player and are not consumed). It **never touches any
`missed_game_*` row**. The regime split this node makes explicit is already being honoured in that
module's code. It is nowhere written down as an epistemic rule, and nothing enforces it.

I also re-derived that receipt's row accounting: `ROSTER_SOURCE_AUDIT_RECEIPT.json` reports
`n_acquisition_rows 1846` / `n_release_rows 927`. Measured: ACQ-category rows = 1,991, of which
**1,846** name an acquired player; REL-category rows = **927**, all naming a relinquished player.
**AGREE**, once the receipt's implicit `player_acquired.notna()` filter is made explicit; the
145-row remainder is the outgoing side of trade sentences.

**The possession lane — this node's lane — binds no injury field in any arm, control or feature
frame.** A `*injur*` sweep over the possession artifacts (`possession_features.py`,
`possessions_v2/`, `projected_exposure_v1/`) returns nothing.

---

## What I could NOT establish, and why

1. **Whether any regime-T `date` is a genuine event date.** `data/injury_history/raw/` does not
   exist in this worktree and `.gitignore` line 7 excludes it. The `manifest.jsonl` that
   `INJURY_HISTORY.md` says records "url/status/time per fetch" — the only artifact that could ever
   have carried a per-fetch observation time — is absent. This is not a gap I could close with more
   work: **it is unrecoverable inside this repository.**
2. **Whether the CSV is re-derivable.** For the same reason, `python scrape_injury_history.py
   --parse-only` would rebuild an **empty** CSV here. I did not run it (it would be a write outside
   my scope); the conclusion follows from the producer's `RAW_DIR`-only parse path plus the
   directory's absence.
3. **The true intraday time of the 313 ambiguous D-1 announcements.** No source in the repository
   carries it. I bounded them rather than guessing: `[d 00:00Z, d 23:59:59Z]`.
4. **Whether a lagged construction over regime R could be made cutoff-valid.** Out of this node's
   mandate. I classified the target-game row and stopped. Nothing here should be cited as licensing
   a lagged injury feature.
5. **D10's numbers.** `data_lane/D10_FIELD_AVAILABILITY_LEDGER/build_ledger.py` exists but its
   output ledger is not materialised in this worktree, so I could compare its verdict text only.

---

## Contradictions found

**C1 — `EVIDENCE_PACKET_V2` vs the bytes. CORRECT the packet.**
The packet lists "injury / transaction history" as **one** field, "8,340 rows ... full contract
span", Category B on cutoff grounds. The bytes are **two regimes with disjoint provenance and
different epistemic status**, and the span is **not** the full contract span (12 team-game rows over
6 clusters postdate it). S3 already names the regime half; the span half is new.
*Severity: A on the regime point (already raised as S3); B on the span point.*

**C2 — `project_docs/INJURY_HISTORY.md` vs the bytes. The document describes a provenance chain
that is not present.**
The doc asserts every HTTP payload is retained under `data/injury_history/raw/` with a
`manifest.jsonl` recording fetch times. Neither exists here; `.gitignore` line 7 excludes the
directory. Consequence: the event-date claim can never be audited against a capture record, and the
"no source timestamp" verdict is permanent.
*Severity: A for any arm that would rely on the cutoff claim.*

**C3 — `prediction_contract_v5.py`'s behaviour vs any written rule. An unwritten invariant.**
`ACQUIRE`/`RELEASE` deliberately exclude every `missed_game_*` category, so the regime split is
already being honoured in code. **No document, gate or receipt states the rule.** Nothing prevents
the next consumer from joining `missed_game_*` on the target-game date — which would attach 2,337
of 2,990 team-game rows (78.2%) to their own realised absences. This is exactly the S1 shape: a
convention where an enforced invariant is required.
*Severity: A as a latent hazard.*

**C4 — the "source timestamp" criterion vs the consumer's date coercion. Silent ambiguity
resolution, always toward admission.**
`pd.to_datetime(tx["date"], utc=True)` pins a date-only announcement to `00:00Z`, the earliest
instant it could have occurred, and admission is `x < c`. 313 regime-T rows straddle the 18:00Z
date-only cutoff, affecting 229 team-games.
*Severity: B, escalating to A if any fitted arm depends on those rows.*

**C5 — `INJURY_HISTORY.md` coverage table vs the bytes. No contradiction.** AGREE on all six
seasons and all four columns. Recorded because it was checked.

**C6 — this node's mandated classification vs sibling node D10.**
`D10_FIELD_AVAILABILITY_LEDGER/build_ledger.py` gives `injury.missed_game_injury_wire` and
`injury.missed_game_other_wire` the verdict **`CUTOFF_UNPROVEN`**. That is not wrong, but it is not
strict enough. `CUTOFF_UNPROVEN` says *we cannot show it was knowable in time*. These rows are
stronger than that: they are the target game's own realised participation, read out of its boxscore.
**No timestamp could rescue them, because the fact does not exist before the game is played.**
`RESEARCH_CONTRACT_V1` precedence — *the stricter governs* — makes **NOT A PREGAME FEATURE** the
operative classification.
*Severity: B — a labelling gap, not a live leak.*

---

## Stop condition

**TRIPPED — raised, not resolved.**

> *a finding would change ... the cutoff-valid feature set — HALT and raise, do not resolve it
> inside the node*

`injury_history.csv` contributes **zero** cutoff-valid rows to the fitted feature universe, in every
fold. `EVIDENCE_PACKET_V2`'s corrected availability table lists it as one Category-B field with
cutoff unproven; the bytes say it is two regimes, and the 5,373-row **majority regime is a realised
participation outcome sourced from the target game's own boxscore**, not merely an unproven pregame
signal. That is a change to the cutoff-valid feature set, and it is a strictly stronger statement
than S3 as written.

I have **not** resolved it: no availability table was edited, no packet was touched, no field was
promoted or demoted anywhere outside this node's directory.

**Not tripped, recorded for completeness.** The primary target, the K0 structure, the inference
structure and the candidate universe are untouched. No possession-lane arm, control or feature frame
binds an injury field, so removing it changes no fitted possession design. The player-lane arm
`cbs_v15_player_oof_v5` *does* bind the file, consumes regime-T categories only, and is recorded
here so the player thread can act on C4 — this node does not adjudicate the player lane.

---

## What would have to change for anything here to become ELIGIBLE

Stated as a proposal for adjudication elsewhere, not as a classification made here. Nothing is
ELIGIBLE today.

* **Regime R: nothing.** No timestamp, no provenance, no relabelling can make a target-game boxscore
  flag knowable before that game. It is closed.
* **Regime T:** one named, registerable relaxation — *accept the Basketball-Reference listed `date`
  as a bona fide event date with an end-of-day upper bound (`d 23:59:59Z` rather than `00:00Z`)* —
  would leave **2,350 of 2,967 rows** surviving an ordering test and **617** still CUTOFF_UNPROVEN.
  Even then the file still has **no availability designation**, and the raw payloads that would let
  the event-date claim be audited do not exist. That relaxation is an explicit, hash-pinned
  assumption someone must sign, not a measurement.
* **The only genuinely cutoff-valid availability source in the repository** is
  `data/injury_capture/injury_log.csv`, which carries a real per-row `capture_utc` and covers
  2026-07-30 onward only — six days of a five-and-a-quarter-season span. That is consistent with
  `EVIDENCE_PACKET_V2`'s `unavailable_or_insufficient` entry and with D10's `CUTOFF_VALID` verdict
  for `injury.status` / `injury.reason` / `injury.report_date` within that span.

---

## Scope note

Write scope observed exactly: every file written by this node lives in
`experiments/player_program/stage2b/P24_INJURY_REGIME_LEDGER/`. No frozen artifact was modified. No
mutating git command was run — the only git invocations were `rev-parse --abbrev-ref HEAD`,
`ls-files`, and `log`, all read-only.

The declared read scope is `experiments/player_program/`. Establishing provenance and designation
semantics for a `data/` artifact required reading, **read-only**, five files outside that tree:
`data/injury_history/injury_history.csv` (the subject), `data/reference/team_cities.csv` (the
team-abbreviation bridge), `project_docs/INJURY_HISTORY.md` and `scrape_injury_history.py` (the
producer and its documentation), plus `prediction_contract_v5.py` after `arm_registry.jsonl` —
which *is* in scope — named it as the binding consumer. Flagged rather than assumed to be fine.
