# E0_I0029 -- DEFECTS FOUND IN THIS SCREEN'S OWN WORK, AND WHERE I COULD HAVE CHEATED

Two defects were found in this screen's own code, both by guards rather than by inspection, and
both **before** any number was read as a result. Both are recorded here with the evidence that the
fix changed only what it was supposed to change.

---

## D-01 -- THE CONDITIONAL REFERENCES WERE RESPONSE-CONDITIONED (severity: HIGH)

**What it was.** Stages B and C need a reference built on the player's prior **fta>0** games. The
first implementation computed those references on the `fta>0` subframe and joined them back onto
the main frame. That left every one of them **NULL on every `fta == 0` row**.

**Why that is a leak and not merely a gap.** The *availability* of the column then encoded the
response exactly: any row on which `ref_mean__y_fta_given` existed was, by construction, a row on
which the player had gone to the line **tonight**. `corr(notna(ref_mean__y_fta_given), y_any_fta)`
was **+1.0**. A screen restricted to rows where the candidate is finite would have been screening
stage A on a row set where stage A's response is constant.

**How it was caught.** Not by reading the code. `s05` computed `SST = 0.0` on the `F08_ONLY` row
set for target `y_any_fta` and died with a `ZeroDivisionError`. The response had no variance
because every row in that set had `y_any_fta == 1`.

**The fix.** Compute the INCLUSIVE running value on the conditional subframe, place it on the full
frame at the conditional rows, then within `(season, player_id)` take `.shift(1).ffill()`. Row *i*
receives the value accumulated over the player's conditional games **strictly before** row *i* --
defined on every row, and still strictly prior.

**Evidence the fix changed the DOMAIN and not the VALUES** (probes P1c/P1d, `leakage_probes.csv`):

- P1c: max absolute difference against the old construction, on conditional rows: **0.000e+00**
- P1d: `corr(notna(ref_mean__y_fta_given), y_any_fta)` fell from **+1.0** to **+0.1138**
- coverage rose from 53.6% of rows (exactly the conditional rows) to **90.9%** of all rows

**What it would have done to the result had it survived.** Two things, in opposite directions.
(1) `F08` would have looked like a spectacular stage-A predictor and been a pure artefact.
(2) More insidiously, `s04`'s honest stage-B forecast fell back to the **league** value on 46% of
rows, which *understated stage B* on the common denominator. Post-fix, stage B's honest
contribution on the DECISION stratum rose from `+0.15559` to `+0.17019`. **The defect was making
the headline conclusion -- that stage A carries the predictability -- look stronger than it is.**
The conclusion survives the fix, but it survives on a smaller margin, and that is the honest
number.

---

## D-02 -- THE NO-OP PLACEBO WAS NOT A NO-OP (severity: MEDIUM)

**What it was.** The prereg defines `G02_placebo_noop` as "an exact affine copy of **the base's
FIRST column**". The base's first column is `ref_mean__<target>` and therefore **differs per
target**. The first implementation built a single placebo pair from `ref_mean__y_ftm` and reused it
on all six targets.

**Consequence.** On the five targets it was not built from, `G02` was a genuine predictor, not a
no-op: observed **max |dR2| = 2.591e-02**, and it "cleared" its own null at median `p = 0.0017`.
The perturbation check that compared `G03` against it was therefore comparing two live signals and
was meaningless -- it reported `INERT` and stopped the run, which is the guard working.

**The fix.** Build `G02_placebo_noop__<target>` and `G03_placebo_perturbed__<target>` per target,
and have `s05` select the column matching the target under test. **This is a bug fix that brings
the code into line with the preregistered text, not a change to the preregistration**, so the
prereg hash is unchanged and the added/dropped counts remain 0/0.

**The check the fix enables**, which is the one the constraints actually asked for:

1. `G02` must be a **confirmed no-op** -- `max |dR2| < 1e-9` across all its cells, because it is
   exactly collinear with its own base. If it is not, the base being fitted is not the base that
   was declared.
2. `G03` must **actually perturb and be detected** -- its dR2 must sit unambiguously above the
   floor of resolution and clear its own null in a majority of cells. A control that is a genuine
   no-op proves the base is right but says nothing about sensitivity; without arm 2, a null result
   here would be uninformative rather than negative.

