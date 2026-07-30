# W6 "Playing-Through-It" Retrospective — NULL RESULT

*2026-07-30. Experiment `w6_microsignal_retrospective_v1` — preregistered
2026-07-30T17:51:46Z (QUARANTINED, regime B, primary metric `absence_auc`,
incumbent `rest_schedule_minutes_baseline`, thresholds min_improvement 0.02 /
harm_ci_bound 0.01 / per_season_tolerance 0.05). Evaluation recorded on the
ledger win-or-lose as run 1, `eval_time 2026-07-30T18:13:29.927438+00:00`
(`experiments/registry.jsonl`). Reproduce everything:
`python experiments/w6_retrospective/run_w6.py` (add `--record` only for a
new ledger run). Local data only; deterministic (numpy seed 20260730).*

---

## 1. Verdict — say it plainly

**The micro-signal has no detectable retrospective predictive power.
Pooled test absence_auc = 0.503, 90% CI [0.483, 0.524] — statistically
indistinguishable from a coin flip.** The preregistered incumbent-relative
gates *pass mechanically* (pooled dAUC +0.028 >= 0.02; CI low +0.004 >=
-0.01; worst season +0.014 >= -0.05), but only because the boring baseline
is itself *below* chance (0.475) at its preregistered fixed orientation.
Beating an anti-predictive baseline while sitting at 0.50 yourself is not
signal. The registered hypothesis — micro-signal anomalies "precede
documented injury absences **at better than chance**" — is **refuted** on
its better-than-chance clause.

At the preregistered alert threshold (1 alert per 100 player-games on train
years) the challenger detects **4 of 200 absence events (2.0% recall)** at
**5.2% row precision against a 4.5% base rate** (lift ~1.1x). There is
nothing here to operationalize, and per ROADMAP W6 even a strong
retrospective correlation would only ever have been a leaderboard footnote.
**W6 micro-signal v1 is dead, cheaply — which is exactly what the
quarantine queue is for.** `promote: false` on the ledger.

## 2. Design (as executed)

- **Unit/target.** Every player-game actually *played* (master_player row,
  non-null minutes). Label 1 if the player has a `missed_game_injury`
  ground-truth record (`data/injury_history/injury_history.csv` — ESPN
  game-day-final DNP reasons, keyword-classified) within her **team's next
  3 games** of the same season; 0 only when all 3 window games are fully
  observed (played, or ESPN missed_game_* row present). Structurally
  missing ground truth is excluded, not imputed (§5, funnel below).
- **Challenger `microsignal_anomaly_v1`.** Four shifted deltas, each
  short-window (last 5 played games strictly before t) minus expanding
  within-season baseline (all played games before t): FT% (aggregate
  makes/attempts; >=5 window / >=10 baseline FTA), mean stint length
  (`data/derived/stints.parquet`), rim-attempt share (Restricted Area /
  total FGA, shotcharts; >=10 / >=20 attempts), minutes. Each delta z-scored
  on train years 2021-2023 (eligible rows); missing component = 0
  (neutral); **score = -(z_ft + z_stint + z_rim + z_min)**. No fitting
  beyond the z-scoring.
- **Incumbent `rest_schedule_minutes_baseline`.** Fixed a-priori fatigue
  orientation, same z-convention: **z(games_last7) - z(days_rest) -
  z(d_min)** (dense schedule, short rest, declining minutes -> risk).
- **Walk-forward hygiene.** Every rolling quantity `.shift(1)`-ed; features
  reset per season; >=5 prior played games required per row (constitution);
  z-params and alert thresholds computed on 2021-2023 only; evaluation on
  2024/2025/2026 separately + pooled. Both scores evaluated on the
  **identical** eligible row set (gate 5 coverage = equal by construction).

## 3. absence_auc — both scores x three seasons (90% game-date-clustered bootstrap CIs)

| scope | n rows | n pos | dates | **micro-signal AUC** | micro 90% CI | **incumbent AUC** | incumbent 90% CI | dAUC (ch-inc) | d 90% CI |
|---|---:|---:|---:|---:|---|---:|---|---:|---|
| 2024 | 3,697 | 156 | 86 | 0.486 | [0.453, 0.520] | 0.472 | [0.432, 0.514] | +0.014 | [-0.027, +0.057] |
| 2025 | 4,438 | 189 | 102 | 0.505 | [0.469, 0.543] | 0.473 | [0.438, 0.507] | +0.032 | [-0.010, +0.073] |
| 2026 | 2,607 | 141 | 57 | 0.522 | [0.488, 0.555] | 0.491 | [0.456, 0.527] | +0.030 | [-0.008, +0.067] |
| **pooled test** | **10,742** | **486** | **245** | **0.503** | **[0.483, 0.524]** | **0.475** | **[0.453, 0.496]** | **+0.028** | **[+0.004, +0.052]** |
| train 2021-23 (reference) | 9,660 | 361 | 247 | 0.474 | [0.450, 0.498] | 0.462 | [0.436, 0.488] | +0.012 | [-0.016, +0.040] |

