# PREREGISTRATION — E1_I0034_redistribution

**Screen.** When a player is absent, where do their minutes, shot attempts and points go, and is
that redistribution forecastable from pre-game information?

**Status when this file is hashed.** The build (`s02`) and four declared probes (`s03`, `s03b`,
`s03c`, `s03d`) have run. **No cell below has been evaluated.** Every number quoted in this file
comes from the build, the anchor reproduction, or the declared probes, and every one of those is
descriptive. Section 9 lists exactly what the probes looked at, because a preregistration that
hides its own exploration is worthless.

---

## 0. Anchors — reproduced on bytes BEFORE anything else (`run_log_s02.txt`)

| Anchor | Source | Published | Reproduced | Match |
|---|---|---|---|---|
| A1 | D104 home advantage, RS 2021–2024 | +0.965090 over 888 games | +0.965090 over 888 games | EXACT |
| A2 | D076 appeared player-games 2022–2024, tier-A | 13,879 | 13,879 | EXACT |
| A3a | E1_I0033 / D111 RS1 team-games | 1,392 | 1,392 | EXACT |
| A3b | E1_I0033 pre-game top-3 rows | 4,176 | 4,176 | EXACT |
| A3c | E1_I0033 top-3 appearance rate | 0.9411 | 0.9411 | EXACT |
| A3d | E1_I0033 top-3 mean `pts_hat` | 14.341 | 14.3408 | EXACT |
| A3e | E1_I0033 absence team-games | 183 | 183 | EXACT |
| A3f | E1_I0033 naive points lost | 15.815 | 15.8151 | EXACT |

`s02` asserts each of these and halts on failure. The data path is the programme's.

---

## 1. Partition

Exploration is **2021–2024 only**. 2025 and 2026 are a sealed confirmation holdout and are never
opened; `screenkit.assert_partition` is run on column VALUES after every load and every filter,
and its receipt is in `_s02.json`.

Manifests, checked before loading (`_s02.json → manifest_checks`):

| Artifact | `asof_granularity` | Status | Use |
|---|---|---|---|
| `data/masters/master_player.parquet` | `row` | USABLE_IF_FILTERED | outcomes + strictly-prior history |
| `data/masters/master_team.parquet` | `row` | USABLE_IF_FILTERED | anchors + team-game keys |
| `experiments/prediction_contract_v4/player_game.parquet` | `row` | USABLE_IF_FILTERED | identity cross-check |
| `experiments/prediction_contract_v4/team_game.parquet` | `row` | USABLE_IF_FILTERED | team-game keys |
| `cbs_v15_player_oof_v5/predictions__*` | `artifact` | **NOT a feature source** | stored forecasts scored as-is; per-fold receipt is the as-of evidence |
| `data/injury_capture/injury_log.csv` | — | **UNVERIFIABLE — REFUSED** | backs no number |
| `data/injury_history/injury_history.csv` | — | **UNVERIFIABLE — REFUSED** | backs no number |

**Because both pre-game absence sources are UNVERIFIABLE, the absence indicator in this screen is
REALISED.** Every forecast comparison is therefore an **ORACLE-ON-ABSENCE CEILING** and is named
so in its own cell id. This is the same conditioning E1_I0033 declared for its team-level
equivalent (D091 ruling 3 pattern). A ceiling that is empty closes the question; a ceiling that is
large only says the value is *conditional on knowing the absence*, which in a props market is
substantially — but not verifiably here — true.

---

## 2. Level declaration (D111 ruling 1)

Everything is measured at the **remaining-player-game level, nested in team-game**, except P01
which is a team-game cell and says so. That is the level at which the candidate varies, and it is
the level the null matches (D108 ruling 4).

---

## 3. Definitions — fixed before any cell is evaluated

Let `g` index a team-game in RS1 (regular season, 2022–2024, 1,392 team-games; anchor A3a).

