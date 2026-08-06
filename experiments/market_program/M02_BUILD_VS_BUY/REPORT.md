# M02_BUILD_VS_BUY — Vendor decision matrix and costed build-vs-buy recommendation

**Node:** M02_BUILD_VS_BUY · **Lane:** market_intelligence · **Date:** 2026-08-06

## Epistemic status (verbatim, per node prompt)

DECISION PREPARATION. Produces the evidence and the costed options for a purchase decision that is NOT this node's to make: every line item that spends money routes to the M02B_VENDOR_PURCHASE_DECISION human gate. The Odds API verification was already running when this node was created (D023 amendment 1); its output is an INPUT to this node and lands under this node's directory.

---

## 0. Frozen-bytes verification (before relying on anything below)

Both governing artifacts were hashed directly against the working tree before use:

```
MARKET_PROGRAM_CONTRACT.md   sha256 = 1152dcd3bf74000f700844bc8bfc0df25de61a067f59534a714ac4f2f20265de   MATCH
TAXONOMY.json                sha256 = c83e25e783a4ee8642a26dd416362e46c2c34196ff8f8354977c28b72940a12c   MATCH
```

Command run: `Get-FileHash -Algorithm SHA256 <path>` against both files in
`experiments/market_program/M00_MARKET_PROGRAM_CONTRACT/`. Both matched the hashes given in this
node's task instructions exactly. No discrepancy to report.

The two W1_DRAFTS inputs this node consumes were also hashed at the moment of use:

```
W1_DRAFTS/ODDS_API_VERIFICATION.md    sha256 = 9f36ce41f5dd7380278b0515d8978b450e34d4ec7e8a2a5917c4a98c409da882
W1_DRAFTS/CAPTURE_UPGRADE_DESIGN.md   sha256 = cb83a0b4d6386a3b0f5eb00f3eb870308d98d9e15b3febc71dc59b25a5001a15
```

`CAPTURE_UPGRADE_DESIGN.md`'s hash matches the frozen `input_hashes_working_tree` entry recorded in
`TAXONOMY.json` at M00 contract-freeze time. `ODDS_API_VERIFICATION.md` is **not** in that frozen
list -- TAXONOMY.json only froze `VENUE_EXECUTION_RESEARCH`, `CAPTURE_UPGRADE_DESIGN`, and
`COMPETITOR_ARCHIVE_DESIGN` at contract time, because the Odds API verification effort (D023
amendment 1) was still running in parallel when M00 froze. Per this node's mandate, that file is
consumed here as a live input, checked (read in full, not skimmed), and neither re-run blindly nor
contradicted without bytes.

---

## 1. What this node found: the state of VENDOR_MATRIX.json

**Consequential fact:** `experiments/market_program/M02_BUILD_VS_BUY/VENDOR_MATRIX.json` already
existed on disk when this node began, containing a complete, internally-hashed prior pass over
exactly the same two input documents (its own recorded input hashes for `ODDS_API_VERIFICATION.md`
and `CAPTURE_UPGRADE_DESIGN.md` were measured independently by this node and matched byte-for-byte).
`REPORT.md` did not exist. This node treated the existing `VENDOR_MATRIX.json` as legitimate prior
work inside its own write scope -- not a foreign artifact to overwrite blindly -- verified its
citations (the `M00-U1` caveat hash it recorded, `1055871c6d535521e86a51e4d5b735b013d88030505ae7e3b0eaca71f4cc80d6`,
was checked against `TAXONOMY.json` line 184 and matches exactly), and **extended it in place**
with new, independently-fetched evidence rather than discarding it. This is reported as a
consequential fact, per the standing rule against narrating routine steps but reporting anything
unusual: an artifact appearing pre-populated inside a fresh node's write scope is unusual enough to
flag, even though its contents checked out as sound.

---

## 2. What was measured, and how

| What | Command / method | Result |
|---|---|---|
| Contract + taxonomy hash verification | `Get-FileHash -Algorithm SHA256` | Both match exactly (Sec.0) |
| Input-doc hash verification | `Get-FileHash -Algorithm SHA256` on both W1_DRAFTS files | `CAPTURE_UPGRADE_DESIGN.md` matches TAXONOMY.json's frozen record; `ODDS_API_VERIFICATION.md` measured but not TAXONOMY-frozen (expected, see Sec.0) |
| SportsDataIO historical-odds product page | `WebFetch https://sportsdata.io/historical-sports-odds-data` | HTTP 404 -- page not found at that URL in this pass |
| SportsDataIO historical mechanics | `WebSearch "SportsDataIO WNBA historical odds API pricing point-in-time snapshot"` | Search-summary claims per-change timestamps for at least the <30-day product; ambiguous for the >30-day warehouse; no pricing surfaced |
| SportsDataIO Historical Data Guide (primary doc) | `WebFetch https://support.sportsdata.io/hc/en-us/articles/4405005816215-Historical-Data-Guide` | HTTP 403 -- blocked, could not read primary source directly |
| SportsGameOdds (SGO) current site | `WebFetch https://sportsgameodds.com/` | Historical data confirmed as a $299/mo Pro-tier feature; **WNBA absent from the site's own listed leagues**, contradicting the legacy research report's "WNBA included" claim |

