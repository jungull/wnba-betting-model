# S33R_PREREGISTRATION_REPAIR — REPORT

**Materialized by the coordinator** from the author's S33R_REPORT_BODY.md (harness rule).

## Coordinator additions before this report is cited

**1. The four Severity C notes are RECOVERED.** The author correctly named their absence as the
biggest remaining risk: S34 wrote no artifact and the coordinator's ledger event compressed the C
notes to a count while recording A and B in full. That was a coordinator failure. The text is
restored with dispositions in `S34_SEVERITY_C_RECOVERED.md` alongside this file. S35 must freeze
against the complete set — 4 A + 8 B (closed in `S34_DISPOSITION.md`) plus those 4 C.

**2. The `master_team.parquet` divergence is CORRECT BEHAVIOR, not corruption — and the author was
right to flag it.** Measured: the PROGRAM worktree copy (sha `ad79ce5c…`, the S33 pin) carries
2,990 rows / 1,495 games — the frozen evaluation universe. The DATA worktree copy (sha
`e8e35b53…`) carries 3,024 rows / 1,512 games because the daily refresh keeps appending games as
the 2026 season is played. A frozen science universe and a live feed are *supposed* to diverge;
the pin exists precisely so the cycle is evaluated against fixed bytes while capture continues.
**The operative discipline this makes explicit: every downstream node — S36 implementation above
all — must read the PINNED path in the program worktree and verify the sha, never the live copy.
Reading the live file would silently evaluate cycle 2 on a 1,508-cluster universe that no card
declares.** Added as an S36 obligation.

---
# S33R_PREREGISTRATION_REPAIR â€” score lane, cycle 2 â€” report body

**Node:** `S33R_PREREGISTRATION_REPAIR` Â· **Lane:** score Â· **Type:** documentation / repair
**Binding law:** `CYCLE2_TARGET_CONTRACT.md` (FROZEN FULL edition) Â· **Control schema:**
`S32B_K0_CONTRACT/K0_MATCHED_SCHEMA_SCORE.json` (frozen) Â· **Repaired artifact:**
`S33_PREREGISTRATION_DRAFT/SPEC.json` (byte-frozen, not edited)

**Program worktree â€” the root every read path below is relative to, stated explicitly:**
`C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program`

## Epistemic status

> REPAIR. Dispositions S34's findings against the REVIEWED draft, which stays byte-frozen and
> auditable. Emits SPEC_V2.json; authorizes nothing to fit.

## 0. Outputs

| file | what it is |
|---|---|
| `SPEC_V2.json` | the repaired card set: 11 arms, 17 `K0_MATCHED` records, the registered identity-set extension, the replacement `game_date` measurement, the multiplicity block with four registered partitions, and a `self_validation` section that was actually run |
| `S34_DISPOSITION.md` | finding-by-finding: quote, repair, evidence, CLOSED / ACCEPTED-WITH-REASON |
| `S33R_REPORT_BODY.md` | this document (the coordinator materializes `REPORT.md`) |
| `MEASURE_A1_DATE_WITNESS.py` â†’ `A1_DATE_WITNESS_RECEIPT.json` | the A1 measurement and its receipt (13 artifacts hashed) |
| `MEASURE_A3_B_STRATA.py` â†’ `A3_B_STRATA_RECEIPT.json` | A3 strata, B2 row bases, B3 clip incidence |
| `MEASURE_B4_B5_SUPPORT.py` â†’ `B4_B5_SUPPORT_RECEIPT.json` | B4 covariate support, B5 condition numbers |
| `VALIDATE.py` | the schema + cross-field validator, run against **both** SPEC.json and SPEC_V2.json |
| `BUILD_SPEC_V2.py` | the transformation, so SPEC_V2 is reproducible from the frozen draft |

**Headline: all four Severity A findings CLOSED and all eight Severity B CLOSED, with no arm
withdrawn â€” 11 arms / 17 elements / 8 primary families / 10 maximal / four registered partitions /
additive program-alpha bound 0.40 / 0.50, unchanged. The four Severity C notes are NOT recoverable
from the program record and that is reported rather than papered over.**

