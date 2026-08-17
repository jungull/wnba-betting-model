# E1_I0052 — identity key divergence in the research lane

**What was asked.** E1_I0048 found that 196 of 1,940 roster windows in 2021–2024 (10.1 %) differ
depending on whether the roster is keyed on `player_name` or `player_id`, and named thirteen
identities carrying two spellings. That measurement was on the shipped path. **Nobody had chased
it into the research lane** — the screens, master tables, contract builders and joins that every
finding in this programme rests on.

**What was found.** The research lane is keyed on `player_id`, and inside every frame the
programme owns, nothing diverges. The exposure that does exist lives at feed boundaries, where the
source carries no stable key.

---

## 1. Method — why this is not a grep

The brief was explicit: resolve the call graph, do not search for the word "name". Four passes,
each able to catch what the previous one would miss.

**Pass 1 — AST census of keyed operations** (`scripts/s01_keyscan.py`). Every `.py` under
`experiments/exploration` and `experiments/player_program` is parsed with `ast` and every `Call`
node whose method is `merge / join / groupby / drop_duplicates / duplicated / set_index /
sort_values / pivot / pivot_table / unstack / map / isin / unique / nunique / value_counts /
factorize / reindex / transform / agg` is recorded **with its key columns**, recovered from
`on= / left_on= / right_on= / by= / subset= / keys= / index= / columns=`, from positional
arguments, and from the receiver column for column-level operations. A per-file constant table
folds module-level `KEY = [...]` bindings. **The search term is "keyed operation", not "name";
name-keying is a classification of the recovered keys.**

902 files, **0 parse failures**, 6,672 keyed operations, of which **4,340 are structural**
(join / groupby / dedup / set-index / pivot / lookup / membership / unique).

**Pass 2 — artifact census** (`scripts/s05_artifact_census.py`). A call graph cannot see keying
imposed by a *schema*. Every persisted `.parquet` / `.csv` in the lane — **830 frames** — is
classified by the identity columns it carries. A frame with a name and no id forces name-keying on
every consumer no matter what the code says.

**Pass 3 — key-variable resolution** (`scripts/s13_varkeys.py`). 872 structural operations hold
their key in a variable. Rather than write them off, every assignment in the lane whose target is a
key-shaped name (`key`, `keys`, `KEY`, `gk`, `pk`, `kk`, `by`, `grp`, `keycols`, `entity_cols`, …)
is recovered by AST and inspected. **310 bindings across 194 files. Zero name a player-name
column.**

**Pass 4 — residual scoping and hand adjudication** (`scripts/s12_residual.py`). An unresolvable
key is only dangerous on a frame where an identity is *actually* ambiguous. Sixteen frames
qualify, owned by eleven screens, containing **70 unresolved structural operations** — all printed
with source context and read individually. Every one resolves to `[player_id, season]`,
`[game_id, team_id, player_id]`, `[season]`, or a non-player grouping.

---

## 2. Anchors reproduced before any new statistic

Twelve declared in `PREREG.md` §4. **Ten reproduce exactly; two do not, and both are explained.**

```
A1   master_player rows, all seasons              expect 34199  got 33712  MISMATCH
A2   null player_id rows                          expect     0  got     0  EXACT
A3   player_id dtype                              expect Int64  got Int64  EXACT
A4   ids with >1 name, all seasons                expect    13  got    12  MISMATCH
A5   names with >1 id, all seasons                expect     0  got     0  EXACT
A6   ids with >1 name, 2021-2024                  expect    12  got    12  EXACT
A7   names with >1 id, 2021-2024                  expect     0  got     0  EXACT
A8   recomputed ambiguous ids == allowlist        expect  True  got  True  EXACT
A9   roster windows simulated, 2021-2024          expect  1940  got  1940  EXACT
A10  windows where the two keys differ            expect   196  got   196  EXACT
A11  divergence rate (%)                          expect 10.10  got 10.10  EXACT
A12  windows with negative delta (drop mode)      expect     0  got     0  EXACT
```

A1 and A4 fail because E1_I0048 read the **production** master (unmanifested) and this screen
read the **manifest-verified research copy**, frozen at `fit_through_date 2026-08-01T12:00Z`.
The entire difference is in the sealed seasons. **A9–A12 — the headline — reproduce exactly on a
different file**, which is a stronger reproduction than a same-file one. Full detail:
`DEFECTS.md` D-3.

Screen-level anchors, reproduced inside each measurement rather than asserted:

| anchor | published | reproduced |
|---|---:|---:|
| E0_I0006 high-usage player-team-seasons | 200 | **200** |
| E0_I0006 absence-game rows | 622 | **622** |
| E0_I0006 teammate redistribution rows | 4,983 | **4,983** |
| E0_I0006 events with a `top1_share` | 578 | **578** |
| E0_I0006 `top1_share` mean | 0.470 | **0.4699** |
| E0_I0006 `top1_share` median | 0.454 | **0.4545** |
| shared screen frame `DECISION` column vs recomputation | — | **18,212 / 18,212** |
| m14 unresolved priced names excluded | 62 | **62** |

`ANCHOR_REPRODUCTION.csv` carries the machine-readable table.

---

## 3. What the census found

| | |
|---|---:|
| structural keyed operations | 4,340 |
| keyed on `player_id` | 492 |
| keyed on `player_name` alone | 25 |
| keyed on a composite carrying both | 8 |
| **name-bearing share of player-keyed operations** | **6.29 %** |
| key-variable bindings inspected / naming a player name | 310 / **0** |
| persisted frames / carrying no player identity | 830 / **721 (86.9 %)** |
| frames carrying a name and no id | **3** |
| screens / with zero name-keyed operations | 83 / **77** |

**Twelve files** contain a name-bearing key — **42 operations in all**, of which **33 are
structural** (the remainder are `nunique` / `value_counts` cardinality reports). Their character
matters more than their count:

* **15 sites, `E1_I0048/scripts/`**: 7 in `s05_name_key.py`, 5 in `s03_damage.py`, 2 in
  `s02_shipped.py`, 1 in `s06_postrepair.py` — the prior screen's own measurement. The name key
  **is** its treatment arm.
* **9 sites, `O14_OPS_ENTITY_RESOLUTION/{fix,repro}_entity_resolution.py`** — the pre-repair
  reproduction arm and the measurement of the binding failure the repair replaced.
* **8 sites, `E0_I0006_usage_redistribution/{analyze_clean,build_redistribution,placebo_check}.py`**
  — of which **5 are in scripts that screen's own `NOTES.md` marks VOID** (contaminated source,
  "must not be cited"). The three live sites are `analyze_clean.py:20, 87, 92`.
* **1 site, `E1_I0045_roster_currency/scripts/s04_coverage_and_exposure.py:88`** — a reporting
  `groupby("player_name")` producing a 10-row published table.
* **9 sites, `m14_lib.py` + `F16_PLAYER_PROPS/measure_props_evidence.py`** — the props ingest,
  whose source has **no `player_id` column at all**.

---

## 4. The measurements

**E0_I0006 — the only live research-lane site with a name-bearing key upstream of a verdict.**
Re-executed under both keys on the identical frame, one line changed:

| | name key | id key | Δ |
|---|---:|---:|---:|
| baseline rows (`groupby` L20) | 690 | 690 | **0** |
| high-usage fit pool | 200 | 200 | **0** |
| teammate baseline rows (L87) | 4,983 | 4,983 | **0** |
| rows surviving the inner join (L92) | 4,983 | 4,983 | **0** |
| events with a `top1_share` | 578 | 578 | **0** |
| `top1_share` mean | 0.4699 | 0.4699 | **0.000000** |
| events whose `top1_share` differs | — | — | **0 of 578** |

**D101: no denominator change.** The row set, the response, the SST basis, the weighting and the
base are identical under both keys.

**Why zero.** The panel is a **perfect bijection — 265 `player_id`, 265 `player_name`, zero
ambiguity** — because the screen was rebuilt from raw per-season gamelogs after an unrelated
contamination correction. All twelve ambiguous identities are present in that panel, each under
exactly one spelling. Had it used `master_player`, the same three lines would have split. See
`DEFECTS.md` D-6.

**Decision stratum** (`n_prior ≥ 8` ∧ trailing-5 minutes ≥ 24, D081):

| surface | stratum rows | of total | rows from an ambiguous identity | share |
|---|---:|---:|---:|---:|
| shared screen frame | 6,431 | 18,212 | **164** | 2.5501 % |
| `E1_I0045/_PF` | 4,964 | 20,084 | **123** | 2.4778 % |

Both surfaces are id-keyed, so those rows are **exposure**, not divergence. Named breakdown in
`AMBIGUOUS_IDENTITIES.md` §3.

**Market lane.** `duplicated(["game_id","player_name","bookmaker_key","line"])` versus its
id-keyed counterpart, on the identical resolved row set: **11,167 vs 11,167. Δ = 0.** The champion
fit pool is assembled at `m13_lib.py:348` on `(game_id, player_id)` with
`validate="one_to_one"` — a name-keyed assembly would raise.

