# E1 I0004c — does the shot-mix signal survive when attempts must also be forecast?

**E1 is NON-CLAIMING.** Nothing below is a RESULT. It is a LEAD or it is dead. No
registry entry, no preregistration, no promotion, no leaderboard row, never cited as
evidence. Seasons **2021–2024 only**; the 2025/2026 confirmation holdout was never read,
joined, filtered against, counted, plotted or described.

Parent: `E1_I0004_shot_selection` (decision D074), which closed KEEP-AS-LEAD on the
shot-mix channel and **disclosed its own caveat unprompted**: its player-game increment
`ΔR² = +0.019138861495123338` on Restricted-Area attempt counts is measured **conditional
on realised FGA**. That is why its base R² is already 0.510 — given a player's actual
total attempts, predicting their rim share is easy. In live use nobody knows realised FGA
before the game. This screen exists to find out whether the signal is still there once
you have to forecast the attempts too.

---

## The short version

**The mix signal survives the attempts forecast almost intact. It does not move points.**

| | ΔR² on rim attempt counts |
|---|---|
| parent, pooled in-sample, **realised** FGA (the number being stress-tested) | **+0.019139** |
| this screen, pooled in-sample, **realised** FGA — reproduction | **+0.019139** (Δ = 0.000e+00) |
| walk-forward out-of-sample, **realised** FGA — cost of OOS fitting alone | +0.018905 |
| walk-forward, **crude** forecast `F_A` | +0.016611 |
| **walk-forward, `F_B`, no realised information anywhere — THE DECISIVE NUMBER** | **+0.016853** |

**88.1% of the conditional increment is retained.** Family-wise p across the five zones
= **0.0002** against the opponent-team-season permutation null (the 1/5001 floor of 5000
draws). MAE on rim attempts improves by **0.0230 attempts/game**. One standard deviation
of the opponent's rim-share allowance moves the *forecast* by **+0.291 rim attempts**
(+9.96% of the 2.922 mean) — against the parent's conditional +0.34.

The reason it survives is worth stating because it is not obvious: **the level of
predictability collapses and the increment does not.** Base R² on rim attempts falls
0.5110 → 0.3135 when realised FGA is replaced by a forecast. But the mix term is close to
orthogonal to attempts-forecast error, so what it adds is nearly unchanged. The
degradation curve below makes this quantitative and is the single most informative object
in the screen.

**Points is a different story and it is a clean KILL.** Walk-forward ΔR² on FG points =
**+0.000021**, cluster-level p **0.2150**. On total box points (incl. free throws) it is
+0.000920 at cluster-level p **0.0844** — and the naive row-level null would have called
that 0.0012, a 2.56× inflation and exactly the failure mode the constraint exists for.
The verdict is a **magnitude** verdict, not a power verdict: 1 sd of the opponent mix
signal moves the points forecast by **0.196 points** against a **5.82-point** response sd,
so even a *perfect, orthogonal* mix term could buy at most **ΔR² = 0.00113**. There is no
version of this channel that matters for a points line.

**Verdict: SPLIT.** Attempts KEEP-AS-LEAD; points KILL.

---

## 0. Reproduce before changing — exact, twice

| | R²(base) | R²(cand) | ΔR² | n |
|---|---|---|---|---|
| parent `dr2_results.json` | 0.5103262851681518 | 0.5294651466632752 | 0.019138861495123338 | 10307 |
| recomputed from the parent's frozen `selection_frame.parquet` | identical | identical | identical | 10307 |
| recomputed from an **independent raw-file rebuild** of the panel | identical | identical | identical | 10307 |
| **absolute difference** | | | **0.000e+00** | **0** |

The raw rebuild is a fresh transcription of the parent's panel construction straight from
`data/shotcharts/shots_{2021..2024}_{regular,playoffs}.parquet` plus the frozen
`own_rate_v2_split_alpha` module. Every column was compared to the frozen frame:

```
max|delta| fga 0.000e+00   z_att 0.000e+00   share 0.000e+00   S1 0.000e+00
           S2  0.000e+00   OS    0.000e+00   role_prior_fga 0.000e+00   n_prior 0.000e+00
row-set match: both 51473, left_only 0, right_only 0
```

Every later difference in this screen is therefore attributable to introducing the FGA
forecast, not to the harness. This is the standard the parent set (0.000e+00 against
*its* predecessor) and it is met.

---

## 1. TIME-WINDOW TABLE — what every constructed quantity reads

Read the construction, not the label. This program has found the retrospective-baseline
trap four times, and it is why the parent's own headline had to be rebuilt.

| quantity | window it READS | prior-only? |
|---|---|---|
| `z_att` (response, step 3) | the current game only — it *is* the outcome | n/a |
| `fg_pts`, `pts_total_box` (responses, step 4) | the current game only — outcomes | n/a |
| `S1` own zone-share baseline | inherited unchanged from the parent: the player's **played games strictly before this game, same season**. Frozen `own_rate_v2_split_alpha`, efficiency channel = `EWMA_0.03(zone share)` shifted one game | **yes** |
| `OS` opponent zone-share allowance | inherited unchanged: the **opponent's games strictly before this game, same season** (expanding cumsum minus the current row), minus the league share over games played **strictly before this calendar date** | **yes** |
| `lg_share_prior`, `lg_zone_rate_prior`, `lg_mean_fga_prior`, `lg_fga_per_min_prior`, `lg_faced_pg_prior` | all league shots / player-games / team-games on calendar dates **strictly before** this game's date, same season | **yes** |
| `F_LG` league-mean FGA forecast | `lg_mean_fga_prior`. No player information at all | **yes** |
| `F_A` crude FGA forecast | expanding sum of the player's FGA over **strictly prior games in season**, shrunk (K_A = 3 pseudo-games) toward `lg_mean_fga_prior` | **yes** |
| `F_A2` reference FGA forecast | `EWMA_0.30` of the player's FGA over **strictly prior games in season** — bit-identical to the parent's `role_prior_fga` | **yes** |
| `F_B_nopace` better FGA forecast, core | frozen `own_rate_v2_split_alpha` with `minutes` := the player's **real box-score minutes in strictly prior games**: `EWMA_0.03(FGA per 36 min)[prior] × EWMA_0.30(minutes)[prior] / 36`. The current game's minutes never enters its own projection (the state is shifted one game) | **yes** |
| `opp_pace` | attempts faced per game in the **opponent's strictly prior games this season** / `lg_faced_pg_prior`, clipped to [0.85, 1.15] | **yes** |
| `F_B` headline FGA forecast | `F_B_nopace × opp_pace` | **yes** |
| `q_prior` zone conversion rate | the player's **strictly prior games in season** in that zone, shrunk (K_Q = 20 attempts) toward `lg_zone_rate_prior`. **No realised conversion anywhere** | **yes** |
| `prior_min_sd`, `prior_min_mean` (step-5 splits only) | expanding sd/mean of the player's minutes over **strictly prior games in season** (`shift(1).expanding()`) | **yes** |
| walk-forward regression coefficients | fitted on all panel rows with `game_date` **strictly before** the date being predicted; training pools earlier seasons, which is earlier in time | **yes** |
| `fga` (realised total attempts) | **the current game** | **NO — DIAGNOSTIC ONLY.** Appears in exactly two roles, both labelled: (i) the reproduction and the `fga*` comparator rows, which exist to quantify the degradation; (ii) the **sample gate** `realised FGA ≥ 5`, inherited unchanged from the parent so the row set is like-for-like. It is never a feature of any forecast. |

### The one place a realised quantity touches the headline, and what was done about it

