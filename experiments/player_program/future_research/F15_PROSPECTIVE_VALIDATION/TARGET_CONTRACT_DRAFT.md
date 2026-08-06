# F15_PROSPECTIVE_VALIDATION — TARGET CONTRACT DRAFT

**Node:** `F15_PROSPECTIVE_VALIDATION` · **Lane:** future_research · **Type:** documentation ·
**Severity on failure:** C · **Role:** read-only research scout
**Governing scientific contract:** `RESEARCH_CONTRACT_V1` · **Branch:** `player-model-program`
**Depends on:** `G04_PROGRAM_ROADMAP_EXTRACTION` · **Written:** 2026-08-04

## Epistemic status of this output

> DIAGNOSTIC AND TARGET-CONTRACT DRAFT ONLY. Discovery work being unblocked is NOT authorisation to fit. Fitting requires a target contract, a matched K0, cutoff-valid evidence, a preregistration and an independent gate review.

## THIS DRAFT DOES NOT AUTHORISE FITTING

**This draft does NOT authorise fitting.** No fit, refit, tune, arm registration, comparison against
a control, or grading of any logged forecast is authorised by anything below. No model code was
written or run. No comparative historical performance of any challenger was inspected.
`stage2b/SEALED_RESULTS/` was not opened. No forecast in `forecasts/forecast_log.jsonl` was joined
to its outcome — see §3.1, where the refusal is itself a contract requirement and not merely a
courtesy.

Independently: `PROGRAM_STATE.json` `state_of_play.experiment_currently_authorized = false` and
`stop_boundary.in_force = true`.

---

## 1. The estimand

### **NOT_DERIVABLE_FROM_DOCUMENTATION**

There is no documented estimand — no target statistic, no unit, no denominator — for a **prospective
validation of the player program**. I did not invent one. What exists instead is two fully
registered prospective contracts that belong to the *team* thread and grade *market* statistics, and
one written estimand inside the player program that is explicitly **retrospective**. Those are
inventoried below; none of them is this node's estimand, and importing either would be the
invention this node is forbidden to make.

### 1.1 The negative, and the proof that the search producing it works

G04 catalogued 42 proposed items with citations (`orchestration/reports/ROADMAP_EXTRACTION.json`,
`counts`: 42 proposed / 13 needing a target contract / 5 human-gated / 33 blocked). The string
`F15` occurs **0 times** in it; sibling ids resolve normally, so the zero is a real absence:

```
python -c "import json; d=json.load(open('experiments/player_program/orchestration/reports/ROADMAP_EXTRACTION.json')); s=json.dumps(d); print([(n, s.count(n)) for n in ['F10','F11','F12','F13','F14','F15','F16']])"
# [('F10', 2), ('F11', 1), ('F12', 0), ('F13', 2), ('F14', 1), ('F15', 0), ('F16', 1)]
```

Five of the seven `future_research` nodes are mapped in G04's `already_modelled` block to a
documented parent item. **F12 and F15 are the two that are not.** F15's title has no documentary
parent either; it is an `(id, title)` pair in the graph seed —
`orchestration/scripts/seed_graph.py:933` `("F15_PROSPECTIVE_VALIDATION", "Prospective validation
design"),` — propagated to `orchestration/PROGRAM_GRAPH.json:4125` `"title": "Prospective validation
design"`. F15 inherits the *form* of a target-contract node without having been given a target.
(F12's draft records the same structure for itself; I re-ran the count rather than citing it.)

A second, independent negative, measured on raw bytes over 608 files under
`experiments/player_program/` (`SEALED_RESULTS/` excluded and not read):

```
files scanned 608
estimand                                          156 hits, 26 files
REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS  147 hits, 124 files   <- positive control
prospective                                       490 hits, 104 files
holdout                                             7 hits,  3 files
out-of-time / out_of_time                            0 hits,  0 files
```

The positive control fires on 124 files, so the sweep reads bytes correctly. Of the 26 files
containing the word `estimand`, **25 are this orchestration graph's own files** (the seven F-node
prompts, `PROGRAM_GRAPH.json`, `GRAPH_POLICY.md`, `DECISION_LEDGER.jsonl`, G04's two reports, and
the sibling F-node outputs written in this same wave). Exactly **one** pre-existing program document
uses the word: `stage2a/PHASE0A_RESOLUTION.md:138`. The concept enters the player program's
vocabulary through this graph, not from the program record.

### 1.2 What I did find — three anchors, none of them a prospective estimand

