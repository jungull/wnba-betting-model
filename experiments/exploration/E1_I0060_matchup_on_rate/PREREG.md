# E1_I0060 — matchup family measured on RATE, not on points

Frozen after `build_frame.py` had been run and its **shape** printed, and before any effect,
increment, comparison or null had been computed. The shape known at freezing: 18,212 rows,
14,259 complete-case, 242 players, 861 games, 48 opponent-team-seasons, seasons 2021–2024,
zone coverage 0.9908, and the standard deviation of each channel column. No relationship
between any channel and any response had been examined.

**Partition.** Exploration 2021–2024 only. 2025 and 2026 are never read, joined, plotted or
described. `build_frame.py` skips holdout shot-chart files by season number and asserts the
season set on the way out.

---

## The question

Every matchup screen this programme has run measured its channel against **points**. Points
are minutes × rate. A defensive matchup acts on the **rate**; it does not predict foul
trouble, a blowout benching, or a rotation change. On this frame minutes alone account for
about half the variance in points, so every one of those screens pushed a rate signal through
a noise amplifier.

The programme's own record already shows the cost: the opponent-defence channel measured
ΔR² = 0.0113 on points-per-minute against 0.0046 on points — the same channel, 2.4× larger
once minutes noise is removed.

So: **re-run the matchup family on the rate, with enough permutations to actually resolve the
multiplicity threshold, and find out whether anything that looked null was merely diluted.**

## Why the archetype precedent forces the permutation count

The previous archetype screen ran 200 permutations against 25 tests corrected at BH 10%. A
p-value cannot fall below 1/201 = 0.00498, while the rank-1 BH threshold was 0.10/25 = 0.004.
**That design could not have flagged a single strong matchup even if one existed.** Here: 6
channels, BH 10%, rank-1 threshold 0.0167, and **2,000 permutations** giving a floor of
0.0005 — a factor of 33 of headroom. This is fixed now so it cannot be trimmed later.

## Responses, frozen

- **PRIMARY: `ppm`** = points per minute, on rows with minutes > 0.
- **SECONDARY: `pts`**, carried only to measure the dilution ratio, never as the headline.

## Base reference, frozen

`B_HONEST` = walk-forward OLS of the response on
`[prior_ppm, prior_min, log1p(n_prior), is_home]`, coefficients fitted on seasons **strictly
earlier** than the season being scored. The earliest season present (2021) is therefore
unscored and is reported as such. For the `pts` response the same base is used with
`prior_pts` substituted for `prior_ppm`.

## Channels, frozen — six, named now

| id | channel |
|---|---|
| `C1_opp_def` | opponent's prior-only defensive rating minus the strictly-earlier league mean |
| `C2_zone_match` | player's prior zone attempt MIX · opponent's prior zone leakiness (points-per-attempt allowed vs league), summed over the five zones |
| `C3a_usage_x_def` | player's prior usage × `C1_opp_def` |
| `C3b_3rate_x_opp3` | player's prior 3-point rate × opponent's prior allowed 3-point rate |
| `C3c_fta_x_oppfta` | player's prior free-throw rate × opponent's prior allowed free-throw rate |
| `C4_opp_pace` | opponent's prior pace minus league — **NEGATIVE CONTROL.** Pace moves volume, not efficiency, so on a RATE response this must come back null. If `C4` clears, the pipeline is leaking and no other result may be read. |

`C2` deliberately uses the player's **prior** zone shares. The earlier shot-selection screen
conditioned on the player's **realised** attempts in the game being predicted, which is not
knowable pre-tip and is the specific reason that channel was never usable. This construction
is pregame-observable end to end.

## Statistic, frozen

Walk-forward **signed ΔR²**: R² of `B_HONEST + channel` minus R² of `B_HONEST`, both scored
on the identical held-out rows, with an unfrozen intercept. Reported per channel, and for the
`C3*` group also as a block.

## Nulls, frozen

1. **Cluster bootstrap by `game_id`**, 2,000 draws, seed 20260820 — 95% interval.
2. **Permutation**: reassign the **opponent-team-season label** within season, 2,000 draws,
   same seed. The whole opponent feature vector travels with the team, so cross-channel
   structure survives and a max-t family-wise statistic is valid.
3. **Multiplicity**: BH at 10% across the six channels, AND a max-t family-wise p from the
   same permutation draws. Both reported; the family-wise one governs.

## Detection floor, frozen

Before reading any real increment, a synthetic effect of known size is injected into the
response at ΔR² ∈ {0.001, 0.003, 0.010} and recovered through the identical pipeline. The
floor is the smallest injected value recovered above the 95th percentile of the permutation
null. **Any real increment below that floor is reported as UNRESOLVED, not as null.**

## The honest re-multiplication — committed now, not added later

A gain on the rate is not a gain on points, and changing the denominator is not a finding. So
whatever `ppm` returns, the screen ALSO reports:

**points forecast = (base rate + channel) × prior-minutes forecast**, scored on points, against
the same two-stage forecast without the channel, and against the direct points model.

Reporting a rate improvement without this step would be measuring a bigger number by choosing
a smaller denominator. It is preregistered here so it cannot be quietly dropped if it is
unflattering.

## Predictions, committed before computing

- **P1** `C1_opp_def` reproduces on `ppm` with signed ΔR² > 0 and clears the family-wise null.
- **P2** The dilution is real: for `C1`, ΔR²(ppm) / ΔR²(pts) > 1.5.
- **P3** At least one channel besides `C1` clears the family-wise correction — i.e. something
  that previously read as null was in fact diluted. **This is the screen's reason to exist.**
- **P4** *(the sceptical one, committed deliberately)* After re-multiplying through minutes,
  the rate-channel gain does **not** beat the direct points-channel gain by more than 0.002 R².
  If P3 passes and P4 also passes, the finding is "better measurement, same money".
- **P5** `C4_opp_pace`, the negative control, does not clear.

## What would make this screen worthless

- **`C4` clearing.** That would mean the pipeline leaks and every other number is void.
- **A channel below the detection floor.** Reported UNRESOLVED. "We could not see it" is not
  "it is not there" — that conflation is what the archetype screen's design forced.
- **The zone channel's coverage.** 0.9908 of zone cells match; the missing 0.9% are cells
  where a defence faced zero prior attempts in a zone. They are counted, never imputed.
- **Nothing here is a wager-shaped claim.** S42 stands. A rate model is still a fitted scoring
  model and this screen authorises no use of it.
