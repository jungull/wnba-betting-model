# D033 event-catalog schema — INJURY-HISTORY track

**Status:** DESIGN, first-pass. Consumed by the odds puller (D033 point 2: "event-adaptive
sampling ... consumes" this catalog). Field set as mandated by D033/coordinator brief, extended
with the amendment-4-style provenance columns the M00 contract requires on every captured row
(`MARKET_PROGRAM_CONTRACT.md` §6.3, applied here by the same self-imposed discipline
`EVENT_LINKAGE_AND_METHODOLOGY.md` §5.6 uses for its Wikipedia table — this is not a market-
snapshot or competitor-projection table in the §6.3 letter, so its exact field list doesn't bind,
but the spirit — never claim a witnessed timestamp you don't have — binds everywhere).

## Table: `injury_event_catalog` (append-only; a correction is a new row, never an UPDATE)

| column | type | definition |
|---|---|---|
| `event_id` | text (deterministic hash) | hash of `(player_name_raw, game_ref_raw, status_after, source_url, source_published_ts)` — stable surrogate key until entity resolution assigns a real one |
| `player_id` | text, nullable | resolved against the frozen O14 entity-resolution map. **Null until resolved. Never guessed.** |
| `player_name_raw` | text | exactly as printed in the source (e.g. "Alysha Clark") |
| `game_id` | text, nullable | resolved against the schedule/game-id map. **Null until resolved.** |
| `game_ref_raw` | text | the source's own description of the game (e.g. "vs. Indiana Fever, May 6 at 7:00 p.m. ET") — carried verbatim so a later ER pass has the raw material |
| `team_raw` | text | team the report was published for (e.g. "Washington Mystics") |
| `status_before` | enum, nullable | designation immediately prior to this event, from the **last catalog row for this player with an earlier `source_published_ts`**. `NULL` (not "AVAILABLE", not assumed) when no earlier row exists in the recovered set — the recovered set is a sample of a much larger population, and an unobserved prior state is not the same as no prior state |
| `status_after` | enum | `{OUT, DOUBTFUL, QUESTIONABLE, PROBABLE, AVAILABLE, HEALTH_AND_SAFETY_PROTOCOLS, SUSPENSION, REST, OTHER}` — frozen taxonomy shared with `EVENT_LINKAGE_AND_METHODOLOGY.md` §A.1 `severity_class`, so this table's events can join the lane's linkage layer without a re-mapping step |
| `reason_raw` | text | the source's stated reason (e.g. "Right Foot", "Health and Safety Protocols") — never normalized lossily here; enum mapping is a downstream concern |
| `event_ts_lower_bound` | timestamp (UTC), nullable | the latest instant at which the **prior** state is known to have still held. `NULL` when `status_before` is `NULL` (interval is left-open/unbounded — see `EVENT_LINKAGE_AND_METHODOLOGY.md` §A.1's `t_prev`, generalized to "unknown" when no prior capture exists in this recovered set) |
| `event_ts_upper_bound` | timestamp (UTC) | the earliest instant at which the new state is **provably** in effect — for a rank-1/rank-2 published report, this is `source_published_ts` if present and trustworthy, else `source_captured_ts` (the archive-crawl time) as a strictly weaker upper bound, per the tier rules below |
| `source_type` | enum | `{OFFICIAL_QUARTER_HOUR_REPORT, OFFICIAL_TEAM_ANNOUNCEMENT, CREDENTIALED_REPORTER, ARCHIVED_PROJECTION_DFS, GENERAL_NEWS, WIKIPEDIA_REVISION, PARTICIPATION_INFERENCE}` — the exact D033 seven-rung hierarchy, used verbatim as the enum |
| `source_hierarchy_rank` | integer 1-7 | the D033 rank of `source_type` (1 = official quarter-hour report ... 7 = participation inference). Carried redundantly with `source_type` so a consumer can sort/filter on rank without an enum lookup table |
| `source_url` | text | canonical URL of the primary document (the `mystics.wnba.com` article, not the Wayback wrapper URL) |
| `source_published_ts` | timestamp (UTC), nullable | the source's own asserted publication timestamp (e.g. the article's `datePublished` meta field), converted to UTC. **This is a T1-tier (vendor/publisher-asserted) timestamp, not witnessed by us** — carried and labeled as such, never silently promoted |
| `source_captured_ts` | timestamp (UTC) | when the **archive** (Wayback) recorded the snapshot we are reading — the CDX `timestamp` field, converted. This is the only timestamp in the row that is witnessed by a third party we did not choose and cannot be gamed by the source restating its own clock — it upper-bounds `source_published_ts` by construction (you cannot archive a page before it was published, though you can archive it long after) |
| `retrieval_ts` | timestamp (UTC) | when **our** process made the Wayback replay request in this session |
| `confidence` | enum | `{OFFICIAL_ASSERTED, TEAM_ASSERTED, REPORTER_ASSERTED, ARCHIVE_INFERRED, EDITOR_ASSERTED_UNVERIFIED, PARTICIPATION_INFERRED}` — mirrors `source_type` but is the field a consumer actually filters on for evidentiary weight; kept separate from `source_type` because two rows can share a `source_type` (e.g. two team-announcement rows) with different confidence if one is a direct team quote and the other is a beat writer paraphrasing the team |
| `payload_hash` | text | sha256 of the raw fetched HTML (or, for an image-only report, the image bytes) — enables byte-for-byte reproduction verification later |
| `recovery_layer` | enum | `{WAYBACK_CDX, TEAM_SITE_LIVE, COMMON_CRAWL, MANUAL}` — which of the three recovery layers produced this row, for provenance and for auditing which layer is actually earning its keep |
| `provenance_class` | text, fixed per row | one-line plain-English restatement of the row's evidentiary status, e.g. `"T1 team-announcement, archive-witnessed 47 days after publication, publish-ts is publisher-asserted and unwitnessed by us"` — mirrors the M00 contract's caveat-verbatim discipline (§5) so a row never has to be re-investigated to know what it can and cannot support |

## Timestamp-tier discipline (borrows `EVENT_LINKAGE_AND_METHODOLOGY.md` §0 verbatim)

- `source_captured_ts` (the Wayback crawl time) is the row's **T0-equivalent** for *this* table's
  own purposes: it is witnessed by an independent third party (the Internet Archive's crawler),
  not asserted by the subject being described. It bounds recency of the *archive copy*, not of the
  underlying event.
- `source_published_ts` is **T1**: plausible, but asserted by the publisher (WordPress
  `datePublished` meta, or a byline date) and unwitnessed by us. It is the better estimate of
  *when the team actually said this*, and is what `event_ts_upper_bound` should prefer when
  present, but every downstream consumer must know it is a T1 number, never silently treated as
  witnessed.
- A row descending from `PARTICIPATION_INFERENCE` (someone's minutes/box-score participation used
  to infer they must not have been OUT) never gets better than the weakest tier its inference
  chain touches, per the standard "derived quantity inherits the weakest tier" rule.

## Why `status_before` is usually NULL in a *recovered* (not live-captured) catalog

This catalog is built by recovering scattered historical documents, not by polling continuously.
Two adjacent recovered reports for the same player are very often **not** adjacent in reality —
there may be six other reports in between that were never captured, published on a site with no
archive depth, or simply not yet pulled in this bounded session. Treating the nearest *recovered*
prior row as `status_before` would silently understate the interval and could manufacture a false
transition. The schema therefore only ever sets `status_before` from a prior row that is itself in
this same catalog (traceable), and otherwise leaves it explicitly `NULL` with `event_ts_lower_bound`
also `NULL` — an honestly wide, structurally-unbounded-below interval, not a guess.
