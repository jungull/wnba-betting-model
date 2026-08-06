# P34 RED TEAM — OFFSET-DEPENDENCE REVIEW (independent reviewer, one dimension)

**Node:** P34_PREREGISTRATION_RED_TEAM  |  **Dimension:** offset dependence
**Reviewer independence:** this reviewer did not author P33 and has read no other P34 reviewer file.

ADVERSARIAL REVIEW. Reviewers are independent of the preregistration author. A clean review does not make an arm true; it makes it fittable.

---

## STOP-CONDITION NOTICE (stated first, per mandate)

Two Severity A findings below (A-1 on A01, A-2 on A04) establish that those arms **cannot pass the
frozen `offset_dependency_guard` as preregistered** — demonstrated by running the frozen guard bytes
on the arms' complete declared designs, not by reading prose. Every resolution path **except
withdrawal of the two arms** would require changing either the frozen guard (inference structure)
or the arms' preregistered K0_MATCHED designs (K0 structure). Per the node's stop conditions I am
**raising this, not resolving it**: if the program elects any fix other than withdrawal of
A01/A04, that decision must be adjudicated above this node. `stop_condition_concern = true`.

No finding in this review touches the primary target, the candidate universe, the cutoff-valid
feature set, or the leakage status. The five-fold/cluster-bootstrap inference scaffold itself is
unchallenged.

---

## 0. Hash verification (performed before anything else)

`Get-FileHash -Algorithm SHA256` on the four pinned inputs — **ALL MATCH**:

| file | pinned | measured |
|---|---|---|
| P33_PREREGISTRATION_DRAFT/SPEC.json | 066b2a04… | 066B2A04… match |
| P33_PREREGISTRATION_DRAFT/REPORT.md | 6d945b86… | 6D945B86… match |
| P32_CANDIDATE_SYNTHESIS/SPEC.json | 1dc25981… | 1DC25981… match |
| P30_EVIDENCE_PACKET_V3/EVIDENCE_PACKET_V3.json | 95d2412c… | 95D2412C… match |

Additionally re-hashed the two implementation receipts the offset resolution rests on:

* `possession_features.py` = `d44cca3828476e1c38b1e310d5ef9974e46afa68df8596cb22fdd24e2670d105` —
  **matches the sha256 pinned in P33 SPEC `inputs_verified_sha256`**.
* `stage2b/P25_OFFSET_DEPENDENCY_GUARD/offset_dependency_guard.py` =
  `c78e70b6a0603b15bd74dd4dd798ba698d962565e813b2eee8df9360cc100e95` — **matches the P33 pin**.

---

## 1. Byte re-derivation of every citation in `inference_spec_gap_resolution`

Each cited line was read from the hash-verified `possession_features.py` bytes:

| citation | claimed content | verified against bytes |
|---|---|---|
| docstring lines 62–64 | "projected_team_off_possessions: it is the OFFSET (as a log), not a feature" | **CONFIRMED** — exact text at lines 62–64 |
| line 135 | `OFFSET_COLUMN = "log_projected_team_off_possessions"` | **CONFIRMED** |
| line 319 | `F[OFFSET_COLUMN] = np.log(F["projected_team_off_possessions"]...)` | **CONFIRMED** |
| lines 399–406 | incumbent's "prediction IS projected_team_off_possessions" | **CONFIRMED** — phrase at line 401, inside `incumbent_input` (function spans 397–406) |
| line 515 | offset handed to gates renamed `log_exposure` | **CONFIRMED** — `offset = frame[OFFSET_COLUMN].rename("log_exposure")` |
| GATE_INVOCATION_CONTRACT §3.1 | "every turnover arm carries log(exposure) (and log(D)) in the offset" | **CONFIRMED** at contract line 117 — but see finding C-2: this sentence is about the **turnover lane** |

Measured live (script in Appendix; feature/schedule columns only, no target value entered any
statistic, nothing fitted, no performance number computed):

* `max |OFFSET_COLUMN − log(projected_team_off_possessions)|` over all 2,982 rows = **0.0** —
  reproduces P33's measurement exactly.
* Universe re-derived: 2,982 rows / 1,491 clusters; `train_clusters == train_rows/2` in all five
  D006 folds (games never split — carried below, it is load-bearing for A02).

