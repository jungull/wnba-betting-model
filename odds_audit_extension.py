#!/usr/bin/env python3
"""
odds_audit_extension.py — new-era odds audit (extension + live tables).

audit_completeness.py §6 reads only the OLD master (data/drive_masters/
master_odds.csv, ends 2025-07-04). This audit covers everything after:

  data/odds_capture/master_odds_extension.csv                (spreads)
  data/odds_capture/master_odds_extension_other_markets.csv  (h2h + totals)
  data/odds_capture/historical/hist_*.json                   (backfill era)
  data/odds_capture/live_*.json                              (live era)

LOCAL ONLY — no network. Read-only on all inputs; writes ONLY to
experiments/odds_audit_ext/ (REPORT.md + row-level evidence CSVs, one per
non-clean finding).

Checks
  1. inventory & CSV-vs-JSON integrity: per-snapshot spread-row counts in the
     extension CSV reconciled against the raw snapshot JSONs; extension
     staleness vs newest capture on disk.
  2. duplicates: full-row and key-level in both extension CSVs
     (key = the build's own dedupe key).
  3. market sanity: spread symmetry (home+away must sum to 0 per event/book/
     snapshot), absurd spread magnitudes, American-price validity, spread
     team names, totals Over/Under point agreement, h2h outcome counts.
  4. game_id mapping coverage vs the schedule: an INDEPENDENTLY rebuilt
     (ET date, home, away) -> GAME_ID index from the refresh gamelogs
     (deliberately not importing build_odds_master_extension's resolver);
     completed games without odds, games without pregame rows, unmatched
     events inside the completed range, game_ids fed by >1 event, game_ids
     absent from the gamelogs.
  5. snapshot cadence: hist era = 2 snapshots per game date (the backfill
     contract); live era = hourly 10:00-23:00 local (14/day); per-game
     largest pregame gap in the final 24h and minutes from last pregame
     snapshot to tip — the machine-off-weekend risk, quantified per game.
  6. book coverage over time: months x bookmaker event coverage, first/last
     sighting per book, continuity vs the old master's book set.
  7. stale-book scan over the FULL snapshot history (same 90-min pregame
     rule as daily_certify check 8, which only watches recent live files).
     Hist-era caveat: 15Z snapshots are 10/11am ET — books that simply had
     not refreshed morning lines yet lag honestly; the report separates the
     eras so live-era staleness is judged on its own.
  8. postponements / tip-time changes over the full extension history:
     distinct commence_time per api_event_id in snapshot order (before ->
     after), plus events that vanish from the feed while still pregame
     (the postpone-then-relist pattern; known case 51f9e00b -> f8d499fa).

Thresholds (documented, hand-chosen):
  STALE_MIN        90   min  — book quote older than this at capture = stale
                              (captures are hourly; >90 min predates the
                              previous snapshot entirely)
  SPREAD_ABSURD    25   pts  — no WNBA spread has ever plausibly exceeded it
  SPREAD_REVIEW    20   pts  — legit but rare; listed for eyeballing
  TOTAL_RANGE      120-220   — plausible WNBA totals band (hard 100-250)
  PRICE_VALID      |p| >= 100 and |p| <= 5000 (American odds)
  VANISH_GRACE     30   min  — pregame margin before a vanish alarms
"""
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
CAP = ROOT / "data" / "odds_capture"
HIST = CAP / "historical"
REFRESH = ROOT / "data" / "refresh_2026"
OUT = ROOT / "experiments" / "odds_audit_ext"

MAIN_CSV = CAP / "master_odds_extension.csv"
OTHER_CSV = CAP / "master_odds_extension_other_markets.csv"
OLD_MASTER = ROOT / "data" / "drive_masters" / "master_odds.csv"

STALE_MIN = 90
SPREAD_ABSURD = 25.0
SPREAD_REVIEW = 20.0
TOTAL_HARD = (100.0, 250.0)
TOTAL_BAND = (120.0, 220.0)
PRICE_MIN, PRICE_MAX = 100, 5000
VANISH_GRACE_MIN = 30
LIVE_WINDOW = (10, 23)          # hourly capture window, local time (daily_certify)

lines, problems, evidence = [], [], []


def note(s=""):
    print(s)
    lines.append(s)


def finding(name, df, filename, desc):
    """Register a finding: writes the evidence CSV when non-empty."""
    n = len(df)
    if n:
        path = OUT / filename
        df.to_csv(path, index=False)
        evidence.append((name, n, filename))
        problems.append(f"{name}: {n} rows ({filename})")
        note(f"**{n}** {desc} -> `{filename}`")
    else:
        evidence.append((name, 0, ""))
        note(f"0 {desc} — clean")
    return n


def iso_utc(s):
    try:
        dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# snapshot iteration (raw JSONs)
