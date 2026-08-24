# -*- coding: utf-8 -*-
"""Capture projected WNBA starting lineups, point-in-time.

WHY THIS EXISTS, AND WHAT IT IS NOT. D196 showed that knowing the starting five improves minutes
forecasting by 2.10% walk-forward. D198 then found the input that result used -- a CONFIRMED
lineup -- does not exist before tip for the WNBA, because the league does not require lineups to
be submitted. What DOES exist is a PROJECTION, published 24-30 hours out and revised through
gameday. So this captures a projection and must never be described as a confirmation.

WHERE THE VALUE IS, MEASURED. Our own promotion history already projects the replacement starter
at 75.8% where that player has been absent before on this team this season -- 58% of cases. On
the other 42%, a first-time absence, we fall to 18.5%. A third-party projection is worth having
for the SECOND group, and any evaluation of this feed must be scored on that split or it will
look good merely by agreeing with us where we were already right.

THE POINT-IN-TIME DISCIPLINE IS THE WHOLE POINT. Every row carries `retrieval_ts_utc` -- when WE
held it -- alongside the lineup status, and the file is APPEND-ONLY. A revised lineup arrives as
a new row rather than overwriting an old one, which is what lets a later analysis ask "what did
we know at 6pm?" and get an honest answer. Overwriting would silently convert hindsight into
foresight, which is the exact failure the programme's cutoff machinery exists to prevent.

ACCESS. `robots.txt` permits `/wnba/lineups.php` for a generic user-agent; it disallows account,
forum and update paths and blocks aggressive offline-copier agents. This requests ONE public page
per run, identifies itself honestly rather than impersonating a browser, and does not
authenticate, bypass a paywall, or touch a disallowed path. Personal research use, authorised by
the operator.
"""
from __future__ import annotations

import csv
import datetime as dt
import glob
import gzip
import hashlib
import os
import re
import sys

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTDIR = os.path.join(ROOT, "data", "lineup_capture")
OUT = os.path.join(OUTDIR, "lineups.csv")
RAWDIR = os.path.join(OUTDIR, "raw")
LOG = os.path.join(OUTDIR, "capture_log.csv")
URL = "https://www.rotowire.com/wnba/lineups.php"
UA = "wnba-research/1.0 (personal research project)"

COLUMNS = ["retrieval_ts_utc", "game_date_et", "tip_time_et", "away_abbr", "home_abbr",
           "side", "lineup_status", "section", "slot", "position", "player_name", "play_likelihood",
           "injury_tag"]

GAME_RE = re.compile(r'<div class="lineup is-nba">(.*?)(?=<div class="lineup is-nba">|<footer)', re.S)
TIME_RE = re.compile(r'lineup__time">([^<]+)<')
ABBR_RE = re.compile(r'lineup__abbr">([A-Z]{2,4})<')
LIST_RE = re.compile(r'lineup__list is-(visit|home)">(.*?)</ul>', re.S)
STATUS_RE = re.compile(r'lineup__status is-(\w+)"[^>]*>.*?</div>\s*([^<]+)<', re.S)
#: Two things an earlier version got wrong, both of which SILENTLY DROPPED ROWS:
#:   * the pct class can be followed by more classes -- `is-pct-play-50 has-injury-status`;
#:   * the position div can carry attributes -- `<div class="lineup__pos" style="width:15px;">`.
#: Between them they discarded precisely the injury-flagged players, who are the entire
#: reason to capture this page. Both are now tolerated, and `lineup__inj` (GTD / OUT) is kept.
PLAYER_RE = re.compile(
    r'lineup__player is-pct-play-(\d+)[^"]*"[^>]*>\s*<div class="lineup__pos"[^>]*>([^<]*)</div>'
    r'\s*<a title="([^"]+)"[^>]*>.*?</a>\s*(?:<span class="lineup__inj">([^<]*)</span>)?', re.S)
#: Each side's list is divided by headings -- the five expected starters, then `MAY NOT PLAY`.
#: The second group carries OUT and GTD designations, which is the input the redistribution
#: model cannot run without (M39 s02: half of all `Out` news breaks inside 90 minutes of tip).
SECTION_RE = re.compile(r'<li class="lineup__title[^"]*">([^<]*)</li>')


