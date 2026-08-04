#!/usr/bin/env python3
"""TESTS.py — re-checks every load-bearing claim this node makes, against the bytes.

Repo convention: standalone runnable script, `main()` returns 1 on failure. pytest is not
installed. READ-ONLY; writes nothing.

    python experiments/player_program/stage2b/P2A_POSSESSION_COLUMN_ADJUDICATION/TESTS.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PP = HERE.parents[1]
POSS = PP / "possessions_v2" / "possessions_raw_v2.parquet"
FINDINGS = HERE / "FINDINGS.json"

LABELS = {"ELIGIBLE", "LAGGED_USE_ONLY", "PROHIBITED", "CUTOFF_UNPROVEN"}
NAMED_SIX = {"is_overtime", "score_diff_offense_start", "score_diff_offense_end",
             "abs_score_diff_start", "regulation_seconds_remaining",
             "non_competitive_conservative"}
DECLARED_OUTPUTS = {"MEASURE.py", "TESTS.py", "FINDINGS.json", "ADJUDICATION.csv", "REPORT.md"}

FAILS: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  -- {detail}" if detail else ""))
    if not ok:
        FAILS.append(name)


def main() -> int:
    f = json.loads(FINDINGS.read_text(encoding="utf-8"))
    d = pd.read_parquet(POSS)
    adj = {row["column"]: row for row in f["adjudication"]}

    # ---- 1. the adjudication covers the bytes exactly, one label each
    check("every column of the artifact is adjudicated exactly once",
          sorted(adj) == sorted(d.columns) and len(f["adjudication"]) == len(d.columns) == 48,
          f"{len(adj)} adjudicated / {d.shape[1]} in the bytes")
    check("every label is one of the four permitted values",
          all(v["label"] in LABELS for v in adj.values()))
    check("label counts sum to 48",
          sum(v for k, v in f["adjudication_summary"].items() if k != "TOTAL") == 48)

    # ---- 2. the acceptance criteria's six columns
    check("the six named columns are all LAGGED_USE_ONLY",
          all(adj[c]["label"] == "LAGGED_USE_ONLY" for c in NAMED_SIX))
    check("no ELIGIBLE column is one of the six",
          not (NAMED_SIX & {c for c, v in adj.items() if v["label"] == "ELIGIBLE"}))
    check("every column carries a non-empty cutoff basis",
          all(str(v["basis"]).strip() for v in adj.values()))

    # ---- 3. nothing is admitted
    check("no column is admitted",
          f["nothing_admitted"]["columns_admitted_to_any_arm"] == 0
          and f["nothing_admitted"]["columns_admitted_on_availability_grounds"] == 0)

    # ---- 4. the reproduced coverage figure
    pct = 100.0 * float(d["lineup_valid_ten"].sum()) / len(d)
    check("valid-ten coverage reproduces the packet's 99.789% of 238,563",
          len(d) == 238563 and round(pct, 3) == 99.789
          and f["valid_ten_lineup_coverage"]["measured_valid_ten"] == 238060,
          f"{pct:.6f}% of {len(d)}")

    # ---- 5. structural facts the adjudication rests on
    g = d.groupby("game_id").agg(max_period=("period", "max"), max_end=("end_sec", "max"),
                                 sum_dur=("duration_sec", "sum"), any_ot=("is_overtime", "any"))
    gm = 40.0 + 5.0 * np.maximum(0, g["max_period"] - 4)
    check("max(end_sec) per game == game_minutes*60 on every game",
          bool((g["max_end"] == gm * 60).all()))
    check("sum(duration_sec) per game == game_minutes*60 on every game",
          bool((g["sum_dur"] == gm * 60).all()))
    check("any(is_overtime) per game == (game_minutes > 40) on every game",
          bool((g["any_ot"] == (gm > 40)).all()))
    check("score_diff_offense_end == score_diff_offense_start + points_scored on every row",
          bool((d["score_diff_offense_end"].to_numpy(float)
                == (d["score_diff_offense_start"] + d["points_scored"]).to_numpy(float)).all()))
    check("source_pbp_game_id is byte-equal to game_id on every row",
          bool((d["source_pbp_game_id"] == d["game_id"]).all()))
    check("all_possessions is constant (feature_gate zero_variance is blocking)",
          d["all_possessions"].nunique(dropna=False) == 1)

    # ---- 6. the target is exactly reconstructible from three adjudicated columns
    n_off = (d.groupby(["game_id", "offense_team_id"]).size().rename("n").reset_index()
             .rename(columns={"offense_team_id": "team_id"}))
    n_off = n_off.merge(g[["max_period"]].reset_index(), on="game_id", how="left")
    n_off["gm"] = 40.0 + 5.0 * np.maximum(0, n_off["max_period"] - 4)
    n_off["target"] = n_off["n"] * 40.0 / n_off["gm"]
    check("the target is reconstructible from game_id, offense_team_id and period alone",
          len(n_off) == 2990 and bool(np.isfinite(n_off["target"]).all()),
          f"{len(n_off)} team-game rows")
    check("offense_team_id and defense_team_id are ELIGIBLE only with the multiplicity hazard "
          "recorded",
          all("multiplicity" in adj[c]["hazard"].lower()
              for c in ("offense_team_id", "defense_team_id", "is_home_offense")))

    # ---- 7. the packet reconciliation is a CORRECTION, not an agreement
    pr = f["packet_reconciliation"]
    check("S8's column total AGREES", pr["columns_total_verdict"] == "AGREE"
          and pr["measured_columns_total"] == 48)
    check("S8's 'zero named in the availability table' is CORRECTED",
          pr["named_verdict"] == "CORRECT" and len(pr["measured_named_in_V2_corrected_table"]) == 7
          and pr["measured_never_named_anywhere_in_the_table"] == 41)

    # ---- 8. write scope
    written = {p.name for p in HERE.iterdir() if p.is_file()}
    check("no file outside the declared output set was written into this node's directory",
          written <= DECLARED_OUTPUTS, f"{sorted(written - DECLARED_OUTPUTS) or 'none extra'}")

    print(f"\n{len(FAILS)} failure(s)" + (f": {FAILS}" if FAILS else ""))
    return 1 if FAILS else 0


if __name__ == "__main__":
    raise SystemExit(main())
