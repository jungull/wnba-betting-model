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
| 2 · Subsidised | `PROMOTIONAL_VALUE` | **The offer's cap** | The venue publishes a hard maximum. With positive EV per unit, value is maximised at that cap — but the number is the *venue's*, not our sizing policy, so it is tagged `OFFER_CAP` and still carries a sizing gate for any amount below it. |
| 3 · Bounded risk | `MIDDLES_AND_DISLOCATIONS` | **No — gated** | Sizing needs a hit probability this node has not measured and a staking policy that is gated: `M24_STAKING` ← `M23_SHADOW_TRADING` ← `M22_CAPACITY`. Equal-stake figures are shown to illustrate payoff shape only. |
| 4 · Informational | `PURE_MICROSTRUCTURE` (dispersion) | No | Line shopping is not a position. |
| Dark | three further lanes | No | Built and switched off; see §5. |

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
*(Promotions were the fourth dark lane. They are now **live** — see §5A.)*

## 5A. Promotions — the taxonomy amended, and why not in place

The user named promotional specials as a legitimate reason to bet. M00's amendment procedure
permits exactly this: *"amended only by a ledgered decision citing user authorization"*. The
user's instruction **is** that authorization, so it is recorded verbatim rather than paraphrased —
a paraphrase of an authorization is not an authorization — and the class is added under `D144`.

**The amendment is additive, in a sidecar, and the base file is untouched.** That is not
squeamishness. `TAXONOMY.json`'s sha256 is **pinned in nine places across six passed nodes**:
`M11_CONSENSUS_MODEL/consensus.py:59` and `M25_MARKET_UI_FIXTURES/contract_constants.py:29` assert
it *at import time and raise rather than render*; `M11_CONSENSUS_MODEL/TESTS.py:291` asserts it in
a suite; and `M01`, `M02`, `M04` record it as verification receipts that are correct as records of
their own date. Editing the base bytes would have broken two importers immediately, falsified one
test suite, and silently invalidated three historical receipts. `TAXONOMY_AMENDMENTS.json` adds the
seventh class beside the six and preserves every one of those pins.

**The cost is stated in the amendment file itself**: a reader of `TAXONOMY.json` alone now sees six
classes and will not know a seventh exists. That is a real defect of this approach, mitigated by
`contract.py`, which composes base + amendments, verifies the base hash still matches what the
amendment was written against, and **fails loudly rather than rendering** if they disagree.

### Why promotions are not behind the model gate

A promotion is valued against the **de-vigged cross-book consensus probability, never against our
own model.** That is deliberate. Routing promo valuation through our model would put it behind
`S42` and — worse — would make a subsidy anyone can capture look as though it depended on an edge
we have measured ourselves *not* to have (`D141`). The venue discloses the subsidy. No
informational advantage is required, and none is claimed.

De-vigging happens **per book before averaging**. The other order bakes an average margin into the
result and biases every promo valuation downward.

### What is computed

| Kind | Formula | Note |
|---|---|---|
| `odds_boost` | `p · d_boosted − 1` | the price itself improves |
| `profit_boost` | `p · (1 + (d−1)(1+b)) − 1` | profit multiplied, stake not |
| `free_bet` | `p · (d−1)` on **face value** | baseline is zero: none of your money was at risk |
| `bonus_back` | `p·(d−1) + (1−p)·(recovery−1)` | `recovery` is a judgement about *your* conversion, not a market fact |

Each row also reports the **uplift** — promo EV minus the EV of the same wager unpromoted — so the
promotion's own contribution is separated from whether the underlying bet was any good.

A property worth knowing, and asserted in the suite: **free bets are worth more at longer prices**,
because the unreturned stake costs relatively less. Valuing one at a short price understates the
token.

### What is not computed

Sizing below the offer's cap. Whether the stated terms are actually realisable — that is an
`EXECUTION_FEASIBLE` question this node does not answer. And nothing enrols in anything: offers are
entered by the user in `promos.json`, the programme does not scrape them, and enrolment is
`USER_REQUIRED` like every other account action. **The shipped `promos.json` contains four
clearly-labelled EXAMPLE offers**, marked as examples on the board itself, so the lane renders and
the arithmetic is inspectable before any real offer is entered.

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

`python TESTS.py` → **120/120 PASS**, exit 0. Two failures were found by the suite during the
build, and both were worth having:

1. A wrong test expectation, not wrong code — `implied_prob(-110)` is `110/210`, not `100/210`.
2. **A genuine discipline slip by the author.** The suite asserts that only deterministic
   sizing may carry a stake number. Adding promotions violated it: a promo is probabilistic
   and was given a number. The cap really is the venue's rather than ours — but blurring
   "the venue's ceiling" and "our recommended size" into one field is exactly the drift the
   invariant exists to prevent. **The data model was fixed rather than the test weakened**:
   stakes now carry an explicit `kind` (`DETERMINISTIC_SPLIT` vs `OFFER_CAP`), only
   arbitrage may use the former, and a promo showing a number must ALSO carry a sizing gate.

## 9. Files

| File | Role |
|---|---|
| `oddsmath.py` | Pure price arithmetic; arbitrage and middle math with settlement rules |
| `contract.py` | Composes the M00 taxonomy with its amendments and verifies both |
| `promos.py` | Promotion valuation against de-vigged cross-book consensus |
| `promos.json` | **Your offers.** Ships with four labelled examples |
| `feed.py` | Data-root resolution, snapshot loading, quote normalisation, cadence measurement |
| `board.py` | Detectors, classification, frozen ranking, stake gating |
| `render.py` | Self-contained HTML dashboard |
| `TESTS.py` | 120 checks, weighted toward the arithmetic |
| `board.html` / `board.json` | Rendered output for the snapshot named in the footer |

Run: `python render.py` → writes `board.html` and `board.json` from the newest snapshot.

## 10. What this node does NOT do

It does not claim any opportunity is executable. It does not size anything probabilistic below
an offer's own cap. It does not evaluate our model against the market. It does not detect stale
lines. It does not scrape, create or enrol in any promotion. It places no orders and never will. Each of those is either a named gate above or a
measurement this node has not made — and none of them is quietly missing.
