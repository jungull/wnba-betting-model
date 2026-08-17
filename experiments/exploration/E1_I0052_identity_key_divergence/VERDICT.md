# VERDICT — is the research lane name-keyed, and does anything diverge?

**Of 4,340 keyed structural operations in the research lane, 33 carry a player name in the key —
6.3 % of the 525 that key on a player at all — and they sit in six of eighty-three screens; the
other seventy-seven contain no name-keyed operation whatsoever, and 721 of 830 persisted frames
carry no player identity at all. All six were measured directly, and inside every frame the
programme owns the divergence is exactly zero rows: no duplication, no drop, no denominator
change, and the reproduced statistics agree with the published ones to the last printed digit.
No published verdict changes.**

The one place where a key change *does* move rows is not inside a frame at all: it is the join
between the props feed, which carries **no `player_id` at any point**, and the owned box scores.
There, **62 of 11,229 priced rows in 2024 (0.55 %) are silently excluded** because two feeds spell
one person two ways — **direction: DROP** — bounded above at **14 of 1,740 fit-pool rows
(0.80 %)**. It is one named person, it is already disclosed as a count by the screen that owns it,
and it changes no verdict. It is reported here because it is the only genuine drop this programme
has found, and because a count that names nobody is exactly what this programme's discipline says
not to accept.

---

## The four answers the brief asked for

### 1. How much of the research lane is name-keyed?

| | |
|---|---:|
| structural keyed operations censused (`merge/join/groupby/drop_duplicates/set_index/pivot/map/isin/unique`) | **4,340** |
| …keyed on `player_id` | **492** |
| …keyed on `player_name` alone | **25** |
| …keyed on a composite carrying both | **8** |
| **name-bearing share of all player-keyed operations** | **33 / 525 = 6.29 %** |
| key-shaped variable bindings recovered and inspected (`key`, `keys`, `gk`, `pk`, `by`, `entity_cols`, …) | **310** |
| …bound to a player-name column | **0** |
| persisted frames scanned | **830** |
| …carrying no player identity at all | **721 (86.9 %)** |
| …carrying `player_id` only | **66** |
| …carrying both | **40** |
| …carrying a name and **no** id | **3** |
| screens enumerated | **83** |
| …with zero name-keyed operations | **77** |
| …with ≥1, all measured directly | **6** |

Three of the twenty-five name-only operations are the E1_I0048 measurement itself, in which the
name key **is** the treatment arm; nine more are O14's pre-repair reproduction arm, which exists
to measure what the repair replaced. Stripping those leaves the true research-lane exposure at
**three sites in one screen** (`E0_I0006_usage_redistribution/analyze_clean.py` lines 20, 87, 92),
**one reporting groupby** (`E1_I0045_roster_currency/scripts/s04_coverage_and_exposure.py:88`),
and **the props ingest**, which has no alternative.

### 2. How many rows diverge, and in which direction?

**Inside the frames the programme owns: zero, in both directions.**

| site | keys used | rows, name key | rows, id key | Δ | direction |
|---|---|---:|---:|---:|---|
| `E0_I0006/analyze_clean.py:20` baseline pool | `player_id, player_name, team_id, season` | 690 | 690 | **0** | NONE |
| …its high-usage fit population | — | 200 | 200 | **0** | NONE |
| `E0_I0006/analyze_clean.py:87` teammate baseline | `player_id, player_name` | 4,983 | 4,983 | **0** | NONE |
| `E0_I0006/analyze_clean.py:92` **inner join** | `player_id, player_name` | 4,983 | 4,983 | **0** | NONE |
| …events surviving | — | 578 | 578 | **0** | NONE |
| `E1_I0045/s04:88` per-player removal table | `player_name` | 10 groups | 10 groups | **0** | NONE |
| m13/m14 market dedup | `game_id, player_name, book, line` | 11,167 | 11,167 | **0** | NONE |

`top1_share` — the statistic E0_I0006's **kill** verdict rests on — is **mean 0.4699, median
0.4545, n = 578 under both keys**, identical to floating-point equality, against a published
0.470 / 0.454 / 578. **D101: the row set, the response, the SST basis and the base are unchanged,
so this is not a denominator change.** Stated explicitly because a zero here is a claim, not an
absence of one.

**The drop mode has zero instances anywhere in the research lane.** Across every guarded frame
that carries both columns, the count of `player_name` values binding to more than one `player_id`
is **0**. E1_I0048's finding holds here.

**Outside the owned frames — the one real divergence.** The props feed
(`master_props_historical.csv`, **no `player_id` column**) is joined to the owned gamelogs by
normalized-exact name. In the 2024 partition, 11,229 two-sided priced rows resolve to 11,167
(99.4479 %); **62 do not, and are excluded.** All 62 are one person — see
`AMBIGUOUS_IDENTITIES.md` §4. **Direction: DROP.** Upper bound on the champion translation fit
pool: **14 of 1,740 rows, 0.80 %**.

### 3. Do any of the twelve reach a decision stratum or an anchor?

**Five of them reach a decision stratum. None reaches it under a name key, because no surface
carrying them is name-keyed — so this is exposure, not divergence.**

Decision stratum = `n_prior ≥ 8` **and** trailing-5 minutes ≥ 24 (D081). On the shared screen
frame the stratum is **6,431 of 18,212 rows**, and the frame's materialised `DECISION` column
agrees with a recomputation on **18,212 of 18,212 rows** — an exact anchor.

