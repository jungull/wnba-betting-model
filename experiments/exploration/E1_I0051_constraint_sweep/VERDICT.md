# Which other screens modelled a constrained quantity without honouring the constraint?

**E1_I0051_constraint_sweep.** `PREREG.md` sha256
`05b1e7ec055eb7f1442baf13aa76da760d0f78be6ba71bdda85b956489ca8c5f`, 21,909 bytes, every cell and
the selection rule fixed before anything was fitted.

---

## THE ANSWER, IN THE FIRST THREE SENTENCES

**Of 67 screen directories carrying 85 distinct responses, 32 screens had no constrained response
at all, 12 have no response to constrain, 8 honoured their constraint and 1 could not be
determined — leaving 14 screens VIOLATED, of which 11 are the same violation: they modelled player
MINUTES, which is a hard budget of 200 team-minutes fixed by the rules of basketball, without ever
requiring their forecasts to sum to it.**

**No published verdict changes, and thirteen of the fourteen violations are harmless because their
published verdicts are already kills, nulls or not-establisheds.** The three candidates that flip
sign under the constraint are candidates no minutes screen ever published, so there is no published
number to overturn; what the flips establish is that **the construction all eleven screens used is
sign-unreliable**, not that any of their conclusions was wrong.

**The fourteenth is not harmless and it was not re-measured here: `E1_I0004_shot_selection` carries
a live `KEEP-AS-LEAD` (β +0.7743, family-wise p 0.0002) on a five-zone simplex response, and its
five fitted shares PROVABLY do not sum to 1** — see §1.2. **That is the single highest-value
follow-up this screen produces and it is a flag, not a finding.**

**The one thing that is new and actionable is not a candidate at all: forcing a minutes forecast to
sum to the budget improves it by ΔR² +0.020020 pooled (z +10.89, p 0.0005, 960 team-game blocks)
and +0.031318 on the decision stratum (z +2.17, p 0.0350, 764 blocks) — and unlike every number in
`E1_I0046`, the budget half of that projection is available before tip-off.**

---

## 1. MOST OF THE PROGRAMME WAS NEVER EXPOSED, AND THAT IS THE MAIN RESULT

`CONSTRAINT_CENSUS.csv`, 85 response rows over 67 directories:

| screen-level classification | screens |
|---|---:|
| **NOT-APPLICABLE — the response was never constrained** | **32** |
| NO-RESPONSE — audits, meta-audits, provenance work, a queue, the kit | 12 |
| **VIOLATED** | **14** |
| HONOURED | 8 |
| NOT-DETERMINABLE | 1 |

*(50 of the 85 individual response rows are NOT-APPLICABLE. `E1_I0004_efficiency_transfer` is
excluded from every count: its own `ABANDONED.md` voids every number in it.)*

**The reason so few are exposed is a distinction the preregistration fixed before the census, in
§2, precisely so it could not be adjusted afterwards to produce casualties:**

> A response is constrained only if its components sum to something **fixed at a higher level** —
> determined *independently of the components themselves*.

| | components sum to | fixed higher up? | constrained? |
|---|---|---|---|
| player **minutes** | 200 + 25·(OT periods) | **YES — by the rules** | **YES** |
| player points / attempts / rebounds | the team total | **NO — the total IS the outcome** | **no** |
| `p_active` over a roster | the realised roster size | **NO — a random variable** | **no** |
| a share response `y_i / Σ y_j` | 1 | YES, but **self-imposed** | yes |

**Modelling player points independently does not break a budget; it implies a team total.** This is
why `E1_I0046`'s result does not sweep the programme: that screen *created* its constraint by
choosing a share response and conditioning on the realised total, which is also why it declares
oracle ceilings eleven times. **D127 ruling 3 binds far fewer screens than its wording suggests.**

The distinction was **measured, not asserted** (`out/s00.txt`, `out/s00b.txt`):

| team-game total | mean | **cv** | on a rules lattice? | MAE of the best pre-tip assertion | **as % of the total** |
|---|---:|---:|---|---:|---:|
| **minutes** | 201.270 | **0.0291** | **YES — 1,776 of 1,776 within 0.066667 of a multiple of 25; 95.2703 % at exactly 200** | **1.26984** | **0.631 %** |
| points | 81.885 | 0.1344 | no | 8.75004 | 10.686 % |
| attempts | 68.250 | 0.0924 | no | 4.95242 | 7.256 % |
| player `possessions` | 408.238 | 0.0546 | no | — | — |
| player `usage_percentage` | 1.7016 | 0.1376 | no | — | — |

