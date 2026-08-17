# NOTES — E1_I0053_minutes

`PREREG.md` sha256 `ac373cc884166e263ddfae43466932de430d0f046966c5d918dc3c3853a1168d`, 20,518 bytes.
Read `VERDICT.md` first, `REFERENCE.md` and `CEILING.md` for the two pre-fit results, `DEFECTS.md`
for what went wrong.

---

## 1. RUN ORDER, AND WHAT EACH STEP MAY LOOK AT

| step | what it does | may it see a candidate-to-response relationship? |
|---|---|---|
| `s00_probe.py` | coverage, sd, **measured variance level of each candidate**, block counts, budget tightness | **NO** — candidate side and row counts only |
| **`PREREG.md` written and hashed** | | |
| `s01_anchors.py` | 39 anchors, run halts on failure | only published numbers from frozen screens |
| `s02_reference.py` | tunes the reference, publishes what the tuning alone is worth | response and base only, **no candidate** |
| `s03_ceiling.py` | the arithmetic ceiling, `c*`, matched controls, family joint | yes, but **no fit is scored** — this is the pre-fit gate |
| **`CEILING.md` written** | | before `s04_primary.py` existed |
| `s04_primary.py` | 84 cells, both arms, matched nulls, bootstrap | yes |
| `s05_controls.py` | injection, null-centre, blind null, type-I, placebos, leakage | yes |
| `s06_budget.py` | *(added after the hash)* the budget decomposition | yes |
| `s07_robustness.py` | *(added after the hash)* variants of the only survivor | yes |
| `s08_findings.py` | *(added after the hash)* floors, concentration, `FINDINGS.json` | assembly only |

**Nothing outside `experiments/exploration/E1_I0053_minutes/` was written.** The shared screen kit
was read for its documented traps and **not imported and not modified**; `E1_I0046/scripts/al_base.py`
and `E1_I0046/scripts/s02_stability_reference_ceiling.py` were read read-only and are credited in
the source where their construction is followed.

## 2. ADDED AFTER THE HASH — three items, with direction

| item | direction |
|---|---|
| `s06_budget.py` — the four-arm projection decomposition | answers a **new** question posed by the coordinator; its answer (the pre-game-available portion is zero) weakens a result from another screen, not one of this screen's own |
| `s07_robustness.py` — eight variants of `C1_player_rest` | **can only weaken**, and it did: it is why `VERDICT.md` reports the survivor as a return-from-absence effect rather than the rest effect it was preregistered as |
| `s08_findings.py` — floor assembly, concentration counts | bookkeeping; the injection floor it publishes (**0.004760** conservative) is **larger** than the linear-interpolation reading (0.001863), so the bar the survivor is held to went **up** |

**Nothing was dropped.** All 10 preregistered candidates, both responses, both arms, all four grids
and all four nulls were run and are reported.

## 3. TIME-WINDOW TABLE — every constructed column, and exactly what it reads

Trap 2 requires this to be declared rather than inferred from a name. `.shift(1)` below always means
inside `(season, player_id)` for player columns and `(season, team_id)` for team columns, with rows
ordered by `game_date` then `game_id`.

| column | reads | window |
|---|---|---|
| `R1_min`, `R2_smin` | the game being forecast | **the response** |
| `T_min`, `n_roster` | the game being forecast | **ORACLE** — used only by the PROJ arms and by `R2_smin`'s denominator; declared in `DEFECTS.md` D-01 |
| `n_prior` | count of this player's earlier appearances this season | strictly prior |
| `prior5_minutes`, `prior5_sd_minutes` | `.shift(1).rolling(5)` of own minutes | strictly prior |
| `PR__*__h*` | `.shift(1).ewm(halflife=h)` of own response | strictly prior |
| `n_hat` | `.shift(1).expanding()` mean of the team's roster size | strictly prior |
| `B_TUNED` | `PR__*__h3` shrunk toward `200 / n_hat` | strictly prior; **200 is the rulebook, not the realised total** |
| `C1_player_rest` | `game_date` − this player's **own previous appearance date**, clipped at 21 | strictly prior |
| `C2_foul_rate` | `.shift(1).ewm(halflife=5)` of own fouls per 36 minutes | strictly prior |
| `C3_blowout_adj` | `.shift(1).expanding()` mean of own minutes in prior **non-blowout** games minus the same over all prior games; blowout = the **prior** game's realised \|margin\| ≥ 15 | strictly prior |
| `C4_min_volatility` | `.shift(1).rolling(5).std()` of own minutes | strictly prior |
| `C5_starter_delta` | `.shift(1).rolling(3)` start rate − `.shift(1).expanding()` start rate | strictly prior |
| `C6_team_rest` | `game_date` − the team's previous game date, clipped at 21 | strictly prior |
| `C7_sched_density` | count of the team's games in the **strictly prior** 7 calendar days | strictly prior |
| `C8_opp_pace_prior` | opponent's `.shift(1).expanding()` mean of `fga + 0.44·fta − oreb + tov` | strictly prior |
| `G01_noise`, `G02_tg_noise` | `default_rng(20260808)` | reads nothing |

The leakage probe (`LEAKAGE_PROBE.csv`) correlates every one of these with the player's own
**strictly-after-date** future mean minutes. The survivor sits at −0.0697; the base at +0.5816;
the largest candidate magnitude is 0.2703. **No flags.**

