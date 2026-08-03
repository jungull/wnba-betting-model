# PLAYER RESEARCH LEDGER

*Append-only record of the player-level modelling program. Opened 2026-08-03.*

**Conventions.** Entries are appended, never rewritten. A superseded entry keeps its text and
gains a status line. Defects are numbered `P-D<n>` and never renumbered. Every claim states how it
was established: **measured** (this program ran it), **quoted** (read from a registry or receipt,
not recomputed), or **read** (asserted by a document, not independently checked).

**Evidence label for the whole ledger to date: NO SCORING HAS OCCURRED.** No accuracy,
calibration, Brier, log-loss, MAE, RMSE, pinball, interval-coverage, threshold, edge, return or
profitability figure has been computed by this program, and no forecast has been compared to any
outcome. Every number below is a row count, a key-set comparison, a flag distribution, a selected
constant, or a gate verdict. **"Coverage" means obligation completeness** throughout; the
statistical sense is always written *interval coverage*.

---

## §1 · Lineage, established rather than assumed

The brief warns not to assume the latest-numbered implementation is valid. It is not, and the
numbering is misleading in a specific way: **the main checkout is four versions behind the tip.**

| where | HEAD | carries |
|---|---|---|
| `C:/Users/jgallagher/wnba-betting-model` (branch `data-refresh-2026`) | `735b63b` | CBS v1–**v6** |
| `.claude/worktrees/cbs-v2-gate-accounting` (branch `worktree-cbs-v2-gate-accounting`) | `d69aa02` | CBS v1–**v14**, contract v1–v4 |
| `origin/worktree-cbs-v2-gate-accounting` | `702a948` | **one commit behind `d69aa02`** |

A reader who opens the repository root sees a world that ended at v6. The live lineage is in a
worktree, and its tip is unpushed. *(measured)*

### Contract-baseline-suite lineage and review status

Compiled from `MISSION_LEDGER.md`, `project_docs/SPEC_ERRATA.md` and the fourteen
`CONTRACT_BASELINE_SUITE_V*.md` documents. **Not one player-path version has been independently
reviewed and confirmed.**

| version | player-path status |
|---|---|
| v1–v3 | definition only; superseded. v3's implementation diverged from its spec in 8 ways (E-V4-1) |
| v4 | implemented against **synthetic data only** |
| v5 | corrected primitives, **no end-to-end runner**; no correction reached a generated row (E-V5-1) |
| v6 | supplied the missing runner |
| v7–v9 | boundaries, training frame, collision-safe identity, first real *frame* |
| v10 | registered a claim that `cbs_real_frames/2` "builds and hashes real player folds". **It did not** — the merge raised `MergeError` for every season 2021–2026. Superseded, key blind |
| v11 | contract v4 fixed the *key*; the *joins* were still team-blind |
| v12 | **team path accepted, player path blocked** |
| v13 | corrected obligation order; opened the real player path; measured a count defect it was not permitted to repair |
| v14 | corrected the prior-obligation count. **Registered; awaiting supervisory review. Not validated, not confirmed, not replicated** — its own document says so |

`cbs_v14_player_oof/1` (`d69aa02`) sits on top of v14 and is **unreviewed, unpushed and unrun**.

### Player artifacts that exist

**None.** `experiments/cbs_v14_player_oof/` does not exist. There is no player forecast anywhere
in this repository. The only fitted contract artifacts are the team ones,
`experiments/cbs_v12_team_oof_v2/attempt_001`. *(measured)*

---

## §2 · Phase 0 audit of `cbs_v14_player_oof/1`

**Verdict: the modelling substrate is sound and unrun; the publication gate around it is broken.**

Full answers to the ten audit questions are in
[`HANDOFF_PLAYER_MODEL_PROGRAM.md`](HANDOFF_PLAYER_MODEL_PROGRAM.md) §2. The receipt is
`experiments/player_program/PHASE0_AUDIT_RECEIPT.json`, regenerable by
`python experiments/player_program/audit_phase0_v14_player_oof.py --season 2022`.

### Measured on the real 2022 fold, executed in memory