The row set is the parent's 10,307 player-games, defined by `realised FGA ≥ 5`. That is a
**sample definition**, not an input — no model sees it — but it does read the game, so the
whole of step 3 was re-run on a frame gated instead at **`F_B ≥ 5`, which is itself
pregame** (10,506 player-games). Restricted Area walk-forward ΔR² = **+0.015764** (F_B) /
+0.015323 (F_A), and all five zones keep their sign and rough size. The headline does not
depend on the realised gate.

### Known offenders explicitly not reused

`player_tendency_loo` (full-season leave-one-out), leave-one-SEASON-out player-by-zone
rates (`B0`), and leave-one-game-out FULL-SEASON team rates (`O1`) are all present in the
parent's code and **none of them is imported, recomputed or referenced anywhere in this
screen**. This screen does not even run the parent's conversion-channel reproduction,
which is where they lived.

---

## 2. Artifacts, manifests, and the two sources with none

`data/zone_maps/*` — all five carry `asof_granularity == "artifact"`, read as a **column
value** from each sibling `.manifest.json`. **Not opened.** Zones come from the raw
per-shot `SHOT_ZONE_BASIC` label, which is a property of that shot's own coordinates.

Thirteen manifests exist under `data/`: 2 `row` (`masters/master_player`,
`masters/master_team` — usable, but not needed and not read), 11 `artifact`/`season`.

Two sources this screen *does* read have **no manifest at all**, which per the standing
rule is **UNVERIFIABLE, not a pass**. Both are admitted on structural grounds, stated
here rather than buried:

- `data/shotcharts/shots_{season}_{type}.parquet` — the season is the filename and every
  column is a property of one shot event. Same basis the parent used.
