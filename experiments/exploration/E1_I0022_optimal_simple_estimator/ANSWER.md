# Your question, answered

> *"so at this point a player's average score to date with a ewma is the best predictor of their
> score and any nuance just muddies the water?"*

**You're most of the way right, and the part you're wrong about is the interesting part.**

You're right that a well-tuned EWMA of a player's own prior games is a very strong predictor — much
stronger than what we'd been comparing against. You're right that it currently beats the big model
on the headline numbers. But you're wrong that the nuance is muddying the water. The nuance is
mostly *fine*. It's being drowned out by a small patch of rows where the model gives up and prints a
constant.

Here's the whole thing in three findings.

---

## 1. Yes — the simple EWMA beats the big model on the headline

Scored on the same 9,517 games (2023 and 2024), with the EWMA's settings chosen only from *earlier*
seasons so it never saw the games it was graded on:

| what we're predicting | who wins | by how much |
|---|---|---|
| **Points** | simple EWMA | 1.93% |
| **Minutes** | simple EWMA | 4.41% |
| **Shot attempts** | simple EWMA | 3.13% |
| **Points per minute** | simple EWMA | 1.33% |

Four for four. Not a whisker either — these are solid, and they'd survive even if I'd cheated
outright and tuned the EWMA on the very games it was graded on (that would only have bought it
another 0.05–0.80%).

So on a straight pooled read: **the sophistication is not currently earning its keep.** That's a
real answer and it's worth saying plainly.

## 2. But we'd been grading the model against a weak opponent

This is the part that should sting a bit. Everything this programme has measured, it measured
against a fixed "naive" baseline — the player's plain running average. Nobody ever checked whether
that baseline was any good.

It isn't. The tuned EWMA beats it by **7.78% on minutes**, 3.04% on shot attempts, 2.29% on points
per minute, 1.34% on points.

Which means the same model forecasts, on the same games, score completely differently depending
purely on who you line them up against:

| what we're predicting | model vs. the old baseline | model vs. the tuned EWMA | swing |
|---|---|---|---|
| **Minutes** | **+3.71%** (a win) | **−4.41%** (a loss) | **8.1 points** |
| Shot attempts | +0.00% | −3.13% | 3.1 points |
| Points per minute | +0.99% | −1.33% | 2.3 points |
| Points | −0.57% | −1.93% | 1.4 points |

The model's proudest number — "+3.55% on minutes" — was a win over a weak reference. Against a
proper one it's a loss. Nothing about the model changed; only the opponent did.

## 3. The model's loss is almost entirely 7% of games where it stops modelling

This is where "the nuance muddies the water" turns out to be wrong.

On **698 of the 9,517 games (7.3%)** the model gives up and emits a fallback. On those 698 games it
prints **two distinct numbers, total.** Not two hundred — two. It is, functionally, a constant.
These are almost exactly the games where a player has fewer than three prior appearances that
season. On those rows the simple EWMA beats it by 35–43%.

Take those 698 games out and look at the other 8,819 — the games where the model is actually doing
its job:

| what we're predicting | who wins | by how much | is it real? |
|---|---|---|---|
| **Points** | **the model** | **+1.07%** | yes, p = 0.0002 |
| **Shot attempts** | **the model** | **+0.88%** | yes, p = 0.0012 |
| Minutes | dead heat | +0.03% | no, p = 0.77 |
| Points per minute | simple EWMA | −0.39% | marginal, p = 0.07 |

So the honest picture is:

- **Minutes: the nuance is worth nothing.** A two-game-half-life EWMA of the player's recent minutes
  is as good as everything we've built. Not slightly better or worse — statistically
  indistinguishable, p = 0.77.
- **Points and shot attempts: the nuance is worth about 1%, and it's real.** Small, but repeatable
  and statistically solid.
- **All the pooled damage comes from the cold-start hole**, not from the modelling.

The pooled −1.93% on points is 610 games at −38% cancelling 8,860 games at +0.92%. Reporting the
pooled number alone actively misleads — which is the same trap this programme fell into before, when
a headline of −0.22% turned out to be +1.44% and −18.6% averaging out.

---

## What the best simple estimator actually looks like

Worth knowing, because it's not one recipe — the right amount of memory differs wildly by quantity:

| quantity | best form | memory | shrink toward |
|---|---|---|---|
| **Minutes** | EWMA | **half-life 2 games** | nothing |
| Shot attempts | EWMA | half-life 5 games | prior season, very lightly |
| **Points** | EWMA (of minutes × points-per-minute) | half-life 8 games | prior season, very lightly |
| **Points per minute** | EWMA | **half-life 40 games** — basically the whole season | prior season, lightly |

That spread is itself a finding. **Minutes is a short-memory quantity** — how many minutes a coach
gave someone last week tells you far more than what they averaged in June. **Shooting efficiency is
a long-memory quantity** — it barely moves, so use everything you have. Using one window for both is
a mistake, and it's the kind of mistake a single "average to date" makes.

Two more things that surprised me:

- **Shrinking toward the league average always hurt.** If you shrink at all, shrink toward the
  player's own prior season. And shrink barely — the best strength was worth about half a game.
- **Throwing away low-minute games from a player's history always hurt**, at every threshold tested.
  Even a 12-minute garbage-time game tells you something. We'd half-expected the opposite.

---

## So: is the nuance muddying the water?

No. But it's currently being wasted.

The model has a small, real edge on points and shot attempts where it's actually modelling — and it
throws that edge away, several times over, on the 7% of games where it isn't. Right now the
sophistication is paying for itself on 93% of games and being buried by the other 7%.

The obvious move is to stop letting the model print a constant. If you hand those 698 games to the
tuned EWMA and keep the model everywhere else, points MAE goes from 4.228 to 4.107 — better than
the model alone by 2.85% and better than the EWMA alone by 0.98%. *(Caveat, stated honestly: I found
that split by looking at the results, so treat that last number as a promising lead rather than a
proven one. The switch itself is legitimate — the model tells you in advance when it's falling
back.)*

And separately: **every skill number this programme has published needs re-reading.** They were all
measured against a baseline we now know is beatable by 1.3–7.8%. The flat curve everyone has been
staring at may partly be an artefact of the ruler, not the thing being measured.

---

### The fine print

- Only 2022–2024 data was touched. Nothing from 2025 or 2026 was read, joined, plotted or described.
- The model was never refitted or retrained — only its stored forecasts were scored.
- Every estimator uses only games played *before* the game being predicted, and the EWMA's settings
  were chosen from earlier seasons only.
- Before computing anything, I reproduced the programme's existing benchmark table exactly — all
  nine numbers to the last decimal place — so we know we're standing on the same ground.
- Full method, every caveat, and a list of every place I could have fooled myself is in `NOTES.md`.
