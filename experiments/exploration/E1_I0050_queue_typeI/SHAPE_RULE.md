# SHAPE_RULE — is Type-I inflation predictable from the candidate's distributional shape?

**Short answer: no, and the reason is that there is almost no Type-I inflation to predict.**
Across 104 estimable (cell, arm) pairs, the composed-2 null exceeds the preregistered 0.075
tolerance on **0** under the EXCH generator and on **3** under CIRCSHIFT. `E1_I0044`'s brief
named two "known-bad candidate types" — a heavy-tailed ratio (`pts__pred_cv`) and a pure counter
(`pl_games_prior`). **Measured against a generator under which H0 actually holds, neither is
bad.** Both are *conservative*.

PREREG **P4 FAILED**, and not marginally: it predicted Spearman(within-block excess kurtosis,
Type-I) > +0.5. Measured **+0.205 on A4 and −0.283 on A1** — below the threshold and
**sign-unstable across the two arms**.

But a general rule did come out of this, and it is about the Type-I study rather than the
candidate. It is in §3 and it is worth more than the queue.

---

## D101 statement

Every shape feature is a description of **one column** on **one arm's rows** after **that arm's
own base** (season fixed effects), computed on the arm-local season-z-scored, season-demeaned
candidate — the exact column the null permutes. Type-I rates are on that same arm, same rows,
same base, same SST. The two arms are reported side by side as two separate measurements and are
never differenced. Files: `_SHAPE_CAND_*.csv`, `_SHAPE_RESP_*.csv`, `_SHAPE_TABLE.csv`,
`_SHAPE_SPEARMAN.csv`.

---

## 1. The two "known-bad" types, measured

| candidate | arm | within-block excess kurtosis | max \|z\| | \|pos corr\| | **Type-I EXCH** | **CIRCSHIFT** | BLOCKBOOT |
|---|---|---:|---:|---:|---:|---:|---:|
| `pts__pred_cv` (heavy-tailed ratio) | A1 | **297.4** | **36.7** | 0.07 | 0.0090–0.0470 | 0.0290–0.0470 | 0.0360–0.0650 |
| `pts__pred_cv` | A4 | 11.3 | 11.4 | 0.00 | 0.0180–0.0350 | 0.0210–0.0300 | 0.0170–0.0370 |
| `pl_games_prior` (pure counter) | A1 | −0.86 | 2.33 | **1.000** | 0.0010–0.0040 | 0.0040 | 0.0040–0.0060 |
| `pl_games_prior` | A4 | −0.81 | 2.45 | **0.990** | 0.0010–0.0020 | 0.0030 | 0.0070–0.0080 |
| `pts__n_prior_games` (counter) | A1 | −0.85 | 2.33 | **1.000** | 0.0010–0.0060 | 0.0040 | 0.0050 |
| `pl_minutes_prior` (counter) | A1 | 0.13 | 3.15 | **0.991** | 0.0210–0.0380 | 0.0240–0.0450 | **0.0210–0.9860** |

A candidate with an excess kurtosis of **297** and a within-block spread of 36 standard
deviations produces a Type-I of **0.009–0.047**. The heavy tail does not break the null; it makes
it more conservative. The counters are the most conservative cells in the whole queue
(0.001–0.006).

**`E1_I0044`'s 0.5950 for `pl_games_prior|pts_absres` reproduces** — I get 0.5810 under its
generator, within the pre-stated band, with the ordering of all five of its cells preserved
(`_SELFTESTS.csv` T1). It is a real number. It is a number about the *generator*.

Two further facts about that cell, both worth recording: **`pl_games_prior|pts_absres` is not one
of the 54.** `E1_I0044` measured its most alarming Type-I on a cell outside its own queue. And on
the two `pl_games_prior` cells that *are* in the queue, the same generator gives 0.004–0.008.

---

## 2. What shape does predict: conservativeness, moderately

Spearman over estimable cells, `_SHAPE_SPEARMAN.csv`. Only features whose sign is stable across
both arms are shown; the full table is in the file.

| feature | ρ with composed-2 Type-I (EXCH), A4 | A1 | reading |
|---|---:|---:|---|
| `pos_corr_mean_abs` (candidate is a function of within-block position) | −0.335 | **−0.639** | more positional → more conservative |
| `shared_position_profile_sd` | **−0.605** | −0.426 | same |
| `pos_monotone_share` | −0.224 | −0.403 | same |
| `dev_lag1_autocorr` | −0.160 | **−0.660** | more serially correlated → more conservative |
| `var_share_between_block` | **+0.400** | +0.235 | more genuinely between-block → closer to nominal |
| `n_distinct_over_n` | +0.212 | +0.410 | more continuous → closer to nominal |
| `dev_excess_kurtosis` | +0.205 | **−0.283** | **sign flips — no rule** |

The strongest and most stable signal is that **serial and positional structure in the candidate
makes the composed-2 null conservative** (|ρ| up to 0.66), and `var_share_between_block` moves it
back toward nominal. That is exactly what §3 of `WHY_1.000.md` predicts from the mechanism:
composed-2 fills a block from one donor, manufacturing a between-block share of 0.114 where an
iid carrier has 0.034. A candidate that already *has* a large between-block share is least
distorted by that; a candidate whose variation is within-block and ordered is most distorted.

**But these are moderate correlations, not a rule.** Both two-feature rules I tried misclassify
heavily:

| rule | A4 misclassified | A1 misclassified |
|---|---:|---:|
| "position-monotone OR between-block share < 0.30" → conservative null | 22 of 50 | 23 of 54 |
| "position-monotone" → a position-preserving Type-I generator will condemn the null | 9 of 50 | 24 of 54 |

**I am not proposing either as a screening rule.** A rule that misclassifies 40–45% of cells
would not let a future screen reject a scheme before spending on it, which is the thing the brief
asked for, and saying so is the honest result.

---

## 3. The rule that *is* general, and it is about the Type-I study

This is the transferable finding and it was reached by measurement, not by argument.

> **A Type-I study whose synthetic-data generator preserves absolute within-block position will
> falsely condemn any null tested against a candidate that is a function of within-block
> position — because the generator has not removed the effect, it has re-planted it.**

Direct measurement, `_SHAPE_TABLE.csv`. For each cell I recorded the mean **signed** observed `t`
over the 1,000 "effect-free" synthetic datasets. Under a generator for which H0 truly holds this
must be ≈ 0.

| generator | A4: median \|mean signed t\| / max / cells with \|mean t\| > 0.5 | A1 |
|---|---|---|
| **EXCH** (means reassigned, deviations permuted) | 0.034 / 0.166 / **0 of 50** | 0.020 / 0.069 / **0 of 54** |
| **CIRCSHIFT** (means reassigned, deviations rolled — keeps serial correlation) | 0.025 / 0.105 / **0 of 50** | 0.055 / 0.161 / **0 of 54** |
| **BLOCKBOOT** (`E1_I0044`'s: whole donor blocks, position preserved) | 0.144 / **2.329** / **9 of 50** | **0.881 / 7.312 / 41 of 54** |

**On A1, 41 of the 54 "effect-free" datasets carry a mean signed `t` above 0.5, and one carries
7.31.** The generator did not produce a null. It produced data with a real association, because
these responses have a within-block positional profile shared across blocks
(`resp_shared_position_profile_sd` 0.167–0.264 on A1, against 0.064–0.118 on A4) and whole-block
donor copying transplants that profile intact into every synthetic dataset.

That is why the effect is far worse on A1 than on A4: the decision stratum (≥8 prior appearances,
≥24 trailing-5 minutes) removes precisely the early-season, low-experience rows where the
positional profile lives.

**Consequence for the programme:** `E1_I0044` did the right thing by refusing to claim its result
on five Type-I measurements. But the five it had were measured against a generator that was not
null, and they condemned its own instrument for a defect the instrument does not have.

---

## 4. Does the confound exist in the real data? — the test that could have retracted everything

If the response has a shared positional profile, the *real-data* association might also be a
time-in-season effect wearing a candidate's name. That would not be a Type-I failure; it would be
a confound, and it would matter more.

`_POSITION_ADJUSTED.csv`, `run_log_s06.txt`. **A separate arm with its own denominator:** same
rows, but base = season fixed effects **plus** relative within-player-season position **and its
square** (4 columns on A4, 5 on A1), SST = the response residualised on *that* base. ΔR² here is
**not** comparable to the main arm's and is never differenced against it. Composed-2 null, 2,000
draws, same 348-cell max-`|t|` bar rebuilt under the new base.

| | A4_CLEAN_DEC | A1_FULL |
|---|---:|---:|
| clean family-wise survivors tested | 16 | 24 |
| annihilated by the position-adjusted base | **0** | **0** |
| still family-wise significant | **16 of 16** | **24 of 24** |
| still per-cell significant | 16 of 16 | 24 of 24 |
| family-wise bar under the position-adjusted base | 4.937 | — |

**The robustness arm retracts nothing.** Even `pl_games_prior|minutes_absres` and
`pts__n_prior_games|minutes_*` — candidates that are *literally* the within-block position —
survive a base containing position and position², at `p_familywise` 0.0005–0.0010. The
association is not the linear-plus-quadratic season trend.

I record this as the result that most weakens my own scepticism, because it is: I built this arm
expecting it to kill the counters and it did not.

---

## 5. What most weakens this document

1. **P4 failed and P3 failed as stated.** P3 predicted BLOCKBOOT would condemn all three
   position-monotone counters. It condemns **one** (`pl_minutes_prior`, up to 0.986);
   `pl_games_prior` and `pts__n_prior_games` sit at 0.004–0.006 under the same generator, because
   for a candidate that *is* the position index, whole-block donor copying reproduces the column
   almost exactly and the permuted `t` equals the observed `t`. The mechanism is real but it is
   not monotone in "how positional the candidate is", and my prediction assumed it was.
2. **Fifteen candidates, not fifty-four.** The 54 cells rest on 15 distinct candidate columns, so
   the shape correlations have 15 effective points and dependent cells inflate their apparent
   precision. No shape correlation here should be read as better than suggestive.
3. **The position-adjusted base is linear and quadratic in relative position.** A profile with a
   different shape — a mid-season dip, a fatigue elbow — would not be removed by it. The arm is a
   check, not a proof of no confounding.
4. **CIRCSHIFT is not a perfect H0 generator either.** Circularly rolling a within-block sequence
   that has a monotone trend produces a sawtooth, which is not a draw from the response's real
   process. It is H0-true for the association being tested — the roll offset is independent of
   the candidate — but it is not a faithful simulation of the data.
5. **The one general rule I am offering is a negative one.** It tells a future screen how *not*
   to build a Type-I study. It does not let anyone reject a null scheme cheaply from the
   candidate's marginal distribution, which is what the brief hoped for, and the two rules I
   tested for that purpose both failed.
