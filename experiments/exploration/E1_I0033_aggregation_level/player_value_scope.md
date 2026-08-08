# Player-value query: what would be needed, what exists, and how accurate the cheapest
# estimator actually is

**E1_I0033_aggregation_level, Step 4.** Scoping, not building. No new player-value model was
constructed. One measurement was made because nothing on record answered it: the honest accuracy
of the estimator the current architecture already gives away for free.

---

## 1. The query, stated precisely

> *"What happens to this team if this player is out?"*

A team-level model cannot answer this, and that is not a defect in the team model — the query
names an entity the team model does not have. This is the strongest form of the user's argument
and it stands.

But the query hides an ambiguity that turns out to decide everything:

| Reading | What is asked | Who can answer |
|---|---|---|
| **R-A** | how many fewer points does the **team** score? | measured below — the answer is *approximately none* |
| **R-B** | how do the **remaining players'** individual lines change? | needs a player model; not measured here |
| **R-C** | how does the **distribution** of the team total change (variance, tails)? | needs a player model; not measured here |

Almost everything the programme has built points at R-A. Almost all the value is in R-B and R-C.

---

## 2. The cheapest available estimator, and its measured accuracy

The bottom-up architecture answers R-A for free: remove the player from the sum, and the team
forecast falls by that player's forecast points. That estimator requires no new modelling and no
new data. It is also **wrong by roughly a factor of thirty-five**.

**Construction.** Regular season 2022–2024, 1,392 team-games. Within each team-game the pre-game
candidate roster is ranked by *expected minutes* (`p_active_hat × min_hat`, both stored champion
forecasts, both strictly pre-cutoff). The top three are the "starters". Absence is then read from
the realised box score.

**Conditioning, declared (D091 ruling 3 pattern).** The absence indicator is **realised**. That is
legitimate for the question being asked — *given* a starter is out, how much does the team lose —
and it is **not** a live forecasting increment, because a live forecast must predict the absence
first. Nothing below enters a headline forecast comparison.

| | value |
|---|---:|
| pre-game top-3 rows | 4,176 over 1,392 team-games |
| their realised appearance rate | 0.9411 |
| their mean forecast points | 14.341 |
| their mean realised points when present | 14.283 |
| team-games with ≥1 top-3 absent | **183** |
| naive estimate of points lost in those games | **15.815** |
| realised shortfall against the team's prior reference | **0.085** |
| **fitted fraction actually lost, β** | **+0.0284** |
| 95 % interval on β | **[−0.0569, +0.1137]** |
| null mean / null sd | −0.0298 / 0.0435 |
| p | 0.6013 |
| distance of β = 1.0 from the null | **22.3 sd — decisively rejected** |
| distance of β = 0 from the null | 0.65 sd — not rejected |

**The null has power.** Injecting known effects and recovering them through the same code path:

| planted β | recovered | p | detected |
|---:|---:|---:|---|
| 0.00 | +0.028 | 0.607 | no |
| **0.10** | +0.128 | **0.0077** | **yes** |
| 0.25 | +0.278 | 0.0002 | yes |
| 0.50 | +0.528 | 0.0002 | yes |
| 1.00 | +1.028 | 0.0002 | yes |

So this is a powered interval and not a shrug. **β is somewhere between −6 % and +11 %, and it is
certainly not 100 %.**

