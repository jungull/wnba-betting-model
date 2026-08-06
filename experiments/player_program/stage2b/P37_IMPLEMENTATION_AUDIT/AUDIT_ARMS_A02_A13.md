# P37 IMPLEMENTATION AUDIT — ARMS A02, A03, A05, A07, A08, A09, A10, A11, A12, A13

IMPLEMENTATION AUDIT. Establishes that the code is the preregistered code. Establishes nothing about results, which remain sealed.

Auditor: independent auditor 2 of 3 (slice: A02, A03, A05, A07–A13). Attestation: this auditor
implemented none of the arms audited here, read nothing under
`experiments/player_program/stage2b/SEALED_RESULTS/`, inspected no comparative historical
performance, never set `P38_UNSEALED`, and wrote only this file inside the node write scope
(plus session-scratchpad copies described in §1).

---

## 1. Method and provenance verification

**Frozen-card verification.** `Get-FileHash stage2b/P35_FREEZE_TASK_CARDS/SPEC.json -Algorithm SHA256`
→ `68EF22F4FCA15A2E8D91EEEB9B84B86F86E8E9E7CAAB5E23E6A9B950385B4D32` — matches the pinned P35
cards hash exactly. All card-vs-code comparisons below are against those bytes.

**Other pins re-measured (same command, one per file):**

| pinned object | measured sha256 | matches pin |
|---|---|---|
| P22 `postgame_surrogate_guard.py` | `951e8513…b73ceeda` | yes (`runner_constants.GUARD_SHA256_PINS`) |
| P23 `merge_guard.py` | `b0e75419…3ca3b7a8` | yes |
| P25 `offset_dependency_guard.py` | `c78e70b6…cc100e95` | yes |
| P26 `validate_k0_matched.py` | `1fc798da…557d7e16` | yes |
| P27 `fold_estimability_guard.py` | `1fbec0d6…ddb25d2f` | yes |
| P33 `SPEC.json` | `066b2a04…d347d093` | yes (carry-by-hash source) |
| `data/reference/team_cities.csv` | `10a544fd…128ac42d` | yes |
| `projected_exposure_v1/team_possession_prior_v1.parquet` | `c37c0751…87c3db18` | yes (frozen real artifact) |
| `possessions_v2/possessions_raw_v2.parquet` | `72008816…?` measured `7200881f…b15a4b1a` | yes |

The two frozen real input artifacts matching their pins is this slice's byte evidence that the
incumbent path / Arm D inputs are unchanged. No file under `possessions_v1/`, `fits_v1/` or any
`*_v1`/`*_v2` canonical directory was written by this audit.

**Test-suite execution.** The P36 arm test suites write `TEST_RECEIPT*.json` into the P36 tree,
which is outside this node's write scope. To re-run them without touching P36 bytes, the whole
`experiments/player_program` tree (excluding `SEALED_RESULTS`, which was never read, and
`__pycache__`) plus `data/reference/team_cities.csv` was copied to the session scratchpad
(`robocopy … /E /XD SEALED_RESULTS __pycache__`) and every suite was run there with
`python <sandbox>/…/arms/<Axx>/tests/TESTS*.py`. The original P36 directories received no write
from this audit.

## 2. Test suites re-run — results

All ten suites pass, zero failures, on Python 3.13.14 / numpy 2.5.1 / pandas 3.0.5:

| arm | suite | self-reported result | P36 SPEC claim | agrees |
|---|---|---|---|---|
| A02 | `arms/A02/tests/TESTS.py` | 14/14 | 14/14 | yes |
| A03 | `arms/A03/tests/TESTS.py` | 13/13 | 13/13 | yes |
| A05 | `arms/A05/tests/TESTS_A05.py` | 10/10 | 10/10 | yes |
| A07 | `arms/A07/TESTS.py` | ALL 15 TEST FUNCTIONS PASSED (55 `[PASS]` check lines) | 54/54 | count convention mismatch — see finding C-13 |
| A08 | `arms/A08/tests/test_a08.py` | 10/10 | 10/10 | yes |
| A09 | `arms/A09/tests/TESTS.py` | 9/9 | 9/9 | yes |
| A10 | `arms/A10/tests/TESTS.py` | 9/9 | 9/9 | yes |
| A11 | `arms/A11/tests/TESTS.py` | 14/14 | 14/14 | yes |
| A12 | `arms/A12/tests/TESTS.py` | 19/19 | 19/19 | yes |
| A13 | `arms/A13/tests/TESTS.py` | 15/15 | 15/15 | yes |

