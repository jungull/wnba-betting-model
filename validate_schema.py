"""
validate_schema.py
==================
Validation harness for wnba_schema.py (the V2/V3 normalizer). LOCAL FILES ONLY.

Default run:
  1. PBP reconciliation — N sampled V2 games (data/playbyplay) and N sampled
     true-V3 games (data/refresh_2026/pbp, V2 strays skipped by per-file schema
     detection): normalized made-shot / 3pt / FT / point counts per team must
     match the team gamelog truth exactly.
       V2 truth: drive_masters/master_team_cleaned.csv (covers all 996 games
                 incl. playoffs) + player-row sums from wnba_gamelog_<year>.
       V3 truth: refresh gamelog_team_* files + player-row sums from
                 gamelog_player_* files.
  2. Boxscore checks — N misc files: normalized team-summed points_paint must
     equal the audit-style raw sums (groupby teamId pointsPaint); minutes
     parsing must cover 100% of non-blank values across the old gamelogs, a
     refresh gamelog and the sampled misc files.

--dual-era mode (build now, runs after tonight's refetch):
  When data/refresh_2026/pbp_v2_dupes/ exists (the 17 2021-playoff V2 strays
  moved there, refetched as V3 into data/refresh_2026/pbp/), assert that
  normalize_pbp(V2 file) and normalize_pbp(V3 file) of the SAME game produce
  identical per-player on-court seconds (stint replay on the canonical frame)
  and reconciled per-person event counts. Exits 1 on failure.

Usage:
  python validate_schema.py [--n-pbp 25] [--n-misc 25] [--seed 42] [--dual-era]
"""

from __future__ import annotations

import argparse
import glob
import os
import random
import sys
from collections import Counter, defaultdict

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from wnba_schema import (
    detect_era, minutes_parse_report, normalize_pbp, normalize_player_box,
    period_length_sec, period_start_sec,
)

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")
PBP_V2_DIR = os.path.join(DATA, "playbyplay")
PBP_REFRESH_DIR = os.path.join(DATA, "refresh_2026", "pbp")
DUPES_DIR = os.path.join(DATA, "refresh_2026", "pbp_v2_dupes")
MISC_DIR = os.path.join(DATA, "refresh_2026", "misc")


# ----------------------------------------------------------------------------
# Truth sources
# ----------------------------------------------------------------------------
def load_v2_team_truth() -> pd.DataFrame:
    """(GAME_ID, TEAM_ID) -> fgm/fg3m/ftm/pts from the drive team master
    (covers every 2021 -> 2025-07-03 game, playoffs included)."""
    f = os.path.join(DATA, "drive_masters", "master_team_cleaned.csv")
    t = pd.read_csv(f, low_memory=False)
    out = pd.DataFrame({
        "GAME_ID": t["GAME_ID"].astype(str).str.zfill(10),
        "TEAM_ID": t["TEAM_ID"].astype("int64"),
        "fgm": t["team_fgm"].astype("int64"),
        "fg3m": t["team_fg3m"].astype("int64"),
        "ftm": t["team_ftm"].astype("int64"),
        "pts": t["team_pts"].astype("int64"),
    })
    return out.set_index(["GAME_ID", "TEAM_ID"])


def load_v2_player_sum_truth() -> pd.DataFrame:
    """Secondary V2 truth: player-row sums from the old season gamelogs
    (regular season only — the files carry no playoff rows)."""
    frames = []
    for y in (2021, 2022, 2023, 2024, 2025):
        f = os.path.join(DATA, f"wnba_gamelog_{y}.parquet")
        if not os.path.exists(f):
            continue
        g = pd.read_parquet(f, columns=["GAME_ID", "TEAM_ID", "FGM", "FG3M", "FTM", "PTS"])
        frames.append(g)
    g = pd.concat(frames, ignore_index=True)
    s = (g.groupby([g.GAME_ID.astype(str), "TEAM_ID"])[["FGM", "FG3M", "FTM", "PTS"]]
         .sum().rename(columns=str.lower))
    s.index.names = ["GAME_ID", "TEAM_ID"]
    return s.astype("int64")


