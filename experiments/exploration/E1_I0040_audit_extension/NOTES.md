# E1_I0040 — AUDIT EXTENSION TO THE THIRTY UNAUDITED SCREENS — NOTES

Extends `E1_I0038_within_entity_null_audit` from 8 screens to all 38. Methodology is
`E1_I0038`'s, applied unchanged. Nothing was rederived.

---

## 1. THE TWO ANSWERS

**How much of the negative record outside the census is exposed? 32 killed cells of 1,304 — 2.5%.**
All 32 are in one screen, `E1_I0031_rapm_as_prior`. Half of them discharge from a number that screen
had already written down. None of them flips. The programme-wide total, combining with
`E1_I0038`'s 83, is **115 exposed kills of 2,671 auditable kills across all 38 screens — 4.3%.**

**Is `E1_I0021_heterogeneity_diagnostic`, the screen named as the highest risk, exposed? No — and
not by luck.** Two of its six regressors have measured between-player variance shares of 0.84 and
0.76, which trips the frozen rule mechanically. But its statistic is the SD of per-player slopes
fitted on within-player demeaned data, so the between-player component is annihilated before the
statistic exists. Manipulating that component changes the statistic by at most **4.441e-16**. The
rule has a scope condition nobody had stated; this is the first screen outside the census that
exposes it, and it is written up as DEFECTS D-03 rather than silently applied.

---

## 2. WHAT WAS ACTUALLY OPENED, AND WHAT WAS DELIBERATELY NOT

| | |
|---|---|
| screens in the programme | 38 |
| covered by `E1_I0036`'s census and audited by `E1_I0038` | 8 |
| **opened here** | **30** |
| ... that decide cells with a permutation null | **15** |
| ... that decide none (feature dumps, reproductions, power studies, the kit) | 15 |
| cells extracted | 2,085 |
| kills | 1,304 |

**Deliberately not counted as new cells:** `E1_I0026_detection_floor`'s 1,349 + 1,975 rows and
`E1_I0036`'s two `N_CYCLIC` re-measurements. Both are re-analyses of census cells that
`E1_I0036`/`E1_I0038` already audited, and counting them would double-count the programme-wide
total. Disclosed as a judgement call in DEFECTS D-08, not as a fact.

**Never opened:** any 2025/26 artefact. Every parquet frame is asserted free of season > 2024 and
date >= 2025-01-01 before a value is read. All CSV sources are 2021–2024 exploration artefacts. The
partition assertion is a hard `SystemExit`, not a warning.

---

## 3. THE ORDER THE WORK WAS DONE IN, AND WHY

| step | script | what it did |
|---|---|---|
| S00 | `s00_anchors.py` | **reproduced eight prior anchors exactly before computing anything new** |
| S01 | `s01_inventory.py` | inventoried all 30 screens: tables, p-columns, null-scheme columns, `.npz` archives, `max()` signature |
| S02 | `s02_probe.py` / `s02b` / `s02c` / `s02d` | a deliberately looser second pass, so a null `max()` result could not be a regex artefact; ceiling and verdict columns; CSV draw dumps tested for standardisation |
| S03 | `s03_schemes.py` | read the **source**, not the column names, for what null each screen actually constructs |
| S04 | `s04_audit_table.py` | built `AUDIT_TABLE_EXT.csv` |
| S05 | `s05_measure_shares.py` | **measured** between-entity variance shares on the screens' own frozen frames |
| S06 | `s06_resolve.py` / `s06b` / `s06c` | resolved UNDETERMINABLE cells; ran the decisive estimand check on `E1_I0021`; recovered null moments from `E1_I0031`'s own archive and proved which stratum they belong to |
| S07 | `s07_finalise.py` | consolidated, and repaired this screen's own substring-match defect |
| S08 | `s08_discharge.py` | discharged 16 exposed cells from disk with no refit; applied the frozen triage rule |
| S09 | `s09_coverage.py` / `s10` | coverage, record-keeping, flag operating characteristics |

The order matters in one place: **S05 before S06 before S08.** The exposure classification could not
be finished until the shares were measured, and the discharge could not be attempted until the
exposure was known. Attempting the discharge first would have produced a smaller exposed count and
a story that looked better.

