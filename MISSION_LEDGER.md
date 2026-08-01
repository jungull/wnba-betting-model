# MISSION LEDGER

*The continuing-mission record. Updated at the end of every working session so the next
session resumes without reconstructing reasoning. Last updated **2026-08-01 ~01:40 UTC /
2026-07-31 21:40 ET**.*

**Success condition (only one):** a frozen, executable betting policy demonstrates
profitability under its preregistered prospective gate. Everything below is interim state.
"No profitable edge found yet" is a project state, not a final answer.

---

## 1. Current champion

| | |
|---|---|
| version | **`freeze-v0`** (tag `f1b6ce5`), approved by John 2026-07-31 |
| runs | `daily_forecast.py --live` via `WNBA_DailyForecast_AM` 10:20 ET, `_PM` 18:45 ET |
| status | **unmodified and will stay unmodified.** No challenger may alter it. |
| what it emits | core-only prediction; `core_plus_w1_prediction` and `w1_extraction` are null by design in v0 |

The champion is not touched while it is under prospective evaluation. A challenger replaces
it only at a declared version boundary, and its own prospective evaluation starts *at* that
boundary — never applied backwards to earlier live records.

## 2. Prospective sample status

| | |
|---|---|
| log | `forecasts/forecast_log.jsonl`, hash-chained, `verify_chain` **ok**, 6/6 verified |
| first record | 2026-07-31T14:28:20Z |
| records | **6** — idx 0–2 manual (`PROV-` ids, T-8h), idx 3–5 **scheduled** (real ids 1022600213/214/215, T-30m and T-90m) |
| automated path | **PROVEN 2026-07-31 18:45 ET**, task result 0, appended and chained |
| AM task | has not yet had a trigger since registration; first firing 2026-08-01 10:20 ET |

**Power (computed, not assumed).** From `experiments/clv_transfer/matched_gap_by_cutoff_and_season.csv`:
2026 T-24h clustered SE = **0.254 pts** over 57 game-dates. ~118 regular-season games
(~47 dates) remain ⇒ **MDE ≈ 0.78 pts**. The disputed margin gap is 0.12. Detecting it needs
~2,000 game-dates ≈ 14 seasons. Method cross-check: MDE(ROI) at n=200 ⇒ +0.198 vs the
conditional-edge arm's registered +0.199.

**This did not stop the mission — it redirected it** (responses 2 and 8): margins are now a
**monitored diagnostic** that may not justify any promotion (`plan_freeze_2026_07_31` F2),
and the decision surfaces are player-level quantities (33,636 player-games) and props
(~1,750 prospective rows against a 0.31 effect). Props clustered SE is **not yet computed**
and is a prerequisite of `calibrated_prob_edge_v1`, not an afterthought.

## 3. Active challengers (all registered, none run)

| id | what it tests | regime | state |
|---|---|---|---|
| `player_model_bakeoff_v1` | is EWMA/ridge underfitting? 4 arms: incumbent, dynamic hierarchical player profiles, CatBoost, TabPFN | A | registered, **not started** — now **amended by `council_design_v1`** |
| `council_design_v1` | does a diverse weighted council beat every individual member? | A | **registered 2026-07-31**, computes nothing yet |
| `calibrated_prob_edge_v1` | calibrated P(over) × executable odds ⇒ EV-thresholded frozen policy | A | **RUN 2026-08-01 — NEGATIVE.** See §4 |
| `executability_fixed_notional_v1` | replaces the unsatisfiable book-limits clause | A | registered, applied |
| `w1_extraction_quality_audit_v1` | what actionable pre-cutoff signal does W1 actually carry? | B | registered, **not started** |

### The council amendment changed the sequencing

`council_design_v1` replaces "which single arm wins" with "does a weighted council beat every
member". Registered **before** the bake-off ran, so it consumes no evaluation slice. Five
orchestrator-added guards are recorded in it; three change what happens next:

- **G2 — out-of-fold span is a blocking prerequisite.** The council must train weights on
  chronological OOF predictions, but the only cross-model aligned OOF set is
  `predictions_v2.csv`: **673 games — 2024 (229) / 2025 (276) / 2026 (168)**. Under the frozen
  slice labels the legitimate weight-*fitting* slice is **2024 alone, 229 games over ~90
  dates**. That cannot support up to nine members across six weighting methods, and gives
  ~23 games per regime for the ten-regime gate. **Ladder rungs 1–2 (equal weight, median)
  estimate no parameters and may proceed; rungs 3–6 are blocked** until
  `base_predictions_oof_2022_2023_v1` extends OOF backwards toward ~730 games.
