# REFERENCE — what tuning the trailing-minutes estimator is worth, on its own

Screen `E1_I0053_minutes` · `PREREG.md` sha256
`ac373cc884166e263ddfae43466932de430d0f046966c5d918dc3c3853a1168d`
Evidence: `REFERENCE_TUNING.csv`, `REFERENCE_WORTH.csv`, `nulls/REF__*.npz`, `out/s02.txt`.
**Established before any candidate was measured**, because D094's headline was withdrawn for testing
against a weak benchmark and `E1_I0046` found the tuning worth more than any candidate it tested.

---

## THE ANSWER

**On the decision stratum in the clean 2023–24 window, tuning the trailing-minutes reference is
worth ΔR² +0.016456 over an untuned halflife-5 EWMA and +0.050624 over the literal trailing-5
arithmetic mean — and the best candidate this screen found anywhere is +0.006644. The tuning alone
is worth 2.5× the best candidate against the nearer benchmark and 7.6× against the further one.**

Response **`minutes` (LEVEL)**, arm **RAW**, row set **DECISION ∩ 2023–24, n = 3,167 in 764
team-game blocks**, SST `Σ(y − ȳ)²` about the unweighted mean = **132,506.769701 min²**, no
weighting, base `[1, B_TUNED]`, **walk-forward** fit, statistic **paired-forecast ΔR² with shared
SST**, null **paired cluster sign-flip over the 764 team-game blocks, 2,000 draws**.

| contrast, `R1_min` / RAW / DECISION / 2023–24 | R² | ΔR² | null sd | z | p | analytic MDE80 (2.80·sd) | × its own floor |
|---|---:|---:|---:|---:|---:|---:|---:|
| **`B_TUNED`** | **+0.228338** | — | — | — | — | — | — |
| vs `B_NAIVE` (EWMA h = 5, no shrinkage) | +0.211882 | **+0.016456** | 0.004887 | **+3.34** | **0.0010** | 0.013684 | **1.20×** |
| vs `B_TRAIL5` (literal trailing-5 mean) | +0.177714 | **+0.050624** | 0.009038 | **+5.63** | **0.0005** | 0.025308 | **2.00×** |
| vs `B_UNIFORM` (equal split of the team's minutes) | −1.825889 | **+2.054226** | 0.093266 | +22.01 | 0.0005 | 0.261146 | 7.87× |

`p = 0.0005` is the attainable floor at 2,000 draws.

**`B_TRAIL5` on this response is exactly `prior5_minutes` — the decision stratum's own gate
variable.** A screen that had used it as its reference would have handed the tuning **7.6× the best
candidate's worth** and called it a feature.

Selected hyperparameters, chosen by SSE on **decision-stratum rows from strictly earlier seasons
only**, so no eval row informs them: **h = 3, k = 1** for eval 2023 (2,506 training rows) and for
eval 2024 (4,102). The same pair is selected on the share response, and on the share response it
reproduces `E1_I0046`'s published values **bit-exactly** (anchors A5T2023/A5T2024, |Δ| = 0).

---

## WHAT THE TUNING IS, IN ONE LINE

```
B_TUNED = (1 − w)·EWMA_h(player's own strictly earlier minutes) + w·(200 / n_hat)
w = k / (k + n_prior)                    n_hat = team's strictly prior mean roster size
```

Two hyperparameters. **200 is the rulebook, not the realised team total** — the shrink target reads
nothing from the game being forecast. `B_NAIVE` is the same object with `h` pinned to 5 and the
shrinkage switched off; `B_TRAIL5` replaces the EWMA with a flat 5-game mean.

**So the entire +0.016456 comes from two numbers: a halflife of 3 instead of 5, and a shrinkage
weight of 1 instead of 0.** That is the whole of what "tuning honestly" bought, and it is larger
than every candidate effect measured in this screen.

---

## THE SAME NUMBERS ON THE OTHER ARMS AND POPULATIONS, REPORTED SECOND

| response | arm | population | vs NAIVE | vs TRAIL5 |
|---|---|---|---:|---:|
| `R1_min` | RAW | **DECISION 2023–24 (headline)** | **+0.016456** (p 0.0010) | **+0.050624** (p 0.0005) |
| `R1_min` | PROJ | DECISION 2023–24 | +0.037051 (p 0.0005) | +0.071062 (p 0.0005) |
| `R1_min` | RAW | *all appeared rows* 2023–24, n = 9,056 | *+0.003743 (p 0.1089)* | *+0.010721 (p 0.0005)* |
| `R1_min` | RAW | **disclosed 2022**, n = 1,350 | **+0.009862 (p 0.4408)** | +0.041923 (p 0.0050) |
| `R2_smin` | PROJ | DECISION 2023–24 | +0.038378 (p 0.0005) | +0.073212 (p 0.0005) |

`E1_I0046` reported the minutes-share tuned-over-naive gap as **+0.0384**; this screen's independent
reimplementation returns **+0.038378** on the same rows. That is the cross-check.

---

## WHAT MOST WEAKENS THIS PAGE

**(a) The tuning clears its own 80 %-power floor against the nearer benchmark by only 1.20×.**
`+0.016456` against an analytic MDE80 of `0.013684`. It is established, and it is not comfortably
established. Against the *further* benchmark (`B_TRAIL5`) it clears by 2.00×.

**(b) The tuning's advantage over `B_NAIVE` does NOT replicate in the disclosed 2022 window** —
`+0.009862` at **p 0.4408**, with a different pair selected there (h = 2, k = 2). Only the gap over
`B_TRAIL5` survives 2022 (+0.041923, p 0.0050). **The honest reading is that the *shape* of the
estimator — an EWMA with shrinkage rather than a flat 5-game mean — is what is robust, and the
*particular* halflife is not.** The headline number above is the one that is least robust of the
two, and it is the one the brief asked for.

**(c) It does not survive the move off the decision stratum.** Pooled over all 9,056 appeared rows
in the clean window, tuned-over-naive is `+0.003743` at **p 0.1089**. The tuning's value is
concentrated in exactly the rows that are bet on, which is the right direction — but it means the
figure is a decision-stratum figure and cannot be quoted as a general property of the estimator.

**(d) Eval 2023 trains on 2021–2022, and 2021 is degenerate** (all forecasts at fallback level 4, a
constant with no usable residual). Half the clean window's hyperparameter selection is therefore one
step removed from a fold with no usable residual. Eval 2024 is not, and the per-season figures are
in `REFERENCE_TUNING.csv`: tuned +0.245087 / naive +0.231726 in 2023, tuned +0.210976 / naive
+0.191500 in 2024. **The gap is larger in the cleaner season**, which is the reassuring direction.

**(e) `B_UNIFORM` is a straw man and is reported only for scale.** An equal split scores R²
**−1.826** — worse than predicting the response mean. Nothing in this screen is measured against it,
and the `+2.054226` in the table above should never be quoted as anything but a sanity check.
