# NOTES — E1_I0035_availability_sum

Technical record. The plain-language mechanism is `DEFECT_ANATOMY.md`; the repair comparison is
`REPAIR_OPTIONS.md`; self-reported defects are `DEFECTS.md`; machine-readable output is
`FINDINGS.json`.

Preregistration `PREREG.md`, sha256
**`7cd32656f3f7a96e869bf649f2ce1034a1c9cc3670f5dbc7605350fba6664205`**.
Seed **20260810**. Partition **2021–2024**; 2025 and 2026 parquet files sit in the same
directories, are never enumerated by any loader, and `av_base.assert_partition` raises on their
presence in any frame.

**No repair was enacted.** Nothing here writes to any arm, contract, registry or production path.

---

## 0. TIME-WINDOW TABLE

| Column | Construction | Window | Reads future? | Evidence |
|---|---|---|---|---|
| `pts` (team), `pts` (player), `appeared`, `minutes` | `master_*.parquet` | this game | no | responses; never a regressor |
| `p_active_hat`, `pts_hat`, `min_hat` | stored `pred_point`, `cbs_v15_player_oof_v5/attempt_001` | (−∞, cutoff]; season *S* fitted on seasons < *S* | no | per-fold receipts; D076 established this walk-forward |
| `A_TEAM` | stored `pred_point`, `cbs_v12_team_oof_v2/attempt_001` | same | no | fold receipts; `/1` is `PROVISIONAL_SUPERSEDED` and is not used |
| `tier_A` | `row_uid ∈ prediction_contract_v4` | contract-time | no | manifest-verified; **verified 100 % identical to v5's `universe_tier` on all 20,084 rows** |
| `game_date` | `master_team` | schedule fact | no | fixture attribute, not an outcome |
| **Xa** strata recalibration `(α_s, β_s)` | logistic on `logit p` within stratum | whole seasons < scored season | no | walk-forward; empty strata reported unrepaired |
| **Xb** `R̂` roster target | expanding mean of realised roster size over **strictly earlier same-season** games | (−∞, game_date) | no | prefix accumulator writes before folding row *i* in; season openers back off to earlier **seasons**' league mean |
| **Xc** τ | grid rule on **strictly earlier seasons** | whole seasons < *S* | no | full τ curve published |
| **Xd** affine `(a, b)` | OLS on **strictly earlier seasons** | whole seasons < *S* | no | 2022 fold has no train pool → intercept only |
| **Xa-O** | same as Xa, fitted **in sample** | **this season** | **YES** | **ORACLE. Ceiling only. Excluded from every verdict.** |
| `ever_appears_for_this_team_from_now` | realised future appearances | **forward** | **YES** | **CHARACTERISATION ONLY.** No repair is built or tuned on it; no number in step 4 or 5 depends on it. Declared in `PREREG.md` §3 P03. |

---

## 1. Provenance

### Inputs and manifest status

| Artifact | Granularity | Status | Use |
|---|---|---|---|
| `data/masters/master_player.parquet` | row | USABLE_IF_FILTERED | outcomes, appearance calendar, population footprint |
| `data/masters/master_team.parquet` | row | USABLE_IF_FILTERED | response, schedule facts |
| `prediction_contract_v4/{player_game,team_game}.parquet` | row | USABLE_IF_FILTERED | identity cross-check; **the tier-A definition** |
| arm `predictions__*.parquet` | artifact | UNUSABLE **as a feature source** | not used as one — these are the stored forecasts being *described*, one file per fold, with the per-fold receipt as the as-of evidence |
| `prediction_contract_v5/player_game.parquet` | — | **UNVERIFIABLE** | **backs no number.** Opened once, in `s07`, purely to *describe* whether the tier proxy matches the real label |
| `data/reference/player_bios.csv` | — | **UNVERIFIABLE** | **backs no number.** Confined to the P02 table, banner-labelled, loads no conclusion |

`data/w1_truth/*` was never opened (D076 records it failing the manifest check for this kind of
screen).

