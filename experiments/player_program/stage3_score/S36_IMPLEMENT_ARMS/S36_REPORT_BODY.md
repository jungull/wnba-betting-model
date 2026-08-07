# S36_IMPLEMENT_ARMS — implementation report

**IMPLEMENTATION. Unit/synthetic/identity/schema tests only; no comparative historical performance
is revealed.**

**Root, stated explicitly:**
`C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program` (the PROGRAM
worktree). Every measurement below ran against these bytes. The live data worktree at
`C:\Users\jgallagher\wnba-betting-model` was never read.

**Node:** S36_IMPLEMENT_ARMS · lane `score` · cycle 2 · Severity A on failure
**Required output:** `RUNNER_MANIFEST.json` — written.
**Status:** `LANDED`, not `VERIFIED`. This node does not mark its own work accepted.

---

## 1. What was built

Eleven arm modules, seventeen frozen element cards, one shared runner, and the receipts the cards
name. `SC07_REF_CREW_TOTALS` is **not** implemented — it was withdrawn by measurement at S33 and
`runner.load_modules()` refuses a module for it by name.

| | |
|---|---|
| arms implemented | 11 (SC01–SC06, SC08–SC12) |
| element cards implemented | 17 |
| designs materialised on the real pinned universe | 16 × 5 folds, Layer-A parity checked on every one |
| designs deferred | 1 (SC09 — see §5, F4) |
| tests | **57 / 57 green** |

Layout: `prebuild/` (the O2 discharge), `runner/` (universe, canonicalisation, estimators,
blinding, seeds, bootstrap, interface, obligations, build and verification drivers), `arms/`
(eleven modules plus the shared head), `tests/`.

`RUNNER_INTERFACE.md` states the frozen module contract; `BYTE_PIN_CANONICALISATION.md` closes
the join-key gap S35 handed forward.

### The design-parity mechanism

A module does not hand back two independently built designs. It returns **one column dictionary
plus two column-name lists**, and `validate_design` reconstructs the K0 from the arm and refuses
the pair unless `arm_cols` minus `treatment_cols` is exactly `k0_cols`, in order. Two separately
constructed designs can drift in a preprocessing step, a fallback or a fold constant, and the
drift is invisible until it surfaces as an unexplained delta. Two views of one dictionary cannot
drift. The validator additionally refuses a treatment term surviving in the K0, a structural term
missing from either side, a non-finite column, a misaligned column, a constant column acting as a
silent second intercept, and a `comparison` outside the two frozen null constructions. Each of
those is a named Severity A, and `tests/TESTS.py` breaks the parity three different ways to show
the refusals fire.

---

## 2. The seven obligations — where each is discharged

Every obligation is carried **verbatim** as a module constant in `runner/obligations.py`, and
`verify_obligation_text()` re-reads the frozen S35 bytes on every run and fails closed on any
drift, so a transcription typo here cannot silently weaken an obligation. Beyond carrying the
text, each is attached to a **mechanism that refuses to emit the thing it governs without it** —
because the program's own recorded lesson is that an obligation living only in a report is one
that gets lost.

