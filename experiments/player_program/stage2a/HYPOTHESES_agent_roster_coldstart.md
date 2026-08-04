# Stage 2A hypotheses — source: `agent_roster_coldstart`

**Mandate.** Roster transition and low-support / cold-start states: season boundaries, roster
turnover, expansion and relocated franchises, early-season identity, mid-season movement,
prior-season→current-season continuity, international-window absences, and what a "team" means
across a season boundary when much of the roster has changed.

**Lane.** Ideation only. Nothing here was fitted, tuned, selected or scored. No accuracy number,
no model, and no realised-pace aggregate was computed by this source. Where a direction is claimed
it is derived from the frozen packet's own reported strata or from a structural argument, and it is
labelled as such.

**Evidence used.**
- `experiments/player_program/stage2a/EVIDENCE_PACKET.json`
  (sha256 `f373e3eed710026c9d82ff88aad1e9a2cae640ee461a5d7df5208d76abaf1e4e`, verified).
- `experiments/player_program/build_projected_exposure.py` (read only).
- Read-only **existence and coverage** inspection of frozen artifacts, listed in §1.

**Discipline note.** The packet's `cutoff_valid_availability_table` records availability, not proof
of cutoff validity, and the construction receipt's own `information_available_at_cutoff` flags are
declarations bound by a receipt, not verifications (PROGRAM_STATE gap `cutoff_validity_asserted`).
Every cutoff claim below is therefore stated as *what would have to be true*, with the check named.

---

## 0. What I deliberately did not compute

To stay inside the lane I did **not** compute: realised `game_pace` means by season or by team; any
error, bias, MAE or calibration number; any fit; any correlation. Several hypotheses below would be
sharper if the league's season-over-season pace drift were known. It is not known to me, and I have
written the expected directions so that they do not silently assume a sign. Where a sign genuinely
cannot be pinned down without that quantity, I say so.

---

## 1. Coverage and structure findings (read-only; these are facts, not results)

These changed how I wrote the hypotheses, so they are recorded first. Each is an existence/coverage
check on a frozen artifact.

**F1 — the level-3 tier is a mixture of two mechanistically different populations.**
All 37 `league_prior_all` rows and all 8 `unresolved_no_prior_games` rows decompose as:

| population | n team-games | dates |
|---|---|---|
| 2021 opening day, no earlier games at all (level 4) | 8 | 2021-05-14 |
| 2021 season start — established franchises, repo simply lacks 2020 and earlier (level 3) | 28 | 2021-05-15 .. 2021-05-28 |
| genuine expansion franchise, first three games (level 3) | 9 | GSV 2025-05-16/21/23; TOR 2026-05-08/13/15; PDX 2026-05-09/12/14 |

The 36 rows from 2021 are **left-censoring of the dataset**, not a cold start in the world. The 9
expansion rows are the condition that recurs. Any "cold start" arm validated mostly on the 2021 rows
is being validated on a population that will never occur again.

**F2 — the `support` axis is not comparable across tiers.** For level-3 rows,
`n_history_games` is the **cumulative league game count**, not team support: 970 for GSV in 2025 and
1,280–1,300 for the 2026 expansion teams. The packet's worst stratum — support `">10"`, n=23,
MAE 4.538, sd 5.504 — is therefore mislabeled. It is not "abundant support"; it is **zero team
support**, backed by a large league count. Any arm chosen against the current support strata is
being chosen against a broken axis.

**F3 — the level-3 anchor is a six-season average.** For a 2026 expansion team the league prior is
the cumulative mean over ~1,290 games spanning 2021–2026 on strictly earlier dates. Its effective
half-life is the whole dataset.

**F4 — season openers are a total roster-evidence blackout under the primary regime.** There are
exactly 76 season-opening team-games (one per team per season: 12/12/12/12/13/15). In
`prediction_contract_v5/player_game_enriched.parquet` these are `team_game_index == 0`, 2,455
candidate rows, and **every one is `universe_tier == B`**: 920 `B_s2_weak_fallback` (prior-season
affiliation) and 1,535 `B_transaction_sensitivity` (retrospectively scraped). **Zero `A_primary`
rows.** `is_cold_start` is 98.9% on those rows. The 76 team-games missing from `A_primary` coverage
(2,914 of 2,990) are exactly these openers, and their pace tiers are 61 prior-season, 7 league-prior,
8 unresolved. So the moment the pace prior is weakest is the moment the primary-regime roster
evidence does not exist at all.

**F5 — opponent-tier contamination is invisible in the packet's stratification.** The projection is
the unweighted mean of *both* sides' estimates, so a game is only as good as its worse side. Joint
crosstab of own vs opponent `pace_level` over 2,990 team-games:

| own \ opp | 1 | 2 | 3 | 4 |
|---|---|---|---|---|
| 1 | 2732 | 22 | 8 | 0 |
| 2 | 22 | 154 | 7 | 0 |
| 3 | 8 | 7 | 22 | 0 |
| 4 | 0 | 0 | 0 | 8 |

**30 team-games have own level 1 but a fallback-tier opponent**, and they are currently reported
inside the clean 2,762-row `team_window_same_season` stratum. Symmetrically 22 level-2 rows are
averaged with a level-1 opponent, which flatters the level-2 stratum.

**F6 — long layoffs in this span are Olympic breaks, and they are league-wide.** Within-season
own-team layoff ≥ 14 days occurs on exactly 24 team-games: 12 in 2021 and 12 in 2024. The
league-wide schedule gaps are 2021-07-11 → 2021-08-15 (35 days, Tokyo) and 2024-07-17 → 2024-08-15
(29 days, Paris). All other in-season breaks are 4–7 days (All-Star). Layoff ≥ 7 days occurs on 103
team-games. Offseason gaps are 201–243 days. All schedule-derived, 2,990/2,990.

**F7 — franchise identity.** `data/reference/team_cities.csv` (16 rows) carries
`first_season` per franchise: GSV 2025, PDX 2026, TOR 2026, all others 2021. The PHO→PHX pair is a
**rebrand within the same `team_id` and the same arena/lat/lon**, not a relocation. **There is no
relocation in this span.** Hypotheses about relocated franchises therefore have zero support here
and I have not written any.

