# E0 I0009 — opponent defensive pressure as an ADDITIVE turnover predictor

Family: `F_TURNOVER_PRESSURE`.
Status: **E0 exploration, non-claiming.** This is a LEAD, never a RESULT, and may not be cited
as evidence for anything (GRAPH_POLICY §13.1). No significance claim, no promotion, no leaderboard.

## The hypothesis as registered

> Opponent defensive pressure (forced-turnover rate per 100 defensive possessions) carries useful
> **additive** signal for player turnover forecasting, independent of any interaction with player
> tendency.

**Provenance, respected and not inherited.** This idea exists only because screen I0005 noticed the
additive main effect *incidentally* while testing (and killing) an **interaction**. I0005 reported
ΔR² ≈ 0.0084 for the main effect, ~13x its interaction. That number was never screened on its own
terms — it had no placebo, no pregame-observable version, no per-season decomposition, and no
confound control. This screen re-derives it from scratch and puts it through all four. The I0005
number is treated here as a starting rumour, not a prior result.

## Partition compliance

**Exploration partition only: seasons 2021, 2022, 2023, 2024.** The filter is applied immediately
after each parquet load in `build_data.py`, before any join, aggregation, or inspection:

- `turnover_targets_v1/player_turnover_targets_v1.parquet` → `season.isin([2021..2024])` at load
  (18,216 rows survive; `rate_defined == True` leaves 18,178).
- `possessions_v2/possessions_raw_v2.parquet` → `season` is stored as **string** here; cast to int,
  then filtered the same way (155,149 rows survive). 2025/2026 rows were touched only by the
  boolean mask — never counted, described, printed, joined, or plotted.

**Artifact safety (§13.2.2):** neither input has a sibling `<artifact>.manifest.json`. Both are
row-per-game / row-per-possession raw artifacts with an explicit `season` column and no fitted
cross-season parameter, so row-level filtering is sufficient. Directory listings of
`turnover_targets_v1/` and `possessions_v2/` confirm no manifest file exists for either.

`assert` statements fail hard on a partition violation in both scripts, including on `game_date`
(`frame["game_date"].dt.year.between(2021, 2024).all()`).

### Partition verification on the actual output bytes

`analyze.py` re-opens each written file as raw text, regex-scans for **every 4-digit `20xx` token
anywhere in the file bytes** (not just the `season` column — this catches dates, ids, anything),
and asserts none fall outside 2021-2024:

```
player_game_analysis.csv: rows=18165  season column values=[2021, 2022, 2023, 2024]
    4-digit-year tokens anywhere in file bytes=['2021', '2022', '2023', '2024']  out-of-partition tokens=NONE
team_game_defense.csv:    rows=1940   season column values=[2021, 2022, 2023, 2024]
    4-digit-year tokens anywhere in file bytes=['2021', '2022', '2023', '2024']  out-of-partition tokens=NONE
PARTITION VERIFIED on output bytes: only 2021-2024 appear anywhere in the written files.
```

## What was built, and from which inputs

`build_data.py` is adapted from `E0_I0005_turnover_interaction/build_data.py` (**the original was
read, copied, and left unmodified**). Inputs are the same two parquets. Additions over I0005:

1. **`game_date` carried through** from `possessions_v2`, enabling a pregame measure.
2. **`points_scored` aggregated per defending team-game**, giving opponent points allowed per 100
   defensive possessions — the confound control.
3. **A team-game defensive table** (`team_game_defense.csv`, 1,940 rows = 970 games x 2 teams) so
   the placebo and the persistence check run off the same tallies as the main effect.

Predictors, all leakage-guarded:

- `player_tendency_loo` — player's season turnover rate per 100 offensive possessions **excluding
  the current game** (identical to I0005). Discipline 3 (LOO any aggregate correlated against its
  own members) applies and is not silently dropped.
- `opponent_pressure_loo` — **rung 1 measure.** Opponent's season defensive forced-TO rate per 100
  defensive possessions, excluding the current game. Idealised: uses the opponent's whole season
  including games that had not yet happened.