| obligation | file | mechanism |
|---|---|---|
| **ROOT_PATH_RULE / O1** | `prebuild/PREBUILD_GAME_ID_DIGEST.py::verify_root_path_rule`, `runner/universe.py::_verify_input_pins`, `runner/runner_constants.py` | re-hashed **independently at this node** before anything was built. The drifted data-worktree copy is refused **by name** (`KNOWN_DRIFTED_MASTER_TEAM_SHA256`), not merely by pin mismatch, so the specific defect the rule describes gets its own error message. The worktree root is derived from the module's own file location — never from cwd, never from an environment variable a caller could repoint. **Measured: `ad79ce5cdda7e058ba24be45243037252e3795a3e9f0c18cc41b3f12f3c38528` — MATCH.** |
| **C4 / O2 pre-build digest** | `prebuild/PREBUILD_GAME_ID_DIGEST.py` → `PREBUILD_GAME_ID_DIGEST.json`; enforced in `runner/universe.py::build_universe` | emitted **before any design matrix existed**, and structurally so: the discharging script imports only pure hashing, pure pins and pure text and is *incapable* of constructing a design matrix. `build_universe()` then refuses to return a frame unless the receipt exists and the built game_id set re-derives to it — so no design matrix in this node can exist over a row set the receipt did not pin. **This converts `invariants.rows` from a deferral into a receipted invariant on all 17 records.** |
| **C1 program-alpha disclosure** | `runner/obligations.py::stamp_program_alpha` | both bounds stamped on **every** receipt this node writes: `GOVERNING_BOUND 0.40` (8 primary families × 0.05, the intersection rule), `DISCLOSED_BOUND 0.50` (10 maximal-partition families × 0.05), `which_governs: "0.40 GOVERNS"`, `no_program_wide_FWER_claim: true`. Tested across all receipts. |
| **C2 SC06 era-kill power statement** | `runner/obligations.py::stamp_sc06_power_statement` / `assert_sc06_era_verdict_carries_power_statement`; `arms/sc06_sched_fatigue_diff.py::era_split_receipt` | `era_split_receipt` is the **only** emitter of an era-split table or era-kill verdict in this node. It stamps the verbatim statement, then re-asserts its presence before returning, so a verdict without it cannot be constructed. Stamping it on an element the obligation does not bind is also refused. The statement additionally travels with the census that is its own evidence, in `CARDED_STRATA_RECEIPT.json`. |
| **C3 SC11 E2 receipt label** | `runner/obligations.py::label_sc11_cross_estimand` / `assert_sc11_cross_estimand_labelled`; `arms/sc11_league_total_drift.py::cross_estimand_receipt` | the **only** constructor. It applies `NON_CITABLE_INTEGRITY_DIAGNOSTIC`, sets `citable=False`, `enters_family=None`, `enters_pass_tally=False`, pins the 0.10-MAE-point integrity threshold, and names the number **`abs_delta_mae_E2_NON_CITABLE`** rather than `delta_mae` — so a downstream caller cannot lift it out by habit and have it read like a result. The label is re-asserted before return. |
| **reporting_rule** | the two self-checking emitters above | both refusals are tested **in both directions**: the sanctioned path produces the label, the unsanctioned path raises. |
| **O5 `R_SC08_FLOOR`** | `arms/sc08_sigma_margin_map.py::r_sc08_floor_receipt` | built and schema-tested now so its absence cannot be discovered late. It takes **no challenger argument at all**, because the card says the challenger's number is not part of this receipt; both inputs are control objects. Registered as a non-gating agreement receipt on SC01::E3 and SC06::E3 as well. The below-floor label and all four automatic consequences are carried. |
| **O6 `R-A1-EXCEPTIONS`** | every `ElementSpec.mandatory_receipts`; SC06's A1-SENSITIVITY kill | declared mandatory on **all 17** elements and asserted in tests. SC06's `game_date` lineage is carried at `CUTOFF_VALID_WITH_ENUMERATED_EXCEPTIONS`, never unconditional. |
| **O7 identity-set extension reviewable** | `runner/obligations.py::O7_EXTENSION_COLUMNS`; column-grain test against `SPEC_V2` | the six extension columns and the S30 base closed set are validated at **column** grain against the frozen bytes, and every column classified `PRESENT_IN_ARTIFACT_NEVER_READ_BY_ANY_ARM` is asserted to carry `current_game_row_consumed = false` — so a later reviewer rejecting any extension member can read the affected element set off the flags mechanically. |

### The pre-build game_id digest (the mandatory one)

```
GAME_ID_SET_SHA256 = e0083be22b32ddf5feaf55d010b1d22eb25ec75774546742eb90d4e3b3c4be1d
```

Rule, exactly as carded: sha256 over the U+001F-joined canonicalised `game_id` values, sorted
lexicographically on `str(game_id)` ascending, UTF-8.

Everything the obligation requires reported, **re-derived here rather than accepted from the
freeze**:

* `n_clusters = 1491`, `n_team_game_rows = 2982` — both match.
* per-season census `205 / 239 / 260 / 262 / 310 / 215` — matches.
* full-schedule reference `1495 / 2990`, D010 exclusion of the 4 games of `2021-05-14` — matches;
  the D010 caveat travels in the receipt.
