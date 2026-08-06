"""
harvest.py — Wikipedia WNBA transactions harvest (Track B)

Authority: D028 (free-data mandate) + D029 (100K tier, irrelevant here — this uses no
paid host) + D030 (WIKIPEDIA_HARVEST_GRADUATED, orchestration/DECISION_LEDGER.jsonl,
player_program worktree, ts 2026-08-06T18:40:10Z). Design basis:
experiments/market_program/FREE_DATA_SURVEY/MARKET_SOURCES.md section 5. Contract:
experiments/market_program/M00_MARKET_PROGRAM_CONTRACT/MARKET_PROGRAM_CONTRACT.md
(sha256 1152dcd3bf74000f700844bc8bfc0df25de61a067f59534a714ac4f2f20265de, verified).

WHAT THIS DOES
    Pulls the raw wikitext (current revision) of every "List of <year> WNBA season
    transactions" page for years 2020-2026 from the MediaWiki Action API
    (en.wikipedia.org/w/api.php) and archives it VERBATIM — no parsing, no
    normalization — one JSON file per page under raw/, keyed by page + retrieval_ts +
    revision_id. Parsing into structured rows is parse.py's job, kept separate so the
    raw archive is always re-parseable without re-fetching.

ETIQUETTE / PROVENANCE DISCIPLINE
    - maxlag=5 sent on every request (backs off politely if replica lag is high).
    - 1 request/second hard floor between requests (well under the 500/hr unauth cap).
    - Descriptive User-Agent with contact info, per Wikimedia API etiquette.
    - No key, no login, no bypass of anything — plain documented GETs only.
    - Every archived row/file carries retrieval_ts (when WE fetched it, UTC ISO8601),
      wiki_revision_id and wiki_revision_ts (Wikipedia's own, editor-asserted), and a
      payload_hash (sha256 of raw response bytes) — Amendment-4 timestamp discipline:
      retrieval_ts and vendor/editor timestamp are never conflated, both always stored.
    - provenance_class fixed at "WIKIPEDIA_API_VERBATIM_ARCHIVE" for every raw file:
      this is the raw capture layer, not yet a claim about parsed correctness.

WHAT THIS DOES NOT DO
    - Does not parse wikitext tables (see parse.py).
    - Does not resolve player_id/team_id.
    - Does not write to any production/model table — output lands only under
      FREE_DATA_SURVEY/wikipedia/raw/, a survey-lane artifact directory.
    - Does not touch api.the-odds-api.com or any paid host.
"""

import argparse
import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API_URL = "https://en.wikipedia.org/w/api.php"

USER_AGENT = (
    "wnba-betting-model-market-research/1.0 "
    "(D028/D030-authorized Wikipedia transactions harvest; "
    "contact: jgallagher@sasscpas.com; purpose: free-data roster/entity-resolution "
    "ground truth, non-commercial internal research)"
)

MIN_REQUEST_INTERVAL_SEC = 1.0  # 1 rps ceiling, politeness margin beyond the 500/hr cap
MAXLAG = 5

SEASONS = list(range(2020, 2027))  # 2020-2026 inclusive

HERE = Path(__file__).resolve().parent
RAW_DIR = HERE / "raw"

_last_request_ts = 0.0


def _throttle() -> None:
    global _last_request_ts
    elapsed = time.monotonic() - _last_request_ts
    if elapsed < MIN_REQUEST_INTERVAL_SEC:
        time.sleep(MIN_REQUEST_INTERVAL_SEC - elapsed)
    _last_request_ts = time.monotonic()


def _get(params: dict, max_retries: int = 3) -> bytes:
    """One polite GET with maxlag handling. Returns raw response bytes."""
    params = dict(params)
    params.setdefault("maxlag", str(MAXLAG))
    url = f"{API_URL}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    for attempt in range(max_retries):
        _throttle()
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            if e.code == 503 and attempt < max_retries - 1:
                # maxlag backoff signal — wait and retry, per Wikimedia etiquette docs.
                retry_after = e.headers.get("Retry-After")
                wait_s = float(retry_after) if retry_after else 5.0
                time.sleep(wait_s)
                continue
            raise


