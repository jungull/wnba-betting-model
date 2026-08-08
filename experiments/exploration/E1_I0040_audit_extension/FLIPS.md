# FLIPS — CELLS WHOSE VERDICT CHANGES UNDER THE MATCHED NULL

Screen `E1_I0040_audit_extension`. Companion to `VERDICT.md`.

---

## THE ANSWER: NONE. ZERO FLIPS IN THE THIRTY SCREENS.

`E1_I0038` found 52 per-cell flips and 11 family-wise flips across 83 exposed cells, all in D085.
**This extension finds 0 flips across its 32 exposed cells.** Nothing here is a lead, and there is
therefore nothing on this page to label an E0 LEAD.

That is not a null result reached by not looking. It is reached three different ways, and each is
recorded below with the cells it disposes of.

---

## HOW THE 32 EXPOSED CELLS WERE DISPOSED OF

| route | cells | can it flip? |
|---|---|---|
| **1. Matched null already on disk, and it kills too** | 16 | **No** — settled |
| **2. Below D103's single-cell floor of 0.00102** | 18 | **No** — no null can produce a lead |
| **3. Eligible under the frozen triage rule, null mean unrecoverable, NOT re-measured** | **7** | **UNKNOWN** |

(Routes 1 and 2 overlap on 9 cells; 16 + 18 − 9 = 25, plus 7 unresolved = 32.)

---

## ROUTE 1 — THE 16 `pm_all` CELLS ARE SETTLED FROM DISK

All 32 exposed cells are in `E1_I0031_rapm_as_prior`. Sixteen of them test the bundle `pm_all`
under a within-player-season cyclic null. The component that null is blind to is
`pm_prev_season_imp` — measured constant within player-season in **475 of 475** player-seasons,
maximum within-group spread **0.000e+00**, so the cyclic shift is provably the identity on it.

`E1_I0031` also tested that exact column **on its own, on the same rows, with the same statistic,
under its correctly matched between-player-season relabel null**, and wrote the result down.
`EXPOSED_DISCHARGE.csv`, all 16:

| target | over | stratum | ΔR² `pm_all` | p (blind cyclic) | ΔR² added by the blind component | p of the blind component under its MATCHED null |
|---|---|---|---|---|---|---|
| ppm | base_only | decision_stratum_wf | 0.001563 | 0.4718 | 4.83e-05 | 0.6422 |
| pts | base_plus_RAPM | wf_eval_2023_24 | 0.000251 | 0.9405 | 4.60e-05 | 0.3808 |
| minutes | base_only | decision_stratum_wf | 0.002061 | 0.1334 | 3.84e-05 | 0.9785 |
| minutes | base_only | wf_eval_2023_24 | 0.000520 | 0.4823 | 2.77e-05 | 0.3898 |
| ppm | base_plus_RAPM | wf_eval_2023_24 | 0.000537 | 0.8381 | 2.71e-05 | 0.5677 |
| ppm | base_only | wf_eval_2023_24 | 0.000470 | 0.8876 | 9.65e-06 | 0.4888 |
| pts | base_only | decision_stratum_wf | 0.001094 | 0.4428 | 3.05e-06 | 0.9375 |
| fga | base_only | decision_stratum_wf | 0.001134 | 0.0820 | 1.36e-06 | 0.9380 |
| fga | base_only | wf_eval_2023_24 | 0.000499 | 0.1659 | 1.64e-06 | 0.9440 |
| pts | base_plus_RAPM | decision_stratum_wf | 0.001203 | 0.3518 | 1.52e-06 | 0.8826 |
| pts | base_only | wf_eval_2023_24 | 0.000216 | 0.9720 | 1.47e-06 | 0.6052 |
| minutes | base_plus_RAPM | wf_eval_2023_24 | 0.000402 | 0.5177 | 9.73e-07 | 0.9150 |
| minutes | base_plus_RAPM | decision_stratum_wf | 0.001640 | 0.2369 | 4.41e-07 | 0.9985 |
| fga | base_plus_RAPM | decision_stratum_wf | 0.000926 | 0.1554 | 2.41e-07 | 0.9675 |
| ppm | base_plus_RAPM | decision_stratum_wf | 0.001850 | 0.3158 | 1.31e-07 | 0.8560 |
| fga | base_plus_RAPM | wf_eval_2023_24 | 0.000380 | 0.2539 | 1.29e-08 | 0.9610 |

**16 of 16: the blind component is killed by the null that can see it, at p between 0.381 and
0.999, and it contributes at most 4.83e-05 of ΔR².** The exposure is real and the verdict does not
move. This is `E1_I0038`'s "discharged with zero refitting" ruling, applied to a second screen.

---

## ROUTE 2 — 18 CELLS ARE BELOW THE FLOOR

`E1_I0038` PREREG 5.1 rules a cell ineligible for re-measurement when its observed statistic sits
below D103's single-cell floor of **0.00102**, on the ground that no null can produce a lead there.
The rule is applied here **as frozen**, not retuned. 18 of the 32 exposed cells fail it, ΔR² ranging
0.000205 to 0.000926 — a factor of 1.1× to 5× *below* the floor.

