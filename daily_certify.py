#!/usr/bin/env python3
"""daily_certify.py — standing daily data certification (ROADMAP Phase 0).

"Standing daily certification (`daily_certify.py`, scheduled; failures alert,
never auto-fix)". LOCAL ONLY — reads files already on disk, never the network
(the game universe is rebuilt from the gamelog parquets rather than the
LeagueGameLog API used by audit_completeness.py; the coverage logic mirrors
that script's section 1).

Implemented now:
  1. duplicate game/player detection in refresh + repo gamelogs
  2. coverage-by-season table: pbp/misc/advanced artifact counts vs the
     gamelog game universe
  3. odds capture freshness: newest data/odds_capture/live_*.json age vs the
     schedule expectation (hourly 10:00-23:00 local, ROADMAP "Immediate
     parallel captures")
  4. injury capture freshness (2x/day baseline; hourly on game days —
     game days detected from commence_time in the newest odds snapshot)
  5. schema fingerprint drift: ordered-column-name hashes per dataset stored
     in data/certify/schema_fingerprints.json; drift WARNS and is never
     auto-accepted (rerun with --accept-schema after a reviewed change)

  6. possession reconciliation (Phase 0 / RAPM prerequisite): re-derives the
     N most recent games from raw pbp via build_possessions.process_game and
     checks possession point sums against master_team final scores exactly

  7. PBP score reconciliation (Phase 0): recompute every sampled game's final
     score from raw pbp event semantics (both eras: data/playbyplay V2,
     data/refresh_2026/pbp V3) and reconcile against (a) the pbp's own posted
     running score at every scoring checkpoint and (b) master_team finals.
     FT sequences, technicals and OREB putback chains all move the recomputed
     score, so a mis-scored event surfaces as a checkpoint divergence or a
     final mismatch; OT is handled by accumulation and reported. Daily runs
     are sampled + incremental (newest games + a deterministic day-rotating
     block that sweeps the full history every ~5 weeks); `--full` runs every
     game and writes experiments/odds_audit_ext/pbp_full_reconciliation.csv.
  8. odds stale-book detection (Phase 0): inside each recent live odds
     snapshot, flag bookmakers whose freshest last_update lags the capture
     time beyond STALE_BOOK_LAG_MIN on not-yet-commenced events; per-book
     summary over the scanned window.
  9. postponement / changed-tip-time detection (Phase 0): track each
     api event's commence_time across recent live snapshots; report every
     before -> after change and any event that vanishes pregame (the
     postpone-then-relist pattern documented in build_odds_master_extension).

Checks 7-9 run in WARN mode this session: they report and count, but a
would-be FAIL is downgraded to WARN so they never flip the overall exit code.
Promote each one later by flipping its *_FAIL_MODE switch below (one line).

Exit code: nonzero only when at least one check FAILs. WARNs alert in the
summary but do not fail the run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
CERTIFY_DIR = DATA / "certify"
FINGERPRINT_PATH = CERTIFY_DIR / "schema_fingerprints.json"

SEASONS = ["2021", "2022", "2023", "2024", "2025", "2026"]

# --- schedule expectations (ROADMAP "Immediate parallel captures") ----------
ODDS_WINDOW = (10, 23)          # hourly snapshots 10:00-23:00 local time
ODDS_PASS_LAG_MIN = 75          # one hourly slot + grace
ODDS_WARN_LAG_MIN = 240
INJ_GAMEDAY_PASS_H = 3          # hourly on game days (began 2026-07-30)
INJ_BASE_PASS_H = 14            # 2x/day baseline otherwise
INJ_FAIL_H = 26                 # a fully missed day always fails

# --- Phase-0 hook parameters (checks 7-9) -----------------------------------
PBP_RECENT_N = 8                # newest games re-reconciled every daily run
PBP_ROTATE_N = 40               # day-rotating incremental block (history swept ~37 days)
PBP_FULL_OUT = ROOT / "experiments" / "odds_audit_ext" / "pbp_full_reconciliation.csv"
STALE_BOOK_LAG_MIN = 90         # book quote older than this at capture = stale.
                                # Rationale: captures are hourly (check 3); a book
                                # >90 min behind predates the PREVIOUS snapshot
                                # entirely, so its quote is not contemporaneous at
                                # any decision cutoff (pregame events only —
                                # books legitimately suspend in-play).
STALE_PERSIST_MIN_SIGHT = 4     # persistent-stale needs >= this many sightings
STALE_SNAPSHOTS_N = 14          # newest live snapshots scanned (~one capture day)
TIP_SNAPSHOTS_N = 200           # newest live snapshots scanned for tip changes
TIP_VANISH_GRACE_MIN = 30       # pregame margin before a vanished listing alarms

# --- FAIL-mode switches for the Phase-0 hooks (checks 7-9) ------------------
# Each hook runs in WARN mode until promoted: it reports and counts, but a
# would-be FAIL is downgraded to WARN and never flips the exit code.
# To promote a hook to FAIL mode later, flip its switch to True (one line).
PBP_RECON_FAIL_MODE = False     # promote check 7 (PBP score reconciliation)
STALE_BOOK_FAIL_MODE = False    # promote check 8 (odds stale-book detection)
TIP_CHANGE_FAIL_MODE = False    # promote check 9 (postponement / tip changes)

STATUS_ORDER = {"PASS": 0, "SKIP": 0, "WARN": 1, "FAIL": 2}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def season_of_game_id(gid: str) -> str:
    """WNBA game ids: 1 0 <TT> <YY> <NNNNN> — TT 02=regular 04=playoffs,
    YY = 2-digit season year (e.g. 1022400001 -> 2024, 1042100002 -> 2021)."""
    gid = str(gid)
    if len(gid) == 10 and gid[0] == "1":
        return "20" + gid[3:5]
    return "unknown"


def parse_stamp(name: str):
    """Extract a UTC timestamp like 20260730T160001Z from a filename."""
    m = re.search(r"(\d{8}T\d{6})Z", name)
    if not m:
        return None
    return datetime.strptime(m.group(1), "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)


def newest_stamped(paths):
    stamped = [(parse_stamp(p.name), p) for p in paths]
    stamped = [(t, p) for t, p in stamped if t is not None]
    return max(stamped) if stamped else (None, None)


def artifact_ids(folder: Path, prefix: str) -> set:
    return {p.stem.split("_", 1)[1] for p in folder.glob(f"{prefix}_*.parquet")} \
        if folder.exists() else set()


def fmt_age(delta: timedelta) -> str:
    h = delta.total_seconds() / 3600.0
    return f"{h * 60:.0f} min" if h < 2 else f"{h:.1f} h"


# ---------------------------------------------------------------------------
# check 1 — duplicates in gamelogs
# ---------------------------------------------------------------------------

def check_duplicates():
    lines, status = [], "PASS"
    specs = []
    for p in sorted((DATA / "refresh_2026").glob("gamelog_team_*.parquet")):
        specs.append((p, ["GAME_ID", "TEAM_ID"], "team"))
    for p in sorted((DATA / "refresh_2026").glob("gamelog_player_*.parquet")):
        specs.append((p, ["GAME_ID", "PLAYER_ID"], "player"))
    for p in sorted(DATA.glob("wnba_gamelog_*.parquet")):
        cols = pq.read_schema(p).names
        key = ["GAME_ID", "PLAYER_ID"] if "PLAYER_ID" in cols else ["GAME_ID", "TEAM_ID"]
        specs.append((p, key, "player" if "PLAYER_ID" in cols else "team"))
    if not specs:
        return "FAIL", ["no gamelog parquet files found under data/"]
    total_dup = 0
    for p, key, kind in specs:
        df = pd.read_parquet(p, columns=key)
        n_dup = int(df.duplicated(subset=key).sum())
        if n_dup:
            total_dup += n_dup
            status = "FAIL"
            lines.append(f"FAIL {p.relative_to(ROOT)}: {n_dup} duplicate {kind} rows on {key}")
        if kind == "team":
            per_game = df.groupby("GAME_ID").size()
            odd = per_game[per_game != 2]
            if len(odd):
                status = "FAIL"
                lines.append(
                    f"FAIL {p.relative_to(ROOT)}: {len(odd)} games without exactly "
                    f"2 team rows (e.g. {odd.index[:3].tolist()})"
                )
    lines.insert(0, f"checked {len(specs)} gamelog files; duplicate rows: {total_dup}")
    return status, lines


# ---------------------------------------------------------------------------
# check 2 — coverage by season (audit_completeness.py section-1 logic, local)
# ---------------------------------------------------------------------------

def game_universe() -> pd.DataFrame:
    ids = set()
    for p in list(DATA.glob("wnba_gamelog_*.parquet")) + \
             list((DATA / "refresh_2026").glob("gamelog_*.parquet")):
        df = pd.read_parquet(p, columns=["GAME_ID"])
        ids.update(df["GAME_ID"].astype(str).str.zfill(10))
    uni = pd.DataFrame({"GAME_ID": sorted(ids)})
    uni["season"] = uni["GAME_ID"].map(season_of_game_id)
    return uni


def check_coverage():
    uni = game_universe()
    if uni.empty:
        return "FAIL", ["empty game universe — no gamelogs readable"]
    have_pbp = artifact_ids(DATA / "playbyplay", "pbp") | \
        artifact_ids(DATA / "refresh_2026" / "pbp", "pbp")
    have_misc = artifact_ids(DATA / "refresh_2026" / "misc", "misc")
    have_adv = artifact_ids(DATA / "refresh_2026" / "advanced", "advanced")
    lines = ["season | games | pbp | misc | advanced",
             "-------|-------|-----|------|---------"]
    status = "PASS"
    gaps = []
    for season, grp in uni.groupby("season"):
        ids = set(grp["GAME_ID"])
        n, np_, nm, na = len(ids), len(ids & have_pbp), len(ids & have_misc), len(ids & have_adv)
        lines.append(f"{season}   | {n:5d} | {np_:3d} | {nm:4d} | {na:8d}")
        for label, got in (("pbp", np_), ("misc", nm), ("advanced", na)):
            if got < n:
                gaps.append(f"{season}: {n - got} games missing {label}")
    if gaps:
        status = "WARN"   # backfill in flight (Phase 0 status 2026-07-30); alert, don't block
        lines += ["", "gaps (WARN - granular backfill running per Phase 0):"] + \
                 [f"  - {g}" for g in gaps[:12]]
        if len(gaps) > 12:
            lines.append(f"  ... and {len(gaps) - 12} more")
    return status, lines


# ---------------------------------------------------------------------------
# check 3 — odds capture freshness
# ---------------------------------------------------------------------------

def _expected_latest_capture(now_local: datetime) -> datetime:
    """Latest moment a capture should exist for, given the 10:00-23:00 hourly
    window: 'now' inside the window, else the most recent window close."""
    lo, hi = ODDS_WINDOW
    today_open = now_local.replace(hour=lo, minute=0, second=0, microsecond=0)
    today_close = now_local.replace(hour=hi, minute=0, second=0, microsecond=0)
    if now_local < today_open:
        return today_close - timedelta(days=1)
    return min(now_local, today_close)


def check_odds_freshness():
    files = list((DATA / "odds_capture").glob("live_*.json"))
    if not files:
        return "FAIL", ["no live_*.json snapshots in data/odds_capture"]
    stamp_utc, newest = newest_stamped(files)
    if stamp_utc is None:
        return "FAIL", ["could not parse timestamps from live_*.json names"]
    now_local = datetime.now().astimezone()
    expected = _expected_latest_capture(now_local)
    lag = expected - stamp_utc.astimezone()
    lines = [
        f"newest snapshot: {newest.name} ({stamp_utc.isoformat()})",
        f"schedule expectation: hourly {ODDS_WINDOW[0]:02d}:00-{ODDS_WINDOW[1]:02d}:00 "
        f"local; expected-latest {expected.isoformat(timespec='minutes')}",
        f"lag vs expectation: {fmt_age(max(lag, timedelta(0)))}",
    ]
    if lag <= timedelta(minutes=ODDS_PASS_LAG_MIN):
        return "PASS", lines
    if lag <= timedelta(minutes=ODDS_WARN_LAG_MIN):
        return "WARN", lines + ["capture is behind schedule"]
    return "FAIL", lines + ["capture appears down"]


def is_game_day_today() -> "bool | None":
    """Game day per the newest odds snapshot's commence times (local dates).
    None when no snapshot is readable — unknown, not 'no games'."""
    files = list((DATA / "odds_capture").glob("live_*.json"))
    _, newest = newest_stamped(files)
    if newest is None:
        return None
    try:
        events = json.loads(newest.read_text(encoding="utf-8"))
        today = datetime.now().astimezone().date()
        for ev in events:
            t = ev.get("commence_time")
            if t and datetime.fromisoformat(t.replace("Z", "+00:00")) \
                    .astimezone().date() == today:
                return True
        return False
    except (json.JSONDecodeError, OSError, ValueError):
        return None


# ---------------------------------------------------------------------------
# check 4 — injury capture freshness
# ---------------------------------------------------------------------------

def check_injury_freshness():
    candidates = []
    raw = DATA / "injury_capture" / "raw"
    if raw.exists():
        t, p = newest_stamped(list(raw.iterdir()))
        if t:
            candidates.append((t, f"raw/{p.name}"))
    log = DATA / "injury_capture" / "injury_log.csv"
    if log.exists():
        try:
            cap = pd.read_csv(log, usecols=["capture_utc"])["capture_utc"]
            t = parse_stamp(str(cap.max()))
            if t:
                candidates.append((t, "injury_log.csv max capture_utc"))
        except (ValueError, KeyError):
            pass
    if not candidates:
        return "FAIL", ["no injury captures found (raw/ empty and log unreadable)"]
    stamp, source = max(candidates)
    age = datetime.now(timezone.utc) - stamp
    gameday = is_game_day_today()
    pass_h = INJ_GAMEDAY_PASS_H if gameday else INJ_BASE_PASS_H
    lines = [
        f"newest capture: {source} ({stamp.isoformat()})",
        f"age: {fmt_age(age)} | game day today: "
        f"{'unknown' if gameday is None else gameday} "
        f"(threshold {pass_h}h; hard fail {INJ_FAIL_H}h)",
    ]
    if age <= timedelta(hours=pass_h):
        return "PASS", lines
    if age <= timedelta(hours=INJ_FAIL_H):
        return "WARN", lines + ["injury capture behind its cadence"]
    return "FAIL", lines + ["injury capture appears down"]


# ---------------------------------------------------------------------------
# check 5 — schema fingerprint drift
# ---------------------------------------------------------------------------

def _columns_of(path: Path) -> "list[str] | None":
    try:
        if path.suffix == ".parquet":
            return list(pq.read_schema(path).names)
        if path.suffix == ".csv":
            return list(pd.read_csv(path, nrows=0).columns)
        if path.suffix == ".json":   # odds snapshot: structural key census
            events = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(events, list) or not events:
                return None
            ev = events[0]
            cols = sorted(ev.keys())
            if ev.get("bookmakers"):
                bm = ev["bookmakers"][0]
                cols += [f"bookmakers[].{k}" for k in sorted(bm.keys())]
                if bm.get("markets"):
                    mk = bm["markets"][0]
                    cols += [f"markets[].{k}" for k in sorted(mk.keys())]
                    if mk.get("outcomes"):
                        cols += [f"outcomes[].{k}"
                                 for k in sorted(mk["outcomes"][0].keys())]
            return cols
    except (OSError, ValueError, KeyError, json.JSONDecodeError):
        return None
    return None


def _fingerprint_targets() -> dict:
    """dataset-key -> representative file (newest where families grow)."""
    targets = {}
    for p in sorted(DATA.glob("wnba_gamelog_*.parquet")):
        targets[p.stem] = p
    for p in sorted((DATA / "refresh_2026").glob("gamelog_*.parquet")):
        targets[f"refresh_{p.stem}"] = p
    for key, folder, prefix in [
        ("refresh_misc", DATA / "refresh_2026" / "misc", "misc"),
        ("refresh_advanced", DATA / "refresh_2026" / "advanced", "advanced"),
        ("refresh_pbp_v3", DATA / "refresh_2026" / "pbp", "pbp"),
        ("playbyplay_v2", DATA / "playbyplay", "pbp"),
    ]:
        files = sorted(folder.glob(f"{prefix}_*.parquet")) if folder.exists() else []
        if files:
            targets[key] = files[-1]
    for key, p in [
        ("injury_log", DATA / "injury_capture" / "injury_log.csv"),
        ("odds_capture_log", DATA / "odds_capture" / "capture_log.csv"),
        ("derived_stints", DATA / "derived" / "stints.parquet"),
        ("derived_starters", DATA / "derived" / "starters.csv"),
        ("derived_possessions", DATA / "possessions" / "possessions.parquet"),
    ]:
        if p.exists():
            targets[key] = p
    live = sorted((DATA / "odds_capture").glob("live_*.json"))
    if live:
        targets["odds_live_json"] = live[-1]
    return targets


def check_schema_drift(accept: bool = False):
    CERTIFY_DIR.mkdir(parents=True, exist_ok=True)
    stored = {}
    if FINGERPRINT_PATH.exists():
        stored = json.loads(FINGERPRINT_PATH.read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    lines, status = [], "PASS"
    drifted, added = [], []
    current = {}
    for key, path in sorted(_fingerprint_targets().items()):
        cols = _columns_of(path)
        if cols is None:
            lines.append(f"WARN {key}: could not read columns from {path.name}")
            status = max(status, "WARN", key=lambda s: STATUS_ORDER[s])
            continue
        h = hashlib.sha256("\n".join(cols).encode("utf-8")).hexdigest()[:16]
        current[key] = {"hash": h, "columns": cols, "source": str(path.relative_to(ROOT))}
        if key not in stored:
            added.append(key)
        elif stored[key]["hash"] != h:
            old = set(stored[key].get("columns", []))
            new = set(cols)
            drifted.append(
                f"{key}: hash {stored[key]['hash']} -> {h} "
                f"(+{sorted(new - old)} -{sorted(old - new)})"
            )
    if drifted and not accept:
        status = "WARN"
        lines += [f"SCHEMA DRIFT (stored baseline kept; rerun with "
                  f"--accept-schema after review):"] + [f"  {d}" for d in drifted]
    if not stored:
        payload = {k: v | {"first_seen": now} for k, v in current.items()}
        FINGERPRINT_PATH.write_text(json.dumps(payload, indent=1), encoding="utf-8")
        lines.append(f"baseline created: {len(current)} dataset fingerprints "
                     f"-> {FINGERPRINT_PATH.relative_to(ROOT)}")
    else:
        payload = dict(stored)
        for k in added:
            payload[k] = current[k] | {"first_seen": now}
        if accept:
            for d in drifted:
                k = d.split(":", 1)[0]
                payload[k] = current[k] | {
                    "first_seen": stored.get(k, {}).get("first_seen", now),
                    "accepted_at": now,
                }
            if drifted:
                lines.append(f"accepted {len(drifted)} schema change(s) into baseline")
        if added or (accept and drifted):
            FINGERPRINT_PATH.write_text(json.dumps(payload, indent=1), encoding="utf-8")
        if added:
            lines.append(f"new datasets baselined: {', '.join(added)}")
        if not drifted and not added:
            lines.append(f"{len(current)} dataset schemas match stored fingerprints")
    return status, lines


# ---------------------------------------------------------------------------
# check 6 — possession reconciliation (Phase 0 / RAPM prerequisite)
# ---------------------------------------------------------------------------

POSS_SAMPLE_N = 8            # most recent games, re-derived from raw pbp
POSS_FAIL_BAD = 3            # > this many non-exact games in the sample = FAIL


def check_possession_reconciliation():
    """Re-derive the POSS_SAMPLE_N most recent games' possessions from raw pbp
    (build_possessions.reconcile_sample) and require the per-team possession
    point sums to match master_team final scores exactly. Fast (~seconds) —
    the full-history reconciliation lives in build_possessions.py's main run
    (report: data/possessions/reconciliation.csv)."""
    try:
        import build_possessions as bp
    except Exception as exc:
        return "FAIL", [f"cannot import build_possessions: {type(exc).__name__}: {exc}"]
    reports = bp.reconcile_sample(n=POSS_SAMPLE_N)
    if not reports:
        return "FAIL", ["no games available to reconcile (pbp + master_team empty?)"]
    lines, n_bad, n_err = [], 0, 0
    for r in reports:
        if r.get("status") != "ok":
            n_err += 1
            lines.append(f"FAIL {r['game_id']}: {r.get('status')}")
        elif r.get("exact"):
            lines.append(f"ok   {r['game_id']} ({r['season']}): exact "
                         f"{r['model_home_pts']}-{r['model_away_pts']}, "
                         f"{r['n_real_possessions']} possessions")
        else:
            n_bad += 1
            lines.append(f"BAD  {r['game_id']} ({r['season']}): residual "
                         f"home {r['resid_home']:+d} away {r['resid_away']:+d} "
                         f"dominant={r.get('dominant_failure') or 'n/a'}")
    lines.insert(0, f"re-derived the {len(reports)} most recent games from raw pbp; "
                    f"{len(reports) - n_bad - n_err} exact, {n_bad} non-exact, "
                    f"{n_err} errored")
    if n_err or n_bad > POSS_FAIL_BAD:
        return "FAIL", lines
    if n_bad:
        return "WARN", lines
    return "PASS", lines


# ---------------------------------------------------------------------------
# checks 7-9 — Phase-0 hooks (WARN mode until promoted via *_FAIL_MODE)
# ---------------------------------------------------------------------------

def _apply_mode(status, fail_mode, lines):
    """WARN-mode governor for the Phase-0 hooks: report the would-be FAIL,
    downgrade it to WARN until the hook's *_FAIL_MODE switch is flipped."""
    if status == "FAIL" and not fail_mode:
        lines.append("WARN mode: this hook would FAIL once promoted "
                     "(flip its *_FAIL_MODE switch at the top of the file)")
        return "WARN", lines
    return status, lines


