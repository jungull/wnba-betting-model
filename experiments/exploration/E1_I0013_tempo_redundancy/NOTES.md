# E1 I0013 — Is the possession-volume survivor a generic tempo main effect?

**Status: E0/E1 exploration screen. Non-claiming.** No registry entry, no preregistration, no
leaderboard row, no promotion. Everything below is a **lead or a kill**, never a result, and none
of it may be cited as evidence.

**Verdict: KILL.**

**Partition: 2021–2024 only.** The 2025/2026 confirmation holdout was never read, joined, filtered
against, counted, plotted or described. Verified in `run_log_partition_verification.txt`, which
re-parses every file this directory wrote and tests **column values**, not text. The value test
matters here: my first pass produced eighteen false hits because the permutation-draw files have
columns *named* `..._team_season`. Their values are ΔR² draws around 1e-4, not seasons. The
checker now requires a column's values to be whole numbers in 1990–2100 before it treats the name
as meaningful.

---

## 0. First, the thing this is NOT: a market test

I verified this independently rather than taking it on trust, because the whole point of the E0
screen's own caveat rests on it.

- **`master_odds.csv` does not exist anywhere in this worktree.** Filename search over the whole
  tree: 0 hits.
- 45 files have market-flavoured names. **Zero of them carry a sibling `.manifest.json`**, so none
  can pass the 13.2.2 `asof_granularity` gate even before coverage is considered.
- `experiments/totals_groundwork/bookie_totals_per_game.csv` — 406 rows, **0 inside 2021–2024**;
  earliest season present is 2025. Real game totals, entirely in the holdout.
- `experiments/totals_head/game_level_totals.csv` — 229 rows fall in 2024, and its
  `bookie_consensus_total` column is **100% null on every one of them**. No price information in
  the partition.
- `data/props_capture/historical/master_props_historical.csv` — 11,237 rows dated inside the
  partition, spanning **2024-05-14 to 2024-10-21 only**. These are **player props, not game
  totals**, they cover the tail of one of four exploration seasons, and the file extends into the
  holdout.

**There are no game totals available for 2021–2024.** Nothing I ran is a market test and none of it
may be described as one. The consequence is not just "we didn't test it" — it is that the E0
screen's own disqualifying caveat **can never be retired on this partition** with the data present.
That fact is load-bearing in the verdict below.

I did find one thing that speaks to the market question without needing a price. See §4.

---

## 1. Construction audit — I read it, I did not trust the label

### (a) How `exp_gposs` is built, and what time window it reads

```
exp_gposs = 0.5 * (opp_pace48 + own_pace48)          run_screen.py L193, pv_base.py L289
pace48    = pr_n_poss * (48 / (pr_n_min / 5))        pv_base.py L156–163
```

`pr_n_*` come from `base.prior_expanding` (E0_I0012/base.py L129–138), which **aggregates to
`(season, team_id, gdate)` first, then takes cumsum minus the current date's own contribution**.
Possessions come from `base.team_possessions` on `master_team` — the symmetrised
`0.5·((fga−oreb+tov+0.44·fta) + opponent mirror)` (base.py L112–119) — and a value is set to NaN
unless the team already has ≥ 300 prior possessions (pv_base.py L88, L168–169).

**Answer: yes, `exp_gposs` is strictly prior-games-only, same season only.** Three independent
confirmations:

1. The date-level aggregation before the cumsum means same-day games cannot see each other, and
   subtracting the current date's own contribution means the target game is excluded.
2. `season` is inside the groupby key, so no later season can leak in.
3. I did not rely on reading the code. I built an analogous rolling team-pace field myself and
   brute-force recomputed 60 randomly sampled values using only rows with `gdate` **strictly less
   than** the target date — 60/60 reproduced exactly. Same audit on the player-side `a5` field:
   60/60.

There is **no retrospective baseline** anywhere in this feature or the E0 base. The only
cross-season quantities are previous-season shrinkage priors (`season += 1` merges), which are
prior information, not future information. `player_tendency_loo`-style full-season leave-one-out,
leave-one-SEASON-out, and leave-one-game-out full-season team rates — the three known offenders in
this repo — appear nowhere.