def parse(html, stamp):
    rows = []
    for block in GAME_RE.findall(html):
        tip = (TIME_RE.search(block).group(1).strip() if TIME_RE.search(block) else "")
        abbrs = ABBR_RE.findall(block)
        away, home = (abbrs + ["", ""])[:2]
        for side, ul in LIST_RE.findall(block):
            st = STATUS_RE.search(ul)
            status = (st.group(2).strip() if st else "unknown")
            # split on the headings: segment 0 is the expected five, later ones are
            # named by their heading (`MAY NOT PLAY`). Numbering restarts per segment,
            # so `slot` stays meaningful as a starter position rather than a row counter.
            parts = SECTION_RE.split(ul)
            segments = [("STARTERS", parts[0])]
            segments += [(parts[i].strip().upper(), parts[i + 1])
                         for i in range(1, len(parts) - 1, 2)]
            got = 0
            for section, seg in segments:
                found = PLAYER_RE.findall(seg)
                got += len(found)
                for slot, (pct, pos, name, inj) in enumerate(found, start=1):
                    rows.append({
                        "retrieval_ts_utc": stamp, "game_date_et": "", "tip_time_et": tip,
                        "away_abbr": away, "home_abbr": home,
                        "side": "away" if side == "visit" else "home",
                        "lineup_status": status, "section": section, "slot": slot,
                        "position": pos.strip(), "player_name": name.strip(),
                        "play_likelihood": pct, "injury_tag": (inj or "").strip()})
            listed = ul.count("lineup__player")
            if got != listed:   # a parser that drops rows must say so, not shrug
                print("  WARNING: %s/%s %s parsed %d of %d player entries"
                      % (away, home, side, got, listed))
    return rows


def content_hash(rows):
    """Fingerprint of WHAT WAS SAID, ignoring when we heard it."""
    body = [tuple(str(r[c]) for c in COLUMNS if c != "retrieval_ts_utc") for r in rows]
    return hashlib.sha256(repr(sorted(body)).encode("utf-8")).hexdigest()[:16]


