# P2A_POSSESSION_COLUMN_ADJUDICATION — S8: the 48 possession columns, individually adjudicated

**Node:** `P2A_POSSESSION_COLUMN_ADJUDICATION` · **Lane:** possession · **Type:** audit
**Role:** schema reconciliation auditor · **Severity on failure:** A

## Epistemic status of this output

> VERIFIED_READ_ONLY_DERIVATION. Closes a coordinator error: the packet dumped 48 column names under context_availability and the gating availability table named none of them. Adjudication makes a column ELIGIBLE or PROHIBITED; it admits nothing.

Nothing here is fitted, scored, promoted or admitted. Nothing here reads
`stage2b/SEALED_RESULTS/`. No comparative historical performance of any challenger was inspected.
`feature_gate.py` was imported and called **read-only, from this node's own call site**, purely to
record what the frozen gate does and does not catch; it was not edited.

---

## Headline

**`possessions_raw_v2` is the target's own source, not a feature source.** The primary target is

```
REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS
  = n_off_poss(game, team) * 40 / (40 + 5 * max(0, max_period(game) - 4))
```

and every input to it is a column of this artifact: `n_off_poss` is the **row count** of
`(game_id, offense_team_id)` — reproduced exactly, 2,990 of 2,990 team-game rows — and
`max_period` is the per-game maximum of `period`. **The target is exactly reconstructible from
three of the 48 columns.**

That is not a new claim I am making about the artifact. It is already the declared status of the
artifact at the one place it is consumed. `possession_features.py` lines 252-257 declare it

> `role="outcome_source"`, `cutoff_valid=False`, "...therefore contributes NO feature column."

**Adjudication of the 48:**

| label | n | meaning |
|---|---:|---|
| **ELIGIBLE** | **7** | target-game value knowable strictly pre-tip; may be *considered*, not admitted |
| **LAGGED_USE_ONLY** | **38** | REALISED TARGET-GAME OUTCOME; target-game value prohibited on the prediction path |
| **PROHIBITED** | **2** | no admissible use in any form |
| **CUTOFF_UNPROVEN** | **1** | availability established, cutoff validity not established |
| | **48** | |

**Zero columns are admitted. Zero columns are admitted on availability grounds.**

---

## Definitions I applied

The four labels answer one question: *what may be done with this column's **target-game value**,
read from **this artifact**, on the **prediction path**?*

* **ELIGIBLE** — the target-game value is determined by a schedule or reference fact known before
  tip, is constant within the game (or within the game-team), and carries no realised in-game
  content. ELIGIBLE means the column may be **considered**. Admission additionally requires a
  registered arm, a construction receipt and a **fold-level** gate pass, none of which happen here.
* **LAGGED_USE_ONLY** — the value is a realised outcome of the target game. The target-game value
  is prohibited on the prediction path. An aggregate over **strictly earlier** games may be
  *proposed*; this node licenses no such construction.
* **PROHIBITED** — no admissible use in any form, target-game or lagged, because the column is
  structurally incapable of carrying information (constant) or is an exact duplicate of another
  column.
* **CUTOFF_UNPROVEN** — present in the bytes, but the argument that its value is knowable at cutoff
  has not been established.

Per `RESEARCH_CONTRACT_V1` precedence — *the stricter governs* — where a column had a defensible
reading under two labels I took the stricter one and recorded the hazard rather than the excuse.

---

## Reproduction

Everything below comes from two scripts, run from the worktree root:

```
python experiments/player_program/stage2b/P2A_POSSESSION_COLUMN_ADJUDICATION/MEASURE.py
python experiments/player_program/stage2b/P2A_POSSESSION_COLUMN_ADJUDICATION/TESTS.py
python -c "import json;json.load(open('experiments/player_program/stage2b/P2A_POSSESSION_COLUMN_ADJUDICATION/FINDINGS.json'))"
```

`MEASURE.py` writes `FINDINGS.json` (every figure) and `ADJUDICATION.csv` (the 48-row grid).
`TESTS.py` re-checks 19 load-bearing invariants against the bytes and returns 1 on failure;
it currently returns **0 failures**.

Inputs pinned by hash:

| artifact | sha256 |
|---|---|
| `possessions_v2/possessions_raw_v2.parquet` | `7200881fd811db9d0d6b10ea0a19b01ec7b6d027ee4567b9ef963241b15a4b1a` |
| `projected_exposure_v1/team_possession_prior_v1.parquet` | `c37c075148553920b79c9320ea03afb37986bfc752fc84dd695f154887c3db18` |
| `stage2a/EVIDENCE_PACKET.json` | `f373e3eed710026c9d82ff88aad1e9a2cae640ee461a5d7df5208d76abaf1e4e` |
| `stage2a/EVIDENCE_PACKET_V2.json` | `3a35ae735333c47713d6e7cc4c35c081e4eb07364c71cba744db03709730a32c` |
| `stage2a/V2_STOP_CONDITION.json` | `a4dd090b2b38dfb4d37028e15daa10c689deb27269cde3d8b9cddd12fd92244d` |

`POSSESSION_INTEGRITY_RECEIPT_V2.json` records `integrity.artifact_sha256 = 7200881f...4b1a`, which
**matches the bytes on disk**. No artifact/receipt disagreement.

Universe, reported both ways and never substituted: the possession artifact spans **238,563
possessions over 1,495 scheduled game clusters (2,990 team-game rows)**; the fitted universe is the
**2,982 resolved team-game rows over 1,491 resolved clusters**. The set difference between the
artifact's game ids and the prior's is **0 in both directions**.

---

## What I measured

### 1. The 99.789% valid-ten coverage — AGREE

```
python -c "import pandas as pd; d=pd.read_parquet('experiments/player_program/possessions_v2/possessions_raw_v2.parquet'); print(d['lineup_valid_ten'].sum(), len(d), 100*d['lineup_valid_ten'].mean())"
```

**238,060 of 238,563 = 99.789154%.** S8 states 99.789% of 238,563. **AGREE**, to the digit.
Independently corroborated by `POSSESSION_INTEGRITY_RECEIPT_V2.coverage.overall` (99.7892) and by
`V1_TO_V2_RECONCILIATION.v2_valid_pct` (99.7892). The 503 invalid possessions decompose as
`defense_underfull` 222, `offense_underfull` 217, `both_underfull` 64.

Because S7 taught that a pooled figure can hide a fold-degenerate one, I broke it out per fold:

| fold | possessions | valid | pct |
|---|---:|---:|---:|
| 2021 | 33,368 | 33,237 | 99.6074 |
| 2022 | 38,307 | 38,200 | 99.7207 |
| 2023 | 41,716 | 41,468 | **99.4055** |
| 2024 | 41,758 | 41,745 | 99.9689 |
| 2025 | 48,780 | 48,777 | 99.9938 |
| 2026 | 34,634 | 34,633 | 99.9971 |

No fold is degenerate; the worst is 2023 at 99.41%.

### 2. What the coverage figure does NOT license — the substance of S8(a)

S8 reads the coverage as an **OPPORTUNITY**: "valid ten-player lineups are present on 99.789% of
238,563 possessions, which promotes player-additive hierarchical arms and an
observation-purification arm from Category B to Category A."

**That inference does not hold on the prediction path, and I am correcting it.** These are
**realised** target-game lineups. Their availability is retrospective. The packet's own corrected
availability table already carries the counter-entry:

> "starting lineup / rotation announced pregame — **UNAVAILABLE** ... realised lineups are
> target-game outcomes."

Both statements are in the same document about the same fact. High coverage licenses **player-level
attribution of completed-game outcomes** — an outcome-side or observation-model use, which is what
`player_season_possessions_v2.parquet` already does. It does not make any lineup column a pregame
feature, and it cannot promote an arm from Category B to Category A **on availability grounds**,
because the criterion those categories turn on is cutoff validity, not availability.

Two further measured facts bear on any player-additive arm built off these columns:

* **The five lineup slots carry no positional meaning.** `off_p1..off_p5` are the **ascending order
  statistics** of the on-court player-id set: strictly ascending on 238,499 of 238,563 rows, and the
  64 exceptions are exactly the rows with no offensive players at all. `off_p1` is simply the
  smallest player id on the floor. Any numeric use of a slot column is meaningless; any one-hot use
  is a 300-level dimension.
* **`off_p5`'s null mask is an exact outcome indicator.** Its 281 nulls coincide **exactly** with
  `lineup_class` in {`offense_underfull`, `both_underfull`} — zero off-diagonal. That is the
  `missingness_encodes_outcome` shape `feature_gate` was built for after ws1.

### 3. The six columns the acceptance criteria name — all LAGGED_USE_ONLY

