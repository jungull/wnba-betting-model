# F14_DECISION_TIME_MARKET_COMPARISON — TARGET CONTRACT DRAFT

**Node:** `F14_DECISION_TIME_MARKET_COMPARISON` · **Lane:** future_research · **Type:** documentation
· **Severity on failure:** C · **Role:** read-only research scout
· **Written:** 2026-08-04 · **Branch:** `player-model-program`

## Epistemic status of this output

> DIAGNOSTIC AND TARGET-CONTRACT DRAFT ONLY. Discovery work being unblocked is NOT authorisation to
> fit. Fitting requires a target contract, a matched K0, cutoff-valid evidence, a preregistration
> and an independent gate review.

---

## 1. The estimand

### `NOT_DERIVABLE_FROM_DOCUMENTATION`

The program record contains no target statistic, no unit and no denominator for a decision-time
market comparison. It contains an activity name, a deferral, two boundary constraints and one
unresolved external conflict. None of those is an estimand, and this draft does not invent one.

**What the documentation actually says.** Four items, each verified against the bytes at the line
cited:

| # | citation | verified text |
|---|---|---|
| E1 | `experiments/player_program/PROJECT_UPDATE_2026-08-04.md:284-285` | "**Deferred.** Staged distributional layer; decision-time comparison; player props last, and not before the market premise is evidenced." |
| E2 | `experiments/player_program/PROJECT_UPDATE_2026-08-04.md:323` | "**No ROI optimisation.** Proper scores and calibration precede any market threshold." |
| E3 | `experiments/player_program/PROJECT_UPDATE_2026-08-04.md:638` | "CLV as sole validation metric ... **conflict unresolved** — near-tautological if the close is efficient; no academic source located establishing it for thin markets" |
| E4 | `experiments/player_program/PROJECT_UPDATE_2026-08-04.md:636` | "WNBA market efficiency — no statistically significant returns to simple strategies, 2007–2012 ... **contradicts** the promotional 'soft market' premise" |

E1 is the whole of the track's mandate in the program record. `ROADMAP_EXTRACTION.json` maps this
node to exactly that line and nothing else: `already_modelled[10] = {"documented_item":
"PROJECT_UPDATE §7 deferred, decision-time comparison", "modelled_as":
"F14_DECISION_TIME_MARKET_COMPARISON"}`.

E2 and E3 are *negative* constraints. They tell a future contract which statistics it may **not**
be — it may not be ROI, and CLV is expressly recorded as an unresolved conflict rather than an
adopted metric. Read together they exclude the two statistics a practitioner would reach for first
and nominate no replacement.

E4 removes the premise that would motivate the comparison in the first place, and E1 makes
"the market premise is evidenced" a precondition on the *adjacent* player-props track.

### Why an estimand is not merely missing but not yet constructible

Three separate pieces are absent, and no two of them can be supplied by the third.

1. **There is no priced quantity corresponding to the primary target.** The settled primary target
   is `REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS`. No sportsbook prices team offensive
   possessions. The nearest analogue is a game total, and the historical archive **has no totals
   market at all**: `stage2b/P29_TIP_TIME_AND_COVERAGE_AUDIT/REPORT.md:282` — "Markets present:
   `odds_spread` and `odds_price`. **No totals column.**" A comparison therefore needs a documented
   mapping from a regulation-equivalent possession projection to a priced quantity. No such mapping
   exists anywhere in the program record.
2. **There is no scoring rule.** E2 requires proper scores and calibration to precede any market
   threshold, but names no proper score, no calibration statistic and no loss. The frozen
   comparison machinery scores arms against matched nulls on the primary target; it has no notion
   of scoring a forecaster against a third-party forecast.
3. **There is no denominator.** Every candidate denominator for a market comparison — priced
   games, priced games at a given decision-time label, executable priced games, games with a
   two-sided quote — is a *market-side* denominator. Section 5 shows that not one of them has been
   measured on this branch, and section 6 shows why several of them cannot be.

**Consequence.** A registered layer with elaborate machinery and no estimand is not closer to
fittable than an unregistered one. This track is in that category. It is stated as such rather
than repaired.

