# CLOSED SURFACES — what is dead, what killed it, and why the mechanism matters

Built 2026-08-08 by the IDEATION agent from `experiments/player_program/orchestration/DECISION_LEDGER.jsonl`
(92 entries, D001–D093) and the completed directories under `experiments/exploration/`.

**Why this file exists.** Roughly 1,000 candidate cells have been screened. Nothing recorded which
*surfaces* those cells exhausted, so every ideation pass re-proposes dead ideas and every screening
agent re-derives dead ground. This is the inventory.

**How to use it.** The **KILL MECHANISM** column is the load-bearing part. A surface killed by an
*arithmetic ceiling* is dead for that target forever and dead for related targets in proportion to
their scale. A surface killed by *absorption into fixed effects* is dead as a between-unit level
effect but may be alive as a within-unit updating effect. A surface killed by a *reference blind
spot* or a *wrong null* is **not dead at all** — it was never honestly tested. A surface killed by a
*real null* is dead. Read the mechanism before proposing a variant.

Legend for KILL MECHANISM:
- `CEILING` — arithmetic: 1 sd of the signal cannot move the target enough, regardless of statistics.
- `ABSORBED` — the effect is fully explained by a control (fixed effects, a level term, a component).
- `REDUNDANT` — the effect is a repackaging of an already-known main effect.
- `REAL_NULL` — properly powered, properly nulled, nothing there.
- `CONSTRUCTION` — the specific construction was defective; the underlying question may survive.
- `SCOPE` — dead for the tested target/level only; explicitly open elsewhere.

---

## 1. The efficiency step — THE PROGRAM'S CENTRAL QUESTION, CLOSED NEGATIVE

D081 established that points skill is lost at the **efficiency** step (minutes skill +3.55%, points
skill −0.22%). Four screens and ~1,000 cells were then fired at efficiency with **no survivor**.

| Surface | Decision | Scale of the attempt | KILL MECHANISM |
|---|---|---|---|
| Generic pre-game state → efficiency | D081 | 550 cells, **0 of 330 rate cells** | `REAL_NULL` |
| Opponent conversion allowance (I0004 conversion channel) | D084 | — | `CEILING` — dR2 ≤ 0.000129, 8.7x smaller than the ceiling that killed shot mix |
| Basketball-specific defensive matchup | D085 | 44 candidates; **12 constructions, 36 cells, 0 survivors** | `REAL_NULL` at team-aggregate level — see caveat below |
| Foul-draw matchup | D085 | — | `REDUNDANT` — a repackaged main effect |
| Shot quality (assisted share, avg shot distance, early-clock share) | D087 | **39 candidates, 0 of 39** on points-per-minute; 0 clearing even per-candidate on the decision stratum | `REAL_NULL` |
| Rest / load | D085 | — | `REAL_NULL` |
| Pace and transition | D085 | — | `REAL_NULL` |

**D087 ruling 1: "SINGLE-GAME SCORING EFFICIENCY IS NOT FORECASTABLE FROM PRE-GAME STATE."**

> **CAVEAT THAT A PROPOSER MAY LEGITIMATELY USE.** D085's 12 defensive-matchup constructions were built
> from **team-level aggregates**. `data/possessions/possessions.parquet` carries the actual on-court
> five for both teams on every possession of all 1,495 games, and I verified that shots join to it
> (see §8). Possession-level *defender identity* is a materially different construction from
> team-season defensive rating. This is **not** authorisation to re-run D085 — it is a statement that
> the kill mechanism was aggregation, and a proposer must say so explicitly and carry the
> ceiling estimate. See QUEUE Q22.

## 2. Opponent / matchup families

| Surface | Decision | KILL MECHANISM |
|---|---|---|
| Opponent defensive matchup → efficiency (12 constructions, 0/36) | D085 | `REAL_NULL` at aggregate level |
| Opponent shot-quality-conceded | D087 | `REAL_NULL` |
| T2 layer-3 personnel matching | D014, D061 | `SCOPE` — documented but **no estimand**; unfittable, not refuted |
| Opponent unfamiliarity | D076 | `ABSORBED` — dR2 ≤ 0.0006 after conditioning |
| Height / size mismatch family (I0008) | D064, E1_I0008 | `REAL_NULL`. Vertical jump and reach are **not collected anywhere** — new acquisition required |
| Positional matchup (E0_I0010) | D075 note | `CONSTRUCTION` — affected by the `base.zwithin` retrospective centering (F7), magnitude never measured |

