# M29 PRICE LEADERSHIP -- report

**Prereg** `895d004fceaf3c3f64bc0d2f04e581520c284925d2af089672b8e5f2d0371f87` (frozen before
any statistic). **Tape pinned at** `2026-08-19T23:05:00Z`. **No game outcome is read, joined,
plotted or described anywhere in this node** -- it studies how prices move relative to each
other, never whether they were right, so there is no result that could leak the holdout.

**Read `DEFECTS.md` before quoting anything here.** The preregistered primary statistic came
back degenerate and is not evaluated. Everything below the first section is post-hoc.

---

## The question

The opportunity board flags books whose prices disagree with their peers, and labels them
"stale by design" because nobody had measured what the disagreement is worth. Two things
had to be established:

1. When a book disagrees with its peers, **who moves?** If the outlier is dragged back, its
   price was a transient and taking the generous side of it captured closing-line value. If
   the peers move to it instead, the outlier was informed and taking the other side is a trap.
2. Even if the outlier reverts, **does that beat the vig you pay to capture it?**

---

## 1. The preregistered test is NOT EVALUATED

The frozen statistic was a median. It returned 0.000 at every threshold, because over an
hourly horizon **65.8% of dislocated books do not move at all** and 32.9% of observations
have neither side moving. A median over a point mass that large reports the point mass.

**P1, P2 and P3 are not evaluated.** `s01` and its degenerate `FINDINGS.json` are kept
exactly as frozen rather than deleted. See DEFECT 1.

---

## 2. Who moves: the outlier, essentially entirely (post-hoc)

Primary threshold, gaps of at least 1.5 percentage points of de-vigged probability, n=1,422
over 47 games, cluster-bootstrapped by game:

| | mean | 95% CI |
|---|---|---|
| Initial gap `\|g0\|` | 1.953 pp | [1.898, 2.008] |
| Gap one horizon later `\|g1\|` | 1.461 pp | [1.380, 1.534] |
| **Gap shrinkage** | **0.491 pp** | **[0.426, 0.574]** |
| ...contributed by the **book** moving | 0.479 pp | [0.352, 0.684] |
| ...contributed by **consensus** moving | 0.131 pp | [-0.047, 0.235] |

**About a quarter of a dislocation closes per hour, and the outlier does essentially all of
the moving.** Consensus movement toward the outlier is not distinguishable from zero.

**P4 is REFUTED. No book leads.** Every book's consensus-share sits in a narrow band around
+0.1 and betmgm's is negative. There is no informed book here that the others follow; there
is a consensus, and there are books that wander from it and come back.

The mechanism is *not* established -- discrete odds mean an extreme quote has more room to
move inward than outward, so some of this is arithmetic rather than information (DEFECT 3).
For a bettor the mechanism does not matter, because the closing-line value is the same either
way. For a claim about which books are smart it would matter, and no such claim is made.

---

## 3. Whether it pays: the threshold is about 2pp, and it is thin (post-hoc)

The test charges the full vig of the book actually being bet and credits us with no
forecasting skill of our own: bet side S at book *b* at its **vigged** price, ask what the
other books' de-vigged median says S is worth, and take the ratio.

| | 2026 live (48 games) | 2025-26 hist (411 games) |
|---|---|---|
| Quotes that beat their peers' consensus | **1.18%** | **1.18%** |
| Mean overround per book/market | 4.635% | 4.702% |
| Every pre-game quote | -4.427% | -4.486% |
| Best price available on each side | -2.045% | -2.557% |
| Book generous by >= 1.0pp | -1.755% | -1.817% |
| Book generous by >= 1.5pp | -0.633% | -0.622% |
| Book generous by >= 2.0pp | +0.024% *(CI spans 0)* | +0.220% *(CI spans 0)* |
| **Book generous by >= 3.0pp** | **+1.436%** | **+2.744%** |

The replication was reserved by the prereg and not consulted until the live headline was
written down. **It is unusually tight**: the fraction of quotes beating consensus agrees to
two decimal places on independent samples, and the 1.5pp bucket agrees to a hundredth of a
percent (-0.633 vs -0.622).

**Three things follow.**

- **Betting blind loses 4.4-4.5% a stake.** That is the hold, and it is nearly identical
  across h2h, spreads and totals -- no market is softer than the others.
- **Line shopping is worth about half of it and still loses.** Always taking the best of 11
  books moves -4.43% to -2.05%. Shopping is necessary and is nowhere near sufficient.
- **The edge threshold is a dislocation of about 2 percentage points of opinion.** Below it
  you lose; at it you break even; above 3pp you clear 1-3%.

### How often that actually happens

Collapsing repeated observations of the same dislocation to distinct opportunities:

| Dislocation | live: per game | hist: per game | mean edge (live / hist) |
|---|---|---|---|
| >= 1.5pp | 8.73 | 2.81 | -0.33% / -0.44% |
| >= 2.0pp | 3.58 | 1.06 | +0.61% / +0.34% |
| **>= 3.0pp** | **0.46** | **0.13** | **+1.08% / +2.81%** |

At >= 2.0pp the **median** distinct opportunity is +0.000% (live) and -0.266% (hist) -- the
positive mean is carried by a tail, so that bucket is not reliably positive bet by bet. Only
the >= 3.0pp bucket is positive at both the mean and the median.

**Order of magnitude.** A ~200-game season at 0.13-0.46 qualifying dislocations per game is
roughly **26 to 92 bets a season at +1% to +3%**. On $100 stakes that is $26-$260 a season.
This sits alongside D153, which bounded arbitrage at single-digit dollars a season: the same
verdict, one rung less severe.

---

## What this changes

1. **The board's dispersion flags now have a defensible threshold rather than a shrug.** A
   dislocation under 2pp is not an opportunity and should not be presented as one; 3pp is
   where it becomes worth acting on. This is measured, replicated, and free of any model of
   ours.
2. **"Beat the market with a better forecast" is not the only route, and is not the cheapest.**
   Every number here is earned from books disagreeing with each other. No scoring model is
   involved, so none of it is exposed to S42 or to D141/D150's finding that our model trails
   the market.
3. **It also bounds the prize.** The tightness of the replication is what makes this
   credible, and what it establishes is a small edge, rarely available.

## What this does NOT establish

- **Nothing about truth.** Consensus is the attractor, not the referee. Every edge figure is
  measured against the other books' opinion; if the whole market is wrong about something,
  this node cannot see it and would score the correct outlier as a mistake.
- **Nothing about executability.** No claim is made that these prices were takeable in the
  size implied, or takeable at all. The board remains in SHADOW.
- **Nothing about the last hour before tip-off**, where the biggest moves are expected. The
  horizon here is "about an hour", on the hourly tape only (DEFECT 5).
