# P2B_MARKET_ODDS_ELIGIBILITY — adjudicating the market-odds family

**Epistemic status (verbatim, as required):**

> VERIFIED_READ_ONLY_DERIVATION. Establishes what historical odds evidence EXISTS and whether it is
> cutoff-valid. It does NOT decide whether a market feature belongs in a possession model -- that is
> a separate question about what the model is, and this node raises it rather than settling it.

**Outcome in one line.** The packet's stated ground is false — twice over, in both directions — and
the family is still inadmissible. The correction is to the packet's *reason*, not to its *outcome*.
This node admits nothing and recommends admitting nothing.

## 0. Read scope disclosure, stated explicitly

The odds archives do not exist on this branch. They live only in the repository ROOT worktree,
`C:/Users/jgallagher/wnba-betting-model`, branch `data-refresh-2026`. My brief permitted and
expected reading them **read-only**, and that is what I did: `pandas.read_csv`, `os.path.getmtime`,
`glob`, and `git check-ignore`. **No file in the root worktree was created, modified or deleted, and
no git command that mutates anything was run.** Every artifact I wrote is inside
`experiments/player_program/stage2b/P2B_MARKET_ODDS_ELIGIBILITY/`.

Reproduce everything with:

```
python experiments/player_program/stage2b/P2B_MARKET_ODDS_ELIGIBILITY/run_measurements.py
python experiments/player_program/stage2b/P2B_MARKET_ODDS_ELIGIBILITY/build_findings.py
```

The first writes `MEASUREMENTS.json`; the second derives `FINDINGS.json` from it without retyping
any number.

## 1. The archive is real, and the 2022-05-21 figure reproduces exactly

Three game-joined odds tables exist, all untracked (`.gitignore:2` `data/drive_masters/`,
`.gitignore:5` `data/odds_capture/`):

| archive | rows | games | `odds_snapshot_timestamp` span (UTC) |
|---|---|---|---|
| `data/drive_masters/master_odds.csv` | 20,004 | 813 | 2022-05-21T17:55:00Z → 2025-07-03T22:55:37Z |
| `data/odds_capture/master_odds_extension.csv` | 27,734 | 406 | 2025-07-05T14:55:37Z → 2026-07-30T16:00:01Z |
| `data/odds_capture/master_odds_extension_other_markets.csv` | 53,178 | 406 | 2025-07-05T14:55:37Z → 2026-07-30T16:00:01Z |

**The 2022-05-21 figure is REPRODUCED, not relayed.** I recomputed it from the bytes: the earliest
snapshot instant in any archive is `2022-05-21T17:55:00Z`, in `master_odds.csv`. It reproduces to the
second.

I attach a material qualification to it immediately, because the figure is the single most
misleading number in this whole file: **it is a vendor-asserted observation instant, not a witnessed
capture.** Section 3 shows why that distinction decides the node.

## 2. `tip_times.csv` provenance: chain closed, and the timestamp is destroyed at the boundary

`data/reference/tip_times.csv` is built by `data/reference/collect_bios.py::phase_tips` (lines
241–291), which reads both parent tables via `load_odds` (line 231).

The chain closes on exact per-season counts — child equals parent in every cell:

| season / source | `tip_times.csv` | parent archive |
|---|---|---|
| 2022 drive_master | 180 | 180 |
| 2023 drive_master | 259 | 259 |
| 2024 drive_master | 261 | 261 |
| 2025 drive_master | 113 | 113 |
| 2025 extension | 197 | 197 |
| 2026 extension | 209 | 209 |

**Does a per-snapshot observation timestamp survive?** This is the question the brief says decides
everything, and the answer differs by stage:

* **In the parent archive: YES.** `odds_snapshot_timestamp` is present on every row with zero nulls,
  alongside `odds_previous_timestamp` and `odds_next_timestamp`. This is genuinely *better* than the
  tip pipeline D10 indicted.
* **In `tip_times.csv`: NO.** The written column list (lines 280–282) omits it entirely. Line 250
  sorts by snapshot and line 253 keeps `commence_utc=("commence_utc", "last")` — the latest
  snapshot's value only. D10's `CUTOFF_UNPROVEN` verdict on the three tip fields is **independently
  reconfirmed here, and not upgraded.**

So the D10 defect is confirmed present, exactly as the brief anticipated. But it is not the binding
constraint, because the parent *does* retain the timestamp. The binding constraint is section 3.

### 2a. A correction: `n_snapshots` in `tip_times.csv` is a row count

