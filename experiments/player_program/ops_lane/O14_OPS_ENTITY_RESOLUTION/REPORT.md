# O14_OPS_ENTITY_RESOLUTION — Entity resolution in the prospective capture path

**Epistemic status (verbatim from the node brief):**

> DESIGN OR IMPLEMENTATION ANALYSIS of a documented prospective-capture defect. Isolated branch only. This lane does not block possession research unless it changes the historical feature evidence.

**Lane:** operations · **Type:** audit · **Node write scope:**
`experiments/player_program/ops_lane/O14_OPS_ENTITY_RESOLUTION/` (nothing outside it was written;
no git command was run; no shared schema or contract was changed).

---

## 0. Headline

The defect **is documented**, and it **reproduces** — including one instance the documentation does
not name, in which a player designated **Out** was simultaneously counted **available** for a team
she no longer plays for, at **22.73 projected minutes** against a 200-minute pool.

Documentation of record: `experiments/player_program/PROJECT_UPDATE_2026-08-04.md:203` (defect
register row **D-e**, severity **B**, "alias and cold-start tests") and its expansion at
`experiments/player_program/PROJECT_UPDATE_2026-08-04.md:212-227`; plus the standing operational
note at `experiments/forecast_dryrun/OPERATIONAL_GAPS.md:182-185`.