* identity with the frozen store's `league_average_v1` game_id set — **holds exactly** (symmetric
  difference empty, both directions reported).
* 26 composite-uncovered clusters, `17 / 3 / 6` in 2021 / 2025 / 2026 — matches the card.
* zero settled ties (E3 well defined), zero null score values.

The receipt halts rather than proceeding on any of these.

---

## 3. The S35 carried-forward gap — closed by measurement

> "the pin states `join_key_columns [game_id, team_id]` but not the inter-column separator
> convention, so the join-key digest did NOT reproduce… **S36 must state the join-key separator
> convention explicitly**."

Closed, and **no digest was changed**. 576 candidate conventions were enumerated (four row
orderings × eleven intra-key separators × six inter-row separators × all-rows/unique-keys, plus
column-sequential and digest-of-digests forms). **Exactly one reproduces the frozen
`join_key_sha256` `6b8b2709…d59b`:**

* components joined **within a row** by `U+001E` RECORD SEPARATOR;
* rows joined by `U+001F` UNIT SEPARATOR;
* rows sorted lexicographically on `(str(game_id), str(team_id))` ascending.

A single-column key never exercises the inner separator, which is exactly why the three
`score_baseline_rows` pins always reproduced while the one two-column pin did not. All four frozen
column digests and both join-key digests now re-derive on every test run, and the suite also
asserts that the *wrong* (single-separator) reading does **not** reproduce — without that negative
control the test would pass for a bad reason. Written up in `BYTE_PIN_CANONICALISATION.md`.

---

## 4. What the implementations were checked against

### 4.1 Carded kill-stratum censuses — re-derived from this node's own feature code

Every kill in this slate fires on a subset defined by a feature this node builds, so reproducing
the carded censuses tests the implementations against the preregistration **end to end** — clock,
sequencing, support floors, row base — while computing no metric at all. A census is a count of
games.

| stratum | predicate | carded | re-derived at S36 |
|---|---|---:|---|
| SC01 early | `max(n_H, n_A) <= 12` | 472 pooled; 75/76/74/81/92; 74 in 2021 | **exact match, every figure** |
| SC01 rejected reading | `min(n_H, n_A) <= 12` | 516 | **516** — the A3 correction re-derives too |
| SC02 early | `min(n_H, n_A) <= 5` | 249 pooled | **249** |
| SC03 early | `min(n_H, n_A) < 10` | 399 pooled | **399** |
| SC12 high-bite | `|w_H - w_A| >= 2.0` | 652 pooled; 97/118/102/141/107; 87 in 2021 | **exact match** (see §5 F2) |
| SC06 habitat | `|F_H - F_A| >= 1`, rest components only | 78 pooled / 77 pooled-test / 17 pre-2024 test | **exact match** — this is the C2 power figure's support |

`CARDED_STRATA_RECEIPT.json`. The SC06 row carries the C2 power statement, because this census is
the number the statement is about.

### 4.2 Frozen card identity

All seventeen `card_sha256` values **re-derive from `SPEC_V2.json`** under the cycle-1 P35
canonicalisation and match the S35 freeze; every `element_id`, `arm_id`, `estimand`,
`primary_metric`, `arm_kind` and `family_primary` is checked against the frozen bytes rather than
transcribed. `SPEC_V2.json` itself hashes to `6402fc11…8945`, and the four input artifacts all
match their pins.

### 4.3 What the tests actually cover