| quantity | value |
|---|---|
| contract obligations, 2021–2026 | 35,627 |
| 2022 train / test / universe rows | 4,850 / 5,563 / 5,563 |
| train ∩ test seasons | ∅ |
| cutoff violations across all `src_asof_*` + `feature_asof` | **0** |
| obligation completeness, all four targets | **1.000** (5,563 / 5,563) |
| obligations excluded | **0** |
| test rows that did not appear, still served | 1,201 |
| `p_active` cold / fallback | 168 / 506 (keyed on prior **obligations**) |
| conditional targets cold / fallback | 310 / 821 (keyed on prior **appearances**) |
| selected λ | 31.622777 |
| selected α — minutes / attempts / points | 0.20 / 0.03 / 0.10 |
| minutes α held fixed for rate targets | yes |
| failed or inherited receipts | none |

The four-target chain, the two-stage identity `E[minutes] = P(active) × E[minutes | active]`, and
the per-target cold-start differentiation are all correct. *(measured)*

---

## §3 · Defects

### P-D1 · The reproducibility gate is fail-open — **CRITICAL, RESOLVED 2026-08-03**

**Resolution, appended rather than rewritten.** The user set `core.bare=false`; verified across
the main checkout and all six worktrees (`rev-parse --show-toplevel` resolves, `status
--porcelain` runs). The preserved repair was reviewed as provenance-only, tested at **61/61
checks** across both runners, and committed as **`ef0d557`** with receipt version
`clean_producer/2`, `supersedes: clean_producer/1`. Erratum:
`experiments/player_program/ERRATUM_CLEAN_PRODUCER_1.md`.

What the repair became visible against, once git worked: **111** dirty paths in the main checkout,
**98** in `cbs-v2-gate-accounting`, **91** in `wnba-target-redesign-891805`. Of the 98, exactly
**3** are real content changes — the repair itself — and 94 differ only in line endings
(`.gitattributes` normalization from `84b2075`). Confirmed in production conditions: the repaired
gate now **refuses** the live player worktree with `7 dirty path(s)`.

`cbs_v12_team_oof/2` is **not invalidated**. Its `/1` receipt's cleanliness claim is unmeasured,
but all 19 recorded producer-source digests recompute **exactly** from `git show 3b04be5:<path>`
and the set digest `12ce0b88…` recomputes from those 19. The runtime digests were taken from disk,
so the producing code on disk was byte-identical to `3b04be5`. Only the broader "no other file in
the tree differed" claim is unverified. The retained generating checkout
`_gen_3b04be5__20260803T011852Z` no longer exists on disk and the exposure window is undetermined;
neither changes the digest verification. **The team thread decides what to regenerate.**

The original finding follows unchanged, because it is the evidence for the erratum and the notice.

`core.bare=true` on the shared repository makes `git status` exit 128 in every worktree while
`git rev-parse HEAD` still succeeds. `require_clean_producer` at `d69aa02` reads status through a
best-effort helper that returns `""` on failure — indistinguishable from a clean tree. Measured in
a pristine checkout of `d69aa02`: `ok: True`, `working_tree_clean_vs_head: True`,
`n_dirty_paths: 0`, `commit: d69aa02…` — **over a tree the gate never inspected.**

This re-grants, silently, the exact defect `cbs_v12_team_oof/1` was rejected for. No player
artifact can be honestly labelled reproducible until it is fixed. *(measured)*

**Consequence beyond this program:** any receipt in this repository claiming `n_dirty_paths: 0`
from a worktree is an **unmeasured** claim, not a false one — it must be re-read, not discarded.
This includes team-thread receipts. Flagged to the team thread as **S1**; not acted on here.

### P-D1a · A repair exists, uncommitted and unreviewed — **PRESERVED**

`.claude/worktrees/cbs-v2-gate-accounting` carries uncommitted working-tree changes to three
files that fix exactly this:

| file | committed | uncommitted | adds |
|---|---|---|---|
| `run_player_oof_v14.py` | 1136 ln | 1198 ln | `_git_checked` (non-zero exit ⇒ `DirtyProducer`), `_git_env` (scrubs inherited `GIT_DIR`/`GIT_WORK_TREE`), toplevel-matches-root proof, `_SHA_RE` commit check |
| `run_team_oof_v12_2.py` | 661 ln | 734 ln | matching changes |
| `tests/test_run_player_oof_v14.py` | 546 ln | 631 ln | tests for the above |

