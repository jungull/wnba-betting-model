# Discovery wave 1 — consolidated summary

Eight discovery workstreams, four integrity workstreams, and a retrospective audit of the wave
against a feature gate that **did not exist when the wave ran**.

Derived from [`FINAL_AUDIT_MATRIX.json`](FINAL_AUDIT_MATRIX.json) and
[`RETROSPECTIVE_GATE_AUDIT.json`](RETROSPECTIVE_GATE_AUDIT.json). Where this summary and the
earlier handoff disagree, **the artifacts govern**.

**No challenger was registered. Arm D is unchanged. No arm was promoted.**

---

## 1. The four questions

Every result below is placed against four separate questions. Collapsing them is how a gate pass
gets mistaken for a valid decision, and how an oracle decomposition gets mistaken for a model.

| # | question | answered by |
|---|---|---|
| 1 | Was the feature **design** valid? | `feature_gate.py`, applied retrospectively |
| 2 | Was the **comparison** valid? | `comparison_gate.py` — Layer A vs matched K0 |
| 3 | Did the feature add value **beyond matched flexibility**? | challenger vs K0, never vs the incumbent alone |
| 4 | Is the result **operational, diagnostic, or hypothesis-generating**? | the matrix's evidence role |

A design can pass question 1 and still fail question 2. A result can pass both and contribute
nothing under question 3. A result can be entirely valid under all three and still be only
diagnostic under question 4 — WS8 is exactly that.

---

## 2. The governing fact about this wave

**The strengthened feature gate did not govern discovery wave 1.**

All eight result commits carry the pre-fix blob `a8a8ea64` from base `eb1103c`. Neither
`55f4500` (rank and conditioning) nor `42af2cd` (informative missingness) is an ancestor of any
of them — verified by `git merge-base --is-ancestor`, eight times, both fixes.

Every feature-design classification in the matrix is therefore a **retrospective application** of
the current gate. It is not a record of what ran. Three workstreams compensated by hand and said
so; that is credited per workstream, with citations, and never inferred globally.

A second fact of the same kind: `rank_check_ran_per_fold` is **false for every workstream** —
including WS1 and WS3, which wrote the rank checks but ran them pooled only. The retrospective
audit ran them per fold everywhere. It changed no conclusion; worst condition number on any
fitted design was 28.66.

---

## 3. Findings by status

### Valid as published
* **WS3** — two-stage team-total plus compositional allocation did not improve player identity
  under fixed team totals. A valid discovery null with a redirection.
* **WS4** — the time-scale family is falsified *in the opposite direction*: error is monotone in
  memory **length**, and faster adaptation helps in no stratum. No feature design exists here to
  be unidentified; this is a valid null, not an integrity failure.
* **WS5** — clean opportunity proxies fail as rate predictors; a small allocation-only value
  (~+0.0017, ~0.2%) survives at the player level.

### Valid only after a corrected rerun
* **WS1** — the original operational run was contaminated; `5313ebd` supersedes `3726991`.
* **WS7** — the original run leaked; the v2 rebuild supersedes it. `WS7_RESULTS_v1_leaky.json` is
  retained as contaminated evidence and must not be cited.

### Invalid as published
* **WS2** — the operational design encoded `did_appear` through **pre-gate imputation**. Its
  player-level operational positive is invalid; its aggregate conclusion is unresolved. See §5.

### Diagnostic only
* **WS6** — mechanism cancellation rejected as the cause; the real cause found. Architectural.
* **WS8** — oracle counterfactuals. Decisive on direction, and **not a model**.

### Contaminated originals, preserved not deleted
`3726991` (WS1) and `WS7_RESULTS_v1_leaky.json` (WS7) are kept as the record of what was
originally published. Superseded, cited as superseded, never silently replaced.

### Falsified hypotheses
WS1's projected-role formulation on the operational decision metric; WS4's faster-adaptation
premise, refuted in the opposite direction; WS5's expected direction for proxies as rate
predictors; WS7's primary-creator concentration hypothesis; WS6's mechanism-cancellation
explanation.