---

## 1. The finding that came before the findings: the wrong tree gives wrong numbers

The first thing this node measured was measured against the wrong root, and it showed immediately.

```
Get-FileHash -Algorithm SHA256 <path>
  worktree  data/masters/master_team.parquet -> ad79ce5cdda7e058ba24be45243037252e3795a3e9f0c18cc41b3f12f3c38528
  main tree data/masters/master_team.parquet -> e8e35b539df2d13f2325e207b9fb2ba8b2e96da476eaa0ec877fcf5588a71c19
  S33 SPEC pin                               -> ad79ce5cdda7e058ba24be45243037252e3795a3e9f0c18cc41b3f12f3c38528
```

The main working tree's copy has drifted because live captures continue there; it yields **1,508**
universe clusters and **232** clusters in 2026 instead of 1,491 and 215. Only the **program
worktree** matches the pin. Every script in this directory hard-codes the worktree root and says so
in its docstring. Two artifacts that exist in the main tree do **not** exist in this branch â€”
`data/drive_masters/` and `data/odds_capture/` â€” which matters directly for A1 below.

## 2. Universe, re-derived (not inherited)

```python
mt   = pd.read_parquet(WORKTREE/"data/masters/master_team.parquet")
home = mt[mt.is_home == 1]                                 # 1,495 clusters / 2,990 rows
first= home[home.season == 2021].game_date.min()           # 2021-05-14
uni  = home[home.game_date > first]                        # 1,491 clusters / 2,982 rows
```
Per season 205 / 239 / 260 / 262 / 310 / 215; pooled-test 1,286. Identical to S33. Command:
`MEASURE_A1_DATE_WITNESS.py`, block `universe`.

## 3. A1 â€” what the S33 measurement actually does, and what replaced it

### 3.1 Re-deriving the review's numbers

`MEASURE_A1_DATE_WITNESS.py`, block `s33_named_measurement_as_written`:

| quantity | measured |
|---|---|
| `tip_times.csv` rows on the universe | 1,219 |
| `source_table` split | 813 `drive_master` + 406 `extension` |
| date deviations vs `master_team` | **0** |
| universe clusters unwitnessed | **272** (2021: 205, 2022: 59, 2023: 1, 2024: 1, 2026: 6) |
| of those, pooled-test | **67** |
| games with `n_commence_variants > 1` | **36** (2022: 1, 2025: 12, 2026: 23) |
| seasons present in `tip_times.csv` | 2022â€“2026 â€” **2021 absent entirely** |

Every figure in S34's A1 reproduces exactly.

The inadmissibility is broader than the review stated. P2B's own `F3_tip_times_provenance` records
the chain as **CONFIRMED â€” chain closed on exact per-season counts**, builder
`data/reference/collect_bios.py::phase_tips` lines 241â€“291: `tip_times.csv` *descends from* the
retrospective odds archive. It is not that 406 of 1,219 rows are archive-sourced; the file is
archive-derived end to end, and S30 Â§8 excludes the promotion channel for any field whose cutoff
validity rests on vendor-asserted timestamps from a retrospective pull.

The second witness's independence is nil and its hole is real: `master_team.source` values are
literally `gamelog_team_<season>_<type>.parquet+misc_<game_id>.parquet` (11 distinct first tokens),
so `data/refresh_2026/gamelog_team_*` **is** master_team's upstream.
`gamelog_team_2024_regular_season.parquet` is absent from that directory; those 240 clusters reach
`master_team` via `data/wnba_team_gamelog_2024.parquet`, which the same `source` field also names.

### 3.2 The replacement, designed and run

`M_A1_GAME_DATE_CUTOFF_V2` has two admissible witnesses and one alarm-only probe.

**Witness A â€” an endpoint outside `master_team`'s build chain.** `data/shotcharts/shots_*.parquet`
(11 files, all sha256-recorded in the receipt) carry `GAME_DATE` per `GAME_ID` from NBA-Stats'
*shotchartdetail* endpoint, a different pull from the team gamelog. Measured:

* clusters witnessed **1,485 / 1,491**, including **all 205 of 2021** â€” the stratum the S33
  measurement could not reach at all;
