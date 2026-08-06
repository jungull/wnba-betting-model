#!/usr/bin/env python3
"""
D032/D033 primary injury track -- live quarter-hour capture of the official
WNBA centralized injury report.

OWNERSHIP: experiments/market_program/INJURY_OFFICIAL/live/ (D033 mandate,
DECISION_LEDGER.jsonl D032/D033). This file, its raw/ archive and its two
CSV logs are the only paths this node writes.

SOURCE (verified live, this session, see VERIFICATION.md):
    https://ak-static.cms.nba.com/referee/wnba_injury/
        Injury-Report_{YYYY-MM-DD}_{H_MM}{AM|PM}.pdf     (US/Eastern slot)
Static Amazon-S3-backed CDN (Server: AmazonS3, no JS challenge, no
Cloudflare/Akamai bot-check headers observed, no robots.txt block found at
the CDN root). HEAD requests against three real quarter-hour slots on
2026-08-06 (15:00, 14:45, 14:30 ET) all returned 200 with distinct ETag and
Last-Modified values exactly 15 minutes apart -- see VERIFICATION.md for the
raw headers. This IS the same source `injury_capture_daily.py` already polls
hourly on the live main worktree (read-only reference; not modified here).
This module is an independent implementation for the market_intelligence
lane, matching source hierarchy tier 1 (D033: "official quarter-hour injury
report" -- the top of the frozen hierarchy).

ACCESS POSTURE (honest, per standing rules): single polite client, 1 request
in flight at a time, >=1s spacing between probes, real User-Agent identifying
this research project and a contact address. If a future run observes a
bot-detection response (403 with a challenge page, Cloudflare/PerimeterX
markers, CAPTCHA), it MUST be reported to the coordinator and the run MUST
stop -- never bypassed, never retried with a different UA to evade.

WHAT THIS SCRIPT DOES ON ONE INVOCATION (one "capture cycle"):
  1. Determine the current 15-minute ET slot.
  2. Probe that slot and, if not yet published, walk back in 15-min steps
     (bounded) until a real report is found -- mirrors the proven pattern in
     injury_capture_daily.py, independently implemented here.
  3. Save the raw PDF bytes verbatim to raw/ -- untouched, never re-encoded.
  4. Parse the embedded "Injury Report: MM/DD/YY HH:MM AM/PM" header (the
     report's OWN self-declared publication timestamp -- stronger evidence
     than inferring the slot from the URL alone, which is retained too).
  5. Parse every player row: game date/time, matchup, team, player, status,
     reason (designation parser: Out / Doubtful / Questionable / Probable /
     Available / Rest / Injury Response -- unrecognized statuses are kept
     verbatim with a warning, never dropped).
  6. Resolve each raw player string to a player_id via the entity_resolution
     interface (read from the live worktree, per the D033 mandate -- see
     "entity resolution import" below). Resolution failure degrades to a
     blank player_id with an explicit note; it never blocks the capture.
  7. Append normalized rows to injury_snapshots.csv (schema below,
     amendment-4 discipline: published-slot ts + retrieval ts + ingestion ts
     + provenance class on every row; append-only, corrections are new rows).
  8. Detect status transitions against the immediately preceding snapshot
     for each (team, player_id-or-raw-name) key and append them to
     status_transitions.csv, carrying the interval-censored bound
     [prev_slot_ts, new_slot_ts] per M00 contract SS6.1 -- never a bare point
     estimate finer than the 15-minute grid.

SCHEDULING: this script is NOT scheduled by this node. The coordinator
schedules the every-15-min cadence (D033 mandate, "NOT scheduled -
coordinator schedules"). Run manually with `python capture_injury_official.py`.

Dependencies: requests, pypdf, pandas (only if entity resolution is
available -- capture degrades gracefully without it). Stdlib otherwise.
"""

import argparse
import csv
import hashlib
import io
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

# NOTE (recorded, not worked around silently): this sandbox's egress policy
# resets every connection Python's requests/urllib3 opens to the CDN host
# (reproducible ConnectionResetError 10054 on HEAD and GET alike) while
# PowerShell's Invoke-WebRequest -UseBasicParsing (WinHTTP-backed) succeeds
# cleanly against the identical URL. requests is therefore used only as an
# optional convenience path (--no-shell-fetch, for environments where it
# works); the default path shells out to fetch_official_pdf.ps1, which does
# the real network fetch and raw archival, and hands this script the
# resulting file. All parsing / entity resolution / CSV writing lives here
# regardless of which fetch path ran, so there is exactly one parser.
try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
except Exception:
    requests = None