Bootstrap: percentile, resampling whole game dates, n_boot 2000, seed
20260730, AUC recomputed per replicate, 0 degenerate replicates.
Team-clustered sensitivity CI on the pooled delta: **[-0.008, +0.059]**
(15 teams) — wider, still above the -0.01 harm bound, still consistent
with ~0. Note the challenger is below 0.5 on its own *train* years — the
tiny positive test delta is not stable structure.

## 4. Threshold metrics (alert threshold = 1 alert/100 player-games on train, per score)

Micro-signal threshold 5.857, incumbent 3.604 (99th percentile of each
score on the 9,660 train rows).

| scope | score | alerts | alerts/100 | false alerts/100 | row precision | events | detected | event recall | median lead (days) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2024 | micro | 60 | 1.62 | 1.60 | 0.017 | 62 | 1 | 0.016 | 8.0 |
| 2024 | incumbent | 101 | 2.73 | 2.73 | 0.000 | 62 | 0 | 0.000 | — |
| 2025 | micro | 28 | 0.63 | 0.56 | 0.107 | 79 | 2 | 0.025 | 6.0 |
| 2025 | incumbent | 107 | 2.41 | 2.39 | 0.009 | 79 | 1 | 0.013 | 7.0 |
| 2026 | micro | 9 | 0.35 | 0.31 | 0.111 | 59 | 1 | 0.017 | 6.0 |
| 2026 | incumbent | 14 | 0.54 | 0.54 | 0.000 | 59 | 0 | 0.000 | — |
| **pooled** | **micro** | **97** | **0.90** | **0.86** | **0.052** | **200** | **4** | **0.020** | **6.5** |
| pooled | incumbent | 222 | 2.07 | 2.06 | 0.005 | 200 | 1 | 0.005 | 7.0 |

Definitions: precision is row-level (alerted rows that were true
label-1); recall is event-level (absence events — player x first absence
game — with >=1 alert among their preceding labeled rows); lead time =
days from first alerting game to the absence date (mechanically bounded
by the 3-team-game window; median 6.5 days on **4 detected events** — too
few to mean anything). Alert-rate drift off the designed 1.00/100
(micro 0.90, incumbent 2.07 on test; incumbent 2.73 in 2024) is
train->test distribution shift in the schedule features — reported, not
corrected.

## 5. Sample accounting (funnel)

| season | played rows | eligible | positives | pos rate | excl: <5 prior | excl: season-end window | excl: roster departure | excl: ESPN gap |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2021 | 3,885 | 2,712 | 101 | 3.7% | 740 | 318 | 115 | 0 |
| 2022 | 4,519 | 3,265 | 117 | 3.6% | 793 | 335 | 126 | 0 |
| 2023 | 4,898 | 3,683 | 143 | 3.9% | 763 | 323 | 129 | 0 |
| 2024 | 4,914 | 3,697 | 156 | 4.2% | 765 | 326 | 126 | 0 |
| 2025 | 5,853 | 4,438 | 189 | 4.3% | 882 | 359 | 174 | 0 |
| 2026 | 4,143 | 2,607 | 141 | 5.4% | 1,027 | 413 | 96 | 0 |

Exclusion rules: season-end truncation applies to positives and negatives
alike (no asymmetric censoring of the base rate); label-0 requires a fully
observed 3-game window; a window game with neither a boxscore row nor any
ESPN missed_game_* row is unobservable (roster departure — waiver, trade,
suspension; 766 rows pooled). The ESPN-gap bucket is empty because ESPN
row coverage of master DNPs is near-total (§7).

## 6. How the comparison was recorded on the ledger (exact mapping)

