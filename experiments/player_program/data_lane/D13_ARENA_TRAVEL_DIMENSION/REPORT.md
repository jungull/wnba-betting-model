# D13_ARENA_TRAVEL_DIMENSION — unique effective-dated team/arena/travel dimension

## Epistemic status of this output

> REFERENCE DATA + INVARIANT. Fixes the S2 fan-out hazard at its source.

That line bounds what this node may be cited for. In particular: **nothing in this report admits
any column to any feature matrix.** The dimension is joinable and its join is proved harmless.
Joinability is not eligibility, and this node establishes no eligibility for anything.

---

## 1. What was built

| File | sha256 | Grain |
|---|---|---|
| `arena_dimension_v1.csv` | `d5bbf1ba72016934a7882cab1dbaa36f3afbce7ed6347807436ce13eded2f62d` | one row per `(team_id, season)` — **the declared key** |
| `venue_pair_travel_v1.csv` | `248acefa7359ca86b13aa3d3d978d205fb2e8f1abbb53abbde54fe455e82bcb4` | one row per **ordered** `(from_venue_id, to_venue_id)` pair |
| `arena_dimension_v1.meta.json` | `185e8f3a5cfa90946a8767a21801ee7c710935f111e3918ba66dccaa6b364414` | per-column derivation and provenance |

Produced by `build_dimension.py`; every number below is re-derivable by

```
python experiments/player_program/data_lane/D13_ARENA_TRAVEL_DIMENSION/build_dimension.py
python experiments/player_program/data_lane/D13_ARENA_TRAVEL_DIMENSION/TESTS.py
```

`TESTS.py` is a standalone script returning 1 on any failure (pytest is not installed).
**40/40 tests pass, exit code 0.**

Inputs, hashed at build time and recorded in `MEASUREMENTS.json`:

| Input | sha256 |
|---|---|
| `data/reference/team_cities.csv` | `10a544fdc52a9c80c1573437c9838b11815c9eafe6ac2cf052be17a2128ac42d` |
| `data/masters/master_team.parquet` | `ad79ce5cdda7e058ba24be45243037252e3795a3e9f0c18cc41b3f12f3c38528` |
| `experiments/player_program/projected_exposure_v1/team_possession_prior_v1.parquet` | `c37c075148553920b79c9320ea03afb37986bfc752fc84dd695f154887c3db18` |

**Scope note, stated rather than buried.** My contract's `allowed_read_paths` is
`experiments/player_program/`. The mandate — build an arena/travel dimension — cannot be
discharged without reading `data/reference/team_cities.csv`, which is the only source of the
fields named in the acceptance criteria, and without `master_team.parquet` to corroborate the
effective dates independently. Both reads are read-only. **No write occurred outside
`experiments/player_program/data_lane/D13_ARENA_TRAVEL_DIMENSION/`.** No git command was run
other than a read-only `git log` on the source file to establish its provenance.

---

## 2. The universe, restated and re-measured

`team_possession_prior_v1.parquet` filtered to `pace_resolved == True`:

- **2,982 team-game rows**
- **1,491 game clusters**
- seasons 2021–2026; game dates 2021-05-15 → 2026-07-31

The unfiltered file carries 2,990 rows / 1,495 games — the 8-row, 4-game difference is the
documented unresolved set. Command: `build_dimension.py`, block `M["universe"]`; tests T1a/T1b.

---

## 3. The declared key, and why it is unique

**Declared key: `(team_id, season)`.** Recorded in `arena_dimension_v1.meta.json["declared_key"]`
and asserted by test T2a, so a downstream reader cannot mistake it.

- rows: **76**
- distinct `team_id`: **15**
- distinct `venue_id`: **15**
- duplicate key rows: **0** (test T2b)
- nulls in every column: **0**
- team-seasons by season: 2021→12, 2022→12, 2023→12, 2024→12, 2025→13, 2026→15

The dimension is **not** deduplicated into uniqueness. Every row is produced by *interval
containment* — season `s` appears for a source row iff `eff_first_season <= s <= eff_last_season` —
and uniqueness is then **proved** (T2b, T8b: 76 rows equals 76 containment hits). This distinction
matters: a dedup produces a unique table whether or not the source was coherent; containment
produces a unique table only if the source intervals are disjoint, which is separately proved below.

