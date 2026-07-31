# -*- coding: utf-8 -*-
"""Regenerate experiments/coherence_study/REPORT.md (the design memo).

House convention (mirrors experiments/channel_reval/write_report.py): the report is
produced by a script so it can be regenerated verbatim. Every number in the memo is
computed and asserted by coherence_analysis.py (see analysis_log.txt /
analysis_summary.json); this file holds the prose. Run coherence_analysis.py FIRST —
if its asserts fail, this memo's numbers are void.
"""

from pathlib import Path

OUT = Path(__file__).resolve().parent

MEMO = r"""# Joint-Coherence Design Study — where margin error actually lives

*2026-07-30 · `experiments/coherence_study/` · **READ-ONLY reconnaissance, NOT a registered
experiment.** No model was fit for promotion, no promotion claim is made, the registry and
leaderboards were not touched. Every number below is computed by
`coherence_analysis.py` from committed artifacts of registered experiments
(`experiments/channel_reval/predictions_v2.csv`, `experiments/channel_reval/channel_base_v2.csv`,
`experiments/w2_integration/game_level_predictions.csv` + `calibration_params.json`,
`experiments/bottomup_3pt/teamgame_level_predictions.csv`, `experiments/w4_refs/crew_factors.csv`),
after hard-asserting reproduction of the ledgered numbers (margin 10.0860 / home 8.7928 /
away 8.6163 / total 14.2236 on the 673 chanreval test games; substituted margin 10.3569 and
incumbent 10.1753 on the 627-game bottomup gate-4 universe; all asserts in `analysis_log.txt`).
Quantities labeled **ORACLE** use realized outcomes and can never be features; quantities labeled
**ANALYTIC-NORMAL** assume Gaussian errors. Error convention: e = prediction − truth.*

## Why this study

Three registered experiments converged on the same structural fact tonight:

1. `experiments/w2_integration/REPORT.md` — overlay factors inflated the 3pt/paint channel
   variances (82→96, 72→92) and made the off-diagonal cancellation deeper but noisier; margin FAIL.
2. `experiments/bottomup_3pt/REPORT.md` — the challenger predicted each side's 3pt points
   *better* (team-total 8.749 vs 8.825) yet the substituted **margin got worse** (10.357 vs
   10.175) because incumbent home/away errors co-move (+0.326) more than substituted (+0.304),
   and that co-movement subtracts out of margins.
3. The chanreval gate-4 machinery (`evalharness/compare.py`) formalizes "the final joint
   forecast does not degrade" but gives no diagnosis of *why* a per-part winner degrades it.

This memo decomposes exactly where the error mass sits, what drives it, what recombinations of
existing predictions can and cannot buy, and what to preregister next.

---

## 1. Shared-shock decomposition — the headline

Per game, side errors split exactly into a **common shock** c = (e_h + e_a)/2 and an
**idiosyncratic** part u = (e_h − e_a)/2, so e_h = c + u, e_a = c − u,
**margin error = 2u** (c cancels), **total error = 2c** (c doubles). With side variances
roughly equal, common share = var(c)/(var(c)+var(u)) ≈ (1+ρ)/2 where ρ = corr(e_h, e_a).

**Incumbent (`chanreval_structural_calibrated`), 673 test games** (`decomposition_summary.csv`):

| quantity | value |
|---|---|
| var(e_h) / var(e_a) | 124.14 / 120.31 |
| cov, corr(e_h, e_a) | +40.82, **+0.3340** |
| var(c) / var(u) | **81.52 / 40.71** |
| **common share var(c)/(var(c)+var(u))** | **0.667** |
| margin error variance = 4·var(u) | 162.8 |
| total error variance = 4·var(c) | 326.1 (**2.00×** the margin's) |

**Two thirds of the incumbent's side-error variance is a game-level common shock.** It never
touches the margin and hits the total doubled — which is why the same model that posts margin
MAE 10.09 posts total MAE 14.22 on the identical games, and why the totals problem
(`experiments/totals_head`, bottomup finding #3) and the margin problem are *different problems
sharing one model*.

Season stability (calibrated, per-season rows in `decomposition_summary.csv`): the split is
real everywhere but not constant —

| scope | corr(e_h,e_a) | var(c) | var(u) | common share | mean(c) |
|---|---|---|---|---|---|
| 2024 (n=229) | +0.390 | 69.6 | 30.5 | 0.695 | −0.01 |
| 2025 (n=276) | +0.178 | 68.8 | 48.1 | 0.589 | +0.14 |
| 2026 (n=168) | +0.459 | 114.8 | 42.7 | 0.729 | **−2.48** |

Within-season halves are stable (2024: 0.690/0.706; 2025: 0.583/0.593; 2026: 0.723/0.733), so
the year-to-year movement is environment, not estimation noise. Two 2026 facts matter downstream:
var(c) jumps ~65% in the elevated-scoring 2026 environment, and **mean(c) drifts to −2.48
(−1.59 first half → −3.38 second half), i.e. the model under-predicts 2026 game totals by ~5.0
points on average** (2·mean(c); the chanreval REPORT's "2026 scoring environment is up" made
quantitative). The α=0.05 trend chains lag a rising league environment.

**What the bottom-up challenger lost** (identical 627 RS games, calibrated; uncal row reproduces
the bottomup REPORT's +0.3258/+0.3036 and 167.27/171.11 exactly at ddof=0):

| | incumbent | substituted (challenger 3pt) | delta |
|---|---|---|---|
| corr(e_h, e_a) | +0.3332 | +0.3158 | −0.017 |
| var(c) | 82.95 | 81.80 | **−1.14 (totals better)** |
| var(u) | 41.48 | 42.53 | **+1.05 (margins worse)** |
| common share | 0.6666 | 0.6579 | −0.0087 |
| per-side error variance (avg) | 124.43 | 124.34 | −0.09 |

The challenger's per-side accuracy gain is real but tiny at the sum level — what it mainly did
was **re-allocate ~1.1 pts² of error variance from the common pool (margin-invisible) to the
idiosyncratic pool (margin-visible)**. Better sides, worse margins, slightly better totals — all
three of tonight's headline numbers follow from this one reallocation.

### 1b. What the shocks are made of (channel decomposition, uncal chains, 673 games)

Channel parts sum exactly to c and u (asserted); variance attribution by β-share
(cov(part, total)/var(total), sums to 1; `channel_shock_decomposition.csv`):

| component | ft | 3pt | paint | np2 |
|---|---|---|---|---|
| common shock c | 0.212 | **0.396** | 0.344 | 0.048 |
| idiosyncratic u | 0.079 | **0.469** | 0.385 | 0.068 |

3pt and paint carry ~74% of the common shock and ~85% of the margin-relevant error. FT
contributes 3× more to c than to u — whistle environment is a genuinely *shared* shock
(consistent with the crew correlate below).

---

## 2. Is the common shock predictable? Essentially no (cross-sectionally)

All features strictly walk-forward from `channel_base_v2.csv` (rest days, prior-mean pace proxy
fga+0.44·fta, prior 3PA volume, trailing 14/30-day and season-to-date league total environment,
days into season, month, season) plus `experiments/w4_refs/crew_factors.csv` (walk-forward crew
FTA prior — with w4's registered caveat: **actual** crew as proxy for the pregame announcement).
Full table: `shock_correlates.csv`.

| walk-forward feature | r with c | r with \|c\| |
|---|---|---|
| crew_factor (w4) | **−0.152** | +0.066 |
| env_total_season | −0.103 | +0.167 |
| season | −0.097 | +0.134 |
| env_total_30d / 14d | −0.082 / −0.082 | +0.160 / +0.173 |
| rest, pace, 3PA-volume priors, month, days-into-season | all \|r\| ≤ 0.06 | ≤ 0.06 |

- **Multivariate:** in-sample OLS R² = **0.045** (12 features + season dummies, n=673); honest
  fit-2024+2025 → predict-2026: **out-of-sample R² = −2.84** (the 2026 level shift is not in
  earlier features; the tiny in-sample fit does not generalize). For u: in-sample R² = 0.021.
  sd(c) = 9.03 points. **Conclusion: game-to-game, c is ~95%+ irreducible game-night noise.**
- **ORACLE context** (decomposition only, never features): c is realized pace + shooting
  variance — corr(c, realized-pace shock) = −0.53, corr(c, c_3pt) = +0.54, c_paint +0.50,
  c_ft +0.45. corr(c, total_true − str_total_cal) = −0.966 ≈ −1 by identity (label check).
  This is the indoor sport's weather: pace realization, make variance, and the whistle.
- **The one real walk-forward signal is slow, not cross-sectional:** the 2026 mean(c) drift.
  c itself is *observable after each game* (it is realized error), so a trailing league-wide
  tracker is legitimate walk-forward. Tested (§3d): a 14-day tracker removes over half the 2026
  totals bias (−4.97 → −2.25) but its noise (corr(c_hat, c) = +0.067) eats the pooled gain
  (total MAE 14.22 → 14.36 raw; best damped variant ×0.25 → **+0.016**, ~nil). A level adapter
  is a totals-line *calibration* story, not a pooled-MAE story, at this sample size.
- The crew correlate (−0.152, ~2.3% of var(c)) is a lead for the **totals side only** — w4's
  registered FT-channel test was already a clean null, and by §3's theorem any crew term applied
  symmetrically to both sides cannot move margins at all.
- **Heteroscedasticity is mildly predictable** (r(\|c\|, env_14d) = +0.17; var(c) 69→115 across
  seasons): relevant to the `dist_margin_cover` line and any totals uncertainty head, not to
  point forecasts.

---

## 3. Recombination simulation — what existing predictions can and cannot buy

Full table: `recombination_results.csv`. Universe A = 673 chanreval test games; universe B =
627 RS bottomup gate-4 games. All rows use committed predictions only.

**Universe A (incumbent recombinations):**

| variant | margin MAE | total MAE |
|---|---|---|
| (a) calibrated margin head (deployed) | **10.0860** | 14.2236 |
| (b) side-head difference home_cal − away_cal | 10.1603 | 14.2236 |
| (c) ORACLE: subtract realized c from both sides, then diff | 10.1603 (≡ (b), asserted ≤1e−9) | 0.0000 |
| (c′) ORACLE: subtract realized u instead | 0.0000 | 14.2236 |
| ANALYTIC-NORMAL: corr(e_h,e_a) → 0 at fixed side accuracy | ~12.49 | ~12.51 |
| (e) walk-forward c tracker (best damped, ×0.25, 14d) | 10.0860 (unchanged by construction) | 14.2073 |

Readings:

- **(c) is the theorem in numbers: removing the entire common shock — an oracle no model can
  beat — buys exactly 0.000 margin points.** Margin error is 2u, period. Any effort spent making
  *sides* better through their common component is margin-dead on arrival. (Its side MAE drops
  8.79 → 5.08 and totals go to zero — that is where common-component work pays.)
- (a) beats (b) by 0.074: the single margin-head calibration on the differential beats
  differencing two separately-calibrated side heads, because unequal side slopes (b_h = 0.6765
  vs b_a = 0.6235, `calibration_params.json`) leak (b_h−b_a)·(common variation) into (b).
  Keep the dedicated margin head; never ship home−away as the margin.
- The +0.334 correlation is **worth ~2.33 margin MAE points and costs ~1.72 total points**
  versus independent side errors at unchanged side accuracy (ANALYTIC-NORMAL). Co-movement is a
  pure transfer between the margin market and the totals market (trade curve in
  `analysis_log.txt`); at fixed side accuracy the two books trade off one-for-one in variance.

**Universe B (bottom-up substitution recombinations, 627 RS games):**

| variant | margin MAE | total MAE |
|---|---|---|
| incumbent margin head / totals | **10.1753** | 14.3225 |
| full substitution (challenger 3pt, gate-4 protocol) | 10.3569 | 14.2172 |
| (d2) blend: incumbent 3pt COMMON + challenger 3pt DIFF | 10.3569 (≡ full sub, asserted) | 14.3203 |
| (d3) blend: challenger 3pt COMMON + incumbent 3pt DIFF | **10.1753 (≡ incumbent, asserted)** | **14.2198** |
| (d4) ORACLE error blend c_inc + u_sub | 10.4171 (≡ full-sub side-diff, identity) | — |

**The registered question — "does cancellation-preserving substitution rescue the bottom-up
result?" — has a sharp answer: rescue of the margin is impossible in principle.** Calibrated
margins are affine in the channel *differentials* only; any swap of common components is
margin-invariant (d2 ≡ full substitution and d4 ≡ full substitution, both verified to 1e−9).
There is no u/c blend that keeps the challenger's per-side gain and the incumbent's margin —
u *is* the margin. What the blend **does** buy is (d3): **take the challenger's common
component only → margins bit-identical to the incumbent by construction, totals improve
−0.103** (14.3225 → 14.2198; 90% date-clustered bootstrap CI on the delta [−0.017, +0.229],
223 clusters, seed 20260730 — design-memo power estimate, not a registered evaluation; seasons
+0.292 / +0.087 / −0.107). Gate-4 dress rehearsal: home 8.851→8.769, away 8.700→8.656, margin
identical, total improves — all components non-degrading.

**Where the substitution damage actually comes from (§3b — the study's sharpest finding):**
the challenger's 3pt *differential alone is better* than the incumbent's (diff MAE 4.906 vs
4.988, +0.082; common MAE also better, 5.206 vs 5.266). The margin still degrades because of
**cross-channel covariance among differentials**:

> Δvar(margin error) = **+3.84** = own-variance term **−2.55** + cross-channel covariance term
> **+6.39**. corr(e_3pt_diff, e_rest_diff): incumbent **−0.480** → challenger **−0.464**.

The bottom-up channel is more accurate *and* less hedged: its 3pt differential errors cancel
less against the paint/ft/np2 differential errors. 100% of the net margin damage (and more) is
lost cross-channel cancellation — the ROADMAP Phase-1 §3 rule ("a channel that improves alone
but breaks error cancellation in the sum is rejected") operating one level down, *inside the
differentials*. Per-side MAE, per-channel MAE, and even isolated differential MAE are all
sign-unreliable proxies for margin impact.

**ORACLE gain ceilings for differential work** (λ-shrink of one channel's differential error,
incumbent margin head, 673 games):

| channel | λ=0.25 | λ=0.5 | λ=1.0 (full removal) |
|---|---|---|---|
| 3pt | 9.338 | **8.957** | 9.423 |
| paint | 9.519 | **9.254** | 9.756 |
| ft | 9.966 | 9.972 | 10.371 |
| np2 | 9.932 | 9.891 | 10.114 |

Baseline 10.086. Two lessons: (1) 3pt and paint differentials are the only margin levers of
size (oracle ceilings ≈ −1.13 and −0.83); (2) **even oracle error-removal is non-monotone** —
fully deleting a channel's differential error *overshoots* (λ=1 worse than λ=0.5) because it
also deletes the cancellation that error was providing. Coherence binds even in the limit.

**Family (i)-lite is dead (§3e):** re-weighting the existing channel differentials
(margin = a + Σ w_ch·diff_ch, the GLS-flavored generalization of the single-b margin head) has
an **in-sample ceiling of +0.087** (9.999 vs 10.086, weights fit on the test games themselves —
an upper bound no honest fit can beat, already below the 0.10 gate), and the honest
fit-2024+25→2026 split is **−0.166**. Margin gains cannot come from recombining existing
predictions at all — they require *new differential information*.

---

## 4. Design recommendations, ranked

**R1 — Preregister next: the cancellation-preserving substitution rule + its first harvest
(d3 on the bottom-up 3pt channel).** Evidence: §3 theorem + d3 row (+0.103 totals, margins
bit-identical, all gate-4 components improve). Cost: ~1 evening; no refit (incumbent
calibrations unchanged; challenger artifacts already committed). Kill: 2026-remainder keeps
degrading (2026 delta is −0.107 now; season completes in ~6 weeks), or any nonzero margin
deviation (protocol bug). Full gate design below.

**R2 — Redirect margin work to a joint differential system (family i, done right) — but only
after R1 lands the protocol.** The evidence kills the cheap versions (re-weighting: ceiling
+0.087 in-sample, negative OOS; per-channel replacement tuned per-side: bottomup FAIL; overlay
factors: w2 FAIL) and defines the requirement: a challenger must improve a channel differential
*while preserving cross-channel differential covariance*, which no per-channel objective sees.
Concretely: train/select on the joint margin objective directly (all four differential chains
evaluated as a system), with §3b's own-var/cross-cov attribution as a mandatory diagnostic.
Expected gain bound: oracle ceilings −1.13 (3pt) / −0.83 (paint); realistic fraction unknown —
the challenger's +0.08 isolated diff gain converted to −0.18 margin, so no observed evidence yet
that any candidate converts. Cost: high. Kill: an evening of the diagnostic applied to the next
candidate showing the cross-cov term again dominates.

**R3 — Shared-shock term in a *distributional* head only (family ii, demoted for means).**
c is cross-sectionally unpredictable (in-sample R² 0.045, OOS negative); a mean-model shock term
is dead. But the c/u split with predictable heteroscedasticity (r(\|c\|, env) ≈ +0.17;
var(c) 69→115 by season; corr trade curve) is exactly the parameterization a margin/total
distribution head needs (`dist_margin_cover` line). The 2026 totals bias (−5.0) also belongs
here as a slow level adapter — worth ~+0.016 pooled MAE at best (damped tracker), but it moves
the totals *line* by ~2–5 points in 2026, which matters for bet selection even when MAE barely
moves.

**R4 — More shared opponent/league scaling terms across sides (family iv): drop.** The raw-trend
sum (no opponent factors) already shows corr(e_h,e_a) = +0.317 vs structural +0.334
(`decomposition_summary.csv`): shared model structure contributes ~5% of the co-movement; the
rest is game-night realization (pace/shooting/whistle, §2). There is no headroom to engineer
more cancellation via shared inputs; cancellation is mostly physics, not architecture.

### The one to preregister: `coherence_substitution_rule_v1`

- **Hypothesis:** substituting ONLY the common (sum) component of the bottom-up 3pt channel —
  side_3pt′ = (chal_h + chal_a)/2 ± (str_3pt_h − str_3pt_a)/2 — into the structural sum improves
  the game-total forecast while leaving the margin forecast bit-identical to the incumbent.
- **Regime A.** Universe: the bottomup_3pt registered universe — chanreval test games, regular
  season, both sides covered by the Stage-A availability artifact (627 games 2024–2026 today;
  grows with the 2026 remainder). Uncovered/playoff games fall back to the pure incumbent
  (delta 0 by construction), so coverage on the full chanreval universe is 1.0000/1.0000.
  **Disclose:** on the full 673-game book the pooled totals delta dilutes to ≈ +0.096; the
  registered primary is the covered-RS universe, same as bottomup_3pt's registration.
- **Primary metric:** total_mae. **Incumbent:** `chanreval_structural_calibrated` total head
  (str_home_cal + str_away_cal; 14.3225 on the universe).
- **Thresholds:** standard gate (min_improvement 0.10, harm_ci_bound 0.05, per_season_tolerance
  0.15, coverage_tolerance 0.0), 90% date-clustered bootstrap, team-cluster sensitivity.
- **Gate 4 (strengthened):** margin must be **bit-identical** to the incumbent (assert
  max|diff| ≤ 1e−9 — stricter than non-degrading), home/away/total each non-degrading (+0.05).
- **Calibration:** incumbent (a,b) triplets applied unchanged — no refit anywhere (challenger
  is unconstructible on 2021–23; d3 needs no train-year artifacts).
- **Point-in-time disclosure (mandatory in the report):** the +0.1027 point estimate was first
  observed in THIS study on the same 2024–26 window; the registered run confirms protocol
  integrity and adds fresh evidence only via post-study games. Gate 1 passes by 0.003 today —
  a knife-edge that the registration must acknowledge as a live FAIL risk, with the 2026
  remainder as the honest decider.
- **Also lands (win or lose):** the substitution protocol as harness policy — every future
  channel replacement reports the c/u (common/differential) split of its channel, §3b's
  own-variance vs cross-covariance attribution of its joint-margin delta, and (when it wins
  per-side but fails gate 4) the d3 harvest as its salvage path.

---

## 5. Problems found / data notes

- **2026 totals bias:** the incumbent under-predicts 2026 game totals by 4.97 points on average
  (2·mean(c); H2 worse at −6.8). Margin unaffected (bias is common). Relevant to
  `totals_head` and any live totals exposure this season. (`decomposition_summary.csv`)
- **Bottomup REPORT variances are ddof=0:** its 167.27/171.11 margin-error variances equal this
  study's ddof=1 values ×(626/627) (167.54/171.38). Cosmetic, worth knowing when cross-citing.
- 16 of 1270 bottomup team-game rows are single-side-covered (games excluded from its own
  gate-4; reproduced here: 627 = (1270−16)/2). Not documented explicitly in that REPORT's
  universe line, which says 1270 team-games / 627 games without the reconciliation.
- predictions_v2.csv carries no TEAM_IDs (abbreviations only, and PHO/PHX renames exist);
  team-level joins here used w2's TEAM_ID columns. Fine as long as w2 stays committed.
- The w4 crew factor is the only nonzero walk-forward correlate of c (−0.152) and w4's
  registered FT-channel test was a clean null — consistent only if the crew effect is spread
  across channels (pace/whistle environment), which is a totals-sidecar lead, not an FT lead.

## Files

- `coherence_analysis.py` — the full analysis; reruns end-to-end from committed artifacts,
  re-asserting every ledger reproduction (exit nonzero on any mismatch).
- `write_report.py` — regenerates this memo (house convention).
- `analysis_log.txt` — complete numeric log of the run (all asserts + every table above).
- `analysis_summary.json` — machine-readable headline numbers.
- `decomposition_per_game.csv` — per-game e_h/e_a/c/u (cal + uncal), substituted-variant
  errors, channel shock parts (ORACLE-prefixed), and all walk-forward observables.
- `decomposition_summary.csv` — variance decomposition by model × scope (incl. per-season and
  half-season stability rows, raw-trend comparison, substituted variant).
- `channel_shock_decomposition.csv` — channel-level covariance split of c and u.
- `shock_correlates.csv` — c/\|c\|/u correlations, walk-forward vs ORACLE-context labeled.
- `recombination_results.csv` — every variant in §3 with margin/total MAE and notes.
"""

if __name__ == "__main__":
    (OUT / "REPORT.md").write_text(MEMO, encoding="utf-8")
    print(f"wrote {OUT / 'REPORT.md'} ({len(MEMO.splitlines())} lines)")