### The identity map, reconstructed

All 26,614 of the champion's `row_uid`s belong to `prediction_contract_v5`'s universe, which is
UNVERIFIABLE. So `row_uid → (player_id, game_id, team_id)` was **recomputed** from the registered
canonical key (`cbs_obligation_key/1`, `CANONICAL_KEY_FIELDS = (player_id, game_id, team_id)`)
over the cross product of 1,940 team-games × 268 players = **519,920 triples**, all keys unique.
The script asserts the field order has not drifted before building anything.

* **Cross-check: 22,659 of 22,659 contract-v4 rows reconstructed and agreeing on all three
  fields. Exact.**
* Resolution on the champion's rows: 26,574 of 26,614 (99.85 %). The 40 unresolved are dropped
  and reported — the same 40 E1_I0033 found.

### The tier proxy, validated

`tier_A := row_uid ∈ contract v4` was adopted because v4 is manifest-verified. `s07` opened v5
once, descriptively, and the proxy agrees with v5's own `universe_tier` on **20,084 of 20,084
rows (100.000 %)**. Tier-B `candidate_source` composition: `S2` 2,222 (weak, early-season only),
`S_TX|S2` 1,044, `S_TX` 506 (transactions, "probable"). `team_assignment_confidence`: weak 2,222,
probable 1,550. **No number changes on this cross-check; it removes a stated limitation.**

---

## 2. Anchor reproduced before any new statistic

| Anchor | Published | Reproduced | Error |
|---|---|---|---|
| D076 appeared player-games, 2022–2024, tier-A obligation set | 13,879 | **13,879** | exact |

`s02` halts on failure; the assertion and its pass are in `run_log_s02.txt`.

---

## 3. Row sets and denominators (D101)

**RS1** — season ∈ {2022,2023,2024}, `season_type == "Regular Season"`, team-arm forecast
present, ≥1 champion player row → **1,392 team-games (432 / 480 / 480)**. Response mean 82.2220,
sd 11.0130, **SST 168 710.4073**, computed once and passed explicitly to every R².

**RS1P** — the champion's rows on RS1 team-games → **20,084** (tier A 16,312, tier B 3,772).
**RS1P-APP** — 13,087 appeared rows.

**Denominator declaration.** Every team-level figure shares response `master_team.pts`, row set
RS1, SST 168 710.4073, no weighting, no base. Player-level figures are declared at each table
with their own response and n. **No team-level ΔR² is compared to any player-level ΔR², and no
skill ratio crosses levels.**

---

## 4. Results

### 4.1 Reproduction — CONFIRMED, every cell inside 5e-4

| Quantity | E1_I0033 | mine | |Δ| |
|---|---:|---:|---:|
| universe rows / team-game | 14.428 | 14.4282 | 2e-4 |
| realised roster / team-game | 9.4016 | 9.4016 | 0 |
| Σ`p_active_hat` / team-game | 10.3381 | 10.3381 | 0 |
| tier-B mean `p_active_hat` | 0.5249 | 0.5249 | 0 |
| tier-B realised appearance rate | 0.1015 | 0.1015 | 0 |
| tier-B n rows | 3,772 | 3,772 | 0 |
| tier-A mean `p_active_hat` | 0.7608 | 0.7608 | 0 |
| tier-A realised appearance rate | 0.7788 | 0.7788 | 0 |
| tier-A n rows | 16,312 | 16,312 | 0 |
| B1 level bias | +8.139 | +8.1389 | 1e-4 |
| **B1_BOTTOMUP_AVAIL MAE** | **18.263037** | **18.263037** | **0 (6 dp)** |
| **A_TEAM MAE** | **8.685506** | **8.685506** | **0 (6 dp)** |

Closing arithmetic: excess 0.9365 players × 8.7406 `p_active`-weighted mean `pts_hat` = **8.1855**
against an observed level bias of **8.1389**. The 0.05 residual is the covariance between the
per-team-game excess and the per-team-game conditional scoring rate; the identity is not exact by
construction and is not claimed to be.