- `data/wnba_gamelog_{season}.parquet` — one file per season, one row per player per
  game, every column a raw counting stat of that single game. The only three columns that
  are not raw counts (`FG_PCT`, `FG3_PCT`, `FT_PCT`) were **re-derived in-script and
  confirmed to be within-row identities** (max |diff| 5.0e-4, the file's own rounding), so
  they are not aggregates either. A column-value scan for 2025/2026 in every column
  returns nothing. It is used for **one** thing: the player's minutes in strictly prior
  games.

Because the gamelog is formally unverifiable, **no headline rests on it alone**: `F_LG`,
`F_A` and `F_A2` never touch it, and `F_A`'s walk-forward ΔR² is **+0.016611** against
`F_B`'s +0.016853. If the gamelog were thrown out entirely the verdict would not change.

Structural violations: **0**. Partition asserted at 8 filter-points across the three
scripts and re-asserted before every write.

---

## 3. Step 2 — the FGA forecasts and their own accuracy

Five forecasts were built. All are strictly prior-games-only (see the time-window table).

**On all player-games with ≥ 3 prior games in season (n = 15,219) — the untruncated set:**

| forecast | MAE | RMSE | R² | bias | corr |
|---|---|---|---|---|---|
| `F_LG` league mean, no player info | 4.1742 | 5.1376 | −0.00105 | −0.173 | 0.011 |
| `F_A` crude shrunk expanding mean | 2.6810 | 3.3983 | 0.56201 | +0.028 | 0.757 |
| `F_A2` EWMA_0.30 of prior FGA | 2.5734 | 3.3475 | 0.57500 | +0.008 | 0.762 |
| `F_B_nopace` per-minute × minutes | 2.5715 | 3.3203 | 0.58189 | +0.060 | 0.764 |
| **`F_B` = `F_B_nopace` × opponent pace** | **2.5670** | **3.3110** | **0.58422** | +0.064 | 0.766 |

**On the headline analysis set (n = 10,307; `realised FGA ≥ 5`):**

| forecast | MAE | RMSE | R² | bias |
|---|---|---|---|---|
| `F_LG` | 3.7239 | 5.0685 | −0.35840 | −2.607 |
| `F_A` | 2.6535 | 3.4872 | **0.35699** | −1.188 |
| `F_A2` | 2.7900 | 3.5836 | 0.32093 | −0.816 |
| `F_B_nopace` | 2.7293 | 3.5149 | 0.34671 | −0.829 |
| `F_B` | 2.7226 | 3.5018 | 0.35158 | −0.817 |

Realised FGA on that set: mean 10.303, sd 4.349.

**This is the number a reader needs.** The attempts forecast leaves an RMSE of ~3.5
attempts against a 4.35-attempt response sd. That is a large error, and it is exactly the
error that could have killed the mix signal.

Two honest notes. First, `F_A` edges `F_B` on R² *on the analysis set only*, because that
set is defined by a realised-FGA gate that truncates the low tail; on the untruncated set
`F_B` wins on every metric. Both are carried through every result. Second, the gamelog
covers regular season only, so 92.0% of player-games have joined minutes; playoff rows do
not *update* the minutes state but their own forecast is still built from prior
regular-season games, and there is a shrunk-rate fallback beneath that. Coverage is
reported, not papered over.

---

## 4. Step 3 — the decisive test, all five zones

`BASELINE: z_att ~ 1 + S1·FGAhat` vs `CANDIDATE: + FGAhat·OS`. Nothing realised on the
right-hand side. Walk-forward: coefficients refitted at every distinct game date on all
rows strictly earlier in time, MIN_TRAIN = 1000 rows, 9,290 of 10,307 RA rows scored OOS.
Plain unweighted OLS, R² = 1 − SSE/SST about the **unweighted** mean (D069).

| zone | FGAhat | wf R²(base) | wf R²(cand) | **wf ΔR²** | wf ΔMAE | pooled ΔR² |
|---|---|---|---|---|---|---|
| **Restricted Area** | `fga`* | 0.5110 | 0.5299 | +0.018905 | −0.02436 | +0.019139 |
| | `F_A` | 0.3220 | 0.3386 | +0.016611 | −0.02234 | +0.016311 |
| | **`F_B`** | 0.3135 | 0.3304 | **+0.016853** | **−0.02298** | +0.016480 |
| In The Paint (Non-RA) | `F_B` | 0.2882 | 0.2960 | +0.007740 | −0.00706 | +0.007670 |
| Mid-Range | `F_B` | 0.4186 | 0.4221 | +0.003524 | −0.00252 | +0.003464 |
| Corner 3 | `F_B` | 0.1083 | 0.1089 | +0.000610 | −0.00129 | +0.001276 |
| Above the Break 3 | `F_B` | 0.5338 | 0.5375 | +0.003760 | −0.00576 | +0.003744 |

\* DIAGNOSTIC: realised FGA. Excluded from every headline.

**Nulls, opponent-team-season level (48 clusters, 5000 draws, seed 20260807), with the
naive row-level null beside so the inflation is visible:**

| zone (`F_B`) | z | p unadj | **p 5-zone FWE** | naive row-level p | **inflation sd(correct)/sd(naive)** |
|---|---|---|---|---|---|
| Restricted Area | +19.87 | 0.0002 | **0.0002** | 0.0002 | **7.00×** |
| In The Paint (Non-RA) | +14.51 | 0.0002 | 0.0002 | 0.0002 | 4.62× |
| Mid-Range | +10.76 | 0.0002 | 0.0002 | 0.0002 | 2.57× |
| Corner 3 | +9.99 | 0.0002 | 0.0004 | 0.0018 | 1.79× |
| Above the Break 3 | +14.42 | 0.0002 | 0.0002 | 0.0002 | 3.17× |

Same permutation form as the parent: the already-computed team-season allowance values are
reshuffled across teams **within season** and re-assigned to rows; the whole five-zone
vector travels with the team, so max-t across the family is valid. Cluster-robust SEs are
not used as a substitute anywhere and are the basis of no verdict.

Here the correct null does **not** overturn anything for attempts — every zone clears
family-wise correction on both readings — but the inflation is 1.8×–7.0×, so it would have
in a weaker cell, and it does bite in step 4.

**The defective no-op placebo, run on purpose.** Permuting the grouping *key* and then
recomputing the aggregate from it is a bijective relabel: every row still receives its own
true value.

```
F_B / Restricted Area:  ref +0.0230121054  mean +0.0230121054  sd 0.000e+00  max|dev| 0.000e+00
```

Bitwise zero on all 5 zones × 2 forecasts and all 4 points cells — no LAPACK noise at all,
because the walk-forward path is a pure cumulative-sum plus a batched 3×3 solve. It tests
**nothing**. It is here so the genuine controls can be seen to be genuine by contrast.

### 4.1 Why walk-forward prints *higher* than pooled, and why that is not a gift

The headline table shows walk-forward ΔR² (+0.016853) above pooled in-sample (+0.016480),
which is the wrong direction and would be a red flag if left unexplained. It is a **row-set**
effect, not an out-of-sample effect: pooled uses all 10,307 rows, walk-forward can only
score the 9,290 after MIN_TRAIN. Held to the identical rows:

| zone | FGAhat | pooled, all rows | pooled, **same rows as wf** | walk-forward | **true OOS cost** |
|---|---|---|---|---|---|
| Restricted Area | `fga`* | +0.019139 | +0.019183 | +0.018905 | −0.000278 |
| Restricted Area | `F_A` | +0.016311 | +0.017148 | +0.016611 | −0.000538 |
| **Restricted Area** | **`F_B`** | +0.016480 | +0.017465 | +0.016853 | **−0.000611** |
| In The Paint (Non-RA) | `F_B` | +0.007670 | +0.008365 | +0.007740 | −0.000626 |
| Mid-Range | `F_B` | +0.003464 | +0.003743 | +0.003524 | −0.000219 |
| Corner 3 | `F_B` | +0.001276 | +0.000919 | +0.000610 | −0.000309 |
| Above the Break 3 | `F_B` | +0.003744 | +0.003928 | +0.003760 | −0.000168 |

The true cost of out-of-sample fitting is **negative in all 15 cells**, as it must be. The
dropped rows are early-season rows where the opponent allowance is at its noisiest and the
increment is smallest.

### The degradation curve — the direct answer to the screen's question

`FGAhat(λ) = λ·F_B + (1−λ)·F_LG`, where `F_LG` carries no player information whatsoever.

| λ | FGAhat's own R² | FGAhat MAE | rim R²(base) | **rim ΔR²** |
|---|---|---|---|---|
| 0.00 | −0.36359 | 3.742 | 0.24787 | +0.016140 |
| 0.25 | 0.00315 | 3.177 | 0.29996 | +0.017051 |
| 0.50 | 0.24538 | 2.783 | 0.32516 | **+0.017429** |
| 0.75 | 0.36310 | 2.629 | 0.32647 | +0.017314 |
| 1.00 (headline) | 0.35630 | 2.722 | 0.31351 | +0.016853 |
| realised FGA* | 1.00000 | 0.000 | 0.51103 | +0.018905 |

**The increment is essentially flat in attempts-forecast quality.** Going from a forecast
with *negative* R² to perfect knowledge of realised FGA moves ΔR² from +0.016140 to
+0.018905 — a 17% span across the entire possible range. FGA forecast error does not
swamp the mix effect because the two error sources are close to orthogonal: the mix term
redistributes a total it does not have to know. That is the finding, and it is stronger
than "it survives".

### Volume placebo — it is a mix signal, not a disguised pace signal

The identical `FGAhat·OS_rim` term applied to realised **total** attempts:

| | rim attempts ΔR² | **total attempts ΔR² (placebo)** | ratio |
|---|---|---|---|
| `F_A` | +0.016611 | **−0.000287** | −1.7% |
| `F_B` | +0.016853 | **−0.000309** | −1.8% |

If `OS_rim` were a proxy for opponent pace it would predict total attempts. It does not —
it is slightly negative. The signal moves shots *between* zones.

### Other robustness

- MIN_TRAIN ∈ {500, 1000, 2000, 4000} → ΔR² +0.016342 / +0.016853 / +0.016906 / +0.015252.
- Every forecast variant: `F_LG` +0.016140, `F_A2` +0.015702, `F_B_nopace` +0.015982.
- Pregame-defined sample gate (`F_B ≥ 5`): RA ΔR² +0.015764.
- By season (F_B, walk-forward): +0.020180 / +0.022231 / +0.014589 / +0.012758 — 4/4
  positive, declining.

---

## 5. Step 4 — does it move points? No, and the reason is arithmetic

`Σ_z OS_z = 0` to machine precision (max |·| = 1.11e-16), so the candidate term is a
**pure mix shift at constant forecast volume** — exactly the thing that should raise
expected points, because prior-only expected points per attempt differ by zone (rim
0.613×2 = 1.23; paint 0.384×2 = 0.77; mid 0.363×2 = 0.73; corner 3 0.370×3 = 1.11; ATB3
0.335×3 = 1.01).

`BASELINE: pts ~ 1 + FGAhat·Σ_z S1_z q_z v_z` vs `CANDIDATE: + FGAhat·Σ_z OS_z q_z v_z`,
with `q_z` the player's shrunk **strictly prior-games** zone conversion rate. No realised
conversion anywhere.

| target | FGAhat | wf R²(base) | **wf ΔR²** | wf ΔMAE | pooled coef | **p cluster** | p naive row |
|---|---|---|---|---|---|---|---|
| FG points (headline) | `F_A` | 0.23331 | −0.000153 | +0.00028 | +0.2205 | 0.5215 | 0.2378 |
| FG points (headline) | **`F_B`** | 0.23858 | **+0.000021** | +0.00043 | +0.5354 | **0.2150** | 0.0710 |
| total box PTS (secondary) | `F_A` | 0.29031 | +0.000289 | −0.00167 | +0.8402 | 0.3029 | 0.0160 |
| total box PTS (secondary) | `F_B` | 0.29902 | +0.000920 | −0.00536 | +1.2801 | **0.0844** | **0.0012** |

The **sign is right** everywhere and the coefficients are positive and sizeable — a
rim-ward mix shift really does raise expected points. It simply does not matter:

- 1 sd of the opponent mix signal moves the points forecast by **0.196 points**.
- The response sd is **5.82** (FG points) / **6.89** (total points).
- So even if the mix term were a **perfect and orthogonal** predictor, the arithmetic
  ceiling is **ΔR² ≤ 0.00113** (FG points) / 0.00079 (total points).

This is a **magnitude** verdict, not a power verdict. No amount of extra data rescues a
channel that is 0.2 points wide. And note the total-box row: naive p 0.0012 versus
correct-level p 0.0844, a 2.56× inflation. Reported at the correct level, it fails.

---

## 6. Step 5 — where the survivor is strongest (pre-game observables only)

Walk-forward ΔR² on rim attempts, model fitted on the full panel, evaluated inside each
bin. All splits are strictly pregame and were specified together before running.

| split | bin | n | ΔR² (`F_B`) | ΔMAE (`F_B`) |
|---|---|---|---|---|
| **\|OS_rim\| terciles** | near-average | 3025 | **+0.000050** | +0.00185 |
| | mid | 3110 | +0.002765 | −0.00718 |
| | **extreme** | 3155 | **+0.047428** | **−0.06235** |
| OS_rim signed | rim-stingy | 3153 | +0.038389 | **−0.08534** |
| | mid | 3035 | +0.000026 | +0.00349 |
| | rim-permissive | 3102 | +0.015007 | **+0.01452** |
| role_prior_fga (cuts 6, 11) | low | 2091 | +0.012903 | −0.01191 |
| | mid | 3946 | +0.018926 | −0.02470 |
| | high | 3253 | +0.017429 | −0.02800 |
| prior-minutes sd terciles | stable | 3132 | +0.010143 | −0.01734 |
| | mid | 3118 | +0.022148 | −0.02732 |
| | volatile | 3037 | +0.018578 | −0.02401 |

Correct-level nulls for the pocket (5000 draws, opponent-team-season): near-average
z = +2.69 p = 0.0012; mid z = +8.34 p = 0.0002; extreme z = +12.80 p = 0.0002.

**Reading, per GRAPH_POLICY 13.5.** The information advantage is concentrated where the
opponent's rim allowance is far from league average, and it is essentially zero when the
opponent is near average — where MAE actually gets slightly *worse*. An abstention rule on
|OS| is supported by this, and it is the operationally useful part of the result.

**Caveat, stated plainly and not buried:** a higher ΔR² in the extreme-|OS| tercile is
**partly mechanical** — the regressor has more variance there, so it must move the
forecast more. This is evidence about **where the model acts**, which is what abstention
needs. It is **not** evidence that the underlying slope is heterogeneous.

Two things worth flagging because they contradict the obvious guess, and because the
parent explicitly warned not to assume where the pocket is:

- The signal is **weaker for stable-minutes players** (+0.010143) than for
  mid/volatile-minutes players (+0.022148 / +0.018578). The opposite of what you would
  design for.
- On the signed split the increment is much larger against **rim-stingy** defences
  (ΔMAE −0.085) than against rim-permissive ones, where **MAE gets worse** (+0.015). This
  split was not preselected as a hypothesis; it is reported because it was computed.
- Role concentration is broad-based (+0.0129 / +0.0189 / +0.0174), consistent with the
  parent's finding that there is no high-usage pocket.

---

## 7. Where I could have cheated

| choice | more favourable option | what I chose | before or after seeing results |
|---|---|---|---|
| which FGA forecast is the headline | `F_A`, marginally, on the RA pooled ΔR² and on analysis-set R² | **`F_B`** | **before** — declared in `end_to_end.py`'s docstring as `headline_forecast = "F_B"` because it is the "better" forecast the task asked for. `F_A` is reported in full beside it everywhere and would change nothing. |
| pooled in-sample vs walk-forward as the headline | **walk-forward is the higher of the two** as printed (+0.016853 vs pooled +0.016480), so my headline choice flatters me and has to be explained, not left as a coincidence — see §4.1 | **walk-forward** | **before**; pooled reported beside it for like-for-like comparison with the parent. The gap is a **row-set** artifact, not an out-of-sample gift: held to the identical rows, pooled is +0.017465 and walk-forward is +0.016853, i.e. OOS fitting costs **−0.000611** as it must. |
| `K_A = 3`, `K_R = 40`, `K_Q = 20`, `PACE_CLIP = (0.85, 1.15)`, `MIN_TRAIN = 1000` | unknown — **not searched** | as listed | **before** the first run, written into `build_forecasts.py` / `end_to_end.py` docstrings. No constant was tuned and no alternative was tried. MIN_TRAIN sensitivity is reported *post hoc* and spans +0.0153 to +0.0169. |
| sample gate | keeping only the parent's realised `FGA ≥ 5` gate | kept it as the **headline** (like-for-like with the parent) **and** re-ran everything on a pregame `F_B ≥ 5` gate | gate inherited **before**; the pregame-gate rerun was added **after**, because a screen about removing realised information cannot leave a realised gate unexamined. It came out slightly *lower* (+0.015764) and is reported. |
| the points target | reporting **total box points** (+0.000920, naive p 0.0012) as the headline | **FG points** as headline, total box points as secondary, both at the correct level | **before** — FG points is the target derivable entirely from the same source as everything else. Had I led with total box points at the naive null I could have claimed a points result. At the correct level it is p 0.0844 and I am not claiming it. |
| the arithmetic ceiling calculation | omitting it | included | **after** seeing the points ΔR² ≈ 0. Added because "not significant" and "cannot possibly be big enough" are very different statements and the reader deserves the second one. |
| volume placebo / degradation curve | omitting them | included | **after** the headline. Both were added because an increment that survives a large forecast error demands an explanation; had either come out badly they would still be here. |
| step-5 splits | picking the split that looked best | four splits specified together, all four reported, plus the signed-OS split | the four **before**; the signed-OS split **after** seeing the \|OS\| result. Flagged as not preselected. |
| one-sided vs two-sided permutation | one-sided | one-sided | **before** (directional hypothesis), following the parent. |
| R² convention | the defective sqrt-weight form inflates nothing here but was never considered | plain unweighted, SST about the unweighted mean, declared | **before**, by D069. No weighting anywhere. |

Two limits that are not choices:

- With 48 opponent-team-season clusters the permutation null cannot resolve below
  p ≈ 1/5001. "p = 0.0002" means "no draw in 5000 reached it", not a point estimate.
- The gamelog has no manifest. It is used for one feature, and the whole result stands
  without it (`F_A`: +0.016611).

---

## 8. What could not be established

- **No holdout evaluation, no preregistration** — out of E1 scope. 2025/2026 was never
  opened.
- **No market comparison.** A +0.29-attempt shift and a 0.023-attempt/game MAE improvement
  have not been compared to any prop line. Exploitability is still completely untested;
  nothing here says the effect is priced or unpriced.
- **The points KILL is a magnitude finding on *this* construction.** A pipeline that also
  forecast free-throw volume, or that used the mix signal to move a *distribution* rather
  than a mean, was not built. What is established is that the mean-points channel through
  zone mix is about 0.2 points wide.
- **`q_z` is not opponent-adjusted.** The parent's separate conversion channel was not
  layered in; combining the mix channel with the conversion channel might do better on
  points and was not tried.
- **Rest, home/away, injuries, lineup, foul trouble and blowout garbage time** were not
  conditioned on anywhere. The FGA forecast reads only prior attempts, prior minutes and
  opponent prior pace — the specific mechanisms the task named as sources of attempts
  error are represented only through their effect on those histories.
- **Why the attempts increment is so nearly orthogonal to volume error** is demonstrated
  (the degradation curve) but not explained mechanistically.

---

## 9. Verdicts

| target | verdict |
|---|---|
| Reproduction of the parent's conditional +0.019138861495123338 | **EXACT**, 0.000e+00, from the frozen frame and from an independent raw rebuild |
| Shot-mix signal on **zone attempt counts**, no realised FGA anywhere | **KEEP-AS-LEAD** — wf ΔR² **+0.016853** (RA, `F_B`), 88.1% of the conditional increment retained, family-wise p **0.0002** at the opponent-team-season level, MAE −0.023 rim attempts/game, all five zones positive, 4/4 seasons positive |
| Shot-mix signal on **player points** | **KILL** — wf ΔR² +0.000021 on FG points at cluster-level p 0.2150; +0.000920 on total box points at cluster-level p 0.0844 (naive row-level p 0.0012 — a 2.56× inflation). Arithmetic ceiling ΔR² ≤ 0.00113. |
| The worry that FGA forecast error swamps the mix effect | **DISCONFIRMED** — the increment is flat in forecast quality across the entire achievable range (+0.01614 at forecast R² −0.36 → +0.01891 at perfect knowledge) |
| The signal being a disguised pace/volume effect | **DISCONFIRMED** — volume placebo −0.000309 vs +0.016853 |
| Abstention pocket | **SUPPORTED** — ΔR² +0.047 in the extreme-\|OS\| tercile vs +0.000 near average; partly mechanical, which is fine for an abstention rule and not fine as a heterogeneity claim |
| **OVERALL** | **SPLIT** — attempts yes, points no |

The lead to carry forward is: **an opponent-conditioned shot-mix forecast improves zone
attempt-count forecasts by ΔR² ≈ +0.017 out of sample with nothing realised anywhere, and
this is genuinely a forecasting increment, not a conditional one. It does not improve a
points forecast and, on this construction, cannot.**
