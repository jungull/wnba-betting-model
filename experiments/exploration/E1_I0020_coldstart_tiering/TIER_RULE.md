# The recommended operating rule

*Written for you, not for an agent. Everything below is measured on 2022–2024 only.*

---

## The one-sentence version

**When a player has fewer than three appearances this season, stop using the model's forecast and
use instead a blend of that player's own games so far with a prior built from their depth-chart
rank and draft slot — this covers about 8% of rows and cuts the points error on them by a third and
the minutes error by nearly half.**

---

## What we found first, and it is the thing worth knowing

You proposed splitting players into "enough data to model" and "needs a smart filler score". That
split already exists inside the model — it just isn't smart yet.

**On the thin-data rows, the model currently prints the same number for everybody.** Across three
seasons and 1,061 player-games it forecast **8.70 points** and **21.6 minutes**, every time, for
every player. The standard deviation of those forecasts is 0.013 points. The actual spread of
what those players scored is 7.2 points.

So it isn't that the model is doing something subtle and getting it wrong. On these rows it is not
looking at the player at all. Your instinct was right, and the fix is the one you described.

---

## The rule

**Step 1 — decide which tier a player is in.** Use the model's own `is_fallback` flag. It already
exists, it costs nothing, and it turns out to be exactly right: it catches every row with fewer
than three appearances this season, plus 62 rows where a player is returning from an absence. If
you would rather have a rule in words: *fewer than three appearances so far this season.*

**Step 2 — for players in the thin tier, replace the forecast with:**

```
forecast  =  w × (that player's average over their own games so far this season)
           +  (1 − w) × (structural prior)

w                 =  n / (n + 2),  where n = games they have already played this season
structural prior  =  league average
                     + adjustment for their depth-chart rank on their own team
                     + adjustment for their draft slot
```

Both adjustments are estimated **only from earlier seasons** — the 2022 numbers use 2021, the 2023
numbers use 2021–22, and so on. Nothing looks forward.

So a player with zero games gets the pure structural prior. After one game it is one-third their
own average, after two games one-half, after four games two-thirds — the model's own forecast takes
over at three games anyway.

**Step 3 — leave everything else alone.** Above three appearances the model is genuinely good and
should not be touched. Nothing here retrains it.

---

## What it is worth

On the thin-data rows (1,061 of 13,879 rows, 7.6%; about 7.8% of the rows you would actually price):

| | model today | this rule | change |
|---|---|---|---|
| points, average error | 6.06 | **4.02** | **−34%** |
| minutes, average error | 9.75 | **5.44** | **−44%** |

Across **all** rows, in the same units the earlier work reported:

| | points skill vs. a naive running mean |
|---|---|
| model as it stands | −0.22% |
| the crude patch already tested (D081) | +1.36% |
| best crude patch available | +3.09% |
| **this rule** | **+3.51%** |

It holds up in all three seasons separately. And as a check that the improvement really lives in
the thin tier rather than in the blend simply being a better forecast everywhere: applying the same
blend to a *random* 8% of rows moves pooled points R² by +0.003, against +0.035 for the real tier —
about a twelfth as much.

---

## Three honest qualifications

**1. Most of the gain is available from something much simpler, and you should know that.**
Just using the player's own games so far — the crude running mean, no priors, no draft data — gets
you from −0.22% to **+3.09%**. The full structural machinery adds **+0.42%** on top of that.
Real, statistically solid (p = 0.0005), reproduced in every season — but it is the last fifth of
the improvement, not the first four fifths. If you want the cheap version, take the running mean
and stop. The draft-and-depth prior is the refinement.

**2. Drop "position" from the proposal.** You suggested position on the team and draft position.
Draft position works. *Listed* position — guard / forward / centre — carries no usable signal at
all here (p = 0.20; adding it moves points accuracy by −0.001). What does work is the player's
**depth-chart rank**: where they sit in their own team's minutes order. That is a much better read
of "their position on the team" than the position label, and it is the single strongest component
by a wide margin.

**3. The pure rookie case is real but tiny, and the system is already dodging it.** Rows where a
player has never appeared at all number **22** in three seasons. There, your proposal wins
enormously — the draft-based prior beats a league average by a huge margin while the model beats it
by essentially nothing. But the model only produces a forecast for 71 of the 479 season debuts in
this period; for the other 85% it declines to forecast at all. So the rookie-placeholder question,
while the most intellectually satisfying part of the proposal, is worth far less in practice than
fixing games two and three of an ordinary player's season, which is where the actual money is.

---

## Where to hand back to the model

- **Points:** the model does not clearly beat this blend until a player has **16+** appearances,
  and even then only barely. Handing back at three is safe; handing back at six loses very little.
- **Minutes:** the model pulls clearly ahead at **6–7** appearances.

A single number for both: **hand back at 3 appearances** (that is where the model's own path
switches on). If you want to squeeze points accuracy, hold the blend until 6.

---

## One implementation note

The blend can produce a very slightly negative points forecast in extreme cases (the minimum
observed was −0.10). Clip it at zero before use.