Every suite is synthetic/identity/schema-only, asserts `P38_UNSEALED` is absent, and every one of
the ten calls `runner_interface.validate_arm_module` on its own module instance(s), so
RUNNER_INTERFACE conformance is exercised, not merely claimed.

## 3. Card-vs-code identity, per arm (line-by-line review)

For each arm: formula, K0 design, enumeration, intercept status, guards, kill hooks, against the
frozen P35 card (which carries P33 by hash).

* **A02** `arm_a02.py`: `eta = log_exposure + gamma*contrast_own_minus_opp_pace_estimate`, no
  intercept; contrast computed as literal `own_est - opp_est` (registered P25 formula, registered
  column name emitted per OFFSET C-5); null `[]`+`[]` term_removal = the incumbent. Preregistered
  contrast + digest hooks present. CONFORMANT (findings C-9, C-11 below).
* **A03** `arm_a03.py`: `eta = log_exposure + alpha_S*1[pace_evidence_depth<=3]`, DEEP reference,
  no intercept, t=3 fixed; treatment column named card-literally `1[SHALLOW]`; null = incumbent;
  S7_TIER_SUPPORT_v1 wired via `p27_rule()` (SHALLOW half) + task-specific `tier_symmetry_check`
  (DEEP half). CONFORMANT (finding B-5 on the DEEP-half call-site wiring).
* **A05** `a05_cal_playoff_intercept.py`: `eta = log_exposure + pi*1[is_playoff_game]`, no
  intercept; strict {0,1} validation; null = incumbent; test-side non-discrimination note carried
  with the P33 measured numbers (four evaluable folds). CONFORMANT (findings C-7, C-8). The
  P33-carried fold naming (`train_lt_YYYY`) recorded in this module is direct documentary support
  for the P27 fold-policy RAISED item's `EXPANDING_PRIOR_SEASONS`-shaped reading.
* **A07** `A07_early_season_transient.py`: `eta = intercept + log_exposure + b1*gap + b2*depth +
  b3*opp_depth + delta*exp(-n_i/5)`, tau=5 fixed; free intercept arm AND null; null grants
  gap/depth/opp_depth/intercept (K0 K5 relabel carried, "not an incumbent benchmark" note
  present); n_i date-strict on a separate contract-schedule frame (n_clock_pin honoured
  structurally). CONFORMANT (findings C-10, C-12).
* **A08** `a08_arm.py` + `features.py`: model and null shapes match the card; K∈{20,80} enforced;
  L_t:=0 pre-window (FOLDS F1/OP-3) implemented; Lbar_train centering reading disclosed.
  **NOT CONFORMANT on the prior-window strictness relation — Severity A finding A-1 below.**
* **A09** `arm.py` + `feature_construction.py`: `log E[y] = log_exposure + beta0*d_t +
  beta*((w(n_t;kappa)-1)*d_t)`, w = n/(n+kappa), κ∈{2,10,50} enforced, K7 drafting closure (flat
  term explicit, treatment = adaptive-vs-flat contrast), d_t:=0 at n_t=0, date-strict prior sums.
  CONFORMANT on formula identity (finding B-2 on the clock-source deferral).
* **A10** `arm.py` + `feature_construction.py`: `log E[y] = log_exposure + beta0*d_t + beta1*c_t`,
  `c_t = ewma_lambda{pace(j)-Lbar_<j} - d_t`, λ∈{0.2,0.5} enforced, both zero-fills implemented,
  null `[log_exposure | d_t]` lambda-free. CONFORMANT (EWMA pin adjudicated in §4; finding B-2).
