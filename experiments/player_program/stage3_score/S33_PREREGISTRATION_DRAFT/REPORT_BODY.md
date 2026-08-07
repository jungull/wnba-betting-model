# S33_PREREGISTRATION_DRAFT — score lane, cycle 2 — report body

**Node:** `S33_PREREGISTRATION_DRAFT` · **Lane:** score · **Type:** preregistration ·
**Binding law:** `CYCLE2_TARGET_CONTRACT.md` (FROZEN FULL edition, sha256 re-verified this node)
· **Candidate universe:** `S32_CANDIDATE_SYNTHESIS/CANDIDATES.json` (12 arms / 18 elements / 9
families) · **Control schema:** `S32B_K0_CONTRACT/K0_MATCHED_SCHEMA_SCORE.json` (frozen)

## Epistemic status

> PREREGISTRATION DRAFT. This node froze the complete specification of every retained
> (arm, estimand) element before any fit. Nothing here is an empirical result. No fit was
> performed; no predictive performance number was computed or read; nothing under any
> `SEALED_RESULTS` directory was read, listed or globbed; git was not run. Every number in
> this report is a coverage, census or existence measurement, and each carries the command
> that produced it.

## 0. Outputs and the headline

| file | what it is |
|---|---|
| `SPEC.json` | machine-readable preregistration: shared universe block, seeds/inference, multiplicity + program-alpha, the SC07 withdrawal record, 11 arm blocks, 17 `K0_MATCHED` records (one per element), self-validation results |
| `REPORT_BODY.md` | this document (the coordinator materializes `REPORT.md`) |

**Headline: 11 of 12 arms retained; 1 withdrawn (SC07, referee crew — measured provenance
failure); 17 elements; 8 mechanism families under the primary partition (10 under the maximal
disputed partition); program-alpha additive bound 0.40 / 0.50 respectively; every element's
K0_MATCHED record validates against the frozen S32B schema (17/17 PASS, plus mechanical
cross-field checks).**

---

## 1. Inputs verified (sha256, re-derived this session)

Every binding input was re-hashed before use; the full map is `SPEC.json →
inputs_verified_sha256`. Anchor pins, verified equal to their frozen references:

* `CYCLE2_TARGET_CONTRACT.md` → `87cd094a…7710` — matches the `TARGET_CONTRACT.json` FULL-edition pin.
* `score_baseline_rows.parquet` → `5d1fc4c9…1452` — matches the S30 freeze pin and every
  column-pin const in the S32B schema.
* `master_team.parquet` → `ad79ce5c…8528`, `team_possession_prior_v1.parquet` → `c37c0751…db18`
  — match the builder-pin consts.
* `comparison_gate.py` → `c2d24258…5b92` — matches the schema's `comparison_gate_binding` const.

Command pattern (all hashes): `Get-FileHash -Algorithm SHA256 <path>` /
`hashlib.sha256` over raw bytes in the measurement scripts below.

## 2. Universe and denominators — measured, not asserted

Command (python + pandas, run this session; logic restated so any auditor can reproduce):

```python
mt = pd.read_parquet("data/masters/master_team.parquet")
home = mt[mt.is_home == 1]                       # 1,495 games / 2,990 rows
first = home[home.season == 2021].game_date.min()  # 2021-05-14, 4 games
uni  = home[home.game_date > first]              # 1,491 games / 2,982 rows
```

* **1,491 game clusters / 2,982 team-game rows** after excluding the 4 games of the first
  2021 date (D010; identical to the cycle-1 P33 derivation). Both counts are reported
  everywhere per §2 of the contract.
* Measured identity: the frozen store's `league_average_v1` game_id set **equals** this
  universe exactly (`set(lg.game_id) == set(uni.game_id)` → True). The universe is therefore
  pinned to a frozen artifact, not just to a filter rule.
* Per-season clusters: 2021: 205 · 2022: 239 · 2023: 260 · 2024: 262 · 2025: 310 · 2026: 215.
* **Zero settled ties** (E3 well-defined) and zero null scores in the universe.
* Folds (train_lt_Y: train = seasons < Y, test = season Y): train/test cluster counts
  205/239, 444/260, 704/262, 966/310, 1276/215. **Pooled-test denominator = 1,286.**
* **Both denominators (1,491 pooled and 1,286 pooled-test) are reported for every element,
  stricter governs** — the S32B report §5.5 raised the denominator-reading question; this
  slate makes it moot by measurement (every element retains 100% under either), and the
  reading question itself stays flagged for any future boundary card rather than silently
  resolved here.
