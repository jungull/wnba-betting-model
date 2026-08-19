# M22_CAPACITY — how much money can each measured opportunity class absorb?

**Coordinator #08, 2026-08-19.** This node was parked as unrunnable because it "requires live
multi-book capture tape that a clean checkout cannot supply." That premise was a consequence of
`D138`: the tape existed, the worktree could not see it. `D146` fixed the access, so the node is
runnable and is run here.

**A capacity figure in this report is an UPPER BOUND under stated assumptions. It is never a
revenue projection**, per this node's own acceptance criteria and `M00`'s
`profitability_standards`. Nothing here says money will be made.

---

## 1. What capacity means, per class

Capacity is not one number. It is bounded by a different thing in each class, so a blended figure
would be meaningless:

| class | what bounds it |
|---|---|
| `TRUE_CROSS_BOOK_ARBITRAGE` | **frequency × size × available depth.** All three are small and they multiply. |
| `PURE_MICROSTRUCTURE` (line shopping) | **your own turnover.** The market imposes no bound; the class is a discount on volume you were already placing. |
| `PROMOTIONAL_VALUE` | **the offer's own posted cap.** Bounded by construction — that is the defining feature of the class. |
| `MIDDLES_AND_DISLOCATIONS` | irrelevant. `D152` measured most as negative expectation; capacity for a losing bet is not a useful quantity. |
| `MODEL_VS_MARKET_VALUE` | zero. `D141`/`D150` measured no edge on any slice. |

## 2. Observed frequency, from the tape

Measured over 16 capture days: **48 distinct games, 3.0 games/day**, roughly 3 two-sided markets
per game, so **~9 pre-game two-sided markets per day** in this league.

That number is the ceiling on everything below. WNBA is a small league with a short season, and no
amount of edge changes how many games exist.

## 3. Arbitrage — bounded at effectively nothing

Combining `D151`'s measured frequency with `M21`'s measured depth:

* arbitrage rate, pre-game: **0.270%** of two-sided markets
* expected occurrences: **0.024/day — one roughly every 41 days**
* observed sizes: median ~0.4%, largest 1.686%
* exchange depth at best price (`M21`, measured on real resting orders): **median $49.01**,
  p25 $25.70, p90 $275.15

| stake available | 0.4% arb | 1.7% arb |
|---|---|---|
| $49 (median depth) | **$0.20** | $0.83 |
| $275 (p90 depth) | $1.10 | $4.68 |

**Upper bound: single-digit dollars per season.** One opportunity every six weeks, worth under a
dollar at typical depth. **This class is not a business.** It is worth scanning for only because
the scanner already exists and costs nothing to run.

## 4. Line shopping — bounded by your turnover, not by the market

`D151` measured the median overround falling from **4.753% at one book to 3.477% taking the best
price on each side**: **1.276 points removed, 26.8% of the vig.**

The market places no cap on this. Capacity equals whatever you were going to stake anyway:

| annual turnover | bound on value |
|---|---|
| $5,000 | $64 |
| $25,000 | $319 |
| $100,000 | $1,276 |

**This is a discount, not income.** It does not generate money; it stops a fixed percentage of
your own money leaking. If you bet nothing, it is worth nothing — which is exactly why it is the
safest thing in this report and also why it can never be a strategy on its own.

## 5. Promotions — the only class with standalone per-unit value

Bounded by the offer's own cap by construction. From the board's valuation model (`D144`), using
the shipped **example** offers:

| offer | modelled EV | bound |
|---|---|---|
| $25 free bet, long price | 40.9% of face | **$10.22** |
| $50 bonus-back | 32.9% | $16.45 |
| $25 odds boost | 22.0% | $5.50 |

**These are the largest per-event figures in this report by two orders of magnitude**, and unlike
arbitrage they recur on the venue's schedule rather than the market's.

**The honest limit on this section:** offer *frequency* is **not measured** — this programme has
never observed a real promotional offer. Any annualised figure would require assuming a rate, and
this node declines to assume one. The per-offer bound is real; the number of offers is unknown.

## 6. The ranking that follows

By upper bound on value, from the measured classes:

1. **Promotions** — largest per unit, recurring, bounded by the offer cap. **Frequency unmeasured.**
2. **Line shopping** — proportional to your own turnover, ~1.28% of it. Certain, mechanical.
3. **Arbitrage** — single-digit dollars per season. Effectively nil.
4. **Middles** — mostly negative (`D152`). Not a capacity question.
5. **Model edge** — zero (`D141`, `D150`).

**The two classes worth anything require no forecasting ability whatsoever.** The one this
programme spent ~58 screens building toward is last.

## 7. Sensitivity — what would move these bounds

| assumption | effect if wrong |
|---|---|
| **Sportsbook limits are UNMEASURED** (`M21` marked ABSENT, correctly). Exchange depth is used as the only measured proxy. | If sportsbook limits are far larger than exchange depth, arbitrage capacity rises — but frequency (one per 41 days) still caps it near nothing. |
| Arbitrage rate 0.270% measured on a mostly **hourly** grid | A faster grid should find MORE. `D151` records this as a lower bound; today's cadence change is what will test it. |
| 3.0 games/day is in-season WNBA | Out of season, every class goes to zero. |
| Promo frequency assumed nowhere | The largest class is also the least measured. |
| Vig of 4.753% and its 26.8% reduction | Measured over 2,591 markets. The most solid number in this report. |

## 8. What this node does NOT establish

* **No realised-profit projection is made**, and none may be derived from this report.
* Sportsbook maximum stakes remain **ABSENT**, not estimated — `M21` checked the schema and the
  codebase and found no such field. Determining them requires the venues' own rules, which is a
  `USER_REQUIRED` matter, not a measurement.
* Execution feasibility is untouched: `EXECUTION_FEASIBLE` on the `M00` ladder needs measured
  latency between decision and fill, which this node does not supply.
* Nothing here authorises a stake, a venue, or a transition above `SHADOW`.