**F8 — in-season movement is rare.** Players appearing for more than one team within a season:
2021:14, 2022:16, 2023:11, 2024:12, 2025:27, 2026:11 (partial), over 1,058 player-seasons. Distinct
players used per team-season (minutes > 0) averages 14–16, min 12, max 21. **The continuity signal
has low variance in this league**, which is the main reason I expect several of my own hypotheses to
fail.

**F9 — participation history is complete; roster *snapshots* are not.**
`data/masters/master_player.parquet` has 33,712 rows over 2021–2026, `minutes` null on 16.0% (DNP
rows), 28,322 rows with minutes > 0, and its `observed_time` spans only **2026-07-31 → 2026-08-01**
— a single retrospective scrape. It is a legitimate source of *lagged realised participation*; it is
**not** a point-in-time roster feed. `possessions_raw_v2` carries `off_p1..off_p5` / `def_p1..def_p5`
with `lineup_valid_ten` ≥ 99.41% in every season (238,060 of 238,563 possessions
`valid_ten_player`), so possession-weighted on-court history is available lagged.

**F10 — the contract's own roster timestamps pass their stated test, but coarsely.** Over all 35,629
`A_primary` rows, `src_asof_roster`, `candidate_evidence_time`, `candidate_published_time` and
`candidate_observed_time` are **each ≤ `forecast_cutoff` on every row (0 violations)**. But
`cutoff_policy` is `date_only_prior_day_cutoff` on 25,368 rows (71%) with `exact_cutoff_ok = False`;
only 10,261 rows (29%) use `exact_tip_T-90m`. `cutoff_source` is `inherited_from_v4` on all rows.
This is consistent with the receipt's declaration but does not verify it, and the 71% date-only
binding is a real precision limit on anything built from the candidate set.

**F11 — projected minutes are pace-independent, so bottom-up weighting is not circular.** In
`build_projected_exposure.py`, `allocate()` consumes only `raw_expected_minutes`; the pace estimate
enters afterwards as a multiplier (`off = projected_team_off_possessions * (minutes / 40)`).
Therefore `projected_player_possessions_v1.projected_minutes` may be used as a weight in a new team
possession estimator without circularity. Coverage: 35,629 rows / 2,914 team-games under
`tier_a_only` — again missing exactly the 76 openers.

**F12 — sources present in the repository that the packet's availability table does not mention.**
This is a correction, offered with the caveats that follow in §3.

| path | rows | span | what it carries |
|---|---|---|---|
| `data/reference/team_cities.csv` | 16 | 2021–2026 | `team_id`, `franchise`, `first_season`, `last_season`, `city`, `arena`, `lat`, `lon`, `elevation_ft`, `timezone` |
| `data/reference/player_bios.csv` | 1,058 | player × season, 2021–2026 | `draft_year`, `draft_round`, `draft_number`, `birthdate`, `age`, `country`, `college`, height, weight |
| `data/injury_history/injury_history.csv` | 8,340 | 2021-01-07 .. 2026-07-29 | `date`, `team`, `player_acquired`, `player_relinquished`, `notes`, `category`, `source_page` |
| `data/reference/tip_times.csv` | 1,219 | 2022-05-21 .. 2026-07-29 | tip UTC/local, timezone (no 2021) |
| `data/derived/starters.csv` | — | — | realised starters (lagged use only) |

`player_bios.csv` has exactly 1,058 rows against exactly 1,058 observed player-seasons in
`master_player` — full coverage.

`injury_history.csv` is a Basketball-Reference transactions scrape (`source_page:
bbref_transactions_2021.html` and siblings) covering the **whole modelling span**, with categories
`missed_game_other` 3,131, `missed_game_injury` 2,242, `signing` 1,455, `waiver` 795, `draft` 260,
`trade` 252, `contract_suspension` 111, `front_office` 49, `retirement` 21, `waiver_claim` 18,
`contract_conversion` 6. Team abbreviations are clean (15 uniques) but Portland appears as `POR`
here and `PDX` in `team_cities.csv`; player fields are free-text names. **The packet's verdict
"injury / availability report — UNAVAILABLE HISTORICALLY" was reached against
`data/injury_capture/injury_log.csv` (6 days) and did not consider this file.** Also,
`team_cities.csv` contradicts the packet's "venue table — ABSENT": coordinates, elevation and
timezone are present for all 15 franchises. Travel is not my lane; I flag it and stop.

---

## 2. Category A — immediately testable

Inputs are historically present, complete enough, reproducible, and *arguably* cutoff-valid with the
named check performed. **The leakage line for this whole category:** roster continuity computed from
**participation in games strictly earlier than the target game** is on the safe side of the line —
it is the same construction the incumbent already uses for pace. Any use of **who appears, starts,
or logs minutes in the target game** — `master_player` rows for the target `game_id`,
`possessions_raw_v2` lineup columns for the target `game_id`, `master_team` box columns for the
target game — is on the leakage side. The **target game's `A_primary` candidate set** is a boundary
case treated explicitly in A5.

---

### A1 — replace the cumulative all-history league prior with a recent league prior

- **Source lens.** Cold start: the level-3 anchor.
- **Mechanism.** Level 3 averages every game on every strictly earlier date. For a 2026 expansion
  team that is ~1,290 games spanning six seasons (F3). If league pace has any secular drift, an
  expansion team entering in 2026 is anchored to a 2021–2026 blend rather than to the league it
  actually enters. Replace with a trailing-L league-game mean, or the prior-season league mean.
- **Expected direction.** Level-3 |bias| falls and level-3 MAE falls. **The sign of the estimate's
  movement equals the sign of (recent league mean − cumulative league mean), which I did not
  compute.** The packet's level-3 bias is −0.296 (mild under-projection), so if recent league pace
  exceeds the six-season mean, the correction moves estimates up and reduces that bias; if not, the
  arm should be abandoned rather than re-signed post hoc.