### 4.2 The correction to E1_I0033

`WHICH_LEVEL_WINS.md` §2(b) states the tier-B rows *"receive a **declared-constant `p_active` of
0.80** against a realised appearance rate of 0.10"*. **That attribution is wrong.**

| Tier B | n | mean `p_active` | realised rate | excess / team-game | share of net excess |
|---|---:|---:|---:|---:|---:|
| carrying the constant 0.800 | **1,625 (43.1 %)** | 0.800 | 0.2129 | +0.6853 | 73.2 % |
| carrying a **fitted** logistic value | **2,147 (56.9 %)** | **0.3167** | **0.0172** | +0.4618 | 49.3 % |

| Tier A | n | mean `p_active` | realised rate | excess / team-game | share |
|---|---:|---:|---:|---:|---:|
| constant | 614 | 0.800 | 0.8208 | −0.0092 | −1.0 % |
| fitted | 15,698 | 0.7593 | 0.7772 | −0.2015 | −21.5 % |
| **net, all rows** | 20,084 | | | **+0.9365** | 100 % |

Two refinements follow. (i) **Only 73 % of the surplus is the constant**; the rest is a
train/score population mismatch. (ii) **Tier A is not neutral — it contributes −0.211**, i.e. it
slightly *under*-predicts availability, which partly offsets tier B.

The screen's own `NOTES.md` §4.4 reports the tier-B mean as 0.5249 and is **correct**; the error
is confined to the plain-language retelling, and it propagated into that screen's `DEFECTS.md`
and `player_value_scope.md`. **Every number in E1_I0033 reproduces exactly and no conclusion of
theirs is affected.** DR-R was satisfied before publishing this: my row set, denominator and
inputs were verified identical to theirs by exact reproduction of five of their statistics first.

### 4.3 The mechanism

**Part one, the constant.** `cbs_generator.py:71` defines
`DECLARED["p_active"] = {"point": 0.800, "sd": None}`. `cbs_v7.py:1341` applies it:

```python
pa_point = p_hat.where(lvl_pa == 0, DECLARED["p_active"]["point"])
```

where `lvl_pa = player_fallback_level(test, hist_te["n_prior_candidate_games"], np.isfinite(p_hat))`.
`cbs_v7.player_fallback_level` (lines 537–555) sets level 2 for 1–2 prior candidate games, level
3 for 0 prior or a non-finite centre, level 4 for `season ∈ DECLARED_CONSTANT_SEASONS = (2021,)`.
**The fitted logistic output is discarded on every nonzero level.** 2,239 of 20,084 RS1P rows
(11.1 %) carry exactly 0.800; the `component_id == "p_active/declared_constant"` flag and the
value agree on every row.

**Provenance of 0.800: none.** `project_docs/CONTRACT_BASELINE_SUITE_V2.md` §9 derives the four
sibling constants arithmetically (200/10 = 20.0; 70 × 0.1 = 7.0; 82 × 0.1 = 8.2; 82.0) and
`experiments/registry.jsonl`'s `contract_baseline_suite_v2` record carries a `derivations` dict
with exactly those **four** keys. `p_active` appears in the value table and **not** in
`derivations`. It is not learned, and it is not a derived prior. It is frozen behind §9's explicit
clause that poor constants are *"a finding to report, not a licence to retune"*.

**Unauthorised scope.** Every document scopes declared constants to ladder level 4
(`season:2021`, no training fold) and level 1 (degenerate fold). **No document authorises the
level-2 / level-3 substitution on fully-fitted seasons.** `tests/test_cbs_generator.py:191` tests
only the 2021 path. The same line appears verbatim in `cbs_v8.py:883`,
`cbs_player_runner_v13.py:231` and `cbs_player_runner_v14.py:231`.