Its docstring documents a real hazard the player program did not have to rediscover: a `pre-push`
hook exports `GIT_DIR`, and this project's hook runs the whole Layer-A gate, so any producer gate
invoked from inside it measured *the hook's repository*.

**Preserved** at `experiments/player_program/preserved_uncommitted_d69aa02/` — the three files,
unified patches against `d69aa02`, and `PRESERVATION_MANIFEST.json` with before/after hashes. The
player program **has not modified them and has not committed them to any team branch.** This is
team-thread material; disposition is the team thread's. Flagged as **S2**. *(measured)*

### P-D2 · played player-games that are not obligations — **v5 Stage 1 BUILT; 977 → 210**

> **Resolution 2026-08-03, appended.** `prediction_contract_v5` Stage 1 is implemented, validated
> and committed at `ac9958f`. `experiments/prediction_contract_v5/`.
>
> | | v4 | v5 |
> |---|---|---|
> | universe rows | 35,627 | **44,851** |
> | Tier A (verified obligation) | 35,627 | 35,629 |
> | Tier B (fallback candidate) | — | 9,222 |
> | v4 obligations lost | — | **0** (superset asserted) |
> | **appearing players missed** | **977** | **210** (−78.5%) |
>
> Residual 210: 94 mid-season, 92 opener, 24 early; **86 of them in 2021**, which has no prior
> season for S2 and the thinnest transaction resolution.
>
> **The false-obligation probe the amendment required is the most useful result.** Sole-source
> rows and how many appeared: **S_TX 1,258 → 434 (34.5%)**; **S2 5,053 → 44 (0.87%)**. S2 as a
> sole source is **99.1% non-appearing, a 115:1 ratio**. Its value could never have been
> established by counting opening-night recoveries — exactly the amendment's point. Retained as
> Tier B, reported separately, flagged `weak`, and structurally barred from Tier A.
>
> **Two defects found by running it**, both recorded rather than quietly fixed:
>
> 1. An earlier spec draft required `n_prior_appearances ≤ n_prior_candidate_obligations` as an
>    invariant. It is not one — appearances count games *played*, obligations count forecasts
>    *owed*, and 8,269 rows demonstrated the difference. Enforcing it would have made the contract
>    refuse to describe the gap it exists to close. Now a reported per-row measure.
> 2. v4 owes nothing for a season opener, so a game where **both** clubs are playing their first
>    game has no v4 row and therefore **no cutoff**. The generator skipped those games entirely,
>    silently discarding **728 of the 749** opener rows v5 exists to recover — the gap had erased
>    its own timestamp. Games absent from v4 now take v4's own `POLICY_DATE_ONLY` fallback, and
>    every row declares `cutoff_source`. 2,345 rows carry a derived cutoff.
>
> Tests: `tests/test_prediction_contract_v5.py`, **44/44**, including a behavioural test of the
> postgame prohibition — a fixture player who appears only in the target game is asserted *not* to
> be a candidate for it and *is* recorded as a candidate-universe miss.
>
> **P-D3 is resolved by the same commit**: `n_prior_games` is retired, replaced by
> `n_prior_candidate_obligations`, `n_prior_appearances`, `n_prior_team_games`.
>
> The original entries follow, retained unchanged.

### P-D2 (original) · 51 → 977 played player-games are not obligations

> **Update 2026-08-03.** The figure is **977, not 51.** The 51 were only the rows visible where
> the registered minutes universe overlapped the contract. Measured against
> `master_player.parquet` by `audit_candidacy_gap.py`: **977 of 28,322** played player-team-games
> (3.45%), 356 players, 233 games, stable at 2.9–4.6% in every season.
>
> The decomposition changes what the fix is. **749 (77%) are season openers** — v4 requires a
> prior *same-season* team game, so every team's first game of every season yields zero
> candidates. **176 (18%) are mid-season arrivals.** 52 are partial early-season windows.
>
> `prediction_contract_v5` is specified against this
> (`experiments/player_program/PREDICTION_CONTRACT_V5_SPEC.md`, registered). Prior-season
> franchise membership is provable and cutoff-safe and recovers **324 of 749** openers (51.2%
> outside 2021); the residue is declared an audited exclusion, because **roster membership cannot
> be reconstructed from box scores alone** and no transaction log exists in this repository.
>
> The original entry follows, retained unchanged.

