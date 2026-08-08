# DEFECTS -- E1_I0036_level_artefact_sweep

Defects found in this screen's own work, in the programme's recorded evidence, and in the
methodology this screen was directed to apply. Severity A = would change a verdict.

---

## D-01 (A) -- 27.6% OF KILLED CELLS NEVER RECORDED THE LEVEL THEY WERE MEASURED AT

**436 of 1,580 killed cells** carry `level_recorded = NOT_RECORDED`. Their source screens
(`E0_I0019_availability_forecast` 318 cells, `E1_I0018_teammate_volume_channel` 154,
`E1_I0023_usage_defence_interaction` 120) ran level-aware nulls — `p_N1_within_entity`,
`p_N2_entity_swap`, `scheme_between`, `p_cluster` — but never wrote down **what the entity
was**.

Consequence: those cells are ineligible for the triage rule and are invisible to this
screen. I did not infer a level from candidate names (five findings have died to name-based
selection), so the hole stays a hole.

D111 ruling 1 already requires every future screen to state its level. **This defect shows the
requirement must be retrospective as well: a recorded `p_correct_level` without a recorded
level is not auditable.** `E1_I0018` in particular records
`var_share_between_team_season` — which strongly implies the entity — but implication is not a
record.

**Remedy:** amend the shared screen kit so `level` / `entity_level` is a REQUIRED column
beside every `p_correct_level`, and assert it non-null.

---

## D-02 (B) -- THE FROZEN KILL-REASON LADDER ASSERTS POWER IT NEVER MEASURED

PREREG 4.2 rule 4 assigns `POWERED_NULL` to any non-blind, non-surviving, non-ceiling cell.
But "non-blind" was read off D103's flags, and **`E0_I0029_freethrow_hurdle` (560 cells,
D108) post-dates D103 entirely and has no D103 power record.** 381 of its cells therefore
landed in `POWERED_NULL` — a claim that they were adequately powered, which was never checked.

Found after the rule was frozen and the selection made. **The frozen label is retained
unchanged so the preregistered triage selection is unaltered** (verified: the top-ranked pair
is `M06_opp_pace → y_fta` before and after). A corrected label is published beside it in
`CENSUS.csv` as `kill_reason_corrected`, where those 381 cells read `POWER_NOT_ASSESSED`.

Effect on the headline: the eligible set and the four re-runs are unchanged.

---

## D-03 (B) -- ONLY ONE SCREEN EVER WROTE AN ARITHMETIC CEILING TO DISK

`CEILING` can only fire in `E0_I0024_reb_ast_characterisation`, the only screen with an
`arithmetic_ceiling.csv` / `CEILING_dr2_*` column. All 213 ceiling kills in the census come
from it.

Ceiling kills certainly exist in the other seven screens — D084's conversion kill is one, and
it is recorded in the ledger rather than in a cell table — but this census cannot see them. The
count of ceiling kills is therefore a **floor, not a total**, and the eligible fraction
(7.5% of killed cells) is correspondingly an **over-estimate**: some eligible cells are
ceiling kills that were never labelled as such.

Direction of the error is conservative for this screen's headline (fewer genuine
re-levelling candidates than counted, and the headline is that re-levelling does not work).

---

## D-04 (A) -- **D108's INJECTION PROTOCOL CAN PASS A NULL THAT IS INVALID FOR THE CANDIDATE**

This is the most important defect here and it is in the methodology, not the data.

D108 ruling 4 made injection verification mandatory: plant a signal, confirm the null detects
it. PREREG 5.3 implemented it faithfully. **`N_CYCLIC` passed it on the D097 cell with power
0.95 at 0.002057**, and by PREREG 6.4 would have been declared the matched null, letting a
false negative stand.

The reason it passes: to build a synthetic response with no real signal, the protocol shuffles
the base residuals. That shuffle **destroys the between-entity structure of the RESPONSE** —
which is exactly the structure `N_CYCLIC` fails to destroy in the **CARRIER**. The test and the
defect cancel each other out, and the null looks fine.

Planting the signal along the *between-entity component* of the carrier instead exposes it
immediately: **power 0.00, in both strata, in 120 replicates.**

**Remedy — proposed amendment to the D108 convention:**

