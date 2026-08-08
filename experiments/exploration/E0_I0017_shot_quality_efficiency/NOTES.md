# E0_I0017 — SHOT QUALITY vs SCORING EFFICIENCY

**E0 exploration screen. LEAD, NEVER A RESULT.** Fast, permissive, time-boxed, explicitly
non-claiming. No bootstrap, no promotion threshold, no registry entry, no ledger entry. Nothing in
this directory may be cited as evidence.

**Candidate list SHA-256 `15314c2163cb9b65c761d8bc859505578d5f474a4044a8442f0cc5cf42c5851f`**
— hashed before any statistic was computed. 39 preselected, 39 screened, 0 added, 0 dropped.

---

# 1. STEP 0 — THE PROVENANCE GATE. VERDICT: **ROW**.

## 1.1 The question, and why inheriting the prior answer was not acceptable

`data/shotcharts/*.parquet` has no sibling `.manifest.json`, so `screenkit.check_manifest` returns
**`UNVERIFIABLE`, which is never a pass** (D080). Two prior screens used the files anyway on
structural grounds. `E1_I0004_shot_selection/NOTES.md:117` states it as:

> "`data/shotcharts/*` has no manifests and needs none: the season is the filename."

That is an argument about the **file name**. Under the program-wide invariant adopted at D086 — *a
substring match on a column name may only ever NOMINATE a column for a value test; it may never, by
itself, cause a violation* — the mirror of that invariant must also hold: **a filename may nominate
a file as clean, but it may never, by itself, certify one.** So the argument was re-tested on
values.

## 1.2 What was tested, and what the values say

`s00_provenance.py`, all eight partition files (132,558 shot events, 2021-05-14 to 2024-10-20).
Nine checks, every one on **column values**:

| # | check | result |
|---|---|---|
| A | every row's `GAME_DATE` year equals its own filename's season | **0 violations** |
| B | no row dated outside 2021–2024 | **0 violations** |
| C | `(GAME_ID, GAME_EVENT_ID)` uniquely identifies a row | **0 duplicates** |
| D | one `GAME_DATE` per `GAME_ID` — an event cannot span dates | **0 games with >1 date** |
| E | per-column within-entity constancy — **the pooling test** | see below |
| F | nominate-by-name, decide-by-value | 1 nominated, **0 convicted** |
| G | `SHOT_DISTANCE` reproducible from `LOC_X`/`LOC_Y` within 1 ft | **1.000000 of rows** |
| H | flags are per-event binary, and agree with `EVENT_TYPE` | **1.000000 agreement** |
| I | cumulative signature (non-decreasing **and** non-constant) | **0 suspects** |

**Check E is the central one.** A precomputed aggregate is constant within whatever entity it was
aggregated over. Measured fraction of player-seasons on which each column is constant:

```
column                 dtype    ndistinct  const/plyr-ssn  const/team-ssn  const/game
GRID_TYPE              str              1          1.0000          1.0000      1.0000
PLAYER_ID              int64          262          1.0000          0.0000      0.0000
TEAM_ID                int64           12          0.9542          1.0000      0.0000
SHOT_ATTEMPTED_FLAG    int64            1          1.0000          1.0000      1.0000
SHOT_DISTANCE          int64           77          0.0288          0.0000      0.0000
SHOT_ZONE_BASIC        str              7          0.0383          0.0000      0.0000
ACTION_TYPE            str             42          0.0298          0.0000      0.0000
SHOT_MADE_FLAG         int64            2          0.0543          0.0000      0.0000
LOC_X / LOC_Y          int64      499 / 593        0.0256          0.0000      0.0000
```

The only columns constant within a player-season are **identity columns** (`PLAYER_ID`,
`PLAYER_NAME`), the **single-valued constants** (`GRID_TYPE`, `SHOT_ATTEMPTED_FLAG` — one distinct
value across all 132,558 rows), and `TEAM_ID`/`TEAM_NAME` at 0.9542, whose 4.6% of exceptions are
in-season trades. **Not one column behaves like a rate, a rank, a shrunk value or a season total.**

