# P2 SUPERSESSION — `turnover_rate_role_context_v1`

**Applies to:** `turnover_rate_role_context_v1` (arm id `turnover_rate_role_context/1`), registered at
commit `7cbfa9d`, executed `2026-08-04T12:32:37.732848Z`, results in `TURNOVER_P2_RESULTS.json`.

**Prepared:** `2026-08-04T13:59:19Z` at commit `0397fbd` on branch `player-model-program`.
**Machine-readable form:** `P2_SUPERSESSION.json`.
**Proposed registry records:** `PROPOSED_REGISTRY_RECORDS.jsonl` (the coordinator appends; this
workstream does not write `arm_registry.jsonl`).

---

## What this document is, and is not

This is a **supersession record**, recorded **forward**.

- **No commit is rewritten.** Not amended, not rebased, not edited. The P2 registration, its results
  JSON, its prediction parquets and its feature artifact are left exactly as they were.
- **Nothing is repaired and re-run.** Dropping a duplicated column, rebuilding a leaking column or
  matching an intercept *after results are visible* is a post-result design change. Every repair
  named below must be registered as a **new frozen challenger in a later wave**.
- **`arm_registry.jsonl` is not modified by this document.**
- **Arm D, canonical exposure, the canonical turnover target and `feature_gate.py` are untouched.**

The feature artifact's sha256 was checked at preparation and matches the receipt in
`TURNOVER_P2_RESULTS.json` (`5ab9160078771f6857cd332da9d3a1182e83ce4ab35b5dd8c2746b0be98b2072`).

---

## Per-arm status

| Arm | Features | Status | Basis |
|---|---|---|---|
| **A** | league constant | **VALID**, unchanged | control arm; carries no P2 feature |
| **D** | frozen P1 EWMA-shrunk | **VALID**, unchanged | not a P2 arm; not altered or re-adjudicated here |
| **E** | group 1, projected role (5) | **INVALID** — algebraic non-identifiability | numerical rank **4 of 5** |
| **F** | group 2, prior role (3) | **operational result INVALID** — missingness encoded `did_appear` | 8,278 null / 27,351 non-null, **zero off-diagonal** |
| **G** | group 3, offensive involvement (1) | published **player-level improvement INVALID AS PUBLISHED EVIDENCE** | leaking feature effect **0.0218** > reported gain **0.00137** |
| **H** | group 4, teammate context (1) | **NOT affected** by the null-mask defect; original comparison against Arm D **CONTAMINATED** | `displaced_involvement` fully populated; unmatched intercept worth **~+0.0033** |
| **I** | groups 1–4 united (10) | **INVALID** — algebraic non-identifiability | numerical rank **8 of 10** |

---

## Arms E and I — INVALID, algebraic non-identifiability

### The defect

Feature group 1 registered **both** `proj_minutes_share` **and** `proj_off_poss_share`. Under the v1
minutes-to-possession mapping, projected possessions are exactly `pace × minutes / 40`, so the two
are **the same column**.

Measured on the frozen feature artifact (35,629 rows):

| quantity | value |
|---|---|
| max absolute difference between the two columns | `5.551115123125783e-17` (representation noise only) |
| Pearson correlation | `1.0` |
| standard deviation, both columns | `0.048326312796813625` (ddof 1) — identical |
| min / max, both columns | `0.00037672499999999995` / `0.2` — identical |

### Measured rank

Recomputed at commit `0397fbd` with `feature_gate.design_rank_report`:

| arm | declared features | numerical rank | full rank? | smallest singular value | condition number |
|---|---|---|---|---|---|
| **E** | 5 | **4** | no | `0.0` | `1.4012e15` |
| **I** | 10 | **8** | no | `0.0` (two of them) | `1.1738e16` |

Arm I carries a **second, independent** exact dependency:
`role_change == proj_minutes_share − trailing_minutes_share`, with maximum absolute deviation
**`0.0`** across all 27,351 rows where `role_change` is defined. Ten declared features span eight
dimensions.

### Consequence

Both arms carry a rank-deficient design on top of an offset that already contains `log(exposure)`.
Their fitted predictions diverge — peak operational fitted value **`4.85e8`** per row (mean
`2.11e7`, median row `0.958`, so the divergence is concentrated rather than uniform).

The reported figures are **not scientific results** and must not be cited, compared, ranked or
plotted:

| track | player deviance | team MAE |
|---|---|---|
| intrinsic (E and I) | `2.04e7` | `9.65e7` |
| operational (E and I) | `4.22e7` | `2.58e8` |