Byte-pin reproduction (four column digests, both join-key digests, positive **and** negative
control); obligation-text fidelity against the frozen bytes; both label refusals in both
directions; blinding refusal on each real signature separately, plus the injected-unseal branch
with an assertion that the flag is absent from the real environment; seed derivation against the
frozen string and the **pairing property** (draw *b* identical across elements, different across
folds and purposes); games-never-split expansion; the two-sided p rule's symmetry; the K7
symmetric NA rule; each estimator against a case with a known closed-form answer (OLS exact
recovery, ridge shrinking only the masked columns and refusing an unnamed mask, IRLS recovering a
known coefficient and being bit-deterministic, dispersion Newton recovering σ₀ and γ, MoM matching
the closed form and clamping at 0); Layer-A parity plus three ways of breaking it; every element
building on every synthetic fold; each arm's characteristic transform (SC01 sum-to-zero exact,
SC03 deactivation is a strict subset with no rows dropped, SC06 era terms active in exactly the
two carded folds on both sides and the index taking only multiples of 0.25 within its pinned
bound, SC08 pace resolved on all 1,491 and the sum-vs-mean invariance proved to 1e-12, SC09 hinge
odd and flat inside the knee, SC10's covariate built but absent from the head, SC12 vanishing when
nothing is clipped); O2 enforcement by fault injection; one end-to-end synthetic fit per estimand
family; `run_element` refusing the real universe; and a sweep of every receipt on disk for
metric-shaped keys.

**What the tests do NOT cover: whether any arm helps.** That is sealed until S38 and adjudicated
at S40. Every fit in the suite runs on a structurally non-real fixture — 360 clusters, 720 rows,
`SYN_*` fold ids — and the fixture asserts its own non-realness so it cannot silently drift into a
real signature and stop testing anything.

---

## 5. Findings — raised, not resolved inside the node

**F1 — the slate-wide EWMA convention was unstated, and is now settled by measurement.**
No card says whether its EWMA is the recursive form or the finite-window form; cycle-1's P36
flagged the same gap as an open interpretive pin on A10. Sweeping 36 combinations of (adjust,
min_periods, floor handling), **exactly one** reproduces all seven of SC12's carded habitat
numbers, to the last printed digit: the **recursive** form (`adjust=False`). The finite-window
form reproduces none of them. Applied uniformly to SC04, SC10, SC11 and SC12 so one arm's
smoothing cannot disagree with another's, and re-run live on every invocation of
`verify_carded_strata.py`.

**F2 — a card-internal discrepancy in SC12, disclosed, changing no inference.**
The reproduction in F1 closes only with the `>= 3 prior games` support floor **not** applied —
while the same card's `parameters.fixed_pinned` and `fallback_cold_start` make that floor
normative. Both readings are frozen bytes, so neither is silently preferred: the module **builds
the normative reading**, and `CARDED_STRATA_RECEIPT.json` reports both side by side. The question
that matters is whether either kill changes behaviour, and measurement says no — the bite habitat
is 652 (no floor) vs 649 (floor), non-empty in every fold either way, so the arm-killing subset
stays checkable in all five folds; and the integrity-kill p90 is 4.7058 vs 4.6795, both roughly
4.7× the 1.0 threshold, so that kill cannot misfire under either reading. Raised to S37. The cards
are immutable from the freeze onward, so any repair is a new erratum record, never an edit.

**F3 — a contradiction between two frozen fields on the three E3 cards.**
`SC01::E3`, `SC06::E3` and `SC08::E3` list `composite_p_home` in `arm_spec.structural_terms`,
while their own `formula` fields fit only the composite **margin** through the link, and
`a4_sc08_null_strength_receipt` describes those E3 K0s the same way. The fitted-column reading is
additionally **not implementable as frozen**: the column carries 188 structural NaN rows
(re-measured here; the byte pin itself records `n_nan = 188`) and no card declares an imputation
for them. This node therefore implements `composite_p_home` as a null-granted **ingredient** —
byte-pinned, identical on both sides, consumed by `R_SC08_FLOOR` as the public-floor control
object — and records both readings. **Raised to S37, not reconciled.**

**F4 — SC09 cannot be materialised on the real universe here, and that is the card, not a gap.**
Its treatment feature is a hinge of the element's **own fitted K0 prediction**, and fitting is not
authorised until S37 passes. It is recorded as `BUILD_REQUIRES_K0_FIT / DEFERRED_TO_S38` rather
than quietly fitted to produce a column. The construction is fully implemented and fully exercised
on synthetic data, and `build()` takes the fold's K0 fit as an argument so that at S38 the runner
supplies the same K0 it is already fitting and no second, differently-fitted `g_hat` can come into
existence.

