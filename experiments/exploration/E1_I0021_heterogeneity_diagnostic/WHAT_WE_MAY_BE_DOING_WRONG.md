# What we may be doing wrong

You asked directly. This is the answer, in plain language, ranked by how strongly this run's own
evidence supports it — not by how plausible it sounds.

First, the two things you asked me to check.

---

## Your minutes idea was right about the mechanism, and it does not rescue the model

You were right that we had been measuring per-minute scoring across *all* games, including the ones
where somebody played four minutes in garbage time. That really was in the data, and it really was
that noisy. Putting a floor on the minutes actually played removes **39% of the variation in
points-per-minute**, and **45%** of the game-to-game variation within a single player. Half the
noise we were fighting was manufactured by our own denominator.

But removing it does not make the model look better. Here is why the number moves depending on how
you ask.

| Realised minutes floor | Games kept | Model's edge over the best available baseline |
|---|---|---|
| none (as published) | 13,879 | +0.56% |
| 10+ | 11,306 | +0.28% |
| 15+ | 9,636 | +0.17% |
| 20+ | 7,849 | +0.44% |
| 25+ | 5,949 | +0.51% |
| 30+ | 3,804 | +0.22% |

Flat. If you instead compare the model to a baseline that was *handicapped* by the same filter, the
edge appears to climb from +0.56% to +4.24% — a sevenfold improvement, and a very tempting headline.
It is not real. At the 30-minute floor that handicapped baseline is simply worse than the ordinary
one (average error 0.150 versus 0.144). The "gain" is the yardstick shrinking, not the model growing.

There is one genuinely useful thing buried in here. The floor changes *which baseline is best*. With
no floor, the best baseline is the average of a player's past per-game rates. With a floor, the best
baseline becomes total-points-over-total-minutes. That second one was never fooled by garbage time
in the first place. **So the noise you identified was real, and our better baseline had already
absorbed it. The model never got the benefit.**

---

## Per-player heterogeneity: not in the way we hoped, but there is one real thing

The idea was: maybe every player responds differently, and averaging them together cancels the
signal out. That is testable — you fit the effect separately for each player and ask whether those
per-player numbers are more spread out than pure chance would produce.

The first answer was yes, and it was exciting: the spread was 9–24% wider than chance, with odds
against it of about 200 to 1 on some measures. **That answer was wrong, and I can show you why.**

Several of the things we measure are *running averages of a player's own history* — how they have
been scoring lately, how much they have been used lately. Those move slowly and smoothly across a
season. The standard way of building the "pure chance" comparison shuffles a player's games into
random order, which flattens that smoothness. Compare a smooth thing against a flattened version of
itself and the flattened one looks too tidy — so real chance variation gets mistaken for signal.

When the comparison is rebuilt so it keeps the smoothness (rotating a player's season rather than
shuffling it), the entire effect disappears. At every minutes floor. The odds against go from 200-to-1
to roughly even. And the giveaway is clean: on the two pure-noise columns we planted as controls —
which have no smoothness by construction — the two methods agree to within 0.4%. The gap shows up
*only* where the smoothness is. Across 48 tests, the size of the error tracks the smoothness of the
input at a correlation of **0.83**.

**So: players' responses are not measurably more varied than chance.** Fitting a model per player
does not have hidden signal waiting in it.

**With one exception, and it is worth your attention.** Players do not respond to defences in
different *directions*, but they do respond at different *strengths*, and the strength is
predictable: the higher a player's usual usage, the more their scoring rate moves against a weak
defence. That relationship is solid — it survives the strict comparison, it survives a rank-based
measure that ignores outliers, it survives dropping the ten most influential players, and both
noise controls stay quiet. Odds against chance about 285 to 1, after correcting for having tested
six relationships.

That is not an argument for per-player models. It is **one extra term in the model we already have**:
usage multiplied by opponent defence.

---

## The ceiling on a single player, measured for the first time

You asked what is achievable with maximum data on one player. I took the five best-sampled players
in the window — around 105 qualifying games each, which is as much as this dataset contains — and
built a dedicated model for each, trained only on that player's earlier games and tested on their
later ones.

**Every one of them lost to that same player's own running average.** Skill of −4.6% to −9.4%.
Not one positive result out of ten player-by-floor combinations.

The gap between what these models *look* like they can do and what they *actually* do is the whole
story: fitted on all of a player's games at once they explain 4–18% of the variation, which looks
respectable. Fitted honestly — only on the past — they explain *less than nothing*. All of the
apparent skill is hindsight.

That bounds everything else. If a dedicated model with maximum data on the best-sampled player in
the dataset cannot beat that player's own average, no per-player or per-cluster scheme built on
less data will either.

---

# Ranked: what is actually going wrong

