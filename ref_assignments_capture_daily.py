#!/usr/bin/env python3
"""
Daily WNBA referee-assignments capture (W4 point-in-time feed).

An assignment is only usable by a forecast if it was public before that
forecast's cutoff, so CAPTURE TIME IS THE FEATURE TIMESTAMP. The league posts
assignments once per game day (~9:00am ET per the page itself); querying a
future date returns nothing, so this log has no lookahead by construction.

PRIMARY  : JSON endpoint behind the NBA officiating site's date picker:
             https://official.nba.com/wp-json/api/v1/get-game-officials?date=YYYY-MM-DD
           Returns {nba, gl, wnba} -> Table.rows[]; each row carries the
           league's own game_id (e.g. 1022600210), game_code, home/away team
           + tricode, and official1..official4 with jersey numbers. The
           site's own renderer labels official1..4 as Crew Chief / Referee /
           Umpire / Alternate, and we record those labels.
           NOTE: official.nba.com is a WordPress property on an Akamai CDN -
           NOT stats.nba.com - safe while stats.nba.com crawls are running.

FALLBACK : The server-rendered page itself (no JS needed for TODAY's data):
             https://official.nba.com/referee-assignments/
           <div class="wnba-refs-content"> holds a plain table
           (Game | Crew Chief | Referee | Umpire | Alternate) plus an
           entry-meta date. Today-only: the date picker goes through the
           JSON endpoint above, so past/future dates have no HTML.

Every run ALWAYS saves the raw response before parsing:
    data/ref_assignments/raw/<source>_<UTC yyyymmddTHHMMSSZ>.<json|html>
then appends normalized rows (one per game-official) to
    data/ref_assignments/assignments_log.csv
schema: capture_utc, game_date, game_id, away_team, home_team,
        official_name, official_num, crew_role, source
game_id is the SOURCE's own identifier (JSON only; blank for HTML rows -
never fabricated). Teams are normalized to the 15 canonical franchise names.

Re-runs within a day append a fresh snapshot (idempotent by capture_utc);
dedupe downstream on (capture date, game, official) taking latest capture -
which also surfaces late official scratches/substitutions for free.

Exit 0 with a one-line summary when a source responds validly - including a
structurally valid "no WNBA assignments posted" day (off-day / before ~9am ET
/ off-season), which is reported loudly with per-source diagnostics, never
silently. Exit nonzero only when every attempted source fails outright.

Dependencies: requests. Stdlib otherwise.
"""

import argparse
import csv
import re
import sys
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parent
OUTDIR = ROOT / "data" / "ref_assignments"
RAWDIR = OUTDIR / "raw"
LOGCSV = OUTDIR / "assignments_log.csv"
CSV_HEADER = ["capture_utc", "game_date", "game_id", "away_team", "home_team",
              "official_name", "official_num", "crew_role", "source"]

JSON_URL = "https://official.nba.com/wp-json/api/v1/get-game-officials"
HTML_URL = "https://official.nba.com/referee-assignments/"
UA = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                     "AppleWebKit/537.36 (KHTML, like Gecko) "
                     "Chrome/126.0 Safari/537.36")}

# How the official site's own renderer labels official1..official4 for WNBA
# (server-rendered table headers on the assignments page).
ROLE_LABELS = ["Crew Chief", "Referee", "Umpire", "Alternate"]

# ---------------------------------------------------------------- teams ----
CANON_TEAMS = [
    "Atlanta Dream", "Chicago Sky", "Connecticut Sun", "Dallas Wings",
    "Golden State Valkyries", "Indiana Fever", "Las Vegas Aces",
    "Los Angeles Sparks", "Minnesota Lynx", "New York Liberty",
    "Phoenix Mercury", "Portland Fire", "Seattle Storm", "Toronto Tempo",
    "Washington Mystics",
]
_ALIASES = {}
for _t in CANON_TEAMS:
    _ALIASES[_t.lower()] = _t
    _ALIASES[_t.rsplit(" ", 1)[-1].lower()] = _t          # nickname
    _ALIASES[_t.rsplit(" ", 1)[0].lower()] = _t           # city
