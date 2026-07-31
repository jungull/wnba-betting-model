# BLAST RADIUS — every consumer of every fitted artifact

*Deliverable (A) of `asof_invariant_audit_v1` (registered 2026-07-31T16:06:42Z). Produced by a
read-only sweep of the repository on 2026-07-31. Machine-readable companion:
`blast_radius.csv` (35 rows). No registry write, no leaderboard render, no experiment script
modified.*

**Headline: 3 committed results carry INVALID-PENDING-RECOMPUTATION content; 5 more are
NEEDS-REVIEW; 27 artifact-consumer pairs clear.** The rating-table contamination reaches one
season further than the erratum recorded, and a **second, independent** fitted artifact — the
zone-map shrinkage constants — is fit on every season it is used to score.

---

## 1. The two contaminated artifacts

| artifact | producer | fit window | evidence |
|---|---|---|---|
| `data/rapm/rapm_v0.csv` (`net_100`) | `build_rapm.py` | seasons **2021–2024**, static single fit | `build_rapm.py:74` `TRAIN_SEASONS = {"2021","2022","2023","2024"}` |
| `data/zone_maps/shrinkage_priors.csv` (30 EB `K` constants) | `build_zone_maps.py` | seasons **2021–2026**, full sample (max shot date 2026-07-29) | `build_zone_maps.py:579` `ktab = estimate_k_table(df)` over all shots; `matchup_overlay.py:26–30` |

Everything else with a fit window — channel alphas and calibrations, the minutes alpha, the
minutes two-stage lambdas and betas, the `bottomup_3pt` EB `K` and two alphas, the `w4_refs`
referee `K`, the `dist_margin_cover` sigma and residual pool, the `w6` z-score params and
thresholds, the `totals_head` OLS coefficients, the feature-lab frozen alphas — is fit on
2021–2023 (or earlier folds) and scored on 2024+. Those all clear.

---

## 2. Verdict ledger

### INVALID-PENDING-RECOMPUTATION

**2.1 `oracle_availability_bracket_v2` — the published pooled numbers (n = 627)**
207 of 627 scored games are 2024, inside the rating table's fit window. All four published
variant MAEs (v1 10.1753 / v2 10.1555 / v3 10.1170 / v4 10.1072) and the `+0.0198` gated delta
are computed over the contaminated union. Already conceded by the erratum; recorded here for
completeness.

*The clean 2025–2026 slice (n = 420) is **VALID**.* Nothing in `oracle_bracket.py` is fitted:
`LINEUP_SCALE = 4.0` is fixed a priori and the centre `str_margin_cal` comes from a 2021–2023
fit. No parameter carries contamination into the clean rows. One second-order caveat: the
replacement value (p25 of `net_100`) is a scalar summary of the contaminated table and is applied
on clean rows too.

**2.2 `joint_differential_v1` — the ENTIRE run, including the "clean-season" read**

This is the escalation. The erratum and `experiments/joint_differential/REPORT.md` both relocate
the honest headline to the RAPM-clean seasons 2025–2026 (`+0.0535` challenger, `+0.0495` RAPM
increment). **That relocation does not hold.** There are two intersections, not one:

1. 229 test games in 2024 sit inside the fit window — the disclosed one.
2. **All three train seasons 2021–2023 also sit inside it.** The script records this itself and
   then does not draw the consequence: `experiments/joint_differential/audit_results.json`
   contains `"train_seasons_inside_fit_window": [2021, 2022, 2023]`.

Every fitted parameter of the full challenger was estimated against `d_rapm` values that carry
contemporaneous information about the very train games they were fit on:

| parameter | fit on | verified at |
|---|---|---|
| four per-channel ridge lambdas | inner walk-forward folds inside 2021–2023 | `joint_differential.py:580–588` |
| four ridge coefficient vectors | the 610 train games 2021–2023 | `:597` `models = fit_channels(g2, train_lab, …)` |
| margin calibration `a=0.1153, b=0.9314` | the same 610 games | `:605–607` `rr.linfit(g2.loc[train_lab, "jd_margin_uncal"], …)` |

