# The availability-sum defect, in plain language

**E1_I0035_availability_sum.** Preregistration hash
`7cd32656f3f7a96e869bf649f2ce1034a1c9cc3670f5dbc7605350fba6664205`.
Regular season 2022–2024, 1,392 team-games, 20,084 player forecasts. 2025 and 2026 were never
opened. **No repair was enacted; every model change is the user's decision.**

---

## The one-paragraph version

Before each game the model lists everyone who might play for a team and gives each a probability
of playing. Individually those probabilities are good — the model reliably ranks who is more
likely to play than whom. But **the list is too long, and the probabilities on the surplus names
are far too high.** Add them up and the model expects **10.34 players** to take the floor when
**9.40** actually do. That extra one phantom player is credited with a normal player's scoring —
about 8.7 points — so any team total built by adding players up starts **8.14 points too high,
every single game.** Nobody caught it because nobody had ever added the probabilities up: each
one was checked on its own, and on its own each one looks fine.

---

## 1. It reproduces. Exactly.

E1_I0033 found this. I rebuilt it from the raw model outputs without using any of their files.

| | E1_I0033 | mine |
|---|---:|---:|
| Names on the list, per team-game | 14.428 | **14.4282** |
| Players who actually played | 9.4016 | **9.4016** |
| Sum of the model's play-probabilities | 10.3381 | **10.3381** |
| Points of level bias this injects | +8.139 | **+8.1389** |
| Bottom-up team forecast error (MAE) | 18.263037 | **18.263037** |

The anchor required before any new statistic — D076's 13,879 appeared player-games — reproduced
exactly, as did the identity map on all 22,659 rows it could be checked against. **The defect is
real and E1_I0033 measured it correctly.**

---

## 2. Who the surplus names are

The candidate list has two tiers. **Tier A** is players with a prior box-score line for that club
this season — the actual roster. **Tier B** is everyone admitted on weaker evidence, and the
contract that builds the list says so in plain terms: for tier B, *current roster membership is
not established*.

There are 3,772 tier-B rows. Here is who they are:

| Who | Share of tier B | Model says they'll play | They actually play | Never play for that club again that season |
|---|---:|---:|---:|---:|
| Last played **in a prior season** (>200 days) | **69.9 %** | 0.536 | 0.111 | 82.4 % |
| Played **somewhere in the last week — for a different club** | **23.4 %** | 0.472 | **0.007** | 98.1 % |
| Genuine debutants, never played anywhere | 5.2 % | 0.694 | 0.369 | 45.1 % |

**83.8 % of tier-B rows are for a player who never appears for that team again that season.**
These are not deep-bench players or two-way contracts. The names carrying the most surplus are
established starters being held against clubs they had already left — Crystal Dangerfield
(44 rows, 3 appearances), Tina Charles, Liz Cambage, Courtney Williams, Natasha Howard.

**So the honest label is: this is primarily a data-freshness problem, with a calibration problem
layered on top.** The model is being asked "will she play for Chicago tonight?" about a player
who is on Dallas. It answers 47 %. The right answer is that the question should not have been
asked.

---

## 3. The mechanism, in two parts

### Part one — a constant nobody defended (73 % of the surplus)

Deep in the code there is a table of fallback values:

```
cbs_generator.py:71    DECLARED = {
                           "p_active": {"point": 0.800, "sd": None},
                           "e_minutes_given_active": {"point": 20.0, ...},
                           ...
```

and one line that uses it:

```
cbs_v7.py:1341    pa_point = p_hat.where(lvl_pa == 0, DECLARED["p_active"]["point"])
```

Read that line carefully. `p_hat` is the model's actual fitted answer. This line **throws it away
and writes 0.800 instead** for every player who has fewer than three prior scheduled appearances.
2,239 of the 20,084 forecasts (11.1 %) are this constant.

