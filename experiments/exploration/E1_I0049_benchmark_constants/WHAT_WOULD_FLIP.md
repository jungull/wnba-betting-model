# WHAT WOULD FLIP — judgements made under the briefed constants, re-checked under the corrected ones

Screen `E1_I0049_benchmark_constants` · PREREG sha256
`4770c3ac21a3e4e4d1c3e277d59dd7b49f1403d7e459e355b851945b58f23dfc`

**Headline: NOTHING FLIPS.** No killed cell reopens, no gate reverses, no verdict changes. Two
sentences in the ledger must be restated, one comparison must be withdrawn, and one claim survives
for a different reason than the one given.

The corrections applied below are:

| briefed | corrected |
|---|---|
| largest live effect `0.002057` | it is a **ceiling**, not an effect. Effect = **0.0023492** (n=4,517, points, walk-forward). Bound = **0.0035631** (n=5,673, ORACLE). |
| single-cell floor `0.00102` (`y_ppm`) | interval **0.00091–0.00336**; points-matched ≈ **0.00072** |
| 132-cell floor `0.00235` (`y_ppm`) | interval **0.00235–0.00974**; points-matched ≈ **0.00181** |

---

## 1. THE 213 CEILING KILLS (D125 / E1_I0047) — **NOTHING FLIPS, AND THE CHECK THAT MATTERS IS RESPONSE-MATCHED**

E1_I0047 ran four comparisons against the briefed constants. Three of them are cross-response and
should not have been made; **the fourth is response-matched and is the one that decides.**

| E1_I0047's check | its result | under corrected constants |
|---|---|---|
| 213's realised ΔR² ≥ `FLOOR_1CELL` 0.00102 | 0 of 213 (max 0.00079634 = 0.781×) | **cross-response** — D097's responses are `y_dreb / y_oreb / y_reb / y_pts / y_ast`; the floor is `y_ppm`. `NOT_COMPARABLE`. |
| ≥ `FLOOR_132` 0.00235 | 0 of 213 | same objection |
| ≥ `BEST_LIVE` 0.002057 | 0 of 213 | max 0.00079634 vs corrected effect 0.0023492 → still **0 of 213** |
| **≥ each cell's OWN injection-verified `mde80_fw`** | **0 of 213** | **THIS IS THE MATCHED CHECK.** max `realised / own mde80_fw` = **0.4713**, min headroom **2.12×**. **Unaffected by anything in this document.** |

**Verdict: all 213 stay dead.** The margin that carries them is their own per-cell, per-response
`mde80_fw`, not the programme's scalar floors. E1_I0047's conclusion was right; three of its four
supporting comparisons were denominator-mismatched and can be dropped without weakening it.

**The one number worth naming.** The top of the 213 is
`DECISION | y_dreb | B_SINGLE | R02_opp_allowed_ra_share`, n = 5,111, ceiling 0.00079634, realised
0.00079634, own `mde80_fw` 0.002373 — **0.336× its own floor**. Even a 30% floor correction of the
size measured here leaves it at 0.48×. It does not cross.

---

## 2. D114 — "THE PROGRAMME'S LARGEST LIVE EFFECT (0.002057) SITS ENTIRELY BELOW THE TEAM-LEVEL DETECTION FLOOR" — **SURVIVES, FOR A DIFFERENT REASON**

E1_I0036's team-level MDE80 is **3.51e-03 – 3.95e-03** (team-game, 1,486 rows, `N_ESWAP`), against
a player-game 4.24e-04.

| reading of the constant | value | vs 3.51e-03 (low end) | claim holds? |
|---|---|---|---|
| as briefed (the ceiling) | 0.0020572 | 0.586× | yes |
| **corrected effect** (D089 walk-forward) | **0.0023492** | **0.669×** | **yes** |
| corrected effect, in-sample same cell | 0.0033139 | 0.944× | yes, marginally |
| corrected **bound** (ORACLE) | 0.0035631 | **1.015×** | **no — it crosses** |

**D114's conclusion stands.** It stands because the sentence says *effect*, and under every
effect reading the number is below the team-level floor. It would fail under the *bound* reading —
and the figure it actually quoted, `0.002057`, is neither an effect nor a bound. **Restate D114
with `0.0023492` and it is true as written.**

*(Caveat recorded against this screen: E1_I0036's team-level floor is on rebound/assist responses,
so even this comparison is not fully denominator-matched. It is reported because D114 made it, not
because it is clean.)*

---

## 3. E1_I0046_allocation — GATE **PROCEED** — **SURVIVES, AND THE RESPONSE CORRECTION MAKES IT SAFER**

| response | family ORACLE ΔR² | × 0.00235 as briefed | × points-matched 0.00181 | × worst DECISION null 0.00974 |
|---|---|---|---|---|
| `R1_s_pts` | 0.005999 | 2.55× | **3.31×** | 0.62× |
| `R2_s_min` | 0.022916 | 9.75× | **12.66×** | 2.35× |
| `R3_s_fga` | 0.005319 | 2.26× | **2.94×** | 0.55× |

**PROCEED holds** under the response correction (margins rise), under the within-player cyclic null
(0.00428 → 1.40× / 5.36× / 1.24×), and under the published floor. It fails only against the
entity-swap **opponent-team-season** null (0.00974), which is not the matched null for a
within-player allocation feature. **No flip; the exposure is named.**

---

## 4. D123 / E1_I0043_opponent_defence — GATE **PROCEED** — **SURVIVES, MARGINS RISE**

