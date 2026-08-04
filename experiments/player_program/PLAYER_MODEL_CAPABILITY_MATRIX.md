# Player model — capability matrix

**Purpose.** Reconcile the expanded player-model plan against what this repository *already
contains*, so nothing is restarted from scratch and nothing is claimed as new when it exists.
Every row below was checked against the worktree, the two registries, and the data directories.
Where I did not verify something deeply, the row says so.

**Scope note.** This is an inventory. No model, event channel or experiment was started while
building it.

Generated at commit — see the commit that adds this file. Worktree `player-model-program`.

---

## The four distinctions this matrix must preserve

| axis | meaning | why it matters here |
|---|---|---|
| **Intrinsic vs operationally achievable** | signal measurable under *realised* conditions vs signal usable from a *pregame* decision point | P3 has intrinsic signal (stint MAE 2.147 vs 2.206) and **no demonstrated operational value** under v1 exposure |
| **Realised vs projected** | reconstructed from what happened vs forecast before the cutoff | `player_possessions/2` is realised and **cannot** be forecast exposure; `projected_player_possessions/1` is the projected counterpart |
| **Captured-as-of vs retrospective** | evidence observed before the cutoff vs reconstructed afterwards | Tier A is `captured_asof`; transaction Tier B was observed 2026-07-30, after every one of its cutoffs |
| **Discovery vs promotion-grade** | development-fold exploration vs registered, walk-forward, incumbent-compared evidence | most feature-screen work is discovery; only `chanreval_2026_structural_repaired` is a promoted team incumbent |

**States used:** `canonical` · `prototype` · `superseded` · `blocked` · `not started`.

---

## 1. Data and reconstruction layer

### raw play-by-play — `canonical`, with a **hard schema split**

| field | value |
|---|---|
| code | `collect_refresh.py`, `fetch_playoff_gamelogs.py`, `collect_misc_backfill.py` |
| artifact | `data/playbyplay/pbp_*.parquet` (996 games) **and** `data/refresh_2026/pbp/pbp_*.parquet` (499 games) |
| registration | none — data acquisition, not an experiment |
| validation | coverage verified here: **1,495 of 1,495 universe games, 100%**, the two stores disjoint (zero overlapping game ids) |
| reusable | both stores; full universe coverage 2021–2026 |
| **must not reuse** | the assumption that one schema covers the universe |
| next dependency | **an event-schema normalisation layer** |

**This is the single most important finding in the matrix.** The two stores share **zero column
names**:

- `data/playbyplay/` — legacy NBA `PlayByPlayV2`: `EVENTMSGTYPE`, `EVENTMSGACTIONTYPE`,
  `PLAYER1_ID`/`PLAYER2_ID`/`PLAYER3_ID`, `HOMEDESCRIPTION`, `PCTIMESTRING`. 996 games,
  2021 → mid-2025.
- `data/refresh_2026/pbp/` — modern NBA CDN format: `actionType`, `subType`, `personId`, `clock`,
  `shotDistance`, `shotResult`, `shotValue`, `isFieldGoal`, `xLegacy`/`yLegacy`, `location`.
  499 games, mid-2025 → 2026.

Every granular event channel (turnovers by mechanism, rebounds, blocks, assists, fouls) depends on
parsing this stream. **None of them can span the universe until the two formats are normalised into
one registered event contract.** The modern format is richer — it carries shot coordinates and
distance inline — so normalisation is not merely a rename.

### event parsing — `canonical` producer, with a `prototype` to audit only

| field | value |
|---|---|
| code | `build_possessions.py`, `derive_lineups.py` (canonical) · `scripts/02_processing/build_possession_based_features.py` (**prototype**) |
| artifact | `data/possessions/possessions.parquet`, `data/possessions/reconciliation.csv` |
| registration | possession artifact registered in the player registry as `player_possessions/2` |
| validation | `POSSESSION_INTEGRITY_RECEIPT_V2.json`, `V1_TO_V2_RECONCILIATION.json` |
| reusable | possession-boundary logic, on-court tracking, the clean-producer hash discipline |
| **must not reuse** | the prototype's **same-game opponent-efficiency normalisation** — it uses target-game outcomes to normalise that game's forecast. Also `data/player_possession_features.parquet` / `_debug.parquet`, its outputs. |
| next dependency | event-schema normalisation (above) before extending parsing to event channels |

