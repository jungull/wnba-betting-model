# Incumbent mapping audit — what registered control exists per contract target

*Originally written 2026-08-01 at commit `5b2e49b`, published at `40b87c0`. Authorised by the
Codex supervisor as a bounded **discovery** task: reproduce and map the existing registered
control from committed code. **No new mapping is registered here, no model is chosen, no
prediction is regenerated, and no accuracy metric is computed.** Where several plausible
components exist, they are listed and the conflict explained rather than resolved by judgment.*

> **CORRECTED 2026-08-01, after supervisory review of `40b87c0`.** The original headline —
> *"one of five targets has an exact existing control"* — was **too permissive**. It classified
> targets on **estimand shape alone**. Under the **full contract** (prediction obligation,
> target support, uncertainty fields, cutoff policy, candidate universe, and cold-start
> coverage) the correct count is **zero exact full-contract controls and five semantic
> mismatches**. Every correction below is matched to a committed artifact; three claims made in
> the supervisory correction itself did not survive that check and are recorded in
> [Corrections carried back to the supervisor](#corrections-carried-back-to-the-supervisor).
>
> Superseded statements are struck through rather than deleted. Nothing here computes,
> inspects, or regenerates a prediction, a fitted parameter, or an accuracy metric.

## Summary — corrected

| contract target | corrected classification | reusable ingredient |
|---|---|---|
| `p_active` | **SEMANTIC_MISMATCH** | registered Stage-A logistic comparator; live deterministic Out gate as a *separately named* comparator |
| `e_minutes_given_active` | **SEMANTIC_MISMATCH** | promoted shifted minutes EWMA α=0.30 — an exact **point-estimator ingredient**, not an exact control |
| `attempts_usage` | **SEMANTIC_MISMATCH** | the volume screen's per-target FGA/36 baseline (see the caveats — it is *named*, not separately registered) |
| `player_scoring_distribution` | **SEMANTIC_MISMATCH** | points/36 EWMA α=0.30 × expected-minutes point projection |
| `team_game_distribution` | **SEMANTIC_MISMATCH** | promoted calibrated home/away score centers; frozen live Gaussian **margin** distribution |

**Zero of five targets has an exact full-contract control. All five need a contract
wrapper/specification.**

~~One of five targets has an exact existing control. That is the finding.~~

The five ingredients are genuinely reusable, but **no existing artifact can be emitted
unchanged as a contract-compliant arm.**

---

## The live player layer (the authoritative "current" layer)

`daily_forecast.py:640` `player_layer()` is what `freeze-v0` actually runs in the prospective
log. Its own docstring: *"Recency dressed roster + minutes EWMA(0.30) + the Phase-3 rule gate:
latest captured designation 'Out' at the cutoff => excluded. **Informational only in v0: never
modifies the team forecast.**"*

| constant | value | provenance |
|---|---|---|
| `MINUTES_ALPHA` | **0.30** | `daily_forecast.py:112`, comment: *"promoted: minutes_ewma_vs_carryforward_v1"* |
| `RECENCY_GAMES` | **3** | `daily_forecast.py:120`, *"MINUTES_MODEL_SPEC §5 recency roster window"* |
| `SIGMA_V0` | **12.9022** | `daily_forecast.py:113`, *"frozen margin sigma: dist_margin_cover_v1"* |
| input | `data/masters/master_player.parquet` | `daily_forecast.py:107` |

Note the live recency window is **3** games; `prediction_contract_v2` uses **5**. Both are
recency-roster proxies of the same family, but they are **not the same universe**. Recorded as
an ambiguity, not reconciled here.

The live EWMA is computed over history filtered to `game_date < slate_date`
(`daily_forecast.py:648-649, 673-679`) on rows with `minutes > 0`, and emits
`min_ewma: None`, `cold_start: True` when a player has no played history — a **flag, not a
prediction**.

---

## `p_active` — SEMANTIC_MISMATCH

**Two candidate components, neither usable as a contract-compliant control.** Both are
reusable ingredients.

1. **The live rule gate** (`player_layer`, `daily_forecast.py:640-690`). Deterministic: if the
   latest captured designation at the cutoff is `Out`, the player is excluded; otherwise
   available. This is a **binary exclusion rule, not P(active)**. It emits no probability and
   has no uncertainty. It is also *informational only in v0*. It may be reported as a
   **separately named deterministic comparator** and must **never** be relabelled as a
   probability.
2. **`minutes_twostage_availability_v1` Stage A** — L2 logistic P(plays), producer
   `minutes_twostage.py`. A genuine probability, and a **reproducible non-promoted
   comparator** — *not* an incumbent, and *not* a component that "failed its gate".

### Correction 1 — Stage A did not fail a gate; it was never gated

~~The only genuine P(plays) is Stage A of `minutes_twostage_availability_v1`, whose
`gate_verdict.json` records verdict FAIL and promote false.~~ That conflates Stage A with its
parent. The artifact-supported account:

- **Stage A was never gated.** `experiments/registry.jsonl` (record
  `minutes_twostage_availability_v1`) registers metric M2 as *"**SECONDARY, recorded not
  gated**: Stage-A pooled Brier on M2_dressed vs shifted expanding played-rate prior."* In code
  the M2 comparison runs with `record=False` (`minutes_twostage.py:951`).
- **Stage A met its preregistered secondary bar.** `secondary_results.json:35-36`:
  `"preregistered_bar": "improvement >= 0.005 and CI excludes degradation"`, `"bar_met": true`.
  Pooled Brier **0.07963** vs the shifted expanding played-rate prior **0.10845**, improvement
  **+0.02882**, 90% date-cluster bootstrap CI **[+0.02667, +0.03120]**.
- **The parent experiment failed its PRIMARY gate.** `primary_metric: minutes_mae`;
  `gate_verdict.json:87-91` records `"verdict": "FAIL"`, `"promote": false`,
  `"failed_gates": ["gate1_pooled_improvement"]` — pooled Stage-B minutes-MAE improvement
  **+0.0370** against a required **+0.10**. Gates 2, 3 and 5 passed; gate 4 is `null`.
- Because `promote: false`, no incumbent replacement occurred; the registered `incumbent_id`
  remains `minutes_ewma_alpha030_v1`.
- Separately, **M3** (the p × m product) recorded `bar_met: false`
  (`secondary_results.json:70-71`). That is a secondary bar on the *product*, not on Stage A's
  probability, and it is not a gate either.

**Correct label:** a **registered, reproducible, non-promoted Stage-A logistic comparator whose
preregistered secondary Brier bar was met**, inside a parent experiment that failed its primary
minutes-MAE promotion gate.

### Correction 2 — the coverage figure, and the universe it belongs to

~~It applies only to the covered subset.~~ False. Stage A scores its whole universe and reports
availability coverage as a *split within* it.

| quantity | value | artifact |
|---|---|---|
| Stage A (M2) rows scored | **16,323** | `secondary_results.json:87` `m2_universe_n`; `test_predictions_m2.csv` has 16,323 data rows |
| Stage A rows with `has_avail=True` | **5,892** (~36.1%) | counted from `test_predictions_m2.csv`, written at `minutes_twostage.py:1150-1153` |
| *M1 played* universe rows | 13,501 | `regime_b_coverage.csv` (4,356 + 5,225 + 3,920) |
| *M1 played* covered rows | **3,505** | `minutes_twostage.py:1016`; `REPORT.md:64` *"Missingness split (M1 test): covered rows 3,505"* |

**3,505 is the covered count in the M1 *played* universe (3,505 / 13,501), not in Stage A's.**
Pairing "16,323 scored" with "3,505 covered" mixes two universes. Stage A's own coverage is
**5,892 / 16,323**.

On "uncovered rows reported separately": a covered-vs-uncovered **MAE** split exists only for
M1 (`secondary_results.json:142-149`). For Stage A the only split reported is the **played
rate** — `covered_played_rate_M2: 0.6118` vs `uncovered_played_rate_M2: 0.9586`
(`secondary_results.json:148-149`). **There is no covered-vs-uncovered Brier split anywhere.**

### Why it is still a mismatch under the full contract

- **Universe.** Registered as `M2_dressed`: *"dressed rows (played + `dnp_reason` set), >=1
  prior same-season dressed appearance"* (`registry.jsonl`; code `minutes_twostage.py:817`
  `m2 = D["prior_dressed"] >= 1`). The contract universe is the pregame recency-roster
  candidate set of **35,615 rows** and requires a prediction for **every** candidate. Rows below
  the >=1-prior-dressed threshold are never scored, so Stage A has **no cold-start path**.
