# Odds API Historical Verification — WNBA (basketball_wnba)

**Lane:** market_intelligence (D023, 2026-08-06)
**Role:** ODDS_API_HISTORICAL_VERIFICATION — user amendment (1), urgent
**Status:** Web-sourced verification complete. NO purchase made, NO key pulled against live endpoints yet. Everything below is a documentation-hypothesis until confirmed with a free/trial key (see §6).
**Author note on method:** Claude web-fetch tools return an LLM-summarized paraphrase of fetched pages, not raw HTML. I have treated every quoted string below as "the fetch tool's paraphrase of the source page," not as a verbatim byte-for-byte quote, and flagged confidence accordingly. Nothing here should be treated as final until re-verified per §6.

---

## 0. Bottom line up front

- The Odds API **does** document a historical odds product with 5-minute (post-Sep-2022) snapshot granularity for "additional markets" (player props, alternates, periods) since **2023-05-03**, and for featured markets (h2h/spreads/totals) since a base date the docs state as **2020-06-06** generally — but the **WNBA-specific product page gives a different, later featured-markets start date: May 2022**, not 2020. This discrepancy is unresolved and is the single most important thing to verify with a live key before we budget anything (see §1c).
- Player props historical data for WNBA is claimed available from **2023-05-03**, at 5-minute snapshots, same as the general "additional markets" line — but no WNBA-specific confirmation of that date was found; it is inferred from the general policy plus a page that says player props are covered "for most US bookmakers" without a start date.
- Current published pricing (DOCUMENTED, but see caveat on plan-name churn in §3) shows historical access is now bundled into **all** paid tiers, including the low-end $30/mo tier, with historical calls costing **10x** the standard credit rate — this is a change from older third-party summaries that gated historical/player-props behind a $99/mo "Business" tier. The two pricing narratives conflict; the vendor's own site is the tie-breaker but should be re-confirmed live at checkout, not assumed.
- Timestamp semantics: the documented `timestamp` field is the API's **own snapshot-capture time**, not book-publication time, and the vendor's terms carry an explicit volatility/accuracy disclaimer with no numeric latency SLA. Per amendment (4), any reaction-time claim built on this data must carry a timestamp-uncertainty term because the vendor does not publish a bounded latency figure — only a "delays may be present" caveat.
- Licensing: personal/internal betting-research and analytical use is explicitly permitted; **resale/redistribution as a standalone data product/API/feed is explicitly prohibited**; storage/retention rights and model-training rights are **not addressed anywhere** in the terms found — this is a real gap, not an inferred "probably fine."

---

## 1. Historical coverage for WNBA — documented claims and conflicts

### 1a. General historical-odds documentation (source: `the-odds-api.com/historical-odds-data/` and `the-odds-api.com/liveapi/guides/v4/`)

DOCUMENTED (via fetch-tool paraphrase, re-verify verbatim):
- Historical odds "accessible for all sports and bookmakers covered by The Odds API."
- Featured markets (h2h, spreads, totals): snapshots from **June 6, 2020**, at **10-minute intervals until September 2022**, then **5-minute intervals** from September 2022 onward.
- Additional markets (player props, alternate lines, period markets): available after **2023-05-03T05:30:00Z**, at 5-minute intervals since inception.
- Endpoint: `GET /v4/historical/sports/{sport}/odds?apiKey=...&regions=...&markets=...&date=...`
- `date` param is ISO8601; API returns the closest snapshot **at or before** the requested date.
- Response carries `timestamp` (the snapshot actually returned), `previous_timestamp`, `next_timestamp` for paging back/forward in time.
- No sport-specific (WNBA) exception is stated on this general page.

### 1b. WNBA-specific page (source: `the-odds-api.com/sports/wnba-odds.html`)

DOCUMENTED (via fetch-tool paraphrase):
- Sport key: `basketball_wnba`.
- Featured markets (h2h, spreads, totals) covered across multiple bookmakers.
- Additional markets — "player props, quarter and half time markets, and more" — covered "for most US bookmakers," including `player_points`, `player_rebounds`, half-time h2h (`h2h_h1`); milestone/alternate lines use `_alternate` suffixed keys.
- **Historical data, per this page: featured markets available from May 2022; other (additional) markets from May 2023.**
- Scores: WNBA final scores available "for games completed up to 3 days ago."
- No explicit WNBA product-launch date stated.

### 1c. The conflict that matters

