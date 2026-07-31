# Session journal — 2026-07-30 evening through 2026-07-31

*A narrative record of what was done, what was found, what was retracted, and why.
For the current state and next actions see `HANDOFF_2026-07-31.md`. For the rules that
bind future work see `../ROADMAP.md`, `HANDOFF.md` §3, `PROGRAM_FIREWALL.md`, and the
amendment chain in `../experiments/registry.jsonl`.*

**Scale:** 80 commits, 37 registered experiments (25 registered in this session), 22
recorded evaluations. Every number was independently recomputed by the orchestrator from
row-level artifacts before being recorded.

---

## 1. What went live

**The prospective clock started.** John approved the v0 freeze; `freeze-v0` is tagged, and
records 1–3 landed on `forecasts/forecast_log.jsonl` at 2026-07-31T14:28:20Z — the full
slate at T−8h with margins, totals, Gaussian cover probabilities and market lines at
cutoff. Two scheduled tasks (10:20 and 18:45 ET) keep it running. **This is now the
project's only holdout capable of supporting a promotion decision.**

**Player props capture, live and backfilled.** All four prop markets are quoted for the
WNBA by five books; four daily snapshots now run. A historical backfill bought 784 games /
36,946 lines / 160 players across 2024–2026. Cost ~8.2K of the paid month's credits.
Props do not fit the free tier — an input to the ~Aug 30 tier decision.

**Operations.** `daily_refresh.py` (collect → masters → channel base → certify) runs at
08:30. Certification grew from 7 checks to 9. A full-history play-by-play reconciliation
recomputed every final score from raw events: **1,489/1,489 exact**.

---

## 2. What we learned about the model

Roughly a dozen registered experiments, nearly all negative, and the negatives were the
valuable part.

**Families closed:** shot-location overlays multiplied onto the channel chains *degrade*
them (constitution rule 6 — composites replace ingredients, never stack); referee crew
free-throw priors collapse to ~1.0 under honest shrinkage; a dedicated totals head loses to
the existing per-side calibrations; rear-view online bias correction provably cannot catch
a level shift (its correction is bounded below the required size at *any* damping).

**The structural finding — the common shock.** 66.7% of side-error variance is a per-game
shock (realized pace and shooting), cross-sectionally unpredictable, which cancels out of
margins and doubles into totals. This single fact explains why totals trail margins, why
the bottom-up rebuild produced better sides but worse margins, and why 2026 totals run hot.
It also proves margins are affine in channel *differentials*, so only differential
information can move them.

**The player layer.** The two-stage availability model won clearly on P(plays) but the
minutes model beat the EWMA floor by only 0.037. Bottom-up 3pt construction tied per
channel and failed the margin gate through the cancellation mechanism above. Player 3P%
skill turned out essentially unestimable at WNBA sample sizes.

---

## 3. What we learned about the market

- **No cover edge at near-tip.** Model cover Brier 0.2602 versus a coin's 0.2500 and the
  market's 0.2498. When we disagree with the line, games cover ~50/50.
- **The market's morning line is as accurate as its close** (10.471 vs 10.465). Line
  movement is repricing, not accuracy gain.
- **The day-before "advantage" is not real** — tested on 246 games scored at both cutoffs:
  gap +0.468 at T−24h vs +0.438 at T−8h. It was sample composition.
- **Props: we lose by 0.31 points in every slice** — all nine books, every tercile, both
  roles, both venues, all three seasons. But the projection beats a *shuffled* version of
  itself, so it carries real information worth less than the vig.
- **Current standing:** behind the books everywhere. Best case is 2026 margins at ~0.12
  behind with an interval spanning zero — parity, not edge.

**The one live lead:** our edge over the market rises monotonically with absence load
(−0.73 / −0.40 / +0.09 across terciles). Post-hoc, observational, development data — which
is why the count that motivated it is *banned* as a feature in the experiment it spawned.

---

## 4. Three failures of rigour, all caught, all recorded

This is the part worth reading twice.

**Leakage in a fitted table.** The player-value ratings are fit on 2021–2024 and were used
to score 2024 as a test season. Caught by an agent running an audit its registration did
not require. The first blast-radius pass found it reached further than recorded: the
*training* seasons were also inside the fit window, so coefficients and calibration were
themselves contaminated — meaning the "clean-season" fallback both the experiment and I
had retreated to was also void. A second contaminated artifact surfaced too: full-sample
zone-map shrinkage constants passed into a run scoring later seasons.

**A screen that could not certify anything.** With 200 permutations the smallest attainable
p is 0.00498; under BH at q=0.10 across 1,368 tests, a floor-valued test needs 69 ties to
pass and only 20 existed. No result could have been certified regardless of truth. The
rule derived from it — permutation count must scale with battery size — was then itself
corrected: it guarantees only a *singleton* rank-one discovery, and my characterisation of
run 1's rejections as "tie-count luck" was withdrawn as unfair to the BH procedure.

**A placebo that could not fail.** One experiment's permutation probe recalibrated on true
targets, handing the null a fitted degree of freedom. Worse, the guarding tolerance was
*looser than the defect it existed to catch* — a human caught it, not the gate. The audit
also found the defect was isolated as a construction but systemic as an absence: seven
experiments ran no placebo at all, later classified individually rather than uniformly.

**And my own overstatements**, each corrected on the record: describing the contamination
correction as "in our favour" when two of three variants got worse (I had cited the
omniscient oracle the roadmap forbids citing); writing "several effects exceed their
detection limits" beneath a table showing only one did; treating exceeding a detection
limit as evidence an effect is real; calling an integrity audit proof of "statistical
power"; and labelling slices "validation" and "holdout" that the firewall had already
reclassified as development.

---

## 5. The rules those failures produced

Every one is registered and binding on future work:

1. **No null without its detection limit.** Underpowered nulls are absence of evidence and
   must be labelled distinctly from genuine nulls.
2. **Exceeding a detection limit is never evidence.** Significance requires a calibrated
   permutation p-value or an interval.
3. **Permutation count scales with battery size** (singleton-resolution guarantee), with a
   fixed B_final for every test and early stopping only under an impossibility bound.
4. **Rare conditions are excluded before testing**, by a power criterion, not an arbitrary
   frequency.
5. **Correlated specifications collapse for reading only** — never to shrink the
   multiplicity denominator after results are known.
6. **No practical-significance threshold until one can be derived** from propagated points
   error or the betting transfer curve. The 0.20% floor was withdrawn as post-hoc.
7. **Any experiment consuming a fitted table must assert its fit window excludes every
   scored season**, and artifacts must carry as-of manifests.
8. **Screen outputs are "rejections produced by the BH procedure"**, not "valid
   FDR-controlled discoveries", where the null's validity is unresolved.
9. **Retrospective seasons develop; the prospective log confirms.** Where they disagree,
   the log wins.

---

## 6. What the day cost and what it bought

It cost most of the day's apparent wins. The +6.4% betting cell failed a broader battery.
Eleven "confirmed" features became three once the cross-season anchor became the baseline —
they had been proxying for long-term player identity. The 18% lineup ceiling was
contaminated, then its correction was contaminated too.

It bought a lab that catches these things. The three failures above were found by the
system's own audits and by a reviewer reading carefully — not by luck, and not after money
was at risk. The engine is not yet better than the market; the *process* now is.