> Injection must be run **component-wise**, not only on the full carrier. Decompose the
> carrier into its between-entity and within-entity parts at the level the null operates on,
> and require the null to detect a planted signal in **the component that carries the majority
> of the candidate's measured effect**. A null that cannot see that component is void for that
> candidate regardless of its power on the full carrier.
>
> Additionally, publish `null_mean` beside every p (D103 already requires this) and **flag any
> cell where `null_mean > observed`**. That single comparison catches this failure mode with no
> extra compute, and it fired on 2 of 2 affected cells here.

---

## D-05 (B) -- "DEGENERATE" AND "UNDERPOWERED" WERE CONFLATED BY THE FROZEN CRITERION

PREREG 5.3 declares any null that fails to detect 0.002057 **DEGENERATE**. Applied at team
level (n = 1,486) this labelled every team-level null degenerate — including `N_ROW`, which
cannot be structurally degenerate.

The label was wrong; the nulls were fine. They reach power 1.00 at delta 0.020 and their MDE80
is 3.5e-03 – 4.4e-03. They are **underpowered at 0.002057 because n is 9x smaller**, not blind.

Corrected in `s12` with a three-way status: `DEGENERATE` (no power even at large delta),
`ANTICONSERVATIVE` (type-I > 0.10), `USABLE_BUT_UNDERPOWERED_AT_<delta>`. The distinguishing
test is whether power rises with delta.

`s11`'s `null_status` column retains the wrong label and is superseded by
`LEVEL_FAIRTEST_CELLS.csv`. **The distinction matters:** a degenerate null voids a verdict; an
underpowered one makes it uninformative. Both were previously called the same thing.

---

## D-06 (B) -- s11's TEAM-LEVEL BASE WAS WEAKER THAN THE PLAYER-LEVEL BASES IT WAS ANSWERING

`s11` used a 3-column team reference against player screens that used 10-column `B_COMPLETE`.
That is D087 reference incompleteness working in the candidate's favour, and it produced
apparent team-level survivals (L4 `p = 0.0050`) that **collapsed by 5.3x** once the reference
was strengthened in `s12` (L4 `p_fw = 0.216`).

Caught and corrected within the screen. `s11` results are retained for the record and are
**superseded by `s12`**; nothing in the verdict rests on them.

Lesson for the programme: **a cross-level survival claim is only as good as the weaker of the
two references**, and it is very easy to build a thin one at a new level by accident.

---

## D-07 (C) -- THE C1 LEVEL-UP CONTROL IS NOT MULTIPLICITY-CONTROLLED

`ROSTER_RA_SHARE → T_oreb` (`D097_RELEVEL_CELLS.csv`) was run to discharge PREREG 6.6, after
the player-level result was known. It is a control, not a preregistered hypothesis test, and it
sits outside the K=4 family-wise correction. Its `p = 0.0066` should be read as descriptive.

---

## D-08 (C) -- FAMILY-WISE MAX-z USES INDEPENDENT DRAWS PER CELL

The K=4 correction in `s12` builds the max-statistic null from independently drawn permutation
sets per cell rather than from a common draw index. This is the convention the programme's
other screens use (`p_familywise_maxt`, `p_familywise_maxz`), so the numbers are comparable,
but it ignores the positive dependence between cells sharing a response (L3 and L4 both target
team points) and is therefore **mildly conservative**. Direction is against the candidates, so
it does not manufacture a survivor.

---

## NOT A DEFECT, RECORDED SO IT IS NOT RE-LITIGATED

- **The 51.1% blindness figure here vs D103's 56.3%** is a different denominator, not a
  contradiction. This census spans 1,999 cells over 8 screens including the 560 post-D103 cells
  of `E0_I0029`; D103 spanned 1,349 cells over 7. Restricted to D103's screens the figures
  agree.
- **`R08_player_ra_share` is not a retrospective baseline.** Verified by reading its
  construction (`prior_sum(p_ra)/prior_sum(p_att)`, expanding, strictly prior), not assumed.
  All team-level references built here additionally passed the empirical `A_NO_RETRO_2` test:
  the last 20% of each season was deleted, every reference rebuilt, and **0 mismatches** over
  1,222 surviving rows across four responses and three reference forms.
- **Roster completeness** was asserted, not assumed: 1,522/1,522 team-games have summed player
  minutes equal to 200 + 25·(overtimes) within 1.0 minute, and the player-sum equals the
  independent team box total on **100.00%** of team-games for fta, ftm, pts, oreb and reb.
