# E0 I0005 — turnover tendency x opponent defensive pressure interaction

Status: **E0 exploration, non-claiming.** This is a LEAD, never a RESULT, and may not be cited
as evidence for anything (GRAPH_POLICY §13.1).

## Partition compliance

**Exploration partition only: seasons 2021, 2022, 2023, 2024.** The filter is applied
immediately after each parquet load, in `build_data.py`, before any join, aggregation, or
inspection:
- `turnover_targets_v1/player_turnover_targets_v1.parquet` → filtered to `season.isin([2021..2024])` at load (18,216 of the parquet's rows survive; the pre-filter row count / 2025-26 content was never read).
- `possessions_v2/possessions_raw_v2.parquet` → `season` column is stored as **string** in this
  parquet (`'2021'`..`'2026'`); cast to int and filtered the same way (155,149 of 238,563 rows
  survive). 2025/2026 rows were touched only by the boolean filter mask, never read, counted,
  described, or joined.

Confirmed by directly inspecting the output CSV: `player_game_analysis.csv` season value counts
are `{2021: 3878, 2022: 4508, 2023: 4886, 2024: 4893}` — no 2025/2026 rows present. An `assert`
in both scripts fails hard if that were violated.

## What existed already (reused, not reinvented)

- **Turnover mechanism taxonomy**: `turnover_targets_v1/player_turnover_targets_v1.parquet` has a
  21-category violation-type breakdown rolling to a 7-category `mechanism_group`
  (`bad_pass`, `lost_ball`, `offensive_foul`, `travel_footwork`, `shot_clock`, `other_violation`,
  `unknown`). **There is no steal-induced-vs-unforced or live-ball-vs-dead-ball split.** The
  target-build receipt states `"no_steal_linkage": true` explicitly — a `steal_player_id` column
  exists in `event_contract_v1/canonical_player_events_v1.parquet` but was deliberately never
  joined into the turnover taxonomy. Building that linkage was out of scope for a 45-minute
  screen; this run used the mechanism-agnostic rate target as-is.
- **Turnover rate target**: `turnovers_per_100_off_poss = 100 * turnovers / realised_off_possessions`,
  defined only where `rate_defined` is true. `realised_off_possessions` is explicitly flagged
  `"not_a_complete_opportunity_denominator"` in the frozen receipt (it's on-court possession
  membership, not touches/passes/ball-handling) — this run inherits that same limitation as its
  exposure measure; it is a possessions proxy, not a touches count.
- **Retracted prior finding (read, not repeated)**: `turnover_p2_v1/P2_SUPERSESSION.md` documents
  Arm G (`turnover_rate_role_context_v1`, feature `offensive_involvement_proxy`) — its published
  gain (0.001373) was **15.92x smaller** than the leak alone (0.021804) once the leak's null mask
  was shown to exactly equal the post-cutoff `did_appear` indicator; on rows where the feature was
  actually observed, Arm G was *worse* than incumbent. This run's own missingness check (below)
  was run specifically because of that prior.
- **A candidate opponent-pressure formulation already exists at the design stage** (not frozen,
  not implemented): `stage2b/P36_IMPLEMENT_ARMS/arms/A20/arm_a20.py`,
  `A20_forced_turnover_contrast`, defines `ftr_team` as an expanding same-season mean of a team's
  defensive-possession forced-turnover share. This screen's `opponent_pressure_loo` is
  methodologically similar (season-level forced-TO rate, leakage-guarded) but computed
  independently and directly from `possessions_v2` for this screen only.

## Construction

`build_data.py`:
1. Player exposure/rate: from `turnover_targets_v1`, filtered to `rate_defined == True`
   (18,178 rows after the season filter).
2. Opponent identity + pressure: from `possessions_v2`, derive a `(game_id, team_id) ->
   opponent_team_id` schedule from the offense/defense pair on each possession, then compute
   each team's per-game defensive possession count and forced-turnover count
   (`end_reason == 'turnover'`).
3. **Leakage guard — leave-one-game-out (LOO) construction for BOTH predictors:**
   - `player_tendency_loo`: player's season turnover rate **excluding the current game**
     (season totals minus this game's own turnovers/possessions).
   - `opponent_pressure_loo`: the opponent's own season defensive forced-TO rate **excluding the
     current game** (their season totals as a defense minus this game's contribution).
   Neither predictor is mechanically part of the outcome it explains — using same-game figures
   for either would trivially inflate the apparent interaction (opponent pressure computed from
   the very possessions that include this player's turnovers).
4. Merge to one row per player-game: 18,165 rows survive after dropping 13 rows where a player or
   team had zero LOO possessions (single-game-in-season appearances — inspected directly; all 13
   are near-zero-turnover single-game players, not a pattern that tracks the outcome, so this is
   not read as a leakage signal, just thin support).

Output: `player_game_analysis.csv` (18,165 rows, columns include `turnovers_per_100_off_poss`,
`player_tendency_loo`, `opponent_pressure_loo`, `realised_off_possessions`, `minutes`, `season`).

## Results (`analyze.py`)

**1. Do opponents differ systematically in turnover creation (pressure)?** Yes, non-trivially.
`opponent_pressure_loo` (defensive forced-TO rate per 100 defensive possessions) ranges 13.8–23.3
across team-seasons (mean 17.4, sd 1.75) — roughly a 70% spread of the mean. Adding it as a main
effect to a model that already has the player's own tendency improves weighted R² from **0.1419
to 0.1504** (ΔR² = 0.0084), a real and larger-than-noise gain on its own.

**2. Does the interaction (player tendency x opponent pressure) carry signal beyond that pooled
picture?** Weak, and not persuasive on close inspection:
- Adding the interaction term to the additive model raises weighted R² by only **0.00062**
  (0.1504 → 0.1510) — roughly **13x smaller** than the opponent main effect's own contribution.
- A partial-correlation permutation test (interaction term vs. residualized outcome, both
  residualized against the additive model; null built by shuffling player tendency within season,
  n=2000 permutations) gives observed partial correlation **0.0238**, two-sided **p = 0.004**.
  Statistically distinguishable from zero at this sample size (n=18,165), but the effect size
  itself is small.
- **Direction is sensible**: a tercile x tercile heatmap (player tendency x opponent pressure,
  weighted mean turnover rate per cell) is monotonic in both dimensions, and the high-tendency
  group's rate rises MORE from low- to high-pressure opponents (+0.699 pts) than the low-tendency
  group's does (+0.374 pts) — a difference-in-differences of +0.325, i.e. turnover-prone players
  are somewhat more exposed to pressure, which is the mechanistically plausible sign.
- **Persistence across seasons is weak.** Per-season partial correlations: 2021 = **0.058**,
  2022 = **-0.002**, 2023 = **0.021**, 2024 = **0.002**. The effect is carried almost entirely by
  2021; two of four seasons are indistinguishable from zero and one is essentially sign-flipped.
  This does not look like a persistent effect — it looks like the pooled significance is driven by
  sample size plus one strong season.
- **Role concentration**: partial correlation by minutes tercile is flat (0.028 / 0.014 / 0.025) —
  no evidence the (already weak) effect concentrates in a particular role.

## Decision: kill (the interaction specifically)

The interaction term is directionally sensible and nominally significant by a permutation test,
but its effect size is roughly an order of magnitude smaller than the plain additive
opponent-pressure effect, and it does not replicate across the four available season splits
(near-zero or sign-flipped in half of them). That combination — small effect, not persistent — is
exactly what E0/E1 is supposed to screen out cheaply, per GRAPH_POLICY §13's own framing
(statistically significant-at-scale but practically negligible and non-persistent). Killing here
costs nothing per §13.4.

**Separable observation, not part of this idea's verdict**: the opponent-pressure **main effect**
(sub-question 2, independent of any interaction) is real and non-trivial (ΔR² 0.0084 standalone
vs. 0.0006 for the interaction) and untested elsewhere in the registry as far as this screen
found. If a future idea wants to pursue it, it should be logged as a fresh, separately-screened
idea (a plain additive opponent-forced-TO-rate feature, not an interaction) rather than treated as
part of I0005's result — I0005's hypothesis was specifically about the interaction.

## Response to coordinator hazard notice (mid-run)

Two hazards were flagged by sibling screens while this run was already in progress:

1. **Holdout-contaminated pre-built artifacts.** Neither source file used here
   (`turnover_targets_v1/player_turnover_targets_v1.parquet`,
   `possessions_v2/possessions_raw_v2.parquet`) is on the confirmed-contaminated list. Both are
   checked directly: they have no `manifest.json`, but their accompanying receipts
   (`TURNOVER_TARGET_RECEIPT.json`, `POSSESSION_INTEGRITY_RECEIPT_V2.json`) describe row-level
   extraction from box score / play-by-play sources with **no cross-season fitted parameter** —
   `turnovers_per_100_off_poss` is computed independently per row from that row's own game data,
   and `possessions_raw_v2` rows are per-possession extractions, not season-normalized or
   z-scored. This is structurally different from the confirmed-contaminated artifacts (RAPM,
   zone-map z-scores, calibration params, walk-forward files), which involve fitting a parameter
   across a training window that included 2025/26. There is no fitted scalar here that could carry
   holdout information backward into a 2021-2024 row. Both files also contain 2025/26 rows
   alongside 2021-2024 (confirmed earlier in this run), but this screen's own season filter runs
   *before* any aggregation (see Partition compliance above), so those rows never entered any
   computation regardless.
2. **Self-inclusion leak via opponent-pressure aggregates.** This was already designed against
   before the notice arrived: both `player_tendency_loo` and `opponent_pressure_loo` are built
   **leave-one-game-out at construction time** (§ Construction, step 3) — the current game's own
   turnovers/possessions are subtracted from the season total before being used as a predictor for
   that same game. No correlation in this NOTES was computed against a non-LOO baseline; there is
   nothing to rerun.

## Honesty / leakage note

Both predictors are leave-one-game-out by construction, so neither can trivially explain the
outcome by definition. The 13 dropped rows (thin-support single-game players) were inspected
directly and are not a pattern correlated with the outcome. No feature here carries the Arm-G
missingness signature (a null mask equal to an outcome-adjacent indicator) — LOO undefined rows
are dropped outright, not imputed, so there is no silent missingness channel for the model to
exploit.

## Artifacts

- `experiments/exploration/E0_I0005_turnover_interaction/build_data.py`
- `experiments/exploration/E0_I0005_turnover_interaction/analyze.py`
- `experiments/exploration/E0_I0005_turnover_interaction/player_game_analysis.csv` (18,165 rows, 2021-2024 only)
- `experiments/exploration/E0_I0005_turnover_interaction/tercile_heatmap.csv`
- `experiments/exploration/E0_I0005_turnover_interaction/summary.json`