Check F nominated exactly one column by name — `PERIOD`, because it contains the substring `per` —
and the value test cleared it: integer-valued, `n_distinct = 6`, constant within only 6.18% of
player-seasons. A nomination is not a conviction.

Check G is the strongest positive evidence: `SHOT_DISTANCE` is reproduced from that same row's
`LOC_X`/`LOC_Y` on **every single row**. It is a **within-row derivation**, so it cannot encode
anything about any other row, in any season.

## 1.3 The conclusion, stated precisely

**VERDICT: ROW.** Every column is a raw per-event property bounded by that event's own game and
game date. There is no aggregation step anywhere in the file that could pool across time, and
therefore no route by which a 2021 shot row could have seen the 2025/2026 confirmation holdout.
`screenkit.assert_partition` passes on values.

**Three things this verdict does NOT say, stated so nobody over-reads it:**

1. **The manifest status is unchanged: `UNVERIFIABLE`.** This screen does not claim the files are
   manifested and does not treat UNVERIFIABLE as a pass. The ROW verdict is an *independent,
   value-based inference about the file's content*. **The manifest backlog remains a real gap** and
   `data/shotcharts/*` and `data/playbyplay/*` still deserve manifests.
2. **Collection provenance is not established.** Nothing here proves *when* the files were scraped.
   It does not need to: because every value is a fact about a single event, a later scrape cannot
   retroactively inject future information into a 2021 shot's coordinates. That is the actual
   argument, and it rests on values, not on the filename.
3. **`data/shotcharts/league_avg_*.parquet` were NEVER OPENED.** They are league-average aggregates.
   The league rates this screen needs were rebuilt strictly-prior from the raw event rows instead.

Play-by-play (`data/playbyplay/pbp_*.parquet`, one file per game) was subjected to the same
reasoning and used only for the per-event assist flag, joined on event identity
`(GAME_ID, GAME_EVENT_ID) == (GAME_ID, EVENTNUM)`. Files `pbp_10225*` (2025) were never opened.

---

# 2. HEADLINE

## 2.1 On the decision-relevant outcome, nothing survives

D081 localised the champion's points failure at the **per-minute efficiency step**. On `y_ppm`:

| test | result |
|---|---|
| family-wise clears, base `[1, refB_ppm]` | **1 of 39** |
| that one cell, after forensics | **killed — see §2.2** |
| family-wise clears, base `[1, refB_ppm, refB_ts, refB_efg]` | **0 of 39** |
| best remaining ppm cell | `B01_dist_t5`, dR2 = 0.00079, per-candidate p = 0.0067, **family-wise p = 0.223** |
| D081 decision stratum (>=8 prior apps, >=24 trailing-5 min; 5,683 rows, 40.6%) | **0 of 20 clear even PER-CANDIDATE**, min p = **0.150** |

## 2.2 The one apparent survivor, and the new trap that produced it

`D04_xefg_minus_own` was the only ppm cell to clear family-wise in the first pass, and it did so
emphatically: **dR2 = 0.009597, correct-level p = 0.001664, family-wise p = 0.001664** — a ~1% R2
increment on precisely the quantity D081 named. It is an artifact.

`D04` is *defined* as `D01_xefg_zone − refB_efg`. Against a base of `[1, refB_ppm]` it therefore
injects the player's own prior **eFG** into a model that contained only their own prior **ppm**:

| added to base `[1, refB_ppm]` | dR2 |
|---|---|
| `D04_xefg_minus_own` | 0.009597 |
| `D01_xefg_zone` alone — *the actual shot-quality term* | 0.000591 |
| **`refB_efg` alone — not a shot-quality feature at all** | **0.010168** |

| added to base `[1, refB_ppm, refB_efg]` | dR2 |
|---|---|
| `D04_xefg_minus_own` | **0.000090** |
| `D01_xefg_zone` | **0.000090** |

`refB_efg` on its own out-performs the entire candidate, and controlling for it collapses D04 by
**107x**.

### This is a trap shape the program has not recorded before: **REFERENCE INCOMPLETENESS**

It is **not** the retrospective-baseline trap. Nothing here reads the future — every reference and
every candidate is strictly prior, the leakage probes are clean, and the first-appearance NaN
assertion passes. The reference was **correctly constructed and simply incomplete**: it measured
the player's own prior efficiency *one* way while the candidate smuggled in a *second* way. The
"skill" was the gap between two strictly-prior references, not skill over either.

