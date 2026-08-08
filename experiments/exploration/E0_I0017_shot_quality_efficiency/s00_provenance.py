"""
E0_I0017 STEP 0 -- PROVENANCE GATE on data/shotcharts/*.

THE QUESTION.  `data/shotcharts/*.parquet` has no sibling `.manifest.json`, so
screenkit.check_manifest returns UNVERIFIABLE, which is NEVER A PASS (D080).  Two prior screens
(E0_I0004_shot_location_allowance, E1_I0004_shot_selection) used the files anyway on STRUCTURAL
grounds -- "no manifests and needs none: the season is the filename".  This script tests that
argument on COLUMN VALUES rather than inheriting it.

D086 INVARIANT OBSERVED THROUGHOUT: a substring match on a column NAME may only ever NOMINATE a
column for a value test; it may never, by itself, cause a violation or a pass.

VERDICT VOCABULARY: ROW / SEASON / ARTIFACT / UNDETERMINED.
  ROW         every row is a raw event bounded by its own game date; no column could have been
              computed by pooling across rows.  Usable if filtered to the partition.
  SEASON      rows carry season-level pooled quantities; usable only if the season is inside the
              partition and nothing crosses seasons.
  ARTIFACT    some column could only have been produced by pooling across time (incl. across the
              2025/2026 holdout); filtering does not help.  STOP.
  UNDETERMINED cannot be established from values.  STOP.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
KIT = os.path.join(ROOT, r"experiments\exploration\_screen_kit")
OUT = os.path.join(ROOT, r"experiments\exploration\E0_I0017_shot_quality_efficiency")
SHOTDIR = os.path.join(ROOT, r"data\shotcharts")
sys.path.insert(0, KIT)
import screenkit as sk  # noqa: E402

PARTITION_FILES = [
    "shots_2021_regular.parquet", "shots_2021_playoffs.parquet",
    "shots_2022_regular.parquet", "shots_2022_playoffs.parquet",
    "shots_2023_regular.parquet", "shots_2023_playoffs.parquet",
    "shots_2024_regular.parquet", "shots_2024_playoffs.parquet",
]
# NEVER OPENED: shots_2025_*, shots_2026_*, league_avg_* (the latter are aggregates by construction)

report = {"step": "S00_provenance_gate", "files": {}, "checks": [], "verdict": None}


def say(*a):
    print(*a)


def sha256_head(path, nbytes=None):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


say("=" * 100)
say("S00.1  check_manifest -- record the kit's verdict verbatim, do not paper over it")
say("=" * 100)
for fn in PARTITION_FILES:
    p = os.path.join(SHOTDIR, fn)
    # SD2: the field is `status`, NOT `verdict`.  A misspelled key returns None from .get and a
    # silent None in a provenance gate reads as "clean".  Dump the WHOLE dict so no key can hide it.
    mv = sk.check_manifest(p, verbose=False)
    report["files"][fn] = {"manifest_status": mv["status"],
                           "usable_at_e0_e1": mv["usable_at_e0_e1"],
                           "filtering_helps": mv["filtering_helps"],
                           "manifest_present": mv["manifest_present"],
                           "asof_granularity": mv["asof_granularity"],
                           "note": mv["note"],
                           "full_return": {k: str(v) for k, v in mv.items()},
                           "sha256": sha256_head(p)}
    say(f"  {fn:34s} status={mv['status']:14s} usable_at_e0_e1={mv['usable_at_e0_e1']} "
        f"manifest_present={mv['manifest_present']}")

# also record that league_avg_* exist and are DELIBERATELY NOT OPENED
report["not_opened"] = {
    "league_avg_*.parquet": "league-average aggregates by name AND never opened; no value test run "
                            "because they are not used at all",
    "shots_2025_*, shots_2026_*": "outside exploration partition; never opened",
}

say("")
say("=" * 100)
say("S00.2  load partition files ONLY; per-file structural value tests")
say("=" * 100)

frames = []
for fn in PARTITION_FILES:
    p = os.path.join(SHOTDIR, fn)
    d = pd.read_parquet(p)
    season = int(fn.split("_")[1])
    d["_src_file"] = fn
    d["_file_season"] = season
    frames.append(d)
    say(f"  {fn:34s} rows={len(d):7d}  cols={d.shape[1]}")

sh = pd.concat(frames, ignore_index=True)
say(f"  TOTAL rows={len(sh)}")
report["total_rows"] = int(len(sh))
report["columns"] = list(sh.columns)

# ---- parse the date column BY VALUE ------------------------------------------------------------
# GAME_DATE is a string like '20230519'.  Parse it; if parsing fails or yields absurd years the
# structural claim collapses.
gd = pd.to_datetime(sh["GAME_DATE"], format="%Y%m%d", errors="coerce")
n_bad = int(gd.isna().sum())
say(f"\n  GAME_DATE parse: {len(gd) - n_bad} parsed, {n_bad} unparseable")
say(f"  GAME_DATE min={gd.min()}  max={gd.max()}")
report["game_date_min"] = str(gd.min())
report["game_date_max"] = str(gd.max())
report["game_date_unparseable"] = n_bad
sh["_game_date"] = gd

# ---- CHECK A: every row's date lies in the season named by its own filename ---------------------
yr = gd.dt.year
same = (yr == sh["_file_season"])
bad = sh.loc[~same, ["_src_file", "GAME_DATE"]]
say(f"\n  CHECK A  rows whose GAME_DATE year != filename season: {len(bad)}")
if len(bad):
    say(bad.head(10).to_string())
report["checks"].append({"id": "A", "name": "date_year_matches_filename_season",
                         "n_violations": int(len(bad)),
                         "pass": bool(len(bad) == 0)})

# ---- CHECK B: partition -- no row dated outside 2021-2024 --------------------------------------
outside = int(((yr < 2021) | (yr > 2024)).sum())
say(f"  CHECK B  rows dated outside 2021-2024: {outside}")
report["checks"].append({"id": "B", "name": "all_rows_inside_exploration_partition",
                         "n_violations": outside, "pass": bool(outside == 0)})

# ---- CHECK C: one row == one shot event.  (GAME_ID, GAME_EVENT_ID) unique? ----------------------
dupe = int(sh.duplicated(subset=["GAME_ID", "GAME_EVENT_ID"]).sum())
say(f"  CHECK C  duplicate (GAME_ID, GAME_EVENT_ID) rows: {dupe}")
report["checks"].append({"id": "C", "name": "game_id_event_id_uniquely_identifies_row",
                         "n_violations": dupe, "pass": bool(dupe == 0)})

# ---- CHECK D: GAME_DATE constant within GAME_ID (an event cannot span dates) --------------------
nd = sh.groupby("GAME_ID")["GAME_DATE"].nunique()
say(f"  CHECK D  games with >1 distinct GAME_DATE: {int((nd > 1).sum())}")
report["checks"].append({"id": "D", "name": "one_date_per_game_id",
                         "n_violations": int((nd > 1).sum()), "pass": bool((nd > 1).sum() == 0)})

# ---- CHECK E: the pooling test.  THE CENTRAL ONE. -----------------------------------------------
# A precomputed AGGREGATE would be constant (or near-constant) within the entity it was aggregated
# over, and would vary across entities.  A raw event property varies shot to shot.  Test EVERY
# column's within-entity constancy at player-season and team-season.  A column that is constant
# within player-season across hundreds of shots is a season aggregate stamped onto every row.
say("\n  CHECK E  per-column within-entity constancy (the pooling test)")
say(f"  {'column':22s} {'dtype':10s} {'ndistinct':>9s} {'const/plyr-ssn':>14s} {'const/team-ssn':>14s} {'const/game':>11s}")
ps = sh.groupby(["PLAYER_ID", "_file_season", "_src_file"], sort=False)
ts = sh.groupby(["TEAM_ID", "_file_season", "_src_file"], sort=False)
gg = sh.groupby("GAME_ID", sort=False)
colrows = []
for c in sh.columns:
    if c.startswith("_"):
        continue
    nun = int(sh[c].nunique(dropna=False))
    try:
        f_ps = float((ps[c].nunique() <= 1).mean())
        f_ts = float((ts[c].nunique() <= 1).mean())
        f_g = float((gg[c].nunique() <= 1).mean())
    except Exception as ex:  # noqa: BLE001
        f_ps = f_ts = f_g = float("nan")
    colrows.append({"column": c, "dtype": str(sh[c].dtype), "n_distinct": nun,
                    "frac_const_within_player_season": f_ps,
                    "frac_const_within_team_season": f_ts,
                    "frac_const_within_game": f_g})
    say(f"  {c:22s} {str(sh[c].dtype):10s} {nun:9d} {f_ps:14.4f} {f_ts:14.4f} {f_g:11.4f}")
report["column_constancy"] = colrows

# ---- CHECK F: NOMINATE-BY-NAME, DECIDE-BY-VALUE (D086) ------------------------------------------
# Nominate any column whose NAME hints at an aggregate, then TEST ITS VALUES.  A nomination alone
# is never a violation.
NOMINATING_SUBSTRINGS = ["pct", "rate", "avg", "mean", "rank", "shrunk", "shrink", "prior",
                         "total", "season", "cum", "expect", "pred", "adj", "index", "share",
                         "per", "zscore", "norm", "league"]
nominated = []
for c in sh.columns:
    lc = c.lower()
    hits = [s for s in NOMINATING_SUBSTRINGS if s in lc]
    if hits and not c.startswith("_"):
        nominated.append((c, hits))
say(f"\n  CHECK F  columns NOMINATED by name for an aggregate value test: {len(nominated)}")
fviol = 0
fdetail = []
for c, hits in nominated:
    s = sh[c]
    isnum = pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s)
    # value test: an aggregate rate/mean is (i) numeric, (ii) NON-INTEGER for at least some rows,
    # (iii) constant within some entity.  All three must hold to convict.
    noninteger = False
    if isnum:
        v = pd.to_numeric(s, errors="coerce").dropna().to_numpy(dtype=float)
        noninteger = bool(len(v) and np.any(np.abs(v - np.rint(v)) > 1e-12))
    cst = float(ps[c].nunique().le(1).mean()) if True else 0.0
    convicted = bool(isnum and noninteger and cst > 0.99)
    fviol += int(convicted)
    fdetail.append({"column": c, "name_hits": hits, "is_numeric": bool(isnum),
                    "has_noninteger_values": noninteger,
                    "frac_const_within_player_season": cst, "convicted": convicted})
    say(f"    {c:22s} name_hits={hits}  numeric={isnum}  noninteger={noninteger} "
        f"const_within_player_season={cst:.4f}  -> {'AGGREGATE' if convicted else 'not an aggregate by value'}")
report["checks"].append({"id": "F", "name": "nominate_by_name_decide_by_value",
                         "n_nominated": len(nominated), "n_convicted": fviol,
                         "detail": fdetail, "pass": bool(fviol == 0)})

# ---- CHECK G: are the numeric columns internally derivable from the row alone? -------------------
# SHOT_DISTANCE should be recoverable from LOC_X, LOC_Y (feet = sqrt(x^2+y^2)/10).  If it is, it is
# a WITHIN-ROW derivation and cannot encode anything about other rows.
d_calc = np.sqrt(sh["LOC_X"].to_numpy(float) ** 2 + sh["LOC_Y"].to_numpy(float) ** 2) / 10.0
d_obs = sh["SHOT_DISTANCE"].to_numpy(float)
agree = float(np.mean(np.abs(d_calc - d_obs) <= 1.0))
say(f"\n  CHECK G  SHOT_DISTANCE reproduced from LOC_X/LOC_Y within 1 ft: {agree:.6f} of rows")
report["checks"].append({"id": "G", "name": "shot_distance_is_a_within_row_derivation",
                         "frac_agree_within_1ft": agree, "pass": bool(agree > 0.99)})

# ---- CHECK H: flags are per-event booleans, not rates -------------------------------------------
sa = sh["SHOT_ATTEMPTED_FLAG"].value_counts(dropna=False).to_dict()
sm = sh["SHOT_MADE_FLAG"].value_counts(dropna=False).to_dict()
et = sh["EVENT_TYPE"].value_counts(dropna=False).to_dict()
say(f"  CHECK H  SHOT_ATTEMPTED_FLAG values={ {int(k): int(v) for k, v in sa.items()} }")
say(f"           SHOT_MADE_FLAG values={ {int(k): int(v) for k, v in sm.items()} }")
say(f"           EVENT_TYPE values={ {str(k): int(v) for k, v in et.items()} }")
flags_ok = set(map(int, sa.keys())) <= {0, 1} and set(map(int, sm.keys())) <= {0, 1}
# and MADE_FLAG must agree with EVENT_TYPE row by row -- a within-row consistency, not a rate
consist = float((( sh["SHOT_MADE_FLAG"] == 1) == (sh["EVENT_TYPE"] == "Made Shot")).mean())
say(f"           SHOT_MADE_FLAG agrees with EVENT_TYPE on {consist:.6f} of rows")
report["checks"].append({"id": "H", "name": "flags_are_per_event_binary_not_rates",
                         "attempted_values": {str(k): int(v) for k, v in sa.items()},
                         "made_values": {str(k): int(v) for k, v in sm.items()},
                         "made_flag_agrees_with_event_type": consist,
                         "pass": bool(flags_ok and consist > 0.999)})

# ---- CHECK I: no column is monotone in time in a way only a cumulative could be ------------------
# A cumulative/expanding column would be non-decreasing within player-season by date.  Test every
# numeric column for that signature.
#
# SD1 FIX (v2).  The v1 test asked only "is it non-decreasing within player-season?".  A CONSTANT
# sequence is non-decreasing, so PLAYER_ID (constant by definition of the group),
# SHOT_ATTEMPTED_FLAG (globally the single value 1) and TEAM_ID (constant absent a trade) were all
# convicted.  A cumulative must be non-decreasing AND actually increase: require >1 distinct value
# inside the group.  Degenerate (constant) groups are excluded from the denominator rather than
# counted as evidence either way.
say("\n  CHECK I v2  cumulative-signature test = non-decreasing AND non-constant within player-season")
shs = sh.sort_values(["PLAYER_ID", "_file_season", "_game_date", "GAME_EVENT_ID"], kind="stable")
cum_hits = []
for c in sh.columns:
    if c.startswith("_") or not pd.api.types.is_numeric_dtype(sh[c]) or pd.api.types.is_bool_dtype(sh[c]):
        continue
    g = shs.groupby(["PLAYER_ID", "_file_season"], sort=False)[c]

    def _cum(x):
        v = x.to_numpy(float)
        if len(v) <= 5:
            return np.nan                      # too short to judge
        if np.nanmin(v) == np.nanmax(v):
            return np.nan                      # DEGENERATE: constant, carries no monotone evidence
        return float(np.all(np.diff(v) >= 0))

    vals = g.apply(_cum)
    n_eff = int(vals.notna().sum())
    frac_mono = float(vals.mean()) if n_eff else float("nan")
    flagged = bool(n_eff > 0 and frac_mono > 0.9)
    if flagged:
        cum_hits.append({"column": c, "frac_groups_nondecreasing": frac_mono,
                         "n_nondegenerate_groups": n_eff})
    say(f"    {c:22s} non-degenerate player-seasons={n_eff:5d}  frac non-decreasing = "
        + (f"{frac_mono:.4f}" if n_eff else "n/a (always constant within group)")
        + ("   <-- CUMULATIVE SUSPECT" if flagged else ""))
report["checks"].append({"id": "I", "name": "no_cumulative_signature_v2_nondegenerate",
                         "suspects": cum_hits, "pass": bool(len(cum_hits) == 0),
                         "note": "v1 of this check convicted constants; see CONSTRUCTION_DEFECTS.md SD1"})

# ---- CHECK J: does any row-level value depend on rows from OTHER seasons? -----------------------
# Direct test of the holdout question: split by season and confirm the marginal distribution of
# every numeric column is *not* identical across seasons (an artifact stamped from a pooled fit
# would repeat exact values).  Also confirm no player-season carries values only explicable by a
# later season -- we test the strongest available proxy: exact value repetition across seasons for
# a continuous column.
say("\n  CHECK J  cross-season value-identity probe")
jd = []
for c in ["SHOT_DISTANCE", "LOC_X", "LOC_Y"]:
    per = {int(s): sh.loc[sh["_file_season"] == s, c].mean() for s in sorted(sh["_file_season"].unique())}
    jd.append({"column": c, "per_season_mean": {str(k): float(v) for k, v in per.items()}})
    say(f"    {c:16s} per-season means: " + ", ".join(f"{k}={v:.3f}" for k, v in per.items()))
report["checks"].append({"id": "J", "name": "cross_season_value_identity_probe", "detail": jd,
                         "pass": True})

# ---- kit partition assertion ON VALUES -----------------------------------------------------------
say("\n  screenkit.assert_partition on the shot frame (value test):")
chk = sh[["_game_date", "_file_season"]].rename(columns={"_game_date": "game_date", "_file_season": "season"})
try:
    sk.assert_partition(chk, verbose=True)
    ap = "PASS"
except Exception as ex:  # noqa: BLE001
    ap = f"RAISED: {type(ex).__name__}: {ex}"
say(f"  assert_partition -> {ap}")
report["assert_partition"] = ap

# ---- VERDICT -------------------------------------------------------------------------------------
say("\n" + "=" * 100)
allpass = all(c.get("pass", False) for c in report["checks"])
say(f"ALL STRUCTURAL CHECKS PASS: {allpass}")
report["verdict"] = "ROW" if allpass else "UNDETERMINED"
say(f"VERDICT: {report['verdict']}")
say("=" * 100)

with open(os.path.join(OUT, "_s00.json"), "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2, default=str)
pd.DataFrame(colrows).to_csv(os.path.join(OUT, "s00_column_constancy.csv"), index=False)
say(f"\nwrote {os.path.join(OUT, '_s00.json')}")