One documentation error is recorded in section 5: the mechanism D-e names ("the matcher's
season-history threshold") does not exist in the code.

---

## 1. Where the defect is documented

| Claim | Path:line |
|---|---|
| Defect register entry **D-e — "Entity resolution / cold start"**, severity **B** (capability risk), required action "alias and cold-start tests" | `experiments/player_program/PROJECT_UPDATE_2026-08-04.md:203` |
| The three D-e sub-claims (no stored forecast changed mechanically; `record_idx 3` not invalidated; two real prospective capability risks remain) | `experiments/player_program/PROJECT_UPDATE_2026-08-04.md:212-227` |
| "Alias / team-history resolution for recently transferred players... Had her status been **Out**, exclusion would have failed on a high-usage player." | `experiments/player_program/PROJECT_UPDATE_2026-08-04.md:214-218` |
| Recommendation: alias-mapping tests, roster-to-history reconciliation, explicit cold-start player objects, **fail-closed or manual-review rule** for unmatched Out/Questionable players | `experiments/player_program/PROJECT_UPDATE_2026-08-04.md:225-227` |
| "Name matching is normalized-exact only (accent/punctuation-insensitive)... A persistent alias table (capture-name -> master player_id) should accumulate as mismatches appear. None appeared today." | `experiments/forecast_dryrun/OPERATIONAL_GAPS.md:182-185` |
| The player layer is informational in v0 and does not modify the team forecast | `experiments/forecast_dryrun/OPERATIONAL_GAPS.md:166`; `daily_forecast.py:603`, `daily_forecast.py:781`, `daily_forecast.py:965` |
| Planned-but-not-built work item **W1-B — "Entity resolution as-of publication"**, naming trades and 7-day contracts as the hazard | `project_docs/PLAN_2026-07-31_W1_AUDIT_AND_BAKEOFF.md:135-138` |
| Measured entity-resolution rates for the **news** feed: 8.2% wrong-team rate, 29 shared surnames, recommendation to derive team from the resolved player's as-of roster — "recorded here and NOT acted on" | `data/w1_truth/W1_TRUTH_REPORT.md:60`, `:76`, `:80` |
| Props settlement joins on `player_name`; "one known chore: name normalization" | `experiments/props_capture_setup/REPORT.md:61-63` |

The implementation under audit is the prospective player layer, `daily_forecast.py:640-760`.
The only name-resolution primitive in the whole path is `_norm_name` at `daily_forecast.py:606-609`
(NFKD, strip combining marks, lowercase, drop non-alphanumerics). Constants:
`MINUTES_ALPHA = 0.30` (`daily_forecast.py:112`), `RECENCY_GAMES = 3` (`daily_forecast.py:120`).

---

## 2. What I measured, and with what

Two scripts, both in this node's directory, both read-only:

* `repro_entity_resolution.py` -> writes `MEASUREMENTS.json`. Command: `python repro_entity_resolution.py`.
* `TESTS.py` -> the fix's contract, synthetic plus one real replay. Command: `python TESTS.py`.
  `main()` returns 1 on failure (pytest is not installed). **Result: ALL CHECKS PASSED (27 checks).**

Two data snapshots, always labelled:

| Label | master_player.parquet | injury_log.csv span |
|---|---|---|
| `SNAP_PROGRAM` — this worktree | through **2026-07-31**, manifest `fit_through_date` `2026-08-01T12:00:00+00:00`, sha256 `52e084ef...8641dce` | `20260730T154950Z` .. `20260801T150005Z` (551 rows) |
| `SNAP_LIVE` — repository root worktree, **read-only** | through **2026-08-03** | `20260730T154950Z` .. `20260804T200008Z` (1,109 rows) |

`SNAP_LIVE` is the snapshot `PROJECT_UPDATE_2026-08-04.md` was written against; it is also **still
being appended to by the live capture schedulers** — the injury log grew from 1,106 to 1,109 rows
between two runs of my harness minutes apart. Every `SNAP_LIVE` number below is therefore a
timestamped observation, not a reproducible constant. `SNAP_PROGRAM` numbers are reproducible.

### Measurements

**M1 — per-team truncation of a transferred player's minutes history.**
`daily_forecast.py:654` filters the player frame to one team (`tp = p[p.team_abbreviation ==
team_ab]`), and every per-player quantity — `games_played`, `min_ewma`, `last_played`, `cold_start`
— is then computed from that team-filtered frame (`daily_forecast.py:674-683`). Same-season rows at
a prior team are discarded.

| | SNAP_PROGRAM | SNAP_LIVE |
|---|---|---|
| players with >1 team in 2026 | 11 | 14 |
| of those, <=1 played game at the new team | 3 | 5 |
| mean absolute EWMA error vs identity EWMA | 0.442 min | 1.272 min |
| max absolute EWMA error | 1.624 min | **9.423 min** |

The 9.42-minute case is **Kelsey Plum**: identity EWMA over her 13 played 2026 games = **29.96 min**;
the value the forecaster computes from her single PHX game = **20.53 min**. Four `SNAP_LIVE` movers
(Bibby, H. Jones, Feagin, Morrow) have **zero** played games at their new team, so the forecaster
labels them `cold_start = True` and `min_ewma = None` despite 4-20 played games each in the same
season — e.g. Morrow, 20 games, identity EWMA 22.73 min.

**M2 / M7 — one identity on two rosters.** Each team's recency roster is built from that team's own
last 3 games (`daily_forecast.py:662-665`) with no cross-team exclusivity check anywhere in the
function. In `SNAP_LIVE`, **2 players** are on two rosters at once — Chloe Bibby (CHI + MIN) and
Aneesah Morrow (CON + TOR) — and **35.56 minutes** of EWMA are attributed across teams for those two
identities (`sum_min_ewma_available`, `daily_forecast.py:743`). In `SNAP_PROGRAM`: 0.

**M6 — as-of designation binding (the reproduction that matters).** Injury rows are selected by
franchise-name equality and then matched by normalized name **within that team only**
(`daily_forecast.py:667-669`, `:685`). Asking the question the way the forecaster asks it — at each
capture timestamp, against only games played before that capture date — over **1,109** captured rows
in `SNAP_LIVE`: 1,049 bind to the named team, **23 rows / 2 players bind to no roster entry at the
named team while the player is plainly visible under another team**, 37 rows / 4 players are absent
from the season entirely.

| player | listed by | statuses | captures affected | window |
|---|---|---|---|---|
| **Aneesah Morrow** | Toronto Tempo | **Out** | 7 | `20260802T000003Z` -> `20260802T230003Z` |
| Kelsey Plum | Phoenix Mercury | Questionable, Available | 16 | `20260802T220002Z` -> `20260803T230002Z` |

In `SNAP_PROGRAM` this count is **0** — the window opens on 2026-08-02, after that snapshot ends.

**M4 — does normalized-exact matching actually lose anything?** No, and this is a negative result
worth keeping. Across both snapshots: **0** normalization collisions between distinct master players;
3 (`SNAP_PROGRAM`) / 4 (`SNAP_LIVE`) captured names unmatched by normalized-exact; **0** of them
recoverable by a strictly weaker rule (first initial + surname). Kara Dunn, Ugonne Onyiah and Tonie
Morgan have **no rows in any season** — genuine cold starts. Iliana Rupert **does** exist, in 2022,
2023 and 2025; she is lost only because the matcher is season-scoped. So the missing "alias table"
of `OPERATIONAL_GAPS.md:182-185` is not what is costing matches today; a cross-season identity index
is. The alias table this node ships (`alias_table.json`) is therefore **empty by design**, with the
two rejected candidates recorded in it.

**M3 — the same question against the FINAL master returns zero.** Deliberately reported: it is the
wrong question, and it is the question that makes the defect invisible. Once the master ingests the
new team's first game, every designation binds and the trace disappears. This is why M6 replays
per-capture.

**M8 — the props path carries no identity at all.** `data/props_capture/master_props.csv` has **no
`player_id` column**; the join key is the bookmaker's display string. 90 distinct names in
`SNAP_LIVE`, of which **1** (Megan Gustafson) fails against the 2026 master and **0** fail against
all seasons — again a season-scoping problem, not a spelling problem.

---

## 3. Does it reproduce? Yes — mechanism, and realized instance

**Mechanism.** Between a trade being published on the injury feed and the master ingesting the
player's first game for her new team, the player has, in the forecaster's view, two disjoint halves:
a roster entry at the **old** team (she is still inside its 3-game recency window) and a designation
at the **new** team that matches nobody. The Phase-3 rule gate (`daily_forecast.py:690-691`) can
only fire where the designation and the roster entry are the same team's, so in that window it
cannot fire at all. The code says so itself, at `daily_forecast.py:731-735`: *matches NO ONE in the
team's season history -- new signing or name mismatch; if the status is Out and the player is
rostered under another spelling, the gate did NOT fire*.

**Realized instance -- Aneesah Morrow, 2026-08-02.** `TESTS.py::t5` replays capture
`20260802T210004Z` against the master as it stood, using a faithful port of `daily_forecast.py:640-760`:

* baseline counts Morrow **available for Connecticut** at **22.73** projected minutes;
* baseline's Out gate fires for her **nowhere**;
* baseline emits exactly the documented WARN for Toronto;
* Connecticut's `sum_min_ewma_available` is **243.18** min under the baseline and **220.44** min under
  the fix -- a **22.73-minute, 11.4%-of-a-200-minute-pool** overstatement of one team's available
  rotation, driven entirely by entity resolution.

This is materially stronger than what D-e records. `PROJECT_UPDATE_2026-08-04.md:216-218` states the
Out case as a **counterfactual** ("Had her status been **Out**, exclusion would have failed on a
high-usage player"). It was not counterfactual. Seven captures earlier the same week, a player with
20 games and a 22.73-minute EWMA was listed **Out** and the exclusion did fail. D-e's claim 1
("neither observed warning changed a stored forecast mechanically") is about Plum and Dunn and is
correct for them; it does not extend to Morrow, whom D-e does not mention.

**What is NOT harmed today.** The player layer is informational in v0 and does not modify the team
forecast (`experiments/forecast_dryrun/OPERATIONAL_GAPS.md:166`; `daily_forecast.py:781`, `:965`), so
no stored team forecast is wrong because of this. The defect is a **capability** defect on the path
that the V4 bottom-up thesis would promote -- which is exactly the severity-B classification D-e
already assigns.

---

## 4. The fix -- designed and tested here, merged nowhere

`fix_entity_resolution.py` holds two functions: `player_layer_baseline` (a faithful port of
`daily_forecast.py:640-760`, present only so the defect can be reproduced without the forecaster's
slate/odds/network path) and `player_layer_resolved` (the fix). Nothing in the production path
imports either. `daily_forecast.py` was **not** modified.

| id | change | fixes |
|---|---|---|
| **F1** | minutes history is taken from `player_id` across the whole season, not from the team-filtered frame | M1 (up to 9.42 min EWMA error; 4 veterans mislabelled `cold_start`) |
| **F2** | single tenancy: an identity belongs to exactly one team as of the cutoff -- the team of her most recent game, unless a **more recent** designation names another team, which wins and is flagged `designation_transfer` | M2/M7 (double-rostering, 35.56 min double-attributed) |
| **F3** | designations bind to a `player_id` via a cross-season identity index, then attach wherever that identity is rostered -- not to a (franchise-name, spelling) pair | M6 (23 unbindable rows), M4 (Rupert), M8 (Gustafson) |
| **F4** | fail-closed: an `Out`/`Doubtful` that binds to no identity raises **BLOCK**, not WARN, and materialises an explicit unresolved cold-start object | `PROJECT_UPDATE_2026-08-04.md:225-227`, the recommended rule |

Deliberately **not** done: fuzzy matching. Resolution stays normalized-exact plus an explicit,
auditable alias table, because M4 shows fuzzy matching would have recovered nothing on this feed --
consistent with the standing "no fuzzy matching by policy" note at `OPERATIONAL_GAPS.md:183`.

`TESTS.py`, 27 checks, all passing:

* **T1** transferred player's prior-team history is not discarded (baseline EWMA error 6.60 min on
  the fixture; fix equals identity EWMA exactly, and flags `transferred_in_season`);
* **T2** one identity cannot occupy two recency rosters (baseline puts her on both; fix on the most
  recent only);
* **T3** an `Out` published under the new team *before* the master has a game for that team still
  fires the gate (baseline: still available at the old team, `n_out = 0` everywhere; fix: removed
  from the old team, `Out` at the new team, 32.0 vacated minutes attributed there);
* **T4** an `Out` binding to no identity fails **closed** (baseline WARN-and-continue; fix BLOCK plus
  an explicit `cold_start_unresolved` object);
* **T5** the real Morrow replay above, which **SKIP**s rather than fails if the live snapshot is absent;
* **T6** no-regression: with no transfers and no unbound designations the fix reproduces the baseline's
  available set, `sum_min_ewma_available` (to 1e-9) and `n_out` exactly.

---

## 5. Contradictions found

1. **The mechanism D-e names does not exist.** `PROJECT_UPDATE_2026-08-04.md:216` attributes the Plum
   failure to *one appearance falls below the matcher's season-history threshold*. There is no
   threshold on season history anywhere in `daily_forecast.py:640-760`. The quantities that exist are
   `RECENCY_GAMES = 3` (`:120`, a window over the team's games, not a count of the player's) and a
   bare presence test (`season_by_norm.get(n) is not None`, `:702`/`:707`). The real mechanism is the
   **as-of race** measured in M6: at the captures in question the master held **zero** PHX rows for
   Plum, so the test that failed was presence, not a threshold. The conclusion D-e draws is right;
   its stated cause is not.
2. **A document/bytes disagreement that is only a snapshot-age artifact, not an error.**
   `PROJECT_UPDATE_2026-08-04.md:215` says Plum shows "LAS 2026 (17 g) + **PHX 2026 (1 g)**". This
   worktree's master shows LAS 17 and **no PHX rows at all**; the root worktree's master shows LAS 17
   + PHX 1 (game date 2026-08-03). The program worktree's master is bound through
   `2026-08-01T12:00:00+00:00` per its manifest and simply predates the game. The document is correct
   about the live bytes. Recorded because a later reader running my harness in this worktree will get
   `M6 = 0` and could wrongly conclude the defect does not reproduce.
3. **A scope difference worth not conflating.** `data/w1_truth/W1_TRUTH_REPORT.md:76` reports an
   **8.2% wrong-team rate**. That is the **news-extraction** feed, where the extracted team behaves
   like feed provenance (`:80`). The **official injury PDF** feed measured here does *not* publish
   wrong-team rows: cross-team binding failures there are trade-timing races, not misattribution.
   The two numbers are not comparable and the 8.2% must not be carried onto the injury path.

---

## 6. What I could NOT establish

* **Whether any stored forecast record was affected in practice.** `forecasts/forecast_log.jsonl`
  holds 23 records; I did not audit which cutoffs ran during the 2026-08-02 Morrow window, because
  that is coverage/obligation accounting (nodes D-a..D-d) and outside this node's mandate. The player
  layer being informational (`OPERATIONAL_GAPS.md:166`) bounds the impact regardless, but I did not
  verify the counterfactual per record.
* **Whether the props path has ever mis-joined a settlement.** M8 establishes only that
  `master_props.csv` carries no `player_id` and that 1 of 90 names fails a season-scoped match. I did
  not run a settlement join, and no graded props file exists in either snapshot to check against.
* **The true size of the transfer population.** 11-14 movers in one partial season is too small to
  put an interval on the EWMA error; the 9.42-minute maximum is one observation, not an estimate of a
  tail.
* **Whether `designation_transfer` (F2) is safe against a mis-typed franchise on the feed.** My fix
  lets a designation reassign a player's team. On the observed feed that is right (the feed led the
  master by ~29 h). A feed that publishes a wrong franchise would move a player wrongly. I tested the
  correct-feed case only; the wrong-franchise case has no instance in the data to test against.
