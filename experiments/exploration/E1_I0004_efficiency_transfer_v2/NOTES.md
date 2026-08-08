# E1_I0004_efficiency_transfer_v2 — NOTES

**Verdict: KILL.** The centred opponent zone-conversion-allowance signal does **not** improve a
point-in-time forecast of player efficiency, on the decision-relevant stratum or off it, and the
channel is closed on **arithmetic** rather than on power.

This is a **retry**. The first attempt, `experiments/exploration/E1_I0004_efficiency_transfer/`,
was killed mid-run by an API error (GRAPH_POLICY §12: infrastructure event, not a finding). Its
`et_base.py` and `s00`–`s04` scripts were read **as scaffolding**; no number, contrast, p-value or
verdict from it is reused. Every contrast here is rebuilt with the centring corrected.

---

## 1. Headline

| | dR2 (candidate − champion) | cluster p | n |
|---|---|---|---|
| **Per-minute efficiency, ON the decision-relevant stratum** | **−0.000556** | **0.2535** | 5,086 |
| Per-minute efficiency, OFF the stratum | −0.000639 | 0.2563 | 6,181 |
| Per-minute efficiency, all rows | −0.000583 | 0.1290 | 11,267 |
| Points, ON the stratum | −0.000288 | 0.4763 | 5,086 |

Cluster p is `screenkit.paired_forecast_comparison` with a whole-cluster sign-flip null at
**opponent-team-season** (36 clusters). Spec: D074's frozen slope +0.3731536 applied to the
**Restricted Area only** — the cell that actually survived D074's five-way multiplicity.

**The arithmetic ceiling.** One sd of the centred signal moves the points forecast by **0.0859
points** against a **7.5505-point** response sd. Even as a perfect, orthogonal predictor:
**dR2 ≤ 0.000129**. D079 killed the shot-mix channel at dR2 ≤ 0.001127. **This channel's ceiling
is 8.7× smaller than the one that already killed shot mix.** Rescaled with hindsight (oracle,
diagnostic only) it is dR2 ≤ 0.000039.

---

## 2. What I centred, and how

**The quantity.** `OC_z` = the opponent's conversion rate allowed **in zone z** over its strictly
prior same-season games, **minus** the **pooled** rate it allowed over those same prior games.
This is D074's O2 construction, reproduced value-for-value from the raw shot files (max abs diff
vs the frozen `O2` column: **0.000e+00**).

**The defect.** Because `OC_z` is a zone-minus-pooled difference, it inherits a large
**zone-specific common level**: restricted-area shots convert far above the pooled average, so
`OC_RA` has a league-wide mean of **+0.1886** against a cross-sectional sd of **0.0380** — a mean
**5.0× its own sd**. In D074's **regression with an intercept** that level is absorbed and
irrelevant. In an **additive forecast adjustment** it is not: it adds essentially the same number
to every row. That is a **level shift, not a cross-sectional signal**, and it is what the
predecessor died reporting.

**The correction.**

```
OCc_z(opponent, season, game) = OC_z − lg_prior_gap_z(season, calendar date)
```

