# E1_I0042 — defects, self-reported

Nine. Two changed a headline. Two were caught only because an anchor or a calibration check was
loud, and both of those would have moved this screen's verdict in the **permissive** direction.

---

## DEF-1 — MEDIUM — the preregistration's `REM_KEEP` allowlist omitted the points regressors

**What.** PREREG s2 declared `REM_KEEP` at 18 columns for E1_I0034's remaining-player frame. It did
not include `u_pts` or `uz_pts`, so preregistered anchor **A8** (the points channel on that frame)
could not be built at all — the load raised `KeyError: 'u_pts'`.

**Fix.** A separate declared allowlist `REM_PTS` (2 columns), length-asserted like every other,
added **after the hash** and labelled as such in `rr_frames.py`.

**Direction.** None. It adds no cell, changes no specification and moves no headline; it makes a
preregistered anchor runnable. A8 then reproduced at 7.6e-16.

---

## DEF-2 — MEDIUM — my first P03 arm was the wrong construction, and anchor A9 caught it

**What.** I built E1_I0034's P03 trailing-5 arm as an **offset** arm (`offset = base5`,
`min_train = 2022`). E1_I0034 s06 builds it as a **regression** — `M0 = [1, base5, z]`,
`M1 = M0 + [u, u·z]` — with `min_train_season = 2021`, because no champion forecast enters it and
the degenerate 2021 fold therefore cannot poison it. A9 missed by **2.03e-2**.

**Fix.** Replaced with E1_I0034's own construction. A9 then reproduced at 5.6e-16.

**Direction.** My wrong arm understated the published effect (0.0092 vs 0.0295), i.e. it would have
made D116 look **weaker**. Fixing it made the prior screen look **stronger**.

---

## DEF-3 — MEDIUM — I re-gated the threshold stratum instead of stratifying it, and A16 caught it

**What.** E1_I0039's `freed_ge_30` cell is a **stratification of the same gated-at-25 arm**, not a
re-gated arm — its VERDICT.md §3 says so explicitly. I built a new arm gated at 30. A16 missed by
**1.28e-3**.

**Fix.** A16 now evaluates the gate-25 arm on the `freed ≥ 30` rows and reproduces at
|Δ| = 0.000e+00. The re-gated arm survives as a **labelled diagnostic** in the D101-clean gate
sweep, where the difference between the two is the actual question.

**Direction.** My wrong arm gave 0.1430 against the published 0.1443 — a 0.9% understatement.
Immaterial to any conclusion, but it is exactly the kind of silent near-miss that a tolerance of
1e-2 would have swallowed.

---

## DEF-4 — **HIGH — my injection planted the effect on top of the real response, and would have licensed the opposite verdict**

**What.** The first component-wise injection computed `y' = y + κ·u` on the **real** response. κ = 0
is then not a null — it is the observed effect carried through a block bootstrap. The instrument
duly reported **power 0.700 at κ = 0** and **0.900 at κ = 0.05**, from which the empirical power at
the observed effect size interpolates to about **0.79**. The whole curve measures power to detect
*(real + κ)*, not κ, so every quantity derived from it is meaningless.

**Fix.** Replaced with a **true null response**: the champion residual `y − champion` permuted
across team-games over the **whole** frame, `y_null = champion + permuted residual`; the planted
effect then enters as `y_null + κ·u`. κ = 0 becomes the type-I instrument.

**Direction, and this is the one that matters.** The broken instrument put the observed effect at
roughly **0.79 power**, a whisker under the 0.80 convention. **The corrected one reports 0.482.**
The broken version would have let VERDICT §1 read "essentially adequately powered"; the corrected
one says the cell cannot reliably see its own effect. **The correction runs against this screen's
own headline, and it is the single largest change any defect here made.**

---

## DEF-5 — **HIGH — my first type-I generator was broken and read 1.0000**

**What.** The first type-I instrument synthesised a response only on the **scored** seasons
(`y_syn = base + permuted residual` where the base is `nan` outside 2023–2024) and left the
**training** seasons at their real values. The walk-forward therefore learned a **real** slope and
applied it to a synthetic response, so the two arms genuinely differed and the two-sided rejection
rate was **1.0000** — not a type-I failure of the null but a broken generator.