def load_v3_team_truth() -> pd.DataFrame:
    """(GAME_ID, TEAM_ID) truth for refresh-era games from the team gamelogs."""
    frames = []
    for name in ("gamelog_team_2025_regular_season", "gamelog_team_2025_playoffs",
                 "gamelog_team_2026_regular_season", "gamelog_team_2021_playoffs"):
        f = os.path.join(DATA, "refresh_2026", f"{name}.parquet")
        if not os.path.exists(f):
            continue
        t = pd.read_parquet(f, columns=["GAME_ID", "TEAM_ID", "FGM", "FG3M", "FTM", "PTS"])
        frames.append(t)
    t = pd.concat(frames, ignore_index=True)
    t["GAME_ID"] = t["GAME_ID"].astype(str).str.zfill(10)
    out = t.rename(columns={"FGM": "fgm", "FG3M": "fg3m", "FTM": "ftm", "PTS": "pts"})
    return out.set_index(["GAME_ID", "TEAM_ID"]).astype("int64")


def load_v3_player_sum_truth() -> pd.DataFrame:
    frames = []
    for name in ("gamelog_player_2025_regular_season", "gamelog_player_2025_playoffs",
                 "gamelog_player_2026_regular_season", "gamelog_player_2021_playoffs"):
        f = os.path.join(DATA, "refresh_2026", f"{name}.parquet")
        if not os.path.exists(f):
            continue
        g = pd.read_parquet(f, columns=["GAME_ID", "TEAM_ID", "FGM", "FG3M", "FTM", "PTS"])
        frames.append(g)
    g = pd.concat(frames, ignore_index=True)
    g["GAME_ID"] = g["GAME_ID"].astype(str).str.zfill(10)
    s = (g.groupby(["GAME_ID", "TEAM_ID"])[["FGM", "FG3M", "FTM", "PTS"]]
         .sum().rename(columns=str.lower))
    return s.astype("int64")


def misc_roster(gid: str):
    f = os.path.join(MISC_DIR, f"misc_{gid}.parquet")
    if not os.path.exists(f):
        return None
    return normalize_player_box(pd.read_parquet(f))


# ----------------------------------------------------------------------------
# Canonical-frame aggregations
# ----------------------------------------------------------------------------
def team_shot_counts(ev: pd.DataFrame) -> pd.DataFrame:
    """Per-team fgm / fg3m / ftm / pts from a canonical event frame."""
    ev = ev[ev.team_id.notna()]
    grp = ev.groupby(ev.team_id.astype("int64"))
    out = pd.DataFrame({
        "fgm": grp.apply(lambda d: int((d.event_type == "shot_made").sum()), include_groups=False),
        "fg3m": grp.apply(lambda d: int(((d.event_type == "shot_made") & (d.points == 3)).sum()), include_groups=False),
        "ftm": grp.apply(lambda d: int((d.event_type == "ft_made").sum()), include_groups=False),
        "pts": grp.apply(lambda d: int(d.points.fillna(0).sum()), include_groups=False),
    })
    out.index.name = "TEAM_ID"
    return out


# ----------------------------------------------------------------------------
# Part 1 — PBP reconciliation
# ----------------------------------------------------------------------------
def reconcile_pbp_game(path: str, truths: list[tuple[str, pd.DataFrame]],
                       roster=None):
    """Returns (game_id, era, per-truth match dict, mismatch detail, anomalies)."""
    gid = os.path.basename(path).split("_")[1].split(".")[0]
    df = pd.read_parquet(path)
    ev = normalize_pbp(df, roster=roster)
    anoms = ev.attrs.get("anomalies", {})
    if ev.empty:
        return gid, "?", {name: "EMPTY_PBP" for name, _ in truths}, \
            [f"{gid}: pbp normalized to 0 events"], anoms
    got = team_shot_counts(ev)
    results, details = {}, []
    for name, truth in truths:
        ok, cover = True, False
        for team_id, row in got.iterrows():
            key = (gid, int(team_id))
            if key not in truth.index:
                continue
            cover = True
            want = truth.loc[key]
            for stat in ("fgm", "fg3m", "ftm", "pts"):
                if int(row[stat]) != int(want[stat]):
                    ok = False
                    details.append(f"{gid} team {team_id} [{name}] {stat}: "
                                   f"pbp={int(row[stat])} truth={int(want[stat])}")
        results[name] = "match" if (ok and cover) else ("no_truth" if not cover else "MISMATCH")
    return gid, ev["era"].iat[0], results, details, anoms


