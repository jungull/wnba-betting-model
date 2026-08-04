# Stage 2A — adversarial leakage and identifiability review

**Source role:** independent adversarial review. Not a proposal of improvements. This document
states what will go WRONG in `TEAM_POSSESSION_PRIOR_V2` before anything is registered.

**Evidence used:** `experiments/player_program/stage2a/EVIDENCE_PACKET.json`
(sha256 `f373e3eed710026c9d82ff88aad1e9a2cae640ee461a5d7df5208d76abaf1e4e`, verified);
`build_projected_exposure.py`; `feature_gate.py`; `comparison_gate.py`; `gate_invocation.py`;
`GATE_INVOCATION_CONTRACT.md`; and read-only structural inspection of the frozen artifacts
`team_possession_prior_v1.parquet`, `possessions_raw_v2.parquet`,
`team_turnover_reconciliation_v1.parquet`. Nothing was fitted, tuned or scored. Every number
below marked **[verified]** was recomputed from frozen bytes as a structural/descriptive count,
not as a model or accuracy figure.

**Not read:** any `HYPOTHESES_*` file, per the independence protocol.

**Nothing here is a commitment.** Every item is a trap to close or a control to consider.

---

## 0. The three defects most likely to sink this experiment

Stated first because the rest is long.

1. **The evaluation has half the sample size it will report.** Both sides of a game receive an
   identical projection **[verified: 0 of 1495 games have differing
   `projected_team_off_possessions`]**, and 98.99% of the team-game target variance is game-level
   **[verified]**. `n = 2982` is `n_effective ≈ 1491`. Every uncertainty statement will be
   understated by ≈√2 unless clustered on `game_id`. §4.1.
2. **The pace scale and the turnover exposure scale are different units, and the obvious fix
   leaks.** The canonical turnover exposure is RAW possessions; the pace target is
   REGULATION-EQUIVALENT **[verified: exact equality of
   `team_turnover_reconciliation_v1.team_off_possessions` with raw `n_off_poss` on all 2990 rows;
   reg-equivalent fails]**. On the 132 OT team-games raw exceeds reg-equivalent by mean factor
   **1.140** (up to 1.5). Converting between them requires the target game's `max_period`. §1.2.
3. **K0 has not been defined, and the definition decides the result.** The incumbent's *pooled*
   bias is negligible (0.19% of MSE) but its *stratum* biases are enormous (−2.845 on
   `team_window_prior_season`, +1.342 on support 3-4, −2.175 on `game_no_in_season` 1-3). A fitted
   challenger with an intercept and one `pace_level` dummy removes all of that with zero
   substantive features. Whether that flexibility sits in K0 or in the challenger is the single
   choice most likely to determine the verdict. §3.1.

---

## 1. Leakage surfaces specific to THIS target

The target is `realised_off_poss = n_off_poss * 40.0 / game_minutes` where
`game_minutes = 40 + 5 * max(0, max_period - 4)`, with `max_period` taken from the TARGET game
(`build_evidence_packet.py:50-53`, matching `build_projected_exposure.py:257`).

### 1.1 The regulation-equivalence divisor is itself a post-cutoff quantity

**Mechanism.** `game_minutes` is a deterministic function of whether and how far the target game
went to overtime. That is legitimate in a *target* (targets are realised) and illegitimate
anywhere on the prediction path. Distribution **[verified]**: `max_period` 4 → 2858 team-games,
5 → 120, 6 → 10, 8 → 2. The transform therefore encodes a 4.4%-prevalence binary outcome plus a
severity level.

The concrete construction that will be built: a variant that predicts *raw* possessions (a more
natural quantity — it is what the possession stream counts) and then rescales to the target's
units by dividing by the realised `game_minutes`. That single line hands the model an exact
overtime indicator on 132 rows.

A second, subtler instance: any per-possession or per-minute normalisation of *history* is safe,
but a `duration_sec`, `period`, `regulation_seconds_remaining` or `is_overtime` column read from
`possessions_raw_v2` for the target `game_id` is not. All four are present in that artifact
(packet `context_availability.possessions_raw_v2_columns`) and a careless join on `game_id`
without a date filter pulls them in.

**How it shows up if undetected.** Possession MAE improves disproportionately on the 132 OT
rows. The packet already reports `by_overtime` MAE of 2.367 (OT) versus 2.928 (non-OT) for the
incumbent — the OT stratum already looks "easier" because the transform compresses it — so an
improvement concentrated there will read as consistent with the incumbent's own pattern rather
than as anomalous. It will not look like leakage; it will look like a variant that handles OT well.

**Detection / prevention.** (a) Enumerate, in the task card, every column of `possessions_raw_v2`
and `master_team` and mark each as history-only; assert at build time that no row of the design
was sourced from a possession row whose `game_id` equals the target `game_id`. (b) Require the
prediction to be emitted natively on the regulation-equivalent scale, with an explicit statement
that no target-game length quantity appears in the path. (c) Report challenger-vs-K0 split by
`went_ot` as a *diagnostic only* — an improvement concentrated on 132 rows is a leak signature,
not a finding (and see §4.5: `went_ot` must never be a reported stratum in the result itself).

**Do existing contracts catch it?** **No.** `feature_gate.target_derived` fires at
`|corr| ≥ 0.98`; an OT indicator's correlation with regulation-equivalent possessions is nowhere
near that. `missingness_encodes_outcome` cannot fire on a design with no nulls.
`GATE_INVOCATION_CONTRACT.md` §7.3 explicitly disclaims this class: *"A column derived from
post-cutoff information whose values happen not to correlate above threshold with the target ...
passes."* **New control needed.**

### 1.2 The units mismatch — and why parity checking will not save you

**Mechanism.** **[verified]** `team_turnover_reconciliation_v1.team_off_possessions` is *exactly*
the raw `n_off_poss` count on all 2990 rows; it is *not* regulation-equivalent. Arm D
(`turnover_rate_pooled_baseline_v1`, EWMA-shrunk, K=200, α=0.10) is a RATE over that canonical
exposure. The incumbent `team_possession_prior/1` emits regulation-equivalent possessions. On the
132 OT team-games, mean raw is 89.96 against mean reg-equivalent 78.91 — ratio **1.140**, and
1.5 for the two `max_period = 8` games.

