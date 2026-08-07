<!-- COORDINATOR HEADER -- materialized, not authored, by the on-duty coordinator -->
# S37_IMPLEMENTATION_AUDIT -- REPORT

**Materialized by the coordinator 2026-08-07** from `S37_REPORT_BODY.md`, sha256 `de28ec24de55bb3f28c21afc2e05f611eb4acbc2f5ec6a59750f3e30d164092b`.
Nothing below this header was edited.

## VERDICT: FAIL -- 18 findings (9 Severity A, 5 B, 4 C). STOP CONDITION TRIPPED (A9).

**This node succeeded by failing.** It was dispatched to find exactly this, and it did so before a
single fit ran. Had it passed the implementation through, the sealed run would have produced numbers
that looked clean and rested on: a lambda rule that is not the carded rule, an estimation objective
absent from the fit path, a ridge penalty never applied, a bootstrap that does not exist, no pooled
surface, and **zero of 34 kill diagnostics actually computed**.

## Coordinator verification -- the two most consequential findings re-run independently

**A7 -- the leakage guard does not detect score leakage. CONFIRMED.** The coordinator re-ran
`measurements/m4_p22.py`. A design containing the current game's **settled final margin**,
`3xtotal-17.5`, and the current game's **home points** returns `passed=True` with **zero blocking
findings**. Correlations against every duration quantity are 0.033-0.038, so nothing trips. The
same unmodified guard given a score prohibited basis returns `passed=False` with **12 blocking
findings naming exactly those three columns**. The battery is sound; it was aimed at duration
quantities and no score prohibited basis exists in the program. The fix belongs at the **call
site** -- the frozen guard may not be edited (GRAPH_POLICY section 3).

**A1 -- the lambda rule flips an arm-killing kill. CONFIRMED.** The coordinator re-ran
`measurements/m7_lambda.py`: **9 of 20 element-by-fold selections differ** between the coded rule
(MAE) and the carded rule (squared error). SC01::E3 reaches the grid maximum in **5 of 5 folds as
coded** versus **1 of 5 as carded**, and SC01 kill 2 fires on "lambda at grid maximum in >=4 of 5
folds" with arm-killing scope. Because lambda sets SC01's rating fit, the treatment column values
themselves differ.

## A9 is a HALT, not a finding to fix

S30 section 8 requires that an `UNPROVEN` field consumed by any arm first be promoted by a
receipted cutoff-validity measurement in this audit. The ledger's verdict counts are
`{CUTOFF_UNPROVEN: 37, ABSENT: 7, CUTOFF_VALID: 5, CUTOFF_INVALID: 3}`, the frozen cards register
**one** such item, and the audit traced **13 ledger-UNPROVEN fields consumed by retained arms, 12
carrying no measurement** -- including schedule identity columns, the back-to-back and 3-in-4
classes feeding SC06, the timezone shift that *is* SC06's tz term, the possession prior feeding
SC08's z1, and the prior box aggregates underneath every lagged construction in the slate.

**Ruling in any direction changes the cutoff-valid feature set, which is a USER surface under
GRAPH_POLICY section 6.** The coordinator has not ruled and will not. The decision packet is
`D058_S37_A9_CUTOFF_VALID_SET`.

## On the routed contradiction: the audit overturned the implementation's ground

S36 raised F3 and the audit ruled the implementation's *reading* correct while finding its
*stated ground* wrong. `composite_p_home` is a null-granted **anchor column not in the prediction
path**, the cards supply the missing-value consequence explicitly, and the A4 receipt **reads**
`p_home` as a comparand -- positive evidence for the anchor reading. The 188 NaN figure is correct
and re-measured, but all 188 sit in 2021, a training season in all five folds, so "unimplementable
as frozen" is overstated and is not the operative ground. **Consequence: the mean-agreement receipt
is live and has no emitter (B2).** This is what independent audit is for -- it accepted neither the
implementer's conclusion nor its reasoning without re-deriving both.

---

# S37_IMPLEMENTATION_AUDIT — independent implementation audit of every score arm before any fit

**Epistemic status (verbatim, as the node contract requires):**

> IMPLEMENTATION AUDIT. Card-vs-code fidelity; cutoff validity receipts; kill-diagnostic presence verified.

**Verdict: FAIL.** 9 Severity A findings, 5 Severity B, 4 Severity C. One Severity A is a **stop
condition, halted and raised rather than resolved**. Fitting must not be authorised.

**Root, stated explicitly:**
`C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program`.
Every measurement below ran against that worktree. Its `data/masters/master_team.parquet` hashes to
`ad79ce5cdda7e058ba24be45243037252e3795a3e9f0c18cc41b3f12f3c38528`, which is the pin. The second
worktree at `C:\Users\jgallagher\wnba-betting-model` (branch `data-refresh-2026`) was never read.

---

## 0. How independence was maintained, and one disclosure