The prototype attempted possession boundaries, on-court tracking, offensive possession attribution,
player on-court points and opponent normalisation. **Do not build a parallel replacement from it.**
`player_possessions/2` is canonical unless validation proves otherwise. Audit the old script only
for event-parsing edge cases.

### realised possessions — `canonical`

| field | value |
|---|---|
| code | `experiments/player_program/possession_artifact_v1.py`, `possession_artifact_v2.py` |
| artifact | `player_possessions/2` — `possessions_raw_v2.parquet`, digest `7200881f…` |
| registration | player registry, artifact id `player_possessions/2` |
| validation | 238,563 possessions across 1,495 games; 99.79% valid ten-player state; **503 possessions (0.21%) excluded** and explicitly labelled |
| reusable | the whole artifact — it is the realised backbone for P3, rate models and any event denominator |
| **must not reuse** | as *forecast* exposure. It is **realised**. This distinction is what the whole exposure bridge exists to enforce. |
| next dependency | none — it is complete for its purpose |

### lineups and stints — `canonical`

| field | value |
|---|---|
| code | `derive_lineups.py` |
| artifact | `data/derived/stints.parquet`, `starters.csv`, `lineup_validation.csv`, `failed_games.csv` |
| registration | consumed by `player_possessions/2`; no independent registration |
| validation | via the possession receipt; failed games enumerated |
| reusable | stint boundaries, starter flags, on-court five-man state |
| **must not reuse** | realised stint boundaries or durations as pregame features — they are oracle information |
| next dependency | a projected substitution-timing model, which does not exist |

---

## 2. Exposure layer — the completed bridge

### availability — `canonical` model, **information-limited history**

| field | value |
|---|---|
| code | `cbs_player_runner_v15.py`, `cbs_v15.py`; `injury_capture_daily.py`, `scrape_injury_history.py` |
| artifact | v15 `predictions__p_active__*.parquet`; `data/injury_capture/`, `data/injury_history/` |
| registration | `cbs_v15_player_oof_v5` (player registry); `minutes_twostage_availability_v1`, `oracle_availability_bracket_v1`/`v2` (team registry) |
| validation | 31/31 v14 control receipts; v15 prescore receipts |
| reusable | `p_active` predictions for all 44,851 obligations |
| **must not reuse** | any claim that historical availability is captured-as-of. **There is no genuine pregame injury/availability feed before 2026-07-30.** |
| next dependency | accumulate real captured feed; historical availability evaluation stays information-limited until then |

### conditional minutes — `canonical`

| field | value |
|---|---|
| code | `cbs_player_runner_v15.py`; `minutes_baselines.py`, `minutes_twostage.py` |
| artifact | v15 `predictions__e_minutes_given_active__*.parquet` |
| registration | `cbs_v15_player_oof_v5`; `minutes_ewma_vs_carryforward_v1` |
| validation | v15 component targets improve on v14 across all four (availability Brier −0.0041, conditional-minutes MAE −0.107, attempts −0.039, scoring −0.051), CIs excluding zero under date- and player-clustered inference |
| reusable | `e_minutes_given_active` |
| **must not reuse** | v15 as a promoted arm. **v15 is not promoted**: despite component gains, end-to-end expected minutes worsened (MAE +0.586, bias +1.83 min) |
| next dependency | the exposure bridge consumed it; the open question is exposure, not rate |

### projected exposure — `canonical` ✅ **the completed bridge**

| field | value |
|---|---|
| code | `experiments/player_program/build_projected_exposure.py` |
| artifact | `projected_player_possessions/1` — player, rotation and pace parquets in `projected_exposure_v1/` |
| registration | `projected_player_possessions_v1` + 4 errata/policies |
| validation | **35/35 checks pass** — exact 200-minute totals in integer micro-minutes, possession mass to 1e-13, runtime provenance of every file and column read, three perturbation tests, fail-closed gates |
| reusable | projected minutes and projected offensive/defensive possessions for 120,262 obligation×regime rows over all 1,495 games |
| **must not reuse** | as production. `production_eligible = False` on every regime. Do not treat equal offensive/defensive possessions as a measured player-level fact — it is a v1 projection assumption. |
| next dependency | none for research use; a substitution-timing model would be needed to separate off/def exposure |

