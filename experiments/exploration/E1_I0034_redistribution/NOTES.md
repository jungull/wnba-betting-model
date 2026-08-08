# NOTES — E1_I0034_redistribution

The narrative: what I expected, what happened, and where the two parted company.

Preregistration `8963b3464f8b6b930940ddf42fe4cbe5f37776ee82bec0d1af79163bc0741b70` (18,575 bytes,
14 cells). Primary window 2023–2024, 8,118 remaining-player-games in 888 team-games. Holdout never
opened.

---

## 1. What I expected

E1_I0033 handed me a clean setup. It had shown, on a powered interval, that when a pre-game top-3
player is absent the team's realised shortfall is 0.085 points against a naive 15.815 (β = +0.0284,
95% CI [−0.0569, +0.1137], β = 1 rejected at 22.3 null sd). Its closing line was that the team
scores the same but *different people score them*, and that this redistribution is the entire
content of a player-props market.

I expected to find, in rough order of confidence:

1. That the minutes redistribution would be **near-total** — minutes are a 200-minute fixed budget
   (D104), so an absent player's 24 minutes have to go *somewhere*.
2. That the allocation would be **concentrated** on the next player down the depth chart, and
   probably on a position match, because that is how basketball rotations visibly work.
3. That **attempts** would show the strongest structure, because D111 found attempts pay the
   largest bottom-up penalty (49.6%) — the fingerprint of a shared budget nobody is enforcing.
4. That **points** would follow minutes and attempts mechanically.

**Three of those four were wrong**, and the fourth was right for a reason I did not anticipate.

---

## 2. The build, and three anchors

I rebuilt the data path from the manifest-verified sources rather than reading E1_I0033's
intermediate parquets, which carry no manifests. The identity map was reconstructed from
`cbs_obligation_key` and agrees with the manifest-verified contract v4 on **all 22,659 rows**.

Then the anchors, before any new statistic, with an assert that halts on failure:

| | published | reproduced |
|---|---|---|
| D104 home advantage | +0.965090 over 888 games | +0.965090 over 888 games |
| D076 appeared player-games (tier A) | 13,879 | 13,879 |
| E1_I0033 RS1 team-games | 1,392 | 1,392 |
| E1_I0033 pre-game top-3 rows | 4,176 | 4,176 |
| E1_I0033 top-3 appearance rate | 0.9411 | 0.9411 |
| E1_I0033 top-3 mean forecast points | 14.341 | 14.3408 |
| E1_I0033 absence team-games | 183 | 183 |
| E1_I0033 naive points lost | 15.815 | 15.8151 |

All exact. The data path is the programme's.

**One decision was forced immediately.** Both pre-game absence sources —
`data/injury_capture/injury_log.csv` and `data/injury_history/injury_history.csv` — return
`manifest_present: false` / UNVERIFIABLE, and the injury log covers 2026 only in any case. So the
absence indicator had to be realised, and **every forecast cell in this screen is an oracle
ceiling**. That is a real limitation, but it is also the right instrument: if a *perfect* absence
forecast buys nothing, the question closes regardless of how forecastable absence is.

---

## 3. Four probes, and the design they forced

I ran four declared probes before writing PREREG.md. They are all in the run logs and PREREG.md §9
lists exactly what they looked at. Two of them destroyed my starting design.

**Probe 1** produced a concentration statistic of **2.98 × 10⁹** because it divided by a near-zero
freed volume. Discarded (DEFECTS D-1).

**Probe 2** was the useful failure. A proportional-to-baseline allocation — big players absorb more
— had a within-team-game correlation with the realised gain of **−0.2577**. The wrong sign. The
players predicted to absorb most absorbed least.

**Probe 3** found out why my rotation was wrong. I had inherited E1_I0033's ranking by the
champion's `p_active_hat × min_hat`. **6.12% of the pre-game top-8 have fewer than three prior
appearances that season**, carrying a declared-constant `p_active_hat` of 0.816 against a
prefix-mean `min_hat` of 21.63 — an expected 17.6 minutes for a player who has never played, which
ranks fifth to eighth on many teams. At K = 8, **only 43% of "absence" team-games had an absentee
with any playing history at all.** In the rest, the "absent starter" was a roster entry that was
never going to play. This is D111 ruling 3 seen from a different angle, and it would have biased
the entire screen toward null (DEFECTS D-2).

