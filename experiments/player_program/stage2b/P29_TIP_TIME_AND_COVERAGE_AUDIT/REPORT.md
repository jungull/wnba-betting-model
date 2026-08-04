# P29 — Tip-time null mask, fold identity, and the eligibility of tip-derived features

**Epistemic status (verbatim from the node contract):**

> VERIFIED_READ_ONLY_DERIVATION. Determines whether a null mask is separable from fold identity. A coverage finding is not a licence to admit a feature.

Every number below was produced by
`experiments/player_program/stage2b/P29_TIP_TIME_AND_COVERAGE_AUDIT/run_measurements.py`, run
against the frozen artifacts, and is written machine-readably to `MEASUREMENTS.json` in the same
directory. One command reproduces all of it:

```
python experiments/player_program/stage2b/P29_TIP_TIME_AND_COVERAGE_AUDIT/run_measurements.py
```

Section references below are to the `M*` blocks of `MEASUREMENTS.json`.

Input hashes (`inputs`) — the two frozen artifacts match `EVIDENCE_PACKET_V2.sources` exactly:

| artifact | sha256 | packet agreement |
|---|---|---|
| `projected_exposure_v1/team_possession_prior_v1.parquet` | `c37c0751…3db18` | AGREES |
| `possessions_v2/possessions_raw_v2.parquet` | `7200881f…4b1a` | AGREES |
| `data/reference/tip_times.csv` | `3bd2c4ab4d7f673f9010a40ac4ac904c88dbb039db4627b0e918d07810c4542a`, 160,391 bytes | **not bound by any packet** |

---

## 1. Ruling

**Every feature derived from `data/reference/tip_times.csv` — `tip_utc`, `tip_local`,
`tip_hour_local`, `tip_dow_local`, and any transform, indicator or interaction of them — is
INELIGIBLE for this wave.**

The node's acceptance criteria authorise exactly this ruling on exactly this condition: *"if the
null mask is not separable from fold identity, tip-derived features are ruled INELIGIBLE for this
wave and the reason is recorded."* The condition holds. Six reasons are recorded in
`FINDINGS.json` under `RULING.reasons`; the load-bearing ones are section 3 and section 4 below.

The ruling does **not** say a tip effect is absent. No fit was run, and none may be — no
performance peeking. It does not condemn the underlying odds feed either: the cutoff unprovenness
is a property of the *derivation*, not of the feed.

---

## 2. The reported pattern is CORRECTED, and its conclusion survives

`stage2a/V2_STOP_CONDITION.json` records, under `not_stop_conditions_but_recorded`:

> `tip_times_null_mask_is_almost_exactly_fold_1`: "1,219 of 1,495 games and NONE of 2021, so any
> tip-derived feature's null mask nearly equals the first fold"

Measured (`M3_null_mask`), joining `tip_times.csv` onto the 1,495-game universe on `game_id`:

| season | games | **null** | covered | null rate |
|---|---|---|---|---|
| 2021 | 209 | **209** | 0 | 1.000000 |
| 2022 | 239 | **59** | 180 | 0.246862 |
| 2023 | 260 | **1** | 259 | 0.003846 |
| 2024 | 262 | **1** | 261 | 0.003817 |
| 2025 | 310 | **0** | 310 | 0.000000 |
| 2026 | 215 | **6** | 209 | 0.027907 |
| **total** | **1,495** | **276** | **1,219** | 0.184615 |

**CORRECTED, on both figures.**

* 1,219 is the **covered** count, not the null count. The null count is **276**.
  1,219 happens also to be the exact row count of `tip_times.csv` (1,219 rows, 1,219 distinct
  `game_id`, 0 duplicates, 0 rows outside the universe — `M2_tip_times_file`), which is how the
  transcription error arises.
* "NONE of 2021" is backwards. 2021 is **209 of 209 null — 100%**.
* The claim is additionally **internally incoherent**: a 1,219-game mask containing no 2021 game
  cannot be "almost exactly fold 1", which is 209 games. The stated numbers contradict the
  sentence they are attached to.

**The qualitative conclusion is nonetheless right**, and I AGREE with it: 209 of the 276 nulls
(75.72%) are 2021, and 2021 is entirely null.

Two independent in-scope sources agree with my figures and disagree with the stop-condition packet:

* `stage2a/CORRECTION_ADDENDUM.json` C7 states `{"rows": 1219, "of": 1495, "verdict": "PARTIAL —
  2021 coverage is zero …"}` — i.e. 1,219 as *coverage*, 2021 as *zero coverage*. Correct. The V2
  stop-condition packet inverted it.
