# NOTES — E1_I0046_allocation

`PREREG.md` sha256 `b6dd2e6b141295b8accd92c9fb8920ef5d05a9901f35bf74410fb9c1ba331322`, 21,729 bytes.
Read `VERDICT.md` first, then `CEILING.md`, then `DEFECTS.md`. This file is the audit trail.

---

## 1. WHAT WAS ADDED AFTER THE HASH, AND WHICH WAY IT PUSHED

**0 preregistered cells dropped. 3 additions.**

| addition | why | direction |
|---|---|---|
| **`N_PSWAP`** — a second null that reassigns whole player-season series inside the team-season | `N_TGSWAP` destroys the candidate's within-player **serial** structure as well as its assignment. That is the K6 hazard one level over, and a null that destroys more than exchangeability requires is **too narrow**. | **WEAKENS.** Every verdict now requires **both** nulls. It happened not to overturn any cell. |
| **`SUBSTITUTE_TEST`** — the attempts-share allocator and a 50/50 blend, scored as forecasts | The surviving cell adds a *coefficient to a column*. What you would build is an *allocator*. The two are not the same claim. | **WEAKENS, materially.** The implementable form does **not** establish on the decision stratum (ΔR² +0.004647, p 0.0870, floor 0.00743). This is counterweight (b) in `VERDICT.md`. |
| **`TYPE_I_NONCIRCULAR`** — 100 synthetic candidates carrying real player-series structure | The injection DGP permutes residuals inside the team-game, which destroys the same structure the null destroys, so its type-I rate is **circular**. | **CONTROL.** It passed (0.040 / 0.010 / 0.020 against a nominal 0.05). Had it failed, the headline would have died. |

**Fixed after the hash, not added:** the candidate prior halflife is **5**, fixed and never tuned.
`PREREG.md` §5.2 said "prior EWMA" without naming it. No candidate hyperparameter ever saw an
evaluation row.

---

## 2. WHY THE RESPONSE IS WHAT IT IS

The brief's instruction — *conditioning on the realised team total removes the part the team model
already owns and isolates the part only a player model can supply* — is implemented literally:

```
s_i = y_i / SUM_{j in C(g)} y_j          C(g) = every player of that team with minutes > 0
```

Three properties were **asserted, not assumed**, and the run halts on any failure:

1. `SUM_j pts_j == team pts` on all 1,776 team-games, **max |diff| exactly 0**. Same for attempts.
   Minutes closes to 0.0667 (minute:second rounding), which is why the minutes share uses the
   **roster sum** rather than the team box minutes as its denominator.
2. Every response sums to **1** inside every team-game to < 1e-12.
3. Every **synthetic** response, at every θ, in every injection replicate, does the same.

**The two uses of the realised total are kept strictly apart**, which is the whole leakage question:

| use | status |
|---|---|
| `Y_g` defines the response; `C(g)` defines the projection denominator | **LEGITIMATE.** This is the conditioning. |
| any base or candidate column reading `Y_g`, any same-game box quantity, or anything dated on or after `game_date` | **FORBIDDEN, and none does.** Every feature is an explicit `.shift(1)`. `starter_flag` for the current game is excluded by construction; A3 uses the player's **prior** start rate. |

This is why the screen reports oracle ceilings and says so eleven times. `DEFECTS.md` D-07.

---

## 3. THE COMPOSITIONAL CONSTRAINT — WHAT WAS ACTUALLY DONE

D111: *allocations of a shared fixed budget do not survive being modelled separately.*

* **Projection.** `ŝ_i ← max(ŝ_i,0) / Σ_{j∈C(g)} max(ŝ_j,0)`, applied identically to the base arm,
  the augmented arm and **every one of the 2,000 null draws**, so it can advantage neither side.
  Fallback to `1/|C(g)|` if a team-game's projected sum is 0 (this never fired).
* **Blocking.** Every null and every power calculation blocks at the **team-game**. Never the row.
* **The RAW arm is reported beside every cell** — the "model them separately" construction — and
  the difference is a deliverable, not a footnote. It is the largest effect in the screen: three of
  four unfrozen candidates on the primary response **flip sign** when the forecast is made an actual
  allocation (`VERDICT.md` §2).

**A log-ratio (clr/alr) transform was considered and rejected**: **2,506 of the 16,717 appeared
player-games have a points share of exactly 0** (69 of them inside the decision stratum's clean
window, and 14 attempts shares), and the projection denominator has to run over the **whole** roster,
so the zeros cannot be filtered away. A zero-replacement constant is a free parameter sitting in the
middle of the response. Projection has no free parameter.

