# `asof_invariant_audit_v1` - audit report

*Registered 2026-07-31T16:06:42Z (regime A, primary metric `audit_findings_count`, incumbent
`none_infrastructure_audit`). Read-only audit - no registry write, no `record_evaluation`, no
leaderboard render, no existing experiment script modified. Produced 2026-07-31.*

**Deliverables in this directory:** `BLAST_RADIUS.md` + `blast_radius.csv` (A),
`permutation_audit.csv` + section 3 below (B), `missing_manifests.csv` + section 4 below (C).
**Code:** `asof_invariant.py` (repo root), `tests/test_permutation_integrity.py`,
`tests/test_asof_invariant.py`.

---

## 1. Findings count

| # | finding | severity |
|---|---|---|
| 1 | `joint_differential_v1`'s **clean-season read is itself contaminated** - all three train seasons sit inside the rating table's fit window, so every fitted coefficient and the margin calibration were estimated on contaminated inputs | **new, high** |
| 2 | **A second contaminated artifact**: the zone-map EB shrinkage constants are fit on 2021-2026 and consumed by `w2_integration` to score 2024-2026 | **new, medium** |
| 3 | `joint_differential.PERM_NEAR_NAIVE_TOL = 0.35` is **looser than the defect it was meant to catch** (observed inflation 0.108) - the automated gate would have passed the defective null | **new, medium** |
| 4 | **Seven experiments run no permutation/placebo test at all** and are unfalsified against the chance hypothesis; three of them fit real parameters and claim comparisons against an incumbent | **new, medium** |
| 5 | **Zero of 18 fitted artifacts carry a manifest** - the as-of invariant is unassertable anywhere in the repository today | **new, structural** |
| 6 | `experiments/rapm_multiseason/rapm_v1_*_train2021_26.csv` are fit through 2026 and would contaminate every row of any season they scored; currently unconsumed | **new, latent** |
| 7 | `oracle_availability_bracket_v2` pooled numbers and `clv_transfer_v1` old-era tables inherit the disclosed 2024 contamination | confirmed, previously known |
| 8 | `props_edge_v1`'s registered null is mis-blocked for playoff-scope cells (disclosed in-code, corrected companion null reported) | confirmed, self-disclosed |

**Bottom line for the review question "how far does each problem reach":** the rating-table
problem reaches **one season further than recorded** - into the train window, and therefore into
every fitted parameter of the one experiment that fits on RAPM features. The placebo problem is
**isolated as a defect and systemic as an absence**: exactly one file contains the defective
construction, and it is non-gating and labelled; but seven files have no placebo at all.

---

## 2. Deliverable A - blast radius

Full ledger in `BLAST_RADIUS.md`; machine-readable inventory in `blast_radius.csv` (35
artifact-consumer rows; columns: artifact, producer, fit_window, fit_window_source, consumer,
consumer_experiment_id, scored_seasons, scored_rows, intersects, verdict, reasoning).

Verdict counts: **3 INVALID-PENDING-RECOMPUTATION**, **5 NEEDS-REVIEW**, **27 VALID**.

The headline finding, in one paragraph: `experiments/joint_differential/audit_results.json`
already contains `"train_seasons_inside_fit_window": [2021, 2022, 2023]`. The script computed the
fact and the report did not draw the consequence. Because `joint_differential.py` tunes lambdas
on inner folds inside 2021-2023 (lines 580-588), fits four ridge coefficient vectors on the 610
train games (line 597), and fits the margin calibration `a=0.1153, b=0.9314` on the same games
(lines 605-607) - all against `d_rapm` values drawn from a table fit on 2021-2024 - the
parameters themselves are contaminated. Applying them to 2025-2026 does not launder them. The
"RAPM-clean seasons" numbers (+0.0535, +0.0495) are a measurement of a mis-specified model. The
ablation arm, which excludes `d_rapm` entirely, is unaffected and remains valid.