### The one place the program record *looks* like it has an estimand, and does not

`product_lane/U10_PREDICTION_API_SCHEMA` defines a `market` block per projection carrying
`available`, `book`, `line`, `over_price`, `under_price`, `captured_at_utc`, `unavailable_reason`
and `edge_vs_line`, and invariant I9 (`SCHEMA.md:66`) governs its absence semantics. This is a
**response-shape contract for display**, not a target contract:

* `edge_vs_line` is a per-projection difference, defined by the schema for a single response. It
  has no aggregation, no denominator, no sign convention across sides, no scoring rule and no
  population over which it is averaged.
* `SCHEMA.md:90` — "Market capture is deliberately **not** a projection dependency"; a missing
  market suppresses the edge, not the projection. The market is decoration on the response, by
  design.
* **Measured:** across the 7 golden fixture responses there are **21** market blocks, **12** with
  `available: true`, and every one of them carries `book = "FIXTURE_BOOK"` with `FIXTURE_`-prefixed
  subject ids. Every market number in the product lane is synthetic. (Command in section 8, M2.)

Anyone later citing `edge_vs_line` as this track's estimand would be citing a fixture.

---

## 2. The matched-K0 requirement for this target

Stated in full even though the estimand is absent, because the requirement binds whichever of the
two constructions a future contract picks, and because the second construction is currently barred.

**The governing contract** is `stage2b/P26_ARM_SPECIFIC_K0_CONTRACT/`. Its terms, as written there:

* `K0_MATCHED` is a **map keyed by `arm_id`**. There is no universal K0. "an arm with no record has
  no authoritative control and cannot be adjudicated" (`P26.../REPORT.md:33-35`).
* `K0_FLAT` is a **diagnostic reference**; every record must carry
  `k0_flat_role: "diagnostic_only"`, pinned by a schema `const`. Beating `K0_FLAT` has **no
  promotion value** (`REPORT.md:37-40`).
* The matched null holds byte-identical rows, target, folds, weights, offset, fallback machinery,
  nuisance terms and lower-order structural terms, enforced as equality on **all seventeen**
  `comparison_gate.DIMENSIONS` (`REPORT.md:43-47`).
* `target` is pinned by the schema with
  `const: "REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS"`. "A record cannot swap the primary
  target." (`REPORT.md:49-51`)
* Exclusion minimality: the null excludes **exactly** the declared `treatment_terms` — no more
  (straw control), no less (feature absorption) (`REPORT.md:55-64`).

**Construction A — market as comparator (the market is a rival forecast, not a feature).**

* A market benchmark is **not** a K0 and may never be used as one. K0 is defined by identity on
  seventeen dimensions with the challenger; a third-party forecast shares none of them — not rows,
  not folds, not weights, not offset. Beating a market line is not evidence about an arm.
* Any arm whose result is reported alongside a market comparison still requires its own
  `K0_MATCHED[arm_id]`, unchanged, and its promotion verdict is decided **against that null only**.
  The market column is at most a descriptive annotation on an already-adjudicated result.
* The market's coverage is not the arm's coverage. Because market coverage is a strict subset of
  the universe (section 5), a market-comparison subset is a **different row set**, which under
  P26 §1.2 is a different K0 record, not the same one restricted.
* The primary-target pin means Construction A cannot be reported as evidence on the primary target
  unless the priced quantity *is* the primary target. It is not, and no mapping is documented.

**Construction B — market as feature (a price enters the prediction path).**

* This makes the market a `treatment_term`, hence an **arm**, hence subject to
  `K0_MATCHED[arm_id]` with exclusion minimality: `set(arm.substantive_features) -
  set(k0.substantive_features)` must equal exactly the set of market terms, and no market term may
  re-enter through `k0.structural_terms`.
* **Construction B is currently barred.** The frozen evidence packet excludes the market-odds
  family (`stage2a/EVIDENCE_PACKET_V2.json:565-569`, verdict `UNAVAILABLE HISTORICALLY`), and
  `P29` has raised the exclusion *ground* as a stop condition, not the exclusion itself (section 7).
  Admitting the family would change the candidate universe. **That is not this node's decision and
  is not taken here.**