### (b) The baseline the ΔR² = 0.001133 was measured over

```
y_count ~ O + D + O*D + Mexp + O*Mexp                run_screen.py L209
```

- `O` — player's pregame expanding per-100-possession rate of the target stat, shrunk 5 units
  toward the **previous** season's own rate (base.py L239–244).
- `D` — opponent's pregame expanding **overall** per-100 allowance of the target stat, **excluding
  this player's own prior contribution** (base.py L234–237).
- `Mexp` — player's pregame expanding minutes per game, shrunk 2 games toward the strictly-prior
  expanding league mean (pv_base.py L215–216).
- All terms z-scored **within season** via `base.zwithin` (base.py L162–166).

This baseline is genuinely pregame-observable. It is **not** a retrospective baseline. But it is a
**rate-based** baseline: it contains the player's per-100 rate and expected minutes, and no direct
prior-games assist-per-game forecast. That gap is exactly what Test C fills.

### (c) Centering and weights — the R² convention question

- The response is the **raw assist count**, used as-is. **Not centered.**
- **No weights anywhere.** No `wls_r2` helper is imported; the defective
  `sst = sum((sqrt(w)*y − mean(sqrt(w)*y))**2)` form does not appear.
- The E0's `r2` is `1 − SSE/SST` with `SST` about the **unweighted** mean (pv_base.py L232,
  base.py L146).

**So D069 is already satisfied by the E0 screen, and by this E1. There is no weight-dispersion
understatement to correct.** I declare the same convention in `FINDINGS.json`.

---

## 2. Reproduction, before changing anything

| quantity | published | reproduced | \|diff\| |
|---|---|---|---|
| ΔR²(exp_gposs \| base) | 0.001133 | **0.001132538** | 4.6e-07 |
| R²_base | 0.4165 | 0.416486281 | 1.4e-05 |
| β (residual scale) | +0.0790 | +0.078995 | 4.7e-06 |
| 2021 ΔR² / β | 0.002526 / +0.086 | 0.002526 / +0.0862 | 2.1e-07 |
| 2022 ΔR² / β | 0.000728 / +0.071 | 0.000728 / +0.0707 | 7.8e-08 |
| 2023 ΔR² / β | 0.000012 / −0.010 | 0.000012 / −0.0100 | 2.8e-07 |
| 2024 ΔR² / β | 0.002574 / +0.132 | 0.002574 / +0.1315 | 5.1e-08 |
| ΔR²(difference \| sum) | 0.000001 | 0.000001 | — |

n = 10,167 rows / 774 games / 198 players, per-season 2128 / 2484 / 2784 / 2771. Every difference
is the rounding of the published figure. **The harness matches; every later difference in this
report is attributable to the change made.**

### One thing the E0 screen understated about its own null

`exp_gposs` is **symmetric in the two teams**, so it takes exactly **one value per `game_id`** —
I checked: max distinct values per game = 1, on 100% of games. It is a **game-level** quantity,
coarser than the team-game level. 10,167 rows carry 774 distinct values, which are themselves
generated by 48 team-season series.

Three nulls, all reported:

| null | mean | sd | frac ≥ real | sd vs naive |
|---|---|---|---|---|
| team-season relabel (**primary**) | 0.000102 | 0.000125 | **0.000** | 1.60× |
| game-level value permutation | 0.000061 | 0.000090 | 0.000 | 1.16× |
| row-level naive (**wrong**) | 0.000059 | 0.000078 | 0.000 | 1.00× |

Width ordering is naive < game-level < team-season. I declared the **team-season relabel** primary
before running anything, because it is the widest and it preserves the feature's real dependence
structure. A verdict taken on the row-level null would be anticonservative by 1.60× in sd.

### The defective no-op placebo, run on purpose

Permuting the grouping key consistently in `master_team` **and** the player frame, then
**recomputing** the aggregate from the permuted key, 60 draws:

```
real dR2          = 0.001132538408
no-op mean        = 0.001132538408
no-op sd          = 0.000000000000   <-- the defect signature
max |draw - real| = 7.8e-18          (floating-point noise)
```

By contrast the real game-level control has mean 0.000061, sd 0.000090 — non-degenerate. The real
controls are genuinely shuffling something.