The second finding: `matchup_overlay.maps_before()` was audited directly rather than trusted. Its
cutoff restriction is real (`matchup_overlay.py:251`, `mask = df["game_date"] < cutoff`) and every
*rate* is recomputed from the pre-cutoff slice. But `w2_integration.py:673` loads the stored
full-sample `k_table` - estimated over 2021-2026 - and passes it into every call, for a run whose
scored seasons are 2024, 2025 and 2026. `matchup_overlay.py:29-30` documents the correct escape
hatch (`k_table=` with train-only estimates); it was not used.

---

## 3. Deliverable B - permutation integrity

Per-file verdicts in `permutation_audit.csv` (16 rows; columns include what is permuted, the
strata, what is refit, what is **not** refit, whether the permutation sits inside the fitting
loop, and evidence line numbers).

### 3.1 Is the defect isolated or systemic?

**The defective construction is isolated to one file: `joint_differential.py`.** No other
permutation implementation in the repository refits a parameter on true targets while refitting
the rest on permuted ones.

Verified in that file at line 732: `a_t, b_t = rr.linfit(pred_sum_tr, y_true_tr)` - the
calibration refit on TRUE train margins, while the ridges above it (lines 726-727) were refit on
permuted ones. It is **non-gating** (`audit3["passed"]` at lines 751-752 reads only `perm_maes`,
the faithful list) and **explicitly labelled** in both the code comment (lines 706-708) and the
report.

The faithful null at line 730 is clean: it refits the ridges *and* the calibration on the
permuted targets. Two carryovers were checked and cleared - the `Standardizer` is fit on features
only, so a Y-permutation leaves it bit-identical; and `d_rapm` is deliberately held fixed because
the null shuffles Y, not X, and re-permuting the feature would construct a different and wrong
null.

### 3.2 The finding the defect exposed: the gate has no teeth

`PERM_NEAR_NAIVE_TOL = 0.35` (`joint_differential.py:125`) lets the null beat naive by up to 0.35
MAE points before the collapse gate fires. The observed defective null beat naive by **0.108**
(11.3005 against 11.4088). Had the true-calibration variant been the null rather than a
diagnostic, **audit 3 would have reported PASS.** The defect was caught by a human reading the
diagnostic line, not by the automated gate. Pinned in
`tests/test_permutation_integrity.py::test_configured_tolerance_is_too_loose`, which fails if the
constant changes without the finding being re-derived. *(Reported, not fixed - modifying
`joint_differential.py` is outside this audit's file boundary.)*

### 3.3 Clean implementations (6)

`feature_lab.py` (`perm_null`, lines 154-181), `interactions_lab.py` Level 2 (`l2_test`, lines
136-220), `crossseason_screen.py` (`perm_null_ms`, lines 190-217), `bios_screen.py` and
`volume_heterogeneity.py` (both delegate to the above, no reimplementation), `pocket_mining.py`
(200 draws per era) and `props_edge.py` (two nulls, 200 draws per season).

All refit every coefficient that could encode the permuted relationship, inside the loop, on the
permuted data. `interactions_lab` is the strongest: it recomputes the permuted side's
standardization fresh each draw (line 195) rather than reusing true-data statistics, and refits
*both* the reference and treatment models.

The two mining files deserve specific credit against the selection-hoisting analogue this audit
was asked to hunt: `pocket_mining` enumerates the full pre-registered cell battery once (lines
737-748) and re-evaluates **every** cell inside each of the 200 draws (lines 768-787), applying
Benjamini-Hochberg afterward. There is no selection step to hoist. `props_edge` follows the same
shape.

Each clean file carries one **MILD-FROZEN-PARAM**: a hyperparameter (candidate alpha, blend
weight, ridge lambda) tuned on true data via inner folds, then frozen and applied *identically*
to both arms. That is the defensible case, not the fatal one, and it is applied consistently -
never refit-in-observed-but-frozen-in-null.

`minutes_twostage.py` is **MILD-FROZEN-PARAM**: a single-draw probe (lines 900-908) that refits
the ridge betas on permuted minutes while reusing `std_b` (fit on X only, therefore identical)
and `lam_b` (CV-tuned, applied to both arms). Defensible; its weakness is power, not validity -
one draw cannot produce a p-value.

`props_edge.py` carries a **different species** of defect, self-disclosed: its registered
within-season block dilutes playoff rows (7.8% of the pool), giving null mean ROI -0.076 for
playoff cells against -0.051 for regular-season ones. That is an exchangeability error, not a
fitted parameter surviving into the null. A corrected within-(season, phase) companion null is
computed and reported alongside, and playoff cells are not headlined.

### 3.4 The systemic problem: seven experiments have no placebo at all

`bottomup_3pt.py`, `w2_integration.py`, `w4_refs.py`, `totals_head.py`, `totals_online.py`,
`dist_margin_cover.py`, `clv_transfer.py`.

Their substitute validation is genuinely rigorous *against a different hypothesis*: hard
incumbent-reproduction gates, truncate-and-recompute (or censor-and-perturb) walk-forward audits,
and paired date-clustered bootstrap CIs. But a bootstrap CI resamples an already-computed
true-data delta and cannot reveal whether that delta is itself a chance or overfitting artifact,
and a truncate-and-recompute audit proves a feature does not peek forward without ever asking
whether the fitting procedure would look skilful on pure noise.

Three of the seven fit real parameters and claim a comparison against an incumbent, and are
therefore unfalsified against precisely the hypothesis a permutation probe exists to rule out:

- `bottomup_3pt.py` - fits `a_rate`, EB `K`, `a_team`
- `w2_integration.py` - fits a calibration `(a, b)`
- `w4_refs.py` - fits referee-prior `K`

The stakes are lower for the other four: `totals_online.py` has zero fitted parameters by
registration, `dist_margin_cover.py` computes rather than optimises its sigma, `clv_transfer.py`
fits nothing in-file, and `totals_head.py` fits a three-parameter closed-form OLS. Lower stakes,
same gap.

`bottomup_3pt.py` is the highest-value place in the repository to add a permutation probe.

### 3.5 Does the new test suite have teeth? Yes - proven three ways

`tests/test_permutation_integrity.py`, 8 tests, `python tests/test_permutation_integrity.py`
exits 0. It builds a three-stage chain matching the repo's shape (standardize -> ridge -> linear
calibration) on synthetic data with ground truth known by construction.