- **Affected stratum.** `pace_source == league_prior_all`, n = 37 (9 genuine expansion, 28
  left-censored 2021), plus the 15 opponent team-games that share those games through the symmetric
  mean (8 with own level 1, 7 with own level 2 — F5).
- **Cutoff-valid inputs.** Realised `game_pace` on strictly earlier dates. **Exists** — it is the
  incumbent's own input.
- **Overlap risk.** **HIGH.** The packet explicitly points at the cumulative league prior; every
  parallel source is being pointed at it too.
- **Leakage risk.** None. Same lag construction as the incumbent.
- **Expected information gain.** **LOW in aggregate** — 37 / 2,982 rows = 1.2%. But it is the only
  mechanism serving expansion franchises, and expansion is accelerating (0 in 2021–24, 1 in 2025, 2
  in 2026).
- **Complexity.** Trivial.
- **Falsifier.** Level-3 MAE does not fall, or level-3 sd rises, or the improvement is confined to
  the 28 left-censored 2021 rows and absent on the 9 expansion rows (see A2).
- **Changes.** Possession total, on a narrow stratum.
- **Honesty.** I expect this **not to move the headline MAE measurably**. I include it because it is
  the correct fix for the correct reason and because A2/A3 cannot be read without it.

### A2 — split level 3 into "franchise-cold" and "dataset-cold"

- **Source lens.** What "no history" means. There are two different absences.
- **Mechanism.** 28 of 37 level-3 rows are established franchises whose pre-2021 history the
  repository does not hold; 9 are franchises that have no history in the world (F1). A team that
  played in 2020 and a team that has never played are not the same estimation problem, and pooling
  them makes the stratum's diagnostics uninterpretable.
- **Expected direction.** **No projection changes.** The reported level-3 stratum should split into
  two sub-strata with visibly different error behaviour; I expect the expansion sub-stratum to be
  the worse of the two, because a genuine expansion roster has no continuity with anything.
- **Affected stratum.** Level 3 (n = 37) and level 4 (n = 8).
- **Cutoff-valid inputs.** `team_cities.csv:first_season` per `team_id`; `season`. **Exists** (F7).
  Franchise first season is fixed long before tip.
- **Overlap risk.** LOW–MEDIUM.
- **Leakage risk.** None.
- **Expected information gain.** Zero for accuracy; **high for validity of every other level-3 arm.**
- **Complexity.** Trivial.
- **Falsifier.** The two sub-strata are statistically indistinguishable.
- **Changes.** Subgroup allocation / diagnostics only.
- **Honesty.** At n = 9 versus n = 28 this **almost certainly cannot reach significance**. I include
  it anyway because it is a correctness precondition: an unstratified level-3 "improvement" would be
  validated four-fifths on a population that cannot recur.

### A3 — expansion-franchise anchor: delay the jump off the league prior

- **Source lens.** The cliff at `MIN_HISTORY_M = 3` applied to the least stable team identity.
- **Mechanism.** At game 4 an expansion franchise jumps from a ~1,290-game league anchor to a pure
  3-game own-window. That is the largest single information cliff in the ladder and it is applied to
  the team whose 3 games are least representative. Replace with a support-weighted blend
  `w_own = n_own / (n_own + k)` for teams in `season == first_season`, keeping a recent-league
  anchor (A1) as the shrinkage target well past game 3.
- **Expected direction.** Variance (sd) falls on expansion team-games 4–13. Bias direction is
  **not** claimed — it depends on whether an expansion team's first games run fast or slow, which I
  did not measure.
- **Affected stratum.** Expansion team-games in games 4–13: GSV 2025, PDX 2026, TOR 2026 ≈ 30
  team-games, plus their opponents via the symmetric mean.
- **Cutoff-valid inputs.** `first_season` (F7), team game index (schedule), own lagged `game_pace`.
  **All exist.**
- **Overlap risk.** **MEDIUM.** A generic shrinkage arm will come from a window/weighting lane; the
  *expansion conditioning* is mine.
- **Leakage risk.** None.
- **Expected information gain.** LOW now (~30 rows), **structurally high forward**.
- **Complexity.** Low.
- **Falsifier.** The expansion sub-stratum's MAE does not fall; **or** generic support-weighted
  shrinkage (A4) helps identically without the expansion conditioning — in which case A3 collapses
  into A4 and should be withdrawn rather than kept as a separate arm.
- **Changes.** Possession total.
- **Honesty.** **This cannot be validated to significance on this span.** It is a
  structural-correctness arm whose value is prospective.

### A4 — blend prior-season with same-season instead of the hard `MIN_HISTORY_M = 3` switch

- **Source lens.** The season boundary as a discontinuity in the estimator rather than in the team.
- **Mechanism.** The ladder discards the prior-season signal the instant three same-season games
  exist, then trusts those three games completely. The packet's own strata show exactly this
  signature: `team_window_prior_season` bias **−2.845** (under-projection) and `game_no_in_season`
  1–3 bias **−2.175**, then 4–6 bias **+1.115** and 7–10 bias **+1.142** (over-projection). Replace
  the switch with a precision-weighted blend `w_same = n_same / (n_same + k)`, `w_prior = 1 − w_same`.
- **Expected direction.** **Well determined by the packet alone, no extra measurement needed.** The
  prior-season estimate sits *below* realised and the early same-season estimate sits *above* it, so
  blending pulls games 4–10 **down**, reducing the +1.1 over-projection. Games 1–3 have no
  same-season history to blend with and are **unchanged** by this arm alone — that is a limitation,
  not an oversight, and it is why A5/A6 exist.
- **Affected stratum.** `game_no_in_season` 4–6 (n = 228) and 7–10 (n = 304); the 183 level-2 rows;
  support buckets 3–4 (n = 156) and 5–9 (n = 390).
- **Cutoff-valid inputs.** Own lagged `game_pace` in both the current and prior season. **Exists** —
  the incumbent already computes both lists (`same` and `prev` in `build_pace`) and simply discards
  one.
- **Overlap risk.** **HIGH.** This is the most obvious idea in the packet.
- **Leakage risk.** None.
- **Expected information gain.** **The highest of any arm I propose**, ~530 rows in the target
  strata with |bias| above 1.1.
