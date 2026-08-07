# E0 I0004 — shot-location tendency/conversion x opponent location allowance

Idea: does a player's shot-location tendency and conversion interact with the
opponent's location-specific allowance, beyond a pooled shooting rate?
Parent thesis: T1 (context-normalized tendency x matchup interaction), T2
layer 3. Full idea record: `experiments/idea_log.jsonl` line 9 (I0004).

**Partition compliance.** Loaded ONLY
`data/shotcharts/shots_{2021,2022,2023,2024}_{regular,playoffs}.parquet`
(8 files, 132,558 shots, 970 games). Asserted `season.max() <= 2024` and
`GAME_DATE` year `<= 2024` in-script before any aggregation; both assertions
passed. `shots_2025_*` and `shots_2026_*` were never opened.

**Deliberately avoided the pre-built `data/zone_maps/*.csv` artifacts.**
Their manifests (`team_zone_defense.csv.manifest.json` etc.) state the
shrinkage priors and shrunk columns are **pooled across all seasons
2021–2026**, i.e. a 2021 row's shrunk value has already seen the 2025/2026
confirmation holdout. Reading even the "raw" columns of those files would
sit downstream of a K constant informed by the holdout, so this screen
rebuilds team/player zone rates directly from the raw per-season shot files
instead. This is a stricter reading of §13.2 than the letter requires, but
it is the only way to be certain nothing leaked.

**Deliberately avoided any on-court lineup join.** I0003 (rebound screen,
same day) found clock-time-to-possession-row lineup attribution only ~72%
accurate. Opponent identity here comes entirely from the two `TEAM_ID`s
present in each shot file's `GAME_ID` group — shot-event-level, no lineup
needed. All 970 games resolved cleanly to exactly 2 teams; 0 shots dropped
for missing opponent.

## 1. Shot-location granularity the data supports

Raw `SHOT_ZONE_BASIC` has 7 zones; `SHOT_ZONE_AREA`/`SHOT_ZONE_RANGE` give
finer angle/distance detail but were not explored here (time-boxed). Used
the 6-zone modeling scheme (merge Left/Right Corner 3, matching the existing
`RECONCILIATION.md` rationale for the pre-built maps, re-derived
independently rather than cited): Restricted Area, In The Paint (Non-RA),
Mid-Range, Corner 3, Above the Break 3, Backcourt. Zone cleanly implies
2pt/3pt value in this 4-season slice (checked directly, not assumed).
Volumes (2021–2024 only): Above Break 3 = 37,939, Restricted Area = 37,743,
Paint (Non-RA) = 27,397, Mid-Range = 24,370, Corner 3 = 4,855, Backcourt =
254. Corner 3 and Backcourt are thin at the player-season level (median
corner-3 attempts per player-season is single digits based on shot counts
here), consistent with the program's existing shrinkage design elsewhere.
**Verdict: the data supports the 6-zone decomposition; finer than that
(angle/range within zone) was not tested and would need more support.**

## 2. Do opponents differ systematically by zone? (§ step 2 of the task)

Computed team-season allowed-conversion and allowed-shot-mix-share by zone,
then a DerSimonian–Laird-style dispersion test (between-team variance vs.
pure binomial sampling noise) — same method family as the existing
`RECONCILIATION.md` used, re-derived here from scratch on the 4-season
partition only (not cited from that file).

**Allowed conversion rate:** only **Restricted Area** shows real between-team
dispersion (Q=175.2 vs df=47, K≈287 pseudo-attempts). Every other zone
(Above Break 3, Corner 3, Paint Non-RA, Mid-Range, Backcourt) is
noise-dominated (K in the hundreds to infinite) — WNBA defenses in
2021–2024 barely differ in the field-goal percentage they allow once a shot
goes up from a given non-rim zone.

**Allowed shot-mix share (what fraction of opponent's shots come from each
zone):** Restricted Area (K≈177) and Paint Non-RA (K≈276) show real
dispersion; Above Break 3, Corner 3, Mid-Range, Backcourt do not.

So: opponents differ meaningfully in **rim defense** (both how much rim/paint
volume they concede and how efficiently they defend the rim specifically),
and barely at all in perimeter/mid-range defense. This independently
reproduces the qualitative pattern visible in the (out-of-scope, all-season)
pre-built zone maps' shrinkage table without citing or reading it as
evidence — it is a coincidence check, not a source.

## 3. Player interaction, beyond pooled — and a leakage catch worth flagging

First pass: built a leave-current-season-out player-zone conversion
baseline (own-player rate from the *other* seasons, min 10 other-season
attempts) and an opponent zone_conv_residual = team-season zone rate minus
team-season pooled rate, then correlated the player's shooting residual
against the opponent's zone residual. Result: **positive correlation in
every zone**, largest in Corner 3 (r=+0.090) — which was immediately
suspicious given step 2 found **zero real between-team dispersion in Corner
3 defense**. A correlation that strong with a variable that has no real
signal is a red flag.

