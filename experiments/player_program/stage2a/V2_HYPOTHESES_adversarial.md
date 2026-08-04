# V2 — ADVERSARIAL LEAKAGE, IDENTIFIABILITY AND EVALUATION REVIEW

**Target:** `TEAM_POSSESSION_PRIOR_V2`, Stage 2A.
**Role of this document:** to state what will go wrong *before* anything is registered. It proposes
no arm, ranks no hypothesis, and commits to nothing. Where it names a control, the control is a
falsification device, not a candidate.

**Nothing was fitted. Nothing was scored. No accuracy number was computed.**

---

## 0. Evidence base and provenance of every number below

**Frozen packet.** `experiments/player_program/stage2a/EVIDENCE_PACKET_V2.json`,
sha256 `3a35ae735333c47713d6e7cc4c35c081e4eb07364c71cba744db03709730a32c` — verified before reading.

**Read-only code consulted:** `build_projected_exposure.py`, `run_turnover_p1_universe_fix.py`,
`feature_gate.py`, `comparison_gate.py`, `gate_invocation.py`, `GATE_INVOCATION_CONTRACT.md`.

**Read-only artifact inspection.** Structural and coverage inspection only (schemas, counts,
cross-tabulations, exact algebraic identities). All four artifacts were hashed and match the
packet's `sources` block byte-for-byte:

| artifact | sha256 | matches packet |
|---|---|---|
| `projected_exposure_v1/team_possession_prior_v1.parquet` | `c37c0751…3db18` | yes |
| `possessions_v2/possessions_raw_v2.parquet` | `72008818…15b4a` | yes |
| `turnover_targets_v1/team_turnover_reconciliation_v1.parquet` | `446af162…9baae6e93` | yes |
| `projected_exposure_v1/projected_player_possessions_v1.parquet` | `1f47f1f1…646df50f` | yes |

Also inspected read-only: `data/reference/team_cities.csv`, `data/reference/tip_times.csv`.

Throughout, figures are marked **[P]** if they come from the frozen packet and **[I]** if they come
from my own read-only inspection. No **[I]** figure is an accuracy or model quantity; every one is
a count, a coverage table, a schema fact or an exact algebraic identity.

**Settled rulings I do not relitigate:** the target unit; the permitted/prohibited line on realised
duration; the frozen downstream scorer's raw-turnover pairing; the inference specification
(2,982 rows / 1,491 clusters, game-clustered resampling, shared rows/weights/folds/units); and
`K0_FLAT` diagnostic / `K0_MATCHED` authoritative with the tier-partition rule. Everything below
operates *inside* those rulings and asks where they will be violated by accident.

---

## 1. LEAKAGE SURFACES SPECIFIC TO THIS TARGET AND THIS RULING

The ruling's line is narrow and asymmetric: realised duration is **required** on the outcome side
(the target *is* `n_off_poss × 40 / game_minutes`) and **prohibited** on the feature side. A single
quantity is simultaneously mandatory and forbidden depending on which side of the equals sign it
sits. Every failure below is a case of that quantity migrating across the sign.

### L1 — The target's own denominator re-used as a feature-side normaliser
**Mechanism.** `build_pace` computes `reg_equiv_off_poss = n_off_poss × 40 / game_minutes` where
`game_minutes = 40 + 5·max(0, max_period − 4)`. This is correct for the *history*. The predictable
error is a challenger that recomputes the trailing window on **raw** possessions to "fix overtime
properly", then rescales the resulting estimate by the **target game's** `game_minutes` so that
feature and outcome are "on the same scale". That reads as a units correction, not as leakage. The
packet is explicit that `game_minutes` is an exact overtime indicator; any function of it used
predictively is target leakage.
**How it shows up undetected.** A modest, uniform-looking MAE gain concentrated on 132 team-rows
[P] with a large sign flip in the OT stratum. Because OT rows are 4.4% of the panel, the pooled
gain looks small and plausible rather than anomalous.
**Detection / prevention.** The duration-ablation test, **A1** below. Nothing else catches it: the
feature's correlation with the target will be nowhere near `target_corr_threshold = 0.98`, it will
be finite, non-constant, complete, and full-rank.
**Existing contract?** **No.** `feature_gate.target_derived` fires only at |r| ≥ 0.98.
`GATE_INVOCATION_CONTRACT` §7.3 explicitly disclaims construction-time provenance: "A column
derived from post-cutoff information whose values happen not to correlate above threshold with the
target … passes." A new control is required.

### L2 — `is_overtime` and `period` are one join away, in the same frozen file
**Mechanism.** `possessions_raw_v2` carries [I] `period`, `duration_sec`, `is_overtime`,
`regulation_seconds_remaining`, `end_sec`, `score_diff_offense_end`, `abs_score_diff_start`. Any
challenger that reads this file for *history* has the target game's realised duration in the same
frame. The incumbent avoids this by projecting `max_period`/`game_minutes` out of the emitted
artifact — [I] `team_possession_prior_v1.parquet` carries only
`game_id, team_id, game_date, season, season_type, pace_level, pace_source, n_history_games,
team_pace_estimate, projected_team_off_possessions, pace_resolved`, with **no** duration column.
That protection disappears the moment a feature builder joins `possessions_raw_v2` directly, which
every plausible challenger must do.
**How it shows up.** A `groupby('team_id')` rolling construction that forgets to exclude the target
`game_id` yields a window silently including the target game. The resulting feature correlates with
the target at roughly 1/10 of unity for a 10-game window — far under 0.98 — and passes.
**Detection / prevention.** **A1** (duration ablation) plus **A2** (target-game ablation). Also:
require every window construction to be expressed as a join against a *pre-filtered* history frame
from which the target `game_id` has been physically removed, not as a `shift()` on a sorted frame.
`shift()` is correct only if the sort is total and stable; ties on `game_date` within a team are
broken by `game_id`, and a re-sort elsewhere in the pipeline silently changes which row is "prior".
**Existing contract?** **No.** This is exactly `GATE_INVOCATION_CONTRACT` §7.3.

### L3 — Same-date contamination, and there is no uniformly available tip time
**Mechanism.** The incumbent's league prior is correct and should be the template: `by_date` groups
by `game_date`, then `cumsum().shift(1)` — **strictly earlier dates**, so same-day games are
excluded. A challenger "improving" the league prior to a recent-window mean will naturally write
`.rolling(k).mean()` over a *game-sorted* frame, which includes same-day games that tipped later.
**Why it cannot be repaired with a finer cutoff.** [I] `data/reference/tip_times.csv` exists
(1,219 rows) but covers only **1,219 of the 1,495 contract games**, and **zero of the 209 games in
2021**; 2022 has 180/239. It is derived from an odds feed (`source_table` ∈ {`drive_master`,
`extension`}) and 36 games carry `n_commence_variants > 1` — the scheduled tip *changed*, and the
file records no as-of binding for which variant was knowable when. So sub-day cutoff resolution is
neither complete nor provenance-clean, and **"strictly earlier date" is the only defensible cutoff
for this wave.**
**How it shows up.** On multi-game dates (the WNBA norm) a per-game rolling window uses information
from that day's other games. The effect is small per row and structurally uniform, so it looks like
a genuine model improvement.
**Detection / prevention.** Assert, by construction, that every history aggregate is keyed on
`game_date` strictly less than the target's, never on row position. Testable: recompute each
feature after randomly permuting `game_id` within each `game_date` and assert bit-identity.
**Existing contract?** **No.**