---

## 4. WHERE THIS SCREEN COULD HAVE CHEATED, AND ONE PLACE IT DID

Every item is a real fork where a more flattering number was available.

1. **`E1_I0021` was the headline result available.** Applying the frozen rule mechanically gives
   **12 exposed cells in the screen the previous audit named as highest-risk** — a clean, quotable
   confirmation of a predecessor's prediction. The estimand check kills it. That check was run
   *because* the number looked too good, and its result is reported as the verdict with the
   mechanical number preserved beside it in `EXPOSURE_MECHANICAL_RULE` so a reader can overturn it.

2. **The 7 unresolved cells could have been called clean.** They pass no filter: above the floor,
   no matched null on disk, null means deleted. Calling them NOT_EXPOSED, or quietly folding them
   into the "below floor" group, would have produced "32 exposed, all discharged". They are recorded
   as **UNRESOLVED** and `FLIPS.md` names the single most awkward of them explicitly.

3. **The flag's specificity could have been quoted at `E1_I0038`'s 0.980.** Re-measured here it is
   **0.840**, on the only independent sample the rule has ever had. Reported in the verdict body,
   not in a footnote, even though it weakens a recommendation this screen otherwise endorses.

4. **The UNDETERMINABLE count could have been driven to 0.** 50 cells entered undeterminable; 44
   were resolved by measurement and 3 remain (3 more were reclassified as already-counted). Zero was
   reachable by inferring `is_home` and `FREED_minutes` from their names. `is_home` was **measured**
   (0.005025 on 21,462 rows) and `FREED_*` was left undeterminable because no share exists at its
   null's entity. `E1_I0038` reported 0 undeterminable and warned that this must not be read as an
   improving record; this screen reports 3 for the same reason.

5. **THIS SCREEN MADE THE ERROR IT WAS WARNED ABOUT.** `s04` matched `FREED_minutes` to
   `u_minutes` by substring and attached the wrong variance share to three cells. Caught by noticing
   that P01 was missing from the undeterminable list, repaired with an explicit map, and written up
   as DEFECTS **D-01** rather than fixed in silence. The brief said five findings here have died to
   substring matching; the count is arguably six.

6. **`E1_I0031`'s null-width ratio was available as a lever.** The cyclic null's p95 is a median
   3.14× wider than the matched relabel null's on the same rows. Dividing the seven unresolved
   p-values by anything derived from that ratio would have manufactured flips. D101 forbids it —
   different candidate bundle, different denominator — and it is reported as a bound on the room, not
   as a repriced p.

7. **The ceiling exclusion was applied, not stretched.** 20 ceiling-attaining cells were identified
   and none was re-measured. It would have been possible to argue that `E1_I0036`'s fair-test cells
   are not "really" ceiling kills and re-open them; they were left alone, because a ceiling is
   arithmetic and survives every methodological revision including this one.

---

## 5. WHAT THE THIRTY LOOK LIKE, IN ONE PARAGRAPH

They are cleaner than the eight, and mostly on purpose. Fourteen of the fifteen screens that decide
cells have zero exposure. Two are immune by design by two different mechanisms: `E0_I0015` picks its
permutation scheme from the measured variance share in its own code
(`s03_mechanism_and_abstention.py:284`) and publishes the 55 shares it used, so its 358 within-block
kills top out at a measured share of 0.4791 and cannot be exposed; `E1_I0021` uses an estimand that
makes the choice moot. `E1_I0030` runs the unsafe within-shuffle beside the safe cyclic one and
labels it unsafe in its own source. `E1_I0027`, `E1_I0031`, `E1_I0036` report one null per row and
never combine them. **The banned `max(p_within, p_between)` conjunction — the defect that produced
`E1_I0038`'s entire finding — occurs zero times in thirty screens.** The programme's null machinery
outside the census was already right, and where it was right it was right on purpose.

---

## 6. THE ONE THING THAT IS WORSE OUT HERE THAN IN THE CENSUS

