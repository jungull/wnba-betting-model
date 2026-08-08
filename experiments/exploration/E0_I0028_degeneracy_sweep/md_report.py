"""E0_I0028 -- the two narrative documents, built by TOKEN REPLACEMENT.

Why not %-formatting: the prose contains em-dashes, percent signs and markdown tables, and
`"...%s..." % (...)` treats every literal `%` in that prose as a format spec. Token replacement has
no such coupling, so the text can say "97% of the value" without an escaping ritual.
"""

TOK = "@@"


def render(template, ctx):
    out = template
    for k, v in ctx.items():
        out = out.replace(TOK + k + TOK, str(v))
    assert TOK not in out, "unreplaced token remains: %s" % (
        out[out.index(TOK):out.index(TOK) + 40],)
    return out


DEGENERATE_REGIONS = """# Degenerate regions in the champion's output — 2022–2024

**Answer to the question that was asked: beyond the cold-start region already known from D092 and
D094, there are ZERO new degenerate regions.**

The brief was right that this is a good answer. The champion is sound outside a region that has
already been identified. Below is what that conclusion rests on, one genuinely new *structural*
fact inside the known region that is worth money, and two defects that a skill-ranked sweep would
have ranked away to nothing.

---

## 1. The headline, and how hard it was tested

The sweep ran a checklist fixed and hashed **before any data was read** (`_prereg.json`, sha256
`@@PREREG@@`): six defect families across twenty pre-game partitions, four targets, two arms, three
seasons — **@@NCELLS_TOTAL@@ cells**.

**@@NCONT@@ of the @@NCELLS@@ cells flagged as constant or near-constant are ≥99% inside the
champion's own `is_fallback` flag.** The single exception is 98.2% inside it.

`is_fallback`, `component_id == */prefix_mean`, `fallback_level in {2,3}`, `is_cold_start`,
`n_prior_games == 0`, `n_prior_appearances == 0`, the low bins of the player's season game index,
`tip_time_quality is null` and `fit_eligible == False` are **not nine discoveries. They are one
population seen through nine windows.** (`tip_time_quality is null` is 100.0% inside `is_fallback`
on all three continuous targets — 1,071 of 1,071 rows.)

The decisive test is the **residual sweep**: the entire checklist re-run with the known fallback
rows removed. Across **@@NRESID@@ non-fallback cells it flagged near-constancy exactly
@@NRESIDD1@@ times.**

**Positive control — the sweep must find the one known instance or it is broken.** It does,
unaided:

| quantity | D092 published | this screen |
|---|---|---|
| points, `n_prior_appearances < 3` | mean 8.704, sd 0.013 | **mean 8.7061, sd 0.0138** (n=5,378, exactly 3 distinct values) |
| minutes, same rows | mean 21.62, sd 0.09 | **mean 21.6056, sd 0.0878** |
| attempts, same rows | *not reported by D092* | mean 7.3146, sd 0.0360 |
| pooled points skill (D081) | −0.22% | **−0.2222%** |

The skill figure reproduces D081's published number to four decimals against D081's own stored
reference column, which validates the join, the truth mapping and the scoring path before any new
claim is made.

---

## 2. What IS recoverable — and the new structural fact about where it lives

D092 described the region as *"fewer than 3 prior appearances"*. That phrase covers **two
populations whose recoverable value differs by more than an order of magnitude**, and the smaller
one holds almost all of it.

Measured against D081's own reference column, v15 arm. **The row counts here are SCOREABLE rows**
— the ones an error can actually be computed on — which is why they are smaller than the
predicted-row counts in the ranked table further down:

@@D081TABLE@@

**Read the points row.** Routing the whole region gains **+2.90%**. Routing only the zero-history
rows gains **+0.08%**. Routing only the one-or-two-prior-appearance rows gains **+2.82%, which is
97% of the total.**

**Two facts drive that, and they compound:**

1. **Most zero-history rows are not scoreable.** A player with no prior appearances frequently does
   not appear in this game either, so the row carries no outcome. `fallback_level == 2` is **33.7%
   of the region's predicted rows (1,815 of 5,378) but 89.3% of its scoreable rows (947 of
   1,061)**. Both numbers are in the tables; quoting only the first would overstate how much the
   sub-region narrows the operational footprint.
2. **The champion is much worse where it is scoreable.** It loses to the tuned simple baseline by
   **9–10%** on the zero-history rows and by **39–66%** on the one-or-two-appearance rows. That gap
   is not a scoreability artefact — it is measured on the same rows for both forecasts.

**Why this matters practically.** On a row with no history at all a constant is defensible — there
is little to condition on and a simple baseline is nearly as blind. On a row where the player has
already played once or twice, the baseline uses that and the champion does not.

> The defect is not *"the champion emits a constant when it knows nothing"*.
> It is **"the champion keeps emitting the constant after it has started to know something."**

Both sub-regions are readable from the champion's own `fallback_level` column at forecast time.
**A rule that routes only `fallback_level == 2` captures ~97% of the value while touching 34% of
the region's predicted rows**, and leaves the genuinely-no-history rows on the champion.

### The full ranked table

@@RANKTABLE@@

Every gain above is significant at the block sign-flip floor (p = 0.00025; clusters =
season × player; 4,000 draws) and stays positive at the **worst** of 8 shrinkage constants × 2
estimator forms.

---

## 3. The counterexample: degenerate does NOT mean recoverable

The **v15 `p_active`** head emits **exactly one** distinct value — 0.8, sd 2.2e-16 — on 2,268 rows
under `component_id == p_active/declared_constant`. By the preregistered test this is the *most*
degenerate cell in the entire sweep.

**Routing it to the simple baseline loses 4.96% of pooled Brier skill.** The flat 0.8 is genuinely
better there than a prior-appearance-rate estimator. The same region on the **v14** arm *gains*
2.08%.

A blanket "route every fallback region" rule would **destroy** v15 `p_active` skill. The decision
has to be made per (arm, target), and this is the case that proves it.

---

## 4. Two defects a skill-ranked sweep would have ranked away

### 4a. `pred_sd` is a per-season constant — on 100% of rows

`pred_sd` takes **exactly one value per season** on each continuous target — **three distinct
values across 2022–2024** — on all 21,617 (v15) and 17,809 (v14) rows. Every player in a season is
emitted with the same predicted dispersion: the leading scorer and the twelfth man alike. Its
correlation with the champion's own realised absolute error runs **−0.0122 to +0.0002**, which is
indistinguishable from zero.

**The sharp part: the quantiles are fine.** On the same rows `q95 − q05` takes **6,519** distinct
values for points, 1,912 for minutes and 4,550 for attempts; nothing ever crosses; coverage is
86.5–87.7% against a nominal 90%. The champion **does** carry per-row dispersion — it simply does
not put it in `pred_sd`.

> **Anything downstream that sizes stakes or computes edge from `pred_sd` is reading a per-season
> constant, while a per-row answer sits unused two columns away.**

`p_active` is worse: `pred_sd` **and all five quantile columns are 100% NULL** on every row of both
arms — 21,617 and 17,809 rows respectively. That head emits no uncertainty at all.

**Recoverable pooled skill: zero.** The point forecast is untouched, so the skill metric is blind to
this. That is exactly why it is reported separately instead of being ranked away — and why a screen
that ranks only by recoverable value would have missed it entirely.

### 4b. A zero floor on the lower quantile

No prediction and no `q05` is ever negative, and the minimum is exactly 0.0, so both are clipped at
zero. 135 v15 points predictions sit exactly at 0.0. The **lower quantile** saturates far more
often: **`pred_q05` is exactly 0.0 on 42.7% of v15 points rows**, 30.7% of attempts rows and 15.4%
of minutes rows.

For a non-negative quantity a zero floor is *correct*, not a bug. The narrower consequence worth
stating: on those rows `q05` carries no information and the interval is effectively one-sided.

---

## 5. What was checked and found clean

| check | result |
|---|---|
| quantile crossings (q05 ≤ q25 ≤ q50 ≤ q75 ≤ q95) | **0** — every row, both arms, all targets |
| point forecast outside its own [q05, q95] | **0** — every row |
| interval coverage, nominal 90% | 86.5–87.7% — mild under-coverage, inside the preregistered tolerance |
| duplicated prediction vectors outside the known region | largest cluster 70 rows / 11 players (points); nothing structural |
| ceiling / upper saturation | none on any target |
| near-constancy outside the known region | **none**, across @@NRESID@@ cells |

---

## 6. What is NOT a finding, and why

D6 flagged `fit_eligible == False` (352 rows) and `evaluation_tier == B_transaction_sensitivity`
(113 rows) with a nominal-90% interval covering 71.4% of realised minutes.

**Those cells contain only @@NSCOREABLE@@ scoreable rows.** A coverage estimated on 14 outcomes has
a standard error near 8 percentage points; 0.714 is 10 of 14. This is noise, and the brief's own
rule — a 20-row curiosity ranks below a 700-row region — applies to it. Recorded as **underpowered,
not established**, so a future screen with more scoreable rows in that tier can pick it up.

An earlier draft of this document described these cells as a defect found. That was wrong and the
correction is recorded in `FINDINGS.json` rather than quietly made.

---

## 7. Honest limits

- **The preregistration was amended after the data was inspected.** The trigger was a row-count
  mismatch alone — the two arms sit on different contracts, and binding both to contract v4 would
  have silently dropped 3,808 v15 rows (17.6% of its output). No defect statistic existed when the
  amendment was written; `run_log_s01_FAILED.txt` is retained as evidence of how far step 01 got.
  It corrected one input path and added six partitions; it dropped and relaxed nothing.
  **A reader who rejects the amendment can read the v14 arm alone, which it does not touch — every
  headline holds there.**
- **The baseline is tuned**, which flatters the routing gain. Tuning is walk-forward on strictly
  earlier exploration seasons; 2022 has no earlier season and uses an untuned default (k = 5) fixed
  in the prereg before any data was read. Worst-case-over-grid figures are published beside every
  selected one, and every headline gain survives the worst case.
- **This sweep tests the champion's OUTPUT.** A region degenerate in some way none of the six
  preregistered families describes would not be found by it.
- **2021 is excluded** as a known non-finding (degenerate by design, `n_train_rows = 0`,
  `model_was_fitted = false`, confirmed from both arms' fold receipts). **2025 and 2026 were never
  read.**
"""


NOTES = """# E0_I0028 — degeneracy sweep: working notes

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

Prereg sha256 `@@PREREG@@`; amendment sha256 `@@AMEND@@` (added 6, dropped 0, corrected 1).

## The three design decisions that carried the result

**1. Containment before novelty.** The sweep flagged @@NCELLS@@ constant-ish cells, which looks
like a large haul. Almost all of them are the *same rows* selected by a different column. Testing
containment in `is_fallback` first collapsed @@NCONT@@ of @@NCELLS@@ into one known region. Without
that step this screen would have reported nine "regions" that are one.

**2. The residual sweep is the real test.** Re-running the whole checklist with the known rows
*removed* is what makes "there are no others" a measurement rather than an absence of effort.
@@NRESID@@ cells, @@NRESIDD1@@ near-constant flags.

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
"""
