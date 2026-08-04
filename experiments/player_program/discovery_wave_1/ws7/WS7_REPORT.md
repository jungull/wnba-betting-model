# ws7_nonlinear_heterogeneous — result: **NULL, and on the decision metric REFUTED**

DISCOVERY lane. Development folds only. Nothing here is promotion evidence, nothing here
replaces Arm D, and nothing was appended to `arm_registry.jsonl`.

Sign convention throughout: **INCUMBENT minus CHALLENGER absolute error. POSITIVE = challenger
is better.** Intervals are 90% game-clustered bootstrap CIs.

Headline results are the **v2 leakage-free rebuild** (`WS7_RESULTS.json`). The contaminated
first pass is preserved in full at `WS7_RESULTS_v1_leaky.json` and reported alongside.

## What was asked

Whether role and involvement effects were being hidden by **linear pooling** — the prior linear
main-effect arms having come back null or negative against the frozen incumbent Arm D
(operational team MAE 2.9675).

## Variants tested: 7

Preregistered and frozen in `PREREGISTRATION.json` at commit `58b3a91`, which deliberately
contains no results. All seven have ≤ 4 free parameters; no unrestricted player-specific slopes
were fitted. Every knot, tier boundary and standardisation statistic is recomputed **inside each
chronological training fold** — the per-fold knot values in `gate/GATE_*.json` do move fold to
fold, which is the audit trail proving nothing was read off the full history.

Three arms are **baselines, not candidates**, and do not enter the multiplicity count:
`L_involvement` and `L_priorrole` (reproductions of P2 arms G and F), and `K0_intercept_only`.

## Two defects found in the shared inputs

**Defect 1 — free-intercept recalibration** (coordinator amendment 1, confirmed independently).
Every Poisson-ridge arm carries an unpenalised intercept that the *unfitted* Arm D does not.
`K0_intercept_only` — zero features, identical pipeline, offset and folds — reaches operational
team MAE **2.9642** against Arm D's 2.9675, reproducing the externally measured 2.96419. A free
+0.00326, which is the same order as every effect this wave is hunting.

**Defect 2 — `did_appear` leakage in the P2 prior-role columns** (coordinator amendment 2,
confirmed). `trailing_minutes_share`, `role_change`, `trailing_rotation_rank` and
`offensive_involvement_proxy` in `turnover_p2_v1/turnover_role_context_features_v1.parquet` are
built by iterating the realised box score and left-merging onto the candidate universe. Their
null pattern is an *exact* `did_appear` indicator — null 8,278 = the non-appearers, non-null
27,351 = the appearers, zero off-diagonal (`TRAILING_REBUILD_RECEIPT.json`). My first pass
standardised then `fillna`'d, which encoded that post-cutoff outcome into the design as a
constant column value for exactly the non-appearers.

I had seen the crosstab and misdiagnosed it as a downstream candidate-precision artifact rather
than as contamination of my own design matrix. The coordinator was right.

**Repair** (`build_trailing_v2.py`): the same EWMA machine, α = 0.10, strictly prior games, but
state is **read for every Tier A candidate** on every candidate date, not only for players who
turned out to appear. State is still *updated* only from realised box scores, which are prior
games by the time they are read. Result: non-null on all 35,629 operational rows, and "no prior
history" falls from 8,278 rows (0 of which appeared) to 473 (71 of which appeared) — it is no
longer an appearance indicator. The canonical artifact was not modified.

A leakage check was added per the amendment: any feature whose null pattern coincides with
`did_appear` is blocking. It fires on **45 of 100** fold-audits under v1 at agreement exactly
1.000, and **0 of 100** under v2. It runs on the operational prediction frame, because the
intrinsic training frame contains only appearers and cannot reveal the defect.

## The result

