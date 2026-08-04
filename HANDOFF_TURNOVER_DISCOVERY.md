# Handoff — WNBA player program, turnover channel and discovery wave 1

Written at the end of a long session. Read this before touching anything.

## 0. Where the work lives

* Branch: `player-model-program`
* **Live lineage is a worktree**, not the repo root:
  `C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program`
* The repo root is on a different branch and is many versions behind. Do not work there.
* Registrations: `experiments/player_program/arm_registry.jsonl` (append-only). The shared team
  registry `experiments/registry.jsonl` is **not** written by this program.

## 1. Commit spine (this session)

| commit | what |
|---|---|
| `9806cb5` | `projected_player_possessions_v1` registered, built, validated 34/34 |
| `471d7f9` | receipt corrections + availability/plausibility split (35/35); P3 experiment registered |
| `e1ea9ee` | P3 downstream comparison executed |
| `e4f244c` | P3 club and player-exposure concentration reporting |
| `7474f64` | P3 frozen complete; `PLAYER_MODEL_CAPABILITY_MATRIX.md` |
| `dac03ee` | `canonical_player_events_v1` registered, built, validated 18/18 |
| `667f49e` | turnover P0 targets, validated 15/15 |
| `5ba303b` | P0 corrections + P1 pooled baselines |
| `7cbfa9d` | **P1 operational-universe correction** (prior operational track invalid) |
| `2c999c3` | P2 role/context wave; arms E and I invalid |
| `eb1103c` | discovery wave 1: hypothesis ledger + `feature_gate.py` |
| `55f4500` | feature gate: rank / conditioning check |
| `42af2cd` | feature gate: informative-missingness check |

## 2. What is FROZEN and VALID

* **`projected_player_possessions/1`** — exposure bridge, 35/35 validation. 35,629 Tier A
  obligations. Do not alter.
* **`canonical_player_events/1`** — 589,123 events, 1,495 games, 18/18. Two disjoint source
  schemas normalised. Boundary is **two-dimensional** (all 2021-2025 playoffs are CDN, plus a clean
  2025-06-29/07-03 regular-season split) — not "a mid-2025 changeover".
* **`player_turnover_targets/1`** — 15/15. 42,082 turnover events, 39,278 player-attributed,
  2,990/2,990 external team reconciliation exact.
* **Arm D** (`turnover_rate_pooled_baseline_v1`, EWMA-shrunk, K=200, alpha=0.10) — P1 development
  champion. Operational team MAE **2.96745**, intrinsic **2.89602**. Not production-ready, not
  universally superior. **Do not alter or retune.**
* **P3 downstream** — all five arms fail. The frozen P3 coefficients did not demonstrate
  incremental team-forecast value under the registered cutoff-valid exposure system.

## 3. What is INVALID or SUPERSEDED — do not cite

* P1 operational results computed over **realised participants** — invalid, superseded by `7cbfa9d`.
* P2 arms **E and I** — algebraic non-identifiability.
* P2 arm **F** operational — outcome-encoded missingness.
* P2 arm **G** player-level gain — leaking feature effect (0.0218 deviance) exceeds the reported
  gain (0.00137).
* P2 arm **H** — unaffected by the null-mask defect but contaminated by unmatched intercept.
* Withdrawn claim: "projected exposure is the dominant error source" — inflated by my own bug.
  Correct statement is in §6.

## 4. FOUR DEFECTS I INTRODUCED — the most important thing to internalise

1. **Operational-universe defect.** P1's operational track summed only over players present in the
   realised target artifact (`R.merge(PX, how="left")` starting FROM realised rows). Retrospective
   rotation membership. Fixed at `7cbfa9d`; the corrected universe is all 35,629 candidates
   including 8,278 non-appearers with realised target 0.
2. **Free-intercept confound.** Fitted challengers carried an unpenalised intercept the unfitted
   incumbent lacked, worth **~+0.0033** operational team MAE — the same size as the effects being
   hunted. An intercept-only control **K0 = 2.96419** was reproduced independently by three
   workstreams. Fix in flight as Workstream A.
3. **Outcome-encoded missingness.** `trailing_minutes_share`, `trailing_rotation_rank`,
   `role_change`, `offensive_involvement_proxy` in `turnover_p2_v1` were built from the realised box
   score and left-merged onto candidates: **8,278 null / 27,351 non-null, zero off-diagonal against
   `did_appear`**. Any `fillna` launders the outcome into the design. `displaced_involvement` is
   **not** affected (fully populated). Gate check added at `42af2cd`.
4. **Receipt drift.** The turnover target artifact was rebuilt by the dedup change without
   regenerating its validation receipt. Being repaired as Workstream B.

**Pattern worth carrying forward:** every one of these was caught downstream by a subagent, not by
me at registration. Prefit validation in this program has been consistently weaker than the
analyses it exists to protect.

## 5. Discovery wave 1 — eight workstreams, zero challengers to Arm D

Results live in separate agent worktrees under `.claude/worktrees/agent-*`.

