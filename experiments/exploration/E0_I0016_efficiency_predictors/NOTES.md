# E0_I0016 — pre-game predictors of player scoring EFFICIENCY

**E0 EXPLORATION. Everything below is a LEAD, never a result. It may not be cited as evidence.**
No bootstrap, no promotion threshold, no registry entry, no preregistration obligation. Nothing was
written to `registry.jsonl`, `DECISION_LEDGER.jsonl`, `GRAPH_EVENTS.jsonl` or `idea_log.jsonl`, and
nothing outside this directory was modified. `E1_I0004_efficiency_transfer/` was neither read nor
written.

---

## 0. The one-line answer

**Yes — three things clear a family-wise correction, and none of them is a defensive matchup.**
The opponent defensive-matchup family, which was the largest and most promising family in the
screen, is **dead: 0 of 36 cells survive**. The three survivors are a role/volume proxy, a
tip-time roster observable, and a term that turns out to be a repackaged main effect. Attrition:
**132 cells → 21 per-candidate → 8 family-wise → 3 candidates, and 2 of those 3 fail their own
follow-up kill tests.**

---

## 1. What was screened

44 preselected candidates (`CANDIDATES_PRESELECTED.md`, sha256
`A39B4C270A2EBB3B527E639CB41138EFA6CCEAED88685C3929B27C787B4DC799`, frozen 2026-08-07T23:46:05-04:00
**before any statistic was computed**) x 3 efficiency outcomes = **132 cells**.

| outcome | definition |
|---|---|
| `y_ppm` | `pts / minutes` — PRIMARY, D081's decomposition axis |
| `y_ts` | `pts / (2*(fga + 0.44*fta))` — true shooting |
| `y_efg` | `(fgm + 0.5*fg3m) / fga` — effective FG% |

Frame: **14,852 player-games, 247 players, 827 games, 2021–2024, Regular Season, appeared
(minutes > 0), >= 3 prior appearances.**

### The statistic — differential skill, not raw error

For each cell, `dR2` = the increment of adding the candidate to the fixed base
`[1, strictly-prior reference]`, plain unweighted OLS with SST about the unweighted mean (**D069**).
The reference is REF-B: the ratio of the player's strictly-prior sums inside `(season, player_id)`,
with a same-season strictly-earlier league-mean cold fallback. **The reference faces the same rows
as the candidate, by construction** — that is the D076 lesson, and this screen measures raw-error
prediction separately (`corr_with_abs_resid`) precisely so the two can never be confused.

The separation is measurable here. Across all 132 cells, `corr(|corr_with_abs_resid|, dR2) = 0.552`
— related, but nowhere near the same thing. Three of the ten cells that best predict the
reference's raw **error magnitude** are family-wise dead:

| cell | corr with abs residual | dR2 | family-wise p |
|---|---|---|---|
| `ts \| F03_minutes_load_7d` | **−0.263** | 0.00411 | **1.000** |
| `ts \| B03_pl_fouls_drawn_per36` | **−0.222** | 0.00247 | **1.000** |
| `ts \| B06_pl_ftpts_per36` | **−0.226** | 0.00179 | **1.000** |

A candidate can rank in the top ten for predicting how wrong the reference will be, and still carry
no differential skill at all, because the reference's error is largest exactly where everything
else is hard too.

---

## 2. TIME-WINDOW TABLE — every constructed column and the window it reads

**Read the construction, not the label.** Every column below was built by sorting inside
`(season, entity)` by `game_date` (ties broken by `game_id`) and applying `.shift(1)` **before**
any `.expanding()` / `.rolling()`. Source: `s01_build_frame.py`, sections 3–7.

### Outcomes — read the CURRENT game only (this is the target)
| column | window |
|---|---|
| `y_ppm`, `y_ts`, `y_efg` | current game box score |

### References — strictly prior
| column | window |
|---|---|
| `refB_{ppm,ts,efg}` | ratio of sums over the player's strictly-prior same-season appearances; cold fallback = expanding mean over games strictly EARLIER in the same season, league-wide |
| `refA_{ppm,ts,efg}` | mean of the player's strictly-prior same-season per-game ratios; same cold fallback |

