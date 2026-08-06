# Wikipedia WNBA transactions harvest (Track B)

**Authority:** D028 (free-data mandate) + D030 (`WIKIPEDIA_HARVEST_GRADUATED`,
`orchestration/DECISION_LEDGER.jsonl`, `experiments/player_program/`, coordinator ruling
ts `2026-08-06T18:40:10Z`). Design basis:
`experiments/market_program/FREE_DATA_SURVEY/MARKET_SOURCES.md` section 5. Contract:
`experiments/market_program/M00_MARKET_PROGRAM_CONTRACT/MARKET_PROGRAM_CONTRACT.md`
(sha256 `1152dcd3bf74000f700844bc8bfc0df25de61a067f59534a714ac4f2f20265de`, verified
byte-exact against the working file before this harvest ran).

No paid host touched (`api.the-odds-api.com` is off-limits to this track while the
coordinator's historical backfill runs). Only `en.wikipedia.org/w/api.php` — free,
keyless, documented MediaWiki Action API — was called.

## Files

| File | Role |
|---|---|
| `harvest.py` | Pulls current-revision wikitext for each season page, verbatim, into `raw/*.json`. |
| `parse.py` | Parses `raw/*.json` wikitext tables into structured rows (`parsed/<year>_transactions.jsonl`) with a strict no-guess rule — anything it can't confidently map goes to `parsed/<year>_rejects.jsonl`, never silently dropped. |
| `revisions.py` | Walks each page's full revision history into `revisions/<year>_..._revisions.jsonl` — the coarse public-knowledge timeline (`WIKIPEDIA_REVISION_TS`). |
| `wikitext_tables.py` | Small dependency-free MediaWiki wikitable parser (header/data cells, `!!`/`||` inline separators, rowspan/colspan grid-fill) that `parse.py` is built on. |
| `tests/test_parse.py` | Unit tests against hand-built wikitext fixtures (rowspan-fill, layout classification, trade-block extraction, reject-not-drop behavior). Run: `python tests/test_parse.py`. All 6 pass. |

## Etiquette

1 request/second ceiling, `maxlag=5` on every call with 503/backoff handling, and a
descriptive `User-Agent` with contact info — all well under Wikimedia's documented
500 req/hour unauthenticated cap. No key, no login, no bypass of anything.

## Amendment-4 timestamp discipline

Every raw and parsed row carries `retrieval_ts` (when *we* fetched it, UTC) separately
from `wiki_revision_ts` (Wikipedia's own editor-asserted revision timestamp) — the two
are never conflated. `WIKIPEDIA_REVISION_TS` bounds public knowledge from **above
only**: a revision at time T proves the edited fact was known to an editor by T, never
when the transaction happened or first became knowable. This caveat is embedded on
every row `revisions.py` writes and must not be dropped by downstream consumers. Every
parsed transaction row also carries a fixed `confidence_label: EDITOR_ASSERTED_UNVERIFIED`
and `provenance_class`, per MARKET_SOURCES.md section 5.6.

**Standing prohibition carried over from MARKET_SOURCES.md section 5.6:** this dataset
may never be the sole or primary input to an F1/F2/reaction-time or stale-line claim.
Lawful uses are roster/entity-resolution ground truth and coarse historical cross-checks
only.

## Row counts per season (harvested 2026-08-06)

| Season | Parsed transaction rows | Reject rows | Wikitext chars | Revisions captured |
|---|---:|---:|---:|---:|
| 2020 | 120 | 9  | 45,351   | 51  |
| 2021 | 103 | 5  | 43,840   | 41  |
| 2022 | 201 | 6  | 62,212   | 17  |
| 2023 | 277 | 11 | 108,147  | 260 |
| 2024 | 170 | 4  | 58,178   | 181 |
| 2025 | 61  | 36 | 182,836  | 657 |
| 2026 | 2   | 25 | 47,847   | 71  |
| **Total** | **934** | **96** | — | **1,278** |

Transaction types covered by the parser: `signed`, `waived`, `retired`, `drafted`
("Previous years' draftees" table only — see note below), `traded`,
`head_coach_change`, `general_manager_change`.

### Known, honestly-stated gaps (not silently patched over)

- **First/Second/Third Round draft-pick tables are not on this page at all.** They are
  MediaWiki template transclusions (`{{#section:<year> WNBA draft|firstround}}`) that
  pull content from the separate `<year> WNBA draft` article. This harvest only
  targeted the season-transactions pages D030 graduated; the draft articles are a
  different page family, not surveyed or graduated here.
- **2025/2026 have higher reject rates** — those seasons introduced new table shapes
  (`Core designation`, `7-day contracts`, `Expansion draft`, legend/caption pseudo-tables
  like "denotes uncoreable unrestricted free agent") that the current layout classifier
  doesn't recognize yet. Every one of those rows is sitting in `rejects.jsonl` with the
  raw cell text preserved, not dropped or guessed at.
- **Trades involving 3+ teams, or a block that isn't a clean `To [[Team]]` + bullet-list
  shape, are rejected, not parsed.** The trade parser only resolves clean 2-side trades.
  This is a deliberate no-guess boundary, not an oversight — see `parse.py`'s
  `parse_trade_table` docstring/comments.
- **`date_wiki` is stored as literal raw text (e.g. "March 15"), never forced into an
  ISO date.** Off-season tables frequently omit the year, and guessing which calendar
  year an unlabeled month/day belongs to (especially across a Nov–Feb boundary) is
  exactly the kind of fabrication the no-guess rule forbids. `season` is stored
  alongside as context only, not asserted as the transaction's calendar year.

## Re-running

```
python harvest.py --seasons 2020 2021 2022 2023 2024 2025 2026
python parse.py
python revisions.py --seasons 2020 2021 2022 2023 2024 2025 2026
python tests/test_parse.py
```

Nothing here is scheduled or wired into any cron/orchestrator — every run above is a
manual, one-shot invocation, consistent with the starter script's original
"documentation-verification only" framing before D030 graduated it to full harvest.
