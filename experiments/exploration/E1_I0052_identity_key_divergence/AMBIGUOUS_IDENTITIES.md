# The ambiguous identities, traced

**Twelve, not thirteen, in the exploration partition.** E1_I0048 counted thirteen across six
seasons. The thirteenth — `player_id` **1643490**, `Eliska Hamzova | Eliska Joklova`, Minnesota —
appears **only in 2026**, which is sealed. Anchor A6 reproduces the exploration-partition count
at exactly 12; anchor A4 (13 across all seasons) does **not** reproduce on the manifest-verified
research master, which carries 12 — see `DEFECTS.md` D-3.

Selection throughout is by `player_id` from the explicit allowlist in `scripts/ik_base.py`,
asserted equal to an independent recomputation (anchor A8). Names below are labels, never keys.

---

## 1. The twelve, resolved and printed

| `player_id` | spellings | seasons | clubs | cause |
|---:|---|---|---|---|
| 203400 | `Skylar Diggins` \| `Skylar Diggins-Smith` | 2021–2024 | PHO SEA | hyphenated surname added |
| 1628922 | `Azura Stevens` \| `Azurá Stevens` | 2021–2024 | CHI LAS | diacritic stripped |
| 1629484 | `Megan DiLeo` \| `Megan Gustafson` | 2021–2024 | LVA PHO WAS | maiden / married |
| 1629546 | `Marine Johannes` \| `Marine Johannès` | 2022–2023 | NYL | diacritic stripped |
| 1629566 | `Han Xu` \| `Xu Han` | 2022–2023 | NYL | given/family order reversed |
| 1630043 | `Bernadett Hatar` \| `Bernadett Határ` | 2021, 2023 | CON IND | diacritic stripped |
| 1630151 | `Olivia Epoupa` \| `Olivia Époupa` | 2024 | MIN | diacritic stripped |
| 1631021 | `Sika Kone` \| `Sika Koné` | 2023–2024 | CHI MIN WAS | diacritic stripped |
| 1631263 | `Nikolina Milic` \| `Nikolina Milić` | 2022–2023 | MIN | diacritic stripped |
| 1641657 | `Dorka Juhasz` \| `Dorka Juhász` | 2023–2024 | MIN | diacritic stripped |
| 1641661 | `Lou Lopez Senechal` \| `Lou Lopez Sénéchal` | 2023–2024 | DAL | diacritic stripped |
| 1642299 | `Nika Muhl` \| `Nika Mühl` | 2024 | SEA | diacritic stripped |

---

## 2. Where the second spelling actually lives — the structural finding

The two spellings are **not** interleaved at random. In `master_player`, the ASCII spelling is
overwhelmingly the **roster / DNP-row** spelling and the accented spelling is the **box-score**
spelling.

| `player_id` | spelling | rows | of which played (`minutes > 0`) |
|---:|---|---:|---:|
| 203400 | `Skylar Diggins` | 19 | **13** |
| | `Skylar Diggins-Smith` | 102 | 102 |
| 1628922 | `Azura Stevens` | 34 | **18** |
| | `Azurá Stevens` | 120 | 120 |
| 1629484 | `Megan DiLeo` | 21 | **2** |
| | `Megan Gustafson` | 120 | 120 |
| 1629546 | `Marine Johannes` | 15 | **12** |
| | `Marine Johannès` | 59 | 59 |
| 1629566 | `Han Xu` | 43 | 43 |
| | `Xu Han` | 17 | **0** |
| 1630043 | `Bernadett Hatar` | 34 | **0** |
| | `Bernadett Határ` | 13 | 13 |
| 1630151 | `Olivia Epoupa` | 22 | **4** |
| | `Olivia Époupa` | 17 | 17 |
| 1631021 | `Sika Kone` | 31 | **2** |
| | `Sika Koné` | 47 | 47 |
| 1631263 | `Nikolina Milic` | 5 | **3** |
| | `Nikolina Milić` | 70 | 70 |
| 1641657 | `Dorka Juhasz` | 20 | **10** |
| | `Dorka Juhász` | 72 | 72 |
| 1641661 | `Lou Lopez Senechal` | 24 | **0** |
| | `Lou Lopez Sénéchal` | 27 | 27 |
| 1642299 | `Nika Muhl` | 24 | **0** |
| | `Nika Mühl` | 16 | 16 |

**Why this matters.** It explains E1_I0048's headline and bounds this screen's. The roster-window
rule that produced the 10.1 % divergence takes `unique()` over *all* rows in the last three box
scores **including DNP rows**, so it sees both spellings and duplicates the player. A screen that
filters to `minutes > 0` sees far less — but **not zero**: eight of the twelve still carry played
rows under both spellings (Diggins 13, Stevens 18, Johannès 12, Juhász 10, Époupa 4, Milić 3,
Gustafson 2, Koné 2). **The exposure survives the minutes filter for two-thirds of them.**

Four (Han Xu, Határ, Lopez Sénéchal, Mühl) carry played rows under one spelling only. For those,
a name-keyed *played-rows* screen would be safe by accident.

---

## 3. The named cases, opened

### Skylar Diggins-Smith — 203400 — the only one that reaches a decision stratum in volume

* Shared screen frame (18,212 rows): **115 rows, 91 in the decision stratum.** Under a name key
  those 91 split **13 / 78**.
* `E1_I0045/_PF` (20,084 rows): **94 rows, 58 in the stratum**, splitting **4 / 54**.
* **Neither surface is name-keyed**, so the stratum row set is identical under both keys. She is
  the largest exposure in the lane and the divergence she causes is zero.
