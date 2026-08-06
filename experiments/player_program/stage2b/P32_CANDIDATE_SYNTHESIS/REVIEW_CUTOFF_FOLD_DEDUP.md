# P32_CANDIDATE_SYNTHESIS — INDEPENDENT ADVERSARIAL REVIEW
## Lens: cutoff validity, fold support, deduplication honesty

Reviewer: independent adversarial reviewer (one of two; lenses differ).
Date: 2026-08-06.

**Blindness attestation.** I did not read, list, or glob the other reviewer's file, and I did not read, list, or glob anything under `experiments/player_program/stage2b/SEALED_RESULTS`. My reads inside the node directory were exactly `SPEC.json` and `REPORT.md`, by direct path. I did not run git, spawned no subagents, performed no fit, and inspected no comparative performance of any challenger.

**Stop-condition statement, up front.** I do **not** believe this synthesis trips a node stop condition. Nothing in it changes the primary target, the K0 structure, the five-fold inference structure, the candidate universe, the packet-adjudicated cutoff-valid feature set, or the leakage status. The **closest call** is Finding F-1 (A06's `season_last_scheduled_date` denominator): if the coordinator judges that admitting a schedule-endpoint field with no packet adjudication *changes the cutoff-valid feature set*, that is a halt-and-raise, not an in-node fix. My own reading is that it is an arm-level definitional gap repairable at P33–P37 without touching the packet's adjudication, so I report it as a required change rather than a stop condition — but I state the alternative reading plainly so the coordinator can disagree.

---

## 1. Hash verification (STEP 1)

Rederived by `Get-FileHash -Algorithm SHA256` over raw bytes, compared case-insensitively to the frozen values in my dispatch. **ALL TEN MATCH.**

| file | result |
|---|---|
| P32_CANDIDATE_SYNTHESIS/SPEC.json (f71fc445…) | MATCH |
| P32_CANDIDATE_SYNTHESIS/REPORT.md (175a17f1…) | MATCH |
| P31_FINAL_V3_IDEATION/GENERATION_ORDER_V3.json (898f4b80…) | MATCH |
| HYPOTHESES_adversarial_identifiability.md (bf589616…) | MATCH |
| HYPOTHESES_calibration_control.md (1085da13…) | MATCH |
| HYPOTHESES_coldstart_fallback.md (8d145ce1…) | MATCH |
| HYPOTHESES_cutoff_leakage.md (3d8c096b…) | MATCH |
| HYPOTHESES_opponent_mechanism.md (88cda948…) | MATCH |
| HYPOTHESES_timeseries_shrinkage.md (ea2cbd42…) | MATCH |
| P30_EVIDENCE_PACKET_V3/EVIDENCE_PACKET_V3.json (95d2412c…) | MATCH |

## 2. What I measured

Reconciliation was recomputed from the SPEC bytes by a python script (scratchpad `reconcile_p32.py`), not taken from the report: **20 families, 26 arms, 5 rejections, 26 + 5 = 31 = the candidate union** (GENERATION_ORDER_V3 `n_hypotheses_reported`: 5+6+6+5+5+4 = 31, re-summed). **30 provenance entries covering exactly 30 distinct source sections, each cited exactly once**; the 31st candidate (AI-H4) appears only in the rejection ledger. Arm ids are unique. **No orphans, no double-counting.** Per-source arm-provenance coverage: adversarial 4, calibration 6, coldstart 6, cutoff 5, opponent 5, timeseries 4 — matches the report's claim including adversarial 4/5.

A token scan of all 26 retained arm definitions for prohibited material (`game_minutes`, `master_team.minutes`, `era`, `team_cities`, tip, market) returned three hits, all verified by reading to be **negative** mentions ("NOT built from era", "no team_cities join occurs", "schema drift … never by conditioning on the CUTOFF_UNPROVEN era column").

Citation spot-checks that **passed** (citation exists in EVIDENCE_PACKET_V3 and says what SPEC.json claims): A01/A02 (offset guard rule text including the verbatim "single preregistered nonredundant contrast (own-opp) is admissible with fold-local full rank" and "recalibration is its own hypothesis family"); A03/A04/A15 (D009 names pace_gap, pace_evidence_depth, opp_pace_evidence_depth, is_playoff_game; declared standard-(a) dependency preserved verbatim); A05 (season_type ELIGIBLE + the exact hazard "fold-degenerate: 0 playoff games in fold 2026", and the S7 known-degeneracies clause requiring the §4 fallback); A07/A09/A11/A12 (S8 ELIGIBLE rows for game_date/season/team ids; LAGGED_USE_ONLY hazard text "only an aggregate over STRICTLY EARLIER games may be proposed" quoted accurately in A17); A13/A22 (off_p*/def_p* LAGGED_USE_ONLY; ascending-order-statistics caveat quoted correctly); A14 (S2 guard rule text on team_id 1611661317 quoted correctly); A21 (non_competitive_conservative basis text quoted correctly); A25 (is_home_offense ELIGIBLE text verbatim); P22 tool sha 951e8513… matches; ACTIVE_SET_RULE_PREREGISTRATION sha 327fa8ec… matches; R5's "132 rows" matches V2_STOP_CONDITION E5; A03's "37–42% of MSE" matches S6 (0.37098/0.42488); train_lt_2022 205 resolved clusters matches the packet.

S1–S9 sweep over all 26 retained arms: no arm touches master_team.minutes (S1); no arm joins team_cities or the venue set (S2, but see F-3); no injury field (S3); offset-affine terms confined to the declared calibration family, stricter CC-H4 null adopted (S4); only the own−opp contrast enters, never the pair (S5); S6 both-directions trap handled explicitly in A03/A04/A12/A14/A15; S7 remedies declared per arm; **every use of an S8 LAGGED_USE_ONLY column in every retained arm is strictly lagged** — I found no unlagged use of a lagged-licensed field anywhere in the 26 arms (S8); nested per-arm nulls with the explicit no-permutation-control declaration on A06/A08 (S9).

Duplicate-rejection verification (source texts compared directly): **R1 TRUE** (OM-H3's ±1 is an affine recoding of AI-H3's 0/1 given the intercept structure; identical mechanism and identification argument). **R2 TRUE** (identical mechanism and functional class; cap and opener rule are specification choices, preserved as choice sets). **R3 TRUE** under the synthesis's own declared merge standard (same mechanism, same substrate — offset deviation × depth; kernel-vs-tier is a basis choice; the null disagreement is materially recorded as D1a and the stricter null is the scientifically correct one — CF-H2's slope-1-only null would let a global gain error load onto the depth kernel, the S4 confound one derivative up). **R4 TRUE** (same mechanism, same feature material, same S9 discipline; monotone-transform vs thirds-bins is a basis choice; the truncated-2026 self-binding is carried verbatim into A06). Hunt for surviving duplicates: A06 vs A07 (calendar clock, cluster-constant vs team clock, within-cluster varying — genuinely different regressors, correctly one family/two arms); A06 vs A08 (schedule position vs data-driven trailing level — distinct); A04 vs A09 and A08 (mutual collapse-on-P25 declarations present); A23 vs A24 (orthogonal projections, different predictions); A17 vs A18, A19 vs A20 (different functionals AND different projections, both carried as declared formulation disagreements). **No surviving duplicate found.**

