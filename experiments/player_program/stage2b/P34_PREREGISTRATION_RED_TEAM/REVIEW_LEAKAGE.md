# P34 REVIEW — LEAKAGE dimension

**Reviewer:** independent leakage reviewer (did not author P33; no other P34 reviewer file was read; the P34 output directory was empty when this file was written and only file NAMES would have been listed).

ADVERSARIAL REVIEW. Reviewers are independent of the preregistration author. A clean review does not make an arm true; it makes it fittable.

## STOP-CONDITION STATEMENT (read first)

**No stop condition is tripped by this review, and the reasoning is stated rather than assumed.** Nothing found here changes the primary target, the K0 structure, the inference structure, the candidate universe, the cutoff-valid feature set, or the leakage status of any adjudicated column. The two findings closest to the line (L1: A16's archive-retrievability claim contradicted by the frozen bytes; L2: A23 bundle_AI's "previous SCHEDULED game" has no receipted source) are both **arm-level definitional defects of the exact shape D021 already ruled non-halting** when it amended A06 to INADMISSIBLE-UNTIL-RECEIPTED instead of halting ("arm-level definitional defect... NO HALT, AMEND"). Both are required changes before the P35 task-card freeze, not universe or target changes. If the coordinator reads either differently, the halt belongs to the coordinator, not to a resolution inside this node.

**Verdict: ACCEPT_WITH_REQUIRED_CHANGES.** No Severity A leakage was found. Four Severity B findings must be closed before P35; if L1 or L2 cannot be closed, the affected arm (A16) or bundle element (A23 bundle_AI) must be withdrawn or made conditional, not papered over.

---

## 0. Hashes verified before anything was read

`Get-FileHash -Algorithm SHA256` on all four pinned inputs, run first:

| artifact | expected | measured | match |
|---|---|---|---|
| P33_PREREGISTRATION_DRAFT/SPEC.json | 066b2a04... | 066B2A046021DB119A75E2C847C325F6F4E40BB6E418BC7B31C8D072D347D093 | YES |
| P33_PREREGISTRATION_DRAFT/REPORT.md | 6d945b86... | 6D945B8663323526BA29FC74CDF963C800FF26D12BAC846E12EF69D1681248AB | YES |
| P32_CANDIDATE_SYNTHESIS/SPEC.json | 1dc25981... | 1DC25981ED14BE0EF59C994A47A99970D790B644D8CDCE354C617F9198C2138C | YES |
| P30_EVIDENCE_PACKET_V3/EVIDENCE_PACKET_V3.json | 95d2412c... | 95D2412C28CE34BB6330F5055BC9087693C1D70ED21A12B4EDB5B5F950875E75 | YES |

Guard citations inside the draft, re-hashed by this reviewer: `postgame_surrogate_guard.py` = 951E85132F470FDD939C8039958F0544413AAAA485DA5DBA7DA9C1B9B73CEEDA (matches the draft's P22 pin) and `offset_dependency_guard.py` = C78E70B6A0603B15BD74DD4DD798BA698D962565E813B2EEE8DF9360CC100E95 (matches the draft's inputs pin). `NEAR_R2 = 0.999**2 == 0.998001` and `SPEARMAN_THRESHOLD = 0.999` read directly from the guard source — the collapse-rule constants the draft cites are the constants in the bytes.

## 1. What this review did

For every feature of all 26 arms I traced the claimed pre-tip availability path back to (a) the P2A `ADJUDICATION.csv` column classification (ELIGIBLE / LAGGED_USE_ONLY / CUTOFF_UNPROVEN / PROHIBITED), (b) the S1–S9 findings in `stage2a/V2_STOP_CONDITION.json`, (c) the frozen producer `possession_features.py`, and (d) the frozen artifacts themselves, which I read live (schema and identity checks only — **no residual, no accuracy, no error statistic, no performance number of any kind was computed**; nothing under SEALED_RESULTS was touched). Measurement script: `p34_leakage_checks.py` in this session's scratchpad, reproduced in substance in section 5; every number below came from running it or from the one-liner shown beside the number.