**The LOG-link conclusion survives this review.** Given the only receipted offset object is
log-scale and the incumbent must be a point of every null family, `g⁻¹(log P) = P` forces `g = log`
on the observed range. The derivation's *gloss* is loose (finding C-1) but the conclusion is fixed
by the bytes.

---

## 2. SEVERITY A FINDINGS

### A-1. A01 cannot pass the frozen offset guard truthfully — guard bytes contradict the preregistered K0_MATCHED

P33 `guards_at_call_site` binds every arm: "before any fit, every arm's complete per-fold design
[offset | nuisance | candidate] passes … offset_dependency_guard (P25/R11) invoked with
offset = log_exposure AND incumbent_projection = projected_team_off_possessions."

A01's treatment column `(log_exposure − m_bar)` is **exactly affine in the offset**
(measured `R²(c ~ 1 + offset) = 1.0` in every training fold — it cannot be otherwise). I ran the
frozen guard on A01's complete design (Appendix script, `guard_A01` block). Results from the
frozen bytes:

| invocation | result | blocking kinds |
|---|---|---|
| `declared_family=SUBSTANTIVE` | **BLOCKED** | `candidate_affine_in_offset`, `candidate_is_function_of_incumbent_projection`, `calibration_parameter_in_substantive_arm`, `design_reconstructs_offset`, `augmented_rank_deficient`, `fold_local_rank_deficient`, `fold_local_reconstructs_offset` |
| `RECALIBRATION`, `k0_carries_offset_slope=False` | **BLOCKED** | `recalibration_family_incomplete` |
| `RECALIBRATION`, `k0_carries_offset_slope=True` | passes | — |

The only passing invocation requires attesting `k0_carries_offset_slope: True`. The guard's frozen
bytes define that key as "the matched control must have the SAME slope freedom (S4)" (line 104) and
its failure detail reads "K0_MATCHED must carry the same offset-slope freedom as the challenger,
else challenger_vs_k0 measures recalibration" (lines 424–426). **A01's preregistered
K0_MATCHED is `[log_exposure] with slope fixed at 1`** — by design it carries NO slope freedom,
because "does a free slope beat slope-1?" IS the hypothesis, and P33's primary gate for A01 is
exactly the challenger-vs-K0 delta_MAE the guard's rule exists to forbid.

So as frozen: either the invocation attests something false about the preregistered null
(defeating the S4 protection nominally rather than actually), or it attests truthfully and the
guard blocks the arm before any fit. **A01 is not fittable as preregistered.** P33 declares A01
fit-ready ("all five evaluable"), cites the guard's docstring phrase "recalibration is its own
hypothesis family" as licence, and nowhere engages the `k0_carries_offset_slope` requirement.
Frozen bytes govern over prose (standing rule 1): the bytes say the arm blocks.

**Close-out options (not resolved here):** withdraw A01; or adjudicate above this node that the
guard's S4 rule does not bind declared-recalibration arms whose slope IS the family-accounted
treatment — which is a change to the frozen guard's enforcement semantics (inference structure)
and trips the stop condition.

### A-2. A04 is blocked by the frozen guard under BOTH declared families — no passing invocation exists at all

A04's complete design is `[offset | 1[SHALLOW] | (log_exposure − m_bar) | 1[SHALLOW]:(log_exposure − m_bar)]`
(the global slope and tier main are nuisance per its CC-H4 stricter null; the interaction is the
treatment). The frozen guard audits **all** design columns — nuisance included
(`design_names = nuisance + candidate`, guard line 245, loop at line 270). Measured on the frozen
bytes (Appendix, `guard_A04` block):

| invocation | result | blocking kinds |
|---|---|---|
| `SUBSTANTIVE` | **BLOCKED** | `calibration_parameter_in_substantive_arm` (the centered-slope nuisance column), `candidate_affine_in_offset`, `candidate_is_function_of_incumbent_projection`, `pair_reconstructs_offset`, `design_reconstructs_offset`, `augmented_rank_deficient`, `fold_local_rank_deficient`, `fold_local_reconstructs_offset` |
| `RECALIBRATION` with complete declaration incl. `k0_carries_offset_slope=True` | **BLOCKED** | `mixed_family_arm` — "a RECALIBRATION arm may carry only functions of the offset or the incumbent projection" (guard lines 427–432); `1[SHALLOW]` and the interaction are depth functions, not offset functions |