This context received the S37 prompt only — no S36 prompt, no implementer narrative, no claim about
what S36 believes it discharged. The order of work was deliberate: the **standard was re-derived
before any implementation file was opened**. All seventeen `card_sha256` values and all eleven
`arm_block_sha256` values were recomputed from `SPEC_V2.json` under the cycle-1 P35 canonicalisation
and matched; so did the two aggregate digests `task_cards_sha256` and `arm_blocks_sha256`; so did the
`arms[i] → arm_id` index mapping. Only then was code read.

`S36_IMPLEMENT_ARMS/REPORT.md` and `S36_IMPLEMENT_ARMS/S36_REPORT_BODY.md` were **never opened**.
`RUNNER_MANIFEST.json` was never opened as a document.

**Disclosure, so it is not discovered later.** `build_manifest.py` was read *as code* — it is the
node's build entry point and the only file that shows the intended order of operations — and that
file embeds the implementer's own `findings_raised_to_S37` list, F1–F6. Every item this audit relies
on that overlaps with it was re-derived afterwards from the pinned bytes: the 188 structural NaN, the
SC12 652-vs-649 habitat split, and the SC12 quantile distribution. The numbers reported here come
from this node's own runs.

Nothing under `stage2b/SEALED_RESULTS` or `stage3_score/SEALED_RESULTS` was opened. One
repository-wide grep for the literal string `postgame_surrogate_guard` returned paths under
`stage2b/SEALED_RESULTS` in its *file list*; no such file was read and no later search touched those
trees.

Every number below came from a script in `measurements/`. Nothing is asserted that was not run.

---

## 1. What reproduced exactly

Before the failures, the things that held — because a FAIL that does not say what was solid is not
usable.

**The frozen bytes.** `SPEC_V2.json` hashes to `6402fc11…e945`. 17/17 element cards and 11/11 arm
blocks recompute. `task_cards_sha256` = `aa759da7…6508` and `arm_blocks_sha256` = `a50fa064…df12`
recompute. The freeze's own claim that no field was transcribed, so no field can drift, holds.

**The universe.** Re-derived independently: 1,491 game clusters over 2,982 team-game rows;
per-season 205 / 239 / 260 / 262 / 310 / 215; zero settled ties, so E3 is well-defined; 26
composite-uncovered clusters taking the `league_average_v1` fallback. The pre-build game_id digest
`e0083be22b32ddf5feaf55d010b1d22eb25ec75774546742eb90d4e3b3c4be1d` reproduces. The O2 fail-closed
mechanism is real, not decorative: `build_universe()` refuses to return a frame unless that receipt
exists and the built id set re-derives to it.

**All four byte pins, and all four join-key digests.** `pred_margin` (1,465 values, 0 NaN),
`pred_total` (1,465 / 0), `p_home` (1,465 / **188**), `projected_team_off_possessions` (2,990 / 8) —
every column digest matches, and so does every `join_key_sha256`. That closes the one documented gap
S35 carried forward: the composite-key convention is *components joined within a row by U+001E RECORD
SEPARATOR, rows joined by U+001F UNIT SEPARATOR*. No digest was changed to make it reproduce; this
node confirmed the frozen values independently.

**O6's S37 obligation, discharged.** S35 binds this node to re-run `M_A1_GAME_DATE_CUTOFF_V2`
byte-for-byte. `MEASURE_A1_DATE_WITNESS.py` was copied to a scratchpad with **only its output
directory changed** — the frozen S33R directory was not written to — and re-run. The resulting
receipt is canonically identical to the frozen one
(`00c85d01fcbb3770eca6d0b15c5121da93d600cee695be2aa3c01e6ff88482da` both sides). The carded figures
re-derive: **10** release-order displaced clusters, **6** clusters without a second-endpoint witness,
1,485 clusters witnessed by the independent shotchart endpoint, **0** cross-endpoint date
disagreements.

**Layer-A parity, structurally.** The interface is the best thing in this node. A module hands back
*one column dictionary and two column-name lists*, and `validate_design` reconstructs the K0 from the
arm and refuses any pair where `arm_cols` minus `treatment_cols` is not exactly `k0_cols`, in order.
Two separately built designs can drift; two views of one dictionary cannot. Sixteen elements × five
folds pass it, plus the intercept rule, the non-finite-value refusal, the indicator check, and a
column-name-set stability check across folds that allows a strict subset only under a declared
deactivation.

**Every carded kill stratum re-derives.** `verify_carded_strata.py` rebuilds each kill's subset from
the node's own feature code and every census matches the card: SC01 472 pooled (75/76/74/81/92 by
test season, 74 in 2021) with the rejected `min ≤ 12` reading at 516; SC02 249; SC03 399; SC12 652.
This node independently re-derived SC12's: 652 pooled with the support floor *not* applied
(87/97/118/102/141/107, median 1.703982, p90 4.705777, max 13.0) and 649 with it applied
(85/97/118/102/140/107, median 1.699105, p90 4.679514, max 12.65564). Both readings leave both SC12
kills checkable. The kills' **subsets** are correctly defined and non-empty. That is not the same as
the kills' **diagnostics** existing — see §4.

---

## 2. Criterion 2 — CUTOFF_UNPROVEN receipts. FAILED, and it is a stop condition.

The governing sentence is `S30 CYCLE2_TARGET_CONTRACT.md` §8:

> F13's cutoff-valid field inventory (5 CUTOFF_VALID, 37 CUTOFF_UNPROVEN at its writing) binds: an
> UNPROVEN field used by any arm must first be promoted by a receipted cutoff-validity measurement in
> the S37 audit — subject to the market-field exclusion above.

The inventory is `data_lane/D10_FIELD_AVAILABILITY_LEDGER/FINDINGS.json`. Its `verdict_counts` are
`{CUTOFF_UNPROVEN: 37, ABSENT: 7, CUTOFF_VALID: 5, CUTOFF_INVALID: 3}` — exactly the contract's
citation. Its rule is unambiguous: *"a field is CUTOFF_VALID for a row only if a per-row source
observation timestamp exists and is ≤ that row's forecast_cutoff. No timestamp means CUTOFF_UNPROVEN.
Structural plausibility is never a substitute."*

The frozen cards register **one** CUTOFF_UNPROVEN item — `master_team.game_date` — and SC06's card
says so in terms: *"the card's one CUTOFF_UNPROVEN item"*. That one has its measurement, and this node
re-ran it byte-for-byte.

Tracing the arms' consumed columns back to the ledger, **thirteen** ledger-UNPROVEN fields are
consumed by retained arms. Twelve of them carry no receipted cutoff-validity measurement:

| ledger # | field | who consumes it | measurement |
|---|---|---|---|
| 0 | `sched.game_id` | every arm — join key, and the `(game_date, game_id)` sequencing of every EWMA | none |
| 1 | `sched.game_date` | SC06 directly; all lagged sequencing | **M_A1 (present)** |
| 2 | `sched.season` | fold assignment on all 17 elements; SC06 era; SC01 two-season window; SC02/SC03/SC10 season clocks | none |
| 3 | `sched.season_type` | carried into the game frame by `build_universe` | none |
| 4 | `sched.is_home` | the universe definition; SC01 η; SC05 home/away split; SC06 venue | none |
| 5 | `sched.opp_team_id` | SC01 matchup ratings; SC10 orthogonalisation covariate; SC06 venue | none |
| 9 | `rest.is_back_to_back` | SC06 fatigue index, weight 1.0 | none |
| 10 | `rest.games_in_prev_7_days` (the 3-in-4 class) | SC06 fatigue index, weight 0.5 | none |
| 12 | `venue.venue_team_id` | SC06 venue attribution | none |
| 18 | `timezone.venue_iana_timezone` | SC06 tz component, weight 0.25 | none |
| 22 | `timezone.shift_from_prev_venue_hours` | SC06 `tz_crossed` **is** this quantity | none |
| 50 | `opponent.opp_pace_estimate` class (`team_possession_prior_v1.parquet`) | SC08 `z1 = z(projected_team_off_possessions)` | none |
| 51 | `opponent.prior_box_aggregates` | every lagged-outcome construction in the slate | none |

Two of the ledger's own evidence strings matter here. On the timezone table: *"The values are
time-invariant in substance, but time-invariance is an argument, not a timestamp, and this ledger does
not accept arguments in place of evidence."* On the pace artifact: *"those receipts attest
construction order, not observation time… This is the sharpest case in the ledger of the difference
between 'validated' and 'timestamped'."* The cards answer both with **classifications**
(`IMMUTABLE_REFERENCE_METADATA`, `IDENTITY_SET_EXTENSION_S34_ADJUDICATED`) and provenance prose. A
classification is not a measurement.

Separately, the five `score_baseline_rows` prediction columns (`pred_home`, `pred_away`, `pred_total`,
`pred_margin`, `p_home`) postdate the inventory entirely. They carry byte pins, the S34-adjudicated
registration, and a line-numbered provenance argument. They do not carry a cutoff-validity
measurement either. Recorded so the gap is not lost.

**There is a genuine internal tension and this audit does not pretend otherwise.** S30 §1 admits a
closed enumerated schedule-identity set "valued as-of-cutoff, never as-played". S30 §8 separately
requires a receipted measurement for any UNPROVEN field an arm uses. The six `master_team` schedule
columns sit under both. The decisive internal evidence is that **S33R itself treated §8 as binding on
a schedule column**: it commissioned and ran `M_A1_GAME_DATE_CUTOFF_V2` for `master_team.game_date`,
a member of the §1 set. If §1's admission alone discharged §8 for schedule columns, that measurement
would have been unnecessary.

**HALT.** Deciding this — in any direction — changes the cutoff-valid feature set, which S30 §11 and
this node's own stop condition make a halt-and-raise. It is raised, not resolved. Finding **A9**
lists the four specific questions the coordinator must answer.

---

## 3. Criterion 4 — is P22 fit for purpose on SCORE surrogates? MEASURED: no.

S30 §1 obliges this audit to establish the guard's applicability *before* relying on it per column,
because "its cycle-1 tests target duration/minutes surrogates". Every one of the eleven frozen arm
blocks repeats the obligation.

First, the simpler half: **S36 never invokes the guard.** A case-insensitive search for `P22`,
`postgame_surrogate`, `prohibited_basis` and `LagSpec` over the whole S36 tree returns only the
verbatim O7 obligation *text* (`obligations.py` line 129, `RUNNER_MANIFEST.json` line 587) and one
unrelated test. There is no import and no call site.