- `opponent_pressure_pregame` — **rung 2 measure.** Expanding within-season rate over the
  opponent's games with `game_date` **strictly before** the current game's date, shrunk toward an
  anchor by a pseudo-count of `K = 200` defensive possessions (~2.5 games; the anchor still carries
  ~20% weight at ~10 games observed). **Anchor rule:** prior-season team rate when season-1 is
  itself inside 2021-2024; otherwise that season's league-mean rate. 2021 therefore always uses the
  league-mean anchor — 2020 is outside the exploration partition and was never read. The league
  mean is a single scalar per season and cannot discriminate between opponents.
- `opponent_defrtg_loo` / `opponent_defrtg_pregame` — opponent points allowed per 100 defensive
  possessions, built the same two ways, as the opponent-quality control.

Final frame: **18,165 player-games** (`player_game_analysis.csv`), season counts
`{2021: 3878, 2022: 4508, 2023: 4886, 2024: 4893}`. 13 rows dropped for undefined LOO/pregame
predictors (thin single-game support) — the same 13 I0005 dropped and inspected.

`corr(opponent_pressure_loo, opponent_pressure_pregame) = 0.861`. 464 rows have zero prior opponent
games (season openers) and therefore sit entirely on the anchor.

Outcome and weighting are identical to I0005 so the numbers are directly comparable:
outcome `turnovers_per_100_off_poss`, weighted least squares with weight
`realised_off_possessions`. Seeds fixed (`20260807`); both scripts are deterministic.

## Rung 1 — the idealised additive effect

Baseline = player tendency (LOO) alone; then add opponent pressure (LOO).

| | n | R² base | R² full | **ΔR²** | β_pressure |
|---|---|---|---|---|---|
| **Pooled** | 18,165 | 0.14193 | 0.15035 | **0.008424** | +0.1573 |
| 2021 | 3,878 | 0.11983 | 0.13844 | **0.018606** | +0.1742 |
| 2022 | 4,508 | 0.11538 | 0.12209 | **0.006718** | +0.1603 |
| 2023 | 4,886 | 0.13773 | 0.14127 | **0.003540** | +0.1357 |
| 2024 | 4,893 | 0.18699 | 0.19407 | **0.007072** | +0.1474 |

The pooled figure reproduces I0005's incidental 0.0084 exactly, which is expected — same frame,
same construction.

**The per-season read is what matters here** (discipline 2, persistence beats significance). All
four seasons are **positive, same-signed, and of the same order**; the coefficient is remarkably
stable (+0.136 to +0.174, a ±12% band). The magnitude range across seasons is ~5x (0.0035 to
0.0186), so it is not uniform — but this is a categorically different pattern from the one that
killed I0005, whose per-season partials were 0.058 / **−0.002** / 0.021 / **0.002**, i.e. one
season carrying everything with a sign flip and two near-zeros. Here 2021 is the strongest season
but removing it does not remove the effect.

Practical size: opponent LOO pressure spans **13.82–23.27** forced TO per 100 defensive possessions
across team-seasons (range 9.45). The pooled β implies **+1.49 turnovers per 100 offensive
possessions** end-to-end against an outcome mean of 3.40 — i.e. the league's most disruptive
defense vs. its least is worth roughly 44% of the average player's turnover rate. That is a large
practical spread, not a rounding effect.

## Rung 2 — the pregame-observable version (the one that matters)

Same baseline; opponent pressure rebuilt using only the opponent's games **strictly before** this
game's date.

| | n | R² base | R² full | **ΔR²** | β_pressure |
|---|---|---|---|---|---|
| **Pooled** | 18,165 | 0.14193 | 0.14843 | **0.006505** | +0.1244 |
| 2021 | 3,878 | 0.11983 | 0.13487 | **0.015038** | +0.1567 |
| 2022 | 4,508 | 0.11538 | 0.12071 | **0.005329** | +0.1146 |
| 2023 | 4,886 | 0.13773 | 0.14001 | **0.002279** | +0.0976 |
| 2024 | 4,893 | 0.18699 | 0.19311 | **0.006121** | +0.1227 |

**This is the rung that decides the idea, and it survives.** The pregame version retains
**77% of the idealised ΔR²** (0.00651 vs 0.00842) and preserves the per-season ordering, all four
signs, and a tight coefficient band (+0.098 to +0.157). Attenuation of this size is exactly what
you expect from measuring the same quantity on less data (openers sit on an anchor; mid-season
estimates use half a season), not from the effect being an artifact of hindsight.

