# Defects found by, and in, E1_I0052_identity_key_divergence

---

## D-1 — MY OWN: my artifact census measured across the seal before I guarded it

**Where.** `scripts/s05_artifact_census.py`, first run.

**What happened.** The census opened every persisted frame in the lane and computed
`rows_diverging_duplication`, `rows_diverging_drop`, `ids_with_multiple_names` and
`names_with_multiple_ids` **on the whole file**, without filtering to 2021–2024. Several frames
span the seal. The most consequential was
`MEASURE_F1_m13_fitpool/*/translation_rows.parquet`, which is **5,889 rows spanning 2024, 2025
and 2026**. The unguarded census reported it as carrying **3 ambiguous identities and 101 exposed
rows**, and I was one step from writing "the champion's fit pool contains three ambiguous
identities" into the deliverable.

**Why it is wrong.** All three are in 2025/2026. **In the exploration partition the m13 fit pool
contains zero ambiguous identities** — 1,726 rows, 0 ids with more than one spelling. The
unguarded number was a statement about sealed data and would have been both a partition violation
and a false finding pointing the same direction.

**How it was caught.** By adding the partition guard to the stratum trace (s06) and watching it
print `sealed_rows_dropped: 4163` on a frame I had already "measured". The guard was in
`ik_base` from the start; I had simply not routed the census through it.

**Fixed** in `scripts/s07_stratum_and_guard.py`, which re-measures all 43 identity-bearing frames
under the guard and additionally reports the 5 frames that carry no `season` column as
STRUCTURE_ONLY, backing no number. Both the unguarded and guarded tables are kept
(`out/_s05_frame_divergence.csv`, `out/_s07_frame_divergence_guarded.csv`) so the correction is
visible rather than silent.

**Generalisable lesson.** A partition guard applied at the *analysis* step and not at the
*inventory* step is not a guard. The inventory is where the numbers that get quoted are actually
formed.

---

## D-2 — MY OWN, caught within the turn: my stratum trace silently found no stratum

**Where.** `scripts/s06_named_trace.py`, section 1.

I looked for `prior5_minutes` on the shared screen frame — the column name used in
`E1_I0043/scripts/od_base.py:decision_mask`. That frame names the same quantity
`ref_trail5_minutes`. The code printed `stratum columns present: ['n_prior']` and **fell through
the whole block without computing anything**, producing a section header with no content. Had I
skimmed the log rather than read it, this screen would have reported no decision-stratum
intersection at all — which reads as "none of the twelve reaches a decision stratum", the exact
opposite of the truth. **Five of them do, and Skylar Diggins-Smith reaches it 91 times.**

**Fixed** in `scripts/s07_stratum_and_guard.py`, which names both columns explicitly per surface
and cross-checks against the frame's own materialised `DECISION` column: **18,212 of 18,212
agree**. Recorded because a block that produces nothing looks identical in a log to a block that
produces a zero.

---

## D-3 — E1_I0048's anchors A1 and A4 do not reproduce, because it read the unmanifested master

**Where.** `E1_I0048_shipped_roster_path/NAME_KEY.md` §1 and §3.

| quantity | E1_I0048 | reproduced here | source |
|---|---:|---:|---|
| `master_player` rows, all seasons | 34,199 | **33,712** | research copy, manifest PRESENT |
| ids with >1 name, all seasons | 13 | **12** | same |
| null `player_id` rows | 0 | **0** | same |
| ids with >1 name, 2021–2024 | 12 | **12** | same |
| roster windows, 2021–2024 | 1,940 | **1,940** | same |
| windows differing under the two keys | 196 | **196** | same |
| divergence rate | 10.10 % | **10.10 %** | same |
| windows with negative delta | 0 | **0** | same |

**This is not an error in E1_I0048.** It read
`C:\Users\jgallagher\wnba-betting-model\data\masters\master_player.parquet` — the file production
reads, which **has no manifest** — as it was on 2026-08-07. I read the research copy, frozen at
`fit_through_date 2026-08-01T12:00Z`. The 487-row and one-identity differences are entirely in the
sealed seasons; the thirteenth identity (`Eliska Hamzova | Eliska Joklova`, 2026) does not exist in
the research copy.

