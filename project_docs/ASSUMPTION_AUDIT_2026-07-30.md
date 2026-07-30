# ASSUMPTION AUDIT — 2026-07-30 (red-team pass)

*Read-only audit of the project's load-bearing assumptions against the evidence actually on
the ledger. Sources: `ROADMAP.md`, `project_docs/HANDOFF.md` §3–§8, `project_docs/HANDOFF_2026-07-30.md`
(incl. §0), `project_docs/MINUTES_MODEL_SPEC.md`, every record in `experiments/registry.jsonl`
(17 lines: genesis + 7 registrations + 8 evaluation records + 1 superseded registration), the four
`leaderboards/*.md`, the REPORT.md files in `experiments/{channel_reval, minutes_baselines,
minutes_twostage, oracle_bracket, w6_retrospective, w5_closing_line, rapm_v0}`, and
`data/refresh_2026/AUDIT_REPORT.md`. Rules honored: nothing was run, nothing modified except this
file; every number below is quoted from a named artifact; where no artifact exists the word is
**untested** — no new numbers were produced by this audit (unregistered results are void per the
registry genesis note).*

**Scale anchors used throughout** (so deltas can be read honestly):
model-vs-avg-bookie pooled margin gap **0.373** MAE on the odds-covered 626-game test subset
(`experiments/oracle_bracket/REPORT.md` bookie-gap table); the standard promotion bar is
**0.10** pooled (ROADMAP §Standard promotion gate; `evalharness/registry.py:87` — "default
template value: 0.10 points for game-margin models"); median open→close line movement is
**0.5 pts**, p90 **2.5 pts** (`experiments/w5_closing_line/REPORT.md` §3).

---

## Verdict table

| # | Assumption | Verdict | Recommendation |
|---|---|---|---|
| 1 | 0.10 practical-improvement bar is betting-aligned | Not supported — template constant, never value-derived | **Amend + test-next** (E2) |
| 2 | MAE-primary is adequate while the betting layer waits | Not supported — PROBABILISTIC/BETTING boards empty | **Test-next** (E1) |
| 3 | Train-years calibration (slope ≈0.78, +1.5 home) era-stable through 2026 | Partially supported; drift never measured | **Test-next** (cheap, E5b) |
| 4 | Charter break invalidates 2021–23 schedule features | Plausible, **untested** as encoded; adjacent evidence supports concern | **Test-next** (cheap, E5c) |
| 5 | Shifted-EWMA-is-enough (rule 3) | Strongly supported for level targets; falsified for its alpha-range clause; fails to transfer to probability targets | **Amend** (rewrite rule 3 scope) |
| 6 | Regime-B strictly-prior-day conservatism costs little | Cost never quantified; provably discards W1 intraday timestamps | **Test-next** (counting exercise, no model) |
| 7 | Regular-season-only minutes system is acceptable | Untested both directions (no playoff line-softness evidence either) | **Test-next** (E5a split) |
| 8 | LINEUP_SCALE=4.0 additive bracket ⇒ "gap mostly not lineup info" | Over-claimed — conclusion is mechanism-conditional | **Amend** wording; E3 is the real test |
| 9 | Odds-ban honored AND permission exploited | Ban: supported. Exploitation: zero registered results; gap number is timing-asymmetric | **Amend + test-next** (E2) |
| 10 | W1 news is forward-only | Supported for pregame designations; partially untested for timestamped news archives | **Keep + cheap probe** |
| 11 | Misc. settled-but-unsupported items (below) | — | see §11 |

---

## 1. The 0.10-point practical-improvement bar

**As stated:** "Pooled MAE (or the registered primary metric) improves by ≥ the preregistered
meaningful amount (default 0.10 points for game-margin models)" — `ROADMAP.md` §Standard
promotion gate (gate 1). Encoded in `evalharness/registry.py:86-87` and copied as
`min_improvement: 0.1` into **every** margin *and minutes* registration on the ledger
(`experiments/registry.jsonl` lines 2, 3, 8, 11, 12, 15, 16, 17 — the only exception is W6 at 0.02).

**Evidence FOR:** It did its anti-noise job. `oracle_availability_bracket_v2` run 1: +0.0198
pooled, 90% CI [−0.0241, +0.0625] — CI spans zero; correctly not promoted
(`experiments/registry.jsonl` eval line; `experiments/oracle_bracket/REPORT.md`). The
constitution's fear of "three tiny point wins (promoting noise)" (`ROADMAP.md` gate note) is
legitimate: every pre-harness sub-9.5 result was leakage (`HANDOFF.md` §7).

**Evidence AGAINST:**
- The bar discarded a **CI-certified real** gain: `minutes_twostage_availability_v1` +0.0370
  pooled with 90% CI [+0.0116, +0.0613] — excludes zero, better in all three seasons
  (2024 +0.0215 / 2025 +0.0383 / 2026 +0.0526) — verdict FAIL on gate 1 alone
  (`experiments/minutes_twostage/REPORT.md`). "Real but small" and "indistinguishable from
  zero" (oracle v2) get the identical verdict; the ledger distinguishes them, the leaderboard
  verdict column does not (`leaderboards/FORECASTING.md` rows 1 and 4, both "FAIL").
- The same numeral 0.10 is applied across **different units and consumers**: margin points
  (game model), minutes (whose consumer is the aggregation layer, gate 4 recorded
  `not_provided` in both minutes experiments — `registry.jsonl` minutes evals), and M3
  expected-minutes. No artifact derives 0.10 from anything downstream.
- Power is not the constraint for small-perturbation challengers: the paired date-clustered
  CI half-width on oracle v2 was ≈0.043 (CI [−0.0241, +0.0625]) on 627 games — a true
  0.05-pt effect is detectable. The bar is a *value* judgment, and the value question is
  unanswered: the **BETTING board has zero rows** (`leaderboards/BETTING.md`: "No registered
  evaluations on this board yet"), so no experiment has ever measured what a margin-MAE delta
  is worth in ROI/CLV.
- Scale mismatch: the entire model-vs-book gap is 0.373 (`oracle_bracket/REPORT.md`); a
  promotion bar equal to 27% of the whole remaining gap guarantees that the endgame — which
  must close the gap in slices — will consist mostly of individually sub-bar improvements.

**What bar would betting ROI imply?** **Untested.** The artifact base to answer it exists
(`experiments/oracle_bracket/game_level_margins.csv` per-game margins for v1/v2;
`data/odds_capture/master_odds_extension.csv` with per-book prices per
`experiments/w5_closing_line/REPORT.md` §5) but no registered study converts an MAE delta into
a bet-set change, CLV, or ROI. Note the market's own granularity: spreads move in 0.5-pt steps
and the median total open→close move is 0.5 pts (`w5_closing_line/REPORT.md` §3) — the
practical betting question is not pooled MAE but how often a delta flips which side of a
half-point the model sits on. That frequency is exactly what the transfer study (E2) measures.

**Cheapest falsifying test:** E2 below — flat-stake paper simulation over the odds-covered
test games using the *already-committed* v1 vs v2 prediction files; if the +0.02 margin delta
produces a materially different bet set / CLV, the bar is misaligned; if it produces nothing,
0.10 is vindicated empirically.

**Recommendation: AMEND + TEST-NEXT.** Keep gate 2 (CI excludes harm) as the noise guard;
re-derive gate 1's threshold per consumer from the E2 transfer curve; add an explicit ledger
status for "CI-positive, sub-bar — bankable, not promoted," and preregister a **stacking
experiment** (two-stage minutes + zone overlay + ref prior jointly) to test whether banked
sub-bar gains clear the bar together — that is the legitimate version of "three tiny wins."

---

## 2. MAE-primary while the betting layer needs calibrated distributions

**As stated:** "Metrics (probability quality is first-class): … pinball loss … CRPS
(distributional); cover-probability Brier; log loss; reliability/calibration plots"
(`ROADMAP.md` §Metrics). Encoded in practice as: `primary_metric` is `margin_mae` or
`minutes_mae` on every registration except W6 (`experiments/registry.jsonl`).

**Evidence FOR (MAE-primacy so far):** MAE is the historically comparable metric (frozen
baselines 11.22 / 10.53 / 9.54, `leaderboards/FORECASTING.md`), and the leakage battery is
built around it. The one probability-quality result that exists was decisively positive:
Stage-A Brier 0.0796 vs 0.1084 expanding prior, delta +0.0288 ≥ bar 0.005, CI
[+0.0267, +0.0312] (`experiments/minutes_twostage/REPORT.md` M2).

**Evidence AGAINST:**
- `leaderboards/PROBABILISTIC.md`: "**No registered evaluations on this board yet.**" No
  margin/total distribution, no CRPS, no cover-probability Brier exists anywhere on the
  ledger. The betting decision layer (system 3) consumes cover probabilities; none have ever
  been produced.
- Even the existing Brier result is invisible on the probability board: it lives inside the
  minutes experiment's run-2 secondary record (`registry.jsonl` run 2) because the
  experiment's *primary* metric routed it to FORECASTING. First-class in prose, second-class
  in the ledger.
- The Stage-A reliability table — cited in `HANDOFF_2026-07-30.md` §0.1 as "well calibrated" —
  shows the mid-probability bin overconfident: predicted 0.598 vs observed 0.528 (n=1,632),
  and bin 1 underconfident 0.215 vs 0.237 (`experiments/minutes_twostage/stage_a_reliability.csv`).
  Tails are excellent; the 0.43–0.75 region — precisely the "Questionable" zone the betting
  layer cares about — is off by ~7 points. No calibration-correction experiment exists.
- The ledger's own pattern (see assumption 5) is that **level targets are EWMA-saturated
  while probability targets rewarded model capacity** — the largest relative win on the
  ledger is the Brier one (26.6% relative). The project is spending on the saturated axis.

**Cheapest falsifying test:** E1 below — distributional layer over the already-committed
`experiments/channel_reval/predictions_v2.csv` (673 rows, calibrated + uncalibrated), scored
by CRPS/cover-Brier/log-loss against the T≈64m lines in `data/drive_masters/master_odds.csv`
+ extension. One day, no new data.

**Recommendation: TEST-NEXT (highest priority).** Until a cover-probability experiment posts
to PROBABILISTIC, the project cannot know whether its 0.373 MAE deficit even matters — a
worse-MAE model with honest variance can still price sides profitably, and ROADMAP Phase 3
already concedes this ("a model can lose globally and win in a calibrated subset").

---

## 3. Train-years calibration (slope ≈0.78, home intercept ≈+1.5) era-stable through 2026

**As stated / encoded:** final calibration is "train-years-only linear (slope ≈ 0.78 shrinkage
+ home-court intercept ≈ +1.5)" (`HANDOFF.md` §4); executed as a = 1.517, b = 0.779 fit on
2021–2023 only (n=610) and applied unchanged to 2024/25/26 (`experiments/channel_reval/REPORT.md`
calibration paragraph and deviation 4: "stricter than expanding-window refits").

**Evidence FOR:**
- Slope reproduction across rebuilds: 0.779 vs July's 0.783 ("reproduces July's 0.783 almost
  exactly" — `channel_reval/REPORT.md`).
- 2024 out-of-sample MAE reproduces July within 0.03 (8.936 vs 8.97, same report).
- All five gates pass with 2025/2026 included; worst-season delta +0.408 ≥ −0.15
  (`registry.jsonl` chanreval eval).

**Evidence AGAINST:**
- The improvement decays monotonically across eras: +1.028 (2024) → +0.434 (2025) → +0.408
  (2026) (`channel_reval/REPORT.md`).
- The 2026 environment shifted: "scoring environment is up (FT 16.7, paint 38.9 per
  team-game)" vs ~35–36 prior; the 3pt structural edge is absent in 2026 (channel Δ +0.045,
  P=0.367) (`channel_reval/REPORT.md` 2026 note). A fixed intercept/slope fit on 2021–23
  levels has never been checked against these level shifts.