The registered primary metric `absence_auc` is a **set-level rank
statistic: per-game paired residuals do not exist for it**, so
`compare_to_incumbent()`'s contract (per-game `y_true`/`y_pred`, per-game
loss, delta = per-game loss difference) cannot host it — any per-row
"AUC contribution" pseudo-loss would have changed the metric being gated.
The harness's documented path for evaluations produced outside compare.py
is `registry.evaluate()` / `record_evaluation()` (registry.py docstring:
"One-shot validate + record for evaluations produced outside compare.py").
That is what was used — one evaluation record, run_number 1, carrying:

- the five gates computed **in compare.py's orientation** against the
  preregistered thresholds: delta = challenger_auc - incumbent_auc
  (higher-better, positive = improvement); gate 1 pooled d >= 0.02 ->
  +0.0278 PASS; gate 2 90% clustered-CI low >= -0.01 -> +0.0036 PASS;
  gate 3 worst season d >= -0.05 -> 2024 +0.0144 PASS; gate 4 joint
  forecast -> `not_provided` (this study produces no game forecast);
  gate 5 coverage -> identical eligible row set for both scores
  (1.0, 1.0) PASS;
- 90% CIs from a seeded game-date-clustered percentile bootstrap
  (numpy, n_boot 2000, seed 20260730 — the harness's own conventions),
  recomputing AUC per replicate, paired delta on the same replicates;
  team-clustered sensitivity CI alongside (compare.py mirror);
- per-season AUCs/deltas/CIs, thresholds, funnel, ground-truth
  accounting, regime-B note, the exploratory footnotes, and an
  `interpretation` field stating the null verbatim — **verdict "PASS"
  (gate mechanics) with `promote: false`** and the explicit statement
  that the better-than-chance clause of the hypothesis is refuted.

Nothing was passed through `compare_to_incumbent()`; no pseudo-residuals
were fabricated. Full payload duplicated at `ledger_payload.json`.

## 7. Regime-B coverage report (duties of every B result)

**Ground truth** = ESPN game-summary DNP reasons, keyword-classified
(`missed_game_injury` vs `_other`), game-day-final outcomes
(see `project_docs/INJURY_HISTORY.md`).

**Games covered.** ESPN summaries exist for every completed game
2021 -> 2026-07-29; of 1,489 master games, 1,313 have >=1 resolved
missed_game row (the remainder are games where nobody DNP'd —
not coverage holes). Row resolution: 5,373 ESPN missed_game rows ->
5,354 matched to a master game (all 19 unmatched are Commissioner's Cup
finals, which have no master game by design) -> 5,354 name-resolved
(5,346 exact normalized-name, 8 via unique first+last-token fallback,
0 unresolved).

**Teams covered.** All 15 franchises, expansion teams from their first
seasons (GSV 2025; TOR/POR 2026). `missed_game_injury` rows per
season x team in `coverage_absences_by_season_team.csv` — season totals
321/293/398/340/528/362 (2021 -> 2026); team-season range 1 (LVA 2022) to
88 (IND 2025); rows != episodes (long absences inflate row counts).

**Source coverage cross-check.** Independent master-boxscore DNP reasons
(stats.nba.com) vs the ESPN ground truth: of master DNPs with injury-ish
reasons, ESPN `missed_game_injury` captures 100% (2021), 97.3% (2022),
96.0% (2023), 93.9% (2024), 95.4% (2025), 95.9% (2026). The 4-6% gap is
classification disagreement (reason phrasing straddling the keyword
heuristic), i.e. **a few percent of injury absences are false negatives
in the ground truth**. Only 1 master DNP row in six seasons has no ESPN
row at all.

**Time-of-day coverage: none, by construction.** ESPN summaries are
post-game artifacts; the dataset has no publication timestamps and no
pregame Out/Questionable/Doubtful/Probable states. Used here strictly as
*outcomes*, that is fine; it means this study can never say anything
about *when* on game day the information became known. Regime-B results
apply to the covered subset, nothing wider.

**Systematic missingness — which absence types are invisible?**

1. **Played-hurt games** — the actual W6 phenomenon of interest — never
   appear: if she played, there is no DNP row. The ground truth only sees
   the *endpoint* (sitting), never the "playing through it" state itself.
2. **Season-long/roster absences** (suspended contracts, overseas,
   pregnancy): never on a game-day roster -> no missed_game rows at all
   (visible only on the BBRef transaction wire).
3. **Masked reasons**: COACH'S DECISION / REST / PERSONAL can hide minor
   injuries or load management -> labeled 0 here.
4. **Keyword misclassification** (~4-6% per the cross-check above), plus
   COVID-protocol rows bucketed as injury though they are not
   musculoskeletal precursors.
5. **Cup finals** (19 rows) and preseason: no master join target.
6. **Non-addressable absence starts**: only **32-44% of absence episode
   starts are addressable by any played-through-it detector of this
   class** (player played >=1 of the 3 prior team games *and* had >=5
   prior played games): 44/123, 45/125, 58/181, 61/163, 76/185, 56/128
   for 2021 -> 2026 (`coverage_event_addressability.csv`). The majority
   of absences begin from states this detector cannot score (already
   sitting, early-season, low-tenure players). Recall numbers in §4 are
   *of the addressable events*.

**Micro-signal input coverage** (share of eligible rows with the
component computable, before neutral fill): minutes 100%; stint mean
95-100% (stints.parquet lacks 2022-2024 playoffs — 65 games); rim share
88-90%; FT% 59-66% (the >=5-FTA window bites). Missing components score
0, diluting the composite toward its other terms.

## 8. Audit trail (why this null is believed)

- **Leakage guards**: all rolling windows `.shift(1)`; within-season only;
  z-params/thresholds train-years-only; label window strictly future
  (team games t+1..t+3). Schedule features (days rest, games-in-7) use
  only game dates known pregame.
- **AUC implementation** unit-tested against hand-computed values incl.
  tie handling; bootstrap deterministic (seed 20260730; re-run reproduces
  every digit).
- **Label spot-checks** against the independently validated cases in
  `INJURY_HISTORY.md`: Ogwumike SEA 2024 (played 05-30, missed 06-04 eye
  injury -> her 05-30 row labels 1 with the right absence date;
  post-return rows 0); Jefferson CHI 2025 (2 appearances before injury ->
  correctly excluded as insufficient history). Ground-truth name/game
  match rates §7.
- **Per-component AUCs** (test pooled, component-available rows only,
  hypothesized orientation): FT% dip 0.530, stint shortening 0.506,
  rim-share decline 0.506, minutes decline **0.489 — wrong direction**
  (players about to sit average *more* minutes vs baseline, +0.19 vs
  +0.09 for negatives). The incumbent's fatigue orientation is backwards
  empirically too: positives have *more* rest (AUC 0.514 for +rest) and
  *fewer* games-in-7 (0.480) — being rested/managed correlates with
  sitting soon, the opposite of the fatigue story. That is why the
  incumbent lands below 0.5. Preregistered orientations were fixed a
  priori and were not flipped after seeing results.

## 9. Exploratory footnotes (post-hoc, not gate inputs)

- **Horizon-1 only** (absence in the very next game vs clean negatives):
  micro 0.511, incumbent 0.474 (n=10,407, 151 pos) — no hidden
  short-horizon signal.
- **FT%-dip alone**: 0.530 on the 6,652 rows (354 pos) where computable;
  0.515 with neutral fill. A whisper, far from useful, and it would need
  its own preregistration to be anything more than a footnote.

## 10. What would actually move W6 (if it is ever revived)

Not more retrospective signal-mining on this ground truth. The binding
constraints are (a) the ground truth cannot see playing-hurt states, only
absences, (b) two-thirds of absence starts are non-addressable, and
(c) the candidate signals are chance-level. If W6 returns, it should be
prospective: the 2026-07-30 live capture (official injury report with
Q/D/P designations + timestamps, `project_docs/INJURY_CAPTURE.md`)
accumulating into a regime-D corpus where "listed Questionable, played
anyway" gives real played-hurt labels — the label this study never had.

## 11. Files

| file | contents |
|---|---|
| `run_w6.py` | full reproducer (dry run by default; `--record` appends to the ledger) |
| `auc_results.csv` | §3 table (all scopes, both scores, CIs, bootstrap params) |
| `threshold_metrics.csv` | §4 table |
| `label_funnel.csv` | §5 funnel |
| `labeled_universe.csv` | every eligible row: ids, dates, label, absence link, raw deltas, schedule features, both scores |
| `component_availability.csv` | §7 micro-signal input coverage |
| `coverage_absences_by_season_team.csv` | ground-truth injury rows per season x team |
| `coverage_source_by_season.csv` | master games vs games with ESPN DNP rows |
| `coverage_master_dnp_crosscheck.csv` | ESPN capture rate of master injury-ish DNPs |
| `coverage_event_addressability.csv` | absence episode starts vs addressable events |
| `zscore_params.json` | train-year z means/stds + alert thresholds |
| `ledger_payload.json` | exact results dict recorded on `experiments/registry.jsonl` (run 1) |