No purchase, subscription, credential, or scraping action was taken to produce any of the above --
all fetches were of public marketing/search-indexed pages, consistent with this node's stop
conditions.

---

## 3. What could not be established, and why

- **The 2020-06-06 vs May-2022 WNBA historical-floor conflict is UNRESOLVED.** The Odds API's
  general historical-odds documentation states featured-market history for "all sports" from
  2020-06-06; its WNBA-specific product page states featured-market history from May 2022. These
  cannot both be the true WNBA floor. This node did not resolve it -- resolving it requires a live
  API call (verification query Q2 in the decision packet below), which this node is not authorized
  to run (it would require provisioning a credential, a USER_REQUIRED action per this node's stop
  conditions). **Stated per the acceptance criteria's explicit requirement to state this conflict,
  not resolve it.**
- **Whether SportsDataIO's >30-day "Historical API data warehouse" preserves per-change timestamp
  granularity, or collapses to closing-line-only once data ages out of the live product, could not
  be established.** The one primary-source document that would answer this (SportsDataIO's own
  Historical Data Guide) returned HTTP 403 when fetched directly in this pass. Only a
  search-engine-summarized paraphrase was obtainable, which is explicitly a weaker evidentiary
  status than a direct page read (this is the same distinction ODDS_API_VERIFICATION.md itself draws
  between its own fetch-tool paraphrases and a "read the actual terms document" standard).
- **SportsDataIO, OddsJam, MetaBet, BetsAPI, and JsonOdds pricing** could not be established from
  any source available to this node -- SportsDataIO requires direct sales contact ("Enterprise
  pricing"); the others had no pricing information in either the wnba_odds_system legacy research
  report or this node's own light verification pass.
- **Whether the wnba_odds_system/ legacy scraper's 2025-07-02 collection run against OddsPortal /
  BetInf.com / ESPN actually completed and how many records it produced** could not be established
  -- CURRENT_STATUS.md is a mid-run handoff document dated over a year before this node's execution,
  not a completion report, and this node has no live process-status access to that legacy system.
- **A numeric vendor-latency bound for The Odds API** does not exist anywhere in what was found --
  only a general liability disclaimer. Per amendment 4, this is why the historical timestamp field
  is reported UNBOUNDED, not assigned a number.

---

## 4. Contradictions found between documents, or between a document and the bytes

1. **The Odds API's own two pages disagree on the WNBA historical floor** (2020-06-06 general vs
   May-2022 WNBA-specific) -- this is the conflict the acceptance criteria explicitly required this
   report to state. See Sec.3 above and VENDOR_MATRIX.json's
   `coverage_conflict_reported_not_reconciled` block. **Not reconciled by this node.**
2. **SportsGameOdds (SGO): the wnba_odds_system legacy research report (dated January 2025, no
   citation given) names SGO as "Best Value" and states "WNBA included in their basketball
   offerings."** This node's own direct fetch of SGO's current live site (2026-08-06) lists 67+
   leagues by name and WNBA is not among them. This is a genuine contradiction between an older,
   uncited third-party report and this node's own live bytes. **Not reconciled** -- three
   explanations are open (the report was wrong when written; SGO has since dropped WNBA; or the
   fetched page simply didn't render the full league list) and none is confirmed. Recorded in
   VENDOR_MATRIX.json under vendor `SPORTS_GAME_ODDS_SGO`.
3. **The Odds API's own pricing pages disagree with each other** on whether historical access is
   included even at the free Starter tier or gated to paid tiers only -- carried forward from
   ODDS_API_VERIFICATION.md Sec.3a, not independently re-resolved by this node (that resolution is
   verification query Q6 in the decision packet, requiring a live checkout page view).
4. **Third-party aggregator pricing summaries for The Odds API name an entirely different tier
   structure** ($29/$49/$99/$199-named tiers) than the vendor's own site (20K/100K/5M/15M-named
   tiers) -- flagged by ODDS_API_VERIFICATION.md itself as likely stale or describing a different
   vendor; this node does not use those figures for any cost line.

---

## 5. Stop conditions considered