## 3. Schedule and rest — DEAD ACROSS FOUR SCREENS AND THREE TARGETS

| Surface | Decision | KILL MECHANISM |
|---|---|---|
| Back-to-back, 3-in-4, rest days, travel | D076, D090 | `REAL_NULL`. 18 cells, best abs(t) 7.46, decile ratios 0.94–1.25, B2B/3-in-4 at p 0.34–0.94 |
| Home / away | D076 | `REAL_NULL` |
| Roster churn, starting-five stability | D076 | `REAL_NULL` |
| Role volatility (`pl_min_sd5`, `pl_min_cv5`) | D076 | `CONSTRUCTION` — large abs(t) but **negative** skill gain at every coverage; they are volume proxies |

**D090 ruling 5: "THE SCHEDULE FAMILY IS CLOSED. Four screens, three targets, nothing. No fifth
attempt without a new mechanism."** Cumulative season *load* is arguably a new mechanism and is not
the same as schedule *state* — queued as Q31 with that argument made explicitly.

## 4. Possession volume and pace — ALL 27 CONSTRUCTIONS CLOSED

| Surface | Decision | KILL MECHANISM |
|---|---|---|
| Expected game possessions → assists (the I0013 survivor) | D073 | `ABSORBED` — a between-team-season pace **LEVEL** effect. ~99% of the effect sits in the team-season level, ~0% in within-season updating |
| All 27 possession-volume constructions | D073 | `ABSORBED` / `REDUNDANT` — "fast teams generate more assists" is true, uninteresting, and already priced by a posted total |
| Possessions-per-minute as a player exposure channel | D073 | `ABSORBED` |
| Supply-side pace instruments | D073 | `ABSORBED` |
| Tempo redundancy (E1_I0013) | D073 | `ABSORBED` by team fixed effects |

> **THE REUSABLE TECHNIQUE, and it is the best methodological result of that screen (D073 ruling 3):**
> when a market comparison is blocked by missing price data, ask which **component** of the feature a
> posted line must already contain, and test whether the effect lives there. Decomposition substitutes
> for comparison. **This technique has never been applied to the currently live leads.** See QUEUE Q11.

## 5. Shot mix / shot location (I0004) — ALIVE ON ATTEMPTS, DEAD ON POINTS

| Surface | Decision | KILL MECHANISM |
|---|---|---|
| Shot-mix (selection) → **points** | D079 | `CEILING` — dR2 ≤ 0.001127. The attempts forecast was not the threat; the response variable's own scale was |
| Conversion channel → **points** | D084 | `CEILING` — dR2 ≤ 0.000129 |
| Rim-specificity | D074 | `REAL_NULL` |
| Role/volume concentration for selection | D074 | `REAL_NULL` |
| Shot-mix → **attempts** | D079 | **NOT DEAD** — KEEP-AS-LEAD, robust out-of-sample. Target is attempt counts by zone |

D084 recommendation: **shelve I0004** unless the free-throw route is judged worth building. The
untested routes it names are: attempt counts feeding rebound/assist opportunity, and zone mix feeding
**foul-draw and free-throw rates**. The free-throw route is queued as Q5 — it is the largest
untested points channel in the repository.

## 6. Per-player and per-cluster heterogeneity — CLOSED ON EVIDENCE (D093)

| Surface | Decision | KILL MECHANISM |
|---|---|---|
| Per-player coefficient heterogeneity in the six tested relationships | D093 | `CONSTRUCTION` — the positive was an artefact of an anticonservative null. Family-wise p 0.0055/0.0045/0.0080 under a plain within-player shuffle; **p 0.625/0.334/0.383/0.623/0.661/0.460 under an honest cyclic-shift null** |
| Per-player model fitting generally | D093 | `CEILING` (power) — five best-sampled players, 102–107 games each, strict walk-forward: **every one loses to that player's own strictly-prior average**. Walk-forward R2 negative on all ten player-floor cells (−0.052 to −0.197) while in-sample R2 is +0.04 to +0.18 |
| Realised-minutes floor as a route to skill | D093 | `REAL_NULL` — flat against the strongest reference: +0.559%, +0.283%, +0.170%, +0.443%, +0.514%, +0.219% at floors 0/10/15/20/25/30 |

