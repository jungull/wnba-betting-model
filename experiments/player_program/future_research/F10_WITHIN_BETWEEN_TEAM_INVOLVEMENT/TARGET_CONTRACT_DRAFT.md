# TARGET CONTRACT DRAFT — F10_WITHIN_BETWEEN_TEAM_INVOLVEMENT

**Node:** F10_WITHIN_BETWEEN_TEAM_INVOLVEMENT · lane `future_research` · type `documentation`
**Produced by:** read-only research scout. No fitting was performed. No model code was written.
**Depends on:** G04_PROGRAM_ROADMAP_EXTRACTION (`orchestration/reports/ROADMAP_EXTRACTION.json`)

> DIAGNOSTIC AND TARGET-CONTRACT DRAFT ONLY. Discovery work being unblocked is NOT authorisation to
> fit. Fitting requires a target contract, a matched K0, cutoff-valid evidence, a preregistration
> and an independent gate review.

---

## 0. THIS DRAFT DOES NOT AUTHORISE FITTING

Stated plainly, because it is the only sentence in this file that constrains what the file can be
cited for:

**This draft does not authorise fitting.** It does not authorise building a feature artifact, it
does not authorise registering an arm, it does not authorise a walk-forward run, and it does not
authorise any comparison against the frozen incumbent `D_ewma_shrunk`. It is a statement of what
the documentation does and does not supply for a within/between involvement forecaster, plus an
inventory of the evidence that exists. Fitting requires all five of: a target contract, a matched
K0, cutoff-valid evidence, a preregistration, and an independent gate review. This file is a draft
of the first of those five and is not itself any of the other four.

---

## 1. THE ESTIMAND

### NOT_DERIVABLE_FROM_DOCUMENTATION

The documentation does not supply an estimand for a within/between involvement forecaster. It
supplies a **functional form**, a **procedural requirement**, and — from an adjacent registered arm
— a **unit** and a **denominator**. It does not supply the **target statistic**, and the target
statistic is the decisive component here, because the documented evidence says this exact feature
moves the two candidate grains in *opposite directions*.

No estimand is invented below. What follows is the inventory of what was actually found.

#### 1.1 What the documentation DOES supply

**A functional form (documented, verified).** The indicated formulation is to enter a share-valued
feature as two coefficients rather than one:

> `discovery_wave_1/HYPOTHESIS_LEDGER.json:879` — "an arm that enters any share-valued feature as
> SEPARATE within-team and between-team coefficients rather than one pooled coefficient. This is
> the single most transferable finding in the wave."

> `discovery_wave_1/HYPOTHESIS_LEDGER.json:872` — "the within/between split of involvement is
> diagnosed, never fitted as a forecasting arm -- entering beta_within and beta_between as two
> separate coefficients is the indicated formulation and is UNTESTED"

**A procedural requirement (documented, verified).**

> `PROJECT_UPDATE_2026-08-04.md:277` — "(10) Within/between involvement as a"
> `PROJECT_UPDATE_2026-08-04.md:278` — "forecaster — a **new experiment**, requiring a matched K0."

> `PROJECT_UPDATE_2026-08-04.md:528` — "The within/between two-coefficient form is identified as the
> cause of arm G's behaviour but was **measured as a diagnostic, never tested as a forecaster.**
> Requires preregistration **and a matched K0**."

> `discovery_wave_1/HYPOTHESIS_LEDGER.json:882` — "the within/between form must be registered and
> frozen before fitting; ws6 only diagnosed it"

**A unit and a denominator, from the adjacent registered arm — NOT from any statement about F10.**
`arm_registry.jsonl:33` registers `turnover_rate_role_context/1`, the P2 arm family in which
`offensive_involvement_proxy` lives:

* unit — `feature_artifact.grain` = `["game_id", "team_id", "player_id", "decision_time_label"]`,
  with `decision_time_label` = `"pregame_cutoff (the contract's forecast_cutoff for that game)"`.
  That is one row per player per team-game at the pregame cutoff.
* denominator — the same record states, of the projected-role feature group: *"projected
  possessions ALREADY enter the model as the count OFFSET, so raw volume is not additional
  information."* The operational denominator for the turnover-rate family is therefore **projected**
  offensive possessions entering as a log offset, not realised possessions.