**F5 — three interpretive pins, declared rather than left implicit.**
*SC05:* `var_m` read as the pooled variance of team-game margins on the fold's **training** rows
(the card names it only inside a per-fold training-time MoM formula, and any other basis would
leak the test fold's dispersion into a training constant); and τ²/`var_m` as fold-train constants
while `n_home`/`n_away` are the row's own strictly-prior counts — the only reading under which
"feature = w·d_raw of the HOME club" is a per-game feature at all.
*SC06:* a **standard**-offset timezone map (no daylight saving — applying it would make the
feature date-dependent in a way the pin does not describe), covering exactly the six IANA zones in
the byte-pinned `team_cities.csv`, enumerated so that a franchise in a seventh zone fails closed
instead of being silently assigned an offset.
*SC08:* game-level pace read as the **sum** of the two sides — provably immaterial, because the
column is z-scored on train moments and z-scoring is scale-invariant; the suite proves
sum ≡ mean to 1e-12 rather than leaving it as a remark.

**F6 — a defect in this node's own first pass, self-caught and fixed.**
The λ-selection record initially wrote **train-tail MAE values** into
`DESIGN_PARITY_RECEIPT.json`. Computing them is unavoidable — the frozen cards make per-fold λ
selection part of the *construction* for SC01 and SC10, so those designs cannot exist without them
— but leaving them on disk violates "no performance number emitted anywhere". Constructing a
number in memory to satisfy a carded construction rule is authorised; persisting it is not. The
scores are now withheld (`selection_scores: WITHHELD_AT_S36_NO_PERFORMANCE_NUMBER_EMITTED`), and
the test that caught it was strengthened from whole-word to substring matching so the same shape
cannot slip through again.

---

## 6. Stop condition

**Not tripped.** Nothing here changes the cycle-2 estimands (E1/E2/E3), the K0 structure, the
inference structure, the declared universe (1,491 clusters / 2,982 rows), the cutoff-valid feature
set or the leakage status. F2 and F3 are contradictions **within** frozen bytes; both are carried
with both readings preserved and referred to S37 rather than resolved inside this node.

Nothing required money, credentials or a vendor API call.

---

## 7. Prohibitions honoured

* **No fit on real data.** The blinding gate refuses row counts {2982, 2990}, cluster counts
  {1491, 1495}, any D006 fold id, and any artifact hashing to a frozen real sha256, unless
  `S38_UNSEALED` is present — which is asserted absent from the process environment. Building
  feature matrices on the pinned universe is separately and explicitly authorised by the freeze,
  so the two boundaries are two different functions and cannot blur.
* **No performance number emitted anywhere.** No MAE, Brier, accuracy or arm-vs-null comparison is
  computed-and-reported or left on disk in any file. A test walks every receipt and refuses
  metric-shaped keys as substrings, with the three carded receipt slots asserted to be `None`
  until the sealed run. See F6 for the one instance this node caught in its own output and
  removed.
* Nothing under `stage2b/SEALED_RESULTS` or `stage3_score/SEALED_RESULTS` was read, listed or
  globbed.
* No frozen artifact modified. `git` was not run. All writes are inside
  `experiments/player_program/stage3_score/S36_IMPLEMENT_ARMS/` (60 files).
* Two other agents wrote concurrently under `experiments/market_program/` (disjoint) and the
  coordinator wrote orchestration files; none of those are this node's writes.

## 8. Reproduce

```
python build_manifest.py
```

which runs, in the order the obligations require:
`prebuild/PREBUILD_GAME_ID_DIGEST.py` → `runner/build_all.py` →
`runner/verify_carded_strata.py` → `tests/TESTS.py`, and refuses to write
`RUNNER_MANIFEST.json` if any step fails.

## 9. Note for the coordinator

`arm_registry.jsonl` currently holds **66** records and hashes to `0e95cd9a…`, not the S35
`post_append_expected` `6b43f40a…` / 65 records. Records 63 and 64 are exactly the SC07 withdrawal
and the S34-Severity-C obligations record, as expected; record 65 is a later A24 erratum append.
So this is a legitimate subsequent append, not a mutation — but the S35 post-append hash is no
longer a usable check and a fresh baseline should be recorded. **This node did not write to that
path.**
