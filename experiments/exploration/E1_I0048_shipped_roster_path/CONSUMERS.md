# Who reads the shipped roster rows?

**The question E1_I0035 did not ask.** E1_I0035 verified that nothing reads `p_active` — a
*probability*. E1_I0045 verified that nothing reads the contract's *row set*. Neither asked about
**the roster rows the shipped job writes into `forecasts/forecast_log.jsonl`**, which is a third
thing: not a number attached to a row, and not a research universe, but a per-player enumeration
sitting inside the official regime-D artifact.

**Answer: nothing reads them. They are write-only.**

---

## 1. What is actually emitted

`daily_forecast.py:1130-1140` writes, inside `core_only_prediction`:

```
player_layer_informational
├── note                       "v0: does NOT modify the team forecast"
├── home / away
│   ├── n_roster
│   ├── n_out
│   ├── vacated_min_ewma
│   ├── sum_min_ewma_available
│   └── n_cold_start
├── out_home                   [names]
└── out_away                   [names]
```

Eight field names. The roster name list is **not** among them — only the `Out` names are written.

---

## 2. Every reader of the forecast log, counted

Repository-wide search over `*.py` for `forecast_log.jsonl` / `DEFAULT_FORECAST_LOG` found eight
files. Each was then counted for the eight player-layer field names:

| file | forecast-log refs | player-layer field refs |
|---|---:|---:|
| `evalharness/forecast_log.py` (the logger) | 15 | **0** |
| `evalharness/__init__.py` | 1 | **0** |
| `verify_all.py` | 1 | **0** |
| `migrate_forecast_log_schema2.py` | 4 | **0** |
| `prospective_pair/alt_model_log.py` | 1 | **0** |
| `tests/test_forecast_log.py` | 23 | **0** |
| `ops_adoption_tests/D4/TESTS.py` | 6 | **0** |
| `daily_forecast.py` — **the writer, not a reader** | 9 | 21 |

`evalharness/forecast_log.py` references `core_only_prediction` seven times, and every one treats
it as an **opaque blob**: it is serialised, hashed into the chain, and compared for duplicate
detection. It never indexes into it. The logger cannot tell a player layer from a weather report.

**Player-layer field references across every reader of the log: 0.**

---

## 3. The product surfaces, traced

The twelve surfaces named in the brief, counted for all eight player-layer field names *and* both
forecast-log tokens *and* `core_only_prediction`:

| surface | total refs |
|---|---:|
| `props_edge.py` | **0** |
| `conditional_edge.py` | **0** |
| `calibrated_prob_edge.py` | **0** |
| `daily_certify.py` | **0** |
| `daily_refresh.py` | **0** |
| `props_capture_daily.py` | **0** |
| `odds_capture_daily.py` | **0** |
| `injury_capture_daily.py` | **0** |
| `wnba-prediction-engine/` (recursive) | **0** |
| `wnba_odds_system/` (recursive) | **0** |
| `wnba-odds-aggregator/` (recursive) | **0** |
| `leaderboards/` (recursive) | **0** |

Twelve zeros. The same twelve zeros E1_I0035 found for `p_active`, re-derived here for a
different object. Those `p_active` zeros were independently recounted as anchor A7 before any of
this ran, and all reproduced at exactly 0.000e+00.

---

## 4. The one token hit, inspected rather than counted

A literal-token scan is only honest if its hits are opened. One file outside the writer matched:

```
cbs_v6.py:466:                 "n_cold_start": int(p.is_cold_start.sum()),
```

This is an unrelated local dictionary key inside a research estimator. `cbs_v6.py` contains zero
references to `forecast_log.jsonl`, `DEFAULT_FORECAST_LOG`, or `core_only_prediction`. **Not a
consumer.** Recorded here so that a later reader does not re-derive it, and so that the count of
"1 file matched" is not mistaken for "1 consumer".

`entity_resolution.py`, `ops_adoption_tests/O14/test_o14.py` and `.../baseline_port.py` also
match — they are the *replacement producer* and its tests, not consumers.

---

## 5. Does the player layer reach the team forecast?

No, and this is enforced rather than merely asserted. The layer is built **after** the team
forecast in `main()`, is passed into `forecast_one_game` only to be attached to the output row,
and the one place a player-layer value crosses into another artifact is:

```
daily_forecast.py:901   "n_out_players": (players.get(st["abbr"], {}) or {}).get("n_out"),
```

— a column in `feature_snapshot.csv`, which is an engineering dump under
`experiments/forecast_dryrun/`. It is not an input to `structural_forecast`, which takes only
`(hs, as_, lg, params)`. The record's own `note` field says `"v0: does NOT modify the team
forecast"`, and the code matches the claim.

---

## 6. Verdict

**The shipped roster rows are cosmetic.** They are written into the regime-D log, they are
covered by its hash chain, and they are read by nothing — no edge calculation, no odds
comparison, no leaderboard, no certification, no downstream artifact, and not the team forecast
they sit next to.

**This is the outcome the brief named as genuinely valuable, and it is not being inflated.** The
last live-path concern from the previous day's work resolves to: a defect that was real, that was
independently repaired in production before this screen ran, and whose pre-repair output reached
nothing.

### The result that most weakens this conclusion

Three, stated plainly:

1. **"Reaches nothing" is a statement about today's repository, not about tomorrow's.** The
   player layer is explicitly labelled `v0` and `informational`; the obvious next version is one
   that *does* modify the forecast. The moment anything reads `sum_min_ewma_available`, a roster
   defect becomes a model defect. The zeros are a snapshot, not a guarantee.
2. **The rows are inside the regime-D hash chain and are therefore permanent.** `verify_chain`
   covers them. They cannot be corrected without breaking the chain, so if a future consumer ever
   reads historical records, records 0–39 carry pre-repair rosters forever. That is an argument
   for leaving them alone, but it is also the reason the count in `SHIPPED_DAMAGE.csv` had to be
   established rather than waved away.
3. **This screen counted references, not behaviour.** A consumer that reached these fields through
   a generic JSON walk — `json.loads` then iterate — would not appear in any token count. I looked
   for that pattern in the eight readers and found none; each either hashes the blob or indexes
   named top-level keys. But a token scan cannot prove the absence of a dynamic access path, and
   this one does not claim to.
