# Layer 3 — Common Crawl index probe: query-pattern design (NOT executed)

**Status: design only, per the explicit mandate instruction ("query pattern doc, no bulk pull this
session").** Nothing in this document was run against Common Crawl this session. It exists so a
future session (or the odds-puller-facing recovery pass) has a ready-to-execute query plan rather
than starting from zero.

## Why Common Crawl at all, given layer 1 already used an index (Wayback CDX)

Common Crawl (`commoncrawl.org`) is an **independent, differently-scheduled** web crawl — it does
not share a crawl schedule, crawl-frequency policy, or discovery heuristic with the Internet
Archive's Wayback crawler. A page Wayback never captured (e.g. `wnba.com/wnba-injury-report` in
2023) may or may not have been captured by a Common Crawl monthly snapshot in that same window —
the two archives' coverage gaps are not the same gaps. It is a **second, free, lawful, differently
biased index over the same lawful-to-view public web** — exactly the kind of corroborating source
D032's "three-layer recovery" structure calls for, not a redundant restatement of layer 1.

## The index API (documented, free, no key)

Common Crawl publishes a CDX-*compatible* index API per crawl, at
`https://index.commoncrawl.org/<CRAWL-ID>-index?url=<url>&output=json`, where `<CRAWL-ID>` is one
of the dated monthly/multi-monthly crawl identifiers (e.g. `CC-MAIN-2022-33`). The **full list of
crawl IDs** is itself published at `https://index.commoncrawl.org/collinfo.json` — this would be
the first live call a future session makes (one GET, no key, returns the complete crawl-ID
inventory needed to plan which snapshots fall in the 2022-2026 window this track cares about).

Query shape mirrors Wayback CDX closely (same underlying CDX file format), e.g.:

```
https://index.commoncrawl.org/CC-MAIN-2022-33-index?url=mystics.wnba.com/news/*&output=json&limit=200
https://index.commoncrawl.org/CC-MAIN-2022-33-index?url=wnba.com/wnba-injury-report&output=json
```

Each row returned gives a `filename` + byte `offset`/`length` into a shared multi-gigabyte WARC
file hosted on AWS S3 (`s3://commoncrawl/...`, also available over plain HTTPS via
`https://data.commoncrawl.org/<filename>`) — retrieving actual page content requires a **ranged
HTTP GET** on that WARC file at the given offset/length, not a separate per-page fetch. This is
the main mechanical difference from Wayback replay (which serves one page per URL request): a
Common Crawl pull is index-query-per-URL, then one ranged-byte-range GET per hit, against a much
larger backing object.

## Proposed query plan (not executed)

1. **Enumerate crawl IDs** covering 2022-01 through 2026-08 from `collinfo.json` (Common Crawl
   runs roughly monthly to bi-monthly; expect on the order of 30-50 crawl IDs in this window).
2. **Per crawl ID, per target URL pattern**, query the index for:
   - `wnba.com/wnba-injury-report` (exact) and `wnba.com/api/injury-reports` (exact) — the layer-1
     finding that Wayback has ~zero depth here makes this the highest-value Common Crawl query:
     if Common Crawl captured this page even a handful of times across 30-50 monthly snapshots,
     that is strictly more rank-1 evidence than currently exists anywhere in this program.
   - `mystics.wnba.com/news/injury-report-*` and `mystics-injury-report-*` (prefix/wildcard, to
     cross-check the Wayback-derived post list — a post Wayback captured once but Common Crawl
     also captured independently would upgrade nothing in tier terms, since both are still T2/T1
     retrospective, but would give a second `source_captured_ts` data point for the same
     publication, useful for corroboration).
   - The same team-injury-report slug patterns for the remaining ~7-11 teams not yet found to have
     a Mystics-style series in Wayback (per `TEAM_SITE_PROBE.md`'s recommendation) — Common Crawl
     is the natural second check before concluding a team genuinely has no archived series.
3. **Politeness:** Common Crawl's index API documents no hard per-IP rate limit as strict as
   Wayback's, but the same self-imposed 1 rps discipline applies regardless — this is a standing
   program rule (`polite clients everywhere`), not conditional on what a host's stated limit is.
   The ranged WARC-byte-range GETs against `data.commoncrawl.org` are the actual bulk-volume cost
   (each hit is a real content fetch) and should be bounded by the same session document caps this
   track has been using (≤200/session as a default, adjustable by explicit instruction).

## What this design deliberately does NOT resolve

- Exact byte-offset mechanics for the ranged GET (well-documented in Common Crawl's own
  `get-started` guide; not reproduced here to avoid stale duplication — a future session should
  pull that guide fresh rather than trust a paraphrase).
- Whether `wnba.com/wnba-injury-report` will actually show up in any Common Crawl snapshot — this
  is an empirical question layer 1 could not answer and this design does not pre-answer it either.
- Legal/ToS posture: Common Crawl's own terms explicitly permit this kind of programmatic index
  and data use (it is built for exactly this purpose, unlike the ESPN/wnba.com direct-scrape cases
  the free-data survey flagged as risky) — noted here as a reason this source is a strong D028
  free-data-mandate candidate, not re-litigated in full ToS detail since no data was pulled this
  session to need the full legal-risk write-up.
