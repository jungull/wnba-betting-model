# DEFECTS — E1_I0058_market_benchmark

Every defect found in this screen, including the ones that do not change the answer. Recorded
because this program's standing finding is that unrecorded construction choices are its top
source of wrong answers.

**None of the five defects below changes the headline.** They are recorded anyway, and D1 and D2
change how the headline may be *worded*.

---

## D1 — the frozen PREREG contradicts itself on what P2 requires (MATERIAL TO WORDING)

**Severity: B. Found by: Coordinator #07 during interpretation. Not repaired — the PREREG is
hash-frozen and was not edited.**

§5 defines the test:

> "Distinguishable from zero" requires BOTH: (i) the 95% cluster-bootstrap percentile interval
> excludes 0, and (ii) the two-sided permutation p-value < 0.05.

§7 states P2's threshold as:

> P2 | In (A), bF is NOT distinguishable from 0 | **both criteria in §5 fail for bF**

These are not the same rule. "NOT distinguishable" under §5 means *at least one* criterion fails.
§7's threshold demands that *both* fail.

**What actually happened.** For `bF` in `ENC_M2_F1`:

* criterion (i): headline 95% CI `[-0.3012, -0.0248]` — **excludes zero.** Criterion (i) HOLDS.
* criterion (ii): permutation p = `0.7111` — **not < 0.05.** Criterion (ii) FAILS.

So exactly one criterion failed:

| reading | verdict |
|---|---|
| §5's definition (governing) — bF is not distinguishable because it fails (ii) | **P2 PASSES** |
| §7's literal threshold — "both criteria fail" — only one did | **P2 fails its threshold** |

**Ruling taken, and why.** §5 governs: §7's own text is a *reference to* §5's definition
("distinguishable from 0"), and §5 states that definition explicitly and unambiguously. §7's
threshold column is a loose restatement of it. `FINDINGS.json` records **both** readings verbatim
so no reader has to take this ruling on trust.

**This is not a licence to pick the convenient reading.** The two readings agree on the substance
— the model has no material edge — and disagree only on the bookkeeping. The convenient reading
would have been to call the negative CI a *finding*; it is not, see D2 and the materiality
arithmetic in `NOTES.md`.

**Lesson for future preregs:** state each prediction's threshold by *reference* to the definition
("`bF` is not distinguishable per §5"), never by restating the logic in different words. A
restatement is a second, unsynchronised copy of the rule.

---

## D2 — the cyclic permutation null for `bF` is not centred at zero, so its p-value does not test what §5 says it tests (MATERIAL TO INTERPRETATION)

**Severity: A for method, none for conclusion. Found by: Coordinator #07 reading the null
distribution rather than only its p-value.**

§6.2 preregisters `SCHEME_WITHIN_CYCLIC` and is right to: F1 is a `shift(1).expanding()`-shaped
walk-forward EWMA with mean within-player lag-1 autocorrelation **0.6365**, well above the 0.15
materiality floor, so a plain shuffle would be anticonservative (D093). The scheme choice is
correct.

**But the resulting null is not centred at zero:**

```
bF null under cyclic within-player shift:  mean +0.1882,  sd 0.0497,  95% [+0.0926, +0.2885]
observed bF:                               -0.1604
```

The cyclic shift preserves each player's *marginal distribution* — including that player's mean
level — and player mean level is genuinely predictive of `pts` beyond the market. So a randomly
re-aligned F1 still earns a coefficient of about **+0.19**. The null therefore tests

> "F1 carries no alignment to the response *beyond the player-level marginal information that
> survives a cyclic shift*"

and **not** the hypothesis §5 attaches to it, "bF = 0".

**Consequence for the reported p-value.** The preregistered statistic is
`p = share of |null| >= |observed|`. With `|observed| = 0.1604` and the null mass sitting near
`+0.19`, most null draws exceed it in absolute value and `p = 0.7111`. **That large p-value is not
evidence that `bF` is near zero.** The observed `bF` in fact lies *entirely below* the null's 95%
interval — a signed comparison would say the model's actual alignment is *worse* than a randomly
shifted copy of itself.

**What is reported.** The preregistered `p = 0.7111` is the headline, exactly as frozen. This
paragraph is attached to it everywhere it appears. The signed observation is labelled **POST-HOC**
and is not used to claim anything.

