# PROGRAM FIREWALL — what each program may know about the others

*Written 2026-07-31 in response to John's review point 1: "a maximum source-date check proves
matrix isolation; it doesn't by itself prove that feature definitions or model choices were
uninfluenced by those outcomes." That is correct, and this document states the firewall
explicitly rather than leaving it implicit.*

## The three programs and their evaluation data

| program | development data | holdout |
|---|---|---|
| **Player-rate program** (the feature lab) | 2021–2024 | **2025 sealed** (first confirmation), **2026 declared locked final holdout** — claimable once |
| **Game/margin model** | 2021–2026 retrospective — **all of it, reclassified as development/audit 2026-07-31** | the **prospective live log** only (first record 2026-07-31T14:28:20Z) |
| **Betting/market layer** | all retrospective odds eras | the **prospective live log** only |

## The honest problem this document exists to record

Matrix isolation is verified: every feature-lab screen's quarantine audit reports a maximum
source date of 2024-09-19. **No player-rate screen has ever loaded a 2025 or 2026 row.**

But the same orchestrator has seen 2025 and 2026 *outcomes* through the game-model program —
channel re-validation, the oracle bracket, totals work, the pocket mining, the props study.
Feature definitions and modelling choices made after that point could in principle be
influenced by knowledge those seasons produced. Matrix isolation cannot rule that out.

### Specific cross-program knowledge held before the feature lab was designed

Recorded plainly so a reader can judge the risk rather than take a reassurance:

1. The structural 3-point channel edge was **absent in 2026** (chanreval flag, 2026-07-30).
2. The model's **2026 totals run ~5 points under actual** (totals groundwork).
3. The market gap is **smaller in 2026** than 2024/2025 (bookie-gap table).
4. **2026 scoring is elevated** relative to the training era (totals head diagnosis).
5. Rest advantage looked profitable in the **betting** pockets across eras.
6. Player-level projections lose to player lines in **all seasons including 2025–26** (props).

The feature catalog was written on 2026-07-31, **after** items 1–5 were known. A reader should
assume the catalog's composition — which families were included, which were prioritised — was
plausibly influenced by them, even though no 2025–26 row entered any screening matrix.

### What that does and does not compromise

- It does **not** compromise the *measurements*: every effect size was computed on 2021–2024
  data with verified quarantine.
- It **does** weaken 2025 as a pristine confirmation for the player-rate program. 2025 remains
  the best available confirmation and materially stronger than re-reading development data,
  but it is **confirmation under a partially-informed prior**, not a virgin test.
- The **only** evaluation surface in this project untouched by any such influence is the
  **prospective live log**, because its games had not been played when the model was frozen.
  That is why the live log — not any retrospective season — is the project's ultimate arbiter.

## Permitted cross-program information (the rule going forward)

**Permitted** — may flow freely between programs:

- Data-engineering facts: schema quirks, coverage gaps, era breaks, identity/dtype hazards,
  collection failures, capture cadence.
- Methodological findings: leakage classes, contaminated artifacts, permutation defects,
  power/detection limits, multiplicity procedures.
- Infrastructure: harness code, audit patterns, manifest conventions.

**Prohibited** — may not influence player-rate program decisions:

- Any 2025 or 2026 *outcome* — effect sizes, error rates, which features or channels worked,
  which seasons behaved unusually — obtained through the game-model or betting programs.
- Selecting, deselecting, prioritising or tuning any player-rate feature, encoding, or
  parameter with reference to such an outcome.

**Enforcement, given that a single orchestrator runs both programs:**

1. Every player-rate decision must be **justified in writing citing only player-rate evidence
   from 2021–2024**. A decision that cannot be so justified is not made.
2. The catalog and every screen registration are **frozen before results are seen**; changes
   require a new registration stating what prompted them.
3. Where cross-program knowledge plausibly touched a decision, it is **declared in the
   registration's `extra` field** (as the cross-season rescue's 2024 provenance now is).
4. Subagents building player-rate screens are given **no game-model results** in their briefs.
5. **The live log is the tiebreaker.** Any conclusion that depends on the 2025 confirmation
   being pristine is held as provisional until prospective evidence agrees.

## Standing acknowledgment

This firewall reduces contamination of judgment; it cannot eliminate it while one operator
runs every program. The honest posture is therefore: **retrospective seasons develop, the
prospective log confirms.** Where those two disagree, the prospective log wins.