* The packet's own separate objection travels with it: a market feature "changes what the model
  is" — from predicting possessions to predicting the market. `EVIDENCE_PACKET_V2.json:569` (the `note` field) —
  "also a market feature, which raises separate questions about what is being learned". Left
  **OPEN**.

**Additional requirement specific to a *decision-time* comparison.** Whichever construction is
chosen, the comparison is only defined at a named decision-time label. The operational vocabulary
in use is `T-24h`, `T-8h`, `T-30m` (measured in `ops_lane/O13_LEAD_WINDOW_LATENCY/FINDINGS.json`,
`ops_lane/O10_LATE_RECORD_AUDIT_CLASSIFICATION/FINDINGS.json:51` (`"decision_time_label": "T-30m"`)). A market observation and a model
projection must be paired **within the same label and the same cutoff**, each carrying its own
observation timestamp, or the pairing is not a decision-time comparison at all. No artifact on this
branch pairs them.

---

## 3. Cutoff-valid evidence — inventory, not assumption

Read scope for this node is `experiments/player_program/` (`PROGRAM_GRAPH.json`). Everything under
the repository `data/` tree is out of scope and was **not opened**. Figures below are either
measured by me inside scope (marked **[mine]**) or quoted from a frozen in-scope receipt with its
owning node named (marked **[quoted]**). Nothing here is assumed.

### 3.1 Market-side evidence

| item | status | basis |
|---|---|---|
| any market price artifact inside `experiments/player_program/` | **NONE** | **[mine]** M1 |
| `data/drive_masters/master_odds.csv` — 20,004 rows, 813 distinct `game_id`, snapshots 2022-05-21T17:55:00Z .. 2025-07-03T22:55:37Z, seasons 2022–2025, spread and price only, **no totals** | EXISTS, OUT OF SCOPE, NOT ON THIS BRANCH | **[quoted]** P29 `MEASUREMENTS.json` `M7_provenance.OUT_OF_SCOPE_ROOT_WORKTREE`; P29 `REPORT.md:278-282` |
| `data/odds_capture/historical` — 292 JSON snapshots, `hist_2025-07-05_15Z.json` .. `hist_2026-07-29_22Z.json` | EXISTS, OUT OF SCOPE, CONTENT UNEXAMINED | **[quoted]** P29 same block; P29 `REPORT.md:324-326` records that whether these carry a totals market was **not** established |
| `data/odds_capture` live snapshots — 69 files, 2026-07-30 .. 2026-08-04 | EXISTS, OUT OF SCOPE | **[quoted]** P29 same block |
| frozen packet verdict on the family: coverage "2026-07-31 .. 2026-08-06 only", `UNAVAILABLE HISTORICALLY` | FROZEN, GROUND DISPUTED | `stage2a/EVIDENCE_PACKET_V2.json:565-569`; ground disputed by P29 SC1 |
| `master_odds.csv` / `data/odds_capture/` present in **this** worktree | **false / false** | **[quoted]** P29 `M7_provenance.upstream_present_in_this_worktree`; P29 `REPORT.md:265-266` — neither is tracked by git |
| any per-snapshot **observation** timestamp surviving into a tracked artifact | **NO** | **[quoted]** D10 `REPORT.md:167-170` — `collect_bios.py::phase_tips` takes the latest snapshot and "does not retain `odds_snapshot_timestamp` in the output" |
| U10 `market` blocks: 21 blocks, 12 `available: true`, book `FIXTURE_BOOK`, all subjects `FIXTURE_`-prefixed | SYNTHETIC FIXTURES ONLY | **[mine]** M2 |

**Net:** zero rows of real market data are cutoff-valid on this branch, because zero rows of real
market data are *reachable* on this branch. The market side of a decision-time market comparison
has an inventory of exactly nothing.

### 3.2 Model-side evidence that a comparison would need

