# P23_DIMENSION_CARDINALITY_GUARD — S2: merge cardinality invariants preserving the 2,982-row / 1,491-game universe

**Lane:** possession | **Type:** implementation | **Severity on failure:** A | **Role:** data-integrity engineer

## Epistemic status

> INFRASTRUCTURE + task-specific INVARIANT. Proves a dimension merge cannot silently change the row universe. Does not establish that any dimension is scientifically usable.

Nothing below may be cited as evidence that venue, elevation, timezone or travel is a usable
feature. It establishes only that a merge which imports them cannot silently alter the row set.

---

## 1. Deliverables

| file | what it is |
|---|---|
| merge_guard.py | the call-site guard. No shared gate was edited. |
| TESTS.py | 16 tests, standalone, main() returns 1 on failure. 16/16 pass. |
| TEST_RESULTS.json | written by TESTS.py; carries every measurement quoted here |
| FINDINGS.json | machine-readable findings |
| REPORT.md | this file |

Validation command and result:

    python experiments/player_program/stage2b/P23_DIMENSION_CARDINALITY_GUARD/TESTS.py
    16/16 passed; results -> .../TEST_RESULTS.json     (exit 0)

`merge_guard.py` is a **call-site wrapper**, per standing rule 3. `feature_gate.py`,
`comparison_gate.py`, `gate_invocation.py`, `receipt_integrity.py`, the registries,
`PROGRAM_STATE.json` and everything under `stage2a/` were opened read-only and are byte-unchanged.
No git command other than `rev-parse --abbrev-ref HEAD` was run.

### Why a wrapper and not a gate amendment

`GATE_INVOCATION_CONTRACT.md` sections 7.2-7.3 already say this in the abstract: the feature gate
"audits one matrix" and "sees the assembled matrix, not how it was built". The fan-out this node
blocks produces a matrix that is entirely innocent to every check `feature_gate.audit` performs —
no duplicate column, no collinearity, no rank deficiency, no informative null mask. The corruption
is in the **row universe**, which is not a property of a design matrix. The check therefore belongs
at the merge call site, which is where the row universe still exists as an object.

---

## 2. Inputs, by hash

Computed with
`python -c "import hashlib,pathlib; print(hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest())"`:

| path | sha256 | bytes |
|---|---|---|
| data/reference/team_cities.csv | 10a544fdc52a9c80c1573437c9838b11815c9eafe6ac2cf052be17a2128ac42d | 1892 |
| experiments/player_program/projected_exposure_v1/team_possession_prior_v1.parquet | c37c075148553920b79c9320ea03afb37986bfc752fc84dd695f154887c3db18 | 44025 |
| experiments/player_program/stage2a/V2_STOP_CONDITION.json | a4dd090b2b38dfb4d37028e15daa10c689deb27269cde3d8b9cddd12fd92244d | 14555 |
| experiments/player_program/stage2a/EVIDENCE_PACKET_V2.json | 3a35ae735333c47713d6e7cc4c35c081e4eb07364c71cba744db03709730a32c | 30883 |

**Scope note, stated rather than glossed.** The node's declared read scope is
`experiments/player_program/`. `data/reference/team_cities.csv` is outside it. That read is
unavoidable: acceptance criterion 5 is stated about `team_id` 1611661317, which exists nowhere
inside `experiments/player_program/`. The file was read read-only and its hash is recorded above so
the read is auditable. No write occurred outside
`experiments/player_program/stage2b/P23_DIMENSION_CARDINALITY_GUARD/`.

---

## 3. What I measured

Every figure below was produced by `TESTS.py` against the bytes hashed in section 2 and is
reproduced in `TEST_RESULTS.json` under `measurements`. Nothing is quoted from the packet. Where
`V2_STOP_CONDITION.json` S2 states a figure I mark **AGREE** or **CORRECT**.

### 3.1 Re-derivation of S2's dimension measurements — TESTS.py::t09

`measurements.S2_dimension`:

| quantity | S2 states | I measure | verdict |
|---|---|---|---|
| rows | 16 | **16** | AGREE |
| distinct_team_id | 15 | **15** | AGREE |
| duplicated_team_id | {1611661317: 2} | **{1611661317: 2}** | AGREE |
| last_season_dtype | float64 | **float64** | AGREE |
| last_season_nulls | 15 of 16 | **15 of 16** | AGREE |
| elevation_ft_range | [20, 2030] | **[20, 2030]** | AGREE |
| venues_above_1000ft | 4 | **4 rows / 3 distinct arenas** | **CORRECT — see 5.1** |

### 3.2 Re-derivation of the row universe — TESTS.py::t10

`measurements.universe`:

* `projected_exposure_v1/team_possession_prior_v1.parquet` = **2,990 rows over 1,495 game_ids**;
* restricting to `pace_resolved == True` gives **2,982 rows over 1,491 game clusters** — the
  universe named in the brief. **AGREE** with the 2,982 / 1,491 figure, and the restriction that
  produces it is `pace_resolved`, matching `possession_features.py:292`
  (`F = F[F["pace_resolved"].astype(bool)]`);
* duplicate (game_id, team_id) keys in the universe: **0**. The universe is a clean 1:1 team-game
  frame, and exactly 2 rows per game_id for all 1,491 clusters (t16);
* distinct team_id: **15**; seasons **2021-2026**; distinct (team_id, season) pairs: **76**;
* rows carrying team_id 1611661317: **246**.

Both figures are reported together throughout, per the standing rule.

### 3.3 The naive join, measured on the real bytes — TESTS.py::t11

`measurements.naive_join`. Command in the test:
`u.merge(tc, on="team_id", how="left")` where `u` is the 2,982-row universe.

| quantity | measured |
|---|---|
| universe rows before | 2,982 |
| rows after naive left merge | **3,228** |
| excess rows | **+246** |
| game clusters after | **1,491 — unchanged** |
| duplicated (game_id, team_id) keys after | **246** |

S2's mechanism claim is **AGREE**, and quantified: the fan-out is exactly the 246 Phoenix team-game
rows, doubled. The game_id count is *unchanged* at 1,491, which is the reason this defect is
dangerous — a guard that only counts games sees nothing. Only the row count and the team-game key
multiplicity move. `merge_guard.RowUniverse` asserts all three, which is why it catches it.

`guarded_merge` rejects this merge with a message naming 1611661317 (t11, `guard_rejected: true`),
and `RowUniverse.assert_unchanged` rejects the already-merged frame independently
(`row_universe_assertion_rejected: true`). The two mechanisms are deliberately redundant: the
primary-key check fires before the merge, the universe assertion after it, so bypassing one does
not get a corrupted frame through.

### 3.4 The null-unsafe filter, measured — TESTS.py::t12

`measurements.null_unsafe_filter`:

| quantity | measured |
|---|---|
| dimension rows | 16 |
| rows surviving last_season.notna() | **1** |
| distinct franchises lost | **14** of 15 |
| universe rows after inner-joining that survivor | **246** |
| universe rows lost | **2,736** of 2,982 |

S2's claim that a null-unsafe filter drops every current franchise is **AGREE** and now quantified:
91.75% of the universe is destroyed, and the 246 rows that survive are — with a bitter symmetry —
the *same* Phoenix rows that the other failure mode duplicates.

### 3.5 The sanctioned resolution — TESTS.py::t13

`measurements.season_effective_resolution`. The declared spec:

    DimensionSpec(
        name="team_cities__season_effective",
        left_keys=("team_id", "season"), right_keys=("team_id", "season"),
        cardinality="m:1",
        value_columns=("abbreviation","franchise","city","arena","lat","lon",
                       "elevation_ft","timezone"),
        require_total_coverage=True,
        effective_from="first_season", effective_to="last_season", effective_on="season",
        open_ended_upper_bound=True)

| quantity | measured |
|---|---|
| required (team_id, season) pairs | **76** |
| resolved dimension rows | **76** |
| pairs matching **no** interval | **0** |
| pairs matching **more than one** interval | **0** |
| multi-row natural keys resolved | ["1611661317"] |
| merged rows | **2,982** |
| merged game clusters | **1,491** |
| merged team-game keys | **2,982** |
| fan-out rows | **0** |
| null expansion | **none** |
| unmatched fact rows | **0** |

The Phoenix split falls out of the declared intervals alone:

| season | resolved abbreviation |
|---|---|
| 2021, 2022, 2023, 2024 | PHO |
| 2025, 2026 | PHX |

which is exactly PHO [first_season 2021, last_season 2024] and PHX [first_season 2025, last_season
null -> open]. The two intervals are contiguous and non-overlapping, with no gap and no double
cover, and the resolver verifies that rather than assuming it.

### 3.6 Order-independence — TESTS.py::t14

`measurements.order_independence`. The dimension was permuted with
`tc.sample(frac=1.0, random_state=seed)` for 8 seeds; the resolved (team_id, season) ->
(abbreviation, elevation_ft, timezone) map was **identical every time**. By contrast,
`drop_duplicates("team_id", keep="first")` and `keep="last"` disagree on **1** key — 1611661317 —
so the arbitrary-order shortcut is measurably not a no-op here. It resolves every pre-2025 and
every post-2025 Phoenix row to the same abbreviation, which is wrong for one side whichever value
of keep is chosen.

