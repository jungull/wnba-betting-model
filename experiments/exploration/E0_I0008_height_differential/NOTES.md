# E0 I0008 — On-court height/size differential vs rebound efficiency

## Partition compliance (GRAPH_POLICY 13.2)

Filtered at the earliest possible point in every script, before any join:
- `build_rung1_rung2.py`: `mp = mp[mp["season"].isin([2021,2022,2023,2024])]` immediately after
  loading `data/masters/master_player.parquet` (line ~16, marked `# FILTER-POINT`).
- `build.py` (rung 3): `poss = poss[poss["season"].isin({"2021","2022","2023","2024"})]`
  immediately after loading `possessions_v2` (marked `# FILTER-POINT`), then events restricted
  to `game_id`s that survive that filter.
- 2025/2026 rows were never loaded into any dataframe used for analysis. Verified by printing
  `sorted(season.unique())` after every filter step (see script stdout, all show only
  2021-2024).

## Inherited defect (must not rediscover — from I0003)

On-court lineup attribution via clock-time joins to possession rows (`possessions_v2`
off_p1-5/def_p1-5 matched to event `clock_seconds_remaining` by interval) is only **~72%
accurate on side-of-play** (84% DRB, 43% ORB). Rung 3 below uses that exact join and inherits
that ceiling. Rungs 1 and 2 use **no on-court join at all** — that is why they were prioritized
first per the coordinator's ladder redirect.

## Data-integrity check performed mid-task (coordinator alert)

The coordinator flagged that several pre-built artifacts are fit through 2025/2026 and named a
general rule: check `<artifact>.manifest.json` for `fit_seasons`/`fit_through_season` including
2025/2026 before using any pre-built artifact; rebuild from raw per-season files if so.

- **`data/masters/master_player.parquet`** (used for rungs 1 and 2, source of
  `offensive_rebound_percentage`/`defensive_rebound_percentage` and `minutes`) — its manifest
  (`master_player.parquet.manifest.json`) states `"fit_through_season": 2026` and
  `"fit_seasons": [2021...2026]`. **This was not caught before rungs 1/2 were built and run.**
  Per the coordinator's rule this artifact should have been rebuilt from raw per-season files
  instead of used as-is. I checked for a clean per-season substitute
  (`data/wnba_boxscore_advanced_2021-2023.parquet` — 2024 is missing; `data/refresh_2026/traditional/`
  only has 2 individual game files; `data/possessions/possessions.parquet` is a different,
  aggregate object) and **no complete 2021-2024 per-season raw substitute exists in this
  worktree that I could find inside the time-box.** Rebuilding one is real engineering, not a
  re-run — the same character of problem I0003 flagged for lineup attribution.
  **Rungs 1 and 2 are therefore reported as UNCONFIRMED PENDING A CLEAN REBUILD, not as a
  cleared E0 pass**, even though row-level box-score counts (fga, reb, oreb, minutes) are
  game-level facts and not obviously a function of other seasons' data — I could not verify
  that assumption inside the time-box, so I am not asserting it.
- **`data/reference/player_bios.csv`** (height source, all rungs) — static biographical data,
  no manifest file exists, confirmed not season-fit (checked: no `.manifest.json` sibling in
  `data/reference/`).
- **`experiments/player_program/possessions_v2/`** and **`experiments/player_program/event_contract_v1/`**
  (rung 3) — no `.manifest.json` files exist in either directory (checked directory listing).
  Both are row-level parses of raw play-by-play (one row per possession / one row per PBP
  event), not statistically fit artifacts, and neither appears on the coordinator's contaminated
  list. Treated as clean for rung 3, but this was a directory-listing check, not a
  manifest-based one, since no manifest exists to read.

## Method and results by rung

### Rung 1 — player height vs opponent's season-long roster height (no on-court join)

`experiments/exploration/E0_I0008_height_differential/build_rung1_rung2.py` →
`player_game_height_vs_opponent.csv` (18,212 player-game rows, 2021-2024, minutes>0 only).

- `rung1_height_diff` = player's own height − opponent team's season minutes-weighted mean
  roster height (all players who logged minutes for that team that season).
- Target = `offensive_rebound_percentage` / `defensive_rebound_percentage` (already-computed
  per-game box efficiency stats from the flagged artifact — see caveat above).
- Own recent rate = trailing EWMA (halflife 5 games, min 3 games, `.shift(1)` so the current
  game never leaks into its own feature) of the player's own OREB%/DREB%, within season.

Raw correlations (n=18,212): `rung1_height_diff` vs OREB% = **0.299**; vs DREB% = **0.332**.
Right direction (taller relative to opponent → higher rebound share) and non-trivial magnitude.

OLS (manual, numpy — no scipy/sklearn in this environment):
| target | own-rate-only R² | height+own R² | incremental R² from height | n |
|---|---|---|---|---|
| OREB% | 0.1077 | 0.1280 | **+0.0203** | 16,345 |
| DREB% | 0.1442 | 0.1618 | **+0.0176** | 16,345 |