| item | status | basis |
|---|---|---|
| whole-ledger verdicts across 52 fields: **CUTOFF_VALID 5**, `CUTOFF_UNPROVEN` 37, `ABSENT` 7, `CUTOFF_INVALID` 3 | see caveat below | **[mine]** M3, recomputed from D10 `FINDINGS.json` |
| `tip.scheduled_tip_time__contract_v4_screened` — the only historical field clearing the cutoff test, 814 of 2,982 team-game rows (27.3%) | CUTOFF_VALID, thin | **[quoted]** D10 `FINDINGS.json` fields[] |
| `injury.status` / `injury.reason` / `injury.report_date` — genuine per-row `capture_utc`, 551 rows, 2026-07-30 .. 2026-08-01 only | CUTOFF_VALID within a 3-day span | **[quoted]** D10 `FINDINGS.json` |
| `roster.captured_availability_affiliation` — 12 of 2,982 rows covered, 2 cutoff-valid | CUTOFF_VALID, negligible | **[quoted]** D10 `FINDINGS.json` |
| tip-time coverage 1,219 of 1,491 universe games; 2021 **zero** | measured elsewhere | **[quoted]** D10 `REPORT.md:164-165`; P29 `M7_provenance` corroboration table |
| prospective forecast stream: 84 obligations, 47 due, 15 served, coverage **0.3191**, promotion_grade **false** | measured elsewhere | **[quoted]** O13 `FINDINGS.json` `auditor_summary_in_memory` |

**Caveat that must travel with the D10 citations.** `GRAPH_STATE.json` records
`D10_FIELD_AVAILABILITY_LEDGER` as **FAILED**. `GRAPH_EVENTS.jsonl` gives the reason: "MANUFACTURED
NEGATIVE: coaching family reported ABSENT with 0 coverage on an assertion contradicted by the bytes
of a file the node itself loaded ... Ledger retained; the other 48 fields are not impeached by this
family." The fields cited above are outside the impeached family, but they are cited as a
**provisional** ledger, not as settled evidence.

### 3.3 What "cutoff-valid" would additionally require here, and does not exist

A decision-time market comparison needs, per paired observation: a model projection with its own
cutoff, **and** a market observation with a per-snapshot observation timestamp proven to precede
that same cutoff, **and** the two bound to the same game and the same decision-time label. The
repository has never produced a single such pair. `construction_receipt.py:523-531` already
provides the vocabulary (`cutoff_contract`, `decision_time_rule`,
`per_row_decision_time_column`); no market artifact has ever been passed through it.

---

## 4. Known data blockers

* **B1 — No priced quantity for the primary target.** No market on team offensive possessions
  exists, and the historical archive carries no totals market (P29 `REPORT.md:282`). Blocks the
  estimand itself, not merely its measurement.
* **B2 — The historical odds archive is not on this branch.** `git ls-files data/odds_capture
  data/drive_masters` returns nothing; neither path exists here (P29 `REPORT.md:265-266`, and
  `M7_provenance.upstream_present_in_this_worktree`). Any future work on this track is not
  reproducible from `player-model-program` as it stands.
* **B3 — Per-snapshot observation timestamps are discarded by the one tracked derivative.**
  `tip_times.csv` drops `odds_snapshot_timestamp` (D10 `REPORT.md:167-170`), which is why every
  tip-time field is `CUTOFF_UNPROVEN`. D10 records the unprovenness as "a property of the
  derivation, not of the underlying feed", i.e. repairable in principle — by a node with the write
  scope to rebuild a source artifact, which this node does not have.
* **B4 — Execution-side fields are not captured, and historical reconstruction is blocked.**
  `PROJECT_UPDATE_2026-08-04.md:280-282`: the nine fields (sportsbook, market, price, timestamp,
  observable limit, decision label, closing line, executability, slippage) are to be captured
  *going forward*; "Historical reconstruction is blocked by DL-002 (27% T-24h coverage)." A
  comparison at a decision-time label needs precisely these, and they begin no earlier than the
  capture start.
* **B5 — The prospective stream is not gradeable.** Coverage 0.3191, promotion_grade false (O13);
  `PROJECT_UPDATE:...D-1` records that fixing the start record "**does not** make the stream
  gradeable". A prospective market comparison would inherit this, not escape it.