def _iso_utc(s):
    try:
        dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# ---- check 7: PBP score reconciliation -------------------------------------

_V2_SCORE_RE = re.compile(r"^\s*(\d+)\s*-\s*(\d+)\s*$")   # V2 SCORE = "away - home"


def _master_finals() -> dict:
    """game_id -> home/away final points + team ids (from master_team)."""
    mt = pd.read_parquet(DATA / "masters" / "master_team.parquet",
                         columns=["game_id", "team_id", "is_home", "pts",
                                  "season", "game_date"])
    out = {}
    for gid, grp in mt.groupby("game_id"):
        h, a = grp[grp.is_home == 1], grp[grp.is_home == 0]
        if len(h) != 1 or len(a) != 1:
            continue     # malformed pairing is check 1's job; skip here
        out[str(gid)] = {
            "home_pts": int(h["pts"].iloc[0]), "away_pts": int(a["pts"].iloc[0]),
            "home_id": int(h["team_id"].iloc[0]), "away_id": int(a["team_id"].iloc[0]),
            "season": str(h["season"].iloc[0]), "game_date": str(h["game_date"].iloc[0]),
        }
    return out


def _pbp_inventory() -> dict:
    """game_id -> (path, era). V3 wins if a game id somehow exists in both."""
    inv = {}
    for p in sorted((DATA / "playbyplay").glob("pbp_*.parquet")):
        inv[p.stem.split("_", 1)[1]] = (p, "v2")
    for p in sorted((DATA / "refresh_2026" / "pbp").glob("pbp_*.parquet")):
        inv[p.stem.split("_", 1)[1]] = (p, "v3")
    return inv