- **Scraping/licensing risk (wnba_odds_system/ build option):** This candidate's own legacy
  documentation names OddsPortal, BetInf.com, and ESPN as scrape targets with no ToS clearance
  documented anywhere in the material reviewed, and its own docstring already treats a paid API as
  the fallback FROM scraping, not the reverse. **This trips the stop condition** "a finding would
  require ... accepting scraping or licensing risk -- HALT and raise to a USER_REQUIRED gate, do not
  resolve it inside the node." This node does not resolve it and does not recommend pursuing this
  path; it is raised to M02B_VENDOR_PURCHASE_DECISION as a flagged, not-recommended option, per
  VENDOR_MATRIX.json's `BUILD_WNBA_ODDS_SYSTEM_SCRAPER_STACK` entry.
- **Reaction-time/latency claims:** No vendor surveyed publishes a numeric latency bound. Every
  latency-adjacent field in VENDOR_MATRIX.json is recorded UNBOUNDED or UNVERIFIED rather than
  assigned a number, per amendment 4's requirement that a claim unable to carry both a
  timestamp-uncertainty and vendor-latency term be reported UNSUPPORTABLE rather than stated
  without them. No sharp timing claim is made anywhere in this deliverable.
- **Final-state archive bounded-uses enumeration:** This node cites the owned archive only as the
  fixed CUTOFF_UNPROVEN comparison baseline the acceptance criteria require, using use-class
  M00-U1 (coverage census) with the caveat text reproduced verbatim and its hash checked against
  TAXONOMY.json. No new use of the archive is proposed and no use outside the M00 contract's
  enumerated classes is invoked -- the bounded-uses enumeration itself is not reopened or extended by
  this node.
- **No purchase, subscription, or credential entry was made.** Every line item in
  VENDOR_MATRIX.json's `recommendation.line_items_for_m02b_gate` -- including the $0 ones -- is
  explicitly flagged `purchase_made_by_this_node: false` and routed to M02B_VENDOR_PURCHASE_DECISION.

---

## 6. Vendor matrix summary (full detail in VENDOR_MATRIX.json)

| Vendor | Point-in-time verdict | Cost known? | Recommended action |
|---|---|---|---|
| Owned final-state archive | T2_CUTOFF_UNPROVEN (settled, D016/P2B) | N/A (owned) | Comparator baseline only |
| The Odds API -- historical tier | T1_VENDOR_ASSERTED_TIMESTAMPED (documented, unverified live) | Live tier known ($30/mo 20K plan); historical backfill cost UNKNOWN pending live-key numbers | Lead candidate -- verify free, then trial |
| SportsDataIO | T1_CANDIDATE_UNVERIFIED (search-summary claim, primary doc blocked at 403) | Not disclosed (enterprise sales only) | First fallback to verify if Odds API floor proves insufficient |
| OpticOdds | T1_CANDIDATE_UNVERIFIED (own marketing language claims "timestamped" data) | Not found | Second fallback -- CLV framing matches this program's use case most directly |
| SportsGameOdds (SGO) | UNKNOWN_INSUFFICIENT_INFO -- WNBA coverage itself contradicted between sources | $299/mo Pro tier (for historical feature, WNBA unconfirmed) | Do not prioritize; resolve WNBA-coverage contradiction first if pursued at all |
| OddsJam | UNKNOWN_INSUFFICIENT_INFO (no historical product found; live/speed-focused) | Not found | Not a historical-backfill candidate on current evidence |
| MetaBet | NOT_APPLICABLE (no historical product found) | Not found | Not a historical-backfill candidate |
| SportsOddsHistory.com | CUTOFF_UNPROVEN (default classification for an unverified free "archive" with no stated snapshot methodology) | Free (browsing); bulk/programmatic access unverified | Low priority |
| BetsAPI | UNKNOWN_INSUFFICIENT_INFO | Not found | Lowest priority -- no detail found |
| JsonOdds | UNKNOWN_INSUFFICIENT_INFO | Not found | Lowest priority -- no detail found |
| Unabated | NOT_APPLICABLE (live tool, no historical product found) | Not found | Not a historical-backfill candidate |
| Build/extend wnba_odds_system/ scraper | LIKELY_CUTOFF_UNPROVEN_OR_WORSE | $0 direct + substantial recurring labor | **Not recommended -- stop condition tripped (scraping/licensing risk)** |

---

## 7. Costed recommendation

**Do not purchase anything yet.** No vendor surveyed has both a live-key-confirmed WNBA historical
floor date and a live-checkout-confirmed price. The recommended path is incremental and mostly
free:

1. Run the free-tier verification queries against The Odds API ($0) -- resolves the 2020-vs-2022
   floor conflict and most of the open pricing/coverage questions.
2. The 20K/$30-per-month tier is already the live-capture critical path's own recommendation
   (CAPTURE_UPGRADE_DESIGN.md) -- a historical-tier decision on this vendor is therefore additive
   credit draw on a plan the program needs regardless, not a second standalone contract. This is the
   single most consequential fact favoring The Odds API over any fallback: every fallback vendor
   would require a second, independent contract and integration.
