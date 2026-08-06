#!/usr/bin/env python3
"""
Designation parser for the official WNBA quarter-hour injury-report PDF.

Owned by: experiments/market_program/INJURY_OFFICIAL/live/ (D032/D033 primary
injury track). Independent implementation, written and tested against real
production bytes in this session -- NOT copied from
injury_capture_daily.py on the live main worktree, though the two arrive at
a structurally similar coordinate-clustering approach because that is what
the PDF's actual layout requires (verified directly, not assumed): the
league's PDF generator emits one word per text-showing operation with no
reliable table/column markup, so cells must be reconstructed from (x, y)
glyph positions, not from `extract_text()` string order.

Layout facts this parser relies on (verified against four real report PDFs
in tests/fixtures/, all sourced read-only from the live production archive
at data/injury_capture/raw/ on the un-modified main worktree -- see
tests/fixtures/PROVENANCE.md):
  - A physical row is a cluster of words sharing (approximately) the same
    y-coordinate (tolerance 2.0 pt, matching observed line jitter).
  - The header row ("Game Date / Game Time / Matchup / Team / Player Name /
    Current Status / Reason") gives the x-boundaries of the seven columns
    for that page; boundaries can shift slightly page to page so they are
    re-derived per page, never assumed global.
  - Row groups repeat a game context (date/time/matchup/team) only on the
    line where it changes; blank cells inherit the last-seen value within
    the same team block. A new "Team" cell always starts a new context.
  - "NOT YET SUBMITTED" is a real, structurally meaningful report state for
    a team-game (the team has not yet filed a report for that game slot) --
    it is captured explicitly, never silently dropped, and never treated as
    equivalent to "no injuries" or "all players available".
  - Wrapped player names (long names) and wrapped reason text continue onto
    a following line with only that one column populated; such lines are
    merged into the previous data row rather than treated as new rows.

KNOWN LIMITATION (documented, not silently hidden -- verified against
tests/fixtures/reference_prod_wnba_official_20260805T230003Z.pdf): the
report generator sometimes gives the "Reason" cell of a row a y-baseline a
few points off from that row's "Player"/"Status" cells -- close enough to
read as the same table row to a human, far enough (>2.0pt) to fall into a
different row-cluster here. When that happens, and when the row is the
FIRST data row after the header (so there is no rows_out[-1] yet to merge
a stray reason-only cluster into), the reason cluster is correctly REJECTED
(reason=unplaceable_row_fragment) rather than silently dropped -- but a
wrapped reason continuation word processed in the same pass can still
attach to the wrong accumulated reason string, producing a reason field
whose WORD ORDER is not reliable (status and player_raw are unaffected).
Downstream consumers must treat `reason` as best-effort free text, never as
a field with guaranteed word order, until this is hardened further; `status`
and `player_raw` do not share this limitation.

Public entry point: parse_official_pdf(pdf_bytes) -> (rows, meta, rejects)
  rows    : list[dict] of successfully parsed player-designation rows
  meta    : dict with 'report_publication_ts_raw' (verbatim embedded header
            string, e.g. "08/06/26 03:00 PM") and per-team NOT_YET_SUBMITTED
            coverage rows (game_date, game_time_et, matchup, team)
  rejects : list[dict] of rows the parser could not confidently place,
            carrying the raw cell text and a reason code -- never silently
            dropped (D034 "unmatched/rejects/ambiguous reported")
"""
from __future__ import annotations

import io
import re
from datetime import datetime

OFFICIAL_STATUSES = {
    "Out", "Doubtful", "Questionable", "Probable", "Available",
    "Rest", "Health and Safety Protocols", "Suspension",
}

_HEADER_TOKENS = {"Game", "Date", "Time", "Matchup", "Team", "Player",
                   "Name", "Current", "Status", "Reason"}