**Where does 0.800 come from? Nowhere.** The spec that declares these constants
(`CONTRACT_BASELINE_SUITE_V2.md` §9) derives the other four arithmetically and shows its working:
200 team-minutes ÷ 10 rotation players = 20.0 minutes; 70 team shots × 10 % = 7.0 shots;
82 team points × 10 % = 8.2 points; 82.0 team points. The machine-readable registry carries a
`derivations` dictionary with exactly those **four** entries. `p_active` is in the value table
and **is not in the derivations**. It is an undefended round number — and it is frozen behind a
clause forbidding anyone to retune it.

**And it is being used somewhere it was never authorised.** Every document scopes these constants
to two situations: the 2021 season, where no training data exists at all, and a fold that failed
to fit. No document authorises substituting the constant for a player with one or two prior games
in a fully-trained season. The regression test that guards this
(`tests/test_cbs_generator.py:191`) only checks the 2021 path. **The scope crept and no test
watched it.**

### Part two — a model applied to a population it never saw (49 % of the surplus)

This half is *not* a constant, and it is the part E1_I0033's user-facing summary missed.

The arm's training rule is one line of policy: **the training frame is tier-A rows only.** So the
availability model is fitted on players who *are* on the roster, where 78 % play — and then
applied unchanged to tier-B rows, where 10 % play. The fitted (non-constant) tier-B forecasts
average **0.317 against a realised 0.017**. That is an 18-fold over-statement with no constant
involved anywhere.

**The contract does its job. It carefully labels these rows as unverified. The arm then reads the
rows and ignores the label.** Nothing in the emission path looks at `universe_tier` at all.

### Where the surplus actually sits

| | Rows | Surplus players per team-game | Share |
|---|---:|---:|---:|
| Tier B, the 0.800 constant | 1,625 | **+0.685** | 73.2 % |
| Tier B, fitted logistic | 2,147 | **+0.462** | 49.3 % |
| Tier A (slightly *under*-predicts) | 16,312 | **−0.211** | −22.5 % |
| **Net** | 20,084 | **+0.937** | 100 % |

0.937 surplus players × 8.74 points each = **+8.19 points**, against an observed level bias of
**+8.14**. The arithmetic closes.

---

## 4. Why D090 called this forecast good, and was right

D090 scored the availability model and found AUC 0.9016 with only ~2 % of its error attributable
to miscalibration. That is not in dispute and it is not wrong. Both things are true, for two
reasons.

**Reason one, and it is the whole paradox in a sentence: AUC does not care about level, and a sum
does nothing else.** AUC measures whether the model ranks a player who plays above a player who
does not. Multiply every probability by 1.5 and the AUC does not move by a thousandth. Add them
up and the answer changes by 50 %. A forecast can rank every player perfectly and still add up to
the wrong number of basketball players. Check it per player and you see the ranking. Only summing
shows the level.

I can show this directly on my own rows:

| Rows scored | n | Base rate | Mean forecast | Brier | **AUC** |
|---|---:|---:|---:|---:|---:|
| Tier A only — D090's picture | 16,312 | 0.779 | 0.761 | 0.093 | 0.898 |
| **Everything, tier B included** | 20,084 | **0.652** | **0.717** | 0.130 | **0.903** |

Adding the broken rows makes the **AUC go up**. Discrimination improves; the level breaks. Any
metric built on ranking was always going to pass.

**Reason two: D090 could not see these rows.** Its own defect note records that 3,808 forecasts
were excluded because the contract that defines tier B has no manifest and therefore could not be
trusted — and those are precisely the marginal-roster rows where the defect lives. Its
constant-detection probe counted only cold-start rows: **18 rows**, against the 2,239 that
actually carry 0.800. It examined under 1 % of the affected population and, on what it examined,
reported correctly.

---

## 5. One correction to E1_I0033

E1_I0033's user-facing document says:

> the universe's tier-B fallback rows, which receive a **declared-constant `p_active` of 0.80**
> against a realised appearance rate of 0.10

**That sentence is wrong, and its own technical notes are right.** Only **1,625 of 3,772**
tier-B rows (43.1 %) carry the constant. The other 2,147 carry a fitted value averaging 0.317.
The screen's `NOTES.md` §4.4 gives the correct tier-B mean of 0.5249, which reproduces exactly;
the error is only in the plain-language retelling, and it propagated into that screen's
`DEFECTS.md` and `player_value_scope.md`.