---

## 3. The three redundancy tests

Tests A and C ran on a **common sample** (n = 8,919 of 10,167; 87.7%) so that every rung is
directly comparable — the restriction is imposed by the `crude10` proxy needing 10 prior games per
team. The reference ΔR² on that sample is **0.001082** (against 0.001133 on the full frame).
Test B is reported on both the common sample **and** the full frame.

### (A) Simple-proxy test — **the survivor passes**

Crudest possible proxy: unadjusted mean of the two teams' **raw** estimated possessions over their
previous N games, strictly before the current date, same season. No per-48 normalisation, no
shrinkage, no minimum-possession gate, no league prior.

| N | ΔR²(crude alone) | corr(crude, exp_gposs) | ΔR²(exp_gposs \| base+crude) | retained | p (team-season) |
|---|---|---|---|---|---|
| 3 | 0.000036 | +0.518 | 0.001211 | 112% | 0.000 |
| 5 | 0.000131 | +0.606 | 0.001065 | 98% | 0.000 |
| 10 | 0.000179 | +0.756 | 0.001209 | 112% | 0.000 |

The crude proxies are individually near-worthless over the E0 base, and `exp_gposs` retains all of
its increment over any of them. **Test A does not kill the survivor.** The per-48 normalisation,
the expanding window and the possession estimator are doing real work that a rolling mean of raw
possessions does not do.

### (B) Main-effect absorption — **decisive**

Full frame, n = 10,167, so directly comparable to the published 0.001133:

| rung | ΔR² | % of base | β | p (team-season) |
|---|---|---|---|---|
| E0 base | 0.001133 | 100% | +0.079 | 0.000 |
| + **own** team-season FE | 0.000582 | 51% | +0.071 | 0.033 |
| + **opp** team-season FE | 0.000429 | 38% | +0.061 | 0.007 |
| + **both** team-season FE | **0.000014** | **1.2%** | **−0.021** | **0.563** |

Common sample gives the same picture (0.000151, 14%, p = 0.19), as does the everything-at-once
rung (0.000178, p = 0.09).

**99% of the survivor's content is between-team-season cross-sectional variation.** With team
identity in the model there is essentially nothing left: no within-season updating, no timing
information, sign flipped, comfortably inside its own null. Its effective sample is **48
team-seasons**, not 10,167 rows.

Two controls that did *not* absorb it, reported because they cut against the kill:

- **Calendar.** Deciles of days-into-season × season leave ΔR² at 0.001212 (112%). An
  expanding-window estimate drifts mechanically across a season; `exp_gposs` is **not** a proxy for
  that drift.
- **Player-season FE** on top of the base leave 0.000341 (32%, p = 0.037) — some of it is
  cross-player composition, but not most of it.

**Honest limit on what Test B proves.** It *locates* the effect; it does not on its own refute it.
A genuine team-season-level pace effect is by definition absorbed by team-season fixed effects.
What Test B establishes is that the survivor is a **generic team-season tempo main effect and
nothing else** — which is precisely the question I was sent to answer, and the answer is yes.

### (C) Realistic-baseline test — **survives on its own, dies in combination**

Realistic baseline = E0 base **plus** a sensible point-in-time forecast of the player's own assist
production, all strictly prior-games-only:

- `apg_pre` — expanding assists per game, shrunk 2 games toward the strictly-prior expanding league
  APG (previous-season fallback)
- `naive_ct` — (prior assists / prior minutes) × (prior minutes / prior games), the naive count
  forecast
- `a5`, `a10` — mean assists over the previous 5 / 10 games
- `m5`, `m10` — mean minutes over the previous 5 / 10 games

| rung | R² | ΔR²(exp_gposs) | retained | p (team-season) |
|---|---|---|---|---|
| R0 E0 base (common sample) | 0.42532 | 0.001082 | 100% | 0.000 |
| C1 realistic player baseline | 0.43580 | **0.000776** | 72% | 0.000 |
| C2 realistic + crude5 | 0.43584 | 0.000907 | 84% | 0.000 |
| C3 realistic + crude5 + team FE + calendar | 0.44730 | **0.000004** | 0.4% | **0.753** |