So I threw the champion ranking out and defined the rotation by **the player's own strictly-prior
trailing-5 minutes**. Phantom-free, pre-game knowable, and every member has a baseline by
construction.

Probe 3 also ran the control that mattered: the same −0.26 correlation, measured in team-games with
**no absence at all**, is −0.111 for minutes against −0.186 with absence. **Most of "big players
absorb least" is mean reversion in a noisy trailing average, not a redistribution effect.** That
put the mean-reversion main effect in the base of every model, before any allocation term.

**Probe 4** killed my preregistered team-level cell before it was preregistered. I had intended a
"closure" cell — do the remaining players absorb the freed volume? For minutes that is an
*identity*: the remaining established players' total is `200 − (call-up minutes)`, so conditional on
their own baselines it has nothing to do with the absence, and a "closure β" can be made to come
out at 1.00 or at 0.28 purely by choosing what to condition on. I rewrote it as a **leakage** cell,
which is not an identity (DEFECTS D-5).

---

## 4. The ceiling, computed before anything was fitted

| channel | corr(Δ, redistribution term) | ΔR² on the level response | ceiling ΔMAE | vs D103's 0.00102 floor | vs the programme's largest live effect 0.002057 |
|---|---:|---:|---:|---:|---:|
| minutes | +0.1168 | 0.00470 | 0.0329 | 4.6× above | 2.3× above |
| attempts | +0.0826 | 0.00258 | 0.0087 | 2.5× above | 1.3× above |
| points | +0.0528 | 0.00146 | 0.0059 | 1.4× above | **0.7× — below** |

This is unusually large for this programme. The preregistration ruled, in advance, that minutes and
attempts clear the floor and are fitted, and that **points would be fitted but its verdict quoted
with the ceiling attached**. Points then returned nothing, exactly as the ceiling said it might.

---

## 5. What actually happened

### Expectation 1 — "the redistribution is near-total" — WRONG, and the reason is the finding

The pooled slope of established-player gain on freed volume is **0.2822**, not 1.0. My first
instinct was that this was a roster-size confound, and partly it is. But the real explanation only
appeared when I computed what the remaining players' own trailing form sums to:

| absent playing time | team-games | remaining players' recent minutes sum to | slack vs 200 | realised gain |
|---|---:|---:|---:|---:|
| none | 261 | 198.96 | +1.0 | −3.24 |
| 0–15 | 220 | 201.08 | −1.1 | −2.59 |
| 15–30 | 171 | 201.50 | −1.5 | −3.01 |
| 30–45 | 124 | 191.44 | +8.6 | +6.36 |
| 45+ | 112 | 184.02 | +16.0 | +15.47 |

**Below about 30 minutes of absence there is no slack.** The remaining players were already, on
their own recent form, playing the whole 200 minutes between them; the absentee's minutes had
already been priced into everyone else's recent averages. Only above that does real slack open, and
then the gain tracks it nearly one-for-one.

The arithmetic behind the surprise: a player's trailing-5 is computed over games she **played**,
which are systematically her higher-minute games. Summed over a team's established players these
baselines reach **249.9 minutes** against a 200-minute budget in heavy-absence games. So the "freed
volume" is an overstatement, and by the most in exactly the games that define the treatment
(DEFECTS D-4).

And it does not leak out. P01: θ = −0.030 / −0.033 / −0.039 for minutes / attempts / points; full
leakage (θ = 1) is **59.6 null sd away** and the null is verified able to see it (planting θ = 1.0
recovers 0.970 at p = 0.001). Call-up minutes are flat at 2–4 per game across every bucket.

### Expectation 2 — "the allocation is concentrated on the depth chart" — WRONG

No pre-game predictor reaches 1.5% of the within-team-game variation in who benefits. The
preregistered tilt cell is not established in any channel (γ = −0.035 / +0.058 / +0.043 against
80%-power floors of 0.083 / 0.131 / 0.181). Position match is +0.099 at p = 0.044 against a floor
of **0.153** — the exact "significant and underpowered" pattern D103 was written for. Against an
actual spread of ±6 minutes per player, this is unforecastable.