- **Complexity.** Low.
- **Falsifier.** No reduction in |bias| or MAE on `game_no_in_season` 4–10; or the reduction is
  offset by degradation in the 11–20 stratum (which currently has the *best* MAE, 2.609, and is the
  thing most at risk from a poorly-chosen `k`).
- **Changes.** Possession total **and** calibration.

### A5 — make the season-boundary blend weight depend on roster continuity

**This is the centre of my mandate.**

- **Source lens.** "Team" is not a stable object across a season boundary. A franchise returning 85%
  of last season's minutes is materially the same team; one returning 35% is not. A4 blends
  prior-season history at a *constant* rate; the rate should be the degree to which the prior-season
  team still exists.
- **Mechanism.** Define continuity from participation in strictly earlier games only, e.g. the
  minutes-weighted overlap between (a) the players who logged minutes for team T in season S−1 and
  (b) the players who have logged minutes for team T in season S in games strictly before the target
  date. Set `w_prior` in A4 proportional to continuity. Low continuity → prior season is
  uninformative → shrink toward the recent league prior (A1) instead.
- **Expected direction.** Reduces **sd** in the `game_no_in_season` 2–10 strata. I **do not claim a
  bias sign**: it depends on whether high-turnover teams systematically play faster or slower than
  their predecessors, which I did not measure and cannot infer from the packet.
- **Affected stratum.** `game_no_in_season` 1–3 (n = 228, minus the 76 openers where it is
  undefined) and 4–10 (n = 532); level-2 rows (n = 183).
- **Cutoff-valid inputs.** `master_player` (`game_id`, `team_id`, `player_id`, `minutes`) restricted
  to games strictly earlier than the target date. **Exists**, 33,712 rows, full span (F9).
  Optionally `possessions_raw_v2` `off_p1..off_p5` for a possession-weighted rather than
  minutes-weighted basis; **exists**, `lineup_valid_ten` ≥ 99.41% every season.
- **Leakage risk — stated exactly.**
  - **SAFE:** both sides of the overlap are realised outcomes of *strictly earlier* games. This is
    the identical lag construction the incumbent already relies on for pace, and `master_player`'s
    single-scrape `observed_time` (F9) does not compromise that, because the games are already
    played.
  - **LEAKAGE:** any use of the target game's participants, starters, minutes or lineups. Concretely
    forbidden: `master_player` rows where `game_id == target`, `possessions_raw_v2` rows where
    `game_id == target`, `data/derived/starters.csv` for the target game, and every
    `master_team.parquet` box column for the target game.
  - **BOUNDARY CASE — the target game's `A_primary` candidate set.** Using it would be far more
    powerful (it names who is *expected* to play, not who played last time). It is *claimed*
    cutoff-available, and I verified 0 timestamp violations against `forecast_cutoff` across all
    35,629 rows (F10). But (i) that is a receipt declaration, and the standing PROGRAM_STATE gap is
    precisely that such declarations are asserted rather than verified; (ii) 71% of those rows bind
    only at day granularity with `exact_cutoff_ok = False`. **Verdict: Category A only if a
    provenance audit of the S1 candidate builder is performed first.** The strictly-safe variant
    uses prior-game participation only and needs no audit. Run the safe variant as the arm and the
    candidate-set variant as a labelled sensitivity.
- **FATAL COVERAGE FACT — state this before anyone builds it.** The safe variant is **undefined at
  `team_game_index == 0`**: there is no same-season participation yet. And the candidate-set variant
  is **also undefined there**, because all 76 openers carry **zero `A_primary` rows** (F4). **Roster
  continuity is unavailable at exactly the game where it matters most.** From game 2 onward it is
  defined and gains support as the season progresses — which is the region where the packet shows
  the largest opposite-signed biases, so the arm is still worth running. But it does not solve the
  opener, and no Category A construction in this repository does.
- **Overlap risk.** **LOW.** No other lane holds this mandate.
- **Expected information gain.** MEDIUM, with a serious caveat below.
- **Complexity.** **MEDIUM.** Requires an as-of, minutes-weighted player-set per team per date, held
  strictly lagged, with a deliberate decision about whether DNP rows (`minutes` null, 16.0%) count
  as roster membership. They should not count as *participation*; whether they count as *presence*
  is a real modelling choice that must be declared, not discovered.
- **Falsifier.** Interacting `w_prior` with continuity produces no MAE reduction over A4's
  continuity-blind blend; **or** continuity has too little cross-team variance to carry any signal.
- **Honesty — my largest doubt about my own lane.** F8 says WNBA rosters are 12 deep, teams use 14–16
  distinct players a season, and only 11–27 players league-wide change teams mid-season. **Continuity
  may simply not vary enough to matter.** If the continuity distribution turns out to be tightly
  concentrated near its upper bound, this arm is dead and should be declared dead rather than
  rescued by re-parameterisation.
- **Changes.** Possession total **and** calibration; substantial subgroup reallocation early-season.

### A6 — roster newness from player bios, as a continuity substitute

- **Source lens.** Because participation-based continuity is undefined at game 1, look for a
  continuity-like quantity whose *input* is knowable before a ball is thrown.
- **Mechanism.** Rookie share and low-experience share of the roster: `draft_year == season`, or
  `season − draft_year ≤ 1`. A rookie-heavy roster is different from its prior-season self in a way
  the prior-season window structurally cannot see.
- **Expected direction.** Higher rookie share → prior-season pace is less predictive → the A4/A5
  blend should shrink harder toward the recent league prior. **I do not claim a direction for pace
  level itself** — I have no basis for asserting that young rosters play faster or slower.
- **Affected stratum.** Early-season strata, and level-2 rows.
- **Cutoff-valid inputs.** `data/reference/player_bios.csv`, 1,058 rows keyed player × season, full
  coverage of the 1,058 observed player-seasons (F12). `draft_year`, `draft_round`, `draft_number`,
  `birthdate` are fixed facts predating the season, so the **bios are unambiguously cutoff-valid**.