**(a) The program's one written estimand is retrospective, and says so in its own construction.**
`stage2a/PHASE0A_RESOLUTION.md:138-140`, verbatim:

> **Estimand.** The population mean absolute error of the downstream operational turnover-team
> prediction over the contract's team-game universe, and its paired difference against a matched
> control on identical rows.

with, in the same block: `:142` *"Equal weight per team-game row. Each game therefore contributes
weight 2."*; `:146-148` *"Chronological, nested, by season, as the incumbent's own walk-forward:
train strictly earlier, evaluate on the held-out season. **A game is never split across folds***";
`:150-152` *"Game-clustered bootstrap: resample the **1,491 game clusters** with replacement"*;
`:156-158` — K0, incumbent and every challenger evaluated on **byte-identical row sets**.

This is a complete target contract, and every structural element of it is a statement about a
**closed** universe: a held-out season, a fixed 1,491-cluster bootstrap population, byte-identical
rows shared across arms. A prospective sample has none of those properties — its n grows, its rows
do not exist yet, and it cannot be shared byte-identically with a control fitted on history. The
program therefore demonstrably knows how to write an estimand and has written exactly one, for the
retrospective setting. The prospective analogue has not been written.

**(b) Two registered prospective contracts exist, and both are team-thread, market-facing and
ROI-primary.** Read in `experiments/registry.jsonl` (the shared evalharness registry, cited by name
at `PLAYER_MODEL_CAPABILITY_MATRIX.md:304`; see §8 note on read scope):

| line | `experiment_id` | `primary_metric` | `incumbent_id` | `decision_time` |
|---|---|---|---|---|
| 31 | `prospective_v0` | `prospective_roi_t24_thr05` | `market_at_cutoff` | `T-24h` |
| 38 | `prospective_pockets_v1` | `live_pocket_roi` | `market_at_cutoff` | `T-24h` |

`prospective_v0` carries its readiness sample verbatim
(`registry.jsonl:31`, `extra.verdict_readiness_sample_defined`):

> ">= 300 logged T-24h-labeled game-forecasts", ">= 150 bets in the primary (0.5-threshold) cell",
> "90 percent CI width on primary-cell ROI <= 12 percentage points", "cover-probability reliability
> weighted |gap| <= 0.05 on logged forecasts", "NO verdict of any kind is read before ALL bars are
> met; interim numbers are never quoted outside the log"

and its thresholds `{min_improvement: 0.02, harm_ci_bound: 0.0}` interpreted as *"primary-cell ROI
after vig must be >= +0.02"* with a date-clustered 90% CI excluding negative. `PROJECT_UPDATE_2026-08-04.md:100-102`
restates the same four bars and records them **"not approached"**.

**These are not this node's estimand, for four reasons each of which is sufficient:**

1. **Wrong thread.** `PROJECT_UPDATE_2026-08-04.md:621`: *"**Affected contracts:** team —
   `prospective_team_pair_v1`, `prospective_v0`. Player — none directly"*.
2. **Wrong statistic.** ROI on paper bets against a market incumbent is not the player program's
   settled primary target, and the player program's own no-go list forbids reaching for it:
   `PROJECT_UPDATE:323` — *"**No ROI optimisation.** Proper scores and calibration precede any
   market threshold."* The registered prospective metric is ROI; the player program's boundary says
   ROI comes last. Both are live; the tension is recorded in §9 (X-F15-2), not resolved here.
3. **Wrong incumbent.** `incumbent_id = market_at_cutoff` for both. The player program's frozen
   incumbent is `D_ewma_shrunk`, and a market is not a K0 (see §2).
4. **Wrong grain.** Both grade team-game bets. Nothing in either contract names a player-grain
   quantity.

**(c) The player program's own prospective-logging row records a mechanism with no evidence.**
`PLAYER_MODEL_CAPABILITY_MATRIX.md:298-308`, the `prospective logging` capability —
status `prototype`, **thin**; artifact `forecasts/forecast_log.jsonl` — **8 entries**; validation
*"mechanism exists; the log is nearly empty"*; **must not reuse**: *"8 entries as prospective
evidence of anything"*; next dependency *"accumulate real prospective rows; this is a time
dependency, not an engineering one"*. Restated as major blocker 5, `:328`: *"**Prospective log is
empty** (8 rows). No prospective evidence is available for anything."*

### 1.3 The consequence, stated in G04's terms