**The one real divergence.** 62 of 11,229 two-sided priced rows in 2024 (0.5521 %) fail
normalized-exact resolution and are excluded. **Direction: DROP.** All 62 are `player_id` 204323,
spelled `Cheyenne Parker` in the props feed and `Cheyenne Parker-Tyus` in `master_player`. Upper
bound on the fit pool: **14 of 1,740 rows (0.80 %)**. `DEFECTS.md` D-5.

**Drop mode elsewhere: zero.** Across every partition-guarded frame in the lane carrying both
columns, the count of `player_name` values binding to more than one `player_id` is **0**. E1_I0048's
finding holds in the research lane.

---

## 5. Structural result worth carrying forward

The two spellings are not interleaved at random. **In `master_player`, the ASCII spelling is
predominantly the roster / DNP-row spelling and the accented spelling is the box-score spelling.**
`Xu Han` has 17 rows and **0** played; `Bernadett Hatar` 34 rows and **0** played;
`Lou Lopez Senechal` 24 and **0**; `Nika Muhl` 24 and **0**.

This explains why E1_I0048's roster rule — which includes DNP rows — diverges at 10.1 %, while
research screens that filter to `minutes > 0` see much less. **But not zero: eight of the twelve
still carry played rows under both spellings** (Diggins 13, Stevens 18, Johannès 12, Juhász 10,
Époupa 4, Milić 3, Gustafson 2, Koné 2). A `minutes > 0` filter is not a substitute for keying on
the id.

---

## 6. Provenance

Production files cited by absolute path and blob sha, verified against `git log -- <path>` rather
than inferred from a timestamp:

| file | blob sha | last changed |
|---|---|---|
| `C:\Users\jgallagher\wnba-betting-model\daily_forecast.py` | `b66e9bac82e2de9a1fda97d664bb43ce8e23c708` | `53c58154`, 2026-08-06 15:39:51 Z |
| `C:\Users\jgallagher\wnba-betting-model\entity_resolution.py` | `0a4ce06690a3192c615d20a20175690f06ea49d7` | `723a56d6`, 2026-08-06 15:48:48 Z |

Repository HEAD `5943846f4d01acf3341ef26f798f045a92655c44`. Both files are clean against HEAD
(`git hash-object` equals `git rev-parse HEAD:<path>`). **E1_I0048 attributes the repair to
`55d84f1e`, which touched only market-snapshot data files** — see `DEFECTS.md` D-4. The repair
itself is verified live: `daily_forecast.py:820` imports `player_layer_resolved`, and
`entity_resolution.py:238` is `seen = set(tp[tp.game_id.isin(recent)].player_id.unique())`.

Manifest status of every artifact opened is in `COVERAGE.md` §4. **The master that production
reads still has no manifest; the research copy does. This screen measured on the research copy
and labelled every unmanifested frame at the point of use.**

---

## 7. Process isolation

No process was launched. No `git` write command was issued. No blanket process kill was run — no
process was killed at all. All writes are confined to
`experiments/exploration/E1_I0052_identity_key_divergence/`. Nothing was enacted, no champion was
fitted, and no production file was modified.

---

## 8. Files

| file | what it is |
|---|---|
| `PREREG.md` + `PREREG.sha256` | declarations, anchors, stopping rule; §0 records when it was written |
| `KEY_CENSUS.csv` | 4,340 structural keyed operations: key used, class, stable-id availability, rows diverging |
| `AMBIGUOUS_IDENTITIES.md` | the twelve, traced individually with named games and surfaces |
| `COVERAGE.md` | the three zones, and exactly where the identity map stops protecting |
| `BLAST_RADIUS.csv` | all 83 screens ranked by (rows changed) × (live verdict) |
| `VERDICT.md` | the answer, with the results that most weaken it |
| `FINDINGS.json` | machine-readable |
| `DEFECTS.md` | two of my own, four found in prior work |
| `ANCHOR_REPRODUCTION.csv` | the twelve anchors and their status |
| `scripts/` | s01 census · s02 sites · s03 anchors · s04 E0_I0006 · s05 artifacts · s06 named trace · s07 stratum + guard · s08 deliverables · s09 market · s10 the drop, opened · s11 its reach · s12 residual · s13 key variables |
| `out/` | intermediate tables, including the pre- and post-guard artifact censuses so D-1's correction is visible |
| `run_log_s*.txt` | full console output of every step |
