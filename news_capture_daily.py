#!/usr/bin/env python3
"""
Daily WNBA news-text capture (W1: News -> Availability Engine, raw layer).

Pulls every VERIFIED-FETCHABLE feed in SOURCES (see
project_docs/NEWS_SOURCES.md for the verification evidence), politely:
honest UA, ~1.5s between requests, per-source try/except so one dead feed
never kills the run.

Every fetch ALWAYS saves the raw payload first:
    data/news_capture/raw/<yyyy-mm-dd UTC>/<source_slug>_<HHMMSS>.<xml|html|json>
then appends parsed items to data/news_capture/news_items.csv:
    capture_utc, source, published_utc, title, url, summary_text,
    teams_mentioned, players_mentioned_raw
* summary_text     : plain text, tags stripped, capped at 1500 chars
* teams_mentioned  : semicolon list matched against the 15 canonical team
                     names + common short names (word-boundary, capitalized)
* players_mentioned_raw : always empty for now - the LLM extraction layer
                     (W1 phase 2) owns player identification.

Dedupe on (source, url) against the existing CSV, so twice-plus-daily runs
never double-log an item. NO LLM calls here - this is the capture skeleton;
every day uncaptured is training data lost, so this runs even though the
extraction layer does not exist yet.

Exit 0 if at least one source succeeded; nonzero only if ALL sources failed.
Dependencies: requests. Stdlib otherwise (no feedparser on purpose).
"""

import csv
import html as htmllib
import json
import re
import sys
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import quote

import requests

ROOT = Path(__file__).resolve().parent
OUTDIR = ROOT / "data" / "news_capture"
RAWROOT = OUTDIR / "raw"
LOGCSV = OUTDIR / "news_items.csv"
CSV_HEADER = ["capture_utc", "source", "published_utc", "title", "url",
              "summary_text", "teams_mentioned", "players_mentioned_raw"]

UA = {"User-Agent": ("wnba-betting-model-news/0.1 "
                     "(personal research bot; polite; 2-4 pulls/day)"),
      "Accept": "*/*"}
TIMEOUT = 25
SLEEP_BETWEEN = 1.5          # seconds between source fetches
SUMMARY_CAP = 1500           # chars of summary_text kept per item

# ------------------------------------------------------------------ teams --
CANON_TEAMS = [
    "Atlanta Dream", "Chicago Sky", "Connecticut Sun", "Dallas Wings",
    "Golden State Valkyries", "Indiana Fever", "Las Vegas Aces",
    "Los Angeles Sparks", "Minnesota Lynx", "New York Liberty",
    "Phoenix Mercury", "Portland Fire", "Seattle Storm", "Toronto Tempo",
    "Washington Mystics",
]
# extra spellings that should also count as a mention (beyond full name +
# standalone capitalized nickname, which are generated automatically)
_EXTRA_ALIASES = {
    "Los Angeles Sparks": [r"LA Sparks", r"L\.A\. Sparks"],
    "Golden State Valkyries": [r"Golden State"],
    "Connecticut Sun": [r"CT Sun"],
}
TEAM_PATTERNS = []
for _t in CANON_TEAMS:
    _nick = _t.rsplit(" ", 1)[-1]
    _alts = [re.escape(_t), re.escape(_nick)] + _EXTRA_ALIASES.get(_t, [])
    # case-sensitive on purpose: "Storm"/"Sky"/"Fire" as common nouns are
    # lowercase; the capitalized word inside WNBA-scoped feeds is the team.
    TEAM_PATTERNS.append((_t, re.compile(r"\b(?:%s)\b" % "|".join(_alts))))

# ---------------------------------------------------------------- sources --
# kind: "rss"       generic RSS/Atom XML          (raw saved as .xml)
#       "espn_json" ESPN site API news JSON       (raw saved as .json)
#       "ap_html"   apnews.com hub page, regex     (raw saved as .html)
#       "wnba_html" wnba.com/news embedded JSON    (raw saved as .html)
# Verified 2026-07-30 (see project_docs/NEWS_SOURCES.md). To disable a
# source, comment it out; to add one, append a dict.
SOURCES = [
    {"slug": "espn_rss", "kind": "rss",
     "url": "https://www.espn.com/espn/rss/wnba/news",
     "note": "ESPN W basketball headlines"},
    {"slug": "espn_api", "kind": "espn_json",
     "url": ("https://site.api.espn.com/apis/site/v2/sports/basketball/"
             "wnba/news?limit=50"),
     "note": "ESPN news JSON - richer than the RSS, same host as the "
             "injury-capture fallback"},
    {"slug": "ap_wnba", "kind": "ap_html",
     "url": "https://apnews.com/hub/wnba",
     "note": "AP WNBA wire - no RSS exists; hub HTML is server-rendered"},
    {"slug": "theix_wnba", "kind": "rss",
     "url": "https://www.theixsports.com/category/wnba/feed/",
     "note": "The Next / The IX Basketball, WNBA-only category feed"},
    {"slug": "winsidr", "kind": "rss",
     "url": "https://winsidr.com/feed/",
     "note": "Winsidr - features/rotations, slower cadence"},
    {"slug": "herhoopstats", "kind": "rss",
     "url": "https://herhoopstats.substack.com/feed",
     "note": "Her Hoop Stats Substack newsletter"},
    {"slug": "wnba_official", "kind": "wnba_html",
     "url": "https://www.wnba.com/news",
     "note": "League editorial - transactions/announcements"},
    {"slug": "cbs_wnba", "kind": "rss",
     "url": "https://www.cbssports.com/rss/headlines/wnba/",
     "note": "CBS Sports WNBA headlines"},
    {"slug": "yahoo_wnba", "kind": "rss",
     "url": "https://sports.yahoo.com/wnba/rss.xml",
     "note": "Yahoo Sports WNBA - high volume, syndicates AP too"},
    {"slug": "swishappeal", "kind": "rss",
     "url": "https://www.swishappeal.com/rss/index.xml",
     "note": "SB Nation Swish Appeal"},
]

