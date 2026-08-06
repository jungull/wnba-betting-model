# F13_SCORE_MARGIN_TOTAL_DISTRIBUTIONS — REPORT

DIAGNOSTIC AND TARGET-CONTRACT DRAFT ONLY. Discovery work being unblocked is NOT authorisation to fit. Fitting requires a target contract, a matched K0, cutoff-valid evidence, a preregistration and an independent gate review.

Companion deliverable: `TARGET_CONTRACT_DRAFT.md` in this directory. That file is the mandate; this
one records how it was arrived at.

---

## 1. Headline

**The estimand for score, margin and total distributions is NOT_DERIVABLE_FROM_DOCUMENTATION.**

The player program documents this track's construction order, its accounting constraints, its
correlation requirement and its binding negative precedent. It states no target statistic, no unit
and no denominator. I did not supply one.

A complete, registered estimand *does* exist on the **team** thread — `dist_margin_cover_v1`,
`primary_metric: "margin_crps"` — and the draft declines to adopt it, for four stated reasons
(wrong thread; wrong universe, 673 games vs 2,982 rows / 1,491 clusters; its own primary metric is
disputed between its design document and the registry bytes; it carries none of the player-side
aggregation obligation). Adopting it would have manufactured a commitment the player program never
made, which is the failure mode this node exists to avoid.

---

## 2. What I measured, and with what

Every number below was produced during this node. No figure is carried from prose.

| claim | value | how measured |
|---|---|---|
| distinct games in the possession artifact | 1,495 | `pandas.read_parquet('possessions_v2/possessions_raw_v2.parquet')`, `game_id.nunique()`; 238,563 rows |
| rows in the team possession prior | 2,990 × 11 | `read_parquet('projected_exposure_v1/team_possession_prior_v1.parquet').shape` |
| contracted universe | 2,982 team-game rows / 1,491 game clusters | `data_lane/D10_FIELD_AVAILABILITY_LEDGER/FINDINGS.json → row_universe` |
| realized home score | mean 83.443, sd 11.432, range 49–125 | last possession per `game_id` ordered by `canonical_seq`; `home_pts_before + points_scored` where `is_home_offense` |
| realized away score | mean 81.764, sd 11.676, range 47–123 | same, away side |
| realized margin | mean 1.680, sd 14.014, range −53…48 | derived home − away |
| realized total | mean 165.207, sd 18.376, range 111–247 | derived home + away |
| ties at end of game | 0 | `(margin == 0).sum()` |
| games containing an overtime possession | 66 of 1,495 | `groupby('game_id').is_overtime.max().sum()` |
| regulation-only sd(margin) / sd(total) / mean(total) | 13.952 / 17.650 / 164.248 | same derivation restricted to `~is_overtime` |
| D10 field verdicts | CUTOFF_VALID 5, CUTOFF_UNPROVEN 37, CUTOFF_INVALID 3, ABSENT 7 (52 fields) | `FINDINGS.json → verdict_counts`, cross-checked against the per-field list |
| cutoff policy split | 2,168 date-only, 814 exact-tip, over 1,491 joined games | `FINDINGS.json → cutoff_definition` |
| prospective log rows | 8 | line count of `forecasts/forecast_log.jsonl` |
| distributional primitives present | `pinball_loss` 63, `mean_pinball_loss` 87, `crps_ensemble` 92, `mean_crps` 116, `brier_score` 136, `log_loss` 142, `reliability_table` 149, `interval_coverage` 195 | `grep -n '^def ' evalharness/metrics.py` |
| files scanned in the negative-proof search | 2,345 | recursive walk over `.md/.json/.py/.jsonl/.txt`, excluding `.git`, `__pycache__`, `SEALED_RESULTS` |

**The overtime split is the consequential measurement.** Full-game and regulation-only sd(total)
differ by 0.73 points (18.376 vs 17.650) and sd(margin) by 0.062. Because the program's primary
target is `REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS` and current-game realized overtime is
prohibited from the prediction path, any future score/margin/total distributional estimand must
choose between the full-game object (what is bettable) and the regulation-equivalent object (what
the possession target is). **No document resolves that fork.** It is a first-order component of the
missing estimand, and I raised it rather than resolving it — resolving it would be changing the
target.

---

## 3. Proving the negative

The claim "no estimand is documented" is only a finding if the search that produced it works. I ran
a whole-repository scan (2,345 files) for any line associating a distributional scoring rule
(CRPS, pinball, log score, interval coverage, predictive distribution, distribution over) with
margin, total, final score or game score, within 140 characters in either direction.

* **Positive control:** the same pass counted 4 lines containing `"Stage E"`, a string I had already
  read at `PLAYER_RESEARCH_COVERAGE_MATRIX.md:73`. The scanner reads and matches the bytes in
  question. This matters here specifically because this program has produced one manufactured
  negative before, from a pandas StringDtype comparison that silently failed on the exact bytes
  being searched — so the search was done on raw file text, not through pandas.
* **Result:** 13 hits. Every one is on the **team** thread or is a metric menu:
  `ROADMAP.md:138` (menu), `experiments/registry.jsonl:18` (`dist_margin_cover_v1`),
  `dist_margin_cover.py`, `experiments/dist_margin_cover/REPORT.md`,
  `leaderboards/PROBABILISTIC.md:22`, `project_docs/ASSUMPTION_AUDIT_2026-07-30.md:113`, and one
  player-program line — `stage2a/V2_HYPOTHESES_basketball.md:117` — which is about the *possession*
  predictive distribution's spread, not about score, margin or total.
* **Zero hits** inside the player program associating a scoring rule with score, margin or total.