Reconciling the registered minutes universe against contract v4 for 2024–2026:

| | |
|---|---|
| incumbent rows | 13,501 |
| present in contract v4 | 13,450 |
| **absent from contract v4** | **51** (2024: 13, 2025: 25, 2026: 13) |
| contract-appeared rows absent from the incumbent universe | 1,058 |
| distinct games / players in the 51 | 43 / 44 |
| those 43 games present in the contract | **43 of 43** |

The games are in the contract; the `(game_id, player_id)` pairs are not. These players
**demonstrably logged minutes** — Odyssey Sims, Marina Mabrey, Moriah Jefferson, Rachel Banham,
Celeste Taylor, Queen Egbo among them — and the pattern is mid-season signings, hardship contracts
and trades: no roster evidence inside the candidacy window, played immediately anyway.

0.35% of the 2024–2026 appeared universe. Small in aggregate, **systematic in kind**, and
production meets this class every week. It is a contract-universe question and the contract is
shared: flagged as **S3**, not changed here. *(measured)*

### P-D3 · `n_prior_games` changes meaning on the cold-start fold — **OPEN, minor**

In `cbs_player_runner_v14.run_player_fold`, the fitted branch gives `p_active` its
`n_prior_candidate_games` (prior obligations) while the three conditional targets get
`n_prior_appearances`. That differentiation is **correct**. The degenerate branch — taken when the
training window is empty, i.e. the 2021 fold — emits `n_prior_appearances` for **all four**
targets. So `p_active`'s `n_prior_games` column counts obligations in 2022–2026 and appearances in
2021.

Not a leak and not a coverage failure; every 2021 row is cold by construction so no decision turns
on it. But any per-history-bucket analysis that pools 2021 with later seasons will bucket 2021
`p_active` rows on the wrong quantity. Repair before the first history-bucketed report. *(measured
by source inspection and confirmed against the emitted 2022 columns)*

---

## §4 · Incumbent and micro-gain evidence, preserved

Both **quoted** from `experiments/registry.jsonl`; neither recomputed, because recomputing a
metric is scoring.

### Incumbent — `minutes_ewma_alpha030_v1`

`minutes_ewma_vs_carryforward_v1` run 1. Shifted per-player minutes EWMA, α = 0.30 frozen by
`MINUTES_MODEL_SPEC`, tuned on 2021–2023.

| | |
|---|---|
| minutes MAE | **4.6428** vs 5.3913 carry-forward |
| pooled improvement | 0.7485, 90% date-cluster CI [0.6899, 0.8029] |
| gates | 1 P · 2 P · 3 P · 4 not provided · 5 P → **PASS** |
| n | 13,501 rows / 253 date clusters, 2024–2026 |

**Status: standing incumbent for `e_minutes_given_active`.** Retained until re-evaluated on the
corrected contract.

### Micro-Gain Portfolio · MG-1 — `minutes_twostage_availability_v1`

Two-stage availability × minutes.

| | |
|---|---|
| minutes MAE | **4.6057** vs 4.6428 |
| improvement | 0.0370, CI [0.0116, 0.0613] — **excludes harm**, **fails** the 0.10 bar |
| gates | 1 **F** · 2 P · 3 P · 4 not provided · 5 P → FAIL |
| Stage-A Brier (M2, secondary) | 0.0796 vs 0.1084 expanding prior, CI [0.0267, 0.0312], **bar met** |
| exploratory RMSE (not preregistered) | 6.928 vs 7.282 |
| audits | incumbent reproduction max dev 7.1e-15; shift-recompute 875 checks, 0 mismatches; permutation probe collapses to shuffled mean |

**Status: retained in the Micro-Gain Portfolio, not discarded.** It fails to *replace* the
champion on the preregistered bar; it is favourable, clean, and its Stage-A component is the
strongest availability evidence the project holds. The RMSE note matters downstream: the
aggregation layer consumes **means**, not medians, and MAE on a zero-inflated mixture structurally
rewards hard zeros. Re-evaluate on the corrected contract before any verdict.

---

### Prior evidence · PE-1 — the bottom-up thesis has already failed the joint gate once

