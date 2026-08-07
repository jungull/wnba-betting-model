# S32B_K0_CONTRACT — the score-family `K0_MATCHED[arm_id::estimand]` contract and machine schema

**Node:** `S32B_K0_CONTRACT` · **Lane:** score · **Type:** documentation/specification ·
**Extends:** cycle-1 `P26_ARM_SPECIFIC_K0_CONTRACT` (possession lane) ·
**Mandated by:** `CYCLE2_TARGET_CONTRACT.md` §4, consistency finding B3 (the cycle-1 schema pins
`target = REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS` and cannot represent E1/E2/E3 controls).

## Epistemic status of this output

> K0 CONTRACT. Defines representable matched controls for E1/E2/E3; no card is registrable before this freezes.

---

## 0. Files this node produced

| file | what it is |
|---|---|
| `REPORT.md` | this document: adoptions, extensions, measurements, judgment calls, gaps |
| `K0_MATCHED_SCHEMA_SCORE.json` | JSON Schema 2020-12 for one score-family `K0_MATCHED[element_id]` record |
| `MEASURE.py` / `MEASUREMENTS.json` | every digest, column name, count and parameter cited by the schema, re-derived from the frozen artifacts (zero verification failures) |
| `TESTS.py` | 31 assertions: schema-vs-measurement consistency, the 17-dimension identity against the imported frozen gate, and positive/negative record validation (T5–T15) |

Nothing frozen was edited. No git command was run. Nothing under any `SEALED_RESULTS`
directory was read. `score_baselines.json` was opened by code that extracted ONLY its
`producer` and `inputs` provenance blocks — no floor value was read out of it and none
appears anywhere in this node's outputs (S30 §4 discipline).

---

## 1. What was measured (all by `MEASURE.py`, 2026-08-07)

### 1.1 Pins verified against bytes on disk — all pass

* `score_baseline_rows.parquet` → `5d1fc4c9af2334a6edd6ddffab91fe7cff5596578d9995937859a86cfc1e1452`
  — **matches** the S30 freeze pin.
* `CYCLE2_TARGET_CONTRACT.md` → `87cd094af1dbc3af49d77d6a1d745f1f728a7d40214bb26bb60edbffd67d1710`
  — **matches** the FULL-edition pin inside `TARGET_CONTRACT.json`.
* `build_score_baselines.py` → `65b7a94213d11703b5820b34c49e0926c465fe20ca4fd1b4a82d8f39d5fd03f8`
  — **matches** the `producer.sha256` recorded inside the frozen `score_baselines.json`
  (the builder was NOT edited after the store was produced).
* All four input-artifact hashes recorded inside `score_baselines.json` match bytes on disk
  (`master_team.parquet`, `team_possession_prior_v1.parquet`, `possessions_raw_v2.parquet`,
  `baseline_metrics.json`).
* `comparison_gate.py` → `c2d242581cc7551c6ce7d3aaf554f0cc18fd9b1f72677edd61ba95f91a7b5b92`;
  imported, `len(DIMENSIONS) == 17`; `k0_has_substantive_features` is in `BLOCKING`.

### 1.2 The frozen composite store, measured

`score_baseline_rows.parquet`: 4,412 rows, 12 columns
(`game_id, pred_home, pred_away, pred_total, pred_margin, p_home, game_date, season,
actual_total, actual_margin, y_home_win, method`), three methods
(`composite_pace_x_eff_v1`, `league_average_v1`, `team_scoring_avg_v1`), `game_id` dtype str.

**Composite rows (`method == composite_pace_x_eff_v1`): 1,465 games, `game_id` unique.**
Internal identities hold exactly: max |pred_home + pred_away − pred_total| = 0.0;
max |pred_home − pred_away − pred_margin| = 0.0.

### 1.3 The ingredient-column digests (the byte pins the schema freezes)