Second, the measurement (`measurements/m4_p22.py`). The P22 module supplies exactly one
prohibited-basis constructor, `realised_duration_basis()`, whose columns are `game_minutes`,
`overtime_periods`, `is_overtime`, `team_minutes` (4 / 4 / 2 / 4 distinct levels on this universe).
`feature_gate.py` hashes to `b064c2c4…f9a7`, matching the wrapper's pin, so the gate is byte-unchanged
and the `gate_bytes_changed` block cannot fire.

Two designs were audited against that basis:

* **A — clean score-lane columns** (`composite_pred_margin`, `composite_pred_total`, `fatigue_diff`,
  `form_spread_short_net`, `winsor_correction_diff`): `passed = True`, 0 blocking. No false positives.
* **B — the same, plus three deliberate current-game realized-SCORE leaks**: the current game's
  settled final margin; `3 × current-game total − 17.5`; the current game's home points.
  **`passed = True`. Zero blocking findings.**

The guard passes a design containing the game's own final margin. It has to: measured |r| between the
realized margin and every duration quantity is 0.033–0.038, no partition test can refine, no affine
map is exact, and the collinearity threshold is 0.999. The prohibited basis is simply the wrong
quantity.

The counterfactual settles what kind of defect this is. Handed an auditor-built score prohibited basis
(`realized_margin`, `realized_total`, `realized_home_pts`), the **same guard, unmodified** returned
`passed = False` with 12 blocking findings naming exactly those three leak columns and no others.

So the battery is sound and the module is incomplete. **Fitness for purpose on score surrogates
depends entirely on a score prohibited basis that does not exist anywhere in this program.** Until one
is built, byte-pinned and invoked, no per-column P22 pass may be cited as evidence about score
leakage. That is finding **A7**.

A second defect the same run exposed: declaring a column `SCHEDULE` or `DERIVED_NO_JOIN` skips the
guard's lag re-derivation layer entirely and records only the informational `schedule_fact_admitted`.
Every score-lane feature in this slate is derived-in-frame, so under any straightforward invocation
the guard's second check never runs on a single column of this slate.

### 3b. The column-grain deletion-invariance receipt, and what this node measured in its place

S30 §1 requires it, S35 authorises its emission, and O7 binds S36 to run it at column grain and S37 to
audit the classification per column. **It was not produced.** What exists is `tests/TESTS.py::t_o7`,
which reads `SPEC_V2.json` and checks that the *cards'* classification strings are mutually consistent
— extension columns a subset of the six, base columns a subset of the enumerated set, every
`NEVER_READ` column carrying `current_game_row_consumed = false`. It nulls nothing, builds no second
feature matrix, compares no bytes. That is a card-consistency test, not the receipt. Finding **A8**.

Because the criterion tells this audit to *check the receipt*, and there was none, the underlying
property was measured directly (`measurements/m3_deletion.py`). For each sampled game *g*,
`master_team`'s outcome columns on *g*'s own two team-rows (`pts`, `opp_pts`, and the derived `margin`,
`env`) were replaced with grossly different finite values, every other column and every other row
retained; each arm's feature constructor was re-run; and *g*'s **own** feature values compared to
baseline. A finite perturbation was used rather than NaN because NaN propagates into unrelated later
rows and breaks SC01's rating fit at later cutoffs; the dependence being tested is identical.

**24 sampled clusters × 28 feature columns spanning all ten buildable arms — zero violations. Byte
identity held everywhere.** No tested feature consumed its own game's realized score. SC01's ratings
were rebuilt from scratch on six of the samples.

