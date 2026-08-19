# M29 PRICE LEADERSHIP -- preregistration

Frozen before any statistic in this node was computed. The panel builder (`panel.py`) had
been run and reports only shape: 59,302 rows, 2,080 series, 203 captures, 11 books. No gap,
attribution, reversion or leadership number had been calculated when this file was hashed.

## The question

When one book's de-vigged price disagrees with its peers, **who moves?** Either the
disagreeing book is dragged back to the consensus (its price was a transient, and taking the
better side of it was a gift), or the consensus moves to the disagreeing book (the book was
informed, and taking the other side of it was a trap).

This decides what the board's dispersion flags are worth. The board currently labels them
"stale by design" and refuses to claim executability. That is honest but it is not an answer.

## Why this is admissible against the partition

**No game outcome is read, joined, plotted or described in this node.** It studies how prices
move relative to one another, not whether they were right. There is no result to leak because
correctness is never evaluated. This is the same admissibility D147 established when the
spread-line dispersion term was taken from holdout-era tape.

## Data

Live capture family (`live_*.json`, 2026-07-30 to 2026-08-19, 203 captures, 11 books).
The `hist_*` 2025 family is reserved as a REPLICATION set and is not consulted until the live
headline is computed and written down.

## Definitions, frozen

For a series `(game, market, side)` at capture `t`, for book `b`:

- `p_b(t)` = implied probability of book b's price, de-vigged proportionally across that
  book's own two sides. De-vigging happens PER BOOK BEFORE any comparison, because a book
  with a fatter margin is not thereby a book with a different opinion.
- `cons_b(t)` = **median de-vigged probability of every OTHER book** at that same instant.
  Requires at least 3 peers; series with fewer are dropped, not imputed.
- `gap_b(t) = p_b(t) - cons_b(t)`.

For consecutive captures `t -> t'` of the same series:

- `d_book = p_b(t') - p_b(t)`, `d_cons = cons_b(t') - cons_b(t)`.
- `s = sign(gap_b(t))`.
- **book_share** `= -s * d_book / |gap_b(t)|` -- how much of the gap the BOOK closed.
- **cons_share** `= +s * d_cons / |gap_b(t)|` -- how much of the gap CONSENSUS closed.
- These sum to the total fraction of the gap closed.

## Inclusion, frozen

1. Pre-game only: `t' < commence_time`. In-play prices are a different process (D151).
2. Horizon: consecutive captures **20 to 90 minutes** apart. The tape's median cadence is
   60 minutes; this admits the hourly grid and today's faster polling without mixing in the
   multi-day blackout gaps.
3. Dislocation threshold, **primary `|gap| >= 0.015`** (1.5 percentage points of probability).
   Prespecified sensitivity at 0.010, 0.020, 0.030. The primary is fixed at 0.015 now so it
   cannot be chosen later to suit an answer.
4. Both `p_b` and `cons_b` must exist at both `t` and `t'`.

## Primary statistic

**Median `book_share` minus median `cons_share`** across all qualifying observations, with a
**cluster bootstrap by `game_id`, 2000 draws, seed 20260819**, reported as a 95% interval.

## Predictions, committed before computing

- **P1** The gap closes on average: median total closure > 0. Prices do not diverge forever.
- **P2** `book_share > cons_share`, i.e. the outlier does most of the moving. This is the
  REVERSION hypothesis and the one that would make dispersion flags worth something.
- **P3** The effect survives at every sensitivity threshold with the same sign.
- **P4** Books differ: at least one book has a materially higher `cons_share` than the rest,
  i.e. some book actually leads. If no book leads, "consensus" is just noise-averaging.

## What would make this node's answer worthless

Recorded now so it cannot be rationalised later:

- **Staleness confound.** A book that never updates cannot revert, and will register
  `book_share = 0` while consensus drifts around it. This must be measured, not assumed
  away: the fraction of observations where `last_update` is unchanged is reported alongside
  the headline, and the primary statistic is recomputed on the subset where the book DID
  update. If the two disagree, the honest reading is the updated-only subset, and the
  headline is restated as such.
- **Reversion is not profit.** Even total reversion earns nothing unless the price was
  actually available and beat the settled consensus after vig. This node measures direction
  of movement, NOT profit, and must not be quoted as though it measured profit.
