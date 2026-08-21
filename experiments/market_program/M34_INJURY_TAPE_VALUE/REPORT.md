# M34 — what the official injury tape is actually worth

**Prereg** `0fcdb68a2db87707a2ed6b36fca8fd4e22adf929a2a7410419fee1fe5804c3db`, frozen after the
join's shape and before any error figure. **701 player-game rows, 10 game dates, 29 games, 198
players.** This is a feasibility measurement. Ten game dates is not evidence and nothing here
generalises.

---

## Three findings, and the first one is structural

### 1. Under the model's own forecast cutoff, the tape does not exist

**CUTOFF_A — 18:00 UTC the day before the game, the contract's convention — sees status on
0.0% of rows. Not one.**

The reports are published on game day. The earliest capture for a game arrives roughly **nine
hours after** the cutoff the arm must respect. So "wire the injury tape into the minutes model"
is not a data-source change. **It is a forecast-cutoff change**, which is a far larger contract
question than adding an input.

That is the single most important thing this screen found, and it was invisible until the
point-in-time join was done properly.

### 2. It is a near-perfect AVAILABILITY signal

At CUTOFF_B (latest capture before tip):

| status | n | appeared |
|---|---|---|
| **Out** | 40 | **0.0%** |
| Questionable | 5 | 80.0% |
| Probable | 2 | 100.0% |
| Available | 23 | 95.7% |
| *(not listed)* | 631 | 85.7% |

**`Out` is perfectly separating on this sample — 0 of 40 played.** That is what the tape is for
and it does it exactly as advertised. Coverage is only 10% of rows because the report lists
designated players only; not being listed is itself the common case and carries an 85.7%
appearance rate.

### 3. It is worth NOTHING for minutes, given the player played

On the 568 rows where the player appeared, with a per-status offset fitted walk-forward on
strictly earlier dates:

| forecast | minutes MAE | 95% CI | vs. base |
|---|---|---|---|
| `BASE` EWMA(half-life 2) | 4.6955 | [4.274, 5.178] | — |
| `BASE + A` contract-legal | 4.6933 | [4.273, 5.158] | +0.0022 |
| **`BASE + B` latest pre-tip** | **4.7059** | [4.287, 5.172] | **−0.0104** |

Knowing a player is Questionable or Probable does not tell you how long they will play once
they do play. **It slightly hurts.**

## Predictions

| | prediction | result |
|---|---|---|
| **P1** | `Out` near-deterministic for non-appearance, <10% | **PASS** — 0.0% |
| **P2** | latest-pre-tip status improves minutes | **FAIL** — −0.0104 |
| **P3** | contract-legal gets under half of that | **n/a** — P2 failed |
| **P4** | no interval separates from base | **PASS** — 10 dates settle nothing |

## What this does to M33's recommendation

M33 found the model-market gap is **entirely minutes-given-played**, needing a 40% error cut,
and named the injury tape as the largest unused asset aimed at it. **On this sample the tape
does not touch that quantity at all.**

So the recommendation splits, and only one half survives:

- **For availability** — will the player appear — the tape is excellent and the programme
  already knows availability is worth 17.8% on prop-shaped questions (E1_I0062). This is the
  strong use, and it is the one the arm's `p_active` target would consume.
- **For minutes-given-played** — M33's actual gap — the tape shows nothing here. The market's
  edge on rotation regulars is not explained by injury designations.

**The coordinator's previous message implied the tape was aimed at the minutes gap. On this
evidence it is not.** It is aimed at the availability branch, which is a real and separate win
that E1_I0062 already sized.

## What this cannot establish

- **Ten game dates**, one league, one August window, with the 08-10→08-14 capture blackout
  sitting inside it. `Out` at n=40 and `Questionable` at n=5 are not samples anyone should
  build on.
- **It does not use the shipped arm.** The frozen outcome snapshot ends 2026-07-31 and the
  injury capture starts 2026-08-06 — they do not overlap on a single row, so the arm's own
  forecasts could not be scored. The baseline here is the ladder's tuned EWMA, rebuilt.
- **The ET→UTC conversion is a fixed −4 offset** for a single August window. Correct here,
  wrong in general.
- **No wager-shaped claim.** S42 untouched; no fitted scoring model appears in this node.

## What would actually settle it

Keep capturing. The tape needs a full season overlapping a refreshed outcome snapshot before
the minutes question can be asked properly. And if the answer matters, the prior question is
**whether the forecast cutoff can move at all** — because at 18:00 UTC the day before, there is
nothing to read.
