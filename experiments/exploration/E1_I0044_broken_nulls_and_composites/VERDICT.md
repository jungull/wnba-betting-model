# VERDICT — E1_I0044, the 73 broken nulls and the programme-wide composite sweep

Partition: **2021–2024 exploration only. 2025/26 was never opened.** Every frame read asserts
`season <= 2024` and `max(gdate) < 2025-01-01` before use.
Preregistration `PREREG.md`, sha256 `d25fc5ec7898779da0082e888b974cfb62689a2356729efe07557a2857f24c7e`.

---

## HEADLINE (first three sentences, as required)

**Of the 35 cells D103 records as adequately powered among the 73 broken nulls, 18 reclassify to
PERMANENTLY UNVERIFIABLE because their candidate has exactly one distinct value per season and is
therefore annihilated by the screen's own base — no statistic exists, so no null could ever have
existed — and on the clean decision-stratum window (2023–24, ≥8 prior appearances and ≥24
trailing-5 minutes) the remaining 17 are all BLIND, so 0 of 35 survive as adequately powered
there; on the full 2022–24 arm kept only for like-for-like comparison with the published cell,
those 17 remain adequately powered and 37 of the 38 cells D103 called blind become adequately
powered, because the degenerate null inflated the critical value rather than the standard
deviation.** **The programme-wide composite sweep covers all 540 (screen, candidate) pairs in the
23 screens that decide cells; 174 of them are composites and 15 are EXPOSED — 14 more than the
one `E1_I0040` already knew about — with 129 clean and 28 undeterminable.** **Of the 73, 54 were
re-measured under a repaired null, 18 are permanently unverifiable as structurally void, and 1
has no functioning null anywhere on disk.**

---

## THE COUNTERWEIGHT, IN THE SAME BREATH

**The repaired null is not uniformly calibrated, it breaks on the candidate that tops the survivor
ranking, and it breaks catastrophically on one other.** Measured Type-I at δ = 0 on five cells,
against 0.05 nominal at a Monte-Carlo se of 0.0109 (`TYPE_I_CALIBRATION.csv`):

| cell | composed-2 (mine) | `E0_I0014`'s own level-matched null | row-naive |
|---|---:|---:|---:|
| `pl_minutes_prior\|minutes_absres` | 0.0225 | 0.0175 | 0.2625 |
| `pl_dnp_frac5\|pts_sqres` | 0.0250 | 0.0675 | 0.1800 |
| `pl_usg_sd5\|pts_absres` | 0.0525 | **0.2500** | 0.2800 |
| `pts__pred_cv\|fga_absres` | **0.1475** | **0.5925** | 0.5475 |
| `pl_games_prior\|pts_absres` | **0.5950** | **0.9250** | 0.9075 |
| **median** | **0.0525** | **0.2500** | **0.2800** |

Three of five are at or below nominal. Two are not: `pts__pred_cv` is a ratio with a heavy tail,
and `pl_games_prior` is a pure within-block counter whose permuted column cannot have the real
column's autocorrelation structure under any of the three schemes — **no null tested here,
including mine, is valid for it.** **Because of this, §2's survivor list is NOT an established
result. It is a list of candidates for follow-up with a measured Type-I attached to each.**
**My analytic floors are also optimistic by 1.4–2.9× against injection** on four of five cells
(ratios 0.739, 0.491, 0.403, 1.330, 0.350), so every `ADEQUATELY_POWERED` verdict resting on an
analytic floor errs toward saying the cell is better powered than it is. `DEFECTS.md` D-2, D-3.

**And 11 of the 15 exposed composites are exposed under an extension to the invariant that I
wrote.** The invariant as adopted speaks to permutation nulls of the candidate. Ten of the 23
screens decide with a paired cluster sign-flip, where nothing is permuted; for those I applied
*the cluster must be at least as coarse as the coarsest level any component varies at*.
**Under the narrow reading — permutation nulls only — the exposed count is 5, not 15.** Both
numbers are in `COMPOSITE_SWEEP.csv` and a reader can recompute either.

---

## ANCHORS REPRODUCED BEFORE ANY NEW STATISTIC

`scripts/run_log_s00.txt`, `run_log_s02.txt`, `run_log_s09.txt`.