G04's finding was that 13 documented tracks have elaborate machinery and no estimand. F15 is a
sharper case of the same disease: the *machinery here is real and running* — a hash-chained forecast
log that verifies (§3.1), a scheduler, a coverage auditor, four registered decision-time labels, two
registered verdict-bar sets — and the thing it would grade, for this program, has never been named.
A prospective validation with a chain receipt and no estimand is a well-specified procedure with
nothing to grade it against. **The correct disposition is `NEEDS_TARGET_CONTRACT`, referred to a
human authorisation step. This draft neither proposes nor implies a candidate statistic.**

### 1.4 What a future F15 target contract must state (form only — no content supplied)

Stated as *requirements on the author*, not as a target. Each is forced by an existing contract, and
none of them can be met by copying the retrospective estimand in §1.2(a):

1. the target statistic, its unit, its denominator, and the population it is a statistic *of*;
2. the **decision-time label** it is defined at — the operational vocabulary is `T-24h`, `T-8h`,
   `T-90m`, `T-30m` (`ops_lane/O11_.../gate_logic.py:53`), and a prospective statistic that does not
   name one is not defined;
3. a **stopping rule and a sample bar fixed before any record is graded**, because a prospective n
   grows and a retrospective bootstrap population does not exist. Both registered prospective
   contracts do supply one (§1.2b), which is the single feature of them worth carrying forward as
   *form*;
4. how it is adjudicated against a control, given §2 — the binding structural problem;
5. how the selection bias in the served subset is handled: `PROJECT_UPDATE:596-598` — *"D-b / D-c /
   D-f mean served obligations are not a random subset, which must be accounted for whenever the
   period is graded."*

---

## 2. The matched-K0 requirement for this target

Because there is no target, this section states the requirement that **would** bind any future F15
arm, and the structural obstacle a future contract must clear first. Nothing here is new policy; it
is read off the existing contract.

**The governing terms** (`stage2b/P26_ARM_SPECIFIC_K0_CONTRACT/`):

1. **`K0_MATCHED` is a map keyed by `arm_id`, not a shared object.** Every arm carries exactly one
   record; two arms may not share one; an arm with no record has no authoritative control and
   cannot be adjudicated (`P26.../REPORT.md` §1.1).
2. **`K0_FLAT` is diagnostic only.** Beating it has no promotion value; every record must carry
   `k0_flat_role: "diagnostic_only"`, pinned by a schema `const` (P26 §1.1).
3. **The invariant set** holds byte-identical rows (as a digest), target, folds, weights, offset,
   fallback machinery, nuisance terms and lower-order structural terms, enforced as equality on all
   seventeen `comparison_gate.DIMENSIONS` (P26 §1.2). Verified in the schema bytes:
   `stage2b/P26_ARM_SPECIFIC_K0_CONTRACT/K0_MATCHED_SCHEMA.json:105` lists
   `required: ["rows","target","folds","weights","offset","fallback_machinery","nuisance_terms","lower_order_structural_terms"]`
   and `:106` describes them as *"Held IDENTICAL between the arm and its matched null. Row-set and
   fold identity are digests, not prose."*
4. **Exclusion minimality:** the null excludes *exactly* the declared treatment terms — no more
   (straw control), no less (feature absorption) (P26 §1.3).
5. **Structural terms are declared in `k0_spec.structural_terms`, never in `substantive_features`**;
   the frozen `comparison_gate.k0_findings` blocks any K0 with `n_substantive_features > 0`
   (P26 §1.4). Enforcement belongs at the call site; the frozen gate is not to be edited.

**Obstacle 1 — the target is pinned by a `const`.**
`K0_MATCHED_SCHEMA.json:109`:

```json
"target": {"type": "string", "const": "REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS"}
```

A `K0_MATCHED` record cannot name any other target. So a prospective statistic on cover
probability, ROI, margin, a proper score or any player-grain quantity has **no representable matched
control today**. Any future F15 work is admissible under the present control structure in exactly
one shape: as a **treatment term inside an arm whose target remains
`REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS`**, with the matched null differing only by that
term — and then the "prospective" part is a *sample*, not a target.

