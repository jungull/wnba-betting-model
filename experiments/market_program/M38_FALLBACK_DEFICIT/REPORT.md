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
