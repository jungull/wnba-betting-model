# M32 — do the quotes that beat consensus actually WIN?

Frozen after `build_quotes.py` printed the frame's **shape only** and before any return, ROI,
win rate or profit figure existed. Known at freezing: 19,559 book-quotes with outcomes, 648
games, 230 game dates, 9 books, seasons 2024–2026, median 4 peers per quote, and the count in
each gap band (10,867 / 5,666 / 2,111 / 915 at 0–1 / 1–2 / 2–3 / 3+ pp).

---

## The question, and why it is the only one that matters

Every profitability number this programme holds is measured **against consensus**. M30/D157
found that a quote sitting 3 percentage points clear of its peers' de-vigged consensus is
"worth +1.44%" — but that means *relative to where the market settled*, not *relative to what
happened*. The board's stale-line lane, the whole opportunity ladder, and the answer given to
the user rest on that.

**Nobody has checked whether those quotes win.** The props archive carries outcomes. This
settles it.

## Universe, frozen

Book-level quotes at the consensus line, in-play excluded, entity-resolved, from
`master_props_historical.csv` via M14's recipe — which is MODEL_VS_MARKET's, which delegates
the vig math to M11 under the preregistered method. Requires **at least 3 peer books**, as M30
did. Outcomes from owned gamelogs via `mvm.load_outcomes()`.

For each quote the benchmark is the **leave-one-out median** of the other books' de-vigged
over-probabilities. Including the book being judged would let a generous book drag its own
benchmark and inflate its apparent edge; M30 used leave-one-out for the same reason.

## Definitions, frozen

- `gap` = peer consensus minus this book's own de-vigged probability, on the side taken.
  Positive means **the book is more generous than its peers**.
- `edge` = `consensus / vigged implied price − 1`: expected return per unit staked **if the peer
  consensus is the fair probability**.
- The side taken is whichever of over/under has the larger `edge`. At most one can be positive.
- **`ret`** = realised return per unit staked: `decimal(price) − 1` if the side won, `−1` if it
  lost. **This is the response.** It is money, not a probability score.

## PRIMARY statistic, frozen

**Mean realised `ret` on quotes with `gap >= 0.03`** — M30's ACT threshold, chosen there and
not re-chosen here — with a **cluster bootstrap by `game_date`, 2,000 draws, seed 20260821**,
reported as a 95% interval.

Also reported, all on the same footing: every quote; `edge > 0`; and the gap bands 1–2pp,
2–3pp, 3pp+. Win rate and mean price alongside ROI in every cell, because an ROI without them
cannot be read.

## Negative control, frozen

Quotes where the book is **STINGY** by 3pp or more — `gap <= −0.03`, the side the peers say is
overpriced. If the mechanism is real this must LOSE, and lose by more than the indiscriminate
baseline. **If the stingy bucket wins, the finding is an artefact and nothing else in this node
may be read.**

## Predictions, committed before computing

- **P1** Betting every quote indiscriminately loses roughly the vig: mean `ret` between −0.08
  and −0.02.
- **P2** The `gap >= 3pp` bucket has **positive** mean `ret`. *This is the claim the programme
  has been implicitly making and has never tested.*
- **P3** ROI rises monotonically across the four gap bands.
- **P4** *(the sceptical one, committed deliberately)* **The 3pp bucket's 95% interval still
  INCLUDES ZERO.** 915 quotes at roughly even money is not enough to establish profitability
  even if the point estimate is positive. If P2 passes and P4 also passes, the honest headline
  is "consistent with a small edge, not established", not "profitable".
- **P5** No single book supplies more than half of the 3pp bucket's total return — the result
  is not one book's pricing quirk.
- **P6** The negative control loses, and loses by more than the indiscriminate baseline.

## What this can NOT establish, whatever it returns

- **It is not a live-executability claim.** The archive holds ONE vendor-asserted snapshot per
  game, a median 1.16 hours before tip, and the vendor's timestamp is unwitnessed (D027). A
  quote in this archive is not a quote we were standing in front of.
- **Prices move.** Nothing here says the price survived to when a bet could be placed. That is
  M31's question and M31's sample gate is still closed.
- **No stake is authorised by any result here.** Execution mode is SHADOW; S42 is untouched
  because no fitted model appears anywhere in this node.
- **2,111 + 915 quotes is a small tail.** Season-level replication is reported but three
  seasons of one league is what it is.
