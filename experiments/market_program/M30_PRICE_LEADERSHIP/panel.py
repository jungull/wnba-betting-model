"""panel.py -- turn the odds capture tape into a tidy price panel.

ONE ROW PER (capture_time, game, market, side, book), carrying the raw American price, the
implied probability, the per-book de-vigged probability, and the LEAVE-ONE-OUT consensus of
every other book at that same instant.

WHY LEAVE-ONE-OUT MATTERS. The question this node exists to answer is whether a book that
disagrees with its peers gets dragged back to them or drags them to it. If the disagreeing
book were included in its own benchmark, an extreme book would mechanically pull the
benchmark toward itself and manufacture the appearance of leadership. Excluding it is what
makes the comparison mean anything.

PARTITION. This reads MARKET PRICES ONLY. No game outcome is read, joined, plotted or
described anywhere in this node, so the confirmation holdout is untouched -- the same
admissibility that D147 established for the spread-line dispersion term. There is nothing
here that could leak a result, because there is no result here to leak: it is a study of how
prices move relative to each other, not of whether they were right.
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", "exploration", "_screen_kit"))
import dataroot  # noqa: E402

TS_RE = re.compile(r"live_(\d{8}T\d{6})Z")
HIST_RE = re.compile(r"hist_(\d{4}-\d{2}-\d{2})_(\d{2})Z")


def implied(american: float) -> float:
    a = float(american)
    return (-a) / (-a + 100.0) if a < 0 else 100.0 / (a + 100.0)


@dataclass(frozen=True)
class Row:
    t: str            # capture instant, ISO-ish
    game_id: str
    commence: str
    market: str
    side: str         # outcome name, plus the point for spreads/totals
    point: float | None
    book: str
    price: float
    p_raw: float
    p_devig: float
    last_update: str


def _capture_time(path: str) -> str | None:
    b = os.path.basename(path)
    m = TS_RE.search(b)
    if m:
        s = m.group(1)
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}T{s[9:11]}:{s[11:13]}:{s[13:15]}Z"
    m = HIST_RE.search(b)
    if m:
        return f"{m.group(1)}T{m.group(2)}:00:00Z"
    return None


def load_rows(family: str = "live", limit: int | None = None,
              as_of: str | None = None) -> list[Row]:
    """family: 'live', 'hist', or 'all'. `as_of` pins the tape.

    The capture job is still running, so the tape grows under this node while it is being
    analysed -- between two stages of the same study it went from 203 captures to 231.
    Every stage therefore pins the same `as_of` and records it, so a re-run reproduces the
    published numbers instead of quietly improving on them.
    """
    root = dataroot.require("odds_capture")
    files = sorted(glob.glob(os.path.join(str(root), "**", "*.json"), recursive=True))
    if family != "all":
        files = [f for f in files if os.path.basename(f).startswith(family + "_")]
    if limit:
        files = files[-limit:]
    rows: list[Row] = []
    skipped: list[str] = []
    for path in files:
        t = _capture_time(path)
        try:
            with open(path, encoding="utf-8") as fh:
                blob = json.load(fh)
        except (json.JSONDecodeError, OSError) as e:
            skipped.append(f"{os.path.basename(path)}: unreadable ({type(e).__name__})")
            continue
        # The two families are shaped differently. `live_*` is a bare list of games; `hist_*`
        # wraps the same list in {timestamp, previous_timestamp, next_timestamp, data} and
        # carries its capture instant INSIDE the file rather than in the filename. An earlier
        # version of this loader tested `isinstance(blob, list)` and silently dropped all 292
        # hist files, which is the same silent-absence failure as D138, D151 and D155 -- so
        # anything this function cannot parse is now COLLECTED AND REPORTED, never dropped.
        if isinstance(blob, dict):
            t = blob.get("timestamp") or t
            games = blob.get("data")
        else:
            games = blob
        if t is None:
            skipped.append(f"{os.path.basename(path)}: no capture timestamp")
            continue
        if not isinstance(games, list):
            skipped.append(f"{os.path.basename(path)}: no game list "
                           f"(top-level {type(blob).__name__})")
            continue
        for g in games:
            gid = g.get("id")
            commence = g.get("commence_time", "")
            if not gid:
                continue
            for bk in g.get("bookmakers", []) or []:
                book = bk.get("key", "")
                for mk in bk.get("markets", []) or []:
                    mkey = mk.get("key", "")
                    outs = mk.get("outcomes", []) or []
                    if len(outs) != 2:
                        continue        # a two-sided market is what de-vigging assumes
                    lu = mk.get("last_update") or bk.get("last_update") or ""
                    ps = [implied(o["price"]) for o in outs if o.get("price") is not None]
                    if len(ps) != 2 or min(ps) <= 0:
                        continue
                    booksum = sum(ps)
                    for o, p in zip(outs, ps):
                        pt = o.get("point")
                        side = o.get("name", "")
                        if pt is not None:
                            side = f"{side}@{pt:g}"
                        rows.append(Row(t, gid, commence, mkey, side, pt, book,
                                        float(o["price"]), p, p / booksum, lu))
    if as_of:
        rows = [r for r in rows if r.t <= as_of]
    if skipped:
        print(f"panel: SKIPPED {len(skipped)} of {len(files)} capture files -- listed so an "
              f"empty result can never be mistaken for an absent phenomenon:")
        for s_ in skipped[:10]:
            print("   ", s_)
        if len(skipped) > 10:
            print(f"    ... and {len(skipped) - 10} more")
    return rows


def keyed(rows):
    """(game, market, side) -> {capture_time -> {book -> Row}}"""
    out = defaultdict(lambda: defaultdict(dict))
    for r in rows:
        out[(r.game_id, r.market, r.side)][r.t][r.book] = r
    return out


def consensus_excluding(books: dict, drop: str) -> float | None:
    """Median de-vigged probability across every book EXCEPT `drop`."""
    vals = sorted(r.p_devig for b, r in books.items() if b != drop)
    n = len(vals)
    if n < 3:            # two peers cannot outvote a disagreement in any meaningful sense
        return None
    mid = n // 2
    return vals[mid] if n % 2 else (vals[mid - 1] + vals[mid]) / 2.0


if __name__ == "__main__":
    fam = sys.argv[1] if len(sys.argv) > 1 else "live"
    rows = load_rows(fam)
    if not rows:
        raise SystemExit(f"family={fam}: NO ROWS. That is a loader failure, not a finding.")
    print(f"family={fam}  rows={len(rows):,}")
    k = keyed(rows)
    print(f"series (game,market,side) = {len(k):,}")
    caps = sorted({r.t for r in rows})
    print(f"captures = {len(caps)}  {caps[0]} -> {caps[-1]}")
    books = sorted({r.book for r in rows})
    print(f"books = {len(books)}: {', '.join(books)}")
