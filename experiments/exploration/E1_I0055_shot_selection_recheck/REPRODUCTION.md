# REPRODUCTION — E1_I0004_shot_selection, before anything was changed

`PREREG.md` sha256 `67a41955bc06fdaef9c83def8a47b553f1b7edbd4f0a6c00e3b3fdc9a9ca70f3`,
19,540 bytes, frozen before any fit. Evidence: `out/s01.txt`, `scripts/_s01.json`,
`raw/A45_published_null_draws_signed_raw.npz`.

---

## THE ANSWER

**It reproduces. 42 of 42 anchors PASS, 21 of them at exactly `0.000e+00`, and the
load-bearing one — the whole 51,473-row analysis frame, rebuilt independently from the
132,558 raw shots without importing the parent screen's code — is cell-exact on ten of
eleven columns and at 7.77e-16 on the eleventh.**

**β = +0.7742726671354558 against the published +0.7742726671354552 (|Δ| = 6.66e-16).
Family-wise p = 0.0001999600079984003 against the published
0.0001999600079984003 (|Δ| = 0.000e+00).**

No halting rule fired. The projection work in `VERDICT.md` therefore rests on a
reproduced object, not on a re-arrangement of the published one.

---

## 1. THE FRAME WAS REBUILT, NOT RE-READ (anchor A8)

`scripts/ss_base.py::build_frame` loads the eight partition shot files
(`shots_{2021..2024}_{regular,playoffs}.parquet`, 132,558 rows, 254 Backcourt shots
excluded, 132,304 five-zone shots) and reconstructs every column from scratch.
The frozen baseline module is **not imported**: `S1` is transcribed directly as
`EWMA_0.03(zone share)` over the player's strictly prior games in season, and
`role_prior_fga` as `EWMA_0.30(FGA)` over the same window — which is what the frozen
module reduces to when it is called with `minutes := total FGA in the game`.

| column | max abs deviation from the published frame |
|---|---|
| row keys (`zone, player_id, season, game_id`), 51,473 rows | **identical** |
| `fga` | **0.000e+00** |
| `z_att` | **0.000e+00** |
| `share` | **0.000e+00** |
| `S1` | 7.772e-16 |
| `S2` | **0.000e+00** |
| `resid_S1` | 7.772e-16 |
| `OS` | **0.000e+00** |
| `opp_share_prior` | **0.000e+00** |
| `lg_share_prior` | **0.000e+00** |
| `role_prior_fga` | 1.776e-15 |
| `n_prior` | **0.000e+00** |

The three non-zero deviations are the EWMA accumulation order; they are at the last
representable bit and they are the same 7.772e-16 the parent screen itself reported for
its own identity check.

**Rows: 51,473 = 10,307 player-games × 5 zones — exact. Seasons `[2021, 2022, 2023,
2024]`, asserted at six filter points. 2025 and 2026 were never read.**

---

## 2. THE EFFECT SIZES (anchors A1, A2, A3, A7)

Response `resid_S1 = share_z − S1_z`; row set = the published 51,473 rows; SST about the
unweighted mean of the response within zone; unweighted; base = the frozen own-prior
offset `S1`; fit = plain OLS with intercept; statistic = OLS slope on `OS_z`.

| zone | published row-level β | reproduced | \|Δ\| |
|---|---|---|---|
| **Restricted Area** | **+0.7742726671354552** | **+0.7742726671354558** | **6.661e-16** |
| In The Paint (Non-RA) | +0.6529896973770617 | +0.6529896973770616 | 1.110e-16 |
| Mid-Range | +0.5558250299356523 | +0.5558250299356523 | **0.000e+00** |
| Corner 3 | +0.32472289963558754 | +0.3247228996355871 | 4.441e-16 |
| Above the Break 3 | +0.5629840482545649 | +0.5629840482545648 | 1.110e-16 |