- **Cutoff.** `decision_time: T-24h`, day-precision rule `record_date <= game_date - 1 day`.
  The contract is T-90m on 407 exact-tip games and prior-day 18:00 UTC on 1,088 date-only games.
- **Fitting.** λ = 31.622777, tuned by 3-fold inner walk-forward strictly inside 2021-2023, then
  **fit once and frozen** for all test seasons. The contract requires refitting **within each
  training fold**.
- **Uncertainty.** `logistic_fit` returns only `beta`; the IRLS Hessian
  (`minutes_twostage.py:553`) is discarded. Admissible for `p_active` — where the contract
  treats the probability itself as the uncertainty — but no covariance is available for any
  downstream composition.

## `e_minutes_given_active` — SEMANTIC_MISMATCH

~~EXACT_EXISTING_CONTROL. This is the one clean case.~~ **Downgraded.** The estimand matches;
the contract obligations do not. `minutes_ewma_vs_carryforward_v1` is an exact **point-estimator
ingredient**, not an exact control.

What is confirmed and reusable:

- `experiments/minutes_baselines/gate_verdict.json`: **`verdict: PASS`, `promote: true`**,
  challenger MAE 4.6428 vs incumbent 5.3913, pooled improvement +0.7485, n = 13,501.
- α = **0.30** (`REPORT.md:26`; `alpha_tuning_curve.csv` argmin `mean_val_mae` 4.755807 at 0.30),
  tuned on 2021-2023 inner folds only, frozen, and carried into production as `MINUTES_ALPHA`
  (`daily_forecast.py:112`).

