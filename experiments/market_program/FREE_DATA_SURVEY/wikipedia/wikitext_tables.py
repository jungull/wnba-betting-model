"""
wikitext_tables.py — small, dependency-free MediaWiki wikitable extractor.

Not a general wikitext parser. Handles exactly the subset needed to walk
`{| ... |}` wikitables: `!`/`!!` header cells, `|`/`||` data cells, `|-` row
separators, and `rowspan=N` propagation down a column. Anything outside that
subset is left as raw text for the caller to reject rather than guess at.

No external dependencies (mwparserfromhell is not installed in this
environment; this module exists so parse.py does not need it).
"""

import re
from dataclasses import dataclass, field

TABLE_RE = re.compile(r"\{\|(?P<attrs>[^\n]*)\n(?P<body>.*?)\n\|\}", re.DOTALL)
LINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
REF_RE = re.compile(r"<ref[^>]*>.*?</ref>|<ref[^/]*/>", re.DOTALL)
COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
SMALL_RE = re.compile(r"</?small>")
BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)


@dataclass
class Cell:
    raw: str
    text: str
    rowspan: int = 1
    colspan: int = 1
    is_header: bool = False


@dataclass
class Table:
    attrs: str
    rows: list = field(default_factory=list)  # list[list[Cell]]
    start_pos: int = 0
    end_pos: int = 0


def clean_cell_text(raw: str) -> str:
    """Strip refs/comments/wiki-markup noise, resolve [[link|display]] to display text."""
    t = raw
    t = REF_RE.sub("", t)
    t = COMMENT_RE.sub("", t)
    t = SMALL_RE.sub("", t)
    t = BR_RE.sub("; ", t)
    t = re.sub(r"\{\{flagicon\|[^}]*\}\}", "", t)
    t = re.sub(r"\{\{dts\|([^}]*)\}\}", lambda m: m.group(1), t)
    # {{sortname|First|Last|...}} is the standard template for a sortable player
    # name cell — render "First Last", never delete it as generic template noise.
    t = re.sub(
        r"\{\{sortname\|([^|}]*)\|([^|}]*)(?:\|[^}]*)?\}\}",
        lambda m: f"{m.group(1).strip()} {m.group(2).strip()}".strip(),
        t,
        flags=re.IGNORECASE,
    )
    t = LINK_RE.sub(lambda m: m.group(2) or m.group(1), t)
    # strip any remaining templates {{...}} conservatively (no nested-brace handling)
    t = re.sub(r"\{\{[^{}]*\}\}", "", t)
    # strip cell attribute prefix like `align=center|` or `style="..."|`
    t = strip_cell_attrs(t.strip())
    t = t.replace("'''", "").replace("''", "")
    return t.strip(" \t\n|")


def strip_cell_attrs(cell_content: str) -> str:
    """
    A wikitable cell can start with `attr=val attr2="val2"|actual content`.
    Only strip if a bare `|` (not part of a link, already resolved above) appears
    before any wiki-link brackets — conservative: only strips a single leading
    attr-block if the heuristic clearly matches.
    """
    m = re.match(r'^([a-zA-Z][a-zA-Z0-9_\- ]*=(?:"[^"]*"|\'[^\']*\'|[^\s|]+)\s*)+\|(?!\|)(.*)$', cell_content, re.DOTALL)
    if m:
        return m.group(2)
    return cell_content


def extract_span_attrs(raw_cell: str) -> tuple:
    rowspan = 1
    colspan = 1
    m = re.search(r"rowspan\s*=\s*\"?(\d+)\"?", raw_cell)
    if m:
        rowspan = int(m.group(1))
    m = re.search(r"colspan\s*=\s*\"?(\d+)\"?", raw_cell)
    if m:
        colspan = int(m.group(1))
    return rowspan, colspan


def find_tables(wikitext: str):
    """Yield Table objects in document order (non-nested; nested tables inside a
    cell will appear mangled — acceptable for this source, none observed in scope)."""
    for m in TABLE_RE.finditer(wikitext):
        attrs = m.group("attrs")
        body = m.group("body")
        rows = _parse_rows(body)
        yield Table(attrs=attrs, rows=rows, start_pos=m.start(), end_pos=m.end())


HEADER_INLINE_SEP_RE = re.compile(r"!!|\|\|")