- **Leakage risk.** The bios are clean; **the roster basis is the risk**. Taking the share over the
  target game's realised participants is leakage. Over the team's prior-game participants is safe
  but undefined at game 1. Over the `A_primary` candidate set inherits A5's boundary case — and at
  the opener is impossible anyway (zero `A_primary` rows). The only roster basis that exists at an
  opener is the B-tier S2 prior-season-affiliation set, which the receipt itself rates operationally
  implausible (max 70 allocated players, max effective rotation 67.8, at p05 only one player clears
  10 projected minutes), or the retrospective S_TX set, which is not cutoff-available.
- **Verdict.** **Category A from game 2 onward. The season-opener version is Category B (see B1).**
- **Overlap risk.** LOW.
- **Complexity.** MEDIUM — a player-season join plus a declared roster basis.
- **Falsifier.** Rookie/experience share adds nothing over the raw support count `n_same`.
- **Changes.** Possession total via the blend weight; calibration.
- **Honesty.** I expect this to be **marginal**. I include it because bios are the only
  continuity-adjacent input that is *complete at the season opener*, so if B1 ever lands, A6 is the
  ready-made carrier.

### A7 — window staleness in calendar time, and the league-wide break

- **Source lens.** International windows. "Stale history" is distinct from "rested players".
- **Mechanism.** The window is 10 *games*, unweighted, with no notion of elapsed time. After a 29–35
  day league-wide break the window is over a month old and describes a roster whose senior
  internationals have been away, returning at different fitness and occasionally not returning. Add
  a staleness term: calendar days spanned by the window, or days since the team last played,
  **conditioned on whether the gap was league-wide or team-specific**.
- **Expected direction.** **Determined by the packet:** `days_rest` `7+` has bias **−1.435** — the
  largest-|bias|, highest-sd (4.307) rest bucket, i.e. post-layoff games realise *higher* pace than
  the stale window implies. A staleness correction should shift those estimates **up** and reduce
  |bias| on that stratum.
- **Affected stratum.** `days_rest 7+` (n = 162); within it, the 24 team-games at ≥ 14 days, all
  Olympic-break (F6); ≥ 7 days on 103 team-games.
- **Cutoff-valid inputs.** `game_date` and the team's prior `game_date`; league-wide idleness from
  the published schedule. **Exists**, 2,990/2,990, schedule-derived.
- **Overlap risk.** **HIGH.** `days_rest` is already a packet stratum and a schedule/fatigue lane
  will own it. My separable contribution is threefold: the mechanism is *window staleness*, not
  player rest; a **league-wide** break is categorically different from an idiosyncratic team gap;
  and the league-wide instances in this span are specifically international-tournament windows.
- **Leakage risk.** None.
- **Expected information gain.** LOW.
- **Complexity.** Trivial.
- **Falsifier.** After controlling for plain `days_rest`, a league-wide-break indicator adds nothing.
- **Changes.** Possession total on a narrow stratum.
- **Honesty.** At n = 24 for the ≥ 14-day events (12 in 2021, 12 in 2024) **this will very likely
  fail the significance bar**. I include it because the input is free, the mechanism is real and
  directionally pinned by the packet, and 2028 is an Olympic year — the stratum recurs on a known
  schedule.

### A8 — opponent evidence quality: precision-weight the two sides instead of averaging them

- **Source lens.** Cold start propagates through the symmetric mean. A cold-start team degrades its
  *opponent's* projection too, and the packet's stratification hides it.
- **Mechanism.** `projected_team_off_possessions` is the unweighted mean of the two sides'
  estimates, so a well-supported team playing an expansion franchise in that franchise's second game
  is handed a projection half-built from a six-season league average. Two moves: (a) report the
  joint (own_level, opp_level) stratification of F5; (b) replace the unweighted mean with a
  precision-weighted mean using each side's *own team* support.
- **Expected direction.** MAE falls on the 30 own-level-1/opp-fallback rows because the low-support
  side is down-weighted. The 22 own-level-2/opp-level-1 rows will get *worse* on the same logic,
  which is correct — their current numbers are flattered by borrowing a good opponent. Net direction
  on the headline is **not** claimed.
- **Affected stratum.** 30 + 22 + 15 = 67 team-games in the off-diagonal cells of F5, plus the
  reallocation of the 2,762-row level-1 stratum's reported error.
- **Cutoff-valid inputs.** `pace_level` and `n_history_games` per side — **already in the frozen
  artifact**; opponent identity from `master_team.opp_team_id` — **exists**, verified 0 join nulls
  against all 2,990 team-games; all schedule-determined and cutoff-valid per the packet.
- **Overlap risk.** **MEDIUM.** An opponent-interaction lane will propose opponent *pace tendency*.
  Mine is opponent *evidence quality* — a different object, and the two compose rather than compete.
- **Leakage risk.** None.
- **Expected information gain.** MEDIUM relative to cost. **This is the highest expected-value item
  in my Category A**: cheap, exactly targeted, and currently invisible in the diagnostics.
- **Complexity.** Low.
- **Falsifier.** Precision weighting does not reduce MAE on the (1, >1) cells, or it degrades the
  (1,1) cell that holds 2,732 of 2,990 team-games. The second is the real risk and must be the
  gating check — a 67-row gain that costs anything on 2,732 rows is a loss.
- **Changes.** Possession total **and** subgroup allocation.

### A9 — correct the support axis before selecting anything against it

- **Source lens.** Low-support diagnostics that are not measuring support.
- **Mechanism.** F2: `n_history_games` means *team* games at levels 1–2 and *cumulative league*
  games at level 3. Emit `n_team_history_games` (own count; 0 at levels 3 and 4) alongside, and
  re-derive the support strata against it.
- **Expected direction.** **No projection changes.** The `">10"` bucket (n = 23, MAE 4.538, sd
  5.504) should disappear and its rows should reappear at team support 0, where they belong. I
  expect the corrected support curve to be monotone in a way the current one is not.
- **Affected stratum.** All four support buckets.
- **Cutoff-valid inputs.** Already in the artifact.
- **Overlap risk.** LOW. This is a diagnostic-integrity finding, not a modelling idea.
- **Leakage risk.** None.
- **Expected information gain.** Zero for accuracy; **prerequisite for the validity of any
  support-conditioned arm**, including A3, A4 and A8.
