# P42_SCIENTIFIC_COMPLETION — Cycle-1 possession challenger program: scientific completion report

SCIENTIFIC COMPLETION REPORT. States what the wave established and what it did not. Does not itself promote anything.

**Node:** `P42_SCIENTIFIC_COMPLETION` · **Lane:** possession · **Author:** coordinator (per node role: coordinator + two reviewers)
**Authorities:** D042 (P40 close), D041 (unseal), D039 (P37 adjudication), the frozen P33/P35 preregistration, GRAPH_POLICY §5/§7.
**Primary sources (all committed, none sealed):** `stage2b/P40_PRIMARY_ADJUDICATION/ADJUDICATION.json` (sha256 `6b26bb6951866236042f4c546009ebe937d1eb6a661b318c0779f28242bd3525`), `ADJUDICATION_TABLE.md`, `P41_DOWNSTREAM_TURNOVER_CONFIRMATION/DOWNSTREAM.json` (sha256 `741626e2263aeb611cbe90029a68009edf137afb2d7922af440c3ef368e242ee`). A small number of contextual figures come from other committed, unsealed artifacts and are attributed in-text where used: the decision ledger (D041 P39 verdict, D045 board rows), `GRAPH_EVENTS.jsonl` (D040 A24 append), and `arm_registry.jsonl` (record count). Nothing under `SEALED_RESULTS/` was read by this node; every adjudicated statistic below is copied from the adjudicated record, produced by `adjudicate.py` against the sealed receipts under D041 authority.

---

## 1. What was tested, and how

Twenty-two preregistered challenger arms, 29 fitted elements after carded enumerations. Card accounting: 23 frozen cards at P35 = 22 fitted arms + A06 (card frozen, its admission conditionals never satisfied); A01/A04/A19 were withdrawn at P34, *before* the freeze, and sit in the resurrection-barred registry section outside the 23. Fitted against the frozen incumbent `D_ewma_shrunk` (K=200, α=0.1) on the settled primary target `REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS`. Five D006 expanding walk-forward folds (train_lt_2022 … train_lt_2026); pooled out-of-fold evaluation over 2,572 rows / 1,286 game clusters; game-clustered bootstrap (10,000 draws) for inference; per-arm `K0_MATCHED` nulls; family-Holm multiplicity at α=0.05 with dual-partition runs where family assignment was disputed (stricter governs). Implementation was audited (P37, D039), fits ran blind (P38), seal integrity was certified before opening (P39: PASS_WITH_FINDINGS — 21/21 structural checks, 0 Severity A, 1 Severity B node-contract self-contradiction reconciled by the D041 ruling), and only P40 opened results (D041).

The frozen primary gate, all four clauses: (a) pooled ΔMAE > 0, (b) family-Holm rejection, (c) no kill condition fired, (d) P28 possession-first ordering respected.

## 2. Decision for every arm — accepted / null / failed

**Accepted: 0 of 29 elements. No challenger passed the preregistered gate. The frozen incumbent stands unchallenged; P43 (champion replacement) does not open.**