---

## WHERE I COULD HAVE CHEATED, AND WHAT STOPS IT

Listed because the constraint asks for it, and because every item here is a place where a
plausible-looking choice would have produced a more exciting number.

1. **Choosing the stage-C exposure.** Stage C's oracle rung `O2` uses the **realised attempt
   count** as exposure, and `ftm` is nearly determined by `fta`. That makes stage C's `R2(O2) =
   0.887` and its "irreducible" share only **11.31%** -- by far the most tractable-looking number
   in the ladder. Reporting that as "conversion is the predictable stage" would have been the
   single easiest way to manufacture a finding here. It is an artefact of the same shape D097
   caught in total rebounds. **The guard**: stage C is *also* reported on the conversion RATE
   itself (`C'  FT% | FTA`), where the matched prior reference scores **-0.0993 (POOLED)** and
   **+0.0296 (DECISION)** -- a player's own prior free-throw percentage barely predicts a single
   game's percentage. And the cross-stage comparison is made only on the common denominator, where
   stage C buys **+0.028 of 0.329**.

2. **Choosing the denominator for stages B and C.** Both live on the `fta>0` subset, whose SST is
   smaller and whose row set is more predictable (73% of DECISION rows). Quoting a subset dR2
   against a full-stratum benchmark would inflate it. **The guard**: D099. Every row of
   `hurdle_stages.csv` and `oracle_ladder_ft.csv` carries an explicit `denominator` column, and the
   headline is computed only on `SST(ftm)` over the full stratum.

3. **Choosing the reference for a conditional stage.** Building stage B's reference on **all**
   prior games rather than prior `fta>0` games would make the reference artificially weak and
   manufacture headroom. **The guard**: the reference is matched (prior conditional games only) and
   probe P1b recomputes it from raw bytes.

4. **Choosing the base.** Every candidate here has a large, significant-looking dR2 over
   `B_SINGLE`. Reporting those would reproduce D087's failure mode exactly. **The guard**:
   `B_SINGLE` is reported only to *exhibit* the shrinkage, never to carry a verdict.

5. **The interaction.** `X01` over `B_COMPLETE` is the number D085 was fooled by. **The guard**:
   both main effects are in `B_MATCHUP` from the start, the `B_COMPLETE` figure is printed and
   explicitly labelled a diagnostic of the trap, and the shrinkage factor is published.

6. **The null.** A row-level shuffle would make almost everything here significant. **The guard**:
   the verdict-carrying null is the cyclic shift (own history) or the entity swap (opponent), the
   row-level p is printed beside every one of them purely to expose the inflation factor, and
   cluster-robust SEs are not used at all.

7. **The stratum.** POOLED includes cold-start and low-minute rows where a free-throw signal is
   partly predicting *who plays*. POOLED numbers are systematically larger here (e.g. the composed
   channel's honest total is 0.232 POOLED vs 0.329 DECISION on a different SST). **The guard**: the
   decision stratum is D081's, `n = 5111`, identical to D097's, and the anchor reproduces D097's
   51.68% to four decimal places.

8. **The partition.** 2025 and 2026 exist in `master_player.parquet` and are 12,250 additional
   rows. They were never read: every load is filtered on `season.isin(2021..2024)` at the
   FILTER-POINT and `assert_partition` re-checks **column values** (not file names) after every
   load and every filter.

## KNOWN LIMITATIONS THAT ARE NOT DEFECTS

- **`M01..M06` are missing on 2.56% of rows** -- an opponent's first game of a season has no prior
  games. Those rows drop out of every cell that uses an opponent column; `n` is recorded per cell.
- **Stage A is fitted by OLS on a binary response** (a linear probability model). This is the D069
  convention and is what makes the number comparable with the rest of the ledger. A logit would
  give a different, non-comparable R2; the honest reading is that the OLS R2 is a *lower* bound on
  what a properly-linked model could achieve, and the oracle rungs bound it from above regardless
  of link.
- **`H4` cannot be scored for 2021** (no earlier season to fit on), which is why the headline is
  2022-2024 and 2021 appears only as a labelled power sensitivity.
- **The champion was never run.** The Step 4 answer is read off the champion's source and artifact
  schemas, not produced by executing it.
