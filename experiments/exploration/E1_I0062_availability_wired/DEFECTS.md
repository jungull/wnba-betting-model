# E1_I0062 — defects, recorded not repaired

`PREREG.md` is frozen at `bfbd792b5180f1245efc732bf87ecb67682bcd0bcc96bc7745534a182c57f195`
and is not edited.

---

## DEFECT 1 — the provenance this screen rests on is inherited, not established here

`v15 p_active` is consumed as an out-of-fold production artifact. Its point-in-time
discipline — that no row was scored using information unavailable at its forecast cutoff — is
**E0_I0019's finding, not this screen's**. That screen needed four attempts at the leak probe
and withdrew three of them as confounded before reaching a verdict of ESTABLISHED.

Every number in this report is downstream of that verdict. If it is ever overturned, nothing
here survives, and this screen has no independent standing to fall back on. It ran no leak
probe of its own.

## DEFECT 2 — all five predictions passed, which is itself worth suspicion

A screen where everything the author predicted came true is a screen that risked predicting
only what it already knew. Three of the five were close to guaranteed before running:

- **P5** (the good instrument is the better instrument) restates E0_I0019's measurement.
- **P4** (the gradient shrinks with threshold) restates E1_I0061's measured gradient.
- **P1** (the better instrument wins) is P5 pushed one step downstream.

Only **P2** — that having *any* branch beats having a *good* one — was a genuine risk, and it
is the only prediction whose failure would have changed a decision. The screen is best read as
a confirmation with one live question in it, not as five independent successes.

## DEFECT 3 — the post-hoc recalibration result is unexplained

Recalibrating `p_active` improves it as an instrument and degrades the minutes forecast that
consumes it. The report offers a plausible mechanism — the played branch is fitted on players
who played, so it runs high for marginal players and `p_active`'s downward bias offsets it —
**and that mechanism is not tested.** It is a story attached to a number.

What is established is only the number: do not recalibrate before wiring in. Why remains open,
and a screen that wanted to use this properly would have to find out, because a compensating
pair of biases is a fragile thing to ship.

## DEFECT 4 — the recalibration subset is not the primary subset

The recalibration needs a strictly-earlier season to fit on, so it covers 9,908 of 14,299
rows and drops the first available season entirely. Its comparison against raw `p_active` is
computed on that subset for both arms, so the contrast is fair, but its numbers are **not**
comparable to the primary table above, which uses all 14,299.

## DEFECT 5 — three seasons, 222 players, and one league

2021 is absent because both availability arms are degenerate there. The cluster bootstrap
resamples 222 player-seasons across three seasons of one league. The gradient across
thresholds is the strongest internal evidence that the mechanism is real; the magnitudes carry
whatever a three-season sample carries.

## DEFECT 6 — the played branch was rebuilt, not imported

`played_branch_cdfs` re-derives E1_I0061's `A3_EMPIRICAL_COND` inside this screen rather than
loading its output, because that screen wrote scores and not per-row CDFs. The construction is
copied and the constants are imported from it, but it is a **re-implementation** and was not
asserted equal to the original row for row. A difference in the played branch would move every
arm identically and so cannot create a difference between arms — which is why this was
accepted — but the absolute CRPS values here are not guaranteed to reproduce E1_I0061's.