**Part two, the population mismatch.** `prediction_contract_v5.py` seam 3: *"TRAIN FILTER — the
training frame is Tier A rows only"*. The ridge logistic is fitted where the base rate is 0.7788
and applied where it is 0.1015. The fitted tier-B rows carry 0.3167 against a realised 0.0172 —
an 18× over-statement with no constant involved. **The contract labels these rows tier B and
states current roster membership is not established; nothing in the emission path reads
`universe_tier`.**

**By tier × fallback level** (`p_active_by_tier_and_fallback_level.csv`): the tier-B level-3 rows
(no prior obligation, n = 909) appear at 0.3366 while the tier-B level-2 rows (1–2 prior
obligations, n = 716) appear at 0.0559 — both on the same 0.800. The ladder is not merely
miscalibrated, it is **non-monotone in the direction that matters**: more prior evidence
correlates with *less* likelihood of appearing, because a tier-B player with prior candidacy is
typically one who keeps being listed and keeps not playing.

**Is this a third instance of "a fallback emits a constant"?** The programme already logged it as
such — `DECISION_LEDGER` D111 ruling 3 names the availability sum as *the third structural defect
this programme has found by looking at what the model EMITS*. Priors: **D092/D102** (the champion
emits a constant at `fallback_level ≤ 2` and keeps emitting it after it knows something) and
**E0_I0028 DEFECT_A** (`pred_sd` is one value per season). **Where this one differs: only 73 % of
it is the constant.** A pure fallback-constant repair leaves roughly half the surplus standing.

**Counterexample not buried.** E0_I0028 measured that routing the v15 `p_active`
declared-constant region to a prior-appearance-rate estimator **loses 4.96 % of pooled Brier
skill** — the flat 0.8 beats that particular replacement. Not contradicted here: Xa
**recalibrates** the constant (an intercept shift within the stratum), it does not replace it
with a different estimator. Different operations, different comparisons.

### 4.4 Reconciling D090

D090: AUC 0.9016, reliability 0.00182 of a 0.09220 Brier (~2 % of error), n = 17,809 player-games
2022–2024, base rate 0.7793. **Not in dispute and not corrected.**

| Row set | n | base | mean `p` | Brier | log-loss | **AUC** |
|---|---:|---:|---:|---:|---:|---:|
| tier A only — D090's picture | 16,312 | 0.7788 | 0.7608 | 0.0932 | 0.3136 | **0.8979** |
| tier B only | 3,772 | **0.1015** | **0.5249** | 0.2905 | 0.8034 | 0.7603 |
| **everything** | 20,084 | 0.6516 | 0.7165 | 0.1302 | 0.4056 | **0.9026** |

Two independent reasons both hold.

1. **AUC is invariant to any monotone transform of the scores; a sum is not.** Adding the broken
   tier-B rows makes AUC *rise* (0.8979 → 0.9026), because tier B is a large, mostly-easy
   negative class that the model does rank below tier A. Discrimination improves while the level
   breaks. Any ranking-based metric was always going to pass.
2. **D090 could not open these rows.** Its DEF-2 records 3,808 v15 forecasts excluded because
   contract v5 has no manifest — exactly the marginal-roster tier-B rows. Its constant-detection
   probe counted only `is_cold_start` rows: **18 rows on v15**, against the 2,239 that carry
   0.800. It examined under 1 % of the affected population.

### 4.5 The population

| Tier B, by last appearance **anywhere**, strictly prior | n | share | mean `p_active` | realised | never returns to this club | excess / team-game |
|---|---:|---:|---:|---:|---:|---:|
| **Z4** last played >200 d ago (a prior season) | 2,637 | **69.9 %** | 0.5355 | 0.1107 | 82.4 % | **+0.805** |
| **Z1** played somewhere within 7 d — for another club | 882 | **23.4 %** | 0.4723 | **0.0068** | **98.1 %** | +0.295 |
| Z0 never appeared anywhere before | 195 | 5.2 % | 0.6939 | 0.3692 | 45.1 % | +0.045 |
| Z2 played 8–30 d ago | 48 | 1.3 % | 0.2660 | 0.1250 | 70.8 % | +0.005 |
| Z3 played 31–200 d ago | 10 | 0.3 % | 0.3234 | 0.7000 | 0 % | −0.003 |

