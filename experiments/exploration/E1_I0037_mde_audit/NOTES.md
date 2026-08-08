# NOTES — E1_I0037, audit of the analytic MDE80

Read `VERDICT.md` first. This is the working record: what I did, in what order, what I nearly got
wrong, and the numbers that did not fit.

---

## 1. What was actually claimed, and why it needed splitting

D113 recorded E1_I0035's D-3 as one claim. It is three, and they came apart under testing:

1. `null_sd` is computed from an effect-carrying vector. **True, and it is in the shared kit.**
2. That makes the analytic MDE80 anti-conservative. **False — it makes it conservative.**
3. On the player cell the error is 6.6×. **Not reproducible; a contrast mismatch.**

The tell was in E1_I0035's own files. `s05_power_and_exposure.py`'s module docstring says the
inflated null sd makes the floor **conservative**; `DEFECTS.md` D-3 says **anti-conservative**.
Both cannot hold, and the docstring is the one that follows from the algebra. My PREREG recorded
this contradiction as the thing to resolve first, before any simulation.

## 2. Order of work

| stage | what | log |
|---|---|---|
| PREREG | design + pre-committed predictions P1–P4, self-checks S1–S6, hashed | `PREREG.sha256` |
| s01 | reproduce D103's anchor; resolve the call graph by AST | `run_log_s01.txt` |
| s02 | the 1,304-condition simulation grid | `run_log_s02.txt` |
| s03 | separate H_A from H_B; recompute the 6.6× cell like-for-like | `run_log_s03.txt` |
| s04 | census + D103 exposure | `run_log_s04.txt` |
| s05 | verify the infinite-MDE result by simulation, not algebra | `run_log_s05.txt` |
| fix | `PROPOSED_FIX/` + 23 tests | `run_log_fixtest.txt` |

## 3. The anchor, reproduced first

`retrospective_power.csv` → group to unique cells → **1,349**, blind at 0.0023 family-wise →
**760**, share **0.5633802816901409**, identical to D103's published `FINDINGS.json` value to all
16 digits. Asserted, not eyeballed. Only then did I compute anything new.

Worth noting: the raw file has **1,975 rows**, and D103's own `run_s06.txt` prints "1975 cells
across 7 screens" while `POWER_VERDICT.md` says 1,349. Both are right — the dedup to unique cells
happens in `s08_named_list.py` — but a reader moving between the two documents will trip over it.

## 4. The algebra, and where my prediction was wrong

Pre-committed (PREREG §1): with `nb` blocks, `sd(e) = sqrt(e²/nb + SE²)`, so 80 % power needs

```
u²(1 − t_crit²/nb) − 2·z₈₀·u + (z₈₀² − t_crit²) ≥ 0,    u = effect/SE
```

Predicted vs measured `true_MDE / (2.802·SE)`:

| nb | 4 | 8 | 16 | 32 | 64 | 128 | 256 | 512 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **predicted** | ∞ (15.8) | 1.628 | 1.221 | 1.096 | 1.045 | 1.022 | 1.011 | 1.005 |
| **measured** | ∞ | 1.223 | 1.076 | 1.028 | 1.015 | 1.002 | 1.008 | 0.996 |

**My prediction over-shot at small block counts** — 1.63 predicted against 1.22 measured at
nb = 8. The normal approximation is the culprit: a sign-flip null over 8 blocks has 256 support
points and is **sub-Gaussian**, so its 97.5 % quantile sits below 1.96 sd and the real test is
more powerful than the Gaussian algebra says. Direction of the finding survives; magnitude at
small nb does not. This is why the shipped fix solves the power equation on the cell's actual
null geometry rather than through the closed form.

**A hypothesis I preregistered and had to abandon (P4a).** I expected the Kish effective block
count `(ΣB²)²/ΣB⁴` to govern the bias, since heavy-tailed block sums should behave like fewer
blocks. It does not. E1_I0035's team cells have 36 nominal blocks but Kish `neff` of 13.5–21.0,
and the measured `E_inj/A_ctr` (1.013–1.049) tracks the **nominal 36** (predicted 1.085), not the
`neff`. I have left `neff_blocks_kish` in the fix's output as a diagnostic and stopped claiming
it drives anything.

## 5. Where the 6.6× actually came from

`s05_power_and_exposure.py`:

```python
45   b0      = (np.clip(PF["w_X0"], 0, 1) - y_app) ** 2
46   bXb     = (np.clip(PF["w_Xb"], 0, 1) - y_app) ** 2      # Xb
50   noise_p = (bXb - b0)[mA]                                # injection noise: the Xb contrast
72   print("    analytic 2.802 x null_sd (Xa cell)  = 0.00038")   # analytic: the Xa contrast
```

The injection floor 0.0025 was measured on `bXb − b0`; the analytic floor 0.00038 came from the
`Xa − X0` null. Recomputed from that screen's own `_player_frame_repaired.parquet` (20,084 rows,
seasons 2022–2024, partition asserted):

| contrast | blocks | observed effect | analytic (obs) | analytic (centred) | injection | inj/ana_obs |
|---|---:|---:|---:|---:|---:|---:|
| **Xa** | 488 | +0.000148 | 0.000372 | 0.000371 | 0.000379 | **1.019** |
| **Xb** | 488 | +0.014239 | 0.003051 | 0.002309 | 0.002334 | **0.765** |

My recomputed analytic figures reproduce E1_I0035's published ones to 3 s.f. (0.000372 vs
0.000382; 0.003051 vs 0.003042 — Monte-Carlo, different seed on 2,000 draws), so I am recomputing
the same quantity they did.

Note the last column against the second-to-last: on **Xb**, injection 0.002334 against the
**centred** analytic 0.002309 is a ratio of **1.011**. The corrected construction is calibrated on
that cell. The 0.765 is H_A doing exactly what H_A does — inflating a floor when the effect is
large.

The team cell **was** like-for-like (Xb on both sides), and its "conservative 2.3×" is real:
contamination 2.435, quoted 4.595, correct 1.887.

## 6. Two things that matter more than the ratio

**Six blocks.** `p_min = 2^(1−nb)` for a two-sided sign-flip, so `p < 0.05` is unattainable below
6 blocks. Measured Type-I at R = 2,000: nb = 3/4/5 → 0.0000 exactly; nb = 6 → 0.0275; nb = 7 →
0.0470. This is a property of the design, visible before any data is loaded, and no screen in this
programme appears to check it.

**`t_crit ≥ √nb` ⟹ infinite MDE.** The threshold outruns the statistic. I did not trust the
algebra on something this consequential, so `s05` sweeps the effect from 0.5 SE to 10,000,000 SE
and reports max power attained: **0.0000** at nb = 48 / `t_crit` 6.974 — which is precisely how
D103 tests E1_I0023's cells. Controls in the same table: same cells at `t_crit` 1.645 reach 80 %
at 2.76 SE; nb = 60 at 6.974 reaches it at 20.3 SE. The boundary behaves as predicted from both
sides.

## 7. The census

2,368 figures. Effect-carrying analytic constructions: **232**, across four screens —
E1_I0023 (120, reaching the ledger through D103), E1_I0034 (71), E1_I0033 (24), E1_I0035 (17).
Classification is by the ratio `value / null_sd` **within the same JSON record**, matched against
three fingerprints (2.800000, 2.801585, 2.486622), not by key name. E1_I0036's `mde80` looked like
a match by name and is not — it interpolates a power curve, which is the correct construction.

## 8. What I would tell the coordinator to do next

1. **The `t_statistic` family, not this one.** 666 of 1,349 D103 cells, 518 of the 760 blind
   verdicts, on a scale conversion that never went through D103's own validation gate. That is a
   bigger unvalidated surface than the one I audited and I did not quantify it.
2. **Check E1_I0034's block counts against 16.1 / 8.1 / 4.9.** If the points cell really has
   fewer than six clusters, its sign-flip null cannot reject at all and the withdrawal of its
   points-negative verdicts was right for a reason it has not yet stated.
3. **Fix E1_I0033's `NOTES.md` §5 label** — "Power verified by injection" over a table of analytic
   2.800× values. That is a documentation defect with a live consequence: D111 quoted those
   numbers to the user as injection-verified.
4. **Do not adopt my fix below 32 blocks expecting an improvement.** It does not improve anything
   there. It stops the number being quoted as if it meant something, which is different.

## 9. Scope

Nothing written outside `experiments\exploration\E1_I0037_mde_audit\`. The shared kit is
unmodified. No `git` command of any kind was run. No process was killed — none was launched
beyond synchronous `python` invocations that returned on their own. Files read outside my scope
were read only; the two E1_I0035 parquet frames I loaded were partition-asserted on load and are
2022–2024.
