"""
AUDIT_SCREEN_INTEGRITY -- output-side audit.

Two checks, both VALUE-BASED (never byte-based -- a prior byte-scan for the literals
"2025"/"2026" produced a FALSE partition violation by matching row counts and digit runs
inside floats):

  (1) observed_time exposure: does any E0 screen output carry an observed_time-like column?
  (2) partition compliance: parse each table and test the VALUES of season / date-like
      columns against the exploration partition 2021-2024.

Also (3): measure the recorded placebo distributions' spread (sd). A no-op placebo
reproduces the real number with sd exactly 0.000000.

READ-ONLY over the E0_* screens. Writes only into AUDIT_SCREEN_INTEGRITY/.
"""
import json
import os
import re

import numpy as np
import pandas as pd

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
EXPL = os.path.join(ROOT, "experiments", "exploration")
HERE = os.path.join(EXPL, "AUDIT_SCREEN_INTEGRITY")

SCREENS = ["E0_I0003_rebound_interaction", "E0_I0004_shot_location_allowance",
           "E0_I0005_turnover_interaction", "E0_I0006_usage_redistribution",
           "E0_I0008_height_differential", "E0_I0009_additive_pressure",
           "E0_I0010_positional_matchup", "E0_I0011_tendency_estimator"]

PARTITION = {2021, 2022, 2023, 2024}
OBS_LIKE = re.compile(r"observed_time|obs_time|observedtime", re.I)
SEASON_LIKE = re.compile(r"^(season|year|yr)$", re.I)
DATE_LIKE = re.compile(r"date|gdate|_dt$|timestamp|_time$", re.I)
ISO_YEAR = re.compile(r"\b(19|20)\d{2}\b")

rows = []
for scr in SCREENS:
    d = os.path.join(EXPL, scr)
    for fn in sorted(os.listdir(d)):
        p = os.path.join(d, fn)
        if not os.path.isfile(p):
            continue
        ext = os.path.splitext(fn)[1].lower()
        if ext not in (".csv", ".parquet"):
            continue
        try:
            df = pd.read_csv(p, low_memory=False) if ext == ".csv" else pd.read_parquet(p)
        except Exception as e:                                   # noqa: BLE001
            rows.append(dict(screen=scr, file=fn, status="UNREADABLE", detail=str(e)[:200]))
            continue

        obs_cols = [c for c in df.columns if OBS_LIKE.search(str(c))]
        season_cols = [c for c in df.columns if SEASON_LIKE.match(str(c))]
        date_cols = [c for c in df.columns if DATE_LIKE.search(str(c))
                     and c not in obs_cols]

        bad_season, season_seen = [], {}
        for c in season_cols:
            v = pd.to_numeric(df[c], errors="coerce").dropna().astype(int)
            seen = sorted(set(v.tolist()))
            season_seen[c] = seen
            if set(seen) - PARTITION:
                bad_season.append({c: sorted(set(seen) - PARTITION)})

        bad_dates, date_years = [], {}
        for c in date_cols:
            s = df[c].dropna().astype(str)
            if s.empty:
                continue
            yrs = set()
            for val in s.unique()[:5000]:
                m = ISO_YEAR.search(val)
                if m:
                    yrs.add(int(m.group(0)))
            if not yrs:
                continue
            date_years[c] = sorted(yrs)
            if yrs - PARTITION:
                bad_dates.append({c: sorted(yrs - PARTITION)})

        obs_years = {}
        for c in obs_cols:
            s = df[c].dropna().astype(str)
            yrs = sorted({int(m.group(0)) for m in
                          (ISO_YEAR.search(v) for v in s.unique()[:5000]) if m})
            obs_years[c] = yrs

        rows.append(dict(
            screen=scr, file=fn, status="OK", n_rows=len(df), n_cols=df.shape[1],
            observed_time_cols=obs_cols, observed_time_years=obs_years,
            season_cols=season_seen, season_out_of_partition=bad_season,
            date_cols=date_years, date_out_of_partition=bad_dates))