**100 % of tier-B rows are definitionally players with no prior admitted box row (DNP included)
for that club that season** — that is what makes them tier B, so a band on
days-since-last-appearance-*for-this-team* is degenerate there and is reported as such. The
informative axis is last appearance *anywhere*.

**83.8 % of tier-B rows are for a player who never appears for that club again that season**,
carrying 1.1183 `p_active` mass per team-game. 47.3 % never appear anywhere that season; 0.95 %
never appear anywhere in 2021–2024. 266 distinct players carry 1,596.9 units of excess mass; the
largest contributors are established starters held against clubs they had left (Crystal
Dangerfield 44 rows / 3 appearances, Tina Charles, Liz Cambage, Courtney Williams, Natasha
Howard) — **not deep bench and not two-way contracts.**

**Ruling: predominantly a data-freshness / roster-membership defect, with a calibration defect
layered on top.** The distinction changes the fix, as the task said it would: a calibration repair
lowers the probability on a pairing that mostly does not exist; a freshness repair stops
manufacturing the pairing. Only the first was measurable from these artifacts.

`s07` corroborates: 58.9 % of tier-B rows come from source `S2`, which
`prediction_contract_v5.py` documents as *"Tier B, weak, early-season only"* — last season's
roster carried into this season's opening weeks. That matches the Z4 band directly.

### 4.6 Repairs — the full table is `REPAIR_OPTIONS.md`

| | Δ team MAE | tier-A Brier Δ | tier-A verdict | exposure misalloc | coverage loss | both levels |
|---|---:|---:|---|---:|---:|---|
| **Xa** recalibrate per tier | **+7.306** | −0.000148 | NOT ESTABLISHED (0.06× floor) | **8.91 → 4.01** | 0 | **YES** |
| **Xb** normalise the sum | +8.810 | **−0.014239** | **ESTABLISHED HARM (5.7×)** | **8.91 → 8.91** | 0 | NO |
| **Xc** prune | +2.249 | **−0.012558** | **ESTABLISHED HARM (5.0×)** | 8.91 → 5.52 | **5.23 %** | NO |
| **Xd** downstream affine | +9.469 | 0 | unchanged | 8.91 → 8.91 | 0 | NO |

Conditional `pts_hat` MAE on the 13,087 appeared rows is **4.255252** and is bit-identical under
Xa, Xb and Xd by construction — the invariance check passes. Under Xc it is 4.297213 on the
12,403 survivors, with 684 appeared player-games carrying no forecast at all.

**Xd's fitted affine slopes are 0.000 / −0.016 / −0.021 and its correlation with the response is
−0.021.** This sharpens E1_I0033's counterweight: for the *unnormalised* bottom-up sum the
recalibration slope is not merely small, it is negative. Xd reaches the best team MAE in the table
by emitting a constant.

**Xb's downstream null result is the sharpest finding in the repair set.** The exposure producer
allocates a fixed 200 team-minutes proportionally, so a per-team-game uniform rescaling cancels
exactly: Xb's misallocation is **8.912455**, identical to the unrepaired champion to the last
digit. Xb fixes the team sum and changes nothing at all downstream.

**Xa's 2022 fold is largely unrepaired** and this is reported rather than hidden: 2021 emits
nothing but declared constants, so both *fitted* strata have zero training rows and 5,135 of the
2022 rows pass through unchanged. The walk-forward headline is therefore **conservative** — the
ORACLE ceiling (team MAE 10.414, Brier 0.0910, misallocation 1.76) shows the gap.

### 4.7 Production reach