Recorded: ceiling 0.00344 (D084 form) and 0.01094 (strict oracle) against `0.00102` → **3.37×** and
**10.73×**. Against the points-matched floor ≈ 0.00072: **4.78×** and **15.2×**. The screen's
response is points, so the correction applies in its favour. **No flip.**

---

## 5. THE INJECTION / POWER TARGETS — **CONSERVATIVE IN THE SAFE DIRECTION**

`E1_I0036` used `DELTAS = [0.002057, 0.001127, 0.000500, 0.000129, 0.000050, 0.0]`;
`E1_I0038` used `[0.0, 0.000129, 0.000500, 0.001127, 0.002057]` and certified `N_CYCLIC` at
**power 0.93 @ 0.002057**.

The corrected target is **larger** (0.0023492 as an effect, 0.0035631 as a bound). Power is
monotone in δ, so:

* every null **certified** as adequately powered at 0.002057 is **still certified** at the larger
  target;
* every cell labelled `USABLE_BUT_UNDERPOWERED_AT_0.002057` was judged against a target **12–73%
  too small**, so some of them were **more** powered than recorded, never less.

**No certification is withdrawn. The direction of the error is safe.** The labels are pessimistic,
not optimistic — which is the one direction that cannot manufacture a false negative.

---

## 6. D108 / E0_I0029 — "1.43× THE 0.002057 BENCHMARK, THE LARGEST THIS PROGRAMME HAS MEASURED" — **WITHDRAW THE COMPARISON**

D108 recorded points ΔR² **0.002951** on n = 5,111 and called it 1.43× the benchmark.

* vs D089's corrected **effect** 0.0023492 (n = 4,517, walk-forward) → 1.256×
* vs D089's corrected **bound** 0.0035631 (n = 5,673) → 0.828× — **D108 would no longer be largest**
* and n = 5,111 vs n = 5,673 vs n = 4,517 are three different row sets

**The superlative is not supportable in either direction.** D108's own finding is untouched; only
the ranking claim goes. This is the one place where a corrected constant reverses a stated ordering
— and it reverses it into `NOT_COMPARABLE`, not into a different winner.

---

## 7. D103's OWN HEADLINE SENTENCE — **UNCHANGED IN SUBSTANCE, SHARPENED**

> *"Inside a 132-cell screen the floor of 0.00235 is ABOVE the 0.0023 lead — D089 WOULD HAVE BEEN
> MISSED."*

This sentence is the **only** place in the record that quotes the lead correctly (`0.0023`, the
realised walk-forward effect) rather than the ceiling. It compares a **points** effect against a
**`y_ppm`** floor, so it is cross-response — but the correction runs in its favour twice over:

* points-matched 132-cell floor ≈ **0.00181** < 0.0023 → **D089 would NOT have been missed**
* the DECISION-stratum 132-cell interval reaches **0.00974** under the opponent-team-season null
  → it very much would have been

**So the sentence is convention-dependent, and both conventions are defensible.** The robust
version: *"D089's lead sits inside the range that an ordinary 132-cell screen on this data can and
cannot resolve, depending on the null."* That is weaker than D103's sentence and is the honest form.

---

## 8. THE COUNT SENTENCES — **TWO MUST BE RESTATED**

| sentence | status |
|---|---|
| "213 cells killed on arithmetic ceiling" | **restate as 173 candidates + 40 controls.** D125 already ruled this; it reproduces exactly here. |
| "550 exposed = 213 + 337" | those 213 are a **different set** from the ceiling 213 (\|A ∩ B\| = 2). Additionally **124 of the 337 are themselves ceiling kills**, so the two arithmetics double-count 126 cells. Neither total is wrong; the two must never be added or differenced. |
| "the decision stratum" | names **four** row sets (5,673 / 5,654 / 5,111 / 5,086). Always give n. |
| "56.3% blind" | already superseded by D122's **45.44%–67.31%**. Quote the interval. |

---

## 9. WHAT DID NOT NEED CHECKING, AND WHY THAT MATTERS

`13,879` reproduces exactly, as it has in at least nine independent screens. `5,673` and `5,654`
reproduce exactly from the frozen frame. D103's `760/1349 = 0.5633802816901409` reproduces to
sixteen digits. D084's `0.00012940370236262536` reproduces at 2.5e-17. D089's `0.0020571994`
reproduces to the digit.

**The programme's arithmetic is not the problem.** Six of the eight constants audited here are
numerically flawless; the seventh (`0.001127`) is unverifiable only because nobody wrote down its
inputs; the eighth (`213`) is a naming collision. **Every defect in this document is a labelling or
comparison defect, not a computation defect.**

---

## WHAT MOST WEAKENS THIS PAGE

* **The points-matched floors used throughout are indicative.** They are one carrier, one null, 600
  draws, and the analytic MDE80 rather than the drift-corrected fixed point. Where a judgement turns
  on them (§3, §4, §7) the direction is robust but the magnitude is not.
* **§7 is the only place a corrected constant changes a sentence's truth value**, and it changes it
  in *both* directions depending on which null you pick — which means the correct reading is that
  D103's sentence was always convention-dependent and nobody noticed, not that it was wrong.
* **§2 survives only because the sentence happens to say "effect".** Had D114 said "bound", it would
  have failed. That the claim holds is partly luck.
* **Zero reopenings is the finding.** Four agents today measured an apparent defect properly and
  retracted it. This screen adds a fifth result of the same shape: the benchmark vocabulary is
  wrong, the benchmark arithmetic is right, and no conclusion in the programme rests on the
  difference.