def reconcile_pbp_game(gid: str, path: Path, era: str, m: dict) -> dict:
    """Recompute one game's final score from raw pbp event semantics and
    reconcile it against the posted running score at every scoring checkpoint
    and against master_team's final. Fully identical duplicated event rows
    (a real defect seen in the wild: 1022300238) are dropped and counted;
    same-event-key rows with different content are counted as conflicts."""
    rec = {"game_id": gid, "era": era, "season": m["season"] if m else "",
           "game_date": m["game_date"] if m else "", "status": "ok",
           "n_events": 0, "n_dup_rows_dropped": 0, "n_conflicting_dup_keys": 0,
           "n_unattributed_pts": 0, "ot_periods": 0,
           "rec_home": None, "rec_away": None,
           "posted_home": None, "posted_away": None,
           "master_home": m["home_pts"] if m else None,
           "master_away": m["away_pts"] if m else None,
           "n_checkpoints": 0, "n_checkpoint_mismatch": 0,
           "first_mismatch_event": "",
           "exact_vs_master": None, "posted_matches_master": None}
    if m is None:
        rec["status"] = "no_master_row"
        return rec
    try:
        df = pd.read_parquet(path)
    except Exception as exc:
        rec["status"] = f"read_error:{type(exc).__name__}"
        return rec
    try:
        # Event order: FILE ORDER for both eras, exactly like build_possessions
        # (1,489/1,489 exact on it). V2 EVENTNUM is NOT chronological — scorer
        # corrections are renumbered high but placed correctly in the file
        # (seen: 1022400002 events 438-440, 1022400017 event 602); V3
        # actionId is strictly file-sequential (actionNumber is shared by
        # paired actions like turnover+steal, so it is not even unique).
        key = "EVENTNUM" if era == "v2" else "actionId"
        if era == "v3":
            df = df.sort_values(key, kind="stable")   # == file order, verified
        n0 = len(df)
        df = df[~df.duplicated()]
        rec["n_dup_rows_dropped"] = n0 - len(df)
        rec["n_conflicting_dup_keys"] = int(df.duplicated(subset=[key]).sum())
        pts = pd.Series(0, index=df.index)
        side = pd.Series("", index=df.index)          # 'h' / 'a'
        if era == "v2":
            desc = (df["HOMEDESCRIPTION"].fillna("") + "|" +
                    df["NEUTRALDESCRIPTION"].fillna("") + "|" +
                    df["VISITORDESCRIPTION"].fillna(""))
            made_fg = df["EVENTMSGTYPE"] == 1
            pts[made_fg] = 2
            pts[made_fg & desc.str.contains("3PT", regex=False)] = 3
            pts[(df["EVENTMSGTYPE"] == 3) &
                ~desc.str.contains("MISS", regex=False)] = 1     # made FTs (incl. technicals)
            side[df["PLAYER1_TEAM_ID"] == m["home_id"]] = "h"
            side[df["PLAYER1_TEAM_ID"] == m["away_id"]] = "a"
            fb = (pts > 0) & (side == "")             # rare: attribute by desc column
            side[fb & df["HOMEDESCRIPTION"].notna() & df["VISITORDESCRIPTION"].isna()] = "h"
            side[fb & df["VISITORDESCRIPTION"].notna() & df["HOMEDESCRIPTION"].isna()] = "a"
            sc = df["SCORE"].astype(str)
            parsed = sc.str.extract(_V2_SCORE_RE)     # away, home
            posted = parsed[0].notna()
            post_h = parsed.loc[posted, 1].astype(int)
            post_a = parsed.loc[posted, 0].astype(int)
            period = df["PERIOD"]
        else:                                          # v3
            desc = df["description"].fillna("").astype(str)
            made_fg = df["actionType"] == "Made Shot"
            pts[made_fg] = df.loc[made_fg, "shotValue"].fillna(0).astype(int).clip(lower=2)
            pts[(df["actionType"] == "Free Throw") &
                ~desc.str.contains("MISS", regex=False)] = 1     # FT shotValue is 0 in V3
            side[df["location"] == "h"] = "h"
            side[df["location"] == "v"] = "a"
            fb = (pts > 0) & (side == "")
            side[fb & (df["teamId"] == m["home_id"])] = "h"
            side[fb & (df["teamId"] == m["away_id"])] = "a"
            sh = df["scoreHome"].astype(str).str.strip()
            sa = df["scoreAway"].astype(str).str.strip()
            posted = sh.str.fullmatch(r"\d+") & sa.str.fullmatch(r"\d+")
            post_h = sh[posted].astype(int)
            post_a = sa[posted].astype(int)
            period = df["period"]
        rec["n_unattributed_pts"] = int(pts[(pts > 0) & (side == "")].sum())
        run_h = (pts * (side == "h")).cumsum()
        run_a = (pts * (side == "a")).cumsum()
        # Checkpoints: compare on SCORING rows only — non-scoring rows that
        # carry a score (period ends, timeouts, replays) are snapshots whose
        # feed position is occasionally wrong; a scoring row's posted score
        # must equal the recomputed running score at that exact event.
        chk = posted & (pts > 0)
        mism = post_h[chk].ne(run_h[chk]) | post_a[chk].ne(run_a[chk])
        rec["n_events"] = int(len(df))
        rec["ot_periods"] = max(int(period.max()) - 4, 0) if len(df) else 0
        rec["n_checkpoints"] = int(chk.sum())
        rec["n_checkpoint_mismatch"] = int(mism.sum())
        if mism.any():
            i = mism[mism].index[0]
            rec["first_mismatch_event"] = (
                f"{key}={df.loc[i, key]} posted {post_a[i]}-{post_h[i]} (a-h) "
                f"recomputed {int(run_a[i])}-{int(run_h[i])}")
        if len(df):
            rec["rec_home"], rec["rec_away"] = int(run_h.iloc[-1]), int(run_a.iloc[-1])
        if posted.any():
            # Posted final = the max-total posted score: cumulative scores are
            # monotonic, so this is order-robust against misplaced feed rows.
            imax = (post_h + post_a).idxmax()
            rec["posted_home"], rec["posted_away"] = int(post_h[imax]), int(post_a[imax])
        rec["exact_vs_master"] = (rec["rec_home"] == m["home_pts"] and
                                  rec["rec_away"] == m["away_pts"])
        if rec["posted_home"] is not None:
            rec["posted_matches_master"] = (rec["posted_home"] == m["home_pts"] and
                                            rec["posted_away"] == m["away_pts"])
    except Exception as exc:
        rec["status"] = f"parse_error:{type(exc).__name__}:{exc}"
    return rec


