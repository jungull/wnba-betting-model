# Which aggregation level wins, for which quantity

**E1_I0033_aggregation_level** — written for the user.
Preregistration hash `0787b5caf7b035c2f3df3b95970ec637abf7d9e9780e17fe0f88d92a2838db2e`
(14 cells hashed before anything was computed, 0 dropped, 5 added afterwards — **all five
additions make the player level look better, not worse**).

Regular season 2022–2024, 1,392 team-games, walk-forward, strictly prior-only.
2021 is excluded from scoring because **both** arms' fold receipts declare that fold degenerate.
2025 and 2026 were never opened.

---

## The short answer

**Your architectural instinct is right, and the data is more emphatic than your argument was.**

Team level wins for team-level questions — on **every one of the six quantities we can measure
both ways, decisively, under both weightings we tried**. And it does not win by a little. But the
*reason* it wins is not the one you'd guess, and it is the reason your second sentence — that we
still need a player-value model — is also right, for a purpose that turns out to be different
from the one you named.

---

## 1. Top-down versus bottom-up on team points — the central test

Same response (team points), same 1,392 rows, same denominator, no weighting, no base.
Every number in this table is comparable to every other number in it.

| Arm | What it is | MAE | R² | Bias | Skill vs matched reference |
|---|---|---:|---:|---:|---:|
| **R2_TEAM_EWMA** | tuned team prior-history reference | **8.480** | +0.0570 | −0.56 | — (this *is* the reference) |
| R1_TEAM_EXPAND | team expanding prior mean | 8.477 | +0.0567 | −0.65 | +0.04% |
| **A_TEAM** | the team arm's stored forecast | **8.686** | +0.0217 | −1.03 | **−2.42%** |
| R0_LEAGUE | expanding league mean (a near-constant) | 8.791 | −0.0051 | −0.64 | −3.66% |
| **B1_BOTTOMUP** | **sum of the champion's player forecasts** | **18.263** | **−8.66** | **+8.14** | **−115.4%** |
| B2_BOTTOMUP_RAW | the same, unweighted by availability | 37.418 | −39.93 | +35.75 | −341.2% |
| *B3_ORACLE_ROSTER* | *sum over players who actually played* | *10.650* | *−0.545* | *−0.65* | *−25.6%* |

*Italic row uses the realised roster. It is an **oracle**, it is excluded from every headline and
every ranking, and it is shown only because it is the diagnostic that separates the causes.*

