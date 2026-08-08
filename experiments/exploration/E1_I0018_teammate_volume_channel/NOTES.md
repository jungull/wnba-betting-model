# E1_I0018 — THE TEAMMATE VOLUME CHANNEL

**E1 exploration. LEAD, NEVER A RESULT.** No bootstrap, no promotion threshold, no registry
entry, no ledger entry, no graph event. Nothing in this directory may be cited as evidence, and
nothing outside this directory was written or modified.

**Candidate list SHA-256 `189C4B971912CCFC89B9546B25E485073573E965C4747116A79FC7D1F20CBF9F`**,
frozen `2026-08-08T06:55:22-04:00`, **before any statistic was computed**. 16 preselected, 2
declared additions made at implementation time before any statistic (reason in §8), 18 screened,
**0 added after seeing results, 0 dropped**. The hash was recomputed in `s07_findings.py` after
every result existed and is byte-identical.

---

# 0. VERDICT: **SPLIT**

| variant | what it needs | survives? |
|---|---|---|
| **tip-time `T01`** | today's box membership — a **post-game** observation | **YES**, everywhere: ppm and shots-per-minute, pooled and decision stratum, single and complete reference, and it propagates to points with a **walk-forward** coefficient at paired dR2 **+0.0078** (cluster p 0.0005) |
| **strictly-prior-only `P01`** | the team's **previous game's** box membership — **no same-day information at all** | **PARTIALLY.** Clears family-wise on **shots-per-minute** under the complete reference on both strata (fw p 0.0116, 0.0116) and reaches points walk-forward at **+0.00235** (cluster p 0.0345, decision stratum). **FAILS** family-wise on points-per-minute under the complete reference (fw p 0.0815 decision, 0.3727 pooled) |

**The prior-only variant retains a median 39.9% of the tip-time effect across every measure this
screen produced** (`tiptime_loss_ladder.csv`). That is the SPLIT, and it is why this is neither
KILL nor KEEP.

**The single most important number:** the arithmetic ceiling on the decision stratum under the
complete reference is **dR2 ≤ 0.003689 (tip-time)** and **≤ 0.002057 (strictly prior only)**.
D079's shot-mix ceiling was 0.001127 and D084's conversion ceiling was 0.000129. **This is the
first channel this program has screened whose ceiling is materially LARGER than the one that
already killed shot mix** — 3.3× D079's, 28.6× D084's. It must be stated with the tip-time
constraint attached every time, and it is stated against a **matched point-in-time reference, not
against the champion**.

---

# 1. STEP 1 — REPRODUCTION. **0.000e+00.**

`C04_teammate_usg_present` was **rebuilt from `master_player.parquet`**, not copied, and then
compared to D085's frozen column.

| level | result |
|---|---|
| the column itself, `max abs diff` vs the frozen `C04` | **0.000000e+00**, 0 NaN-pattern mismatches |
| `C08_vacated_usg` (rebuilt as `T03_absent_usg`) | **0.000000e+00** |
| `y_ppm`, `y_ts`, `y_efg`, `refB_ppm`, `refB_efg`, `n_prior` | **0.000000e+00** (`refB_ts` 2.220e-16) |
| row sets | **identical**, 14,852 rows both frames |

| published cell (D085) | published | reproduced | abs delta |
|---|---|---|---|
| ppm pooled dR2, n=14,852 | 0.0032997045402004 | 0.0032997045402004 | **0.000e+00** |
| ts pooled dR2, n=14,079 | 0.0004907097327293 | 0.0004907097327293 | **3.253e-19** |
| efg pooled dR2, n=13,989 | 0.0001182487824825 | 0.0001182487824825 | **0.000e+00** |
| ppm decision stratum dR2, n=5,673 | 0.0049627746 | 0.0049627746 | 3.601e-11 |
| ppm + reliability controls, n=11,933 | 0.0016436943 | 0.0016436943 | 2.632e-12 |
| ppm alternate entity (player-season) | 0.0032997045 | 0.0032997045 | 4.020e-11 |
| per-season dR2, all four seasons | see `_s02.json` | — | ≤ 3.34e-11 |
| `p_N1`, `p_N2`, `p_row` on all six cells | — | — | ≤ 3.51e-11 |
| `var_share_between`, `corr_with_ref_residual` | — | — | **0.000e+00** |