_ALIASES.update({
    # tricodes as used by the officials feed and elsewhere
    "atl": "Atlanta Dream", "chi": "Chicago Sky", "con": "Connecticut Sun",
    "conn": "Connecticut Sun", "dal": "Dallas Wings",
    "gsv": "Golden State Valkyries", "gs": "Golden State Valkyries",
    "ind": "Indiana Fever", "lva": "Las Vegas Aces", "lv": "Las Vegas Aces",
    "las": "Los Angeles Sparks", "la": "Los Angeles Sparks",
    "lal": "Los Angeles Sparks", "min": "Minnesota Lynx",
    "nyl": "New York Liberty", "ny": "New York Liberty",
    "phx": "Phoenix Mercury", "pho": "Phoenix Mercury",
    "por": "Portland Fire", "pdx": "Portland Fire", "sea": "Seattle Storm",
    "tor": "Toronto Tempo",
    "was": "Washington Mystics", "wsh": "Washington Mystics",
})


def normalize_team(raw):
    """Map any team spelling/tricode to one of the 15 canonical full names.
    Unknown names pass through unchanged (with a stderr warning) so no data
    is silently dropped if the league expands or renames."""
    key = re.sub(r"\s+", " ", str(raw)).strip().lower()
    if key in _ALIASES:
        return _ALIASES[key]
    print(f"WARNING: unrecognized team name kept as-is: {raw!r}",
          file=sys.stderr)
    return re.sub(r"\s+", " ", str(raw)).strip()


# ---------------------------------------------------------------- http -----
def make_session():
    s = requests.Session()
    s.headers.update(UA)
    retry = Retry(total=3, connect=3, read=2, backoff_factor=1.5,
                  status_forcelist=[429, 500, 502, 503, 504],
                  allowed_methods=["HEAD", "GET"])
    s.mount("https://", HTTPAdapter(max_retries=retry))
    return s


def eastern_now():
    """Current US/Eastern time. zoneinfo when available, else manual DST rule
    (2nd Sunday of March 2am -> 1st Sunday of November 2am)."""
    utc = datetime.now(timezone.utc)
    try:
        from zoneinfo import ZoneInfo
        return utc.astimezone(ZoneInfo("America/New_York"))
    except Exception:
        y = utc.year
        mar = datetime(y, 3, 8, tzinfo=timezone.utc)
        mar += timedelta(days=(6 - mar.weekday()) % 7)      # 2nd Sun of March
        nov = datetime(y, 11, 1, tzinfo=timezone.utc)
        nov += timedelta(days=(6 - nov.weekday()) % 7)      # 1st Sun of Nov
        dst = mar.replace(hour=7) <= utc < nov.replace(hour=6)  # 2am local
        return utc.astimezone(timezone(timedelta(hours=-4 if dst else -5)))


# ----------------------------------------------------------- json parse ----
def _mdy_to_iso(s, default=""):
    m = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", str(s or "").strip())
    return f"{m.group(3)}-{m.group(1)}-{m.group(2)}" if m else default


def parse_json_payload(payload, requested_date):
    """get-game-officials JSON -> (wnba rows, per-league game counts).
    payload[league] is a dict {Table:{rows:[...]}} on game days, or the
    string "null"/None when that league has nothing."""
    counts = {}
    for lg in ("nba", "gl", "wnba"):
        v = payload.get(lg)
        rows = v.get("Table", {}).get("rows") if isinstance(v, dict) else None
        counts[lg] = rows if isinstance(rows, list) else []
    out = []
    for g in counts["wnba"]:
        gd = _mdy_to_iso(g.get("game_date"), default=requested_date)
        if gd != requested_date:
            print(f"WARNING: row game_date {gd} != requested {requested_date}",
                  file=sys.stderr)
        away = g.get("away_team") or g.get("away_team_abbr") or ""
        home = g.get("home_team") or g.get("home_team_abbr") or ""
        for i, role in enumerate(ROLE_LABELS, start=1):
            name = str(g.get(f"official{i}") or "").strip()
            if not name:
                continue                       # alternate often unassigned
            out.append({
                "game_date": gd,
                "game_id": str(g.get("game_id") or "").strip(),
                "away_team": normalize_team(away),
                "home_team": normalize_team(home),
                "official_name": name,
                "official_num": str(g.get(f"official{i}_JNum") or "").strip(),
                "crew_role": role,
            })
    return out, counts