def _classify(cells):
    """cells: [(x, text), ...] sorted by x, for one physical row."""
    joined = " ".join(t for _, t in cells)
    if ("Game" in joined and "Matchup" in joined and "Player" in joined
            and "Reason" in joined):
        return "HEADER"
    if re.search(r"Injury\s*Report\s*:", joined) or re.match(
            r"^Page\s*\d+\s*of", joined):
        return "META"
    return "ROW"


def _extract_words(page):
    """page -> [(y, x, text), ...] via pypdf's visitor_text (coordinate-
    accurate; extract_text() alone loses column position)."""
    words = []

    def visitor(text, cm, tm, font_dict, font_size):
        t = text.strip()
        if t:
            words.append((tm[5], tm[4], t))

    page.extract_text(visitor_text=visitor)
    return words


def _cluster_rows(words):
    """[(y, x, text), ...] -> [[y, [(x, text), ...]], ...], y-clustered
    with 2.0pt tolerance, x-sorted within each row."""
    rows = []
    for y, x, t in sorted(words, key=lambda w: w[0]):
        if rows and abs(rows[-1][0] - y) <= 2.0:
            rows[-1][1].append((x, t))
        else:
            rows.append([y, [(x, t)]])
    for r in rows:
        r[1].sort(key=lambda w: w[0])
    return rows


def _page_reading_order(rows, prev_ascending):
    """Determine whether this page's rows read top-to-bottom in ascending or
    descending y (PDF y-axis convention varies by generator/page); use the
    header row's position relative to the data rows to decide, falling back
    to the previous page's finding if this page has no header."""
    kinds = [_classify(r[1]) for r in rows]
    ascending = prev_ascending
    if "HEADER" in kinds:
        hy = rows[kinds.index("HEADER")][0]
        data_ys = [r[0] for r, k in zip(rows, kinds) if k == "ROW"]
        if data_ys:
            ascending = hy <= min(data_ys)
    order = range(len(rows)) if ascending else range(len(rows) - 1, -1, -1)
    return [(kinds[i], rows[i][1]) for i in order], ascending


def _column_starts(header_cells):
    xs = {}
    seen_game = 0
    for x, t in header_cells:
        if t == "Game":
            if seen_game == 0:
                xs["game_date"] = x
            else:
                xs["game_time"] = x
            seen_game += 1
        elif t == "Matchup":
            xs["matchup"] = x
        elif t == "Team":
            xs["team"] = x
        elif t == "Player":
            xs["player"] = x
        elif t == "Current":
            xs["status"] = x
        elif t == "Reason":
            xs["reason"] = x
    need = ["game_date", "game_time", "matchup", "team", "player", "status",
            "reason"]
    missing = [k for k in need if k not in xs]
    if missing:
        raise ValueError(
            f"injury PDF header changed; missing columns {missing} in "
            f"{header_cells!r}")
    return [(k, xs[k]) for k in need]


def _bucket(cells, cols):
    out = {k: [] for k, _ in cols}
    bounds = [x for _, x in cols] + [float("inf")]
    for x, t in cells:
        placed = False
        for i, (name, _) in enumerate(cols):
            if bounds[i] - 4 <= x < bounds[i + 1] - 4:
                out[name].append(t)
                placed = True
                break
        if not placed:
            out[cols[0][0]].append(t)
    return {k: " ".join(v).strip() for k, v in out.items()}


def _parse_report_publication_ts(meta_text):
    """'Injury Report: 08/06/26 03:00 PM' -> raw string + parsed ET
    datetime, or (raw, None) if the embedded stamp doesn't parse. This is
    the PROVIDER PUBLICATION timestamp class (T1, publisher-asserted) --
    distinct from the URL/document slot and from our own retrieval time."""
    m = re.search(
        r"Injury\s*Report\s*:\s*(\d{2}/\d{2}/\d{2,4})\s+(\d{1,2}:\d{2})\s*"
        r"(AM|PM)", meta_text, re.IGNORECASE)
    if not m:
        return meta_text.strip(), None
    date_s, time_s, ampm = m.groups()
    fmt_d = "%m/%d/%Y" if len(date_s) == 10 else "%m/%d/%y"
    try:
        dt = datetime.strptime(f"{date_s} {time_s} {ampm.upper()}",
                                f"{fmt_d} %I:%M %p")
    except ValueError:
        return f"{date_s} {time_s} {ampm}", None
    return f"{date_s} {time_s} {ampm}", dt