Why it is nevertheless a mismatch:

- **Universe** (`minutes_baselines.py`): `season_type == "Regular Season"` (`:115`) — **playoffs
  are excluded entirely**; `minutes > 0` (`:119, :123`); and `prior_apps >= 1` (`:623`) where
  `prior_apps` is a `cumcount()` grouped by `(player_id, season)` (`:154-156`), i.e. **>= 1
  prior same-season *played* appearance**. `REPORT.md:472` explicitly disclaims the higher tier:
  *"spec D5's >= 3-appearance cold-start tier is a model-phase rule, not part of this
  preregistered floor."*
- **Obligation.** Because the universe is built from played rows, an eventual DNP can never be
  predicted *or* scored. Its scored universe is 13,501 rows against the contract's 35,615
  required.

  > **WORDING CORRECTED 2026-08-01** (supervisory review of `db9f011`). This bullet previously
  > quoted the contract's warning that *"an arm cannot buy coverage by dropping the inactive"*
  > and then asserted **"this artifact buys coverage exactly that way."** That sentence is
  > **withdrawn.** The warning governs an arm answering the contract; `minutes_baselines` is not
  > such an arm. It was registered against a **legitimate played-only estimand** — E[minutes] on
  > rows where the player played — predates `player_game_contract/2`, and never claimed contract
  > coverage. It did not evade an obligation it was never under.
  >
  > The accurate and narrower statement — the one that actually blocks reuse — is that its
  > **coverage figure is conditional on an already-filtered frame and therefore cannot establish
  > contract prediction coverage.** A coverage of 1.0 over played rows with >= 1 prior appearance
  > is silent about the 22,114 contract rows outside that frame. See the gate-5 circularity
  > bullet below, which makes the same point about the same number.
- **Cold start.** `:169-175` asserts NaN features on every `prior_apps == 0` row and `:623`
  deletes them. Production has the same hole (`daily_forecast.py:678-683`: `min_ewma: None`,
  `cold_start: True`).
- **Gate-5 coverage of 1.0 is circular** — `:679-680` computes coverage over the already-filtered
  frame (`REPORT.md:519`: *"all three baselines predict every eligible row by construction"*).
  It measures nothing about slate coverage.
- **Uncertainty.** No predictive SD. `test_predictions.csv` carries no sd/sigma/quantile column;
  `minutes_baselines.py` has zero matches for `pred_sd|quantile|sigma|std(`; the comparison is
  MAE-only (`:699`). The contract requires *"predictive sd of minutes, strictly > 0"*.
