# DIAGNOSTIC — why the model loses 7.79 points on cold-start rows

**E0 / characterisation. NON-CLAIMING (`GRAPH_POLICY §13.1`).** This is not a screen, tests no
preregistered hypothesis, and may not be cited as evidence for anything. It exists to answer one
follow-up question raised by `D150`: on the 7.4% of rows carrying 56% of the model's deficit, is
that deficit a **limit** (the information genuinely is not there) or a **defect** (the information
is there and we are not using it)?

**It is a defect, and it is one number.**

---

## 1. The finding

On the 146 cold-start rows in the `D141` frame:

```
distinct values of the model's forecast F1 : 1   ->  8.72211660329531
distinct values of the minutes forecast    : 1   ->  21.5175239402901
```

**The model emits a single hard-coded constant for every cold-start player**, irrespective of who
they are, who they play, or how long they are expected to be on court.

|  | cold start (n=146) | not cold start (n=1826) |
|---|---|---|
| mean actual points | **15.610** | 14.495 |
| mean model forecast | **8.722** | 14.813 |
| mean market estimate | 14.777 | 14.663 |
| **model bias** | **−6.887** | +0.318 |
| market bias | −0.833 | +0.169 |
| model MAE | **7.794** | 5.126 |
| market MAE | **4.637** | 4.926 |
| sd of model forecast | **0.000** | 4.601 |
| mean expected minutes | **21.518** | 30.773 |
| mean actual minutes | **31.244** | 30.722 |
| **minutes bias** | **−9.727** | +0.051 |

Both fallback levels (2 and 3) emit the identical value, so this is one code path, not two.

## 2. Why this is a defect rather than a limit

Three facts, each independently sufficient:

1. **The market achieves 4.637 MAE on exactly these rows** — *better* than its own 4.926 on
   established players. The outcome is not unusually hard to forecast. The information exists and
   somebody else is using it.
2. **These are not marginal players.** They played **31.2 minutes** on average — indistinguishable
   from established players' 30.7. The model assigns them a bench-sized minutes forecast (21.5) and
   a bench-sized scoring forecast, and they are starters.
3. **A constant cannot be a forecast.** Zero variance across 146 heterogeneous player-games means
   the model is contributing no information at all on these rows; it is contributing a wrong prior.

## 3. What a trivially better constant would be worth

*Diagnostic arithmetic. The 14.495 anchor is the mean of non-cold-start 2024 rows and is therefore
**RETROSPECTIVE** — it is a measuring stick for the size of the defect, **not** a proposed fix.*

| forecast on cold-start rows | MAE |
|---|---|
| de-vigged market M2 | 4.637 |
| raw market line M1 | 4.668 |
| **constant 14.495** *(retrospective anchor)* | **5.849** |
| **current model — constant 8.722** | **7.794** |

Swapping one constant for a better one is worth **+1.945 MAE on those rows**. Because they are
7.4% of the frame, pooled model MAE would move roughly:

```
5.3232  ->  ~5.1792        (market: 4.9043)
```

**That is a larger single improvement than anything ~58 screens of feature search produced, and it
comes from changing one number.**

## 4. What it does NOT do

**It does not create an edge.** Even fully repaired to the retrospective anchor, the model sits at
~5.18 against the market's 4.90 and remains behind. `D150`'s conclusion is unchanged: the model
beats the market nowhere. This reduces a self-inflicted deficit; it does not manufacture skill.

It also does not license the 14.495 constant. **A production fix must use only information legal
at the forecast cutoff** — a prior-season or training-window anchor, not the 2024 outcome mean used
here to size the problem.

## 5. This was already known, and the fix is already authorised

This is not a discovery so much as a quantification of something the ledger records:

* **`D092`** is titled *"THE USER'S COLDSTART PROPOSAL IS VALIDATED **AND THE CHAMPION EMITS A
  CONSTANT**"* — the constant emission was identified there.
* **`D137` ruling 2** authorised cold-start tiering for implementation, requiring it to reproduce
  its validated numbers under test.
* **`D139`** found the authorised rule *"is not the one that was validated"* — its `4.02` came from
  a variant including listed position, while its own ruling says drop position, which yields
  `4.032479`. The user must re-rule on which object is being authorised.

**So the defect is known, a fix was validated, the fix was authorised, and it has not landed
because the authorised object is ambiguous.** What this diagnostic adds is the first measurement of
what landing it is worth **against the market benchmark** rather than against an internal baseline —
which is the number that decides whether it is worth the user's attention.

## 6. What should happen next

1. **Re-rule `D092`/`D139`** — a USER item, unchanged by this diagnostic, now with a price attached.
2. **A preregistered cold-start screen** using only cutoff-legal anchors, measured against the
   market on this same frame. This diagnostic deliberately does **not** do that: it used a
   retrospective anchor to size the problem and would be the wrong instrument for accepting a fix.
3. **Until either lands, abstention is the interim answer** (`D150` §4): declining these rows more
   than halves the pooled deficit and requires no code change at all.
