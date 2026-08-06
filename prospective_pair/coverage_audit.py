"""Forecast-coverage auditor.

Compares the OFFICIAL SCHEDULED SLATE against the forecast obligations that slate
creates at every registered decision time, and classifies each obligation. Both logs
are read-only here.

An obligation is one (game, decision_time_label). The slate is assembled from:
    tip times   data/odds_capture/live_*.json      (The Odds API commence_time)
    game ids    data/ref_assignments/assignments_log.csv
    outcomes    data/masters/master_team.parquet   (completed games)

CLASSES
    forecast_logged            a forecast record exists for this obligation
    explicit_no_forecast       the job ran and recorded WHY it could not forecast
    not_yet_due                cutoff is in the future
    postponed_or_tip_changed   tip time moved between captures; the obligation moved with it
    missing_job_did_not_run    cutoff passed, no record, and the job produced nothing
                               for ANY game at that cutoff -- an operational miss
    missing_data_unavailable   cutoff passed, no record, but the job did serve other
                               games at that cutoff -- game-specific data gap
    duplicate                  more than one record for the same obligation
    late_record                a record exists but was created after its own cutoff

THE DISTINCTION THAT MATTERS
    `explicit_no_forecast` is an HONEST DECLINE -- the system was present and said so.
    `missing_job_did_not_run` is an OPERATIONAL MISS -- nobody was home. Only the first
    is acceptable in a promotion-grade period. Coverage that conflates them would hide
    exactly the failure that demoted prospective_v0 to a pilot.
"""
from __future__ import annotations

import glob
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO))

from alt_model_log import read_official, read_records  # noqa: E402

CONTRACT_LABELS = [("T-24h", 24.0), ("T-8h", 8.0), ("T-90m", 1.5), ("T-30m", 0.5)]

#: PREREGISTERED coverage threshold for a promotion-grade period. Registered
#: 2026-08-03 before any prospective_team_pair_v1 data exists.
MIN_COVERAGE_SERVED = 0.95      # served = forecast_logged or explicit_no_forecast
MAX_OPERATIONAL_MISSES = 0      # missing_job_did_not_run tolerated in a graded period
REQUIRE_ALL_EXPLAINED = True

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


#: a tip is only "moved" if it shifts by at least this much. The Odds API drifts
#: commence_time by seconds routinely; treating that as a postponement would mask
#: real operational misses behind a benign-looking class.
TIP_MOVE_TOLERANCE = timedelta(minutes=30)


def _slate_date(tip: datetime) -> str:
    """The ET calendar date of the game. A 20:00 ET tip is 00:00 UTC the NEXT day;
    keying on the UTC date would split one slate across two and invent phantom games.
    The assignments log and the forecast job both use the ET date."""
    try:
        from zoneinfo import ZoneInfo
        return tip.astimezone(ZoneInfo("America/New_York")).date().isoformat()
    except Exception:
        return (tip - timedelta(hours=5)).date().isoformat()


