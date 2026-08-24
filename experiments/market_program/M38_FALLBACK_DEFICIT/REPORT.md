# M38 — 8.8% of priced rows carry 42% of the deficit, and the market handles them fine

**E0-style diagnostic, NON-CLAIMING.** Not a graph node. Nothing here fits, adopts or ships a
model, and no wager-shaped claim is made. S42 untouched.

---

## The finding

On the 5,889 priced player-games (738 games, 2024–2026), the arm falls back to a **prefix mean**
for the minutes forecast on **519 rows — 8.8% of the population**. Those rows carry **42.3% of
the model's entire competitive deficit to the market**, 95% CI **[31.7, 51.9]**, game-clustered.

| fallback level | n | minutes MAE | minutes bias | model MAE | **market MAE** | response |
|---|---|---|---|---|---|---|
| 0 — no fallback | 5,370 | 4.065 | +0.155 | 5.111 | 4.915 | −0.196 |
| 2 | 351 | 4.598 | −0.834 | 6.022 | 4.968 | −1.054 |
| **3** | **168** | **7.925** | **−6.048** | **7.239** | **4.858** | **−2.381** |

**The market's MAE is flat across every level — 4.86 to 4.97.** It prices the fallback rows
exactly as well as it prices everything else. This is therefore **not an intrinsically
unpredictable population**; the degradation is entirely ours.

At level 3 the model under-forecasts minutes by **six minutes** and emits an effectively constant
value (variance 5e-05 across 168 heterogeneous player-games) — the same degenerate-constant
failure mode D150 found, still live in the repaired arm.

## Why this is not a re-run of the cold-start finding

D150 found 7.4% of rows carrying 56% of the deficit, traced it to one hardcoded constant, and the
repair shipped as arm revision 9. **D169 then measured that repair and found it moved the
competitive verdict by a net one call**, because — in its own words — "the repair helps where the
market does not compete." The cold-start rows it fixed are largely unpriced.

**These 519 rows are priced.** A repair here lands where the market actually competes, which is
precisely what the earlier one did not.

## s02 CORRECTS THIS: the realistic repair is worth ~7%, not 37%

Read the ceiling below with the correction that follows it. **A one-number repair delivers about
7% of the model-market gap, not 37%**, and the two fallback levels are different problems:

* **Level 3 (168 rows) is a genuine constant** — 3 distinct values, sd 0.007.
* **Level 2 (351 rows) is not** — 339 distinct values, sd 5.50, spanning 4.35 to 39.90. The
  model uses per-row information there and a single constant would be **worse**. So "519 rows
  take a prefix mean" was too broad; only 168 do.

**Why the constant is wrong is now diagnosed:** 21.51 is a prefix mean over a population
including bench players, applied to priced rows that are **74% starters** averaging 27.6 minutes.
A selection effect, not a modelling failure.

Replacing it with a **walk-forward** constant (prior-season priced mean, 30.09 — knowable before
any of these games, available for 127 of 168 rows) takes minutes MAE on those rows from 7.460 to
**5.405**, and moves the overall competitive response from −0.3093 to **−0.2872: 7% of the gap**.
The oracle constant does no better, so nothing is lost by staying walk-forward.

## What it would be worth, as a bound

If fallback rows scored like non-fallback rows, points MAE improves **0.1150**, 95% CI
**[0.0685, 0.1655]**, against a current gap to market of **0.3093** — **37% of the entire
model-vs-market gap**.

Set against M33's framing, which said closing the gap needs roughly a **40% cut in minutes
error** and "will not come from another feature sweep": more than a third of that gap sits in
under a tenth of the rows, in a code path that emits a prefix mean.

## How the rows were identified, and a method note worth keeping

**Not by heuristic.** A first pass grouped predictions by repeated value, found three
near-identical constants around 21.51, and identified **168 rows**. The arm's own prediction files
carry `is_fallback`, `fallback_level`, `is_cold_start` and `n_prior_games`, and using those flags
finds **519**. The heuristic would have understated the finding by two thirds and attributed
22% of the deficit instead of 42%.

The arm read is **`attempt_002`** — the repaired rev-9 attempt, checked rather than assumed.
Diagnosing a defect on a superseded attempt would have been worthless.

## What this does not establish

- **It does not say how to fix it.** It locates the deficit; it proposes no repair.
- **The parity counterfactual is a ceiling, not a plan.** "If fallback rows scored like
  non-fallback rows" assumes a repair reaches full parity, and nothing here shows that is
  achievable. These players genuinely have **0–2 prior games** (median 1).
- **The market may be using information we do not have** — confirmed lineups, beat reporting,
  late scratches. Its flat MAE proves the rows are predictable *by someone*, not that they are
  predictable *from our feature set*.
- **n is small at the worst level** — 168 rows at level 3, 519 in total.
- **No claim about wagering.** A smaller model-market gap is not an edge; M32 measured the one
  candidate strategy at −7.2%, and nothing here revisits that.


---

# s03 — two walk-forward repairs, chosen out-of-sample, worth 21% of the gap

## Level 2 is a rate problem, not a minutes problem

An oracle decomposition **within** fallback levels separates them cleanly:

| level | n | as-is | +oracle minutes | reading |
|---|---|---|---|---|
| 0 | 5,370 | −0.196 | **+0.408** | correct minutes and the model **beats** the market |
| **2** | **351** | −1.054 | **−0.592** | oracle minutes recovers **under half** — not mainly minutes |
| 3 | 168 | −2.381 | −0.362 | 85% is minutes — the constant |

Level 2's rate MAE is **0.1945** against level 0's **0.1601**, with a bias of **+0.0372**
points per minute — about a point of systematic over-prediction across 29 minutes. That is
textbook small-sample over-fitting: a player who scored well in one or two prior games gets an
inflated rate.

## The two repairs

* **Level 3** — replace the prefix-mean constant with the **prior-season** priced-population mean
  minutes.
* **Level 2** — shrink the fitted rate toward the **prior-season** priced-population mean rate.

Every constant comes from strictly earlier seasons, so all of it was knowable before the games.

## The tuning is honest, and s02's was not

s02 chose its shrinkage weight by maximising the response on the same rows it then reported —
in-sample tuning, **the very error the level-2 rows themselves commit**. Here the weight is
chosen on **2024–2025 alone** (w = 0.60) and evaluated on **2026**, which never informed it.

| | fit seasons | **held-out 2026** |
|---|---|---|
| current model | −0.3084 | −0.3108 |
| level-3 constant only | −0.2935 | −0.2751 |
| level-2 shrinkage only | −0.2818 | −0.2805 |
| **both repairs** | −0.2669 | **−0.2447** |

**21.3% of the gap closed on 2,005 held-out rows.** The repairs touch disjoint row sets and are
close to additive, and the held-out improvement *exceeds* the fit-season improvement — which
argues they generalise rather than over-fit.

## What this is not

- **The model still loses.** −0.2447 is negative; the market remains better on the priced
  population. **Closing part of a deficit is not an edge**, and nothing here revisits M32's −7.2%.
- **Neither repair is implemented.** The arm is registered and byte-locked; changing it is a new
  revision, not a diagnostic's business.
- **Coverage is partial** — the level-3 constant is available for 127 of 168 rows and the level-2
  prior for 255 of 351. First-season rows have no prior by construction.


## Robustness — two checks the 21.3% needed

**Why did held-out beat in-sample?** That is backwards from the usual pattern and needed an
explanation rather than a shrug. It is benign: **2026 simply contains more of the rows the repair
touches.**

| season | n | fallback share | level 2 | level 3 |
|---|---|---|---|---|
| 2024 | 1,726 | 7.9% | 5.6% | 2.4% |
| 2025 | 2,158 | 8.2% | 5.3% | 2.9% |
| **2026** | 2,005 | **10.3%** | 7.0% | 3.2% |

A repair that only touches fallback rows naturally does more where there are more of them. No
appeal to luck is required, and none is made.

**How certain is the magnitude?** Game-clustered bootstrap on the held-out season, 2,000 draws:

| | |
|---|---|
| gap closed | **21.3%** |
| 95% CI | **[6.3, 35.2]** |
| draws where the repair helps | **99.6%** |

**The direction is solid; the magnitude is wide.** It could be as small as 6%. Quote the interval,
not the point estimate — and note that even the top of the interval leaves the model losing.


---

# s04 — level-0 error is game script, and the obvious fix is contract-blocked

Level 0 is **91% of priced rows**, and s03 showed oracle minutes there takes the model from
−0.196 to **+0.408** — correct minutes and it *beats* the market. So what drives its error?

## Game script, cleanly

| final margin | n | minutes bias |
|---|---|---|
| 0–5 | 1,424 | **−1.177** — starters stay on |
| 6–10 | 1,540 | −0.719 |
| 11–15 | 1,011 | +0.091 |
| 16–20 | 710 | +1.507 |
| **21+** | 685 | **+3.581** — starters sit |

Correlation of minutes error with final margin: **0.2975**. The model does not anticipate how
competitive a game will be.

## The ceiling is modest

Removing the margin-conditional bias entirely: level-0 minutes MAE **4.0651 → 3.8249**, response
**−0.1957 → −0.1502** — about **23% of level-0's deficit**. This uses the **final margin**, so it
is pure oracle and bounds the prize rather than describing a plan. The margin comes from the
outcome masters, **not** from any odds archive.

## HALT — the pre-game-spread test cannot be run

The natural next step is to ask whether the pre-game spread anticipates the margin well enough
to fix this. It is prohibited:

- `data/drive_masters/master_odds.csv` carries `odds_spread` over the right seasons, but M00's
  final-state archive ruling enumerates six permitted uses, and **M00-U4 states the archive is
  for coarse descriptive context — "never a feature, never a benchmark."** This lane's stop
  condition says HALT and raise rather than stretch the enumeration.
- The cutoff-valid source, `data/odds_capture`, begins **2026-07-30 — the day the priced frame
  ends.** There is no legal pre-game spread for this window at all.

Amending the enumeration is a contract change and not a coordinator's to make silently.

## The point that outlives the block

**Even with permission, this route cannot produce edge.** Closing the gap by feeding the model
the market's own spread imports market information — it moves the model *toward* the market
asymptotically, never past it.

That distinction matters more than the block itself, because a future coordinator granted the
permission could close the gap substantially and mistake it for progress toward profitability.
It would not be.
