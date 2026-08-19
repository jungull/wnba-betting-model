# NOTES — E1_I0059_conditional_edge

**Decision D150.** Evidence level **E1**, and E1 is the ceiling: single partition, 2024 only.
Prereg frozen `853c3617c8f4e640798be22f022c83576379cafcddc29b0ee2175db3f474bdf9` at
2026-08-19T17:45:50Z, before any statistic involving `pts` was computed for this screen.

Run on the user's instruction to *"assess why it has failed thus far then figure out what will
work."*

---

## 1. The question, and why nobody had asked it

Roughly 58 screens have asked whether pre-game information predicts player outcomes. All of them
asked a **pooled** question. `GRAPH_POLICY §13.5` has said since 2026-08-07 to stop centring global
MAE and instead ask *where* the advantage lives and whether we can abstain elsewhere — and no
screen had ever run that on the population books actually price.

A pooled loss is fully compatible with being better on an identifiable slice. That was the
hypothesis. **It is false, and the way it is false is the useful part.**

## 2. The headline: the model loses everywhere, and it is not close

Response is `d = |market error| − |model error|`; **positive means our model was closer.**

| subgroup | n | mean(d) | 99% CI | MDE |
|---|---|---|---|---|
| established (`n_prior_games` > 19) | 965 | **−0.165** | [−0.295, −0.035] | 0.136 |
| thin history (≤ 19) | 1007 | **−0.663** | [−0.984, −0.401] | 0.317 |
| high expected minutes | 986 | −0.255 | [−0.399, −0.118] | 0.148 |
| low expected minutes | 986 | −0.583 | [−0.890, −0.295] | 0.324 |
| **high volume (line > 14.5)** | 856 | **−0.693** | [−1.027, −0.416] | 0.338 |
| low volume (line ≤ 14.5) | 1116 | −0.208 | [−0.322, −0.101] | 0.121 |
| books disagree | 937 | −0.567 | [−0.849, −0.334] | 0.283 |
| books agree exactly | 1035 | −0.285 | [−0.464, −0.126] | 0.182 |
| **cold start (`is_fallback`)** | 146 | **−3.157** | [−4.590, −1.876] | 1.484 |
| not cold start | 1826 | −0.200 | [−0.292, −0.112] | 0.099 |

**All ten subgroups are negative. All ten 99% intervals exclude zero on the negative side.**
Ten independent chances to find a slice where we are merely competitive; ten losses.

**P1 PASSES.** The model beats the market nowhere this screen looked.

### The power caveat, stated precisely rather than waved

**P3 FAILS**: zero of five conditioners have MDE < 0.10 in *both* halves, so this screen could not
have detected a *small* edge in most subgroups. **That does not weaken the finding**, and the
distinction matters: low power limits the ability to detect a *small* effect, not the trust in a
*large* one that was detected. Every interval here excludes zero decisively. What this screen
cannot rule out is an edge below roughly 0.10–0.34 points depending on the slice. What it rules
out comfortably is any edge worth acting on.

## 3. The finding that actually matters: the loss is concentrated, not broad

**P4 FAILS, and its failure is the most useful result in the screen.** Predicted spread across
subgroups < 0.40; observed **2.99**. The disadvantage is not spread thinly — it is piled onto a
small, identifiable group.

Sorting every row into three disjoint buckets *(post-hoc, not preregistered)*:

| bucket | n | share | mean(d) | model MAE | market MAE | share of total deficit |
|---|---|---|---|---|---|---|
| **A. cold start** | 146 | 7.4% | **−3.157** | **7.794** | 4.637 | **56%** |
| B. thin history, not cold start | 861 | 43.7% | −0.240 | 5.150 | 4.910 | 25% |
| C. established | 965 | 48.9% | −0.165 | 5.104 | 4.940 | 19% |

The three contributions sum to −0.4188 against a pooled −0.4189 — the decomposition is exact.

**Seven percent of rows carry fifty-six percent of the entire deficit.** On those rows our model
misses by 7.79 points while the market misses by 4.64.

**And the market is BETTER on cold-start rows than on established ones** (4.637 vs 4.940). The
players we handle worst are the ones the market handles *best*. Cold start is not an opportunity
we have failed to exploit; it is a hole we are digging.

Cold-start rows are a **strict subset** of thin-history rows — zero fallback rows have more than 19
prior games — so this is one phenomenon, not two.

## 4. What abstention buys, measured

*(post-hoc)*

| policy | rows kept | mean(d) | model MAE |
|---|---|---|---|
| forecast everything | 1972 (100%) | −0.4189 | 5.3232 |
| **decline cold-start rows** | 1826 (92.6%) | **−0.2000** | **5.1257** |
| decline cold start + thin history | 965 (48.9%) | −0.1646 | 5.1042 |