**Obstacle 2 — a prospective sample cannot satisfy the `rows` invariant against a historical
control.** The invariant is a row digest that must be byte-identical on both sides
(`K0_MATCHED_SCHEMA.json:108`, *"row_digest() string; byte-identical on both sides"*). Rows that do
not exist yet cannot be digest-matched. A prospective comparison is therefore either (i) a *new*
`K0_MATCHED[arm_id]` record over the prospective row set, refit on the same forward rows under the
same exclusion-minimality rule, or (ii) not a matched comparison at all. The registered prospective
contracts take neither option: both use `incumbent_id = market_at_cutoff`, i.e. an external rival
forecast. **A market benchmark is not a K0 and may never be used as one** — it shares none of the
seventeen dimensions with a challenger, so beating it is not evidence about an arm.

**Obstacle 3 — the frozen downstream mismatch travels forward.** The operational scorer pairs
regulation-equivalent projected exposure with raw full-game turnovers; the mismatch is documented
and the scorer is frozen. Possession candidates are selected on the primary possession target
first; downstream turnover results are secondary and may never rescue a candidate that fails or
worsens the primary target. A prospective design does not relax this ordering.

I state these as facts about the current contract. **Creating a second adjudicable target, or a
second control structure to make a prospective statistic gradeable, would change the primary target
and the K0 structure — a listed stop condition. HALT: raised in §6, not resolved here.**

---

## 3. Cutoff-valid evidence — inventoried, never assumed

Two standing cautions govern every row below.

* **Availability is not eligibility; eligibility is not admission.**
* `stage2a/EVIDENCE_PACKET_V2.json`, `cutoff_valid_availability_table_CORRECTED.warning`: the table
  *"records AVAILABILITY and COVERAGE. It does NOT prove cutoff validity — a construction receipt
  binds that declaration but cannot verify it"*. The corresponding gap
  `cutoff_validity_asserted` is in `PROGRAM_STATE.json` `open_methodological_gaps`, severity B,
  `implemented: false`. Every `cutoff_valid: true` anywhere in this program is a **declaration**.

A prospective design changes the *shape* of this problem but does not remove it: forward capture can
in principle **prove** cutoff validity by recording an observation timestamp before the cutoff,
which is exactly what a historical reconstruction cannot do. The inventory below is therefore the
inventory of what has actually been captured forward, and it is very small.

### 3.1 The prospective stream itself — measured on the bytes

`forecasts/forecast_log.jsonl` (19,808 bytes), measured by me:

| property | measured value |
|---|---|
| records | **8**, all `schema = "evalharness/forecast_log/1"` |
| hash chain | `verify_chain()` → `ok=True`, `n_records=8`, `n_verified=8`, `first_bad_index=None`, tip `6747f986a9e06fe112eaa867444a3b2e38e42cdc80a1a0342cc39c5737ca47db` |
| span | cutoffs `2026-07-31T14:28:20Z` .. `2026-08-01T14:20:03Z` |
| decision-time labels | `T-8h` 3, `T-90m` 3, `T-30m` 2 — **`T-24h`: 0** |
| producing model | `structural_channels_v2_daily_v0` on all 8 (`core_only_prediction.model`) |
| `core_plus_w1_prediction` | `null` on **all 8** |
| provisional game ids | `game_id_provisional = True` on **3** of 8 (`PROV-2026-07-31-*`) |
| outcome-joinable today | **3** of 8 — games `1022600213/214/215` have both team-rows in `data/masters/master_team.parquet`; `1022600216/217` have **0** rows (master `game_date` ends 2026-07-31); the 3 `PROV-` records carry no official id at all |
| `intended_bet_decision` | `not_applicable` on all 8; `paper_stake = 0.0` on all 8; `predicted_close = null` on all 8 |
| player-grain content | **none.** Byte scan of the whole log: `poss` 0, `pace` 0, `regulation` 0, `player_id` 0, `minutes` 0, `turnover` 0, `crps`/`pinball`/`q05` 0. Controls in the same scan: `margin` 24, `market` 40, `channels` 24, `paint` 16 |
| the one player-shaped block | `core_only_prediction.player_layer_informational`, carrying `n_roster`, `n_out`, `n_cold_start`, `sum_min_ewma_available`, `vacated_min_ewma` and an explicit `note`: **`"v0: does NOT modify the team forecast"`** |

**Read this table as one sentence.** The only prospective evidence the repository has ever produced
is eight team-margin forecasts from a frozen *team* model, three of which cannot be joined to an
outcome at all, none of which is at the label the registered prospective contract grades, none of
which contains a possession quantity, and whose player content is a self-declared non-input.