Every one of the 16 `wf_eval_2023_24` cells is in this group. **This is why the six cells that trip
`z < −1.0` produce nothing**: all six are `wf_eval_2023_24` cells at ΔR² 0.000205–0.000470, and
the flag firing on a cell below the detection floor is exactly the "there is simply no effect"
branch that `E1_I0038` identified as the source of the bare flag's 0.146 PPV. Ranked by |z| for
completeness, and **none of these is a lead**:

| rank | candidate | target | over | ΔR² | p (blind) | null mean | **z** | ΔR² ÷ floor |
|---|---|---|---|---|---|---|---|---|
| 1 | `pm_all` | pts | base_only | 0.000216 | 0.9720 | 0.000585 | **−1.501** | 0.21× |
| 2 | `pm_game_level` | pts | base_only | 0.000215 | 0.9570 | 0.000565 | **−1.419** | 0.21× |
| 3 | `pm_all` | pts | base_plus_RAPM | 0.000251 | 0.9405 | 0.000503 | **−1.340** | 0.25× |
| 4 | `pm_game_level` | pts | base_plus_RAPM | 0.000205 | 0.9220 | 0.000442 | **−1.221** | 0.20× |
| 5 | `pm_all` | ppm | base_only | 0.000470 | 0.8876 | 0.001103 | **−1.083** | 0.46× |
| 6 | `pm_game_level` | ppm | base_only | 0.000460 | 0.8876 | 0.001096 | **−1.051** | 0.45× |

**The largest is at 0.25× the single-cell floor.** Correcting the null does not correct the power —
`E1_I0038`'s own closing caveat, and it is the whole story for these six.

---

## ROUTE 3 — 7 CELLS UNRESOLVED, AND THEY ARE NOT CLEAN

These pass both filters. They are the only place in the thirty where a flip could still live.

| candidate | target | over | stratum | n | ΔR² | p (blind cyclic) | ΔR² ÷ floor | null mean |
|---|---|---|---|---|---|---|---|---|
| `pm_game_level` | minutes | base_only | decision_stratum_wf | 3,549 | 0.002023 | 0.1444 | **1.98×** | **GONE** |
| `pm_game_level` | ppm | base_plus_RAPM | decision_stratum_wf | 3,549 | 0.001849 | 0.3228 | **1.81×** | **GONE** |
| `pm_game_level` | minutes | base_plus_RAPM | decision_stratum_wf | 3,549 | 0.001640 | 0.2669 | **1.61×** | **GONE** |
| `pm_game_level` | ppm | base_only | decision_stratum_wf | 3,549 | 0.001514 | 0.4488 | 1.48× | **GONE** |
| `pm_game_level` | pts | base_plus_RAPM | decision_stratum_wf | 3,549 | 0.001202 | 0.3463 | 1.18× | **GONE** |
| `pm_game_level` | fga | base_only | decision_stratum_wf | 3,549 | 0.001133 | 0.0805 | 1.11× | **GONE** |
| `pm_game_level` | pts | base_only | decision_stratum_wf | 3,549 | 0.001091 | 0.4118 | 1.07× | **GONE** |

Ranked by effect size, as required. `GONE` is literal: `E1_I0031`'s draw archive omits the stratum
key and the decision-stratum arm's 2,000 draws were never written, so no null mean and no z exists
for any of these seven and none can ever be reconstructed from disk (DEFECTS D-02, proof in
`scripts/s06b_stratum_check.py`).

**They were not re-measured, and the reason is a rule, not an opinion.** The matched
between-player-season null for this bundle does not exist on disk — unlike D085 and D097, which ran
both arms, `E1_I0031` ran exactly one null per candidate. Producing a matched p means running a
fresh 2,000-draw permutation on a walk-forward stratum. That is a refit, and the brief makes
refitting the last resort. It also would not produce a finding: the result would be in-sample, on
one stratum, with no family recomputation and no walk-forward validation.

### What is knowable about them without a refit

Two on-disk facts, both reported as bounds rather than as answers:

1. **The blind null is a median 3.14× wider at p95 than the matched relabel null** on the same rows
   and the same statistic in the same screen (`NULL_WIDTH_CONTRAST.csv`; 2.28×–3.32× on the
   decision stratum specifically). A null 3× too wide is a lot of room. **This does not license
   dividing anything**: D101 forbids treating a different candidate bundle's null as a repriced
   denominator, and this is exactly that. It says only that the room is not negligible.
2. **`E1_I0031` recorded no family-wise p for any plus-minus cell.** Even a per-cell flip would
   have to clear a family of 24 before it meant anything, and the family-wise bar is not on disk
   either.

**If any of these seven flipped per-cell, it would still be an E0 LEAD and nothing more: in-sample,
one stratum, families not recomputed, no walk-forward, no power check.** None of them has flipped,
because none of them has been re-measured.

---

## THE RESULT THAT MOST WEAKENS THIS PAGE

`fga → pm_game_level, base_only, decision_stratum_wf` sits at **p = 0.0805 under a null that is
provably blind to 73% of the dominant column's variance**, at 1.11× the single-cell floor. That is
the closest thing to a flip in the thirty screens: a cell already within a factor of 1.6 of
significance, judged by an instrument that cannot see most of what it is judging, whose correct
comparator is roughly 2.3× narrower and whose null mean was deleted before anyone thought to look.

**It is not reported as a lead and it is not a finding.** It is reported because leaving it out
would make this page look tidier than the evidence is.
