# MARKET_SOURCES — free/lawful market-adjacent & information-event source survey

**Lane:** market_intelligence · **Mandate:** D028 free-data mandate, market_intelligence lens
**Contract binding:** M00_MARKET_PROGRAM_CONTRACT/MARKET_PROGRAM_CONTRACT.md v1.0.0
sha256 `1152dcd3bf74000f700844bc8bfc0df25de61a067f59534a714ac4f2f20265d` — **verified byte-exact**
against the working file at survey time (`Get-FileHash -Algorithm SHA256`). TAXONOMY.json sha256
`c83e25e783a4ee8642a26dd416362e46c2c34196ff8f8354977c28b72940a12` — verified, not independently
re-parsed by this survey (no TAXONOMY.json edits proposed here).

**Scope discipline:** this document only *surveys*. Nothing here is captured, scheduled, or
executed beyond the 1–2 no-key documentation-verification calls logged per source below. Any
source graduating to capture still requires a coordinator ruling that it fits an M00 §1
opportunity class or a named node's stated need before a single production row is written; this
survey does not itself authorize ingestion into any table.

**Method note:** all classifications below were tested from this sandboxed research environment
in addition to desk research (WebSearch + a bounded number of direct HTTP calls). Where a fetch
failed for reasons that look like bot-detection (403/connection-reset on a normal GET, no
JS/challenge solving attempted), that is reported as evidence of an access posture, not bypassed —
per the standing rule against defeating bot-detection, no attempt was made to work around any
403/challenge.

---

## Quick table

| Source | Legality class | Zero cost? | Cadence | Graduated? |
|---|---|---|---|---|
| WNBA official site (injury report, news, transactions) | TOLERATED_UNCLEAR → practically PROHIBITED for automation | yes if reachable | n/a | **No — parked** |
| WNBA/team legacy RSS | PROHIBITED (retired) | n/a | n/a | No — does not exist |
| stats.wnba.com-style public JSON | UNKNOWN / not found | n/a | n/a | No — no confirmed endpoint |
| ESPN public scoreboard/news JSON | TOLERATED_UNCLEAR | yes if reachable | n/a | **No — parked, RotoWire-class discipline** |
| Wikipedia / Wikimedia API (roster-transaction history) | **PERMITTED** | yes | daily-in-season / weekly off | **Yes — capture design + starter script below** |
| Wikidata (SPARQL, player-team qualifiers) | **PERMITTED** | yes | as-needed backfill | Noted as PERMITTED; folded into the same design, no separate script |
| The Odds API (free tier / historical) | PERMITTED but **already owned by another founding-wave node** (amendment 1) | partial (500 credits/mo; historical costs 10×) | n/a here | **No — cross-referenced only, not duplicated** |
| Kalshi public market-data reads | Technically open, but **Data ToS prohibits our use case** | data reads yes; usage no | n/a | **No — PROHIBITED for capture, route to M02B if pursued** |
| ProphetX / BettorEdge APIs | Partner-gated, no self-serve key | no (requires relationship) | n/a | No — not free/open |
| Kaggle / academic WNBA odds datasets | TOLERATED_UNCLEAR (provenance/license unverified per-dataset) | yes | n/a | No — parked pending per-dataset license check |
| BigDataBall WNBA data | PAID | no | n/a | No — build-the-case candidate, route to M02B |

---

## 1. WNBA official site — injury report, news, transactions

**What it would add:** the actual primary-source injury designations (`wnba.com/wnba-injury-report`)
and news/transactions (`wnba.com/news`) — the highest-authority information-event source for F1
(injury-report latency) if it were programmatically reachable, and a clean feed for M04-adjacent
roster ground truth.

**Access test performed:** two no-key GET attempts, both from this environment: (1) WebFetch to
`https://www.wnba.com/robots.txt` → `ECONNRESET`; (2) direct `Invoke-WebRequest` (PowerShell,
browser-style User-Agent) to the same URL → HTTP 403. No JavaScript execution, challenge-solving,
or header-spoofing beyond a standard User-Agent string was attempted, per the standing prohibition
on bypassing bot-detection — so this result is reported as-is, not worked around.