**Generalisation worth carrying forward:** any candidate defined as a *difference against a
reference-like quantity* can manufacture skill this way, and neither a permutation null nor a
leakage probe will catch it — both were passed with the maximum possible confidence. The only thing
that caught it was decomposing the candidate and asking what its pieces did separately. The remedy
adopted here is to re-screen every cell against the **full own-prior base**
`[1, refB_ppm, refB_ts, refB_efg]`.

## 2.3 There IS a real effect on eFG/TS — and it does not reach points

Prior shot mix predicts effective FG% and true shooting strongly and stably: **37 of 78 eFG/TS
cells clear family-wise** under the full own-prior base, **55 of 60 candidate-outcome pairs are
sign-consistent across all four seasons**, and the effect survives the decision stratum. Signs are
basketball-sensible throughout: closer shots and more restricted-area/layup share → higher eFG;
greater mean shot distance → lower eFG.

But **eFG and TS are by definition mix-weighted conversion rates**, so a prior shot-mix feature
predicting them is substantially arithmetic rather than a discovery. And the effect is cancelled
before it reaches points. `s04_transfer.py` tested the volume-offset hypothesis
(`ppm ≈ points-per-shot × shots-per-minute`) on 12 mix candidates:

**12 of 12 candidates have opposing signs on eFG and on shots-per-minute.**

| candidate | Δ eFG (p10→p90) | Δ FGA/min | Δ pts/min |
|---|---|---|---|
| `A02_share_lt5ft` | **+0.0340** (p=0.0017) | **−0.0167** (p=0.0017) | +0.0140 |
| `A03_share_restricted` | +0.0326 | −0.0162 | +0.0143 |
| `D01_xefg_zone` | +0.0336 | −0.0192 | +0.0069 |
| `A01_dist_mean` | −0.0277 | +0.0115 | −0.0181 |

A player who takes closer shots converts better *and takes fewer shots per minute*. Mean
`|Δ pts/min|` across the full p10→p90 range is **0.0137 points per minute = 0.41 points per game at
30 minutes** — and that is the *per-candidate* figure, before the multiplicity correction that
kills it. Compare D081: a **perfect** rate forecast cuts points MAE 58.5%. This is not that.

## 2.4 The two families nobody could reach before are both dead

| family | cells | family-wise clears | min family-wise p |
|---|---|---|---|
| **C — assisted share** (the feature D085 most wanted) | 15 | **0** | **0.534** |
| **E — opponent shot-quality CONCEDED** (the new matchup story) | 18 | **0** | **0.973** |

Family C: only 2 of 15 cells clear even per-candidate, and neither survives multiplicity. Family E
is the more consequential kill. D084 killed opponent zone **conversion** allowance on an arithmetic
ceiling; D085 killed twelve **outcome-based** defensive constructions (0 of 36 cells); this screen
kills the **shape of shots a defence concedes**. **The opponent-defence surface is now closed from
three independent directions.**

## 2.5 The interaction family repeated D085's pattern exactly

All four player×opponent interactions cleared against `[1, ref]` on ts/efg at p = 0.0017. With
**their own two main effects in the base**, **10 of 12 cells** collapse to p > 0.13, with dR2
falling by factors of **1.9x to 25,715x** — the extreme being `F04_3pa_x_opp3pa` on efg,
5.217e-04 → **2.029e-08**, p 0.027 → 0.980. This is the same shape as D085's foul-draw matchup
interaction, which cleared family-wise and then went to exactly zero once its own main effects were
controlled. **Screening an interaction without its main effects is not a weak test, it is the wrong
test**, and it has now produced a false positive twice in consecutive screens.

**The two exceptions are reported rather than dropped, because they move the other way.**
`F01_dist_x_oppdist` on ppm (p 0.201 → **0.017**) and `F02_lt5ft_x_opplt5ft` on ppm (p 0.912 →
**0.033**) become *more* significant once their main effects are controlled — the main effects were
masking them. Neither is a survivor: both are per-candidate p-values on the single-reference base,
and on ppm under the full own-prior base with family-wise correction the count is **0 of 39**. They
are noted because a screen that reports only the collapses and hides the two that grew would be
selecting its own evidence.