Multiplying a raw-basis rate by a regulation-equivalent exposure under-projects team turnovers on
every OT game by 11-33%.

**How it shows up if undetected.** It does **not** show up as a difference. The incumbent, K0 and
all 6-10 challengers share the identical defect, so every contrast is unaffected and every parity
check passes. What it does instead is inflate the shared downstream error floor on 4.4% of rows,
which compresses all contrasts toward each other and makes the whole experiment less able to
resolve the effect it is hunting. Then someone notices the OT rows and "fixes" it by multiplying
by the realised `game_minutes / 40` — which is defect 1.1 exactly.

Note also that the packet's own downstream figure is *not* the Arm D propagation: it computes
`rate = team_tov / realised_off_poss` (`build_evidence_packet.py:118`) — an oracle rate on the
regulation-equivalent basis. The JSON says so honestly (`"at the realised team turnover rate"`);
the code comment above it says `"with the frozen Arm D rate"` (line 107), which is wrong and is
exactly the phrasing that migrates into a task card. `mean_abs_propagated = 0.51744` is an
oracle-rate floor, not a prediction of what the registered experiment will observe. It must not
be quoted as an expected effect size.

**Detection / prevention.** The task card must state, as a number and a unit, what Arm D's
denominator is, and pick one of: (a) keep everything on the regulation-equivalent scale and
re-derive an OT-consistent Arm D exposure (which changes Arm D's inputs — probably out of scope);
(b) have the challenger predict RAW possessions, which requires forecasting game length and is a
genuinely different, harder problem whose OT component must itself be cutoff-valid; (c) restrict
the scored universe to `max_period == 4` (2858 of 2990) and report the 132 OT rows separately as
out-of-scope. Option (c) is the only one that is both clean and cheap, and it must be declared
*before* any fit because it changes `evaluation_rows`.

**Do existing contracts catch it?** **Partially, and in the wrong direction.**
`comparison_gate.DIMENSIONS` includes `exposure_offset` — *"log-exposure offset, its definition
and its units"* — which is precisely the dimension for this. But the gate only tests **parity**:
`dimension_parity` fires when two sides *differ*. Here all three sides declare the same wrong
units and parity is perfect. **A parity gate cannot catch a shared error. New control needed: an
absolute units assertion, checked on the OT subset.**

### 1.3 League-to-date means and the date-versus-row boundary

**Mechanism.** The incumbent gets this right, and that is worth stating so a V2 does not
"simplify" it. `build_projected_exposure.py:279-282` aggregates `game_pace` to `game_date`
*first*, then `cumsum().shift(1)`. The shift is therefore by one **observed date**, not one row
and not one calendar day. Any V2 that instead computes an expanding/rolling league mean at the
GAME level, or calls `.shift(1)` on a game-sorted frame, or uses `.rolling(window)` without a
date-level collapse, silently includes contemporaneous games.

**[verified]** 446 of 575 game dates carry ≥2 games; the mean is 2.60 and the maximum 6. A
same-date leak therefore contaminates the majority of rows, at a strength of 1-5 concurrent games.
League pace on a given night is correlated across games (schedule, officiating crew rotation,
season phase), so this is a live channel, not a technicality.

Two further traps in the same family. (i) The incumbent's league prior is **cumulative over all
history and never resets at a season boundary** — a stated assumption. A "recent-window league
prior" variant must define the window on strictly-earlier DATES, and the 129 single-game dates
make an off-by-one hard to see. (ii) `league_prior_mean.get(r.game_date, np.nan)` is a lookup on
a date index; a V2 that reindexes or resamples that series (e.g. to a daily calendar with
forward-fill) will forward-fill *across* the season boundary and give a 2026 opener a league prior
that includes 2025 playoff pace as if it were current.

**How it shows up.** A uniform, small improvement across all rows with no plausible mechanism —
the classic same-day-leak signature. Because the effect is small per row and universal, it
survives every stratified diagnostic.

**Detection / prevention.** A two-line exact assertion, cheap and decisive: for any
league-to-date column, (a) its value must be **constant within each `game_date`**, and (b) it must
equal the mean over rows with **strictly earlier** `game_date`. Both are computable from the
design alone. **Category A.**

**Do existing contracts catch it?** **No.** Neither `feature_gate` nor `gate_invocation` inspects
chronology at any point. `gate_invocation` touches "cutoff" only as an author-supplied assertion
(`cutoff_valid: True` required per operation, line 1189), and its own docstring at line 1133 says
the gate cannot verify cutoff validity. **New control needed.**

### 1.4 Opponent history — the `<` / `<=` boundary, amplified by the shared projection

The packet flags opponent trailing `game_pace` as cutoff-valid and unused by the incumbent. It is
the most obvious V2 feature and therefore the most likely place for the boundary error.

**Mechanism.** Building it requires a schedule self-join. A merge on
`(opp_team_id, game_date)` with `<=` rather than `<`, or an `asof` join with
`allow_exact_matches=True` (the pandas default), puts the TARGET game into the opponent's history.
Because `game_pace` is the mean of BOTH sides' realised regulation-equivalent counts
(`build_projected_exposure.py:263-265`), one leaked window slot of ten carries weight 0.1 on
`(R_A + R_B)/2` — i.e. **0.05 directly on the team's own target**.

**The amplifier the incumbent's construction supplies.** `projected_team_off_possessions` is the
mean of the two sides' `team_pace_estimate` (line 327-329) and is **identical for both sides**
**[verified: 0 of 1495 games differ]**. So a leak in team A's estimate propagates into team B's
projection at half weight through the averaging step. A leak test that only asks *"does team A's
history exclude team A's target row?"* passes while team A's *projection* is corrupted through
team B. The test must be applied at both levels.

A second, non-leak but real hazard: **own history is already opponent-contaminated by
construction.** Because `game_pace` is a game-level mean, a team's own trailing window already
contains every historical opponent's contribution. The incumbent's stated "no opponent adjustment"
is true only of the TARGET opponent. **[verified]** 50.1% of level-1 team-games have at least one
prior head-to-head meeting inside the trailing 10-game window (mean 0.667 meetings; 296 rows have
2, 45 have 3, 22 have ≥4), and a shared meeting contributes the *identical number* to both teams'
windows. See §2.5.

**How it shows up.** A large, clean, plausible-looking improvement — opponent adjustment is a
real effect, so a leaked version looks like a confirmed hypothesis. This is the worst kind.

**Detection / prevention.** (a) Per-row assertion at the `team_pace_estimate` level:
`max(history.game_date) < target.game_date` AND `target.game_id ∉ history.game_id`. (b) The same
assertion at the assembled game-projection level, covering both sides. (c) A **date-shift
placebo**: rebuild with every history date advanced by +1 day; rows whose window boundary crosses
must change. A projection that is *invariant* to this is not reading the boundary it claims to
read. (d) Never use `merge_asof` defaults. **Category A.**

### 1.5 Season boundary, expansion, and the truncated 2026 fold

**[verified] `pace_level` by season:**

| season | L1 | L2 (prior season) | L3 (league) | L4 (unresolved) | teams | games | playoff team-games |
|---|---|---|---|---|---|---|---|
| 2021 | 382 | **0** | 28 | 8 | 12 | 209 | 34 |
| 2022 | 442 | 36 | **0** | 0 | 12 | 239 | 46 |
| 2023 | 484 | 36 | **0** | 0 | 12 | 260 | 40 |
| 2024 | 488 | 36 | **0** | 0 | 12 | 262 | 44 |
| 2025 | 581 | 36 | 3 | 0 | 13 | 310 | 48 |
| 2026 | 385 | 39 | 6 | 0 | **15** | 215 | **0** |

**Mechanism and hazards.**
- `s == r.season - 1` reaches back exactly one season. For 2021 there is no prior season, so
  **level 2 cannot fire at all in 2021**. A V2 that reaches back two seasons for expansion teams
  pulls a roster that does not exist.
- **[verified]** All 183 level-2 rows have `n_history_games == 10` — the prior-season window is
  always full. The column carries **zero information** about prior-season support on exactly the
  stratum with the largest bias (−2.845). Any shrinkage weight built on it is constant there.
- 2026 has **zero playoff games** and ends `2026-07-31` against a current date of `2026-08-04`.
  The final chronological fold is a truncated, in-progress regular season while every earlier
  fold contains 34-48 playoff team-games. Any `season_type`, "games remaining", "playoff race" or
  "season phase" construction is not merely leaky in 2026 — it is undefined.
- 2025 and 2026 add expansion teams (13, then 15). Their first games are precisely the level-3
  and level-4 rows, i.e. the highest-error stratum (`league_prior_all` MAE 3.902).

**How it shows up.** A variant that "handles cold start better" improves on rows that exist in
only three of six folds, and the consolidated number picks it up while three folds contribute
nothing. See §2.3 and §4.3.

**Detection / prevention.** Pre-declare, numerically, how each of these strata is treated per
fold, and pre-declare the fallback under `GATE_INVOCATION_CONTRACT.md` §4 *before* results are
visible. §4 is unambiguous: a fold-level failure discovered after results are visible invalidates
the arm and does not license repair-and-rerun.

### 1.6 The packet's own `days_rest` and `game_no_in_season` are wrong, and will be inherited

This is not a hypothetical. It is in the frozen packet's producer and will be copied.

**`days_rest`** — `build_evidence_packet.py:96`:
`res.groupby("team_id")["game_date"].diff().dt.days`. Grouped by `team_id` **only**, not by
`(team_id, season)`, and computed on `res` (the *resolved* subset, line 92).
**[verified]** 68 season-opener rows receive a median `days_rest` of **234 days**. Of the 162 rows
in the packet's `"7+"` bucket, **61 (37.7%) are season openers**. So the `"7+"` stratum — the
second-worst in the packet at MAE 3.527, bias −1.435 — is not a rest effect. It is a season-opener
effect, which is an alias for `pace_level ∈ {2,3}`.

**`game_no_in_season`** — line 98: `res.groupby(["team_id","season"]).cumcount() + 1`, also on the
resolved subset. Dropping the 8 unresolved rows (all in 2021) shifts the numbering of every
subsequent row in those 8 team-seasons. **[verified] the packet's `game_no_in_season` disagrees
with the true within-season game number on 266 of 2982 rows (8.9%).**

**How it shows up.** A "schedule fatigue" or "early season" feature that is really a re-labelling
of `pace_level` will improve exactly the rows `pace_level` already identifies, and the improvement
will be attributed to a schedule mechanism that is not there. Since schedule features are among
the few genuinely cutoff-valid inputs available (see §5, Category B), this is a likely path.

**Detection / prevention.** Correct definitions, and a reconciliation assertion. `game_id` encodes
season and a within-season sequence (`1022100001` = `10` | `2` | `21` | `00001`), so a true,
schedule-derived, cutoff-valid game number is derivable without any cumcount over a filtered
frame. `days_rest` must be grouped by `(team_id, season)` and computed over the *full* team-game
frame, with the season opener explicitly NaN rather than 234.

---

## 2. Identifiability risks

### 2.1 `pace_level` and the within-season game number are the SAME VARIABLE, exactly

**[verified] on all 2990 rows, with zero off-diagonal:**

| | true game no. ≥ 4 | true game no. ≤ 3 |
|---|---|---|
| `pace_level == 1` | 2762 | **0** |
| `pace_level ∈ {2,3,4}` | **0** | 228 |

This is not empirical, it is algebraic: level 1 requires `len(same) >= MIN_HISTORY_M == 3`, i.e.
at least three strictly-earlier same-season games, i.e. true game number ≥ 4. The implication
`pace_level > 1 ⟺ game_no_in_season ≤ 3` holds by construction and will hold on any rebuild.

**Mechanism.** A design carrying both a `pace_level` dummy set and any early-season indicator
(`game_no ≤ 3`, `is_cold_start`, `first_week`, a spline on game number) is exactly rank-deficient.

**How it shows up.** With both as numeric columns, `feature_gate.design_rank_report` fires
`rank_deficient` and blocks — good. But the failure mode that gets through is the **threshold**
form: a 3-level `pace_level` categorical plus a continuous `game_no_in_season` are not linearly
dependent, yet `1[game_no ≤ 3]` reproduces the level partition exactly.
`GATE_INVOCATION_CONTRACT.md` §7.1 names this class explicitly as an open gap: *"a threshold
indicator ... can be exactly redundant while the design retains full numerical rank and
unremarkable pairwise correlations. The gate passes it."*

**Detection / prevention.** State the dependency in the task card and forbid carrying both. Add a
pre-fit assertion of the 2×2 above as a *positive* check (it should hold — if a rebuild breaks it,
something else changed).

### 2.2 `n_history_games` is three different variables sharing one column

**[verified]** by level: L1 → 3..10 (trailing window size); **L2 → exactly 10 on all 183 rows**;
L3 → 4..1300 (the *cumulative league* game count, not team support); L4 → 0.

**Mechanism.** `build_projected_exposure.py:309` sets `n_hist = int(ln)` at level 3, where `ln` is
`league_prior_n` — a league-wide cumulative count. The column's *unit* changes with `pace_source`.

**Consequences.** (a) A shrinkage weight `n/(n+k)` is **constant across all of level 2** — the
stratum with bias −2.845 — so it cannot possibly correct it. (b) On level 3 the weight is ≈1,
implying maximal confidence on exactly the stratum with the *worst* MAE (3.902) and the *weakest*
team-specific support. The column is backwards where it matters most. (c) The packet's
`support_bucket` inherits this: the `">10"` bucket (n=23, MAE 4.538 — the worst stratum in the
whole packet) is **entirely level-3 rows** — the bins are
`[-1, 0, 2, 4, 9, 10, 1e9]` and nothing else can exceed 10.

**How it shows up.** Pooled, the column has ample variance, no nulls, finite values, and passes
every `feature_gate` check. A variant using it as a confidence weight looks well-motivated and
will produce a modest, believable gain driven entirely by the level-3 rows being treated as
high-confidence. Nothing in any gate can see a semantic error in a numerically healthy column.

**Detection / prevention.** Split it. Emit `n_team_history_games` (window support, NaN or 0 at
level 3) and `n_league_prior_games` as separate columns, or forbid the column outright and derive
support from `pace_source` + the corrected game number.

### 2.3 Per-fold zero variance — four named columns, four named folds

Under `GATE_INVOCATION_CONTRACT.md` §1, audits run per chronological training fold. **[verified]**
the following are zero-variance in specific folds:

| candidate column | zero-variance folds | rows in nearest non-empty fold |
|---|---|---|
| `1[pace_level == 2]` / prior-season-fallback | **2021** (0 of 418) | 36 |
| `1[pace_level == 3]` / league-prior-fallback | **2022, 2023, 2024** (0 each) | 3 (2025), 6 (2026) |
| `1[season_type == Playoffs]` | **2026** (0 of 430) | 34-48 elsewhere |
| any expansion-team indicator | 2021-2024 | 1 team (2025), 3 (2026) |

**Mechanism.** `feature_gate.audit` fires `zero_variance` (BLOCKING) and, at `std < 1e-8`,
`impossible_scaling` (BLOCKING). This is exactly the ws3 shape the contract was written for
(`proj_off_poss_share` std `7.80e-09` in the 2022 fold against `findings: []` pooled).

**How it shows up.** Pooled, all four columns look fine. The arm dies at the *first* per-fold gate
call — and under §4 it dies for good, because *"a fold-level failure discovered after results are
visible invalidates the affected arm's published result"* and *"any fallback ... must be part of
the frozen specification, registered before execution, with its trigger stated numerically."*

**Do existing contracts catch it?** **Yes, and this is the good news** — `feature_gate` blocks it
and `gate_invocation.audit_run` makes `no_per_fold_record` NON_ADJUDICABLE. But the gate **blocks;
it does not rescue.** The task card must pre-register the numeric fallback for each of these four,
or the experiment cannot run 2021 (or 2022-2024, or 2026) at all.

### 2.4 Team fixed effects break the fold schema

**[verified]** 12 / 12 / 12 / 12 / 13 / 15 teams by season. A design with team indicators trained
on ≤2025 has no column for the two 2026 expansion clubs. That is
`gate_invocation.train_test_schema_mismatch` (BLOCKING) or `feature_gate.schema_mismatch`
(BLOCKING). And the expansion clubs' first games are precisely the level-3/4 cold-start rows the
experiment most wants to improve — so the natural remedy (pool the new teams into an "other"
category) puts the hardest rows into a bucket with almost no training support.

### 2.5 Own-pace and opponent-pace are not independent regressors, and the dependence grows within a season

**[verified]** 50.1% of level-1 team-games have ≥1 prior head-to-head meeting inside the trailing
10-game window; mean 0.667 meetings; 1020 rows have exactly 1, 296 have 2, 45 have 3, 22 have ≥4.
Because `game_pace` is the game-level mean, a shared meeting contributes the **identical number**
to both teams' windows.

**Mechanism.** `own_trailing_pace` and `opponent_trailing_pace` share, on half the rows, at least
one of ten terms exactly. Their correlation floor is a function of how many head-to-head games
have already occurred, which **grows monotonically through a season**. So the collinearity is
mildest early and worst late — the reverse of the usual "early folds are degenerate" intuition,
and therefore the reverse of where anyone will look.

**The specific rank-deficiency that will be built.** Given that both own- and opponent-pace will
be on the table, the near-certain design is
`{own_pace, opp_pace, differential = own_pace − opp_pace}`. That is *exactly* the three-term
dependency `c = a − b` that `feature_gate.design_rank_report`'s own docstring documents from the
P2 defect: rank 4 of 5, smallest singular value `0.0`, condition `1.4012e15`, largest pairwise
correlation only `0.659`. The pairwise checks pass it; the SVD catches it — **but only if all
three are in the design simultaneously and the per-fold gate is actually called with them.**

**Detection / prevention.** Forbid the differential alongside both components. Report the
head-to-head overlap count per fold as a standing diagnostic so the season-progress dependence is
visible.

### 2.6 The rows most at risk, ranked by fold

Combining the coverage figures: the folds most likely to produce a per-fold identifiability
failure, in order, are **2021** (no level 2 at all; 8 unresolved rows; 28 of the 37 league-prior
rows; smallest season), **2026** (no playoffs; 2 expansion teams; truncated at 2026-07-31; highest
sd at 3.948 and the fold nearest deployment), and **2022-2024** (no level-3 rows at all, so any
league-prior treatment is untrainable there).

---

## 3. Comparison-parity risks

### 3.1 What K0 must be, exactly — and why the packet's own headline reading is misleading here

The incumbent is an unfitted deterministic formula: no intercept, no coefficients, no training
rows, no penalty. Everything a fitted challenger gets *before it uses a single substantive
feature*:

1. a free intercept;
2. a free **slope** on the incumbent's own estimate — i.e. shrinkage of the trailing mean toward a
   fitted constant, which the incumbent structurally cannot do (its window is explicitly
   "UNWEIGHTED and UNSHRUNK");
3. free **stratum re-centering** if any level/support indicator is admitted.

The packet's `bias_variance.reading` says squared bias is 0.19% of MSE and *"a better point
estimate must reduce dispersion, not re-centre."* **That statement is true pooled and dangerously
misleading as a parity statement**, because the stratum biases are large and of opposite signs, so
they cancel in the pool:

| stratum | n | bias |
|---|---|---|
| `team_window_prior_season` | 183 | **−2.845** |
| `game_no_in_season` 1-3 | 228 | **−2.175** |
| `days_rest` 7+ (38% season openers) | 162 | −1.435 |
| support `>10` (all level 3) | 23 | −1.113 |
| support `3-4` | 156 | **+1.342** |
| support `5-9` | 390 | **+1.147** |
| `game_no_in_season` 7-10 | 304 | +1.142 |

A challenger with an intercept plus a three-level `pace_level` dummy removes −2.845 on 183 rows
and roughly +1.1 on ~550 rows **with zero substantive features**. Given the reference case
(`comparison_gate.REFERENCE_CASE`: a free intercept alone was worth +0.00326 team MAE, *"the same
magnitude as the effects being hunted"*), re-centering of this size will dominate anything the
features do.

**Therefore K0 must be:** the challenger's identical pipeline — identical folds, identical
evaluation rows, identical link, offset, clipping, preprocessing, missing-value handling,
aggregation and post-processing — whose only regressor is **the incumbent's own
`team_pace_estimate` / `projected_team_off_possessions`**, fitted with the **same intercept
treatment and the same penalty treatment** as the challenger. That is a *free-recalibration-of-the-
incumbent* control.

**K0 must NOT be intercept-only.** An intercept-only K0 leaves the entire slope/shrinkage gain
(item 2 above) to be credited to the challenger's features, which is the P2 defect in a new
costume.

**And the task card must decide, in writing, before any fit, whether the `pace_level` /
support re-centering belongs to K0 or to the challenger.** If it is part of the hypothesis, it is
a declared substantive feature and sits with the challenger. If it is not, it belongs in K0. There
is no third option, and choosing after seeing results is selection.

**Do existing contracts catch it?** **Only if the author declares honestly.**
`comparison_gate.k0_findings` enforces `k0.n_substantive_features == 0`, but "substantive" is the
author's own label on a free-text tuple. Nothing prevents declaring the incumbent's own output as
non-substantive in K0 — which is correct — or, equally, declaring a `pace_level` dummy as
non-substantive, which would be a silent theft. **The declaration is the control; it must be
adjudicated in the task card, not at fit time.**

### 3.2 `pipeline_id` is asserted, not demonstrated — and it bites hardest here

`comparison_gate.REMAINING_GAPS.pipeline_id_is_asserted_not_demonstrated` is live and it matters
specifically in this experiment, because K0 and the challenger differ **only** in a feature list.
The natural implementation is a config flag, and the natural bug is a "no substantive features"
short-circuit that skips a standardisation step, a clipping step, or the symmetrisation step
(§3.4) that the challenger performs. `pipeline_id` will be identical because it is a string, and
Layer A will report CLEAN.

**Prevention available now without building the digest infrastructure:** require K0 and the
challenger to be produced by the *same invocation* of the *same script* in the same process, with
the feature list as the only differing argument, and record the argv/config digest. That is weaker
than producer-source digest binding but strictly stronger than a hand-written string.

### 3.3 Layer B adjudication will decay into boilerplate — and the one that is not boilerplate

Against an unfitted formula, `intercept_treatment`, `penalty_treatment` and `training_rows`
mismatch by construction, and `LAYER_B_REASON_CODES` supplies exactly three codes
(`incumbent_has_no_fitted_intercept`, `incumbent_is_unpenalised_by_construction`,
`incumbent_has_no_training_rows`) to wave them through. The module's own docstring warns this is
*"how adjudication decays into boilerplate."* Those three are genuinely structural and will be
granted.

**The one to watch is `calibration_freedom` / `post_processing`.** These must never be inferred
from silence (`comparison_gate` says so explicitly: it is the dimension *"that must never be
inferred from silence"*). Concretely: clipping projected possessions to a plausible band,
rounding, or renormalising is a post-processing step, and if K0 does not do the identical thing,
Layer A blocks — correctly. The dangerous case is §3.4.

### 3.4 The symmetrisation step is a post-processing choice worth more than the features

The incumbent averages the two sides' estimates into one game-level projection
(`build_projected_exposure.py:327-329`). Given that **98.99% of the target variance is game-level**
**[verified, §4.1]**, whether a challenger symmetrises its two per-side predictions to their mean
is not a cosmetic choice — it is a variance-reduction step worth more than most feature effects,
and it is available with **zero** substantive features.

If the challenger symmetrises and K0 does not, the entire gain is a `post_processing` mismatch. If
K0 symmetrises and the challenger does not, the challenger is handicapped. Either way, Layer A
should block on `post_processing`/`calibration_freedom` — **but only if both sides declare it**,
and `UNSPECIFIED` on either side is skipped by `dimension_parity` (line 596) after being flagged
once by `side_findings`. Declare it explicitly, on both sides, in the task card.

### 3.5 `evaluation_rows` is never adjudicable, and there are 8 rows that will tempt someone

`LAYER_B_NON_ADJUDICABLE_DIMENSIONS = {evaluation_rows, chronological_folds}` — no reason code
can excuse a difference. The incumbent emits NaN for 8 team-games (4 games, `pace_resolved` False,
2021). A challenger with a better cold-start fallback will *resolve* them, and resolving 8 rows
the incumbent could not looks like an improvement while actually changing the scored universe.

**Rule to pre-register:** the 8 unresolved team-games are excluded from the scored universe for
all three sides. Any claim about resolving them is a separate, separately-reported result with no
promotion authority. Similarly, if a challenger declines to predict any row, its fallback must be
the incumbent's own value, declared under `fallback_rules`, and identical in K0.

Note also that §1.2 option (c) — restricting to `max_period == 4` — is itself an `evaluation_rows`
decision and must be made *before* any fit for the same reason.

---

## 4. Evaluation risks

### 4.1 The effective sample size is 1491, not 2982

**Mechanism [verified].** `projected_team_off_possessions` is identical for both sides in
**1495 of 1495 games**. The target decomposes exactly as `R_side = game_pace ± spread/2`, and:

- within-game spread `|R_A − R_B|`: mean **0.880**, sd 0.779, median **1.0**, 25th pct **0.0**,
  max 4.0 — so the within-game component has sd ≈ **0.390**, variance ≈ **0.152**;
- between-game variance of `game_pace`: **14.988**;
- **98.99% of the team-game target variance is game-level.**

The two rows per game are near-duplicates. Their residuals differ *only* by `±(R_A − R_B)/2`,
which is exactly 0 for 25% of games.

**How it shows up if undetected.** Every table reports `n = 2982`. Naive standard errors are
understated by ≈√2. A `challenger_vs_k0` gain that reads as "2 sigma" at n=2982 is ≈1.4 sigma at
the true effective n. Across 6-10 variants that is precisely the difference between a result and
nothing. This is the most likely single cause of a false positive in this experiment.

**Two corollaries.** (i) The within-game variance of 0.152 is **irreducible for any game-symmetric
model**, and the incumbent is symmetric. (ii) A variant that predicts *different* values for the
two sides is chasing at most **1%** of the target variance; if it appears to gain more than that
from asymmetry alone, the gain is not coming from asymmetry.

**Detection / prevention.** Cluster every standard error, bootstrap and confidence interval on
`game_id`. Report `n_independent_units = 1491` alongside `n_rows = 2982` in every table. Declare
the clustering unit in the frozen spec.

**Do existing contracts catch it?** **No.** `comparison_gate.uncertainty_block` supplies a slot
per contrast and states *"NO UNCERTAINTY SUPPLIED ... the interval is UNKNOWN, not zero"* when
absent — excellent — but it **never checks that a supplied interval is correct**. An unclustered
SE is accepted verbatim. **New control needed: the clustering unit is part of the frozen spec.**

### 4.2 Multiplicity across 6-10 variants, with a gate whose default margin is zero

**Mechanism.** `comparison_gate.gain_findings` fires `gain_within_free_flexibility` when
`net <= gain_margin`, and `gain_margin` **defaults to 0.0** (`audit_fold`, `audit`). So *any*
positive gain, however small, passes. With 6-10 correlated variants on 1491 independent units and
a reference effect size of 0.00326 team MAE, the max over variants will comfortably exceed zero by
chance.

**Prevention.** (a) Pre-declare **one** primary variant and **one** primary metric; all others are
secondary with no promotion authority. (b) Set `gain_margin` explicitly to a pre-declared,
defensible value rather than accepting 0.0. (c) Pre-declare the decision rule as a *number*, not
as "beats K0". (d) If all 6-10 are to be reported, pre-declare the multiplicity adjustment.

**Existing contracts:** `comparison_gate` has **no multiplicity control of any kind**. It audits
one comparison at a time and has no concept of a family. **New control needed.**

### 4.3 Selection on the evaluation period, and an unaudited consolidation

Fold sizes (team-games): 2021 → 418, 2022 → 478, 2023 → 520, 2024 → 524, 2025 → 620, 2026 → 430.
2026 is 14% of a row-weighted pool but is the only fold that resembles deployment, and it is the
fold with the highest sd (3.948), no playoffs, and two expansion teams. Which of "row-weighted
pool", "fold-mean", or "2026 only" is the headline changes the answer.

**Mechanism.** `comparison_gate.audit` computes consolidated gains from the manifest's
`consolidated` block, which the **author supplies**. The gate never checks that the consolidated
number is a defensible aggregation of the per-fold numbers. A challenger that wins 3 of 6 folds
with a positive consolidated number will pass every check in the module.

**Prevention.** Pre-declare the aggregation rule. Require the per-fold table in the report
alongside the consolidated number (the manifest structure already supports this; requiring it in
the *report* is the addition). Require a sign-consistency statement: how many folds the challenger
wins, stated as a number.

### 4.4 Possession MAE and downstream turnover MAE are different objectives and can diverge

**Mechanism.** The propagation weight is the team turnover rate: mean 0.177, sd 0.049, p05 0.101,
p95 0.260 — a **~2.6× spread** across rows. A variant that concentrates its possession improvement
on low-rate teams delivers less downstream benefit than a variant with a *worse* possession MAE
that improves high-rate teams. The rank ordering of 6-10 variants can differ between the two
metrics, and reporting whichever is favourable is selection.

Two further cautions. (i) The packet's `mean_abs_propagated = 0.51744` uses the **realised
(oracle) rate**, not Arm D's rate. It is a floor, not a forecast, and must not be quoted as the
expected downstream effect. (ii) It is computed on the regulation-equivalent basis and therefore
carries the §1.2 units defect.

**Prevention.** Pre-declare the **downstream turnover-team MAE as the primary metric** — it is
what the experiment claims — and possession MAE as secondary with no promotion authority. Require
the propagation to be reported by rate decile so a rate-weighted reshuffle is visible rather than
netting out.

### 4.5 Small-n strata invite noise-mining

The strata most likely to be offered as "where the improvement comes from", with their effective
(game-clustered) n roughly halved:

| stratum | rows | ≈ independent games |
|---|---|---|
| `league_prior_all` | 37 | ~19 |
| support `>10` | 23 | ~12 |
| level 3 in 2025 | 3 | ~2 |
| level 3 in 2026 | 6 | ~3 |
| `max_period == 8` | 2 | 1 |

**Prevention.** Pre-declare a minimum effective n (in independent games) below which no stratum
result may be reported as a finding. And **`by_overtime` must not be a reported result stratum at
all** — OT status is post-cutoff, and reporting it is what invites the §1.1 "fix".

---

## 5. Category A / Category B

### Category A — diagnostics and controls that are testable NOW

| # | Control | Closes | Cost |
|---|---|---|---|
| A1 | League-to-date value must be **constant within `game_date`** and equal the mean over strictly-earlier dates | §1.3 same-day leak | 2 assertions |
| A2 | `max(history.game_date) < target.game_date` AND `target.game_id ∉ history.game_id`, asserted at **both** the `team_pace_estimate` level and the assembled game-projection level | §1.4 opponent-history boundary + shared-projection amplifier | 2 assertions |
| A3 | **Date-shift placebo**: rebuild with history dates +1 day; rows whose window boundary crosses must change | §1.3, §1.4 — catches a boundary that is not being read | 1 rebuild |
| A4 | **Future-blind rebuild**: recompute the artifact from a frame truncated at each fold cutoff and assert byte-equality of in-fold projections against the full-data build | The strongest available cutoff test; closes `cutoff_validity_asserted` for *this* artifact | 1 build per fold |
| A5 | **Units assertion** binding the predicted possession scale to Arm D's denominator, checked specifically on the 132 OT team-games | §1.2 — a parity gate cannot see a shared error | 1 assertion |
| A6 | Cluster all SEs/CIs/bootstraps on `game_id`; report `n_independent_units = 1491` beside `n_rows = 2982` | §4.1 | spec text |
| A7 | Per-fold zero-variance pre-check for the four named columns, with the §4 fallback **frozen in the card** with numeric triggers | §2.3 — the gate blocks, it does not rescue | spec text |
| A8 | Corrected `game_no_in_season` (from the `game_id` sequence) and `days_rest` grouped by `(team_id, season)` over the **full** frame; plus a positive assertion that `pace_level > 1 ⟺ game_no ≤ 3` on 100% of rows | §1.6, §2.1 | 1 rebuild of 2 columns |
| A9 | **K0 definition and `gain_margin` recorded before any fit** (§3.1, §4.2), including the explicit ruling on where stratum re-centering sits | §3.1 — the decision most likely to determine the verdict | spec text |
| A10 | Split `n_history_games` into `n_team_history_games` and `n_league_prior_games` | §2.2 — a semantic error no gate can see | 1 column |
| A11 | Report head-to-head window overlap per fold as a standing diagnostic (50.1% pooled) | §2.5 — the collinearity grows within a season | 1 diagnostic |
| A12 | Declare `post_processing` and `calibration_freedom` explicitly on **all three** sides, naming whether the two sides of a game are symmetrised | §3.4 — `UNSPECIFIED` is skipped by `dimension_parity` | spec text |
| A13 | Exclude the 8 unresolved team-games from the scored universe for all three sides; any resolution of them is a separate result | §3.5 — `evaluation_rows` is never adjudicable | spec text |

A4 deserves emphasis. It is the only control here that turns `cutoff_valid` from an assertion into
a verified property *for this artifact*, and it is cheap: the producer already runs end-to-end in
one pass. It does not close the program-wide `cutoff_validity_asserted` gap, but it closes it
where this experiment needs it.

### Category B — verification currently impossible, with missing input

| # | Capability | Missing input | Why it matters | Minimum viable collection | Prospective-only? |
|---|---|---|---|---|---|
| B1 | Cutoff validity **verified from bytes** rather than asserted | No producer in the repository emits a construction receipt. `gate_invocation` says so explicitly and caps such callers at `RAW_PROVENANCE_ASSERTED`, which is **not** a full Stage 1 pass | Every leakage control in §1 currently rests on an author's declaration | `build_projected_exposure.py` emits a `construction_receipt/1` binding input digests, the declared cutoff per row, and a **per-team-game history row-set digest** | **No** — buildable retrospectively |
| B2 | A machine-readable statement of **Arm D's exposure units** | I could not locate one in the read-only scope. `register_turnover_p2.py:159` says "log(projected or realised offensive possessions)", which does not distinguish raw from regulation-equivalent — and the canonical reconciliation is raw **[verified]** | §1.2 cannot be resolved without it; the whole downstream claim rests on it | One `units` field in the Arm D registration, plus the A5 assertion | **No** |
| B3 | Verified `pipeline_id` (K0 provably from the challenger's code path) | `comparison_gate.REMAINING_GAPS` — producer-source digest binding not implemented | §3.2: K0 and challenger differ only in a feature list, so a mislabelled control is the easiest possible mistake | Producers emit source+config+library digests at write time | **No**, but requires producer changes |
| B4 | A genuinely untouched holdout season | All six seasons are inside the artifact; 2026 is truncated at 2026-07-31 against a current date of 2026-08-04 | Every fold has been available during ideation; §4.2/§4.3 selection risk cannot be fully retired by any in-sample device | Freeze the challenger now; score forward on games after 2026-08-04 | **Yes** — the only genuinely clean test available, and it costs nothing but pre-registration |
| B5 | Any personnel signal (injury/availability, coaching, announced lineup) | As the packet records: injury capture covers 2026-07-30..2026-08-04 only; no coaching source exists; no pregame lineup feed | **The adversarial angle the packet does not state:** with no legitimate personnel signal available, every remaining high-yield construction is a schedule or history transform of the target itself, so the pressure toward a realised-box-score lag is maximal. This is a *leakage* risk created by a *coverage* gap | Per the packet | Mostly **yes** |
| B6 | Use of the existing injury feed at all | It begins 2026-07-30, i.e. inside the **2026 evaluation fold** and the final 2 days of a 6-season span | Using it gives the last fold a feature no earlier fold has — a per-fold `schema_mismatch`, not merely a coverage gap. It must be excluded by name, not merely omitted | n/a — exclude explicitly | n/a |
| B7 | Travel / time-zone burden | No venue table exists | The packet lists it; my addition is that `days_rest` as currently defined (§1.6) is *not* a substitute and will be mistaken for one | Static 12-15 team venue table with coordinates | **No** |

---

## 6. Pre-registration checklist — traps the task card must close before any fitting is authorized

Each line is a specific thing that will otherwise be gotten wrong.

**Units and scale**
1. State Arm D's exposure denominator **in units** (raw possessions vs regulation-equivalent). If
   they differ from the pace scale, state which of §1.2(a)/(b)/(c) is chosen. Blocking.
2. State that no target-game `max_period`, `game_minutes`, `is_overtime`, `duration_sec`,
   `period` or `regulation_seconds_remaining` appears anywhere on the prediction path, and bind
   the A5 assertion on the 132 OT rows.

**Cutoff validity**
3. Bind A1 (same-date constancy), A2 (strict inequality at both levels), A3 (date-shift placebo)
   and A4 (future-blind rebuild) as *pre-fit* obligations with named outputs.
4. Forbid `merge_asof` defaults; require `allow_exact_matches=False` or an explicit `<` filter.
5. State that the league prior window, if changed, is defined on strictly-earlier **dates**, and
   that no daily reindex/forward-fill crosses a season boundary.

**Definitions the packet gets wrong**
6. Re-derive `game_no_in_season` from the `game_id` sequence, not a cumcount over a filtered
   frame. **[verified: the packet's version is wrong on 266 of 2982 rows.]**
7. Re-derive `days_rest` grouped by `(team_id, season)` over the full frame, with season openers
   NaN. **[verified: 68 openers currently carry a median 234 days; 61 of the 162 rows in the "7+"
   bucket are openers.]**
8. Split `n_history_games` by unit, or forbid it. **[verified: constant 10 across all of level 2;
   a league count up to 1300 at level 3.]**

**Identifiability**
9. Record the exact dependency `pace_level > 1 ⟺ game_no_in_season ≤ 3` **[verified exact, 2990/2990]**
   and forbid carrying both. Note that the threshold form is invisible to `feature_gate`
   (contract §7.1).
10. Forbid `{own_pace, opp_pace, own_pace − opp_pace}` in one design — the documented `c = a − b`
    defect.
11. Pre-register, with numeric triggers, the §4 fallback for each of the four fold-degenerate
    columns in §2.3 (`pace_level==2` in 2021; `pace_level==3` in 2022/2023/2024; playoffs in 2026;
    expansion-team indicators). A fallback chosen after a fold fails invalidates the arm.
12. State the treatment of the 13th and 15th teams (2025, 2026) if any team-level term is used.

**Comparison parity**
13. Define K0 **exactly** (§3.1): the challenger's identical pipeline with the incumbent's own
    estimate as the sole regressor, same intercept treatment, same penalty treatment. **Not
    intercept-only.**
14. Rule, in writing, whether `pace_level`/support re-centering is a substantive feature
    (challenger) or free flexibility (K0). This decision must precede any fit.
15. Declare `post_processing` and `calibration_freedom` on all three sides, explicitly naming
    whether the two sides of a game are symmetrised to a common value (§3.4).
16. Declare that K0 and the challenger are produced by the same script invocation with the feature
    list as the only differing argument, and record the config digest (§3.2 mitigation).
17. Freeze the scored universe: the 8 unresolved team-games are excluded for all three sides
    (§3.5); if §1.2(c) is chosen, the OT restriction is stated here too.

**Evaluation**
18. Declare `game_id` as the clustering unit; report `n_independent_units = 1491` beside
    `n_rows = 2982` in every table. **[verified: 98.99% of target variance is game-level.]**
19. Name **one** primary variant and **one** primary metric (downstream turnover-team MAE) before
    seeing anything. All other variants are secondary, non-promotable.
20. Set `gain_margin` explicitly; do not accept the 0.0 default.
21. Declare the fold-aggregation rule, and require the per-fold win count in the report, not only
    the consolidated number.
22. Declare a minimum effective n (in independent games) below which no stratum may be reported as
    a finding; exclude `went_ot` as a result stratum entirely.
23. State that `mean_abs_propagated = 0.51744` is an oracle-rate, reg-equivalent-basis floor and
    may not be quoted as an expected effect size.

**Standing**
24. Record that a passing `feature_gate` record is necessary and never sufficient
    (`GATE_INVOCATION_CONTRACT.md` §7), and that §7.1 (nonlinear/threshold dependency), §7.2
    (comparison properties) and §7.3 (construction-time provenance) are all *live* in this
    experiment — items 2, 9 and 13 respectively sit in those three blind spots.

---

## 7. What I would expect to see if a leak is present

Recorded so the pattern is recognisable rather than rationalised after the fact.

- An improvement concentrated on the 132 OT rows → §1.1.
- A small, uniform improvement across all rows with no stratum structure → §1.3 same-day leak.
- A large improvement on rows where the two teams have met before, scaling with the number of
  head-to-head meetings → §1.4 `<=` boundary.
- A challenger whose `challenger_vs_k0` is large while `k0_vs_incumbent` is near zero, in a
  program whose reference case is that `k0_vs_incumbent` was the *whole* effect → suspect that K0
  is not the challenger's pipeline (§3.2), or that K0 was defined too weakly (§3.1).
- Improvement that appears in the pooled number and in 2-3 folds but reverses in 2021 or 2026 →
  §2.3 fold degeneracy, or §4.3 aggregation.
- Any result whose significance rests on n = 2982 → §4.1.
