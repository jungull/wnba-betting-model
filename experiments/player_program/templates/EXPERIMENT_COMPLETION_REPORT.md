# Experiment completion report

> Copy this file. Fill **every** field. Governed by `RESEARCH_CONTRACT_V1`.
> Use the status vocabulary exactly. `LANDED` is not `VERIFIED`.

## Identity and status

| field | value |
|---|---|
| **Task ID** | |
| **Specification version** | including any `_v2` amendment actually worked under |
| **Status** | `REQUESTED` / `RUNNING` / `LANDED` / `VERIFIED` / `COMMITTED` / `SCIENTIFICALLY_ACCEPTED` / `SUPERSEDED` / `INVALID` |
| **Base commit** | |
| **Result commit** | |
| **Working-tree state** | clean / N modified — list them |

## Exact completed scope

What was **actually** done. Separately: what was in the specification and **not** done, and why.
If part of the work was produced under an earlier specification version and not revisited, say so
here.

## Preflight receipt table

| requirement | status | receipt path / digest |
|---|---|---|
| hypothesis card frozen | | |
| basketball mechanism stated | | |
| candidate universe frozen | | |
| target and denominator frozen | | |
| **raw** feature frame audited | | |
| transformation / imputation declared | | |
| **transformed** fit frame audited | | |
| per-fold rank / conditioning / variance / missingness | | |
| challenger ↔ K0 Layer A parity | | |
| incumbent differences disclosed (Layer B codes) | | |
| metrics / sign / stop boundary frozen | | |
| lineage recorded | | |

**Dual-frame compliance:** demonstrated by tooling / **asserted by author** (delete one). If
asserted, say what was not mechanically verified.

## Evaluation universe

| count | value |
|---|---|
| candidate rows | |
| training rows | |
| evaluation rows | |
| team-games | |
| folds | |
| appearers / non-appearers | |

## Results

One standardized table. Sign convention stated explicitly; positive = ______.

| arm | metric | value | uncertainty | vs K0 | vs incumbent |
|---|---|---|---|---|---|
| | | | | | |

### Challenger versus K0 — PRIMARY feature-value test

Value, uncertainty, and whether the features added anything beyond matched flexibility.

### Challenger versus incumbent — operational relevance only

Value, uncertainty, and the free-flexibility gain (K0 vs incumbent) that must be subtracted before
any attribution.

> A challenger that beats the incumbent while failing against K0 **has not demonstrated feature
> value**. Say so in those words if it applies.

## Direct findings versus inference

| # | claim | direct measurement or inference? | evidence path |
|---|---|---|---|

Anything not directly measured is an inference and must be labelled as one.

## Defects and deviations

| # | defect | severity A/B/C | affected outputs | action |
|---|---|---|---|---|

Include deviations from the frozen specification, and any amendment worked under.

## Classifications

| axis | value | rationale |
|---|---|---|
| **Feature-design integrity** | `posthoc_current_gate_pass` / `manual_equivalent_checks_documented` / `corrected_after_gate_defect` / `not_applicable_no_feature_fit` / `fails_current_gate` / `not_reconstructable` | |
| **Decision validity** | `valid_as_published` / `valid_only_after_corrected_rerun` / `diagnostic_only` / `superseded` / `invalid` / `not_reconstructable` | |

The axes are independent. A gate pass does not establish decision validity.

## Scientific disposition

Falsified / null under this formulation / partial / diagnostic / hypothesis-generating —
and what specifically remains **formulation-dependent** rather than disproven.

**May this justify a future frozen challenger?** Yes / No, with reasoning.

## Recommended next action

Exactly **one**.

## Stop confirmation

- [ ] I stopped at the boundary in the task card.
- [ ] I did not promote any arm, alter Arm D, alter canonical artifacts, append to the registry,
      modify a shared gate, or begin another experiment.

Not begun: ______