Safety and power first:

- **known-ZERO signal + faithful null** -> the null collapses to the published no-skill baseline
  and the real model is not distinguishable from it (`NO-SIGNAL`, six seeds).
- **known signal + faithful null** -> the null still collapses and the real model beats *every*
  permutation (`SIGNAL`, six seeds).

Then the teeth - three deliberately-defective pipelines that must be caught:

1. **`test_truecal_defect_is_caught_statistically`** implements the `joint_differential` defect
   verbatim (`cal_target=y_tr` while `y_tr` is permuted). On zero-signal data the broken null
   scores systematically *better* than the faithful null on identical draws and lands below the
   published baseline, where the faithful null sits above it. The rule fires on 8/8 seeds.
2. **`test_null_must_depend_only_on_permuted_targets`** is the sharper instrument, and it uses no
   statistics at all. Relabel the true targets by a fixed permutation pi and compose each draw
   with pi-inverse; both runs then see **bit-identical permuted target vectors**. A faithful null
   is a function of the permuted targets alone, so its per-draw MAEs must match to 0.0 - they do.
   The defective null moves. This is a structural proof of what the null reads, with no tolerance
   to tune, and it catches defects far too small to move a mean - which matters given 3.2.
3. **`test_hoisted_selection_manufactures_false_positive`** covers the mining analogue: a
   pre-registered battery of 120 cells over pure-noise outcomes, where the observed statistic is
   the *maximum* cell mean. Re-selecting inside the loop gives the honest `NO-SIGNAL` answer;
   scoring only the true-data winner under permutation strips the null of the selection advantage
   and drives the p-value to its floor on data with **no signal whatsoever**. At least 5 of 6
   seeds produce a false positive under the defect and at most 1 of 6 under the honest null.