**What I deliberately did not do.** I did not join any prediction to any final score and computed no
error, hit rate, ROI, calibration or CLV of any kind. That is not caution alone: `prospective_v0`'s
own registered terms say *"NO verdict of any kind is read before ALL bars are met; interim numbers
are never quoted outside the log"*, and `PROJECT_UPDATE:316-318` forbids relaxing the registered
prospective gate. Anyone inventorying this stream inherits that rule.

### 3.2 The prospective capture infrastructure — measured coverage of the obligation stream

| item | value | source |
|---|---|---|
| obligations total / due / served | 84 / 47 / **15** | `ops_lane/O10_.../evidence/coverage_receipt_snapshot.json` |
| `coverage_served` | **0.3191** against `min_coverage_served` 0.95 | same |
| `operational_misses` | **26** against `max_operational_misses` 0 | same |
| `promotion_grade` | **false** | same |
| corrected receipt (Appendix E) | 47 due, 15 served, 27 operational misses, coverage **31.9%**, *"`promotion_grade = false`"* | `PROJECT_UPDATE:550-567` |
| T-24h obligations discoverable before their own cutoff | **0 of 21**, median id lead **−971.2 min** | `ops_lane/O11_.../REPORT.md:118-124` |
| the sentence that matters | *"Not one T-24h obligation in the entire captured period was discoverable before its cutoff."* | `O11 REPORT.md:124` |

`O11` also records that T-8h sits on the boundary (8 of 21 discoverable, median lead −11.2 min).
The registered primary cell of `prospective_v0` is a **T-24h** cell. The stream currently cannot
produce a single admissible record in it, and this is a discovery-logic defect (D-b), not a volume
problem.

### 3.3 Live-information capture — implemented, bound to nothing

`data_lane/D11_LIVE_INFORMATION_CAPTURE/SOURCE_BINDING.json`, `headline`, verbatim:

> ZERO of the eight domains is bound to a live source by this node. The capture mechanism is
> implemented and tested; it has captured no real observation.

`n_bound = 0`, `n_domains = 8`. Per domain, with the packet verdict and the flag that matters most
to a *prospective* design — `wishlist_evidence.prospective_only_validation`:

| domain | bound | packet verdict | prospective-only |
|---|---|---|---|
| injury_designation | false | UNAVAILABLE HISTORICALLY (2026-07-30 .. 2026-08-04, 6 days) | **true** |
| lineup | false | UNAVAILABLE | **true** |
| odds | false | UNAVAILABLE HISTORICALLY (2026-07-31 .. 2026-08-06) | **true** |
| starter | false | UNAVAILABLE | (not flagged) |
| minute_restriction | false | (no packet verdict) | (not flagged) |
| news | false | (no packet verdict) | (not flagged) |
| transaction | false | AVAILABILITY ESTABLISHED; CUTOFF VALIDITY NOT ESTABLISHED | (not flagged) |
| coaching_change | false | ABSENT | false — the only one reconstructable historically |

D11's own epistemic status: *"PROSPECTIVE CAPTURE INFRASTRUCTURE. Builds the record that would make
future features cutoff-provable. Creates no historical evidence and repairs no historical gap."*
That is the correct description of the entire prospective apparatus as it stands.

### 3.4 The target side — realised outcomes for the primary target stop where the log starts

Measured on the frozen artifacts:

| artifact | rows | games | `game_date` max |
|---|---|---|---|
| `possessions_v1/possessions_raw_v1.parquet` | 238,563 | 1,495 | **2026-07-31** |
| `projected_exposure_v1/projected_player_possessions_v1.parquet` | 120,262 | 1,495 | 2026-07-31 |
| `projected_exposure_v1/team_possession_prior_v1.parquet` | 2,990 | 1,495 | 2026-07-31 |
| `data/masters/master_team.parquet` | 2,990 | — | 2026-07-31 |

Every artifact that could supply a **realised** `REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS`
value ends on 2026-07-31 — the same day the prospective log begins. There is currently **no forward
production path that emits the primary target for a newly played game**, and no prospective record
that contains a possession projection to compare it to (§3.1). The two halves of a prospective
validation of the primary target do not overlap by a single game.

### 3.5 Declared-cutoff-valid fields available to a future prospective arm

Inventoried, not assumed, and all inherit the `cutoff_validity_asserted` gap:

* `stage2a/EVIDENCE_PACKET_V2.json` carries **9** entries with a `cutoff_valid` key — 7 `true`,
  2 `"ONLY LAGGED"` (schedule identity, dates/season, `is_home`, rest/density, own and opponent
  realised `game_pace` over strictly earlier games, venue/travel/elevation; and, ONLY LAGGED, the
  team prior-game box aggregates and possession-level `end_reason`/`duration_sec`/`period`).
  Re-measured by F12 in this same wave; I did not re-derive it and cite it as documentary.