| anchor | prior screen's value | reproduced here |
|---|---|---|
| D103 `out/retrospective_power.csv`, keyed `(screen, decision, family_size_K, cell)`, worst arm | 1,349 / 760 / 0.5633802816901409 | **exact to 16 digits** |
| `E1_I0041` `t_statistic` family | 666 | **666** |
| ... degenerate `mean\|t\|/sd\|t\| > 5` | 67 | **67** |
| ... `sd` exactly 0 | 6 | **6** (overlap 0) |
| ... recorded adequately powered | 35 | **35**, all in `E0_I0014` |
| `E0_I0014` `vsb`, 58 candidates, rebuilt from the frame | — | **0.000e+00** |
| `E0_I0014` `t_classical`, 348 cells | — | max rel **3.939e-15**, **276 of 348 bitwise identical** |
| `E0_I0014` `null_correct_sd`, 348 cells, from the saved draws | — | **2.220e-16** (published uses `ddof=1`) |
| `E0_I0014` `p_correct_level`, 348 cells | — | **0 mismatches** |
| `E0_I0019` null sd + p, 756 arm-cells, from its own archive | — | max abs **1.456e-03**, **0 p mismatches** |

Ten anchors, four of them at exactly 0.000e+00 or bitwise. The `ddof` check was not decoration:
it caught that `E0_I0014` publishes `ddof=1` while `E1_I0041`'s `sd_used_by_D103` is the same
number, so the two are consistent and the floors compare like for like.

---

## 1. THE 73 — MECHANISM, RESOLUTION, CORRECTED CLASSIFICATION

`BROKEN_NULLS.csv`, all 73 rows, every arm.

**"Degenerate null" was three different things and only one of them is a null problem.**

| mechanism | cells | what it is |
|---|---:|---|
| **M-VOID** | **18** | the candidate takes **exactly one distinct value per season**; `sxx` after the base is 0.000e+00 / 9.09e-27 / 4.59e-26 against **1.3876e+04** for all 55 other candidates. Observed `t` is `NaN` or ~1e-13. `s04_screen.py:215` writes 0.0 for a non-finite permuted `t`, which is where D103's `sd = 0` and its floor of *exactly 0.0* come from. |
| **M-WITHIN** | **52** | the within-block shuffle preserves each block mean **exactly** (measured max change **1.776e-15** over 475 blocks × 58 candidates), and the block-mean component alone carries a larger `\|t\|` than the assembled candidate — `pl_pts_sd5\|pts_absres`: `t_full` 25.60, `t_blockmean_only` **44.04**, `t_withindev_only` −2.47. The null contains the alternative. |
| **M-BETWEEN** | **3** | `block_index` maps the donor onto the receiver in **chronological position order** and truncates a long donor to its first `len(b)` rows, so the within-block ordinal profile survives. Measured correlation of real vs permuted within-block deviation 0.140 for `pts__pred_width`, 0.48–0.64 for the monotone counters. |

**Two hypotheses in the brief are false here, and that is a real answer.** The permutation set is
never trivially small — **1,000 distinct draws in every non-void cell**. No cell is below six
blocks: 475 player-season and 36 team-season on the full arm, 174 and 24 on the smallest.
`p_min = 2^(1−nb)` is a sign-flip identity and does not apply to a permutation null; here
`p_min = 1/(R+1)`.

**The blindness test was run before anything was condemned.** Multiplying the component the null
cannot see by ten and then deleting it changed the statistic by a **minimum of 2.303861e-02**
across all 72 `E0_I0014` broken cells, and **0 of 72** are immune. `E0_I0014`'s statistic is a
pooled `t` on the raw candidate, so the escape hatch that saved `E1_I0021` at 4.441e-16 does not
exist here. A mechanical level-mismatch rule would not have over-condemned; it would have been
right, and this is the measurement that says so.

### Resolution

| | cells |
|---|---:|
| **RE-MEASURED** under the composed-2 null | **54** |
| **PERMANENTLY UNVERIFIABLE — STRUCTURALLY VOID** | **18** |
| **PERMANENTLY UNVERIFIABLE — NO FUNCTIONING NULL ON DISK** | **1** |

The 18 are `pts__pred_sd`, `minutes__pred_sd` and `fga__pred_sd` × six dependents. They are not
merely unverifiable: **ΔR² is identically zero after the base**, so they could never have shown
an effect. The one is `E0_I0019 pl_opps_prior|brier`, and it is the most interesting single cell
in the screen — see §3.

### The repaired null

**COMPOSED-2**: a donor block drawn at random within season, then `len(b)` values resampled
uniformly from the **whole** donor block; one shared gather index per draw across all 58
candidates so max-|t| stays valid. It destroys the block-mean alignment, the within-block ordinal
alignment and the length truncation. 2,000 draws, seed 20260808, **signed and unstandardised**
draws saved for every arm in `nulls/composed2_null_*.npz`; `np.abs` appears at no storage site.

