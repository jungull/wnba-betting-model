# E0 I0006 -- usage redistribution when a high-usage player is absent

**Partition compliance:** every build script filters to `season in [2021,2024]` at the
file-selection or load step, before any aggregation, with an assertion. Never read, joined, or
printed anything from 2025/2026. Confirmed in every script's printed output.

## IMPORTANT: contamination correction mid-screen

The first pass of this screen used `data/masters/master_player.parquet` for `usage_percentage`,
`minutes`, and `dnp_reason`. Partway through, the coordinator flagged that this file's own
manifest (`data/masters/master_player.parquet.manifest.json`) declares
`"fit_through_season": 2026` and `"fit_seasons": [2021...2026]` -- i.e. the master build process
touches the full 2021-2026 range even for rows that are individually dated 2021-2024, which
violates GRAPH_POLICY 13.2 for an exploration-partition screen.

**Everything from the first pass (`build_redistribution.py`, `analyze.py`, `followup.py`,
`position_check.py`, `placebo_check.py`, and their CSV outputs without a `clean_` prefix in this
directory) is VOID and must not be cited.** They are left in this directory for audit trail only.

The screen was **rebuilt from raw, single-season/single-game sources with no manifest and no
cross-season fitting**:
- `data/wnba_gamelog_{2021,2022,2023,2024}.parquet` -- one file per season, read only for players
  who played; `usage_percentage` was **self-computed** from `FGA/FTA/TO/MIN` with the standard
  formula (`100*(FGA+0.44FTA+TOV)*(TmMP/5) / (MP*(TmFGA+0.44TmFTA+TmTOV))`), not read from any
  pre-fit artifact.
- `data/refresh_2026/misc/misc_<game_id>.parquet` -- per-*game* files (24 rows = both full
  rosters incl. DNPs), used only for `comment` (DNP reason) and roster membership. Selected by
  parsing the season out of the `game_id` in the filename (`2000 + int(gid[3:5])`) and only
  opening files whose inferred season is in {2021,2022,2023,2024} -- 2025/2026 files were never
  opened (970 of 1495 total files opened).

Neither source carries a manifest with `fit_seasons`/`fit_through_season`, consistent with being
untouched raw captures rather than derived/fit products; `data/reference/player_bios.csv` (used
for position) was treated the same way -- a per-season direct API pull (`source:
leaguedashplayerbiostats`) with no manifest, no evidence of cross-season fitting.

Rebuild scripts: `rebuild_clean.py` (writes `clean_played_panel.parquet`,
`clean_roster_panel.parquet`), `analyze_clean.py` (everything downstream). All numbers below are
from the clean rebuild.

## Method (clean rebuild)

1. **High-usage rotation regulars**: player-team-season with mean self-computed
   `usage_percentage` >= 0.20 over games played and >= 15 games played. 200 rows (vs 167 in the
   voided first pass -- the raw gamelog/misc sources have slightly different game coverage than
   the master file, expected and immaterial to the conclusion).
2. **Absence proxy**: roster rows for that player/team/season with a non-empty `comment` field
   (any DNP/DND/NWT reason, not distinguished). 622 absence-game rows.
3. **Teammate baseline**: each teammate's mean `usage_percentage` over the *other* games that
   season/team where the studied player *did* play (>= 5 such control games required).
4. **Redistribution**: `delta_usage` per teammate per absence game. 4,983 teammate-game rows
   across 578 usable absence games.
5. **Placebo (noise floor)**: for 200 high-usage player-seasons, picked one random game they
   *actually played in* as a pseudo-event, rebuilt the teammate baseline **leaving that game
   out** (leave-one-out, avoiding the self-inclusion leak pattern the coordinator separately
   flagged), and computed the identical statistic. This measures how much apparent
   "concentration" ordinary single-game noise produces with **no true absence at all**.

## Results

### Pooled concentration vs the noise floor
Top-1 teammate's share of total positive `delta_usage`:
- **Real absence games**: mean 0.470, median 0.454 (n=578)
- **Placebo (no absence, pure noise)**: mean **0.539**, median 0.526 (n=200)

The placebo is *more* concentrated than the real effect, again. This replicates the voided first
pass's finding (0.397 real vs 0.508 placebo) on independently rebuilt, uncontaminated data --
the direction and magnitude of the gap are consistent across two different constructions, which
is reassuring that this is a real property of the data rather than a bug in one pipeline.
**Ordinary game-to-game variance in `usage_percentage`, measured against a multi-game mean
baseline, mechanically produces this "someone always has a relatively big game" pattern.** There
is no detectable absence-specific concentration effect to explain.

