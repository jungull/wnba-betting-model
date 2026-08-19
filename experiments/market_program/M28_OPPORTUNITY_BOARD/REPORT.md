# M28_OPPORTUNITY_BOARD — one ranked board for every reason to bet

**Built by Coordinator #08, 2026-08-18/19, on direct user instruction.** The user extended the
product goal: *"every WNBA bet from every platform in one dashboard ranked by recommendation and
a suggested amount"*, explicitly noting that a bet does not have to be justified by our model
beating the line — **arbitrage on slower-moving markets, or a special/promo, are acceptable
reasons** — and asked for everything buildable that is not gated by something else.

This node is that board. It runs against **live capture**, not fixtures.

---

## 1. What was already here, and what was actually missing

The analytical pieces existed and had passed: `M09_TRUE_ARB_SCANNER`, `M10_MIDDLES`,
`M11_CONSENSUS_MODEL`, `M21_EXECUTION_REALISM`, `M25_MARKET_UI_FIXTURES`, and the product-lane
shells `U10`–`U13`. **Nothing unified them.** There was no single surface that took every
opportunity class, ranked them against each other, and answered *what would you bet, in what
order, and how much*. That gap is this node's entire scope, and it is why this is an integration
node rather than a new detector.

## 2. What it does

Reads the newest live odds snapshot, normalises every quote, and emits one ranked board:

| Tier | Class | Stake shown? | Why |
|---|---|---|---|
| 1 · Locked | `TRUE_CROSS_BOOK_ARBITRAGE` | **Yes, exact** | The split follows from the prices and the bankroll. No probability estimate is involved anywhere, so the number is arithmetic and is defensible. |
| 2 · Bounded risk | `MIDDLES_AND_DISLOCATIONS` | **No — gated** | Sizing needs a hit probability this node has not measured and a staking policy that is gated: `M24_STAKING` ← `M23_SHADOW_TRADING` ← `M22_CAPACITY`. Equal-stake figures are shown to illustrate payoff shape only. |
| 3 · Informational | `PURE_MICROSTRUCTURE` (dispersion) | No | Line shopping is not a position. |
| Dark | four further lanes | No | Built and switched off; see §5. |

Ranking is frozen in code: tier first, then a score within tier. Reordering is a visible code
change, never a judgement made at render time. Middles rank by **window width per unit of cost**,
not raw width — ranking on width alone rewards expensive straddles.

## 3. The arithmetic, and the one trap in it

`oddsmath.py` is the only module permitted to carry a hard claim, because an arbitrage is a
statement about numbers rather than a forecast. The trap it exists to avoid:

> The tempting implementation — *implied probabilities sum below 1, therefore arbitrage* — is
> **wrong on whole-number totals and spreads**, and wrong in the direction that loses money quietly.

A whole-number line can land exactly on the number and **push**, returning the stake. A
combination that is positive on both win branches but nets **zero** on the push branch is not
locked-positive, and M00 defines arbitrage as locked positive in *every* settlement outcome. So
`arb_two_way` takes a `push_possible` flag, evaluates the push branch explicitly, and **rejects**
such a combination — reporting it as a dislocation with the reason stated. Stakes are also
re-checked *after* rounding to a real currency increment, because rounding can move a marginal
combination across zero.

`TESTS.py` covers this directly: the same prices are asserted to be **rejected** on a 170.0 line
and **accepted** on a 170.5 line.

## 4. The honesty constraint that shapes the whole product

**Capture is on an hourly grid** (measured: median gap 3600 s, with an overnight pause). A locked
combination detected here describes a price that existed somewhere inside that window. It is
**not** a claim that you could still take it, and the board says so in a banner above every result.

Under M00 no executability claim is permitted without the `EXECUTION_FEASIBLE` rung, which needs
measured limits, latency and slippage. Every opportunity therefore carries
`executability_claimed = False`, and the node never sets it otherwise.