| | arm A1_FULL |
|---|---|
| cells that function (`\|mean signed t\| < 0.20` and ratio ∈ [1.10, 1.60]) | **330 of 348** |
| the 18 that do not | **exactly the 18 void cells** |
| median degeneracy ratio over the family | **1.3259** (symmetric-null value 1.32) |
| median `\|mean signed t\|` | **0.0230** |

### Corrected power classification, all 73

`corrected_classification_*` in `BROKEN_NULLS.csv`.

| D103 said | → on **A4** (2023–24 × decision stratum, **reported first**) | → on A1 (2022–24, like-for-like) |
|---|---|---|
| ADEQUATELY POWERED (35) | 17 **BLIND**, 18 PERMANENTLY UNVERIFIABLE | 17 ADEQUATELY POWERED, 18 PERMANENTLY UNVERIFIABLE |
| BLIND (38) | 33 BLIND, 4 UNVERIFIABLE-in-stratum, 1 PERMANENTLY UNVERIFIABLE | **37 ADEQUATELY POWERED**, 1 PERMANENTLY UNVERIFIABLE |

**The direction is the opposite of what "degenerate null" suggests.** D103's floor is
`((t_crit + z₈₀)·sd)²/n`. When the null's *location* collapses far from zero, its 97.5th
percentile of `|t|` runs to 8–20 instead of ~2, while its `sd` stays near 0.9 — so the published
floors for these cells are too **large**, not too small, and repairing the null makes most of
them *better* powered, not worse. The exception is the six `sd = 0` cells, whose floor of exactly
0.0 is too small by an infinite factor and which turn out to have no statistic at all.

The four UNVERIFIABLE-in-stratum cells are `pts__is_fallback` and `pts__fallback_level` on the
two minutes responses: a row with ≥8 prior appearances is never a fallback row, so the candidate
is constant inside the decision stratum. That is a property of the stratum, not a defect.

---

## 2. SURVIVORS — RANKED, NOT ESTABLISHED, AND MOSTLY NOT NEW

**Read §"THE COUNTERWEIGHT" first. Nothing in this section is an established result.** Two of the
five candidates whose Type-I I measured reject at 0.1475 and 0.5950 under my own repaired null,
so a `p < 0.05` here is only as good as the calibration of the cell it sits on, and I measured
calibration on five of fifty-four. **The list below is a ranked follow-up queue, not a finding.**

**PREREG P4 failed.** It predicted every re-measured cell would have composed-2 `p ≥ 0.05` on
A4. **37 of 54 have p < 0.05.** Under a properly built family-wise max-|t| bar on the same 348
cells, **17 of the 54 are family-wise significant on A4** and 37 on A1.

`SURVIVOR_RANKING_A4.csv` (reported first), ranked by effect size × exposure confidence, filtered
to `p_familywise < 0.05` **and** observed ΔR² ≥ D103's single-cell floor 0.00102.

| rank | cell | n | blocks | ΔR² | p_fw | Type-I flag |
|---:|---|---:|---:|---:|---:|---|
| 1 | `pts__pred_cv\|pts_absres` | 3,549 | 174 | 0.02743 | 0.0005 | **UNCALIBRATED** |
| 2 | `pl_min_rng5\|minutes_absres` | 3,549 | 174 | 0.02511 | 0.0010 | ok |
| 3 | `pl_min_sd5\|minutes_absres` | 3,549 | 174 | 0.02422 | 0.0010 | ok |
| 4 | `pts__pred_cv\|pts_sqres` | 3,549 | 174 | 0.02407 | 0.0010 | **UNCALIBRATED** |
| 5 | `pts__pred_cv\|fga_absres` | 3,549 | 174 | 0.01937 | 0.0015 | **UNCALIBRATED** |
| 6 | `pts__pred_cv\|fga_sqres` | 3,549 | 174 | 0.01854 | 0.0020 | **UNCALIBRATED** |
| 7 | `pts__pred_cv\|minutes_sqres` | 3,549 | 174 | 0.01557 | 0.0060 | **UNCALIBRATED** |
| 8 | `pl_abs_min_trend5\|minutes_absres` | 3,549 | 174 | 0.01381 | 0.0065 | ok |
| 9 | `pl_start_switch5\|minutes_absres` | 3,549 | 174 | 0.01283 | 0.0085 | ok |
| 10–17 | eight more, ΔR² 0.00815–0.01264 | | | | 0.0085–0.0455 | ok |

