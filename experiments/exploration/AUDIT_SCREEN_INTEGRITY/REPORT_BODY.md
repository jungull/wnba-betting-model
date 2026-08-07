# AUDIT_SCREEN_INTEGRITY — program-wide audit of two known defects

**Status:** complete. **Auditor:** subagent dispatched by Coordinator #04, 2026-08-07.
**Scope:** every shipped E0 screen under `experiments/exploration/`.

> **Provenance of this file.** The auditing subagent was blocked by the harness from writing
> report `.md` files. Its findings were returned inline and **materialized here verbatim in
> substance by Coordinator #04**, per the coordinator mandate to materialize any REPORT that a
> subagent could not write. The machine-readable record in `AUDIT.json` is the subagent's own
> output and is authoritative where the two differ.

---

## Headline

**No shipped E0 screen contains a no-op placebo. No verdict is downgraded. No verdict is
unsupported.** The only no-op instance in the program is the one **I0010 found in its own draft
and fixed inside the same script before reaching a verdict**. It never shipped and did not spread.

**No code anywhere treats `master.observed_time` as an as-of / observation bound.** Every consumer
either refuses it explicitly or uses it in the conservative direction. **No E0 screen output
carries it.**

---

## 1. Defect 1 — the no-op placebo

**The defect.** A negative control that permutes a *grouping key* and then *recomputes the
aggregate from the permuted key* is a no-op: the permuted cell is the same row set under a new
name, so every row still receives its own true value. It looks like a working placebo and tests
nothing. **Diagnostic signature: it reproduces the real number with sd exactly 0.000000.** The
correct form permutes the **assignment of an already-computed value to rows**.

### Per-screen classification

| Screen | Classification | Placebo sd | Verdict | Consequence for the verdict |
|---|---|---|---|---|
| `E0_I0003_rebound_interaction` | NO PLACEBO CLAIMED | — | kill | **Unaffected** |
| `E0_I0004_shot_location_allowance` | GENUINE (specificity control) | not measurable | iterate | **Unaffected** |
| `E0_I0005_turnover_interaction` | GENUINE | 0.007976 | kill | **Unaffected** |
| `E0_I0006_usage_redistribution` | GENUINE (matched-sample) | 0.17240 | kill | **Survives** |
| `E0_I0008_height_differential` | NO PLACEBO CLAIMED | — | iterate | **Unaffected** |
| `E0_I0009_additive_pressure` | GENUINE | 0.000105 | keep-as-lead | **Survives** |
| `E0_I0010_positional_matchup` | GENUINE (no-op caught pre-verdict) | 1.44e-4 / 1.56e-4 / 1.36e-4 | kill ×3 | **Survives** |
| `E0_I0011_tendency_estimator` | GENUINE (single-draw controls) | n/a by design | keep-as-lead / kill | **Unaffected** |

### Evidence

* **I0006** — `analyze_clean.py:105-115` plus `build_redistribution` at `:73-98`. Placebo events
  are the player's **own presence games** (a no-treatment event set); `leave_one_out=True` at line
  82 excludes the pseudo-event from the teammate baseline. No grouping key is permuted, so the
  defect's mechanism cannot arise. Placebo n=167, sd 0.1724, 166 unique values; real n=578,
  sd 0.1311. **This was the highest-stakes item in the audit** — I0006 is the only screen whose
  kill rests *entirely* on its placebo (real 0.470 < placebo 0.539). It holds.
* **I0009** — `analyze.py:120-137` precomputes pressure from a panel keyed on **true** team ids;
  line 144 `off = rng.integers(1, n_teams_row)` starts at 1 so no row can draw its own opponent;
  line 136 asserts the lookup reproduces the real value exactly. This independently reproduces
  Coordinator #03's by-hand code inspection. sd 0.000105; real ≈70× the placebo mean.
* **I0005** — `analyze.py:80-84` permutes `player_tendency_loo`, an already-computed per-row value,
  within season. The shipped `summary.json` records *p* but **not sd**, so the auditor re-ran it
  from a copy (`rerun_I0005_permutation_sd.py`, same seed 20260807, n=2000): **sd 0.007976,
  2000/2000 unique draws, p=0.004 reproduced exactly.** Doubly safe — the kill was made *against*
  the permutation (p=0.004 was overruled by per-season non-replication).
* **I0010** — the shipped version keeps the panel keyed on true `opp_team_id` (`:242-259`) and
  deranges the lookup (`:290-301`); line 286 computes the REAL statistic through identical
  machinery under an identity map. Measured from the shipped draws: **200/200 unique values in all
  15 columns**, no degenerate spread anywhere.
* **I0011** — `score.py:163-176` assigns another player's already-computed expanding estimate to
  this player's rows, with the donor map deranged at `:87`. No distribution exists by design, but
  the no-op signature is definitively absent: `NEG_other_player` degrades MAE 1.7–2.7× on every
  target and ranks last on all four (pts 7.816 vs 4.035; minutes 12.800 vs 4.687).
* **I0004** — `build_and_test.py:211-215` is a **specificity control, not a permutation null**:
  true-opponent aggregate against a deliberately non-informative substitute (+0.0211 vs real RA
  diff +0.0392). It has no distribution, so it **does not bound the effect** and must not be read
  as a noise floor.

### Verdicts now unsupported

**None.** Every E0 verdict either rests on a genuine negative control or never rested on one.

### The real gap found — two screens with no noise floor at all

An *absent* support is not a *broken* support, and neither verdict is downgraded. Naming it
precisely:

* **I0003** (kill) — no placebo, and none needed; the kill's binding limitation is the
  already-recorded ~72% side-of-play measurement confound.
* **I0008** (iterate) — **no noise floor of any kind.** Its +0.018–0.020 incremental R² over
  own-recent-rate has never been compared against a permutation null. I0006 demonstrated *inside
  this same program* that a plausible statistic can be beaten by its own noise floor.
  **ACTION: run a permutation null before I0008's placebo strength is weighed against I0009's or
  I0011's in any E1 promotion decision** — permute which opponent's roster-height aggregate each
  row receives, keeping the aggregate keyed on true opponents.

---

## 2. Defect 2 — the `observed_time` tripwire

**Fact.** String column, 10 distinct values, all mid-2026 file mtimes; on 2021–2024 rows the range
is `2026-07-31T20:42:42+00:00` … `2026-08-01T13:00:36+00:00`. The manifest declares
`asof_granularity: "row"` and states verbatim: *"Any observed_time column in this artifact is a
LOCAL FILE MTIME and is deliberately NOT used as an as-of bound."* Written by
`build_masters.py:490` and `:595`.

### (a) Outputs containing it — no E0 screen does

I0010 caught it on itself and dropped it (`build_features.py:219-223`, `analyze.py:221-227`,
recorded at `NOTES.md:72-77` and `:339-341`).

Four files **elsewhere** carry it with 2026 values. Named here so a future byte-level check does
not misreport them; **none is an E0/E1 artifact and none is a partition violation**:

| file | rows |
|---|---|
| `data/masters/master_player.csv` | 33,712 |
| `data/masters/master_team.csv` | 2,990 |
| `experiments/playoff_shift/series_game_rows.csv` | 212 |
| `experiments/forecast_dryrun/forecast_today.csv` | 2 |

### (b) Treated as an as-of bound — NO instance found

All consumers are conservative or refuse it outright:

* `D10_FIELD_AVAILABILITY_LEDGER/build_ledger.py:229,238-259,683,704-735,796-836` — counts rows
  observed **after** their own cutoff and issues `CUTOFF_UNPROVEN` / `CUTOFF_INVALID`. Lines
  709-711 state the file *"cannot prove the box was observed before the cutoff."* This is the
  opposite of the defect.
* `cbs_provenance.py`, `cbs_real_adapter.py`, `cbs_accounting_v11.py`, `prediction_contract_v3.py`,
  `v4.py` — bound derived from `game_date`; they stamp `observed_time_deliberately_unused: True`.
* `tests/test_cbs_v8.py:532-534` asserts *"the as-of bound is derived from game_date, never
  observed_time."*
* `daily_forecast.py:1046-1050,1089,1147,1240` — propagates it onto forecast rows as a
  **provenance label**; nothing gates on it. **Flagged, not claimed:** it places a 2026 mtime under
  a field name a downstream reader could misread. Ticket, not a finding.

### Adjacent finding — different field, flagged not claimed

`prediction_contract_v5.py:477` sets `candidate_observed_time` for the S2 source to
`pd.Timestamp(f"{season}-01-01T00:00:00Z")` (defined at `:459`) — a **synthetic season-start
marker, not an observation**. `validate_projected_exposure.py:565` then asserts
`observed_after_cutoff == 0` for `B_s2_weak_fallback` and **passes**, necessarily, because the
marker was constructed to precede every cutoff.

This is a **manufactured cutoff-availability pass by exactly the Defect-2(b) mechanism**, but on a
different field. It is already disclosed at `build_projected_exposure.py:128-135`. Routed to the
coordinator, not asserted as a defect.

> **Coordinator #04 action taken:** this was relayed mid-flight to the in-flight D065 **tier-2
> cutoff-validity audit**, with the instruction that a passing `observed_after_cutoff == 0` check
> is not itself evidence of cutoff validity — the timestamp being compared must be traced to a
> genuine per-observation source before any existing pass is credited.

---

## 3. Partition compliance

A value-based parse — **never a byte scan** — of every `.csv` and `.parquet` in all eight screen
directories, testing the **values** of season/date-like columns against {2021, 2022, 2023, 2024}:
**clean, zero violations, zero unreadable files.** Full record in `output_scan.json`.

The deliberately-not-repeated approach is the byte scan for the literals `2025`/`2026`, which
previously produced a **false** partition violation by matching row counts that happen to equal
2026 and digit runs inside floats.

---

## 4. What this audit could not determine

* **I0004** and **I0011** have no placebo *distribution* (a single statistic and a single draw
  respectively), so no sd exists. Both are classified GENUINE **on construction**. Re-running would
  yield the same single value, so neither was re-run.
* The four concurrently-written directories — `E1_I0009_additive_pressure`,
  `E1_I0011_split_alpha`, `S43_CUTOFF_RECEIPTS_TIER1`, `S43_CUTOFF_RECEIPTS_TIER2` — were **not
  audited**, per instruction, because agents held live write scopes on them. **Their placebo
  integrity is unknown to this audit and should be checked once those agents finish.**

---

## 5. Files in this directory

| file | what it is |
|---|---|
| `AUDIT.json` | the authoritative machine-readable record |
| `audit_outputs.py` | the output/partition scanner |
| `output_scan.json` | per-file partition scan results |
| `placebo_spreads.json` | measured placebo spreads per screen |
| `rerun_I0005_permutation_sd.py` / `.json` | I0005 re-run from a copy to recover its unrecorded sd |
| `run_log_audit_outputs.txt`, `run_log_rerun_I0005.txt` | run logs |
| `REPORT_BODY.md` | this file (materialized by Coordinator #04) |
