# Reach — does a row-set change go further than a probability change?

**The question nobody had asked.** E1_I0035 established that the `p_active` *calibration* defect
does not reach production. A roster-currency fix is a different kind of change: it alters **which
player-club pairings exist at all**, not the number attached to one. A row-set change can propagate
through anything that enumerates the universe, even if nothing reads the probability. That
distinction had not been checked.

**Answer: it reaches exactly as far — nowhere. But the check turned up something more useful,
which is that the shipped code has the same defect in an independent copy.**

---

## 1. E1_I0035's zero-reference finding, independently re-verified

Counted directly, not taken on trust:

| | `p_active` references |
|---|---:|
| `daily_forecast.py`, `props_edge.py`, `conditional_edge.py`, `calibrated_prob_edge.py` | **0 each** |
| `daily_certify.py`, `daily_refresh.py`, `props_capture_daily.py`, `odds_capture_daily.py`, `injury_capture_daily.py` | **0 each** |
| `wnba-prediction-engine/`, `wnba_odds_system/`, `wnba-odds-aggregator/`, `forecasts/`, `leaderboards/` (all files, recursive) | **0 each** |

Confirmed.

---

## 2. The new question: who consumes the universe *row set*?

Searched for consumers of `prediction_contract_v4/v5` artifacts and modules, and for `row_uid` /
`obligation_uid` / `universe_tier` / `candidate_source` used as a row enumeration.

**Production / scheduled path: zero consumers.** The scheduled-task inventory
(`setup_scripts/verify_scheduled_tasks.ps1:67-79`) lists eleven tasks. None reads the contract.
`daily_refresh.py:39-45` fixes the refresh chain to four steps — `collect_refresh`, `build_masters`,
`build_channel_base_v2`, `daily_certify` — and none of the four references it.

**Research tree: many.** ~32 files under `experiments/player_program/`, the `cbs_v12`–`cbs_v15`
estimator stack (`cbs_v15.py:38  ROW_UNIVERSE = "prediction_contract_v5"`), the market program's
verifier, ten exploration screens, and the contract test suite. **A currency rule would move all of
these.** That is a real cost — it invalidates cached research frames and every receipt keyed on the
row set — but it is a cost inside the laboratory, not outside it.

**So the blast radius of a row-set change is larger than that of a calibration change, and it is
larger entirely within the research tree. It crosses the production boundary in zero places.**

---

## 3. The multiply site, confirmed

`experiments/player_program/build_projected_exposure.py`:

```
:238   base["raw_expected_minutes"] = base["p_active"] * base["e_minutes_given_active"]
:77/85/93   "production_eligible": False   (all three regimes)
```

and its validator refuses to let that change —
`validate_projected_exposure.py:571-572`:

```python
    assert not any(ev["production_eligible"] for ev in M.REGIME_EVIDENCE.values()), \
        "a regime claims production eligibility; nothing here is promoted"
```

**Its row set is the contract's row set, one-to-one** (`:42` reads
`prediction_contract_v5/player_game_enriched.parquet`; `:185` reads it whole; `:227-229` merges the
predictions on `row_uid` with `validate="1:1"`). So a currency rule *would* be seen here — every
allocation denominator shifts, and `:439 raise ProducerFailure(f"no contract rows for team-game …")`
would fire if a rule ever emptied a team-game. **No rule measured here does: R3 removes at most
2,054 of 20,084 rows and never all of a team-game's.** The artifact this producer writes is consumed
by nothing on the daily path.

**Registry check.** `production_eligible: true` — **zero hits repository-wide.** The functional
analogue that does carry `true` is `promote` in `experiments/registry.jsonl`, which has exactly two:
a team-level channel forecast, and `minutes_ewma_vs_carryforward_v1` — the only promoted component
touching player rows. It is live as `daily_forecast.py:112  MINUTES_ALPHA = 0.30  # promoted:
minutes_ewma_vs_carryforward_v1`, and it is applied to the recency roster below, never to a
contract obligation.

---

## 4. The finding that matters: the shipped roster is built by a *different copy of the same rule*

`daily_forecast.py` is on the scheduler (`WNBA_DailyForecast_AM`, `_PM`, marked `Critical`). It
never opens the contract. It builds its own player list — `daily_forecast.py:647-665`:

```python
    p = pd.read_parquet(MASTER_PLAYER)
    p = p[(p.season == season) & (pd.to_datetime(p.game_date).dt.date < slate_date)].copy()
    ...
        recent = set(tgames[-RECENCY_GAMES:])
        roster = tp[tp.game_id.isin(recent)].player_name.unique()
```

with `RECENCY_GAMES = 3` (`:120`), then excludes only players the injury feed marks `Out`
(`:690-691`). `props_edge.py` is different again: its row set is whatever the sportsbooks posted
(`:393` reads `data/props_capture/master_props.csv`), with the masters used only as a name→id
lookup.

The shipped per-player enumeration is real and it is in the log —
`forecasts/forecast_log.jsonl` carries `"out_away":["Ezi Magbegor","Taina Mair"]`,
`"n_roster":13` and so on, written at `daily_forecast.py:1130-1140`. **Every one of those names
comes from the box-score recency roster, not from the contract.**

Three consequences, in order of importance:

1. **Repairing the contract universe would not change one line of shipped output.** The two systems
   share no code.
2. **The shipped roster has the same roster-currency defect**, in a stricter form: a three-game
   lookback rather than five, and **no departure check either**. A player traded yesterday remains
   on her old club's shipped roster for three games.
3. **It is keyed on `player_name`, not `player_id`.** This screen's rules are all `player_id`-based;
   they would not port across without an entity-resolution step, and the programme has lost six
   findings to name matching.

---

## 5. Verdict

| | calibration fix (Xa / Xa+) | row-set fix (Z_R3) |
|---|---|---|
| production consumers | 0 | **0** |
| research consumers | the arm's `p_active` column | **~32 player_program files + the cbs_v12–v15 stack + 10 screens + the contract tests** |
| would it change shipped output | no | **no** |
| would it break a producer | no | no (no rule empties a team-game) |
| cost of enacting | re-registration of a recalibration | re-registration **plus** invalidation of every cached frame and receipt keyed on the row set |

**A roster-currency rule does not reach further than a calibration fix does, in the only direction
that matters. It reaches considerably further inside the laboratory, which makes it the more
expensive of the two changes to enact for a benefit that — on the clean window — is not
distinguishable from the cheaper one.** That comparison is `CURRENCY_RULE.md` §5.

**The one thing here that is worth acting on independently of any of it:** the shipped roster in
`daily_forecast.py` carries this defect in its own right, is on the critical scheduled path, and
was not previously known to. It is logged in `DEFECTS.md` as **D-2**.
