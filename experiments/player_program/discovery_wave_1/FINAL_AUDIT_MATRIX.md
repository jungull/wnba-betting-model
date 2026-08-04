# Discovery wave 1 — final audit matrix

Derived from `RETROSPECTIVE_GATE_AUDIT.json` and `HYPOTHESIS_LEDGER.json`.
The end-of-wave ranking is derived from THIS matrix, not transcribed from the handoff.

## Gate governance

The strengthened feature gate did NOT govern discovery wave 1. All eight result commits carry the pre-fix blob a8a8ea6416c9613302209a4c71008ef9927d6f82; neither 55f4500 nor 42af2cd is an ancestor of any of them. Every classification on the feature-design axis is a RETROSPECTIVE application of the current gate, not a record of what ran.

## What this matrix refuses to collapse

* a valid null is NOT a failure of integrity
* a diagnostic is NOT a challenger
* a fitted coefficient is NOT a forecast gain
* a post-hoc audit is NOT proof that the current gate governed the original execution

## Matrix

| WS | prereg | original | corrected | gate blob | feature-design integrity | comparison parity | decision validity | role |
|---|---|---|---|---|---|---|---|---|
| ws1 | — | 3726991 | 5313ebd | a8a8ea6 | `manual_equivalent_checks_documented` | `k0_matched_control_present` | `valid_only_after_corrected_rerun` | hypothesis_generating |
| ws2 | 8116b7d | 863a900 | — | a8a8ea6 | `posthoc_current_gate_pass` | `k0_present_via_companion_script` | `invalid` | hypothesis_generating |
| ws3 | — | 1e3509f | — | a8a8ea6 | `manual_equivalent_checks_documented` | `k0_matched_control_present` | `valid_as_published` | diagnostic |
| ws4 | a6d5cd4 | 1b634fb | — | a8a8ea6 | `not_applicable_no_feature_fit` | `not_applicable_no_fitted_intercept` | `valid_as_published` | diagnostic |
| ws5 | 059db0d | 6d9e3f2 | — | a8a8ea6 | `posthoc_current_gate_pass` | `k0_matched_control_present` | `valid_as_published` | diagnostic |
| ws6 | — | 5ef1f25 | — | a8a8ea6 | `posthoc_current_gate_pass` | `no_featureless_control_confound_uncontrolled` | `diagnostic_only` | diagnostic |
| ws7 | 58b3a91 | e858e96 | — | a8a8ea6 | `corrected_after_gate_defect` | `k0_matched_control_present` | `valid_only_after_corrected_rerun` | hypothesis_generating |
| ws8 | — | c1d2637 | — | a8a8ea6 | `not_applicable_no_feature_fit` | `not_applicable_no_fitted_intercept` | `diagnostic_only` | diagnostic_only |

All eight executed under the same pre-fix gate blob. Every feature-design classification is retrospective.

### ws1 — repaired projected role

**Hypothesis.** turnover rate changes most when a player occupies a substantially DIFFERENT offensive role than normal, not merely a large one

* preregistration: `none`
* original result: `3726991`
* corrected result: `5313ebd`
* gate blob actually used: `a8a8ea6416c9` (pre-fix)
* feature-design integrity: `manual_equivalent_checks_documented`
* comparison parity: `k0_matched_control_present` — a featureless K0 from the arm's own pipeline exists and was fitted
* decision validity: `valid_only_after_corrected_rerun`
* evidence role: **hypothesis_generating**
* execution: COMPLETE · integration: INTEGRATED

**Valid decision metric.** operational team MAE vs matched K0: L1_linear -0.00145 (CI [-0.00792,+0.00477]); N1_split -0.00378 (CI [-0.01170,+0.00343]). ZERO arms beat K0 with a CI excluding zero. Against the unfitted Arm D the arms look better, but K0 -- no features at all -- already collects +0.00326 of that.

**Evidence status.** original run contaminated; corrected rerun preserved and reproducible