**Minutes is the only response in this programme that passes the budget gate, and it passes it by
an order of magnitude.**

### 1.1 The fourteen violations

**Eleven are minutes** — `E0_I0011`, `E0_I0015`, `E1_I0004_efficiency_transfer_v2`, `E1_I0020`,
`E1_I0022`, `E1_I0027`, `E1_I0031`, `E1_I0032`, `E1_I0034`, `E1_I0039`, `E1_I0042`.

**Two are per-event rebound allocation** — `E0_I0003` and `E0_I0008`, whose event-level responses
allocate a budget of exactly one rebound across ten players. Both verdicts are nulls, and
`E1_I0036` already re-levelled the rebound family and found D111 survived. **Exposure: nil.**

**One is a five-zone shot-mix simplex** — `E1_I0004_shot_selection`. See §1.2.

### 1.2 THE ONE EXPOSED LIVE LEAD, AND IT WAS NOT RE-MEASURED HERE

`E1_I0004_shot_selection`'s response is `share_z`: a player-game's share of her **own** field-goal
attempts falling in each of five zones. The five shares sum to 1 within every player-game. Its
verdict on the selection channel is **`KEEP-AS-LEAD`**: β **+0.7743** row-level / **+0.9193**
cluster-level, R² **0.035209**, player-game ΔR² **+0.0191**, opponent-team-season permutation
p **0.0002** unadjusted *and* family-wise across the five zones (both at the 1/5001 resolution
floor). **This is a live, positive, family-wise-significant lead.**

It was classified `NOT-DETERMINABLE` from its documents and **resolved by reading its source**:

* `analyze.py:200` and `dr2_playergame.py:69` both loop `for z in ZONES:` and fit **five
  independent per-zone regressions**. A case-insensitive search of the whole directory for
  `softmax|multinomial|dirichlet|simplex|renorm|normalis|normaliz|"sum to 1"|jointly|compositional`
  returns **one hit** — the word *compositional* used descriptively in `NOTES.md:167`.
* **And the violation is provable, not merely unchecked.** The regressor `OS_z` is constructed as
  `pre_z/pre_tot − lg_share_prior_z`; both terms sum to 1 across zones, so **`Σ_z OS_z = 0` by
  construction**. The fitted increment to the share vector is `Σ_z b_z·OS_z`, which is identically
  zero **only if all five `b_z` are equal**. They are `+0.774 / +0.653 / +0.556 / +0.325 / +0.563`
  — spread by more than 2×. **The five fitted shares provably do not sum to 1.**

**This screen did not re-measure it.** Doing so needs the shotchart frame (132,558 shots) and a
different construction from the minutes work, and the preregistered selection rule of §4 sent the
re-measurement budget to minutes on a measured gate. **It is recorded as a flag and as the single
highest-value follow-up, not as a finding, and nothing here says the lead is wrong.**

### 1.3 `E1_I0034` declared its own violation and nobody repaired it

This is a quotation, not a measurement of mine:

> *"a team's trailing-form minutes do not sum to 200 — they sum to 199 when everyone is healthy and
> to **250** when three rotation players are out … **Fix the trailing-form arithmetic before
> anything else.** … This is the same class of defect as D111 ruling 3."*

`E1_I0042` reproduced that accounting exactly — all 20 published figures — and **did not repair it
either**. The violation has been named, quantified at 250 against 200, attributed to the right
ruling, and left in place across two screens.

---

## 2. THE PROJECTION IS AN IMPROVEMENT, AND ITS BUDGET IS LIVE

`Q1_PROJECTION_EFFECT.csv`, `PROJECTION_SIGNFLIP.csv`. Response `M_level_min` (minutes as a
**level**, the construction every violating screen used), tuned prior-minutes EWMA base, `(h,k)`
selected on strictly earlier seasons, SST on the scored rows, unweighted, paired sign-flip over
whole team-games:

| row set | n | blocks | R² RAW | R² PROJ_BUDGET | R² PROJ_ORACLE | **ΔR² BUDGET vs RAW** | **ΔR² ORACLE vs RAW** |
|---|---:|---:|---:|---:|---:|---:|---:|
| **DECISION × CLEAN 2023–24** | 3,167 | 764 | 0.228338 | 0.259656 | 0.285863 | **+0.031318** (z +2.17, p 0.0350) | +0.057525 (z +3.47, p 0.0010) |
| all appeared, clean window | 9,056 | 960 | 0.643469 | 0.663489 | 0.668045 | **+0.020020** (z +10.89, p 0.0005) | +0.024576 (z +11.97, p 0.0005) |