* **base5**`_i^ch` = mean of channel `ch ∈ {minutes, fga, pts}` over player `i`'s **last five
  strictly earlier same-season appearances**. Written before row `i` is folded in. Verified two
  ways in `s02` §8: the first row of every player-season block is NaN in all three channels, and
  one row is recomputed by brute force to 0.00e+00. **No season aggregate and no same-game
  quantity enters any baseline.** (RETROSPECTIVE-BASELINE CHECK — done, explicitly.)
* **ESTABLISHED**`_g` = champion candidate rows for `g` with ≥3 strictly-prior same-season
  appearances and a `base5`. Mean 10.51 per team-game.
* **ABSENT**`_g` = ESTABLISHED ∧ `appeared == 0`. Mean 1.385 per team-game. **REALISED — ORACLE.**
* **REM**`_g` = ESTABLISHED ∧ `appeared == 1`. Mean 9.129 per team-game. ABSENT and REM partition
  ESTABLISHED, so there is no third category and no silent drop.
* **FREED**`_g^ch` = Σ over ABSENT`_g` of `base5^ch`. Strictly prior in its values; oracle in its
  membership. Mean 19.14 minutes; >0 in 70.5% of team-games.
* `u_i = FREED_g^ch / |REM_g|` — the uniform-allocation term.
* `z_i` = within-team-game z-score of `base5_i^ch` computed over **ESTABLISHED**`_g` (not REM), so
  `z` is absence-blind.
* `Δ_i^ch = y_i^ch − base5_i^ch`.

### Row sets

| id | definition | n | blocks |
|---|---|---|---|
| **RSP-W2** (primary) | REM rows, seasons **2023–2024** | **8,118** | 888 team-games |
| **RSP-W1** (secondary, declared) | REM rows, seasons 2022–2024 | 11,721 | 1,284 team-games |
| **RST-W2** | RS1 team-games, 2023–2024 | 888 | — |

**Why W2 is primary.** P04 compares against the champion arm and needs a walk-forward increment
fitted on a strictly earlier *scored* season; the 2021 champion fold is declared `degenerate:true`
and cannot serve. Making W2 primary for **every** cell keeps P03 and P04 on **identical rows,
identical response, identical weighting and identical base** — the D101 denominator rule — at the
cost of a third of the data. W1 is reported as a declared secondary for the five cells that do not
touch the champion, **and the direction it moves each result will be stated**.

Seasons 2021 and 2022 are used as **training data only** for walk-forward coefficients. They are
never scored in W2.

---

## 4. Column allowlists — NO NAME-BASED SELECTION ANYWHERE

Every column set is written out in full in `scripts/redist_base.py`, resolved against the frame,
printed, and its length asserted by `assert_allowlist`. Five findings in this programme died to
substring matching; nothing here matches on a substring.

* `CHANNELS = ("minutes", "fga", "pts")`, asserted length 3.
* `PLAYER_BOX_COLS` — 11 columns, asserted.
* `BIOS_COLS = ("player_id", "season", "position_raw", "draft_number")`, asserted length 4.
* Champion forecast columns are addressed by an explicit `{channel → column}` dict:
  `{"minutes": "min_hat", "fga": "fga_hat", "pts": "pts_hat"}`. Three entries, asserted.

**Reference coverage (D087).** `player_bios.csv` covers `position_raw` on 0.9332 and
`draft_number` on 0.8494 of champion rows; on the ABSENT/REM rows used here `position_raw`
coverage is **1.0000** (1,778 absentee rows, 11,721 remaining rows). Asserted in `s02` §9 and
re-asserted on the cell row set in `s04`. P05 is run on the position-known subset and its n is
reported separately.

---

## 5. THE ARITHMETIC CEILING — computed BEFORE anything is fitted

Largest linear association available between the redistribution term and the response, on RSP-W2,
before any model exists:

| channel | corr(Δ, u) | corr(Δ, u·z) | ΔR² on the **level** response | ceiling ΔMAE | vs D103 floor 0.00102 | vs largest live effect 0.002057 |
|---|---:|---:|---:|---:|---:|---:|
| **minutes** | +0.1168 | −0.0907 | **0.00470** | 0.0329 | **4.6× above** | **2.3× above** |
| **fga** | +0.0826 | −0.0466 | **0.00258** | 0.0087 | **2.5× above** | 1.3× above |
| **pts** | +0.0528 | −0.0663 | **0.00146** | 0.0059 | 1.4× above | **0.7× — BELOW** |

**Ruling, made now.** Minutes and FGA clear the floor and are fitted. **Points sits 1.4× above
D103's single-cell floor but BELOW the programme's largest live effect**; it is fitted, and its
verdict must be quoted with that ceiling attached. If the points cell returns null it is
NOT ESTABLISHED and the ceiling is the reason, not the data.

Note the sign pattern: `corr(Δ, u)` is positive (the freed volume does reappear) but
`corr(Δ, u·z)` is **negative in all three channels** — the freed volume tilts toward the players
with the *smaller* baselines, not the larger. Probe 3 showed part of that is mean reversion in a
noisy trailing-5 (the same within-team-game correlation is −0.111 for minutes in team-games with
no absence at all, against −0.186 with absence). **The mean-reversion main effect therefore sits
in the BASE of every model below, before any allocation term is tested** (D108's main-effects rule).

---

## 6. THE PREREGISTERED CELLS — 14, fixed

Every cell states: response, row set, base, candidate, null scheme, and the level the null matches.
`null_mean` and `null_sd` are published beside every p (D103 ruling 2). MDE80 = 2.80 × null_sd is
computed for **every** cell before it is interpreted (D103).

### P01 — LEAKAGE (3 cells: P01_minutes, P01_fga, P01_pts)

**The team-level question, in the only form that is not vacuous.** The naive team-level question —
"do the remaining players absorb the freed volume?" — is an *identity* for minutes: the remaining
established players' total is `200 − (minutes of players with no established baseline)`, so
conditional on the remaining players' own baselines it has nothing to do with FREED at all. The
non-vacuous version is: **does the freed volume leak OUT of the established roster to call-ups?**

* Response: minutes / FGA / points accumulated by players in team-game `g` who are **not**
  ESTABLISHED (no trailing-5) and appeared.
* Row set: RST-W2 (888 team-games).
* Candidate: `FREED_g^ch`. Base: intercept only.
* Statistic: walk-forward OLS slope `θ`. `θ ≈ 1` = full leakage to call-ups; `θ ≈ 0` = none.
* Null **N4**: permute `FREED_g` across team-games **within season** (the candidate varies at
  team-game level). 20,000 draws.

### P02 — ALLOCATION TILT (3 cells: P02_minutes, P02_fga, P02_pts)

**Is the redistribution concentrated, and on whom?** Not measured from the ex-post spread of Δ,
which is dominated by idiosyncratic noise and would read as "concentrated" even under a perfectly
uniform allocation.

* Response: `Δ_i^ch`. Row set: RSP-W2.
* Base (absence-blind, walk-forward): `α + β₁·base5_i + β₂·z_i`. **The mean-reversion main effect
  is in the base.**
* Candidate: `γ` on `u_i·z_i`, with `u_i` also in the model as a main effect.
* `γ = 0` → diffuse/uniform allocation. `γ > 0` → concentrated on the big-baseline players.
  `γ < 0` → concentrated on the bench.
* Null **N1 — WITHIN-TEAM-GAME SHUFFLE**: permute `z_i` among REM`_g` **within** the team-game,
  holding outcomes, absence and team-game marginals fixed. This destroys exactly *which* player is
  predicted to benefit and nothing else. It matches the level the candidate varies at.
  **D108's degenerate case was a WITHIN-PLAYER cyclic shift applied to a BETWEEN-PLAYER candidate,
  which a rotation preserves; this is the opposite construction.** 2,000 draws.

### P03 — FORECAST GAIN over the trailing-5 base, ORACLE ON ABSENCE (3 cells)

* Response: realised `minutes` / `fga` / `pts` (the LEVEL, not Δ). Row set: RSP-W2.
* **M0 (absence-blind)**: `α + β₁·base5_i + β₂·z_i`, walk-forward on strictly earlier seasons.
* **M1 (absence-aware)**: M0 + `β₃·u_i + β₄·u_i·z_i`, same walk-forward rule.
* Statistic: `ΔMAE = MAE(M0) − MAE(M1)`. Positive = the absence helps.
* Null **N2 — PAIRED BLOCK SIGN-FLIP** on the per-row loss difference, blocked at **team-game**
  (the absence is a team-game property, so rows within a team-game share the treatment and a
  row-level flip would be anticonservative). 20,000 draws.

### P04 — FORECAST GAIN over the CHAMPION, ORACLE ON ABSENCE (3 cells) — the commercial cell

* Response and row set: **identical to P03** (D101).
* **M0′**: champion forecast (`min_hat` / `fga_hat` / `pts_hat`) **plus a walk-forward
  intercept**, so the comparison isolates the redistribution term rather than the champion's level
  bias. The raw champion MAE is reported alongside but is not the comparison base.
* **M1′**: M0′ + `β₃·u_i + β₄·u_i·z_i`.
* Statistic and null: as P03.

### P05 — WHO BENEFITS: POSITION MATCH (1 cell, minutes only)

* Response `Δ_minutes`, row set RSP-W2 restricted to rows with a known position group
  (coverage asserted; expected ≈ 1.0000).
* Base: P02's model **including** `γ·u·z`, so position match must pay **on top of** the
  baseline-size tilt.
* Candidate: `δ` on `u_i · posmatch_i`, where `posmatch_i = 1` if player `i`'s position group
  (first token of `position_raw`, e.g. "Guard-Forward" → "Guard") equals that of the absentee
  carrying the largest `base5_minutes` in `g`.
* Null **N1** (shuffle `posmatch` within team-game).

### P06 — NEGATIVE CONTROL: PSEUDO-ABSENCE (1 cell, minutes only)

* Restricted to team-games with **FREED = 0** (no established player sat).
* In each, randomly designate `m` established players **who actually played** as pseudo-absent,
  with `m` drawn from the empirical `n_absent` distribution of the real absence games; remove them
  from REM; compute pseudo-FREED from their `base5`.
* Run the **P03-minutes machinery byte-for-byte** on the resulting frame.
* **PASS = null.** Any material gain means the machinery manufactures signal from roster
  arithmetic rather than from absence. The pseudo-absentees' realised minutes are *in* the team's
  200 and are *not* removed from anyone else's, so there is nothing to redistribute.
* This is **not** a masked copy of the treatment: the treatment row set (FREED > 0) and the
  control row set (FREED = 0) are disjoint by construction.

---

## 7. POWER — verified by injection, per cell, before any verdict (D103, D108 ruling 4)

For **every** null above, before its p is read:

1. **Injection recovery.** Plant a synthetic effect of known size through the *same code path* and
   confirm the null detects it. For P02/P05 (N1) the planted effect is added to Δ proportional to
   the candidate; for P03/P04/P06 (N2) it is a known MAE shift; for P01 (N4) it is a known slope.
   Multiples reported: 0 (must NOT detect), then 0.5×, 1×, 2×, 4× the cell's own null sd.
2. **Type-I calibration.** 400 synthetic no-effect datasets per null family, pushed through the
   full null, rejection rate reported. Target ≈ 0.05.
3. **MDE80 = 2.80 × null_sd**, computed and printed for every cell.

**A null that cannot recover a planted signal carries no verdict and will be reported as
UNINFORMATIVE, not as evidence of absence.** Where MDE80 exceeds the observed effect the verdict is
**NOT ESTABLISHED**, never "no effect" (D108 ruling 4, D103 ruling 3).

**A known trap, declared in advance** (E1_I0033 DEFECT D-1): a two-sided permutation p evaluated at
an observed statistic of *exactly* zero is 1.0000 by construction and is not a test. Any cell whose
real statistic rounds to zero will have that stated rather than reported as a type-I pass.

---

## 8. Other guards, each with the check that will be run

* **D101 denominator rule.** P03 and P04 share response, row set, SST basis, weighting and base
  family. Their ΔMAEs are set beside each other; **no ΔR² is compared across different responses**
  and no ceiling is compared across channels. Every number carries its row set and n.
* **Placebo.** A no-op transform pushed through each stat function must reproduce the real
  statistic with deviation exactly 0.0.
* **Leakage.** The time-window table in `_s02.json` names every column, its construction window,
  and the evidence. The only future-reading column in the screen is the absence indicator, which is
  labelled ORACLE in every cell id that uses it.
* **Roster/reference completeness (D087).** ESTABLISHED and REM coverage counts are asserted on the
  cell row set, not assumed from the build.
* **Seed** 20260814, fixed. Permutation draws saved as `.npz`.

---

## 9. WHAT THE PROBES LOOKED AT BEFORE THIS FILE WAS HASHED

Full disclosure, because the cells above were chosen partly in response to these:

1. `s03` — team minute budget (200 in 78.4% of team-games); rotation-depth sweep on the champion
   ranking; absence volumes; a first arithmetic ceiling; a concentration table that **blew up to
   2.98e9 because it divided by a near-zero FREED** and was discarded.
2. `s03b` — the same with a baseline-completeness requirement; the discovery that a
   proportional-to-baseline allocation has within-team-game correlation **−0.2577** with the
   realised Δ, i.e. the wrong sign.
3. `s03c` — the phantom diagnosis (6.12% of the champion's pre-game top-8 have fewer than three
   prior appearances; their `p_active_hat` is the declared constant 0.816 against a `min_hat` of
   21.63 — D111 ruling 3 seen from another direction), which is **why the rotation is defined by
   the player's own trailing-5 and not by the champion's expected minutes**; and the mean-reversion
   control that showed −0.111 of that −0.186 is present with no absence at all.
4. `s03d` — the accounting closure, which showed the pooled slope of established-player gain on
   FREED is **0.2822, not 1.0**, and that this is a roster-size confound rather than a finding —
   which is **why P01 was rewritten as a leakage cell instead of a closure cell**.

No cell above was evaluated in any probe. The probes measured associations that *inform* the
specification; the cells measure the specification against a null.

---

## 10. Decision rules, fixed now

* **DR1.** P03/P04 verdict per channel: DECIDED-POSITIVE if `ΔMAE > 0`, `p < 0.05` and
  `ΔMAE > MDE80`; DECIDED-NEGATIVE if `ΔMAE < 0` under the same conditions; otherwise
  **NOT ESTABLISHED**, with MDE80 quoted.
* **DR2.** P02 verdict: the sign of `γ` is reported with its interval regardless of significance.
  A `γ` indistinguishable from 0 at a power that could have seen `|γ|` equal to the probe's
  observed association is reported as **DIFFUSE**; at lower power, as **NOT ESTABLISHED**.
* **DR3.** If P06 (negative control) returns a gain exceeding its own MDE80, **every P03/P04 cell
  is withdrawn** and the screen reports a machinery defect instead of a finding.
* **DR4.** The headline is whichever of P03/P04 is *weakest*, not strongest, when they disagree,
  and REDISTRIBUTION.md must state the counterweight in the same document.
* **DR5.** Any cell added after this hash is reported as ADDED, with the direction it moved the
  result. Any cell dropped is reported as DROPPED, with the reason.

---

*Nothing below this line was known when this file was hashed.*
