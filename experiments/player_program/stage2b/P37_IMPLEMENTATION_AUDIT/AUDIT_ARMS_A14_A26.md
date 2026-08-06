# P37_IMPLEMENTATION_AUDIT — Auditor slice A14–A26 (A14, A15, A16, A17, A18, A20, A21, A22, A23, A24, A25, A26)

IMPLEMENTATION AUDIT. Establishes that the code is the preregistered code. Establishes nothing about results, which remain sealed.

Auditor independence: this auditor implemented none of the arms it audits (independent context; no P36 arm or runner unit was authored here). No file under `SEALED_RESULTS/` was read; no comparative historical performance of any challenger was inspected; no real fold was fitted. All fits executed in this audit ran on synthetic fixtures only, through the P36 runner's own blinding gate, which admitted them without any unseal flag.

---

## 1. Frozen inputs verified before reliance

| artifact | command | result |
|---|---|---|
| P35 task cards | `Get-FileHash .../P35_FREEZE_TASK_CARDS/SPEC.json -Algorithm SHA256` | `68EF22F4FCA15A2E8D91EEEB9B84B86F86E8E9E7CAAB5E23E6A9B950385B4D32` — MATCHES the dispatch pin. All card comparisons below are against these bytes. |
| P22 guard bytes | `Get-FileHash .../P22_POSTGAME_SURROGATE_GUARD/postgame_surrogate_guard.py` | `951e8513...b73ceeda` — matches `runner_constants.GUARD_SHA256_PINS` |
| P23 guard bytes | same, `merge_guard.py` | `b0e75419...3ca3b7a8` — matches |
| P25 guard bytes | same, `offset_dependency_guard.py` | `c78e70b6...cc100e95` — matches (also matches the A01-withdrawal basis pin in P35) |
| P26 validator bytes | same, `validate_k0_matched.py` | `1fc798da...557d7e16` — matches |
| P27 guard bytes | same, `fold_estimability_guard.py` | `1fbec0d6...ddb25d2f` — matches |
| team_cities.csv | `Get-FileHash data/reference/team_cities.csv` | `10a544fd...128ac42d` — matches the OP-5 pin |
| possessions_raw_v2.parquet | `Get-FileHash experiments/player_program/possessions_v2/possessions_raw_v2.parquet` | `7200881f...b15a4b1a` — matches the frozen pin (`runner_constants.REAL_ARTIFACT_SHA256`) |

Schedule facts measured for the findings below (identity/coverage reads of frozen inputs, no performance quantity touched): `possessions_raw_v2` carries **1,495 distinct game_ids — the identical game set as `team_possession_prior_v1` (set difference empty both directions, measured)** — including the four universe-excluded 2021 openers `1022100001..1022100004` with **167/156/165/180** possession rows respectively; `team_possession_prior_v1` carries 2,990 rows / 1,495 games with exactly 8 `pace_resolved == False` rows, all on those four game_ids. (`game_id` is a **string** column in both artifacts; a first integer-typed membership probe returned zero rows for all four openers and was corrected — recorded here so nobody repeats the dtype mistake.)

## 2. Line-by-line code/formula identity vs the frozen cards

Method: each arm's module(s) read in full and compared clause-by-clause against its P35 task card (model string, K0_MATCHED construction, intercept table membership, guard_invocation pins, fold_local_fallback, kill_conditions_frozen, amendments_applied) and, where the card is carried by hash reference, against the P33 record and named P31 hypothesis records.

