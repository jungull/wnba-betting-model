# M31 DISLOCATION PERSISTENCE -- preregistration

Frozen **before the data required to answer it exists**. At the time of freezing, the
five-minute capture era holds 107 captures over 8 games and 31 dislocation episodes, which
is far below the sample gate set out below. Nothing beyond those counts has been computed:
no duration, no survival estimate, no persistence statistic of any kind.

Preregistering now is the point. The analysis is fixed while the answer is still unknowable,
so it cannot be shaped to whatever the tape turns out to say.

## The question

M30/D157 established that a book out of line with its peers reverts to them, and that a
dislocation of about 3 percentage points is where the return becomes positive. It said
nothing about **how long such a price stays on the screen**, and that is the question that
decides whether any of it is reachable.

The opportunity board refreshes every ten minutes. If a 3pp dislocation typically survives
half an hour, the board can catch it. **If it typically survives five minutes, the board is
structurally incapable of ever showing one in time, and no amount of ranking or presentation
fixes that** -- the answer would be that this edge is not addressable at our polling rate,
which is a finding about the product and not about the market.

## Why this is admissible against the partition

**No game outcome is read, joined, plotted or described in this node.** It measures how long
a price persists, not whether the price was right. Same admissibility as M30 and D147.

## Data

The five-minute capture era only: `live_*.json` at or after `2026-08-19T14:00:00Z`, which is
the first capture after the cadence change. The hourly tape is EXCLUDED and cannot be used
here -- a phenomenon lasting minutes is invisible at a sixty-minute grid, and pooling the two
would let the hourly era dominate the sample while contributing nothing about short horizons.

This is the defect that M30 recorded as DEFECT 5 and did not repair. Here the horizon is
defined in **clock time**, never in "consecutive captures", so the measurement no longer
changes meaning when the polling rate changes.

## Definitions, frozen

Reusing M30's arithmetic unchanged, so a dislocation means the same thing in both nodes:
de-vig each book across its own two sides first, then compare against the **median de-vigged
probability of every OTHER book**, requiring at least 3 peers.

- `edge(t) = consensus(t) / p_raw(t) - 1` -- the return per unit staked at the vigged price.
- A series is `(game, market, side, book)`.
- An **episode** OPENS at the first capture where `edge > 0`, having been `<= 0` (or absent)
  at the previous capture of that series.
- An episode CLOSES at the first later capture where `edge <= 0`.
- **Lifetime** = close time minus open time, in minutes.
- An episode is **RIGHT-CENSORED** if the game commences, or the tape ends, while it is still
  open. Censored episodes are kept and handled as censored, never dropped and never counted
  as though they closed -- dropping them would bias every lifetime downward, which is the
  direction that flatters the "act fast" conclusion.

Episodes are additionally graded, as in M30: **STRONG** if the opinion gap reaches 3pp at any
point while open, otherwise WEAK.

## Inclusion, frozen

1. Pre-game only. In-play is a different process (D151).
2. A capture gap **strictly greater than 12 minutes** inside an episode makes that episode
   UNOBSERVABLE and it is discarded, with the discarded count reported. Capture coverage is
   61% (D154) and the laptop sleeps; an episode straddling a blackout has an unknown lifetime
   and must not be given a fabricated one.
3. Both endpoints must have at least 3 peers.

## SAMPLE GATE -- the primary statistic MUST NOT be computed until this is met

**At least 30 distinct games AND at least 150 episodes, of which at least 40 are STRONG.**

Until the gate opens, this node reports **sample counts only**. This exists to prevent
optional stopping: without it, a coordinator could recompute the survival curve every day and
publish on whichever day the number looked best, which is indistinguishable from choosing the
answer. The gate is a fixed threshold on sample size, not on any property of the result.

At roughly 4 episodes per game and 5 games a day, and with capture coverage at 61%, the gate
is expected to open around **2026-08-27 at the earliest**, later if the machine sleeps.

## Primary statistic

**Median episode lifetime in minutes, Kaplan-Meier, computed separately for STRONG and WEAK
episodes**, with a cluster bootstrap by `game_id`, 2000 draws, seed 20260820, reported as a
95% interval.

## Predictions, committed before computing

- **P1** Median STRONG lifetime is **under 30 minutes**. Cross-book dislocations are widely
  scanned by better-resourced actors than us and should not survive long.
- **P2** STRONG episodes are **shorter-lived than WEAK** ones. A bigger dislocation is more
  visible and should be corrected sooner. If this inverts, the likeliest explanation is not
  that big edges linger but that some books are simply slow to requote at all, and that
  alternative must be checked before P2 is called confirmed.
- **P3** At least 20% of STRONG episodes survive 10 minutes -- the board's refresh interval.
  This is the ACTIONABILITY prediction and it is the one that matters for the product.
- **P4** Lifetime differs by book, with at least one book's median at least twice another's.

## What would make this node's answer worthless

Recorded now so it cannot be rationalised later:

- **Censoring handled wrongly.** If censored episodes are dropped rather than censored, every
  lifetime shrinks and P1/P3 both move in the flattering direction. Kaplan-Meier is specified
  precisely so this is not a judgement call at analysis time.
- **The five-minute grid is a floor on resolution.** Nothing here can distinguish a lifetime
  of one minute from four. Any episode opening and closing within a single interval is
  invisible entirely, so **every lifetime reported is an over-estimate**, and P3 in particular
  is measured optimistically. This bias cannot be removed at this polling rate; it can only
  be stated, and it is stated here.
- **`edge > 0` is measured against peer consensus, not against truth.** An episode is a
  period when one book disagreed with the others, nothing more. If the market is collectively
  wrong, this node cannot see it.
- **Survival is not profit.** A price that stays on the screen was not necessarily takeable,
  in any size, by us. This node measures persistence and makes no executability claim.