> **D093's own preserved disagreement, which a proposer may cite:** "a negative on six is not a
> negative on all possible heterogeneity... A successor should not cite this as proof that no
> player-specific structure exists anywhere in basketball."

> **The one genuine positive from D093:** per-player sensitivity to opponent defence rises with the
> player's own strictly-prior usage (Spearman +0.320, family-wise p 0.0035 under the cyclic null,
> both negative controls clean). **This is currently being screened by `E1_I0023_usage_defence_interaction`
> — DO NOT PROPOSE IT.**

## 7. Miscellaneous closed items

| Surface | Decision | KILL MECHANISM |
|---|---|---|
| Assisted share | D087 | `REAL_NULL` (part of the 39 shot-quality candidates) |
| Layer-2 offensive-rebound main effect | D062 / I0003 lineage | `REAL_NULL`; note I0003 carried a ~72% lineup-attribution defect |
| `p_active` as an abstention variable | D090 | `REDUNDANT` — adds nothing over prior-appearance depth. Do **not** combine the two |
| `p_active` quality generally | D090 | Not a problem — AUC 0.90, 2% of error from miscalibration. **Should not be rebuilt** |
| Listed position in the cold-start tier rule | D092 | `REAL_NULL` as tested (p 0.783, permutation null 0.1996) — **but see the §9 warning; the column may have been the wrong one** |
| Bottom-up aggregation (layer 4) / projected exposure (P3) | D061, D062 | `SCOPE` — status is **VIABLE_BUT_UNVALIDATED**, explicitly *not* cleared and *not* refuted. Do not rerun unchanged; a materially improved exposure artifact would justify a retest |
| Market comparison on the exploration partition | D071, D073 | `SCOPE` — **impossible**, not refuted. No usable 2021–2024 totals: `bookie_totals_per_game.csv` has 0 rows in-partition, `totals_head/game_level_totals.csv` has 229 rows dated 2024 with `bookie_consensus_total` **100% NULL**. Of 45 market-named files, **zero** carry a manifest |

## 8. LIVE LEADS — do not propose these as new; extensions are welcome and must be marked

| Lead | Decision | Standing |
|---|---|---|
| Teammate-volume channel, **prior-only** variant | D089 | **The program's best usable lead.** Walk-forward points dR2 **+0.0023**, largest measured arithmetic ceiling **0.0021**, largest points-MAE reduction 0.79%. Modest in absolute terms and must be described that way |
| Teammate-volume, **tip-time** variant | D089 | **NEVER QUOTE AS A RESULT.** Computed from a post-game observation. ~49.2% of the channel is same-day news nobody can currently have. dR2 0.0078 is an upper bound, not a forecast |
| Cold-start tiering rule | D092 | **VALIDATED**, more than doubles the crude splice. Target population is **1–2 prior appearances, not rookies/debuts** |
| Shot-mix → attempts | D079 | KEEP-AS-LEAD, attempts only |
| `p_active` long-absence miscalibration | D090 | **11.5 pp too pessimistic** on returns from long absence; mis-shapes the duration curve rather than being uniformly biased |
| `p_active` void-risk under-estimate | D090 | **7.7 pp** under-estimate concentrated in the 0.50–0.80 band, running in the costly direction, on 9.5% of rows. "The most directly monetisable finding of the session." Needs no new signal and no new data |
| I0009 (additive pressure / turnover) | D072 | Survives but **materially reduced**: ranking entry **0.000413**, not 0.004003 |

**CURRENTLY RUNNING — DO NOT PROPOSE:** `E1_I0022_optimal_simple_estimator` (is the champion beating
a well-tuned prior-history estimator?), `E1_I0023_usage_defence_interaction`,
`E0_I0024_reb_ast_characterisation`, `_screen_kit` repair.

## 9. STRUCTURAL FACTS I VERIFIED ON BYTES THAT ARE NOT IN THE LEDGER

These are new. Each is either a trap sitting in the data directory or a constraint on future work.

1. **`master_player.position` is blank on exactly the 18,762 non-starter rows (55.65%).** Cross-tab is
   perfectly separating: `position` non-blank = 14,950 = `starter_flag == 1`. Any feature keyed on
   this column silently conditions on starter status. `data/reference/player_bios.csv:position_raw`
   is the correct source at **99.81%** coverage of 1,058 player-seasons. D092's "listed position
   contributes nothing" may have been measured on a column missing for over half the rows.