**The defect does not reach production.** Zero references to `p_active` in `daily_forecast.py`,
`daily_refresh.py`, `daily_certify.py`, `props_edge.py`, `props_capture_daily.py`,
`conditional_edge.py`, `calibrated_prob_edge.py`, or in the `wnba-prediction-engine`,
`wnba_odds_system`, `wnba-odds-aggregator`, `forecasts`, `leaderboards` or `modeling_v2` trees.

The shipped per-player forecast is **conditional on playing** — `props_edge.py:349-350` computes
`per36_after × min_after / 36` where `min_after` is an EWMA over played rows only. **There is no
`× P(active)` term.** A miscalibrated `p_active` cannot corrupt it.

The only multiply site in the repository is
`experiments/player_program/build_projected_exposure.py:238`
(`raw_expected_minutes = p_active * e_minutes_given_active`), registered
`production_eligible: False` on all three regimes. **No production path sums `p_active` per
team-game**; every such sum in the repository lives in three exploration screens (E1_I0033,
E1_I0034, this one).

Even in that producer the exposure is damped: it allocates a fixed 200 team-minutes in proportion
to the raw product, so a uniform `p_active` error cancels exactly and only the relative shape
survives. Measured: **14.44 of 200 team-minutes allocated to tier-B rows against 5.53 actually
played — 8.91 minutes per team-game misallocated.**

**Urgency: LOW as a live risk, HIGH as a gate** on promoting anything bottom-up, exposure-based
or props-facing that consumes `p_active`.

---

## 5. Nulls, power and controls

**N1 — paired block sign-flip** on the per-row loss difference. Both arms forecast the same row.
Team cells block at **team-season** (36 blocks); player cells at **player-season** (725 all / 488
tier A / 709 tier B). The block level matches the level each quantity varies at: a per-stratum
recalibration moves a player's whole series together.

**The within-player cyclic shift is not used anywhere** (D108: degenerate for between-entity
quantities, p = 1.0000 in 0 of 15 planted-signal configurations). Every quantity here varies at
team-game level or between strata, both of which a within-player rotation preserves.

**Power verified by injection, and the injection disagrees with the analytic MDE.** The programme
convention MDE80 = 2.802 × null_sd is computed from a difference vector that *carries the effect*,
which inflates the sign-flip null sd. Both are published; **the injection is the authority.**

| Cell | analytic 2.802 × null_sd | injection 80 % floor | direction |
|---|---:|---:|---|
| team MAE | 4.596 (Xb cell) | **2.00** | analytic is **conservative** 2.3× |
| player tier-A Brier | 0.00038 (Xa cell) | **0.0025** | analytic is **ANTI-conservative** 6.6× |

Injection curves (`injection_power_curves.csv`), planting onto a real centred difference vector
so the no-effect world carries this data's dispersion and block structure:

* team: 0.5 → 0.077, 1.0 → 0.290, 1.5 → 0.597, 1.75 → 0.703, **2.0 → 0.827**, 2.5 → 0.963
* player tier A: 0.0005 → 0.087, 0.001 → 0.243, 0.0015 → 0.467, 0.002 → 0.663,
  **0.0025 → 0.847**, 0.003 → 0.967

**No verdict in this screen changes under either floor.** Every team effect (2.249 … 9.469)
clears both; Xb and Xc's tier-A harm clears both; Xa's tier-A effect is below both.

**Type-I check.** 400 synthetic no-effect worlds through the full N1 path: rejection rate at
nominal 0.05 = **0.0650**, p quartiles 0.236 / 0.482 / 0.750. (SE at n = 400 is 0.0109, so 0.065
sits 1.4 SE above nominal — calibrated, mildly liberal, and it does not bind since no verdict
here rests on a p between 0.01 and 0.05.)

---

## 6. Where this screen could have cheated

Declared in `PREREG.md` §5 before any repair statistic.

1. **C-1 — building a repair from realised rates and scoring it on the same rows.** The largest
   cheat and the one the task names. Every headline repair is walk-forward; `Xa-O` is the only
   in-sample arm, is labelled ORACLE and carries no verdict. Its gap to Xa (10.414 vs 10.957 team
   MAE) is the size of the cheat that was declined.