I did not expect this. It is the single most commercially consequential result in the screen,
because it says the thing a props book would most want — *which* player picks up the slack — is not
available from anything in this dataset.

### Expectation 3 — "attempts show the strongest structure" — WRONG, and I nearly published the opposite

P03_fga came out at +0.00736, p = 0.0235. I would have reported that as a small positive. Then the
stratification:

| P03_fga stratum | n | ΔMAE | p |
|---|---:|---:|---:|
| ALL | 8,118 | +0.00736 | 0.0235 |
| FREED > 0 | 5,593 | +0.00356 | 0.4126 |
| FREED ≥ 25 min | 2,475 | −0.00387 | 0.6815 |
| **FREED = 0** | 2,525 | **+0.01579** | **0.00055** |

**The entire pooled gain is produced on rows where the treatment term is identically zero.** Because
M1's intercept and slopes are fitted jointly with the redistribution terms, the rest of the model
moves even where the terms contribute nothing. It is coefficient refitting, not attempt
redistribution, and it reverses sign where the treatment is strongest (DEFECTS D-3).

So D111's prediction — attempts are where the shared-budget constraint should bite hardest, because
they pay the largest bottom-up penalty (49.6%) — **does not survive at the individual-player level.**
Worth recording as a specific, falsified prediction rather than a vague null.

### Expectation 4 — "points follow mechanically" — right in direction, wrong in sign

Points does follow minutes. It follows them **downward**. On the ≥25-minute stratum:

| | P03 vs trailing-5 | P04 vs champion |
|---|---:|---:|
| minutes | **+0.1228** (2.34%, p 0.00005) | **+0.0927** (1.82%, p 0.0003) |
| attempts | −0.0039 (p 0.682) | −0.0001 (p 0.993) |
| points | **−0.0366** (−0.84%, p 0.00015) | **−0.0485** (−1.17%, p 0.0008) |

Adding the redistribution term makes points **worse**, decidedly so under the analytic floor, in
both bases and on both treated strata. Under the injection-verified correction for the points
response (~2.6×, §7) those verdicts soften to NOT ESTABLISHED — but **not one of the four treated
points cells is positive**, and the consistency of the direction is itself informative.

The most likely reading: extra minutes go to bench players whose points-per-minute is both lower
and noisier than the model's fitted conversion assumes, so a term calibrated on the pooled
relationship over-predicts their scoring. That is a hypothesis this screen does not test.

---

## 6. The coordinator's correction, and what it changed

Mid-screen the coordinator flagged E1_I0036 (severity A): injecting a planted effect onto
**shuffled residuals** destroys the response structure the null fails to destroy, so an injection
test can certify a null that is blind to the real candidate. The demonstrated case is a
within-player cyclic null that passed injection at power 0.95 and has power 0.00 against a
between-player candidate.

Three things, and I added a whole step (`s09`) for them. **This is the one addition after the hash
and it made the headline weaker, not stronger.**

**(a) My injections were already component-wise.** Every injection in `s07` adds `plant × candidate`
to the **real** response and reruns the entire path. I ran the shuffled-residual construction beside
it anyway (`injection_style_comparison.csv`) and it **systematically attenuates the recovered
effect** — at 2 null sds on minutes it recovers 0.024 component-wise against −0.001 shuffled. The
correction is confirmed on this screen's own data.

**(b) The level of every candidate, measured rather than asserted.** The tilt candidates are
**95.3–96.0% within-team-game between-player** — precisely the direction the coordinator warned
about. Their null is a **within-team-game player swap**, which is the matched null. The forecast
term is **100% team-game** (zero within-team-game variance, by construction) and its null blocks at
team-game. **No within-player cyclic shift is used anywhere in this screen**, and `redist_base.py`
said so in its docstring before the correction arrived.

**(c) The blindness demonstration, which I ran because arguing is weaker than showing.** A
between-player effect of 4 null sds planted into the minutes tilt:

| null | p | detected |
|---|---:|---|
| within-team-game **player swap** (mine) | **0.0017** | **YES** |
| within-**player** cyclic shift (the degenerate one) | **0.8087** | NO |

E1_I0036 reproduced exactly, on this screen's own candidate.

**(d) The absorption tell, on all 14 cells.** **Zero** cells have a null mean exceeding their
observed statistic. **One** fires the warning: `P02_TILT_minutes`, null mean −0.0232 against an
observed −0.0349 — same sign, 67% of the observed. That cell's "diffuse" reading is weaker evidence
than its p = 0.673 suggests, and it is carried as NOT ESTABLISHED (DEFECTS D-6).

**(e) D113 on the MDE.** The block-bootstrap sampling sd **matches** the analytic null sd (ratio
0.963–1.013 over six cells), so the variance estimate is sound and **the ~6.6× claim does not
reproduce here**. But a simulated power curve — planted effect × block bootstrap × full null, 60
replicates per level — shows the *power rule* is anti-conservative:

| cell | observed ΔMAE | analytic MDE80 | empirical power at the observed effect | injection-verified MDE80 | ratio |
|---|---:|---:|---:|---:|---:|
| P03_minutes | 0.0295 | 0.0253 | **0.783** | 0.0308 | 1.22× |
| P03_fga | 0.0074 | 0.0092 | **0.300** | 0.0148 | 1.61× |
| P03_pts | 0.0023 | 0.0089 | **0.033** | 0.0301 *(extrapolated)* | 3.40× |

**This hit my own headline.** Under the analytic rule the pooled minutes cell is decided. Under the
injection-verified floor it sits just below it at 78.3% power. I downgraded it to *at the boundary*
and moved the headline onto the ≥25-minute stratum, which sits at 4.68 null sds against an
injection-verified threshold of 3.41 (DEFECTS D-7). Rescaling everything to those thresholds also
**withdraws my own points-negative verdicts** — −4.01 and −3.28 null sds against a points threshold
of 9.50 — so the correction cost me a positive *and* a negative headline.

---

## 7. Verification summary

* Type-I: N2 rejection rates **0.0575 / 0.0525 / 0.0400** over 400 synthetic no-effect datasets
  each; N1 **0.033 / 0.067 / 0.050** over 60 each.
* No-op placebo: deviation **exactly 0.0** on all three channels, with the transform asserted to be
  the identity permutation so the check is not vacuous.
* Negative control (P06): pseudo-absences on a **disjoint** row set — team-games where nobody sat —
  ΔMAE −0.00067, p 0.8175, floor 0.00796. **Passes.**
* Injection recovery: every null recovers a planted effect at or below 2.8 of its own null sds
  except P01, which detects at 4 sd and detects full leakage (θ = 1) at p = 0.001.
* Retrospective baseline: checked two ways — the first row of every player-season block is NaN in
  all three channels, and one row was recomputed by brute force to 0.00e+00 error. No season
  aggregate and no same-game quantity enters any baseline.
* Reference completeness (D087): every analysis column has coverage **1.000000** on the cell row
  set, asserted; position group is known on **1.0000** of rows where an absence is present.
* Column selection: three explicit allowlists, resolved, printed and length-asserted. **No
  substring matching anywhere.**
* Partition: `assert_partition` on column values after every load and every filter. Seasons 2025
  and 2026 never read.

---

## 8. What is NOT established here

* Anything about **absence forecastability**. The indicator is realised. Every forecast number is a
  ceiling. D090 already bounds the availability forecast; this screen does not touch it.
* Anything about **variance or tails** — E1_I0033's reading R-C remains untouched. This screen
  measures point-forecast MAE only.
* **Why** the points term is harmful. The bench-conversion hypothesis in §5 is a hypothesis.
* The **shape** of the allocation. "Diffuse" here is a not-established verdict on a statistic that
  flips sign between windows (the attempts tilt goes +0.058 → +0.109, p 0.007, and points
  +0.043 → +0.161, p 0.007, when 2022 is added — both still below their own power floors). Anyone
  wanting the shape rather than its unforecastability needs more data than 2021–2024 contains.
* Anything about **playoffs** — regular season only, for D104's structural reason.
* Anything about **2025–2026**. Sealed.