**`PROJ_BUDGET` uses only the number 200. It captures 81.5 % of the oracle projection's gain
pooled and 54.4 % on the decision stratum.** `E1_I0046` had to grant two oracles — the realised
total and the realised roster — and stated eleven times that no number in it was an achievable live
increment. **This screen grants one.** The budget is knowable before tip-off at an MAE of 0.631 % of
itself; **the denominator set `C(g)` is still an oracle, and that is this screen's largest
limitation** (`DEFECTS.md` D-05).

### Why nobody caught the violation

`BUDGET_VIOLATION.csv`. An independently-modelled minutes forecast, summed over the appeared roster:

| base | mean team-game sum | sd | **MAE vs 200** | within 5 minutes of the budget |
|---|---:|---:|---:|---:|
| prior-minutes EWMA `h=3, k=0` | **201.5603** | 17.2478 | **13.0942** | **28.49 %** |
| `h=13, k=0` | 201.3053 | 19.1243 | 14.9254 | 22.64 % |

**The mean is fine. The dispersion is not.** The violation is **10.3× the budget's own pre-tip
uncertainty**. This is the same shape as D112 — `p_active` was checked one player at a time and
never summed — and as `E1_I0035`'s adopted invariant that *AUC is never sufficient for a forecast
that will be summed.*

---

## 3. THE SIGN FLIPS

`SIGN_FLIPS.csv`. Response `M_level_min`, DECISION stratum (`n_prior ≥ 8` AND
`prior5_minutes ≥ 24`), clean window 2023–24, **n = 3,167 in 764 team-game blocks**, SST on the
scored rows, unweighted, base `B_TUNED`, null `N_TGSWAP` (within-team-game swap, 1,776 blocks),
2,000 draws.

**UNFROZEN — three of five between-player candidates flip:**

| candidate | **RAW** | z, p | family-wise p | **PROJ_BUDGET** | z, p | family-wise p | flip |
|---|---:|---|---:|---:|---|---:|---|
| `A1_pts_share_prior` | **+0.004501** | +6.78, 0.0005 | **0.0005** | **−0.005456** | −4.92, 0.9975 | **1.0000** | **YES** |
| `A2_fga_share_prior` | **+0.004210** | +6.39, 0.0005 | **0.0005** | **−0.004702** | −4.11, 0.9960 | **1.0000** | **YES** |
| `A3_starter_rate_prior` | +0.000162 | +0.45, 0.2459 | 0.6692 | +0.001368 | +2.43, 0.0020 | 0.0150 | no |
| `A4_vac_x_own` | +0.000877 | +0.46, 0.3238 | 0.6597 | **−0.018404** | −5.90, 1.0000 | 1.0000 | **YES** |
| `G01_noise` *(control)* | −0.000402 | −0.25, 0.7036 | 0.9695 | −0.000317 | −0.02, 0.6297 | 0.9375 | no |

**Modelling minutes independently produces TWO family-wise-significant survivors at p 0.0005.
Requiring the forecast to sum to the budget leaves NONE, and reverses both.** That is `E1_I0046`'s
signature reproduced on a different response, a different construction, and a budget that is real
rather than self-imposed.

**FROZEN — zero of five flip, and this is the half that must be reported with it:**

| candidate | RAW | **PROJ_BUDGET** | z | family-wise p |
|---|---:|---:|---:|---:|
| `A1_pts_share_prior` | +0.003365 | **+0.021110** | **+28.49** | **0.0005** |
| `A2_fga_share_prior` | +0.003141 | **+0.020479** | +27.65 | **0.0005** |
| `A3_starter_rate_prior` | +0.000164 | +0.005088 | +8.74 | 0.0005 |
| `A4_vac_x_own` | +0.003156 | +0.012132 | +3.54 | 0.0010 |
| `G01_noise` | −0.000401 | −0.000344 | −0.21 | 0.9680 |

**The two arms say something sharper than either alone.** Frozen, the projection reveals large real
allocation-shape information that is nearly invisible RAW (`A1`: +0.003365 → +0.021110, a factor of
6.3). Unfrozen, the same candidates go negative. **The reason is structural, not statistical: both
arms fit in RAW space and the projection is applied afterwards, so the unfrozen refit is optimising
the wrong objective** (`DEFECTS.md` D-04). That is precisely the construction the eleven violating
screens used — which makes it the right thing to measure and the wrong thing to build.

