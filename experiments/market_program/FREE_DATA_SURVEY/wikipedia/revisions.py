"""
revisions.py — capture full REVISION HISTORY for each WNBA season-transactions page.

Authority: same as harvest.py (D028 + D030). Design basis: MARKET_SOURCES.md section 5,
"WIKIPEDIA_REVISION_TS" concept.

WHAT THIS DOES
    For each season page, walks the MediaWiki Action API's revision-history listing
    (prop=revisions, rvlimit, paginated via rvcontinue) and archives every revision's
    (revision_id, timestamp, size, comment, user-or-anon-flag) as the coarse
    public-knowledge timeline for that page. One JSONL file per season under
    revisions/.

MANDATORY CAVEAT — READ BEFORE USING THIS DATA FOR ANY LATENCY/TIMING CLAIM
    WIKIPEDIA_REVISION_TS bounds public knowledge from ABOVE ONLY. A revision at time T
    proves the fact stated in that edit was known to at least one editor by T — it says
    NOTHING about when the fact first became true, or became knowable, or was first
    reported anywhere else. Absence of an earlier revision does not mean the fact wasn't
    already public; it may simply mean no editor had gotten to it yet. This label is
    carried on every row in this dataset (see WIKIPEDIA_REVISION_TS_CAVEAT constant) and
    must never be dropped or paraphrased away by downstream consumers.

    This file is explicitly NOT a substitute for, or input to, any F1/F2/reaction-time
    claim — same standing prohibition as the parsed-transactions table in parse.py.

WHAT THIS DOES NOT DO
    - Does not fetch full wikitext content per revision (that would be one GET per
      revision — expensive and unnecessary; only ids/timestamps/size/comment/user-flag
      are pulled, which is available in the same paginated listing call).
    - Does not attempt to reconstruct diffs.
"""

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from harvest import API_URL, USER_AGENT, MAXLAG, SEASONS, season_page_title, _throttle

HERE = Path(__file__).resolve().parent
REV_DIR = HERE / "revisions"

WIKIPEDIA_REVISION_TS_CAVEAT = (
    "WIKIPEDIA_REVISION_TS bounds public knowledge from ABOVE ONLY: a revision at time T "
    "proves the edited fact was known to at least one editor by T. It never establishes "
    "when the underlying transaction happened or when it first became publicly knowable. "
    "Never use this field alone as a reaction-time, latency, or 'first known' claim."
)

RVLIMIT = 50  # per MediaWiki docs, max 50 for non-bot-flagged unauthenticated queries


def _get(params: dict, max_retries: int = 3) -> bytes:
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
                retry_after = e.headers.get("Retry-After")
                time.sleep(float(retry_after) if retry_after else 5.0)
                continue
            raise


def fetch_revision_history(title: str):
    """
    Paginated walk of a page's full revision history, oldest-first is not
    guaranteed by the API default (it returns newest-first); we record whatever
    order the API gives and let consumers sort by timestamp if they need order.
    Returns (found: bool, revisions: list[dict], pages_fetched: int).
    """
    revisions = []
    rvcontinue = None
    pages_fetched = 0
    found = None

    while True:
        params = {
            "action": "query",
            "titles": title,
            "prop": "revisions",
            "rvprop": "ids|timestamp|size|comment|user|flags",
            "rvlimit": str(RVLIMIT),
            "format": "json",
            "formatversion": "2",
        }
        if rvcontinue:
            params["rvcontinue"] = rvcontinue

        raw_body = _get(params)
        pages_fetched += 1
        parsed = json.loads(raw_body)

        pages = parsed.get("query", {}).get("pages", [])
        if not pages:
            found = False
            break
        page = pages[0]
        if page.get("missing"):
            found = False
            break
        found = True

        for rev in page.get("revisions", []):
            revisions.append({
                "wiki_revision_id": rev.get("revid"),
                "wiki_parent_revision_id": rev.get("parentid"),
                "wiki_revision_ts": rev.get("timestamp"),
                "wiki_revision_ts_label": "WIKIPEDIA_REVISION_TS",
                "wiki_revision_ts_caveat": WIKIPEDIA_REVISION_TS_CAVEAT,
                "size_bytes": rev.get("size"),
                "comment": rev.get("comment"),
                "user_or_anon": rev.get("user"),
                "is_minor_edit": rev.get("minor", False),
            })

        cont = parsed.get("continue", {})
        rvcontinue = cont.get("rvcontinue")
        if not rvcontinue:
            break

    return found, revisions, pages_fetched


def compute_size_deltas(revisions: list) -> list:
    """Revisions come back newest-first from the API; size delta = this revision's
    size minus its parent's size where the parent is also present in our list."""
    by_id = {r["wiki_revision_id"]: r for r in revisions}
    for r in revisions:
        parent = by_id.get(r["wiki_parent_revision_id"])
        if parent is not None and r["size_bytes"] is not None and parent["size_bytes"] is not None:
            r["size_delta_bytes"] = r["size_bytes"] - parent["size_bytes"]
        else:
            r["size_delta_bytes"] = None  # parent not in this fetch window — not guessed
    return revisions


def archive_season_revisions(year: int, out_dir: Path = REV_DIR) -> dict:
    title = season_page_title(year)
    retrieval_ts = datetime.now(timezone.utc).isoformat()
    found, revisions, pages_fetched = fetch_revision_history(title)
    revisions = compute_size_deltas(revisions)

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{year}_{title}_revisions.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for rev in revisions:
            row = {
                "season": year,
                "page_title": title,
                "retrieval_ts": retrieval_ts,
                "provenance_class": "WIKIPEDIA_REVISION_HISTORY",
                **rev,
            }
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    return {
        "season": year,
        "title": title,
        "found": found,
        "revision_count": len(revisions),
        "api_pages_fetched": pages_fetched,
        "out_path": str(out_path),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seasons", type=int, nargs="*", default=SEASONS)
    ap.add_argument("--out-dir", type=Path, default=REV_DIR)
    args = ap.parse_args()

    print(f"Wikipedia revision-history harvest — {len(args.seasons)} season page(s), "
          f"1 rps, maxlag={MAXLAG}, keyless.\n")
    print(f"CAVEAT (applies to every row written): {WIKIPEDIA_REVISION_TS_CAVEAT}\n")

    results = []
    for year in args.seasons:
        r = archive_season_revisions(year, args.out_dir)
        status = "OK" if r["found"] else "NOT FOUND"
        print(f"  {year}: {status}  revisions={r['revision_count']}  "
              f"api_calls={r['api_pages_fetched']}  -> {r['out_path']}")
        results.append(r)

    total_rev = sum(r["revision_count"] for r in results)
    print(f"\nDone. {total_rev} total revisions archived across {len(results)} season page(s).")


if __name__ == "__main__":
    main()
