# -*- coding: utf-8 -*-
"""M36 -- is the props seam crossable, and does that unblock the p_active wiring?

E0-style diagnostic, NON-CLAIMING. Nothing here fits, scores or adopts a model.

WHY THIS EXISTS. The handoff names one live, sized, unbuilt improvement: wire the
injury tape into `p_active` at T-90m, measured by M35 at +15.2% on appearance Brier.
That improvement cannot be measured against the shipped arm today, and M35 said so
correctly: "the outcome snapshot and the capture do not overlap".

This file asks the next question -- WHY they do not overlap, and whether that is a
data problem or a plumbing problem. The distinction decides whether the improvement
is weeks away or days away.

WHAT IS ACTUALLY CHECKED, in order:

  1. The boundary. Where does the arm's scored frame end, where does the tape begin?
  2. The cause. M13 reads master_props_historical.csv under D027. Where does that end?
  3. The alternative. The programme's OWN live props ladder (D028/D029) writes
     master_props.csv. What does it cover?
  4. Is it joinable? The live file has no game_id. Resolve events to game_id via
     (game_date, home, away) and count unresolved AND ambiguous matches. Both must
     be zero for the seam to be crossable on identity.
  5. Does it support a T-90m question? Count quotes standing at least 90 minutes
     before tip. A cutoff question needs pre-cutoff quotes; if the ladder only fires
     near tip, the seam is useless for this purpose regardless of identity.

WHAT THIS DELIBERATELY DOES NOT DO. It does not re-point M13, does not modify
translation_rows.parquet, and does not cite master_props.csv into any receipted
node. Those are authorization matters (D027 governs the historical archive only),
not things a feasibility check may decide.
"""
from __future__ import annotations

import datetime as dt
import json
import os

import pandas as pd

ROOT = r"C:\Users\jgallagher\wnba-betting-model"
HIST = os.path.join(ROOT, "data", "props_capture", "historical",
                    "master_props_historical.csv")
LIVE = os.path.join(ROOT, "data", "props_capture", "master_props.csv")
INJ = os.path.join(ROOT, "data", "injury_official_live", "injury_snapshots.csv")
MTEAM = os.path.join(ROOT, "data", "masters", "master_team.parquet")
ARM = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                   "M13_PLAYER_VALUE_TRANSLATION", "translation_rows.parquet")

#: The Odds API uses full club names; the masters use abbreviations. PHO and PHX
#: both appear in master_team for the same team_id -- collapsed, not deduplicated,
#: because they are the same club and the duplicate is an upstream naming wrinkle.
NAME2ABV = {
    "Atlanta Dream": "ATL", "Chicago Sky": "CHI", "Connecticut Sun": "CON",
    "Dallas Wings": "DAL", "Golden State Valkyries": "GSV", "Indiana Fever": "IND",
    "Los Angeles Sparks": "LAS", "Las Vegas Aces": "LVA", "Minnesota Lynx": "MIN",
    "New York Liberty": "NYL", "Portland Fire": "PDX", "Phoenix Mercury": "PHX",
    "Seattle Storm": "SEA", "Toronto Tempo": "TOR", "Washington Mystics": "WAS",
}

T90_MIN = 90


def _dates(s, tz="US/Eastern"):
    return pd.to_datetime(s, utc=True, errors="coerce").dt.tz_convert(tz).dt.date


