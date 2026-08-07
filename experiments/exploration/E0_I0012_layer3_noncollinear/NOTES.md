# E0 I0012 — Layer 3 (matchup interaction) at PLAYER level, non-collinear formulations

**Status: E0 exploration sweep. Non-claiming.** No registry entry, no preregistration, no
leaderboard row, no promotion threshold. Everything below is a **lead or a kill**, never a result.

**Partition: 2021–2024 only.** The 2025/2026 confirmation holdout was never read, joined, counted,
plotted, filtered against, or described. Verified in `run_log_partition_verification.txt` by
parsing every written CSV and testing the *values* of its season and date columns — not by a
byte-scan for "2025"/"2026", which previously produced a false violation by matching row counts and
digit runs inside floats.

---

## 1. What this sweep was for

I0010 tested **defence-vs-position** and was killed on all three targets, for a specific reason:
positional allowance was **overall opponent defensive strength wearing a position costume**
(r = +0.57/+0.58/+0.59 with overall defence within season; 93–94 % of its variance for reb/ast was
*between-position*).

That killed the positional **formulation**, not layer 3. The open question was whether a matchup
variable that is genuinely **not** collinear with overall team defence carries anything. This sweep
built four such formulations and screened them.

## 2. The design rule, applied to every formulation

> Residualize the candidate M against overall opponent defensive strength **first**, then test
> whether the residual carries signal.

Concretely, the base model every candidate must beat is

```
y ~ O + D + O*D
```

where `y` is the player-game per-100-possession rate, `O` is the player's pregame expanding own
rate, and `D` is the opponent's pregame expanding **overall** allowance (computed excluding the
player's own prior contribution to it, so a player is never part of the defence he is matched
against). `M` is centered within season, regressed on `D` and `O*D`, and only the residual `Mres`
and the interaction `O × Mres` are ever tested.

For every formulation I report (a) raw correlation with overall opponent defence within season,
(b) between- vs within-group variance decomposition against the relevant **nuisance** grouping, and
(c) split-half reliability of the constructed measure.

**A note on (b) that matters for reading the numbers.** For I0010 the disqualifying decomposition
was *between-position*, because position was a nuisance. Here, for team-level style variables, a
high *between-opponent* share is **not** disqualifying — the opponent is the treatment unit, not a
nuisance. The nuisance (overall strength) is removed by residualization, not by centering. Where
the nuisance genuinely is the grouping — F1, where a persistent miss in `own_pre` would masquerade
as opponent-specific — I decomposed against **player** and re-ran the honest within-player version.

## 3. Shift discipline

`base.prior_expanding` aggregates to date level first, then takes a strict cumulative-minus-self.
A value serving a target game therefore comes only from rows **strictly before** that game's date,
and same-day games cannot see each other. Nothing uses the target game's own outcome.

The one exception worth naming explicitly: **F2 is conditional on tonight's roster being known**.
It is pregame-observable only if inactives are known pregame — the same KNOWN-LINEUP framing under
which this program previously found real intrinsic player signal. It is not a blind-forecast
feature and must not be scored as one.

## 4. Placebo construction

Every placebo permutes the **assignment of an already-computed value to rows**, within season. No
placebo permutes a grouping key and recomputes an aggregate — that is the no-op whose signature is
sd exactly 0.000000. **30 placebo distributions were run; the minimum sd observed was 6.708e-05 and
none was degenerate.** The correct construction is also documented inline in
`base.screen_increment_quiet`.

R4 uses a different and stronger placebo: a **side-exchangeability** flip that swaps which team's
pace each row is assigned, testing the null that the two sides are exchangeable.

## 5. R² convention (relevant to cross-screen comparison)

All R² here is **plain unweighted OLS R²** — `1 − SSE/SST`, SST about the unweighted mean. **No
observation weights are used anywhere in this screen.** The ~8 % understatement reported by the
concurrent E1 screen affects a *weighted* R² helper (sqrt-weight-transformed SST about its own mean
instead of weighted SST about the weighted mean); this screen contains no weighted regression, so
no number in this directory is affected. Verified numerically in `run_log_r2_convention.txt`.

Comparing these ΔR² against I0009's 0.006–0.007 is valid in **magnitude** but is an
unweighted-vs-weighted comparison. Treat it as order-of-magnitude, not a ranking to three figures.

## 6. Hazards honored

- `master_player.position` — **not used**. It is a starting-lineup-slot label. No formulation here
  needs a position field.
- `master_player.pace` — **not read** (known corrupt). Pace comes from `master_team` via
  `base.team_possessions()`.
- `master_player.possessions` — used, but only after an explicit check: `sum(player possessions) /
  (5 × team possessions)` has median 0.992 (p05 0.960, p95 1.023) and `corr(possessions, minutes) =
  0.9919`. The possessions column is sound even though its sibling `pace` is not. R1 additionally
  re-runs the survivor on a **minutes** denominator that never touches possessions.