`bottomup_3pt_channel_v1`, quoted from the registry. Team 3-point points as Σ over rostered
players of [shifted per-minute 3PA-rate EWMA × EB-shrunk 3P% × expected minutes (Stage-A
`p_plays` × shifted minutes EWMA)]. A prototype of the layer this program is chartered to build.

It **improved its own channel** (MAE 7.0614 vs 7.1142) and **degraded the joint forecast**
(margin MAE 10.3569 vs 10.1753, degradation 0.1816 against a 0.05 tolerance, 627 games). Gates
1 F · 2 P · 3 F · 4 **F** · 5 P.

The mechanism is fully decomposed in the registry and is not a mystery:

| | challenger | incumbent |
|---|---|---|
| var(e_home) | 124.58 | 126.84 |
| var(e_away) | 121.09 | 121.22 |
| cov(e_home, e_away) | 37.34 | 40.46 |
| corr(e_home, e_away) | **0.3036** | **0.3258** |
| var(margin error) | 171.11 | 167.27 |

Since `var(margin err) = var(e_h) + var(e_a) − 2·cov`, the bottom-up layer bought ~2.4 units of
per-side variance and paid ~6.2 units in lost covariance. **The team model's two-sided errors
share a common component — league scoring level, pace, era — which cancels in the margin.
Per-player idiosyncratic noise does not cancel.**

This is the single most important piece of prior evidence the player program holds, and it is a
direct answer to the brief's instruction to *"report where player-level gains disappear during
aggregation"*: they disappear into **lost error correlation**. It is also a concrete argument for
hierarchical (rung 3) over per-player (rung 7) structure that does not depend on any per-player
accuracy claim — a model with league-wide and role-level effects retains a shared term; a
fully-idiosyncratic one does not.

Caveat from the gate's own protocol note: the challenger was unconstructible on 2021–2023 (its
Stage-A artifacts were test-years only), so the incumbent's train-years-only calibration was
applied unchanged and no refit was possible without touching test data. The uncalibrated
sensitivity check agrees in direction (10.4371 vs 10.3402), so the verdict stands, but a rebuilt
player layer with full-history Stage-A artifacts is entitled to a fresh test rather than inheriting
this conclusion. **Status: retained as prior evidence, not as a settled verdict on bottom-up
aggregation.**

---

## §5 · Where the program stands against its objective

`cbs_v14_player_oof/1` occupies **rungs 1–2** of the modelling hierarchy (shifted EWMA baselines;
regularised pooled models). Rungs 3–7 do not exist:

| rung | status |
|---|---|
| 1 · shifted EWMA baselines | **built** (three conditional targets) |
| 2 · regularised pooled models | **built** (`p_active` ridge logistic) |
| 3 · hierarchical with player effects | **not started** — preregistered as `player_model_bakeoff_v1` arm 2, blocked |
| 4 · role/archetype partial pooling | **not started** |
| 5 · constrained nonlinear | **not started** — preregistered as arm 3 (CatBoost) |
| 6 · mixture of experts | **not started** |
| 7 · player-specific models | **not started**, and correctly gated behind chronological OOS evidence |

Individualisation today comes **only** from player-specific recent state (the EWMA). There are no
player random intercepts, no archetype effects, no partial pooling, no player-specific
uncertainty, and no opponent context in the player targets.

Stage coverage: **A** built, **B** built, **C** partial (`attempts_usage` only — no 3PA, FTA,
rebound, assist, turnover or foul opportunity), **D** absent entirely, **E** absent entirely.

The unblock: `player_model_bakeoff_v1` (registry row 65) is blocked on "a shared as-of feature
matrix, manifest-first". **`cbs_real_frames/3` is that matrix**, and this audit has verified it
builds, is cutoff-safe and is attested. Wiring the bake-off to it is the single highest-leverage
next step, and it is already preregistered under a binding identical-treatment clause with 2025
sealed and 2026 declared a locked final holdout. *(read + measured)*

---

## §6 · Stop conditions, and why the program is stopped

Instructed to stop before accuracy interpretation if the contract, provenance, chronological
split, player universe, or coverage validation fails.

