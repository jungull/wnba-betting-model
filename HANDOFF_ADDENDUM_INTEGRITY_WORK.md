# Handoff addendum — program-integrity work A–D is NOT done

Companion to `HANDOFF_TURNOVER_DISCOVERY.md` (commit `49b8faa`), which was written by a parallel
session and **predates** the events below. Where the two disagree about workstreams A–D, this file
is correct.

## State verified at the time of writing

Live lineage: worktree `.claude/worktrees/player-model-program`, branch `player-model-program`,
HEAD `49b8faa`. **Not the repo root.**

`experiments/player_program/feature_gate.py` is intact and authoritative at commits `55f4500`
(rank / conditioning) and `42af2cd` (informative missingness). Verified: 12 blocking kinds, both
`rank_deficient` and `missingness_encodes_outcome` present. **Do not modify it for those two gaps
again** — both are closed and were verified against the exact WS1 cases.

The duplicate background task (`task_ab6a6675`, "Close two feature_gate.py blind spots") could not
be cancelled from the coordinating session — it ran in a separate local session outside the task
registry. It appears to have produced `49b8faa`, a handoff document only. **It did not touch
`feature_gate.py`.** There is nothing from it to review, merge or reject.

## What failed

Four integrity workstreams were launched as background agents in isolated worktrees. The Claude
Code process exited while they were running and **their in-process state was lost**.

Verified: all four worktrees sit at `42af2cd` with **zero commits**. Two carry uncommitted scratch
(3 modified files each) that has not been reviewed and should not be assumed useful.

| workstream | agent worktree | commits | dirty |
|---|---|---|---|
| A — baseline parity | `agent-a8b2a81b3bb3e2873` | none | 0 |
| B — receipt integrity | `agent-a23337c4426be67ff` | none | 3 |
| C — ledger integration | `agent-ab10010b33ac8cf6d` | none | 0 |
| D — supersession records | `agent-abf96c131866cfbf4` | none | 3 |

**All four must be redone from scratch.** Nothing landed.

## What the next session must do

Re-run A–D. Full specifications are in the operator instruction; the essentials:

**A — baseline-parity contract.** New file `experiments/player_program/comparison_gate.py`.
**Do not put this in `feature_gate.py`.** It detects when a challenger receives fitting flexibility
its baseline does not. Fails closed unless a manifest establishes parity across sixteen dimensions
(prediction universe, training rows, evaluation rows, folds, offset, intercept treatment, intercept
penalisation, calibration freedom, clipping, link, companion components, fallback rules, candidate
universe, preprocessing, missing-value handling, post-processing). Requires a matched featureless
`K0` control per challenger. Reports three distinct quantities: challenger vs frozen incumbent,
challenger vs K0, K0 vs frozen incumbent. Regression test from the real WS2 case: K0 operational
team MAE ≈ **2.96419**, frozen Arm D ≈ **2.96745**, unmatched intercept ≈ **0.0033**. Plus: equal
pipelines pass; challenger-only intercept blocks; different clipping blocks; different evaluation
rows blocks; different companion blocks; different offset blocks; adjudicated difference passes
while staying visible. Invokable per fold and on the consolidated manifest.

**B — receipt integrity.** The turnover target artifact was rebuilt by the source-aware
exact-deduplication change and its validation receipt was never regenerated, so artifact and
receipt have drifted. Revalidate the **existing corrected artifact** through
`validate_turnover_targets.py`. **Do not alter the target to make the receipt match.** Confirm:
canonical events **589,123**; turnover events **42,082**; player-attributed **39,278**; team-game
external reconciliation **2,990 / 2,990** exact. Then add a permanent check that fails on hash
divergence, count divergence, producer/contract version divergence, or a validated artifact rebuilt
without a refreshed receipt. Sweep `projected_exposure_v1`, `event_contract_v1`,
`turnover_targets_v1`.

**C — central ledger integration.** Single writer merges the discovery patches into
`experiments/player_program/discovery_wave_1/HYPOTHESIS_LEDGER.json`. Agent results live in
**separate worktrees**: ws1 `agent-a062ec7d27d10b55b` @`5313ebd` (supersedes `3726991`); ws2
`agent-a366d924a9b4dfcd5` @`863a900` (prereg `8116b7d`); ws3 `agent-a96f23f70cffc45d0` @`1e3509f`;
ws4 `agent-a578166bb62b091a5` @`1b634fb` (prereg `a6d5cd4`); ws5 `agent-ab8223114ea98f146`
@`6d9e3f2` (freeze `059db0d`); ws6 `agent-abba0a0dbf84578f1` @`5ef1f25`; ws7
`agent-ab4ac90b1f887b5b7` @`e858e96` (prereg `58b3a91`); ws8 `agent-a5694dab4e5ccdb3d` @`c1d2637`.
The eight status blocks must be preserved **verbatim** from the operator instruction — do not
soften or embellish.

**D — supersession records.** No commit rewriting. Record: E and I invalid (algebraic
non-identifiability, rank 4 of 5); F operational invalid (outcome-encoded missingness, 8,278 null /
27,351 non-null, zero off-diagonal); G player-level improvement invalid as published evidence (the
leaking feature is worth **0.0218** deviance versus a reported gain of **0.00137**); H unaffected by
the null-mask defect but its challenger-vs-D conclusion contaminated by unmatched intercept
treatment. WS5 and WS6 clean results stay separate and must **not** be backfilled into the P2
registration. Also add `GATE_INVOCATION_CONTRACT.md`: feature audits run per chronological training
fold **and** on the final assembled design; a pooled audit cannot establish fold-level
identifiability. Cite the real case — ws3's 2022 stage-2 fold had std 7.8e-9 while pooled variance
looked healthy, saturating a softmax to exact 0/1 shares.

Registry appends stay with the coordinator. Agents write **proposed** records only; nothing appends
to `arm_registry.jsonl` concurrently.

## Substantive conclusion to preserve

Ranked: (1) team-possession-total projection is the clearest remaining team-aggregate opportunity;
(2) a preregistered gated role-expansion challenger is the strongest narrow turnover hypothesis;
(3) clean involvement proxies may have small player-allocation value; (4) broader turnover-rate
feature expansion should yield priority.

Required wording — **do not** call turnover research exhausted:

> Under the tested total-turnover formulations, the conditional rate model is near its practical
> team-aggregate ceiling. Remaining turnover value is more likely to come from improved
> team-possession projection, a narrowly gated role-expansion effect, or player-level applications
> than from additional broad pooled rate features.

## Unclosed methodological gaps

1. **Baseline parity** — workstream A. No feature-matrix check can catch it; it is a property of
   the comparison, not the design.
2. **Gate invocation timing** — workstream D. The gate has no opinion about *when* it is called.
3. **Nonlinear dependency** — the gate now catches linear rank deficiency only. A feature
   deterministic in others through a nonlinear map still passes.

## Stop boundary (unchanged)

Do not begin a new confirmation experiment, promote a discovery arm, alter Arm D, alter canonical
exposure, begin another event channel, or merge the duplicate gate task without review.
