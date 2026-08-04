# Stage 2A synthesis — deduplicated families, proposed variants, multiplicity plan

Six independent sources, one frozen packet (`f373e3ee…`). Coordinator set frozen 18:03:30Z before
any agent launched; five agents launched simultaneously; none saw another's output.

**Nothing fitted. Nothing registered. No accuracy opened.**

---

## 0. Two items that are NOT hypotheses — they are blocking Phase 0 questions

### P0-1. Possession units are inconsistent between artifacts — **THREE sources, independently**

Time-series, opponent/environment and adversarial all reached this from different lenses.
Verified: `team_turnover_reconciliation_v1.team_off_possessions` equals the **raw** count on
2990/2990 rows; the incumbent projects **regulation-equivalent**. On 132 OT team-games raw exceeds
regulation-equivalent by a mean factor of 1.140 (~+10.6 possessions, ~+1.70 turnovers).

This explains an oddity in the packet that I recorded without interrogating: OT games show
*better* MAE (2.367) than non-OT (2.928), because the panel is blind to the basis difference.

**No arm may be registered until the downstream scorer is read and the operative unit
established.** If the scorer normalises for game length, an entire family below is void. If it
does not, the challenger and the metric are on different quantities. Adversarial adds the sting:
all three sides would declare the *same wrong* unit, so `comparison_gate`'s `exposure_offset`
dimension **passes** — parity checking structurally cannot catch this.

Adversarial also flags the trap in the obvious fix: rescaling by realised `game_minutes` hands the
model an exact overtime indicator, i.e. target leakage.

### P0-2. Effective n is 1,491, not 2,982 — **TWO sources**

Verified: both sides of every game share one identical projection (1495/1495), and 97.8% of
team-game target variance is game-level. Naive standard errors are understated by ≈√2; a "2σ"
gain is ≈1.4σ. **Comparisons must be paired on identical games and clustered at game level.**
`comparison_gate` supplies an uncertainty slot but never checks a supplied interval is correct.

---

## 1. Deduplicated hypothesis families

| # | family | sources | targets | verdict |
|---|---|---|---|---|
| **F1** | Measurement-basis correction: count regulation possessions directly rather than minute-scaling OT | pace, opponent, time-series, adversarial | 32.8% of windows | **propose**, gated on P0-1 |
| **F2** | Duration-domain aggregation: combine as `4800/(d_A+d_B)` not `(n_A+n_B)/2` | pace, opponent | all rows | **propose** |
| **F3** | Fallback-tier re-centring / league drift | coordinator, pace, opponent, roster | 183 + 228 rows | **propose** |
| **F4** | Support-scaled shrinkage & effective sample size (window length, EWMA, local-level nested) | coordinator, time-series, pace | 2,413 full-support rows | **propose** |
| **F5** | Opponent interaction / head-to-head | coordinator, pace, opponent | 85.1% of rows | **propose — CONTESTED** |
| **F6** | Genuine expansion cold start | roster | **9 rows** | **reject as an arm** |
| **F7** | Roster-weighted bottom-up pace | roster | all rows | **propose, low prior** |

### The four sources that converged on F3 did so from four different mechanisms
Coordinator called it league drift; pace called it relative-tempo re-basing; opponent called it a
near-pure bias fix; roster called it a season-boundary blend. Same 183+228 rows, same −2.845 /
−2.175 bias. **One family, not four.**

---

## 2. Disagreements — preserved, not resolved

**D1. Opponent adjustment: is there anything there?**
* Time-series: ceiling ≈**0.01 MAE**. A 10-game window is already schedule-balanced, so opponent
  mix largely averages out.
* Pace/coaching: head-to-head is the **only genuinely non-additive mechanism** available, with
  broad coverage.
* Coordinator (me): argued it was potentially the highest-value item.
* Adversarial, unprompted, supplies the decisive complication: **50.1% of level-1 team-games
  already contain a head-to-head meeting inside the trailing window**, contributing an identical
  value to both teams' histories — so own/opponent collinearity *grows* through a season.

I do not resolve this. It is the sharpest disagreement in the set and F5 exists to settle it.
My own prior has moved toward time-series: the mechanism I found most compelling is the one with
the best-argued ceiling against it.

**D2. Is the incumbent's `(a+b)/2` a functional-form error?**
* Pace/coaching: yes — durations partition the clock exactly (verified: 2400.0s, sd 0, 1495/1495),
  so averaging *counts* is a convex-function error with a determinate sign.
* Time-series: the MSE-optimal pair shrinkage at K=10 is **λ\*≈0.546**, so the incumbent's 0.5 is
  near-optimal *by coincidence*, and a naive additive `a+b−μ` will **lose**.

These are compatible: the duration-domain form (F2) is not the additive form time-series rejects.
F2 must be specified as `4800/(d_A+d_B)`, explicitly **not** `a+b−μ`.

**D3. Head-to-head coverage.** Pace measured 70.2%; I measured 85.1%. **Unreconciled.** Neither
figure may be quoted in a task card until the denominators are aligned.

**D4. The roster source doubts its own lane.** It states rosters are shallow and stable and pace
is plausibly more coach-determined, naming coaching identity as the cheapest Category B item
precisely because its own Category A may be measuring the wrong discontinuity. Recorded as an
honest self-assessment that strengthens rather than weakens its output.