* D10's whole-ledger verdicts across 52 fields: `CUTOFF_VALID` 5, `CUTOFF_UNPROVEN` 37, `ABSENT` 7,
  `CUTOFF_INVALID` 3 — carrying the caveat that `GRAPH_STATE.json` records
  `D10_FIELD_AVAILABILITY_LEDGER` as **FAILED** for a manufactured negative in the coaching family;
  the other fields are not impeached but the ledger is provisional.
* Genuinely prospective, per-row observation-timestamped: `injury.status` / `injury.reason` /
  `injury.report_date`, 551 rows, **2026-07-30 .. 2026-08-01 only**, `capture_utc` per row —
  D11 records this as *"the only source in the repository that can create a verified obligation for
  a player with no prior box row"*.

**Nothing in this section has been reviewed for admission.** Availability is not eligibility;
eligibility is not admission.

---

## 4. Known data blockers

* **B1 — No estimand.** The binding blocker (§1). Everything below is downstream of it.
* **B2 — The prospective stream is not gradeable, by the program's own ruling.**
  `PROJECT_UPDATE:301` (D-1): fixing the start record *"**does not** make the stream gradeable"*;
  `:594-598` keeps three things separate — validity of the first record (established), whether the
  stream is promotion-grade (**no**), whether coverage passes the registered gate (**no**) — and
  states *"Start validity does not imply a gradeable confirmation sample"*. Restated as a no-go at
  `:324-325`.
* **B3 — The served subset is not random.** `PROJECT_UPDATE:596-598`: D-b / D-c / D-f *"mean served
  obligations are not a random subset, which must be accounted for whenever the period is graded."*
  Any prospective estimand must carry a selection-bias treatment; none is documented.
* **B4 — The T-24h cell is structurally unreachable until D-b is repaired.** 0 of 21 T-24h
  obligations discoverable before cutoff, median lead −971.2 min (§3.2). The repair set is **four**
  faults, not one (`PROJECT_UPDATE:569-572`), and D-4 is ruled *"Prepare, do not implement"*
  (`:304`).
* **B5 — The log is empty and must not be reused as evidence.** 8 rows;
  `CAPABILITY_MATRIX:307` **must not reuse** *"8 entries as prospective evidence of anything"*;
  `:308` the next dependency is **time**, not engineering.
* **B6 — Nothing player-grain is logged.** Measured (§3.1): zero possession, minutes, player-id or
  distributional fields; the player block is flagged `"v0: does NOT modify the team forecast"`. A
  prospective validation of the *player* program has no stream to validate on.
* **B7 — No forward production of the primary target** (§3.4). Realised-possession artifacts end
  2026-07-31 with a fixed 1,495-game universe.
* **B8 — Zero live domains bound** (§3.3): 0 of 8; the capture mechanism has captured no real
  observation.
* **B9 — Execution-side fields are not captured, and historical reconstruction is blocked.**
  `PROJECT_UPDATE:280-282`: nine fields to be captured *going forward*; *"Historical reconstruction
  is blocked by DL-002 (27% T-24h coverage)."*
* **B10 — Cutoff validity is asserted, never verified** — `PROGRAM_STATE` gap
  `cutoff_validity_asserted`, severity B, `implemented: false`.
* **B11 — Feature-producer provenance is incomplete** —
  `PROGRAM_STATE.provenance_status.general_feature_producer_provenance = "incomplete"`; G04 raised
  it as `Q10` and recorded the Severity-A stop condition as **triggered**. Any future prospective
  feature producer inherits it.
* **B12 — Program-level authorisation is absent.** `experiment_currently_authorized = false`;
  `stop_boundary.in_force = true`.

---

## 5. This draft does not authorise fitting

Repeated because it is the operative sentence of the document. **This draft does NOT authorise
fitting.** Fitting requires five things; this document supplies a *draft* of two of them and one of
those comes back `NOT_DERIVABLE`:

1. a **target contract** — absent; the estimand is `NOT_DERIVABLE_FROM_DOCUMENTATION` (§1);
2. a **matched K0** — the requirement is stated (§2); no `K0_MATCHED[arm_id]` exists for any
   prospective arm, and §2 records that a prospective statistic has no representable matched
   control under the `const`-pinned schema;