- **Complexity.** Trivial.
- **Falsifier.** Not applicable — I verified the mixed semantics directly (F2). What is falsifiable
  is only the claim that the corrected curve is better behaved.
- **Changes.** Subgroup allocation / diagnostics only.

### A10 — separate the dataset's left-censored cold start from the real one in the evaluation design

- **Source lens.** F1, applied to evaluation rather than to the estimator.
- **Mechanism.** 36 team-games (28 level-3 + 8 level-4) exist only because the repository starts in
  2021. They are not evidence about cold starts; they are evidence about the archive. Report them as
  a named excluded-or-separate population and evaluate cold-start arms against the 9 expansion rows.
- **Expected direction.** No projection changes; the reported cold-start error profile changes
  materially because 80% of its rows are removed.
- **Affected stratum.** Levels 3 and 4.
- **Cutoff-valid inputs.** `first_season` (F7), season, date. **Exists.**
- **Overlap risk.** LOW.
- **Leakage risk.** None.
- **Expected information gain.** Zero for accuracy; **high for not fooling ourselves**.
- **Complexity.** Trivial.
- **Falsifier.** Not applicable — this is a design assertion, not an empirical claim. The empirical
  claim riding on it (that the two populations behave differently) is likely unprovable at n = 9.
- **Changes.** Subgroup allocation only.

### A11 — in-season roster discontinuity detected from lagged participation

- **Source lens.** Mid-season trades and departures.
- **Mechanism.** A player who logged material minutes for team T across T's recent window stops
  appearing in T's most recent games, or begins appearing for another team. Detected purely from
  strictly earlier games. When such a departure is detected, the trailing window overstates roster
  continuity and the estimate should be shrunk toward the recent league prior.
- **Expected direction.** Reduces error on affected team-games. **No bias sign claimed** — a
  departure could raise or lower pace depending on who left.
- **Affected stratum.** Team-games following a detected departure — F8 puts this at roughly 1–2
  events per team-season (11–27 movers league-wide per season).
- **Cutoff-valid inputs.** `master_player` lagged. **Exists.**
- **Overlap risk.** LOW.
- **Leakage risk.** None in the detection itself — **but two confounds must be declared.** (i) A
  "stopped appearing" signal is **indistinguishable from an injury absence** without a transaction
  feed (see B2). (ii) The detection is **lagged by construction**: the flag can only fire after the
  team has already played games without the player, by which time the trailing window has already
  partly absorbed the change. So the feature fires late, precisely when it is least needed.
- **Expected information gain.** **LOW.**
- **Complexity.** Low, once A5's machinery exists.
- **Falsifier.** No MAE reduction on the affected rows.
- **Changes.** Possession total, very narrow stratum.
- **Honesty.** **I expect this to fail on sample size and on detection lag.** I include it because it
  is the only in-season expression of the continuity mechanism available without new data, its
  marginal cost after A5 is near zero, and its failure would be informative: it would localise the
  continuity story to the season boundary rather than to roster change in general.

### A12 — resolve level 4 with a declared constant, and be explicit that this is coverage, not accuracy

- **Source lens.** Obligation completeness at the extreme cold start.
- **Mechanism.** 8 team-games (4 games, all 2021-05-14) are unresolved because there is no earlier
  game at all, so the league prior is undefined. The only possible resolution is an exogenous
  declared constant.
- **Expected direction.** Coverage goes from 2,982/2,990 to 2,990/2,990. **Headline MAE will very
  likely get worse**, because 8 previously-excluded and maximally-hard rows enter the denominator.
- **Affected stratum.** Level 4, n = 8.
- **Cutoff-valid inputs.** A declared constant. Trivially cutoff-valid; **but it cannot be learned
  from this span without using the span's own realised pace**, which would make it a fitted quantity
  and is therefore out of bounds for this lane.
- **Overlap risk.** LOW.
- **Leakage risk.** **Real and easy to miss** — any constant chosen by looking at realised pace over
  the modelling span is retrospective. It must come from outside the span or be declared a priori.
- **Expected information gain.** **Zero for accuracy.**
- **Complexity.** Trivial.
- **Falsifier.** Not applicable.
- **Changes.** Coverage only; mechanically degrades the possession-total metric.
- **Honesty — I expect this to look like a regression, and I am including it deliberately.** In this
  program "coverage" means obligation completeness, and an unresolved obligation is a real
  operational failure that an MAE computed on resolved rows conceals. Note also that in live
  production this branch would **never bind** — there is always prior league history — so its entire
  value is bookkeeping honesty on the historical span.

### A13 — bottom-up: roster-weighted pace from player on-court history

- **Source lens.** The strongest form of the mandate. If the team changes, do not shrink the team's
  number — **rebuild it from the players**.
- **Mechanism.** Compute each player's on-court pace tendency from strictly earlier games using
  `possessions_raw_v2` lineup columns, then project team pace as a weighted mean over the players
  expected to play. This is the only construction that transfers cleanly across a roster
  discontinuity: a team returning 40% of last year's minutes gets a projection assembled from the
  players who are actually there, with no dependence on the franchise's own trailing window.
- **Expected direction.** Variance falls broadly, **most** in the low-support and post-roster-change
  strata. Bias direction not claimed.
- **Affected stratum.** All strata; disproportionately support 3–4 (n = 156), 5–9 (n = 390),
  `game_no_in_season` 1–10 (n = 760), and level 2 (n = 183).
- **Cutoff-valid inputs.** `possessions_raw_v2` `off_p1..off_p5` / `def_p1..def_p5` over strictly
  earlier games — **exists**, `lineup_valid_ten` ≥ 99.41% per season. Weights from
  `projected_player_possessions_v1.projected_minutes` — **exists**, 2,914 team-games under
  `tier_a_only`.
