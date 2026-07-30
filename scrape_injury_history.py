"""Recover historical WNBA player injury/absence/transaction data, 2021-01-01 -> today.

Sources (chosen 2026-07-30 after evaluating alternatives -- see project_docs/INJURY_HISTORY.md):

1. ESPN game summaries (site.api.espn.com, the public JSON API behind espn.com):
   per-game "did not play" entries with reasons (e.g. "RIGHT ANKLE INJURY",
   "COACH'S DECISION") for every WNBA regular-season and playoff game.
   This is the per-game injury/absence signal.

2. Basketball-Reference WNBA transaction pages
   (basketball-reference.com/wnba/years/<YYYY>_transactions.html):
   the league transaction wire -- signings, waivers, trades, drafts and
   contract suspensions/activations. robots.txt allows /wnba/ and asks for
   Crawl-delay: 3, which this script honors (3.5 s).

   NOTE: prosportstransactions.com (the original first choice, which has a
   dedicated "missed games due to injury" archive) sits behind a Cloudflare
   managed challenge that 403s every scripted client regardless of
   User-Agent. It was NOT scraped; do not add bypass tooling.

Behavior:
  * Every raw HTTP payload is saved under data/injury_history/raw/ first;
    parsing runs offline from those files and is re-runnable.
  * Resumable: raw files that already exist are not re-fetched (except the
    current season's scoreboard, which is refreshed so new games appear).
  * Polite: sequential, honest User-Agent, 1.6 s between ESPN requests,
    3.5 s between Basketball-Reference requests.

Output CSV (UTF-8): data/injury_history/injury_history.csv with columns
  date, team, player_acquired, player_relinquished, notes, category, source_page

Usage:
  python scrape_injury_history.py             # fetch (resumable) + parse
  python scrape_injury_history.py --fetch-only
  python scrape_injury_history.py --parse-only   # offline re-parse of raw/
"""
from __future__ import annotations

import argparse
import csv
import html as htmllib
import json
import re
import sys
import time
import unicodedata
from datetime import date, datetime
from pathlib import Path

import requests

try:  # exact Eastern dates if tzdata is available; else fixed UTC-4 (see eastern_date)
    from zoneinfo import ZoneInfo
    _ET = ZoneInfo("America/New_York")
except Exception:  # pragma: no cover
    _ET = None

# ----------------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------------
REPO = Path(__file__).resolve().parent
OUT_DIR = REPO / "data" / "injury_history"
RAW_DIR = OUT_DIR / "raw"
CSV_PATH = OUT_DIR / "injury_history.csv"
MANIFEST = RAW_DIR / "manifest.jsonl"

USER_AGENT = (
    "wnba-injury-history-research/1.0 (personal non-commercial research; "
    "python-requests; polite: sequential, rate-limited)"
)
ESPN_DELAY = 1.6   # seconds between ESPN API requests
BBREF_DELAY = 3.5  # seconds between Basketball-Reference requests (robots Crawl-delay: 3)

TODAY = date.today()
FIRST_SEASON = 2021
CURRENT_SEASON = TODAY.year

# scoreboard enumeration windows (games only happen Apr-Nov)
def season_window(year: int) -> tuple[str, str]:
    end = f"{year}1115"
    if year == TODAY.year:
        end = TODAY.strftime("%Y%m%d")
    return f"{year}0401", end

# ESPN team abbreviation -> stats.nba.com TEAM_ABBREVIATION (as in wnba_gamelog_*.parquet)
ESPN_TO_STATS = {
    "ATL": "ATL", "CHI": "CHI", "CON": "CON", "CONN": "CON", "DAL": "DAL",
    "IND": "IND", "LA": "LAS", "LV": "LVA", "MIN": "MIN", "NY": "NYL",
    "PHX": "PHO", "SEA": "SEA", "WSH": "WAS", "GS": "GSV",
    "TOR": "TOR", "POR": "POR",  # 2026 expansion
}
# Basketball-Reference team names -> stats abbreviation
BBREF_TEAM_TO_STATS = {
    "Atlanta Dream": "ATL", "Chicago Sky": "CHI", "Connecticut Sun": "CON",
    "Dallas Wings": "DAL", "Indiana Fever": "IND", "Las Vegas Aces": "LVA",
    "Los Angeles Sparks": "LAS", "Minnesota Lynx": "MIN",
    "New York Liberty": "NYL", "Phoenix Mercury": "PHO", "Seattle Storm": "SEA",
    "Washington Mystics": "WAS", "Golden State Valkyries": "GSV",
    "Toronto Tempo": "TOR", "Portland Fire": "POR",
}

