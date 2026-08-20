# E1_I0060 — the matchup family, measured on rate instead of points

**Prereg** `d53637d0fbe9971e2051316003af05cbc9dff64c58f318a8ff9d21194e4e1b7c`, frozen after the
frame's shape was printed and before any effect existed. **Exploration partition 2021–2024
only; 2025 and 2026 were never read, joined, plotted or described.** 14,259 complete rows,
242 players, 861 games, 48 opponent-team-seasons; 11,279 scored (2021 has no prior season).

---

## The answer in three lines

**Measuring on rate is a genuinely better surface, and it is worth about a fifth of what
switching from a plain average to an EWMA was worth.** The matchup increment is 35% larger on
rate than on points, and routing the forecast through rate × minutes rather than modelling
points directly improves MAE by **0.458%** all in.

**But the dilution hypothesis that motivated this screen is TRUE AND SMALL, and it does not
explain the nulls.** I predicted the rate/points ratio would exceed 1.5 for the opponent-defence
channel. **It is 1.21. That prediction failed.** The 2.4× figure I quoted from the programme's
record came from a different row set and a different base, and it does not reproduce here.

**Nothing that previously read as null came alive.** The shot-zone channel — the one I said was
the most promising candidate — is dead in its pregame-observable form. The channel that does
clear was already known.

---

## Preregistered predictions, scored

| | prediction | result |
|---|---|---|
| **P1** | opponent defence reproduces on rate and clears family-wise | **PASS** — ΔR² +0.002531, p_fwe 0.0005 |
| **P2** | dilution ratio for that channel > 1.5 | **FAIL** — ratio 1.21 |
| **P3** | at least one other channel clears family-wise | **PASS** — but see the post-hoc below, which guts it |
| **P4** | rate route does *not* beat the direct points route by > 0.002 R² *(sceptical)* | **PASS** — margin +0.001001 |
| **P5** | the pace negative control does not clear | **PASS** — ΔR² −0.004182, p_fwe 1.0000 |

## The six channels

| channel | ΔR² on rate | ΔR² on points | ratio | p_fwe | verdict |
|---|---|---|---|---|---|
| `C1_opp_def` opponent defensive rating | **+0.002531** | +0.002085 | 1.21 | 0.0005 | **clears** |
| `C2_zone_match` player zone mix · opponent zone leakiness | −0.000204 | −0.000043 | — | 0.9130 | below floor — **unresolved** |
| `C3a_usage_x_def` player usage × opponent defence | **+0.003737** | +0.002862 | 1.31 | 0.0005 | **clears** |
| `C3b_3rate_x_opp3` 3-pt rate × opponent 3-pt defence | +0.000501 | +0.000020 | — | 0.1104 | below floor — **unresolved** |
| `C3c_fta_x_oppfta` FT rate × opponent FT defence | +0.000731 | +0.000230 | — | 0.0490 | clears, then collapses (below) |
| `C4_opp_pace` **negative control** | −0.004182 | −0.000730 | — | 1.0000 | correctly null |

The negative control behaved exactly as required — strongly negative, nowhere near clearing.
Opponent pace moves *volume*, not efficiency, so on a rate response it is pure added noise and
a walk-forward fit is actively harmed by it. The pipeline is not leaking.

Detection floor, by injection: **0.001**. The permutation 95th percentile for a single channel
is +0.000420. `C2` and `C3b` sit below the floor and are reported **UNRESOLVED — not null.**
"We could not see it" is a different statement from "it is not there", and conflating those is
exactly the defect the old archetype screen's design forced.

## The post-hoc test the preregistration should have specified

`C3a` is *built from* `C1`. Testing each against a base that contains neither cannot tell them
apart. That test was not preregistered; it is run here and labelled post-hoc.

| | ΔR² on rate |
|---|---|
| `C1` alone over base | +0.002531 |
| `C3a` alone over base | +0.003737 |
| **`C3a` over base + `C1`** | **+0.001679** |
| `C1` over base + `C3a` | +0.000473 |
| both together | +0.004210 |
| **`C3c` over base + `C1` + `C3a`** | **−0.000169** |

Two things follow, and both cut against the headline.

**There is ONE channel here, not three.** The interaction is the better expression of it —
`C1` retains only 19% of its value once `C3a` is present, while `C3a` retains 45% the other way
— but they are largely the same information. And **`C3c`, which cleared the family-wise
correction on its own, contributes nothing once the other two are in.** It was carrying shared
variance. Counting it as a third channel would have been wrong, and the preregistered design
(each channel against a common base) would have let me.

The surviving channel is not new. D093 recorded the structural fact that sensitivity to
opponent defence rises with the player's own prior usage, and E1_I0023 asked whether the
interaction improved a forecast and returned SPLIT. This screen's contribution is that it
clears a proper family-wise correction on the rate, with a negative control and a measured
detection floor.

## What it is worth, in points

The only unit that matters. 11,279 held-out player-games, response sd 7.510.

| forecast | MAE | vs. baseline |
|---|---|---|
| direct points, no matchup | 4.17863 | — |
| direct points, with matchup | 4.16768 | +0.262% |
| two-stage rate × minutes, no matchup | 4.17266 | +0.143% |
| **two-stage rate × minutes, with matchup** | **4.15952** | **+0.458%** |

The matchup stack itself is worth **0.0131 points of MAE**. Switching to the rate route is worth
another 0.0059. Together, **0.458%**.

For scale: moving from a player's plain average to a tuned EWMA was worth **2.0%**. This entire
matchup family, measured the better way, is roughly **a quarter of that**.

## What this settles

- **Run the matchup family on rate, not points.** It is free, it is a better measurement
  surface, and it makes the increment 35% larger. That part of the recommendation holds.
- **But dilution was not hiding anything.** The nulls were nulls. At a ratio of 1.21, a channel
  that measured 0.0000 on points was not going to measure 0.006 on rate.
- **The shot-zone idea is closed in this form.** The strong version in the earlier screen needed
  the player's realised shot count, which is not knowable pre-tip. Built pregame-observably from
  prior zone shares, it has no forecasting content on rate: ΔR² −0.000204, below floor.
- **The real ceiling is elsewhere.** The base rate model reaches R² 0.156 on `ppm` against 0.478
  on points — most of what is predictable about a player's points is *how long they play*, not
  how well. That is where the remaining room is.

## What this does NOT establish

- **No wager-shaped claim.** S42 stands. A rate model is still a fitted scoring model.
- **Exploration only.** Nothing here has been near 2025–26, and the market still beats this
  model on the rows where both exist (D141, D150).
- **`C2` and `C3b` are unresolved, not dead.** They sit below a measured floor of 0.001. A
  larger sample could resolve them; this one cannot.
