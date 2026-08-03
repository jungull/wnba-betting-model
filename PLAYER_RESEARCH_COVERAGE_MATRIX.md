# PLAYER RESEARCH COVERAGE MATRIX

*What the player program is required to cover, against what exists. Opened 2026-08-03.*

**Status legend**

| | |
|---|---|
| **BUILT** | exists, executes on the real contract, verified by this program |
| **BUILT‑U** | exists and executes, but **unrun** — no artifact has been generated |
| **LEGACY** | exists outside the contract path; evidence quoted from the registry, not re-derived on the contract |
| **BLOCKED** | designed or preregistered, cannot proceed until a named blocker clears |
| **ABSENT** | not started |

**No cell in this matrix contains an accuracy figure.** Nothing has been scored. "Coverage" in
the obligation columns means **obligation completeness**; the statistical sense is written
*interval coverage*.

**Live blockers** — see [`PLAYER_RESEARCH_LEDGER.md`](PLAYER_RESEARCH_LEDGER.md) §3:

* **P-D1** reproducibility gate fail-open (`core.bare=true`) → nothing can be generated with an
  honest receipt
* **P-D2** 51 played player-games outside the obligation universe
* **P-D3** `n_prior_games` changes meaning on the 2021 cold-start fold
* **SCORING** unauthorised; escalated to the user and still open

---

## 1 · Prediction targets

### Stage A — availability

| target | status | where | note |
|---|---|---|---|
| `P(active)` | **BUILT‑U** | `cbs_player_runner_v14` | ridge logistic, 12 Stage-A features, λ chronologically selected. Emitted for every obligation; 0 excluded |

Stage-A **evaluation** — Brier, log loss, calibration, false-active/false-inactive rates, and
breakdowns by role, history, injury status, team and season — is **BLOCKED on SCORING**. A legacy
Stage-A Brier result exists (MG-1, quoted) but was computed off-contract.

### Stage B — minutes conditional on playing

| target | status | note |
|---|---|---|
| `E[minutes \| active]` | **BUILT‑U** | walk-forward active-masked EWMA, α selected per fold (0.20 on 2022) |
| conditional minute **quantiles / distribution** | **BUILT‑U, shape only** | q05/q25/q50/q75/q95 are emitted, but from a **single fold-level dispersion σ with fixed z-offsets** — not a fitted conditional distribution. Adequate as a placeholder, not as a quantile model |
| two-stage identity `E[min] = P(active) × E[min\|active]` | **BUILT‑U** | verified formable: both targets key onto an identical `row_uid` set |

Stage-B evaluation — MAE, RMSE, pinball, **interval coverage**, errors by starter/bench, after
absences, during rotation changes, and cold-start — is **BLOCKED on SCORING**.

### Stage C — opportunities

| opportunity | status |
|---|---|
| FGA | **BUILT‑U** as `attempts_usage` |
| 3PA · FTA · usage/possession share · rebound opportunities · potential-assist / assist rate · turnovers · personal fouls | **ABSENT** — all seven |

The brief prefers rate/share × expected minutes over direct counts. `attempts_usage` already uses
a conditional-centre decomposition with the minutes constant held fixed, so the pattern is
established and the remaining seven are extensions of an existing shape rather than new
architecture.

### Stage D — efficiency

**ABSENT in full.** No 2-point conversion by location, 3-point conversion, free-throw conversion,
rebound share, assist conversion, turnover rate, foul-drawing rate or foul-committing rate. No
partial pooling of any efficiency quantity exists on the contract path.

Assets that would feed it: `data/shotcharts/`, `data/possessions/`, `data/playbyplay/` (996
games), `build_zone_maps.py`, `bottomup_3pt.py`.

### Stage E — final stat distributions

**ABSENT in full.** No points, rebounds, assists, 3PM, FTA or turnover distribution.
`player_scoring_distribution` is a **conditional centre plus a fold-level σ**, not a distribution
over points. Direct-stat baselines for comparison do not exist on the contract path.

---

## 2 · Modelling hierarchy