- **No artifact refits the calibration on any later window** — whether a=1.517/b=0.779 is
  still the 2026 optimum is untested. The frozen protocol was a deliberate strictness choice,
  not a tested era-stability claim.

**Cheapest falsifying test:** expanding-window recalibration variant (fit calib through 2024
for 2025 scoring, through 2025 for 2026 — still walk-forward-legal), compared against the
frozen calibration on the same `predictions_v2.csv` uncalibrated columns. Hours of work; E5b.

**Recommendation: TEST-NEXT (cheap).** If the refit moves MAE < 0.05, retire the worry and
pin the frozen protocol; if it moves more, the regime-D freeze (HANDOFF_2026-07-30 §5 item 8)
should not inherit a stale calibration.

---

## 4. Charter-flight era break invalidates 2021–23 schedule features

**As stated / encoded:** `MINUTES_MODEL_SPEC.md` D8: "Back-to-back/travel coefficients learned
on 2021–2023 may not transfer … Mitigation: keep schedule features few and simple … and check
their marginal contribution separately per era in the feature-importance CSV before trusting
them." Also `HANDOFF_2026-07-30.md` §6 gotcha: "Charter flights from 2024 may invalidate B2B
fatigue features learned on 2021-23."

**Evidence FOR the concern (adjacent, not direct):**
- W6's schedule-based incumbent was *anti-predictive* out of era: rest/schedule/minutes
  baseline AUC 0.475 pooled test, below chance; "positives have *more* rest (AUC 0.514 for
  +rest) and *fewer* games-in-7 (0.480) — the opposite of the fatigue story"
  (`experiments/w6_retrospective/REPORT.md` §8).