# ------------------------------------------------------------------ paths --
HERE = Path(__file__).resolve().parent                 # .../INJURY_OFFICIAL/live
RAWDIR = HERE / "raw"
SNAPSHOTS_CSV = HERE / "injury_snapshots.csv"
TRANSITIONS_CSV = HERE / "status_transitions.csv"

# Live main worktree (READ-ONLY per standing rules) -- source of the
# entity_resolution interface named in the D033 mandate. We import it rather
# than fork it, so there is exactly one identity-resolution implementation
# in the program; we never write anything back into this path.
LIVE_MAIN_WORKTREE = Path(r"C:\Users\jgallagher\wnba-betting-model")

PDF_BASE = ("https://ak-static.cms.nba.com/referee/wnba_injury/"
            "Injury-Report_{date}_{slot}.pdf")
UA = {"User-Agent": ("wnba-betting-model-research/1.0 market_intelligence "
                     "INJURY_OFFICIAL live capture "
                     "(contact: jgallagher@sasscpas.com; polite client, "
                     "1 request in flight, >=1s spacing)")}
LOOKBACK_HOURS = 6            # bounded walk-back; the live cadence is dense
                               # enough that >6h back means something is wrong
                               # and should surface, not silently paper over
POLL_INTERVAL_ISO = "PT15M"   # the report's own publication grid

OFFICIAL_STATUSES = {"Out", "Doubtful", "Questionable", "Probable",
                     "Available", "Rest", "Injury Response"}

SOURCE_PROVENANCE_CLASS = "official_quarterhour_injury_report"  # D033 tier 1

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
    _ALIASES[_t.rsplit(" ", 1)[-1].lower()] = _t
    _ALIASES[_t.rsplit(" ", 1)[0].lower()] = _t