### Family A — opponent defence (12) — strictly prior
All twelve come from the **opponent team's own strictly-prior same-season team-games** in
`master_team`, where that team's `opp_*` columns record what it ALLOWED. Merged onto the player row
on `(season, opp_team_id, game_id)`, so the opponent's aggregate entering *this* game is used and no
later opponent game is read.
`A01_opp_efg_allowed`, `A02_opp_ts_allowed`, `A03_opp_paintpts_allowed`, `A04_opp_blk`,
`A05_opp_fg3pct_allowed`, `A06_opp_fg3a_share_allowed`, `A07_opp_ftrate_allowed`, `A08_opp_pf`,
`A09_opp_stl`, `A10_opp_defrtg`, `A11_opp_fastbreak_allowed`, `A12_opp_2ndchance_allowed`.

### Family B — foul-draw / free throws (6) — strictly prior
`B01_pl_ftrate`, `B02_pl_ftpct`, `B03_pl_fouls_drawn_per36`, `B06_pl_ftpts_per36` are sums over the
player's strictly-prior same-season appearances. `B04_matchup_ftrate = B01 x A07` and
`B05_matchup_fouldraw = B03 x A08` are products of two strictly-prior terms.

### Family C — teammate context (8) — **THREE OF THESE ARE TIP-TIME, NOT STRICTLY PRIOR**
Availability is rebuilt from `master_player` box membership (appeared = `minutes > 0`), exactly as
D076 did. `data/w1_truth/player_game_availability.csv` and `roster_asof.csv` are artifact-granular
and bound at fit_through_season 2026 — **they were not opened.**

| column | window | flag |
|---|---|---|
| `C01_tm_usage_hhi` | HHI over the team's prior-active roster, each member's usage-per-game as of their last prior appearance | strictly prior |
| `C02_tm_ast_per_game`, `C03_tm_ast_rate` | team's strictly-prior same-season team-games | strictly prior |
| `C04_teammate_usg_present` | prior usage-per-game of the OTHER players **in today's box** | **TIP-TIME** |
| `C05_top_usg_teammate_out` | is the top prior-usage other player absent **from today's box** | **TIP-TIME** |
| `C06_top_usg_teammate_out_lastgame` | the same quantity evaluated on the team's PREVIOUS game | strictly prior |
| `C07_pl_usage_rank` | player's rank by prior usage-per-game among the prior-active roster | strictly prior |
| `C08_vacated_usg` | prior usage of prior-active players **not in today's box** | **TIP-TIME** |

**TIP-TIME means known roughly 30 minutes before tip, not the day before.** The usage values inside
these columns are all strictly prior; what is *not* prior is the set membership. A tip-time lead is
still usable in principle — lineups are public before tip — but it is a different and weaker claim
than a strictly-pregame lead, and it is flagged in `FINDINGS.json` per survivor
(`tip_time_observable: true`).

### Family D — pace / transition (6) — strictly prior
`D01_tm_poss_per40`, `D06_tm_fastbreak_pts` from the team's prior team-games;
`D02_opp_poss_per40` from the opponent's prior team-games; `D03 = D01 + D02`;
`D04_pl_fastbreak_share` from the player's prior appearances; `D05 = D04 x D03`.
Possessions are computed here as `fga - oreb + tov + 0.44*fta` from `master_team`, **not** read from
`master_player.pace / pace_per40 / estimated_pace`, which D081 records as corrupt.

### Family E — shot-mix proxies (7) — strictly prior
`E01_pl_fg3a_share`, `E02_pl_paintpts_share`, `E03_pl_blocked_rate`, `E06_pl_efg_prior`,
`E07_pl_2ndchance_share` from the player's prior appearances; `E04 = E01 x A05`, `E05 = E02 x A04`.

### Family F — rest / load x shooting (4) — strictly prior
`F03_minutes_load_7d` sums the player's minutes over appearances **strictly earlier and within 7
days** (`searchsorted` on the sorted date array, upper bound exclusive of the current row).
The back-to-back flag is `team's previous game date == today − 1 day`, taken from the team frame's
`.shift(1)`. `F01 = b2b x E01`, `F02 = b2b x B01`, `F04 = F03 x E01`.

### Family G — negative control (1)
`G01_noise`: `np.random.default_rng(20260807).standard_normal(n)`. Reads nothing.

### Leakage probes actually run (not just asserted)
`screenkit.future_leakage_probe` was run on **all 44 candidates** against the clean reference, with
the player's own strictly-after-date future `y_ppm` as target. **0 of 44 were flagged.** Results in
`leakage_probes.csv`. A deliberately retrospective positive control (the player's **full-season**
mean `y_ppm`) was built solely to prove the probe fires here, and it did:
corr with the unplayed future **+0.8465** vs the reference's **+0.6741**, dR2 in predicting that
future **0.2731**. The control was then dropped and used nowhere else.

---