- Direct distribution shift on record: the incumbent's alert rate designed at 1.00/100 on
  train drifted to 2.07/100 on test ("train->test distribution shift in the schedule
  features" — same report §4).

**Evidence AGAINST (i.e., that the break may not matter much):** schedule features were kept
few per D8, and Stage B's overall result (+0.037 over EWMA) leaves little room for any
feature group to matter much; but this is inference, not measurement.

**The encoded promise is unfulfilled:** D8's own mitigation — per-era marginal-contribution
checks — appears in **no artifact**. `experiments/minutes_twostage/feature_importance_minutes_stage_b.csv`
is a single train-era fit (33 features + intercept, 35 lines); no per-era split of
`days_rest_team`/`b2b_flag` contribution exists for the minutes model or the channel model.
**Untested as encoded.**

**Cheapest falsifying test:** E5c — ablation refit of Stage B (and the channel calibration
input set) with schedule features zeroed, scored per era on the existing test universes; plus
a 2021–23 vs 2024–26 coefficient comparison. No new data; an afternoon.

**Recommendation: TEST-NEXT (cheap), then either delete the caveat or delete the features.**
A standing untested caveat is the worst of both worlds: it neither protects the model nor
lets the features be trusted.

---

## 5. "Shifted-EWMA-is-enough" (rule 3) vs the minutes result — and where it generalizes

**As stated:** `HANDOFF.md` §3 rule 3: "Shifted EWMA with low alpha (0.05–0.15) wins the
forecasting bake-offs. AR never won once…" Rule 4: complexity subtracted value.

**Evidence FOR (it keeps winning on level targets — three independent confirmations on the ledger):**
1. **Minutes:** the 33-feature ridge with availability archive beat shifted EWMA(0.30) by only
   +0.0370 (4.6057 vs 4.6428) — "Minutes-trend EWMA is nearly sufficient for played-row
   minutes; complexity earned little (constitution rule 4 again)" (`HANDOFF_2026-07-30.md`
   §0.2; `experiments/minutes_twostage/REPORT.md`).
2. **Line paths (the market system!):** "close = current line" 0.980 beats the ridge on
   (current, hours-to-tip, movement) 1.007 — "the current line already embeds nearly
   everything the line path knows about the close" (`experiments/w5_closing_line/REPORT.md` §4).
   Rule 3's phenomenon reproduced in a different system it was never claimed for.
3. **Channels (pre-harness):** monolithic ridge 9.60–10.86 lost to structural EWMA chains 9.54
   (`HANDOFF.md` §4); speculative interactions hurt (10.24 vs 9.53, §3 rule 4).