def season_page_title(year: int) -> str:
    return f"List_of_{year}_WNBA_season_transactions"


def fetch_page_wikitext(title: str) -> dict:
    """
    Fetch current revision wikitext + id/timestamp for one page. Returns a dict ready
    to archive verbatim (raw parsed JSON kept in full, plus our own capture metadata).
    Returns {"found": False, ...} if the page does not exist rather than raising, so
    the harvest can continue past known-missing seasons without crashing.
    """
    params = {
        "action": "query",
        "titles": title,
        "prop": "revisions",
        "rvprop": "ids|timestamp|content|comment|size",
        "rvslots": "main",
        "format": "json",
        "formatversion": "2",
    }
    retrieval_ts = datetime.now(timezone.utc).isoformat()
    raw_body = _get(params)
    payload_hash = hashlib.sha256(raw_body).hexdigest()
    parsed = json.loads(raw_body)

    record = {
        "provenance_class": "WIKIPEDIA_API_VERBATIM_ARCHIVE",
        "vendor_ts_semantics": "WIKIPEDIA_EDITOR_ASSERTED",
        "retrieval_ts": retrieval_ts,
        "payload_hash_sha256": payload_hash,
        "api_url_no_key": API_URL,
        "title_requested": title,
        "found": False,
    }

    pages = parsed.get("query", {}).get("pages", [])
    if not pages:
        record["raw_response"] = parsed
        return record

    page = pages[0]
    if page.get("missing"):
        record["found"] = False
        record["pageid"] = None
        record["raw_response"] = parsed
        return record

    revisions = page.get("revisions", [])
    if not revisions:
        record["found"] = False
        record["raw_response"] = parsed
        return record

    rev = revisions[0]
    content = rev.get("slots", {}).get("main", {}).get("content", "")

    record.update(
        {
            "found": True,
            "pageid": page.get("pageid"),
            "page_title": page.get("title"),
            "wiki_revision_id": rev.get("revid"),
            "wiki_parent_revision_id": rev.get("parentid"),
            "wiki_revision_ts": rev.get("timestamp"),
            "wiki_revision_comment": rev.get("comment"),
            "wiki_revision_size_bytes": rev.get("size"),
            "wikitext_raw": content,
            "wikitext_length_chars": len(content),
        }
    )
    return record


def archive_season(year: int, out_dir: Path = RAW_DIR) -> dict:
    title = season_page_title(year)
    record = fetch_page_wikitext(title)
    record["season"] = year

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{year}_{title}.json"
    out_path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")

    return {
        "season": year,
        "title": title,
        "found": record["found"],
        "wiki_revision_id": record.get("wiki_revision_id"),
        "wikitext_length_chars": record.get("wikitext_length_chars"),
        "out_path": str(out_path),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--seasons",
        type=int,
        nargs="*",
        default=SEASONS,
        help="Season years to harvest (default: 2020-2026 inclusive).",
    )
    ap.add_argument("--out-dir", type=Path, default=RAW_DIR)
    args = ap.parse_args()

    print(f"Wikipedia transactions harvest — {len(args.seasons)} season page(s), "
          f"1 rps, maxlag={MAXLAG}, keyless, User-Agent set.\n")

    results = []
    for year in args.seasons:
        r = archive_season(year, args.out_dir)
        status = "OK" if r["found"] else "NOT FOUND"
        print(f"  {year}: {status}  rev={r['wiki_revision_id']}  "
              f"chars={r['wikitext_length_chars']}  -> {r['out_path']}")
        results.append(r)

    found = sum(1 for r in results if r["found"])
    print(f"\nDone. {found}/{len(results)} season pages archived.")


if __name__ == "__main__":
    main()
