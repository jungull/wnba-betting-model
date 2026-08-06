# Full-recovery runbook — INJURY-HISTORY event catalog

**Purpose:** what a future session (or this one, if given a larger budget) should actually run to
turn this session's bounded sample into the real 2022-2026 catalog. Ordered by evidentiary value
per unit of politeness-budget spent, given what this session's probing actually found.

## Step 0 — before any more fetching: resolve the two open unknowns from layers 1-2

1. Does `mystics.wnba.com`'s dated-report series genuinely stop after 2023-09-18, or did the CDX
   filter miss a post-2023 naming convention / did Wayback's crawl depth simply thin out? One
   targeted CDX query against the two category pages
   (`/news/category/injury` and `/news/category/injury-report`, both of which exist in Wayback
   from 2024-2025) with full pagination-link extraction would answer this directly — those pages
   are indexes; reading their own captured HTML lists every post they link to, independent of
   whether each individual post URL was separately crawled.
2. Do the 7 remaining teams (Sun, Wings, Fever, Storm, Valkyries, Dream — Sky/Liberty/Aces/Sparks
   already probed) have a Mystics-style series under a slug this session's `*injury*` filter would
   have caught? The filter is broad enough that a genuinely recurring `<team>-injury-report-<date>`
   series would have matched (Mystics matched three different naming conventions with the same
   filter) — so a `[]` or near-empty result for these 7, using the identical query, is reasonably
   strong evidence of absence, not just an untried gap. **Recommended next action: run the same
   9-query pattern from this session against these 7 domains before assuming any of them has depth.**

## Step 1 — Common Crawl cross-check (per `COMMON_CRAWL_DESIGN.md`)

Execute the design doc's proposed query plan, prioritized exactly as ordered there: rank-1 URLs
first (near-zero cost if the answer is again "nothing," maximum value if it isn't), then the
Mystics slug cross-check, then the other-teams check. This can run in parallel with Step 0 since
it hits a different host.

## Step 2 — bulk document pull, Mystics series (the confirmed-dense source)

~35 dated posts identified in the CDX index (§2 of the enumeration doc), 2022-05 through
2023-09. At 1 rps with a small per-fetch processing overhead, this is roughly **2-3 minutes of
wall-clock politeness-bound fetching** for the full series — trivially inside any reasonable
session budget. Each fetch: Wayback replay GET → regex extract (`<Name> – <Reason> – <Designation>`
lines, per the confirmed format in §3 of the enumeration doc) → one or more `injury_event_catalog`
rows per post (most posts list 1-3 players, based on the two samples pulled).

**Estimated row yield:** 35 posts × ~1.5 players/post (rough estimate from n=2; needs revision
once the real 35 are pulled) ≈ **50 rows**, covering exactly one franchise, exactly one ~16-month
window. This number should be treated as a rough planning figure, not a claim — it is extrapolated
from a sample of 2.

## Step 3 — entity resolution pass

Every row from steps 2 lands with `player_id`/`game_id` = NULL. Resolving `player_name_raw` →
`player_id` requires the frozen O14 entity-resolution map (owned elsewhere in the market lane;
not touched by this track). Resolving `game_ref_raw` (opponent + date + time, e.g. "vs. Indiana
Fever, May 6 2022, 7:00 p.m. ET") → `game_id` requires the lane's schedule/game-id map. **Neither
map was consulted this session** — this step is a hard dependency the catalog cannot skip before
the odds puller can actually use it (the puller needs `game_id` to know which game's line to
sample around).

## Step 4 — scale-out only after steps 0-3 prove the pipeline on real volume

Do not commit to a 12-team, multi-season bulk pull before Step 0 answers whether any other team
even has material to pull. The realistic honest range, given what this session found:

- **Best case** (several more teams turn out to have depth this session's narrow probe missed, or
  the Mystics series extends further via the category-page pagination check): low hundreds of
  rows across the league for 2022-2023, plus whatever 2024-2026 crawl coverage Common Crawl adds.
- **Worst case, and the current evidence-weighted expectation:** Mystics remains the only team
  with meaningful team-site depth, and Common Crawl adds little beyond what Wayback already found.
  In that world, this track's realistic 2022-2025 historical contribution is on the order of **a
  few hundred rows for one franchise**, not a league-wide historical injury tape — a material,
  honestly-scoped input to the event catalog, not the whole of it. The catalog's other
  rank-2-and-below sources (credentialed-reporter Twitter/beat-writer archives, DFS/projection
  site archived snapshots, general news, Wikipedia) — none surveyed by this track this session —
  would need to carry most of the 2022-2025 volume for the other 11 franchises. **This is the
  single most important planning fact this runbook can hand upward**: the D033 event catalog for
  historical seasons will be assembled from many thin, uneven sources, not one deep one, and the
  odds-puller consumer should be designed for sparse, per-team-uneven coverage from the start
  rather than assuming Mystics-grade depth generalizes.

## Volume/budget summary table

| layer | status this session | estimated additional session budget to complete | estimated row yield |
|---|---|---|---|
| Wayback CDX, `wnba.com` official report | DONE — exhausted (1 capture each endpoint) | 0 (nothing more to find) | 0 rows, ever, for 2022-2025 |
| Wayback CDX, Mystics series | enumerated, 2 of ~35 posts fetched | ~10-15 min for the remaining ~33 posts | ~50 rows (1 team, 16 months) |
| Wayback CDX, other 4 probed teams | DONE — confirmed sparse/none | 0 (nothing more to find at this depth) | ~0 recurring-series rows; the ~11 one-off posts found could each still be pulled for a single ad hoc event (rank-2, low volume) |
| Wayback CDX, 7 unprobed teams | NOT STARTED | ~5 min (9 queries × 7 teams, metadata only) | unknown — likely mirrors the 4-teams-probed pattern (mostly none) per the honest read above |
| Common Crawl, all patterns | design only | ~20-30 min for index queries + a bounded content sample | unknown, corroborating |
| Entity resolution (player_id/game_id) | NOT STARTED | depends on O14 map maturity, out of this track's scope | required before any row is puller-usable |