`is_overtime`, `score_diff_offense_start`, `score_diff_offense_end`, `abs_score_diff_start`,
`regulation_seconds_remaining` and `non_competitive_conservative` are **REALISED TARGET-GAME
OUTCOMES**. Each is derived in `possession_artifact_v1.enrich()` from realised in-game state. The
identities reproduce exactly:

| identity | rows |
|---|---|
| `score_diff_offense_end == score_diff_offense_start + points_scored` | **238,563 / 238,563** |
| `abs_score_diff_start == abs(score_diff_offense_start)` | **238,563 / 238,563** |
| `non_competitive_conservative` reproduced from `GARBAGE_RULE` over `abs_score_diff_start`, `regulation_seconds_remaining`, `is_overtime` | **238,563 / 238,563** |

`score_diff_offense_end` contains the possession's **own** realised points. The final absolute
margin of every one of the 1,495 games is readable off the last possession's
`score_diff_offense_end` (mean 11.4883, max 53). `home_pts_before` / `away_pts_before` are the
running scoreboard; total points per game reconstruct to a mean of 165.209 (min 111, max 247).
`non_competitive_conservative` fires on 14,593 possessions (6.117%) touching 873 games; it is
pre-*possession* within the game, which is not the same thing as pre-*game*, and that distinction is
exactly what the ruling is about.

### 4. Same-game duration and overtime surrogates — the S1 shape, inside this artifact

The ruling prohibits `game_minutes`, realised duration, realised overtime **and any exact or
approximate same-game surrogate** from the prediction path. Measured, over all 1,495 games:

| column | reconstruction of realised game duration | exact on |
|---|---|---|
| `period` | `game_minutes = 40 + 5*max(0, max_period - 4)` — this **is** the target's denominator | definitional |
| `end_sec` | `max(end_sec) == game_minutes * 60` | **1,495 / 1,495** |
| `duration_sec` | `sum(duration_sec) == game_minutes * 60` | **1,495 / 1,495** |
| `is_overtime` | `any(is_overtime) == (game_minutes > 40)` | **1,495 / 1,495** |
| `period_clock_start_sec` | max over the game's **last** period is 600 in regulation, 300 in OT | **1,495 / 1,495** |

66 games (**132 team-game rows**) went to overtime; `game_minutes` takes the values 40 (2,858
team-game rows), 45 (120), 50 (10), 60 (2).

`regulation_seconds_remaining` is the *approximate* case, and it is worth stating precisely because
"approximate" is where an arm would try to live. Its zero-floor fires on 1,497 rows against 1,434
overtime rows; the 63 excess rows are **all** period-4 possessions starting at exactly 2400.0s — a
clip boundary, not overtime. As a game-level detector:

| rule | games flagged | true OT | false positive | false negative |
|---|---:|---:|---:|---:|
| any row with `rsr == 0` | 118 | 66 | 52 | **0** |
| two or more rows with `rsr == 0` | 70 | 66 | **4** | **0** |

100% sensitivity at 96.4% / 99.7% specificity. That is an approximate same-game overtime surrogate,
and the ruling prohibits approximate surrogates, not only exact ones.

**S1 said `master_team.minutes` is an exact overtime indicator and the availability table missed
it. The same defect is inside `possessions_raw_v2`, five separate ways, and S8 named none of
them.**

### 5. What the frozen gate does and does not catch — it does not catch this