**After removing every cell whose candidate has a measured Type-I above 0.05 + 2 MC se: 12 of 17
on A4, and 31 of 37 on A1.** Those numbers are ceilings, not estimates — 49 of the 54 cells have
no measured Type-I at all, and among the five that do, two failed.

**Three things stop this being a lead list.**

1. **They are heteroscedasticity relationships, not point-forecast edges.** `E0_I0014`'s response
   is `|residual|` or squared residual of a forecast. D103's 0.0023 comparison bar is a ΔR² on
   D089's walk-forward **points**. Comparing them crosses responses — a D101 violation that is
   D103's own design and that `E1_I0041` already put on the record. Every classification in §1
   inherits it.
2. **Most were already significant in `E0_I0014`'s own per-cell column.** 25 of the 50 cells
   significant on A1 had a published `p_correct_level < 0.05`. What changes is the **family-wise**
   verdict: `E0_I0014` published `p_familywise_whole_screen = exactly 1.000` for **41 of the 54**,
   because its bar is an unstandardised max|t| over cells whose null widths span two orders of
   magnitude. Under a properly built bar, **33 of those flip on A1 and 17 on A4.** That is a
   verdict-level correction to a live screen and it is the largest thing this screen found.
3. **The four biggest effects on A1 are near-tautological.** `pts__is_fallback` and
   `pts__fallback_level` predict the magnitude of the minutes residual at ΔR² 0.099–0.111. A
   fallback forecast being worse is not a discovery, and those four cells vanish on the decision
   stratum because it contains no fallback rows.

**Arithmetic-ceiling kills: `E1_I0036` names 213, all in `E0_I0024_reb_ast_characterisation`.
0 of the 73 and 0 of the 15 exposed composites are among them, so 0 were found and 0 excluded.**
A ceiling kill is arithmetic and survives every methodological revision, including this one.

---

## 3. THE ONE CELL OUTSIDE `E0_I0014`, AND WHY IT IS THE CLEANEST DEMONSTRATION

`E0_I0019 pl_opps_prior|brier`, n = 17,809, observed `t` = −8.008. `_E0_I0019_ARMS.csv`, read
straight off the screen's own draw archive with no refit.

| arm | null mean signed t | sd | degeneracy ratio | published p | MDE80 per-cell |
|---|---:|---:|---:|---:|---:|
| `player_between` **(the verdict arm)** | **−5.850** | 1.167 | **5.01** | 0.0320 | 0.004643 → BLIND |
| `player_within` | **−4.372** | 0.851 | **5.14** | 0.0010 | 0.002505 → BLIND |
| `row` (naive) | **−0.032** | 0.955 | **1.368** | 0.0010 | 0.000452 → ADEQUATE |

The screen's own `grouping_levels.csv` records this candidate at
`var_share_between_primary_block = 0.093425` — **91% of it lives *within* player-season** — and
the verdict arm is a *between*-player-season relabel. **Both block-level arms are degenerate; the
only centred null on disk is the row-level one, which the screen's own inflation factor of 1.222
says is anticonservative.** So the cell is **PERMANENTLY UNVERIFIABLE — no functioning null on
disk**, and the thing that would settle it is a 2,000-draw composed null on `E0_I0019`'s own
frame, which is a refit on another screen and was not run.

**What it would probably say, stated as a bound and not adopted:** re-centring the null without
changing its width collapses the bar from 8.11 to ≈1.96·sd, and at any of the three widths on
disk (0.851–1.167) the floor lands in **[0.00032, 0.00060]** — adequately powered, from a cell
currently recorded blind at 0.004643. That is an inference, it is labelled as one, and the cell
stays UNVERIFIABLE in `BROKEN_NULLS.csv`.

---

## 4. THE COMPOSITE SWEEP — 15 EXPOSED, 14 OF THEM NEW

`COMPOSITE_SWEEP.csv`, all 540 rows.

