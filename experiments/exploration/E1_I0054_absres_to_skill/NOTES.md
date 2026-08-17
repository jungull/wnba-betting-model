# NOTES — E1_I0054 · absolute residual → skill, or variance?

PREREG sha256 `7054f16908c7a2360aab0e48cd932ae1979a88a85e449e74ac373b3600a4c36a`
(`PREREG.sha256`, written before any statistic in this screen was computed).
Partition **2021–2024**. **2025/26 was never opened**; the guard is asserted on `season` and on
`gdate` in `scripts/_common.py` and re-asserted by every caller.

---

## The four answers, in order

| question | answer |
|---|---|
| **Do the sixteen reproduce?** | **Yes — exactly, at three seeds, symmetric difference 0. A1_FULL's 36 too.** |
| **Does it improve points?** | **No.** 96 channel arms; best ΔR² **+0.00047**, cluster p **0.41**, floor **0.00072**. |
| **How much is a volume proxy?** | **12 of 16.** Median retained ΔR² **24%**; five cells keep **< 1%**. |
| **What is the variance forecast's calibration?** | Top/bottom predicted-error decile ratio **1.63** (points, CI 1.42–1.90), **1.91** (minutes), calibration slope **0.93–1.01**. On points and FGA, trailing level alone matches it. |

---

## Reading order

1. `REPRODUCTION.md` — the anchors and the sixteen.
2. `VOLUME_PROXY.md` — the degenerate explanation, excluded first as required.
3. `SKILL_OR_VARIANCE.md` — the central answer, in its first three sentences.
4. `CALIBRATION.csv` / `CALIBRATION_DECILES.csv` — the fallback value, measured.
5. `DEFECTS.md` — mine, and two found in others' work.

## Files

| file | what |
|---|---|
| `REPRODUCTION.csv` | 54 cells × 2 arms × seeds: observed signed t, ΔR², null mean signed t, per-cell and family-wise p, my verdict |
| `VOLUME_PROXY.csv` | 54 cells × 5 bases: t, ΔR², retained share, family-wise p under that base's own null |
| `CALIBRATION.csv` | 3 targets × 2 schemes × 5 variance models: decile spread, ratio + block-bootstrap CI, Spearman, calibration slope/intercept, OOF R² |
| `CALIBRATION_DECILES.csv` | the reliability curves themselves, 10 rows per cell of the above |
| `POINTS_TEST.csv` | 96 channel arms + references: ΔR² on points, both cluster sign-flip p, floor comparisons |
| `ABSTENTION.csv` | S5, scored on MSE against 2,000 matched random subsets |
| `TYPEI_CENTRED.csv` | T1/T3: centring check, composed-2 Type-I, null mean signed t on the real response |
| `_T2_PLACEBO.csv`, `_T2_PLACEBO_RAW.csv` | T2: Type-I of the points statistic under a placebo `v̂` |
| `_PLACEBO_CALIBRATED.csv` | observed channels read against their own placebo distribution |
| `_ABSTENTION_DECOMPOSED.csv` | POST-HOC: R² on retained rows, and a level-only abstention rule |
| `_PRED_COLUMN_DEGENERACY.csv`, `_PRED_CV_MECHANISM.csv`, `_PRED_CV_SUBSTITUTION.csv` | POST-HOC: what `pred_cv` actually is |
| `_BAR_ANATOMY.csv`, `_BAR_ANATOMY_BY_BASE.csv` | T4: single-cell dominance of every family-wise bar reported |
| `_LEVEL_CORRELATIONS.csv` | candidate ↔ trailing level ↔ response correlations |
| `raw/*.npz` | **signed, unstandardised draws** with full stratum keys: season, player_id, team_id, gdate, player-season block, team-season block |

`np.abs` appears at no storage site. Every `.npz` stores the signed statistic.

---

## Things measured here that were not known before

1. **`<target>__pred_sd` takes exactly ONE value per season on the decision stratum** (and 3
   values on the full 13,879 rows, one per season). The shipped forecast emits a constant
   uncertainty. Consequence: `<target>__pred_cv` **is** `k(season)/<target>__pred_point`, and
   substituting `1/pts__pred_point` reproduces five of the sixteen cells to every printed digit.
   This is the mechanism behind the largest apparent positive result in the programme.
