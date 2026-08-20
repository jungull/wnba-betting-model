# M31 DISLOCATION PERSISTENCE -- report

**THIS NODE HAS NO ANSWER YET, BY DESIGN.** The analysis is frozen and implemented; the data
is not there. The sample gate is closed and the survival curve has not been computed.

**Prereg** `51fc14ff79821bdbfe3569145dd517d5433f1defbef515380bb6b37653fbcb76`, frozen before
the data required to answer the question existed. **No game outcome is read anywhere.**

---

## The question

M30/D157 found that a book out of line with its peers reverts to them, and that a
dislocation of about 3 percentage points is where the return turns positive. It said nothing
about **how long such a price stays on the screen**, and that is what decides whether any of
it is reachable.

The board refreshes every ten minutes. If a 3pp dislocation typically lives half an hour, the
board can catch it. **If it typically lives five minutes, the board can never show one in
time**, and no amount of ranking or presentation fixes that. The answer would then be a fact
about our polling rate, not about the market.

## Why there is no answer yet

The five-minute capture only began on 2026-08-19. As of the last capture:

| | have | need |
|---|---|---|
| distinct games | 5 | 30 |
| episodes | 38 | 150 |
| STRONG episodes (gap reached 3pp) | 3 | 40 |

Three strong episodes cannot support a survival curve, and a cluster bootstrap over five
games is not an interval, it is a decoration.

## The gate, and why it is in the code rather than in a person's head

`s01_persistence.py` **refuses to compute the primary** until the thresholds are met. This is
not caution, it is a specific defence against a specific failure: without it, the curve could
be recomputed every day and published on whichever day it looked best. That is choosing the
answer while appearing to measure it, and it leaves no trace. A fixed threshold on sample
size, decided before any data existed, removes the opportunity.

Expected to open around **2026-08-27** at the earliest, at roughly 4 episodes per game and 5
games a day. Later if the machine sleeps -- capture coverage is 61% (D154) and the binding
constraint is whether the laptop is awake, not how fast it polls.

Nothing needs to be done to advance it. Capture is already running. Re-run
`python s01_persistence.py` and it will either say "not yet" or produce the answer.

## What is already fixed, before any result

- **The horizon is defined in clock time**, not in "consecutive captures". This is M30's
  DEFECT 5, which tied that study's clock to the polling rate and meant the faster tape
  contributed nothing to it. It cannot recur here.
- **Right-censoring is specified, not left to analysis-time judgement.** An episode still
  open when the game starts or the tape ends is censored, not dropped. Dropping them shortens
  every lifetime, which is the direction that flatters the "act fast" story.
- **Episodes straddling a capture gap over 12 minutes are discarded, and counted.** 10 were
  discarded so far. An episode spanning a blackout has an unknown lifetime and must not be
  given a fabricated one.

## What this node will not be able to say, however much data arrives

- **Nothing below five minutes.** The grid is the resolution floor. An episode that opens and
  closes inside one interval is invisible, so **every lifetime reported will be an
  over-estimate** and the actionability prediction is measured optimistically.
- **Nothing about truth.** An episode is a period when one book disagreed with the others.
- **Nothing about executability.** A price that stayed on the screen was not necessarily
  takeable, in size, by us.
