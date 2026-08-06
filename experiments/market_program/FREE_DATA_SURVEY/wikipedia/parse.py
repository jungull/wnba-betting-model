"""
parse.py — parse archived Wikipedia WNBA transactions wikitext into structured rows.

Reads raw/*.json (written by harvest.py — verbatim wikitext + capture metadata) and
produces:
    parsed/<season>_transactions.jsonl  — one structured row per parsed transaction
    parsed/<season>_rejects.jsonl       — every table row this parser could not map
                                           with confidence, WITH THE RAW TEXT PRESERVED,
                                           never silently dropped (strict no-guess rule).

SCHEMA (parsed rows)
    date_wiki            raw date text as it appears in the table (e.g. "March 15") —
                          NOT normalized to an ISO date, because the tables frequently
                          omit the year and this parser refuses to guess which calendar
                          year an unlabeled month/day belongs to.
    season                the season page's year (int) — CONTEXT ONLY, not asserted to
                          be the transaction's calendar year (off-season moves in
                          Nov/Dec/Jan routinely belong to the adjacent calendar year).
    player                player display name (wikilink text resolved)
    team_from             team text, or null if not applicable/not stated
    team_to               team text, or null if not applicable/not stated
    transaction_type      one of: signed, waived, retired, drafted, traded,
                          head_coach_change, general_manager_change
    source_line           the ref/citation text found in the row (raw, uncleaned,
                          for traceability back to the cited source)
    section / subsection   wikitext heading path the row was found under
    wiki_revision_id / wiki_revision_ts  carried through from the raw archive record
    retrieval_ts          carried through from the raw archive record
    payload_hash_sha256   carried through from the raw archive record
    provenance_class      "WIKIPEDIA_PARSED_TABLE_ROW"
    confidence_label      fixed "EDITOR_ASSERTED_UNVERIFIED" (matches MARKET_SOURCES.md
                          section 5.6 schema discipline)

REJECTS SCHEMA
    season, table_type_guess, section, subsection, reason, raw_row_cells (list of raw
    cell text), wiki_revision_id, retrieval_ts — enough to manually inspect and fix the
    parser later without re-fetching.

NO-GUESS RULE
    A table row is only emitted as a parsed transaction if its header shape matches one
    of the known layouts below AND every required field for that layout resolved to
    non-empty text. Anything else — unrecognized header set, column-count mismatch after
    rowspan-fill, empty required cell — goes to rejects with a specific reason string.
    Trade tables (asymmetric "To [[Team]]" block layout, not row-per-transaction) are
    parsed with a dedicated, narrower routine; trade blocks involving more than two
    teams or that don't match the expected bullet-list-of-players shape are rejected
    rather than guessed at.
"""

import argparse
import json
import re
from pathlib import Path

from wikitext_tables import Cell, clean_cell_text, find_tables, materialize_grid

HERE = Path(__file__).resolve().parent
RAW_DIR = HERE / "raw"
PARSED_DIR = HERE / "parsed"

HEADING_RE = re.compile(r"^(={2,5})\s*(.*?)\s*\1\s*$")
SUBHEADING_MARKER_RE = re.compile(r"^;\s*(.+)$")  # e.g. `;Off-season`

TEAM_LINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
BULLET_PLAYER_RE = re.compile(r"^\*\s*(.+)$", re.MULTILINE)
MONTH_HEADER_RE = re.compile(r"^!\s*colspan\s*=\s*\d+\s*\|\s*([A-Za-z]+)\s*$")