Plus two guard rails: `test_audit_rule_would_have_caught_the_real_defect` replays the actual
published numbers (11.4730 / 11.3005 / 11.4088) and requires the rule to clear the faithful null
and reject the diagnostic one; `test_configured_tolerance_is_too_loose` pins section 3.2.

If a future edit weakens the audit rules, tests 1-3 go green when they should be red and the file
fails. That is what "teeth" means here: the suite fails when the *detector* breaks, not only when
a pipeline breaks.

---

## 4. Deliverable C - the as-of-date invariant

### 4.1 The invariant

> For every scored forecast row, every fitted artifact feeding it must prove that its latest
> source observation **strictly** predates that row's forecast timestamp.

Strictness is load-bearing: equality is a violation. An artifact whose last source observation
*is* the row being scored is exactly the `rapm_v0` failure. This is stronger than season-level
walk-forward - an artifact refit for season s from seasons < s still has to prove its last
observation precedes each row it scores, which catches a mid-season refit that silently swept in
yesterday's games.

### 4.2 `asof_invariant.py`

Stdlib-only (no pandas in the import graph, so a builder, a scorer, a test or a hook can all use
it). Three pieces, as registered:

**(1) The manifest convention.** Every fitted artifact `<path>` carries a sidecar
`<path>.manifest.json` with `schema`, `artifact`, `producer`, `fit_through_date`,
`fit_through_season`, `fit_seasons`, `content_sha256`, `content_bytes`, `created_at`, `notes`.
`fit_through_date` is the **latest source observation** - not the build time, not the file mtime.
`content_sha256` binds the manifest to the bytes, so a refit that forgets to rewrite its manifest
is *detected* rather than trusted. `write_manifest()` / `read_manifest()`; `read_manifest` raises
`ManifestError` on absent, malformed, incomplete, or wrong-schema sidecars and never returns a
partially-trusted dict.

**(2) `assert_asof(artifact_manifest, forecast_time)`** raises `AsOfViolation` unless the
artifact's `fit_through_date` strictly precedes `forecast_time`. Optional `verify_hash=True`
re-hashes the artifact first (cheap per run, too slow per row). `check_asof()` is the non-raising
form for reporting loops. Companion `assert_scored_seasons_clean(manifest, scored_seasons)`
applies the same rule at season granularity - this is the call that would have refused `rapm_v0`
for 2024.

**(3) The scanner.** `scan_artifacts()` walks the repo against a conservative glob list of known
fitted artifacts and reports, per artifact, whether a manifest exists, validates, and matches the
current bytes. Nothing is written and nothing raises. CLI:
`python asof_invariant.py --scan --csv experiments/asof_audit/missing_manifests.csv`
(exit 1 if anything is unattested or drifted).

`tests/test_asof_invariant.py`, 8 tests, exits 0. Covers the round trip, every refusal path, hash
drift detection, the strict-ordering boundary (including the equality case), timezone
normalisation (naive = UTC; a bare date becomes midnight UTC, the conservative reading), the
`rapm_v0` season regression, and the scanner.

### 4.3 Which artifacts lack manifests

**All of them. 18 of 18, zero attested** - see `missing_manifests.csv`:

`data/rapm/rapm_v0.csv`; the four `data/zone_maps/*.csv` map tables;
`data/zone_maps/shrinkage_priors.csv`; `evalharness/frozen_baselines.json`;
`experiments/channel_reval/run_summary.json`; `experiments/channel_reval/predictions_v2.csv`;
`experiments/dist_margin_cover/residual_pool.csv`; the five
`experiments/rapm_multiseason/rapm_v1_*.csv`;
`experiments/w2_integration/calibration_params.json`; `experiments/w4_refs/crew_factors.csv`;
`experiments/w6_retrospective/zscore_params.json`.

The invariant holds for most of them in fact - section 2 establishes that by hand. It is
assertable for none of them. That is the actual structural finding: the repository's leakage
discipline is carried entirely by module-level constants and prose, which is why `TRAIN_SEASONS`
sitting at line 74 of `build_rapm.py` was invisible to two downstream consumers until a build
agent went looking.