## 3. What I could not establish

* Whether any cutoff-valid artifact carries *scheduled* (as opposed to realized) season endpoints (bears on F-1); the packet adjudicates no such field and my read scope contains no data artifacts.
* Whether `own_est`/`opp_est` are receipted-path outputs covered by the Stage 1B scoped acceptance, and whether `own_est − opp_est` coincides with `pace_gap` (bears on F-2); requires the incumbent's receipted construction, outside this review's inputs.
* A14's actual expansion cluster counts per training fold (same read-scope limit the synthesis itself declared).

---

## 4. Findings

### F-1 (Severity A) — A06's cutoff-validity citation does not cover the feature's denominator; no packet source establishes a cutoff-valid "scheduled season length"

A06's single feature is cited to "S8 table: game_date ELIGIBLE ('schedule fact; it is the cutoff boundary itself')". That citation exists and is quoted accurately — **for the per-game date**. But the constructed feature is `(game_date − season_first_game_date) / (season_last_scheduled_date − season_first_game_date)` (or "nth scheduled game normalized by SCHEDULED season length"). `season_first_game_date` is a past fact at any in-season cutoff; **`season_last_scheduled_date` is a property of FUTURE games** and is covered by no adjudication anywhere in EVIDENCE_PACKET_V3. The only date source the packet names is master_team — a retrospective bulk scrape of *realized* games. If the denominator is implemented from the archive (max game_date within season), it becomes a function of realized playoff series lengths — post-cutoff, outcome-dependent information — and, in fold 2026, of the capture truncation at 2026-07-31 itself. The arm text does say "never realized length" (carried from AI-H5), so the SPEC does not *authorize* the leaky implementation — but it retains an arm whose defining denominator has **no cited cutoff-valid source and may be unconstructible from adjudicated material**. Under my dispatch's rule (a citation that does not support the claim is Severity A) this is an A. Required change: either name the cutoff-valid source for scheduled season endpoints (a preseason-published schedule artifact, receipted through P23), or redefine the phase/index denominator from past-only schedule facts (e.g., fixed calendar offsets from `season_first_game_date`, or regular-season scheduled length if and only if a cutoff-valid source exists). Note the same question infects the CC-H5 thirds cut identically; this is not basis-choice-specific.

