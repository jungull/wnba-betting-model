# STAGE2A_PHASE0A_RESOLUTION_v1

Read-only. No model fitted, no arm registered, no challenger performance calculated, no canonical
artifact regenerated. The original `EVIDENCE_PACKET.json` (`f373e3ee…`), `GENERATION_ORDER.json`,
the six hypothesis sets and `PACKET_ADDENDUM_coordinator.md` are **immutable and untouched**.

---

## 1. Repository scope, `db66a720..d1e783d`

Live at 2026-08-04T18:40:24Z: branch `player-model-program`, HEAD `d1e783d`, **clean**.

**One commit in range.**

| commit | author | subject |
|---|---|---|
| `d1e783d` | John Gallagher `<jgallagher@sasscpas.com>` | Stage 2A: frozen evidence packet, six independent hypothesis sets, synthesis |

**12 files, all `A` (added), all under `experiments/player_program/stage2a/`, 5,490 insertions,
0 deletions, 0 modifications.**

```
A  stage2a/EVIDENCE_PACKET.json                 593
A  stage2a/EVIDENCE_PACKET.sha256                 1
A  stage2a/GENERATION_ORDER.json                103
A  stage2a/HYPOTHESES_agent_adversarial.md      744
A  stage2a/HYPOTHESES_agent_opponent_env.md     533
A  stage2a/HYPOTHESES_agent_pace_coaching.md   1056
A  stage2a/HYPOTHESES_agent_roster_coldstart.md 721
A  stage2a/HYPOTHESES_agent_timeseries.md       730
A  stage2a/HYPOTHESES_coordinator.md            191
A  stage2a/PACKET_ADDENDUM_coordinator.md       291
A  stage2a/SYNTHESIS.md                         176
A  stage2a/build_evidence_packet.py             351
```

**Confirmed:** no shared contract, canonical artifact, Arm D artifact, registry record or prior
scientific result appears in the range.

---

## 2. Possession-unit lineage, source to consumer

| field | producer | semantic unit | raw / reg-equiv | overtime treatment | pregame? | consumer | transformation between |
|---|---|---|---|---|---|---|---|
| `duration_sec`, `period`, `offense_team_id` | `possessions_raw_v2.parquet` | possession events | **raw** | full game, all periods | **postgame** | `build_pace` | none |
| `n_off_poss` | `build_pace` (in-memory) | count per team-game | **raw** | includes OT possessions | postgame | `reg_equiv_off_poss` | none |
| `game_minutes` | `build_pace` | minutes | — | `40 + 5*max(0, max_period-4)` | **postgame** — derived from realised `max_period` | `reg_equiv_off_poss` | none |
| `reg_equiv_off_poss` | `build_pace` | count normalised to 40 min | **regulation-equivalent** | **removed by scaling** | postgame | `game_pace` | `n_off_poss * 40 / game_minutes` |
| `game_pace` | `build_pace` | count per game | **regulation-equivalent** | removed | postgame | trailing window | mean of the two sides |
| `team_pace_estimate` | `team_possession_prior_v1` | count | **regulation-equivalent** | inherited | **pregame** (lagged only) | `projected_team_off_possessions` | mean of last ≤10 strictly-earlier `game_pace` |
| `projected_team_off_possessions` | `team_possession_prior_v1` | count | **regulation-equivalent** | inherited | **pregame** | Arm D operational track; player exposure | mean of the two sides' estimates |
| `projected_off_possessions` | `projected_player_possessions_v1` (`build_projected_exposure.py:505`) | count per player | **regulation-equivalent** | inherited | **pregame** | Arm D operational player exposure | minutes-weighted allocation of the team prior |
| `team_off_possessions` | `team_turnover_reconciliation_v1` | count per team-game | **RAW** (int64, equals `n_off_poss` on 2990/2990) | **includes OT** | postgame | Arm D **intrinsic** track exposure; companion rate denominator | none |
| `player_attributed` / `turnovers` | `player_turnover_targets_v1` | event count | **raw count over the full game** | **includes OT** | postgame | Arm D **target** `y_team` | none |

**The consumer split, `run_turnover_p1_universe_fix.py:149`:**

```python
expo_t = g["team_off_possessions"] if name == "intrinsic" else g["projected_team_off_possessions"]
```

* **intrinsic** track: RAW exposure vs RAW target — internally consistent.
* **operational** track: **REGULATION-EQUIVALENT exposure vs RAW full-game target** — inconsistent
  on overtime games.

Measured consequence:

| stratum | n | raw team possessions | reg-equiv projection | ratio | mean `player_attributed` |
|---|---|---|---|---|---|
| non-OT | 2,849 | 79.305 | 79.445 | 0.998 | 13.065 |
| **OT** | **132** | **89.962** | **79.447** | **1.132** | **14.530** |

On overtime games the operational track applies a 40-minute exposure to a turnover count
accumulated over 45+ minutes: a **structural ~13% exposure shortfall**, and OT games genuinely
carry more turnovers (14.53 vs 13.07).

### The prohibited-versus-permitted line

* `game_minutes` is derived from the realised `max_period`. Using it — or any function of it,
  including a rescaling by realised game length — as a **predictive feature** is **PROHIBITED**:
  it is an exact overtime indicator and therefore target leakage.
* Using realised duration **solely to construct or normalise the historical outcome target** is a
  different act. The incumbent already does exactly this, inside `build_pace`, to define
  `game_pace` over strictly earlier games. That use is retrospective, applies only to completed
  games, and never touches the target game.

The distinction is real and must be stated in any task card: **normalising history is permitted;
predicting with realised duration is not.**

### Adjudication — RETURNED FOR COORDINATOR RULING

The governing artifacts **do not establish one authoritative unit** for the operational track.
They establish two, and never reconcile them:

* `turnover_target_contract_v1` defines the target as realised turnovers over the **full game**.
* the exposure contract defines projected possessions as **regulation-equivalent**.

Neither registry record adjudicates the operational pairing. Per the stop rule I am **not**
selecting one, and I am explicitly **not** selecting on which produces better results.

The four candidate rulings, stated neutrally:

1. **Raw full-game possessions.** Target unit becomes raw; the projection must then predict
   expected full-game possessions, which requires an OT-probability term. Pregame-legitimate only
   if that term uses no realised duration.
2. **Regulation-equivalent possessions.** The target must then be normalised to 40 minutes as
   well, i.e. `player_attributed * 40 / game_minutes`. This changes the canonical target's
   definition and is therefore **out of scope** without a separate ruling — it would regenerate a
   canonical quantity.
3. **Expected raw possessions incorporating only pregame-available OT probability.** Consistent
   with both artifacts and leakage-free, but introduces a new estimated quantity (~4.4% base rate)
   that is itself a modelling decision.
4. **Declare the operational track's current pairing a known, bounded approximation**, quantify it
   (132 of 2,982 rows, ~13% exposure shortfall on those rows), and require every arm to report the
   OT subset separately.

**Recommendation for the ruling, not a decision:** option 3 or 4. Option 2 is out of scope. I
note that whichever is chosen, it must be fixed **before** any arm runs, since it changes what the
decision metric means.

---

## 3. Dependence and inference specification

Describing the sample as "n = 1,491" is wrong; so is "n = 2,982". The correct statement:

* **2,982 team-game rows** — the analysis units.
* **1,491 game clusters** — the independent projection units. Every game's two team-rows share
  one **identical** `projected_team_off_possessions` (verified 1495/1495 games, zero games with
  two distinct values).
* **Within-game target dependence:** the two sides' realised regulation-equivalent counts differ
  by mean 0.880 (sd 0.779); between-game variance is 14.988 against a within-game half-spread
  variance of 0.152. **97.78%** of team-game target variance is game-level.
* **Within-game residual dependence:** because the projection is identical across the pair, the
  two residuals differ only by the within-game spread — they are near-perfectly correlated.

**Estimand.** The population mean absolute error of the downstream operational turnover-team
prediction over the contract's team-game universe, and its paired difference against a matched
control on identical rows.

**Row weighting.** Equal weight per team-game row. Each game therefore contributes weight 2. No
inverse-variance or support weighting — that would silently reweight toward the strata whose
support definition the addendum shows to be broken.

**Fold construction.** Chronological, nested, by season, as the incumbent's own walk-forward:
train strictly earlier, evaluate on the held-out season. **A game is never split across folds** —
both team-rows of a game always fall in the same fold.

**Interval method.** Game-clustered bootstrap: resample the **1,491 game clusters** with
replacement, carrying **both team-rows of a sampled game together**, recompute the paired
statistic per replicate, and take percentile intervals. Never resample team-rows independently.
Report the clustered interval alongside the naive one so the ≈√2 inflation is visible rather than
implicit.

**Shared rows and weights.** K0, the frozen incumbent and every challenger must be evaluated on
**byte-identical row sets** with identical weights, verified by the row-identity digest already
implemented in `gate_invocation.binding_fields`. Any row droppable by one arm must be dropped by
all, before scoring.

**No model fitting is authorized and none was performed.**
