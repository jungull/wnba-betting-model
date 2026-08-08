# NOTES -- E1_I0038_within_entity_null_audit

Working notes: what was done, in what order, what was decided and why, and what a successor
should pick up. `VERDICT.md` has the answer; this file has the reasoning.

---

## 1. WHAT THIS SCREEN WAS ASKED TO DO

D115 rulings 1-2. Audit the 550 killed cells at exposed entity levels; classify by null scheme
and candidate level; flag `null_mean > observed` everywhere computable; re-measure a small
number; and verify, implement and demonstrate the D-04 amendment to D108's injection protocol.

D115 emphasised that the audit is "a query against columns already recorded". **That turned out
to be truer than expected in one direction and less true in another.**

* *Truer:* for **all 83** exposed cells the correctly matched null had already been run and its
  p is on disk. No refit was needed to correct a single verdict.
* *Less true:* the null mean was recorded by the screen itself for only **846 of 1,999** cells.
  It had to be recovered from raw `.npz` draw archives for **916** more. Without those archives
  the flag would have been computable on 42% of the record.

## 2. ORDER OF WORK

1. `s00_inventory.py` — every CSV under `exploration/` with a null/level/scheme column; every
   `FINDINGS.json`; full column dump of the 8 census source tables.
2. `s01_probe.py` — per-screen: which recorded p is the decision p, and which null produced it,
   established by **exact numeric match** (`|p_col − p_correct| < 1e-12`) rather than by reading
   a column name. Cross-checked against each screen's recorded scheme label where one exists.
3. `s02_ledger.py` / `s03_npz_probe.py` — the decision ledger (114 entries, see §6) and the
   seven raw permutation-draw archives, including the statistic each is on.
4. **PREREG.md written and hashed** (`09ccb1fa…`). Section 0 discloses everything already seen,
   including the one fact that could have shaped a rule (see §3).
5. `s04_audit_table.py` — the 1,999-row `AUDIT_TABLE.csv`.
6. `s05_flag_refine_and_triage.py` — flag agreement, the `z` refinement, `TRIAGE_RANKING.csv`.
7. `s06_d04_demonstration.py` + `s06b_mechanism.py` — the five preregistered D-04 runs and the
   post-hoc mechanism correction.
8. `s07_remeasure.py` — the free matched-null recheck and the 4 paid re-measurements.
9. `s08_coverage.py` — how much of the programme the census does not cover.
10. `s09_summary.py`, `s10_d04_confirm_250.py` — reconciliation and the confirmatory run of the
    shipped module at 250 replicates.

## 3. THE ONE METHODOLOGICAL CHOICE THAT COULD HAVE BEEN GAMED

The exposure rule needs a threshold on the candidate's between-entity variance share. Any
number I invented would have been open to the charge that I picked the one that produced the
most casualties.

`E0_I0014/s04_screen.py:229` reads `use_between = np.where(np.isfinite(vsb), vsb > 0.5, True)`.
**The programme already had an operational 0.50.** I adopted it for that reason, disclosed it in
PREREG section 0 *before* freezing, and preregistered sensitivity at 0.30 and 0.80 (143 and 35
exposed). A reader who prefers 0.80 gets a smaller number and the same conclusions, because all
11 family-wise flips sit above 0.85.

There is an irony worth recording: adopting `E0_I0014`'s threshold also guarantees `E0_I0014`
scores zero exposed cells, since it chose its own nulls by that exact rule. That is not
circularity — it is the correct answer arrived at twice — but it should be said out loud.

## 4. WHY `UNDETERMINABLE` CAME OUT AT ZERO

This is the number most likely to be misread, and DEFECTS D-06 covers it in full. Short version:
`E1_I0036` needed a **level name** to build a team-level frame and ruled 436 cells ineligible
without one. This audit needs a **between-entity variance share over the null's own entity**, and
1,069 cells carry one. A measured share is a stronger record of "where the candidate varies"
than a declared string, and more screens happen to have it.

I did **not** relax the D-01 line that matters: **no level, no entity and no variance share was
ever inferred from a candidate's or a column's name.** Every classification cites either a table
value, a frozen prereg JSON, or an exact file:line in the screen's own source
(`null_source_cite` in `AUDIT_TABLE.csv`).

Strip both concessions (`CODE`-sourced entities and `COMPUTED` shares) and the headline drops
from 83 to 65 exposed, all from `E0_I0016`, all `TABLE`+`RECORDED` — and nothing in `VERDICT.md`
changes.