Regime labelling — the four axes kept separate:

| regime | available at cutoff | captured as-of | operationally plausible | production-eligible |
|---|---|---|---|---|
| `tier_a_only` | yes | **yes** | yes, *at the median* | no |
| `tier_a_plus_tx_b` | **no** | no | no | no |
| `tier_a_plus_tx_b_plus_s2` | yes | no | **no** | no |

Known limitation kept visible: Tier A's median effective rotation size is 8.97, but its **maximum is
14.21**, exceeding the 12-player standard active roster, and 994 of 2,914 allocated team-games name
more candidates than that roster allows.

### pace — `canonical`

| field | value |
|---|---|
| code | `build_projected_exposure.py::build_pace` |
| artifact | `team_possession_prior/1` |
| registration | `team_possession_prior_v1`, registered before execution |
| validation | independently re-derived to 1e-12; level support 2,762 / 183 / 37 / 8 closes arithmetically |
| reusable | prior-games-only projected team offensive possessions for 2,982 of 2,990 team-games |
| **must not reuse** | `features/common.py::pace_sew` as a cutoff-valid pace artifact — it is a team-model feature column with no season-opening fallback, no overtime normalisation, Regular-Season-only, ordered by game index rather than cutoff |
| next dependency | none; reuse it for any downstream possession need |

---

## 3. Event channels — all `not started`, all behind one blocker

**None of the six granular channels below has any code, artifact or registration.** All are
derivable in principle from the play-by-play stream, and all are blocked on the same dependency:
**the event-schema normalisation layer**, plus a registered opportunity-denominator contract per
channel.

The legacy store encodes events in `EVENTMSGTYPE` / `EVENTMSGACTIONTYPE` with `PLAYER1/2/3`
attribution; the modern store uses `actionType` / `subType` / `personId`. Both carry enough to
separate mechanisms — but only after normalisation.

| capability | state | derivable from | opportunity denominator needed | notes |
|---|---|---|---|---|
| **shot attempts and scoring** | `prototype` | v15 `attempts_usage` and `player_scoring_distribution` targets **exist and are predicted**; `data/shotcharts/shots_*.parquet` covers ~1,485 of 1,495 games with locations | attempts by shot type/location; makes conditional on attempts | the only channel with existing predictions. `build_zone_maps.py`, `w2_zone_channel_integration_v1` registered |
| **steals and turnovers** | `not started` | pbp turnover events with cause sub-type | turnovers per touch/possession-used; steals per defensive possession | must separate live-ball/steal-related turnovers from travels and offensive fouls |
| **rebounds** | `not started` | pbp rebound events | **rebound opportunities**, not total possessions | the known blocker: opportunity denominators require the event stream, not the possession stream |
| **blocks and rim events** | `not started` | pbp block events; shot distance/coordinates | blockable opponent attempts / rim attempts | rim-defence attribution is weakly supported — `PLAYER3` credits the blocker only |
| **assists** | `not started` | pbp `PLAYER2` on made field goals | potential assists / teammate conversion opportunities | true "potential assists" are **not** in this data; a weaker proxy must be registered explicitly |
| **fouls and free throws** | `not started` | pbp foul and free-throw events | fouls per defensive possession; FT makes conditional on projected attempts | `w4_refs.py`, `data/ref_assignments/`, `w4_ref_fta_priors_v1` registered — officiating priors exist and are reusable |

---

## 4. Player-impact and structure layer

### P3 / RAPM — `canonical` coefficients, **downstream null**

| field | value |
|---|---|
| code | `experiments/player_program/fit_rate_and_p3.py`, `validate_p3.py`; `build_rapm.py`, `build_rapm_v1.py`, `build_rapm_walkforward.py` (earlier) |
| artifact | `fits_v1/p3_coefficients_v1.parquet` — 1,177 player-cutoff rows, cutoffs 2021–2025 |
| registration | `p3_adjusted_impact_v1`, `p3_defensive_impact__amendment_downstream_ablation`, `p3_projected_exposure_downstream_v1` |
| validation | **intrinsic: positive.** Stint differential MAE 2.147 vs 2.206 intercept-only on 35,515 held-out stints / 1,286 games, game-clustered CIs excluding zero. **Operational: null.** All five arms fail under projected exposure |
| reusable | the frozen coefficients, **for a future ablation only if a materially different exposure artifact is developed for an independently justified reason** |
| **must not reuse** | individual **defensive** coefficients as interpretable player ratings — off/def possession columns correlate ≈0.99999, design rank deficiency 2, defensive penalties selected 3–10× larger. Do not retune penalties or rescale the adjustment. |
| next dependency | **none authorised.** P3 work is stopped. |