* `data_lane/D10_FIELD_AVAILABILITY_LEDGER/FINDINGS.json` reports 2,438 of 2,982 team-game rows
  covered and 1,219 of 1,491 clusters covered, with per-season row coverage 0 / 360 / 518 / 522 /
  620 / 418. My team-row measurement is 2,982 rows, 544 null, 2,438 covered — identical
  (`M5_team_row_frame`).

Universe reproduction (`M1_universe`) also AGREES with the packet: 2,990 team-game rows over 1,495
games; 2,982 resolved rows over 1,491 clusters. All four games dropped from the resolved frame are
2021 games and all four are null, which is why the null count falls 276 -> 272 on the cluster frame
while the covered count stays 1,219.

---

## 3. The null mask's correlation with fold identity — measured explicitly

Fold construction is taken from the artifacts, not assumed. Two definitions are in play and both
are reported, because they give different-strength answers and the second is the operative one.

**(a) Season labels, six folds** (`EVIDENCE_PACKET_V2.inference_specification.fold_construction`:
"chronological, nested by season"). Fold 1 = 2021. Measured on the 1,495-game frame
(`M4_fold_identity`):

| measure | value |
|---|---|
| phi(null mask, fold-1 indicator) | **0.847227** |
| Cramer's V(null mask, fold) | **0.876231** (chi2 = 1147.832271, n = 1495, dof = 5) |
| eta^2 — share of the null mask's variance explained by fold alone | **0.767781** |
| share of nulls falling in fold 1 | 0.757246 |
| share of fold 1 that is null | **1.000000** |
| off-diagonal against an exact fold-1 mask | 67 games (4.4816%), all in the "null but not 2021" direction; 0 in the other |
| mask is *exactly* fold 1 | **false** |

Per-fold variance of the mask itself: 2021 sd = 0.0 (constant 1), 2025 sd = 0.0 (constant 0),
2022 sd = 0.431186, 2023 sd = 0.061898, 2024 sd = 0.061662, 2026 sd = 0.164706.

**(b) The operational folds actually fitted** —
`possession_features.py::chronological_folds` is an **expanding window with five folds** (test
seasons 2022 to 2026), because 2021 has no strictly earlier season. **2021 is never a test fold.**
It is 410 of the 410 training rows of `train_lt_2022` and sits inside the training set of every
later fold. Measured (`M9_operational_expanding_window_folds`):

| fold | cutoff | train rows | train rows **with** a tip time | train missing rate |
|---|---|---|---|---|
| `train_lt_2022` | 2022-05-06 | 410 | **0** | **1.000000** |
| `train_lt_2023` | 2023-05-19 | 888 | 360 | 0.594595 |
| `train_lt_2024` | 2024-05-14 | 1,408 | 878 | 0.376420 |
| `train_lt_2025` | 2025-05-16 | 1,932 | 1,400 | 0.275362 |
| `train_lt_2026` | 2026-05-08 | 2,552 | 2,020 | 0.208464 |

**Separability verdict: NOT SEPARABLE in the sense that governs admission.**

I state the qualification honestly rather than overclaiming: the mask is *not* literally identical
to fold identity. 67 games are null outside 2021, and eta^2 leaves 23.2% of the mask's variance
unexplained by fold. There is residual contrast. But 59 of those 67 games sit in 2022 — itself the
earliest test fold — and on the one fold that decides admission, `train_lt_2022`, the mask has
**zero variance across 410 of 410 training rows**. Inside that fold there is no contrast at all
that could distinguish a tip effect from a 2021 level effect. That is what "not separable" has to
mean operationally.

### What the mask actually encodes: calendar time, not basketball (`M4b`)

| measure | value |
|---|---|
| phi(null, `game_date` < 2022-05-21) | **0.923591** |
| games before 2022-05-21 | 242 — of which **242 are null** |
| nulls on or after 2022-05-21 | 34 |

Those 34 decompose as: 2022 Playoffs 23, 2022 Regular Season 3, 2023 RS 1, 2024 RS 1, 2026 RS 6.
Playoff coverage is 2021: 17/17 null, 2022: 23/23 null, 2023-2025: 0 of 66 null. 2022-05-21 is
the earliest snapshot timestamp in the parent odds archive.

The mask is therefore "the game predates the odds archive, or is in the 2022 playoffs, or
postdates the last capture". It is a record of when someone archived odds. It is not a property of
any game.

---