## 3. THE DESIGN DEFECT I SHIPPED AND THEN CAUGHT — the most important thing in this file

**My first pass was wrong, and it was wrong in exactly the way this program has been burned five
times.** It is recorded here rather than quietly deleted, because the failure mode is new to the
program's catalogue.

Every candidate here is an expanding prior, so it is neither constant within its entity-season nor
mean-free within it — which means **neither of screenkit's two schemes is valid on it as-is**. My
first pass tried to fix that by splitting each candidate into an entity-season **mean** and the
mean-free remainder, giving each piece a scheme the kit calls valid. It ran clean, it looked
rigorous, and **47 of 264 cells cleared family-wise.**

It is nonsense. **The entity-season mean of a row in game 5 includes games 6 through 40.** Both
components read the future. No survivor on either could have been a pre-game lead.

The tell was the sanity anchor. `E06_pl_efg_prior` is *by construction* the eFG reference, so
against `y_efg` its increment must be zero. Instead, its two components returned an **identical**
dR2 of `0.040729` — the algebraic signature of adding `b` to a base that already contains `b + w`,
which can only produce a nonzero increment if the split itself carries information the base does
not. A candidate that is definitionally the baseline cannot have a real increment. That single
number condemned the whole pass.

The superseded code, results and log are kept: `s02_screen_SUPERSEDED.py`,
`screen_results_SUPERSEDED.csv`, `run_log_s02_SUPERSEDED_decomposition_read_future.txt`.

**Generalisation worth adding to the program's trap catalogue: the retrospective-baseline trap does
not only live in the BASELINE. It can be introduced by the INFERENCE MACHINERY.** Here it entered
through a variance decomposition chosen to satisfy a permutation scheme. Any construction that
centres, standardises, ranks or residualises within a group that spans the whole season is a
future-reading transform, no matter how statistical it looks. The `TIME_WINDOW_TABLE` discipline
should cover columns built by the *analysis*, not only columns built by the *feature pipeline*.

The corrected pass, reported below, uses no derived columns at all.

---

## 4. Nulls, and the honest statement of what each one can and cannot do

Every cell got **three** nulls, 600 draws each, all blocked within `season`.

| null | what it is | what it kills | verdict weight |
|---|---|---|---|
| **N1 within-entity-season** | `screenkit.permutation_null(scheme=SCHEME_WITHIN)` | game-to-game alignment; entity level SURVIVES | counts |
| **N2 entity-label swap** | **written here, not a kit function** — whole entity-season series reassigned to other entity-seasons within the season at proportional positions | entity IDENTITY; marginal distribution and within-season temporal shape survive | counts |
| **N3 naive row-level** | `screenkit.ROW_LEVEL` | everything, incorrectly | **CONTRAST ONLY — never a verdict** |

**Headline `p_correct_level = max(p_N1, p_N2)`** — a candidate is credited only if it beats BOTH,
which is the rule `E0_I0014` used and the kit's own guidance for a candidate in neither regime.

`screenkit.detect_grouping_level` was run on all 132 cells (`grouping_levels.csv`). It returned
`NO_COARSER_LEVEL_EXISTS__ROW_NULL_IS_ANTICONSERVATIVE` for **69 of 132** and
`COARSER_LEVEL_FOUND` for 63, and **no candidate is constant within its declared entity-season, in
any cell**. That is the empirical statement of why the two-null design was necessary.

### N1 is biased CONSERVATIVE here, and the direction matters

For any candidate that is *itself* an expanding prior, permuting it within its entity-season
destroys its collinearity with the reference (which is also an expanding prior over the same
history), which **inflates** the null draws relative to the real statistic. The signature is
`p_N1 ≈ 1.000` sitting next to a clearly positive dR2 — visible on `B03`, `B06`, `F03`, and on
`E06` against `y_ts`. **This costs power; it cannot manufacture a survivor.** Every candidate killed
only by N1 should be treated as *not shown*, not as *shown absent*. N2, which preserves temporal
position by construction, is the better-behaved null of the two and is the one to trust when they
disagree.

### The row-level null would have passed most of the screen

| gate | cells passing (of 132) |
|---|---|
| naive ROW-LEVEL null, p < 0.05 | **65** |
| both correct-level nulls, p < 0.05 | 21 |
| family-wise max-t, p < 0.05 | **8** |

**45 cells pass the row-level null while failing both correct-level nulls.** Median sd inflation
`sd_N1/sd_row = 1.339`, `sd_N2/sd_row = 1.267`, **max 21.06**. Consistent with the 1.6x–3.8x range
this program has measured before, and with the same conclusion: the naive null is not a fallback.

