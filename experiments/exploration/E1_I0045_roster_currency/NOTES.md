# NOTES — E1_I0045_roster_currency

Technical log. The plain-language documents are `UNIVERSE_CONSTRUCTION.md`, `CURRENCY_RULE.md`,
`REACH.md`. This file records what was run, in what order, and the working behind numbers that are
quoted elsewhere without it.

Seed 20260811. Partition 2021–2024; 2025/2026 never enumerated.
**No change enacted anywhere.**

---

## 1. Order of operations

| step | script | what |
|---|---|---|
| 1 | — | read E1_I0035 in full (`DEFECT_ANATOMY.md`, `REPAIR_OPTIONS.md`, `PREREG.md`, `av_base.py`, `s02`, `s04`) |
| 2 | — | read `prediction_contract_v5.py` and `audit_roster_sources.py` end to end |
| 3 | `s01_build_and_anchor.py` | frames + **ten anchors** + currency features |
| 4 | `s02_universe.py` | re-execute S1/S2 over `master_player`; population characterisation |
| 5 | — | **`PREREG.md` written and hashed** (see its §0 for the honest provenance) |
| 6 | `s03_currency.py` | Xa reproduced, then the Y/Z arms; nulls; injection power; frozen intercept |
| 7 | `s04_coverage_and_exposure.py` | named coverage cost; exposure shape (**anchor 8.912455**) |
| 8 | `s05_stratify_not_remove.py` | **POST HOC** `Xa+`; per-comparison injection floors; head-to-head |
| 9 | `s06_resolve_floors.py` | re-sweep the tier-B floors s05's grid never reached (`DEFECTS.md` D-1) |

`rc_base.py` is an independent reimplementation. **Nothing is imported from E1_I0035's `av_base`**,
so the anchor reproductions are an independent path rather than a re-execution. Consequence: I never
wrote to E1_I0035's directory, not even a `__pycache__` mtime.

---

## 2. The anchors (§ s01, s03, s04)

Ten in `ANCHOR_REPRODUCTION.csv`, plus Xa's five headlines in `_s03.json`, plus the exposure anchor.
The five that landed to six decimals or better:

| quantity | mine | published | abs diff |
|---|---:|---:|---:|
| D076 appeared player-games (tier A, 2022–24) | 13,879 | 13,879 | 0 |
| B1 bottom-up team MAE | 18.263037 | 18.263037 | **0.000000** |
| top-down team MAE | 8.685506 | 8.685506 | **0.000000** |
| RS1 SST | 168 710.4073 | 168 710.4073 | 0.0000 |
| exposure misallocation, X0 | 8.912455 | 8.912455 | **0.000000** |

The other five (universe rows/team-game, realised roster, Σ`p_active`, level bias, the four player
metrics) land within 5e-5 to 4.8e-5, all inside their declared tolerances. Xa's own reproduction:
team MAE 10.957277 vs 10.957, Brier 0.094677 vs 0.0947, tier-A 0.093349 vs 0.0933, AUC 0.928452 vs
0.9285, Σw 9.560942 vs 9.561. **`s03` halts if any of these misses.**

Identity map: reconstructed from `cbs_obligation_key/1` over 1,940 team-games × 268 players =
519,920 triples; agrees with the manifest-verified contract v4 on **22,659 of 22,659** rows on all
three fields. 40 champion rows (0.15 %) do not resolve and are dropped and reported — same 40
E1_I0035 found, still unexplained (`DEFECTS.md` D-4). None is inside RS1P.

---

## 3. The universe reconstruction (§ s02)

Constants read out of `prediction_contract_v5.py` **by AST**, not transcribed:
`ROSTER_LOOKBACK = 5`, `S2_HORIZON = 5`, `S_TX_HORIZON = 3`, `REPORT_ERA_START = 2026-07-30`.

**S3 is asserted dead in this partition**, not assumed: latest `forecast_cutoff` is 2024-09-18,
`REPORT_ERA_START` is 2026-07-30. Tier A here is S1 and nothing else.