| zone | published cluster-level β | reproduced | \|Δ\| |
|---|---|---|---|
| Restricted Area | +0.9193293906251634 | +0.9193293906251636 | 2.220e-16 |
| In The Paint (Non-RA) | +0.9573065893798413 | +0.9573065893798413 | **0.000e+00** |
| Mid-Range | +0.8107877872674014 | +0.8107877872674016 | 2.220e-16 |
| Corner 3 | +0.6377490716953922 | +0.6377490716953922 | **0.000e+00** |
| Above the Break 3 | +0.7916478162560328 | +0.7916478162560330 | 2.220e-16 |

`R²` Restricted Area: published 0.035209, reproduced **0.03520873844800998**
(|Δ| 2.6e-07 — the published figure is rounded to six places).

---

## 3. THE PERMUTATION NULL AND THE FAMILY-WISE BAR (anchors A4, A5)

5,000 draws, the parent screen's own seed `20260807 + 1`, opponent-team labels permuted
within season with the whole five-zone allowance vector travelling with the team.

| zone | null mean \|Δ\| | null sd \|Δ\| |
|---|---|---|
| Restricted Area | 2.331e-18 | 2.776e-17 |
| In The Paint (Non-RA) | 1.735e-18 | 1.943e-16 |
| Mid-Range | 3.036e-18 | 5.551e-17 |
| Corner 3 | 2.429e-17 | 1.388e-16 |
| Above the Break 3 | 1.496e-17 | 1.110e-16 |

Family-wise one-sided p for the **row-level** reals — the numbers `E1_I0004` actually
carries — reproduce **bit-for-bit, all five at `|Δ| = 0.000e+00`**:

| zone | published | reproduced |
|---|---|---|
| **Restricted Area** | **0.0001999600079984003** | **0.0001999600079984003** |
| In The Paint (Non-RA) | 0.0023995200959808036 | 0.0023995200959808036 |
| Mid-Range | 0.0009998000399920016 | 0.0009998000399920016 |
| Corner 3 | 0.060187962407518496 | 0.060187962407518496 |
| Above the Break 3 | 0.0001999600079984003 | 0.0001999600079984003 |

### The family-wise bar is NOT supplied by one cell — measured, first time

`PREREG.md` §7.5 required this and nobody had looked. Fraction of the 5,000 draws in
which each zone supplies the maximum z:

| zone | share of draws supplying the max |
|---|---|
| Corner 3 | 23.06 % |
| Mid-Range | 21.08 % |
| In The Paint (Non-RA) | 20.84 % |
| Above the Break 3 | 20.48 % |
| Restricted Area | **14.54 %** |

**No dominance.** The bar is close to the 20 % an exchangeable family would give, and
the Restricted Area cell — the headline — supplies it *least* often, which makes the bar
if anything harder for the headline than an independent bar would be. This is a clean
pass, and it is one of the few places in this programme where that check has come back
negative for a defect.

---

## 4. THE DECISION-STRATUM MACHINERY (anchor A9)

Built from `master_player.parquet` (`asof_granularity == "row"`, manifest read as a
column value, filtered to 2021–2024 immediately after load; 21,462 partition rows,
18,212 with minutes > 0). `n_prior` = count of prior appeared games in season;
`prior5_minutes` = `shift(1).rolling(5, min_periods=1).mean()`.

| anchor | target | reproduced | \|Δ\| |
|---|---|---|---|
| `E1_I0051` DECISION × CLEAN 2023–24 rows | 3,167 | **3,167** | **0** |
| … team-game blocks | 764 | **764** | **0** |

The stratum machinery is therefore the sibling screens' machinery, not a re-invention.

---

## 5. WHAT THE REPRODUCTION DOES **NOT** ESTABLISH

* It establishes that the published numbers are **arithmetically what the parent screen
  says they are**. It says nothing about whether the construction is right — that is
  what `CLOSURE.md` and `VERDICT.md` are for.
* The published headline pairs a **row-level β** (+0.7743) with a **family-wise p**
  computed from a null whose regressor is **team-season constant by construction**.
  Those two are not like-for-like, the parent screen said so in its own §6, and this
  screen reproduces both readings rather than choosing between them.
* `R² = 0.035209` is on a response conditioned on **realised** FGA. The parent screen
  disclosed this; it is repeated here because it survives into every number below.