## 4. Coverage in later seasons is NOT a licence to admit the feature

2023, 2024 and 2025 are 99.6%, 99.6% and 100.0% covered. That is availability. It is not
eligibility, and it does not repair `train_lt_2022`.

`GATE_INVOCATION_CONTRACT` section 4 is unambiguous: *"A feature that is healthy pooled but
degenerate in a fold must FAIL for that fold, or be governed by a fallback frozen and registered
before any result is visible. There is no third option."* It further forbids admitting a fold
because it is "early", "small", or "a warm-up". No preregistered fallback governing tip coverage
exists. The fold fails, and with it the feature, for this wave.

### The frozen gate does not catch this — measured, not assumed

I invoked `feature_gate.audit` unmodified (`M6_frozen_gate_behaviour`), with `offset`, `target` and
`test_df` supplied as section 3.1 requires:

* **Pooled**: `passed: true`. One finding, `missingness_present` (544 missing, rate 0.182428),
  which is **not** in `BLOCKING`. `corr(null mask, target) = -0.017358` against the
  `missingness_corr_threshold` of 0.5 — two orders of magnitude below it. So
  `missingness_informative` cannot fire, and with no `outcome_mask` making the mask an exact
  outcome indicator, neither can `missingness_encodes_outcome`. This confirms the V2 packet's
  parenthetical, "neither gate branch blocks (0.5 correlation threshold, non-outcome mask)".

* **On the 100%-missing fold the result is worse than the packet claims.** For the 410 rows of
  season 2021 — `train_lt_2022`'s entire training set — the gate returns `passed: true` with an
  **empty findings list**. Not `missingness_present`. Nothing at all.

I measured the mechanism rather than inferring it (`M10`), on a synthetic 50-row all-NaN column:

* `np.nanstd` of an all-NaN column is `nan`, and `nan == 0.0` is `False`, so `zero_variance`
  cannot fire;
* `feature_gate.py` line 152 short-circuits — `if n_miss == 0 or n_miss == len(miss): continue` —
  so a fully-missing column is skipped by the missingness loop entirely;
* `design_rank_report` returns `checked: false` ("insufficient complete rows to assess rank"),
  and the caller appends nothing when `checked` is false.

Result: `{"passed": true, "findings": [], "blocking": []}`. **A column that is 100% missing over
the rows handed to the frozen gate produces zero findings.** This is not specific to tip times: any
feature whose coverage begins mid-history passes the shared gate silently on every early fold. See
section 6, SC2.

The obvious remedy — "add a missingness dummy" — is itself fold-degenerate: as a feature the
indicator blocks on `zero_variance` + `rank_deficient` in 2021 **and** 2025, and passes pooled.

### The call-site guard that does catch it

I ran P27's `fold_estimability_guard.guard` unmodified, with
`fold_policy="EXPANDING_PRIOR_SEASONS"` (`M11_P27_callsite_guard`):

| fold | verdict |
|---|---|
| `train_lt_2022` | **UNEVALUABLE_PROSPECTIVELY** — `single_level_factor` (`unique_levels: 0`), `no_cluster_support` |
| `train_lt_2023` through `train_lt_2026` | ESTIMABLE |

and `pooled_pass_would_be_misleading: true`. The call-site remedy exists and returns the right
verdict. The gap is that nothing makes routing through it mandatory.

### A second, independent reason: the null mask confounds the cold-start stratum

Of the 37 `league_prior_all` team-game rows — the incumbent's coldest fallback tier — **28 (75.7%)
fall on tip-null rows**; 9 do not (`M5_team_row_frame`, phi = 0.16669). Imputing the tip nulls
therefore injects a proxy for precisely the stratum V2 finding S6 measures as carrying 37-42% of
MSE as *bias*. Apparent feature value could be pure stratum re-centring, and `comparison_gate` has
no dimension for that. This is the S4/S6 shape reappearing through a null mask.

### And a third: coverage fails at the live edge

The six null 2026 games are `1022600210` through `1022600215`, dated 2026-07-30 (three) and
2026-07-31 (three) — the final two days of the universe (`M8`, dates confirmed against the prior
artifact). The null mask is open at **both** ends of calendar time. A tip feature would be missing
on exactly the most recent games a deployed model must score.

---

## 5. The `tip_times.csv` provenance question

The acceptance criteria ask me to address that `tip_times.csv` is odds-derived and covers
2022-2026, which sits oddly beside the packet's "market odds unavailable historically".

**The oddity is real. The packet's stated reason is false. The packet's practical verdict happens
to hold for this branch, for a different reason.**