**Heterogeneity by the size of the absentee** (team-games with exactly one top-3 absent, quartiles
of that player's forecast points):

| quartile | n | absentee's forecast points | realised residual | implied ratio |
|---:|---:|---:|---:|---:|
| 1 | 35 | 8.51 | +3.99 | −0.47 |
| 2 | 35 | 11.49 | +3.04 | −0.26 |
| 3 | 34 | 15.30 | −0.62 | +0.04 |
| 4 | 35 | 19.84 | −1.61 | **+0.081** |

There is a monotone gradient — bigger absentees do cost more — but even in the top quartile the
team retains **92 %** of the missing production. The negative ratios in the bottom quartiles are
not evidence that losing a rotation player helps; with n = 35 per cell they are consistent with
noise and with selection (a team whose *third*-ranked player is out is otherwise healthy).

**And knowing the absence in advance buys the team model nothing.** Handed the realised absence as
an oracle, an absence-aware team forecast improves MAE by **−0.00004** against an 80 %-power floor
of **0.00584**. That is the *ceiling* on what a perfect availability forecast could contribute to a
team points forecast, and it is zero.

### What this establishes

**Substitution is essentially complete for team totals.** Minutes are a fixed shared budget (D104:
identical for both teams in 970 of 970 games) and possessions are a shared game property. When a
starter sits, someone else plays those minutes and takes those shots. The team scores the same
number of points; **different people score them**.

So the honest answer to R-A is: *nothing measurable happens to the team total*. Any player-value
model justified by R-A is being justified by an effect that does not exist at the resolution this
data supports.

---

## 3. What already exists

| Artifact | Path | State |
|---|---|---|
| Walk-forward RAPM | `experiments/rapm_walkforward` | exists, 4 files, `season` granularity |
| Multi-season RAPM | `experiments/rapm_multiseason` | exists, 15 files |
| RAPM v0 | `experiments/rapm_v0` | exists, 4 files |
| **RAPM evaluated as a prior** | `experiments/exploration/E1_I0031_rapm_as_prior` | 53 files — **D107** |
| Champion availability forecast `p_active` | `experiments/cbs_v15_player_oof_v5` | in production use |
| Availability screen | `experiments/exploration/E0_I0019_availability_forecast` | 65 files — D090 |
| Two-stage minutes | `experiments/minutes_twostage` | 14 files |
| Derived lineups | `data/lineups` | 5 files |

### What D107 already settled, and its boundary

* **As a feature, no.** Not significant on the decision stratum (p 0.07–0.19); worse than a tuned
  simple estimator on 7 of 8 target-by-stratum cells; and its largest single component is
  `has_rapm_f`, the *indicator that a RAPM value exists at all* — a veteran-versus-rookie flag.
* **As a reference component, yes but small, and mostly not the adjustment.** A raw prior-season
  box score achieves +0.63 / +0.85 / +1.06 / +0.45 % against RAPM's +1.04 / +0.96 / +1.33 / +0.38.
  **The opponent-and-teammate adjustment buys almost nothing over an unadjusted box score.** The
  prior-season *information* is what works.
* **Veterans returning: it genuinely wins.** +2.28 % on points over D092's placeholder (p 0.0015),
  +1.03 % on minutes; RAPM's own contribution is ~+1.2 pp on points, clear of its null. That
  population is 572 of 698 cold-start rows.
* **True rookies: it actively hurts.** −54 % on points, −51 % on minutes. The imputed near-league
  value destroys the draft-slot signal D092 relies on. **Never apply it there.**
* **Provenance caveats that travel with it.** `train_seasons` is cumulative rather than
  prior-season-only; `check_manifest` returns UNVERIFIABLE for `season` granularity, so the pass
  came from a value-level check, not the manifest; and `lambda_chosen` varies 50× across seasons,
  giving a 25× spread in the scale of `net_100`.

**So a player-value model already partly exists, and its scope is known: veterans returning after
a gap, as a reference component, worth about +2 % on points.**

---

## 4. What would be needed to answer the query properly — and it is R-B, not R-A

Since R-A is measurably empty, a player-value model can only earn its keep on **redistribution**.
That changes the requirements completely.

| Requirement | Status | Gap |
|---|---|---|
| Who is available, pre-game | `p_active` exists | **Miscalibrated in aggregate**: sums to 10.34 players where 9.40 play; tier-B fallback rows carry a declared-constant 0.80 against a 0.10 realised rate. This is a roster-arithmetic bug that only summing exposes, and it is worth +8.14 points of level bias. **Cheapest, highest-value fix identified by this screen.** |
| How minutes redistribute when someone sits | `minutes_twostage`, `e_minutes_given_active` | Never evaluated *conditionally on a teammate's absence*. The champion forecasts each player's minutes independently; nothing enforces the 200-minute team budget. |
| How usage redistributes | `attempts_usage` exists; E0_I0006 screened redistribution | Same issue: no team-level attempt constraint. This screen shows shot attempts is the quantity where bottom-up is **worst** (49.6 % penalty, corr ratio 0.45) — precisely the fingerprint of a missing shared-budget constraint. |
| Player quality independent of context | walk-forward RAPM | Exists; D107 bounds it. Adjustment adds ~nothing over a raw prior-season box score. |
| Lineup-level interaction | `data/lineups` (5 files) | Not screened. Sample depth is the binding constraint — D103's floor says effects below ~3 × 10⁻⁴ are unreachable from 2021–2024 under any design. |

### The one structural change this screen would recommend

**Impose the team budget on the player forecasts, rather than hoping they sum correctly.** Every
finding here points the same way:

* minutes are a fixed shared budget (200 + 25 per overtime, identical for both teams, D104);
* possessions are a shared game property (D104);
* player errors within a team-game **cancel** (0.674× the independence prediction) because the
  total is constrained;
* the quantities where bottom-up loses most (shot attempts, points) are exactly the shared-budget
  ones, and where it loses least (free throws, assists) are the individual-act ones;
* substitution absorbs 97 % of an absent starter's production.

A reconciliation that takes the **total from the team level** and the **allocation from the player
level** is the construction the evidence supports. Note that this screen's `C2_PRORATE` arm makes
the point mechanically: proportionally reconciling player forecasts to the direct team forecast
reproduces the direct team forecast *exactly* at the team total. **Reconciliation does no work on
the total. All of its work is at the player level, and that is where it should be evaluated.**

---

## 5. What is NOT established here

* Nothing about **player props accuracy** under absence. This screen measured team totals only.
* Nothing about **variance or tail behaviour** — R-C is untouched.
* The absence measurement uses a **realised** indicator and a **pre-game** starter ranking. A
  different starter definition (declared lineups, injury reports) could move it; no such artifact
  was used, and `player_game_availability.csv` and `roster_asof.csv` were **not opened** — D076
  records that both fail the manifest check for exactly this kind of screen.
* β is measured on **183 team-games**. The interval [−0.057, +0.114] is powered against 0.10 but
  cannot separate 0.03 from 0.08. Anyone wanting the *size* of the substitution effect rather than
  its *absence* needs more data than 2021–2024 contains.
* This is a **regular-season** result. The 130-team-game playoff stratum was excluded before any
  statistic, for D104's structural reason.