Scientific classification of the 29 FAIL verdicts (Δ = pooled out-of-fold MAE improvement over the arm's own K0_MATCHED null, possessions; positive = arm better; p = two-sided, game-clustered, uncorrected):

### Preserved lead — null under multiplicity, sign-stable positive (1)

| element | family | Δ pooled | p | decision |
|---|---|---|---|---|
| A07_early_season_transient__single | COLDSTART_FALLBACK | **+0.0540** | 0.0280 | **NULL this cycle — preserved lead.** Largest improvement in the fleet (arm 2.81090 vs null 2.86494). Fails Holm in BOTH candidate families (COLDSTART m=5 threshold 0.01; alternate CAL+A07 m=4 threshold 0.0125; must reject in both). Treatment intervals exclude 0 (positive) in 4 of 5 folds. The carded n≤5 concentration kill was NOT evaluable from the receipt (§6). May not be promoted on this evidence; may re-enter ONLY as a newly preregistered arm in a future cycle (carried per D043). |

### Failed — significant harm (2)

| element | family | Δ pooled | p | decision |
|---|---|---|---|---|
| A10_lambda0.5 | timeseries_shrinkage | −0.0022 | 0.0138 | **FAILED — significantly worse than its null.** Permanent negative result. |
| A20_forced_turnover_contrast | OPPONENT_MECHANISM_F1 | −0.0004 | 0.0496 | **FAILED — significantly worse than its null** (marginally; kill also fired). Permanent negative result. |

### Killed by carded condition, effect otherwise unresolvable (1)

| element | family | Δ pooled | p | decision |
|---|---|---|---|---|
| A14_expansion_intercept_decay__single | COLDSTART_FALLBACK (fixed Holm slot, promotion-ineligible by card) | +0.0173 | 0.0432 | **FAILED — carded single-fold-decidable kill fired** (single evaluable fold train_lt_2026, 430 rows). Diagnostic only by preregistration; no effect claim survives. |

### Null — no detectable effect on the primary target (25)

All remaining elements: |Δ| ≤ 0.0116 possessions, no p below the Holm threshold in any governing family run, and several with kills fired independently. Grouped by mechanism family with pooled Δ (possessions) and p:

- **Calibration controls** — A02 (−0.0002, 0.41), A03 (−0.0056, 0.23), A05 (−0.0046, 0.10; kill fired under both preserved fold-set readings, C2). *Calibration-shaped context adjustments do not move pooled possession MAE.*
- **Timeseries shrinkage** — A08_K20 (−0.0116, 0.11), A08_K80 (+0.0019, 0.87), A09 κ∈{2,10,50} (−0.0011…−0.0069, 0.19–0.68), A10_λ0.2 (−0.0018, 0.18), A11 ρ∈{0.25,0.5,0.75} (+0.0004…+0.0008, 0.17–0.67). *The incumbent's timescale/shrinkage settings are at a local optimum; every perturbation is null or harmful (see A10_λ0.5 above). Consistent with the earlier ws4 self-falsification of the EWMA-timescale family.*
- **Cold-start / carryover** — A12 (+0.0020, 0.14), A13 (−0.0070, 0.20), A15 (+0.0001, 0.96; 2 kills). *Roster-carryover mechanisms are null; the early-season phenomenon, if real, was detected only in A07's transient form — an arm that is itself null this cycle (see §3's guards).*
- **Lagged tempo / mechanism contrasts** — A16 (−0.0003, 0.12), A17 (−0.0031, 0.71), A18 (−0.0001, 0.27), A26 (−0.0004, 0.36). *Opponent-mechanism decompositions add nothing measurable.*
- **Evidence quality** — A21 garbage-time contamination (−0.0048, 0.52). *The hypothesized contamination channel does not convert to MAE.*
- **Personnel continuity** — A22 lineup churn (−0.0038, 0.61).
- **Schedule / rest / home** — A23 rest differential, both preserved source-consistent bundles (bundle_AI +0.00002, 0.90, β̂ negative in all 5 folds; bundle_OM +0.00005, 0.71, β̂ positive in all 5 folds — opposite-signed point estimates, both below carded resolution, never averaged; D7 preserved), A24 rest advantage symmetric (−0.0032, 0.50; appended via the D040 single-writer amendment, 50→51 registry records, byte-identity verified), A25 home-offense contrast (−0.0055, 0.29; home-offense β negative with 0 excluded in 4/5 folds — a reproducible coefficient signal with NO MAE payoff). ***Rest, schedule and home-court context did not detectably move PACE in this cycle.** Score, margin and win probability were not tested by this cycle; whether such factors affect those targets is an open cycle-2 question (coordinator priors are recorded separately in D046 as planning context only, and are not findings of this program).*

## 3. Bounded effect estimates and uncertainty