with open(os.path.join(HERE, "output_scan.json"), "w") as f:
    json.dump(rows, f, indent=2, default=str)

print("=" * 78)
print("CHECK 1 -- observed_time exposure in E0 screen OUTPUTS")
print("=" * 78)
hits = [r for r in rows if r.get("observed_time_cols")]
if not hits:
    print("NONE. No E0 screen output carries an observed_time-like column.")
for r in hits:
    print(f"  {r['screen']}/{r['file']}: {r['observed_time_cols']} years={r['observed_time_years']}")

print()
print("=" * 78)
print("CHECK 2 -- partition compliance by PARSED VALUES (not bytes)")
print("=" * 78)
viol = [r for r in rows if r.get("season_out_of_partition") or r.get("date_out_of_partition")]
if not viol:
    print("NONE. Every season/date-like column in every readable output is inside 2021-2024.")
for r in viol:
    print(f"  VIOLATION {r['screen']}/{r['file']}: season={r['season_out_of_partition']} "
          f"date={r['date_out_of_partition']}")
bad = [r for r in rows if r["status"] != "OK"]
for r in bad:
    print(f"  UNREADABLE {r['screen']}/{r['file']}: {r['detail']}")

print()
print("=" * 78)
print("CHECK 3 -- recorded placebo distribution spread (no-op signature: sd == 0.000000)")
print("=" * 78)
placebo_sd = {}
for tgt in ["pts", "reb", "ast"]:
    p = os.path.join(EXPL, "E0_I0010_positional_matchup", f"placebo_draws_{tgt}.csv")
    if not os.path.exists(p):
        continue
    v = pd.read_csv(p)
    cols = [c for c in v.columns if c != "target"]
    print(f"\n  I0010 placebo_draws_{tgt}.csv  n_draws={len(v)}")
    for c in cols:
        x = pd.to_numeric(v[c], errors="coerce").dropna().values
        if len(x) == 0:
            continue
        print(f"    {c:>8}: mean={x.mean():+.8f}  sd={x.std():.8f}  "
              f"min={x.min():+.8f}  max={x.max():+.8f}  n_unique={len(np.unique(x))}")
        placebo_sd[f"I0010/{tgt}/{c}"] = dict(sd=float(x.std()), mean=float(x.mean()),
                                              n_unique=int(len(np.unique(x))), n=int(len(x)))

# I0006's placebo is a matched-sample control, not a permutation distribution:
# its "spread" is the across-event dispersion of the placebo statistic.
p6 = os.path.join(EXPL, "E0_I0006_usage_redistribution", "placebo_presence_games.csv")
if os.path.exists(p6):
    v = pd.read_csv(p6)
    x = pd.to_numeric(v["top1_share"], errors="coerce").dropna().values
    print(f"\n  I0006 placebo_presence_games.csv  n_events={len(x)}")
    print(f"    top1_share: mean={x.mean():.6f} sd={x.std():.6f} "
          f"min={x.min():.6f} max={x.max():.6f} n_unique={len(np.unique(x))}")
    placebo_sd["I0006/top1_share"] = dict(sd=float(x.std()), mean=float(x.mean()),
                                          n_unique=int(len(np.unique(x))), n=int(len(x)))

p6c = os.path.join(EXPL, "E0_I0006_usage_redistribution", "clean_per_absence_game_summary.csv")
if os.path.exists(p6c):
    v = pd.read_csv(p6c)
    x = pd.to_numeric(v["top1_share"], errors="coerce").dropna().values
    print(f"\n  I0006 clean_per_absence_game_summary.csv (REAL arm) n={len(x)}")
    print(f"    top1_share: mean={x.mean():.6f} sd={x.std():.6f}")
    placebo_sd["I0006/real_top1_share"] = dict(sd=float(x.std()), mean=float(x.mean()),
                                               n=int(len(x)))

with open(os.path.join(HERE, "placebo_spreads.json"), "w") as f:
    json.dump(placebo_sd, f, indent=2)
print("\nwrote output_scan.json and placebo_spreads.json")