2. **The `era` measurement regime is confounded with the exploration/holdout partition.**
   2021–2024 is ~92% `gamelog_old`; **2025–2026 is 100% `gamelog_new`** (0 `gamelog_old` rows).
   Every E0/E1 screen ran on one measurement regime and every E2 confirmation will run on the other.
   A failure to replicate at E2 would be **uninterpretable**. Not recorded anywhere.

3. **Raw play-by-play is holdout-poor.** `data/playbyplay/` holds 996 files of 1,495 games:
   2021–2024 = 888/970 (**91.5%**), 2025 = 108/310, **2026 = 0/215**. Any lead built on raw pbp is
   constructible in exploration and **not confirmable** at E2.

4. **`data/possessions/possessions.parquet` does NOT share that gap** — 238,563 possessions covering
   **all 1,495 games including 2026**, with the full on-court five for both teams. It has **no
   manifest**, and its coverage exceeds the raw pbp it was presumably derived from, which is an
   open provenance question a screen must resolve before relying on it.

5. **Shots join to possessions on all seasons without raw pbp.** Verified: 100% of `shots_2023_regular`
   GAME_IDs present in possessions; on a 40-game sample, **5,515 of 5,515 shots (100%)** fall inside a
   possession window under the cumulative-game-seconds convention. 46% are boundary-ambiguous and need
   tie-breaking by `offense_team_id`. 2026 shots also match 100%.

6. **`data/lineups/lineups_*.parquet` are SEASON-AGGREGATE totals retrieved 2026-08-06**
   (`GROUP_SET='Lineups'`, GP/W/L season totals, `retrieval_ts` 2026-08-06,
   `vendor_ts_semantics='not_a_timing_claim'`). Using them for any exploration-season row is a
   **retrospective-baseline violation** — full-season lineup totals read the future of every game.
   This is trap #1 sitting unlabelled in the data directory.

7. **`data/injury_history/injury_history.csv` carries dated, typed absence records nobody has used**:
   8,340 rows, 2021-01-07 → 2026-07-29, including **2,242 `missed_game_injury`** with 184 distinct
   body-part notes (KNEE INJURY 179, RIGHT KNEE INJURY 152, ACL 53, ACHILLES 36, CONCUSSION PROTOCOL
   57, ILLNESS 42) and **3,131 `missed_game_other`**. 3,262 of these fall in 2021–2024. This is not a
   pre-game inactives feed, but a player's **own and teammates' prior absence spells with injury type**
   are strictly-prior facts. D089 recorded that no pre-game injury feed exists; that is true of
   *today's* inactives and **not** true of absence history.

8. **`dnp_reason` is 100% populated on all 5,384 DNP rows and null on all played rows**, with 22
   distinct values separating Coach's Decision (2,824) from Injury/Illness (1,662+464) and Not With
   Team (152). 15.97% of `master_player` rows are DNP rows. 78.5% of team-games have ≥1 DNP, 30.8%
   have ≥3.

9. **Overtime inflates the target on 4.23% of played rows and is unforecastable at tip-off.**
   66 of 1,495 games reach period ≥5. Mean minutes 21.068 (non-OT) vs 25.147 (OT), **+19.4%**;
   mean points 8.652 vs 10.224, **+18.2%**.

10. **Every count target is over-dispersed and zero-inflated**, so a Gaussian/OLS treatment is a
    modelling choice nobody has justified. Exploration partition: `reb` var/mean 2.93, `ast` 2.40,
    `oreb` 1.74 with **53.0% zeros**, `blk` 1.51 with **70.9% zeros**, `fg3m` 1.79 with 56.6% zeros,
    `ftm` 2.87 with **49.3% zeros**, `pts` var/mean 6.45.

11. **Free throws are 17.4% of points and the channel has never been screened.** `ftm` correlates
    **+0.6595** with points (a perfect `ftm` forecast bounds at R2 **0.435** of points variance);
    `fouls_drawn` correlates +0.6749 and is 100% covered in all six seasons. `fta == 0` on **46.4%**
    of played rows, so it is a hurdle process, not a continuous rate.

12. **Cold-start populations are small.** Played rows with ≤0 prior appearances: 384 (1.36%);
    ≤1: 756 (2.67%); ≤2: 1,115 (3.94%). This bounds every cold-start proposal and corroborates
    D092's ruling that the target is 1–2 prior appearances rather than debuts.
