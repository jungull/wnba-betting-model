# COORDINATOR STATE PACKET — 2026-08-08

## 0. READ THIS FIRST: THIS IS NOT A RETIREMENT HANDOFF

**Coordinator #06 is STILL ON DUTY.** The user directed on 2026-08-08 that there be no handoff
this session (`D070`) — #06 does not self-retire and does not summon #07. All five scheduled
coordinator tasks are **disabled**, including the daily backstop, so nothing will spawn a competing
coordinator.

**This packet exists as INSURANCE, not as a succession.** The previous packet
(`COORDINATOR_HANDOFF_2026-08-07.md` §13) is now **thirty decisions stale**. If you are reading
this because the session ended unexpectedly, start here.

**If you are a successor:** the program has **no automatic restart** — the daily cron is off. Ask
the user before re-enabling it, and identify yourself as **Coordinator #07** if you take over.

---

## 1. STATE

* **100 decisions** in `DECISION_LEDGER.jsonl` (`D070`–`D100` were added this session).
* Graph unchanged at **104 nodes / 86 PASSED / 1 HALTED / 2 READY (parked) / 3 USER_REQUIRED /
  6 BLOCKED / 6 SUPERSEDED** — expected, since discovery work creates no graph nodes by design.
* Tree clean, **everything pushed**, repository gate **PASS 35/35**.

## 2. IN FLIGHT — CHECK BEFORE RE-DISPATCHING ANYTHING

Six agents were running when this was written. **Check whether their directories exist and contain
`FINDINGS.json` before assuming anything.** A dead agent leaves a directory that can look complete
(`D083` — read `experiments/exploration/E1_I0004_efficiency_transfer/ABANDONED.md` for the canonical
example, where a complete-looking `FINDINGS.json` rested on a construction the agent had itself
flagged as wrong).

| directory | question |
|---|---|
| `E1_I0026_detection_floor` | **What is the smallest effect this program can detect?** If the floor is above 0.001, a large share of ~1,000 nulls are power failures. |
| `E1_I0027_reference_ladder` | One canonical reference; re-price every quoted lead. **Does the ranking change?** |
| `E0_I0028_degeneracy_sweep` | Are there other regions where the champion emits a degenerate output? |
| `E0_I0029_freethrow_hurdle` | The last untested feature channel; free throws are a hurdle process, not a rate. |
| `E1_I0030_home_advantage_accounting` | Team home advantage is real — **where does it go at player level?** An accounting identity, so a null is not an available answer. |
| `E1_I0031_rapm_as_prior` | A walk-forward RAPM artifact exists, carries a manifest, and **no screen has ever used it.** |

## 3. WAITING ON THE USER — DO NOT SELF-GRANT

1. **`D067` / `N1`** — the halted score lane. The cutoff audit went *against* us. Fitting remains
   **unauthorised** for that lane.
2. **`D078`** — the M13/M14 calibration defect. **Measured and immaterial** (7.7% of one CI width);
   recommendation on record is annotate + fix-forward, not re-run.
3. **`D095` — NEW AND THE MOST CONSEQUENTIAL.** The **measurement regime boundary coincides exactly
   with the exploration/confirmation partition boundary**: 92% of exploration rows are one gamelog
   format, and 2025/26 contains **zero** rows of it. **A failed E2 confirmation would be
   uninterpretable.** An operational hold is in place: **no E2 should start until this is ruled on.**
   It costs nothing — nothing is ready for promotion.

**Two production changes are validated and await authorisation** (both are model changes):
* **cold-start tiering** (`D092`): below 3 prior appearances, replace the champion with
  `λ(n)·own_running_mean + (1−λ(n))·(league + depth-chart-rank + draft-slot)`, `λ(n)=n/(n+2)`.
  Pooled points skill **−0.22% → +3.51%**; tier MAE 6.06 → 4.02.
* **fallback routing** (`D094`): route the champion's own `is_fallback` rows to a tuned simple
  estimator. **Two independent routes reached this same recommendation.**

## 4. WHAT CHANGED METHODOLOGICALLY — READ BEFORE DESIGNING ANY SCREEN

**Eight traps, each paid for at least once.** The full checklist is
`experiments/exploration/IDEATION_QUEUE/TRAP_CHECKLIST.md`. The three that are new today:

* **REFERENCE INCOMPLETENESS (`D087`)** — a candidate can be real, non-random, and *not incremental*,
  because the reference measured the target one way and the candidate smuggled in a second. It
  **passes the leakage probe, the entity-swap null and the correct-level permutation null.** Only
  decomposition catches it. **Reference dependence is now the top-ranked source of wrong answers in
  this program** — the same result has moved 6.5×, 4.6× and **8.12 points** on reference choice alone.
* **AUTOCORRELATION IN THE NULL (`D093`)** — a within-player shuffle is **anticonservative** for
  shift-expanding regressors, which is this program's modal construction. Use the **cyclic** variant.
  The kit now refuses the unsafe path. **This repair caught a false positive in the very next screen**
  (`D097`), on its strongest candidate, under a preregistered rule.
* **VACUOUS CONTROLS (`D093`)** — the natural per-player control is a **literal no-op** (sd 5.2e-17)
  and returns a clean bill of health while testing nothing.

**The shared kit** (`experiments/exploration/_screen_kit/`) is at **224 assertions, all passing**.
Nine defects found by seven users. **Read its FALSE-ASSURANCE AUDIT section** — it documents seven
further ways it can be confidently wrong. **Frozen to bug fixes only**; new capability arrives only
when a *second* screen independently needs it.

**The program-wide invariant (`D086`):** *a substring match on a column name may only ever NOMINATE a
column for a value test; it may never, by itself, cause a violation.* Five instances of that trap,
including one the coordinator committed **in a throwaway script hours after adopting the rule**.

**`D100` — the newest policy:** hindsight-informed data **may** be used to decide **where to look**,
and **never** to produce a number that drives a decision. Disclose when you use it.

## 5. THE SCIENCE, IN ONE PARAGRAPH

Single-game scoring **efficiency is not forecastable from pre-game state** — four campaigns, ~1,000
cells, no survivor (`D081`, `D084`, `D085`, `D087`). Rebounds and assists have **less** reachable
headroom than points, not more (`D097`), so `D051` is now discharged for all five targets. A
**tuned simple estimator beats the champion pooled on all four targets** (`D094`); the champion wins
only on the rows it genuinely models, and only on points and attempts, by about 1%. **The
+3.55% minutes skill cited all session was a statement about the benchmark and has been withdrawn.**
The best usable lead is the **teammate-volume channel** (`D089`, walk-forward points dR2 +0.0023,
strictly pre-game); note that ~49% of that channel is same-day news nobody can have. An
**opponent-defence effect** worth ~+0.005 is **raised but NOT accepted** (`D098`, `D099`) — mostly
pooled rather than concentrated, and ~4× smaller than first headlined.

**Start here:** `IDEATION_QUEUE/CLOSED_SURFACES.md` (what is dead **and the mechanism that killed
it** — the mechanism is what tells you whether a variant could survive), then `QUEUE.md` (44 ranked
candidates, 75% structural).

## 6. THE HABIT THAT MATTERED MOST

**Verify agent claims on bytes, and read the whole artifact before calling anything an
inconsistency.** Twice this session the coordinator began writing up a false discrepancy and the
artifact simply had more structure than the first read — both times the agent was right. The
inverse also holds: agents caught **four** coordinator errors today, including a briefing that
misquoted its own ledger and a claim repeated across many messages that did not survive a proper
benchmark.