Applying those parameters to 2025–2026 does not launder them. The feature *values* on clean rows
are clean; the *coefficients multiplying them* are not. The clean-season delta measures a
mis-specified model, not "what a walk-forward lineup-value differential is worth". Its sign is
not even reliably conservative: an in-window-inflated feature-target correlation biases the ridge
coefficient upward, while the calibration slope `b = 0.9314` was fit to shrink inflated
predictions — the two errors do not cancel in a knowable direction.

*One part survives.* The **ablation arm** (`FEATSETS_ABL`) excludes `d_rapm` entirely, so neither
its features nor its coefficients touch `rapm_v0`. Its finding — the differential reframing
carries nothing (`-0.0175` pooled, `+0.0040` clean) — is **VALID** and is the only result in
`joint_differential_v1` that this audit clears.

**2.3 `clv_transfer_v1` — old-era tables only**
`clv_transfer.py:78` reads all four committed oracle margin variants and builds its transfer
curve on the MAE spacing between them. On old-era games (2024 and pre-2025-07-05 2025) that
spacing is contamination-driven, so every old-era transfer and breakeven row inherits it.

*The registered primary comparison is **VALID***: extension era, T-24h, 2025-07-05 onward, 286
games — entirely outside the fit window, and nothing in `clv_transfer.py` is fitted.

### NEEDS-REVIEW

**2.4 `w2_zone_channel_integration_v1` — the zone-map shrinkage constants**
This is the second, previously-unrecorded contamination.

`maps_before()` **does** genuinely restrict by cutoff — verified, not taken on trust:
`matchup_overlay.py:251` `mask = df["game_date"] < cutoff`, and every rate (league conversion,
league shares, team offense/defense) is recomputed from that pre-cutoff slice. The rates are
walk-forward clean.

The **shrinkage constants are not**. `w2_integration.py:673` calls `mo.load_k_table()` — the
stored full-sample table — and passes it unchanged into every `maps_before` call for both train
and test games. The K constants were estimated over 2021–2026, which contains **every season
w2_integration scores** (2024, 2025, 2026). `matchup_overlay.py:29–30` anticipates exactly this
and is worth quoting: it says a strict walk-forward experiment may re-estimate them on train
years only and pass its own table via `k_table=`. `w2_integration` did not.

Severity is low — 30 variance-ratio scalars estimated from ~1000 cells each, with 2024–2026
contributing roughly half the cells — and the registered verdict was FAIL, which contamination
would only have made harder to reach. But the run is not walk-forward clean and must stop being
described as such.

**2.5 `coherence_study` / `coherence_substitution_rule_v1` — transitive**
`coherence_analysis.py:105` consumes `experiments/w2_integration/calibration_params.json` and
w2 game-level predictions, both produced with the contaminated K. The study's central R2 claim
(recombining existing predictions is dead; only new differential information moves the margin)
does not obviously turn on the K values, but it is not independently clean and should be
re-derived once w2 is rebuilt with a train-only `k_table`. Note this claim is the same one
`joint_differential_v1` was registered to test — and that test is now invalid, so the claim is
currently supported by neither.

**2.6 `experiments/rapm_multiseason/rapm_v1_*_train2021_26.csv` — DO NOT ADOPT**
`build_rapm_v1.py:877,897` writes candidate tables fit through **2026**. Any consumer scoring any
season would intersect on every row. They are currently unconsumed — grep confirms only
`build_rapm_v1.py` references them — which is the only reason this is not already a second
incident. The `*_train2021_24` siblings carry the identical defect for 2021–2024.

**2.7 `data/zone_maps/{player,team}_zone_*.csv` — DO NOT CONSUME**
Full-sample season-stratified maps with `_shrunk` columns. No scoring code reads them (verified
across all `*.py`); `w2_integration` rebuilds from `shots_enriched.parquet` via `maps_before`
instead. Any future consumer must use `maps_before` with a train-only `k_table`, never these.

