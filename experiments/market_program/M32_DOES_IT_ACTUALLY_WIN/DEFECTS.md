# M32 — defects, recorded not repaired

`PREREG.md` is frozen at `22edafa5d230a817e4c468b9d8ff5920b002481e259c7b4651376529c17412e1`
and is not edited.

---

## DEFECT 1 — the preregistered negative control was empty by construction

The prereg specified a control of quotes where the book is STINGY by 3pp or more,
`gap <= -0.03`. **That set is empty and always would have been.** `gap` is defined on the side
TAKEN, and the side taken is whichever of over/under carries the larger edge -- which is always
the side the book is generous on. The control could never have fired.

It was written as a real safeguard and it was not one. Had the primary come back positive, the
screen would have reported a passing negative control that had tested nothing.

**Substituted, and disclosed:** the control is now the OPPOSITE SIDE of the very same quotes.
That answers the same question -- if peers identify a mispriced side, the side they call
overpriced should lose more. It does not: −6.04% against the primary's −7.21%.

## DEFECT 2 — the coordinator published the untested version of this result first

D157 measured the ≥3pp dislocation against consensus and reported +1.44%/+2.74%. The
coordinator relayed that to the user as "the only positive-expectation route measured", sized
at 26–92 bets a season, with the caveat "measured against consensus, not truth" attached.

The caveat was correct and was carried as boilerplate for four exchanges rather than treated as
the open question it was. It took a direct user question -- *is there any profitable strat yet?*
-- to make anyone test it. **The honest reading is that the caveat was doing decorative work.**

## DEFECT 3 — one snapshot per game, and its timestamp is unwitnessed

The archive holds a single vendor-asserted snapshot per game, median 1.16 hours before tip
(D027). Nothing here establishes that any of these prices was available when a bet could have
been placed, in either direction. A negative result on unexecutable prices is not proof that an
executable version would also lose -- it is evidence, not closure.

## DEFECT 4 — the primary bucket is a tail of a tail

915 quotes, drawn from 19,559, across 3 seasons of one league, clustered into 230 game dates.
The interval excludes zero, so the finding is not merely underpowered -- but the by-season
split is 575 / 285 / 55, and the 2026 cell (n=55) has an interval spanning ±33 points. Nothing
season-specific should be read from this.

## DEFECT 5 — `edge` and `gap` select different things and only `gap` was preregistered

The primary is bucketed on `gap` (peer consensus minus this book's de-vigged probability). The
`edge > 0` row uses a different selector (consensus over the vigged price) and returns −8.99%,
worse than the primary. Both are reported; only `gap` was preregistered as the primary, and the
`edge` row should be read as the secondary it is.
