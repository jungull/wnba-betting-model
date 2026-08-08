# E1_I0027 — the canonical reference ladder, and what the ledger's leads are worth on it

**Ladder spec sha256 `8079f632ea1bc159bdb993e1e1efdf49d6f73c11e5ade1b5398bdffb8dac24db`, frozen by
`s03_prereg.py` before any re-priced figure was computed.**

---

## 1. The answer to the operative question

**The ranking does not change — and only two of the five leads could be ranked in the first place.**

On an identical 3,165-row set with one denominator, D099's opponent-defence effect outranks D089's
teammate-volume channel before re-pricing (+0.003335 vs +0.002349) and after (+0.004550 vs
+0.003572). Zero rank swaps. For those two leads the reference problem is a **reporting** problem,
not a decision problem.

That sentence is true and, on its own, misleading. Two things sit underneath it.

**First, the standing of one lead changes even though its position does not.** D089 is filed in its
own decision entry as *"the programme's best usable lead."* Against its own reference it clears a
correct-level null on these rows (cluster sign-flip p 0.0377). Against the canonical rung it does
not: cluster p 0.2067, within-player cyclic p 0.0779. Its point estimate is *larger* on the better
reference; its evidence is weaker. D099 clears everywhere (p 0.0022 clustered, p 0.0010 cyclic).
Ordering by magnitude was safe. Treating "top of the list" as "established" was not.

**Second, three of the five leads were never commensurable.** D074/D079 is measured on
restricted-area attempt counts. D072 is measured on turnovers per 100 offensive possessions. D092 is
an MAE skill ratio, not a dR2 at all. No denominator convention repairs a response mismatch — D072's
own ruling 4 said so — and the programme has been ordering these against each other regardless. The
inconsistent-reference problem is real, but the larger defect this screen found is that the ranking
was assembled from quantities that are not the same kind of thing.

**Third, and least expected: a better reference moves numbers in both directions.** Holding the row
set fixed, D089's increment **grows** to 1.52× and D099's points increment **shrinks** to 0.85×. Any
intuition of the form "a proper reference will cut every lead down" would have been wrong half the
time here.

---

## 2. What the ladder is

Five rungs, weakest to strongest, every one strictly prior-games-only, all reproducible from a
single function of `(frame, target)` — `refladder.ladder`. Six targets: points, minutes, attempts,
points-per-minute, rebounds, assists. Full definition and the time-window table are in
`REFERENCE_LADDER.md`.

| rung | what it is |
|---|---|
| `R0_LEAGUE` | expanding same-season league value over strictly earlier **dates** → previous season → GRAND (78 rows, all in the frame's opening season, never in an evaluation set) |
| `R1_PLAYER_EXPAND` | the player's own expanding prior mean — **the programme's incumbent reference** |
| `R2_EWMA_TUNED` | tuned EWMA, form/half-life/shrinkage taken from D094's 15,048-cell grid |
| `R3_RATE_X_MINUTES` | EWMA(target per minute) × EWMA(minutes, half-life 2); degenerate for minutes and returned as NaN there |
| `R4_RICH_LOOKUP` | walk-forward OLS blend of the player's own prior measurements of the target **and its components**; coefficients fitted on seasons strictly earlier than the scored season |

D094's grid was read, not repeated. The half-lives it measured (minutes 2, attempts 5, points 8,
points-per-minute 40), its finding that EWMA beats SMA beats expanding, its finding that shrinkage is
weak and **never toward the league**, and its finding that a history minutes-floor hurts
monotonically are all imported wholesale. The only hyperparameters chosen inside this screen are the
rebound and assist half-lives (5 and 8), selected on seasons 2021–2022 only, frozen and hashed before
any re-priced figure — and used in no re-priced figure, since every re-price is on points or
points-per-minute.

**How much the reference alone is worth**, on 9,808 evaluation rows:

| target | worst rung MAE | best rung MAE | spread | the incumbent R1 is beaten by |
|---|---|---|---|---|
| points | 6.266 | 4.064 | 35.1% | 2.43% |
| minutes | 9.558 | 4.860 | 49.1% | 7.80% |
| attempts | 4.502 | 2.507 | 44.3% | 4.79% |
| points-per-minute | 0.2083 | 0.1798 | 13.7% | 2.33% |
| rebounds | 2.615 | 1.773 | 32.2% | 3.14% |
| assists | 1.745 | 1.198 | 31.4% | 3.38% |

The last column is the size of the reporting error that has been sitting under every skill figure in
this ledger: any number expressed as skill against R1 is inflated by roughly that much, and by 7.8%
on minutes — which is the mechanism behind D094's 8.12-point swing.

**The ladder is ordered by R², on all six targets, R0 < R1 < {R2, R3} < R4, with every step from R0
to R2 clearing the clustered paired sign-flip at the 4,000-draw floor.** It is *not* identically
ordered by MAE — R3 edges R4 on points and assists, R2 edges R4 on minutes. That is reported rather
than smoothed. And **the order is not stratum-invariant**: R4 is best by R² on the decision stratum
but is the *worst* of R2/R3/R4 by MAE on the cold-start-heavy tier frame. A rung is not strong in
the abstract; it is strong on a row set, and any future screen quoting a rung must quote the row set
with it.