* D010 caveat carried verbatim: the universe excludes the 2021 opening day; cold-start
  figures are flattered by construction; no cold-start claim may cite the missing stratum.

## 3. Coverage posture — one shared predicate, measured

All 11 retained arms declare the same posture (S32 already recommended it; this node
measured it): **no trimming predicate anywhere**. The only information-based coverage
boundary in the pipeline is composite-store absence for 26 clusters. Measured:

* Composite covers 1,465/1,491 pooled = 98.26%; uncovered 26 = 17 (2021) + 3 (2025) + 6 (2026).
* **All 26 uncovered games have a side with < 3 strictly-prior games** (measured by
  recomputing per-team strictly-prior any-season game counts against each uncovered game
  date: `min_prior_games_lt_3: 26, other: 0`) — i.e. the cause is exactly the builder's
  `EFF_MIN_HISTORY = 3` information condition, cutoff-valid by construction.
* Fallback, identical both sides, declared in `fallback_rules`: those 26 clusters take the
  frozen store's `league_average_v1` row for the same game_id (same hash-pinned artifact).
  Retention is therefore **1491/1491 pooled (100%), 1286/1286 pooled-test (100%), and
  239/239 · 260/260 · 262/262 · 310/310 · 215/215 per fold (100% each)** against the
  90%/80% floors. The mandatory all-covered sensitivity row coincides with the gated row
  for every element; the §2.4 dropped-game receipt will read "0 dropped".
* Context: had an arm instead trimmed to composite coverage, per-fold test retention would
  have been 100/100/100/99.03/97.21% — also above floor. Measured for the record; not used.