def _pbp_sample_ids(master: dict, inv: dict) -> "tuple[list, int]":
    """Newest PBP_RECENT_N games + a deterministic day-rotating block of
    PBP_ROTATE_N: consecutive daily runs sweep adjacent blocks, so the full
    history is re-reconciled every ceil(n / PBP_ROTATE_N) days."""
    ids = sorted((g for g in inv if g in master),
                 key=lambda g: (master[g]["game_date"], g))
    n = len(ids)
    if n == 0:
        return [], 0
    recent = ids[-PBP_RECENT_N:]
    start = (datetime.now().astimezone().date().toordinal() * PBP_ROTATE_N) % n
    block = [ids[(start + i) % n] for i in range(min(PBP_ROTATE_N, n))]
    seen, out = set(), []
    for g in recent + block:
        if g not in seen:
            seen.add(g)
            out.append(g)
    return out, n


def check_pbp_reconciliation(full: bool = False):
    master = _master_finals()
    inv = _pbp_inventory()
    if not inv or not master:
        return _apply_mode("FAIL", PBP_RECON_FAIL_MODE,
                           ["no pbp files or master_team rows readable"])
    no_master = sorted(g for g in inv if g not in master)
    if full:
        ids, n_uni = sorted(g for g in inv if g in master), len(inv)
    else:
        ids, n_uni = _pbp_sample_ids(master, inv)
    rows = [reconcile_pbp_game(g, *inv[g], master.get(g)) for g in ids]
    errs = [r for r in rows if r["status"] != "ok"]
    nonexact = [r for r in rows if r["status"] == "ok" and not r["exact_vs_master"]]
    posted_bad = [r for r in rows if r["status"] == "ok" and r["exact_vs_master"]
                  and r["posted_matches_master"] is False]
    quirks = [r for r in rows if r["status"] == "ok" and r["exact_vs_master"]
              and (r["n_checkpoint_mismatch"] or r["n_dup_rows_dropped"]
                   or r["n_conflicting_dup_keys"] or r["n_unattributed_pts"])]
    by_era = pd.Series([r["era"] for r in rows]).value_counts().to_dict()
    scope = (f"FULL history: {len(rows)} games" if full
             else f"sample: {len(rows)} of {n_uni} games "
                  f"(newest {PBP_RECENT_N} + rotating block {PBP_ROTATE_N})")
    lines = [f"{scope} | eras {by_era} | "
             f"{len(rows) - len(nonexact) - len(errs)} exact, "
             f"{len(nonexact)} non-exact, {len(errs)} errored"
             + (f" | {len(no_master)} pbp games lack a master_team row "
                f"(e.g. {no_master[:3]})" if no_master else "")]
    cap = len(rows) if full else 15
    for r in nonexact[:cap]:
        lines.append(
            f"BAD  {r['game_id']} ({r['era']} {r['season']}): recomputed "
            f"{r['rec_home']}-{r['rec_away']} (h-a) vs master "
            f"{r['master_home']}-{r['master_away']} | posted "
            f"{r['posted_home']}-{r['posted_away']} | "
            f"{r['n_checkpoint_mismatch']}/{r['n_checkpoints']} checkpoints off | "
            f"first: {r['first_mismatch_event'] or 'n/a'}")
    for r in posted_bad[:5]:
        lines.append(f"BAD  {r['game_id']}: pbp posted final "
                     f"{r['posted_home']}-{r['posted_away']} != master "
                     f"{r['master_home']}-{r['master_away']} (truncated feed?)")
    for r in errs[:5]:
        lines.append(f"ERR  {r['game_id']} ({r['era']}): {r['status']}")
    for r in quirks[:5]:
        lines.append(
            f"note {r['game_id']} ({r['era']} {r['season']}): final exact but "
            f"{r['n_dup_rows_dropped']} duplicated row(s) dropped, "
            f"{r['n_conflicting_dup_keys']} conflicting key(s), "
            f"{r['n_checkpoint_mismatch']} checkpoint mismatch(es), "
            f"{r['n_unattributed_pts']} unattributed pts")
    if full:
        PBP_FULL_OUT.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(rows).to_csv(PBP_FULL_OUT, index=False)
        lines.append(f"full per-game table -> {PBP_FULL_OUT.relative_to(ROOT)}")
    if errs or nonexact or posted_bad:
        status = "FAIL"     # non-exact games are data bugs, never auto-fixed
    elif quirks or no_master:
        status = "WARN"
    else:
        status = "PASS"
    return _apply_mode(status, PBP_RECON_FAIL_MODE, lines)


