# Stage 2A hypotheses — source: **opponent interaction and game environment**

Artifact: `experiments/player_program/stage2a/HYPOTHESES_agent_opponent_env.md`
Task: `TEAM_POSSESSION_PRIOR_V2` Stage 2A
Lane: **DIAGNOSTIC / IDEATION ONLY.** Nothing in this file was fitted, tuned, selected or scored.
Independence: this source read no other source's prompt or output and no `HYPOTHESES_*` file.

## Evidence actually used

| Source | Role |
|---|---|
| `experiments/player_program/stage2a/EVIDENCE_PACKET.json` (sha256 `f373e3ee…abaf1e4e`, verified) | frozen primary evidence |
| `experiments/player_program/build_projected_exposure.py` | read-only, incumbent construction |
| `data/masters/master_team.parquet` | field existence + coverage only |
| `experiments/player_program/possessions_v2/possessions_raw_v2.parquet` | field existence + coverage only |
| `experiments/player_program/turnover_targets_v1/team_turnover_reconciliation_v1.parquet` | field **semantics** check (see S4) |
| `experiments/prediction_contract_v5/player_game_enriched.parquet` | field existence + coverage only |
| `data/reference/team_cities.csv`, `data/reference/tip_times.csv` | existence + coverage (see S6 — packet correction) |

Standing caveat, applied to every row below: everything reported as "exists" is an **availability**
finding. Availability is not cutoff validity. Per the packet's own warning
(`cutoff_validity_asserted`), and per my instruction not to treat a receipt's `cutoff_valid`
declaration as proof, each input still needs scientific review before it may back a registered arm.

---

## S0 — Four structural readings that shape everything below

These come before the hypotheses because two of them **prune** hypotheses rather than generate them,
and a coordinator should see the pruning first.

### S0.1 — The error is variance in aggregate, but it is *bias that cancels* across strata

The packet is explicit: squared bias is 0.0019 of MSE, so "a better point estimate must reduce
dispersion, not re-centre." That is correct **marginally** and misleading **conditionally**. Several
strata carry large, opposite-signed local bias:

| stratum | n | bias | MAE | \|bias\| / MAE |
|---|---|---|---|---|
| `team_window_prior_season` | 183 | **−2.845** | 3.693 | 0.77 |
| `game_no_in_season` 1–3 | 228 | **−2.175** | 3.777 | 0.58 |
| `days_rest` 7+ | 162 | **−1.435** | 3.527 | 0.41 |
| `support` >10 | 23 | −1.113 | 4.538 | 0.25 |
| `support` 3–4 | 156 | **+1.342** | 3.144 | 0.43 |
| `support` 5–9 | 390 | **+1.147** | 3.065 | 0.37 |
| `game_no_in_season` 4–6 / 7–10 | 456 | **+1.11 / +1.14** | ~3.05 | ~0.37 |

The overall bias of +0.159 is these cancelling. **Conditional de-biasing is therefore a live route to
lower MAE even though the marginal bias is negligible** — and it is the *cheapest* route, because it
needs no new variance-reduction machinery, only a stratum-correct level. This reframing is the single
most actionable thing I can contribute, and part of it lands in my lane (rest, season phase,
season-over-season drift) and part of it does not (support / window / cold start).

### S0.2 — Within-game differentiation has almost no headroom. Do not spend effort there.

My mandate flags that "both teams receive an IDENTICAL projection, so the model carries no within-game
differentiation." I checked whether there is anything to differentiate. Over all 1495 contract games,
the gap between the two sides' realised offensive possession counts is:

| \|A − B\| possessions | 0 | 1 | 2 | 3 | 4 |
|---|---|---|---|---|---|
| games | 504 | 704 | 244 | 39 | 4 |

Mean gap **0.886**; 97.1% of games have a gap ≤ 2. Possessions alternate, so the two counts are
mechanically near-identical and the residual gap is essentially *who happened to hold the ball at each
period buzzer* — close to a coin flip and not predictable pregame.

**Consequence:** the best conceivable within-game differentiator recovers ~0.44 possessions per side
against an incumbent MAE of 2.903 — a ceiling of ~15%, and the realistic figure is a small fraction of
that because the quantity is near-random. **The symmetry assumption is not the defect it looks like.**
All the payoff in my lane is in the *level of the shared game total*, and every hypothesis below is
written as a game-level term. I am deliberately proposing **no** side-splitting arm.

### S0.3 — The incumbent is not innocent of opponent information; it carries the *wrong* opponent adjustment

From `build_projected_exposure.py`: `game_pace` is itself the mean of *both* sides in each historical
game, and `team_pace_estimate` is the mean of the team's last 10 such game-level values. So a team's
"own" pace estimate is roughly **half composed of the pace contributions of the ten opponents it
happened to face**, weighted equally. The projection for the target game is then the mean of two such
half-contaminated estimates.

This means the incumbent already contains an opponent adjustment — just an adjustment toward the
*past* opponents rather than the *target* opponent, with a ~50% effective weight and no correction.
A team emerging from a slow stretch of schedule carries a depressed estimate that is partly a property
of teams it will not play again, and when the target opponent is fast that contamination is
wrong-signed. Removing schedule contamination (**A2**) is therefore not "adding opponent adjustment to
a model that has none"; it is *replacing a biased implicit adjustment with a correct explicit one*.
That framing matters for how the arm is compared.

### S0.4 — Possession *duration* is the additive primitive; possession *count* is its reciprocal

Possessions tile game time. `duration_sec` has 100% coverage over 238,563 possessions, mean 15.13 s;
238,563 / 1495 × 15.13 ≈ 2415 s per game ≈ 40.25 min, exactly consistent with 2400 s of regulation plus
132 overtime games. So `count ≈ T / mean_duration`, and averaging *counts* across two teams is an
arithmetic average of a **convex** function of the additive quantity. The incumbent averages counts.
This is a mechanism-level defect independent of any data, and it yields hypothesis **A1** with an exact
sign.

---

## S1 — CATEGORY A: immediately testable

Inputs historically available across the full 2021–2026 span, cutoff-valid by construction (lagged or
schedule-derived), complete, and operationally reproducible from frozen artifacts.

Legend for the last field: **TOTAL** = changes the projected possession total; **CAL** = changes
calibration / uncertainty; **ALLOC** = only re-allocates across subgroups.

---

### A1 — Combine the two sides in duration space, not count space