**The optimiser converged.** A damped IRLS with step-halving was added and the fit converges. The
explosion is the collinear design, not optimiser divergence. The root cause is the **registration**,
not the solver.

### What remains valid

Nothing from E or I. A rank-deficient design's coefficients are a property of the ridge penalty, not
of the data, so there is no partial result to salvage.

### Relationship to the existing erratum

`arm_registry.jsonl` already carries `p2__erratum_arms_E_and_I_invalid_collinear_registration`. This
record **confirms and extends** it — adding the measured rank deficiency and arm I's second
dependency. It does not contradict or replace it.

---

## Arm F — operational result INVALID, missingness encoded `did_appear`

### The defect

`trailing_minutes_share`, `trailing_rotation_rank`, `role_change` and
`offensive_involvement_proxy` were built from the **realised box score** and left-merged onto the
Tier A candidate universe. Their null mask is an exact post-cutoff appearance indicator.

Measured on `turnover_p2_predictions_operational.parquet` (35,629 rows; `did_appear` true on 27,351,
false on 8,278), recomputed at commit `0397fbd`:

| column | non-null | null | null AND appeared | non-null AND did not appear |
|---|---|---|---|---|
| `trailing_minutes_share` | 27,351 | 8,278 | **0** | **0** |
| `trailing_rotation_rank` | 27,351 | 8,278 | **0** | **0** |
| `role_change` | 27,351 | 8,278 | **0** | **0** |
| `offensive_involvement_proxy` | 27,351 | 8,278 | **0** | **0** |

**Zero off-diagonal in every case.** Independently confirmed by ws3's `leakage_audit` (tip
`1e3509f`) and ws5's `shared_input_defect` (tip `6d9e3f2`).

### Consequence

**Any `fillna` launders the outcome into the design.** P2's operational fit mean-imputes those nulls
inside the fold, which encodes a post-cutoff appearance oracle into the design matrix. The P2
registration's own feature boundary forbids post-cutoff availability, so the operational result
violates the arm's declared boundary.

Value-based leakage checks are structurally blind to this — they only ever see the non-null subset.
Only a null-mask-versus-outcome test catches it. That test now exists in `feature_gate.py` as
`missingness_encodes_outcome` (added at `42af2cd`); it did not exist when P2 was fitted. Re-running
the gate on group 2 at this commit blocks all three columns on that kind.

### What is withdrawn

Every published Arm F **operational** number, including team MAE `2.968025`, player deviance
`1.228388`, and the paired comparison `F vs D: −0.000574 [−0.004406, +0.003147]`.

### What this record does NOT do

It makes **no finding that clears the intrinsic track**. The intrinsic frame is realised-participant
rows only and carries no `did_appear` column; its 894 nulls on every P2-merged feature arise from
left-merge non-matches, not from the appearance mask. The intrinsic track is neither invalidated nor
independently re-validated here.

The **direction** of the P2 F conclusion — that the registered prior-role formulation added no
stable incremental value — is not established by Arm F. Any such claim must cite clean evidence.

---

## Arm G — published player-level improvement INVALID AS PUBLISHED EVIDENCE

### Scope

This finding is about the **player-level improvement claim** only. The arithmetic in
`TURNOVER_P2_RESULTS.json` is correct; it is the **attribution** that fails.

### The defect

`offensive_involvement_proxy` carries the same exact `did_appear` null mask — 27,351 non-null,
8,278 null, zero off-diagonal.

### The decisive comparison

| quantity | value |
|---|---|
| leaking feature effect (deviance) | **`0.0218`** (`0.021804146249029932`) |
| P2 published Arm G gain, operational player deviance `D − G` | **`0.00137`** (`0.0013726932561086702`) |
| ratio | **`15.92×`** |

**The leaking feature effect exceeds the reported gain by roughly a factor of sixteen.**

