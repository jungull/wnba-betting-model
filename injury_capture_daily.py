#!/usr/bin/env python3
"""
Daily WNBA injury/availability report capture.

Scheduled twice daily (noon + 6:30pm local) via Windows Task Scheduler so we
snapshot the league availability picture before lines move and near lock.

PRIMARY  : Official WNBA injury report PDF (same generator as the NBA report).
           PDFs land hourly on a static Akamai CDN:
             https://ak-static.cms.nba.com/referee/wnba_injury/
                 Injury-Report_{YYYY-MM-DD}_{HH_MM}{AM|PM}.pdf   (US/Eastern)
           We walk back from "now" in 15-minute steps (max 48h) until a PDF
           exists, so we always capture the latest published report. Columns:
           Game Date / Game Time / Matchup / Team / Player / Status / Reason,
           with real designations (Out/Doubtful/Questionable/Probable/Available).
           NOTE: this host is a static CDN - NOT stats.nba.com - safe to hit
           while stats.nba.com collection runs are in progress.

FALLBACK : ESPN injuries JSON (no key, no JS, works in the off-season too):
             https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/injuries
           Coarser statuses (Out / Day-To-Day) and no game date, but keeps the
           log alive if the league PDF moves or fails to parse.

Every run ALWAYS saves the raw payload first:
    data/injury_capture/raw/<source>_<UTC yyyymmddTHHMMSSZ>.<pdf|json>
then appends normalized rows (one per player-designation) to
    data/injury_capture/injury_log.csv
schema: capture_utc, report_date, game_date, team, player, status, reason, source

Exit 0 with a one-line summary when either source succeeds (a structurally
valid but empty report - e.g. every team NOT YET SUBMITTED - is success);
exit nonzero only when BOTH sources fail.

Dependencies: requests, pypdf (pip install --user pypdf). Stdlib otherwise.
"""

import argparse
import csv
import io
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parent
OUTDIR = ROOT / "data" / "injury_capture"
RAWDIR = OUTDIR / "raw"
LOGCSV = OUTDIR / "injury_log.csv"
CSV_HEADER = ["capture_utc", "report_date", "game_date", "team", "player",
              "status", "reason", "source"]

PDF_BASE = ("https://ak-static.cms.nba.com/referee/wnba_injury/"
            "Injury-Report_{date}_{slot}.pdf")
ESPN_URL = ("https://site.api.espn.com/apis/site/v2/sports/basketball/"
            "wnba/injuries")
UA = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                     "AppleWebKit/537.36 (KHTML, like Gecko) "
                     "Chrome/126.0 Safari/537.36")}
LOOKBACK_HOURS = 48          # how far back to hunt for the newest PDF
OFFICIAL_STATUSES = {"Out", "Doubtful", "Questionable", "Probable", "Available"}

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
    # tricodes as used in the official report Matchup column and elsewhere
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


def slot_label(dt):
    """ET datetime -> '11_00AM' / '12_00PM' style filename slot."""
    h = dt.hour % 12
    if h == 0:
        h = 12
    return f"{h:02d}_{dt.minute:02d}{'AM' if dt.hour < 12 else 'PM'}"