* p_home is NaN on the 188 structural 2021 composite rows (no prior season for the
  walk-forward calibration — S32B's measurement, cited); these sit entirely in training
  years of the earliest fold, and every E3 record declares their handling identically on
  both sides through `missing_value_handling`.

## 4. The SC07 withdrawal — resolved by measurement, as mandated

The S32 registration was conditional on two blocking preconditions. Both were measured:

**(a) Historical crew identity — EXISTS.** `data/officials_master.csv` (sha256 in SPEC):
4,550 official-game rows, 63 distinct officials, covering **1,485 of 1,491** universe games
(205/239/260/262/310/209 per season; the 6 missing are 2026 games); crew sizes 3 (1,402
games) or 4 (83); `SOURCE == "v2"` (boxscore lineage) on every row. These are as-worked,
postgame-published records — admissible **lagged** facts, sufficient for building a
strictly-lagged crew tendency.

**(b) Pregame assignment provenance for the same-game join — FAILS, decisively.** The only
witnessed capture stream is `data/ref_assignments/assignments_log.csv`: **69 rows, 8
distinct games, captures 2026-07-30T17:08Z through 2026-08-01T14:00Z** (plus raw JSON/HTML
snapshots in `data/ref_assignments/raw/`, all 2026-07-30 onward). It cannot cover
2021–2026. Joining the as-worked `officials_master` crew to its own game on the prediction
side is exactly the P2B failure shape the contract cites by name — a retrospective record
is a claim about a past instant, not a witness to it — and an as-worked crew can differ
from the pregame assignment (late scratches), so it additionally encodes realized facts.
Separately, the upcoming game's crew is not in the contract's closed schedule-identity
column set, so consuming it would also need an S34 set-extension — moot given the
provenance failure.

**Disposition:** SC07 is **WITHDRAWN** — not registrable this cycle; recorded with these
receipts rather than carding an unfittable arm; lapses without penalty; `FAM_S2_REFEREE`
leaves the family table (shrinking the program-alpha bound). Prospective path recorded: the
witnessed stream that began 2026-07-30 accumulates toward a future-cycle registration with
T0 provenance. (Consistent with the S32 slate's own stated most-likely failure for this arm.)

## 5. What was frozen per element (summary; SPEC.json is authoritative)

Uniform head convention (Judgment call J1, below): every element is a single per-fold
train-fit head — OLS (E1/E2), bernoulli-logit IRLS (E3 GLM arms), or the SC08 probit margin
map — whose design is **intercept + the byte-pinned composite column for the estimand
(train-fitted coefficient) + the arm's treatment terms**. The K0 is the identical head minus
exactly the treatment terms (containment; R2 exclusion minimality checked mechanically).
`estimation_objective` (loss, response family, shrinkage, p-clipping [0.001, 0.999] for E3)
is declared identically on both sides; any S36 deviation voids the arm.

| element | treatment (fitted df in head) | key pins |
|---|---|---|
| SC01::E2/E3/E1 | interacting off/def strength recombination (1) | two-season window; ridge grid {2,8,32,128}; sum-to-zero; §5 covariance receipt mandatory |
| SC02::E1/E2 | A07 transient sum/diff (1) | tau = 5 carried pinned; concentration table MANDATORY (D042/D043) |
| SC03::E2/E1 | shrunk-faded prior-season carryover (1) | lambda 0.5, K = 10; fold-1 structural deactivation declared |
| SC04::E2 | centered lagged league HCA EWMA (1) | halflife 60; centering = identification |
| SC05::E2 | EB-shrunk team home offset (1) | deterministic MoM tau²; 2+2 support floor |
| SC06::E2/E3 | fatigue diff + charter-era interaction (2) | pinned index 1.0/0.5/0.25; era terms active only in folds 4–5 (declared) |
| SC08::E3 | log-linear dispersion covariates (2 + σ0) | mu frozen pre-dispersion; nested K0 at γ=0 |
| SC09::E2 | hinge on the K0's own prediction (1) | knee 8; sign-pinned negative |
| SC10::E1/E2 | two within-season horizon spreads (2, ridged) | halflives 4/12; L_prevseason term dropped (J5) |
| SC11::E1 | centered lagged league total EWMA (1) | halflife 60; E2 integrity receipt, bound 0.10 |
| SC12::E2 | winsorized-minus-raw EWMA correction (1) | cap ±15 frozen (J6); 8% inertness floor |

Every element additionally freezes: feature lineage (column → artifact hash → lag
semantics), fallback/cold-start, kills each with a receipted sealed-run diagnostic,
expected failure mode, family assignment (disputed ones under both partitions,
stricter governs), and its full K0_MATCHED record against the frozen schema.

## 6. Feasibility and kill-stratum measurements (commands in the scripts; all counts, no performance)

* Early-season strata (min of the two sides' same-season strictly-prior counts):
  **≤ 5: 249 pooled** (40/40/39/42/49 per test season) — SC02's concentration stratum;
  **< 10: 399** (64/62/64/67/78) — SC03's habitat; **≤ 12: 516** (81/80/82/88/103) — SC01's
  early stratum. All non-empty in every fold: every early-season kill is checkable.
* Fatigue (rest components only; tz adds at sealed-run receipt time): 89 back-to-back
  team-games, 88 third-in-four; **|F_H − F_A| ≥ 1: 78 pooled clusters** (8/9/19/29/12 per
  test season; 18 pre-2024 vs 60 in 2024+ — the charter era has *more* B2B differentials,
  so the era interaction is estimable where it is active). Thin habitat recorded as SC06's
  honest survival risk. 111 clusters at ≥ 0.5.
* SC12 incidence: **26.16%** of universe settled margins exceed 15 absolute (390/1,491);
  margin 5th/95th percentiles −21/+24 — the ±15 cap and the 8% inertness floor are live.
* SC09 habitat proxy: **8.94%** of composite-covered clusters have |frozen `pred_margin`| > 8
  (131 games) — *below* the 10% habitat kill on the raw column; the recalibrated g_hat may
  shift it either way; recorded before any fit as the arm's most likely death.
* SC08 supports: pace prior resolved on **all 1,491** universe games; the margin-sd ≥ 4-game
  support holds for 1,455/1,491 (fallback touches 36).
* SC06 travel table: `data/reference/team_cities.csv` (sha256-pinned in SPEC) covers **every
  universe team_id** incl. the 2025/2026 expansion clubs, with IANA zones mapped to pinned
  standard offsets in the card.
* SC03's open question from S32, answered by reading the frozen builder source
  (`build_score_baselines.py` lines 57–69): the composite's efficiency EWMAs are
  **continuous across seasons at full weight** (`EFF_MIN_HISTORY = 3`, "CONTINUOUS ACROSS
  SEASONS"), and the pace prior uses same-season-first windows with prior-season fallback.
  Consequence frozen as J4 below.

## 7. Judgment calls (each deliberate, each reviewable)

1. **J1 — uniform head convention.** Every arm hosts the null-granted column as a
   train-fitted linear regressor inside a single head; `calibration_freedom = "none"`
   explicitly on both sides. This makes the K0 an affine recalibration of the frozen
   composite — at least as strong as the composite itself (it absorbs the builder's
   documented no-HCA margin bias and regulation-equivalent total bias) — and makes every
   Δ a pure treatment contrast under containment.
2. **J2 — full universe + fallback instead of a 98.26% trim.** Measured either way; chosen
   because it keeps arm and K0 on the identical 1,491 universe, makes the sensitivity row
   coincide with the gated row, and pins the fallback to a frozen artifact row rather than
   an invented value.
3. **J3 — E3 K0 probability path.** Per-fold train-refit of the margin→probability map on
   the composite margin (logit for GLM arms, the probit margin map for SC08). For test
   season Y, "train = seasons < Y" is *exactly* the frozen builder's walk-forward
   construction of `p_home`, so the K0's probability path structurally reproduces the
   public floor; the frozen `p_home` column is additionally carried (satisfying the
   schema's E3 containment conditional via the path-1 byte pin) as a non-predicting anchor
   with a receipted agreement diagnostic. S34 should review this reading explicitly.
4. **J4 — SC03 direction de-pinned.** The measured builder continuity (§6) removes the
   premise under which S32's `beta <= 0` kill presumed a direction (under-carry). Whether
   the null over- or under-carries across the boundary is now genuinely open (shrink-vs-
   full-weight is the live question), so the directional kill is replaced by a
   sign-consistency kill (same sign in ≥ 3 of the 4 evaluable folds) plus the unchanged
   early-subset and leave-one-season-out kills. This is the node's principal
   measurement-driven amendment to the slate.
5. **J5 — SC10 drops the `L_prevseason_shrunk` term** from the spread block: cross-season
   initialization is FAM_S2_EARLY_SEASON's habitat (SC03); double-registering it in
   FAM_S2_FORM_DYNAMICS would blur the family partition the multiplicity correction relies
   on. SC10 is now purely within-season.
6. **J6 — SC12 clip frozen to the fixed ±15 cap** (the slate's 2-option preserved set,
   frozen to one as directed): pre-computable, transparent, does not drift with strength
   spread; the train-quantile variant stays a cited alternative, unregistered.
7. **J7 — SC04's "2021 test split" kill reworded.** 2021 is never a test season under the
   pinned folds — the slate's wording was uncheckable as written (an uncheckable kill is a
   card defect). Replaced by leave-one-test-season-out single-season dependence, which
   covers the 2022 reopening boundary without naming a season.
8. **J8 — SC06 era terms structurally deactivated in folds 1–3** (zero training variance:
   folds train_lt_2022/2023 have no 2024+ rows anywhere; train_lt_2024 has none in
   training), declared before any fit with numeric trigger 0, symmetric — the P26
   zero-variance-on-the-control pattern. The era main effect is carried as a structural
   nuisance term on both sides (R5 lower-order closure for the interaction).
9. **J9 — SC08 mean frozen as the per-fold train-affine map of the composite margin**, both
   sides, before any dispersion fit (mu-frozen identification); historical-OT variance
   inflation folded into σ0 (league OT rate treated as constant — declared simplification).
10. **J10 — SC01 pins:** two-season observation window; ridge grid {2, 8, 32, 128} with the
    80/20-by-date train-tail selection rule; points scale directly (the optional
    per-possession recombination is not registered — fewer moving parts, and the pace
    ingredient already lives inside the null-granted composite). Grid justified as a
    logarithmic spread on the effects scale; no floor/bar value informs any grid (a
    mechanical numeral scan for the three D043 bar values over SPEC.json and this file
    passed; S34 re-checks independently).
11. **J11 — `invariants.rows` deferred to S36** with a fail-closed obligation: the schema
    requires a `row_digest` string; no matrix exists before the build, so every record
    carries the explicit TO_BE_EMITTED_AT_S36_BUILD contract (universe pinned meanwhile by
    count, per-season census, and the measured identity with the frozen store's
    `league_average_v1` id set). S34 should confirm this reading or demand a pre-build digest
    of the game_id set itself.
12. **J12 — stratum clocks.** All early-season strata use min(n_H, n_A) — the conservative
    reading (a stratum game is one where *both* sides are early); SC01's stratum wording
    "each team ≤ 12" is exactly min ≤ 12.
13. **J13 — seeds.** Master seed 20260807; the cycle-1 derivation function unchanged; one
    test-bootstrap stream per fold shared by every arm and null (paired), one train-refit
    stream per fold; all fits deterministic — a stochastic fitting step violates the card.

## 8. Multiplicity, program alpha, and gate

* Element = (arm, estimand); 17 elements; families by mechanism: **8 primary / 10 maximal**
  (disputes: FAM_S2_EARLY_SEASON split; FAM_S2_BLOWOUT_DISCOUNT split; the SC04+SC11
  lagged-league-drift merge, which does not change the count). Every disputed element must
  survive Holm under **both** partitions; stricter governs.
* **Program-alpha declaration (cycle-1 P35 restatement): no program-wide FWER claim; the
  additive bound is 8 × 0.05 = 0.40 (primary) / 10 × 0.05 = 0.50 (maximal).**
* Multi-survivor comparisons are within-estimand only, matched-universe rule enforced.
* Gate (a)–(d) restated per element in SPEC; kills uncorrected; every kill diagnostic is a
  declared sealed-run output (each is listed next to its kill in the arm blocks).
* Covariance obligation (§5): SC01 is the slate's only side-splitting arm; its per-side
  variances / covariance / corr(e_home, e_away) receipts are mandatory sealed outputs.
* SC02's early-stratum concentration table is a MANDATORY sealed output (D042/D043); its
  absence is a card defect.

## 9. Self-validation (schema + cross-field), and its limits

Command: the generator script validates each record against
`K0_MATCHED_SCHEMA_SCORE.json` using the stdlib subset validator re-implemented verbatim
from S32B `TESTS.py` (same keyword coverage), then runs mechanical cross-field checks
R1–R5 and R11 plus full 17-dimension Layer-A sidespec string identity between arm and K0.

**Result: 17/17 elements PASS both.** Recorded per element in `SPEC.json →
self_validation`. Limits, stated:

* No conformant JSON Schema 2020-12 processor exists in this environment (`jsonschema` not
  importable — same gap S32B and P26 recorded); a keyword outside the subset would be
  silently ignored. Hand the records to a real processor when available.
* R6 (truth-before-visibility), R7 (no CANNOT_HOST element exists in this slate — the path
  is never invoked, as S32 predicted), R8 (moot at 100% retention), R9 (an S36-time check),
  and R10 (validator recomputation of digests from the artifact) are audit-time rules that
  this node cannot discharge; they fall to S34/S36/S37 as the schema assigns them.
* `pipeline_id` remains asserted-not-demonstrated (frozen gate's documented open gap).

## 10. What I could NOT establish

1. **`game_date` scheduled-vs-as-played status** — the card's one CUTOFF_UNPROVEN field.
   Named S37 promotion measurement (required before any consuming element's sealed result
   is citable): cross-check every universe `game_date` against `data/reference/tip_times.csv`
   captures (2022+) and the refresh artifacts; enumerate deviations; classify postponement
   rewrites; recompute or receipt affected features. Primary exposure: SC06.
2. **The pooled-floor denominator reading** (S32B §5.5) — measured moot for this slate
   (100% retention under both readings); the reading itself remains unresolved and flagged.
3. **P22 guard fitness on score surrogates** — the contract itself assigns this
   verification to S37; the card carries the obligation, not the proof.
4. **SC09's habitat** — the measured proxy (8.94% < 10%) says the arm likely dies at its
   own habitat kill once g_hat is recalibrated; whether recalibration lifts it above
   threshold cannot be known without fitting, which this node may not do. Preregistered
   honestly rather than quietly retuning the knee.
5. **No cross-field validator is shipped for the S-lane** (S32B gap 2, still open): my
   cross-field checks cover R1–R5/R11 mechanically; a dedicated validator node remains the
   natural next build.
6. **The 6 universe games missing from `officials_master.csv`** (all 2026) are recorded for
   completeness; nothing in the retained slate consumes officials data.

## 11. Final counts and the biggest unresolved risk

* **Retained: 11 arms. Withdrawn: 1 (SC07). Elements: 17. Families: 8 primary / 10 maximal.
  Program-alpha additive bound: 0.40 / 0.50.**
* Biggest unresolved risk: **the `game_date` as-of-cutoff assumption (CUTOFF_UNPROVEN #1)**
  — it underpins the rest/travel arm directly and the (date, game_id) sequencing of every
  lagged construction indirectly; if S37 finds postponement-rewritten dates in-universe,
  SC06's features and, in the worst case, several EWMA sequencings must be re-derived
  before any sealed result is citable. Second risk, structural: with the null-strength
  floor granting every K0 an affine-recalibrated composite, most 1-df arms are honestly
  expected to die (cycle 1: 29 fitted, 0 passed); the slate's value is that each death is
  now cheap, receipted, and informative.

## 12. Prohibitions honoured / stop conditions

No fit; no performance number; no `SEALED_RESULTS` access of any kind; no frozen artifact
modified; no git; writes confined to
`experiments/player_program/stage3_score/S33_PREREGISTRATION_DRAFT/` (`SPEC.json`, this
file). Stop conditions per contract §11: nothing in this node changes estimands, K0
structure, inference structure, declared universe, cutoff-valid feature set or leakage
status; the SC07 withdrawal removes a candidate, which S32's registration explicitly
provided for ("lapses without penalty"). This node does not mark its own work accepted;
S34 adjudication governs.