### L4 — Things that *look* cutoff-valid and are not, or are not what they say

| surface | why it looks valid | what is actually wrong |
|---|---|---|
| `n_history_games` | present in the frozen artifact, complete, finite, varying | **Two meanings.** [I] verified: `team_window_same_season` 3–10 (team games), `team_window_prior_season` exactly 10, `league_prior_all` **4–1300 (cumulative *league* games; team support is ZERO)**. The packet withdrew the *stratum* (C2); the **column in the artifact is unchanged**. A shrinkage weight built on it treats the 37 zero-team-support rows as the *best*-supported rows in the panel. Passes every `feature_gate` check. |
| `season_type` | listed cutoff-valid [P]; the label is knowable pregame | Its **provenance** is the realised possession stream — `build_pace` takes it from `p.groupby('game_id').agg(season_type='first')`, and the packet records that `possessions_raw_v2` carries **no capture timestamp at all**. Cutoff validity here is an assertion. Separately, `is_playoffs` has **zero variance in the 2026 fold** [I]: 0 of 430 rows. |
| forward schedule density ("games in next N days", "games remaining") | derived from schedule dates, which the packet marks cutoff-valid | Uses **future** dates. For playoffs those dates do not exist pregame (game 5 exists only if 1–4 split). For 2026 they do not exist **in the artifact**: [I] the panel ends `2026-07-31` mid-season with no playoff rows. Any "fraction of season elapsed" feature is a function of **where the extract was cut**, and is pure artifact in the newest fold. |
| trailing OT rate / OT-corrected window | genuinely lagged, genuinely cutoff-valid | Cutoff-valid, but see **E5**: its only downstream benefit channel is exploiting the documented scorer mismatch. |
| venue / travel / elevation (packet C7, "AVAILABLE — Category A") | static reference table | [I] `team_cities.csv` has 16 rows for a 12–15 team league and **team_id `1611661317` (Phoenix) appears twice** (`PHO` 2021–2024, `PHX` 2025–). A `merge(on='team_id')` without `validate=` **silently duplicates every Phoenix team-game**, breaking the 2,982-row / 1,491-cluster inference specification without raising. `build_projected_exposure` uses `validate="m:1"` throughout; a new feature builder that does not will not fail, it will just be wrong. Also `elevation_ft` is a 16-level near-constant that is mostly a team-identity proxy. |
| `era`, `non_competitive_conservative`, `lineup_class`, `canonical_seq` in `possessions_raw_v2` | present in a frozen input | [I] present; derivation unknown and unrecorded. Any of them could be a whole-panel retrospective classification. Category B (see **B1**). |
| `game_no_in_season` | trivially derivable from dates | Packet C10 is **UNRESOLVED**: a source claims 266 of 2,982 rows wrong; the coordinator measures 0 of 2,990 under a deterministic ordering. **266 rows is larger than the entire level-2 stratum (183).** Until reconciled, no game-number feature may back a registered arm. |
| head-to-head history | intuitively strong | Packet C6 **UNRESOLVED** and explicitly forbids quoting any coverage figure. A H2H feature cannot be motivated by a coverage claim in this wave. |

### L5 — Informative missingness that `feature_gate` is configured not to see
**Mechanism.** The gate's `missingness_informative` branch fires at
|corr(null-mask, target)| ≥ `missingness_corr_threshold = 0.5`, and
`missingness_encodes_outcome` requires the mask to be an *exact* separator of `outcome_mask` (zero
off-diagonal) or a constant target on the missing rows. A mask that is **exactly `season == 2021`**
satisfies none of those: the target varies inside 2021, and the mask is not an outcome indicator.
**The concrete instance already in the repository.** [I] any tip-derived feature is null on **all
209 games of 2021** and 59 of 2022. That null mask is nearly exactly the first chronological fold —
the fold that contains [I] **all 28 early `league_prior_all` rows, all 8 unresolved rows, the
highest OT rate (16/209 = 7.7%)** and [P] the worst by-season MAE (3.13383). Imputing the feature
converts "this is the 2021 fold" into a numeric value, which is the **ws2 shape** the dual-frame
requirement exists for — but the *raw*-frame audit will not block it either, because the mask is
not outcome-encoding.
**Detection / prevention.** Require a per-column, per-fold missingness census with the mask
cross-tabulated against **fold identity**, not only against the outcome. Pre-register that any
column whose null mask is ≥95% explained by a single fold is barred, not imputed.
**Existing contract?** **Partially.** `gate_invocation` §8a forces the raw frame to be audited and
records per-column mask digests, so the mask is *visible*. But no threshold blocks on it. A new
control is needed.

### L6 — What is correct and must not be broken
Stated so that a "fix" does not remove a real protection:
- `build_pace` league prior: `cumsum().shift(1)` over `game_date` — strictly earlier dates. Correct.
- Window selection: `same = [v for (d,s,v) in h if d < r.game_date and s == r.season]` — strict `<`.
  Correct.
- `agg(... n_sides="size", n_unresolved=isna().sum())` with the comment "size(), not count() —
  count() drops NaN and would hide an unresolved side". Correct, and load-bearing: it is why
  unresolved rows come in **pairs** [I] (8 rows = 4 games, both sides, all on 2021-05-14).
- `assert_producer_invariants` blocks `OUTCOME_COLS` from reaching the artifact. Correct, and it is
  the only structural leakage guard in the producer — note that it is a **name blocklist**, so a
  renamed or derived outcome column passes it.

---

## 2. IDENTIFIABILITY RISKS

### I1 — The exact three-term dependency the program has already been bitten by, rebuilt
**[I] Verified exactly, zero deviation, on all resolved rows:**

```
team_pace_estimate(own) + team_pace_estimate(opp)  ==  2 × projected_team_off_possessions
max |deviation| = 0.0
```

This is `c = (a+b)/2` — structurally identical to the P2 defect
(`role_change == proj_minutes_share − trailing_minutes_share`) that
`GATE_INVOCATION_CONTRACT` §2 names as the reason numerical rank is mandatory.

**And the packet's own availability table points a challenger straight at it:** "OPPONENT realised
game_pace over strictly earlier games — cutoff_valid: true — **NOT used by the incumbent**". The
single most obvious challenger in this wave is "add opponent adjustment", and its natural design is
`{own_estimate, opponent_estimate}` with `projected_team_off_possessions` as offset.