- **Leakage risk.** The tendencies are lagged and safe. **The weights are the exposure.** Two
  distinct points:
  - **No circularity** — I verified in `build_projected_exposure.py` that `allocate()` consumes only
    `raw_expected_minutes` and that pace enters afterwards purely as a multiplier
    (`off = projected_team_off_possessions * (minutes / 40)`). The projected minutes therefore do
    **not** depend on the pace estimate, so using them to build a new pace estimate is not circular
    (F11).
  - **But** the weights derive from the `A_primary` candidate set and inherit both its cutoff caveat
    (A5's boundary case, F10) and its coverage gap: **zero coverage at all 76 season openers** (F4).
    A minutes-weighted bottom-up estimator is therefore structurally incapable of producing an
    opener projection. That is not a bug to be patched; it is the same wall as A5.
- **Overlap risk.** **MEDIUM–HIGH.** A player-level or bottom-up lane may propose the same estimator
  from a different motive. My contribution is the roster-transition justification and the leakage /
  circularity / coverage analysis attached to the weights.
- **Expected information gain.** **Potentially the highest of anything in this document**, and also
  the highest-variance bet.
- **Complexity.** **HIGH.** Per-player lagged on-court pace with sane shrinkage for thin players, a
  weighting scheme, and a documented fallback for every team-game where the candidate set is absent.
- **Falsifier.** Bottom-up player-weighted pace fails to beat the team trailing window on the full
  support stratum (n = 2,413); **or**, more decisively for my lane, it fails to beat it specifically
  on the low-support strata, which is the only reason to prefer it.
- **Changes.** Possession total **and** calibration, everywhere.

---

## 3. Category B — high value, not currently available

None of these may enter TEAM_POSSESSION_PRIOR_V2 as arms. They are a data and capability roadmap.

### B1 — point-in-time pregame roster / active list, especially at the season opener

- **Missing input.** A captured, timestamped roster or active list observable before tip.
- **Why it may matter.** F4: all 76 season openers have **zero `A_primary` candidate rows**, and
  those same team-games sit on the weakest pace tiers (61 prior-season, 7 league-prior, 8
  unresolved). This is the single largest hole in my lane: the continuity signal is undefined
  exactly where the pace prior is worst. Every Category A continuity idea (A5, A6, A13) hits this
  wall.
- **Minimum viable collection.** Capture published opening-night rosters and daily active lists
  going forward. The existing S2 prior-season-affiliation set already fills the *slot* at openers but
  the receipt rates it operationally implausible on its own numbers (max 70 allocated players, max
  effective rotation 67.8, at p05 only one player clears 10 projected minutes), so it is not a
  substitute. A partial retrospective reconstruction is possible from B2's `signing` / `waiver` /
  `draft` / `trade` rows.
- **Prospective-only validation required.** **Yes** for the captured feed. A retrospective
  reconstruction could be evaluated on history but only as a clearly-labelled non-production
  sensitivity, in the same tier as the existing `B_transaction_sensitivity`.
- **Expected value of closing the gap.** **HIGH.** It converts A5/A6/A13 from "works from game 2"
  into "works from game 1", on 76 team-games per six seasons plus the opponents that share those
  games — and openers are 2.5% of the universe concentrated in the worst strata.

### B2 — transaction feed with a captured publication time

*(The file exists; the timestamp does not. This is my most consequential Category B item and a
correction to the packet's availability table.)*

- **Missing input.** Not the transactions — an **observation or publication timestamp** for them.
- **What exists.** `data/injury_history/injury_history.csv`: 8,340 rows, **2021-01-07 .. 2026-07-29**
  — the whole modelling span — scraped from Basketball-Reference transaction pages. Categories:
  `trade` 252, `signing` 1,455, `waiver` 795, `draft` 260, `retirement` 21, `contract_suspension`
  111, `waiver_claim` 18, `contract_conversion` 6, `front_office` 49, plus `missed_game_injury`
  2,242 and `missed_game_other` 3,131. Team abbreviations are clean (15 uniques).
- **Why it may matter.** This is the **only source in the repository that dates roster change across
  the entire span**. It would let A5 and A11 fire at the season opener, detect a trade before the
  participation record reveals it, and separate "player departed" from "player injured" — which is
  the confound that I expect to kill A11 on its own.
- **Why it is Category B and not Category A.** There is **no `observed_time` or published-time column
  anywhere in the file** — only an effective `date` and a `source_page`. This is the identical
  objection the construction receipt raises against the S_TX transaction source, which it found was
  observed at 2026-07-30T17:42Z with `candidate_published_time` null, i.e. *after every one of its
  cutoffs*, and therefore not available at the historical decision time regardless of its backdated
  effective date. **A backdated effective date is not evidence of contemporaneous availability**, and
  Basketball-Reference backfills and corrects. Separately, the `missed_game_*` categories (5,373 of
  8,340 rows, 64%) are per-game absence annotations derived after the fact; for the target game they
  are a direct outcome and must never be joined on the target `game_id`.
- **Minimum viable collection.** (i) An entity-resolution layer from free-text player names and team
  abbreviations to `player_id` / `team_id` — note `POR` here versus `PDX` in `team_cities.csv`.
  (ii) Either a forward point-in-time capture of the same source, or an archival provenance audit
  (dated web-archive snapshots) establishing that a row's content was on the page before the relevant
  cutoff. (iii) A hard split of the transaction categories from the `missed_game_*` categories, which
  have completely different leakage properties and must not share a code path.
- **Prospective-only validation required.** **Yes for the strict cutoff claim.** A retrospective
  sensitivity arm, explicitly labelled non-production in the manner of the existing tier-B regimes,
  could be run today and would at least establish an upper bound on how much the signal is worth
  before anyone pays for the capture.
- **Expected value of closing the gap.** **HIGH.** It is the difference between a continuity feature
  that starts at game 2 and one that starts at game 1, and it is the only route to disambiguating
  departure from injury.

### B3 — senior national-team / international-window participation by player

- **Missing input.** Which players were away at FIBA or Olympic duty, and when they returned.
- **Why it may matter.** The 29–35 day breaks (F6) are the one moment when a roster's effective
  composition changes with **no transaction at all** — players leave and return without ever
  appearing in a transaction log or a participation gap that means what it looks like. Returning
  players carry accumulated load. This is the cleanest instance of "the team that takes the floor is
  not the team in the window", and it is currently completely invisible to the model.
- **Minimum viable collection.** A hand-maintained roster-by-tournament table: ~15 teams × ~2 events
  per cycle × ~30 players. Genuinely small, and historically documentable.
- **Prospective-only validation required.** **No.** This is public historical record.
- **Expected value of closing the gap.** **MEDIUM.** Only 24 team-games at ≥ 14-day gaps in this
  span, so it will not validate here — but the event recurs on a fixed international calendar and
  2028 is an Olympic year.

### B4 — coaching identity and coaching change

- **Missing input.** Coach by team-season, plus in-season change dates. The packet already records
  this as ABSENT and a `*coach*` sweep over `data/` returns nothing; I re-list it because it belongs
  to my lane for a reason the packet does not give.
- **Why it may matter.** A coaching change at a **season boundary** is the exact event that makes the
  prior-season pace estimate uninformative about the current team — which is the mechanism A5 is
  trying to reach indirectly, and badly, through a roster proxy. If pace is more coach-determined
  than roster-determined (which I consider likely), then A5 is a weak instrument for the thing that
  actually matters, and its likely failure would be *mis-attributed to roster continuity not
  mattering* when the real explanation is that I measured the wrong discontinuity.
- **Minimum viable collection.** A ~90-row coach-by-team-season table (15 franchises × 6 seasons)
  plus mid-season change dates.
- **Prospective-only validation required.** **No.** Fully documentable retrospectively, and unlike a
  roster feed there is no plausible cutoff dispute: a coach's identity on a given date is public and
  stable.
- **Expected value of closing the gap.** **HIGH**, and cheap. If I could nominate one Category B item
  to be collected first, it would be this one, ahead of B2 — smaller, no entity resolution, no
  provenance audit, and it directly tests whether my lane's central premise is even the right premise.

### B5 — preseason and training-camp observations for expansion franchises

- **Missing input.** Any in-domain competitive observation of an expansion team before its first
  regular-season game.
- **Why it may matter.** An expansion franchise at games 1–3 has literally zero competitive history,
  which is why it falls to a six-season league average (F3). Preseason games are the only in-domain
  evidence that exists at that moment.
- **Minimum viable collection.** Capture preseason box scores, which are published. GSV 2025 and the
  2026 pair may still be obtainable retrospectively.
- **Prospective-only validation required.** **No** for future expansion; historically it depends on
  what is still retrievable.
- **Expected value of closing the gap.** **MEDIUM–LOW now** (9 rows), rising with each expansion
  cohort. Caveat: preseason pace is played under different rotation and effort conditions and may be
  a biased estimator of regular-season pace — which would itself have to be established, and cannot
  be established from 9 rows.

---

## 4. Overlap declaration

Ideas I expect other sources to raise independently, so the coordinator can de-duplicate rather than
double-count: **A1** (the packet points directly at the cumulative league prior), **A4** (shrinkage /
window weighting is the most obvious response to the bias-variance reading), **A7** (`days_rest` is
already a packet stratum), and **A13** in its generic bottom-up form. Ideas I believe are distinctive
to this lane: **A2**, **A5**, **A8** (opponent *evidence quality*, not opponent pace tendency),
**A9**, **A10**, and the F12 source corrections.

## 5. Hypotheses I expect to fail, and why I included them anyway

| # | Why I expect failure | Why it is still here |
|---|---|---|
| A1 | 37 of 2,982 rows; cannot move the headline | Only mechanism serving expansion; prerequisite for A2/A3 |
| A2 | n = 9 vs 28, underpowered | Correctness precondition — otherwise a level-3 fix is validated four-fifths on a non-recurring population |
| A3 | ~30 rows, cannot reach significance on this span | Structural correctness; expansion is scheduled to recur |
| A6 | Likely marginal over raw support count | The only continuity-adjacent input that is complete at a season opener; the carrier if B1 lands |
| A7 | n = 24 at ≥ 14 days, underpowered | Free input, direction pinned by the packet, recurs every Olympic cycle |
| A11 | Event rate ~1–2 per team-season; detection is lagged by construction; confounded with injury | Near-zero marginal cost after A5, and its failure would usefully localise the continuity story to the season boundary |
| A12 | Will mechanically **worsen** MAE | Coverage is obligation completeness here, and an MAE over resolved rows conceals 8 real operational failures |

## 6. Where I am uncertain

1. **My lane's central premise may be wrong.** F8 shows WNBA rosters are shallow and stable — 14–16
   distinct players per team-season, 11–27 in-season movers league-wide. Continuity may not vary
   enough to carry signal (A5), and pace may be far more coach-determined than roster-determined
   (B4). If A5 fails, **do not conclude that roster transition does not matter** until B4 is
   available; the correct reading may be that I measured the wrong discontinuity.
2. **I did not measure league pace drift**, so A1's *sign* is genuinely open. It must be established
   before the arm is run, and not re-signed afterwards to match whatever helped.
3. **Cutoff validity of the candidate set (A5/A6/A13) is asserted, not verified.** I verified 0
   timestamp violations across 35,629 rows, which is necessary but not sufficient; 71% bind only at
   day granularity. I have written the safe variants so the arms can proceed without resolving this,
   but the powerful variants cannot.
4. **`injury_history.csv` may be more or less usable than I judge.** I inspected its schema and
   category counts, not the fidelity of its dates. My verdict (Category B, needs a provenance audit)
   is a conservative default given the receipt's finding about the S_TX source; a real audit could
   move some categories — `draft` and `trade` most plausibly — into Category A.
5. **Nearly every stratum in my lane is small.** Level 3 is 37 rows, expansion is 9, level 4 is 8,
   Olympic-break layoffs are 24, opponent contamination is 30. **Almost nothing here can be
   established to significance on this span.** The honest framing for most of my Category A is
   structural correctness plus prospective value, not measurable near-term MAE gain. The exceptions
   are **A4** (~530 rows with |bias| > 1.1) and **A13** (all rows), which are the only two arms I
   propose that could plausibly move the headline.