* the target artifact `arm_registry.jsonl:29` (`turnover_target_contract/1`) fixes the label:
  `target_hierarchy[0]` = `"1. total player-attributed turnovers"`, on a row universe that
  *"contains ALL SCOREABLE player-game rows, including ZERO-turnover games"* and that **excludes**
  candidates who did not appear (*"An inactive candidate is NOT a zero-turnover observation."*).

These are real and they are cited. They are also the unit and denominator of a *different* arm.
Nothing in the corpus says that an F10 arm inherits them, and §1.2 explains why that inheritance
cannot be assumed silently.

#### 1.2 What the documentation does NOT supply, and why it matters

**The target statistic is unstated, and the grain is the whole question.** WS6's own audit row
records that it had no promotion metric at all:

> `discovery_wave_1/FINAL_AUDIT_MATRIX.json:504` — "per-mechanism deviance and error contribution
> across 20 targets, 180 gate audits, max condition 1.549; **NO promotion metric by design**"

The entire documented content of the within/between finding is that the pooled coefficient *helps
one grain and hurts the other*:

> `discovery_wave_1/HYPOTHESIS_LEDGER.json:847` — "The resulting coefficient allocates turnovers
> correctly BETWEEN TEAMMATES (player deviance improves) while pushing TEAM TOTALS the wrong way
> (team MAE degrades)."

So "does the two-coefficient form work?" has no answer until someone says *at which grain, against
which statistic*. Candidate statistics visible in the corpus — player-row Poisson deviance,
player-row MAE, operational team-game turnover MAE — are documented to disagree in **sign** for
precisely this feature. Choosing among them is a scientific commitment. It is not in this node's
gift, and picking one here would manufacture a commitment the program never made.

**Second reason the inheritance in §1.1 cannot be assumed.** The wave's team-total-pinned
*allocation* arms cannot move the team total by construction; a within/between **rate** arm is not
pinned, so it can move both grains. A target contract that silently adopts the P2 arm's
configuration would be choosing the grain by default rather than by decision.

**Third: the primary program target is a different quantity entirely.** The settled primary target
is `REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS`; turnovers are documented as the downstream,
secondary track. Nothing in the corpus states whether an F10 arm is graded on the primary target,
on the secondary turnover track, or on neither. Not derivable.

#### 1.3 Verdict

**Estimand: NOT_DERIVABLE_FROM_DOCUMENTATION.** A registered layer with a stability report and no
estimand is not closer to fittable than an unregistered one. F10 currently has a form, a
requirement, and an adjacent arm's unit and denominator. It does not have a target statistic, and
therefore it does not have an estimand. Supplying one is a decision for a preregistration and a
human gate, not for this node.

---

## 2. THE MATCHED-K0 REQUIREMENT FOR THIS TARGET

The matched-K0 requirement is stated, and unlike the estimand it *is* derivable, because
P26_ARM_SPECIFIC_K0_CONTRACT (status `PASSED` in `orchestration/GRAPH_STATE.json`) supplies the
per-arm-kind rule and the within/between form falls squarely inside one of its declared kinds.

**2.1 The gate-level requirement.** `comparison_gate.py:37-40` — "**Layer A — challenger versus
matched K0. STRICT PIPELINE PARITY, and THE PRIMARY TEST OF WHETHER THE SUBSTANTIVE FEATURES ADD
VALUE.**" `comparison_gate.py:1358` (`require_matched_k0`) — "A comparison without K0 is blocked
outright: the free-flexibility gain is then unmeasured, and an unmeasured confound of the size of
the effect is indistinguishable from the effect." A Layer A mismatch is **not** adjudicable by an
ordinary reason.

**2.2 Why WS6 cannot be reused as its own control.** WS6 has no featureless control of any kind:

> `discovery_wave_1/FINAL_AUDIT_MATRIX.json:494` — `comparison_parity`:
> `"no_featureless_control_confound_uncontrolled"`; the evidence block records
> `matched_k0_present: false` and "NONE. There is no zero-feature control in
> run_ws6_mechanism_decomposition.py."