**Why the gate will not catch it in the offset form.** [I] measured pairwise correlations:
`corr(own_est, projected) = 0.7738`, `corr(own_est, opp_est) = 0.1977`. Both are far below
`corr_threshold = 0.999`, so `deterministic_transform_of_offset` and `near_collinear` cannot fire.
`design_rank_report` is computed **on the feature columns only** — the offset is not in the SVD —
and `{own_est, opp_est}` is honestly rank 2. **The design is exactly determined by its own offset
and passes every existing check.**
**How it shows up.** The offset supplies zero constraint: `pred = offset + b0 + b1·own + b2·opp`
collapses to `b0 + (0.5+b1)·own + (0.5+b2)·opp`. The "challenger" is a free two-parameter re-fit of
the incumbent's own arithmetic, presented as an opponent adjustment. It will look like new
information and is not. See **P2**.
**Detection / prevention.** Extend the rank check to the **augmented** design `[X | offset]` for
every fold, and block on rank deficiency of the augmented matrix. This is a two-line change in
call-site policy (pass the offset as an extra column to a second `design_rank_report` call) and
requires no modification to `feature_gate.py`.
**Existing contract?** **No** — `feature_gate` audits `X`, not `[X | offset]`.

### I2 — Exact partition aliasing, invisible in continuous form
**[I] Verified over all 2,990 rows** (the packet reports 2,982/2,982 on resolved rows [P]; the
identity also holds on the 8 unresolved):

```
pace_level > 1   ⟺   game_no_in_season <= 3      agreement 2990/2990, zero off-diagonal
```

and, on the 2,762 level-1 rows, **[I] exactly**:

```
n_history_games == min(game_no_in_season − 1, 10)
```

**Consequence.** A design carrying a tier dummy *and* `game_no_in_season` as an **integer** is
deterministically dependent through a threshold and a `min()` — both **nonlinear**, both explicitly
named in `GATE_INVOCATION_CONTRACT` §7.1 as an open gap the gate passes. In *dummy* form the
duplication is caught (r = 1.0); in continuous form it is not. And `n_history_games` is a bounded
ramp of the same underlying variable, so `{tier, game_no, n_history_games}` is one variable in three
costumes, at full numerical rank.
**Detection / prevention.** A pre-registered exact-dependency census over the candidate column set:
for every pair and triple, test exact functional determination (group-by-and-check-constant), not
correlation. Cheap, mechanical, fit-free. See **A3**.
**Existing contract?** **No** — §7.1 concedes it.

### I3 — Per-fold degeneracy: four of six folds, from the incumbent's own structure
Chronological folds nested by season. [I] `pace_source × season`, team-game rows:

| season | `league_prior_all` | `team_window_prior_season` | `team_window_same_season` | unresolved | playoff rows |
|---:|---:|---:|---:|---:|---:|
| 2021 | **28** | **0** | 382 | 8 | 34 |
| 2022 | **0** | 36 | 442 | 0 | 46 |
| 2023 | **0** | 36 | 484 | 0 | 40 |
| 2024 | **0** | 36 | 488 | 0 | 44 |
| 2025 | **3** | 36 | 581 | 0 | 48 |
| 2026 | **6** | 39 | 385 | 0 | **0** |

**Blocking `zero_variance` findings that a per-fold audit will produce, and a pooled audit will
not:**

1. `pace_source == league_prior_all` — **identically zero in the 2022, 2023 and 2024 folds.**
2. `pace_source == team_window_prior_season` — **identically zero in the 2021 fold** (no prior
   season exists in the panel).
3. `is_playoffs` — **identically zero in the 2026 fold** (0 of 430).
4. Any `season_type × tier` interaction — **identically zero panel-wide**: [I] all 212 playoff rows
   are `pace_level == 1` with `n_history_games == 10`.

This is the same shape as the ws3 reference case (`proj_off_poss_share` std `7.8e-09` in the 2022
fold against a clean pooled audit), except **it lands on the tier partition that `K0_MATCHED` is
explicitly authorised to reproduce.** `GATE_INVOCATION_CONTRACT` §4 is unambiguous: a
pooled-healthy / fold-degenerate column must fail for that fold **or** be governed by a fallback
**frozen and registered before any result is visible, with its trigger stated numerically**. There
is no third option and no repair-after-observation.

**The trap in one sentence:** the first fold audit of the authoritative control will block, and the
only compliant response is a fallback that was written down before anyone ran it.

### I4 — The near-degenerate case the gate passes and the bootstrap cannot rescue
[I] The `league_prior_all` stratum is **not one stratum**:

| regime | rows | seasons | `n_history_games` | game clusters |
|---|---:|---|---|---:|
| panel start-up | 28 | 2021-05-15 … 2021-05-28 | 4 – 28 | 20 |
| expansion franchise | 3 | 2025 (Golden State) | 970 – 986 | 3 |
| expansion franchise | 6 | 2026 (Toronto, Portland) | 1280 – 1300 | 6 |

The packet reports this as one stratum, n = 37, MAE 3.90215, sd 4.9035 [P]. **76% of its rows are a
consequence of where the panel begins** — they would not exist if the extract started in 2020 — and
the only operationally recurring instances are **9 rows across the last two folds**.

In the 2025 fold the level-3 dummy has 3 positive rows of 620 (std ≈ 0.07); in 2026, 6 of 430
(std ≈ 0.12). Neither triggers `zero_variance` (std == 0) nor `impossible_scaling` (std < 1e-8).
**The gate passes them cleanly while the coefficient is estimated from 3 and 6 game clusters
respectively.** Under game-clustered resampling of 1,491 clusters, ~5% of draws contain none of the
2025 expansion clusters at all.
**Prevention.** A pre-registered **minimum cluster count per estimated stratum**, enforced at
design time, not at reporting time. Absent one, "expansion-franchise cold start" is a nine-row
finding that will be reported as a mechanism.

### I5 — 97.8% of the target variance is game-level, and the incumbent is exactly symmetric
[P] `game_level_share_of_variance = 0.9778`; `within_game_half_spread_variance = 0.1519`;
`games_with_two_distinct_projections = 0`. [I] confirmed: **1,491 of 1,491 games share a single
projection value across both team-rows.**

Two hard consequences a task card must state as bounds, not discover as results:

- **Any within-game-antisymmetric feature** (`is_home`, own-minus-opponent pace, rest differential,
  travel differential) can address **at most the 0.1519 within-game variance component**. That is
  the ceiling on the entire home/away and opponent-differential family, and it is ~1% of the
  15.27299 target variance [P].
- **Any symmetric (game-level) feature** takes an identical value on both rows of a game. Over
  2,982 rows the design then contains 1,491 exactly duplicated rows. Rank is unaffected — duplicate
  *rows* do not reduce column rank — so `design_rank_report` reports full rank and healthy
  conditioning on what is effectively half the stated sample. The packet's clustered resampling is
  the correct remedy and it is already mandated; the risk is that the **feature gate's** healthy
  report is read as corroborating the row count.

### I6 — The packet's headline bias/variance reading is false on exactly the strata a challenger
will target
[P] pooled: `squared_bias = 0.025335`, `bias_share_of_mse = 0.001874`, and the packet's stated
reading: *"A better point estimate must reduce dispersion, not re-centre."*