def find_latest_official_pdf(sess):
    """Walk back from now (ET) in 15-min steps until a published PDF exists.
    Returns (url, report_datetime_et) or (None, None)."""
    now_et = eastern_now()
    t = now_et.replace(minute=(now_et.minute // 15) * 15, second=0,
                       microsecond=0)
    for _ in range(LOOKBACK_HOURS * 4):
        url = PDF_BASE.format(date=t.strftime("%Y-%m-%d"), slot=slot_label(t))
        try:
            if sess.head(url, timeout=(10, 20)).status_code == 200:
                return url, t
        except requests.RequestException:
            pass                      # transient probe error: keep walking
        time.sleep(0.05)              # be polite to the CDN
        t -= timedelta(minutes=15)
    return None, None


# ------------------------------------------------------- official parse ----
def _classify(cells):
    joined = " ".join(t for _, t in cells)
    if ("Game" in joined and "Matchup" in joined and "Player" in joined
            and "Reason" in joined):
        return "HEADER"
    if (re.search(r"Injury\s+Report:", joined)
            or re.match(r"^Page\s+\d+\s*of", joined)):
        return "META"
    return "ROW"


def _page_rows(page, prev_ascending):
    """Extract words with coordinates, cluster into visual rows, and return
    ([(kind, [(x, text)]), ...] in reading order, ascending_used).

    The league PDF generator emits text bottom-up, so reading order must be
    derived, not assumed: the header row always sits visually ABOVE the data
    rows, so whichever y-sort puts the header before the data is correct.
    Title/page-number rows are excluded from that comparison."""
    words = []

    def visitor(text, cm, tm, font_dict, font_size):
        t = text.strip()
        if t:
            words.append((tm[5], tm[4], t))               # (y, x, text)

    page.extract_text(visitor_text=visitor)
    if not words:
        return [], prev_ascending
    rows = []                                             # [y, [(x, text)]]
    for y, x, t in sorted(words, key=lambda w: w[0]):
        if rows and abs(rows[-1][0] - y) <= 2.0:
            rows[-1][1].append((x, t))
        else:
            rows.append([y, [(x, t)]])
    for r in rows:
        r[1].sort(key=lambda w: w[0])

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
    """Header tokens -> x start of each of the 7 columns."""
    xs = {}
    toks = header_cells                                    # already x-sorted
    for i, (x, t) in enumerate(toks):
        if t == "Game" and "game_date" not in xs:
            xs["game_date"] = x
        elif t == "Game":
            xs["game_time"] = x
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
    if any(k not in xs for k in need):
        raise ValueError(f"injury PDF header changed; found columns {xs}")
    return [(k, xs[k]) for k in need]


def _bucket(cells, cols):
    """Assign row tokens to named columns by x position."""
    out = {k: [] for k, _ in cols}
    bounds = [x for _, x in cols] + [float("inf")]
    for x, t in cells:
        for i, (name, _) in enumerate(cols):
            if bounds[i] - 4 <= x < bounds[i + 1] - 4:
                out[name].append(t)
                break
        else:
            out[cols[0][0]].append(t)                      # left of table
    return {k: " ".join(v).strip() for k, v in out.items()}


def parse_official_pdf(pdf_bytes):
    """Official injury-report PDF -> (player_rows, meta). Carries game/team
    context across wrapped lines and page breaks; skips NOT YET SUBMITTED."""
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(pdf_bytes))
    rows_out, meta = [], {"report_date": "", "not_submitted": 0}
    ctx = {"game_date": "", "game_time": "", "matchup": "", "team": ""}
    cols, ascending = None, True
    for page in reader.pages:
        page_rows, ascending = _page_rows(page, ascending)
        for kind, cells in page_rows:
            joined = " ".join(t for _, t in cells)
            if kind == "HEADER":
                cols = _column_starts(cells)
                continue
            if kind == "META":
                m = re.search(r"Injury\s+Report:\s*(\d{2}/\d{2}/\d{2,4})",
                              joined)
                if m:
                    d = m.group(1)
                    fmt = "%m/%d/%Y" if len(d) == 10 else "%m/%d/%y"
                    meta["report_date"] = (datetime.strptime(d, fmt)
                                           .strftime("%Y-%m-%d"))
                continue
            if cols is None or not joined:  # stray text before any header
                continue
            cell = _bucket(cells, cols)
            if cell["game_date"]:
                ctx["game_date"] = cell["game_date"]
                ctx["team"] = ""                       # new date, new group
            if cell["game_time"]:
                ctx["game_time"] = cell["game_time"]
                ctx["team"] = ""
            if cell["matchup"]:
                ctx["matchup"] = cell["matchup"]
                ctx["team"] = ""                       # never carry across
            if cell["team"]:
                ctx["team"] = cell["team"]
            if "NOT YET SUBMITTED" in joined.upper():
                meta["not_submitted"] += 1
                continue
            player, status, reason = cell["player"], cell["status"], \
                cell["reason"]
            if player and status:
                player = re.sub(r"-\s+", "-", player)      # 'Parker- Tyus'
                if "," in player:                          # Last, First
                    last, first = player.split(",", 1)
                    player = f"{first.strip()} {last.strip()}"
                if status not in OFFICIAL_STATUSES:
                    print(f"WARNING: unexpected status {status!r} for "
                          f"{player!r}", file=sys.stderr)
                gd = ctx["game_date"]
                if re.match(r"^\d{2}/\d{2}/\d{4}$", gd):
                    gd = datetime.strptime(gd, "%m/%d/%Y").strftime("%Y-%m-%d")
                rows_out.append({
                    "report_date": meta["report_date"],
                    "game_date": gd,
                    "team": normalize_team(ctx["team"]),
                    "player": player,
                    "status": status,
                    "reason": reason,
                })
            elif reason and not player and rows_out:
                rows_out[-1]["reason"] = (rows_out[-1]["reason"] + " "
                                          + reason).strip()
            elif player and not status and rows_out:       # wrapped name
                rows_out[-1]["player"] = (rows_out[-1]["player"] + " "
                                          + player).strip()
    if not meta["report_date"] and rows_out:
        meta["report_date"] = rows_out[0]["game_date"]
    return rows_out, meta