| arm | files | formula identity | notes |
|---|---|---|---|
| A14 | `arms/A14/A14_expansion_intercept_decay.py` | **MATCHES** | eta, exp_i, n_i (contract-schedule clock via constructor-injected `contract_schedule`), tau=5, K0 grants gap/depth/opp_depth/decay/intercept and no expansion term, free intercept arm+null, S7 floor 10, single-fold kill chain all card-exact. Colon-free treatment column name: disclosed (C-1). |
| A15 | `arms/A15/A15_gap_by_depth_asymmetry.py` | **MATCHES** | s(d)=1/(1+d/5), asym, gap*asym treatment, all mains incl. asym granted to null, free intercept, no active-set rule. Three card-silent kill operationalisations disclosed (C-2). |
| A16 | `arms/A16/arm_a16.py` | **MATCHES** (equivalence argument required, C-3) | dev from lagged (realised_reg_equiv − projected), shift(1)+rolling(5, min_periods=1), fillna(0), opponent lookup by (game_id, team_id); zero-parameter null = incumbent; no intercept. |
| A17 | `arms/A17/feature_construction.py`, `a17_transition_mix_share.py` | **MATCHES** | possession-count-weighted decayed share, threshold 8s, h=10, disc=0.5, Δ=1-indexed kernel (disclosed, C-4); F2 per-side training-mean imputation computed from `fold["train_idx"]` only; is_playoff nuisance; no intercept. |
| A18 | `arms/A18/feature_construction.py`, `arm_a18.py` | **MATCHES** | z1 = med_dur_opp − med_dur_own, same-season strictly earlier, pooled median per the P31 OPPONENT_MECHANISM_H1 text (disclosed, C-5); E=3 on distinct prior games in the possessions frame; zero-parameter null; no intercept. |
| A20 | `arms/A20/arm_a20.py` | **DEVIATES — finding B-1** | z2 = ftr_own − ftr_opp and E_TO={"turnover"} card-exact; but the trailing window and the E=3 count run on the **universe frame's rows**, not the completed-game clock the card's "as A18" clause and the literal formula ("ALL of t's strictly earlier same-season games") denote. |
| A21 | `arms/A21/feature_construction.py`, `arm_a21.py` | **DEVIATES — finding B-2** | nc materialised as a decayed **mean of per-game shares** (game-weighted), where the frozen phrase — identical in shape to A17's — denotes a decayed **share of possessions** (possession-weighted, A17's construction). Kernel-indexing disclosure is value-irrelevant (see B-2); F2 imputation constant pooled own+opp (value-identical on cluster-complete training folds, C-6). |
| A22 | `arms/A22/feature_construction.py`, `arm_a22.py` | **MATCHES** | TV churn 0.5·Σ|u_last − u_base| on usage shares; u_last/u_base split disclosed with a four-fact convergence argument (C-7); decay recurrence matches A17's Δ=1 convention (checked algebraically); churn:=0 at n_prior ≤ 1; is_playoff nuisance; no intercept. |
| A23 | `arms/A23/feature_construction.py`, `arm_a23.py` | **DEVIATES — finding B-4** | caps 7/4, opener rules, redefined completed-game prior rule, S7 AI rule (≥10 nonzero-contrast training clusters, disclosed reading) all card-conform; but rest is computed on the fitting universe frame with no contract-schedule input, so the 8 opener-team second-2021-games misresolve under "previous COMPLETED same-season game". Opposite-sign kill returned UNDECIDABLE (verified correct: neither P33 nor P35 states the predicted sign numerically — P33 A23 record read directly), C-8. |
| A24 | `arms/A24/feature_construction.py`, `arm_a24.py` | **MATCHES the card; the card is defective — finding B-3** | rest on the contract-schedule clock via a separate constructor-injected `contract_schedule` (the correct clock, disclosed reading of "contract game date"); cap 10; x = mean of the two sides; zero-parameter null. Fails closed on franchise-debut rows the card's "fallback: none needed" claim does not cover. |
| A25 | `arms/A25/arm_a25.py` | **MATCHES** | 0/1 is_home_offense pass-through, strict 0/1 check, zero-parameter null = incumbent, no intercept, SCHEDULE lag kind, guard-positive-control note carried. Cleanest module in the slice. |
| A26 | `arms/A26/feature_construction.py`, `arm_a26.py` | **DEVIATES (bounded) — finding B-5** | z5 = c_own − c_opp with c_t = −(sched_t − Lbar); LOO one-clock as-of-g rule implemented exactly per L6; E=3-plus-undefined-LOO imputation exact; RAW counts, no OT reweighting. Lbar cancels **exactly** in z5 (algebraic identity, so the disclosed same-season-league-mean scope question is value-irrelevant to z5). But the prior-game history/E-count iterate over **universe rows**, same root cause as B-1/B-4. |