**Top-down beats bottom-up by 9.578 MAE points per team-game** (p < 0.0001; null mean +0.014,
null sd 1.766, 36 team-season blocks; the effect sits 5.4 null standard deviations out and the
cell's 80 %-power detection floor is 4.95, so this is not a marginal call).

Two things in that table matter as much as the headline.

**The bottom-up sum has essentially zero correlation with the thing it is forecasting.**
Correlation of each forecast with realised team points:

| Forecast | correlation |
|---|---:|
| Team prior-history reference | **+0.2526** |
| The team arm | +0.1879 |
| Bottom-up, roster-normalised | +0.1823 |
| Bottom-up, as the champion emits it | **+0.0013** |

**And the team arm loses to a simple team-level prior average.** A_TEAM is 0.205 MAE worse than a
tuned EWMA over the team's own earlier games (p = 0.0159). That is significant but *underpowered* —
the observed gap of 0.205 sits below this cell's 80 %-power floor of 0.251 — and it should always
be quoted with that caveat. It is the same shape as D076's finding that the champion barely beats
a prior mean on points, and D101's finding that the incumbent baseline was worse than a plain
expanding mean.

---

## 2. Why bottom-up loses — the decomposition

You asked whether it is error compounding, the roster problem, or individually weak player
forecasts. **It is overwhelmingly the roster problem, and error compounding is not happening at
all.** Each step below is applied on top of the previous one, so they sum to the total by
construction.

| Step | MAE | Improvement | Share of the 9.578-point gap |
|---|---:|---:|---:|
| Literal bottom-up (sum of champion forecasts) | 18.263 | — | — |
| **+ fix the roster size** (weights rescaled to the team's prior-games roster size) | 10.443 | **+7.820** | **81.7 %** |
| + remove residual level and scale bias (walk-forward affine) | 8.655 | +1.788 | 18.7 % |
| Target: the top-down team arm | 8.686 | −0.031 | −0.3 % |

### (b) The roster problem — 81.7 % of the gap, and here is exactly what it is

The champion's obligation universe averages **14.43 players per team-game** against a realised
roster of **9.40**. Its availability forecast sums to **10.34**. The excess sits in the universe's
tier-B fallback rows, which receive a **declared-constant `p_active` of 0.80 against a realised
appearance rate of 0.10**. One phantom player times an ~8.7-point conditional scoring forecast is
**+8.14 points of level bias per team-game** — which is essentially the whole disadvantage.

This is not a subtle statistical effect. It is an arithmetic consequence of summing a
per-player-calibrated availability forecast over a roster: **the availability model is calibrated
one player at a time and nobody ever checked whether it adds up to a basketball team.** Summing is
what exposes it, and nothing in the player-first architecture forces anyone to sum.

### (a) Error compounding — it is not happening; the errors *cancel*

| | raw | roster-normalised |
|---|---:|---:|
| Players summed per team-game | 14.43 | 14.43 |
| sd of the summed error | 33.44 | **13.26** |
| sd if player errors were independent | 20.14 | **19.68** |
| ratio observed / independent | 1.66 | **0.674** |
| mean Σ\|per-player error\| | — | 52.00 |
| mean \|Σ per-player error\| | — | 10.45 |
| cancellation ratio | 0.326 | **0.201** |

Once the level bias is removed, the summed error is **0.674×** what independence would predict, and
the 52 points of per-player error present in an average team-game collapse to **10.5** once summed.
Player errors are *negatively* aligned within a team-game and largely cancel — a team's points are
a near-fixed budget, so one player's over-forecast is another's under-forecast. **Adding up ten
noisy forecasts is not the problem.** The intuition that granular errors compound is wrong here.

### (c) Individually weaker player forecasts — a little, and both levels are negative

Against a matched prior-history reference built the same way at each level:

* **player level**: champion points forecast, n = 13,021 appeared player-games, MAE 4.249 against
  a matched reference of 4.132 → **skill −2.82 %**
* **team level**: team arm, n = 1,392, MAE 8.686 against 8.480 → **skill −2.42 %**

*These are different responses and are not dΔR², so only the skill ratios are set beside each
other, never a variance share.* Both models lose to a simple prior average at their own level. The
player one loses slightly more.

### And the honest counterweight

If you *fully* repair the bottom-up sum — fix the roster and then let a walk-forward affine
recalibration fix the level — it **ties** the team arm (MAE 8.655 vs 8.686, p = 0.73, i.e. not
established either way). So the level itself is not what beats it.

**But it ties only by throwing the player information away.** That recalibration's fitted slope is
**0.07 – 0.15** across seasons — it is shrinking the summed player forecast almost entirely to a
constant. The team arm's own slope on the same construction is 0.33 – 0.99. Bottom-up reaches
parity by ceasing to be bottom-up.

---

## 3. The which-level-wins table — six quantities, matched construction

This is the clean test of your question, because the *estimator class is held fixed and only the
aggregation level varies*. Both sides are the same prior-history EWMA with shrinkage, tuned by the
same rule on strictly earlier seasons, scored against the same team-level response on the same
rows with the same denominator. The player side weights each candidate by the champion's own
availability forecast, rescaled so the weights sum to the team's prior-games roster size — the
fairest available construction, and one that had to be *added* to the preregistered list because
the preregistered version flattered the team side.

| Quantity | Team-level MAE | Player-level MAE | Team advantage | as % of team MAE | p | Winner |
|---|---:|---:|---:|---:|---:|---|
| **Shot attempts (FGA)** | 4.698 | 7.025 | +2.328 | **49.6 %** | <0.0001 | **TEAM** |
| **Points** | 8.480 | 10.791 | +2.311 | **27.3 %** | <0.0001 | **TEAM** |
| **Rebounds** | 4.400 | 5.092 | +0.692 | **15.7 %** | <0.0001 | **TEAM** |
| **Assists** | 3.233 | 3.587 | +0.354 | **11.0 %** | <0.0001 | **TEAM** |
| **Free-throw attempts** | 4.867 | 5.222 | +0.354 | **7.3 %** | <0.0001 | **TEAM** |
| **Free throws made** | 4.220 | 4.497 | +0.277 | **6.6 %** | <0.0001 | **TEAM** |

Every cell is DECIDED. Every cell favours the team level. The preregistered version (raw
availability weights, no roster normalisation) gives the same six winners with penalties two to
three times larger.

**But look at the ordering, because that is the quantity-dependence you asked about.** The cost of
going bottom-up is not uniform — it ranges from **49.6 %** to **6.6 %**, a factor of 7.5. The same
picture in correlation terms, player level as a fraction of team level:

| Quantity | team corr | player corr | player / team |
|---|---:|---:|---:|
| Assists | 0.307 | 0.264 | **0.86** |
| Points | 0.253 | 0.182 | 0.72 |
| Free throws made | 0.128 | 0.087 | 0.68 |
| Free-throw attempts | 0.160 | 0.094 | 0.58 |
| Rebounds | 0.240 | 0.140 | 0.58 |
| Shot attempts | 0.182 | 0.082 | **0.45** |

**Assists and free throws are where the player level comes closest. Shot attempts is where it is
furthest behind.** That is exactly the shape your argument predicts: the quantities that are
genuinely *individual acts* — a free throw is one player alone at the line — survive aggregation
from below. The quantities that are *allocations of a shared, fixed team budget* — shot attempts
out of ~200 team minutes and ~80 possessions — do not, because modelling ten players separately
throws away the constraint that their attempts must sum to the team's.

Worth noting: free throws are the channel D108 found the player arm **does not model at all**, and
it is one of the two channels where the player level is least penalised. That is where a player
decomposition would cost least if anyone wanted one.

---

## 4. The free-throw composition — your concrete example, quantified

You asked whether a team shooting 85 % converts the home free-throw edge differently from a team
shooting 70 %. **Yes, exactly and calculably — and it is far too small to move a forecast, which we
could prove before fitting anything.**

D104 established the venue edge is **+1.087 free-throw attempts** with accuracy worth only +0.4
percentage points. Over 2022–2024:

* the **lowest** team-season free-throw percentage was **74.2 %**, the highest **84.0 %**
* the same +1.087 attempts is worth **0.807 points** to the first team and **0.913 points** to the
  second
* **the entire spread is 0.106 points per game** — 11.0 % of the +0.965-point home advantage, and
  **0.0096 of one standard deviation of team points**

Computed before any fitting, exactly as D104 did: the **largest ΔR² a perfect composition term
could add over a flat home constant is 1.94 × 10⁻⁶**. That is

* **526×** below D103's detection floor for a single preregistered cell (~1.0 × 10⁻³), and
* **24×** below the player-level home ceiling of 4.63 × 10⁻⁵ that D104 already called unmeasurable.

The measurement then landed on its ceiling, as it had to:

| Comparison | ΔMAE | p | 80 %-power floor |
|---|---:|---:|---:|
| Composed vs flat home constant | +0.00037 | 0.672 | 0.0024 |
| Composed vs no venue term at all | +0.00023 | 0.990 | 0.0467 |
| Composed-over-flat (incremental form) vs flat | +0.011 | 0.479 | 0.0430 |

**This is NOT ESTABLISHED, not ABSENT** (D108 ruling 4) — but here absence and non-establishment
coincide, because the arithmetic ceiling is 500× below what the data could ever resolve. The
free-throw main effects were in the base from the start, as D108 requires; the whole free-throw
family, main effects included, makes the team points forecast **worse** than the plain prior
reference (8.490 vs 8.480).

**The composition is real. It is 0.106 points per game. It is not actionable.**

---

## 5. The player-value question — a team model cannot answer it, and neither can subtraction

You said a team model cannot tell you what happens when a player is out, so we need a player-value
model. The first half is true. The second half needs a correction that changes what such a model
is *for*.

We measured the cheapest estimator the bottom-up architecture already gives away for free —
"the team loses that player's forecast points":

* 1,392 team-games; **183** have at least one pre-game top-3-by-expected-minutes player absent
* those absences are worth **15.8 forecast points** on the naive estimate
* the team's realised shortfall against its prior reference is **0.085 points**
* fitted fraction actually lost: **β = 0.028**, 95 % interval **[−0.057, +0.114]**
* the null detects a planted β of **0.10**, so this is a powered interval, not a shrug
* β = 1.0 — "the team loses exactly that player's points" — sits **22 null standard deviations
  away** and is decisively rejected

**Substitution is essentially complete for team totals.** Even for the largest absentees (top
quartile, ~19.8 forecast points) the implied ratio is only **0.081**. Knowing about the absence
*in advance* — an oracle we gave the team model for free — improves the team points forecast by
−0.00004 MAE against an 80 %-power floor of 0.0058. **Nothing.**

**What that does and does not mean.** It does *not* mean player-value modelling is pointless. It
means the value is not in the team total. When a starter sits, the team scores the same number of
points — but *different people score them*, and that redistribution is invisible at team level and
is the entire content of a player-props book. The player model's job is the **distribution across
players**, not the **total**.

That is your own sentence, sharpened: *the holistic owns the total; the granular owns the
allocation*. The programme has been asking the granular layer to produce the total, which is the
one thing it is worst at.

See `player_value_scope.md` for what exists, what would be needed, and D107's already-measured
boundary — walk-forward RAPM wins for veterans returning (+2.28 % on points, p 0.0015) and hurts
true rookies (−54 %).

---

## 6. What this means for the programme

1. **Forecast team-level quantities at team level.** Six for six, decisively, and the top-down arm
   is not even the good version — a tuned prior-history team average beats it.
2. **The player arm should not be summed to produce team totals.** As emitted it correlates
   +0.0013 with team points. The single largest defect is a roster-arithmetic one: the
   availability forecast sums to 10.34 players where 9.40 play, and nobody has checked that,
   because nobody has ever summed it.
3. **Aggregation level is a design choice with measurable consequences — and it is being made by
   default.** The team arm carries exactly one target (`team_game_distribution`). The player arm
   carries four. The programme did not choose to model at the player level; it accumulated there.
4. **Keep the player model, and point it at what it is good for.** Props, allocation,
   distributional shape, and — per D108 — the free-throw hurdle the current scalar-plus-envelope
   architecture structurally cannot represent. Not team totals.
5. **The one place the levels genuinely converge is worth remembering.** Fully repaired bottom-up
   ties the team arm (p = 0.73), but only after its own recalibration has shrunk it to a
   near-constant (slope 0.07–0.15). Parity bought by discarding the granular information is not
   evidence that the granular information was useful.

---

## Discipline record

* Anchors reproduced on bytes **before** any new statistic: D104's home advantage **+0.965090 on
  888 games** (exact) and D076's **13,879** appeared player-games (exact).
* Identity map **reconstructed** from `cbs_obligation_key` rather than read from the unmanifested
  `prediction_contract_v5`, and verified **exact on all 22,659** rows the manifest-verified
  contract v4 carries.
* Null: paired block sign-flip at team-season, with `null_mean` and `null_sd` beside every p.
  The within-player cyclic shift is **not used anywhere** — every candidate here varies at
  team-game or between-team level, where D108 showed that null is powerless.
* **Power verified by injection before any verdict**, per cell. Type-I rejection rate **0.0425**
  over 400 synthetic no-effect datasets.
* Negative controls perturbed 88.0 % and 99.9 % of rows and both destroyed the advantage as they
  should. No-op placebo reproduced the real statistic with deviation **exactly 0.0**.
* Three defects self-reported in `DEFECTS.md`, including one power construction that was
  uninformative and one preregistered decision rule whose shares do not partition.
* Playoffs excluded before any statistic for D104's structural reason, and reported separately
  anyway (the ordering is unchanged).