**The builder is in scope and I read it.** `data/reference/collect_bios.py::phase_tips`
(`M7_provenance.builder`):

* reads `data/drive_masters/master_odds.csv` (tagged `source_table="drive_master"`) and
  `data/odds_capture/master_odds_extension.csv` (tagged `"extension"`);
* sorts by snapshot and takes `commence_utc=("commence_utc", "last")` per `(game_id,
  source_table)` — the **latest** snapshot's scheduled start — preferring `extension` where both
  cover a game;
* records `n_snapshots` and `n_commence_variants` but **does not write
  `odds_snapshot_timestamp`**.

That reconciles exactly with the output (`M2`): `2022|drive_master` 180, `2023|drive_master` 259,
`2024|drive_master` 261, `2025|drive_master` 113, `2025|extension` 197, `2026|extension` 209.
`n_commence_variants` is 1 for 1,183 games, 2 for 35, 3 for 1; `n_snapshots` runs 10 / 30 / 146
(min / median / max).

**Cutoff consequence.** For the 36 games whose commence time provably moved, the retained value is
the last one seen, and with the snapshot timestamp discarded it cannot be shown to predate the
forecast cutoff. `D10_FIELD_AVAILABILITY_LEDGER` already records `tip.tip_utc__tip_times_csv`,
`tip.tip_hour_local` and `tip.tip_dow_local` as **CUTOFF_UNPROVEN** with `cutoff_valid_rate: 0.0`
on all 2,438 covered rows. I reconfirmed the ledger's reasoning by reading `phase_tips` directly. I
did not upgrade the verdict and could not: see section 7.

**The in-scope provenance finding, which I think is the important one.** Neither
`data/drive_masters/` nor `data/odds_capture/` is tracked by git, and neither exists in this
worktree. `git ls-files data/odds_capture data/drive_masters` returns nothing; `git check-ignore`
returns nothing either, so they are simply untracked. `tip_times.csv` **is** tracked. So a tracked
derived artifact has an entirely unversioned upstream that is absent from the branch carrying the
frozen program artifacts. Its construction is not reproducible from this branch, and no packet
binds its hash. Severity B, reproducibility.

**Out-of-scope observation, disclosed rather than suppressed.** The provenance question cannot be
answered from inside this branch, so I read the odds tables read-only in the repository-root
working tree (branch `data-refresh-2026`), which is outside this node's declared read scope. It is
quarantined in `FINDINGS.json` under `OUT_OF_SCOPE_ROOT_WORKTREE_OBSERVATION` and should be
re-measured by whoever owns that branch before it is relied on:

* `data/drive_masters/master_odds.csv` — 20,004 rows, 813 distinct `game_id`, split
  2022: 180 / 2023: 259 / 2024: 261 / 2025: 113. **That is exactly the `drive_master` per-season
  count in `tip_times.csv`**, which closes the provenance chain. All 813 game_ids lie inside the
  contract universe. `odds_snapshot_timestamp` spans 2022-05-21T17:55:00Z to 2025-07-03T22:55:37Z.
  Markets present: `odds_spread` and `odds_price`. **No totals column.**
* `data/odds_capture/historical` — 292 JSON snapshots, `hist_2025-07-05_15Z.json` to
  `hist_2026-07-29_22Z.json`.
* `data/odds_capture` live snapshots — 69 files, `live_20260730T150132Z.json` to
  `live_20260804T200008Z.json`.

The packet's entry reads: *"market odds / totals — source `data/odds_capture/` — coverage
2026-07-31 .. 2026-08-06 only — UNAVAILABLE HISTORICALLY."* The 2026-07-31 start describes the
live-capture files only. It is not true of the directory as a whole, and it is not true of the
odds data in the operator's tree. That is a stop condition; see section 6.

---

## 6. Stop conditions — raised, not resolved

**SC1 — CUTOFF-VALID FEATURE SET / CANDIDATE UNIVERSE. Severity A.**
The market-odds family was excluded on the stated ground that capture begins 2026-07-31. A
game-joined historical odds archive with snapshots from 2022-05-21 demonstrably exists and is the
parent of a tracked repository artifact. Whether market features may enter the candidate universe —
and the separate objection the packet itself raises, that a market feature *changes what the model
is* — are not mine to decide. **HALTED and raised.** This node constructed, evaluated, proposed and
admitted no odds-derived feature.

