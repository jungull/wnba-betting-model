# INDEPENDENCE — ARE THE FOUR SIGHTINGS FOUR MEASUREMENTS?

Screen `E1_I0043_opponent_defence` · `PREREG.md` sha256
`629fe4aa2d757d393ec7db5861feba28e431f25cb89562ac1e61e05cf9b73add`
Partition 2021–2024 exploration only. 2025/26 was never opened.
Evidence: `INDEPENDENCE.csv`, `INDEPENDENCE_ROWSETS.csv`, `AFAMILY_CORRELATION.csv`,
`scripts/run_log_s01.txt`.

---

## THE ANSWER: NO. THEY ARE ONE SIGHTING, SEEN FOUR TIMES.

**All four sightings read the same 14,852 values of the same column out of the same physical file —
`experiments/exploration/E0_I0016_efficiency_predictors/screen_frame.parquet`, column
`A10_opp_defrtg` — measured against the same response `y_ppm`, on four row sets that are strictly
nested inside one another.** Maximum value difference between the column any sighting used and the
source column: **0.000e+00 across all 14,852 rows.**

The corroboration pattern the brief flagged is exactly the shared-upstream signature, not four
independent arrivals. **No corroboration credit may be taken from the count of four.** The correct
statement of the programme's evidence is: *one measurement of one column, refined four times.*

---

## THE SHARED-INPUT AUDIT, STATED EXPLICITLY

| axis | shared? | evidence |
|---|---|---|
| **the column** | **IDENTICAL** | one file, one column, max\|diff\| **0.000e+00** |
| **the source file** | **ONE** | `E0_I0016/screen_frame.parquet` sits at the root of all four |
| **the row set** | **FULLY NESTED** | S1 ⊂ S2 ⊂ S3 ⊂ S4, every pair contained |
| **the response** | **SHARED** | `y_ppm` is reported by all four; it is the only response common to all four |
| **the reference** | **SAME FAMILY** | all four use the `refB_*` player-prior family; none carries a possession or opponent-pace term |
| **the frame** | **ONE** | 14,852 rows, 247 players, 48 opponent-team-seasons, 827 games |

### The provenance chain (I5)

```
E0_I0016_efficiency_predictors/screen_frame.parquet  ->  A10_opp_defrtg
  |-- E1_I0021 (D093)  merged D085+D089        -> Spearman +0.320   [the STRUCTURAL claim]
  |-- E1_I0023 (D098)  merged D085+D089        -> SIGHTING 1
  |     `-- E1_I0025 (D099) confirmation of S1 -> SIGHTING 2
  |-- E1_I0026 (D103)  joined D085 onto D089   -> SIGHTING 3
  `-- E0_I0016 own recorded null (D085)        -> SIGHTING 4 via E1_I0038 (D117)
```

Resolved on bytes, not on names:

* `E1_I0023/uid_base.py:92` — `pd.read_parquet(os.path.join(D085F, "screen_frame.parquet"))`,
  where `D085F = E0_I0016_efficiency_predictors`.
* `E1_I0025/cbase.py:54` — `DEFENCE = "A10_opp_defrtg"`, on the same merged frame.
* `E1_I0026/NOTES.md:2` — *"joined 1:1 and losslessly on `(player_id, game_id)` to
  `E0_I0016_efficiency_predictors/screen_frame.parquet` for the opponent columns."*
* `E1_I0038` did not measure anything new at all: it read D085's own recorded matched-null p out of
  `E0_I0016/screen_results.csv`.

**A defect in how that one column was constructed would propagate to all four identically, and no
combination of the four could detect it.** This screen therefore ran its own leakage probe rather
than inheriting one (see below).

### The row sets (I2)

| sighting | ledger | screen | rows |
|---|---|---|---|
| S1 | D098 | `E1_I0023` top usage tercile, decision stratum, walk-forward | **1,687** (recorded) / 1,505 (reconstructed here) |
| S2 | D099 | `E1_I0025` decision stratum, common denominator | **4,514** (recorded and reproduced exactly) |
| S3 | D103 | `E1_I0026` decision stratum, in-sample | **5,673** (recorded) / 5,670 (reconstructed here) |
| S4 | D117 | `E1_I0038` / D085, the whole frame | **14,852** (reproduced exactly) |

Every pair is contained: `a ⊆ b` or `b ⊆ a` for all six pairs. Jaccard runs 0.101 (S1 vs S4) to
0.796 (S2 vs S3). **There is no pair of sightings measured on rows that differ by a single
independent observation.**