## 4. WHAT THIS SCREEN CONTRIBUTES THAT NO EARLIER ONE DID

1. **A dedicated minutes screen on the decision stratum.** Every prior minutes result was a
   by-product of a screen aimed at points, shares or absence.
2. **A LEVEL response, so that team-game-constant candidates get a fair test.** `E1_I0046` disposed
   of rest, pace, venue and travel on *arithmetic* — they cannot move a share. On a level they can,
   and here they were given the chance and did nothing: `C6_team_rest` −0.000237 (p 0.5182),
   `C7_sched_density` +0.000810 (p 0.2074), `C8_opp_pace_prior` −0.001882 (p 0.9855).
3. **The tuning value on minutes**: +0.016456 over an untuned EWMA, +0.050624 over the trailing-5
   mean, against a best candidate of +0.006644.
4. **The budget/roster decomposition of the projection gain** — the projection is worth −0.000061
   (p 0.9970) on regulation-time team-games. All of its apparent value is overtime.
5. **A localisation of the absence channel.** `E1_I0034`/D116 found the absence channel real for
   minutes; this screen finds *where*: 120 of 3,167 decision-stratum rows, a step at eight days,
   about four minutes, and nothing at all between one and seven days.

## 5. RELATIONSHIP TO SIBLING AND PRIOR SCREENS

* **`E1_I0051_constraint_sweep`** ran concurrently on the same response and stratum and deferred to
  this screen. Its budget-tightness result is **confirmed** here on this screen's own frame (1,776
  of 1,776 team-games within 0.066667 of a multiple of 25). **One correction:** summed from the
  player box, the total is *exactly* 200.000000 in **81.02 %** of team-games; the **95.27 %** figure
  is the fraction within 0.07 of 200, i.e. a tolerance band, not exact equality. And its
  **+0.020020 projection gain is shown here to be an overtime oracle**, worth −0.000061 at p 0.9970
  once overtime team-games are excluded.
* **`E1_I0046_allocation`**'s minutes-share reference is reproduced here **bit-exactly** (anchors
  A5*, |Δ| = 0 on tuned, naive and uniform R² for eval 2022, 2023 and 2024, on the selected
  halflife and shrinkage, on the training SSE and on all row counts). That is the check that this
  screen's independent reimplementation is faithful.
* **`E1_I0042_redistribution_replication`.** The brief that commissioned this screen states that the
  minutes result "survives an intercept freeze and GROWS (+1.774 %, p 0.0030)". It does survive the
  freeze. **Its own `HEADLINE_WITH_FLOORS.csv` records `verdict_vs_carried =
  BELOW_FLOOR_NOT_ESTABLISHED` and `effect_over_injection_floor = 0.5547` on that row.** The
  brief's characterisation is stronger than the artifact supports, and this screen's own finding —
  small, concentrated, and clearing its conservative floor by 1.40× — is consistent with that.
* **`E1_I0049_benchmark_constants`**'s reference card was used in place of remembered constants, and
  its central ruling applies directly: **none of the programme's published floors is on this
  screen's response.** All comparisons to them are `NOT_COMPARABLE` under D101 and none is made.
* **The possessions correction** the coordinator issued (D111's "identical in 970 of 970 games" is
  about *minutes*, not possessions; the box possessions estimator differs by a mean of 2.28 with
  exact equality in 0.45 % of 888 games) does not touch anything here — **this screen makes no
  possessions argument** and its shared-pool reasoning is about the minutes budget only, which is
  the version that survives.

## 6. REPRODUCING

```
python scripts\s00_probe.py       > out\s00.txt      # ~40 s   writes scripts\_frame.parquet
python scripts\s01_anchors.py     > out\s01.txt      # ~60 s   HALTS on any anchor failure
python scripts\s02_reference.py   > out\s02.txt      # ~90 s   writes scripts\_base.npz
python scripts\s03_ceiling.py     > out\s03.txt      # ~5 min
python scripts\s04_primary.py     > out\s04.txt      # ~12 min  84 cells, ~250 npz
python scripts\s05_controls.py    > out\s05.txt      # ~20 min
python scripts\s06_budget.py      > out\s06.txt      # ~3 min
python scripts\s07_robustness.py  > out\s07.txt      # ~4 min
python scripts\s08_findings.py    > out\s08.txt      # ~5 s    writes FINDINGS.json
```

Seed `20260808` throughout. Standard library, numpy and pandas only — **scipy is not installed in
this environment and is not imported.** Two python processes were launched by this screen
(`s05`/`s06` briefly ran concurrently, and `s07` alongside nothing); **no process not launched by
this screen was signalled, and no blanket process kill of any kind was issued.**

## 7. STORAGE

`nulls/` holds one `.npz` per cell per null, plus the bootstrap draws, the robustness variants, the
blind-null demonstration, the response placebo, the type-I `z` vector and the reference contrasts.
Every payload carries **raw, unstandardised, signed draws** together with the observed signed
statistic, the null mean and sd, the group and block counts, and the full stratum key (response,
projection, arm, candidate, stratum, window, row count, scored block count) — in the filename **and**
in the payload. Standardising erases the null mean irrecoverably, which is why 117 cells elsewhere
in this programme are permanently unauditable; nothing here is stored that way.