Practical size: pregame pressure spans 13.14–24.12 (range 10.98, wider than the LOO version because
early-season estimates are noisier); the pooled β implies **+1.37 turnovers per 100** end-to-end.

## Rung 3 — placebo (negative control)

Opponent identity is permuted **within season**: each player-game is attached the pregame pressure
of a **randomly chosen different** team in that same season, evaluated at that same game's date,
through the **identical** expanding/shrinkage construction. 200 permutations, seed 20260807.
`analyze.py` asserts that the precomputed lookup matrix reproduces the real pregame pressure exactly
before permuting, so real and placebo differ *only* in identity.

**Rung-2 (pregame) placebo floor, pooled:**

```
mean=0.000093  sd=0.000105  median=0.000057  p90=0.000268  p95=0.000313  p99=0.000427  max=0.000504
REAL = 0.006505   →   0 of 200 placebo draws >= real
```

The real effect is **~70x the placebo mean and ~13x the largest of 200 placebo draws.**

**Per season:**

| season | placebo mean | placebo p95 | placebo max | real ΔR² | draws ≥ real |
|---|---|---|---|---|---|
| 2021 | 0.000395 | 0.001503 | 0.002829 | 0.015038 | 0/200 |
| 2022 | 0.000243 | 0.000877 | 0.001800 | 0.005329 | 0/200 |
| 2023 | 0.000166 | 0.000688 | **0.002133** | **0.002279** | 0/200 |
| 2024 | 0.000172 | 0.000657 | 0.001169 | 0.006121 | 0/200 |

**Honest caveat on 2023:** no placebo draw exceeded the real value, but 2023's real ΔR² (0.002279)
is only **1.07x the placebo maximum** (0.002133). 2023 clears the floor, but barely — it is the one
season where this effect is not comfortably separated from noise. 2021, 2022 and 2024 clear their
own maxima by 5.3x, 3.0x and 5.2x respectively.

A placebo was also run for the **rung-1 (idealised)** measure: mean 0.000143, p95 0.000405,
max 0.000755 vs real 0.008424 — 0/200 draws ≥ real, an 11x margin over the maximum.

This is the discipline-1 check that I0006 lacked. Unlike I0006, the floor here is far *below* the
real effect rather than above it.

## Rung 4 — is the predictor itself forecastable?

An opponent trait is only usable if it persists, since the pregame estimate is an extrapolation.

**(a) Season-over-season correlation of team forced-TO rate per 100 defensive possessions:**

```
2021 -> 2022:  r = +0.474  (n = 12 teams)
2022 -> 2023:  r = +0.662  (n = 12)
2023 -> 2024:  r = +0.410  (n = 12)
pooled across consecutive pairs: r = +0.464  (n = 36 team-season pairs)
```

