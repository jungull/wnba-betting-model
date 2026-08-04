# Experiment task card

> Copy this file. Fill **every** field. A blank field is an unfrozen decision, and an unfrozen
> decision is how a formulation gets changed after seeing results.
> Governed by `RESEARCH_CONTRACT_V1`.

## Identity

| field | value |
|---|---|
| **Task ID** | |
| **Specification version** | e.g. `TURNOVER_DW2_WS3_v1` |
| **Research lane** | DISCOVERY (development folds only) / CONFIRMATION |
| **Branch** | |
| **Worktree** | one isolated worktree per parallel agent |
| **Base commit** | |

## Scientific question

**Question.**

**Basketball mechanism.** State the mechanism, not the feature list. Why would this be true about
basketball, independent of any model?

## Frozen inputs

| field | value |
|---|---|
| **Frozen inputs** | artifact ids + sha256 |
| **Prediction universe** | which rows a prediction is emitted for |
| **Candidate universe** | which player-games are eligible at all |
| **Target** | |
| **Denominator / exposure** | |
| **Chronological folds** | boundaries and ordering |

## Arms

| field | value |
|---|---|
| **Frozen arms** | exact feature lists; no "and variants" |
| **Matched K0** | the challenger's identical pipeline, zero substantive features |
| **Incumbent** | e.g. Arm D `turnover_rate_pooled_baseline_v1` — frozen, do not alter |

## Required preflight (Phase 0)

- [ ] hypothesis card frozen
- [ ] basketball mechanism stated
- [ ] candidate universe frozen
- [ ] target and denominator frozen
- [ ] **raw** feature frame audited
- [ ] transformation / imputation declared explicitly
- [ ] **transformed** fit frame audited
- [ ] **per-fold** rank, conditioning, variance, missingness checks pass
- [ ] challenger ↔ K0 strict Layer A parity
- [ ] incumbent differences disclosed with Layer B reason codes
- [ ] metrics, sign conventions, stop boundary frozen
- [ ] artifact / source / receipt lineage recorded

> Requirements 5–7 are **not fully tooled** (`GATE_INVOCATION_CONTRACT.md` §8a). State in the
> completion report whether dual-frame compliance is demonstrated or merely asserted.

## Evaluation

| field | value |
|---|---|
| **Primary metric** | |
| **Sign convention** | state explicitly which direction is better |
| **Uncertainty method** | e.g. 90% game-clustered CI |
| **Falsifier** | what result would refute the hypothesis — decided **before** running |

## Boundaries

| field | value |
|---|---|
| **Allowed files** | |
| **Prohibited files** | `feature_gate.py`, `comparison_gate.py`, `gate_invocation.py`, `arm_registry.jsonl`, canonical artifacts, Arm D |
| **Deliverables** | |
| **Stop boundary** | what must NOT be done without fresh authorization |

## Standing prohibitions

Do not promote a discovery arm; alter Arm D; alter canonical exposure or the canonical target;
begin a confirmation experiment; start another event channel; append to the registry (propose
records instead); or modify a shared gate.
