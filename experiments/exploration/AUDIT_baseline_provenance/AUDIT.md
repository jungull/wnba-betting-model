# AUDIT — baseline provenance / the retrospective-baseline trap

**Date:** 2026-08-07 · **Scope:** whole program · **Mode:** read-only. Nothing outside
`experiments\exploration\AUDIT_baseline_provenance\` was created or modified. Frozen screens were
read, never repaired.

---

## ANSWER FIRST

**Yes. There is a fifth instance under a live claim, and there are several.** The single worst is
**not** in the exploration screens — it is in `M13_PLAYER_VALUE_TRANSLATION`, whose residual
distribution is fitted on a season pool that includes seasons *later* than the rows it scores, and
whose output propagates into every number `M14_MODEL_MARKET_RESIDUAL` publishes. No clean variant
exists anywhere in that chain.

The exploration-side fifth instance is **E0 I0005**, which is worse than a plain construction error:
its `NOTES.md` presents full-season leave-one-game-out as the *leakage guard* and concludes
"there is nothing to rerun." That paragraph is a false all-clear on a screen whose ΔR² = 0.008424
is the direct ancestor of the I0009 line of work.

---

## COVERAGE STATEMENT

### What was enumerated (scripted, not eyeballed)

| Area | Enumerated | Method |
|---|---|---|
| `experiments\exploration\` | 17 screens in scope (+3 excluded, +1 this audit dir) | `enumerate.py` |
| `experiments\player_program\` | 24 sub-areas, incl. all of stage2a / stage2b / stage3_score / possession_features_v1 / turnover_* / projected_exposure_v1 / fits_v1 / validation_v1 | `enumerate.py` |
| `experiments\market_program\` | 29 nodes | `enumerate.py` |
| Root-level analysis scripts | 106 `.py` at repo root, incl. all four named in the brief | `enumerate.py` |
| **All other `experiments\*` directories** | **51 more** (gap-closing pass — see correction below) | `scan_remaining.py` |
| **Python files scanned for baseline constructions** | **515** | `scan_baselines.py` → 6,366 candidate lines, 173 flagged as name+window-operator co-occurrences |
| `experiments\registry.jsonl` | 96 records, every one parsed; increment-bearing fields extracted | `registry_claims.py` |
| Artifact→manifest map | 142 referenced artifacts resolved on disk | `manifest_check.py` |

### What was inspected by reading the construction

Every one of the 173 `BASELINE_CONSTRUCTION` hits was triaged; every candidate in the 17
in-scope exploration screens was read to the line that builds it. `player_program` and
`market_program` were swept by two dedicated read-only investigators working to the same rule
(classification is rejected without a quoted construction line); their findings are merged here and
tagged by source in `AUDIT.json`.

### What was deliberately skipped, and why

- **`E1_I0013_tempo_redundancy`, `E1_I0004_shot_selection`, `E0_I0014_residual_heterogeneity`** —
  excluded entirely by instruction (concurrent agents, mid-write, contents inconsistent). Not read.
  Note the consequence: `E1_I0013` and `E0_I0014` both call `base.zwithin`, so **finding F7 very
  likely applies to them too and could not be checked.**
- **`_screen_kit` and `E1_I0004_fga_forecast`** — these two directories **did not exist when I
  enumerated** and appeared under `experiments\exploration\` during the audit (last writes 22:13:54
  and 22:14:14, i.e. seconds before I finished). They are not in the inventory and were **not
  audited**. They need a follow-up pass once they are frozen.
- **Timing note on `E0_I0013_possession_volume`** — it was written concurrently earlier in the
  evening (last write 21:11), before I read it. My F7 reading of it is therefore against a stable
  version, but that is luck rather than design; re-verify if it moves again.
- **`2025`/`2026` data** — never read, joined, described or summarised. Source code referencing
  those seasons was read (reading source is not reading holdout data). Every probe executed here
  asserts `season ⊆ {2021,2022,2023,2024}` on its input frame before use; see the
  `[partition-check]` lines in `run_log_probe.txt`.

### Not reached (stated plainly so it can be dispatched)

- stage2b arms A02, A03, A05, A07, A08–A11, A14, A15, A18, A20, A22–A25 — scored for
  guard-vs-aggregation density; the low-guard outliers were read, the rest were not. **A02 and A25
  are the two to open first.**
- stage3_score arms sc02–sc05, sc08, sc11, sc12 — cleared only via the shared `features_common.py`.
- `pocket_mining.py` (1,676 lines) and `conditional_edge.py` beyond two regions — skimmed only.
- `daily_forecast.py` — a forward-forecast producer, not an evaluator; no baseline hits.
- `experiments\playoff_shift\` and `experiments\totals_groundwork\` — identified as consumers of the
  artifact-granular incumbent (F17) but their increment logic was not read line by line.

### Correction to my own coverage — recorded rather than quietly fixed

My first scan covered only `exploration`, `player_program`, `market_program` and the root scripts,
which left **51 other `experiments\*` directories silent**, and I initially reported that
`coherence_study` did not exist. **It does** — `experiments\coherence_study\coherence_analysis.py`,
705 lines. A gap-closing pass (`scan_remaining.py`) swept all 51. It found **four further consumers
of the artifact-granular `predictions_v2.csv`** — `coherence_study`, `playoff_shift`,
`totals_groundwork`, plus `channel_reval` as its producer — now recorded as **F17**. Most of the
other 47 directories contain no code at all (they are frozen artifact/report directories).

---

## PRIORITISED TABLE

Severity reflects **blast radius**, not effect size. A small effect under a heavily-quoted headline
outranks a large effect in a dead screen.

| # | Sev | Baseline / control | Where built | Class | Live claims it contaminates | Clean variant shipped? | Probe |
|---|---|---|---|---|---|---|---|
| **F1** | **CRITICAL** | M13 residual `fit_pool` | `M13...\build_translation.py:60,369-375` | RETRO **CROSS-SEASON** | M13 `calib_verdict`, brier/logloss CI95 → `translation_rows.parquet` → **all of M14**: every `resid_prob_*`, `falsification.verdict`, `residual_by_season/book` | **NO** — all four distributional variants share the same leaky pool | n/a (substrate outside partition) |
| **F2** | **HIGH** | `opponent_pressure_loo` + `player_tendency_loo` | `E0_I0005\build_data.py:60,62,74,76` | RETRO SAME-SEASON | `summary.json r2_gain_pressure_over_pooled = 0.008424`; the NOTES sentence that spawned I0009; re-quoted as `E0_rung1_pooled_dR2` in `E1_I0009_r2_rerun\step23:73` | **NO** | **0.7417 vs 0.5148, ΔR²=0.3426** |
| **F3** | **HIGH** | `A_incumbent` = `predictions_v2.csv` | `run_p3_downstream.py:39,188` | RETRO CROSS-SEASON (`asof_granularity:"artifact"`, `fit_through_season:2026`) | `team_score_mae_improvement`, `margin_mae_improvement`, both CI90s, `paired_vs_incumbent`, `concentration` → `P3_DOWNSTREAM_RESULTS.json`; `p3_downstream_rows.parquet` inherits | **NO** (sibling `B_off/B_def/B_net` *are* clean) | n/a |
| **F4** | MED-HIGH | `baseline_mse_intercept_only` | `fit_rate_and_p3.py:173` | RETRO SAME-SEASON (+ contemporaneous) | `folds[*]` beside `test_mse` → `RATE_AND_P3_REPORT.json` `p3_full_game` / `p3_competitive` | **NO** | n/a |
| **F5** | MED-HIGH | `displaced_involvement` (challenger side) | `run_turnover_p2.py:143,155,159` | RETRO CROSS-SEASON | `paired_vs_D`, `mean_mae_reduction`, ci90 → `TURNOVER_P2_RESULTS.json`. **Plus a false attestation in `FEATURE_VALIDATION.json`** | **NO** | n/a |
| **F6** | MED | `rapm_v0.csv` `net_100` | `oracle_bracket.py:213` | RETRO CROSS-SEASON | `res3/res4.pooled_improvement`, gated `v2_vs_v1`; registry `oracle_availability_bracket_v1/_v2` | **NO** — and `joint_differential.py` *does* disclose the identical input | n/a |
| **F7** | MED | `base.zwithin` / I0010 `demean` within-season centering | `E0_I0012\base.py:162-164,255-257,277-282` | RETRO SAME-SEASON + CROSS-SEASON | E0_I0012 pooled `dR2_M` / `dR2_OxM`; E0_I0013 `run_screen.py:203-206`; E1_I0012; E0_I0010 `analyze.py:166` | NO — but the **per-season** rows in the same tables are far less affected | **not measured** — see caveat |
| **F8** | MED | roster/rotation height, full-season minutes weights | `E1_I0008\build_frame.py:123-136` (orig. `E0_I0008:46-49`) | RETRO SAME-SEASON | I0008's +0.018–0.020 lead | **YES for the baseline** (`shift(1).ewm(...)`); it is the *signal* that reads ahead | **already disclosed & neutralised** |
| **F9** | MED | `LATE` market snapshot vs earlier-decided model | `SCORE_BASELINES:500` / `MODEL_VS_MARKET:332` | CONTEMPORANEOUS | SCOREBOARD `advantage_ci95`, `paired_delta_composite_minus_market`, published verdict string; `model_vs_market.json` headline | PARTIAL (`EARLY` class exists, never used) / NO | n/a |
| **F10** | LOW-MED | `baselines_raw_on_off` | `fit_rate_and_p3.py:346-352,441` | RETRO CROSS-SEASON | `RATE_AND_P3_REPORT.json baselines_raw_on_off` | NO — but self-labelled `"DIAGNOSTIC ONLY"` | n/a |
| **F11** | LOW | `tm_baseline` full-season presence-game mean | `E0_I0006\analyze_clean.py:85-95` | RETRO SAME-SEASON | I0006 redistribution shares | NO — but it is a descriptive estimand, not a forecast increment; placebo asymmetry handled correctly | n/a |
| **F12** | LOW | `own_avg` / `high3` | `E0_I0003\aggregate_and_test.py:107-108,131-132` | RETRO SAME-SEASON | descriptive contrast only, no ΔR², no gate | NO | n/a |
| **F13** | LOW | `prior_*` **fallback scalar** | `E0_I0011\build_frame.py:106,161` | prior_* itself CLEAN; fallback RETRO CROSS-SEASON | `SHRINK_*` estimator family only | **YES** — NAIVE and INCUMBENT never touch `prior_*` | n/a |
| **F14** | LOW | `sigma_hat` archive median | `M16...\coherence.py:240,252` | RETRO CROSS-SEASON | `incoherence_B` quantiles. No outcome enters, no improvement published | NO | n/a |
| **F15** | LOW | `base = yf.mean()` on `fit_2024` | `prob_edge_ablation.py:146,160` | RETRO SAME-SEASON (that slice only) | `slices.fit_2024` logloss/brier | YES — later slices are clean, and the slice label discloses it | n/a |
| **F16** | LOW | `pd.qcut` bucket boundaries | `p3_concentration_addendum.py:98` | RETRO CROSS-SEASON | reporting strata only | NO | n/a |
| **F17** | MED | `predictions_v2.csv` as incumbent, 4 more consumers | `coherence_study\coherence_analysis.py:89`; `playoff_shift\run_playoff_shift.py:46`; `totals_groundwork\run_totals_groundwork.py:38`; produced at `channel_reval\run_reval.py:544` | RETRO CROSS-SEASON (artifact-granular) | `coherence_study` "pooled totals improvement (d3 − incumbent)" + 90% bootstrap CI + **a gate-4 dress rehearsal**; playoff_shift and totals_groundwork increments | **NO** | n/a |

**F7 caveat, stated explicitly:** this is an *aggregate-level preprocessing* leak, not row-level
hindsight — categorically milder than a leave-one-out. The mechanism is real (a season-specific
centering constant inside a pooled regression whose base model has no season dummies is *not*
absorbed by the intercept, and the headline metric is a product term), but **I did not measure its
magnitude**, because doing so would require re-executing a frozen screen. It is reported because
those screens' own FINDINGS describe these arms as "fully pregame-observable," which is not
literally true.

---

## THE PROBE (STEP 3c) — five suspects, 2021-2024 only

For each: does the suspect predict the entity's own **strictly-after-date** future rate better than
a legitimately-pregame baseline does? A baseline that predicts the unplayed future does so because
it contains it.

| Probe | Suspect | corr(suspect, own future) | corr(clean, own future) | ΔR² suspect over clean | n |
|---|---|---|---|---|---|
| A1 *(method control)* | `player_tendency_loo` | **+0.6455** | +0.3647 | **0.331880** | 17,544 |
| **A2 (new)** | `opponent_pressure_loo` | **+0.7417** | +0.5148 | **0.342649** | 1,892 |
| **A3 (new)** | `opponent_defrtg_loo` | **+0.6992** | +0.4958 | **0.270074** | 1,892 |
| B1 | `loo_zone_rate` (opp allowance) | +0.9601 | +0.8994 | 0.121747 | 108,756 |
| B2 | `player_zone_baseline` (LOSO) | +0.8091 | +0.7120 | 0.161126 | 81,842 |

A1 reproduces the brief's figures (+0.6455 / +0.3647 / 0.3319) **exactly**, which is what licenses
the other four rows. A2 is the finding that matters: the opponent-pressure LOO — *the quantity
I0005 and I0009-rung-1 actually tested* — contains **more** future than the player tendency baseline
does. B1/B2's absolute correlations are inflated by between-zone level differences (rim vs three);
the *difference* and the ΔR² are the informative quantities there.

---

## MANIFEST CHECK

Method note: manifest fields were read **as JSON**. No byte/regex scan for season strings was used —
that check has produced false positives in this program twice.

- **142** referenced artifacts resolved on disk.
- **`asof_granularity: "row"`** (filtering IS sufficient) — 3 distinct files, including
  `data\masters\master_player.parquet` and `master_team.parquet`. **This matters:** those two are the
  foundation of E0_I0010 / I0011 / I0012 / I0013, and they are clean.
- **`asof_granularity: "artifact"`** (whole file bounded by its latest input — **filtering does not
  help**): 2 files, both live.
  - `experiments\channel_reval\predictions_v2.csv` — `fit_through_season: 2026`. Consumed by
    `bottomup_3pt.py`, `w4_refs.py`, `totals_head.py`, `totals_online.py`, `joint_differential.py`,
    `dist_margin_cover.py`, `clv_transfer.py`, `conditional_edge.py`, `pocket_mining.py`,
    `oracle_bracket.py`, **`run_p3_downstream.py:39` as `A_incumbent`** (F3), **and four more found
    in the gap-closing pass** — `coherence_study`, `playoff_shift`, `totals_groundwork`,
    `channel_reval` (F17). It is the incumbent behind essentially every `pooled_improvement` in the
    root scripts. Registry entries `bottomup_3pt_channel_v1` and `w4_ref_fta_priors_v1` sit on top
    of it. **This single file is the largest concentration of blast radius in the audit.**
  - `data\rapm\rapm_v0.csv` — `fit_seasons: [2021..2024]`. Its own `backfill_basis` names it as the
    artifact whose misuse motivated `asof_invariant_audit_v1`. Disclosed by `joint_differential.py`,
    **undisclosed by `oracle_bracket.py`** (F6).
- **No sibling manifest at all** (the check *cannot be performed*): **68 shared/upstream artifacts**
  (plus 24 screen-local intermediates, which are less concerning). Full list in
  `MISSING_MANIFESTS.json`. The two named in the brief are confirmed:
  `player_turnover_targets_v1.parquet` and `possessions_raw_v2.parquet`.

**Seven whole directories contain zero manifests** — `possession_features_v1`, `turnover_p1_v1`,
`turnover_p2_v1`, `turnover_targets_v1`, `projected_exposure_v1`, `fits_v1`, `validation_v1`. These
are pure artifact directories (receipts + parquet, no `.py`). Two mitigations worth crediting:
`team_possession_prior_v1.parquet` is row-granular *in fact* (builder verified at
`build_projected_exposure.py:280-311`), and `p3_coefficients_v1.parquet` carries a
`training_cutoff_season` column, i.e. it is row-granular by construction. Both still need manifests.

---

## UNDETERMINED — said plainly

| Item | Why | What would resolve it |
|---|---|---|
| `fit_rate_and_p3.py:445-447` `replacement_level` | A scalar from the *latest* cutoff, published — but I could not establish whether any delta consumes it as a reference | grep consumers of `RATE_AND_P3_REPORT.json` `replacement_level` / `primary_mean_net_rapm_100` |
| `bookie_totals_per_game.csv` vintage | No manifest; producing script outside scope. Opening vs matched vs closing total is unknown | read the `totals_groundwork` builder; backfill a manifest |
| `master_odds.csv`, `master_odds_extension.csv` | Referenced by five root scripts but **absent at those paths in this worktree** | confirm whether they are gitignored data present in the main checkout |
| stage2b arms A02, A25 | Not opened. A02's `groupby(GAME_COL).transform("sum")` is within-game — legitimate *if* the estimate is pregame | read both files end to end |
| **F7 magnitude** | Not measured — requires re-executing a frozen screen with an altered centering rule | a coordinator-authorised rerun outside the frozen directories |
| `evalharness\frozen_baselines.json` | Carries `asof_granularity: "artifact"`; three `player_program` scripts import from `evalharness`, only the stats helpers were verified | grep those three scripts for `frozen_baselines` |
| F7 in the three excluded screens | `E1_I0013` and `E0_I0014` both call `base.zwithin`; not readable during this audit | re-check after those agents finish |

---

## THINGS THAT LOOK LIKE THE TRAP AND ARE NOT

Recorded because each cost real time to clear, and because mistaking them for findings is how an
audit loses credibility.

| Construction | Why it is clean |
|---|---|
| `base.prior_expanding` (`E0_I0012\base.py:134`) | `cumsum() − own`, but **aggregated to date level first** (line 132) so same-day games cannot see each other. Strictly before the date. |
| `features_common.py:171-177`, `A13\arm_a13.py:216-219` | `groupby("season").mean()` — looks like a whole-season mean, but `agg["season"] += 1` makes it a *completed prior season*. |
| `props_edge.py:316-319` | The per-36 EWMA includes the row's own game — but is only ever served through `merge_asof(..., allow_exact_matches=False)`, so the served value is strictly prior. |
| `A26\feature_construction.py:190` | A **leave-one-out that is genuinely pregame** — the opponent mean is formed only from `_prior_count_and_sum(..., cutoff_date)`. The P35 "one-clock LOO-as-of-target-date" repair held. |
| `E0_I0011\build_frame.py:141-146` | `c_g_*` uses **realised** pace and the code says so — but it is only consumed via `prior_shift()`, so the value used is the *previous* game's realised pace, which is known. |
| `E0_I0010\analyze.py:163-164` | Computes both arms and labels them `"WITHIN-SEASON LOO (uses future games)"` and `"PREGAME-OBSERVABLE (decides the verdict)"`. The verdict rests on the clean arm. Exemplary. |
| `totals_head.py:266,388-406` | `searchsorted(side="left")` **plus** a truncate-and-recompute proof that `raise SystemExit`s on failure. The strongest walk-forward evidence in the repo. |

---

## FILES IN THIS DIRECTORY

`AUDIT.json` · `AUDIT.md` · `MISSING_MANIFESTS.json` · `probe_results.json` ·
`inventory.json` · `scan_hits.json` · `registry_claims.json` · `triage_exploration.txt`
Scripts: `enumerate.py` · `scan_baselines.py` · `registry_claims.py` · `triage_exploration.py` ·
`manifest_check.py` · `manifest_detail.py` · `merge_manifests.py` · `probe.py` · `scan_remaining.py`
Logs: `run_log.txt` · `run_log_scan.txt` · `run_log_registry.txt` · `run_log_manifest.txt` ·
`run_log_manifest_detail.txt` · `run_log_manifest_merge.txt` · `run_log_probe.txt` ·
`run_log_scan_remaining.txt` · `scan_remaining.json`