| rung | status | note |
|---|---|---|
| 1 · shifted EWMA baselines | **BUILT‑U** | three conditional targets |
| 2 · regularised pooled models | **BUILT‑U** | `p_active` ridge logistic |
| 3 · hierarchical with player effects | **BLOCKED** | preregistered as `player_model_bakeoff_v1` arm 2, "dynamic hierarchical player profiles", highest priority. Blocker of record: *"shared as-of feature matrix, manifest-first"* — **`cbs_real_frames/3` is that matrix**, verified here |
| 4 · role/archetype partial pooling | **ABSENT** | `player_vs_archetype_v1` and `experiments/feature_archetypes/` exist as legacy screens |
| 5 · constrained nonlinear | **BLOCKED** | bake-off arm 3 (CatBoost) |
| 6 · mixture of experts | **ABSENT** | |
| 7 · player-specific models | **ABSENT** | correctly gated: permitted only on stable chronological OOS improvement over the pooled/hierarchical alternative, never by reputation |

### Sources of individualisation

| source | present? |
|---|---|
| shared coefficients | **yes** — `p_active` ridge is pooled across all players |
| player random intercepts / effects | **no** |
| player-specific recent state | **yes** — the EWMA; this is currently the *only* individualising mechanism for Stages B/C |
| role / archetype effects | **no** |
| player-specific uncertainty | **no** — σ is fold-level, identical for every player in a target |
| team and opponent context | **no** in the player targets. `p_active` reads team-schedule features (`team_gp_season`, `played_last_team_game`, `played_share_l10_team_games`, `games_missed_streak`) but no **opponent** feature exists on any player target |

---

## 3 · Player heterogeneity

Every routing or archetype definition must be built from training-period information only. Nothing
below is implemented on the contract path.

| dimension | data available? | implemented? |
|---|---|---|
| stable starter vs volatile rotation | yes — `starter_flag_observed`, `start_share_l5`, `started_last` | **no** |
| high vs low usage | partially — `attempts_usage` emitted; no usage share | **no** |
| high vs low historical sample | yes — `n_prior_appearances`, `n_prior_candidate_games` | **used only for fallback banding**, never for routing |
| rookie / new signing | partially — cold-start flags exist; no transaction log | **no** |
| returning from absence | yes — `returning_flag`, `days_since_last_appearance`, `games_missed_streak`, `prev_dnp_{cd,inj,nwt,unknown}` | **no** |
| position / functional role | **not in the contract frame** | **no** |
| team rotation depth | derivable from the appearance index | **no** |
| scoring archetype | derivable from shotcharts | **no** |
| foul / FT dependence | **not in the contract frame** (no PF, no FTA) | **no** |
| player-specific volatility | derivable; σ is currently fold-level | **no** |

The fallback ladder (`player_fallback_level` → levels 0/2/3) is the only heterogeneity mechanism
in force, and it is a **history-depth** ladder, not a behavioural one.

---

## 4 · Evaluation surface

Required for every target. **All of it is BLOCKED on SCORING**; the two obligation-completeness
rows are the exception and already pass.

| dimension | status |
|---|---|
| pooled micro | BLOCKED |
| macro average across players | BLOCKED |
| minutes-weighted | BLOCKED |
| per-player where sample adequate | BLOCKED |
| by role and volume bucket | BLOCKED — and routing definitions do not exist yet (§3) |
| by history / cold-start bucket | BLOCKED — **and P-D3 must be repaired first**, or 2021 `p_active` rows bucket on the wrong quantity |
| by team and season | BLOCKED |
| calibration | BLOCKED |
| prediction-**interval** coverage | BLOCKED — and the quantiles are a fixed-σ placeholder, so this will grade the placeholder, not a model |
| **obligation completeness** | **PASS** — 1.000 on all four targets, 2022 fold, 0 excluded |
| **exclusions** | **PASS** — 0 exclusions; every DNP obligation still served |
| complexity / operational cost | partially available — `elapsed_seconds` per fold; the 2022 fold takes ~35 s |

**Dependence structure.** The brief forbids treating thousands of player-games as independent. The
incumbent evidence already uses date-cluster bootstrap (253 clusters) with a team-cluster
sensitivity check. The contract path has `row_uid`, `player_id`, `team_id`, `game_id`,
`game_date` and `season` on every row, so date/game/team/player-aware uncertainty is constructible.
**Not yet implemented on the contract path.**