**What is worth recording is that the 2021–2024 numbers reproduce exactly across two different
files.** That is a stronger reproduction than a same-file one, and it means E1_I0048's headline is
robust to the master's drift. But **two of its published constants are properties of an
unmanifested artifact at a moment in time**, and neither is labelled as such. The programme's rule
is `MISSING = UNVERIFIABLE and may back no number`; 34,199 and 13 are numbers backed by exactly
that.

---

## D-4 — E1_I0048 attributes the entity-resolution repair to a commit that does not contain it

**Where.** `E1_I0048_shipped_roster_path/PATH_ANATOMY.md` §0 and §1, and `NAME_KEY.md` §5.

All three say the repair landed in commit **`55d84f1e`** at **2026-08-06 19:47 Z**, and §1 lists
`55d84f1e, 9cfe22e6, 5943846f` as the post-repair commits.

**`55d84f1e` exists and carries that timestamp, and it touched no source file.** Its diff is
entirely `data/market_snapshots/**` and `data/props_capture/historical/**`; its subject line is
*"Backfill COMPLETE: 1,415 featured snapshots…"*. It is a market-data backfill commit whose
timestamp happens to sit in the window where the repair was looked for.

**The repair actually landed in `53c58154`** — *"O16 bundles B and C adopted: entity-resolution
contract and per-game scope + log SCHEMA/2; handoff verified 110/110"* — at **2026-08-06
11:39:51 −0400 = 15:39:51 Z**, which created `entity_resolution.py` and rewired
`daily_forecast.py` in one commit. `723a56d6` (15:48:48 Z) is a follow-up datetime-coercion fix to
`entity_resolution.py` only. **The repair was live four hours and eight minutes earlier than
stated**, which strengthens E1_I0048's conclusion rather than weakening it.

**The substance of E1_I0048 §5 is verified correct**, independently, against the running file:

| | |
|---|---|
| `C:\Users\jgallagher\wnba-betting-model\daily_forecast.py` | blob `b66e9bac82e2de9a1fda97d664bb43ce8e23c708`, clean vs HEAD `5943846f4d01acf3341ef26f798f045a92655c44` |
| `…daily_forecast.py:820` | `from entity_resolution import player_layer_resolved` |
| `C:\Users\jgallagher\wnba-betting-model\entity_resolution.py` | blob `0a4ce06690a3192c615d20a20175690f06ea49d7`, clean vs HEAD |
| `…entity_resolution.py:238` | `seen = set(tp[tp.game_id.isin(recent)].player_id.unique())` |

**Why this matters more than a typo.** E1_I0048's own **D-3** is the finding that a screen citing
production must record path and sha because a claim without one cannot be aged. Its own stamp
names the wrong commit. **A provenance convention that records a commit id nobody verifies is not
better than no convention** — the id must be checked against the file it is supposed to explain,
with `git log -- <path>`, not inferred from a timestamp. This screen cites blob shas for exactly
that reason: a blob sha cannot be attributed to the wrong change.

**Not enacted.** Nothing in E1_I0048 was modified; it is outside my write scope.

---

## D-5 — A named person is dropped from the market denominator, and the disclosure has no name

**Where.** `MODEL_VS_MARKET/compute_model_vs_market.py:build_market_frame`, and every
`MEASURE_F1_m13_fitpool/m14_out/*/FINDINGS.json`.

**62 of 11,229 two-sided priced rows in the 2024 partition (0.5521 %) fail normalized-exact
identity resolution and are excluded.** All 62 are one person: `player_id` **204323**, spelled
`Cheyenne Parker` in the props feed and `Cheyenne Parker-Tyus` in `master_player` — the only
spelling that file carries, in every season 2021–2026. `alias_table.json` is empty, so the index
has no entry for the props spelling.

**Direction: DROP.** She has 0 rows in the 2024 champion translation fit pool of 1,726; her
exclusion costs that pool at most **14 rows of 1,740 (0.80 %)**.