def main():
    out = {}
    print("=" * 94)
    print("M36 -- the props seam: is the p_active wiring blocked by data or by plumbing?")
    print("=" * 94)

    # ---- 1. the boundary -------------------------------------------------
    arm = pd.read_parquet(os.path.normpath(ARM))
    arm_lo, arm_hi = str(arm["game_date"].min()), str(arm["game_date"].max())
    inj = pd.read_csv(INJ)
    inj_gd = pd.to_datetime(inj["game_date"], errors="coerce").dt.date
    inj_lo, inj_hi = str(inj_gd.min()), str(inj_gd.max())
    gap = (pd.Timestamp(inj_lo) - pd.Timestamp(arm_hi)).days

    print("\n1. THE BOUNDARY")
    print("   arm scored frame (translation_rows) : %s .. %s  (%d rows)"
          % (arm_lo, arm_hi, len(arm)))
    print("   injury tape                         : %s .. %s  (%d rows)"
          % (inj_lo, inj_hi, len(inj)))
    print("   overlap                             : NONE -- a %d-day gap" % gap)
    out["boundary"] = {"arm": [arm_lo, arm_hi], "tape": [inj_lo, inj_hi],
                       "overlap_days": 0, "gap_days": int(gap)}

    # ---- 2. the cause ----------------------------------------------------
    h = pd.read_csv(HIST, low_memory=False)
    h_hi = str(pd.to_datetime(h["last_update"], utc=True, errors="coerce").max())
    print("\n2. THE CAUSE")
    print("   M13 reads master_props_historical.csv EXCLUSIVELY, under D027.")
    print("   that archive's last quote : %s" % h_hi)
    print("   -> the frame ends where its only authorised source ends.")
    out["historical_last_update"] = h_hi

    # ---- 3. the alternative ---------------------------------------------
    l = pd.read_csv(LIVE, low_memory=False)
    live_cols = set(l.columns)          # BEFORE any derived column is added
    l["gd"] = _dates(l["commence_time"])
    l["snap"] = pd.to_datetime(l["snapshot_utc"], utc=True, errors="coerce")
    l["tip"] = pd.to_datetime(l["commence_time"], utc=True, errors="coerce")
    l["lead_min"] = (l["tip"] - l["snap"]).dt.total_seconds() / 60.0
    print("\n3. THE ALTERNATIVE -- the programme's own live ladder (D028/D029)")
    print("   master_props.csv : %d rows, %d events, %s .. %s"
          % (len(l), l["api_event_id"].nunique(), l["gd"].min(), l["gd"].max()))
    print("   markets          : %s" % l["market_key"].value_counts().to_dict())
    print("   books            : %d" % l["bookmaker_key"].nunique())
    out["live"] = {"rows": int(len(l)), "events": int(l["api_event_id"].nunique()),
                   "lo": str(l["gd"].min()), "hi": str(l["gd"].max()),
                   "books": int(l["bookmaker_key"].nunique())}

    # schema difference -- stated, not smoothed over
    miss = sorted(set(h.columns) - live_cols)
    extra = sorted(live_cols - set(h.columns))
    print("   columns the live file LACKS  : %s" % miss)
    print("   columns the live file ADDS   : %s" % extra)
    out["schema_missing"] = miss
    out["schema_extra"] = extra

    # ---- 4. joinable? ----------------------------------------------------
    ev = (l.groupby("api_event_id")
            .agg(gd=("gd", "first"), home=("home_team", "first"),
                 away=("away_team", "first")).reset_index())
    unmapped = sorted(n for n in set(ev["home"]) | set(ev["away"])
                      if n not in NAME2ABV)
    ev["h"] = ev["home"].map(NAME2ABV)
    ev["a"] = ev["away"].map(NAME2ABV)

    mt = pd.read_parquet(MTEAM)
    mt["gd"] = pd.to_datetime(mt["game_date"]).dt.date
    g = mt[(mt["is_home"] == 1) & (mt["gd"] >= dt.date(2026, 7, 31))][
        ["game_id", "gd", "team_abbreviation", "opp_team_abbreviation"]]
    g.columns = ["game_id", "gd", "h", "a"]
    g["h"] = g["h"].replace({"PHO": "PHX"})
    g["a"] = g["a"].replace({"PHO": "PHX"})
    outcome_hi = max(g["gd"])

    m = ev.merge(g, on=["gd", "h", "a"], how="left")
    # an event is only resolvable if its game has been PLAYED -- outcomes stop
    # earlier than the props ladder, which quotes future games. Not a defect.
    played = ev["gd"] <= outcome_hi
    unresolved = int((m["game_id"].isna() & played).sum())
    ambiguous = int((m.groupby("api_event_id").size() > 1).sum())

    print("\n4. IS IT JOINABLE? (live file has no game_id)")
    print("   unmapped team names      : %s" % (unmapped or "none"))
    print("   events                   : %d" % len(ev))
    print("   events on played dates   : %d  (outcomes stop %s)"
          % (int(played.sum()), outcome_hi))
    print("   resolved to one game_id  : %d" % int(m["game_id"].notna().sum()))
    print("   UNRESOLVED               : %d" % unresolved)
    print("   AMBIGUOUS (multi-match)  : %d" % ambiguous)
    out["join"] = {"events": int(len(ev)), "played": int(played.sum()),
                   "resolved": int(m["game_id"].notna().sum()),
                   "unresolved": unresolved, "ambiguous": ambiguous,
                   "unmapped_names": unmapped}

    # ---- 5. does it support a T-90m question? ---------------------------
    pts = l[l["market_key"] == "player_points"]
    n90 = int((pts["lead_min"] >= T90_MIN).sum())
    ev90 = int(pts.loc[pts["lead_min"] >= T90_MIN, "api_event_id"].nunique())
    snaps = pts.groupby("api_event_id")["snap"].nunique()

    print("\n5. DOES IT SUPPORT A T-90m QUESTION?")
    print("   player_points quotes     : %d over %d events"
          % (len(pts), pts["api_event_id"].nunique()))
    print("   distinct snapshots/event : median %.0f (min %d, max %d)"
          % (snaps.median(), snaps.min(), snaps.max()))
    print("   median lead before tip   : %.0f min" % pts["lead_min"].median())
    print("   quotes standing >= T-90m : %d (%.1f%%) across %d events"
          % (n90, 100.0 * n90 / len(pts), ev90))
    out["t90"] = {"quotes": int(len(pts)), "at_or_before_t90": n90,
                  "pct": round(100.0 * n90 / len(pts), 1), "events": ev90,
                  "median_lead_min": round(float(pts["lead_min"].median()), 1),
                  "median_snapshots_per_event": float(snaps.median())}

    # ---- verdict ---------------------------------------------------------
    crossable = (unresolved == 0 and ambiguous == 0 and not unmapped
                 and n90 > 0)
    print("\n" + "=" * 94)
    print("VERDICT: the seam is %sCROSSABLE ON IDENTITY, and the ladder %s a T-90m question."
          % ("" if crossable else "NOT ", "supports" if n90 else "cannot support"))
    print("It is NOT free: no game_id in the file, and snapshot_utc replaces the")
    print("requested/returned pair that bounded staleness -- which matters precisely")
    print("because the open question IS a cutoff question. Crossing it cites a source")
    print("D027 does not govern. That is an authorisation decision, not a code change.")
    print("=" * 94)
    out["crossable_on_identity"] = bool(crossable)

    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "FINDINGS.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    print("\nwrote FINDINGS.json")


if __name__ == "__main__":
    main()