* **A11** `arm_a11.py` + `feature_construction.py`: repaired card implemented exactly —
  `dblend_t(rho) = (n_cur*dcur + rho*m_prev*dprev)/(n_cur + rho*m_prev)`, ρ∈{0.25,0.5,0.75} fixed
  per element, null = `dblend_t(1)` with free beta as `parameter_fixed_at_null` (null's own free
  column carried in the null design's `treatment_cols`, exactly per RUNNER_INTERFACE §3);
  empty-window rule verbatim; `structurally_deactivated_folds() == ["train_lt_2022"]`; replaced
  kill set (i)/(ii)/(iii) implemented, struck "rho interval includes 1" not implemented anywhere.
  CONFORMANT (finding C/B-6 on the sign-instability convention).
* **A12** `A12_carryover_additive_decay.py`: full model with w(n)=1/(1+n/5), h=5 fixed; 2-df joint
  treatment {dev_prev, w_n:dev_prev}; null grants w_n main + gap/depth/opp_depth/intercept and no
  dev_prev in any form; n_i date-strict on a caller-supplied history superset; dev_prev
  period-based reg-equiv with the D9 duration reading struck; S7 rule (≥10 clusters,
  |dev_prev|>0) via the generic P27 mechanism; train_lt_2022 structurally deactivated; interaction
  named `w_n:dev_prev` so the frozen P26 R6 factor-split verifies marginality closure.
  CONFORMANT (finding B-4 on the beta2-sign kill reading).
* **A13** `arm_a13.py`: A12's full arm design reconstructed byte-equivalently (not imported —
  write-scope isolation honoured) + cont main + centered interaction treatment; cbar_F and the
  n=0 cont imputation computed from `fold["train_idx"]` only, once per fold, held fixed across
  refits (LEAKAGE L4 verbatim); cont_i Jaccard built exactly per the H4 provenance resolution the
  module discloses; treatment named `cont_i:dev_prev` (compound-name concession to the frozen P26
  factor-split, values are the card's centered interaction — verified in `build_design`).
  CONFORMANT (finding B-3 on the beta3<0 kill hook).

**K0 designs**: all ten arms' null designs match the frozen `k0_matched_frozen` blocks, including
the three zero-parameter nulls that ARE the incumbent (A02/A03/A05), the two granted-features
nulls (A07/A12), the shared lambda/kappa/K-free `[log_exposure | d_t]` nulls (A08/A09/A10), A11's
`parameter_fixed_at_null` single-blended-column null, and A13's A12-plus-cont-main null. Arm and
null row sets are identical by construction in every module (all columns are materialised
full-length against the same universe frame).

**Enumeration exactness**: constructors hard-reject off-grid elements (A08 K∉{20,80}, A09
κ∉{2,10,50}, A10 λ∉{0.2,0.5}, A11 ρ∉{0.25,0.5,0.75} all raise); single-element arms return `{}`
from `enumeration_element()`; no training-time selection path exists in any module. Verified by
code reading and by the suites' enumeration tests.

**Pinned constants re-verified in code**: IRLS tol 1e-10 / 100 iterations, B_test=10,000,
B_train=2,000, percentile 95%, master seed 20260806 and the derivation string
(`runner_constants.py`, imported read-only by A08–A11); tau=5 (A07), h=5 (A12/A13), t=3 (A03),
10-cluster floors (A03/A12/A13), E-thresholds n/a in this slice; the intercept table (A07/A12/A13
with, all others without) agrees with `ARMS_WITH_FREE_GLOBAL_INTERCEPT` and with every module's
`uses_global_intercept()`.

## 4. A10 EWMA interpretive pin — adjudication: CONFIRMED, with a caveat

The disclosed pin (`arms/A10/feature_construction.py` docstring + code): plain recursive EWMA
over the team's strictly-prior games ordered `(game_date, game_id)` — `S_1 = dev(j_1)`,
`S_k = lambda*dev(j_k) + (1-lambda)*S_(k-1)`, `c_t = S_(n_t) - d_t`, with `dev(j) = pace(j) -
Lbar_<j` evaluated at j's OWN date (a property of row j alone, matching the frozen formula
string). The recursion is hand-verified in `TESTS.py t01_pace_and_ewma_identities`.

**Confirmed** because: (a) the frozen bytes pin only the string `ewma_lambda{pace(j) - Lbar_<j}`;
some deterministic completion is required; (b) the chosen recursion is standard, deterministic,
identical for both lambda elements, and disclosed pre-P38 in the frozen implementation record;
(c) it cannot introduce arm-vs-null asymmetry — the null `[log_exposure | d_t]` carries no EWMA
term at all, so the choice affects only what "recency" means inside the treatment column.