**Record-keeping.** 21.3% of cells in the thirty carry a null mean beside their p, against 42.3% in
the census. The offsetting good news is larger: **0 of 30 screens stored draws standardised**, so
`E0_I0017`'s permanent loss of 117 cells does not recur, and 1,592 of the 1,616 missing null means
are recoverable from archives already on disk.

The exception is exact and it is expensive. `E1_I0031`'s draw archive is keyed on four columns and
its results table on five; the missing key is `stratum`, and the arm that was never written is the
**decision** stratum. 24 null means are gone, 16 of them on exposed cells, including all 7 cells
this audit's own triage rule would have made eligible. **A missing key is worse than
standardisation, because the file still loads, still parses, still joins — and answers about the
wrong arm.** Detected only by matching the archive's p95 against the recorded `null_p95` and finding
it exact on half the rows and wrong on the other half.

---

## 7. SCOPE COMPLIANCE

* Wrote only inside `experiments\exploration\E1_I0040_audit_extension\`. Nothing outside was
  written, staged, or committed. No `git` write command was run.
* **`_screen_kit` was opened read-only**, for its scheme vocabulary only. Not modified, not copied,
  not patched. Other agents hold it open; it was never touched.
* **No process was killed.** Every Python invocation was synchronous and short-lived in the
  foreground; none outlived its command, so no PID needed recording. No `Stop-Process`, no
  `taskkill`, no `Get-Process python | Stop-Process` — no blanket kill of any kind was issued at any
  point. Sibling agents' processes were never enumerated, let alone signalled.
* All frozen exploration frames and every prior screen's outputs read **read-only**.
* 2021–2024 only; 2025/26 never opened, asserted rather than assumed.
* No champion fitted. No production change enacted. No cell re-measured. The only arithmetic
  performed on raw data was a variance share and a slope dispersion, both measurements of existing
  frozen columns.

---

## 8. FILES

| file | what |
|---|---|
| `VERDICT.md` | the answer, counts, and what would change it |
| `FLIPS.md` | zero flips, the three routes that dispose of all 32 exposed cells, and the most awkward remaining cell |
| `DEFECTS.md` | 9 defects, two of them in this screen's own work |
| `FINDINGS.json` | every headline number, machine-readable |
| **`AUDIT_TABLE_EXT.csv`** | **2,085 cells × 37 columns** — the deliverable: null scheme, class, combination rule, candidate level, measured variance share and its source, null mean and its source, observed, z, both flags, exposure and its reason, plus `EXPOSURE_MECHANICAL_RULE` so a reader can overturn DEFECTS D-03 |
| `nulls/E1_I0031_plusminus_wf_eval_recovered_draws.npz` | the 24 × 2,000 raw draws this audit recovered, with the stratum attribution the source file lacks |
| `EXPOSED_CELLS_EXT.csv` | the 32 exposed kills with their triage disposition |
| `EXPOSED_DISCHARGE.csv` | the 16 discharged from disk, with the matched p that discharges them |
| `MEASURED_VARIANCE_SHARES.csv` | 25 shares measured on frozen frames, with the frame and row count |
| `E1_I0021_ESTIMAND_CHECK.csv` | the 4.441e-16 result |
| `E1_I0031_RECOVERED_NULL_MOMENTS.csv` | 24 null means recovered from that screen's own archive |
| `E1_I0031_EXPOSURE_DETAIL.csv` | per-cell exposure for the one exposed screen |
| `NULL_WIDTH_CONTRAST.csv` | cyclic vs relabel null p95, same rows, reported as a bound only |
| `COVERAGE_EXT.csv` | per-screen coverage and record-keeping |
| `MAX_SIGNATURE_HITS.csv`, `MAX_SIGNATURE_LOOSE*.csv` | the `max()` hunt, both passes |
| `SCHEME_BY_SCREEN.csv`, `SCHEME_CODE_HITS.csv` | what null each screen constructs, read from source |
| `INVENTORY_*.csv` | screens, tables, `.npz` and CSV draw archives, verdict/ceiling columns |
| `scripts/s00`–`s10`, `run_log_*.txt` | everything above, reproducible |