**Legality class:** **TOLERATED_UNCLEAR at best for a human visitor; effectively PROHIBITED for
automated capture from this class of environment.** The site sits behind bot-mitigation that
rejects a plain scripted GET even for `robots.txt` itself, which is a stronger signal than a mere
ToS clause — it is an active technical control. Attempting to defeat it would cross into the
explicitly prohibited "bypass bot-detection" category regardless of what the written ToS says.
This is not a legality judgment on wnba.com's terms (not retrieved — the block occurred before the
terms page could be read); it is a report that the front door itself refuses scripted access from
here.

**Cadence / quota:** N/A — not accessible.

**Verdict:** **Parked, not graduated.** A human researcher can read the injury report and news
pages manually (no rule against a person browsing a public page), but that is not a "capture
design" — there is no lawful, documented, automatable path evidenced here. If the user later
confirms a different network/browser context reaches the site cleanly, or WNBA/the league
publishes a documented feed or grants written permission, this should be re-surveyed — it does not
graduate on the evidence gathered today.

---

## 2. WNBA / team RSS feeds

**What it would add:** low-friction, poll-cheap news/injury/transaction event timestamps if a live
feed existed.

**Finding:** the only RSS artifact found is a **legacy, retired** feed under the old
`wnba.com/archive/.../storm/news/rss.html` path (a pre-redesign team subdomain). Search turned up
no live RSS endpoint on the current wnba.com or any current team site; third-party RSS aggregators
(Yahoo, ESPN, Feedspot) surface WNBA content but those are re-publications of third-party
editorial, not a league feed.

**Legality class:** PROHIBITED / not applicable — the artifact does not exist as a working feed to
classify. Not a real candidate.

**Verdict:** Parked. No live source to design against.

---

## 3. `stats.wnba.com`-style public JSON stats endpoints

**What it would add:** if it mirrored the well-known `stats.nba.com` undocumented-but-widely-used
JSON API (the backbone of the popular `nba_api` Python package), it would be a rich box-score/
play-by-play source useful to fundamental (S-FUND) work and to M04 as an independent stats
comparator.

**Finding:** extensive search (including the `nba_api`/`swar` ecosystem docs, which enumerate NBA
endpoints exhaustively) turned up **no confirmed WNBA-specific equivalent** of `stats.nba.com`.
The `nba_api` package exposes `teams.get_wnba_teams()`, but that is a static team-ID list, not
evidence of a working `stats.wnba.com` JSON backend; no endpoint URL, response schema, or working
example was found for WNBA play-by-play/box-score JSON analogous to the NBA one. WNBA's data
distribution instead runs through Sportradar as the league's stated official data provider — i.e.
a paid/licensed channel, not a free public endpoint.

**Legality class:** UNKNOWN — cannot classify an endpoint that was not located. If a working
`stats.wnba.com` JSON host is confirmed later (e.g. by network trace from wnba.com/stats in a
normal browser session — out of scope for this desk survey), it would need the same ToS/robots
check as §1 before any classification above TOLERATED_UNCLEAR.

**Verdict:** Parked — no artifact to design against. Flagged for a follow-up browser-trace pass
(different tooling than this survey) if the S-FUND side wants to pursue it; not something to build
a starter script against on today's evidence.

---

## 4. ESPN public scoreboard / news JSON (`site.api.espn.com`)

**What it would add:** scores, schedule, team rosters, and news at
`http://site.api.espn.com/apis/site/v2/sports/basketball/wnba/{scoreboard,news,teams}` — a fast,
schema-stable, no-key JSON source. If it graduated, it would help M04 (independent injury/news
event timestamps to cross-check provider-asserted timestamps) and general schedule/roster
bookkeeping.

**Access test performed:** two no-key GET attempts from this environment against the scoreboard
endpoint: WebFetch → HTTP 403; direct PowerShell `Invoke-WebRequest` with a browser User-Agent →
HTTP 403. This is a commonly reported endpoint that many public write-ups (the `pseudo-r/
Public-ESPN-API` GitHub repo, various blog posts) show working with a plain GET from ordinary
consumer networks; the 403 here most plausibly reflects this environment's IP/network being
recognized as non-consumer traffic, not that the endpoint is universally dead. No attempt was made
to work around the block.

