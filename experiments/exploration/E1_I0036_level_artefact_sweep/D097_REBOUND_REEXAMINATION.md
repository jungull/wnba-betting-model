# D097's REBOUND KILL -- RE-EXAMINATION

Outstanding programme debt raised by D108 ruling 4: *"Match the null to where the candidate
varies, and VERIFY POWER BY INJECTION before trusting any null. D097's rebound kill is flagged
for re-examination."*

Screen `E1_I0036_level_artefact_sweep`, PREREG section 6 (directed cell, **not** a triage hit —
the brief named it and I had located it before freezing; disclosed in PREREG section 0).

---

## THE CELL

| | |
|---|---|
| candidate | `R08_player_ra_share` — the player's own **strictly-prior** share of their own field-goal attempts taken from the Restricted Area |
| construction | `prior_sum(p_ra) / prior_sum(p_att)`, an expanding ratio over strictly earlier games (verified by reading `E0_I0024/s02_build_frame.py` lines 295–307) |
| response | `y_oreb` — offensive rebounds |
| base | `B_COMPLETE` (10 columns): the player's own expanding-mean, EWMA, trailing-5, rate×minutes and percentage history of offensive rebounds, plus prior minutes, prior trailing-5 minutes, prior pace, cold-start count, venue |
| rows | 13,784 (POOLED, 2022–2024) / 5,111 (DECISION: ≥8 prior appearances, ≥24 trailing-5 minutes) |
| D097's verdict | **DEAD.** `p_cyclic_shift = 0.996672`, family-wise `p = 1.0000` |
| D097's own note | *"the LARGEST raw increment in the entire screen… It is nonetheless DEAD… D093's autocorrelation trap firing exactly as warned"* |

Row-level p was 0.001664. Entity-swap p was 0.001664. **Only the cyclic null killed it.**

---

## STEP 1 — ANCHOR REPRODUCTION (gate)

```
fast dR2 (Frisch-Waugh)  = 0.0064881160
literal two-fit dR2      = 0.0064881160     |difference| = 8.9e-17
D097 recorded dR2        = 0.006488         |difference| = 1.2e-07
row set                  = 13,784  (D097 recorded 13,784)  EXACT
A_REF_COVERAGE           = all 10 base columns cover all 13,784 rows
```

**Reproduced.** Gate passed. (Second anchor, D111's six bottom-up penalties, reproduced in
PREREG section 9.)

## STEP 2 — ARITHMETIC CEILING, BEFORE ANY FITTING

`CEILING = (beta · sd(residualised carrier) / sd(y))² = 6.488e-03` = **6.36x the single-cell
floor**, 2.76x the 132-cell floor. **This is not a ceiling kill.** Fitting is warranted.

## STEP 3 — WHERE DOES `R08` ACTUALLY VARY?

A fact about the regressor, established before touching the outcome.

```
variance share BETWEEN players            0.7975
variance share BETWEEN player-seasons     0.8762
variance share WITHIN player               0.2025

dR2 from the BETWEEN-player component alone   1.099e-02
dR2 from the WITHIN-player component alone    2.031e-04
share of the measured effect carried BETWEEN players   0.9819
```

**`R08` is a between-player candidate.** 98.19% of the effect D097 measured lives in variation
*across* players, not in a player's drift over a season. In the DECISION stratum the
concentration is even sharper (98.16% of variance between player-seasons).

This is the whole case in one number, and it was computable in 2018 without any new data.

## STEP 4 — THREE NULLS, EVERY ONE INJECTION-VERIFIED (D108 mandate)

R = 601 draws each. `null_mean` and `null_sd` published beside every p (D103 ruling 2).

### 4a. The preregistered injection (PREREG 5.3) — and why it was not enough

| null | p (real y) | null_mean | null_sd | MDE80 | power @ 0.002057 | type-I @ 0 | status |
|---|---|---|---|---|---|---|---|
| `N_ROW` | 0.001661 | 4.93e-05 | 6.80e-05 | 4.26e-04 | 1.00 | 0.05 | USABLE |
| `N_CYCLIC` | **0.995017** | **7.90e-03** | 5.77e-04 | 1.54e-03 | **0.95** | 0.04 | USABLE |
| `N_PSWAP` | 0.001661 | 7.54e-05 | 9.48e-05 | 4.24e-04 | 1.00 | 0.05 | USABLE |