---

# 3. TIME-WINDOW TABLE — features **and inference steps**

D085's agent introduced a retrospective baseline through its **inference machinery**, not its
features: it decomposed candidates into an entity-season mean plus remainder purely to satisfy the
kit's permutation schemes, and that mean read the whole season. This table therefore covers every
transformation introduced for statistical convenience, not only the features.

## 3.1 Features

| column | window read | mechanism |
|---|---|---|
| `A01`–`A12` (own shot profile) | player's games **strictly before** this game_date, same season | `.shift(1).expanding().sum()` inside `(season, player_id)` sorted by date; ratio of prior sums |
| `B01`–`B03` (trailing-5) | player's **5 most recent strictly prior** games, same season | `.shift(1).rolling(5, min_periods=1).sum()` |
| `B04`–`B06` (trends) | as above; a difference of two strictly-prior quantities | trailing-5 minus expanding prior |
| `C01`–`C05` (assisted share) | player's strictly prior games (regular season only — pbp has no playoff files) | as `A`, over pbp-joined per-event assist flags |
| `D01`–`D03` (shot-quality index) | **two** strictly-prior windows, see §3.2 | player prior mix × league prior zone rate |
| `D04` | `D01` minus `refB_efg`, both strictly prior | **the reference-incompleteness vector — see §2.2** |
| `E01`–`E06` (opponent conceded) | opponent's games **strictly before** this game_date, same season | `.shift(1).expanding()` inside `(season, opp_team_id)` |
| `F01`–`F04` | product of two strictly-prior columns | no new window |
| `G01_noise` | none — seeded `standard_normal` | negative control |
| `G02_ref_echo` | identical to `refB_<outcome>` | vacuous positive control |

## 3.2 The league rate inside family D — the step most likely to have leaked

`D01`/`D02`/`D03` price a player's prior shot mix at **league** conversion rates. A naive
implementation uses a whole-season or whole-file league rate, which reads the future. Here the
league rates are themselves strictly prior: shot events are aggregated to `(season, game_date,
zone)`, then cumulated with `.shift(1).expanding().sum()` **at the date level within season**, so a
row dated *d* prices its mix at rates computed from games on dates **strictly earlier than *d***. A
zone not yet attempted in the season falls back to the season-to-date overall league rate, itself
strictly prior. Verified: on each season's first date the entire league-rate table is all-NaN.

## 3.3 Inference steps

| inference step | window read | note |
|---|---|---|
| reference `refB_<rt>` | player's strictly prior games; league prior on cold start | ratio of prior sums; identical construction to D085 |
| reference `refA_<rt>` | player's strictly prior games | kept only as the leakage probe's clean comparator |
| `BaseFit` screening regression | in-sample, current rows only | fits `y ~ 1 + base + candidate`; the increment is compared to a permutation null, **never to zero** |
| `EntitySwap` permutation | relabels **entity identity**; preserves each series' length and within-season temporal shape | reads no data beyond the frame; index arrays precomputed from `arange(n)`, an exact optimisation |
| full own-prior base (§2.2) | three strictly-prior references | **adds no new window** — all three already existed |
| decision-stratum filter | `n_prior >= 8`; trailing-5 mean minutes, `.shift(1).rolling(5)` | the minutes filter is strictly prior; it is a *pre-game observable*, so the stratum is decidable before tip |
| **entity-season mean/remainder decomposition** | — | **NOT USED. DELIBERATELY DECLINED.** This is what read the future in D085. `screenkit.entity_swap_null` needs no such decomposition. |