| field | value |
|---|---|
| **Source** | opponent interaction / game environment |
| **Mechanism** | Possessions tile a fixed game clock. If side A's own tempo implies mean offensive possession duration `d_A` and B's implies `d_B`, the game's possession count is `≈ 2 · T / (d_A + d_B)` — i.e. the *harmonic-type* combination. The incumbent instead averages the two implied counts, `½(T/d_A + T/d_B)`. By Jensen's inequality on the convex map `d ↦ T/d`, the arithmetic mean of counts **exceeds** the count implied by the mean duration, and the gap grows with `(d_A − d_B)²`. |
| **Exact expected direction** | The new estimator is **≤** the incumbent for every game, with **equality only when the two sides' paces are identical**, and a monotonically increasing downward correction in the absolute pace gap between the two teams. Given the incumbent's mildly positive overall bias (+0.159), a uniformly-downward correction is directionally *helpful*, not harmful. |
| **Affected stratum** | Games pairing a fast team with a slow team — a *pairing*-defined stratum the packet does not currently break out. Neutral for evenly-matched-tempo pairs by construction. |
| **Cutoff-valid inputs** | Per-team trailing offensive possession duration over strictly earlier games: `possessions_raw_v2.duration_sec`, `offense_team_id`, `game_id`, plus the contract schedule. Identical lag discipline to the incumbent. |
| **Inputs exist?** | **Yes.** `duration_sec` 100% non-null over all 238,563 possessions, all 1495 contract games, all six seasons. |
| **Overlap risk** | **Low.** This is a functional-form change to the combination rule, orthogonal to window length, shrinkage, weighting, or feature addition. It will however *interact* with A2/A3 — apply it last, or test the combination rule on the incumbent's own inputs first so the effect is isolated. |
| **Leakage risk** | **Very low.** Same lag discipline as the incumbent; no target-game field touched. |
| **Expected information gain** | **Small but essentially free and sign-certain.** The correction is second-order in the pace gap, so I expect low-single-digit-percent MAE movement overall, concentrated in mismatched pairings. I rate this the best effort-to-confidence ratio in the file. |
| **Complexity** | **Low.** Arithmetic; no fitting, no new source, no new join. |
| **Falsifier** | If, restricted to the top decile of \|pace gap\|, the duration-space estimator does **not** reduce MAE relative to the count-mean, the mechanism is wrong (or the pace gap is too small in this league for the second-order term to clear the noise floor) and the arm dies. |
| **Changes** | **TOTAL** |

---

### A2 — De-contaminate the trailing window for the schedule actually faced

| field | value |
|---|---|
| **Source** | opponent interaction |
| **Mechanism** | Per S0.3, `team_pace_estimate` is ~half a property of the ten opponents faced. Decompose each historical `game_pace` into an own-tempo contribution and an opponent contribution, then re-project against the *target* opponent. A no-fitting version suffices: for each historical game in the window, subtract the opponent's contemporaneous pace level relative to league mean, average the residuals to get a schedule-free own-tempo index per side, and recombine the two indices with the league level. |
| **Exact expected direction** | The projection moves **toward** the target opponent's tempo and **away** from the mean tempo of the opponents recently faced. Concretely: for a team whose last-10 opponents were slower than the target opponent, the corrected projection is **higher** than the incumbent's; slower-target-opponent case, **lower**. Magnitude scales with (mean pace of window opponents − pace of target opponent). |
| **Affected stratum** | Largest in early season and after unbalanced schedule stretches, i.e. `game_no_in_season` 4–20 and the `support` 3–9 buckets that currently carry **+1.15 to +1.34** bias. Also the strongest candidate to explain part of that positive bias: early-season windows are the least schedule-balanced. |
| **Cutoff-valid inputs** | Opponent identity per historical game (`master_team.opp_team_id`, 2990/2990) and each opponent's own lagged pace history. The packet already certifies "OPPONENT realised game_pace over strictly earlier games" as available, coverage 2982, and explicitly notes it is **not used by the incumbent**. |
| **Inputs exist?** | **Yes**, at full coverage. |
| **Overlap risk** | **Moderate–high.** Any source working the estimator-form lane will likely propose window weighting/shrinkage, which changes the *same* number. The interaction is not additive: a schedule-corrected estimate is less noisy and therefore wants *less* shrinkage. Recommend these be tested jointly or in a fixed order, never as independent additive deltas. |
| **Leakage risk** | **Low but non-trivial.** The trap is using the opponent's *full-season* pace (which includes games after the target date) as the adjustment term. The adjustment must use the opponent's pace over **strictly earlier dates only**, which is thinner and noisier early in the season. An implementation that quietly reaches for a season aggregate is leakage and will look deceptively good. |
| **Expected information gain** | **Moderate — the highest in my lane on pure mechanism.** But see the honest caution: because `game_pace` is symmetric, the contamination is already half-averaged, and over a 10-game window opponent effects partly wash out. The residual signal is the *imbalance* of the window, which in a 40-ish-game season with 13 teams is real but not large. |
| **Complexity** | **Medium.** Requires an iterative or single-pass de-meaning over a strictly-earlier-dates panel, plus careful handling of games where the opponent itself has thin history. |
| **Falsifier** | Stratify by \|mean window-opponent pace − target-opponent pace\|. If the arm shows no MAE improvement in the top decile of that quantity — where the correction is by construction largest — the mechanism is absent. |
| **Changes** | **TOTAL** (and should tighten **CAL**, since removing a systematic contaminant should shrink residual dispersion) |

---

### A3 — Decompose offense-imposed and defense-imposed tempo

