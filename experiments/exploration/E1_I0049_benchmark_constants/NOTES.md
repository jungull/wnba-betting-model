# NOTES — E1_I0049_benchmark_constants

E1 **diagnostic**. Nothing here is a lead, a result or a promotion. No registry, ledger,
graph-event or idea-log entry was written by this screen. No production change is enacted. No
champion was fitted, loaded or touched.

PREREG: `PREREG.md`, sha256
`4770c3ac21a3e4e4d1c3e277d59dd7b49f1403d7e459e355b851945b58f23dfc`, hashed **before** any
statistic in this directory was computed and re-verified unchanged afterwards.

**Partition: 2021–2024 only.** `screenkit.assert_partition` (a VALUE test on parsed dates and
season-valued columns) after every load and every filter. **2025/26 was never read, joined,
plotted, described or inferred from.** Frames touched: `E1_I0018/screen_frame.parquet`
(14,852 × 59, seasons 2021/22/23/24), `E0_I0016/screen_frame.parquet` (join, opponent columns),
`E1_I0031/analysis_frame.parquet` (13,879, seasons 2022–2024),
`E1_I0004_fga_forecast/forecast_frame.parquet` (51,473 × 33). All read-only.

**Write scope respected.** Every file written by this screen is under
`experiments/exploration/E1_I0049_benchmark_constants/`. Nothing outside it was created, modified,
moved or renamed. **The shared screen kit was imported, never edited** — three sibling agents hold
it open and `_screen_kit/screenkit.py` is byte-identical before and after.

**No `git` command of any kind was run.**

**PROCESS DISCIPLINE.** No `Get-Process python | Stop-Process`, no `taskkill`, no blanket kill.
This screen launched short foreground `python` processes for `s01`, `s01b`, `s02`, `s03`, `s04` and
`s05` (nine invocations in total including re-runs), each of which ran to completion and exited on
its own.
**No PID required intervention and none was killed.** One early run of `s02` exited 1 by design
(the preregistered "fewer than 10 anchors → stop" rule fired) and one `s04` invocation was
terminated at exit 255 by a PowerShell `Select-Object -First` closing the pipe; both were re-run to
completion and both run logs are the completed ones.

---

## 1. WHAT WAS ASKED AND WHAT CAME BACK

The brief's premise was that the coordinator had propagated **unaudited** constants into a dozen
briefs. That is true of the *vocabulary* and false of the *arithmetic*.

* **Six of eight constants are numerically flawless.** `13,879`, `5,673`, `5,654`, `0.5633802817`,
  `0.00012940370236262536` and `0.0020571994` all re-derive from their artifacts, four of them
  exactly.
* **One is unverifiable to its own precision**: D079's `0.001127` exists only as a rounded scalar.
* **One is a naming collision**: `213` names two almost-disjoint sets.
* **The one that matters is mislabelled, not miscomputed**: `0.002057` is a transported ceiling
  with `c*` = 1.359, quoted as an effect.
* **Nothing reopens.** No killed cell, no gate, no verdict.

"The constants are correct as recorded" is *nearly* the outcome. The honest version is: **the
constants are correct as computed and wrong as named.**

---

## 2. ANCHORS — 22, ALL PASS, 13 AT 1e-16 OR BETTER

Reproduced before any new statistic, per PREREG §4. Full table in `raw/_s02_anchors.csv`.