Line 255 reads `n_snapshots=("snap", "size")`. `size` counts **rows**, not distinct snapshots. Audited
against the parent over all 813 `drive_master` games:

* recorded `n_snapshots` equals the parent **row count** in **813 of 813** games;
* recorded `n_snapshots` equals the true **distinct-snapshot count** in **0 of 813** games;
* recorded min/median/max = 10 / 24 / 32; true distinct min/median/max = **1 / 1 / 1**.

The 24 is the bookmaker × team fan-out (22 bookmakers), not a capture time series. P29 relayed this
field's min/median/max as "10 / 30 / 146" without recomputing it against the parent, and it reads as
evidence of dense capture. It is not. Every game in the 2022–2025 archive has exactly **one** snapshot.

## 3. The decisive finding: everything before 2026-07-30 is a retrospective harvest

Four independent lines of evidence, any one of which would be suggestive; together they are conclusive.

**E1 — one snapshot per game.** All 813 games in `master_odds.csv` carry exactly one distinct
snapshot instant (min = median = max = 1). A capture stream does not produce that.

**E2 — a targeted offset on a subsampled grid.** Harvested snapshots sit *only* on minute `:25` and
`:55`, at a modal lead of **64–65 minutes before commence** (15,124 rows at 64 min, 4,468 at 65).
Meanwhile `odds_previous_timestamp`/`odds_next_timestamp` show the vendor's true grid is **5
minutes**. So the harvest *selected* one grid point per game at approximately tip-minus-one-hour out
of a 5-minute lattice. That is a query pattern, not a stream.

**E3 — a single-burst download, and this is the clincher.** The 292 files in
`data/odds_capture/historical/` are named for event dates spanning `2025-07-05` → `2026-07-29`. Their
filesystem mtimes span **2026-07-30 15:43:40Z → 15:53:11Z** — a 571-second burst, all on one day.
Every "historical" snapshot was downloaded in under ten minutes, up to a year after the event it
describes.

**E4 — the contemporaneous stream, by contrast, is unmistakable.** The 71 `live_*.json` files have
mtimes tracking their filename stamps to a **median of 1.6 seconds** (max 14.5s). That is what a real
witnessed capture looks like. It begins **2026-07-30T15:01:32Z**.

**Verdict.** A surviving vendor timestamp is a *claim* about a past instant, not a *witness* to it.
The governing rule in my brief is that a single retrospective pull is permanently `CUTOFF_UNPROVEN`
no matter how far back its event dates reach. That rule applies here in full. **Every market field on
every row before 2026-07-30T15:01:32Z is CUTOFF_UNPROVEN.** The archive's retention of
`odds_snapshot_timestamp` improves its documentation; it does not convert a harvest into a capture.

## 4. Where the packet's number actually came from

`data/odds_capture/capture_log.csv` is the compiled live stream: 20,112 rows, `snapshot_utc` spanning
`20260730T150132Z` → `20260804T220003Z`, and `commence_time` spanning **`2026-07-31T00:02:55Z` →
`2026-08-06T23:00:00Z`**.

The packet states coverage as **"2026-07-31 .. 2026-08-06 only"**. That is the **commence-time** span
— the dates of the *games quoted* — reported as if it were the capture span. The capture span is
2026-07-30 → 2026-08-04.

So the packet's sentence is wrong in both directions at once:

* it is **too late** at the front — contemporaneous capture begins 2026-07-30T15:01:32Z, a day earlier;
* it is **far too narrow** overall — a retrospective archive reaches game dates back to 2022-05-21.

Two frozen statements are therefore false as written:
`.cutoff_valid_availability_table_CORRECTED.unavailable_or_insufficient[2].note` and
`.statement_classification.UNCHANGED[9]` ("market odds unavailability (capture begins 2026-07-31)").
**I did not edit the packet.** The correction is raised as P2B-SC1.

## 5. Coverage by season and by fold — never pooled

Universe as loaded via `possession_features.load_universe()`: **2,982 team-game rows / 1,491 game
clusters**, seasons 2021–2026, 2021-05-15 → 2026-07-31. Folds from
`possession_features.chronological_folds()`.

Every join was proved non-empty before use (`prove_join`), because this program has already produced
one manufactured negative from a silent dtype mismatch: universe ∩ spread = 1,219 games;
universe ∩ totals = 406; universe ∩ tip_times = 1,219. All non-empty.

**Game coverage by season:**

