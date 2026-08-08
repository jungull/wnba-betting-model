# DEFECTS — defects in E1_I0035's own work

Self-reported. Six found, three of them by me during the run and corrected, three standing as
limitations. Listed worst-first.

---

## D-1 — MY FIRST POWER-VERIFICATION-BY-INJECTION MEASURED NOTHING. Corrected.

**Severity: would have been serious.** The first version of `av_base.injection_power` planted a
**constant** onto a loss vector:

```python
lb = la + effect + rng.normal(0.0, 1e-9, size=len(la))
r  = paired_signflip_block(la, lb, block_codes, n_draws, ...)
```

The resulting per-row difference is exactly `effect` at every row. Block sums are then
`effect × n_j`, so under sign-flipping the **null sd scales linearly with the planted effect** and
the ratio `real / null_sd` is *identical at every effect size*. It reported a detection rate of
**1.000 at every planted value tested (0.5, 1.0, 2.0, 5.0 MAE)** and I nearly published that as
"power verified".

This is exactly the failure D108 exists to catch — a null (or here, a power check) that appears to
work and is structurally incapable of discriminating. It is embarrassing that it appeared in the
verification step itself.

**Fixed** by planting onto a **real, centred paired-difference vector**, resampled by block
sign-flip so each replicate is a genuine no-effect world with this data's dispersion and block
structure. The corrected curves are non-degenerate (team: 0.077 → 0.290 → 0.597 → 0.827 → 0.963;
tier-A player Brier: 0.087 → 0.243 → 0.467 → 0.663 → 0.847 → 0.967) and are in
`injection_power_curves.csv`.

**Consequence for the results: none.** The corrected floors (2.00 team MAE, 0.0025 tier-A Brier)
leave every verdict unchanged. But the defective run's numbers were written to `run_log_s04.txt`
and then **overwritten by the corrected rerun**, so the defective output is not preserved on disk.
It should have been kept under a `_DEFECTIVE` suffix, as this programme does elsewhere. That is a
second, smaller failure and it is recorded here because the log no longer shows it.

---

## D-2 — MY FIRST TYPE-I CHECK WAS DEGENERATE. Corrected.

The first construction was `paired_signflip_block(la0, la0 + d - d.mean(), ...)`. Subtracting the
mean makes the observed statistic **exactly 0.0**, so `|draws| ≥ 0` holds for every draw and
`p = 1.0000` always. It reported a rejection rate of **0.0000** with p quartiles 1.000 / 1.000 /
1.000, which reads like a beautifully conservative null and is in fact a broken one.

**Fixed** with `av_base.type_I_rate`, which flips whole blocks of a real centred difference vector
and plants an effect of exactly zero. Corrected result: rejection rate **0.0650**, p quartiles
0.236 / 0.482 / 0.750. That is mildly liberal — 1.4 SE above nominal at n = 400 — and I have not
tuned it away. It does not bind: no verdict in this screen rests on a p between 0.01 and 0.05.

---

## D-3 — THE PROGRAMME'S ANALYTIC MDE80 IS ANTI-CONSERVATIVE ON THE PLAYER CELL, BY 6.6×.

Not a defect I introduced, but one this screen surfaces and must not paper over.

`MDE80 = 2.802 × null_sd` is computed from the **observed** difference vector, which carries the
effect. A block sign-flip on a vector with a large mean shift has an inflated null sd, so the
analytic floor moves with the effect it is supposed to be independent of.

| Cell | analytic | injection | error |
|---|---:|---:|---|
| team MAE (Xb cell) | 4.596 | **2.00** | conservative 2.3× |
| player tier-A Brier (Xa cell) | 0.00038 | **0.0025** | **anti-conservative 6.6×** |

The anti-conservative direction is the dangerous one: a screen quoting the analytic 0.00038 could
declare an effect of 0.0006 "established and above the floor" when the null in fact detects it
only ~10 % of the time. **I have published both everywhere and treated the injection as the
authority.** No verdict here changes under either. Flagging it because other screens in this
programme quote the analytic form alone.

---

## D-4 — MY ROW SET WAS BUILT TO MATCH E1_I0033's, NOT DERIVED INDEPENDENTLY OF IT.