- **Incumbent benchmark (VERIFIED):** pooled OOF MAE **2.86649** possessions, 2,572 rows / 1,286 clusters, five expanding folds — the shared K0_MATCHED null of the nine arms whose null is exactly the incumbent ([log_exposure], zero fitted parameters: A02/A03/A16/A18/A20/A23/A24/A25/A26).
- **Effect bounds:** every challenger effect on the primary target lies in **[−0.0116, +0.0540]** possessions of pooled MAE. Among promotion-eligible, multi-fold-evaluable elements, only A07's +0.0540 (1.9% relative) has an uncorrected p < 0.05 with positive sign, and it does not survive multiplicity; A14 (+0.0173, p 0.0432) also has positive sign at uncorrected p < 0.05 but is promotion-ineligible by card, single-fold, and killed by its carded single-fold-decidable rule (§2). Per-element treatment-coefficient 95% intervals (game-clustered **train-refit** bootstrap, B=2,000; the test-side ΔMAE/p inference uses B=10,000) are recorded in `ADJUDICATION.json` `elements[*].per_fold[*].treatment_intervals_95`; A07's intervals exclude zero (positive) in folds train_lt_2023/2024/2025/2026 (4 of 5).
- **A07 null-strength guard (K5 amendment, carried from the record):** `MAE(K0[A07])` is **not** an incumbent benchmark — A07's matched null carries receipted incumbent-path features and is deliberately *stronger* than the incumbent. Consequently A07's arm MAE (2.81090) may **not** be compared against the incumbent's 2.86649; the only licensed comparison is A07 vs its own K0_MATCHED null (2.86494).
- **Non-comparability guard (carried from P40):** the operational full-history turnover-lane MAE ≈ 2.9675 is NOT comparable to the pooled OOF possession MAEs here (different targets, row sets and pooling). No cross-claim is made anywhere in this report.

## 4. Failure explanations and downstream implications