* **0** date disagreements against `master_team`;
* **0** games whose own shotchart rows disagree internally;
* hole: **6 clusters, all 2026**, enumerated â€” `1022600210 â€¦ 1022600215` (the six most recent
  fixtures, the same six missing from `officials_master.csv`).

Honest scope limit, carried in the receipt and in SPEC_V2: both endpoints are **postgame** records.
Witness A can falsify a rewrite that touched only the gamelog chain; it cannot witness what the
schedule said before tip, and a postponement both endpoints agree on is invisible to it.

**Witness B â€” the schedule-release ordinal, which tests reschedule directly and covers 2021.**
The trailing five digits of a regular-season `game_id` are the league's schedule-release sequence
number, fixed at publication before any game is played. A fixture moved to a different date keeps
its number and lands out of order against its neighbours. Playoff ids encode round/series/game, not
a linear counter, so playoffs are reported separately as **structural** and never used as
reschedule evidence â€” measured adjacent-date decreases in playoffs are 1/4/4/4/4 per season and are
bracket structure, not postponements.

The test flags a game as displaced when its date is later (or earlier) than **both** release-order
neighbours, which localises the mover instead of blaming whoever follows it. Measured over all
1,491 clusters: **10 displaced regular-season clusters**, in 5 adjacent pairs.

| game_id | season | played | displacement | universe games inside the window |
|---|---|---|---|---|
| **1022300038** | 2023 | 2023-07-28 | **51 days after its next release-order neighbour** | **103** |
| 1022600183 | 2026 | 2026-07-20 | 3 days late | 6 |
| 1022100023 / 24, 1022100100 / 101, 1022100055, 1022500158 / 159, 1022600010 / 184 | 2021 / 2025 / 2026 | â€” | 1 day | 0 |

`1022300038` is the textbook signature of a postponed-and-replayed fixture. The S33-named
measurement returns zero deviations and could never have surfaced it. **That is the difference
between a measurement that can falsify and one that cannot.**

**The barred archive, alarm-only.** Using an excluded channel to attempt *falsification* is not
promotion through it; using it to *confirm* would be, and SPEC_V2 forbids that explicitly. The
probe is convergent on exactly one fixture: `1022600183` is flagged **both** by the release-ordinal
test and by `n_commence_variants > 1` â€” two independently derived flags on the same game. The other
35 market-flagged games show no release-order displacement, which bounds Witness B's sensitivity
honestly: it sees reschedules that break release order, not those that preserve it.

### 3.3 What the field is promoted to, and the receipt that goes with it

`master_team.game_date` â†’ **`CUTOFF_VALID_WITH_ENUMERATED_EXCEPTIONS`**. The exception set is the
10 displaced clusters plus the 6 without a second-endpoint witness, enumerated by game_id in
`SPEC_V2.a1_game_date_cutoff_promotion.enumerated_exception_set`. Binding consequences, registered
before any fit: **R-A1-EXCEPTIONS**, a mandatory non-gating sealed receipt on every element
(primary metric recomputed with the exception clusters removed, identical universe string both
sides), and on SC06 â€” the only arm whose *treatment* reads the field â€” a new **A1-SENSITIVITY
kill** if that removal flips the sign of the affected-subset Î”.

**No arm withdrawn.** The acceptance criterion's fallback ("if no admissible witness exists,
withdraw or re-card") was not reached, because an admissible witness does exist. SC06 is re-carded
in place.

## 4. A2 â€” the identity-set extension, registered

The premise is confirmed by reading the artifact, not by argument:

```python
pyarrow.parquet.ParquetFile(".../score_baseline_rows.parquet").schema.names
# game_id, pred_home, pred_away, pred_total, pred_margin, p_home,
# game_date, season, actual_total, actual_margin, y_home_win, method
```

Settled outcomes sit on the **same rows** as the predictions every element consumes, so source-grain
retention proves nothing and the receipt must run at column grain â€” exactly as S30 Â§1 says.