### Multiplicity

Family-wise max-t across **all 132 cells**, standardised per cell from that cell's own draws,
computed separately on the N1 and N2 draw matrices, and **the worse of the two reported**.
Draws in `permutation_draws.npz`; the max-t null in `maxt_null_draws.csv`.

### No-op placebo (mandatory) — observed sd, not rounded

| control | observed sd | verdict |
|---|---|---|
| identity | **1.084202e-19** | CONFIRMED NO-OP (1 distinct draw value) |
| permute the grouping key and recompute | **2.168404e-19** | CONFIRMED NO-OP — a key-relabel control would test nothing here |
| **entity-label swap (N2), 30 draws** | **1.785413e-04** | **NOT a no-op** — the real null does move |

The middle row is the point: the obvious-looking control this screen might have used instead of N2
is the identity in disguise, and the kit catches it.

---

## 5. Results — the kill/keep log

Full 132-row log in `kill_keep_log.csv`; every cell with all nulls in `FINDINGS.json`.

### Per-family attrition

| family | candidates | cells | max dR2 | clear N1 | clear N2 | clear BOTH | **clear FAMILY-WISE** | would clear on row-naive |
|---|---|---|---|---|---|---|---|---|
| **A** opponent defensive matchup | 12 | 36 | 0.00144 | 2 | 19 | 1 | **0** | 23 |
| **B** foul-draw / free throw | 6 | 18 | 0.00298 | 3 | 10 | 3 | **3** | 10 |
| **C** teammate context | 8 | 24 | 0.00659 | 6 | 10 | 6 | **4** | 10 |
| **D** pace / transition | 6 | 18 | 0.00106 | 2 | 2 | 1 | **0** | 2 |
| **E** shot-mix proxy | 7 | 21 | 0.00717 | 10 | 14 | 10 | **1** | 14 |
| **F** rest & load x shooting | 4 | 12 | 0.00411 | 0 | 6 | 0 | **0** | 6 |
| **G** negative control | 1 | 3 | 0.00008 | 0 | 0 | 0 | **0** | 0 |

**Controls behaved.** `G01_noise` is dead on all three outcomes (dR2 ≈ 6e-5, p_N1 0.30–0.34,
p_N2 0.30–0.33). `E06_pl_efg_prior` against `y_efg`, where it **is** the reference by construction,
returns **dR2 = 0.000000 exactly** — the machinery is not manufacturing signal.

### The 8 family-wise survivors, and what happened when I tried to kill them

| # | cell | dR2 | corr-level p | family-wise p | decile spread on ref-residual | survives its kill test? |
|---|---|---|---|---|---|---|
| 1 | `ppm \| E06_pl_efg_prior` | 0.00717 | 0.0017 | 0.0017 | −0.0795 ppm ≈ **−1.72 pts/game** | **YES** |
| 2 | `ppm \| C07_pl_usage_rank` | 0.00659 | 0.0017 | 0.0017 | −0.0425 ppm ≈ **−0.92 pts/game** | **partly** — dR2 falls 7.3x under reliability controls |
| 3 | `ts \| C07_pl_usage_rank` | 0.00447 | 0.0017 | 0.0017 | −0.0506 ts | **NO** — dR2 → 0.000001, p 0.92/0.94 |
| 4 | `ppm \| C04_teammate_usg_present` | 0.00330 | 0.0017 | 0.0017 | −0.0406 ppm ≈ **−0.88 pts/game** | **YES** (but TIP-TIME) |
| 5 | `efg \| C07_pl_usage_rank` | 0.00314 | 0.0017 | 0.0017 | −0.0345 efg | **NO** — dR2 → 0.000061, p 0.46/0.46 |
| 6 | `ts \| B05_matchup_fouldraw` | 0.00298 | 0.0017 | 0.0017 | +0.0578 ts | **NO** — dR2 → **0.000000** with own main effects |
| 7 | `ppm \| B05_matchup_fouldraw` | 0.00145 | 0.0017 | 0.0017 | +0.0324 ppm ≈ +0.70 pts/game | **NO** — dR2 → 0.000025, p 0.50/0.50 |
| 8 | `efg \| B05_matchup_fouldraw` | 0.00122 | 0.0017 | 0.0033 | +0.0444 efg | **NO** — dR2 → 0.000001, p 0.90/0.90 |