### F-2 (Severity B) — A02's cutoff citation is an admissibility ruling, not a cutoff adjudication

A02's feature (`own_est − opp_est`) cites `enforcement.offset_dependency_guard_S4_S5.rule` plus "D009 standard (a)". The guard rule is about *identifiability beside the offset* (which pairs may not enter; which contrast may). It is not a cutoff-validity adjudication of `own_est`/`opp_est`. D009's scoped acceptance names four features (pace_gap, pace_evidence_depth, opp_pace_evidence_depth, is_playoff_game); `own_est`/`opp_est` are not among them, and their membership in "the exact receipted incumbent-equivalent possession path" is asserted by the SPEC ("incumbent-internal components, Stage 1B receipted path"), not established from any packet text. Additionally, whether `own_est − opp_est` coincides (up to scale) with the already-admitted `pace_gap` is undetermined; if it does, A02's treatment column is literally a K0-grantable incumbent feature and the A02/A15 credit accounting interacts. Required change: the preregistration must pin, **from receipts**, (a) that own_est/opp_est lie on the D009-standard-(a) path, and (b) the relationship of own−opp to pace_gap; A02 is inadmissible until (a) is shown.

### F-3 (Severity B) — The franchise-continuity (PHO/PHX) precondition is stated as universal but bound to only four arms

A11's note declares, correctly: "franchise continuity across the PHO/PHX rebrand must be receipted by the P23 merge guard for **ANY cross-season history feature**." The rejection_category_scan then binds the extension to A11, A12, A13 (plus A14 by source declaration). But the union contains many more cross-season history constructions: **A08, A09, A10** (TS lag operator is all-prior-games, cross-season by definition), **A16** (last-k window crosses season boundaries early in seasons), **A17, A19, A21, A22** (the CL lag operator L is explicitly cross-season — season-boundary discount λ = 0.5 exists precisely because prior-season games are included), and **A24** (cross-season prior game allowed by its own formula). If the receipt is needed for F10's arms, it is needed for all of these; if team_id continuity in the possessions artifact makes it vacuous, that reason must be named once and applied uniformly. As written, the synthesis states a principle and applies it to a third of its scope. Required change: extend the P23 receipt precondition to every arm whose lag window can span a season boundary, or record the named reason it is confined to F10/A14.

### F-4 (Severity B) — A14's declared remedy is concrete and preregisterable but its kill conditions are unfalsifiable in the realistic support case

A14's remedies (≥10-cluster active-set rule; retirement-unevaluated if no fold qualifies) are exactly the packet's S7 discipline, and I confirm the retention-over-rejection call is defensible: degeneracy is unmeasured, and rejecting on unmeasured support would itself violate "measure rather than assert". However: by the arm's own definition (`first season >= 2022`), expansion team-games can exist only in the *latest* seasons, so at most the last training fold(s) can activate — plausibly exactly one. The declared kill "sign instability across active folds" is **vacuously unfalsifiable with a single active fold**, and "kappa interval covers 0 in every active fold-set" degenerates to a one-fold test with no transport evidence. Required change: the preregistration must state in advance what inference a single-active-fold result licenses (my view: report-only, never promotion) and restate A14's kill conditions to be decidable in that case. A05, by contrast, I attack and clear: its §4 fallback is declared with the exact structural consequence stated (test-side treatment column identically zero ⇒ arm reduces to null by construction), the effective four-fold evidence base is recorded rather than hidden, the D3 objection travels with the arm, and its training-side support claim is left to the guard to measure. That is the packet's own prescribed remedy, correctly executed.

### F-5 (Severity B) — R5's rationale overstates the source: AI-H4's primary-target signal is not "ZERO by its own construction"

The rejection outcome is **correct** and I confirm the classification: AI-H4's source preregistered non-promotion ("gain over K0 triggers a pipeline investigation, not a candidate promotion"), and E5 records that trailing OT rate's only downstream benefit channel is arbitraging the OT bias — the named exclusion. Preserving the audit content as a diagnostic recommendation is the right disposal. But R5's detail claims the "hypothesized primary-target signal is ZERO by its own construction", which misstates the source: AI-H4 explicitly names "a genuine physiological fatigue-after-OT effect" as a confound — a legitimate primary-target pace mechanism that the source *declined to pose* because it would be unidentifiable from the normalization defect inside one arm. Nothing predictive was wrongly discarded from the union as proposed (no source posed the fatigue channel as a candidate), but the ledger as written could mislead a future wave into believing the channel was shown empty. Conversely I hunted for retained arms whose real value is mismatch exploitation and found none: A19/A20's value channel is the primary target itself (declared, P28-consistent); A26 is the nearest case — see F-7. Required change: amend R5's detail to record the fatigue-after-OT confound as unproposed-but-legitimate, not nonexistent.