**There is no declared_family under which A04's complete preregistered design passes the frozen
guard.** Unlike A01, not even a false attestation rescues it. Under P33's own
`guards_at_call_site` rule, A04 dies at invocation, before any fit, in every fold — yet P33
declares it fit-ready with a full kill-condition set that presumes it fits. Same close-out
options as A-1; same stop-condition raise. (Note: A04's `expected_failure_mode` names the S4
confound and power, not guard-invocability. This failure was not anticipated by the draft.)

---

## 3. SEVERITY B FINDINGS (must fix before P35 task-card freeze)

### B-1. The P25 invocation is under-specified for all 26 arms: `declared_family` and the recalibration declaration payload are frozen nowhere

The frozen guard's behaviour branches on `declared_family` ∈ {SUBSTANTIVE, RECALIBRATION} and on a
six-key `recalibration_declaration`. P33 freezes neither, for any arm. The SPEC's per-arm
`arm_kind` field ("calibration_only" for A01–A06) **does not map onto the guard's axis**: measured,
A02's design passes only under SUBSTANTIVE (its `pace_gap` treatment is not an offset function; if
invoked as RECALIBRATION — a natural misreading of `arm_kind: calibration_only` — the frozen guard
blocks it with `mixed_family_arm`). A03, A05, A06 are in the same position. P35 must pin, per arm:
`declared_family`, and where RECALIBRATION, the full declaration payload — with values that are
TRUE of the arm's preregistered K0 (see A-1 for why this is not currently possible for A01).

### B-2. "The preregistered intercept structure" is referenced everywhere and defined nowhere; it decides what K0_MATCHED[A01] actually is, and whether m_bar is load-bearing

