# Kalshi Data Terms of Use — verbatim re-verification (D031 honesty-preservation step)

**Retrieved:** 2026-08-06 (this session), via WebFetch
**Source URL:** `https://kalshi-public-docs.s3.amazonaws.com/kalshi-data-terms-of-service.pdf`
(the same document FREE_DATA_SURVEY/MARKET_SOURCES.md §8 cited)
**Method:** direct fetch of the PDF; no scripted access to any Kalshi API or website endpoint was
made to obtain this — it is Kalshi's own published legal document, fetched once by a human-facing
tool, not "used" as Kalshi Data.
**Document title as rendered:** "KALSHI DATA TERMS OF USE". No revision/effective date is printed
on the document itself.

This file exists to satisfy D031's explicit condition: *"the capture builder re-verifies the
CURRENT data-terms text verbatim as it builds; if the explicit archival-prohibition clause the
survey quoted still stands, the exact quote is surfaced to the user once before capture starts -
otherwise capture begins."*

## Verbatim text, full document

### Preamble

> Content on the kalshi.com website ("Website") is owned or licensed by Kalshi and is protected by
> worldwide intellectual property laws. The products, technology or processes described in this
> Website may also be protected by intellectual property rights of Kalshi or third parties. No
> license is granted with respect to those intellectual property rights. By accessing the Website,
> you acknowledge and agree that you are requesting access to the Kalshi Data made available on the
> Website.
>
> The content on the Website includes, without limitation: volume, bid-ask prices, opening and
> closing range prices, high-low prices, settlement prices, indexes, open interest and related
> information, market descriptions, materials, and other content on the Website ("Kalshi Data").
> Kalshi Data is calculated according to the proprietary methods of Kalshi or certain third-parties
> with which Kalshi has a relationship with and through the application of methods, creativity and
> standards of judgment used and developed through the expenditure of considerable work, time and
> money, and may be modified from time to time based on this same or other criteria, and all
> rights, title, and interest therein are expressly reserved by Kalshi.
>
> All access and use of Kalshi Data is subject to these Kalshi Data Terms of Use. You acknowledge
> and agree that the reservation of rights by Kalshi in these Kalshi Data Terms of Use is
> appropriate.

### I. PERMITTED USES

> You are only permitted to access and use the Kalshi Data in the form in which it is presented on
> the Website. You understand, acknowledge and agree, that use of Kalshi Data is at your sole risk.
> You may access content only for your personal use for non-commercial purposes. Non-commercial use
> does not include the use of Kalshi Data without prior written consent from Kalshi in connection
> with: (1) the development of any software program, including, but not limited to, training a
> machine learning or artificial intelligence system; or (2) providing archived or cached data sets
> containing Kalshi Data to another person or entity. You understand, acknowledge and agree that the
> Kalshi Data is provided "as is" and Kalshi does not warrant the accuracy, completeness,
> non-infringement, timeliness or any other characteristic of the Kalshi Data. All Kalshi Data
> contained within the Website should be considered as a reference only and should not be used as
> validation against, nor as a complement to, any Kalshi data feeds.

### II. PROHIBITED USES

> You acknowledge and agree that, unless Kalshi, its applicable affiliate, and/or an applicable
> third party provider give you prior written authorization, you are strictly prohibited from
> selling, licensing, renting, modifying, changing, manipulating, altering, printing, collecting,
> copying, reproducing, downloading (other than to view only where a link is provided), uploading,
> transmitting, disclosing, distributing, disseminating, publicly displaying, publishing, editing,
> adapting, creating derivative works, electronically extracting or scrubbing, scraping, compiling
> (including, without limitation, through framing or systematic retrieval to create collections,
> compilations, databases or directories) or conducting 'text and data mining' (as those terms are
> defined in EU Directive 2019/790) in relation to any Kalshi Data and other Kalshi intellectual
> property you access via the Website or otherwise transfer any of the content to any third person
> (including, without limitation, others in your company or organization).
>
> You agree not to, and have no rights to, use the Kalshi Data to create, calculate, issue, settle,
> maintain, support or develop any financial instruments (including but, without limitation exchange
> traded products, certificates, warrants, contracts for difference, swaps, options, structured
> products), indexes, products, services (including but without limitation, portfolio management
> services, pre- and post-trade risk management services, or valuation services) or any other
> derivative works without the express written consent of Kalshi.
>
> You agree not to analyze, reverse-engineer or disassemble any Kalshi Data and not to insert any
> code or product to manipulate the Website content in any way that affects any user's experience.
> Unless Kalshi gives you prior written permission, use of any Web browsers (other than generally
> available third-party browsers), engines, scripts, software, spiders, robots, avatars, agents,
> tools or other devices or mechanisms (such as crawlers, browser plug-ins and add-ons, or other
> technology) to navigate, access, copy in bulk, retrieve, harvest, index, search or analyze any
> portion of the Website is strictly prohibited.
>
> **For the avoidance of doubt and to the fullest extent permitted by law, use of any Kalshi Data
> (including associated metadata) in any manner for any machine learning and/or artificial
> intelligence, including without limitation for the purposes of training, coding, or development of
> artificial intelligence technologies, tools, or solutions or machine learning language models, or
> otherwise for the purposes of using or in connection with the use of such technologies, tools, or
> models to generate any information, material, data, derived works, content, or output is expressly
> prohibited.** (bold in original)

### III. OWNERSHIP / IV. DISCLAIMER

> [Standard IP-reservation and as-is disclaimer language; no additional access restriction beyond
> the above. Full text on file, omitted here as non-load-bearing for this ruling.]

## Comparison against the FREE_DATA_SURVEY finding this re-verifies

FREE_DATA_SURVEY/MARKET_SOURCES.md §8 (frozen before this session) quoted the archival clause
("developing any software program... or providing archived or cached data sets containing Kalshi
Data to another person or entity") and concluded PROHIBITED for capture absent written consent.

**That clause still stands, verbatim, unchanged in substance.** Additionally, this re-verification
surfaces two things the prior survey pass did not quote:

1. A **general anti-automation clause** in Part II reaching far beyond archiving — it strictly
   prohibits using "scripts, software, spiders, robots, ... agents, tools" to "navigate, access,
   copy in bulk, retrieve, harvest, index, search or analyze **any portion of the Website**" absent
   Kalshi's prior written permission. This is not limited to bulk/archival use; it reaches a single
   scripted market-search GET request.
2. A **specific, bolded AI/ML-use prohibition** added to Part II: use of Kalshi Data "in any manner
   for any machine learning and/or artificial intelligence... or otherwise for the purposes of using
   or in connection with the use of such technologies, tools, or models to generate any information,
   material, data, derived works, content, or output is expressly prohibited." This document is
   being produced by exactly such a system.

**Conclusion of this re-verification: the prohibition does not merely still stand — it is broader
and more explicit than the survey recorded, and it reaches every mechanism D033 asked this track to
build** (scripted series/event search, scripted trade/candlestick backfill, scripted order-book
polling). See `HALT_USER_REQUIRED.md` in this directory for the disposition this triggers.