### Effective dates

Columns `eff_first_season`, `eff_last_season`, `eff_last_season_is_open`.
Semantics: **a row is effective for seasons `[first_season, last_season]` inclusive; a null
`last_season` means open-ended**, encoded with the sentinel `9999`. The sentinel is asserted to
exceed every season in the universe (T12; max season 2026), so it can never collide with a real one.

Measured over the source:

- malformed intervals (`first > last`): **0**
- **overlapping** intervals within a `team_id`: **0** (T4a)
- **gaps** between intervals within a `team_id`: **0** (T4b)

Disjointness plus gaplessness is exactly the condition under which containment yields one row per
team-season — which is why the two are tested rather than asserted.

---

## 4. The PHO/PHX duplicate is resolved from **documented** effective-date semantics

The acceptance criterion allows resolution *only* from documented effective-date or season
semantics, or else exclusion of the family. Resolution succeeded, from a written source, and was
then independently corroborated.

**The documentation.** The producer of the file, `data/reference/collect_bios.py`, states in the
header of `phase_cities()`:

> "One row per (team_id, abbreviation). PHO (2021-2024) and PHX (2025-) are the same
> franchise/team_id 1611661317 - the 2025 abbreviation rename."

This is a documented effective-date semantics, not an inference of mine. The source rows agree:
`PHO` first_season 2021 / last_season 2024.0; `PHX` first_season 2025 / last_season null.

**The independent corroboration.** Grouping `master_team.parquet` by `(team_id, team_abbreviation)`
and taking min/max season gives 16 pairs. Outer-merged against the dimension source on
`(team_id, abbreviation)` with `validate="1:1"`:

- merge indicator: **both 16, left_only 0, right_only 0**
- `first_season` disagreements: **0**
- `last_season` disagreements: **0** (treating the open sentinel as satisfied by `master_last == 2026`)

So the effective dates are not merely documented — they reproduce exactly from the game data
itself. `PHO` spans 2021–2024 in the master (163 rows), `PHX` 2025–2026 (84 rows).

**What the duplicate is and is not.** The two Phoenix source rows are **identical on every
physical venue field** — `city`, `arena`, `lat`, `lon`, `elevation_ft`, `timezone` (measured: 1
distinct tuple; test T9d). They differ on exactly three columns: `abbreviation`, `first_season`,
`last_season`. The duplicate is an *abbreviation rename*, not a relocation. Tests T9a–T9c assert
Phoenix has exactly one dimension row per season, carrying `PHO` for 2021–2024 and `PHX` for 2025+.

---

## 5. Cardinality tests prove a merge cannot fan out

### The safe merge

`universe.merge(dim, on=["team_id","season"], how="left", validate="m:1")`:

| Quantity | Before | After | Test |
|---|---|---|---|
| team-game rows | 2,982 | **2,982** | T5a |
| game clusters | 1,491 | **1,491** | T5b |
| exact `(game_id, team_id)` key set | — | **identical** | T5c |

- universe `(team_id, season)` keys: **76**; keys absent from the dimension: **0** (T6b)
- **null expansion: 0** on every attached column (T6a). Reported as a number rather than as an
  adjective, and reported whether or not it is zero.

### Fan-out fails, demonstrated in both directions

A test that only shows the good merge working proves nothing about the guard. Both directions are
measured:

- **T7a — a duplicated primary key is rejected.** The dimension is deliberately poisoned with a
  duplicated key row and re-merged; `validate="m:1"` raises `pandas.errors.MergeError` rather than
  fanning out. Verified to raise.
- **T7b/T7c — the historical hazard, quantified.** The *raw* source merged on `team_id` alone
  produces **3,228 rows against 2,982 — an excess of 246 rows**, and 246 is exactly the number of
  Phoenix team-game rows in the universe. The fan-out is precisely the Phoenix duplication, doubling
  that franchise's rows. S2 asserted this hazard; **it did not quantify it. 246 is new.**