where `lg_prior_gap_z` is the **league's own** zone-minus-pooled conversion gap computed over
**all league games on strictly earlier calendar dates in the same season** (cumulative sums minus
the current date's own contribution). It is **not back-filled** — back-filling the first dates
from later ones would read forward, which is the trap-2 signature.

**Why this is the right anchor.** `lg_prior_gap_z` is a **date-indexed scalar shared by every
opponent**. Subtracting it therefore leaves the cross-sectional ordering of opponents on any given
date **exactly unchanged** while removing the additive level. This is D080's distinction: a
scalar shared by all teams is harmless cross-sectionally and *not* harmless for a level claim, and
this screen makes a level claim (it adds the term to a forecast). Unlike `pressure_lib.py`'s
`*_pregame` columns, this anchor is built only from games **strictly before** the date, so it is
legitimate for the level claim too.

Per-zone effect of the centring:

| zone | mean OC | sd OC | mean lg_gap | mean OCc | sd OCc | corr(OC, OCc) |
|---|---|---|---|---|---|---|
| Restricted Area | +0.1886 | 0.0380 | +0.1863 | +0.0023 | 0.0379 | 0.989 |
| In The Paint (Non-RA) | −0.0473 | 0.0339 | −0.0468 | −0.0005 | 0.0335 | 0.987 |
| Mid-Range | −0.0695 | 0.0340 | −0.0688 | −0.0007 | 0.0333 | 0.977 |
| Corner 3 | −0.0753 | 0.0590 | −0.0763 | +0.0010 | 0.0560 | 0.947 |
| Above the Break 3 | −0.0961 | 0.0285 | −0.0954 | −0.0006 | 0.0278 | 0.976 |

The mean goes to ~0 and the sd is essentially preserved: **the level is removed, the signal is
kept.** `corr < 1` confirms the centring is not the identity.

**Measured damage of not centring** (this is why the abandoned directory's artifacts must not be
read): on the decision-relevant stratum the **uncentred** per-minute dR2 is **−0.009234** against
the centred **−0.000556** — about **16× more damaging** — and on points it is **−0.008063 at
cluster p = 0.0042**. Two-sided, that reads as "significant". It is significant *in the wrong
direction*, and it is entirely an artefact of the uncorrected level. A reader of the abandoned
`FINDINGS.json` is reading that artefact.

A second centring (within-slate cross-sectional demean, `OCc_xs`) was also built and gives the
same verdict. It is secondary because it depends on who else played that night.

---

## 3. TIME-WINDOW TABLE — read the construction, not the label

| quantity | column | window actually read | realised info? |
|---|---|---|---|
| champion points/minutes/FGA forecasts | `pts__pred_point`, `minutes__pred_point`, `fga__pred_point` | whatever the frozen season-chronological walk-forward champion saw; **nothing refitted** | no |
| champion implied efficiency | `mdl_ppm`, `mdl_ppf`, `mdl_fpm` | ratios of the above; nothing new fitted | no |
| opponent zone allowance | `OC_z` | the **opponent's own** games with `game_date` strictly earlier in the same season (cumsum **minus** the current game) | no |
| **centring anchor** | `lg_prior_gap_z` | **all league games** on strictly earlier **calendar dates** in the same season (cumsum minus the current date). Not back-filled. | no |
| **centred allowance** | `OCc_z` | both of the above | no |
| player prior zone mix | `w_z` | the **player's own** games strictly earlier in the same season (cumsum minus the current game); NaN below 20 prior FGA | no |
| opponent identity | `opp_team_id` | the two team ids appearing in the game — a **schedule fact, known pre-game** | no |
| point-in-time references | `ref_pts`, `refA_ppm`, `refB_ppm`, `refA_ppf`, `refB_ppf` | D081's frozen constructions: `.shift(1)` **before** `.expanding()` inside (season, player), with a same-season expanding league-mean cold fallback | no |
| responses | `y_pts`, `y_minutes`, `y_fga`, `r_ppm`, `r_ppf` | the realised game — **response only** | yes, as response |
| ORACLE ceiling | `DIAGNOSTIC_ORACLE_best_scaling_dR2` | **uses the realised response.** An upper bound, loudly labelled, excluded from every headline | **yes — diagnostic only** |
| direction diagnostic | `DIAGNOSTIC_corr_resid_vs_move` | **uses the realised response.** Descriptive, excluded from every headline | **yes — diagnostic only** |

**Retrospective-baseline traps avoided by construction.** No `player_tendency_loo`. No
leave-one-SEASON-out zone rates. No leave-one-game-out full-season team rates (D074's own O1 form
is *not* used here — only its corrected prior-only O2 form). No `*_pregame` column from
`pressure_lib.py` is read at all, so D080's shrink-toward-current-season-league-mean hazard does
not arise. `data/zone_maps/*` is never opened; zones come from the raw per-shot `SHOT_ZONE_BASIC`
label.

---

## 4. Partition

2021–2024 only; champion-forecast work is 2022–2024 (D076: the 2021 fold is degenerate,
`n_train_rows=0`, `model_was_fitted=false`). `shots_2025_*.parquet` and
`shots_2026_regular.parquet` exist in `data/shotcharts/` and were **never constructed as a path**.
`screenkit.assert_partition` — a **value** test on parsed dates and season-valued columns — is run
on every frame at every stage and passes. **No byte or regex scan is used as a partition check
anywhere**, per the three prior false-hit incidents.

---

## 5. Inference hygiene

`screenkit.detect_grouping_level` was run rather than assumed:

* `RA_OCc` (the centred allowance on the analysis rows) is **constant at
  `opponent_team_season_game`** (1,466 groups) and **not** constant within opponent-team-season —
  it evolves through a season as the opponent accumulates games.
* `var_share_between(RA_OCc, opponent_team_season) = 0.6815` — **68.2% of the variance is between
  opponent-team-seasons**, which is where the signal lives.
* The **assembled** signal `S` varies row by row, because the player mix `w_z` does. The kit
  correctly returned `recommended_permutation_level = None` with
  `status = NO_COARSER_LEVEL_EXISTS__ROW_NULL_IS_ANTICONSERVATIVE` rather than the old `"row"`
  sentinel — the P2 fix working as intended.

**Headline cluster level: opponent-team-season (36 clusters)** — the coarsest level the signal's
variance actually lives at, and the conservative choice. Three finer levels are reported beside it.

**Row-level null inflation: 1.53× (on stratum), 1.76× (off), 1.83× (all rows).** This matters
here in an unusual way: several **row-level** p values look "significant" (e.g. 0.0056 on all
rows) **for a NEGATIVE dR2**. Reading them as support would have been backwards twice over — wrong
level *and* wrong sign. Cluster-robust SEs are **not** used as a substitute anywhere.

**Placebos** (`s03b_placebo.py`):

* **P1, literal identity** — `noop_placebo` observed **sd = 0.000000e+00**, `is_noop = True`.
  Exactly as it must be; this is a harness check, not evidence about the signal.
* **P2, permute-the-key-and-rebuild** — observed sd 2.57e-05, i.e. ~5% of the real null's width.
  Not flagged a formal no-op (the group-mean step shrinks rows toward a random group mean rather
  than returning them verbatim), but it is a **degenerate** control and carries no p-value here.
* **P3, the real control** — whole opponent-team-seasons' allowance values reassigned between
  opponents, 2,000 draws: **null sd 5.29e-04, null median −1.97e-04**, real dR2 **−0.000556**,
  two-sided **p = 0.3418**. The real contrast sits comfortably inside the null. The centred
  transfer is **indistinguishable from a randomly reassigned opponent's allowance.**

---

## 6. Why this is not D079 repeated

D079 killed the **shot-mix** channel on the argument that mix **reallocates attempts at constant
volume**, which caps what it can move. That argument genuinely does **not** apply to conversion —
converting better is not reallocating — and that is why this screen was worth running. The
conversion channel needed its **own** ceiling calculation, and it got one. The ceiling turns out
to be **smaller**, for a different reason:

```
1 sd of centred RA allowance      0.0324
× D074 transfer slope             0.3732
× points per rim make             2
× player's prior rim share        0.290
= 0.00703 points PER ATTEMPT
× typical FGA forecast            11.11
= 0.0781 points per game      (measured: 0.0859)
÷ points response sd              7.55
= 1.03% of a response sd
```

The mechanism is not arithmetically constrained the way mix is. It simply has a **tiny lever**:
the cross-sectional spread in opponent rim-conversion allowance is small, and it reaches player
points only through a ~29% rim share of attempts and a 0.373 transfer slope.

**The failure is not a mis-scaled coefficient.** The oracle bound — the best any rescaling could
do, chosen with hindsight on these very rows — is **dR2 ≤ 0.000039** on the stratum. And the
direction diagnostic `corr(residual, forecast movement)` is **−0.0074** on the stratum: once
aggregated from shot-zone conversion rate to player-game points, the residual correlation with the
transferred adjustment is slightly **negative**. The mechanism does not survive aggregation.

---

## 7. Reproduction (Step 1)

| anchor | target | reproduced | abs delta |
|---|---|---|---|
| D074 conversion slope | +0.3731535713 | +0.3731535713 | **0.000e+00** |
| D074 n | 30,764 | 30,764 | 0 |
| D074 opponent construction rebuilt from raw shots vs frozen `O2` | — | — | **0.000e+00** (0 NaN) |
| D074 five-zone family (5 zones × 3 stats) | published 4-dp table | — | **4.99e-05** |
| D081 stratum n | 5,107 | 5,107 | 0 |
| D081 stratum points skill | −0.0035882639 | −0.0035882639 | **0.000e+00** |
| D081 stratum block-sign-flip p | 0.2663668166 | 0.2663668166 | **0.000e+00** |
| D081 stratum minutes skill | +0.0614326711 | +0.0614326711 | **0.000e+00** |
| D081 stratum rate-ppm skill | −0.0019721319 | −0.0019721319 | **0.000e+00** |

**One clarification, not a discrepancy.** The task brief quoted D081's minutes skill as **+7.7%**.
The frozen `decomp_frame` value **on the decision-relevant stratum** (≥8 prior appearances AND
trailing-5 minutes ≥24, n=5,107) is **+6.143%**, which is what reproduced at 0.000e+00. Tracked
back to D081's own `NOTES.md`: **+7.69%** is the minutes skill on the **≥20 prior appearances ×
≥24 minutes** cell (n=3,087) of its depth × volume grid — a *tighter* cell inside the stratum, not
the stratum itself. Different row set; the conclusion ("minutes skill is good there and buys
nothing") is identical on both.

Also worth recording for anyone citing the ceiling: the brief's **5.82-point response sd** is
D079's **FG-points** response on the `shot_selection` frame. The response here is **total points**
on `decomp_frame`, sd **7.55**. Both denominators are in `arithmetic_ceiling.csv`; the headline
uses **7.55**, the larger denominator, which yields the **smaller and more damning** ceiling.

---

## 8. Screen-kit feedback

**No kit defects found.** Everything used behaved as documented.

Three positive confirmations worth recording:

1. `r2_of_forecast` vs `r2_plain` — the naming hazard the kit warns about is real and the fix
   works. Every forecast here is scored with `r2_of_forecast`; nothing was refit.
2. `detect_grouping_level`'s **P2 fix** did exactly its job: for the assembled signal it returned
   `recommended_permutation_level = None` with
   `status = NO_COARSER_LEVEL_EXISTS__ROW_NULL_IS_ANTICONSERVATIVE` and a long warning, instead of
   silently handing back `"row"`. Piping it into `permutation_null` would have refused. This is
   the intended behaviour and it changed how the cluster level was chosen here.
3. `paired_forecast_comparison` is the right shape for this question and its automatic
   `p_row_level_NAIVE` + `inflation` reporting is what surfaced the 1.53–1.83× inflation without
   any extra work.

**One usage note, not a defect.** `detect_grouping_level`'s `candidate_keys` must be a **dict**
`{name: [cols]}`; passing a list of column-lists raises `AttributeError: 'list' object has no
attribute 'items'` rather than a typed error. Harmless — it fails loudly and immediately — but a
`TypeError` with the expected shape would be friendlier. Recorded, not escalated.

---

## 9. Self-reported defect in my own construction

Found and written to disk immediately rather than held for the final message.

The **first pass** of `s03` section 3.5 ran `noop_placebo` twice: once on the literal identity and
once on a transform I labelled "relabel the key and recompute". That second transform was written
as `(S − mu + mu)`, which is **algebraically S** — the identity wearing a different name. Its
`is_noop = True` therefore proved nothing at all about the relabel-and-recompute pattern it
claimed to test. It was replaced by `s03b_placebo.py`, which runs a genuine
permute-key-and-rebuild transform (P2) and a genuine between-opponent reassignment null (P3).

**No published number is affected**: the placebo never entered any contrast. But the failure mode
is worth recording, because it is the *same* failure mode `noop_placebo` exists to catch — a
control that looks like a control and is the identity — and I wrote one by accident while using
the tool designed to detect it.

---

## 10. Cheating disclosure

**Where I could have cheated, and what I did instead.**

* **Spec choice.** Three transfer specs (RA-only, all-five-global, all-five-per-zone) × three
  centrings (league-centred, uncentred, cross-sectionally demeaned) × two efficiency responses ×
  three strata = **54 cells**. Picking the best would be spec-shopping. `SPEC_RA` on
  points-per-minute was **declared primary in `s01`'s printed output before any contrast was
  computed**, on the stated ground that RA is the cell that survived D074's multiplicity. **The
  full 54-cell table is published** in `efficiency_contrast.csv`, and **§10a below chases the best
  cells in it to ground** rather than asserting they do not matter.
* **Cluster level.** Four levels were run. The **coarsest** (opponent-team-season, 36 clusters) is
  the headline. Finer levels give *smaller* p — for a *negative* dR2 — so the coarse choice is
  conservative for a KILL and would have been the cheat had the sign been positive.
* **Ceiling framing.** The ceiling could have been quoted against D079's 5.82 FG-points sd to make
  it look larger. Both denominators are in `arithmetic_ceiling.csv`; the headline uses this
  frame's own 7.55 total-points sd — the larger denominator, hence the smaller ceiling.
* **Preselected specifications: YES** for the primary cell, **NO** for the secondary specs, which
  are exploratory and labelled as such. **Nothing was computed and then dropped.**
* **Nothing was reused from the abandoned run.**

---

## 10a. The best cells in the 54-cell table, chased to ground (`s06_ppf_ceiling_check.py`)

Four cells in the table have a **positive** centred dR2, and all four are on the **secondary**
response, points-per-FGA, on the stratum. Honesty requires reporting what happens to them:

| spec | ppf dR2 on stratum | ppf cluster p | its own ceiling | **points** dR2 | **points** cluster p |
|---|---|---|---|---|---|
| ALL5_PERZONE_XSCENTRED | +0.000817 | 0.307 | 0.000336 | **+0.000019** | 0.966 |
| RA_XSCENTRED | +0.000747 | 0.277 | 0.000258 | **−0.000054** | 0.883 |
| ALL5_PERZONE | +0.000691 | 0.399 | 0.000371 | **−0.000185** | 0.691 |
| RA (primary) | +0.000601 | 0.397 | 0.000284 | **−0.000288** | 0.476 |

Three things, stated plainly:

1. **Each of these positive dR2 values exceeds its own "perfect orthogonal predictor" ceiling.**
   That is not a signal beating a bound — the ceiling is exact only for a predictor orthogonal to
   the baseline's error, and ordinary sampling variation can overshoot it. A dR2 sitting *above*
   the ceiling for a term this small is a **symptom of noise**, not of strength.
2. **None is significant at the cluster level** (p 0.277–0.399).
3. **The response itself is weak.** The points-per-FGA baseline has a **negative** R2 (−0.0126 on
   the stratum) — the champion's implied points-per-attempt is worse than a constant. A positive
   dR2 against a baseline already worse than the mean is a low bar.

And decisively: **every one of them vanishes or reverses when propagated to points**, the response
the program actually cares about — the largest becomes +0.000019 at p = 0.966. Nothing survives
the propagation. Full numbers in `ppf_ceiling.csv` and `ppf_positive_cells_propagation.csv`.

---

## 11. Provenance status

`screenkit.check_manifest` on all six inputs (`decomp_frame.parquet`, `repro_ra_common.parquet`,
`conversion_frame.parquet`, and the three raw `shots_20XX_regular.parquet`) returns
**UNVERIFIABLE — no sibling manifest**. That is explicitly **not a pass** and it travels with this
verdict. It does not weaken a KILL: an unverifiable input cannot manufacture a *ceiling* that is
8.7× below an already-fatal one.

---

## 12. What this kills and what it does not

**KILLED.** The transfer of D074's opponent zone-conversion-allowance signal into the champion's
per-minute or per-attempt **efficiency** forecast, and thence into points. Killed on the
decision-relevant stratum and off it, and killed on **arithmetic** — which is a complete answer
and closes the lead.

**NOT touched.** D074's own finding stands and reproduced at 0.000e+00. The signal is real at the
shot-zone conversion level. It is simply far too small a lever on player-game points. Nothing here
says the **efficiency step** is unfixable — it says this particular basketball-specific candidate
is not the fix, and D081's finding that generic pre-game state is dead is unchanged. Whatever
closes the efficiency gap will have to move the points forecast by considerably more than 1% of a
response sd.

---

## 13. Files

| file | what |
|---|---|
| `etv2_base.py` | loader, the centring, prior-only constructions, scoring helpers |
| `s00_inspect.py` / `run_log_s00.txt` | schema and join-key inspection |
| `s01_reproduce.py` / `run_log_s01.txt` / `_s01.json` | both anchors + the centring-level table |
| `s02_build.py` / `run_log_s02.txt` / `_s02.json` | centred frame, signal specs, coverage, grouping level |
| `s03_contrast.py` / `run_log_s03.txt` / `_s03.json` | the 54-cell efficiency contrast |
| `s03b_placebo.py` / `run_log_s03b.txt` / `_s03b.json` | corrected placebos and the real null |
| `s04_points_and_ceiling.py` / `run_log_s04.txt` / `_s04.json` | points propagation and the ceiling |
| `s05_findings.py` / `run_log_s05.txt` | assembles `FINDINGS.json` |
| `eff_frame_v2.parquet` | the built contrast frame (13,879 × 70) |
| `efficiency_contrast.csv` | all 54 cells |
| `points_contrast.csv`, `arithmetic_ceiling.csv`, `efficiency_ceiling.csv` | step 4 |
| `centring_report.csv`, `centring_level_table.csv`, `coverage.csv` | the centring and coverage |
| `permutation_draws_paired_cluster.csv` | 5,000 sign-flip draws × 3 primary cells |
| `placebo_draws_opponent_reassign.csv` | 2,000 between-opponent reassignment draws |
| `FINDINGS.json` | the machine-readable finding |