### What most weakens the sign-flip headline, in the same table

`BOOTSTRAP_VARIANCE.csv`, 1,000 resamples of the 764 team-game blocks:

| candidate, UNFROZEN | PROJ_BUDGET | boot sd | **t** | MDE80 boot | **|obs| ÷ floor** | verdict under the bootstrap |
|---|---:|---:|---:|---:|---:|---|
| `A4_vac_x_own` | −0.018404 | 0.002233 | **−8.24** | 0.006253 | **2.94×** | **established** |
| `A1_pts_share_prior` | −0.005456 | 0.001855 | −2.94 | 0.005193 | 1.05× | marginal |
| `A2_fga_share_prior` | −0.004702 | 0.001793 | −2.62 | 0.005021 | **0.94×** | **NOT ESTABLISHED** |

**One of the three flips does not clear its own preregistered bootstrap floor and a second clears
it by five per cent.** The honest headline is **one established flip, one marginal, and one the
bootstrap does not support** (`DEFECTS.md` D-09). The permutation null and the bootstrap disagree
here as they did in `E1_I0046`, and both are stated.

**Stability, which cuts the other way.** `SEASON_STABILITY.csv`: all three flipped candidates are
negative under `PROJ_BUDGET` in **every** evaluation season — `A1` −0.005240 / −0.005673 /
−0.009308 and `A4` −0.028943 / −0.008231 / −0.036008 across eval 2023, eval 2024 and the disclosed
2022 contrast. **The sign is not a fold artefact.**

---

## 4. THE ARITHMETIC CONTROL DID EXACTLY WHAT IT WAS PREREGISTERED TO DO

`A5_opp_defrtg` is constant within the team-game. Under its **correct** null (`N_TGBLOCK`, opponent
permuted within date) it is null in both arms — RAW −0.001812 (p 0.9620), PROJ_BUDGET −0.000870
(p 0.9460) — and **the projection attenuates it toward zero**, as a candidate incapable of moving an
allocation must.

Under `N_TGSWAP` it is the **literal identity**, and the measured null sd is **6.513e-19**,
**2.171e-19**, and **exactly 0.000e+00** in one of the four cells. Run deliberately; reported as a
control that cannot fail, not as a clean bill of health.

---

## 5. THE BLIND-NULL DEMONSTRATION, RE-RUN AND POINTING THE OTHER WAY

`BLIND_NULL_DEMO.csv`. A within-player cyclic null applied to a between-player candidate, on this
screen's own cells:

| cell | observed | correct `N_TGSWAP` | **blind within-player** |
|---|---:|---|---|
| `A1_pts_share_prior` FROZEN | **+0.021110** | null mean −0.000582, z +30.48, **p 0.0025** | null mean **+0.030311**, z −3.19, **p 1.0000** |
| `A4_vac_x_own` UNFROZEN | −0.018404 | z −5.84, p 1.0000 | z **−11.91**, p 1.0000 |

`E1_I0046` showed the blind null **manufacturing** a survivor with the sign reversed. **Here it
does the opposite: it destroys a real one**, because its own null mean (+0.030311) sits *above* the
observed statistic. **A blind null is not conservatively wrong. It is arbitrarily wrong, in
whichever direction its own centre happens to fall** — which is a stronger statement than either
screen makes alone.

---

## 6. THE AVAILABILITY DEFECT READS THE SAME WAY, AND THAT IS THE ANSWER

Full treatment in `AVAILABILITY_AS_CONSTRAINT.md`. In one paragraph:

**No, the constraint framing suggests no repair the calibration framing missed, because a roster sum
is not a budget.** Measured: the realised roster size has cv **0.10706** against the minutes budget's
**0.02910**, and the best pre-tip assertion misses it by **8.94 %** of itself against the budget's
**0.631 %** — **14.17× looser**. What the framing does contribute is a *derivation* of something
`E1_I0035` had to measure: `Xb` is a **uniform per-team-game rescaling**, the exposure producer
**renormalises within the team-game**, and a uniform rescaling therefore cancels **identically** —
verified at max deviation **2.132e-14** on this screen's own team-game structure. That predicts
`E1_I0035`'s measured Xb misallocation of **8.912455 minutes, identical to the unrepaired champion
to the last digit**, with no data. **It closes a family of repairs; it opens none. D112's
recommendation stands exactly as recorded and no repair is enacted or proposed.**

