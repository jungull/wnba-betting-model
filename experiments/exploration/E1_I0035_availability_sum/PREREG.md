# PREREG — E1_I0035_availability_sum

**Preregistered before any repair statistic was computed.** The only computation that precedes
this file is (i) the anchor reproduction (D076's 13,879 appeared player-games, required by the
programme standard to run *before* any new statistic) and (ii) the arithmetic reproduction of
E1_I0033's four disputed descriptive quantities, which are reproductions of published numbers,
not tests. Both are in `run_log_s02.txt` and neither involves a hypothesis, a null or a verdict.

Seed **20260810**. Partition **2021–2024**. 2025 and 2026 are sealed and are never enumerated by
any loader; `av_base.assert_partition` raises on their presence.

---

## 0. What is being measured, and what is NOT

This is a **defect investigation**. The valuable output is a mechanism, not an effect size. Two
things are separated throughout and never conflated:

* **JUDGING calibration** against realised appearance rates — legitimate, and used freely.
* **BUILDING a repair** from realised appearance rates and then scoring it on the same rows —
  **circular**. Every headline repair below is fitted **walk-forward on strictly earlier seasons
  only**. Where an in-sample / same-season version is also computed it is labelled **ORACLE**,
  is excluded from every verdict, and is published only as the ceiling the walk-forward version
  is trying to reach.

**No repair is enacted.** Nothing in this screen writes to any arm, contract, registry or
production path. Every model change requires the user's authorisation.

---

## 1. Row sets and denominators (D101)

| id | definition | n |
|---|---|---:|
| **RS1** | team-games: season ∈ {2022,2023,2024}, `season_type == "Regular Season"`, team-arm forecast present, ≥1 champion player row | **1,392** |
| **RS1P** | the champion's player rows on RS1 team-games | **20,084** |
| **RS1P-A** | RS1P ∩ contract-v4 universe (tier A) | **16,312** |
| **RS1P-B** | RS1P \ contract-v4 universe (tier B) | **3,772** |
| **RS1P-APP** | RS1P rows with `appeared == 1` | (stated at use) |

`tier_A` is defined **only** as membership in the manifest-verified `prediction_contract_v4`
row-uid set. `prediction_contract_v5` carries the arm's real `universe_tier` column but has **no
sibling manifest → UNVERIFIABLE → may not back a number**, so it is used nowhere.

**Denominator declaration.** Team-level numbers share response `master_team.pts`, row set RS1,
SST 168 710.4073, no weighting, no base. Player-level numbers are declared separately at each
table with their own response, row set and n. **No team-level ΔR² is ever compared with a
player-level ΔR², and no skill ratio crosses the two levels without the response difference
being stated in the same sentence.**

---

## 2. Columns

Every column set is an explicit tuple in `scripts/av_base.py` (`MASTER_TEAM_COLS`,
`MASTER_PLAYER_COLS`, `PRED_COLS`), resolved through `av_base.pick`, which prints the resolved
list and asserts the count. **No substring or name-pattern column selection anywhere.**

---

## 3. Preregistered cells

### Group R — reproduction (descriptive; no null, no verdict)

| cell | quantity | E1_I0033's value |
|---|---|---:|
| R01 | universe rows per team-game | 14.428 |
| R02 | realised roster per team-game | 9.4016 |
| R03 | Σ`p_active_hat` per team-game | 10.3381 |
| R04 | tier-B mean `p_active_hat` | 0.5249 |
| R05 | tier-B realised appearance rate | 0.1015 |
| R06 | B1 level bias | +8.139 |

**Decision rule DR-R:** a reproduced value within 5e-4 of the published one is CONFIRMED.
Outside that, the discrepancy is written up **loudly**, with my working shown, and I state
which of the two I believe and why. A prior coordinator twice began writing up a false
discrepancy and was wrong both times, so a disagreement is only published after the input
provenance, the row set and the denominator have each been checked to be identical.

### Group M — mechanism (descriptive; no null)

* **M01** share of tier-B rows carrying the declared constant, by `pa_fallback_level`.
* **M02** attribution of the Σ`p_active` excess to (tier × declared-constant/fitted) cells.
  Shares are of the **net** excess and may be negative; they sum to 1 by construction.