# ---------------------------------------------------------------------------

def iter_snapshots():
    """Yield (kind, snap_key, snap_utc, events, filename) for every snapshot.
    snap_key matches the extension CSV's odds_snapshot_timestamp exactly:
    the wrapper timestamp for hist files, the filename ISO for live files."""
    for f in sorted(HIST.glob("hist_*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            yield "hist", None, None, None, f.name
            continue
        yield "hist", d.get("timestamp"), iso_utc(d.get("timestamp")), \
            d.get("data", []), f.name
    for f in sorted(CAP.glob("live_*.json")):
        m = re.match(r"live_(\d{8})T(\d{6})Z\.json", f.name)
        if not m:
            continue
        ds, ts = m.group(1), m.group(2)
        key = f"{ds[:4]}-{ds[4:6]}-{ds[6:]}T{ts[:2]}:{ts[2:4]}:{ts[4:]}Z"
        try:
            events = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            yield "live", key, iso_utc(key), None, f.name
            continue
        yield "live", key, iso_utc(key), events, f.name


# ---------------------------------------------------------------------------
# independent (ET date, home, away) -> GAME_ID index from refresh gamelogs
# ---------------------------------------------------------------------------

def game_index():
    files = sorted(REFRESH.glob("gamelog_team_2025_*.parquet")) + \
            sorted(REFRESH.glob("gamelog_team_2026_*.parquet"))
    if not files:
        sys.exit("no refresh gamelogs under data/refresh_2026/")
    g = pd.concat([pd.read_parquet(f, columns=["GAME_ID", "GAME_DATE",
                                               "MATCHUP", "TEAM_NAME"])
                   for f in files], ignore_index=True)
    g["GAME_ID"] = g["GAME_ID"].astype(str).str.zfill(10)
    home = g[g["MATCHUP"].str.contains("vs.", regex=False)]
    away = g[g["MATCHUP"].str.contains("@", regex=False)]
    pair = home.merge(away[["GAME_ID", "TEAM_NAME"]], on="GAME_ID",
                      suffixes=("_home", "_away"))
    pair = pair.rename(columns={"TEAM_NAME_home": "home_team",
                                "TEAM_NAME_away": "away_team",
                                "GAME_DATE": "et_date"})
    pair["et_date"] = pair["et_date"].astype(str)
    return pair[["GAME_ID", "et_date", "home_team", "away_team"]]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    note("# Odds audit — extension + live tables (new era)")
    note(f"\nGenerated by odds_audit_extension.py, "
         f"{datetime.now().astimezone().isoformat(timespec='seconds')}. "
         f"Old-master coverage (2022 -> 2025-07-04) stays with "
         f"audit_completeness.py §6; this audit owns everything after.")

    if not MAIN_CSV.exists():
        sys.exit(f"missing {MAIN_CSV}")
    dfm = pd.read_csv(MAIN_CSV, dtype=str)
    dfo = pd.read_csv(OTHER_CSV, dtype=str) if OTHER_CSV.exists() else pd.DataFrame()
    for d in (dfm, dfo):
        if len(d):
            d["spread_f"] = pd.to_numeric(d.get("odds_spread"), errors="coerce")
            d["point_f"] = pd.to_numeric(d.get("outcome_point"), errors="coerce")
            d["price_f"] = pd.to_numeric(
                d["odds_price"] if "odds_price" in d else d.get("outcome_price"),
                errors="coerce")
            d["snap_utc"] = pd.to_datetime(d["odds_snapshot_timestamp"],
                                           utc=True, format="mixed")
            d["commence_utc"] = pd.to_datetime(d["odds_commence_time"],
                                               utc=True, format="mixed")
            d["game_id"] = d["game_id"].fillna("")

    # ---- 1. inventory & CSV-vs-JSON integrity -----------------------------
    note("\n## 1. Inventory & extension-vs-raw integrity")
    json_census = {}          # snap_key -> dict(kind, n_events, n_spread_rows)
    unreadable = []
    stale_scan = []           # (kind, snap_key, book, lag_min, matchup)
    sightings = defaultdict(list)   # eid -> [(snap_utc, commence, home, away)]
    snap_times = []
    for kind, key, snap_t, events, fname in iter_snapshots():
        if events is None:
            unreadable.append(fname)
            continue
        snap_times.append((snap_t, kind))
        n_spread = 0
        for ev in events:
            sightings[ev.get("id")].append(
                (snap_t, ev.get("commence_time"), ev.get("home_team"),
                 ev.get("away_team")))
            commence = iso_utc(ev.get("commence_time"))
            pregame = commence is not None and commence > snap_t
            for bm in ev.get("bookmakers", []):
                upds = []
                for mk in bm.get("markets", []):
                    if mk.get("key") == "spreads":
                        n_spread += len(mk.get("outcomes", []))
                    u = iso_utc(mk.get("last_update"))
                    if u:
                        upds.append(u)
                if not upds:
                    u = iso_utc(bm.get("last_update"))
                    upds = [u] if u else []
                if pregame and upds:
                    lag = max((snap_t - max(upds)).total_seconds() / 60.0, 0.0)
                    stale_scan.append((kind, key, bm.get("key"), lag,
                                       f"{ev.get('away_team')} @ {ev.get('home_team')}"))
        json_census[key] = {"kind": kind, "n_events": len(events),
                            "n_spread_rows": n_spread, "file": fname}
    n_hist = sum(1 for v in json_census.values() if v["kind"] == "hist")
    n_live = len(json_census) - n_hist
    note(f"\nsnapshot files on disk: {n_hist} hist + {n_live} live "
         f"(+{len(unreadable)} unreadable: {unreadable or 'none'})")
    note(f"extension spreads rows: {len(dfm)} | other-markets rows: {len(dfo)}")
    note(f"extension snapshot span: {dfm['odds_snapshot_timestamp'].min()} -> "
         f"{dfm['odds_snapshot_timestamp'].max()}")
    if unreadable:
        problems.append(f"{len(unreadable)} unreadable snapshot JSONs")

    csv_census = dfm.groupby("odds_snapshot_timestamp").size()
    rows_int = []
    for key, v in json_census.items():
        got = int(csv_census.get(key, 0))
        if got != v["n_spread_rows"]:
            rows_int.append({"snapshot": key, "kind": v["kind"], "file": v["file"],
                             "spread_rows_in_json": v["n_spread_rows"],
                             "spread_rows_in_csv": got})
    for key, got in csv_census.items():
        if key not in json_census:
            rows_int.append({"snapshot": key, "kind": "csv-only", "file": "",
                             "spread_rows_in_json": 0,
                             "spread_rows_in_csv": int(got)})
    finding("csv-vs-json row counts", pd.DataFrame(rows_int),
            "ev_snapshot_rowcount_mismatch.csv",
            "snapshots whose extension spread-row count differs from the raw "
            "JSON (or exist on one side only)")
    newest_disk = max((t for t, _ in snap_times if t), default=None)
    newest_csv = dfm["snap_utc"].max()
    if newest_disk and newest_disk - newest_csv > timedelta(minutes=1):
        lag_h = (newest_disk - newest_csv).total_seconds() / 3600
        note(f"\nNOTE: extension CSV is **{lag_h:.1f} h behind** the newest "
             f"snapshot on disk ({newest_disk.isoformat()}) — rerun "
             f"build_odds_master_extension.py to fold in the latest captures "
             f"(expected between rebuilds; listed so nobody trusts the CSV "
             f"as live).")
        problems.append(f"extension CSV {lag_h:.1f} h behind newest capture "
                        f"(rebuild is manual)")

    # ---- 2. duplicates ----------------------------------------------------
    note("\n## 2. Duplicates")
    full_dup_m = dfm[dfm.duplicated(keep=False)]
    finding("full-row dupes (spreads)", full_dup_m.head(2000),
            "ev_duplicate_rows_main.csv", "fully identical spread rows")
    key_m = ["api_event_id", "bookmaker_key", "team", "odds_snapshot_timestamp"]
    key_dup_m = dfm[dfm.duplicated(subset=key_m, keep=False) & ~dfm.duplicated(keep=False)]
    finding("key dupes (spreads)", key_dup_m,
            "ev_duplicate_keys_main.csv",
            f"spread rows sharing the build key {key_m} with different content")
    if len(dfo):
        full_dup_o = dfo[dfo.duplicated(keep=False)]
        finding("full-row dupes (other)", full_dup_o.head(2000),
                "ev_duplicate_rows_other.csv", "fully identical h2h/totals rows")
        key_o = ["api_event_id", "bookmaker_key", "market_key", "outcome_name",
                 "odds_snapshot_timestamp"]
        key_dup_o = dfo[dfo.duplicated(subset=key_o, keep=False)
                        & ~dfo.duplicated(keep=False)]
        finding("key dupes (other)", key_dup_o,
                "ev_duplicate_keys_other.csv",
                "h2h/totals rows sharing the build key with different content")

    # ---- 3. market sanity -------------------------------------------------
    note("\n## 3. Market sanity")
    grp = dfm.groupby(["api_event_id", "bookmaker_key",
                       "odds_snapshot_timestamp"])
    sym = grp.agg(n_sides=("team", "nunique"), n_rows=("team", "size"),
                  sum_spread=("spread_f", "sum"),
                  home_team=("home_team", "first"),
                  away_team=("away_team", "first"),
                  matchup_date=("matchup_date", "first")).reset_index()
    asym = sym[(sym["n_rows"] != 2) | (sym["n_sides"] != 2) |
               (sym["sum_spread"].abs() > 1e-9)]
    finding("spread symmetry", asym, "ev_spread_asymmetry.csv",
            "event/book/snapshot groups without exactly two sides summing to 0")

    # In-play rows (snapshot at/after commence) are kept by design in the
    # extension (see build_odds_master_extension NOTE); extreme values there
    # are real market states, not defects. Only PREGAME extremes are bugs.
    inplay = dfm["snap_utc"] >= dfm["commence_utc"]
    absurd = dfm[(dfm["spread_f"].abs() > SPREAD_ABSURD) & ~inplay]
    finding(f"absurd PREGAME spreads (|s|>{SPREAD_ABSURD:g})", absurd,
            "ev_spread_absurd.csv",
            f"pregame spread rows with |spread| > {SPREAD_ABSURD:g}")
    absurd_ip = dfm[(dfm["spread_f"].abs() > SPREAD_ABSURD) & inplay]
    if len(absurd_ip):
        absurd_ip.to_csv(OUT / "ev_spread_absurd_inplay.csv", index=False)
        evidence.append(("in-play extreme spreads", len(absurd_ip),
                         "ev_spread_absurd_inplay.csv"))
        note(f"({len(absurd_ip)} rows with |spread| > {SPREAD_ABSURD:g} are "
             f"IN-PLAY captures (snapshot >= commence; e.g. the 22Z backfill "
             f"grid catching a blowout in progress) — real market states, "
             f"filter by timestamp downstream -> `ev_spread_absurd_inplay.csv`)")
    review = dfm[(dfm["spread_f"].abs() > SPREAD_REVIEW)
                 & (dfm["spread_f"].abs() <= SPREAD_ABSURD) & ~inplay]
    if len(review):
        rv = (review.groupby(["api_event_id", "home_team", "away_team",
                              "matchup_date"])["spread_f"]
              .agg(["min", "max", "size"]).reset_index())
        rv.to_csv(OUT / "ev_spread_review_band.csv", index=False)
        evidence.append(("review-band spreads", len(rv), "ev_spread_review_band.csv"))
        note(f"{len(review)} rows in the {SPREAD_REVIEW:g}-{SPREAD_ABSURD:g} "
             f"review band across {len(rv)} events (legit blowout lines; "
             f"listed, not a defect) -> `ev_spread_review_band.csv`")
    missing_spread = dfm[dfm["spread_f"].isna()]
    finding("unparseable spread points", missing_spread,
            "ev_spread_unparseable.csv", "spread rows with non-numeric point")

    badp = dfm["price_f"].isna() | (dfm["price_f"].abs() < PRICE_MIN) \
        | (dfm["price_f"].abs() > PRICE_MAX)
    finding("invalid American prices (spreads, pregame)", dfm[badp & ~inplay],
            "ev_price_invalid_main.csv",
            f"pregame spread rows with price missing, |p|<{PRICE_MIN} or "
            f"|p|>{PRICE_MAX}")
    if (badp & inplay).sum():
        dfm[badp & inplay].to_csv(OUT / "ev_price_extreme_inplay_main.csv",
                                  index=False)
        evidence.append(("in-play extreme prices (spreads)",
                         int((badp & inplay).sum()),
                         "ev_price_extreme_inplay_main.csv"))
        note(f"({int((badp & inplay).sum())} extreme spread prices are "
             f"in-play rows — real, filter by timestamp -> "
             f"`ev_price_extreme_inplay_main.csv`)")

    namebad = dfm[(dfm["team"] != dfm["home_team"])
                  & (dfm["team"] != dfm["away_team"])]
    finding("spread team-name mismatches", namebad,
            "ev_team_name_mismatch.csv",
            "spread rows whose team is neither the event's home nor away")

    if len(dfo):
        tot = dfo[dfo["market_key"] == "totals"]
        tgrp = tot.groupby(["api_event_id", "bookmaker_key",
                            "odds_snapshot_timestamp"])
        tchk = tgrp.agg(n_outcomes=("outcome_name", "nunique"),
                        n_points=("point_f", "nunique"),
                        point_min=("point_f", "min"),
                        home_team=("home_team", "first"),
                        away_team=("away_team", "first")).reset_index()
        badtot = tchk[(tchk["n_outcomes"] != 2) | (tchk["n_points"] != 1)]
        finding("totals Over/Under agreement", badtot,
                "ev_totals_point_mismatch.csv",
                "totals groups without exactly Over+Under on one shared point")
        offband = tchk[(tchk["point_min"] < TOTAL_BAND[0])
                       | (tchk["point_min"] > TOTAL_BAND[1])]
        hard = tchk[(tchk["point_min"] < TOTAL_HARD[0])
                    | (tchk["point_min"] > TOTAL_HARD[1])]
        finding(f"totals outside hard range {TOTAL_HARD}", hard,
                "ev_totals_absurd.csv", "totals outside the hard plausibility range")
        if len(offband) and not len(hard):
            note(f"({len(offband)} totals outside the soft {TOTAL_BAND} band "
                 f"but inside hard limits — fine)")
        h2h = dfo[dfo["market_key"] == "h2h"]
        hgrp = (h2h.groupby(["api_event_id", "bookmaker_key",
                             "odds_snapshot_timestamp"])["outcome_name"]
                .nunique().reset_index(name="n_outcomes"))
        finding("h2h outcome counts", hgrp[hgrp["n_outcomes"] != 2],
                "ev_h2h_outcome_count.csv",
                "h2h groups without exactly two outcomes")
        inplay_o = dfo["snap_utc"] >= dfo["commence_utc"]
        badp_o = dfo["price_f"].isna() | (dfo["price_f"].abs() < PRICE_MIN) \
            | (dfo["price_f"].abs() > PRICE_MAX)
        finding("invalid American prices (other, pregame)",
                dfo[badp_o & ~inplay_o], "ev_price_invalid_other.csv",
                "pregame h2h/totals rows with missing or out-of-range price")
        if (badp_o & inplay_o).sum():
            dfo[badp_o & inplay_o].to_csv(
                OUT / "ev_price_extreme_inplay_other.csv", index=False)
            evidence.append(("in-play extreme prices (other)",
                             int((badp_o & inplay_o).sum()),
                             "ev_price_extreme_inplay_other.csv"))
            note(f"({int((badp_o & inplay_o).sum())} extreme h2h/totals "
                 f"prices are in-play rows (huge favorites late in games) — "
                 f"real, filter by timestamp -> "
                 f"`ev_price_extreme_inplay_other.csv`)")

    # ---- 4. game_id mapping coverage vs schedule --------------------------
    note("\n## 4. game_id mapping vs the schedule (independent index)")
    gi = game_index()
    window_lo = "2025-07-05"                      # extension era begins here
    gi_win = gi[gi["et_date"] >= window_lo].copy()
    max_glog = gi["et_date"].max()
    note(f"\ncompleted games in the extension window ({window_lo} .. "
         f"{max_glog}): {len(gi_win)}")
    ext_gids = set(dfm.loc[dfm["game_id"] != "", "game_id"])
    note(f"distinct game_ids carrying odds in the extension: {len(ext_gids)}")

    missing = gi_win[~gi_win["GAME_ID"].isin(ext_gids)]
    finding("completed games without odds", missing,
            "ev_games_missing_odds.csv",
            "completed games in the window with zero extension odds rows")

    pre = dfm[dfm["snap_utc"] < dfm["commence_utc"]]
    pre_gids = set(pre.loc[pre["game_id"] != "", "game_id"])
    nopregame = gi_win[gi_win["GAME_ID"].isin(ext_gids - pre_gids)]
    finding("games with only in-play odds", nopregame,
            "ev_games_no_pregame.csv",
            "covered games whose every extension row is at/after tip "
            "(unusable for pregame cutoffs)")

    per_season = []
    for season, grp_ in gi_win.groupby(gi_win["GAME_ID"].str[3:5]):
        got = grp_["GAME_ID"].isin(ext_gids).sum()
        per_season.append(f"| 20{season} | {len(grp_)} | {got} "
                          f"| {got / len(grp_) * 100:.0f}% |")
    note("\n| season | completed games in window | with odds | coverage |")
    note("|---|---|---|---|")
    for r in per_season:
        note(r)

    ev_last = {eid: max(s, key=lambda x: x[0]) for eid, s in sightings.items()
               if any(x[0] for x in s)}
    ext_events = dfm.groupby("api_event_id").agg(
        game_id=("game_id", "first"), home_team=("home_team", "last"),
        away_team=("away_team", "last"),
        last_matchup_date=("matchup_date", "last"),
        last_commence=("odds_commence_time", "last"),
        n_rows=("game_id", "size")).reset_index()
    ext_events["last_et_date"] = (
        pd.to_datetime(ext_events["last_commence"], utc=True, format="mixed")
        .dt.tz_convert("America/New_York").dt.date.astype(str))
    unmatched = ext_events[(ext_events["game_id"] == "")
                           & (ext_events["last_et_date"] <= max_glog)]
    finding("unmatched events in completed range", unmatched,
            "ev_unmatched_completed_events.csv",
            "events with no game_id whose last-quoted ET date is inside the "
            "completed-gamelog range (expected: only the non-gamelog "
            "Commissioner's Cup final)")

    multi = (dfm[dfm["game_id"] != ""].groupby("game_id")["api_event_id"]
             .nunique())
    multi = multi[multi > 1].reset_index(name="n_events")
    if len(multi):
        multi = multi.merge(
            dfm[dfm["game_id"] != ""][["game_id", "api_event_id"]]
            .drop_duplicates(), on="game_id")
    finding("game_ids fed by >1 event", multi, "ev_gameid_multi_event.csv",
            "game_ids mapped from multiple api events (reschedule dups — "
            "closing-line work must pick the final listing)")

    bogus = sorted(ext_gids - set(gi["GAME_ID"]))
    finding("mapped game_ids absent from gamelogs",
            pd.DataFrame({"game_id": bogus}), "ev_gameid_not_in_gamelogs.csv",
            "extension game_ids that do not exist in the refresh gamelogs")

    # ---- 5. snapshot cadence ----------------------------------------------
    note("\n## 5. Snapshot cadence (the machine-off risk)")
    hist_dates = defaultdict(int)
    for key, v in json_census.items():
        if v["kind"] == "hist":
            hist_dates[v["file"][5:15]] += 1        # hist_YYYY-MM-DD_HHZ.json
    live_day_hours = defaultdict(set)
    for t, kind in snap_times:
        if kind == "live" and t:
            loc = t.astimezone()
            live_day_hours[str(loc.date())].add(loc.hour)

    first_live_date = min(live_day_hours) if live_day_hours else None
    game_dates = sorted(set(gi_win["et_date"]))
    hist_rows = []
    for d in game_dates:
        if first_live_date and d >= first_live_date:
            continue                                 # live era covers it
        n = hist_dates.get(d, 0)
        if n < 2:
            hist_rows.append({"et_game_date": d, "hist_snapshots": n,
                              "games": int((gi_win["et_date"] == d).sum())})
    finding("hist-era game dates below 2 snapshots", pd.DataFrame(hist_rows),
            "ev_hist_cadence_gaps.csv",
            "pre-live game dates with fewer than the contracted 2 backfill "
            "snapshots")
    extra_hist = sorted(set(hist_dates) - set(game_dates))
    if extra_hist:
        note(f"({len(extra_hist)} hist snapshot dates with no completed game "
             f"— harmless: future/postponed listings; e.g. {extra_hist[:4]})")

    live_rows = []
    today_local = datetime.now().astimezone()
    for d, hours in sorted(live_day_hours.items()):
        lo, hi = LIVE_WINDOW
        expect = set(range(lo, hi + 1))
        if d == str(today_local.date()):
            expect = {h for h in expect if h <= today_local.hour}
        if d == first_live_date:
            expect = {h for h in expect if h >= min(hours)}   # capture began mid-day
        missing_h = sorted(expect - hours)
        if missing_h:
            live_rows.append({"local_date": d, "captures": len(hours),
                              "expected": len(expect),
                              "missing_hours": ",".join(map(str, missing_h))})
    finding("live-era days with missed hourly slots", pd.DataFrame(live_rows),
            "ev_live_cadence_gaps.csv",
            "live-capture days missing hourly 10:00-23:00 slots")
    note(f"(live era began {first_live_date}; days observed: "
         f"{len(live_day_hours)}. A machine-off weekend would surface here "
         f"as whole missing days — and in ev_per_game_pregame_cadence.csv "
         f"as games with no near-tip snapshot.)")

    snap_ts_sorted = sorted(t for t, _ in snap_times if t)
    cad_rows = []
    for _, g in gi_win.iterrows():
        ext_g = dfm[dfm["game_id"] == g["GAME_ID"]]
        if not len(ext_g):
            continue
        tip = ext_g["commence_utc"].max()
        w0 = tip - timedelta(hours=24)
        in_win = sorted({t for t in ext_g.loc[(ext_g["snap_utc"] >= w0)
                                              & (ext_g["snap_utc"] < tip),
                                              "snap_utc"]})
        if in_win:
            seq = [w0] + in_win + [tip]
            biggest = max((b - a).total_seconds() / 60.0
                          for a, b in zip(seq, seq[1:]))
            last_to_tip = (tip - in_win[-1]).total_seconds() / 60.0
        else:
            biggest, last_to_tip = 24 * 60.0, 24 * 60.0
        cad_rows.append({"game_id": g["GAME_ID"], "et_date": g["et_date"],
                         "home": g["home_team"], "away": g["away_team"],
                         "n_snapshots_last24h": len(in_win),
                         "largest_gap_min": round(biggest),
                         "last_snapshot_to_tip_min": round(last_to_tip)})
    cad = pd.DataFrame(cad_rows)
    if len(cad):
        cad.to_csv(OUT / "ev_per_game_pregame_cadence.csv", index=False)
        evidence.append(("per-game pregame cadence", len(cad),
                         "ev_per_game_pregame_cadence.csv"))
        note(f"\nper-game final-24h cadence over {len(cad)} covered games -> "
             f"`ev_per_game_pregame_cadence.csv`")
        note(f"- last pregame snapshot to tip: median "
             f"{cad['last_snapshot_to_tip_min'].median():.0f} min, p90 "
             f"{cad['last_snapshot_to_tip_min'].quantile(.9):.0f} min, max "
             f"{cad['last_snapshot_to_tip_min'].max():.0f} min")
        no_near_tip = cad[cad["last_snapshot_to_tip_min"] > 180]
        note(f"- games with NO snapshot within 3h of tip: {len(no_near_tip)} "
             f"of {len(cad)} ({len(no_near_tip) / len(cad) * 100:.0f}%) — the "
             f"structural cost of the 2/day backfill grid; hourly live "
             f"capture is what fixes it going forward")

    # ---- 6. book coverage over time ---------------------------------------
    note("\n## 6. Book coverage over time")
    dfm["month"] = dfm["snap_utc"].dt.strftime("%Y-%m")
    bk = (dfm.groupby(["bookmaker_key", "month"])
          .agg(n_events=("api_event_id", "nunique"),
               n_rows=("api_event_id", "size")).reset_index())
    bk.to_csv(OUT / "ev_book_coverage_monthly.csv", index=False)
    evidence.append(("book coverage by month", len(bk),
                     "ev_book_coverage_monthly.csv"))
    piv = bk.pivot(index="bookmaker_key", columns="month",
                   values="n_events").fillna(0).astype(int)
    note("\nevents quoted per book x month (`ev_book_coverage_monthly.csv`):\n")
    note("```")
    note(piv.to_string())
    note("```")
    span = (dfm.groupby("bookmaker_key")["snap_utc"].agg(["min", "max"])
            .astype(str).reset_index()
            .rename(columns={"min": "first_seen", "max": "last_seen"}))
    stale_books = span[span["last_seen"] < str(dfm["snap_utc"].max())[:10]]
    if len(stale_books):
        note(f"\nbooks absent from the newest snapshot day: "
             f"{stale_books['bookmaker_key'].tolist()}")
    if OLD_MASTER.exists():
        old_books = set(pd.read_csv(OLD_MASTER, usecols=["bookmaker_key"],
                                    low_memory=False)["bookmaker_key"].dropna())
        new_books = set(dfm["bookmaker_key"].dropna())
        note(f"\nold master had {len(old_books)} books; extension has "
             f"{len(new_books)}.")
        note(f"- gone since the old era: {sorted(old_books - new_books)}")
        note(f"- new in the extension era: {sorted(new_books - old_books)}")

    # ---- 7. stale books, full history -------------------------------------
    note("\n## 7. Stale-book scan, full snapshot history "
         f"(pregame, threshold {STALE_MIN} min)")
    ss = pd.DataFrame(stale_scan,
                      columns=["era", "snapshot", "book", "lag_min", "matchup"])
    if len(ss):
        summ = (ss.groupby(["era", "book"])["lag_min"]
                .agg(sightings="size", median_lag="median",
                     p90_lag=lambda s: s.quantile(.9), max_lag="max",
                     n_stale=lambda s: (s > STALE_MIN).sum())
                .round(1).reset_index())
        summ["stale_share"] = (summ["n_stale"] / summ["sightings"]).round(3)
        summ.to_csv(OUT / "ev_stale_book_full_history.csv", index=False)
        evidence.append(("stale-book history", len(summ),
                         "ev_stale_book_full_history.csv"))
        note("\nper era x book (`ev_stale_book_full_history.csv`):\n")
        note("```")
        note(summ.sort_values(["era", "stale_share"],
                              ascending=[True, False]).to_string(index=False))
        note("```")
        worst = ss[ss["lag_min"] > STALE_MIN].sort_values("lag_min",
                                                          ascending=False)
        finding("stale sightings (full history)", worst,
                "ev_stale_sightings.csv",
                f"book sightings > {STALE_MIN} min behind their snapshot "
                f"(hist 15Z rows are 10/11am ET — morning lag there is "
                f"honest history, not a capture defect; judge the live era "
                f"separately)")

    # ---- 8. postponements / tip-time changes, full history ----------------
    note("\n## 8. Postponements & tip-time changes, full history")
    ext_all = pd.concat(
        [dfm[["api_event_id", "home_team", "away_team", "odds_commence_time",
              "odds_snapshot_timestamp", "snap_utc"]],
         dfo[["api_event_id", "home_team", "away_team", "odds_commence_time",
              "odds_snapshot_timestamp", "snap_utc"]]] if len(dfo) else
        [dfm[["api_event_id", "home_team", "away_team", "odds_commence_time",
              "odds_snapshot_timestamp", "snap_utc"]]],
        ignore_index=True).drop_duplicates(
            subset=["api_event_id", "odds_commence_time",
                    "odds_snapshot_timestamp"])
    ext_all = ext_all.sort_values(["api_event_id", "snap_utc"])
    chg_rows = []
    for eid, g in ext_all.groupby("api_event_id"):
        seq = g.drop_duplicates(subset="odds_commence_time", keep="first")
        if len(seq) > 1:
            rs = seq.to_dict("records")
            for a, b in zip(rs, rs[1:]):
                # post-tip refinement = the API's routine correction of
                # commence to the actual tip, first observed at/after tip;
                # pregame reschedule = the change was visible before tip —
                # the kind that moves decision cutoffs.
                seen = b["snap_utc"]
                after = iso_utc(b["odds_commence_time"])
                kind_ = ("post-tip refinement"
                         if after is not None and seen >= after
                         else "pregame reschedule")
                chg_rows.append({
                    "api_event_id": eid, "away": b["away_team"],
                    "home": b["home_team"],
                    "commence_before": a["odds_commence_time"],
                    "commence_after": b["odds_commence_time"],
                    "first_seen_snapshot": b["odds_snapshot_timestamp"],
                    "kind": kind_})
    chg = pd.DataFrame(chg_rows)
    finding("commence_time changes", chg, "ev_tip_changes.csv",
            "events whose quoted commence_time changed across snapshots "
            "(before -> after)")
    if len(chg):
        kc = chg["kind"].value_counts().to_dict()
        note(f"- of these, {kc.get('pregame reschedule', 0)} are pregame "
             f"reschedules (cutoff-moving) and {kc.get('post-tip refinement', 0)} "
             f"are post-tip refinements (the API firming commence to the "
             f"actual tip — routine; ROADMAP's 'tip time known-at-capture' "
             f"rule means consumers must read commence per snapshot anyway)")

    all_snaps = sorted(t for t, _ in snap_times if t)
    van_rows = []
    for eid, seen in sightings.items():
        seen = [s for s in seen if s[0]]
        if not seen:
            continue
        last_t, last_c, h, a = max(seen, key=lambda x: x[0])
        later = [t for t in all_snaps if t > last_t]
        if not later:
            continue
        c = iso_utc(last_c)
        if c and c > later[0] + timedelta(minutes=VANISH_GRACE_MIN):
            van_rows.append({"api_event_id": eid, "away": a, "home": h,
                             "last_quoted_commence": last_c,
                             "last_seen_snapshot": last_t.isoformat(),
                             "next_snapshot_missing_it": later[0].isoformat()})
    finding("pregame vanishes", pd.DataFrame(van_rows),
            "ev_vanished_events.csv",
            "events that left the feed while still pregame (postpone/relist "
            "pattern; 51f9e00b -> f8d499fa is the documented 2026 case)")

    # ---- 9. companion artifact: PBP full reconciliation -------------------
    pbp_csv = OUT / "pbp_full_reconciliation.csv"
    if pbp_csv.exists():
        note("\n## 9. Companion artifact: PBP full-history score reconciliation")
        pr = pd.read_csv(pbp_csv, dtype={"game_id": str})
        n_bad = int((pr["exact_vs_master"] == False).sum())  # noqa: E712
        quirk = pr[(pr["n_dup_rows_dropped"] > 0)
                   | (pr["n_conflicting_dup_keys"] > 0)
                   | (pr["n_checkpoint_mismatch"] > 0)
                   | (pr["n_unattributed_pts"] > 0)]
        note(f"\n`pbp_full_reconciliation.csv` (written by `daily_certify.py "
             f"--full`, check 7): {len(pr)} games, "
             f"{len(pr) - n_bad} recomputed finals exactly matching "
             f"master_team, {n_bad} non-exact; {len(quirk)} games carry "
             f"integrity quirks (duplicated event rows / transient posted-"
             f"score checkpoint mismatches) with exact finals — row-level "
             f"detail in the CSV.")
        evidence.append(("pbp full reconciliation", len(pr),
                         "pbp_full_reconciliation.csv"))
        if n_bad:
            problems.append(f"PBP: {n_bad} games with non-exact recomputed "
                            f"finals (see pbp_full_reconciliation.csv)")

    # ---- verdict ----------------------------------------------------------
    note("\n## Verdict & evidence index")
    real = [p for p in problems]
    if real:
        note("\n**Findings (each with row-level evidence):**")
        for p in real:
            note(f"- {p}")
    else:
        note("\n**CLEAN — every check passed.**")
    note("\n| check | rows | evidence |")
    note("|---|---|---|")
    for name, n, f in evidence:
        note(f"| {name} | {n} | {f or '(clean)'} |")

    (OUT / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nreport -> {OUT / 'REPORT.md'}")


if __name__ == "__main__":
    main()