# ----------------------------------------------------------- html parse ----
class _RefPageParser(HTMLParser):
    """Pull each league's assignments table off the server-rendered page.

    Structure per league section (league inferred from the wrapper div class
    '<league>-refs-content'):
        <h1 class="entry-title">WNBA Referee Assignments</h1>
        <div class="entry-meta">July 30, 2026</div>
        ...
        <div class="wnba-refs-content"><table>
          <thead><tr><th>Game</th><th>Crew Chief</th>...</thead>
          <tbody><tr><td>Minnesota @ Toronto</td><td>Maj Forsberg (#34)</td>...
    Sections for leagues with no games that day may be absent entirely.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.sections = {}      # league -> {date, header[], rows[[]]}
        self._league = None     # set while inside a *-refs-content table
        self._grab = None       # "title" | "meta" | "cell"
        self._buf = []
        self._cells = None      # current <tr>'s cell texts
        self._pending_title = None

    def handle_starttag(self, tag, attrs):
        cls = dict(attrs).get("class", "")
        if tag == "div" and cls:
            m = re.search(r"(?:^|\s)([\w-]+)-refs-content(?:\s|$)", cls)
            if m:
                self._league = m.group(1).lower()
                self.sections.setdefault(self._league,
                                         {"date": "", "header": [],
                                          "rows": []})
            elif "entry-meta" in cls and self._pending_title:
                self._grab, self._buf = "meta", []
        elif tag == "h1" and "entry-title" in cls:
            self._grab, self._buf = "title", []
        elif self._league and tag == "tr":
            self._cells = []
        elif self._league and tag in ("td", "th") and self._cells is not None:
            self._grab, self._buf = "cell", []

    def handle_data(self, data):
        if self._grab:
            self._buf.append(data)

    def handle_endtag(self, tag):
        text = re.sub(r"\s+", " ", "".join(self._buf)).strip()
        if tag == "h1" and self._grab == "title":
            m = re.match(r"(.+?)\s+Referee\s+Assignments", text, re.I)
            self._pending_title = m.group(1) if m else None
            self._grab = None
        elif tag == "div" and self._grab == "meta":
            league = {"nba": "nba", "wnba": "wnba",
                      "g league": "g-league"}.get(
                          self._pending_title.lower(), self._pending_title)
            self.sections.setdefault(league,
                                     {"date": "", "header": [], "rows": []})
            self.sections[league]["date"] = text
            self._pending_title, self._grab = None, None
        elif tag in ("td", "th") and self._grab == "cell":
            self._cells.append((tag, text))
            self._grab = None
        elif tag == "tr" and self._league and self._cells:
            sec = self.sections[self._league]
            if all(k == "th" for k, _ in self._cells):
                sec["header"] = [t for _, t in self._cells]
            else:
                sec["rows"].append([t for _, t in self._cells])
            self._cells = None
        elif tag == "table" and self._league:
            self._league = None


_OFFICIAL_RE = re.compile(r"^(?P<name>.*?)\s*\(#(?P<num>[^)]*)\)\s*$")


def parse_html_page(html_text, requested_date):
    """Assignments page HTML -> (wnba rows, diagnostics-string)."""
    p = _RefPageParser()
    p.feed(html_text)
    diag = "; ".join(
        f"{lg}: date={s['date'] or '?'} games={len(s['rows'])}"
        for lg, s in sorted(p.sections.items())) or "no league sections found"
    sec = p.sections.get("wnba")
    if not sec:
        return [], diag
    page_date = requested_date
    try:
        page_date = (datetime.strptime(sec["date"], "%B %d, %Y")
                     .strftime("%Y-%m-%d"))
    except ValueError:
        print(f"WARNING: could not parse page date {sec['date']!r}; "
              f"using {requested_date}", file=sys.stderr)
    if page_date != requested_date:
        print(f"WARNING: page shows {page_date}, requested {requested_date}; "
              f"rows recorded under the page's own date", file=sys.stderr)
    header = sec["header"] or ["Game"] + ROLE_LABELS
    if header[0].lower() != "game":
        raise ValueError(f"assignments table header changed: {header}")
    out = []
    for cells in sec["rows"]:
        if not cells or "@" not in cells[0]:
            continue                                    # not a matchup row
        away, home = (x.strip() for x in cells[0].split("@", 1))
        for role, cell in zip(header[1:], cells[1:]):
            if not cell:
                continue                                # unfilled alternate
            m = _OFFICIAL_RE.match(cell)
            out.append({
                "game_date": page_date,
                "game_id": "",              # HTML gives none; never fabricate
                "away_team": normalize_team(away),
                "home_team": normalize_team(home),
                "official_name": (m.group("name") if m else cell).strip(),
                "official_num": (m.group("num") if m else "").strip(),
                "crew_role": role,
            })
    return out, diag


# ---------------------------------------------------------------- main -----
def save_raw(stamp, source, ext, text):
    RAWDIR.mkdir(parents=True, exist_ok=True)
    p = RAWDIR / f"{source}_{stamp}.{ext}"
    p.write_text(text, encoding="utf-8")
    return p


def append_log(stamp, rows, source):
    OUTDIR.mkdir(parents=True, exist_ok=True)
    new = not LOGCSV.exists()

    def clean(v):                      # keep the CSV one physical line/row
        return re.sub(r"\s+", " ", str(v)).strip()

    with open(LOGCSV, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(CSV_HEADER)
        for r in rows:
            w.writerow([stamp] + [clean(r[k]) for k in CSV_HEADER[1:-1]]
                       + [source])


def capture_json(sess, stamp, game_date):
    resp = sess.get(JSON_URL, params={"date": game_date}, timeout=(10, 60))
    resp.raise_for_status()
    raw_path = save_raw(stamp, "official_nba_json", "json", resp.text)
    rows, counts = parse_json_payload(resp.json(), game_date)
    note = (f"HTTP {resp.status_code}; wnba {len(counts['wnba'])} games / "
            f"{len(rows)} official rows; "
            f"nba {len(counts['nba'])}, gl {len(counts['gl'])} games")
    return rows, raw_path, note


def capture_html(sess, stamp, game_date):
    today_et = eastern_now().strftime("%Y-%m-%d")
    if game_date != today_et:
        raise RuntimeError(f"HTML page only shows today ({today_et}); "
                           f"cannot serve {game_date}")
    resp = sess.get(HTML_URL, timeout=(10, 60))
    resp.raise_for_status()
    raw_path = save_raw(stamp, "official_nba_html", "html", resp.text)
    rows, diag = parse_html_page(resp.text, game_date)
    return rows, raw_path, f"HTTP {resp.status_code}; {diag}"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--date", metavar="YYYY-MM-DD",
                    help="capture this game date instead of today (ET); "
                         "JSON source only - the HTML page is today-only")
    ap.add_argument("--force-source", choices=["json", "html"],
                    help="skip the normal primary->fallback chain (testing)")
    args = ap.parse_args()

    if args.date and not re.match(r"^\d{4}-\d{2}-\d{2}$", args.date):
        sys.exit(f"--date must be YYYY-MM-DD, got {args.date!r}")
    game_date = args.date or eastern_now().strftime("%Y-%m-%d")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    sess = make_session()

    order = {"json": [("official_nba_json", capture_json)],
             "html": [("official_nba_html", capture_html)],
             None: [("official_nba_json", capture_json),
                    ("official_nba_html", capture_html)]}[args.force_source]

    rows, raw_path, note, used = [], None, "", None
    attempts = []                            # (name, outcome) for diagnostics
    for name, fn in order:
        try:
            rows, raw_path, note = fn(sess, stamp, game_date)
            attempts.append((name, f"OK - {note} | raw={raw_path.name}"))
            if rows:
                used = name
                break
            print(f"NOTE: {name} returned no WNBA assignment rows",
                  file=sys.stderr)
        except Exception as e:
            attempts.append((name, f"FAILED - {type(e).__name__}: {e}"))
            print(f"WARNING: {name} capture failed: {e}", file=sys.stderr)

    if used is None:
        all_failed = all(a[1].startswith("FAILED") for a in attempts)
        print(f"NO WNBA ASSIGNMENTS CAPTURED for {game_date}; checked:",
              file=sys.stderr)
        for name, outcome in attempts:
            print(f"  {name}: {outcome}", file=sys.stderr)
        if all_failed:
            sys.exit(f"{stamp}: all assignment sources failed; "
                     f"nothing captured")
        # Valid-but-empty (off day / pre-9am-ET / off-season): loud, exit 0.
        print(f"{stamp}: 0 assignment rows for {game_date} - no WNBA "
              f"assignments posted on any checked source (details above)")
        return

    append_log(stamp, rows, used)
    games = len({(r['game_id'], r['away_team'], r['home_team'])
                 for r in rows})
    with open(LOGCSV, newline="", encoding="utf-8") as f:
        total = sum(1 for _ in csv.reader(f)) - 1
    print(f"{stamp}: {len(rows)} official-assignment rows across {games} "
          f"games for {game_date} | source={used} ({note}) | "
          f"raw={raw_path.relative_to(ROOT)} | "
          f"log={LOGCSV.relative_to(ROOT)} (total {total} rows)")


if __name__ == "__main__":
    main()