- **G1 — market-as-member degeneracy guard.** Admitting the market as a *weighted* member
  recreates the comparative-error trap: since the market beats us in every measured market,
  an accuracy-optimising weight vector collapses onto it, and the council appears to win while
  having learned nothing. The market also enters **twice** — as a forecast member and as the
  price in the decision layer. The council is therefore fit and reported **both with and
  without** it; weight collapse onto the market is recorded as a **NULL, not a win**.
- **G3 — regime gating is development-only this season.** ~118 games / ~1,750 prop rows across
  ten regimes is ~175 rows per regime. Developable retrospectively with per-regime MDEs; not
  promotable on this season's prospective sample.

## 4. Failed and retired approaches (kept visible on purpose)

- **Comparative-error target — DEFECTIVE BY CONSTRUCTION.** `|edge| ≤ |model − market|`, so
  the target is maximised by *agreeing* with the line; it rewards abstention, not skill.
  Formalised permanently in `tests/test_edge_target_identity.py`. Successor was
  `calibrated_prob_edge_v1` — now also retired, below.
- **`calibrated_prob_edge_v1` — NEGATIVE, 2026-08-01.** The successor's objective was *sound*
  (binary `P(points > line)`, not comparative error) and the answer is simply **no edge**.
  Frozen policy loses ≈10% per unit staked out of sample. 2026 log loss **0.70154 > log(2) =
  0.69315** — worse than a constant 50% predictor. Calibration slope **inverts**: +1.144 →
  +0.445 → −0.263. Even in the fitting slice both ROIs span zero.
  **Mechanism:** `corr(p_over, disagree) = +0.007` vs `corr(p_over, market implied) = +0.612`.
  The projection carries essentially no information; the fitted probability is a degraded echo
  of the line, and the policy pays vig to bet against the real one.
  **Erratum, self-reported:** the first run's MDEs were anti-conservative ~20× (permutation
  shuffled only among selected bets). Corrected per v2 P3; conclusion unchanged.
  **This retires the "tune the betting policy" family.** Re-tuning EV thresholds, widening the
  band or searching bookmaker subsets are specification-searching against a signal-free input
  and are barred.
- **`player_volume_heterogeneity_v1`** — VOID (permutation resolution, B < m/q).
- **`joint_differential_v1`** — VOID in full (contaminated ratings).
- **Absence-load proxy** — relabelled **proxy failure** (r = 0.092 vs the post-hoc count),
  not evidence against the hypothesis. Needs a direct measurement (see §7).
- **Playoff betting** — paused by John 2026-07-31; gap vs books roughly doubles in playoffs.

## 5. Assumptions currently under question

1. That the incumbent player layer underfits (→ `player_model_bakeoff_v1`).
2. That W1 news carries actionable pre-cutoff signal at all (→ §7; current honest estimate
   is **near zero** at headline grade).
3. That props have enough rows to decide anything this season (→ compute the clustered SE).
4. That 2025 is usable as confirmation for the player-rate program — weakened by
   `PROGRAM_FIREWALL.md`; the live log is the tiebreaker.

## 6. Data being accumulated (all automated, all verified tonight)

| stream | cadence | StartWhenAvailable |
|---|---|---|
| odds capture | hourly 10:00–23:00 | True |
| injury capture | hourly | True |
| news capture | 4×/day | True |
| props capture | 4×/day | **True** (repaired 2026-07-31) |
| referee assignments | daily | True |
| `daily_refresh.py` | 08:30 | **True** (repaired 2026-07-31) |
| forecasts | 10:20, 18:45 ET | True |

A missed day is permanently missing and is never backfilled. **The machine must stay on.**

## 7. Known data gaps, with plans

### GAP 1 — article body text (highest value, partially authorized)

- **What is missing:** the text of news articles. `news_capture_daily.py` stores only the RSS
  `<description>`: median **90 chars**, only **23 of 1,672** items have ≥3 sentences.
- **Why the existing proxy is inadequate:** **331 of 354** extractions (93.5%) quote evidence
  that is a verbatim substring of the *headline*. The extraction guardrail works — 353/354
  are literally grounded — but the input is a headline, so W1 is headline classification.
  That also explains `aggregator` 324/354: a headline rarely reveals the publisher's tier.
  Actionable funnel today: 354 → 137 specific → 95 non-speculative → 88 team-resolved → 23
  non-aggregator → **0 with a referenced game date**.
