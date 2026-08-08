# CONVERSION_ANATOMY — what the conversion does, in plain language

No statistics background assumed. Six pages of arithmetic, told as a story about units.

---

## The problem the conversion was invented to solve

D103 asks one question of every result this programme has ever recorded: *given how noisy that
measurement was, how big would a real effect have had to be before you'd have spotted it?* That
number is the **detection floor**. If a screen reported "no effect" and its floor was larger than
the biggest effect anyone here has ever found, then "no effect" told you nothing — you couldn't
have seen one either way.

To compare floors across sixty screens you need them all in the same unit. D103 picked **ΔR²** —
"what share of the wobble in the outcome does this predictor explain?" It's a proportion, so a
floor of 0.0023 means the same thing everywhere: *this measurement could resolve an effect
explaining a fifth of one percent of the variation, and nothing smaller.*

Most screens published their noise in ΔR² already. Two did not. `E0_I0014` and `E0_I0019`
published theirs as a **t-statistic** — the older, unitless "how many standard errors away from
zero is this?" measure. Between them they account for **666 of D103's 1,349 cells and 518 of its
760 blind verdicts.** Something had to translate.

## The translation

`s06_retrospective.py`, lines 66–77:

```python
def mde80_tscale(sd_null_t, t_crit, n):
    return float(((t_crit + Z80) * sd_null_t) ** 2 / n)
```

Three ingredients:

* **`sd_null_t`** — how much the t-statistic bounced around when the screen shuffled its data to
  simulate "no real effect". The width of the noise.
* **`t_crit`** — how far out a result had to land before the screen called it real. The bar.
* **`n`** — how many rows of data.

And the logic, which is genuinely elegant:

> A t-statistic and a ΔR² are two views of the same thing: **ΔR² ≈ t² / n**. So work out how big
> `t` has to get, then square it and divide by `n` to get back to ΔR².
>
> How big does `t` have to get? It has to clear the bar (`t_crit` widths of noise) — and it has to
> clear it *reliably*, four times out of five, so add another 0.84 widths of headroom for the
> noise pushing you the wrong way. Total: `(t_crit + 0.84) × sd_null_t`.
>
> Square it. Divide by `n`. Done.

**I checked all of that and it is correct.** The ΔR² ≈ t²/n identity holds on E0_I0014's own
published cells to a median ratio of 1.0000 (using the exact form with `df = n − 4`). The formula
itself, given honest ingredients, reproduces a floor measured the hard way — by actually planting
effects of known size in synthetic data and seeing when they got caught — to a median of 0.989
across 96 conditions built to match this programme's real structure. **The equation is not the
problem.**

---

## Defect one: the noise width is the width of the wrong variable

Here is the whole thing in one picture.

A t-statistic has a sign. It can be +2 (the predictor pushes the outcome up) or −2 (it pushes it
down). When the screen shuffled the data 1,000 times, it got 1,000 t-values scattered on both
sides of zero — a symmetric cloud.

`E0_I0014` then did this (`s04_screen.py`, line 211):

```python
v = np.abs(tvec(yt, Xx, NS)[1])      # <- np.abs
```

It **threw away the sign** before storing them. That's reasonable for its own purpose: it only
cared about "how far from zero", not "which way". Every one of the 18 saved arrays has zero
negative values and a minimum of exactly 0.0 — the fold is visible in the file.

But now measure the width of what's left. Fold a symmetric cloud in half and it gets narrower —
you've stacked the left side on top of the right side. For a normal-shaped cloud the folded
version is only **0.603×** as wide.

D103 reads that folded width and puts it into a formula whose entire derivation is about the
*signed* statistic. The bar comes out 40 % too close. The floor, which is the bar squared, comes
out **2.75× too small**. Every one of E0_I0014's 348 cells looks about three times more sensitive
than it was.

`E0_I0019` kept the sign (`s04_screen.py`, line 181: `null_t[s][d, ci, di] = tt`), so its 318
cells are clean on this point. **Same field name in D103's table. Different variable underneath.
Nothing in the code says so.**

### Recovering what was thrown away

The signed width isn't lost. If the cloud was centred on zero to begin with, then

> (signed width)² = (folded width)² + (folded average)²

exactly — no assumption about the cloud's shape, only that it was centred. Both quantities survive
in E0_I0014's saved file. Checked against the truth in simulation, where both versions exist: the
recovery is off by a median of **0.03 %**, worst case 4.6 %, and it works just as well on
heavy-tailed and flat-topped clouds as on normal ones.