**Caveat (measured, must travel with the pin):** the module's supporting claim that this matches
"the recursive convention already in use elsewhere in this program (D_ewma_shrunk)" could NOT be
verified from bytes in scope — no D_ewma_shrunk builder exists anywhere under this worktree
(searched: `Select-String -Pattern "def.*ewma|ewma_shrunk"` over every non-P36 `.py`; the
incumbent is consumed from frozen artifacts only). The one sibling EWMA implementation found in
the repository (`experiments/market_program`-adjacent `experiments/channels/run_experiment.py`)
uses `pandas .ewm(alpha, adjust=True)` — the NORMALIZED convention, which differs from the plain
recursion for finite windows. The pin therefore stands on its own disclosure, not on the analogy.
P38 must carry the exact recursion (it is in the sidespec/preprocessing string) in every receipt.

## 5. Findings

Severity discipline: **A** = code is not the preregistered code / a frozen pin is violated;
**B** = disclosed-or-latent ambiguity or gap that will change decidable outcomes or pin
compliance at P38 unless adjudicated first; **C** = recorded deviation/bookkeeping with no
outcome path.

### A-1 (Severity A) — A08 prior-window strictness contradicts the frozen date-granular pins; d_t is NOT the shared column

`arms/A08/features.py` defines "strictly earlier" by **game_rank** (dense rank over
`(game_date, game_id)`): `n_prior_league = ranks`, `all_prior_league_mean[i] = cum_sum[r-1]/…`,
L_t window `[r-K, r-1]`. A game on the SAME calendar date with a smaller `game_id` counts as
"strictly before". The frozen bytes say otherwise:

* `construction_pins.d_t_league_mean_pin`: "Lbar_<g = mean … over ALL completed league games
  **strictly before game_date(g)**";
* `construction_pins.a08_window_tie_break`: "last K completed league games **strictly before
  game_date(g)** … deterministic, **date-granular**, leak-free" — the `(game_date, game_id)`
  ordering is a tie-break WITHIN the strictly-earlier-date set, not a redefinition of it;
* `task_cards[A08].k0_matched_frozen`: d_t is "ONE shared null … (d_t is K-free per the
  league-mean pin)" shared verbatim across A08/A09/A10 (K4).

A09, A10 and A11 all implement the **date-strict** relation (same-date rows never count —
`_prior_sum_count_by_date` groups by date and subtracts the own-date aggregate). Measured
divergence (script run in the sandbox; three games per date, 40 dates, 6 teams, seeded rng):

```
A08: same-date sibling game counted: n_prior_league=1, Lbar_<g=85.0, windowed_defined=True (date-strict expects 0/0.0/False)
A09: same row: n_t=0, d_t=0 (same-date rows excluded)
A08 vs A09 d_t on the tie-heavy fixture: max|diff| = 2.6818, 156 of 240 rows differ
A09 vs A10 d_t: byte-identical; A11 dcur == A09 d_t (single season): True
```

Consequences if unfixed: (i) `d_t` is not one shared column across A08/A09/A10 — K4 violated —
so A08's null `[log_exposure | d_t]` is a DIFFERENT null from A09/A10's on any schedule with
same-date games (the real WNBA schedule has multiple games on most dates); (ii) L_t's window
admits same-date games whose completion before the target tip is not established by `game_id`
ordering — the exact lookahead shape the "completed … strictly before game_date(g)" wording
excludes; (iii) A08's own strict-lagging tests never exercise the case (its fixture is built
"one/day" — `test_a08.py` line 69), which is why 10/10 passes while the deviation stands.

Not disclosed: `features.py`'s own docstring restates the date-strict prose while the code is
rank-strict. This is a card-vs-code identity failure on the A08 prediction path and on the K4
shared-column invariant. Per the standing rules it is reported, not fixed. Note the fix direction
is confined to A08's `features.py` (A09/A10/A11 already agree with the pins).

### B-2 (Severity B) — A09/A10 compute the pinned contract-schedule clock from the runner's `universe` argument

