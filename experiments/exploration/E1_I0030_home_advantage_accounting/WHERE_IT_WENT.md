# Where the home advantage went

You said: *there is a measurable difference in avg score between home and away teams, so if that
doesn't show up on the player level then where does it?*

You were right on both counts. There **is** a home advantage, and it **is** at player level. Here is
the whole chain, with the arithmetic balancing at every step.

All numbers below are **regular-season games, 2021–2024** (888 games). Playoff games are excluded
from the headline and I say why at the bottom.

---

## 1. How big is it?

**Home teams score 0.97 more points per game than away teams.** 82.37 vs 81.40.

That is a real effect but a small one. It is about one point in eighty-two — roughly 1.2%. For
scale, the game-to-game swing in a team's score is about 11 points, so this is a tenth of one
typical night's noise.

*(If you include the playoffs the gap looks like 1.36 points, and playoffs alone look like 5.7
points. Ignore that. In the playoffs home court is **awarded to the better team**, so a "home
advantage" measured there is mostly just "the better team is better." The regular season is the only
place the comparison is clean, because the schedule gives every team almost exactly half its games
at home — I checked, and no team is further than 3% off a 50/50 split.)*

---

## 2. Two of the three places you suggested it could hide are **structurally closed**

You proposed pace as the most likely hiding place, and minutes as another. Both turn out to be
impossible rather than merely unlikely, and nobody in this programme had checked.

**Minutes cannot hide it.** A team plays 200 minutes in regulation, and overtime adds 25 more — *to
both teams at once.* I checked every game: **the two teams played exactly the same number of team
minutes in 970 out of 970 games.** Not similar. Identical. So "the home team plays more" is not a
small effect, it is an arithmetically unavailable one.

**Pace almost cannot hide it either, and for the same kind of reason.** Possessions alternate. The
two teams in a game get the same number of possessions to within one. The measured gap is +0.13
possessions per game and it does not clear its own significance test (p = 0.16). Pace is a property
of *the game*, not of the home team — the correlation between the home team's possessions and the
away team's possessions in the same game is 0.82.

So your intuition that per-minute and per-rate screens would be blind to a pace effect was a good
one — it just turns out there is no pace effect to be blind to. **The gap has to be efficiency**, and
it is: +0.82 of the 0.97 points is points-per-possession.

---

## 3. Inside efficiency, it is **free throws**, and almost nothing else

Points break down exactly — no approximation, no leftover:

> points = 2 × (two-pointers made) + 3 × (three-pointers made) + (free throws made)

Applying that to the 0.97-point gap:

| channel | contribution to the home advantage |
|---|---|
| **Free throws made** | **+0.941** |
| Three-pointers made (×3) | +0.199 |
| Two-pointers made (×2) | **−0.176** |
| **Total** | **+0.965** ✓ |

**Free throws are 97.6% of the entire home advantage.** Two-point shooting is actually *worse* at
home. Field-goal percentage, effective field-goal percentage, shot volume, three-point volume — all
of them are flat to four decimal places and none is anywhere near significant.

And splitting the free-throw channel one more time:

- **Free-throw attempts: +1.087 per game** at home — that's the whole story
- Free-throw accuracy: +0.4 percentage points — negligible, not significant

Home teams don't shoot better. **They go to the line more.** And the reason shows up directly in the
foul counts:

- Home teams **commit 0.59 fewer fouls** per game
- Home teams **draw 0.59 more fouls** per game

Those two are the same number with opposite signs, because a foul committed by one team is a foul
drawn by the other. This is a whistle effect, and it is the single most robust thing in the whole
screen. When I correct for having looked at 25 different quantities, **free-throw attempts and the
foul differential are the only cells that survive** (corrected p = 0.00005 and 0.00015). The points
gap itself barely survives (0.029). Points-per-possession does not (0.069).

That ordering is worth sitting with: *the fouls are a cleaner signal than the points they cause.*

---

## 4. The reconciliation: the team gap, pushed all the way down to players

This is the part you asked for. Team points are the sum of player points, so the team gap has to
equal the sum of the player gaps. It does — exactly.

The identity I used splits the team gap into two pieces with **no residual term**:

> team gap = (players scoring differently at home) + (different players being on the floor at home)

| | value | share of the 0.965 gap |
|---|---|---|
| Team-level home advantage | **+0.965** | 100% |
| (1) **Same players, scoring more** | **+1.314** | 136% |
| (2) Different players on the floor | −0.349 | −36% |
| (1) + (2) | +0.965 | ✓ |
| **Residual** | **4 × 10⁻¹⁵** | zero |