What that does **not** establish, stated plainly: it is 24 of 1,491, not exhaustive; it covers
`master_team`'s outcome columns only — that `score_baseline_rows.actual_total / actual_margin /
y_home_win` and `master_team.minutes / plus_minus / wl` are never read rests on reading
`build_universe`'s explicit column list, which is a code reading, not a deletion receipt; and it is
not byte identity of the two *feature matrices*, which is what the contract requires. **S36 still owes
the receipt.**

### 3c. Per-source column classification, recorded as required

217 column entries across the eleven arm blocks, 24 distinct columns:

| classification | entries | columns |
|---|---|---|
| `SCHEDULE_IDENTITY_S30_SECTION_1` | 93 | game_id, game_date, season, season_type, is_home, team_id, opp_team_id |
| `PRESENT_IN_ARTIFACT_NEVER_READ_BY_ANY_ARM` | 69 | actual_total, actual_margin, y_home_win, minutes, plus_minus, wl |
| `IDENTITY_SET_EXTENSION_S34_ADJUDICATED` | 20 | pred_home, pred_away, pred_total, pred_margin, p_home, projected_team_off_possessions |
| `LAGGED_OUTCOME_STRICTLY_PRIOR_ROWS_ONLY` | 19 | pts, opp_pts |
| `IMMUTABLE_REFERENCE_METADATA` | 16 | team_id, city, arena, timezone, method |

Retained on the current game's row: the first, third and fifth groups. Nulled: the second and fourth.
Every `NEVER_READ` column does carry `current_game_row_consumed = false`, so O7's promise that a later
reviewer can mechanically read off the affected element set is kept at the card level.

One note: `season_type` is classified `SCHEDULE_IDENTITY_S30_SECTION_1`, but S30 §1's base closed set
enumerates four items — scheduled game date, opponent/matchup identity, home/away designation, season
— and does not name it. See finding **C3**.

---

## 4. Criterion 3 — kill diagnostics. Zero of thirty-four.

S30 §4(c), carried verbatim into the S35 freeze: *"every kill's diagnostic must be a receipted output
of the sealed run (an uncheckable kill is a card defect)"*.

The slate carries **34** kill conditions across the eleven arms (SC01 3, SC02 3, SC03 3, SC04 3,
SC05 2, SC06 4, SC08 3, SC09 3, SC10 3, SC11 3, SC12 4). The planned run is
`runner/runner.py::run_element` — `RUNNER_INTERFACE.md` §4 "Order of operations" steps 5–8 describe it
as the run, and it is the only executable fit path in the node. Its per-fold output is: `arm_coef`,
`k0_coef`, `delta_ci95` (that fold alone), `two_sided_p` (that fold alone), cluster counts,
`deactivated`, `fold_constants`, plus the seed manifest, bootstrap pins and the C1 alpha stamp.

**Not one of the 34 carded diagnostics is among them.** `SPEC.json` carries the full per-kill census,
one line each. Four structural gaps produce the zero:

1. **No pooled out-of-fold surface at all.** `run_element` bootstraps each fold separately and never
   pools. The primary gate's clause (a) is stated on pooled OOF improvement, and roughly fifteen kills
   are stated on pooled Δ. A per-fold interval is not a pooled interval. (Finding **A5**.)
2. **No train-refit bootstrap.** `B_TRAIN_REFIT = 2000` exists in `runner_constants`, the seed manifest
   derives and digests the `train_refit` stream, and `run_element` stores `b_train` in its receipt —
   and no code ever draws from it. There is therefore no coefficient 95% CI anywhere, and five kills
   are stated on train-refit coefficient CIs. In the same place, `cluster_bootstrap.na_draw_rule`
   implements the K7 symmetric-NA rule correctly and is called only from tests, while `runner.py`'s
   docstring lists symmetric NA as enforced guarantee 5. (Findings **A4**, **C2**.)
3. **No subset/stratum Δ machinery, and no leave-one-test-season-out machinery.** Every stratum
   *predicate* is re-derived and every census matches; no code computes a Δ on a stratum, and none
   removes a test season.
4. **No SC08 probability path.** See finding A2 below.

Three receipt **wrappers** do exist, and they are well built: `sc06.era_split_receipt` refuses to
return an era-split table without the verbatim C2 power statement; `sc11.cross_estimand_receipt`
applies the `NON_CITABLE_INTEGRITY_DIAGNOSTIC` label, sets `citable=False`, and renames the field
`abs_delta_mae_E2_NON_CITABLE` so a caller cannot lift it out by habit; `sc08.r_sc08_floor_receipt`
takes no challenger argument, exactly as the A4 rule says it must. **Each of the three takes the number
it labels as a caller-supplied argument, and nothing in the node computes any of them.** The labels
are honest and the quantities are absent.

Two kills deserve naming because they cannot fire at all rather than merely lacking a table:

* **SC06's A1-SENSITIVITY kill** (arm-killing). `R-A1-EXCEPTIONS` appears in the node only as a string
  in `mandatory_receipts`. No code reads the enumerated exception set from `SPEC_V2`, holds the 16
  game_ids, or builds an exception-removed universe. The exception set itself is sound — this node
  re-derived 10 + 6 byte-for-byte — but nothing consumes it. (Finding **B3**.)
* **SC12's outliers-are-signal kill.** The card went out of its way to pin the ranking statistic
  deterministically and train-only — *"for each fold, spread statistic = variance across teams of final
  training-window season-to-date net ratings; the two folds with the largest statistic are the
  'widest' seasons"* — precisely so the widest seasons could not be chosen after seeing results. No
  code computes it. The kill has no defined subject, and the discretion the pin closed is reopened.
  (Finding **B4**.)

---

## 5. The three card-vs-code deviations that void arms by the cards' own clause

Every affected card stamps `estimation_objective.s36_deviation_consequence =
ANY_PER_ARM_DEVIATION_DISCOVERED_AT_S36_VOIDS_THE_ARM`. These are not stylistic.

### A1 — the λ-selection loss is not the carded loss, and the deviation flips an arm-killing kill

SC01's `penalty_treatment` (all three elements, both sides) pins: *"…score the strength-feature head's
**squared error** on the last 20% of training rows, argmin, then refit on the full training window"*.
SC10's (both elements) pins the same rule by reference: *"score head **squared error** on last 20%"*.

`sc01_opp_adj_interacting.py` line 132 returns `np.mean(np.abs(...))`. `sc10_form_trend.py` line 115
returns `np.mean(np.abs(...))`. `_head.select_lambda_train_tail` calls them "training-tail MAE values"
in its own docstring, so the choice is consistent and deliberate, not a slip. **Mean absolute error,
where the card says squared error.**

This is not cosmetic. For SC01 λ determines the ridge rating fit and therefore the *values of the
treatment column itself*; for SC10 it is the shrinkage on the two spread coefficients the kill is
stated on. Running the node's own selection rule twice per (element, fold) — once each way, reporting
only the **selected λ**, never the selection scores (`measurements/m7_lambda.py`):

**9 of 20 selections differ.**

| element | fold | as coded (MAE) | as carded (SSE) |
|---|---|---|---|
| SC10::E2 | train_lt_2025 | 4 | 64 |
| SC01::E2 | train_lt_2024 | 128 | 2 |
| SC01::E1 | train_lt_2022 | 8 | 2 |
| SC01::E1 | train_lt_2024 | 32 | 2 |
| SC01::E1 | train_lt_2026 | 8 | 2 |
| SC01::E3 | train_lt_2022 | 128 | 8 |
| SC01::E3 | train_lt_2023 | 128 | 32 |
| SC01::E3 | train_lt_2024 | 128 | 2 |
| SC01::E3 | train_lt_2026 | 128 | 2 |

SC01's kill 2 is *"shrinkage collapse: the pinned selection rule drives λ to the grid maximum in ≥ 4 of
5 folds"*, scope **kills the arm**. Counting grid-maximum (128) selections: under the coded rule
SC01::E3 selects 128 in **5 of 5** folds and SC01::E2 in 4 of 5 — the threshold is met on both. Under
the carded rule SC01::E3 selects 128 in **1 of 5** and SC01::E2 in 4 of 5. **The coded rule fires an
arm-killing kill on SC01::E3 that the carded rule does not.** These are counts of selected
construction constants, not performance comparisons.

Fix: change both closures to return the mean squared error on the train tail. The 80/20 chronological
split and the smaller-λ tie-break are correctly implemented and unaffected.

### A2 — SC08's frozen estimation objective is absent from the fit path

SC08's card pins `training_loss = gaussian_mle_on_train_margin_residuals_for_dispersion_parameters_only__mean_path_frozen_before_dispersion_fit`,
`response_family = gaussian_probit_margin_map`, link `p = Φ(μ̂/σ̂)` with μ̂ a per-fold train-OLS map of
the composite margin **frozen before any dispersion fit**, and `null_construction = parameter_fixed_at_null`.

`runner.py::_fit_side` branches on the **estimand only**: `if estimand == "E3_HOME_WIN_PROB": return
fit_logit_irls(...)`. There is no branch on `arm_id` and none on `DesignPair.comparison`. So the
planned run fits SC08's design as a Bernoulli logit against the 0/1 win indicator and predicts with the
logistic. There is no μ̂, no σ̂, and the mu-frozen identification the card registers is destroyed.

`estimators.fit_dispersion_newton` and `sigma_from_dispersion` implement the carded Newton fit
correctly — pinned init at log σ₀ = log sd(resid), γ = 0, tol 1e-10, expected-information Hessian. A
search over the whole node finds exactly three call sites, all in `tests/TESTS.py`. **The correct
estimators are dead code.** All three SC08 kills need σ̂ and none can be evaluated.

### A3 — SC10's carded ridge is never applied at fit time

SC10 pins *"ridge (prior mean 0) on the two spread coefficients only… intercept and null-granted
coefficient unpenalized; K0 has no penalized terms"*. `fit_ols(..., ridge=lam, penalise=[F,F,T,T])` is
called **only inside the λ-selection closure**. The `DesignPair` carries the selected λ and the names
in `fold_constants`, but has no field a fitter reads for a penalty, and `_fit_side` calls
`fit_ols(X, y, cols)` with the default `ridge=0.0`. The head coefficients the planned run would produce
are unpenalised OLS coefficients — and SC10's kill 1 is stated on those coefficients.

---

## 6. Ruling on the item formally routed to this node

**Routed statement.** Three E3 cards list `composite_p_home` among their `structural_terms` while
their own formulas and the A4 receipt appear to fit only the composite *margin*; the fitted-column
reading appears unimplementable because of 188 structural NaN with no declared imputation; the
implementation proceeded by treating it as a null-granted ingredient.

**Ruling. The implementation's chosen reading is correct and is not a deviation. But there is no
contradiction between two frozen fields — the cards settle the question in their own text — so both
the characterisation of the item as a contradiction and the ground given for the reading are wrong.
Underneath it sits a real defect the implementation did not report.**

*Evidence 1, the cards are not silent.* All three E3 cards carry, byte-identically on the arm side and
the K0 side, in `companion_components`:

> composite_pred_margin (byte-pinned frozen-store column, see null_strength_floor) as a train-fitted
> linear regressor inside the single head fit; **composite_p_home carried as a null-granted anchor
> column NOT in the prediction path** — the sealed run receipts mean |p_model − p_home| agreement on
> non-NaN rows as a non-gating integrity diagnostic; identical treatment on both sides

`structural_terms` lists it because `declaration_routing` routes it to `companion_components`, and that
dimension holds both a fitted regressor and a carried non-fitted anchor. Listing a term in
`structural_terms` declares *that the null keeps it*, not that it is a design column. The two fields
agree.

*Evidence 2, the same cards answer the NaN question.* `missing_value_handling`, again on all three and
on both sides: *"…NaN rows contribute nothing to the carried anchor and its agreement receipt; **the
prediction path never consumes p_home so no imputation exists to diverge**; identical on both sides."*
The implementation read the absence of an imputation rule as a gap; the card supplies it as a
consequence.

*Evidence 3, the A4 claim is partly false as routed.* `a4_sc08_null_strength_receipt.receipt.computation`
reads: compute the Brier of (i) SC08::E3's own K0 probability path Φ(μ̂/σ₀) and **(ii) the frozen
store's byte-pinned p_home column**, on the identical matched universe with identical handling of the
188 structural NaN. A4 does say SC08's *mean map* is fitted to margin — that is why A4 exists — but
p_home is A4's second comparand, the public-floor control object. A4 is positive evidence for the
anchor reading. It **reads** the column; it does not **fit** it.

*Evidence 4, the 188 figure, re-measured.* On `score_baseline_rows.parquet` filtered to
`composite_pace_x_eff_v1`: 1,465 rows, `p_home` NaN = **188**, `pred_margin` NaN = 0, `pred_total`
NaN = 0. On the built 1,491-cluster universe: `C_p_home` NaN = **188**, and the season breakdown of
those 188 is `{2021: 188}` — all of them. The column digest reproduces. **The figure is correct.**

*Evidence 5, was the alternative really unimplementable?* **Overstated, and it is not the operative
ground.** All 188 NaN sit in 2021, which is a *training* season in all five folds and never a test
season, so they never touch an evaluation row — they would break only the fold-train fits. Whether
that makes the fitted reading unimplementable depends on whether a row drop is admissible, and a row
drop is barred independently: the coverage predicate is TRUE with no trimming, the strictly-prior row
base is pinned, and retention is measured at 100% on both denominators. So the fitted reading *is*
blocked — by the coverage rule plus the absence of a declared imputation, not by NaN alone. The
distinction matters: "the card forbids the alternative" and "the card is silent and the alternative is
awkward" are different epistemic positions, and only the first safely grounds an implementation choice.

*What the ruling exposes.* Because `composite_p_home` **is** a carried ingredient rather than dead
weight, the obligation attached to it is live: the sealed run must receipt mean |p_model − p_home|
agreement on non-NaN rows, on SC01::E3, SC06::E3 and SC08::E3, arm side and K0 side. **No emitter for
that quantity exists.** `R_SC08_FLOOR` is a different object — a Brier-vs-Brier floor comparison
between two control objects. Finding **B2**.

What should have been recorded is not "a contradiction between two frozen fields, raised not resolved"
but: *"the card routes composite_p_home to companion_components and states it is not in the prediction
path; implemented accordingly; the mean-agreement receipt the same field mandates is owed at S38 and
is not implemented here."*

**No stop condition.** This ruling reads a frozen card as written and changes no estimand, no K0
structure, no inference structure, no universe, no cutoff-valid feature-set entry and no leakage
status.

---

## 7. The remaining findings, in brief

Full text for all eighteen is in `SPEC.json`. Summarising only those not already covered:

**B1 (Severity B) — SC06's fatigue clock.** The card qualifies both rest components as *same-season*
and declares *"previous game undefined → F = 0"*. `fatigue_index` groups by `team_id` alone, so at
every season opener from 2022 the "previous game" is the previous *season's* last game and the travel
term is computed across the off-season. Measured: **30 team-game rows differ** (7/4/4/7/8 across
2022–2026), all of them season openers, all differences pure tz contributions of 0.25/0.5/0.75 where
the card reading gives 0; **19 game clusters carry a different `fatigue_diff`**. The
`|F_H − F_A| ≥ 1` kill stratum is 71 under both readings (7/8/17/28/10 per test season identically),
so the kill's habitat is unaffected. Severity B rather than A because the card's same-season qualifier
attaches explicitly only to the rest terms — the reading is genuinely ambiguous. The defect is that
the choice was made **silently**: S36's own SC06 interpretive-pin disclosure covers the standard-offset
map and not the cross-season clock.

**B5 — SC10's orthogonalised variant is half-built.** The covariate is built and correctly kept out of
the primary head, which is exactly what makes the "sealed-variant only" clause checkable. But no
orthogonalised design and no variant Δ exists, so the kill it serves cannot fire.

**C1 — SC06's timezone map has seven entries where the card enumerates six.** `America/Denver: -7` is
added. `team_cities.csv` (16 rows, pinned) contains exactly the six carded zones, so no current value
changes — but the module's own comment claims the map "covers EXACTLY the six… so that a new franchise
in a seventh zone fails closed", and with Denver present it would not.

**C3 — the implemented base closed set has seven members.** `O7_BASE_CLOSED_SET` lists game_id, season,
season_type, game_date, team_id, opp_team_id, is_home. `season_type` is in neither S30 §1's four nor
the S34-adjudicated extension. It is classified `SCHEDULE_IDENTITY_S30_SECTION_1` on the **frozen
cards**, so S36 inherited rather than introduced it, and no arm feature in this slate reads it — which
is why this is C and not a raise. If a future element consumes it, it becomes a cutoff-valid-feature-set
question and therefore a stop condition.

**C4 — SC09 has no real-universe design.** 16 of 17 elements are parity-checked; SC09 is skipped
because its treatment feature is a transform of its own fitted K0 prediction and fitting is
unauthorised. That is a property of the card, and the implementation handled it well — `build()` takes
`g_hat` as a keyword so S38 can pass the same K0 it is already fitting. Two residual notes: `run_element`
calls `spec.build(universe, fold, cache)` positionally, so `g_hat` defaults to `None` and
`k0_prediction` refits internally, defeating the safeguard; and SC09's habitat kill is the one carded
census `verify_carded_strata.py` could not re-derive, so unlike every other kill in the slate its
subset is not yet known to be non-empty.

---

## 8. What this audit could not establish

* Whether the twelve unreceipted CUTOFF_UNPROVEN fields are in fact cutoff-valid. Establishing it
  either way changes the cutoff-valid feature set — a stop condition. The gap was measured; the
  question was not answered.
* Exhaustive current-game-deletion invariance. 24 of 1,491 clusters, 28 columns, zero violations. That
  is evidence, not the receipt.
* Whether the five `score_baseline_rows` prediction columns are cutoff-valid. Their digests reproduce;
  their provenance argument was not re-derived from the builder's own inputs.
* Whether SC09's habitat kill can fire.
* Whether the `arm_registry.jsonl` append specified by the S35 freeze has been performed correctly.
  That is the coordinator's byte-identity proof; the registry was not opened.
* `pipeline_id` remains asserted-not-demonstrated, as S35 recorded. The frozen `comparison_gate`'s own
  documented gap was not closed here.
* Dimension-by-dimension satisfaction of `comparison_gate.LAYER_A_STRICT`. The dimensions the cards
  actually vary were checked by hand and produced A1, A2 and A3; the frozen gate itself was not run,
  because it operates on fitted side-specs and no fit is authorised.

---

## 9. Prohibitions honoured

**No performance number is emitted anywhere in this node's output.** No MAE, Brier, accuracy, log-loss,
Δ or arm-vs-null comparison. The numbers here are counts, censuses, hashes, NaN counts, cluster counts,
correlations between a deliberately-constructed leak column and a duration basis (a leakage diagnostic,
not a model metric), and **selected λ values**, which are construction constants drawn from the cards'
own pinned grids. The λ-selection *scores* were computed in memory because the cards' construction rule
requires it, and are not emitted — the same redaction discipline S36 applied.

The only fits run on real rows were SC01's ridge rating construction and the train-tail selection fits,
both of which are feature-construction steps the cards mandate and neither of which touches a test
cluster. No arm head and no K0 head was fitted for evaluation; no out-of-fold prediction was scored.

No frozen artifact was modified. `MEASURE_A1_DATE_WITNESS.py` was re-run from a **copy** with only its
output directory changed, so `S33R_PREREGISTRATION_REPAIR` was not written to. No S36 script that
writes into S36's directory was executed — `build_manifest.py`, `build_all.py`,
`PREBUILD_GAME_ID_DIGEST.py` and `verify_carded_strata.py` were all left unrun, and S36's modules were
imported and driven in memory instead. All writes are inside
`experiments/player_program/stage3_score/S37_IMPLEMENTATION_AUDIT/`. `git` was not run. No money, no
credentials, no vendor calls.

*(Note for reuse: `measurements/m5_a1_rerun.py` has its `HERE` constant hard-pointed at this session's
scratchpad. Repoint it before re-running, and never at the S33R directory.)*

---

## 10. Recommendation

**Do not authorise fitting.** S35 states that fitting requires a PASSED S37 audit; this audit returns
FAIL.

Order of repair:

1. **Resolve stop condition A9 first.** It is a contract-interpretation question and it governs whether
   several arms may consume their inputs at all. Every later repair is wasted if the answer narrows the
   feature set.
2. Repair **A1, A2, A3** — three local, unambiguous code defects that void arms by the cards' own
   clause. The cards are right; the code is wrong; no erratum is needed.
3. Build the three missing machineries — **A4** (train-refit bootstrap with the symmetric-NA rule),
   **A5** (pooled OOF surface), and A2's σ path. Most kill diagnostics are not expressible without them.
4. Discharge **A6** kill by kill against the per-kill census in `SPEC.json`, then **A7** (build and pin
   a score prohibited basis; invoke per column on both sides of all 17 elements, at the call site — the
   frozen guard module may not be edited) and **A8** (the column-grain deletion receipt).
5. B1–B5 and C1–C4 alongside; none blocks the others.

The cards are immutable. B1's ambiguity and C3's `season_type` classification are card-side; pinning a
reading for either requires a registry-appended erratum naming the defective field, never an edit.

This node does not mark its own work accepted.
