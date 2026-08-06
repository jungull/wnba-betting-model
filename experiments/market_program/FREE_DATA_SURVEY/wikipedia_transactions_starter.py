"""
wikipedia_transactions_starter.py

STARTER / DOCUMENTATION-VERIFICATION SCRIPT ONLY.
Part of the D028 free-data mandate, market_intelligence lane, market-adjacent lens.
See FREE_DATA_SURVEY/MARKET_SOURCES.md section 5 for the full capture design, legality
classification, schema mapping, and amendment-4 discipline this script exists to support.

WHAT THIS DOES
    Makes AT MOST ONE unauthenticated GET request against the MediaWiki Action API
    (en.wikipedia.org/w/api.php) for a single WNBA season-transactions page, and prints
    the parsed structure (revision id/timestamp + a preview of the wikitext) so a human
    can inspect what the source actually looks like.

WHAT THIS DOES NOT DO
    - It does not write to any database, table, or file. print() only.
    - It is not scheduled, looped, or wired into any cron/orchestrator.
    - It does not resolve player_id / team_id against the O14 entity-resolution map.
    - It does not require, read, or accept any API key or credential (none needed for
      this endpoint at this volume).
    - It must not be pointed at more than a handful of pages in a single manual run
      without re-reading Wikimedia's rate-limit etiquette
      (https://www.mediawiki.org/wiki/Wikimedia_APIs/Rate_limits) — this script does
      not implement a scheduler or backoff loop by design, so it cannot be told to.

Running this file executes the one documented call described in MARKET_SOURCES.md section
5.3. It is not run automatically by anything in this repository.
"""

import hashlib
import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone

API_URL = "https://en.wikipedia.org/w/api.php"

# A descriptive User-Agent is Wikimedia API etiquette, not a legal requirement at this
# volume, but it costs nothing and is the polite/compliant thing to send.
USER_AGENT = (
    "wnba-betting-model-market-research/0.1 "
    "(free-data-survey documentation check; no scheduled use)"
)

# One page, chosen because 2026 is the season in scope for this program per M00 context.
SEASON_PAGE_TITLE = "List_of_2026_WNBA_season_transactions"


def fetch_transactions_page(title: str) -> dict:
    """
    Single GET against the MediaWiki Action API for one page's latest revision content
    plus revision id/timestamp. No key. No pagination. No retry loop.
    """
    params = {
        "action": "query",
        "titles": title,
        "prop": "revisions",
        "rvprop": "ids|timestamp|content",
        "rvslots": "main",
        "format": "json",
        "formatversion": "2",
    }
    url = f"{API_URL}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    retrieval_ts = datetime.now(timezone.utc).isoformat()
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw_body = resp.read()

    payload_hash = hashlib.sha256(raw_body).hexdigest()
    parsed = json.loads(raw_body)

    return {
        "retrieval_ts": retrieval_ts,
        "payload_hash": payload_hash,
        "parsed": parsed,
    }


def summarize(result: dict) -> None:
    """
    Print a human-readable preview only. This is the "documentation verification" output —
    it demonstrates the endpoint works and shows its real shape, nothing more.
    """
    print(f"retrieval_ts (ours, UTC): {result['retrieval_ts']}")
    print(f"payload_hash (sha256 of raw response bytes): {result['payload_hash']}")

    pages = result["parsed"].get("query", {}).get("pages", [])
    if not pages:
        print("No page data returned — title may not exist or API shape changed.")
        return

    page = pages[0]
    print(f"page title: {page.get('title')}")
    print(f"pageid: {page.get('pageid')}")

    revisions = page.get("revisions", [])
    if not revisions:
        print("No revisions in response.")
        return

    rev = revisions[0]
    print(f"wiki_revision_id: {rev.get('revid')}")
    print(f"wiki_revision_ts (Wikipedia-recorded, UTC): {rev.get('timestamp')}")
    print(
        "  ^ this is when an editor last touched the page, NOT when any transaction "
        "happened. Never conflate the two — see MARKET_SOURCES.md section 5.6."
    )

    content = rev.get("slots", {}).get("main", {}).get("content", "")
    print(f"wikitext length: {len(content)} chars")
    print("wikitext preview (first 600 chars):")
    print(content[:600])
    print(
        "\nNOTE: parsing the wikitext table into structured rows (date, player, team, "
        "transaction type) is deliberately NOT implemented in this starter script — "
        "that is capture-implementation work gated on a coordinator ruling per the "
        "mandate's 'design only until then' discipline, not a documentation check."
    )


if __name__ == "__main__":
    print(
        "This script makes ONE live GET request to en.wikipedia.org/w/api.php. "
        "It is a documentation-verification call, not a scheduled capture run.\n"
    )
    result = fetch_transactions_page(SEASON_PAGE_TITLE)
    summarize(result)