# Google News RSS catch-all: one per-team injury query + one league-wide.
# This is what covers beat reporters, local papers, and the JS-only team
# sites (team-site posts are indexed by Google News).
def _gnews(q):
    return ("https://news.google.com/rss/search?q=" + quote(q) +
            "&hl=en-US&gl=US&ceid=US:en")

for _t in CANON_TEAMS:
    SOURCES.append({
        "slug": "gnews_" + _t.rsplit(" ", 1)[-1].lower(),
        "kind": "rss",
        "url": _gnews('"%s" (injury OR injured OR "ruled out" OR '
                      'questionable OR doubtful OR waived OR signed) '
                      'when:3d' % _t),
        "note": "Google News catch-all: " + _t})
SOURCES.append({
    "slug": "gnews_league", "kind": "rss",
    "url": _gnews('WNBA (injury OR "ruled out" OR questionable OR doubtful '
                  'OR "out indefinitely" OR waived) when:2d'),
    "note": "Google News catch-all: league-wide availability terms"})

RAW_EXT = {"rss": "xml", "espn_json": "json", "ap_html": "html",
           "wnba_html": "html"}


# ------------------------------------------------------------- utilities --
def strip_tags(s):
    """HTML/XML fragment -> collapsed plain text."""
    if not s:
        return ""
    s = htmllib.unescape(htmllib.unescape(s))
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", s).strip()[:SUMMARY_CAP]


def to_utc_iso(s):
    """Best-effort date string -> '2026-07-30T15:49:50Z' (else '')."""
    if not s:
        return ""
    s = str(s).strip()
    dt = None
    if re.fullmatch(r"\d{12,13}", s):                     # epoch millis
        dt = datetime.fromtimestamp(int(s) / 1000, tz=timezone.utc)
    else:
        try:
            dt = parsedate_to_datetime(s)                  # RFC 822
        except Exception:
            try:
                dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            except Exception:
                return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def teams_mentioned(text):
    hits = [name for name, pat in TEAM_PATTERNS if pat.search(text)]
    return ";".join(hits)


# --------------------------------------------------------------- parsers --
def parse_rss(body):
    """RSS 2.0 / Atom bytes -> list of {title,url,published,summary}.
    Regex-based on purpose: survives the undeclared-namespace and bad-entity
    XML that real-world sports feeds ship, which xml.etree rejects."""
    text = body.decode("utf-8", "replace")
    items = re.findall(r"<item[\s>].*?</item>", text, re.S)
    if not items:
        items = re.findall(r"<entry[\s>].*?</entry>", text, re.S)
    out = []
    for it in items:
        def _f(tag, block=it):
            m = re.search(r"<%s[^>]*>(?:\s*<!\[CDATA\[)?(.*?)(?:\]\]>\s*)?"
                          r"</%s>" % (tag, tag), block, re.S)
            return m.group(1).strip() if m else ""
        title = strip_tags(_f("title"))
        link = strip_tags(_f("link"))
        if not link:                                       # Atom style
            m = re.search(r'<link[^>]+href="([^"]+)"', it)
            link = m.group(1).strip() if m else ""
        pub = _f("pubDate") or _f("published") or _f("updated") or _f("dc:date")
        summary = strip_tags(_f("description") or _f("summary") or
                             _f("content:encoded") or _f("content"))
        if title or link:
            out.append({"title": title, "url": link,
                        "published": to_utc_iso(strip_tags(pub)),
                        "summary": summary})
    return out


def parse_espn_json(body):
    j = json.loads(body.decode("utf-8", "replace"))
    out = []
    for a in j.get("articles", []):
        links = a.get("links", {}) or {}
        url = (links.get("web", {}) or {}).get("href", "") or \
              (links.get("mobile", {}) or {}).get("href", "")
        out.append({"title": strip_tags(a.get("headline", "")),
                    "url": url,
                    "published": to_utc_iso(a.get("published", "")),
                    "summary": strip_tags(a.get("description", ""))})
    return [o for o in out if o["url"] or o["title"]]