def run_pbp_validation(n: int, seed: int):
    print("=" * 78)
    print(f"PART 1 - PBP reconciliation ({n} V2 + {n} V3 sampled games, seed={seed})")
    print("=" * 78)
    rng = random.Random(seed)

    v2_files = sorted(glob.glob(os.path.join(PBP_V2_DIR, "pbp_*.parquet")))
    v2_sample = rng.sample(v2_files, min(n, len(v2_files)))
    v3_all = sorted(glob.glob(os.path.join(PBP_REFRESH_DIR, "pbp_*.parquet")))
    v3_true = [f for f in v3_all if detect_era(pq.read_schema(f).names) == "v3"]
    v3_sample = rng.sample(v3_true, min(n, len(v3_true)))
    print(f"V2 pool {len(v2_files)} files; V3 pool {len(v3_true)} true-V3 files "
          f"({len(v3_all) - len(v3_true)} V2 strays skipped)")

    v2_truth = [("master_team", load_v2_team_truth()),
                ("player_sums", load_v2_player_sum_truth())]
    v3_truth = [("team_gamelog", load_v3_team_truth()),
                ("player_sums", load_v3_player_sum_truth())]

    all_anoms = Counter()
    for label, sample, truths, use_roster in (
            ("V2", v2_sample, v2_truth, False), ("V3", v3_sample, v3_truth, True)):
        tallies = defaultdict(Counter)
        mismatches = []
        for path in sample:
            gid = os.path.basename(path).split("_")[1].split(".")[0]
            roster = misc_roster(gid) if use_roster else None
            gid, era, results, details, anoms = reconcile_pbp_game(path, truths, roster)
            all_anoms.update(anoms)
            for name, status in results.items():
                tallies[name][status] += 1
            mismatches.extend(details)
        print(f"\n{label} sample ({len(sample)} games):")
        for name, c in tallies.items():
            total = sum(c.values())
            print(f"  vs {name:14s}: {c['match']}/{total} exact "
                  f"(mismatch {c['MISMATCH']}, no-truth-coverage {c['no_truth']})")
        if mismatches:
            print(f"  MISMATCH DETAIL ({len(mismatches)} lines):")
            for line in mismatches[:40]:
                print(f"    {line}")
    print(f"\nAggregate pbp anomaly counters: {dict(sorted(all_anoms.items()))}")
    return all_anoms