# ---- check 8: odds stale-book detection ------------------------------------

def _live_snapshots(n: "int | None" = None) -> list:
    """[(path, snap_utc, events-or-None), ...] oldest -> newest."""
    files = sorted((DATA / "odds_capture").glob("live_*.json"),
                   key=lambda p: p.name)
    if n:
        files = files[-n:]
    out = []
    for p in files:
        t = parse_stamp(p.name)
        if t is None:
            continue
        try:
            out.append((p, t, json.loads(p.read_text(encoding="utf-8"))))
        except (json.JSONDecodeError, OSError):
            out.append((p, t, None))
    return out


def check_stale_books():
    snaps = _live_snapshots(STALE_SNAPSHOTS_N)
    if not snaps:
        return _apply_mode("FAIL", STALE_BOOK_FAIL_MODE,
                           ["no live_*.json snapshots to scan"])
    unreadable = [p.name for p, _, ev in snaps if ev is None]
    per_book = {}          # book -> dict(sight, stale, max_lag)
    stale_rows = []
    for p, snap_t, events in snaps:
        if events is None:
            continue
        for ev in events:
            commence = _iso_utc(ev.get("commence_time"))
            if commence is None or commence <= snap_t:
                continue                       # pregame events only
            for bm in ev.get("bookmakers", []):
                upds = [_iso_utc(mk.get("last_update"))
                        for mk in bm.get("markets", [])]
                upds = [u for u in upds if u is not None] or \
                       [u for u in [_iso_utc(bm.get("last_update"))] if u is not None]
                if not upds:
                    continue
                lag_min = max((snap_t - max(upds)).total_seconds() / 60.0, 0.0)
                d = per_book.setdefault(bm.get("key", "?"),
                                        {"sight": 0, "stale": 0, "max_lag": 0.0})
                d["sight"] += 1
                d["max_lag"] = max(d["max_lag"], lag_min)
                if lag_min > STALE_BOOK_LAG_MIN:
                    d["stale"] += 1
                    stale_rows.append((p.name, f"{ev.get('away_team')} @ "
                                       f"{ev.get('home_team')}", bm.get("key"), lag_min))
    lines = [f"scanned {len(snaps)} live snapshots "
             f"({snaps[0][0].name} .. {snaps[-1][0].name}); threshold "
             f"{STALE_BOOK_LAG_MIN} min on pregame events"]
    if unreadable:
        lines.append(f"unreadable snapshots: {unreadable}")
    persistent = []
    for bk in sorted(per_book, key=lambda b: (-per_book[b]["stale"], b)):
        d = per_book[bk]
        flag = ""
        if d["sight"] >= STALE_PERSIST_MIN_SIGHT and d["stale"] > d["sight"] / 2:
            persistent.append(bk)
            flag = "  <- PERSISTENTLY STALE"
        lines.append(f"{bk:<16} sightings {d['sight']:3d} | stale {d['stale']:3d} "
                     f"| max lag {d['max_lag']:6.0f} min{flag}")
    for name, matchup, bk, lag in stale_rows[:8]:
        lines.append(f"  stale: {bk} {lag:.0f} min behind in {name} ({matchup})")
    if len(stale_rows) > 8:
        lines.append(f"  ... and {len(stale_rows) - 8} more stale sightings")
    if persistent or unreadable:
        status = "FAIL"
    elif stale_rows:
        status = "WARN"
    else:
        status = "PASS"
    return _apply_mode(status, STALE_BOOK_FAIL_MODE, lines)