Intercept-table conformance: A14/A15 declare `uses_global_intercept() == True` and materialise the explicit all-ones `intercept` column in arm AND null; all ten others declare `False` and no design carries any constant column — matches `runner_constants.ARMS_WITH_FREE_GLOBAL_INTERCEPT`/`ARMS_WITHOUT_GLOBAL_INTERCEPT`, which I compared against the P35 `intercept_structure` table directly (byte-equal membership). The runner enforces this ("checked, not trusted") in `validate_arm_module`.

Guard invocation pins: every module in the slice returns `declared_family() == "SUBSTANTIVE"` and `recalibration_declaration() == "NOT_APPLICABLE"`, offset `log_exposure`, incumbent projection `projected_team_off_possessions` — card-exact for all twelve.

Franchise-continuity hooks: A14/A16/A17/A21/A22/A24 return True and pin team_cities at `10a544fd...` (the P33 precondition list names exactly these six in my slice); A15/A18/A20/A23/A25/A26 return False and are verifiably absent from that list. A23 carries the narrower game_date-join precondition, which no shared wrapper enforces — the module flags this itself (C-9).

## 3. Test suites — run by this auditor

Commands: `python <arm>/TESTS.py` (A14, A15, A16, A20, A26), `python <arm>/tests/TESTS.py` (A18, A21, A22, A23, A24), `python A17/tests/TESTS_A17.py`, `python A25/tests/TESTS_A25.py`.

| arm | my run | fleet record | match |
|---|---|---|---|
| A14 | 19/19 (module prints "ALL 19 TEST FUNCTIONS PASSED") | 19/19 | yes |
| A15 | 18/18 | 18/18 | yes |
| A16 | 14/14 (14 test headers counted) | 14/14 | yes |
| A17 | 12/12 | 12/12 | yes |
| A18 | 9/9 | 9/9 | yes |
| A20 | 16/16 | 16/16 | yes |
| A21 | 14/14 | 14/14 | yes |
| A22 | 13/13 | 13/13 | yes |
| A23 | 9/9 | 9/9 | yes |
| A24 | 14/14 | 14/14 | yes |
| A25 | 10/10 | 10/10 | yes |
| A26 | 16/16 | 16/16 | yes |

**164/164 test functions pass under this auditor's own execution**; per-arm counts equal the P36 SPEC.json fleet record exactly. The end-to-end tests exercise the full-design gate battery (P22, P25, P26-wrapper, P27) inside `runner.run_arm` on synthetic fixtures; all gates passed in my runs (every non-deactivated fold reached `EVALUABLE`).

**Write-scope side effect, disclosed (see §7):** several suites unconditionally rewrite their own `TEST_RECEIPT`/`*_receipt.json` artifacts inside `P36_IMPLEMENT_ARMS/arms/*` on every run. My mandated re-execution therefore re-wrote those bytes for A17, A18, A21, A22, A23, A24, A25 (file list in §7). I measured the rerun delta on A17 field-by-field: **only wall-clock `seconds` fields differ; no substantive content changes** (`p37_parity` diff, §6 command). The receipts are not byte-deterministic by design; the coordinator's baseline commit remains the canonical byte record.

## 4. Row-parity spot-verification (two arms + K0_FLAT + incumbent, synthetic fixtures)