Line citations in the draft's link derivation were checked against the bytes of `possession_features.py`: OFFSET_COLUMN at line 135, `np.log(...)` construction at line 319, offset-as-log docstring at lines 62–64, incumbent-prediction identity docstring at lines 399–406, `log_exposure` rename at line 515, target construction at lines 197–212. **All six citations are accurate.**

## 2. Findings

### L1 (Severity B) — A16's archive-retrievability claim is contradicted by the frozen bytes; the "defined on all 2,982 rows in every fold" fallback claim does not follow

Draft claim (SPEC A16.features.cutoff_evidence, repeated at REPORT.md lines 181–184): *"team_possession_prior_v1.parquet carries projected_team_off_possessions per (game_id, team_id) row for all 2,990 team-games (read live)"* — used to discharge P32's could-not-establish #3.

Measured by this reviewer (pandas over the frozen parquet):

- rows: 2,990; `projected_team_off_possessions` **non-null on 2,982, NULL on 8**;
- the 8 null rows are exactly the `pace_resolved == False` rows: game_ids 1022100001–1022100004 (the D010 2021 opening day), two team-rows each.

The COLUMN exists on all 2,990 rows; the VALUE does not. A16's `dev_team` is a mean over the team's **last k = 5 completed games** of (realized − ARCHIVED projection). Opening-day 2021 games are completed real games: they sit inside the trailing windows of the first ~5 games of every 2021 team even though they are excluded from the universe as target rows. For those prior games the archived projection is NULL and the per-game dev is **undefined**. The draft's fallback line — "resolved universe already excludes the no-prior-games stratum; defined on all 2,982 rows in every fold" — conflates target-row exclusion (D010) with history availability and is false as written for early train_lt_2022 training rows.

This is **not leakage** — no post-tip information flows anywhere — but it is a frozen factual claim the bytes contradict (standing rule 1: report, never silently reconcile) plus an **undeclared construction convention** that P36 would otherwise improvise (skip unresolved prior games? shrink the window? impute?). Any improvised choice made after results start existing is exactly what preregistration exists to prevent.

**Required change:** correct the claim to "2,982 of 2,990 rows carry a non-null archived projection; the 8 opening-day rows do not", and freeze A16's handling of a trailing window containing an unresolved prior game (recommended: that prior game contributes no dev term and the window mean is over the resolved members, identically in arm and null; if fewer than 1 resolved member, the row falls under a declared active-set rule). Decidable now; touches only train_lt_2022.

### L2 (Severity B) — A23 bundle_AI's prior-game definition ("previous SCHEDULED same-season game") has no receipted pre-tip source; the same evidentiary standard that made A06 conditional is not applied to it

A06 was amended (D021) to INADMISSIBLE-UNTIL-RECEIPTED precisely because **scheduled-season facts have no receipted artifact**: the draft itself records "this node measured no such artifact inside experiments/player_program/". Yet A23's bundle_AI defines rest from the "previous SCHEDULED same-season game". The only receipted date source is `game_date` joined from master_team — a **retrospective bulk scrape of PLAYED games** (P2A: "joined from master_team... the join carries master_team's revision risk"). A scheduled-but-not-completed game does not exist anywhere in the receipted archive, so:

1. bundle_AI as written is **unimplementable from receipted artifacts**; an implementation will silently substitute the completed-game definition — which is bundle_OM's definition — leaving the two "source-consistent bundles" differing only in cap (7 vs 4) and opener rule while claiming a scheduled-vs-completed distinction the data cannot express;
2. if a P36 implementer instead reached for any post-hoc schedule source to honor the word "SCHEDULED", that source would be **unadjudicated under S8 and unreceipted under P23** — the exact A06 defect.

Direction-of-leakage note, measured honestly: because the archive records only played games at played dates, the substituted completed-game definition uses **past facts only** — there is no forward information flow in either reading. This is a receipt/constructibility defect and an admissibility-consistency defect, not an information leak. That is why it is B, not A.