`arms/A09/arm.py` and `arms/A10/arm.py` compute n_t/d_t (and A10's c_t) from the `universe` frame
passed to `build_design` ("the supplied universe frame IS the contract-schedule history"),
deferring the n_clock_pin ("the universe-row clock is barred") to an undocumented P38 caller
obligation to hand the 2,990-row contract schedule in as `universe`. But RUNNER_INTERFACE §3's
`universe` is the fit frame the folds index into, and the 2,990-row superset contains 8 rows with
no resolved projection (no valid `log_exposure`), so it cannot simply BE the fit universe. Every
other clock-bearing arm in this slice (A07, A08, A11, A12, A13) binds a separate
history/contract-schedule frame at construction. As written, a P38 executor who passes the
2,982-row universe gets the barred clock silently (the four excluded 2021 opening-day games leave
the counts). Needs a binding resolution before P38: either A09/A10 gain a constructor-bound
history frame like their siblings, or the P38 execution record must pin exactly how the
contract-schedule rows reach `build_design` without entering the fit rows.

### B-3 (Severity B) — A13 `beta3_negative_kill`: code and its own docstring decide differently

Code: `any(v < 0.0 for v in fold_points)` — fires on ANY negative per-fold point estimate.
Docstring on the same function: "a NEGATIVE, **non-zero-covering** estimate refutes". Divergent
case: one fold's interval excludes 0 (positive), another fold's point estimate is negative inside
a zero-covering interval — code kills, docstring reading does not. The card ("beta3 < 0 (refutes
mechanism)") supports the code's literal reading; the docstring narrows it. One of the two must
be pinned before unsealing; the kill outcome differs between them.

### B-4 (Severity B) — A12 beta2 "sign contradicting decay": disclosed reading has a noise edge

Module pins: kill iff sign(beta2) ≠ sign(beta1), both nonzero, any fold (disclosed as ambiguity
note 2 — properly raised, not silent). Caveat for adjudication: when beta1 ≈ 0 (its sign is
noise), the rule can fire on the noise sign even though the fitted dev_prev effect
`beta1 + beta2*w(n)` decays exactly as the mechanism predicts. An alternative frozen-compatible
reading (beta2 opposing the PREDICTED carryover direction) does not have this edge. P37/P38 must
pin one reading before any kill is evaluated; recording the module's reading as-is is acceptable
provided the edge case is carried in the record.

### B-5 (Severity B) — A03 DEEP-tier half of S7_TIER_SUPPORT_v1 is not wired into any shared execution path

The card's rule is two-sided ("EITHER tier below the 10-cluster floor"). The generic P27
`ActiveSetRule` can only see the declared SHALLOW column, so `p27_rule()` honestly expresses the
SHALLOW half only; the DEEP half lives in the module's own `tier_symmetry_check()` (a correct
task-specific wrapper per standing rule 3, tested, decidable). But nothing in the shared runner
calls `tier_symmetry_check` — the runner consumes `p27_rule()` only. Disclosed in the module
docstring. The P38 execution record must bind the executor to invoke `tier_symmetry_check` per
fold (arm and null identically) or the frozen "either tier" rule silently degrades to a one-sided
rule.

### B/C-6 (Severity B if unpinned at P38) — "sign instability" is operationalised two different ways across this slice

A02/A03/A05: sign flip decided over the nonzero POINT-estimate signs of all evaluable folds.
A08/A11: signs collected ONLY from folds whose 95% interval excludes 0. Same frozen prose family
("sign instability/flip across evaluable folds"), two decision rules; a fold with a
zero-covering, opposite-sign point estimate kills under the first and not under the second. Each
is individually defensible; carrying both silently is not. One convention (or an explicit per-arm
pin) must be recorded before unsealing.

### C-7 — A05 treatment column name drift

Materialised as `is_playoff_indicator`; card's term is `1[is_playoff_game]` (contrast A03, which
uses the card-literal `1[SHALLOW]`). Values are the exact 0/1 cast of the schedule flag; name
drift only, but receipts/keys will carry the non-card name.

### C-8 — missing-interval conventions point in opposite directions across kill evaluators

A05 `evaluate_kill_conditions`: a fold with a missing interval counts as covers-zero
(kill-friendly). A02: a missing interval blocks the non-rejection claim (kill-unfriendly). The
frozen cards do not pin the convention; it only matters if the K7 NA rule leaves a fold with no
effective draws, but it should be one convention, recorded.

### C-9 — A02 degeneracy trigger `sd(contrast)==0` implemented as `min_std = 1e-08`

Card numeric trigger is exact zero; module uses a 1e-8 floor (disclosed in its P26 record's
`numeric_threshold`). Harmless direction (catches numerically-degenerate folds the exact-zero
test would miss), but it is a numeric substitution inside a frozen trigger — record it.

### C-10 — A07/A12 "concentrated on n<=5" pinned to a majority-share (>=0.5) convention

The frozen kills name concentration without a threshold. Both arms disclose the 0.5 majority
reading, identically. Affirmed as the plain-language reading; the 0.5 constant must be carried in
the P38 decision record as an implementation pin, not silently treated as frozen.

