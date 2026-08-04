"""O11 — measure the obligation-discovery lag that causes defect D-b.

READ-ONLY. Reconstructs, per scheduled game, the earliest wall-clock instant at
which `should_run_base.assess()` could possibly have seen it, and compares that
instant to each registered decision-time cutoff.

Discovery requires an official `game_id`, because should_run_base.py:80-82 skips
any slate row whose game_id is null. `game_id` is supplied by
`data/ref_assignments/assignments_log.csv` (coverage_audit.py:116-124) or by a
COMPLETED game in master_team.parquet (coverage_audit.py:128-142). For a
not-yet-played game only the first source can apply, so the discovery instant is
the earliest `capture_utc` at which the assignments log carried a non-null
game_id for that (game_date, home, away).

The odds captures are the source of tip times and are what makes the game exist
on the slate at all; they are captured hourly and are NOT the binding constraint,
but the script measures them too so the claim is not assumed.

Usage:  python measure_discovery_lag.py [--repo <path>] [--json out.json]
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

DEFAULT_REPO = Path("C:/Users/jgallagher/wnba-betting-model")

# Verbatim from coverage_audit.py:47 and :55-61 (read, not imported: the module
# lives in a different worktree and this node may not depend on its presence).
CONTRACT_LABELS = [("T-24h", 24.0), ("T-8h", 8.0), ("T-90m", 1.5), ("T-30m", 0.5)]
TEAMS = {
    "Atlanta Dream": "ATL", "Chicago Sky": "CHI", "Connecticut Sun": "CON",
    "Dallas Wings": "DAL", "Golden State Valkyries": "GSV", "Indiana Fever": "IND",
    "Las Vegas Aces": "LVA", "Los Angeles Sparks": "LAS", "Minnesota Lynx": "MIN",
    "New York Liberty": "NYL", "Phoenix Mercury": "PHX", "Portland Fire": "PDX",
    "Seattle Storm": "SEA", "Toronto Tempo": "TOR", "Washington Mystics": "WAS",
}


def _utc(t) -> datetime:
    if isinstance(t, str):
        t = datetime.fromisoformat(t.replace("Z", "+00:00"))
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return t.astimezone(timezone.utc)


def _stamp(s: str) -> datetime:
    return _utc(datetime.strptime(s, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc))


def _slate_date(tip: datetime) -> str:
    try:
        from zoneinfo import ZoneInfo
        return tip.astimezone(ZoneInfo("America/New_York")).date().isoformat()
    except Exception:
        return (tip - timedelta(hours=5)).date().isoformat()


def odds_first_seen(repo: Path) -> dict:
    """(game_date, home, away) -> (earliest capture that showed it, latest tip)."""
    out = {}
    for f in sorted(glob.glob(str(repo / "data" / "odds_capture" / "live_*.json"))):
        try:
            games = json.load(open(f, encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        cap = _stamp(Path(f).stem.replace("live_", ""))
        for g in games:
            h, a = TEAMS.get(g.get("home_team")), TEAMS.get(g.get("away_team"))
            if not h or not a:
                continue
            tip = _utc(g["commence_time"])
            key = (_slate_date(tip), h, a)
            r = out.setdefault(key, {"odds_first_seen": cap, "tip": tip})
            r["tip"] = tip          # latest observed tip, as build_slate does
    return out


def assignment_first_id(repo: Path) -> dict:
    """(game_date, home, away) -> earliest capture_utc carrying a NON-NULL game_id."""
    A = pd.read_csv(repo / "data" / "ref_assignments" / "assignments_log.csv",
                    dtype={"game_id": str})
    A["home"] = A.home_team.map(TEAMS)
    A["away"] = A.away_team.map(TEAMS)
    A = A.dropna(subset=["home", "away", "game_id"])
    A = A[A.game_id.astype(str).str.strip().ne("")]
    out = {}
    for r in A.itertuples():
        key = (str(r.game_date), r.home, r.away)
        t = _stamp(str(r.capture_utc))
        if key not in out or t < out[key]["id_first_seen"]:
            out[key] = {"id_first_seen": t,
                        "game_id": str(r.game_id).split(".")[0]}
    return out


def build(repo: Path) -> pd.DataFrame:
    odds = odds_first_seen(repo)
    ids = assignment_first_id(repo)
    rows = []
    for key, o in sorted(odds.items()):
        d, h, a = key
        i = ids.get(key)
        for label, hrs in CONTRACT_LABELS:
            cutoff = o["tip"] - timedelta(hours=hrs)
            disc = i["id_first_seen"] if i else None
            rows.append({
                "game_date": d, "home": h, "away": a,
                "game_id": (i or {}).get("game_id"),
                "tip_utc": o["tip"].isoformat(),
                "label": label,
                "cutoff_utc": cutoff.isoformat(),
                "odds_first_seen_utc": o["odds_first_seen"].isoformat(),
                "id_first_seen_utc": disc.isoformat() if disc else None,
                "odds_lead_min": round((cutoff - o["odds_first_seen"]).total_seconds() / 60, 1),
                "id_lead_min": (round((cutoff - disc).total_seconds() / 60, 1)
                                if disc else None),
                "discoverable_before_cutoff": (bool(disc is not None and disc <= cutoff)),
            })
    return pd.DataFrame(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=str(DEFAULT_REPO))
    ap.add_argument("--json", default=None)
    ap.add_argument("--csv", default=None)
    args = ap.parse_args()
    repo = Path(args.repo)
    if not (repo / "data" / "odds_capture").exists():
        print("NO DATA: %s has no data/odds_capture. Nothing measured." % repo)
        return 2

    D = build(repo)
    if D.empty:
        print("NO DATA: no slate rows could be assembled.")
        return 2

    never = D[D.id_first_seen_utc.isna()]
    known = D[D.id_first_seen_utc.notna()]
    summary = {
        "obligations_examined": int(len(D)),
        "distinct_games": int(D.groupby(["game_date", "home", "away"]).ngroups),
        "obligations_with_no_game_id_ever": int(len(never)),
        "obligations_discoverable_before_cutoff": int(known.discoverable_before_cutoff.sum()),
        "obligations_NOT_discoverable_before_cutoff": int(
            len(never) + int((~known.discoverable_before_cutoff).sum())),
        "by_label": {},
        "odds_lead_min_median_by_label": {},
        "id_lead_min_median_by_label": {},
    }
    for label, _ in CONTRACT_LABELS:
        L = D[D.label == label]
        Lk = L[L.id_first_seen_utc.notna()]
        summary["by_label"][label] = {
            "n": int(len(L)),
            "discoverable_before_cutoff": int(Lk.discoverable_before_cutoff.sum()),
            "not_discoverable": int(len(L) - int(Lk.discoverable_before_cutoff.sum())),
        }
        summary["odds_lead_min_median_by_label"][label] = (
            None if L.empty else float(L.odds_lead_min.median()))
        summary["id_lead_min_median_by_label"][label] = (
            None if Lk.empty else float(Lk.id_lead_min.median()))

    print(json.dumps(summary, indent=2))
    print("\nPER-GAME T-24h DETAIL (the label the defect names)")
    T = D[D.label == "T-24h"].sort_values(["game_date", "home"])
    for r in T.itertuples():
        seen = r.id_first_seen_utc
        seen = "NEVER" if not isinstance(seen, str) else seen[:19]
        lead = r.id_lead_min
        lead = "n/a" if lead is None or pd.isna(lead) else "%.0f" % lead
        print("  %s %s v %s  cutoff %s  id_first_seen %s  lead %s min  %s"
              % (r.game_date, r.home, r.away, r.cutoff_utc[:19], seen, lead,
                 "OK" if r.discoverable_before_cutoff else "UNDISCOVERABLE"))

    if args.csv:
        D.to_csv(args.csv, index=False)
        print("\nwrote %s" % args.csv)
    if args.json:
        json.dump(summary, open(args.json, "w"), indent=2)
        print("wrote %s" % args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