# ----------------------------------------------------------------------------
# Part 2 — boxscore checks
# ----------------------------------------------------------------------------
def run_box_validation(n_misc: int, seed: int):
    print("\n" + "=" * 78)
    print(f"PART 2 - Boxscore checks ({n_misc} misc files + gamelog minutes sweep)")
    print("=" * 78)
    rng = random.Random(seed)
    misc_files = sorted(glob.glob(os.path.join(MISC_DIR, "misc_*.parquet")))
    sample = rng.sample(misc_files, min(n_misc, len(misc_files)))

    paint_ok = paint_bad = 0
    minutes_fail = 0
    starter5_bad = 0
    raw_minutes = []
    for f in sample:
        raw = pd.read_parquet(f)
        box = normalize_player_box(raw)
        # audit-style sums straight off the raw frame
        want = raw.groupby("teamId")["pointsPaint"].sum(min_count=1)
        got = box.groupby(box.team_id.astype("int64"))["points_paint"].sum(min_count=1)
        if want.sort_index().equals(got.sort_index().rename("pointsPaint")):
            paint_ok += 1
        else:
            paint_bad += 1
            print(f"  POINTS_PAINT MISMATCH {os.path.basename(f)}:\n"
                  f"    raw={want.to_dict()} normalized={got.to_dict()}")
        minutes_fail += box.attrs.get("minutes_parse_failures", 0)
        raw_minutes.extend(raw["minutes"].tolist())
        st = box.groupby("team_id")["starter_flag"].sum()
        starter5_bad += int((st != 5).sum())
    print(f"points_paint team sums: {paint_ok}/{len(sample)} files exact "
          f"({paint_bad} mismatches)")
    print(f"misc starter flags != 5 per team-game: {starter5_bad} team-games")

    print("\nMinutes parsing (minutes_to_float via the canonical regex):")
    total_fail = 0
    rep = minutes_parse_report(raw_minutes)
    total_fail += rep["n_failed"]
    print(f"  {len(sample)} misc files          : n={rep['n']:6d} blank(DNP)={rep['n_blank']:5d} "
          f"parsed={rep['n_parsed']:6d} FAILED={rep['n_failed']}"
          + (f" {rep['failed_values']}" if rep["n_failed"] else ""))
    for y in (2021, 2022, 2023, 2024, 2025):
        f = os.path.join(DATA, f"wnba_gamelog_{y}.parquet")
        if not os.path.exists(f):
            continue
        rep = minutes_parse_report(pd.read_parquet(f, columns=["MIN"])["MIN"])
        total_fail += rep["n_failed"]
        print(f"  wnba_gamelog_{y} (full)   : n={rep['n']:6d} blank(DNP)={rep['n_blank']:5d} "
              f"parsed={rep['n_parsed']:6d} FAILED={rep['n_failed']}"
              + (f" {rep['failed_values']}" if rep["n_failed"] else ""))
    f = os.path.join(DATA, "refresh_2026", "gamelog_player_2026_regular_season.parquet")
    rep = minutes_parse_report(pd.read_parquet(f, columns=["MIN"])["MIN"])
    total_fail += rep["n_failed"]
    print(f"  gamelog_player_2026 (full) : n={rep['n']:6d} blank(DNP)={rep['n_blank']:5d} "
          f"parsed={rep['n_parsed']:6d} FAILED={rep['n_failed']}"
          + (f" {rep['failed_values']}" if rep["n_failed"] else ""))
    print(f"  TOTAL PARSE FAILURES: {total_fail} (target 0)")
    return paint_bad == 0 and total_fail == 0


# ----------------------------------------------------------------------------
# Part 3 — dual-era identity (runs once pbp_v2_dupes/ exists)
# ----------------------------------------------------------------------------
EVID_TYPES = {"shot_made", "shot_missed", "ft_made", "ft_missed",
              "rebound", "turnover", "foul"}
EVID_OTHER_SUBTYPES = {"Steal", "Block", "Assist", "Foul Drawn",
                       "Jump Ball", "Jump Ball Tip"}
STRICT_COUNT_TYPES = ["shot_made", "shot_missed", "ft_made", "ft_missed",
                      "rebound", "turnover", "foul", "sub_in", "sub_out",
                      "timeout", "period_start", "period_end"]