Earlier `experiments/rapm_v0/` is a `prototype` (report, `rapm_by_season.csv`, `stint_eval.csv`),
superseded by the frozen P3 fit.

### archetypes — `prototype`, discovery-grade

| field | value |
|---|---|
| code | `features/archetypes.py` (5 axes: rot_height, opp_3pa, rim_protect, pressure, pace) |
| artifact | `experiments/feature_archetypes/` — `archetype_results.csv`, `named_player_deviations.csv`, `quarantine_audit.json`, `survivor_summary.csv` |
| registration | `player_vs_archetype_v1` (team registry) |
| validation | discovery-grade only; not a registered promotion experiment |
| reusable | the axis definitions and the quarantine audit pattern |
| **must not reuse** | any all-years clustering solution applied retrospectively; archetypes as fixed career identities |
| next dependency | the registered archetype layer (`player_archetype_discovery_layer`), which must not begin before the relevant pooled baselines exist |

### lineup chemistry and pairings — `not started`

No code, no artifact, no registration. Registered as a future track in
`player_program_capability_matrix_and_lanes`. Constraint on record: do not begin with unrestricted
lineup IDs; use shrinkage and minimum-support rules. Depends on stints (available) and on a
projected-rotation model (available, v1).

### situational effects (rest, travel, venue, schedule) — `prototype`, discovery-grade

| field | value |
|---|---|
| code | `features/fam_a.py` (venue, time, travel, rest), `features/moderators.py` (11 preregistered moderator traits), `fam_b/d/e/f/g/h/i/j.py` |
| artifact | `experiments/feature_screen*/`, `feature_interactions/`, `feature_screen_crossseason/` |
| registration | `player_feature_screen_v1`, `player_feature_crossseason_v1`, `player_feature_rebaselined_v1`, `player_feature_interactions_v1` |
| validation | screening-protocol amendments v2–v5 registered; discovery-grade |
| reusable | the moderator trait definitions and the screening protocol |
| **must not reuse** | screen results as promotion evidence |
| next dependency | wave P4 of a registered event-channel program |

### player development and aging — `prototype`

| field | value |
|---|---|
| code | `bios_screen.py`, `features/bios_features.py`, `collect_bios` path |
| artifact | `experiments/bios_collection/` — coverage, sanity and height-by-position checks |
| registration | **none found** in either registry |
| validation | collection-level sanity only |
| reusable | biographical joins, height/position, tip coverage |
| **must not reuse** | future-season information to inform development effects — they may inform priors only |
| next dependency | wave P5; not before pooled baselines |

### coaching and rotation strategy — `not started`

No code, artifact or registration. Registered as a future track. Now unblocked in principle: the
projected-rotation artifact exists, which is what it needed.

---

## 5. Aggregation, simulation and logging

### team aggregation — `canonical` incumbent, with a **binding negative precedent**

| field | value |
|---|---|
| code | `experiments/channel_reval/run_reval.py`, `build_channel_base_v2.py`; `bottomup_3pt.py`; `joint_differential.py` |
| artifact | `experiments/channel_reval/predictions_v2.csv` — the **frozen structural team incumbent**, 673 games, `str_home_cal` / `str_away_cal` |
| registration | `chanreval_2026_structural_repaired` (PASS, all five gates); `bottomup_3pt_channel_v1`; `joint_differential_v1` |
| validation | structural sum beats raw-trend by 0.630 MAE pooled, 90% date-clustered CI [+0.394, +0.866] |
| reusable | the incumbent predictions as the paired baseline for any player-to-team aggregation |
| **must not reuse** | `experiments/arm_incumbent/predictions.parquet` — **REJECTED**: target-box membership controlled its coverage |
| next dependency | any aggregation experiment must report home/away residual variance, covariance, `corr(e_home, e_away)`, and resulting margin variance and MAE |

