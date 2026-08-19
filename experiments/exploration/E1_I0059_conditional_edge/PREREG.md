# PREREG — E1_I0059_conditional_edge

**Question:** on the population a bettor can actually act on, is there an **observable pre-game
state** in which this programme's player-points forecast beats the market — and if not, how large
an edge can we rule out?

**Written:** after a structural probe of `E1_I0058_market_benchmark/out/analysis_frame.csv`
(columns, dtypes, null counts, ranges) and **before any statistic involving `pts` was computed
for this screen.**

**Frozen hash of this file:** see `PREREG.sha256`.

**RULE OF THIS DOCUMENT.** If a prediction below fails, the failure is recorded as a FAILURE.
No threshold, split, conditioner, seed or draw count is revised after freezing. Anything computed
that is not in this file is labelled POST-HOC everywhere it appears.

---

## 0. Why this screen exists — the assessment that produced it

Roughly 58 screens have asked whether a pre-game information set predicts player outcomes, and
answered no. `D141` closed the strongest form of the question: on book-priced player-games the
de-vigged market beats our forecast by **0.4189 MAE points** and the combination adds nothing.

**But every one of those screens asked a POOLED question.** `GRAPH_POLICY §13.5` has told this
programme since 2026-08-07 to stop centring global MAE and instead ask *"where is our information
advantage strongest, what observable pre-game state predicts that advantage, and can we abstain
everywhere else?"* — and **no screen has ever run that test on the population books price.**
`D141 §8` pre-specified four subgroups and correctly gated them off, because its own decisive
coefficient was not distinguishable from zero; the gate was there to stop fishing after a
disappointing headline, and it worked. This is the separate, properly preregistered version.

Two prior findings make the question live rather than hopeful:

* `D076` measured the model as having **negative skill on thin-sample players**, and found that
  declining to forecast that group roughly doubled skill on the rest.
* `D119` found the programme's validated gains land on rows nobody would bet on — the failure was
  **where** the gains sat, not whether they were real.

A pooled loss is fully consistent with being better on an identifiable slice and much worse
elsewhere. That is the hypothesis. **It is equally consistent with being uniformly worse, which is
the outcome this screen expects.**

## 1. Population — unchanged from D141, and conditional in the same way

The frozen `E1_I0058` analysis frame: **n = 1,972 obligations, 78 players, 262 games**, season
2024 only, 2024-05-14..2024-10-20. sha256 `8605a559fc66076990055a35c3b932c9f242d665656d795e018ce2b9a547b7c8`,
re-verified at run time.

> **SELECTION STATEMENT, attached to every number this screen produces.** These are **40.2% of
> season-2024 played player-game rows** — the ones a bookmaker chose to price. Every figure here is
> conditional on that selection and says nothing about unpriced players.

**Partition.** 2024 only; 2025 and 2026 are never read. Inherited from the frozen frame and
re-asserted at run time.

## 2. The response — signed error advantage

For each row *i*:

```
d_i = |M2_i - pts_i| - |F1_i - pts_i|
```

**`d_i > 0` means our model was closer than the market on that row.** M2 is the de-vigged market
estimate and F1 the model's `E[points | active]`, both exactly as frozen in `D141`.

`mean(d)` over the whole frame is **already known to be negative** (D141: model MAE 5.3232 vs
market 4.9043, so mean(d) = −0.4189). That is not re-tested. **The question is entirely about
conditional structure.**

## 3. The five conditioners — pre-specified, and why exactly these

Every one is **knowable before tip** and is **not derived from `pts` or realised `minutes`**.
Chosen from the structural probe on prior grounds, not on any relationship to `d`:

| id | conditioner | split | prior reason |
|---|---|---|---|
| **C1** | `n_prior_games` | median | `D076` measured negative skill on thin-history players. The single strongest prior. |
| **C2** | `min_hat` | median | The model's own pre-game minutes forecast. `D131` found minutes is the only real budget. |
| **C3** | `M1` | median | Market line level = volume tier. `D134` found twelve of sixteen survivors were a volume tautology. |
| **C4** | `line_sd` | **> 0 vs = 0** | Cross-book disagreement. Median is 0.000, so a median split is degenerate; the honest split is "books disagree at all" vs "books agree exactly". |
| **C5** | `is_fallback` | its own boolean | The cold-start path. `D092`/`D139` concern exactly these rows. |