3. **cutoff-valid evidence** — inventoried (§3), and the prospective side of it is eight
   team-margin records, three joinable, zero at the registered label;
4. a **preregistration** — none drafted here;
5. an **independent gate review** — not this node's; no verifier has reviewed this draft.

None of the five is in this node's gift. Nothing here may be cited as evidence that any prospective
statistic has been agreed, that the logged stream may be graded, that any registered bar may be
read, or that any player-grain forecast may be logged into the chain. No git command was run; no
frozen artifact was modified; writes are confined to
`experiments/player_program/future_research/F15_PROSPECTIVE_VALIDATION/`.

---

## 6. Stop conditions

| stop condition | status | note |
|---|---|---|
| a finding would change the primary target, the K0 structure, the inference structure, the candidate universe, the cutoff-valid feature set or the leakage status | **RAISED, not resolved** | §2: `K0_MATCHED_SCHEMA.json:109` pins the target with a `const` and `:108` requires a byte-identical row digest. A prospectively-sampled statistic can satisfy neither against a historical control. Making prospective validation adjudicable would change the K0 structure and, if the graded statistic is not the primary target, the primary target as well. Referred upward. Nothing was changed. |
| (inherited, G04) Severity A gap blocking fitted work | **already triggered upstream** | `general_feature_producer_provenance`, `implemented: false` (Q10). Restated because a forward-capture producer inherits it. |
| (inherited, F14 / P29) market-odds candidate-universe adjudication | **open, not this node's** | `P2B_MARKET_ODDS_ELIGIBILITY` owns it. Both registered prospective contracts have `incumbent_id = market_at_cutoff`, so this adjudication is upstream of any prospective design that keeps a market incumbent. This node constructed, proposed and admitted no odds-derived feature. |

---

## 7. What I could not establish

* **Any estimand for this node.** Not established, and deliberately not invented (§1).
* **Whether "prospective validation design" was ever intended as a player-program item at all, or is
  the team thread's `prospective_v0` seen from the player side.** `seed_graph.py:933` supplies the
  title with no citation; G04 maps no item to it; `PROJECT_UPDATE:621` says the prospective
  contracts affect *"Player — none directly"*. I could not resolve this and did not guess.
* **Whether any forward production path could emit the realised primary target for a new game.** The
  frozen artifacts stop at 2026-07-31 (§3.4); whether the reconstruction pipeline can be run forward
  is an engineering question outside this node's read scope and write scope. Unmeasured in either
  direction.
* **Any accuracy, calibration, ROI or CLV figure on the 8 logged records.** Not computed, by
  contract (§3.1). The three outcome-joinable records were identified by id join only.
* **Whether the 15 served obligations are salvageable as a graded sample after the selection-bias
  treatment B3 demands.** That is a question for whoever writes the estimand.
* **The content of `project_docs/FREEZE_PROPOSAL_v0.md`**, which `PROJECT_UPDATE:578-580` treats as
  the defining protocol for `prospective_v0`. Outside the read scope; not opened. The registry
  record (§1.2b) was read instead and is described as registering that protocol *"verbatim in
  substance"*.

---

## 8. Measurements — commands and results

Run read-only on this branch. Read scope for this node is `experiments/player_program/`
(`PROGRAM_GRAPH.json`). **Two files outside that scope were opened, read-only, and are declared
here rather than silently used:** `forecasts/forecast_log.jsonl` and `experiments/registry.jsonl`.
Both are named as the defining artifacts of the prospective capability by an in-scope document
(`PLAYER_MODEL_CAPABILITY_MATRIX.md:303-304`). Declaring "no prospective estimand is documented"
without opening the registration that document points at would have manufactured a negative — the
failure mode this program has already produced once. `data/masters/master_team.parquet` and the
`possessions_v1` / `projected_exposure_v1` parquets were read for row counts and date maxima only.
`stage2b/SEALED_RESULTS/` was **not** opened.

**M1 — F15 in G04's extraction.** See §1.1. `[('F15', 0)]` with sibling controls firing.

**M2 — byte sweep for estimand vocabulary.** `os.walk` over `experiments/player_program`
(608 files, `SEALED_RESULTS` skipped), `re.findall` on raw bytes, positive control
`REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS` = 147 hits / 124 files. `estimand` = 156 hits /
26 files, of which 25 are this graph's own orchestration and F-node files; the sole pre-existing
document is `stage2a/PHASE0A_RESOLUTION.md`.

