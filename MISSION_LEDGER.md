# MISSION LEDGER

*The continuing-mission record. Updated at the end of every working session so the next
session resumes without reconstructing reasoning. Last updated **2026-08-01, after
`prediction_contract_v2` was patched fail-closed. Supersedes every earlier statement in this
file about the calibrated-edge mechanism, council scope, and what the 2022-23 OOF extension
unblocks.*

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

## 3. Challengers — registered, and what has actually run

| id | what it tests | regime | state |
|---|---|---|---|
| `player_model_bakeoff_v1` | is EWMA/ridge underfitting? 4 arms: incumbent, dynamic hierarchical player profiles, CatBoost, TabPFN | A | registered, **not started** — now **amended by `council_design_v1`** |
| `council_design_v1` | does a diverse weighted council beat every individual member? | A | **registered 2026-07-31**, computes nothing yet |
| `calibrated_prob_edge_v1` | calibrated P(over) × executable odds ⇒ EV-thresholded frozen policy | A | **RUN 2026-08-01 — NEGATIVE.** See §4 |
| `executability_fixed_notional_v1` | replaces the unsatisfiable book-limits clause | A | registered, applied |
| `prob_edge_mechanism_ablation_v2` | de-vigged nested specs; supersedes v1's vig-inclusive market arm | A | **RUN - label A.** See section 4 |
| `council_scope_v2` | graph arm admitted; market excluded; five target-specific councils | A | registered, binding |
| `prediction_contract_v2` | pregame-selected universe, real tips, obligation != scoring | A | **BUILT + patched fail-closed** |
| `w1_extraction_quality_audit_v1` | what actionable pre-cutoff signal does W1 actually carry? | B | registered, **not started** |

### Council scope — settled 2026-08-01 (`council_scope_v2`)

**Five direct player-model arms:** incumbent EWMA/ridge · dynamic hierarchical · CatBoost ·
TabPFN · **lineup graph** (admitted now — the best candidate for complementary rather than
correlated residuals). It may use a different internal representation but must emit the same
player-game rows, targets and cutoffs.

**Staged, not blocking:** a *compact* sequence model after the first five-arm bake-off. If
sample, sequence length or history coverage prove inadequate, the response is to improve the
dataset or representation — **never** to tune a large network until it wins.

**Modular, not a peer:** possession simulation consumes components (availability → minutes →
usage → attempts → shot mix → conversion) and emits correlated distributions. It may not be
averaged with CatBoost unless both emit the same target distribution from the same cutoff.

**Five target-specific councils**, never one weight vector: `P(active)` ·
`E[minutes|active]` · attempts/usage · player scoring distribution · team/game distribution.
Predictions for different targets are not interchangeable votes.

**The shared artifact is a prediction contract** — a common player-game row index, cutoff and
manifest — **not** one literal feature matrix. That preserves the intent of
`council_design_v1`'s identical-inputs clause while admitting the representational diversity
this whole amendment exists to obtain.

### Two of my own guards were corrected here

`council_design_v1` replaces "which single arm wins" with "does a weighted council beat every
member". Registered **before** the bake-off ran, so it consumes no evaluation slice. Five
orchestrator-added guards are recorded in it; three change what happens next:

- **G2 — WITHDRAWN AND REPLACED by `council_scope_v2` S5.** I claimed the OOF extension
  would unblock council rungs 3–6. **That was wrong.** `predictions_v2.csv` and the 2022–23
  extension are **game-level** margin/total predictions. The council now required is a
  **player-level** council, whose weights must train on chronologically OOF **player-game**
  predictions from each arm, aligned on the same player, game, target and cutoff. The
  extension still helps the game-level conditional-edge line and a future team/game council —
  but it does **not** unblock the player-level rungs, which stay blocked until the prediction
  contract and per-arm player-game OOF exist.
- **G1 — SUPERSEDED, and strengthened, by `council_scope_v2` S4.** I proposed fitting the
  council both with and without the market. John's ruling goes further: **the market is not a
  member of the basketball council at all.** It is a mandatory benchmark, a separately
  reported blend, and the price in the decision layer — nothing else. A council that wins by
  collapsing onto the market has not created a basketball edge. With-market remains
  *diagnostic*; the **promotable** council must show independent value without it.
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
  **Mechanism - settled by `prob_edge_mechanism_ablation_v2`, not by a correlation.** The marginal-correlation argument was too weak and the replacement's first market arm was vig-inclusive; both fixed. Primary contrast (full minus de-vigged-market-plus-controls) **spans zero on all three slices**. The de-vigged market beats a constant detectably **only on 2025**. Non-projection controls *appear* harmful on 2025/2026 - a diagnostic lead, uncorrected for the comparison family, **not** a confirmed mechanism.
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
| ~~10~~ | ~~run `calibrated_prob_edge_v1`~~ | **DONE 2026-08-01 — NEGATIVE.** See §4 |

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
`FITTED_ARTIFACT_GLOBS` (scan was 24/24 at the time; **29/29** as of 2026-08-01 — see
`project_docs/GATE_LOG_2026-08-01.md`).

Consequence: **council ladder rungs 3–6 are unblocked** (G2 cleared).

> **Correction to an earlier claim in this file.** I wrote that the OOF extension would
> enlarge the *props* fitting sample from ~229 to ~730 games. That was wrong. Props history
> begins **2024-05-14**, so no amount of backward game-level extension adds props rows;
> `calibrated_prob_edge_v1` fit on 2024 props regardless (6,320 rows / 246 games). The
> extension enlarges the **game-level** conditional-edge sample and the **council weighting**
> basis, which is real value — but it did not help the props experiment, and I said it would.