| arm | team MAE (v2) | vs Arm D (v1 leaky) | vs Arm D (v2) | **vs K0 (v2)** |
|---|---|---|---|---|
| D (frozen incumbent) | 2.9675 | — | — | — |
| **K0_intercept_only** | **2.9642** | +0.00326 | +0.00326 [−0.00014, +0.00672] | — |
| W1_pw_involvement | 2.9698 | −0.00244 | −0.00238 [−0.00693, +0.00191] | −0.00564 [−0.00822, −0.00316] |
| W2_rcs_involvement | 2.9723 | −0.00463 | −0.00489 [−0.00964, −0.00029] | −0.00815 [−0.01111, −0.00532] |
| W3_expansion_contraction | 2.9652 | +0.00251 | **+0.00221** [−0.00569, +0.01019] | −0.00105 [−0.00718, +0.00479] |
| W3b_priorrole_asym | 2.9704 | −0.00111 | −0.00299 [−0.01139, +0.00480] | −0.00624 [−0.01418, +0.00043] |
| W4_inv_x_minutes | 2.9690 | −0.00176 | −0.00159 [−0.00736, +0.00409] | −0.00485 [−0.00860, −0.00135] |
| W5_inv_x_support | 2.9732 | −0.00547 | −0.00572 [−0.01120, −0.00047] | −0.00898 [−0.01295, −0.00544] |
| W6_partial_pool_tier | 2.9718 | −0.00385 | −0.00435 [−0.01006, +0.00095] | −0.00761 [−0.01196, −0.00384] |
| L_involvement (=P2 arm G) | 2.9727 | −0.00506 | −0.00522 | −0.00848 [−0.01166, −0.00551] |
| L_priorrole (=P2 arm F) | 2.9702 | −0.00057 | −0.00279 | −0.00605 [−0.00944, −0.00291] |

**Zero of seven variants beat Arm D. Zero beat K0.** Five are significantly *worse* than fitting
no features at all. The one variant with a positive point estimate against D,
`W3_expansion_contraction` (+0.00221, CI spanning zero), goes to **−0.00105 against K0** — its
entire apparent gain, and a little more, was the free intercept.

The leakage repair moved the arms that lean hardest on the affected columns:
`L_priorrole` −0.00057 → −0.00279 and `W3b` −0.00111 → −0.00299. The leakage had been
*flattering* the prior-role arms. Nothing about the verdict changed.

Reproduction controls under v1 matched `TURNOVER_P2_RESULTS.json` to five decimals
(−0.00506 / −0.00057), confirming the harness before the repair moved them.

## Where the effect is concentrated

Against K0, at player-row level, so only the functional form is credited. `appr` = fraction of
the stratum that actually appeared.

| stratum | n | appr | W1 | W4 | W6 | L_involvement (linear) |
|---|---|---|---|---|---|---|
| primary_creator | 7,772 | 0.88 | **−0.00204\*** | −0.00179\* | −0.00315\* | −0.00245\* |
| secondary_expanded | 1,167 | 0.93 | **+0.00517\*** | +0.00052 | +0.00329\* | +0.00295\* |
| role_expansion | 4,526 | 0.72 | +0.00298\* | +0.00565\* | +0.00571\* | +0.00585\* |
| abrupt_change | 6,683 | 0.50 | +0.00063\* | +0.00138\* | +0.00250\* | +0.00246\* |
| low_usage | 12,083 | 0.62 | +0.00214\* | +0.00539\* | +0.00406\* | +0.00443\* |
| stable_role | 28,946 | 0.83 | +0.00140\* | +0.00193\* | +0.00132\* | +0.00138\* |

\* CI excludes zero.

- **Primary creators: refuted, and more sharply than before.** The preregistered expectation was
  that the effect would concentrate there. After the repair every arm is significantly
  *negative* in that stratum. (Under v1 it read ≈ 0; the leakage was masking a real loss.)
- **Secondary creators receiving expanded roles: the one genuine positive.** W1 +0.00517, and
  this is the cleanest stratum in the table — 93% of it appeared, so it is not an appearance
  artifact. But the *linear* arm already captures +0.00295 of it, so nonlinearity buys an
  increment, not a new phenomenon. And it does not survive aggregation to team level.
- **The large gains track non-appearance, not role.** `low_usage` (+0.00539) and `abrupt_change`
  are the strata with the *lowest* appearance rates (0.62, 0.50). Under v1 this was flagrant: the
  `no_prior_history` stratum held 8,278 rows, 0 of which appeared, and showed the biggest gains
  of all. Under v2 that stratum is **empty** — proof it was an artifact of the leaky nulls — but
  its rows have redistributed into `low_usage`, which now carries 38% non-appearers. Gains that
  concentrate where players do not appear are candidate-precision, not role effects.