# ----------------------------------------------------------- espn parse ----
def parse_espn(payload):
    """ESPN injuries JSON -> normalized rows (no game_date; running list)."""
    report_date = ""
    ts = payload.get("timestamp", "")
    m = re.match(r"(\d{4}-\d{2}-\d{2})", ts)
    if m:
        report_date = m.group(1)
    rows = []
    for team_block in payload.get("injuries", []):
        team = normalize_team(team_block.get("displayName", ""))
        for inj in team_block.get("injuries", []):
            det = inj.get("details") or {}
            bits = [det.get("side"), det.get("type")]
            reason = " ".join(b for b in bits if b)
            if det.get("detail") and det["detail"] != reason:
                reason = f"{reason} ({det['detail']})" if reason \
                    else det["detail"]
            if not reason:
                reason = (inj.get("shortComment") or "").strip()
            rows.append({
                "report_date": report_date,
                "game_date": "",
                "team": team,
                "player": (inj.get("athlete") or {}).get("displayName", ""),
                "status": inj.get("status", ""),
                "reason": reason,
            })
    return rows


# ---------------------------------------------------------------- main -----
def save_raw(stamp, source, ext, data):
    RAWDIR.mkdir(parents=True, exist_ok=True)
    p = RAWDIR / f"{source}_{stamp}.{ext}"
    if isinstance(data, bytes):
        p.write_bytes(data)
    else:
        p.write_text(data, encoding="utf-8")
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
            w.writerow([stamp] + [clean(r[k]) for k in
                                  ("report_date", "game_date", "team",
                                   "player", "status", "reason")] + [source])


def capture_official(sess, stamp):
    url, slot_dt = find_latest_official_pdf(sess)
    if url is None:
        raise RuntimeError(f"no official PDF found in last {LOOKBACK_HOURS}h "
                           f"(pattern {PDF_BASE})")
    resp = sess.get(url, timeout=(10, 60))
    resp.raise_for_status()
    raw_path = save_raw(stamp, "wnba_official", "pdf", resp.content)
    rows, meta = parse_official_pdf(resp.content)
    label = slot_dt.strftime("%Y-%m-%d %I:%M %p ET")
    return rows, raw_path, (f"report {label}, "
                            f"{meta['not_submitted']} team-slots not yet "
                            f"submitted")


def capture_espn(sess, stamp):
    resp = sess.get(ESPN_URL, timeout=(10, 60))
    resp.raise_for_status()
    payload = resp.json()
    raw_path = save_raw(stamp, "espn", "json", resp.text)
    rows = parse_espn(payload)
    return rows, raw_path, "espn season injury list (no per-game designations)"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--force-source", choices=["official", "espn"],
                    help="skip the normal primary->fallback chain (testing)")
    args = ap.parse_args()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    sess = make_session()
    attempts = []                                  # (name, error) for report

    order = {"official": [("wnba_official", capture_official)],
             "espn": [("espn", capture_espn)],
             None: [("wnba_official", capture_official),
                    ("espn", capture_espn)]}[args.force_source]

    rows, raw_path, note, used = [], None, "", None
    for name, fn in order:
        try:
            rows, raw_path, note = fn(sess, stamp)
            used = name
            if rows:
                break                              # got data - done
            if name == "wnba_official":
                print("NOTE: official report parsed to 0 player rows; "
                      "trying fallback", file=sys.stderr)
        except Exception as e:
            attempts.append((name, f"{type(e).__name__}: {e}"))
            print(f"WARNING: {name} capture failed: {e}", file=sys.stderr)

    if used is None:
        for name, err in attempts:
            print(f"FAILED {name}: {err}", file=sys.stderr)
        sys.exit(f"{stamp}: all injury sources failed; nothing captured")

    append_log(stamp, rows, used)
    with open(LOGCSV, newline="", encoding="utf-8") as f:
        total = sum(1 for _ in csv.reader(f)) - 1
    print(f"{stamp}: {len(rows)} injury rows captured | source={used} "
          f"({note}) | raw={raw_path.relative_to(ROOT)} | "
          f"log={LOGCSV.relative_to(ROOT)} (total {total} rows)")


if __name__ == "__main__":
    main()