Its two reference points — arm G refitted on the TOTAL, and a walk-forward `share_baseline` — are
**same-feature** references, not featureless ones. Neither is a K0.

**2.3 The arm kind, and the consequence for the verdict label.** Under the P26 taxonomy
(`stage2b/P26_ARM_SPECIFIC_K0_CONTRACT/K0_MATCHED_SCHEMA.json`, `arm_kind` enum), an arm whose
claim is *"two coefficients rather than one pooled coefficient"* on the **same** feature is a
`structural_reparameterisation`, not a `substantive_feature`. The pooled arm-G form is exactly the
restriction `beta_within = beta_between`. P26's rule for that kind:

> `stage2b/P26_ARM_SPECIFIC_K0_CONTRACT/REPORT.md:99` — "`structural_reparameterisation` | carries
> the **arm's own new parameterisation with the tested parameter at its null** — not the incumbent's
> old structure. ... | structural result"

> `stage2b/P26_ARM_SPECIFIC_K0_CONTRACT/REPORT.md:104` — "`calibration_only`,
> `structural_reparameterisation` and `hierarchical_pooling` **fix a parameter**; the others
> **remove a term**."

Therefore, if the arm is declared `structural_reparameterisation`:

* `K0_MATCHED[arm_id]` is **the pooled single-coefficient form** — the arm's own parameterisation
  with the tested contrast `(beta_within − beta_between)` fixed at its null value **0** — and is
  **not** an intercept-only model;
* `tested_parameters` must be non-empty and must name that contrast (a record of this kind naming
  none blocks with `tested_parameter_missing`);
* the arm is eligible for a **structural result** label only. It can never earn a feature-value
  label, however large `challenger_vs_k0` is. The feature value of involvement *itself* is a
  separate, already-answered question and may not be re-credited here.