SPEC_V2 registers the extension S30 Â§1 provides for: the five byte-pinned composite prediction
columns (`pred_home`, `pred_away`, `pred_total`, `pred_margin`, `p_home`, digests carried unchanged
from the S32B schema consts, which S34 independently recomputed from the parquet) plus
`projected_team_off_possessions`. **No column-level pin existed for the pace prior**, so this node
computed one under the S32B canonicalisation rule:

```
sort (str(game_id), str(team_id)) asc; floats via repr(float(v)) (NaN->'nan'); joined U+001F; sha256
column_sha256 = 9078790427e0c3357dd8fe6a337fcc96852bfbfedaac48d963f5686894ac71bd
join_key_sha256 = 6b8b2709af3890c40a2fbc14eec36f02a5eae048aece1480ce7f3929126dd59b
n_values = 2990, n_nan = 8, artifact c37c075148553920b79c9320ea03afb37986bfc752fc84dd695f154887c3db18
```
(computed in `BUILD_SPEC_V2.py`; the artifact hash is asserted equal to the S33 pin and the build
fails closed otherwise.)

The justification is the frozen builder's own bytes, cited by line:
`build_score_baselines.py:286` â€” `prior_idx = [j for j in range(len(sub)) if dates[j] < dates[i]]`
(strictly earlier **dates**, never same-day) â€” and lines 411â€“437, the win-probability logistic
calibrated on strictly-prior **seasons** only, walk-forward, never pooled. The pace prior is the
frozen VERIFIED regulation-equivalent ingredient S30 Â§8 declares consumable as-is.

Every `features_lineage` entry moved from artifact grain to **consumed-source-column grain**: each
source now carries a `columns` list, each column a `classification` and a
`current_game_row_consumed` flag, and each arm a per-column `p22_guard_obligation`. Checked
mechanically over all 11 arms (`self_validation.repair_specific_checks.N2`, `N3` â€” both `true`), so
S37 has a per-source classification to run the receipt against rather than an assertion.

## 5. A3 â€” one predicate, its own number

`MEASURE_A3_B_STRATA.py`. Clock = same-season strictly-prior completed games on the pinned row base.

| reading | pooled | 2022 / 23 / 24 / 25 / 26 | 2021 (never a test season) |
|---|---|---|---|
| `max(n_H,n_A) â‰¤ 12` (**BOTH** early) | **472** | 75 / 76 / 74 / 81 / 92 | 74 |
| `min(n_H,n_A) â‰¤ 12` (at least one) | 516 | 81 / 80 / 82 / 88 / 103 | 82 |

**Pinned: `max â‰¤ 12`, 472.** The card's predicate text is kept; the number is corrected. J12 is
corrected on the record: "each/both teams â‰¤ 12" is `max`, not `min`; `min â‰¤ 12` means *at least one*
side is early. J12 had already declared the BOTH reading the intended conservative one, so the
predicate was right and the arithmetic was wrong. Non-empty in all five folds, so the kill that
terminates all three SC01 elements stays checkable. SC02 (`min â‰¤ 5` â†’ 249) and SC03 (`min < 10` â†’
399) re-derive unchanged and card their reducer explicitly.

## 6. A4 â€” SC08's null, and why the receipt route rather than a refit

The gap is visible in the record's own strings: SC08::E3's training loss is
`gaussian_mle_on_train_margin_residuals_for_dispersion_parameters_only__mean_path_frozen_before_dispersion_fit`,
and its `missing_value_handling` says outright that "the prediction path never consumes p_home" â€”
the byte-pinned public floor for E3 is carried as an inert anchor. SC01::E3 and SC06::E3 fit a
per-fold logistic of the composite margin on seasons `< Y`, which *is* the frozen builder's
walk-forward construction of `p_home`; SC08's probit-of-margin map is not.