def build_slate() -> pd.DataFrame:
    """One row per scheduled game: latest tip, earliest-seen tip, ids."""
    rows = {}
    for f in sorted(glob.glob(str(REPO / "data" / "odds_capture" / "live_*.json"))):
        try:
            games = json.load(open(f, encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        cap = Path(f).stem.replace("live_", "")
        for g in games:
            h, a = TEAMS.get(g.get("home_team")), TEAMS.get(g.get("away_team"))
            if not h or not a:
                continue
            tip = _utc(g["commence_time"])
            key = (_slate_date(tip), h, a)
            r = rows.setdefault(key, {"first_tip": tip, "tip": tip, "first_seen": cap,
                                      "n_captures": 0})
            r["tip"], r["last_seen"], r["n_captures"] = tip, cap, r["n_captures"] + 1
    for r in rows.values():
        r["tip_moved"] = abs(r["tip"] - r["first_tip"]) >= TIP_MOVE_TOLERANCE
        r["tip_shift_min"] = round((r["tip"] - r["first_tip"]).total_seconds() / 60.0, 1)
    S = pd.DataFrame([{"game_date": k[0], "home": k[1], "away": k[2], **v}
                      for k, v in rows.items()])
    if S.empty:
        return S

    # official game ids
    ap = REPO / "data" / "ref_assignments" / "assignments_log.csv"
    if ap.exists():
        A = pd.read_csv(ap, dtype={"game_id": str})
        A["home"] = A.home_team.map(TEAMS)
        A["away"] = A.away_team.map(TEAMS)
        A["game_id"] = A.game_id.astype(str).str.split(".").str[0]
        A = A.dropna(subset=["home", "away"]).drop_duplicates(["game_date", "home", "away"])
        S = S.merge(A[["game_date", "home", "away", "game_id"]],
                    on=["game_date", "home", "away"], how="left")
    else:
        S["game_id"] = None

    # completed games (also supplies ids the assignments log lacks)
    tm = pd.read_parquet(REPO / "data" / "masters" / "master_team.parquet")
    tm["game_date"] = pd.to_datetime(tm.game_date)
    H = tm[tm.is_home == 1].copy()
    if "team_abbreviation" in H.columns:
        H["home"] = H.team_abbreviation
        ab = tm[["team_id", "team_abbreviation"]].drop_duplicates() \
            .set_index("team_id").team_abbreviation.to_dict()
        H["away"] = H.opp_team_id.map(ab)
        H["game_date"] = H.game_date.dt.date.astype(str)
        H["played_game_id"] = H.game_id.astype(str)
        S = S.merge(H[["game_date", "home", "away", "played_game_id"]],
                    on=["game_date", "home", "away"], how="left")
        S["game_id"] = S.game_id.fillna(S.played_game_id)
        S["completed"] = S.played_game_id.notna()
    else:
        S["completed"] = False
    return S


def _resolve_provisional(official: list, slate: pd.DataFrame) -> dict:
    """Map a base record's logged game_id to the slate game key.

    Records written before the real id existed carry PROV-<date>-<away>@<home>.
    Coverage is counted PER GAME, so those are resolved here. Pairing in the
    companion log is NOT resolved this way -- it references the base record's
    literal identity so the reference is verifiable from the two logs alone.
    """
    out = {}
    for r in official:
        gid = str(r.get("game_id"))
        c = r.get("core_only_prediction") or {}
        h, a = c.get("home_team"), c.get("away_team")
        if gid.startswith("PROV-"):
            parts = gid.split("-", 4)
            date = "-".join(parts[1:4]) if len(parts) >= 4 else None
            hit = slate[(slate.game_date == date) & (slate.home == h) & (slate.away == a)]
            out[gid] = str(hit.iloc[0].game_id) if len(hit) and pd.notna(hit.iloc[0].game_id) else gid
        else:
            out[gid] = gid
    return out


def audit(now=None) -> pd.DataFrame:
    now = _utc(now or datetime.now(timezone.utc))
    slate = build_slate()
    if slate.empty:
        return pd.DataFrame()
    official = read_official()
    alt = read_records()
    prov = _resolve_provisional(official, slate)

    # The period cannot start before its first record. Obligations whose cutoff
    # precedes the log's genesis are NOT misses -- the system did not exist yet.
    period_start = min((_utc(r["logged_at_utc"]) for r in official), default=None)

    # Which games the job served at (SLATE DATE, label). This must be keyed by date:
    # a global key would report "the job served 6 other games at T-8h" for a day it
    # never ran at all, dressing an operational miss as a game-specific data gap.
    gid_date = {str(g.game_id): g.game_date for g in slate.itertuples()
                if pd.notna(g.game_id)}
    served_at: dict[tuple, set] = {}
    for r in official:
        rgid = prov.get(str(r["game_id"]), str(r["game_id"]))
        d = gid_date.get(rgid)
        if d is not None:
            served_at.setdefault((d, r["decision_time_label"]), set()).add(rgid)

    rows = []
    for g in slate.itertuples():
        gid = str(g.game_id) if pd.notna(g.game_id) else None
        for label, hrs in CONTRACT_LABELS:
            cutoff = g.tip - timedelta(hours=hrs)
            recs = [r for r in official
                    if prov.get(str(r["game_id"]), str(r["game_id"])) == gid
                    and r["decision_time_label"] == label]
            arm = [r for r in alt if str(r["game_id"]) == gid
                   and r["decision_time_label"] == label]
            base = {"game_date": g.game_date, "home": g.home, "away": g.away,
                    "game_id": gid, "tip_utc": g.tip.isoformat(),
                    "decision_time_label": label, "cutoff_utc": cutoff.isoformat(),
                    "tip_moved": bool(g.tip_moved), "completed": bool(g.completed),
                    "n_base_records": len(recs), "n_arm_records": len(arm),
                    "arm_models": ",".join(sorted({r["model_id"] for r in arm})) or None}

            # An obligation is SERVED by its ORIGINAL record. Extra records for the same
            # (game, decision time) are commissioning duplicates: labelled, counted, and
            # excluded from every numerator -- but they must never turn an obligation
            # that WAS served into a missing one. `recs` is in chain order, so recs[0]
            # is the original.
            base["n_duplicate_records"] = max(0, len(recs) - 1)
            base["duplicate_record_idxs"] = ",".join(
                str(official.index(x)) for x in recs[1:]) or None
            if recs:
                r = recs[0]
                is_fc = (r.get("core_only_prediction") or {}).get("status", "forecast") == "forecast"
                created = _utc(r["logged_at_utc"])
                dup_note = (f" [+{len(recs) - 1} duplicate record(s), excluded]"
                            if len(recs) > 1 else "")
                if created > cutoff:
                    cls, why = "late_record", f"created {created.isoformat()} after cutoff{dup_note}"
                elif is_fc:
                    cls, why = "forecast_logged", (dup_note.strip() or None)
                else:
                    cls, why = "explicit_no_forecast", \
                        ((r["core_only_prediction"] or {}).get("no_forecast_reason") or "") + dup_note
            elif cutoff > now:
                cls, why = "not_yet_due", None
            elif period_start is not None and cutoff < period_start:
                cls, why = "before_period_start", \
                    f"cutoff precedes the log's first record ({period_start.isoformat()})"
            elif g.tip_moved:
                cls, why = "postponed_or_tip_changed", \
                    f"tip moved {g.tip_shift_min:+.0f} min between captures"
            elif not served_at.get((g.game_date, label)):
                cls, why = "missing_job_did_not_run", \
                    f"no base record for ANY game on {g.game_date} at {label}"
            else:
                cls, why = "missing_data_unavailable", \
                    ("job served %d other game(s) on %s at %s"
                     % (len(served_at[(g.game_date, label)]), g.game_date, label))
            rows.append({**base, "classification": cls, "reason": why})
    return pd.DataFrame(rows)


SERVED = ("forecast_logged", "explicit_no_forecast")
EXCLUDED = ("not_yet_due", "before_period_start", "postponed_or_tip_changed")
DUE = SERVED + ("missing_job_did_not_run", "missing_data_unavailable", "late_record")


def summarize(A: pd.DataFrame) -> dict:
    due = A[A.classification.isin(DUE)]
    served = due[due.classification.isin(SERVED)]
    misses = int((A.classification == "missing_job_did_not_run").sum())
    unexplained = int(due[~due.classification.isin(SERVED) & due.reason.isna()].shape[0])
    cov = (len(served) / len(due)) if len(due) else None
    return {
        "obligations_total": int(len(A)),
        "duplicate_records_excluded": int(A.n_duplicate_records.sum()),
        "obligations_due": int(len(due)),
        "served": int(len(served)),
        "coverage_served": cov,
        "not_yet_due": int((A.classification == "not_yet_due").sum()),
        "operational_misses": misses,
        "unexplained": unexplained,
        "promotion_grade": bool(
            cov is not None and cov >= MIN_COVERAGE_SERVED
            and misses <= MAX_OPERATIONAL_MISSES
            and (not REQUIRE_ALL_EXPLAINED or unexplained == 0)),
        "threshold": {"min_coverage_served": MIN_COVERAGE_SERVED,
                      "max_operational_misses": MAX_OPERATIONAL_MISSES,
                      "require_all_explained": REQUIRE_ALL_EXPLAINED},
    }


def main() -> None:
    A = audit()
    if A.empty:
        print("no slate could be assembled"); return
    print("=" * 100)
    print("FORECAST COVERAGE AUDIT   generated %s" % datetime.now(timezone.utc).isoformat())
    print("=" * 100)
    print("\nCUMULATIVE by classification")
    for k, v in A.classification.value_counts().items():
        print("  %-28s %d" % (k, v))
    s = summarize(A)
    print("\n  obligations %d | due %d | served %d | coverage %s"
          % (s["obligations_total"], s["obligations_due"], s["served"],
             "n/a" if s["coverage_served"] is None else "%.1f%%" % (100 * s["coverage_served"])))
    print("  operational misses %d | unexplained %d" % (s["operational_misses"], s["unexplained"]))
    print("  PROMOTION-GRADE: %s   (needs >= %.0f%% served, <= %d operational misses, all explained)"
          % ("YES" if s["promotion_grade"] else "NO",
             100 * MIN_COVERAGE_SERVED, MAX_OPERATIONAL_MISSES))

    print("\nDAILY")
    print("  %-12s %5s %7s %7s %8s %9s %8s" % ("date", "oblig", "served", "due", "excl",
                                               "opmiss", "arm_recs"))
    for d, g in A.groupby("game_date"):
        due = g[g.classification.isin(DUE)]
        print("  %-12s %5d %7d %7d %8d %9d %8d" % (
            d, len(g), int(g.classification.isin(SERVED).sum()), len(due),
            int(g.classification.isin(EXCLUDED).sum()),
            int((g.classification == "missing_job_did_not_run").sum()),
            int(g.n_arm_records.sum())))

    bad = A[~A.classification.isin(SERVED) & ~A.classification.isin(EXCLUDED)]
    if len(bad):
        print("\nEVERY MISSING OR IRREGULAR OBLIGATION (each must carry an explanation)")
        for r in bad.itertuples():
            print("  %s %s v %s %-7s %-26s %s" % (r.game_date, r.home, r.away,
                                                  r.decision_time_label, r.classification,
                                                  r.reason or "*** UNEXPLAINED ***"))
    outdir = REPO / "forecasts"
    outdir.mkdir(exist_ok=True)
    A.to_csv(outdir / "coverage_audit.csv", index=False)
    json.dump(s, open(outdir / "coverage_receipt.json", "w"), indent=2, default=str)
    print("\nwrote forecasts/coverage_audit.csv and forecasts/coverage_receipt.json")


if __name__ == "__main__":
    main()