**No tip-time exceptions.** D085 carried three (C04, C05, C08 read today's box membership). This
screen has zero: every candidate is a function of games strictly before the row's own game_date.

## 3.4 Proof by construction

`s01` **halts** unless every player-entity candidate is NaN on a player's first appearance of a
season and every opponent-entity candidate is NaN on the opponent's first game of a season. All 38
non-noise candidates pass at exactly 0 finite values. A candidate that read its own game could not
satisfy this.

---

# 4. STATISTICAL HYGIENE

- **R2 convention (D069):** plain unweighted OLS, SST about the **unweighted** mean. Declared.
  `BaseFit.dr2` verified against `screenkit.delta_r2_plain` on real data before any result was
  produced: **absolute difference 1.15e-16**.
- **Skill, not error (D076):** every dR2 is an increment over a strictly-prior reference facing the
  **same rows**. No raw MAE reduction appears anywhere in this screen.
- **Null level:** `detect_grouping_level` reports `NO_COARSER_LEVEL_EXISTS__ROW_NULL_IS_ANTICONSERVATIVE`
  for **39 of 39** candidates — every candidate is an expanding prior, so it varies within its
  entity-season while the question is between entities. Primary null is therefore
  `entity_swap_null` (`SCHEME_ENTITY_SWAP`), 600 draws.
- **Row-level null reported for contrast only.** Inflation `sd_correct / sd_row`: **median 1.331**,
  range 0.876–2.599. The naive row null would have cleared **65** cells per-candidate versus **61**
  on the correct null. Honest note: **in this screen the null level was not where the damage was.**
  The attrition came from multiplicity and from the full reference base. The number is reported so
  it is visible rather than rediscovered a ninth time.
- **Multiplicity:** family-wise max-z across all 117 cells from the same draws. **61 per-candidate →
  31 family-wise** on the single-ref base; **0 of 39** on ppm under the full base.
- **`noop_placebo`:** observed sd = **0.000000e+00** for all three outcomes, `max|draw−real| = 0`,
  `n_distinct_draw_values = 1`, verdict `CONFIRMED NO-OP`. Reported as observed rather than rounded.
- **Negative control `G01_noise`:** dR2 3.8e-05 to 5.8e-05, correct-level p 0.324/0.394/0.451,
  family-wise p 1.000 on all three. It died, as it must.
- **Vacuous control `G02_ref_echo`:** dR2 **exactly 0.000000**, p 1.000 on all three — confirming
  `BaseFit` correctly gives zero credit for re-adding a column already in the base.
- **Leakage probes.** No candidate was flagged (`leakage_probes.csv`, all 39). The *reference* probe
  is reported honestly: `refB_ppm` vs `refA_ppm` came back **FLAGGED**
  (`FLAGGED__CONSISTENT_WITH_LEAKAGE__ALSO_CONSISTENT_WITH_A_BETTER_ESTIMATOR`), as did the
  deliberately-retrospective positive control. **A flag on `refB` is expected and is not evidence of
  leakage**: `refB` is a ratio of prior sums and `refA` a mean of prior ratios, so `refB` is simply
  the better estimator of a persistent quantity, and the probe's own status string says it cannot
  distinguish the two explanations. D085 saw the same. The construction was read as well as the
  probe: `refB` applies `.shift(1)` before `.expanding()` inside `(season, player_id)`, and the
  first-appearance assertion (§3.4) holds independently.

---

# 5. KIT FEEDBACK — `_screen_kit` (D077, D082, D086)

The kit is now at 159 assertions after seven defects found by three users. I am the fourth user.
**I found no new defect in the kit's behaviour.** Every function did what its docstring said,
including the ones I misused. Two **documentation/ergonomics** observations, neither a behavioural
bug, plus one endorsement:

### KF1 — `check_manifest`'s verdict field is named `status`, and the wrong key fails SILENTLY

I wrote `check_manifest(p)["verdict"]` and got `None` for all eight files. `verdict` is not a key;
`dict.get` returned `None`. **In a provenance gate a silent `None` reads as "no problem found"**,
which is the exact inversion of what the kit had actually returned (`UNVERIFIABLE`, loudly and
correctly). Contrast `noop_placebo`, where I made the *same class* of mistake — guessing
`observed_sd` when the field is `sd` — and got a `KeyError`, which is the safe failure.

The behaviour is correct in both cases; this is about which failure mode a caller's typo lands in.
Two cheap options, in preference order: (a) have `check_manifest` return a `dict` subclass whose
`__missing__`/`get` raises on unknown keys, so a misspelled provenance key can never read as clean;
or (b) add a `verdict` alias, since that is evidently the word a caller reaches for. My own bug is
recorded as **SD2** in `CONSTRUCTION_DEFECTS.md`.

### KF2 — the README says `noop_placebo` "returns the observed sd" but does not name the field

The field is `sd`. The function-reference table lists guarantees, not field names. A one-word
change (`returns the observed sd as \`sd\``) closes it. Low severity — the failure is a `KeyError`.

### KF3 — `entity_swap_null` / `EntitySwap` is the right abstraction and it paid for itself here

Every one of my 39 candidates returned `NO_COARSER_LEVEL_EXISTS`, exactly as the K2 note predicts.
Without `EntitySwap` I would have faced D085's dilemma and been tempted into the same
entity-season decomposition that read the future. **The kit's fix removed the incentive that
created D085's error**, which is a stronger form of prevention than a warning.

One usage note for future callers, offered as documentation rather than a defect:
`EntitySwap.draw(values, rng)` is a pure relabelling of row positions that does not depend on
`values`, so `draw(np.arange(n), rng)` yields the permutation **index**, which can be cached and
reused across many candidates and outcomes. This is exact, not an approximation, and it is what
made 117 cells × 2 nulls × 600 draws plus a full re-screen affordable in an E0 time box. Worth a
line in the docstring.

### KF4 — a gap that is NOT a kit defect, but is a program-level one

`future_leakage_probe` and `entity_swap_null` **both passed `D04_xefg_minus_own` with maximum
confidence** while it was an artifact (§2.2). Neither is at fault — the candidate genuinely reads
no future, and its entity labels genuinely matter. The gap is that the program has no guard for
**reference incompleteness**. A cheap candidate guard, if the kit ever wants one: flag any
candidate whose correlation with a *reference* column exceeds some threshold, or that is
constructed as a difference against one, and require it to be screened against a base containing
that reference. I am not proposing an implementation; I am recording that the trap exists and that
two existing guards do not see it.

---

# 6. WHERE I COULD HAVE CHEATED

1. **I could have kept `D04_xefg_minus_own` and led with it.** It was a family-wise-clean 1% R2
   increment on exactly the quantity the program has been hunting for four screens, produced by a
   pre-registered candidate, with clean leakage probes and a correct-level null. Reporting it would
   have been the single most rewarded outcome available in this session. I decomposed it instead
   and it evaporated by 107x. **This is the most important disclosure in this document.**

2. **I could have led with the eFG/TS result and buried the ppm null.** 37 family-wise clears,
   sign-consistent across four seasons, surviving the decision stratum, is a genuinely impressive-
   looking table. Framing "shot quality predicts efficiency" on `y_efg` and leaving the volume
   offset unexamined would have read as a major find. The eFG result is real; it is also
   substantially arithmetic and it does not reach points, and both facts are in the headline.

3. **I could have stopped before the full-reference base.** The single-ref base was the
   pre-registered design and gave 31 family-wise clears. Adding `refB_ts` and `refB_efg` to the
   base was my own decision, made *after* seeing the results, and it is what killed the headline.
   Disclosed as a post-hoc analysis: it is a stricter test than the pre-registered one, never a
   looser one, but it was not pre-registered.

4. **I could have inherited the Step 0 argument.** Two frozen screens already assert the shotcharts
   are safe. Copying that citation would have taken one minute and looked identical in the write-up.

5. **I could have used the entity-season decomposition.** It would have made `SCHEME_BETWEEN`
   applicable and cleared many more cells, exactly as it did for D085 — and, like D085's, those
   clears would have read the future.

6. **The candidate list is hashed, so I could not have quietly widened it.** That is the point of
   the hash, and it constrained me: several mid-run ideas (shot-clock proxies, a defender-proximity
   surrogate from `ACTION_TYPE`) were **not** added, because adding them post-hoc would have made
   "39 screened" false. They are noted here as ideas, not as results.

7. **Same-day granularity in the league cold-start fallback.** `league_prior_mean` sorts by
   `(season, game_date, game_id)` and shifts by one **row**, so a row can see earlier rows from
   games played on the *same date*. This affects only the 630 of 13,989 rows (4.5%) that use the
   cold-start fallback, it is a same-day rather than a future exposure, and it is the identical
   construction used by D076/D081/D085 — I kept it for comparability rather than silently improving
   it. Disclosing it because "identical to prior screens" is a reason, not an excuse.

8. **The `fga >= 1` filter.** eFG and TS are undefined without a field-goal attempt, so the frame is
   13,989 rows rather than D085's 14,852. This drops the lowest-usage appearances, which are the
   noisiest rows. I did not test whether including them (with `y_ppm` only) changes the ppm null.

9. **In-sample dR2.** Every increment is in-sample, controlled by permutation and multiplicity
   rather than by held-out scoring. That is E0 convention and it is permissive. No candidate here
   has been shown to hold out of sample, and none is claimed to.

---

# 7. WHAT THIS CLOSES, AND WHAT IT DOES NOT

**Closes.** Combined with D081 (0 of 330 generic rate cells), D084 (opponent zone conversion,
killed on an arithmetic ceiling of dR2 ≤ 0.000129) and D085 (0 of 36 opponent matchup cells, 0 of
12 rest/load, 0 of 18 pace/transition), this screen tests the **last surface D085 named** and finds
nothing that moves points per minute. Assisted share and opponent shot-quality-conceded — the two
families that were previously unreachable — are both dead. The provenance question that blocked
them is resolved on values.

The efficiency step now has **four independent screens and roughly 1,000 cells** against it with no
survivor on `y_ppm`. The reasonable read is that the program's central question is answered in the
negative and effort should move to the **minutes-and-abstention** work that is paying off.

**Does not close.**

- **The manifest backlog is still real.** This screen resolved shotchart provenance by value test,
  not by manifest. That worked *because* the files are raw events; it would not have worked for an
  artifact-granular file, and the next agent facing an unmanifested aggregate has no such escape.
- **The eFG/TS effect is real and unexplained beyond the volume offset.** Why volume offsets
  quality so precisely is a mechanism question this screen only sketched.
- **Shot-clock and defender-proximity shot quality remain untested and untestable** from this repo.
  If those data are ever acquired, the surface reopens — this screen tested shot *location and
  type*, which is not all of shot quality.
- **Nothing here is a result.** E0. Lead only.

---

# 8. FILES

| file | what it is |
|---|---|
| `FINDINGS.json` | structured findings, 98 KB |
| `NOTES.md` | this file |
| `CANDIDATES_PRESELECTED.md` + `.sha256` | the frozen 39, hashed before any statistic |
| `CONSTRUCTION_DEFECTS.md` | **defects in MY OWN construction**, written at the moment of discovery |
| `s00_provenance.py`, `run_log_s00.txt`, `_s00.json`, `s00_column_constancy.csv` | Step 0 gate |
| `s00b_recon.py`, `run_log_s00b.txt` | join-key and pbp reconnaissance |
| `sq_base.py` | shared constants, strictly-prior helpers, `BaseFit` |
| `s01_build_frame.py`, `run_log_s01.txt`, `_s01.json` | frame build, probes, assertions |
| `s02_screen.py`, `run_log_s02.txt`, `_s02.json` | the 117-cell screen |
| `s03_forensics.py`, `run_log_s03.txt`, `_s03.json` | the four kill tests |
| `s04_transfer.py`, `run_log_s04.txt`, `_s04.json` | volume-offset mechanism |
| `s05_finalise.py`, `run_log_s05.txt` | assembles `FINDINGS.json` |
| `screen_frame.parquet` | 13,989 rows × 63 cols |
| `screen_results.csv` | all 117 cells, single-ref base |
| `k1_full_reference_base.csv` | all 117 cells, full own-prior base |
| `k3_decision_stratum.csv`, `k4_per_season.csv` | stratum and stability |
| `interaction_with_main_effects.csv` | family F with its own main effects |
| `s04_volume_offset.csv` | eFG vs FGA/min vs ppm, signed |
| `family_attrition.csv`, `grouping_levels.csv`, `var_share_between.csv` | screening bookkeeping |
| `leakage_probes.csv`, `candidate_coverage.csv` | per-candidate probes and coverage |
| `permutation_draws.npz`, `maxt_null_draws.csv` | the draws behind every p-value |