**Fix.** The corrected generator (DEF-4) synthesises across all four seasons. Type-I is now
**0.0575** over 400 datasets against a target of 0.05.

**Direction.** None on the headline directly — but **DEF-4 was found only because DEF-5 was loud.**
A rejection rate of 1.0000 is impossible to ignore; power 0.700 at κ = 0 is not. Had the second
defect been quieter, the first would have passed and this screen would have reported DECIDED.

---

## DEF-6 — MEDIUM — the frozen arm's no-intercept slope fit can absorb a level shift through `u`

**What.** `wf_frozen` fits the candidate's slopes with **no intercept** on the residual about the
frozen base. Because `u` has a non-zero mean on the training pool, the slope can absorb some level
shift *through* `u`. That is not the shared-intercept channel — the movement is strictly
proportional to `u` and therefore strictly confined to treated rows, which G2 and G4 verify at
exactly 0.000e+00 — but it is **not literally zero recalibration**; it is recalibration that can
only reach rows the treatment touches.

**Consequence, disclosed rather than fixed.** This is why the frozen effect can exceed the shared
one (+0.0796 vs +0.0760) rather than being bounded by it. A stricter variant would centre `u` on
the training pool before fitting, which changes the functional form and would no longer be D116's
candidate. **Not fixed; declared.**

---

## DEF-7 — LOW — the preregistered "not localised" rule is the wrong instrument for the result it met

**What.** PREREG s6 said: if the threshold's bootstrap interval spans more than 20 minutes, report
it as not localised. The measured interval is **[0.0, 0.0]**, width zero, which the rule
mechanically calls **LOCALISED** — the opposite of the truth. The interval is degenerate because
the crossing estimator returned 0.0 in **every replicate that crossed at all**, and 23.6% of
replicates found no crossing anywhere.

**Fix.** The rule's output is reported verbatim *and* immediately contradicted in the same block,
with the two diagnostics that actually settle it (distinct bootstrap values; no-crossing fraction).
**A preregistered rule that gives the wrong answer is reported, not quietly replaced.**

---

## DEF-8 — LOW — the specification spread verdict turns on two thousandths of a minute

**What.** PREREG s8 declares a headline specification-dependent if the lattice spread exceeds it.
Spread = 0.07738, headline = 0.07960. The rule returns "not specification-dependent" by **0.00222**
— 2.8% of the headline. This is a threshold effect on a preregistered binary and it should not be
read as a substantive finding in either direction. The honest statement is in VERDICT §8: the
lattice spans 97% of the headline and only the sign is robust.

---

## DEF-9 — OPERATIONAL — non-zero exit codes when stdout is piped through `Tee-Object`

**What.** `s06` and `s07` returned exit 255 when their output was piped through PowerShell's
`Tee-Object`, after all files had been written. Run without the pipe, `s07` returns **exit 0**. No
traceback is produced and every output artefact is present and correct on disk (verified by
timestamp and by re-reading `_s06.json`, `POWER_FLOORS.csv` and `POWER_ARITHMETIC.csv`).

**Assessment.** A shutdown-time stdout flush artefact of the harness, not of the analysis.
Recorded so that a later reader does not mistake it for a failed run — but **it is a real reason to
distrust "the script exited cleanly" as evidence**, and every artefact here was checked
individually rather than inferred from an exit code.

---

## Not defects, but declared limitations

* **Every cell is an ORACLE-ON-ABSENCE CEILING.** The absence indicator is realised, not forecast.
  Both pre-game injury sources return `manifest_present: false`; UNVERIFIABLE is not a pass.
* **The bootstrap in `THRESHOLD.csv` does not refit the walk-forward.** It resamples team-games from
  the already-fitted per-row losses, so it estimates the sampling variability of the **evaluation**,
  holding the fit. That is the right object for an interval on a threshold *location*; it is
  labelled in the CSV and in the script header.
* **The per-fold injection floors in `HEADLINE_WITH_FLOORS.csv` are a CARRIED RESCALE**, not a
  per-fold measurement: this screen's own measured ratio (1.876×) applied to each fold's analytic
  floor. Labelled wherever it appears.
* **`ADMISSIBLE_SCORED` is a constant in `rr_base.py`.** It is not trusted: `s01` derives the
  scorable seasons from the champion receipts and **raises** if the derivation disagrees with the
  constant, so the constant cannot silently drift from the evidence.