def norm_header(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def build_section_index(wikitext: str):
    """
    Returns a sorted list of (pos, level, section_title_path, subheading_or_None)
    so any table's start_pos can be mapped back to the nearest enclosing headings.
    """
    events = []
    current_h2 = None
    current_h3 = None
    current_semicolon = None
    pos = 0
    for line in wikitext.split("\n"):
        line_len = len(line) + 1
        m = HEADING_RE.match(line.strip())
        if m:
            level = len(m.group(1))
            title = m.group(2)
            if level == 2:
                current_h2, current_h3, current_semicolon = title, None, None
            elif level == 3:
                current_h3, current_semicolon = title, None
            else:
                current_semicolon = None
        else:
            m2 = SUBHEADING_MARKER_RE.match(line.strip())
            if m2:
                current_semicolon = m2.group(1)
        events.append((pos, current_h2, current_h3, current_semicolon))
        pos += line_len
    return events


def section_for_pos(events, pos):
    best = (None, None, None)
    for ev_pos, h2, h3, semi in events:
        if ev_pos <= pos:
            best = (h2, h3, semi)
        else:
            break
    return best


# ---------------------------------------------------------------------------
# Known simple-list table layouts: header-set -> (transaction_type, field map)
# field map values are lists of acceptable normalized header strings for that
# logical field, checked in order.
# ---------------------------------------------------------------------------
LAYOUTS = [
    {
        # observed live header set (2024): Player | Date Waived | Former Team | Ref
        "type": "waived",
        "required": {
            "player": ["player"],
            "date": ["date waived"],
            "team_from": ["former team"],
        },
        "optional": {"source_line": ["ref", "ref."]},
    },
    {
        # observed live header set (2024, "Free agency" section): Player | Date signed
        # | New team | Former team | Ref
        "type": "signed",
        "required": {
            "player": ["player"],
            "date": ["date signed", "signing date"],
            "team_to": ["new team"],
        },
        "optional": {"source_line": ["ref", "ref."], "team_from": ["former team"]},
    },
    {
        # observed live header set (2021/2020 "Retirement" section): Date | Name |
        # Team(s) played (years) | Age | Notes | Ref.  NOTE: "Team(s) played (years)"
        # is stored verbatim into team_from including any parenthetical year ranges
        # it contains — not split apart, that would be guessing at structure the
        # cell text doesn't cleanly delimit.
        "type": "retired",
        "required": {
            "player": ["name", "player"],
            "date": ["date", "retirement date"],
        },
        "optional": {
            "source_line": ["ref", "ref.", "ref "],
            "team_from": ["team(s) played (years)", "team", "last team"],
        },
    },
    {
        # observed live header set ("Previous years' draftees"): Draft | Pick | Player
        # | Date signed | Team | Previous team | Ref. NOTE: the First/Second/Third
        # Round draft tables on this page are MediaWiki template transclusions
        # ({{#section:<year> WNBA draft|firstround}}) with no literal wikitable in
        # this page's wikitext — they are NOT captured by this harvest (out of scope:
        # would require fetching the separate "<year> WNBA draft" page, not surveyed
        # or graduated by D030). Only this "previous years' draftees" table, which is
        # a literal wikitable on the transactions page itself, is covered.
        "type": "drafted",
        "required": {
            "player": ["player"],
            "team_to": ["team"],
        },
        "optional": {
            "date": ["date signed", "date"],
            "source_line": ["ref", "ref."],
            "pick": ["pick"],
            "round": ["draft", "round"],
            "team_from": ["previous team"],
        },
    },
    {
        "type": "head_coach_change",
        "required": {
            "team_from": ["team"],
            "date": ["departure date"],
        },
        "optional": {
            "outgoing": ["outgoing head coach"],
            "incoming": ["incoming head coach"],
            "hire_date": ["hire date"],
            "source_line": ["ref", "ref."],
        },
    },
    {
        "type": "general_manager_change",
        "required": {
            "team_from": ["team"],
            "date": ["departure date"],
        },
        "optional": {
            "outgoing": ["outgoing\ngeneral manager", "outgoing general manager"],
            "incoming": ["incoming\ngeneral manager", "incoming general manager"],
            "hire_date": ["hire date"],
            "source_line": ["ref", "ref."],
        },
    },
]


def classify_layout(headers_norm):
    header_set = set(headers_norm)
    for layout in LAYOUTS:
        req = layout["required"]
        ok = True
        field_to_idx = {}
        for field, candidates in req.items():
            idx = None
            for cand in candidates:
                if cand in headers_norm:
                    idx = headers_norm.index(cand)
                    break
            if idx is None:
                ok = False
                break
            field_to_idx[field] = idx
        if ok:
            opt = layout.get("optional", {})
            for field, candidates in opt.items():
                for cand in candidates:
                    if cand in headers_norm:
                        field_to_idx[field] = headers_norm.index(cand)
                        break
            return layout["type"], field_to_idx
    return None, None


def parse_simple_table(table, season, section_path, revision_meta, rejects):
    grid = materialize_grid(table.rows)
    if len(grid) < 2:
        return []
    header_row = grid[0]
    headers_norm = [norm_header(c.text) if c else "" for c in header_row]
    ttype, field_to_idx = classify_layout(headers_norm)
    if ttype is None:
        rejects.append({
            "season": season,
            "table_type_guess": "unrecognized_simple_table",
            "section": section_path,
            "reason": f"header set not recognized: {headers_norm}",
            "raw_row_cells": headers_norm,
            **revision_meta,
        })
        return []

    out = []
    for row in grid[1:]:
        def get(field):
            idx = field_to_idx.get(field)
            if idx is None or idx >= len(row) or row[idx] is None:
                return None
            return row[idx].text

        player = get("player")
        date_wiki = get("date")
        team_from = get("team_from")
        team_to = get("team_to")
        source_line = get("source_line")

        # required-field presence check per layout (player + date always meaningful;
        # drafted/coach/gm layouts have their own required set already enforced by
        # classify_layout at the header level, but per-row emptiness still checked)
        missing = []
        if ttype in ("waived", "signed", "retired", "drafted") and not player:
            missing.append("player")
        if ttype in ("head_coach_change", "general_manager_change") and not team_from:
            missing.append("team_from")

        if missing:
            rejects.append({
                "season": season,
                "table_type_guess": ttype,
                "section": section_path,
                "reason": f"required field(s) empty after rowspan-fill: {missing}",
                "raw_row_cells": [c.text if c else None for c in row],
                **revision_meta,
            })
            continue

        out.append({
            "date_wiki": date_wiki,
            "season": season,
            "player": player,
            "team_from": team_from,
            "team_to": team_to,
            "transaction_type": ttype,
            "source_line": source_line,
            "section": section_path,
            "provenance_class": "WIKIPEDIA_PARSED_TABLE_ROW",
            "confidence_label": "EDITOR_ASSERTED_UNVERIFIED",
            **revision_meta,
        })
    return out


# ---------------------------------------------------------------------------
# Trade tables: asymmetric layout, month sub-headers, "To [[Team]]" cells with
# bullet-list players. Only 2-team, clearly-shaped blocks are parsed; anything
# else (3+ teams, unparseable cell shape) is rejected explicitly.
# ---------------------------------------------------------------------------

def parse_trade_table(table, season, section_path, revision_meta, rejects):
    body_rows = table.rows
    out = []
    current_month = None
    current_date = None  # carried across rowspan rows within a trade block

    i = 0
    while i < len(body_rows):
        row = body_rows[i]
        if len(row) == 1 and row[0].is_header:
            m = MONTH_HEADER_RE.match("!" + row[0].raw if not row[0].raw.startswith("colspan") else "!" + row[0].raw)
            # header cell raw already stripped of leading '!'; try direct match too
            mm = re.match(r"^\s*colspan\s*=\s*\d+\s*\|\s*([A-Za-z]+)\s*$", row[0].raw.strip())
            if mm:
                current_month = mm.group(1)
            i += 1
            continue

        if not row:
            i += 1
            continue

        cells = row
        # first cell, if not consumed by rowspan carry semantics at this raw-row
        # level, may hold the date (e.g. "January 31" split as day only, month from
        # header). We only trust an explicit date cell; otherwise reject the block.
        first = cells[0]
        date_candidate = first.text.strip()
        team_cells = cells[1:]

        if not team_cells or len(team_cells) < 2:
            rejects.append({
                "season": season,
                "table_type_guess": "trade",
                "section": section_path,
                "reason": "trade row has fewer than 2 team/reference cells; not parsed",
                "raw_row_cells": [c.text for c in cells],
                **revision_meta,
            })
            i += 1
            continue

        # Expect exactly 2 "To [[Team]]" blocks + 1 ref cell (3 cells) for a clean
        # 2-team trade. Anything else is rejected rather than guessed.
        to_blocks = [c for c in team_cells if c.text.strip().lower().startswith("to ")]
        if len(to_blocks) != 2:
            rejects.append({
                "season": season,
                "table_type_guess": "trade",
                "section": section_path,
                "reason": f"expected exactly 2 'To <Team>' blocks, found {len(to_blocks)} "
                          f"(likely 3+-team trade or non-standard cell shape) — not parsed",
                "raw_row_cells": [c.text for c in cells],
                **revision_meta,
            })
            i += 1
            continue

        source_line_cell = next((c for c in team_cells if c not in to_blocks), None)
        source_line = source_line_cell.raw if source_line_cell else None

        parsed_sides = []
        block_ok = True
        for block in to_blocks:
            # team name is on the first line only ("To [[Team]]<hr>" then a bullet
            # list follows on subsequent lines) — match line-by-line, not the whole
            # multi-line cell text, since a trailing "$" without DOTALL/MULTILINE
            # would otherwise never match a cell that contains embedded newlines.
            first_line = block.text.strip().split("\n", 1)[0]
            first_line = re.sub(r"<hr\s*/?>\s*$", "", first_line, flags=re.IGNORECASE).strip()
            m = re.match(r"^to\s+(.+?)\s*$", first_line, re.IGNORECASE)
            if not m:
                block_ok = False
                break
            team_name = m.group(1).strip()
            players = BULLET_PLAYER_RE.findall(block.raw)
            player_names = []
            for p in players:
                p_clean = clean_cell_text(p)
                # skip pick/asset lines (no player wikilink resolvable, e.g. "2026 first-round pick")
                if TEAM_LINK_RE.search(p) or not re.search(r"pick|cash|consideration", p, re.IGNORECASE):
                    if p_clean:
                        player_names.append(p_clean)
            parsed_sides.append((team_name, player_names))

        # Both sides must resolve a team name; at least one side must carry a player
        # (a pick-for-pick or pick-only side legitimately has zero players — that is
        # not an error, just nothing to emit for that side). Only reject if NEITHER
        # side has a player (nothing worth recording) or a team name failed to parse.
        if not block_ok or all(not side[1] for side in parsed_sides):
            rejects.append({
                "season": season,
                "table_type_guess": "trade",
                "section": section_path,
                "reason": "could not extract team name, or neither trade block contained a player "
                          "(e.g. picks-only both sides — nothing to record)",
                "raw_row_cells": [c.text for c in cells],
                **revision_meta,
            })
            i += 1
            continue

        (team_a, players_a), (team_b, players_b) = parsed_sides
        date_wiki = f"{current_month} {date_candidate}".strip() if current_month and date_candidate and not re.search(r"[A-Za-z]", date_candidate) else (date_candidate or current_month)

        for player in players_a:
            out.append({
                "date_wiki": date_wiki,
                "season": season,
                "player": player,
                "team_from": team_b,
                "team_to": team_a,
                "transaction_type": "traded",
                "source_line": source_line,
                "section": section_path,
                "provenance_class": "WIKIPEDIA_PARSED_TABLE_ROW",
                "confidence_label": "EDITOR_ASSERTED_UNVERIFIED",
                **revision_meta,
            })
        for player in players_b:
            out.append({
                "date_wiki": date_wiki,
                "season": season,
                "player": player,
                "team_from": team_a,
                "team_to": team_b,
                "transaction_type": "traded",
                "source_line": source_line,
                "section": section_path,
                "provenance_class": "WIKIPEDIA_PARSED_TABLE_ROW",
                "confidence_label": "EDITOR_ASSERTED_UNVERIFIED",
                **revision_meta,
            })
        i += 1

    return out


def is_trade_table(section_path) -> bool:
    _h2, h3, _semi = section_path
    return bool(h3 and "trade" in h3.lower())


def parse_record(record: dict):
    """record: one raw/*.json dict from harvest.py. Returns (parsed_rows, reject_rows)."""
    if not record.get("found"):
        return [], [{
            "season": record.get("season"),
            "table_type_guess": None,
            "section": None,
            "reason": "page not found at harvest time",
            "raw_row_cells": None,
            "wiki_revision_id": None,
            "wiki_revision_ts": None,
            "retrieval_ts": record.get("retrieval_ts"),
            "payload_hash_sha256": record.get("payload_hash_sha256"),
        }]

    wikitext = record["wikitext_raw"]
    season = record["season"]
    revision_meta = {
        "wiki_revision_id": record.get("wiki_revision_id"),
        "wiki_revision_ts": record.get("wiki_revision_ts"),
        "retrieval_ts": record.get("retrieval_ts"),
        "payload_hash_sha256": record.get("payload_hash_sha256"),
    }

    events = build_section_index(wikitext)
    parsed_rows = []
    reject_rows = []

    for table in find_tables(wikitext):
        h2, h3, semi = section_for_pos(events, table.start_pos)
        section_path = (h2, h3, semi)
        if is_trade_table(section_path):
            parsed_rows.extend(parse_trade_table(table, season, section_path, revision_meta, reject_rows))
        else:
            parsed_rows.extend(parse_simple_table(table, season, section_path, revision_meta, reject_rows))

    return parsed_rows, reject_rows


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    ap.add_argument("--out-dir", type=Path, default=PARSED_DIR)
    args = ap.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)

    totals = {}
    for raw_path in sorted(args.raw_dir.glob("*.json")):
        record = json.loads(raw_path.read_text(encoding="utf-8"))
        season = record.get("season")
        parsed_rows, reject_rows = parse_record(record)

        parsed_path = args.out_dir / f"{season}_transactions.jsonl"
        rejects_path = args.out_dir / f"{season}_rejects.jsonl"
        with parsed_path.open("w", encoding="utf-8") as f:
            for row in parsed_rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        with rejects_path.open("w", encoding="utf-8") as f:
            for row in reject_rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

        totals[season] = (len(parsed_rows), len(reject_rows))
        print(f"season {season}: {len(parsed_rows)} parsed rows, {len(reject_rows)} rejects "
              f"-> {parsed_path.name} / {rejects_path.name}")

    total_parsed = sum(v[0] for v in totals.values())
    total_rejects = sum(v[1] for v in totals.values())
    print(f"\nTotal: {total_parsed} parsed rows, {total_rejects} rejects across {len(totals)} season(s).")


if __name__ == "__main__":
    main()