**Population, asserted not assumed.** 38 screens exist; **23 decide cells** and the other 15
decide nothing with a permutation null (`E1_I0040`'s coverage finding, re-asserted here).
`E1_I0036/CENSUS.csv` (1,999 cells) ∪ `E1_I0040/AUDIT_TABLE_EXT.csv` (2,085) = **4,084 cells,
540 distinct (screen, candidate) pairs**.

**No name-based selection.** A candidate is classified from its **construction expression**,
located by exact-string match as an assignment target and then parsed with `ast`. 523 of 540
resolved to a site; the 17 that did not are twelve bare ΔR² values and five tier labels that are
not candidate names at all. **34 over-broad name generators were rejected before any candidate
was resolved** — one of them, `["%s_%d" % (arm, s)]` in an unrelated file, matched **351 of the
540 names** and would have been substring matching in disguise (`_GENERATORS_REJECTED.csv`).

| | pairs |
|---|---:|
| **COMPOSITE** (ratio / difference / product / sum / bundle / model spec) | **174** (32.2%) |
| ATOMIC or single-quantity aggregate | 258 |
| NOT A FEATURE (stratum, arm label, harvest artefact) | 37 |
| construction UNDETERMINABLE | 71 |

| verdict among the 174 composites | |
|---|---:|
| **EXPOSED** | **15** |
| NOT EXPOSED | **129** |
| UNDETERMINABLE | 28 |
| not applicable (declared oracle) | 2 |

### The 15, in full

| screen | candidate | why |
|---|---|---|
| `E1_I0031` | `pm_all` | **the one already known.** A cyclic shift within player-season is the identity on `pm_prev_season_imp` (max within-group spread 0.000e+00). 16 of its 32 kills discharged from disk by `E1_I0040`; 7 unresolved. |
| `E0_I0017` | `F01_dist_x_oppdist` | **measured straddle**: `A01_dist_mean` between-player-season 0.9650, `E01_opp_dist_conceded` between-opp-team-season 0.8109 |
| `E0_I0017` | `F02_lt5ft_x_opplt5ft` | 0.9458 vs 0.8281 |
| `E0_I0017` | `F03_xefg_x_oppxefg` | 0.8547 vs 0.6599 |
| `E0_I0017` | `F04_3pa_x_opp3pa` | 0.9630 vs 0.7650 |
| `E1_I0020` | `P5e_careerblend_k2/k3/k5` | `own_career` and `n_career` accumulate **across** seasons; the cluster is (season, player_id), which splits exactly that dependence |
| `E1_I0032` | `STEP4` | adds an **opponent-team-game** regressor gated by a **player**-level selector under a **player-season** cluster. increment p **0.004749** — a decided increment |
| `E1_I0032` | `STEP5` | `P01` is a team-game roster sum with the own term removed; p 0.2259 |
| `E1_I0032` | `STEP6` | `is_home` is a **team-game** column under a **player-season** cluster; p 0.3872 |
| `E1_I0032` | `STACK`, `FULL_STACK`, `PLACEBO_STACK`, `PLACEBO_FULL` | contain STEP4–6 |

**The four `E0_I0017` cells are the sharpest new finding and they were reached by measurement.**
Each is a product of a player-dominant term and an opponent-dominant term; `E0_I0017` uses
`entity_swap_null` at **one** declared entity per candidate and does not decompose
(`s02_screen.py:12-13`, `s05_finalise.py:179`). Whichever entity it picks, the other component's
variation lives inside the permuting block. The assembled products' between-opp-team-season
shares are **0.0174, 0.0292, 0.1026, 0.0204** — 90–98% of the product varies *within* the block
the swap moves.

### And a mechanical rule would have over-condemned, twice, measurably

* **`E0_I0016_efficiency_predictors` — 12 composites, 0 exposed, immune by design.** The screen
  **decomposes** every feature into an entity-season mean and a mean-free within component and
  screens each under a null valid for it (`ep_base.py:279-291`). Its own docstring makes the
  composite argument verbatim: *scheme="between" applied to a feature that varies within its
  groups "annihilates 100% of the within-group variation and yields a p that is manufactured
  rather than measured", while scheme="within" is the literal identity for a feature that is
  constant within groups.* Nobody instructed it to do this. **This is the fourth screen immune by
  design**, after `E0_I0014`'s level selection, `E0_I0015`'s measured share and `E1_I0021`'s
  within-entity estimand — and its interaction candidates are exactly the ones a mechanical rule
  condemns in `E0_I0017`.
* **`E1_I0025`'s `L2` and `L3`, and `E1_I0004`/`_v2`'s nine specs, are products spanning two
  levels and are NOT exposed.** The null permutes the *shared factor* — the defence value, the
  opponent allowance — which multiplies every tested term, so permuting it destroys the whole
  family including the interaction. **A composite is not exposed for spanning levels; it is
  exposed when a component's association survives the null.**
* **`E1_I0034` did the work itself.** Its `u*z` and `u*posmatch` are products of a team-game
  factor and a between-player-within-team-game factor; the screen measured the shares
  (`candidate_level_audit.csv`) and chose the matched within-team-game shuffle. Clean.

### Undeterminable — 28, and it went up before it went down

51 composites entered undeterminable; **23 were resolved by measuring** component variance shares
on the screens' own frozen frames (`MEASURED_COMPONENT_SHARES.csv`), the same move `E1_I0040`
used to resolve 44 of 50. The 28 that remain are named in `COMPOSITE_SWEEP.csv`. Four of them —
`E1_I0030`'s `__RECON_sum_of_parts`, `__RECON_residual`, `__RECON_within_via_minutes`,
`__RECON_within_via_ppm` — are undeterminable for a reason worth stating plainly: **they have no
null of any kind.** Three are `E1_I0034`'s `FREED_*`, the same three `E1_I0040` left open, and
they are still open for the same reason: the null's entity is `season` and the screen's measured
shares are over player and team-game.

---

## 5. DOES THE NEGATIVE RECORD SURVIVE ITS FIFTH CHALLENGE?

**On composites, yes and comfortably: 129 of 174 are clean, and three screens are immune by
design by three different mechanisms none of them was told to use.** The one previously-known
exposure remains the only *bundle* exposure in the programme. Of the 14 new ones, seven are in a
single screen (`E1_I0032`) and rest on my own extension to the invariant; four are in `E0_I0017`
and rest on measurement; three are in `E1_I0020` and turn on a cross-season accumulator.

**On the 73, no — and the failure is a power-record failure, not a lead.** D103's recorded power
for these cells is wrong in both directions, and `E0_I0014`'s family-wise verdict for 41 of them
is `p = exactly 1.000` where a properly built bar gives 33 significant. Nothing in that becomes a
betting edge: the response is forecast error magnitude, the comparison bar is on a different
response, and on the clean decision-stratum window every one of the 54 is BLIND to the
programme's best lead.

---

## 6. WHAT MOST WEAKENS THIS VERDICT

1. **My repaired null over-rejects at 0.1475 on `pts__pred_cv` and at 0.5950 on
   `pl_games_prior`** — three times and twelve times nominal. `pts__pred_cv` holds four of the
   top seven A4 survivor slots. The honest credible count on A4 is **12 of 17, and that is a
   ceiling**: 49 of the 54 cells have no measured Type-I at all. **This is the single largest
   threat to §2 and it is why §2 is a follow-up queue and not a finding.** I did not retune the
   null after seeing the ranking, and I do not know how many of the 49 unmeasured cells would
   fail the same check.
2. **My analytic floors are optimistic by 1.4–2.9× against injection** on four of five cells
   (0.739, 0.491, 0.403, 1.330, 0.350). `E1_I0041` validated the same formula at a median ratio
   of 0.989 across 96 *synthetic* conditions; on real cells it is worse. Every
   `ADEQUATELY_POWERED` verdict that rests on an analytic floor should be read as an upper bound
   on the cell's power — including the 17 of the 35 that survive on A1.
3. **Eleven of the fifteen exposed composites rest on an extension I wrote.** Under the invariant
   as adopted — permutation nulls only — the count is **5**: `pm_all` and the four `E0_I0017`
   products. The disagreement is preserved in the file, not resolved by assertion.
4. **My own first repaired null was defective** in the same shape as the defect it was repairing,
   and it is preserved (`_REMEASURE_ALL_ARMS.csv`, `nulls/composed_null_*.npz`). It passed only
   28 of 72 cells where composed-2 passes 54 of 54. The pre-committed functioning test caught it.
5. **The 0.50 straddle threshold is `E1_I0038`'s and was not retuned.** `E0_I0017`'s four
   exposures are not marginal to it (0.66–0.83 opponent-side, 0.85–0.96 player-side), but
   `C05_assisted_trend` at 0.5575 sits close and its verdict would move at 0.60.
6. **`E1_I0034`'s three `FREED_*` cells and `E1_I0030`'s four null-less accounting terms remain
   undeterminable**, and the second group is undeterminable because the quantities were published
   without a null at all. If a coordinator counts a published quantity with no null as exposed by
   default, the exposed count is **19**, not 15.
7. **PREREG P3 failed on the arm it was stated for.** I predicted at most 5 of the 35 would remain
   adequately powered on A1 and 17 do. It holds only on A4, which is not the arm the prediction
   named.