**✅ DONE 2026-08-01 — `calibrated_prob_edge_v1`, verdict NEGATIVE** (registry run 1, report
at `experiments/calibrated_prob_edge/REPORT.md`). Details in §4.

**DONE - `prob_edge_mechanism_ablation_v2`, label A supported.** Nested specifications with a genuine de-vigged market comparator settled what a marginal correlation could not. Six
specifications on identical folds settled what a marginal correlation could not. The
projection adds **no incremental information** given market probability and every other
control — and is not even marginally informative. It also surfaced something new: the
**non-projection controls are actively harmful out of sample**, which is the mechanism behind
the calibration inversion.

**NEXT — `council_scope_v2` S9, the approved execution order.** Steps 2–10 remain:

| # | step | state |
|---|---|---|
| 1 | correct ledger + mechanism/permutation labels | **✅ done 2026-08-01** |
| 2 | manifest-first player-game as-of PREDICTION CONTRACT | **DONE - `prediction_contract_v2`, fail-closed** |
| 3 | chronological OOF per arm | **incumbent attempt `ac2e2f0` REJECTED** - see section 14; corrected reference required before any other arm |
| 4 | compare individual models **before** any council weights | blocked on 3 |
| 5 | residual diversity + leave-one-member-out value | blocked on 4 |
| 6 | equal-weight and median councils | blocked on 5 |
| 7 | **only then** constrained learned weights | blocked on 6 |
| 8 | compact sequence challenger, staged | after 7 |
| 9 | possession simulation, modular | after components calibrate |
| 10 | keep logging prospective core-only, **freeze-v0 unaltered** | continuous, running |

Step 2 is the real unblocker: the player-level council cannot begin until per-arm player-game
OOF predictions exist on a shared row index, cutoff and manifest.

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

- Gate: **`python verify_all.py`** — runs **12** checks, exit non-zero on any failure.
  **But they are not one kind of evidence**, and since 2026-08-01 they are reported as two layers
  that are never added together:
  - **Layer A — reproducible repository gate.** The test suites plus `asof_manifest_scan` and
    `forecast_chain`. Reads only committed files; **reproduces from a clean checkout of the commit
    and nothing else.** **`len(verify_all.REPOSITORY_CHECKS)` is the only source of truth for the
    count** — no number is hard-coded in the code, the tests or this ledger, because every count
    written down here has gone stale within a cycle. At the last run it was **12 checks / 427
    tests** (36+22+8+13+5+45+35+66+123+75), up from 8 checks / 129 tests when the split was
    introduced. The cardinality is not the invariant — the membership is: every layer-A check
    reads only committed files, and `daily_certify` is never among them.
  - **Layer B — operational certification, 1 check** — the **ninth** `verify_all` check as
    originally numbered, not a tenth; the number ten belongs to the **ten hooks `daily_certify`
    runs internally**. It reads **git-ignored, untracked and dirty** live capture data, so it is
    **environment-dependent and cannot be reproduced from a commit.** A layer-B result is only
    meaningful paired with the aggregate hash of the manifest binding its inputs.
  - **The pre-push hook runs Layer A only** (`verify_all.py --repository-gate`). A clean checkout
    cannot supply layer-B inputs and must not be refused a push for lacking files it was never
    supposed to contain. Layer B is run separately on the capture machine, always with
    `operational_input_manifest.py`. `tests/test_gate_layers.py` enforces the split, the hook's
    flag, and the absence of any cross-layer aggregate.
- Last gate — **layer A: PASS, 12/12, 427 tests, 29/29 artifacts attested, forecast chain
  `ok=True` (8 records)**, 2026-08-01T20:30:26Z–20:31:20Z, exit 0, reproduced in a clean checkout
  holding no git-ignored capture data.
  **Layer B: `WARN`, 0 fail, 1 warn, 9 pass/skip**, 2026-08-01T20:31:38Z–20:32:14Z, exit 0, bound
  to input manifest **`aef07bc3b8a9a6c2441e1f0255776f4975d612a9e3062e654834ce4c750cf762`** —
  **4,649 inputs audited across all ten `daily_certify` hooks, 4,608 committed-clean (bound by the
  commit, not hashed), 41 non-committed hashed** (36 ignored, 4 untracked, 1 dirty), 6,026,677
  bytes. The manifest was regenerated immediately before and after the run with an identical
  aggregate **and an identical producer-tree identity**. Bound set at
  **`project_docs/OPERATIONAL_INPUTS_2026-08-01T2032Z.json`**; every run window at
  **`project_docs/GATE_LOG_2026-08-01.md`**. Earlier manifests (`…T1823Z`, `…T1915Z`, `…T1954Z`)
  are **retained** as the bindings for their own runs, never replaced.
  > **Provenance correction 2026-08-01.** Manifests previously recorded only `root_commit`, which
  > was misleading: a manifest is captured from a **working tree**, normally dirty relative to
  > HEAD, whose changes become the *next* commit — so `root_commit=3096c5d` sat in a manifest whose
  > tree became `c742263`, inviting the false reading "certified at 3096c5d". A commit also cannot
  > self-identify by embedding its own final hash. Manifests now carry a **producer-tree identity**
  > — HEAD-descended-from, the digests of the operational code actually executed
  > (`daily_certify.py`, `operational_input_manifest.py`), and digests of the tracked diff and the
  > untracked-file list — plus an explicit `working_tree_clean_vs_head` flag. The last run's
  > identity is `d8126ef34b2a42eaee740bd8fd0d8cf221299602725a79a9dadc64ac367d77d3`, descended from
  > `c742263`, tree **not** clean. **No layer-B result is an exact-commit certification.**
  > **Completeness correction 2026-08-01.** An earlier manifest claimed to bind every operational
  > input while omitting the ten `data/wnba_gamelog_*.parquet` files that `daily_certify` reads in
  > its duplicate, coverage and schema checks (`daily_certify.py:156, :189, :375`). They are all
  > tracked-clean today, so the aggregate hash is unchanged — but a future dirty copy would have
  > escaped hashing while the manifest still said "complete". Declared now; audited unique paths
  > rose 4,637 → **4,647**.
  > **CORRECTED 2026-08-01.** This entry previously read *"9/9 green … run at commit `40b87c0`"*.
  > That number is **retired**: it silently added layer B to layer A and was **not reproducible
  > from any commit** — an isolated run at exact `db9f011` fails `daily_certify` because
  > `data/odds_capture/` is entirely git-ignored. The layer-A content was never wrong (129 tests
  > and 29/29 both reproduce); the aggregation was. *(An earlier correction had already fixed
  > "8 checks / 28/28": the 29th artifact is `experiments/arm_incumbent/predictions.parquet`,
  > added to `FITTED_ARTIFACT_GLOBS` at `ac2e2f0`, attested-but-REJECTED.)*