**Substantive disposition.** The tested projected-role formulation is FALSIFIED on the operational decision metric. The bounded expansion coefficient is stable -- +0.02647, sd 0.00175, positive in all five walk-forward folds -- but it is a COEFFICIENT, NOT A FORECAST GAIN. Intrinsic expansion-segment improvement vs K0 is +0.01314 with CI [-0.00032,+0.02771] INCLUDING zero, while the 2,283 non-expansion team-games are -0.00995 with CI [-0.01750,-0.00371] EXCLUDING zero, i.e. significantly worse. On the operational track the split is 946/1,968 and the sign REVERSES: -0.00758 vs D with expansion, +0.00632 without -- and that +0.00632 vanishes against K0 (-0.00089, CI spans zero).

**May justify a future frozen challenger?** NO. Retained only as a formulation-dependent discovery lead. A genuinely cutoff-valid, player-specific responsibility-transition measure could still matter; the tested role variables do not justify a frozen challenger.

Supporting artifact: `experiments/player_program/discovery_wave_1/ws1/WS1_RESULTS.json (at 5313ebd)`

### ws2 — responsibility transfer

**Hypothesis.** turnovers rise specifically for players positioned to ABSORB missing teammates' offensive responsibility

* preregistration: `8116b7d`
* original result: `863a900`
* corrected result: `none — original stands`
* gate blob actually used: `a8a8ea6416c9` (pre-fix)
* feature-design integrity: `posthoc_current_gate_pass`
* comparison parity: `k0_present_via_companion_script` — a K0 exists but was produced by a second script, not the arm runner itself
* decision validity: `invalid`  **(coordinator override)**
* evidence role: **hypothesis_generating**
* execution: COMPLETE · integration: INTEGRATED

**Valid decision metric.** NONE ESTABLISHED OPERATIONALLY. The operational design encoded did_appear through values produced by PRE-GATE imputation to 0.0: transfer_direct, transfer_allocated and transfer_role_sensitive are non-zero on 25,522 / 25,522 / 9,577 appearers and on ZERO of the 8,278 non-appearers, so a non-zero value certifies appearance. The published operational fit is therefore contaminated, and no clean operational rerun is preserved.

**Evidence status.** operational result INVALID as published; no clean corrected rerun exists; intrinsic track classified separately

**Substantive disposition.** INVALID AS PUBLISHED; THE FORMULATION REMAINS UNRESOLVED OPERATIONALLY. The player-level operational positive (T1 +0.00178, T2 +0.00225 vs K0, CIs excluding zero) is invalid. The aggregate null is NOT claimed to survive a fortiori: removing a favourable leak would usually weaken a positive, but refitting alters every coefficient and prediction, and no clean corrected aggregate result is in hand. The INTRINSIC track is classified separately and is not subject to the operational appearance leak, because intrinsic training folds contain appearers only. Responsibility-transfer directionality is HYPOTHESIS-GENERATING ONLY.

**May justify a future frozen challenger?** NOT ON THIS EVIDENCE. A clean operational rerun would be required before any claim, in either direction, about the aggregate.

Supporting artifact: `experiments/player_program/discovery_wave_1/ws2/WS2_VERDICT.json (at 863a900)`

### ws3 — team total + allocation

**Hypothesis.** one model should not have to control BOTH how many turnovers a team commits AND which players commit them

* preregistration: `none`
* original result: `1e3509f`
* corrected result: `none — original stands`
* gate blob actually used: `a8a8ea6416c9` (pre-fix)
* feature-design integrity: `manual_equivalent_checks_documented`
* comparison parity: `k0_matched_control_present` — a featureless K0 from the arm's own pipeline exists and was fitted
* decision validity: `valid_as_published`
* evidence role: **diagnostic**
* execution: COMPLETE · integration: INTEGRATED

**Valid decision metric.** two-stage team-total + compositional allocation did not improve player identity under fixed team totals; the premise as originally stated was withdrawn by the workstream itself

**Evidence status.** preserved and reproducible; pooled-only gate invocation was insufficient and the workstream's own fold_gate() caught it