| id | anchor | \|Δ\| |
|---|---|---|
| A1 | D089 `CEILING_dr2_points_per_sd` ≡ (move/sd_y)², 16 cells | 4.700e-11 (abs; inputs rounded to 10 dp) |
| A2 | D089 `CEILING_dr2_points_actual_shift` ≡ (move_sd/sd_y)², 16 cells | 4.768e-11 |
| A3 | D089 headline `0.002057` is `DECISION\|B_COMPLETE\|P01_c04_prevgame` | **0.000e+00** |
| A4 | D089 recon `realised ≡ (2c*−1)·var_share`, 16 rows | 3.807e-13 |
| A5 | D089 recon `oracle ≡ c*²·var_share`, 16 rows | 1.579e-13 |
| A6 | D084 `CEILING_A ≡ (move/sd_y)²`, 9 rows | 6.120e-13 (rel) |
| A7 | D084 headline `0.00012940370236262536` | **2.534e-17** |
| A8 | D089 volume-route ceiling from its own 5 components, 8 rows | 7.282e-13 (rel) |
| A9 | D103 blindness `760/1349` | **0.000e+00** |
| A10 | E1_I0026 analytic MDE80 ≡ `mde80_percell`, 1,189 rows, `t_crit` 1.645 | ≤1e-9 |
| A11 | D076 `13,879` appeared player-games | **0** |
| A12 | D089 `DECISION` n = 5,673 from the predicate | **0** |
| A12b | D089 `POOLED` n = 14,852 | **0** |
| A13 | `EXPOSURE_213` row count 213 | **0** |
| A14 | frozen-frame refit reproduces D089 `CEILING_dr2_points_per_sd`, 16 cells | 4.700e-11 |
| A14b | …reproduces `paired_dr2_points`, 16 cells | 4.806e-11 |
| A14c | …reproduces recorded `c*` | 4.517e-11 |
| A14d | …reproduces recorded ORACLE | **2.312e-13** |
| A15a | ARM P real ΔR² ≡ E1_I0026's recorded `real_dr2` | **3.643e-17** |
| A15b | ARM P `null_mean` ≡ E1_I0026's recorded null mean, 600 draws | **7.324e-17** |
| A15c | ARM P `null_sd` ≡ E1_I0026's recorded null sd | **1.868e-17** |
| A15d | ARM P n ≡ 5,673 | **0** |

