# E0 I0006 -- usage redistribution when a high-usage player is absent

**Partition compliance:** filtered to `season.between(2021, 2024)` immediately after load, in
`build_redistribution.py` line ~15, with an assertion. `season_type == 'Regular Season'` only.
Never read, joined, or printed anything from 2025/2026. Verified: `post-filter seasons present:
[2021, 2022, 2023, 2024]`.

**Data source:** `data/masters/master_player.parquet` (per-player-per-game box score, 33,712 rows
across 2021-2026; 19,642 after partition+regular-season filter). This has `usage_percentage`,
`minutes`, `dnp_reason` per player-game directly -- it does **not** require the clock-time
on-court lineup join that I0003 found to be only ~72% accurate on side-of-play. That known defect
does not apply to this screen's construction.

## Method

1. **High-usage rotation regulars**: player-team-season with mean `usage_percentage` >= 0.20 over
   games played (minutes > 0) and >= 15 games played. 167 player-team-season rows.
2. **Absence proxy**: rows for that player/team/season where `dnp_reason` is non-null and
   minutes == 0 (any DNP/DND/NWT reason -- injury, coach's decision, rest, etc., not
   distinguished). 451 absence-game rows.
3. **Teammate baseline**: for each absent player, each teammate's baseline usage = their mean
   `usage_percentage` across *other* games that season/team where the studied player *did* play
   (>= 5 such games required, to exclude callups/small samples).
4. **Redistribution**: `delta_usage = usage_percentage_in_absence_game - teammate_baseline_usage`,
   computed for every teammate who played in each absence game. 3,838 teammate-game rows across
   335 usable absence games (116 absence games dropped for having no teammate meeting the >=5
   control-game requirement).

## Results

### Q1 -- concentration (raw, before the placebo check)
Top-1 gainer's share of total positive `delta_usage`: mean 0.397, median 0.385, vs a naive
even-split baseline of 1/n_gainers (mean 0.199). Paired comparison: t=35.55. Read naively this
looks like a strong concentration signal.

### Critical robustness check -- placebo test (this is what kills the idea)
The Q1 comparison's "even split" baseline is not the right null. The right question is: **does
ordinary game-to-game noise in `usage_percentage`, with no absence at all, produce this same
apparent concentration?** Built a placebo (`placebo_check.py`): for 167 of the same high-usage
players, picked a random game they actually *played in* as a pseudo-event, rebuilt teammate
baselines leaving that game out, and computed the identical top1_share statistic.

- **Real absence games**: top1_share mean = 0.397 (n=335)
- **Placebo presence games (no absence, pure noise)**: top1_share mean = **0.508** (n=167)

The placebo is *more* concentrated than the real effect. Ordinary noise in single-game
`usage_percentage` readings against a multi-game mean baseline mechanically produces this
"someone always has a relatively big game" pattern even when nothing changed. The Q1 result is
not evidence of a redistribution effect; it is measurement variance. This alone is close to
sufficient to kill the idea, but the remaining checks were run to completion since they were
already in flight.

### Q2/Q3 -- stability (same absent player, repeat absences)
44 players had >= 3 usable absence games (mean ~1058 total data points). For each, looked at
whether the *same* teammate is the top usage-gainer across that player's absences. Modal
absorber's share of that player's absence games: mean 0.342, median 0.306 -- i.e. even the
*most common* top absorber for a given player only "wins" about 30% of that player's absence
games. Most players show 3-8 distinct top absorbers across their absences. Not stable.

### Q4 -- does teammate composition explain who absorbs it?
Two composition proxies tested, both null:
- **Season-baseline usage rank**: does the highest-baseline-usage teammate present become the top
  absorber? Observed match rate 7.2%, vs a naive random baseline of 9.9% (n=335) -- if anything
  *below* chance, not above. `followup.py` extended this to the full rank distribution: mean rank
  of the actual top absorber is 6.4th out of ~11.5 teammates present (near the middle, i.e.
  indistinguishable from random selection). Share landing in the top-3-by-baseline-usage: 28.1%
  observed vs 26.2% naive-random baseline -- no lift.
- **Position match** (`position_check.py`, using `data/reference/player_bios.csv` since
  `master_player.position` is populated for starters only): does the top absorber share the
  absent player's simplified position (G/F/C)? Observed match rate 32.5% vs a league
  position-distribution-implied random-match baseline of 32.3% -- no lift, essentially exact
  agreement with the null.

## Decision

**kill**

## Reason

The central question was whether vacated usage redistributes in a patterned, predictable way.
Every test that could show a pattern came back null or was shown to be an artifact:
- the apparent "concentration" (Q1) is smaller than what ordinary single-game noise alone
  produces on a placebo of non-absence games -- there is no detectable *absence-specific* effect
  to explain in the first place;
- who benefits is not stable game-to-game for the same absent player (Q2/Q3);
- who benefits is not predicted by teammate season-usage rank or by position match (Q4), both of
  which landed within noise of a naive random baseline.

This is a substantive, informative kill, not an inconclusive one: the placebo check specifically
rules out the most likely way this screen could have looked positive by accident (mistaking
ordinary box-score variance for a real redistribution effect). Given that a real effect exists
would need to survive a check this basic, and it did not, further investment (adding more
covariates, trying non-linear composition models) is unlikely to be worth it at E0/E1 rigor
without a different empirical entry point (e.g. a cleaner within-season control such as
back-to-back games, or explicitly separating injury-DNPs from coach's-decision-DNPs, which this
screen did not distinguish and which is the most plausible refinement if anyone revisits this).

## Honesty notes
- All numbers above are LEADS, never RESULTS (E0, non-claiming, GRAPH_POLICY 13.1).
- `dnp_reason` categories were not separated (injury/illness vs coach's decision vs rest) --
  pooling all DNP causes together is a real simplification; a coach's-decision DNP (often
  load-management for a healthy star, semi-predictable) and an injury DNP (more exogenous) could
  plausibly redistribute differently. This screen did not have time to split them (~45 min
  time-box) and that is the most likely reason a real effect could still exist and be missed here.
- The placebo used a random *one* game from the player's own presence games as the pseudo-event,
  not a matched blowout/back-to-back control; a more careful placebo could reduce noise further
  but is very unlikely to reverse the conclusion given the placebo's effect size *exceeds* the
  real one.
- Sample sizes are modest (335 real absence-games with usable teammate data, out of 451 total
  absence-game rows; 167 placebo games) -- consistent with the WNBA's small season sizes inside
  the exploration partition (966 games total across 2021-2024 per `EXPLORATION_PARTITION/1`).
- No lineup/on-court clock-time join was used anywhere in this construction, so the ~72%
  side-of-play attribution ceiling documented for I0003 does not apply here and is not a caveat
  on these numbers.

## Artifacts
`experiments/exploration/E0_I0006_usage_redistribution/`:
- `build_redistribution.py`, `analyze.py`, `followup.py`, `position_check.py`, `placebo_check.py`
  (scratch scripts, run in that order)
- `high_usage_players.csv`, `absence_games.csv`, `redistribution_rows.csv`,
  `per_absence_game_concentration.csv`, `top_absorber_per_game.csv`, `stability_by_player.csv`,
  `placebo_presence_games.csv` (intermediate/output data)
- `NOTES.md` (this file)