Convention, frozen in the schema and implemented in `MEASURE.py`: filter to
`method == composite_pace_x_eff_v1`; sort lexicographic on `str(game_id)` ascending;
canonicalise floats via `repr(float(v))` (NaN → `'nan'`), ints via `str(int(v))`,
timestamps via `.isoformat()`, else `str(v)`; join with U+001F; UTF-8; sha256.

| column | sha256 | n | n_NaN |
|---|---|---|---|
| `game_id` (join key) | `d3a4b7fac5399f8d5c7e27b969e8e9901e6e44846f95c42af7967aa7eb51d249` | 1465 | 0 |
| `pred_home` | `e754709cfc7b0779502af153b4b89e8a5d3ee3223b2e365bdc0d046e974d4525` | 1465 | 0 |
| `pred_away` | `9178138c5f94cc4dbe981ebdc2a94d2e8d030e4b9337f9cb8c0f7d12e98adebe` | 1465 | 0 |
| `pred_total` | `16c312aba2f964682f4d20a694b09890f4488f0e5bcdf31f827946158e145f3d` | 1465 | 0 |
| `pred_margin` | `1d79ff3adeda3d66e26f3bda1702d36301da447d87828c474d488d793de44ff4` | 1465 | 0 |
| `p_home` | `8a92c017e4f8606c3a7405116a455dc746493581454dc4dcbe1aab6d00b41989` | 1465 | 188 |

The 188 NaN `p_home` values are **all of the composite's 2021 games** — structural, not
missing data: the walk-forward win-probability logistic trains only on strictly-prior
seasons and 2021 has none. Measured per-season composite coverage: 2021: 188, 2022: 239,
2023: 260, 2024: 262, 2025: 307, 2026: 209; `p_home` is non-null on 100% of 2022–2026
composite rows.

### 1.4 Builder resolved parameters (the alternate byte-pin path)

From the imported builder module: `EFF_EWMA_SPAN = 10`, `EFF_ALPHA = 0.18181818181818182`,
`EFF_MIN_HISTORY = 3`, `BLEND = 0.5`, composite model version `composite_pace_x_eff_v1`;
win-prob = walk-forward logistic on `pred_margin`, strictly-prior seasons only.
Rows-store input artifacts: `master_team.parquet`
(`ad79ce5cdda7e058ba24be45243037252e3795a3e9f0c18cc41b3f12f3c38528`),
`team_possession_prior_v1.parquet`
(`c37c075148553920b79c9320ea03afb37986bfc752fc84dd695f154887c3db18`),
`possessions_raw_v2.parquet`
(`7200881fd811db9d0d6b10ea0a19b01ec7b6d027ee4567b9ef963241b15a4b1a`).
`bookie_baseline_metrics.json` is deliberately NOT in this pin: reading the builder source
shows it feeds only the market-comparison block, never the frozen prediction rows.

### 1.5 Coverage context for the S30 §2 floors (context, not adjudication)

Composite-covered games: 1,465 of the 1,491 base clusters = **98.26%** (≥ the 0.9 pooled
floor). Against the store's own per-season base counts (from `league_average_v1`, which
covers all 1,491), per-season composite retention: 2022: 239/239, 2023: 260/260,
2024: 262/262, 2025: 307/310, 2026: 209/215 — every test-fold season ≥ 0.8. The 2021
`p_home` NaNs sit entirely in training-years rows for the earliest fold; the schema
routes their declared treatment through `missing_value_handling` (stated identically on
both sides). Nothing here adjudicates any card's predicate — that is S33/S34's job.

---

## 2. What was adopted from P26, and why

Carried structurally unchanged, because the underlying failure modes are target-agnostic:

* **Map, not object** — one record per key; no universal control; `K0_FLAT` pinned
  `diagnostic_only` by `const` (beating it has no promotion value).
* **`arm_kind`** (six kinds) determining null shape and verdict-label eligibility;
  **`treatment_mechanism`** with `treatment_terms`, `tested_parameters`,
  `claimed_signal_axes`, `null_construction`.