**`N_CYCLIC` PASSED the preregistered injection test.** Power 0.95 at the programme's largest
live effect. By the letter of PREREG 5.3 and of D108's criterion, it is not degenerate here,
and it is the most conservative usable null, so PREREG 6.4 would have declared it the matched
null and let the kill stand.

**That would have been wrong, and one number gives it away: `null_mean = 7.90e-03` is LARGER
than the observed statistic `6.49e-03`.** A null distribution centred *above* the thing it is
supposed to be a null for is not excluding the effect — it contains it. Cyclic-shifting a
series within a player leaves that player's mean exactly where it was, so the between-player
variation that carries 98.19% of the effect is preserved untouched in every single draw.

The preregistered injection cannot see this, because shuffling the base residuals to build the
synthetic response destroys exactly the between-player *response* structure that `N_CYCLIC`
fails to destroy in the *carrier*. **This is a genuine limitation of D108's injection protocol
and it is recorded as defect D-04.**

### 4b. The added component-targeted injection (disclosed as post-hoc)

Plant the signal along the component of the carrier where the real effect actually lives, and
ask each null again. 60 replicates per delta.

**Power at delta = 0.002057:**

| stratum | n | null | planted FULL | planted **BETWEEN** | planted WITHIN | type-I |
|---|---|---|---|---|---|---|
| POOLED | 13,784 | `N_ROW` | 1.00 | **1.00** | 1.00 | 0.07 |
| POOLED | 13,784 | `N_CYCLIC` | 0.85 | **0.00** | 1.00 | 0.03 |
| POOLED | 13,784 | `N_PSWAP` | 1.00 | **1.00** | 1.00 | 0.05 |
| DECISION | 5,111 | `N_ROW` | 1.00 | **1.00** | 1.00 | 0.10 |
| DECISION | 5,111 | `N_CYCLIC` | 0.13 | **0.00** | 1.00 | 0.05 |
| DECISION | 5,111 | `N_PSWAP` | 1.00 | **1.00** | 1.00 | 0.10 |

**`N_CYCLIC` has power 0.00 against a between-player signal.** Not low — zero, in 120
replicates across two strata, at an effect size 1.8x larger than anything this programme has
ever measured live. It also has `null_mean > observed` in both strata.

`N_CYCLIC` is a perfectly good null for a *within-player* candidate — power 1.00 there. It is
simply the wrong instrument for this candidate, and D097 pointed it at the one candidate in its
250-cell family that it could not possibly see.

## STEP 5 — THE VERDICT UNDER THE MATCHED NULL

The matched null is **`N_PSWAP`**: it swaps each player-season's *entire ordered series* with
another player-season's within the same season, so it destroys the between-player alignment
(which `N_CYCLIC` cannot) **while preserving each series' internal serial structure** — which is
D093's autocorrelation concern, the concern that motivated the cyclic null in the first place.
`N_PSWAP` honours both requirements at once. It is verified at power 1.00 on all three
components with type-I 0.05–0.10.

| stratum | n | dR2 | **p (`N_PSWAP`)** | null_mean | null_sd | MDE80 | above MDE80? |
|---|---|---|---|---|---|---|---|
| POOLED | 13,784 | 0.006488 | **0.001661** | 6.83e-05 | 9.82e-05 | 4.24e-04 | yes, 15.3x |
| DECISION | 5,111 | 0.001146 | **0.003322** | 1.39e-04 | 1.85e-04 | ~4e-04 | yes, ~2.8x |

`p = 0.001661` is the minimum attainable at R = 601.

> **D097's kill of `R08_player_ra_share → y_oreb` was a FALSE NEGATIVE. The cell survives the
> correctly matched, injection-verified null in both strata.**

## STEP 6 — WAS THE LEVEL THE PROBLEM TOO? (PREREG 6.6 — both possibilities, as directed)