Script: `p37_parity_a14_a26.py` (auditor scratchpad; reads frozen P36 code only, writes nothing into the repository). One shared synthetic universe (252 rows / 126 game clusters / 2 folds, blinding-gate-admitted), A18 and A25 both run end-to-end through `runner.run_arm` with the same folds and prohibited basis. **21/21 checks passed:**

* per fold: test `n_rows` and `n_clusters` **identical** across the two arms (84/42, 84/42);
* per fold: the `K0_FLAT` diagnostic record (both variants, all fit fields) **byte-identical** across the two arms' receipts (JSON-canonical string equality) — same rows in, same bytes out;
* per fold: each arm's zero-parameter K0_MATCHED null MAE equals the directly computed **incumbent** MAE with **exact float equality** (A18: 7.5993027086284695 both; A25: same; fold 2: 7.020714004965743 both);
* the zero-parameter null prediction path is **bitwise** `exp(log_exposure)` (`np.array_equal` on the mu vectors) — the "null IS the frozen incumbent exactly" clause holds at the byte level, not merely to tolerance;
* `exp(log_exposure)` equals the `projected_team_off_possessions` column to ≤1e-12 on every test row;
* pooled `n_rows` identical across the two arms' receipts.

This verifies the acceptance criterion "row parity is byte-identical across arms, K0_FLAT, K0_MATCHED and the incumbent" as far as it is verifiable pre-P38: the runner presents one immutable universe and one fold list to every member, the paired test bootstrap uses one shared seeded draw per (fold, b), and the two spot arms + both K0s + incumbent all scored exactly the same rows with byte-identical overlap where the designs coincide.

## 5. Findings — severity B (adjudication required before P38; none trips a stop condition)

**B-1. A20: prior-game clock deviates from the frozen "as A18" / literal-formula clock; live on the real archive.**
`ArmA20._own_trailing_rate` computes both the expanding ftr window and the E=3 prior-game count over the rows of the supplied **universe** frame. A18 — whose rule A20's card adopts verbatim ("E = 3 imputation as A18") — counts distinct prior games on the **possessions** frame. Measured: the four universe-excluded 2021 openers ARE present in possessions_raw_v2 (167/156/165/180 possession rows), so at P38 the two clocks diverge for the 8 opener teams' 2021 rows. Synthetic boundary demonstration (script §4, exit-checked): on identical schedule facts A18 counts 3 prior games and emits a defined nonzero z1 while A20 counts 2 and imputes z2 := 0. Real-archive exposure: the imputation flips on each opener team's 4th completed 2021 game (≤8 rows), and the trailing-mean CONTENT (the opener game's forced-turnover rate) is excluded from all of that team's subsequent 2021 windows under the module's clock. P35 `construction_pins.n_clock_pin` states "every other prior-game COUNT is computed on the CONTRACT SCHEDULE … The universe-row clock is barred," which reads against the module's choice; the module does **not** disclose this as an ambiguity (its docstring asserts the universe window "is exactly what prior-games-only, same-season means"). Bounded: 2021 rows only, training-side in every fold, past-facts-only under either reading (leakage status unchanged), value lives only in the arm's treatment column with machinery identical arm/null. Not resolvable here: either pin the universe-row clock on the record or require re-derivation on the possessions/contract clock.