### Formulation-dependent nulls
Every null above is a null **under the tested formulation**, not in general. Each ledger entry
carries a `formulation_dependence` block naming the specific untested formulations that remain
live. A null that produces no challenger is still a valid result.

### Narrow discovery leads
1. Team-possession-total projection (WS8, corroborated by WS3's redirection).
2. Within-team versus between-team decomposition of involvement (WS6).
3. Clean allocation proxies under fixed team totals (WS5).

---

## 4. The role-expansion correction

The handoff ranked a gated role-expansion challenger second. **The corrected evidence does not
support that ranking**, and the figures behind it came from the contaminated run `3726991`.

Recorded exactly:

* `+0.02647` (sd 0.00175, positive in all five walk-forward folds) is a **fitted coefficient,
  not an MAE gain**.
* Intrinsic expansion-segment improvement versus K0 is `+0.01314` with CI `[-0.00032, +0.02771]`
  — **includes zero**.
* The operational material-expansion segment is **worse** than Arm D: `-0.00758` over 946
  team-games.
* The apparent operational gain outside the expansion segment (`+0.00632` over 1,968 team-games)
  **disappears against K0** (`-0.00089`, CI spans zero) — it was free flexibility.
* **No WS1 arm beats K0 with a confidence interval excluding zero.** WS1's own verdict block
  reads `falsifies`.
* The tested formulation is **falsified on the operational decision metric**.

What survives: *a genuinely cutoff-valid measure of player-specific responsibility transition
could still matter, but the tested role-expansion formulation does not currently justify a frozen
challenger.* The basketball hypothesis is retained; the tested formulation is not.

---

## 5. The WS2 correction

WS2's `build_constructions()` imputed to `0.0` **before** calling the gate. What reached the gate
was a fully populated design with no missingness at all, and it passed every fold. The mask
survived as a value:

| construction | non-zero on appearers | non-zero on the 8,278 non-appearers |
|---|---|---|
| `transfer_direct` | 25,522 | **0** |
| `transfer_allocated` | 25,522 | **0** |
| `transfer_role_sensitive` | 9,577 | **0** |

A non-zero value certifies appearance. `missingness_encodes_outcome` cannot fire on a frame with
no missingness.

Dispositions:

* original operational player-level positive (T1 +0.00178, T2 +0.00225 vs K0, CIs excluding
  zero) — **invalid**;
* original operational aggregate null — **invalid as published**; *not* claimed to survive
  a fortiori. Removing a favourable leak would usually weaken a positive, but refitting alters
  every coefficient and prediction, and no clean corrected aggregate exists;
* intrinsic result — classified **separately**; intrinsic training folds contain appearers only,
  so the operational appearance leak does not act there;
* responsibility-transfer directionality — **hypothesis-generating only**.

WS2 was **not** rerun: the conservative disposition — *invalid as published; formulation remains
unresolved operationally* — is reachable from the preserved artifacts.

---

## 6. Shared-contract defects found, and what was built

| defect | where it bit | contract built | commit |
|---|---|---|---|
| baseline parity — a challenger receiving flexibility its baseline lacks | P1/P2, ~+0.0033 team MAE | `comparison_gate.py` | `75ac7ba`, `b626d50` |
| stale **validation verdict** certifying prior bytes | turnover + event validation receipts | `receipt_integrity.py` | `7d7fc7b`, `88c128a` |
| gate arguments optional, silently disabling four checks | all eight workstreams | `gate_invocation.py` | `d58a6b2` |
| gate invocation timing — pooled audits hiding fold degeneracy | WS3 2022 fold | `GATE_INVOCATION_CONTRACT.md` | `507f62d` |
| P2 arms cited as valid evidence | E, I, F, G, H | `P2_SUPERSESSION.*` + 6 registry records | `507f62d` |

The free-intercept confound, stated precisely: *the challenger-only intercept created
approximately 0.0033 of unmatched flexibility, comparable in scale to the effects being
evaluated. Its own 90% interval includes zero, so it is not evidence that recalibration
definitively improves the forecast; it is evidence that the comparison could not attribute small
challenger gains to the substantive features.* A confound does not need to be independently
significant to invalidate attribution when it is the size of the reported effect.

The receipt defect, stated precisely: the **target** receipt matched the rebuilt artifacts
exactly; `TURNOVER_VALIDATION.json` was stale and certified prior artifact hashes;
`EVENT_VALIDATION.json` had the analogous stale-verdict condition; the repair regenerated
validation through the canonical paths; **no parquet bytes were modified**.

---

## 7. Remaining methodological gaps

1. **Dual-frame auditing — REQUIRED, NOT IMPLEMENTED.** The wrapper does not catch pre-gate
   transformation. A caller can supply a fully populated imputed design with valid, aligned
   arguments while withholding the raw frame. Specified in `GATE_INVOCATION_CONTRACT.md` §8a.
   **No claim is made that the invocation layer closes the WS2 class.**
2. **Validator lineage is incomplete.** `validate_turnover_targets.py` records the *producer*
   hash but not its own. Until validator identity is emitted and bound, validator-lineage proof
   is incomplete and **the chain is not cryptographically closed**. Required: validator source
   digest; unique validation-run ID; exact input manifest; output receipt bound to both;
   producing commit or environment identity.
3. **Fresh execution is not provable.** `fresh_execution_not_proven` fires only on positive
   duplication evidence and never asserts that validation did not run. Closing it needs a
   validator-emitted per-execution nonce.
4. **Nonlinear deterministic dependency.** The gate catches *linear* rank deficiency. A feature
   deterministic in others through a nonlinear map still passes.
5. **`pipeline_id` is asserted, not demonstrated.** `comparison_gate` cannot prove K0 came from
   the challenger's code path. Producer-source digest binding would close it.
6. **Comparison parity was absent for the whole wave**, and is uncontrolled in WS6, which has no
   featureless control of any kind.
7. **Concurrency.** Four agents shared one worktree. Isolation was verified from diffs — no file
   touched twice, final diff exactly reconstructable — but future parallel work returns to
   separate worktrees.

The gate does **not** detect every unidentified or leakage-prone construction. A passing gate
record is necessary, never sufficient.

---

## 8. Evidence-led ranking

Derived from the matrix.

1. **Team-possession-total projection** — the strongest remaining team-aggregate research
   opportunity. WS8 measures it at `+0.1033 [0.0833, 0.1244]`, the only materially addressable
   exposure error found; WS3 redirects to the same place independently.
2. **Within-team versus between-team involvement separation** — a strong architectural
   explanation and a possible future design direction. **Not a validated challenger.** The proxy
   is a share; 92.6% of its variance is within-team; within `+0.036`, between `-0.107`, reversal
   in 9 of 9 fitted mechanisms.
3. **Clean player-allocation proxies** — small player-level value (~+0.0017), limited team-total
   relevance. By construction they cannot move the team total: projected exposure sums to exactly
   5× projected team possessions.
4. **Role-transition and responsibility-transfer effects** — basketball-plausible but
   formulation-dependent, contaminated or adverse under the tested operational designs.
5. **Broad pooled turnover-rate feature expansion** — deprioritized.

**Items 2–4 are discovery directions, not promotion candidates.**

---

## 9. Conclusion

> Under the tested total-turnover formulations, broad pooled conditional-rate expansion is near
> its practical team-aggregate ceiling. The clearest remaining team-level opportunity is improved
> possession-total projection. Involvement information may still be useful when separated into
> within-team allocation and between-team total components, while role-transition and
> responsibility-transfer effects remain formulation-dependent rather than disproven.

Turnover research is **not** exhausted.

One asymmetry worth carrying: the 5× identity gives no cancellation at the **player** level,
where props settle. Non-appearing candidates carry **14.18%** of player-level absolute error.
That is an availability problem, not a turnover problem.

---

## 10. Stop boundary

In force. Not begun: any confirmation experiment; promotion of any discovery arm; alteration of
Arm D; alteration of canonical exposure; any further event channel.

The most defensible next substantive step, if authorised, is a registered improvement to
`team_possession_prior/1` — the only materially addressable team-aggregate error source found.
Its honest prize is small: 1.2–2.2% of operational MAE.