---

## 3. Proposed variants — 8 arms plus controls

Family budget, hyperparameters nested. Order is the recommended execution order.

| arm | family | mechanism | stratum | prerequisite |
|---|---|---|---|---|
| **V1** | F1 | count regulation possessions directly; no minute-scaling | 32.8% of windows | **P0-1 resolved** |
| **V2** | F2 | duration-domain combination `4800/(d_A+d_B)` | all | — |
| **V3** | F3 | league-drift re-basing of the prior-season fallback | 183 | — |
| **V4** | F3 | continuous support-weighted blend replacing the discrete ladder | ~570 | — |
| **V5** | F4 | support-scaled shrinkage toward a current-season league mean | 546 | — |
| **V6** | F4 | effective-sample-size window family (length / EWMA / local-level **nested**) | 2,413 | — |
| **V7** | F5 | opponent-tempo asymmetry using lagged opponent history | 85.1% | collinearity probe first |
| **V8** | F7 | roster-weighted bottom-up pace via projected minutes | all | low prior |

**Controls, not arms:** `K0` — the challenger's identical pipeline with zero substantive
features; and the frozen incumbent. Adversarial's warning is decisive here: **an intercept plus a
single `pace_level` dummy removes nearly all stratum bias with zero substantive features.** K0
must therefore be specified to include whatever tier structure the challenger uses, or every
F3/F4 arm will beat a straw control.

---

## 4. Rejected, with reasons

| idea | why rejected | source of the refutation |
|---|---|---|
| Within-game team differentiation | 97.8% of target variance is game-level; residual is near-random | opponent (declined to propose it), time-series, adversarial |
| Garbage-time purge | measured: non-competitive 15.239s vs competitive 15.126s — premise unsupported | opponent |
| Home/away split | league gap 0.17s ≈1.1%, and splitting halves support where MAE is worst | opponent |
| Travel / elevation | elevation spans only 20–2030 ft; likely absorbed by rest | opponent |
| Playoffs-specific arm | already the **best** stratum (MAE 2.422) | opponent |
| Expansion cold start as an arm | **9 rows**; 36 of 45 level-3 rows are non-recurring 2021 left-censoring | roster |
| Additive `a+b−μ` combination | λ\*≈0.546 makes the incumbent's 0.5 near-optimal | time-series |
| **My schedule-gap hypothesis (A6)** | **my own `days_rest` was computed across seasons; 61 of 164 "7+ rest" rows are season openers** | adversarial |
| **My home/away hypothesis (A7)** | subsumed by the above and by the variance decomposition | opponent |
| Changepoint detection | SNR ≈0.37 — will fire on noise | time-series (self-flagged) |
| Post-break rust | expected to fail; kept only as a disambiguating diagnostic | pace (self-flagged) |

---

## 5. Multiplicity plan

* **8 arms across 7 families.** Hyperparameters (window length, EWMA half-life, shrinkage
  constant, blend weight) are **nested inside their family** and cost the family once.
* **Family-level budget.** A family is credited only if its best arm survives; arms within a
  family are not separately counted against the incumbent.
* **Predeclared decision rule, frozen before results:** an arm is promotable only if it (a) beats
  matched K0 on the downstream operational metric, (b) with a **game-clustered** interval
  excluding zero, (c) is stable in sign across every chronological fold, and (d) shows no material
  calibration or coverage regression. All four, not any.
* **Effective n = 1,491.** All intervals game-clustered and paired on identical games.
* **Per-fold zero-variance risk, named by adversarial and to be frozen before results:**
  `pace_level==2` has 0 rows in 2021; `pace_level==3` has 0 rows in 2022, 2023, 2024; playoffs
  have 0 rows in 2026. Fold-level fallback must be specified in advance.
* **The known algebraic trap:** `pace_level > 1` ⟺ `game_no_in_season ≤ 3` **exactly**
  (2982/2982, zero off-diagonal). No design may carry both. In threshold form `feature_gate`'s
  linear rank check may not see it.
* **Possession MAE is the mechanism metric; downstream turnover-team MAE is the decision metric.**
  An arm that improves possession MAE without improving the downstream metric does not win.
* **Honest ceiling.** Time-series bounds the whole Category A programme at ≈**0.10–0.15 possession
  MAE (3.5–5%)**, worth ≈**0.01–0.03 turnovers per team-game**. If the downstream metric must move
  more than that, it cannot come from the possession count at all. This should be stated in the
  task card so the experiment is not judged against an impossible bar.

---

## 6. Category B roadmap — four sources converged on the same top item

**Coaching identity and coaching-change table.** Named independently by the coordinator, pace,
roster and opponent sources as the highest-value missing input. Pace is the most coach-determined
team property; a coaching change is a structural break no trailing window can see; and the table
is **retrospectively buildable** — roughly 90–100 rows of public record, no entity resolution, no
cutoff dispute. It is the only Category B item that could become Category A with bounded one-off
effort.

Then: repair the officials `game_id` join (a data-engineering defect, not an availability one);
a rule-change log to make league-drift correction causal rather than blind extrapolation;
pregame injury capture persisted forward; announced lineups.

**Injury/transaction history exists for the full span** (8,340 rows, 2021-01-07 to 2026-07-29) but
carries **no observation timestamp**, so it stays in Category B on cutoff grounds, not
availability grounds.