**B-2. A21 vs A17: one frozen phrase, two constructions — A21's aggregation level deviates from the literal text and from A17's implementation of the same clause shape.**
P33 formula strings: A17 "short_off(t,g) = w-weighted **share of t's offensive possessions** in P(t,g) with duration_sec <= 8"; A21 "nc(t,g) = w-weighted **share of t's offensive possessions** in P(t,g) flagged non_competitive_conservative". A17 implements the literal reading (ratio of decayed possession-count sums — possession-weighted); A21 implements a decayed weighted **mean of per-game shares** (game-weighted). Measured on identical inputs through both modules' own functions (script §4): 0.341214 (A17 construction, matches its closed form to 1e-12) vs 0.613857 (A21 construction, matches its closed form to 1e-12) — a 0.27 absolute divergence on a [0,1] share. A21's own disclosed ambiguity covers only the decay-kernel indexing, which I verified is **value-irrelevant** for A21 (its rank−1 exponent differs from A17's Δ convention by one uniform factor of base, which cancels in the normalised mean); the aggregation level is the substantive divergence and is **not** disclosed. D6 ("A17/A19/A21/A22 decay h=10 lambda=0.5") binds these arms to one shared trailing-evidence convention family, which strengthens the case that the divergence is a deviation rather than two admissible readings. Bounded: deterministic, symmetric machinery arm/null, past-facts-only, treatment-column-only. Adjudicate which aggregation level is the preregistered one; if A17's, A21's nc must be rebuilt (identical decayed-sum machinery exists in A17's own recurrence).

**B-3. A24: fails closed on franchise-debut rows — WILL raise on the real universe at P38 (disclosed by the implementer; the defect is the card's).**
The card's "fallback: none needed (cross-season prior game covers openers)" is measured-false for a true franchise debut: three exist on the archive (team 1611661331's 2025 debut; 1611661327 and 1611661332's 2026 debuts — named in A14's own frozen card), where the debuting team's rest is structurally undefined. The module refuses to invent a substitution (correct under standing rules 1/7) and `build_design` raises `A24ConstructionFailure` whenever any row's x is undefined — which on the real universe includes the debut rows AND their opponents' rows (the symmetric mean is NaN on both sides of each debut game, ≥6 rows, including fold-4/5 TEST rows). Consequence: **A24 is unrunnable at P38 as implemented** until an adjudicated fallback (or row/fold disposition) is frozen. Because A24 is the preregistered LAG OPERATOR POSITIVE CONTROL ("if the machinery cannot cleanly evaluate this arm, no lagged-arm result should be trusted"), leaving this to fail at fit time would contaminate the positive-control reading; it must be disposed before P38, by a registry-appended amendment, not by a silent P38 patch.

**B-4. A23: rest computed on the fitting universe frame; the redefined "previous COMPLETED same-season game" misresolves for the 8 opener teams' second 2021 games.**
The four excluded openers are completed contract-schedule games (they exist, dated, in team_possession_prior_v1 — measured), so under the P35 L2/OP-4 redefinition the opener teams' second 2021 games have a previous completed same-season game. `compute_rest_and_opener` sees only universe rows (the runner hands `build_design` the same frame it fits on; A23 takes no separate contract-schedule input, unlike A14/A24 which both do), so those 8 rows are misclassified as openers: bundle_AI forces their contrast to 0 (and they enter the S7 support count as zeros); bundle_OM assigns f := cap. The module's `lag_specs` rationale asserts "the universe frame IS the contract-schedule history," which is false under the runner's calling convention at P38. Bounded: 8 rows, 2021, training-side, past-facts-only, symmetric machinery. Same adjudication fork as B-1; the A24 constructor pattern is the in-fleet remedy if the contract clock is pinned.

**B-5. A26: same universe-row clock root cause as B-1/B-4, with two exact mitigations verified.**
`compute_z5` builds team histories, E-counts and LOO opponent means from universe rows joined to possession counts; the opener games' raw counts (which exist — B-1 measurement) never enter raw/sched means or E-counts. Mitigations verified: (i) the league trailing mean cancels **exactly** in z5 (z5 = −(sched_own − sched_opp); algebraic identity in the module's own arithmetic), so the disclosed same-season-Lbar scope question and the Lbar content are value-irrelevant to the design column; (ii) the E=3 trigger flip and window-content differences are confined to 2021 rows of the 8 opener teams and their early-season opponents' LOO means. Report-only elsewhere card-exact (the L6 one-clock rule is implemented precisely as pinned).