### 4.4 How the walk-forward rating rebuild must satisfy this

`build_rapm_walkforward_v1` (registered 2026-07-31T15:58:28Z, in flight in another session)
becomes acceptable under this invariant when all six hold. The shape is pinned as an executable
test - `tests/test_asof_invariant.py::test_walkforward_family_satisfies_invariant` - which builds
exactly this family and asserts the battery below.

1. **One manifest per season table.** The rebuild emits a family, not one file: the table used
   for season s is fit only on seasons < s. Each gets its own sidecar. A family sharing one
   manifest cannot express per-season fit windows and defeats the point.
2. **`fit_through_date` is the max source observation, derived from the data.** For the season-s
   table that is `max(game_date)` over the possessions that entered the fit - not the build
   timestamp, not the season boundary as a hardcoded constant. `fit_through_season = s - 1`,
   `fit_seasons = [seasons < s]`.
3. **The consumer asserts, per row, before scoring.** `assert_asof(manifest, forecast_time)` for
   the timestamp rule and `assert_scored_seasons_clean(manifest, [s])` for the season rule. Both,
   not either: the season rule is what catches `rapm_v0`; the timestamp rule is what catches a
   mid-season refit the season rule would wave through.
4. **The registration's `fit_through_season` column is necessary but not sufficient.** The
   registration specifies an output schema identical to `rapm_v0.csv` plus a `fit_through_season`
   column. Good - but a column inside the file cannot be checked before the file is read, cannot
   express a *date*, and cannot detect that the file was rebuilt. Emit the column **and** the
   sidecar.
5. **The 2022 and 2021 tables need explicit handling.** Per the registration, 2022 is fit on 2021
   alone (thin-history caveat) and 2021 has no prior and is excluded from any downstream use. The
   2021 case must be an absent manifest or an explicit refusal - not a manifest claiming a fit
   window it does not have. The invariant helper raises on a missing manifest, which is the
   correct default.
6. **Round-trip proof, not assertion.** For every scored row in the recomputed
   `oracle_availability_bracket_v2` and `joint_differential_v1`, the season table used must pass
   both rules. The 2025-2026 slice of `oracle_availability_bracket_v2` should reproduce the
   committed clean numbers to floating point (nothing there is fitted); if it does not, the
   rebuild has a bug. `joint_differential_v1` must re-run **end to end** - retune lambdas, refit
   ridges, refit the calibration - because its committed parameters are contaminated (section 2);
   its ablation arm should reproduce exactly.

Adoption sequencing, so the rebuild does not inherit the problem it is fixing: manifests first
(they are cheap and independent), then the rebuild emits them natively, then consumers add the
asserts, then the recomputations in `BLAST_RADIUS.md` section 4 run. Producers that already know
their fit window - `run_reval.py`, `dist_margin_cover.py`, `run_w6.py` - can be manifested
immediately and would cost a single `write_manifest()` call each.

---

## 5. Limitations of this audit

- **Static reading, not execution.** No experiment was re-run. Verdicts rest on source, committed
  artifacts and JSON audit records. The one number I could not independently re-derive is the
  11.3005 defective-null mean, which comes from `experiments/joint_differential/REPORT.md`; the
  code's construction is fully consistent with it.
- **The repository moved during the audit.** `rebaseline_screen.py` (12:23), `daily_forecast.py`
  (12:14), `props_edge.py` (12:08) and `.claude/worktrees/hungry-keller-ad0318/` (which contains
  a `build_rapm_walkforward.py`) changed while it ran. `rebaseline_screen.py` was not audited for
  permutation integrity; it declares `VAL_SEASON = 2024` and follows the `feature_lab` shape, but
  it should be added to `permutation_audit.csv` when it settles.
- **Severity of the zone-map K contamination is argued, not measured.** Measuring it requires
  re-running `w2_integration` with a train-only `k_table`, which is a re-run this audit's file
  boundary forbids.
- **The direction of the `joint_differential` parameter bias is unknown.** I claim the
  clean-season numbers are not a valid measurement; I do not claim to know which way they move
  once the parameters are refit on clean values.
