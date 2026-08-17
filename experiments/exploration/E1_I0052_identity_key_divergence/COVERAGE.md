# Coverage — how much of the research lane the verified identity map protects

**The boundary is the real answer to this screen, so it is drawn precisely: the lane divides into
three zones, and only the third is exposed.**

| zone | what identifies a player | share of the lane | divergence measured |
|---|---|---:|---:|
| **Z1 — no identity at all** | nothing; the frame is team-, game- or cell-level | **721 of 830 frames (86.9 %)** | structurally impossible |
| **Z2 — `player_id` present and used** | the stable key, carried in the frame | 106 of 830 frames; 492 of 525 player-keyed operations | **0 rows** |
| **Z3 — no stable key at source** | a name string, because the feed has no id | 3 frames + the props ingest | **62 rows, DROP** |

---

## 1. What the "verified identity map" actually is, and why it protects Z2

Two different things in this programme are called an identity map. They are not the same and they
protect different things.

### 1a. The `row_uid → (player_id, game_id, team_id)` map — E1_I0033

Recomputed from `cbs_obligation_key/1` (`CANONICAL_KEY_FIELDS = (player_id, game_id, team_id)`)
over the cross product of team-games and the 268 players in the partition — **519,920 triples, all
keys unique** — and cross-checked against `prediction_contract_v4`: **22,659 of 22,659 `row_uid`s
reconstructed, all three fields agreeing. Exact.** Resolution on the champion's own rows:
**26,574 of 26,614 (99.85 %)**; the 40 unresolved are tier-B cold-start fallback rows for players
with no box-score row anywhere in 2021–2024.

**This map contains no name.** It is a key-to-key map, and what it buys is that the champion's row
space is addressable by `(player_id, game_id, team_id)` without ever consulting a string.
**Wherever a screen carries `row_uid` or the canonical triple, name-keying is not merely avoided —
it is unavailable.** That covers `E1_I0035`, `E1_I0045`, `E1_I0033` and the m13/m14 chain: 20,084
to 26,574 rows per frame.

### 1b. The `normalized_name → player_id` index — O14 `build_identity_index`

Built by enumerating every distinct `(player_id, player_name)` pair observed in a box score, with
the latest season binding last, plus an explicit alias table. **This one does contain names**, and
it exists precisely to convert Z3 into Z2 at the feed boundary.

Verified here on the exploration partition: **271 distinct normalized spellings, 0 of which bind
to more than one `player_id`.** The map never merges two people. `alias_table.json` is present and
**empty (0 entries)**, which O14 documents as correct-by-design.

**Its coverage is exactly the set of spellings that have appeared in a box score.** That is the
whole boundary, and §3 is what falls outside it.

---

## 2. Zone 2 — measured, not assumed

Everything in Z2 was measured rather than asserted safe:

* **492 of 525** player-keyed structural operations name `player_id` in the key.
* **310 of 310** key-shaped variable bindings (`key`, `keys`, `gk`, `pk`, `by`, `entity_cols`, …)
  across 194 files resolve to id- or non-player keys. **Zero** name a player-name column. The six
  most common bindings are `['player_id','season']`, `['game_id','team_id','player_id']`,
  `[df['player_id'], df['season']]`, `['season','player_id']`.
* **70 of 387** unresolvable structural operations sit inside the eleven screens that own or
  consume a frame in which an identity is actually ambiguous. All 70 were printed with source
  context and adjudicated by hand; every one resolves to `[player_id, season]`,
  `[game_id, team_id, player_id]`, `[season]`, or a non-player grouping.
* The champion's fit pool is assembled by
  `m13_lib.py:348  scored.merge(market, on=['game_id','player_id'], how='inner',
  validate='one_to_one')`. **A name-keyed assembly there is not merely absent, it would raise.**
* The shared screen frame's decision stratum recomputes to the materialised `DECISION` column on
  **18,212 of 18,212 rows**.

**Two composite sites deserve naming because they carry a name in the key and are still in Z2.**
`E0_I0006_usage_redistribution/analyze_clean.py` groups and inner-joins on
`["player_id","player_name"]`. That is a name-bearing key. It measures zero divergence **only
because its panel is a perfect 265-id / 265-name bijection**, rebuilt from raw per-season gamelogs
after an unrelated contamination correction. It is in Z2 by accident of provenance, not by design
— see `VERDICT.md`, weakening result 1.

---

## 3. Zone 3 — the exposed boundary, in full

### 3a. The props feed — the only lane with no stable key at source

`data/props_capture/historical/master_props_historical.csv`
sha256 `47983f8725e775aac16ff342d7704b7b2a8e72c3dfdf0b1448d4481660431a82`
— **manifest: MISSING → UNVERIFIABLE**, and **read from the production worktree, not the research
one** (`compute_model_vs_market.py:69` resolves `PROPS_CSV` under `LIVE_ROOT`).