**SC2 — LEAKAGE STATUS / enforcement of the cutoff-valid feature set. Severity A.**
`feature_gate.audit` returns `passed: true` with an empty findings list for a column that is 100%
missing over the rows it is handed — measured on the real 410-row fold and on a synthetic all-NaN
column. Any feature whose coverage begins mid-history therefore passes the shared gate silently on
every early fold. **HALTED and raised. `feature_gate.py` was not edited and must not be.** The
call-site remedy already exists — P27's guard returns `UNEVALUABLE_PROSPECTIVELY` and
`pooled_pass_would_be_misleading: true` on exactly this case. The open question is program-level:
whether routing through it is mandatory at every call site.

Neither stop condition is discharged here.

---

## 7. What I could NOT establish

1. **Whether the retained `commence_time` predates the forecast cutoff** for the 36 games with
   `n_commence_variants > 1`. `tip_times.csv` discards `odds_snapshot_timestamp` and the parent
   odds tables are absent from this branch. D10's CUTOFF_UNPROVEN verdict stands — reconfirmed,
   not upgraded.
2. **Whether the `data/odds_capture/` JSON snapshots carry a totals market.** Those files are not
   in this worktree and I did not open them in the root worktree. `master_odds.csv` carries spread
   and price only.
3. **Why the 2022 playoffs are 23-of-23 uncovered while 2023-2025 playoffs are 0-of-66**, and why
   six games on 2026-07-30/31 are uncovered. Both need the odds archive this branch does not have.
4. **Any statement about how much predictive value a tip feature would carry.** No fit was run and
   none is permitted — no performance peeking. Nothing under `stage2b/SEALED_RESULTS/` was read.
5. **Whether a preregistered active-set rule could lawfully govern the `train_lt_2022`
   degeneracy.** P27's preregistration machinery exists, but no rule covering tip coverage is
   registered, and registering one now — after this measurement is visible — would violate
   `GATE_INVOCATION_CONTRACT` section 4's `results_visible_at_registration == false` requirement.

---

## 8. Contradictions found

**X1 — `V2_STOP_CONDITION.json` vs `CORRECTION_ADDENDUM.json` vs the bytes.** The stop-condition
packet records the tip null mask as "1,219 of 1,495 games and NONE of 2021". The addendum records
the same 1,219/1,495 as *coverage*, with "2021 coverage is zero". The bytes say 276 null / 1,219
covered, and 2021 100% null. The stop-condition packet inverted the addendum's coverage figure into
a null figure and then negated the 2021 statement. The addendum and the bytes agree. Both packets
are frozen; reported, not edited.

**X2 — `EVIDENCE_PACKET_V2` availability table vs `tip_times.csv` and its builder.** Detailed in
section 5. Trips SC1. The nuance must travel with the correction: market-odds features genuinely
are unavailable *on this branch* — but for a reproducibility reason, not the capture-window reason
the packet gives.

**X3 — `experiments/bios_collection/tip_coverage_by_season.csv` vs the contract universe.** The
bios file reports 2026 as 209 of 209 covered, 0 without. Against the 1,495-game contract universe,
2026 has 215 games and 6 are null. The denominators differ — the bios file counts `master_team`
`is_home` rows, not the contract universe. Neither file is wrong, but the "100% covered" reading
does not transfer and must not be cited as if it did. For 2021-2025 the bios file agrees with my
measurement exactly (0 / 180 / 259 / 261 / 310 covered).

**X4 — unbound input.** `CORRECTION_ADDENDUM` C7 adjudicates `data/reference/tip_times.csv` on
availability grounds, but no packet binds it by hash. Recorded here so a later node can detect
drift: `sha256 = 3bd2c4ab4d7f673f9010a40ac4ac904c88dbb039db4627b0e918d07810c4542a`, 160,391 bytes.

---

## 9. Scope compliance

Written: only inside `experiments/player_program/stage2b/P29_TIP_TIME_AND_COVERAGE_AUDIT/` —
`REPORT.md`, `FINDINGS.json`, `run_measurements.py`, `MEASUREMENTS.json`. No frozen artifact was
modified; `feature_gate.py` and P27's guard were imported and invoked unmodified. No mutating git
command was run — only `rev-parse`, `ls-files` and `check-ignore`, all read-only.
`stage2b/SEALED_RESULTS/` was not accessed.

Reads outside the declared read scope, disclosed: `data/reference/tip_times.csv` and
`data/reference/collect_bios.py` (both tracked, both in this worktree, both required by the
acceptance criteria); and the root-worktree odds directories, read-only and quarantined as
described in section 5.
