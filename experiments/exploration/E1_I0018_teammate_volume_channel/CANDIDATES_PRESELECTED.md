# E1_I0018 — TEAMMATE VOLUME CHANNEL — PRESELECTED CANDIDATE LIST

**This file is frozen and SHA-256 hashed BEFORE any statistic is computed.** The hash, the
preselected count, the screened count, and the added/dropped counts are reported in
`FINDINGS.json` and `NOTES.md`. Nothing may be added after seeing a result; anything dropped
must be reported as an attrition line with its reason.

**E1 exploration. LEAD, NEVER A RESULT.** No bootstrap, no promotion threshold, no registry
entry, no ledger entry, no graph event. Nothing here may be cited as evidence.

---

## 0. The lead being examined

`C04_teammate_usg_present` from D085 (`E0_I0016_efficiency_predictors`), defined in that screen's
frozen `s01_build_frame.py` as, for player `p` in team-game `g`:

```
C04[p,g] = sum over q in PRESENT(g), q != p, of  prior_usage_per_game[q]
prior_usage_per_game[q] = (cumulative q "used" over the team's STRICTLY PRIOR games this season)
                          / (count of those games q appeared in)
used = fga + 0.44*fta + tov
PRESENT(g) = the set of players with minutes > 0 in TODAY's box for that team-game
```

Everything except `PRESENT(g)` is strictly prior. `PRESENT(g)` is **TODAY'S BOX MEMBERSHIP** —
who actually dressed and played — which is **not knowable when an early line is posted**. That is
the tip-time constraint, and it is attached to every tip-time number in this screen.

---

## 1. OUTCOMES (5 primary + 2 secondary), all realised-game responses

`TSA = fga + 0.44*fta` ("true shot attempts", the true-shooting denominator).

| id | definition | role |
|---|---|---|
| `y_ppm` | `pts / minutes` | the D081 quantity — the per-minute step where the champion fails |
| `y_spm` | `TSA / minutes` | **the volume arm of the decomposition** |
| `y_pps` | `pts / TSA` | the conversion arm — `y_ppm = y_spm * y_pps` EXACTLY |
| `y_ts` | `pts / (2*TSA)` | D085 reproduction target. `y_ts == y_pps / 2` exactly |
| `y_efg` | `(fgm + 0.5*fg3m) / fga` | D085 reproduction target |
| `y_fgapm` | `fga / minutes` | secondary decomposition, volume arm |
| `y_ppfga` | `pts / fga` | secondary decomposition, conversion arm |

## 2. BASES (references). D069: plain unweighted OLS, SST about the UNWEIGHTED mean.

All reference columns are ratios of **strictly prior** sums inside `(season, player_id)`,
`.shift(1)` before `.expanding()`, with a same-season strictly-earlier league-expanding-mean cold
fallback. Identical construction to D085's REF-B.

| id | columns in the base | purpose |
|---|---|---|
| `B_SINGLE` | `[1, refB_<outcome>]` | **D085's base.** Used for the reproduction and for the like-for-like channel comparison |
| `B_COMPLETE` | `[1, refB_ppm, refB_spm, refB_pps, refB_mpg]` | **the D087 REFERENCE-INCOMPLETENESS check.** Every available prior measurement of the target quantity, not only the one that names the outcome: prior points-per-minute, prior shots-per-minute, prior points-per-shot, prior minutes-per-game |
| `B_COMPLETE_PLUS_USAGE` | `B_COMPLETE + [refB_own_usg_pg]` | the player's own strictly-prior usage per game, added because of the algebraic identity in §5 |
| `B_RELIABILITY` | `B_SINGLE + [n_prior, prior5_minutes]` | D085's own reliability/role control, reproduced |

## 3. STRATA

| id | rule | n (D085) |
|---|---|---|
| `POOLED` | Regular Season, appeared (minutes > 0), `n_prior >= 3` | 14,852 on ppm |
| `DECISION` | `POOLED` AND `n_prior >= 8` AND trailing-5 prior mean minutes `>= 24` | 5,673 |

## 4. CANDIDATES — 16 preselected

**TIP-TIME** = reads today's box membership. **PRIOR** = reads nothing dated on or after game day.

### Family T — tip-time (reads TODAY's box)

| id | definition | window |
|---|---|---|
| `T01_c04_tiptime` | D085's `C04_teammate_usg_present`, rebuilt here and asserted equal to the frozen column | **TIP-TIME** |
| `T02_teamgame_present_usg` | `sum over q in PRESENT(g) of prior_usage_per_game[q]` — INCLUDING self; constant within a team-game | **TIP-TIME** |
| `T03_absent_usg` | D085's `C08_vacated_usg`: `sum over roster q NOT in PRESENT(g) of prior_usage_per_game[q]` | **TIP-TIME** |
| `T04_n_present` | number of players in today's box for that team | **TIP-TIME** |

### Family O — strictly-prior own-quantity (the reference-incompleteness vector)

| id | definition | window |
|---|---|---|
| `O01_own_usg_pg` | the player's OWN `prior_usage_per_game` — strictly prior, player level | strictly prior |

### Family P — strictly-prior-only availability variants (**no same-day information at all**)

