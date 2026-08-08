# I0009 — R² convention re-run (E1 re-measurement)

**NON-CLAIMING (GRAPH_POLICY 13.1).** No registry entry, no preregistration, no leaderboard row,
no promotion. Output is a LEAD verdict only.

**Partition: 2021–2024 ONLY.** Verified on `season` column values and `game_date.dt.year` values
for all four input CSVs (no byte/regex scan — that check has produced false hits twice in this
program). 2025/2026 were never read, joined, described or summarised.

**Write scope honoured.** Every file created lives in
`experiments/exploration/E1_I0009_r2_rerun/`. The frozen screens `E0_I0009_additive_pressure`
and `E1_I0009_additive_pressure` were read and copied from; neither was modified. No write to
`registry.jsonl`, `DECISION_LEDGER.jsonl`, `GRAPH_EVENTS.jsonl` or `idea_log.jsonl`.

---

## 0. The premise was half wrong, and the half that was wrong is the important half

I was sent to fix an *understatement*. What I found is an *overstatement*.

D069 is correct that `E0_I0009_additive_pressure/analyze.py` carries a defective weighted-R²
helper. `wls_r2` sits at lines 40–48; line 47 is the defect:

```python
sst = float(((yw - yw.mean()) ** 2).sum())     # yw = sqrt(w) * y
```

It feeds `delta_r2` (lines 55–62) and therefore every dR² E0 published.

D069 is **not** correct that E1 carries it into its published numbers. `E1_.../analyze.py` has no
function named `wls_r2`. Its headline helper is `r2_in` at lines 68–72, which is already the
standard weighted R²:

```python
ybar = np.average(yy, weights=ww)
return 1.0 - np.sum(ww * r ** 2) / np.sum(ww * (yy - ybar) ** 2), b
```

and its out-of-sample helper `oos_delta` (lines 281–301) uses the standard weighted SST about the
**train** weighted mean. The defective form survives in E1 only inside `delta_r2_e0convention`
(lines 220–228), whose entire job is to reproduce E0's published figures as a frame-identity check.
It touches no E1 headline number. E1's own note at lines 239–248 says as much explicitly.

**So the headline +0.004003 was never a defective-convention number, and fixing the SST does not
raise it.** What actually moves it is the *other half* of the adopted convention — dropping the
possession weights — and that moves it **down by 79%**.

---

## 1. Weight and centering audit (the thing that governs the bias)

| | value |
|---|---|
| weight variable | `realised_off_possessions` |
| min / max | 1.0 / 95.0 |
| mean / sd | 42.672 / 21.205 |
| CV | 0.4969 |
| max/min ratio | **95×** |
| response | `turnovers_per_100_off_poss` |
| mean / sd | 3.3957 / 3.9884 |
| mean-to-sd ratio | **0.8514** |
| centered? | **no** (strictly non-negative rate) |
| corr(y, √w) | −0.0496 |

Both governing factors are present and both are substantial, so a non-trivial conservative bias
was predicted before measuring.

### Prediction, stated before measurement

SSE is identical under both conventions, so for any model comparison fitted on the same rows

```
dR2_defective / dR2_standard  ==  SST_standard / SST_defective     (exactly)
```

which is computable from `y` and `w` alone. Predicted pooled ratio **0.924644**, i.e. reported dR²
**7.5356% below** standard. Per season: −5.7706% (2021), −5.2362% (2022), −8.7755% (2023),
−9.7585% (2024).

### Measurement

Measured pooled bias **−7.535579%**; per season −5.770599 / −5.236181 / −8.775505 / −9.758531.
Max discrepancy between prediction and measurement: **5.04 × 10⁻¹² percentage points.** Exact match.
The mechanism is confirmed, and every figure sits inside the predicted 0–25% band.

### One correction to D069's wording