**Substantive disposition.** A VALID DISCOVERY NULL for this formulation, with a redirection. Fold-level retrospective audit supports it: ws3's own fold_gate() dropped proj_off_poss_share (std 7.80e-09) and p_active (std 5.14e-17) in the 2022 stage-2 fold, while the POOLED audit over the same 8 columns and 35,629 rows returned findings [] and passed. That pooled-versus-fold divergence is the measured justification for mandatory per-fold invocation.

**May justify a future frozen challenger?** NO. Its value is the redirection toward team-possession totals.

Supporting artifact: `experiments/player_program/discovery_wave_1/ws3/LEDGER_UPDATE_ws3.json (result + disposition) and ws3/WS3_RESULTS.json (at 1e3509f)`

### ws4 — EWMA timescale family

**Hypothesis.** one decay rate cannot suit both stable and unstable roles

* preregistration: `a6d5cd4`
* original result: `1b634fb`
* corrected result: `none — original stands`
* gate blob actually used: `a8a8ea6416c9` (pre-fix)
* feature-design integrity: `not_applicable_no_feature_fit`
* comparison parity: `not_applicable_no_fitted_intercept` — nothing is fitted, so there is no free-recalibration confound to control
* decision validity: `valid_as_published`
* evidence role: **diagnostic**
* execution: COMPLETE · integration: INTEGRATED

**Valid decision metric.** by-stratum deviance and team MAE against the frozen registered alpha=0.10 running through the identical state machine; error is monotone in memory LENGTH

**Evidence status.** preserved and reproducible; unfitted state-machine comparison, no feature design to audit

**Substantive disposition.** FALSIFIED IN THE OPPOSITE DIRECTION from the hypothesis. Faster adaptation helps in NO stratum; the ordering favours longer memory and is directional and small. This is a valid null, not an integrity failure -- there is no feature matrix here to be unidentified. One team-level interval excludes zero (V5_dual_precision, +0.00331) and the workstream itself declines to claim it; recorded as a caveat, not a result.

**May justify a future frozen challenger?** NO.

Supporting artifact: `experiments/player_program/discovery_wave_1/ws4/WS4_VERDICT.json (at 1b634fb)`

### ws5 — opportunity proxies

**Hypothesis.** FGA share is an incomplete proxy for ball-handling responsibility

* preregistration: `059db0d`
* original result: `6d9e3f2`
* corrected result: `none — original stands`
* gate blob actually used: `a8a8ea6416c9` (pre-fix)
* feature-design integrity: `posthoc_current_gate_pass`
* comparison parity: `k0_matched_control_present` — a featureless K0 from the arm's own pipeline exists and was fitted
* decision validity: `valid_as_published`
* evidence role: **diagnostic**
* execution: COMPLETE · integration: INTEGRATED

**Valid decision metric.** conditional rate deviance and allocation weight quality vs K0; proxies fail as RATE predictors; allocation-only gain approximately +0.0017 (~0.2%) at the player level

**Evidence status.** preserved and reproducible; features clean, gate passes post hoc

**Substantive disposition.** PARTIAL, ALLOCATION ONLY. The expected direction is falsified: clean opportunity proxies do not improve the conditional rate, and the rate and interaction arms are CLOSED. A small player-level allocation value survives at zero team cost -- and by construction it cannot improve the team total, because projected exposure sums to exactly 5x projected team possessions.

**May justify a future frozen challenger?** NOT AS A RATE MODEL. Possible small value as an allocation weight under fixed team totals.

Supporting artifact: `experiments/player_program/discovery_wave_1/ws5/WS5_VERDICT.json (at 6d9e3f2)`

### ws6 — mechanism decomposition

**Hypothesis.** the arm G player-level gain and team-level loss arise from OFFSETTING mechanism effects

* preregistration: `none`
* original result: `5ef1f25`
* corrected result: `none — original stands`
* gate blob actually used: `a8a8ea6416c9` (pre-fix)
* feature-design integrity: `posthoc_current_gate_pass`
* comparison parity: `no_featureless_control_confound_uncontrolled` — no zero-feature control exists; the free-intercept confound is uncontrolled
* decision validity: `diagnostic_only`
* evidence role: **diagnostic**
* execution: COMPLETE · integration: INTEGRATED