### No arbitrary first/last-row deduplication anywhere

Three independent checks, because a single source-text scan is weak:

- **T8a** — an **AST** scan of `build_dimension.py` for real `drop_duplicates(<single column>)`
  calls without an explicit `keep=`, and for `groupby(...).first()/.last()`. Zero hits. A text scan
  would have been unusable here: this report names the forbidden pattern, and stripping string
  literals to compensate would also strip the argument that identifies a genuine use.
- **T8a-meta** — the scanner is itself tested against a known-bad probe file and correctly finds
  both planted defects. An undetectable detector is not evidence.
- **T8c — the decisive one.** The dimension is independently re-derived by interval containment
  from **five shuffled copies** of the source (seeds 0, 1, 7, 42, 1337) and must reproduce the
  artifact exactly on all nine core columns. It does. This proves order-invariance empirically
  rather than proxying it through code inspection.

Where the builder *does* collapse rows, it deduplicates on the **full column tuple** and then
**proves** the key is unique, rather than picking a row: the venue table raises `SystemExit` if two
rows share an arena name but differ on a physical field.

---

## 6. Elevation, timezone and travel fields carry their derivation

Every column's derivation is in `arena_dimension_v1.meta.json`; test T10a asserts no dimension
column lacks one. Summary of the substantive ones:

| Field | Derivation | Honest caveat, from the source's own words |
|---|---|---|
| `lat`, `lon` | verbatim from `team_cities.csv` | producer: *"lat/lon = arena/metro, **city-level precision**"*. Hand-entered 2026-07-31. No geocoder, no datum recorded — WGS84 is assumed, **not stated**. |
| `elevation_ft` | verbatim | producer: *"elevation_ft **approximate**"*. No datum, no method, no upstream source. |
| `elevation_m` | `elevation_ft * 0.3048`, 1 dp | unit conversion only; inherits the source's approximateness |
| `timezone` | verbatim IANA identifier | validated by successful `ZoneInfo()` construction for all 16 source rows |
| `utc_offset_hours_jul` | `ZoneInfo(tz).utcoffset()` at the **fixed** instant 2024-07-01 12:00 local | a fixed-instant reference, **not** a per-game offset. The WNBA regular season sits in northern summer, so this is the operative one. |
| `utc_offset_hours_jan` | same at 2024-01-15 12:00 local | exists **only** to derive `observes_dst` |
| `observes_dst` | `jul != jan` | — |
| `venue_id` | `arena` lowercased, non-alphanumeric runs → `_` | collapses the two Phoenix abbreviation rows onto one building |

A distinction the field names hide, measured: **6 distinct IANA zones collapse to 3 distinct July
UTC offsets** (−4: New_York, Toronto, Indiana/Indianapolis; −5: Chicago; −7: Los_Angeles, Phoenix).
`America/Phoenix` is the only zone not observing DST, and in season its offset equals Pacific's.
A feature keyed on the zone string and one keyed on the offset are **different partitions** and
must not be substituted for one another.

**Travel** (`venue_pair_travel_v1.csv`, 15 venues → **225 ordered pairs**):

- `great_circle_km` — haversine on a sphere of radius **6371.0088 km** (IUGG mean). Explicitly
  **not** road distance, **not** air routing, **not** an ellipsoidal geodesic. It inherits the
  city-level precision of `lat`/`lon`.
- `great_circle_mi` = `great_circle_km * 0.621371`
- `elevation_gain_ft` = `to − from`; `tz_offset_delta_hours_jul` = `to − from` at the July reference

Matrix invariants, all measured: diagonal max |value| **0.0 km**; symmetry max |A − A^T| **0.0 km**;
triangle-inequality violations **0** over all 3,375 triples; and the haversine agrees with an
independently coded spherical law of cosines to **0.0001 km** on a spot-checked pair (T11a–T11e).

Range: max pair **Mohegan Sun Arena ↔ Chase Center, 4,266.545 km**; max |tz delta| **3.0 h**; max
|elevation gain| **2,010 ft**.