- **Caveat on the frozen thresholds.** The stratum cuts were frozen against the v1 distribution.
  The repaired `role_change` is differently distributed, so the same absolute thresholds now
  partition differently (`has_abrupt_change` team-games 1,339 → 2,368). I have **not** retuned
  them — that would be the post-hoc tuning the preregistration exists to prevent — but the
  stratum sizes are not comparable across v1 and v2 and should not be read as such.

## Why player-level gains do not survive team aggregation

Every arm *improves* player-row MAE (0.8479 → ~0.8453) and Poisson deviance while *worsening*
team MAE. From `WS7_ADDENDUM.json` (v2, signed team error):

| arm | overall | abrupt-change games | stable games |
|---|---|---|---|
| D | +0.0804 | +0.0009 | **+0.4254** |
| K0 (no features) | −0.0092 | −0.0847 | +0.3184 |
| W6_partial_pool_tier | −0.0105 | −0.0896 | +0.3322 |

Arm D is essentially unbiased on abrupt-change team-games and over-predicts stable ones by
+0.43. The correction needed is stratum-specific. What every arm applies — **including K0, which
has no features** — is a broadly *uniform downward shift*: it helps the over-predicted stable
games but pushes the already-unbiased abrupt games into under-prediction. Against K0,
`has_abrupt_change` is negative for six of seven variants with CIs excluding zero.

So the features are not supplying a role-specific correction with the right sign. They act as a
near-global scale adjustment that K0 supplies more cheaply. Under MAE on a low-count,
right-skewed target, shifting mass downward reduces per-row absolute error; but team totals
require the *sum* to be right, and within a team-game those shifts are correlated and do not
cancel.

## The ledger's own falsification test

The card falsifies on "linear and nonlinear indistinguishable". Strictly they are not always
indistinguishable: at team level `W1_pw_involvement` beats `L_involvement` by +0.00284
[+0.00045, +0.00550] and `W4_inv_x_minutes` by +0.00363 [+0.00092, +0.00619]. Linear pooling
*was* costing something.

This rescues nothing. Both remain below Arm D and significantly below K0. The honest statement:
**the involvement features damage team-level accuracy, and the nonlinear forms damage it less
than the linear form does** — recovering part of a loss they should not have been creating,
never opening a gain.

## Multiplicity

7 variants against one primary metric, 90% CIs, no correction applied (~0.35 false positives per
tail expected). Zero variants positive against K0; the single nominal positive against D has a CI
spanning zero and inverts once the free intercept is controlled. **There is no positive here
requiring a multiplicity defence.**

## Gate

`feature_gate.audit()` ran **before every fit**: 10 arms × 5 fitted folds × 2 tracks = 100
audits per mode, 0 blocked under v2, 0 non-blocking findings. Receipts in `gate/` (v2) and
`gate_v1_leaky/`. The self-test confirms the gate still blocks
`proj_minutes_share`/`proj_off_poss_share` at corr = 1.0; no arm includes both — `W4` uses
`proj_minutes_share` alone. The added `did_appear` leakage check: 45/100 blocking under v1,
0/100 under v2.

## Verdict

**NULL on the hypothesis; REFUTED on the operational decision metric.** No bounded nonlinear or
heterogeneous formulation of role or involvement beats the frozen incumbent, and none beats a
zero-feature recalibration. The preregistered claim that the effect concentrates among primary
creators is refuted outright — those players are where the arms do the most damage. A real but
small player-level effect exists among secondary creators receiving expanded roles (+0.00517,
93% appearance rate, the one clean positive); it does not survive team aggregation.

**Recommendation:** carry no ws7 form forward. The two findings worth more than another
functional form are both defects in shared inputs, and both are now demonstrated rather than
asserted:

1. **`K0` must become a standing baseline for this channel.** Every arm in this programme
   evaluated against unfitted Arm D has been receiving a free +0.0033.
2. **The P2 prior-role columns are unusable on the operational track as built.** Any operational
   result that consumed them with null-imputation should be re-checked; `build_trailing_v2.py`
   is a drop-in rebuild. The `did_appear` null-pattern test belongs in the permanent gate.

Two substantive leads remain, neither about nonlinearity: Arm D's +0.43 over-prediction on
stable team-games against near-zero bias on abrupt ones, and the 8,278 non-appearing Tier A
candidates carrying a mean 15.1 possessions of projected exposure.