**The exclusion behaviour is correct** — O14 forbids fuzzy fallback, and excluding-and-listing is
the right call. **The defect is the shape of the disclosure.** It reads
`"n_unresolved_player_names_excluded": 62` and stops. Nothing says the 62 are one person; nothing
says the repository already knows who she is; nothing says a one-line alias entry recovers all of
them. This programme has twice been rescued by opening named cases that a count concealed, most
recently nine false positives inside E1_I0048 itself. **A count that names nobody is precisely the
artifact that discipline exists to reject.**

**Not enacted, and deliberately not proposed as a fix here.** Adding
`{"Cheyenne Parker": 204323}` to
`experiments/player_program/ops_lane/O14_OPS_ENTITY_RESOLUTION/alias_table.json` would recover 62
rows and change a denominator on a live-verdict screen. That is a D022 decision, not an
exploration screen's. It is recorded as a measured finding with its bound.

---

## D-6 — E0_I0006's clean rebuild is name-safe for a reason unrelated to identity

**Where.** `E0_I0006_usage_redistribution/analyze_clean.py:20, 87, 92`.

The authoritative arm of a screen carrying a **kill** verdict groups on
`["player_id","player_name","team_id","season"]` and inner-joins on `["player_id","player_name"]`.
Both are name-bearing keys, sitting directly upstream of two population thresholds
(`games_played ≥ 15`, `n_control_games ≥ 5`) and an inner join — the three places a split turns
into a drop.

Measured: **690 vs 690 baseline rows, 200 vs 200 high-usage pool, 4,983 vs 4,983 teammate rows,
578 vs 578 events, `top1_share` mean 0.4699 under both keys.** Δ = 0 everywhere. All four of that
screen's published counts reproduce exactly.

**The reason is that its panel is a perfect bijection: 265 distinct `player_id`, 265 distinct
`player_name`, zero ambiguity.** That is because `NOTES.md` records the screen being rebuilt from
`data/wnba_gamelog_{2021..2024}.parquet` after a **contamination** correction — the raw per-season
gamelogs carry one spelling per player, whereas `master_player`, where all twelve ambiguous
identities live, does not.

**Had that rebuild not happened for unrelated reasons, these three lines would have split Skylar
Diggins-Smith's 102 played rows from her 13 alternate-spelling rows inside the very thresholds
that define the fit population.** This is not a defect today. It is recorded because "no
divergence" here is a property of a data source chosen for a different purpose, and a future
rebuild against `master_player` would reintroduce the hazard with no code change at all.

---

## Not defects, recorded so a later reader does not re-derive them

* **`str.join` and `os.path.join` inflate any naive scan of `.join(` by ~3,200 calls.** The first
  pass of `s01_keyscan.py` reported 9,875 "keyed operations" of which 3,216 were string
  concatenation. Excluding constant and `os.path` receivers brings the census to 6,672, of which
  4,340 are structural. Any future key census in this repository needs the same exclusion.
* **31 files in `experiments/exploration` carry a UTF-8 BOM** and fail `ast.parse` under plain
  `utf-8`. Read with `utf-8-sig`. Uncorrected, the census silently drops scripts from E0_I0029,
  E1_I0004_shot_selection, E1_I0026, E1_I0032, E1_I0035, E1_I0037, E1_I0039 and E1_I0040 —
  several of which carry live verdicts. Correcting it raised the file count from 871 to **902
  with 0 parse failures**, and added 5 name-keyed and 86 id-keyed operations to the census. A
  scan that reports 871 files and does not report its failures is indistinguishable from a
  complete one.
* **`alias_table.json` is empty (0 entries) and that is correct**, per O14. Its emptiness is the
  proximate cause of D-5, which is the cost O14 already priced and accepted.
* **`E1_I0035_availability_sum/_player_frame_all_seasons.parquet` and
  `E1_I0045/_pf_all_seasons.parquet` are named "all seasons" but contain only 2021–2024** (26,574
  rows, `sealed_rows_dropped: 0`). The names are misleading; the files are compliant.
* **The m13 champion fit pool is 2024-only within the exploration partition** — 1,726 of its 5,889
  rows. Any statement about "the champion's fit pool" in 2021–2024 is a statement about one
  season and 76 distinct players.
