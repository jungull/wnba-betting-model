# The name key: was a stable id available, and how many rows differ?

**Short answer: yes, in the same DataFrame, on the same line, with zero nulls — and the
pre-repair code used the name anyway. Under the two keys, 204 of 3,030 roster windows across the
repository differ. In the shipped pre-repair window, 0 differ. The reason is 22 days.**

---

## 1. Was a stable id available at that point in the code?

Line 647 of the pre-repair `daily_forecast.py` is `p = pd.read_parquet(MASTER_PLAYER)`. Line 665
is `roster = tp[tp.game_id.isin(recent)].player_name.unique()`. The frame `tp` is a slice of `p`.

| | |
|---|---|
| `player_id` present in `master_player.parquet` | **yes** |
| null `player_id` rows | **0 of 34,199** |
| dtype | `Int64` |
| distance from the id to the line that ignored it | **same DataFrame, 18 lines** |

There was no lookup to perform, no join to write, and no missing-value policy to decide. The
column was already in hand. `roster = tp[...].player_id.unique()` would have been the same number
of characters.

**Stated plainly, as the brief asks: a stable player id was available at that point in the code,
and the code used a name instead.**

The programme's `cbs_obligation_key` and the verified identity map — recomputed over 519,920
triples and matched on all 22,659 rows — were not even needed. This is not a case where entity
resolution was hard and was skipped; it is a case where the resolved key was the adjacent column.

---

## 2. How many rows differ under the two keys?

The recency-roster construction was simulated at **every** team-game index in every season —
3,030 windows — and the roster size under `player_name.unique()` compared with `player_id.unique()`
on the identical frame. Same data, same window, one line changed: no drift, no confounding.

| partition | windows | windows where the keys differ | rate |
|---|---:|---:|---:|
| **2021–2024** (exploration partition) | 1,940 | **196** | **10.10 %** |
| 2025 (SEALED) | 620 | 0 | 0.00 % |
| 2026 (SEALED) | 470 | 8 | 1.70 % |
| **all** | **3,030** | **204** | 6.73 % |

Every difference is in the same direction: the name key returns **more** entries than the id key
(`delta` is +1 or +2, never negative). That is the duplication mode — one player, two spellings,
two roster rows — and it inflates `n_roster` and double-counts part of a player's minutes inside
`sum_min_ewma_available`.

The drop mode (two players, one spelling) has **zero instances**: no `player_name` maps to more
than one `player_id` in any season. So the merged-history hazard described in `PATH_ANATOMY.md`
§5 is real in the code and absent in this data.

---

## 3. The thirteen identities, named

27 (season, identity) pairs across 13 distinct `player_id` values carry more than one
`player_name`. Grouped by cause — the exact categories the brief asked about:

| cause | identities |
|---|---|
| **diacritics stripped in one source** | `Azurá/Azura Stevens`, `Bernadett Határ/Hatar`, `Marine Johannès/Johannes`, `Nikolina Milić/Milic`, `Sika Koné/Kone`, `Dorka Juhász/Juhasz`, `Olivia Époupa/Epoupa` |
| **hyphenated surname added** | `Skylar Diggins` → `Skylar Diggins-Smith` |
| **maiden / married name** | `Megan DiLeo` → `Megan Gustafson`; `Eliska Hamzova` → `Eliska Joklova` |
| **name-order transliteration** | `Han Xu` / `Xu Han` |

Full listing with seasons and clubs in `NAME_KEY_offenders.csv`; per-window detail in
`NAME_KEY_window_diffs.csv`.

Note the interaction with the designation gate. `_norm_name` strips accents and punctuation, so
the seven diacritic cases and the hyphen case **do** bind correctly to the injury feed — the
normaliser absorbs them. It does **not** absorb a maiden-name change or a reversed name order.
`Eliska Hamzova` and `Eliska Joklova` normalise to different strings; so do `Han Xu` and `Xu Han`.
Those are precisely the cases where the `Out` gate can fail to fire, and the pre-repair code's own
`WARN` said so.

---

## 4. How many *shipped* rows differ? Zero — and why that is luck, not design

Across the 76 pre-repair shipped team-slots:

| | |
|---|---:|
| name→multiple-id collisions (a player dropped) | **0** |
| id→multiple-name variants (a player duplicated) | **0** |
| slots where the two keys give different roster sizes | **0 of 76** |

**This is the result that most weakens this screen's own conclusion, so it is stated here rather
than in a footnote.**

The only 2026 identity with two spellings is `player_id` 1643490, Minnesota — `Eliska Hamzova` /
`Eliska Joklova`. Her name alternated between the two through May and early July and settled on
`Joklova` from 2026-07-06 onward; the last box score carrying `Hamzova` is **2026-07-03**. The
eight differing 2026 windows are Minnesota's slate indices 2–7 (May) and 21–22 — the last of which
is the roster window in effect around **2026-07-09**.

The shipped forecast log opens on **2026-07-31**.

**The name key produced no damage in shipped output because regime D started 22 days after the
last window in which it would have fired.** Had the log opened three weeks earlier, Minnesota
would have shipped a 15-name roster containing one player twice, with her minutes history split
across the two entries. The correct reading of the zero in `SHIPPED_DAMAGE.csv` is *"this defect
did not fire in the window that happened to be logged"*, not *"this defect was harmless"*.

---

## 5. Is it still a live risk?

No. From commit `55d84f1e` (2026-08-06 19:47 Z) the production roster is
`entity_resolution.player_layer_resolved`, and at `entity_resolution.py:238` it is:

```python
        seen = set(tp[tp.game_id.isin(recent)].player_id.unique())
```

`player_id`, not `player_name`. Two spellings of one identity now collapse to one roster entry by
construction, and the minutes history is taken from `player_id` across the whole season (F1)
rather than a team-filtered, name-filtered frame — so the split-history mode is closed as well.

Designations bind through a cross-season identity index plus an explicit alias table (F3), with
**no fuzzy fallback anywhere**, which is the right call: the O14 measurement found zero
normalized-exact failures a weaker rule would have recovered, and the alias table is empty by
design with its two rejected candidates recorded and reasoned. An `Out` that binds to nothing now
raises `BLOCK` rather than `WARN` (F4).

That the repair also fixes the maiden-name case is checkable and was checked: `build_identity_index`
maps every distinct `(player_id, player_name)` pair, so both `eliskahamzova` and `eliskajoklova`
resolve to 1643490.

---

## 6. The residual

`data/entity_resolution/alias_table.json` is empty. That is correct today and it is a standing
dependency: the identity index only knows spellings that have appeared **in a box score**. A
player whose first appearance under a new married name is on an injury report, before she next
plays, is unbindable — and now fails closed with `BLOCK` rather than silently, which is the right
behaviour but is still an operational event someone has to action. This is not a defect; it is
the cost of having no roster feed, and it is where the alias table earns its existence.