### C-11 — `claimed_signal_axes` prose→enum translation (all arms)

The frozen P26 schema restricts axes to an 8-value enum, so the cards' prose axes cannot be used
literally. Mappings audited and sensible: A02→opponent_identity; A03→support_size;
A05→season_time; A07/A09/A11/A12→season_time+support_size; A08→league_time;
A13→roster+support_size. Forced translation, correctly disclosed where non-obvious (A12).

### C-12 — P22 lag-kind labels for count/window features (A07 n_i, A12 w_n: SCHEDULE; A08 d_t/L_t, A11 dblend, A12 dev_prev, A13 cont/dev_prev: DERIVED_NO_JOIN)

Affirmed: the frozen P22 kinds cannot express a windowed/cumulative aggregate as PRIOR_GAME (its
re-derivation battery verifies a single `shift(n_back)`), and a completed-game count is a
pre-tipoff schedule fact (P22's own SCHEDULE examples include the playoff flag). Consequence to
carry: the P22 battery therefore never mechanically validates these lags — strict lagging rests
on each arm's own identity tests, and A08's tests have the tie blind spot of finding A-1.

### C-13 — A07 test-count bookkeeping in the fleet record

P36 SPEC.json says A07 "54/54". Measured: 15 test functions, 55 `[PASS]` check lines, 0 failures
(`(python arms/A07/TESTS.py | Select-String "^\[PASS\]").Count` → 55). No failing content; the
fleet record's count matches neither convention and should be corrected or annotated.

### C-14 — A08 defers the pinned pace formula to its caller

`features.py` consumes a caller-supplied `pace` column; the lagged_regulation_equivalent_pin
formula `n_off_poss*40/(40+5*max(0,max_period-4))` is implemented inside A09/A10/A11/A12/A13 but
not inside A08. Disclosed in the docstring. The P38 execution record must pin that A08's `pace`
input is computed by the frozen formula (one more caller obligation to bind alongside B-2).

## 6. RAISED-worklist items from the P36 fleet record touching this slice

* **A10 EWMA interpretive pin** — CONFIRMED with caveat (§4).
* **P27 fold-policy naming** — this slice contributes documentary evidence: the P33-carried A05
  record and A11's `train_lt_2022` structural deactivation both use `train_lt_YYYY`
  (expanding-prior-seasons-shaped) fold ids; consistent with the harness default. No conflict
  found in any of the ten arms.
* **K0_FLAT naming / bootstrap p-value / P26 R8 call-site adjudication** — runner-slice items;
  from the arm side, every module in this slice labels `k0_flat_role: diagnostic_only`, and the
  calibration_only arms (A02/A03/A05) each declare exactly one tested parameter with
  `null_value == 0`, satisfying the extended R8 rule the adjudication mandates.
* **Directory-exclusive isolation** — verified for this slice: no arm module imports another
  arm's directory (A13 reconstructs A12's design rather than importing it; A09/A10/A11 carry
  independent copies of the shared prior-sum construction — behavioral identity of those copies
  measured in §5 A-1's script: A09 == A10 == A11 exactly).

## 7. What this audit could NOT establish

* **Real-data magnitude of finding A-1.** Blinding was honoured: no real fold was constructed,
  so the divergence was measured on a tie-heavy synthetic schedule only. The real-schedule
  magnitude depends on games-per-date density and is a P38-time measurement (after the A-1
  resolution, not before).
* **The incumbent D_ewma_shrunk recursion convention** — no builder bytes in scope (§4 caveat).
* **End-to-end runner behavior on real folds** — structurally refused without `P38_UNSEALED`;
  out of scope and correctly so.
* **Whether P36's "54/54" for A07 was a defensible historical count** — only the current bytes
  were measured.

## 8. Stop-condition assessment

Finding A-1 does not change the primary target, the K0 structure as *specified*, the inference
structure, the candidate universe, the cutoff-valid feature set, or the leakage *status* of any
frozen document — it is an implementation-vs-card identity failure inside one arm's feature
construction, squarely what this audit exists to catch, and its remedy (making A08 date-strict
like its siblings) is a code correction toward the frozen bytes, not a preregistration change.
No stop condition is tripped. It IS promotion-blocking for A08 as implemented: fitting A08 in its
current state would fit a design the preregistration does not describe, and its K0 would not be
the pinned shared null.
