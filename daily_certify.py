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

TODO hooks (log-only, per Phase 0 spec — no NotImplementedError):
  * PBP score reconciliation (running score vs final, FT sequences,
    technicals, OREB chains, OT)
  * odds stale-book detection (per-book last_update lag inside a snapshot)
  * postponement / changed-tip-time detection (tip time known-at-capture vs
    schedule)

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
# TODO hooks — Phase 0 items not yet implemented (log-only, never raise)
# ---------------------------------------------------------------------------

def todo_hooks():
    # TODO(Phase 0): PBP score reconciliation — running score vs final, FT
    #   sequences, technicals, OREB chains, OT (ROADMAP Phase 0).
    # TODO(Phase 0): odds stale-book detection — per-book last_update lag
    #   within a snapshot (ROADMAP Phase 0 "odds freshness & stale-book").
    # TODO(Phase 0): postponement & changed tip time detection — tip time
    #   known-at-capture vs schedule (ROADMAP Phase 0).
    hooks = [
        "PBP score reconciliation",
        "odds stale-book detection",
        "postponement / changed tip-time detection",
    ]
    return "SKIP", [f"{h}: not yet implemented" for h in hooks]


# ---------------------------------------------------------------------------
# runner
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--accept-schema", action="store_true",
                    help="accept current schemas as the new fingerprint baseline")
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
        ("phase-0 reconciliation hooks", todo_hooks),
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