The phrase appears in P30 `k0_matched.core_rules` ("slope 1; the preregistered lower-order
intercept structure"), P32 (A01, A03, A06), and P33 (A01 null "with slope fixed at 1 and the
preregistered intercept structure"; A03/A06 "incumbent intercept structure"). No document
enumerates it. The incumbent carries **no intercept** (eta = offset exactly; verified from
`incumbent_input`). The two readings differ materially:

* **No free intercept** (the only reading consistent with "nested null recovers the incumbent
  EXACTLY"): K0_MATCHED[A01] has zero fitted parameters and IS the incumbent; A01 is a
  one-parameter family in which **m_bar is load-bearing** — `eta = (1+delta)·off − delta·m_bar`,
  so different m_bar values define genuinely different model families pivoting at exp(m_bar).
* **Free intercept**: m_bar is fully absorbed and cosmetic, but K0_MATCHED[A01] is a one-parameter
  refit, NOT the incumbent — delta_MAE then measures something other than "arm vs incumbent", and
  the exact-recovery premise in the link derivation fails as stated (containment still holds, so
  the LOG conclusion survives; the gate's meaning does not).

P35 must pin intercept presence/absence per arm and per null. Until it does, A01's primary gate is
ambiguous between two different comparisons.

### B-3. The quasi-Poisson self-freeze cites, but does not dispose of, the V2 record that RETIRED count/Poisson GLMs

`V2_STOP_CONDITION.json` → `not_stop_conditions_but_recorded.retired_families_with_bounds`:
"count/Poisson GLMs (target dispersion ratio 0.193 — UNDER-dispersed …) … NOT verified by the
coordinator." P33 borrows the 0.193 figure from this exact note while freezing quasi-Poisson IRLS
as the estimation objective — without stating why the retirement does not bind. The defensible
disposal exists and should be written down at P35: V2 retired Poisson GLMs **as challenger
response families for replacing the incumbent point estimator**; P33 uses the quasi-Poisson score
equations **as a shared fitting scaffold for testing additive terms beside a frozen offset**,
identically on arm and null, with all inference by cluster bootstrap. As it stands the
preregistration silently re-admits a family its own cited source retired — a document-vs-document
tension reported per standing rule 1.

On the substance I verified the freeze is **coherent** (attacked, did not break):

* The target is continuous non-negative (OT rescale, `possession_features.py` lines 210–211);
  quasi-likelihood score equations require no integer support. No zero-target rows exist in this
  universe, so the quasi-deviance convergence criterion is well-defined.
* Constant under-dispersion (Var ≈ 0.193·mu) **cancels exactly** from the IRLS score equations
  (weights ∝ 1/mu either way): point estimates are invariant to the dispersion constant, so the
  draft's "dispersion biases only likelihood SEs, never used" is correct and in fact understated —
  under proportional under-dispersion the 1/mu working weights are also efficiency-correct up to
  the cancelled constant.
* Exp-link + cluster bootstrap: coherent; the bootstrap resamples whole game clusters, the offset
  is cluster-constant (measured, §4), so no draw can split the exposure structure.
* Residual note, deferred to the operational-relevance reviewer: the primary gate is MAE while the
  fit objective targets the conditional mean; the mismatch is symmetric in arm and null and frozen
  in advance, so it is not an offset-dimension defect.

---

## 4. THE A02 IDENTITY: by construction, not coincidence (question answered with bytes)

The dimension brief asked whether `(own_est − opp_est) == pace_gap` — and A02's declared
non-offset-dependence — holds by construction or by coincidence of this dataset. **By
construction, at three separately verified levels:**

1. **`pace_gap` is defined as that difference.** `possession_features.py` line 315:
   `F["pace_gap"] = F["team_pace_estimate"] - F["opp_pace_estimate"]`. The == is definitional
   given the pairing merge (lines 275–289), which fails closed unless every game has exactly one
   opponent per side. Measured max dev **0.0**. (P25 `TESTS.py` lines 60–71 build `opp_est` as
   game-sum-minus-own — algebraically identical for two-row games; the two constructions agree.)
2. **The blend identity is a producer invariant, not a dataset fact.**
   `build_projected_exposure.py` lines 320–328: `projected_team_off_possessions` is constructed as
   the per-game **mean of the two sides' `team_pace_estimate`**, merged m:1 onto both rows, with a
   hard `ProducerFailure` unless every game has exactly two sides, and game-level NaN (dropping
   BOTH rows via `pace_resolved`) if either side is unresolved. Hence `own + opp == 2·projected`
   (measured **0.0** on all 2,982 rows) holds in every fallback tier by code path, and the offset
   is **cluster-constant by construction** — measured: all 1,491 games carry exactly one distinct
   projection value.
3. **Exact orthogonality to the offset is then algebra, not luck.** Within each game the two rows'
   gaps are ±d (measured: max |per-game gap sum| = **0.0**) while `log_exposure` is
   cluster-constant, so the sample covariance cancels game-by-game **exactly** — in any row set
   composed of whole games. Measured per training fold: corr(pace_gap, log_exposure) between
   −1.4e−18 and +1.7e−18 (float noise), R² ≈ 0, reproducing P33's numbers independently.

**The load-bearing caveat P33 does not state:** the exactness is conditional on the
games-never-split invariant. I verified `train_clusters == train_rows/2` in all five folds, and
the cluster bootstrap carries both rows by construction — so the condition holds everywhere the
preregistration operates. But any future subsetting that splits clusters (a stratum analysis, a
row-level diagnostic) voids the exact-zero and A02's "measured 0.0" must not be quoted for such
subsets. Record this with the arm.

Guard confirmation (frozen bytes, Appendix): A02's design `[log_exposure | pace_gap]` **passes**
under SUBSTANTIVE with `incumbent_projection` supplied; the forbidden pair `{own_est, opp_est}`
**blocks** with `pair_reconstructs_offset` — the guard's asymmetric treatment of pair vs contrast
works exactly as the P25 receipt claims.

---

## 5. SEVERITY C FINDINGS (record)

* **C-1. Exact-recovery gloss is loose.** "Every arm's nested null must recover the incumbent
  EXACTLY at zero treatment" is false as stated for every null carrying free parameters (A04, A07,
  A11–A15, …): a fitted null does not sit at the incumbent. The property that actually pins the
  link is **containment** — the incumbent must be a point of every null family — which holds iff
  the link is log given the log-scale offset. Same conclusion, correct premise. P35 should restate.
* **C-2. Citation (3) is cross-lane.** GATE_INVOCATION_CONTRACT §3.1's offset row reads "every
  TURNOVER arm carries log(exposure) (and log(D)) in the offset" (line 117). P33 calls this "the
  program-wide convention"; it is a turnover-lane sentence and the `log(D)` half does not even
  apply to the possession lane. Harmless — citations (1)+(2) carry the derivation alone — but the
  overreach should not survive into the frozen preregistration.
* **C-3. m_bar centering is fold-safe; under the no-intercept reading it is also load-bearing.**
  m_bar is a training-fold-only statistic of cutoff-valid values applied as a constant to test
  rows — no leakage channel (verified by construction of `chronological_folds` + the definition).
  Measured per fold: 4.377434 / 4.377799 / 4.378700 / 4.377825 / 4.374304. Under the no-intercept
  reading (B-2) different m_bar means genuinely different one-parameter families per fold;
  cross-fold delta-hat sign comparisons implicitly assume m_bar stability, which is empirically
  tight here (range 0.0044 log units ≈ 0.44%). A04 is immune: with the SHALLOW main in both arm
  and null, any shift of the interaction's centering constant is absorbed exactly by the tier main.
* **C-4. A02's mechanism gloss is first-order only.** gamma = 0 recovers the equal-weight blend
  exactly (verified algebra), but nonzero gamma gives `mu = P·exp(gamma·gap)` — a multiplicative
  surrogate, not a natural-scale reweighted blend `w·own + (1−w)·opp`. The preregistered test is
  fine; the interpretation of gamma as "the optimal blend weight exceeds one half" is approximate
  and should be recorded as such.
* **C-5. A02 contrast-record mismatch.** P25's frozen `PREREGISTERED_CONTRASTS.json` registers the
  column under the name `contrast_own_minus_opp_pace_estimate` with
  `offset_it_is_audited_against: projected_team_off_possessions` (natural scale). P33 names the
  treatment column `pace_gap` and invokes the guard with `offset = log_exposure`. The guard's
  formula-reproduction check fires only for columns whose NAME matches a registered record (or is
  prefixed `contrast_`): if P36 ships the column as `pace_gap`, the check never fires; if it ships
  the registered name, the record's declared audit offset differs from the invocation offset. Pin
  the P36 column name to the registered record (or re-register under `pace_gap`) and restate the
  record's audit offset as `log_exposure` at P35 so the contrast discipline actually executes.
* **C-6. P25 lessons elsewhere: applied.** Every arm whose treatment is built from the same
  evidence stream as the offset (A08 L_t, A09 w(n)·d_t, A10 c_t, A16 dev contrast, A17/A26 shares,
  A18/A20) carries an explicit P25 invocation and a withdrawal-on-rejection kill; A24/A25 carry
  the positive-control roles. The A04/A09 near-affinity test is frozen decidably for the P25 call
  site. Outside A01/A04 (findings A-1/A-2) I found no arm where an offset-dependency lesson that
  binds was skipped.

---

## 6. What I could NOT establish

* Whether the intended semantics of `k0_carries_offset_slope` for declared-recalibration arms
  differs from the guard bytes' plain reading. The P25 FINDINGS/TESTS exercise the RECALIBRATION
  path only with `cal`-style columns and complete declarations; no test fixes the intended truth
  conditions of the key against a slope-fixed null. Only the guard author's intent could differ
  from the bytes, and the bytes govern.
* Whether the P36 implementation will hand the guard per-fold designs with per-fold m_bar (the
  audit here used per-fold and pooled centering; both give R² = 1.0 identically, so no conclusion
  changes) — the invocation wiring is P35/P36 scope.
* Anything about fitted behaviour: nothing was fitted, no SEALED_RESULTS read, no performance
  number computed or seen.

## 7. Contradictions found (documents vs bytes / documents vs documents)

1. P33 SPEC (A01/A04 "fit-ready, all five folds evaluable") vs frozen `offset_dependency_guard.py`
   bytes (both arms blocked at invocation) — findings A-1/A-2.
2. P33's "program-wide convention" gloss vs GATE_INVOCATION_CONTRACT §3.1's actual turnover-lane
   wording — finding C-2.
3. P33's quasi-Poisson freeze vs V2_STOP_CONDITION's retired-families record it cites — finding B-3.
4. P33 "nested null recovers the incumbent EXACTLY at zero treatment" vs the actual free-parameter
   nulls of A04, A07, A11–A15 — finding C-1.
5. P25 PREREGISTERED_CONTRASTS.json (name + natural-scale audit offset) vs P33 A02 (name
   `pace_gap`, log-scale invocation offset) — finding C-5.

## 8. Verdict

**ACCEPT_WITH_REQUIRED_CHANGES**, with the stop-condition raise stated at the top. The offset
resolution itself (link = LOG) is byte-verified and stands. A02's non-offset-dependence is proven
by construction, not coincidence. The quasi-Poisson self-freeze is substantively coherent but must
dispose of the retirement record it cites. A01 and A04 are not fittable under the frozen guard as
preregistered: each must be withdrawn, or the conflict adjudicated above this node before the P35
task-card freeze.

Required changes:
1. Resolve A-1 (A01): withdraw, or escalate the guard-vs-K0 conflict for adjudication above this node.
2. Resolve A-2 (A04): withdraw, or escalate identically.
3. Pin per-arm `declared_family` and complete, TRUTHFUL recalibration declarations for every P25 invocation (B-1).
4. Define the intercept structure per arm and per null (B-2).
5. State the disposal of the V2 retired-families note against the quasi-Poisson freeze (B-3).
6. Reconcile the A02 contrast preregistration record's name and audit offset (C-5).

---

## Appendix — measurement script (run verbatim; feature/schedule columns only; nothing fitted)

Run as: `python p34_offset_review_measurements.py` from the repo root, with the script body below.
All numbers in this review come from this script's single run plus `Get-FileHash` and file reads.

```python
#!/usr/bin/env python3
"""P34 offset-dependence reviewer measurements.

Feature/schedule-only. No target values enter any statistic. Nothing is fitted.
No performance number is computed. The only model-adjacent calls are invocations
of the frozen offset_dependency_guard (a pre-fit, fit-free design audit).
"""
import json, sys
from pathlib import Path
import numpy as np
import pandas as pd

PP = Path("experiments/player_program").resolve()
sys.path.insert(0, str(PP))
sys.path.insert(0, str(PP / "stage2b" / "P25_OFFSET_DEPENDENCY_GUARD"))

import possession_features as pf
import offset_dependency_guard as G

OUT = {}
u = pf.load_universe()
F = u.frame
folds = pf.chronological_folds(u)
OUT["universe"] = {"rows": int(len(F)), "clusters": int(F["game_id"].nunique())}

off = F[pf.OFFSET_COLUMN].to_numpy(float)
proj = F["projected_team_off_possessions"].to_numpy(float)
own = F["team_pace_estimate"].to_numpy(float)
opp = F["opp_pace_estimate"].to_numpy(float)
gap = F["pace_gap"].to_numpy(float)

OUT["offset_equals_log_projection_maxdev"] = float(np.max(np.abs(off - np.log(proj))))
OUT["own_plus_opp_equals_2projected_maxdev"] = float(np.max(np.abs(own + opp - 2 * proj)))
OUT["own_minus_opp_equals_pace_gap_maxdev"] = float(np.max(np.abs((own - opp) - gap)))

per_game_nunique = F.groupby("game_id")["projected_team_off_possessions"].nunique()
OUT["offset_cluster_constant"] = bool((per_game_nunique == 1).all())
OUT["max_abs_within_game_gap_sum"] = float(F.groupby("game_id")["pace_gap"].sum().abs().max())

fold_rows = {}
for f in folds:
    tr = F.loc[f.train_index]
    o = tr[pf.OFFSET_COLUMN].to_numpy(float)
    g = tr["pace_gap"].to_numpy(float)
    m_bar = float(o.mean())
    c = o - m_bar
    fold_rows[f.fold_id] = {
        "n_train_rows": int(len(tr)),
        "train_clusters_eq_rows_over_2": bool(tr["game_id"].nunique() * 2 == len(tr)),
        "m_bar_train_mean_log_exposure": round(m_bar, 6),
        "r2_centered_offset_on_offset": float(G._r2(c, [o])),
        "spearman_centered_offset_vs_projection": float(
            G._spearman(c, tr["projected_team_off_possessions"].to_numpy(float))),
        "corr_pace_gap_log_exposure": float(np.corrcoef(g, o)[0, 1]),
        "r2_offset_on_pace_gap": float(G._r2(o, [g])),
    }
OUT["per_training_fold"] = fold_rows

season_fold_ids = F["season"].to_numpy()
def kinds(rec):
    return sorted({b["kind"] for b in rec["blocking"]})

X = pd.DataFrame(index=F.index); X["centered_off"] = off - off.mean()
recal_decl = {"family_id": "F01_CAL_GLOBAL_GAIN", "nested_null_id": "K0_MATCHED[A01]",
              "k0_carries_offset_slope": True, "n_hypotheses_in_family": 7,
              "multiplicity_procedure": "holm", "family_alpha": 0.05}
recal_decl_false = dict(recal_decl, k0_carries_offset_slope=False)
a01_sub = G.audit_augmented_design(X, ["centered_off"], off, incumbent_projection=proj,
    fold_ids=season_fold_ids, declared_family=G.SUBSTANTIVE, raise_on_block=False)
a01_rt = G.audit_augmented_design(X, ["centered_off"], off, incumbent_projection=proj,
    fold_ids=season_fold_ids, declared_family=G.RECALIBRATION,
    recalibration_declaration=recal_decl, raise_on_block=False)
a01_rf = G.audit_augmented_design(X, ["centered_off"], off, incumbent_projection=proj,
    fold_ids=season_fold_ids, declared_family=G.RECALIBRATION,
    recalibration_declaration=recal_decl_false, raise_on_block=False)
OUT["guard_A01"] = {"SUBSTANTIVE": {"passed": a01_sub["passed"], "blocking_kinds": kinds(a01_sub)},
    "RECALIBRATION_k0slope_True": {"passed": a01_rt["passed"], "blocking_kinds": kinds(a01_rt)},
    "RECALIBRATION_k0slope_False": {"passed": a01_rf["passed"], "blocking_kinds": kinds(a01_rf)}}

X4 = pd.DataFrame(index=F.index)
X4["shallow"] = (F["pace_evidence_depth"] <= 3).astype(float)
X4["centered_off"] = off - off.mean()
X4["shallow_x_centered_off"] = X4["shallow"] * X4["centered_off"]
a04_sub = G.audit_augmented_design(X4, ["shallow_x_centered_off"], off,
    nuisance_features=["shallow", "centered_off"], incumbent_projection=proj,
    fold_ids=season_fold_ids, declared_family=G.SUBSTANTIVE, raise_on_block=False)
a04_rec = G.audit_augmented_design(X4, ["shallow_x_centered_off"], off,
    nuisance_features=["shallow", "centered_off"], incumbent_projection=proj,
    fold_ids=season_fold_ids, declared_family=G.RECALIBRATION,
    recalibration_declaration=recal_decl, raise_on_block=False)
OUT["guard_A04"] = {"SUBSTANTIVE": {"passed": a04_sub["passed"], "blocking_kinds": kinds(a04_sub)},
    "RECALIBRATION_full_decl": {"passed": a04_rec["passed"], "blocking_kinds": kinds(a04_rec)}}

X2 = pd.DataFrame(index=F.index); X2["pace_gap"] = gap
a02 = G.audit_augmented_design(X2, ["pace_gap"], off, incumbent_projection=proj,
    fold_ids=season_fold_ids, declared_family=G.SUBSTANTIVE, raise_on_block=False)
OUT["guard_A02"] = {"SUBSTANTIVE": {"passed": a02["passed"], "blocking_kinds": kinds(a02)}}

XP = pd.DataFrame(index=F.index); XP["own_est"] = own; XP["opp_est"] = opp
pr = G.audit_augmented_design(XP, ["own_est", "opp_est"], off, incumbent_projection=proj,
    fold_ids=season_fold_ids, declared_family=G.SUBSTANTIVE, raise_on_block=False)
OUT["guard_pair_own_opp"] = {"passed": pr["passed"], "blocking_kinds": kinds(pr)}

print(json.dumps(OUT, indent=2, default=str))
```

Key raw outputs of the run (verbatim): all three identity max-devs `0.0`;
`offset_cluster_constant: true`; `max_abs_within_game_gap_sum: 0.0`;
`r2_centered_offset_on_offset: 1.0` in all five folds;
corr(pace_gap, log_exposure) in [−1.4e−18, +1.7e−18] across folds;
guard verdicts exactly as tabulated in findings A-1, A-2, and section 4.