That is the negative, and it is proven rather than assumed.

---

## 4. What I could not establish

1. **Whether the graded object is full-game or regulation-equivalent** (§2). Not documented either way.
2. **Whether the denominator is the team-game row or the game cluster**, and which universe —
   2,982/1,491 or 2,990/1,495. D10 explicitly reports the 4-game / 8-row difference as the possession
   producer's own exclusion, `"reported, not reconciled here"`. I did not reconcile it either; it is
   outside this node's write scope and resolving it would touch the candidate universe.
3. **Whether any predictor a score/margin/total model would want is cutoff-valid.** The D10 ledger
   gives verdicts, and its CUTOFF_VALID verdicts are themselves *assertions* — PROGRAM_STATE carries
   `cutoff_validity_asserted` at severity B precisely because cutoff validity is a property of
   upstream construction and cannot be verified from bytes. I inventoried the verdicts; I could not
   verify them.
4. **What a matched distributional K0 would look like in code.** There is none, and no code that
   could emit one (`"No simulation code exists"`, capability matrix:291). §4.3 of the draft states
   what such a control would have to match; it is a requirement, not a design.
5. **The original construction provenance of `team_possession_prior_v1.parquet`.** PROGRAM_STATE
   records it as `legacy_receipts_only`.

---

## 5. Contradictions found

**C-1.** `project_docs/ASSUMPTION_AUDIT_2026-07-30.md:537–539` designs E1 with
`"Preregister: primary = cover-Brier vs the line-implied-probability benchmark"`; the record that
landed the same day, `experiments/registry.jsonl:18`, carries `primary_metric: "margin_crps"`.
Frozen bytes govern, so `margin_crps` is what was registered — but design and bytes disagree about
the primary metric of the one distributional experiment on the ledger. Reported, not reconciled.

**C-2.** `ASSUMPTION_AUDIT_2026-07-30.md:112–114` states that no margin/total distribution and no
CRPS `"exists anywhere on the ledger"`. `dist_margin_cover_v1` registered at
`2026-07-30T21:23:43Z`. The audit sentence appears to predate the registration rather than
contradict it; both are cited so the earlier sentence does not mislead a later reader.

**C-3.** Row-universe mismatch, 2,982/1,491 vs 2,990/1,495 (§4.2). Documented as unreconciled by D10.

**C-4.** Fold structure mismatch: D10 records that `prediction_contract_v5/player_game_enriched.parquet`
carries a `fold_id` of the form `season:YYYY` with six values and no train/test split, which is not
the same object as the five expanding-window chronological folds used for the possession target.

---

## 6. Disclosure — no-performance-peeking

While proving the negative in §3 I ran a full-text scan whose hit list included two outcome-bearing
lines (`leaderboards/PROBABILISTIC.md:22` and `experiments/dist_margin_cover/REPORT.md`). I then ran
a field-level extraction against `experiments/registry.jsonl` with an outcome-field suppressor
intended to print only definitional fields; the suppressor did not catch several result-bearing key
names and leaked outcome fields of the team-thread record `dist_margin_cover_v1`.

I am reporting this rather than omitting it.

* The exposure is to a **team-thread** experiment. It is not a player-program challenger.
* `experiments/player_program/stage2b/SEALED_RESULTS/` was never opened at any point in this node.
* **No figure from any of those sources appears in, or is relied on by, either deliverable.**
  `TARGET_CONTRACT_DRAFT.md` §3.4 cites only definitional fields of that record — experiment id,
  schema, registration timestamp, decision time, primary-metric *name*, incumbent *id*, universe
  description, and the preregistered thresholds — and the conclusion drawn there is *do not adopt
  this estimand*, which rests on thread, universe and contradiction C-1, none of which is an outcome.

A verifier should treat this as a process defect in my extraction script, and should confirm
independently that no leaked figure propagated into the draft.

---

## 7. Stop conditions

None tripped. Nothing here changes the primary target, the K0 structure, the inference structure,
the candidate universe, the cutoff-valid feature set or the leakage status.

Two items are **raised and deliberately left unresolved** because resolving them would trip a stop
condition: the full-game versus regulation-equivalent fork (§2) touches the primary target, and the
1,491-versus-1,495 cluster question (§4.2, §5 C-3) touches the candidate universe. Both belong to
whoever issues the estimand as a versioned specification under `RESEARCH_CONTRACT_V1`.

---

## 8. Files read

Player program: `orchestration/reports/ROADMAP_EXTRACTION.json`,
`orchestration/prompts/F13_SCORE_MARGIN_TOTAL_DISTRIBUTIONS.md`, `PLAYER_MODEL_CAPABILITY_MATRIX.md`,
`PROJECT_UPDATE_2026-08-04.md`, `PROGRAM_STATE.json`, `register_program_roadmap.py`,
`comparison_gate.py`, `data_lane/D10_FIELD_AVAILABILITY_LEDGER/FINDINGS.json`,
`possessions_v2/possessions_raw_v2.parquet`, `projected_exposure_v1/team_possession_prior_v1.parquet`.

Repository root (all previously cited by G04, or reached through a G04 citation):
`PLAYER_RESEARCH_COVERAGE_MATRIX.md`, `ROADMAP.md`, `project_docs/ASSUMPTION_AUDIT_2026-07-30.md`,
`experiments/registry.jsonl`, `evalharness/metrics.py`, `forecasts/forecast_log.jsonl`.

Not read: `experiments/player_program/stage2b/SEALED_RESULTS/` (forbidden input).

Nothing was written outside
`experiments/player_program/future_research/F13_SCORE_MARGIN_TOTAL_DISTRIBUTIONS/`. No git command
that mutates state was run.