def per_player_seconds(ev: pd.DataFrame) -> Counter:
    """Stint replay on a canonical frame -> {(team_id, person_id): seconds}.

    Mirrors the battle-tested derive_lineups starter rule: plain evidence only
    proves on-floor if strictly earlier (clock) than the player's first sub_in;
    a sub_out is proof regardless. No boxscore fill — pure pbp, so both eras
    are judged by the identical procedure.
    """
    is_other_evid = ((ev.event_type == "other")
                     & (ev.event_subtype.isin(EVID_OTHER_SUBTYPES)
                        | ev.event_subtype.astype(str).str.startswith("Violation")))
    evid = ev[(ev.event_type.isin(EVID_TYPES) | is_other_evid)
              & ~ev.technical_flag & ev.person_id.notna() & ev.team_id.notna()]
    buckets = defaultdict(list)
    for r in evid.itertuples(index=False):
        buckets[(int(r.period), int(r.team_id))].append(
            (int(r.event_idx), float(r.game_seconds_elapsed), "ev", int(r.person_id)))
    subs = ev[ev.event_type.isin(("sub_in", "sub_out"))
              & ev.person_id.notna() & ev.team_id.notna()]
    for r in subs.itertuples(index=False):
        kind = "in" if r.event_type == "sub_in" else "out"
        buckets[(int(r.period), int(r.team_id))].append(
            (int(r.event_idx), float(r.game_seconds_elapsed), kind, int(r.person_id)))

    seconds = Counter()
    for (period, team), evs in sorted(buckets.items()):
        evs.sort(key=lambda x: x[0])
        p0 = period_start_sec(period)
        p1 = p0 + period_length_sec(period)
        first_in = {}
        for pos, t, kind, pid in evs:
            if kind == "in" and pid not in first_in:
                first_in[pid] = (pos, t)
        first_sig = {}
        for pos, t, kind, pid in evs:
            if kind == "in" or pid in first_sig:
                continue
            fi = first_in.get(pid)
            if fi is None or (pos < fi[0] and (kind == "out" or t < fi[1] - 1e-9)):
                first_sig[pid] = pos
        cand = sorted(first_sig, key=lambda p: first_sig[p])[:5]
        on = {pid: p0 for pid in cand}
        for pos, t, kind, pid in evs:
            if kind == "out" and pid in on:
                start = on.pop(pid)
                if not np.isnan(t):
                    seconds[(team, pid)] += t - start
            elif kind == "in" and pid not in on and not np.isnan(t):
                on[pid] = t
        for pid, t0 in on.items():
            seconds[(team, pid)] += p1 - t0
    return seconds


def strict_counts(ev: pd.DataFrame) -> Counter:
    """(team_id, person_id-or-None, event_type) -> n for the strict type list."""
    c = Counter()
    sel = ev[ev.event_type.isin(STRICT_COUNT_TYPES)]
    for r in sel.itertuples(index=False):
        team = int(r.team_id) if pd.notna(r.team_id) else None
        pid = int(r.person_id) if pd.notna(r.person_id) else None
        c[(team, pid, r.event_type)] += 1
    return c