- `.gitattributes` (`* -text`) is **load-bearing** — without it every manifest hash drifts on
  a Windows checkout.

---

## 13. The prediction contract (step 2) - current state

`prediction_contract_v2`, built and then **patched fail-closed** after review. v1 is
superseded and marked DO-NOT-CONSUME in its own file.

| | |
|---|---|
| candidate rows | **35,615** over 1,458 games |
| additional recency-roster-**proxy** candidates vs v1 | 8,260 |
| appeared / not | 27,349 / 8,266 |
| tables | `pg_` 35,615 - `tg_` 2,990 - `g_` 1,495 |

**Exact-tip provenance now fails closed.** An observation supports an exact T-90m cutoff only
if its *actual* `observed_at` is strictly earlier than that cutoff. Two unsafe paths were
removed: imputing `observed_at` as `tip - 7 days`, and a fallback that accepted the earliest
observation regardless of when it became available. Both manufactured availability.

| | |
|---|---|
| observations total / rejected too late | 2,217 / **866** |
| observations missing `observed_at` | 0 |
| games exact / downgraded to date-only | **407 / 1,088** |
| exact rows failing `observed_at < cutoff` | **0** (hard post-condition) |

That is a large, deliberate loss: **377 of the 784 games previously labelled exact** had no
observation recorded before tip-90. Those labels were not defensible and are withdrawn. Only
`exact_cutoff_ok` rows may be used for exact-cutoff market comparisons.

**Lookback cannot cross a season boundary** - it was grouped by team alone, so an opener
inherited the prior season's roster. Now grouped by (team, season).

**Coverage failures stay visible, never dropped:** 37 games and 76 team-games with zero
candidates - exactly the 76 season openers, which legitimately have no in-season prior game.
Candidates per game: min 10, median 24, max 31. 15 teams, 3 absent from some seasons
(expansion GSV 2025, TOR/PDX 2026).

**Two descriptions corrected.** v1's active rate was ~84%, not ~100% - it *did* include ~5,390
DNPs; the defect is that **membership** was postgame-selected, not that all members appeared.
And the added rows are **proxy candidates**, not players v1 "should have predicted"; 76.8% is
the appearance rate *within this proxy universe*, not the WNBA availability rate.

---

## 14. REJECTED: incumbent arm attempt at `ac2e2f0`

**Do not consume `experiments/arm_incumbent/predictions.parquet`.** Raised by the Codex
supervisor 2026-08-01; every figure independently verified against the committed parquet
before acceptance. Full detail in `experiments/arm_incumbent/REJECTED.md`.

**Blocking defect.** The arm built features from `master_player` and joined to contract
candidates on `(game_id, player_id)`, so a feature row existed **only when the player also had
a target-game box row**. Dropping label columns removed the *values*, not the *membership* -
the v1 selection channel was reintroduced after contract construction.

| verified | |
|---|---|
| exclusions with `in_target_box == False` | **3,154 / 3,154** |
| target-box rows excluded | 0 |
| excluded rows with >=1 strictly prior appearance | **2,697** |
| excluded rows that later appeared | **0 / 3,154** |
| `n_prior_games` != strictly-prior appearances | **16,102 / 32,461** |

So `no_strictly_prior_observation` was **false for all 3,154**.

**The misread that matters.** I reported conditional `scoreable_coverage = 1.0000` as "exactly
as the contract intends." It was the opposite: coverage was 1.0 *because* no excluded row ever
appeared, so exclusion perfectly predicted non-appearance. An outcome-selection alarm reported
as a success.

**No accuracy result was computed or inspected** from this artifact; nothing downstream used
it. Evidence labels unchanged.

**Required before any other arm** (Codex, accepted): new registration for a target-specific
incumbent mapping; features built FROM CANDIDATE ROWS with availability-based history filters
(discard, never clamp); genuine as-of cold-start fallback; `n_prior_games` = strictly-prior
appearances; full C3 provenance (dependency hashes, producer commit, real snapshot hash,
fold-specific model hashes); an arm-level invariance suite wired into `verify_all.py`;
regeneration to a NEW artifact directory with coverage cross-tabbed by `in_target_box` and
later `appeared`.

---

## 15. Incumbent mapping audit (discovery only)