* **B6 — The availability table conflates observation span with event-date span.** D11 finding C1:
  the packet's market row reads "2026-07-31 .. 2026-08-06", two days into the future relative to
  the machine clock at writing (2026-08-04T19:58:51Z), while the injury row on the same table is an
  observation span. A reader who takes the market row as an observation span "credits the
  repository with having seen two days of the future" (D11 `REPORT.md:126-135`). Severity B, frozen,
  not edited.
* **B7 — Sub-day cutoff resolution is unverifiable in this wave.** `V2_HYPOTHESES_adversarial.md:707-709`
  (B7): tip times for 1,219 of 1,495 games, none in 2021, 36 games with `n_commence_variants > 1`,
  no as-of binding — "Any claim that a feature is cutoff-valid at sub-day resolution is
  unverifiable in this wave." A decision-time comparison is inherently sub-day.
* **B8 — The motivating premise is contradicted, and the fallback metric is unresolved.** E4 and
  E3. Not a data blocker in the mechanical sense; recorded here because a future contract that
  proposes CLV or ROI walks straight into an already-registered no-go (E2).

---

## 5. This draft does not authorise fitting

**This draft does NOT authorise fitting.** It is a target-contract *draft* that concludes the
target contract cannot yet be written. Fitting on this track requires, and does not have:

1. a **target contract** — absent; the estimand is `NOT_DERIVABLE_FROM_DOCUMENTATION` (section 1);
2. a **matched K0** — the requirement is stated (section 2), no `K0_MATCHED[arm_id]` record exists
   for any market-touching arm, and P26 records that no real arm exists yet at all;
3. **cutoff-valid evidence** — inventoried in section 3; the market side is empty on this branch;
4. a **preregistration** — none drafted, and the pre-registration checklist at
   `V2_HYPOTHESES_adversarial.md:726` is open;
5. an **independent gate review** — not this node's, and no verifier has reviewed this draft.

None of the five is in this node's gift. Nothing in this document may be cited as evidence that any
market-derived feature is admissible, that any market comparison has been authorised, or that any
estimand has been agreed. No fit was run, no model code was written, no comparative historical
performance was inspected, and nothing under `stage2b/SEALED_RESULTS/` was read.

---

## 6. Stop conditions

**No new stop condition is raised by this node.** One inherited stop condition is **restated as
open**, and one objection is **restated as OPEN**, neither resolved here:

* **Inherited SC1 (P29 `REPORT.md:296-303`), Severity A — candidate universe / cutoff-valid feature
  set.** The market-odds family was excluded on the ground that capture begins 2026-07-31; a
  game-joined historical archive with snapshots from 2022-05-21 demonstrably exists. Whether market
  features may enter the candidate universe is not this node's decision. `P2B_MARKET_ODDS_ELIGIBILITY`
  is recorded as `RUNNING` in `GRAPH_STATE.json` and is the node contracted to adjudicate it. **This
  node constructed, evaluated, proposed and admitted no odds-derived feature.**
* **The packet's separate objection — that a market feature changes what the model IS**, from
  predicting possessions to predicting the market (`EVIDENCE_PACKET_V2.json:569` (the `note` field)). Restated,
  **left OPEN**.
* Note the direction of the qualification P29 attaches (X3/X2, `REPORT.md:344-348`): market-odds
  features genuinely are unavailable *on this branch* — "but for a reproducibility reason, not the
  capture-window reason the packet gives." Both halves must travel together.

---

## 7. What I could not establish

* **Whether the historical odds snapshots carry any totals market.** `master_odds.csv` carries
  spread and price only; the 292 `data/odds_capture/historical` JSON files were **not opened** —
  they are outside this node's read scope and P29 records that it did not open them either.
* **Whether any market observation on any game could be proven to precede its own forecast cutoff.**
  This requires the odds tables, which are not on this branch and are out of scope. Unmeasured, in
  either direction.
* **How many of the 1,219 tip-time games would survive an `observed_at < tip - 90 min` screen.**
  D10 explicitly declined to measure it for the same scope reason (`REPORT.md:416-420`); it remains
  unmeasured.
* **Any real market coverage figure by season or by fold.** None exists to report. No pooled figure
  is offered in its place.
