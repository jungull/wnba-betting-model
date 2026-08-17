# The availability defect, read as a constraint violation rather than a calibration one

**E1_I0051_constraint_sweep.** `PREREG.md` sha256
`05b1e7ec055eb7f1442baf13aa76da760d0f78be6ba71bdda85b956489ca8c5f`, 21,909 bytes. §6 of that file
records **two predictions, P1 and P2, written before this analysis** and both derivable from
`E1_I0046`'s arithmetic rather than from any fit.

> **NOTHING HERE IS ENACTED AND NOTHING IS RECOMMENDED.** Three repair options are already recorded
> in `E1_I0035_availability_sum/REPAIR_OPTIONS.md` and are awaiting the user. This document
> measures. It adds no fourth option.

---

## THE ANSWER IN THREE SENTENCES

**No. The constraint framing does not suggest a repair the calibration framing missed, and the
reason is that a roster sum is not a budget.** What it does instead is *derive*, from arithmetic and
before looking, two things `E1_I0035` had to *measure*: that `Xb` — the repair that looks most like
a constraint projection — must be exactly vacuous downstream, and that `Xa`'s advantage is not that
it calibrates better but that it is **non-uniform within the team-game**. **That is a strictly
weaker contribution than finding a new repair, and it is reported as such.**

---

## 1. WHY THE ROSTER SUM IS NOT A BUDGET — P1, MEASURED

`E1_I0046`'s constraint was a **fixed budget**: the shares of a composition sum to 1, exactly, with
no error. `E1_I0051`'s re-measurement used a different but equally hard one: **200 team-minutes, +25
per overtime period, fixed by the rules of basketball.**

The availability sum is neither. Measured on the same 1,776 team-games:

| quantity | mean | sd | **cv** | distinct values | lands on a rules lattice? | MAE of the best pre-tip assertion | **as % of itself** |
|---|---:|---:|---:|---:|---|---:|---:|
| **team MINUTES** | 201.26954 | 5.85727 | **0.02910** | 10 | **YES — 1,776 of 1,776 within 0.0667 of a multiple of 25** | 1.26984 (assert 200) | **0.63091 %** |
| **realised ROSTER SIZE** | 9.41273 | 1.00771 | **0.10706** | 7 (integers 6–12) | **NO — no rule fixes it** | 0.84157 (assert the mean) | **8.94073 %** |

*(Row set: all 1,776 regular-season team-games, 2021–2024, appeared roster. `AVAILABILITY_P1_TIGHTNESS.csv`.)*

**The roster count is 14.17× looser, as a fraction of itself, than the minutes budget.** There is no
rule of basketball that says nine or ten players must appear. A coach may play seven or twelve. The
realised roster size is an **outcome**, exactly as the team's points total is an outcome — and
`PREREG.md` §2 classifies both the same way.

**P1 is confirmed. The availability defect is a LEVEL defect, not a compositional one, and
projection is not the right operation for it.** D112's calibration framing was the correct framing.

---

## 2. THE ONE THING THE CONSTRAINT FRAMING DOES DERIVE — P2

`E1_I0035` measured that `Xb` (normalise `Σ p_active` to `R̂`) changes the downstream exposure
allocation by **exactly nothing**:

> Xb's measured misallocation is **8.912455 minutes — identical to the unrepaired champion to the
> last digit.**

That is presented in `REPAIR_OPTIONS.md` as an empirical discovery — *"the decisive detail"*, found
by measuring. **The constraint framing predicts it, exactly, with no data.**

`E1_I0046`'s second arithmetic fact is that **a team-game-constant quantity cannot move an
allocation**, because adding it to every member of a composition and renormalising divides through
by the same shift. `Xb` multiplies every `p_active` in a team-game by **one scalar**
`s_g = R̂_g / Σ p_active_g`. The exposure producer then allocates a fixed 200 team-minutes in
proportion to `p_active × e_min` — that is, it **renormalises within the team-game**. A uniform
per-team-game rescaling is precisely a team-game-constant multiplicative shift, and it therefore
cancels identically.

Verified numerically in `s05_controls.py` on this screen's own 1,776-team-game structure, with
randomly drawn positive weights and randomly drawn per-team-game scalars, so the demonstration is a
property of the arithmetic and not of any basketball fact:

```
max | project(w)  −  project(s_g · w) |   over 16,717 rows / 1,776 team-games   =   2.132e-14
```

That is floating-point exactness, not analytic exactness stated loosely: the deviation is at the
level of double-precision division and the algebraic cancellation is exact.

`AVAILABILITY_P2_CANCELLATION.csv`. **P2 is confirmed.**

### What that buys, stated at its real size

It buys a **reason**, not a repair. `E1_I0035` already reached the right conclusion by measuring;
this only shows the conclusion was available a priori. The one operational consequence is a rule
that generalises past `Xb`:

> **Any proposed repair to `p_active` that is uniform within the team-game is arithmetically
> incapable of changing anything downstream of the exposure producer.** It can only move the
> reported sum. Testing such a repair against the exposure metric is testing an identity.

That rule closes a family — the same shape as `E1_I0046`'s disposal of opponent, venue, pace and
rest for allocation responses — rather than opening one.

---

## 3. WHY `Xa` WINS, RESTATED IN CONSTRAINT TERMS

`E1_I0035` ranks `Xa` first because it improves the team sum **without an established cost to
individual forecasts**, and because it *"targets the actual mechanism"*.

The constraint reading gives the same answer for a sharper reason. The defect is **not** that
`Σ p_active` has the wrong level. It is that the surplus is **concentrated in one subpopulation**:

| | rows | surplus players per team-game | share of the surplus |
|---|---:|---:|---:|
| Tier B, the 0.800 constant | 1,625 | +0.685 | 73.2 % |
| Tier B, fitted logistic | 2,147 | +0.462 | 49.3 % |
| **Tier A** (slightly *under*-predicts) | 16,312 | **−0.211** | **−22.5 %** |
| net | 20,084 | +0.937 | 100 % |

(`E1_I0035/DEFECT_ANATOMY.md`; not recomputed here.)

**A uniform correction is the wrong shape for a non-uniform error.** `Xb` shrinks the 13,600
well-calibrated tier-A probabilities in order to absorb an error living in 3,772 tier-B rows, and
duly degrades tier-A Brier by **−0.014239, which is 5.7× the injection floor: ESTABLISHED HARM**.
`Xa` is tier-dependent, and tier **varies within the team-game**, so it is exactly the class of
correction that *can* move an allocation. Its misallocation falls **8.91 → 4.01** minutes where
`Xb`'s does not move at all.

**So the constraint framing reproduces `E1_I0035`'s ranking. It does not change it.**

---

## 4. THE PLACE WHERE A REAL BUDGET *IS* HIDING, AND IT IS ALREADY HONOURED

There are **two** constrained quantities in this area and they have been conflated:

| quantity | constraint | fixed at a higher level? | honoured? |
|---|---|---|---|
| `Σ p_active` over the universe | ≈ E[roster size] | **NO** — an outcome, cv 0.107 | n/a — not a budget |
| **the exposure allocation of 200 team-minutes** | **exactly 200** | **YES — by the rules** | **YES, in shipping code** |

The exposure producer *does* enforce a hard budget, and it enforces it correctly. That is why the
`+8.14` points of level bias and the `8.91` minutes of misallocation are **two different defects**:

* the **+8.14 points** is a pure level error and it reaches only a bottom-up team total;
* the **8.91 minutes** is a pure *shape* error — the distribution of roster weight — and it is the
  only part that survives the producer's own renormalisation.

**Fixing the level does not touch the shape.** `Xd` is the proof: it achieves the best team MAE in
the table (8.794) and leaves the exposure allocation bit-identical. `E1_I0035` says this in prose;
the constraint framing makes it the same statement twice.

This is the census entry that surprised me. `E1_I0035`'s exposure allocation is classified
**HONOURED** in `CONSTRAINT_CENSUS.csv`, and **it is the only place in this programme where the
200-minute budget is actually enforced — in shipping code, not in a screen.** Thirteen screens
modelled minutes against that budget without enforcing it. The producer nobody was auditing got it
right.

---

## 5. WHAT THIS DOCUMENT DOES NOT ESTABLISH

* **It does not measure `p_active`.** Every number in §3 is quoted from `E1_I0035` and none is
  recomputed here. `E1_I0035` reproduced `E1_I0033` exactly and there is no reason to doubt it, but
  this document contributes **no independent measurement of the availability forecast**.
* **It does not test a fourth repair**, and it deliberately does not propose one. The rule in §2 is
  a *negative* result about a family of repairs.
* **P2 is a derivation of something already known.** Had `E1_I0035` not already measured Xb's
  downstream null, P2 would be a prediction; as it is, it is a post-hoc explanation that happens to
  have been written down in advance in this screen's own preregistration. **The reader should
  discount it accordingly.**
* **Nothing here touches 2025 or 2026.** Never opened.

---

## 6. THE ANSWER TO THE QUESTION AS ASKED

> *Does framing it as a constraint suggest a repair the calibration framing missed?*

**No.** The calibration framing was correct because the roster sum is not a constraint of the kind
that would make projection appropriate — measured, P1, at 13.3× looser than a real budget. The
constraint framing contributes one closed family (`§2`: uniform repairs are downstream-vacuous by
arithmetic) and one sharpened reason for a ranking that does not change. **D112's recommendation
stands exactly as recorded, and `Xa` remains the only option that passes at both levels.**