The general historical page says featured-market history starts **2020-06-06** ("all sports"). The WNBA-specific page says WNBA featured-market history starts **May 2022**. These cannot both be literally true for WNBA unless one of:
1. The general page's "2020-06-06" is the earliest date *the historical system itself* began operating, and WNBA simply wasn't a covered sport on the-odds-api.com until later (most likely explanation — WNBA coverage was almost certainly added to the vendor's book coverage sometime after 2020, and "featured markets since May 2022" on the WNBA page is the real, sport-specific floor); or
2. One of the two pages is stale/wrong; or
3. The fetch-tool paraphrase mangled one of the two figures.

**This is exactly the kind of claim amendment (1) says must be VERIFIED, not assumed.** Until confirmed against a live/trial key, treat **May 2022** as the working assumption for WNBA featured-market historical floor (it's the sport-specific, more conservative number, and it's more plausible than a blanket 2020 date for a league whose odds market and API coverage were both much thinner pre-2022). Do not backfill-budget past May 2022 for WNBA featured markets until this is confirmed live. Player props at May 2023 is consistent across both the general and WNBA pages (though the WNBA page never states the date itself — it's inferred by applying the general "additional markets" policy).

### 1d. What is NOT documented anywhere found

- No explicit statement of when `basketball_wnba` was added as a sport key to the live API (which would be the true floor for any historical data on that sport, since you can't have historical snapshots of a sport before its odds were being ingested at all).
- No per-book breakdown of which sportsbooks' WNBA player props are actually captured historically (the WNBA page says "most US bookmakers" for current/live coverage, not stated for historical).
- No documented gap/outage calendar (whether every single day back to May 2022 actually has snapshots, or whether there are known holes).

---

## 2. Player props historical availability — WNBA

DOCUMENTED (inferred by combining §1a general policy + §1b WNBA market list, NOT independently confirmed for WNBA):
- If WNBA player props are treated as "additional markets" under the general policy, historical availability would start **2023-05-03**, at 5-minute snapshots.
- Markets: `player_points`, `player_rebounds`, and likely other player_* keys (points, rebounds, assists, threes, etc. by analogy to NBA — **not explicitly enumerated for WNBA** in what was fetched).

INFERRED, NOT DOCUMENTED: full list of WNBA player prop market keys and per-book coverage. This needs to come from the live API's `/v4/sports/basketball_wnba/odds?markets=...` response or the markets-list documentation page, which was not fetched in this pass.

---

## 3. Plan tiers, pricing, and historical/player-props quota cost

Two materially different pricing narratives turned up across sources. Flagging both, vendor's own site wins as primary but is itself possibly cached/stale relative to what's live today.

### 3a. Vendor homepage (source: `the-odds-api.com/`, DOCUMENTED via fetch-tool paraphrase)
- **Starter (Free):** 500 credits/month
- **20K plan:** $30/month — 20,000 credits
- **100K plan:** $59/month — 100,000 credits
- **5M plan:** $119/month — 5,000,000 credits
- **15M plan:** $249/month — 15,000,000 credits
- **Custom:** contact sales, higher volume
- Stated: "All tiers include All sports, All bookmakers, All betting markets, and Historical Odds" — i.e., per this page, **historical access is not gated behind a specific tier**, it's universal on paid plans (and possibly even the free Starter tier — ambiguous, needs live confirmation since a separate general page said "historical data is only available on paid usage plans," which would exclude the free Starter tier).
- Player props: "now available in the API for selected US sports and bookmakers, with more on the way" — no tier gate stated here.

### 3b. Third-party aggregator summaries (UNVERIFIED, third-party, likely stale or describing a different/older plan structure — do NOT rely on)
- Named a "Professional $29/mo," "Business $99/mo," "Champion $49/mo," "Superstar $99/mo," "Legend $199/mo" tier structure, with player props and "full historical odds archive at zero extra credit cost" gated to the $99/mo Business tier.
- This tier-naming does not match the vendor homepage's own 20K/100K/5M/15M naming at all. Likely either an outdated snapshot of the vendor's actual historical pricing page (which changes tier names periodically) or confusion with a *different* odds API vendor. **Do not use these third-party numbers for budgeting.**

### 3c. Quota / credit cost for historical calls (DOCUMENTED, consistent across vendor's own pages — higher confidence)
- Regular (live/upcoming) odds request cost: `markets × regions` credits.
- Historical odds request cost: **`10 × markets × regions`** credits (featured markets), and **`10 × markets × regions` per event** for additional markets (player props) via the historical event-odds endpoint — i.e., historical player-prop pulls are charged per-event, not per-slate, which matters a lot for a full-season backfill cost estimate.

### 3d. Rough full-season WNBA backfill cost — ORDER OF MAGNITUDE ONLY, NOT A QUOTE

Not independently modeled with real numbers here — flagging this explicitly as a gap rather than fabricating a credit estimate. A real estimate requires knowing: (a) actual confirmed historical floor date for WNBA (§1c unresolved), (b) number of games/season (~240 regular season + playoffs), (c) how many 5-minute snapshots per game-window you actually want (not the full pregame-to-close window necessarily — probably a bounded pre-game and in-game capture window), (d) number of markets × regions × bookmakers per pull, (e) whether player-prop historical pulls are charged per-event as stated in §3c (which multiplies cost heavily for a full season of full-roster props). **This must be computed as a discrete step in §6 against real per-request costs from a trial key before any purchase decision, not estimated here from unverified pricing narratives.**

---

## 4. Licensing

DOCUMENTED (source: `the-odds-api.com/terms-and-conditions.html`, via fetch-tool paraphrase — recommend a verbatim read before signing anything):
- **Personal/internal analytical and betting-research use: explicitly supported.** The vendor "supports and encourages" use of the data "in websites, mobile apps, dashboards, analytical tools, and other user-facing applications, including commercial use, provided our data is not the primary product being sold or redistributed."
- **Redistribution/resale explicitly prohibited:** "Do not resell, repackage, or redistribute our data as a standalone data product" — covers "your own API, data feed, downloadable files, or any other format intended to serve as a source of raw data for others." This matters if any future step of this program considers selling or sharing raw odds feeds outside the model/program itself; internal model use is fine, standing up our own odds-data product/feed on top of it is not.
- **Storage/retention rights: NOT ADDRESSED.** No clause found that either grants or denies the right to store historical pulls long-term in our own database. This is a real gap — most vendors in this space implicitly permit local caching for the subscription term (that's the entire point of a historical archive product), but "not addressed" is not the same as "confirmed permitted," and terms can also require deletion on subscription lapse. **Needs a direct question to team@the-odds-api.com or a re-read of the full terms page verbatim**, not an inference.
- **Model-training rights: NOT ADDRESSED.** No clause found either permitting or prohibiting using the historical odds data to train a statistical/ML model (which is exactly our use case). Silence here is a genuine open question, not a green light — flag before committing budget.
- **Accuracy/latency disclaimer:** "Wagering markets are highly volatile; on occasion, errors or additional delays may be present." Vendor disclaims liability for actions taken on "correct, erroneous, or outdated" data, and pushes responsibility to the user to "independently verify the accuracy of the data with the respective wagering operator." **No numeric latency bound is published.**

---

## 5. Timestamp semantics and vendor latency (amendment 4 — mandatory framing)

DOCUMENTED:
- The `timestamp` field returned by the historical endpoint is defined as "the closest available timestamp equal to or earlier than the provided date parameter" — i.e., it is **the API's own snapshot-capture time**, the moment their system polled/ingested the book's line, not the moment the sportsbook itself published or moved the line.
- No documented bound on the gap between (book publishes/moves a line) and (the-odds-api.com's system captures it as a snapshot). The only latency-adjacent language found is the general disclaimer that "errors or additional delays may be present," which is a liability disclaimer, not a latency spec.
- Practical consequence for this program: **any claim of the form "the market moved before/after event X by N seconds/minutes" built on this historical archive must be stated with an explicit uncertainty band**, because (a) snapshot granularity itself is 5 minutes (post-2022) or 10 minutes (pre-2022) — meaning true line-change time could be anywhere inside that window, and (b) there is an additional, undocumented and unbounded vendor-side capture latency stacked on top of the snapshot grid. Per amendment (4), this uncertainty (grid granularity + unbounded vendor latency) must be carried as an explicit term in every downstream reaction-time claim, not silently assumed to be zero or "close enough."

---

## 6. Verification queries to run against a free/trial key BEFORE any purchase

None of these have been run yet — this list is the actual verification plan, not a substitute for it. Recommend running all of these on the free Starter tier (or a short trial) before committing to a paid plan:

1. `GET /v4/sports?apiKey=...` — confirm `basketball_wnba` is a live, active sport key today, and check if the response or docs expose an "active since" date.
2. `GET /v4/historical/sports/basketball_wnba/odds?apiKey=...&regions=us&markets=h2h&date=2022-01-01T00:00:00Z` (and step forward month by month toward mid-2022) — find the actual earliest date that returns real data rather than an empty/error response. This directly resolves the §1c conflict (2020 vs May 2022 floor).
3. Repeat the same walk-forward test for `date=2023-01-01...2023-06-01` with `markets=player_points` on the historical **event**-odds endpoint — confirm actual WNBA player-prop historical floor (§2 is inferred, not confirmed).
4. Pull one full day of 5-minute snapshots for a single known WNBA game and manually diff consecutive snapshots against a known line-movement source (e.g., a screenshot/log of a book's actual posted line) to empirically estimate real-world vendor capture latency, since none is published (§5).
5. Check the actual current credit cost charged for one historical featured-market call and one historical player-prop event call against account usage dashboard, to confirm the documented `10×` multiplier and per-event charging in §3c before modeling season-backfill cost.
6. Confirm on the live pricing/checkout page (not just the marketing homepage) which paid tier is the cheapest one that unlocks historical + player props, since §3a and §3b materially disagree.
7. Email team@the-odds-api.com directly to get written confirmation on: (a) WNBA historical floor date, (b) storage/retention rights for historical pulls after subscription lapse, (c) whether internal model-training use is permitted under "analytical tools" language in the terms.

---

## 7. Fallback alternatives — quick survey (not deep-verified, flagging for later deep dive if Odds API historical floor proves insufficient)

DOCUMENTED at a shallow, search-summary level only — none of these were fetched from primary docs in this pass; treat as leads, not verified facts:

- **SportsDataIO**: Search summary claims historical betting lines "from 2019 onwards" across major sports with "props and futures from 2020," and states WNBA is among covered leagues in their production historical API, connected to a "new Data Warehouse." If true this would be a materially deeper historical floor than the-odds-api.com's WNBA May-2022 figure — worth a real verification pass if the-odds-api.com's WNBA floor turns out to be a hard blocker for pre-2022 backfill needs.
- **OpticOdds**: Search summary claims "years of historical sports betting odds across 200+ sportsbooks with timestamped, normalized data for backtesting, CLV analysis, and quantitative research," and lists WNBA among covered basketball leagues for live odds. Historical WNBA-specific depth not confirmed in this pass.
- **Unabated**: Search summary describes live WNBA odds/props comparison tooling (spread, moneyline, totals, player props) but nothing found describing a historical archive/API product in what was searched — may be more of a live consumer tool than a historical data vendor; needs direct check of their API product page if pursued.

None of the three alternatives had pricing, quota cost, licensing, or exact WNBA historical start dates verified in this pass. If the-odds-api.com's WNBA floor (§1c) turns out to genuinely start no earlier than May 2022, and the program needs data before that, SportsDataIO is the first fallback worth a real primary-source verification pass given its claimed 2019/2020 floor.

---

## 8. Recommendation and the exact user decision required

**Recommendation:** Do not purchase a paid Odds API plan yet. Run the seven verification queries in §6 against the free Starter tier first (500 credits/month should be enough to answer questions 1–3 and 6–7 without spending money; question 4 needs one day of a single game's snapshots, also cheap; question 5 needs at minimum a live paid-tier account to see real credit deduction, but can be deferred to a one-month low-tier trial). Total cost to fully resolve every open question here: at most one month of the cheapest paid tier (~$30/mo per the vendor homepage, unconfirmed against live checkout), plus free-tier credits for the rest.

**Exact decision needed from the user:**
1. Authorize spending on a free-tier or trial Odds API key (no cost) to run verification queries §6.1–§6.3, 6.6, 6.7 now — recommended, no purchase involved.
2. Separately authorize (yes/no, and if yes at what dollar ceiling) upgrading to a one-month low paid tier (~$30/mo, to be reconfirmed against live checkout before charging) to run §6.4–§6.5 and get a real, empirically-measured vendor latency figure and confirmed credit-cost model for a full-season backfill estimate — this is the step that actually costs money and should not proceed without explicit sign-off.
3. Decide whether the WNBA historical floor question (§1c: 2020 vs May 2022) is a hard gate on proceeding with any live-capture/backfill work under amendment (3)'s critical path, or whether the critical path (high-frequency live capture, event-to-market linkage, competitor projection archiving) can proceed in parallel while the historical-backfill floor question is still being resolved — my read is these are independent enough to run in parallel, but flagging for explicit confirmation since amendment (3) names live capture as the *immediate* critical path and this historical-verification task as amendment (1)'s separate, also-urgent track.

---

## 9. Bounded legitimate uses of the existing final-state odds archive (amendment 2 — cross-reference)

Amendment (2) asks that the existing 813-game final-state retrospective archive (ruled CUTOFF_UNPROVEN for timing claims in D016/P2B) have its bounded legitimate uses enumerated rather than discarded. That archive is **not** Odds-API-sourced and is out of this role's direct scope (a separate ownership boundary), but noting the connection here since it's directly relevant to how any newly-verified Odds-API historical data would complement or supersede it: if the Odds-API WNBA historical floor is confirmed usable back to May 2022 (or earlier via a fallback vendor), that new source could supply the point-in-time granularity the existing final-state archive structurally cannot (it has one snapshot per game, no intra-game timing), while the final-state archive would remain legitimately usable for closing-line-only comparisons, longer-horizon retrospective checks, and any analysis that only ever needed a single end-state number rather than a timing claim. Full enumeration of that archive's bounded uses is presumably a separate role's deliverable — flagging the connection here only so the coordinator can sequence the two pieces of work sensibly, not attempting to complete that enumeration in this document.