* **Exclusion minimality, lower-order closure, structural closure, routing** (P26 §1.3,
  §1.4, §1.6) — carried as binding cross-field rules R2–R5, because JSON Schema cannot
  express them; P26 established that pattern explicitly.
* **The routing resolution of the featureless-K0 paradox** (P26 §1.4 / X5): structural
  terms live in `structural_terms` and are *declared* in a structural gate dimension with
  an identical string on both sides; `substantive_features` stays empty on the K0. This is
  load-bearing here — it is exactly how the null-granted composite ingredients enter the K0
  without tripping the frozen gate's `k0_has_substantive_features` block (re-measured: that
  kind is in `BLOCKING`).
* **All seventeen `comparison_gate.DIMENSIONS` required per side**, `UNSPECIFIED` never
  meaning "same as the other side". T3 asserts the schema's required list equals the
  imported frozen module's tuple, so the claim cannot rot.
* **`fold_local_fallback`** with numeric trigger declared before results.
* **`registered_before_results`, `verdict_label_policy`, `pipeline_id`
  asserted-not-demonstrated** (the frozen gate's documented gap, restated, still open).

## 3. What is new for score targets

1. **Element keying.** Records are keyed by `element_id = arm_id + '::' + estimand` —
   S30 §4's unit of testing is the (arm, estimand) pair, so the control map is per-element,
   not per-arm. `estimand` is an enum over E1/E2/E3; `invariants.target` is bound to it by
   conditionals (a record cannot swap targets, and the possession target is unrepresentable).
2. **`primary_metric` pinned per estimand** (E1/E2 → `mae`; E3 →
   `brier_raw_model_probability`), enforced by the same conditionals.
3. **`estimation_objective` as an explicit required block** — training loss, response
   family, shrinkage/regularization, and `p_clipping`; `matched_identically_for_arm_and_k0`
   is `const true` and the S36 void-the-arm consequence is a `const` in every record
   (cycle-1 P35 clause, carried verbatim per S30). For E3, `p_clipping.applicable` must be
   true with numeric bounds strictly inside (0,1); for E1/E2 it must be false with null
   bounds. `calibration_freedom` is additionally typed (`string`, `minLength 1`) in the
   sidespec — the one dimension that must never be inferred from silence now cannot be.
4. **The null-strength floor, pinned to bytes.** `null_strength_floor.status` is either
   `NULL_GRANTED_INGREDIENTS_CARRIED` (normal) or `CANNOT_HOST`. Carried ingredients are an
   array of terms, each routed to a structural dimension and each carrying a `byte_pin`
   that is one of two paths:
   * **Path 1 — frozen-store column digest:** artifact path + artifact sha256 + method
     filter + sort rule + canonicalisation + the `game_id` join-key digest (pinning row
     alignment) + the column name + that column's measured sha256, all `const`. The five
     admissible columns and their digests are enumerated as a `oneOf` of const-pairs, so
     **naming a column without its exact measured digest is schema-unsatisfiable** — a
     self-reimplemented "EWMA" that matches the name but not the bytes cannot validate.
   * **Path 2 — builder source + resolved parameters:** the builder's sha256, its resolved
     constants (span/alpha/min-history/blend/model-version/win-prob construction), and the
     three rows-store input-artifact hashes, all `const` (deep equality — T15 proves a
     changed parameter fails), plus a `const true` obligation that regenerated columns
     byte-match the path-1 digests. The two paths therefore pin the same bytes.
   * **Estimand containment:** an E1 record must carry `pred_total` (or the builder pin),
     E2 `pred_margin`, E3 `p_home` — enforced by `contains` conditionals (T8 proves an E3
     record carrying only `pred_total` fails). More ingredients may be carried.
5. **The cannot-host path is mechanical and down-labeled.** `CANNOT_HOST` requires: a path
   to a runnable mechanical demonstration; a demonstration kind from a closed enum
   (unrepresentable, or provably rank-deficient, in the declared design); an S34
   reproduction block whose receipt reference is null until a reviewer independently
   reproduces it (rule R7: no gate result citable while null); the exact verdict label
   `FEATURE VALUE OVER OWN NULL ONLY — BELOW-FLOOR NULL` as a `const`; inseparability,
   never-in-unqualified-tallies, S40→S42 routing, and the non-gating D045-floor-recomputed
   report obligation — all `const`s, per S30 §4.
6. **The canonical nesting reading, declared and frozen: cycle-1 containment** —
   null-granted terms appear in the arm's own design (arm = null terms + treatment). Two
   mechanical reasons, not preference: (a) under containment, arm-minus-K0 differs by
   exactly the treatment terms, so `challenger_vs_k0` stays a pure treatment contrast with
   unchanged Layer A semantics; (b) the ingredients are carried in structural dimensions
   that Layer A requires byte-identical on both sides, so a non-nested arm makes the
   declared strings differ and the frozen gate blocks it as a Layer A `dimension_mismatch`,
   escapable only through the loud, permanent `LAYER_A_OVERRIDE_CODE`. The frozen machinery
   itself makes any other reading extraordinary. A non-nested K0 remains representable —
   it is a harder test, not an exploit — but the record must declare the deviation before
   results, with the `NON_NESTED_K0_HARDER_TEST` label, the Δ-semantics change, and the
   frozen-gate consequence spelled out (T12 proves silence fails).
7. **Coverage-predicate reference fields** matching S30 §2 exactly: information-based
   cutoff-valid predicate text, market fields barred, identical for arm and K0, base
   universe consts (1491 / 2982), the 0.9 pooled and 0.8 per-fold floors as consts, the
   mandatory non-gating all-covered sensitivity row, whole-fold structural deactivation in
   cycle-1 card-declared form only (numeric trigger + symmetric + before any fit, when
   declared), and selection visibility.
8. **`comparison_gate_binding`** — every record pins the frozen gate module's sha256 and
   the 13-prose→17-machine mapping authority (`comparison_gate.LAYER_A_STRICT`, whose
   own import-time assertion proves exact single coverage). If the frozen module's bytes
   ever changed, every record would fail loudly.
9. **`k0_spec.substantive_features` capped at `maxItems 0`** — the state the frozen gate
   blocks is now unrepresentable at the schema layer too (T7).
10. **Score signal axes** added to `claimed_signal_axes` (home_court, schedule_rest_travel,
    era_2024_charter_break, referee_crew, score/efficiency observation, early_season_transient)
    matching the D047 directed families; cycle-1 axes retained.
11. **Optional `distributional_secondary` block** (S30 §5): if present, it must declare
    matched functional form, train-years-only dispersion, matched quantile grid, matched
    home/away covariance treatment, and the sealed-until-S40 / never-a-promotion-basis
    status as consts.

## 4. Judgment calls, each with its reason

1. **"Ingredient columns" read as the five composite prediction columns** of the frozen
   store (`pred_home, pred_away, pred_total, pred_margin, p_home`), not the upstream raw
   pace/efficiency series. Reason: the store is the frozen, hash-pinned form of the
   composite's ingredients that S30 names by artifact; the upstream series exist only
   transiently inside the builder, and path 2 (builder bytes + resolved parameters + input
   hashes + regeneration byte-match) covers any arm that needs them at finer grain.
2. **`game_id` pinned as join key inside every column pin**, so a column digest can never
   silently ride a different row order or subset.
3. **Digest canonicalisation frozen to the `MEASURE.py` convention** (sort rule, float
   `repr`, U+001F join). Any deterministic convention would do; this one is now the one,
   stated verbatim in the schema so an independent verifier can reproduce every digest.
4. **Estimand-minimum containment with more allowed** — e.g. an E2 K0 may also carry
   `p_home`. The floor requires at least the estimand's own composite output; granting the
   null more strength is never an exploit.
5. **Cycle-1 containment picked as the canonical nesting reading** — see §3.6; the frozen
   gate's Layer A behavior, not taste, decides it.
6. **`bookie_baseline_metrics` excluded from the builder pin** — it feeds only the
   market-comparison block of the builder, never the prediction rows (read from source;
   T2 asserts the exclusion).
7. **The 2021 `p_home` NaNs handled through `missing_value_handling`**, not by shrinking
   the schema's universe consts: the NaNs are structural (no prior season), sit entirely
   outside the test folds, and their declared treatment must simply be identical on both
   sides. The schema annotates this at the dimension itself.
8. **No S-lane fold-local threshold owner exists yet** — the `fold_local_fallback` field is
   declared and required exactly as P26 did, with the ownership gap stated rather than a
   threshold invented here.
9. **`registered_before_results` kept `type boolean`** (not `const true`), matching P26:
   the record must state it, and rule R6 makes truth-before-visibility a validator/audit
   check — a `const` would only force authors to write `true` while drafting, hiding the
   lie rather than preventing it.
10. **Cross-field rules listed inside the schema** (`x_cross_field_rules_binding`, R1–R10)
    rather than in prose only, so the future validator has its exact worklist and a record
    author cannot claim ignorance. Custom `x_` keys are legal JSON Schema annotations.

## 5. What I could NOT establish

1. **No conformant JSON Schema processor exists in this environment** (`jsonschema` not
   importable — re-measured, same as P26 gap 4). `TESTS.py` T5–T15 run against a stdlib
   subset validator implementing exactly the keywords this schema uses; a keyword outside
   that set would be silently ignored. The schema file is valid 2020-12 and should be
   handed to a real processor when one is available.
2. **No cross-field validator is shipped.** P26 shipped `validate_k0_matched.py`; this
   node's mandate was the schema + report. Rules R1–R10 are enumerated and binding, but
   until an S-lane validator node exists, a record can satisfy this schema while violating
   them and nothing mechanical will notice. That validator (and the call-site order:
   contract checks first, then the frozen `comparison_gate.require_matched_k0`) is the
   natural next node.
3. **No real S-lane arm exists yet** — the schema is unexercised against real candidates;
   `TESTS.py`'s records are constructed examples. First real exercise is S33+.
4. **`pipeline_id` remains asserted, not demonstrated** (frozen gate `REMAINING_GAPS`,
   carried; nothing here closes it).
5. **The S30 §2 pooled-floor denominator** ("≥ 90% of the 1,491 clusters pooled") includes
   2021, which is never a test fold under the five pinned folds. I carried the consts
   exactly as written and did not reinterpret; the measured coverage context (§1.5) shows
   the frozen composite itself clears both floors either way, but a future card near the
   boundary would need S33/S34 to resolve the reading. Raised, not resolved.
6. **Float-`repr` stability across Python versions** is relied on by the digest convention
   (stable since CPython 3.1's shortest-repr algorithm, and re-derivable by re-running
   `MEASURE.py`); a non-CPython verifier must use the same shortest-round-trip float
   formatting or digests will not match. Stated so a mismatch is diagnosable, not mysterious.
7. **Nothing about performance.** No comparative historical performance was inspected; no
   metric value left `score_baselines.json`; no `SEALED_RESULTS` directory was read.

## 6. Stop conditions

Per S30 §11: nothing in this node changes the estimands, the inference structure, the
declared universe, the cutoff-valid feature set, or the leakage status. The K0 structure is
*defined* here for the score lane exactly as S30 §4 mandates a node to do; the one
raised-not-resolved item is §5.5 (the pooled-floor denominator reading), which sits inside
S30's own text and is flagged for the coordinator rather than resolved inside this node.

---

*Freeze note: at freeze, this node's outputs should be sha256-pinned in the events ledger.
An independent verifier can reproduce every number in this report by running
`MEASURE.py` (writes `MEASUREMENTS.json`, exits nonzero on any pin mismatch) and
`TESTS.py` (31 assertions, exits nonzero on any failure).*