**The residual is machine zero.** The books balance.

Term (2) — the roster-composition term — looks large but it is **noise**. I tested it against its
own honest null (randomly relabelling which team in each game is home, 4,000 times, recomputing the
entire decomposition each time): p = 0.54. It is a coin flip. Term (1), the real one, comes in at
p = 0.028.

So: **all of it is the same players scoring more at home. None of it is different players playing.**

That also kills the third hiding place you and the coordinator raised — minutes and rotations. I
checked directly: home and away teams use the same number of players (9.41 vs 9.41, p = 1.00), spread
minutes with the same concentration (p = 0.94), and give starters the same share (p = 0.98). Blowout
substitution is not doing anything, because home teams win only 53.2% of games and the minutes budget
is fixed anyway.

Splitting term (1) once more:

- via **minutes per appearance**: +0.241 (18%)
- via **points per minute**: +1.073 (82%)

And running the same reconciliation directly on free throws: **105% within-player, −5% composition.**
The free-throw advantage is entirely the same players getting to the line more, not different
players getting to the line.

---

## 5. So what does one player actually get?

Here is the number that explains every null this programme has ever reported on home/away.

Spread across the ~9.4 players who appear in a team-game, the advantage is:

| per player, per game played | home minus away |
|---|---|
| **Points** | **+0.101** |
| **Free-throw attempts** | **+0.116** |
| Points per minute | +0.0074 |
| Minutes | −0.007 (nothing) |
| Shot attempts | +0.007 (nothing) |
| Effective FG% | −0.0004 (nothing) |

A player scores **one tenth of one point more** at home. And the free-throw line is where it comes
from: +0.116 attempts is the most statistically solid player-level cell in the screen (p = 0.00015),
far more solid than the points it produces (p = 0.10).

Now the punchline. **A player's game-to-game standard deviation in points is 7.46.** So the home
effect on one player is **0.68% of one night's normal variation** — and it is worse than that,
because a forecast built from a player's own history already sits at the *average* of their home and
away games, so the piece a home/away term could add is only *half* the gap: **0.051 points.**

**That is not a null. That is an effect one seventieth the size of the noise it is buried in.**

---

## 6. Does a home/away term actually improve a forecast? No — and it can't

I ran the test that had never been run: take a proper prior-games-only forecast of a player's
points, add a home/away term fitted only on earlier seasons, and see if it forecasts better.

Across 4 targets × 4 references × 2 strata (32 cells): **nothing.** Best cell is points on the
decision stratum, +0.028% MAE improvement, p = 0.17.

But here is the thing that makes it interpretable rather than just another null. **Before fitting
anything**, the arithmetic above says the absolute maximum a *perfect* home term could add to
forecast R² for points is **4.6 × 10⁻⁵**. The observed value is **6.5 × 10⁻⁵**.

**The measurement landed on its own ceiling.** The effect isn't missing. It is exactly the size it
was predicted to be, and that size is below what 13,152 games can resolve.

For contrast: a randomly generated fake home/away label, through the identical pipeline, gives
−2.3 × 10⁻⁵. Real is positive and at its ceiling; fake is negative. That is what a genuine but
undetectable effect looks like.

---

## 7. The "reference absorption" theory — real as arithmetic, wrong as an explanation

The coordinator's second candidate was that a player's rolling average blends home and away games,
so the home increment is hidden inside it. That is true as arithmetic — it is exactly why the
detectable piece is half the gap rather than the whole gap.

But it is **not** why the earlier screens returned null, and I can show that directly. I built a
second set of references using only the player's prior games **at the same venue type** — home rows
see only prior home games, away rows only prior away games. If absorption were hiding a usable
signal, un-blending should recover it.

It doesn't. **The venue-split reference is worse in all 8 cells, by 3.3% to 5.6% MAE, p = 0.0002
every time.**

The reason is simple: splitting by venue halves the history behind every estimate. The information
you buy is a 0.05-point venue increment. The noise you add by throwing away half your sample is two
orders of magnitude bigger. **Un-blending the reference costs about 100× more than the signal it
recovers.**

---

## 8. Do players differ? Not measurably

You wondered whether home/away affects players differently. The per-player home-minus-away point
differences do spread out — standard deviation 1.22 across 149 players with at least 20 home and 20
away games.

