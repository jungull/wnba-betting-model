# M40 — who gets promoted when a starter sits

**E0-style diagnostic, NON-CLAIMING.** Nothing here fits, adopts or ships a model.
Re-run with `python s01_promotion_baseline.py`.

## Why this was run

D198 recorded that our own promotion projection is **75.8%** where the absent player has a
pair history on this team this season (**58%** of cases) and **18.5%** where she does not
(**42%**). Those numbers carried real weight: they were the entire argument for buying a
third-party lineup feed, since a vendor could only pay us on the weak half.

They were not backed by a script. A number in the ledger nobody can re-run is a number
nobody can check, so this rebuilds them from the masters.

## What an event is

Within a team-season, consecutive games are compared. A player who **started the previous
game and does not play in this one** is absent; a player who **starts this game and did not
start the previous one** is promoted. Only the clean case — exactly one of each — is scored,
so the promotion is unambiguously attributable to that absence.

- clean single-absence promotions: **369**
- dropped as multi-absence/ambiguous: **111** (counted, not guessed at)
- median candidate pool: **5**

Every predictor is walk-forward: each event is predicted using only games strictly before it.

## The headline: D198 does not reproduce

| | D198 claimed | M40 measures |
|---|---|---|
| share with same-season pair history | 58% | **23.3%** |
| accuracy, pair-history half | 75.8% | **40.7%** |
| accuracy, first-time half | 18.5% | **39.9%** |

The share is inverted and the gap between the halves has essentially vanished. Our promotion
projection is roughly **40% across the board**, against a chance level of **20.3%** — a real
2× signal, but a flat one.

**This dismantles the premise that made a vendor feed attractive.** The argument in D198 was
that we are strong where we have pair history and nearly blind without it, so someone else's
projection could cover the blind half. We are not blind there: first-time absences are called
at 39.9%, marginally *better* than the repeat half. A vendor would have to beat ~40% overall,
not rescue an 18.5% hole that does not exist.

## Pair history is not demonstrably worth its machinery

The comparison the ledger never made is against the dumbest available rule — pick the bench
player with the most trailing minutes — scored on the **same events**:

| predictor | repeat half | first-time half |
|---|---|---|
| pair history | 40.7% | n/a by definition |
| **top bench minutes** | 33.7% | **39.9%** |
| position-filtered top minutes | 30.2% | 38.2% |

On its own ground, pair history leads by **+7.0 pp**, 95% paired bootstrap **[−7.0, +19.8]**,
positive in 83% of resamples, n=86. **The interval spans zero.** On this evidence the extra
machinery is not demonstrably better than "pick the busiest bench player". The bootstrap is
paired because both predictors run on the same correlated events; two independent intervals
would overstate the uncertainty of the gap.

## A negative result worth keeping: the position filter hurts

The starting five is always 2F/2G/1C, and the promoted player takes the vacated position slot
**74.0%** of the time. That looks like a free constraint, and it is not.

Restricting candidates to players whose prior starts match the vacated position **contains the
true answer only 64.5% of the time** — a predictor cannot beat its own pool coverage. The
promoted player is very often someone who *has never started before*, so a filter built from
prior starts throws the answer away and then looks precise on the small pool that remains.

The first version of this file made exactly that error and scored *below its own chance level*,
which is the tell. Two fixes: unknown-position candidates are eligible, and chance is defined
as the accuracy a random pick inside the pool would actually score — **zero when the pool does
not contain the answer**. Otherwise shrinking a pool past the truth is rewarded. Even repaired,
the filter still loses (38.2% vs 39.9%).

`team_freq` (12.0%) and `cross_season` (2.6%) are both far below chance and are dead ends.

## Per season (walk-forward)

| season | n | pair half | first-time, position-filtered |
|---|---|---|---|
| 2021 | 50 | 37.5% | 33.3% |
| 2022 | 65 | 52.9% | 39.6% |
| 2023 | 56 | 35.7% | 35.7% |
| 2024 | 54 | 63.6% | 44.2% |
| 2025 | 68 | 31.6% | 46.9% |
| 2026 | 76 | 29.4% | 30.5% |

The pair half swings from 29.4% to 63.6% across seasons on 50–86 events. That instability is
itself a reason not to lean on the 40.7% point estimate.

## Limits

- **Small n.** 86 repeat-half events across six seasons. The season table shows how unstable
  that is.
- **Absence is inferred from box scores**, not from a designation — a player who played zero
  minutes and one who was never active look identical here.
- **Only clean single-absence transitions are scored.** The 111 dropped multi-absence games
  are plausibly the harder and more valuable cases, and nothing here speaks to them.
- 2025/2026 are the confirmation holdout and are reported separately rather than pooled.

## What this does not do

Nothing is bound, adopted or promoted. No contract is revised and no model consumes this. The
one operational consequence is negative and belongs in the ledger: **the D198 case for buying
a lineup vendor rests on a split that does not reproduce.**