def parse_official_pdf(pdf_bytes: bytes):
    """Official injury-report PDF bytes -> (rows, meta, rejects)."""
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(pdf_bytes))

    rows_out = []
    rejects = []
    not_yet_submitted = []
    meta = {"report_publication_ts_raw": None,
            "report_publication_ts_et": None}

    ctx = {"game_date": "", "game_time": "", "matchup": "", "team": ""}
    cols = None
    ascending = True

    for page_idx, page in enumerate(reader.pages):
        words = _extract_words(page)
        if not words:
            continue
        row_clusters = _cluster_rows(words)
        page_rows, ascending = _page_reading_order(row_clusters, ascending)

        for kind, cells in page_rows:
            joined = " ".join(t for _, t in cells)
            if kind == "HEADER":
                try:
                    cols = _column_starts(cells)
                except ValueError as e:
                    rejects.append({"page": page_idx, "kind": "HEADER",
                                     "raw": joined, "reason": str(e)})
                continue
            if kind == "META":
                raw, dt = _parse_report_publication_ts(joined)
                if dt is not None:
                    meta["report_publication_ts_raw"] = raw
                    meta["report_publication_ts_et"] = dt.isoformat()
                continue
            if cols is None:
                if joined:
                    rejects.append({"page": page_idx, "kind": "ROW",
                                     "raw": joined,
                                     "reason": "row_before_header"})
                continue
            if not joined:
                continue

            cell = _bucket(cells, cols)
            if cell["game_date"]:
                ctx["game_date"] = cell["game_date"]
                ctx["team"] = ""
            if cell["game_time"]:
                ctx["game_time"] = cell["game_time"]
                ctx["team"] = ""
            if cell["matchup"]:
                ctx["matchup"] = cell["matchup"]
                ctx["team"] = ""
            if cell["team"]:
                ctx["team"] = cell["team"]

            if "NOT YET SUBMITTED" in joined.upper():
                not_yet_submitted.append({
                    "game_date": ctx["game_date"],
                    "game_time_et": ctx["game_time"],
                    "matchup": ctx["matchup"],
                    "team_raw": ctx["team"],
                })
                continue

            player, status, reason = (cell["player"], cell["status"],
                                       cell["reason"])
            if player and status:
                player = re.sub(r"-\s+", "-", player)
                if "," in player:
                    last, first = player.split(",", 1)
                    player = f"{first.strip()} {last.strip()}"
                gd = ctx["game_date"]
                if re.match(r"^\d{2}/\d{2}/\d{4}$", gd):
                    gd = datetime.strptime(gd, "%m/%d/%Y").strftime(
                        "%Y-%m-%d")
                row = {
                    "game_date": gd,
                    "game_time_et": ctx["game_time"],
                    "matchup": ctx["matchup"],
                    "team_raw": ctx["team"],
                    "player_raw": player,
                    "status": status,
                    "reason": reason,
                }
                if status not in OFFICIAL_STATUSES:
                    rejects.append({"page": page_idx, "kind": "ROW",
                                     "raw": joined,
                                     "reason": f"unrecognized_status:{status!r}",
                                     "row": row})
                    continue
                rows_out.append(row)
            elif reason and not player and rows_out:
                rows_out[-1]["reason"] = (
                    rows_out[-1]["reason"] + " " + reason).strip()
            elif player and not status and rows_out:
                rows_out[-1]["player_raw"] = (
                    rows_out[-1]["player_raw"] + " " + player).strip()
            elif joined:
                rejects.append({"page": page_idx, "kind": "ROW",
                                 "raw": joined,
                                 "reason": "unplaceable_row_fragment"})

    meta["not_yet_submitted"] = not_yet_submitted
    return rows_out, meta, rejects