* **M03** appearance rate, mean `p_active`, and calibration of the **fitted** tier-B rows —
  the test of whether this is a fallback-constant defect or a train/score population defect.

### Group P — the population (descriptive; no null)

* **P01** tier-B rows by realised career footprint in `master_player` (manifest-verified, row
  granularity): games ever played in partition, first/last appearance date, whether the player
  ever appears for this team in this season, days since their last appearance for this team.
* **P02** the same cross-tabulated against `player_bios.csv`. **`player_bios.csv` has NO
  manifest → UNVERIFIABLE → it may not back a number.** P02 is therefore published as
  *colour only*, is labelled UNVERIFIABLE in every table it touches, and no conclusion in
  `DEFECT_ANATOMY.md` or `REPAIR_OPTIONS.md` rests on it. P01 carries the load.
* **P03 (the decisive one)** — the distinction the task turns on. For each tier-B row, is the
  player *still on this team's roster in the pre-game-knowable sense*? Operationalised without
  the unverifiable contract as: `days_since_last_appearance_for_this_team_this_season`, and
  whether the player has **any** later appearance for this team this season. A universe row for
  a player who never appears for that team again in that season is a **staleness** row, not a
  calibration row.

### Group X — the repairs (tested; walk-forward; no repair is enacted)

All four are applied to the same RS1/RS1P frames. `w` denotes the availability weight used in
the bottom-up sum; the champion's own emission is `w = p_active_hat`.

| cell | repair | construction | fitted on |
|---|---|---|---|
| **X0** | none (the champion as emitted) | `w = p_active_hat` | — |
| **Xa** | **recalibrate per tier** | logistic recalibration of `logit(p_active_hat)` within each (tier × declared-constant) stratum: `w = σ(α_s + β_s·logit p)` | **strictly earlier seasons only**; the 2022 fold sees 2021 only |
| **Xa-O** | *the same, in-sample* | *same, fitted on the scored season* | **ORACLE — diagnostic, no verdict** |
| **Xb** | **normalise the sum** | `w = p_active_hat · (R̂ / Σ p_active_hat)` where `R̂` is the team's **strictly prior same-season** mean realised roster size | prior games only |
| **Xc** | **prune the universe** | drop rows with `p_active_hat < τ`; `w = p_active_hat` on survivors | τ chosen on **strictly earlier seasons** to equate Σ`w` to the prior-season roster size |
| **Xd** | **leave it, fix downstream** | `w = p_active_hat`, then a walk-forward affine `a + b·B1` at the team total | strictly earlier seasons |

**Every cell is reported at BOTH levels. A repair that fixes the team sum but degrades
individual forecasts is NOT a repair, and the player-level table is the one that decides it.**