For contrast, a deliberately **weak** baseline — player-season dummies and nothing else — gives
ΔR² = 0.000421 (p = 0.033), i.e. *smaller*, because player FE also soak up team composition. So the
usual "weak baseline flatters the candidate" story does **not** apply to this candidate, and I say
so even though it weakens my case.

**Test C does not kill it on its own.** Over a realistic point-in-time player baseline the effect
retains 72% at p = 0.000. It only dies when team identity is added on top — which is the Test B
result reappearing, not an independent kill.

### (D) An extra probe: is it just a pass-heavy offensive system?

`exp_gposs` splits into `own_pace48` (ΔR² 0.000476, β +0.051) and `opp_pace48` (ΔR² 0.000533,
β +0.054); the two are near-orthogonal within season (r = −0.107), so the halves roughly add.

The obvious competing mechanism the E0 confound ladder never controlled for: a team that plays fast
and *also* passes a lot. I built the player's own team's strictly-prior assists per 100 possessions
from `master_team` (≥ 300 prior possessions), plus the opponent's assists-allowed per 100 and both
sides' prior points per 100.

| rung | ΔR² | retained | p |
|---|---|---|---|
| + own-team prior ast/100 | 0.000925 | 82% | 0.000 |
| + own ast/100 + opp ast-allowed/100 | 0.000929 | 82% | 0.000 |
| + both sides' ast rates and offensive ratings | 0.000914 | 81% | 0.000 |

**Rejected as the explanation.** I ran this expecting it to hand me a clean kill and it did not.
Reported prominently against my own verdict.

---

## 4. What can be said about the market question without a price

This is the one genuinely new thing here, and it is why the verdict is a kill rather than a shrug.

The component of a pregame tempo instrument that a bookmaker's posted total is **certain** to
already contain is the **team-season pace level** — which teams are fast. Every book knows that.
The component a posted total is **least likely** to contain is within-season updating and timing —
the drift of a team's pace as the season goes on.

The fixed-effect decomposition says **~99% of the survivor sits in the first component and ~0% in
the second**. Not "some of it might be priced" — essentially all of the measurable signal is in the
part that is definitionally priced, and the part that might be exploitable is empirically empty.

That is an argument about the market question that needs **no** totals archive, and it points the
same way as the E0 screen's own caveat.

---

## 5. The 2023 anomaly

Per-season, each against **its own** correct-level null (team-season relabel *within* that season,
300 draws):

| season | n | games | ΔR² | p(ΔR², team-season) | p(ΔR², game-level) | β | null mean ± sd | null 95% | two-sided p | z |
|---|---|---|---|---|---|---|---|---|---|---|
| 2021 | 2,128 | 163 | 0.002526 | 0.000 | 0.010 | **+0.1144** | +0.0043 ± 0.0252 | [−0.042, +0.054] | 0.000 | **+4.38** |
| 2022 | 2,484 | 187 | 0.000728 | 0.037 | 0.070 | +0.0611 | −0.0030 ± 0.0275 | [−0.053, +0.052] | 0.030 | +2.33 |
| **2023** | 2,784 | 213 | 0.000012 | **0.740** | 0.777 | **−0.0090** | +0.0033 ± 0.0234 | [−0.041, +0.050] | **0.697** | **−0.52** |
| 2024 | 2,771 | 211 | 0.002574 | 0.030 | 0.003 | +0.1207 | +0.0419 ± 0.0385 | [−0.038, +0.109] | 0.003 | +2.04 |

### 2023 is a null season, not a sign flip

The brief's framing invited me to call this a sign flip, which would have been the more damning
and easier read. It isn't one. β = −0.0090 sits essentially at the **centre** of its own
permutation null (mean +0.0033, sd 0.0234, 95% interval [−0.041, +0.050]); two-sided p = 0.70,
z = −0.52. It is statistically indistinguishable from **zero**, not from a negative effect. Calling
it a dead season is exactly right; calling it a sign flip overstates it.

### But the season-to-season instability is real

Real per-season betas [+0.114, +0.061, −0.009, +0.121]: range 0.1296, sd 0.0601. Against the same
correct-level null:

- null range mean 0.0746 ± 0.0294 → **frac(null range ≥ real) = 0.047**
- **frac(null sd ≥ real sd) = 0.030**

I computed both statistics before looking and both agree. **The four-season spread is larger than
the correct-level null produces by chance.** This is genuine instability, not sampling noise.

### What is *not* wrong with 2023

I chased four candidate explanations and ruled all four out.

| candidate cause | verdict | evidence |
|---|---|---|
| data-coverage break | **ruled out** | 2023 has the fullest schedule of the four (240 games, 40/team), 100% non-null pregame pace coverage, no date gap over 6 days, and the largest analysis-row count (2,784) |
| instrument failure | **ruled out** | corr(exp_gposs, realised game possessions) = **0.274** in 2023 vs 0.216 in 2022; odd/even split-half reliability of team pace r = **0.519** (SB 0.683) in 2023 vs r = 0.418 (SB 0.589) in 2022. The instrument works *better* in 2023 than in a season where the effect showed up |
| feature-dispersion collapse | **ruled out** | sd(exp_gposs) = 1.048 in 2023 vs 1.006 (2022) and 1.067 (2024); cross-team dispersion of true season pace 1.054 vs 1.033 and 1.205 |
| schedule or rule change | **no evidence** | 2023 and 2024 have identical schedule shape (240 games, 40/team) and similar league pace, yet β = −0.009 vs +0.121 |

### The more interesting outlier is 2021, not 2023

2021 is the **shortest** season (32 games/team), has the **widest** feature dispersion (sd 1.543 vs
~1.05 elsewhere), the **strongest** instrument (corr with realised game possessions 0.479 vs
0.22–0.31), the **strongest** outcome link (corr(realised game possessions, assists) 0.117 vs
0.02–0.04), a 35-day mid-season break, and the largest per-season effect (z = +4.38). The pooled
increment leans heavily on the least typical season in the partition — consistent with the E0's own
recency slice, where dropping 2021 took the pooled ΔR² from 0.001133 to 0.000698.

---

## 6. Verdict — KILL

`exp_gposs → ast` is a **generic, purely cross-sectional team-season tempo main effect** with no
within-season content, unstable across seasons, and its entire content sits in exactly the
component a posted game total is certain to price — which cannot be tested on this partition
because no game-totals archive exists for 2021–2024.

**Reasons:**

1. **Test B.** With own- and opponent-team-season FE, ΔR² falls 0.001133 → 0.000014 (1.2%,
   p = 0.56, sign flipped). 99% between-team-season, ~0% within-season. Effective sample: **48
   team-seasons**, not 10,167 rows.
2. **The market caveat is now both sharper and permanently untestable.** The surviving component is
   the one a total certainly prices; the component a total least likely prices carries nothing.
   And there are no 2021–2024 game totals in this worktree, so the E0's own disqualifying caveat
   can never be retired on this partition.
3. **Test C.** Over a realistic point-in-time player baseline the increment is 0.000776 — roughly
   an order of magnitude under I0009's existing 0.006–0.007 — and 0.000004 (p = 0.75) once team
   identity is also controlled.
4. **Step 4.** 2023 is a dead season with no data, coverage, instrument, dispersion or schedule
   explanation, and the four-season beta spread exceeds its own correct-level null (p = 0.047 on
   range, 0.030 on sd). The pooled figure leans on 2021, the most atypical season in the partition.

**Reported against the verdict** (things that did *not* kill it): it is not redundant with a crude
rolling-mean tempo proxy (Test A, 98–112% retained at p = 0.000); the own-team passing-rate
mechanism was rejected (81–82% retained); a calendar control does not absorb it; and the
between-team-season association itself is statistically real on this partition (pooled p = 0.000,
3 of 4 seasons at z = +2.0 to +4.4).

**If the coordinator prefers to record this as SPLIT rather than KILL**, the only defensible
corrected headline is:

> Across 48 team-seasons in 2021–2024, team-season pace level is cross-sectionally associated with
> player assist counts beyond a pregame rate-and-minutes baseline (ΔR² 0.001133 pooled, 0.000776
> over a realistic player baseline, 0.000014 once team identity is controlled). There is no
> within-season component, no stability across seasons, and no test against a price is possible on
> this partition.