2. **C-2 — pruning then scoring only survivors.** The team response is per team-game and is
   unchanged by pruning; Xc is charged its coverage loss explicitly and it is the number that
   sinks it.
3. **C-3 — reporting only the team level.** Every cell carries both, in the same table.
4. **C-4 — quoting 0.5249 as if it were the declared constant.** Kept separate; the difference is
   the mechanism.
5. **C-5 — using contract v5's tier column.** Not used for any number. Opened once in `s07`,
   descriptively, and it *confirmed* the proxy at 100 %.
6. **C-6 — using `player_bios.csv` to back a number.** Confined to the banner-labelled P02 table.
   That table also turns out to be defective (see `DEFECTS.md` D-5) and nothing rests on it.
7. **C-7 — τ shopping.** τ is fitted by the preregistered rule on strictly earlier seasons; the
   whole curve is published.
8. **C-8 — declaring a discrepancy with a sibling screen carelessly.** DR-R was applied: five of
   E1_I0033's statistics were reproduced exactly *first*, establishing the row set and
   denominator are identical, before any disagreement was written up. The disagreement that
   survived is a textual attribution, verifiable directly on the same frame (1,625 of 3,772).

---

## 7. What is NOT established

* **Nothing about 2025 or 2026.** Never read, joined, plotted or described.
* **That Xa is safe for tier-A forecasts.** −0.000148 sits at 0.06× the injection floor. NOT
  ESTABLISHED — no harm detected and none could have been at that magnitude. This is a failure to
  reject, not a demonstration of safety (D103).
* **That any measured repair is the right one.** Four points in a larger space, on a fixed row
  set.
* **The repair the population analysis actually points at.** Not manufacturing the tier-B
  obligation at all was **not measurable** from these artifacts: it needs a roster source the
  contract explicitly declines to trust, and no manifest-verified artifact in this partition
  supplies one. **This is the largest gap in the screen.**
* **That the exposure-shape numbers transfer to the real producer.** They reproduce the
  proportional step faithfully but omit the 40-minute cap and the water-filling loop.
* **That E1_I0033's conclusions are affected.** Every number of theirs reproduces exactly; one
  sentence of mechanism attribution is corrected and nothing downstream of it changes.
* **That the tier-B population is what `player_bios.csv` says.** Unverifiable, and the one table
  built from it is defective.

---

## 8. Files

| File | What |
|---|---|
| `DEFECT_ANATOMY.md` | **the mechanism, in plain language** |
| `REPAIR_OPTIONS.md` | four repairs, each at both levels |
| `PREREG.md` + `PREREG.sha256` | preregistration |
| `FINDINGS.json` | machine-readable, all steps |
| `DEFECTS.md` | defects in this screen's own work |
| `reproduction_vs_E1_I0033.csv` | §4.1 |
| `p_active_by_tier_and_fallback_level.csv`, `excess_mass_attribution.csv` | §4.2–4.3 |
| `population_footprint_by_tier.csv`, `staleness_bands*.csv`, `tier_b_players.csv` | §4.5 |
| `repairs_team_level.csv`, `repairs_team_level_tests.csv` | §4.6 team |
| `repairs_player_level.csv`, `repairs_player_level_tests.csv`, `REPAIR_SUMMARY.csv` | §4.6 player |
| `Xa_walkforward_fits.csv`, `Xc_tau_curve.csv` | repair construction, auditable |
| `exposure_shape_distortion.csv` | §4.7 |
| `injection_power_curves.csv` | §5 |
| `UNVERIFIABLE_bios_crosstab.csv`, `UNVERIFIABLE_tier_proxy_crosscheck.json` | unverifiable inputs, quarantined |
| `nulls/permutation_draws.npz`, `nulls/type_I_pvalues.npz` | null draws |
| `scripts/` | `av_base.py`, `s01`…`s07` |
| `run_log_s*.txt` | per step |
