"""Inspect COLUMN NAMES + a per-row timestamp presence check for capture/reference artifacts.
Column VALUES are read only to confirm a per-row as-of timestamp exists; no 2025/2026 numeric
probe is performed and no holdout data is loaded into any analysis."""
import os, io, csv, json

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
OUT = os.path.join(ROOT, "experiments", "exploration", "MANIFEST_REMEDIATION")

FILES = [
    r"data\reference\team_cities.csv",
    r"data\reference\tip_times.csv",
    r"data\reference\player_bios.csv",
    r"data\injury_capture\injury_log.csv",
    r"data\injury_history\injury_history.csv",
    r"data\ref_assignments\assignments_log.csv",
    r"experiments\market_program\INJURY_OFFICIAL\live\capture_log.csv",
    r"experiments\market_program\INJURY_OFFICIAL\live\injury_snapshots.csv",
    r"experiments\market_program\INJURY_OFFICIAL\live\status_transitions.csv",
    r"data\props_capture\historical\master_props_historical.csv",
    r"data\props_capture\master_props.csv",
    r"data\masters\master_player.csv",
    r"experiments\player_program\data_lane\D12_COACHING_HISTORY\team_season_coverage_v1.csv",
]
ASOF = ("captur", "snapshot", "timestamp", "observed", "asof", "as_of", "pulled",
        "commence", "date", "_ts", "ts_", "effective", "retrieved", "time")

res = {}
for f in FILES:
    p = os.path.join(ROOT, f)
    if not os.path.exists(p):
        res[f] = {"exists": False}
        continue
    with io.open(p, encoding="utf-8", errors="replace", newline="") as fh:
        rdr = csv.reader(fh)
        try:
            hdr = next(rdr)
        except StopIteration:
            res[f] = {"exists": True, "empty": True}
            continue
        n = 0
        for _ in rdr:
            n += 1
            if n > 400000:
                break
    asof_cols = [c for c in hdr if any(a in c.lower() for a in ASOF)]
    res[f] = {"exists": True, "n_cols": len(hdr), "n_rows_scanned": n,
              "columns": hdr, "per_row_asof_candidates": asof_cols}
    print("\n=== %s\n    rows=%d cols=%d" % (f, n, len(hdr)))
    print("    columns: %s" % ", ".join(hdr[:28]))
    print("    per-row as-of candidates: %s" % (asof_cols or "NONE <-- no per-row time bound"))

json.dump(res, open(os.path.join(OUT, "capture_headers.json"), "w", encoding="utf-8"), indent=1)