**No Severity A finding.** Nothing in this slice changes the primary target, the K0 structure, the inference structure, the candidate universe, the cutoff-valid feature set, or the leakage status; every B item is an arm-level construction question on past-facts-only quantities, bounded to 2021 training rows (B-1/B-4/B-5), a single frozen phrase's aggregation level (B-2), or three named rows requiring a pre-P38 disposition (B-3). No stop condition is tripped; nothing here is resolved inside this node.

## 6. Findings — severity C (disclosed pins for P37 fleet-level affirmation)

* **C-1 (A14):** treatment column materialised as `expansion_decay_interaction` instead of the card prose spelling `exp_i:exp(-n_i/5)`, to avoid a P26 R6 false positive against the card's own "no expansion-indexed term" null. The R6 tension is real (verified against `validate_k0_matched`'s colon-splitting rule); the arithmetic is card-exact. AFFIRM recommended; nothing frozen pins the literal column-name string.
* **C-2 (A15):** three card-silent operationalisations, all disclosed: negative refutation = any fold's interval entirely below 0; "concentrated" = majority share ≥ 0.5; "top-|asym| bucket" = top quartile. Card-consistent, conservative; needs a pinned affirmation so P38 cannot re-choose.
* **C-3 (A16):** the module's "last 5 resolved universe games" equals the card's "resolved members of the last k=5 completed games" **on this archive** because every unresolved game is a team's first game (the 8 NULL-projection rows are all openers — measured); the two readings could diverge only if an unresolved game occurred mid-history, which does not occur. Tie-break reuse of (game_date, game_id) disclosed. AFFIRM as archive-conditional equivalence.
* **C-4 (A17):** Δ=1-indexed decay kernel pinned, 0-indexed alternative flagged. A22 matches A17's convention; A21's differs but value-irrelevantly (B-2 covers the substantive divergence). Affirm one fleet convention on the record.
* **C-5 (A18):** pooled-median reading (one median over all qualifying possessions, zero-duration rows included) resolved from the originating P31 H1 text, not invented. A18's E-clock (possessions frame) coincides with the contract-schedule game set exactly (measured: identical 1,495-game sets), so A18 carries no B-1-type exposure. AFFIRM.
* **C-6 (A21):** F2 imputation constant pooled over own+opp defined values; value-identical to per-side means on cluster-complete training folds (games never split), hence F2-conformant in value. Note only.
* **C-7 (A22):** u_last/u_base closed form pinned from four convergent frozen facts; reading is forced, not invented. AFFIRM.
* **C-8 (A23):** "opposite-sign rejection" returned UNDECIDABLE_NO_PREDICTED_DIRECTION — verified correct: the P33 A23 record (read directly) states no numeric predicted sign for beta anywhere. Adjudicate a direction (from the mechanism sentence) or freeze the undecidable status.
* **C-9 (schema/vocabulary gaps flagged by modules, all real on inspection):** `fold_local_fallback.action` enum has no value for deterministic row-level substitution (A16/A18/A20 use `not_applicable` with the true rule stated in `trigger`); A23's game_date-join precondition has no enforcing wrapper in `guard_harness.p23_check`; the P35 `intercept_structure.consequence` sentence omits A18/A20/A23/A24 from the zero-parameter-null list although their constructions are identical to the named A16/A25 (documentation incompleteness, no code effect).
* **C-10 (runner-level RAISED items, my slice's exposure):** the K0_FLAT dual-reading (runner RAISED item 1) was exercised in the parity run — both variants computed, labelled, byte-identical across arms; diagnostic-only status confirmed in every receipt seen. The P27 fold-policy parameter and bootstrap p-value operationalisation (RAISED items 2–3) are consumed unchanged by every arm in this slice; naming/formula sign-off is a fleet-level P37 item, not per-arm.

## 7. Contradictions found (documents vs documents, or mandate vs mandate)

1. **"Run the arm test suites yourself" vs "write ONLY your own file":** the suites for A17/A18/A21/A22/A23/A24/A25 unconditionally rewrite receipt artifacts inside `P36_IMPLEMENT_ARMS/arms/*` on every execution. My runs re-wrote: `A17/TEST_RECEIPT_A17.json`, `A17/tests/artifacts/A17_receipt.json`, `A18/TEST_RECEIPT.json`, `A18/tests/artifacts/A18_receipt.json`, `A21/A21_TEST_RECEIPT.json` (+ artifacts copies), `A22/TEST_RECEIPT.json` (+ artifact), `A23/TEST_RECEIPT.json` (+ both bundle receipts), `A24/TEST_RECEIPT.json` (+ artifacts copies), `A25/TEST_RECEIPT_A25.json` (+ artifact). Measured field-level delta on rerun: **wall-clock `seconds` fields only**; no hash, count, verdict or config field changes. A14/A15/A16/A20/A26 receipts were not rewritten (original P36 timestamps intact). Reported, not silently reconciled; the coordinator's baseline commit is the canonical byte record and can restore pre-audit bytes if byte-stability of receipts is required.
2. **P35 n_clock_pin ("every other prior-game COUNT … CONTRACT SCHEDULE; the universe-row clock is barred") vs the A18/A20/A26 cards' silence on their E-count clock:** the K6 amendment is applied by name only to A07/A09/A11/A12/A13/A14 cards, yet the pin's own text is universal. A18 lands on the contract-equivalent clock (possessions frame, game-set-identical — measured); A20/A26 land on the universe clock. This document-internal scope ambiguity is the root of B-1/B-5 and must be adjudicated once, fleet-wide, not per-module.
3. **A24's frozen "fallback: none needed" vs A14's frozen franchise-debut facts:** two P35 cards jointly entail that A24's claim is false on three known rows (B-3). The implementer found it and failed closed; recorded here as a frozen-record contradiction, not an implementation defect.
4. **First probe of opener membership in possessions_raw_v2 returned zero rows for all four openers (integer-typed probe against a string game_id column).** Corrected measurement: all four present. Recorded because an auditor repeating the integer probe would wrongly conclude B-1/B-4/B-5 are empirically empty.

## 8. What I could NOT establish

* Which frame P38 will hand each `build_design` — the B-1/B-4/B-5 clock findings assume the runner's documented convention (the fitting universe is the design frame); if P38 instead injects contract-schedule-clock constructions upstream, the exposure changes and must be re-measured then.
* A20's OP-8 dictionary-drift diagnostic (the module cannot compute it without the full P34 OP-1 level dictionary and honestly declines to fabricate it; carried forward as the card requires).
* Any behaviour of these designs on real folds: no real fold was fitted, per the blinding rules. Everything in §4–§6 is code identity, schedule facts, and synthetic execution.
* Byte-identical row parity on the REAL universe across all 22 arms — structurally guaranteed by the shared runner (one universe object, one fold list, shared seeded draws) and spot-verified on synthetic; the real-frame confirmation is a P38 receipt check by construction.
* Whether the other two auditors' slices reach consistent verdicts on the shared C-10 runner items (independent contexts by design).

## 9. Verdict for this slice

Code identity: **10 of 12 arms card-exact** (A14, A15, A16, A17, A18, A22, A24*, A25, plus A21/A23 structurally conform outside their named findings; *A24 is card-exact and the card itself is defective). **Three bounded construction deviations (A20, A21, A23/A26 clock family) and one unrunnable-at-P38 fail-closed (A24) require P37 fleet adjudication before any fit.** Tests: 164/164 pass under independent execution, matching the fleet record. Row parity, K0_FLAT diagnostics, zero-parameter-null-equals-incumbent, and the guard byte pins are verified by measurement. No canonical artifact was modified by this audit except the non-substantive test-receipt timing rewrites disclosed in §7; Arm D untouched; nothing under SEALED_RESULTS read; no stop condition tripped.