If instead an arm were declared `substantive_feature` (K0 carrying no involvement term at all), it
would be testing whether involvement helps — **not** whether the decomposition helps — and would
not answer the documented question at `HYPOTHESIS_LEDGER.json:879`. The kind must be declared
**before results** (`K0_MATCHED_SCHEMA.json`: "An arm may not be scored under a kind it did not
declare before results").

**2.4 Invariants that bind either way.** `stage2b/P26_ARM_SPECIFIC_K0_CONTRACT/REPORT.md:118-123`: `intercept_treatment`,
`calibration_freedom`, `penalty_treatment`, `link_function`, `preprocessing`, `fallback_rules`,
`companion_components` and `post_processing` must be **identical** between arm and null; any
difference is countable as `free_flexibility_granted`. `LAYER_A_STRICT` in `comparison_gate.py`
additionally includes `aggregation` — "how player-level predictions aggregate to a team total" —
which is load-bearing for this arm specifically, since the documented behaviour of the pooled form
is a player/team aggregation disagreement.

**2.5 A control this draft flags as NOT documented.** To attribute a result to the *decomposition*
rather than to the *feature*, a three-way comparison (two-coefficient arm / pooled arm / featureless
K0) is the natural design. P26 requires the first two; nothing in the corpus requires the third
alongside them. This is recorded as a drafting note, **not** as a documented requirement, and is
handed to preregistration.

---

## 3. INVENTORY OF CUTOFF-VALID EVIDENCE — inventoried, not assumed

Every row below was checked against bytes in this worktree or against a named git object. Nothing
here is inferred from prose alone.

### 3.1 NOT cutoff-valid — confirmed by measurement, not by citation

**`turnover_p2_v1/turnover_role_context_features_v1.parquet` — `offensive_involvement_proxy`,
`trailing_minutes_share`, `role_change`, `trailing_rotation_rank`.** This is the exact column WS6
fitted. Measured here by joining the feature file to
`turnover_targets_v1/player_turnover_targets_v1.parquet` on `(game_id, team_id, player_id)` and
crosstabbing null-ness against appearance:

| column | null & did-not-appear | non-null & appeared | off-diagonal |
|---|---|---|---|
| `offensive_involvement_proxy` | 8,278 | 27,351 | **0** |
| `trailing_minutes_share` | 8,278 | 27,351 | **0** |
| `role_change` | 8,278 | 27,351 | **0** |
| `trailing_rotation_rank` | 8,278 | 27,351 | **0** |

35,629 rows total; 27,351 appeared. The null mask is an **exact post-cutoff `did_appear`
indicator**, reproducing the documented figures precisely. **These columns are not admissible in a
forecaster on the operational universe.** (On WS6's intrinsic universe every row is an appearer, so
the mask there means "first appearances" and WS6's own fits remain internally sound — that
distinction is documented and is preserved here.)

**WS6's offset is realised same-game exposure.**
`discovery_wave_1/ws6/run_ws6_mechanism_decomposition.py:266` at commit `5ef1f25`:
`F1["exposure"] = F1["realised_off_possessions"].astype(float)`, with
`:397` `off = np.log(clip(exposure)) + log(D_ewma_shrunk)`. The registered P2 arm explicitly
forbids this on the forecast path — `arm_registry.jsonl:29`, `explicitly_not_authorised` includes
*"using actual target-game possession exposure in an operational forecast"*, and
`arm_registry.jsonl:33` `feature_boundary.forbidden` includes *"actual target-game possessions"*.
**The diagnostic's denominator is not the forecaster's denominator.**

**WS6's between-team component is itself post-cutoff.** `run_ws6_mechanism_decomposition.py:642-644`:
`tg_mean = Zw.groupby(["game_id","team_id"])["_z"].transform("mean")`; `_z_between = tg_mean`;
`_z_within = _z - tg_mean`. `Zw` is `F1`, restricted at `:265` to `realised_off_possessions > 0`.
So **both the centring value and the set it is averaged over are the realised appearer set**. A
forecaster must form the between-team component over the *projected* candidate set. This is a
construction change, not a re-run, and it interacts directly with the documented candidate-precision
problem (8,278 non-appearing Tier A candidates).

### 3.2 Cutoff-valid and available — measured

**`ws5_opportunity_proxy_features_v1.parquet`** (git object at commit `6d9e3f2`; see §4 blocker B1).
36,523 rows; restricted to `is_tier_a_candidate` → **35,629 rows**, matching the operational
universe exactly. Measured null counts on the Tier A subset: `x1_fga_share` 0, `x2_pe_per36` 0,
`x3_pe_share` 0, `x4_pe_share_delta` 0, `x5_involvement_rank` 0, `x6_responsibility_share` 0.
Crosstab against appearance confirms **non-null on all 8,278 non-appearers as well as all 27,351
appearers** — i.e. the leak of §3.1 is absent. These are the only cutoff-valid involvement
constructions that exist in this program.

**The within/between decomposition is reproducible on cutoff-valid inputs.** Computed here as a
variance decomposition only (no fit, no model, no performance quantity), standardising each proxy
and centring within `(game_id, team_id)`:

| feature | universe | rows | between var | within var | within share |
|---|---|---|---|---|---|
| `x1_fga_share` | all Tier A candidates | 35,629 | 0.049826 | 0.950174 | **0.95017** |
| `x1_fga_share` | appearers only | 27,351 | 0.077622 | 0.922378 | **0.92238** |
| `x3_pe_share` | all Tier A candidates | 35,629 | 0.053425 | 0.946575 | **0.94658** |
| `x3_pe_share` | appearers only | 27,351 | 0.082265 | 0.917735 | **0.91773** |

WS6's leaked-column figure on its own universe was `within_share_of_variance = 0.92568`. The clean
appearer-restricted replication is **0.92238** — the architectural fact survives the leakage repair.
Note that the within share *rises* to ~0.95 when the projected candidate set is used, because
non-appearers add within-team spread and no between-team spread. **The between-team component,
which is the half carrying the negative documented coefficient, is the scarcer half of the variance
and gets scarcer under the cutoff-valid construction.** Any target contract should treat the
identifiability of `beta_between` as an open question, not a given.

**Command of record for §3.1 and §3.2:** pandas/pyarrow under Python 3.13, reading
`turnover_p2_v1/turnover_role_context_features_v1.parquet`,
`turnover_targets_v1/player_turnover_targets_v1.parquet` and the extracted
`git show 6d9e3f2:experiments/player_program/discovery_wave_1/ws5/ws5_opportunity_proxy_features_v1.parquet`.
No fit was run; the only computations were null crosstabs and variance decompositions.

### 3.3 Universes — three of them, and they do not coincide

Measured:

| artifact | rows | team-games | games |
|---|---|---|---|
| `turnover_p2_v1/turnover_role_context_features_v1.parquet` | 35,629 | **2,914** | 1,458 |
| `turnover_targets_v1/player_turnover_targets_v1.parquet` | 28,328 | **2,990** | 1,495 |
| `turnover_targets_v1/team_turnover_reconciliation_v1.parquet` | 2,990 | 2,990 | 1,495 |
| program universe as stated in the node contract | — | **2,982** | 1,491 clusters |
| WS6 fit universe (`WS6_MECHANISM_DECOMPOSITION.json`, `fit_universe`) | 28,193 | — | 1,491 |

The candidate/feature universe covers **2,914** team-games — 68 short of the 2,982 stated in the
governing contract and 76 short of the turnover-target universe. Tier A candidates per team-game:
mean 12.23, min 9, max 17. This is recorded as a **measured non-alignment that a target contract
must resolve explicitly** (which denominator defines the estimand's population), not as a defect
claim. Games must never be split across folds or cluster-bootstrap draws regardless of which is
chosen.

### 3.4 Not inventoried, deliberately

No comparative historical performance was read. `stage2b/SEALED_RESULTS/` was not opened. The
`ws5_predictions_*.parquet` and `WS5_RESULTS.json` objects were listed but **not read**, because
they carry comparative performance.

---

## 4. KNOWN DATA BLOCKERS

**B1 — the wave-1 workstream evidence is not reachable from HEAD.** Measured:
`git ls-tree -r --name-only HEAD -- experiments/player_program/discovery_wave_1/<ws>` returns **0
files for every one of ws1…ws8**. The ws6 artifacts exist at commit `5ef1f25` and the ws5 artifacts
at `6d9e3f2`, but `git merge-base --is-ancestor` reports **NO** for both against
HEAD `4374f7c548bbac7589df3cacc0dbeed3d7a8e1e1`; each is contained only in an unmerged
`worktree-agent-*` branch. At HEAD, only the summaries survive — `HYPOTHESIS_LEDGER.json`,
`FINAL_AUDIT_MATRIX.{json,md}`, `DISCOVERY_WAVE_1_SUMMARY.md`, `RETROSPECTIVE_GATE_AUDIT.*`.
**Consequence:** the only cutoff-valid involvement feature artifact in the program
(`ws5_opportunity_proxy_features_v1.parquet`) is not present in the working tree; the ws6
coefficients are prose at HEAD and bytes only in an unmerged object. Any preregistration citing
either must either bind the commit hash explicitly or the artifacts must be brought onto the branch
first. This is an evidence-availability blocker, not a scientific finding.

**B2 — the diagnostic's denominator is prohibited on the prediction path.** §3.1. WS6 used realised
offensive possessions as offset. A forecaster must use projected offensive possessions. There is no
existing run of the within/between form on a projected offset.

**B3 — the between-team component must be reconstructed over the projected candidate set.** §3.1.
WS6 centred within the realised appearer set. Rebuilding the centring over Tier A candidates is a
new construction requiring its own gate audit, and it changes the variance split (§3.2).

**B4 — the leaking P2 columns must not be used.** §3.1, measured, zero off-diagonal.
`turnover_p2_v1/turnover_role_context_features_v1.parquet` is a canonical artifact and was **not**
modified by this node.

**B5 — candidate precision.** 8,278 Tier A candidates never appear; the documentation records them
as carrying a mean 15.1 possessions of projected exposure and 14.18% of player-level absolute error.
Whether an F10 arm scores on the candidate universe or the appearer universe is unresolved and
interacts with §3.3.

**B6 — WS6 was executed under an older gate blob.** `FINAL_AUDIT_MATRIX.json` records
`gate_fixes_in_force_during_execution`: `55f4500_rank_and_conditioning` **false**,
`42af2cd_informative_missingness` **false**. The designs pass the current gate *post hoc*
(`posthoc_current_gate_pass`, 180 audits, worst condition 1.549), but a fresh arm must be audited
per training fold under the current gate, per the documented P27/ws1 lesson.

---

## 5. CONTRADICTIONS FOUND

**C1 — "reversal in 9 of 9" is two different claims, and only one of them is true.**

`discovery_wave_1/DISCOVERY_WAVE_1_SUMMARY.md:215-216` reads "within `+0.036`, between `-0.107`,
reversal / in 9 of 9 fitted mechanisms", and `FINAL_AUDIT_MATRIX.json:506` reads "reversal present
in 9 of 9 fitted mechanisms". Read plainly alongside the quoted `+0.036 / -0.107` pair, that says
*sign* reversal in 9 of 9. Recomputed directly from
`WS6_MECHANISM_DECOMPOSITION.json` at `5ef1f25`
(`cancellation_test.competing_explanation_within_team_reallocation.per_mechanism_within_vs_between_fit`,
9 mechanisms):

* `beta_between < beta_within`: **9 of 9** ✔
* sign reversal, i.e. `beta_within > 0 > beta_between`: **4 of 9** (bad_pass, bad_pass_out_of_bounds,
  lost_ball, lost_ball_out_of_bounds)
* both coefficients negative: **5 of 9** (offensive_foul, traveling, step_out_of_bounds,
  three_second, backcourt)
* `within_significant_90`: 5 of 9 · `between_significant_90`: 6 of 9

`HYPOTHESIS_LEDGER.json:847` states it correctly — "The reversal holds in 9 of 9 fitted mechanisms
-- **beta_between < beta_within everywhere**" — i.e. it defines "reversal" as the ordering. The
summary and the audit matrix drop that definition and the sentence then reads as a sign claim that
the bytes do not support. **Frozen bytes govern over prose.** Reported, not reconciled: no file was
edited.

**C2 — WS6's supporting-artifact path does not resolve at HEAD.**
`FINAL_AUDIT_MATRIX.json` `supporting_artifacts` gives
`experiments/player_program/discovery_wave_1/ws6/WS6_MECHANISM_DECOMPOSITION.json (.verdict) at
5ef1f25`. The commit qualifier is honest, but `5ef1f25` is not an ancestor of HEAD (§B1), so a
reader following the path in the working tree finds nothing. Documentation-vs-bytes mismatch.

---

## 6. WHAT THIS NODE COULD NOT ESTABLISH

1. **An estimand.** Deliberately. See §1.3.
2. **Whether an F10 arm is graded at player grain or team grain.** Undocumented, and the two are
   documented to disagree in sign for this feature.
3. **Whether the F10 track is scored on the primary possessions target or the secondary turnover
   track.** Not stated anywhere in the corpus.
4. **Whether `beta_between` is identifiable under the cutoff-valid construction.** §3.2 shows the
   between-team share of variance falling to ~0.05 on the projected candidate set. Establishing
   identifiability requires a per-fold design audit, which would be model-adjacent work this node
   is not authorised to do.
5. **Any statement about how well anything performs.** No comparative performance was read.

---

## 7. STOP CONDITIONS

**None tripped.** Nothing found here changes the primary target, the K0 structure, the inference
structure, the candidate universe, the cutoff-valid feature set, or the leakage status. The
`did_appear` leak in the P2 columns was already documented by ws3 and ws5; this node re-measured and
confirmed it (§3.1) rather than discovering it. C1, C2 and B1 are raised for the coordinator as
documentation and evidence-availability issues, not resolved inside the node.

---

## 8. SUMMARY FOR THE GATE

| acceptance criterion | status |
|---|---|
| the estimand, unit and denominator are stated | **stated as NOT_DERIVABLE_FROM_DOCUMENTATION**, with the unit and denominator that *are* documented (from an adjacent arm) inventoried and the missing target statistic named — §1 |
| the matched-K0 requirement is stated for this target | **stated** — `structural_reparameterisation`; K0 = the pooled single-coefficient form with the tested contrast fixed at 0; structural-result label only — §2 |
| cutoff-valid evidence is inventoried, not assumed | **inventoried by measurement** — leak crosstabs, ws5 null coverage, variance decompositions, universe counts — §3 |
| the draft states explicitly that it does not authorise fitting | **stated** — §0 |