def parse_ap_html(body):
    """apnews.com hub: split on PagePromo cards; each card carries an
    article href, a headline <span>, and an epoch-ms posted timestamp."""
    text = body.decode("utf-8", "replace")
    out, seen = [], set()
    # each split piece is exactly one promo card (it runs until the next
    # card's class attribute), so the first article link in it is the card's
    for chunk in re.split(r'class="PagePromo"', text)[1:]:
        m = re.search(r'href="(https://apnews\.com/article/[^"]+)"[^>]*>'
                      r'\s*<span[^>]*>([^<]{5,200})</span>', chunk)
        if not m:
            continue
        url, title = m.group(1), strip_tags(m.group(2))
        if url in seen:
            continue
        seen.add(url)
        ts = re.search(r'data-posted-date-timestamp="(\d+)"', chunk)
        out.append({"title": title, "url": url,
                    "published": to_utc_iso(ts.group(1)) if ts else "",
                    "summary": ""})
    return out


def parse_wnba_html(body):
    """wnba.com/news: article objects live JSON-embedded in the Next.js
    payload as "title":...,"hub"...,"permalink":...,"date": triples."""
    text = body.decode("utf-8", "replace")
    out, seen = [], set()
    for m in re.finditer(r'"title":"([^"]{5,200})","hub".*?"permalink":'
                         r'"(https://www\.wnba\.com/news/[^"]+)".*?'
                         r'"date":"([^"]+)"', text, re.S):
        raw_title, url, date = m.groups()
        if url in seen:
            continue
        seen.add(url)
        try:
            title = json.loads('"%s"' % raw_title)         # JSON-unescape
        except Exception:
            title = raw_title
        out.append({"title": strip_tags(title), "url": url,
                    "published": to_utc_iso(date), "summary": ""})
    return out


PARSERS = {"rss": parse_rss, "espn_json": parse_espn_json,
           "ap_html": parse_ap_html, "wnba_html": parse_wnba_html}


# ------------------------------------------------------------------ main --
def load_seen():
    seen = set()
    if LOGCSV.exists():
        with open(LOGCSV, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                seen.add((row.get("source", ""), row.get("url", "")))
    return seen


def main():
    run_utc = datetime.now(timezone.utc)
    capture_stamp = run_utc.strftime("%Y%m%dT%H%M%SZ")
    rawdir = RAWROOT / run_utc.strftime("%Y-%m-%d")
    rawdir.mkdir(parents=True, exist_ok=True)
    OUTDIR.mkdir(parents=True, exist_ok=True)

    seen = load_seen()
    new_rows, per_source, failures = [], [], []

    for src in SOURCES:
        slug, kind, url = src["slug"], src["kind"], src["url"]
        try:
            r = requests.get(url, headers=UA, timeout=TIMEOUT)
            r.raise_for_status()
            fetch_utc = datetime.now(timezone.utc)
            rawfile = rawdir / ("%s_%s.%s" % (slug,
                                              fetch_utc.strftime("%H%M%S"),
                                              RAW_EXT[kind]))
            rawfile.write_bytes(r.content)          # raw ALWAYS saved first
            items = PARSERS[kind](r.content)
            n_new = 0
            for it in items:
                key = (slug, it["url"])
                if not it["url"] or key in seen:
                    continue
                seen.add(key)
                text_blob = "%s %s" % (it["title"], it["summary"])
                new_rows.append({
                    "capture_utc": capture_stamp,
                    "source": slug,
                    "published_utc": it["published"],
                    "title": it["title"],
                    "url": it["url"],
                    "summary_text": it["summary"],
                    "teams_mentioned": teams_mentioned(text_blob),
                    "players_mentioned_raw": "",
                })
                n_new += 1
            per_source.append((slug, len(items), n_new))
        except Exception as e:
            failures.append((slug, "%s: %s" % (type(e).__name__,
                                               str(e)[:90])))
            print("WARN %s failed - %s: %s" % (slug, type(e).__name__,
                                               str(e)[:120]), file=sys.stderr)
        time.sleep(SLEEP_BETWEEN)

    if new_rows:
        newfile = not LOGCSV.exists()
        with open(LOGCSV, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=CSV_HEADER)
            if newfile:
                w.writeheader()
            w.writerows(new_rows)

    n_sources_ok = len(per_source)
    detail = " ".join("%s:%d/%d" % (s, new, tot)
                      for s, tot, new in per_source if new) or "none-new"
    fail_txt = ",".join(s for s, _ in failures) or "none"
    print("news_capture %s | %d new items | %d/%d sources ok | new-by-source "
          "[%s] | failures: %s" % (capture_stamp, len(new_rows), n_sources_ok,
                                   len(SOURCES), detail, fail_txt))
    return 0 if n_sources_ok else 1


if __name__ == "__main__":
    sys.exit(main())