| | |
|---|---:|
| columns | 14 |
| carries `player_id` | **no** |
| rows, all seasons | 36,946 |
| rows, 2021–2024 partition (2024 only) | 11,237 |
| in-play excluded | 0 |
| one-sided excluded (cannot devig) | 8 |
| two-sided rows | **11,229** |
| resolved to a `player_id` by normalized-exact | **11,167 (99.4479 %)** |
| **unresolved and excluded** | **62 (0.5521 %)** |

`F16_PLAYER_PROPS/measure_props_evidence.py` states the constraint in its own words: *"no
player_id exists on either props file."* **This is not a choice of key. It is the only key the
source admits**, and the correct response is the one taken — normalized-exact, exclude-and-list,
no fuzzy fallback.

The name-keyed dedup at `m14_lib.py:267` / `compute_model_vs_market.build_market_frame`
(`duplicated(["game_id","player_name","bookmaker_key","line"])`, run **before** the id is
assigned) was tested against its id-keyed counterpart on the identical resolved row set:
**11,167 survivors under both. Δ = 0.** The ordering is safe here because no book priced one
player under two spellings in one game at one line.

Only **two** of the twelve ambiguous identities are priced at all in 2024 — Diggins-Smith (232
rows) and Stevens (64) — and **each appears under exactly one spelling in the feed**.

### 3b. The three `NAME_ONLY` frames

| frame | rows | name column | rows carrying an ambiguous spelling |
|---|---:|---|---:|
| `E1_I0045_roster_currency/top_removed_players_R3.csv` | 10 | `player_name` | **2** |
| `E1_I0049_benchmark_constants/CENSUS.csv` | 9 | `name` | 0 |
| `E1_I0043_opponent_defence/INDEPENDENCE.csv` | 6 | `name` | 0 |

The latter two hold benchmark/diagnostic labels, not players. The first is the lane's one
name-keyed published table, and it is unchanged under the correct key (proof by exhaustion in
`AMBIGUOUS_IDENTITIES.md` §3).

### 3c. The injury feed — outside this screen's measurement, named for completeness

`data/injury_capture/injury_log.csv` has **no manifest in either worktree** and is deduplicated on
`["team","player"]` — a name key — in the shipped path, in O14's reproduction, and in E1_I0048's
re-execution. It is the historical source of most of this programme's six name-matching failures.
It is not measured here because it is a production input on the shipped lane, not a research
artifact, and E1_I0048 already quantified its effect. It belongs in this coverage table because
**it is the third and last place the lane has no choice**.

---

## 4. Manifest status of everything this screen opened

| artifact | manifest | used for |
|---|---|---|
| `.../player-model-program/data/masters/master_player.parquet` sha256 `52e084ef…` | **PRESENT** — `asof_granularity: row`, `fit_through_date 2026-08-01T12:00Z` | every identity number |
| `C:\Users\jgallagher\wnba-betting-model\data\masters\master_player.parquet` | **MISSING → UNVERIFIABLE** | **not opened for any number** |
| `.../data/masters/master_team.parquet` | PRESENT — `row` | not used |
| `E0_I0006/clean_played_panel.parquet` sha256 `4819dbf2…` | MISSING | E0_I0006 re-execution, labelled |
| `E0_I0006/clean_roster_panel.parquet` sha256 `c980a426…` | MISSING | E0_I0006 re-execution, labelled |
| `E0_I0029/screen_frame.parquet` sha256 `a6d94f66…` | MISSING | decision stratum, labelled |
| `E1_I0045/_PF.parquet` sha256 `28c91e30…` | MISSING | decision stratum, labelled |
| `MEASURE_F1_m13_fitpool/repro_out/translation_rows.parquet` sha256 `9935e1dd…` | MISSING | fit-pool membership, labelled |
| `master_props_historical.csv` (**production**) sha256 `47983f87…` | MISSING | §3a, labelled |

**Every research artifact this screen measured except `master_player` is unmanifested.** Under
`MISSING = UNVERIFIABLE` those numbers are internal-consistency results — "this frame, as it sits
on disk, does not diverge" — not statements about a verified pipeline. That limitation applies to
the zeros as much as to anything else, and it is the same governance gap E1_I0048 logged as its
D-4. It has not narrowed.

---

## 5. What could not be covered

* **5 of the 43 identity-bearing frames carry no `season` column** and could not be
  partition-guarded. They are reported as STRUCTURE_ONLY in
  `out/_s07_frame_divergence_guarded.csv` and back no number.
* **1 CSV was unreadable** (`E1_I0040_audit_extension/MAX_SIGNATURE_HITS.csv`, empty).
* **Frames over 220 MB** would have been skipped; none was.
* The census covers `experiments/exploration` and `experiments/player_program`, **902 Python
  files, 0 parse failures**. It does **not** cover `experiments/market_program` as a lane in its
  own right; the two market files that feed the research lane
  (`MODEL_VS_MARKET/compute_model_vs_market.py`, `M13/M14`) were read and measured directly, but a
  full market-lane census is out of scope and its absence is a coverage gap, not a clean result.