**Evidence AGAINST (two clauses fail):**
- **The alpha-range clause is falsified for minutes:** tuned alpha = **0.30**, chosen by the
  train-only grid with a flat curve 0.25–0.35 (`experiments/minutes_baselines/REPORT.md` tuning
  table) — double the rule's "0.05–0.15" (which the channels still choose: 0.05–0.10,
  `channel_reval/REPORT.md` alphas note). The spec predicted this ("minutes are role-driven
  and may want faster alphas — the grid, not habit, decides", `MINUTES_MODEL_SPEC.md` §6).
- **It does not transfer to probability targets:** Stage-A logistic beat the shifted
  expanding-prior floor by Brier +0.0288 on a 0.005 bar with CI [+0.0267, +0.0312]
  (`minutes_twostage/REPORT.md` M2) — a 26.6% relative improvement, the largest relative win
  on the ledger. And **structural composition** of EWMAs beat raw EWMA sums by +0.63
  (`registry.jsonl` chanreval eval) — capacity spent on *structure* and on *probabilities*
  pays; capacity spent on level-regression does not.

**Where else it likely generalizes (untested):** a channel-level ridge/GBM challenger on the
rebuilt masters was deliberately not re-run under the harness ("July's exploratory
monolithic-ridge/hybrid variants were not re-run — unregistered results are void",
`channel_reval/REPORT.md` deviation 6) — so rule 3 at the channel level is supported by
pre-harness evidence only. Given three confirmations elsewhere, re-testing it is low-EV.

**Cheapest falsifying test (of the amended rule):** none needed for the level clause; the
probability clause is tested by E1 (if a distributional model *fails* to beat a naive
constant-σ Gaussian, then EWMA-saturation extends to distributions too and the E1 lane closes).

**Recommendation: AMEND rule 3.** Rewrite as: "Shifted EWMA saturates *conditional-mean*
forecasting (team stats α≈0.05–0.15, minutes α≈0.30 — tune per target); spend model capacity
only on (a) structural composition of trends and (b) probability/distribution targets, where
the ledger shows real returns." This redirects effort instead of just restraining it.

---

## 6. Regime-B strictly-prior-day conservatism — how much signal does it discard?

**As stated / encoded:** "Every injury-history record used for target game G must satisfy
record_date <= game_date(G) - 1 day (day-precision conservatism: same-day records cannot
prove they preceded tip). W1 news must satisfy date(published_utc) <= game_date - 1"
(`registry.jsonl`, minutes_twostage registration `point_in_time_rule`); audited in-run
("windows end at game_date - 1 day via searchsorted(hi) on strictly-less", run-2
`timestamp_audit`).

**Evidence FOR (the conservatism is cheap for the current sources):**
- ESPN missed-game rows are "postgame per-game records, usable from the following day"
  (run-2 `regime_b_accounting.sources`) — zero loss by construction.
- The features still fitted: miss_inj_l21 ranked #6 in Stage-A coefficients
  (`HANDOFF_2026-07-30.md` §3 results table) and covered rows show real risk separation:
  covered played-rate 0.612 vs uncovered 0.959 (run-2 `systematic_missingness`).

**Evidence AGAINST (real discard, never counted):**
- bbref transactions are "official league transactions, **public same-day**, day precision"
  (run-2 `regime_b_accounting.sources`) — every same-day signing/waiver/trade is delayed one
  day by the rule. **How many rows this affects is untested** — no artifact counts
  record_date == game_date events.
- The rule is *over*-conservative for W1 news, which carries **exact `published_utc`**
  (same source table) — a same-day story published at 10:00 before a 19:00 tip is provably
  pregame, and tip times are stored with every odds snapshot (`ROADMAP.md` Phase 0:
  "tip time known-at-capture is stored with every odds snapshot"). The day-precision rule
  throws that provability away. Today the cost is ~zero (the overlay touched **1 row** in the
  2026 window — `minutes_twostage/REPORT.md` W1 overlay), but the same rule template, carried
  into regime D, would discard the highest-value hours of game-day news — exactly the window
  where lines move fastest (~0.09 pts/elapsed-hour inside the last hour, and the overnight
  22Z→15Z step is "where injury-report news lands" — `w5_closing_line/REPORT.md` §3).

**Cheapest falsifying test:** a counting exercise, no model: (a) count injury-history records
with record_date == game_date per season; (b) for the live-capture era, count W1 signals and
injury-report revisions with timestamp < stored tip time on game day
(`data/news_capture/`, `data/injury_capture/`, hourly PDF revisions per
`HANDOFF_2026-07-30.md` §1). If (b) is a large share of all signals — likely, given hourly
game-day cadence — the regime-D rule must be timestamp-precise, not day-precise.

**Recommendation: KEEP for the historical backtest** (day precision is all bbref/ESPN can
prove) **but AMEND the forward rule now**: regime-D cutoff logic should compare
`published_time`/`observed_time` against per-game tip time (both already captured per the
prediction contract's provenance fields), before the first frozen model ships.

---

## 7. Minutes system regular-season-only while playoffs may be where lines are softest

**As stated / encoded:** `MINUTES_MODEL_SPEC.md` §2.1: "v1 trains and scores on
regular-season rows; playoff rotations tighten (starters stretch toward 40), so playoff rows,
when used, are scored as a separate split, never blended silently." Enforced downstream:
oracle bracket dropped 46 playoff games from all variants ("minutes system is
regular-season-only (MINUTES_MODEL_SPEC 2.1)" — `registry.jsonl` oracle v2 run-2 `coverage`),
and `bottomup_3pt_channel_v1` inherits the restriction ("availability system is RS-only",
registration `extra.universe`).

**Evidence FOR the restriction:** the rotational-regime argument is stated but **not
quantified anywhere** (no artifact measures playoff minutes-MAE of the EWMA under playoff
rotations). It is a reasonable prior, not a result.

**Evidence AGAINST / the missed upside:**
- The claim that playoff lines are softest is **untested in both directions** — no artifact
  splits bookie MAE or the model-vs-book gap by RS/playoff. The inputs exist: the channel
  test set *includes* playoffs (673 games "incl. playoffs", `registry.jsonl`
  w2_zone registration `extra.universe`), `predictions_v2.csv` covers them, and playoff odds
  exist (old master 2024: 261/262 games covered, `data/refresh_2026/AUDIT_REPORT.md` §6;
  extension era spans "post-All-Star + playoffs" 2025, `w5_closing_line/REPORT.md` §6).
- The exclusion silently shrinks every availability-layer result: 46 of 673 test games (6.8%)
  are invisible to the entire minutes→lineup pipeline, in the season phase with the highest
  stakes-per-game and (per the spec's own §11) *more* projectable rotations ("playoff
  rotations tighten" cuts both ways — tighter rotations are easier minutes targets).

**Cheapest falsifying test:** E5a — split the existing 673 predictions + odds joins into
RS/playoff and report model MAE, bookie MAE, and gap per split. Pure arithmetic on committed
artifacts; an hour. If the playoff gap is smaller (books sharper) the restriction is cheap;
if larger, a playoff minutes split (spec already anticipates "scored as a separate split")
should be pulled forward before the 2026 playoffs.

**Recommendation: TEST-NEXT (nearly free), decision before September.**

---

## 8. LINEUP_SCALE=4.0 and the additive-adjustment framing — is "~18% gap closure" robust?

**As stated / encoded:** margin_v = str_margin_cal + LINEUP_SCALE × [(m_v−m_1)_home −
(m_v−m_1)_away], LINEUP_SCALE = 4.0 "= 5 on-floor slots x (80 team possessions / 100), fixed
a priori, no fitting" (`registry.jsonl` oracle v2 registration; `oracle_bracket.py:62`).
Conclusion drawn: "The bookie gap is mostly NOT cheap lineup info: … even OMNISCIENT minutes
close only ~18% of the 0.373 pooled gap (to 0.305)" (`HANDOFF_2026-07-30.md` §0.3). Numbers:
v1 gap 0.3732 → v4 0.3046 (18.4% closed); v3 0.3141 (15.8%)
(`experiments/oracle_bracket/REPORT.md` bookie-gap table).

**Evidence FOR the conclusion:**
- The bracket is preregistered, dimensionally checked (v1's 40× units error was caught in
  smoke and documented — `registry.jsonl` v2 registration `hypothesis`), audited (v1 identity
  max dev 0.0; Stage-B reproduction 7.11e-15 — run-2 `audits`), and internally consistent:
  v2 < v3 < v4 pooled (10.1555 / 10.1170 / 10.1072).
- The v4-worse-than-v3 2024 result (9.1662 vs 9.0347) matches the ROADMAP regime-C warning
  about blowout-script contamination — the bracket behaved as theory predicted.

**Evidence AGAINST robustness — the conclusion is conditional on at least four mechanism choices:**
1. **Even the oracles are statistically indistinguishable from nothing under this mechanism:**
   v3 vs v1 +0.0582, CI [−0.0123, +0.1273]; v4 vs v1 +0.0681, CI [−0.0254, +0.1641]
   (`oracle_bracket/REPORT.md`). A mechanism that cannot extract a CI-clean gain *from perfect
   information* is as likely indicting the mechanism as bounding the information.
2. **LINEUP_SCALE was never fitted, even legally.** 4.0 is an a-priori constant; a train-years
   fit of the scale (walk-forward-legal) was never run. If the response of margin to weighted
   RAPM shifts is nonlinear or the constant is off by 2×, the whole bracket rescales.
   **Untested.**
3. **RAPM v0 quality bounds the values being weighted:** λ=5000 sits at the sweep boundary
   ("the true optimum may lie above 5000"), YoY stability r = 0.456/0.366, and the stint-MAE
   edge over a team-strength baseline is −0.016 (`experiments/rapm_v0/REPORT.md` diagnostics
   1–2, limitation 4). 3,411 player-rows fell to the p25 replacement value −0.89 (run-2
   `coverage`). Noisy val(p) attenuates any real lineup signal toward zero.
4. **Common dressed universe means v2 measures reweighting only** — "not who-is-dressed news"
   (`oracle_bracket/REPORT.md` design notes). The bracket never priced the news that a star is
   out of the *building*; it priced redistribution among those dressed.

**Cheapest falsifying test:** two one-day sensitivities on the committed artifacts —
(a) sweep/fit LINEUP_SCALE on train years and re-read the bracket (if 18% → 30%+ under a
fitted scale, the "mostly not lineup info" claim dies); (b) re-run v3/v4 with per-season RAPM
at other λ values (`rapm_v0.csv` already carries `net_100_lam{500..5000}` columns). The
*definitive* test is already registered: `bottomup_3pt_channel_v1` ("oracle bracket showed
additive lineup adjustments cap at ~18% …; this is the bottom-up alternative the bracket
pointed to" — `registry.jsonl` registration `extra.strategic_context`).

**Recommendation: AMEND the claim's wording everywhere it appears** — from "the bookie gap is
mostly not cheap lineup info" to "an additive minutes-weighted RAPM-v0 adjustment at fixed
scale 4.0 recovers ≤18% of the gap even with oracle minutes." The strategic redirection
(bottom-up rebuild) is right either way; the epistemic status should not overreach the
mechanism. Then run E3.

---

## 9. "Odds never features in the basketball model" — honored? And is the permission exploited?

**Part A — the ban is honored (supported):**
- Greps of the basketball-model builders find no odds/spread/market references
  (`experiments/channel_reval/build_channel_base_v2.py`, `minutes_twostage.py` — zero matches;
  verified this audit).
- The blowout proxy is deliberately internal: "|own net EWMA − opp net EWMA| (D7: **not** the
  market spread)" (`MINUTES_MODEL_SPEC.md` §6D, D7), and the odds capture is ledgered
  "Benchmarks/CLV only — never features (rule 7)" (spec §10).
- W6 and all minutes/channel features trace to gamelogs/pbp/schedule/injury archive only
  (feature lists in `registry.jsonl` registrations).

**Part B — the permission is NOT being exploited (the amended rule's other half is dead letter):**
- ROADMAP's amendment explicitly *permits* odds "in the separately trained market model and
  the betting decision layer" (`ROADMAP.md` §Amended constitution rules). Registered results
  using that permission: **zero**. `leaderboards/MARKET.md` and `leaderboards/BETTING.md`:
  "No registered evaluations on this board yet." The single market-side attempt (W5 ridge)
  used line-path features only and failed (1.007 vs 0.980, `w5_closing_line/REPORT.md` §4);
  no decision-policy comparison, no CLV computation, no Kelly sizing test exists.
- **The benchmark itself is timing-asymmetric and the reports stopped saying so.** Every
  registration's decision time is T−24h (`registry.jsonl`), but the bookie gap is computed
  against "each book's **latest pre-tip snapshot**" (oracle v1 registration
  `extra.bookie_gap_table`) — ≈T−64m lines in the old master (`w5_closing_line/REPORT.md` §2).
  Lines move materially in that window: |close − line@T−24h| MAE 1.133 on the extension era
  (§3 baseline table), i.e., the book's near-tip number embeds ~a point of information the
  T−24h model could not see. ROADMAP's information-parity caveat promises this "is
  acknowledged in reports, never assumed away" (`ROADMAP.md` prediction contract) — but
  neither `oracle_bracket/REPORT.md` nor `HANDOFF_2026-07-30.md` §0.3 restates it beside the
  0.373 figure. How much of 0.373 is timing rather than skill: **untested**.

**Cheapest falsifying test:** E2 — on the 2025–26 extension games (multi-snapshot), recompute
the model-vs-book gap against the T−24h line and against the latest pre-tip line side by side.
If the T−24h-matched gap is materially below 0.373, the basketball model is closer to
market-competitive *at its own decision time* than every current document implies — which
re-prices the entire roadmap.

**Recommendation: KEEP the ban; AMEND the reporting** (decision-time-matched benchmark rows on
FORECASTING); **TEST-NEXT** the market/decision layers — they are the only systems with zero
evidence and they are the ones that make money.

---

## 10. W1 news being forward-only — is there really no historically-timestamped source we own?

**As stated / encoded:** "Pregame injury designations, 2021–2025 … **Unknowable historically**
— league reports are ephemeral" (`MINUTES_MODEL_SPEC.md` §10); "W1 news extractions are NOT
fitted features (zero 2021-2023 coverage makes them unfittable)" (`registry.jsonl`
minutes_twostage registration); "W1's value is forward-only (regime D), as the missing-data
ledger always said" (`HANDOFF_2026-07-30.md` §0.4).

**Evidence FOR:**
- The 2026 overlay window found 210 signals but touched **1** dressed-universe row
  (`minutes_twostage/REPORT.md` W1 overlay), and 138/200 resolved signals carried status
  "unknown" with 145 speculation rows (run-2 `w1_overlay_exploratory.resolution`) —
  aggregator-tier headlines are noisy even live.
- Official pregame designations genuinely are ephemeral; nothing in `NEWS_SOURCES.md`
  contradicts that for the *designation* class.

**Evidence AGAINST / nuance:**
- The project **already owns one historically-timestamped availability source and fitted it**:
  the B-Ref transaction wire (day precision, public same-day) inside
  `data/injury_history/` — miss_inj_l21 is the #6 Stage-A coefficient
  (`HANDOFF_2026-07-30.md` §3). "Forward-only" is true of *news text*, not of all
  timestamped availability information; regime-B coverage is already 23.1–28.2% of rows
  (run-2 `regime_b_accounting.coverage_by_season`).
- Whether owned/free news archives reach back further is **untested, not impossible**: the
  2026-07-30 fetches show archive *depth per feed* — Her Hoop Stats full-text feed spans
  May 20 → Jul 30 (~10 weeks), Winsidr Jun 9 → Jul 22, but ESPN RSS only Jul 27–30 and AP
  ~Jul 20–30 (`project_docs/NEWS_SOURCES.md` cadence column). No one has audited outlet
  sitemaps/archives (The Next/IX, Substack back-catalogs, AP hub pagination) for
  timestamped 2024–25 injury coverage; prosportstransactions is Cloudflare-walled
  (`HANDOFF_2026-07-30.md` §3), and no Wayback probe is on record.

**Cheapest falsifying test:** a one-day, no-model crawl audit: for each VERIFIED source in
`NEWS_SOURCES.md`, measure how far back a timestamped item list can be retrieved; then take
the 2025 `missed_game_injury` events (528 rows — `w6_retrospective/REPORT.md` §7) and count
what fraction have a retrievable timestamped article dated ≥1 day before the missed game.
That number *is* the achievable regime-B W1 extension.

**Recommendation: KEEP the forward-only posture for designations; run the cheap archive
probe before writing "unknowable" about news text.** If the probe finds <10% event coverage,
close the question permanently on the ledger; if more, a regime-B W1 backtest slice becomes
buildable for 2025.

---

## 11. Other settled-but-unsupported items found

1. **Derived layers are stale relative to the certified-complete raw layer.**
   `AUDIT_REPORT.md` §1 certifies pbp complete for all 1,489 games, but possessions/RAPM
   were built from **1,424** games with "2022–24 playoff pbp … not on disk (noted, not
   hidden)" (`experiments/rapm_v0/REPORT.md` Stage 1 + limitation 1), and stints lack the
   same 65 games (`w6_retrospective/REPORT.md` §7 input coverage). The 65 playoff games
   arrived later the same day (`HANDOFF_2026-07-30.md` §3). Anything consuming rapm_v0 or
   stints (the oracle bracket did) inherits the gap. **Fix: rebuild possessions/stints/RAPM
   before the RAPM promotion experiment; cheap, scripted.**
2. **"Promoted in spirit" is a governance leak.** Stage A "promoted-in-spirit (bar met; it
   becomes the availability input for item 4/5)" (`HANDOFF_2026-07-30.md` §5 item 2) — a
   secondary, ungated metric result is now a load-bearing dependency of a registered
   experiment (`bottomup_3pt_channel_v1` consumes "committed Stage-A predictions",
   `registry.jsonl` registration) and of the planned regime-D freeze. The M2 bar was
   preregistered and decisively met, so the substance is fine — but there is no ledger
   object that says "Stage A is the incumbent availability model." **Fix: register a
   one-line promotion/adoption record (or a primary-metric Stage-A experiment) so the
   dependency chain is on the ledger, not in a handoff sentence.**
3. **Leaderboard verdict semantics can mislead.** W6 posts "**PASS**" on FORECASTING
   (`leaderboards/FORECASTING.md` row 5) while the registry interpretation says "NULL RESULT
   in substance … the registered hypothesis's 'better than chance' clause is REFUTED"
   (`registry.jsonl` w6 eval). Anyone scanning the board sees a passing quarantined
   experiment. **Fix: render `promote`/hypothesis-refuted alongside verdict.**
4. **The stated money target has no benchmark on any board.** "the realistic money target is
   player props/totals, not spreads" (`HANDOFF.md` §1) — yet every market benchmark row on
   all four leaderboards is a *spread* margin-MAE row; the model's total forecast exists
   (14.2236 vs raw 14.763, `registry.jsonl` chanreval gate-4 detail) and 27,820 totals rows
   are already captured (`w5_closing_line/REPORT.md` §5), but no bookie-totals MAE, no
   totals cover evidence, nothing on props. The end-goal metric ("beating average bookie" on
   spread MAE, `HANDOFF.md` §1) and the end-goal market (props/totals) point at different
   targets. **Fix: E4.**
5. **Early-season coverage holes are unpriced.** 108 of 781 test games (13.8%) are excluded
   by the ≥5-prior-games rule (`channel_reval/REPORT.md` expansion section; coverage 0.8617
   in the eval record). Books price those games; the system structurally cannot. No artifact
   estimates the betting opportunity forfeited. Minor today; matters at the betting layer.
6. **The 9.54 "champion" number is a different-sample anchor.** Frozen 9.54 (308 games
   2024–partial-2025) vs the current-era pooled 10.086 on 673 games (`leaderboards/FORECASTING.md`
   frozen rows vs rank 3). Both are honest; any narrative arithmetic ("we're 0.6 behind
   books") must use same-sample pairs — the 0.373 pooled gap — or it overstates progress.

---

# Ranked: the 5 highest-EV next experiments on the path to profit

*Ranking principle, from the ledger itself: point-forecast MAE headroom vs the book is small
and expensive (0.373 total; oracle ceiling ≤0.07 via additive lineup info), while the
probability→market→decision chain — the part that actually monetizes — has **zero registered
evidence** on three of four leaderboards. Highest EV = experiments that convert existing,
committed artifacts into betting-relevant knowledge, before more MAE-mining.*

### E1. Distributional margin layer + cover probabilities (`dist_margin_cover_v1`, regime A → PROBABILISTIC)
**Design.** On the committed `experiments/channel_reval/predictions_v2.csv` (673 games,
calibrated + uncalibrated margins): fit train-years-only residual distributions — constant-σ
Gaussian floor vs heteroscedastic σ (conditioned on predicted total / pace trend) vs
Student-t; produce full margin/total distributions and P(cover) against each game's stored
book line (old master T≈−64m rows + extension per-book snapshots). Score walk-forward
2024/25/26: CRPS, cover-Brier, log loss; run the ROADMAP-mandated calibration competition
(Platt vs isotonic vs hierarchical — "isotonic is NOT the presumed winner"). Preregister:
primary = cover-Brier vs the line-implied-probability benchmark; floor challenger =
constant-σ.
**Cost.** ~1 day; zero new data.
**Decision change.** If cover probabilities beat the vig-free line-implied benchmark in any
calibrated subset, the betting simulator (Phase 3) unblocks immediately; if even the
best distributional layer is dominated by the market's implied probabilities everywhere, the
spread-betting lane is evidentially dead and effort reroutes to totals/props (E4) — either
answer is worth more than 0.05 of MAE.

### E2. Decision-time-matched market benchmark + MAE→value transfer curve (`clv_transfer_v1`, regime A → BETTING)
**Design.** Two halves, both on committed artifacts. (a) *Timing repair:* on the 2025–26
extension era (406 games, multi-snapshot, per-book prices), compute model-vs-book margin gap
against the line at T−24h **and** the latest pre-tip line, side by side — the first
decision-time-fair measurement of the 0.373 gap. (b) *Transfer curve:* flat-stake paper
simulation using `experiments/oracle_bracket/game_level_margins.csv` (v1 and v2 margins per
game): bet where |model − line| ≥ k over a k-grid; report bet count, ROI after vig (prices
are stored), and CLV per decision time; difference the v1 and v2 bet sets to measure what a
+0.02 MAE delta is worth in decisions. Preregistered as diagnostic (no promotion claim).
**Cost.** ~1 day.
**Decision change.** Replaces the templated 0.10 bar with an empirically derived
value-per-MAE-point curve (assumption 1); establishes whether the T−24h-fair gap is already
near zero (assumption 9) — which would flip the project's self-assessment from "0.4 behind
the books" to "competitive at our decision time, behind only on late news."

### E3. Execute `bottomup_3pt_channel_v1` (already registered, regime B → FORECASTING)
**Design.** As registered 2026-07-30T21:05Z (`registry.jsonl`): per-player shifted 3PA-rate
EWMA × EB-shrunk 3P% × (Stage-A p_plays × minutes EWMA), per-team uncovered-minutes
correction, incumbent opponent factor; gate on threep_channel_mae ≥0.10 with gate-4 joint
margin substitution. Registration already carries the strategic context ("additive lineup
adjustments cap at ~18% of the bookie gap; this is the bottom-up alternative the bracket
pointed to").
**Cost.** 2–3 days (largest of the five; the registration and all inputs are committed).
**Decision change.** This is the first true test of the V4 bottom-up thesis — the mechanism
by which lineup information is supposed to enter after the oracle bracket closed the additive
route. PASS → the player-layer rebuild proceeds with evidence; FAIL → the bottom-up margin
thesis joins the additive one, and the project's edge must come from probability quality and
market timing (E1/E2 lanes), not player-margin modeling. Either way it also settles
assumption 8's mechanism question with a registered result.

### E4. Totals-market benchmark + totals distribution (`totals_market_bench_v1`, regime A → FORECASTING/PROBABILISTIC)
**Design.** Build the missing bookie-totals benchmark: join the model's existing total
forecasts (chanreval joint output) to book totals (old master totals columns + extension
`master_odds_extension_other_markets.csv`, 27,820 totals rows); report model-vs-book totals
MAE same-games by season; extend E1's distributional machinery to totals for over/under
cover-Brier. Preregister totals-MAE gap and totals cover-Brier vs line-implied.
**Cost.** 1–2 days.
**Decision change.** HANDOFF §1 names props/totals the realistic money target, on zero
evidence. If the model's totals gap is proportionally smaller than its spread gap (plausible
— totals lean on pace/scoring structure, the model's strength, less on late lineup news),
market-entry strategy reorders around totals; if it is worse, the props/totals thesis loses
its presumption and W4 (refs → totals, already registered) gains priority context.

### E5. Robustness bundle: playoff split, recalibration drift, schedule-era ablation (`robustness_bundle_v1`, regime A, diagnostics)
**Design.** Three preregistered diagnostics on committed artifacts, none promotable:
(a) split the 673 chanreval predictions + odds by regular/playoff; report model MAE, bookie
MAE, gap per split (assumption 7); (b) expanding-window recalibration (refit slope/intercept
through the prior season, walk-forward-legal) vs the frozen a=1.517/b=0.779 on the
uncalibrated predictions (assumption 3); (c) schedule-feature ablation and per-era
(2021–23 vs 2024–26) coefficient comparison for Stage B (assumption 4, fulfilling D8's own
promised check).
**Cost.** ~1 day combined.
**Decision change.** (a) decides whether a playoff minutes split is built before the 2026
playoffs (calendar-bound: it is July 30); (b) decides whether the regime-D freeze inherits
the frozen calibration; (c) retires or confirms two standing constitutional caveats before
they get copied into another year of specs.

*(The other two registered-but-unevaluated experiments — `w2_zone_channel_integration_v1`,
`w4_ref_fta_priors_v1` — stay queued per HANDOFF §5; they rank below E1–E5 because both are
point-forecast refinements inside a lane whose total headroom the oracle bracket just
measured at ≤0.07–0.37, while E1/E2/E4 open lanes with zero current evidence and direct
monetization logic.)*

---

## Three assumptions in most urgent need of revision

1. **The 0.10 practical bar (assumption 1)** — it is a template constant applied across
   incompatible units, it cannot be value-aligned because no MAE→ROI mapping exists
   (BETTING board empty), and it just filed a CI-certified real improvement
   (+0.037, CI [+0.012, +0.061]) in the same bin as a CI-zero one. Amend after E2's
   transfer curve; add a "bankable, sub-bar" ledger status plus a stacking experiment.
2. **"The bookie gap is mostly NOT cheap lineup info" (assumption 8 / HANDOFF §0.3)** — the
   18% figure is conditional on an unfitted scale constant (4.0), boundary-tuned RAPM
   (λ=5000 at sweep edge, YoY r 0.37–0.46, 3,411 replacement rows), an additive mechanism
   whose oracle variants have CIs spanning zero, and a common dressed universe that excludes
   who-is-dressed news. Restate as a mechanism-bounded result; let E3 measure the thesis it
   is being used to justify.
3. **The 0.373 gap itself (assumption 9, reporting half)** — measured against ≈T−64m book
   lines for a T−24h model, in a window where lines move ~1.1 pts on average, with ROADMAP's
   own information-parity caveat dropped from the reports that quote it. Until E2's
   decision-time-matched re-measurement, the project's core "distance behind the market"
   number is an upper bound being treated as a point estimate.
