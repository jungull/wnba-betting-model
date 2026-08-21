# M34 — what is the official injury tape actually worth for minutes?

Frozen after the join's **shape** was established and before any error, skill or improvement
figure existed. Known at freezing: the injury tape covers **10 usable game dates**
(2026-08-06 … 2026-08-20, with the 08-10→08-14 capture blackout in the middle), **701
player-game rows, 198 players, 29 games**, and status counts Out 6,351 / Questionable 2,029 /
Probable 1,691 / Available 607 / Doubtful 37 across 786 captures.

---

## Why this screen exists, and what it cannot be

M33 established that the model-market gap is **entirely minutes**: hand the model correct
minutes and it beats the market by 0.326, and matching the market needs a **40% cut in minutes
error** — roughly five times everything the modelling programme has achieved on that target. So
the deficit is information, and the largest unused information asset is the official injury
tape, which the production arm has never read.

**This screen cannot settle that question and does not claim to.** Ten game dates is a
feasibility measurement, not evidence. It is run now because the alternative — recommending a
contract change to a byte-locked arm on the strength of an untested asset — is worse.

## The blocker this screen worked around, stated plainly

The frozen outcome snapshot the market nodes use ends **2026-07-31**. The injury capture begins
**2026-08-06**. They do not overlap at all, so the production arm's own forecasts cannot be
scored against the injury tape on a single row.

The raw gamelogs ARE current (through 2026-08-20). So this screen **does not use the arm**. It
builds its own minutes baseline from the same construction the reference ladder selected —
EWMA of the player's own prior played minutes, half-life 2 — exactly as E1_I0061 did. The
baseline is therefore comparable to the ladder's `R2_EWMA_TUNED`, not to the shipped arm.

## THE CRUX: how late are you allowed to look?

The reports are published on game day. The contract's forecast cutoff is 18:00 UTC the day
BEFORE. Most of the tape therefore falls *after* the cutoff the current model must respect. So
both are measured and neither is allowed to stand in for the other:

- **CUTOFF_A — contract-legal.** Last capture with `retrieval_ts_utc` strictly before 18:00 UTC
  on the day before the game. Directly comparable to what the arm could use today.
- **CUTOFF_B — latest pre-tip.** Last capture strictly before the game's scheduled start. What a
  bettor could actually see, and NOT available to the current arm without a cutoff change.

**A result under CUTOFF_B may never be quoted as an improvement to the current model.** It
measures a different product with a different information set.

## Arms, frozen

Response: **actual minutes**, on rows where the player appeared.

| id | forecast |
|---|---|
| `BASE` | EWMA(half-life 2) of the player's own prior played minutes |
| `BASE+A` | `BASE` plus the point-in-time status at CUTOFF_A |
| `BASE+B` | `BASE` plus the point-in-time status at CUTOFF_B |

The status enters as a per-status additive offset fitted on **strictly earlier game dates only**
— walk-forward within the 10 dates, so no row's own date contributes to its own offset. Dates
with no earlier date are unscored and counted.

Separately, and reported apart because it is a different question already answered at 17.8% by
E1_I0062: **availability** — does the status predict whether the player appeared at all?

## Statistic, frozen

Mean absolute error in minutes, with a **cluster bootstrap by game date, 2,000 draws, seed
20260821**. Ten clusters is few and that is stated with every interval rather than once.

## Predictions, committed before computing

- **P1** `Out` is near-deterministic for non-appearance: appearance rate under `Out` below 10%.
- **P2** `BASE+B` beats `BASE` on minutes MAE for players who appeared.
- **P3** *(the one that decides the recommendation)* `BASE+A` — the contract-legal version —
  improves by **less than half** of what `BASE+B` does, because the reports that matter are
  published after the current cutoff.
- **P4** *(sceptical)* No interval excludes zero. Ten game dates cannot establish anything, and
  a screen this size returning a significant result should be doubted rather than believed.

## What this screen cannot establish, whatever it returns

- **Ten game dates, one league, one August.** Nothing here generalises.
- **It does not use the shipped arm** and so cannot be quoted against the arm's own numbers.
- **It cannot value the tape for the 40% target.** M33's requirement is measured against the
  market on 5,889 rows; this is 701 rows with no market comparison at all.
- **No wager-shaped claim.** S42 untouched, SHADOW unchanged, no fitted scoring model involved.