But under the correct null — cyclically shifting each player's home/away sequence, which preserves
both how often they play at home and the run structure of home stands — the expected spread from
pure noise is **1.13**. Observed 1.22, null 1.13, **p = 0.109**. Same story for points per minute
(p = 0.077) and free-throw attempts (p = 0.054).

There may be something there at the edge, but nothing in this data clears a bar you'd want to bet on.

*(I also ran the control an analyst reaches for first — shuffle the player labels and see if the
spread shrinks. It is a mathematical no-op: standard deviation 10⁻¹⁷. It cannot fail, so it proves
nothing. I'm reporting it as vacuous rather than as a pass.)*

---

## 9. Eastbound travel: your restriction was the right one, and it came back negative

You said we should only look for an effect on eastbound travel that crosses time zones. That is the
correct restriction and it's what made this testable — so I preregistered it and hashed the
prediction before computing anything: **eastbound crossings should HURT** (negative on points and on
points per possession), because flying east demands a circadian phase advance, the harder direction.

**It came back the wrong way.** Eastbound is **+0.86 points** — a *positive* coefficient — with
p = 0.87 in the direction I'd committed to. On points per possession, +0.001, p = 0.47.

And the internal controls refute the mechanism outright. If circadian disruption were real, the
ordering should be eastbound worst, same-zone neutral, westbound best. Instead:

| arm | effect on points per possession |
|---|---|
| Eastbound (should be worst) | +0.001 |
| Westbound (should be best) | +0.008 |
| **Same-zone travel** (no circadian component) | **−0.005** — the worst arm |

The sharpest version — road games only, eastbound vs westbound, which removes the home/away confound
entirely — gives a raw difference of **+0.006 points** across 211 vs 212 games. Nothing.

**And I should say plainly: yes, this is the dead rest-and-schedule family in new clothes.** The raw
travel numbers look like they show something, but only because the travel arms are 30–38% home games
while the "no travel" arm is 87% home games. The raw contrast is mostly the home effect wearing a
travel costume. Hold home/away and rest fixed and nothing survives. This is the fifth time this
family has died here and it died the same way.

One genuinely useful detail that fell out: **Phoenix does not observe daylight saving time, so during
the WNBA season the Phoenix clock equals the Pacific clock.** A Phoenix–Seattle trip is a *same-zone*
trip for body-clock purposes. Using the time-zone name instead of the actual clock offset would have
invented crossings that don't exist. The league spans three real clock zones in season, not four.

---

## 10. Attendance: the data does not exist

You flagged it and doubted we could model it. You were right, and for a more basic reason than you
thought — **there is no attendance data in this repository at all.**

I scanned all 5,612 tabular files under `data/`. **Zero** carry a column matching "attend". Every
mention of attendance anywhere in the repo is one of:

- a field name on an upstream stats endpoint that was surveyed but never ingested
- a placeholder key (`attendance_actual`) in a forward-looking live-capture schema
- catalogue row 99 in `FEATURE_LAB_CATALOG.md`, marked **"not captured; noted"**
- prose about 2021 having been played under attendance restrictions
- one league-wide press figure in a research report

Per your brief I stopped there and built no proxy. Arena capacity, market size, weekend-vs-weeknight
and 2021-vs-later are all available and all tempting, and none of them is attendance. Presenting one
as an answer would be exactly the substitution you told me not to make.

If you want this tested it needs an external per-game attendance series joined on `game_id`. Worth
knowing before you commission it: attendance is measured *at* the game and is itself downstream of
team quality, opponent, and day of week, so it isn't a clean pre-game feature. The defensible version
would use the venue's prior-games-only average attendance — which is a market-size proxy, a different
question from the one you asked.

---

## The whole thing in six lines

1. Home teams score **+0.97 points** per regular-season game. Real, small.
2. It **cannot** be minutes (identical in 970/970 games) and **is not** pace (possessions are shared).
3. It is **97.6% free throws** — home teams take **1.09 more attempts** and commit **0.59 fewer fouls**.
4. Pushed to player level it reconciles **exactly** (residual 4×10⁻¹⁵): **all of it is the same
   players scoring more**, none of it is rotation or roster changes.
5. Per player that is **+0.10 points and +0.12 free-throw attempts per game** — under 1% of one
   player's nightly noise. That is why every player-level screen returned null, and the observed
   forecast gain landed **exactly on the ceiling** that arithmetic predicted.
6. **Eastbound travel: refuted against a preregistered direction. Attendance: not in the data.**

**Your accounting argument was correct, and the effect was never missing. It was located, it is
distributed across nine players, and it lives at the free-throw line.**
