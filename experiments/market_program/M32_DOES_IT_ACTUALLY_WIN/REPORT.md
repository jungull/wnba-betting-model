# M32 — do the quotes that beat consensus actually win?

**Prereg** `22edafa5d230a817e4c468b9d8ff5920b002481e259c7b4651376529c17412e1`, frozen after the
frame's shape and before any return existed. 19,559 book-quotes with realised outcomes, 648
games, 230 game dates, 9 books, seasons 2024–2026.

---

## The answer: NO. The one candidate strategy loses money, significantly.

| bucket | n | realised ROI | 95% CI | win rate | mean price |
|---|---|---|---|---|---|
| every quote, indiscriminately | 19,559 | **−4.97%** | [−5.88, −3.96] | 50.2% | −72.3 |
| **beats peer consensus (edge > 0)** | 570 | **−8.99%** | [−15.53, −1.77] | 45.3% | +27.7 |
| gap 0–1pp | 10,867 | −5.56% | [−7.46, −3.67] | 50.5% | −90.7 |
| gap 1–2pp | 5,666 | −4.25% | [−6.20, −2.43] | 50.2% | −63.0 |
| gap 2–3pp | 2,111 | −2.94% | [−6.63, +0.77] | 50.0% | −34.7 |
| **gap ≥ 3pp — M30's ACT threshold** | **915** | **−7.21%** | **[−12.93, −1.73]** | **47.2%** | **+1.8** |

**The threshold this programme was about to act on loses 7.2 cents per dollar staked, and its
confidence interval excludes zero.** It is not unproven. It is measurably losing, and it loses
*worse* than betting at random.

Selecting on "beats the de-vigged consensus of other books" is worse still: **−8.99%**, nearly
double the vig.

## Predictions, scored

| | prediction | result |
|---|---|---|
| **P1** | betting everything loses roughly the vig | **PASS** — −4.97%, and this is what validates the pipeline |
| **P2** | the 3pp bucket has positive realised return | **FAIL** — −7.21% |
| **P3** | ROI rises monotonically across gap bands | **FAIL** — −5.56, −4.25, −2.94, **−7.21** |
| **P4** | its interval still includes zero *(underpowered)* | **FAIL** — it excludes zero, on the losing side |
| **P5** | no single book supplies >50% of the return | **PASS** — largest share 43% |
| **P6** | the control loses, and by more than baseline | **PASS**, but see below — it passes in a way that damns the thesis |

## Why it fails, and it is visible in one column

Look at **mean price**. Overall it is −72.3; at gap ≥ 3pp it is **+1.8**.

Selecting quotes where a book is generous relative to its peers is, in practice, **selecting
plus-money longshot sides**. Those sides win 47.2% of the time at roughly even money, which is
a loss. The consensus said they were underpriced. The outcomes said they were not.

## The control inverts the thesis

The preregistered control was unbuildable (DEFECT 1). The control that answers the same
question is **the opposite side of the very same quotes** — the side the peers call overpriced:

| | ROI | win rate |
|---|---|---|
| the "edge" side (gap ≥ 3pp) | −7.21% | 47.2% |
| **the opposite side of the same quotes** | **−6.04%** | 52.8% |

P6 passes on its literal wording — the control loses more than the indiscriminate baseline. But
the comparison that matters is control against *primary*, and **the side the consensus calls
overpriced did BETTER than the side it calls underpriced.** Both lose, because you pay vig
either way. The consensus signal points the wrong way.

## What this overturns

**D157 said a ≥3pp dislocation is "worth +1.44% live and +2.74% replicated". That number is
against CONSENSUS. Against OUTCOMES the same selection returns −7.21%.**

Both measurements are correct and they are measuring different things. A quote 3pp clear of its
peers really does revert toward them — M30 measured that on 121,000 quotes and it replicated.
But reverting toward consensus is not the same as being right, and this node is the first time
the programme has checked the second thing.

**The coordinator told the user this was "the only positive-expectation route measured" and
sized it at 26–92 bets a season at +1% to +3%. That was wrong**, and it was wrong in the
specific way the caveat attached to it warned about — "measured against consensus, not truth" —
which is not much of a defence, because the caveat was carried as boilerplate rather than
treated as an open question until now.

## So: is there a profitable strategy yet?

**No, and this closes the last candidate.** The full ledger of what has been measured:

- **Arbitrage** — bounded at single-digit dollars a season (D153).
- **Line shopping** — removes 24.3% of the vig and still returns −2.05% (D155/D157). Necessary,
  nowhere near sufficient.
- **Middles** — negative expectation at the windows actually observed; the push branch is now
  priced and does not rescue them (D156).
- **Model versus market** — the model loses, and the cold-start repair did not narrow it
  (D141, D150, D169).
- **Consensus dislocation** — **this node. −7.21%.**
- **Promotions** — the only thing never measured, because no real offer has been entered. It is
  now the *only* untested route left.

## What this does NOT establish

- **Not a live-executability claim in either direction.** One vendor-asserted snapshot per game,
  median 1.16 hours pre-tip, timestamp unwitnessed (D027).
- **It does not say the market is unbeatable.** It says *this signal, on this archive, at this
  snapshot* loses. A different signal, a faster feed, or closing-line data could say otherwise.
- **915 quotes across 3 seasons of one league.** The interval excludes zero, but the sample is
  a tail of a tail.
- **No stake is authorised by anything here.** SHADOW; S42 untouched — no fitted model appears
  in this node.