**Micro-Gain Portfolio.** Instituted; MG-1 (`minutes_twostage_availability_v1`) is its first
member — favourable, clean, below the replacement bar, retained rather than discarded.

---

## 5 · Downstream gate — aggregation into the team forecast

**ABSENT in full.** No player prediction has ever been aggregated to a team quantity.

| requirement | status |
|---|---|
| aggregate to home score / away score / margin / total | **ABSENT** |
| aggregate into the existing structural scoring channels | **ABSENT** — the channels (`ch_ft`, `ch_3pt`, `ch_paint`, `ch_np2`) exist on the team frame with the box identity verified to 1e-9; the player→channel map does not |
| team-minute constraint | **ABSENT** — nothing constrains Σ player minutes to 200 (+ OT) |
| statistical accounting identities | **ABSENT** |
| uncertainty propagation | **ABSENT** |
| cold-start and missing-player accounting | **partially available** — per-row cold and fallback flags exist and would propagate |
| report where player gains vanish under aggregation, and where aggregation cancels error | **ABSENT** |

Note the architecture is designed for this: `project_docs/HANDOFF.md` §4 records that each channel
"decomposes naturally into Σ(player rate × expected minutes) — it is the scaffold the player layer
bolts onto." The scaffold exists; the bolt does not.

The promotion rule stands: a player layer must improve its player target **and** not degrade the
joint team forecast. `gate4_joint_forecast` is `not_provided` on every registered *player-target*
evaluation — `minutes_ewma_vs_carryforward_v1`, `minutes_twostage_availability_v1`,
`oracle_availability_bracket_v2`, `w6_microsignal_retrospective_v1`. No minutes or availability
result has ever been tested against the joint team forecast.

### The one time bottom-up aggregation *was* tested, it failed — and the mechanism is known

`bottomup_3pt_channel_v1` is the V4 bottom-up thesis's first true test: team 3-point points as
Σ over rostered players of [shifted per-minute 3PA-rate EWMA × empirical-Bayes-shrunk 3P% ×
expected minutes (Stage-A `p_plays` × shifted minutes EWMA)], with the incumbent's structural
opponent-allowed adjustment applied. **This is a prototype of exactly the layer this program is
building.** *(quoted from the registry)*

| | challenger (bottom-up) | incumbent (team structural) |
|---|---|---|
| 3-point channel MAE | **7.0614** | 7.1142 |
| margin MAE after substitution | **10.3569** | 10.1753 |
| var(e_home) | 124.58 | 126.84 |
| var(e_away) | 121.09 | 121.22 |
| cov(e_home, e_away) | 37.34 | 40.46 |
| **corr(e_home, e_away)** | **0.3036** | **0.3258** |
| var(margin error) | 171.11 | 167.27 |

Gates: 1 **F** · 2 P · 3 **F** · 4 **F** (degradation 0.1816, tolerance 0.05) · 5 P, over 627 games.

**The player layer won at its own target and lost the game.** Because
`var(margin err) = var(e_h) + var(e_a) − 2·cov(e_h, e_a)`, the bottom-up channel reduced *each
side's* error variance yet **decorrelated the two sides**, and losing 3.1 units of covariance cost
more than the 2.4 units of variance it saved. The team-level model's two-sided errors share a
common component — league scoring level, pace, era mis-estimation — which **cancels in the
margin**. Replacing it with per-player idiosyncratic noise destroys that cancellation.

Three binding consequences for this program, recorded before any player layer is built:

1. **Per-side improvement is not evidence.** Every aggregation candidate is judged on margin and
   total, not on its own channel.
2. **corr(e_home, e_away) is a first-class reported quantity**, alongside the two variances, for
   every aggregation candidate. A candidate that improves per-side error while lowering this
   correlation should be expected to fail.
3. **Preserving the shared component is a design goal, not an afterthought.** A hierarchical
   player model with league-wide and role-level effects retains a common term that a
   fully-idiosyncratic per-player model does not — which is a concrete, testable argument for
   rung 3 over rung 7, independent of any per-player accuracy claim.