INJURY_REASON_PAT = re.compile(
    r"injur|ill\b|illness|sore|strain|sprain|tear|torn|acl\b|mcl\b|achill|concuss|"
    r"protocol|surg|fract|broken|knee|ankle|foot|hip\b|back\b|shoulder|wrist|hand\b|"
    r"leg\b|calf|hamstring|quad|groin|toe\b|heel|elbow|neck|finger|thumb|eye\b|nose|"
    r"head\b|rib\b|abdom|pelvi|plantar|meniscus|health|covid|medical|rehab|recovery|"
    r"adductor|patell|contus|bruise|spasm|tendin|tendon|shin\b|fibula|tibia|lisfranc|"
    r"jaw|facial|dental|appendec|oblique|bicep|tricep|lumbar|cervical|migraine|"
    r"vertigo|nasal|orbital|cartilage|labrum|ligament|sternum|collarbone|clavicle",
    re.I,
)

CSV_COLUMNS = ["date", "team", "player_acquired", "player_relinquished",
               "notes", "category", "source_page"]


def eastern_date(iso_utc: str) -> str:
    """ESPN event timestamps are UTC ('2024-05-04T00:00Z'); games are dated in US
    Eastern. Convert; if no tz database is available, subtract 4h (the WNBA
    calendar Apr-Nov is EDT; a 1h DST error never crosses midnight for real
    tipoff times)."""
    try:
        dt = datetime.strptime(iso_utc[:16], "%Y-%m-%dT%H:%M")
    except ValueError:
        return iso_utc[:10]
    if _ET is not None:
        from datetime import timezone
        return dt.replace(tzinfo=timezone.utc).astimezone(_ET).date().isoformat()
    from datetime import timedelta
    return (dt - timedelta(hours=4)).date().isoformat()

# ----------------------------------------------------------------------------
# Fetch layer
# ----------------------------------------------------------------------------
session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"})


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def record_manifest(fname: str, url: str, status: int, nbytes: int) -> None:
    with open(MANIFEST, "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "file": fname, "url": url, "status": status, "bytes": nbytes,
            "fetched_at": datetime.now().isoformat(timespec="seconds"),
        }) + "\n")


def fetch_to_file(url: str, path: Path, delay: float, force: bool = False) -> bool:
    """Fetch url -> path unless it already exists. Returns True if fetched."""
    if path.exists() and not force:
        return False
    time.sleep(delay)
    r = session.get(url, timeout=60)
    if r.status_code != 200:
        log(f"  WARN {r.status_code} for {url}")
        record_manifest(path.name, url, r.status_code, len(r.content))
        return False
    path.write_bytes(r.content)
    record_manifest(path.name, url, r.status_code, len(r.content))
    return True


def fetch_bbref() -> None:
    for yr in range(FIRST_SEASON, CURRENT_SEASON + 1):
        url = f"https://www.basketball-reference.com/wnba/years/{yr}_transactions.html"
        path = RAW_DIR / f"bbref_transactions_{yr}.html"
        force = (yr == CURRENT_SEASON) and _stale(path)
        if fetch_to_file(url, path, BBREF_DELAY, force=force):
            log(f"bbref {yr}: fetched ({path.stat().st_size} bytes)")
        else:
            log(f"bbref {yr}: cached")


def _stale(path: Path, hours: float = 20.0) -> bool:
    if not path.exists():
        return True
    age = time.time() - path.stat().st_mtime
    return age > hours * 3600