**Valid decision metric.** per-mechanism deviance and error contribution across 20 targets, 180 gate audits, max condition 1.549; NO promotion metric by design

**Evidence status.** preserved and reproducible; fitted designs pass the current gate post hoc, but NO featureless control exists, so the free-intercept confound is uncontrolled

**Substantive disposition.** MECHANISM CANCELLATION REJECTED AS THE CAUSE; the real cause was identified. The involvement proxy is a SHARE, so 92.6% of its variance is within-team: within effect +0.036, between effect -0.107, reversal present in 9 of 9 fitted mechanisms. Given a free coefficient the fit spends it at the team level, where it is wrong. This survives as an ARCHITECTURAL diagnostic.

**May justify a future frozen challenger?** NO. It is an explanation and a design direction, not a candidate.

Supporting artifact: `experiments/player_program/discovery_wave_1/ws6/WS6_MECHANISM_DECOMPOSITION.json (.verdict) at 5ef1f25`

### ws7 — nonlinear / heterogeneous

**Hypothesis.** role and involvement effects may be hidden by linear pooling

* preregistration: `58b3a91`
* original result: `e858e96`
* corrected result: `none — original stands`
* gate blob actually used: `a8a8ea6416c9` (pre-fix)
* feature-design integrity: `corrected_after_gate_defect`
* comparison parity: `k0_matched_control_present` — a featureless K0 from the arm's own pipeline exists and was fitted
* decision validity: `valid_only_after_corrected_rerun`
* evidence role: **hypothesis_generating**
* execution: COMPLETE · integration: INTEGRATED

**Valid decision metric.** stratum-wise deviance and operational team MAE vs K0; null on the hypothesis and REFUTED on the decision metric for primary creators

**Evidence status.** original run contaminated (WS7_RESULTS_v1_leaky.json preserved); corrected v2 rebuild preserved and reproducible

**Substantive disposition.** NULL ON THE HYPOTHESIS, ADVERSE ON THE DECISION METRIC, under the corrected rerun. Bounded nonlinear and heterogeneous formulations do not beat K0, and the primary-creator concentration hypothesis is refuted under the tested formulation. The leaky v1 run is retained as contaminated evidence and must not be cited.

**May justify a future frozen challenger?** NO under the tested formulations.

Supporting artifact: `experiments/player_program/discovery_wave_1/ws7/WS7_RESULTS.json + ws7/WS7_LEDGER_UPDATE.json (at e858e96). NOT WS7_RESULTS_v1_leaky.json.`

### ws8 — operational error decomposition

**Hypothesis.** where does operational error actually come from: availability, candidate precision, minute allocation, possession allocation, or rate

* preregistration: `none`
* original result: `c1d2637`
* corrected result: `none — original stands`
* gate blob actually used: `a8a8ea6416c9` (pre-fix)
* feature-design integrity: `not_applicable_no_feature_fit`
* comparison parity: `not_applicable_no_fitted_intercept` — nothing is fitted, so there is no free-recalibration confound to control
* decision validity: `diagnostic_only`
* evidence role: **diagnostic_only**
* execution: COMPLETE · integration: INTEGRATED

**Valid decision metric.** incremental team MAE per labelled counterfactual: team possession-total projection +0.1033 [0.0833, 0.1244]; within-team allocation -0.0181 (the oracle is WORSE); availability -0.0034 (null); missing participants -0.0003 (null); ratio to the MAD floor 0.9969

**Evidence status.** preserved and reproducible; oracle counterfactuals, not models

**Substantive disposition.** DECISIVE ON DIRECTION. Team-possession-total projection is the clearest addressable team-aggregate exposure error. The rate model sits at its Poisson noise floor. Oracle variants are NOT models and are NOT promotion evidence.

**May justify a future frozen challenger?** NO ARM. It identifies WHERE to work, not WHAT to register.

Supporting artifact: `experiments/player_program/discovery_wave_1/ws8/WS8_ERROR_DECOMPOSITION.json and ws8/WS8_LEDGER_RESULT.json (at c1d2637)`