* **Whether the market premise (E1's precondition) could be evidenced.** That is P2B's question and
  the answer is not in this node's read scope.

---

## 8. Measurements — commands and results

Every figure marked **[mine]** above was produced by one of these, run on this branch at HEAD of
`player-model-program`, read-only.

**M1 — market artifacts inside the read scope.** Byte-level regex sweep over
`experiments/player_program/` (excluding `SEALED_RESULTS/`, which was not read) for
`closing_line|over_price|under_price|sportsbook|bookmaker|american_odds|decimal_odds|vig|no_vig|implied_prob|edge_vs_line|clv`,
with a **positive control** in the same pass (`REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS`).

```
python  # os.walk over experiments/player_program, re.findall on raw bytes
files scanned 590   positive-control files containing the primary-target token: 117
bookmaker    2  -> O14 REPORT.md, P29 MEASUREMENTS.json          (prose/measurement about odds, not odds)
sportsbook   3  -> PROJECT_UPDATE_2026-08-04.md, ROADMAP_EXTRACTION.{json,md}   (prose)
edge_vs_line 12 -> U10 fixtures/schema/tests only                 (synthetic)
over_price   12 -> U10 fixtures/build_fixtures.py only            (synthetic)
under_price  12 -> U10 fixtures/build_fixtures.py only            (synthetic)
clv          15 -> PROJECT_UPDATE (Appendix F), O12, DOCUMENT_INDEX_CORRECTION, + parquet substring
vig           3 -> possessions parquet substrings only
```

The control fired on 117 files, so the sweep reads bytes correctly; the negative is a measured
negative, not a failed search. The `clv`/`vig` parquet hits are substring coincidences inside
compressed columnar bytes, not market columns. **No artifact under `experiments/player_program/`
contains a real market price, line or closing line.**

**M2 — U10 market blocks are synthetic.**

```
python  # json.load over product_lane/U10_PREDICTION_API_SCHEMA/fixtures/responses/*.json
fixture files 7 · market blocks 21 · available:true 12 · books {'FIXTURE_BOOK'}
all subject ids FIXTURE-prefixed: True
```

**M3 — D10 ledger verdict counts, recomputed from the bytes.**

```
python  # json.load of data_lane/D10_FIELD_AVAILABILITY_LEDGER/FINDINGS.json, Counter over verdicts
CUTOFF_UNPROVEN 37 · ABSENT 7 · CUTOFF_VALID 5 · CUTOFF_INVALID 3
```
Recomputed count agrees with the ledger's own `verdict_counts` block. Carries the D10-FAILED caveat
of section 3.2.

**M4 — node states, read from `orchestration/GRAPH_STATE.json`.**

```
P2B_MARKET_ODDS_ELIGIBILITY   RUNNING
F14_DECISION_TIME_MARKET_COMPARISON RUNNING
P29_TIP_TIME_AND_COVERAGE_AUDIT  PASSED
D11_LIVE_INFORMATION_CAPTURE     PASSED
G04_PROGRAM_ROADMAP_EXTRACTION   PASSED
D10_FIELD_AVAILABILITY_LEDGER    FAILED
```

---

## 9. Contradictions found

* **X-F14-1 — the packet's market row mixes an observation span with an event-date span** (D11 C1,
  restated, not re-derived: the odds row ends two days after the machine clock at D11's writing).
  Frozen; not edited.
* **X-F14-2 — the stated ground for excluding the market family is contradicted by an archive that
  exists** (P29 SC1 / X2, restated). Frozen; not edited; adjudication belongs to P2B.
* **X-F14-3 — the product lane specifies a market comparison the science lane has no estimand for.**
  `U10` freezes a response shape with `line` and `edge_vs_line` and an invariant governing their
  absence, while the program record defers the comparison entirely (E1) and forbids the two
  statistics an edge would be scored with (E2, E3). This is not a byte-level contradiction — U10 is
  explicit that its market blocks are fixtures and that market capture is not a projection
  dependency — but the shape is registered and the target is not, which is precisely the pattern
  G04 catalogued. Recorded so that the shape is never mistaken for a commitment.

---

*Ends. No git command was run. No frozen artifact was edited. Nothing was written outside*
*`experiments/player_program/future_research/F14_DECISION_TIME_MARKET_COMPARISON/`.*