1. **Why the sweep is null:** consistent with the incumbent's EWMA already capturing the predictable component of pace on this universe *to within limits no carded context mechanism improved* (D042's own bound). Context mechanisms (rest, home, opponent, personnel, garbage time) either (i) do not affect possession counts at a detectable magnitude, or (ii) carry structure collinear with the trailing window the incumbent already smooths. The recurring pattern of **coefficient rejections without MAE payoff** (A25, A10_λ0.2, A17, A08_K80's L_t — each with intervals excluding zero in ≥3 folds yet Δ ≈ 0) is consistent with (ii): coefficient-level structure that does not convert into out-of-fold loss — recorded in the adjudication as evidence for future ideation only, via proper channels, never as established effects.
2. **Downstream (P41, closed):** the carded downstream turnover confirmation closed with **zero downstream numbers computed** (`downstream_numbers_computed: 0`; all 29 candidates refused under the P28 R3 refusal; the frozen scorer's bytes verified sha256-identical to the P28 pin and never invoked). No candidate was scored downstream, so no rescue was attempted or possible — "a number that does not exist cannot rescue anything" (`DOWNSTREAM.json`). This is a discipline confirmation, not an empirical comparison: it does **not** establish that downstream scoring was tried and failed to help. Criteria: two satisfied vacuously-with-measurement, one positively. P28 ordering held program-wide: no downstream number existed before any primary verdict.
3. **For cycle 2 (D043):** pace is settled as an *ingredient*. The score-family gap to the market (paired: +0.38 total / +0.80 margin / +0.017 Brier — from the committed D045 board rows, not from this adjudication) is D043's declared territory: efficiency estimation (F12), distributional structure (F13), and candidate context channels on scoring — carrying this cycle's evidence that such channels do not *detectably* act on pace, and nothing more.
4. **Permanent negative results:** the two significant harms and every kill stand as permanent, citable negative results under the preserve-nulls rule; the family-level nulls bound future ideation (nothing here may be quietly retried in the same form).

## 5. Contradictions and preserved disagreements (reported, not reconciled)

Summarized from the adjudicated record (`contradictions_found`, full text in `ADJUDICATION.json`) — **six**: **C1** sealed-receipt basis strings over-claim "card-pinned" for the fold-2022 structural deactivations of A05/A15/A17/A21/A22 (operative authority is the D040 fold-local P25 wrapper; manifest finding P38-R1 mechanism (ii)); **C2** A05's two fold-set readings (card {2022..2025} vs sealed {2023..2026}) — identical verdict under both; **C3** A24's registered enumeration count is measured FALSE under its own predicate (3/6 registered vs 5/10/7 measured) — no accounting consequence, contradiction stands; **C4** P26 R8-shape BLOCKING findings on A02/A03/A05 tolerated per the frozen P35 r8_scope_adjudication and D039 EXEC-M7 (recorded per element, not a silent pass); **C5** the executor's 26-vs-21 dispatch-count contradiction (D040) — the fitted-element count of record is 29 receipts across 22 arms (card accounting per §1: 23 frozen = 22 fitted + A06 frozen-but-never-admitted; A01/A04/A19 withdrawn at P34 before the freeze, outside the 23); **C6** the kill-sign wording of A12 ("β2 sign contradicting decay") and A13 ("β3 < 0") admits both a point-sign and a rejection reading — both readings were evaluated and reported under the kill entries; no verdict depends on the choice.

Preserved disagreements (`preserved_disagreements_reported_not_harmonized`) — all carried, none harmonized: **D1** A11 (blend-null at ρ=1) and A12 (term-removal null with incumbent-path features) are non-incumbent-equivalent nulls; both preserved readings fitted, both fail independently; **D2/D5** family-assignment disputes discharged by dual-Holm under BOTH partitions (every disputed element fails under both); **D3** A05's two positions travel with the arm (same verdict); **D6** four trailing-window conventions evaluated per-arm exactly as frozen, never pooled — all fail independently; **D7** A23's two source-consistent bundles give OPPOSITE-signed β̂ (see §2), both below carded resolution, never averaged; **D9** three OT conventions fitted per-arm as frozen (A12 rescale / A16 regulation-equivalent / A26 raw) — all nulls/fails independently, and **A26's symmetric-cancellation assertion remains preserved-as-unmeasured** (the §2 family gloss "add nothing measurable" describes the MAE outcomes, not a measurement of that assertion).

## 6. Unresolved limitations

1. **Kills not evaluable from receipts:** the stratum-concentration kill inputs (A07 n≤5 concentration; A11 thin-evidence; A12 n≤5-stratum and all-rows-only decomposition; A15 top-|asym| bucket) and the A21/A22 depth-absorption robustness refits are absent from the sealed receipts; P40's scope was adjudication of the sealed record, not refitting. Marked NOT_EVALUABLE_FROM_RECEIPT. **No promotion decision depended on any of them** (every affected element fails on (a) or (b) regardless) — but A07's preserved-lead status carries this asterisk: its concentration kill is unchecked. Any future A07 preregistration MUST make that diagnostic a recorded, receipted output.
2. **Universe bound:** all findings are bounded to the corrected candidate universe (2,982 team-game rows / 1,491 clusters; OOF subset 2,572/1,286) and WNBA 2021–2026. The 2024 league operational changes (charter travel) sit inside the sample; no era interaction was carded in cycle 1.
3. **Retrospective only:** every number is blind *walk-forward retrospective*. Nothing here is prospective evidence, and none of it speaks to market-relative or betting performance.
4. **Single primary target:** conclusions bound possession-count prediction only. Efficiency, score, margin, win probability and player-level targets are untested by this cycle.

## 7. Prospective-confirmation recommendation

**Recommended, in order:**
1. **Prospective shadow run of the frozen incumbent** on the remainder of the 2026 season via the existing daily forecast + live capture infrastructure (F15 design, PASSED): log pregame possession projections at a declared cutoff, score them as games complete, and compare the prospective MAE distribution to the retrospective 2.86649 benchmark with game-clustered intervals. This generates new prospective evidence alongside the VERIFIED retrospective row (it does not convert that row), at low marginal cost on already-running infrastructure.
2. **A07 re-registration in a future cycle** (per D042/D043): new preregistered card, the concentration-kill diagnostic as a mandatory receipted output, early-season-window definition frozen before any result is seen. Cycle-1 evidence may motivate but can never fund its promotion.
3. **No prospective spend on the null families** (shrinkage perturbations, opponent mechanisms, rest/schedule/home *on pace*): the program should decline to re-test these forms absent a new mechanism, per §4.4's retry bound.

## 8. Stop conditions

None tripped. Nothing in this report changes the primary target, K0 structure, inference structure, candidate universe, cutoff-valid feature set, or leakage status. (The P38-R1 escalation was resolved by D040 before sealing; the A24 scope item was ruled at arm level under D041 assignment.)

---
*Every adjudicated statistic above was copied from `ADJUDICATION.json` / `DOWNSTREAM.json` by the coordinator via `python -c` JSON reads (no recomputation, no sealed access). Contextual figures from other committed, unsealed artifacts are attributed in-text where used: the D045 board rows and D041 P39 verdict (decision ledger), the A24 50→51 registry append (`GRAPH_EVENTS.jsonl`, corroborated by `arm_registry.jsonl`'s 51 records). Where a figure could not be established from the record, it is listed in §6 rather than estimated.*