**A consequence derived before any fit and then tested:** a candidate that is **constant within the
team-game** cannot move a projected allocation to first order. `A5_opp_defrtg` was preregistered as
that demonstration. It returned ΔR² −0.000005, and the within-composition swap is its **literal
identity** (null sd 8.5e-22; exactly 0.0 in two of six cells) — a control that cannot fail, run
deliberately and labelled as such rather than reported as a clean bill of health.

---

## 4. NULLS — WHAT EACH ONE TESTS AND WHAT IT DOES NOT

| null | exchangeability tested | blocks | valid for | NOT valid for |
|---|---|---:|---|---|
| **`N_TGSWAP`** | which player *in this composition* holds which candidate value | 1,776 team-games | every between-player candidate (A1–A4, G01) | anything team-game-constant — it is the **identity** there |
| **`N_PSWAP`** | which player owns a whole candidate **series**, inside the team-season | 48 team-seasons, 634 series | the same set, preserving serial structure | the same exclusion |
| `N_TGBLOCK` | which opponent this composition faced, holding the calendar fixed | 335 dates, 1,776 units | A5 only | between-player candidates |
| `N_WITHIN_PLAYER` | — | 634 player-seasons | **nothing. CONTRAST ONLY.** | everything here |
| `N_SIGNFLIP_TG` | forecast-vs-forecast on the same rows | 764 team-games | Q1 and the substitute test | increments |

**D120 is satisfied by construction, not by assertion.** The family-wise statistic is a max-z over
the four real between-player candidates computed from **one shared draw stream** — a single
permutation per draw applied to all four candidates simultaneously — so the cross-candidate
correlation is preserved and the null is valid for **every** component. Each component was
additionally verified by **component-wise injection into the real response** (`s04`), not by
shuffled residuals, which E1_I0036 found defective.

**The blindness of the within-entity null is demonstrated on this screen's own cells rather than
cited**, and it is worse than a power loss: on two cells whose correct null returns p = 1.0000, the
blind null returns **p = 0.0020 with the sign reversed**, because its own mean sits three times
further negative than the observed statistic (`BLIND_NULL_DEMO.csv`, `VERDICT.md`).

---

## 5. FROZEN AND UNFROZEN — BOTH, EVERYWHERE

* **FROZEN**: intercept **and** base slope held at the base-only fit; only the candidate coefficient
  estimated, on the base's **training** residual, against a **train-mean-centred** candidate, so no
  mean shift can be smuggled in.
* **UNFROZEN**: all coefficients refit.

The mandate for the freeze was a prior component that *"scored +0.0287 at p 0.00005 on rows where it
substituted nothing"*. Here the freeze does its job and the result is the opposite shape: the
surviving candidate scores **−0.004696 frozen** and **+0.005487 unfrozen**, which identifies it as a
**substitute** rather than an addition. Both numbers are in the first paragraph of `VERDICT.md`.
`DEFECTS.md` D-03 explains why the freeze is structurally punitive for a collinear substitute and
why that is a feature.

---

## 6. THE POWER PICTURE, HONESTLY

For the one surviving cell (`R1_s_pts / A2 / UNFROZEN / DECISION / CLEAN`):

| floor | value | observed / floor | kind |
|---|---:|---:|---|
| analytic `2.80 × null_sd` | 0.000731 | **7.5×** | analytic |
| injection-verified, recovered units | 0.000926 | **5.9×** | **injection** |
| block bootstrap `2.80 × boot_sd` | 0.005897 | **0.93×** | bootstrap |

**The bootstrap and the permutation null disagree by 8.08×**, where E1_I0034 measured the same ratio
at 0.963–1.013. This is the single largest unresolved item in the screen and it is counterweight (a)
in `VERDICT.md`. The two estimate different things — the permutation asks whether the assignment
carries information, the bootstrap asks whether this *number* would replicate — and the direct
evidence on replication is the season split: **+0.005472 (2023), +0.005503 (2024), +0.008590
(disclosed 2022)**, three independent evaluation seasons far tighter than a sd of 0.0021 predicts.
The verdict is stated under both.

**Block counts are never marginal.** The smallest is 48 (N_PSWAP team-seasons), well above the six
below which a two-sided sign-flip cannot reject; the sign-flip cells carry 764 blocks.

---

## 7. THE STABILITY QUESTION, AND WHY THE ANSWER IS SMALL

Share and level are **different responses** and are never compared by ΔR², MAE, skill ratio or
variance share (D101). The **only** cross-response quantities in this screen are **autocorrelation**
and **ICC**, both unitless, both computed on **identical rows** in identical `(game_date, game_id)`
order within `(season, player_id)`. That exception is declared in `PREREG.md` §8 and justified there.