Refitting SC08's mean map to the win outcome would change the element's estimation objective and
K0 structure â€” an S30 Â§11 **stop condition for this node**. So the repair is the other route the
acceptance criteria allow, and it is written into the binding records rather than the report:
`R_SC08_FLOOR`, a mandatory sealed receipt comparing the K0's pooled and per-fold Brier against the
frozen `p_home` column's on the identical matched universe (both are **control** objects; no
challenger number enters), plus a preregistered below-floor rule that forces the
`FEATURE VALUE OVER OWN NULL ONLY â€” BELOW-FLOOR NULL` label, excludes the element from every
unqualified tally, and routes S40 â†’ S42 USER. The same receipt is registered non-gating on SC01::E3
and SC06::E3 so their structural claim is checked, not asserted.

Floor/bar discipline was checked rather than assumed: the rule names the floor *artifact column*
that S30 Â§4 already obliges every K0 to carry by byte pin, prints no floor or bar **value**, and is
a labelling rule â€” not one of the four categories S30 Â§4 forbids from referencing floor values. A
mechanical scan of `SPEC_V2.json` for the three D043 bar numerals passes (`N6`).

## 7. Severity B â€” the measurements behind each

**B1 made mechanical.** `VALIDATE.py` implements R5 as the schema states it â€” a *literal key* match
on `FACTOR` in `FACTOR:feature` â€” and raises `UnhandledKeyword` on any schema keyword it does not
implement, rather than ignoring it as the S33 validator did. Run against the **frozen S33 bytes** it
fails exactly two records:

```
SC06_SCHED_FATIGUE_DIFF::E2_FINAL_MARGIN_HOME
  R5: interaction ERA2024:fatigue_diff lacks main effect 'ERA2024' in k0_spec.structural_terms
SC06_SCHED_FATIGUE_DIFF::E3_HOME_WIN_PROB   (same)
```
Run against V2: **17/17 PASS**, both schema and cross-field. Both runs are recorded inside
`SPEC_V2.self_validation`. The repair renames the main effect to the byte-identical key `ERA2024` in
both sides' `structural_terms`, `declaration_routing`, `nuisance_terms` and
`lower_order_structural_terms`.

**B2, measured.** The two bases were both live. Pinned to the **1,491-cluster resolved universe**.
Consequence, measured rather than waved at: 187 universe clusters have different same-season
strictly-prior counts under the two bases â€” **all 187 are 2021 games, training-only rows in every
fold, zero in any test season**. Stratum counts under pinned vs full: SC01 `maxâ‰¤12` 472 vs 470,
`minâ‰¤12` 516 vs 510, SC02 `minâ‰¤5` 249 vs 245, SC03 `min<10` 399 vs 394. **No test-season stratum
count changes.**

**B3, measured.** 780 of 2,982 team-game margin observations exceed Â±15 = **26.16%**; lowest
per-season share **20.61%** (2024). A "< 8% clipped" kill is unreachable, and the S33 justification
inverted the inference. The replacement kill is pinned to the mechanism's realised bite,
`|w_H âˆ’ w_A|` with `w = EWMA(clip(margin,Â±15)) âˆ’ EWMA(margin)`, span 10: median **1.704**, p75
**3.068**, p90 **4.706**, max **13.0**; 9.93% of clusters below 0.25 points. High-bite subset
`â‰¥ 2.0` = **652 clusters (43.7%)**, per test season 97/118/102/141/107 â€” non-empty everywhere, so
the new kill can fire. A second kill at p90 < 1.0 is labelled **implementation-integrity**, not
science, because on the frozen construction only a build defect could produce it.

**B4, measured.** `trailing_opponent_strength_diff` becomes a first-class lineage entry with source
hash, column classifications, lag semantics and a per-column P22 obligation. Support: both sides
have â‰¥ 4 same-season strictly-prior games on **1,322 / 1,491 (88.67%)**; the other **169** take the
declared zero fallback, identically on both sides.