# ---- check 9: postponement / changed-tip-time detection --------------------

def check_tip_changes():
    snaps = [(p, t, ev) for p, t, ev in _live_snapshots(TIP_SNAPSHOTS_N)
             if ev is not None]
    if not snaps:
        return _apply_mode("FAIL", TIP_CHANGE_FAIL_MODE,
                           ["no readable live_*.json snapshots to scan"])
    sightings = {}          # eid -> list of (snap_idx, commence_str, home, away)
    for idx, (p, snap_t, events) in enumerate(snaps):
        for ev in events:
            sightings.setdefault(ev.get("id"), []).append(
                (idx, ev.get("commence_time"), ev.get("home_team"),
                 ev.get("away_team")))
    changes, vanished = [], []
    for eid, seen in sightings.items():
        for (i0, c0, h, a), (i1, c1, _, _) in zip(seen, seen[1:]):
            if c0 != c1:
                changes.append((eid, a, h, c0, c1, snaps[i1][0].name))
        last_idx, last_c, h, a = seen[-1][0], seen[-1][1], seen[-1][2], seen[-1][3]
        if last_idx < len(snaps) - 1:            # absent from a later snapshot
            nxt_t = snaps[last_idx + 1][1]
            c = _iso_utc(last_c)
            if c and c > nxt_t + timedelta(minutes=TIP_VANISH_GRACE_MIN):
                vanished.append((eid, a, h, last_c, snaps[last_idx][0].name))
    lines = [f"scanned {len(snaps)} live snapshots, {len(sightings)} events; "
             f"{len(changes)} commence_time change(s), "
             f"{len(vanished)} pregame vanish(es)"]
    for eid, a, h, c0, c1, fname in changes[:12]:
        lines.append(f"TIP CHANGE {a} @ {h}: {c0} -> {c1} "
                     f"(first seen {fname}; event {eid[:8]})")
    for eid, a, h, c, fname in vanished[:8]:
        lines.append(f"VANISHED pregame: {a} @ {h} commence {c} last seen "
                     f"{fname} (event {eid[:8]}) — postponement/relist pattern")
    status = "FAIL" if (changes or vanished) else "PASS"
    return _apply_mode(status, TIP_CHANGE_FAIL_MODE, lines)