`project_docs/INCUMBENT_MAPPING_AUDIT.md`, 2026-08-01. Bounded discovery of what registered
control already exists per contract target. **No mapping registered, no model chosen, no
prediction regenerated, and no new accuracy metric computed.**

> **WORDING CORRECTED 2026-08-01** (supervisory review of `db9f011`). This entry previously read
> "no accuracy metric computed **or inspected**", which was false. A mapping audit *is* an
> inspection of committed evidence: it read Stage A's preregistered secondary Brier figures, the
> minutes-MAE gate verdicts, `props_edge_v1`'s projection-vs-line MAE table, and the already-
> committed prediction artifacts. The accurate claim is **no new metric was computed; pre-
> existing committed evidence was inspected.** Nothing was refit, rescored, or regenerated.

> **CORRECTED 2026-08-01 after supervisory review of `40b87c0`.** The original table classified
> targets on **estimand shape alone** and was too permissive. Under the **full contract**
> (prediction obligation, target support, uncertainty, cutoff policy, candidate universe,
> cold-start coverage) the count is **zero exact controls and five semantic mismatches**.

| contract target | corrected classification | reusable ingredient |
|---|---|---|
| `p_active` | **SEMANTIC_MISMATCH** | registered Stage-A logistic comparator + live Out gate as a *separately named* comparator |
| `e_minutes_given_active` | **SEMANTIC_MISMATCH** | promoted shifted minutes EWMA α=0.30 — a point-estimator **ingredient**, not a control |
| `attempts_usage` | **SEMANTIC_MISMATCH** | the volume screen's FGA/36 baseline (named in a field, not separately registered) |
| `player_scoring_distribution` | **SEMANTIC_MISMATCH** | points/36 EWMA α=0.30 × expected-minutes point projection |
| `team_game_distribution` | **SEMANTIC_MISMATCH** | promoted calibrated home/away centers + frozen live Gaussian **margin** distribution |

~~One of five targets has an exact existing control.~~
**Zero of five targets has an exact full-contract control. All five need a contract
wrapper/specification** — which is what `contract_baseline_suite_v1` (§16) froze and
`contract_baseline_suite_v2` (§17) makes executable.

Four corrections of record, each matched to a committed artifact:

1. **`p_active`.** Stage A did **not** "fail its gate" — it was **never gated**. It is
   registered as *"SECONDARY, **recorded not gated**"* and run with `record=False`, and it
   **met** its preregistered secondary Brier bar (0.07963 vs 0.10845, +0.02882, 90% CI
   [+0.02667, +0.03120]). The **parent** experiment failed its **primary** minutes-MAE gate
   (+0.0370 vs a required +0.10) and carries `promote: false`. Stage A is a reproducible
   **non-promoted comparator**, not an incumbent. It scored **16,323** rows of which
   **5,892** are availability-covered; it did not apply "only to the covered subset".