**Why the conclusion is unaffected.** The conclusion does not rest on the p-value. It rests on
magnitudes that need no null at all: F1 is **0.4189 MAE points worse** than M2 standalone, and the
fitted blend buys **0.0079** (in-sample) / **0.0051** (leave-one-game-out) MAE points against a
preregistered materiality floor of **0.10**. The model adds nothing material whichever way the
inference is read. Had the magnitudes been material, this defect would have blocked the finding.

**Lesson:** a permutation scheme chosen to preserve a nuisance structure may also preserve
*signal*, which moves the null away from the parameter value being tested. Always report the null's
mean and interval beside the p-value; a p-value alone hides this completely.

---

## D3 — an un-preregistered 0.25 threshold in the power flag

**Severity: C. Found by: Coordinator #07 reading `s02_score.py` before executing it.**

`s02_score.py:279` computes `UNDERPOWERED = bool(MDE_bF > 0.25)`. The frozen PREREG §6.3 says only:

> if `MDE(bF)` is large relative to 1.0, the null is reported as UNINFORMATIVE

**0.25 appears nowhere in the PREREG.** It was introduced in the script, written 2026-08-17 17:11
local, three minutes *after* the PREREG froze at 17:08.

**Mitigating, and verifiable:** the script's mtime precedes the frame's completion of any outcome
statistic, and no outcome statistic had been computed when it was written, so the threshold is not
outcome-tuned. It is nevertheless a threshold introduced after the freeze and is labelled
**POST-HOC**.

**Not repaired, and not relied on.** The script was executed as frozen. `FINDINGS.json` argues the
power conclusion from the PREREG's *own* materiality floor instead:

```
MDE(bF) = 0.1987 in coefficient units
        = 0.0351 MAE points
materiality floor (PREREG §4) = 0.10 MAE points
```

The smallest effect this screen could detect is finer than the smallest effect that would matter.
The null is therefore **informative** — which satisfies D136 without appealing to the 0.25 cutoff
at all. The flag's value (`False`) happens to agree; that agreement is a coincidence, not the
argument.

---

## D4 — the frozen PREREG carries a decision id that was already taken

**Severity: C, bookkeeping. Found by: Coordinator #07 diffing the briefing against the ledger.**

`PREREG.md` line 3 reads `**Decision:** D138.`

`DECISION_LEDGER.jsonl` had already assigned **D138** to `E1_I0057_information_gap` at
**2026-08-17T20:15:00Z** — roughly 53 minutes *before* this PREREG was frozen at
**2026-08-17T21:08:30Z**. The agent that wrote the PREREG took the next number it had seen rather
than re-reading the ledger.

**Not repaired.** Editing `PREREG.md` would break its sha256 and destroy the freeze, which is a
far worse defect than a wrong label. The file stands as frozen.

**Correct id: `D141`.** Recorded in `FINDINGS.json` (`decision_id`, with
`decision_id_printed_inside_frozen_PREREG` beside it) and in the ledger event for this screen.
Anyone reading the PREREG in isolation will see D138 and must be told this; that is what this entry
is for.

---

## D5 — the screen was executed 19 hours after its frame was built, by a different coordinator

**Severity: C, provenance. Recorded for completeness.**

`s00`, `s01` and the PREREG freeze were completed 2026-08-17 (17:06–17:11 local) by an agent
dispatched under Coordinator #06. That agent died on an API error before executing `s02`, leaving a
0-byte output file that made the work look lost. It was not lost. Coordinator #07 executed `s02` on
2026-08-18 at 15:50 local under the *existing* frozen hash.

**Nothing was re-run, re-derived or rewritten upstream.** The evidence that nothing moved in the
interval is not an assertion but a hash:

```
PREREG.md        sha256 6ea05be00509ab80d8fa7220bc24b07ad87c8159b52c05962f8838b13596ca9b
                 re-derived on disk 2026-08-18, matches PREREG.sha256 exactly
analysis_frame   sha256 8605a559fc66076990055a35c3b932c9f242d665656d795e018ce2b9a547b7c8
                 re-derived on disk 2026-08-18, matches the value s01 recorded in leak_proof.json
```

The one thing that *would* have been a serious defect — rewriting the PREREG, or re-deriving
thresholds, seeds or draw counts now that the frame exists and its shape is known — did not happen
and cannot have happened without breaking the first hash.