| id | definition | window |
|---|---|---|
| `P01_c04_prevgame` | as `T01` but `PRESENT` replaced by the box membership of the team's **PREVIOUS** game | strictly prior |
| `P02_c04_availweighted` | `sum over roster q != p of prior_usage_per_game[q] * prior_availability_rate[q]`, where `prior_availability_rate[q]` = fraction of the team's strictly prior games this season in which `q` appeared | strictly prior |
| `P03_c04_avail5` | as `P02` but the availability rate is over the team's **5 most recent strictly prior** games | strictly prior |
| `P04_absent_usg_prevgame` | as `T03` but measured on the team's **PREVIOUS** game | strictly prior |
| `P05_n_present_prevgame` | number of players in the team's **PREVIOUS** game box | strictly prior |
| `P06_c04_rotstab` | `P03` further multiplied, per teammate, by that teammate's **rotation stability** = 1 if they appeared in each of the team's last 3 prior games, else their appearance rate over those 3 | strictly prior |

### Family N — the same-day news increment (what a prior-only variant CANNOT know)

| id | definition | window |
|---|---|---|
| `N01_news_vs_prevgame` | `T01 - P01` | **TIP-TIME** |
| `N02_news_vs_avail` | `T01 - P02` | **TIP-TIME** |

### Family M — mechanism / asymmetry (absence vs return)

`dev = T01 - (team's strictly-prior expanding mean of T01 this season)`.

| id | definition | window |
|---|---|---|
| `M01_dev_pos` | `max(dev, 0)` — **more** teammate usage present than the team's own running norm (returns) | **TIP-TIME** |
| `M02_dev_neg` | `min(dev, 0)` — **less** than the norm (absences) | **TIP-TIME** |

`M01` and `M02` are entered TOGETHER in one regression; the asymmetry test is whether their two
coefficients are equal and opposite.

### Family G — controls

| id | definition | window |
|---|---|---|
| `G01_noise` | deterministic pseudo-random `N(0,1)`, seed 20260808. **Negative control**: carries no information by construction | none |

Preselected candidate count: **16** (`T01`–`T04`, `O01`, `P01`–`P06`, `N01`, `N02`, `M01`, `M02`,
`G01`). Counting `G01` as a control, **15 substantive**.

## 5. THE ALGEBRAIC IDENTITY THAT MOTIVATES `O01` AND `B_COMPLETE_PLUS_USAGE`

Written before any statistic was computed, from reading D085's frozen construction:

```
T01[p,g] = sum over q in PRESENT(g), q != p, of prior_usg_pg[q]
         = ( sum over q in PRESENT(g) of prior_usg_pg[q] )  -  prior_usg_pg[p]
         = T02[g]  -  O01[p]
```

`T02[g]` is **constant within a team-game**. Therefore **ALL of `T01`'s within-team-game variation
is exactly `-O01`, the player's own strictly-prior usage per game** — a strictly-prior
PLAYER-LEVEL quantity that is **not in D085's base `[1, refB_ppm]`**. This is the
REFERENCE-INCOMPLETENESS shape D087 recorded: a candidate that smuggles a second, strictly-prior
measurement of the player's own volume into a base that measured only their prior points rate.

**This is a prediction, not a finding.** It predicts that `T01`'s ppm increment collapses once
`O01` (or, equivalently, the player's own prior shots-per-minute and prior minutes) is in the
base. §2's `B_COMPLETE` and `B_COMPLETE_PLUS_USAGE` are the tests. The prediction is recorded here,
in the pre-registered file, so that whichever way it lands it cannot be presented as a
post-hoc rationalisation.

## 6. SIGN PREDICTIONS, RECORDED IN ADVANCE

Two rival mechanisms make **opposite** sign predictions on `T01`:

| mechanism | story | predicted sign of `T01` on `y_ppm` and on `y_spm` |
|---|---|---|
| **usage redistribution** | when high-usage teammates are absent, the remaining players absorb their shots | **NEGATIVE** (more teammate usage present -> fewer shots for me) |
| **shot creation** | when creators are absent, nobody generates good looks and everyone's volume falls | **POSITIVE** |

Asymmetry prediction: a pure mechanical redistribution is **symmetric** — `M01` and `M02` should
have equal and opposite slopes. A behavioural/role story (a player promoted into a bigger role does
not fully surrender it when the starter returns) predicts **asymmetry**.

## 7. THE CELL GRID ENTERED INTO MULTIPLICITY

Every cell is `(candidate, outcome, base, stratum)` with a dR2 against a **matched
point-in-time reference facing the same rows**, plus the three nulls (N1 within-entity-season,
N2 entity-label swap, N3 row-level CONTRAST ONLY). The family-wise max-t is computed across
**every cell screened in this directory**, on both correct-level nulls, and the **worse** is
reported. The exact cell count and the attrition ladder are in `FINDINGS.json`.

## 8. WHAT IS **NOT** DONE HERE

- No model is fitted. The champion is never loaded and never retrained.
- `data/w1_truth/player_game_availability.csv` and `data/w1_truth/roster_asof.csv` are
  **NEVER OPENED**. Both are artifact-granular with `fit_through_season: 2026`; filtering does not
  help. Availability is rebuilt from box membership (the D076 method).
- No 2025 or 2026 row is read, joined, plotted or described anywhere.
- No cluster-robust standard error is reported as an alternative to a permutation null.