def fetch_scoreboards() -> None:
    for yr in range(FIRST_SEASON, CURRENT_SEASON + 1):
        beg, end = season_window(yr)
        url = ("https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/"
               f"scoreboard?dates={beg}-{end}&limit=1000")
        path = RAW_DIR / f"espn_scoreboard_{yr}.json"
        force = (yr == CURRENT_SEASON) and _stale(path)
        if fetch_to_file(url, path, ESPN_DELAY, force=force):
            log(f"scoreboard {yr}: fetched")
        else:
            log(f"scoreboard {yr}: cached")


def load_games() -> list[dict]:
    """Enumerate completed regular-season + playoff games between real franchises."""
    games = []
    for yr in range(FIRST_SEASON, CURRENT_SEASON + 1):
        path = RAW_DIR / f"espn_scoreboard_{yr}.json"
        if not path.exists():
            continue
        j = json.loads(path.read_text(encoding="utf-8"))
        for e in j.get("events", []):
            stype = e.get("season", {}).get("type")
            if stype not in (2, 3):          # 2 = regular season, 3 = playoffs
                continue
            comp = (e.get("competitions") or [{}])[0]
            status = comp.get("status", {}).get("type", {}).get("name", "")
            if status != "STATUS_FINAL":
                continue
            teams = {}
            ok = True
            for c in comp.get("competitors", []):
                ab = c.get("team", {}).get("abbreviation", "")
                if ab not in ESPN_TO_STATS:   # drops All-Star / USA exhibitions
                    ok = False
                    break
                teams[c.get("homeAway", "?")] = ESPN_TO_STATS[ab]
            if not ok or len(teams) != 2:
                continue
            notes = " ".join(
                n.get("headline", "") for n in comp.get("notes", []) if isinstance(n, dict)
            )
            games.append({
                "event_id": str(e["id"]),
                "date": eastern_date(e.get("date", "")),
                "season": yr,
                "season_type": stype,
                "home": teams.get("home"), "away": teams.get("away"),
                "is_cup_final": (
                    "commissioner's cup championship" in notes.lower()
                    # 2021: ESPN gave the final no distinct headline; it is the
                    # lone regular-season-typed game inside the Olympic break
                    # (Aug 12, 2021, CON @ SEA in Phoenix).
                    or ("commissioner's cup" in notes.lower()
                        and eastern_date(e.get("date", "")) == "2021-08-12")
                ),
            })
    games.sort(key=lambda g: (g["date"], g["event_id"]))
    return games


def fetch_summaries(games: list[dict]) -> None:
    todo = [g for g in games if not (RAW_DIR / f"espn_summary_{g['event_id']}.json").exists()]
    log(f"summaries: {len(games)} games total, {len(todo)} to fetch "
        f"(~{len(todo) * (ESPN_DELAY + 0.4) / 60:.0f} min)")
    done = 0
    for g in todo:
        url = ("https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/"
               f"summary?event={g['event_id']}")
        path = RAW_DIR / f"espn_summary_{g['event_id']}.json"
        fetch_to_file(url, path, ESPN_DELAY)
        done += 1
        if done % 50 == 0:
            log(f"  summaries progress: {done}/{len(todo)}")
    log(f"summaries: done ({done} fetched)")


# ----------------------------------------------------------------------------
# Parse layer (offline, from raw/)
# ----------------------------------------------------------------------------
def clean_name(name: str) -> str:
    """Strip markup leftovers, bullet markers and asterisks; collapse whitespace."""
    name = htmllib.unescape(name)
    name = name.replace("•", " ").replace("*", " ").replace("\xa0", " ")
    name = re.sub(r"\s+", " ", name).strip(" .,;")
    return name


