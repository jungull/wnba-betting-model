# S30 red-team disposition map — draft v1 → v2 (2026-08-07)

Two independent reviews of `CYCLE2_TARGET_CONTRACT_DRAFT.md` v1. Every Severity A/B finding
and its disposition in v2. Disagreements preserved; nothing averaged away.

## Reviewer 2 — leakage/exploitability (verdict on v1: PASS_WITH_FINDINGS, 3 A + 4 B)

| # | sev | finding (compressed) | disposition in v2 |
|---|---|---|---|
| 1 | A | E1/E2/E3 Holm family undefined; three correlated shots per arm | §4: test element = (arm, estimand); all of an arm's elements sit INSIDE its single mechanism family; stricter-governs frozen (labeled a strengthening); kills uncorrected carried; cross-estimand claims need corrected pass on each estimand; multi-survivor rule + program-alpha declaration restated at S35 |
| 2 | A | weak-K0 exploit: intercept-only null + public-floor feature = trivial pass | §4 null-strength floor: every K0_MATCHED carries the composite's frozen ingredients as receipted null-granted features (K5/A07 pattern); genuine-inability path adjudicated at S33/S34 and labeled "FEATURE VALUE OVER OWN NULL ONLY — BELOW-FLOOR NULL" with non-gating floor-recomputation report; "genuinely extends" retired for a decidable pipeline_id + ingredient-hash criterion with named adjudicator |
| 3 | A | per-arm coverage predicates permit easy-subset selection | §2: predicates information-based & cutoff-valid only; ≥90%-of-clusters floor (lower requires S33/S34 adjudication); mandatory non-gating all-covered-games sensitivity row with declared fallback; dropped-count + dropped-vs-kept naive-floor difficulty reported |
| 4 | B | P2B uncited; market fields could enter via §8 promotion or coverage predicates | §8: market-odds fields inadmissible as features and coverage inputs; promotion channel excludes vendor-asserted retrospective timestamps; future admission needs P2B's open objection settled at USER level; live-stream consumption filters snapshot < commence (P2B F9) |
| 5 | B | OT prohibition not audit-checkable | §1: P22 invocation per feature column; frozen feature-lineage table; current-game-deletion invariance receipt (byte-identity of the feature matrix) |
| 6 | B | E3 estimation objective not a matched dimension | §4: estimation_objective/response family added as an explicitly matched dimension with the P35 deviation-voids-the-arm clause; p-clipping declared arm+K0; calibration table a receipted sealed output |
| 7 | B | observed-bar contamination unnamed/unbounded | §4: floors referenced by artifact+hash, values not printed in the contract; authors assumed contaminated; floor/bar values banned from kills/stopping/coverage/grids (S34 checks); ideation packets exclude D045 numeric rows; permanent honest-labeling note in adjudication |
| 8 | C | 13-prose vs 17-machine dimensions; secondary side-channel; A07 strength noted | §4 cites the 17-dimension machine mapping; §5 seals secondaries with primaries, opened only at S40 |

## Reviewer 1 — contract consistency (verdict on v1: PASS_WITH_FINDINGS, 0 A + 6 B + 4 C)

| # | sev | finding (compressed) | disposition in v2 |
|---|---|---|---|
| B1 | B | D049 cited in present tense while absent from the ledger at review time | D049 was recorded 2026-08-07 (after v1 authorship, before any freeze — the reviewer's read predated the append; both facts recorded). Header now states the timing explicitly; freeze precondition satisfied and re-checkable |
| B2 | B | "game-date-clustered … adopted unchanged" misdescribes cycle 1 (game-clustered) | §3 corrected to game-clustered; the board's date-clustered CI convention explicitly distinguished as context-only |
| B3 | B | P26 K0 schema pins the possession target; cannot represent E1/E2/E3; undisclosed | §4 disclosure + new graph node `S32B_K0_CONTRACT` (S-lane analog of P26) required frozen before S33 completes; S33 dependency updated |
| B4 | B | required-areas-in-ideation-packets conflicts with D047 p3 isolation | §7 restructured: ideation fully isolated (contract-only packets); user-directed families enter at S32 as DIRECTED CANDIDATES with provenance labels, never counted as independent sources |
| B5 | B | "off_A×def_B / off_B×def_A" misquotes D047's "and" as a ratio-reading slash | §7 quotes D047 exactly ("and"); no functional form proposed |
| B6 | B | F13 §3.5/§7(f) covariance obligation dropped; §4.3 quantile-grid/covariance K0 items condensed away | §5 restores the covariance obligation as first-class receipted quantities (bottomup_3pt_channel_v1 precedent) and the matched quantile-grid + covariance-matching K0 items |
| C1 | C | D036 p6 miscited for the matched-universe rule | §2 cites D036 p4 / D038 / D045 p3 |
| C2 | C | injury-store start date wrong (2026-08-07 vs capture history) | §8 corrected: witnessed live store 2026-08-06/07; earlier daily captures 07-30..08-04 named; conclusion unchanged |
| C3 | C | "mirrors cycle 1" hides two deltas (stricter-governs; kills-uncorrected omitted) | §4 labels stricter-governs a frozen strengthening and carries kills-uncorrected explicitly |
| C4 | C | F12 identifiability obstacle unmentioned | §7 identifiability acknowledgment: every directed-candidate card registers its identification constraint |

## Round 2 — reviewer 2 re-verification of v2 (all v1 findings CURED; 4 new B on v2's own surfaces) → v3

| # | sev | finding (compressed) | disposition in v3 |
|---|---|---|---|
| N1 | B | cannot-host hatch undecidable; below-floor pass still promotes and launders into pass counts | §4: blockage must be demonstrated mechanically and REPRODUCED by an S34 reviewer; BELOW-FLOOR-NULL label inseparable from every citation; never in unqualified pass tallies; S40 routes any such would-be promotion to the S42 USER gate |
| N2 | B | S31 graph read scope included market_program (floors readable); cycle-1 forbidden-file receipt dropped | S31 allowed_read_paths narrowed to its own packet dir; manifest must record per-source packet content hash + forbidden-file list (P31 receipt restored) |
| N3 | B | 90% pooled floor permits concentrated single-fold trimming | §2: additional per-fold floor (≥80% of every fold's test clusters); only alternative is cycle-1-style symmetric whole-fold structural deactivation with a numeric pre-registered trigger |
| N4 | B | null-granted ingredients pinned by name, not bytes; weak reimplementation nominally complies | §4 + S32B criteria: ingredients bound to bytes (score_baseline_rows.parquet column-level digests, or frozen builder source hash + resolved parameters); name-matching never satisfies |
| N5 | C | no dropped-candidate log at synthesis | S32 criteria: REPORT.md enumerates every non-retained ideation candidate with reason |
| N6 | C | multi-survivor rule undefined across metrics | §4: multi-survivor comparison operates within-estimand only; no cross-metric ordering defined or permitted |
| N7 | C | DIRECTED channel authored by contaminated coordinator (inherent) | S34 criteria: every DIRECTED card checked against D047 text for scope creep + floor/bar reference ban checked |

**Verified-clean list (reviewer 1):** F13 sd figures; D045 floor values and method name; universe
counts; 5/37 inventory; thirteen-dimension prose list; fold names; B=10,000/2,000; gate clauses
vs `primary_gate_applied_verbatim`; P42 §6 lesson; estimand feasibility from owned data
(master_team.parquet pts/opp_pts; zero settled ties). These stand as the draft's verified base.