| WS | branch @ commit | verdict |
|---|---|---|
| 1 repaired role | `a062ec7d27d10b55b` @ `5313ebd` (supersedes `3726991`) | falsifies; original run contaminated |
| 2 responsibility transfer | `a366d924a9b4dfcd5` @ `863a900` (prereg `8116b7d`) | null vs K0 |
| 3 total+allocation | `a96f23f70cffc45d0` @ `1e3509f` | null; premise contaminated |
| 4 EWMA timescale | `a578166bb62b091a5` @ `1b634fb` (prereg `a6d5cd4`) | falsified in the opposite direction |
| 5 opportunity proxies | `ab8223114ea98f146` @ `6d9e3f2` (freeze `059db0d`) | partial: allocation only |
| 6 mechanism decomposition | `abba0a0dbf84578f1` @ `5ef1f25` | hypothesis rejected as cause; real cause found |
| 7 nonlinear/heterogeneous | `ab4ac90b1f887b5b7` @ `e858e96` (prereg `58b3a91`) | null; refuted on primary creators |
| 8 error decomposition | `a5694dab4e5ccdb3d` @ `c1d2637` | decisive on direction |

**Convergent mechanism (WS5 + WS6 + WS8).** The involvement proxy is a *share*, so 92.6% of its
variance is within-team; within effect **+0.036**, between effect **−0.107**, reversal present in
9 of 9 fitted mechanisms. Given a free coefficient the fit spends it at the team level where it is
wrong. And projected exposure sums to exactly 5x projected team possessions, so candidate-set and
allocation errors **cannot** change forecast volume — only the weighted mean rate.

**WS8 ranking** (delta = MAE before fix − after; positive = that source contributes error):
team possession-total projection **+0.1033** [0.0833, 0.1244]; within-team allocation **−0.0181**
(oracle is *worse*); availability **−0.0034** (null); missing participants **−0.0003** (null).
The rate model is at its Poisson noise floor: ratio to the MAD floor **0.9969**.

## 6. Ranked substantive conclusion (preserve this wording)

1. **Team-possession-total projection** is the clearest remaining team-aggregate opportunity.
2. A **preregistered gated role-expansion challenger** is the strongest narrow turnover hypothesis
   (WS1: `expanded_role_bounded` +0.0265, sd 0.0017, positive in every fold; helps on the 699
   team-games with material expansion, hurts the 2,283 without).
3. **Clean involvement proxies** may have small player-allocation value (+0.0017, ~0.2%).
4. Broader turnover-rate feature expansion should **yield priority**.

> Under the tested total-turnover formulations, the conditional rate model is near its practical
> team-aggregate ceiling. Remaining turnover value is more likely to come from improved
> team-possession projection, a narrowly gated role-expansion effect, or player-level applications
> than from additional broad pooled rate features.

**Do not say turnover research is exhausted.** Note also that the 5x identity gives **no**
cancellation at player level, where props settle: non-appearing candidates carry **14.18%** of
player-level absolute error. That is an availability problem, not a turnover problem.

## 7. IN FLIGHT when this handoff was written

Four integrity workstreams launched in isolated worktrees; **integrate sequentially, coordinator
appends to the registry, agents propose records only**:

* **A** — `comparison_gate.py`, baseline-parity contract. Separate module; must NOT go into
  `feature_gate.py`. Regression test: K0 2.96419 vs Arm D 2.96745, ~0.0033 unmatched intercept.
* **B** — regenerate the turnover receipt through the canonical validation path (do **not** alter
  the target), plus a permanent receipt-integrity check.
* **C** — merge the eight `LEDGER_UPDATE` patches centrally into `HYPOTHESIS_LEDGER.json`.
* **D** — P2 supersession records + `GATE_INVOCATION_CONTRACT.md` (per-fold audits; WS3 found a
  2022 fold with std 7.8e-9 that looked healthy pooled).

**Duplicate task `task_ab6a6675`** ("Close two feature_gate.py blind spots") is running in a
separate local session and could not be cancelled from here. **Do not merge or cherry-pick its
feature-gate changes.** `55f4500` and `42af2cd` are authoritative. Diff it; adopt only a genuinely
new defect.

## 8. Open methodological gaps

* **Baseline parity** is not yet enforced anywhere (Workstream A closes it).
* The feature gate is now rank-aware and missingness-aware but still cannot see **nonlinear**
  dependency, or anything that is a property of the *comparison* rather than the design matrix.
* **Gate invocation timing** is not yet contractual (Workstream D).
* `rebound_type` is `unresolved` on all 125,309 rebound rows — neither source types
  offensive-vs-defensive structurally.
* Free-throw **outcome** is supplied by neither source.
* Steal/block/assist attribution differs structurally across the two source schemas; counts are
  **not** comparable across stores without a registered linkage rule.
* Availability before 2026-07-30 is not a genuine captured pregame feed.
* The rate-model sensitivity arm is unrepaired; `gate_receipt.py` is fail-open (team thread).

## 9. Stop boundary in force

Do **not**, without fresh authorisation: promote any discovery arm; alter Arm D; alter canonical
exposure or the canonical target; begin a confirmation experiment; start another event channel
(rebounds, assists, blocks, fouls, shots); feed turnover forecasts into the team model; link steals
by adjacency; retune P1; merge the duplicate gate task.

## 10. Suggested next step

Finish integrating A-D, commit, then produce the consolidated discovery-wave summary distinguishing
valid / contaminated / corrected / falsified / formulation-dependent-null / narrow-lead findings,
shared-contract defects found, contract fixes implemented, and remaining gaps. Then stop and ask.

The single highest-value *substantive* next experiment, if authorised, is a registered improvement
to `team_possession_prior/1` — it is the only materially addressable team-aggregate error source
found, and its honest prize is small (1.2-2.2% of operational MAE).