**Cause found:** the opponent's season-zone rate included the very shot
(and the player's whole game) being tested against it. A make mechanically
inflates the exact "allowance" number used to explain it, and the bias is
largest precisely in the thinnest zones (Corner 3), which is exactly the
pattern observed. This is the same family of self-inclusion leakage as
report-worthy findings elsewhere in this program.

**Fix:** recomputed the opponent's zone rate and pooled rate as
**leave-one-game-out** (excise the current game's makes/attempts from the
opponent's season-zone tally before computing the comparison rate). Same
player-zone baseline as before. Re-ran the correlation:

| zone | n | corr | mean diff (hi−lo opp-allowance half) | approx SE(diff) |
|---|---|---|---|---|
| Above the Break 3 | 34,961 | +0.0027 | +0.0033 | 0.0051 |
| Corner 3 | 3,872 | −0.0153 | −0.0147 | 0.0157 |
| In The Paint (Non-RA) | 25,436 | −0.0027 | −0.0021 | 0.0061 |
| Mid-Range | 22,461 | +0.0110 | +0.0197 | 0.0065 |
| **Restricted Area** | 34,681 | **+0.0444** | **+0.0392** | 0.0052 |

The Corner 3 "signal" **evaporated and flipped sign** under the corrected
measure, confirming it was the self-inclusion artifact, not a real effect.
Above-the-Break-3 and Paint (Non-RA) are indistinguishable from zero.
Mid-Range is small relative to its SE (~3x, but this is one of five zones
tested with no multiplicity correction, and mid-range didn't show real
opponent dispersion in step 2 either — it should be read cautiously).

**Restricted Area is the one result that is internally coherent**: it is
the *only* zone with (a) measured real between-team dispersion in opponent
allowance (step 2) and (b) a leave-one-game-out player-level interaction
effect large relative to its noise (diff ≈ 7.5x its approximate SE).

## 4. Direction and persistence (within-partition only)

Split the Restricted Area and Mid-Range LOO results into 2021–2022 vs.
2023–2024 (both halves strictly inside the exploration partition):

- Restricted Area: corr +0.049 (n=16,297) in 2021–2022, +0.034 (n=18,384)
  in 2023–2024 — same sign, same rough magnitude, both halves.
- Mid-Range: corr +0.007 (n=11,131) then +0.015 (n=11,330) — small and
  inconsistent enough to not trust.

Direction is the expected one: a shooter's rim-finishing rate, net of their
own baseline, tends to run higher against opponents whose rim defense is
specifically more permissive than their overall defense (net of the
opponent's own overall defensive level) — i.e. a real interaction beyond
either pooled effect. It survives a season-half split inside the
exploration partition.

**Not tested, time-boxed out:** concentration by player type/role (e.g. is
this driven by a handful of high-volume rim finishers, or broad-based?),
the shot-selection/tendency channel (does a player's *share* of shots taken
at the rim shift game-to-game with the specific opponent's rim-share
allowance — only the conversion channel was tested here), and any formal
multiplicity-corrected significance test (5 zones, casual normal-approx SEs
only, no clustering by player or team-season accounted for).

## Data quality notes worth keeping

- The pre-built `data/zone_maps/*` artifacts are **not usable inputs for
  any E0/E1 work** without re-derivation, because their shrinkage priors
  are pooled across 2021–2026 (confirmed via manifest). Anyone reusing
  I0005/I0006 (turnover, usage-redistribution) or a future zone-based E1
  should rebuild from `data/shotcharts/shots_*` per-season files directly,
  the way this screen did, rather than reading those CSVs.
- Shot-event-level opponent resolution (two `TEAM_ID`s per `GAME_ID`) is
  clean and complete for 2021–2024 (0/970 games ambiguous, 0/132,558 shots
  dropped) — a reusable, lineup-free pattern for any future zone/shot-level
  screen in this program.

## Decision

**Iterate (narrowed scope)**: kill the general "shot-location tendency x
opponent location allowance across all 4 zones" framing as originally
posed — most zones show no real opponent dispersion and no surviving
interaction once the self-inclusion leak is fixed. But the **Restricted
Area-specific** version (rim finishing vs. opponent rim-defense allowance,
net of pooled opponent defense and player's own baseline) is a coherent,
sign-consistent, within-partition-persistent lead worth a proper E1 basic
season-split/holdout-free confirmation before it can be called even a
signal candidate. Corner 3 / Above-the-Break 3 / Paint (Non-RA) / Backcourt
/ Mid-Range: kill for this framing.

Artifacts: `build_and_test.py`, `robustness_loo.py`, `run_log.txt`,
`run_log_loo.txt`, `team_zone_defense_2021_2024.csv`,
`shot_level_residuals_2021_2024.csv` (pre-fix, kept for the leakage
writeup), `shot_level_residuals_LOO_2021_2024.csv` (the trustworthy one).
