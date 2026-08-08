# E0_I0028 — degeneracy sweep: working notes

## What was asked

D092 and D094 found that the champion emits a near-constant for players with fewer than three prior
appearances, and that fixing that one region was worth pooled points skill −0.22% → +1.36% (D081).
**Nobody had asked whether there were others.** A feature screen cannot find this, because it is a
fact about the model's *output*, not about the data — and pooled error absorbs a degenerate region
silently, since the affected rows are a small share and the average barely moves.

## Answer

**Zero new degenerate regions.** The cold-start / fallback region is the only one.

## How it was run

| step | file | what it did |
|---|---|---|
| 00 | `s00_prereg.py` | wrote and hashed the checklist. **Read no data at all.** |
| 00b | `s00b_prereg_amend.py` | declared amendment: per-arm contracts, +6 partitions |
| 01 | `s01_load.py` | joined predictions + provenance + contract + priors; positive control |
| 02 | `s02_sweep.py` | the preregistered checklist over 1,612 cells |
| 03 | `s03_routing.py` | containment, residual sweep, uncertainty defect, routing gains |
| 04 | `s04_adjudicate.py` | fixed the containment bug; adjudicated every surviving flag |
| 05 | `s05_findings.py` | wrote the documents from the tables (computes nothing new) |

Prereg sha256 `895bac8bc2255c9d660ac956873884eefbc95ddab6128fd80cbf90b8cbc6dac0`; amendment sha256 `f110da75d20249a8efd88a507644a31ca56962dc03a558cd4e6d2065563d207f` (added 6, dropped 0, corrected 1).

## The three design decisions that carried the result

**1. Containment before novelty.** The sweep flagged 104 constant-ish cells, which looks
like a large haul. Almost all of them are the *same rows* selected by a different column. Testing
containment in `is_fallback` first collapsed 103 of 104 into one known region. Without
that step this screen would have reported nine "regions" that are one.

**2. The residual sweep is the real test.** Re-running the whole checklist with the known rows
*removed* is what makes "there are no others" a measurement rather than an absence of effort.
286 cells, 0 near-constant flags.

**3. Ranking by recoverable value separated two things that look identical.** `R2` (0 prior
appearances) and `R3` (1–2 prior appearances) are both inside D092's region and both emit the same
constant. By oddity they are indistinguishable. By recoverable value they differ ~37×. That is the
one genuinely new actionable fact this screen produced, and only the value ranking exposes it.

## Two things that nearly went wrong

**A label is not a value.** Cell labels were round-tripped through CSV, so a partition group whose
key is a real `NaN` was compared against the four-character string `"nan"`, matched nothing, and
was reported as `NOT_FULLY_CONTAINED` with `n_rows = 0` — four false "new regions". An assertion
that a flagged cell must match at least one row caught it. It is the screen kit's K0 lesson one
layer down, and it is fixed at source (`_S()` in `s02_sweep.py`, under an asserted invariant that
no partition key carries a NULL).

**A small region overstated.** The D6 coverage cells (352 and 113 rows) were briefly written up as
a defect found. They hold **14 scoreable rows**. Coverage on 14 outcomes is noise. Demoted to
underpowered, with the error recorded rather than erased.

## Kit usage

`_screen_kit` was **not** imported — three other agents are running in adjacent directories and the
kit has been edited mid-run by concurrent agents before (`E1_I0022` recorded exactly that reason).
The four things needed were reimplemented in `dg_base.py` with the ideas credited in its header:
value-based partition assertion (kit K0/K4), `r2_of_forecast` / skill semantics (D081), block
sign-flip paired null (D081), cyclic shift within groups (D093). No kit defect is reported, because
the kit was not exercised.

## Reproduction

```
python s00_prereg.py && python s00b_prereg_amend.py && python s01_load.py
python s02_sweep.py && python s03_routing.py && python s04_adjudicate.py && python s05_findings.py
```

Every step re-verifies the prereg hash and re-asserts the 2022–2024 partition on values, never on
text. Run logs for each step are in `run_log_s0*.txt`; `run_log_s01_FAILED.txt` is retained
deliberately as the evidence behind the amendment.