D111 gives rebounds only a **15.7%** bottom-up penalty — the third lowest of six quantities —
and an offensive rebound is an **allocation of a shared budget**: exactly one player collects
each one. D111's rule says allocations of a shared budget do *not* survive aggregation from
below. So even with the null corrected, re-levelling might have been the real fix, or might
have been useless. Both were tested.

**(a) Re-levelling was never applicable.** `R08` is a `player_season` candidate. It fails
triage condition T2. Its mechanism is a property of a player; summing to team destroys the
variation rather than recovering it. **The level was not the problem.**

**(b) But the mechanism does survive being levelled up anyway.** Levelling `R08` to the roster
(`ROSTER_RA_SHARE`, the roster's mean prior restricted-area share) against **team** offensive
rebounds, n = 1,486 team-games, null `N_TSWAP` (swap team-season series within season),
injection-verified at power 1.00:

| base | dR2 | p | null_mean | null_sd | MDE80 | above MDE80? |
|---|---|---|---|---|---|---|
| `B_TEAM_COMPLETE` (7 col) | 0.004856 | 0.018272 | 7.64e-04 | 1.14e-03 | 3.56e-03 | yes |
| `B_TEAM_PLUS_OPP` (8 col) | 0.005468 | 0.006645 | 6.93e-04 | 9.78e-04 | 3.60e-03 | yes |

Unlike the four triage re-runs, this one **strengthens** when the opponent's prior allowed
offensive rebounds is added to the base, and holds under both references.

**Answer to the directed question: the null was wrong, the level was not.** Shot-location
profile predicts offensive rebounding at both levels. It is not a level artefact; it is a null
artefact. D111's 15.7% figure correctly predicted that re-levelling would not be where the
answer lay.

---

## COUNTERWEIGHT — WHAT THIS IS NOT

State these with the finding, every time it is quoted.

1. **The effect is 5.7x smaller where it would be used.** POOLED 0.006488 → DECISION 0.001146.
   POOLED carries cold-start and low-minute rows, where D097 itself observed the channel "is
   just predicting who plays". At DECISION it is **1.12x the single-cell floor and 0.49x the
   132-cell floor**.
2. **Family-wise multiplicity was not recomputed.** D097's family is 250 cells. I re-ran one.
   At DECISION, 0.001146 is well below the 132-cell floor of 0.00235, so it would very likely
   **not** clear a 250-cell family-wise threshold. `p = 0.003322` is a per-cell number.
3. **Every number here is in-sample.** No walk-forward, no season-stability, no out-of-sample
   propagation. D097's own walk-forward table shows how much these shrink.
4. **Between-player predictive power on top of a player's own history is a shrinkage story.**
   A player's restricted-area share is a position proxy; it refines a noisy estimate of who a
   player is. That is real and usable, but it is a cold-start / player-typing gain, not a
   game-to-game matchup signal. It belongs with D092's cold-start tiering work, not with the
   matchup channel.
5. **`R08`'s `y_reb` cells were ceiling kills** and remain dead. Only the `y_oreb` and `y_dreb`
   cells are affected by this re-examination.
6. **This is a lead, not a champion.** Nothing here is proposed for production.

## THE DEBT THIS LEAVES BEHIND

The failure mode is general: **a null that permutes WITHIN an entity is blind to a candidate
whose variance is BETWEEN entities**, and it announces itself by `null_mean > observed`.

The census records **213 killed cells at `player_season` level** and **337 at
`opp_team_season` level** — 550 of the 1,580 kills (299 and 427 respectively if surviving cells
are counted too). Wherever a within-entity null decided one of those, the verdict is
suspect by exactly the argument above. Several screens already recorded the diagnostic
(`var_share_between_entity`, `var_share_between_team_season`, `var_share_between_blocks`) and
also recorded `null_mean` — so the audit is a query, not a re-run:

> flag every recorded cell where the correct-level null was a within-entity scheme AND the
> candidate's between-entity variance share exceeds ~0.5, OR where `null_mean` exceeds the
> observed statistic.

That is the cheapest high-value follow-up this screen can name, and it is larger in scope than
the single cell it discharged.
