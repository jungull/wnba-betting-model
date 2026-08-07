r"""S43 / emit REPORT_BODY.md, the human-readable half of this node's deliverable.

The numbers in the prose are the ones MEASURE_T2_CUTOFF_VALIDITY.py measured and BUILD_RECEIPTS.py
recorded; this file asserts nothing that RECEIPTS.json does not carry. It exists because the node
contract requires a REPORT_BODY.md alongside RECEIPTS.json, matching S33R and S37.
"""
import io
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
R = json.load(open(os.path.join(HERE, "RECEIPTS.json"), encoding="utf-8"))

BODY = r'''# S43_CUTOFF_RECEIPTS_TIER2 — point-in-time cutoff-validity audits of the computed-from-observations fields

**Epistemic status:** POINT-IN-TIME CUTOFF-VALIDITY AUDIT. Exhaustive per-row measurement against
each row's own `forecast_cutoff`. No fit. No performance number of any kind.

**Commissioned by** user decision D065. Discharges the **tier-2** half of S37 finding **A9**
(Severity A). The cheap tier-1 provenance receipts are a separate agent's work and are not
attempted here.

**Verdict: 5 CUTOFF_INVALID, 1 CUTOFF_UNPROVEN, 0 promoted.** The audit obligation is met; the
contract condition A9 exists to satisfy is not. **Fitting must not be authorised on the strength of
this node.**

**Root, stated explicitly:**
`C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program`. Every measurement
below ran against that worktree. `data/masters/master_team.parquet` hashes to `ad79ce5c…8528`,
which is the pin. The main working tree was never read.

---

## 1. What tier 2 actually asks, and the decomposition that made it measurable

The user's ruling sets the standard: *prove that every underlying observation predates the forecast
cutoff*. The D10 ledger sets the test it has been failing: *a per-row source observation timestamp
exists and is ≤ that row's forecast_cutoff; no timestamp means CUTOFF_UNPROVEN; structural
plausibility is never a substitute.*

Those are not the same sentence, and the gap between them is where this finding has been stuck.
Separating them is what let the audit produce a determinate answer instead of a twelfth restatement
of "no timestamp exists":

* **(E) the EVENT claim** — every event whose realisation entered the value had **finished** before
  the row's cutoff.
* **(R) the RECORD claim** — the repository's **observation of** those events existed before the
  cutoff. This is D10's timestamp test.

(R) is unmeasurable here and this node does not pretend otherwise: no capture timestamp exists on
any target artifact, and none was invented. But **(E) is necessary**, it has never been measured
anywhere in this program, and it *is* exactly measurable, because every target's contributing source
set is re-derivable from its producer's own code.

The asymmetry is what makes this worth the effort. **A field that fails (E) is CUTOFF_INVALID, not
merely unproven** — a value that demonstrably absorbs a game which had not finished at its own cutoff
cannot be rescued by any future capture receipt. That is a stronger and more useful result than the
ledger's UNPROVEN, and it is the result five of six constructions returned.

### How each row was bounded in time, without assuming an envelope

1. **Re-derive the producer** so the contributing source set of every row is *recomputed*, not
   argued — then check the re-derivation against the frozen artifact's own values and byte pins.
2. **Take the latest contributing source game.** It binds: if the latest source clears the cutoff,
   every earlier source does too. Classifying only the latest is exact, not a shortcut.
3. **Bound that source event with hard bounds only.** A final score cannot exist before
   *tip + 40 minutes* of regulation clock (+5 per OT period). A game that can start no earlier than
   *00:00 UTC of its own calendar date* cannot still be in progress *24 hours* later. Both are
   bounds on physical fact, not wall-clock estimates.
4. **Compare to `prediction_contract_v4/game.parquet::forecast_cutoff`** — the same per-row column
   the D10 ledger itself joins to.

This node **deliberately refuses to assert a wall-clock envelope** (e.g. "games take about two
hours"). An envelope is a plausibility argument, it points in the direction of PASS, and the
ledger's rule forbids exactly that. Where the hard bounds cannot decide a row, the row is reported
as NOT ESTABLISHED rather than resolved in favour of unblocking.

### The two witnesses, and which verdicts depend on which

| witness | source | D10 verdict | how used here |
|---|---|---|---|
| **A** | `prediction_contract_v4.scheduled_tip_time`, screened by `tip_time_observed_at` | **CUTOFF_VALID** (#26) | freely, both directions |
| **B** | `data/reference/tip_times.csv` | CUTOFF_UNPROVEN (#23) | **alarm only** — may prove a violation, never clear one (S33R precedent) |
| **floor** | 00:00 UTC of the source game's calendar date | needs no timestamp at all | freely, both directions |

Witness A was **traced, not assumed**: 407 rows, 199 distinct capture instants spanning
2025-07-05 → 2026-07-30, zero nulls, every capture preceding both its own tip and its own cutoff. It
is a real capture series, not a marker. Its limitation is stated: live capture began in July 2025,
so it cannot witness 2021–2024 at all. Witness B is market-archive derived and carries no capture
timestamp, so every verdict below states separately what survives refusing it entirely.

---

## 2. Target 1 — the possession prior. The centrepiece, and it falsifies rather than merely fails to prove.

`opponent.opp_pace_estimate` (D10 #50) and `opponent.prior_game_evidence_depth` (#49);
`projected_exposure_v1/team_possession_prior_v1.parquet`; consumed by SC08 as
`z1 = z(projected_team_off_possessions)` and by the score-baseline builder as its pace factor.

**The producer re-derives exactly.** `build_projected_exposure.build_pace` was re-implemented from
its own source and run against `possessions_raw_v2` plus schedule identities alone. All 2,990 rows
reproduce: `pace_level` 0 mismatches, `pace_source` 0, `n_history_games` 0, `team_pace_estimate` max
abs diff 0.0, `projected_team_off_possessions` max abs diff 0.0. The frozen column pin
`9078790427…71bd` and the join-key pin `6b8b2709…d59b` both recompute.

That reproduction is what licenses everything after it: the contributing source set of every row is
now *known*, not inferred. Each row's value is the mean of the last ≤ 10 qualifying prior games
under the predicate `d < r.game_date`.

**GRAPH_POLICY 13.2.2.** There is **no `team_possession_prior_v1.parquet.manifest.json`**, so
`asof_granularity` is **undeclared**. The rule's gate was never passed. This node established the
granularity by re-derivation instead — the artifact is **row-granular at DATE resolution** — which is
stronger evidence than the manifest would have carried, but the process control was simply absent.
See new finding N3.

**The measurement, exhaustive over all 1,491 clusters at the grain SC08 consumes:**

| | clusters |
|---|---|
| event claim **passes** unconditionally (calendar-date bound alone) | 1,426 |
| event claim **FAILS** — provably after cutoff | **44** |
| not established | 21 |

All 44 failures sit under `date_only_prior_day_cutoff`. **All 407 exact-tip clusters pass.** The
lateness of the failures runs from 1.7 to 8.75 hours, median 5.7.

**The producer is not at fault and the card is not at fault.** `d < r.game_date` is honoured
literally and exactly. The defect is structural: a **date-grained lag cannot respect a cutoff that
sits at 18:00 UTC on the day *before* the game.** A team that played last night contributes its
result to a feature whose decision boundary was six hours before that game tipped.

### Answering the ledger in its own words

The ledger's sentence on this artifact — the one this node was told to engage with — is:

> those receipts attest construction order, not observation time… This is the sharpest case in the
> ledger of the difference between 'validated' and 'timestamped'.

That is correct, and this node confirms it independently: construction order re-derives bit-for-bit.
But the framing **understates the result**. Measuring observation time does not leave the field
UNPROVEN. It **falsifies it on 44 clusters**. 'Validated' and 'timestamped' are indeed different
things — and here the timestamped reading is not silent, it is *negative*.

Verdict: **CUTOFF_INVALID**. Refusing witness B entirely (all 44 failures rest on it) downgrades
this to CUTOFF_UNPROVEN — it removes the proof of invalidity and grants nothing.

---

## 3. Targets 2 and 3 — prior box aggregates and every recent-form input

The constructions were **enumerated by reading the eleven arm modules and `features_common.py`**,
not taken from the A9 table. Fifteen constructions across eleven arms. Every one maps onto one of
four sequencing regimes, so none is left unmeasured.

### 3a. Per-team lags — SC01, SC02, SC03's clock, SC05, SC08's sd20, SC10's form, SC12's winsor

Exhaustive over 2,982 team-game rows: **2,912 pass, 45 FAIL, 10 not established, 15 have no source.**

Identical under ROW-strict career, ROW-strict same-season and DATE-strict — because no team plays
twice on one calendar date, so for a team's *own* history the two sequencing conventions coincide.
All 45 failures are under `date_only_prior_day_cutoff`; all 814 exact-tip rows pass.

Verdict: **CUTOFF_INVALID**.

### 3b. League-level lags — SC04 and SC11. The worst result in the audit.

`league_prior_ewma` over the whole universe, half-life 60 league games, sequenced
`(game_date, game_id)`.

| | clusters |
|---|---|
| event claim passes | 314 |
| event claim **FAILS** | **1,061 (71.2%)** |
| not established | 115 |

Lateness up to **33.2 hours**. And this is **the one result that does not depend on the market
archive**: 335 failures are provable from CUTOFF_VALID evidence alone — 184 from contract_v4's
screened tip captures, **151 from the unconditional calendar-date floor, which needs no timestamp of
any kind.**

The cause is `features_common`'s own stated convention that *an earlier same-day `game_id` DOES
count as prior*. **917 of 1,491 clusters have a same-day immediately-prior league game.** Under the
day-before cutoff policy a same-day source is after the cutoff by construction, with no evidence
required.

It also fails on **182 of the 407 clusters that already carry exact tip cutoffs** — so, unlike every
other target here, a better cutoff policy alone would not repair it.

Verdict: **CUTOFF_INVALID**, and it survives refusing witness B.

### 3c. The prior-season carryover — SC03. The one clean result.

`prior_season_aggregates`. **2,572 of 2,572 rows with a prior-season aggregate clear their own
cutoff by the calendar-date bound alone** — no tip evidence needed. Zero failures, zero
indeterminate, zero unwitnessed. The remaining 410 rows are 2021, which has no prior season.

This is the strongest tier-2 position any field in the A9 table reaches, and it is reached by the
construction whose lag is a **season** rather than a **row**. That is the lesson of this audit in
one line: the event claim survives exactly when the lag is coarser than the cutoff's resolution.

Verdict: **CUTOFF_UNPROVEN** — the event claim is clean; only the record claim is missing.

### 3d. Recent form specifically

Every recent-form input in the slate resolves to 3a or 3b: SC10's half-life 4 and 12 spreads, its
expanding same-season anchor and its orthogonalisation covariate; SC12's span-10 winsor correction;
SC08's sd20. **None resolves to the one clean regime** — because a form input is by definition a
short lag, and a short lag is precisely what a day-grained cutoff cannot absorb.

Verdict: **CUTOFF_INVALID**.

---

## 4. Target 4 — the five `score_baseline_rows` prediction columns

`pred_home`, `pred_away`, `pred_total`, `pred_margin`, `p_home`. S37 recorded the gap precisely:
their *"provenance argument was not re-derived from the builder's own inputs."* Re-deriving it is
exactly what was done.

**The re-derivation is byte-identical to the frozen pins.** `build_score_baselines.py` was
re-implemented against the three inputs it names — `master_team.parquet`,
`team_possession_prior_v1.parquet`, `possessions_raw_v2.parquet` — and the rebuilt columns recompute
to their pinned sha256 values: `pred_margin` → `1d79ff3a…4ff4`, `pred_total` → `16c312ab…5f3d`,
`p_home` → `8a92c017…1989`, with NaN positions identical (including the 188). **S37's open item is
now closed as a provenance fact.** It does not make the columns cutoff-valid.

`score_baseline_rows.parquet` also has **no sibling manifest**, so its `asof_granularity` is
likewise undeclared (N3).

**The measurement, as the universe actually assembles these columns** — composite on 1,465 clusters,
`league_average_v1` on the 26 uncovered ones:

| | clusters |
|---|---|
| event claim passes | 1,426 |
| event claim **FAILS** | **44** (42 composite + 2 fallback) |
| not established | 21 |

The columns inherit the pace prior's own 44-cluster defect plus the efficiency EWMA's date-grained
lag over both teams' histories.

**The walk-forward calibration layer is clean and should be recorded as such.** `p_home` is a
logistic in `pred_margin` fitted *only* on seasons strictly earlier than the target's, never pooled,
never same-season. Every training season ends months before the target season begins, so the SEASON
bound implies the row bound for that layer. The binding constraint on `p_home` is `pred_margin`'s
own date-strict source set, not the calibration fit.

Verdict: **CUTOFF_INVALID**. SC09 inherits it, since its treatment feature is a transform of the
K0's own fitted prediction.

---

## 5. NEW FINDINGS

### N1 — fold-train moments are not a row-level as-of. NOT in the A9 table.

`zscore_train()` and `center_on_train()` compute a **fold-train constant over the whole training
window** and apply it to every training row — including rows whose own `forecast_cutoff` long
precedes the last training observation.

Measured, and the result is total rather than marginal:

| fold | train clusters | latest observation entering the fold-train moment | train clusters whose own cutoff precedes it |
|---|---|---|---|
| train_lt_2022 | 205 | 2021-10-17 | **205 (100%)** |
| train_lt_2023 | 444 | 2022-09-18 | **444 (100%)** |
| train_lt_2024 | 704 | 2023-10-18 | **704 (100%)** |
| train_lt_2025 | 966 | 2024-10-20 | **966 (100%)** |
| train_lt_2026 | 1,276 | 2025-10-10 | **1,276 (100%)** |

Consumers: **SC08's `sigma_z_pace_prior` and `sigma_z_lagged_margin_sd`** (both `zscore_train`),
SC08's pooled train-margin-sd fallback, SC04 and SC11's centred league drifts, and SC01/SC10's
lambda selection on the train tail.

**Scope, stated fairly.** Test rows are unaffected: every fold's training seasons end before its
test season begins. This is the standard walk-forward convention and calling it leakage would be
tendentious. But D065's standard is written *per row* — "every underlying observation predates the
forecast cutoff" — and on training rows it is violated on 100% of rows in every fold. **The
coordinator must decide whether the tier-2 standard binds training rows or only evaluation rows.**
This node does not decide it, and flags that the decision is not cosmetic: it is the difference
between SC08's two treatment columns being admissible and not.

### N2 — the slate contains two different meanings of "strictly prior", with different point-in-time consequences

`features_common.STRICTLY_PRIOR_STATEMENT` admits an earlier **same-day** `game_id` as prior. SC01's
card and the pace producer instead use the **date-strict** reading. Measured: **917 of 1,491
clusters** have a same-day immediately-prior league game; 0 team-rows do (no team plays twice a day).

Under the day-before cutoff policy a same-day source is provably after the cutoff with **no evidence
required at all**, which is why 3b fails so much harder than 3a. `features_common`'s own docstring
asserts the opposite rationale — that the primitives exist *"so that one arm's clock cannot silently
disagree with another's"* — and on this axis they do disagree, in the direction that matters.

### N3 — neither consumed artifact carries an `asof_granularity` manifest

`team_possession_prior_v1.parquet` and `score_baseline_rows.parquet` both lack a sibling
`.manifest.json`. GRAPH_POLICY 13.2.2 makes that manifest the gate for relying on a pre-built
artifact, and both were consumed by the frozen cards without one. This node established row
granularity by re-derivation instead — better evidence than the manifest would have given — but the
**process control was absent**, and the next artifact may not be so tractable.

### N4 — a manufactured cutoff-availability pass exists nearby, and the pace artifact is isolated from it

Routed in mid-flight by the coordinator from a concurrent integrity audit, and recorded here because
it is the failure shape this node exists to catch. `prediction_contract_v5.py:459` sets the S2
source's `candidate_observed_time` to `pd.Timestamp(f"{season}-01-01T00:00:00Z")` — a **synthetic
season-start marker** — and `validate_projected_exposure.py:565` then asserts
`observed_after_cutoff == 0` for `B_s2_weak_fallback`, which cannot fail. It is disclosed at
`build_projected_exposure.py:128-135`, so it is not concealed.

**It does not reach any target here, and that isolation was measured rather than read off the
code.** `build_pace()` consumes only `base[['game_id','team_id','game_date','season']]` plus
`possessions_raw_v2`; `candidate_observed_time` is not even in `load_inputs()`'s `keep` list. More
decisively: this node reproduced all 2,990 rows of the artifact from master_team's schedule
identities and the possession stream **alone** — no contract-v5 frame, no roster regime, no candidate
timestamps — including the frozen byte pin. Isolation established by reproduction.

The general lesson is recorded in `RECEIPTS.json` under `timestamp_provenance_trace`: **a passing
`observed_after_cutoff == 0` is not evidence of anything until you trace what timestamp it
compares.** Four neighbouring validations were traced and **none was credited** — including
`PROJECTED_EXPOSURE_VALIDATION.json`'s 35/35, which D10 itself cites for this artifact, and
`validate_projected_exposure.py::pace_matches_independent_rederivation`, which is a genuine check
but a *construction-order* one. No verdict in this receipt inherits another node's pass.

---

## 6. What this audit could NOT establish

* **The record claim, for anything.** No per-row capture timestamp exists for any source box score,
  for the possession stream, for the pace artifact or for the score baselines. Nothing here closes
  D10's actual test, and nothing here pretends to. For 2021–2024 it is **not closable at all** —
  only declarable unclosable.
* **Whether the 44/45 marginal failures survive a stricter evidence standard.** They rest on the
  market-archive tip witness, which may raise a flag but never clear one. Refusing it downgrades T1,
  T2a and T4 from CUTOFF_INVALID to CUTOFF_UNPROVEN. Only T2b's verdict survives that refusal
  intact.
* **21 clusters (T1/T4) and 115 clusters (T2b) could not be decided either way.** 2021 has no tip
  witness of any kind — witness A begins in July 2025 and `tip_times.csv` has no 2021 rows — so
  2021's tight cases are permanently indeterminate on present evidence.
* **Whether the `date_only_prior_day_cutoff` policy is itself the right boundary.** This audit takes
  the repository's declared cutoff as given. 1,088 of 1,495 games sit on a policy constant rather
  than a measurement. Note the direction, which is favourable: a policy cutoff *earlier* than a real
  one makes this audit **stricter**, never laxer. But if the policy is wrong, the failure counts
  change.
* **Whether the D065 standard binds training rows** (see N1). Left to the coordinator.
* **Anything about the other seven A9 fields** — the schedule-identity and rest/travel/timezone items
  (ledger #0, 2, 3, 4, 5, 9, 10, 12, 18, 22). Those are the tier-1 half and belong to the companion
  agent.
* **Whether repairing the lag predicates would leave the arms' carded habitats intact.** Every
  carded stratum census in S37 was measured against the *current* feature values. A re-cut lag
  changes those values and therefore possibly those censuses. Not measured here; flagged.

---

## 7. Disposition of A9's tier-2 half

**The audit obligation is met. The contract condition is not.**

A9 asks for a receipted cutoff-validity measurement for each tier-2 field. That measurement now
exists, is exhaustive over every row rather than sampled, and returns a determinate answer. But S30
section 8's requirement is that an UNPROVEN field used by any arm must first be **promoted** by such
a measurement — and the measurement promotes nothing. It demotes five constructions from UNPROVEN to
**INVALID**.

**The tier-2 half of A9 is NOT DISCHARGED, and fitting must not be authorised.**

This changes the cutoff-valid feature set, which S30 section 11 makes a halt-and-raise. It is
**raised, not resolved**. The repair in every case is a change to a **frozen card's lag predicate** —
replacing a date-grained or row-grained "strictly prior" with an explicit
`source_event_end_time <= row.forecast_cutoff` filter — which this node has no authority to make. The
alternative repair, obtaining exact tip cutoffs for the 1,088 date-only games, fixes most of
3a/T1/T4 but demonstrably does **not** fix 3b.

Every write from this node is inside
`experiments/player_program/stage3_score/S43_CUTOFF_RECEIPTS_TIER2/`. No frozen artifact was
modified. No S33R script was re-run against its own directory. `master_team.observed_time` was
dropped at load and never written. `git` was not run. No fit was performed and no performance number
appears anywhere in this node's output.

This node does not mark its own work accepted.
'''

FOOTER = "\n\n---\n\n*Machine-readable receipt: `RECEIPTS.json` " \
         "(verdict_counts %s). Evidence: `EVIDENCE_DETAIL.json`. " \
         "Scripts: `MEASURE_T2_CUTOFF_VALIDITY.py`, `BUILD_RECEIPTS.py`, " \
         "`BUILD_REPORT_BODY.py`.*\n" % json.dumps(R["verdict_counts"])

with io.open(os.path.join(HERE, "REPORT_BODY.md"), "w", encoding="utf-8", newline="\n") as f:
    f.write(BODY + FOOTER)

print("REPORT_BODY.md written, %d chars" % (len(BODY) + len(FOOTER)))