*Disclosure.* S1 and S3 are RECONSTRUCTIONS and miss their recorded counts by 182 and 3 rows
respectively — the tercile cut and the complete-case column list are not recorded to the row in
their source screens. The containment conclusion does not depend on the reconstruction: the
recorded counts 1,687 < 4,514 < 5,673 < 14,852 are themselves nested, and 4,514 and 14,852
reproduce exactly. This is recorded in `DEFECTS.md` as D-03.

---

## S1 AND S2 ARE NOT EVEN TWO SIGHTINGS OF ONE COLUMN — THEY ARE ONE INVESTIGATION

D099 is not an independent arrival. Its own ledger entry describes it as the confirmation D098's
coordinator *dispatched*: "D098 raised a lead worth dR2 +0.023863 … and the coordinator held it
pending one named test". D099 then **corrected D098's headline downward by a factor of four** and
**withdrew D098's ceiling claim**. Counting a finding and its own correction as two independent
sightings double-counts the weakest of the four.

D103's arrival is likewise incidental rather than independent: the agent was using `A10_opp_defrtg`
**as a power carrier** for an unrelated measurement and noticed the statistic in passing. It
explicitly declined to raise it.

**A more honest count of the record is: ONE channel, ONE column, ONE row family — investigated
once (D093/D098), corrected once (D099), noticed once in passing (D103), and once recovered from a
null-audit column (D117).**

---

## D103'S STATED REASON FOR TREATING ITS SIGHTING AS NEW IS FACTUALLY WRONG

`E1_I0026/NOTES.md` justifies the incidental sighting as being "on an outcome D085 did not screen
the A-family against (D085 screened them against **efficiency**, not points-per-minute)".

**D085 did screen `A10_opp_defrtg` against `ppm`.** `E0_I0016/screen_results.csv` carries the cell
`ppm|A10_opp_defrtg`, n 14,852, dR² 0.001443, alongside `ts` and `efg` — 12 A-family constructions
× 3 outcomes {ppm, ts, efg} = the 36 cells D085's ruling names. The outcome set was
{points-per-minute, true shooting, effective FG}, and points-per-minute is in it.

So D103's sighting was not a new outcome. It was **the same candidate, the same response and a
subset of the same rows as sighting 4**, measured in-sample instead of pooled. Recorded in
`DEFECTS.md` as D-04.

---

## I6 — AND D085'S "TWELVE CONSTRUCTIONS" WERE NOT TWELVE TESTS EITHER

D085's headline kill reads "0 of 36 cells across TWELVE separate constructions". Measured on its
own frame:

| | corr with `A10_opp_defrtg` |
|---|---|
| `A02_opp_ts_allowed` | **+0.8289** |
| `A01_opp_efg_allowed` | **+0.8153** |
| `A05_opp_fg3pct_allowed` | +0.6473 |
| `A09_opp_stl` | −0.4819 |
| `A11_opp_fastbreak_allowed` | +0.4208 |
| the remaining six | +0.2205 to +0.3047, and `A04_opp_blk` −0.1997 |

The 12-column correlation matrix has eigenvalues
`[4.13, 2.10, 1.70, 1.10, 0.84, 0.77, 0.70, 0.34, 0.17, 0.09, 0.06, 0.008]`:
**8 components carry 95% of the variance and 10 carry 99%.** The leading component alone carries
34% of it.

Twelve constructions is a defensible description of the *intent*. It is not twelve independent
tests, and a family-wise correction computed as if it were is conservative in the count and
optimistic about what breadth was actually purchased. This does not change D085's verdict — which
this screen reproduces to 9.3e-18 — but it does change what "comprehensive" bought.

---

## WHAT WOULD OVERTURN THIS PAGE

**A genuinely independent sighting is available and nobody has taken it.** Opponent defensive
rating can be rebuilt from `master_team` by an independent shift-then-expanding construction —
D098 did exactly that as a leakage probe and matched the frozen column to **1.42e-14**, which
proves the frozen column is faithful but is not an independent measurement, because it is the same
estimator recomputed. An independent sighting would need a *different estimator of opponent
defensive strength* (opponent points allowed per game; a RAPM-derived defensive rating; an
opponent-adjusted rating), measured on a **different row set**, against a **different response**.
This screen did not build one, and until someone does, the count of independent arrivals at this
channel is **one**.

The nearest thing to an independent replication that exists is this screen's own probe on the
**opponent's previous-season** mean defensive rating — a different row-to-value mapping using only
prior-season information. It returns dR² **+0.00094** on `y_ppm` (against +0.00940 for the
in-season column): **below the single-cell detection floor of 0.00102**. The one construction that
is even partly independent of the in-season column carries essentially nothing. That is the result
on this page that most weakens the case for the channel being a durable property of teams, and it
is reported here rather than in a footnote.