Every survivor also cleared `screenkit.paired_forecast_comparison` at the entity-season cluster
level (p = 0.0005 on 2,000 cluster sign-flips, every one), and every survivor's dR2 reproduces
within a factor of ~2 when the reference is swapped from REF-B to REF-A. Sign is **identical in all
four seasons** for all eight cells. So the survivors are not artefacts of one reference, one null,
or one season — they are what they are, and what they are is mostly small and mostly explained.

### What each surviving lead actually is

**LEAD 1 — `E06_pl_efg_prior` against `y_ppm` (dR2 0.00717, negative sign).** This is not a new
observable; it is the player's own prior eFG, and it says the **points-per-minute reference is
incomplete**. Conditional on prior points-per-minute, a player with higher prior *shooting
efficiency* scores at a *lower* rate per minute — the volume/efficiency trade-off, which a
single-rate reference cannot see. Holds under reliability controls (0.0049), in the decision
stratum (0.0028, n=5,673), and in all four seasons. **Practical size: −1.72 points per game across
the outer deciles.** This is the largest effect in the screen and it is a *reference-construction*
lead, not a mechanism lead.

**LEAD 2 — `C07_pl_usage_rank`.** Survives on all three outcomes raw, but is **largely a
reliability/role proxy**: adding `n_prior` and trailing-5 prior minutes to the base collapses it
from 0.00447 → **0.000001** on `ts` and 0.00314 → **0.000061** on `efg`, both dead (p ≈ 0.46–0.94),
and both die in the decision stratum too. Only the `ppm` cell partly survives, shrinking 7.3x to
0.00090. It also fails N1 at the alternate `player_season` entity (p = 1.000). Read: usage rank
mostly encodes *how noisy this player's own reference is*, which is a shrinkage signal, not a
mechanism.

**LEAD 3 — `C04_teammate_usg_present` against `y_ppm` (dR2 0.00330, negative sign) — the only
survivor that gets stronger under pressure.** It holds under reliability controls (0.00164), holds
at the alternate entity (p_N1 0.010, p_N2 0.0017), is stable across seasons, and **is larger in the
decision stratum than overall (0.00496 vs 0.00330, n = 5,673)** — the opposite of the usual
decay. **Practical size: −0.88 points per game across the outer deciles.** Two caveats, both
load-bearing: it is **TIP-TIME**, not strictly prior; and it is **dead on `ts` (fw p 0.885) and
`efg` (fw p 1.000)**, which are the pure conversion measures. That pattern says the channel is
**shots per minute, not points per shot** — when high-usage teammates are on the floor, a player
takes fewer shots per minute, not worse ones. It is a real points-per-minute lead and it is *not*
an efficiency-of-conversion lead.

### The kills that matter most

**The opponent defensive-matchup family is dead: 0 of 36 cells clear family-wise, best dR2 0.00144
(`A10_opp_defrtg`).** Every A candidate that clears N2 (the between-opponent null, 19 of 36) fails
N1 badly — typically p_N1 0.83–0.998 — which is the signature of a variable whose apparent effect
is a level difference between opponents that carries no within-season information. Twelve
constructions were tried: eFG allowed, TS allowed, paint points allowed, blocks, 3P% allowed, 3PA
share allowed, FT-rate allowed, fouls committed, steals, defensive rating, fast-break allowed,
second-chance allowed. **Box-score-derived opponent defensive quality does not predict an
individual player's scoring efficiency beyond that player's own prior rate.**

**The foul-draw matchup interaction is not an interaction.** `B05_matchup_fouldraw` = player prior
fouls-drawn-per-36 x opponent prior fouls-committed. It survives family-wise on all three outcomes —
and then goes to **exactly zero** (0.000000 / 0.000025 / 0.000001, p 0.50–0.95) once its own two
main effects are in the base. It was never a matchup; it was `B03_pl_fouls_drawn_per36` wearing an
opponent term as a hat, and `B03` itself fails N1 at p = 0.998. This is precisely why an
interaction must be screened against its own main effects, and it is the single cleanest kill in
this screen.

**The rest/load family is the dead family wearing a hat, and I said I would check.** All 12 F cells
fail (0 clear even one correct-level null on the max rule; 6 clear only the naive row null).
`F03_minutes_load_7d` is a genuinely different construction from the dead rest-days flag and it
does have a real between-player association (p_N2 0.0017 on all three outcomes) — but that is
between-player level, killed by N1 at p 0.58–0.86, i.e. it is "some players play more minutes and
are better", not "accumulated load degrades shooting". **Honest answer: yes, this family is the
dead one in new clothes.**

**Pace does not interact with efficiency.** 0 of 18 D cells survive; `D05_transition_x_pace`,
the specific fast-game/transition-shot mechanism, is nowhere near.