**M3 — the prospective log.** `json.loads` per line + `evalharness.forecast_log.verify_chain`:

```
ChainReport(ok=True, n_records=8, n_verified=8, first_bad_index=None,
            tip_sha256='6747f986a9e06fe112eaa867444a3b2e38e42cdc80a1a0342cc39c5737ca47db')
labels Counter({'T-8h': 3, 'T-90m': 3, 'T-30m': 2})
models Counter({'structural_channels_v2_daily_v0': 8})
game_id_provisional Counter({False: 5, True: 3})
core_plus_w1_prediction non-null: 0
token counts in raw bytes -> poss 0, pace 0, regulation 0, player_id 0, minutes 0, turnover 0,
                             crps 0, pinball 0, q05 0 | controls: margin 24, market 40, channels 24
```

**M4 — outcome joinability.** `pd.read_parquet('data/masters/master_team.parquet')` → 2,990 rows,
`game_date` max 2026-07-31. Row counts by logged `game_id`: `1022600213` 2, `1022600214` 2,
`1022600215` 2, `1022600216` 0, `1022600217` 0. No prediction column was joined.

**M5 — target-side artifact spans.** `pd.read_parquet` on each artifact in §3.4; shapes, distinct
`game_id`, and `game_date` min/max as tabulated.

**M6 — registry.** `json.loads` per line of `experiments/registry.jsonl` (96 lines); the two
prospective records are lines 31 and 38 as tabulated in §1.2b.

**M7 — D11 binding.** `json.load` of `data_lane/D11_LIVE_INFORMATION_CAPTURE/SOURCE_BINDING.json`;
`n_bound = 0`, `n_domains = 8`; per-domain `bound`, `packet_evidence.verdict`,
`wishlist_evidence.prospective_only_validation` as tabulated in §3.3.

---

## 9. Contradictions found

**X-F15-1 — a graph node with no documentary parent (severity C).** `PROGRAM_GRAPH.json:4075-4125`
schedules F15 with the full acceptance criteria of a target-contract node; G04 — its sole declared
dependency — contains no item it corresponds to (0 occurrences of `F15`, against 2/1/2/1/1 for
F10/F11/F13/F14/F16, and 5 of 7 future nodes mapped in `already_modelled`). Either a documented item
exists that G04 missed, or the node was seeded from a title alone. On the bytes I can read, it is
the second. Recorded, not resolved. (F12's draft records the identical defect for itself; the two
unmapped nodes are exactly F12 and F15.)

**X-F15-2 — the only registered prospective estimands are ROI, and the player program's no-go list
puts ROI last (severity C).** `registry.jsonl:31` `primary_metric = "prospective_roi_t24_thr05"` and
`:38` `primary_metric = "live_pocket_roi"`, both `incumbent_id = "market_at_cutoff"`, versus
`PROJECT_UPDATE:323` *"**No ROI optimisation.** Proper scores and calibration precede any market
threshold."* These are not formally in conflict — the registrations are team-thread and predate the
boundary statement, and `:621` scopes them away from the player thread — but a future author
looking for "the program's prospective estimand" will find ROI first and the prohibition second.
Recorded so the registration is never mistaken for the player program's commitment.

**X-F15-3 — the prospective apparatus grades a quantity the program's primary target is not
(severity C, structural rather than byte-level).** The settled primary target is
`REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS`; the logged stream contains margin, total, cover
probability and market fields and **zero** possession fields (§3.1, measured). The registered
verdict bars are ROI and cover-probability reliability. So the machinery that exists cannot, as
built, validate the target that is settled — and the target that is settled has no forward
production path (§3.4). Recorded; repairing it would change the K0 structure and is referred upward
under §6.

*(G04 recorded contradictions X1–X4 and F14 recorded X-F14-1..3; none is re-litigated here.)*

---

## 10. Recommended disposition

`NEEDS_TARGET_CONTRACT` — human authorisation step. If the program wants a prospective validation of
the player model, the estimand must be written by whoever owns the objective, and it must clear five
things this node has measured as open: the `const`-pinned K0 target and the byte-identical row
digest (§2), the absence of any player-grain prospective record (§3.1, B6), the absence of a forward
production path for the primary target (§3.4, B7), the non-random served subset (B3), and the
structurally unreachable T-24h cell (B4). Until then, F15 has running machinery, a verified hash
chain, two registered bar sets belonging to another thread, and no estimand — which is exactly the
condition G04 named.