#### Team-level response (RS1, n = 1,392, response `pts`, SST 168 710.4073)
`MAE`, `bias`, `R²` on the common SST, correlation with the response, and the walk-forward
affine slope (a slope near zero means the arm has been shrunk to a constant and is no longer
carrying player information — E1_I0033's counterweight, carried forward).

#### Player-level responses — three distinct products, each with its own declared denominator

1. **`p_active` as a probability forecast of appearance.** RS1P, n = 20,084, response
   `appeared`. Brier, log-loss, AUC, and the calibration intercept/slope from a logistic
   regression of `appeared` on `logit(w)`. Reported for RS1P, RS1P-A and RS1P-B separately,
   because a repair that helps tier B may hurt tier A and the pooled number would hide it.
2. **Unconditional expected points**, `w · pts_hat`, RS1P, n = 20,084, response `pts` (0 for a
   non-appearance). MAE, bias. This is the quantity a "will this player go over 12.5" market
   actually needs when availability is uncertain.
3. **Conditional points on appeared rows**, `pts_hat`, RS1P-APP, response `pts`. MAE.
   **This is an INVARIANCE CHECK**: no repair to `p_active` may move it, because `pts_hat` is
   emitted conditional on playing and no repair below touches it. If it moves, I have a bug.
   Xc is the exception and that is the point — pruning deletes forecasts, so Xc is additionally
   charged its **coverage loss**: the number and share of *appeared* player-games left with no
   forecast at all.

### Decision rules, fixed now

* **DR1** — a repair is TEAM-BENEFICIAL if its RS1 MAE improvement over X0 is significant
  under N1 **and** exceeds that cell's MDE80.
* **DR2** — a repair is PLAYER-SAFE if it does not significantly worsen Brier on RS1P **and**
  does not significantly worsen Brier on RS1P-A (the tier where the product lives), and leaves
  the conditional `pts_hat` MAE bit-identical.
* **DR3** — a repair is RECOMMENDABLE FOR MEASUREMENT only if DR1 and DR2 both hold. Anything
  else is reported with both effects and no recommendation.
* **DR4** — if a comparison is underpowered (|effect| < MDE80) the verdict is **NOT
  ESTABLISHED**, never "no effect" (D103).

---

## 4. Nulls, and the level they are matched to (D108)

**N1 — paired block sign-flip on the per-row loss difference.** Both arms forecast the same row,
so the comparison is paired.

* Team-level cells block at **team-season** (36 blocks). A team's whole forecast series shares
  its fitted state.
* Player-level cells block at **player-season**. This is the level a `p_active` repair varies
  at: a per-tier recalibration moves a player's whole series together, so a row-level flip
  would be anticonservative in the usual way.

**The within-player cyclic shift is NOT USED ANYWHERE.** D108 established it is degenerate for
between-entity quantities (p = 1.0000 in 0 of 15 planted-signal configurations). Every quantity
here varies either at team-game level or between strata, both of which a within-player rotation
preserves exactly.

**N2 — the naive row-level flip.** Computed *only* to publish the inflation factor N1/N2.
**Never carries a verdict.**

**VERIFY BY INJECTION, before any verdict.** For every null used, a known constant effect is
planted into the loss vector and the detection rate at nominal 0.05 is measured over ≥200
replicates. A null that does not detect its own planted effect is reported as powerless and its
cell is declared NOT ESTABLISHED regardless of the p it produces. `null_mean` and `null_sd` are
printed beside every p (D103 ruling 2), and **MDE80 = 2.8016 × null_sd** is stated for every
comparison.

**Type-I check.** 400 synthetic no-effect datasets pushed through the full N1 path; the
rejection rate at nominal 0.05 is reported.

---

## 5. Where this screen could cheat, declared in advance

* **C-1 — building the repair from realised rates and scoring it on the same rows.** The
  largest available cheat, and the one the task names. Handled by the walk-forward/ORACLE split
  above; every ORACLE arm is labelled and excluded from every verdict.
* **C-2 — pruning the universe and then scoring only the survivors.** This would make Xc look
  free. The team-level response is per **team-game**, which is unchanged by pruning, and Xc is
  charged its coverage loss on the player side explicitly.
* **C-3 — reporting only the team level.** The task states the per-player forecast is the
  product. Every cell carries both, in the same table, always.
* **C-4 — quoting the tier-B mean 0.5249 as if it were the declared constant.** These are
  different objects and the difference is the mechanism. Kept separate throughout.
* **C-5 — using `prediction_contract_v5`'s tier column.** UNVERIFIABLE. Not used. Tier is
  defined from manifest-verified v4 membership only.
* **C-6 — using `player_bios.csv` to back a number.** UNVERIFIABLE. Restricted to P02, labelled
  everywhere, loads no conclusion.
* **C-7 — τ shopping in Xc.** τ is fitted by a stated rule on strictly earlier seasons, not
  chosen by looking at the scored result. The whole τ curve is published so the choice is
  auditable.
* **C-8 — declaring a discrepancy with E1_I0033 without checking my own row set first.** DR-R
  above.

---

## 6. Deliverables

`PREREG.md` (+ sha256) · `FINDINGS.json` · `NOTES.md` · `DEFECT_ANATOMY.md` ·
`REPAIR_OPTIONS.md` · `DEFECTS.md` · a CSV for every published number · `nulls/*.npz`.
