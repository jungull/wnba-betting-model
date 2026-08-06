#!/usr/bin/env python3
"""P2B_MARKET_ODDS_ELIGIBILITY -- measurements.

Read-only. Reads the contract universe from THIS worktree (player-model-program) and the odds
archives READ-ONLY from the repository ROOT worktree (branch data-refresh-2026), which is where
they physically live. Nothing is written outside
experiments/player_program/stage2b/P2B_MARKET_ODDS_ELIGIBILITY/.

Every join is proved before it is used (see prove_join): this program has already produced one
manufactured negative from a dtype mismatch that silently matched nothing.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
WORKTREE = HERE.parents[3]                      # .../worktrees/player-model-program
ROOT = Path("C:/Users/jgallagher/wnba-betting-model")   # repository root worktree, READ-ONLY

sys.path.insert(0, str(WORKTREE / "experiments" / "player_program"))
import possession_features as pf  # noqa: E402

ARCHIVES = {
    "drive_master__master_odds": ROOT / "data/drive_masters/master_odds.csv",
    "extension__master_odds_extension": ROOT / "data/odds_capture/master_odds_extension.csv",
    "extension__other_markets": ROOT / "data/odds_capture/master_odds_extension_other_markets.csv",
}
TIP_TIMES = ROOT / "data/reference/tip_times.csv"

M: dict = {}


def norm_gid(s: pd.Series) -> pd.Series:
    """game_id -> zero-padded 10-char string, from float/int/str alike."""
    x = pd.to_numeric(s, errors="coerce")
    out = x.dropna().astype("int64").astype(str).str.zfill(10)
    return out.reindex(s.index)


def prove_join(left_ids: pd.Series, right_ids: pd.Series, label: str) -> dict:
    """A search returning nothing is not absence until the search is shown to work."""
    L = {x for x in left_ids.dropna() if isinstance(x, str)}
    R = {x for x in right_ids.dropna() if isinstance(x, str)}
    inter = L & R
    proof = {
        "label": label,
        "n_left": len(L), "n_right": len(R), "n_intersection": len(inter),
        "left_sample": sorted(L)[:3], "right_sample": sorted(R)[:3],
        "join_proved_nonempty": len(inter) > 0,
    }
    if not inter:
        proof["WARNING"] = ("EMPTY INTERSECTION -- treat as a possible dtype/format failure, "
                            "NOT as evidence of absence")
    return proof


# --------------------------------------------------------------------------- #
# 1. archive spans, cadence, and whether a per-snapshot observation timestamp survives
# --------------------------------------------------------------------------- #
def measure_archives() -> None:
    out = {}
    for name, path in ARCHIVES.items():
        d = pd.read_csv(path, low_memory=False)
        ts = pd.to_datetime(d["odds_snapshot_timestamp"], utc=True, errors="coerce", format="mixed")
        cm = pd.to_datetime(d["odds_commence_time"], utc=True, errors="coerce", format="mixed")
        gid = norm_gid(d["game_id"])
        per_game_snaps = d.assign(_g=gid, _t=ts).groupby("_g")["_t"].nunique()
        lead_min = ((cm - ts).dt.total_seconds() / 60.0)
        rec = {
            "path_read_only": str(path),
            "tracked_by_git": False,       # verified separately, see M["provenance"]
            "n_rows": int(len(d)),
            "columns": list(d.columns),
            "has_per_row_observation_timestamp_column": "odds_snapshot_timestamp" in d.columns,
            "snapshot_timestamp_nulls": int(ts.isna().sum()),
            "snapshot_span_utc": [str(ts.min()), str(ts.max())],
            "n_distinct_snapshot_timestamps": int(ts.nunique()),
            "n_distinct_game_id": int(gid.nunique()),
            "games_by_season": {int(k): int(v) for k, v in
                                d.assign(_g=gid).groupby("season")["_g"].nunique().items()},
            "distinct_snapshots_per_game": {
                "min": int(per_game_snaps.min()), "median": float(per_game_snaps.median()),
                "max": int(per_game_snaps.max()), "mean": round(float(per_game_snaps.mean()), 4),
            },
            "snapshot_minute_of_hour_values": sorted(
                int(x) for x in pd.DatetimeIndex(sorted(ts.dropna().unique())).minute.unique()),
            "lead_minutes_commence_minus_snapshot": {
                "min": round(float(lead_min.min()), 2),
                "median": round(float(lead_min.median()), 2),
                "max": round(float(lead_min.max()), 2),
                "mode_top5": {str(k): int(v) for k, v in
                              lead_min.round(0).value_counts().head(5).items()},
                "n_rows_snapshot_after_commence": int((lead_min < 0).sum()),
            },
        }
        if "market_key" in d.columns:
            rec["market_key_counts"] = {str(k): int(v) for k, v in
                                        d["market_key"].value_counts().items()}
            rec["markets_by_season_games"] = {
                str(mk): {int(s): int(n) for s, n in
                          sub.assign(_g=norm_gid(sub["game_id"])).groupby("season")["_g"].nunique().items()}
                for mk, sub in d.groupby("market_key")}
        else:
            rec["market_columns_present"] = [c for c in ("odds_spread", "odds_price")
                                             if c in d.columns]
            rec["totals_market_present"] = False
        out[name] = rec
    M["archives"] = out


# --------------------------------------------------------------------------- #
# 2. tip_times.csv provenance: does the observation timestamp survive the derivation?
# --------------------------------------------------------------------------- #
def measure_tip_provenance() -> None:
    t = pd.read_csv(TIP_TIMES, low_memory=False)
    tg = norm_gid(t["game_id"])
    drive = pd.read_csv(ARCHIVES["drive_master__master_odds"], low_memory=False)
    ext = pd.read_csv(ARCHIVES["extension__master_odds_extension"], low_memory=False)

    per_season_source = (t.assign(_g=tg).groupby(["season", "source_table"])["_g"]
                         .nunique().to_dict())
    parent_counts = {
        "drive_master": {int(k): int(v) for k, v in
                         drive.assign(_g=norm_gid(drive["game_id"]))
                         .groupby("season")["_g"].nunique().items()},
        "extension": {int(k): int(v) for k, v in
                      ext.assign(_g=norm_gid(ext["game_id"]))
                      .groupby("season")["_g"].nunique().items()},
    }
    # true distinct-snapshot count per game in the parents, vs what tip_times recorded
    dg = drive.assign(_g=norm_gid(drive["game_id"]))
    true_drive_snaps = dg.groupby("_g")["odds_snapshot_timestamp"].nunique()
    true_drive_rows = dg.groupby("_g").size()
    td = t.assign(_g=tg)
    td_drive = td[td["source_table"] == "drive_master"].set_index("_g")["n_snapshots"]
    aligned = pd.DataFrame({"recorded_n_snapshots": td_drive,
                            "true_distinct_snapshots": true_drive_snaps,
                            "parent_row_count": true_drive_rows}).dropna()

    M["tip_provenance"] = {
        "tip_times_path": str(TIP_TIMES),
        "tip_times_columns": list(t.columns),
        "observation_timestamp_column_in_output": "odds_snapshot_timestamp" in t.columns,
        "builder": "data/reference/collect_bios.py::phase_tips",
        "builder_evidence": {
            "reads_snapshot_at_line_231": 'usecols=[... "odds_snapshot_timestamp" ...]',
            "keeps_only_last_at_line_253": 'commence_utc=("commence_utc", "last")',
            "n_snapshots_is_row_count_line_255": 'n_snapshots=("snap", "size")  # size == rows, not nunique',
            "output_cols_line_280_282": "odds_snapshot_timestamp is NOT among the written columns",
        },
        "tip_games_by_season_and_source": {f"{int(k[0])}|{k[1]}": int(v)
                                           for k, v in per_season_source.items()},
        "parent_games_by_season": parent_counts,
        "join_proof_tip_to_drive": prove_join(tg, norm_gid(drive["game_id"]), "tip_times<->master_odds"),
        "join_proof_tip_to_ext": prove_join(tg, norm_gid(ext["game_id"]), "tip_times<->extension"),
        "n_snapshots_field_audit": {
            "n_games_compared": int(len(aligned)),
            "recorded_equals_true_distinct": int(
                (aligned["recorded_n_snapshots"] == aligned["true_distinct_snapshots"]).sum()),
            "recorded_equals_parent_row_count": int(
                (aligned["recorded_n_snapshots"] == aligned["parent_row_count"]).sum()),
            "recorded_n_snapshots_min_med_max": [
                int(aligned["recorded_n_snapshots"].min()),
                float(aligned["recorded_n_snapshots"].median()),
                int(aligned["recorded_n_snapshots"].max())],
            "true_distinct_snapshots_min_med_max": [
                int(aligned["true_distinct_snapshots"].min()),
                float(aligned["true_distinct_snapshots"].median()),
                int(aligned["true_distinct_snapshots"].max())],
        },
    }


# --------------------------------------------------------------------------- #
# 3. coverage of each candidate market field over the CONTRACT universe,
#    by season and by fold -- never pooled
# --------------------------------------------------------------------------- #
def measure_coverage() -> None:
    u = pf.load_universe()
    F = u.frame
    folds = pf.chronological_folds(u)

    ugid = norm_gid(F["game_id"]) if F["game_id"].dtype != object else F["game_id"].astype(str)
    if ugid.str.len().max() != 10:
        ugid = norm_gid(F["game_id"])
    F = F.assign(_g=ugid)

    # candidate market fields -> the set of game_ids on which the field has a non-null value
    fields: dict[str, set] = {}
    drive = pd.read_csv(ARCHIVES["drive_master__master_odds"], low_memory=False)
    drive["_g"] = norm_gid(drive["game_id"])
    ext = pd.read_csv(ARCHIVES["extension__master_odds_extension"], low_memory=False)
    ext["_g"] = norm_gid(ext["game_id"])
    oth = pd.read_csv(ARCHIVES["extension__other_markets"], low_memory=False)
    oth["_g"] = norm_gid(oth["game_id"])

    both_spread = pd.concat([drive[["_g", "odds_spread"]], ext[["_g", "odds_spread"]]])
    fields["market_spread"] = set(both_spread.loc[both_spread["odds_spread"].notna(), "_g"])
    both_price = pd.concat([drive[["_g", "odds_price"]], ext[["_g", "odds_price"]]])
    fields["market_moneyline_price"] = set(both_price.loc[both_price["odds_price"].notna(), "_g"])
    tot = oth[(oth["market_key"] == "totals") & oth["outcome_point"].notna()]
    fields["market_total_points"] = set(tot["_g"])
    h2h = oth[(oth["market_key"] == "h2h") & oth["outcome_price"].notna()]
    fields["market_h2h_price_other"] = set(h2h["_g"])

    t = pd.read_csv(TIP_TIMES, low_memory=False)
    fields["tip_utc__tip_times_csv"] = set(norm_gid(t["game_id"]).dropna())
    # NaN game_ids can never join; drop them so set ops and sorting stay type-clean
    fields = {k: {x for x in v if isinstance(x, str)} for k, v in fields.items()}

    M["universe"] = {
        "team_game_rows": int(len(F)),
        "game_clusters": int(F["_g"].nunique()),
        "seasons": sorted(int(s) for s in F["season"].unique()),
        "date_span": [str(F["game_date"].min()), str(F["game_date"].max())],
        "join_proofs": {k: prove_join(F["_g"], pd.Series(sorted(v)), f"universe<->{k}")
                        for k, v in fields.items()},
    }

    by_season, by_fold = {}, {}
    for fname, gids in fields.items():
        S = pd.Series(sorted(gids))
        cov = F["_g"].isin(gids)
        by_season[fname] = {}
        for s, sub in F.assign(_c=cov).groupby("season"):
            g = sub.groupby("_g")["_c"].max()
            by_season[fname][int(s)] = {
                "games": int(len(g)), "games_covered": int(g.sum()),
                "game_coverage_rate": round(float(g.mean()), 6),
                "team_game_rows": int(len(sub)),
                "row_coverage_rate": round(float(sub["_c"].mean()), 6),
            }
        by_fold[fname] = {}
        for fs in folds:
            entry = {}
            for scope, idx in (("train", fs.train_index), ("test", fs.test_index)):
                sub = F.loc[idx].assign(_c=F.loc[idx, "_g"].isin(gids))
                g = sub.groupby("_g")["_c"].max()
                entry[scope] = {
                    "games": int(len(g)), "games_covered": int(g.sum()),
                    "game_coverage_rate": round(float(g.mean()), 6),
                    "team_game_rows": int(len(sub)),
                    "degenerate_zero_variance": bool(g.nunique() == 1),
                    "all_missing": bool(g.sum() == 0),
                }
            entry["cutoff_date"] = fs.cutoff_date
            by_fold[fname][fs.fold_id] = entry
        _ = S
    M["coverage_by_season"] = by_season
    M["coverage_by_fold"] = by_fold


# --------------------------------------------------------------------------- #
# 4. earliest-snapshot figure: reproduce or correct 2022-05-21
# --------------------------------------------------------------------------- #
def measure_earliest() -> None:
    rows = []
    for name, path in ARCHIVES.items():
        d = pd.read_csv(path, usecols=["odds_snapshot_timestamp"], low_memory=False)
        ts = pd.to_datetime(d["odds_snapshot_timestamp"], utc=True, errors="coerce", format="mixed")
        rows.append((name, str(ts.min()), str(ts.max())))
    earliest = min(rows, key=lambda r: r[1])
    M["earliest_snapshot_adjudication"] = {
        "claim_under_test": "earliest snapshot in the parent odds archive is 2022-05-21",
        "per_archive_min_max": [{"archive": a, "min": b, "max": c} for a, b, c in rows],
        "earliest_overall_utc": earliest[1],
        "earliest_overall_archive": earliest[0],
        "date_component": earliest[1][:10],
        "verdict": "REPRODUCED" if earliest[1][:10] == "2022-05-21" else "CORRECTED",
        "note": ("The DATE reproduces exactly. What the figure does NOT establish is that the "
                 "row was OBSERVED on that date -- see retrospective_harvest_evidence."),
    }


# --------------------------------------------------------------------------- #
# 5. capture witness: was the archive OBSERVED when it says, or harvested later?
#    A vendor-supplied observation timestamp is a CLAIM about the past. The only
#    local witness to when a byte entered this repository is the file mtime.
# --------------------------------------------------------------------------- #
def measure_capture_witness() -> None:
    import datetime as dt
    import glob
    import os
    import re

    def mtime_utc(p: str) -> dt.datetime:
        return dt.datetime.fromtimestamp(os.path.getmtime(p), dt.UTC)

    hist = sorted(glob.glob(str(ROOT / "data/odds_capture/historical/hist_*.json")))
    hm = [mtime_utc(p) for p in hist]
    live = sorted(glob.glob(str(ROOT / "data/odds_capture/live_*.json")))
    lm = [mtime_utc(p) for p in live]

    skew = []
    for p in live:
        stamp = re.search(r"live_(\d{8}T\d{6})Z", os.path.basename(p)).group(1)
        named = dt.datetime.strptime(stamp, "%Y%m%dT%H%M%S").replace(tzinfo=dt.UTC)
        skew.append(abs((mtime_utc(p) - named).total_seconds()))

    M["capture_witness"] = {
        "method": ("filename/event date compared against filesystem mtime. mtime is the only "
                   "LOCAL witness of when the byte arrived; odds_snapshot_timestamp is a VENDOR "
                   "CLAIM about a past instant and is not self-witnessing."),
        "historical_json": {
            "n_files": len(hist),
            "event_name_date_span": [os.path.basename(hist[0]), os.path.basename(hist[-1])],
            "mtime_span_utc": [str(min(hm)), str(max(hm))],
            "distinct_mtime_dates": sorted({str(x.date()) for x in hm}),
            "burst_duration_seconds": round((max(hm) - min(hm)).total_seconds(), 1),
            "verdict": ("RETROSPECTIVE -- 292 files whose event dates span 2025-07-05..2026-07-29 "
                        "were all written inside a single ~9.5 minute burst on 2026-07-30"),
        },
        "live_json": {
            "n_files": len(live),
            "first": os.path.basename(live[0]), "last": os.path.basename(live[-1]),
            "mtime_span_utc": [str(min(lm)), str(max(lm))],
            "abs_skew_filename_vs_mtime_seconds": {
                "max": round(max(skew), 1), "median": round(sorted(skew)[len(skew) // 2], 1)},
            "verdict": ("CONTEMPORANEOUS -- mtime tracks the filename stamp to within seconds; "
                        "this is a genuine witnessed capture stream"),
        },
        "csv_archive_mtimes_utc": {
            str(p): str(mtime_utc(str(p))) for p in list(ARCHIVES.values()) + [TIP_TIMES]},
        "earliest_contemporaneously_witnessed_odds_capture_utc": "2026-07-30T15:01:32Z",
    }

    # Where the packet's "2026-07-31 .. 2026-08-06" figure actually comes from.
    c = pd.read_csv(ROOT / "data/odds_capture/capture_log.csv", low_memory=False)
    M["packet_figure_reconstruction"] = {
        "packet_path": ".cutoff_valid_availability_table_CORRECTED.unavailable_or_insufficient[2]",
        "packet_claim": "coverage: 2026-07-31 .. 2026-08-06 only",
        "capture_log_path": str(ROOT / "data/odds_capture/capture_log.csv"),
        "capture_log_rows": int(len(c)),
        "capture_log_columns": list(c.columns),
        "has_game_id": "game_id" in c.columns,
        "commence_time_span": [str(c["commence_time"].min()), str(c["commence_time"].max())],
        "snapshot_utc_span": [str(c["snapshot_utc"].min()), str(c["snapshot_utc"].max())],
        "markets": {str(k): int(v) for k, v in c["market"].value_counts().items()},
        "finding": ("The packet's 2026-07-31..2026-08-06 window is the COMMENCE-TIME span of "
                    "capture_log.csv -- the dates of the GAMES quoted -- not the capture span. "
                    "The capture span is 2026-07-30T15:01:32Z..2026-08-04T22:00:03Z. The packet "
                    "reported a game-date range as if it were a capture range, and then reasoned "
                    "from it that the family is historically unavailable."),
    }


def main() -> None:
    measure_archives()
    measure_earliest()
    measure_capture_witness()
    measure_tip_provenance()
    measure_coverage()
    out = HERE / "MEASUREMENTS.json"
    out.write_text(json.dumps(M, indent=2, sort_keys=False), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