The answer is **no** — the acf1 gap runs from **−0.0023** (points, decision stratum, clean window)
to **+0.0116** (minutes, decision stratum, all seasons) — and the reason is arithmetic:
`sd(log team points) = 0.1359` against `sd(log player points) = 0.6499`, so the team total is only
**4.4 %** of the level's log-variance. **There was at most ~4 % of variance available to strip out.**
On minutes it is 0.8 %, which is why the minutes gap is the largest in *relative* terms and still
+0.009 in absolute terms.

The team total is also **weakly autocorrelated in its own right** (+0.1524 within team-season on
points, +0.0159 on minutes), so removing it removes very little persistence either.

---

## 8. WHAT WAS NOT DONE, DELIBERATELY

* **No champion was fitted** and **no production change is proposed.**
* **The shared screen kit was not imported and not modified.** Everything needed is reimplemented in
  `scripts/al_base.py`; `PlayerSeriesSwap` follows `E0_I0016/ep_base.py::EntitySwap` (read-only) and
  that authorship is credited in the source. The anchor block is the check that the reimplementation
  is faithful — and it reproduces `E1_I0043`'s decision-stratum counts (5,673 / 149 / 708 / 3,167)
  exactly from a completely independent frame built from `master_player`.
* **No name-based column selection anywhere.** Every list is an explicit literal, printed when
  resolved, with its length asserted against a literal (`RESPONSES` 3, `CANDIDATES` 6,
  `BETWEEN_PLAYER_CANDIDATES` 5, `MP_COLS` 12, `MT_COLS` 9). The partition gate is value-based and
  date-checks a column only if its dtype is genuinely datetime.
* **2021 was never evaluated** and **2025/2026 was never read, joined, merged or described.**
* **No process outside this screen was touched.** The only processes stopped were PIDs this screen
  launched and recorded (`scripts/_s04_pid.txt`), stopped by id, never by a blanket kill.

---

## 9. WHAT WOULD MOVE THIS RESULT

1. **A live roster and a live total.** Everything here is an oracle ceiling. The single highest-value
   follow-up is not another candidate, it is an availability forecast that sums to a basketball team
   (E1_I0033 measured 10.34 against 9.40).
2. **More seasons.** The clean window is two. The attempts effect replicates across all three
   available evaluation seasons, which is the strongest evidence in the screen, and three is still
   three.
3. **The blend, on the decision stratum, with more rows.** ΔR² +0.004647 at p 0.0870 against a floor
   of 0.00743 is exactly the shape that resolves with data and cannot be resolved by argument.
4. **A joint allocation model rather than a projected regression.** The projection is a crude way to
   respect the simplex. A model that is compositional by construction would not lose 36 % of its own
   ceiling to the projection step — and given that the constraint is the largest effect in this
   screen, that is where the next increment most plausibly lives.

---

## 10. FILE MAP

| file | what |
|---|---|
| `PREREG.md` / `PREREG.sha256` | the frozen design |
| **`CEILING.md`** / `CEILING.csv` | the arithmetic ceiling and the gate, computed **before** any fit |
| **`VERDICT.md`** | the decision-stratum result, frozen and unfrozen, in the first three sentences |
| **`STABILITY.csv`** / `STABILITY_COUNTERWEIGHT.csv` | share-vs-level autocorrelation and ICC, plus the arithmetic cap on the gap |
| `ANCHORS.csv` | 20 anchors, 17 at exactly 0.000e+00; the run halts on any failure |
| `DECISION_STRATUM.csv` | the census, reported before any pooled number |
| `REFERENCE_TUNING.csv` | the 42-combination tuned reference, selected on strictly earlier seasons |
| `Q1_ALLOCATION_FORECASTABLE.csv` | tuned vs naive vs equal split |
| `PRIMARY_CELLS.csv` | every response × candidate × arm × projection × population |
| `NULLS.csv` / `NULLS_PSWAP.csv` / `FAMILYWISE.csv` | both matched nulls and the max-z family correction |
| `BLIND_NULL_DEMO.csv` | the within-player null manufacturing a survivor with the wrong sign |
| `INJECTION_POWER.csv` / `POWER_FLOORS.csv` / `TYPE_I_NONCIRCULAR.csv` / `BOOTSTRAP_VARIANCE.csv` | power |
| `PLACEBOS.csv` / `RESPONSE_PLACEBO.csv` / `LEAKAGE_PROBE.csv` | controls |
| `SUBSTITUTE_TEST.csv` / `SEASON_STABILITY.csv` | the two post-hash weakening tests |
| `nulls/*.npz` | raw, unstandardised, **signed** draws — absolute values are never stored |
| `DEFECTS.md` | ten defects, four of which would have changed a published number |
| `FINDINGS.json` | machine-readable, with sha256 of every `.md` and `.csv` in the directory |
| `scripts/` | `al_base.py` + `s00`–`s06`, with the full captured `run_log_s0*.txt` for each |