It is **not** a player-level possession-exposure channel and must never be described as one.

---

## 7. Where I could have cheated

| choice | the more favourable alternative | what I did |
|---|---|---|
| **Which null is primary** | Reporting the naive row-level null (1.60× narrower in sd) or the game-level null would have made every rung look more significant — **favouring KEEP** | Declared the team-season relabel primary **before running anything**, because it is widest and preserves the dependence structure. All three reported. |
| **Crude-proxy window N** | Reporting only N=10 (r = 0.756 with exp_gposs, the most redundant-looking) would have **favoured a kill on Test A** | Fixed N ∈ {3,5,10} **before** running; reported all three. Test A came out against the kill and is reported that way. |
| **Contents of the "realistic" baseline** | A richer one (opponent-adjusted assist projection, teammate availability, a fitted minutes model) would very likely have pushed 0.000776 lower and made the kill easier | Fixed the six features **before** running and did **not** tune them after seeing 72% retention. My restraint here biases **against** my own verdict. |
| **Running Test B on the full frame** | The full-frame result (1.2% retained) is **more damning** than the common-sample one (14%). I ran the full-frame version **after** seeing the common-sample version | Disclosed. Both reported. The stated reason was comparability with the published 0.001133 on identical rows — but the ordering is disclosed because it could have been motivated. |
| **How to describe 2023** | Calling it a sign flip would have been more damning and easier to justify a kill on | Tested it and reported the **less** damning, more accurate finding: indistinguishable from zero (two-sided p = 0.70, z = −0.52). Decided after seeing the null, against my verdict's convenience. |
| **The own-team passing-rate probe** | Not running it. I expected it to absorb the effect and hand me a clean kill | Ran it; it did not absorb (81–82% retained); reported prominently in the "does not kill it" list. |
| **Heterogeneity statistic** | Picking whichever of range/sd crossed 0.05 would be a cherry-pick | Computed both before looking; both agree (0.047, 0.030). Both reported. |

One more, on scope rather than statistics: my first partition check flagged eighteen "violations"
that were column *names* ending in `_season` holding ΔR² draws. I could have quietly deleted the
check. I fixed it to test values and left both the failure and the fix in the run log.

---

## 8. Write scope and files

**This directory only.** `E0_I0013_possession_volume` and `E0_I0012_layer3_noncollinear` were
imported from and **not modified**; `base.OUT` and `pv_base.OUT` were re-pointed into this
directory at import, and bytecode writing was disabled **before** those imports. Verified after
the fact by timestamp: the two `.pyc` files in `E0_I0012/__pycache__` are dated 22:16 and 22:23,
both **before** this run's earliest artifact, and one of them (`f34_style_rest`) is a module this
E1 never imports. `git status` shows one changed path inside this directory and two untracked
directories outside it that belong to other screens.

| file | what it is |
|---|---|
| `e1_lib.py` | shared machinery; imports the two E0 bases read-only, re-points their `OUT` here, partition guard, D069 R², FWL increments, the three permutation levels |
| `step0_env_audit.py` | independent market-archive search, manifest gate, value-based partition coverage of every market-like file |
| `step2_reproduce.py` | reproduction of the published number, layer check, unit-of-variation audit, the three nulls, the deliberate no-op placebo |
| `step3_redundancy.py` | Tests A, B and C on the common sample, plus the weak-baseline contrast |
| `step3d_step4.py` | full-frame FE absorption, the own-team-passing mechanism probe, per-season nulls, the beta-heterogeneity test, 2023 forensics, per-season split-half reliability |
| `make_findings.py` | assembles `FINDINGS.json` from the result JSONs; retypes no number |
| `verify_partition.py` | re-parses every file written here and tests season/date **values**; write-scope check by timestamp |
| `FINDINGS.json` | machine-readable everything, with the R² convention declared |
| `perm_draws_*.csv`, `noop_diagnostic_e1.csv` | the raw draw distributions behind every p-value |
| `common_sample_features.csv` | the constructed strictly-prior features, so the builds are auditable |
| `run_log*.txt` | full stdout of every run, including every printed season list |