---

## 6. Kit feedback

`_screen_kit` was used for manifests, partition, grouping-level detection, both permutation
schemes, `var_share_between`, `paired_forecast_comparison`, `noop_placebo`, `future_leakage_probe`,
`delta_r2_plain` and `r2_of_forecast`. It caught real things and its P1–P4 fixes did their job.
**Four items to report**, in descending importance. K0 has a minimal reproduction in
`KIT_BUG_REPRO.py` (`python KIT_BUG_REPRO.py`, exit 0 = defect reproduced), written rather than
worked around silently, following the precedent E0_I0015 set.

### K0 — `assert_partition` false-positives on any column named `candidate` — TRAP 3 INSIDE THE ANTI-TRAP-3 FUNCTION

`assert_partition` auto-detects date columns **by name**:

```python
cand_date = [c for c in df.columns if "date" in str(c).lower()]
```

The word **"candi-DATE" contains "date"**. So do `upDATE_flag` and `valiDATEd`. Every column this
program names `candidate`, `n_candidates`, `mae_with_candidate`, `candidate_id`, … is treated as a
date column. It is then parsed with `pd.to_datetime(col, errors="coerce")`, which **on a float
column does not raise** — it reads the floats as nanoseconds since the epoch, returns **1970**, and
1970 is outside every real partition. Result:

> `PartitionViolation: date column 'mae_with_candidate' has out-of-partition YEAR VALUES [1970]; date column 'n_candidates' has out-of-partition YEAR VALUES [1970]`

on a frame **whose every real value is inside 2021–2024**. This screen hit it on
`screen_results.csv`, `family_attrition.csv` and `FINDINGS.json::all_cells`.

**The defect is an asymmetry, and the asymmetry is the tell.** The SEASON branch already has a
value-plausibility guard, `_is_season_valued`, added precisely because columns *named*
`_team_season_2025` held dR2 draws near `1e-4` — and it has a regression test in `TESTS.py`.
**The DATE branch has no equivalent guard.** The same hardening was applied to one branch and not
the other, and because `pd.to_datetime` on floats never raises, nothing surfaces it.
`KIT_BUG_REPRO.py` REPRO 3 demonstrates both branches side by side on one frame: the season-named
column holding dR2 draws is correctly **skipped**; the date-named column holding MAE numbers is
wrongly **checked and flagged**.

**Why this is not cosmetic even though the direction is conservative.** A false alarm cannot let a
2025/2026 row through. But the workaround a hurried caller reaches for is
`assert_partition(df, date_cols=[])` — **which disables the date check entirely**. REPRO 4 shows a
frame containing a real `2026-06-01` game date: caught by default, and **passed clean** under that
workaround. A guard that cries wolf on the program's single most common column name trains callers
to switch it off, and "candidate" is not an unlucky word here — it is the vocabulary of every
exploration screen in the program. **This will recur.**

**Suggested fix, mirroring what the season branch already does:** require a name-matched date
column to be date-VALUED before checking it — accept `datetime64` dtype outright; for object/string
columns require a high parse-success rate; and for **numeric** columns refuse to interpret values as
epoch nanoseconds at all, recording them under `skipped_name_only` with the same wording the season
branch uses ("name is date-like but VALUES are not dates"). A caller who genuinely stores epoch
integers can still pass `date_cols=[...]`, which is the escape hatch the season branch already
offers. A regression test in the shape of `TESTS.py`'s existing trap-3 test — a clean 2021–2024
frame with a column named `mae_with_candidate` holding MAE floats must **pass** — would have caught
it.

**What this screen did instead of the false-pass workaround** (`s05_verify.py`): named the real date
columns explicitly (`game_date`, plus any `datetime64` column) **and** added a compensating
value-based sweep that parses every non-numeric column regardless of name and checks any that
genuinely reads as dates. `assert_partition`'s unconditional numeric year-value sweep — the guard
that catches a year-valued column with an innocuous name — is unaffected and remained active on
every artifact. All 10 written artifacts verify clean.

### K1 — `future_leakage_probe`'s verdict string asserts something that is FALSE, and it fired here

Run on `refB_ppm` (suspect) vs `refA_ppm` (clean), the probe returned:

> `'refB_ppm'` predicts the entity's UNPLAYED FUTURE better than `'refA_ppm'` (|0.6741| vs |0.6571|)
> and adds dR2=0.0235 on top of it in predicting that future. **That is only possible because it
> CONTAINS the future.**