**Required change (one of):** (i) redefine bundle_AI's prior-game rule to "previous COMPLETED same-season game" and state that on this archive the scheduled reading is unimplementable (the bundles then differ in cap + opener rule only, honestly); or (ii) make bundle_AI conditional on the same preseason-published schedule receipt as A06 path (a), with its element leaving the schedule_context_family denominator if the receipt does not land. Silence is not an option: the current text preregisters a construction that cannot be built from the frozen inputs.

### L3 (Severity B) — A06 repair path (b) is an unreviewed feature definition entering after the red team; its leak-freedom is not decidable today

The A06 conditional preregistration is decidable and leak-free in three of its four limbs: path (a) (preseason-published schedule artifact, P23-receipted, hash-pinned before P35) is a genuine pre-tip source; the exclusion rule (no receipt ⇒ PREREGISTERED_CONDITIONAL_NOT_FIT, 2 elements leave the denominator) is decidable by the P35 freeze date; and the formula correctly bans realized season length and season-as-feature (S8 fold-identifier hazard). But path (b) — "redefinition of the phase/index denominator from past-only schedule facts" — names **no concrete formula**. If path (b) is exercised, a feature this red team never saw enters the fit set with only the generic call-site guards between it and the fitter. "Past-only schedule facts" is a family of constructions, not a construction; its S8 status cannot be adjudicated in advance of knowing what it is.

**Required change:** the P35 task card must bind path (b) to: a concrete frozen formula, hash-pinned; explicit S8/P2A-style adjudication of every input column; P22 invocation like every other feature; and a recorded note that the P34 leakage review did **not** review the redefined feature (so a positive A06 result under path (b) carries that caveat permanently). With that binding, both repair paths and the exclusion rule are decidable and leak-free; without it, path (b) is a preregistration escape hatch.

### L4 (Severity B) — A13's centering constant `cbar_F` is not pinned to training-only computation