The leak figure is ws3's, from `WS3_RESULTS.json ::
motivating_premise_retest.value_of_the_leak_alone.deviance_advantage_of_the_leaking_column_over_the_clean_one`
(branch tip `1e3509f`). ws3 refitted the same one-feature arm through an identical pipeline, once on
the canonical **leaking** column (8,278 nulls mean-imputed, player deviance `1.2631277277244133`)
and once on a cutoff-valid **rebuild** (769 nulls, player deviance `1.2849318739734432`), with
identical training rows. The difference is `0.0218041462490299`. ws3 notes that both variants were
refitted on the operational track walk-forward whereas P2 trained on the intrinsic frame, so
absolute levels need not reproduce P2 — the **leaking-versus-clean contrast** is the measurement.

The published gain is reproduced at this commit:
`1.2285420505227964 − 1.2271693572666877 = 0.0013726932561086702`.

### Independent corroboration computed here

Decomposing the published `D − G` operational player deviance by appearance status:

| rows | n | `D − G` deviance |
|---|---|---|
| appearing | 27,351 | **−0.0016175779** |
| non-appearing | 8,278 | **+0.0112527254** |

The entire published gain originates on the 8,278 rows whose feature value is an imputation
determined by the outcome-encoding null mask. **On the rows where the feature is actually observed,
Arm G is worse than Arm D.**

### Consequence

The reported improvement cannot be attributed to the basketball content of the involvement proxy.
Arm G may not be cited as evidence that offensive involvement adds player-level turnover-rate
information.

This is **not** a claim that the involvement proxy is worthless. Per
`player_event_failure_analysis_policy_v1`, a failed registered formulation is not a finding about
the underlying basketball information.

### What is not withdrawn

The **team-level loss** — `G vs D` operational team MAE `−0.005056 [−0.009646, −0.000614]` — is a
separately reproduced phenomenon and is not withdrawn by this record. ws6 (tip `5ef1f25`) reproduces
the reference involvement coefficient `beta = 0.024297`, `z = 4.8938`.

### What is withdrawn

The published Arm G **player-level improvement claim** and every downstream statement resting on it.

---

## Arm H — not affected by the null-mask defect; conclusion contaminated by unmatched intercept

### Not affected by the null-mask defect

`displaced_involvement` is **fully populated**: **35,629 non-null, 0 null**, verified at this commit
on both the feature artifact and the operational predictions. It carries no null mask at all, so it
cannot encode `did_appear` through missingness. Arm H is explicitly **outside** the
`missingness_encodes_outcome` finding that invalidates F and G.

Re-running `feature_gate.audit` on Arm H's design at this commit — with `target` and `outcome_mask`
supplied — returns **`passed: true`, `findings: []`**, numerical rank 1 of 1, condition number
`1.0`.

### But the challenger-versus-D comparison is contaminated

The P2 comparison rule compares each challenger against **the exact frozen Arm D predictions**. The
challenger is refitted with an **unpenalised intercept**; Arm D is not refitted at all. The two
sides do not receive the same intercept treatment.

What that intercept alone is worth, measured by **K0** — an unpenalised intercept and **zero
features**, fitted through the identical walk-forward pipeline on the identical offset and folds:

| quantity | value |
|---|---|
| K0 operational team MAE | `2.9641944524592625` |
| frozen Arm D operational team MAE | `2.967450520182488` |
| paired K0 vs D | **`+0.003256067723225449`**, ci90 `[−0.000141, +0.006720]` (does not exclude zero) |

Reproduced independently in three workstream artifacts: ws1 (`5313ebd`), ws5 (`6d9e3f2`), ws7
(`e858e96`).

Arm H's published effects are of the **same order or smaller**:

| Arm H, published | value |
|---|---|
| operational, H vs D team MAE | `−0.000695 [−0.005398, +0.003629]` |
| intrinsic, H vs D team MAE | `−0.001994 [−0.006145, +0.002267]` |
| operational player deviance `D − H` | `−0.0000819` |
| intrinsic player deviance `D − H` | `−0.0001915` |

A comparison whose unmatched intercept term is worth about `+0.0033` **cannot adjudicate effects of
this size in either direction**. The original Arm H challenger-versus-D conclusion is withdrawn as
an **adjudication**, not as arithmetic.

### What remains valid

- The Arm H **feature is clean** and may be reused without missingness remediation.
- The Arm H **numbers are arithmetically correct** and may be quoted as descriptive statistics.
- The **non-promotion** of Arm H stands. Nothing here argues Arm H should have been promoted; it
  argues the comparison as constructed could not decide either way.

### What is required before re-adjudication

A re-run against an **intercept-matched incumbent**, registered as a new frozen challenger in a
later wave. Not a re-analysis of the existing fit. The general form of this defect is the subject of
`comparison_gate.py` (integrity workstream A); this record neither specifies nor assumes that
module's interface.

---

## Clean discovery results are SEPARATE evidence

> **The clean WS5 and WS6 discovery results MUST NOT be backfilled into the original P2
> registration. P2 stands superseded AS RUN. It is not retroactively repaired.**

| workstream | branch tip | status and verdict |
|---|---|---|
| ws5 opportunity proxies | `6d9e3f2` (freeze `059db0d`) | DISCOVERY, historical development evidence only. SPLIT: all six clean proxies fail as rate predictors and as interactions against K0; five of six give a small season-stable player-level gain as allocation weights (x1: `+0.00175` vs K0, ci90 `[0.0015, 0.00198]`). Expected direction FALSIFIED (`r = 0.994`). |
| ws6 mechanism decomposition | `5ef1f25` | DISCOVERY ONLY. `REJECTED_AS_CAUSE__HETEROGENEITY_REAL_BUT_NOT_OFFSETTING`. |
| ws3 total + allocation | `1e3509f` | DISCOVERY; premise contaminated; verdict null. Supplies the leaking-versus-clean measurement quoted under Arm G — cited as ws3's finding, on ws3's evidence, at ws3's commit. |

They are separate evidence for four reasons, each independently sufficient:

1. **Different lane.** P2 is a registered promotion-style comparison against a frozen incumbent.
   ws3, ws5 and ws6 are DISCOVERY, on development folds, explicitly non-promotable.
2. **Different inputs.** ws3 and ws5 rebuilt the leaking columns. Their numbers are measured on
   inputs the P2 registration never used.
3. **Different registration status.** None was registered before execution as a P2 challenger.
   Inserting their results into P2 would convert post-hoc discovery into pre-registered
   confirmation — the exact substitution the program's registration discipline exists to prevent.
4. **Backfilling would launder a null.** P2's honest outcome is that no registered role feature
   added stable value, with several arms invalid. Grafting a clean discovery result onto that record
   would convert a null into an apparent success that no pre-registered test produced.

Cite the clean findings from their own workstream records, at their own commits, under their own
DISCOVERY status.

---

## Gate-invocation clause

A companion contract is added at `experiments/player_program/GATE_INVOCATION_CONTRACT.md`:

> Feature audits must run separately on EVERY chronological training fold and again on the final
> assembled design. A pooled audit cannot establish that every training fold is identified.

Its motivating case is ws3's stage-2 **2022** training fold, where `proj_off_poss_share` had
standard deviation `7.80108356964482e-09` and `p_active` `5.13611574504531e-17`, while the **pooled**
audit over the same 35,629 rows passed both columns with zero findings. `|X·gamma|` reached `6.9e4`,
the within-team softmax saturated to exact `0.0`/`1.0` shares, and the optimiser converged in five
Newton iterations in every fold. Pooled variance is an average; identifiability is a per-fold
property.

Had that contract and the current gate been in force at P2, Arms E and I would have been blocked
pre-fit on `near_collinear` and `rank_deficient`, and Arms F and G on
`missingness_encodes_outcome`. That is an observation about invocation timing — **not** a licence to
repair and re-run those arms inside the P2 wave.

---

## Verification receipts

Recomputed at commit `0397fbd` against the frozen files in this directory, not copied from the
results JSON:

- Arm E rank 4 / 5 and Arm I rank 8 / 10 via `feature_gate.design_rank_report`
- duplicate-column identity, `max|Δ| = 5.551115123125783e-17`, correlation `1.0`
- `role_change` identity, `max|Δ| = 0.0` over 27,351 defined rows
- null-mask-vs-`did_appear` cross-tabulation, all four affected columns, zero off-diagonal
- `displaced_involvement` 35,629 non-null / 0 null
- `feature_gate.audit` re-run per arm design: **E blocked, F blocked, G blocked, H passed, I
  blocked**
- Arm G gain `1.2285420505227964 − 1.2271693572666877 = 0.0013726932561086702`, and its
  decomposition by appearance status
- E/I maximum fitted operational prediction `485165195.4` per row
- feature artifact sha256 matches its results receipt

Quoted from other workstreams and **not** re-executed here: ws3's `0.021804146249029932` (located in
`WS3_RESULTS.json` and arithmetically checked against ws3's own two reported deviances, but the two
ws3 fits were not re-run), ws3's `6.9e4` / saturation / five-iteration convergence, ws5's verdict
and per-proxy figures, ws6's verdict and reference coefficient. `K0 = 2.9641944524592625` and the
`+0.003256067723225449` paired difference were checked in **two** independent workstream artifacts
(ws1 and ws5) and agree to all reported digits.