- **Reconstructible historically?** **No.** `data/news_capture/raw/` holds *feed* documents,
  never article pages. Bodies were never fetched. **Forward-only capture is the only path.**
- **Sources:** the same publisher URLs already captured (ESPN, AP, CBS, Yahoo, team sites,
  beat outlets).
- **Cost / constraints:** bandwidth trivial; ~300 URLs × 2 arms of Anthropic extraction is
  modest. Constraint is **robots.txt / ToS**, which is why the freeze capped it.
- **Authorization:** **already granted** — `plan_freeze_2026_07_31` F4 approves W1-I at a
  **hard 300-URL ceiling**, robots-respecting, rate-limited, cached, **prompt unchanged**
  between arms. Exceeding any of those needs a new record.
- **Sample needed:** 300 URLs for the pilot contrast; a decision on full rollout follows.
- **Time:** pilot is hours of engineering, then forward accumulation.
- **What it unlocks:** the headline-grade vs body-grade contrast (W1-I), which decides
  whether W1 becomes a live model input at all (W1-J).
- **Work that continues meanwhile:** the entire bake-off, which needs no W1.

### GAP 2 — timestamped lineup and starter announcements
Not currently captured. Would replace the failed absence-load proxy with a direct
measurement (response 3). Needs a source survey — **queued, not started**.

### GAP 3 — injury-report revision history
Official PDFs are captured hourly, but supersession between revisions is not modelled.
Partly addressable from data already on disk (22+ PDFs and growing).

### GAP 4 — official transactions / roster moves
W1-B measured **8.2% wrong-team** resolution. Trades and 7-day contracts are the hazard.

## 8. Registered next experiments, in execution order

Steps 0–3 of `PLAN_2026-07-31_W1_AUDIT_AND_BAKEOFF.md` are **done**. Remaining:

| # | step | blocked by |
|---|---|---|
| 4 | W1-C/D/E/F/G audit on the existing headline corpus | nothing |
| 5 | W1-H manual audit sample (~150, stratified) | step 4 |
| 6 | W1-I body-fetch pilot (300 URLs) | nothing — approved |
| 7 | W1-J actionable-yield answer; decide if W1 is a live input | 4–6 |
| 8 | shared as-of feature matrix, manifest-first | nothing |
| 9 | run `player_model_bakeoff_v1` arms 1→4 | step 8 |
| 10 | run `calibrated_prob_edge_v1` (no redesign) | nothing — **can start now** |

## 9. External requests awaiting John's decision

| # | request | benefit | cost |
|---|---|---|---|
| 1 | **`git push` permission in this session** — the local classifier now refuses it | 8 verified commits are stranded locally | none |
| 2 | **GitHub App → Contents: read and write** at `github.com/settings/installations` | ends the bundle hand-off for every cloud session | none |
| 3 | **Odds tier decision by ~Aug 30** | props require the paid tier — and props are where the statistical power is | subscription |
| 4 | `historical_odds` drive pull | recovers old-era line paths, possibly old totals | credits |
| 5 | 2024 totals backfill | only if historical totals work is wanted | ~7–8K credits |
| 6 | **Council scope decision** — admit lineup graph / sequence model / possession simulation? | genuine representational diversity; without them the council is 4 tabular arms + availability + market, which risks correlated residuals | these are **SCOPE-ONLY** in `PLAN_2026-07-31` §3; admitting them is a scope expansion only John can authorize |

## 10. Highest-value next action

**✅ DONE 2026-08-01 — `base_predictions_oof_2022_2023_v1`.** Reproduction gate passed at
**2.842e-14** (registered tolerance 1e-12) on the 229 registered 2024 rows *and* on the full
673-row committed intersection, so the estimator is provably identical and only the training
window differs. Emitted **435 new OOF rows**: 2022 (207 games, trained on 2021 alone —
**thin history**, flagged in the manifest) and 2023 (228 games, trained on 2021–2022).
Leakage audits PASS for both. **Fitting sample 229 → 664 games.** Artifact carries a
`asof_granularity="season"` manifest with per-season source-observation bounds and is now in
`FITTED_ARTIFACT_GLOBS` (scan 24/24 attested).

Consequence: **council ladder rungs 3–6 are unblocked** (G2 cleared).