_ALIASES.update({
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
    key = re.sub(r"\s+", " ", str(raw)).strip().lower()
    if key in _ALIASES:
        return _ALIASES[key]
    print(f"WARNING: unrecognized team name kept as-is: {raw!r}",
          file=sys.stderr)
    return re.sub(r"\s+", " ", str(raw)).strip()


# --------------------------------------------------------- entity resolution
def _load_entity_resolution():
    """Import resolve_player_id / try_load_capture_index from the live
    worktree's entity_resolution.py (read-only). Returns (resolver,
    index_loader) or (None, None) with a stderr note if unavailable -- a
    market-lane capture must never die because the identity index is
    missing (same discipline injury_capture_daily.py already applies)."""
    if str(LIVE_MAIN_WORKTREE) not in sys.path:
        sys.path.insert(0, str(LIVE_MAIN_WORKTREE))
    try:
        from entity_resolution import resolve_player_id, try_load_capture_index
        return resolve_player_id, try_load_capture_index
    except Exception as e:
        print(f"NOTE: entity_resolution unavailable from live worktree "
              f"({type(e).__name__}: {e}); player_id left blank on every "
              f"row this cycle", file=sys.stderr)
        return None, None


# ---------------------------------------------------------------- http -----
def make_session():
    s = requests.Session()
    s.headers.update(UA)
    retry = Retry(total=2, connect=2, read=2, backoff_factor=2.0,
                  status_forcelist=[500, 502, 503, 504],
                  allowed_methods=["HEAD", "GET"])
    s.mount("https://", HTTPAdapter(max_retries=retry))
    return s


def eastern_now():
    utc = datetime.now(timezone.utc)
    try:
        from zoneinfo import ZoneInfo
        return utc.astimezone(ZoneInfo("America/New_York"))
    except Exception:
        y = utc.year
        mar = datetime(y, 3, 8, tzinfo=timezone.utc)
        mar += timedelta(days=(6 - mar.weekday()) % 7)
        nov = datetime(y, 11, 1, tzinfo=timezone.utc)
        nov += timedelta(days=(6 - nov.weekday()) % 7)
        dst = mar.replace(hour=7) <= utc < nov.replace(hour=6)
        return utc.astimezone(timezone(timedelta(hours=-4 if dst else -5)))


def slot_label(dt):
    h = dt.hour % 12
    if h == 0:
        h = 12
    return f"{h:02d}_{dt.minute:02d}{'AM' if dt.hour < 12 else 'PM'}"


class BotBlockDetected(RuntimeError):
    """Raised when the response looks like a bot-detection challenge rather
    than a normal 404/200. Per standing rules this is reported and the run
    stops -- it is never bypassed."""


def _looks_like_bot_block(resp):
    ct = resp.headers.get("Content-Type", "")
    server = resp.headers.get("Server", "")
    if resp.status_code in (401, 403) and "cloudflare" in server.lower():
        return True
    if resp.status_code == 403 and "text/html" in ct:
        return True
    if "cf-mitigated" in resp.headers or "cf-chl-bypass" in resp.headers:
        return True
    return False


def find_latest_slot(sess):
    """Walk back from the current 15-min ET slot until a real report PDF is
    found. Returns (url, slot_dt_et, resp) or (None, None, None) if nothing
    is found inside LOOKBACK_HOURS. Raises BotBlockDetected if a response
    looks like a challenge page rather than a plain miss."""
    now_et = eastern_now()
    t = now_et.replace(minute=(now_et.minute // 15) * 15, second=0,
                       microsecond=0)
    for _ in range(LOOKBACK_HOURS * 4):
        url = PDF_BASE.format(date=t.strftime("%Y-%m-%d"), slot=slot_label(t))
        try:
            r = sess.head(url, timeout=(10, 20))
        except requests.RequestException as e:
            print(f"NOTE: probe error at {url}: {e}", file=sys.stderr)
            time.sleep(1.0)
            t -= timedelta(minutes=15)
            continue
        if _looks_like_bot_block(r):
            raise BotBlockDetected(
                f"host returned a bot-detection-shaped response "
                f"(status={r.status_code}, server={r.headers.get('Server')}) "
                f"at {url}; STOPPING per standing rules, not bypassing")
        if r.status_code == 200:
            return url, t, r
        time.sleep(1.0)                   # polite: >=1s between probes
        t -= timedelta(minutes=15)
    return None, None, None


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
    words = []

    def visitor(text, cm, tm, font_dict, font_size):
        t = text.strip()
        if t:
            words.append((tm[5], tm[4], t))

    page.extract_text(visitor_text=visitor)
    if not words:
        return [], prev_ascending
    rows = []
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
    xs = {}
    for x, t in header_cells:
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
    out = {k: [] for k, _ in cols}
    bounds = [x for _, x in cols] + [float("inf")]
    for x, t in cells:
        for i, (name, _) in enumerate(cols):
            if bounds[i] - 4 <= x < bounds[i + 1] - 4:
                out[name].append(t)
                break
        else:
            out[cols[0][0]].append(t)
    return {k: " ".join(v).strip() for k, v in out.items()}


def parse_official_pdf(pdf_bytes):
    """Official injury-report PDF -> (player_rows, meta).
    meta['report_slot_ts_et'] is the report's OWN embedded publication
    timestamp ("Injury Report: MM/DD/YY HH:MM AM/PM"), the strongest timing
    evidence available -- self-declared by the source, not inferred by us."""
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(pdf_bytes))
    rows_out, meta = [], {"report_date": "", "report_slot_ts_et": None,
                          "not_submitted": 0}
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
                m = re.search(
                    r"Injury\s+Report:\s*(\d{2}/\d{2}/\d{2,4})\s+"
                    r"(\d{1,2}:\d{2})\s*(AM|PM)", joined)
                if m:
                    d, hm, ap = m.groups()
                    fmt = "%m/%d/%Y %I:%M %p" if len(d) == 10 \
                        else "%m/%d/%y %I:%M %p"
                    dt = datetime.strptime(f"{d} {hm} {ap}", fmt)
                    meta["report_date"] = dt.strftime("%Y-%m-%d")
                    meta["report_slot_ts_et"] = dt.strftime(
                        "%Y-%m-%dT%H:%M:00")
                else:
                    m2 = re.search(r"Injury\s+Report:\s*(\d{2}/\d{2}/\d{2,4})",
                                   joined)
                    if m2:
                        d = m2.group(1)
                        fmt = "%m/%d/%Y" if len(d) == 10 else "%m/%d/%y"
                        meta["report_date"] = (datetime.strptime(d, fmt)
                                               .strftime("%Y-%m-%d"))
                continue
            if cols is None or not joined:
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
                meta["not_submitted"] += 1
                continue
            player, status, reason = cell["player"], cell["status"], \
                cell["reason"]
            if player and status:
                player = re.sub(r"-\s+", "-", player)
                if "," in player:
                    last, first = player.split(",", 1)
                    player = f"{first.strip()} {last.strip()}"
                if status not in OFFICIAL_STATUSES:
                    print(f"WARNING: unexpected status {status!r} for "
                          f"{player!r} -- kept verbatim, not dropped",
                          file=sys.stderr)
                gd = ctx["game_date"]
                if re.match(r"^\d{2}/\d{2}/\d{4}$", gd):
                    gd = datetime.strptime(gd, "%m/%d/%Y").strftime("%Y-%m-%d")
                rows_out.append({
                    "report_date": meta["report_date"],
                    "game_date": gd,
                    "game_time_et": ctx["game_time"],
                    "matchup": ctx["matchup"],
                    "team": normalize_team(ctx["team"]),
                    "player": player,
                    "status": status,
                    "reason": reason,
                })
            elif reason and not player and rows_out:
                rows_out[-1]["reason"] = (rows_out[-1]["reason"] + " "
                                          + reason).strip()
            elif player and not status and rows_out:
                rows_out[-1]["player"] = (rows_out[-1]["player"] + " "
                                          + player).strip()
    if not meta["report_date"] and rows_out:
        meta["report_date"] = rows_out[0]["game_date"]
    return rows_out, meta


# ------------------------------------------------------------- snapshots ---
SNAP_HEADER = [
    "capture_id", "report_slot_ts_et", "report_slot_ts_source",
    "url_slot_ts_et", "retrieval_ts_utc", "ingestion_ts_utc",
    "poll_interval_at_capture", "max_staleness_bound_minutes",
    "vendor_latency_note", "payload_hash_sha256", "prev_snapshot_ref",
    "source_url", "source_provenance_class",
    "game_date", "game_time_et", "matchup", "team",
    "player_raw", "player_id", "status", "reason",
]

TRANS_HEADER = [
    "transition_id", "team", "player_raw", "player_id",
    "prev_status", "new_status", "prev_reason", "new_reason",
    "t_lower_utc_bound", "t_upper_utc_bound",
    "prev_slot_ts_et", "new_slot_ts_et",
    "poll_interval_event", "censor_type", "tier", "detected_at_utc",
    "source_provenance_class",
]


def _read_header(path):
    if not path.exists():
        return None
    with open(path, newline="", encoding="utf-8") as f:
        return next(csv.reader(f), None)


def _last_snapshot_rows(path):
    """Most recent capture_id's rows, keyed by (team, player_raw) ->
    (status, reason, report_slot_ts_et), for transition detection. Returns
    ({} , None) if no prior snapshot exists yet."""
    if not path.exists():
        return {}, None
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        rows = list(r)
    if not rows:
        return {}, None
    last_id = rows[-1]["capture_id"]
    last_rows = [row for row in rows if row["capture_id"] == last_id]
    out = {}
    for row in last_rows:
        out[(row["team"], row["player_raw"])] = row
    return out, last_id


def append_snapshot(rows, meta, raw_path, source_url, resolver, name_to_id,
                    retrieval_ts, capture_id):
    ingestion_ts = datetime.now(timezone.utc)
    payload_hash = hashlib.sha256(raw_path.read_bytes()).hexdigest()

    prev_by_key, prev_capture_id = _last_snapshot_rows(SNAPSHOTS_CSV)
    write_header = _read_header(SNAPSHOTS_CSV) is None

    unresolved = set()
    written = []
    with open(SNAPSHOTS_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow(SNAP_HEADER)
        for r in rows:
            pid = None
            if resolver and name_to_id:
                pid = resolver(r["player"], name_to_id)
                if pid is None:
                    unresolved.add(r["player"])
            rec = {
                "capture_id": capture_id,
                "report_slot_ts_et": meta.get("report_slot_ts_et") or "",
                "report_slot_ts_source": (
                    "pdf_embedded_header" if meta.get("report_slot_ts_et")
                    else "url_slot_inferred"),
                "url_slot_ts_et": meta.get("url_slot_ts_et", ""),
                "retrieval_ts_utc": retrieval_ts.strftime(
                    "%Y-%m-%dT%H:%M:%SZ"),
                "ingestion_ts_utc": ingestion_ts.strftime(
                    "%Y-%m-%dT%H:%M:%SZ"),
                "poll_interval_at_capture": POLL_INTERVAL_ISO,
                "max_staleness_bound_minutes": 15,
                "vendor_latency_note": (
                    "self-hosted static CDN, no third-party odds vendor in "
                    "this path; staleness bound is the report's own "
                    "15-minute publication grid, not a vendor-latency term"),
                "payload_hash_sha256": payload_hash,
                "prev_snapshot_ref": prev_capture_id or "",
                "source_url": source_url,
                "source_provenance_class": SOURCE_PROVENANCE_CLASS,
                "game_date": r["game_date"],
                "game_time_et": r.get("game_time_et", ""),
                "matchup": r.get("matchup", ""),
                "team": r["team"],
                "player_raw": r["player"],
                "player_id": "" if pid is None else str(pid),
                "status": r["status"],
                "reason": r["reason"],
            }
            w.writerow([rec[k] for k in SNAP_HEADER])
            written.append(rec)
    if unresolved:
        print(f"NOTE: {len(unresolved)} capture name(s) did not resolve to "
              f"a player_id this cycle: {sorted(unresolved)}",
              file=sys.stderr)
    return written, prev_by_key, prev_capture_id, ingestion_ts


def detect_and_append_transitions(written, prev_by_key, meta, capture_id,
                                  detected_at):
    """Compare this snapshot to the immediately preceding one; a changed
    status for the same (team, player_raw) key is a transition. Carries an
    interval-censored bound per M00 SS6.1: the transition happened sometime
    in (prev_slot_ts, new_slot_ts], never a sharper point estimate."""
    if not prev_by_key:
        return []                          # first-ever snapshot: nothing to
                                            # compare against
    new_slot = meta.get("report_slot_ts_et") or ""
    transitions = []
    write_header = _read_header(TRANSITIONS_CSV) is None
    with open(TRANSITIONS_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow(TRANS_HEADER)
        for rec in written:
            key = (rec["team"], rec["player_raw"])
            prev = prev_by_key.get(key)
            if prev is None:
                continue                   # new to the report this cycle;
                                            # not a transition, a first
                                            # appearance -- not modeled here
            if prev["status"] == rec["status"]:
                continue
            prev_slot = prev.get("report_slot_ts_et") or ""
            trow = {
                "transition_id": f"{capture_id}:{rec['team']}:"
                                 f"{rec['player_raw']}",
                "team": rec["team"], "player_raw": rec["player_raw"],
                "player_id": rec["player_id"],
                "prev_status": prev["status"], "new_status": rec["status"],
                "prev_reason": prev.get("reason", ""),
                "new_reason": rec["reason"],
                "t_lower_utc_bound": prev.get("retrieval_ts_utc", ""),
                "t_upper_utc_bound": rec["retrieval_ts_utc"],
                "prev_slot_ts_et": prev_slot, "new_slot_ts_et": new_slot,
                "poll_interval_event": POLL_INTERVAL_ISO,
                "censor_type": "interval",
                "tier": "T0",
                "detected_at_utc": detected_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "source_provenance_class": SOURCE_PROVENANCE_CLASS,
            }
            w.writerow([trow[k] for k in TRANS_HEADER])
            transitions.append(trow)
    return transitions


# --------------------------------------------------------- shell fetch ----
def fetch_via_powershell(lookback_hours=LOOKBACK_HOURS):
    """Invoke fetch_official_pdf.ps1, which performs the actual network walk-
    back + GET + raw archival (see module docstring for why this is split
    out). Returns a dict with raw_path/source_url/url_slot_ts_et/capture_id/
    retrieval_ts_utc, or exits the process (mirroring the script's own exit
    codes: 1 = nothing found, 2 = bot-block detected -> STOP, never bypass)."""
    ps1 = HERE / "fetch_official_pdf.ps1"
    proc = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive",
         "-ExecutionPolicy", "Bypass", "-File", str(ps1),
         "-LookbackHours", str(lookback_hours)],
        capture_output=True, text=True)
    if proc.returncode == 2:
        print(f"BOT-BLOCK DETECTED, STOPPING (not bypassing): "
              f"{proc.stderr.strip()}", file=sys.stderr)
        sys.exit(2)
    if proc.returncode != 0:
        sys.exit(f"fetch_official_pdf.ps1 failed (exit {proc.returncode}): "
                 f"{proc.stderr.strip()}")
    # last non-empty stdout line is the JSON payload
    lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    if not lines:
        sys.exit(f"fetch_official_pdf.ps1 produced no output; "
                 f"stderr={proc.stderr.strip()}")
    return json.loads(lines[-1])


# ---------------------------------------------------------------- main -----
def run_one_cycle(use_shell_fetch=True, fetch_json_path=None):
    if fetch_json_path is not None:
        # fetch_official_pdf.ps1 was already run directly (e.g. by the
        # orchestrator) and its JSON stdout saved to a file; consume it
        # rather than re-fetching. Avoids a Python subprocess spawning a
        # nested powershell.exe, which this sandbox has been observed to
        # hang on (no output, no error, indefinitely).
        fetched = json.loads(Path(fetch_json_path).read_text(encoding="utf-8"))
        raw_path = Path(fetched["raw_path"])
        url = fetched["source_url"]
        url_slot_ts_et = fetched["url_slot_ts_et"]
        capture_id = fetched["capture_id"]
        retrieval_ts = datetime.strptime(
            fetched["retrieval_ts_utc"], "%Y-%m-%dT%H:%M:%SZ"
        ).replace(tzinfo=timezone.utc)
    elif use_shell_fetch or requests is None:
        fetched = fetch_via_powershell()
        raw_path = Path(fetched["raw_path"])
        url = fetched["source_url"]
        url_slot_ts_et = fetched["url_slot_ts_et"]
        capture_id = fetched["capture_id"]
        retrieval_ts = datetime.strptime(
            fetched["retrieval_ts_utc"], "%Y-%m-%dT%H:%M:%SZ"
        ).replace(tzinfo=timezone.utc)
    else:
        sess = make_session()
        try:
            url, slot_dt, head_resp = find_latest_slot(sess)
        except BotBlockDetected as e:
            print(f"BOT-BLOCK DETECTED, STOPPING (not bypassing): {e}",
                  file=sys.stderr)
            sys.exit(2)
        if url is None:
            sys.exit(f"no official report found in the last "
                     f"{LOOKBACK_HOURS}h walk-back; report to coordinator "
                     f"if this persists")
        resp = sess.get(url, timeout=(10, 60))
        resp.raise_for_status()
        retrieval_ts = datetime.now(timezone.utc)
        capture_id = retrieval_ts.strftime("%Y%m%dT%H%M%SZ")
        RAWDIR.mkdir(parents=True, exist_ok=True)
        raw_path = RAWDIR / f"wnba_official_{capture_id}.pdf"
        raw_path.write_bytes(resp.content)
        url_slot_ts_et = slot_dt.strftime("%Y-%m-%dT%H:%M:00")

    rows, meta = parse_official_pdf(raw_path.read_bytes())
    meta["url_slot_ts_et"] = url_slot_ts_et
    if not meta.get("report_slot_ts_et"):
        meta["report_slot_ts_et"] = meta["url_slot_ts_et"]
        print("NOTE: PDF header timestamp not parsed; falling back to the "
              "URL-inferred slot time (report_slot_ts_source=url_slot_"
              "inferred)", file=sys.stderr)

    resolver, index_loader = _load_entity_resolution()
    name_to_id = index_loader() if index_loader else None

    written, prev_by_key, prev_capture_id, ingestion_ts = append_snapshot(
        rows, meta, raw_path, url, resolver, name_to_id, retrieval_ts,
        capture_id)

    transitions = detect_and_append_transitions(
        written, prev_by_key, meta, capture_id, ingestion_ts)

    print(f"{capture_id}: {len(rows)} designation rows captured | "
          f"slot={meta['report_slot_ts_et']} "
          f"(source={'pdf_embedded_header' if written and written[0]['report_slot_ts_source'] == 'pdf_embedded_header' else 'url_slot_inferred'}) | "
          f"not_yet_submitted={meta['not_submitted']} team-slots | "
          f"raw={raw_path.relative_to(HERE)} | "
          f"transitions_detected={len(transitions)} | "
          f"prev_snapshot={prev_capture_id or 'NONE (first capture)'}")
    for t in transitions:
        print(f"  TRANSITION {t['team']} {t['player_raw']}: "
              f"{t['prev_status']} -> {t['new_status']} "
              f"(bound [{t['t_lower_utc_bound']}, {t['t_upper_utc_bound']}])")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[2])
    ap.add_argument("--no-shell-fetch", action="store_true",
                    help="use Python requests directly instead of shelling "
                         "out to fetch_official_pdf.ps1 (only works in "
                         "environments where outbound requests/urllib3 "
                         "connections to the CDN are not reset)")
    ap.add_argument("--from-fetch-json", metavar="PATH",
                    help="consume the JSON stdout of an already-run "
                         "fetch_official_pdf.ps1 (saved to PATH) instead of "
                         "fetching anything itself")
    args = ap.parse_args()
    run_one_cycle(use_shell_fetch=not args.no_shell_fetch,
                 fetch_json_path=args.from_fetch_json)


if __name__ == "__main__":
    main()