| season | games | spread | rate | total | rate |
|---|---|---|---|---|---|
| 2021 | 205 | 0 | 0.000 | 0 | 0.000 |
| 2022 | 239 | 180 | 0.753 | 0 | 0.000 |
| 2023 | 260 | 259 | 0.996 | 0 | 0.000 |
| 2024 | 262 | 261 | 0.996 | 0 | 0.000 |
| 2025 | 310 | 310 | 1.000 | 197 | 0.635 |
| 2026 | 215 | 209 | 0.972 | 209 | 0.972 |

**Coverage by fold** (train rows are what decide estimability):

| fold | cutoff | spread train | spread test | total train | total test |
|---|---|---|---|---|---|
| `train_lt_2022` | 2022-05-06 | **0 / 205 (ALL MISSING)** | 180 / 239 | **0 / 205 (ALL MISSING)** | **0 / 239 (ALL MISSING)** |
| `train_lt_2023` | 2023-05-19 | 180 / 444 | 259 / 260 | **0 / 444 (ALL MISSING)** | **0 / 260 (ALL MISSING)** |
| `train_lt_2024` | 2024-05-14 | 439 / 704 | 261 / 262 | **0 / 704 (ALL MISSING)** | **0 / 262 (ALL MISSING)** |
| `train_lt_2025` | 2025-05-16 | 700 / 966 | 310 / 310 | **0 / 966 (ALL MISSING)** | 197 / 310 |
| `train_lt_2026` | 2026-05-08 | 1010 / 1276 | 209 / 215 | 197 / 1276 (0.154) | 209 / 215 |

The spread family reproduces the tip family's failure exactly: **zero variance across all 205
training rows of `train_lt_2022`**, the earliest fold. The totals family is worse: **all-missing
training rows in four of five folds.**

`experiments/player_program/GATE_INVOCATION_CONTRACT.md:129-130` (§4, *Pooled-healthy /
fold-degenerate*) is unambiguous: *"A feature that is healthy pooled but degenerate in a fold must
FAIL for that fold, or be governed by a fallback frozen and registered before any result is
visible."* Line 130 adds: *"There is no third option."* Line 133 forbids rescuing a fold for being
"early", "small", or "a warm-up". **No fallback governing market coverage is registered**, and
registering one now — after these coverage figures are visible — would violate the same section's
requirement that results not be visible at registration. Coverage in later seasons is availability,
not eligibility.

## 6. Two corrections to P29, in opposite directions

P29 reported: *"Markets present: `odds_spread` and `odds_price`. **No totals column.**"*

* **P29 was right about the two files it opened** and right that the 2022-reaching archive carries no
  totals.
* **P29 was wrong about the family.** A totals market *does* exist — 27,820 rows in
  `master_odds_extension_other_markets.csv`, a file P29 did not open, alongside 25,358 h2h rows.

The correction matters because it cuts *against* admission, not for it. The totals market covers
**2025 (197 games) and 2026 (209 games) only**. The market total is precisely the member the packet's
own candidate entry names — *"market total / pace-implied market expectation with history"*. So
discovering an archive that reaches 2022-05-21 does **not** supply history for the feature the packet
was actually contemplating. The 2022-reaching archive is spread and price only.

## 7. In-play contamination — a live prohibited-surrogate risk

`master_odds.csv` is clean on this: **0** rows have a snapshot after commence. The extensions are not:

* `master_odds_extension.csv`: **232** rows post-commence, earliest lead **−172.6 minutes**;
* `master_odds_extension_other_markets.csv`: **338** rows post-commence, same −172.6 minute floor.

An in-play odds value is an approximate **same-game surrogate for the realised game**, which the
settled target prohibits from the prediction path. The rule already in use — `phase_tips`'s "take the
last snapshot" — would select exactly those rows. Any future market feature must filter
`snapshot < commence` at the call site. `collect_bios.py::phase_tips` does not.

## 8. The separate objection — STATED, AND LEFT OPEN

The packet carries an objection entirely independent of everything above:

> `.unavailable_but_potentially_valuable.candidates[4].caution` — *"a market feature changes what the
> model is: it would no longer be a pure pace projection"*

> `.cutoff_valid_availability_table_CORRECTED.unavailable_or_insufficient[2].note` — *"... also a
> market feature, which raises separate questions about what is being learned"*

**This node does not resolve it, and nothing in this report should be cited as resolving it.**