> **Correction to an earlier claim in this file.** I wrote that the OOF extension would
> enlarge the *props* fitting sample from ~229 to ~730 games. That was wrong. Props history
> begins **2024-05-14**, so no amount of backward game-level extension adds props rows;
> `calibrated_prob_edge_v1` fit on 2024 props regardless (6,320 rows / 246 games). The
> extension enlarges the **game-level** conditional-edge sample and the **council weighting**
> basis, which is real value — but it did not help the props experiment, and I said it would.

**✅ DONE 2026-08-01 — `calibrated_prob_edge_v1`, verdict NEGATIVE** (registry run 1, report
at `experiments/calibrated_prob_edge/REPORT.md`). Details in §4.

**Next: the player-model bake-off under `council_design_v1`.** This is not a default choice —
it is what the negative result *points at*. The failure was upstream of the decision layer:
`projection − line` carries no information (`corr = +0.007`), so no betting policy built on
that projection can work, however it is tuned. The projection itself is the thing that must
improve. Prerequisite is step 8, the shared as-of feature matrix, built manifest-first.

Still open before the council can use rungs 3–6 honestly: the **scope decision** in §9 (#6).
Four tabular arms on one feature matrix risk correlated residuals, which is the one thing
that makes a council pointless.

---

### Historical note — the readiness audit that preceded the run

Recorded because the process mattered: `calibrated_prob_edge_v1` was audited *before* launch,
since it can only run once.

*What is ready.* `experiments/props_edge/bet_universe_per_book.csv` is the row-level input:
**33,610 rows, 2024–2026**, per book, carrying `line`, `over_price`/`under_price`,
`proj_used`, `actual_pts`, `exp_min`, `n_prior`, `role`, `venue` and `resolve_status`.
`master_props_historical.csv` adds **36,946 rows over 784 games / 160 players** (player_points
only, 9 books) with `last_update` **fully populated**.

*Sub-blocker 1 — `last_update` absent from the bet universe. FIXABLE.* The registration
requires prices "verified SIMULTANEOUSLY LIVE via `last_update`, staleness excluded". The
field is missing from `bet_universe_per_book.csv` but present in the historical master, so it
can be joined back. Engineering, not acquisition.

*Sub-blocker 2 — book limits are captured NOWHERE. EXTERNAL BLOCKER.* The registration also
requires "book limits applied". The Odds API does not expose limits on the current tier, so
this cannot be satisfied with data we hold or can collect at present.

**Consequence, stated plainly:** a **negative** result remains admissible (the gap *flatters*
returns, so a loss under flattering assumptions is robust). A **positive** result would be
**inadmissible** — the same defect that downgraded the earlier props study. Running the
experiment now therefore risks spending its one registration on a result we could not act on
if it came out well.

**Resolution:** John authorised the fixed-notional path on 2026-08-01;
`executability_fixed_notional_v1` was registered before the run. Sub-blocker 1 was fixed (the
join is one-to-one, so it cannot change which price row is used; **0 rows** were missing
`last_update`). Sub-blocker 2 stands — limits remain unobtainable — but the result came out
**negative**, and a negative measured under assumptions that *flatter* returns is robust. A
positive one would have been provisional.

## 11. Evidence required before the next decision

- **Before promoting anything:** an untouched prospective holdout evaluating a *frozen*
  model, with clustered intervals and the MDE written beside every bucket.
- **Before believing the bake-off:** each arm's permuted negative control must fail to beat
  the incumbent, and every fitted artifact must carry a manifest (v5 C3-BLOCKING).
- **Before W1 becomes a model input:** W1-J must show more than a token number of actionable
  pre-cutoff signals per slate, and any W1 model must be logged *alongside* core-only
  prospectively, estimating P(active), E[minutes|active] and conditional-minutes uncertainty
  separately.
- **ROI may not promote on this sample** (`plan_freeze_2026_07_31` F5). Detecting +5% ROI
  needs ~3,100 bets; we will have hundreds.

## 12. Standing operational state

- Gate: **`python verify_all.py`** — 8 checks, 35s, exit non-zero on any failure.
  `--quick` skips `daily_certify`; `--install-hook` refuses pushes unless green.
- Last full gate: **PASS**, 8/8 green, 23/23 artifacts attested, 84 tests.
- `.gitattributes` (`* -text`) is **load-bearing** — without it every manifest hash drifts on
  a Windows checkout.
