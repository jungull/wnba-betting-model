# Layer 2 — team-site injury archive depth probe

**Method:** identical Wayback CDX queries (see `WAYBACK_CDX_ENUMERATION.md` §0 for the exact
query strings and politeness log) run against four additional `*.wnba.com` team subdomains, using
the Mystics finding as the baseline to test against. No live request was made to any team site —
Wayback CDX only, per the same access posture as layer 1.

**Team selection:** Liberty, Aces, Sparks, Chicago Sky — chosen for geographic/market spread and
because they came up incidentally in the layer-1 domain-wide `wnba.com` scan (§1 of the
enumeration doc), giving a reason to check each specifically rather than picking arbitrarily.

## Result table

| team | recurring dated "Injury Report" series (Mystics-style)? | category/index page? | what *was* found |
|---|---|---|---|
| **Mystics** (baseline) | **YES** — ~35 dated posts, 2022-05 to 2023-09 | YES, 2 pages | see enumeration doc §2 |
| Liberty | **NO** | NO | 6 one-off single-player posts, 2020-2026, irregular ("brittany-boyd-injury-update", "ionescu-injury-update", "ionescu-injury-update-2", "jocelyn-willoughby-injury-update", "michaela-onyenwere-injury-update", + 1 tracking-noise URL) |
| Aces | **NO** | NO | 3 one-off single-player posts, 2021-2026, irregular ("angel-mccoughtry-sustains-right-acl-injury", "las-vegas-aces-guard-dana-evans-out-with-left-leg-injury", "megan-gustafson-sustains-lower-left-leg-injury") |
| Sparks | **NO** | NO | 2 one-off single-player posts (2022, 2023: "rae-burrell-injury-update", "stephanie-talbot-injury-update") plus theme tracking-noise sub-URLs |
| Chicago Sky | **NO** | NO | 1 post total, dated 2017-2019 ("chicago-sky-injury-report-72817"), nothing current |

## Interpretation

The Mystics series is **not representative of team-site coverage generally** — it is the single
best case found, not a template that generalizes to "any team site, if crawled, will yield a
report archive." A recovery strategy that assumed Mystics-style depth existed for all 12+
franchises and budgeted accordingly would have overbuilt for 11 teams and been surprised by the
12th. The honest read: team sites are a **spot-check source**, worth re-probing per-team before
committing crawl budget, not a uniform layer-2 archive to bulk-harvest.

Two hypotheses for *why* Mystics differs, neither confirmed this session (flagged for the
runbook, not resolved here):
1. **Editorial practice difference** — the Mystics' digital/PR staff may simply have chosen to
   post a recurring named "Injury Report" article each game, where other teams only post ad hoc
   single-player injury news. This is consistent with the content itself (Mystics posts follow a
   rigid template; other teams' posts read as one-off news items).
2. **Wayback crawl-depth difference**, independent of what each team actually published — if the
   Archive's crawler happened to discover and follow the Mystics `/news/category/injury-report`
   listing page (which itself only first appears in Wayback in 2025, per the enumeration doc,
   i.e. *after* the dated-post series had already ended) but never discovered an equivalent page
   on the other four sites, the CDX index would show exactly this asymmetry even if the underlying
   *publication* pattern were more similar across teams than it appears. **This cannot be
   distinguished from CDX metadata alone** — it would require checking whether e.g. Liberty ever
   had a recurring report under a slug this search didn't try (only the exact
   `/news/category/injury-report` path and a generic `*injury*` filter were tried; a team could in
   principle use a differently-worded slug, e.g. `/news/liberty-injury-report-<date>`, that a
   broader per-team slug enumeration would need to test before concluding "Liberty has none").

## Access posture

All four probes went through Wayback CDX only. No 403s, resets, or any bot-detection signal was
encountered from `web.archive.org` for any of the four domains — the "report blocks, never
bypass" rule was not triggered because nothing was blocked; this is a clean negative finding
(the archive genuinely has little/nothing for these four teams), not an access failure.

## Recommendation carried into the runbook

Before committing bulk-crawl budget to any additional team site: (1) re-run the domain-wide
`*injury*` CDX filter for the remaining ~7 franchises not yet probed (Sun, Wings, Fever, Storm,
Valkyries, Dream, Sky already done); (2) for any team that DOES show a dense pattern, fetch 2-3
sample documents exactly as done for Mystics before assuming the content format transfers
(the "prose, not image" finding is Mystics-specific evidence, not yet generalized).