### 1. We keep measuring "better than what?" and the answer keeps changing the result
**Evidence: direct and strong, from this run.**
The exact same forecast, on the exact same games, scored +0.22% or +4.24% depending only on which
baseline it was compared against. D090 already showed this once (+46.4% versus +7.1%). This is now
twice, in different work, on different targets.

Our baselines are genuinely good. Total-points-over-total-minutes from a player's own history is a
strong forecast, and beating it by 0.5% is not the same as "nothing predicts scoring efficiency."
**A lot of what we have been calling a null is really "our baseline already knew that."**

*What to do:* stop reporting a single skill number. Report the model against the strongest available
baseline, and report what that baseline is. It costs nothing and it is the difference between a
result and an artefact.

### 2. Our test for "is this real?" was itself broken — and nobody had checked
**Evidence: decisive, and new. This is the seventh explanation, not on anyone's list.**
This run nearly published a false positive. The standard shuffle test is too lenient whenever the
thing being tested is a running average of an entity's own history — which describes most of what
this program builds. Measured here: it reported odds of 200-to-1 where the honest test reports
roughly even.

Worse, the control an analyst would naturally reach for — *shuffle the player labels and see if the
spread shrinks* — is **mathematically incapable of detecting anything**. Relabelling players moves
whole players around intact, so every number comes back identical. Confirmed on this data to 16
decimal places.

This program has caught the same shape of error nine times at the row level. This is the same error
one level down, and it was undetected.

*What to do:* add a rotation-based comparison to the shared toolkit and make it warn automatically
when a feature is smooth. The fix is about fifteen lines. Details in `NOTES.md` §5b.

### 3. There genuinely is not enough data per player
**Evidence: measured directly for the first time.**
About 57 games per player before any filter; the very best-sampled player has ~105 qualifying games,
and a walk-forward model can only score ~80 of them. That is the ceiling, and at that ceiling
dedicated per-player models still lose.

*What to do:* treat "more model per player" as closed. If more precision is wanted it has to come
from more *data*, not more parameters — which points at the injury/inactives feed D089 already
flagged as the highest-value acquisition.

### 4. The big screens used an instrument that cannot see what we were looking for
**Evidence: demonstrated in this run.**
The omnibus test — "is the overall spread bigger than chance?" — found nothing. A directed test
along one named axis found something at 285-to-1 in the same data. Both are correct. A wide net with
a very high bar (8.68 across 318 cells) will miss a small effect that a single sharp question finds
easily.

*What to do:* keep the broad screens for discovery, but when there is a real mechanistic hypothesis,
ask it directly with its own preregistered test. Do not make it queue behind 300 cells it has
nothing to do with.

### 5. Points-per-minute hides the two things it is made of
**Evidence: supported, quantified here.**
At the 20-minute floor, against the best baseline: shots-per-minute skill **+1.06%**,
points-per-shot skill **+0.83%**, but the two multiplied together — points-per-minute — only
**+0.44%**. The composite is weaker than either part at almost every floor. D087 saw components
moving in opposite directions; this measures the cost.

*What to do:* stop treating points-per-minute as the target. Model shot volume and conversion
separately and multiply at the end.

### 6. The minutes noise was real — it just was not the blocker
**Evidence: mechanism confirmed, effect on the conclusion nil.**
39% of the variation removed, and no change in the model's edge. Your diagnosis of the *mechanism*
was correct and the fix should be adopted anyway — cleaner measurement is worth having. It is not
the reason the screens came back empty.

### 7. Pooling was not, on this evidence, destroying a signal
**Evidence: tested properly, came back negative.**
Once the comparison is built correctly, the per-player numbers are no more spread out than chance.
The one exception — response strength scaling with usage — is a pooled interaction term, not an
argument against pooling.

I want to be clear that this is a genuine negative and not a failure to look. It was the
centrepiece test, it was preregistered before anything was computed, it was run at six different
minutes floors against four different comparison methods, and it closes the heterogeneity question
properly rather than by assumption.

---

## What I would actually do next

1. **Add the usage × opponent-defence interaction to the pooled model.** One term. It is the only
   live, evidence-backed lead this run produced.
2. **Fix the shared toolkit** (item 2 above). Fifteen lines, and it protects every future screen.
3. **Re-report the existing nulls against their strongest baseline**, not their published one.
   Some of the four "nothing predicts efficiency" verdicts may read differently, and it costs no new
   data and no refitting.
4. **Split the target** into shot volume and conversion rather than points-per-minute.
5. **Treat per-player and per-cluster modelling as tested and closed** — step 4 measured the ceiling
   and it is below the do-nothing baseline.
6. **Adopt the minutes floor for measurement anyway**, with the label attached: it answers "given
   they played, was it predictable", and it is not a forecast we could place a bet on, because a
   real forecast has to predict the minutes first.