---

## 3. The re-price table

Full table in `reprice_table.csv`; every rung in `reprice_by_rung.csv` and
`d092_reprice_by_rung.csv`.

**Read the anchors before the ratios.** R4 is undefined in a frame's first season, and that cascades
into the walk-forward fit, so the common scored set is 2023–2024 (n=3,165) rather than the leads'
published 2022–2024 sets (n≈4,515). Comparing a published figure straight to a re-priced one would
confound the row set with the reference. Each lead's own construction was therefore re-run on the
common rows first, which splits the two effects apart:

| lead | response | published | own construction, common rows | **row-set effect** | on the canonical rung | **reference effect** |
|---|---|---|---|---|---|---|
| D089 teammate volume | points | +0.0023492 | +0.0023570 | ×1.003 | **+0.0035723** | **×1.515** |
| D099 opponent defence | points | +0.0033354 | +0.0053434 | ×1.602 | **+0.0045499** | **×0.851** |
| D099 opponent defence | ppm | +0.0050281 | +0.0102973 | ×2.048 | **+0.0112795** | **×1.095** |

D099's headline 1.36× and 2.24× ratios against the published figures are therefore *mostly the row
set*, not the reference. D089's 1.52× is *entirely the reference*. Anyone quoting a single ratio
without that split is repeating the error this screen exists to fix.

**D092 is the largest single finding in the table**, and it is the one measured on the same 13,879
rows as its published figure, so no anchor is needed:

| reference | MAE of the reference | skill of the identical operating rule |
|---|---|---|
| D076's expanding running mean (**as published**) | 4.1816 | **+3.506%** |
| `R0_LEAGUE` | 6.1252 | +34.12% |
| `R1_PLAYER_EXPAND` | 4.0973 | +1.52% |
| `R2_EWMA_TUNED` | 4.0439 | **+0.22%** |
| `R3_RATE_X_MINUTES` | 4.0165 | **−0.46%** |
| `R4_RICH_LOOKUP` | 4.2398 | +4.83% |

Nothing about the rule changed. **The sign of its headline depends on the rung.** Against a tuned
EWMA of the player's own prior games the cold-start fix is worth two-tenths of one percent; against
the rate × minutes composite it is negative. Note also that D076's reference is *worse than a plain
player expanding mean* (4.1816 vs 4.0973) — which is the degeneracy D092's own screen diagnosed and
then quoted the headline against anyway.

The reproduction is exact: the operating rule's pooled MAE recomputes to 4.035010863560213 against a
published 4.035010863560213, and the skill to 0.035062396968632 against 0.03506239696863178.

**Two leads were skipped, not approximated.** D074/D079's response is a *zone-level* attempt count
and its base is a five-zone forecast system; the ladder defines a rung for total attempts, and
substituting it would be a different quantity wearing the same name. D072's response is a turnover
rate that is not one of the six targets and its base is a fitted pressure model rather than a
reference forecast. Both require re-running their pipelines. (D072 is worth one note: it is the one
case in the ledger where the reference *was* already corrected — D072 re-ran it on discovering the
baseline read the future, and 0.000413 is the post-correction number.)

---

## 4. The denominator rule

Two dR2 figures are comparable **only if all five hold**:

- **D1 — same response.** The same variable in the same units.
- **D2 — same scored rows.** The identical row set, not merely the same *n*.
- **D3 — same denominator.** SST on that full scored row set, about its own unweighted mean. A
  subset's SST is never a valid denominator for a figure that will be compared to a stratum-wide one.
- **D4 — same weighting** in all three of the fit, the SSE and the SST.
- **D5 — same base.** Both increments over the same reference model.

Failing **D2 alone is repairable**: re-express both as `SSE_reduction / SST_common`, `SST_common`
being the SST of the common scored rows — which is what D099 did. **Failing D1 is not repairable at
all** and no denominator convention rescues it.

This screen enforces D3 structurally rather than by discipline: `refladder.paired_dr2` and every dR2
in `s05` take the denominator as an explicit argument, so there is no code path that can compute a
subset's own SST by accident.

**Quoted figures in the ledger that sit on non-comparable denominators:**