I handed `feature_gate.audit` the six named columns aggregated to team-game level (mean over the
team's own offensive possessions) with the real target supplied as `target=`.

| column | corr with target |
|---|---:|
| `abs_score_diff_start` | 0.068461 |
| `regulation_seconds_remaining` | -0.063800 |
| `is_overtime` | -0.020892 |
| `non_competitive_conservative` | 0.008597 |
| `score_diff_offense_start` | 0.006487 |
| `score_diff_offense_end` | 0.006320 |

`target_derived` **did not fire** — the threshold is 0.98 and the largest absolute correlation is
0.0685. The single blocking finding on the six-column design is `near_collinear` between
`score_diff_offense_start` and `score_diff_offense_end` (r = 0.999917) — a **within-design
redundancy, not leakage**. Drop that one column and **the remaining five realised target-game
outcomes PASS the gate outright**.

**I will not overstate why this matters.** The correlations are small for a real reason: the target
is *regulation-equivalent*, i.e. deliberately normalised to remove realised duration, so realised
`game_minutes` correlates with it at only **-0.0209**. A leakage argument resting on a measured
linear correlation would be **false here**. The prohibition rests on two things that *are*
measured: (a) the ruling prohibits realised duration and overtime **categorically**, and each of
these columns is an exact or approximate same-game surrogate for them; and (b) combined with the
row count of `offense_team_id`, `period` reconstructs the target **exactly**. A small correlation is
evidence about a linear channel, not evidence of safety.

This is the S1 and S5 shape a third time: **the gate is not the control here — the adjudication
is.**

### 6. The seven ELIGIBLE columns, and the hazard on three of them

`game_id`, `season`, `season_type`, `game_date` are schedule facts, constant within game, identical
to values the contract schedule already supplies. `season_type` is the **one** possession column
already carried as a feature anywhere — `possession_features.py:318`,
`is_playoff_game = (season_type == "Playoffs")`.

`offense_team_id`, `defense_team_id` and `is_home_offense` are team identity and the home/away
mapping — schedule-determined, and `is_home_offense` is constant within
`(game_id, offense_team_id)`. **They carry a severe hazard, recorded on each of their rows in
`ADJUDICATION.csv`:** the **row multiplicity** of `offense_team_id` *is* the target numerator
(2,990 of 2,990 exact). Identity use requires a `drop_duplicates` join. Any `size()`, `count()` or
per-possession aggregate over these columns reconstructs the target. An arm that takes team identity
from this artifact rather than from the contract schedule buys nothing and carries that
reconstruction one function call away.

### 7. Fold-local estimability — S7's shape on a column S8 never reached

| fold | team-game rows | clusters | playoff rows | `is_playoff_game` sd | era v2 / v3 | `era` sd |
|---|---:|---:|---:|---:|---:|---:|
| 2021 | 418 | 209 | 34 | 0.2734 | 384 / 34 | 0.2734 |
| 2022 | 478 | 239 | 46 | 0.2949 | 432 / 46 | 0.2949 |
| 2023 | 520 | 260 | 40 | 0.2665 | 480 / 40 | 0.2665 |
| 2024 | 524 | 262 | 44 | 0.2773 | 480 / 44 | 0.2773 |
| 2025 | 620 | 310 | 48 | 0.2673 | 216 / 404 | 0.4765 |
| **2026** | 430 | 215 | **0** | **0.0000** | 0 / 430 | **0.0000** |

**`is_playoff_game` is identically zero in fold 2026.** That is a blocking `feature_gate`
`zero_variance` condition in that fold, on the only possession column anything currently uses. The
cause is benign — the 2026 season is incomplete, data ending 2026-07-31, so no playoffs have been
played — but the consequence is live for any fold-level gate run today, and it is the ws3 / S7
shape: pooled healthy, fold degenerate.

### 8. `era` — the one CUTOFF_UNPROVEN column

`era` is the play-by-play **schema** era, set in `build_possessions.py:443` from
`wnba_schema.detect_era`, which detects it **per file, from the target game's own play-by-play**.
That file does not exist before the game is played and ingested.

The obvious rescue — "it is derivable from the schedule" — **fails on measurement**. The date spans
overlap: v2 runs 2021-05-14 to 2025-06-29, v3 runs 2021-09-23 to 2026-07-31. It is not a function of
`season` (both eras appear in every season 2021-2025) and not a function of `season_type` (v3 carries
all 106 playoff games **and** 393 regular-season games). The 2025 regular season splits mid-season:
last v2 game 2025-06-29, first v3 game 2025-07-03. Availability is established; cutoff validity is
**not**. It is also zero-variance in fold 2026.

### 9. The two PROHIBITED columns

* **`all_possessions`** — literal `True` on all 238,563 rows. `feature_gate` raises **blocking
  `zero_variance`**. It is a filter flag, and there is no construction, lagged or otherwise, in
  which it carries information.
* **`source_pbp_game_id`** — byte-equal to `game_id` on **238,563 of 238,563** rows. `feature_gate`
  raises **blocking `exact_duplicate`**. A provenance alias; its only possible effect on a design is
  to inflate an apparent feature count.

---

## The full adjudication

`ADJUDICATION.csv` and `FINDINGS.json.adjudication` carry, per column: label, origin (the exact
producer expression), cutoff basis, hazard, dtype, nulls, cardinality, whether the availability table
named it, and whether it is one of the six the acceptance criteria name.

| label | columns |
|---|---|
| **ELIGIBLE** (7) | `game_id`, `season`, `season_type`, `game_date`, `offense_team_id`*, `defense_team_id`*, `is_home_offense`* |
| **CUTOFF_UNPROVEN** (1) | `era` |
| **PROHIBITED** (2) | `all_possessions`, `source_pbp_game_id` |
| **LAGGED_USE_ONLY** (38) | `possession_idx`, `period`, `start_sec`, `end_sec`, `duration_sec`, `points_scored`, `end_reason`, `home_pts_before`, `away_pts_before`, `off_p1`-`off_p5`, `def_p1`-`def_p5`, `n_off_oncourt`, `n_def_oncourt`, `is_overtime`, `period_clock_start_sec`, `period_clock_end_sec`, `regulation_seconds_remaining`, `score_diff_offense_start`, `score_diff_offense_end`, `abs_score_diff_start`, `non_competitive_conservative`, `is_zero_duration`, `is_technical_derived`, `possession_kind`, `lineup_class`, `lineup_valid_ten`, `n_oncourt_total`, `source_possession_idx`, `canonical_seq`, `source_order_differs` |

(*) ELIGIBLE **as identity only**, under the row-multiplicity hazard in section 6.

---

## Contradictions found

**C1 — S8's `named_in_the_CUTOFF_VALID_AVAILABILITY_TABLE: 0`. CORRECTED to 7.**
Whole-word matching each of the 48 column names against the serialised
`cutoff_valid_availability_table_CORRECTED`: **7 are named** — `game_id`, `season`, `season_type`,
`game_date`, `period`, `duration_sec`, `end_reason`. Three of them (`period`, `duration_sec`,
`end_reason`) appear in the entry that explicitly cites `possessions_raw_v2` as its source, with the
verdict "ONLY LAGGED". **41 of 48 are never named anywhere in the table.** The identical 7 are named
in the V1 table.
The substantive point *survives and is barely dented*: 41 columns were never adjudicated at all, and
the 3 that were, were adjudicated **as a group, with no per-column evidence**. But the figure "0" is
not what the bytes say. *Severity: B — a wrong count inside a Severity-A finding.*

**C2 — this node's own mandate line says "32 possession columns". NOT REPRODUCED.**
The generated brief is titled *"S8: adjudicate the 32 possession columns the availability table never
named"*, while S8's own body says 48 total and 0 named. Measured: 48 total, 7 named, 41 never named,
45 never named with `possessions_raw_v2` as the cited source. **No arithmetic over the packet
produces 32.** I adjudicated all 48 regardless, which is what the acceptance criterion asks for.
*Severity: B — a contract/finding disagreement, recorded not resolved.*

**C3 — the packet asserts an availability OPPORTUNITY and an availability PROHIBITION about the same
fact.**
`cutoff_valid_availability_table_CORRECTED` says "starting lineup / rotation announced pregame:
UNAVAILABLE ... realised lineups are target-game outcomes", while S8 reads the 99.789% lineup
coverage as promoting player-additive arms "from Category B to Category A". Both are about the same
realised lineup columns. The first is correct for the prediction path; the second is a category error
between **availability** and **cutoff validity**. *Severity: A — it is precisely the error the
acceptance criterion "no column is admitted on availability grounds alone" exists to catch.*

**C4 — the packet names three possession columns "ONLY LAGGED" and stops one step short.**
The entry "possession-level `end_reason`, `duration_sec`, `period` — coverage: all contract games —
cutoff_valid: ONLY LAGGED" is correct as far as it goes. But `duration_sec` **sums exactly to
realised game duration** and `period` **is the target's own denominator input**, on 1,495 of 1,495
games. Naming them "ONLY LAGGED" without naming that is the S1 defect again: a convention where an
enforced invariant is required. *Severity: A as a latent hazard.*

**C5 — `feature_gate` passes five of the six named realised-outcome columns.**
Not a document contradiction but a contradiction between the program's stated protection and its
actual reach; measured in section 5. *Severity: A as a latent hazard — the gate cannot be the control
for this class of column.*

**C6 — no artifact/receipt disagreement.** `POSSESSION_INTEGRITY_RECEIPT_V2.integrity.artifact_sha256`,
row count 238,563 and `valid_pct_possession_weighted` 99.7892 all reproduce against the bytes.
Recorded because it was checked, not because it was doubtful.

---

## What I could NOT establish, and why

1. **Whether any lagged construction over the 38 LAGGED_USE_ONLY columns is cutoff-valid.** Out of
   mandate. I adjudicated the target-game row and stopped. Nothing here licenses a trailing overtime
   rate, a trailing lineup feature, or any other lagged construction — each is a *different object*
   with its own cutoff argument. In particular, the packet's E5 note that "trailing OT rate is
   cutoff-valid and gate-passing" is **not** confirmed by this node.
2. **Whether `era`'s value could be known pregame from the ingestion pipeline's own rollout
   schedule.** I established it is not a function of `season` or `season_type` in the observed data.
   I did not establish what *does* determine it; that would need the feed operator's rollout record,
   which is not in this repository.
3. **Why 52 games carry a period-4 possession starting at exactly 2400.0s and 1,377 do not.** I
   established the 63 false-positive rows are a clip artifact of `clip(2400 - start_sec, 0, None)`
   and not overtime. Diagnosing their origin would be repair work on a frozen artifact.
4. **Anything about downstream turnover.** Not measured, deliberately: the primary possession verdict
   must be frozen before any downstream number is computed.
5. **Whether the 4 unresolved clusters / 8 unresolved team-game rows differ in column semantics.**
   They are absent from the fitted universe by construction and the possession artifact covers all
   1,495 clusters. I reported both universes and did not analyse the 8 rows separately.
6. **Whether the ELIGIBLE 7 survive a fold-level gate.** I measured fold-local variance for
   `season_type` and `era` only. A full per-fold rank, conditioning and missingness audit of any
   proposed design is Phase 0 requirement 8 and belongs to the arm that proposes it.

---

## Stop conditions

> *a finding would change the primary target, the K0 structure, the inference structure, the
> candidate universe, the cutoff-valid feature set or the leakage status — HALT and raise, do not
> resolve it inside the node*

**TRIPPED on the CUTOFF-VALID FEATURE SET. Raised, not resolved.**

Three items, in descending severity:

1. **41 of 48 columns were never adjudicated, and 38 of the 48 are realised target-game outcomes.**
   The cutoff-valid feature set as the availability table describes it is incomplete in the direction
   that admits. This is S8 as raised, now quantified per column.
2. **Five exact same-game duration/overtime surrogates live inside `possessions_raw_v2`** — `period`,
   `end_sec`, `duration_sec`, `is_overtime`, `period_clock_start_sec` — plus one approximate
   surrogate, `regulation_seconds_remaining`, at 100% sensitivity. S1 raised this shape for
   `master_team.minutes`. It is the same defect, in the possession artifact itself, and the
   availability table's "ONLY LAGGED" entry does not name it.
3. **The target is exactly reconstructible from three columns of the artifact.** Any arm that reads
   `possessions_raw_v2` for anything other than the target must do so under an enforced invariant,
   not a convention.

**TRIPPED on the INFERENCE STRUCTURE. Raised, not resolved.**

`is_playoff_game` — the only possession column currently carried as a feature — is **identically zero
in fold 2026**, a blocking `zero_variance` condition per fold; `era` likewise.
`GATE_INVOCATION_CONTRACT` section 4 requires the fold-level fallback frozen with a numeric trigger
**before results are visible**. This column sits inside that requirement and had not been identified
as such. It overlaps P27's mandate and is recorded here rather than resolved.

**NOT tripped.** The primary target, the K0 structure and the candidate universe are untouched by
this node. No column was promoted, demoted or admitted anywhere outside this node's directory. No
packet, availability table or gate was edited.

---

## Scope note

Every file written by this node lives in
`experiments/player_program/stage2b/P2A_POSSESSION_COLUMN_ADJUDICATION/`: `MEASURE.py`, `TESTS.py`,
`FINDINGS.json`, `ADJUDICATION.csv`, `REPORT.md`. `TESTS.py` asserts that set. No frozen artifact was
modified. **No mutating git command was run.** The only git invocations were
`git rev-parse --abbrev-ref HEAD` (to confirm the worktree is on `player-model-program`) and
`git status --porcelain` (to confirm nothing outside this directory was touched); both are read-only.

Declared read scope is `experiments/player_program/`. Establishing the derivation of `era` required
reading, read-only, two files outside that tree: `build_possessions.py` and `wnba_schema.py`, both
named in `possession_artifact_v2.PRODUCERS`. Flagged rather than assumed to be fine.