`assert_no_order_dependent_dedup` scans `merge_guard.py` for drop_duplicates, keep=first/last,
.first(), .last(), .nth(, .head(, .tail(, .idxmin/.idxmax(, .iloc[0] and .sort_values( and finds
**0** hits outside comments (t08). The scanner is itself tested against a probe file containing
those constructs, so a silent scanner is not mistaken for a clean module.

---

## 4. Acceptance criteria, against evidence

| criterion | where enforced | where demonstrated |
|---|---|---|
| every dimension merge declares explicit keys and expected cardinality | DimensionSpec.__post_init__ rejects an invalid/absent cardinality, key-arity mismatch, empty keys, empty value_columns, partial interval declaration | t01 — 5 invalid specs rejected |
| row count, game key set and team-game key set are asserted unchanged | RowUniverse.capture / .assert_unchanged, called inside guarded_merge | t04 (all mutation kinds detected), t13 (2,982 / 1,491 / 2,982 preserved on real data) |
| duplicate primary keys are rejected and fan-out fails the merge | check_dimension_primary_key before the merge; pandas validate="m:1"/"1:1"; assert_unchanged after | t02, t03, t11 |
| null expansion is reported | null_expansion_report, split into nulls from unmatched fact rows vs nulls already in the dimension | t05 (4 from dimension values, 4 from unmatched rows), t13 (real merge: none) |
| 1611661317 resolved ONLY from documented effective-date/season semantics, else EXCLUDE | resolve_effective_dimension uses first_season/last_season and nothing else; raises AmbiguousDimensionError whose message instructs exclusion on 0 or >1 interval matches; UndeclaredNullIntervalError on an undeclared null endpoint | t06, t07, t13, t14 |
| deduplication by arbitrary first/last row order is not used anywhere | absent by construction; assert_no_order_dependent_dedup proves absence by source scan | t08, t14 |

On criterion 5 specifically: the resolution **succeeded**, so the exclusion branch was not taken on
this dimension. The exclusion branch is nonetheless implemented and tested (t07 — overlapping
intervals and uncovered pairs both raise, with EXCLUDE in the message), because a criterion that is
only satisfied when the data happens to cooperate is not satisfied.

---

## 5. Contradictions found

### 5.1 V2_STOP_CONDITION.json S2: "4 venues above 1000 ft" is a **row** count, not a venue count

S2 records: "The source also reports elevation as a dead feature: I measure 4 venues above 1000 ft,
not 3 -- a minor discrepancy, and the substantive point stands."

Measured (t09): **4 rows**, **3 distinct arenas**, **3 distinct franchises**. The fourth row is the
second Phoenix row. PHO and PHX are the *same building* — Footprint Center, identical
lat/lon/elevation_ft — split across two rows by the rebrand.

The original source's **3 is correct** as a count of venues; the coordinator's 4 counts rows. This
is not a nit. It is the S2 fan-out defect **occurring inside the measurement that documents the S2
fan-out defect**: a team_id-keyed frame was counted as though it were venue-keyed, and the
duplicated key inflated the count by exactly one. The coordinator's own note on S8 — "I curated a
table by hand and did not reconcile it against the schema I had already dumped" — has the same
shape. V2_STOP_CONDITION.json is frozen and was **not** edited; this is raised, not reconciled.

Consequence: any downstream statement of the form "N venues above 1000 ft" must be recomputed on
distinct venues. It does not disturb the substantive point that the elevation *spread* is narrow.

### 5.2 EVIDENCE_PACKET_V2.json lists 9 of the 11 columns of team_cities.csv

The packet's cutoff_valid_availability_table_CORRECTED.CORRECTED_now_available[0].source reads
"data/reference/team_cities.csv (16 rows: team_id, franchise, first_season, last_season, city,
arena, lat, lon, elevation_ft)".

Measured (t15): the file has **11** columns. **abbreviation and timezone are omitted** from the
packet's listing. The row count (16) **AGREES**.

timezone is the material omission: the same packet entry names "venue, travel distance, elevation,
**time zone**" as the promoted feature family, so the packet promotes a family on the strength of a
column its own schema listing does not mention. This is S8's failure mode — a curated list not
reconciled against the schema — recurring on the venue source. Again: raised, not edited.

### 5.3 first_season / last_season are documented by name only

There is no data dictionary for team_cities.csv anywhere under `experiments/player_program/`. The
"documented effective-date or season semantics" that criterion 5 requires are the **column names
themselves plus their observed values**: first_season is int64 with 0 nulls; last_season is float64,
null on 15 of 16 rows, and non-null exactly on the one row whose successor row's first_season is the
next season. That is a *coherent* reading and the only one consistent with the bytes — the intervals
are contiguous, non-overlapping, and cover all 76 required (team_id, season) pairs with multiplicity
exactly 1 — but it is an inferred reading of an undocumented schema, not a citation of a written
specification. Stated plainly so it is not mistaken for stronger provenance than it has. The guard
makes the reading **explicit and refutable**: open_ended_upper_bound=True is a declaration the
caller must write down, and if the reading were wrong the interval checks would have to fail
somewhere, and they do not.

---

## 6. What I could NOT establish

1. **That the venue/elevation/timezone family is scientifically usable.** Out of epistemic scope by
   the status line above, and out of mandate. This node establishes joinability only.
2. **Cutoff validity of anything.** Untouched. Per GATE_INVOCATION_CONTRACT.md section 7.3,
   construction provenance is not delegated to any gate, and it is not delegated to this one either.
3. **That other dimension merges in the program are safe.** I audited exactly one dimension —
   team_cities.csv — because that is what S2 names. master_team.parquet, the injury sources, and the
   possession/rotation artifacts were **not** audited for merge cardinality. merge_guard.py is
   written to be applied to them; it has not been. Their key uniqueness is an **open question**, not
   a passed check.
4. **Whether season is the correct effective-date grain.** first_season/last_season are seasons, and
   the universe carries season, so the resolution is grain-consistent. A mid-season venue or identity
   change could not be represented in this schema at all, and I have no evidence about whether one
   ever occurred. If one did, it is invisible to both the file and this guard.
5. **The provenance of team_possession_prior_v1.parquet itself.** possession_features.py:156 already
   records that its receipt "does not re-establish the construction provenance" of that artifact. I
   take its 2,982 pace_resolved rows as the universe on the same footing the rest of the program
   does; I did not re-derive them from possessions.
6. **Whether the packet's other schema listings are complete.** I checked the one entry S2 concerns
   (5.2). Given that this is the third instance of the same curation failure (venue, injury, S8's 32
   possession columns), a systematic reconciliation of every packet listing against its schema is
   warranted. That is not this node's mandate and I did not attempt it.

---

## 7. Stop conditions

**None tripped.** Stated explicitly against each protected object:

| protected object | effect of this node |
|---|---|
| primary target | untouched. No target is read, written or referenced. |
| K0 structure | untouched. Neither K0_FLAT nor K0_MATCHED is constructed or altered. |
| inference structure | untouched. No fold, bootstrap or estimator is defined. |
| candidate universe | **preserved and now enforced.** 2,982 rows / 1,491 clusters, asserted identical across the merge. The node's entire purpose is that this cannot change silently. |
| cutoff-valid feature set | untouched. No field is promoted, demoted or adjudicated. S2's unresolved:true is *not* cleared by this node. |
| leakage status | untouched. |

S2 remains **unresolved as an adjudication**. What changed is narrower and should be described
narrowly: the specific hazard S2 names — "a naive join fans out 1:m and duplicates that franchise's
rows" — is now blocked by an enforced invariant with a passing test, and the resolution path S2
implies is now implemented and measured. Whether the venue family should be *used* is a scientific
question this node does not touch.

### One item raised rather than resolved — TESTS.py::t16

team_cities.csv carries **no game-level key** (no game_id, no is_home, no home_team_id), and the
2,982-row universe artifact carries **no is_home and no opp_team_id** (measured; the universe's 11
columns are game_id, team_id, game_date, season, season_type, pace_level, pace_source,
n_history_games, team_pace_estimate, projected_team_off_possessions, pace_resolved).

A team_id-keyed venue merge therefore attaches each team **its own** arena on **every** row,
including its 1,491 away team-game rows. It answers "which arena does this franchise call home in
this season", not "where was this game played". Any elevation, altitude, travel-distance or
timezone-shift feature needs the latter, and building it requires a home-team or opponent key that
this artifact does not carry — projected_team_rotations_v1.parquet does carry opp_team_id, but
joining it is an additional merge that is itself in scope for this guard and that I have not
performed.

This is not a stop condition: it changes no target, control, universe or adjudication. It is a
**construction constraint on how a venue feature family could be built**, and per the standing rules
I raise it rather than resolve it inside the node. It does not alter the 3.5 result — the
season-effective merge is cardinality-safe regardless of what the imported columns *mean*.

---

## 8. Preserved negative results

* The exclusion branch of criterion 5 was **not exercised on real data**, because the real data
  resolved cleanly. Reported as a fact about the data, not as a strengthening of the guard.
* No dimension other than team_cities.csv was found to require interval resolution, because no other
  dimension was audited (6.3). Absence of findings elsewhere is absence of looking.
* elevation_ft has **3** distinct venues above 1000 ft over a **[20, 2030]** ft range. I make no
  claim about whether that is enough spread for a feature; S2 records a source calling elevation
  dead, and I neither confirm nor refute it — doing so would require fitting.