A01/A04 pin their centering explicitly: "m_bar = training-fold mean of log_exposure" (SPEC A01.formula; REPORT.md line 56). A13's treatment is `beta3*(cont_i − cbar_F)*dev_prev_i` and **nowhere in SPEC.json or REPORT.md is cbar_F defined** (grep for `cbar` returns only the formula itself; the only nearby rule is the n=0 fallback "cont := training-fold mean", which is a different constant). If cbar_F were computed over the whole fold (train + test), every training row's treatment column would embed post-cutoff lineup information — a genuine, if numerically mild, cutoff violation, and the only construction in the draft where one is still possible by omission rather than by data. The same pen stroke should confirm the n=0 imputation constant ("training-fold mean" — of which rows' cont, over which window) is training-only, which it already says, and that both constants are recomputed inside each training-cluster bootstrap refit or declared fixed — either is defensible, but it must be written.

**Required change:** one sentence in the P35 task card: "cbar_F is the mean of cont_i over the fold's TRAINING rows only, as is the n=0 imputation constant; identical in arm and null." Decidable now; costs nothing.

### L5 (Severity C, record) — the A19 live-ball dictionary question is decidable today, and the answer is that the withdrawal fires

The draft defers "whether end_reason distinguishes live-ball turnover terminators" to the P35 dictionary freeze (could_not_establish #2). Measured by this reviewer from the frozen possessions parquet: `end_reason` has exactly 9 levels — `defensive_rebound, inferred_flip, made_ft_final, made_ft_nonfinal_flip, made_shot, miss_flip_no_rebound, period_end, technical_ft, turnover`. There is a **single undifferentiated `turnover` level and no steal/live-ball distinction anywhere in the level set**. A19's E_LB (live-ball subset) cannot be expressed; its preregistered withdrawal-as-design-failure ("dictionary cannot distinguish live-ball turnover terminators — mechanism unmeasurable in this artifact") will fire at P35 unless a different column is smuggled in — which the fail-closed dictionary rule correctly forbids. A20 (all turnover terminators) is unaffected: the `turnover` level exists. From the leakage lens the fail-closed behavior is clean; the consequence for the LAGGED_TEMPO_MIX denominator belongs to the multiplicity reviewer, and I flag the cross-reference without resolving it.

### L6 (Severity C, record) — two leak-free determinism gaps to pin at P35

- **A26:** the LOO term `sched_t` does not pin the as-of date of each opponent's `raw_opp` (as of the meeting date j, or as of the target date g). Both readings use only games strictly earlier than g — leak-free either way — but they are different numbers; pin one.
- **A08:** "last K completed league games strictly before game_date(g)" needs a deterministic tie-break when the K-boundary falls inside a multi-game date (tip times are unusable: the V2 record shows the tip_times null mask nearly equals fold 1). Any date-granular rule is leak-free; pick one and write it down.

### L7 (Severity C, record) — design constants frozen from pooled full-archive feature marginals

A03's t = 3 (justified by the pooled depth histogram), A08's {20, 80} (justified by pooled league-games-per-season counts), and A16's k = 5 were all chosen using feature marginals computed over ALL seasons, including seasons that are test data in early folds. I re-computed the depth histogram live and it is exactly as the draft states — {0: 37, 3–9: 76 each, 10: 2413}, SHALLOW(≤3) = 113 — so the justification is honest about its inputs. No outcome or performance value entered any of these choices, which is the line the program draws; but the record should say plainly that fold-1 designs embed full-archive feature-marginal knowledge. This is standard preregistration practice and I do not ask for a change; I ask that it not be described as fold-blind if anyone ever tries.

### L8 (Severity C, record) — the self-frozen quasi-Poisson IRLS convention is leakage-inert

Scrutinized as instructed. The response-family freeze moves no data across the tip boundary: the mean structure (log link + receipted `log_exposure` offset) is derived from receipts I verified line-by-line; the family choice affects only the IRLS working weights on TRAINING rows, and no likelihood-based standard error is ever consumed (all inference is game-cluster bootstrap). From the leakage dimension the freeze is inert. Whether freezing an unreceipted family is acceptable convention-invention is a legitimate question — it is simply not a leakage question, and I leave it to the reviewers whose lens it touches.

## 3. What was traced and found CLEAN (the negative results, preserved)

- **Same-game surrogates:** no arm's prediction path touches current-game `period`, `duration_sec`, `end_sec`, `is_overtime`, `game_minutes`, `master_team.minutes` (S1), score-differential columns, `non_competitive_conservative` at target-game value, `era` (CUTOFF_UNPROVEN — A19 explicitly routes era drift through the fail-closed dictionary instead), or tip times. Every use of a LAGGED_USE_ONLY column is declared as an aggregate over strictly earlier completed games AND routed through P22 at invocation — which matters because P2A's own hazard text says the table licenses *proposing* lagged constructions, not using them ("that construction needs its own adjudication — this node does not license one"), and D005 proved the shared feature_gate enforces none of this. The draft consistently carries the P22-at-call-site obligation; the licence citations are therefore load-bearing only jointly with P22, and the draft says so.
- **Realized-OT derivatives:** the target's own realized-OT normalization (lines 197–212) is the explicitly licensed completed-game-outcome-only use. Prior-game OT enters A12 (rescale), A16 (regulation-equivalent normalization), A26 (raw, unmeasured-cancellation preserved as unmeasured) — all lagged-game realized values, licensed under S8, D9 conventions frozen per-arm and never harmonized. No current-game OT anywhere in any prediction path.
- **S8 lagged-use-only compliance, sampled against bytes where bytes exist:** `is_overtime == (period > 4)` on all 238,563 possessions (re-measured; matches P2A's exactness claim); the incumbent's tiered-switch source counts (2762/183/37/8) re-read from PROJECTED_EXPOSURE_RECEIPT.json and they match the A11 d1_resolution citation exactly; playoff counts by season re-measured (2026: 0 playoff rows; cumulative playoff clusters 17/40/60/82/106 — the A05 fallback trigger's numbers are right); expansion first-seasons consistent with the season table (2025: one new franchise's 46 rows; 2026: 57). The arm-level lag operators themselves (d_t, dev_prev, churn, shares) are P36 scope and DO NOT EXIST YET as code — see section 4.
- **A16's ELIGIBLE join keys:** `(team_id, game_date)` has **zero duplicate rows** in the frozen prior artifact (measured) — no doubleheaders, so the declared join is well-defined 1:1 (the retrievability defect L1 is about null VALUES, not about the join).
- **Fold/cutoff structure:** per-row strictly-earlier discipline (DECISION_TIME_RULE) plus D006 expanding windows; test-time features that consume earlier test-season games are the incumbent's own walk-forward convention and are per-row cutoff-clean. Training-fold constants (m_bar, Lbar_train) are declared training-only everywhere except the L4 gap. Games are never split (train_clusters == train_rows/2 in the draft's fold table, arithmetic checked).
- **Centering/imputation symmetry:** every imputation and active-set rule I traced (A03/A04 10-cluster floor, A05 numeric trigger, A11 2021 fallback, A12/A13 active-set, A18/A20/A26 E=3, A22 |P|=1, A23 opener rules) is declared identical in arm and null — the leak channel where an arm's fallback differs from its null's was checked arm-by-arm and does not appear.
- **A06's formula-level hygiene:** season never enters (S8 fold-identifier hazard respected); realized season length banned by text; the truncated-2026-fold auto-kill is preregistered. The residual defect is only L3's path-(b) openness.
- **A07/A09/A14/A24/A25 schedule-fact features** (n counts, exp_i, rest level, is_home_offense): pure functions of past schedule facts and identities; is_home_offense is taken by identity join per the S8 SEVERE multiplicity hazard note, never by row aggregate. Clean.

## 4. What this review could NOT establish, and why

1. **The lag operators as implemented.** Every "strictly lagged" assertion for A08–A22/A26 is a specification, not code; P36 has not built them. I verified the specifications' availability logic and the frozen inputs' schema, and I verified the one retrievability claim that WAS checkable against bytes (L1 — and it failed in part). The strictly-lagged property of the eventual implementations rests on P22 invocation per design, which is preregistered but has not run. No amount of review now substitutes for those receipts then.
2. **master_team game_date revision risk** (A23/A24, and the fold boundaries themselves): the dates are a retrospective scrape; whether any game's recorded date differs from its as-of-tip date is unmeasurable inside this repository. Declared in the draft; carried, not resolved.
3. **Whether a preseason-published schedule artifact exists anywhere** (A06 path (a), L2 remedy (ii)): outside this node's read scope; the draft says the same.
4. **The A04/A09 near-affinity numbers:** d_t does not exist yet; the frozen test at the P25 call site is decidable and I confirmed the guard constants it will use are in the guard bytes.

## 5. Contradictions found between documents and bytes

1. **A16 retrievability (L1):** SPEC A16.features cutoff_evidence + REPORT.md lines 181–184 say "all 2,990 team-games" carry the archived projection; the bytes say 2,982 non-null / 8 NULL. Frozen bytes govern. This is the only document-vs-bytes contradiction found.
2. **A23 bundle_AI vs the A06 admissibility standard (L2):** document-vs-document inconsistency — the same unreceipted "scheduled" concept is conditional in one arm and unconditioned in another.

Measurement commands (all run in this session, worktree root): `Get-FileHash -Algorithm SHA256` for section 0; pandas reads of `team_possession_prior_v1.parquet` and `possessions_raw_v2.parquet` for null counts, duplicate keys, season×season_type counts, end_reason levels, is_overtime exactness, and the depth histogram; `json` read of `PROJECTED_EXPOSURE_RECEIPT.json` for source_counts. No fit, no residual, no accuracy statistic, no SEALED_RESULTS access.

## 6. Disposition requested

ACCEPT_WITH_REQUIRED_CHANGES. Close L1–L4 in the P35 task-card freeze (each is a one-to-three-sentence frozen declaration; none requires new data or touches any frozen artifact). L5–L8 are records. No arm requires withdrawal on leakage grounds today; A16 and A23 bundle_AI become withdrawal candidates only if L1/L2 are not closed. Disagreement with any other reviewer's lens is expected and should be preserved, not averaged.