| figure | which clause it fails | status |
|---|---|---|
| D098 +0.023863 (defence, top volume tercile) | **D3** — subset SST, 36% of the stratum's | already superseded by D099 ruling 2 |
| D098's "6.2× the largest ceiling this programme has measured" | **D3** — same inflated denominator | withdrawn by D099 |
| **D089's "the prior-only ceiling is ~1.8× D079's mix ceiling and ~16× D084's conversion ceiling"** | **D1** — D089's ceiling is on **points**, D079's on **zone attempt counts**. These are variance shares of different responses; the comparison reads as a size ordering and is not one | **not previously flagged — raised here** |
| D072's pair 0.002795 (weighted) / 0.000413 (plain) | **D4** — weighting | handled by D072 rulings 2–3; the risk is a successor quoting one alone |
| D092's +3.51% pooled points skill | **D5**, plus a metric mismatch (an MAE ratio, not a dR2) | re-priced here; its sign depends on the rung |
| D074's +0.019139 conditional-on-realised-FGA increment | **D2/D5** — conditioned on a realised quantity | handled by D079; the pair must never be quoted as one number |
| D090's +46.4% / +7.1%; D094's +3.71% / −4.41% | **D5** — one forecast, two references | already corrected in their own entries; listed so the pattern reads as one pattern rather than four incidents |

---

## 5. Controls

- **Negative control.** `G01_noise` added over every rung: |dR2| ≤ 3.0e−4, cluster p 0.57–0.98,
  cyclic p 0.609. Dead at every rung, so the machinery is not manufacturing increments out of the
  rung's residual structure.
- **Correct-level nulls only.** The paired comparisons use the shared kit's
  `paired_forecast_comparison`, sign-flipping whole (season, player) clusters. The prior-history
  regressors use `SCHEME_WITHIN_CYCLIC` — D093 measured that a plain within-player shuffle is
  anticonservative for exactly this shape (p 0.0015 where the honest null gave 0.39) and the kit now
  refuses it. Row-level p is computed for contrast only and always printed beside the clustered one.
- **The kit was imported, not reimplemented.** D096 closed five false-assurance defects in this
  machinery and the repaired suite carries 224 assertions; reimplementing would forfeit that.
- **The champion was never fitted.** Only its stored forecast columns were read.
- **Partition.** 2021–2024 only. `assert_partition` tests values, never file text, and deliberately
  does not fire on year-valued *player attributes* such as `draft_year` — that is D092's K4 defect,
  whose obvious workaround (`season_cols=['season']`) hides real leaks. Season disjointness is
  asserted before any previous-season aggregate is used. 2025/2026 was never read, joined, plotted
  or described.

---

## 6. Where I could have cheated

1. **R3 was wrong on the first run of `s04` and was corrected.** The rate × minutes form was applied
   to points-per-minute, which is already a rate; it produced MAE 8.238 and R² −1190. The fix defines
   R3 for a rate target as the ratio of prior component sums and pins the composite's minutes arm at
   half-life 2 for level targets — which is what `REFERENCE_LADDER.md` already said. No re-priced
   figure existed at that point and `s05` had not been written, but it is a rung changed after seeing
   a number and it is declared. The first run's log is preserved verbatim as
   `run_log_s04_FIRSTRUN_r3_defect.txt`.
2. **The canonical rung flatters D092.** `R4_RICH_LOOKUP` was fixed as canonical in the
   preregistration, before any re-price, and on the decision stratum the choice is defensible on its
   merits (best R² there). On D092's tier frame it is *not* the strongest rung — by MAE R4 is 4.2398
   against R3's 4.0165. **Had I picked R3 as canonical, D092 would have re-priced negative.** Every
   rung is in `d092_reprice_by_rung.csv` and the R2/R3 figures are in the reprice table's note
   column, so no reader has to take the R4 headline.
3. **The re-price row set is 30% smaller than the published ones** (3,165 vs ≈4,515), for the
   structural reason above. Handled by the same-rows anchors, but no arithmetic makes the rows
   reappear.
4. **Rebound and assist half-lives were selected inside this screen** — on 2021–2022 only, from
   D094's unchanged grid, frozen before any re-price, and used in no re-priced figure.
5. **Two leads were skipped rather than approximated.** The tempting move for D074/D079 was to
   substitute the total-attempts rung for the zone-attempts response. It was not made.
6. **The direction of the reference effect was not predicted in advance.** That D089 grows and
   D099's points figure shrinks is descriptive, not a confirmed prediction.
7. **The D099 anchors are reconstructions, not byte reproductions.** E1_I0025 stores no frame, so
   D099's construction was rebuilt from D098's preregistered base list joined to the defence column
   in E0_I0016's frozen frame. It is close in form; it is not certified equal to D099's code path.

---

## 7. What a successor should do with this

- **Use `refladder.py`.** It takes a frame and a target and returns every rung. That reusability is
  the deliverable; the re-price is the demonstration.
- **Quote the rung and the row set with every skill figure**, the way a measurement carries its
  units. `+3.51%` is not a number about the cold-start rule; `+3.51% against D076's expanding mean on
  13,879 rows` is.
- **Stop ranking across responses.** Three of the five leads in this table are not comparable to each
  other and never were. A ranking table should carry a `comparable_family` column and refuse to sort
  across it — `ranking_change.csv` is written that way.
- **Re-open D089's standing.** It keeps its position and loses its significance. That is a question
  about the lead, not about the ladder, and it should be settled on its own terms before the lead is
  described as best-evidenced again.