# ---------------------------------------------------------------------------
# runner
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--accept-schema", action="store_true",
                    help="accept current schemas as the new fingerprint baseline")
    ap.add_argument("--full", action="store_true",
                    help="exhaustive PBP score reconciliation over every game "
                         "(writes experiments/odds_audit_ext/"
                         "pbp_full_reconciliation.csv; takes a few minutes)")
    args = ap.parse_args(argv)

    checks = [
        ("duplicate game/player rows", lambda: check_duplicates()),
        ("coverage by season (pbp/misc/advanced)", lambda: check_coverage()),
        ("odds capture freshness", lambda: check_odds_freshness()),
        ("injury capture freshness", lambda: check_injury_freshness()),
        ("schema fingerprint drift",
         lambda: check_schema_drift(accept=args.accept_schema)),
        ("possession reconciliation (recent-game sample)",
         check_possession_reconciliation),
        ("pbp score reconciliation "
         + ("(full history)" if args.full else "(sampled+incremental)"),
         lambda: check_pbp_reconciliation(full=args.full)),
        ("odds stale-book detection", check_stale_books),
        ("postponement / tip-time change detection", check_tip_changes),
    ]
    print(f"daily_certify - {datetime.now().astimezone().isoformat(timespec='seconds')}")
    print("=" * 72)
    results = []
    for name, fn in checks:
        try:
            status, lines = fn()
        except Exception as exc:   # a crashing check is itself a FAIL, loudly
            status, lines = "FAIL", [f"check crashed: {type(exc).__name__}: {exc}"]
        results.append((name, status))
        print(f"\n[{status}] {name}")
        for line in lines:
            print(f"    {line}")
    print("\n" + "=" * 72)
    n_fail = sum(1 for _, s in results if s == "FAIL")
    n_warn = sum(1 for _, s in results if s == "WARN")
    for name, s in results:
        print(f"  {s:<4}  {name}")
    verdict = "FAIL" if n_fail else ("WARN" if n_warn else "PASS")
    print(f"\nSUMMARY: {verdict}  ({n_fail} fail, {n_warn} warn, "
          f"{len(results) - n_fail - n_warn} pass/skip)")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
