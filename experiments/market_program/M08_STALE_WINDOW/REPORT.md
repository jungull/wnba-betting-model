# M08 — the stale window, and whether this cadence can measure one at all

**PROSPECTIVE MEASUREMENT. A stale window exists only where a fresher cross-book quote was
demonstrably capturable at time T; without that, staleness is an artifact of the observer's own
cadence.**

Preregistration frozen at `1a38e2b70fe6fd882cdde8dfe6a1ec9a88eeeb4fa78a441acd9451c96e7ba128`,
verified by [`s01_stale.py`](s01_stale.py) before anything is computed.

---

## The headline: the gate is closed, and the premise is in doubt

| | |
|---|---|
| episodes found | 250 |
| discarded as unobservable (capture gap > 12 min) | **54 (21.6%)** |
| usable | 196 — 120 closed, 76 right-censored |
| distinct games | **10** |

**Sample gate: 30 games, 150 episodes, 60 resolvable.** Episodes (196) and resolvable (94) are
already met; **games is the sole binding constraint at 10 of 30.** The survival curve was **not**
computed. On the observed game rate the gate should open around the same time as M31's.

## S1 — the resolution floor, and why it is the real finding today

| | |
|---|---|
| episodes **at the floor** (closed within one poll) | **102 (52.0%)** |
| episodes **resolvable** (span 2+ poll intervals) | 94 (48.0%) |

An episode that opens at poll *i* and closes at poll *i+1* has a true duration somewhere in
`(0, 2 × cadence)`. It carries **no duration information at all**. Reporting it as a measured
window would be reporting our own polling rate as though it were the market's behaviour — which
is exactly the failure the node's epistemic status was written to prevent.

**PREREG.md named a falsification condition: if the overwhelming majority of episodes sit at the
floor, this cadence cannot measure stale windows and no median may be reported however the gate
stands. At 52.0% that condition is ACTIVE.** It is not yet decisive — 48% remain resolvable — but
the premise of this node is genuinely in question, and that is a real possible outcome of the
node rather than a failure of it.

### A defect discovered after freezing, recorded and not repaired

**The primary statistic, as preregistered, is biased upward, and I did not see it when I froze
the prereg.**

Restricting the Kaplan-Meier estimate to *resolvable* episodes **conditions on duration**. Every
episode that resolved quickly is excluded by construction, so the surviving sample is the long
ones. The median it yields is therefore an **upper bound on typical staleness, not an estimate of
it** — and the true median is somewhere below it, bounded by how many of the 52% at the floor
were genuinely short rather than merely unobserved.

The prereg is **not** edited — it is hash-frozen, and this programme records defects rather than
repairing them into the record. When the gate opens, the primary must be reported **as an upper
bound with this bias stated**, never as "the typical stale window is N minutes".

## S2 — staleness concentrates, and not randomly

| book | episodes | share |
|---|---|---|
| **mybookieag** | 50 | **25.5%** |
| bovada | 24 | 12.2% |
| williamhill_us | 22 | 11.2% |
| lowvig | 16 | 8.2% |
| betrivers | 16 | 8.2% |
| betonlineag | 14 | 7.1% |
| betus | 14 | 7.1% |
| fanatics | 14 | 7.1% |
| draftkings | 10 | 5.1% |
| fanduel | 8 | 4.1% |
| betmgm | 8 | 4.1% |

One book accounts for a quarter of all staleness, and the major regulated books
(draftkings, fanduel, betmgm) are the **least** stale at 4–5% each. This is a count, not a rate —
it is not normalised by how often each book is quoted, so it must not be read as "mybookieag is
5× slower than fanduel". Normalising it is not preregistered here and is not done.

## S3 — the capture gap tax, again

**21.6% of episodes straddle a capture gap greater than 12 minutes** and were discarded as
unobservable. That is the D154 machine-uptime limit charging this node directly, the same way it
charged M31 (20.5%). It is not a code defect and no cadence change fixes it.

## What this node does not establish

- **No median, no survival curve.** The gate is closed and the primary was not computed.
- **No executability claim.** That a stale line persisted for N minutes says nothing about
  whether it could be taken, at what size, or at what price. That is M21/M22, and nothing here
  licenses an opportunity claim.
- **This is not M31.** M31 measures how long a book's price stays *better than consensus*; M08
  measures how long a book goes *without repricing while peers have*. A book can be dislocated
  because it moved and its peers did not. The two results may not be quoted as each other.
- **Nothing finer than the cadence is knowable**, per M07's resolution floor, which this node
  inherits whole rather than working around.
- **THRESH = 0.02 was frozen before the durations were seen** and is not tuned. No post-hoc
  sensitivity sweep over it may be reported as primary.