That is true pooled and **false on the cold-start strata**. Recomputing `bias² / (bias² + sd²)`
directly from the packet's own published stratum figures:

| stratum [P] | bias | sd | bias share of MSE |
|---|---:|---:|---:|
| `team_window_prior_season` (n=183) | −2.84451 | 3.71408 | **37.0%** |
| season openers (n_rows=76, clusters=41) | −3.47113 | 4.0653 | **42.2%** |
| `team_support 3-4` (n=152) | +1.35075 | 3.72032 | 11.6% |
| overall (n=2982) | +0.15917 | 3.67425 | 0.19% |

**Two adversarial consequences, in opposite directions:**

1. A task card that quotes the packet's `bias_variance.reading` verbatim will be steered *away* from
   the one region where re-centring demonstrably dominates. The sentence needs a scope qualifier.
2. More importantly — **the largest and most measurable defect in the incumbent is precisely the one
   `K0_MATCHED` is authorised to absorb.** The cold-start region is a *level* error on a partition
   that `K0_MATCHED` may carry as architecture. A challenger whose mechanism is a cold-start level
   correction is therefore **dead on arrival against the authoritative control**, however real its
   effect. That is the ruling working as designed, and a task card must acknowledge it **before**
   spending a wave, not after.

Note also that the cold-start region is **not one effect**: [P] rows falling back to prior-season or
league history are **under**-projected (bias −2.84, −3.47), while short-window level-1 rows are
**over**-projected (bias +1.35 at 3–4 games, +1.15 at 5–9). A single monotone "shrink early-season
estimates" term fits the average of two opposite-signed effects and helps neither.

---

## 3. COMPARISON-PARITY RISKS

### P1 — The free-**slope** confound: the P2 defect one derivative up
**This is the most dangerous item in this document.**

`comparison_gate` exists because a fitted challenger carried an unpenalised free *intercept* that
the unfitted incumbent lacked, worth +0.00326 team MAE. The same hole exists for the **slope**, and
this wave walks straight into it.

**Mechanism.** `K0_MATCHED` is the challenger's pipeline with **zero substantive features**. For
parity it will carry the incumbent's projection as the `exposure_offset`. So:

```
K0_MATCHED :  pred = offset + b0                     (offset = projected;  intercept only)
challenger :  pred = offset + b0 + b1·projected  ==  b0 + (1+b1)·projected
```

A challenger whose *only* declared substantive feature is **the incumbent's own output** obtains a
free recalibration **slope** that `K0_MATCHED` does not have. It adds **zero information**, and it
will beat `K0_MATCHED` whenever the incumbent's calibration slope differs from 1.

**And the packet's own numbers say it does.** [P] `var(target) = 15.27299`, variance explained
0.11608. [I] `sd(projected_team_off_possessions) = 1.550`, so `var(projected)/var(target) = 0.157`
against 0.116 explained — consistent with a projection that is somewhat **over-dispersed** relative
to its predictive content. Shrinking it toward the league mean is a one-parameter operation. It is
also *exactly* what the packet's own reading recommends ("reduce dispersion, not re-centre"), so it
will be proposed, and it will be proposed sincerely.

**What the gate does.** `comparison_gate` Layer A compares seventeen dimensions. Challenger and K0
can declare **identical** `exposure_offset` (same definition, same units) and be identical on all
seventeen. The difference lives in `substantive_features`, which is exactly where differences are
*supposed* to live. Layer A passes. `gain_report` computes `challenger_vs_k0 > 0` and
`_headline_judgment` returns **`features_bought_incremental_value` — "FEATURE VALUE DEMONSTRATED
beyond the matched featureless control."**

**The wave would certify pure recalibration as a feature, in the module built to prevent exactly
that.**

**Prevention.** Pre-register, as a hard rule in the task card: *any function of
`projected_team_off_possessions`, `team_pace_estimate` or `game_pace` declared as a substantive
feature makes the comparison a **recalibration study**, not a feature study.* Such a challenger
requires a control that carries the same recalibration freedom, and its `challenger_vs_k0` against
an intercept-only `K0_MATCHED` may not be reported as feature value. The cleanest formulation:
**K0_MATCHED must carry a free slope on the offset whenever the challenger does.** This is not a
relitigation of the ruling — the ruling governs *tier and fallback partitions*; the offset slope is
a case it does not reach, and the gap must be closed explicitly rather than by silence.

### P2 — Re-fitting the incumbent's frozen constants, declared as "features"
Continuing **I1**: the incumbent's frozen constants are `WINDOW_K = 10`, `MIN_HISTORY_M = 3`, the
unweighted window, the 50/50 game-pace symmetrisation, and the 1→2→3 fallback ladder [P]. A
challenger that declares `{own_estimate, opponent_estimate, tier dummies, n_history_games}` as
substantive features is not adding information — it is **re-estimating four frozen constants**. K0
genuinely lacks those columns, so Layer A blesses it and the decision table reports feature value.

**`K0_MATCHED` as specified cannot distinguish "new information" from "re-fit of the incumbent's own
arithmetic."** That distinction is the entire scientific content of Stage 2.

**Proposed additional control (diagnostic only, cannot overturn `K0_MATCHED`):** `K0_RECONSTRUCTION`
— the challenger's pipeline carrying **only** algebraic components of the incumbent's own frozen
output and nothing external. Then `challenger_vs_K0_RECONSTRUCTION` isolates genuinely new
information. This stands in the same relation to `K0_MATCHED` that `K0_FLAT` does: it quantifies a
confound, it does not adjudicate. Pre-register it as non-authoritative so it cannot become a
post-hoc tiebreaker.

### P3 — What `K0_MATCHED` must contain, and how to PROVE it stayed matched
The ruling fixes the *policy*: identical pipeline, folds, offsets, fallback tiers, switching rules
and estimation flexibility; zero contextual predictors; a tier partition only where it reproduces
architecture already in the incumbent or challenger path. **Nothing in the codebase enforces any of
it.** `comparison_gate.k0_findings` checks `k0.n_substantive_features > 0` — where
`substantive_features` is *a tuple of strings the author writes down* — and compares `pipeline_id`,
which the module's own `REMAINING_GAPS` states is "ASSERTED, NOT DEMONSTRATED".

So the honest answer to *"how would you prove it?"* is: **you cannot, from declarations.** Four
things can be proven from bytes, all implementable now:

**(a) Column-subset proof.** Require `K0_columns ⊂ challenger_columns` with the set difference
**exactly equal** to the declared `substantive_features`. `gate_invocation` already emits
`feature_order_digest` and `feature_name_membership_digest` per fold; this is a set comparison over
existing digests. If K0's column set is not a subset, K0 is not "the challenger with the features
removed", whatever the declaration says.