**Excluded, and why, decided now:** `pred_sd` is **constant** across all 1,972 rows (single value
5.41173741069646 — `D136`'s finding that shipped uncertainty is an intercept, confirmed here
structurally), so it cannot condition anything. `lead_h` takes six values spanning 0.57–1.157 h and
is effectively constant. `overround`, `n_books`, `is_home`, `starter_flag` are **not tested** —
holding the family to five keeps the multiplicity correction meaningful.

**Multiplicity:** five conditioners, **Bonferroni α = 0.05 / 5 = 0.01**. Declared now.

## 4. What counts as an edge — all three required

For a subgroup to be called an edge, **all three** must hold:

1. **`mean(d) > 0`** in that subgroup — the model is actually closer than the market;
2. **the 95% cluster-bootstrap interval excludes 0**, at α = 0.01 (i.e. a 99% interval);
3. **`mean(d) ≥ 0.10` points** — the same materiality floor `D141` used. An edge below the floor
   is a TIE regardless of any interval.

**A subgroup passing 1 and 2 but failing 3 is recorded as REAL BUT IMMATERIAL, not as an edge.**

## 5. Inference — clustering, nulls, seeds

Rows are not independent; classical t-statistics have been found untrustworthy in this programme
twice, independently. **No classical or cluster-robust SE is used for any headline interval.**

**5.1 Cluster bootstrap.** Pairs bootstrap resampling whole clusters with replacement, recomputing
the subgroup mean each draw, percentile intervals.
* `BOOT_GAME`: cluster = `gid` (262 clusters). **seed 20260819, 5000 draws.**
* `BOOT_PLAYER`: cluster = `player_id` (78 clusters). **seed 20260819, 5000 draws.**
* **The headline interval is the WIDER of the two**, declared now, before seeing either.

**5.2 Permutation null.** The subgroup label is reassigned **at the game level** (whole games move
together), preserving `d`'s within-game structure and destroying only the alignment between the
conditioner and the advantage. **seed 20260820, 5000 draws.** Two-sided p on the subgroup-mean
difference, with the +1/+1 correction.

*Why game-level and not row-level:* a row-level shuffle would break the clustering that makes these
rows dependent and produce an anticonservative p, which is the exact defect `D093`/`D115`/`D117`
spent four decisions repairing.

**5.3 MDE, computed and reported BEFORE any null is interpreted (`D136`).**
`MDE = 2.802 × SD_bootstrap(subgroup mean)` at 80% power, α = 0.05. **If the MDE for a subgroup
exceeds the 0.10 materiality floor, that subgroup's null is reported as UNINFORMATIVE, not as
evidence of no edge.**

## 6. The four preregistered predictions

| id | prediction | threshold |
|---|---|---|
| **P1** | The model beats the market **nowhere**: no conditioner produces a subgroup meeting all three §4 criteria | zero subgroups qualify |
| **P2** | `C1` (thin history) shows the model **relatively worse** on the low-`n_prior_games` half | `mean(d)` lower in the low half, consistent with `D076` |
| **P3** | The screen is **powered** to rule out a material edge | MDE < 0.10 in at least 3 of 5 conditioners |
| **P4** | The model's disadvantage is **broad rather than concentrated** | the spread of subgroup `mean(d)` across all ten subgroups is < 0.40 points |

**P1 is the expected outcome and a clean confirmation of it is the publishable result.**
P2 is a sanity check against an independent prior finding. P3 decides whether a null means
anything. P4 distinguishes "uniformly beaten" from "beaten on average but competitive somewhere".

## 7. If an edge IS found

It is a **LEAD, never a RESULT** (`GRAPH_POLICY §13.1`). It may not be cited, may not size a bet,
and may not be reported to the user as an edge. It would require a preregistered E2 on the
confirmation partition, which this screen does not touch and does not request.

**Additional scepticism required by this programme's own record:** any surviving subgroup must be
checked against `D086` (read the construction, not the label), `D134` (is it a volume tautology?)
and `D119` (does it reach rows anyone would bet?). Those checks are named now so that passing them
is not mistaken for having thought of them afterwards.

## 8. Registered limitations, in advance

* One season, one league, 1,972 rows, 78 players. **A screen. It promotes nothing.**
* Conditional on the book-priced population (§1).
* Ten subgroups from five binary splits is a small family, but it is still a family; the Bonferroni
  correction is the whole defence and it is declared, not chosen later.
* Median splits discard within-half structure. A continuous interaction would be more powerful and
  is deliberately not used, because it would multiply the researcher degrees of freedom.
* `d` is an absolute-error difference, so it is insensitive to the direction of the miss.

## 9. Evidence level claimed in advance

At most **E1**. E2/E3 are impossible here by construction: the confirmation partition may not be
touched.