3. Only if the confirmed WNBA floor proves insufficient does amendment 1's instruction -- "acquiring
   historical point-in-time data by another route becomes a program priority" -- trigger a
   verification pass on SportsDataIO and/or OpticOdds, the two named alternatives whose own language
   claims genuine per-change timestamps (as opposed to closing-line-only or undisclosed granularity).
4. Do not pursue the wnba_odds_system/ scraper build option -- stop condition tripped.

---

## 8. Exact decision packet for the M02B human gate

### 8.1 Tier commitment

**The Odds API, 20K plan, $30/month.** Same tier the live-capture critical path
(CAPTURE_UPGRADE_DESIGN.md) already recommends independently, with 3-11x modeled headroom over
live ladder+burst load on that document's own numbers. Historical calls draw from the same 20K
credit pool at the documented 10x per-call multiplier -- no separate "history tier" purchase is
expected. Do not commit to 100K or higher until real telemetry (per CAPTURE_UPGRADE_DESIGN.md's
own break-even language) shows sustained usage above ~15,000/month.

### 8.2 Trial-key verification queries to run first (in order)

1. `GET /v4/sports?apiKey=...` -- confirm basketball_wnba is a live active sport key today; check
   for an "active since" date.
2. `GET /v4/historical/sports/basketball_wnba/odds?apiKey=...&regions=us&markets=h2h&date=2022-01-01T00:00:00Z`,
   stepped month-by-month toward mid-2022 -- find the actual earliest date returning real data.
   **This is the query that resolves the 2020-06-06 vs May-2022 conflict.**
3. Repeat the same walk-forward for date=2023-01-01 through 2023-06-01 with markets=player_points
   on the historical event-odds endpoint -- confirms the WNBA player-prop historical floor (currently
   inferred, not confirmed).
4. Pull one full day of 5-minute snapshots for one known WNBA game; diff consecutive snapshots
   against an independently logged real line-movement source to empirically estimate vendor capture
   latency (none is published).
5. Check the actual credit cost charged (account usage dashboard / x-requests-used header) for one
   historical featured-market call and one historical player-prop event call -- confirms the
   documented 10x multiplier and per-event player-prop charging.
6. Confirm on the live checkout/pricing page (not the marketing homepage) which paid tier is the
   cheapest that unlocks historical + player props.
7. Email team@the-odds-api.com for written confirmation of: (a) WNBA historical floor date, (b)
   storage/retention rights for historical pulls after subscription lapse, (c) whether internal
   model-training use is permitted under the terms' "analytical tools" language.

### 8.3 Historical backfill sizing formula, awaiting live-key numbers

```
credits_featured = snapshots_per_game_in_window x 10 x markets_featured x regions x N_games
credits_props     = snapshots_per_game_in_window x 10 x markets_props    x regions x N_games   (per-event charging)
total_credits     = credits_featured + credits_props
total_usd_at_20K_plan = (total_credits / 20000) x 30    [only valid within a single month's allotment; overage/rollover policy undocumented]
```

Unbound inputs, each pending live-key or scope confirmation:

- **N_games** -- depends entirely on query 2's answer. If the WNBA floor confirms at 2020-06-06,
  N_games spans ~6 seasons (2020-2025); if it confirms at the conservative working assumption of
  May-2022, N_games spans ~4 seasons (2022-2025) -- roughly a 1.5x cost difference on this input
  alone, before any other variable is considered.
- **snapshots_per_game_in_window** -- a scope decision, not a vendor fact: how many of the
  available 5/10-minute-grid points per game the program actually wants pulled for a pregame
  backfill. Not yet decided; belongs at M02B, not fixed by this node.
- **markets_featured / markets_props / regions** -- markets_featured=3 (h2h/spreads/totals)
  and regions=1 (us) are known from the live-capture design's own cost model; markets_props (how
  many player_* keys to backfill) is not enumerated anywhere for WNBA -- flagged as inferred by
  analogy to NBA only in ODDS_API_VERIFICATION.md Sec.2.

**Illustrative example only, not a quote:** at N_games=1000, 8 snapshots/game (matching the live
ladder's own rung count), 3 featured markets, 1 region: credits_featured = 8 x 10 x 3 x 1 x 1000 =
240,000 credits -- 12x the 20K plan's entire monthly allotment in a single month. This shows the
formula is not a rounding error away from ordinary live-capture headroom; a real backfill of this
shape needs either a spread across multiple billing months or a temporarily higher tier, and must be
sized with real N_games and real per-call costs (queries 2 and 5) before any dollar figure reaches
a human for approval.

### 8.4 No purchase made

This node made no purchase, opened no subscription, and entered no credential. Every costed line
item above routes to M02B_VENDOR_PURCHASE_DECISION.