A15b/c are the strongest: **600 entity-swap draws reproduced bit-for-bit** (the captured draw
vector matches the kit's own at `atol = 0`), which means the ARM T and ARM C arms measured beside
them sit on exactly D103's null sequence and are matched draw-for-draw.

Two anchor definitions were **changed after first running** and both changes are recorded in
`DEFECTS.md` D-08.3/D-08.4: A1/A2 moved from a relative to an absolute tolerance because
`E1_I0018/FINDINGS.json` rounds to 10 **decimal places**; A10 moved from `mde_table.csv` (a
*simulated* number) to `retrospective_power.csv` (where the analytic form is actually used).
**Zero anchors were dropped. Zero constants were added or removed from the PREREG §3 allowlist.**

---

## 3. THE ONE THING WORTH READING TWICE

`E1_I0018/FINDINGS.json`, one object, two adjacent keys:

```
"paired_dr2_points":          0.0033139323      <- what the shift actually bought
"CEILING_dr2_points_per_sd":  0.0020571994      <- the number written into a dozen briefs
```

The realised increment is **1.611×** the ceiling that bounds it, in the same object, since August
2026. `c*` = 1.3594722754. The true bound is 0.0035630546.

D125 said `0.002057` "has no recorded bound in either direction". That is right about
`arithmetic_ceiling.csv` and **wrong about the screen**: `ceiling_reconciliation.csv` records
`implied_optimal_rescaling` and `DIAGNOSTIC_ORACLE_ceiling_best_rescaling` for this exact cell. The
bound was in the record. It was missing from the ledger sentence.

---

## 4. NO NAME-BASED SELECTION

Six findings in this programme died to substring matching. Every selection here is an explicit
allowlist, printed in full and count-asserted:

* **constants**: PREREG §3 table, 10 keys, fixed before the sweep. Zero added, zero dropped.
* **files**: the s01 sweep resolved 56 `FINDINGS.json`, 148 `.md`, 694 `.csv` and 124 ledger
  entries; the `FINDINGS.json` list is printed in full in `scripts/run_log_s01.txt`.
* **candidates** (D089): `[T01_c04_tiptime, P01_c04_prevgame, P02_c04_availweighted, G01_noise]`,
  printed, `assert len == 4`.
* **negative controls** (the 213): `[G01_noise, G02_placebo_noop]`, printed, presence asserted,
  counts asserted `20 + 20 = 40` and `213 − 40 = 173`.
* **kills** (E1_I0036 census): `[POWERED_NULL, UNINFORMATIVE_NULL, CEILING]`, printed,
  `assert len == 1580` against E1_I0036's published figure.

**The CSV arm of the s01 sweep is deliberately not used as evidence.** Literal substring matching
against float text produces incidental hits (`0.00102` inside `0.001023…`) — 1,113 of them for that
one constant. The counts are in `raw/_s01_summary.json`; the *prose* record (ledger + `FINDINGS` +
`.md`) is what the census rests on. That is itself a small demonstration of the trap.

---

## 5. SIGNED, UNSTANDARDISED STORAGE

`raw/s03_null_draws_signed_raw.npz` and `.csv` hold all 600 draws × 3 arms **raw, signed and
unstandardised**, with the full stratum key
`DECISION|B_COMPLETE|N_B_entity_swap_team_season|P01_c04_prevgame` on every arm, plus `n`,
`n_draws`, `seed`, `SST_ppm` and `SST_pts`. No absolute values were taken and no standardisation
was applied at any point. 117 cells in this programme are permanently unauditable because one
screen stored standardised draws and 24 more because a stratum key was omitted; a successor can
recompute anything from these.

---

## 6. WHERE I COULD HAVE CHEATED

1. **Ceiling-form shopping.** D089 records **three** ceilings for the headline cell (0.0019279 /
   0.0020572 / 0.0020995) and a fourth on another row set (0.0012290). Choosing the smallest would
   have maximised the apparent breach. **All four are published in `DEFECTS.md` D-07 and the
   headline uses the one the ledger quotes** (0.0020571994).
2. **Floor shopping.** The DECISION-stratum K=1 floor ranges 0.00091–0.00336 across the published
   surface. Quoting the top would have made every kill look safer and every claim look worse.
   **The whole 20-row surface is printed in `scripts/run_log_s02.txt` and the interval is reported,
   not a point.**
3. **The D084 "10×".** It would have been easy to repeat E1_I0047's number. Checking it cost one
   table read and it does not survive; **the correction runs against the direction this screen was
   commissioned in** (it makes a prior defect smaller, not larger).
4. **The response mismatch could have been announced as a 30% error in every floor comparison.**
   It is reported as a **ratio from one carrier under one null with 600 draws**, with the absolute
   points-scale floors explicitly labelled indicative.
5. **Stratum/response shopping in the flip analysis.** Every comparison in `WHAT_WOULD_FLIP.md`
   that is cross-response is labelled cross-response, including the three of E1_I0047's four that
   are, and including D103's own headline sentence.
6. **The 213.** The decisive check is each cell's **own** `mde80_fw`, which is response-matched and
   which this screen did not compute — it read it from `EXPOSURE_213.csv`. Max ratio 0.4713, zero
   cells ≥ 1. That check makes every floor correction in this document irrelevant to the 213, and
   it is stated first in `WHAT_WOULD_FLIP.md` rather than after the corrections that do not matter.

---

## 7. THINGS A SUCCESSOR SHOULD KNOW

**A ceiling and an effect are different objects and this programme has one word for both.** The
single most expensive error in the record is not a wrong number — it is `0.002057` being read as
"how big the best thing is" when it means "how big the best thing could have been under a
construction that does not bound it". Any future brief should give effects and ceilings different
words.

**`(d·d)/SST` has a noise floor and it is now measured for the programme's most-cited ceiling.**
600 matched entity-swap draws through the identical transported path give null mean 1.357e-04 and
q95 5.276e-04 on n = 5,673. D089's ceiling clears it at 3.65× with p = 0.0017. **It cost 0.7
seconds.** There is no excuse for a ceiling table without a control column, and D125's "only 2 of
33 tables record one" is a cheap fix, not a deep problem.

**The floors are a surface, not a number.** `mde_table.csv` has 180 rows. Quoting one cell of it as
"the detection floor" has been the practice all session. The null matters more than the sample
(4.8× spread), the response matters ~30%, the drift correction matters up to 2.7×, and the family
size matters 2.3×. **Name the cell or quote the interval.**

**`n` is not a decoration.** Four row sets call themselves "the decision stratum". The correct
habit is to write `DECISION (n = 5,673)` every time, because `DECISION (n = 5,111)` is a different
question with a different answer.

---

## 8. FILES

| file | what |
|---|---|
| `PREREG.md` / `.sha256` | the hashed design, allowlists and dispositions |
| **`REFERENCE_CARD.md`** | **the corrected constants with full denominators — quote this** |
| `CENSUS.csv` | 9 constants × 16 columns: origin, denominator, bound status, control status |
| `RE_DERIVATION.csv` | 21 rows: source value vs re-derived value vs delta vs verdict |
| `WHAT_WOULD_FLIP.md` | nine judgements re-checked under the corrected constants |
| `DEFECTS.md` | eight defects, including this screen's own |
| `FINDINGS.json` | every number, machine-readable |
| `scripts/s01…s05` + `run_log_s0*.txt` | every stage's console output, in order |
| `raw/` | anchors, re-derived tables, the MDE grid copy, and the signed raw draws |