**B5, measured.** Îºâ‚‚ â‰¥ 1000 on the fold's training design `[intercept, standardised null-granted
column, standardised treatment term]` is pinned as the retirement trigger; â‰¥ 2 folds retires the arm
UNEVALUATED. Feasibility (a condition number involves no target and no metric): per-fold maxima
1.087 / 1.241 / 1.211 / 1.143 / 1.121, overall **1.241**. The threshold is a convention, not a value
read off the table, and the measurement shows the kill is a live guard rather than pre-satisfied.

**B6, carried.** Partition D `FAM_S2_LAGGED_OWN_FORM = {SC10, SC12}` (3 elements) is registered on
both cards and all three records. Alpha arithmetic stated explicitly: the additive bound uses the
maximum family count over registered partitions; D is a **merge** and merges never raise the count,
so the maximum stays 10 and the bound is unchanged at **0.40 / 0.50**. D makes Holm strictly harder
for those three elements.

**B7.** SC05's dual assignment now appears on its own card and record, not only in the multiplicity
block.

**B8, re-carded.** `calibration_freedom = "none"` is literally correct for the post-fit machine
dimension (the hinge is a within-head regressor), and changing that string would have broken
Layer-A byte identity for nothing. The defect is the kind claim: the treatment is a monotone hinge
of the **K0's own fitted prediction**. SC09 is re-carded `arm_kind: calibration_only`, its
`verdict_label_policy` rewritten so it **may never be reported as feature value**, and the
`calibration_freedom` string amended identically on both sides to say so explicitly.

## 8. Self-validation, actually run

`VALIDATE.py` + `BUILD_SPEC_V2.py`:

* **17/17 records PASS** schema validation and cross-field rules R1â€“R5 (R5 literal), R11, the
  P26 1.5 `tested_parameters` rule, full 17-dimension Layer-A sidespec byte identity, and the
  `k0` no-substantive-features constraint.
* **8/8 repair-specific checks pass** (`N1` identity-extension note on every element; `N2`/`N3`
  column-grain lineage complete and classified; `N4` every kill has a receipted diagnostic; `N5`
  every arm declares its row base; `N6` no floor/bar numeral anywhere; `N7`/`N8` 17 elements /
  11 arms).
* The node's own contract command passes:
  `python -c "import json;json.load(open('experiments/player_program/stage3_score/S33R_PREREGISTRATION_REPAIR/SPEC_V2.json'))"`.

## 9. What I could NOT establish

1. **The four Severity C notes.** S34 wrote no artifact directory; the only surviving text is the
   `agent_returned` event, which enumerates the A findings and gives counts only for B and C. I
   searched `GRAPH_EVENTS.jsonl` (6 S34 events), `DECISION_LEDGER.jsonl` (one S34 entry, D050,
   about operating policy) and `reports/COORDINATOR_HANDOFF_2026-08-07.md` (repeats "4 A, 8 B, 4 C"
   and details only the A's). I did not invent them. SPEC_V2 dispositions the four items **S33
   itself escalated to S34**, labelled a reconstruction: J3 (ANSWERED by A4), J11 (ACCEPTED â€” the
   pre-build game_id-set digest is recommended to S35), the pooled-floor denominator reading
   (ACCEPTED â€” measured moot, still flagged), `pipeline_id` asserted-not-demonstrated (ACCEPTED â€”
   a frozen-gate property this node may not touch). **This is the one part of the mandate not
   closed against the actual review, and the re-verifier should re-run it if the reviewer's C text
   can be recovered from its transcript.**
2. **A pre-tip schedule witness.** No committed artifact in this branch records what the schedule
   said *before* tip. Both A1 witnesses are postgame. A reschedule that both endpoints agree on and
   that preserved release order is invisible to this design, and no measurement in this repo can
   change that â€” a point-in-time schedule capture is prospective work.
3. **Whether the 10 displaced clusters were postponements or league-published out-of-order
   fixtures.** Witness B detects displacement, not its cause. Nine of the ten are one-to-three-day
   displacements with 0â€“6 universe games inside the window; only `1022300038` (51 days, 103 games
   inside) is material. The card handles this by receipt and sensitivity kill rather than by
   asserting a cause.
4. **`invariants.rows` digests.** Still deferred to S36 with the fail-closed contract; the row
   *base* is now pinned, which was the part that was genuinely ambiguous.
5. **A conformant JSON Schema 2020-12 processor.** `jsonschema` is not importable here â€” the same
   gap P26, S32B and S33 recorded. `VALIDATE.py` is stricter than S33's (it refuses unknown
   keywords instead of ignoring them) but is still not certified.
6. **R10 for the five composite column pins.** Discharged here only for the pin this node created
   (`projected_team_off_possessions`, recomputed from the parquet). The five composite digests are
   carried unchanged; S34 independently recomputed all six byte pins from the parquet, so they are
   twice-verified, but not by me.

## 10. Contradictions found

1. **Document vs bytes â€” the row base.** S33's prose treats the 1,491 universe as the row base while
   several arms' constructions read "any season" strictly-prior rows, which on the full schedule is
   the 1,495 base. Both were live; the divergence is 187 clusters, all 2021. Pinned in V2.
2. **Card vs card â€” SC01's stratum.** Predicate said BOTH (472), number said min (516). Pinned.
3. **Card vs measurement â€” SC12.** The card cites 26.16% incidence as evidence its 8% inertness
   floor is "live"; the same number proves the floor unreachable. Kill replaced.
4. **Self-validation vs the schema â€” R5.** S33 reported 17/17 PASS; a literal reading of R5 fails
   two records. Demonstrated by running the validator over the frozen bytes.
5. **Contract vs data â€” the identity set.** S30 Â§1 requires a column-grain receipt whose identity
   set excludes the very columns S30 Â§4 requires every K0 to carry. That is a genuine tension in the
   frozen law, and Â§1 anticipates it with exactly one lawful resolution â€” the S34-adjudicated
   extension â€” which is what V2 registers.

## 11. Stop conditions

Nothing here changes the estimands (E1/E2/E3), the K0 structure, the inference structure, the
declared universe, or the leakage status. Two items touch the boundary and are recorded plainly
rather than smuggled:

* **The cutoff-valid feature set does change.** `master_team.game_date` moves from CUTOFF_UNPROVEN
  to CUTOFF_VALID_WITH_ENUMERATED_EXCEPTIONS on a measurement this node ran, and the
  schedule-identity column set is extended. Both are changes S30 explicitly provides for at this
  stage â€” Â§8's promotion path and Â§1's "extendable only by S34 adjudication" â€” and this node exists
  to make them. They are registered as reviewable adjudications, not assertions, and the affected
  element set is mechanically readable.
* **A4 deliberately did not refit SC08.** The refit would have changed the element's estimation
  objective and K0 structure, which *is* a stop condition. The receipt route closes the labelling
  hole without touching either.

The one item raised-not-resolved from S32B (the pooled-floor denominator reading) remains
measured-moot for this slate and flagged.

## 12. Final counts and the biggest remaining risk

* **11 arms Â· 17 elements Â· 1 withdrawal (SC07, unchanged) Â· 8 primary families / 10 maximal Â·
  4 registered partitions (A, B, C, D) Â· additive program-alpha bound 0.40 / 0.50, unchanged.**
* Re-carded in place: SC01 (stratum), SC02 (Îºâ‚‚ threshold), SC05 (dispute), SC06 (A1 kill + receipt),
  SC08 (floor receipt + below-floor rule), SC09 (calibration_only), SC10 (covariate lineage +
  partition D), SC12 (kill replaced + partition D).

**Biggest remaining risk: the Severity C gap.** Every A and B finding is closed against text I could
quote and numbers I re-derived, but four findings the independent reviewer actually raised exist
only as a count. A repair node that closes 12 of 16 findings and reconstructs the rest is not the
same as a repair node that closed all 16, and S35 should not freeze on the assumption that it is.

**Second risk, scientific:** `1022300038` â€” a fixture played 51 days out of its schedule-release
order with 103 universe games inside the displacement window. The A1 design handles it by receipt
and sensitivity kill, which is the right posture given no pre-tip schedule witness exists, but if
S37's re-run finds more such fixtures once the exception scan is applied to the EWMA sequencing of
every arm, the second-order exposure S33 flagged becomes first-order and several lagged
constructions must be re-derived before any sealed result is citable.

**Third risk, structural (carried from S33, undiminished):** with the null-strength floor granting
every K0 an affine-recalibrated composite, most 1-df arms are honestly expected to die, and SC09 â€”
now formally `calibration_only` â€” cannot claim feature value even if it passes.
