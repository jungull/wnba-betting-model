# E1 I0004b — the shot-SELECTION channel, role concentration, and the five-zone family

**E1 is NON-CLAIMING.** Nothing below is a RESULT. It is a LEAD or it is dead. No
registry entry, no preregistration, no promotion, no leaderboard row, never cited as
evidence. Seasons **2021–2024 only**; the 2025/2026 confirmation holdout was never
read, joined, filtered against, counted, plotted or described.

Parents: `E0_I0004_shot_location_allowance`, `E1_I0004_rim_finishing`.

---

## The short version

Three things were untested after the conversion-channel screen. All three now have
answers, and they do not all point the same way.

**1. The selection channel is real, and it is much larger than the conversion
channel that I0004 has been carried on.** A player's Restricted-Area *attempt share*
moves with the opponent's strictly-prior-games rim-share allowance at
**beta = +0.774** (row-level) / **+0.919** (cluster-level), **corr +0.188**,
**R² = 0.0352**. Against a permutation null built at the **opponent-team-season**
level the unadjusted p is **0.0002** and the **five-zone family-wise p is 0.0002** —
both at the 1/5001 resolution floor of 5000 draws. 4/4 seasons positive, both halves
positive, *strengthens* under player-season and shooting-team-season fixed effects,
and essentially unchanged when the opponent's allowance is rebuilt excluding every
prior game against the shooting team (+0.775) or excluding the player's own prior
attempts (+0.783).

**2. But it is not a rim story.** All five zones are positive; four of five clear the
family-wise correction on the row-level statistic. This is a general shot-**location**
matchup effect that happens to be strongest at the rim. The rim framing that I0004
has carried since E0 does not survive on the selection side.

**3. Role/volume concentration: no.** For selection the share-metric slope is flat to
mildly *decreasing* in role (+0.818 / +0.847 / +0.639 across preselected low/mid/high
FGA bins; continuous interaction −0.0245, two-sided permutation p 0.0165). The
conditional-edge thesis does not get support here — the effect is broad-based. For
the conversion channel there *is* a monotone gradient (+0.253 / +0.354 / +0.557; R²
0.00034 → 0.00175, a 5.1× spread) under both binnings, but the continuous interaction
is p = 0.108 at the correct grouping level, so it is **suggestive, not established**.

**4. The surviving conversion headline survives multiplicity, but thinly.** Scoring
+0.3731536 against the opponent-team-season null: z = +2.75, unadjusted one-sided
p = **0.0026**, five-zone family-wise p = **0.0124** (one-sided, preselected) /
**0.0220** (two-sided). E1's reported "0/400 draws" was resolution-limited; at 5000
draws the honest number is 0.0026 before correction and 0.0124 after.

**Verdict: SPLIT.** Corrected headline for the conversion channel is unchanged
(+0.373 slope / +0.0176 diff / +0.0288 corr) and now carries a family-wise p of
0.0124. The new selection-channel lead is `beta +0.774, R² 0.0352, family-wise
p 0.0002`, but must be carried as a **shot-mix** lead, not a rim lead.

---

## 0. Reproduce before changing — exact

Before touching anything, the corrected E1 conversion headline was rebuilt from the
raw shot files by an independent transcription of the same construction.

| | n | corr | diff | beta |
|---|---|---|---|---|
| E1 `measure_results.json` | 30764 | +0.02881718 | +0.01757440 | +0.37315357 |
| reproduced here | 30764 | +0.02881718 | +0.01757440 | +0.37315357 |
| **absolute difference** | **0** | **0.000e+00** | **0.000e+00** | **0.000e+00** |

E0's published five-zone leave-one-game-out table also reproduces exactly (all five
zones match on n, corr and diff to < 5e-5). Every later difference in this screen is
therefore attributable to the change, not the harness.

**The killed E0 headline (+0.0392) is not used anywhere and is not cited.**

---

## 1. TIME-WINDOW TABLE — what every constructed quantity reads

The whole reason this screen exists is that E0 measured an increment over a baseline
that read the future *on both sides* and never noticed. So: every quantity, and the
window it actually reads. Read the construction, not the label.