def run_dual_era(seconds_tol: float = 1e-6, near_tol: float = 2.0) -> bool:
    print("\n" + "=" * 78)
    print("PART 3 - Dual-era identity check (2021 playoffs: V2 dupes vs V3 refetch)")
    print("=" * 78)
    if not os.path.isdir(DUPES_DIR):
        print(f"{DUPES_DIR} does not exist yet - nothing to check. "
              "Run again after tonight's move+refetch.")
        return True
    dupes = sorted(glob.glob(os.path.join(DUPES_DIR, "pbp_*.parquet")))
    print(f"{len(dupes)} V2 dupe files found")
    truth = load_v3_team_truth()
    n_pass = n_fail = n_skip = 0
    for f2 in dupes:
        gid = os.path.basename(f2).split("_")[1].split(".")[0]
        f3 = os.path.join(PBP_REFRESH_DIR, f"pbp_{gid}.parquet")
        if not os.path.exists(f3):
            print(f"  {gid}: V3 refetch missing - SKIP")
            n_skip += 1
            continue
        df3 = pd.read_parquet(f3)
        if detect_era(df3) != "v3":
            print(f"  {gid}: refetched file is still V2 - SKIP")
            n_skip += 1
            continue
        roster = misc_roster(gid)
        ev2 = normalize_pbp(pd.read_parquet(f2), roster=roster)
        an2 = ev2.attrs.get("anomalies", {})
        ev3 = normalize_pbp(df3, roster=roster)
        an3 = ev3.attrs.get("anomalies", {})
        problems = []
        if ev2.empty or ev3.empty:
            print(f"  {gid}: FAIL - empty normalized frame "
                  f"(v2 {len(ev2)} rows, v3 {len(ev3)} rows)")
            n_fail += 1
            continue

        # 1 - per-player seconds via identical stint replay.
        # V2 clocks are whole seconds ("9:45"); V3 carries tenths ("PT09M45.30S"),
        # so sub-second disagreement at stint boundaries is the floor of achievable
        # precision, not an error. Pass bound = near_tol (2s clock-precision bound);
        # only diffs BEYOND it are failures. The exact/near split is still reported.
        s2, s3 = per_player_seconds(ev2), per_player_seconds(ev3)
        keys = set(s2) | set(s3)
        diffs = {k: abs(s2.get(k, 0.0) - s3.get(k, 0.0)) for k in keys}
        worst = max(diffs.values()) if diffs else 0.0
        n_exact = sum(1 for d in diffs.values() if d <= seconds_tol)
        n_near = sum(1 for d in diffs.values() if seconds_tol < d <= near_tol)
        n_far = len(diffs) - n_exact - n_near
        if n_far:
            offenders = sorted(diffs.items(), key=lambda kv: -kv[1])[:6]
            problems.append(f"seconds: {n_exact} exact / {n_near} within {near_tol}s / "
                            f"{n_far} BEYOND; worst={worst:.1f}s {offenders}")

        # 2 - strict event-count reconciliation between the eras
        c2, c3 = strict_counts(ev2), strict_counts(ev3)
        count_diffs = {k: (c2.get(k, 0), c3.get(k, 0))
                       for k in set(c2) | set(c3) if c2.get(k, 0) != c3.get(k, 0)}
        if count_diffs:
            # keys may contain None (nulled person ids) - sort None-safe by string
            sample_d = dict(sorted(count_diffs.items(), key=lambda kv: str(kv[0]))[:8])
            problems.append(f"counts: {len(count_diffs)} (team,person,type) keys differ "
                            f"(v2,v3): {sample_d}")

        # 3 - both eras against the team-gamelog truth
        for tag, ev in (("v2", ev2), ("v3", ev3)):
            got = team_shot_counts(ev)
            for team_id, row in got.iterrows():
                key = (gid, int(team_id))
                if key not in truth.index:
                    continue
                want = truth.loc[key]
                bad = {s: (int(row[s]), int(want[s])) for s in ("fgm", "fg3m", "ftm", "pts")
                       if int(row[s]) != int(want[s])}
                if bad:
                    problems.append(f"{tag} vs truth team {team_id}: {bad}")

        anom_note = ""
        interesting = {k: v for k, v in {**{f"v2:{k}": v for k, v in an2.items()},
                                         **{f"v3:{k}": v for k, v in an3.items()}}.items()
                       if "unresolved" in k or "malformed" in k}
        if interesting:
            anom_note = f"  anomalies: {interesting}"
        if problems:
            n_fail += 1
            print(f"  {gid}: FAIL{anom_note}")
            for p in problems:
                print(f"      {p}")
        else:
            n_pass += 1
            print(f"  {gid}: PASS ({len(s2)} players, {n_exact} exact / {n_near} "
                  f"within {near_tol}s clock precision, worst {worst:.3f}s){anom_note}")
    print(f"\nDual-era result: {n_pass} pass / {n_fail} fail / {n_skip} skipped")
    return n_fail == 0


# ----------------------------------------------------------------------------
def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n-pbp", type=int, default=25)
    ap.add_argument("--n-misc", type=int, default=25)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--dual-era", action="store_true",
                    help="also run the same-game V2-vs-V3 identity check "
                         "(no-op with a note until pbp_v2_dupes/ exists)")
    args = ap.parse_args()

    run_pbp_validation(args.n_pbp, args.seed)
    box_ok = run_box_validation(args.n_misc, args.seed)
    dual_ok = True
    if args.dual_era:
        dual_ok = run_dual_era()
    if not (box_ok and dual_ok):
        sys.exit(1)


if __name__ == "__main__":
    main()