| identity | `player_id` | stratum rows | split a name key would impose |
|---|---:|---:|---|
| **Skylar Diggins-Smith** | 203400 | **91** | 13 `Skylar Diggins` / 78 `Skylar Diggins-Smith` |
| **Azurá Stevens** | 1628922 | **40** | 5 `Azura Stevens` / 35 `Azurá Stevens` |
| **Dorka Juhász** | 1641657 | **25** | 3 `Dorka Juhasz` / 22 `Dorka Juhász` |
| **Marine Johannès** | 1629546 | **7** | 0 / 7 |
| **Megan Gustafson** | 1629484 | **1** | 0 / 1 |
| the other seven | — | **0** | — |

**164 of 6,431 stratum rows (2.55 %)** belong to an identity carrying two spellings; the same
figure on E1_I0045's `_PF` frame is **123 of 4,964 (2.48 %)**. That is the size of the hole a
single name-keyed line would have opened, and it is why "6.3 % of operations" is not a
reassuring number on its own.

**Anchors:** none of the twelve appears in any anchor number this programme quotes, and none
appears in the champion's fit pool. Two appear by name in one published table — `Bernadett Hatar`
and `Lou Lopez Sénéchal` in `E1_I0045/top_removed_players_R3.csv` — and that table is unchanged
under the correct key (proof by exhaustion in `AMBIGUOUS_IDENTITIES.md` §3).

**The thirteenth identity is not in this partition.** `player_id` 1643490,
`Eliska Hamzova | Eliska Joklova`, appears only in 2026, which is sealed. The exploration
partition carries **twelve**, not thirteen — anchor A6, reproduced exactly.

### 4. Does any published verdict change?

**No.** Six screens carry a name-keyed operation. Three of the six carry a live verdict
(`E1_I0048_shipped_roster_path`, `MEASURE_F1_m13_fitpool`, `E1_I0045_roster_currency`); all three
measure a delta of exactly zero. E0_I0006's **kill** stands on numbers that are identical under
the correct key. The cross-feed drop touches one non-verdict feasibility measurement and is
bounded below 1 % of a fit pool that is itself 2024-only.

**`BLAST_RADIUS.csv` ranks all 83 screens. Seventy-seven have a rank score of 0 because they
contain no name-keyed operation. That was established first and cheaply, exactly as the brief
asked, and it is the bulk of the answer.**

---

## The results that most weaken this conclusion

Stated here, not in a footnote.

1. **Zero is not the same as safe, and the reason zero happened is luck in one place.**
   `E0_I0006`'s composite key `["player_id","player_name"]` diverges only if a player carries two
   spellings *in that panel*. She does not — because that screen was rebuilt from the raw
   per-season gamelogs (a **perfect 265-id / 265-name bijection**) after a contamination
   correction that had nothing to do with identity. Had it used `master_player`, where **all
   twelve** ambiguous identities live, the same three lines would have split Skylar Diggins-Smith's
   102 played rows from her 13 alternate-spelling rows inside the very `games_played ≥ 15` and
   `n_control_games ≥ 5` thresholds that define its population, and its inner join would have
   dropped teammates outright. **The screen is correct for a reason unrelated to why it is
   correct.** That is the honest reading of its zero.

2. **The dangerous mode exists in this repository; it is just not where anyone looked.** The
   "two people, one name" drop has zero instances. The **cross-feed** drop has one, and it is a
   drop of exactly the kind the brief warned about — a player silently removed from a denominator
   — living in the one lane whose source has no stable key. It is disclosed today only as
   `"n_unresolved_player_names_excluded": 62` in an m14 `FINDINGS.json`, with no name attached.
   **A count with no name is what this programme has already been burned by twice.**

3. **My two failed anchors are real failures, not rounding.** A1 (34,199 rows) and A4 (13
   identities) did not reproduce: the manifest-verified research master carries 33,712 rows and
   12 identities. The difference is entirely in the sealed seasons, and A6–A12 reproduce exactly
   on a **different file** from the one E1_I0048 read — which is a stronger reproduction than a
   same-file one. But the two masters are not the same artifact and **the one production reads
   still has no manifest**, so no number in this screen is backed by production's own input.

4. **872 of 4,340 keyed operations hold their key in a variable my static resolver could not
   fold.** I closed that residual three ways (§1 above, plus per-frame scoping and hand
   adjudication of all 70 unresolved structural operations in the eleven screens where an
   ambiguity actually exists) and found nothing. **It is a closed residual, not an empty one**,
   and a future refactor that binds a key variable to a name column would reopen it silently.

5. **Five of the 43 identity-bearing frames have no `season` column and could not be
   partition-guarded.** They are reported as structure-only and back no number here. One CSV was
   unreadable (empty). Both are listed in `COVERAGE.md`.

---

## What this retires, and what it does not

**Retired.** The claim that name matching is a live defect *in the research lane* does not
survive this measurement. Six findings in this programme have died to name matching; none of them
died in an exploration screen's own joins, and the census says none can, because those joins do
not use names. The lane is id-keyed by construction, not by luck — 310 of 310 key-variable
bindings, 492 of 525 player-keyed operations, and every frame that matters.

**Not retired.** The defect class survives at **feed boundaries**, where a source carries no
stable key and the only join available is a string. That is where the last six instances actually
lived — the injury feed, the props feed, the roster reconstruction — and it is where the alias
table, empty by design and correctly so, earns its existence. **The right statement is not "name
matching is fixed"; it is "name matching is confined to the three places where the data leaves no
choice, and all three now exclude-and-list rather than guess."**