I want to be precise about why it must stay open. Every finding in sections 1–7 is an *evidentiary*
finding: about capture witness, coverage, degeneracy, contamination. Suppose all of them were
repaired — a perfectly witnessed, fully covered, contamination-free market archive reaching 2021.
**The objection would survive untouched.** It is a question about the identity and purpose of the
model — whether a system that consumes the market's own consensus is still predicting possessions or
has become a system for predicting the market — and it is a question about what the program is *for*,
not about what the data *is*. It must be decided by the program before any market feature is
considered, and it must not be treated as discharged by this node's evidence.

## 9. Stop conditions

The trigger I was given: *if the evidence would ADMIT a family the frozen packet excluded, HALT and
raise.*

**Not tripped by admission.** My evidence does not admit the family. It falsifies the packet's stated
reason while sustaining the packet's outcome on stronger grounds. The candidate universe is unchanged
by this node.

Three things are raised and **not** discharged:

* **P2B-SC1 (A) — evidence-packet correction required.** Two frozen packet statements are factually
  false (section 4). A frozen artifact may not be edited by this node and was not. The correction
  belongs to whoever owns the packet.
* **P2B-SC2 (A) — P29's SC1 remains undischarged.** This node supplies the evidence P29 lacked and
  recommends **no** admission, but the candidate-universe decision and the section-8 objection belong
  to the program.
* **P2B-SC3 (A) — fold-degeneracy blindness reconfirmed on a second family.** `market_total_points`
  is 100% missing on training rows in 4 of 5 folds; `market_spread` in 1 of 5. A pooled-only gate
  check would not see this. This is P29's SC2 mechanism, reproduced independently.

## 10. What I could NOT establish

1. **Whether the vendor's asserted `odds_snapshot_timestamp` values are accurate.** They are
   internally consistent with a 5-minute grid, but no independent witness exists in this repository
   and none can be constructed from it. This is unfalsifiable from inside the repo and should stay
   that way in the record.
2. **Whether the 6 uncovered 2026 games (2026-07-30/31) are covered by the live stream.**
   `capture_log.csv` carries **no `game_id`** — it is keyed on team names only — so it cannot be
   joined to the contract universe without an entity-resolution step I did not perform and was not
   asked to perform.
3. **Why 2022 coverage is 180/239 (75.3%) while 2023–2025 are ≥99.6%.** The harvest's selection rule
   is not documented in any script found in either worktree.
4. **The identity of the code that produced `master_odds.csv`.** Its schema is a historical odds API
   response shape. `wnba-odds-aggregator/scripts/historical_backfill.py` is a 54-line stub whose
   scraping logic is an unimplemented `TODO` (line 26); the `wnba_odds_system` scripts target a
   different (oddsportal) source and a different schema. The producing code is absent from both
   worktrees, so the archive is not reproducible from either.
5. **Any statement about predictive value.** No fit was run, none is permitted, and nothing under
   `stage2b/SEALED_RESULTS/` was read.

## 11. Contradictions found

* **X1 — packet vs bytes (section 4).** `capture begins 2026-07-31` is a game date reported as a
  capture date; true contemporaneous capture begins 2026-07-30T15:01:32Z and a retrospective archive
  reaches 2022-05-21. Frozen; reported, not edited.
* **X2 — P29 vs bytes (section 6).** "No totals column" is false of the family; a totals market
  exists in a file P29 did not open. The correction nonetheless strengthens exclusion.
* **X3 — `tip_times.csv` self-description vs its parent (section 2a).** `n_snapshots` counts rows,
  not snapshots; true distinct snapshots per game is 1, not 24, and P29 relayed the field at face value.
* **X4 — D10 ledger gap.** The market-odds family has **no entry** in
  `D10_FIELD_AVAILABILITY_LEDGER`; the only odds-descended entries are the three tip fields. The
  family was excluded by packet prose without ever entering the ledger that governs availability
  verdicts.

## 12. Bottom line

The market-odds family is **NOT ADMITTED**. It is `CUTOFF_UNPROVEN` on every row before
2026-07-30T15:01:32Z because all of it is a retrospective harvest; it is fold-degenerate on the
folds that decide; its only pace-relevant member has no history before 2025-07-05; its extension
carries in-play rows that the incumbent snapshot rule would select; and the question of whether it
belongs in a possession model at all remains **open and unaddressed by this node**.

The packet reached the right answer for a reason that does not survive contact with the bytes. That
is worth fixing on its own, because the next node to rely on the stated reason will be relying on
something false.