**Binding precedent:** `bottomup_3pt_channel_v1` improved its own channel and *degraded* joint
team-margin accuracy by reducing useful home/away residual covariance. A channel-level gain is not
sufficient for promotion. `p3_projected_exposure_downstream_v1` is now the second negative
aggregation result.

### uncertainty and simulation — `not started`

No simulation code exists. `evalharness/metrics.py` provides the distributional primitives
(pinball, CRPS, coverage, reliability) and v15/v12 emit quantiles `q05…q95`, so the *evaluation*
side is `canonical` while the *generative* side is `not started`. Accounting constraints already
enforced by the exposure bridge: team minutes 200, player possessions reconcile to team
possessions, both clubs coherent. Constraints not yet enforced anywhere: rebounds originate from
missed shots, assists relate to made field goals, makes ≤ attempts.

### prospective logging — `prototype`, **thin**

| field | value |
|---|---|
| code | `evalharness/forecast_log.py`, `daily_forecast.py`, `daily_certify.py`, `daily_refresh.py` |
| artifact | `forecasts/forecast_log.jsonl` — **8 entries** |
| registration | `prospective_v0`, `prospective_pockets_v1` |
| validation | mechanism exists; the log is nearly empty |
| reusable | the logging contract and the daily pipeline |
| **must not reuse** | 8 entries as prospective evidence of anything |
| next dependency | accumulate real prospective rows; this is a time dependency, not an engineering one |

---

## 6. Major blockers

1. **Event-schema split.** Two play-by-play formats with zero shared columns and a hard changeover
   mid-2025. Full universe coverage exists (1,495/1,495) but cannot be used as one stream. **Every
   granular event channel is behind this.** This is the single highest-value unblocking task.
2. **Opportunity denominators do not exist.** Rebound opportunities, potential assists, blockable
   attempts and touches are not derivable from the possession stream and are only partly derivable
   from the event stream. Weaker proxies must be registered explicitly, never presented as
   equivalent.
3. **No projected substitution timing.** v1 exposure assigns equal offensive and defensive
   possessions. Until a stint-level projection exists, no experiment can distinguish offensive from
   defensive exposure — which is exactly what limited the P3 ablation.
4. **Historical availability is not captured-as-of** before 2026-07-30. Every availability result on
   historical data is information-limited.
5. **Prospective log is empty** (8 rows). No prospective evidence is available for anything.
6. **The sensitivity arm of the rate model is unrepaired** — `_build_sensitivity` removes Tier B rows
   from the test frame as well as from history. Repair requires a new registered revision.
7. **The shared team gate `gate_receipt.py` remains fail-open** under the inherited `GIT_DIR`
   condition; `certifies_this_commit` can falsely certify when git status was never measured. This
   is a **team-thread** action and was deliberately not modified from this worktree.

## 7. Reusable assets

- `player_possessions/2` — 238,563 realised possessions, 1,495 games, hash-verified.
- `projected_player_possessions/1` + `team_possession_prior/1` — validated 35/35, the exposure and
  pace bridge, reusable by every future channel as the exposure weight.
- `prediction_contract_v5` — 44,851 tiered obligations with candidacy, evidence-time and
  ambiguity fields; strict superset of v4.
- v15 `p_active` and `e_minutes_given_active` for every obligation.
- Frozen P3 coefficients — for a future ablation only, under the stated condition.
- The frozen structural team incumbent — the paired baseline for any aggregation test.
- `evalharness` — metrics, clustered/moving-block bootstrap, splits, frozen baselines, the standard
  promotion gate.
- Full play-by-play (after normalisation) and shot charts with coordinates for ~1,485 games.
- Officiating priors (`w4_ref_fta_priors_v1`, `data/ref_assignments/`).
- The clean-producer hash discipline and fail-closed receipt pattern, reusable by every producer.

## 8. What must not be reused

- `experiments/arm_incumbent/predictions.parquet` — REJECTED artifact.
- The prototype's same-game opponent-efficiency normalisation, and its
  `data/player_possession_features*.parquet` outputs.
- `features/common.py::pace_sew` as a cutoff-valid pace artifact.
- Realised minutes, lineups, stint durations, possessions or pace as pregame features.
- Individual P3 defensive coefficients as interpretable player ratings.
- Transaction-derived Tier B or S2 regimes as candidate production models.
- Any claim that historical availability before 2026-07-30 is captured-as-of.