Applied to the real cells, the recovered widths are a median of **1.79×** the published ones —
a bit above the 1.66 you'd get from a perfectly normal cloud, because the real clouds are not
perfectly normal.

## Defect two: the bar was borrowed from a different kind of measurement

`t_crit` is supposed to answer: *how many noise-widths out does a result have to land before we
call it real, given that we're looking at 348 results at once and one of them will look
impressive by luck?*

D103 didn't compute that for the t-statistic. It reused a number computed for a **different
statistic** — a standardised ΔR² from screen D089 (`s04_power.py`, lines 70–72). And ΔR² is a
*squared* quantity: it can't go negative, and its cloud has a long tail off to the right where a
t-statistic's cloud is symmetric. A lopsided cloud's "how many widths out" number is much bigger
than a symmetric one's, for exactly the same level of caution.

The borrowed number is **6.686** widths (E0_I0014) and **6.974** (E0_I0019). The right number for
348 or 318 symmetric results is **3.795** and **3.773** — which I measured two ways: by the
standard formula, and by generating a 60,000-draw noise cloud in simulation and reading the
answer off directly, with a separate 60,000-draw cloud held back to check it. The two agree.

So the bar is roughly **1.8× too far out**, and the floor — bar squared — about **3× too large**.

## The accident

Put the two defects together for E0_I0014:

```
too-narrow width   ×   too-distant bar
    0.559          ×        1.762        =  0.985
 (measured median fold 1.79;      (6.686 / 3.795)
  1/1.659 = 0.603 if the
  cloud were exactly normal)
```

**They cancel to under two percent.** E0_I0014's published bar works out to 3.735 of its own true
noise widths; the correct bar is 3.795. Two substantial errors, in opposite directions, landing
almost exactly on the right answer for entirely the wrong reasons. (On the *floors* the median
per-cell discrepancy is larger — about 12 % — because the fold factor varies cell to cell and the
resulting ratio is right-skewed; the cancellation is exact only at the median.)

E0_I0019 has only the second defect, uncompensated, and its floors come out about **2.85× too
large** against the same benchmark.

This is why the conversion looked fine to everyone who glanced at it, and it is why the direction
of the correction flips depending on which bar you regard as correct. It also means the family's
floors carry no *reliability* — they happen to be near-right in one screen and far-wrong in the
other, and nothing about the construction would have told you which.

## Defect three: some of the noise clouds aren't noise

The formula's logic is "a narrower noise cloud means a sharper measurement means a lower floor".
That is true — right up until the cloud collapses for a reason that has nothing to do with
sharpness.

Shuffling only destroys a pattern if the shuffle actually moves things. Shuffle a column that is
constant inside every block, by swapping whole blocks around, and for some columns almost nothing
changes: the statistic lands in nearly the same place every time. The result is a **tight cloud
sitting a long way from zero** — which is not a picture of a well-measured cell, it's a picture of
a test that never ran.

You can spot it without any modelling. For *any* symmetric cloud, the average distance from zero
is about **1.32×** the width. If that ratio comes back at 20, the cloud isn't centred on zero and
the shuffle didn't do its job. `E0_I0019`'s authors knew this and built exactly this check for
themselves (`s05_spreads_and_decomposition.py`, lines 56–58, cut at 5). Nobody applied it to
`E0_I0014`, and D103 doesn't apply it to anyone.

* **67 of the 666 cells** are over that line.
* **6 more have a noise width of exactly zero.** For those, the formula returns a floor of exactly
  0.0 — a perfect measurement, infinitely sensitive, recorded as such.
* **35 of the 73 are counted by D103 as adequately powered.**

The formula is doing exactly what it was told. A collapsed null is the cheapest way to buy a low
floor, and there is nothing in the code that notices.

---

## What this changes

Correcting the folding alone — the one defect that is a plain category error rather than an
arguable design choice — moves D103's headline from **56.34 % to 65.68 %** of recorded cells
unable to detect the programme's own best finding. Using each screen's own bar instead of the
borrowed one takes it to 67.31 %. Using the textbook bar takes it *down* to 45.44 %.

D103's message was: *most of our null results are uninformative, not evidence of absence.* That
message is not overturned by any of these. Under the correction I'd defend, it gets stronger. What
does not survive is the **precision** of the number: 56.3 % was quoted to two decimals and it is
really somewhere between 45 % and 67 % depending on a convention nobody wrote down.