**Every number in E1_I0033 reproduces exactly.** The 81.7 % share, the +8.14 bias, the whole
which-level-wins conclusion — all untouched. What changes is only the mechanism attribution, and
it changes the fix: a repair aimed only at the constant leaves roughly half the surplus in place.

---

## 6. Is this the third "a fallback emits a constant" defect?

**Partly — and the programme already counted it as the third.** Decision ledger D111 names the
availability sum as *the third structural defect this programme has found by looking at what the
model emits rather than at what predicts the outcome*. The two priors are D092/D102 (the champion
emits a constant for minutes, points and attempts and keeps emitting it after it has begun to
know something) and E0_I0028's DEFECT_A (`pred_sd` is one value per season on every row).

But it is **not purely** that pattern, and that is the finding here. The constant is 73 % of it.
The rest is a train/score population mismatch that neither prior instance has. **Fix only the
constant and you fix only half the defect.**

One documented counterexample deserves naming rather than burying: E0_I0028 found that replacing
the flat 0.800 with a prior-appearance-rate estimator *loses* 4.96 % of Brier skill on this arm —
the constant beats that particular alternative. That is a real result and it is not contradicted
here, because the repair measured below **recalibrates** the constant rather than replacing it
with a different estimator. Those are different operations.

---

## 7. Does it reach production? No.

**Nothing that ships reads `p_active` at all.** The daily forecast, the props edge, the
conditional and calibrated edge scripts, the capture jobs, the prediction engine, the odds
systems, the forecasts and leaderboards trees — zero references, all of them.

The shipped per-player points forecast is **conditional on playing**: it multiplies a
points-per-36 average by expected minutes, where the minutes average is taken over games the
player actually played. There is no × P(active) term anywhere in it. **A broken availability
probability cannot corrupt the per-player product**, because the per-player product does not use
it.

The only place in the entire repository that multiplies by `p_active` is a minutes-exposure
producer that is registered `production_eligible: False` on all three of its regimes. And even
there the damage is limited by an accident of construction: it hands out a fixed 200 team-minutes
in proportion to `p_active × expected minutes`, so any *uniform* error in `p_active` divides out
exactly. What survives is the *shape* — how the roster's weight is distributed. Measured:

> **14.44 of every 200 team-minutes are allocated to tier-B rows, against 5.53 actually played
> by them — 8.91 minutes per team-game taken from players who do play and handed to players who
> mostly do not.**

**Verdict: low urgency as a live risk, high as a gate.** Nothing is broken today. But this must be
repaired before anything bottom-up, exposure-based or props-facing that consumes `p_active` is
promoted — and per E1_I0033 the bottom-up path is exactly what someone would reach for next.

---

## 8. What a repair has to survive

The full comparison is in `REPAIR_OPTIONS.md`. The short version:

* **Recalibrating the probabilities per tier** fixes the team sum (18.26 → 10.96 MAE), improves
  the player-level forecast (Brier 0.130 → 0.095), leaves the tier-A rows alone, and cuts the
  minutes misallocation from 8.91 to 4.01. **It is the only option that passes at both levels.**
* **Normalising the sum to a plausible roster size** gives the best honest team number
  (MAE 9.45) and is a trap: it degrades the 16,312 tier-A player forecasts by a margin 5.7× the
  detection floor, and — because the exposure producer renormalises anyway — it changes the
  downstream allocation by **exactly nothing**. It fixes the symptom the team sum shows and none
  of the disease.
* **Pruning the list** is worst on every axis and deletes 5.23 % of the player-games that
  actually happened. A props book cannot price a player it has erased.
* **Leaving it and correcting the level downstream** gives the best team MAE of all (8.79) by
  shrinking the forecast to a near-constant — its fitted slope is *negative* — and does nothing
  whatever at the player level.

The pattern is the one the task predicted: **the repair that looks best at the team level is the
one that quietly damages the product.**
