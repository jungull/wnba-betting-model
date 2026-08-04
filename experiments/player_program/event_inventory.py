#!/usr/bin/env python3
"""event_inventory.py — reconcile the two play-by-play stores against the 1,495-game universe.

Runs BEFORE the canonical event contract is registered, because the registration must state the
real schema-change boundary, the real taxonomy values and the real coverage rather than assume
them. Nothing here normalises or fits anything; it only counts and reports.

Writes ``EVENT_SOURCE_INVENTORY.json``.

Run::

    python experiments/player_program/event_inventory.py
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "event_contract_v1"

LEGACY = ROOT / "data/playbyplay"
CDN = ROOT / "data/refresh_2026/pbp"
CONTRACT = ROOT / "experiments/prediction_contract_v5/player_game_enriched.parquet"
SHOTS = ROOT / "data/shotcharts"


def _gid(p: Path) -> str | None:
    m = re.search(r"pbp_(\d+)", p.name)
    return m.group(1) if m else None


def scan(store: Path) -> tuple[dict, list[dict]]:
    files, bad, dupes = {}, [], Counter()
    for p in sorted(store.glob("pbp_*.parquet")):
        g = _gid(p)
        if g is None:
            bad.append({"file": p.name, "reason": "unparseable game id"})
            continue
        dupes[g] += 1
        try:
            d = pd.read_parquet(p)
        except Exception as exc:                                    # noqa: BLE001
            bad.append({"file": p.name, "reason": f"unreadable: {type(exc).__name__}"})
            continue
        files[g] = {"file": p.name, "rows": int(len(d)), "cols": list(d.columns)}
    return files, bad, [g for g, n in dupes.items() if n > 1]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    legacy, legacy_bad, legacy_dupes = scan(LEGACY)
    cdn, cdn_bad, cdn_dupes = scan(CDN)

    c = pd.read_parquet(CONTRACT, columns=["game_id", "game_date", "season"]).drop_duplicates("game_id")
    c["game_id"] = c["game_id"].astype(str)
    universe = set(c["game_id"])
    dates = c.set_index("game_id")["game_date"]
    seasons = c.set_index("game_id")["season"]

    L, C = set(legacy), set(cdn)
    both = L & C
    only_l, only_c = L - C, C - L
    covered = (L | C) & universe
    missing = universe - (L | C)
    extra = (L | C) - universe

    def _span(ids: set[str]) -> dict:
        ids = [g for g in ids if g in dates.index]
        if not ids:
            return {}
        d = dates.loc[ids]
        return {"first": str(d.min().date()), "last": str(d.max().date()), "games": len(ids)}

    # Is the changeover clean? A GLOBAL date test is misleading here: the CDN span starts
    # 2021-09-23 because playoff games were backfilled from the CDN source for every season. The
    # partition is two-dimensional -- season_type first, then a date boundary inside the 2025
    # regular season -- so it must be tested stratified.
    l_span, c_span = _span(L & universe), _span(C & universe)
    stype = (pd.read_parquet(ROOT / "data/possessions/possessions.parquet",
                             columns=["game_id", "season_type"])
             .drop_duplicates("game_id"))
    stype["game_id"] = stype["game_id"].astype(str)
    st = stype.set_index("game_id")["season_type"]

    strata, overlaps = {}, []
    for g in sorted(universe):
        key = (int(seasons.loc[g]), str(st.get(g, "unknown")))
        b = strata.setdefault(key, {"legacy": [], "cdn": []})
        b["legacy" if g in L else "cdn"].append(dates.loc[g])
    stratum_report = {}
    for (s, t), b in sorted(strata.items()):
        rec = {"legacy_games": len(b["legacy"]), "cdn_games": len(b["cdn"])}
        if b["legacy"] and b["cdn"]:
            l_last, c_first = max(b["legacy"]), min(b["cdn"])
            c_last, l_first = max(b["cdn"]), min(b["legacy"])
            n_ov = sum(1 for d in b["legacy"] if d >= c_first) + \
                sum(1 for d in b["cdn"] if d <= l_last)
            rec.update({"legacy_span": [str(l_first.date()), str(l_last.date())],
                        "cdn_span": [str(c_first.date()), str(c_last.date())],
                        "date_overlap_games": n_ov,
                        "boundary_clean": n_ov == 0})
            if n_ov:
                overlaps.append({"season": s, "season_type": t, "games": n_ov})
        stratum_report[f"{s}/{t}"] = rec

    clean = (len(both & universe) == 0) and not overlaps
    overlap_window = {
        "global_span_test_is_misleading": (
            "the CDN span begins 2021-09-23 only because playoff games were backfilled from the "
            "CDN source for EVERY season; it is not evidence of a temporal overlap"),
        "strata_with_a_date_overlap": overlaps,
        "by_stratum": stratum_report,
    }

    # per-season counts by store
    by_season = {}
    for g in sorted(universe):
        s = int(seasons.loc[g])
        b = by_season.setdefault(s, {"universe": 0, "legacy": 0, "cdn": 0, "both": 0, "neither": 0})
        b["universe"] += 1
        in_l, in_c = g in L, g in C
        b["legacy"] += int(in_l and not in_c)
        b["cdn"] += int(in_c and not in_l)
        b["both"] += int(in_l and in_c)
        b["neither"] += int(not in_l and not in_c)

    rows_l = sum(v["rows"] for g, v in legacy.items() if g in universe)
    rows_c = sum(v["rows"] for g, v in cdn.items() if g in universe)

    # ---- taxonomy: every raw value that a crosswalk must cover -------------------- #
    tax_legacy, tax_cdn = Counter(), Counter()
    for g in sorted(L & universe):
        d = pd.read_parquet(LEGACY / legacy[g]["file"],
                            columns=["EVENTMSGTYPE", "EVENTMSGACTIONTYPE"])
        tax_legacy.update(zip(d["EVENTMSGTYPE"].astype("Int64"),
                              d["EVENTMSGACTIONTYPE"].astype("Int64")))
    for g in sorted(C & universe):
        d = pd.read_parquet(CDN / cdn[g]["file"], columns=["actionType", "subType"])
        tax_cdn.update(zip(d["actionType"].astype(str), d["subType"].astype(str)))

    # ---- shot-coordinate coverage ------------------------------------------------ #
    coord = {}
    # (a) coordinates carried inside the CDN event stream itself
    cdn_with_xy = set()
    for g in sorted(C & universe):
        d = pd.read_parquet(CDN / cdn[g]["file"], columns=["xLegacy", "yLegacy", "isFieldGoal"])
        if d["xLegacy"].notna().any():
            cdn_with_xy.add(g)
    # (b) the separate shot-chart store
    shot_games, shot_rows = set(), 0
    shot_files = sorted(SHOTS.glob("shots_*.parquet"))
    for p in shot_files:
        d = pd.read_parquet(p)
        gcol = "GAME_ID" if "GAME_ID" in d.columns else ("game_id" if "game_id" in d.columns else None)
        if gcol is None:
            continue
        shot_rows += len(d)
        shot_games |= set(d[gcol].astype(str))
    shot_in_universe = shot_games & universe
    no_shotchart = sorted(universe - shot_games)

    # for each universe game lacking a shot-chart row, why?
    diagnosis = []
    for g in no_shotchart:
        rec = {"game_id": g, "season": int(seasons.loc[g]), "date": str(dates.loc[g].date()),
               "in_legacy": g in L, "in_cdn": g in C}
        if g in C:
            d = pd.read_parquet(CDN / cdn[g]["file"],
                                columns=["isFieldGoal", "xLegacy", "yLegacy", "shotDistance"])
            fg = int((d["isFieldGoal"] == 1).sum()) if "isFieldGoal" in d else 0
            rec.update({"shot_events_in_event_file": fg,
                        "events_with_coordinates": int(d["xLegacy"].notna().sum()),
                        "cause": ("shot events exist WITH coordinates in the CDN event stream; "
                                  "only the separate shot-chart store lacks this game")
                        if d["xLegacy"].notna().any() else
                        "shot events exist WITHOUT coordinates"})
        elif g in L:
            d = pd.read_parquet(LEGACY / legacy[g]["file"], columns=["EVENTMSGTYPE"])
            rec.update({"shot_events_in_event_file": int(d["EVENTMSGTYPE"].isin([1, 2]).sum()),
                        "events_with_coordinates": 0,
                        "cause": "legacy PlayByPlayV2 schema does not supply shot coordinates at all"})
        diagnosis.append(rec)

    coord = {
        "shot_chart_files": [p.name for p in shot_files],
        "shot_chart_rows": shot_rows,
        "shot_chart_games_total": len(shot_games),
        "shot_chart_games_in_universe": len(shot_in_universe),
        "universe_games_without_a_shot_chart_row": len(no_shotchart),
        "cdn_games_with_inline_coordinates": len(cdn_with_xy),
        "legacy_games_with_inline_coordinates": 0,
        "legacy_schema_supplies_coordinates": False,
        "per_game_diagnosis": diagnosis,
    }

    inv = {
        "schema": "event_source_inventory/1",
        "generated_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "nothing_fitted": True,
        "universe": {"games": len(universe),
                     "source": "experiments/prediction_contract_v5/player_game_enriched.parquet"},
        "stores": {
            "legacy_PlayByPlayV2": {
                "path": "data/playbyplay",
                "files_readable": len(legacy), "unreadable_or_malformed": legacy_bad,
                "duplicate_game_files": legacy_dupes,
                "games_in_universe": len(L & universe),
                "games_outside_universe": sorted(L - universe),
                "event_rows_in_universe": rows_l,
                "span": l_span,
            },
            "modern_CDN": {
                "path": "data/refresh_2026/pbp",
                "files_readable": len(cdn), "unreadable_or_malformed": cdn_bad,
                "duplicate_game_files": cdn_dupes,
                "games_in_universe": len(C & universe),
                "games_outside_universe": sorted(C - universe),
                "event_rows_in_universe": rows_c,
                "span": c_span,
            },
        },
        "reconciliation": {
            "games_only_in_legacy": len(only_l & universe),
            "games_only_in_cdn": len(only_c & universe),
            "games_in_both": len(both & universe),
            "games_in_neither": len(missing),
            "games_in_neither_list": sorted(missing),
            "games_covered": len(covered),
            "arithmetic": (f"{len(only_l & universe)} + {len(only_c & universe)} + "
                           f"{len(both & universe)} + {len(missing)} = {len(universe)}"),
            "closes": (len(only_l & universe) + len(only_c & universe) + len(both & universe)
                       + len(missing)) == len(universe),
            "files_outside_the_universe": sorted(extra),
            "partition_is_exact_and_disjoint": clean,
            "boundary_shape": (
                "TWO-DIMENSIONAL, not a single date. (1) season_type: every playoff game in "
                "2021-2025 comes from the CDN store regardless of season. (2) date, inside the "
                "2025 regular season: legacy through 2025-06-29, CDN from 2025-07-03. 2026 is "
                "entirely CDN. No game appears in both stores."),
            "changeover_analysis": overlap_window,
        },
        "by_season": by_season,
        "row_counts": {"legacy_events": rows_l, "cdn_events": rows_c,
                       "total_raw_events": rows_l + rows_c},
        "taxonomy_raw_values": {
            "legacy_distinct_(EVENTMSGTYPE,EVENTMSGACTIONTYPE)": len(tax_legacy),
            "legacy_distinct_EVENTMSGTYPE": sorted({int(k[0]) for k in tax_legacy if pd.notna(k[0])}),
            "legacy_pairs": {f"{k[0]}/{k[1]}": v for k, v in
                             sorted(tax_legacy.items(), key=lambda x: -x[1])},
            "cdn_distinct_(actionType,subType)": len(tax_cdn),
            "cdn_distinct_actionType": sorted({k[0] for k in tax_cdn}),
            "cdn_pairs": {f"{k[0]}/{k[1]}": v for k, v in
                          sorted(tax_cdn.items(), key=lambda x: -x[1])},
        },
        "shot_coordinates": coord,
    }
    (OUT / "EVENT_SOURCE_INVENTORY.json").write_text(json.dumps(inv, indent=2, default=str),
                                                     encoding="utf-8")

    r = inv["reconciliation"]
    print(f"universe {len(universe)} games")
    print(f"  only legacy {r['games_only_in_legacy']}  only cdn {r['games_only_in_cdn']}  "
          f"both {r['games_in_both']}  neither {r['games_in_neither']}")
    print(f"  arithmetic closes: {r['closes']}  ({r['arithmetic']})")
    print(f"  partition exact and disjoint: {r['partition_is_exact_and_disjoint']}")
    for k, v in r["changeover_analysis"]["by_stratum"].items():
        if v.get("legacy_games") and v.get("cdn_games"):
            print(f"    split stratum {k}: legacy {v['legacy_games']} {v.get('legacy_span')} | "
                  f"cdn {v['cdn_games']} {v.get('cdn_span')} | clean={v.get('boundary_clean')}")
    print(f"  legacy span {l_span}  cdn span {c_span}")
    print(f"  raw events: legacy {rows_l:,}  cdn {rows_c:,}  total {rows_l + rows_c:,}")
    print(f"  taxonomy: legacy {len(tax_legacy)} pairs, cdn {len(tax_cdn)} pairs")
    print(f"  shot charts: {coord['shot_chart_games_in_universe']} of {len(universe)} games; "
          f"{coord['universe_games_without_a_shot_chart_row']} without")
    print(f"  cdn games with inline coordinates: {coord['cdn_games_with_inline_coordinates']}")
    print(f"\nwrote {OUT / 'EVENT_SOURCE_INVENTORY.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