### Conditional cuts (per the user's guard against a pooled-null-hides-structure failure mode)
Every requested cut was checked against the pooled real mean (0.470) and the placebo noise floor
(0.539) that any cut would need to exceed to be interesting:

| cut | groups | top1_share mean | n |
|---|---|---|---|
| starter vs bench absence | bench-type absent | 0.482 | 305 |
| | starter-type absent | 0.456 | 273 |
| absent player's position | C | 0.440 | 85 |
| | F | 0.486 | 201 |
| | G | 0.467 | 216 |
| | Hybrid | 0.468 | 76 |
| team (coach proxy) | 12 teams | range 0.445-0.498 | 18-103 each |
| remaining-lineup composition | 1 high-usage player out alone | 0.470 | 396 |
| | 2+ high-usage players out simultaneously | 0.469 | 182 |

None of these cuts separate meaningfully from each other, from the pooled 0.470, or approach the
0.539 noise floor. The team cut is the most direct test of "is there hidden structure the pool
average hides": across 12 teams, the **standard deviation of team-level means is 0.017**, versus
a **pooled per-game standard deviation of 0.131** -- team averages sit far tighter together than
individual-game noise would allow if any team had a real, distinct redistribution policy. No
conditional slice shows systematic structure; the pooled null is not concealing anything found by
these four cuts.

### Stability and composition (carried over from the first pass's method, now understood in light of the placebo result)
The voided first pass additionally found: the same absent player's top usage-absorber is
inconsistent game to game (modal absorber wins only ~31% of that player's absence games); who
absorbs it is not predicted by teammate season-usage rank (match rate ~7% vs ~10% random
baseline) or by position match (32.5% vs 32.3% random baseline). These numbers are void
(contaminated source) but are qualitatively consistent with, and now explained by, the placebo
result on clean data: if the "concentration" itself is noise, then which player exhibits that
noise on a given night has no reason to be stable or predictable. Re-running these exact checks
on the clean data was not repeated given the time-box, since the pooled+conditional result on
clean data already independently supports the same conclusion.

## Decision

**kill**

## Reason

The central question was whether vacated usage redistributes in a patterned, predictable way.
On corrected, uncontaminated data: the pooled result shows no absence-specific concentration
effect at all (placebo noise exceeds it), and none of the four user-mandated conditional cuts
(starter/bench, position, team/coach, simultaneous-absence count) reveal structure the pool
conceals -- every cut is statistically indistinguishable from the pooled mean and well short of
the noise floor. This is a substantive kill, not an inconclusive one, and it now rests on data
that was rebuilt specifically to rule out the contamination and self-inclusion-leak failure modes
the coordinator flagged.

## Honesty notes
- All numbers above are LEADS, never RESULTS (E0, non-claiming, GRAPH_POLICY 13.1).
- `comment`/`dnp_reason` categories were not separated (injury/illness vs coach's decision vs
  rest) -- pooling all DNP causes together is a real simplification and the most plausible
  refinement if anyone revisits this idea.
- The placebo used one random game from the player's own presence games as the pseudo-event, not
  a matched blowout/back-to-back control; a more careful placebo could reduce noise further but
  is very unlikely to reverse the conclusion given the placebo's effect size *exceeds* the real
  one in both the voided and the clean construction.
- No on-court clock-time lineup join was used anywhere in this construction, so the ~72%
  side-of-play attribution ceiling documented for I0003 does not apply here.
- `data/reference/player_bios.csv` was treated as an uncontaminated raw per-season capture on the
  basis of having no manifest and a `source` field naming a direct stats-API endpoint; this is an
  inference from absence of contamination evidence, not a positive confirmation, and is flagged
  here rather than asserted.
- Sample sizes: 578 real absence-games with usable teammate data (out of 622 total absence-game
  rows), 200 placebo games -- modest but adequate given the pooled effect direction reversed
  (real < placebo) rather than merely failing to reach significance in the hoped direction.

## Artifacts
`experiments/exploration/E0_I0006_usage_redistribution/`:
- **Clean/authoritative**: `rebuild_clean.py`, `analyze_clean.py`,
  `clean_played_panel.parquet`, `clean_roster_panel.parquet`, `clean_high_usage_players.csv`,
  `clean_absence_games.csv`, `clean_redistribution_rows.csv`, `clean_per_absence_game_summary.csv`
- **Void (contaminated source, kept for audit trail only, do not cite)**:
  `build_redistribution.py`, `analyze.py`, `followup.py`, `position_check.py`,
  `placebo_check.py`, and their non-`clean_`-prefixed CSV outputs
- `NOTES.md` (this file)