* Named separately in `E1_I0045/CURRENCY_RULE.md` §4 among the R4 over-reach arm's losses
  ("Nneka Ogwumike and Skylar Diggins-Smith on Seattle's 2024 opener"). That prose is a
  description of an arm that carries no verdict, and the row it describes is selected by
  `player_id` upstream.

### Azurá Stevens — 1628922
40 stratum rows, splitting **5 / 35**. Second-largest exposure. Zero divergence.

### Dorka Juhász — 1641657
25 stratum rows, splitting **3 / 22**. Zero divergence.

### Marine Johannès — 1629546
7 stratum rows, all under the accented spelling; a name key would split 0 / 7 — i.e. it would
create an empty second group, harmless. Zero divergence.

### Megan Gustafson (née DiLeo) — 1629484
**1** stratum row. The maiden/married pair is the case `_norm_name` cannot absorb, and it is also
the case with almost no stratum presence. Zero divergence.

### Bernadett Határ — 1630043, and Lou Lopez Sénéchal — 1641661
**The only two of the twelve that appear by name in a published table.**
`E1_I0045_roster_currency/top_removed_players_R3.csv` is built by
`groupby("player_name")` — the lane's single name-keyed grouping — and lists
`Bernadett Hatar` (ASCII) and `Lou Lopez Sénéchal` (accented), each with `rows_removed = 1`.

Both spellings of both identities are present in the source frame `_PF.parquet` (43 and 75 rows
respectively), so the table *could* have split them. It did not, and the proof is by exhaustion:
**the table has 10 rows and the `.head(20)` truncation does not bind**, so it is the complete
grouping of the removal set. If the second spelling of either identity were also in the removal
set it would be an eleventh row. It is not. **Group count under the name key = 10 = group count
under the id key. Δ = 0. D101: no denominator change.**

Neither has any decision-stratum row on either surface.

### Han Xu / Xu Han — 1629566, Olivia Époupa — 1630151, Sika Koné — 1631021, Nikolina Milić — 1631263, Nika Mühl — 1642299
Present in the frames, **zero decision-stratum rows**, zero divergence. `Xu Han` has **0** played
rows: the reversed-order spelling exists only on roster rows.

---

## 4. The thirteenth that E1_I0048 could not see — and it is a DROP

The prior screen compared `master_player` against itself, so it could only find identities
ambiguous *within one file*. There is a fourteenth spelling pair that is invisible to that test
because **the two spellings live in different feeds**:

| feed | spelling | rows, 2024 |
|---|---|---:|
| `data/props_capture/historical/master_props_historical.csv` (production) | `Cheyenne Parker` | **62**, over 14 game_ids |
| `data/masters/master_player.parquet` (research, manifest-verified) | `Cheyenne Parker-Tyus` | 129 across 2021–2024 |

One person: **`player_id` 204323**. `master_player` carries **only** the hyphenated spelling, in
every season 2021–2026. `_norm_name` gives `cheyenneparker` and `cheyenneparkertyus` — different
strings — and the alias table is **empty**, so `build_identity_index` has no entry for the props
spelling and all 62 rows resolve to `NaN`.

**They are excluded. That is a DROP: 62 priced rows removed from the market denominator, 0.5521 %
of the 11,229 two-sided 2024 rows.** She has **0 rows in the 2024 champion translation fit pool**
of 1,726; the upper bound on what her exclusion costs that pool is **14 rows of 1,740, 0.80 %**
(upper bound because a game also needs a scored model row and a two-sided consensus line).

**This is already disclosed — as a number.** `m14_out/*/FINDINGS.json` carries
`"n_unresolved_player_names_excluded": 62`. It does not say who, and it does not say that all 62
are one person whose identity the repository already knows. `compute_model_vs_market.py` names her
in a `known_variants` comment and declines to guess, which is the correct behaviour under O14's
no-fuzzy-fallback rule. **The exclusion is right; the silence about who is the finding.**

**Not enacted.** Adding `{"Cheyenne Parker": 204323}` to
`experiments/player_program/ops_lane/O14_OPS_ENTITY_RESOLUTION/alias_table.json` would recover
all 62 rows and is the obvious repair. It is outside this screen's write scope, it changes a
denominator, and it must go through whoever owns D022 — not through an exploration screen. It is
recorded in `DEFECTS.md` D-5 as a finding, not a proposal.

---

## 5. What normalisation absorbs, and why that is not what makes the lane safe

`_norm_name` strips diacritics and punctuation and lowercases.

* **Absorbed — both spellings collapse to one string (9 of 12):** Stevens, Johannès, Határ,
  Époupa, Koné, Milić, Juhász, Lopez Sénéchal, Mühl.
* **Not absorbed — two distinct normalized strings (3 of 12):** Diggins / Diggins-Smith,
  DiLeo / Gustafson, Han Xu / Xu Han.

**Both groups resolve correctly anyway.** `build_identity_index` enumerates *every* distinct
`(player_id, player_name)` pair observed in a box score, so `skylardiggins` and
`skylardigginssmith` both map to 203400, and `hanxu` and `xuhan` both map to 1629566. **It is
enumeration, not normalisation, that makes the index safe** — and enumeration is exactly what
fails for a spelling that has never appeared in a box score, which is why §4 happens.

Checked and clean: **0 normalized spellings bind to more than one `player_id`** across the 271
distinct normalized names in the 2021–2024 partition. The index is many-to-one and never merges
two people.