2. **The repaired family-wise bar is set by TEAM-scheme candidates.** Its most frequent supplier
   is `tm_poss_mean_prior|minutes_absres` (12.5% of 2,000 draws, 284 distinct suppliers). On the
   decision stratum there are **24** team-season blocks against **174** player-season blocks, so
   the team candidates have the widest nulls and set the bar for a family that is 41/58
   player-level. Conservative for every player-level cell in it.
3. **The programme's "largest positive result" is mostly about minutes, not points.** Nine of
   the sixteen cells have a `minutes` response; only three have a points-error response; and
   **none of the three survives the volume base**. All four B3 survivors are minutes.
4. **Variance weighting has a systematic non-zero effect on the points forecast** of magnitude
   ≈ 2×10⁻⁴ ΔR² — 8–9 sd above a noise-`v̂` placebo, and about **one third of the single-cell
   detection floor**. Real, correctly signed, and far too small to matter. Recorded because it
   is the finding that most weakens this screen's own null conclusion.
5. **Abstention's MSE gain is a level effect.** Dropping the top 30% by predicted error cuts MSE
   12.5% but cuts response variance 22.1% and lowers R² on the retained rows by 8.4 points; a
   rule using the forecast level alone cuts MSE **13.7%**.

## Preregistered predictions — as they came out, not as predicted

| id | prediction | outcome |
|---|---|---|
| P-R1 | A4 family-wise set has cardinality 16 | **HELD** |
| P-R2 | across three seeds the set varies by ≤ 2 cells | **HELD** (0) |
| P-R3 | bar q95 within ±0.30 of 5.323 | **HELD** (5.2935) |
| P-V1 | `pts__pred_cv\|pts_absres` retained share under B2 < 0.50 | **HELD** (0.012) |
| P-V2 | ≥ 3 minutes candidates retained > 0.50 under B2 | **HELD** (4 of 5) |
| P-V3 | ≥ 4 of the 16 lose family-wise significance under B3 | **HELD** (12) |
| P-C1 | VSIG minutes top/bottom decile ratio > 1.6 | **HELD** (1.909) |
| P-C2 | VSIG beats V0 on OOF R² for all three targets | **HELD** |
| P-C3 | VSIG does **not** beat VSD by > 0.02 OOF R² on points | **FAILED** — gap **0.032**, because VSD is a per-season constant |
| P-S1 | no channel meets the decision rule | **HELD** |
| P-S2 | S3's `v̂` coefficient not significant at cluster p < 0.05 | **HELD** (p 0.41) |
| P-S3 | abstention cuts MSE > 15% at q = 30% | **FAILED** — 13.2% (12.5% on the fixed-threshold decomposition) |

Two of twelve failed. Neither threshold was revised after seeing a result; no seed, draw count,
sample size or tolerance was changed after measurement.

---

## Processes launched by this screen (PROCESS ISOLATION)

**No blanket kill of any kind was issued at any point.** No `Get-Process python | Stop-Process`,
no `taskkill`, no wildcard, no `Stop-Process` at all. Sibling agents were running throughout and
none of their processes was touched.

| PID | script | fate |
|---|---|---|
| 28056 | `s01_reproduce.py` | ran to completion (85 s) |
| 19348 | `s02_volume_proxy.py` | ran to completion (126 s) |
| 4512 | `s03_calibration.py` (run 1) | **exited on its own** with `LinAlgError: Singular matrix` — `pts__pred_sd` is constant on the training window. Not killed. Log preserved as the current `run_log_s03_err.txt` content was overwritten by run 2; the defect is recorded in `DEFECTS.md` D-1 and the cause is the finding in `VOLUME_PROXY.md` §3. |
| 24828 | `s03_calibration.py` (run 2) | ran to completion (43 s) |
| 16624 | `s04_points_test.py` | ran to completion (96 s) |
| 23760 | `s06_typeI_centred.py` | ran to completion (23 s) |

`s00`, `s02b`, `s05`, `s07` ran in the foreground. PIDs are recorded in `scripts/_pid_s0*.txt`.

## Scope

Everything written by this screen is inside
`experiments/exploration/E1_I0054_absres_to_skill/`. No file outside it was created or
modified. No `git` write command was issued. The shared screen kit, `E0_I0014`, `E1_I0044`,
`E1_I0049` and `E1_I0050` were opened **read-only**; `E1_I0044`'s and `E1_I0050`'s scripts were
read for specification and **never imported or executed**. **No production change is enacted or
recommended.**