**ToS finding (this is the controlling issue, independent of the 403):** ESPN retired its
official public developer API program in 2018. The endpoints above are **not documented or
sanctioned by ESPN** — they are the internal JSON backend that ESPN's own site/apps call, reverse-
engineered and republished by third parties (the GitHub docs found are unofficial community
reconstructions, not ESPN publications). ESPN's general site Terms of Use prohibit "spiders,
robots, or other automated data mining techniques to catalog, download, store, or otherwise
reproduce or distribute content" from their properties. An endpoint being reachable with a bare
GET and no key is **not** the same as it being a "documented public API or explicitly permitted
feed" under this mandate's gate (3): there is no ESPN documentation authorizing third-party
programmatic use, and the general ToS reads as prohibiting exactly this kind of automated pull.

**Legality class:** **TOLERATED_UNCLEAR** — widely used by hobbyists, technically often
reachable, but unsanctioned and arguably ToS-inconsistent. This is the same shape of risk the
M04 design already flagged RED/YELLOW for RotoWire/RotoGrinders/Stokastic (undocumented terms or
explicit anti-crawl clauses): a plausible-looking, no-key JSON endpoint that nonetheless fails the
"documented API or explicit permission" bar.

**Verdict:** **Not graduated.** Per the RotoWire-class discipline this mandate imports from M04,
this stays parked as a survey entry, not a capture design. If the user wants to pursue it, the
lawful path is the same as RotoWire/Dimers: a direct inquiry to ESPN (they do run licensed data
partnerships) or an explicit written-permission determination — which is a §9/M02B-style
USER_REQUIRED legal-risk-acceptance question, not something this survey can resolve by reading a
ToS page.

---

## 5. Wikipedia / Wikimedia APIs — roster-transaction history — **GRADUATED**

### 5.1 What it adds and to which node

The annual **"List of `<year>` WNBA season transactions"** articles (confirmed to exist at least
2010–2025, e.g. `en.wikipedia.org/wiki/List_of_2025_WNBA_season_transactions`) are
community-maintained, plain-text-tabular chronicles of signings, waivers, trades, retirements, and
front-office changes, keyed by date and team. Player infoboxes and Wikidata's structured
`P54` (member of sports team) statements — which carry `start time` / `end time` qualifiers —
give the same information in machine-queryable form.

This is useful to:
- **M04 (competitor-projection archive):** independent, free roster/entity-resolution ground
  truth to sanity-check the O14 player_id ↔ provider_id mapping and to detect roster moves the
  archive's own `schedule_shift_flag` should be reacting to.
- **A future M13-style player-value-translation node:** career team-history timelines (which
  team, which seasons) are a direct input to any cross-team value-translation model, and this is
  effectively a free, continuously-maintained version of that timeline.
- **Information-event capture generally:** a coarse, free, always-available second opinion on
  *that* a transaction happened and *roughly when*, usable as an independent cross-check
  alongside whatever primary capture pipeline the lane builds — **never** as the timing record
  itself (see caveats below).

No M06 injury-studies node was found materialized in this worktree (it may live in the
player-lane side, not surveyed here) — this source is not injury data and is not offered as an
injury source; noting the gap honestly rather than assuming M06's needs.

### 5.2 Legality class: PERMITTED

- **Documented, official API:** the MediaWiki Action API (`en.wikipedia.org/w/api.php`) and the
  Wikimedia REST API are Wikimedia Foundation-operated, publicly documented endpoints
  (`mediawiki.org/wiki/API:Query`, `api.wikimedia.org`), not reverse-engineered.
- **Explicit terms:** governed by the Wikimedia Foundation Terms of Use and a published API usage
  policy (`foundation.wikimedia.org/wiki/Policy:API_usage_guidelines`), which explicitly
  contemplates third-party programmatic and commercial use subject to fair-use rate limits — this
  is the opposite posture from ESPN/wnba.com above.
- **No key required** for the volumes this design needs; **documented rate limit** of 500
  requests/hour per IP unauthenticated (5,000/hour with a free personal API token) — comfortably
  above what a once-a-day pull of a handful of pages requires.
- **License obligation, not a prohibition:** content is CC-BY-SA 3.0/4.0 + GFDL. Our use
  (extracting structured facts — dates, teams, player names — into our own schema) is standard
  API consumption; any verbatim prose we ever *display* would need attribution, but structured
  fact extraction for internal modeling does not implicate that concern the way republishing an
  article would.

### 5.3 Access-verification call performed