`s02` asserts `len(TF) == 1392`. I rebuilt RS1 from E1_I0033's *stated recipe* — not from their
files — but I asserted the target count, and had it come out 1,391 I would have gone looking for
the difference rather than proceeding.

This is the right choice for a **reproduction** (a comparison is only meaningful on an identical
row set, per D101) and it is what made the exact 6-dp agreement on B1 and A_TEAM MAE possible.
But it means the row set is **not independent evidence** that their recipe is correct — only that
mine implements the same one. Anyone treating "RS1 = 1,392" as independently confirmed here is
overreading it. The *statistics on* those rows were computed independently and are the reproduction.

---

## D-5 — THE `player_bios.csv` CROSS-TAB IS DEFECTIVE. Kept on disk, superseded, backs nothing.

`UNVERIFIABLE_bios_crosstab.csv` computes `undrafted = draft_round.isna()`, which conflates
**"undrafted"** with **"no bios row at all"**. Only 1,988 of 3,772 tier-B rows match a bios row, so
the reported `pct_undrafted = 0.528` is mostly just the 0.473 non-match rate. **The true
undrafted-among-matched share is roughly 0.10, not 0.53, and the table as printed is misleading.**

It is not corrected because the file is UNVERIFIABLE (no sibling manifest) and may not back a
number under the partition rules — so fixing it would only produce a more accurate number that
still cannot be used. **It is quarantined, banner-labelled, and no statement in `FINDINGS.json`,
`DEFECT_ANATOMY.md` or `REPAIR_OPTIONS.md` rests on it.** The population characterisation that
carries the load (P01/P03) is built entirely from the manifest-verified `master_player.parquet`.

Related: the non-match rate itself is interesting — 47.3 % of tier-B rows have no bios row for
that season, against 1.4 % of tier-A rows — and I have deliberately **not** drawn the obvious
inference from it, because the file cannot back one.

---

## D-6 — MY FIRST TIER-B STALENESS BANDING WAS DEGENERATE. Corrected, and the degeneracy kept.

I banded rows by days since the player's last appearance **for this team this season**, and every
one of the 3,772 tier-B rows fell in a single band. That is not a bug in the data — it is
*definitional*: tier B is precisely "no prior admitted box row for this club", so the band can
only ever take one value there.

**Fixed** by adding a second axis, last appearance **anywhere** (strictly prior), which is what
produced the decisive Z1/Z4 split. **The degenerate table is retained and printed** in
`staleness_bands_tier_B.csv` and `run_log_s03.txt` with a note, because the degeneracy is itself
the cleanest single statement of what tier B *is*, and deleting it would hide that.

A related bug in the same step: the tier-B player table grouped on `player_name`, which is NaN
whenever the player has no box row for that game — most of tier B — and pandas silently drops NaN
group keys. It reported 230 players carrying **−46.0** units of excess mass, an obviously
impossible sign that I caught only because the total was negative. Fixed with a partition-wide
name lookup and an assertion that the table partitions the tier (`who["n_rows"].sum() == len(XB)`);
correct answer 266 players, 1,596.9 units. **A quieter version of this bug would not have flipped
a sign and I would not have caught it.**

---

## Not defects, but limitations worth the same prominence

* **The repair the evidence actually points at was not measurable.** The population analysis says
  83.8 % of tier-B rows describe player-club pairings that never happen; the right fix is
  therefore to stop manufacturing the obligation, not to recalibrate the answer. That needs a
  roster source `prediction_contract_v5` explicitly declines to trust, and no manifest-verified
  artifact in this partition supplies one. **All four measured repairs treat the symptom.**
* **The exposure-shape number is a proxy.** It reproduces `build_projected_exposure`'s
  proportional allocation but omits the 40-minute cap and the water-filling loop, so 8.91 minutes
  is the un-capped figure. The *direction* and the Xb-cancels-exactly result are structural and do
  not depend on the omission.
* **Xa's 2022 fold is largely unrepaired** (5,135 rows pass through unchanged because 2021 emits
  only declared constants and both fitted strata have no training pool). This makes Xa's headline
  conservative, which is the safe direction, but it means the walk-forward number understates a
  properly-trained recalibration and the ORACLE gap overstates the achievable improvement.
* **I did not test any repair on 2025/26.** Sealed. Every number here is 2022–2024.