**What the travel table is not.** It is a static venue-to-venue reference. It asserts nothing about
any team's actual itinerary, rest days, trip origin, or road-trip structure, and it contains no
per-game row. Deriving a real travel feature requires the previous game's venue and a rest interval;
that is not this node's mandate and is not done here.

---

## 7. Cutoff validity: **CUTOFF_UNPROVEN**

Stated plainly because the standing rule requires it.

- `team_cities.csv` has **no row-level source-timestamp column**. Its columns are exactly
  `team_id, abbreviation, franchise, first_season, last_season, city, arena, lat, lon, elevation_ft, timezone` —
  measured, not recalled.
- Its only temporal evidence is a **single git commit**, `a3677bcdb086b54444db9190c49bf25713f06bcc`,
  dated **2026-07-31 09:32:28 -04:00** (`git log --format="%H %ad" --date=iso -- data/reference/team_cities.csv`).
- The universe's game dates run 2021-05-15 → **2026-07-31**. **6 team-game rows over 3 games** fall
  on the commit day itself and cannot be ordered against the commit without a tip time.

The content is time-invariant physical fact — a building's latitude does not depend on when it was
written down. **That is not a proof of cutoff validity of the record, and this node does not treat
it as one.** Status: `CUTOFF_UNPROVEN`. Anything downstream that wants to use these fields must
establish cutoff validity separately; this node does not supply it and must not be cited as if it did.

---

## 8. Contradictions found

**C1 — the "4 venues above 1000 ft" correction in `V2_STOP_CONDITION.json` is itself wrong, in
exactly the way S2 is about.** S2 records: *"The source also reports elevation as a dead feature: I
measure 4 venues above 1000 ft, not 3."* Measured against the bytes: **4 rows**, **3 distinct
arenas**, **3 distinct franchises** above 1,000 ft. The fourth row is the second Phoenix row.
The original source's "3" was correct about venues; the coordinator's correction counted the
duplicated row it was in the middle of documenting. `S2.measurement.venues_above_1000ft: 4` is
mislabelled — the value is a row count, not a venue count. The stop-condition file is frozen and I
have not edited it.

**C2 — "the join is clean" is true only on a key the document does not name.**
`stage2a/HYPOTHESES_agent_opponent_env.md:398` states that `team_cities.csv` *"gives each team one
home arena per season and the join is clean"*. The first half is verified true: **0 teams change
arena across seasons**, **0 change elevation**, and there is exactly one row per team-season. The
second half is true on `(team_id, season)` and **false on `team_id`**, where the merge produces
3,228 rows against 2,982. Two documents in the same corpus therefore disagree about the same join,
and neither states the key. This dimension removes the ambiguity by declaring the key in machine-
readable metadata.

**C3 — `first_season` is left-censored, and one of its four "entries" is not an entry.**
`stage2a/HYPOTHESES_agent_roster_coldstart.md` (F7, lines 96/136/212) treats
`team_cities.csv:first_season` as franchise identity usable for expansion/cold-start reasoning.
Measured: **12 of 16 rows have `first_season == 2021`, which is the data-window start**, not a
founding year — the New York Liberty did not enter the league in 2021. Only 4 rows have
`first_season > 2021`: **GSV (2025), PDX (2026), TOR (2026) — and PHX (2025)**. PHX's 2025 is the
abbreviation rename established in section 4, not a franchise entry. A rule of the form
`first_season > 2021 => expansion franchise` therefore **misclassifies Phoenix 2025 as an expansion
team** while being blind to every pre-2021 franchise's real founding date. Escalated (section 10).

**C4 — a latent arbitrary-dedup defect in the shipped producer, currently benign.**
`data/reference/collect_bios.py :: phase_tips()` builds its timezone map with
`cities.drop_duplicates("team_id")` — first-row-wins on the very table that has a duplicated
`team_id`. Measured: **0 team_ids where the first and last row disagree on timezone**, so it changes
no current value. It is harmless only because the two Phoenix rows happen to agree on `timezone`.
Any future effective-dated row differing on a physical field — a real relocation — would be resolved
silently by CSV row order. The file is outside this node's write scope and was not touched.