D069 says the ratio is *exactly* 1.0000 if the response is centered. It is not, quite. Exact
cancellation needs **both** `sum(w·y) = 0` and `sum(√w·y) = 0`; centering y at its unweighted mean
delivers only the first. Measured on this frame, centering takes the ratio to **0.99931**, not
1.00000 — it removes 99.1% of the bias, not all of it. Uniform weights **do** give exactly
`1.0000000000`. Of D069's two stated escape hatches, only the uniform-weight one is exact. This
does not change any of D069's conclusions; it just means the second condition is asymptotic rather
than algebraic.

---

## 2. Reproduction first (step 2)

Both screens' helpers were copied **verbatim** and run on copies of their own frozen CSVs.

* E0's eight published figures reproduced with `wls_r2` as-is — max |Δ| **3.93 × 10⁻⁷**.
* E1's fourteen published figures (six in-sample, eight out-of-sample) reproduced with `r2_in` /
  `oos_delta` as-is — max |Δ| **4.75 × 10⁻⁷**.
* Headline: published 0.004003, reproduced 0.004003, |Δ| **9.03 × 10⁻⁸**.

Both maxima sit at the rounding granularity of the 6-decimal numbers in the frozen run logs.
Reproduction is exact to the precision at which the numbers were published, so every later
difference is attributable to the convention change and not to this harness.

---

## 3. Three-column table — the numbers that matter

`quantity | as-published | standard weighted | plain unweighted OLS (adopted)`

### E0 screen (published numbers genuinely are defective)

| quantity | as-published (defective) | standard weighted | plain OLS | bias % |
|---|---|---|---|---|
| rung-1 pooled | 0.008424 | 0.009111 | 0.005079 | −7.54 |
| rung-2 pooled | 0.006505 | 0.007035 | 0.004046 | −7.54 |
| rung-2 2021 | 0.015038 | 0.015959 | 0.012866 | −5.77 |
| rung-2 2022 | 0.005329 | 0.005624 | 0.002995 | −5.24 |
| rung-2 2023 | 0.002279 | 0.002499 | 0.000973 | −8.78 |
| rung-2 2024 | 0.006121 | 0.006783 | 0.003304 | −9.76 |
| rung-1, defrtg-controlled | 0.007529 | 0.008142 | 0.004920 | −7.54 |
| rung-2, defrtg-controlled | 0.005696 | 0.006161 | 0.003747 | −7.54 |

### E1 in-sample (published numbers are already standard weighted)

| quantity | as-published (std wtd) | defective | plain OLS |
|---|---|---|---|
| M_A E0 replication | 0.007035 | 0.006505 | 0.004046 |
| M_B + venue | 0.007045 | 0.006514 | 0.004056 |
| M_C + schedule balance | 0.007013 | 0.006484 | 0.004027 |
| M_D + opp defrtg | 0.005999 | 0.005547 | 0.003681 |
| M_E pregame baseline | 0.006765 | 0.006256 | 0.003970 |
| M_F pregame full control | 0.005649 | 0.005224 | 0.003566 |

### E1 out-of-sample — where the lead actually lives

| quantity | as-published (std wtd) | defective | plain OLS | change vs published |
|---|---|---|---|---|
| LOSO mean, M_B | 0.007071 | 0.006587 | 0.003949 | −44% |
| **WF mean, M_B (HEADLINE)** | **0.004003** | 0.003668 | **0.000850** | **−79%** |
| LOSO mean, M_D | 0.006297 | 0.005885 | 0.003729 | −41% |
| WF mean, M_D | 0.003270 | 0.003022 | 0.000767 | −77% |
| LOSO mean, M_E | 0.006731 | 0.006272 | 0.003808 | −43% |
| WF mean, M_E | 0.003479 | 0.003181 | 0.000453 | −87% |
| LOSO mean, M_F | 0.005908 | 0.005526 | 0.003581 | −39% |
| **WF mean, M_F (honest)** | **0.002795** | 0.002584 | **0.000413** | **−85%** |

The defective-vs-standard bias is a steady −6.5% to −9.8% everywhere, exactly as predicted.
The **unweighting** is what does the damage, and it does far more damage to the walk-forward folds
than to the in-sample or leave-one-season-out ones. Read plainly: the effect is concentrated in
high-possession player-games, and the possession weights were putting most of the walk-forward
signal there.