* **Anything about challenger performance.** Not inspected; nothing under `stage2b/SEALED_RESULTS/`
  was read.

---

## 7. Stop conditions and escalation

**No stop condition is tripped.** Nothing here touches the primary target, the K0 structure, the
inference structure, the candidate universe, the cutoff-valid feature set, or leakage status.

**No escalation to the possession lane is warranted, and I checked rather than assumed.** The defect
is confined to the prospective path, which resolves players by `(team_abbreviation, player_name)`
strings. The historical builders key on `player_id` throughout -- `possession_artifact_v1.py:263`
(`groupby(["player_id", "season"])`), `fit_rate_and_p3.py:289`, `score_v14_v15.py:245` -- and
`validate_p3.py:250` already counts players with more than one `team_id` in a season and reports
mover-vs-stayer coefficient continuity explicitly. Historical feature evidence is therefore not
changed by anything in this report.

**Nothing is proposed for merge from this lane.** The fix is a design plus tests inside this node's
directory. The changes it implies to the shared prospective contract -- a `player_id` column on the
capture artifacts, single-tenancy in the roster construction, and a BLOCK severity for an unbindable
`Out` -- are listed as proposals only in `FINDINGS.json` (`shared_contract_changes_proposed`) and
belong to **O16_SHARED_SCHEMA_ADOPTION** and the user.

---

## 8. Files produced by this node

| file | what it is |
|---|---|
| `REPORT.md` | this report |
| `FINDINGS.json` | machine-readable findings |
| `MEASUREMENTS.json` | raw output of the harness, both snapshots |
| `repro_entity_resolution.py` | the measurement harness (M1-M8), read-only |
| `fix_entity_resolution.py` | faithful baseline port + the designed fix (F1-F4) |
| `TESTS.py` | 27 checks; `main()` returns 1 on failure |
| `alias_table.json` | explicit alias table, empty by design, with rejected candidates recorded |
