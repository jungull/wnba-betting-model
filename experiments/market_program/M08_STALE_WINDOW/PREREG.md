# M08 STALE WINDOW -- preregistration

**PROSPECTIVE MEASUREMENT. A stale window exists only where a fresher cross-book quote was
demonstrably capturable at time T; without that, staleness is an artifact of the observer's own
cadence.**

Frozen before the primary statistic is computed. At the time of freezing the five-minute era
holds **168 closed stale episodes over 10 distinct games**, of which **90 (53.6%) sit at the
resolution floor**. Those three counts, and nothing else, have been computed: no duration, no
survival estimate, no window statistic of any kind.

## The question

M07 measured *which* book moves first and returned a hard limit: within a poll, ordering is
`INDISTINGUISHABLE_AT_GRID`, and any ordering is resolvable **no finer than the poll-to-poll
cadence**. M08 asks the next question -- when a book is left behind, **how long does it stay
behind** -- and inherits that limit whole.

This matters for one reason only. If a stale line typically persists for many minutes, an
observer polling every five minutes can see it. If it typically resolves inside one poll
interval, then nothing an observer at this cadence reports about its duration is a fact about
the market.

## What is NOT being asked, so this is not confused with M31

M31 measures **dislocation persistence**: how long a book's price stays *better than the
de-vigged peer consensus*. That is a statement about price level, and a book can be dislocated
because **it** moved while its peers did not.

M08 measures **staleness**: how long a book goes *without repricing while its peers have
repriced*. That is a statement about update behaviour. The two overlap but are not the same
event, and neither result may be quoted as the other.

## Definitions, frozen

* A **series** is `(game_id, market, side)`, as in M30/M31, on the `panel.py` loader unchanged.
* The **peer consensus** for book `b` is the median de-vigged probability across every book
  except `b`, requiring at least 3 peers (`panel.consensus_excluding`, unchanged).
* Book `b` **reprices** at poll `t` when its de-vigged probability differs from its own previous
  observed value.
* A **stale episode OPENS** at the first poll where, since `b` last repriced, the peer consensus
  has moved by at least **THRESH = 0.02** in de-vigged probability, and `b` has not repriced.
* A stale episode **CLOSES** at the first later poll where `b` reprices.
* An episode is **RIGHT-CENSORED** if the game commences, or the tape ends, while it is still
  open. Censored episodes are kept and handled as censored -- never dropped, never counted as
  though they closed.

### The resolution floor, which governs every duration this node reports

An episode that opens at poll `i` and closes at poll `i+1` has a true duration somewhere in
`(0, 2 x cadence)`. It is **AT THE FLOOR** and carries no duration information.

* Episodes at the floor are **counted and reported**, never silently dropped.
* They are **excluded from the duration estimate**, because including them would report the
  observer's cadence as if it were the market's behaviour.
* Every duration is stated as a **bound under the capture cadence**, carrying the D023
  amendment-4 timestamp-uncertainty and vendor-latency terms.

**A capture gap strictly greater than 12 minutes inside an episode makes that episode
UNOBSERVABLE**, exactly as in M31: coverage is 61% (D154) and an episode straddling a blackout
has an unknown lifetime. Unobservable episodes are discarded from the estimate and reported as a
count.

## SAMPLE GATE -- the primary statistic MUST NOT be computed until this is met

**At least 30 distinct games AND at least 150 episodes, of which at least 60 are RESOLVABLE
(span 2 or more poll intervals).**

Until the gate opens this node reports **sample counts and the resolution-floor analysis only**.
The gate is a fixed threshold on sample size, not on any property of the result. It exists to
stop the curve being recomputed daily and published on the day it looks best, which is choosing
an answer rather than measuring one.

30 games is chosen for the same reason as M31's gate, on the same tape: the primary carries a
game-clustered bootstrap, and 10 clusters cannot support one.

## Primary statistic, once the gate opens

**Median stale-episode lifetime in minutes, Kaplan-Meier, computed over RESOLVABLE episodes
only**, with a cluster bootstrap by `game_id`, 2000 draws, seed 20260822, reported as a point
estimate with a 95% interval.

## Secondary, preregistered

* **S1** The share of episodes at the resolution floor. This is computable now and is reported
  now, because it is a statement about the observer rather than about the market.
* **S2** Per-book episode counts, to see whether staleness concentrates in particular books.
* **S3** The share of episodes that are unobservable due to capture gaps.

## What would falsify the premise of this node

If the overwhelming majority of episodes sit at the resolution floor, then **the honest finding
is that this cadence cannot measure stale windows at all**, and no median may be reported however
the gate stands. That is a real possible outcome of this node and is not a failure of it.

## Known defects, recorded not repaired

* **`edge`-free by construction.** This node never uses the M30/M31 `edge` quantity, so its
  episodes are not comparable to M31's and no cross-citation is licensed.
* **THRESH = 0.02 is a judgement.** It is frozen here before the durations are seen. It is not
  tuned, and no sensitivity sweep over it may be added after the fact and reported as primary.
* **De-vigged probability is a derived quantity**, and its vig treatment is inherited from
  `panel.py` rather than re-derived. A defect there propagates here.
* **No executability claim.** That a stale line existed for N minutes says nothing about whether
  it could have been taken, at what size, or at what price. Execution feasibility is M21/M22, and
  nothing in this node licenses an opportunity claim.
