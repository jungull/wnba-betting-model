#!/usr/bin/env python3
"""
D13_ARENA_TRAVEL_DIMENSION -- cardinality and effective-date invariants.

Standalone runnable test script (pytest is NOT installed in this environment).
main() returns 0 on pass, 1 on any failure.

These tests run against the WRITTEN artifacts (arena_dimension_v1.csv,
venue_pair_travel_v1.csv) and the real universe -- not against in-memory state
from the builder. A test that only re-checks the builder's own variables proves
nothing about the artifact a downstream node would actually read.

Run:  python experiments/player_program/data_lane/D13_ARENA_TRAVEL_DIMENSION/TESTS.py
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]

DIM_PATH = HERE / "arena_dimension_v1.csv"
VP_PATH = HERE / "venue_pair_travel_v1.csv"
META_PATH = HERE / "arena_dimension_v1.meta.json"
SRC_CITIES = ROOT / "data" / "reference" / "team_cities.csv"
SRC_PRIOR = (
    ROOT / "experiments" / "player_program" / "projected_exposure_v1"
    / "team_possession_prior_v1.parquet"
)

KEY = ["team_id", "season"]
EXPECTED_ROWS = 2982
EXPECTED_GAMES = 1491
PHOENIX_TEAM_ID = 1611661317

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(ok), detail))


def arbitrary_dedup_calls(path: Path) -> list[str]:
    """Find ACTUAL arbitrary-row-order deduplication calls, via the AST.

    A text scan is not usable here: a report that names the forbidden pattern
    would trip its own test, and stripping string literals to fix that would also
    strip the very argument that identifies a real use. So parse instead.

    Flags:
      * .drop_duplicates(<subset naming a single key column>) with no keep= that
        makes the choice explicit -- i.e. row order decides which row survives;
      * .groupby(...).first() / .last() -- same defect one call deeper.
    """
    import ast

    tree = ast.parse(path.read_text(encoding="utf-8"))
    hits: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        name = node.func.attr
        if name == "drop_duplicates":
            # positional or keyword subset that is a single column name
            subset = None
            if node.args:
                subset = node.args[0]
            for kw in node.keywords:
                if kw.arg == "subset":
                    subset = kw.value
            explicit_keep = any(
                kw.arg == "keep" and isinstance(kw.value, ast.Constant)
                for kw in node.keywords
            )
            if (isinstance(subset, ast.Constant) and isinstance(subset.value, str)
                    and not explicit_keep):
                hits.append(f"line {node.lineno}: drop_duplicates({subset.value!r})")
        elif name in ("first", "last"):
            inner = node.func.value
            if (isinstance(inner, ast.Call)
                    and isinstance(inner.func, ast.Attribute)
                    and inner.func.attr == "groupby"):
                hits.append(f"line {node.lineno}: groupby(...).{name}()")
    return hits


def load_universe() -> pd.DataFrame:
    prior = pd.read_parquet(SRC_PRIOR)
    return prior[prior["pace_resolved"]].copy()


def main() -> int:
    dim = pd.read_csv(DIM_PATH)
    vp = pd.read_csv(VP_PATH)
    meta = json.loads(META_PATH.read_text(encoding="utf-8"))
    universe = load_universe()

    # ---- T1 the universe is what the contract says it is -------------------
    check("T1a universe rows == 2982", len(universe) == EXPECTED_ROWS, str(len(universe)))
    check("T1b universe game clusters == 1491",
          universe["game_id"].nunique() == EXPECTED_GAMES,
          str(universe["game_id"].nunique()))

    # ---- T2 the dimension is unique on its DECLARED key --------------------
    check("T2a declared key recorded in meta", meta["declared_key"] == KEY,
          str(meta.get("declared_key")))
    ndup = int(dim.duplicated(subset=KEY).sum())
    check("T2b dimension unique on (team_id, season)", ndup == 0, f"{ndup} duplicate keys")

    # ---- T3 effective dates present and well-formed ------------------------
    for col in ["eff_first_season", "eff_last_season", "eff_last_season_is_open"]:
        check(f"T3a effective-date column present: {col}", col in dim.columns)
    check("T3b every row's season lies inside its effective interval",
          bool(((dim["eff_first_season"] <= dim["season"])
                & (dim["season"] <= dim["eff_last_season"])).all()))
    check("T3c no malformed interval",
          bool((dim["eff_first_season"] <= dim["eff_last_season"]).all()))

    # ---- T4 source intervals per team_id are disjoint and gapless ----------
    raw = pd.read_csv(SRC_CITIES)
    raw["_f"] = raw["first_season"].astype(int)
    raw["_l"] = raw["last_season"].fillna(9999).astype(int)
    overlaps = gaps = 0
    for _tid, g in raw.sort_values("_f").groupby("team_id"):
        rows = g[["_f", "_l"]].values.tolist()
        for i in range(1, len(rows)):
            if rows[i][0] <= rows[i - 1][1]:
                overlaps += 1
            elif rows[i][0] > rows[i - 1][1] + 1:
                gaps += 1
    check("T4a no overlapping effective intervals within a team_id", overlaps == 0,
          f"{overlaps} overlaps")
    check("T4b no gaps between effective intervals within a team_id", gaps == 0,
          f"{gaps} gaps")

    # ---- T5 THE FAN-OUT TEST: the safe merge cannot change the universe ----
    before_keyset = set(map(tuple, universe[["game_id", "team_id"]].values))
    merged = universe.merge(dim, on=KEY, how="left", validate="m:1")
    check("T5a merge preserves row count", len(merged) == EXPECTED_ROWS, str(len(merged)))
    check("T5b merge preserves game-cluster count",
          merged["game_id"].nunique() == EXPECTED_GAMES,
          str(merged["game_id"].nunique()))
    check("T5c merge preserves the exact (game_id, team_id) key set",
          set(map(tuple, merged[["game_id", "team_id"]].values)) == before_keyset)

    # ---- T6 null expansion is zero and is REPORTED either way --------------
    added = [c for c in dim.columns if c not in KEY]
    nulls = {c: int(merged[c].isna().sum()) for c in added}
    check("T6a no null expansion on any attached column", sum(nulls.values()) == 0,
          json.dumps({k: v for k, v in nulls.items() if v}))
    check("T6b every universe key is covered by the dimension",
          int(universe[KEY].drop_duplicates()
              .merge(dim[KEY], on=KEY, how="left", indicator=True)
              .pipe(lambda d: (d["_merge"] == "left_only").sum())) == 0)

    # ---- T7 a duplicate primary key is REJECTED, and fan-out FAILS ---------
    # Inject a duplicate key and prove validate="m:1" raises rather than fanning out.
    poisoned = pd.concat([dim, dim.iloc[[0]]], ignore_index=True)
    try:
        universe.merge(poisoned, on=KEY, how="left", validate="m:1")
        check("T7a duplicate primary key is rejected by validate='m:1'", False,
              "merge SUCCEEDED on a poisoned dimension -- the guard is not working")
    except pd.errors.MergeError:
        check("T7a duplicate primary key is rejected by validate='m:1'", True)

    # T7b the historical hazard, measured: merging the RAW source on team_id
    # alone fans out. This must fan out -- if it did not, S2 would be wrong.
    naive = universe.merge(raw.drop(columns=["_f", "_l"]), on="team_id", how="left")
    excess = len(naive) - EXPECTED_ROWS
    phx_rows = int((universe["team_id"] == PHOENIX_TEAM_ID).sum())
    check("T7b naive team_id-only merge on the RAW source fans out",
          excess > 0, f"+{excess} rows")
    check("T7c the fan-out is exactly the Phoenix duplication",
          excess == phx_rows, f"excess={excess}, phoenix universe rows={phx_rows}")

    # ---- T8 no arbitrary first/last-row deduplication anywhere -------------
    hits = arbitrary_dedup_calls(HERE / "build_dimension.py")
    check("T8a builder contains no arbitrary first/last-row dedup (AST scan)",
          not hits, "; ".join(hits))
    # The scanner must actually be able to catch the thing it forbids.
    probe = HERE / "_t8_probe.py"
    probe.write_text(
        'import pandas as pd\n'
        'x = pd.DataFrame().drop_duplicates("team_id")\n'
        'y = pd.DataFrame().groupby("team_id").last()\n',
        encoding="utf-8",
    )
    try:
        probe_hits = arbitrary_dedup_calls(probe)
        check("T8a-meta the AST scanner detects a known-bad probe",
              len(probe_hits) == 2, str(probe_hits))
    finally:
        probe.unlink()
    # T8c the decisive test: the artifact must be INVARIANT to source row order.
    # An independent re-derivation of the dimension by interval containment, from
    # a shuffled copy of the source, must reproduce the artifact exactly. If any
    # arbitrary-order dedup were load-bearing, this would differ.
    core = ["team_id", "season", "abbreviation", "city", "arena", "lat", "lon",
            "elevation_ft", "timezone"]
    seasons_all = sorted(pd.read_parquet(
        ROOT / "data" / "masters" / "master_team.parquet", columns=["season"]
    )["season"].unique().tolist())
    order_stable = True
    for seed in (0, 1, 7, 42, 1337):
        sh = raw.sample(frac=1.0, random_state=seed).reset_index(drop=True)
        rebuilt = pd.DataFrame.from_records([
            {**{c: r[c] for c in core if c != "season"}, "season": int(s)}
            for _, r in sh.iterrows() for s in seasons_all
            if r["_f"] <= s <= r["_l"]
        ])[core].sort_values(KEY).reset_index(drop=True)
        ref = dim[core].sort_values(KEY).reset_index(drop=True)
        if not rebuilt.equals(ref):
            order_stable = False
            break
    check("T8c dimension is invariant to source row order (5 shuffles)", order_stable)

    # The dimension's own row count must equal the interval-containment count,
    # i.e. nothing was silently dropped to force uniqueness.
    seasons = sorted(universe["season"].unique().tolist())
    expected_rows = sum(
        1 for _, r in raw.iterrows() for s in seasons if r["_f"] <= s <= r["_l"]
    )
    check("T8b dimension row count equals interval-containment count",
          len(dim) == expected_rows, f"{len(dim)} vs {expected_rows}")

    # ---- T9 PHO/PHX resolved from effective dates, not guessed -------------
    phx = dim[dim["team_id"] == PHOENIX_TEAM_ID].sort_values("season")
    check("T9a Phoenix has exactly one row per season",
          phx["season"].is_unique and len(phx) == len(seasons),
          f"{len(phx)} rows, {phx['season'].nunique()} seasons")
    check("T9b Phoenix 2021-2024 carries abbreviation PHO",
          set(phx.loc[phx["season"] <= 2024, "abbreviation"]) == {"PHO"})
    check("T9c Phoenix 2025+ carries abbreviation PHX",
          set(phx.loc[phx["season"] >= 2025, "abbreviation"]) == {"PHX"})
    check("T9d both Phoenix source rows agree on every physical venue field",
          raw[raw["team_id"] == PHOENIX_TEAM_ID][
              ["city", "arena", "lat", "lon", "elevation_ft", "timezone"]
          ].drop_duplicates().shape[0] == 1)

    # ---- T10 derivation metadata present for every attached column ---------
    documented = set(meta["columns"].keys())
    undocumented = [c for c in dim.columns if c not in documented]
    check("T10a every dimension column carries a derivation in the meta",
          not undocumented, str(undocumented))
    for c in ["elevation_ft", "timezone", "lat", "lon", "utc_offset_hours_jul"]:
        check(f"T10b derivation text non-empty for {c}",
              bool(meta["columns"][c]["derivation"].strip()))
    check("T10c travel companion derivation documents the earth model",
          "6371" in meta["companion"]["venue_pair_travel_v1.csv"]["great_circle_km"])

    # ---- T11 travel matrix invariants --------------------------------------
    piv = vp.pivot(index="from_venue_id", columns="to_venue_id", values="great_circle_km")
    check("T11a travel matrix is square over the dimension's venues",
          set(piv.index) == set(dim["venue_id"].unique()),
          f"{len(piv.index)} venues")
    check("T11b zero diagonal",
          all(abs(piv.loc[v, v]) < 1e-9 for v in piv.index))
    check("T11c symmetric", float((piv - piv.T).abs().to_numpy().max()) < 1e-6)
    viol = sum(
        1 for i in piv.index for j in piv.index for k in piv.index
        if piv.loc[i, k] > piv.loc[i, j] + piv.loc[j, k] + 1e-6
    )
    check("T11d triangle inequality holds", viol == 0, f"{viol} violations")
    # spot-check haversine against an independent closed form on one pair
    a = dim[dim["venue_id"] == "chase_center"].iloc[0]
    b = dim[dim["venue_id"] == "barclays_center"].iloc[0]
    ref = 6371.0088 * math.acos(
        min(1.0, math.sin(math.radians(a["lat"])) * math.sin(math.radians(b["lat"]))
            + math.cos(math.radians(a["lat"])) * math.cos(math.radians(b["lat"]))
            * math.cos(math.radians(b["lon"] - a["lon"])))
    )
    got = float(vp[(vp["from_venue_id"] == "chase_center")
                   & (vp["to_venue_id"] == "barclays_center")]["great_circle_km"].iloc[0])
    check("T11e haversine agrees with spherical-law-of-cosines to 0.01 km",
          abs(ref - got) < 0.01, f"{ref:.4f} vs {got:.4f}")

    # ---- T12 the open-end sentinel cannot collide with a real season -------
    check("T12 open-end sentinel 9999 exceeds every season in the universe",
          9999 > max(seasons), f"max season {max(seasons)}")

    # ------------------------------------------------------------------ out
    failed = [r for r in RESULTS if not r[1]]
    for name, ok, detail in RESULTS:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  -- {detail}" if detail else ""))
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