**(b) Within-season split-half (first half vs second half of each team's schedule):**

```
2021: r = +0.673   2022: r = +0.360   2023: r = +0.742   2024: r = +0.516
pooled: r = +0.547  (n = 48 team-seasons)
```

Both are positive in every split. Team defensive pressure **is** a persistent trait: roughly half
the within-season variance carries from one half of a schedule to the other, and ~46% of the
signal survives an offseason. This is the rung that most cleanly separates this idea from a noise
artifact — a trait that persists at r ≈ 0.55 within season is exactly the kind of thing an
expanding pregame estimate can actually track. **Caveat: n = 12 teams per season.** These
correlations have wide confidence intervals; the season-to-season range (+0.36 to +0.74) is
consistent with sampling noise around a single underlying value and should not be over-read.

## Confound check — is pressure just opponent quality?

Control added: opponent points allowed per 100 defensive possessions, built LOO and pregame the
same way as pressure.

```
corr(pressure_LOO, defrtg_LOO)         = -0.404
corr(pressure_pregame, defrtg_pregame) = -0.390
```

Pressure and overall defensive quality are meaningfully but not dominantly correlated (high-pressure
defenses do allow fewer points, sensibly).

| | uncontrolled ΔR² | **controlled ΔR²** | retained |
|---|---|---|---|
| Rung 1 (LOO) | 0.008424 | **0.007529** | 89% |
| Rung 2 (pregame) | 0.006505 | **0.005696** | 88% |

Per-season, rung-2 controlled: 2021 = 0.014230, 2022 = 0.006093, 2023 = 0.002108, 2024 = 0.002794.
Pressure's contribution does **not** vanish under the control — ~88% survives pooled, and the
coefficient is essentially unchanged (+0.1244 → +0.1263). **But note 2024 drops from 0.006121 to
0.002794 under the control** (2022 actually rises slightly). So the per-season stability is
noticeably worse *with* the control than without it, and pooled robustness is partly masking that.
Pace is already largely normalized away by the per-100-possessions outcome.

## Verdict

**`keep-as-lead`**

Reason: the additive effect survives all four rungs — it is not an artifact of hindsight (rung 2
retains 77% of rung 1), it is 13x the largest of 200 identity-permuted placebo draws with the same
construction, its per-season components are all positive and same-signed with a coefficient stable
within ±12% (unlike I0005's sign-flipping interaction, which is why that was killed), the predictor
itself persists (within-season split-half r = +0.55, season-over-season r = +0.46), and ~88% of it
survives an opponent-quality control. It is a lead worth an E1, not a result.

## What was NOT tested — may not be claimed

Flagged explicitly, in the same spirit that produced this idea from I0005's incidental observation.
None of the following was screened; do not treat any of it as established, and if any is worth
pursuing, log it as a **fresh, separately-screened idea**:

1. **The baseline is only player tendency.** ΔR² is measured against a one-variable model. A real
   forecasting model would already contain rest, home/away, teammate context, opponent pace, and
   the player's recent form. Pressure may be partly redundant with those. **The ΔR² here is an
   upper bound on marginal value in a real model, not an estimate of it.**
2. **Home/away is uncontrolled, and this is the most likely remaining confound.** Teams plausibly
   force more turnovers at home; opponent pressure computed over a mixed home/away schedule could
   partly encode venue. Not tested. This is the first thing an E1 should rule out.
3. **Rung 2's baseline still uses LOO player tendency**, which is *not* pregame-observable. Rung 2
   is therefore a hybrid: pregame opponent side, hindsight player side. A fully pregame version
   (expanding player tendency too) was not built. Direction of bias is not obvious and was not
   determined.
4. **No mechanism split.** Inherited from I0005: the target has no steal-induced vs. unforced and no
   live-ball vs. dead-ball split (`"no_steal_linkage": true` in the target receipt). Whether the
   effect is concentrated in steal-type turnovers — which would be the mechanistically satisfying
   result — is unknown and untestable from this frame.
5. **Rung 4's persistence rests on n = 12 teams per season.** The correlations are positive
   everywhere but individually imprecise.
6. **2023 barely clears its placebo maximum (1.07x).** One of four seasons is only marginally
   separated from noise. Not a kill, but not clean either.
7. **The confound control degrades per-season stability** (2024: 0.0061 → 0.0028). Whether the
   pooled controlled figure is being propped up by 2021 was not investigated further.
8. **Incidental, untested, flagged not claimed:** the player-tendency-only baseline R² varies
   substantially by season (0.115 in 2022 to 0.187 in 2024). Something about 2024 makes player
   turnover rate markedly more predictable from tendency alone. That is a separate observation of
   unknown cause — possibly a data-coverage or rule change — and it is **not** part of this
   screen's verdict.
9. **No forecasting or betting-relevant evaluation of any kind.** ΔR² on in-sample weighted least
   squares is not out-of-sample skill and is certainly not edge against a market line. E0 does not
   do that and this screen did not.

## Artifacts

- `experiments/exploration/E0_I0009_additive_pressure/pressure_lib.py` — shared pregame lookup, used
  by both the real and placebo paths so they cannot diverge.
- `experiments/exploration/E0_I0009_additive_pressure/build_data.py`
- `experiments/exploration/E0_I0009_additive_pressure/analyze.py`
- `experiments/exploration/E0_I0009_additive_pressure/player_game_analysis.csv` (18,165 rows, 2021-2024 only)
- `experiments/exploration/E0_I0009_additive_pressure/team_game_defense.csv` (1,940 rows, 2021-2024 only)
- `experiments/exploration/E0_I0009_additive_pressure/summary.json`
- `experiments/exploration/E0_I0009_additive_pressure/run_log.txt` (actual stdout of both runs)
