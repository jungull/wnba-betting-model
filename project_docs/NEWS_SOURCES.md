# WNBA News-Text Source Inventory (W1: News -> Availability Engine)

Raw-text layer for the availability engine. Every source below was **actually
fetched on 2026-07-30** with plain `requests` (raw HTTP, no JS, honest UA
`wnba-betting-model-news/0.1`, 1.5s spacing). **VERIFIED-FETCHABLE** means the
listed URL returned parseable items to that client on that day; evidence is
the real item count from the fetch. Capture is implemented in
`news_capture_daily.py` (repo root) -> `data/news_capture/` (raw bytes +
`news_items.csv`). No LLM extraction yet - that is W1 phase 2; this layer
exists so no day of text goes uncaptured while phase 2 is built.

## League-wide sources

| source | URL | format | verdict | evidence (2026-07-30) | paywall | cadence (from item dates) | injury usefulness |
|---|---|---|---|---|---|---|---|
| ESPN W headlines | `https://www.espn.com/espn/rss/wnba/news` | RSS | **VERIFIED** | 13 items | none | ~3-4/day (13 items span Jul 27-30) | High - designation-grade headlines ("WNBA bars Storm co-owner...", "Clark's 32...") land here fast |
| ESPN news API | `https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/news?limit=50` | JSON | **VERIFIED** | 50 articles | none | ~8/day (50 span Jul 24-30) | High - richer descriptions than the RSS; same host family as the injury-capture ESPN fallback |
| AP WNBA wire | `https://apnews.com/hub/wnba` | HTML (server-rendered) | **VERIFIED** (HTML parse) | 35 (url, headline, epoch-ms timestamp) triples from raw HTML | none | ~3-4/day (35 span Jul 20-30) | High - gamers + league news within minutes; injury lines inside recaps |
| The Next / The IX Basketball | `https://www.theixsports.com/category/wnba/feed/` | RSS | **VERIFIED** | 10 items, WNBA-only | subscriber paywall on full articles; feed carries excerpt only (~1.4KB/item) | ~2/day (11 captured span Jul 26-30) | Medium-high - best independent beat network; excerpts still name names ("Natisha Hiedeman... shine in Seattle") |
| Winsidr | `https://winsidr.com/feed/` | RSS | **VERIFIED** | 10 items, full text in feed (129KB/10) | mostly free | ~1-2/week (10 items span Jun 9 - Jul 22) | Medium - rotation/fit features, not breaking injury news |
| Her Hoop Stats | `https://herhoopstats.substack.com/feed` | RSS (Substack) | **VERIFIED** | 20 items, full text (394KB/20) | free + paid mix | ~2/week (span May 20 - Jul 30) | Low-medium - analysis (trade deadline, stats), rarely first on injuries |
| WNBA.com editorial | `https://www.wnba.com/news` | HTML (Next.js embedded JSON) | **VERIFIED** (HTML parse) | 10 (title, permalink, date) triples from embedded JSON | none | ~1-2/day (10 span Jul 22-28) | Medium - official transactions/announcements; injury *report PDF* is a separate pipeline (see INJURY_CAPTURE.md) |
| CBS Sports WNBA | `https://www.cbssports.com/rss/headlines/wnba/` | RSS | **VERIFIED** | 36 items | none | ~3/day (span Jul 19-30) | Medium-high - fast aggregation incl. injury explainers |
| Yahoo Sports WNBA | `https://sports.yahoo.com/wnba/rss.xml` | RSS | **VERIFIED** | 50 items | none | **very high - all 50 items dated 2026-07-30** (syndicates AP + originals; 50-item window can roll over within a day) | High volume, medium precision |
| Swish Appeal (SB Nation) | `https://www.swishappeal.com/rss/index.xml` | RSS | **VERIFIED** | 10 items | none | ~2/day (span Jul 26-30) | Low-medium - discussion/previews |

### Rejected / unusable (with evidence)

| candidate | evidence | verdict |
|---|---|---|
| AP RSS (`apnews.com/hub/wnba.rss`, `.../hub/wnba/rss`) | both HTTP 404 | no AP feed exists; use the hub HTML parse above |
| `wnba.com/feed` | HTTP 404 | league site has no site-wide feed |
| `<team>.wnba.com/feed/` (all 15 tested) | HTTP 404 x15 | team sites expose no RSS |
| `<team>.wnba.com/news/` HTML (sampled fever, 430KB) | Next.js RSC app: 0 `__NEXT_DATA__`, 1 extractable article anchor in the whole page - listing is client-rendered | JS-only -> **unusable** for raw-HTTP parsing; team-site posts still reach us via Google News (e.g. `lynx.wnba.com` items appeared x4 in the Lynx query sample) |
| `thenexthoops.com/feed/` | 200 but it is now The IX Sports **network** feed - mixed PWHL/soccer/etc. | superseded by the WNBA category feed (verified above) |
| ESPN injuries HTML page, Rotowire, CBS injuries HTML | JS-rendered / bot-blocked (documented 2026-07-30 in INJURY_CAPTURE.md) | text pipeline uses feeds above instead |

## Google News RSS - programmatic catch-all (VERIFIED)

Pattern (URL-encoded):
`https://news.google.com/rss/search?q="<Team Name>" (injury OR injured OR "ruled out" OR questionable OR doubtful OR waived OR signed) when:3d&hl=en-US&gl=US&ceid=US:en`

