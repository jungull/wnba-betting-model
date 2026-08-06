# F14_DECISION_TIME_MARKET_COMPARISON — REPORT

**Node:** `F14_DECISION_TIME_MARKET_COMPARISON` · **Lane:** future_research · read-only research scout
· **Branch:** `player-model-program` · **Written:** 2026-08-04

## Epistemic status of this output

> DIAGNOSTIC AND TARGET-CONTRACT DRAFT ONLY. Discovery work being unblocked is NOT authorisation to
> fit. Fitting requires a target contract, a matched K0, cutoff-valid evidence, a preregistration
> and an independent gate review.

The substantive deliverable is `TARGET_CONTRACT_DRAFT.md` in this directory. This report records
what was measured, what could not be established, and the contradictions found. It does not repeat
the draft.

## 1. Headline

**The estimand is `NOT_DERIVABLE_FROM_DOCUMENTATION`.** The program record contains one deferral
line for this track (`PROJECT_UPDATE_2026-08-04.md:284-285`), two negative boundary constraints
(`:323` no ROI optimisation; `:638` CLV recorded as an unresolved conflict) and one finding that
contradicts the motivating premise (`:636`). It contains no target statistic, no unit and no
denominator. None was invented.

Beyond "not documented", the draft records that an estimand is not currently *constructible*: the
settled primary target is `REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS`, no market prices team
offensive possessions, the historical archive carries spread and price only with **no totals
column** (P29 `REPORT.md:282`), and no mapping from a regulation-equivalent possession projection to
any priced quantity exists in the record.

## 2. What I measured

| id | measurement | result |
|---|---|---|
| M1 | byte-level regex sweep of `experiments/player_program/` (excl. `SEALED_RESULTS/`, unread) for eleven market tokens, with `REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS` as a positive control in the same pass | 590 files scanned; control fired on 117 files; **no real market price, line or closing line in scope**. All `over_price`/`under_price`/`edge_vs_line` hits are U10 fixtures; `sportsbook`/`bookmaker` hits are prose; `clv`/`vig` parquet hits are substring coincidences |
| M2 | `json.load` over the 7 U10 golden fixture responses, counting `market` blocks | 21 market blocks, 12 `available: true`, every one `book = "FIXTURE_BOOK"`, all subject ids `FIXTURE_`-prefixed — **entirely synthetic** |
| M3 | `Counter` over `verdict` in D10 `FINDINGS.json` | `CUTOFF_UNPROVEN` 37, `ABSENT` 7, `CUTOFF_VALID` 5, `CUTOFF_INVALID` 3; agrees with the ledger's own `verdict_counts` |
| M4 | node states read from `orchestration/GRAPH_STATE.json` | `P2B_MARKET_ODDS_ELIGIBILITY` **RUNNING**; `P29` PASSED; `D11` PASSED; `G04` PASSED; `D10` **FAILED** |

M1's positive control is the point: this program has already produced one manufactured negative
from a search that silently failed on the bytes it was searching. The control fired 117 times in
the same pass over the same bytes, so the market negative is measured, not assumed.

Every other figure in the draft is quoted from a frozen in-scope receipt with its owning node
named, in the manner D11 used: someone else's measurement, attributed.

## 3. What I could not establish

* Whether the 292 `data/odds_capture/historical` JSON snapshots carry a totals market. Out of read
  scope; not opened. P29 records that it did not open them either.
* Whether any market observation on any game could be proven to precede its own forecast cutoff.
  Requires the odds tables, which are not on this branch and are out of scope. Unmeasured in either
  direction — this is not a claim that they could not be.
* How many of the 1,219 tip-time games would survive an `observed_at < tip - 90 min` screen. D10
  declined it for the same scope reason (`REPORT.md:416-420`).
* Any real market coverage figure by season or by fold. None exists to report; no pooled figure is
  offered in its place.

## 4. Contradictions

* **X-F14-1** — the frozen availability table's market row mixes an observation span with an
  event-date span (D11 C1, `REPORT.md:126-135`). Frozen; restated, not re-derived, not edited.
* **X-F14-2** — the stated ground for excluding the market family is contradicted by an archive
  that demonstrably exists (P29 SC1/X2). Frozen; adjudication belongs to `P2B`, which is RUNNING.
* **X-F14-3** — `U10_PREDICTION_API_SCHEMA` freezes a market-comparison *response shape*
  (`line`, `edge_vs_line`, invariant I9) for a comparison the science lane has deferred entirely
  and whose two obvious scoring statistics are barred. Not a byte-level contradiction — U10 is
  explicit that its market blocks are fixtures and that market capture is not a projection
  dependency — but the shape is registered and the target is not. Recorded so the shape is never
  mistaken for a commitment.

## 5. Stop conditions

**No new stop condition is raised.** One is restated as open and not resolved here: P29's **SC1**
(Severity A — candidate universe / cutoff-valid feature set), on whether market features may enter
the candidate universe given that a historical odds archive with snapshots from 2022-05-21 exists.
`P2B_MARKET_ODDS_ELIGIBILITY` is the node contracted to adjudicate it and is RUNNING. The packet's
separate objection — that a market feature changes what the model IS — is restated and left OPEN.

This node constructed, evaluated, proposed and admitted **no** odds-derived feature.

## 6. Caveat attached to the D10 citations

`GRAPH_STATE.json` records `D10_FIELD_AVAILABILITY_LEDGER` as FAILED; `GRAPH_EVENTS.jsonl` gives the
reason as a manufactured negative in the coaching family, with the note "Ledger retained; the other
48 fields are not impeached by this family." The fields cited in the draft lie outside the impeached
family, but they are cited as a **provisional** ledger, not as settled evidence.

## 7. Boundaries observed

No fit, no model code, no comparative historical performance inspected. Nothing under
`experiments/player_program/stage2b/SEALED_RESULTS/` was read. No git command was run. No frozen
artifact was edited. Nothing was written outside
`experiments/player_program/future_research/F14_DECISION_TIME_MARKET_COMPARISON/`.

*Ends.*