**That last sentence is not true, and it is not true here.** Both columns are strictly prior by
construction — the same `.shift(1)`-before-`.expanding()` window over the same history — and they
differ only as *estimators*: REF-B is a ratio of prior sums, REF-A a mean of prior ratios. A
lower-variance estimator of a persistent quantity will out-predict a noisier one on the future
without containing any of it. The probe is doing its job (it is a positive detector, and its own
docstring says it is not a certificate); the **verdict text over-claims**, and it over-claims in
the direction that causes a false alarm on a clean column. Suggested fix: state the *alternative*
explanation in the verdict — "either it contains the future, **or it is a lower-variance estimator
of a persistent quantity**; read the construction to distinguish them". The probe's positive
control fired correctly in the same run (full-season mean: corr +0.8465, dR2 0.2731), so the
machinery is right; only the wording is wrong. **Not a numerical defect. A wording defect that
would have made a careless caller discard a clean baseline** — which is the mirror image of the
error the probe exists to prevent, and therefore worth fixing.

### K2 — MISSING MACHINERY: no valid null exists in the kit for the between-entity question on a within-varying feature

This is a real gap, not a misuse. P4 added `SCHEME_WITHIN` alongside `SCHEME_BETWEEN`, but:

* `SCHEME_BETWEEN` **requires** constancy within groups, and forcing it with
  `allow_nonconstant=True` is what the kit itself documents as a p "manufactured rather than
  measured", because the draws lose 100% of the within-group variation the real statistic keeps;
* `SCHEME_WITHIN` is refused when the feature *is* constant within groups.

**Any expanding prior — which is what essentially every pre-game feature in this program is — falls
between the two.** `detect_grouping_level` confirms it empirically here: **no candidate is constant
within its declared entity-season in any of the 132 cells.** So the question "does *which
opponent* you face matter" — the entire point of a defensive-matchup family — has no valid scheme
in the kit today.

I implemented one (`ep_base.EntitySwap` / `entity_swap_null`) and declared it. It reassigns whole
entity-season series to other entity-seasons inside the same season at **proportional positions**,
so series length and within-season temporal shape survive while identity dies. The proportional
alignment matters and is the non-obvious part: an early-season expanding prior is mechanically
noisier than a late-season one, and a null that scrambled that would not be comparing like with
like — which is exactly the bias that makes N1 conservative (section 4).

Suggested kit addition: `permutation_null(..., scheme="entity_swap", entity_cols=..., order_col=...)`,
with the same refusal discipline as the existing schemes. Two caveats belong in its docstring and
are in mine: it does not preserve the exact marginal distribution when partners differ in length,
and it is a randomisation of labels, not a bootstrap.

### K3 — small, and a compliment

`noop_placebo` earned its keep twice: the identity control returned sd `1.084202e-19` with one
distinct draw value, and the "permute the grouping key and recompute" control returned
`2.168404e-19` — **confirming that the obvious-looking control this screen might have used instead
of an entity swap is the identity in disguise.** Reporting the observed sd rather than asserting
zero is the right call; both numbers are nonzero and both are reported unrounded.
`detect_grouping_level`'s P2 fix also did its job: it returned `None` and the
`NO_COARSER_LEVEL_EXISTS` status on 69 cells rather than nudging me toward the row null.

---

## 7. Where I could have cheated — disclosure

1. **Preselection.** The candidate list was written and hashed **before any statistic existed**
   (`CANDIDATES_PRESELECTED.md`, sha256 `A39B4C27...`, timestamp in `run_log.txt` line 1).
   **44 candidates were preselected; 44 were screened; 0 were added after seeing results; 0 were
   dropped.** The three outcomes and the two reference constructions were also fixed in that file.
2. **The obvious cheat I did not take: reporting the first pass.** It gave **47 family-wise
   survivors** instead of 8, across every family including the opponent-defence family. Deleting
   the tell (the E06 anchor) and shipping it would have produced a far more exciting return. The
   superseded artifacts are kept in-directory so the claim is checkable.
3. **The second obvious cheat: reporting N2 alone.** N2 passes **61** cells per-candidate and 23
   family-wise, versus 8 under `max(p_N1, p_N2)`. Since I argue in section 4 that N1 is biased
   conservative, I could have justified dropping it. I did not; the strict rule is the headline and
   the N1-only and N2-only counts are both published in `FINDINGS.json`.
4. **The third: reporting the row-level null.** It passes **65 of 132**. It is reported as contrast
   only, in every table, with its inflation factor.