2. **`e_minutes_given_active`.** α=0.30 is promoted and reusable, but the registered artifact
   predicts only **regular-season played rows with >= 1 prior same-season played appearance**
   (13,501 rows vs the contract's 35,615 required), emits **no predictive sd**, is registered at
   **T-24h**, and satisfies neither the every-candidate obligation nor a cold-start path. Its
   gate-5 coverage of 1.0 is **circular** — computed over the already-filtered frame.
3. **`attempts_usage`.** The VOID verdict voids the screen's **null**, not the baseline — but
   `player_volume_ewma_baseline` has **no registration record of its own** (it is only the
   experiment-level `incumbent_id` string), the report selected **`ratio_ewma`** rather than
   EWMA-of-rate, and α=0.05 sits on a **monotone curve at the grid floor**, so the minimising α
   is unidentified. Still a mismatch: FGA/36 is a rate, not the contract's raw conditional
   count, with no sd and coverage of only 11,948 rows (2021-2024, minutes >= 8, >= 5 prior).
4. **`team_game_distribution`.** The claim that a **total distribution** exists is **withdrawn**
   — the total is a **point** forecast with no sigma anywhere. What exists is the promoted
   calibrated home/away **point centers** and a frozen live Gaussian **margin** sigma (12.9022,
   `daily_forecast.py:113`). Neither is a team-points distribution with per-team sd, and no
   committed artifact emits one.

Additionally, `props_edge_v1`'s **T-90m label is unenforced**: no cutoff logic exists in the
module, its line vintage is median **T-69.4m**, its projection gate is **date-level**, and under
the contract's fail-closed rule only **2 of 784** props observations qualify — with **0 of 262**
2024 games certifiable.

Ambiguities remaining for the specification decision: live recency window is 3 games vs the
contract's 5; cutoff disagreements throughout; the live EWMA's shift semantics need confirming
by reproduction; and `p_active` has no promoted probabilistic control at all.

### Commit-scope contamination in `40b87c0` — labelled, not erased

`40b87c0` was staged with a broad `git add data/ logs/` and swept in concurrent capture output
unrelated to the mapping conclusion: **83** `data/news_capture/news_items.csv` rows (all batch
`20260801T154504Z`) and **27** `data/w1_extractions/extractions.jsonl` records (all
`extracted_utc 2026-08-01T15:46:10Z`, **all carrying `skip_reason: duplicate_title`**). The
commit is timestamped 15:50:22Z. These are genuine prospective capture records: they are
**preserved**, the pushed commit is **not** rewritten, and **no conclusion depends on them**.

**Process correction, effective now:** stage explicit paths; capture artifacts get their own
named commit. `.claude/` is **not** gitignored and now contains worktrees, so `git add -A` from
the repo root would commit them — explicit-path staging is load-bearing.

---

## 16. `contract_baseline_suite_v1` — registered, definition only — **SUPERSEDED, see §17**

> **SUPERSEDED 2026-08-01 by `contract_baseline_suite_v2` (§17).** v1 was a genuine no-output
> freeze but was **not executable** — five rules it named were never stated, and its claim that
> points α = 0.30 was "tuned on 2021-2023" is **false** (that is the *minutes* provenance).
> v1's registry record is **not mutated**; this section is retained as the historical record.

`project_docs/CONTRACT_BASELINE_SUITE_V1.md`, registered 2026-08-01 **before any output**.
**Nothing has been computed**: no prediction, fitted parameter, accuracy figure, coverage score
or prediction file exists for this suite, and none was inspected. The registry record carries
`computed_nothing: true`, and `register()` touches no data and fits nothing.

This replaces the inaccurate phrase *"the current EWMA/ridge player layer, unchanged"* used when
`arm_incumbent` was attempted at `ac2e2f0`. §15 establishes there is no such unchanged layer.
It is a **registered baseline suite** — the reference later council members must beat — and
**not** a previously promoted incumbent arm, not a promotion candidate, and not evidence. Its
registry thresholds are **sentinels**.

Frozen before any output: the common contract-v2 layer (35,615 pg / 2,990 tg rows, two cutoff
classes reported separately, `season:<YYYY>` chronological folds, the obligation/scoring split,
per-row provenance, and the fail-closed `validate_predictions()` check), plus per target:

| target | component id | note |
|---|---|---|
| `p_active` | `cbs1_pactive_logistic_histonly` | history-only Stage-A logistic, **refit within each training fold**; Out gate reported as `cbs1_pactive_rulegate_comparator`, never relabelled a probability |
| `e_minutes_given_active` | `cbs1_eminutes_ewma_a030` | promoted shifted minutes EWMA α=0.30 as a point-estimator ingredient |
| `attempts_usage` | `cbs1_attempts_fga36_x_minutes` | shifted FGA/36 EWMA α=0.05 × minutes/36 — **NEW COMPOSITION** |
| `player_scoring_distribution` | `cbs1_points_pts36_x_minutes` | shifted points/36 EWMA α=0.30 × minutes/36 — **NEW COMPOSITION** |
| `team_game_distribution` | `cbs1_teampoints_structural_cal` | promoted calibrated structural home/away centers; margin Gaussian kept distinct as `cbs1_margin_gaussian_comparator` |

Also frozen: **strictly training-fold** residual sd/quantiles with truncation, support rules and
monotone quantiles; **deterministic training-only fallbacks** so every required row is predicted,
with `is_fallback` / `is_cold_start` flags and the fallback stratum always broken out; the 76
zero-candidate team-games kept **visible**; and a standing obligation to cross-tab every
exclusion by `in_target_box` and `appeared` — the `ac2e2f0` outcome-selection trap.

**`season:2021` has an empty training set** (`seasons < 2021`), so the entire fold takes the
fallback path and is reported as its own stratum, never pooled silently.

**Three open questions are frozen with it, awaiting a supervisory ruling before any OOF is
generated:** (1) the instructed *"shifted FGA/36 EWMA"* differs from the artifact's selected
`ratio_ewma`; (2) α=0.05 is a grid-boundary corner on a monotone curve, so the minimising α is
unidentified; (3) the inherited α=0.30 values were tuned on 2021-2023, which overlaps predicted
folds, so they are frozen as fixed constants and must not be called fold-honest.

**Status: no chronological OOF predictions generated. The dynamic hierarchical arm is not
begun.**

---

## 17. `contract_baseline_suite_v2` — registered, definition only — **SUPERSEDED, see §18**

> **SUPERSEDED 2026-08-01 by `contract_baseline_suite_v3` (§18).** v2 was executable but **not
> pipeline-honest**: the same inner validation segments selected the hyperparameters *and* supplied
> the dispersion residuals. v2's registry record is **not mutated**; this section is retained as
> the historical record.


`project_docs/CONTRACT_BASELINE_SUITE_V2.md`, registered 2026-08-01 **before any output**.
Registry append was **1 insertion, 0 deletions** (79 → 80 records); the record carries
`computed_nothing: true` and `definition_only: true`, and `config_hash`
**`7ad8c09742bcbe89e469c7647d5026f5444ec85660ee713f0a921c3c9abeadb9`** verifies under the same
self-referential convention v1 used. **v1's record was not touched.** No new metric was computed;
pre-existing committed evidence (feature lists, grids, promoted alphas, calibration coefficients)
was inspected in order to *specify* the estimators.

**Why v2 exists.** v1 was frozen but **not executable** — two engineers reading it could not have
produced the same numbers. v2 states the five missing rules and rules on v1's three open
questions.

| v1 defect | v2 |
|---|---|
| `p_active`: no feature vector, standardisation, λ grid, tie-break, minimum-history or low-data rule | exact 14-feature history-only vector, `ddof=0` standardisation refit at every fit, 13-point log-λ grid, Brier selection, **ties → smallest λ**, no minimum-history requirement |
| `season:2021` constants "declared here" — but none were | full numeric point/sd/quantile table, derived from **declared structural arithmetic**, never from a season's outcomes |
| "training-fold residuals" — in-sample or out-of-sample? | **chronological inner-OOF (prequential) only**; residuals from the fit that produced the center are **forbidden**. Estimator, min sample (200 / 30), `ddof=1`, `numpy.quantile(method="linear")`, fold-global pooling and fallback all frozen |
| team centers reused with no fold-honest refit rule | channel alphas **and** the two-parameter linear calibration maps **refit inside every outer training fold**; the fixed 2021-2023 fit becomes a named legacy sensitivity |
| "points α = 0.30 was tuned on 2021-2023" | **false and corrected** — `props_edge.py:203` declares `ALPHA = 0.30  # registered frozen family` |

**Supervisory rulings applied.** (1) `attempts_usage` uses the **artifact-selected**
`ratio_ewma = EWMA(FGA)/EWMA(minutes) × 36`, not the EWMA of the FGA/36 rate v1 froze; the raw-
attempts composition stays labelled **NEW**. (2) The attempts α grid is predeclared with a floor
of **0.01** — the old sweep's floor was 0.05 on a monotone curve, so 0.05 was never an identified
optimum; a boundary solution is **retained and reported**, never fixed by widening the grid after
the fact. (3) Minutes-rate, points-rate and team channel alphas are all selected **inside each
outer training fold**; fixed versions survive only as named legacy sensitivities with explicit
contamination windows.

One asymmetry is recorded rather than quietly enjoyed: the minutes legacy α=0.30 **is**
outcome-contaminated on folds `season:2021-2023` (it was tuned against those outcomes), while the
points legacy α=0.30 is **not** contaminated on any fold (it was *declared*, never tuned). The two
legacies do not carry the same status.

`season:2021` remains its own cold-start stratum — every row flagged, reported separately, and
**excluded from every pooled headline score and every council/meta-weight fit**. If its declared
constants prove poor, that is a finding to report, **not a licence to retune them**.

**Status: no chronological OOF predictions generated.** v1's open-question block is lifted by this
registration, but generation itself awaits supervisory review of this record. The dynamic
hierarchical arm is **not** begun. `arm_incumbent` remains **rejected and unconsumed**.

---

## 18. `contract_baseline_suite_v3` — registered, definition only — **SUPERSEDED, see §19**

> **SUPERSEDED 2026-08-01 by `contract_baseline_suite_v4` (§19).** v3 froze the right ideas but
> its helpers were **useful primitives rather than the registered pipeline**, and five points let
> contamination back in. v3's registry record is **not mutated** and its document is **not
> edited**; the erratum lives in `project_docs/SPEC_ERRATA.md`.


`project_docs/CONTRACT_BASELINE_SUITE_V3.md`, registered 2026-08-01 **before any output**.
Registry append **1 insertion, 0 deletions** (80 → 81); `computed_nothing: true`; `config_hash`
**`b8d22ec8c3d4584a3bba97f9cc47ba64d369e0f91f29f0e38560b33da595733e`** verifies by recomputation.
**Neither the v1 nor the v2 record was touched**, and the 80-line registry is the exact byte prefix
of the 81-line registry.

**The correction that forced v3.** v2 derived dispersion from "chronological inner-OOF residuals"
— out-of-sample with respect to the *fit*, but the very same three validation segments had already
chosen α and λ. The selected pipeline is the one that looked best on those rows, so its residuals
there are biased small and **every prediction interval would have been too narrow** — a bias no
single-arm check would surface. v3 freezes a **disjoint chronological calibration tail**:

- **player targets** — training window cut on *distinct dates* (so no slate straddles the
  boundary): first **75 %** tunes, last **25 %** calibrates, minimums 8 and 4 distinct dates;
- **team points** — **three** disjoint segments, because the calibration map is itself fitted:
  **T1** (50 %) channel α, **T2** (25 %) calibration-map fit, **T3** (25 %) dispersion;
- **degenerate windows** are reported and fall back to declared constants. They may **not** reuse
  tuning residuals, and the builder makes that unrepresentable by returning an empty calibration
  index.

**Four further corrections.** (1) Target-specific masks frozen: `p_active` tunes on **all**
candidate obligations; the three conditional targets on **active, outcome-scoreable** rows only;
team points on **resolved** team-games. (2) Stage-A history is built on prior **contract candidate
obligations**, with `n_prior_candidate_games` and `n_prior_appearances` recorded separately — so
**0 appearances across k>0 obligations is `0/k`, real evidence**, and the base-rate default is
reserved for rows with *no prior obligation at all*. Conflating them would have overwritten
evidence with a league average for exactly the players least likely to play. (3) The `p_active`
feature order is canonical and positional, and a test asserts the document, the registry record and
`cbs_builders.py` agree. (4) Tuning order is explicit: minutes α first, then attempts and points
α **after composition with the minutes leg held fixed**, since a rate α chosen against a floating
minutes leg would absorb minutes error.

**A v2 over-claim withdrawn.** v2 reasoned that because no points-target tuning curve exists,
points α = 0.30 must be outcome-independent, hence fold-honest and weight-eligible everywhere.
**Absence of a record is not evidence of independence.** Provenance and contamination are now
labelled **UNKNOWN** and the legacy is **sensitivity-only on all folds**. Neither α = 0.30 legacy
is weight-fit eligible.

Team-points positivity floor frozen numerically at **`1e-6`**.

**Executable, and demonstrated so.** `cbs_builders.py` implements the split, the obligation
history, the shifted estimators, the ordered masked α selection and the quantile emission;
`tests/test_cbs_builders.py` exercises them on **synthetic toy data only** (66 assertions,
including a deliberately corrupted split that must raise `SelectionLeakage`, and a leakage probe
that perturbs one outcome and requires no feature to move). Both are wired into the repository
gate.

**Status: no historical OOF, fitted suite artifact, accuracy or coverage result generated.**
Generation into a new v3 artifact directory awaits supervisory review; validation, provenance,
obligation coverage and the exclusion cross-tabs must all pass **before any accuracy metric is
inspected**. The dynamic hierarchical arm is **not** begun.

---

## 19. `contract_baseline_suite_v4` — registered, implemented — **SUPERSEDED, see §20**

> **SUPERSEDED 2026-08-01 by `contract_baseline_suite_v5` (§20).** v4's *specification* was sound;
> its **implementation differed materially from it**. v4's registry record and document are
> **not mutated**, and its implementation files (`cbs_generator.py`, `cbs_pipeline.py`) are left
> exactly as registered.


`project_docs/CONTRACT_BASELINE_SUITE_V4.md`, registered 2026-08-01. Registry append **1
insertion, 0 deletions** (81 → 82); the 81-line registry is the exact byte prefix of the 82-line
registry and **the v1, v2 and v3 records are all unchanged**. `config_hash`
**`190b9e26c0de3ccdecce87297a762bc57367792eb9314e7ded3d14763e59bcef`** verifies by recomputation.
**No real contract row has been read, and no historical OOF, accuracy or coverage figure exists.**

**Why v4.** v3's helpers proved *useful primitives*, not the registered pipeline, and five points
let contamination back in through the side door:

1. the team **T1/T2/T3 split cut on team-game rows**, so one game's two rows — and two games on a
   date — could land in different segments, putting one team's outcome in the segment fitting the
   other's calibration map. v4 cuts on **distinct dates**, with frozen floor rounding
   (`n_t3 = n_t2 = floor(n·0.25)`, T1 takes the remainder), minimums 8/4/4, and an explicit
   degenerate fallback that empties T2 and T3 rather than borrowing;
2. **selection took bare frames.** Returning disjoint arrays does not make contamination
   *unrepresentable*. Every v4 selection API takes a `SplitContext` and raises `SelectionLeakage`
   on any calibration or test index; an overlapping context cannot be constructed. **The guard
   rejected this pipeline's own first run twice** — whole-frame masks for the `p_active` base rate
   and for team channel-α — each of which would otherwise have returned a plausible number
   computed partly on calibration rows;
3. **obligation ordering was unpinned.** Now `(player_id, season, forecast_cutoff, game_id)`,
   stable sort, **failing closed** on indistinguishable duplicates or a missing key;
4. **a constant residual pool yields `sd = 0`** — finite, so v3 accepted it, but the contract
   requires `pred_sd > 0`. Nonfinite *or* nonpositive sd is now **insufficient** and routes to the
   declared fallback;
5. **base rates and fallback means** are computed only from tuning indices, through the same guard.

A sixth defect surfaced while implementing and is fixed rather than left latent: **conditional
history ran the EWMA over every obligation**, so a DNP row's recorded zero moved the estimate and
therefore the selected conditional α — defeating the target-specific masks by another route.
Conditional history is now the **active subsequence only**, strictly as-of, never reading an
inactive outcome. `p_active` is deliberately unaffected: inactive rows are what it exists to
predict, and they still move its base rate.

**Implemented and demonstrated.** `cbs_generator.py` (guarded primitives) and `cbs_pipeline.py`
(the end-to-end fold runners) contain **no file I/O whatsoever** — no path argument exists — so the
pipeline cannot reach real data even by mistake. `tests/test_cbs_generator.py` drives every stage
on **synthetic frames only** with **123 assertions**, including all eight required negative /
invariance tests (N1 calibration- and test-outcome invariance; N2 contaminated calls rejected;
N3 inactive rows move `p_active` but not conditional tuning; N4 game- and date-integrity of the
team segments; N5 zero-candidate and excluded obligations visible plus the outcome-selection alarm;
N6 constant/degenerate pools fail closed; N7 duplicate obligations fail closed; N8 validation,
provenance, coverage and quantile monotonicity gate any scoring path). Output is checked with the
**real** `prediction_contract_v2.validate_predictions()`, not a stand-in.

**Status: definition plus synthetic implementation only.** Generation into a new v4 artifact
directory awaits supervisory review; validation, provenance, obligation coverage and the exclusion
cross-tabs must all pass **before any accuracy metric is inspected**. The dynamic hierarchical arm
is **not** begun. `arm_incumbent` remains **rejected and unconsumed**.

---

## 20. `contract_baseline_suite_v5` — corrected primitives — **SUPERSEDED, see §21**

> **SUPERSEDED 2026-08-01 by `contract_baseline_suite_v6` (§21).** v5 corrected the primitives but
> shipped **no end-to-end runner**, so none of its corrections reached a generated contract row.
> v5's registry record and document are **not mutated**; the erratum is in
> `project_docs/SPEC_ERRATA.md`.


`project_docs/CONTRACT_BASELINE_SUITE_V5.md`, registered 2026-08-01. Registry append **1
insertion, 0 deletions** (82 → 83); the 82-line registry is the exact byte prefix of the 83-line
registry and **v1-v4 records are all unchanged**. `config_hash`
**`ea701817e5f87caf3fe1041037cd8bec430df95d9c25e6128fa4db4f9ec5afda`** verifies by recomputation.
**No real contract row has been read; no historical OOF, accuracy or coverage figure exists.**

**v4's specification was sound; its implementation was not.** Eight defects, each confirmed by
direct reproduction before being fixed — all of which would have produced *confidently wrong
numbers* rather than errors:

1. **λ tuning was not chronological.** It sliced tuning *row indices* 75/25, and because
   obligations are ordered by player the fit side held **P0-P5** while validation held **P6-P7**,
   with **all 36 dates on both sides**. v5 cuts on distinct dates (floor 25% tail, minimums 6/2,
   degenerate → declared default).
2. **The team runner never ordered its rows**, so a later game could become history for an earlier
   one. Shuffling identical frames moved predictions by **up to 5.9 points** here (16.1 in the
   supervisor's reproduction) and dispersion **8.38 → 8.27**. v5 sorts explicitly on the
   registered `run_reval` keys before every grouping, and shuffle-invariance is tested.
3. **One pooled calibration map** where the spec requires **separate home/away** maps — and no
   side indicator was required at all. Now both are required.
4. **The residual sign was inverted**: residuals were `prediction - outcome` while offsets are
   *added* to the point, so every asymmetric empirical quantile came out **mirrored**. Now
   `outcome - prediction`, with the inverted convention reproduced in a test.
5. **Missing channels were silently dropped**, quietly turning the registered four-channel
   estimator into a different model. Now fail-closed.
6. **Fitted hashes were incomplete** — only the coefficients — so fits differing in scaler, λ or
   feature order could share one `model_hash`. Now the complete fitted state, with a fail-closed
   real-adapter identity boundary.
7. **Cold-start ignored the target.** A player with prior obligations but **zero prior
   appearances** has no conditional history at all, yet was marked non-cold; team rows always
   reported zero prior games. Now target-specific.
8. **Stage-A silently zero-filled** absent features and trusted caller-supplied `feature_asof`.
   Both now fail closed, with `feature_asof` derived from the maximum actual source timestamp.

**Team history is taken from the registered family, not approximated**: sort
`(team_id, game_date, game_id)`, group `(team_id, season)` so history **resets each season**,
`prior_games = cumcount`, `MIN_PRIOR = 5`, channels `ft/3pt/paint/np2`
(`run_reval.py:59-61, 86, 89, 102`).

**A strict validator, alongside the unchanged historical one.**
`contract_validator_v2_strict.py` (`contract_v2_strict/1`) validates the same v2 row universe and
adds what the historical validator never checked: universe-joined `fold_id` and `forecast_cutoff`,
target identity and support on point **and** quantiles, sd required-positive or required-null,
boolean and prior-count types, hash format and expected hashes, strict feature-as-of. The
historical validator is **not rewritten** — other registered artifacts were checked against it.
**Passing it is necessary but not sufficient**, and the suite *measures* how many mutations it
misses rather than asserting it.

`tests/test_cbs_v5.py` — **75 assertions, synthetic only**. v4's implementation files are left
exactly as registered.

**Status: definition plus corrected synthetic implementation.** Generation into a v5 artifact
directory awaits supervisory review; validation, provenance, obligation coverage and exclusion
cross-tabs must pass **before any accuracy metric is inspected**. The hierarchical arm is **not**
begun.

---

## 21. `contract_baseline_suite_v6` — the runner that was missing

`project_docs/CONTRACT_BASELINE_SUITE_V6.md`, registered 2026-08-01. Registry append **1 insertion,
0 deletions** (83 → 84); prefix byte-identical, **v1–v5 records unchanged**. `config_hash`
**`4857907f8f338bd9bafbcf22847da56f3f22785159a7d65b4f1381e2a02ec0f7`** verifies by recomputation.
**No real contract row read; no OOF, accuracy or coverage figure exists.**

**Why.** v5 corrected the primitives and stopped there: `cbs_v5.py` ended at
`resolve_feature_asof`, with no fold runner, emission path, fitted-state constructor, validation
composition or call site outside its own tests. **So none of v5's corrections reached a generated
contract row** — the only executable runners were still v4's, with v4's defects and v4's arm
identity. v5's "corrected implementation" label was too strong; the erratum is in
`project_docs/SPEC_ERRATA.md` and v5's document is untouched.

**What v6 adds.** `run_player_fold` / `run_team_fold` over the corrected primitives; all five
targets emitted for every obligation; a versioned **`cbs_history_audit/1` sidecar** persisting
`n_prior_candidate_games` and `n_prior_appearances` per row (v5 computed them and dropped them, yet
they are the evidence that 0-of-k was treated as evidence); target-specific cold/fallback **bound
into the emitted rows**; an explicit **`FittedState`** per fold and target so `model_hash` covers
the real fitted objects; strict real-boundary identity; and **one composite fail-closed receipt**
(historical validator AND strict validator) with `scoring_permitted` gated on it.

**Validator hardened to `contract_v2_strict/2`**: the four expected identities are now
**mandatory** (they defaulted to `None`, making identity binding optional); the universe must carry
`fold_id` and `forecast_cutoff`; points and quantiles must be **finite**; `p_active.pred_sd` must
be *actually* null rather than non-numeric coerced; flags must be genuine booleans, not numeric
0/1; excluded rows must carry **null values and full identity lineage**; and a malformed frame
returns a verdict instead of raising.

**Operational provenance corrected.** `OPERATIONAL_INPUTS_…T2032Z.json` attested
`operational_input_manifest.py = c1231b…`, the **parent** version — code that could not have
written the `producer_tree` structure it was attesting, because `producer_tree_identity` hashed
`root/<name>` while the executing code lived in the worktree. The generating file is now hashed via
`__file__` with a self-check, root copies are recorded separately with an explicit
`producer_code_mismatches` list, untracked files are hashed by **name and content** (names alone
collided), and the "iff the tree agreed" claim is **narrowed** to a declared `identity_scope`.

`tests/test_cbs_v6.py` — **104 runner-level assertions, synthetic only**. Four assertions in
`tests/test_cbs_v5.py` had begun passing for the wrong reason once identity became mandatory; they
were corrected to bind identity and assert *which* problem was raised (75 → 79).

**Status: definition plus complete synthetic runner.** Real-contract execution awaits supervisory
review. The hierarchical arm is **not** begun.