The census entry that surprised me: **the one place in this programme where the 200-minute budget is
actually enforced is the exposure producer — shipping code, registered `production_eligible: False`,
that nobody was auditing.** Thirteen screens modelled minutes against that budget without enforcing
it. The producer got it right.

---

## 7. WHAT FOLLOWS, AND WHAT DOES NOT

1. **No published verdict changes and none should be reopened.** The eleven minutes screens'
   published conclusions are kills, nulls and not-establisheds; `E1_I0042` already reports its own
   frozen minutes effect at **0.55× its injection-verified floor** and labels it
   `BELOW_FLOOR_NOT_ESTABLISHED`. Nothing here makes any of them wrong.
2. **Do not read the sign flips as retractions of published cells.** They are on a preregistered
   candidate set chosen to anchor against `E1_I0046`, not on the candidates those screens tested.
   **This screen re-measured a construction, not a result.**
3. **The projection is worth building and it is not free.** +0.020020 pooled at p 0.0005 is real and
   the budget is live, but the denominator set is not. **The rate-limiting input is the same one
   D089 and `E1_I0046` both identified: an availability forecast that sums to a basketball team.**
4. **Any future screen with a minutes response must state its roster sum.** One line. The eleven
   violations exist because the mean looked right and nobody printed the dispersion.
5. **`E1_I0053_minutes` is the dedicated minutes screen and it was running concurrently with this
   one** (`DEFECTS.md` D-02). Two agents independently selected minutes — corroboration of the
   selection rule and a duplication of effort. **Where the two disagree, prefer `E1_I0053`.**
6. **No production change is proposed. No champion was fitted. No repair was enacted.**

---

## DISCIPLINE RECORD

* **12 of 13 anchors reproduced before any new statistic**, two at exactly `0.000e+00` (the points
  and attempts closures over all 1,776 team-games) and D104's home advantage at **+0.965090 on 888
  games, |d| 9.01e-08**; also `E1_I0043`'s decision stratum at **5,673 / 149 / 708** and **3,167**
  in the clean window, and `E0_I0016`/`E1_I0018`'s frame at **14,852** — all exact, from an
  independent frame built from `master_player`.
* **The one anchor that did not reproduce is reported as a non-reproduction and the search for a
  matching construction was stopped rather than continued** (`DEFECTS.md` D-01). It is this screen's
  own D101 violation: the preregistration named an anchor without its row set.
* **A13, which the preregistration called "the load-bearing one", did not reproduce quantitatively
  and is demoted to a qualitative corroboration**, with the failing bucket published
  (`DEFECTS.md` D-03). The census entry it was meant to support rests on a direct quotation instead.
* **The census enumerates the filesystem with a halting assertion in both directions.** That is how
  two screens created by sibling agents *during this run* were caught rather than silently omitted.
* **No-op placebo: deviation exactly `0.000e+00` on all 36 cells**, with the transform asserted to
  be the identity so the check is not vacuous.
* **Response placebo**: `A4`/`PROJ_BUDGET` observed −0.018404 against a placebo range
  [−0.008512, +0.003315] over 200 within-team-game response permutations.
* **Both nulls on every between-player verdict** (`N_TGSWAP` 1,776 blocks, `N_PSWAP` 48
  team-seasons), family-wise max-z from **one shared draw stream** so cross-candidate correlation is
  preserved (D120), and the correct `N_TGBLOCK` for the team-game-constant candidate.
* **The benchmark constant `0.002057` is used nowhere.** `E1_I0049` established it is an in-sample
  transported ceiling; every floor here is a bootstrap or analytic floor computed on this screen's
  own row set and labelled.
* **Ten defects self-reported**, including the one that most weakens the headline (D-09: only one of
  three flips clears its own bootstrap floor) and one factual drift in the commissioning brief that
  this screen nearly inherited (D-08: the "970 of 970" identity is **minutes**, not possessions —
  measured here, the two sides' box possessions differ by mean 2.2771 and are exactly equal in
  0.45 % of games).
* **No blanket process kill of any kind was issued.** Two background PIDs were launched and recorded
  in `scripts/_s03_pid.txt` and `scripts/_s05_pid.txt`; both exited on their own.
* **2021 was never evaluated. 2025 and 2026 were never read, joined, merged or described.**
* **The shared screen kit was not imported and not modified.**