**This is the single highest-value upgrade to the product**: at hourly cadence, true arbitrage
detection is effectively retrospective. Sub-minute per-book polling is what would make tier 1
actionable, and `M03_CAPTURE_UPGRADE` / `M27_PER_BOOK_POLLING` already passed — the capability
exists and is not running at the cadence the product needs.

## 5. What is deliberately dark, and why

A board that silently omits a category is indistinguishable from one that found nothing there, so
each dark lane is rendered with its blocking gate named:

* **Our model vs the line** — `S42_ADOPTION_DECISION` (the user's) plus `D141`, which measured the
  player-points model at 5.32 MAE against the de-vigged market's 4.90 on the population books
  price, adding nothing material in combination. **There is no measured edge to show.**
* **Stale lines after news** — `M08_STALE_WINDOW`, parked. A line is only stale against a fresher
  quote demonstrably capturable at the same moment; on an hourly grid that comparison cannot be
  made, so any staleness shown would be an artifact of our own cadence.
* **Vendor projections** — `M02B_VENDOR_PURCHASE_DECISION`, the user's alone.
* **Boosts, specials and promos** — **the user asked for these and they are not in the contract.**
  M00's `opportunity_taxonomy` has six classes and promotional value is not one of them. The
  arithmetic is trivial, but adding a seventh class is a contract amendment that follows M00's own
  amendment procedure; a rendering node must not mint a taxonomy class. **The lane is scaffolded
  and stays dark until the class exists.** This is the one part of the user's request that is
  blocked by something, and the block is procedural rather than technical.

## 6. Safety posture

Execution mode is fixed at **`SHADOW`** — D024's default and the only mode this node will ever
operate in. It generates flags; **it places nothing, holds no credentials and contacts no venue.**
Every transition above SHADOW is `USER_REQUIRED`, as are staking changes, deposits and any order.
Nothing in this node can be configured into placing a wager.

## 7. Data root — and a D138 defect fixed in passing

`feed.resolve_data_root()` resolves the capture directory explicitly and **fails loudly** when it
cannot find one, listing every path it tried. This matters because `D138` found that the research
worktree cannot see gitignored data directories, so every screen ran blind to data the live
pipeline reads daily — **an environmental absence recorded as a repository fact.** This node
resolves via a parent climb to the main checkout and prints which root it used in the page footer,
so "which data was this built from" is always answerable.

## 8. Verified state at build time

Two live snapshots were exercised, roughly 18 hours apart:

| Snapshot | Games | Books | Quotes | Locked | Middles | Dispersion |
|---|---|---|---|---|---|---|
| `20260818T210003Z` | 6 | 11 | 374 | **0** | 8 | 12 |
| `20260819T140003Z` | — | — | 258 | **0** | 8 | 5 |

**Zero locked arbitrage in both.** That is the expected and correct result on eleven mainstream US
books at hourly cadence: true arbitrage is rare, brief, and rarer still on a coarse grid. The
detector is proven live by a manufactured fixture in `TESTS.py`, not by a real hit.

`python TESTS.py` → **69/69 PASS**, exit 0. One test failure was found and fixed during the build:
the expectation, not the code — `implied_prob(-110)` is `110/210`, not `100/210`.

## 9. Files

| File | Role |
|---|---|
| `oddsmath.py` | Pure price arithmetic; arbitrage and middle math with settlement rules |
| `feed.py` | Data-root resolution, snapshot loading, quote normalisation, cadence measurement |
| `board.py` | Detectors, classification, frozen ranking, stake gating |
| `render.py` | Self-contained HTML dashboard |
| `TESTS.py` | 69 checks, weighted toward the arithmetic |
| `board.html` / `board.json` | Rendered output for the snapshot named in the footer |

Run: `python render.py` → writes `board.html` and `board.json` from the newest snapshot.

## 10. What this node does NOT do

It does not claim any opportunity is executable. It does not size anything probabilistic. It does
not evaluate our model against the market. It does not detect stale lines. It does not price
promos. It places no orders and never will. Each of those is either a named gate above or a
measurement this node has not made — and none of them is quietly missing.