**The cross-check that licenses everything downstream:** re-executing S1 (box membership including
DNP rows, in the club's latest ≤5 admitted prior same-season games, admitted at `game_date + 36 h <
cutoff`) over `master_player` reproduces contract-v4 membership on **20,084 of 20,084 rows, zero
disagreements in either direction.** So my source attribution rests on a manifest-verified artifact
and a rule I re-ran, not on the unverifiable v5 parquet.

Tier-B composition (`tier_b_by_admitting_source.csv`): 3,266 of 3,772 (86.6 %) admitted by S2,
506 by neither S1 nor S2 (⇒ S_TX). 98.5 % of tier-B rows sit at `team_game_index` 0–4.

For colour only, and labelled UNVERIFIABLE everywhere it appears: v5's own `team_assignment_source`
puts 2,222 tier-B rows on S2 and 1,550 on S_TX. The gap against my 3,266 is precedence — v5 labels a
row S_TX when both sources fire, and 1,044 of its S_TX rows also satisfy S2. Those rows would still
be in the universe if S_TX did not exist, which is why my S2-scoped rules act on them and v5's label
does not contradict that. **No number in any document rests on this paragraph.**

---

## 4. Currency features (§ s01 §7)

18,212 admitted appearance records (`minutes > 0`, 2021–24). Per-player and per-(player, team)
sorted `avail` arrays; `searchsorted(..., side="left")` against each row's own `forecast_cutoff`,
which is a strict `<` because `avail` values equal to the cutoff sort to the right of the insertion
point. Features on 26,574 champion rows:

* never played for this club (admitted): 1,214 (4.57 %)
* never played anywhere: 619 (2.33 %)
* `departed`: 2,139 (8.05 %)
* `seasons_since_club`: {0: 21,906, 1: 2,022, 2: 997, 3: 435, never: 1,214}

`trail5_min` is the mean minutes over the last ≤5 admitted same-season appearances; `n_prior_app_season`
is the count of admitted same-season appearances. Together they reproduce E1_I0004's registered
decision stratum (`>=8 prior, trail5 min >=24`), which selects 4,964 of 20,084 RS1P rows.

---

## 5. Scoring convention, and why it satisfies D101

A row a rule removes **keeps its row and takes `w = 0`**. This is E1_I0035's Xc convention exactly.
Consequences worth stating because they are easy to get wrong:

* every arm is scored on the identical 1,392 team-games and 20,084 player rows, same response, same
  SST, no weighting, no base — so D101 holds and no arm is flattered by a smaller denominator;
* Brier on a removed row is `(0 − appeared)²`, which is 0 when she did not play and **1** when she
  did. Removal is therefore charged its full penalty inside the metric, and *additionally* charged
  by name in `COVERAGE_COST.csv`. It is not charged twice in the same number;
* log-loss on a removed appeared row is `−log(ε)` ≈ 13.8, which is why R4's log-loss explodes to
  0.494 from Xa's 0.314 while its Brier looks nearly fine. **Log-loss is the metric that sees
  over-removal; Brier barely does.** Anyone reading only Brier would miss R4's damage.

---

## 6. The Z arms' training pools

For `Z_R*`, the walk-forward recalibration's training pool excludes rows the *same rule* would have
removed in the earlier seasons. Otherwise the fit would be trained on a population the arm never
scores. `walkforward_recalibration_fits.csv` carries every fit; the 2022 fold's two *fitted* strata
are empty for every arm (2021 emits nothing but the declared constant), so 5,135 of the 2022 rows go
through unrecalibrated. That is E1_I0035's finding reproduced, it makes the full-window results
**worse** than they would otherwise be, and it is the reason the clean window is the headline.

Because `stale` is false on every tier-A row by construction, the tier-A strata and their fits are
byte-identical between Xa, Xa+ and every Z arm. **The tier-A Δ Brier of exactly 0.000000 is
structural, not a null result.**

---

## 7. Power

Two kinds, always labelled.

**Analytic (sign-flip MDE80 = 2.8016 × null_sd)** — printed beside every p, never carries a verdict.
**Injection-verified** — computed from *that comparison's own* centred per-row loss difference, 200
replicates, 2,000 draws each. **This is the floor that carries the verdict**, per the brief.

They disagree, and the disagreement matters. Z_R3 vs Xa on the clean window: sign-flip MDE80 0.470
against an effect of 0.438 (fail), injection floor 0.60 (fail — worse). Xa+ vs Xa: MDE80 0.455
against 0.471 (pass), injection floor 0.40 (pass). And in `s03` I used a *mismatched* noise vector
(Y_R1-vs-Xa) for the team sweep, which produced a floor of ~1.15 and would have failed everything.
**A floor built from the wrong comparison's noise is not conservative, it is wrong.** `s05` computes
one floor per comparison and those are the numbers quoted.

Block counts: team-season 36 (full) / 24 (clean); player-season 725 / 512, tier A 488 / 320, tier B
709 / 508, decision stratum 254 / 171. All above the six-block floor.

Type-I: 0.0675 at nominal 0.05 over 400 synthetic no-effect datasets, p quartiles 0.253 / 0.530 /
0.776. Mildly anticonservative; recorded, and no verdict rests on p alone.

---

## 8. The frozen-intercept result, stated once more because it is the most important thing here

*Team.* Rescale each arm's per-team-game Σ`w` to Xa's and the clean-window MAEs become X0 10.324,
Xa 10.386, Xa+ 10.395, Z_R3 10.395. **The unrepaired champion wins.** Every team-level number in
this screen — and Xa's own +9.53 over X0 — is shared-level movement. E1_I0035 proved that a uniform
per-team-game rescaling cancels **exactly** in the only downstream consumer (its Xb changed the
allocation by 0.000000 minutes). The same argument voids the team-level column here.

*Player.* One global walk-forward intercept-only recalibration on every arm. Full window: X0
0.13025 → 0.12367, Xa 0.09468 → 0.09398, Z_R3 0.09035 → 0.09038. The Z_R3-over-Xa gap is 0.0036
frozen against 0.0043 unfrozen — **84 % of it survives.** The player-level gain is shape.

That asymmetry is the whole result: **the same repair is a level artefact at the team level and a
genuine shape improvement at the player level.** A screen that reported only one of the two would
have been wrong in one direction or the other.

---

## 9. Things I checked that produced nothing worth a section

* Whether the recency threshold has an interior optimum — it does not; `recency_tau_curve.csv` is
  flat from τ = 7 to τ = 200 (the same 3,266 rows) and steps at the season boundary. The signal is
  discrete.
* Whether R1 and R2 are redundant — they are not: R1 keeps Brittney Griner (no other club), R2 keeps
  the 1,489-row departed set only insofar as it is also stale. Their union R3 is the better arm and
  their intersection is uninteresting.
* Whether tier-A departed rows should be removed — no. 248 rows, appearance rate 0.145, already
  priced at 0.212. R4 measures the cost of doing it anyway: 151 false removals and a tier-B AUC
  collapse from 0.772 to 0.688.