| field | value |
|---|---|
| **Source** | opponent interaction (defensive tempo control) |
| **Mechanism** | The incumbent's `game_pace` cannot distinguish "team A plays fast" from "team A's opponents play fast." Split it: compute, per team over strictly earlier games, (i) mean duration of its **own offensive** possessions and (ii) mean duration of possessions it **defended**. A game's expected possession duration is then a combination of A-offense-with-B-defense and B-offense-with-A-defense. This is the standard offense/defense split, and it is a strict generalisation of the incumbent (which is the special case where the two components are constrained equal). |
| **Exact expected direction** | Relative to the incumbent, the projection rises when the pairing is (fast offense) × (permissive defense) on **both** directed halves, and falls when it is (slow offense) × (tempo-suppressing defense) on both. When the two directed halves disagree the correction is near zero. Expected magnitude: larger than A1, smaller than the naive "opponent adjustment" intuition, because the defense's share of possession-length control is genuinely the smaller of the two. |
| **Affected stratum** | Pairings where the two sides' offensive and defensive tempo profiles are *discordant* — again a pairing-defined stratum not currently in the packet's break-outs. |
| **Cutoff-valid inputs** | `possessions_raw_v2`: `offense_team_id`, `defense_team_id`, `duration_sec`, `game_id`, `period`; plus schedule. All strictly-earlier-dates only. |
| **Inputs exist?** | **Yes.** All fields 100% present over all 238,563 possessions; `defense_team_id` is a first-class column. |
| **Overlap risk** | **High with A2** — both are opponent adjustments and they will compete for the same signal. A3 subsumes much of A2's content in a cleaner parameterisation. If the coordinator can only run one, **run A3**; A2 is the cheaper approximation. |
| **Leakage risk** | **Low**, same lag discipline. The one trap: `lineup_class` shows 503 possessions with an under-full lineup and `possession_kind` includes 1,799 zero-duration sequences and 588 technical-FT sequences — these distort a duration mean and should be excluded from *history* by a documented, symmetric rule, not by anything conditioned on the target game. |
| **Expected information gain** | **Moderate.** The most mechanistically principled arm in the file. |
| **Complexity** | **Medium–high.** Needs a combination rule for the two directed halves; the honest version is an additive-in-log-duration or league-relative-additive form, either of which is computable arithmetically without fitting. |
| **Falsifier** | If the per-team offensive-duration and defensive-duration-allowed indices are not separately stable across a season split (i.e. a team's defensive tempo index has no year-internal persistence beyond noise), there is nothing to decompose and the arm dies at the diagnostic stage before any scoring. |
| **Changes** | **TOTAL** |

---

### A4 — Condition each side's history on the venue role it is about to occupy

| field | value |
|---|---|
| **Source** | game environment (home/away) |
| **Mechanism** | The *game total* is shared, but the *venue* is a property of the specific matchup: this game is played in the home team's building, under its crowd, its clock operator, and its travel-free preparation. If a given team's home games run systematically faster or slower than its road games, then using an undifferentiated trailing window mis-states the tempo the venue will produce. Use the home side's **home-game** pace history and the road side's **road-game** pace history. |
| **Exact expected direction** | Directionally **team-specific, not league-uniform** — I predict a near-zero league-average effect and a non-zero per-team effect. My prior is that the league-average home/road tempo difference is small. Supporting evidence: mean offensive possession duration is 15.050 s for home offense and 15.216 s for away offense, a gap of **0.17 s (~1.1%)** — real but tiny, implying a home-team-offense-slightly-faster effect worth well under 1 possession per game at the league level. |
| **Affected stratum** | Would show up as a venue/home-team-identity stratum; nothing in the packet breaks out home/away, which is itself a gap worth filling diagnostically. |
| **Cutoff-valid inputs** | `master_team.is_home` (2990/2990, exactly 1495 home / 1495 away) plus the same lagged pace history. |
| **Inputs exist?** | **Yes**, full coverage; the packet already certifies `is_home` as schedule-determined. |
| **Overlap risk** | **Moderate.** Halving each window (home-only / road-only) collides directly with any window-length or support hypothesis — it halves effective support and will *increase* variance in the low-support strata that already have the worst MAE. |
| **Leakage risk** | **Very low.** |
| **Expected information gain** | **Low.** I am including it because home/away is explicitly in my mandate and because its *absence* deserves a recorded negative, not because I expect it to win. The 0.17 s league-level gap sets a ceiling of roughly 1% of a possession count, and the support cost is real. |
| **Complexity** | **Low.** |
| **Falsifier** | If per-team home-minus-road pace differences do not persist across seasons (i.e. a team's 2024 home/road tempo split does not predict its 2025 split), the effect is noise and the arm dies. I consider this the likely outcome. |
| **Changes** | **TOTAL**, marginally; realistically **ALLOC** only. |

---

### A5 — Correct the season-over-season league tempo drift, and un-stale the league prior

| field | value |
|---|---|
| **Source** | game environment (season phase / league environment) |
| **Mechanism** | Two related defects, both visible in the packet. (i) `team_window_prior_season` (n=183) has bias **−2.845** — projections built from last season's pace **under-project** this season's by nearly three possessions. Under-projection at a season boundary is the signature of a league that is speeding up year over year. The incumbent never blends or rescales across the boundary ("prior-season history is used only as a fallback and never blended"). (ii) The level-3 league prior is a **cumulative all-history mean** (the packet lists this as an explicit assumption), so under an upward drift it is stale by construction; that stratum shows MAE 3.902 on n=37. Fix: rescale any prior-season-derived estimate by the ratio of same-season-to-date league mean pace to the prior season's league mean pace over the comparable elapsed window; and replace the cumulative league prior with a recent-window league mean. |
| **Exact expected direction** | Prior-season-derived projections move **upward** (if the observed drift is upward, which the −2.845 bias implies); the level-3 league prior moves **toward the recent past** rather than the all-time mean. Expected effect on the `team_window_prior_season` stratum: bias toward zero, MAE toward roughly its own sd (3.714) from 3.693 — i.e. a **potential MAE reduction of up to ~35–40% within that stratum**, since \|bias\|/MAE there is 0.77. |
| **Affected stratum** | `team_window_prior_season` (n=183, 6.1% of team-games), `league_prior_all` (n=37), and by extension `game_no_in_season` 1–3 (n=228, bias −2.175, MAE 3.777) which is largely the same rows. Combined roughly 7–10% of team-games at the **worst** MAE in the panel. |
| **Cutoff-valid inputs** | League mean `game_pace` over strictly earlier dates, in the current and prior season — the incumbent already computes exactly this cumulative structure (`league_prior_mean` / `league_prior_n` in `build_projected_exposure.py`), so the machinery exists and only the aggregation window changes. |
| **Inputs exist?** | **Yes.** No new source at all. |
| **Overlap risk** | **High.** This is the most obvious available fix and I would expect an estimator-form or cold-start source to arrive at the same place from a different direction. It is also the one where duplicate proposals are *cheapest to reconcile*, since there is only one sensible correction. |
| **Leakage risk** | **Low**, provided "same-season to date" strictly means dates earlier than the target game — at a team's game 1–3 that denominator is thin (opening night has *no* prior same-season games at all) and there must be a documented fallback rather than a silent reach for a fuller season aggregate. That silent reach is the leakage trap here and it would look spectacular and be worthless. |
| **Expected information gain** | **Highest concrete expected value in the file**, because it is near-pure bias correction on a stratum where bias is 77% of MAE, and because per S0.1 conditional de-biasing is a live route even though marginal bias is negligible. |
| **Complexity** | **Low.** Two arithmetic changes to code paths that already exist. |
| **Falsifier** | If the league mean `game_pace` computed per season shows no monotone or otherwise structured drift across 2021–2026 — i.e. the −2.845 stratum bias is instead an artefact of *which teams* fall into the prior-season fallback (e.g. expansion clubs, of which this span has at least two: GSV from 2025 and PDX from 2026) — then the drift interpretation is wrong and the correction must be re-derived as a team-composition effect instead. **This is a genuinely open question I could not settle within my evidence scope.** |
| **Changes** | **TOTAL** and **CAL** |

---

### A6 — Project *expected game length*, not regulation-equivalent length

| field | value |
|---|---|
| **Source** | game environment (competitiveness → overtime) |
| **Mechanism** | The incumbent projects a **regulation-equivalent** quantity: `reg_equiv = n_off_poss · 40 / game_minutes`. But the operational turnover target is a **whole-game count**. I verified the field semantics directly: in `team_turnover_reconciliation_v1.parquet`, `team_off_possessions` equals the **raw** possession count from `possessions_raw_v2` for **2990 / 2990** team-games with no normalisation, and `team_turnovers_total` is likewise the raw whole-game count. Overtime team-games (132; `max_period` distribution 4:2858, 5:120, 6:10, 8:2) average **89.96** raw possessions against **79.32** for regulation games — a gap of **+10.6 possessions**, alongside mean turnovers of **15.70 vs 14.00** (**+1.70**). Overtime probability is a pure opponent-interaction quantity: it rises with expected closeness, which is knowable pregame from lagged strength. Fix: multiply the regulation-equivalent projection by `E[game_minutes]/40 = 1 + 0.125 · E[#OT periods]`, with `E[#OT]` a function of pregame expected margin. |
| **Exact expected direction** | The projection moves **strictly upward**, by ~0 for lopsided pairings and by up to ~1.3 possessions (≈0.23 turnovers) for the closest pairings at a base OT rate of ~4.4% and ~12.5% length inflation per OT period. Because the correction is one-sided, it will **worsen** any comparison made against a regulation-equivalent target and **improve** one made against the raw operational target. That asymmetry is the whole point. |
| **Affected stratum** | The `went_ot` stratum (n=132). Note the packet reports OT games with MAE **2.367**, *lower* than non-OT's 2.928 — which is exactly what one expects if the packet's diagnostic target is itself regulation-equivalent. The diagnostic panel is therefore **blind to this defect by construction**, and that blindness is my most important finding after S0.2. |
| **Cutoff-valid inputs** | Lagged team strength / expected margin from `master_team` box columns over strictly earlier games (all 65 columns 100% non-null across 2990 rows and all six seasons), plus schedule. Historical OT base rates from `possessions_raw_v2.period` / `is_overtime`. |
| **Inputs exist?** | **Yes**, in full. |
| **Overlap risk** | **Low.** I would be mildly surprised if another source frames this as a *scale* problem rather than a pace problem. |
| **Leakage risk** | **Low for the inputs, high for the sloppy implementation.** `is_overtime`, `max_period`, `abs_score_diff_start`, `score_diff_offense_end`, `wl`, `plus_minus` and `non_competitive_conservative` are **all target-game realised outcomes**. Only the *predicted* OT probability may enter; the realised one is catastrophic leakage that would look like a large win. This arm needs the strictest guard in the file. |
| **Expected information gain** | **Potentially the largest single operational win here — conditional on a prerequisite I could not verify.** 4.4% of team-games × ~1.7 turnovers is ~0.075 turnovers of mean absolute error, against a propagated mean-absolute of 0.517. That is ~15% of the *propagated* possession-attributable turnover error, though a smaller share of total turnover MAE. |
| **Complexity** | **Low–medium** for the multiplier; the OT-probability model is the work, and even a crude closeness-bucketed base rate captures most of it. |
| **Falsifier** | **Verification prerequisite (blocking):** confirm how the operational turnover-team scorer consumes `projected_team_off_possessions`. **If the operational pipeline already normalises for realised or expected game length, this hypothesis is void.** I did not read the downstream scorer — it is outside my declared evidence scope and I chose the boundary over the answer. Secondary falsifier: if a pregame closeness index does not separate OT rates across its deciles, the multiplier has no signal and reduces to a constant 1.044 uplift, which is then a pure re-centring and should be rejected on S0.1 grounds. |
| **Changes** | **TOTAL** (a scale correction), and **CAL** materially — the current projection is on a different measurement basis from the operational target for 4.4% of rows. |

---

### A7 — A symmetric rest and schedule-density term

| field | value |
|---|---|
| **Source** | game environment (rest, schedule density) |
| **Mechanism** | Fatigue and freshness plausibly change transition frequency and dead-ball behaviour. Because the total is shared (S0.2), the term must be a **symmetric function of both sides' rest**, e.g. `mean(rest_A, rest_B)`, `min(...)`, and the count of each side's games in the trailing 7 days — not a per-side adjustment. |
| **Exact expected direction** | The packet's `by_days_rest` panel gives the sign directly: `days_rest` 7+ has bias **−1.435** (projection below realised → long-rest games run **faster** than projected), while `0–1 (b2b)` has bias **+0.497** (short rest → **slower** than projected). So: **more rest → higher projection; denser schedule → lower projection**, monotone in between. Note the middle buckets (2, 3, 4–6) carry bias +0.34, +0.18, +0.11 — a clean monotone decline from b2b through 7+, which is encouraging for the mechanism. |
| **Affected stratum** | `days_rest` 7+ (n=162, MAE 3.527 — the second-worst rest bucket) and `0–1` (n=89). Together 251 team-games, 8.4%. |
| **Cutoff-valid inputs** | Game dates only. I verified derivability at full coverage: trailing-7-day game counts distribute {0:137, 1:476, 2:1321, 3:1022, 4:34} over all 2990 team-games with no missing values. |
| **Inputs exist?** | **Yes**, and the packet already certifies days_rest / b2b / density as 2990/2990 cutoff-valid. |
| **Overlap risk** | **Moderate.** The `days_rest` panel is the most conspicuous table in the packet and I expect at least one other source to reach for it. |
| **Leakage risk** | **Very low** — derived from prior dates only. |
| **Expected information gain** | **Low–moderate, and I am openly suspicious of it.** The `7+` bucket is heavily **confounded**: long gaps coincide with the all-star break, the pre-playoff gap, and playoff series spacing, and they concentrate in exactly the rows that also sit in unusual `game_no_in_season` and season-type strata. The −1.435 bias may be a season-phase or a playoff effect wearing a rest costume. Any arm must control for season phase and season type simultaneously, or it will attribute the wrong cause and will not generalise. |
| **Complexity** | **Low.** |
| **Falsifier** | If, **within** the regular season and **excluding** all-star-break-adjacent games, the 7+ rest bucket's bias collapses toward zero, then rest is not the operative variable and the arm should be reallocated to A12 (season phase). |
| **Changes** | **TOTAL** on ~8% of rows; elsewhere **ALLOC** |

---

### A8 — Travel burden and time-zone displacement

| field | value |
|---|---|
| **Source** | game environment (travel) |
| **Mechanism** | Travel is a fatigue channel distinct from days of rest: a team on day 3 of a 4-game road trip with two time-zone crossings is not equivalently rested to a team at home on 3 days' rest. Encode great-circle distance from the previous game's venue, signed time-zone delta, and road-trip run length, as a symmetric game-level combination of the two sides. |
| **Exact expected direction** | Same sign as A7's fatigue arm: **greater accumulated travel burden → lower projected possessions**. Because the home side by definition has zero travel-since-previous-home-stand in most cases, the game-level term is dominated by the road side, and the expected magnitude is a fraction of A7's. |
| **Affected stratum** | Road-trip rows. I verified the structure: away-game run lengths distribute {1:724, 2:432, 3:217, 4:92, 5:26, 6:3, 7:1} against 1495 home games — so ~24% of team-games are the 2nd-or-later leg of a trip, a decent stratum. |
| **Cutoff-valid inputs** | `data/reference/team_cities.csv` (see S6) — 16 rows / 15 team_ids with `lat`, `lon`, `elevation_ft`, `timezone`, `first_season`, `last_season`; plus the schedule. |
| **Inputs exist?** | **Yes — and this contradicts the frozen packet, which lists travel/time-zone as "ABSENT … would need venue geocoding … a venue table that does not exist here."** It does exist. I verified the join: every one of the 15 team_ids in `master_team` is present, and a season-aware join (`first_season ≤ season ≤ last_season`) resolves **exactly one arena for all 76 team-seasons**, no ambiguity, no misses, `lat`/`lon` non-null on all 16 rows, 6 distinct timezones. |
| **Overlap risk** | **Low**, precisely because the packet declares the input absent — other sources reading only the packet will not propose it. |
| **Leakage risk** | **Very low** (static reference + prior dates). One caveat: the table encodes each team's *regular home arena*, so **neutral-site and relocated games are silently mis-located** (see B5). That is a correctness bug, not a leak. |
| **Expected information gain** | **Low, and I expect this to fail.** Reasons I am including it anyway: it is in my mandate, it is now cheap, and its *negative* result is worth recording. Reasons I expect failure: (a) rest (A7) likely absorbs most of it; (b) `elevation_ft` spans only 20–2030 ft with no true-altitude venue, so the altitude channel is dead in this league and should be dropped rather than tested; (c) the league is small enough that distance and time-zone delta are highly collinear with the identity of a handful of West-coast clubs, so an apparent travel effect may be a team fixed effect. |
| **Complexity** | **Low–medium** (haversine + previous-game lookup + tz offset). |
| **Falsifier** | If the travel term adds nothing once `days_rest` and 7-day density are already in, it is redundant and should be dropped. If it appears *only* for the two or three most-travelled clubs, it is a team effect and should be rejected. |
| **Changes** | **ALLOC** most likely; **TOTAL** if the effect is real |

---

### A9 — Pairing-specific history: same-season head-to-head

| field | value |
|---|---|
| **Source** | opponent interaction (familiarity / style mismatch, measured directly) |
| **Mechanism** | Two routes, and I prefer the first. (i) **Direct pairing prior:** the realised pace of *this exact matchup's* earlier meetings this season is the most on-point estimate of how these two styles interact, capturing any mismatch effect without having to model it. Blend it with the incumbent by support. (ii) **Familiarity:** repeated meetings mean better scouting, fewer transition opportunities, more half-court possessions. |
| **Exact expected direction** | (i) The projection moves **toward the mean pace of prior same-season meetings**, by an amount increasing in the number of such meetings. (ii) Predicts **monotonically lower** projected possessions as prior-meeting count rises. **These two can conflict** and I flag that honestly: if the direct pairing prior is high, route (i) pushes up while route (ii) pushes down. Route (ii) should be tested as a *residual* effect after route (i), not alongside it. |
| **Affected stratum** | I verified support: **2100 / 2990** team-games (70.2%) have ≥1 prior same-season meeting with the target opponent; the distribution of prior-meeting counts is {0:890, 1:836, 2:746, 3:336, 4:66, 5:54, 6:40, 7:20}. Support is ample for the 1–3 buckets and thin beyond. |
| **Cutoff-valid inputs** | `opp_team_id` + schedule dates + lagged realised pace. All 2990/2990. |
| **Inputs exist?** | **Yes.** |
| **Overlap risk** | **Moderate with A2/A3** — the direct pairing prior is a non-parametric shortcut to the same opponent-interaction signal those arms model parametrically, so it will double-count. |
| **Leakage risk** | **Low if disciplined, and there is a specific trap:** "prior meetings this season" must be filtered by **date**, not by meeting index, and a playoff series makes this especially easy to get wrong. Also note the playoff stratum is by construction saturated with repeat meetings, so an unstratified H2H term will silently become a playoff term. |
| **Expected information gain** | **Low–moderate.** With 1–3 prior meetings the pairing prior is very noisy (a two-game mean of a quantity with sd ~3.9), so its optimal weight is small. It is most attractive as a *shrunk* addition, and shrinkage weight selection is a fitting question that belongs to a later stage. |
| **Complexity** | **Low.** |
| **Falsifier** | If the pairing-specific residual (prior-meetings pace minus the incumbent's projection for those meetings) shows no within-season persistence, there is no pairing effect and the arm dies. If route (ii)'s familiarity slope vanishes once season-phase is controlled, it was a proxy for time-of-season. |
| **Changes** | **TOTAL** |

---

### A10 — Expected competitiveness as a non-monotone driver of end-of-game possession inflation

| field | value |
|---|---|
| **Source** | opponent interaction (mismatch) + game environment (blowout / close-game dynamics) |
| **Mechanism** | Both tails of the expected-margin axis inflate possession counts relative to the middle, by *different* mechanisms. (a) **Close games:** trailing teams foul intentionally in the final two minutes, generating a burst of very short possessions and free-throw sequences (`end_reason = made_ft_final` accounts for 22,821 possessions league-wide). Close games also risk overtime (→ A6). (b) **Blowouts:** garbage time substitutes bench units and removes late-clock discipline. A pregame expected margin — computable from lagged net rating — should therefore predict possession count **non-monotonically**, U-shaped in \|expected margin\|. |
| **Exact expected direction** | Projection **raised** for expected-close pairings (mechanism a, which I believe is the stronger); projection **raised, if at all, weakly** for expected-blowout pairings (mechanism b — see the falsifying evidence below); **unchanged** for moderate expected margins. Net effect on the panel: it should specifically reduce the residual dispersion that currently reads as irreducible variance. |
| **Affected stratum** | Not currently broken out by the packet. Would be a new pregame-expected-margin stratum. |
| **Cutoff-valid inputs** | Lagged team net rating / point differential from `master_team` (`pts`, `opp_pts`, `plus_minus` — all 2990/2990) over strictly earlier games. |
| **Inputs exist?** | **Yes**, at full coverage across all six seasons. |
| **Overlap risk** | **High with A6** — expected closeness drives both the OT multiplier and the fouling burst, and they must not be counted twice. Recommend A6 first (it is a cleaner, larger, scale-level effect) and A10 as the residual. |
| **Leakage risk** | **The highest in the file.** `abs_score_diff_start`, `score_diff_offense_start/end`, `non_competitive_conservative`, `plus_minus` and `wl` on the target game are all realised outcomes and are exactly the fields one instinctively reaches for. Only a *pregame-predicted* margin may enter. An arm that accidentally uses realised margin will show a spectacular, entirely fake improvement. This is the arm I would gate hardest. |
| **Expected information gain** | **Moderate for mechanism (a); low for mechanism (b)** — see A11 for the evidence against (b). |
| **Complexity** | **Medium** (needs a pregame margin index, i.e. a small auxiliary estimator). |
| **Falsifier** | If realised possession counts show no elevation in the lowest decile of *predicted* \|margin\| after removing overtime games (so A6 is not doing the work), mechanism (a) is absent. |
| **Changes** | **TOTAL** and **CAL** |

---

### A11 — Purge non-competitive possessions from the trailing history *(included, expected to fail)*

| field | value |
|---|---|
| **Source** | game environment (garbage time) |
| **Mechanism** | If garbage-time possessions have a different tempo from competitive ones, then a trailing window containing blowouts measures a blend rather than the team's competitive tempo. `possessions_raw_v2.non_competitive_conservative` flags **14,593 / 238,563 possessions (6.12%)**, so the contaminated share is non-trivial. Purge those from history to get a competitive-pace index, then add back an expected garbage-time share for the target game. |
| **Exact expected direction** | Would shift each team's estimate toward its competitive-only tempo. |
| **Affected stratum** | Teams whose recent window contains a disproportionate share of blowouts. |
| **Cutoff-valid inputs** | `non_competitive_conservative` used **only as history** (it is a realised flag; on the target game it is pure leakage). |
| **Inputs exist?** | **Yes**, 100% populated. |
| **Overlap risk** | Moderate with A10. |
| **Leakage risk** | **High if misused** — the flag is realised. Lagged use only. |
| **Expected information gain** | **I expect this to fail, and I am including it so the negative is recorded before someone spends effort on it.** I checked the mechanism directly: mean possession duration is **15.126 s** for competitive possessions and **15.239 s** for flagged non-competitive ones — a difference of **0.11 s (0.7%)**, i.e. garbage-time possessions are *not* meaningfully faster. The premise that garbage time distorts tempo is not supported at the duration level in this dataset. |
| **Complexity** | Low. |
| **Falsifier** | Already largely falsified above. The remaining live version is a *count-rate* rather than duration argument (stoppage density differs even if per-possession duration does not), which would need its own diagnostic. |
| **Changes** | **TOTAL** if it worked; realistically nothing. Note the trap: purging history without the add-back is a **pure level shift**, which per S0.1 (marginal bias ≈ 0) will *hurt* MAE. |

---

### A12 — Season-phase environment: the early-season sign flip

| field | value |
|---|---|
| **Source** | game environment (season phase) |
| **Mechanism** | The packet's `by_game_no_in_season` panel contains a **sign flip** that no single mechanism explains: games 1–3 bias **−2.175** (under-projection), then games 4–6 and 7–10 flip to **+1.115 / +1.142** (over-projection), then 11–20 settles to −0.050 and 21+ to +0.279. A monotone "windows get better with more data" story predicts a *decaying* bias, not a *sign flip*. The flip implies a genuine early-season environment effect layered on top of the support effect: opening games run faster than any prior-based estimate (rust, fewer set plays, more transition, fresh legs after the off-season), and then games 4–10 run slower than a window still anchored on those unusually fast openers. |
| **Exact expected direction** | Raise the projection for a team's games **1–3**; lower it for games **4–10**; leave 11+ alone. |
| **Affected stratum** | `game_no_in_season` 1–3 (n=228, MAE **3.777** — the worst non-degenerate stratum in the panel) and 4–10 (n=532, MAE ~3.05). Together 760 team-games, **25.5%** of the panel, all above the overall MAE of 2.903. |
| **Cutoff-valid inputs** | `team_game_index` (present in the contract, range 0–55) or equivalently a count of prior same-season games — schedule-derived, 2990/2990. |
| **Inputs exist?** | **Yes.** |
| **Overlap risk** | **Very high — the highest in the file.** These strata are largely the *same rows* as the `support` 3–4 / 5–9 and `pace_level` 2/3 strata, so any cold-start or window source will be operating on them too, from a different causal story. **Only one of the two stories can be right**, and the discriminating test is whether the flip survives conditioning on support. I flag this explicitly rather than claim the territory. |
| **Leakage risk** | **Very low.** |
| **Expected information gain** | **High if the environment story is right; zero if the support story fully explains it.** Genuinely uncertain — this is the hypothesis I am least able to adjudicate from the packet alone, because the packet does not cross-tabulate `game_no_in_season` against `support`. **That cross-tab is the single most valuable additional diagnostic the coordinator could commission**, and it is cheap. |
| **Complexity** | **Low** (a phase-indexed offset) — but it is a *fitted* offset, so it needs proper out-of-sample discipline or it will simply memorise the panel. |
| **Falsifier** | Cross-tabulate `game_no_in_season` against `support`. If, holding support fixed at 10 (full window), the early-season sign flip disappears, the effect is support, not season phase, and this arm should be withdrawn in favour of the estimator-form lane. |
| **Changes** | **TOTAL** and **CAL** |

---

### A13 — Playoff environment *(included, expected to fail)*

| field | value |
|---|---|
| **Source** | game environment (playoff vs regular season, game importance) |
| **Mechanism** | Playoff basketball is conventionally slower: shorter rotations, more half-court execution, more timeouts, higher leverage per possession. One might add a playoff offset or a series-game-number term. |
| **Exact expected direction** | Would lower the projection for playoff games. |
| **Affected stratum** | `season_type = Playoffs`, n=212 (7.1%). |
| **Cutoff-valid inputs** | `season_type` (2990/2990) plus schedule-derived series position. |
| **Inputs exist?** | **Yes.** |
| **Overlap risk** | Moderate with A9 (playoff series are saturated repeat meetings). |
| **Leakage risk** | Low for `season_type` itself. Series *elimination* status is schedule-plus-results and needs care: whether a game is an elimination game depends on prior games' outcomes, which is cutoff-valid, but whether a *scheduled* game is played at all is not knowable when the series can end early — a subtle survivorship issue in any series-position feature. |
| **Expected information gain** | **Near zero, and I expect this to fail. I am including it because it is named in my mandate and because the packet's evidence points the other way, which is worth stating.** The packet shows playoffs are **already the best stratum**: MAE **2.422** vs regular season **2.940**, and bias **−0.074** — essentially unbiased. There is no level error to correct and less dispersion than elsewhere. With n=212, any playoff-specific offset is far more likely to memorise noise than to find structure. |
| **Complexity** | Low. |
| **Falsifier** | Already effectively falsified by the packet's own `by_season_type` panel. Any playoff arm that *appears* to help should be treated as overfitting until it replicates on a held-out post-season. |
| **Changes** | **ALLOC** at best |

---

## S2 — CATEGORY B: high-value but unavailable

These may **not** become arms in `TEAM_POSSESSION_PRIOR_V2`. They belong to a data roadmap.

### B1 — Officiating crew assignment, joinable to `game_id`

- **Missing input:** referee crew identity per game, keyed to the contract's `game_id`.
- **Why it may matter:** officiating is one of the strongest tempo levers in basketball and the one this program is most blind to. Whistle rate drives free-throw sequences, and `end_reason` shows **22,821 possessions ending in `made_ft_final`** plus 588 technical-FT sequences — roughly 10% of all possessions terminate at the line. A crew's foul-call tendency is a persistent, measurable, *pregame-announced* quantity in most leagues, and it plausibly moves possession counts by more than several of my Category A arms combined.
- **Minimum viable collection:** the repository already has `data/ref_assignments/` and `data/officials_master.csv`, but the packet records **0 of 1495 contract games overlap** and `officials_master.csv` "carries no game_id join at all." The MVC is therefore not new scraping but a **join key**: map officials rows to contract `game_id` via (game_date, home team) and backfill. If the existing rows genuinely do not span 2021–2026, then a forward capture of the league's daily crew posting plus per-crew trailing foul-rate aggregation.
- **Prospective-only validation?** **Depends entirely on whether the historical rows can be keyed.** If the join can be repaired retrospectively over the existing span, full retrospective validation is possible and this becomes the highest-value item on the roadmap. If not, prospective only.
- **Expected value of closing the gap:** **Highest of any missing input.** Distinct mechanism, persistent signal, genuinely pregame-announced, and currently at zero coverage rather than partial — meaning the whole effect is unmeasured, not just noisily measured.

### B2 — Pregame availability feed with historical depth, focused on ball-dominant players

- **Missing input:** a captured-as-of pregame injury/availability report spanning 2021–2026. The packet confirms `data/injury_capture/injury_log.csv` covers **2026-07-30 .. 2026-08-04 only** — six days of a five-season span.
- **Why it may matter:** tempo is partly a *personnel* property and the effect is concentrated, not diffuse: losing a primary ball-handler or the team's transition engine plausibly changes possession rate far more than losing an equivalent-minutes big. A generic "star out" flag would blur this; the useful version is availability **weighted by the absent player's lagged share of transition and early-clock possessions**, which `possessions_raw_v2` (`off_p1..off_p5`, `duration_sec`) could compute *if* the availability side existed.
- **Minimum viable collection:** persist the existing capture forward from 2026-07-30 with a genuine as-of timestamp; separately attempt an archival backfill. **Backfilled availability is not the same artifact as captured availability** and must be labelled as such — the producer's own Tier-B episode is the cautionary precedent.
- **Prospective-only validation?** **Yes** for any honest version. A backfilled report carries retrospective-observation contamination even when its effective date is correct.
- **Expected value:** High mechanistically, but slow — a prospective-only feature needs seasons of accumulation before it can be validated at the resolution this program demands.

### B3 — Coaching identity and coaching-change events

- **Missing input:** a coach-by-team-season (ideally coach-by-team-game) table. The packet's sweep finds **no coaching source anywhere in the repository**.
- **Why it may matter:** pace is arguably the most coach-determined team-level property in basketball. A coaching change is a **structural break** that a 10-game trailing window cannot see and will actively fight, mis-projecting for exactly the ~10 games after the change. It is also a candidate explanation for part of the `team_window_prior_season` bias of −2.845 (A5): a team's prior season may have been coached by someone else entirely.
- **Minimum viable collection:** a small hand-maintained table — roughly 13–15 teams × 6 seasons plus mid-season changes, on the order of 100 rows. **This is by far the cheapest item on the roadmap.**
- **Prospective-only validation?** **No.** Coaching identity is public historical record; a hand-built table is fully retrospectively valid, and a coaching change is knowable pregame by definition.
- **Expected value:** **Best value-per-hour on the roadmap.** ~100 rows of manual entry unlocks a structural-break indicator, an interaction with A5, and a plausible partial explanation for the worst-biased stratum in the panel.

### B4 — Scheduled tip time and broadcast window, at full historical coverage

- **Missing input:** tip time for the whole span. This is *partially* present — see S6 — but **not sufficiently complete for Category A**, which is why it is here.
- **Coverage as verified:** `data/reference/tip_times.csv` covers **1219 / 1495 games**, by season: 2021 **0/209**, 2022 180/239, 2023 259/260, 2024 261/262, 2025 310/310, 2026 209/215. The contract's own `scheduled_tip_time` is thinner still (26.8% of team-games; 0% for 2021–2024).
- **Why it may matter:** afternoon and "getaway" games, and nationally-televised windows with longer commercial breaks, plausibly shift both fatigue and stoppage structure. Verified distribution: `tip_hour_local` is 19:00 for 706 games but 11:00–15:00 for 302 games — a real, sizeable day-game population.
- **Why not Category A:** three independent disqualifiers. (i) **2021 has zero coverage, and 2021 is the worst-MAE season (3.134)** — the feature is absent from exactly the stratum most in need of help. (ii) The provenance is odds-derived (`source_table` = `drive_master` 813 / `extension` 406), i.e. **retrospectively assembled**, and `n_commence_variants > 1` for 36 games shows the recorded time is a *reconciled* value, not necessarily the pre-tip scheduled one. (iii) A tip time's *value* is schedule-knowable weeks ahead, but its *capture* here is not as-of — the same distinction that sank the producer's transaction Tier B.
- **Minimum viable collection:** a properly as-of captured schedule feed with tip time and broadcast designation, plus a retrospective backfill of 2021 from league schedule archives (which are public and static, so a backfill here is far more defensible than a backfill of injury status).
- **Prospective-only validation?** **No, if the 2021–2022 backfill comes from an official published schedule archive.** Yes, for broadcast-designation history if no archive exists.
- **Expected value:** Moderate. Worth doing because the backfill is tractable and the feature is genuinely pregame; not worth doing before B1 or B3.

### B5 — Neutral-site, relocated, and arena-change flags

- **Missing input:** a per-game venue override. `team_cities.csv` gives each team **one home arena per season** and the join is clean (S6), but it therefore **silently mis-locates** any neutral-site game, one-off relocation, in-season arena change, or international/showcase game.
- **Why it may matter:** it is a **correctness dependency for A8** — a mis-located game injects a false travel distance for both sides. It is also a small environment effect in its own right (neutral crowd, unfamiliar floor).
- **Minimum viable collection:** a short exceptions table of game_id → actual venue, built by diffing scheduled venue against the league's published game notes. Likely a few dozen rows over six seasons.
- **Prospective-only validation?** **No** — public historical record.
- **Expected value:** Low on its own; **necessary** if A8 is pursued.

### B6 — League rule-change and point-of-emphasis log

- **Missing input:** a season-indexed record of rule changes and officiating points of emphasis (shot-clock reset rules, defensive-three-seconds emphasis, flagrant/take-foul rules, transition-foul rules).
- **Why it may matter:** this is the **causal mechanism behind A5**. A5 proposes a blind drift correction; a rule-change log would tell us whether the drift is a smooth trend (extrapolate it) or a set of step changes at specific season boundaries (do not extrapolate — apply the step). Those two produce *different* corrections at the next season boundary, and getting it wrong is worse than not correcting at all.
- **Minimum viable collection:** one row per season with a short structured description; ~6–10 rows.
- **Prospective-only validation?** **No** — public record.
- **Expected value:** **High relative to cost.** Almost free, and it converts the highest-expected-value Category A arm from a blind extrapolation into a defensible one.

### B7 — Market total with genuine history

- **Missing input:** historical market totals. The packet records `data/odds_capture/` as **2026-07-31 .. 2026-08-06 only**.
- **Why it may matter:** a market total is an external consensus that already prices tempo, injuries, rest and officiating jointly. As a *benchmark* it would bound how much of the residual variance is even in principle predictable — which the packet's `variance_explained_vs_target = 0.116` currently leaves entirely open.
- **Minimum viable collection:** persist odds capture forward with as-of timestamps.
- **Prospective-only validation?** **Yes.**
- **Expected value:** **High as a diagnostic ceiling, questionable as a feature.** I endorse the packet's own caution: a market feature changes what the model *is*. My additional recommendation: even if it is never used as a feature, capture it as a **benchmark** — knowing whether the market's possession-total error is 2.9 or 1.9 tells us whether this entire program has headroom, and nothing else in the inventory can tell us that.

---

## S3 — Leakage traps specific to this lane

Recording these because my lane touches the two most leak-prone ideas in the whole design space
(expected margin and game length), and a coordinator merging several sources should be able to see the
traps without re-deriving them.

| Field | Why it is a trap |
|---|---|
| `is_overtime`, `max_period`, `period` | Realised game length. Only *predicted* OT may enter A6. |
| `abs_score_diff_start`, `score_diff_offense_start/end` | Realised in-game score state. Fatal to A10. |
| `non_competitive_conservative` | Realised garbage-time flag. Lagged-history use only (A11). |
| `wl`, `plus_minus`, `pts`, `opp_pts` on the target game | Realised outcome. Only lagged aggregates. |
| `master_team.observed_time` | Post-game capture timestamp, not a pregame quantity. |
| Opponent's **full-season** pace in A2/A3 | Includes post-target games. Must be strictly-earlier-dates. |
| "Prior meetings this season" in A9 | Must filter by date, not meeting index. |
| Playoff series position in A13 | Whether a scheduled series game is played depends on earlier results — a survivorship subtlety. |

---

## S4 — Corrections and additions to the frozen packet's inventory

The packet is frozen and I have not modified it. These are recorded here for the coordinator.

1. **`data/reference/team_cities.csv` exists.** The packet lists travel/time-zone as `ABSENT` —
   "would need venue geocoding … derivable in principle from a venue table that does not exist here."
   The table does exist: 16 rows, 15 team_ids, with `city`, `arena`, `lat`, `lon`, `elevation_ft`,
   `timezone`, `first_season`, `last_season`. I verified a season-aware join resolves **exactly one
   arena for all 76 team-seasons** with no misses and no ambiguity (it correctly handles the
   `PHO → PHX` abbreviation change under a stable `team_id`, and the 2025 GSV / 2026 PDX expansions).
   This **promotes travel and time-zone from Category B to Category A** (A8), subject to B5.
2. **`data/reference/tip_times.csv` exists** with 1219/1495 games. Not Category-A-complete
   (2021 = 0), and the provenance is odds-derived rather than as-of captured. Recorded as B4.
3. **The operational turnover target is a raw whole-game count, while the incumbent projection is
   regulation-equivalent.** Verified: `team_turnover_reconciliation_v1.team_off_possessions` equals
   the raw `possessions_raw_v2` count for **2990/2990** team-games. OT team-games (n=132) average
   **89.96** raw possessions vs **79.32** for regulation games. The packet's diagnostic panel cannot
   see this because its realised target is itself regulation-equivalent — which is why the `went_ot`
   stratum shows *better* MAE (2.367) than non-OT (2.928). This drives A6 and is, in my judgement,
   the most consequential item in this file after S0.2.

---

## S5 — Where I am uncertain, and what I expect to fail

**Stated plainly, as instructed.**

**Uncertainties I could not resolve within my evidence scope:**

- **A6's blocking prerequisite.** I did not read the downstream turnover scorer. Repository grep shows
  ~34 files reference `projected_team_off_possessions`, including `run_p3_downstream.py` and
  `run_turnover_p1.py`, but reading them exceeds my declared evidence scope and risks contaminating
  independence. **If the operational pipeline already normalises for game length, A6 is void.**
  I chose the boundary over the answer; someone must check this before A6 is registered.
- **A12 vs the support story.** The packet does not cross-tabulate `game_no_in_season` against
  `support`, so I cannot tell whether the early-season sign flip is an environment effect or a
  restatement of thin-window behaviour. **That cross-tab is the cheapest high-value diagnostic
  available and I recommend commissioning it before any early-season arm is registered.**
- **A5's causal basis.** The −2.845 prior-season bias reads as league-wide upward tempo drift, but I
  cannot rule out that it is a *composition* effect — the prior-season-fallback stratum is
  disproportionately expansion and roster-churn clubs (GSV enters 2025, PDX enters 2026). A drift
  correction and a composition correction point in different directions at the next season boundary.
- **The overall ceiling.** `variance_explained_vs_target` is 0.116 and residual sd is 3.674 against a
  target sd of 3.908. Much of the remainder is genuinely irreducible — whistle variance, rebounding
  luck, and the near-random within-game gap documented in S0.2. **I do not believe the hypotheses in
  this file, even all of them together and all working, move overall possession MAE by more than a few
  percent.** The exception is A6, which is not a variance reduction at all but a measurement-basis
  correction, and could move *operational* turnover error more than the rest combined.

**Hypotheses I expect to fail, included deliberately:**

| # | Why included | Why I expect failure |
|---|---|---|
| **A11** garbage-time purge | The premise is intuitive and someone will propose it. Recording the disconfirming measurement now saves that effort. | Directly checked: non-competitive possessions average **15.239 s** vs competitive **15.126 s** — 0.7% apart. The tempo-distortion premise is not supported. |
| **A13** playoff environment | Named in my mandate; the packet's evidence points the other way and that deserves to be on the record. | Playoffs are **already the best stratum** (MAE 2.422, bias −0.074). No level error to correct, n=212, high overfit risk. |
| **A8** travel | Now cheap (S4.1) and in my mandate; the negative result is worth having. | Likely absorbed by rest (A7); collinear with a handful of West-coast team identities; `elevation_ft` spans only 20–2030 ft so the altitude channel is dead in this league. |
| **A4** home/away split | Explicitly in my mandate; its absence should be a recorded negative rather than an untested assumption. | League-average home/away possession-duration gap is **0.17 s (~1.1%)**, and splitting the window halves support in exactly the strata that already have the worst MAE. |

**The hypothesis family I deliberately did *not* propose:** anything that gives the two sides of a game
different possession totals. Per S0.2 the realised gap averages 0.886 possessions and is 97.1% within
±2, and it is essentially determined by who holds the ball at each period buzzer. The ceiling is ~15%
of MAE under perfect prediction of a near-random quantity. **The incumbent's symmetry is not a defect
worth attacking**, and I would rather spend my one recommendation on saying so than on an arm I expect
to be noise.

---

## S6 — Suggested ordering, if only a few arms can be run

Ranked by expected value per unit of implementation risk, not by expected effect size alone.

| Rank | Arm | Rationale |
|---|---|---|
| 1 | **A6** expected game length | Largest operational effect if the prerequisite clears; a measurement-basis correction, not a variance play. **Verify the prerequisite first.** |
| 2 | **A5** league drift + un-stale league prior | Near-pure bias correction where \|bias\|/MAE = 0.77; no new data; two arithmetic changes to existing code paths. |
| 3 | **A1** duration-space combination | Sign-certain, no fitting, no new source, low overlap. Best effort-to-confidence ratio. |
| 4 | **A3** offense/defense decomposition | Most principled opponent adjustment; subsumes A2. |
| 5 | **A12** season phase | Potentially large, **but run the support cross-tab first** — it may belong to another lane entirely. |
| 6 | **A7** rest and density | Clean monotone signal in the packet, but confounded; needs simultaneous season-phase control. |
| 7 | **A10** expected competitiveness | Real mechanism, highest leakage risk in the file; gate hardest. |
| 8 | **A9** head-to-head | Cheap, noisy, overlaps A2/A3. |
| 9–12 | A2, A4, A8, A11, A13 | A2 only if A3 is not run. The remainder are documented negatives. |

Roadmap priority (Category B): **B3 coaching** (~100 rows, fully retrospective, unlocks a structural
break and interacts with A5) → **B6 rule log** (~10 rows, makes A5 defensible) → **B1 officials**
(highest ceiling; first step is repairing a join, not new scraping) → B5 → B4 → B7 → B2.

---

*Nothing in this file was fitted, tuned, selected or scored. No existing file was modified. Nothing was
registered, committed, or written to the registry. Every quantitative statement above is either quoted
from the frozen evidence packet or is a field-existence, coverage, or field-semantics property of a
frozen artifact, computed without reference to any projection or model output.*
