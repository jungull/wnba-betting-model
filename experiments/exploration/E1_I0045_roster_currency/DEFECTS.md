# Defects found by, and in, E1_I0045_roster_currency

---

## D-1 — MY OWN HARNESS: an unreached injection grid was reported as a failed test

**Where.** `scripts/s05_stratify_not_remove.py`, the per-comparison injection floor.

**What happened.** The floor is found as `min([e for e, v in sweep.items() if v >= 0.80],
default=None)`. On tier B the per-row Brier difference is roughly an order of magnitude more
dispersed than on tier A, so **no** value on the swept grid (max 0.002) reached 80 % power and the
function returned `None`. The verdict rule then read `floor is None` as *"below the injection
floor"* and printed **NOT ESTABLISHED** for an effect of **+0.0169** — eight times the largest value
ever tested.

**Why it matters.** This is the failure mode that looks like conservatism and is not. It converts
"I did not measure the floor" into "the effect is too small", and it does so on the row set where
the effect is largest. Had the tier-B cells been the headline, the screen would have reported the
opposite of the truth about its own arm.

**Fixed** in `scripts/s06_resolve_floors.py`, which re-sweeps tier B on a grid extending to 0.032.
**No verdict from s05's tier-B cells is carried forward**; `tierB_resolved_floors.csv` replaces
them. The tier-A and pooled cells are unaffected — their grids were reached.

**Generalisable lesson for the programme.** An injection sweep that never reaches 80 % power must
report *"floor not reached on the tested grid"*, which is a different statement from *"the effect is
below the floor"*, and a verdict function must not collapse the two. E1_I0035's DEFECTS.md D-1
recorded the mirror-image bug (a degenerate injection that reported 1.000 at every effect size).
**Both are failures to make the power calculation say what it actually measured.**

---

## D-2 — THE SHIPPED ROSTER HAS THE SAME ROSTER-CURRENCY DEFECT, IN AN INDEPENDENT COPY

**Where.** `daily_forecast.py:647-665`, on the critical scheduled path
(`WNBA_DailyForecast_AM` / `_PM`).

**What it does.**

```python
        recent = set(tgames[-RECENCY_GAMES:])
        roster = tp[tp.game_id.isin(recent)].player_name.unique()
```

`RECENCY_GAMES = 3`. This is the contract's S1 rule with a three-game window instead of five, and
it is the *entire* roster construction — the only subsequent filter is the injury feed's `Out`
designation (`:690-691`).

**The defect.** It has **no departure check**. A player who was traded yesterday appeared in her old
club's box score within the last three games and is therefore on that club's shipped roster for
three more games. It also has no release check and no transaction input of any kind.

**Severity.** Lower than the contract's, because the window is three games rather than "any prior
season, forever", so it self-corrects within about a week. But unlike the contract's version **this
one is in shipped output**: `forecasts/forecast_log.jsonl` carries per-player `out_home` /
`out_away` / `n_roster` fields written from this list, and the promoted minutes-EWMA component
(`daily_forecast.py:112`, `experiments/registry.jsonl` `promote: true`) is applied to it.

**Two further hazards in the same lines.**
* It keys on **`player_name`**, not `player_id`. This programme has lost six findings to name-based
  matching. Any repair ported from this screen — whose features are all `player_id`-based — needs an
  entity-resolution step first.
* It is a **completely separate code path from the contract.** Repairing
  `prediction_contract_v5.py` would not change one line of shipped output. Anyone who reads
  E1_I0035's "the defect does not reach production" and concludes the shipped roster is therefore
  current will be wrong.

**Not measured here.** This screen's partition and row sets are the contract's. Quantifying D-2
needs its own screen against the shipped log. **Nothing was changed.**

---

## D-3 — S2 STAMPS AN EVIDENCE TIME THAT CARRIES NO EVIDENCE

**Where.** `prediction_contract_v5.py:459`.

```python
                        e["times"]["S2"] = pd.Timestamp(f"{season}-01-01T00:00:00Z")
```

Every S2 row's `candidate_evidence_time` is 1 January of the season being forecast, regardless of
whether the player last played for that club four months ago or four years ago. The contract's own
comment is honest about why ("the last admitted game of the prior season is not tracked per row, so
the season boundary is used and labelled as such"), and the value is cutoff-safe, so this is not a
leakage defect.

**But it is an information defect.** The single field that a downstream consumer would naturally
reach for to judge how stale a candidacy is has had the staleness deliberately removed from it. The
recency that `seasons_since_club` recovers — separating a 0.109 appearance rate from a 0.003 one —
was available at row-construction time and was discarded. Any consumer trusting
`candidate_evidence_time` as a recency measure is being misled by a field that is nonetheless
correct as declared.

**Cheapest possible repair, and it is not a model change:** stamp the *actual* last admitted
appearance date for that club. It is already computed inside `build_candidates`' neighbourhood, it
changes no row and no probability, and it would let any consumer implement a currency rule without
this screen's machinery. **Not enacted — it is still a contract change and therefore the user's.**

---

## D-4 — 40 CHAMPION ROWS CANNOT BE RESOLVED TO A PLAYER-GAME-TEAM TRIPLE

**Where.** `s01_build_and_anchor.py` §3, reproducing E1_I0035's identical count.

40 of the champion arm's 26,614 rows (0.15 %) carry a `row_uid` that does not appear in the identity
map reconstructed from `cbs_obligation_key/1` over (every team-game) × (every player in the
partition). They are dropped and reported. None falls inside RS1P — after the RS1 restriction the
count is 20,084 exactly, matching E1_I0035 — so no number here is affected.

**It is still unexplained.** The map is a full cross product, so an unresolvable `row_uid` means a
player_id or game_id the masters do not contain. E1_I0035 reported the same 40 and also did not
explain them. **Two screens have now stepped over this; it should be explained rather than reported
a third time.**

---

## Not defects, recorded so a later reader does not re-derive them

* **`prediction_contract_v5` has no sibling manifest.** Its `player_game.parquet`,
  `player_game_enriched.parquet` and `contract.json` carry none, while v4's four artifacts all do.
  UNVERIFIABLE ⇒ may not back a number. Consistent with E1_I0035; recorded because the arm's real
  row universe is v5, so every screen touching this arm must reconstruct rather than read.
* **`data/injury_history/injury_history.csv` has no manifest either**, and its observation time is a
  single retrospective scrape (`S_TX_OBSERVED_TIME = 2026-07-30T17:42Z`) postdating every row in the
  2021–2024 partition. It is the strongest affiliation evidence in the repository and it still
  cannot back a number. That is the constraint that shaped this screen, not an oversight.
* **Type-I rate 0.0675 at nominal 0.05** (400 synthetic no-effect datasets, team-season blocks).
  Mildly anticonservative. Every team-level verdict here rests on an injection-verified floor rather
  than on p alone, so no verdict turns on it, but it is reported.