def _split_cells(line_group: str, sep_single: str, sep_double: str, is_header: bool):
    """
    line_group: text belonging to one logical row-line (may itself contain
    embedded newlines for continuation content like refs).

    MediaWiki allows a header line (starting with `!`) to separate its cells with
    EITHER `!!` or `||` — both are observed in the wild across different years of
    the same article family, so header rows split on either, not `!!` only.
    """
    cells = []
    if is_header:
        parts = HEADER_INLINE_SEP_RE.split(line_group)
    else:
        # Split on the double-pipe separator (same-line multi-cell)
        parts = re.split(re.escape(sep_double), line_group)
    for part in parts:
        rowspan, colspan = extract_span_attrs(part)
        text = clean_cell_text(part)
        cells.append(Cell(raw=part, text=text, rowspan=rowspan, colspan=colspan, is_header=is_header))
    return cells


def _parse_rows(body: str):
    """
    Parse the body between {| ... |} into logical rows. MediaWiki wikitable syntax:
      |-        starts a new row
      !  / !!   header cell(s) on one line
      |  / ||   data cell(s) on one line
    A cell's content can span multiple physical lines if a `|`-prefixed line
    doesn't appear (e.g. embedded refs/lists) — we join continuation lines into
    the preceding cell.
    """
    lines = body.split("\n")
    rows = []  # list[list[Cell]]
    current_row_lines = []  # raw cell-start lines accumulated for current row
    pending_cell = None  # (prefix_char, text_accum)

    def flush_cell():
        nonlocal pending_cell
        if pending_cell is not None:
            prefix, buf = pending_cell
            current_row_lines.append((prefix, buf))
            pending_cell = None

    def flush_row():
        nonlocal current_row_lines
        flush_cell()
        if current_row_lines:
            row_cells = []
            for prefix, buf in current_row_lines:
                is_header = prefix == "!"
                sep_double = "!!" if is_header else "||"
                row_cells.extend(_split_cells(buf, prefix, sep_double, is_header))
            rows.append(row_cells)
        current_row_lines = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|-"):
            flush_cell()
            flush_row()
            continue
        if stripped.startswith("|}") or stripped.startswith("{|"):
            continue
        if stripped.startswith("!"):
            flush_cell()
            pending_cell = ("!", stripped[1:])
        elif stripped.startswith("|"):
            flush_cell()
            pending_cell = ("|", stripped[1:])
        else:
            # continuation of previous cell's content (e.g. wrapped ref/list line)
            if pending_cell is not None:
                prefix, buf = pending_cell
                pending_cell = (prefix, buf + "\n" + line)
            # else: stray text before first cell (captions etc.) — ignored
    flush_row()
    return rows


def materialize_grid(rows):
    """
    Turn the raw row list (with rowspan/colspan) into a dense grid of Cell
    references, propagating rowspan down columns. Returns list[list[Cell]] where
    every row has the same length (padded with None for genuinely short rows —
    caller must treat None as a reject signal, never guess a value).

    Standard HTML/wikitable grid-fill algorithm: track active rowspan carries as
    (col_index -> (Cell, rows_remaining)); for each new row, columns occupied by a
    carry are skipped when placing that row's own new cells into the next free
    column slots, left to right.
    """
    if not rows:
        return []
    ncols = max((sum(c.colspan for c in row) for row in rows), default=0)
    if ncols == 0:
        return []

    grid = []
    carry = {}  # col_index -> (Cell, rows_remaining_after_this_row)

    for row in rows:
        out_row = [None] * ncols

        # 1) place carried-over rowspan cells at their fixed columns
        for c, (cell, _remaining) in carry.items():
            if c < ncols:
                out_row[c] = cell

        # 2) place this row's own cells into the next free (non-carried) columns
        c = 0
        for cell in row:
            while c < ncols and out_row[c] is not None:
                c += 1
            for _ in range(cell.colspan):
                if c >= ncols:
                    break
                out_row[c] = cell
                c += 1

        grid.append(out_row)

        # 3) decrement carries, drop expired ones, add newly-introduced rowspans
        new_carry = {}
        for c2, (cell, remaining) in carry.items():
            if remaining - 1 > 0:
                new_carry[c2] = (cell, remaining - 1)
        c = 0
        for cell in row:
            while c < ncols and out_row[c] is not cell:
                c += 1
            for _ in range(cell.colspan):
                if c >= ncols:
                    break
                if cell.rowspan > 1 and c not in new_carry:
                    new_carry[c] = (cell, cell.rowspan - 1)
                c += 1
        carry = new_carry

    return grid
