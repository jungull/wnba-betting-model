# Project update — 2026-08-04

Prepared by the research-advisory thread. Read-only analysis: no experiment, refit,
preregistration, contract amendment or registry modification was performed in producing it.

---

## 1. Document status

**As-of 2026-08-04T17:29:42Z (13:29:42 ET).** Worktree `player-model-program`, HEAD
`e79ae2ce261cd6c14571856711790ecd4b128db0`, clean. Full artifact hashes and the readiness ruling
are in [Appendix A](#appendix-a--integration-preflight-receipt).

| | |
|---|---|
| player program | worktree `player-model-program`, HEAD `e79ae2ce`, **clean** |
| repo root | `data-refresh-2026` @ `735b63b`, dirty |
| `main` / `origin/main` | `3f47074`, 2025-08-28 — **nothing from 2026 is pushed** |
| team program | outside the repo, in `OneDrive - Sasserath Co\WNBA`; no repo writes |

**Evidence labels used throughout:** `VERIFIED_PROJECT_STATE` · `VERIFIED_READ_ONLY_DERIVATION` ·
`POST_HOC_DIAGNOSTIC` · `EXTERNAL_SOURCE_DERIVED` · `RELAYED_UNVERIFIED_PRACTITIONER_SOURCE` ·
`PENDING_DECISION`.

Frozen artifacts and receipts govern over prose handoffs. Two published project figures were
reproduced exactly as validation of the extraction chain: the Wave 2 2024 margin interval, and the
14.18% non-appearer error share. **Later scheduler runs supersede the prospective receipt in
[Appendix E](#appendix-e--prospective-coverage-receipt-and-start-ruling).**

Three figures in this document supersede earlier estimates produced during its own preparation.
The superseded values and the reason each was withdrawn are preserved in
[Appendix B](#appendix-b--correction-changelog).

---

## 2. Executive update

**What changed.** Four verification packets plus two precision passes closed the major open
uncertainties. The gate-wrapper concern is resolved and requires no action. The team-model
promotion question is settled by simulation of the registered gate rather than by inference.
Player-grain re-adjudication is confirmed available for five of eight workstreams and has been
recomputed on evaluable folds. The prospective-capture defect decomposed into **four** distinct
faults, not one.

**Principal conclusion — two claims, deliberately not merged.**

1. **W2-C1 is unlikely to promote.** Its observed 2024 margin effect is −0.0153 against a
   registered −0.10 threshold. The complete registered gate passed **99/2,000 (4.95%)** and
   **105/2,000 (5.25%)** on two independent seeds. That residual is noise-driven: as sample size
   grows, the probability of clearing a point-estimate threshold the true effect does not meet
   falls toward zero. **This simulation is candidate-specific.**
2. **The gate is not universally unreachable.** A true effect of −0.20 reaches 80% power in ~4.9
   seasons at full capture, ~5.2 at the registered 95%. The gate is demanding, not impossible.
   *"This candidate cannot pass"* must not be collapsed into *"no team candidate can ever pass."*

**Decisions required.** Six, in [§8](#8-decision-register); one is resolved by existing contract
and one is newly ambiguous.

---

## 3. Verified current program state — `VERIFIED_PROJECT_STATE`

### Player program

Discovery Wave 1 complete and audited; **no challenger registered; Arm D unchanged.** Frozen
incumbent `D_ewma_shrunk`, K=200, α=0.1, operational team MAE 2.9675, intrinsic 2.896. Canonical
frozen artifacts: `projected_player_possessions/1` (35/35), `canonical_player_events/1` (18/18;
589,130 events, 1,495 games), `player_turnover_targets/1`, `player_possessions/2` (238,563
possessions), `team_possession_prior/1`. Registry **41 records**, append-only, coordinator-only.
Stop boundary in force, 8 prohibitions. *All verified unchanged at the preflight.*

**Gate-wrapper item resolved.** Commit `11529bb` implements `GATE_INVOCATION_CONTRACT` §8a
dual-frame binding. Authorization is recorded in the body of `bf04a3d`: the prior guard *"made it
fail the moment Stage 1 changed the file under explicit authorization."* `PROGRAM_STATE` now
records `dual_frame_audit: implemented = true`, closing the Severity A gap and lifting the Phase 0
caveat on `RESEARCH_CONTRACT_V1` requirements 5–7, which previously stood as author-asserted
rather than tooling-demonstrated.

**Open methodological gaps at HEAD `e79ae2ce`** — three are new as of 2026-08-04:

| gap | implemented |
|---|---|
| `dual_frame_audit` | **true** (was false) |
| `general_feature_producer_provenance` | false — **new** |
| `construction_receipt_forgery` | false — **new** |
| `cutoff_validity_asserted` | false — **new** |
| `validator_lineage`, `fresh_execution_unprovable`, `nonlinear_dependency`, `pipeline_id_asserted`, `ws6_no_featureless_control` | false |

### Team program

Wave 1 is 5/5 NEGATIVE after the universe correction. Wave 2 executed; the freeze gate fails;
W2-C1 was frozen anyway under an explicitly weaker standard. Production incumbent remains the
committed structural model (freeze-v0); BENCH-R remains the margin benchmark. Champion lineage
UNRESOLVED (R5). DL-004 stands: no season permits a clean comparison of the two team models.

### Prospective state

`prospective_v0` is an operational pilot, not promotion-grade. `prospective_team_pair_v1` start is
resolved by contract ([§8, D-1](#8-decision-register)). Base chain 23 records; companion chain 4.
Registered `prospective_v0` verdict bars, **not approached**: ≥300 logged T-24h game-forecasts;
≥150 policy bets in the 0.5 cell; 90% CI width on that cell's ROI ≤ 12pp; cover reliability
|gap| ≤ 0.05.

---

## 4. New verified findings

### 4.1 W2-C1: effect size, not precision — `VERIFIED_READ_ONLY_DERIVATION`

The registered date-block bootstrap was reproduced exactly: 2024 margin Δ **−0.0153**, 90% CI
**[−0.4677, +0.4252]** (ledger records −0.015, [−0.468, +0.425]).

**Complete registered promotion gate**, nested bootstrap at the registered replicate count —
per-condition detail in [Appendix C](#appendix-c--power-and-gate-calculations):

| outer seed | complete gate | frequency | 95% Monte Carlo interval |
|---|---|---|---|
| 0 | 99 / 2,000 | **4.95%** | [4.00%, 5.90%] |
| 12345 | 105 / 2,000 | **5.25%** | [4.27%, 6.23%] |

Stable across seeds. **Conditional on condition 6 passing** — if it fails, the gate is 0/2,000 by
conjunction ([§4.4](#44-condition-6-is-ambiguous--pending_decision)).

Margin-only conditions 1+3 as a function of sample size: 8.1% at 64 dates, 16.8% at 500, 0.3% at
5,000, ~0 at 50,000. **More data lowers the pass rate**, because the binding constraint is a
threshold on a point estimate that the true effect does not approach.

**Two figures not previously on the record:** 2026 margin Δ **+0.5009, 90% CI [+0.1003, +0.9421]
— the interval excludes zero** (watch item W-1 records the point estimate but not its
significance); and pooled all-season margin Δ **+0.1097**, W2-C1 worse — not a defect, since 2026
is quarantined by design, but absent from the ledger and the figure a naive reader computes.

### 4.2 Player-grain resolution on the WS1 surface — `VERIFIED_READ_ONLY_DERIVATION`

**Scoped statement.** *On the frozen WS1 turnover surface, using identical dates and a
date-clustered comparison, the player-game analysis achieved approximately five times finer
relative interval resolution than the team-game aggregation.* Half-width as a share of each
grain's own baseline MAE: player-game **0.046%**, team-game **0.232%**.

- **Verified for:** WS1 turnover predictions only.
- **Supports:** investigating other workstreams at player grain.
- **Not established:** as a universal factor across targets, universes or models. **The factor
  must be computed per workstream, not assumed.**
- **Where analogous calculations are possible:** determined by
  [Appendix D](#appendix-d--workstream-auditability).

Design effects — game 1.14, **date 1.40** (binding), player 1.01. Within-game ICC **0.0113**;
repeated-player ICC **0.0496**; effective N **25,503** of 35,629 nominal. The raw obligation ratio
(12.2×) overstates the gain; √N (3.5×) understates it. On this surface, aggregation rather than
clustering destroys the information.

### 4.3 WS1 recomputed on evaluable folds — `VERIFIED_READ_ONLY_DERIVATION`

**4,850 rows are mechanically disabled** — `pred_L1 == pred_D == pred_K0` exactly — and **all
4,850 are season 2021**, which has no prior season to train on
(`{"skipped": true, "reason": "fold falls back to Arm D (beta=0)"}`). This is the L-W1-005
silently-disabled-challenger pattern; it is disclosed in the per-fold audits, not concealed.

**Sign convention: Δ = challenger MAE − comparison MAE.** Negative favours the challenger.

| | all rows (diluted by the fallback fold) | **evaluable folds** |
|---|---|---|
| N | 35,629 | **30,779** |
| dates | 563 | **474** |
| seasons | 2021–2026 | **2022–2026** |
| baseline (K0) MAE | 0.8469 | **0.8124** |
| Δ vs K0 | +0.00021, SE 0.00024, 90% CI [−0.00017, +0.00062] | **+0.00025, SE 0.00027, CI [−0.00020, +0.00071]** |
| Δ vs incumbent D | −0.00081, CI [−0.00118, −0.00039] | **−0.00093, CI [−0.00137, −0.00047]** |
| half-width / baseline | 0.046% | **0.055%** |

**Excluding 2021 does not change the scientific conclusion.**

> Against K0, the result is a tightly bounded null. The 90% interval rules out a beneficial MAE
> reduction larger than approximately 0.00020, equal to about 0.025% of the evaluable-fold K0
> baseline. It does not rule out deterioration as large as approximately 0.00071, about 0.087%.

Against the *unfitted* Arm D the challenger looks favourable with an interval excluding zero —
reproducing the wave's own free-flexibility finding at player grain: it beats an unfitted incumbent
while failing to beat a matched featureless control.

### 4.4 Condition 6 is ambiguous — `PENDING_DECISION`

Registered wording: *"Benchmark — must beat **BENCH-R** on margin on common rows, or carry an
explicit written reason why not."* The only frozen text bearing on it is the freeze-decision
table's *"N/A — W2-C1 is BENCH-R extended; margins identical."* Full adjudication in
[Appendix C](#c3-condition-6-adjudication). **Ruling: `AMBIGUOUS — requires coordinator ruling`.**
The complete gate is ≈5% if condition 6 passes and **0%** if it fails.

### 4.5 Capture defect decomposes into four faults

See [§5](#5-defects-and-evidence-risks).

---

## 5. Defects and evidence risks

| # | Defect | Severity | Required action |
|---|---|---|---|
| **D-a** | **Audit classification.** The coverage auditor accepts `late_record`s as evidence the job was healthy at a label. 2026-08-03 PHX@CHI T-30m is classed `missing_data_unavailable` on the strength of two records that are themselves late. A variant of the bug PL-003 fixed once. | **B** | exclude `late_record` from the served-evidence test. Operational misses **26 → 27**. |
| **D-b** | **Obligation discovery / lead window.** 2026-08-04 TOR@GSV T-24h, cutoff 02:00:00Z: the gate declined at 01:30, 01:45 and 02:00 with *"no unserved obligation inside its 20-minute lead window"* — yet at 01:45 the cutoff was 14.9 minutes away, inside the window. **Per-game scope does not fix this, and it fails silently.** | **A** for coverage integrity | independent fix in `should_run_base.py` |
| **D-c** | **Per-game execution scope.** `daily_forecast.py` cannot be scoped to one game and keys deduplication on `now`. It was holding **every 15-minute firing** at the as-of time. Serves a **non-random** subset. | **A** for confirmation validity | cross-thread amendment; bundle with the `forecast_log.py` schema change |
| **D-d** | **Lead-window execution latency.** Two records created 22:45:08Z against 22:34 / 22:44 cutoffs. Distinct from D-b: discovery worked, execution was late. | **B** | separate correction |
| **D-e** | **Entity resolution / cold start.** See below. | **B** (capability risk) | alias and cold-start tests |
| **D-f** | **Logout survival.** The Interactive-mode task does not run when logged out. | **C** | reliability improvement, **not** the primary historical cause — 25 of 26 job-did-not-run misses predate a functioning scheduler entirely |

### D-e — three separate claims

1. **Neither observed warning changed a stored forecast mechanically.** Kelsey Plum was
   **Available** at every relevant run. Kara Dunn has zero rows in `master_player.csv`, so no
   projected minutes existed to remove.
2. **Neither warning invalidates `record_idx 3`.** Both concern Phoenix; the record is GSV v TOR.
3. **The warnings expose two real prospective capability risks**, and claim 1 does not dispose of
   them:
   - **Alias / team-history resolution for recently transferred players.** Plum shows LVA 2021–24,
     LAS 2025, **LAS 2026 (17 g) + PHX 2026 (1 g)**; one appearance falls below the matcher's
     season-history threshold. Had her status been **Out**, exclusion would have failed on a
     high-usage player.
   - **Cold start for genuine new signings.** Dunn is **Out**, "Pending Physical", with no
     historical rows. *"Zero projected minutes made it a no-op"* establishes only that nothing
     changed mechanically — **not that the forecast was substantively correct.** A new signing can
     carry real latent rotation value that a history-keyed model cannot represent at all.

**Classification: entity-resolution / cold-start capability risk. Not a defect in these two
records.** Recommended: alias-mapping tests against the injury feed; roster-to-history
reconciliation; explicit cold-start player objects; and a **fail-closed or manual-review rule** for
unmatched Out/Questionable players with expected rotation relevance.

---

## 6. Scientific interpretation

**What the closed team-grain findings establish.** Under the tested formulations, broad pooled
conditional-rate expansion is near its practical team-aggregate ceiling; two structurally distinct
team architectures produce margin residuals correlated at 0.958 and both beat a constant by only
~12%; the rate model sits at its Poisson noise floor (MAD ratio 0.9969); team-total features
failed against an intercept. Four independent lines, same direction.

**What they do not establish at player grain.** The wave adjudicated player mechanisms on **team**
MAE, where the 5× exposure identity forces cancellation. WS2's own `formulation_dependence` states
it: *"A different metric, not a different feature, is what this result argues for."* WS8 records
availability as null at team grain while non-appearing candidates carry **14.18%** of player-level
absolute error. A null at a grain where the effect cannot express itself is not a null about the
mechanism.

**Why player-grain review is an audit, not indiscriminate reopening.** The fold rule is frozen,
deterministic and verified ([Appendix D](#appendix-d--workstream-auditability)). Predictions,
targets, matched K0 and incumbent survive as frozen bytes. **Nothing is refitted.** §4.3 shows the
audit can return the same answer — which is the point.

**Why W2-C1 is unlikely to promote.** A ~5% complete-gate pass rate at its observed effect vector
(0% if condition 6 fails), with the residual attributable to noise that more data removes.

**Metric boundary.** Every metric used is either preregistered or reproduces a published project
figure. Poisson deviance, log score, appearance-conditional scoring and subgroup calibration are
marked `POST_HOC_DIAGNOSTIC` and preserved as guidance for the *next* target contract. MAE alone is
**not** sufficient for zero-heavy counts — 23.2% of player-game rows are non-appearers — but that
is an argument about designing the next contract, not a licence to rescore a closed one.

---

## 7. Prioritized next actions

**Engineering (blocking).** (1) Bundle two cross-thread amendments: per-game scope for
`daily_forecast.py` (D-c) and additive `alt_model_predictions` with `SCHEMA`→`/2` in
`evalharness/forecast_log.py`. (2) Fix obligation discovery (D-b) — independently necessary.
(3) Fix the auditor's late-record evidence test (D-a). (4) Address lead-window latency (D-d).
(5) Batch-logon with IT — reliability, demoted.

**Audit.** (6) WS1 player-grain re-adjudication is **complete** for the primary arm; extend to the
remaining WS1 arms. (7) Read-only feasibility extraction for WS2, WS3, WS5 and WS7 per
[Appendix D](#appendix-d--workstream-auditability), **computing the resolution factor per
workstream**.

**Research.** (8) Team possession-total projection — already authorised; honest prize 1.2–2.2% of
operational MAE. (9) Multiplicity framework — Hansen SPA / Model Confidence Set / Romano–Wolf,
**not** Deflated Sharpe; plus an effective-trial ledger counting abandoned formulations, threshold
searches, universe changes and analyst-guided reformulations. (10) Within/between involvement as a
forecaster — a **new experiment**, requiring a matched K0.

**Operational logging.** (11) Begin capturing execution-side fields now: sportsbook, market, price,
timestamp, observable limit, decision label, closing line, executability, slippage. Historical
reconstruction is blocked by DL-002 (27% T-24h coverage).

**Deferred.** Staged distributional layer; decision-time comparison; player props last, and not
before the market premise is evidenced.

---

## 8. Decision register

### Resolved

R-1 gate wrapper (authorized, committed, `dual_frame_audit` now `true`) · R-2 external Reddit
review abandoned by instruction; material retained for hypothesis generation only · R-3 registered
prospective gate preserved exactly as written.

### Required

| # | Decision | Recommended ruling | Owner | Evidence | Consequence of approval | Consequence of delay |
|---|---|---|---|---|---|---|
| **D-1** | `prospective_team_pair_v1` start record | **`RESOLVED_BY_EXISTING_CONTRACT`** — `record_idx 3`, game `1022600225` (GSV v TOR), T-8h, cutoff 2026-08-04T18:00Z, created **2026-08-04T14:30:06.442135Z**. Awaiting acknowledgment only. | John | Appendix E | start-of-record fixed; **does not** make the stream gradeable | start timestamp gets retro-fitted later |
| **D-2** | WS1 no-refit audit | **Approve.** Evaluable-fold recomputation complete (§4.3); extend to remaining arms. | John | §4.3, Appendix D | closes WS1 at player grain | strongest cheap evidence stays unused |
| **D-3** | Read-only feasibility extraction, WS2–WS8 | **Approve, with the standing constraint** — no new metric-based rescoring of closed work. | John | Appendix D | scopes the audit before effort is committed | audit scope stays guesswork |
| **D-4** | Bundled cross-thread amendment | **Prepare, do not implement.** The repair set is **four** faults; the bundle covers D-c only. | John + engineering | §5, Appendix E | one round of consumer re-verification instead of two | coverage stays ~32%; selection bias accumulates |
| **D-5** | Multiplicity methods | **Research prospectively; do not retroactively apply to closed waves.** | John | §7 item 9 | defensible trial accounting for future waves | effective-trial count grows unmeasured |
| **D-6** | **Condition 6 adjudication** | **`AMBIGUOUS — requires coordinator ruling`.** Do not infer PASS from identity. | John | Appendix C.3 | fixes the gate result at ~5% or 0% | the complete-gate figure remains conditional |

**Not recommended either way:** whether the team programme accepts a multi-season horizon or
renegotiates its promotion criterion. If renegotiated, it must be a registered amendment decided
**before** more evidence accumulates.

---

## 9. No-go boundaries

- **No gate relaxation.** Both the registered prospective gate and the Wave 2 promotion gate stand
  exactly as written. Setting a looser standard after seeing 31.9% coverage or a ~5% pass rate is
  the post-hoc standard-setting this programme spent two waves eliminating.
- **No refit disguised as audit.** If fold identity, K0 or targets cannot be read from frozen
  bytes, it is a new experiment requiring preregistration.
- **No reopening falsified EWMA variants.** WS4 is falsified in the opposite direction; reading
  α=0.05 off the aggregate is what the preregistration forbids.
- **No ROI optimisation.** Proper scores and calibration precede any market threshold.
- **No promotion from incomplete prospective evidence.** Start validity does not imply a gradeable
  sample.
- **No player-prop market claims without evidence.**
- **No post-hoc metric may overturn a closed decision.**
- **No generalisation of the ~5× resolution factor** beyond WS1 without computing it.

---

# Appendices

## Appendix A — Integration-preflight receipt

Captured 2026-08-04T17:29:42Z / 13:29:42 ET, immediately before this document was written.

| | |
|---|---|
| worktree | `.claude/worktrees/player-model-program` |
| branch | `player-model-program` |
| HEAD | **`e79ae2ce261cd6c14571856711790ecd4b128db0`** |
| worktree status | **CLEAN** — zero dirty paths |
| `build_program_state.py --check` | **"substantively current"**; live HEAD `e79ae2c` **(clean)** |

**Cited-artifact identifiers**

| artifact | identifier |
|---|---|
| `forecasts/coverage_receipt.json` | sha256 `00b2274684125f46f73157d0eabe18d68e3978d8` (16 lines) |
| `forecasts/coverage_audit.csv` | sha256 `26b22b90636071a0c2e20bd9ab4cee90bc0ebe96` (84 obligations) |
| `forecasts/forecast_log.jsonl` | sha256 `d1a5886be7d5afb32b8e8647e7d908d008b32fd9`, **n=23**, last `record_idx 22`, terminal `prev_record_sha256 696651c5…` |
| `forecasts/alternative_model_log.jsonl` | sha256 `b6b3da00a73fcf5d8e61c9445015262e6577ba16`, **n=4**, last `record_idx 3`, terminal `prev ec597f60…`, `self 71ebddc3…` |
| `run_ws1.py @ 5313ebd` | blob `c83a48d7301735322568cfd92bbbee3fc3560b4f` |
| `ws1_predictions_operational.parquet @ 5313ebd` | blob `9939f8b5be51192654fa5a33a32fd986f1d80908` |
| `FINAL_AUDIT_MATRIX.json @ 866f3fb` | blob `07c150373de6ce88c0ebf40c556e6b27c4bc39a3` |
| `PROGRAM_STATE.json @ HEAD` | blob `7805d6297e27ae2c2bdc2ac354df2ae80a3a772d` |
| `gate_invocation.py @ HEAD` | blob `57e82b00b2ab5455ce54455780be72dd8cf3b3a9`, recorded sha256 `5c144b12c679…` |

**Regeneration performed during preparation.** HEAD advanced `bf04a3d` → `dd25c5c` → `9dd9629` →
`b6f874c` → `e79ae2ce`. Every cited `PROGRAM_STATE` field was diffed: `frozen_incumbent`,
`canonical_artifacts`, `stop_boundary`, `state_of_play`, `discovery_wave_1` and
`registry.n_records` (41) — **all unchanged**. Two substantive changes were folded into §3:
`dual_frame_audit` became `implemented: true`, and three new gaps appeared. No calculation was
carried forward from an older artifact state.

**Ruling: `INTEGRATION_READY`** — worktree clean; every cited artifact hash agrees with the state
against which the findings were computed.

---

## Appendix B — Correction changelog

Three figures were corrected during preparation. **The values below are superseded and must not be
cited as current results.** They are retained under the programme's no-deletion rule so the
methodology failure is on the record.

### B.1 Complete-gate pass rate — two supersessions

| estimate | method | status | why superseded |
|---|---|---|---|
| **0.0%** | Conditions 1, 2, 4, 4b, 5, 6 bootstrapped per draw; **condition 3 evaluated once on the full sample** and, failing there, applied as a constant `false`. | **SUPERSEDED — invalid methodology** | Condition 3 is a property of each hypothetical sample, not of the observed one. Holding it fixed at `false` forced the conjunction to zero by construction rather than by simulation. |
| **1.6%** (32/2,000) | Nested bootstrap, 2,000 outer × **300 inner** replicates. | **SUPERSEDED — under-sampled** | The registered uncertainty condition specifies a 2,000-replicate date-block bootstrap. A 300-replicate inner estimate of the 95th percentile is noisy and biased: condition 3's pass rate reads 2.5% at 300 inner replicates versus 8.05% at 2,000, which propagates through the conjunction. |
| **≈5%** — 99/2,000 (4.95%) seed 0; 105/2,000 (5.25%) seed 12345 | Nested bootstrap, 2,000 outer × **2,000 inner**, two independent outer seeds. | **CURRENT** | Matches the registered replicate count; two seeds give overlapping Monte Carlo intervals. |

The **direction** of the conclusion was unaffected by either correction. The magnitude changed by
roughly threefold between the second and third estimates.

### B.2 WS1 bound and sign interpretation

An earlier draft stated that the evaluable-fold interval "excludes any effect larger than
0.00071." **That used the wrong side of the interval.** With Δ = challenger MAE − comparison MAE
and negative favouring the challenger, the correct reading is in §4.3: the interval rules out a
*beneficial* reduction larger than ~0.00020 (~0.025% of baseline) and permits *deterioration* up
to ~0.00071 (~0.087%).

### B.3 Scope of the player-grain resolution factor

An earlier draft stated generally that "team-game aggregation costs 5.0× resolution." That factor
is computed on the WS1 turnover surface only and is now scoped accordingly in §4.2.

---

## Appendix C — Power and gate calculations

### C.1 Complete-gate nested bootstrap

`VERIFIED_READ_ONLY_DERIVATION`. **Outer draws 2,000; inner draws 2,000** (the registered
replicate count). **Seed construction:** `np.random.SeedSequence(outer_seed)` drives the outer
date-block resample; `ss.spawn(2000)` yields one independent child seed per outer draw for its
inner bootstrap, so inner streams are reproducible and non-overlapping. Decision universe **2024**
(n=176, 64 dates), per condition 7.

| # | Registered wording (abbreviated) | frozen verdict | seed 0 | seed 12345 |
|---|---|---|---|---|
| 1 | margin MAE Δ ≤ −0.10 | **FAIL** (−0.0153) | 37.80% | 35.75% |
| 2 | home / away / total each degrade ≤ +0.05 | PASS | 87.30% | 87.00% |
| 3 | 90% date-block CI on the margin delta excludes degradation worse than +0.05 | **FAIL** (upper +0.4252) | 8.05% | 8.45% |
| 4 | no season degrades > +0.15 on margin | PASS | 73.15% | 72.35% |
| 4b | none > +0.25 on home / away / total | PASS | 97.15% | 98.45% |
| **5** | **calibration slope not worsened on any target** | **FAIL** (margin 0.782 vs 1.158) | **28.15%** | **26.40%** |
| 6 | beat BENCH-R on margin, or carry an explicit written reason | **AMBIGUOUS** (C.3) | 100% (assumed) | 100% (assumed) |
| 7 | conditions 1–6 must hold excluding 2025–2026 | applied as the universe | — | — |
| | **COMPLETE GATE** | **FAIL** | **99/2,000 = 4.95%**, 95% MC [4.00%, 5.90%] | **105/2,000 = 5.25%**, 95% MC [4.27%, 6.23%] |
| | **with condition 6 FAILING** | | **0/2,000 = 0.00%** (analytic — conjunctive) | same |

**Stability.** The two seeds' Monte Carlo intervals overlap substantially; the ~5% result is not
materially sensitive to nested Monte Carlo noise.

**Condition 7 was applied, not separately simulated** — it defines the universe every row uses.
This is why condition 4 passes here while the ledger's freeze-decision table records it failing on
2026 (+0.501).

**Two distinct gates.** The ledger's *freeze-decision* gate and the *registered promotion* gate are
different instruments: the freeze table's condition 1 reads "some target improves by ≥ 0.10"
(PASS); the registered promotion condition 1 reads "margin MAE Δ ≤ −0.10" (FAIL). **The simulation
above is of the registered promotion gate.**

**Calibration universe.** The ledger reports pooled slopes (margin 0.739 vs 1.018); condition 7
implies a 2024-only evaluation (0.782 vs 1.158). **FAIL under both.** Classification:
**documentation inconsistency and mild specification ambiguity — not an evidence defect.**
Recommend the next contract version state the evaluation universe per condition.

### C.2 Team-promotion power table

`VERIFIED_READ_ONLY_DERIVATION`. **Margin conditions 1 and 3 only; a necessary-condition analysis
and an optimistic upper bound on complete-gate pass probability.** The complete-gate figure is in
C.1 and is **candidate-specific**.

Assumptions: 2.75 games/date, ~253 games/season, ~92 dates/season, K = SE·√dates = 2.1374. Capture
scaling assumes served games are a random subset — **they are not**.

| true effect | 50% | 80% | 90% | seasons @100% (50/80/90) | @95% cap | @31.9% cap |
|---|---|---|---|---|---|---|
| −0.05 | never | never | never | — | — | — |
| −0.10 | 550 dates | never | never | 6.0 / — / — | 6.3 | 18.7 |
| −0.15 | 310 | 1,295 | 3,002 | 3.4 / 14.1 / 32.6 | 3.5 / 14.8 / 34.3 | 10.6 / 44.1 / 102.3 |
| −0.20 | 198 | 452 | 751 | 2.2 / 4.9 / 8.2 | 2.3 / 5.2 / 8.6 | 6.7 / 15.4 / 25.6 |

"Never" is a **design property**, not a flaw: a threshold on the point estimate caps power at 50%
when the true effect sits exactly at it, and near 0 below it.

**Complete-gate simulation under hypothetical effects was not attempted** — shifting the margin
series while holding home/away/total fixed is incoherent (margin ≡ home − away), and no generative
model of joint four-target challenger effects exists.

**Specification gap:** the registered gate carries **no minimum-n condition**. That is why a
64-date season returns a non-trivial pass probability for a candidate whose true effect is −0.015.

### C.3 Condition 6 adjudication

**Registered wording** — `RESEARCH_LEDGER.md` L617: *"6. **Benchmark** — must beat **BENCH-R** on
margin on common rows, or carry an explicit written reason why not."*

**Candidate written reason** — `RESEARCH_LEDGER.md` L805, freeze-decision gate table:
*"| 6 | beats BENCH-R on margin | **N/A** — W2-C1 *is* BENCH-R extended; margins identical |"*

**Supporting fact** — L776: *"margin == BENCH-R margin (2.8e−14)"*. Registration L646 anticipated
the identity: W2-C1 *"makes BENCH-R joint-capable for the first time."*

**Why this is not a clean PASS.** (i) The text was written against the **freeze-decision** gate, a
different instrument from the registered promotion gate, whose condition 6 has never been
adjudicated for W2-C1. (ii) It records **"N/A"**, not an assertion that the clause is satisfied.
(iii) Identity alone cannot satisfy an "or written reason" clause by inference.

**Why it is not a clean FAIL.** The substantive reason is strong and frozen: W2-C1's margin *is*
BENCH-R's margin to 2.8e−14, so "beating" it is definitionally impossible, and the registration
foresaw this.

**Ruling: `AMBIGUOUS — requires coordinator ruling`.** Complete gate ≈ **4.95–5.25%** if condition
6 passes; **0.00%** if it fails.

---

## Appendix D — Workstream auditability

### D.1 WS1 fold verification

`VERIFIED_PROJECT_STATE`. Result commit **`5313ebd`**; `run_ws1.py` blob
**`c83a48d7301735322568cfd92bbbee3fc3560b4f`**; predictions blob
**`9939f8b5be51192654fa5a33a32fd986f1d80908`**.

Rule, verbatim from the frozen source: `tr = train_src[train_src["season"] < s]`;
`te_idx = np.where(df["season"].to_numpy() == s)[0]`. Pure expanding-window walk-forward by season.
Ordering is `sort_values(["game_date","game_id"])`; fold assignment keys on `season` alone.
**No randomness, no shuffle, no row-order dependence.**

**Column reconciliation.** There is **no column named `fold`**. There **is** a `season` column in
every prediction artifact. The verified frozen rule maps `season` → fold as a total, injective
function with no other input. Fold identity is therefore **recoverable exactly, not
approximately** — but it is *derived*, not *stored*. Correct statement: **the fold key is stored;
the fold label is not; recovery is exact.**

**Disclosed split artifact:** the 2021 fold is skipped — 4,850 rows, all season 2021.
Recomputation in §4.3.

### D.2 WS1–WS8 auditability matrix

`VERIFIED_PROJECT_STATE` for artifact survival; resolution factor computed for **WS1 only**.

| WS | commit | Status | What survives / what cannot be adjudicated |
|---|---|---|---|
| **WS1** | `5313ebd` | **`NO_REFIT_AUDIT_AVAILABLE`** | 3 parquets; `pred_K0_intercept_only`, `pred_D`, targets, `did_appear`, `exposure`, `season`. Nominal 35,629 / evaluable 30,779; effective N 25,503 (design effect 1.40); binding cluster **date**. Audit complete for the primary arm. |
| **WS2** | `863a900` | **`PARTIAL_NO_REFIT_AUDIT_AVAILABLE`** | Intrinsic predictions survive and are auditable — intrinsic training folds contain appearers only, so the appearance leak does not act there. **The operational track remains INVALID**: `build_constructions()` imputed to 0.0 before the gate, so a non-zero value certifies appearance. **An intrinsic audit cannot retroactively become operational evidence.** A clean operational result requires a rerun, which is a new experiment. |
| **WS3** | `1e3509f` | **`NO_REFIT_AUDIT_AVAILABLE`** | 4 parquets, K0 present. Cannot revive stage 1, which failed against an intercept. |
| **WS4** | `1b634fb` | **`DIAGNOSTIC_ONLY_NO_FORECAST_AUDIT`** | 2 parquets survive, so player-grain error across the frozen α family is inspectable. But **nothing was fitted** — no feature design, no K0, no fitted intercept — so there is no challenger-vs-K0 comparison to re-adjudicate. Any α selected from these results violates the preregistration. |
| **WS5** | `6d9e3f2` | **`NO_REFIT_AUDIT_AVAILABLE`** | 3 parquets, K0 present. **The only workstream whose player-level metric was preregistered.** Cannot establish team-total value — projected exposure sums to exactly 5× projected team possessions. |
| **WS6** | `5ef1f25` | **`NEW_EXPERIMENT_REQUIRED`** | **No prediction artifacts (3 files, JSON only). No featureless control of any kind.** The within/between two-coefficient form is identified as the cause of arm G's behaviour but was **measured as a diagnostic, never tested as a forecaster.** Requires preregistration **and a matched K0**. |
| **WS7** | `e858e96` | **`NO_REFIT_AUDIT_AVAILABLE`** | 5 parquets. **Never cite `*_v1_leaky.parquet`.** Stratum cuts were frozen against the v1 distribution and not retuned after the repair, so stratum *sizes* are not comparable across v1 and v2 (`has_abrupt_change` 1,339 → 2,368). |
| **WS8** | `c1d2637` | **`CLOSED_NO_SURVIVING_PREDICTION_SURFACE`** | **No prediction artifacts (3 files).** Consists of **oracle counterfactuals, not deployable predictions.** Its 14.18% availability finding is reproduced from WS1's artifact, not WS8's, and stands. |

**Zero-heavy counts.** 23.2% of player-game rows are non-appearers; **MAE alone is not
sufficient.** Poisson deviance, log score, appearance-conditional scoring and subgroup calibration
are scientifically preferable and were **not preregistered**. They are `POST_HOC_DIAGNOSTIC` /
future-contract guidance and **may not overturn any closed result.**

---

## Appendix E — Prospective coverage receipt and start ruling

### E.1 Receipt — as-of 2026-08-04T17:29:42Z / 13:29:42 ET, single vintage

All four artifacts were byte-identical across the 16:33Z, 17:01Z, 17:11Z and 17:29Z captures.

| | published | corrected |
|---|---|---|
| total obligations | 84 | 84 |
| not-yet-due | 22 | 22 |
| before-period-start | 15 | 15 |
| **due** | **47** | **47** |
| timely served | 15 | 15 |
| late records | 2 | 2 |
| data-unavailable misses | 4 | **3** |
| **operational misses** | **26** | **27** |
| unexplained | 0 | 0 |
| **coverage** | **31.9%** | **31.9%** |

Reclassified: 2026-08-03 PHX@CHI T-30m — its only health evidence was two `late_record`s. The
other three data-unavailable rows have genuine timely-served companions and **stand**.

| registered criterion | threshold | actual | verdict |
|---|---|---|---|
| coverage served | ≥ 0.95 | 0.319 | **FAIL** |
| operational misses | ≤ 0 | 27 | **FAIL** |
| all explained | true | 0 unexplained | **PASS** |

**`promotion_grade = false`. Later scheduler runs supersede this receipt.**

**Complete required repair set — four faults, not one.** (i) per-game execution scope (D-c);
(ii) obligation-discovery / lead-window logic (D-b) — **independent, and fails silently**;
(iii) audit classification excluding late records as health evidence (D-a); (iv) lead-window
execution latency (D-d), a separate correction since discovery worked and execution was late.
Logout survival (D-f) is a **reliability improvement, not the primary historical cause**: 25 of 26
job-did-not-run misses predate a functioning scheduler entirely.

### E.2 Start ruling — `record_idx 3`

`project_docs/FREEZE_PROPOSAL_v0.md` defines `prospective_v0` (two fixed daily cutoffs; per-game
dispatching named "a documented v1 upgrade"; "missed days are missed — never backfilled") and
**nowhere makes scheduler logon mode a validity condition**. `prospective_team_pair_v1`'s four
registered start conditions:

| condition | evidence | verdict |
|---|---|---|
| both arms logged before outcomes | base + arm `record_idx 3`, created 14:30:06.442135Z, cutoff 18:00:00Z | **PASS** |
| scheduler operating, "verified by a firing receipt, not by a manual run" | task `Ready`, `LastTaskResult = 0`, autonomous 15-minute firings, event receipts | **PASS** |
| coverage auditor confirms the expected cutoff served | GSV v TOR T-8h = `forecast_logged` | **PASS** |
| model, data and code identities valid on both arms | `ridge_score_level_w2c1_v1`, hash `5d295bb8b99cd34e`, data snapshot + producer commit | **PASS** |

**`RESOLVED_BY_EXISTING_CONTRACT — record_idx 3 is the valid start`**, pending acknowledgment so
the ledger records it. Batch-logon entered in PL-006 as *logout survival* — a reliability
improvement — and was **never a registered validity condition**.

**Three things kept separate.** (1) *Validity of the first record* — established. (2) *Whether the
stream is promotion-grade* — **no**. (3) *Whether current coverage passes the registered gate* —
**no**. **Start validity does not imply a gradeable confirmation sample**, and D-b / D-c / D-f mean
served obligations are not a random subset, which must be accounted for whenever the period is
graded.

**Ledger correction.** PL-006 predicted the first scheduler-produced pair would be CHI v PHX T-30m
at 00:30Z. **That obligation was never served.**

---

## Appendix F — Contract-amendment map

| file | change | owner | bundle |
|---|---|---|---|
| `daily_forecast.py` | per-game scope; stop keying deduplication on `now` (D-c) | engineering | **yes** |
| `evalharness/forecast_log.py` | additive optional `alt_model_predictions`; `SCHEMA`→`/2`; `/1` records stand | engineering (shared: `clv_transfer.py`, `cbs_accounting_v11.py`) | **yes** |
| `prospective_pair/should_run_base.py` | obligation discovery (D-b); lead-window latency (D-d) | team thread | no — internal |
| `prospective_pair/coverage_audit.py` | exclude `late_record` from served-evidence (D-a) | team thread | no — internal |

**Why bundle the first two:** same job family, both cross-thread, and sequential amendments force
two rounds of downstream consumer re-verification. **Why not the latter two:** they sit inside the
team thread's own boundary and touch no shared consumer.

**Required after:** regenerate `coverage_receipt.json`; re-run `verify_chain()` on both chains;
confirm no schema-`/1` consumer breaks; re-run `build_program_state.py`.

**Affected contracts:** team — `prospective_team_pair_v1`, `prospective_v0`. Player — none
directly; the schema change is the extension point a future player arm would use, which is the
argument for making it general now rather than W2-C1-specific.

---

## Appendix G — External research leads

`EXTERNAL_SOURCE_DERIVED` unless marked. Retained at hypothesis-generation strength only.

| lead | source | status |
|---|---|---|
| Multiplicity control for dependent forecast-loss comparisons — Hansen SPA, Model Confidence Set, Romano–Wolf stepdown, White's Reality Check | forecast-evaluation literature | **preferred over** Deflated Sharpe (Bailey & López de Prado), which targets Sharpe ratios on returns |
| Hierarchical forecast reconciliation as a statistical method, not merely a coherence constraint | forecasting literature | **scope to player grain and the distributional layer** — team totals are provably insensitive (5× identity; WS8 oracle allocation is *worse* at −0.0181) |
| Staged distributional construction: marginals → within-player dependence → team reconciliation → cross-team | — | matches the `not started` generative gap |
| WNBA market efficiency — no statistically significant returns to simple strategies, 2007–2012 | Paul & Weinbach (2014), *International Journal of Financial Studies* 2(2) 193–202 | **contradicts** the promotional "soft market" premise |
| Basketball modelling survey — player value, defensive metrics, shot modelling, production curves | Terner & Franks, arXiv:2007.10550 | anchor for a fuller external round |
| CLV as sole validation metric | practitioner corpus | **conflict unresolved** — near-tautological if the close is efficient; no academic source located establishing it for thin markets |
| Practitioner themes — point-in-time state preservation, entity resolution, entry-time definition, mining protection, probability-before-ROI | relayed via a second model | `RELAYED_UNVERIFIED_PRACTITIONER_SOURCE` — hypothesis generation only |

---

*Ends.*