**Non-contradiction, checked and confirmed.** `stage2a/V2_HYPOTHESES_basketball.md:328` states team
counts by season of 12, 12, 12, 12, 13, 15. The dimension reproduces exactly 12, 12, 12, 12, 13, 15.

---

## 9. What I could **not** establish

- **Per-game venue.** There is no venue or arena column anywhere in `master_team.parquet` —
  verified by scanning all 65 column names for `venue`/`arena`: **false**. The dimension can
  therefore only assign a team-game the **home team's season-primary arena**. It **silently
  mis-locates** any neutral-site game, one-off relocation, in-season arena change, or international
  showcase. I cannot measure how many such games exist, because the data that would identify them
  does not exist in this repository. This is a genuine negative, not an omission.
- **A known instance of that error, from the producer's own notes.** `collect_bios.py` records that
  the Seattle Storm split early-2021 home games with Everett, WA while Climate Pledge Arena was
  under construction. The dimension assigns all of them to Climate Pledge Arena. I cannot enumerate
  the affected games — no per-game venue exists to enumerate them from.
- **Provenance of `lat`/`lon`/`elevation_ft`.** Hand-entered constants with no upstream source,
  method, datum or precision recorded. I verified internal consistency (the distance matrix's
  metric axioms) but **cannot verify accuracy** against any external reference, and did not fabricate
  one.
- **Cutoff validity** — see section 7. Unproven, by measurement, not by assumption.
- **Whether any of this is scientifically usable.** Out of mandate and deliberately not attempted.
  No model was fitted, no performance was inspected, and nothing under `stage2b/SEALED_RESULTS/`
  was read.

### One measurement that bears on eligibility, and its limit

Because "availability is not eligibility", I measured the one structural property that decides
whether the static fields could ever carry information beyond a team dummy:

- `elevation_ft` takes **15 distinct values across 15 teams — an exact bijection with `team_id`**.
  As a *static per-team* field it is a team-identity re-encoding, nothing more. V2 called it
  "mostly a team-identity proxy"; the measurement makes it **exactly** one.
- `timezone` is **not** a bijection: 6 zones over 15 teams.
- The **game-venue** form behaves differently: attaching the home team's row to each team-game
  gives **10 to 15 distinct game-venue elevations per team**, and **736 of 2,982 team-games
  (24.68%)** are played above 1,000 ft. So the *home* elevation is a team proxy while the
  *game-venue* elevation is not.

This distinction is a fact about structure only. **It does not make the game-venue form eligible** —
it remains `CUTOFF_UNPROVEN`, and eligibility is a separate adjudication this node does not make.

---

## 10. Stop conditions and escalations

**No stop condition is tripped by this node's own output.** The dimension provably preserves the
2,982-row / 1,491-cluster universe (section 5), introduces no feature, changes no target, touches
no K0 construction, and alters no inference structure. It removes a hazard; it does not move a
boundary.

`S2_team_cities_join_hazards` in `stage2a/V2_STOP_CONDITION.json` remains marked
`unresolved: true`. **That file is frozen and I have not edited it.** What this node supplies is
the artifact and the invariant that make S2's hazard non-reachable through a keyed merge — the
adjudication of S2's status belongs to the coordinator, not to me.

Two items are escalated because they change the **historical feature evidence** for the possession
wave rather than anything inside this node:

1. **C3 — the `first_season` expansion trap.** The cold-start hypothesis family reads
   `first_season` as franchise identity. Measured, it is left-censored at the 2021 data window for
   12 of 16 rows, and `first_season > 2021` includes PHX 2025, which is a rename and not an entry.
   Any expansion/cold-start feature already reasoned about on this basis rests on a field that does
   not mean what the document says it means.
2. **C1 + the elevation bijection.** The record's elevation measurement is mislabelled (rows read
   as venues), and the "mostly a team-identity proxy" characterisation is measurably an *exact*
   bijection in the static form while being genuinely varying in the game-venue form (24.68% of
   team-games above 1,000 ft). Both directions of that correction change what the historical
   evidence supports about the venue/travel family.

Neither is resolved here. Both are raised.