- **Cutoff.** Registered `decision_time: T-24h`; contract rows are T-90m or date-only.
- **Provenance gap.** α appears **nowhere** in the registry entry or `gate_verdict.json`. Its
  only machine-readable provenance is `alpha_tuning_curve.csv` plus prose in `REPORT.md`. The
  registered record does not pin the promoted hyperparameter.

## `attempts_usage` — SEMANTIC_MISMATCH

~~NO_REGISTERED_CONTROL. No registered component predicts field-goal attempts.
`player_volume_heterogeneity_v1` is VOID and certifies nothing.~~ **Reclassified.** The VOID
verdict does not erase the per-target baseline, but the baseline is weaker than the supervisory
correction assumed — see [Corrections carried back](#corrections-carried-back-to-the-supervisor).

What actually exists:

- `experiments/registry.jsonl` (`player_volume_heterogeneity_v1`) carries
  `"incumbent_id": "player_volume_ewma_baseline"` — **one experiment-level field covering all
  four targets**, not an FGA-specific component. The only per-target baseline language is in
  `features_desc`: *"Baseline per target: shifted per-player EWMA of that target, alpha tuned on
  inner folds."*
- **`player_volume_ewma_baseline` has no registration record of its own.** It appears in the
  ledger only as the `incumbent_id` *field* of that experiment and its two evaluations. There is
  no `kind: "component"` record, no thresholds, no promotion. It is a **screen-internal
  reference baseline named in a field**, not a separately registered predictive component.
- **What the report selected is `ratio_ewma`, not EWMA-of-rate.** `REPORT.md:30`:
  `| shot attempts / 36 | ratio_ewma | 0.05 | 3.295344 |`. Per `volume_heterogeneity.py:181-185`
  these are *distinct* estimators: `ewma_target` = shifted EWMA of the rate itself;
  `ratio_ewma` = shifted **ratio-of-EWMAs** of (fga, minutes) × 36. Both are strictly shifted,
  so "shifted EWMA family" is loosely true, but the shifted EWMA *of FGA/36* is the **losing**
  encoding here.
- **α = 0.05 is a grid-boundary corner.** `ALPHA_GRID = np.arange(0.05, 0.501, 0.05)`
  (`feature_lab.py:72`) and the fga36 curve is **monotonically increasing** across all ten points
  (3.295344 at 0.05 → 3.625096 at 0.50, `baseline_alpha_curves.csv:22-31`). The minimising α is
  **unidentified** and lies at or below the grid floor.

**Scope of the VOID.** `screening_protocol_amendment_v3` states it precisely: *"Screens found
resolution-limited have their **nulls** VOIDED (they certify nothing) while their **EFFECT SIZES
and detection limits remain valid and reportable**."* So the VOID applies to the screen's
1,368-test null, **not** to the baseline. But that is not a licence either: the screen's
`primary_metric` is `volume_mae_delta_2024`, a **delta against** the baseline, so the baseline's
own inner-fold MAE is a tuning artifact that was **never gated**.

Why it is a mismatch:

- **Target support.** The registered target is **FGA per 36 minutes**, a rate
  (`volume_heterogeneity.py:106-109, 136-137`). The contract's `attempts_usage` is *"Field-goal
  attempts conditional on appearing"* — a **raw count**. Converting rate → count requires a
  minutes forecast the baseline does not supply; **composing them would be new**.
- **Coverage.** `feature_lab.py:200` gates on `minutes >= 8.0` **and** `prior_apps >= 5`
  (same-season), plus non-null on all four point channels. Universe = **11,948 rows**,
  regular-season played rows, **2021-2024 only** (2025/2026 quarantined). First row of each
  player-season is NaN and silently dropped (`volume_heterogeneity.py:168`).
- **Uncertainty.** None. No sd/quantile column anywhere; no per-row baseline predictions are
  committed at all.
- **Cutoff.** No baseline-specific cutoff exists; the experiment's is `T-24h`.

No other registered component forecasts player field-goal attempts. A programmatic scan of all
86 ledger records for `fga|field.goal.attempt|shot.attempt` returns only this experiment and
`bottomup_3pt_channel_v1`, whose `fga3_per_min` EWMA is an **internal input to a team-level 3pt
channel forecast**, not a player FGA forecast. The one module that *does* emit an FGA prediction
— `arm_incumbent.py:200`, α=0.25, with an sd borrowed from points × 0.5 — is **unregistered and
REJECTED**.

## `player_scoring_distribution` — SEMANTIC_MISMATCH

`props_edge_v1` defines the projection as *"per-36 points-rate EWMA (alpha=0.30 frozen family) ×
expected minutes (minutes EWMA alpha=0.30)"*. Confirmed at `props_edge.py:203, 312, 316-319,
350`: both legs use α = 0.30, `adjust=True`, and the estimator is
`per36_after * min_after / 36.0`.

Mismatches, with the universe and cutoff now recorded explicitly:

- **Point projection only** — no sd, no quantiles (`props_edge.py:349-353` emits `proj` and
  `exp_min`). The contract requires *"predictive sd PLUS the named quantiles"*.
- **Universe: >= 3 prior same-season *played* appearances** — `props_edge.py:204`
  `MIN_PRIOR = 3`, enforced at `:349-353`, rows dropped at `:613`. Unlike the minutes baseline,
  playoffs are **not** excluded (groupby key is season only).
- **Prop-line rows only** — `:398/:427` `market_key == "player_points"`, `:389` `line.notna()`.
  A player with no posted line is never projected. Attrition ladder
  (`experiments/props_edge/accounting.json`): 36,946 → 33,610, dropping 556 name-unresolved,
  915 zero-prior, **1,865 with 1-2 prior appearances**.
- **Registered as a MEASUREMENT STUDY** whose `incumbent_id` is `prop_line_at_neartip`, i.e. the
  market, with sentinel thresholds. Not a promoted forecasting model. Its own headline result:
  projection MAE 5.2440 vs line MAE 4.9321 — **projection worse by +0.3119** (90% CI +0.2680 to
  +0.3554), losing in every slice.
- **Conditionality is unstated**; the contract asks for points conditional on appearing.

### Correction 3 — the T-90m claim does not survive

~~`props_edge_v1` (`decision_time: T-90m`) is the only component whose cutoff matches the
contract.~~ **True of the registry label, false of the artifact.**

- `props_edge.py` contains **no 90-minute cutoff logic anywhere**; the label is unenforced
  metadata.
- Line vintage: `historical_props_backfill.py:66` `SNAP_LEAD_MIN = 65`, applied at `:216`.
  Measured on the delivered table over 784 games: median **69.4 min** pre-tip, mean 69.3.
  **0.0% of games fall in the 85-95 min band; 98.1% fall in 60-70 min.** The lines carry
  information from ~21 minutes *after* the registered decision time.
- The projection side has **no time-of-day cutoff at all** — `project_targets` (`:342-346`) is a
  `merge_asof` on **dates** with `allow_exact_matches=False`. That is a *date-level* gate,
  closer to the contract's `date_only_prior_day_cutoff` than to T-90m.
- Under contract v2's fail-closed rule (`prediction_contract_v2.py:235`,
  `observed_at < tip - 90m`), only **2 of 784** props observations qualify, and
  `game.parquet` `tip_time_source` shows `props_historical` supplying just **2** exact tips
  against `odds_extension`'s 405.
- Exact-tip availability by season is **0/209 (2021), 0/239 (2022), 0/260 (2023), 0/262 (2024),
  197/310 (2025), 210/215 (2026)** — so contract v2 can certify **zero** exact-tip games in
  2024, one of `props_edge_v1`'s study seasons.

T-90m therefore matches only the exact-tip rows *of other sources*, and date-only rows are a
distinct contract policy.

## `team_game_distribution` — SEMANTIC_MISMATCH

Contract target: **team points** distribution with a per-team predictive sd.

### Correction 4 — there is no total distribution

~~Margin and total distributions exist; team points does not.~~ The summary line was wrong on
the total. **The total is a point forecast.** (The body of the original document was already
correct at `:124-125`; only its summary table overstated.)

- **`totals_head_v1`** — `primary_metric: total_mae`; the challenger is
  `a * structural_uncal_total + b + c * league_env_dev`, a **mean function only**.
  `gate_verdict.json`: `promote: false`, `verdict: FAIL`, three failed gates,
  `pooled_improvement: -0.1641`. `game_level_totals.csv` has no sd, sigma or quantile column.
  Its `dispersion_diagnostics` are SDs *across games* of the prediction and outcome series, not
  per-game predictive SDs.
- **`totals_online_correction_v1`** is also a point correction and also failed
  (`promote: false`, two failed gates). Its `correction_distribution.csv` summarises corrections
  *across* games — a diagnostic, not a per-game predictive total distribution.
- The live record carries `"total": 171.316` with **no** accompanying sigma, in contrast to
  `"margin": 7.899` + `"margin_sigma": 12.9022`. `FREEZE_PROPOSAL_v0.md:29` freezes exactly one
  distribution — margin. There is no total row.

### What does exist, recorded accurately

- **A frozen live Gaussian *margin* distribution.** `daily_forecast.py:113`
  `SIGMA_V0 = 12.9022  # frozen margin sigma: dist_margin_cover_v1`, applied at `:1109-1117`.
  Sigma provenance: `summary.json` `pool_std_ddof1 = 12.902156605139535`, the std of 610
  train-year (2021-2023) calibrated margin residuals. It is frozen via `prospective_v0` /
  `freeze-v0` (`FREEZE_PROPOSAL_v0.md:29`), **not** via a gate PASS, and it is live in the real
  chain — every `forecasts/forecast_log.jsonl` record carries `"margin_sigma": 12.9022`.
- **`dist_margin_cover_v1` failed, but note what failed.** `gate_verdict.json`:
  `promote: false`, `verdict: FAIL`, `failed_gates: ["gate1_pooled_improvement"]`,
  `pooled_improvement: -7.7159e-05` against `min_improvement: 0.05`. The **empirical-quantile
  challenger** failed to beat the **Gaussian incumbent** (`gaussian_train_sigma_baseline`). The
  Gaussian was not refuted — it was not improved upon. Either way this is a distribution of
  **margin**, not team points.
- **Promoted calibrated structural home/away point centers.** `chanreval_2026_structural_repaired`
  evaluates to `promote: true`, `verdict: PASS`, all five gates true,
  `pooled_improvement: 0.6299`. Per-side scores were gated inside gate 4 (`joint_check`:
  home_score challenger MAE 8.7928 vs incumbent 9.2234; away_score 8.6163 vs 9.0853). The
  calibrations are two-parameter linear **mean** maps
  (`str_home: [27.4922, 0.6765]`, `str_away: [30.2931, 0.6235]`).
  `predictions_v2.csv` carries `str_home_cal` / `str_away_cal` and **no sd, sigma or quantile
  column of any kind**. The nearest thing to dispersion is a 4×4 **channel-level** in-sample
  residual covariance — a diagnostic over channels, not per-team-game, not emitted with any
  prediction, and never turned into a predictive team-points SD by any gate or registration.

**Does any committed artifact emit a per-team points predictive sd or quantiles? No.** The only
per-game distributional artifact in the repo is `dist_margin_cover/game_level_dist.csv`, whose
`sigma` / `q05..q95` are on the **margin** scale. The only arm emitting `pred_sd`/`pred_q*` at
all is `arm_incumbent`, which emits **no** team target (`target_key` counts: four player targets
at 35,615 each, `team_game_distribution` absent) and is **REJECTED**.

A team-points distribution could be derived from a margin distribution plus a total, but the
total has no sigma — so that derivation is a **new specification**, not an existing control.

---

## Commit-scope contamination in `40b87c0` — labelled, not erased

`40b87c0` was staged with a broad `git add data/ logs/`. It therefore swept in **concurrent
W1/news capture output that has nothing to do with the mapping conclusion**. Those records are
genuine prospective capture and are **preserved**; the pushed commit is **not** rewritten.

| swept-in artifact | rows | stamp | character |
|---|---|---|---|
| `data/news_capture/news_items.csv` | **83** | all capture batch `20260801T154504Z` | genuine news-capture output, 5m18s before the commit |
| `data/w1_extractions/extractions.jsonl` | **27** | all `extracted_utc = 2026-08-01T15:46:10Z` | **all 27 carry `skip_reason: duplicate_title`** — deduplication records, across 11 `gnews_*` sources |

The commit itself is timestamped `2026-08-01T15:50:22Z`. Neither artifact was produced by,
consumed by, or referenced in the mapping audit; **no conclusion in this document depends on
them.** The same capture cycle continued past the commit (a further 234 extraction records
spanning 15:46:19Z-15:57:20Z, 60 CSV rows, and `raw/run_20260801T154617Z.jsonl`), which is why
the working tree was dirty at review time.

**Process correction, effective now: stage explicit paths. Capture artifacts get their own
named commit and never ride along with an analysis commit.** Note also that `.claude/` is
**not** in `.gitignore` and now contains git worktrees — `git add -A` or `git add .` from the
repository root would commit them. Explicit-path staging is therefore load-bearing, not a
style preference.

---

## Corrections carried back to the supervisor

Three claims in the supervisory correction of 2026-08-01T16:05Z did not survive artifact
verification. They are recorded here because the charter requires every factual claim to match
a committed artifact.

1. **Stage A coverage.** The correction states Stage A *"scored 16,323 rows, with 3,505
   availability-covered."* The row count is right; **3,505 belongs to the M1 *played* universe
   (3,505 / 13,501)**. Stage A's own coverage is **5,892 / 16,323**. The correction is also
   stronger than "not simply failed its gate": Stage A was registered *"SECONDARY, **recorded
   not gated**"* and run with `record=False` — it was never gated at all.
2. **The FGA/36 baseline.** The correction states `player_volume_heterogeneity_v1` *"explicitly
   registered `player_volume_ewma_baseline` for FGA/36"* and directs registering *"shifted
   FGA/36 EWMA alpha 0.05"*. In the ledger, `player_volume_ewma_baseline` is only the
   **experiment-level `incumbent_id` string**; it has **no registration record of its own**.
   And the report selected **`ratio_ewma`** (shifted ratio-of-EWMAs of fga and minutes), which
   is a *different* estimator from the shifted EWMA of the FGA/36 rate. α = 0.05 is the
   **first point of the swept grid** on a **monotonically increasing** curve, so the minimising
   α is unidentified and lies at or below the grid floor. **A supervisory ruling is requested**
   — see the open questions frozen in `contract_baseline_suite_v1`.
3. **`props_edge_v1` at T-90m.** The correction says T-90m *"matches only exact-tip rows"*. It
   is weaker than that: `props_edge.py` has **no cutoff logic at all**, its line vintage is
   median **T-69.4m** (0.0% in the 85-95m band), and its projection gate is **date-level**.
   Under the contract's fail-closed rule only **2 of 784** props observations qualify, and
   **0 of 262** 2024 games have a certifiable exact tip.

A fourth, minor: the ledger's *"28/28 artifacts attested"* was stale, and `MISSION_LEDGER.md:320`
said "8 checks" where line 322 said "9/9" — 8 is the `--quick` count, 9 the full count. Both are
corrected, and current gate evidence is committed at `project_docs/GATE_LOG_2026-08-01.md`.

---

## Unresolved items, for the specification decision

1. **Recency window disagreement**: live layer 3 games, contract 5.
2. **Cutoff disagreement**: the promoted minutes control is registered at T-24h; the volume
   screen at T-24h; `props_edge_v1` is labelled T-90m but is effectively date-level with
   ~T-69m lines. Contract rows are T-90m (407 games) or date-only (1,088 games).
3. **Shift semantics**: the live EWMA filters history to `game_date < slate_date` rather than
   calling `.shift()`. The two coincide for a strictly-prior history, but the equivalence should
   be confirmed by reproduction rather than assumed.
4. **`p_active` has no promoted probabilistic control at all.**
5. ~~Three of five targets need a decision before any arm can claim to be "the incumbent".~~
   **All five targets need a contract wrapper/specification.** No existing artifact is
   emittable unchanged. This is what `contract_baseline_suite_v1` freezes.

## Statement of scope

No accuracy metric was computed. No predictions were regenerated. No fitted parameter was
produced. The historical gate verdicts, registrations and reports quoted above are
**pre-existing committed development evidence** read to verify claims about themselves, as the
charter requires — not new results. `experiments/arm_incumbent` remains rejected and unconsumed.
Evidence labels unchanged: `calibrated_prob_edge_v1` NEGATIVE, mechanism label A,
harmful-controls an uncorrected diagnostic lead, `freeze-v0` untouched.