| quantity | window it READS | prior-only? |
|---|---|---|
| `share_z` (response) | the current game only — it *is* the outcome | n/a |
| `S1` own zone-share baseline | the player's **played games strictly before this game, same season**. Frozen `own_rate_v2_split_alpha` called with `minutes := total FGA in the game`, `target := zone attempts`, so its efficiency channel *is* `EWMA_0.03(zone share)` shifted by one. Verified against a direct `pandas.ewm`: **max abs diff 7.772e-16** | **yes** |
| `S2` shrunk own zone-share baseline | same player's strictly prior games in season, shrunk (K = 50) toward the league share over games played **strictly before this calendar date** | **yes** |
| `OS` opponent zone-share allowance | the **opponent's games strictly before this game, same season** (expanding cumsum minus the current row — a team plays at most one game per date, so there is no same-day ambiguity), minus the league share over games played **strictly before this calendar date** | **yes** |
| `OS_exT` | as `OS`, minus every prior game the opponent played **against the shooting team** | **yes** |
| `OS_exP` | as `OS`, minus **this player's own** prior attempts against that opponent | **yes** |
| `lg_share_prior` | all league shots on calendar dates **strictly before** this game's date, same season | **yes** |
| `role_prior_fga` | `EWMA_0.30` of the player's FGA per game over strictly prior games in season (the frozen baseline's exposure channel) | **yes** |
| `B1` / `Bz` conversion own-rate | the player's strictly prior games in season | **yes** |
| `O2` / `OC` opponent conversion allowance | the opponent's strictly prior games in season | **yes** |
| `fga` (share denominator; `dR²` conditioner) | **the current game** — realised, NOT pregame-observable | **NO — disclosed** |
| `B0` (E0's leave-one-SEASON-out player × zone rate) | **the player's other seasons — reads the future** | **NO** — used in the reproduction step **only** |
| `O1` (E0's leave-one-GAME-out FULL-SEASON opponent rate) | **the opponent's whole season minus this game — reads the future** | **NO** — used in the reproduction step **only** |

Two of these are the known offenders inherited from E0/E1 code. They are reproduced
faithfully so the reproduction step is honest, and they appear in **no new
statistic**. Everything used for a new claim is strictly prior-games-only.

The one honest exception is `fga`. The share is *attempts in zone / attempts in
game*, so the denominator is realised volume. That makes this a **shot-mix model
given volume**, not a volume model. It is disclosed at every point the `ΔR²` appears
and is not claimed as a forecasting increment.

---

## 2. The zone maps were not read, and were not needed

All five `data/zone_maps/*` carry `asof_granularity = "artifact"` — checked by
reading the **column value** in each sibling `.manifest.json`, not by scanning text.
Their own manifests say a 2021 row's shrunk value saw later seasons, so filtering
does not help. None were opened.

Zone assignment instead comes from the raw per-shot `SHOT_ZONE_BASIC` label inside
each per-season shot file (`Left Corner 3` + `Right Corner 3` → `Corner 3`). A shot's
zone label is a property of that shot's own coordinates and reads no other row, so it
carries no cross-season information at all. `data/shotcharts/*` has no manifests and
needs none: the season is the filename.

`data/masters/*` are `asof_granularity = "row"` and would have been usable filtered.
They were simply not needed and were not read.

Full manifest inventory (13 artifacts: 2 `row`, 11 `artifact`/`season`) in
`run_log_05_verify_partition.txt`. **Structural violations: 0.**

---

## 3. What was built

**Panel.** Every player-game with ≥ 1 FGA × the five zones, with zero-attempt zones
**present as share = 0** — otherwise the test would condition on having shot there.
Analysis rows gate at ≥ 5 FGA in the game and ≥ 3 prior played games:
**10,307 player-games × 5 zones = 51,473 rows**, 2021–2024.

**Opponent gate**: ≥ 200 attempts faced in prior games this season (≈ 2.5 games).
91.8% of opponent-games qualify.

All gates (`MIN_FGA_GAME = 5`, `MIN_PRE_TOTAL = 200`, `SHRINK_K = 50`,
`ROLE_CUTS = (6, 11)`) were written into `build_frames.py`'s docstring **before the
first run** and none was tuned.

---

## 4. The selection result

Row-level statistics, plain unweighted OLS, R² = 1 − SSE/SST about the unweighted
mean:

| zone | n | corr | diff | beta | R² | p (unadj) | **p (5-zone FWE)** | inflation vs naive null |
|---|---|---|---|---|---|---|---|---|
| **Restricted Area** | 10307 | **+0.1876** | +0.0443 | **+0.7743** | **0.0352** | **0.0002** | **0.0002** | 3.80× |
| In The Paint (Non-RA) | 10307 | +0.1112 | +0.0255 | +0.6530 | 0.0124 | 0.0004 | 0.0024 | 3.58× |
| Mid-Range | 10307 | +0.0861 | +0.0164 | +0.5558 | 0.0074 | 0.0002 | 0.0010 | 2.48× |
| Corner 3 | 10245 | +0.0370 | +0.0052 | +0.3247 | 0.0014 | 0.0110 | 0.0602 | 1.80× |
| Above the Break 3 | 10307 | +0.0972 | +0.0237 | +0.5630 | 0.0094 | 0.0002 | 0.0002 | 2.66× |

**In natural units** (per 1 sd of the opponent regressor, sd = 0.0423 at the rim): a
1-sd more rim-permissive defence moves **+3.28 share points**, i.e. **+11.3%
relative** on a 29.0% base, i.e. **+0.34 rim attempts** for a 10.3-FGA player.

**Persistence.** Rim share: +0.667 / +0.786 / +0.927 / +0.733 — 4/4 positive; halves
+0.734 and +0.812. Four of five zones are 4/4 positive (Corner 3 is 3/4).

**Fixed effects.** Player-season FE: +0.919 → **+0.938**. Shooting-team-season FE:
→ **+0.936**. It is within-player and it is not a shooting-team composition artifact.

**The mechanical-confound test.** An all-five-zones-positive result on a compositional
response demands one: the opponent's allowed mix is measured against the offences it
faced, one of which may be this player's own team. Rebuilding the regressor to exclude
every prior game against the shooting team leaves the rim slope at **+0.7753** (from
+0.7743); excluding the player's own prior attempts gives **+0.7834**. Both stricter.
`corr(OS, OS_exT) = 0.982`. The confound is not doing the work.

**Baseline and weighting.** S2 (shrunk expanding prior share) gives +0.7645;
attempt-weighted gives +0.7530 (with standard weighted SST about the weighted mean).
The conclusion is not an artifact of how the prior share was smoothed.

**Player-game increment.** `ra_attempts ~ 1 + S1·fga` vs `+ fga·OS`:
**ΔR² = +0.0191** pooled, and **+0.0200 / +0.0205 / +0.0163 / +0.0197** by season —
stable, unlike the conversion channel's ΔR² which was essentially all 2023–24. Against
the opponent-team-season null the ΔR² 95th percentile is +0.0029, so p = 0.0002. **But
this is conditional on realised FGA and is a mix increment, not a forecast increment.**

---

## 5. Why the nulls are built at the opponent-team-season level, and what it changed

The regressor is an opponent-team-season quantity: **12 teams × 4 seasons = 48
distinct defensive units** sharing a value across thousands of rows. The program has
twice found the naive row-level null too narrow, and has seen cluster-robust SEs
*raise* t in one case and lower it in another — so they are reported here but are the
basis of no verdict.

**Inflation factor, sd(correct cluster-level null) / sd(naive row-level null):**

- selection: **1.80× – 3.80×** (rim: 3.80×)
- conversion: **0.89× – 2.29×** (rim: 2.29×)

The naive null would have declared *every* selection zone at p ≈ 0.0005 including
Corner 3, which the correct null puts at 0.0110 unadjusted / 0.0602 family-wise. That
is exactly the failure mode the constraint was written for.

Permutation form: the **already-computed** team-season allowance values are reshuffled
across teams within season and re-assigned to rows. The whole five-zone vector travels
with the team, so the cross-zone correlation structure survives — which is what makes
max-t across the family valid. 5000 draws, seed 20260807.

**The defective no-op (D0), run on purpose.** Permuting the grouping *key* and then
recomputing the aggregate from it is a bijective relabel: every row still receives its
own true value. Signature confirmed on both families —

```
selection  / Restricted Area:  ref +0.9193293906  mean +0.9193293906  sd 0.0000000000  max|dev| 0.00e+00
conversion / Restricted Area:  ref +0.6700704452  mean +0.6700704452  sd 0.0000000000  max|dev| 0.00e+00
```

It tests **nothing**. It is here so the genuine controls can be seen to be genuine by
contrast.

---

## 6. The five-zone family-wise correction

Each zone's beta is standardised by its own permutation null; the maximum z over the
five zones is taken **within each draw** (same team permutation across all zones); the
family-wise p is the fraction of draws whose max exceeds the zone's real z. One-sided
was preselected (the hypothesis is directional). Two-sided is reported and is stricter.

**Conversion family — the row-level reals, which is what E1 carries:**

| zone | beta | z | p unadj | **p FWE 1-sided** | p FWE 2-sided |
|---|---|---|---|---|---|
| **Restricted Area** | +0.4037 | +2.95 | 0.0012 | **0.0066** | 0.0128 |
| In The Paint (Non-RA) | −0.1216 | −0.42 | 0.6551 | 0.9958 | 0.9978 |
| Mid-Range | +0.0377 | +0.41 | 0.3445 | 0.8860 | 0.9986 |
| Corner 3 | −0.2558 | −1.54 | 0.9370 | 1.0000 | 0.4905 |
| Above the Break 3 | +0.0005 | +0.15 | 0.4379 | 0.9480 | 1.0000 |

**E1's exact carried headline** (+0.3731536, on its 30,764-row common set) scored
against the same null: z = +2.75, unadjusted **p = 0.0026**, family-wise
**p = 0.0124** one-sided / **0.0220** two-sided. **It survives.** But it is a
one-in-eighty statement, not the "0/400 draws" statement E1 made — that was
resolution-limited by 400 draws, not wrong.

### The stricter/looser disagreement, stated plainly

This is the single most important caveat in the screen. The permutation null's
regressor is team-season-constant by construction, so the *like-for-like* real is the
cluster-level one (x replaced by its team-season mean). On that reading the
conversion family looks very different:

| zone | beta row-level | p FWE row | beta cluster-level | p FWE cluster |
|---|---|---|---|---|
| Restricted Area | +0.4037 | 0.0066 | +0.6701 | 0.0002 |
| In The Paint (Non-RA) | −0.1216 | 0.9958 | +0.2986 | 0.0352 |
| Mid-Range | +0.0377 | 0.8860 | +0.5628 | **0.0002** |
| Corner 3 | −0.2558 | 1.0000 | +0.2640 | 0.0834 |
| Above the Break 3 | +0.0005 | 0.9480 | +0.3378 | 0.0050 |

Mid-Range flips from "nothing" to "as strong as the rim". The mechanism is not
mysterious: within a team-season the expanding opponent allowance carries a lot of
early-season estimation noise, which attenuates the row-level slope; aggregating to
the team-season mean removes it. Both readings are defensible. **I preselected the
row-level form** because it is what E1 reported and what any downstream model would
actually consume, and I am carrying it. But a reader should know that the looser form
would support a much broader claim, and that I chose before seeing which way it went
only in the sense that the convention was inherited — not because I tested and picked.

For the **selection** family the two readings agree on the substance (rim, paint,
mid-range and ATB3 all clear family-wise correction on both readings; only Corner 3
differs: 0.0602 row vs 0.0002 cluster).

---

## 7. Role / volume concentration

Role feature: `EWMA_0.30` of the player's FGA per game over strictly prior games in
season. Two binnings, both specified before running.

**Selection (rim share)** — preselected absolute cuts:

| bin | n | mean FGA/g | beta | perm z | perm p | R² |
|---|---|---|---|---|---|---|
| low (<6) | 2315 | 4.33 | +0.8181 | +5.03 | 0.0005 | 0.0298 |
| mid (6–11) | 4411 | 8.49 | +0.8474 | +5.53 | 0.0005 | 0.0405 |
| high (≥11) | 3581 | 14.04 | +0.6389 | +5.70 | 0.0005 | 0.0326 |

Within-season tertiles agree: +0.860 / +0.812 / +0.636. Continuous interaction
**−0.0245**, null sd 0.0101, z = −2.42, two-sided permutation **p = 0.0165** — a
*significantly negative* interaction. **There is no high-usage pocket.** The effect is
broad-based, and if anything the share responds slightly *less* for high-volume
players.

One arithmetic caveat that must not be mistaken for concentration: measured in
**attempts** rather than share, the ordering reverses (+0.150 / +0.305 / +0.380
attempts per 1 sd for low/mid/high), simply because high-usage players take more
shots. That is a volume identity, not a heterogeneous effect.

**Conversion (rim finishing)** — preselected absolute cuts:

| bin | n | mean FGA/g | beta | perm z | perm p | R² |
|---|---|---|---|---|---|---|
| low | 4626 | 4.40 | +0.2533 | +2.32 | 0.0080 | 0.00034 |
| mid | 12713 | 8.65 | +0.3537 | +3.54 | 0.0005 | 0.00077 |
| high | 12250 | 14.13 | +0.5566 | +3.85 | 0.0005 | 0.00175 |

Tertiles agree (+0.335 / +0.362 / +0.576). Monotone, 2.2× in slope and 5.1× in R².
But the continuous interaction is **+0.0389**, null sd 0.0200, z = +1.60, two-sided
**p = 0.108**. So: the shape the conditional-edge thesis predicts is there, and it is
not significant at the correct grouping level. **Suggestive, not established.** With
48 clusters this is a power statement as much as an evidence statement.

---

## 8. Why the two R² numbers must not be compared naively

Selection R² 0.0352 vs conversion R² 0.00098 is a 36× ratio, and most of it is a unit
artifact. The selection response is a player-game share averaging **10.3 shots**; the
conversion response is **one Bernoulli draw**.

| | var(response) | irreducible binomial floor | % irreducible | R² |
|---|---|---|---|---|
| selection, rim share | 0.03052 | 0.02023 | **66.3%** | 0.0352 |
| conversion, single shot | 0.24190 | 0.21929 | **90.7%** | 0.00098 |

As a fraction of *reducible* variance the selection channel explains ~10.4%. The
conversion channel's reducible slice is so thin that the equivalent ratio (~1.0%) is
numerically unstable and is shown only to make the point. The selection channel is
genuinely the bigger object, but by roughly one order of magnitude, not two.

---

## 9. Where I could have cheated

| choice | more favourable option | what I chose | before or after seeing the result |
|---|---|---|---|
| row-level vs cluster-level "real" | **cluster-level**, dramatically so for conversion Mid-Range (0.0002 vs 0.8860) | row-level | convention inherited from E1, so effectively preselected — but I did see both. Both reported in full; see §6. |
| one-sided vs two-sided max-t | one-sided | one-sided as headline | **before** (directional hypothesis); two-sided reported everywhere and changes no conclusion |
| `OS_exT` / `OS_exP` stricter regressors | n/a — they made the result *stronger* | reported as robustness; headline stays on the preselected `OS` | **after** seeing the headline. Added because an all-five-zones-positive result demanded a mechanical-confound test. Had they weakened it they would still be here. |
| gates (5 FGA, 200 prior attempts, K = 50, cuts 6/11) | unknown — not searched | as listed | **before** the first run, written into the script docstring. No gate was tuned; no alternative tried. |
| unweighted vs attempt-weighted | attempt-weighted (R² 0.0376 vs 0.0352) | unweighted | **before**, by D069's default. Weighted reported with weighted SST about the weighted mean. |
| role binning | neither — both agree | absolute cuts as headline, tertiles reported | **before**; both specified together |
| which zones/seasons to report | reporting only Restricted Area | all five zones, all four seasons, both halves | **before**; nothing dropped |
| Backcourt exclusion | including it would make FWE *stricter* | excluded, following E0's own n ≥ 200 gate | **before**; 254 shots, 0.19% |

One more, which is not a choice but a limit: with 48 opponent-team-season clusters the
permutation null cannot resolve below p ≈ 1/5001, and several selection cells sit at
that floor. "p = 0.0002" here means "no draw in 5000 reached it", not a point estimate.

---

## 10. What could not be established

- **No walk-forward, no preregistration, no holdout evaluation** — out of E1 scope.
- **The ΔR² of +0.0191 on rim attempts is conditional on realised FGA.** A
  pregame-observable volume model was not built, so this is not a forecasting
  increment and must not be carried as one.
- **Pace, rest, home/away, injuries and lineup** were not conditioned on; the
  opponent allowance is built from shot-event data alone.
- **Exploitability is untested.** A 0.34-attempt shift at the rim is small relative to
  typical prop lines, and no market comparison was made.
- **The role-concentration question is underpowered.** 48 clusters is not many for an
  interaction test; the conversion gradient may well be real and simply undetected.
- **Why the effect is broad across zones** — a genuine defensive-scheme story, a
  schedule-mix artifact this screen's exclusions did not catch, or both — is not
  resolved. The exclusions rule out the two most obvious mechanical routes, not all.

---

## 11. Verdicts

| target | verdict |
|---|---|
| Shot-selection channel — existence and within-partition persistence | **KEEP-AS-LEAD** (beta +0.774, R² 0.0352, family-wise p 0.0002) |
| The claim that the selection effect is **rim-specific** | **KILL** — all five zones positive; carry it as a shot-**mix** lead |
| Role/volume concentration, selection channel | **KILL** — no concentration; interaction significantly *negative* |
| Role/volume concentration, conversion channel | **KEEP-AS-LEAD (weak)** — monotone 2.2×/5.1× gradient, interaction p = 0.108, not established |
| Five-zone multiplicity for the surviving conversion headline (+0.373) | **SURVIVES** — family-wise p 0.0124 one-sided / 0.0220 two-sided |
| **OVERALL** | **SPLIT** |

The corrected conversion headline is unchanged and should continue to be carried as
**+0.373 slope / +0.0176 diff / +0.0288 corr**, now with **family-wise p = 0.0124**
attached. The E0 headline **+0.0392 remains dead and is not used anywhere in this
screen.**
