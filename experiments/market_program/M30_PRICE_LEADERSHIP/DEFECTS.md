# M30 -- defects, recorded not repaired

NOTE ON THE NODE NUMBER: this node was first created as M29, which collided with the existing and already-PASSED M29_CREDIT_BURN_ATTRIBUTION, and was renumbered to M30. `PREREG.md` still carries the old title in its text because it is HASH-FROZEN and is not edited for any reason, cosmetic ones least of all. D158 records the renumber.

`PREREG.md` is frozen at `895d004fceaf3c3f64bc0d2f04e581520c284925d2af089672b8e5f2d0371f87`.
It is not edited. These are the ways it turned out to be wrong, written down so that the
difference between what was promised and what was delivered stays visible.

---

## DEFECT 1 -- the preregistered primary statistic is degenerate

**What was frozen.** "Median `book_share` minus median `cons_share`, cluster bootstrap by
game, 2000 draws, seed 20260819."

**What happened.** Every median came back 0.000, at every threshold, with intervals that
also round to zero. The statistic is not noisy; it is measuring the wrong thing.

**Why.** Over a 20-90 minute horizon most quotes simply do not change. At the primary
threshold, 65.8% of dislocated books do not move at all, 43.7% of consensus values do not
move at all, and 32.9% of observations have neither side moving. A median over a
distribution with a point mass that large at exactly zero reports the point mass. It was the
wrong estimator for a discrete, mostly-stationary price process, and that was foreseeable
before freezing -- 82.6% of consecutive quote pairs are identical, which could have been
checked from the panel shape alone. It was not checked.

**Consequence.** **P1, P2 and P3 are NOT EVALUATED on the preregistered statistic.** s01
stands exactly as frozen and its degenerate output is kept in `FINDINGS.json` rather than
deleted. Everything in `s02` and `s03` is post-hoc, is labelled as such in the files
themselves, and may motivate a preregistered follow-up but may not be quoted as confirmed.

**What a corrected prereg would say.** Mean share, or better, movement denominated in
probability points with the zero-movement mass reported separately -- because "the book did
not move" is itself one of the answers to the question being asked, not a nuisance.

---

## DEFECT 2 -- `last_update` cannot detect staleness in this feed

**What was frozen.** "The fraction of observations where `last_update` is unchanged is
reported alongside the headline, and the primary statistic is recomputed on the subset where
the book DID update."

**What happened.** The gate passed 100% of observations. `last_update` differs across 99.6%
of consecutive captures (55,454 of 55,694) while **82.6% of the prices are identical**. The
feed re-stamps the field on every poll, so it records when the feed was asked, not when the
book moved. This is the same mechanism D151 found when phantom in-play arbitrage could not
be detected by quote age.

**Repair, and its status.** The *intent* of the gate is unambiguous -- did the book requote?
-- so `s02` reimplements it on **price identity**. This is a substitution of measure, not a
change of question, and it is disclosed here, in the s02 docstring, and in the report.
`PREREG.md` is not edited.

**It mattered.** Split on price identity, the two subsets behave completely differently:
where the book requoted, book-minus-consensus share is +0.661 [+0.457,+0.970]; where it did
not, consensus still closes +0.132 [+0.097,+0.172] of the gap on its own. Had the broken
gate been trusted, both would have been pooled and reported as one number.

---

## DEFECT 3 -- reversion is not the same as regression to the mean, and this node cannot separate them

**Not a preregistration error; a limit of the design, recorded so it is not overclaimed.**

American odds are discrete. A book quoting an extreme price has more room to move toward the
middle than away from it, so some apparent reversion is arithmetic rather than information.
This node cannot separate the two, and does not try.

**Why the headline survives it anyway.** The practical question is not the mechanism but
whether the gap closes and who closes it. For a bettor, taking the generous side of a
dislocation and watching the gap close is positive closing-line value whatever caused it.
The mechanism would matter for a claim about which books are *informed*, and no such claim
is made -- P4 was in fact refuted.

---

## DEFECT 4 -- the sample is small and one-sided in time

48 games and 20 calendar days, with a six-day capture blackout (2026-08-09 to 08-14, D154)
sitting in the middle of it, and a median cadence of 60 minutes that only became 5 minutes
on the final day. The horizon studied is therefore "about an hour", and nothing here
describes what happens in the last minutes before tip-off, which is when the largest moves
in this market are generally expected. The 2025 `hist_` replication in `s03` is the only
out-of-sample check performed.

---

## DEFECT 5 -- the horizon is defined on consecutive captures, so faster polling breaks it

**Not a preregistration error caught late; a design flaw the faster capture cadence exposed.**

`PREREG.md` defines the horizon as "consecutive captures 20 to 90 minutes apart". That ties
the study's clock to the POLLING RATE rather than to real time. When capture ran hourly,
consecutive captures were about an hour apart and the gate passed. Now that capture runs
every 5 minutes (D154 follow-up), consecutive captures are 5 minutes apart and **no pair
qualifies at all** -- which is why extending the pin from 203 captures to 231 added exactly
zero observations. The tape got better and the study got nothing from it.

**Not repaired here.** Repairing it means changing the frozen definition, and the correct
form -- pair each capture with the nearest capture 20-90 minutes LATER, regardless of how
many captures fall in between -- would silently restate s01's population. It is recorded for
the follow-up prereg instead, which should define the horizon in clock time.

**Consequence for what is published:** every number in this node describes the HOURLY tape.
Nothing here uses the 5-minute capture, and nothing here describes sub-hour dynamics.