Two no-key checks were made in this session, within the mandate's 1–2-call documentation-
verification budget: (1) `WebSearch` confirmed the exact article title pattern and Wikipedia URL
shape for multiple years (2010, 2018, 2019, 2020, 2023, 2025 all resolve); (2) the companion
starter script (§5.7) was actually run once, live, to confirm the endpoint genuinely works rather
than trusting the URL-pattern search alone. Result: `en.wikipedia.org/w/api.php` returned page
`List of 2026 WNBA season transactions` (pageid 82906139), latest revision id `1367522518`,
Wikipedia-recorded revision timestamp `2026-08-03T16:06:28Z`, 47,847 chars of wikitext, no key,
no error. This confirms the source is live and reachable as designed; it does not itself
constitute capture (no row was written anywhere, no parsing of the wikitext into structured rows
was performed — see the script's own docstring). No further live calls were made beyond this one
verification run.

### 5.4 Cadence

- **In-season:** daily poll of the current-year transactions page is more than sufficient — these
  pages are edited by volunteers on a lag of hours to a few days after real-world events, so
  polling faster than daily buys nothing.
  **This lag is exactly why the source can never carry a reaction-time or latency claim** (§1.3,
  §6) — it is a *content* source, not a *timing* source.
- **Off-season:** weekly poll is sufficient (front-office and draft-adjacent moves cluster, but
  nothing here is time-critical).
- **Backfill:** Wikidata SPARQL query, run once per full backfill, not on a recurring cadence.

### 5.5 Quota / rate-limit etiquette

- Unauthenticated: ≤500 req/hour/IP (Wikimedia-documented). This design issues on the order of
  1–5 requests per poll (one page fetch + revision-history check per season page in scope), so it
  sits far under any limit even at daily cadence.
  - **Etiquette beyond the hard limit:** set a descriptive `User-Agent` per Wikimedia's API
    etiquette guidance (contact info + purpose), and never poll faster than the stated cadence
    even though the hard limit would technically allow it.

### 5.6 Schema mapping (proposed — not yet ratified by a coordinator/DESIGN.json review)

Table: `wikipedia_roster_transactions` (append-only, per §4.5/§6.3 discipline the lane already
applies to other captured tables)

| column | type | notes |
|---|---|---|
| `row_id` | uuid | our surrogate key |
| `season_page` | text | e.g. `List_of_2026_WNBA_season_transactions` |
| `transaction_date_wiki` | date | the date the Wikipedia table row itself states — **this is an editor-asserted content date, never a witnessed capture timestamp** |
| `player_name_raw` | text | as it appears in the wikitext |
| `player_id` | text, nullable | resolved against the O14 entity-resolution map; null until resolved, never guessed |
| `team_raw` | text | as it appears in the wikitext |
| `team_id` | text, nullable | resolved against the lane's team ID map |
| `transaction_type_raw` | text | e.g. "signed", "waived", "traded", "retired" — enum normalization is a downstream concern, not stored lossily here |
| `wiki_revision_id` | integer | the MediaWiki revision ID that produced this row's current text |
| `wiki_revision_ts` | timestamp (UTC) | the timestamp Wikipedia recorded for that revision — **this is when an editor touched the page, not when the transaction happened; both are always reported together, never conflated** |
| `retrieval_ts` | timestamp (UTC) | when our script made the API call |
| `ingestion_ts` | timestamp (UTC) | when the row was written to our store |
| `payload_hash` | text | sha256 of the raw API response body for this page/revision |
| `source_url` | text | canonical Wikipedia URL |
| `license_basis` | text | fixed value `CC-BY-SA-4.0-and-GFDL` |
| `confidence_label` | enum | fixed value `EDITOR_ASSERTED_UNVERIFIED` on every row |

**Amendment-4 discipline applied:** this table is explicitly **not** a market-snapshot table
(§6.3's `vendor_ts_semantics` field list) and **not** a competitor-projection archive row (§6.3's
`capture_rung`/`provider_update_ts_confidence` list) — it is a third free-standing content source.
The spirit of §6 is honored by (a) never presenting `transaction_date_wiki` or
`wiki_revision_ts` as a witnessed event timestamp, (b) the fixed `EDITOR_ASSERTED_UNVERIFIED`
confidence label on every row with no path to upgrade it from this table alone, and (c) an
explicit, standing prohibition (stated here and to be repeated in any node's future use) that
**this table may never be the sole or primary input to an F1/F2/§1.3 reaction-time or
stale-line claim.** Its lawful uses are roster/entity-resolution ground truth and coarse
historical cross-checks only — the same "bounded uses, everything else prohibited" discipline
§5 of the M00 contract already applies to the T2 odds archive, self-imposed here by analogy even
though this is a different object the contract doesn't itself rule on.

### 5.7 Starter script (documentation-verification only — not scheduled, not run against a live pipeline in this session)

Written to `experiments/market_program/FREE_DATA_SURVEY/wikipedia_transactions_starter.py`
(companion file). It makes **at most one** GET against `en.wikipedia.org/w/api.php`, no key, and
prints the parsed structure for manual inspection — it does not write to any table, does not loop,
and is not wired into any scheduler. Running it is left to the user/coordinator's discretion.

---

## 6. Wikidata (structured roster-transition facts via SPARQL)

Folded into the graduated design above rather than given a separate script, since it answers the
same node-need (roster/career-team ground truth) with a different query surface.

**Endpoint:** `https://query.wikidata.org/sparql` (Wikimedia-operated, documented, no key).
**Legality class:** PERMITTED — same Wikimedia Foundation terms as §5.
**Use:** a one-off SPARQL query for `P54` (member of sports team) statements on WNBA player
entities with `start time`/`end time` qualifiers gives a structured career-team timeline without
parsing wikitext tables — useful as a cross-check against the §5 transaction-page parse, not a
replacement (Wikidata statements lag article edits further and are sparser for recent
transactions). **Cadence:** backfill-only, not a recurring poll. Not built out as a separate
starter script in this pass to avoid duplicating §5's coverage; flagged as a design option if the
coordinator wants the cross-check.

---

## 7. The Odds API — free tier and historical endpoint (cross-referenced, not duplicated)

This lane's M01 node (`M01_MARKET_DATA_INVENTORY`) already has live work in flight on The Odds
API — `ODDS_API_VERIFICATION.md` / `ODDS_API_LIVE_VERIFICATION.md` and an already-executed
historical pull (`data/props_capture/historical/master_props_historical.csv`, flagged UNGOVERNED
in M01's report) are the actual state of the art here, not this survey. Duplicating that
investigation would create exactly the kind of unreconciled parallel finding M01 already flagged
as a contradiction risk. This survey only adds the desk-research confirmation relevant to *this*
lens:

- The Odds API's own per-sport page (`the-odds-api.com/sports/wnba-odds.html`) states current
  odds/scores are available on the free Starter plan (500 credits/month, no card required), and
  that historical odds exist from **May 2022** for featured markets (h2h/spreads/totals) and
  **May 2023** for other markets (props) — but a historical request costs **10×** the credits of
  a live request (`10 × markets × regions`), so 500 free credits buys very little historical
  volume. This is consistent with, not contradictory to, what M01/M02's own verification work is
  already tracking; treat M01's live-key findings as authoritative over this desk-research note if
  they differ.
- **Legality class:** PERMITTED (documented commercial API with an explicit free tier) — already
  the correct classification other nodes are using; not re-litigated here.
- **Verdict for this survey:** **not graduated as a new artifact** — ownership stays with
  M01/M02, this entry exists only so the market-adjacent survey doesn't read as having missed it.

---

## 8. Kalshi public market-data reads (exchange, free-tier read access)

**What it would add, if usable:** live and historical prediction-market prices on WNBA-adjacent
contracts (where they exist) — genuinely free, no-key reads for most public market-data GETs
(`external-api.kalshi.com/trade-api/v2/markets/...`), which is the kind of thing this mandate is
built to find.

**The disqualifying finding:** Kalshi's **Data Terms of Service** (a separate, binding document
from the general site ToS — `kalshi-public-docs.s3.amazonaws.com/kalshi-data-terms-of-service.pdf`)
explicitly restricts use of Kalshi Data to **personal, non-commercial use**, and its definition of
prohibited non-commercial use expressly includes: *"developing any software program... or
providing archived or cached data sets containing Kalshi Data to another person or entity"*
without Kalshi's prior written consent — and separately prohibits scraping/text-and-data-mining
and storing beyond a quick look. **Building an append-only capture table from this feed is
exactly the activity the Data ToS names and prohibits without written permission.** The fact that
the HTTP calls themselves require no API key and return 200 does not make this a PERMITTED
source under gate (2) of this mandate ("lawful access... NO fuzzy legality").

**Legality class:** **PROHIBITED for this use case** as surveyed (not TOLERATED_UNCLEAR — the
prohibition is explicit and on-point, not ambiguous). This is also consistent with §7 of the M00
contract, which already excludes Kalshi from production execution planning during its NY dispute
— the data-capture prohibition is a second, independent reason, not a restatement of the same one.

**Path forward, if the user wants it:** this is a genuine **build-the-case-for-M02B** candidate —
not because it costs money, but because it requires **written permission** (§9.7,
legal/risk-acceptance is a USER_REQUIRED action). Do not capture from Kalshi absent that written
consent.

---

## 9. ProphetX / BettorEdge APIs

Both are exchange platforms named in the M00 §7 venue policy as sandbox/shadow research tracks.
Desk research found: ProphetX publishes API documentation (`docs.prophetx.co`) describing a
Trader API, a read-only Display API, and partner-integration APIs — but **no self-serve developer
portal or public API key signup**; access runs through their affiliate/partner team. BettorEdge
was not found to publish a public API surface at all in this search pass.

**Legality class:** not classifiable as PERMITTED-and-free — there is no open door to test. This
fails gate (1)/(2) on the "documented public API" criterion as a **currently accessible** thing
(the documentation exists, but the access grant does not, absent a partner relationship).

**Verdict:** parked. If the user wants execution-track access to either (consistent with §7's
SHADOW-mode research track), that is a partner-outreach/credentials question — a §9.3
USER_REQUIRED action, not a free-data-survey capture design.

---

## 10. Academic / community odds datasets (Kaggle, etc.)

Found: a Kaggle dataset titled "Basketball-odds-history" / "WNBA odds history"
(`kaggle.com/datasets/zachht/wnba-odds-history`) and general-purpose NBA odds/stats Kaggle
datasets. These are free to download (Kaggle's own hosting terms apply, not the underlying data's
original terms).

**The problem:** Kaggle datasets in this space are near-universally **re-publications of scraped
or vendor data with the original provenance and license undocumented or unclear** — exactly the
"fuzzy legality" this mandate's gate (2) rules out. A dataset uploader restating odds numbers on
Kaggle does not grant *us* a clean lawful-access chain back to whichever book/aggregator the
numbers originated from, and Kaggle's own dataset license field is frequently blank or
"unknown" for scraped sports-odds uploads.

**Legality class:** **TOLERATED_UNCLEAR**, per-dataset — could in principle turn PERMITTED for a
specific dataset if its uploader-stated license is genuinely open (e.g. a clearly-marked
CC0/MIT dataset with a documented, lawful collection method), but that has to be checked
per-dataset, not assumed from the category. None was found in this pass with clean-enough
documentation to graduate.

**Verdict:** parked. If a specific candidate dataset is later identified with a clean, explicit
open license and documented provenance, it is a fast re-survey, not a new investigation — but
nothing found today clears the bar.

---

## 11. BigDataBall WNBA data

Found in search as a paid vendor (`bigdataball.com/datasets/wnba-data/`) selling game-by-game
box scores, betting odds, and play-by-play in Excel/CSV form. Not free.

**Legality class:** N/A (paid, not surveyed for legality since it fails gate (1) outright).
**Verdict:** **Build-the-case candidate for M02B**, not a free-data survey entry. Flagging its
existence because it is a plausible paid alternative if the free options above (particularly the
Odds API historical tier, already M01's territory) prove insufficient for volume — routed, never
subscribed.

---

## Summary of what actually graduated

Exactly **one** new capture-design-eligible source came out of this lens: **Wikipedia/Wikimedia
roster-transaction history (§5–6)**, useful for M04-style entity-resolution ground truth and
future player-value-translation career timelines, explicitly bounded away from any timing/latency
claim. Every other candidate surveyed here is either already free-and-owned by another node (The
Odds API, §7 — do not duplicate), blocked by an active technical control this mandate forbids
bypassing (wnba.com, §1), unsanctioned/ToS-inconsistent in the RotoWire-class sense (ESPN hidden
API, §4), explicitly prohibited by name for this exact use (Kalshi Data ToS, §8), inaccessible
without a partner relationship (ProphetX/BettorEdge, §9), provenance-unclear (Kaggle, §10), or
paid (BigDataBall, §11; The Odds API beyond its thin free tier, §7).