Height differential coefficient stays positive and stable in sign/magnitude after adding own
recent rate (OREB%: 0.0054→0.0030; DREB%: 0.0106→0.0054) — attenuated but not zeroed.

Bucket check (median split on own recent rate, assumption-light cross-check of the OLS): within
BOTH the low-own-rate and high-own-rate halves, `rung1_height_diff` still correlates with the
target (OREB%: 0.153 low / 0.207 high; DREB%: 0.174 low / 0.212 high, n≈8,170 each half) — the
height effect is not simply a proxy fully absorbed by a player's own recent form.

**Conditional cut — position** (DREB%, requested by coordinator as a within-class probe):
Guard (G) 0.149 (n=3,880), Forward (F) **0.367** (n=3,880), Center (C) 0.108 (n=1,940).
Signal concentrates hardest in forwards; centers (who are more uniformly tall already, less
height variance both for themselves and opponents) and guards show a real but visibly weaker
relationship.

**Season stability** (DREB%): 2021 r=0.337, 2022 r=0.357, 2023 r=0.316, 2024 r=0.323 — stable
across all four exploration seasons, no single-season artifact.

### Rung 2 — player height vs opponent's top-8-minutes rotation height (no on-court join)

Same construction, opponent height profile restricted to each team-season's top 8 players by
total season minutes (a cheap proxy for "expected active rotation" rather than full roster).
Results are essentially identical to rung 1 (correlations 0.297/0.330; incremental R² +0.020 /
+0.017) — restricting to the likely rotation vs. the whole roster made no material difference at
this level of screening. Not a distinct finding from rung 1; reported for completeness because
the coordinator asked for it as a separate rung.

### Rung 3 — actual on-court simultaneous lineup height differential (inherits 72% ceiling)

`build.py` → `rebound_events_height.csv` (66,566 rebound events with fully height-resolved
5-vs-5 on-court lineups, out of 81,393 rebound events in the 2021-2024 partition; 81,034 had a
valid enclosing possession with `lineup_valid_ten==True` before the height join dropped the
remainder for missing bio rows).

`off_minus_def_height` = mean height of the 5 offensive on-court players − mean height of the 5
defensive on-court players at the moment of the rebound. Outcome = `is_orb` (1 if the credited
rebounder's team matches the possession's offense team, i.e. an offensive rebound).

Result: **corr(off_minus_def_height, is_orb) = 0.023, n=66,566** — essentially flat. Quintile
buckets of height diff show ORB rate barely moving (0.943 → 0.957 → 0.955 → 0.959 → 0.958 from
most-defense-favored to most-offense-favored) and overall ORB rate in this dataset is 0.954
(this reflects that `is_orb` here is measuring "which team is credited," not overall ORB% of
opportunities — see limitation below). Stable near-zero across all four seasons (0.021-0.027).

**This null is AMBIGUOUS, not negative**, per the coordinator's explicit instruction: it may
mean the mechanism doesn't operate at the instant-of-rebound level, or it may mean the ~72%
lineup-attribution noise (inherited from I0003) and a further construction issue below wash out
a real effect.

**Separate construction limitation surfaced during this rung, worth flagging honestly**: `is_orb`
as built here is 1 for ~95% of matched rebound events, which is implausible for a true ORB rate
(WNBA ORB% on missed shots is normally ~25-30%). This indicates the `event_team_id ==
offense_team_id` comparison is not cleanly discriminating offense/defense in this construction
— likely a downstream symptom of the same clock-time possession-matching noise, possibly
compounded by `offense_team_id` sometimes reflecting the team that will next possess rather than
the team that just shot. **This rung's null should be read as evidence the construction needs
real rework, not as evidence about height.**

## What this does and does not mean

- Rungs 1/2 show a real, directionally-correct, season-stable, own-rate-surviving,
  position-varying relationship between pregame-observable height mismatch and rebound
  efficiency — **but the box-score source used for the outcome variable is flagged by the
  coordinator's manifest rule and was not rebuilt from clean per-season data inside this
  time-box.** This is a LEAD pending a clean rebuild, not a confirmed E0 pass.
- Rung 3's null is not informative about the height mechanism; it surfaced a distinct
  construction defect in offense/defense side attribution beyond the previously-known lineup
  ceiling.
- Per the user's explicit guard: if the coarse pregame proxy (rung 1) had come back null, that
  would kill only the coarse proxy, not the broader size/matchup thesis. It did not come back
  null — it came back as signal, subject to the data-integrity caveat above.
- Vertical jump / reach remain absent from the repo and were not sought.

## Artifacts

`experiments/exploration/E0_I0008_height_differential/`:
`build_rung1_rung2.py`, `analyze_rung1_rung2.py`, `player_game_height_vs_opponent.csv`,
`build.py`, `analyze_rung3.py`, `rebound_events_height.csv`, `player_season_reb_counts.csv`,
`NOTES.md` (this file).
