# SX Bet Terms and Conditions — verbatim ToS posture (D033 honesty-preservation step)

**Retrieved:** 2026-08-06 (this session), via WebFetch
**Source URL:** `https://help.sx.bet/en/articles/3613372-terms-and-conditions` ("Terms and Conditions")
**Companion source:** `https://help.sx.bet/en/articles/12984899-api` ("API" help article)
**Method:** direct fetch of SX Bet's own published Help Center articles; not itself a request against
`api.sx.bet` or any market-data endpoint.

This file exists for the same reason `kalshi/DATA_TERMS_OF_USE_VERIFIED_2026-08-06.md` exists on the
sibling track: before building any standing capture, verify the CURRENT data-terms text verbatim, and
surface the exact quote if it conflicts with what's being asked, per the D031 honesty-preservation
pattern (Kalshi-specific ruling) and per M00 contract §9.7 (ToS interpretation is a USER_REQUIRED
action, never the graph's own reading of convenience).

## Verbatim text, Terms and Conditions

> "use any robot, spider, crawler, scraper, or other automated means or interface not provided by us,
> to access the service or to extract data"

> "As between us and you, we are the sole owners of the rights in and to the Service, our technology,
> software and business systems (the "Systems") as well as our odds."

> "You agree not to use any automatic or manual device to monitor or copy web pages or content within
> the Service."

> "to scrape our odds or violate any of our intellectual property rights" [listed among prohibited
> conduct]

> "No information or content on the Service or made available to you in connection with the Service
> may be modified or altered, merged with other data or published in any form including for example
> screen or database scraping"

> Nextgen Blockchain Technologies LTD owns the service and grants "a limited, revocable, transferable
> license to access and use the portions of the service that are proprietary to SX." Also: "you may
> not resell, lease, lend, share, distribute or otherwise permit any third party to use the service,
> or use the service for time-sharing or service bureau purposes."

## Verbatim text, API help article (`help.sx.bet/.../12984899-api`)

> "You can access endpoints, pull markets/odds, and post or fill orders without an API key... SX Bet
> provides free access to the API."

No separate "API Terms of Use" document distinct from the general Terms and Conditions was found —
the help article does not carve out or cross-reference an API-specific license that overrides the
scraping/automation clauses above.

## The tension, stated plainly

Two things are both true and not obviously reconciled by SX Bet's own published text:

1. SX Bet **operates and actively promotes** a documented, free, no-key-required REST API
   (`api.sx.bet`) whose stated purpose includes letting third parties "pull markets/odds." This is
   materially different from Kalshi's Data Terms of Use, which contain **no** API-specific carve-out
   at all — Kalshi's clause reaches "any portion of the Website" without qualification.
2. SX Bet's general Terms and Conditions simultaneously (a) claim ownership of "our odds" as IP,
   (b) prohibit "robot, spider, crawler, scraper, or other automated means **not provided by us**" —
   which arguably does NOT reach the official API, since the API *is* "provided by us" — but also
   (c) separately list "to scrape our odds" as prohibited conduct with no "not provided by us"
   qualifier attached, and (d) prohibit content being "merged with other data or published in any
   form including... database scraping," language that is not obviously limited to unauthorized
   scraping methods.

Reading (b) alone, an engineer could conclude the official API is a sanctioned automated means and
therefore exempt from the general anti-scraper clause. Reading (c) and (d) alone, an engineer could
conclude any programmatic archival of "our odds" — even via the sanctioned API — is prohibited absent
SX Bet's consent, since those two clauses aren't qualified by "not provided by us." SX Bet's own
documents do not resolve which reading controls, and this track is not the appropriate place to
resolve it: M00 §9.7 assigns "ToS interpretation" to the user exclusively, and §11 lists "accepting
scraping/licensing risk" as a lane-wide stop condition that HALTs to USER_REQUIRED.

**This is a genuinely different fact pattern from D031's Kalshi ruling**, not a re-litigation of it.
D031 resolved a Kalshi-specific question (whether the permission-letter dependency was necessary given
Kalshi's *own* public-endpoint documentation) but did not rule on SX Bet's terms, and the D031 text
that added "SX Bet as a candidate under the same D028 gates" did not include a ToS reading for SX Bet.
See `HALT_USER_REQUIRED.md` in this directory for the disposition this produces.