**Declining 7.4% of rows more than halves the deficit.** Declining a further 43.7% buys almost
nothing beyond that — the returns stop immediately after the cold-start rows are gone.

**This is not an edge.** After abstaining we are still behind by 0.20 points with an interval
excluding zero. It is the removal of a self-inflicted wound, and it is the single largest
improvement available to the player model — bigger than anything 58 screens of feature search
produced, and it requires no new data, no refit and no new information. `D076` measured the same
shape on a different response; this confirms it on the population that matters.

## 5. Why the programme failed — the assessment, grounded in its own record

**1. It asked the pooled question for 58 screens.** Its own policy told it not to, on
2026-08-07, in §13.5. This screen is the first execution of that instruction on the priced
population, and it took ninety minutes.

**2. It optimised against baselines that could not locate it.** The market benchmark did not exist
until `D141`, twelve days ago. Before that, "better" meant better than a reference of our own
choosing — and `D087`/`D136` record the same result moving 6.5×, 4.6× and 8.12 points on reference
choice alone. A programme that cannot see the scoreboard cannot tell whether it is improving.

**3. It attacked the market's strongest ground.** The model is worst on **high-volume players**
(−0.693) and best on low-volume ones (−0.208). Books price their headline markets hardest. We
spent four campaigns and ~1,000 tests on shooting efficiency (`D081`/`D084`/`D085`/`D087`), which
is precisely the quantity the market prices most carefully.

**4. Half its nulls could not see their own best finding** (`D103`), so "no effect" frequently
meant "could not have detected one". The machinery was repaired across `D115`–`D120`, but the
screens run before that remain measured on the weaker instrument.

**5. It measured a poorer information set than its own shipped code** (`D138`), and only learned
this on 2026-08-17.

**6. It never separated the population it could act on from the one it could not** until `D119`,
and even then did not act: the gains it validated landed on rows nobody would bet.

Note what is *not* on this list: dishonesty, or bad statistics after `D120`. The methodology is
now unusually good. **The failure was one of aim, not of rigour.** Thirty-four decisions went to
how to measure; comparatively few went to where to look.

## 6. What will work — and what the evidence says will not

### Closed, on this evidence

**Beating the posted line on player points, for priced players, using a pre-game fundamental
model.** Ten slices, ten losses, every interval excluding zero. Combined with `D141`'s
encompassing result — the model adds 0.005 MAE points to the market out-of-fold against a 0.10
floor — this path is not merely unproven, it is **measured and lost**. Further feature search
against this target is, on the record, the worst available use of effort.

### The trap in "the unpriced 60%"

The obvious retort is that this screen only covers book-priced rows and the other ~60% is
untested. That population is **commercially unreachable by construction: you cannot bet a player
the book does not price.** Being better than the market where there is no market is a modelling
curiosity, not a revenue path. Any future proposal to attack it should carry that sentence.

### Live, and needing no forecasting edge at all

The `M28` board's other lanes do not require beating anyone's forecast:

* **arbitrage** — locked arithmetic on witnessed prices, needs no opinion;
* **middles and dislocations** — bounded-risk structure, needs no opinion;
* **promotions** — a disclosed subsidy, valued against the market's own consensus (`D144`);
* **line shopping** — free, mechanical, and currently unexploited.

**This is where the measured value in this programme now sits**, and one of them is already
shipped and running on live prices. `D145` showed the binding constraint there is capture cadence,
which was raised today.

### The one fundamental-model action worth taking

**Stop forecasting cold-start rows.** Measured, free, and worth more than any feature found so
far. It does not create an edge; it stops donating one. Implementing it is a production change
gated on `S42` and is not requested here.

## 7. What this screen does NOT say

* It does not say the model is bad at basketball. It says it is worse than a bookmaker on the
  players a bookmaker chose to price, in 2024, on a 40.2% selection.
* It does not rule out an edge smaller than ~0.10–0.34 points depending on slice. It rules out one
  worth acting on.
* It tests **five** conditioners. Others exist; they were excluded to keep the Bonferroni
  correction honest, not because they were tried and failed.
* It is a screen. **It promotes nothing and kills nothing outside its own scope.**

## 8. Reproduce

```
python s01_edge.py      # verifies both hashes, then runs; writes FINDINGS.json + run_log_s01.txt
```

Seeds are frozen in the prereg: bootstrap 20260819, permutation 20260820, 5,000 draws each,
Bonferroni α = 0.01, materiality floor 0.10.