def last_hash():
    if not os.path.exists(LOG):
        return None
    with open(LOG, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return rows[-1]["content_sha"] if rows else None


def log_tick(stamp, digest, changed, n):
    new = not os.path.exists(LOG)
    with open(LOG, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["retrieval_ts_utc", "content_sha",
                                          "changed", "n_rows"])
        if new:
            w.writeheader()
        w.writerow({"retrieval_ts_utc": stamp, "content_sha": digest,
                    "changed": int(changed), "n_rows": n})


def raw_pages():
    """Every retained page, gzipped or not -- early captures predate compression."""
    return (glob.glob(os.path.join(RAWDIR, "lineups_*.html"))
            + glob.glob(os.path.join(RAWDIR, "lineups_*.html.gz")))


def write(rows, mode):
    """Append rows, but REFUSE to append under a header that no longer matches.

    The first version of this file had 11 columns; widening it to 13 appended wider rows
    beneath the old header and produced a table pandas could not read at all. A ragged tape
    is worse than a missing one, so a schema change now fails loudly and points at --reparse.
    """
    if mode == "a" and os.path.exists(OUT):
        with open(OUT, encoding="utf-8") as f:
            head = f.readline().strip().split(",")
        if head != COLUMNS:
            print("HEADER MISMATCH: the file on disk has %d columns, this parser writes %d.\n"
                  "  Refusing to append ragged rows. Rebuild from the retained raw pages:\n"
                  "    python ops/lineup_capture.py --reparse" % (len(head), len(COLUMNS)))
            sys.exit(1)
    new = mode == "w" or not os.path.exists(OUT)
    with open(OUT, mode, encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        if new:
            w.writeheader()
        w.writerows(rows)


def reparse():
    """Rebuild the table from every raw page ever captured.

    This is safe precisely BECAUSE the raw HTML is kept: the observations are the pages, and
    the CSV is a derived parse of them. Rebuilding a derived view from retained sources is not
    a rewrite of history -- it is what makes a parser fix recoverable instead of a permanent
    hole. Timestamps come from the filenames, so they are second-precision here where a live
    capture records microseconds.
    """
    rows, seen = [], set()
    for f in sorted(raw_pages()):
        m = re.search(r"lineups_(\d{8}T\d{6})Z\.html", os.path.basename(f))
        if not m:
            continue
        t = dt.datetime.strptime(m.group(1), "%Y%m%dT%H%M%S")
        stamp = t.strftime("%Y-%m-%dT%H:%M:%S.000000Z")
        op = gzip.open if f.endswith(".gz") else open
        with op(f, "rt", encoding="utf-8") as fh:
            got = parse(fh.read(), stamp)
        # Same invariant the live gate enforces: one row-set per DISTINCT state. Pages
        # captured before the gate existed are all identical, and replaying them
        # verbatim would reintroduce exactly the duplication the gate prevents.
        d = content_hash(got)
        if d in seen:
            print("  %s -> unchanged (%s), skipped" % (os.path.basename(f), d))
            continue
        seen.add(d)
        print("  %s -> %d rows (%s)" % (os.path.basename(f), len(got), d))
        rows += got
    if not rows:
        print("no raw pages parsed; refusing to write an empty table")
        sys.exit(1)
    write(rows, "w")
    print("rebuilt %s from %d raw pages: %d rows" % (OUT, len(raw_pages()), len(rows)))


def main():
    os.makedirs(RAWDIR, exist_ok=True)
    if "--reparse" in sys.argv:
        return reparse()
    now = dt.datetime.now(dt.timezone.utc)
    stamp = now.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    try:
        r = requests.get(URL, headers={"User-Agent": UA}, timeout=45)
    except requests.RequestException as e:
        print("fetch failed: %s" % e)
        sys.exit(1)
    if r.status_code != 200:
        print("HTTP %d -- nothing captured" % r.status_code)
        sys.exit(1)

    # The raw page is kept ONLY when the content changed -- see the hash gate below.
    # It is what made both parser fixes recoverable, so it is not optional; it is
    # merely deduplicated. Gzipped (~5x) and gitignored: at ~65KB a page and 96 ticks
    # a day, storing every tick would add gigabytes a season for no extra information.
    rows = parse(r.text, stamp)
    if not rows:
        # a silent zero is how a broken parser masquerades as an empty slate
        print("PARSED ZERO ROWS from %d bytes -- the page structure has probably changed. "
              "The raw page was kept; fix the parser against it." % len(r.text))
        sys.exit(1)

    # ---- only RECORD A CHANGE -------------------------------------------------
    # At a 15-minute cadence most ticks see the identical lineup, and appending it
    # again would bloat the table without adding an observation. The hash is over the
    # PARSED CONTENT, not the HTML: the page carries rotating ads and timestamps, so
    # hashing the bytes would call every tick a change and defeat the purpose.
    # Unchanged ticks still get a `capture_log` row -- "we looked and it was the same"
    # is itself a point-in-time fact, and without it a gap in the tape would be
    # ambiguous between a stable lineup and a capture outage.
    digest = content_hash(rows)
    prev = last_hash()
    changed = digest != prev
    if changed:
        with gzip.open(os.path.join(RAWDIR, "lineups_%s.html.gz"
                                    % now.strftime("%Y%m%dT%H%M%SZ")),
                       "wt", encoding="utf-8") as f:
            f.write(r.text)
        write(rows, "a")
    log_tick(stamp, digest, changed, len(rows))

    games = len({(x["away_abbr"], x["home_abbr"]) for x in rows})
    conf = sum(1 for x in rows if "confirm" in x["lineup_status"].lower())
    print("captured %d player-slots over %d games at %s" % (len(rows), games, stamp))
    print("  lineup status: %s" % {s: sum(1 for x in rows if x["lineup_status"] == s)
                                   for s in {x["lineup_status"] for x in rows}})
    print("  rows on a CONFIRMED lineup: %d (the rest are projections)" % conf)
    print("  content %s (%s)" % ("CHANGED -- appended" if changed else
                                   "unchanged -- logged, not appended", digest))
    print("  -> %s" % OUT)


if __name__ == "__main__":
    main()
