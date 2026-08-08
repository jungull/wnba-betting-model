# NOTES — E1_I0039_stacking

Working notes: what was run, in what order, why each choice was made, and what I would tell a
successor. `VERDICT.md` is the answer; this is the reasoning.

---

## 0. Order of work, and why the row overlap came first

The brief was explicit: compute the row-set intersections **before any modelling**, and let them
determine how much of the rest is worth running. That instruction turned out to be the single most
valuable thing in the brief, because it changed the shape of the screen.

| step | file | what it did |
|---|---|---|
| s01 | `scripts/s01_inspect.py` | column inventory of five stored frames. No statistics. |
| s02 | `scripts/s02_anchors_and_overlap.py` | **14 anchors, then ROW_OVERLAP.csv.** No statistics. |
| s03 | `scripts/s03_join_probe.py` | join and coverage counts only. No statistics. |
| — | `PREREG.md` | hashed **9ff71975…** after s02/s03, with both disclosed in §10. |
| s04 | `scripts/s04_build.py` | fit frame + **anchor A8** (E1_I0034's P04 minutes, to 5.1e-16). |
| s05 | `scripts/s05_lattice.py` | the lattice: 8 arms × 2 responses × 2 strata + 8 sensitivity cells. |
| s06 | `scripts/s06_controls.py` | vacuous split, negative strata, no-op, random target, type-I. |
| s07 | `scripts/s07_attribution_power_w1.py` | intercept-frozen attribution, injections, W1. |
| s08 | `scripts/s08_findings.py` | assembles `FINDINGS.json`. Computes nothing new. |

**The overlap result reshaped the screen.** I expected three roughly independent components. What
came back was one strict subset (A ⊂ B) and two near-disjoint pairs. That meant the AB cell was a
*redundancy* measurement needing an explicit precedence rule — which did not exist in the brief and
had to be preregistered — and that the AC/BC cells were essentially a *check on arithmetic*. Had I
built the model first I would have spent the effort in the wrong place and probably reported the
AB redundancy as an "interaction".

---

## 1. Why the universe is what it is

**U = 9,022** scored, regular-season, appeared champion player-games, 2023–2024, 960 team-games.

* **2023–2024, not 2022–2024.** E1_I0034's RSP-W2 is the primary window for every D116 number,
  because C's walk-forward increment needs a strictly earlier *scored* season and the champion's
  2021 fold is declared degenerate. Keeping every lattice cell on W2 is what makes the D101
  denominator rule satisfiable: identical rows, response, SST basis, weighting and base. It costs
  a third of the data and I would make the same trade again — a lattice measured on three different
  row sets answers nothing.
* **Regular season only.** Forced by the D087 completeness assertion (DEFECTS DEF-7). The 156
  playoff team-games it surfaced were *not* vacuous.
* **Appeared rows only.** Matches D076's tier-A definition and E1_I0034's REM.
* **Decision stratum n = 3,158.** This is the W2 regular-season restriction of the programme's
  5,111–5,673 and is **not the same number**. It is 35.0% of U against D109's 37.0% of its 13,808,
  so the proportion is stable; the count is not comparable and I have said so everywhere it appears.

**Component definitions, and the two places I had to choose.**

* **A** is D092's rule *as retargeted by D102* — `fallback_level == 2`, not "fewer than 3 prior
  appearances". D102 measured that retargeting as 97% of the value on a smaller population, and
  using D092's original definition would have made A and B *more* overlapping, not less.
* **B** routes to the tuned simple estimator **imported** from E1_I0032, which imports E1_I0027's
  CANON, which is D094's tuned grid. Nothing was re-tuned. Coverage on B's rows is 1.0000.
* **C** is E1_I0034's P04 construction verbatim, verified by anchor A8 to 5.1e-16.
* **Choice 1 — precedence.** A ⊂ B, so `AB` needs a rule. Preregistered: A wins on
  `fallback_level == 2`, B covers `fallback_level == 3`. The alternative (B everywhere) is run as
  a declared sensitivity and is in `STACK_LATTICE.csv` as `AB_Bwins` / `ABC_Bwins`. On pooled
  minutes `AB_Bwins` = +0.3828 and `AB` = +0.3660 — i.e. **giving B its whole row set beats the
  precedence rule**, which is another way of saying A adds nothing.
  Worth stating plainly: `AB_Bwins` is **bit-identical to B** and `ABC_Bwins` is **bit-identical to
  BC**, on all four (response, stratum) cells, to the last digit. That is the containment A ⊂ B
  showing up as an exact identity in the outcome statistics, not merely in the row counts — the
  cleanest confirmation of the overlap result available.
* **Choice 2 — order.** C is applied on top of A/B. The reverse order is measured
  (`order_sensitivity.csv`) and moves ABC's pooled MAE by 0.0048 (minutes) / 0.0044 (points).
  Negligible pooled; **19–22% of the decision-stratum effect**, which is why it is in VERDICT §6.

---

## 2. Why the anchors were worth the time

Seventeen, sixteen at exactly zero deviation. Two of them earned their keep:

* **A3, D092's fallback-row skill −0.1863.** Reproducing it required working out that the published
  "skill" is on an **MAE basis**, not an SSE basis (MAE gives −0.186264, SSE gives −0.219258). That
  is a D101 denominator question hiding inside a single published number, and a successor
  reproducing D092 should know which one it is.
* **A8, E1_I0034's P04 minutes cell.** This is what licenses the entire C machinery, and it caught
  two real defects on the way to reproducing (DEF-1, DEF-2). Without it I would have published a C
  arm that made minutes **0.70 MAE worse** and read as "redistribution destroys the forecast".

---

## 3. The finding I did not expect: components leak onto rows they do not touch

The vacuous split (`vacuous_split.csv`) was run as a guard, expecting it to pass. It did pass in
the sense the brief meant — A's minutes gain is +4.989 (49.3%) on its 632 treated rows against
+0.005 elsewhere, so the gain does live where the treatment is. But the *elsewhere* number is not
zero, and on the decision stratum it is **the entire number**.

**Mechanism.** All arms share a walk-forward intercept refit. Changing what the model emits on 632
cold-start rows changes the residual pool the intercept is fitted on, which shifts every other
row's forecast by a small constant. On the decision stratum, where A and B treat **zero** rows,
that constant *is* the whole measured effect.

**Quantified** (`recalibration_share.csv`, `intercept_frozen_attribution.csv`): freeze the base
intercept and re-measure with each arm equal to the base off its own treated rows —

* A and B on the decision stratum go to **exactly 0.0000** on both responses.
* C's decision-stratum **minutes** number goes **up**, +0.0150 → **+0.0253**: the shared
  recalibration was *costing* C 0.0060.
* C's decision-stratum **points** number goes from +0.0080 to **−0.0044**: the apparent points
  gain there was 100% recalibration, and C's own effect on points is negative, which is what D116
  says it should be.

**This is not a bug.** In production you would recalibrate after routing, so the shared-intercept
number is the one that describes the deployed system. But it is **not attributable to the
component**, and a stacking screen that does not separate the two will credit a component for a
global calibration shift it merely triggered. I would make this diagnostic mandatory for any future
composition screen in this programme.

---

## 4. On the power floors, and why I ended up in a weaker position than preregistered

The prereg promised injection-verified floors derived on this screen's own machinery. **I did not
get them.** Three constructions, three failures, all disclosed (DEF-3, DEF-5, DEF-6):

1. **Constant loss subtraction** — no dispersion, block variance collapses, floor comes out 5×
   *below* analytic. Wrong sign against D113/D116, which is the tell.
2. **Effect planted through the candidate into the response** — the planted δ was swamped by the
   real effect already present; k = 0 recovered the real effect, not zero.
3. **Permuting the component's actual forecast change across team-games, then planting on top** —
   the "null" has a large true effect (misapplied redistribution is genuinely harmful), so it
   calibrates nothing.

Construction 3 is a **good negative control** and is reported as one: misapplied redistribution
costs −5.0% pooled and −12.6% on the decision stratum, which is direct evidence that the *targeting*
carries the effect rather than the functional form.

For the floors themselves I fell back on **D116's carried factors** (minutes 1.22×, points 3.40×),
labelled `MDE80_injection_D116carried` in every artefact, with the analytic floor published beside
it and a second verdict column so a reader can see the dependence. **Twelve of forty verdicts
change between the two floors.** None of them is the headline.

**What I would tell a successor to try instead.** Build the null by *refitting the component on a
response with the candidate's signal removed* — regress y on the candidate, take residuals as the
synthetic response, then plant a known effect back in through the candidate. That preserves the
noise structure (unlike 1), removes the real effect (unlike 2), and does not introduce a true
negative effect (unlike 3). I ran out of budget before I could validate it and am not reporting
numbers from a construction I have not checked.

---

## 5. Things that surprised me

* **A ⊂ B exactly, with zero rows escaping.** D094 said the two recommendations "converge"; the
  overlap says something stronger and more specific — one is contained in the other. `B \ A` is
  313 rows, all `fallback_level == 3`, and those 313 are where B's extra 0.029 minutes MAE over A
  comes from.
* **The whole stack is worse than its best single part.** ABC minutes (+0.3817) < B alone
  (+0.3828); ABC points (+0.2089) < B alone (+0.2140). Not by much, and not significantly, but the
  direction is the opposite of what "aggregate fractional improvements" suggests, and it comes
  entirely from the A/B redundancy plus C's near-zero pooled points contribution.
* **The 30-minute threshold reproduced from a completely different direction.** I measured
  `0 < freed < 25` as a stratum only because the prereg asked for a negative control, and it came
  back **−0.0230 at p 0.0003 — actively harmful**. D116 said the rotation absorbs small absences
  and nothing should be applied below the threshold; this is that statement measured as a cost
  rather than as an absence of benefit. Two screens, opposite directions, same threshold.
* **The points harm reproduced to two decimal places.** D116: −1.17% on the 2,475 rows. Here:
  −1.15%, on a row set rebuilt from a different frame with a different universe filter. The stage
  boundary is real and it is sharp.

---

## 6. What a successor should not re-derive

* `ROW_OVERLAP.csv` is a fact about the champion's own flags and E1_I0034's own definitions. It
  will not change unless one of those definitions changes.
* The A ⊂ B containment means **any future screen proposing both should propose one.** The choice
  is between D092's structural placeholder on 632 rows and D094's tuned estimator on 945; on this
  evidence, on pooled minutes and pooled points, **B alone dominates every combination tested**.
* The decision-stratum answer is **C or nothing**. A and B are structurally incapable of reaching
  it — not weak there, *absent* there — and no amount of stacking changes that.

---

## 7. Files

| file | what |
|---|---|
| `PREREG.md` + `PREREG.sha256` | preregistration, sha256 `9ff71975…` |
| `ROW_OVERLAP.csv` | **run first** — the exact intersections |
| `STACK_LATTICE.csv` | every arm × response × stratum, two verdict columns |
| `additivity.csv` | sum-of-parts / whole for every pair and the triple |
| `vacuous_split.csv` | each component's gain split treated / untreated / untreated∩decision |
| `intercept_frozen_attribution.csv`, `recalibration_share.csv` | §3 above |
| `negative_and_threshold_strata.csv` | freed = 0, 0–25, ≥25, ≥30 |
| `C_on_own_rows.csv` | the decision-stratum commercial cell |
| `control_noop.csv`, `control_random_target.csv`, `power_type_I.csv` | controls |
| `power_injection.csv`, `power_floors.csv` | **failed** construction 1, retained as record |
| `power_injection_componentwise.csv`, `power_floors_componentwise.csv` | construction 3, read as a negative control only |
| `secondary_W1.csv`, `secondary_W1_movement.csv` | the degenerate-fold secondary |
| `order_sensitivity.csv`, `component_A_walkforward_fits.csv` | build diagnostics |
| `nulls/lattice_draws.npz` | 20,000 permutation draws per preregistered cell |
| `out/s0*.txt` | full run logs, including the failed runs |
| `FINDINGS.json`, `VERDICT.md`, `DEFECTS.md`, `NOTES.md` | deliverables |