One caveat, recorded from the gate's own protocol note: the challenger was *unconstructible on
2021–2023* because its Stage-A artifacts were test-years only, so no calibration refit was
possible without touching test data, and the incumbent's train-years-only calibration was applied
unchanged. The comparison is therefore slightly unfavourable to the challenger by construction.
The uncalibrated sensitivity check shows the same direction (10.4371 vs 10.3402), so the verdict
survives, but a rebuilt player layer with full-history Stage-A artifacts deserves a fresh test
rather than inheriting this one's conclusion.

---

## 6 · RAPM

**Gated by the brief** behind a passing real player baseline suite and possession reconciliation.
Neither has passed: the baseline suite is unrun (P-D1) and possession reconciliation is
unverified by this program.

Legacy assets exist: `experiments/rapm_v0/`, `experiments/rapm_multiseason/` (decay-pooled,
prior-anchored and extended-λ fits for 2021-24 and 2021-26, with sweeps),
`experiments/rapm_walkforward/`, `build_rapm{,_v1,_walkforward}.py`,
`data/player_possession_features.parquet`.

| validation required | status |
|---|---|
| predictive error on future stints | **ABSENT** |
| future on/off and lineup performance | **ABSENT** |
| year-over-year stability | **ABSENT** |
| ridge-penalty stability | **partial** — λ sweeps exist (`sweep_lambda_extended.csv`), stability not established |
| garbage-time and leverage sensitivity | **ABSENT** |
| replacement-level behaviour | **ABSENT** |
| rookie / low-minute behaviour | **ABSENT** |
| downstream team-forecast contribution | **ABSENT** |

**"Known stars rank highly" is a data-quality smoke test only** and is not admissible as a
promotion test. Recorded here so it cannot be reintroduced as evidence.

---

## 7 · Location-and-context expected points

Gated behind valid minutes and RAPM foundations. **ABSENT in full.**

| component | status | asset |
|---|---|---|
| player shot-location tendency | ABSENT | `data/shotcharts/`, `build_zone_maps.py` |
| location-based expected conversion | ABSENT | same |
| shooter performance vs location expectation | ABSENT | |
| opponent allowed-location distribution | ABSENT | |
| opponent conversion allowed | ABSENT | |
| empirical-Bayes / hierarchical shrinkage for player-zone cells | ABSENT | **required** — raw player-zone cells are far too thin |
| back-off to team / archetype / league prior for unsupported players | ABSENT | **required** |

---

## 8 · Referees and garbage time

### Referee hypotheses — preserved, not yet testable on the player path

| hypothesis | status |
|---|---|
| FT-dependent player × crew FTA propensity | **ABSENT** — and FTA is not a contract target (Stage C gap) |
| foul-out risk | **ABSENT** — personal fouls are not a contract target |
| star-whistle effects | **ABSENT** |
| player-prop effects | **ABSENT** on the contract path; `experiments/props_edge/` is legacy |

Assets: `experiments/w4_refs/` (crew factors, k-tuning, game-level predictions),
`data/officials_master.csv`, `data/ref_assignments/assignments_log.csv`, `w4_refs.py`,
`ref_assignments_capture_daily.py`.

**Hard precondition, recorded now so it is not discovered late:** referee assignments must be
available **before the relevant forecast cutoff**. The contract's cutoff policy is date-based and
the assignment log is a daily capture; whether assignments land before cutoff is an **unverified**
question and must be established before any referee feature enters a player forecast.

### Garbage time

**ABSENT.** No garbage-time definition exists on the player path.

Requirements recorded: keep **both** a full-game and a competitive-possession version — do not
delete low-leverage possessions; define the rule using **only score differential and time
remaining**, never with reference to the final outcome.

---

## 9 · Program hygiene

| requirement | status |
|---|---|
| separate branch / worktree | **DONE** — `player-model-program` |
| team artifacts treated read-only | **DONE** — no shared file modified; §7 of the ledger records this |
| dedicated player-experiment artifact directory | **DONE** — `experiments/player_program/` |
| handoff · ledger · coverage matrix | **DONE** — this file and its two siblings |
| Phase 0 audit before new architecture | **DONE** — receipt regenerable |
| invalid work preserved, not silently rewritten | **DONE** — P-D1a, `preserved_uncommitted_d69aa02/` with manifest and patches |
| communicate via frozen artifacts only | **in force** — nothing has yet been handed to the team thread |
| shared changes stopped and documented | **DONE** — S1, S2, S3 in the handoff §6 |