def parse_espn_dnp(games: list[dict]) -> list[dict]:
    rows = []
    idx = {g["event_id"]: g for g in games}
    missing = 0
    for g in games:
        path = RAW_DIR / f"espn_summary_{g['event_id']}.json"
        if not path.exists():
            missing += 1
            continue
        try:
            j = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            log(f"  WARN bad json {path.name}")
            continue
        seen = set()
        for tm in j.get("boxscore", {}).get("players", []):
            ab = tm.get("team", {}).get("abbreviation", "")
            team = ESPN_TO_STATS.get(ab, ab)
            for grp in tm.get("statistics", []):
                for ath in grp.get("athletes", []):
                    if not ath.get("didNotPlay"):
                        continue
                    a = ath.get("athlete", {})
                    key = (team, a.get("id") or a.get("displayName"))
                    if key in seen:
                        continue
                    seen.add(key)
                    reason = (ath.get("reason") or "").strip()
                    player = clean_name(a.get("displayName", ""))
                    if not player:
                        continue
                    if reason and INJURY_REASON_PAT.search(reason):
                        cat = "missed_game_injury"
                    elif reason:
                        cat = "missed_game_other"
                    else:
                        cat = "missed_game_unspecified"
                    note_bits = [reason] if reason else []
                    if g["season_type"] == 3:
                        note_bits.append("[playoffs]")
                    if g["is_cup_final"]:
                        note_bits.append("[commissioners-cup-final]")
                    rows.append({
                        "date": g["date"], "team": team,
                        "player_acquired": "", "player_relinquished": player,
                        "notes": " ".join(note_bits),
                        "category": cat,
                        "source_page": path.name,
                    })
    if missing:
        log(f"  WARN {missing} game summaries missing from raw/")
    return rows


# --- Basketball-Reference transactions ---------------------------------------
DATE_RE = re.compile(
    r"^(January|February|March|April|May|June|July|August|September|October|"
    r"November|December)\s+\d{1,2},\s+\d{4}$"
)
PLAYER_A_RE = re.compile(r"""<a href=["']/wnba/players/[^"']+["']>(.*?)</a>""")
TEAM_HREF_RE = re.compile(r"""<a href=["']/wnba/teams/([A-Z]{2,4})/[^"']*["']>(.*?)</a>""")
TAG_RE = re.compile(r"<[^>]+>")


def _txt(fragment: str) -> str:
    t = re.sub(r"\s+", " ", htmllib.unescape(TAG_RE.sub(" ", fragment))).strip()
    return re.sub(r"\s+([.,;])", r"\1", t)


def classify_bbref(sentence_html: str, season_page: str) -> list[dict] | None:
    """Turn one BBRef transaction sentence (HTML) into 0+ CSV rows (no date yet)."""
    text = _txt(sentence_html)
    if not text:
        return None
    players = [clean_name(p) for p in PLAYER_A_RE.findall(sentence_html)]
    # BBRef team hrefs (/wnba/teams/WAS/2021.html) already use stats-style
    # abbreviations; fall back to the display-name map if needed.
    stats_teams = []
    for abbr, disp in TEAM_HREF_RE.findall(sentence_html):
        stats_teams.append(abbr if abbr in BBREF_TEAM_TO_STATS.values()
                           else BBREF_TEAM_TO_STATS.get(clean_name(disp), abbr))
    low = text.lower()
    team0 = stats_teams[0] if stats_teams else ""

    def row(team, acq, rel, cat):
        return {"team": team, "player_acquired": acq, "player_relinquished": rel,
                "notes": text, "category": cat, "source_page": season_page}

    if " traded " in low:
        # Ignore draft-pick annotations "(<player> later selected)" -- those
        # players were not part of the trade; they arrive via 'draft' rows.
        core_html = re.sub(r"\([^()]*later selected[^()]*\)", " ", sentence_html)
        core_players = [clean_name(p) for p in PLAYER_A_RE.findall(core_html)]
        core_text = _txt(core_html)
        out_rows = []
        if stats_teams:
            actor = stats_teams[0]
            partner = stats_teams[1] if len(stats_teams) == 2 else None
            for_pos = core_text.lower().find(" for ")
            for p in core_players:
                pos = core_text.find(p)
                outgoing = for_pos == -1 or pos < for_pos
                if outgoing:
                    out_rows.append(row(actor, "", p, "trade"))
                    if partner:
                        out_rows.append(row(partner, p, "", "trade"))
                else:
                    out_rows.append(row(actor, p, "", "trade"))
                    if partner:
                        out_rows.append(row(partner, "", p, "trade"))
        return out_rows or [row(team0, "", "", "trade")]
    if "claimed" in low and "waiver" in low:
        return [row(team0, p, "", "waiver_claim") for p in players] or [row(team0, "", "", "waiver_claim")]
    if "converted" in low and "contract" in low:
        # development contract -> standard contract (2026 CBA); player stays.
        return [row(team0, p, "", "contract_conversion") for p in players]
    if "suspended the contract" in low or ("suspended" in low and "contract" in low):
        return [row(team0, "", p, "contract_suspension") for p in players] or [row(team0, "", "", "contract_suspension")]
    if "activated" in low or "unsuspended" in low or "removed the suspension" in low:
        return [row(team0, p, "", "activation") for p in players]
    if "waived" in low or "released" in low:
        return [row(team0, "", p, "waiver") for p in players]
    if "drafted" in low:
        return [row(team0, p, "", "draft") for p in players]
    if "signed" in low or "re-signed" in low:
        return [row(team0, p, "", "signing") for p in players]
    if "retire" in low:
        return [row(team0, "", p, "retirement") for p in players]
    if any(k in low for k in ("head coach", "general manager", "hired", "resigns",
                              "fired", "named", "coach")):
        return [row(team0, "", "", "front_office")]
    return [row(team0, "", "", "other")]