5. **Choice of entity level.** Assigning each candidate to an entity is a judgement call that moves
   the p-values. It was fixed by family in the preselection file, and every survivor was re-run at
   a second entity level; `ts`/`efg` `C07` and `ppm` `B05` all fail N1 at the alternate entity, and
   that is reported rather than buried.
6. **The screening regression is IN-SAMPLE**, so every dR2 is optimistically biased by roughly
   `1/n` per parameter. That is exactly why the comparator is a permutation null and never zero,
   and why `skill_vs_reference` (which uses the in-sample fit) is labelled in-sample everywhere it
   appears. No out-of-sample claim is made anywhere in this screen. **No model was fitted beyond
   the two-column screening regression; the champion was never loaded and never retrained.**
7. **Partition hygiene.** `observed_time` and `source` in `master_player`/`master_team` contain 2026
   strings — they are local file mtimes and filenames, and the artifacts' own manifests say
   explicitly they are not an as-of bound. **They were deliberately left in the frame that
   `assert_partition` inspected** rather than dropped, because dropping columns to make a check
   pass is itself a cheat; the check is value-based and correctly ignores them. Season and date
   columns were filtered to 2021–2024 and re-asserted after every filter. No 2025/2026 row was
   loaded, joined, plotted, described or summarised at any point.
8. **`E06_pl_efg_prior` is not a discovery.** It is definitionally the eFG reference, was declared
   as a sanity anchor in the preselection file, and returns exactly 0.000000 there. Its `ppm`
   result is reported as a reference-construction lead and labelled as such, not as a new
   observable.

---

## 8. Limitations that a follow-up should fix

* **No shot-chart data.** `data/shotcharts/*.parquet` carries **no sibling manifest** →
  UNVERIFIABLE → not used. So assisted-shot share, average shot distance and early-clock share —
  three of the shot-quality proxies the brief specifically suggested — were **not screened at all**.
  Family E is box-score shadows only. Getting manifests onto the shotchart files would open the
  single largest unscreened surface for this question.
* **`E0_I0014/analysis_frame.parquet` has no manifest either**, so this screen rebuilt its frame
  from `master_player`/`master_team` (both row-granular) rather than reusing D076's. Consequence:
  the numbers here are not directly comparable to D076/D081 skill percentages, which are measured
  against the champion's walk-forward predictions. This screen never touches the champion.
* **In-sample only.** No walk-forward, no held-out season. A lead here is an association, not a
  forecast.
* **N1's conservative bias** (section 4) means candidates killed only by N1 are *not shown*, not
  *shown absent*. `F03_minutes_load_7d`, `B03`, `B06` are in that class.
* **2021 is included here** (D076/D081 excluded it because the champion's 2021 fold is degenerate).
  Since no model is scored here, 2021 is usable; per-season tables are reported for every survivor
  and no survivor depends on it.

---

## 9. Files

| file | what it is |
|---|---|
| `CANDIDATES_PRESELECTED.md` | the frozen candidate list, hashed before any result |
| `ep_base.py` | loader, strictly-prior helpers, `BaseFit` fast dR2, `EntitySwap` (declared kit gap) |
| `s01_build_frame.py` → `screen_frame.parquet`, `leakage_probes.csv`, `_s01.json` | frame build, manifest checks, partition asserts, 44 leakage probes, fast-dR2 verification against the kit |
| `s02_screen.py` → `screen_results.csv`, `maxt_null_draws.csv`, `permutation_draws.npz`, `_s02.json` | the 132-cell screen, three nulls each, family-wise max-t |
| `s03_survivors.py` → `FINDINGS.json`, `survivor_forensics.json` | survivor kill tests, attrition, D076 trap contrast |
| `s04_summary.py` → `family_attrition.csv`, `kill_keep_log.csv`, `grouping_levels.csv` | per-family attrition and the 132-row kill/keep log |
| `s05_verify.py` | final value-based partition sweep over every written artifact, frame integrity, E0 hygiene |
| `s06_finalise_findings.py` | adds the narrative sections to `FINDINGS.json` (headline, leads, principal kills, design defect, kit feedback, limitations, hygiene) — a separate step because both the superseded pass and kit defect K0 were found *after* the screen ran |
| `KIT_BUG_REPRO.py` → `run_log_kit_bug.txt` | **minimal reproduction of kit defect K0** (`assert_partition` vs `candidate`) |
| `run_log.txt`, `run_log_s0*.txt` | captured output of every step |
| `s02_screen_SUPERSEDED.py`, `screen_results_SUPERSEDED.csv`, `run_log_s02_SUPERSEDED_*.txt` | **the wrong first pass, kept deliberately** (section 3) |