- `observed_time` — dropped at load and re-checked in `base.safe_write()`. It reaches no output.
- **Rest/travel were confirmed absent** from both masters and were constructed here from the
  schedule plus `data/reference/team_cities.csv`. Venue coordinates resolved on 1776/1776
  team-games; b2b share 0.026; median travel 883 km; timezone shift non-zero on 44 % of games.

## 7. What died, and why it matters that it died *cleanly*

| formulation | why it died |
|---|---|
| **F1 opponent-specific residual history** (familiarity / scheme fit) | Not a costume (r ≈ −0.03…−0.05) and mostly within-player. It died on **measurability**: the pair instrument's split-half reliability is 0.03–0.08. |
| **F2 availability-conditioned matchup** (opponent's specialist out) | Not a costume, low between-group variance, **high-reliability instrument** (SB 0.70–0.93). A genuine, bankable negative. |
| **F3 style/tempo orthogonalized** (3PA-rate allowed, forced TOV, OREB allowed, pace) | 11 of 12 cells inside their placebo floors or killed on multiplicity. |
| **F4 rest / travel × opponent** | All 12 cells inside their floors, per-season betas flipping sign. Measured without error, so a clean negative. |

**The most useful structural finding for the program:** the I0010 costume diagnosis **does not
generalize**. All four non-positional formulations came in genuinely non-collinear with overall
opponent defence (|r| 0.03–0.14, against I0010's 0.57–0.59). They mostly died — but they died as
**real nulls, not as costumes**. The personnel-matching channel of layer 3 (familiarity,
availability, style-fit) is now screened and empty. What remains live is the **possession-volume**
channel.

### Two kills that need their qualifier read

- **F1 is a kill on deployability, not a clean negative.** Reliability 0.03–0.08 means the null is
  *uninformative about whether the phenomenon exists*. What it does establish is that the effect is
  unmeasurable with this league's schedule: a (player, opponent) pair meets ~4× a season, the
  ceiling across four seasons is 14, and the median analysis row has 3 prior meetings. With
  per-game surprise sd ≈ 10.4 points, a 3-meeting mean has a standard error near 6 points per 100.
  This is structural, not a sample-size problem more seasons would fix at a useful rate.
  **Do not cite F1 as evidence that opponent familiarity does not exist.**

- **F2 has a known construction weakness.** The roster pool forward-fills a player's last observed
  rate indefinitely, so a player who leaves a team mid-season keeps inflating DELTA. frac(DELTA>0)
  of 0.36–0.51 is implausibly high for an injury rate. The strict subset (DELTA > 0.5, 3–9 % of
  rows, a plausible injury rate) is also null, and the raw contrasts are directionally sensible but
  tiny (+0.41 pts/100 with the rim protector out; +0.29 reb/100 with the top rebounder out). A
  tighter pool definition would sharpen the measure; the negative is solid but not final.

### Multiplicity

The sweep ran **60 tests**. Three cells cleared their own placebo floor at nominal p 0.010–0.040
(d3par × own for pts; dorebA main for pts; dpace main for ast). All three have standardized z
between 3.4 and 3.7 against a randomization **max-T** null whose p95 is **6.53**. They are exactly
the false positives a 60-test sweep predicts, and they are **killed on multiplicity, not kept**.

One of them deserves a single line in the *layer-2* backlog rather than layer 3: **opponent OREB
allowed** predicts player points as a main effect with betas positive in 4/4 seasons — i.e. total
points allowed may not fully capture the second-chance possession channel. Its matched interaction
with the player's own OREB rate is 0.000025, dead, so it is not a matchup.

---

## 8. The one survivor

**Opponent PACE × the player's own pregame REBOUND rate**, target = rebounds.

| diagnostic | value |
|---|---|
| pooled ΔR²(O×M) | **0.001071** |
| placebo mean / sd | 0.000064 / 0.0000874 |
| permutations ≥ real | **0 / 200** |
| per-season β(O×M) | +0.356, +0.335, +0.167, +0.064 (**4/4 same sign**) |
| collinearity vs overall opponent defence | **+0.108** |
| between-opponent variance share | 0.350 (opponent is the treatment, not a nuisance) |
| split-half reliability of the pace instrument | r 0.678, **SB 0.808** |

**Mechanism.** Rebounds are a volume statistic: they scale with how many shots go up. A fast
opponent produces more shot attempts, and a player who already claims a large share of available
rebounds converts that extra volume into more rebounds *even after* both additive main effects and
the base `O×D` term. That is a genuinely multiplicative matchup channel, and it is not the kind of
thing that could be overall defensive strength in disguise.

### It survived four robustness checks

1. **R1 — normalization.** Re-run per 36 **minutes**, a denominator that never touches possessions:
   ΔR² = 0.000930, 0/400 permutations, betas positive 4/4. **Not a denominator artifact.**
2. **R2 — family-wise error.** Randomization max-T across all 60 tests × 200 permutations:
   candidate z = **10.69**, larger than the largest null draw (9.34). Family-wise p = 0.0000.
3. **R3 — control ladder.** Adding the player's own team's pregame pace, `O × own-team pace`, the
   opponent's allowed-OREB style, and `O ×` that leaves ΔR² at 0.000948 (from 0.001069).
4. **R4 — the decisive symmetry test.** β(O × **opponent** pace) = **+0.1915** vs
   β(O × **own-team** pace) = **−0.0962**; difference +0.2876 against a 2000-draw
   side-exchangeability placebo (sd 0.0666, 0/2000 at or above). Given `O × own-team pace`, opponent
   pace still adds 0.000942; the reverse adds only 0.000256. **Asymmetric → an opponent matchup,
   not symmetric game tempo.**

### A void rung, recorded so nobody re-runs it

R3's final rung ("+ TOTAL game pace & O × total") is **rank-deficient by construction** — I formed
total pace as the exact sum of the two sides, so `O × total` is an exact linear combination of the
two terms already in the model. Its ΔR² collapse to 0.000027 and β of 5.27 with per-season signs of
−0.52 / +14.66 / −12.01 / +1.01 are a **linear-algebra artifact, not evidence of absorption**. That
rung is void; R4 replaces it and is the test that actually answers the question.

### 🚩 The caveat that should govern any decision about this lead

**The effect decays monotonically across the partition and is essentially gone in 2024.**

| season | β(O×M) | R4 asymmetry difference |
|---|---|---|
| 2021 | +0.356 | +0.372 |
| 2022 | +0.335 | +0.403 |
| 2023 | +0.167 | +0.275 |
| 2024 | **+0.064** | **−0.035** |

The pooled result is carried by 2021–2022. 2024 is the season nearest the holdout. Any confirmation
run on 2025/2026 would be testing a trend that has **already decayed to zero inside the exploration
window**. Combined with an absolute size ~6× smaller than I0009's existing 0.006–0.007 lead, this is
a small lead with a live mechanism for failing. It must be stated on any promotion proposal.

---

## 9. What I would do next on the survivor

In priority order. None of this is a promotion recommendation — it is what would have to be true
before one.

1. **Explain the decay before spending a confirmation budget on it.** This is the first thing, not
   the last. Is 2021 an artifact of the 2021 season's structure (COVID-era schedule, roster
   volatility, the smaller `n` of 2128 analysis rows), or did the league genuinely change? Test by
   re-running with 2021 dropped entirely: if the 2022–2024 trend still decays, the lead is dying on
   its own and should be abandoned without touching the holdout. Cheap, and it is the highest-value
   next step by a wide margin.
2. **Replace the pace instrument with a cleaner one.** `dpace` is possessions per 48 derived from
   the standard estimator on `master_team`. Try opponent **shot attempts allowed per 48** and
   opponent **missed shots per 48** directly — missed shots are the actual rebound supply, and if
   the mechanism is what I think it is, the supply variable should beat the tempo proxy. If it does
   not, the mechanistic story is wrong and the lead weakens.
3. **Split the target.** Rebounds are OREB + DREB with different mechanics: DREB supply comes from
   the *opponent's* misses, OREB supply from the player's *own team's* misses. The asymmetry found
   in R4 predicts the effect should live almost entirely in **DREB**. That is a sharp, falsifiable
   prediction and it costs one run. If the effect is equally in OREB, the R4 asymmetry result is
   suspect and the lead should be re-examined.
4. **Check heterogeneity by player rebound volume.** The interaction implies the effect concentrates
   in high-rebound-rate players. Confirm it is a smooth gradient and not driven by a handful of
   high-minute bigs — a quantile-of-`O` breakdown, plus a leave-one-player-out jackknife on the
   pooled β.
5. **Only then** consider whether this belongs on a preregistration. Given a size of ~0.001 ΔR² and
   the decay, my own reading is that it likely does not clear a promotion bar on its own, and its
   real value is as a **pointer**: the live surface in layer 3 is possession volume, so the next E0
   sweep should be built there rather than on more personnel-matching variants.

### And what I would *not* do

Do not build more personnel-matching formulations (familiarity, availability, style-fit,
positional). Between I0010 and this sweep that channel has now been screened from four independent
directions, with high-reliability instruments in F2 and F3, and it is empty. F1 is the one place
where the null is uninformative — but it is uninformative because the WNBA schedule structurally
cannot supply the data, which is a reason to stop rather than to try harder.

---

## 10. Files

| file | what it is |
|---|---|
| `base.py` | shared loader, partition gate, manifest gate, shift discipline, diagnostics, screen |
| `f1_pair_history.py` | F1 — opponent-specific residual history |
| `f2_availability.py` | F2 — availability-conditioned matchup |
| `f34_style_rest.py` | F3 — style orthogonalized; F4 — rest/travel |
| `r_robustness.py` | R1 normalization, R2 family-wise, R3 control ladder (final rung void) |
| `r_symmetry.py` | R4 — the decisive opponent-vs-own-team symmetry test |
| `make_findings.py` | assembles `FINDINGS.json` by reading result JSONs, never retyping numbers |
| `verify_partition.py` | parses every written CSV and tests season/date **values** |
| `run_log_*.txt` | full console output of every run, including the R² convention check |