All 16 queries (15 teams + league-wide) returned HTTP 200 RSS to the honest
UA with items carrying `pubDate` + `<source>` outlet attribution. Item links
are stable `news.google.com/rss/articles/...` redirect URLs (safe dedupe
keys); the headline carries the outlet as a ` - Outlet` suffix. Probe counts
(14-day injury window): Dream 45, Sky 43, Sun 45, Wings 63, Valkyries 44,
**Fever 100 (capped)**, Aces 61, Sparks 53, Lynx 52, Liberty 58, Mercury 53,
**Fire 59**, Storm 67, **Tempo 48**, Mystics 55, league 57 - i.e. the
catch-all works for the expansion markets too. This is the layer that picks
up beat reporters, local papers, and the JS-only team sites.

## Per-team: official sites + beat coverage

Official team news pages all follow `https://<slug>.wnba.com/news/` and are
**not** raw-HTTP parseable (see rejection table); each team's row is covered
by its Google News query. "Top covering outlets" = outlet counts observed in
that team's 14-day Google News injury-query sample on 2026-07-30 (national
syndicators Yahoo/SI/Athlon/Bleacher Nation appear everywhere and are
omitted). Beat names are best-effort from bylines/knowledge - re-verify
before treating as ground truth.

| team | official news page (JS-only) | top covering outlets in GN sample | likely beat (verify bylines) |
|---|---|---|---|
| Atlanta Dream | `dream.wnba.com/news/` | no dominant local outlet in sample | AJC (intermittent) |
| Chicago Sky | `sky.wnba.com/news/` | ESPN x3; (`mshale.com` x12 is SEO/syndication noise - ignore) | Chicago Sun-Times (Annie Costabile moved to The Athletic - verify) |
| Connecticut Sun | `sun.wnba.com/news/` | CT Insider (also x3 in Wings sample via Sun matchups) | Maggie Vanoni, CT Insider |
| Dallas Wings | `wings.wnba.com/news/` | Dallas Morning News x2, WFAA x2, CT Insider x3 | Dallas Morning News |
| Golden State Valkyries | `valkyries.wnba.com/news/` | national only in sample | Marisa Ingemi, SF Chronicle |
| Indiana Fever | `fever.wnba.com/news/` | **IndyStar x6** (strongest local signal league-wide) | Chloe Peterson, IndyStar |
| Las Vegas Aces | `aces.wnba.com/news/` | national only in sample | Las Vegas Review-Journal |
| Los Angeles Sparks | `sparks.wnba.com/news/` | national only in sample | LA Times (occasional) |
| Minnesota Lynx | `lynx.wnba.com/news/` | Star Tribune x2, lynx.wnba.com x4 (own site, GN-indexed) | Star Tribune |
| New York Liberty | `liberty.wnba.com/news/` | New York Post x3, NetsDaily x3 | NY Post |
| Phoenix Mercury | `mercury.wnba.com/news/` | arizonasports.com x3 (98.7 FM) | Arizona Sports / AZ Republic |
| Portland Fire | `fire.wnba.com/news/` | **OregonLive x10** (clearest expansion-team beat) | The Oregonian / OregonLive |
| Seattle Storm | `storm.wnba.com/news/` | sample diluted by Fever-crossover stories | Percy Allen, Seattle Times |
| Toronto Tempo | `tempo.wnba.com/news/` | Sportsnet.ca x4, Toronto Star x3 | Sportsnet + Toronto Star |
| Washington Mystics | `mystics.wnba.com/news/` | RotoWire x3, national | Kareem Copeland, Washington Post |

## Capture implementation + live verification

`news_capture_daily.py` pulls all 26 verified sources (10 direct feeds + 16
Google News queries), saves raw bytes to
`data/news_capture/raw/<yyyy-mm-dd>/<slug>_<HHMMSS>.<xml|html|json>` before
parsing, appends to `data/news_capture/news_items.csv`, and dedupes on
`(source, url)`. Live proof (2026-07-30): run 1 `16:25Z` -> **1051 new,
26/26 sources ok**; run 2 `16:27Z` -> 27 new (26 = AP parser widened
mid-test + 1 genuinely new The IX post; the other 24 sources re-served
everything and logged **0**); run 3 `16:28Z` -> 15 new, all fresh Google
News items. 1093 rows total, **0 duplicate (source,url) pairs**. 75% of rows
auto-tagged with at least one of the 15 team names.

## Recommended schedule (not yet registered)

Run news capture **4x daily - 08:00, 11:45, 17:00, 21:30 local** (Task
Scheduler, same style as `WNBA_OddsCapture`). 2x aligned with the injury
task (12:00/18:30) is *nearly* enough for archival completeness because most
feeds carry multi-day windows - but not quite, and the misses are exactly
the valuable ones: (a) Yahoo's 50-item window was entirely same-day at
verification time, and the Fever Google News query ran ~30 items/day, so on
heavy news days a 2x cadence can let items roll out of a feed window
unlogged - permanent loss for a training corpus; (b) W1's core payoff is
detecting designation *changes* between the 12:00 and 18:30 injury reports,
which requires at least one text pull inside that gap (the 17:00 run - news
of "ruled out" typically precedes the official designation flip); (c) the
21:30 run captures in-game injury news the night it happens instead of 11
hours later, which matters once capture timestamps are used to align text
against next-morning line moves. Marginal cost is ~90 seconds of polite
fetching per run, so 4x is cheap insurance; more than 4x adds little because
`capture_utc` only needs to bracket the injury-report cycle, not tick-by-tick
news flow.