| condition | verdict |
|---|---|
| contract | **PASS** — real v4 contract, attested, 35,627 obligations, canonical key re-derives |
| chronological split | **PASS** — train/test seasons disjoint, 0 cutoff violations, tuning and calibration inside the train frame |
| coverage validation (obligation completeness) | **PASS** — 1.000 on all four targets, 0 excluded, *within v4's universe* |
| **provenance** | ~~FAIL~~ → **PASS** — P-D1 resolved; gate measured, `FAIL_OPEN: false` |
| **player universe** | **FAIL** — P-D2, now measured at **977** played player-team-games outside the obligation universe, not 51 |

### The authorised gate list (2026-08-03 instruction), current state

| # | condition | state |
|---|---|---|
| 1 | `core.bare=false` verified | **PASS** — all seven checkouts resolve |
| 2 | producer gate fails closed | **PASS** — 61/61, `clean_producer/2` at `ef0d557` |
| 3 | new or amended player universe passes | **PASS** — v5 Stage 1 built and validated, 44/44 tests, superset over v4 asserted |
| 4 | obligation coverage reconciles | **PASS with a declared residue** — misses 977 → 210, enumerated by cause, season and tier; the residue is *audited*, never zero and never unknown |
| 5 | cold-start and fallback semantics reconcile | **PASS** — `is_cold_start` derives from prior appearances; Tier A/B carry `is_fallback`, `team_assignment_confidence` and evidence times |
| 6 | `n_prior_games` semantics corrected | **PASS** — retired; three named fields, never conditioned on fold or target |
| 7 | snapshot and model identities valid | **PASS** — all receipts pass, no failed or inherited |
| 8 | real OOF artifact reproducible | **BLOCKED** — Stage 2 not authorised; never generated |

**Seven of eight clear. Only the out-of-fold artifact remains, and it is Stage 2.** Accuracy
interpretation remains unauthorised and the program stops here as instructed. This is consistent with the standing escalation in `MISSION_LEDGER.md`, in which the
supervisor declined to self-authorize the first outcome-comparing step under reduced independence.

---

## §7 · Changes made to shared material

**None.** This program has created files only, on branch `player-model-program`, in
`experiments/player_program/` plus three root documents. It has not modified any team artifact,
`MISSION_LEDGER.md`, any leaderboard, `experiments/registry.jsonl`, any
`CONTRACT_BASELINE_SUITE_*` document, `prediction_contract_v4`, or any file in the team branch.
The preserved uncommitted material was **copied**; its source worktree is untouched.

---

## §8 · This program's own deliverables were uncommitted, for the reason it documented — **CLEARED**

> **Cleared 2026-08-03.** `core.bare=false` was set by the user; `git add` works; the gate repair
> is committed at `ef0d557` and these documents at the commit that follows it. The record below
> is retained because the situation it describes — a defect severe enough to block the recording
> of its own discovery — is worth keeping.
>
> Before/after, for the record:
>
> ```
> before : [core] bare = true      (git status → fatal, exit 128, in every checkout)
> after  : [core] bare = false     (git status → runs; 111 dirty paths in the main checkout)
> command: git --git-dir=C:/Users/jgallagher/wnba-betting-model/.git config --local core.bare false
> ```
>
> No tracked file was modified by the configuration correction.

P-D1 blocks more than evidence generation: `core.bare=true` makes **every** git write operation
fail, `git add` included. These three documents and `experiments/player_program/` exist on disk in
the `player-model-program` worktree and **cannot be committed** until S1 clears.

The repair is one command, and it is deliberately **not** run by this program:

```
git --git-dir=C:/Users/jgallagher/wnba-betting-model/.git config --local core.bare false
```

The setting is unambiguously wrong rather than intentional — verified: `.git/` is a subdirectory,
tracked files are checked out in the main directory, and `.git/config` line 4 carries
`bare = true`. A genuinely bare repository has neither a `.git/` subdirectory nor a checkout. The
repair changes no tracked file, no artifact, no result and no classification, and reverses with
`core.bare true`.

It was attempted and **denied by the environment's permission layer**. That denial is respected
rather than worked around, so the change is escalated to the user together with the rest of S1.

**Reproducing P-D1 after the repair** — the proof is re-armable, not lost. Set `core.bare true`,
run the audit, observe `producer_gate_FAIL_OPEN: true`, set it back. The audit script probes the
raw git exit codes and compares them against the gate's rendered verdict, so it *detects* the
condition rather than assuming it.
