#!/usr/bin/env python3
"""build_report.py -- emits REPORT.md for P28. The report text is the deliverable; this file is
the generator so the exact bytes are reproducible.

Run: python experiments/player_program/stage2b/P28_PRIMARY_SECONDARY_ORDERING_CONTRACT/build_report.py
"""
from pathlib import Path

REPORT = r"""# P28_PRIMARY_SECONDARY_ORDERING_CONTRACT — possession-first adjudication; the OT-mismatch arbitrage channel is prohibited

**Node:** `P28_PRIMARY_SECONDARY_ORDERING_CONTRACT` · **Lane:** possession · **Type:** documentation ·
**Severity on failure:** A · **Role:** adjudication methodologist ·
**Addresses:** the V2 stop-condition record `E5_scorer_mismatch_is_exploitable_not_merely_documented`
(with measured bearing on **S4**, **S6**, **S9**, and on the recorded caveat
`OT_stratum_lower_MAE_may_be_a_units_artifact`).

## Epistemic status of this output

> CONTRACT. Fixes the order in which evidence may be consulted. Prevents a secondary number from rescuing a primary failure; decides no arm's fate itself.

---

## 0. Files this node produced

| file | what it is |
|---|---|
| `REPORT.md` | this document: the contract, every measurement, every contradiction |
| `FINDINGS.json` | the machine-readable finding set |
| `ordering_contract.py` | the **call-site** wrapper that enforces R1-R8. It edits nothing and patches nothing |
| `TESTS.py` | 86 assertions across 28 tests, standalone, `main()` returns 1 on failure |
| `MEASURE.py` / `MEASUREMENTS.json` | every number below, re-derived from the frozen artifacts |
| `build_report.py` | the generator for this file |

Nothing frozen was edited. No mutating git command was run — the only git invocation in this node
was `git rev-parse --abbrev-ref HEAD` (read-only), to confirm the worktree is `player-model-program`.

Reproduce everything:

```
python experiments/player_program/stage2b/P28_PRIMARY_SECONDARY_ORDERING_CONTRACT/MEASURE.py
python experiments/player_program/stage2b/P28_PRIMARY_SECONDARY_ORDERING_CONTRACT/TESTS.py
```

`TESTS.py` prints `86 assertions across 28 tests` / `all assertions passed`, exit 0.

---

## 1. The contract

### 1.0 Two objects, named once and never conflated

* **PRIMARY TARGET** — `REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS`. Metric: MAE. Lower is
  better. `primary_delta_vs_k0 = challenger - K0_MATCHED[arm_id]`; **negative is an improvement**.
* **SECONDARY DOWNSTREAM METRIC** — any turnover figure produced through the frozen scorer
  `run_turnover_p1_universe_fix.py:149`, which pairs regulation-equivalent projected exposure with
  **RAW full-game turnovers**.

The contract is about the **order** in which those two may be consulted, and about one benefit
channel that exists only because they disagree.

### 1.1 R1 — PRIMARY GATE FIRST

> A candidate must pass its **registered PRIMARY possession-target gate**, against its own
> per-arm `K0_MATCHED[arm_id]` (P26), before it may enter the frozen turnover scorer.

`K0_FLAT` does not discharge this. A pooled primary verdict does not discharge it either: the
verdict record must carry a per-fold block, per `GATE_INVOCATION_CONTRACT` section 1.
Enforced by `ordering_contract.authorize_downstream`, which refuses an unsealed or failing record.

### 1.2 R2 — SEAL BEFORE COMPUTE

> The primary verdict is **frozen — content-addressed — before any downstream number is computed
> at all.** The downstream receipt must bind that digest.

`seal_primary_verdict` refuses a record whose `downstream_computed` is not `False`. The digest is a
sha256 over a canonical JSON rendering of the verdict fields, so re-writing any primary figure after
the fact breaks the binding. `validate_downstream_receipt` **recomputes** the digest from the
primary record's own bytes rather than trusting the stored one, so a tampered record that carries
its old digest is caught (`primary_verdict_mutated_after_sealing`).

The point is not ceremony. An unsealed primary verdict lets the downstream figure act as an
**unregistered tiebreaker** — the author sees both numbers and decides afterwards which one the
task card "really" meant.

### 1.3 R3 — NO DOWNSTREAM RESCUE

> No downstream number may rescue a primary FAIL.

`adjudicate()` has **no code path that reads a downstream figure when the primary verdict is not
PASS**. This is asserted structurally, not by inspection: `T24` supplies four different downstream
figures (0.0, 0.1, 0.5, 5.0) to a failing candidate and requires the adjudication output to be
byte-identical across all four.

### 1.4 R4 — WORSENING THE PRIMARY TARGET IS TERMINAL

> A candidate improving downstream turnover MAE while **WORSENING** the primary
> regulation-equivalent possession target **FAILS**.

`primary_delta_vs_k0 > 0` means the record may only be `FAIL`; declaring it `PASS` raises
`worsening_primary_not_marked_FAIL`. An improvement smaller than the pre-registered MED is also not
a pass, and the MED must be flagged as registered **before** fitting.

Section 2.5 measures why this rule is the whole contract: across **692 perturbation values in each
of four families, there is not one at which both metrics improve.** Every downstream gain available
through this channel is bought with a primary-target loss.

### 1.5 R5 — THE ARBITRAGE CHANNEL MAY NOT BE CREDITED

> Trailing overtime rate, or any feature whose **only** benefit channel is arbitraging the
> raw/regulation-equivalent exposure mismatch, may not be credited.

Operationalised two ways, because either alone is defeatable:

1. **Declaration.** Every declared feature must name its benefit channel(s). A feature whose sole
   declared channel is `ot_mismatch_arbitrage` is not creditable.
2. **Carrier recognition.** A name matching the presumptive-carrier patterns (trailing OT rate, OT
   propensity, OT-corrected pace window, `game_minutes`, `max_period`, duration, OT-adjusted
   exposure, raw-possession gap, explicit mismatch indicators) is not creditable **unless** a
   non-mismatch channel is demonstrated **on the PRIMARY target** and carries a named adjudication.

The rule prohibits the **channel**, not a name list. The name list is a tripwire; the load-bearing
clause is "only benefit channel". Section 2.6 shows why that distinction matters: the feature E5
actually names turns out to be a *weak* carrier in this panel, while the channel it exploits is
large.

R5 blocks a **PASS**; it does not block sealing a **FAIL**. A rejected candidate must still be
recordable, or the program loses its negative results.

### 1.6 R6 — THE MISMATCH IS RESTATED, NOT REPAIRED

> The scorer is **frozen**. `run_turnover_p1_universe_fix.py` is not edited, its exposure column is
> not swapped, and turnovers are not rescaled by `game_minutes` to "fix" the pairing.

Every downstream receipt must carry the scorer's file, line, sha256 and `modified: False`, and must
restate the documented mismatch **verbatim** — including its `disposition`,
`"RESTATED, NOT REPAIRED. The scorer is frozen."`. `T14` shows that changing the disposition to
`"REPAIRED: turnovers rescaled to regulation-equivalent"` is refused, and `T26` re-checks the pinned
sha256 against the file on disk.

### 1.7 R7 — DOWNSTREAM IS REPORTABLE, NEVER DECISIVE

`epistemic_role` is pinned to `secondary_diagnostic` and `may_overturn_primary` to `False`; both are
refused if relabelled. OT and non-OT strata must each be reported **with their row and cluster
counts** — the packet's own reporting requirement, enforced here rather than asserted.

### 1.8 R8 — "PRIMARY" IS DISAMBIGUATED

`comparison_gate.py` names `challenger_vs_k0` the **primary incremental test** — that is a primary
**CONTRAST** (which two sides are compared). This contract's "primary" is a primary **TARGET**
(which outcome the metric is computed against). Measured: the string `primary_incremental_test`
occurs **2** times in `comparison_gate.py` (block `M8`), and `SideSpec` has **no** `target` field. Both senses
must hold. Neither substitutes for the other. This report never uses the bare word.

---

## 2. What I measured

Every number below comes from `MEASURE.py` run against the frozen bytes. Artifact digests
(`MEASUREMENTS.json`, block `M0`):

| artifact | sha256 |
|---|---|
| `projected_exposure_v1/team_possession_prior_v1.parquet` | `c37c075148553920b79c9320ea03afb37986bfc752fc84dd695f154887c3db18` |
| `possessions_v2/possessions_raw_v2.parquet` | `7200881fd811db9d0d6b10ea0a19b01ec7b6d027ee4567b9ef963241b15a4b1a` |
| `turnover_targets_v1/team_turnover_reconciliation_v1.parquet` | `446af16c237d59cc52a5294862ce60a2977522e14500370ec843cc29baae6e93` |
| `run_turnover_p1_universe_fix.py` | `612e0543a98f2ef945b7e92ff6b0c75679f5c8253f0a983a031918b993d57338` |

The first two match the digests P26 independently reverified against `EVIDENCE_PACKET_V2`.

### 2.1 The universe — AGREES

`MEASURE.py` block `M2`. Read `team_possession_prior_v1.parquet` (2,990 rows), join realised
possessions from `possessions_raw_v2.parquet`, keep `pace_resolved`.

| quantity | measured | packet | verdict |
|---|---:|---:|---|
| team-game rows | **2,982** | 2,982 | AGREES |
| game clusters | **1,491** | 1,491 | AGREES |
| rows dropped from the published 2,990 | 8 | — | — |
| games in the possessions artifact | **1,495** | 1,495 | AGREES |
| overtime games | **66** | 66 | AGREES |
| OT game rate | **0.044147** | 0.04415 | AGREES |

OT composition: **60** games at `max_period = 5`, **5** at 6, **1** at 8. The stratum is not
homogeneous, which matters in 3.5 below.

The 1,491 / 1,495 pair the V2 stop condition flags as a nit is confirmed as **two correct figures
over different universes**: 1,491 clusters is the prediction universe (2,982 rows); 1,495 is every
game in the possessions artifact, including the 4 whose projection is unresolved. Both reproduce.
No numeric error; a wording hazard only, and the packet is frozen and is not edited.

### 2.2 The frozen scorer's pairing — AGREES

`MEASURE.py` block `M1`. Line 149 of `run_turnover_p1_universe_fix.py`, read from the bytes:

```
expo_t = g["team_off_possessions"] if name == "intrinsic" else g["projected_team_off_possessions"]
```

The operational track selects `projected_team_off_possessions`, which is regulation-equivalent. The
outcome it is scored against is the realised **RAW** full-game turnover total. Measured:
**no line anywhere in the scorer references `game_minutes`**, so nothing rescales the turnover side.
The mismatch the packet documents is present exactly as recorded.

### 2.3 The mismatch, re-derived — AGREES on all 16 stated figures

`MEASURE.py` block `M3`. Every figure in
`EVIDENCE_PACKET_V2.downstream_operational_boundary.measured_mismatch` reproduces to the last
stated digit.

| | regulation | overtime |
|---|---:|---:|
| rows | **2,850** | **132** |
| game clusters | **1,425** | **66** |
| MAE vs reg-equiv target | **2.92806** | **2.36744** |
| MAE vs RAW target | **2.92806** | **10.51782** |
| bias vs reg-equiv | **0.14147** | **0.54129** |
| bias vs RAW | **0.14147** | **-10.51510** |
| mean realised reg-equiv | **79.3053** | **78.9057** |
| mean realised raw | **79.3053** | **89.9621** |

All sixteen AGREE with the packet (delta 0.0 on every one).

Derived here and not stated in the packet: pooled MAE vs reg-equiv **2.90325**, pooled MAE vs RAW
**3.26403**; and the accounting gap itself — `raw - reg_equiv` is **11.0564** possessions on OT rows
and **exactly 0.0** on all 2,850 non-OT rows. That zero is why the channel is targetable: the
mismatch is not noise spread over the panel, it is a step function on 4.4% of it.

### 2.4 The propagation coefficient — AGREES, on a denominator the packet does not state

`MEASURE.py` block `M4`. The packet's `implied_team_tov_rate` block does not say what the
denominator is, so I computed five candidates and reported which reproduces it:

| definition | mean | vs packet mean 0.17733 |
|---|---:|---|
| `team_turnovers_total / reg_equiv possessions` | **0.17733** | **AGREES** (sd, p05, p50, p95 all AGREE exactly) |
| `team_turnovers_total / raw possessions` | 0.17624 | CORRECTS by -0.00109 |
| `player_attributed / raw` | 0.16435 | CORRECTS |
| `player_attributed / reg_equiv` | 0.16536 | CORRECTS |

So the packet's figures are **exactly right** and the coefficient is `0.17733`. What is worth
recording is that the propagation coefficient is computed on the **regulation-equivalent**
denominator while the scorer's outcome side is **RAW** — the same asymmetry the contract exists to
police, appearing one level up in the diagnostics. See C1.

All downstream figures below use each row's own realised rate on that definition.

### 2.5 The arbitrage — MEASURED, and it is always a primary-target trade

`MEASURE.py` block `M6`. Closed-form deterministic perturbations of the frozen incumbent
projection, `proj_lambda = proj * m(lambda)`. **These are counterexample constructions, not fitted
arms, not registered challengers.** No challenger's comparative historical performance was
inspected and nothing under `stage2b/SEALED_RESULTS/` was read.

* **Primary metric:** MAE of the projection against the regulation-equivalent target.
* **Downstream metric:** the packet's own mechanical propagation through the frozen pairing,
  `mean |realised_rate * (projected_reg_equiv_exposure - RAW possessions)|`.

Baseline (lambda = 0): primary **2.903246**, downstream **0.591919** (OT rows 2.170689, non-OT
0.518797).

Fine scan, 692 lambda values per family:

| family | carrier | admissible? | lambdas with arbitrage | **lambdas where BOTH improve** | best downstream gain | primary cost |
|---|---|---|---:|---:|---:|---:|
| `uniform_inflation` | none (a constant scale) | yes | 28 | **0** | -0.000240 (-0.041%) | +0.006983 |
| `trailing_ot_rate_uncentered` | trailing OT rate | yes | 92 | **0** | -0.000019 (-0.003%) | +0.000505 |
| `trailing_ot_rate_centered` | trailing OT rate, mean-preserving | yes | 0 | **0** | none | none |
| `ORACLE_target_game_is_overtime` | the target game's realised OT — **PROHIBITED** | **no** | 542 | **0** | **-0.061099 (-10.32%)** | **+0.358761** |

Three things are established.

**(a) The channel is real and large.** Under perfect foreknowledge of overtime — the oracle, which
the ruling prohibits and which is included only to bound the channel — inflating the projection by
12.5% on OT rows moves the downstream turnover metric from 0.591919 to **0.530820**, a **10.32%
improvement**, while the primary possession MAE degrades from 2.903246 to **3.262007**. That is
exactly the failure E5 describes, measured on the frozen artifacts.

**(b) There is no lambda, in any family, at which both metrics improve.** 0 of 692 per family,
0 of 2,768 overall. Every gain available through this channel is *purchased* with a primary-target
loss. R4 is therefore not a conservative tie-breaking convention; on this data it is the *complete*
characterisation of the channel.

**(c) The gate cannot see it.** Section 2.6.

### 2.6 The named carrier passes every gate — and is weak in this panel

`MEASURE.py` block `M5`. I built trailing OT rate exactly as a challenger would: per team, the mean
of the OT indicator over its most recent 10 games with `game_date` **strictly earlier** than the
row's own. The target game's `max_period` never enters. 15 of 2,982 rows have no prior game; nulls
filled with 0.0, declared.

`feature_gate.audit` with **every** optional argument supplied (`offset=log(projection)`,
`target=reg-equiv realised`, `test_df=`, `outcome_mask=is_overtime`):

* final assembled design: `passed: true`, `findings: []`, `blocking: []`, rank 1 of 1, condition 1.0;
* **and on every one of the six chronological folds** (2021 n=410, 2022 n=478, 2023 n=520,
  2024 n=524, 2025 n=620, 2026 n=430): `passed: true`, no findings.

Correlations against the gate's own thresholds: with the target `0.02211` (threshold 0.98), with the
offset `0.05894` (threshold 0.999). Nothing is close. **No feature-matrix check in this repository
can block this feature, and none should — it is genuinely cutoff-valid.** That is precisely why the
prohibition has to be an ordering constraint at the adjudication layer rather than a gate finding.

**And now the negative result, preserved rather than smoothed over.** In this panel the trailing OT
rate does **not** predict target-game overtime:

* `corr(trailing_ot_rate, target-game is_overtime)` = **-0.02696**;
* mean trailing OT rate on OT rows **0.03671** vs non-OT rows **0.04562** — *lower* on the rows the
  exploit needs, by -0.00891, against a base rate of 0.04427.

Consequently the admissible carrier's maximum arbitrage is **1.9e-05** of downstream MAE (0.003%),
against the oracle's 0.0611 (10.32%) — roughly **three orders of magnitude** smaller. E5's
*mechanism* reproduces; E5's *named carrier* is, on this panel, a poor instrument for it.

This is not a licence to admit the feature, and the contract is not weakened by it. The channel is
large; only this particular key fits the lock badly. A better OT-propensity carrier — and the
program has not looked for one — would exploit the same channel. R5 therefore prohibits the
**channel**, with the name list as a tripwire, not the other way round.

### 2.7 What the frozen gates can and cannot represent

`MEASURE.py` block `M7`, by introspection of the modules themselves.

* `comparison_gate.DIMENSIONS` — **17** dimensions; none of them is a target, a metric identity or
  an ordering.
* `comparison_gate.SideSpec` — 22 fields; `target` **absent**, `metric` **absent**, no field
  containing "order".
* `comparison_gate.gain_report(metrics, *, lower_is_better=True, metric_name='metric', ...)` —
  `metric_name` is a **free string**. A possession MAE and a turnover MAE are indistinguishable to
  it.
* `feature_gate.BLOCKING` — 12 kinds, all properties of one matrix; no target-identity check.

**Neither frozen gate carries any representation of which target a metric was computed against, or
of the order in which two metrics were computed.** The ordering constraint is therefore not
implementable inside either gate — which is the right outcome, since section 7.2 of
`GATE_INVOCATION_CONTRACT` already says the gate audits one matrix and has no view of the
comparison. `ordering_contract.py` sits at the **call site**, exactly as the standing rules require.

---

## 3. Contradictions found

### C1 — the propagation coefficient's denominator is regulation-equivalent while the scorer's outcome is raw

`EVIDENCE_PACKET_V2.downstream_turnover_team_error.implied_team_tov_rate` reproduces **exactly**
(mean 0.17733, sd 0.04893, p05 0.1013, p50 0.175, p95 0.2597) only when the denominator is realised
**regulation-equivalent** possessions. The block does not state its denominator. The raw-denominator
version is 0.17624 — a 0.6% difference, immaterial to any conclusion here, but the *asymmetry* is
the same one this contract polices: a diagnostic that mixes the two exposure conventions.
**Not an error in the packet's numbers.** A documentation gap, recorded so a later reader does not
re-derive 0.17624 and conclude the packet is wrong.

### C2 — "uniform inflation loses on net" is not correct as stated

`V2_HYPOTHESES_adversarial.md` E5 states: *"Uniform inflation loses on net (4.4% of rows). But
inflation targeted at rows correlated with OT propensity wins."*

Measured: uniform inflation **wins marginally** over lambda in [0.0001, 0.0028], optimum
lambda = 0.0016, downstream -0.000240 (-0.041%) at a primary cost of +0.006983. The stated
intuition — that the 4.4% OT weight cannot pay for the 95.6% non-OT loss — is wrong at small lambda
because the non-OT error distribution is nearly symmetric about a small positive bias (+0.14147), so
the first-order cost of a small uniform inflation there is almost zero while the OT benefit is
first-order. **CORRECTS.**

The consequence is not cosmetic. It means the arbitrage channel is reachable by an arm carrying **no
feature at all** — a pure level or calibration-slope freedom. That is S4's territory (the free-SLOPE
confound that `comparison_gate` has no dimension for) and P26's `K0_MATCHED` invariants. P28 does
not resolve it; see section 5.

### C3 — E5's named carrier does not have the property E5 attributes to it

E5 asserts *"a team's trailing OT rate is a perfectly cutoff-valid lagged feature"* — confirmed,
measured, passes every gate on every fold — and that targeted inflation on it "wins". Measured, the
correlation of that carrier with target-game overtime is **-0.02696**, i.e. slightly *negative*, and
its maximum arbitrage is 1.9e-05 against the oracle's 0.0611. **CORRECTS the magnitude, confirms the
mechanism.** Preserved as a negative result. It does not weaken the contract; see 2.6.

### C4 — the "primary" collision between this contract and `comparison_gate.py`

`comparison_gate.py` uses `primary_incremental_test` (2 occurrences, block `M8`) and the prose
"THE PRIMARY TEST" for the **contrast** `challenger_vs_k0`. The ruling and the packet use "primary" for the **target**
`REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS`. A completion report saying "the primary test
passed" is ambiguous between them, and the two are independent conditions. No document disambiguates
them. R8 fixes the vocabulary inside P28's scope only; the collision itself remains in the shared
module, which is frozen and was not edited.

### C5 — the OT-stratum sd-compression figure depends on an unstated choice of statistic

`V2_STOP_CONDITION.not_stop_conditions_but_recorded.OT_stratum_lower_MAE_may_be_a_units_artifact`
gives "sd ratio 0.831 against the 40/45 = 0.889 compression factor". Measured (block `M9`):

* **signed**-error sd: OT 3.07361, non-OT 3.69921, ratio **0.83088** — the source's figure. AGREES,
  and identifies which statistic it used, which the source does not state.
* **absolute**-error sd: OT 2.02355, non-OT 2.26443, ratio **0.89363** — *above* 0.88889.
* the correct comparison factor is not 40/45: the OT stratum contains 60 single-OT, 5 double-OT and
  1 quadruple-OT game, so the mean realised scale factor over OT rows is **0.87879**, not 0.88889.

So whether "compression explains the gap" flips sign depending on which dispersion statistic is
compared, and the reference factor itself is slightly wrong. **CORRECTS the reference factor;
records that the conclusion is statistic-dependent.** P28 deliberately does **not** resolve this —
it forbids the downstream number from deciding anything, which is a weaker and safer claim than
adjudicating the OT stratum's difficulty.

---

## 4. What I could NOT establish

1. **Whether any actual challenger exhibits this arbitrage.** No challenger has been fitted in this
   wave. I am forbidden from inspecting comparative historical performance and did not read
   `stage2b/SEALED_RESULTS/`. Everything in 2.5 is a constructed perturbation of the frozen
   incumbent projection, and is labelled as such in `MEASUREMENTS.json`.

2. **The frozen scorer's own downstream metric was not reproduced.** I did **not** run
   `run_turnover_p1_universe_fix.py`. The downstream figures in 2.5 are the packet's *mechanical
   propagation* — the realised rate held fixed — not the scorer's per-player fitted output summed to
   team. The direction and the existence of the channel follow from the exposure/outcome pairing and
   are robust to that; the exact magnitudes would differ under the real scorer. Stated rather than
   papered over.

3. **Whether a *better* OT-propensity carrier exists among cutoff-valid columns.** I did not search
   for one. Doing so would be feature discovery against a downstream metric, which is the very thing
   this contract prohibits. The oracle bound (10.32%) is what a perfect carrier would be worth; how
   much of that is reachable from lagged information is unmeasured, and deliberately so.

4. **Whether R5's carrier-name patterns are complete.** They cannot be. A name list is a tripwire.
   The load-bearing clauses are the declared-channel rule and R4, both of which are name-independent.

5. **Dual-frame provenance (`GATE_INVOCATION_CONTRACT` section 8a).** The 2.6 gate audits supply a
   fully populated frame with a declared fill. Per the standing limitation, that reaches
   `RAW_PROVENANCE_ASSERTED`, not a full pass. The claim "trailing OT rate passes the gate" is an
   audit result on the frames I built, not a construction-provenance attestation.

---

## 5. Stop conditions — what I am raising rather than resolving

My brief halts me if a finding would change the primary target, the K0 structure, the inference
structure, the candidate universe, the cutoff-valid feature set, or the leakage status.

**Nothing in this node changes any of those, and I have not resolved anything belonging to another
node.** Stated plainly, in case a reader disagrees with that classification:

* **C2 bears on K0_MATCHED and on S4, and P28 does not resolve it.** That an arm with *no feature*
  can reach the arbitrage channel through a pure level or calibration-slope freedom is the S4
  free-SLOPE defect meeting the E5 mismatch channel. The remedy — pinning exposure level and
  calibration slope in `K0_MATCHED[arm_id]` — is P26's contract and S4's adjudication, not mine.
  **Raised, not resolved.** R4 makes the channel unprofitable regardless, since the primary target
  always worsens; but that is a backstop, not the fix.
* **C5 bears on the OT stratum's interpretation.** I decline to adjudicate it; P28 only forbids the
  downstream figure from deciding anything.
* **C3 is a magnitude correction to a recorded observation, not to a stop-condition finding.** The
  E5 entry sits in `not_stop_conditions_but_recorded`, and it stays there.

I do **not** propose editing `EVIDENCE_PACKET_V2.json`, `V2_STOP_CONDITION.json`,
`comparison_gate.py`, `feature_gate.py` or the frozen scorer. The packet is frozen; C1-C5 are
recorded here and in `FINDINGS.json` for the coordinator to dispose of.

---

## 6. How a candidate uses this

```python
import sys; sys.path.insert(0, "experiments/player_program/stage2b/P28_PRIMARY_SECONDARY_ORDERING_CONTRACT")
import ordering_contract as oc

sealed = oc.seal_primary_verdict(primary_verdict_record)   # raises on any R2/R4/R5 violation
auth   = oc.authorize_downstream(sealed)                   # raises unless the primary PASSED
# ---- only now may the frozen turnover scorer be run ----
oc.validate_downstream_receipt(downstream_receipt, sealed) # raises on R2/R6/R7 violation
verdict = oc.adjudicate(sealed, downstream_receipt)        # decided_by == "PRIMARY_TARGET_ONLY"
```

Every step fails **closed**: missing fields, unknown fields (so a typo cannot silently disable a
rule), broken bindings and relabelled roles all raise `OrderingContractFailure`.

## 7. Status

`LANDED` — files written, tests passing, not independently checked. Not `VERIFIED`. This node does
not mark its own work accepted, and it decides no arm's fate.
"""

if __name__ == "__main__":
    out = Path(__file__).resolve().parent / "REPORT.md"
    out.write_text(REPORT, encoding="utf-8")
    print(f"wrote {out} ({len(REPORT.encode('utf-8'))} bytes)")
