# E1_I0061 — defects, recorded not repaired

`PREREG.md` is frozen at `e44c46a5f2b83da6f3834ddcb7b7816b8abe0419bad74c4d74c2478c0f99244a`
and is not edited.

---

## DEFECT 1 — the arm named `A0_SHIPPED_STYLE` is not the shipped model, and the name overclaims

`A0` is a constant-sd Gaussian whose constant is **fitted on strictly earlier seasons'
residuals of this screen's own point forecast**. That makes it a *correctly calibrated*
constant-sd Gaussian: it covers 0.8056 at a nominal 0.80.

The **shipped** object is different. E1_I0056 confirmed on the emitted bytes that its `pred_sd`
is a per-season scalar carried over from a production fold, and measured its nominal-80%
coverage at **0.685**. That number is about a badly-chosen constant. Mine is about a
well-chosen one.

**P1 therefore failed because of my labelling, not because E1_I0056 was wrong.** The
prediction was written as though the two objects were the same; they are not, and nothing
here refutes E1_I0056's coverage finding. The name is left as frozen and the correction is
recorded, rather than the arm being quietly renamed.

**Consequence:** this screen shows a constant-sd Gaussian is nearly as good as anything else
*once its constant is fitted properly*. It does not show the shipped model is fine. The
shipped constant is still wrong and E1_I0056's defect stands unrepaired.

## DEFECT 2 — four of six predictions failed, and the screen's own thesis is the weakest result

P1, P3, P4 and P5 all failed. The thesis (P2) survives only in direction — the scale gain is
**negative**, so the preregistered "at least twice" ratio is computed against a negative
denominator and is not a quantity. The honest statement is "shape helps a little, scale hurts
a little", not the 2× the prereg asked for.

The screen was commissioned on the argument that shape matters more than scale for a bounded,
flat-topped response. That is true and it is small: **+0.83% CRPS**, against the >3% predicted.
The result that matters (P6) is about a branch the distributional argument had nothing to say
about.

## DEFECT 3 — P4's predicted signature was backwards

I predicted the constant-sd arm would show **excess mass in the outer PIT bins** — the classic
too-narrow-in-the-tails signature. Outer mass is 0.1905, slightly *below* the uniform 0.20.
The distribution is strongly non-uniform (χ² 90.1) but the misfit is in the **interior**, which
is what a flat-topped (kurtosis −1.03) response should do to a bell-shaped forecast, and is
what I should have predicted from the shape statistic I had already printed before freezing.

## DEFECT 4 — CRPS is computed on a grid, and pinball is read off a step function

CRPS uses a fixed 0.25-minute grid over [0, 48] for every arm, so comparisons are fair but
absolute values are approximations. The pinball figures read quantiles off the step CDF by
`argmax(F >= q)`, which biases every arm's quantile upward by up to one grid cell. Identical
treatment across arms, so the ordering holds; the absolute numbers should not be quoted.

## DEFECT 5 — `A4` mixes in an availability estimate that is known to be the worse one

`A4` is `A3 × EWMA(prior appearance rate)`. E0_I0019 measured that family at Brier 0.122 /
AUC 0.841, against the shipped `p_active` at 0.092 / 0.902. The headline 11.5% is therefore a
**lower bound** obtained with the weaker instrument, which is the conservative direction — but
it also means this screen has NOT tested the thing it is recommending. Wiring in the good
availability model is a separate screen and needs its own preregistration.

## DEFECT 6 — the DNP universe is "dressed", and who dresses is itself a forecast

`U_DRESSED` contains rows the frame records as dressed, appeared or not. A player who is not
on the roster at all never appears in the frame, so the mixture answers "given they dressed,
will they play?" and not "will this named player produce minutes tonight?". For a prop that
distinction matters and is not resolved here.