**The three cells transcribed from D085's full-precision `screen_results.csv` reproduced at
0.000e+00 / 3.253e-19. The residual ~1e-11 deltas are entirely the 10-decimal rounding in
`survivor_forensics.json`, which is the only place the decision-stratum, reliability-control and
alternate-entity numbers are published.** Seed 20260807 (D085's) was used for the reproduction
cells specifically so the permutation p-values are bit-comparable; every new cell uses this
screen's own seed 20260808.

**A free check on the kit fell out of this.** D085's N2 (entity-label swap) was implemented in its
own `ep_base.py` because the kit had no valid scheme for it — the declared **K2 gap**. That code
was ported into `screenkit` at D086. This screen called **the kit version** and reproduced D085's
`p_N2` **exactly in every cell**. The port is confirmed correct on real data.

---

# 2. STEP 2 — THE CHANNEL, MEASURED RATHER THAN INFERRED

With `TSA = fga + 0.44·fta` as "shots", `y_ppm = y_spm · y_pps` **exactly** (max abs err
1.776e-15). And `y_pps ≡ 2·y_ts`, `refB_pps ≡ 2·refB_ts`, both at **0.000e+00** — so the
conversion arm of this decomposition **is** D085's true-shooting outcome rescaled, and because R²
is invariant to a positive rescaling of the response the `pps` cell **must** return D085's `ts`
dR2 to machine precision. It does, in all six (stratum × base) combinations. That is a free
correctness check on the machinery, and it is why I did not need to take D085's `ts` result on
trust.

## 2.1 Base `[1, refB_<outcome>]` — D085's base, like for like

| outcome | POOLED dR2 | fw p | DECISION dR2 | fw p |
|---|---|---|---|---|
| `y_ppm` | 0.003300 | **0.0017** | 0.004963 | **0.0017** |
| **`y_spm` — the volume arm** | **0.003066** | **0.0017** | **0.007987** | **0.0017** |
| `y_pps` — the conversion arm | 0.000491 | 0.5907 | 0.000062 | 1.0000 |
| `y_ts` (= pps/2) | 0.000491 | 0.5907 | 0.000062 | 1.0000 |
| `y_efg` | 0.000118 | 1.0000 | 0.000068 | 1.0000 |
| `y_fgapm` (FGA-only volume arm) | 0.004254 | **0.0017** | 0.007341 | **0.0017** |
| `y_ppfga` (FGA-only conversion arm) | 0.000479 | 0.5874 | 0.000090 | 1.0000 |

**D085's indirect inference was right, and the direct measurement makes it sharper: on the
decision stratum the volume arm carries a LARGER increment (0.007987) than points-per-minute
itself (0.004963), while the conversion arm is dead (0.000062, fw p 1.0).** The FGA-only
decomposition agrees, so the result is not an artifact of the 0.44 free-throw weight.

## 2.2 STEP 2b — the D087 reference-incompleteness check

**The prediction was registered in advance** (`CANDIDATES_PRESELECTED.md` §5, inside the hash),
from reading D085's construction:

```
T01[p,g] = Σ_{q ∈ PRESENT(g), q≠p} prior_usg_pg[q]
         = T02[g] − O01[p]              (asserted on data at 1.421e-14)
```

`T02[g]` is **constant within a team-game**, so **all** of `T01`'s within-team-game variation is
exactly **minus the player's own strictly-prior usage per game** — a strictly-prior player-level
quantity **absent from D085's base**. That is precisely D087's shape. The prediction was that
completing the reference would collapse the increment.

| base | ppm POOLED | ppm DECISION | spm POOLED | spm DECISION |
|---|---|---|---|---|
| `B_SINGLE` `[1, refB_oc]` | 0.003300 (0.0017) | 0.004963 (0.0017) | 0.003066 (0.0017) | 0.007987 (0.0017) |
| `B_COMPLETE` `[1, refB_ppm, refB_spm, refB_pps, refB_mpg]` | 0.001274 (0.0050) | 0.004240 (0.0017) | 0.002213 (0.0017) | 0.007567 (0.0017) |
| `B_COMPLETE_PLUS_USAGE` (+ `refB_own_usg_pg`) | 0.001117 (0.0100) | 0.004235 (0.0017) | 0.001911 (0.0017) | 0.007563 (0.0017) |

**THE PREDICTION WAS HALF RIGHT, AND THAT IS REPORTED AS SUCH RATHER THAN QUIETLY DROPPED.**

* **On the pooled frame the trap is real and large.** Completing the reference cuts `T01`'s ppm
  increment **2.95×** (0.003300 → 0.001117). And `O01_own_usg_pg` on its own is the **single
  largest ppm increment in this entire screen — dR2 0.011116** against `[1, refB_ppm]` — which
  itself collapses **8.2×** to 0.001360 once the reference is completed. **D085's base was
  genuinely incomplete**, and a screen of this family that used only `[1, refB_ppm]` would be
  reading own-volume as teammate context.
* **On the decision stratum it costs almost nothing** (0.004963 → 0.004235, **1.17×**; spm 1.06×),
  and the surviving signal is carried by `T02`, the **team-game** component (0.004216 on ppm,
  0.007575 on spm under `B_COMPLETE`, both fw p 0.0017) — which is **not** an own-prior quantity
  and therefore **cannot** be a reference-incompleteness artifact. Correspondingly, `O01`'s own
  decision-stratum increment goes to **0.000078, fw p 1.0** under the complete reference.

**So the trap explains most of the pooled effect and essentially none of the decision-stratum
effect.** The decision stratum is where the volume channel actually lives, and it survives the
completion. It survives on shots-per-minute most strongly of all.

---

# 3. STEP 3 — THE TIP-TIME QUESTION

## 3.1 (a) Exactly what the feature needs, and when it is knowable

The **only** non-prior input to `T01` is `PRESENT(g)` = **the set of players with `minutes > 0` in
today's box for that team**. Everything else — each teammate's usage weight — is a strictly-prior
expanding mean.

**`minutes > 0` is strictly stronger than "was on the active list".** A dressed, healthy
coach's-decision DNP; a blowout benching; a warm-up injury; an ejection — every one of these
removes a player from `PRESENT(g)`. **A perfect pre-game injury report therefore reconstructs at
best a SUPERSET of `PRESENT(g)`, never `PRESENT(g)` itself.** `PRESENT(g)` is a **post-game
observation** and is never knowable pre-game at all.

The closest pre-game proxies are the official inactive list and the announced starting lineups,
roughly **30–60 minutes before tip**. **Early lines are posted the previous day or the morning
of** — hours earlier. So even the degraded proxy arrives after the moment the brief cares about.

**What this screen cannot establish, stated as a limit rather than worked around:** the split
between "absent because unavailable" and "active but logged zero minutes" cannot be made here,
because `data/w1_truth/roster_asof.csv` is exactly the file that would make it and it is
**FORBIDDEN** (artifact-granular, `fit_through_season: 2026`; filtering does not help). It was
**never opened**. Availability was rebuilt from box membership, the D076 method, as D085 also did.
**This is precisely the file an availability screen reaches for first, and it stays shut.**

Measured churn (`s06`, `_s06.json`):

| quantity | value |
|---|---|
| sd of `T01` (tip-time) | 11.1768 |
| sd of `P01` (previous game's roster) | 10.3756 |
| sd of the same-day news `T01 − P01` | 8.2062 |
| mean \|news\| | 5.1514 usage units |
| **R² of the previous game's roster predicting today's** | **0.5075** |
| **share of `T01`'s variance that is same-day news** | **0.4925** |
| share of rows where the two rosters are **identical** | 0.2882 |

**A DESCRIPTIVE DIAGNOSTIC THAT READS THE NEXT GAME** (produces no feature, enters no base, enters
no dR2, labelled in the time-window table): of 1,241 newly-absent teammate-game transitions,
**55.8% persist into the team's next game** and 44.2% last exactly one game. Persistence is
**necessary but not sufficient** for pre-game knowability, so 55.8% is an **upper bound** on what
a perfect pre-game injury report could recover from the news component — not an estimate of what
one would recover.

## 3.2 (b) The strictly-prior-only variants

Six were preselected. All read **no same-day information at all**.

| candidate | ppm POOLED | ppm DECISION | spm POOLED | spm DECISION |
|---|---|---|---|---|
| | B_SINGLE / **B_COMPLETE** | B_SINGLE / **B_COMPLETE** | B_SINGLE / **B_COMPLETE** | B_SINGLE / **B_COMPLETE** |
| **`P01_c04_prevgame`** | 0.002200 (0.0017) / **0.000484 (0.3727)** | 0.002911 (0.0017) / **0.002342 (0.0815)** | 0.001458 (0.0017) / **0.000776 (0.0116) ✓** | 0.003345 (0.0083) / **0.003037 (0.0116) ✓** |
| `P02_c04_availweighted` | 0.006193 (0.0017) / 0.000482 (0.3611) | 0.005120 (0.0017) / 0.002601 (0.1980) | 0.002019 (0.0017) / 0.000414 (0.4326) | 0.001541 (0.0133) / 0.000695 (0.4742) |
| `P03_c04_avail5` | 0.002636 (0.0017) / 0.000232 (0.9667) | 0.002416 (0.0599) / 0.001607 (0.7354) | 0.001538 (0.0017) / 0.000577 (0.1398) | 0.002506 (0.1730) / 0.002126 (0.1930) |
| `P04_absent_usg_prevgame` | 0.000000 (1.0) / 0.000005 (1.0) | 0.000045 (1.0) / 0.000024 (1.0) | 0.000023 (1.0) / 0.000060 (1.0) | 0.000327 (0.9967) / 0.000890 (0.4759) |
| `P05_n_present_prevgame` | 0.000018 (1.0) / 0.000004 (1.0) | 0.000024 (1.0) / 0.000023 (1.0) | 0.000005 (1.0) / 0.000000 (1.0) | 0.000210 (0.9983) / 0.000226 (0.9967) |
| `P06_c04_rotstab` | 0.001749 (0.0017) / 0.000119 (1.0) | 0.001736 (0.0233) / 0.001230 (0.5075) | 0.001057 (0.0033) / 0.000400 (0.3028) | 0.002003 (0.4143) / 0.001941 (0.4193) |

(family-wise p in parentheses; ✓ marks a cell that clears family-wise under the **complete**
reference.)

**Only `P01` — the simplest possible construction, "who played in the team's last game" —
survives a complete reference, and only on shots-per-minute.** `P02` and `P03`, the
availability-rate-weighted variants that looked strongest under D085's single reference, are
reference-incompleteness casualties; `P02` **also fails walk-forward** (cluster p 0.16 pooled,
0.16 decision). `P04` and `P05` are dead everywhere, which is itself informative: **the signal is
not "how many bodies are available" or "how much usage is out", it is "which specific usage mass
is on the floor with me".**

## 3.3 (c) How much is lost between the two — the loss ladder

Full table in `tiptime_loss_ladder.csv`. Under the **complete** reference:

| measure | stratum | tip-time | prior-only | prior-only retains |
|---|---|---|---|---|
| dR2 on `y_ppm` | POOLED | 0.001274 | 0.000484 | 38.0% |
| dR2 on `y_ppm` | DECISION | 0.004240 | 0.002342 | 55.2% |
| dR2 on `y_spm` | POOLED | 0.002213 | 0.000776 | 35.1% |
| dR2 on `y_spm` | DECISION | 0.007567 | 0.003037 | 40.1% |
| paired dR2 on POINTS, in-sample coefficient | DECISION | 0.010522 | 0.003314 | 31.5% |
| **paired dR2 on POINTS, WALK-FORWARD coefficient** | **DECISION** | **0.007817** | **0.002349** | **30.1%** |
| paired dR2 on POINTS, walk-forward | POOLED | 0.003012 | 0.000631 | 21.0% |
| arithmetic ceiling (D084 form) | DECISION | 0.003484 | 0.001928 | 55.3% |

**Median across the whole 20-row ladder: the strictly-prior-only variant retains 39.9%, so about
60% of the effect is same-day information.**

**Direct confirmation that the tip-time advantage is real and not just "P01 is a noisier P01":**
the **pure same-day news increment** `N02_news_vs_avail = T01 − P02` **clears family-wise on its
own**, at dR2 0.006892 (fw p 0.0017) on `y_spm`, decision stratum, complete reference — nearly as
large as `T01` itself. `N01_news_vs_prevgame = T01 − P01` likewise clears at 0.001985 (fw p
0.0017). If the tip-time advantage were an artifact of estimator noise, the pure news component
would carry nothing.

---

# 4. STEP 4 — DOES IT REACH POINTS, AND WHAT IS THE CEILING?

## 4.1 The propagation, and why the headline is walk-forward

`points_forecast = ppm_forecast × m_hat`. `m_hat` is **strictly prior** (trailing-5 prior mean
minutes, `.shift(1)` before `.rolling(5)`, cold fallback the expanding prior mean) and is
**identical in the reference and the candidate forecast**, so the contrast isolates the per-minute
step exactly as D081 framed it. Realised minutes are used only in a loudly-labelled
**ORACLE-MINUTES DIAGNOSTIC**, excluded from every headline.

`s04` fits the screening coefficient **in sample**. That coefficient reads the whole partition, and
**constraint 3 of this screen's brief requires the time-window audit to cover inference steps, not
only features** — so `s05` refits it **strictly forward**: for season *s*, fitted on seasons `< s`
and applied to season *s*. 2021 is unscored. **That walk-forward number is the headline.**

| stratum | base | candidate | R² ref → cand | **walk-forward paired dR2** | cluster p | points MAE |
|---|---|---|---|---|---|---|
| DECISION | B_COMPLETE | **`T01` tip-time** | 0.299844 → 0.307661 | **+0.007817** | **0.0005** | 5.0212 → 4.9942 (0.54%) |
| DECISION | B_COMPLETE | **`P01` prior-only** | 0.299844 → 0.302193 | **+0.002349** | **0.0345** | 5.0212 → 5.0150 (0.12%) |
| DECISION | B_COMPLETE | `P02` prior-only | 0.299844 → 0.303360 | +0.003516 | 0.1644 | — |
| DECISION | B_COMPLETE | `G01_noise` | 0.299844 → 0.300110 | +0.000266 | 0.4633 | — |
| POOLED | B_COMPLETE | `T01` tip-time | 0.505156 → 0.508168 | +0.003012 | 0.0005 | 4.0321 → 4.0210 (0.28%) |
| POOLED | B_COMPLETE | `P01` prior-only | 0.505156 → 0.505787 | +0.000631 | 0.0065 | 4.0321 → 4.0305 (0.04%) |
| POOLED | B_COMPLETE | `G01_noise` | 0.505156 → 0.505190 | +0.000034 | 0.7921 | — |

The null is `screenkit.paired_forecast_comparison` with a **whole-cluster sign-flip** at
team-season (48 clusters); the row-wise version is reported beside it for contrast only.

**D076's rule, obeyed and shown:** the largest points-MAE reduction anywhere in this screen is
**0.79%**, and the MAE column sits next to the skill column throughout precisely so the two can
never be confused. D076's own counterexample cut points MAE 9.9% while moving skill by +0.00007.

## 4.2 The arithmetic ceiling

D084's form: 1 sd of the centred signal moves the points forecast by *X* points against a *Y*-point
response sd, so **dR2 ≤ Var(shift)/Var(response)**.

| | points move per 1 sd | response sd | **ceiling dR2, D084's exact form** `(move/sd)²` | ceiling from the **actual** per-row forecast shift |
|---|---|---|---|---|
| **tip-time, DECISION, complete reference** | **0.4553** | **7.4956** | **0.003689** | 0.003484 |
| **prior-only, DECISION, complete reference** | **0.3400** | 7.4956 | **0.002057** | 0.001928 |
| tip-time, POOLED, complete reference | 0.2335 | 7.4829 | 0.000974 | 0.000907 |
| prior-only, POOLED, complete reference | 0.1477 | 7.4829 | 0.000390 | 0.000356 |
| — D079 shot-mix channel | — | 5.82 (FG-points) | 0.001127 | — |
| — D084 conversion channel | 0.0859 | 7.5505 | 0.000129 | — |

The two ceiling columns differ only in what is called "the move": D084's exact form uses
`|β| · sd(signal) · mean(m_hat)`, while the second uses the sd of the shift that actually enters
the points forecast, `β · (signal residualised on the base) · m_hat`. **They agree to within 6%
everywhere.** The first column is the one to quote, because it is computed the same way in D079,
D084 and D087; the second is in `ceiling_reconciliation.csv` and is the one the identity in §4.3
is built on.

**This one is materially larger, and the comparison is close to apples-to-apples because the
response sd is almost identical to D084's (7.4956 vs 7.5505): the signal moves the points forecast
5.3× further per sd than D084's conversion channel did.** The tip-time ceiling is **3.3× D079's
mix ceiling and 28.6× D084's conversion ceiling**. **The strictly-prior-only ceiling is still 1.8×
D079's and 15.9× D084's.**

**Cross-check through the volume route** (`arithmetic_ceiling.csv`): 1 sd of `T01` × `beta_spm`
(−0.001266) = 0.012968 shots/min × 30.22 min = 0.3919 shots × 1.0798 points/shot = **0.4231
points**, dR2 ≤ 0.003210 — i.e. **93% of the points move travels through shots, not through
conversion**, independently confirming §2.

**Why D087's volume-offset argument does not apply here, and why that was the point of running
this.** D087 killed the shot-mix efficiency route because closer shots convert better **and yield
fewer attempts**, so the two arms cancel. This signal has **no conversion arm to cancel against**:
its `pps` increment is 0.000062 with family-wise p 1.0. It is a pure volume signal, so there is
nothing to offset it.

## 4.3 The ceiling "paradox", reconciled — because a reader will hit it

In several cells the **realised** paired dR2 on points **exceeds** the D084-form ceiling
(e.g. decision, single reference, tip-time: realised +0.011521 vs ceiling 0.004070). That is not
an arithmetic error and it is not left unexplained.

The coefficient is fitted on **points-per-minute** and then multiplied by minutes to reach
**points**. Points errors scale with minutes, so the shift is **under-scaled for points** — the
implied optimal rescaling is 1.30× to 3.00×. The identity

```
realised = (2·c_opt − 1) · var_share        and        ORACLE = c_opt² · var_share
```

holds across all 16 cells at **8.674e-19** (`ceiling_reconciliation.csv`). The best-rescaling
**ORACLE** ceiling is reported alongside and is a **DIAGNOSTIC ONLY — it uses the realised
response** — exactly the treatment D084 gave its own oracle. Its largest value is 0.014930
(decision, single reference, tip-time).

**The D084-form ceiling is the number to quote**, because it is the one computed the same way in
D079, D084 and D087, and it is the conservative one.

## 4.4 The denominator caveat, stated plainly

**Every increment here is measured against a matched strictly-prior point-in-time reference facing
the same rows — not against the champion.** That reference's points R² is 0.30 on the decision
stratum and 0.51 pooled. A champion that already contains some teammate context would leave less
room. This screen is not authorised to load or retrain the champion and did not.

---

# 5. STEP 5 — MECHANISM, WITH THE SIGN PREDICTED IN ADVANCE

`CANDIDATES_PRESELECTED.md` §6, inside the hash, before any statistic:

> usage redistribution → **NEGATIVE** on ppm and spm  |  shot creation → **POSITIVE**

**Result: USAGE REDISTRIBUTION. `T01`'s coefficient is NEGATIVE on both `y_ppm` and `y_spm` in
every stratum and under every base — 16 of 16 cells — and the complementary quantity
`T03_absent_usg` is POSITIVE on `y_spm` in every stratum.** The shot-creation story predicted the
opposite sign and is refuted. More teammate usage on the floor ⇒ **fewer** shots for this player;
more usage absent ⇒ **more**.

Practical magnitude, decision stratum, p10 → p90 of `T01`, measured on the reference residual:

* **−0.0504 shots per minute = −1.52 true-shot attempts per game** at 30.2 minutes
* **−0.0622 points per minute = −1.88 points per game**

## 5.1 Symmetry — directionally asymmetric, not significantly so

`dev = T01 − (strictly-prior running norm)`; the return arm is `max(dev,0)` and the absence arm is
`min(dev,0)`. A purely mechanical redistribution is symmetric, so the **kink** term should add
nothing over the linear deviation.

| stratum | outcome | norm | β(returns) | β(absences) | ratio | kink dR2 | p_N1 | p_N2 |
|---|---|---|---|---|---|---|---|---|
| POOLED | ppm | team | −0.001416 | −0.002074 | 0.683 | 6.0e-05 | 0.434 | 0.288 |
| POOLED | ppm | player | −0.000638 | −0.000995 | 0.641 | 1.7e-05 | 0.612 | 0.581 |
| POOLED | spm | team | −0.000642 | −0.001589 | 0.404 | 2.4e-04 | 0.043 | 0.007 |
| POOLED | spm | player | −0.000664 | −0.000908 | 0.732 | 1.5e-05 | 0.579 | 0.541 |
| DECISION | ppm | team | −0.001414 | −0.001632 | 0.866 | 8.0e-06 | 0.879 | 0.769 |
| DECISION | ppm | player | −0.000754 | −0.001341 | 0.562 | 6.6e-05 | 0.619 | 0.406 |
| DECISION | spm | team | −0.000853 | −0.001411 | 0.605 | 1.2e-04 | 0.406 | 0.305 |
| DECISION | spm | player | −0.000764 | −0.001377 | 0.555 | 1.6e-04 | 0.193 | 0.216 |

**The absence arm's slope is larger in 8 of 8 cells (ratio 0.40–0.87, median 0.62) — a player gains
more when a teammate goes out than they give back when the teammate returns. But the kink term
fails BOTH correct-level nulls in 7 of 8 cells,** and the one exception (spm, pooled, team norm,
p_N2 0.0067, dR2 2.39e-04) would not clear the family-wise threshold. **The honest statement: the
data are consistent with a symmetric mechanical redistribution and this screen cannot distinguish
that from a modest asymmetry.** The directional consistency across 8 of 8 cells is reported
because suppressing it would be selecting evidence, not because it is significant.

---

# 6. TIME-WINDOW TABLE — **FEATURES AND INFERENCE STEPS**

D085's own agent introduced a retrospective baseline through its **inference machinery**, not its
features (an entity-season-mean decomposition built to satisfy a permutation scheme, whose mean at
game 5 contained games 6…40, clearing 47 of 264 cells). **Six instances now, one through the
statistics.** This table therefore covers every transformation introduced for statistical
convenience.

## 6.1 Features

| column | window read | mechanism | reads today? | reads future? |
|---|---|---|---|---|
| `prior_usg_pg[q]` (the weight inside every C-family column) | that teammate's games with **this team**, **strictly before** this game_date, same season | running `[cum used, cum appearances]` advanced only **after** every row of the current game is written | **no** | no |
| `T01_c04_tiptime` | the weights above × **TODAY's box membership** | `Σ_{q∈PRESENT(g), q≠p}` | **YES — post-game observation** | no |
| `T02_teamgame_present_usg` | as `T01`, including self | constant within a team-game | **YES** | no |
| `T03_absent_usg` | weights × roster members **not** in today's box | | **YES** | no |
| `T04_n_present` | today's box size | | **YES** | no |
| `O01_own_usg_pg` | the player's own prior usage per game with this team | the same running state | **no** | no |
| `P01_c04_prevgame` | weights × the team's **PREVIOUS** game's box | `prev_present`, set after the previous game | **no** | no |
| `P02_c04_availweighted` | weights × appearances / team games, all strictly prior | | **no** | no |
| `P03_c04_avail5` | weights × appearance rate over the team's **last 5 prior** games | `deque(maxlen=5)` of prior box sets | **no** | no |
| `P04_absent_usg_prevgame`, `P05_n_present_prevgame` | previous game only | | **no** | no |
| `P06_c04_rotstab` | `P03` × appearance rate over the **last 3 prior** games | | **no** | no |
| `N01`, `N02` | `T01 − P01`, `T01 − P02` | a difference of the above | **YES** (via `T01`) | no |
| `M01`/`M02` | `T01` − team's `.shift(1).expanding().mean()` of `T01`, clipped | norm strictly prior; `T01` is not | **YES** (via `T01`) | no |
| `M03`/`M04` | same with the **player's** prior expanding mean | | **YES** (via `T01`) | no |
| `G01_noise` | nothing | `default_rng(20260808).standard_normal` | no | no |
| `refB_*` (ppm, spm, pps, ts, efg, fgapm, ppfga, mpg, own_usg_pg) | ratio of the player's **strictly prior** sums inside `(season, player_id)` | `.shift(1)` **before** `.expanding()`; cold fallback = same-season **strictly earlier** league expanding mean | no | no |
| `refA_*` | mean of the player's prior per-game **ratios** | `.shift(1)` before `.expanding()` | no | no |
| `prior5_minutes`, `m_hat` | player's **5 most recent strictly prior** games | `.shift(1)` **before** `.rolling(5)`; cold fallback `refB_mpg` | no | no |
| `y_*` (all outcomes) | **the realised game** | response only | yes, **as response** | — |

## 6.2 Inference steps — the part D085 got caught by

| step | window read | verdict |
|---|---|---|
| **screening regression coefficient, `s02`–`s04`** | **THE WHOLE PARTITION** — fitted in sample on the same rows it scores | **DECLARED, NOT HIDDEN.** It is an **upper bound**, labelled as such at every use. `s05` repeats the points propagation with a **walk-forward** coefficient (fitted on seasons `< s`, applied to season `s`) and **that is the headline**. |
| N1 permutation, `SCHEME_WITHIN` at `(team_id, season)` | permutes **already-computed values** inside each entity-season, `block_col="season"` | clean — no aggregate is recomputed from a permuted key (the classic no-op form; `noop_placebo` confirms a key-relabel control would be vacuous here at sd 1.735e-18) |
| N2 `entity_swap_null` at `(team_id, season)` | reassigns whole entity-season **series** within a season at proportional positions | clean — same reasoning; and it is now the kit's own function, not a local reimplementation |
| N3 row-level null | contrast only | never carries a verdict anywhere |
| family-wise max-t | standardises each cell's draws by **its own** null mean/sd, then maxes across cells per draw index | clean — the standardisation uses only that cell's own null draws, no cross-cell or cross-time pooling |
| `var_share_between`, `detect_grouping_level` | the analysis frame's own rows | descriptive; no aggregate enters a base |
| **`decompose` into entity-season mean + remainder** | **NOT USED.** | This is the exact transformation that produced D085's superseded pass. It is deliberately absent from this screen; the entity-swap null removes any need for it. |
| **absence-persistence diagnostic, `s06` §2** | **READS THE TEAM'S NEXT GAME** | **DIAGNOSTIC ONLY.** Produces no feature, enters no base, enters no dR2, appears in no headline. It exists solely to characterise knowability, because the file that would answer it directly is forbidden. |
| **ORACLE-MINUTES diagnostic, `s04`** | **reads the realised minutes** | **DIAGNOSTIC ONLY**, excluded from every headline. |
| **ORACLE best-rescaling ceiling, `s05`** | **reads the realised response** | **DIAGNOSTIC ONLY**, excluded from every headline. |
| `_LEAKY_control_ppm` (full-season mean) | **reads the whole season** | built **only** as the leakage probe's positive control, dropped from the frame immediately afterwards, never used anywhere else. |

## 6.3 Partition

`screenkit.assert_partition` was run on `master_player` after the season filter, on the built
frame, on D085's frozen frame, and at the top of every downstream script — **on column VALUES**
(parsed dates and season-valued columns). **No regex or byte scan is used as a partition check
anywhere in this screen.** The guard correctly skipped `season_type` as *"name is season-like but
VALUES are not seasons"*. `max(game_date) < 2025-01-01` is asserted separately. No 2025 or 2026
row was read, joined, plotted or described.

---

# 7. NULLS, MULTIPLICITY AND ATTRITION

`screenkit.detect_grouping_level` returned
`NO_COARSER_LEVEL_EXISTS__ROW_NULL_IS_ANTICONSERVATIVE` with
`recommended_permutation_level = None` — the **K2 signature**. Neither the within nor the
between scheme alone is a valid null there, so **both** were run at `(team_id, season)` and a cell
is credited **only if it beats both** (`p_correct_level = max(p_N1, p_N2)`). The row-level null is
computed by `null_width_comparison` for **contrast only** and carries no verdict anywhere. **No
cluster-robust standard error is reported anywhere as an alternative to a permutation null.**

Row-null inflation on this frame: median `sd_N1/sd_row` = **1.018**, `sd_N2/sd_row` = **1.166**.
Both close to 1, i.e. **the row-level null happens not to be badly too narrow here**. That is
reported, not relied on.

**Family-wise correction is over ALL 154 cells screened in this directory, in ONE family**, max-t
from the correct-level permutation draws standardised per cell, computed separately on N1 and N2
with the **worse** reported. The decomposition and the tip-time analysis were deliberately run in
**one script** so they could not become two families and quietly halve the correction.

| attrition step | count |
|---|---|
| candidates preselected and hashed | **16** |
| declared additions before any statistic (§8) | 2 |
| candidates screened | **18** |
| candidates added after seeing results | **0** |
| candidates dropped after seeing results | **0** |
| cells screened | **154** |
| clear per-candidate on N1 (p<0.05) | 98 |
| clear per-candidate on N2 (p<0.05) | 97 |
| clear per-candidate on **both** correct-level nulls | **97** |
| clear **family-wise** on the worse null | **64** |
| would have cleared on the naive row-level null | 98 (*contrast only*) |
| **negative control `G01_noise`: cells clearing family-wise** | **0 of 8** |

`G01_noise` dR2 ranges 0.000021–0.000263 with per-candidate p 0.19–0.55 and family-wise p 1.0 in
all 8 cells, and its points propagation is +0.000014 to +0.000284 with cluster p 0.46–0.92
walk-forward.

**No-op placebo (mandatory), observed sds reported, not rounded to zero:**
identity placebo **sd = 4.336809e-19** (1 distinct draw value, `is_noop=True`); the
relabel-the-key-and-recompute placebo **sd = 1.734723e-18**, also a confirmed no-op — **so a
key-relabel control would have tested nothing on this frame**, which is why the entity swap is
used instead.

**Observed sds** of every candidate and outcome are in `FINDINGS.json → observed_sds`. Headlines:
`T01` 11.1768, `P01` 10.3756, `G01_noise` 0.9969, `y_ppm` 0.2763, `y_spm` 0.1992, `y_pts` 7.4831.

**Leakage probes:** 0 of 18 candidates flagged. The two reference probes fired on `refB` vs `refA`
— **both strictly prior by construction** — which is precisely the better-estimator case the kit's
**K1** fix documents; a flag is a screening flag, **not a verdict**. The positive control (a
full-season mean) fired far harder (corr +0.8465 vs +0.6741, dR2 0.2731 vs 0.0235), which is the
calibration.

---

# 8. DECLARED DEVIATION FROM THE HASHED SPECIFICATION

`CANDIDATES_PRESELECTED.md` §4 family M specified the norm as *"the **team's** strictly-prior
expanding mean of `T01`"*. `T01` is **player-specific**, so a team mean of it averages `O01` across
players and is not the player's own norm. Rather than silently reinterpret the hashed text, **both
norms were built**: `M01`/`M02` implement the hashed specification **exactly**, and
`M03`/`M04` are the player-norm variant, **declared as additions at implementation time, before
any statistic was computed**, and entered into the same family-wise correction. Both are reported
in §5.1. This is 2 added candidates and **0 added after seeing results**.

---

# 9. KIT FEEDBACK — **fifth user, no defect found**

`python TESTS.py` was re-run from this session: **159 assertions, 159 passed, 0 failed, exit 0**
(`run_log_kit_TESTS.txt`). Nothing in this screen worked around kit behaviour, and **no defect was
found.** The fourth user found none either; this is the second consecutive clean run. Three
positive observations and two minor documentation notes:

**Positive — the K2 port is confirmed correct on real data.** D085's `entity_swap_null` lived in
its own `ep_base.py` because the kit had no valid scheme. It was ported at D086. This screen called
**the kit function** on the same frame with the same seed and reproduced D085's `p_N2` **exactly in
every reproduction cell**. That is the strongest possible confirmation the port preserved
behaviour, and it came free.

**Positive — the K0 date value gate earned its keep immediately.** This frame's `master_player`
carries `season_type`, whose name matches the `season` substring. `assert_partition` correctly
reported *"name is season-like but VALUES are not seasons"* and skipped it rather than raising.
Under the pre-K0 asymmetry this would have been the season branch's job only; the point is that
the invariant now holds on both branches and the frame passed with **zero warnings**.

**Positive — `r2_of_forecast` vs `r2_plain` (the P3 hazard) is now unmissable.** This screen needed
both — `r2_of_forecast` to score the constructed points forecasts, `delta_r2_plain` to validate the
fast path — and the docstrings made the choice obvious. The fast-dR2 path was verified against
`delta_r2_plain` on **18 candidates × 2 bases** at max abs err **2.854e-16**.

**Documentation note 1 — `null_width_comparison`'s `inflation` has no documented meaning below 1.**
The docstring says only *"A value > 1 means the row-level null was TOO NARROW by that factor."* In
this screen several cells returned **inflation < 1** (0.795 and 0.841 on the ppm reproduction
cells), meaning the within-entity null is **narrower** than the row null. That is legitimate — the
within scheme preserves the entity-season mean structure that the row scheme destroys — but a
caller reading only the docstring has no guidance for what to do with it, and could reasonably
misread it as "the row null was conservative, so it is safe". A one-line addition stating that
`inflation < 1` still does **not** license the row-level p would close it. **This is a
documentation gap, not a behavioural defect; no number is wrong.**

**Documentation note 2 — `noop_placebo`'s `transform` signature.** The parameter is documented by
example rather than by signature; that `transform(df, rng) -> df` is the required shape had to be
read out of `E0_I0016`'s usage. A single line in the docstring would save the next user the
lookup. Again cosmetic.

---

# 10. CHEATING DISCLOSURE — where I could have made this look better

Written deliberately, in the spirit of an earlier agent that died holding a warning it had not yet
put on disk. **Every per-step result was written to disk incrementally** (`_s01.json` … `_s06.json`
and a CSV per step) as it was produced, before the next step ran.

1. **I could have quoted only the decision-stratum, single-reference numbers.** `dR2 = 0.007987` on
   shots-per-minute is the biggest number in this screen and it is the least defended one. The
   complete-reference and walk-forward versions are smaller and they are the headline instead.
2. **I could have let the tip-time variant carry the headline.** It is the strongest result by a
   wide margin, and dropping the constraint once would have made this read as a KEEP. It is
   labelled TIP-TIME in every table, in `FINDINGS.json`, in the verdict, and in the loss ladder.
3. **My own pre-registered prediction was half wrong and I kept it.** §5 of the hashed candidate
   file predicted the reference-incompleteness trap would collapse the effect. It collapsed the
   pooled effect 2.95× and the decision-stratum effect only 1.17×. Deleting §5 after the fact, or
   quietly reframing it as a confirmed diagnosis, would have been easy and is exactly the
   post-hoc-rationalisation move the pre-registration exists to block. It is reported as half
   right.
4. **The realised points dR2 exceeds the D084-form ceiling and I did not hide it.** Quoting only
   the realised +0.011521 and omitting the 0.004070 ceiling would have made the result look
   ~3× better. Quoting only the ceiling and omitting the reconciliation would have looked more
   rigorous while concealing a number a reader would eventually find. Both are in §4.3 with the
   identity that links them.
5. **`P02_c04_availweighted` looked like the best prior-only variant and is not.** Under D085's
   single reference it gives ppm dR2 0.006193 pooled — larger than `T01`. It dies under the
   complete reference and dies again walk-forward. Reporting it as the prior-only headline would
   have doubled the apparent usable effect. It is reported as attrition.
6. **The in-sample screening coefficient was the easy road.** It gives +0.011521 on the decision
   stratum against +0.007817 walk-forward. The walk-forward is the headline and the in-sample is
   labelled an upper bound.
7. **I could have used `data/w1_truth/player_game_availability.csv`.** It is the natural file for
   this exact question and it would have let me separate "inactive" from "active, zero minutes",
   which is the single biggest limitation in §3.1. It is artifact-granular at 2026 and forbidden.
   It was never opened, the limitation is stated instead, and the manifest verdict was read from
   disk at call time rather than cited from these notes.
8. **The absence-persistence diagnostic reads the next game.** It is genuinely informative about
   knowability and it genuinely reads a later game. It is fenced in the time-window table, produces
   no feature, and appears in no dR2. I could have converted it into a feature and it would have
   scored well.
9. **The family-wise correction could have been split.** Running the decomposition and the tip-time
   analysis as two scripts with two families would have roughly halved the correction and turned
   several borderline prior-only cells (e.g. `P01` ppm decision at fw p 0.0815) into clears. They
   were run in one script, in one family, deliberately.
10. **The frame filter, the entity level and the decision stratum were all taken from D085
    unchanged**, before any result was seen, precisely so they could not be tuned. `MIN_PRIOR_
    APPEARANCES = 3`, entity `team_season`, stratum `n_prior ≥ 8 AND trailing-5 minutes ≥ 24`.

---

# 11. WHAT WOULD SETTLE THIS

Not run here, and named so the next screen does not have to rediscover it:

1. **A manifest for a pre-game availability source.** The whole SPLIT hinges on the gap between
   today's box and the previous game's box. A properly-manifested, row-granular, as-of-timestamped
   injury/inactive feed would collapse §3 into a single measurement. **`data/w1_truth/
   player_game_availability.csv` and `roster_asof.csv` are the artifacts that should get manifests
   first** — they are artifact-granular at 2026 today and therefore unusable at E0/E1 for any
   question at all.
2. **Whether the champion already contains this.** Every number here is against a matched
   point-in-time reference, not the champion. If the champion already carries teammate context, the
   headroom is smaller than 0.0078; if it does not, this is the largest unexploited channel the
   program has found. **That question is not answerable without loading the champion, which this
   screen is not authorised to do.**
3. **`P01` is the crudest possible prior-only construction and it is the only one that survived.**
   A better prior-only availability model — one that actually models multi-game absence spells
   rather than copying last game's box — is the obvious next candidate, and the 55.8% persistence
   figure in §3.1 says there is structure there to model.