**(b) Producer-source digest binding — the gap is closable *for this wave*.**
`comparison_gate.REMAINING_GAPS` says the fix requires producers to emit digests, "none of which is
independently testable from inside this module". But `construction_receipt.py` exists and
`gate_invocation` already **reads a `construction_receipt/1` from disk and re-derives every digest
in it** — that is the only route to `IDENTITY_VERIFIED` / `TRANSFORMATION_VERIFIED`. Therefore:
make the Stage 2B fit harness the single producer of **both** the challenger and the K0 artifacts,
emit one construction receipt per fit, and set `pipeline_id` **to that receipt's binding digest**.
Two artifacts produced by the same code path then carry the same digest as a matter of arithmetic,
not authorship. This does not close the gap globally; it closes it for this wave, which is what is
needed.

**(c) Call-shape proof.** Require K0 to be produced by the *same function call* with
`features=[]` as the only differing argument, and record the resolved argument set in the
construction receipt. A separately written control is the failure mode
`k0_not_from_challenger_pipeline` names and cannot detect.

**(d) The absorption diagnostic — how you detect quiet absorption after the fact.**
Decompose `k0_vs_incumbent` by `pace_level` and by season-opener status, per fold. If K0's advantage
over the frozen incumbent is concentrated on the **228 tier>1 rows** [I] rather than spread over the
2,762 level-1 rows, then the tier partition is doing **substantive** work inside the control, and
that must appear in the decision table as a disclosed quantity rather than as an unexamined design
choice. Pre-register the threshold (e.g. "if >50% of `k0_vs_incumbent` originates in tier>1 rows,
the tier partition is declared substantive and the challenger's `challenger_vs_k0` is reported with
that disclosure attached"). Decide the threshold before seeing a number.

**Why both directions are live.** The packet argues that omitting the tier structure lets an
intercept-plus-tier-dummy challenger beat a straw control. True. But **I6** shows the converse is
equally live: the tier partition carries a bias of −2.84 on 183 rows and −3.47 on 76 rows, which is
real predictive content, so including it in K0 kills any cold-start challenger outright. **The
ruling as written does not determine which of these two the wave is doing**, and the determination
must be made **per challenger, before fitting**, not once for the wave.

### P4 — Structural parity items specific to this target
- **Symmetry.** The incumbent emits one number per game. An asymmetric challenger emits two. The
  producer's arithmetic would carry this correctly (`pair` merge takes the *opponent row's* value,
  and `assert_producer_invariants`' home/away reconciliation compares `dfn_a` to `off_b`), but the
  registered receipt statement `possession_accounting.off_equals_def_by_construction: True` and its
  stated rationale ("the pace estimate is symmetric, so a player's projected offensive and defensive
  possessions are equal") become **false**. An asymmetric challenger therefore invalidates a claim
  bound into the registered downstream artifact's receipt. That is a registration consequence a task
  card proposing home/away or opponent adjustment will not have noticed.
- **`prediction_universe` and the 8 unresolved rows.** [I] The 8 unresolved rows are 4 games on
  2021-05-14, both sides unresolved together. A challenger with a *different* fallback ladder may
  resolve them, changing `prediction_universe` and `evaluation_rows`. `evaluation_rows` is in
  `LAYER_B_NON_ADJUDICABLE_DIMENSIONS` — **never adjudicable on either layer**. So a challenger that
  resolves more rows than the incumbent cannot be compared to it at all unless the evaluation set is
  fixed to the 2,982 intersection in advance. Pre-register the intersection.
- **`companion_components`.** The downstream path binds a companion rate with
  `TEAM_MIN_PRIOR_TEAM_GAMES` support, and `run_turnover_p1_universe_fix` records
  `total_turnover_mae_uses_the_same_team_games_for_every_arm: True` and
  `frozen_before_results: True`. Any Stage 2 challenger that changes exposure must inherit that
  frozen companion unchanged, or Layer A's `companion_components` dimension mismatches.

---

## 4. EVALUATION RISKS

### E1 — Multiplicity, with no pre-registered effect size anywhere
The packet supplies strata for season (6), pace level (3), season type (2), overtime (2), days rest
(5), team support (3), season openers (1), plus per-fold reporting and three contrasts per
comparison. A wave of even four challengers generates a few hundred reportable numbers.

**And there is no minimum effect of interest for possession MAE anywhere in the evidence.** The only
calibrated magnitude in the entire program is the **+0.00326 free-flexibility gain on operational
*team turnover* MAE** — a different metric on a different scale. It cannot be transferred to
possession MAE by assertion.

**A magnitude anchor can be derived from the packet's own arithmetic** (this is arithmetic on
published figures, not a fit, and it is an **upper bound**): [P] mean |propagated turnover error|
attributable to possession mis-projection = 0.51744 turnovers per team-game, holding the rate fixed.
A fractional reduction *f* in possession error propagates to at most `f × 0.51744` turnovers.

| possession MAE improvement | ≈ upper-bound downstream turnover MAE effect | vs. the 0.00326 confound |
|---:|---:|---:|
| 1% (≈ 0.029 poss) | ≈ 0.0052 | **1.6× — inside the known confound's magnitude** |
| 2% (≈ 0.058 poss) | ≈ 0.0103 | 3.2× |
| 5% (≈ 0.145 poss) | ≈ 0.0259 | 7.9× |

**Consequence to pre-register:** any possession-MAE improvement below roughly 1–2% is
**downstream-indistinguishable** from the free-intercept confound the program has already been
burned by. A numeric MED on possession MAE must be written into the task card *before* fitting, or
every verdict becomes a post-hoc judgement about whether a number feels large.

### E2 — Selection on the evaluation period; the newest fold is the least representative
[I] Structural facts about the 2026 fold: **430 rows / 215 games; zero playoff rows; 15 distinct
teams (up from 12); two brand-new franchises; 45 `game_no ≤ 3` rows — the highest cold-start density
in the panel; panel truncated at 2026-07-31, four days before the present, mid-season.** [P] Its MAE
(3.12151) is the second worst of six, behind only 2021 (3.13383) — the *other* structurally
anomalous fold.

**The two worst folds are the first and the last, and both are anomalous for structural reasons
rather than for modelling reasons.** A challenger that helps in 2021 and 2026 will look like a
panel-level improvement while helping only where composition is unlike everywhere else.

Meanwhile the newest *phenomenon* in the panel — expansion franchises — appears in **9 rows across
those same two most-recent folds** [I]. It is unfalsifiable within this panel and is exactly what an
operator will care about most.

**Prevention.** Pre-register the aggregation rule (pooled vs. per-fold vs. most-recent-fold) and the
fold-weighting **before** any fit. State explicitly whether 2026 is an evaluation fold at all given
that it is truncated mid-season.

### E3 — The OT stratum's apparent advantage is a plausible units artifact
[P] OT rows: MAE 2.36744, sd 3.07361 (n=132). Non-OT: MAE 2.92806, sd 3.69921 (n=2,850).

Read naively, "the incumbent is *better* on overtime games." But the regulation-equivalent transform
divides the **realised** side by `game_minutes` while the projection is unaffected: for a
single-OT game the realised value and all its deviations are multiplied by `40/45 = 0.889`. The
observed sd ratio is `3.074 / 3.699 = 0.831`, which is close to that compression factor.

**This is a candidate mechanism that must be ruled out before the OT stratum is read as
substantive.** It is testable without fitting anything: compare the dispersion of the *realised*
regulation-equivalent target on OT versus non-OT rows, and compare it to the pure scale factor
implied by each game's `game_minutes`. [I] the OT population is not homogeneous — 60 games at
`max_period = 5`, 5 at 6, 1 at 8 — so the compression factor varies across the stratum.

### E4 — OT frequency trends across the panel, so OT-sensitive gains are composition-weighted
[I] overtime games per season: **2021: 16/209 (7.7%), 2022: 12/239, 2023: 11/260, 2024: 10/262,
2025: 8/310 (2.6%), 2026: 9/215 (4.2%)** — total 66 of 1,495, matching the packet's 66/1,495 [P].
By season type: 10 of 106 playoff games, 56 of 1,389 regular-season games.

An OT-handling challenger's leverage therefore varies by a factor of three across folds: 32 OT
team-rows in 2021 versus 16 in 2025. A pooled figure averages that away; a most-recent-fold figure
lands on 18. Report per fold, with the OT row count alongside every OT-conditioned number.

### E5 — The documented scorer mismatch is an *exploitable* channel, not merely a caveat
[P] `run_turnover_p1_universe_fix.py:149` pairs regulation-equivalent exposure with **RAW full-game
turnovers**. On the 132 OT team-rows: `bias_vs_RAW = −10.5151`, `mae_vs_RAW = 10.51782` (against
`mae_vs_reg_equiv = 2.36744`). The exposure understates raw possessions by ≈11 per OT team-game,
so downstream turnovers are understated by ≈11 × 0.177 ≈ 1.9.

**The exploit.** *Any* challenger that inflates its possession projection reduces downstream RAW
turnover MAE on OT rows and increases it on the other 2,850. Uniform inflation loses on net (4.4% of
rows). But **inflation targeted at rows correlated with OT propensity wins**. And a team's trailing
OT rate is a perfectly cutoff-valid lagged feature that will pass every gate in the repository.

**The result would be a challenger that improves the downstream operational metric while making the
primary regulation-equivalent possession MAE *worse*, purely by exploiting a documented accounting
mismatch.** The packet already requires OT/non-OT downstream diagnostics to be reported separately
and forbids overturning the primary decision on them — necessary but not sufficient, because it does
not forbid the *feature*.

**Prevention, and it is an ordering constraint:** the primary regulation-equivalent possession
verdict must be **computed, receipted and frozen before any downstream turnover number is computed
at all.** Otherwise the downstream figure becomes an unregistered tiebreaker. Additionally,
pre-register that any challenger whose primary possession MAE worsens is rejected regardless of its
downstream figure.

### E6 — Improving possession MAE ≠ improving turnover MAE, and the rate varies 2.5×
[P] implied team turnover rate: mean 0.17733, p05 0.1013, p50 0.175, p95 0.2597. The downstream
value of a possession-error reduction therefore varies by **a factor of 2.5** across rows. A
challenger that improves possession MAE on low-rate rows buys almost nothing downstream; the same
improvement on high-rate rows buys 2.5× more. The two metrics can move in opposite directions with
no defect present anywhere.
**Prevention.** Report the possession-error improvement **weighted by the realised team turnover
rate** as a separate diagnostic, so the two metrics' divergence is a measured quantity rather than
a surprise. Note that this diagnostic uses a realised rate and is therefore a **post-hoc
attribution**, not a predictive path — it must be labelled as such and must never enter a feature
matrix.

### E7 — Small-n strata that will invite noise-mining, with cluster counts

| stratum | rows [P] | game clusters [P] | why it will attract a challenger |
|---|---:|---:|---|
| season openers | 76 | **41** | MAE 4.26806, bias −3.47113 — the most extreme figures in the packet. ≈7 clusters per season; **not estimable per fold**. |
| `league_prior_all` | 37 | 26 | See **I4** — two incompatible regimes, and only 9 rows are operationally recurring. |
| `days_rest 0-1 (b2b)` | 89 | 84 | Intuitively compelling. |
| `days_rest 7+` | 101 | 80 | Post-correction, no longer a rest effect. |
| overtime | 132 | 66 | See **E3**, **E5**. |
| expansion franchises | **9** [I] | **9** [I] | The only genuinely novel structure in the panel. |

**And a finding that must be stated so it is not quietly reversed:** the packet's **corrected**
days-rest table is, read adversarially, evidence of **no rest effect at all**. [P] MAE 2.98238 (7+),
2.97065 (b2b), 2.95031 (3), 2.94842 (4-6) — a spread of 0.034 across four strata — with only the
modal `2` stratum (n=1,432, MAE 2.77953) lower, and that stratum is nearly half the panel so it sits
close to the overall mean by construction. Pre-register this reading, so that a rest term cannot
later be presented as motivated by the packet.

### E8 — Two denominators inside one packet block
[P] `dependence_structure` states `game_clusters: 1491` and, three lines later,
`games_with_one_shared_projection: 1495`. [I] the difference is exactly the 4 unresolved games
(2,990 − 8 = 2,982 rows; 1,495 − 4 = 1,491 games). Both figures are correct; they are over
**different universes**. A task card that quotes them side by side is quoting two populations as
one. Fix the wording, not the numbers.

---

## 5. CATEGORY A — TESTABLE NOW (no fitting, no scoring)

**A1 — Duration-ablation test. The single most valuable new control.**
Rebuild every candidate feature against a perturbed copy of `possessions_raw_v2` in which the
**target game's** overtime periods are deleted (equivalently, `max_period` forced to 4), leaving all
history untouched. **Assert bit-identity of every feature, every fallback decision and every
prediction.** Anything that moves is a function of the target game's realised duration and violates
the ruling.
*Why it works:* it converts the ruling's permitted/prohibited line into a byte-level property rather
than an assertion, and it attacks the standing gap directly — `cutoff_valid` is an ASSERTION bound
into a receipt, not verified from bytes. *Why it is cheap:* `build_projected_exposure.build_frames`
already exists precisely so "the validator calls it with the module's input paths patched to
perturbed copies, so the perturbation tests exercise the REAL producer rather than a
re-implementation of it." The machinery is built.
*Catches:* **L1**, **L2**. *Existing contract:* none.

**A2 — Target-game ablation (generalisation of A1).**
Replace every realised column of the **target** team-game with a sentinel, rebuild, assert
bit-identity. Any feature that moves is reading the target game. This mechanically closes the whole
"the builder accidentally touched the target row" class. It cannot prove an *input artifact* was
built without lookahead — that is **B1**.

**A3 — Exact-dependency census over the candidate column set.**
For every pair and every triple of candidate columns, test **exact functional determination**
(group-and-check-constant), not correlation. Already known to fire [I]: `pace_level > 1` ⟺
`game_no ≤ 3` (2990/2990); `n_history_games == min(game_no − 1, 10)` on level-1 rows;
`own_est + opp_est == 2 × projected` (max deviation 0.0). *Catches:* **I1**, **I2** — both of which
the linear gate provably misses (§7.1).

**A4 — Augmented-design rank check `[X | offset]`, per fold.**
A second `design_rank_report` call with the offset appended as a column, blocking on rank
deficiency. *Catches:* **I1** in its offset form, which is otherwise invisible. Requires no change
to `feature_gate.py` — only a call-site policy.

**A5 — Per-fold zero-variance and cluster-count census, run BEFORE any fit and published.**
Run `feature_gate.audit` per season fold over the candidate columns and publish the result as a
**pre-fit deliverable**. It will block; the blocks listed in **I3** are already known. The point is
that the frozen fallback (§4) gets written against a **known** list rather than improvised after the
first failure. Pair it with a per-fold, per-stratum **game-cluster** census and a pre-registered
cluster minimum (**I4**).

**A6 — Symmetric/antisymmetric decomposition of every candidate feature.**
For each column report within-game half-spread variance and between-game variance. A feature with
≈0 within-game variance can only address the 0.1519 component; one with ≈0 between-game variance is
orthogonal to 97.8% of the target. Publishes the ceiling on each feature family before anyone fits.
*Catches:* **I5**.

**A7 — Same-date permutation invariance.**
Permute `game_id` within each `game_date`, rebuild every history feature, assert bit-identity.
*Catches:* **L3**, and it is the only available test given that tip times cover 1,219 of 1,495 games
and none of 2021.

**A8 — Extract-boundary invariance.**
Recompute every candidate feature on the panel truncated at each season's last date minus 14 days;
assert values are unchanged for surviving rows. *Catches:* the "fraction of season elapsed" /
"games remaining" family (**L4**), which is pure artifact in the 2026 fold.

**A9 — Join-cardinality assertions on every reference table.**
`validate=` on every merge; explicit season-aware join keys for `team_cities.csv` (the duplicated
Phoenix `team_id` [I]); assert the row count is exactly 2,990 and the cluster count exactly 1,495
after every join. *Catches:* the silent row-duplication in **L4**.

**A10 — Two-meaning guard on `n_history_games`.**
Assert that any use is either restricted to level-1/2 rows or explicitly recoded so that level-3
team support is **0**. The packet corrected the stratum; the artifact column is unchanged.

**A11 — Fold-explained missingness census.**
Cross-tabulate every candidate column's null mask against **fold identity**, not only against the
outcome. Pre-register a bar on any column whose mask is ≥95% explained by one fold. *Catches:*
**L5**, which the gate's 0.5 correlation threshold provably will not.

**A12 — Pipeline-identity binding for K0 (P3b) and the column-subset proof (P3a).**
Both implementable now using `construction_receipt.py` and the digests `gate_invocation` already
emits.

**A13 — K0 absorption decomposition (P3d).** Decompose `k0_vs_incumbent` by `pace_level` and
season-opener status per fold, against a threshold fixed in advance.

**A14 — Stratum-level bias/variance decomposition.** The packet publishes it pooled only; **I6**
shows the pooled reading inverts on the cold-start strata. Publish it per stratum before any
hypothesis is written.

---

## 6. CATEGORY B — VERIFICATION CURRENTLY IMPOSSIBLE

**B1 — Lookahead inside `possessions_raw_v2` itself.** [P] it "carries no capture timestamp at
all". [I] it carries `era`, `non_competitive_conservative`, `lineup_class`, `canonical_seq`,
`source_order_differs` — derived columns whose construction is unrecorded, any of which could be a
whole-panel retrospective classification. **A1/A2 cannot reach this**: they verify that *downstream*
features do not touch the target game; they cannot verify that the *input* was built causally.
Needs a producer construction receipt for `possessions_raw_v2`, which does not exist.

**B2 — Point-in-time validity of `master_team`.** [P] ten distinct `observed_time` values in two
bulk windows (2026-07-31 and 2026-08-04) covering game dates from 2021-05-14. Cutoff validity rests
on a **lag** argument only, never a **capture** argument, and revision risk is real and
**unmeasurable** — with a single vintage you cannot detect a retroactive stat correction. Needs a
second-vintage snapshot.

**B3 — `injury_history.csv` date semantics.** [P] availability established (8,340 rows, full
contract span); cutoff validity **not** established, because there is no observation timestamp and
the verdict rests on `date` being an event date rather than a compilation date. Needs the source's
own documentation or a second vintage.

**B4 — Prospective-only families.** Injury/availability feed, announced lineups, market totals: [P]
capture begins 2026-07-30/07-31. Four to six days of a five-season span. These cannot be validated
retrospectively at all, only forward.

**B5 — Head-to-head coverage.** [P] UNRESOLVED; 70.2% vs 85.1% is **not** a denominator difference
(four denominators tested, spanning 85.1–87.4%, with playoffs at 100.0% against the source's 99.1%).
Explicit instruction: no figure may be quoted until independently reproduced with the source.

**B6 — `game_no_in_season` correctness.** [P] UNRESOLVED; a claim of 266 wrong rows versus a
coordinator measurement of 0 of 2,990. Not adopted, not dismissed. 266 rows exceeds the entire
level-2 stratum.

**B7 — Sub-day cutoff resolution.** [I] tip times exist for 1,219 of 1,495 games, **none in 2021**,
derived from an odds feed, with 36 games showing `n_commence_variants > 1` and no as-of binding.
Any claim that a feature is cutoff-valid at sub-day resolution is unverifiable in this wave.

**B8 — `season_type` provenance for the 212 playoff rows.** Sourced from the possession stream,
which has no capture timestamp (B1).

**B9 — Whether the *packet's own availability table* is complete.** [I] `data/reference/tip_times.csv`
is derived from historical odds snapshots (`source_table` ∈ {`drive_master`, `extension`}, 813 + 406
rows, covering 2022–2026), yet the packet's verdict on market data is "UNAVAILABLE HISTORICALLY —
capture begins 2026-07-31" on the basis of `data/odds_capture/`. These are different sources and
there is no literal contradiction, but **a historical odds-snapshot store evidently exists somewhere
in this repository.** Recorded as an observation for the coordinator, **not** as a correction: the
packet is frozen, and resolving this requires the coordinator's own reconciliation with the source.
Flagged because "market odds are unavailable" is currently doing load-bearing work in scoping the
wave.

---

## 7. PRE-REGISTRATION CHECKLIST — traps the task card must close before fitting is authorised

Each line is a trap that is **live now**. None is closed by an existing contract unless stated.

**Leakage**
1. ☐ **A1 duration-ablation** is a gating deliverable, run and receipted **before** any fit. No arm
   proceeds without a bit-identity result.
2. ☐ **A2 target-game ablation** likewise.
3. ☐ Every history aggregate is keyed on `game_date <` the target's, never on row position; proven
   by **A7** same-date permutation invariance.
4. ☐ No feature uses forward schedule dates. Explicitly bar "games remaining", "fraction of season
   elapsed", "days to season end" — proven by **A8**.
5. ☐ `n_history_games` is barred or explicitly recoded (**A10**). State which.
6. ☐ Every reference-table join carries `validate=` and a post-join row/cluster assertion (**A9**).
   Name the Phoenix duplicate-`team_id` case in the card so it cannot be rediscovered as a bug.
7. ☐ Null masks are cross-tabulated against **fold identity** and the ≥95%-single-fold bar is
   applied (**A11**). Name the 2021 tip-time case.
8. ☐ `game_no_in_season` is **not used** until packet C10 is reconciled with its source (**B6**).
9. ☐ No head-to-head coverage figure is quoted (**B5**).

**Identifiability**
10. ☐ **A3 exact-dependency census** published before any design is frozen; the three known exact
    identities are listed in the card by name.
11. ☐ **A4 augmented `[X | offset]` rank check** is mandatory per fold. Without it, the most obvious
    challenger in this wave passes every check while being exactly determined by its own offset.
12. ☐ **A5 per-fold zero-variance census** published pre-fit, and the §4 fallback for
    `league_prior_all` (2022/2023/2024), `team_window_prior_season` (2021) and `is_playoffs` (2026)
    is **frozen and registered with a numeric trigger before any result is visible.** State it as a
    rule, not as a remedy.
13. ☐ A **minimum game-cluster count** per estimated stratum is fixed in advance (**I4**: the
    expansion stratum is 3 clusters in 2025 and 6 in 2026).
14. ☐ **A6** ceilings published: the within-game-antisymmetric family is bounded by the 0.1519
    variance component, i.e. ~1% of target variance.
15. ☐ **A14** stratum-level bias/variance published, and the packet's
    "reduce dispersion, not re-centre" reading is **scope-qualified** — it inverts on the level-2
    (37% bias share) and season-opener (42%) strata.
16. ☐ The card states that the cold-start region contains **two opposite-signed biases** and that a
    monotone shrinkage term is mis-specified for it.

**Comparison parity**
17. ☐ **The free-slope rule (P1) is written into the card as a hard rule.** Any function of
    `projected_team_off_possessions`, `team_pace_estimate` or `game_pace` declared as a substantive
    feature makes the comparison a **recalibration study**; `K0_MATCHED` must then carry the same
    recalibration freedom, or the challenger is barred. **Without this line the wave will certify
    pure recalibration as demonstrated feature value, and `comparison_gate` will print
    "FEATURE VALUE DEMONSTRATED" while it happens.**
18. ☐ The card states, per challenger and **before fitting**, whether the tier partition is
    architecture or feature for that challenger (**P3**), and acknowledges that a cold-start-level
    challenger is **dead on arrival** against a tier-carrying `K0_MATCHED` (**I6**).
19. ☐ **P3a column-subset proof**: `K0_columns ⊂ challenger_columns`, set difference exactly equal
    to the declared `substantive_features`, checked from the digests `gate_invocation` already emits.
20. ☐ **P3b pipeline binding**: one producer for both artifacts; `pipeline_id` = construction-receipt
    binding digest. Closes `comparison_gate.REMAINING_GAPS` **for this wave**.
21. ☐ **P3d absorption threshold** fixed in advance.
22. ☐ `K0_RECONSTRUCTION` registered as a **diagnostic, non-authoritative** control (**P2**), on the
    same footing as `K0_FLAT`, so it cannot become a post-hoc tiebreaker.
23. ☐ `evaluation_rows` fixed to the 2,982-row intersection in advance — it is **never adjudicable**
    on either layer (**P4**).
24. ☐ If any challenger is asymmetric, the card states that
    `possession_accounting.off_equals_def_by_construction` in the downstream registered receipt
    becomes false, and names the registration consequence (**P4**).
25. ☐ The frozen companion component is inherited unchanged (**P4**).

**Evaluation**
26. ☐ A **numeric MED on possession MAE** is registered before fitting (**E1**). The 1–2% anchor is
    offered as a floor: below it, the downstream effect is the same order as the +0.00326 confound.
27. ☐ The aggregation rule — pooled vs. per-fold vs. most-recent — and fold weighting are fixed
    before any fit, with an explicit decision on whether the **truncated, playoff-free, 15-team 2026
    fold** is an evaluation fold at all (**E2**).
28. ☐ **Ordering constraint (E5):** the primary regulation-equivalent possession verdict is computed,
    receipted and **frozen before any downstream turnover number is computed at all.**
29. ☐ Any challenger whose **primary possession MAE worsens** is rejected regardless of its
    downstream turnover figure (**E5**).
30. ☐ Trailing-OT-rate and any OT-propensity feature is either barred or registered with an explicit
    statement that its downstream benefit channel is the documented scorer mismatch (**E5**).
31. ☐ Every OT-conditioned number is reported with its per-fold OT row count (**E4**: 32 rows in 2021
    vs 16 in 2025).
32. ☐ The **E3** units-artifact explanation for the OT stratum's lower MAE is tested and ruled in or
    out before that stratum is cited as evidence of anything.
33. ☐ A turnover-rate-weighted possession-error diagnostic accompanies every possession-MAE claim
    (**E6**), labelled as post-hoc attribution that never enters a feature matrix.
34. ☐ The **days-rest null reading** is pre-registered (**E7**): the corrected table shows a 0.034
    MAE spread across four strata, i.e. no rest effect, and a rest term may not later be presented
    as packet-motivated.
35. ☐ The 1,491 / 1,495 denominator distinction is stated wherever both appear (**E8**).

---

## 8. THE FOUR THINGS MOST LIKELY TO ACTUALLY GO WRONG

Ranked by expected damage, stated plainly:

1. **P1 — the free-slope confound.** A challenger whose only feature is the incumbent's own output
   gets a free recalibration slope `K0_MATCHED` lacks, adds zero information, and is certified
   "FEATURE VALUE DEMONSTRATED" by the module built to prevent exactly this. It is the P2 defect one
   derivative up, and the gate has no dimension for it.
2. **I1 / A4 — the offset-determined design.** `own + opp == 2 × projected` exactly, and every
   pairwise check misses it (0.774 and 0.198 against a 0.999 threshold) because the offset is not in
   the rank matrix. The most obvious challenger in the wave is the exact shape of the P2 defect.
3. **I6 / P3 — the tier partition decides the wave, and nobody has decided it.** The incumbent's
   largest measurable defect is a cold-start *level* error (37% and 42% bias share of MSE) on the
   partition `K0_MATCHED` may absorb. Whether that partition is in or out of the control determines
   the verdict, in opposite directions, and the ruling as written does not settle which.
4. **E5 — the scorer mismatch is exploitable, not merely documented.** A cutoff-valid, gate-passing
   trailing-OT-rate feature improves the downstream operational metric while worsening the primary
   target, purely by arbitraging a −10.5 accounting bias on 132 rows. Only an ordering constraint —
   primary verdict frozen first — prevents it.

---

*No hypothesis is proposed, ranked or endorsed. No arm, control, registry entry or canonical
artifact was created or modified. Nothing was fitted. Nothing was scored.*