---

## 4. The retrospective-baseline check (constraint 3) — a real hit

I read the construction, not the label.

**The predictor is clean.** `opponent_pressure_pregame` comes from
`pressure_lib_e1.PregameTeamPressure.lookup` → `_PrefixIndex.prefix`, which does
`np.searchsorted(dates, date_ns, side="left")` — strictly before this game's date — then shrinks
(K = 200 possessions) toward the prior-season team rate or that season's league mean. Nothing it
touches is on or after the game date. The other controls (`opp_prior_home_share`,
`opponent_defrtg_pregame`, `player_is_home`) are likewise prior-games-only or schedule facts.

**The baseline carrying the headline is not clean.** `player_tendency_loo`
(`build_data.py` lines 164–170) sums the player's turnovers and possessions over **all** games in
the season, then subtracts this game's own tallies. That is a full-season leave-one-out — the exact
offender named in constraint 3. It reads games that had not been played yet.

Measured, not assumed:

* corr(LOO baseline, the player's own strictly-**after**-date season rate) = **+0.6455**
* corr(pregame baseline, same future rate) = **+0.3647**
* dR² of adding the LOO baseline on top of the pregame baseline, with the **future rate** as the
  target = **0.3319**

A quantity that explains a third of the variance in games that have not happened is reading the
future. Confirmed.

**How much does this matter here?** Less than it might, because E1 already anticipated it and
shipped fully-pregame variants. M_A–M_D use the retrospective baseline; M_E and M_F use
`player_tendency_pregame`, which is strictly-before-date. So the fix is not new work — it is
switching which row of the existing table gets quoted. The headline +0.004003 is M_B, i.e. the
retrospective one. **The forecasting-honest analogue is M_F: 0.002795 as published, 0.000413 under
the adopted convention.**

I am flagging this prominently as instructed, but with the honest caveat that it is a *reporting*
failure rather than a *construction* failure: the clean number exists in the frozen screen and was
simply not the one promoted to headline.

---

## 5. Permutation nulls at the correct grouping level (constraint 4)

`opponent_pressure_pregame` varies at **opponent-team × game-date** level — 12 teams per season,
1,940 team-game cells, broadcast across 18,165 player rows. The correct permutation is the team-
identity derangement within season (each row receives *another* team's already-computed pregame
value at its own date), which preserves the 12-team coarseness and the within-team-game repetition.
I ran both that and the row-level shuffle, at N = 200 each, under plain OLS, seeded 20260807 (the
frozen screen's seed, so the draws are the same ones).

| statistic | real | correct-level null sd | row-level null sd | draws ≥ real (correct level) |
|---|---|---|---|---|
| in-sample M_A | +0.004046 | 0.000257 | 0.000073 | 0/200 |
| in-sample M_B | +0.004056 | 0.000257 | 0.000073 | 0/200 |
| in-sample M_F | +0.003566 | 0.000256 | 0.000077 | 0/200 |
| LOSO mean M_B | +0.003949 | 0.000440 | 0.000143 | 0/200 |
| LOSO mean M_F | +0.003581 | 0.000435 | 0.000148 | 0/200 |
| WF mean M_B | +0.000850 | 0.000654 | 0.000207 | 0/200 |
| **WF mean M_F** | **+0.000413** | **0.000712** | 0.000207 | **7/200 (p = 0.035)** |

The correct-level null is **2.5–3.5× wider** than the row-level one on every statistic. Row-level
shuffling is anti-conservative here, exactly as the constraint warns.

**Cluster-robust SEs do not rescue it.** The row-level t on the pressure coefficient is +8.74 to
+8.18 across specs; clustering on opponent team-game (1,940 clusters) moves it to +8.95 to +8.29 —
essentially unchanged, and in the *wrong direction*. It comes nowhere near the width the
permutation null actually shows. Third independent confirmation in this program that classical and
cluster-robust inference on team-aggregate features is not trustworthy in this data.

**Convention changes the significance, not just the size.** Under the as-published weighted
convention the M_F walk-forward mean sits outside all 200 correct-level draws (p < 0.005). Under
plain OLS, 7 of 200 draws equal or beat it (p = 0.035). It survives, but marginally.

## 5b. The defective no-op placebo, run on purpose (constraint 5)

Ran a drawer that returns the real pressure vector unchanged, 25 draws, all seven statistics.
Signature reproduced exactly: mean == real to < 1e-12 and sd = 0 for all seven. Five of seven were
bitwise-exact 0.0; two (the walk-forward statistics) came back at LAPACK float noise ~1e-19 rather
than a hard zero, which is a property of `lstsq` reproducibility, not of the control. Since the two
genuine nulls have sd of 1.4×10⁻⁴ to 7.1×10⁻⁴ and place the real value well outside their support,
they are demonstrably shuffling.

---

## 6. Does the verdict change?

**The gate holds. The magnitude does not.**

| gate | as published | adopted convention |
|---|---|---|
| retained after home/away control > 0.5 | 1.0015 ✓ | 1.0025 ✓ |
| LOSO all-positive, M_B | true ✓ | true ✓ |
| LOSO all-positive, M_F | true ✓ | true ✓ |
| placebo draws ≥ real, LOSO M_B | 0 ✓ | 0 ✓ |
| placebo draws ≥ real, LOSO M_F | 0 ✓ | 0 ✓ |
| instrument split-half mean r > 0.3 | 0.5725 ✓ | 0.5725 ✓ (convention-independent) |
| **verdict** | **keep-as-lead** | **keep-as-lead** |

So: **the lead survives, and it weakens.** Those are not in tension — the frozen gate was built out
of sign and rank conditions, all of which are convention-invariant, and none of which constrain
effect size.

**The ranking consequence is the real output.** Against leads screened under plain OLS, I0009 must
be entered at **0.000413** (fully pregame baseline, fully controlled, walk-forward) or at most
**0.000850** (retrospective LOO baseline, venue-controlled). Not at 0.004003 — and emphatically not
at 0.004003 scaled *up* for a supposed defective-SST understatement, which was the working
assumption going in. The old ranking was invalid, but in the **opposite direction** to the one D069
anticipated. I0009 was flattered by possession weighting far more than it was penalised by the SST
bug.

**Caveat I want on the record.** Both estimands are legitimate. Weighting by possessions targets a
possession-level effect; plain OLS targets a player-game-level one. Neither is "the truth". The
argument for quoting the plain-OLS number is comparability with the other three leads, nothing more.
The size of the gap (0.004003 → 0.000850) is itself a finding worth keeping: it says the effect
lives disproportionately in high-possession player-games, which is a substantive claim about the
mechanism and could be tested directly.

---

## 7. Manifest check (constraint 2) — a program gap, not a clean pass

The two inputs to `build_data.py` are
`experiments/player_program/turnover_targets_v1/player_turnover_targets_v1.parquet` and
`experiments/player_program/possessions_v2/possessions_raw_v2.parquet`. **Neither has a sibling
`<artifact>.manifest.json`**, so `asof_granularity` cannot be read for either — I confirmed by
directory listing, and the repo does carry manifests elsewhere (`data/masters/`, `data/rapm/`,
`data/zone_maps/`, various `experiments/` artifacts), so their absence here is a gap rather than a
convention that manifests do not exist.

I therefore could not execute the manifest rule as written. Both artifacts are raw
row-per-game / row-per-possession tallies with an explicit `season` column and no fitted
cross-season parameter, so row-level filtering does bound them — but that is an argument from
reading the builder, not from a manifest. This measurement in any case re-uses the **frozen CSVs
the screens already wrote**, which I verified 2021–2024 on column values directly. Worth a
follow-up to backfill manifests for the `player_program` artifacts (`backfill_manifests.py` exists
at repo root).

---

## 8. Where I could have cheated

Stated honestly, with when each choice was made.

1. **Choosing which convention counts as "plain OLS".** I defined it before running anything, in
   `step23_reproduce_and_rerun.py`: unweighted fit, unweighted SSE, SST about the unweighted mean;
   out-of-sample, fit on train unweighted with SST about the train unweighted mean. I could instead
   have kept the weighted *fit* and only unweighted the R² denominator, which would have given a
   number much closer to the published one and made the lead look better. I did not, and I am
   flagging that the choice matters a lot here — it is worth ~3× on the walk-forward figure. The
   third column is the honest reading of "plain unweighted OLS R² = 1 − SSE/SST", but a coordinator
   who meant something else should say so and I will re-run.

2. **Which figure to call "the headline".** The task named +0.004003, which is M_B — the
   retrospective-baseline spec. I could have quietly reported only that one and skipped M_F.
   I chose before seeing results to carry both M_B and M_F through every step, precisely because
   constraint 3 told me to expect a baseline problem. M_F is the worse number for the lead and I am
   leading with it.

3. **Permutation count and seed.** N = 200 and seed 20260807 were fixed before running, chosen to
   match the frozen screen so the draws are literally the same ones. I did not re-roll the seed
   after seeing that M_F's walk-forward p came out at 0.035 — a second seed would very likely move
   it either side of 0.05 and I am not going to shop for that. If the coordinator wants a tighter
   p, the right fix is N = 2000 on a pre-declared seed, not a second draw of 200.

4. **The no-op placebo tolerance.** The assertion originally demanded sd bitwise-exactly 0.0 and
   failed on two of seven statistics at ~1e-19. I relaxed it to < 1e-15 **after** seeing the
   failure. That is a post-hoc change and I am disclosing it. The raw sd values are recorded in
   `step4_results.json` under `sd_by_statistic` so the relaxation can be audited. The diagnostic's
   purpose — proving the real controls are not no-ops — is unaffected, since the real controls'
   sds are 15 orders of magnitude larger.

5. **Not re-running `build_data.py`.** I used the frozen CSVs rather than rebuilding from the
   parquets. This means I inherit any error in the frozen build rather than independently checking
   it. I chose this deliberately: the task is a like-for-like convention comparison, and rebuilding
   would confound the convention change with build drift. It does mean I have **not** independently
   verified the frozen frame against the source parquets. That is a real limitation, not a
   formality.

6. **The analytic prediction was stated before measuring**, in `step1_audit.py`, which runs and
   writes `step1_audit.json` before `step23_reproduce_and_rerun.py` executes. The exact-to-5e-12
   agreement is therefore a genuine prediction, not a fit. But I should note the prediction is
   *algebraically* guaranteed given identical SSE, so its confirmatory value is about verifying
   that SSE really is identical, not about validating the mechanism story independently.

---

## Files

* `FINDINGS.json` — full structured output: three-column table, weight/centering audit, prediction
  vs measurement, reproduction deltas, baseline audit, nulls, verdict impact.
* `NOTES.md` — this file.
* `run_log.txt` — full console output of all five steps.
* `step1_audit.py` / `step1_audit.json` — configuration audit and analytic prediction.
* `step23_reproduce_and_rerun.py` / `step23_results.json` — reproduction + three conventions.
* `step4_verdict_and_nulls.py` / `step4_results.json` — permutation nulls, no-op diagnostic, t-stats.
* `step5_baseline_audit_and_gate.py` / `step5_results.json` — baseline audit, weighted WF null, gate.
* `step6_build_findings.py` — assembles FINDINGS.json.
* `permutation_draws_plain_ols.csv` — 2,975 draws (2 nulls × 7 statistics × 200, plus no-op 7 × 25).
* `permutation_draws_standard_weighted_wf.csv` — 400 draws, weighted walk-forward null.
* `player_game_analysis.csv`, `team_game_defense.csv`, `pressure_lib_e1.py` — copies of the frozen
  E1 inputs. `E0_*.csv`, `pressure_lib.py`, `E0_summary_published.json` — copies of the frozen E0
  inputs and published summary.
* `src/E0_analyze_original.py`, `src/E1_analyze_original.py` — read-only copies of the frozen
  screens, kept so the line numbers cited above can be checked without touching the originals.