**2.8 Prose citing the contaminated numbers**
`project_docs/ASSUMPTION_AUDIT_2026-07-30.md`, `project_docs/HANDOFF_2026-07-30.md`,
`experiments/oracle_bracket/REPORT.md`, `experiments/joint_differential/REPORT.md`. The last of
these presents the clean-season read as the honest headline, which §2.2 finds is itself not
clean.

**2.9 `evalharness/frozen_baselines.json` — valid as used, review as cited**
The eight constants never enter a prediction; `load_frozen_baselines()` is a tamper check that
raises on drift. But 9.54 / 10.53 / 11.22 were *measured* on 2024–25 games, and the 2026-07-31
erratum amendment reclassified the game model's 2024–2026 seasons as DEVELOPMENT/AUDIT data.
They remain legitimate references. They can no longer be described as confirmatory.

### VALID (27 artifact–consumer pairs)

Every consumer of `experiments/channel_reval/run_summary.json` (alphas + six calibration pairs,
fit on 610 games 2021–2023, latest source observation 2023-10-18): `dist_margin_cover`,
`joint_differential`, `w2_integration`, `w4_refs`, `bottomup_3pt`, `totals_head`, `totals_online`,
`oracle_bracket`, `pocket_mining`, `clv_transfer`, `daily_forecast`. Plus the tuned constants
listed in §1. Full reasoning per row in `blast_radius.csv`.

Two are worth singling out as the pattern the rest of the repo should copy:

- **`dist_margin_cover.py:330–336`** refuses to run — `raise SystemExit("PROVENANCE VIOLATION…")`
  — unless the residual pool's seasons equal `TRAIN_YEARS` exactly and its max date precedes the
  test era. This is the only place in the repository where a provenance rule is *enforced* rather
  than documented. Had `build_rapm.py` carried the equivalent, this audit would not exist.
- **`experiments/w6_retrospective/zscore_params.json`** stores `train_seasons: [2021, 2022, 2023]`
  alongside the parameters — an informal manifest, and the closest thing in the repo to
  deliverable C's convention.

---

## 3. The live prospective log

`daily_forecast.py` → `forecasts/forecast_log.jsonl` (first record 2026-07-31T14:28:20Z,
hash-chained, forward-only) is the game model's holdout after the erratum reclassification. Its
artifacts: channel alphas and calibrations (latest source observation 2023-10-18), `SIGMA_V0 =
12.9022` (train-only pool, 2023), `MINUTES_ALPHA = 0.30` (tuned 2021–2023). It reads **no** RAPM
and **no** zone maps (verified by grep).

**The invariant holds. It cannot currently be asserted.** None of those artifacts carries a
manifest, so the check today is a human reading three constants in a header comment. That is the
gap deliverable C closes; see `REPORT.md` §4.

---

## 4. What recomputation requires

1. `build_rapm_walkforward_v1` lands: per-season tables, values for season *s* fit only on
   seasons < *s*, each with an `asof_invariant` manifest.
2. **`oracle_availability_bracket_v2`** re-runs on the walk-forward values. Only the 2024 slice
   changes; the 2025–2026 numbers should reproduce to floating-point, which is itself a useful
   check on the rebuild.
3. **`joint_differential_v1`** re-runs *end to end* — retune lambdas, refit ridges, refit the
   calibration. Reusing the committed coefficients on new values would carry the defect forward.
   The ablation arm should reproduce exactly; if it does not, the rebuild has a bug.
4. **`clv_transfer_v1`** re-runs its old-era tables off the recomputed oracle margins.
5. **`w2_zone_channel_integration_v1`** re-runs with `k_table=` estimated on 2021–2023 only —
   the escape hatch `matchup_overlay` already provides.
6. **`coherence_study`** re-derives off the rebuilt w2 outputs.
7. Prose in §2.8 amended in the same pass.

Until (1), the standing rule from the `build_rapm_walkforward_v1` registration binds: no
experiment may consume fitted player values on a scored season inside the fit window.