def parse_bbref() -> list[dict]:
    rows = []
    for yr in range(FIRST_SEASON, CURRENT_SEASON + 1):
        path = RAW_DIR / f"bbref_transactions_{yr}.html"
        if not path.exists():
            log(f"  WARN missing {path.name}")
            continue
        html = path.read_text(encoding="utf-8", errors="replace")
        page_rows = 0
        for li in re.findall(r"<li[^>]*>(.*?)</li>", html, re.S):
            # date lives in a <span> (or leading text); transactions follow in <p> blocks
            ps = re.findall(r"<p[^>]*>(.*?)</p>", li, re.S)
            head = _txt(re.split(r"<p[^>]*>", li, maxsplit=1)[0])
            if not DATE_RE.match(head):
                continue
            d = datetime.strptime(head, "%B %d, %Y").date()
            if d < date(FIRST_SEASON, 1, 1) or d > TODAY:
                continue
            for p_html in ps:
                out = classify_bbref(p_html, path.name)
                for r in out or []:
                    r["date"] = d.isoformat()
                    rows.append(r)
                    page_rows += 1
        log(f"bbref {yr}: {page_rows} rows")
    return rows


# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------
def write_csv(rows: list[dict]) -> None:
    rows.sort(key=lambda r: (r["date"], r["category"], r["team"],
                             r["player_relinquished"], r["player_acquired"]))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        w.writeheader()
        w.writerows(rows)
    log(f"wrote {len(rows)} rows -> {CSV_PATH}")
    # per-season summary
    per = {}
    for r in rows:
        yr = r["date"][:4]
        per.setdefault(yr, {"total": 0})
        per[yr]["total"] += 1
        per[yr][r["category"]] = per[yr].get(r["category"], 0) + 1
    for yr in sorted(per):
        cats = {k: v for k, v in sorted(per[yr].items()) if k != "total"}
        log(f"  {yr}: {per[yr]['total']} rows | {cats}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--fetch-only", action="store_true")
    ap.add_argument("--parse-only", action="store_true")
    args = ap.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    if not args.parse_only:
        log("=== fetch: Basketball-Reference transaction pages ===")
        fetch_bbref()
        log("=== fetch: ESPN season scoreboards ===")
        fetch_scoreboards()
        games = load_games()
        log(f"=== fetch: ESPN game summaries ({len(games)} games) ===")
        fetch_summaries(games)
    if args.fetch_only:
        return 0

    log("=== parse ===")
    games = load_games()
    rows = parse_espn_dnp(games) + parse_bbref()
    write_csv(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