### F-6 (Severity C) — Record accuracy in the rest-family merge (R2/A23/D7)

(a) D7 and A23 record AI-H2's cap 7 as a *frozen* source constant ("each source FROZE its own cap (4 and 7)"). AI-H2's text gives the cap as an example — "f a preregistered cap (e.g. min(rest, 7))" — i.e., a preregistration parameter, not a frozen value. Small, but this ledger exists precisely to be accurate about who froze what. (b) A23's merged formula reads "previous **scheduled/completed** same-season game", silently gluing AI-H2's "previous scheduled game" to OM-H4's "most recent strictly earlier completed contract game"; those can differ (postponements/reschedules) and the divergence is not listed in the choice set. (c) R2 carried OM-H4's opposite-sign kill into A23, but R1 carried no analogue of OM-H3's directional expectation (β3 > 0) into A25, whose kill is interval-covers-0 only — an asymmetry in merge practice worth recording.

### F-7 (Severity C) — OT-handling divergence across lagged pace constructions is a real cross-source disagreement not captured in D6

A12 rescales prior-game OT possessions to regulation-equivalent using that game's own lagged duration/overtime columns; A16 normalizes by regulation-equivalent duration; A26 deliberately uses **raw** per-game row counts, OT included, with the argument that the LOO correction contrast "differences OT noise symmetrically" — an assertion, not a measurement. This is a formulation disagreement of exactly the D6 kind (each source froze its own convention) and it leaves A26 carrying a weak residual lagged-OT channel. The risk is bounded — P28's ordering contract and the primary gate stand between it and any mismatch credit, and lagged OT is not same-game information — but the divergence should be named in the preserved-disagreements ledger so the preregistration cannot silently harmonize it either way.

### F-8 (Severity C) — A23's "satisfies even the strict D009 standard (b) trivially" overstates

The construction cell claims the rest contrast satisfies the timestamped-observation standard "trivially", while the same feature's citation correctly carries master_team's revision risk (game_date is joined from a retrospective bulk scrape). A schedule fact routed through a retrospective scrape is not a timestamped observation; the honest claim is "cutoff-valid by construction *conditional on the P23-receipted game_date join*", which the citation itself already implies. Wording fix only.

---

## 5. Verdict

**ACCEPT_WITH_REQUIRED_CHANGES.**

The deduplication is honest and arithmetically exact (verified against bytes: 31 = 26 + 5, no orphans, no double-counting, all four duplicate rejections true duplicates, no surviving duplicate found). No retained arm uses a lagged-licensed field unlagged; no same-game surrogate enters any prediction path; the S1–S9 discipline is genuinely engaged arm-by-arm, not recited. The A05 and A14 retentions follow the packet's own S7 clause, with A14 needing the single-fold inference statement (F-4). The R5 classification is correct in outcome with an overstated rationale (F-5).

Required changes before preregistration:
1. **(F-1, A)** A06: name a cutoff-valid source for scheduled season endpoints or redefine the phase/index denominator from past-only schedule facts; the current citation covers only the per-game date.
2. **(F-2, B)** A02: establish from receipts that own_est/opp_est are on the D009-standard-(a) path and pin the own−opp vs pace_gap relationship; inadmissible until shown.
3. **(F-3, B)** Extend the P23 franchise-continuity receipt precondition to every arm whose lag window can span a season boundary (A08–A10, A16, A17, A19, A21, A22, A24), or record the named reason confining it to F10/A14.
4. **(F-4, B)** A14: preregister what a single-active-fold result licenses and restate its kill conditions to be decidable in that case.
5. **(F-5, B)** Amend R5's detail: the fatigue-after-OT channel is unproposed-but-legitimate, not "zero by its own construction".
6. **(F-6/F-7/F-8, C)** Ledger corrections: AI-H2's cap was an example, not frozen; the scheduled-vs-completed prior-game definition in A23 is a choice, list it; add the OT-handling divergence (A12/A16/A26) to the preserved disagreements; soften A23's standard-(b) claim.

None of these changes alters the primary target, K0 structure, inference structure, candidate universe, or leakage status; F-1 is the item the coordinator should re-examine against the stop-condition rule if they read the cutoff-valid feature set more strictly than I do.