## 5. THE FINDING I DID NOT EXPECT

I went in expecting to find screens that had pointed the wrong null at the wrong candidate.
**There are none.** Every screen that ran a within-entity null also ran the matched
between-entity null in the same pass, on the same rows, and wrote both p-values down.

The damage is entirely in `p_correct = max(p_within, p_between)` — "credited only if it beats
BOTH". That reads as textbook conservatism and it is, right up until one of the two nulls has
no power, at which point the conjunction is unfalsifiable rather than strict. The screens that
were bitten are the ones that were *more* careful, not less.

`E0_I0019` (D090) had already worked this out on its own: its DEF-4 repair replaced the max with
two separately reported schemes, on the reasoning "two schemes, two questions, no max()". That
repair is the fix D-02 proposes, arrived at independently, months earlier, and never
generalised.

## 6. SMALL DISCREPANCIES, RECORDED RATHER THAN SILENTLY RECONCILED

* **The brief says the decision ledger has 115 entries. It has 114** (`D001`…`D115`, with `D068`
  absent — the sequence skips from `D067_A9_TIER2_HALT_AND_RAISE` to `D069_WEIGHTED_R2_CONVENTION`).
  Nothing in this screen depends on it.
* **`E1_I0036` reports `N_CYCLIC`'s null mean as 7.90e-03; D097's own archive gives 7.88024e-03
  and my own 601-draw rebuild gives 7.9343e-03.** All three are the same quantity at different
  draw counts and seeds; the ordering claim (`null_mean > observed = 6.488e-03`) holds in all
  three. I used D097's own recorded draws for the preregistered anchor A2 because they are the
  only version that predates the hypothesis.
* **`E1_I0036` reports `N_CYCLIC` injection power 0.95 at 100 replicates; I get 0.933 at 60.**
  Consistent within Monte-Carlo error — and the size of that error is itself DEFECTS D-03.
* **My census reproduces `E1_I0036`'s counts exactly** — 1,999 cells, 1,580 kills, 213
  `player_season` + 337 `opp_team_season` killed (= D115's 550), 299/427 including survivors,
  213 ceiling kills across 16 candidates. These were asserted as hard gates in `s04`; the script
  halts if any moves.

## 7. WHAT I DELIBERATELY DID NOT DO

* **Did not re-measure any of the 213 arithmetic-ceiling kills.** They are named in
  `CEILING_EXCLUSIONS.csv`. A ceiling kill is arithmetic and survives every methodological
  revision, this one included.
* **Did not write anything back into the eight census screens**, though writing their own null
  means back from their own `.npz` archives would discharge D103 ruling 2 retrospectively for
  916 cells. Out of scope; recorded in DEFECTS D-05 as available work.
* **Did not modify the shared screen kit.** `scripts/lab38.py` and `scripts/d04_protocol.py` are
  local copies, written that way specifically so the kit could stay closed while other agents
  hold it open.
* **Did not fit a champion, did not propose any production change, and did not open 2025/26.**
  Partition asserted on every frame load.
* **Did not re-run D103's power audit on the 11 flipped cells.** D085's own D103 record says 53
  of its 132 cells were blind to the programme's best live effect; correcting a null does not
  correct power, and some of the 11 are probably still uninformative for that separate reason.

## 8. FOR A SUCCESSOR, IN PRIORITY ORDER

1. **The 11 D085 flips need the standard treatment before any is more than a lead:** a power
   check under D103/D113, a recomputation of D085's 132-cell family under the matched arm alone,
   season stability, and walk-forward. `A10_opp_defrtg → ppm` is the fourth independent sighting
   of the opponent-defence signal (after D098, D099 and D103's incidental observation) and is the
   one worth doing first.
2. **Audit the 30 out-of-census screens.** `E1_I0021_heterogeneity_diagnostic` first — it is
   specifically a heterogeneity screen, it carries `p_vs_cyclic_null` and
   `n4_cyclic_null_mean_w` columns, and it is therefore more likely than average to have pointed
   a cyclic null at a between-entity quantity.
3. **Retrospectively write `null_mean` / `null_sd` back into the eight census screens** from
   their own draw archives. Cheap, discharges D103 ruling 2 for 916 cells, and makes the `z`
   refinement (specificity 0.980) computable on the whole census instead of 234 cells.
4. **Forbid `max()` over an unvalidated null arm** in the shared kit — when it is safe to touch.
5. **Raise the injection replicate floor to 250** in every screen currently running.
