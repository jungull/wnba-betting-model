#!/usr/bin/env python3
"""CONSTRAINT 4 -- manifest check on every artifact M13 actually consumes.

Enumerates the real input paths (read out of compute_model_vs_market.py and
build_translation.py, not guessed), then for each looks for the sibling
<artifact>.manifest.json and reports asof_granularity. A MISSING manifest is
recorded as UNVERIFIABLE, never as a pass. Cross-referenced against the audit's
MISSING_MANIFESTS.json.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORKTREE = HERE.parents[2]
LIVE_ROOT = WORKTREE.parents[2]
ATT = WORKTREE / "experiments" / "cbs_v15_player_oof_v5" / "attempt_001"

INPUTS = [
    ("game_date lookup", WORKTREE / "data" / "masters" / "master_player.parquet"),
    ("outcomes 2021", WORKTREE / "data" / "wnba_gamelog_2021.parquet"),
    ("outcomes 2022", WORKTREE / "data" / "wnba_gamelog_2022.parquet"),
    ("outcomes 2023", WORKTREE / "data" / "wnba_gamelog_2023.parquet"),
    ("outcomes 2024", WORKTREE / "data" / "wnba_gamelog_2024.parquet"),
    ("outcomes 2025", WORKTREE / "data" / "refresh_2026" / "gamelog_player_2025_regular_season.parquet"),
    ("outcomes 2026", WORKTREE / "data" / "refresh_2026" / "gamelog_player_2026_regular_season.parquet"),
    ("row contract / tiers / cutoffs",
     WORKTREE / "experiments" / "prediction_contract_v5" / "player_game_enriched.parquet"),
    ("props archive (T1)", LIVE_ROOT / "data" / "props_capture" / "historical" / "master_props_historical.csv"),
]
for s in (2021, 2022, 2023, 2024, 2025, 2026):
    INPUTS.append((f"legacy predictions {s}", ATT / f"predictions__player_scoring_distribution__{s}.parquet"))

MISSING_JSON = (WORKTREE / "experiments" / "exploration" / "AUDIT_baseline_provenance"
                / "MISSING_MANIFESTS.json")


def main():
    audit_missing = set()
    if MISSING_JSON.exists():
        blob = json.loads(MISSING_JSON.read_text(encoding="utf-8"))

        def harvest(o):
            if isinstance(o, dict):
                for k, v in o.items():
                    if k in ("path", "artifact", "file", "relpath") and isinstance(v, str):
                        audit_missing.add(v.replace("\\", "/").lower())
                    harvest(v)
            elif isinstance(o, list):
                for v in o:
                    harvest(v)
            elif isinstance(o, str):
                if o.endswith((".parquet", ".csv")):
                    audit_missing.add(o.replace("\\", "/").lower())
        harvest(blob)

    rows = []
    for role, p in INPUTS:
        man = Path(str(p) + ".manifest.json")
        rel = str(p).replace("\\", "/")
        try:
            relw = str(p.relative_to(WORKTREE)).replace("\\", "/")
        except ValueError:
            relw = str(p.relative_to(LIVE_ROOT)).replace("\\", "/")
        rec = {"role": role, "path": rel, "exists": p.exists(),
               "manifest_path": str(man).replace("\\", "/"),
               "manifest_exists": man.exists()}
        if man.exists():
            m = json.loads(man.read_text(encoding="utf-8"))
            rec["asof_granularity"] = m.get("asof_granularity", "ABSENT_FIELD")
            rec["asof_max"] = m.get("asof_max") or m.get("asof") or m.get("max_asof")
            rec["status"] = ("ROW_BOUNDED_FILTERABLE" if rec["asof_granularity"] == "row"
                             else "ARTIFACT_BOUNDED_FILTERING_DOES_NOT_HELP"
                             if rec["asof_granularity"] == "artifact"
                             else f"MANIFEST_PRESENT_BUT_GRANULARITY={rec['asof_granularity']}")
            rec["manifest_keys"] = sorted(m.keys())
        else:
            rec["asof_granularity"] = None
            rec["status"] = "UNVERIFIABLE_NO_MANIFEST"
        rec["listed_in_audit_MISSING_MANIFESTS"] = any(
            relw.lower().endswith(x) or x.endswith(relw.lower()) for x in audit_missing)
        rows.append(rec)
        print(f"{rec['status']:<45} {relw}")

    summary = {
        "n_inputs": len(rows),
        "n_with_manifest": sum(1 for r in rows if r["manifest_exists"]),
        "n_unverifiable_no_manifest": sum(1 for r in rows if not r["manifest_exists"]),
        "n_artifact_granular": sum(1 for r in rows if r.get("asof_granularity") == "artifact"),
        "n_row_granular": sum(1 for r in rows if r.get("asof_granularity") == "row"),
        "inputs": rows,
    }
    (HERE / "step0_manifests.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print()
    print(json.dumps({k: v for k, v in summary.items() if k != "inputs"}, indent=1))


if __name__ == "__main__":
    main()
